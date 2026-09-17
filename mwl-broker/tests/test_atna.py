"""IHE ATNA audit trail: message building, syslog framing, delivery, buffering."""
import socket
import threading
import time

import pytest

from mwl_broker import atna, settings_service


class _Receiver:
    """Minimal syslog/TLS receiver that records every frame it gets."""

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.sock.settimeout(0.2)
        self.frames: list[bytes] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._accept, daemon=True)
        self._thread.start()

    @property
    def port(self) -> int:
        return self.sock.getsockname()[1]

    def _accept(self):
        while not self._stop.is_set():
            try:
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with conn:
                conn.settimeout(1.0)
                try:
                    self.frames.append(conn.recv(65536))
                except socket.timeout:
                    pass

    def close(self):
        self._stop.set()
        self._thread.join(timeout=2)
        self.sock.close()


@pytest.fixture()
def receiver():
    srv = _Receiver()
    try:
        yield srv
    finally:
        srv.close()


def _configure(receiver=None, protocol="tcp", enabled=True, port=None):
    settings_service.set_value("atna_enabled", "true" if enabled else "false")
    settings_service.set_value("atna_syslog_host", "127.0.0.1" if receiver else "")
    settings_service.set_value("atna_syslog_port", str(port or (receiver.port if receiver else 6514)))
    settings_service.set_value("atna_syslog_protocol", protocol)
    atna.reset_for_tests()   # the config cache has a short TTL


def _wait_for(predicate, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


# ── message building ───────────────────────────────────────────────────


def test_build_produces_a_ps315_audit_message():
    xml = atna.build(
        atna.EVENT_QUERY, broker_aet="MWLBROKER", source_aet="CT_01", source_ip="10.0.2.10",
        patient_id="P1001", study_uid="1.2.3", accession="ACC-A-001", query="(0008,0060)=CT",
        event_type=("ITI-20", "Modality Worklist Query"),
    )

    assert xml.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert "<AuditMessage" in xml and xml.endswith("</AuditMessage>")
    # event identification
    assert 'EventActionCode="E"' in xml
    assert 'EventOutcomeIndicator="0"' in xml
    assert 'csd-code="110112"' in xml and "Query" in xml
    assert 'csd-code="ITI-20"' in xml
    # participants: the modality (requestor) and the broker (destination)
    assert 'UserID="CT_01"' in xml and 'UserIsRequestor="true"' in xml
    assert 'NetworkAccessPointID="10.0.2.10"' in xml
    assert 'UserID="MWLBROKER"' in xml and 'UserIsRequestor="false"' in xml
    assert 'csd-code="110153"' in xml and 'csd-code="110152"' in xml
    assert "<AuditSourceIdentification" in xml
    # objects: patient, study, accession, query
    assert 'ParticipantObjectID="P1001"' in xml
    assert 'ParticipantObjectID="1.2.3"' in xml and 'csd-code="110180"' in xml
    assert 'ParticipantObjectID="ACC-A-001"' in xml and 'csd-code="110181"' in xml
    assert "(0008,0060)=CT" in xml


def test_build_escapes_values():
    xml = atna.build(atna.EVENT_QUERY, broker_aet="MWLBROKER",
                     patient_id='P1"&<script>')
    assert "<script>" not in xml
    assert "&lt;script&gt;" in xml


def test_build_without_objects_stays_valid():
    xml = atna.build(atna.EVENT_SECURITY, outcome="8", broker_aet="MWLBROKER",
                     source_aet="UNKNOWN")
    assert "<EventIdentification" in xml
    assert "ParticipantObjectIdentification" not in xml


def test_event_codes_match_the_dicom_catalogue():
    assert atna.EVENT_QUERY[0] == "110112"
    assert atna.EVENT_IMPORT[0] == "110104"
    assert atna.EVENT_EXPORT[0] == "110106"
    assert atna.EVENT_SECURITY[0] == "110113"


def test_sample_message_is_a_query():
    xml = atna.sample_message()
    assert 'csd-code="110112"' in xml
    assert "ACC-A-001" in xml and "P1001" in xml


# ── syslog framing ─────────────────────────────────────────────────────


def test_syslog_frame_is_rfc5424_with_bom():
    frame = atna.syslog_message("<AuditMessage/>")

    assert frame.startswith(b"<86>1 ")           # facility 10 (security), severity 6
    assert b"\xef\xbb\xbf" in frame              # DICOM requires the UTF-8 BOM
    assert b"mwl-broker" in frame
    assert frame.endswith(b"<AuditMessage/>")


# ── delivery ───────────────────────────────────────────────────────────


def test_audit_message_reaches_the_repository(receiver):
    _configure(receiver)
    atna.start()

    assert atna.audit(atna.EVENT_QUERY, broker_aet="MWLBROKER", source_aet="CT_01",
                      patient_id="P1001") is True

    assert _wait_for(lambda: len(receiver.frames) == 1)
    frame = receiver.frames[0]
    assert b"<86>1 " in frame and b'csd-code="110112"' in frame and b"P1001" in frame
    atna.stop()


def test_send_is_a_noop_when_not_configured():
    _configure(None, enabled=False)
    assert atna.configured() is False
    assert atna.audit(atna.EVENT_QUERY, broker_aet="MWLBROKER") is False


def test_delivery_failure_is_tolerated(receiver):
    _configure(receiver, port=1)     # nothing listens there
    ok, error = atna.deliver(atna.syslog_message("<AuditMessage/>"))
    assert ok is False and error


def test_queue_is_bounded_and_drops_instead_of_blocking(receiver, monkeypatch):
    from prometheus_client import REGISTRY

    _configure(receiver)
    settings_service.set_value("atna_queue_max", "100")
    monkeypatch.setattr(atna, "_connect", lambda *a, **k: (_ for _ in ()).throw(
        ConnectionError("down")))
    # a worker that never drains: fill the queue by hand
    dropped_before = REGISTRY.get_sample_value("mwl_atna_dropped_total") or 0
    for _ in range(20000):
        if not atna.send("<AuditMessage/>"):
            break
    dropped_after = REGISTRY.get_sample_value("mwl_atna_dropped_total") or 0
    assert dropped_after > dropped_before, "the bounded queue never dropped anything"


def test_tls_uses_the_configured_ca(monkeypatch):
    """The TLS branch must verify the repository against the configured CA."""
    _configure(None, protocol="tls", port=6514)
    settings_service.set_value("atna_syslog_host", "audit.example")
    settings_service.set_value("atna_tls_ca_file", "/etc/ssl/certs/ca.pem")
    atna.reset_for_tests()
    captured: dict = {}

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def sendall(self, data):
            captured["sent"] = data

    class FakeContext:
        def wrap_socket(self, sock, **kwargs):
            captured["server_hostname"] = kwargs.get("server_hostname")
            return sock

    def fake_context(*, cafile=None):
        captured["cafile"] = cafile
        return FakeContext()

    monkeypatch.setattr(atna.ssl, "create_default_context", fake_context)
    monkeypatch.setattr(atna.socket, "create_connection", lambda *a, **k: FakeSocket())

    ok, error = atna.deliver(b"frame")

    assert ok is True and error == ""
    assert captured["cafile"] == "/etc/ssl/certs/ca.pem"
    assert captured["server_hostname"] == "audit.example"
    assert captured["sent"] == b"frame"


def test_send_test_reports_the_result(receiver):
    _configure(receiver)

    result = atna.send_test()

    assert result["ok"] is True
    assert _wait_for(lambda: len(receiver.frames) == 1)
    assert b'csd-code="110113"' in receiver.frames[0]   # Security Alert


def test_send_test_without_configuration():
    _configure(None, enabled=False)
    result = atna.send_test()
    assert result["ok"] is False and "not configured" in result["error"]


def test_stats_report_the_configuration(receiver):
    _configure(receiver)
    data = atna.stats()

    assert data["enabled"] is True and data["configured"] is True
    assert data["host"] == "127.0.0.1" and data["port"] == receiver.port
    assert data["protocol"] == "tcp" and data["queue_max"] >= 100
    assert data["queue_size"] == 0
