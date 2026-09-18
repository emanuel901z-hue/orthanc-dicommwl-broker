"""Real DICOM associations over TLS — inbound, outbound, mTLS and C-STORE."""
import shutil
from pathlib import Path

import pytest
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, generate_uid
from pynetdicom import AE, evt
from pynetdicom.sop_class import ModalityWorklistInformationFind, Verification
from sqlalchemy import select

from mwl_broker import settings_service, tls
from mwl_broker.db import session_factory
from mwl_broker.dimse import BrokerSCP
from mwl_broker.models import MwlSource, PacsTarget
from mwl_broker.upstream import SourceCfg, c_echo, query_source

TLS_DIR = Path(__file__).resolve().parent.parent / ".pytest-tls"


def _port(server) -> int:
    return server.server_address[1]


def _client_ae(aet: str) -> AE:
    """A client AE with short timeouts — a refused TLS handshake must fail fast."""
    ae = AE(ae_title=aet)
    ae.acse_timeout = 5
    ae.network_timeout = 5
    ae.dimse_timeout = 5
    return ae


@pytest.fixture(autouse=True)
def tls_workspace():
    shutil.rmtree(TLS_DIR, ignore_errors=True)
    TLS_DIR.mkdir(parents=True, exist_ok=True)
    settings_service.set_value("tls_dir", str(TLS_DIR))
    tls.reset_for_tests()
    yield
    tls.reset_for_tests()
    shutil.rmtree(TLS_DIR, ignore_errors=True)


@pytest.fixture()
def certs():
    """A server and a client certificate (client signed by its own CA)."""
    server = tls.generate_self_signed("127.0.0.1", 365, ["127.0.0.1"], filename="server")
    client = tls.generate_self_signed("mwl-broker", 365, ["127.0.0.1"], filename="client")
    return server, client


def _server_context(cert_path: str, key_path: str, client_ca: str = "",
                    require_client: bool = False):
    import ssl

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)
    if require_client:
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(cafile=client_ca or cert_path)
    return context


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


def _ct_dataset(accession: str = "ACC-TLS-1") -> FileDataset:
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = CTImageStorage
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset("tls.dcm", {}, file_meta=meta, preamble=b"\0" * 128)
    ds.SOPClassUID = CTImageStorage
    ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    ds.AccessionNumber = accession
    ds.StudyInstanceUID = generate_uid()
    ds.PatientID = "P-TLS"
    ds.PatientName = "Tls^Test"
    ds.Modality = "CT"
    return ds


def _tls_worklist_scp(cert_path: str, key_path: str):
    """A minimal TLS worklist SCP returning one item."""
    def handle_find(event):
        ds = Dataset()
        ds.SpecificCharacterSet = "ISO_IR 100"
        ds.PatientID = "P-TLS"
        ds.PatientName = "Tls^Upstream"
        ds.AccessionNumber = "ACC-TLS-UP"
        ds.StudyInstanceUID = generate_uid()
        sps = Dataset()
        sps.ScheduledProcedureStepID = "SPS-TLS"
        sps.ScheduledStationAETitle = "CT_01"
        sps.Modality = "CT"
        sps.ScheduledProcedureStepStatus = "SCHEDULED"
        ds.ScheduledProcedureStepSequence = [sps]
        yield 0xFF00, ds
        yield 0x0000, None

    ae = AE(ae_title="RIS_TLS")
    ae.acse_timeout = 5
    ae.network_timeout = 5
    ae.dimse_timeout = 5
    ae.add_supported_context(ModalityWorklistInformationFind)
    ae.add_supported_context(Verification)
    server = ae.start_server(
        ("127.0.0.1", 0), block=False,
        evt_handlers=[(evt.EVT_C_FIND, handle_find)],
        ssl_context=_server_context(cert_path, key_path),
    )
    return ae, server


def _tls_store_scp(cert_path: str, key_path: str):
    """A minimal TLS storage SCP collecting what it receives."""
    received: list = []

    def handle_store(event):
        ds = event.dataset
        ds.file_meta = event.file_meta
        received.append(ds)
        return 0x0000

    ae = AE(ae_title="PACS_TLS")
    ae.acse_timeout = 5
    ae.network_timeout = 5
    ae.dimse_timeout = 5
    ae.add_supported_context(CTImageStorage)
    ae.add_supported_context(Verification)
    server = ae.start_server(
        ("127.0.0.1", 0), block=False,
        evt_handlers=[(evt.EVT_C_STORE, handle_store)],
        ssl_context=_server_context(cert_path, key_path),
    )
    return received, ae, server


# ── inbound: modalities connect to the broker over TLS ─────────────────


def test_cfind_over_tls_to_the_broker(certs):
    """The TLS listener answers a C-FIND; the plain port stays untouched."""
    server_cert, _client_cert = certs
    settings_service.set_value("tls_inbound_enabled", "true")
    settings_service.set_value("tls_inbound_cert_file", server_cert["certificate_path"])
    settings_service.set_value("tls_inbound_key_file", server_cert["key_path"])
    settings_service.set_value("tls_inbound_port", "0")
    tls.reset_for_tests()

    from mwl_broker.config import Settings

    settings = Settings(dicom_port=0)
    scp = BrokerSCP(settings)
    scp.start()
    try:
        assert scp.listening is True
        tls_port = _port(scp.tls_server)

        # the broker offers one item so the association has something to return
        with session_factory()() as s:
            from mwl_broker.models import LocalWorklistItem

            s.add(LocalWorklistItem(accession="ACC-TLS-1", sps_id="1", patient_id="P-TLS",
                                    patient_name="Tls^Test", modality="CT",
                                    station_aet="CT_01", enabled=True))
            s.commit()

        context = tls.build_client_context(verify=True,
                                          ca_file=server_cert["certificate_path"])
        ae = _client_ae("TLSSCU")
        ae.add_requested_context(ModalityWorklistInformationFind)
        assoc = ae.associate("127.0.0.1", tls_port, ae_title=settings.broker_aet,
                             tls_args=(context, "127.0.0.1"))
        assert assoc.is_established, "the TLS association was not established"
        try:
            answers = [ds for status, ds in assoc.send_c_find(
                _wildcard_query(), ModalityWorklistInformationFind) if status.Status == 0xFF00]
        finally:
            assoc.release()

        assert len(answers) == 1
        assert str(answers[0].AccessionNumber) == "ACC-TLS-1"
    finally:
        scp.shutdown()


def test_tls_listener_is_absent_by_default(certs):
    from mwl_broker.config import Settings

    settings_service.set_value("tls_inbound_enabled", "false")
    tls.reset_for_tests()
    scp = BrokerSCP(Settings(dicom_port=0))
    scp.start()
    try:
        assert scp.listening is True
        assert scp.tls_listening is False
    finally:
        scp.shutdown()


def test_mtls_requires_a_client_certificate(certs):
    """With client authentication 'required' only certified modalities get in."""
    server_cert, client_cert = certs
    settings_service.set_value("tls_inbound_enabled", "true")
    settings_service.set_value("tls_inbound_cert_file", server_cert["certificate_path"])
    settings_service.set_value("tls_inbound_key_file", server_cert["key_path"])
    settings_service.set_value("tls_inbound_port", "0")
    settings_service.set_value("tls_inbound_client_auth", "required")
    settings_service.set_value("tls_inbound_ca_file", client_cert["certificate_path"])
    tls.reset_for_tests()

    from mwl_broker.config import Settings

    scp = BrokerSCP(Settings(dicom_port=0))
    scp.start()
    try:
        tls_port = _port(scp.tls_server)

        def _attempt(client_cert_path: str, key_path: str) -> bool:
            context = tls.build_client_context(verify=True,
                                              ca_file=server_cert["certificate_path"])
            if client_cert_path:
                context.load_cert_chain(client_cert_path, key_path)
            ae = _client_ae("MTLSCU")
            ae.add_requested_context(Verification)
            assoc = ae.associate("127.0.0.1", tls_port, ae_title=Settings().broker_aet,
                                 tls_args=(context, "127.0.0.1"))
            established = assoc.is_established
            if established:
                assoc.release()
            return established

        # without a certificate the association is refused
        assert _attempt("", "") is False
        # with the certificate the broker trusts, it works
        assert _attempt(client_cert["certificate_path"], client_cert["key_path"]) is True
    finally:
        scp.shutdown()


# ── outbound: the broker queries/forwards over TLS ─────────────────────


def test_upstream_query_over_tls(certs):
    server_cert, _client = certs
    ae, server = _tls_worklist_scp(server_cert["certificate_path"], server_cert["key_path"])
    settings_service.set_value("tls_outbound_ca_file", server_cert["certificate_path"])
    tls.reset_for_tests()
    try:
        source = SourceCfg(id=1, name="ris-tls", aet="RIS_TLS", host="127.0.0.1",
                           port=_port(server), calling_aet="MWLBROKER",
                           charset="ISO_IR 100", timeout_s=10, tls=True, tls_verify=True)
        answers = query_source(source, _wildcard_query())
    finally:
        server.shutdown()

    assert len(answers) == 1
    assert str(answers[0].AccessionNumber) == "ACC-TLS-UP"


def test_upstream_query_fails_without_the_ca(certs):
    """A self-signed upstream is rejected unless its certificate is trusted."""
    server_cert, _client = certs
    ae, server = _tls_worklist_scp(server_cert["certificate_path"], server_cert["key_path"])
    settings_service.set_value("tls_outbound_ca_file", "")
    tls.reset_for_tests()
    try:
        source = SourceCfg(id=1, name="ris-tls", aet="RIS_TLS", host="127.0.0.1",
                           port=_port(server), calling_aet="MWLBROKER",
                           charset="ISO_IR 100", timeout_s=5, tls=True, tls_verify=True)
        with pytest.raises(Exception):
            query_source(source, _wildcard_query())
    finally:
        server.shutdown()


def test_c_echo_over_tls(certs):
    server_cert, _client = certs
    ae, server = _tls_worklist_scp(server_cert["certificate_path"], server_cert["key_path"])
    settings_service.set_value("tls_outbound_ca_file", server_cert["certificate_path"])
    tls.reset_for_tests()
    try:
        # no exception = the echo succeeded
        c_echo("RIS_TLS", "127.0.0.1", _port(server), "MWLBROKER", timeout_s=10,
               tls=True, tls_verify=True)
    finally:
        server.shutdown()


def test_cstore_over_tls(certs):
    """Forwarding uses the target's TLS settings (cstore.send_store)."""
    from mwl_broker import cstore

    server_cert, _client = certs
    received, ae, server = _tls_store_scp(server_cert["certificate_path"],
                                          server_cert["key_path"])
    settings_service.set_value("tls_outbound_ca_file", server_cert["certificate_path"])
    tls.reset_for_tests()
    try:
        target = cstore.resolve_target.__globals__["routing"].TargetCfg(
            id=1, name="pacs-tls", aet="PACS_TLS", host="127.0.0.1", port=_port(server),
            calling_aet="MWLBROKER", enabled=True, is_default=True, tls=True, tls_verify=True,
        )
        cstore.send_store(_ct_dataset(), target)
    finally:
        server.shutdown()

    assert len(received) == 1
    assert str(received[0].AccessionNumber) == "ACC-TLS-1"


def test_target_tls_flags_reach_the_config(certs):
    """The per-node flags are carried from the database into the config objects."""
    from mwl_broker import routing

    with session_factory()() as s:
        target = PacsTarget(name="pacs-tls", aet="PACS_TLS", host="127.0.0.1", port=2762,
                            calling_aet="MWLBROKER", is_default=True, tls=True, tls_verify=False)
        source = MwlSource(name="ris-tls", aet="RIS_TLS", host="127.0.0.1", port=2762,
                           calling_aet="MWLBROKER", charset="ISO_IR 100",
                           tls=True, tls_verify=False)
        s.add(target)
        s.add(source)
        s.commit()

        cfg = routing._target_cfg(s.get(PacsTarget, target.id))
        assert cfg.tls is True and cfg.tls_verify is False

        from mwl_broker.cache import sources_due_for_refresh

        # `sources_due_for_refresh` builds the same SourceCfg objects the
        # fan-out uses, so it proves the flags travel from the database.
        s.get(MwlSource, source.id).cache_refresh_s = 60
        s.commit()
        cfg = next(c for c in sources_due_for_refresh() if c.name == "ris-tls")
        assert cfg.tls is True and cfg.tls_verify is False
