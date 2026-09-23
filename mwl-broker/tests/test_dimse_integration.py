"""End-to-end DIMSE tests without docker: real pynetdicom associations
against the broker SCP (ephemeral ports) with in-process mock upstreams.

Uses the shared sqlite DB from conftest (BROKER_DATABASE_URL).
"""
import socket
import threading
import time

import pytest
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, generate_uid
from pynetdicom import AE, evt
from pynetdicom.sop_class import ModalityWorklistInformationFind, Verification
from sqlalchemy import select

from mwl_broker import settings_service
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
    TransformRule,
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


def _seed_source(port: int, name="ris-a", aet="RIS_A", timeout_s=10) -> int:
    with session_factory()() as s:
        row = MwlSource(name=name, aet=aet, host="127.0.0.1", port=port,
                        calling_aet="MWLBROKER", charset="ISO_IR 100",
                        timeout_s=timeout_s)
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
    """Broker that only accepts calling AET 'CT_01'.

    Restrictions come from the runtime settings service (DB override over the
    ENV default) — the same path the UI writes to.
    """
    settings_service.set_value("allowed_calling_aets", "CT_01")
    scp = BrokerSCP(Settings(dicom_port=0))
    scp.start()
    yield _port(scp.server)
    scp.shutdown()


@pytest.fixture()
def lenient_broker():
    """Broker with strict_store_status=false (store failures → success)."""
    settings_service.set_value("strict_store_status", "false")
    scp = BrokerSCP(Settings(dicom_port=0))
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


def test_store_forward_failure_is_spooled_and_accepted(broker):
    """Store and forward: the instance is queued and the modality is told OK."""
    from mwl_broker import spool

    _seed_target(1, name="dead-pacs", is_default=True)  # port 1 — refused
    ds = _ct_dataset("ACC-X", generate_uid())

    # the spool accepts it (default: accept_when_queued) → success, not 0xA700
    assert _cstore(broker, ds) == 0x0000

    with session_factory()() as s:
        row = s.scalars(select(StoreLog)).one()
        assert row.status == "queued"
        assert row.error
    queued = spool.items(status="queued")
    assert len(queued) == 1
    assert queued[0]["sop_instance_uid"] == str(ds.SOPInstanceUID)
    assert queued[0]["target_name"] == "dead-pacs"


def test_store_forward_failure_without_spool_marks_failed(broker):
    """With the spool disabled the previous policy applies (strict → failure)."""
    settings_service.set_value("spool_enabled", "false")
    _seed_target(1, name="dead-pacs", is_default=True)
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


# ── Transform rules in the C-STORE path ────────────────────────────────


def _seed_transform(name="t1", ops=None, source_id=None, target_id=None,
                    priority=100, enabled=True) -> int:
    with session_factory()() as s:
        row = TransformRule(
            name=name, operations=ops or [], source_id=source_id,
            target_id=target_id, priority=priority, enabled=enabled,
        )
        s.add(row)
        s.commit()
        return row.id


def _route_to(source_id: int, target_id: int) -> None:
    with session_factory()() as s:
        s.add(RoutingRule(source_id=source_id, target_id=target_id))
        s.commit()


def test_store_applies_transform_rules(broker, mwl_scp, store_scp):
    received, store_port = store_scp
    source_id = _seed_source(mwl_scp)
    target_id = _seed_target(store_port)
    _route_to(source_id, target_id)
    _seed_transform(
        "kh-modify",
        [
            {"op": "prefix", "tag": "PatientID", "value": "KH_"},
            {"op": "set", "tag": "InstitutionName", "value": "Klinikum"},
            {"op": "remove", "tag": "PatientBirthDate"},
        ],
        source_id=source_id,
    )

    _cfind(broker, _wildcard_query())
    ds = _ct_dataset(VARIANTS["a"][0].AccessionNumber, VARIANTS["a"][0].StudyInstanceUID)
    ds.PatientID = "P1001"
    ds.PatientBirthDate = "19800101"

    assert _cstore(broker, ds) == 0x0000
    got = received[0]
    assert got.PatientID == "KH_P1001"
    assert got.InstitutionName == "Klinikum"
    assert not hasattr(got, "PatientBirthDate")
    # the UIDs must survive untouched (linkage)
    assert got.StudyInstanceUID == ds.StudyInstanceUID
    with session_factory()() as s:
        assert s.scalars(select(StoreLog)).one().applied_transforms == ["kh-modify"]


def test_transform_scope_excludes_other_targets(broker, mwl_scp, store_scp):
    received, store_port = store_scp
    source_id = _seed_source(mwl_scp)
    target_id = _seed_target(store_port)
    other_target = _seed_target(1, name="other-pacs")
    _route_to(source_id, target_id)
    _seed_transform(
        "only-other-target",
        [{"op": "set", "tag": "InstitutionName", "value": "X"}],
        target_id=other_target,
    )

    _cfind(broker, _wildcard_query())
    ds = _ct_dataset(VARIANTS["a"][0].AccessionNumber, VARIANTS["a"][0].StudyInstanceUID)
    assert _cstore(broker, ds) == 0x0000
    assert not hasattr(received[0], "InstitutionName")
    with session_factory()() as s:
        assert s.scalars(select(StoreLog)).one().applied_transforms == []


def test_broken_transform_op_does_not_lose_instance(broker, mwl_scp, store_scp):
    """A failing operation is logged and skipped — the instance is still
    forwarded and later operations still run."""
    received, store_port = store_scp
    source_id = _seed_source(mwl_scp)
    target_id = _seed_target(store_port)
    _route_to(source_id, target_id)
    _seed_transform(
        "partly-broken",
        [
            # copy from an empty tag → raises inside the op
            {"op": "copy", "tag": "InstitutionName", "from_tag": "RequestedProcedureDescription"},
            {"op": "set", "tag": "InstitutionName", "value": "OK"},
        ],
        source_id=source_id,
    )

    _cfind(broker, _wildcard_query())
    ds = _ct_dataset(VARIANTS["a"][0].AccessionNumber, VARIANTS["a"][0].StudyInstanceUID)
    assert _cstore(broker, ds) == 0x0000
    assert received[0].InstitutionName == "OK"


def test_disabled_transform_not_applied(broker, mwl_scp, store_scp):
    received, store_port = store_scp
    source_id = _seed_source(mwl_scp)
    target_id = _seed_target(store_port)
    _route_to(source_id, target_id)
    _seed_transform(
        "off",
        [{"op": "set", "tag": "InstitutionName", "value": "X"}],
        source_id=source_id, enabled=False,
    )
    _cfind(broker, _wildcard_query())
    ds = _ct_dataset(VARIANTS["a"][0].AccessionNumber, VARIANTS["a"][0].StudyInstanceUID)
    assert _cstore(broker, ds) == 0x0000
    assert not hasattr(received[0], "InstitutionName")


def test_cfind_increments_metrics(broker):
    from prometheus_client import REGISTRY

    labels = {"result": "success"}
    before = REGISTRY.get_sample_value("mwl_cfind_requests_total", labels) or 0
    _cfind(broker, _wildcard_query())
    after = REGISTRY.get_sample_value("mwl_cfind_requests_total", labels)
    assert after == before + 1


# ── Local worklist items ───────────────────────────────────────────────


def _local_item(accession="EMERG-1", **kwargs) -> None:
    from mwl_broker.models import LocalWorklistItem

    values = {
        "accession": accession, "sps_id": "1", "patient_id": "P9001",
        "patient_name": "Notfall^Anna", "modality": "CT", "station_aet": "CT_01",
        "procedure_description": "CT Schädel (Notfall)", "scheduled_date": "2026-09-17",
        "origin": "manual", "enabled": True,
    }
    values.update(kwargs)
    with session_factory()() as s:
        s.add(LocalWorklistItem(**values))
        s.commit()


def test_cfind_includes_local_items(broker, mwl_scp):
    _seed_source(mwl_scp)
    _local_item()

    answers = _cfind(broker, _wildcard_query())

    assert len(answers) == 3                      # two from the RIS + the local one
    local = [ds for ds in answers if str(ds.AccessionNumber) == "EMERG-1"]
    assert len(local) == 1
    assert str(local[0].PatientName) == "Notfall^Anna"
    assert str(local[0].ScheduledProcedureStepSequence[0].Modality) == "CT"

    # the query log shows the pseudo source
    log_row = _last_query_log()
    assert log_row.per_source.get("local") == 1


def test_local_items_respect_the_query_filters(broker, mwl_scp):
    _seed_source(mwl_scp)
    _local_item("EMERG-CT", modality="CT")
    _local_item("EMERG-MR", modality="MR", station_aet="MR_01")

    mr_answers = _cfind(broker, _station_query("MR_01"))

    accessions = {str(ds.AccessionNumber) for ds in mr_answers}
    assert "EMERG-MR" in accessions
    assert "EMERG-CT" not in accessions


def test_local_item_wins_the_dedupe(broker, mwl_scp):
    """The local entry replaces the RIS one for the same accession."""
    _seed_source(mwl_scp)
    accession = VARIANTS["a"][0].AccessionNumber
    # the merge key is patient + accession + SPS ID, so the local entry has to
    # carry the same identity to replace the RIS answer
    _local_item(accession, patient_id=VARIANTS["a"][0].PatientID,
                sps_id=f"SPS-{accession}", procedure_description="Notfall-Override")

    answers = _cfind(broker, _wildcard_query())

    matches = [ds for ds in answers if str(ds.AccessionNumber) == accession]
    assert len(matches) == 1
    assert str(matches[0].RequestedProcedureDescription) == "Notfall-Override"

    # provenance follows the local pseudo source (which routing rules can use)
    with session_factory()() as s:
        row = s.scalars(
            select(SeenItem).where(SeenItem.accession == accession)
            .order_by(SeenItem.ts.desc())
        ).first()
        local_source = s.scalars(select(MwlSource).where(MwlSource.name == "local")).one()
        assert row.source_id == local_source.id


def test_station_rule_can_hide_local_items(broker, mwl_scp):
    from mwl_broker.models import StationRule

    from mwl_broker import local_worklist

    _seed_source(mwl_scp)
    _local_item()
    local_worklist.local_source_id()      # the pseudo source appears with the first item
    with session_factory()() as s:
        local_source = s.scalars(select(MwlSource).where(MwlSource.name == "local")).one()
        s.add(StationRule(name="hide-local", station_aet="CT_01", mode="deny",
                          source_ids=[local_source.id]))
        s.commit()

    accessions = {str(ds.AccessionNumber) for ds in _cfind(broker, _station_query("CT_01"))}

    assert "EMERG-1" not in accessions


def test_mllp_listener_applies_an_order_and_answers():
    """The MLLP listener accepts an ORM message and returns an ACK."""
    import socket as socket_mod
    import threading as threading_mod

    from mwl_broker import mllp

    settings_service.set_value("hl7_mllp_port", "0")   # bind an ephemeral port
    probe = socket_mod.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    settings_service.set_value("hl7_mllp_bind", "127.0.0.1")
    settings_service.set_value("hl7_mllp_port", str(port))

    stop = threading_mod.Event()
    thread = threading_mod.Thread(target=mllp.serve, args=(stop,), daemon=True)
    thread.start()
    try:
        deadline = time.time() + 5
        ack = ""
        while time.time() < deadline:
            try:
                with socket_mod.create_connection(("127.0.0.1", port), timeout=1) as conn:
                    message = (
                        "MSH|^~\\&|RIS||MWLBROKER||20260917103000||ORM^O01|MLLP1|P|2.5\r"
                        "PID|1||P5001||Test^Patient||19900101|F\r"
                        "ORC|NW\r"
                        "OBR|1||ACC-MLLP-1|CT^CT Notfall|R|20260917140000\r"
                    )
                    conn.sendall(b"\x0b" + message.encode() + b"\x1c\x0d")
                    ack = conn.recv(4096).decode("utf-8", "replace")
                break
            except OSError:
                time.sleep(0.1)
    finally:
        stop.set()
        thread.join(timeout=2)

    assert "MSA|AA|MLLP1" in ack
    with session_factory()() as s:
        from mwl_broker.models import Hl7Message, LocalWorklistItem

        assert s.query(LocalWorklistItem).count() == 1
        assert s.query(Hl7Message).one().transport == "mllp"


# ── ATNA audit trail ───────────────────────────────────────────────────


def test_cfind_writes_a_query_audit_message(broker, mwl_scp, monkeypatch):
    from mwl_broker import atna

    messages: list[str] = []
    monkeypatch.setattr(atna, "send", lambda xml: messages.append(xml) or True)
    _seed_source(mwl_scp)

    _cfind(broker, _station_query("CT_01"))

    assert messages, "no audit message was produced"
    assert all('csd-code="110112"' in xml for xml in messages)   # Query
    assert any("ScheduledStationAETitle=CT_01" in xml for xml in messages)
    # every disclosed patient gets its own message (that is the audit trail)
    assert any('ParticipantObjectID="P1001"' in xml for xml in messages)


def test_cstore_writes_import_and_export_audits(broker, mwl_scp, store_scp, monkeypatch):
    from mwl_broker import atna

    messages: list[str] = []
    monkeypatch.setattr(atna, "send", lambda xml: messages.append(xml) or True)
    _seed_source(mwl_scp)
    _cfind(broker, _wildcard_query())
    _seed_target(store_scp[1], name="pacs", is_default=True)

    ds = _ct_dataset(VARIANTS["a"][0].AccessionNumber, VARIANTS["a"][0].StudyInstanceUID)
    assert _cstore(broker, ds) == 0x0000

    codes = {xml.split('EventID csd-code="')[1][:6] for xml in messages}
    assert {"110104", "110106"} <= codes          # Import + Export
    assert any('ParticipantObjectID="ACC-A-001"' in xml for xml in messages)


def test_rejected_calling_aet_writes_a_security_alert(restricted_broker, monkeypatch):
    """A rejected association is a security event — it belongs in the audit trail."""
    from mwl_broker import atna

    messages: list[str] = []
    monkeypatch.setattr(atna, "send", lambda xml: messages.append(xml) or True)

    # the restricted broker does not allow the helper's AE title
    assert _cfind_final_status(restricted_broker, _wildcard_query()) == 0xA700

    assert len(messages) == 1
    assert 'csd-code="110113"' in messages[0]     # Security Alert
    assert 'EventOutcomeIndicator="8"' in messages[0]
    assert 'UserID="TESTSCU"' in messages[0]


def test_auditing_is_off_by_default(broker, mwl_scp):
    """Without configuration nothing is queued (and nothing breaks)."""
    from mwl_broker import atna

    _seed_source(mwl_scp)

    _cfind(broker, _wildcard_query())

    assert atna.configured() is False
    assert atna.stats()["queue_size"] == 0


# ── Per-station rules ──────────────────────────────────────────────────


def _station_query(station: str) -> Dataset:
    q = _wildcard_query()
    q.ScheduledProcedureStepSequence[0].ScheduledStationAETitle = station
    return q


def test_cfind_applies_the_station_filter(broker, mwl_scp):
    """A station rule hides a source for that console only."""
    from mwl_broker.models import StationRule

    source_id = _seed_source(mwl_scp)
    with session_factory()() as s:
        s.add(StationRule(name="ct-hides-ris-a", station_aet="CT_01", mode="deny",
                          source_ids=[source_id]))
        s.commit()

    # the mock items are scheduled for CT_01 → the rule hides the only source
    assert _cfind(broker, _station_query("CT_01")) == []

    # another station is unaffected
    assert len(_cfind(broker, _station_query("MR_01"))) == 2
    # and a query without a station matches no rule at all
    assert len(_cfind(broker, _wildcard_query())) == 2


def test_cfind_station_allow_list(broker, mwl_scp):
    from mwl_broker.models import StationRule

    source_id = _seed_source(mwl_scp)
    with session_factory()() as s:
        s.add(StationRule(name="mr-only", station_aet="MR_01", mode="allow",
                          source_ids=[source_id + 99]))
        s.commit()

    # allow-list without this source → nothing is shown
    assert _cfind(broker, _station_query("MR_01")) == []
    assert len(_cfind(broker, _station_query("CT_01"))) == 2


def test_cfind_station_priority_override_wins_the_dedupe(broker, mwl_scp):
    """Two sources with the same items: the station decides who wins."""
    from mwl_broker.models import StationRule

    first = _seed_source(mwl_scp, name="ris-a", aet="RIS_A")
    second = _seed_source(mwl_scp, name="ris-b", aet="RIS_B")
    with session_factory()() as s:
        s.get(MwlSource, second).priority = 1        # ris-b wins by default
        s.commit()
        s.add(StationRule(name="ct-prefers-a", station_aet="CT_01", mode="deny",
                          source_ids=[], source_priority={str(first): 1}))
        s.commit()

    assert len(_cfind(broker, _wildcard_query())) == 2          # ris-b wins
    assert len(_cfind(broker, _station_query("CT_01"))) == 2    # ris-a wins instead

    # the provenance (seen_items) follows the override
    with session_factory()() as s:
        rows = s.query(SeenItem).order_by(SeenItem.id.desc()).limit(2).all()
        assert {row.source_id for row in rows} == {first}


# ── C-STORE spool (store and forward) ──────────────────────────────────


def test_spooled_instance_is_delivered_once_the_target_recovers(broker, mwl_scp, store_scp):
    """The full store-and-forward round trip: down → queued → up → delivered."""
    from mwl_broker import spool

    received, store_port = store_scp
    _seed_source(mwl_scp)
    _cfind(broker, _wildcard_query())                      # worklist provenance
    target_id = _seed_target(1, name="dead-pacs", is_default=True)  # unreachable

    ds = _ct_dataset("ACC-A-001", generate_uid())
    assert _cstore(broker, ds) == 0x0000, "the modality is told success (queued)"

    queued = spool.items(status="queued")
    assert len(queued) == 1
    assert queued[0]["target_name"] == "dead-pacs"
    with session_factory()() as s:
        assert s.scalars(select(StoreLog)).one().status == "queued"

    # the target comes back (same name/AET, now reachable)
    with session_factory()() as s:
        s.get(PacsTarget, target_id).port = store_port
        s.commit()

    result = spool.run_once()

    assert result["sent"] == 1
    assert spool.stats()["open"] == 0
    assert spool.stats()["sent"] == 1
    # and the instance really arrived
    assert len(received) == 1
    assert str(received[0].SOPInstanceUID) == str(ds.SOPInstanceUID)


def test_spooled_instance_is_not_sent_twice(broker, mwl_scp, store_scp):
    """A duplicate C-STORE must not produce a second delivery."""
    from mwl_broker import spool

    received, store_port = store_scp
    target_id = _seed_target(1, name="dead-pacs", is_default=True)
    ds = _ct_dataset("ACC-A-001", generate_uid())
    assert _cstore(broker, ds) == 0x0000

    with session_factory()() as s:
        s.get(PacsTarget, target_id).port = store_port
        s.commit()
    spool.run_once()
    assert len(received) == 1

    # the modality repeats the store (it never got a "stored" confirmation from
    # the PACS) — the broker answers from the duplicate guard
    assert _cstore(broker, ds) == 0x0000
    assert len(spool.items(status="queued")) == 0
    assert len(received) == 1


def test_spool_disabled_keeps_the_strict_failure(broker, mwl_scp):
    from mwl_broker import spool

    settings_service.set_value("spool_enabled", "false")
    _seed_target(1, name="dead-pacs", is_default=True)

    assert _cstore(broker, _ct_dataset("ACC-A-001", generate_uid())) == 0xA700
    assert spool.items() == []


def test_accept_when_queued_can_be_turned_off(broker, mwl_scp):
    """With accept_when_queued=false the modality is told that it did not arrive."""
    from mwl_broker import spool

    settings_service.set_value("accept_when_queued", "false")
    _seed_target(1, name="dead-pacs", is_default=True)

    assert _cstore(broker, _ct_dataset("ACC-A-001", generate_uid())) == 0xA700
    # ... but the instance is safely spooled anyway
    assert len(spool.items(status="queued")) == 1


# ── Worklist cache (outage bridge) ─────────────────────────────────────


def test_cfind_serves_a_stale_snapshot_when_the_source_dies(broker, mwl_scp):
    """RIS outage: the modality still gets the worklist, marked as stale."""
    from mwl_broker import cache

    settings_service.set_value("cache_stale_max_s", "300")
    source_id = _seed_source(mwl_scp)

    # 1. a live query fills the snapshot
    assert len(_cfind(broker, _wildcard_query())) == 2
    assert len(cache.items()) == 2
    assert _last_query_log().served_stale is None

    # 2. the RIS becomes unreachable → the answer comes from the cache
    with session_factory()() as s:
        s.get(MwlSource, source_id).port = 1
        s.commit()

    answers = _cfind(broker, _wildcard_query())

    assert len(answers) == 2, "the cached worklist must be served"
    log_row = _last_query_log()
    assert log_row.served_stale == ["ris-a"]
    assert log_row.status == "partial", "serving stale is degraded, not success"
    assert log_row.per_source["ris-a"] == 2


def test_cfind_serves_the_snapshot_while_the_breaker_is_open(broker, mwl_scp):
    """A source that is known to be down is skipped — but still served from cache."""
    from mwl_broker import breaker, cache

    settings_service.set_value("cache_stale_max_s", "300")
    settings_service.set_value("breaker_fail_threshold", "1")
    source_id = _seed_source(mwl_scp)
    _cfind(broker, _wildcard_query())          # fills the cache
    breaker.record_failure(source_id, "down")  # and now the breaker is open

    answers = _cfind(broker, _wildcard_query())

    assert len(answers) == 2
    log_row = _last_query_log()
    assert log_row.served_stale == ["ris-a"]
    assert log_row.per_source["ris-a"] == 2
    assert log_row.status == "partial"
    assert cache.items(), "the snapshot stays for the next query"


def test_cfind_returns_nothing_when_the_snapshot_is_expired(broker, mwl_scp):
    from datetime import datetime, timedelta, timezone

    from mwl_broker import cache
    from mwl_broker.models import WorklistCache

    settings_service.set_value("cache_stale_max_s", "60")
    source_id = _seed_source(mwl_scp)
    _cfind(broker, _wildcard_query())
    with session_factory()() as s:
        for row in s.query(WorklistCache).filter_by(source_id=source_id):
            row.fetched_at = datetime.now(timezone.utc) - timedelta(seconds=600)
        s.commit()
        s.get(MwlSource, source_id).port = 1
        s.commit()

    answers = _cfind(broker, _wildcard_query())

    assert answers == []
    log_row = _last_query_log()
    assert log_row.per_source["ris-a"] == "error"
    assert log_row.status == "failed"
    assert log_row.served_stale is None
    assert cache.items(), "the expired rows are still there until the purge"


def test_cfind_drops_finished_steps_from_the_snapshot(broker, mwl_scp):
    """A step completed in the RIS must not come back from the cache."""
    from mwl_broker import cache
    from mwl_broker.models import WorklistCache

    settings_service.set_value("cache_stale_max_s", "300")
    source_id = _seed_source(mwl_scp)
    _cfind(broker, _wildcard_query())
    with session_factory()() as s:
        rows = s.query(WorklistCache).filter_by(source_id=source_id).all()
        rows[0].sps_status = "COMPLETED"
        completed_accession = rows[0].accession
        s.get(MwlSource, source_id).port = 1
        s.commit()

    answers = _cfind(broker, _wildcard_query())

    assert len(answers) == 1
    assert str(answers[0].AccessionNumber) != completed_accession
    assert _last_query_log().served_stale == ["ris-a"]


# ── Circuit breaker in the C-FIND fan-out ──────────────────────────────


@pytest.fixture()
def hanging_port():
    """A TCP port that accepts connections but never answers DIMSE.

    Simulates the expensive failure mode: a source that is reachable but
    dead, so every query costs the full timeout.
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(16)
    srv.settimeout(0.2)
    conns: list[socket.socket] = []
    stop = threading.Event()

    def accept_loop():
        while not stop.is_set():
            try:
                conn, _ = srv.accept()
                conns.append(conn)  # hold it open, send nothing
            except socket.timeout:
                continue
            except OSError:
                break

    thread = threading.Thread(target=accept_loop, daemon=True)
    thread.start()
    try:
        yield srv.getsockname()[1]
    finally:
        stop.set()
        thread.join(timeout=2)
        for conn in conns:
            conn.close()
        srv.close()


def _last_query_log():
    with session_factory()() as s:
        return s.scalars(select(QueryLog).order_by(QueryLog.ts.desc())).all()[0]


def test_breaker_skips_hanging_source_and_keeps_queries_fast(broker, mwl_scp, hanging_port):
    settings_service.set_value("breaker_fail_threshold", "2")
    settings_service.set_value("breaker_open_seconds", "60")
    _seed_source(mwl_scp)
    _seed_source(hanging_port, name="hanging", aet="HANG", timeout_s=1)

    # two failing queries open the breaker (each pays the 1 s timeout)
    for _ in range(2):
        assert len(_cfind(broker, _wildcard_query())) == 2
        assert _last_query_log().per_source["hanging"] == "error"
    assert _last_query_log().status == "partial"

    # the next query skips the source entirely — and is fast
    started = time.monotonic()
    answers = _cfind(broker, _wildcard_query())
    elapsed = time.monotonic() - started
    # The property under test is that the skipped source is not waited for; the
    # bound is deliberately generous because a loaded CI machine is slow. Paying
    # the 1 s timeout again would take at least twice as long as the limit.

    assert len(answers) == 2, "the live source must still answer"
    # The proof that the source was *skipped* is deterministic and lives in the
    # query log below ("breaker_open" instead of "error"). A wall-clock bound was
    # flaky on loaded CI machines (the suite needs 20 minutes there), so it is only
    # a coarse smoke bound: paying the 1 s timeout would already be far above it.
    assert elapsed < 5.0, f"the query took {elapsed:.2f}s — did the breaker run?"
    log_row = _last_query_log()
    assert log_row.per_source["hanging"] == "breaker_open"
    assert log_row.per_source["ris-a"] == 2
    assert log_row.status == "partial"


def test_breaker_reopens_only_after_the_cooldown(broker, mwl_scp, hanging_port):
    settings_service.set_value("breaker_fail_threshold", "1")
    settings_service.set_value("breaker_open_seconds", "3600")
    _seed_source(mwl_scp)
    _seed_source(hanging_port, name="hanging", aet="HANG", timeout_s=1)

    _cfind(broker, _wildcard_query())  # trips the breaker
    assert _last_query_log().per_source["hanging"] == "error"

    _cfind(broker, _wildcard_query())
    assert _last_query_log().per_source["hanging"] == "breaker_open"

    # an operator reset puts the source back into the fan-out immediately
    from mwl_broker import breaker

    with session_factory()() as s:
        source_id = s.scalars(select(MwlSource).where(MwlSource.name == "hanging")).one().id
    breaker.reset(source_id)

    _cfind(broker, _wildcard_query())
    assert _last_query_log().per_source["hanging"] == "error"


def test_c_find_runs_the_shared_aggregation(broker, monkeypatch):
    """The live C-FIND must go through `aggregation.collect` — the same function
    the operator's preview calls.

    A second, inline implementation of the fan-out once shadowed it (two methods
    with the same name; Python keeps the last one). Preview and modality then
    disagreed, and the inline copy was missing the guard that keeps a failing
    cache write from counting as a source failure: a foreign RIS answer with two
    identical dedupe keys opened the breaker and took that source out of the
    worklist. Found with the DVTk RIS emulator.
    """
    from mwl_broker import aggregation

    with session_factory()() as s:
        row = MwlSource(name="dvtk-ris", aet="DVTK_MWL_SCP", host="127.0.0.1", port=1,
                        calling_aet="MWLBROKER", charset="ISO_IR 100", enabled=True)
        s.add(row)
        s.commit()
        source_id = row.id
    src = aggregation.source_config(source_id)
    assert src is not None

    sentinel = Dataset()
    sentinel.PatientID = "SENTINEL"
    sps = Dataset()
    sps.ScheduledProcedureStepID = "SPS-SENTINEL"
    sentinel.ScheduledProcedureStepSequence = [sps]

    result = aggregation.AggregationResult()
    result.items = [sentinel]
    result.merged = [(sentinel, src)]
    result.per_source = {src.name: 1}

    calls: list[Dataset] = []

    def fake_collect(identifier, **kwargs):
        calls.append(identifier)
        return result

    monkeypatch.setattr(aggregation, "collect", fake_collect)

    answers = _cfind(broker, _wildcard_query())

    assert calls, "the live C-FIND did not use aggregation.collect"
    assert [answer.get("PatientID") for answer in answers] == ["SENTINEL"]
