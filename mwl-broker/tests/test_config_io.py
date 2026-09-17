"""Configuration export, import (dry-run + apply) and portability."""
from fastapi.testclient import TestClient

from mwl_broker import config_io
from mwl_broker.main import create_app

SOURCE = {
    "name": "ris-a", "aet": "RIS_A", "host": "127.0.0.1", "port": 11114,
    "calling_aet": "MWLBROKER", "charset": "ISO_IR 100", "enabled": True,
    "timeout_s": 5, "priority": 10,
}
TARGET = {
    "name": "pacs-kh", "aet": "PACS_KH", "host": "127.0.0.1", "port": 104,
    "calling_aet": "MWLBROKER", "enabled": True, "is_default": True,
}


def _seed(client) -> None:
    src = client.post("/api/v1/sources", json=SOURCE).json()
    tgt = client.post("/api/v1/targets", json=TARGET).json()
    client.post("/api/v1/rules", json={"source_id": src["id"], "target_id": tgt["id"],
                                       "priority": 7, "enabled": True})
    client.post("/api/v1/transforms", json={
        "name": "kh-modify", "enabled": True, "priority": 10,
        "source_id": src["id"], "target_id": None,
        "operations": [{"op": "prefix", "tag": "PatientID", "value": "KH_"}],
    })
    client.put("/api/v1/settings/echo_interval_s", json={"value": "45"})


def test_export_is_portable_and_versioned(client):
    _seed(client)

    doc = client.get("/api/v1/config/export").json()

    assert doc["schema_version"] == config_io.SCHEMA_VERSION
    assert doc["exported_at"]
    assert [s["name"] for s in doc["sources"]] == ["ris-a"]
    assert [t["name"] for t in doc["targets"]] == ["pacs-kh"]
    # rules and modify rules reference by name, not by id
    assert doc["rules"] == [{"source": "ris-a", "target": "pacs-kh", "priority": 7, "enabled": True}]
    assert doc["transforms"][0]["source"] == "ris-a"
    assert doc["transforms"][0]["target"] is None
    assert doc["settings"] == {"echo_interval_s": "45"}


def test_dry_run_reports_creates_and_writes_nothing(client):
    doc = client.get("/api/v1/config/export").json()  # empty broker
    doc["sources"] = [SOURCE]
    doc["targets"] = [TARGET]
    doc["rules"] = [{"source": "ris-a", "target": "pacs-kh", "priority": 7, "enabled": True}]

    plan = client.post("/api/v1/config/import", json=doc).json()  # dry_run defaults to true

    assert plan["dry_run"] is True
    assert plan["summary"] == {"create": 3, "update": 0, "skipped": 0}
    assert {c["entity"] for c in plan["changes"]} == {"source", "target", "rule"}
    # nothing was written
    assert client.get("/api/v1/sources").json() == []
    assert client.get("/api/v1/targets").json() == []
    assert client.get("/api/v1/rules").json() == []


def test_import_applies_creates_and_updates(client):
    _seed(client)
    doc = client.get("/api/v1/config/export").json()
    doc["sources"][0]["port"] = 11199
    doc["sources"].append({**SOURCE, "name": "ris-b"})

    plan = client.post("/api/v1/config/import?dry_run=false", json=doc).json()

    assert plan["dry_run"] is False
    assert plan["summary"]["create"] == 1  # ris-b
    assert plan["summary"]["update"] == 1  # ris-a port
    sources = {s["name"]: s for s in client.get("/api/v1/sources").json()}
    assert sources["ris-a"]["port"] == 11199
    assert "ris-b" in sources


def test_import_is_idempotent(client):
    _seed(client)
    doc = client.get("/api/v1/config/export").json()

    first = client.post("/api/v1/config/import", json=doc).json()
    second = client.post("/api/v1/config/import", json=doc).json()

    assert first["summary"] == {"create": 0, "update": 0, "skipped": 0}
    assert second["summary"] == {"create": 0, "update": 0, "skipped": 0}


def test_import_never_deletes(client):
    _seed(client)
    doc = client.get("/api/v1/config/export").json()
    doc["sources"] = []          # a file without sources is not a delete statement
    doc["targets"] = []
    doc["rules"] = []

    client.post("/api/v1/config/import?dry_run=false", json=doc)

    assert len(client.get("/api/v1/sources").json()) == 1
    assert len(client.get("/api/v1/targets").json()) == 1
    assert len(client.get("/api/v1/rules").json()) == 1


def test_import_skips_unknown_references_and_reports_why(client):
    doc = {
        "schema_version": config_io.SCHEMA_VERSION,
        "sources": [SOURCE],
        "targets": [],
        "rules": [{"source": "ris-a", "target": "does-not-exist"}],
        "transforms": [{"name": "t", "source": "nope", "operations": [
            {"op": "remove", "tag": "PatientAddress"}]}],
        "settings": {"echo_interval_s": "9999", "nope": "1"},
    }

    plan = client.post("/api/v1/config/import", json=doc).json()

    assert plan["summary"]["skipped"] == 4
    joined = " | ".join(plan["skipped"])
    assert "unknown source or target" in joined
    assert "unknown source nope" in joined
    assert "must be between 5 and 3600" in joined
    assert "unknown key" in joined


def test_import_rejects_an_unsupported_schema_version(client):
    r = client.post("/api/v1/config/import", json={
        "schema_version": 99, "sources": [], "targets": [], "rules": [],
        "transforms": [], "settings": {},
    })

    assert r.status_code == 422
    assert "schema_version 99" in str(r.json()["detail"])


def test_import_records_audit_entries_per_change(client):
    doc = client.get("/api/v1/config/export").json()
    doc["sources"] = [SOURCE]
    doc["settings"] = {"echo_interval_s": "45"}

    client.post("/api/v1/config/import?dry_run=false", json=doc,
                headers={"X-OE3-User": "operator"})

    entries = client.get("/api/v1/audit/config").json()
    actions = {e["action"] for e in entries}
    assert "import.source" in actions and "import.setting" in actions
    assert all(e["actor"] == "operator" for e in entries)


def test_export_import_roundtrip_reproduces_the_configuration(client):
    _seed(client)
    doc = client.get("/api/v1/config/export").json()
    before = {
        "sources": client.get("/api/v1/sources").json(),
        "targets": client.get("/api/v1/targets").json(),
        "rules": client.get("/api/v1/rules").json(),
        "transforms": client.get("/api/v1/transforms").json(),
    }

    # wipe everything, then import the document into the empty broker
    for src in before["sources"]:
        client.delete(f"/api/v1/sources/{src['id']}")
    for tgt in before["targets"]:
        client.delete(f"/api/v1/targets/{tgt['id']}")
    client.delete("/api/v1/settings/echo_interval_s")
    assert client.get("/api/v1/sources").json() == []

    plan = client.post("/api/v1/config/import?dry_run=false", json=doc).json()
    assert plan["summary"]["skipped"] == 0

    after = {
        "sources": client.get("/api/v1/sources").json(),
        "targets": client.get("/api/v1/targets").json(),
        "rules": client.get("/api/v1/rules").json(),
        "transforms": client.get("/api/v1/transforms").json(),
    }
    # ids differ, names/fields do not
    assert [s["name"] for s in after["sources"]] == [s["name"] for s in before["sources"]]
    assert after["sources"][0]["port"] == before["sources"][0]["port"]
    assert len(after["rules"]) == len(before["rules"]) == 1
    assert after["transforms"][0]["operations"] == before["transforms"][0]["operations"]
    assert next(s for s in client.get("/api/v1/settings").json()
                if s["key"] == "echo_interval_s")["value"] == "45"


def test_import_into_a_broker_with_a_different_scope_mapping(client):
    """The portable format survives a rename of the referenced nodes."""
    src = client.post("/api/v1/sources", json=SOURCE).json()
    client.post("/api/v1/targets", json=TARGET)
    client.post("/api/v1/rules", json={"source_id": src["id"], "target_id": 1})
    doc = client.get("/api/v1/config/export").json()
    assert doc["rules"][0]["source"] == "ris-a"

    # rename the source, then re-import: the rule follows the name
    client.put(f"/api/v1/sources/{src['id']}", json={**SOURCE, "name": "ris-a-renamed"})
    plan = client.post("/api/v1/config/import?dry_run=false", json=doc).json()

    assert plan["summary"]["skipped"] == 0
    assert any(c["entity"] == "source" and c["name"] == "ris-a" for c in plan["changes"])
    assert len(client.get("/api/v1/rules").json()) == 2


def test_plan_import_is_pure():
    """plan_import must not write — verified via a second identical plan."""
    with TestClient(create_app()) as c:
        doc = c.get("/api/v1/config/export").json()
        doc["sources"] = [SOURCE]
        first = c.post("/api/v1/config/import", json=doc).json()
        second = c.post("/api/v1/config/import", json=doc).json()
        assert first == second
