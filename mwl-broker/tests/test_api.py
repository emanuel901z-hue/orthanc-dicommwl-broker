import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

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


def test_openapi_documents_all_endpoints(client):
    """Every path operation carries a summary/tag, query params and schema
    fields carry descriptions — keeps Swagger UI usable for integrators."""
    spec = client.get("/openapi.json").json()

    assert spec["info"]["title"] == "MWL Broker"
    assert len(spec["info"]["description"]) > 100
    tag_names = {t["name"] for t in spec["tags"]}
    assert {"sources", "targets", "rules", "transforms", "settings",
            "logs", "monitoring"} <= tag_names

    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            assert op.get("summary"), f"{method.upper()} {path} missing summary"
            assert op.get("tags"), f"{method.upper()} {path} missing tag"

    # Query parameters documented
    params = spec["paths"]["/api/v1/logs/queries"]["get"]["parameters"]
    assert params and all(p.get("description") for p in params)

    # Request/response schema fields documented — ALL properties of the
    # schemas integrators consume must carry a description.
    for schema_name in [
        "SourceIn", "SourceOut", "TargetIn", "TargetOut",
        "RuleIn", "RuleOut", "QueryLogOut", "StoreLogOut",
        "EchoResult", "StatusOut",
        "TransformIn", "TransformOut", "TransformOperation",
        "SettingOut", "SettingUpdateIn",
    ]:
        schema = spec["components"]["schemas"][schema_name]
        for field, prop in schema["properties"].items():
            assert prop.get("description"), (
                f"{schema_name}.{field} missing description"
            )
