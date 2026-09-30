"""Prior-study prefetch: find a patient's earlier studies and pull them in.

The broker acts as a **query/retrieve client** here (study-level C-FIND + C-MOVE
SCU) — it still never offers C-MOVE as a service. The end-to-end test runs two
real pynetdicom servers in-process: a Q/R provider that answers the study query
and performs the move, and a storage SCP that receives the images.
"""
import pytest
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, generate_uid
from pynetdicom import AE, evt
from pynetdicom.sop_class import (
    StudyRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelMove,
)

from mwl_broker import prefetch


def _study(uid: str, date: str, description: str = "CT Thorax") -> Dataset:
    ds = Dataset()
    ds.PatientID = "P-100"
    ds.StudyInstanceUID = uid
    ds.StudyDate = date
    ds.StudyDescription = description
    ds.ModalitiesInStudy = "CT"
    ds.NumberOfStudyRelatedInstances = "2"
    return ds


def _instance(study_uid: str) -> Dataset:
    uid = generate_uid()
    ds = Dataset()
    # a C-STORE sub-operation needs the file meta (SOP class + transfer syntax)
    ds.file_meta = FileMetaDataset()
    ds.file_meta.MediaStorageSOPClassUID = CTImageStorage
    ds.file_meta.MediaStorageSOPInstanceUID = uid
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.SOPClassUID = CTImageStorage
    ds.SOPInstanceUID = uid
    ds.StudyInstanceUID = study_uid
    ds.PatientID = "P-100"
    ds.PatientName = "Muster^Max"
    return ds


def _target(client, name: str, aet: str, port: int) -> None:
    client.post("/api/v1/targets", json={
        "name": name, "aet": aet, "host": "127.0.0.1", "port": port,
        "calling_aet": "MWLBROKER", "enabled": True, "is_default": False,
    })


# ── pure helpers ───────────────────────────────────────────────────────


def test_a_study_is_reported_without_the_patient_name(client):
    study = prefetch._study_dict(_study("1.2.3", "20200101"))

    assert study["study_uid"] == "1.2.3"
    assert study["study_date"] == "20200101"
    assert "patient" not in {key.lower() for key in study}


def test_an_unknown_status_gets_a_plain_language_text(client):
    assert prefetch.STATUS_TEXT[0xA801] == "move destination unknown to the query node"


# ── the endpoint (network stubbed) ─────────────────────────────────────


def test_dry_run_lists_the_priors_and_moves_nothing(client, monkeypatch):
    _target(client, "pacs", "QR_AET", 1)
    _target(client, "dest", "DEST_AET", 1)
    monkeypatch.setattr(prefetch, "find_studies",
                        lambda *a, **k: [{"study_uid": "1.2.3", "study_date": "20200101",
                                          "description": "CT", "modalities": "CT",
                                          "instances": "2"}])
    monkeypatch.setattr(prefetch, "move_study",
                        lambda *a, **k: pytest.fail("a dry run must not move"))

    result = client.post("/api/v1/prefetch?dry_run=true", json={
        "patient_id": "P-100", "query_node": "pacs", "destination": "dest",
    }).json()

    assert result["dry_run"] is True
    assert [s["study_uid"] for s in result["studies"]] == ["1.2.3"]
    assert result["moved"] == []
    # PHI-free: the patient ID is the query, never echoed
    assert "patient_id" not in result


def test_applying_moves_every_prior(client, monkeypatch):
    _target(client, "pacs", "QR_AET", 1)
    _target(client, "dest", "DEST_AET", 1)
    monkeypatch.setattr(prefetch, "find_studies",
                        lambda *a, **k: [{"study_uid": "1.2.3", "study_date": "20200101",
                                          "description": "CT", "modalities": "CT",
                                          "instances": "2"}])
    moved = []
    monkeypatch.setattr(prefetch, "move_study",
                        lambda node, uid, dest, **k: moved.append((uid, dest)) or {
                            "study_uid": uid, "status": 0x0000, "completed": 2,
                            "failed": 0, "warning": 0, "ok": True, "error": ""})

    result = client.post("/api/v1/prefetch?dry_run=false", json={
        "patient_id": "P-100", "query_node": "pacs", "destination": "dest",
    }).json()

    assert result["dry_run"] is False
    assert result["moved"][0]["ok"] is True
    assert moved and moved[0][0] == "1.2.3"


def test_an_unknown_node_is_refused_before_any_network_call(client):
    response = client.post("/api/v1/prefetch", json={
        "patient_id": "P-100", "query_node": "nope", "destination": "dest",
    })

    assert response.status_code == 422
    assert "unknown query node" in response.json()["detail"]


# ── end to end: real C-FIND + C-MOVE + C-STORE ─────────────────────────


@pytest.fixture()
def qr_network():
    """A Q/R provider (study C-FIND + C-MOVE) and a storage SCP as destination."""
    received: list[Dataset] = []
    studies = [_study("1.2.840.1", "20200101"), _study("1.2.840.2", "20210101")]
    instances = {study.StudyInstanceUID: [_instance(study.StudyInstanceUID)]
                 for study in studies}

    def handle_store(event):
        received.append(event.dataset)
        return 0x0000

    store_ae = AE(ae_title="DEST_AET")
    store_ae.add_supported_context(CTImageStorage)
    store = store_ae.start_server(("127.0.0.1", 0), block=False,
                                  evt_handlers=[(evt.EVT_C_STORE, handle_store)])

    def handle_find(event):
        for study in studies:
            yield 0xFF00, study
        yield 0x0000, None

    def handle_move(event):
        # 1) destination address, 2) number of sub-operations, 3) (status, dataset)…
        yield ("127.0.0.1", store.server_address[1])
        uid = str(event.identifier.StudyInstanceUID)
        yield len(instances[uid])
        for ds in instances[uid]:
            yield 0xFF00, ds
        yield 0x0000, None

    qr_ae = AE(ae_title="QR_AET")
    qr_ae.add_supported_context(StudyRootQueryRetrieveInformationModelFind)
    qr_ae.add_supported_context(StudyRootQueryRetrieveInformationModelMove)
    # the C-MOVE SCP opens the sub-operation association itself — it needs the
    # storage presentation context as a *requested* one
    qr_ae.add_requested_context(CTImageStorage)
    qr = qr_ae.start_server(("127.0.0.1", 0), block=False,
                            evt_handlers=[(evt.EVT_C_FIND, handle_find),
                                          (evt.EVT_C_MOVE, handle_move)])
    yield qr, store, received
    qr.shutdown()
    store.shutdown()


def test_prefetch_pulls_the_priors_to_the_destination(client, qr_network):
    qr, store, received = qr_network
    _target(client, "pacs-main", "QR_AET", qr.server_address[1])
    _target(client, "dest", "DEST_AET", store.server_address[1])

    plan = client.post("/api/v1/prefetch?dry_run=true", json={
        "patient_id": "P-100", "query_node": "pacs-main", "destination": "dest",
    }).json()
    # newest first, and nothing moved yet
    assert [s["study_uid"] for s in plan["studies"]] == ["1.2.840.2", "1.2.840.1"]
    assert received == []

    applied = client.post("/api/v1/prefetch?dry_run=false", json={
        "patient_id": "P-100", "query_node": "pacs-main", "destination": "dest",
    }).json()

    assert all(move["ok"] for move in applied["moved"])
    assert len(applied["moved"]) == 2
    # the images really arrived at the destination SCP
    assert {str(ds.StudyInstanceUID) for ds in received} == {"1.2.840.1", "1.2.840.2"}


def test_prefetch_can_skip_the_study_being_read(client, qr_network):
    qr, store, _received = qr_network
    _target(client, "pacs-main", "QR_AET", qr.server_address[1])
    _target(client, "dest", "DEST_AET", store.server_address[1])

    plan = client.post("/api/v1/prefetch?dry_run=true", json={
        "patient_id": "P-100", "query_node": "pacs-main", "destination": "dest",
        "exclude_study_uid": "1.2.840.2",
    }).json()

    assert [s["study_uid"] for s in plan["studies"]] == ["1.2.840.1"]
