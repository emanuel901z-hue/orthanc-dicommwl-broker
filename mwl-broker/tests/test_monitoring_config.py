"""Die Alarmregeln und das Dashboard müssen zu den echten Metriken passen.

Eine Alarmregel auf einen Metriknamen, den es nicht gibt, schlägt nie an —
und das merkt man erst, wenn der Ausfall da ist. Dieser Test liest die
Monitoring-Dateien und vergleicht die Metriknamen mit `metrics.py`.
"""
import re
from pathlib import Path

import pytest
import yaml

BASE = Path(__file__).resolve().parents[2]
RULES = BASE / "deploy" / "monitoring" / "prometheus-rules.yml"
DASHBOARD = BASE / "deploy" / "monitoring" / "grafana-dashboard.json"


def _declared_metrics() -> set[str]:
    """Alle Metriknamen, die metrics.py erzeugt."""
    source = (Path(__file__).resolve().parents[1] / "mwl_broker" / "metrics.py").read_text()
    names = set(re.findall(r'"([a-z][a-z0-9_]+_total|mwl_[a-z0-9_]+)"', source))
    # Prometheus ergänzt _created für Counter
    return {n for n in names if n.startswith("mwl_")}


def test_rules_file_exists_and_parses():
    assert RULES.is_file(), f"missing {RULES}"
    data = yaml.safe_load(RULES.read_text())
    assert "groups" in data and data["groups"], "no rule groups"


def test_every_rule_has_the_expected_shape():
    data = yaml.safe_load(RULES.read_text())
    for group in data["groups"]:
        for rule in group["rules"]:
            assert rule.get("alert"), rule
            assert rule.get("expr"), rule
            assert rule.get("labels", {}).get("severity") in ("warning", "critical"), rule
            annotations = rule.get("annotations", {})
            assert annotations.get("summary"), rule
            assert annotations.get("description"), rule


def _expressions() -> str:
    """Nur die Ausdrücke — Kommentare nennen Dateinamen wie mwl_broker/metrics.py."""
    data = yaml.safe_load(RULES.read_text())
    return "\n".join(rule["expr"] for group in data["groups"] for rule in group["rules"])


def test_rules_only_use_metrics_that_exist():
    """Jede `mwl_*`-Metrik in den Regeln muss metrics.py kennen."""
    declared = _declared_metrics()
    used = set(re.findall(r"\bmwl_[a-z0-9_]+", _expressions()))
    # Histogramme liefern _bucket/_count/_sum, Counter zusätzlich _created
    suffixes = ("_bucket", "_count", "_sum", "_created")
    unknown = sorted(
        name for name in used
        if name not in declared
        and not any(name == d + s for d in declared for s in suffixes)
        and not any(name.startswith(d) for d in declared)
    )
    assert not unknown, f"rules use metrics that do not exist: {unknown}"


def test_rules_cover_the_important_failures():
    """Die Regeln müssen die Fälle abdecken, die im Runbook stehen."""
    text = RULES.read_text()
    for expected in ("MWLBrokerDown", "MWLSourceDown", "MWLTargetDown", "MWLSpoolFull",
                     "MWLSpoolDeadLetters", "MWLCertificateExpiring", "MWLConfigError",
                     "MWLNotifyFailing", "MWLMppsForwardFailing"):
        assert expected in text, f"{expected} is missing from the alert rules"
    # jede Regel verweist auf das Runbook oder erklärt sich selbst
    assert text.count("runbook:") >= 8


def test_dashboard_is_valid_and_uses_real_metrics():
    import json

    assert DASHBOARD.is_file(), f"missing {DASHBOARD}"
    dashboard = json.loads(DASHBOARD.read_text())
    assert dashboard.get("title"), "the dashboard needs a title"
    assert dashboard.get("panels"), "the dashboard has no panels"

    declared = _declared_metrics()
    suffixes = ("_bucket", "_count", "_sum", "_created")
    text = "\n".join(
        str(target.get("expr", ""))
        for panel in dashboard["panels"] for target in panel.get("targets", [])
    )
    used = set(re.findall(r"\bmwl_[a-z0-9_]+", text))
    unknown = sorted(
        name for name in used
        if name not in declared
        and not any(name == d + s for d in declared for s in suffixes)
        and not any(name.startswith(d) for d in declared)
    )
    assert not unknown, f"dashboard uses metrics that do not exist: {unknown}"

    for panel in dashboard["panels"]:
        assert panel.get("title"), panel
        assert panel.get("type"), panel
