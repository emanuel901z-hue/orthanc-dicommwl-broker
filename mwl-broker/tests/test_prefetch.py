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


# ── bounded work: time budget and concurrency ──────────────────────────


def _three_studies():
    return [{"study_uid": f"1.2.{n}", "study_date": "20200101", "description": "CT",
             "modalities": "CT", "instances": "1"} for n in (1, 2, 3)]


def test_studies_that_no_longer_fit_the_budget_are_skipped_not_cut_off(client, monkeypatch):
    """The whole call is bounded — a half-transferred study is worse than none.

    Each C-MOVE occupies a request worker for as long as the PACS takes, so the
    budget covers the *call*, not each study. What does not fit is reported as
    `skipped` instead of being started and aborted mid-transfer.
    """
    import time as time_module

    _target(client, "pacs", "QR_AET", 1)
    _target(client, "dest", "DEST_AET", 1)
    client.put("/api/v1/settings/prefetch_timeout_s", json={"value": "5"})
    monkeypatch.setattr(prefetch, "find_studies", lambda *a, **k: _three_studies())

    def slow_move(node, uid, dest, **kwargs):
        time_module.sleep(2.5)          # eats most of the 5 s budget
        return {"study_uid": uid, "status": 0x0000, "completed": 1, "failed": 0,
                "warning": 0, "ok": True, "error": ""}

    monkeypatch.setattr(prefetch, "move_study", slow_move)

    result = client.post("/api/v1/prefetch?dry_run=false", json={
        "patient_id": "P-100", "query_node": "pacs", "destination": "dest",
    }).json()

    assert len(result["moved"]) == 1
    assert result["skipped"] == ["1.2.2", "1.2.3"]


def test_too_many_parallel_calls_are_refused_instead_of_queued(client, monkeypatch):
    """A prefetch holds a worker and a PACS association — the rest gets 429.

    Without the limit, a handful of concurrent calls would tie up the API (and
    with it `/healthz`) for everyone: the broker would look dead while it is
    only busy prefetching.
    """
    _target(client, "pacs", "QR_AET", 1)
    _target(client, "dest", "DEST_AET", 1)
    client.put("/api/v1/settings/prefetch_max_concurrency", json={"value": "1"})
    monkeypatch.setattr(prefetch, "find_studies", lambda *a, **k: _three_studies()[:1])
    monkeypatch.setattr(prefetch, "move_study", lambda node, uid, dest, **k: {
        "study_uid": uid, "status": 0x0000, "completed": 1, "failed": 0,
        "warning": 0, "ok": True, "error": ""})
    body = {"patient_id": "P-100", "query_node": "pacs", "destination": "dest"}

    with prefetch._slot():                       # pretend another call is running
        busy = client.post("/api/v1/prefetch?dry_run=false", json=body)
        assert busy.status_code == 429
        assert "already running" in busy.json()["detail"]

    # the slot was released again — the next call goes through
    assert client.post("/api/v1/prefetch?dry_run=false", json=body).status_code == 200


def test_a_dry_run_is_never_refused_by_the_concurrency_limit(client, monkeypatch):
    """Looking is cheap and must stay available even while a prefetch runs."""
    _target(client, "pacs", "QR_AET", 1)
    _target(client, "dest", "DEST_AET", 1)
    client.put("/api/v1/settings/prefetch_max_concurrency", json={"value": "1"})
    monkeypatch.setattr(prefetch, "find_studies", lambda *a, **k: _three_studies()[:1])

    with prefetch._slot():
        response = client.post("/api/v1/prefetch?dry_run=true", json={
            "patient_id": "P-100", "query_node": "pacs", "destination": "dest"})

    assert response.status_code == 200
    assert response.json()["dry_run"] is True


def test_the_prefetch_does_not_hold_a_database_session_during_the_move(client, monkeypatch):
    """The C-MOVE can take the whole budget — it must not keep a pooled
    connection, or a few calls would starve every other endpoint and the DIMSE
    handlers (pool: 10 + 20 overflow)."""
    from mwl_broker import db

    _target(client, "pacs", "QR_AET", 1)
    _target(client, "dest", "DEST_AET", 1)
    monkeypatch.setattr(prefetch, "find_studies", lambda *a, **k: _three_studies()[:1])

    opened = []
    real_engine = db.get_engine()

    def counting_move(node, uid, dest, **kwargs):
        # while the "move" runs, the API must be able to take a fresh session
        with db.get_session() as s:
            s.execute(__import__("sqlalchemy").text("SELECT 1"))
        opened.append(uid)
        return {"study_uid": uid, "status": 0x0000, "completed": 1, "failed": 0,
                "warning": 0, "ok": True, "error": ""}

    monkeypatch.setattr(prefetch, "move_study", counting_move)

    response = client.post("/api/v1/prefetch?dry_run=false", json={
        "patient_id": "P-100", "query_node": "pacs", "destination": "dest"})

    assert response.status_code == 200
    assert opened == ["1.2.1"]
    assert real_engine is not None


# ── Fehlerpfade, die die Oberfläche in Klartext melden muss ─────────────


def test_a_missing_patient_id_is_refused(client):
    with pytest.raises(ValueError, match="patient_id is required"):
        prefetch.prefetch("  ", query_node="a", destination="b")


def test_an_unknown_destination_is_refused(client):
    _target(client, "pacs", "QR_AET", 1)
    with pytest.raises(ValueError, match="unknown destination"):
        prefetch.prefetch("P-1", query_node="pacs", destination="nope")


def test_a_rejected_association_is_an_error_not_an_empty_answer(client, monkeypatch):
    """A PACS that refuses the association must not look like "no priors"."""
    node = prefetch.NodeCfg(id=1, name="pacs", aet="QR", host="127.0.0.1", port=1)

    class _Refused:
        is_established = False

    monkeypatch.setattr(prefetch, "_associate", lambda ae, n, timeout: _Refused())

    with pytest.raises(ConnectionError, match="association rejected"):
        prefetch.find_studies(node, "P-1")
    with pytest.raises(ConnectionError, match="association rejected"):
        prefetch.move_study(node, "1.2.3", "DEST")


def test_tls_arguments_are_only_built_for_a_tls_node(client):
    plain = prefetch.NodeCfg(id=1, name="p", aet="A", host="h", port=1, tls=False)
    secure = prefetch.NodeCfg(id=2, name="s", aet="B", host="h", port=1, tls=True)

    assert prefetch._tls_args(plain) is None
    assert prefetch._tls_args(secure) is not None      # the TLS context is built
