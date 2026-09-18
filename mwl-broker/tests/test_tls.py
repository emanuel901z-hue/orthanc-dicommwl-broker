"""DICOM TLS: contexts, certificate management, endpoint check, real handshake."""
import socket
import ssl
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from mwl_broker import settings_service, tls

TLS_DIR = Path(__file__).resolve().parent.parent / ".pytest-tls"


@pytest.fixture(autouse=True)
def tls_dir():
    import shutil

    shutil.rmtree(TLS_DIR, ignore_errors=True)
    TLS_DIR.mkdir(parents=True, exist_ok=True)
    settings_service.set_value("tls_dir", str(TLS_DIR))
    tls.reset_for_tests()
    yield
    tls.reset_for_tests()
    shutil.rmtree(TLS_DIR, ignore_errors=True)


def _configure(**values):
    for key, value in values.items():
        settings_service.set_value(key, str(value).lower() if isinstance(value, bool) else str(value))
    tls.reset_for_tests()


def _generate(days: int = 365, common_name: str = "broker.local",
              san: list[str] | None = None, is_ca: bool = False,
              filename: str = "mwl-broker") -> dict:
    settings_service.set_value("tls_dir", str(TLS_DIR))
    tls.reset_for_tests()
    return tls.generate_self_signed(common_name, days, san, is_ca, filename)


# ── certificate generation ─────────────────────────────────────────────


def test_generate_self_signed_writes_cert_and_key():
    result = _generate(365, "mwl-broker.hospital.local",
                       ["10.0.1.47", "mwl-broker.hospital.local"])

    cert_path, key_path = Path(result["certificate_path"]), Path(result["key_path"])
    assert cert_path.is_file() and key_path.is_file()
    # the private key is never world readable
    assert key_path.stat().st_mode & 0o777 == 0o600
    assert "BEGIN CERTIFICATE" in result["certificate_pem"]

    cert = result["certificate"]
    assert cert["ok"] is True
    assert cert["subject"].startswith("mwl-broker.hospital.local")
    assert cert["self_signed"] is True
    assert cert["is_ca"] is False
    assert "10.0.1.47" in cert["san"] and "mwl-broker.hospital.local" in cert["san"]
    assert 300 < cert["days_left"] <= 365

    assert result["key"]["ok"] is True and result["key"]["world_readable"] is False


def test_generate_as_ca():
    result = _generate(3650, "hospital-ca", is_ca=True)
    assert result["certificate"]["is_ca"] is True


def test_generate_requires_a_common_name():
    with pytest.raises(ValueError):
        _generate(365, "   ")


def test_san_defaults_to_the_common_name():
    cert = _generate(30, "broker.local")["certificate"]
    assert cert["san"] == ["broker.local"]


# ── inspection ─────────────────────────────────────────────────────────


def test_inspect_reports_missing_and_broken_files():
    assert tls.inspect_certificate("")["error"] == "not configured"
    missing = tls.inspect_certificate(str(TLS_DIR / "nope.crt"))
    assert missing["exists"] is False and missing["error"] == "file not found"

    broken = TLS_DIR / "broken.crt"
    broken.write_text("this is not a certificate")
    assert "not a readable certificate" in tls.inspect_certificate(str(broken))["error"]


def test_inspect_detects_an_expired_certificate():
    result = _generate(1, "old.local")
    # backdate the certificate by re-signing is overkill — use a negative window
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "expired.local")])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(subject).issuer_name(subject).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=400))
            .not_valid_after(now - timedelta(days=10))
            .sign(key, hashes.SHA256()))
    path = TLS_DIR / "expired.crt"
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    inspected = tls.inspect_certificate(str(path))
    assert inspected["expired"] is True and inspected["days_left"] < 0
    assert result["certificate"]["expired"] is False


def test_inspect_detects_a_world_readable_key():
    result = _generate(30, "broker.local")
    Path(result["key_path"]).chmod(0o644)
    assert tls.inspect_private_key(result["key_path"])["world_readable"] is True


def test_key_matches_certificate():
    result = _generate(30, "broker.local")
    assert tls.key_matches_certificate(result["certificate_path"], result["key_path"]) is True

    other = _generate(30, "other.local", filename="other")
    assert tls.key_matches_certificate(result["certificate_path"], other["key_path"]) is False
    assert tls.key_matches_certificate("/nope.crt", "/nope.key") is None


def test_overview_reports_everything_configured():
    result = _generate(20, "broker.local")   # expires within the warning window
    _configure(tls_inbound_enabled=True, tls_inbound_cert_file=result["certificate_path"],
               tls_inbound_key_file=result["key_path"], tls_inbound_port=2762,
               tls_outbound_verify=False)

    overview = tls.overview()

    assert overview["inbound_enabled"] is True and overview["inbound_port"] == 2762
    assert overview["entries"]["inbound_cert"]["ok"] is True
    assert overview["entries"]["inbound_cert"]["expiring_soon"] is True
    assert overview["entries"]["inbound_pair_matches"]["ok"] is True
    assert overview["outbound_verify"] is False
    assert [entry["role"] for entry in overview["certificates"]] == ["inbound_cert"]
    # the private key never appears in the certificate list
    assert all("BEGIN" not in str(entry) for entry in overview["certificates"])


def test_expiring_certificates_lists_only_pending_ones():
    fresh = _generate(3650, "fresh.local", filename="fresh")
    soon = _generate(5, "soon.local", filename="soon")
    _configure(tls_outbound_ca_file=soon["certificate_path"])
    _configure(tls_inbound_cert_file=fresh["certificate_path"])

    expiring = tls.expiring_certificates()

    assert len(expiring) == 1
    assert expiring[0]["path"] == soon["certificate_path"]


# ── contexts ───────────────────────────────────────────────────────────


def test_server_context_needs_cert_and_key():
    _configure(tls_inbound_enabled=True)
    with pytest.raises(ValueError, match="certificate and a private key"):
        tls.build_server_context()


def test_server_context_with_client_auth():
    result = _generate(365, "broker.local", is_ca=True)
    _configure(tls_inbound_enabled=True, tls_inbound_cert_file=result["certificate_path"],
               tls_inbound_key_file=result["key_path"],
               tls_inbound_client_auth="required")

    # mTLS without a CA file is a configuration error, not a silent accept-all
    with pytest.raises(ValueError, match="CA file"):
        tls.build_server_context()

    _configure(tls_inbound_ca_file=result["certificate_path"])
    context = tls.build_server_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.minimum_version == ssl.TLSVersion.TLSv1_2


def test_server_context_defaults_to_no_client_auth():
    result = _generate(365, "broker.local")
    _configure(tls_inbound_enabled=True, tls_inbound_cert_file=result["certificate_path"],
               tls_inbound_key_file=result["key_path"])

    context = tls.build_server_context()
    assert context.verify_mode == ssl.CERT_NONE


def test_server_context_is_none_when_disabled():
    _configure(tls_inbound_enabled=False)
    assert tls.build_server_context() is None


def test_client_context_verify_off_is_explicit():
    _configure(tls_outbound_verify=False)
    context = tls.build_client_context()
    assert context.verify_mode == ssl.CERT_NONE
    assert context.check_hostname is False


def test_client_context_loads_the_client_certificate():
    result = _generate(365, "broker.local")
    _configure(tls_outbound_client_cert_file=result["certificate_path"],
               tls_outbound_client_key_file=result["key_path"])

    context = tls.build_client_context()

    assert context.get_ca_certs() is not None      # default store loaded
    assert tls.client_tls_args() is not None
    _configure(tls_outbound_client_cert_file="", tls_outbound_client_key_file="")


def test_client_tls_args_is_none_only_when_not_used():
    args = tls.client_tls_args(verify=False)
    assert isinstance(args, tuple) and isinstance(args[0], ssl.SSLContext)


# ── endpoint check (a real handshake) ──────────────────────────────────


class _TlsServer:
    """A real TLS server that presents a generated certificate."""

    def __init__(self, cert_path: str, key_path: str, require_client_cert: bool = False,
                 ca_path: str = ""):
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.load_cert_chain(cert_path, key_path)
        if require_client_cert:
            self.context.verify_mode = ssl.CERT_REQUIRED
            self.context.load_verify_locations(cafile=ca_path or cert_path)
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(4)
        self.sock.settimeout(0.3)
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    @property
    def port(self) -> int:
        return self.sock.getsockname()[1]

    def _serve(self):
        while not self._stop.is_set():
            try:
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                with self.context.wrap_socket(conn, server_side=True) as tls_conn:
                    tls_conn.recv(1024)
            except Exception:
                pass

    def close(self):
        self._stop.set()
        self.thread.join(timeout=2)
        self.sock.close()


def test_endpoint_check_reports_the_peer_certificate():
    generated = _generate(365, "127.0.0.1", ["127.0.0.1"])
    server = _TlsServer(generated["certificate_path"], generated["key_path"])
    try:
        result = tls.test_endpoint("127.0.0.1", server.port, verify=False)
    finally:
        server.close()

    assert result["ok"] is True, result["error"]
    assert result["protocol"].startswith("TLSv1.")
    assert result["cipher"]
    assert result["peer_subject"].startswith("127.0.0.1")   # CN, then O
    assert "MWL Broker" in result["peer_subject"]
    assert result["peer_san"] and "127.0.0.1" in result["peer_san"]
    assert result["peer_self_signed"] is True
    assert result["peer_days_left"] is not None


def test_endpoint_check_verifies_against_the_configured_ca():
    generated = _generate(365, "127.0.0.1", ["127.0.0.1"])
    server = _TlsServer(generated["certificate_path"], generated["key_path"])
    try:
        # trusting the certificate itself makes verification succeed
        ok = tls.test_endpoint("127.0.0.1", server.port, verify=True,
                               ca_file=generated["certificate_path"])
        # ... without it, the self-signed certificate is rejected
        failed = tls.test_endpoint("127.0.0.1", server.port, verify=True)
    finally:
        server.close()

    assert ok["ok"] is True, ok["error"]
    assert failed["ok"] is False
    assert "verification failed" in failed["error"]
    # the message tells the operator what to do
    assert "verify" in failed["error"].lower()


def test_endpoint_check_reports_an_unreachable_port():
    result = tls.test_endpoint("127.0.0.1", 1, verify=False)
    assert result["ok"] is False and result["error"]


def test_endpoint_check_accepts_a_client_certificate():
    """mTLS: the server demands a certificate, the broker presents one."""
    server_cert = _generate(365, "127.0.0.1", ["127.0.0.1"], filename="server")
    client_cert = _generate(365, "mwl-broker", filename="client")
    server = _TlsServer(server_cert["certificate_path"], server_cert["key_path"],
                        require_client_cert=True, ca_path=client_cert["certificate_path"])
    _configure(tls_outbound_client_cert_file=client_cert["certificate_path"],
               tls_outbound_client_key_file=client_cert["key_path"],
               tls_outbound_ca_file=server_cert["certificate_path"])
    try:
        result = tls.test_endpoint("127.0.0.1", server.port, verify=True,
                                   ca_file=server_cert["certificate_path"])
    finally:
        server.close()
    assert result["ok"] is True, result["error"]


def test_publish_metrics_reports_the_soonest_expiry():
    from prometheus_client import REGISTRY

    generated = _generate(42, "broker.local")
    _configure(tls_inbound_cert_file=generated["certificate_path"])

    tls.publish_metrics()

    assert REGISTRY.get_sample_value("mwl_tls_certificate_days_left") == 41


def test_describe_is_short_and_safe():
    _configure(tls_inbound_enabled=True, tls_inbound_port=2762,
               tls_inbound_client_auth="required", tls_outbound_verify=True)
    described = tls.describe()
    assert described == {"inbound_enabled": True, "inbound_port": 2762,
                         "inbound_client_auth": "required", "outbound_verify": True}
