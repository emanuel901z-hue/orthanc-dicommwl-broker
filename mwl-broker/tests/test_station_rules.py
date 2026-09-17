"""Per-station worklist rules: matching, visibility, priority override."""
from datetime import datetime, timezone

from pydicom.dataset import Dataset

from mwl_broker import station_rules
from mwl_broker.db import session_factory
from mwl_broker.models import MwlSource, StationRule
from mwl_broker.upstream import SourceCfg


def _source(name: str, priority: int) -> int:
    with session_factory()() as s:
        row = MwlSource(name=name, aet=name.upper(), host="127.0.0.1", port=1,
                        calling_aet="MWLBROKER", charset="ISO_IR 100", priority=priority)
        s.add(row)
        s.commit()
        return row.id


def _cfg(source_id: int, name: str, priority: int) -> SourceCfg:
    return SourceCfg(id=source_id, name=name, aet=name.upper(), host="127.0.0.1",
                     port=1, calling_aet="MWLBROKER", charset="ISO_IR 100",
                     timeout_s=5)


def _rule(name="ct-rule", station="CT_01", mode="deny", source_ids=None,
          source_priority=None, priority=100, enabled=True) -> int:
    with session_factory()() as s:
        row = StationRule(name=name, station_aet=station, mode=mode,
                          source_ids=source_ids or [], source_priority=source_priority or {},
                          priority=priority, enabled=enabled)
        s.add(row)
        s.commit()
        return row.id


def _item(accession="ACC-1", sps_id="SPS-1") -> Dataset:
    ds = Dataset()
    ds.AccessionNumber = accession
    sps = Dataset()
    sps.ScheduledProcedureStepID = sps_id
    sps.ScheduledStationAETitle = "CT_01"
    ds.ScheduledProcedureStepSequence = [sps]
    return ds


# ── query station extraction ───────────────────────────────────────────


def test_query_station_reads_the_sps_sequence():
    ds = _item()
    assert station_rules.query_station(ds) == "CT_01"


def test_query_station_accepts_a_top_level_value():
    ds = Dataset()
    ds.ScheduledStationAETitle = "mr_01"
    assert station_rules.query_station(ds) == "MR_01"


def test_query_station_is_empty_without_a_station():
    assert station_rules.query_station(Dataset()) == ""


# ── matching ───────────────────────────────────────────────────────────


def test_no_rule_means_everything_is_visible():
    source_id = _source("ris-a", 10)
    assert station_rules.matching_rule("CT_01") is None
    assert station_rules.source_visible(None, source_id) is True


def test_exact_match_wins_over_the_fallback():
    _rule(name="fallback", station="*", mode="deny", source_ids=[99])
    _rule(name="exact", station="CT_01", mode="deny", source_ids=[1])

    rule = station_rules.matching_rule("ct_01")

    assert rule["name"] == "exact"


def test_fallback_applies_to_unknown_stations():
    _rule(name="fallback", station="*", mode="deny", source_ids=[1])

    assert station_rules.matching_rule("XR_99")["name"] == "fallback"
    # ... but not when the query has no station at all
    assert station_rules.matching_rule("") is None


def test_disabled_rules_are_ignored():
    _rule(name="off", station="CT_01", enabled=False)
    assert station_rules.matching_rule("CT_01") is None


def test_rule_order_decides_between_two_rules_for_the_same_station():
    _rule(name="later", station="CT_01", priority=50, mode="deny", source_ids=[1])
    _rule(name="first", station="CT_01", priority=10, mode="deny", source_ids=[2])

    assert station_rules.matching_rule("CT_01")["name"] == "first"


# ── visibility ─────────────────────────────────────────────────────────


def test_deny_hides_the_listed_sources():
    rule = {"id": 1, "name": "r", "mode": "deny", "source_ids": [2],
            "source_priority": {}, "priority": 100, "enabled": True}

    assert station_rules.source_visible(rule, 1) is True
    assert station_rules.source_visible(rule, 2) is False


def test_allow_shows_only_the_listed_sources():
    rule = {"id": 1, "name": "r", "mode": "allow", "source_ids": [2],
            "source_priority": {}, "priority": 100, "enabled": True}

    assert station_rules.source_visible(rule, 1) is False
    assert station_rules.source_visible(rule, 2) is True


def test_empty_allow_list_hides_everything():
    rule = {"id": 1, "name": "r", "mode": "allow", "source_ids": [],
            "source_priority": {}, "priority": 100, "enabled": True}

    assert station_rules.source_visible(rule, 1) is False


# ── ordering + filtering ───────────────────────────────────────────────


def test_priority_override_reorders_the_sources():
    first = _source("ris-a", 10)
    second = _source("ris-b", 20)
    sources = [_cfg(first, "ris-a", 10), _cfg(second, "ris-b", 20)]
    rule = {"id": 1, "name": "r", "mode": "deny", "source_ids": [],
            "source_priority": {str(second): 1}, "priority": 100, "enabled": True}

    ordered = station_rules.order_sources(sources, rule)

    assert [src.name for src in ordered] == ["ris-b", "ris-a"]


def test_without_a_rule_the_order_is_untouched():
    sources = [_cfg(1, "ris-a", 10), _cfg(2, "ris-b", 20)]
    assert station_rules.order_sources(sources, None) == sources


def test_filter_merged_drops_hidden_sources():
    rule = {"id": 1, "name": "r", "mode": "deny", "source_ids": [2],
            "source_priority": {}, "priority": 100, "enabled": True}
    merged = [(_item("ACC-1"), _cfg(1, "ris-a", 10)), (_item("ACC-2"), _cfg(2, "ris-b", 20))]

    kept, dropped = station_rules.filter_merged(merged, rule)

    assert [str(ds.AccessionNumber) for ds, _ in kept] == ["ACC-1"]
    assert dropped == 1


def test_filter_merged_without_a_rule_keeps_everything():
    merged = [(_item(), _cfg(1, "ris-a", 10))]
    kept, dropped = station_rules.filter_merged(merged, None)
    assert kept == merged and dropped == 0


# ── preview (simulation) ───────────────────────────────────────────────


def test_preview_reports_visibility_and_priority():
    first = _source("ris-a", 10)
    second = _source("ris-b", 20)
    _rule(name="ct", station="CT_01", mode="deny", source_ids=[second],
          source_priority={str(second): 1})
    sources = [_cfg(first, "ris-a", 10), _cfg(second, "ris-b", 20)]

    result = station_rules.preview("CT_01", sources)

    assert result["rule_name"] == "ct" and result["mode"] == "deny"
    by_name = {src["name"]: src for src in result["sources"]}
    assert by_name["ris-a"]["visible"] is True
    assert by_name["ris-b"]["visible"] is False
    assert by_name["ris-b"]["effective_priority"] == 1
    assert "ct" in result["reason"]


def test_preview_without_a_rule():
    source_id = _source("ris-a", 10)
    result = station_rules.preview("UNKNOWN", [_cfg(source_id, "ris-a", 10)])

    assert result["rule_id"] is None
    assert result["sources"][0]["visible"] is True
    assert "no station rule" in result["reason"]


def test_reset_for_tests_is_a_noop():
    station_rules.reset_for_tests()
    assert datetime.now(timezone.utc)  # module import sanity
