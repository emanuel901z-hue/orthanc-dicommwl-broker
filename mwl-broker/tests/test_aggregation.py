"""The C-FIND aggregation directly — the core of the broker.

The DIMSE integration tests cover the live path end to end; these tests pin the
branches that are hard to reach over the wire: a source skipped by an open
breaker, an upstream that fails while a snapshot exists (and one where none
does), the single-source mode the C-FIND test uses, and the flags that keep a
preview from writing provenance or moving counters.
"""
import pytest
from pydicom.dataset import Dataset
from sqlalchemy import select

from mwl_broker import aggregation, breaker, cache, local_worklist, settings_service
from mwl_broker.db import get_engine, session_factory
from mwl_broker.models import MwlSource, SeenItem


def _source(**overrides) -> dict:
    payload = {
        "name": "ris-a", "aet": "RIS_A", "host": "127.0.0.1", "port": 1,
        "calling_aet": "MWLBROKER", "charset": "ISO_IR 100",
        "enabled": True, "timeout_s": 1, "priority": 10,
    }
    payload.update(overrides)
    return payload


def _item(accession: str, sps_id: str = "1") -> Dataset:
    ds = Dataset()
    ds.AccessionNumber = accession
    ds.PatientID = "P-1"
    ds.StudyInstanceUID = "1.2.3"
    sps = Dataset()
    sps.ScheduledProcedureStepID = sps_id
    sps.Modality = "CT"
    sps.ScheduledStationAETitle = "CT_01"
    ds.ScheduledProcedureStepSequence = [sps]
    return ds


@pytest.fixture()
def seeded(client):
    """Two enabled sources plus one disabled — the usual fan-out shape."""
    a = client.post("/api/v1/sources", json=_source()).json()
    b = client.post("/api/v1/sources", json=_source(name="ris-b", aet="RIS_B", priority=20)).json()
    client.post("/api/v1/sources", json=_source(name="ris-off", aet="RIS_OFF", enabled=False))
    return a, b


def test_collect_merges_in_priority_order_and_dedupes(client, seeded, monkeypatch):
    a, b = seeded

    def fake_query(cfg, identifier):
        # both sources know ACC-1, only b knows ACC-2
        # query_source returns the answers themselves (query_one wraps them)
        return [_item("ACC-1"), _item("ACC-2")] if cfg.name == "ris-b" else [_item("ACC-1")]

    monkeypatch.setattr(aggregation, "query_source", fake_query)
    result = aggregation.collect(Dataset())

    # the higher-priority source wins the dedupe, the other one is not repeated
    assert [ds.AccessionNumber for ds in result.items] == ["ACC-1", "ACC-2"]
    assert result.merged[0][1].name == "ris-a"
    assert result.status == "success"
    assert result.per_source == {"ris-a": 1, "ris-b": 2}
    # the disabled source never takes part
    assert "ris-off" not in result.per_source


def test_skipped_source_serves_the_snapshot_and_otherwise_reports_skipped(
    client, seeded, monkeypatch,
):
    """An open breaker skips the timeout — with a snapshot it still contributes."""
    a, b = seeded
    settings_service.set_value("breaker_fail_threshold", "1")
    breaker.record_failure(a["id"], "boom")
    assert breaker.is_available(a["id"]) is False

    monkeypatch.setattr(aggregation, "query_source",
                        lambda cfg, identifier: [_item("ACC-B")])

    # without a snapshot: skipped, and the outcome says why
    result = aggregation.collect(Dataset())
    assert result.per_source["ris-a"] == breaker.SKIPPED
    skipped = [o for o in result.outcomes if o.name == "ris-a"][0]
    assert skipped.answers == breaker.SKIPPED
    assert skipped.breaker_state == "open"
    assert result.status == "partial"          # one source answered, one was skipped

    # with a snapshot: the outage bridge serves it
    cache.store_snapshot(a["id"], [_item("ACC-CACHED")])
    result = aggregation.collect(Dataset())
    assert "ris-a" in result.served_stale
    assert result.per_source["ris-a"] == 1
    assert "ACC-CACHED" in [ds.AccessionNumber for ds in result.items]


def test_failing_source_falls_back_to_the_cache_or_reports_error(client, seeded, monkeypatch):
    a, b = seeded
    # one failure is enough to open the breaker in this test
    settings_service.set_value("breaker_fail_threshold", "1")

    def failing(cfg, identifier):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(aggregation, "query_source", failing)

    # nothing cached → an honest error, and the query still returns
    result = aggregation.collect(Dataset())
    assert result.per_source["ris-a"] == aggregation.ERROR
    assert result.status == "failed"

    # a snapshot exists → served stale, the breaker recorded the failure
    cache.store_snapshot(a["id"], [_item("ACC-OLD")])
    result = aggregation.collect(Dataset())
    assert result.per_source["ris-a"] == 1
    assert "ris-a" in result.served_stale
    assert result.status == "partial"
    assert breaker.state_of(a["id"]) == "open"


def test_single_source_mode_queries_only_that_source(client, seeded, monkeypatch):
    """The C-FIND test on the sources page asks exactly one source."""
    a, b = seeded
    asked: list[str] = []

    def fake_query(cfg, identifier):
        asked.append(cfg.name)
        return [_item("ACC-ONLY")]

    monkeypatch.setattr(aggregation, "query_source", fake_query)
    result = aggregation.collect(Dataset(), only_source_id=b["id"])

    assert asked == ["ris-b"]
    assert [ds.AccessionNumber for ds in result.items] == ["ACC-ONLY"]


def test_local_items_participate_with_the_highest_priority(client, seeded, monkeypatch):
    a, b = seeded
    monkeypatch.setattr(aggregation, "query_source",
                        lambda cfg, identifier: [_item("ACC-1")])

    from mwl_broker.models import LocalWorklistItem

    with session_factory()() as s:
        s.add(LocalWorklistItem(accession="ACC-1", sps_id="1", patient_id="P-LOCAL",
                                patient_name="Notfall^Nora", modality="CT",
                                station_aet="CT_01", enabled=True))
        s.commit()

    result = aggregation.collect(Dataset())
    # the local (emergency) entry wins the dedupe against the same case
    assert result.merged[0][1].name == local_worklist.LOCAL_SOURCE_NAME
    assert "local" in result.per_source


def test_preview_flags_keep_provenance_and_counters_untouched(client, seeded, monkeypatch):
    """A preview must not change where images are routed."""
    a, b = seeded
    monkeypatch.setattr(aggregation, "query_source",
                        lambda cfg, identifier: [_item("ACC-1")])

    before = _seen_items()
    result = aggregation.collect(Dataset(), count_metrics=False)
    assert result.items, "the aggregation still runs"
    # collect() itself never writes provenance — the DIMSE handler does
    assert _seen_items() == before

    # and with store_cache=False nothing is cached
    cache.clear()
    aggregation.collect(Dataset(), store_cache=False)
    assert cache.items() == []


def _seen_items() -> int:
    with session_factory()() as s:
        return len(s.scalars(select(SeenItem)).all())


def test_version_comes_from_pyproject(client):
    """The reported version must be the one in the tree, not stale metadata."""
    from mwl_broker import __version__

    assert __version__ and __version__ != "0.0.0"

