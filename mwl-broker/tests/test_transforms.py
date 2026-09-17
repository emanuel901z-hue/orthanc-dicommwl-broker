"""Unit tests for DICOM transform rules — validation and application.

No network: pure dataset manipulation + the operations validator.
"""
from pydicom.dataset import Dataset
from sqlalchemy import select

from mwl_broker.db import session_factory
from mwl_broker.models import MwlSource, PacsTarget, TransformRule
from mwl_broker.transforms import (
    TransformCfg,
    applicable,
    apply_transforms,
    validate_operations,
)


def _cfg(name="r", ops=(), priority=100, source_id=None, target_id=None) -> TransformCfg:
    return TransformCfg(id=1, name=name, priority=priority,
                        source_id=source_id, target_id=target_id, operations=list(ops))


def _ds(**attrs) -> Dataset:
    ds = Dataset()
    for k, v in attrs.items():
        setattr(ds, k, v)
    return ds


# ── validation ─────────────────────────────────────────────────────────


def test_validate_accepts_real_keywords():
    assert validate_operations([
        {"op": "set", "tag": "InstitutionName", "value": "Klinikum"},
        {"op": "prefix", "tag": "PatientID", "value": "KH_"},
        {"op": "suffix", "tag": "StudyDescription", "value": " (KH)"},
        {"op": "replace", "tag": "AccessionNumber", "pattern": "^ALT", "value": "KH"},
        {"op": "copy", "tag": "StudyDescription", "from_tag": "RequestedProcedureDescription"},
        {"op": "remove", "tag": "PatientAddress"},
    ]) == []


def test_validate_rejects_unknown_keyword():
    errors = validate_operations([{"op": "set", "tag": "NotATag", "value": "x"}])
    assert errors and "unknown DICOM keyword" in errors[0]


def test_validate_rejects_protected_uids():
    errors = validate_operations([{"op": "set", "tag": "StudyInstanceUID", "value": "1.2.3"}])
    assert errors and "must not be modified" in errors[0]


def test_validate_rejects_unknown_op():
    errors = validate_operations([{"op": "explode", "tag": "PatientID", "value": "x"}])
    assert errors and "unknown op" in errors[0]


def test_validate_requires_value():
    errors = validate_operations([{"op": "prefix", "tag": "PatientID"}])
    assert errors and "'value' is required" in errors[0]


def test_validate_rejects_bad_regex():
    errors = validate_operations([
        {"op": "replace", "tag": "AccessionNumber", "pattern": "([", "value": "x"},
    ])
    assert errors and "invalid regex" in errors[0]


def test_validate_copy_requires_valid_source_keyword():
    errors = validate_operations([
        {"op": "copy", "tag": "PatientID", "from_tag": "Nope"},
    ])
    assert errors and "unknown source keyword" in errors[0]


def test_validate_rejects_empty_operations():
    assert validate_operations([]) == ["operations must be a non-empty list"]


# ── application ────────────────────────────────────────────────────────


def test_apply_set_prefix_suffix_replace_remove():
    ds = _ds(PatientID="P1", StudyDescription="CT Abdomen",
             AccessionNumber="ALT-42", PatientAddress="Street 1")
    applied, errors = apply_transforms(ds, [_cfg(ops=[
        {"op": "set", "tag": "InstitutionName", "value": "Klinikum"},
        {"op": "prefix", "tag": "PatientID", "value": "KH_"},
        {"op": "suffix", "tag": "StudyDescription", "value": " (KH)"},
        {"op": "replace", "tag": "AccessionNumber", "pattern": "^ALT", "value": "KH"},
        {"op": "remove", "tag": "PatientAddress"},
    ])])
    assert errors == []
    assert applied == ["r"]
    assert ds.InstitutionName == "Klinikum"
    assert ds.PatientID == "KH_P1"
    assert ds.StudyDescription == "CT Abdomen (KH)"
    assert ds.AccessionNumber == "KH-42"
    assert not hasattr(ds, "PatientAddress")


def test_apply_copy_takes_source_value():
    ds = _ds(RequestedProcedureDescription="MR Schädel")
    apply_transforms(ds, [_cfg(ops=[
        {"op": "copy", "tag": "StudyDescription", "from_tag": "RequestedProcedureDescription"},
    ])])
    assert ds.StudyDescription == "MR Schädel"


def test_failing_op_is_reported_and_skipped():
    ds = _ds(PatientID="P1")
    applied, errors = apply_transforms(ds, [_cfg(name="broken", ops=[
        {"op": "copy", "tag": "InstitutionName", "from_tag": "RequestedProcedureDescription"},
        {"op": "set", "tag": "InstitutionName", "value": "OK"},
    ])])
    assert applied == ["broken"]          # rule ran …
    assert len(errors) == 1               # … one op failed …
    assert ds.InstitutionName == "OK"     # … the rest still applied


def test_rules_apply_in_given_order():
    ds = _ds(PatientID="P1")
    apply_transforms(ds, [
        _cfg(name="a", ops=[{"op": "prefix", "tag": "PatientID", "value": "A"}]),
        _cfg(name="b", ops=[{"op": "prefix", "tag": "PatientID", "value": "B"}]),
    ])
    assert ds.PatientID == "BAP1"


# ── scope resolution ───────────────────────────────────────────────────


def _seed(source_name=None, target_name=None):
    with session_factory()() as s:
        src_id = tgt_id = None
        if source_name:
            row = MwlSource(name=source_name, aet="A", host="h", port=1, calling_aet="C")
            s.add(row)
            s.flush()
            src_id = row.id
        if target_name:
            row = PacsTarget(name=target_name, aet="A", host="h", port=1, calling_aet="C")
            s.add(row)
            s.flush()
            tgt_id = row.id
        s.commit()
        return src_id, tgt_id


def _add_rule(name, source_id, target_id, priority=100, enabled=True):
    with session_factory()() as s:
        s.add(TransformRule(name=name, operations=[{"op": "remove", "tag": "PatientAddress"}],
                            source_id=source_id, target_id=target_id,
                            priority=priority, enabled=enabled))
        s.commit()


def test_applicable_matches_scope_and_orders_by_priority():
    src_id, tgt_id = _seed("ris-a", "pacs-kh")
    _add_rule("any", None, None, priority=30)
    _add_rule("src", src_id, None, priority=10)
    _add_rule("tgt", None, tgt_id, priority=20)
    _add_rule("other-src", src_id + 99, None, priority=5)
    _add_rule("off", src_id, tgt_id, priority=1, enabled=False)

    with session_factory()() as s:
        names = [r.name for r in applicable(s, src_id, tgt_id)]
    assert names == ["src", "tgt", "any"]


def test_applicable_without_source_only_global_rules():
    src_id, tgt_id = _seed("ris-a", "pacs-kh")
    _add_rule("any", None, None)
    _add_rule("src", src_id, None)
    with session_factory()() as s:
        names = [r.name for r in applicable(s, None, tgt_id)]
    assert names == ["any"]


def test_applicable_returns_detached_configs():
    src_id, tgt_id = _seed("ris-a", "pacs-kh")
    _add_rule("r", src_id, tgt_id)
    with session_factory()() as s:
        rules = applicable(s, src_id, tgt_id)
    # usable after the session is closed
    assert rules[0].operations[0]["tag"] == "PatientAddress"
    assert isinstance(rules[0], TransformCfg)
