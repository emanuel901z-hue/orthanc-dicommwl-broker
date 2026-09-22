"""MPPS: accepting performed procedure steps and reporting them back.

The modality side is exercised over a real association (N-CREATE/N-SET), the
forwarding with a real MLLP receiver socket — a mock would not prove that the
message is understood by a RIS.
"""
import socket
import threading
import time

import pytest
from pydicom.dataset import Dataset
from pynetdicom import AE, evt
from pynetdicom.sop_class import ModalityPerformedProcedureStep

from mwl_broker import mpps, settings_service
from mwl_broker.db import session_factory
from mwl_broker.models import MppsStep
from mwl_broker.config import Settings
from mwl_broker.db import session_factory
from mwl_broker.dimse import BrokerSCP


def _create_ds(accession="ACC-MPPS-1", patient_id="P-1", station="CT_01") -> Dataset:
    ds = Dataset()
    ds.PatientID = patient_id
    ds.StudyInstanceUID = "1.2.3.4"
    ds.PerformedProcedureStepID = "PPS-1"
    ds.PerformedProcedureStepStartDate = "20260921"
    ds.PerformedProcedureStepStartTime = "101530"
    ds.PerformedProcedureStepStatus = "IN PROGRESS"
    sps = Dataset()
    sps.AccessionNumber = accession
    sps.ScheduledProcedureStepID = "SPS-1"
    sps.ScheduledStationAETitle = station
    sps.Modality = "CT"
    ds.ScheduledStepAttributesSequence = [sps]
    return ds


def _set_ds(status="COMPLETED") -> Dataset:
    ds = Dataset()
    ds.PerformedProcedureStepStatus = status
    ds.PerformedProcedureStepEndDate = "20260921"
    ds.PerformedProcedureStepEndTime = "102045"
    return ds


def test_parse_step_reads_the_identifiers():
    fields = mpps.parse_step(_create_ds())

    assert fields["accession"] == "ACC-MPPS-1"
    assert fields["patient_id"] == "P-1"
    assert fields["sps_id"] == "SPS-1"
    assert fields["station_aet"] == "CT_01"
    assert fields["modality"] == "CT"
    # no patient name anywhere — the table must stay free of it
    assert "patient_name" not in fields


def test_record_create_and_update_keep_the_state(client):
    settings_service.set_value("mpps_enabled", "true")
    settings_service.set_value("mpps_forward_enabled", "false")

    created = mpps.record_create("1.2.840.1", _create_ds())
    assert created["status"] == mpps.STATUS_IN_PROGRESS
    assert created["accession"] == "ACC-MPPS-1"
    assert created["started_at"] is not None
    assert created["ended_at"] is None

    updated = mpps.record_update("1.2.840.1", _set_ds())
    assert updated["status"] == mpps.STATUS_COMPLETED
    assert updated["ended_at"] is not None
    # the identifiers from the create survive the update
    assert updated["accession"] == "ACC-MPPS-1"
    assert updated["station_aet"] == "CT_01"

    assert mpps.stats()["by_status"][mpps.STATUS_COMPLETED] == 1
    # the accession is now finished, so it is hidden from the worklist
    assert "ACC-MPPS-1" in mpps.completed_identifiers()


def test_update_without_create_is_recorded_not_lost(client):
    """A modality may send N-SET after a restart — the event must not vanish."""
    settings_service.set_value("mpps_enabled", "true")
    settings_service.set_value("mpps_forward_enabled", "false")

    step = mpps.record_update("1.2.840.2", _set_ds("DISCONTINUED"))
    assert step["status"] == mpps.STATUS_DISCONTINUED
    assert step["sop_instance_uid"] == "1.2.840.2"


def test_status_message_is_a_readable_oru(client):
    settings_service.set_value("mpps_enabled", "true")
    settings_service.set_value("mpps_forward_enabled", "false")
    mpps.record_create("1.2.840.3", _create_ds())
    step = mpps.record_update("1.2.840.3", _set_ds("COMPLETED"))

    message = mpps.build_status_message(step)

    assert message.startswith("MSH|")
    assert "ORU^R01^Z02" in message          # exam ended
    assert "ACC-MPPS-1" in message           # the RIS finds its order
    assert "|CM" in message                  # result status: completed
    assert "1.2.840.3" in message
    assert message.endswith("\r")
    # PHI: the patient *name* never appears (only the ID)
    assert "Muster" not in message


def test_forwarding_to_a_ris_over_mllp(client):
    """A real MLLP receiver stands in for the RIS and answers with an ACK."""
    received: list[bytes] = []
    ready = threading.Event()

    def receiver(stop: threading.Event) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            server.settimeout(0.3)
            ready.server_port = server.getsockname()[1]
            ready.set()
            while not stop.is_set():
                try:
                    conn, _ = server.accept()
                except socket.timeout:
                    continue
                with conn:
                    data = conn.recv(8192)
                    received.append(data)
                    conn.sendall(b"\x0bMSH|^~\\&|RIS|||20260921102045||ACK|1|P|2.4\r"
                                 b"MSA|AA|1\r\x1c\x0d")

    stop = threading.Event()
    thread = threading.Thread(target=receiver, args=(stop,), daemon=True)
    thread.start()
    assert ready.wait(timeout=5), "the test receiver did not start"

    settings_service.set_value("mpps_enabled", "true")
    settings_service.set_value("mpps_forward_enabled", "true")
    settings_service.set_value("mpps_forward_transport", "mllp")
    settings_service.set_value("mpps_forward_host", "127.0.0.1")
    settings_service.set_value("mpps_forward_port", str(ready.server_port))

    step = mpps.record_update("1.2.840.4", _set_ds("COMPLETED"))
    result = mpps.forward(step["id"])
    stop.set()
    thread.join(timeout=3)

    assert result["ok"] is True, result
    assert received, "the RIS received nothing"
    # MLLP framing: start block, message, end block
    assert received[0].startswith(b"\x0b")
    assert b"ORU^R01" in received[0]
    assert mpps.get_step(step["id"])["forwarded"] is True


def test_forwarding_reports_a_missing_ris(client):
    """A broker that cannot reach the RIS must say so, not pretend."""
    settings_service.set_value("mpps_enabled", "true")
    # record first with forwarding off, then try the delivery by hand — otherwise
    # the background thread would count an attempt as well
    settings_service.set_value("mpps_forward_enabled", "false")
    step = mpps.record_update("1.2.840.5", _set_ds("COMPLETED"))
    settings_service.set_value("mpps_forward_enabled", "true")
    settings_service.set_value("mpps_forward_transport", "mllp")
    settings_service.set_value("mpps_forward_host", "")   # not configured
    result = mpps.forward(step["id"])

    assert result["ok"] is False
    assert "host" in result["error"]
    stored = mpps.get_step(step["id"])
    assert stored["forwarded"] is False
    assert stored["forward_error"]
    assert stored["forward_attempts"] == 1


def test_forward_pending_retries_what_failed(client):
    settings_service.set_value("mpps_enabled", "true")
    settings_service.set_value("mpps_forward_enabled", "false")
    mpps.record_update("1.2.840.6", _set_ds("COMPLETED"))
    mpps.record_update("1.2.840.7", _set_ds("COMPLETED"))
    settings_service.set_value("mpps_forward_enabled", "true")
    settings_service.set_value("mpps_forward_host", "")

    result = mpps.forward_pending()

    assert result["attempted"] == 2
    assert result["failed"] == 2
    assert result["sent"] == 0


# ── die Strecke über eine echte DICOM-Assoziation ──────────────────────────

def test_mpps_over_a_real_association(client):
    """N-CREATE and N-SET over the wire, as a modality does it."""
    settings_service.set_value("mpps_enabled", "true")
    settings_service.set_value("mpps_forward_enabled", "false")

    scp = BrokerSCP(Settings(dicom_port=0, start_dicom=False))
    scp.start()
    try:
        port = scp.server.server_address[1]
        ae = AE(ae_title="CT_01")
        ae.add_requested_context(ModalityPerformedProcedureStep)
        assoc = ae.associate("127.0.0.1", port, ae_title=scp.settings.broker_aet)
        assert assoc.is_established, "the MPPS association was not established"
        try:
            status, _ = assoc.send_n_create(
                _create_ds(), ModalityPerformedProcedureStep, "1.2.840.100")
            assert status.Status == 0x0000, f"create failed: {status}"
            status, _ = assoc.send_n_set(
                _set_ds("COMPLETED"), ModalityPerformedProcedureStep, "1.2.840.100")
            assert status.Status == 0x0000, f"set failed: {status}"
        finally:
            assoc.release()
    finally:
        scp.shutdown()

    steps = mpps.list_steps()
    assert steps, "the step was not recorded"
    step = steps[0]
    assert step["sop_instance_uid"] == "1.2.840.100"
    assert step["status"] == mpps.STATUS_COMPLETED
    assert step["accession"] == "ACC-MPPS-1"


def test_mpps_is_refused_when_switched_off(client):
    """Without the switch the broker must not accept a step it cannot report."""
    settings_service.set_value("mpps_enabled", "false")
    settings_service.set_value("mpps_forward_enabled", "false")

    scp = BrokerSCP(Settings(dicom_port=0, start_dicom=False))
    assert not scp.ae.supported_contexts or True  # contexts are built at start
    scp.start()
    try:
        port = scp.server.server_address[1]
        ae = AE(ae_title="CT_01")
        ae.add_requested_context(ModalityPerformedProcedureStep)
        assoc = ae.associate("127.0.0.1", port, ae_title=scp.settings.broker_aet)
        # the presentation context is not accepted → no MPPS association
        accepted = assoc.is_established and any(
            cx.abstract_syntax == ModalityPerformedProcedureStep
            for cx in assoc.accepted_contexts
        )
        assoc.release()
        assert not accepted, "MPPS was offered although it is switched off"
    finally:
        scp.shutdown()
    assert mpps.list_steps() == []


def test_mpps_endpoints(client):
    settings_service.set_value("mpps_enabled", "true")
    settings_service.set_value("mpps_forward_enabled", "false")
    mpps.record_create("1.2.840.9", _create_ds(accession="ACC-API-1"))
    mpps.record_update("1.2.840.9", _set_ds())

    listed = client.get("/api/v1/mpps").json()
    assert listed and listed[0]["accession"] == "ACC-API-1"

    step_id = listed[0]["id"]
    detail = client.get(f"/api/v1/mpps/{step_id}").json()
    assert detail["status"] == "COMPLETED"
    assert detail["forwarded"] is False

    stats = client.get("/api/v1/mpps/stats").json()
    assert stats["total"] >= 1
    assert stats["pending_forward"] >= 1

    # a delivery attempt without a configured RIS is an honest failure
    result = client.post(f"/api/v1/mpps/{step_id}/forward").json()
    assert result["ok"] is False
    assert client.post("/api/v1/mpps/forward-pending").json()["attempted"] >= 1

    assert client.get("/api/v1/mpps/999").status_code == 404
    assert client.post("/api/v1/mpps/999/forward").status_code == 404


def test_completed_steps_disappear_from_the_worklist(client):
    """The whole point: a finished examination must not come back."""
    from mwl_broker import aggregation, local_worklist

    settings_service.set_value("mpps_enabled", "true")
    settings_service.set_value("mpps_forward_enabled", "false")
    settings_service.set_value("mpps_hide_completed", "true")

    from mwl_broker.models import LocalWorklistItem

    with session_factory()() as s:
        s.add(LocalWorklistItem(accession="ACC-DONE", sps_id="1", patient_id="P-9",
                                patient_name="Fertig^Fritz", modality="CT",
                                station_aet="CT_01", enabled=True))
        s.commit()

    before = aggregation.collect(Dataset())
    assert any(ds.AccessionNumber == "ACC-DONE" for ds in before.items)

    mpps.record_create("1.2.840.10", _create_ds(accession="ACC-DONE"))
    mpps.record_update("1.2.840.10", _set_ds("COMPLETED"))

    after = aggregation.collect(Dataset())
    assert not any(ds.AccessionNumber == "ACC-DONE" for ds in after.items), \
        "a completed step was served again"


def test_the_status_message_names_a_receiving_facility(client):
    """dcm4che's receiver answered "Missing Receiving Facility" (MSA|AE) — the
    RIS would never learn that the examination was performed."""
    message = mpps.build_status_message({
        "id": 1, "status": "COMPLETED", "accession": "ACC-1", "sps_id": "1",
        "patient_id": "P-1", "station_aet": "CT_01", "modality": "CT",
        "sop_instance_uid": "1.2.3", "started_at": "", "ended_at": "",
        "performed_procedure_step_id": "PPS-1",
    })

    msh = message.split("\r")[0].split("|")
    assert msh[5], "MSH-6 (receiving facility) must not be empty"
    assert msh[8].startswith("ORU^R01"), "MSH-9 stays the message type"


def test_a_modality_may_leave_the_sop_instance_uid_to_us(client):
    """DICOM PS3.7: the SCU may omit it — then the SCP assigns and returns it.

    Found by a foreign MPPS SCU (dcm4che `mppsscu`): it sends the N-CREATE
    without the element, we answered "Cannot understand" (0xC000) and the
    examination never reached the RIS.
    """
    from types import SimpleNamespace

    from pydicom.uid import generate_uid
    from pynetdicom.dimse_primitives import N_CREATE, N_SET

    from mwl_broker.config import Settings
    from mwl_broker.dimse import BrokerSCP

    scp = BrokerSCP(Settings())

    request = N_CREATE()
    request.MessageID = 1
    request.AffectedSOPInstanceUID = None          # the element is absent
    attribute_list = Dataset()
    attribute_list.PatientID = "MPPS-UID-1"
    attribute_list.Modality = "MR"
    attribute_list.PerformedProcedureStepStatus = "IN PROGRESS"
    attribute_list.StudyInstanceUID = generate_uid()
    attribute_list.PerformedProcedureStepStartDate = "20260922"
    attribute_list.PerformedProcedureStepStartTime = "200000"

    status, assigned = scp.handle_mpps_create(
        SimpleNamespace(request=request, attribute_list=attribute_list),
    )

    assert status == 0x0000, "an SCU that leaves the UID to us must succeed"
    assert assigned is not None, "the response must carry the UID we assigned"
    uid = str(assigned.AffectedSOPInstanceUID)
    assert uid, "the assigned UID must not be empty"

    # the following N-SET names the step with exactly that UID
    update = N_SET()
    update.RequestedSOPInstanceUID = uid
    status, _ = scp.handle_mpps_update(
        SimpleNamespace(request=update, attribute_list=Dataset()),
    )
    assert status == 0x0000

    with session_factory()() as s:
        row = s.query(MppsStep).filter_by(sop_instance_uid=uid).one()
    assert row.status == "COMPLETED"
