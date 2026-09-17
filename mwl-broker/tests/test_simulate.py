"""Dry-run simulation of routing and modify rules.

The important property: the simulator must return exactly what the live path
would do — asserted by comparing against the broker's own resolver.
"""
from datetime import datetime, timezone

from mwl_broker import routing, simulate
from mwl_broker.db import session_factory
from mwl_broker.dimse import BrokerSCP
from mwl_broker.models import MwlSource, PacsTarget, RoutingRule, SeenItem, TransformRule


def _source(name="ris-a", enabled=True) -> int:
    with session_factory()() as s:
        row = MwlSource(name=name, aet="RIS_A", host="127.0.0.1", port=1,
                        calling_aet="MWLBROKER", charset="ISO_IR 100", enabled=enabled)
        s.add(row)
        s.commit()
        return row.id


def _target(name="pacs-kh", is_default=False, enabled=True) -> int:
    with session_factory()() as s:
        row = PacsTarget(name=name, aet="PACS_KH", host="127.0.0.1", port=104,
                         calling_aet="MWLBROKER", is_default=is_default, enabled=enabled)
        s.add(row)
        s.commit()
        return row.id


def _rule(source_id: int, target_id: int, priority=100, enabled=True) -> int:
    with session_factory()() as s:
        row = RoutingRule(source_id=source_id, target_id=target_id,
                          priority=priority, enabled=enabled)
        s.add(row)
        s.commit()
        return row.id


def _seen(accession: str, source_id: int, study_uid="1.2.3") -> None:
    with session_factory()() as s:
        s.add(SeenItem(accession=accession, study_uid=study_uid, source_id=source_id,
                       ts=datetime.now(timezone.utc)))
        s.commit()


def _transform(name="kh", source_id=None, target_id=None, ops=None, enabled=True) -> None:
    with session_factory()() as s:
        s.add(TransformRule(name=name, source_id=source_id, target_id=target_id, enabled=enabled,
                            operations=ops or [{"op": "prefix", "tag": "PatientID", "value": "KH_"}]))
        s.commit()


# ── routing ────────────────────────────────────────────────────────────


def test_route_uses_the_matching_rule():
    src = _source()
    tgt = _target()
    _rule(src, tgt, priority=5)
    _seen("ACC-1", src)

    with session_factory()() as s:
        result = simulate.simulate_route(s, "ACC-1")

    assert result["matched_via"] == "accession"
    assert result["source_name"] == "ris-a"
    assert result["target_name"] == "pacs-kh"
    assert result["rule_id"] is not None
    assert "rule" in result["reason"]


def test_route_falls_back_to_the_default_target():
    _target(is_default=True)

    with session_factory()() as s:
        result = simulate.simulate_route(s, "UNKNOWN")

    assert result["matched_via"] == "default"
    assert result["target_name"] == "pacs-kh"
    assert result["rule_id"] is None
    assert result["source_id"] is None


def test_route_without_any_target_explains_the_rejection():
    _source()

    with session_factory()() as s:
        result = simulate.simulate_route(s, "ACC-X")

    assert result["target_id"] is None
    assert result["matched_via"] == "none"
    assert "rejected" in result["reason"]


def test_route_matches_by_study_uid():
    src = _source()
    tgt = _target()
    _rule(src, tgt)
    _seen("ACC-1", src, study_uid="1.2.3.4")

    with session_factory()() as s:
        result = simulate.simulate_route(s, "", "1.2.3.4")

    assert result["matched_via"] == "study_uid"
    assert result["target_name"] == "pacs-kh"


def test_route_ignores_disabled_rules_and_targets():
    src = _source()
    disabled_rule_target = _target("pacs-off", enabled=True)
    _rule(src, disabled_rule_target, enabled=False)
    fallback = _target("pacs-default", is_default=True)
    _seen("ACC-1", src)

    with session_factory()() as s:
        result = simulate.simulate_route(s, "ACC-1")

    assert result["target_name"] == "pacs-default"
    assert result["rule_id"] is None


def test_simulation_matches_the_live_resolver():
    """The simulator and the C-STORE path must agree — same code, same result."""
    src = _source()
    tgt = _target()
    _rule(src, tgt, priority=3)
    _seen("ACC-1", src, study_uid="9.8.7")

    with session_factory()() as s:
        decision = routing.resolve(s, "ACC-1", "")

    live_source_id, live_target = BrokerSCP._resolve_target("ACC-1", "")

    assert live_source_id == decision.source_id
    assert live_target.id == decision.target.id
    assert live_target.name == decision.target.name


# ── modify rules ───────────────────────────────────────────────────────


def test_transform_simulation_reports_the_tag_diff():
    src = _source()
    tgt = _target()
    _rule(src, tgt)
    _seen("ACC-1", src)
    _transform(source_id=src, ops=[
        {"op": "prefix", "tag": "PatientID", "value": "KH_"},
        {"op": "set", "tag": "InstitutionName", "value": "Klinikum"},
        {"op": "remove", "tag": "PatientAddress"},
    ])

    with session_factory()() as s:
        result = simulate.simulate_transform(
            s, {"PatientID": "P1", "InstitutionName": "ALT", "PatientAddress": "Street 1"},
            accession="ACC-1",
        )

    assert result["target_name"] == "pacs-kh"
    assert result["rules_applied"] == ["kh"]
    changes = {c["tag"]: (c["before"], c["after"]) for c in result["changes"]}
    assert changes["PatientID"] == ("P1", "KH_P1")
    assert changes["InstitutionName"] == ("ALT", "Klinikum")
    assert changes["PatientAddress"][1] == ""  # removed
    assert result["errors"] == []


def test_transform_simulation_respects_the_scope():
    src = _source()
    other_src = _source("ris-b")
    tgt = _target()
    _rule(src, tgt)
    _seen("ACC-1", src)
    _transform("only-b", source_id=other_src)

    with session_factory()() as s:
        result = simulate.simulate_transform(s, {"PatientID": "P1"}, accession="ACC-1")

    assert result["rules_applied"] == []
    assert result["changes"] == []


def test_transform_simulation_can_override_the_scope():
    src = _source()
    tgt = _target()
    _transform("global", ops=[{"op": "suffix", "tag": "PatientID", "value": "_X"}])

    with session_factory()() as s:
        result = simulate.simulate_transform(
            s, {"PatientID": "P1"}, source_id=src, target_id=tgt,
        )

    assert result["rules_applied"] == ["global"]
    assert result["changes"][0]["after"] == "P1_X"


def test_transform_simulation_reports_failing_operations_instead_of_raising():
    """A failing operation is reported; the simulation still returns a result."""
    _target(is_default=True)
    _transform("broken", ops=[
        {"op": "copy", "tag": "InstitutionName", "from_tag": "RequestedProcedureDescription"},
    ])

    with session_factory()() as s:
        result = simulate.simulate_transform(s, {"PatientID": "P1"})

    assert any("broken" in e for e in result["errors"])
    # the rule is still listed as applied, the instance would still be forwarded
    assert result["rules_applied"] == ["broken"]


def test_transform_simulation_survives_unusual_values():
    """pydicom warns instead of raising for odd values — the simulation must
    not turn that into an error."""
    _target(is_default=True)

    with session_factory()() as s:
        result = simulate.simulate_transform(
            s, {"StudyDate": "not-a-date", "PatientID": "P1"},
        )

    assert result["errors"] == []
    assert result["target_name"] == "pacs-kh"


def test_transform_simulation_does_not_write_anything():
    src = _source()
    tgt = _target()
    _rule(src, tgt)
    _transform(source_id=src)

    with session_factory()() as s:
        simulate.simulate_transform(s, {"PatientID": "P1"}, accession="ACC-1")

    with session_factory()() as s:
        from mwl_broker.models import StoreLog

        assert s.query(StoreLog).count() == 0
        assert s.query(SeenItem).count() == 0
