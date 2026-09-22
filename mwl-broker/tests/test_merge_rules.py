"""Field-level merge: which source wins for a single DICOM attribute.

Default merge = the whole item from the highest-priority source that knows the
case. A rule overrides single fields (demographics from the HIS feed while the
study description comes from the RIS).
"""
import pytest
from pydicom.dataset import Dataset

from mwl_broker import aggregation, merge_rules
from mwl_broker.db import get_engine, session_factory
from mwl_broker.models import MergeRule


def _item(accession: str, patient_name: str, station: str = "CT_01",
          description: str = "Standard") -> Dataset:
    ds = Dataset()
    ds.AccessionNumber = accession
    ds.PatientID = f"P-{accession}"
    ds.PatientName = patient_name
    ds.StudyInstanceUID = "1.2.840.113619.2.55.3.1"
    sps = Dataset()
    sps.ScheduledProcedureStepID = "1"
    sps.Modality = "CT"
    sps.ScheduledStationAETitle = station
    sps.ScheduledProcedureStepDescription = description
    ds.ScheduledProcedureStepSequence = [sps]
    return ds


@pytest.fixture()
def seeded(client):
    a = client.post("/api/v1/sources", json={
        "name": "his-feed", "aet": "HIS", "host": "127.0.0.1", "port": 1,
        "calling_aet": "MWLBROKER", "charset": "ISO_IR 100",
        "enabled": True, "timeout_s": 1, "priority": 10}).json()
    b = client.post("/api/v1/sources", json={
        "name": "ris-a", "aet": "RIS_A", "host": "127.0.0.1", "port": 1,
        "calling_aet": "MWLBROKER", "charset": "ISO_IR 100",
        "enabled": True, "timeout_s": 1, "priority": 20}).json()
    return a, b


def test_without_a_rule_the_whole_item_comes_from_one_source(client, seeded, monkeypatch):
    """The default must not change — a rule is opt-in."""
    monkeypatch.setattr(aggregation, "query_source", lambda cfg, identifier: (
        [_item("ACC-1", "His^Hanna")] if cfg.name == "his-feed"
        else [_item("ACC-1", "Ris^Rita")]
    ))

    result = aggregation.collect(Dataset())

    assert result.merged[0][1].name == "his-feed"      # higher priority wins
    assert str(result.merged[0][0].PatientName) == "His^Hanna"
    assert result.field_changes == []


def test_a_rule_takes_one_field_from_another_source(client, seeded, monkeypatch):
    """Demographics from the RIS, everything else from the HIS feed."""
    client.post("/api/v1/merge-rules", json={
        "tag": "PatientName", "sources": ["ris-a"], "enabled": True})

    monkeypatch.setattr(aggregation, "query_source", lambda cfg, identifier: (
        [_item("ACC-1", "His^Hanna", description="HIS text")] if cfg.name == "his-feed"
        else [_item("ACC-1", "Ris^Rita", description="RIS text")]
    ))

    result = aggregation.collect(Dataset())
    item, winner = result.merged[0]

    # the winning item is still the HIS one …
    assert winner.name == "his-feed"
    assert str(item.ScheduledProcedureStepSequence[0].ScheduledProcedureStepDescription) == "HIS text"
    # … but the name was taken from the RIS
    assert str(item.PatientName) == "Ris^Rita"
    assert result.field_changes and result.field_changes[0]["tag"] == "PatientName"
    assert result.field_changes[0]["from"] == "ris-a"
    assert result.field_changes[0]["before"] == "His^Hanna"
    assert result.field_changes[0]["after"] == "Ris^Rita"


def test_the_rule_order_decides(client, seeded, monkeypatch):
    """First source in the rule that has a value wins."""
    client.post("/api/v1/merge-rules", json={
        "tag": "PatientName", "sources": ["ris-a", "his-feed"], "enabled": True})
    monkeypatch.setattr(aggregation, "query_source", lambda cfg, identifier: (
        [_item("ACC-1", "His^Hanna")] if cfg.name == "his-feed"
        else [_item("ACC-1", "Ris^Rita")]
    ))

    result = aggregation.collect(Dataset())
    # ris-a is asked first in the rule, so its value is used
    assert str(result.merged[0][0].PatientName) == "Ris^Rita"


def test_a_disabled_rule_is_ignored(client, seeded, monkeypatch):
    client.post("/api/v1/merge-rules", json={
        "tag": "PatientName", "sources": ["ris-a"], "enabled": False})
    monkeypatch.setattr(aggregation, "query_source", lambda cfg, identifier: (
        [_item("ACC-1", "His^Hanna")] if cfg.name == "his-feed"
        else [_item("ACC-1", "Ris^Rita")]
    ))

    result = aggregation.collect(Dataset())
    assert str(result.merged[0][0].PatientName) == "His^Hanna"


def test_rules_can_reach_into_the_sps_sequence(client, seeded, monkeypatch):
    """Scheduled fields live inside the sequence — the rule must find them."""
    client.post("/api/v1/merge-rules", json={
        "tag": "ScheduledProcedureStepDescription", "sources": ["ris-a"], "enabled": True})
    monkeypatch.setattr(aggregation, "query_source", lambda cfg, identifier: (
        [_item("ACC-1", "His^Hanna", description="HIS text")] if cfg.name == "his-feed"
        else [_item("ACC-1", "Ris^Rita", description="RIS text")]
    ))

    result = aggregation.collect(Dataset())
    sps = result.merged[0][0].ScheduledProcedureStepSequence[0]
    assert str(sps.ScheduledProcedureStepDescription) == "RIS text"


def test_merge_rule_endpoints(client, seeded):
    created = client.post("/api/v1/merge-rules", json={
        "tag": "PatientName", "sources": ["ris-a"], "enabled": True})
    assert created.status_code == 201, created.text
    rule_id = created.json()["id"]

    listed = client.get("/api/v1/merge-rules").json()
    assert any(r["tag"] == "PatientName" for r in listed)

    # posting the same tag replaces the order instead of adding a second rule
    again = client.post("/api/v1/merge-rules", json={
        "tag": "PatientName", "sources": ["his-feed"], "enabled": True})
    assert again.status_code == 201
    assert again.json()["sources"] == ["his-feed"]
    assert len([r for r in client.get("/api/v1/merge-rules").json()
                if r["tag"] == "PatientName"]) == 1

    # nonsense is refused with a clear message
    bad_tag = client.post("/api/v1/merge-rules", json={
        "tag": "NotATag", "sources": ["ris-a"]})
    assert bad_tag.status_code == 422
    assert "not a DICOM attribute" in bad_tag.json()["detail"][0]

    bad_source = client.post("/api/v1/merge-rules", json={
        "tag": "PatientName", "sources": ["does-not-exist"]})
    assert bad_source.status_code == 422
    assert "unknown source" in bad_source.json()["detail"][0]

    empty = client.post("/api/v1/merge-rules", json={"tag": "PatientName", "sources": []})
    assert empty.status_code == 422

    assert client.delete(f"/api/v1/merge-rules/{rule_id}").status_code == 204
    assert client.delete("/api/v1/merge-rules/999").status_code == 404


def test_preview_shows_what_the_rule_changed(client, seeded, monkeypatch):
    """The dry run must name the change, otherwise a rule cannot be verified."""
    client.post("/api/v1/merge-rules", json={
        "tag": "PatientName", "sources": ["ris-a"], "enabled": True})
    monkeypatch.setattr(aggregation, "query_source", lambda cfg, identifier: (
        [_item("ACC-1", "His^Hanna")] if cfg.name == "his-feed"
        else [_item("ACC-1", "Ris^Rita")]
    ))

    body = client.post("/api/v1/simulate/worklist", json={}).json()

    assert body["field_changes"], body
    change = body["field_changes"][0]
    assert change["tag"] == "PatientName"
    assert change["from"] == "ris-a"
    assert change["after"] == "Ris^Rita"


def test_rules_are_stored_and_listed(client, seeded):
    merge_rules.upsert_rule("PatientName", ["ris-a", "his-feed"])
    merge_rules.upsert_rule("ScheduledStationAETitle", ["ris-a"])

    with session_factory()() as s:
        rows = s.query(MergeRule).all()
    assert len(rows) == 2
    assert [r["tag"] for r in merge_rules.list_rules()] == [
        "PatientName", "ScheduledStationAETitle"]
