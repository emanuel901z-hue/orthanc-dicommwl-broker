"""Alerting: event registry, webhook delivery, de-bounce, failure tolerance."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from mwl_broker import notify, settings_service


class _Receiver(BaseHTTPRequestHandler):
    """Minimal webhook receiver — records every payload it gets."""

    received: list[dict] = []
    status = 200

    def do_POST(self):  # noqa: N802 (http.server API)
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        try:
            type(self).received.append(json.loads(body))
        except Exception:
            type(self).received.append({"raw": body.decode("utf-8", "replace")})
        self.send_response(type(self).status)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):  # keep the test output clean
        pass


@pytest.fixture()
def webhook():
    """A local webhook receiver; yields (url, received, set_status)."""
    _Receiver.received = []
    _Receiver.status = 200
    server = HTTPServer(("127.0.0.1", 0), _Receiver)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}/hook"
    try:
        yield url, _Receiver.received, lambda status: setattr(_Receiver, "status", status)
    finally:
        server.shutdown()
        server.server_close()


def _wait_for(predicate, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


# ── registry & settings ────────────────────────────────────────────────


def test_events_registry_is_exposed():
    codes = {event["code"] for event in notify.events()}

    assert {"source_down", "source_recovered", "target_down", "target_recovered",
            "breaker_open", "spool_dead_letter", "spool_backlog", "spool_full",
            "config_error"} <= codes
    entry = next(event for event in notify.events() if event["code"] == "source_down")
    assert entry["severity"] == "error" and entry["description"]


def test_subscription_parsing():
    settings_service.set_value("notify_events", "source_down, spool_full")
    assert notify.subscribed("source_down") is True
    assert notify.subscribed("spool_full") is True
    assert notify.subscribed("target_down") is False

    settings_service.set_value("notify_events", "")
    assert notify.subscribed("source_down") is False


def test_settings_validation():
    assert settings_service.validate_value("notify_webhook_url", "https://x/hook") == []
    assert settings_service.validate_value("notify_webhook_url", "") == []
    assert settings_service.validate_value("notify_webhook_url", "ftp://x")
    assert settings_service.validate_value("notify_events", "source_down,spool_full") == []
    assert settings_service.validate_value("notify_events", "source_down,nope")


# ── delivery ───────────────────────────────────────────────────────────


def test_notify_without_a_url_is_a_noop():
    settings_service.set_value("notify_events", "source_down")
    settings_service.set_value("notify_webhook_url", "")

    assert notify.notify("source_down", "should not go anywhere") is False


def test_notify_requires_a_subscription(webhook):
    url, received, _ = webhook
    settings_service.set_value("notify_webhook_url", url)
    settings_service.set_value("notify_events", "target_down")

    assert notify.notify("source_down", "not subscribed") is False
    assert _wait_for(lambda: True, 0.1)
    assert received == []


def test_notify_delivers_a_slack_compatible_payload(webhook):
    url, received, _ = webhook
    settings_service.set_value("notify_webhook_url", url)
    settings_service.set_value("notify_events", "source_down")

    assert notify.notify("source_down", "source 'ris-a' stopped answering",
                         {"kind": "source", "name": "ris-a"}, subject="ris-a") is True

    assert _wait_for(lambda: len(received) == 1), "no webhook call arrived"
    payload = received[0]
    assert payload["event"] == "source_down"
    assert payload["severity"] == "error"
    assert payload["details"]["name"] == "ris-a"
    assert "ris-a" in payload["text"] and "[ERROR]" in payload["text"]
    assert payload["broker"] and payload["timestamp"]


def test_notify_debounces_the_same_event_and_subject(webhook):
    url, received, _ = webhook
    settings_service.set_value("notify_webhook_url", url)
    settings_service.set_value("notify_events", "source_down")
    settings_service.set_value("notify_min_interval_s", "300")

    assert notify.notify("source_down", "first", subject="ris-a") is True
    assert notify.notify("source_down", "second", subject="ris-a") is False
    # a different subject is a different event
    assert notify.notify("source_down", "other source", subject="ris-b") is True

    assert _wait_for(lambda: len(received) == 2)
    time.sleep(0.1)
    assert len(received) == 2


def test_debounce_can_be_disabled(webhook):
    url, received, _ = webhook
    settings_service.set_value("notify_webhook_url", url)
    settings_service.set_value("notify_events", "source_down")
    settings_service.set_value("notify_min_interval_s", "0")

    assert notify.notify("source_down", "one", subject="ris-a") is True
    assert notify.notify("source_down", "two", subject="ris-a") is True

    assert _wait_for(lambda: len(received) == 2)


def test_unknown_event_is_rejected():
    assert notify.notify("not_an_event", "nope") is False


def test_delivery_failure_is_not_fatal(webhook, caplog):
    url, received, set_status = webhook
    settings_service.set_value("notify_webhook_url", url)
    settings_service.set_value("notify_events", "source_down")
    set_status(500)

    # the call returns immediately (fire-and-forget) and must not raise
    assert notify.notify("source_down", "target is angry", subject="ris-a") is True

    assert _wait_for(lambda: len(received) == 1)


def test_unreachable_webhook_is_tolerated():
    settings_service.set_value("notify_webhook_url", "http://127.0.0.1:1/hook")
    settings_service.set_value("notify_events", "source_down")

    assert notify.notify("source_down", "nobody is listening", subject="ris-a") is True
    time.sleep(0.2)  # the background delivery fails silently


def test_send_test_reports_the_result(webhook):
    url, received, set_status = webhook
    settings_service.set_value("notify_webhook_url", url)

    assert notify.send_test()["ok"] is True
    assert received and received[0]["details"]["test"] is True

    set_status(503)
    result = notify.send_test()
    assert result["ok"] is False and "503" in result["error"]


def test_webhook_url_is_redacted_in_the_logs(webhook, caplog):
    """A Slack/Teams URL carries a secret token — it must not reach the logs."""
    import logging

    url, _received, _ = webhook
    settings_service.set_value("notify_webhook_url", url + "/secret-token-abc")

    with caplog.at_level(logging.INFO, logger="mwl_broker.notify"):
        notify.send_test()

    joined = " ".join(record.getMessage() for record in caplog.records)
    assert "secret-token-abc" not in joined
    assert notify._redacted("https://hooks.slack.com/services/T/B/secret") == \
        "https://hooks.slack.com/…"


def test_send_test_without_url():
    settings_service.set_value("notify_webhook_url", "")
    assert notify.send_test() == {"ok": False, "error": "no webhook URL configured"}


# ── event sources ──────────────────────────────────────────────────────


def test_echo_transition_alerts(webhook, monkeypatch):
    """A source that stops answering produces exactly one source_down alert."""
    from mwl_broker import echo
    from mwl_broker.upstream import SourceCfg

    url, received, _ = webhook
    settings_service.set_value("notify_webhook_url", url)
    settings_service.set_value("notify_events", "source_down,source_recovered")
    settings_service.set_value("notify_min_interval_s", "0")

    cfg = SourceCfg(id=1, name="ris-a", aet="RIS_A", host="127.0.0.1", port=1,
                    calling_aet="MWLBROKER", charset="ISO_IR 100", timeout_s=1)
    echo.echo_one("source", cfg)          # first check: no alert (no transition yet)
    echo.echo_one("source", cfg)          # still down: still no new alert
    assert received == []

    monkeypatch.setattr("mwl_broker.echo.c_echo", lambda *a, **k: None)
    echo.echo_one("source", cfg)          # recovered → alert

    assert _wait_for(lambda: len(received) == 1)
    assert received[0]["event"] == "source_recovered"
    assert received[0]["details"]["name"] == "ris-a"


def test_echo_down_alert(webhook, monkeypatch):
    from mwl_broker import echo
    from mwl_broker.upstream import SourceCfg

    url, received, _ = webhook
    settings_service.set_value("notify_webhook_url", url)
    settings_service.set_value("notify_events", "source_down")
    settings_service.set_value("notify_min_interval_s", "0")

    cfg = SourceCfg(id=2, name="ris-b", aet="RIS_B", host="127.0.0.1", port=1,
                    calling_aet="MWLBROKER", charset="ISO_IR 100", timeout_s=1)
    monkeypatch.setattr("mwl_broker.echo.c_echo", lambda *a, **k: None)
    echo.echo_one("source", cfg)          # healthy
    monkeypatch.undo()
    echo.echo_one("source", cfg)          # now unreachable

    assert _wait_for(lambda: len(received) == 1)
    assert received[0]["event"] == "source_down"


def test_breaker_open_alerts(webhook):
    from mwl_broker import breaker
    from mwl_broker.db import session_factory
    from mwl_broker.models import MwlSource

    url, received, _ = webhook
    settings_service.set_value("notify_webhook_url", url)
    settings_service.set_value("notify_events", "breaker_open")
    settings_service.set_value("breaker_fail_threshold", "1")
    settings_service.set_value("notify_min_interval_s", "0")
    with session_factory()() as s:
        row = MwlSource(name="ris-a", aet="RIS_A", host="127.0.0.1", port=1,
                        calling_aet="MWLBROKER", charset="ISO_IR 100")
        s.add(row)
        s.commit()
        source_id = row.id

    breaker.record_failure(source_id, "connection refused")

    assert _wait_for(lambda: len(received) == 1)
    assert received[0]["event"] == "breaker_open"
    assert received[0]["details"]["failures"] == 1


def test_spool_dead_letter_alerts(webhook, monkeypatch):
    from pydicom.dataset import Dataset
    from pydicom.uid import CTImageStorage

    from mwl_broker import cstore, spool
    from mwl_broker.db import session_factory
    from mwl_broker.models import PacsTarget

    url, received, _ = webhook
    settings_service.set_value("notify_webhook_url", url)
    settings_service.set_value("notify_events", "spool_dead_letter")
    settings_service.set_value("spool_max_attempts", "1")
    settings_service.set_value("notify_min_interval_s", "0")
    with session_factory()() as s:
        target = PacsTarget(name="pacs", aet="PACS", host="127.0.0.1", port=1,
                            calling_aet="MWLBROKER", is_default=True)
        s.add(target)
        s.commit()
        target_id = target.id

    ds = Dataset()
    ds.SOPClassUID = CTImageStorage
    ds.SOPInstanceUID = "1.2.3.4"
    spool.enqueue(ds, None, target_id, "pacs", "boom")
    monkeypatch.setattr(cstore, "send_store",
                        lambda *_: (_ for _ in ()).throw(ConnectionError("down")))
    spool.forward(spool.items()[0]["id"])

    assert _wait_for(lambda: len(received) == 1)
    assert received[0]["event"] == "spool_dead_letter"
    assert received[0]["details"]["target"] == "pacs"


def test_reset_clears_the_debounce(webhook):
    url, received, _ = webhook
    settings_service.set_value("notify_webhook_url", url)
    settings_service.set_value("notify_events", "source_down")
    settings_service.set_value("notify_min_interval_s", "300")

    notify.notify("source_down", "first", subject="ris-a")
    assert notify.notify("source_down", "second", subject="ris-a") is False

    notify.reset_for_tests()
    assert notify.notify("source_down", "after reset", subject="ris-a") is True
