"""Role-based access: the proxy decides, the broker enforces read vs. write."""
import pytest
from fastapi.testclient import TestClient

from mwl_broker import rbac, settings_service


def _source_payload(**overrides) -> dict:
    payload = {
        "name": "ris-a", "aet": "RIS_A", "host": "127.0.0.1", "port": 1,
        "calling_aet": "MWLBROKER", "charset": "ISO_IR 100",
        "enabled": True, "timeout_s": 5, "priority": 10,
    }
    payload.update(overrides)
    return payload


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from mwl_broker.main import create_app

    with TestClient(create_app()) as c:
        yield c


def test_off_by_default_everything_is_allowed():
    assert rbac.enforce() is False
    assert rbac.can_write({}) is True
    assert rbac.describe({})["enforced"] is False


def test_enforce_rejects_writes_without_the_role(client):
    client.put("/api/v1/settings/rbac_mode", json={"value": "enforce"})

    # reads stay open (the proxy already authenticated the user)
    assert client.get("/api/v1/sources").status_code == 200
    assert client.get("/api/v1/rbac/status").status_code == 200

    denied = client.post("/api/v1/sources", json=_source_payload())
    assert denied.status_code == 403
    assert "brokerWrite" in denied.json()["detail"]

    # with the role the write goes through
    allowed = client.post("/api/v1/sources", json=_source_payload(name="ris-b"),
                          headers={"X-OE3-Roles": "brokerRead,brokerWrite"})
    assert allowed.status_code == 201

    settings_service.set_value("rbac_mode", "off")


def test_enforce_rejects_every_write_kind(client):
    """Sources, settings and operator actions are all writes."""
    client.put("/api/v1/settings/rbac_mode", json={"value": "enforce"})
    headers = {"X-OE3-Roles": "brokerRead"}

    assert client.post("/api/v1/sources", json=_source_payload(),
                       headers=headers).status_code == 403
    assert client.put("/api/v1/settings/echo_interval_s", json={"value": "20"},
                      headers=headers).status_code == 403
    assert client.post("/api/v1/spool/retry-all", headers=headers).status_code == 403
    assert client.delete("/api/v1/cache", headers=headers).status_code == 403

    # reads are fine
    assert client.get("/api/v1/sources", headers=headers).status_code == 200

    settings_service.set_value("rbac_mode", "off")


def test_rbac_settings_are_validated(client):
    # while enforcement is on, the caller needs the write role to change settings
    headers = {"X-OE3-Roles": "brokerWrite"}
    assert client.put("/api/v1/settings/rbac_mode", json={"value": "enforce"},
                      headers=headers).status_code == 200
    assert client.put("/api/v1/settings/rbac_mode", json={"value": "maybe"},
                      headers=headers).status_code == 422
    assert client.put("/api/v1/settings/rbac_write_role", json={"value": "brokerWrite"},
                      headers=headers).status_code == 200
    rows = {s["key"]: s for s in client.get("/api/v1/settings").json()}
    assert rows["rbac_mode"]["kind"] == "enum:off,enforce"
    assert rows["rbac_mode"]["default"] == "off"


def test_rbac_status_endpoint(client):
    status = client.get("/api/v1/rbac/status").json()
    assert status["enforced"] is False and status["can_write"] is True

    client.put("/api/v1/settings/rbac_mode", json={"value": "enforce"})
    denied = client.get("/api/v1/rbac/status",
                        headers={"X-OE3-Roles": "brokerRead"}).json()
    assert denied["enforced"] is True and denied["can_write"] is False
    assert denied["roles"] == ["brokerRead"]

    allowed = client.get("/api/v1/rbac/status",
                         headers={"X-OE3-Roles": "brokerWrite"}).json()
    assert allowed["can_write"] is True

    settings_service.set_value("rbac_mode", "off")



# ── Read-only work stays allowed (the operator must be able to look) ────

def test_read_only_posts_stay_allowed_in_enforce_mode(client):
    """Dry-runs, C-ECHO and the TLS check are POSTs but change nothing.

    Measured before the fix: every one of them answered 403 for a read-only
    operator, so the safest tools were the ones they could not use.
    """
    src = client.post("/api/v1/sources", json=_source_payload()).json()
    client.put("/api/v1/settings/rbac_mode", json={"value": "enforce"})

    # a read-only caller (no roles header)
    assert client.post("/api/v1/simulate/route",
                       json={"accession": "ACC-1"}).status_code == 200
    assert client.post("/api/v1/simulate/station",
                       json={"station_aet": "CT_01"}).status_code == 200
    assert client.post("/api/v1/simulate/transform",
                       json={"accession": "ACC-1"}).status_code == 200
    assert client.post(f"/api/v1/sources/{src['id']}/echo").status_code == 200
    assert client.post("/api/v1/tls/test",
                       json={"host": "127.0.0.1", "port": 1}).status_code == 200

    # …but applying something still needs the write role
    assert client.post("/api/v1/simulate/route",
                       json={"accession": "ACC-1"}).status_code == 200
    assert client.post("/api/v1/sources", json=_source_payload(name="x", aet="X")).status_code == 403


def test_dry_run_is_allowed_but_applying_is_not(client):
    """`?dry_run=true` is a read; the same route without it is a write."""
    client.put("/api/v1/settings/rbac_mode", json={"value": "enforce"})

    # the dry run reaches the handler (422 = the empty message is invalid,
    # but it was *not* rejected for missing rights)
    assert client.post("/api/v1/hl7/orm?dry_run=true", content="",
                       headers={"Content-Type": "text/plain"}).status_code != 403
    assert client.post("/api/v1/hl7/orm", content="",
                       headers={"Content-Type": "text/plain"}).status_code == 403
    assert client.post("/api/v1/config/import?dry_run=true", json={}).status_code != 403
    assert client.post("/api/v1/config/import", json={}).status_code == 403


def test_side_effecting_tests_keep_the_write_role(client):
    """A test message really leaves the building — that stays a write."""
    client.put("/api/v1/settings/rbac_mode", json={"value": "enforce"})

    assert client.post("/api/v1/atna/test").status_code == 403
    assert client.post("/api/v1/notify/test").status_code == 403
    # with the role it works
    assert client.post("/api/v1/notify/test",
                       headers={"X-OE3-Roles": "brokerWrite"}).status_code == 200


def test_read_only_helper_matches_the_policy():
    assert rbac.is_read_only_request("GET", "/api/v1/sources") is True
    assert rbac.is_read_only_request("POST", "/api/v1/simulate/route") is True
    assert rbac.is_read_only_request("POST", "/api/v1/tls/test") is True
    assert rbac.is_read_only_request("POST", "/api/v1/sources/7/echo") is True
    assert rbac.is_read_only_request("POST", "/api/v1/config/import",
                                     "dry_run=true") is True
    assert rbac.is_read_only_request("POST", "/api/v1/config/import") is False
    assert rbac.is_read_only_request("POST", "/api/v1/sources") is False
    assert rbac.is_read_only_request("DELETE", "/api/v1/cache") is False
