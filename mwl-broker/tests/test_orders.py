"""Order context (`GET /orders/context`) — the accession ↔ study correlation.

The endpoint exists so a manifest creator (IHE MADO) or the operator can answer
"which order does this study belong to?" without guessing. These tests pin the
things that make the answer trustworthy: the facts are merged from all four
places the broker learns them, the provenance is visible, and the patient name
never shows up.
"""
from datetime import datetime, timezone

from mwl_broker.db import session_factory
from mwl_broker.models import LocalWorklistItem, MppsStep, MwlSource, SeenItem, StoreLog

STUDY = "1.2.826.0.1.3680043.8.498.1"
ACC = "ACC-ORD-1"

SOURCE = {"name": "ris-a", "aet": "RIS_A", "host": "127.0.0.1", "port": 11112,
          "calling_aet": "MWLBROKER", "charset": "ISO_IR 100", "timeout_s": 1}


def _source() -> int:
    with session_factory()() as s:
        row = MwlSource(name=SOURCE["name"], aet=SOURCE["aet"], host=SOURCE["host"],
                        port=SOURCE["port"], calling_aet=SOURCE["calling_aet"],
                        charset=SOURCE["charset"], enabled=True, timeout_s=1, priority=10)
        s.add(row)
        s.commit()
        s.refresh(row)
        return row.id


def _local_item(accession: str = ACC, sps_id: str = "1", study_uid: str = STUDY,
                name: str = "Doe^John") -> None:
    with session_factory()() as s:
        s.add(LocalWorklistItem(
            accession=accession, sps_id=sps_id, study_uid=study_uid,
            patient_id="PAT-1", patient_name=name, modality="CT",
            station_aet="CT_01", procedure_description="CT Thorax",
            scheduled_date="2026-09-22", scheduled_time="08:30",
            sps_status="SCHEDULED", origin="manual",
        ))
        s.commit()


def _mpps_step(accession: str = ACC, sps_id: str = "1", study_uid: str = STUDY,
               status: str = "COMPLETED") -> None:
    with session_factory()() as s:
        s.add(MppsStep(
            sop_instance_uid=f"1.2.3.4.{status}", status=status, accession=accession,
            patient_id="PAT-1", sps_id=sps_id, station_aet="CT_01", modality="CT",
            study_uid=study_uid,
            started_at=datetime(2026, 9, 22, 8, 31, tzinfo=timezone.utc),
            ended_at=datetime(2026, 9, 22, 8, 45, tzinfo=timezone.utc),
        ))
        s.commit()


def _seen_item(accession: str = ACC, sps_id: str = "1", study_uid: str = STUDY) -> None:
    source_id = _source()
    with session_factory()() as s:
        s.add(SeenItem(accession=accession, sps_id=sps_id, study_uid=study_uid,
                       patient_id="PAT-1", source_id=source_id))
        s.commit()


def _store_log(accession: str = ACC, study_uid: str = STUDY) -> None:
    with session_factory()() as s:
        s.add(StoreLog(calling_aet="CT_01", sop_instance_uid="1.2.3.4.5",
                       study_uid=study_uid, accession=accession, status="success"))
        s.commit()


# ── der Kern: eine Frage, eine Antwort ────────────────────────────────────


def test_study_uid_finds_the_order(client):
    """The manifest creator knows the study UID — that must be enough."""
    _local_item()
    _seen_item()
    _mpps_step()

    body = client.get("/api/v1/orders/context", params={"study_uid": STUDY}).json()

    assert len(body) == 1
    order = body[0]
    assert order["accession"] == ACC
    assert order["sps_id"] == "1"
    assert order["study_uid"] == STUDY
    assert order["modality"] == "CT"
    assert order["station_aet"] == "CT_01"
    assert order["procedure_description"] == "CT Thorax"
    assert order["scheduled_date"] == "2026-09-22"
    assert order["scheduled_time"] == "08:30"
    assert order["sps_status"] == "SCHEDULED"


def test_accession_number_works_the_same_way(client):
    """IHE IID/MADO clients often only carry the accession number."""
    _local_item()
    body = client.get("/api/v1/orders/context", params={"accession": ACC}).json()
    assert [o["study_uid"] for o in body] == [STUDY]


def test_the_answer_says_where_the_facts_came_from(client):
    """'Which RIS knows this case, and did the examination run?' is the point."""
    _local_item()
    _seen_item()
    _mpps_step()
    _store_log()

    order = client.get("/api/v1/orders/context", params={"study_uid": STUDY}).json()[0]

    assert order["sources"] == ["ris-a"]
    assert order["origins"] == ["local", "mpps", "worklist", "store"]
    assert order["mpps_status"] == "COMPLETED"
    assert order["mpps_started_at"].startswith("2026-09-22T08:31")
    assert order["mpps_ended_at"].startswith("2026-09-22T08:45")
    assert order["forwarded_instances"] == 1


def test_images_without_a_worklist_entry_are_still_reported(client):
    """'Images arrived, order unknown' is exactly what an operator has to chase."""
    _store_log(accession="ACC-ONLY-IMAGES", study_uid="9.9.9")

    body = client.get("/api/v1/orders/context", params={"accession": "ACC-ONLY-IMAGES"}).json()

    assert len(body) == 1
    assert body[0]["sps_id"] == ""
    assert body[0]["origins"] == ["store"]
    assert body[0]["forwarded_instances"] == 1
    assert body[0]["sources"] == []


def test_one_accession_can_carry_several_scheduled_steps(client):
    """Two steps on one order are two entries — merging them would lose a step."""
    _local_item(sps_id="1")
    _local_item(sps_id="2")

    body = client.get("/api/v1/orders/context", params={"accession": ACC}).json()

    assert [o["sps_id"] for o in body] == ["1", "2"]


def test_both_keys_together_narrow_the_answer(client):
    """Whoever gives both knows both — matching either one would be wrong."""
    _local_item(accession="ACC-A", study_uid="1.1.1")
    _local_item(accession="ACC-B", study_uid="2.2.2")

    body = client.get("/api/v1/orders/context",
                      params={"study_uid": "1.1.1", "accession": "ACC-B"}).json()

    assert body == []


def test_unknown_study_is_an_empty_answer_not_an_error(client):
    """The caller may be ahead of the broker — an empty list is the honest answer."""
    r = client.get("/api/v1/orders/context", params={"study_uid": "does.not.exist"})
    assert r.status_code == 200
    assert r.json() == []


# ── Grenzen ───────────────────────────────────────────────────────────────


def test_a_question_without_a_key_is_rejected(client):
    """No key at all would return the whole database — refuse it plainly."""
    r = client.get("/api/v1/orders/context")
    assert r.status_code == 422
    assert "study_uid" in r.json()["detail"] and "accession" in r.json()["detail"]


def test_limit_is_bounded(client):
    assert client.get("/api/v1/orders/context",
                      params={"accession": ACC, "limit": 0}).status_code == 422
    assert client.get("/api/v1/orders/context",
                      params={"accession": ACC, "limit": 501}).status_code == 422
    assert client.get("/api/v1/orders/context",
                      params={"accession": ACC, "limit": 500}).status_code == 200


def test_the_patient_name_never_leaves_the_broker(client):
    """PHI rule: the name stays in the table that needs it, not in the answer."""
    _local_item(name="Musterfrau^Erika")

    r = client.get("/api/v1/orders/context", params={"study_uid": STUDY})

    assert "Musterfrau" not in r.text
    assert "patient_name" not in r.text
    assert r.json()[0]["patient_id"] == "PAT-1"
