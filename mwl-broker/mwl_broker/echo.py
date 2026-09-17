"""Periodic C-ECHO monitoring of all sources and targets + on-demand echo.

Status lives in a module-level dict guarded by a lock — the DICOM/SCP and
API threads both read it."""
import threading
import time
from datetime import datetime, timezone

from sqlalchemy import select

from . import metrics, notify
from .db import session_factory
from .models import MwlSource, PacsTarget
from .upstream import c_echo

_lock = threading.Lock()
ECHO_STATUS: dict[str, dict[int, dict]] = {"source": {}, "target": {}}


def _record(kind: str, row_id: int, name: str, ok: bool, rtt_ms: int | None, error: str | None):
    with _lock:
        previous = ECHO_STATUS[kind].get(row_id)
        ECHO_STATUS[kind][row_id] = {
            "kind": kind,
            "id": row_id,
            "name": name,
            "ok": ok,
            "rtt_ms": rtt_ms,
            "last_check": datetime.now(timezone.utc),
            "error": error,
        }
    metrics.ECHO_UP.labels(kind=kind, name=name).set(1 if ok else 0)

    # Alert on the transition only — a flapping node must not become a storm.
    if previous is not None and previous.get("ok") != ok:
        if ok:
            notify.notify(f"{kind}_recovered", f"{kind} '{name}' answers again.",
                          {"kind": kind, "name": name}, subject=name)
        else:
            notify.notify(f"{kind}_down", f"{kind} '{name}' stopped answering C-ECHO.",
                          {"kind": kind, "name": name, "error": error}, subject=name)


def echo_one(kind: str, row) -> dict:
    started = time.monotonic()
    try:
        c_echo(row.aet, row.host, row.port, row.calling_aet, timeout_s=10)
        rtt = int((time.monotonic() - started) * 1000)
        _record(kind, row.id, row.name, True, rtt, None)
    except Exception as exc:
        _record(kind, row.id, row.name, False, None, str(exc)[:256])
    with _lock:
        return dict(ECHO_STATUS[kind][row.id])


def reset_for_tests() -> None:
    """Clear the in-memory echo state (test isolation)."""
    with _lock:
        ECHO_STATUS["source"].clear()
        ECHO_STATUS["target"].clear()


def snapshot() -> dict[str, list[dict]]:
    with _lock:
        return {kind: list(items.values()) for kind, items in ECHO_STATUS.items()}


def _notify_config_errors() -> None:
    """Alert about configuration findings (errors only, de-bounced per code)."""
    from . import health_checks
    from .config import get_settings

    try:
        with session_factory()() as s:
            findings = health_checks.config_findings(s, get_settings())
    except Exception:
        return
    for finding in findings:
        if finding["severity"] != "error":
            continue
        notify.notify("config_error", f"Configuration check failed: {finding['message']}",
                      {"code": finding["code"], **finding.get("details", {})},
                      subject=finding["code"])


def echo_loop(interval_s: int, stop: threading.Event) -> None:
    """Background loop: echo every enabled source/target.

    The interval is re-read from the effective settings each tick (UI override
    wins over the ENV default). Roughly once an hour a retention purge removes
    expired seen_items; sources with `cache_refresh_s > 0` get their worklist
    snapshot refreshed so the cache is warm when a RIS goes down.
    """
    from . import cache, settings_service

    ticks = 0
    while not stop.is_set():
        try:
            with session_factory()() as s:
                sources = s.scalars(select(MwlSource).where(MwlSource.enabled.is_(True))).all()
                targets = s.scalars(select(PacsTarget).where(PacsTarget.enabled.is_(True))).all()
            for r in sources:
                echo_one("source", r)
            for r in targets:
                echo_one("target", r)
            for source_cfg in cache.sources_due_for_refresh():
                cache.refresh(source_cfg)
            ticks += 1
            if ticks % 10 == 0:
                _notify_config_errors()
            if ticks % 60 == 0:
                settings_service.purge_seen_items()
                cache.purge()
        except Exception:
            pass  # DB not ready yet — next tick retries
        try:
            wait_s = settings_service.get_int("echo_interval_s")
        except Exception:
            wait_s = interval_s
        stop.wait(wait_s)
