"""Alerting: push broker events to a webhook (Slack/Teams-compatible JSON).

The operator should hear about a dead RIS or a spool dead letter **before** the
radiology calls. Delivery is deliberately fire-and-forget:

* every send happens on a short-lived background thread — a slow or broken
  webhook must never delay a C-FIND or a C-STORE,
* a failure is logged and counted, never propagated to the caller,
* each event kind is de-bounced per subject (`notify_min_interval_s`), so a
  flapping source does not turn into a message storm.

The payload carries the structured event plus a `text` field, which is what
Slack and Microsoft Teams render.
"""
import json
import logging
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from . import metrics, settings_service

log = logging.getLogger("mwl_broker.notify")

# event code -> (severity, human description) — the UI renders this list
EVENTS: dict[str, tuple[str, str]] = {
    "source_down": ("error", "An upstream worklist source stopped answering C-ECHO."),
    "source_recovered": ("info", "An upstream source answers again."),
    "target_down": ("error", "A PACS target stopped answering C-ECHO."),
    "target_recovered": ("info", "A PACS target answers again."),
    "breaker_open": ("warning", "A source was skipped after repeated C-FIND failures."),
    "spool_dead_letter": ("error", "A spooled instance gave up and needs attention."),
    "spool_backlog": ("warning", "Instances are waiting in the spool for too long."),
    "spool_full": ("error", "The C-STORE spool is full — new instances are refused."),
    "config_error": ("error", "The configuration health checks found an error."),
    "tls_certificate_expiring": ("warning", "A configured TLS certificate expires soon."),
}

# last delivery attempt per de-bounce key (in-memory: a restart clears it)
_last_sent: dict[str, float] = {}
_lock = threading.Lock()


def events() -> list[dict]:
    """The known event codes (for the settings UI)."""
    return [
        {"code": code, "severity": severity, "description": description}
        for code, (severity, description) in sorted(EVENTS.items())
    ]


def _urls() -> list[str]:
    """One or more webhook targets (comma separated) — e.g. Teams *and* a
    syslog converter in parallel."""
    return [part.strip() for part in
            (settings_service.get_str("notify_webhook_url") or "").split(",")
            if part.strip()]


def subscribed(code: str) -> bool:
    raw = settings_service.get_str("notify_events").strip()
    if not raw:
        return False
    wanted = {part.strip() for part in raw.split(",") if part.strip()}
    return code in wanted


def min_interval_s() -> int:
    return settings_service.get_int("notify_min_interval_s")


def _debounced(key: str) -> bool:
    """True when this key was notified too recently (suppressed)."""
    import time

    interval = min_interval_s()
    if interval <= 0:
        return False
    now = time.monotonic()
    with _lock:
        last = _last_sent.get(key)
        if last is not None and (now - last) < interval:
            return True
        _last_sent[key] = now
    return False


def _payload(code: str, message: str, details: dict | None) -> dict:
    severity = EVENTS.get(code, ("info", ""))[0]
    broker_aet = settings_service.get_str("broker_aet")
    return {
        # Slack/Teams render `text`
        "text": f"[{severity.upper()}] MWL broker: {message}",
        "event": code,
        "severity": severity,
        "message": message,
        "details": details or {},
        "broker": broker_aet,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _redacted(url: str) -> str:
    """Webhook URLs usually carry a secret token — never log the full URL."""
    try:
        parts = urllib.parse.urlsplit(url)
        return f"{parts.scheme}://{parts.netloc}/…"
    except Exception:
        return "<webhook>"


def _post(url: str, payload: dict, timeout_s: int = 5) -> tuple[bool, str]:
    """Deliver one payload. Returns (ok, error)."""
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "mwl-broker"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return 200 <= response.status < 300, ""
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:  # network/timeout — never fatal
        return False, str(exc)[:200]


def _deliver(url: str, payload: dict, code: str) -> None:
    ok, error = _post(url, payload)
    if ok:
        metrics.NOTIFY_SENT.labels(event=code).inc()
        log.info("notify: delivered %s", code)
    else:
        metrics.NOTIFY_FAILED.labels(event=code).inc()
        log.warning("notify: delivery of %s failed: %s", code, error)


def notify(code: str, message: str, details: dict | None = None,
           subject: str | None = None) -> bool:
    """Send an event (fire-and-forget). Returns whether it was dispatched.

    `subject` de-bounces per object (e.g. one message per source, not one per
    source event kind).
    """
    if code not in EVENTS:
        log.error("notify: unknown event %r", code)
        return False
    urls = _urls()
    if not urls or not subscribed(code):
        return False
    key = f"{code}:{subject or ''}"
    if _debounced(key):
        metrics.NOTIFY_SUPPRESSED.labels(event=code).inc()
        log.info("notify: %s suppressed (within the minimum interval)", key)
        return False

    payload = _payload(code, message, details)
    threading.Thread(target=_deliver_all, args=(urls, payload, code), daemon=True).start()
    return True


def _deliver_all(urls: list[str], payload: dict, code: str) -> None:
    """Deliver to every configured target; ok when at least one accepted it."""
    errors = []
    delivered = 0
    for url in urls:
        ok, error = _post(url, payload)
        if ok:
            delivered = True
            metrics.NOTIFY_SENT.labels(event=code).inc()
        else:
            metrics.NOTIFY_FAILED.labels(event=code).inc()
            errors.append(f"{_redacted(url)}: {error}")
    if delivered:
        log.info("notify: delivered %s to %d webhook(s)", code, len(urls))
    else:
        log.warning("notify: delivery of %s failed: %s", code, "; ".join(errors))


def send_test() -> dict:
    """Send a test message synchronously to every configured target."""
    urls = _urls()
    if not urls:
        return {"ok": False, "error": "no webhook URL configured"}
    payload = _payload("config_error", "Test message from the MWL broker configuration UI.",
                       {"test": True})
    results = [_post(url, payload) for url in urls]
    ok = any(ok for ok, _error in results)
    if ok:
        metrics.NOTIFY_SENT.labels(event="test").inc()
    else:
        metrics.NOTIFY_FAILED.labels(event="test").inc()
    errors = [f"{_redacted(url)}: {error}" for (ok, error), url in zip(results, urls) if not ok]
    log.info("notify: test message to %d webhook(s) -> %s", len(urls),
             "ok" if ok else "failed")
    return {"ok": ok, "error": "" if ok else ("; ".join(errors) or "delivery failed")}


def reset_for_tests() -> None:
    with _lock:
        _last_sent.clear()
