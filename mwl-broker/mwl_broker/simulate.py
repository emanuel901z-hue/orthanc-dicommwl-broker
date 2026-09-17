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
