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


def test_ups_subscriptions_travel_with_the_configuration(client):
    """They are configuration like sources/targets — a staging export must carry them."""
    client.post("/api/v1/dicom-web/workitems/subscriptions",
                json={"subscriber_aet": "ct_01", "workitem_uid": "1.2.3",
                      "deletion_lock": True})

    doc = client.get("/api/v1/config/export").json()
    assert doc["ups_subscriptions"] == [
        {"subscriber_aet": "CT_01", "workitem_uid": "1.2.3", "deletion_lock": True}]

    # gone in production, back from the document
    client.delete("/api/v1/dicom-web/workitems/subscriptions/CT_01")
    assert client.get("/api/v1/dicom-web/workitems/subscriptions").json() == []

    plan = client.post("/api/v1/config/import?dry_run=true", json=doc).json()
    assert any(c["entity"] == "ups_subscription" and c["action"] == "create"
               for c in plan["changes"])
    client.post("/api/v1/config/import?dry_run=false", json=doc)

    listed = client.get("/api/v1/dicom-web/workitems/subscriptions").json()
    assert [s["subscriber_aet"] for s in listed] == ["CT_01"]
    assert listed[0]["workitem_uid"] == "1.2.3"


def test_an_import_cannot_smuggle_in_a_deployment_owned_setting(client):
    """`spool_dir` from a file would point the container at an unmapped path —
    the same value the API refuses with 409 must not slip in through the import."""
    document = {"schema_version": 1, "settings": {"spool_dir": "/tmp/evil"}}
    plan = client.post("/api/v1/config/import?dry_run=true", json=document).json()
    assert any("deployment" in reason for reason in plan["skipped"])

    before = client.get("/api/v1/settings/spool_dir").json()["value"]
    client.post("/api/v1/config/import?dry_run=false", json=document)
    assert client.get("/api/v1/settings/spool_dir").json()["value"] == before
    assert before != "/tmp/evil"


def test_an_import_reports_updates_not_only_creates(client):
    """A second import with changed values is an *update* — the plan has to say
    so, otherwise the operator sees "nothing to do" and the change never lands."""
    client.post("/api/v1/sources", json=SOURCE)
    client.post("/api/v1/targets", json={"name": "pacs", "aet": "PACS", "host": "10.0.0.9",
                                         "port": 104, "calling_aet": "MWLBROKER",
                                         "enabled": True, "is_default": True})
    doc = client.get("/api/v1/config/export").json()

    doc["targets"][0]["port"] = 11112
    doc["sources"][0]["timeout_s"] = 42
    doc["settings"] = {"echo_interval_s": "90"}

    plan = client.post("/api/v1/config/import?dry_run=true", json=doc).json()
    updates = {(c["entity"], c["name"]) for c in plan["changes"] if c["action"] == "update"}

    assert ("target", "pacs") in updates
    assert ("source", "ris-a") in updates
    assert ("setting", "echo_interval_s") in updates

    client.post("/api/v1/config/import?dry_run=false", json=doc)
    assert client.get("/api/v1/sources").json()[0]["timeout_s"] == 42


def test_a_modify_rule_with_an_unknown_target_is_skipped_with_a_reason(client):
    doc = {"schema_version": 1, "transforms": [
        {"name": "t1", "source": None, "target": "ghost", "priority": 100,
         "enabled": True, "operations": [{"op": "remove", "tag": "PatientAddress"}]},
    ]}
    plan = client.post("/api/v1/config/import?dry_run=true", json=doc).json()

    assert any("unknown target ghost" in reason for reason in plan["skipped"])


def test_a_subscription_without_a_subscriber_is_skipped(client):
    """The schema already rejects an empty subscriber; a document that reaches
    the module another way must not create a subscription without one."""
    from mwl_broker.db import session_factory

    with session_factory()() as s:
        plan = config_io.plan_import(s, {"schema_version": 1, "ups_subscriptions": [
            {"subscriber_aet": "  ", "workitem_uid": ""}]})

    assert any("without subscriber_aet" in reason for reason in plan["skipped"])
    assert plan["changes"] == []


def test_importing_a_changed_subscription_updates_it(client):
    client.post("/api/v1/dicom-web/workitems/subscriptions",
                json={"subscriber_aet": "CT_01"})
    doc = {"schema_version": 1, "ups_subscriptions": [
        {"subscriber_aet": "ct_01", "workitem_uid": "1.2.3", "deletion_lock": True}]}

    plan = client.post("/api/v1/config/import?dry_run=true", json=doc).json()
    assert any(c["entity"] == "ups_subscription" and c["action"] == "update"
               for c in plan["changes"])

    client.post("/api/v1/config/import?dry_run=false", json=doc)
    listed = client.get("/api/v1/dicom-web/workitems/subscriptions").json()
    assert listed[0]["workitem_uid"] == "1.2.3" and listed[0]["deletion_lock"] is True


def test_a_rule_in_the_document_updates_an_existing_rule(client):
    """The same source→target pair with a new priority is an update."""
    client.post("/api/v1/sources", json=SOURCE)
    client.post("/api/v1/targets", json={"name": "pacs", "aet": "PACS", "host": "10.0.0.9",
                                         "port": 104, "calling_aet": "MWLBROKER",
                                         "enabled": True, "is_default": True})
    src = client.get("/api/v1/sources").json()[0]
    tgt = client.get("/api/v1/targets").json()[0]
    client.post("/api/v1/rules", json={"source_id": src["id"], "target_id": tgt["id"],
                                       "priority": 10, "enabled": True})
    doc = {"schema_version": 1,
           "rules": [{"source": "ris-a", "target": "pacs", "priority": 77, "enabled": False}]}

    plan = client.post("/api/v1/config/import?dry_run=true", json=doc).json()
    assert any(c["entity"] == "rule" and c["action"] == "update" for c in plan["changes"])

    client.post("/api/v1/config/import?dry_run=false", json=doc)
    rules = client.get("/api/v1/rules").json()
    assert rules[0]["priority"] == 77 and rules[0]["enabled"] is False


def test_a_modify_rule_in_the_document_updates_an_existing_rule(client):
    client.post("/api/v1/transforms", json={
        "name": "t1", "priority": 100, "enabled": True,
        "operations": [{"op": "remove", "tag": "PatientAddress"}]})
    doc = {"schema_version": 1, "transforms": [
        {"name": "t1", "source": None, "target": None, "priority": 55, "enabled": False,
         "operations": [{"op": "set", "tag": "InstitutionName", "value": "KH"}]}]}

    plan = client.post("/api/v1/config/import?dry_run=true", json=doc).json()
    assert any(c["entity"] == "transform" and c["action"] == "update" for c in plan["changes"])

    client.post("/api/v1/config/import?dry_run=false", json=doc)
    row = client.get("/api/v1/transforms").json()[0]
    assert row["priority"] == 55 and row["enabled"] is False
