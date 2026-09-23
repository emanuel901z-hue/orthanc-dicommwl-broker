"""Worklist cache: snapshot replacement, bounded stale fallback, housekeeping."""
from datetime import datetime, timedelta, timezone

from pydicom.dataset import Dataset

from mwl_broker import cache, settings_service
from mwl_broker.db import session_factory
from mwl_broker.models import MwlSource, WorklistCache


def _source(name="ris-a", stale_on_error=True, refresh_s=0, enabled=True) -> int:
    with session_factory()() as s:
        row = MwlSource(name=name, aet="RIS_A", host="127.0.0.1", port=1,
                        calling_aet="MWLBROKER", charset="ISO_IR 100",
                        cache_stale_on_error=stale_on_error, cache_refresh_s=refresh_s,
                        enabled=enabled)
        s.add(row)
        s.commit()
        return row.id


def _item(accession="ACC-1", patient="P1", status="SCHEDULED", station="CT_01",
          sps_id="SPS-1", study_uid="1.2.3") -> Dataset:
    ds = Dataset()
    ds.PatientID = patient
    ds.PatientName = "Mueller^Hans"
    ds.AccessionNumber = accession
    ds.StudyInstanceUID = study_uid
    sps = Dataset()
    sps.ScheduledProcedureStepID = sps_id
    sps.ScheduledProcedureStepStatus = status
    sps.ScheduledStationAETitle = station
    sps.Modality = "CT"
    ds.ScheduledProcedureStepSequence = [sps]
    return ds


def _age_cache(source_id: int, seconds: int) -> None:
    with session_factory()() as s:
        for row in s.query(WorklistCache).filter_by(source_id=source_id):
            row.fetched_at = datetime.now(timezone.utc) - timedelta(seconds=seconds)
        s.commit()


# ── snapshot semantics ─────────────────────────────────────────────────


def test_store_snapshot_indexes_metadata():
    source_id = _source()

    assert cache.store_snapshot(source_id, [_item(), _item(accession="ACC-2", sps_id="SPS-2")]) == 2

    rows = {r["accession"]: r for r in cache.items()}
    assert set(rows) == {"ACC-1", "ACC-2"}
    assert rows["ACC-1"]["sps_status"] == "SCHEDULED"
    assert rows["ACC-1"]["modality"] == "CT"
    assert rows["ACC-1"]["station_aet"] == "CT_01"
    # patient identifiers are never exposed through the API view
    assert "patient" not in str(rows["ACC-1"]).lower()
    assert "Mueller" not in str(rows)


def test_snapshot_is_replaced_not_merged():
    """Medavis semantics: an order that left the RIS worklist must disappear."""
    source_id = _source()
    cache.store_snapshot(source_id, [_item(), _item(accession="ACC-2", sps_id="SPS-2")])

    # the RIS now only returns ACC-1 (ACC-2 was completed/cancelled there)
    cache.store_snapshot(source_id, [_item()])

    assert [row["accession"] for row in cache.items()] == ["ACC-1"]


def test_snapshot_replacement_is_idempotent():
    source_id = _source()
    cache.store_snapshot(source_id, [_item()])
    cache.store_snapshot(source_id, [_item()])

    assert len(cache.items()) == 1


def test_max_items_caps_the_snapshot():
    settings_service.set_value("cache_max_items", "2")
    source_id = _source()

    stored = cache.store_snapshot(source_id, [
        _item(accession=f"ACC-{i}", sps_id=f"SPS-{i}") for i in range(5)
    ])

    assert stored == 2
    assert len(cache.items()) == 2


def test_store_is_a_noop_when_disabled():
    settings_service.set_value("cache_enabled", "false")
    source_id = _source()

    assert cache.store_snapshot(source_id, [_item()]) == 0
    assert cache.items() == []


# ── stale serving ──────────────────────────────────────────────────────


def test_stale_answers_are_served_within_the_window():
    source_id = _source()
    cache.store_snapshot(source_id, [_item()])

    answers, age = cache.stale_answers(source_id)

    assert len(answers) == 1
    assert answers[0].AccessionNumber == "ACC-1"
    assert answers[0].PatientName == "Mueller^Hans"  # payload round-trips
    assert age is not None and age <= 5


def test_stale_answers_expire_after_the_window():
    settings_service.set_value("cache_stale_max_s", "60")
    source_id = _source()
    cache.store_snapshot(source_id, [_item()])
    _age_cache(source_id, 120)

    answers, age = cache.stale_answers(source_id)

    assert answers == [] and age is None


def test_stale_serving_can_be_disabled_globally():
    settings_service.set_value("cache_enabled", "false")
    source_id = _source()
    settings_service.set_value("cache_enabled", "true")
    cache.store_snapshot(source_id, [_item()])
    settings_service.set_value("cache_enabled", "false")

    assert cache.stale_answers(source_id) == ([], None)


def test_stale_serving_can_be_disabled_per_source():
    source_id = _source(stale_on_error=False)
    cache.store_snapshot(source_id, [_item()])

    assert cache.stale_answers(source_id) == ([], None)


def test_stale_window_of_zero_disables_serving():
    settings_service.set_value("cache_stale_max_s", "0")
    source_id = _source()
    cache.store_snapshot(source_id, [_item()])

    assert cache.stale_answers(source_id) == ([], None)


def test_finished_steps_are_never_served_from_the_cache():
    """A stale snapshot must not resurrect a completed step."""
    source_id = _source()
    cache.store_snapshot(source_id, [
        _item(accession="ACC-OPEN"),
        _item(accession="ACC-DONE", sps_id="SPS-2", status="COMPLETED"),
        _item(accession="ACC-STOP", sps_id="SPS-3", status="DISCONTINUED"),
    ])

    answers, _age = cache.stale_answers(source_id)

    assert [ds.AccessionNumber for ds in answers] == ["ACC-OPEN"]


def test_finished_steps_can_be_served_when_explicitly_allowed():
    settings_service.set_value("cache_hide_completed", "false")
    source_id = _source()
    cache.store_snapshot(source_id, [_item(status="COMPLETED")])

    answers, _age = cache.stale_answers(source_id)

    assert len(answers) == 1


def test_empty_cache_returns_nothing():
    assert cache.stale_answers(_source()) == ([], None)


def test_corrupt_payload_does_not_break_the_query():
    source_id = _source()
    cache.store_snapshot(source_id, [_item()])
    with session_factory()() as s:
        s.query(WorklistCache).filter_by(source_id=source_id).one().payload = {"json": "{broken"}
        s.commit()

    assert cache.stale_answers(source_id) == ([], None)


# ── stats, items, clear, purge ─────────────────────────────────────────


def test_stats_report_state_per_source():
    fresh = _source("ris-fresh")
    old = _source("ris-old")
    empty = _source("ris-empty")
    settings_service.set_value("cache_stale_max_s", "60")
    cache.store_snapshot(fresh, [_item()])
    cache.store_snapshot(old, [_item()])
    _age_cache(old, 300)

    by_name = {row["source_name"]: row for row in cache.stats()}

    assert by_name["ris-fresh"]["state"] == cache.STATE_AVAILABLE
    assert by_name["ris-fresh"]["entries"] == 1
    assert by_name["ris-fresh"]["stale_on_error"] is True
    assert by_name["ris-old"]["state"] == cache.STATE_EXPIRED
    assert by_name["ris-empty"]["state"] == cache.STATE_EMPTY
    assert by_name["ris-empty"]["age_s"] is None
    assert empty  # silence linters


def test_items_can_be_filtered_by_source():
    first = _source("ris-1")
    second = _source("ris-2")
    cache.store_snapshot(first, [_item(accession="ACC-1")])
    cache.store_snapshot(second, [_item(accession="ACC-2", sps_id="SPS-2")])

    assert [row["accession"] for row in cache.items(source_id=first)] == ["ACC-1"]
    assert len(cache.items()) == 2
    assert cache.items(limit=1)[0]["source_name"] in {"ris-1", "ris-2"}


def test_clear_removes_everything_or_one_source():
    first = _source("ris-1")
    second = _source("ris-2")
    cache.store_snapshot(first, [_item()])
    cache.store_snapshot(second, [_item()])

    assert cache.clear(first) == 1
    assert [row["source_id"] for row in cache.items()] == [second]

    assert cache.clear() == 1
    assert cache.items() == []


def test_purge_drops_snapshots_that_can_never_be_served_again():
    settings_service.set_value("cache_stale_max_s", "60")
    source_id = _source()
    cache.store_snapshot(source_id, [_item()])
    _age_cache(source_id, 3600)

    assert cache.purge() == 1
    assert cache.items() == []


def test_purge_keeps_recent_snapshots():
    source_id = _source()
    cache.store_snapshot(source_id, [_item()])

    assert cache.purge() == 0
    assert len(cache.items()) == 1


# ── background refresh ─────────────────────────────────────────────────


def test_sources_due_for_refresh_respects_the_interval():
    due = _source("ris-due", refresh_s=60)
    off = _source("ris-off", refresh_s=0)
    _source("ris-disabled", refresh_s=60, enabled=False)

    names = [cfg.name for cfg in cache.sources_due_for_refresh()]

    assert names == ["ris-due"]
    assert off and due


def test_sources_due_for_refresh_skips_fresh_snapshots():
    source_id = _source("ris-warm", refresh_s=3600)
    cache.store_snapshot(source_id, [_item()])

    assert cache.sources_due_for_refresh() == []


def test_refresh_stores_a_snapshot(monkeypatch):
    from mwl_broker import upstream
    from mwl_broker.upstream import SourceCfg

    source_id = _source("ris-refresh")
    cfg = SourceCfg(id=source_id, name="ris-refresh", aet="RIS_A", host="127.0.0.1",
                    port=1, calling_aet="MWLBROKER", charset="ISO_IR 100", timeout_s=5)
    monkeypatch.setattr(upstream, "query_source", lambda src, ident: [_item()])

    assert cache.refresh(cfg) == 1
    assert [row["accession"] for row in cache.items()] == ["ACC-1"]


def test_refresh_failure_is_silent(monkeypatch):
    from mwl_broker import upstream
    from mwl_broker.upstream import SourceCfg

    source_id = _source("ris-broken")
    cfg = SourceCfg(id=source_id, name="ris-broken", aet="RIS_A", host="127.0.0.1",
                    port=1, calling_aet="MWLBROKER", charset="ISO_IR 100", timeout_s=5)

    def boom(_src, _ident):
        raise ConnectionError("down")

    monkeypatch.setattr(upstream, "query_source", boom)

    assert cache.refresh(cfg) == 0
    assert cache.items() == []


def test_duplicate_dedupe_keys_never_reach_the_bulk_upsert(monkeypatch):
    """A foreign RIS can send the same (patient, accession, step ID) twice.

    The DVTk RIS emulator does exactly that: one response carries several
    Scheduled Procedure Steps, or different orders arrive without accession and
    step ID. The bulk upsert may only touch a row once — PostgreSQL aborted the
    whole statement (`CardinalityViolation … cannot affect row a second time`)
    and the snapshot was lost, although the live answer had been fine. Found by
    the DVTk RIS emulator interop test; the guard is asserted here because
    SQLite (the test database) tolerates the duplicate.
    """
    source_id = _source()
    captured: list[list[dict]] = []
    real_upsert = cache.db.upsert

    def spy(session, model, rows, **kwargs):
        captured.append(list(rows))
        return real_upsert(session, model, rows, **kwargs)

    monkeypatch.setattr(cache.db, "upsert", spy)

    stored = cache.store_snapshot(source_id, [
        _item(),                                       # P1 / ACC-1 / SPS-1
        _item(),                                       # same key again
        _item(patient="P2", accession="", sps_id=""),  # order without accession
        _item(patient="P2", accession="", sps_id=""),  # same key again
        _item(accession="ACC-2", sps_id="SPS-2"),
    ])

    keys = [row["dedupe_key"] for row in captured[0]]
    assert len(keys) == len(set(keys)), "duplicate keys would abort the upsert"
    assert stored == 3
    assert sorted(row["accession"] for row in cache.items()) == ["", "ACC-1", "ACC-2"]
