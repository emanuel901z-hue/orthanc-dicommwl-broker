"""End-to-end DIMSE tests without docker: real pynetdicom associations
against the broker SCP (ephemeral ports) with in-process mock upstreams.

Uses the shared sqlite DB from conftest (BROKER_DATABASE_URL).
"""
import pytest
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, generate_uid
from pynetdicom import AE, evt
from pynetdicom.sop_class import ModalityWorklistInformationFind, Verification
from sqlalchemy import select

from mwl_broker.config import Settings
from mwl_broker.db import session_factory
from mwl_broker.dimse import BrokerSCP
from mwl_broker.mock_ris import VARIANTS
from mwl_broker.models import (
    MwlSource,
    PacsTarget,
    QueryLog,
    RoutingRule,
    SeenItem,
    StoreLog,
)
from mwl_broker.upstream import c_echo


def _port(server) -> int:
    return server.server_address[1]


@pytest.fixture()
def mwl_scp():
    """In-process MWL SCP serving VARIANTS['a']."""
    items = VARIANTS["a"]

    def handle_find(event):
        for item in items:
            yield 0xFF00, item
        yield 0x0000, None

    ae = AE(ae_title="RIS_A")
    ae.add_supported_context(ModalityWorklistInformationFind)
    ae.add_supported_context(Verification)
    srv = ae.start_server(("127.0.0.1", 0), block=False,
                          evt_handlers=[(evt.EVT_C_FIND, handle_find)])
    yield _port(srv)
    srv.shutdown()


@pytest.fixture()
def store_scp():
    """In-process storage SCP collecting received datasets."""
    received = []

    def handle_store(event):
        ds = event.dataset
        ds.file_meta = event.file_meta
        received.append(ds)
        return 0x0000

    ae = AE(ae_title="PACS_KH")
    ae.add_supported_context(CTImageStorage)
    srv = ae.start_server(("127.0.0.1", 0), block=False,
                          evt_handlers=[(evt.EVT_C_STORE, handle_store)])
    yield received, _port(srv)
    srv.shutdown()


@pytest.fixture()
def broker():
    settings = Settings(dicom_port=0)
    scp = BrokerSCP(settings)
    scp.start()
    yield _port(scp.server)
    scp.shutdown()


def _cfind(broker_port, query: Dataset):
    ae = AE(ae_title="TESTSCU")
    ae.add_requested_context(ModalityWorklistInformationFind)
    assoc = ae.associate("127.0.0.1", broker_port, ae_title="MWLBROKER")
    assert assoc.is_established
    answers = []
    try:
        for status, ds in assoc.send_c_find(query, ModalityWorklistInformationFind):
            if status and status.Status in (0xFF00, 0xFF01):
                answers.append(ds)
    finally:
        assoc.release()
    return answers


def _wildcard_query() -> Dataset:
    q = Dataset()
    q.SpecificCharacterSet = "ISO_IR 100"
    sps = Dataset()
    sps.ScheduledStationAETitle = ""
    sps.Modality = ""
    sps.ScheduledProcedureStepStartDate = ""
    q.ScheduledProcedureStepSequence = [sps]
    q.PatientName = ""
    q.PatientID = ""
    q.AccessionNumber = ""
    return q


def _ct_dataset(accession: str, study_uid: str) -> FileDataset:
    sop_uid = generate_uid()
    meta = FileMetaDataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID = CTImageStorage
    meta.MediaStorageSOPInstanceUID = sop_uid
    ds = FileDataset(None, {}, file_meta=meta, preamble=b"\0" * 128)
    ds.SOPClassUID = CTImageStorage
    ds.SOPInstanceUID = sop_uid
    ds.Modality = "CT"
    ds.AccessionNumber = accession
    ds.StudyInstanceUID = study_uid
    ds.PatientID = "P1001"
    return ds


def _cstore(broker_port, ds: Dataset) -> int:
    ae = AE(ae_title="TESTSCU")
    ae.add_requested_context(CTImageStorage)
    assoc = ae.associate("127.0.0.1", broker_port, ae_title="MWLBROKER")
    assert assoc.is_established
    try:
        status = assoc.send_c_store(ds)
        return status.Status
    finally:
        assoc.release()


def _seed_source(port: int, name="ris-a", aet="RIS_A") -> int:
    with session_factory()() as s:
        row = MwlSource(name=name, aet=aet, host="127.0.0.1", port=port,
                        calling_aet="MWLBROKER", charset="ISO_IR 100")
        s.add(row)
        s.commit()
        return row.id


def _seed_target(port: int, name="pacs", aet="PACS_KH", is_default=False) -> int:
    with session_factory()() as s:
        row = PacsTarget(name=name, aet=aet, host="127.0.0.1", port=port,
                         calling_aet="MWLBROKER", is_default=is_default)
        s.add(row)
        s.commit()
        return row.id


def test_cfind_proxy_merges_and_logs(broker, mwl_scp):
    _seed_source(mwl_scp)
    answers = _cfind(broker, _wildcard_query())
    assert len(answers) == len(VARIANTS["a"])
    assert {a.AccessionNumber for a in answers} == {"ACC-A-001", "ACC-A-002"}

    with session_factory()() as s:
        log_row = s.scalars(select(QueryLog)).one()
        assert log_row.status == "success"
        assert log_row.answers == 2
        assert log_row.per_source == {"ris-a": 2}
        assert log_row.calling_aet == "TESTSCU"
        assert s.scalars(select(SeenItem)).all().__len__() == 2


def test_cfind_no_sources_returns_success_empty(broker):
    answers = _cfind(broker, _wildcard_query())
    assert answers == []
    with session_factory()() as s:
        log_row = s.scalars(select(QueryLog)).one()
        assert log_row.status == "success"
        assert log_row.answers == 0


def test_cfind_dead_source_marks_partial_failure(broker, mwl_scp):
    _seed_source(mwl_scp)
    _seed_source(1, name="dead-ris", aet="DEAD")  # port 1 — connection refused
    answers = _cfind(broker, _wildcard_query())
    assert len(answers) == 2  # live source still answered
    with session_factory()() as s:
        log_row = s.scalars(select(QueryLog)).one()
        assert log_row.status == "partial"
        assert log_row.per_source["dead-ris"] == "error"


def test_store_routes_to_rule_target(broker, mwl_scp, store_scp):
    received, store_port = store_scp
    source_id = _seed_source(mwl_scp)
    target_id = _seed_target(store_port)
    with session_factory()() as s:
        s.add(RoutingRule(source_id=source_id, target_id=target_id))
        s.commit()

    # C-FIND first so seen_items is populated
    _cfind(broker, _wildcard_query())
    acc = VARIANTS["a"][0].AccessionNumber
    uid = VARIANTS["a"][0].StudyInstanceUID

    assert _cstore(broker, _ct_dataset(acc, uid)) == 0x0000
    assert len(received) == 1
    assert received[0].AccessionNumber == acc

    with session_factory()() as s:
        row = s.scalars(select(StoreLog)).one()
        assert row.status == "success"
        assert row.source_id == source_id
        assert row.target_id == target_id


def test_store_unrouted_strict(broker):
    ds = _ct_dataset("UNKNOWN-ACC", generate_uid())
    assert _cstore(broker, ds) == 0xA700  # strict_store_status default
    with session_factory()() as s:
        row = s.scalars(select(StoreLog)).one()
        assert row.status == "unrouted"


def test_echo_endpoint_helper(mwl_scp):
    c_echo("RIS_A", "127.0.0.1", mwl_scp, "MWLBROKER", timeout_s=5)


# ── Calling-AET allowlist, failure paths, fallbacks, PHI hygiene ───────


@pytest.fixture()
def restricted_broker():
    """Broker that only accepts calling AET 'CT_01'."""
    scp = BrokerSCP(Settings(dicom_port=0, allowed_calling_aets="CT_01"))
    scp.start()
    yield _port(scp.server)
    scp.shutdown()


@pytest.fixture()
def lenient_broker():
    """Broker with strict_store_status=False (store failures → success)."""
    scp = BrokerSCP(Settings(dicom_port=0, strict_store_status=False))
    scp.start()
    yield _port(scp.server)
    scp.shutdown()


def _cfind_final_status(broker_port, query: Dataset) -> int | None:
    """Like _cfind but returns the last non-pending DIMSE status."""
    ae = AE(ae_title="TESTSCU")
    ae.add_requested_context(ModalityWorklistInformationFind)
    assoc = ae.associate("127.0.0.1", broker_port, ae_title="MWLBROKER")
    assert assoc.is_established
    last = None
    try:
        for status, _ds in assoc.send_c_find(query, ModalityWorklistInformationFind):
            if status is not None:
                last = status.Status
    finally:
        assoc.release()
    return last


def test_cfind_rejected_for_disallowed_calling_aet(restricted_broker, mwl_scp):
    _seed_source(mwl_scp)
    assert _cfind_final_status(restricted_broker, _wildcard_query()) == 0xA700
    with session_factory()() as s:
        assert s.scalars(select(QueryLog)).all() == []  # rejected before fan-out


def test_cstore_rejected_for_disallowed_calling_aet(restricted_broker):
    ds = _ct_dataset("ACC-X", generate_uid())
    assert _cstore(restricted_broker, ds) == 0xA700
    with session_factory()() as s:
        assert s.scalars(select(StoreLog)).all() == []


def test_store_unrouted_lenient_returns_success(lenient_broker):
    ds = _ct_dataset("UNKNOWN-ACC", generate_uid())
    assert _cstore(lenient_broker, ds) == 0x0000
    with session_factory()() as s:
        assert s.scalars(select(StoreLog)).one().status == "unrouted"


def test_store_forward_failure_marks_failed(broker):
    _seed_target(1, name="dead-pacs", is_default=True)  # port 1 — refused
    ds = _ct_dataset("ACC-X", generate_uid())
    assert _cstore(broker, ds) == 0xA700  # strict default
    with session_factory()() as s:
        row = s.scalars(select(StoreLog)).one()
        assert row.status == "failed"
        assert row.error


def test_cfind_disabled_source_skipped(broker, mwl_scp):
    _seed_source(mwl_scp)
    dead_id = _seed_source(1, name="dead-ris", aet="DEAD")
    with session_factory()() as s:
        s.get(MwlSource, dead_id).enabled = False
        s.commit()
    answers = _cfind(broker, _wildcard_query())
    assert len(answers) == 2
    with session_factory()() as s:
        log_row = s.scalars(select(QueryLog)).one()
        assert log_row.status == "success"  # disabled source never queried
        assert "dead-ris" not in log_row.per_source


def test_store_routes_via_study_uid_fallback(broker, mwl_scp, store_scp):
    """Empty AccessionNumber → seen_items matched via StudyInstanceUID."""
    received, store_port = store_scp
    source_id = _seed_source(mwl_scp)
    target_id = _seed_target(store_port)
    with session_factory()() as s:
        s.add(RoutingRule(source_id=source_id, target_id=target_id))
        s.commit()
    _cfind(broker, _wildcard_query())
    uid = VARIANTS["a"][0].StudyInstanceUID
    ds = _ct_dataset("", uid)  # accession intentionally empty
    assert _cstore(broker, ds) == 0x0000
    assert len(received) == 1


def test_query_log_never_stores_patient_name(broker, mwl_scp):
    """PHI hygiene: PatientName in the query must not land in query_keys."""
    _seed_source(mwl_scp)
    q = _wildcard_query()
    q.PatientName = "Müller^Hans"
    _cfind(broker, q)
    with session_factory()() as s:
        row = s.scalars(select(QueryLog)).one()
        assert "PatientName" not in row.query_keys
        assert "Müller" not in str(row.query_keys)


def test_cfind_increments_metrics(broker):
    from prometheus_client import REGISTRY

    labels = {"result": "success"}
    before = REGISTRY.get_sample_value("mwl_cfind_requests_total", labels) or 0
    _cfind(broker, _wildcard_query())
    after = REGISTRY.get_sample_value("mwl_cfind_requests_total", labels)
    assert after == before + 1
