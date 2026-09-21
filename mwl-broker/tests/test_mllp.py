"""The MLLP listener — many RIS speak only this, so it must be tested directly.

Covers the framing (a TCP stream, not messages), the apply path with the same
parser as the REST endpoint, the ACK/NAK answer and a real socket round-trip
against the listener thread.
"""
import socket
import threading
import time

import pytest

from mwl_broker import hl7, mllp, settings_service

ORM = (
    "MSH|^~\\&|RIS|KH|MWLBROKER|KH|20260921100000||ORM^O01|MSG-MLLP-1|P|2.4\r"
    "PID|1||P-1||Muster^Max||19800101|M\r"
    "ORC|NW|ACC-MLLP-1\r"
    "OBR|1|ACC-MLLP-1||CT\r"
)


class FakeSocket:
    """Minimal recv() stand-in: the framing is a pure stream transformation."""

    def __init__(self, payload: bytes, chunk: int = 4096):
        self._payload = payload
        self._chunk = chunk

    def recv(self, _size: int) -> bytes:
        data, self._payload = self._payload[: self._chunk], self._payload[self._chunk:]
        return data


def test_read_frame_unwraps_the_mllp_framing():
    framed = b"\x0b" + ORM.encode() + b"\x1c\x0d"
    assert mllp._read_frame(FakeSocket(framed)) == ORM


def test_read_frame_handles_split_chunks():
    """A real TCP stream arrives in pieces — the framing must survive that."""
    framed = b"\x0b" + ORM.encode() + b"\x1c\x0d"
    text = mllp._read_frame(FakeSocket(framed, chunk=7))
    assert text == ORM


def test_read_frame_rejects_oversized_messages():
    huge = b"\x0b" + b"x" * (mllp.MAX_FRAME + 10)
    with pytest.raises(ValueError, match="maximum frame size"):
        mllp._read_frame(FakeSocket(huge, chunk=1024 * 1024))


def test_read_frame_returns_empty_on_closed_connection():
    assert mllp._read_frame(FakeSocket(b"")) == ""


def test_handle_message_applies_and_answers_with_an_ack(client):
    """The MLLP path uses the same parser and upsert as the REST endpoint."""
    from sqlalchemy import select

    from mwl_broker.db import session_factory
    from mwl_broker.models import Hl7Message, LocalWorklistItem

    ok, control_id, error = mllp.handle_message(ORM)

    assert ok is True
    assert control_id == "MSG-MLLP-1"
    assert error == ""

    with session_factory()() as s:
        item = s.scalars(select(LocalWorklistItem).where(
            LocalWorklistItem.accession == "ACC-MLLP-1")).first()
        assert item is not None
        assert item.modality == "CT"
        # the message is logged with the mllp transport
        logged = s.scalars(select(Hl7Message).order_by(Hl7Message.id.desc())).first()
        assert logged.transport == "mllp"

    ack = hl7.build_ack(control_id, ok, error)
    assert "MSA|AA|MSG-MLLP-1" in ack


def test_handle_message_reports_a_bad_message_without_crashing(client):
    """A broken sender gets a NAK, the listener keeps running."""
    ok, control_id, error = mllp.handle_message("this is not HL7 at all")

    assert ok is False
    assert error, "the reason must be visible"
    assert "MSA|AE|" in hl7.build_ack(control_id, ok, error)


def test_handle_message_survives_an_unexpected_error(client, monkeypatch):
    """An exception inside the intake must not kill the listener."""
    from mwl_broker import local_worklist

    def boom(*_args, **_kwargs):
        raise RuntimeError("database is on fire")

    monkeypatch.setattr(local_worklist, "upsert_from_hl7", boom)

    ok, control_id, error = mllp.handle_message(ORM)
    assert ok is False
    assert "database is on fire" in error


def test_listener_answers_a_real_socket_round_trip(client):
    """End to end: a client sends a framed ORM and reads the ACK."""
    settings_service.set_value("hl7_mllp_enabled", "true")
    settings_service.set_value("hl7_mllp_bind", "127.0.0.1")
    settings_service.set_value("hl7_mllp_port", "0")  # ephemeral: no port clash

    stop = threading.Event()
    # serve() binds the configured port; bind to a free one instead
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    settings_service.set_value("hl7_mllp_port", str(port))

    thread = threading.Thread(target=mllp.serve, args=(stop,), daemon=True)
    thread.start()

    deadline = time.time() + 5
    ack = ""
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2) as conn:
                conn.sendall(b"\x0b" + ORM.encode() + b"\x1c\x0d")
                ack = conn.recv(4096).decode("utf-8", "replace")
                break
        except OSError:
            time.sleep(0.1)

    stop.set()
    thread.join(timeout=3)

    assert "MSA|AA|MSG-MLLP-1" in ack, ack or "no ACK received"


def test_listener_reports_a_busy_port_instead_of_crashing(client):
    """A second listener on the same port must not take the process down."""
    settings_service.set_value("hl7_mllp_bind", "127.0.0.1")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as holder:
        holder.bind(("127.0.0.1", 0))
        holder.listen(1)
        port = holder.getsockname()[1]
        settings_service.set_value("hl7_mllp_port", str(port))

        stop = threading.Event()
        mllp.serve(stop)  # returns immediately, logs the error
    # nothing raised, the process is still alive
    assert stop.is_set() is False
