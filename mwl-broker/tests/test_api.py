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


def test_column_migrations_are_idempotent():
    from mwl_broker import db

    engine = db.get_engine()
    db._apply_column_migrations(engine)
    db._apply_column_migrations(engine)  # already applied — must not raise


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


def test_openapi_documents_all_endpoints(client):
    """Every path operation carries a summary/tag, query params and schema
    fields carry descriptions — keeps Swagger UI usable for integrators."""
    spec = client.get("/openapi.json").json()

    assert spec["info"]["title"] == "MWL Broker"
    assert len(spec["info"]["description"]) > 100
    tag_names = {t["name"] for t in spec["tags"]}
    assert {"sources", "targets", "rules", "transforms", "settings",
            "logs", "monitoring", "audit", "config", "simulation"} <= tag_names

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
    ]:
        schema = spec["components"]["schemas"][schema_name]
        for field, prop in schema["properties"].items():
            assert prop.get("description"), (
                f"{schema_name}.{field} missing description"
            )
