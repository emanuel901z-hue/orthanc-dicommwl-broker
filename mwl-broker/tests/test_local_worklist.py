"""Local worklist items: DICOM view, matching, HL7 upsert, expiry."""
from datetime import datetime, timedelta, timezone

from pydicom.dataset import Dataset

from mwl_broker import local_worklist, settings_service
from mwl_broker.db import session_factory
from mwl_broker.models import LocalWorklistItem, MwlSource


def _item(accession="EMERG-1", sps_id="1", **kwargs) -> LocalWorklistItem:
    values = {
        "accession": accession, "sps_id": sps_id, "patient_id": "P1",
        "patient_name": "Mueller^Hans", "modality": "CT", "station_aet": "CT_01",
        "procedure_description": "CT Schädel", "scheduled_date": "2026-09-17",
        "scheduled_time": "12:00", "study_uid": "1.2.3", "sps_status": "SCHEDULED",
        "origin": "manual", "enabled": True,
    }
    values.update(kwargs)
    with session_factory()() as s:
        row = LocalWorklistItem(**values)
        s.add(row)
        s.commit()
        s.refresh(row)
        return row


def _query(station="", modality="", patient="", accession="", date="") -> Dataset:
    q = Dataset()
    q.PatientID = patient
    q.AccessionNumber = accession
    sps = Dataset()
    sps.ScheduledStationAETitle = station
    sps.Modality = modality
    sps.ScheduledProcedureStepStartDate = date
    q.ScheduledProcedureStepSequence = [sps]
    return q


# ── DICOM view ─────────────────────────────────────────────────────────


def test_to_dataset_builds_a_worklist_answer():
    ds = local_worklist.to_dataset(_item())

    assert ds.PatientID == "P1" and ds.PatientName == "Mueller^Hans"
    assert ds.AccessionNumber == "EMERG-1"
    assert ds.StudyInstanceUID == "1.2.3"
    sps = ds.ScheduledProcedureStepSequence[0]
    assert sps.ScheduledProcedureStepID == "1"
    assert sps.ScheduledStationAETitle == "CT_01"
    assert sps.Modality == "CT"
    assert sps.ScheduledProcedureStepStartDate == "20260917"
    assert sps.ScheduledProcedureStepStartTime == "1200"
    assert sps.ScheduledProcedureStepStatus == "SCHEDULED"
    assert ds.RequestedProcedureDescription == "CT Schädel"


def test_to_dataset_tolerates_empty_fields():
    ds = local_worklist.to_dataset(_item(modality="", station_aet="", study_uid="",
                                         scheduled_time="", procedure_description=""))
    sps = ds.ScheduledProcedureStepSequence[0]
    assert sps.Modality == "" and "StudyInstanceUID" not in ds


# ── matching ───────────────────────────────────────────────────────────


def test_active_items_honour_the_query_keys():
    _item("EMERG-1")
    _item("EMERG-2", modality="MR", station_aet="MR_01")

    assert len(local_worklist.active_items(_query())) == 2
    assert [i.accession for i in local_worklist.active_items(_query(modality="CT"))] == ["EMERG-1"]
    assert [i.accession for i in local_worklist.active_items(_query(station="MR_01"))] == ["EMERG-2"]
    assert local_worklist.active_items(_query(station="XR_99")) == []


def test_matching_supports_wildcards_and_patient_lookup():
    _item("EMERG-1")

    assert len(local_worklist.active_items(_query(accession="EMERG*"))) == 1
    assert len(local_worklist.active_items(_query(accession="OTHER"))) == 0
    assert len(local_worklist.active_items(_query(patient="P1"))) == 1
    assert len(local_worklist.active_items(_query(patient="P9"))) == 0
    assert len(local_worklist.active_items(_query(date="20260917"))) == 1
    assert len(local_worklist.active_items(_query(date="20260101"))) == 0


def test_disabled_and_expired_items_are_not_returned():
    _item("EMERG-OFF", enabled=False)
    _item("EMERG-OLD", valid_until=datetime.now(timezone.utc) - timedelta(minutes=5))
    _item("EMERG-NEW", valid_until=datetime.now(timezone.utc) + timedelta(days=1))

    assert [i.accession for i in local_worklist.active_items(_query())] == ["EMERG-NEW"]


# ── fan-out contribution ───────────────────────────────────────────────


def test_answers_for_is_none_without_items_and_creates_no_source():
    assert local_worklist.answers_for(_query()) is None
    with session_factory()() as s:
        assert s.query(MwlSource).count() == 0     # no pseudo source yet


def test_answers_for_creates_the_pseudo_source_on_demand():
    _item("EMERG-1")

    contribution = local_worklist.answers_for(_query())

    assert contribution is not None
    source, answers = contribution
    assert source.name == "local" and source.priority < 0
    assert len(answers) == 1 and answers[0].AccessionNumber == "EMERG-1"
    with session_factory()() as s:
        row = s.query(MwlSource).one()
        assert row.name == "local" and row.enabled is False   # never queried


def test_purge_expired_removes_only_expired_items():
    _item("EMERG-OLD", valid_until=datetime.now(timezone.utc) - timedelta(minutes=1))
    _item("EMERG-KEEP")
    _item("EMERG-LATER", valid_until=datetime.now(timezone.utc) + timedelta(days=1))

    assert local_worklist.purge_expired() == 1
    assert [i.accession for i in local_worklist.active_items(_query())] == [
        "EMERG-KEEP", "EMERG-LATER"
    ]


def test_expiry_for_uses_the_setting():
    settings_service.set_value("local_default_validity_days", "3")
    expiry = local_worklist.expiry_for()
    assert expiry is not None
    delta = expiry - datetime.now(timezone.utc)
    assert 2.9 < delta.total_seconds() / 86400 < 3.1

    settings_service.set_value("local_default_validity_days", "0")
    assert local_worklist.expiry_for() is None


# ── HL7 upsert ─────────────────────────────────────────────────────────


def _parsed(accession="EMERG-HL7", **kwargs) -> dict:
    base = {
        "message_type": "ORM^O01", "control_id": "C1", "order_control": "NW",
        "accession": accession, "patient_id": "P7", "patient_name": "Weber^Karl",
        "birth_date": "1970-01-01", "sex": "M", "modality": "DX",
        "procedure_description": "Thorax p.a.", "scheduled_date": "2026-09-18",
        "scheduled_time": "08:30", "study_uid": "", "station_aet": "XR_01",
        "sps_id": "1", "warnings": [],
    }
    base.update(kwargs)
    return base


def test_upsert_creates_updates_and_cancels():
    created = local_worklist.upsert_from_hl7(_parsed())
    assert created["action"] == "created"

    updated = local_worklist.upsert_from_hl7(_parsed(procedure_description="Thorax seitlich"))
    assert updated["action"] == "updated"
    assert updated["item_id"] == created["item_id"]
    with session_factory()() as s:
        row = s.get(LocalWorklistItem, created["item_id"])
        assert row.procedure_description == "Thorax seitlich"
        assert row.origin == "hl7"

    cancelled = local_worklist.upsert_from_hl7(_parsed(order_control="CA"))
    assert cancelled["action"] == "cancelled"
    with session_factory()() as s:
        assert s.query(LocalWorklistItem).count() == 0


def test_upsert_rejects_a_message_without_accession():
    result = local_worklist.upsert_from_hl7(_parsed(accession=""))
    assert result["action"] == "rejected" and result["error"]


def test_cancelling_an_unknown_order_is_reported():
    result = local_worklist.upsert_from_hl7(_parsed(accession="NOPE", order_control="CA"))
    assert result["action"] == "cancel-unknown"


def test_upsert_never_blanks_existing_fields():
    created = local_worklist.upsert_from_hl7(_parsed())
    local_worklist.upsert_from_hl7(_parsed(patient_name="", modality=""))

    with session_factory()() as s:
        row = s.get(LocalWorklistItem, created["item_id"])
        assert row.patient_name == "Weber^Karl" and row.modality == "DX"


def test_upsert_uses_the_configured_defaults():
    result = local_worklist.upsert_from_hl7(_parsed(station_aet="", modality=""),
                                           default_station_aet="CT_FALLBACK",
                                           default_modality="CT")
    with session_factory()() as s:
        row = s.get(LocalWorklistItem, result["item_id"])
        assert row.station_aet == "CT_FALLBACK" and row.modality == "CT"


def test_upsert_keeps_sps_ids_apart():
    first = local_worklist.upsert_from_hl7(_parsed(sps_id="1"))
    second = local_worklist.upsert_from_hl7(_parsed(sps_id="2"))

    assert first["item_id"] != second["item_id"]
    with session_factory()() as s:
        assert s.query(LocalWorklistItem).count() == 2


def test_publish_metrics_counts_active_items():
    from prometheus_client import REGISTRY

    _item("EMERG-1")
    _item("EMERG-OFF", enabled=False)

    local_worklist.publish_metrics()

    assert REGISTRY.get_sample_value("mwl_local_worklist_items") == 1
