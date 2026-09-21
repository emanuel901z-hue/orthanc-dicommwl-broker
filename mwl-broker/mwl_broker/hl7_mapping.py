"""HL7 → DICOM field mapping: read extra values out of the ORM message.

The built-in parser covers the standard fields (patient, order, modality,
scheduling). Hospitals regularly put extra information somewhere else — the room
in OBR-18, the contrast agent in a ZDS segment, the requesting physician in
ORC-12. A mapping names the HL7 location and the DICOM worklist attribute it
should fill, so nobody has to change code for a local convention.

Nothing is applied unless a mapping exists — the standard behaviour is unchanged.
"""
import logging

from sqlalchemy import select

from . import hl7
from .db import session_factory
from .models import Hl7FieldMap

log = logging.getLogger("mwl_broker.hl7_mapping")


def list_maps() -> list[dict]:
    with session_factory()() as s:
        rows = s.scalars(select(Hl7FieldMap).order_by(Hl7FieldMap.segment, Hl7FieldMap.field)).all()
        return [_as_dict(r) for r in rows]


def _as_dict(row: Hl7FieldMap) -> dict:
    return {
        "id": row.id,
        "segment": row.segment,
        "field": row.field,
        "component": row.component,
        "target_tag": row.target_tag,
        "enabled": row.enabled,
        "created_at": row.created_at,
    }


def get_map(map_id: int) -> dict | None:
    with session_factory()() as s:
        row = s.get(Hl7FieldMap, map_id)
        return _as_dict(row) if row is not None else None


def upsert_map(segment: str, field: int, target_tag: str, component: int = 0,
               enabled: bool = True, map_id: int | None = None) -> dict:
    segment = segment.strip().upper()
    with session_factory()() as s:
        row = s.get(Hl7FieldMap, map_id) if map_id else None
        if row is None:
            row = s.scalars(select(Hl7FieldMap).where(
                Hl7FieldMap.segment == segment,
                Hl7FieldMap.field == field,
                Hl7FieldMap.component == component,
            )).first()
        if row is None:
            row = Hl7FieldMap(segment=segment, field=field, component=component)
            s.add(row)
        row.target_tag = target_tag.strip()
        row.enabled = enabled
        s.commit()
        s.refresh(row)
        return _as_dict(row)


def delete_map(map_id: int) -> bool:
    with session_factory()() as s:
        row = s.get(Hl7FieldMap, map_id)
        if row is None:
            return False
        s.delete(row)
        s.commit()
        return True


def _read_location(segments: dict[str, list[list[str]]], segment: str, field: int,
                   component: int) -> str:
    """Read one HL7 location: segment, field number, component index."""
    blocks = segments.get(segment.upper()) or []
    if not blocks:
        return ""
    raw = hl7._field(blocks[0], field, msh=(segment.upper() == "MSH"))
    if not raw:
        return ""
    # components are counted the HL7 way (1-based: OBR-18.2 = second component);
    # 0 means "the whole field"
    return hl7._component(raw, component - 1) if component else raw


def apply_maps(parsed: dict, raw_text: str) -> tuple[dict, list[dict]]:
    """Apply the configured mappings to a parsed message.

    Returns the (possibly extended) parsed dict and a report of what was filled —
    the dry run shows it, so a mapping can be verified before it matters.
    """
    rules = [m for m in list_maps() if m["enabled"]]
    if not rules:
        return parsed, []

    segments = {}
    for segment in hl7._segments(raw_text):
        segments.setdefault(segment[0].upper(), []).append(segment)

    applied: list[dict] = []
    for rule in rules:
        value = _read_location(segments, rule["segment"], rule["field"], rule["component"])
        if not value:
            continue
        parsed.setdefault("mapped", {})
        parsed["mapped"][rule["target_tag"]] = value
        applied.append({
            "from": f"{rule['segment']}-{rule['field']}"
                    + (f".{rule['component']}" if rule["component"] else ""),
            "tag": rule["target_tag"],
            "value": value,
        })
    if applied:
        log.info("HL7 mapping filled %d extra field(s)", len(applied))
    return parsed, applied
