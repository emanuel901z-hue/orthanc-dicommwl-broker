"""C-ECHO monitoring: single-node echo + the background loop.

The loop is exercised with a patched interval/purge so it runs fast and
deterministically (no sleeping for minutes).
"""
import threading
import time

from pydicom.dataset import Dataset
from pynetdicom import AE, evt
from pynetdicom.sop_class import Verification
from sqlalchemy import select

from mwl_broker import echo, settings_service
from mwl_broker.db import session_factory
from mwl_broker.models import MwlSource, PacsTarget


def _verification_scp(aet="RIS_A"):
    def handle_echo(event):
        return 0x0000

    ae = AE(ae_title=aet)
    ae.add_supported_context(Verification)
    srv = ae.start_server(("127.0.0.1", 0), block=False,
                          evt_handlers=[(evt.EVT_C_ECHO, handle_echo)])
    return srv, srv.server_address[1]


def _seed_source(port: int, name="ris-a", enabled=True) -> MwlSource:
    with session_factory()() as s:
        row = MwlSource(name=name, aet="RIS_A", host="127.0.0.1", port=port,
                        calling_aet="MWLBROKER", charset="ISO_IR 100", enabled=enabled)
        s.add(row)
        s.commit()
        s.refresh(row)
        s.expunge(row)
        return row


def test_echo_one_records_success_and_rtt():
    srv, port = _verification_scp()
    try:
        row = _seed_source(port)
        result = echo.echo_one("source", row)
        assert result["ok"] is True
        assert result["error"] is None
        assert isinstance(result["rtt_ms"], int) and result["rtt_ms"] >= 0
        assert result["last_check"] is not None
        # snapshot exposes the recorded state (list of entries)
        entry = next(e for e in echo.snapshot()["source"] if e["id"] == row.id)
        assert entry["ok"] is True and entry["name"] == "ris-a"
    finally:
        srv.shutdown()


def test_echo_one_records_failure():
    row = _seed_source(1)  # nothing listening
    result = echo.echo_one("source", row)
    assert result["ok"] is False
    assert result["rtt_ms"] is None
    assert result["error"]


def test_echo_loop_echoes_enabled_nodes_and_purges(monkeypatch):
    srv, port = _verification_scp()
    try:
        src = _seed_source(port)
        with session_factory()() as s:
            s.add(PacsTarget(name="pacs", aet="PACS", host="127.0.0.1", port=port,
                             calling_aet="MWLBROKER"))
            s.commit()

        purges = []
        monkeypatch.setattr(settings_service, "purge_seen_items", lambda *a, **k: purges.append(1) or 0)
        # 0 s interval → the 60-tick purge branch is reached in milliseconds
        monkeypatch.setattr(settings_service, "get_int", lambda key: 0)

        stop = threading.Event()
        t = threading.Thread(target=echo.echo_loop, args=(5, stop), daemon=True)
        t.start()
        deadline = time.time() + 5
        while not purges and time.time() < deadline:
            time.sleep(0.02)
        stop.set()
        t.join(timeout=2)

        assert not t.is_alive(), "echo loop did not stop"
        assert purges, "retention purge was never triggered"
        snap = echo.snapshot()
        assert next(e for e in snap["source"] if e["id"] == src.id)["ok"] is True
        assert next(e for e in snap["target"] if e["id"] == 1)["ok"] is True
    finally:
        srv.shutdown()


def test_echo_loop_survives_db_errors(monkeypatch):
    """A failing DB lookup must not kill the loop."""
    from mwl_broker import db

    calls = []

    def broken_factory():
        calls.append(1)
        raise RuntimeError("db not ready")

    monkeypatch.setattr(db, "session_factory", broken_factory)
    monkeypatch.setattr(echo, "session_factory", broken_factory)
    monkeypatch.setattr(settings_service, "get_int", lambda key: 0)

    stop = threading.Event()
    t = threading.Thread(target=echo.echo_loop, args=(5, stop), daemon=True)
    t.start()
    time.sleep(0.2)
    stop.set()
    t.join(timeout=2)

    assert not t.is_alive()
    assert calls, "loop never attempted a DB read"
