"""ADT messages the broker acts on (IHE Patient Information Reconciliation).

An ADT feed is how a hospital tells everyone that patient data changed. The
broker cares about four events:

| Event | What it means                              | What the broker does |
|-------|--------------------------------------------|----------------------|
| `A08`, `A31` | patient information update            | rewrites the demographics of its **own** worklist entries (emergencies, unscheduled exams); a merge-retired ID is resolved first |
| `A24` | two records are the same person (link)      | records a **link**: both IDs stay valid, no answer is rewritten |
| `A40` | the old identifier is retired (merge)       | records the merge and moves the stored data to the current ID |
| `A47` | the link was wrong (unlink)                 | takes **links** back — never a merge |

Everything else is recognised and reported, not applied.

Both transports call this module (the REST endpoint and the MLLP listener), so an
`A08` that arrives over MLLP behaves exactly like one that arrives over HTTP.

Not done here, on purpose: an `A08` does **not** rewrite cached worklist
snapshots. The cache mirrors the upstream, is only served while the upstream is
down, and has a short stale window (`cache_stale_max_s`, default 120 s) — and the
message came from that upstream, so it is alive when it matters. The alternative
(scanning every cached payload) would cost more than the risk.
"""
import logging

from . import hl7, local_worklist, merges, metrics

log = logging.getLogger("mwl_broker.adt")

EVENT_UPDATE = "A08"
# A31 ("update person information") is the same kind of change as A08 — which of
# the two a house sends is a property of its RIS/KIS, not a semantic difference
# for us. Found in a foreign sample set (dcm4che/MESA).
EVENT_UPDATE_ALT = "A31"
EVENT_LINK = "A24"
EVENT_MERGE = "A40"
EVENT_UNLINK = "A47"

HANDLED = (EVENT_UPDATE, EVENT_UPDATE_ALT, EVENT_LINK, EVENT_MERGE, EVENT_UNLINK)

ACTION_MERGED = "merged"
ACTION_LINKED = "linked"
ACTION_UNLINKED = "unlinked"
ACTION_UPDATED = "updated"
ACTION_NA = "not-applicable"


def apply(text: str, *, actor: str = "hl7", transport: str = "http",
          dry_run: bool = False) -> dict:
    """Parse and apply one ADT message. Returns what happened (never raises)."""
    parsed = hl7.parse_adt(text)
    event = parsed["event"]
    result = {
        "dry_run": dry_run,
        "event": event,
        "control_id": parsed["control_id"],
        "old_patient_id": parsed["old_patient_id"],
        "new_patient_id": parsed["new_patient_id"],
        "action": ACTION_NA,
        "record_id": None,
        "updated_items": 0,
        "warnings": list(parsed["warnings"]),
    }

    if event not in HANDLED:
        result["warnings"].append(
            f"{event or 'unknown'} is not handled "
            "(A08/A31, A24, A40 and A47 are)")
        _log(parsed, result["action"], transport, text, dry_run)
        return result
    if result["warnings"]:
        # A message we cannot apply must not be applied halfway.
        _log(parsed, "rejected", transport, text, dry_run,
             error="; ".join(result["warnings"]))
        result["action"] = "rejected"
        return result

    if dry_run:
        result["action"] = {
            EVENT_MERGE: ACTION_MERGED, EVENT_LINK: ACTION_LINKED,
            EVENT_UNLINK: ACTION_UNLINKED, EVENT_UPDATE: ACTION_UPDATED,
            EVENT_UPDATE_ALT: ACTION_UPDATED,
        }[event]
        return result

    try:
        if event == EVENT_MERGE:
            row = merges.merge(parsed["old_patient_id"], parsed["new_patient_id"],
                               reason=f"ADT A40 {parsed['control_id']}",
                               actor=actor, origin="adt")
            result.update(action=ACTION_MERGED, record_id=row["id"])
        elif event == EVENT_LINK:
            row = merges.link(parsed["old_patient_id"], parsed["new_patient_id"],
                              reason=f"ADT A24 {parsed['control_id']}",
                              actor=actor, origin="adt")
            result.update(action=ACTION_LINKED, record_id=row["id"])
        elif event == EVENT_UNLINK:
            result.update(
                action=ACTION_UNLINKED,
                updated_items=merges.unlink(parsed["old_patient_id"],
                                            parsed["new_patient_id"]),
            )
        else:  # A08 / A31
            result.update(
                action=ACTION_UPDATED,
                updated_items=_update_demographics(parsed),
            )
    except ValueError as exc:
        result["warnings"].append(str(exc))
        result["action"] = "rejected"
        _log(parsed, "rejected", transport, text, dry_run, error=str(exc))
        return result

    _log(parsed, result["action"], transport, text, dry_run)
    metrics.HL7_MESSAGES.labels(transport=transport, result=result["action"]).inc()
    return result


def _update_demographics(parsed: dict) -> int:
    """Apply an A08 to the broker's own worklist entries.

    A merge-retired ID is resolved first (its entries already live under the
    current one); a *link* is not followed, because both IDs stay valid and may
    each have their own entries.
    """
    patient_id = parsed["new_patient_id"]
    current = merges.answer_mapping([patient_id]).get(patient_id, patient_id)
    return local_worklist.update_demographics(
        current,
        patient_name=parsed["patient_name"],
        birth_date=parsed["birth_date"],
        sex=parsed["sex"],
    )


def _log(parsed: dict, action: str, transport: str, text: str, dry_run: bool,
         error: str = "") -> None:
    """Record the message for troubleshooting — never on a dry run."""
    if dry_run:
        return
    local_worklist.log_hl7(transport, parsed, action, error, raw=text)
