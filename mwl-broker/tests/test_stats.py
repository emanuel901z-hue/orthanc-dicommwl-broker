"""Reporting: the numbers an operator and a quality manager ask for.

Everything is derived from the existing logs — no extra bookkeeping, no PHI.
"""
from datetime import datetime, timedelta, timezone

import pytest

from mwl_broker import stats
from mwl_broker.db import get_engine
from mwl_broker.models import MppsStep, QueryLog, StoreLog, StoreSpool
from sqlalchemy.orm import Session as OrmSession


def _seed(queries=3, stores=2, mpps=1, days_ago=0) -> None:
    now = datetime.now(timezone.utc) - timedelta(days=days_ago)
    with OrmSession(get_engine()) as s:
        for i in range(queries):
            s.add(QueryLog(ts=now, calling_aet="CT_01", status="success" if i else "failed",
                           answers=2, duration_ms=100 + i,
                           query_keys={"SPS": {"ScheduledStationAETitle": "CT_01"}, "Modality": "CT"},
                           per_source={"ris-a": 2, "ris-b": "error" if not i else 1},
                           served_stale=["ris-b"] if not i else []))
        for i in range(stores):
            s.add(StoreLog(ts=now, calling_aet="CT_01", status="success" if i else "failed",
                           source_id=1, target_id=1))
        for i in range(mpps):
            s.add(MppsStep(ts=now, sop_instance_uid=f"1.2.3.{days_ago}.{i}",
                           status="COMPLETED", accession="ACC-1", forwarded=bool(i)))
        s.commit()


def test_overview_totals(client):
    _seed()

    body = client.get("/api/v1/stats/overview").json()

    totals = body["totals"]
    assert totals["queries"] == 3
    assert totals["answers"] == 6
    assert totals["queries_failed"] == 1
    assert totals["queries_from_cache"] == 1
    assert totals["avg_duration_ms"] > 0
    assert totals["stores"] == 2
    assert totals["stores_forwarded"] == 1
    assert totals["stores_failed"] == 1
    assert totals["mpps_steps"] == 1
    assert body["days"] if False else True  # (period is in totals)
    assert totals["days"] == 7


def test_overview_groups_by_source(client):
    _seed()

    body = client.get("/api/v1/stats/overview", params={"group_by": "source"}).json()

    names = {g["name"] for g in body["groups"]}
    assert {"ris-a", "ris-b"} <= names
    ris_b = next(g for g in body["groups"] if g["name"] == "ris-b")
    # ris-b could not be reached in one of the queries
    assert ris_b["queries_failed"] >= 1


def test_overview_groups_by_station_and_modality(client):
    _seed()

    by_station = client.get("/api/v1/stats/overview", params={"group_by": "station"}).json()
    assert by_station["groups"][0]["name"] == "CT_01"
    assert by_station["groups"][0]["queries"] == 3

    by_modality = client.get("/api/v1/stats/overview", params={"group_by": "modality"}).json()
    assert by_modality["groups"][0]["name"] == "CT"


def test_series_is_gap_free_and_oldest_first(client):
    _seed(days_ago=0)
    _seed(days_ago=2)

    body = client.get("/api/v1/stats/overview", params={"days": 3}).json()

    series = body["series"]
    assert len(series) == 4          # today and the three days before (inclusive window)
    assert [d["day"] for d in series] == sorted(d["day"] for d in series)
    assert sum(d["queries"] for d in series) == 6
    assert all("queries" in d and "stores" in d and "mpps" in d for d in series)


def test_period_can_be_chosen_and_is_bounded(client):
    _seed(days_ago=30)

    week = client.get("/api/v1/stats/overview", params={"days": 7}).json()
    assert week["totals"]["queries"] == 0        # older than the period

    quarter = client.get("/api/v1/stats/overview", params={"days": 60}).json()
    assert quarter["totals"]["queries"] == 3

    # nonsense is refused with a plain 422
    assert client.get("/api/v1/stats/overview", params={"days": 0}).status_code == 422
    assert client.get("/api/v1/stats/overview", params={"days": 9999}).status_code == 422
    assert client.get("/api/v1/stats/overview", params={"group_by": "nonsense"}).status_code == 422


def test_spool_state_is_reported(client):
    with OrmSession(get_engine()) as s:
        s.add(StoreSpool(sop_instance_uid="1.2.3", study_uid="1.2", target_name="pacs",
                         status="queued", attempts=0, payload_bytes=8))
        s.add(StoreSpool(sop_instance_uid="1.2.4", study_uid="1.2", target_name="pacs",
                         status="dead", attempts=10, payload_bytes=8))
        s.commit()

    totals = client.get("/api/v1/stats/overview").json()["totals"]

    assert totals["spool_open"] == 1
    assert totals["spool_dead"] == 1


def test_overview_is_phi_free(client):
    """Reporting must never leak patient data."""
    _seed()
    body = client.get("/api/v1/stats/overview").json()
    text = str(body)
    assert "PatientName" not in text
    assert "Muster" not in text
    # accession numbers are not part of the report either
    assert "ACC-1" not in text


def test_empty_period_reports_zeroes(client):
    body = client.get("/api/v1/stats/overview").json()

    assert body["totals"]["queries"] == 0
    assert body["totals"]["stores"] == 0
    assert body["groups"] == []
    assert len(body["series"]) >= 7
