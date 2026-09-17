"""Circuit breaker state machine (unit, DB-backed)."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from mwl_broker import breaker, settings_service
from mwl_broker.db import session_factory
from mwl_broker.models import MwlSource, SourceBreaker


def _seed_source(name="ris-a") -> int:
    with session_factory()() as s:
        row = MwlSource(name=name, aet="RIS_A", host="127.0.0.1", port=1,
                        calling_aet="MWLBROKER", charset="ISO_IR 100")
        s.add(row)
        s.commit()
        return row.id


def _row(source_id: int) -> SourceBreaker | None:
    with session_factory()() as s:
        return s.get(SourceBreaker, source_id)


def test_unknown_source_is_available():
    assert breaker.is_available(4242) is True  # no row → closed


def test_failures_below_threshold_keep_the_source_available():
    settings_service.set_value("breaker_fail_threshold", "3")
    source_id = _seed_source()

    breaker.record_failure(source_id, "timeout")
    breaker.record_failure(source_id, "timeout")

    assert breaker.is_available(source_id) is True
    row = _row(source_id)
    assert row.state == breaker.STATE_CLOSED
    assert row.failures == 2
    assert row.last_error == "timeout"


def test_threshold_opens_the_breaker():
    settings_service.set_value("breaker_fail_threshold", "2")
    settings_service.set_value("breaker_open_seconds", "60")
    source_id = _seed_source()

    breaker.record_failure(source_id, "connection refused")
    assert breaker.is_available(source_id) is True
    breaker.record_failure(source_id, "connection refused")

    assert breaker.is_available(source_id) is False
    row = _row(source_id)
    assert row.state == breaker.STATE_OPEN
    assert row.open_until is not None
    assert row.last_error == "connection refused"


def test_expired_open_window_probes_half_open():
    settings_service.set_value("breaker_fail_threshold", "1")
    settings_service.set_value("breaker_open_seconds", "60")
    source_id = _seed_source()
    breaker.record_failure(source_id, "boom")
    assert breaker.is_available(source_id) is False

    # simulate the cooldown having elapsed
    with session_factory()() as s:
        row = s.get(SourceBreaker, source_id)
        row.open_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        s.commit()

    assert breaker.is_available(source_id) is True
    assert _row(source_id).state == breaker.STATE_HALF_OPEN


def test_success_closes_the_breaker_and_resets_failures():
    settings_service.set_value("breaker_fail_threshold", "1")
    source_id = _seed_source()
    breaker.record_failure(source_id, "boom")
    assert _row(source_id).state == breaker.STATE_OPEN

    breaker.record_success(source_id)

    row = _row(source_id)
    assert row.state == breaker.STATE_CLOSED
    assert row.failures == 0
    assert row.open_until is None
    assert row.last_error == ""
    assert breaker.is_available(source_id) is True


def test_failure_in_half_open_reopens_immediately():
    settings_service.set_value("breaker_fail_threshold", "1")
    settings_service.set_value("breaker_open_seconds", "60")
    source_id = _seed_source()
    breaker.record_failure(source_id, "boom")
    with session_factory()() as s:
        row = s.get(SourceBreaker, source_id)
        row.state = breaker.STATE_HALF_OPEN
        row.failures = 0
        s.commit()

    breaker.record_failure(source_id, "still down")

    row = _row(source_id)
    assert row.state == breaker.STATE_OPEN
    assert breaker.is_available(source_id) is False


def test_reset_and_forget_remove_the_state():
    settings_service.set_value("breaker_fail_threshold", "1")
    source_id = _seed_source()
    breaker.record_failure(source_id, "boom")
    assert _row(source_id) is not None

    breaker.reset(source_id)

    assert _row(source_id) is None
    assert breaker.is_available(source_id) is True

    breaker.record_failure(source_id, "boom")
    breaker.forget(source_id)  # called when a source is deleted
    assert _row(source_id) is None


def test_snapshot_reports_state_and_retry_window():
    settings_service.set_value("breaker_fail_threshold", "1")
    settings_service.set_value("breaker_open_seconds", "30")
    healthy = _seed_source("ris-ok")
    broken = _seed_source("ris-down")
    breaker.record_failure(broken, "refused")

    snap = breaker.snapshot()

    # a healthy source needs no row — "missing" means closed
    assert healthy not in snap
    assert snap[broken]["state"] == breaker.STATE_OPEN
    assert snap[broken]["name"] == "ris-down"
    assert snap[broken]["failures"] == 1
    assert 0 < snap[broken]["retry_in_s"] <= 30
    assert snap[broken]["last_error"] == "refused"

    # after a recovery the row stays, but reports closed
    breaker.record_success(broken)
    assert breaker.snapshot()[broken]["state"] == breaker.STATE_CLOSED
    assert breaker.snapshot()[broken]["retry_in_s"] is None


def test_breaker_state_is_published_as_metric():
    from prometheus_client import REGISTRY

    settings_service.set_value("breaker_fail_threshold", "1")
    source_id = _seed_source("ris-metric")
    breaker.record_failure(source_id, "boom")

    assert REGISTRY.get_sample_value(
        "mwl_upstream_breaker_state", {"source": "ris-metric"}
    ) == 2  # open

    breaker.record_success(source_id)
    assert REGISTRY.get_sample_value(
        "mwl_upstream_breaker_state", {"source": "ris-metric"}
    ) == 0  # closed


def test_breaker_state_survives_a_new_session():
    """The state is persisted, so a broker restart keeps skipping a dead source."""
    settings_service.set_value("breaker_fail_threshold", "1")
    source_id = _seed_source()
    breaker.record_failure(source_id, "boom")

    # fresh engine/session (simulates the restart)
    from mwl_broker import db

    db.reset_for_tests()
    assert breaker.is_available(source_id) is False
    with session_factory()() as s:
        assert s.scalars(select(SourceBreaker)).all()[0].state == breaker.STATE_OPEN
