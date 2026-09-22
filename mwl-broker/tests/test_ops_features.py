"""F6 (MPPS N-GET + Statistik je Modalität), F7 (Stations-Matrix), B6 (Selbstüberwachung).

Die drei kleinen Betreiber-Funktionen aus docs/next-steps.md, Schritt 2.
"""
import shutil

import pytest
from pydicom.dataset import Dataset

from mwl_broker import health_checks, mpps, settings_service
from mwl_broker.config import Settings


def _step_dataset(status="COMPLETED") -> Dataset:
    ds = Dataset()
    ds.PerformedProcedureStepStatus = status
    ds.PerformedProcedureStepEndDate = "20260922"
    ds.PerformedProcedureStepEndTime = "101500"
    return ds


def _create(accession="ACC-OPS-1", station="CT_01", modality="CT") -> Dataset:
    ds = Dataset()
    ds.PatientID = "P-1"
    ds.StudyInstanceUID = "1.2.840.113619.2.55.3.1"
    ds.PerformedProcedureStepID = "PPS-1"
    sps = Dataset()
    sps.AccessionNumber = accession
    sps.ScheduledProcedureStepID = "SPS-1"
    sps.ScheduledStationAETitle = station
    sps.Modality = modality
    ds.ScheduledStepAttributesSequence = [sps]
    return ds


# ── F6: N-GET ─────────────────────────────────────────────────────────────

def test_a_modality_can_read_its_step_back(client):
    """N-GET: the modality verifies what the broker stored."""
    settings_service.set_value("mpps_enabled", "true")
    settings_service.set_value("mpps_forward_enabled", "false")
    mpps.record_create("1.2.840.100", _create())
    mpps.record_update("1.2.840.100", _step_dataset())

    step = mpps.get_step_by_uid("1.2.840.100")
    assert step is not None
    ds = mpps.to_dataset(step)

    assert ds.PerformedProcedureStepStatus == "COMPLETED"
    assert ds.PerformedProcedureStepID == "PPS-1"
    assert ds.PerformedProcedureStepEndDate == "20260922"
    sps = ds.ScheduledStepAttributesSequence[0]
    assert sps.AccessionNumber == "ACC-OPS-1"
    assert sps.ScheduledStationAETitle == "CT_01"
    assert sps.Modality == "CT"


def test_n_get_for_an_unknown_step_is_answered_with_not_found(client):
    assert mpps.get_step_by_uid("does-not-exist") is None


def test_n_get_over_a_real_association(client):
    """The handler answers on the wire, not only in-process."""
    from pynetdicom import AE
    from pynetdicom.sop_class import ModalityPerformedProcedureStep

    from mwl_broker.config import Settings
    from mwl_broker.dimse import BrokerSCP

    settings_service.set_value("mpps_enabled", "true")
    settings_service.set_value("mpps_forward_enabled", "false")
    mpps.record_create("1.2.840.101", _create(accession="ACC-OPS-2"))
    mpps.record_update("1.2.840.101", _step_dataset())

    scp = BrokerSCP(Settings(dicom_port=0, start_dicom=False))
    scp.start()
    try:
        port = scp.server.server_address[1]
        ae = AE(ae_title="CT_01")
        ae.add_requested_context(ModalityPerformedProcedureStep)
        assoc = ae.associate("127.0.0.1", port, ae_title=scp.settings.broker_aet)
        assert assoc.is_established
        try:
            status, ds = assoc.send_n_get(
                [0x00400041, 0x00080050, 0x00401001],   # status, accession, SPS-ID
                ModalityPerformedProcedureStep, "1.2.840.101")
            assert status.Status == 0x0000, f"N-GET failed: {status}"
            assert ds is not None
            assert str(ds.PerformedProcedureStepStatus) == "COMPLETED"
        finally:
            assoc.release()
    finally:
        scp.shutdown()


# ── F6: Statistik je Modalität ────────────────────────────────────────────

def test_stats_show_which_modality_reports_nothing(client):
    settings_service.set_value("mpps_enabled", "true")
    settings_service.set_value("mpps_forward_enabled", "false")
    mpps.record_create("1.2.840.102", _create(accession="ACC-OPS-3", modality="CT"))
    mpps.record_create("1.2.840.103", _create(accession="ACC-OPS-4", modality="MR"))

    body = client.get("/api/v1/mpps/stats").json()

    assert body["by_modality"]["CT"] == 1
    assert body["by_modality"]["MR"] == 1
    # a step without a modality is counted under a readable name, not dropped
    mpps.record_create("1.2.840.104", _create(accession="ACC-OPS-5", modality=""))
    assert "(unbekannt)" in client.get("/api/v1/mpps/stats").json()["by_modality"]


# ── F7: Stations-Matrix ───────────────────────────────────────────────────

@pytest.fixture()
def two_sources(client):
    a = client.post("/api/v1/sources", json={
        "name": "ris-a", "aet": "RIS_A", "host": "127.0.0.1", "port": 1,
        "calling_aet": "MWLBROKER", "charset": "ISO_IR 100",
        "enabled": True, "timeout_s": 1, "priority": 10}).json()
    b = client.post("/api/v1/sources", json={
        "name": "ris-b", "aet": "RIS_B", "host": "127.0.0.1", "port": 1,
        "calling_aet": "MWLBROKER", "charset": "ISO_IR 100",
        "enabled": True, "timeout_s": 1, "priority": 20}).json()
    return a, b


def test_station_matrix_shows_what_each_console_sees(client, two_sources):
    a, b = two_sources
    client.post("/api/v1/station-rules", json={
        "name": "ct-only", "station_aet": "CT_01", "mode": "allow",
        "source_ids": [a["id"]], "enabled": True})

    body = client.post("/api/v1/simulate/stations",
                       json={"station_aets": ["CT_01", "MR_01"]}).json()

    by_station = {entry["station_aet"]: entry for entry in body["stations"]}
    assert body["source_count"] == 2

    ct = by_station["CT_01"]
    assert ct["rule_name"] == "ct-only"
    visible = [s["name"] for s in ct["sources"] if s["visible"]]
    assert visible == ["ris-a"], ct
    # the other source is listed as hidden, not silently dropped
    assert any(not s["visible"] for s in ct["sources"])

    mr = by_station["MR_01"]
    assert mr["rule_id"] is None
    assert all(s["visible"] for s in mr["sources"])


def test_station_matrix_defaults_to_the_configured_rules(client, two_sources):
    a, _b = two_sources
    client.post("/api/v1/station-rules", json={
        "name": "ct-only", "station_aet": "CT_01", "mode": "allow",
        "source_ids": [a["id"]], "enabled": True})

    body = client.post("/api/v1/simulate/stations", json={}).json()

    assert [entry["station_aet"] for entry in body["stations"]] == ["CT_01"]


# ── B6: Selbstüberwachung ─────────────────────────────────────────────────

def test_health_warns_when_the_spool_disk_is_tight(client, monkeypatch, tmp_path):
    from mwl_broker.db import session_factory

    settings_service.set_value("spool_enabled", "true")
    settings_service.set_value("spool_dir", str(tmp_path))

    class Usage:
        total = 100 * 1024 ** 3
        free = 2 * 1024 ** 3
        used = total - free

    monkeypatch.setattr(shutil, "disk_usage", lambda _path: Usage())
    with session_factory()() as s:
        findings = health_checks.config_findings(s, Settings())

    codes = {f["code"] for f in findings}
    assert "spool_disk_tight" in codes
    assert not any(f["severity"] == "error" for f in findings if f["code"].startswith("spool_disk"))


def test_health_reports_a_full_spool_disk_as_error(client, monkeypatch, tmp_path):
    from mwl_broker.db import session_factory

    settings_service.set_value("spool_enabled", "true")
    settings_service.set_value("spool_dir", str(tmp_path))

    class Usage:
        total = 100 * 1024 ** 3
        free = int(0.2 * 1024 ** 3)
        used = total - free

    monkeypatch.setattr(shutil, "disk_usage", lambda _path: Usage())
    with session_factory()() as s:
        findings = health_checks.config_findings(s, Settings())

    entry = next(f for f in findings if f["code"] == "spool_disk_low")
    assert entry["severity"] == "error"
    assert "refuses new instances" in entry["message"]


def test_health_is_quiet_when_everything_is_fine(client, monkeypatch, tmp_path):
    from mwl_broker.db import session_factory

    settings_service.set_value("spool_enabled", "true")
    settings_service.set_value("spool_dir", str(tmp_path))

    class Usage:
        total = 100 * 1024 ** 3
        free = 80 * 1024 ** 3
        used = total - free

    monkeypatch.setattr(shutil, "disk_usage", lambda _path: Usage())
    with session_factory()() as s:
        findings = health_checks.config_findings(s, Settings())

    assert not [f for f in findings if f["code"].startswith("spool_disk")]
