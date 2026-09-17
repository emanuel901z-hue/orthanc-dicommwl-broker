"""Configuration change log: recording, filtering and rollback."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from mwl_broker import audit, settings_service
from mwl_broker.db import session_factory
from mwl_broker.main import create_app
from mwl_broker.models import ConfigAudit, MwlSource, PacsTarget, RoutingRule

SOURCE = {
    "name": "ris-a", "aet": "RIS_A", "host": "127.0.0.1", "port": 11114,
    "calling_aet": "MWLBROKER", "charset": "ISO_IR 100", "enabled": True,
    "timeout_s": 5, "priority": 10,
}
TARGET = {
    "name": "pacs-kh", "aet": "PACS_KH", "host": "127.0.0.1", "port": 104,
    "calling_aet": "MWLBROKER", "enabled": True, "is_default": True,
}
TRANSFORM = {
    "name": "kh-modify", "enabled": True, "priority": 10,
    "source_id": None, "target_id": None,
    "operations": [{"op": "prefix", "tag": "PatientID", "value": "KH_"}],
}


@pytest.fixture()
def client():
    with TestClient(create_app()) as c:
        yield c


def _entries() -> list[ConfigAudit]:
    with session_factory()() as s:
        return s.scalars(select(ConfigAudit).order_by(ConfigAudit.id)).all()


def test_every_mutation_is_recorded(client):
    src = client.post("/api/v1/sources", json=SOURCE).json()
    tgt = client.post("/api/v1/targets", json=TARGET).json()
    rule = client.post("/api/v1/rules", json={"source_id": src["id"], "target_id": tgt["id"]}).json()
    client.post("/api/v1/transforms", json=TRANSFORM)
    client.put("/api/v1/settings/echo_interval_s", json={"value": "45"})

    client.put(f"/api/v1/sources/{src['id']}", json={**SOURCE, "port": 11199})
    client.put(f"/api/v1/rules/{rule['id']}", json={
        "source_id": src["id"], "target_id": tgt["id"], "priority": 5, "enabled": False,
    })
    client.delete(f"/api/v1/targets/{tgt['id']}")
    client.delete("/api/v1/settings/echo_interval_s")

    actions = [e.action for e in _entries()]
    assert actions == [
        "create.source", "create.target", "create.rule", "create.transform",
        "update.setting", "update.source", "update.rule", "delete.target",
        "reset.setting",
    ]


def test_snapshots_capture_before_and_after(client):
    src = client.post("/api/v1/sources", json=SOURCE).json()
    client.put(f"/api/v1/sources/{src['id']}", json={**SOURCE, "port": 11199, "enabled": False})

    created, updated = _entries()
    assert created.before_json is None
    assert created.after_json["port"] == 11114

    assert updated.before_json["port"] == 11114
    assert updated.before_json["enabled"] is True
    assert updated.after_json["port"] == 11199
    assert updated.after_json["enabled"] is False


def test_delete_records_the_removed_state(client):
    src = client.post("/api/v1/sources", json=SOURCE).json()
    client.delete(f"/api/v1/sources/{src['id']}")

    entry = _entries()[-1]
    assert entry.action == "delete.source"
    assert entry.before_json["name"] == "ris-a"
    assert entry.after_json is None
    assert entry.entity_id == src["id"]


def test_actor_comes_from_the_configured_header(client):
    client.post("/api/v1/sources", json=SOURCE, headers={"X-OE3-User": "dr.mueller"})
    client.post("/api/v1/targets", json=TARGET)

    actors = [e.actor for e in _entries()]
    assert actors == ["dr.mueller", "api"]


def test_correlation_id_is_kept(client):
    client.post("/api/v1/sources", json=SOURCE, headers={"X-Request-Id": "corr-123"})
    assert _entries()[-1].correlation_id == "corr-123"


def test_audit_endpoint_filters_and_paginates(client):
    client.post("/api/v1/sources", json=SOURCE)
    client.post("/api/v1/targets", json=TARGET)
    client.post("/api/v1/sources", json={**SOURCE, "name": "ris-b"})

    body = client.get("/api/v1/audit/config").json()
    assert [e["action"] for e in body] == ["create.source", "create.target", "create.source"]
    # newest first
    assert body[0]["after_json"]["name"] == "ris-b"

    only_sources = client.get("/api/v1/audit/config?entity=source").json()
    assert len(only_sources) == 2
    assert {e["entity"] for e in only_sources} == {"source"}

    assert len(client.get("/api/v1/audit/config?limit=1").json()) == 1
    assert len(client.get("/api/v1/audit/config?offset=2").json()) == 1


def test_rollback_restores_an_update(client):
    src = client.post("/api/v1/sources", json=SOURCE).json()
    client.put(f"/api/v1/sources/{src['id']}", json={**SOURCE, "port": 11199})
    update_entry = [e for e in _entries() if e.action == "update.source"][0]

    r = client.post(f"/api/v1/config/rollback/{update_entry.id}")

    assert r.status_code == 200
    assert r.json()["action"] == "restore"
    assert client.get("/api/v1/sources").json()[0]["port"] == 11114
    # the rollback itself is audited
    assert _entries()[-1].action == "rollback.source"


def test_rollback_of_a_creation_deletes_it_again(client):
    client.post("/api/v1/targets", json=TARGET)
    create_entry = _entries()[-1]

    r = client.post(f"/api/v1/config/rollback/{create_entry.id}")

    assert r.json()["action"] == "delete"
    assert client.get("/api/v1/targets").json() == []


def test_rollback_of_a_deletion_recreates_the_entry(client):
    src = client.post("/api/v1/sources", json=SOURCE).json()
    client.delete(f"/api/v1/sources/{src['id']}")
    delete_entry = _entries()[-1]

    r = client.post(f"/api/v1/config/rollback/{delete_entry.id}")

    assert r.json()["action"] == "recreate"
    restored = client.get("/api/v1/sources").json()
    assert len(restored) == 1
    assert restored[0]["name"] == "ris-a" and restored[0]["port"] == 11114


def test_rollback_of_a_setting_override(client):
    client.put("/api/v1/settings/echo_interval_s", json={"value": "45"})
    entry = _entries()[-1]

    assert client.post(f"/api/v1/config/rollback/{entry.id}").json()["action"] == "delete"

    rows = {s["key"]: s for s in client.get("/api/v1/settings").json()}
    assert rows["echo_interval_s"]["source"] == "env"


def test_rollback_unknown_entry_is_404(client):
    assert client.post("/api/v1/config/rollback/999").status_code == 404


def test_audit_never_contains_patient_data(client):
    """The change log is configuration only — assert the shape stays clean."""
    client.post("/api/v1/sources", json=SOURCE)
    entry = _entries()[-1]

    assert set(entry.after_json) == {
        "name", "aet", "host", "port", "calling_aet", "charset", "enabled",
        "timeout_s", "priority", "cache_stale_on_error", "cache_refresh_s",
    }


def test_serializer_rejects_unknown_entity():
    with pytest.raises(ValueError):
        audit.snapshot("patient", None)


def test_settings_service_still_works_inside_an_api_session(client):
    """set_value() must reuse the caller's session (audit + write atomically)."""
    client.put("/api/v1/settings/breaker_fail_threshold", json={"value": "7"})
    assert settings_service.get_int("breaker_fail_threshold") == 7


def test_audit_rows_are_configuration_only():
    """Sanity check on the model: no PHI-capable columns."""
    columns = {c.name for c in ConfigAudit.__table__.columns}
    assert columns == {
        "id", "ts", "actor", "action", "entity", "entity_id",
        "before_json", "after_json", "correlation_id",
    }
    # models referenced by the serializers are the configuration tables only
    assert MwlSource.__tablename__ == "mwl_source"
    assert PacsTarget.__tablename__ == "pacs_target"
    assert RoutingRule.__tablename__ == "routing_rule"
