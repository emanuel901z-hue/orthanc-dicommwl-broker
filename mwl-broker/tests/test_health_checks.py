"""Configuration consistency checks — one test per finding code."""
from mwl_broker import breaker, health_checks, settings_service
from mwl_broker.config import Settings
from mwl_broker.db import session_factory
from mwl_broker.models import MwlSource, PacsTarget, RoutingRule, TransformRule

SETTINGS = Settings(broker_aet="MWLBROKER")


def _source(name="ris-a", enabled=True, aet="RIS_A") -> int:
    with session_factory()() as s:
        row = MwlSource(name=name, aet=aet, host="127.0.0.1", port=1,
                        calling_aet="MWLBROKER", charset="ISO_IR 100", enabled=enabled)
        s.add(row)
        s.commit()
        return row.id


def _target(name="pacs", is_default=True, enabled=True, aet="PACS") -> int:
    with session_factory()() as s:
        row = PacsTarget(name=name, aet=aet, host="127.0.0.1", port=104,
                         calling_aet="MWLBROKER", is_default=is_default, enabled=enabled)
        s.add(row)
        s.commit()
        return row.id


def _rule(source_id: int, target_id: int, enabled=True) -> None:
    with session_factory()() as s:
        s.add(RoutingRule(source_id=source_id, target_id=target_id, enabled=enabled))
        s.commit()


def _transform(name="t", target_id=None, enabled=True) -> None:
    with session_factory()() as s:
        s.add(TransformRule(name=name, target_id=target_id, enabled=enabled,
                            operations=[{"op": "remove", "tag": "PatientAddress"}]))
        s.commit()


def _findings(settings=SETTINGS) -> list[dict]:
    with session_factory()() as s:
        return health_checks.config_findings(s, settings)


def _codes(findings) -> set[str]:
    return {f["code"] for f in findings}


def _healthy_echo(monkeypatch, source_id: int) -> None:
    monkeypatch.setattr(
        health_checks.echo, "snapshot",
        lambda: {"source": [{"id": source_id, "ok": True}], "target": []},
    )


def test_missing_default_target_is_an_error():
    _source()  # no target at all

    findings = _findings()

    assert "no_default_target" in _codes(findings)
    assert next(f for f in findings if f["code"] == "no_default_target")["severity"] == "error"


def test_disabled_default_target_counts_as_missing():
    _target(is_default=True, enabled=False)

    assert "no_default_target" in _codes(_findings())


def test_multiple_default_targets_are_an_error():
    _target("pacs-a", is_default=True)
    _target("pacs-b", is_default=True)

    finding = next(f for f in _findings() if f["code"] == "multiple_default_targets")

    assert finding["severity"] == "error"
    assert finding["details"]["count"] == 2
    assert set(finding["details"]["names"]) == {"pacs-a", "pacs-b"}


def test_rule_on_disabled_source_is_reported():
    src = _source(enabled=False)
    tgt = _target()
    _rule(src, tgt)

    finding = next(f for f in _findings() if f["code"] == "rule_source_disabled")

    assert finding["severity"] == "warning"
    assert finding["entity"]["kind"] == "rule"


def test_rule_on_disabled_target_is_reported():
    src = _source()
    tgt = _target(enabled=False)
    _rule(src, tgt)

    assert "rule_target_disabled" in _codes(_findings())


def test_disabled_rule_is_not_reported():
    src = _source(enabled=False)
    tgt = _target()
    _rule(src, tgt, enabled=False)

    assert "rule_source_disabled" not in _codes(_findings())


def test_transform_scoped_to_disabled_target_is_reported():
    tgt = _target(enabled=False)
    _transform(target_id=tgt)

    finding = next(f for f in _findings() if f["code"] == "transform_target_disabled")

    assert finding["entity"]["kind"] == "transform"
    assert finding["entity"]["name"] == "t"


def test_all_sources_disabled_is_reported():
    _source(enabled=False)
    _target()

    assert "no_enabled_source" in _codes(_findings())


def test_no_working_source_is_reported_until_an_echo_succeeds(monkeypatch):
    src = _source()
    _target()

    assert "no_working_source" in _codes(_findings())

    _healthy_echo(monkeypatch, src)
    assert "no_working_source" not in _codes(_findings())


def test_empty_aet_whitelist_is_an_info():
    _source()
    _target()

    finding = next(f for f in _findings() if f["code"] == "aet_whitelist_empty")
    assert finding["severity"] == "info"

    settings_service.set_value("allowed_calling_aets", "CT_01")
    assert "aet_whitelist_empty" not in _codes(_findings())


def test_broker_aet_collision_is_reported():
    _target(aet="MWLBROKER")  # same AE title as the broker itself

    finding = next(f for f in _findings() if f["code"] == "broker_aet_collision")

    assert finding["entity"]["kind"] == "target"
    assert "MWLBROKER" in finding["message"]


def test_open_breaker_is_reported():
    settings_service.set_value("breaker_fail_threshold", "1")
    settings_service.set_value("breaker_open_seconds", "45")
    src = _source()
    _target()
    breaker.record_failure(src, "connection refused")

    finding = next(f for f in _findings() if f["code"] == "source_breaker_open")

    assert finding["severity"] == "warning"
    assert finding["entity"]["id"] == src
    assert 0 < finding["details"]["retry_in_s"] <= 45


def test_stale_serving_is_reported(monkeypatch):
    from datetime import datetime, timezone

    from mwl_broker.db import session_factory
    from mwl_broker.models import QueryLog

    src = _source()
    _target()

    assert "cache_serving_stale" not in _codes(_findings())

    with session_factory()() as s:
        s.add(QueryLog(calling_aet="CT_01", answers=2, per_source={"ris-a": 2},
                       duration_ms=12, status="partial", served_stale=["ris-a"],
                       ts=datetime.now(timezone.utc)))
        s.commit()

    finding = next(f for f in _findings() if f["code"] == "cache_serving_stale")
    assert finding["severity"] == "warning"
    assert "ris-a" in finding["message"]
    assert finding["details"]["sources"] == "ris-a"
    assert src  # silence linters


def test_old_stale_serving_is_not_reported():
    from datetime import datetime, timedelta, timezone

    from mwl_broker.db import session_factory
    from mwl_broker.models import QueryLog

    _source()
    _target()
    with session_factory()() as s:
        s.add(QueryLog(calling_aet="CT_01", answers=1, per_source={"ris-a": 1},
                       duration_ms=9, status="partial", served_stale=["ris-a"],
                       ts=datetime.now(timezone.utc) - timedelta(hours=2)))
        s.commit()

    assert "cache_serving_stale" not in _codes(_findings())


def test_spool_dead_letters_are_an_error():
    from pydicom.dataset import Dataset
    from pydicom.uid import CTImageStorage

    from mwl_broker import spool

    _source()
    target = _target()
    ds = Dataset()
    ds.SOPClassUID = CTImageStorage
    ds.SOPInstanceUID = "1.2.3"
    spool.enqueue(ds, None, target, "pacs", "boom")
    from mwl_broker.db import session_factory
    from mwl_broker.models import StoreSpool

    with session_factory()() as s:
        s.get(StoreSpool, 1).status = "dead"
        s.commit()

    finding = next(f for f in _findings() if f["code"] == "spool_dead_letters")
    assert finding["severity"] == "error"
    assert finding["details"]["count"] == 1


def test_spool_backlog_is_a_warning():
    from datetime import datetime, timedelta, timezone

    from pydicom.dataset import Dataset
    from pydicom.uid import CTImageStorage

    from mwl_broker import spool
    from mwl_broker.db import session_factory
    from mwl_broker.models import StoreSpool

    _source()
    target = _target()
    ds = Dataset()
    ds.SOPClassUID = CTImageStorage
    ds.SOPInstanceUID = "1.2.3"
    spool.enqueue(ds, None, target, "pacs", "boom")
    with session_factory()() as s:
        s.get(StoreSpool, 1).created_at = datetime.now(timezone.utc) - timedelta(hours=1)
        s.commit()

    finding = next(f for f in _findings() if f["code"] == "spool_backlog")
    assert finding["severity"] == "warning"
    assert finding["details"]["oldest_minutes"] >= 59


def test_spool_full_is_an_error():
    from pydicom.dataset import Dataset
    from pydicom.uid import CTImageStorage

    from mwl_broker import settings_service, spool

    _source()
    target = _target()
    settings_service.set_value("spool_max_items", "1")
    ds = Dataset()
    ds.SOPClassUID = CTImageStorage
    ds.SOPInstanceUID = "1.2.3"
    spool.enqueue(ds, None, target, "pacs", "boom")

    finding = next(f for f in _findings() if f["code"] == "spool_full")
    assert finding["severity"] == "error"
    assert finding["details"]["max_items"] == 1


def test_healthy_spool_reports_nothing():
    _source()
    _target()

    codes = _codes(_findings())

    assert not {"spool_dead_letters", "spool_backlog", "spool_full"} & codes


def test_tls_findings_are_absent_when_unused():
    _source()
    _target()
    assert not {"tls_certificate_expiring", "tls_configuration_incomplete",
                "tls_verification_disabled"} & _codes(_findings())


def test_tls_expiring_certificate_is_a_warning(tmp_path):
    from mwl_broker import settings_service, tls

    _source()
    _target()
    settings_service.set_value("tls_dir", str(tmp_path))
    tls.reset_for_tests()
    generated = tls.generate_self_signed("broker.local", 10, filename="soon")
    settings_service.set_value("tls_inbound_cert_file", generated["certificate_path"])

    finding = next(f for f in _findings() if f["code"] == "tls_certificate_expiring")
    assert finding["severity"] == "warning"
    assert finding["details"]["days_left"] <= 10


def test_tls_incomplete_configuration_is_an_error():
    from mwl_broker import settings_service, tls

    _source()
    _target()
    settings_service.set_value("tls_inbound_enabled", "true")
    settings_service.set_value("tls_inbound_cert_file", "/nonexistent/broker.crt")
    tls.reset_for_tests()

    codes = _codes(_findings())
    assert "tls_file_unusable" in codes
    assert "tls_configuration_incomplete" in codes


def test_tls_verification_off_is_reported():
    from mwl_broker import settings_service, tls

    _source()
    _target()
    settings_service.set_value("tls_outbound_verify", "false")
    tls.reset_for_tests()

    finding = next(f for f in _findings() if f["code"] == "tls_verification_disabled")
    assert finding["severity"] == "warning"


def test_findings_are_sorted_by_severity_and_summarised():
    _source(enabled=False)                        # warning: no_enabled_source
    _transform(target_id=_target(enabled=False))  # error: no_default_target
    findings = _findings()

    severities = [f["severity"] for f in findings]
    assert severities == sorted(severities, key=lambda s: {"error": 0, "warning": 1, "info": 2}[s])

    summary = health_checks.summary(findings)
    assert summary == {"error": 1, "warning": 2, "info": 1}
    assert sum(summary.values()) == len(findings)
    assert severities[0] == "error"


def test_findings_are_published_as_metrics():
    from prometheus_client import REGISTRY

    _source()  # no default target → one error

    _findings()

    assert REGISTRY.get_sample_value("mwl_config_findings", {"severity": "error"}) == 1
