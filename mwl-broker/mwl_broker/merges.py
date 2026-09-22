"""Patient identifier reconciliation (IHE Patient Information Reconciliation).

Hospitals end up with several patient IDs for the same person (an emergency
admission that is merged later, a second MRN from another system). The RIS
announces that with an **ADT A40** message, and from then on the images that
were acquired under the old ID belong to the new one.

This module keeps the merges and resolves an ID through them:

* `merge(old, new)` — recorded, audited, and reversible
* `resolve(id)` — follows chains (A→B→C) and is cycle-safe
* the worklist answer and the routing provenance both use the resolved ID, so a
  merge changes where images are routed *and* what the modality sees

Without ADT (or for a quick fix) the merge can be entered in the UI — the same
table, the same effect. What is **not** implemented: the IHE link/unlink
messages (A24/A47) and PIX/PDQ queries; those are named as boundaries in the
conformance statement.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from .db import session_factory
from .models import PatientMerge

log = logging.getLogger("mwl_broker.merges")

MAX_CHAIN = 10   # A→B→C… ; a longer chain is a data problem, not a use case


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
        "active": row.active,
    }


def merge(old_patient_id: str, new_patient_id: str, reason: str = "",
          actor: str = "api", origin: str = "manual") -> dict:
    """Record that `old_patient_id` is now `new_patient_id`."""
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
            return _as_dict(existing)
        # a merge in the other direction would make the chain ambiguous
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
        row = PatientMerge(old_patient_id=old, new_patient_id=new,
                           reason=reason.strip()[:256], actor=actor, origin=origin)
        s.add(row)
        s.commit()
        s.refresh(row)
        result = _as_dict(row)
    log.info("patient ID merged: %s → %s (%s)", old, new, origin)
    _apply_to_data(old, new)
    return result


def unmerge(merge_id: int) -> bool:
    """Undo a merge (the entry stays for the audit trail, marked inactive)."""
    with session_factory()() as s:
        row = s.get(PatientMerge, merge_id)
        if row is None or not row.active:
            return False
        row.active = False
        s.commit()
        log.info("patient merge %s undone (%s → %s)",
                 merge_id, row.old_patient_id, row.new_patient_id)
        return True


def resolve(patient_id: str) -> str:
    """Follow the merge chain to the current ID (cycle-safe)."""
    current = (patient_id or "").strip()
    if not current:
        return current
    with session_factory()() as s:
        rows = s.scalars(
            select(PatientMerge).where(PatientMerge.active.is_(True))
        ).all()
    mapping = {row.old_patient_id: row.new_patient_id for row in rows}
    seen: set[str] = set()
    for _ in range(MAX_CHAIN):
        if current in seen:                      # cycle: stop instead of looping
            log.warning("patient ID merge chain has a cycle at %s", current)
            return current
        seen.add(current)
        nxt = mapping.get(current)
        if not nxt or nxt == current:
            return current
        current = nxt
    log.warning("patient ID merge chain longer than %d for %s", MAX_CHAIN, patient_id)
    return current


def resolve_many(patient_ids: list[str]) -> dict[str, str]:
    """Resolve a batch — one query instead of one per ID."""
    with session_factory()() as s:
        rows = s.scalars(select(PatientMerge).where(PatientMerge.active.is_(True))).all()
    mapping = {row.old_patient_id: row.new_patient_id for row in rows}
    out: dict[str, str] = {}
    for pid in patient_ids:
        current = (pid or "").strip()
        seen: set[str] = set()
        for _ in range(MAX_CHAIN):
            if not current or current in seen:
                break
            seen.add(current)
            nxt = mapping.get(current)
            if not nxt or nxt == current:
                break
            current = nxt
        out[pid] = current
    return out


def _apply_to_data(old: str, new: str) -> None:
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


def rewrite_datasets(items: list, mapping: dict[str, str]) -> int:
    """Rewrite PatientID in worklist answers (returns how many were changed)."""
    changed = 0
    for ds in items:
        pid = str(ds.get("PatientID", "") or "")
        if pid and pid in mapping and mapping[pid] != pid:
            ds.PatientID = mapping[pid]
            changed += 1
    return changed
