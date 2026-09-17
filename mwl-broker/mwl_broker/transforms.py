"""DICOM attribute transformations applied before forwarding a C-STORE.

Rules are validated against the DICOM data dictionary (pydicom) — only real
keywords are accepted, and UIDs that must stay consistent with the forwarded
instance are blocked on purpose. A failing operation never breaks the store:
it is logged and the remaining operations still run.
"""
import logging
import re
from dataclasses import dataclass

from pydicom.datadict import tag_for_keyword
from sqlalchemy import select

from .models import TransformRule

log = logging.getLogger("mwl_broker.transforms")


@dataclass(frozen=True)
class TransformCfg:
    """Detached copy of a transform rule — safe across DIMSE worker threads."""

    id: int
    name: str
    priority: int
    source_id: int | None
    target_id: int | None
    operations: list

OPS = ("set", "remove", "prefix", "suffix", "replace", "copy")

# Rewriting these would silently break PACS linkage (study/series/instance
# identity). Blocked deliberately — such changes belong in a dedicated
# migration tool, not in a forwarding transform.
PROTECTED_TAGS = frozenset({
    "SOPInstanceUID",
    "StudyInstanceUID",
    "SeriesInstanceUID",
    "SOPClassUID",
    "MediaStorageSOPInstanceUID",
    "MediaStorageSOPClassUID",
})


def _valid_keyword(tag) -> bool:
    return isinstance(tag, str) and bool(tag) and tag_for_keyword(tag) is not None


def validate_operations(operations) -> list[str]:
    """Return validation errors for an operations list (empty = valid)."""
    if not isinstance(operations, list) or not operations:
        return ["operations must be a non-empty list"]
    errors: list[str] = []
    for i, op in enumerate(operations):
        where = f"operation {i + 1}"
        if not isinstance(op, dict):
            errors.append(f"{where}: must be an object")
            continue
        kind = op.get("op")
        if kind not in OPS:
            errors.append(f"{where}: unknown op {kind!r} (allowed: {', '.join(OPS)})")
            continue
        tag = op.get("tag")
        if not _valid_keyword(tag):
            errors.append(f"{where}: unknown DICOM keyword {tag!r}")
            continue
        if tag in PROTECTED_TAGS:
            errors.append(f"{where}: {tag} must not be modified (PACS linkage)")
        if kind in ("set", "prefix", "suffix") and "value" not in op:
            errors.append(f"{where}: 'value' is required for op {kind!r}")
        if kind == "replace":
            if "pattern" not in op:
                errors.append(f"{where}: 'pattern' is required for op 'replace'")
            else:
                try:
                    re.compile(str(op["pattern"]))
                except re.error as exc:
                    errors.append(f"{where}: invalid regex in 'pattern' ({exc})")
            if "value" not in op:
                errors.append(f"{where}: 'value' is required for op 'replace'")
        if kind == "copy" and not _valid_keyword(op.get("from_tag")):
            errors.append(f"{where}: unknown source keyword {op.get('from_tag')!r}")
    return errors


def applicable(session, source_id: int | None, target_id: int | None) -> list[TransformCfg]:
    """Enabled rules matching this source/target scope, in priority order.

    A NULL scope means "any". Detached copies are returned so callers can use
    them outside the session (DIMSE worker threads).
    """
    rows = session.scalars(
        select(TransformRule)
        .where(TransformRule.enabled.is_(True))
        .order_by(TransformRule.priority, TransformRule.id)
    ).all()
    return [
        TransformCfg(
            id=r.id, name=r.name, priority=r.priority,
            source_id=r.source_id, target_id=r.target_id,
            operations=list(r.operations or []),
        )
        for r in rows
        if (r.source_id is None or r.source_id == source_id)
        and (r.target_id is None or r.target_id == target_id)
    ]


def apply_transforms(ds, rules: list[TransformCfg]) -> tuple[list[str], list[str]]:
    """Apply rules to `ds` in order.

    Returns (applied_rule_names, error_messages). Errors are per-operation
    and never abort the forward.
    """
    applied: list[str] = []
    errors: list[str] = []
    for rule in rules:
        for i, op in enumerate(rule.operations or []):
            try:
                _apply_op(ds, op)
            except Exception as exc:  # a bad value must not lose the instance
                msg = f"{rule.name}[{i + 1}]: {exc}"
                errors.append(msg)
                log.warning("transform operation failed: %s", msg)
        applied.append(rule.name)
    return applied, errors


def _apply_op(ds, op: dict) -> None:
    kind = op["op"]
    tag = op["tag"]
    if kind == "remove":
        if hasattr(ds, tag):
            delattr(ds, tag)
    elif kind == "set":
        setattr(ds, tag, op["value"])
    elif kind == "prefix":
        setattr(ds, tag, str(op["value"]) + str(getattr(ds, tag, "") or ""))
    elif kind == "suffix":
        setattr(ds, tag, str(getattr(ds, tag, "") or "") + str(op["value"]))
    elif kind == "replace":
        current = str(getattr(ds, tag, "") or "")
        setattr(ds, tag, re.sub(str(op["pattern"]), str(op["value"]), current))
    elif kind == "copy":
        source = getattr(ds, op["from_tag"], None)
        if source is None:
            raise ValueError(f"source tag {op['from_tag']} is empty")
        setattr(ds, tag, source)
    else:  # pragma: no cover — validate_operations rejects unknown ops
        raise ValueError(f"unknown op {kind!r}")
