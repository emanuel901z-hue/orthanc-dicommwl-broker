"""DICOM TLS — contexts for the broker as server and as client, plus the
certificate handling a hospital without its own PKI actually needs.

Three ideas shape this module:

1. **Off by default, per direction.** A LAN/VPN installation keeps working
   unchanged; TLS is switched on for the inbound listener and/or per upstream
   node when the network requires it. Plain and TLS can run side by side
   (separate ports), which is what a staged rollout needs: one modality at a
   time.
2. **The operator has to see what is wrong.** `overview()` answers "does this
   file exist, is it readable, whose is it, when does it expire, do key and
   certificate belong together" in plain words, and `test_endpoint()` performs a
   real handshake and reports protocol, cipher and the peer's certificate — the
   check before a modality is switched over.
3. **Nothing secret leaves the process.** Private keys are never returned by the
   API; generated keys are written with mode 0600.

The settings are read through a short cache (the DICOM path asks for them per
association).
"""
import ipaddress
import logging
import socket
import ssl
import time
from datetime import datetime, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from . import metrics, settings_service

log = logging.getLogger("mwl_broker.tls")

MIN_TLS_VERSION = ssl.TLSVersion.TLSv1_2
EXPIRY_WARNING_DAYS = 30

# ── settings (short cache: asked per association) ──────────────────────

_config_cache: dict = {"at": 0.0, "value": None}
_CONFIG_TTL_S = 2.0


def _config() -> dict:
    now = time.monotonic()
    cached = _config_cache["value"]
    if cached is not None and (now - _config_cache["at"]) < _CONFIG_TTL_S:
        return cached
    value = {
        "inbound_enabled": settings_service.get_bool("tls_inbound_enabled"),
        "inbound_port": settings_service.get_int("tls_inbound_port"),
        "inbound_cert": settings_service.get_str("tls_inbound_cert_file").strip(),
        "inbound_key": settings_service.get_str("tls_inbound_key_file").strip(),
        "inbound_ca": settings_service.get_str("tls_inbound_ca_file").strip(),
        "inbound_client_auth": (settings_service.get_str("tls_inbound_client_auth") or "none").strip().lower(),
        "outbound_ca": settings_service.get_str("tls_outbound_ca_file").strip(),
        "outbound_cert": settings_service.get_str("tls_outbound_client_cert_file").strip(),
        "outbound_key": settings_service.get_str("tls_outbound_client_key_file").strip(),
        "outbound_verify": settings_service.get_bool("tls_outbound_verify"),
        "dir": settings_service.get_str("tls_dir").strip() or "/var/lib/mwl-broker/tls",
    }
    _config_cache["at"] = now
    _config_cache["value"] = value
    return value


def reset_for_tests() -> None:
    _config_cache["at"] = 0.0
    _config_cache["value"] = None


def reload() -> None:
    """Drop the settings cache (the API reads fresh values after a change)."""
    reset_for_tests()


def inbound_enabled() -> bool:
    return bool(_config()["inbound_enabled"])


def inbound_port() -> int:
    return int(_config()["inbound_port"])


def directory() -> Path:
    return Path(str(_config()["dir"]))


# ── contexts ───────────────────────────────────────────────────────────


def build_server_context() -> ssl.SSLContext | None:
    """TLS context for the inbound DICOM listener (None = plain only)."""
    cfg = _config()
    if not cfg["inbound_enabled"]:
        return None
    if not cfg["inbound_cert"] or not cfg["inbound_key"]:
        raise ValueError("inbound TLS needs a certificate and a private key "
                         "(tls_inbound_cert_file / tls_inbound_key_file)")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = MIN_TLS_VERSION
    context.load_cert_chain(certfile=cfg["inbound_cert"], keyfile=cfg["inbound_key"])

    mode = cfg["inbound_client_auth"]
    if mode in ("optional", "required"):
        if not cfg["inbound_ca"]:
            raise ValueError(f"client authentication '{mode}' needs a CA file "
                             "(tls_inbound_ca_file) to verify the modality certificates")
        context.load_verify_locations(cafile=cfg["inbound_ca"])
        context.verify_mode = (ssl.CERT_REQUIRED if mode == "required"
                               else ssl.CERT_OPTIONAL)
    else:
        context.verify_mode = ssl.CERT_NONE
    return context


def build_client_context(verify: bool | None = None, ca_file: str = "") -> ssl.SSLContext:
    """TLS context for outgoing associations (upstream queries, forwarding)."""
    cfg = _config()
    use_verify = cfg["outbound_verify"] if verify is None else verify
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = MIN_TLS_VERSION
    if use_verify:
        context.verify_mode = ssl.CERT_REQUIRED
        context.check_hostname = True
        trust = ca_file or cfg["outbound_ca"]
        if trust:
            context.load_verify_locations(cafile=trust)
        else:
            context.load_default_certs()
    else:
        # explicitly asked for: a lab PACS with a self-signed certificate
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    if cfg["outbound_cert"] and cfg["outbound_key"]:
        context.load_cert_chain(certfile=cfg["outbound_cert"], keyfile=cfg["outbound_key"])
    return context


def client_tls_args(verify: bool | None = None, ca_file: str = "",
                    server_name: str = "") -> tuple:
    """`tls_args` for pynetdicom's `associate()`.

    The server name is required: with verification switched on, Python refuses
    to check a hostname it was not given (and SNI needs it as well).
    """
    return (build_client_context(verify, ca_file), server_name or None)


# ── certificate inspection ─────────────────────────────────────────────


def _load_cert(path: str) -> x509.Certificate:
    data = Path(path).read_bytes()
    try:
        return x509.load_pem_x509_certificate(data)
    except ValueError:
        return x509.load_der_x509_certificate(data)


def _name(name: x509.Name) -> str:
    parts = []
    for attribute in (NameOID.COMMON_NAME, NameOID.ORGANIZATION_NAME,
                      NameOID.ORGANIZATIONAL_UNIT_NAME, NameOID.COUNTRY_NAME):
        value = name.get_attributes_for_oid(attribute)
        if value:
            parts.append(str(value[0].value))
    return ", ".join(parts) or str(name.rfc4514_string())


def inspect_certificate(path: str) -> dict:
    """Everything an operator wants to know about a certificate file."""
    result = {"path": path, "exists": False, "ok": False, "error": ""}
    if not path:
        result["error"] = "not configured"
        return result
    file = Path(path)
    if not file.is_file():
        result["error"] = "file not found"
        return result
    result["exists"] = True
    try:
        cert = _load_cert(path)
    except Exception as exc:
        result["error"] = f"not a readable certificate: {str(exc)[:120]}"
        return result

    now = datetime.now(timezone.utc)
    not_after = cert.not_valid_after_utc
    days_left = int((not_after - now).total_seconds() // 86400)
    try:
        san = [str(entry.value) for entry in cert.extensions
               .get_extension_for_class(x509.SubjectAlternativeName).value]
    except x509.ExtensionNotFound:
        san = []
    try:
        is_ca = bool(cert.extensions.get_extension_for_class(x509.BasicConstraints)
                     .value.ca)
    except x509.ExtensionNotFound:
        is_ca = False

    result.update({
        "ok": True,
        "subject": _name(cert.subject),
        "issuer": _name(cert.issuer),
        "self_signed": cert.subject == cert.issuer,
        "serial": format(cert.serial_number, "x"),
        "not_before": cert.not_valid_before_utc.isoformat(),
        "not_after": not_after.isoformat(),
        "days_left": days_left,
        "expired": days_left < 0,
        "expiring_soon": 0 <= days_left < EXPIRY_WARNING_DAYS,
        "san": san,
        "is_ca": is_ca,
        "signature_algorithm": cert.signature_algorithm_oid._name,
    })
    return result


def inspect_private_key(path: str) -> dict:
    """State of a private key file — never the key material itself."""
    result = {"path": path, "exists": False, "ok": False, "error": ""}
    if not path:
        result["error"] = "not configured"
        return result
    file = Path(path)
    if not file.is_file():
        result["error"] = "file not found"
        return result
    result["exists"] = True
    mode = file.stat().st_mode & 0o777
    result["mode"] = format(mode, "03o")
    result["world_readable"] = bool(mode & 0o044)
    try:
        key = serialization.load_pem_private_key(file.read_bytes(), password=None)
    except TypeError:
        result["error"] = "the key is encrypted — the broker cannot use a passphrase-protected key"
        return result
    except Exception as exc:
        result["error"] = f"not a readable private key: {str(exc)[:120]}"
        return result
    result["ok"] = True
    result["type"] = type(key).__name__
    result["bits"] = getattr(key, "key_size", None)
    return result


def key_matches_certificate(cert_path: str, key_path: str) -> bool | None:
    """Whether the private key belongs to the certificate (None = cannot tell)."""
    try:
        cert = _load_cert(cert_path)
        key = serialization.load_pem_private_key(Path(key_path).read_bytes(), password=None)
        cert_public = cert.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        key_public = key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        return cert_public == key_public
    except Exception:
        return None


def overview() -> dict:
    """Certificate management overview for the UI and the health checks."""
    cfg = _config()
    entries = {
        "inbound_cert": inspect_certificate(cfg["inbound_cert"]),
        "inbound_key": inspect_private_key(cfg["inbound_key"]),
        "inbound_ca": inspect_certificate(cfg["inbound_ca"]),
        "outbound_ca": inspect_certificate(cfg["outbound_ca"]),
        "outbound_client_cert": inspect_certificate(cfg["outbound_cert"]),
        "outbound_client_key": inspect_private_key(cfg["outbound_key"]),
    }
    if cfg["inbound_cert"] and cfg["inbound_key"]:
        entries["inbound_pair_matches"] = {
            "ok": key_matches_certificate(cfg["inbound_cert"], cfg["inbound_key"]),
        }
    if cfg["outbound_cert"] and cfg["outbound_key"]:
        entries["outbound_pair_matches"] = {
            "ok": key_matches_certificate(cfg["outbound_cert"], cfg["outbound_key"]),
        }
    return {
        "inbound_enabled": cfg["inbound_enabled"],
        "inbound_port": cfg["inbound_port"],
        "inbound_client_auth": cfg["inbound_client_auth"],
        "outbound_verify": cfg["outbound_verify"],
        "directory": cfg["dir"],
        "entries": entries,
        "certificates": [
            {
                "role": role,
                "path": entry.get("path", ""),
                "subject": entry.get("subject", ""),
                "days_left": entry.get("days_left"),
                "expired": entry.get("expired", False),
                "expiring_soon": entry.get("expiring_soon", False),
                "error": entry.get("error", ""),
            }
            for role, entry in entries.items()
            if isinstance(entry, dict) and entry.get("ok")
            and role in ("inbound_cert", "inbound_ca", "outbound_ca", "outbound_client_cert")
        ],
    }


def expiring_certificates() -> list[dict]:
    """Configured certificates that are expired or close to it."""
    out = []
    for entry in overview()["entries"].values():
        if not isinstance(entry, dict) or not entry.get("ok"):
            continue
        if entry.get("expired") or entry.get("expiring_soon"):
            out.append(entry)
    return out


def publish_metrics() -> None:
    days = [entry["days_left"] for entry in overview()["entries"].values()
            if isinstance(entry, dict) and entry.get("ok") and entry.get("days_left") is not None]
    metrics.TLS_CERT_DAYS.set(min(days) if days else 0)


# ── self-signed certificate (for installations without a PKI) ──────────


def generate_self_signed(common_name: str, days: int = 3650,
                         san: list[str] | None = None, is_ca: bool = False,
                         filename: str = "mwl-broker") -> dict:
    """Create a self-signed certificate + key in the managed directory.

    This is the pragmatic path for a hospital without a PKI: the operator
    generates the certificate here, hands the public part to the modality
    vendor, and switches TLS on. The private key never leaves the broker.
    """
    if not common_name.strip():
        raise ValueError("a common name is required (e.g. the broker host name)")

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name.strip()),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "MWL Broker"),
    ])
    now = datetime.now(timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now.replace(microsecond=0) + __import__("datetime").timedelta(days=days))
        .add_extension(x509.BasicConstraints(ca=is_ca, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, key_encipherment=True, content_commitment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=is_ca,
            crl_sign=is_ca, encipher_only=False, decipher_only=False,
        ), critical=True)
    )

    entries: list[x509.GeneralName] = []
    for item in (san or []):
        value = item.strip()
        if not value:
            continue
        try:
            entries.append(x509.IPAddress(ipaddress.ip_address(value)))
        except ValueError:
            entries.append(x509.DNSName(value))
    if not entries:
        entries = [x509.DNSName(common_name.strip())]
    builder = builder.add_extension(x509.SubjectAlternativeName(entries), critical=False)
    certificate = builder.sign(key, hashes.SHA256())

    target = directory()
    target.mkdir(parents=True, exist_ok=True)
    cert_path = target / f"{filename}.crt"
    key_path = target / f"{filename}.key"
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    key_path.chmod(0o600)
    cert_path.chmod(0o644)
    log.info("TLS: generated a self-signed certificate for '%s' (%s)", common_name, cert_path)

    return {
        "certificate_path": str(cert_path),
        "key_path": str(key_path),
        "certificate_pem": certificate.public_bytes(serialization.Encoding.PEM).decode(),
        "certificate": inspect_certificate(str(cert_path)),
        "key": inspect_private_key(str(key_path)),
        "is_ca": is_ca,
    }


# ── endpoint check ─────────────────────────────────────────────────────


def _inspect_der(der: bytes) -> dict:
    """Inspect a certificate from its DER bytes (used for the peer check)."""
    cert = x509.load_der_x509_certificate(der)
    now = datetime.now(timezone.utc)
    try:
        san = [str(entry.value) for entry in cert.extensions
               .get_extension_for_class(x509.SubjectAlternativeName).value]
    except x509.ExtensionNotFound:
        san = []
    return {
        "subject": _name(cert.subject),
        "issuer": _name(cert.issuer),
        "self_signed": cert.subject == cert.issuer,
        "not_after": cert.not_valid_after_utc.isoformat(),
        "days_left": int((cert.not_valid_after_utc - now).total_seconds() // 86400),
        "san": san,
    }


def test_endpoint(host: str, port: int, verify: bool | None = None,
                  ca_file: str = "", server_name: str = "",
                  timeout_s: int = 10) -> dict:
    """Perform a real TLS handshake and report what the peer presented."""
    result: dict = {"host": host, "port": port, "ok": False, "error": ""}
    context = build_client_context(verify, ca_file)
    if not server_name:
        # verifying without a name is pointless — use the host we connect to
        server_name = host
    try:
        with socket.create_connection((host, port), timeout_s) as raw:
            with context.wrap_socket(raw, server_hostname=server_name or host) as tls_sock:
                result.update({
                    "ok": True,
                    "protocol": tls_sock.version(),
                    "cipher": (tls_sock.cipher() or ("", "", 0))[0],
                })
                # Read the peer certificate in DER form: Python only parses it
                # when verification is on, and the operator wants to see it either way.
                der = tls_sock.getpeercert(binary_form=True)
                if der:
                    peer = _inspect_der(der)
                    result.update({
                        "peer_subject": peer["subject"],
                        "peer_issuer": peer["issuer"],
                        "peer_not_after": peer["not_after"],
                        "peer_san": peer["san"],
                        "peer_days_left": peer["days_left"],
                        "peer_self_signed": peer["self_signed"],
                    })
    except ssl.SSLCertVerificationError as exc:
        result["error"] = (f"certificate verification failed: {exc.verify_message or exc}. "
                           "Import the server certificate into the CA file, or switch "
                           "'verify' off for this node (self-signed lab system).")
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    return result


def describe() -> dict:
    """Short state for the status endpoint and the health checks."""
    cfg = _config()
    return {
        "inbound_enabled": cfg["inbound_enabled"],
        "inbound_port": cfg["inbound_port"],
        "inbound_client_auth": cfg["inbound_client_auth"],
        "outbound_verify": cfg["outbound_verify"],
    }
