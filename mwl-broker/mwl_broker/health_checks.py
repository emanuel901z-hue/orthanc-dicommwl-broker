"""Configuration consistency checks ("broker health").

The typical outage in production is a misconfiguration, not a crash: no
default target, a rule pointing at a disabled node, a dead source nobody
noticed. These checks surface that as actionable findings.

Findings carry a stable `code` — the UI translates it (i18n) and falls back
to the English `message`. `entity` points at the affected object so the UI can
deep-link into the right form.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from . import breaker, echo, metrics, settings_service, spool
from .models import MwlSource, PacsTarget, QueryLog, RoutingRule, TransformRule

log = logging.getLogger("mwl_broker.health")

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def _finding(code: str, severity: str, message: str, entity: dict | None = None,
             details: dict | None = None) -> dict:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "entity": entity or {},
        "details": details or {},
    }


def config_findings(session, settings) -> list[dict]:
    """Run every consistency check and return findings (sorted by severity)."""
    sources = session.scalars(select(MwlSource).order_by(MwlSource.id)).all()
    targets = session.scalars(select(PacsTarget).order_by(PacsTarget.id)).all()
    rules = session.scalars(select(RoutingRule).order_by(RoutingRule.id)).all()
    transforms = session.scalars(select(TransformRule).order_by(TransformRule.id)).all()

    by_id_src = {s.id: s for s in sources}
    by_id_tgt = {t.id: t for t in targets}
    findings: list[dict] = []

    # ── store routing ──────────────────────────────────────────────────────
    defaults = [t for t in targets if t.is_default and t.enabled]
    if not defaults:
        findings.append(_finding(
            "no_default_target", "error",
            "No enabled default target: stores without a matching routing rule "
            "are rejected.",
        ))
    if len(defaults) > 1:
        findings.append(_finding(
            "multiple_default_targets", "error",
            "More than one target is marked as default — which one is used is "
            "undefined.",
            details={"count": len(defaults), "names": [t.name for t in defaults]},
        ))

    # ── rules ──────────────────────────────────────────────────────────────
    for rule in rules:
        if not rule.enabled:
            continue
        src, tgt = by_id_src.get(rule.source_id), by_id_tgt.get(rule.target_id)
        if src is not None and not src.enabled:
            findings.append(_finding(
                "rule_source_disabled", "warning",
                f"Rule {rule.id} points at the disabled source '{src.name}' and "
                "never matches.",
                entity={"kind": "rule", "id": rule.id, "name": f"{src.name} → ?"},
            ))
        if tgt is not None and not tgt.enabled:
            findings.append(_finding(
                "rule_target_disabled", "warning",
                f"Rule {rule.id} forwards to the disabled target '{tgt.name}'.",
                entity={"kind": "rule", "id": rule.id, "name": f"? → {tgt.name}"},
            ))

    # ── modify rules ───────────────────────────────────────────────────────
    for rule in transforms:
        if not rule.enabled or rule.target_id is None:
            continue
        tgt = by_id_tgt.get(rule.target_id)
        if tgt is None or not tgt.enabled:
            findings.append(_finding(
                "transform_target_disabled", "warning",
                f"Modify rule '{rule.name}' only applies to a target that is "
                "disabled or missing — it has no effect.",
                entity={"kind": "transform", "id": rule.id, "name": rule.name},
            ))

    # ── sources ────────────────────────────────────────────────────────────
    if sources and not any(s.enabled for s in sources):
        findings.append(_finding(
            "no_enabled_source", "warning",
            "All upstream sources are disabled — every worklist query returns "
            "an empty list.",
        ))

    echo_state = echo.snapshot().get("source", [])
    ok_ids = {e["id"] for e in echo_state if e.get("ok")}
    if sources and any(s.enabled for s in sources) and not ok_ids:
        findings.append(_finding(
            "no_working_source", "warning",
            "No upstream source answered its last C-ECHO — check the endpoints.",
            details={"checked": len([s for s in sources if s.enabled])},
        ))

    breakers = breaker.snapshot()
    for source_id, state in breakers.items():
        if state["state"] == breaker.STATE_OPEN:
            findings.append(_finding(
                "source_breaker_open", "warning",
                f"Source '{state['name']}' is temporarily skipped after repeated "
                f"failures (retry in {state['retry_in_s']}s).",
                entity={"kind": "source", "id": source_id, "name": state["name"]},
                details={"retry_in_s": state["retry_in_s"], "failures": state["failures"],
                         "last_error": state["last_error"]},
            ))

    # ── C-STORE spool ──────────────────────────────────────────────────────
    spool_state = spool.stats()
    if spool_state["dead"]:
        findings.append(_finding(
            "spool_dead_letters", "error",
            f"{spool_state['dead']} spooled instance(s) could not be delivered and "
            "gave up — retry them after fixing the target or discard them.",
            details={"count": spool_state["dead"]},
        ))
    if spool_state["capacity"]["full"]:
        findings.append(_finding(
            "spool_full", "error",
            "The C-STORE spool is full — new instances that cannot be forwarded "
            "are refused instead of queued.",
            details={
                "items": spool_state["capacity"]["items"],
                "max_items": spool_state["capacity"]["max_items"],
                "bytes": spool_state["capacity"]["bytes"],
                "max_bytes": spool_state["capacity"]["max_bytes"],
            },
        ))
    if spool_state["open"] and (spool_state["oldest_age_s"] or 0) > 900:
        findings.append(_finding(
            "spool_backlog", "warning",
            f"{spool_state['open']} instance(s) are waiting in the spool "
            f"(oldest {int((spool_state['oldest_age_s'] or 0) / 60)} min) — check the "
            "target PACS.",
            details={
                "open": spool_state["open"],
                "oldest_minutes": int((spool_state["oldest_age_s"] or 0) / 60),
            },
        ))

    # ── worklist cache ─────────────────────────────────────────────────────
    stale_since = datetime.now(timezone.utc) - timedelta(minutes=5)
    recent = session.scalars(
        select(QueryLog).where(QueryLog.ts >= stale_since).order_by(QueryLog.ts.desc())
    ).all()
    stale_sources = sorted({
        name for row in recent for name in (row.served_stale or [])
    })
    if stale_sources:
        findings.append(_finding(
            "cache_serving_stale", "warning",
            "Worklist queries were answered from the cache because these sources "
            f"failed: {', '.join(stale_sources)}.",
            details={"sources": ", ".join(stale_sources)},
        ))

    # ── global settings ────────────────────────────────────────────────────
    if not settings_service.get_aets():
        findings.append(_finding(
            "aet_whitelist_empty", "info",
            "No calling-AE-title allowlist is configured: any AET may query and "
            "store. Restrict it for production.",
        ))

    broker_aet = (settings.broker_aet or "").upper()
    for tgt in targets:
        if tgt.enabled and (tgt.aet or "").upper() == broker_aet:
            findings.append(_finding(
                "broker_aet_collision", "warning",
                f"Target '{tgt.name}' uses the broker's own AE title "
                f"({broker_aet}) — forwarding could loop back into the broker.",
                entity={"kind": "target", "id": tgt.id, "name": tgt.name},
            ))

    findings.sort(key=lambda f: (SEVERITY_ORDER.get(f["severity"], 9), f["code"]))
    _publish(findings)
    return findings


def summary(findings: list[dict]) -> dict:
    return {
        severity: len([f for f in findings if f["severity"] == severity])
        for severity in ("error", "warning", "info")
    }


def _publish(findings: list[dict]) -> None:
    counts = summary(findings)
    for severity, count in counts.items():
        metrics.CONFIG_FINDINGS.labels(severity=severity).set(count)
