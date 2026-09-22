"""F1: Patient identifier reconciliation (IHE PIR).

A merge must change what the modality sees *and* where images are routed — a
half-applied merge is worse than none.
"""
import pytest
from pydicom.dataset import Dataset

from mwl_broker import merges, settings_service
from mwl_broker.db import session_factory
from mwl_broker.models import LocalWorklistItem, SeenItem

ADT_A40 = (
    "MSH|^~\\&|RIS|KH|MWLBROKER|KH|20260922120000||ADT^A40|MSG-ADT-1|P|2.4\r"
    "PID|1||12345^^^KH^MR||Muster^Max||19800101|M\r"
    "MRG|ALT-4711^^^KH^MR\r"
)


def _local_item(patient_id: str, accession: str = "ACC-PIR-1") -> None:
    with session_factory()() as s:
        s.add(LocalWorklistItem(accession=accession, sps_id="1", patient_id=patient_id,
                                patient_name="Muster^Max", modality="CT",
                                station_aet="CT_01", enabled=True))
        s.commit()


def _source() -> int:
    from mwl_broker.models import MwlSource

    with session_factory()() as s:
        row = s.query(MwlSource).first()
        if row is None:
            row = MwlSource(name="ris-a", aet="RIS_A", host="127.0.0.1", port=11112,
                            calling_aet="MWLBROKER", charset="ISO_IR 100",
                            enabled=True, timeout_s=1, priority=10)
            s.add(row)
            s.commit()
            s.refresh(row)
        return row.id


def _seen_item(patient_id: str, accession: str = "ACC-PIR-1") -> None:
    source_id = _source()
    with session_factory()() as s:
        s.add(SeenItem(accession=accession, sps_id="1", study_uid="1.2.3",
                       patient_id=patient_id, source_id=source_id))
        s.commit()


# ── Kern ──────────────────────────────────────────────────────────────────

def test_merge_resolves_the_identifier(client):
    merges.merge("ALT-1", "NEU-1", reason="ADT A40", actor="tester")

    assert merges.resolve("ALT-1") == "NEU-1"
    assert merges.resolve("NEU-1") == "NEU-1"        # unchanged
    assert merges.resolve("UNBEKANNT") == "UNBEKANNT"


def test_a_chain_is_followed(client):
    merges.merge("A", "B", actor="tester")
    merges.merge("B", "C", actor="tester")

    assert merges.resolve("A") == "C"
    assert merges.resolve_many(["A", "B", "C"]) == {"A": "C", "B": "C", "C": "C"}


def test_a_cycle_does_not_hang(client):
    """Data problems must not become a hang — the chain stops."""
    merges.merge("X", "Y", actor="tester")
    merges.merge("Y", "Z", actor="tester")
    # build a cycle behind the module's back (a real ADT could do this)
    from mwl_broker.models import PatientMerge

    with session_factory()() as s:
        s.add(PatientMerge(old_patient_id="Z", new_patient_id="X", actor="tester"))
        s.commit()

    assert merges.resolve("X") in {"X", "Y", "Z"}     # returns, does not loop


def test_the_other_direction_is_refused(client):
    merges.merge("A", "B", actor="tester")

    with pytest.raises(ValueError) as exc:
        merges.merge("B", "A", actor="tester")
    assert "ambiguous" in str(exc.value)


def test_identical_ids_and_empty_input_are_refused(client):
    with pytest.raises(ValueError):
        merges.merge("A", "A")
    with pytest.raises(ValueError):
        merges.merge("", "B")


def test_merging_twice_is_idempotent(client):
    first = merges.merge("ALT-2", "NEU-2", actor="tester")
    again = merges.merge("ALT-2", "NEU-2", actor="tester")

    assert first["id"] == again["id"]
    assert len(merges.list_merges()) == 1


def test_unmerge_takes_it_out_of_effect_but_keeps_the_trail(client):
    row = merges.merge("ALT-3", "NEU-3", actor="tester")

    assert merges.unmerge(row["id"]) is True
    assert merges.resolve("ALT-3") == "ALT-3"
    assert merges.list_merges() == []
    assert len(merges.list_merges(active_only=False)) == 1


# ── Wirkung auf die Daten ─────────────────────────────────────────────────

def test_a_merge_updates_local_entries_and_routing_provenance(client):
    _local_item("ALT-4")
    _seen_item("ALT-4")

    merges.merge("ALT-4", "NEU-4", actor="tester")

    with session_factory()() as s:
        item = s.query(LocalWorklistItem).filter_by(accession="ACC-PIR-1").one()
        seen = s.query(SeenItem).filter_by(accession="ACC-PIR-1").one()
    assert item.patient_id == "NEU-4"
    assert seen.patient_id == "NEU-4", "routing provenance must follow the merge"


def test_the_worklist_answer_carries_the_current_id(client):
    """An image acquired under the old ID is routed by its (merged) worklist entry."""
    from mwl_broker import aggregation

    ds = Dataset()
    ds.PatientID = "ALT-5"
    ds.AccessionNumber = "ACC-PIR-2"
    ds.StudyInstanceUID = "1.2.3.4"
    merges.merge("ALT-5", "NEU-5", actor="tester")

    changed = merges.rewrite_datasets([ds], merges.resolve_many(["ALT-5"]))

    assert changed == 1
    assert ds.PatientID == "NEU-5"


def test_aggregation_applies_the_merge(client, monkeypatch):
    """The DIMSE path and the preview share the code — both must merge."""
    from mwl_broker import aggregation
    from mwl_broker.models import MwlSource

    with session_factory()() as s:
        s.add(MwlSource(name="ris-a", aet="RIS_A", host="127.0.0.1", port=11112,
                        calling_aet="MWLBROKER", charset="ISO_IR 100",
                        enabled=True, timeout_s=1, priority=10))
        s.commit()

    answer = Dataset()
    answer.PatientID = "ALT-6"
    answer.AccessionNumber = "ACC-PIR-3"
    answer.StudyInstanceUID = "1.2.3.5"
    answer.ScheduledStationAETitle = "CT_01"
    answer.Modality = "CT"
    sps = Dataset()
    sps.ScheduledProcedureStepID = "SPS-1"
    sps.ScheduledStationAETitle = "CT_01"
    sps.ScheduledProcedureStepStartDate = "20260922"
    answer.ScheduledProcedureStepSequence = [sps]

    monkeypatch.setattr(aggregation, "query_source", lambda src, ident: [answer])
    settings_service.set_value("cache_enabled", "false")
    merges.merge("ALT-6", "NEU-6", actor="tester")

    result = aggregation.collect(Dataset())

    served = [ds for ds, _src in result.merged]
    assert served, "the merged source answer is missing"
    assert served[0].PatientID == "NEU-6"


# ── API ───────────────────────────────────────────────────────────────────

def test_merge_api_records_an_audit_entry(client):
    created = client.post("/api/v1/merges", json={
        "old_patient_id": "ALT-7", "new_patient_id": "NEU-7", "reason": "Notfall"})
    assert created.status_code == 201
    row = created.json()
    assert row["origin"] == "manual" and row["active"] is True

    listed = client.get("/api/v1/merges").json()
    assert [m["old_patient_id"] for m in listed] == ["ALT-7"]

    resolved = client.get("/api/v1/merges/resolve/ALT-7").json()
    assert resolved == {"patient_id": "ALT-7", "resolved": "NEU-7", "merged": True}

    audit_rows = client.get("/api/v1/audit/config").json()
    rows = audit_rows["items"] if isinstance(audit_rows, dict) else audit_rows
    actions = [row["action"] for row in rows if isinstance(row, dict)]
    assert "patient.merge" in actions, actions

    assert client.delete(f"/api/v1/merges/{row['id']}").status_code == 204
    assert client.get("/api/v1/merges").json() == []
    assert client.delete(f"/api/v1/merges/{row['id']}").status_code == 404


def test_adt_a40_dry_run_reports_without_writing(client):
    result = client.post("/api/v1/hl7/adt?dry_run=true", content=ADT_A40,
                         headers={"Content-Type": "text/plain"}).json()

    assert result["event"] == "A40"
    assert result["old_patient_id"] == "ALT-4711"
    assert result["new_patient_id"] == "12345"
    assert result["action"] == "merged" and result["dry_run"] is True
    assert client.get("/api/v1/merges").json() == []


def test_adt_a40_applies_the_merge(client):
    _local_item("ALT-4711", accession="ACC-PIR-9")

    result = client.post("/api/v1/hl7/adt?dry_run=false", content=ADT_A40,
                         headers={"Content-Type": "text/plain"}).json()

    assert result["record_id"]
    assert merges.resolve("ALT-4711") == "12345"
    with session_factory()() as s:
        item = s.query(LocalWorklistItem).filter_by(accession="ACC-PIR-9").one()
    assert item.patient_id == "12345"


def test_adt_with_a_missing_mrg_is_refused_with_plain_words(client):
    broken = ("MSH|^~\\&|RIS|KH|MWLBROKER|KH|20260922120000||ADT^A40|MSG-2|P|2.4\r"
              "PID|1||12345^^^KH^MR||Muster^Max\r")

    response = client.post("/api/v1/hl7/adt?dry_run=false", content=broken,
                           headers={"Content-Type": "text/plain"})

    assert response.status_code == 422
    assert "MRG-1" in response.text


def test_an_unhandled_adt_event_is_reported_but_not_applied(client):
    """A03 (visit notification) is none of the broker's business."""
    other = ("MSH|^~\\&|RIS|KH|MWLBROKER|KH|20260922120000||ADT^A03|MSG-3|P|2.4\r"
             "PID|1||99999^^^KH^MR||Muster^Max\r")

    result = client.post("/api/v1/hl7/adt?dry_run=false", content=other,
                         headers={"Content-Type": "text/plain"}).json()

    assert result["action"] == "not-applicable"
    assert any("A03" in w for w in result["warnings"])
    assert client.get("/api/v1/merges").json() == []


def test_merge_api_refuses_nonsense_with_plain_words(client):
    same = client.post("/api/v1/merges", json={"old_patient_id": "A", "new_patient_id": "A"})
    assert same.status_code == 422
    assert "identical" in same.json()["detail"]

    reverse = client.post("/api/v1/merges", json={"old_patient_id": "A", "new_patient_id": "B"})
    assert reverse.status_code == 201
    back = client.post("/api/v1/merges", json={"old_patient_id": "B", "new_patient_id": "A"})
    assert back.status_code == 422
    assert "ambiguous" in back.json()["detail"]


def test_migrations_cover_the_merge_table(client):
    """The PIR table must exist after the migrations, not only via create_all."""
    from sqlalchemy import inspect

    from mwl_broker.db import get_engine

    assert "patient_merge" in inspect(get_engine()).get_table_names()
