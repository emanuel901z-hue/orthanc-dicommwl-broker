import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from mwl_broker import settings_service
from mwl_broker.main import create_app


@pytest.fixture()
def client():
    with TestClient(create_app()) as c:
        yield c


SOURCE = {
    "name": "ris-a",
    "aet": "RIS_A",
    "host": "127.0.0.1",
    "port": 11114,
    "calling_aet": "MWLBROKER",
    "charset": "ISO_IR 100",
    "enabled": True,
    "timeout_s": 5,
    "priority": 10,
}

TARGET = {
    "name": "pacs-kh",
    "aet": "PACS_KH",
    "host": "127.0.0.1",
    "port": 104,
    "calling_aet": "MWLBROKER",
    "enabled": True,
    "is_default": True,
}


def test_source_crud(client):
    r = client.post("/api/v1/sources", json=SOURCE)
    assert r.status_code == 201
    row = r.json()
    assert row["name"] == "ris-a"

    r = client.get("/api/v1/sources")
    assert [s["name"] for s in r.json()] == ["ris-a"]

    r = client.post("/api/v1/sources", json=SOURCE)
    assert r.status_code == 409

    r = client.put(f"/api/v1/sources/{row['id']}", json={**SOURCE, "enabled": False})
    assert r.json()["enabled"] is False

    r = client.delete(f"/api/v1/sources/{row['id']}")
    assert r.status_code == 204
    assert client.get("/api/v1/sources").json() == []


def test_rule_requires_existing_rows(client):
    r = client.post("/api/v1/rules", json={"source_id": 99, "target_id": 99})
    assert r.status_code == 404

    src = client.post("/api/v1/sources", json=SOURCE).json()
    tgt = client.post("/api/v1/targets", json=TARGET).json()
    r = client.post("/api/v1/rules", json={"source_id": src["id"], "target_id": tgt["id"]})
    assert r.status_code == 201
    assert client.get("/api/v1/rules").json()[0]["source_id"] == src["id"]


def test_status_shape(client):
    client.post("/api/v1/sources", json=SOURCE)
    r = client.get("/api/v1/status")
    assert r.status_code == 200
    body = r.json()
    assert body["db_ok"] is True
    assert body["scp_listening"] is False  # disabled in tests
    assert body["sources"][0]["name"] == "ris-a"
    assert body["sources"][0]["error"] == "never checked"
    assert "queries" in body["counts"]


def test_healthz(client):
    assert client.get("/healthz").json()["ok"] is True


def test_logs_empty(client):
    assert client.get("/api/v1/logs/queries").json() == []
    assert client.get("/api/v1/logs/stores").json() == []


def test_target_crud(client):
    r = client.post("/api/v1/targets", json=TARGET)
    assert r.status_code == 201
    row = r.json()
    assert row["is_default"] is True

    r = client.put(f"/api/v1/targets/{row['id']}", json={**TARGET, "enabled": False})
    assert r.json()["enabled"] is False

    r = client.delete(f"/api/v1/targets/{row['id']}")
    assert r.status_code == 204
    assert client.get("/api/v1/targets").json() == []


def test_source_validation_rejects_bad_payload(client):
    r = client.post("/api/v1/sources", json={"name": "x"})  # aet/host/port missing
    assert r.status_code == 422


def test_echo_unknown_source_404(client):
    assert client.post("/api/v1/sources/999/echo").status_code == 404


def test_echo_unreachable_source_returns_error(client):
    """Echo against a dead endpoint returns ok=False + error detail."""
    src = client.post(
        "/api/v1/sources",
        json={**SOURCE, "port": 1, "timeout_s": 1},
    ).json()
    r = client.post(f"/api/v1/sources/{src['id']}/echo")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["error"]


def test_seed_config_supports_rules(client):
    """BROKER_SEED_CONFIG_JSON may include {"kind":"rule",...} items that
    resolve source/target by name."""
    from mwl_broker.db import seed_from_json

    seed_from_json([
        {**SOURCE, "kind": "source"},
        {**TARGET, "kind": "target"},
        {"kind": "rule", "source": "ris-a", "target": "pacs-kh", "priority": 5},
    ])
    rules = client.get("/api/v1/rules").json()
    assert len(rules) == 1
    assert rules[0]["priority"] == 5


def test_seed_rule_skips_unknown_names(client):
    from mwl_broker.db import seed_from_json

    seed_from_json([{"kind": "rule", "source": "nope", "target": "nope"}])
    assert client.get("/api/v1/rules").json() == []


def test_rule_crud(client):
    src = client.post("/api/v1/sources", json=SOURCE).json()
    tgt = client.post("/api/v1/targets", json=TARGET).json()

    rule = client.post("/api/v1/rules", json={"source_id": src["id"], "target_id": tgt["id"]}).json()
    assert rule["priority"] == 100 and rule["enabled"] is True

    r = client.put(f"/api/v1/rules/{rule['id']}", json={
        "source_id": src["id"], "target_id": tgt["id"], "priority": 5, "enabled": False,
    })
    assert r.status_code == 200
    assert r.json()["priority"] == 5 and r.json()["enabled"] is False

    assert client.put("/api/v1/rules/999", json={
        "source_id": src["id"], "target_id": tgt["id"],
    }).status_code == 404
    assert client.delete(f"/api/v1/rules/{rule['id']}").status_code == 204
    assert client.get("/api/v1/rules").json() == []
    assert client.delete("/api/v1/rules/999").status_code == 404


def test_source_and_target_404_on_update_delete(client):
    assert client.put("/api/v1/sources/999", json=SOURCE).status_code == 404
    assert client.delete("/api/v1/sources/999").status_code == 404
    assert client.put("/api/v1/targets/999", json=TARGET).status_code == 404
    assert client.delete("/api/v1/targets/999").status_code == 404


def test_target_echo_endpoint(client):
    tgt = client.post("/api/v1/targets", json={**TARGET, "port": 1}).json()
    r = client.post(f"/api/v1/targets/{tgt['id']}/echo")
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "target"
    assert body["ok"] is False and body["error"]
    assert client.post("/api/v1/targets/999/echo").status_code == 404


def test_log_endpoint_filters_and_pagination(client):
    from mwl_broker.db import session_factory
    from mwl_broker.models import QueryLog, StoreLog

    with session_factory()() as s:
        s.add(QueryLog(calling_aet="CT_01", answers=1, per_source={"ris-a": 1}, status="success"))
        s.add(QueryLog(calling_aet="MR_01", answers=0, per_source={"ris-a": "error"}, status="failed"))
        s.add(StoreLog(calling_aet="CT_01", sop_instance_uid="1.2.3", status="success"))
        s.add(StoreLog(calling_aet="CT_01", sop_instance_uid="1.2.4", status="unrouted"))
        s.commit()

    assert len(client.get("/api/v1/logs/queries").json()) == 2
    by_aet = client.get("/api/v1/logs/queries?calling_aet=CT_01").json()
    assert [q["calling_aet"] for q in by_aet] == ["CT_01"]
    failed = client.get("/api/v1/logs/queries?status=failed").json()
    assert len(failed) == 1 and failed[0]["status"] == "failed"

    unrouted = client.get("/api/v1/logs/stores?status=unrouted").json()
    assert len(unrouted) == 1 and unrouted[0]["sop_instance_uid"] == "1.2.4"

    assert len(client.get("/api/v1/logs/queries?limit=1").json()) == 1
    assert len(client.get("/api/v1/logs/queries?offset=1").json()) == 1
    # query params are validated (ge/le constraints are part of the contract)
    assert client.get("/api/v1/logs/queries?limit=0").status_code == 422
    assert client.get("/api/v1/logs/queries?limit=501").status_code == 422
    assert client.get("/api/v1/logs/queries?offset=-1").status_code == 422


def test_metrics_endpoint_exposes_prometheus(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    for metric in ("mwl_cfind_requests_total", "mwl_cstore_total", "mwl_echo_up", "mwl_seen_items"):
        assert metric in r.text


def test_healthz_reports_db_state(client):
    body = client.get("/healthz").json()
    assert body["ok"] is True and body["db"] is True


def test_check_db_returns_false_when_engine_fails(monkeypatch):
    from mwl_broker import db

    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(db, "get_engine", boom)
    assert db.check_db() is False


def test_settings_second_override_updates_existing_row(client):
    client.put("/api/v1/settings/echo_interval_s", json={"value": "20"})
    r = client.put("/api/v1/settings/echo_interval_s", json={"value": "25"})
    assert r.json()["value"] == "25"

    from mwl_broker.db import session_factory
    from mwl_broker.models import BrokerSetting

    with session_factory()() as s:
        assert s.get(BrokerSetting, "echo_interval_s").value == "25"


def test_settings_validation_edge_cases(client):
    from mwl_broker import settings_service

    assert settings_service.validate_value("nope", "x") == ["unknown setting 'nope'"]
    assert settings_service.validate_value("strict_store_status", "maybe") == [
        "expected a boolean (true/false)"
    ]
    assert settings_service.validate_value("echo_interval_s", "9999") == ["must be between 5 and 3600"]


def test_settings_get_int_falls_back_on_corrupt_value(client):
    from mwl_broker import settings_service

    settings_service.set_value("echo_interval_s", "not-a-number")  # bypasses validation on purpose
    assert settings_service.get_int("echo_interval_s") == int(
        settings_service._env_default("echo_interval_s")
    )


def test_seed_updates_existing_rows(client):
    from mwl_broker.db import seed_from_json

    seed_from_json([{**SOURCE, "kind": "source"}, {**TARGET, "kind": "target"}])
    seed_from_json([
        {**SOURCE, "kind": "source", "port": 11199, "priority": 5},
        {**TARGET, "kind": "target", "is_default": False},
    ])
    src = client.get("/api/v1/sources").json()[0]
    tgt = client.get("/api/v1/targets").json()[0]
    assert src["port"] == 11199 and src["priority"] == 5
    assert tgt["is_default"] is False

    seed_from_json([{"kind": "transform", "name": "t",
                     "operations": [{"op": "remove", "tag": "PatientAddress"}]}])
    seed_from_json([{"kind": "transform", "name": "t", "priority": 7,
                     "operations": [{"op": "remove", "tag": "PatientID"}]}])
    tr = client.get("/api/v1/transforms").json()[0]
    assert tr["priority"] == 7 and tr["operations"][0]["tag"] == "PatientID"


def test_seed_transform_with_unknown_source_name_is_skipped(client):
    from mwl_broker.db import seed_from_json

    seed_from_json([{"kind": "transform", "name": "x", "source": "does-not-exist",
                     "operations": [{"op": "remove", "tag": "PatientAddress"}]}])
    tr = client.get("/api/v1/transforms").json()[0]
    assert tr["source_id"] is None


def test_lifespan_seeds_and_starts_scp(monkeypatch):
    """Startup path: seed from JSON + bind the DICOM SCP + echo thread."""
    import json

    from fastapi.testclient import TestClient

    from mwl_broker import api as api_mod
    from mwl_broker import main as main_mod
    from mwl_broker.config import Settings

    settings = Settings(
        dicom_port=0,
        start_dicom=True,
        start_echo_loop=True,
        echo_interval_s=1,
        seed_config_json=json.dumps([
            {"kind": "target", "name": "seed-target", "aet": "SEED",
             "host": "127.0.0.1", "port": 1, "is_default": True},
        ]),
    )
    monkeypatch.setattr(main_mod, "get_settings", lambda: settings)
    try:
        with TestClient(main_mod.create_app()) as c:
            assert [t["name"] for t in c.get("/api/v1/targets").json()] == ["seed-target"]
            assert c.get("/api/v1/status").json()["scp_listening"] is True
    finally:
        api_mod.bind_scp(None)  # keep other tests independent of the SCP global


def test_lifespan_reports_seed_errors(monkeypatch):
    """A broken seed JSON must not prevent startup."""
    from fastapi.testclient import TestClient

    from mwl_broker import api as api_mod
    from mwl_broker import main as main_mod
    from mwl_broker.config import Settings

    settings = Settings(dicom_port=0, start_dicom=False, start_echo_loop=False,
                        seed_config_json="{not json")
    monkeypatch.setattr(main_mod, "get_settings", lambda: settings)
    try:
        with TestClient(main_mod.create_app()) as c:
            assert c.get("/healthz").json()["ok"] is True
    finally:
        api_mod.bind_scp(None)


TRANSFORM = {

    "name": "kh-modify",
    "enabled": True,
    "priority": 10,
    "source_id": None,
    "target_id": None,
    "operations": [{"op": "prefix", "tag": "PatientID", "value": "KH_"}],
}


def test_transform_crud(client):
    r = client.post("/api/v1/transforms", json=TRANSFORM)
    assert r.status_code == 201
    row = r.json()
    assert row["operations"][0]["tag"] == "PatientID"
    assert row["source_id"] is None

    assert client.post("/api/v1/transforms", json=TRANSFORM).status_code == 409

    r = client.put(f"/api/v1/transforms/{row['id']}", json={**TRANSFORM, "enabled": False})
    assert r.json()["enabled"] is False

    assert client.get("/api/v1/transforms").json()[0]["name"] == "kh-modify"
    assert client.delete(f"/api/v1/transforms/{row['id']}").status_code == 204
    assert client.get("/api/v1/transforms").json() == []


def test_transform_validation_rejects_bad_ops(client):
    r = client.post(
        "/api/v1/transforms",
        json={**TRANSFORM, "operations": [{"op": "set", "tag": "Nope", "value": "x"}]},
    )
    assert r.status_code == 422
    assert "unknown DICOM keyword" in str(r.json()["detail"])

    r = client.post(
        "/api/v1/transforms",
        json={**TRANSFORM, "operations": [{"op": "set", "tag": "StudyInstanceUID", "value": "1.2"}]},
    )
    assert r.status_code == 422
    assert "must not be modified" in str(r.json()["detail"])


def test_transform_scope_must_exist(client):
    assert client.post("/api/v1/transforms", json={**TRANSFORM, "source_id": 99}).status_code == 404
    assert client.post("/api/v1/transforms", json={**TRANSFORM, "target_id": 99}).status_code == 404


def test_settings_list_defaults_from_env(client):
    rows = {s["key"]: s for s in client.get("/api/v1/settings").json()}
    assert {"allowed_calling_aets", "strict_store_status",
            "seen_item_ttl_days", "echo_interval_s"} <= set(rows)
    assert rows["strict_store_status"]["source"] == "env"
    assert rows["strict_store_status"]["value"] == "True"
    assert rows["allowed_calling_aets"]["default"] == ""


def test_settings_override_and_reset(client):
    r = client.put("/api/v1/settings/allowed_calling_aets", json={"value": "CT_01,MR_01"})
    assert r.status_code == 200
    assert r.json()["source"] == "db"

    row = next(s for s in client.get("/api/v1/settings").json()
               if s["key"] == "allowed_calling_aets")
    assert row["value"] == "CT_01,MR_01"
    assert row["source"] == "db"

    assert client.delete("/api/v1/settings/allowed_calling_aets").status_code == 204
    row = next(s for s in client.get("/api/v1/settings").json()
               if s["key"] == "allowed_calling_aets")
    assert row["source"] == "env"


def test_settings_validation(client):
    assert client.put("/api/v1/settings/nope", json={"value": "x"}).status_code == 404
    assert client.delete("/api/v1/settings/nope").status_code == 404
    assert client.put("/api/v1/settings/echo_interval_s", json={"value": "abc"}).status_code == 422
    assert client.put("/api/v1/settings/echo_interval_s", json={"value": "1"}).status_code == 422
    assert client.put("/api/v1/settings/allowed_calling_aets",
                      json={"value": "lower-case"}).status_code == 422


def test_settings_affect_runtime_values(client):
    from mwl_broker import settings_service

    assert settings_service.get_bool("strict_store_status") is True
    client.put("/api/v1/settings/strict_store_status", json={"value": "false"})
    assert settings_service.get_bool("strict_store_status") is False
    client.delete("/api/v1/settings/strict_store_status")
    assert settings_service.get_bool("strict_store_status") is True


def test_retention_purge_removes_old_seen_items(client):
    from datetime import datetime, timedelta, timezone

    from mwl_broker import settings_service
    from mwl_broker.db import session_factory
    from mwl_broker.models import SeenItem

    src = client.post("/api/v1/sources", json=SOURCE).json()
    with session_factory()() as s:
        s.add(SeenItem(accession="OLD", source_id=src["id"],
                       ts=datetime.now(timezone.utc) - timedelta(days=40)))
        s.add(SeenItem(accession="NEW", source_id=src["id"]))
        s.commit()

    client.put("/api/v1/settings/seen_item_ttl_days", json={"value": "30"})
    assert settings_service.purge_seen_items() == 1
    with session_factory()() as s:
        assert [r.accession for r in s.scalars(select(SeenItem)).all()] == ["NEW"]


def test_seed_config_supports_transforms_and_settings(client):
    from mwl_broker.db import seed_from_json

    seed_from_json([
        {**SOURCE, "kind": "source"},
        {**TARGET, "kind": "target"},
        {"kind": "transform", "name": "kh", "source": "ris-a",
         "operations": [{"op": "remove", "tag": "PatientAddress"}]},
        {"kind": "setting", "key": "echo_interval_s", "value": "45"},
    ])
    tr = client.get("/api/v1/transforms").json()
    assert tr[0]["name"] == "kh"
    assert tr[0]["source_id"] is not None
    st = next(s for s in client.get("/api/v1/settings").json() if s["key"] == "echo_interval_s")
    assert st["value"] == "45" and st["source"] == "db"


def test_seed_setting_rejects_invalid_value(client):
    from mwl_broker.db import seed_from_json

    seed_from_json([{"kind": "setting", "key": "echo_interval_s", "value": "nonsense"}])
    st = next(s for s in client.get("/api/v1/settings").json() if s["key"] == "echo_interval_s")
    assert st["source"] == "env"


def test_status_exposes_breaker_state_for_sources(client):
    from mwl_broker import breaker

    src_row = client.post("/api/v1/sources", json=SOURCE).json()
    client.post("/api/v1/targets", json=TARGET)

    body = client.get("/api/v1/status").json()
    healthy = next(s for s in body["sources"] if s["id"] == src_row["id"])
    assert healthy["breaker_state"] == "closed"
    assert healthy["breaker_retry_in_s"] is None
    # targets have no breaker
    assert body["targets"][0]["breaker_state"] is None

    settings_service.set_value("breaker_fail_threshold", "1")
    settings_service.set_value("breaker_open_seconds", "30")
    breaker.record_failure(src_row["id"], "connection refused")

    body = client.get("/api/v1/status").json()
    broken = next(s for s in body["sources"] if s["id"] == src_row["id"])
    assert broken["breaker_state"] == "open"
    assert 0 < broken["breaker_retry_in_s"] <= 30


def test_reset_breaker_endpoint(client):
    from mwl_broker import breaker

    src_row = client.post("/api/v1/sources", json=SOURCE).json()
    settings_service.set_value("breaker_fail_threshold", "1")
    breaker.record_failure(src_row["id"], "boom")
    assert breaker.is_available(src_row["id"]) is False

    r = client.post(f"/api/v1/sources/{src_row['id']}/reset-breaker")
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "closed" and body["source_id"] == src_row["id"]
    assert breaker.is_available(src_row["id"]) is True

    assert client.post("/api/v1/sources/999/reset-breaker").status_code == 404


def test_deleting_a_source_removes_its_breaker_state(client):
    from mwl_broker.db import session_factory
    from mwl_broker.models import SourceBreaker

    src_row = client.post("/api/v1/sources", json=SOURCE).json()
    settings_service.set_value("breaker_fail_threshold", "1")
    from mwl_broker import breaker

    breaker.record_failure(src_row["id"], "boom")
    with session_factory()() as s:
        assert s.get(SourceBreaker, src_row["id"]) is not None

    assert client.delete(f"/api/v1/sources/{src_row['id']}").status_code == 204
    with session_factory()() as s:
        assert s.get(SourceBreaker, src_row["id"]) is None


def test_deleting_a_source_removes_dependent_configuration(client):
    """Postgres enforces the FKs — deleting a source must clean up first."""
    from mwl_broker import breaker
    from mwl_broker.db import session_factory
    from mwl_broker.models import SeenItem

    src_row = client.post("/api/v1/sources", json=SOURCE).json()
    tgt = client.post("/api/v1/targets", json=TARGET).json()
    client.post("/api/v1/rules", json={"source_id": src_row["id"], "target_id": tgt["id"]})
    client.post("/api/v1/transforms", json={**TRANSFORM, "source_id": src_row["id"]})
    with session_factory()() as s:
        s.add(SeenItem(accession="ACC-1", source_id=src_row["id"]))
        s.commit()
    breaker.record_failure(src_row["id"], "boom")

    assert client.delete(f"/api/v1/sources/{src_row['id']}").status_code == 204

    assert client.get("/api/v1/sources").json() == []
    assert client.get("/api/v1/rules").json() == []
    assert client.get("/api/v1/transforms").json() == []
    with session_factory()() as s:
        assert s.scalars(select(SeenItem)).all() == []


def test_deleting_a_target_removes_dependent_configuration(client):
    src_row = client.post("/api/v1/sources", json=SOURCE).json()
    tgt = client.post("/api/v1/targets", json=TARGET).json()
    client.post("/api/v1/rules", json={"source_id": src_row["id"], "target_id": tgt["id"]})
    client.post("/api/v1/transforms", json={**TRANSFORM, "target_id": tgt["id"]})

    assert client.delete(f"/api/v1/targets/{tgt['id']}").status_code == 204

    assert client.get("/api/v1/targets").json() == []
    assert client.get("/api/v1/rules").json() == []
    assert client.get("/api/v1/transforms").json() == []


def test_health_config_endpoint_reports_findings(client):
    # nothing configured → the missing default target is an error
    body = client.get("/api/v1/health/config").json()
    codes = {f["code"] for f in body["findings"]}
    assert "no_default_target" in codes
    assert body["summary"]["error"] >= 1
    finding = next(f for f in body["findings"] if f["code"] == "no_default_target")
    assert finding["severity"] == "error" and finding["message"]

    client.post("/api/v1/sources", json=SOURCE)
    client.post("/api/v1/targets", json=TARGET)

    body = client.get("/api/v1/health/config").json()
    assert body["summary"]["error"] == 0
    # the empty AET allowlist stays an info-level note
    assert "aet_whitelist_empty" in {f["code"] for f in body["findings"]}


def test_healthz_ready_reports_components(client):
    r = client.get("/healthz/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["ready"] is True
    assert body["checks"] == {"db": True, "scp": True}  # DICOM disabled in tests


def test_healthz_ready_is_503_when_db_is_down(client, monkeypatch):
    from mwl_broker import db as db_mod

    monkeypatch.setattr(db_mod, "check_db", lambda: False)

    r = client.get("/healthz/ready")

    assert r.status_code == 503
    assert r.json()["ready"] is False
    assert r.json()["checks"]["db"] is False


def test_breaker_settings_are_validated(client):
    assert client.put("/api/v1/settings/breaker_fail_threshold",
                      json={"value": "5"}).status_code == 200
    assert client.put("/api/v1/settings/breaker_fail_threshold",
                      json={"value": "0"}).status_code == 422
    assert client.put("/api/v1/settings/breaker_open_seconds",
                      json={"value": "1"}).status_code == 422
    rows = {s["key"]: s for s in client.get("/api/v1/settings").json()}
    assert rows["breaker_fail_threshold"]["source"] == "db"


def test_simulate_route_endpoint(client):
    src_row = client.post("/api/v1/sources", json=SOURCE).json()
    tgt = client.post("/api/v1/targets", json=TARGET).json()
    client.post("/api/v1/rules", json={"source_id": src_row["id"], "target_id": tgt["id"]})

    # no seen_items yet → default target
    body = client.post("/api/v1/simulate/route", json={"accession": "ACC-1"}).json()
    assert body["matched_via"] == "default"
    assert body["target_name"] == TARGET["name"]

    # with a worklist history the rule wins
    from datetime import datetime, timezone

    from mwl_broker.db import session_factory
    from mwl_broker.models import SeenItem

    with session_factory()() as s:
        s.add(SeenItem(accession="ACC-1", source_id=src_row["id"],
                       ts=datetime.now(timezone.utc)))
        s.commit()

    body = client.post("/api/v1/simulate/route", json={"accession": "ACC-1"}).json()
    assert body["matched_via"] == "accession"
    assert body["source_name"] == SOURCE["name"]
    assert body["rule_id"] is not None


def test_simulate_transform_endpoint(client):
    src_row = client.post("/api/v1/sources", json=SOURCE).json()
    client.post("/api/v1/targets", json=TARGET)
    client.post("/api/v1/transforms", json={
        **TRANSFORM, "source_id": src_row["id"],
        "operations": [{"op": "prefix", "tag": "PatientID", "value": "KH_"}],
    })

    body = client.post("/api/v1/simulate/transform", json={
        "source_id": src_row["id"], "values": {"PatientID": "P1"},
    }).json()

    assert body["rules_applied"] == [TRANSFORM["name"]]
    assert body["changes"] == [{"tag": "PatientID", "before": "P1", "after": "KH_P1"}]
    assert body["errors"] == []
    # nothing was stored
    assert client.get("/api/v1/logs/stores").json() == []


def test_cache_endpoints(client):
    src_row = client.post("/api/v1/sources", json=SOURCE).json()

    # empty cache
    stats = client.get("/api/v1/cache/stats").json()
    entry = next(row for row in stats if row["source_id"] == src_row["id"])
    assert entry["entries"] == 0 and entry["state"] == "empty" and entry["age_s"] is None
    assert entry["stale_on_error"] is True and entry["refresh_s"] == 0
    assert client.get("/api/v1/cache/items").json() == []

    # fill it through the internal API (the DIMSE path is covered elsewhere)
    from pydicom.dataset import Dataset
    from pydicom.uid import CTImageStorage

    from mwl_broker import cache

    ds = Dataset()
    ds.AccessionNumber = "ACC-1"
    ds.PatientID = "P1"
    ds.PatientName = "Mueller^Hans"
    ds.StudyInstanceUID = "1.2.3"
    sps = Dataset()
    sps.ScheduledProcedureStepID = "SPS-1"
    sps.ScheduledProcedureStepStatus = "SCHEDULED"
    sps.ScheduledStationAETitle = "CT_01"
    sps.Modality = "CT"
    ds.ScheduledProcedureStepSequence = [sps]
    cache.store_snapshot(src_row["id"], [ds])

    stats = client.get("/api/v1/cache/stats").json()
    entry = next(row for row in stats if row["source_id"] == src_row["id"])
    assert entry["entries"] == 1 and entry["state"] == "available"
    assert entry["age_s"] is not None

    items = client.get("/api/v1/cache/items").json()
    assert len(items) == 1
    assert items[0]["accession"] == "ACC-1"
    assert items[0]["sps_status"] == "SCHEDULED"
    # no patient identifiers in the operator view
    assert "patient" not in json.dumps(items).lower()

    assert client.get(f"/api/v1/cache/items?source_id={src_row['id']}").json()
    assert client.get("/api/v1/cache/items?source_id=999").json() == []
    assert client.get("/api/v1/cache/items?limit=0").status_code == 422

    # clearing one source, then everything
    assert client.delete(f"/api/v1/cache/sources/{src_row['id']}").status_code == 204
    assert client.get("/api/v1/cache/items").json() == []
    assert client.delete("/api/v1/cache").status_code == 204
    assert client.delete("/api/v1/cache/sources/999").status_code == 404


def test_source_cache_fields_round_trip(client):
    created = client.post("/api/v1/sources", json={
        **SOURCE, "cache_stale_on_error": False, "cache_refresh_s": 300,
    }).json()

    assert created["cache_stale_on_error"] is False
    assert created["cache_refresh_s"] == 300

    updated = client.put(f"/api/v1/sources/{created['id']}", json={
        **SOURCE, "cache_stale_on_error": True, "cache_refresh_s": 0,
    }).json()
    assert updated["cache_stale_on_error"] is True and updated["cache_refresh_s"] == 0


def test_cache_settings_are_validated(client):
    assert client.put("/api/v1/settings/cache_stale_max_s",
                      json={"value": "0"}).status_code == 200
    assert client.put("/api/v1/settings/cache_stale_max_s",
                      json={"value": "99999"}).status_code == 422
    assert client.put("/api/v1/settings/cache_enabled",
                      json={"value": "nope"}).status_code == 422
    rows = {s["key"]: s for s in client.get("/api/v1/settings").json()}
    assert rows["cache_hide_completed"]["default"] == "True"


def test_spool_endpoints(client):
    from pydicom.dataset import Dataset
    from pydicom.uid import CTImageStorage

    from mwl_broker import spool

    target = client.post("/api/v1/targets", json=TARGET).json()

    # empty spool
    stats = client.get("/api/v1/spool/stats").json()
    assert stats["open"] == 0 and stats["dead"] == 0 and stats["bytes"] == 0
    assert stats["oldest_age_s"] is None
    assert stats["capacity"]["full"] is False
    assert stats["enabled"] is True and stats["accept_when_queued"] is True
    assert client.get("/api/v1/spool").json() == []

    ds = Dataset()
    ds.SOPClassUID = CTImageStorage
    ds.SOPInstanceUID = "1.2.3.4.5"
    ds.StudyInstanceUID = "9.8.7"
    ds.AccessionNumber = "ACC-1"
    ds.PatientName = "Mueller^Hans"
    assert spool.enqueue(ds, None, target["id"], target["name"], "connection refused") == "queued"

    stats = client.get("/api/v1/spool/stats").json()
    assert stats["queued"] == 1 and stats["open"] == 1
    assert stats["oldest_age_s"] is not None
    assert stats["capacity"]["items"] == 1

    items = client.get("/api/v1/spool").json()
    assert len(items) == 1
    entry = items[0]
    assert entry["sop_instance_uid"] == "1.2.3.4.5"
    assert entry["status"] == "queued" and entry["attempts"] == 0
    assert entry["last_error"] == "connection refused"
    assert entry["target_name"] == target["name"]
    # the payload stays on disk — the API never exposes patient data
    assert "Mueller" not in json.dumps(items)
    assert "payload_path" not in entry

    assert len(client.get("/api/v1/spool?status=queued").json()) == 1
    assert client.get("/api/v1/spool?status=dead").json() == []
    assert client.get("/api/v1/spool?limit=0").status_code == 422

    # retry one entry, then all of them
    assert client.post(f"/api/v1/spool/{entry['id']}/retry").json() == {"requeued": 1}
    assert client.post("/api/v1/spool/999/retry").status_code == 404
    assert client.post("/api/v1/spool/retry-all").json() == {"requeued": 0}

    # discarding requires a reason and is audited
    assert client.delete(f"/api/v1/spool/{entry['id']}").status_code == 422
    assert client.delete(f"/api/v1/spool/{entry['id']}?reason=duplicate").status_code == 204
    assert client.get("/api/v1/spool").json() == []
    assert client.delete(f"/api/v1/spool/{entry['id']}?reason=gone").status_code == 404

    actions = [row["action"] for row in client.get("/api/v1/audit/config").json()]
    assert "retry.spool" in actions and "discard.spool" in actions


def test_spool_settings_are_validated(client):
    assert client.put("/api/v1/settings/spool_dir",
                      json={"value": "/var/lib/mwl-broker/spool"}).status_code == 200
    assert client.put("/api/v1/settings/spool_dir",
                      json={"value": "relative/path"}).status_code == 422
    assert client.put("/api/v1/settings/spool_max_attempts",
                      json={"value": "0"}).status_code == 422
    assert client.put("/api/v1/settings/accept_when_queued",
                      json={"value": "false"}).status_code == 200
    rows = {s["key"]: s for s in client.get("/api/v1/settings").json()}
    assert rows["spool_dir"]["kind"] == "path"
    assert rows["spool_enabled"]["default"] == "True"


def test_notify_endpoints(client):
    events = client.get("/api/v1/notify/events").json()
    codes = {event["code"] for event in events}
    assert "source_down" in codes and "spool_dead_letter" in codes
    assert all(event["severity"] and event["description"] for event in events)

    # no webhook configured → the test message reports it
    assert client.post("/api/v1/notify/test").json() == {
        "ok": False, "error": "no webhook URL configured",
    }

    client.put("/api/v1/settings/notify_webhook_url", json={"value": "http://127.0.0.1:1/hook"})
    result = client.post("/api/v1/notify/test").json()
    assert result["ok"] is False and result["error"]

    actions = [row["action"] for row in client.get("/api/v1/audit/config").json()]
    assert "test.notify" in actions


def test_notify_settings_are_validated(client):
    assert client.put("/api/v1/settings/notify_webhook_url",
                      json={"value": "https://hooks.example/x"}).status_code == 200
    assert client.put("/api/v1/settings/notify_webhook_url",
                      json={"value": "not-a-url"}).status_code == 422
    assert client.put("/api/v1/settings/notify_events",
                      json={"value": "source_down,target_down"}).status_code == 200
    assert client.put("/api/v1/settings/notify_events",
                      json={"value": "source_down,bogus"}).status_code == 422
    rows = {s["key"]: s for s in client.get("/api/v1/settings").json()}
    assert rows["notify_webhook_url"]["kind"] == "url"
    assert rows["notify_min_interval_s"]["default"] == "300"


def test_station_rule_crud_and_simulation(client):
    src_row = client.post("/api/v1/sources", json=SOURCE).json()
    other = client.post("/api/v1/sources", json={**SOURCE, "name": "ris-b"}).json()

    created = client.post("/api/v1/station-rules", json={
        "name": "ct-hides-ris-a", "station_aet": "CT_01", "mode": "deny",
        "source_ids": [src_row["id"]], "source_priority": {str(other["id"]): 1},
    })
    assert created.status_code == 201
    rule = created.json()
    assert rule["mode"] == "deny" and rule["source_ids"] == [src_row["id"]]
    assert rule["source_priority"] == {str(other["id"]): 1}

    assert [r["name"] for r in client.get("/api/v1/station-rules").json()] == ["ct-hides-ris-a"]

    updated = client.put(f"/api/v1/station-rules/{rule['id']}", json={
        **{k: rule[k] for k in ("name", "station_aet", "source_ids", "source_priority")},
        "mode": "allow", "priority": 5, "enabled": False,
    }).json()
    assert updated["mode"] == "allow" and updated["enabled"] is False

    # the rule is disabled → no rule applies
    body = client.post("/api/v1/simulate/station", json={"station_aet": "CT_01"}).json()
    assert body["station_aet"] == "CT_01"
    assert body["rule_id"] is None and "no station rule" in body["reason"]

    client.put(f"/api/v1/station-rules/{rule['id']}", json={
        **{k: rule[k] for k in ("name", "station_aet", "source_ids", "source_priority")},
        "mode": "allow", "priority": 5, "enabled": True,
    })
    body = client.post("/api/v1/simulate/station", json={"station_aet": "CT_01"}).json()
    assert body["rule_name"] == "ct-hides-ris-a" and body["mode"] == "allow"
    by_name = {src_["name"]: src_ for src_ in body["sources"]}
    # allow-list contains ris-a → only that source is visible
    assert by_name["ris-a"]["visible"] is True
    assert by_name["ris-b"]["visible"] is False
    # ... but the priority override still reorders the fan-out
    assert by_name["ris-b"]["effective_priority"] == 1

    # validation
    assert client.post("/api/v1/station-rules", json={
        "name": "bad", "mode": "maybe",
    }).status_code == 422
    assert client.post("/api/v1/station-rules", json={
        "name": "bad", "station_aet": "lower case!",
    }).status_code == 422
    assert client.post("/api/v1/station-rules", json={
        "name": "ct-hides-ris-a",
    }).status_code == 409

    assert client.delete(f"/api/v1/station-rules/{rule['id']}").status_code == 204
    assert client.get("/api/v1/station-rules").json() == []

    actions = [row["action"] for row in client.get("/api/v1/audit/config").json()]
    assert "create.station" in actions and "delete.station" in actions


def test_atna_endpoints(client):
    stats = client.get("/api/v1/atna/stats").json()
    assert stats["enabled"] is False and stats["configured"] is False
    assert stats["queue_size"] == 0 and stats["queue_max"] >= 100
    assert stats["protocol"] == "tcp"

    # the sample message documents the format for the receiving team
    sample = client.get("/api/v1/atna/sample").json()["xml"]
    assert sample.startswith('<?xml version="1.0"')
    assert 'csd-code="110112"' in sample and "</AuditMessage>" in sample

    # not configured → the test message reports it
    assert client.post("/api/v1/atna/test").json() == {
        "ok": False, "error": "audit repository not configured or disabled",
    }

    # configure a dead endpoint → delivery fails, reported back
    client.put("/api/v1/settings/atna_enabled", json={"value": "true"})
    client.put("/api/v1/settings/atna_syslog_host", json={"value": "127.0.0.1"})
    client.put("/api/v1/settings/atna_syslog_port", json={"value": "1"})
    from mwl_broker import atna

    atna.reset_for_tests()
    result = client.post("/api/v1/atna/test").json()
    assert result["ok"] is False and result["error"]

    actions = [row["action"] for row in client.get("/api/v1/audit/config").json()]
    assert "test.atna" in actions


def test_atna_settings_are_validated(client):
    assert client.put("/api/v1/settings/atna_syslog_protocol",
                      json={"value": "tls"}).status_code == 200
    assert client.put("/api/v1/settings/atna_syslog_protocol",
                      json={"value": "udp"}).status_code == 422
    assert client.put("/api/v1/settings/atna_syslog_port",
                      json={"value": "0"}).status_code == 422
    assert client.put("/api/v1/settings/atna_queue_max",
                      json={"value": "10"}).status_code == 422
    assert client.put("/api/v1/settings/atna_tls_ca_file",
                      json={"value": "relative.pem"}).status_code == 422
    rows = {s["key"]: s for s in client.get("/api/v1/settings").json()}
    assert rows["atna_syslog_protocol"]["kind"] == "enum:tcp,tls"
    assert rows["atna_enabled"]["default"] == "False"


LOCAL_ITEM = {
    "accession": "EMERG-001", "sps_id": "1", "patient_id": "P9001",
    "patient_name": "Notfall^Anna", "modality": "CT", "station_aet": "CT_01",
    "procedure_description": "CT Schädel (Notfall)", "scheduled_date": "2026-09-17",
    "scheduled_time": "12:00",
}

ORM = (
    "MSH|^~\\&|RIS|HOSPITAL|MWLBROKER|RAD|20260917103000||ORM^O01|MSG0001|P|2.5\r"
    "PID|1||P1001||Mueller^Hans||19800101|M\r"
    "ORC|NW|PLACER1|FILLER1\r"
    "OBR|1|PLACER1|ACC-HL7-1|CT^CT Thorax|R|20260917120000\r"
    "ZDS|1.2.3.4|CT_01\r"
)


def test_local_item_crud(client):
    created = client.post("/api/v1/local-items", json=LOCAL_ITEM)
    assert created.status_code == 201
    item = created.json()
    assert item["accession"] == "EMERG-001" and item["origin"] == "manual"
    assert item["valid_until"] is not None      # default validity applied
    assert item["enabled"] is True

    assert client.post("/api/v1/local-items", json=LOCAL_ITEM).status_code == 409
    assert [row["accession"] for row in client.get("/api/v1/local-items").json()] == ["EMERG-001"]

    updated = client.put(f"/api/v1/local-items/{item['id']}", json={
        **LOCAL_ITEM, "procedure_description": "CT Schädel nativ", "enabled": False,
    }).json()
    assert updated["procedure_description"] == "CT Schädel nativ"
    assert updated["enabled"] is False

    assert client.delete(f"/api/v1/local-items/{item['id']}").status_code == 204
    assert client.get("/api/v1/local-items").json() == []
    assert client.delete(f"/api/v1/local-items/{item['id']}").status_code == 404

    actions = [row["action"] for row in client.get("/api/v1/audit/config").json()]
    assert "create.local_item" in actions and "delete.local_item" in actions
    # the change log stays PHI-free
    entries = client.get("/api/v1/audit/config?entity=local_item").json()
    assert entries
    # scheduling data is audited, patient identity is not (PHI boundary)
    assert "patient_name" not in json.dumps(entries)
    assert "Notfall^Anna" not in json.dumps(entries)
    assert "P9001" not in json.dumps(entries)
    created_entry = next(e for e in entries if e["action"] == "create.local_item")
    assert created_entry["after_json"]["accession"] == "EMERG-001"
    # a delete has no "after" state
    deleted_entry = next(e for e in entries if e["action"] == "delete.local_item")
    assert deleted_entry["after_json"] is None


def test_local_item_validation(client):
    assert client.post("/api/v1/local-items", json={**LOCAL_ITEM, "accession": ""}).status_code == 422
    assert client.post("/api/v1/local-items", json={**LOCAL_ITEM, "accession": "X" * 80}).status_code == 422


def test_hl7_orm_dry_run_and_apply(client):
    # dry run: parse and report, write nothing
    plan = client.post("/api/v1/hl7/orm?dry_run=true", content=ORM,
                       headers={"Content-Type": "text/plain"}).json()
    assert plan["dry_run"] is True
    assert plan["accession"] == "ACC-HL7-1" and plan["order_control"] == "NW"
    assert plan["parsed"]["patient_id"] == "P1001"
    assert plan["parsed"]["station_aet"] == "CT_01"
    assert plan["warnings"] == []
    assert client.get("/api/v1/local-items").json() == []

    # apply
    applied = client.post("/api/v1/hl7/orm?dry_run=false", content=ORM,
                          headers={"Content-Type": "text/plain"}).json()
    assert applied["dry_run"] is False and applied["action"] == "created"
    assert applied["item"]["accession"] == "ACC-HL7-1"
    assert applied["item"]["origin"] == "hl7"

    # a cancel removes it again
    cancel = client.post("/api/v1/hl7/orm?dry_run=false",
                         content=ORM.replace("ORC|NW|", "ORC|CA|"),
                         headers={"Content-Type": "text/plain"}).json()
    assert cancel["action"] == "cancelled"
    assert client.get("/api/v1/local-items").json() == []

    # the message log documents both
    messages = client.get("/api/v1/hl7/messages").json()
    assert [m["action"] for m in messages] == ["cancelled", "created"]
    assert all(m["transport"] == "http" for m in messages)


def test_hl7_orm_rejects_unusable_messages(client):
    # no accession → 422 with the parser warnings
    r = client.post("/api/v1/hl7/orm", content="MSH|^~\\&|RIS||MWLBROKER||2026||ORM^O01|C1|P|2.5",
                    headers={"Content-Type": "text/plain"})
    assert r.status_code == 422

    client.put("/api/v1/settings/hl7_enabled", json={"value": "false"})
    assert client.post("/api/v1/hl7/orm", content=ORM,
                       headers={"Content-Type": "text/plain"}).status_code == 422
    client.put("/api/v1/settings/hl7_enabled", json={"value": "true"})


def test_hl7_and_local_settings_are_validated(client):
    assert client.put("/api/v1/settings/local_default_validity_days",
                      json={"value": "30"}).status_code == 200
    assert client.put("/api/v1/settings/local_priority",
                      json={"value": "5"}).status_code == 200
    assert client.put("/api/v1/settings/hl7_mllp_port",
                      json={"value": "0"}).status_code == 422
    rows = {s["key"]: s for s in client.get("/api/v1/settings").json()}
    assert rows["hl7_mllp_enabled"]["default"] == "False"
    assert rows["local_priority"]["default"] == "-1"


def test_tls_endpoints(client, tmp_path):
    overview = client.get("/api/v1/tls/overview").json()
    assert overview["inbound_enabled"] is False
    assert overview["inbound_port"] == 2762
    assert overview["inbound_client_auth"] == "none"
    assert overview["outbound_verify"] is True
    assert overview["certificates"] == []
    # nothing configured → no key material anywhere in the response
    assert "BEGIN" not in json.dumps(overview)

    # generate a certificate (the pragmatic path without a PKI)
    client.put("/api/v1/settings/tls_dir", json={"value": str(tmp_path)})
    created = client.post("/api/v1/tls/self-signed", json={
        "common_name": "mwl-broker.hospital.local", "days": 365,
        "san": ["10.0.1.47", "mwl-broker.hospital.local"],
    })
    assert created.status_code == 201
    body = created.json()
    assert "BEGIN CERTIFICATE" in body["certificate_pem"]
    assert "PRIVATE KEY" not in json.dumps(body)          # never the key
    assert body["certificate"]["subject"].startswith("mwl-broker.hospital.local")
    assert body["certificate"]["san"] == ["10.0.1.47", "mwl-broker.hospital.local"]
    assert body["key"]["mode"] == "600"

    # ... and it shows up in the overview
    client.put("/api/v1/settings/tls_inbound_cert_file",
               json={"value": body["certificate_path"]})
    overview = client.get("/api/v1/tls/overview").json()
    assert overview["entries"]["inbound_cert"]["ok"] is True
    assert overview["entries"]["inbound_cert"]["days_left"] > 300

    # validation
    assert client.post("/api/v1/tls/self-signed", json={"common_name": ""}).status_code == 422
    assert client.post("/api/v1/tls/self-signed",
                       json={"common_name": "x", "days": 0}).status_code == 422

    # endpoint check against a dead port reports the problem in plain words
    result = client.post("/api/v1/tls/test",
                         json={"host": "127.0.0.1", "port": 1, "verify": False}).json()
    assert result["ok"] is False and result["error"]

    actions = [row["action"] for row in client.get("/api/v1/audit/config").json()]
    assert "generate.tls_certificate" in actions


def test_tls_settings_are_validated(client):
    assert client.put("/api/v1/settings/tls_inbound_client_auth",
                      json={"value": "required"}).status_code == 200
    assert client.put("/api/v1/settings/tls_inbound_client_auth",
                      json={"value": "maybe"}).status_code == 422
    assert client.put("/api/v1/settings/tls_inbound_port",
                      json={"value": "0"}).status_code == 422
    assert client.put("/api/v1/settings/tls_inbound_cert_file",
                      json={"value": "relative.crt"}).status_code == 422
    assert client.put("/api/v1/settings/tls_outbound_verify",
                      json={"value": "false"}).status_code == 200
    rows = {s["key"]: s for s in client.get("/api/v1/settings").json()}
    assert rows["tls_inbound_client_auth"]["kind"] == "enum:none,optional,required"
    assert rows["tls_inbound_enabled"]["default"] == "False"
    assert rows["tls_outbound_verify"]["default"] == "True"


def test_source_and_target_tls_flags_round_trip(client):
    source = client.post("/api/v1/sources", json={**SOURCE, "tls": True,
                                                  "tls_verify": False}).json()
    assert source["tls"] is True and source["tls_verify"] is False
    target = client.post("/api/v1/targets", json={**TARGET, "tls": True}).json()
    assert target["tls"] is True and target["tls_verify"] is True   # verify defaults on

    # the defaults keep the LAN/VPN setup unchanged
    plain = client.post("/api/v1/sources", json={**SOURCE, "name": "plain"}).json()
    assert plain["tls"] is False and plain["tls_verify"] is True


def test_nonsense_node_values_are_rejected(client):
    """A host with a space or an AE title in lower case can never work."""
    base = {
        "name": "mfa", "aet": "RIS_A", "host": "10.0.1.20", "port": 104,
        "calling_aet": "MWLBROKER", "charset": "ISO_IR 100",
    }

    # nonsense the untrained user types: a sentence instead of an address
    assert client.post("/api/v1/sources", json={**base, "host": "ris server 1"}).status_code == 422
    assert client.post("/api/v1/sources", json={**base, "host": "http://ris"}).status_code == 422
    assert client.post("/api/v1/sources", json={**base, "host": "10.0.1.20/pacs"}).status_code == 422

    # DICOM AE titles are upper case
    assert client.post("/api/v1/sources", json={**base, "aet": "ris_a"}).status_code == 422
    assert client.post("/api/v1/sources", json={**base, "aet": "ct 01"}).status_code == 422
    assert client.post("/api/v1/sources", json={**base, "calling_aet": "mwl"}).status_code == 422
    # the port range is enforced as well
    assert client.post("/api/v1/sources", json={**base, "port": 99999}).status_code == 422

    # valid values still work (IP, hostname, docker service name)
    for host in ("10.0.1.20", "ris-a.hospital.local", "mock-ris-a"):
        created = client.post("/api/v1/sources", json={**base, "name": host, "host": host})
        assert created.status_code == 201, created.text

    # the same rules apply to targets
    target = {"name": "pacs", "aet": "PACS", "host": "ris server", "port": 104}
    assert client.post("/api/v1/targets", json=target).status_code == 422
    assert client.post("/api/v1/targets",
                       json={**target, "host": "10.0.1.30"}).status_code == 201


def test_nonsense_node_values_are_rejected_on_update_too(client):
    """The same rules apply when an existing node is changed, not only on create."""
    created = client.post("/api/v1/sources", json={
        "name": "mfa-edit", "aet": "MFA_EDIT", "host": "10.0.1.21", "port": 104,
        "calling_aet": "MWLBROKER", "charset": "ISO_IR 100",
    }).json()

    bad_host = client.put(f"/api/v1/sources/{created['id']}", json={
        **{k: created[k] for k in ("name", "aet", "port", "calling_aet", "charset",
                                   "enabled", "timeout_s", "priority",
                                   "cache_stale_on_error", "cache_refresh_s",
                                   "tls", "tls_verify")},
        "host": "ris server 1",
    })
    assert bad_host.status_code == 422
    assert "spaces" in bad_host.json()["detail"]

    bad_aet = client.put(f"/api/v1/sources/{created['id']}", json={
        **{k: created[k] for k in ("name", "port", "host", "calling_aet", "charset",
                                   "enabled", "timeout_s", "priority",
                                   "cache_stale_on_error", "cache_refresh_s",
                                   "tls", "tls_verify")},
        "aet": "klein",
    })
    assert bad_aet.status_code == 422

    # the row is unchanged after the rejected attempts
    assert client.get("/api/v1/sources").json()[-1]["host"] == "10.0.1.21"


def test_every_setting_is_documented_for_the_ui(client):
    """The settings page renders key, description, kind and bounds — all present."""
    rows = client.get("/api/v1/settings").json()
    assert len(rows) >= 40
    for row in rows:
        assert row["description"].strip(), f"{row['key']} has no description"
        assert row["kind"], f"{row['key']} has no kind"
        if row["kind"] == "int":
            assert row["min"] is not None and row["max"] is not None, (
                f"{row['key']} has no bounds")
            assert row["min"] <= row["max"]
        if row["kind"].startswith("enum:"):
            assert row["choices"], f"{row['key']} has no choices"


def test_settings_expose_constraints_for_the_ui(client):
    """The UI constrains its inputs from the API — bounds and enum choices."""
    rows = {s["key"]: s for s in client.get("/api/v1/settings").json()}

    # integers carry their allowed range
    interval = rows["echo_interval_s"]
    assert interval["kind"] == "int"
    assert interval["min"] == 5 and interval["max"] == 3600

    # enums carry their choices
    protocol = rows["atna_syslog_protocol"]
    assert protocol["kind"] == "enum:tcp,tls"
    assert protocol["choices"] == ["tcp", "tls"]
    assert rows["rbac_mode"]["choices"] == ["off", "enforce"]

    # non-numeric kinds have no bounds
    assert rows["allowed_calling_aets"]["min"] is None
    assert rows["allowed_calling_aets"]["choices"] == []


def test_openapi_documents_all_endpoints(client):
    """Every path operation is documented: summary, description, documented
    failures and described parameters — keeps Swagger UI usable for integrators."""
    spec = client.get("/openapi.json").json()

    assert spec["info"]["title"] == "MWL Broker"
    assert len(spec["info"]["description"]) > 100
    # the info block tells integrators what a failure looks like and that the
    # API is versioned and licensed
    assert spec["info"]["version"]
    assert spec["info"]["license"]["name"] == "MIT"
    assert "detail" in spec["info"]["description"]
    assert "/rbac/status" in spec["info"]["description"]
    tag_names = {t["name"] for t in spec["tags"]}
    assert {"sources", "targets", "rules", "transforms", "settings",
            "logs", "monitoring", "audit", "config", "simulation", "cache",
            "spool", "atna", "local", "tls"} <= tag_names

    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            where = f"{method.upper()} {path}"
            assert op.get("summary"), f"{where} missing summary"
            assert op.get("tags"), f"{where} missing tag"

            # every 2xx response carries a real description, not FastAPI's default
            for code, response in op["responses"].items():
                if not code.startswith("2"):
                    continue
                description = response.get("description", "")
                assert description and description != "Successful Response", (
                    f"{where} {code} missing response description"
                )

            # path + query parameters are documented
            for param in op.get("parameters", []):
                assert param.get("description"), (
                    f"{where}: parameter {param['name']} missing description"
                )

            # a description explains what the operation does and when to use it
            assert op.get("description"), f"{where} missing description"
            assert len(op["description"]) > 40, f"{where} description too short"

            # no auto-generated response text anywhere (2xx or error)
            for code, response in op["responses"].items():
                description = response.get("description", "")
                assert description not in ("Successful Response", "Validation Error"), (
                    f"{where} {code}: still FastAPI's default description"
                )
                assert description, f"{where} {code} has no description"

            # every operation documents at least one failure
            assert any(code in op["responses"] for code in ("403", "404", "409", "422")), (
                f"{where}: no error response documented"
            )

    # every tag is explained (Swagger groups by them)
    for tag in spec["tags"]:
        assert tag.get("description"), f"tag {tag['name']} has no description"

    # request bodies documented
    for path, method in [
        ("/api/v1/sources", "post"), ("/api/v1/sources/{row_id}", "put"),
        ("/api/v1/targets", "post"), ("/api/v1/targets/{row_id}", "put"),
        ("/api/v1/rules", "post"), ("/api/v1/rules/{rule_id}", "put"),
        ("/api/v1/transforms", "post"), ("/api/v1/transforms/{rule_id}", "put"),
        ("/api/v1/settings/{key}", "put"),
    ]:
        body = spec["paths"][path][method].get("requestBody")
        assert body, f"{method.upper()} {path} has no requestBody"
        # FastAPI puts Body(description=…) on the content schema, not on the
        # requestBody object itself — accept either location.
        schema = body["content"]["application/json"]["schema"]
        assert body.get("description") or schema.get("description"), (
            f"{method.upper()} {path} requestBody missing description"
        )

    # Request/response schema fields documented — ALL properties of the
    # schemas integrators consume must carry a description.
    for schema_name in [
        "SourceIn", "SourceOut", "TargetIn", "TargetOut",
        "RuleIn", "RuleOut", "QueryLogOut", "StoreLogOut",
        "EchoResult", "StatusOut",
        "TransformIn", "TransformOut", "TransformOperation",
        "SettingOut", "SettingUpdateIn",
        "BreakerStateOut", "FindingOut", "HealthOut", "ReadyOut",
        "AuditEntryOut", "RollbackOut", "ConfigImportIn", "ConfigExportOut",
        "ImportPlanOut", "ImportChangeOut", "SimulateRouteIn", "SimulateRouteOut",
        "SimulateTransformIn", "SimulateTransformOut", "TagChangeOut",
        "RuleByNameIn", "TransformImportIn",
        "CacheSourceOut", "CacheItemOut",
        "SpoolStatsOut", "SpoolItemOut", "SpoolRetryOut",
        "NotifyEventOut", "NotifyTestOut",
        "AtnaStatsOut", "AtnaTestOut", "AtnaSampleOut",
        "TlsOverviewOut", "TlsCertificateOut", "TlsKeyOut",
        "TlsSelfSignedIn", "TlsSelfSignedOut", "TlsTestIn", "TlsTestOut",
        "LocalItemIn", "LocalItemOut", "Hl7MessageOut", "Hl7ParseOut",
        "StationRuleIn", "StationRuleOut", "StationSimulateIn",
        "StationPreviewOut", "StationPreviewSourceOut",
    ]:
        schema = spec["components"]["schemas"][schema_name]
        for field, prop in schema["properties"].items():
            assert prop.get("description"), (
                f"{schema_name}.{field} missing description"
            )
