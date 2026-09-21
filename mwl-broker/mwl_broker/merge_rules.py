"""Field-level merge: which source wins for a single DICOM attribute.

The default merge takes the whole item from the highest-priority source that
knows the case. That is not always what a hospital wants: the patient
demographics may be most reliable in the HIS feed, while the study description
comes from the RIS. A merge rule names a tag and the order in which sources are
asked for it — everything else still comes from the winning item.
"""
import logging

from sqlalchemy import select

from .db import session_factory
from .models import MergeRule

log = logging.getLogger("mwl_broker.merge_rules")

# Reading a value out of a worklist item: tags live either at the top level or
# inside the scheduled procedure step sequence.
SPS_TAGS = {
    "ScheduledProcedureStepID", "ScheduledStationAETitle", "Modality",
    "ScheduledProcedureStepStartDate", "ScheduledProcedureStepStartTime",
    "ScheduledPerformingPhysicianName", "ScheduledProcedureStepDescription",
    "ScheduledProcedureStepLocation", "RequestedContrastAgent",
}


def _read(ds, tag: str):
    """Read a tag from the item, looking inside the SPS sequence when needed."""
    value = ds.get(tag, "")
    if value not in ("", None):
        return value
    if tag in SPS_TAGS:
        sps_seq = ds.get("ScheduledProcedureStepSequence") or []
        if sps_seq:
            return sps_seq[0].get(tag, "")
    return ""


def _write(ds, tag: str, value) -> None:
    """Set an attribute by keyword.

    pydicom writes by *attribute* (`setattr`), not by string key — `ds[tag] = …`
    raises "Dataset items must be 'DataElement' instances".
    """
    if value in ("", None):
        return
    if tag in SPS_TAGS:
        sps_seq = ds.get("ScheduledProcedureStepSequence") or []
        if not sps_seq:
            from pydicom.dataset import Dataset

            sps_seq = [Dataset()]
            ds.ScheduledProcedureStepSequence = sps_seq
        setattr(sps_seq[0], tag, value)
    else:
        setattr(ds, tag, value)


def list_rules() -> list[dict]:
    with session_factory()() as s:
        rows = s.scalars(select(MergeRule).order_by(MergeRule.tag)).all()
        return [_as_dict(r) for r in rows]


def _as_dict(row: MergeRule) -> dict:
    return {
        "id": row.id,
        "tag": row.tag,
        "sources": [x for x in (row.sources or "").split(",") if x],
        "enabled": row.enabled,
        "created_at": row.created_at,
    }


def get_rule(rule_id: int) -> dict | None:
    with session_factory()() as s:
        row = s.get(MergeRule, rule_id)
        return _as_dict(row) if row is not None else None


def upsert_rule(tag: str, sources: list[str], enabled: bool = True,
                rule_id: int | None = None) -> dict:
    """Create or replace a rule. One rule per tag."""
    with session_factory()() as s:
        row = s.get(MergeRule, rule_id) if rule_id else None
        if row is None:
            row = s.scalars(select(MergeRule).where(MergeRule.tag == tag)).first()
        if row is None:
            row = MergeRule(tag=tag)
            s.add(row)
        row.tag = tag
        row.sources = ",".join(s.strip() for s in sources if s.strip())
        row.enabled = enabled
        s.commit()
        s.refresh(row)
        return _as_dict(row)


def delete_rule(rule_id: int) -> bool:
    with session_factory()() as s:
        row = s.get(MergeRule, rule_id)
        if row is None:
            return False
        s.delete(row)
        s.commit()
        return True


def active_rules() -> list[dict]:
    return [r for r in list_rules() if r["enabled"] and r["sources"]]


def apply_field_rules(
    merged: list[tuple],
    collected: list[tuple],
) -> tuple[list[tuple], list[dict]]:
    """Overwrite single fields from other sources, as configured.

    `merged` is the deduped list (dataset, source) in priority order, `collected`
    the raw per-source answers. Returns the adjusted list plus a report of what
    was changed — the preview shows it, so a rule can be verified before it
    matters.
    """
    rules = active_rules()
    if not rules:
        return merged, []

    by_source = {src.name: answers for src, answers in collected}
    # index the answers of every source by dedupe key for quick lookup
    from .upstream import dedupe_key

    indexed: dict[str, dict[tuple, object]] = {
        name: {dedupe_key(ds): ds for ds in answers} for name, answers in by_source.items()
    }

    changes: list[dict] = []
    for ds, winner in merged:
        key = dedupe_key(ds)
        for rule in rules:
            tag = rule["tag"]
            for source_name in rule["sources"]:
                if source_name == winner.name:
                    continue
                other = indexed.get(source_name, {}).get(key)
                if other is None:
                    continue
                value = _read(other, tag)
                if value in ("", None):
                    continue
                before = _read(ds, tag)
                _write(ds, tag, value)
                changes.append({
                    "accession": str(ds.get("AccessionNumber", "") or ""),
                    "tag": tag,
                    "from": source_name,
                    "before": str(before or ""),
                    "after": str(value),
                })
                break  # first matching source in the rule wins
    if changes:
        log.info("field merge applied %d change(s) from %d rule(s)", len(changes), len(rules))
    return merged, changes
