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
