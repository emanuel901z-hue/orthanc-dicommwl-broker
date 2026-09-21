"""HL7 → DICOM field mappings: local conventions without a code change.

The built-in parser covers the standard fields. A mapping reads an extra value
from anywhere in the message into a worklist attribute (the room in OBR-18, the
contrast agent in a ZDS segment) — and nothing happens without one.
"""
import pytest

from mwl_broker import hl7, hl7_mapping, local_worklist

ORM = (
    "MSH|^~\\&|RIS|KH|MWLBROKER|KH|20260921100000||ORM^O01|MSG-MAP-1|P|2.4\r"
    "PID|1||P-1||Muster^Max||19800101|M\r"
    "ORC|NW|ACC-MAP-1|||||||||||1234^Hausarzt^Anna\r"
    "OBR|1|ACC-MAP-1||CT|Routine|||||||||||||CT_03^Room 3\r"
    "ZDS|1.2.3.4.5|CT_01|BARIUM\r"
)


def test_without_a_mapping_nothing_changes(client):
    parsed = hl7.parse(ORM)

    extended, applied = hl7_mapping.apply_maps(parsed, ORM)

    assert applied == []
    assert "mapped" not in extended


def test_a_mapping_fills_an_extra_attribute(client):
    """The room number lives in OBR-18, component 2 — map it to the station."""
    created = client.post("/api/v1/hl7/field-maps", json={
        "segment": "OBR", "field": 18, "component": 2,
        "target_tag": "ScheduledProcedureStepLocation", "enabled": True})
    assert created.status_code == 201, created.text

    parsed, applied = hl7_mapping.apply_maps(hl7.parse(ORM), ORM)

    assert applied and applied[0]["tag"] == "ScheduledProcedureStepLocation"
    assert applied[0]["from"] == "OBR-18.2"
    assert applied[0]["value"] == "Room 3"
    assert parsed["mapped"]["ScheduledProcedureStepLocation"] == "Room 3"


def test_the_dry_run_shows_what_the_mapping_filled(client):
    client.post("/api/v1/hl7/field-maps", json={
        "segment": "ZDS", "field": 3, "component": 0,
        "target_tag": "RequestedContrastAgent"})

    body = client.post("/api/v1/hl7/orm?dry_run=true", content=ORM,
                       headers={"Content-Type": "text/plain"}).json()

    assert body["dry_run"] is True
    assert body["mapped"], body
    assert body["mapped"][0]["tag"] == "RequestedContrastAgent"
    assert body["mapped"][0]["value"] == "BARIUM"
    assert body["parsed"]["mapped"]["RequestedContrastAgent"] == "BARIUM"


def test_applying_the_message_carries_the_mapped_field(client):
    """The value must end up on the worklist item, not only in the preview."""
    from sqlalchemy import select

    from mwl_broker.db import session_factory
    from mwl_broker.models import LocalWorklistItem

    client.post("/api/v1/hl7/field-maps", json={
        "segment": "ZDS", "field": 3, "target_tag": "RequestedContrastAgent"})

    result = client.post("/api/v1/hl7/orm?dry_run=false", content=ORM,
                         headers={"Content-Type": "text/plain"}).json()
    assert result["item_id"], result

    with session_factory()() as s:
        item = s.scalars(select(LocalWorklistItem).where(
            LocalWorklistItem.accession == "ACC-MAP-1")).first()
    assert item is not None
    # the built-in fields still work …
    assert item.patient_name == "Muster^Max"
    # … and the mapped value is stored in the extra attributes
    assert item.extra_attributes.get("RequestedContrastAgent") == "BARIUM"


def test_a_disabled_mapping_is_ignored(client):
    created = client.post("/api/v1/hl7/field-maps", json={
        "segment": "ZDS", "field": 3, "target_tag": "RequestedContrastAgent",
        "enabled": False}).json()

    _, applied = hl7_mapping.apply_maps(hl7.parse(ORM), ORM)
    assert applied == []

    # switching it on afterwards works without a second rule
    again = client.post("/api/v1/hl7/field-maps", json={
        "segment": "ZDS", "field": 3, "target_tag": "RequestedContrastAgent",
        "enabled": True}).json()
    assert again["id"] == created["id"]
    _, applied = hl7_mapping.apply_maps(hl7.parse(ORM), ORM)
    assert applied


def test_a_missing_field_is_not_an_error(client):
    """A mapping whose field the message does not carry is simply skipped."""
    client.post("/api/v1/hl7/field-maps", json={
        "segment": "OBR", "field": 40, "target_tag": "ScheduledProcedureStepID"})

    parsed, applied = hl7_mapping.apply_maps(hl7.parse(ORM), ORM)

    assert applied == []
    assert parsed["accession"] == "ACC-MAP-1"


def test_mapping_endpoints_validate_the_input(client):
    bad_segment = client.post("/api/v1/hl7/field-maps", json={
        "segment": "OBR2", "field": 1, "target_tag": "PatientID"})
    assert bad_segment.status_code == 422
    assert "HL7 segment" in bad_segment.json()["detail"][0]

    bad_field = client.post("/api/v1/hl7/field-maps", json={
        "segment": "OBR", "field": 0, "target_tag": "PatientID"})
    assert bad_field.status_code == 422

    bad_tag = client.post("/api/v1/hl7/field-maps", json={
        "segment": "OBR", "field": 18, "target_tag": "NotATag"})
    assert bad_tag.status_code == 422
    assert "not a DICOM attribute" in bad_tag.json()["detail"][0]

    created = client.post("/api/v1/hl7/field-maps", json={
        "segment": "OBR", "field": 18, "target_tag": "PatientID"}).json()
    assert any(m["target_tag"] == "PatientID" for m in client.get("/api/v1/hl7/field-maps").json())
    assert client.delete(f"/api/v1/hl7/field-maps/{created['id']}").status_code == 204
    assert client.delete("/api/v1/hl7/field-maps/999").status_code == 404
