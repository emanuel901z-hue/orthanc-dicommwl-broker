"""Patient identifier reconciliation (IHE Patient Information Reconciliation).

Hospitals end up with several patient IDs for the same person (an emergency
admission that is merged later, a second MRN from another system). The RIS
announces that with an **ADT** message, and this module keeps the result:

* `merge(old, new)` — **A40**: the old ID is retired, everything moves to the new
  one. The worklist answer is rewritten, the routing provenance follows.
* `link(old, new)` — **A24**: the two records are the *same person*, but both IDs
  stay valid. Nothing is moved and nothing is rewritten; the link is what makes
  `resolve()` answer "these belong together".
* `resolve(id)` — follows chains (A→B→C) and is cycle-safe, across merges *and*
  links.
* `answer_mapping(ids)` — the mapping for worklist answers: **merges only**,
  because rewriting an answer for a link would retire an ID that is still valid.
* `unmerge(id)` / `unlink(id)` — reversible; the entry stays for the audit trail.

The events themselves (A08/A24/A40/A47) are handled in `adt.py`, which both the
REST endpoint and the MLLP listener call. What is **not** implemented: PIX/PDQ
queries; those are named as boundaries in the conformance statement.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from .db import session_factory
from .models import PatientMerge

log = logging.getLogger("mwl_broker.merges")

MAX_CHAIN = 10   # A→B→C… ; a longer chain is a data problem, not a use case

KIND_MERGE = "merge"
KIND_LINK = "link"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def list_merges(active_only: bool = True) -> list[dict]:
    with session_factory()() as s:
        query = select(PatientMerge).order_by(PatientMerge.ts.desc())
        if active_only:
            query = query.where(PatientMerge.active.is_(True))
        return [_as_dict(row) for row in s.scalars(query).all()]


def _as_dict(row: PatientMerge) -> dict:
    return {
        "id": row.id,
        "ts": row.ts,
        "old_patient_id": row.old_patient_id,
        "new_patient_id": row.new_patient_id,
        "reason": row.reason,
        "actor": row.actor,
        "origin": row.origin,
        "kind": row.kind or KIND_MERGE,
        "active": row.active,
    }


def _record(old_patient_id: str, new_patient_id: str, kind: str, reason: str,
            actor: str, origin: str) -> tuple[dict, bool]:
    """Store the relation. Returns (row, created) — a repeat is not an error."""
    old = (old_patient_id or "").strip()
    new = (new_patient_id or "").strip()
    if not old or not new:
        raise ValueError("both patient IDs are required")
    if old == new:
        raise ValueError("old and new patient ID are identical")
    with session_factory()() as s:
        existing = s.scalars(
            select(PatientMerge).where(
                PatientMerge.old_patient_id == old,
                PatientMerge.new_patient_id == new,
                PatientMerge.active.is_(True),
            )
        ).first()
        if existing is not None:
            if kind == KIND_MERGE and (existing.kind or KIND_MERGE) != KIND_MERGE:
                # A link can be followed by the merge it anticipated (A24, then
                # A40 for the same pair). The stronger relation wins — and the
                # merge's *effect* has to happen, otherwise the old identifier
                # would never be retired and the answer never rewritten.
                existing.kind = KIND_MERGE
                existing.reason = reason.strip()[:256] or existing.reason
                s.commit()
                s.refresh(existing)
                log.info("patient link %s → %s upgraded to a merge",
                         existing.old_patient_id, existing.new_patient_id)
                return _as_dict(existing), True
            return _as_dict(existing), False
        # the other direction would make the chain ambiguous
        reverse = s.scalars(
            select(PatientMerge).where(
                PatientMerge.old_patient_id == new,
                PatientMerge.new_patient_id == old,
                PatientMerge.active.is_(True),
            )
        ).first()
        if reverse is not None:
            raise ValueError(
                f"{new} is already merged into {old} — the other direction would "
                "be ambiguous. Undo that merge first."
            )
        row = PatientMerge(old_patient_id=old, new_patient_id=new, kind=kind,
                           reason=reason.strip()[:256], actor=actor, origin=origin)
        s.add(row)
        s.commit()
        s.refresh(row)
        return _as_dict(row), True


def merge(old_patient_id: str, new_patient_id: str, reason: str = "",
          actor: str = "api", origin: str = "manual") -> dict:
    """Record that `old_patient_id` is now `new_patient_id` (ADT A40).

    The old identifier is retired: the stored data moves to the new one.
    """
    result, created = _record(old_patient_id, new_patient_id, KIND_MERGE, reason,
                              actor, origin)
    if created:
        log.info("patient ID merged: %s → %s (%s)", result["old_patient_id"],
                 result["new_patient_id"], origin)
        moved_items, moved_seen = _apply_to_data(result["old_patient_id"],
                                                 result["new_patient_id"])
        # the operator asked "what did that do?" — answer it instead of guessing
        result["moved_items"] = moved_items
        result["moved_seen"] = moved_seen
    return result


def link(old_patient_id: str, new_patient_id: str, reason: str = "",
         actor: str = "api", origin: str = "manual") -> dict:
    """Record that two identifiers belong to the same person (ADT A24).

    Deliberately *not* a merge: both identifiers stay valid, so no data moves and
    no worklist answer is rewritten. The link is visible through `resolve()` and
    in the operator's list — that is what an A24 means.
    """
    result, created = _record(old_patient_id, new_patient_id, KIND_LINK, reason,
                              actor, origin)
    if created:
        log.info("patient IDs linked: %s ↔ %s (%s)", result["old_patient_id"],
                 result["new_patient_id"], origin)
    # a link moves nothing, by definition — say it explicitly
    result.setdefault("moved_items", 0)
    result.setdefault("moved_seen", 0)
    return result


def unmerge(merge_id: int) -> bool:
    """Undo a merge or a link (the entry stays for the audit trail, marked inactive)."""
    with session_factory()() as s:
        row = s.get(PatientMerge, merge_id)
        if row is None or not row.active:
            return False
        row.active = False
        s.commit()
        log.info("patient %s %s undone (%s → %s)", row.kind or KIND_MERGE, merge_id,
                 row.old_patient_id, row.new_patient_id)
        return True


def unlink(old_patient_id: str, new_patient_id: str = "") -> int:
    """Take links back (ADT A47). Returns how many were deactivated.

    Only links: an A47 says "these records are not the same person after all",
    which must never silently undo a merge.
    """
    old = (old_patient_id or "").strip()
    if not old:
        return 0
    with session_factory()() as s:
        query = select(PatientMerge).where(
            PatientMerge.old_patient_id == old,
            PatientMerge.kind == KIND_LINK,
            PatientMerge.active.is_(True),
        )
        if new_patient_id.strip():
            query = query.where(PatientMerge.new_patient_id == new_patient_id.strip())
        rows = s.scalars(query).all()
        for row in rows:
            row.active = False
        s.commit()
    if rows:
        log.info("patient link(s) undone for %s: %d", old, len(rows))
    return len(rows)


def resolve(patient_id: str) -> str:
    """Follow the chain to the current ID (cycle-safe), merges *and* links."""
    return _resolve(patient_id, kinds=None)


def resolve_many(patient_ids: list[str]) -> dict[str, str]:
    """Resolve a batch — one query instead of one per ID."""
    return _resolve_many(patient_ids, kinds=None)


def answer_mapping(patient_ids: list[str]) -> dict[str, str]:
    """The mapping for worklist answers: **merges only**.

    A link does not retire an identifier, so an answer that arrived under the
    linked ID has to stay as it is — rewriting it would tell the modality to
    forget an ID that is still valid.
    """
    return _resolve_many(patient_ids, kinds=(KIND_MERGE,))


def _relations(kinds: tuple[str, ...] | None) -> list[PatientMerge]:
    with session_factory()() as s:
        query = select(PatientMerge).where(PatientMerge.active.is_(True))
        if kinds:
            query = query.where(PatientMerge.kind.in_(kinds))
        return list(s.scalars(query).all())


def _follow(current: str, mapping: dict[str, str]) -> str:
    seen: set[str] = set()
    for _ in range(MAX_CHAIN):
        if not current or current in seen:      # cycle: stop instead of looping
            if current in seen:
                log.warning("patient ID chain has a cycle at %s", current)
            return current
        seen.add(current)
        nxt = mapping.get(current)
        if not nxt or nxt == current:
            return current
        current = nxt
    log.warning("patient ID chain longer than %d for %s", MAX_CHAIN, current)
    return current


def _resolve(patient_id: str, kinds: tuple[str, ...] | None) -> str:
    current = (patient_id or "").strip()
    if not current:
        return current
    mapping = {row.old_patient_id: row.new_patient_id for row in _relations(kinds)}
    return _follow(current, mapping)


def _resolve_many(patient_ids: list[str], kinds: tuple[str, ...] | None) -> dict[str, str]:
    mapping = {row.old_patient_id: row.new_patient_id for row in _relations(kinds)}
    return {pid: _follow((pid or "").strip(), mapping) for pid in patient_ids}


def _apply_to_data(old: str, new: str) -> tuple[int, int]:
    """Follow the merge through the data that is already stored.

    * local worklist items: the modality must see the current ID
    * routing provenance (seen_items): an image acquired under the old ID must
      still be routed by its worklist entry — so the provenance moves with it
    * cached worklist entries: they are upstream snapshots and are rewritten when
      they are served, so nothing to do here
    """
    from .models import LocalWorklistItem, SeenItem

    with session_factory()() as s:
        items = s.scalars(
            select(LocalWorklistItem).where(LocalWorklistItem.patient_id == old)
        ).all()
        for item in items:
            item.patient_id = new
        seen = s.scalars(select(SeenItem).where(SeenItem.patient_id == old)).all()
        for row in seen:
            row.patient_id = new
        s.commit()
    if items or seen:
        log.info("patient merge %s → %s applied to %d local item(s) and %d provenance row(s)",
                 old, new, len(items), len(seen))
    return len(items), len(seen)


def rewrite_datasets(items: list, mapping: dict[str, str]) -> int:
    """Rewrite PatientID in worklist answers (returns how many were changed)."""
    changed = 0
    for ds in items:
        pid = str(ds.get("PatientID", "") or "")
        if pid and pid in mapping and mapping[pid] != pid:
            ds.PatientID = mapping[pid]
            changed += 1
    return changed
