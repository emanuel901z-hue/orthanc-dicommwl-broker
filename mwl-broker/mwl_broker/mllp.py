"""MLLP listener for HL7 ORM orders.

Many RIS only speak MLLP (a TCP stream with `0x0B` … `0x1C 0x0D` framing), so
the broker offers a listener next to the REST endpoint. It applies the same
parser and upsert path, answers with an ACK/NAK and never touches the DICOM
path — a slow or broken sender only occupies its own connection.
"""
import logging
import socket
import threading

from . import hl7, local_worklist, metrics, settings_service

log = logging.getLogger("mwl_broker.mllp")

START_BLOCK = b"\x0b"
END_BLOCK = b"\x1c\x0d"
MAX_FRAME = 5 * 1024 * 1024


def _read_frame(conn: socket.socket) -> str:
    buffer = bytearray()
    while True:
        chunk = conn.recv(4096)
        if not chunk:
            break
        buffer.extend(chunk)
        if END_BLOCK in buffer:
            break
        if len(buffer) > MAX_FRAME:
            raise ValueError("message exceeds the maximum frame size")
    if not buffer:
        return ""
    start = buffer.find(START_BLOCK)
    if start >= 0:
        buffer = buffer[start + 1:]
    end = buffer.find(END_BLOCK)
    if end >= 0:
        buffer = buffer[:end]
    return buffer.decode("utf-8", "replace")


def handle_message(text: str, transport: str = "mllp") -> tuple[bool, str, str]:
    """Parse and apply one message. Returns (ok, control_id, error)."""
    parsed = hl7.parse(text)
    control_id = parsed.get("control_id", "")

    try:
        # the shared path logs the message (created/updated/cancelled/rejected)
        result = local_worklist.upsert_from_hl7(
            parsed, transport=transport,
            default_station_aet=settings_service.get_str("hl7_default_station_aet"),
            default_modality=settings_service.get_str("hl7_default_modality"),
        )
    except Exception as exc:  # a bad message must never kill the listener
        error = str(exc)[:200]
        local_worklist.log_hl7(transport, parsed, "error", error)
        metrics.HL7_MESSAGES.labels(transport=transport, result="error").inc()
        return False, control_id, error

    metrics.HL7_MESSAGES.labels(transport=transport, result=result["action"]).inc()
    if result["action"] == "rejected":
        return False, control_id, result.get("error", "")
    return True, control_id, ""


def serve(stop: threading.Event) -> None:
    """Accept MLLP connections until `stop` is set."""
    bind = settings_service.get_str("hl7_mllp_bind") or "0.0.0.0"
    port = settings_service.get_int("hl7_mllp_port")
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((bind, port))
        server.listen(8)
        server.settimeout(0.5)
    except OSError as exc:
        log.error("MLLP listener cannot bind to %s:%s — %s", bind, port, exc)
        server.close()
        return
    log.info("MLLP listener on %s:%s", bind, port)

    try:
        while not stop.is_set():
            try:
                conn, addr = server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with conn:
                conn.settimeout(10)
                try:
                    text = _read_frame(conn)
                    ok, control_id, error = handle_message(text, transport="mllp")
                    conn.sendall(hl7.build_ack(control_id, ok, error).encode("utf-8"))
                except Exception as exc:
                    log.warning("MLLP connection from %s failed: %s", addr, exc)
    finally:
        server.close()
        log.info("MLLP listener stopped")
