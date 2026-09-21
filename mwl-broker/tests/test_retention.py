"""Retention and deletion: overview, purge, metrics, API."""
from datetime import datetime, timedelta, timezone

from pydicom.dataset import Dataset
from pydicom.uid import CTImageStorage

from mwl_broker import retention, settings_service
from mwl_broker.db import session_factory
from mwl_broker.models import (ConfigAudit, Hl7Message, LocalWorklistItem, MwlSource,
                               QueryLog, SeenItem, StoreLog, StoreSpool)


def _old_query_log(days: int) -> None:
    with session_factory()() as s:
        s.add(QueryLog(calling_aet="CT_01", answers=1, per_source={}, duration_ms=1,
                       status="success", ts=datetime.now(timezone.utc) - timedelta(days=days)))
        s.commit()


def _old_store_log(days: int) -> None:
    with session_factory()() as s:
        s.add(StoreLog(calling_aet="CT_01", sop_instance_uid="1.2.3", study_uid="9.8.7",
                       accession="ACC-1", status="success",
                       ts=datetime.now(timezone.utc) - timedelta(days=days)))
        s.commit()


def _old_seen_item(days: int) -> None:
    with session_factory()() as s:
        s.add(SeenItem(accession="ACC-1", study_uid="9.8.7", sop_instance_uid="1.2.3",
                       source_id=None, target_id=None,
                       ts=datetime.now(timezone.utc) - timedelta(days=days)))
        s.commit()


def _old_hl7(days: int) -> None:
    from mwl_broker.models import Hl7Message

    with session_factory()() as s:
        s.add(Hl7Message(ts=datetime.now(timezone.utc) - timedelta(days=days),
                         transport="http", accession="ACC-1", action="created"))
        s.commit()


def test_overview_lists_every_table_with_its_retention():
    data = retention.overview()

    tables = {entry["table"]: entry for entry in data["tables"]}
    assert set(tables) == {"query_log", "store_log", "seen_item", "hl7_message", "mpps_step",
                           "local_worklist_item", "store_spool", "config_audit"}
    assert tables["query_log"]["retention_days"] == 90
    assert tables["config_audit"]["retention_days"] == 0     # the accounting trail
    assert tables["query_log"]["description"]
    assert all(entry["rows"] == 0 for entry in tables.values())


def test_overview_counts_rows_and_what_would_be_deleted(client):
    from datetime import timezone

    client.post("/api/v1/sources", json={
        "name": "ris-a", "aet": "RIS_A", "host": "h", "port": 1,
        "calling_aet": "MWLBROKER", "charset": "ISO_IR 100",
        "enabled": True, "timeout_s": 5, "priority": 10,
    })
    with session_factory()() as s:
        s.add(QueryLog(calling_aet="CT_01", answers=1, per_source={}, duration_ms=1,
                       status="success", ts=datetime.now(timezone.utc) - timedelta(days=400)))
        s.add(QueryLog(calling_aet="CT_01", answers=1, per_source={}, duration_ms=1,
                       status="success", ts=datetime.now(timezone.utc)))
        s.commit()

    tables = {entry["table"]: entry for entry in retention.overview()["tables"]}
    assert tables["query_log"]["rows"] == 2
    assert tables["query_log"]["will_delete"] == 1     # only the 400-day-old one
    assert tables["query_log"]["oldest"] is not None


def test_purge_removes_only_what_is_older_than_the_window(client):
    from datetime import timezone

    fresh_ts = datetime.now(timezone.utc)
    old_ts = fresh_ts - timedelta(days=400)
    with session_factory()() as s:
        s.add(QueryLog(calling_aet="CT_01", answers=1, per_source={}, duration_ms=1,
                       status="success", ts=old_ts))
        s.add(QueryLog(calling_aet="CT_01", answers=1, per_source={}, duration_ms=1,
                       status="success", ts=fresh_ts))
        s.commit()

    result = retention.purge("query_log")

    assert result["removed"]["query_log"] == 1
    with session_factory()() as s:
        assert s.query(QueryLog).count() == 1      # the fresh one survives


def test_purge_skips_tables_with_retention_zero():
    from datetime import timezone

    with session_factory()() as s:
        s.add(QueryLog(calling_aet="CT_01", answers=1, per_source={}, duration_ms=1,
                       status="success", ts=datetime.now(timezone.utc) - timedelta(days=4000)))
        s.commit()
    settings_service.set_value("retention_query_log_days", "0")

    assert retention.purge("query_log")["total"] == 0
    with session_factory()() as s:
        assert s.query(QueryLog).count() == 1       # 0 = keep forever
    settings_service.set_value("retention_query_log_days", "90")


def test_purge_all_covers_every_table_and_is_audited(client):
    from datetime import timezone

    with session_factory()() as s:
        s.add(QueryLog(calling_aet="CT_01", answers=1, per_source={}, duration_ms=1,
                       status="success", ts=datetime.now(timezone.utc) - timedelta(days=400)))
        source = MwlSource(name="ris-a", aet="RIS_A", host="h", port=1,
                           calling_aet="MWLBROKER", charset="ISO_IR 100")
        s.add(source)
        s.flush()
        s.add(SeenItem(accession="ACC-1", source_id=source.id,
                       ts=datetime.now(timezone.utc) - timedelta(days=400)))
        s.commit()

    # through the API so the action is audited
    result = client.post("/api/v1/retention/purge").json()
    assert result["removed"]["query_log"] == 1
    assert result["removed"]["seen_item"] == 1
    assert result["total"] == 2

    actions = [row["action"] for row in client.get("/api/v1/audit/config").json()]
    assert "purge.retention" in actions


def test_purge_of_an_unknown_table_is_rejected(client):
    assert client.post("/api/v1/retention/purge?table=nope").status_code == 404


def test_retention_endpoints(client):
    overview = client.get("/api/v1/retention").json()
    tables = {entry["table"]: entry for entry in overview["tables"]}
    assert set(tables) == {"query_log", "store_log", "seen_item", "hl7_message", "mpps_step",
                           "local_worklist_item", "store_spool", "config_audit"}
    assert all("rows" in entry and "retention_days" in entry for entry in tables.values())

    # the change log is kept by default (0 = forever)
    assert tables["config_audit"]["retention_days"] == 0

    result = client.post("/api/v1/retention/purge").json()
    assert result["total"] == 0 and set(result["removed"]) == set(tables)

    assert client.post("/api/v1/retention/purge?table=nope").status_code == 404

    actions = [row["action"] for row in client.get("/api/v1/audit/config").json()]
    assert "purge.retention" in actions


def test_retention_settings_are_validated(client):
    assert client.put("/api/v1/settings/retention_query_log_days",
                      json={"value": "365"}).status_code == 200
    assert client.put("/api/v1/settings/retention_query_log_days",
                      json={"value": "-1"}).status_code == 422
    assert client.put("/api/v1/settings/retention_config_audit_days",
                      json={"value": "0"}).status_code == 200
    rows = {s["key"]: s for s in client.get("/api/v1/settings").json()}
    assert rows["retention_query_log_days"]["default"] == "90"
    assert rows["retention_config_audit_days"]["default"] == "0"


def test_old_rows_are_deleted_and_recent_ones_survive():
    from datetime import timezone

    from mwl_broker.models import MwlSource, QueryLog

    now = datetime.now(timezone.utc)
    with session_factory()() as s:
        s.add(QueryLog(calling_aet="CT_01", answers=1, per_source={}, duration_ms=1,
                       status="success", ts=now - timedelta(days=400)))
        s.add(QueryLog(calling_aet="CT_01", answers=1, per_source={}, duration_ms=1,
                       status="success", ts=now - timedelta(days=1)))
        s.commit()

    assert retention.purge()["total"] == 1

    with session_factory()() as s:
        assert s.query(QueryLog).count() == 1


def test_publish_metrics_exposes_the_oldest_row_age():
    from prometheus_client import REGISTRY

    from datetime import timezone

    with session_factory()() as s:
        s.add(QueryLog(calling_aet="CT_01", answers=1, per_source={}, duration_ms=1,
                       status="success",
                       ts=datetime.now(timezone.utc) - timedelta(days=5)))
        s.commit()

    retention.publish_metrics()

    value = REGISTRY.get_sample_value("mwl_retention_oldest_seconds", {"table": "query_log"})
    assert value is not None
    assert 5 * 86400 - 60 < float(value) < 5 * 86400 + 60
