"""Dry-run simulation of routing and modify rules.

Both entry points call exactly the functions the live path uses
(`routing.resolve`, `transforms.applicable`/`apply_transforms`), so a
simulation cannot drift from reality. Nothing is sent, nothing is stored —
only the decision and the tag diff are reported.
"""
import logging

from pydicom.dataset import Dataset

from . import routing, transforms
from .models import MwlSource, PacsTarget

log = logging.getLogger("mwl_broker.simulate")


def simulate_route(session, accession: str = "", study_uid: str = "") -> dict:
    """Where would an instance with this accession/study go?"""
    decision = routing.resolve(session, accession, study_uid)
    source = session.get(MwlSource, decision.source_id) if decision.source_id else None
    return {
        "accession": accession,
        "study_uid": study_uid,
        "matched_via": decision.matched_via,
        "source_id": decision.source_id,
        "source_name": source.name if source is not None else None,
        "target_id": decision.target.id if decision.target else None,
        "target_name": decision.target.name if decision.target else None,
        "rule_id": decision.rule_id,
        "reason": decision.reason,
    }


def _build_dataset(values: dict, accession: str, study_uid: str):
    """Build a dataset from tag/value pairs; report tags that cannot be set."""
    ds = Dataset()
    errors: list[str] = []
    if accession:
        values = {**values, "AccessionNumber": values.get("AccessionNumber", accession)}
    if study_uid:
        values = {**values, "StudyInstanceUID": values.get("StudyInstanceUID", study_uid)}
    for tag, value in values.items():
        try:
            setattr(ds, tag, value)
        except Exception as exc:  # wrong VR/format — report, keep simulating
            errors.append(f"{tag}: {exc}")
    return ds, errors


def simulate_transform(session, values: dict, accession: str = "", study_uid: str = "",
                       source_id: int | None = None,
                       target_id: int | None = None) -> dict:
    """Which modify rules would apply, and how would the tags change?"""
    decision = routing.resolve(session, accession, study_uid)
    if source_id is None:
        source_id = decision.source_id
    if target_id is None:
        target_id = decision.target.id if decision.target else None

    ds, build_errors = _build_dataset(values or {}, accession, study_uid)
    before = {tag: str(ds.get(tag, "")) for tag in list(values or {}) + ["AccessionNumber", "StudyInstanceUID"]}

    rules = transforms.applicable(session, source_id, target_id) if target_id else []
    applied, errors = transforms.apply_transforms(ds, rules)

    changes = []
    for tag in before:
        after = str(ds.get(tag, "")) if hasattr(ds, tag) else ""
        if before[tag] != after:
            changes.append({"tag": tag, "before": before[tag], "after": after})

    source = session.get(MwlSource, source_id) if source_id else None
    target = session.get(PacsTarget, target_id) if target_id else None
    return {
        "accession": accession,
        "study_uid": study_uid,
        "matched_via": decision.matched_via,
        "source_id": source_id,
        "source_name": source.name if source is not None else None,
        "target_id": target_id,
        "target_name": target.name if target is not None else None,
        "rule_id": decision.rule_id,
        "reason": decision.reason,
        "rules_applied": applied,
        "changes": changes,
        "errors": build_errors + errors,
    }


# ---------------------------------------------------------------------------
# Worklist preview (A9) and the per-source C-FIND test (A8)
# ---------------------------------------------------------------------------

# What the operator sees. PatientName/PatientID are PHI and only appear when
# `simulate_show_phi` is switched on deliberately (health panel shows it).
PHI_FREE_FIELDS = (
    ("accession", "AccessionNumber"),
    ("study_uid", "StudyInstanceUID"),
    ("requested_procedure_id", "RequestedProcedureID"),
)
PHI_FREE_SPS_FIELDS = (
    ("sps_id", "ScheduledProcedureStepID"),
    ("station_aet", "ScheduledStationAETitle"),
    ("modality", "Modality"),
    ("start_date", "ScheduledProcedureStepStartDate"),
    ("start_time", "ScheduledProcedureStepStartTime"),
)


def summarize_dataset(ds, *, phi: bool = False) -> dict:
    """One worklist item as a flat, readable summary.

    PHI-free by default: accession, station, modality, date, UIDs — the same
    fields the query log carries. Patient name/ID need `phi=True`.
    """
    out: dict = {}
    for key, tag in PHI_FREE_FIELDS:
        value = str(ds.get(tag, "") or "")
        if value:
            out[key] = value
    sps_seq = ds.get("ScheduledProcedureStepSequence") or []
    if sps_seq:
        for key, tag in PHI_FREE_SPS_FIELDS:
            value = str(sps_seq[0].get(tag, "") or "")
            if value:
                out[key] = value
    if phi:
        out["patient_name"] = str(ds.get("PatientName", "") or "")
        out["patient_id"] = str(ds.get("PatientID", "") or "")
    return out


def show_phi() -> bool:
    """Whether the operator deliberately switched the preview to include names."""
    from . import settings_service

    return settings_service.get_bool("simulate_show_phi")


def worklist_preview(identifier: Dataset, *, phi: bool | None = None,
                     max_items: int = 50) -> dict:
    """What would a modality with this query get? Runs the real aggregation."""
    from . import aggregation

    if phi is None:
        phi = show_phi()
    result = aggregation.collect(identifier, count_metrics=False)

    # who else knew each merged case (the dedupe decisions, made visible)
    from .upstream import dedupe_key

    sources_by_key: dict[tuple, list[str]] = {}
    for src, answers in result.collected:
        for ds in answers:
            sources_by_key.setdefault(dedupe_key(ds), []).append(src.name)

    items = []
    for ds, src in result.merged[:max_items]:
        entry = summarize_dataset(ds, phi=phi)
        entry["source"] = src.name
        entry["also_in"] = [n for n in sources_by_key.get(dedupe_key(ds), []) if n != src.name]
        items.append(entry)

    return {
        "station": result.station,
        "rule": result.rule_name,
        "status": result.status,
        "duration_ms": result.duration_ms,
        "answers": len(result.merged),
        "hidden": result.hidden,
        "phi": bool(phi),
        "served_stale": result.served_stale,
        "sources": [
            {
                "name": o.name,
                "source_id": o.source_id,
                "answers": o.answers,
                "stale": o.stale,
                "breaker_state": o.breaker_state,
            }
            for o in result.outcomes
        ],
        "items": items,
        "field_changes": result.field_changes,
        "truncated": len(result.merged) > max_items,
    }


def source_query_test(source_id: int, identifier: Dataset, *, phi: bool | None = None,
                      max_items: int = 20) -> dict:
    """Ask one source directly: does it deliver worklists, and what does it say?"""
    from . import aggregation

    if phi is None:
        phi = show_phi()
    src = aggregation.source_config(source_id)
    if src is None:
        return {"ok": False, "error": "not found", "answers": 0, "items": []}

    answers, duration_ms, error = aggregation.query_one(src, identifier)
    return {
        "source_id": src.id,
        "name": src.name,
        "ok": not error,
        "error": error,
        "answers": len(answers),
        "duration_ms": duration_ms,
        "phi": bool(phi),
        "items": [
            {**summarize_dataset(ds, phi=phi), "source": src.name, "also_in": []}
            for ds in answers[:max_items]
        ],
        "truncated": len(answers) > max_items,
    }
