import pytest
from fastapi.testclient import TestClient

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


def test_openapi_documents_all_endpoints(client):
    """Every path operation carries a summary/tag, query params and schema
    fields carry descriptions — keeps Swagger UI usable for integrators."""
    spec = client.get("/openapi.json").json()

    assert spec["info"]["title"] == "MWL Broker"
    assert len(spec["info"]["description"]) > 100
    tag_names = {t["name"] for t in spec["tags"]}
    assert {"sources", "targets", "rules", "logs", "monitoring"} <= tag_names

    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            assert op.get("summary"), f"{method.upper()} {path} missing summary"
            assert op.get("tags"), f"{method.upper()} {path} missing tag"

    # Query parameters documented
    params = spec["paths"]["/api/v1/logs/queries"]["get"]["parameters"]
    assert params and all(p.get("description") for p in params)

    # Request/response schema fields documented
    for schema_name, field in [
        ("SourceIn", "aet"), ("SourceIn", "charset"), ("TargetIn", "is_default"),
        ("RuleIn", "source_id"), ("QueryLogOut", "query_keys"),
        ("StoreLogOut", "target_id"), ("EchoResult", "rtt_ms"),
        ("StatusOut", "counts"),
    ]:
        schema = spec["components"]["schemas"][schema_name]
        assert schema["properties"][field].get("description"), (
            f"{schema_name}.{field} missing description"
        )
