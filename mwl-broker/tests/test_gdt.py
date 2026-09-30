"""GDT/BDT intake — practices without an HL7 interface.

GDT is the German XDT record format: one field per line,
`<3-digit length><4-digit field number><content>`, the length counting the CR+LF
terminator. Only record type `6302` ("Neue Untersuchung anfordern") is an order;
`6300`/`6301` carry master data and `6310`/`6311` examination results. Applying
those would fill the worklist with data nobody ordered — the same class of bug
the `ORU^R01` check prevents on the HL7 path.

The order number has no standard field (vendors make it configurable), so the
adapter derives one from sender, patient and day and says so — or the site sets
it in `gdt_field_map`.
"""
import json

import pytest

from mwl_broker import gdt


def _line(number: str, content: str) -> str:
    # the declared length includes the two-character CR+LF terminator
    return f"{3 + 4 + len(content) + 2:03d}{number}{content}"


def _record(*pairs: tuple[str, str]) -> str:
    return "\r\n".join(_line(number, content) for number, content in pairs) + "\r\n"


ORDER = _record(
    ("8000", "6302"),          # order
    ("8316", "PVS1"),          # sender
    ("8315", "MWLBROKER"),     # receiver
    ("9218", "02.10"),
    ("3000", "P-100"),
    ("3101", "Muster"),
    ("3102", "Max"),
    ("3103", "18121940"),      # TTMMJJJJ → 1940-12-18
    ("3110", "1"),             # male
    ("8402", "CT01"),          # requested examination
)


def _post(client, body: str, dry_run: bool = False):
    return client.post(f"/api/v1/gdt/order?dry_run={'true' if dry_run else 'false'}",
                       content=body, headers={"Content-Type": "text/plain"})


# ── the parser ─────────────────────────────────────────────────────────


def test_a_6302_order_parses_the_patient_and_the_request(client):
    parsed = gdt.parse(ORDER)

    assert parsed["supported"] is True
    assert parsed["record_type"] == "6302"
    assert parsed["sender_id"] == "PVS1"
    assert parsed["patient_id"] == "P-100"
    assert parsed["patient_name"] == "Muster^Max"
    assert parsed["birth_date"] == "1940-12-18"   # GDT TTMMJJJJ → DICOM DA
    assert parsed["sex"] == "M"
    assert parsed["procedure_description"] == "CT01"
    # no order-number field is configured → a stable one is derived, with a note
    assert parsed["accession"].startswith("GDT-PVS1-P-100-")
    assert any("derived" in warning for warning in parsed["warnings"])


@pytest.mark.parametrize("record_type,needle", [
    ("6300", "master-data"),
    ("6301", "master-data"),
    ("6310", "examination data"),
    ("6311", "examination data"),
])
def test_only_order_records_may_create_a_worklist_entry(client, record_type, needle):
    parsed = gdt.parse(_record(("8000", record_type), ("3000", "P-1"), ("3101", "Muster")))

    assert parsed["supported"] is False
    assert needle in parsed["reject_reason"]


def test_an_unknown_record_type_is_refused_with_the_accepted_one(client):
    parsed = gdt.parse(_record(("8000", "9999"), ("3000", "P-1")))

    assert parsed["supported"] is False
    assert "6302" in parsed["reject_reason"]


def test_a_wrong_declared_length_is_reported_not_ignored(client):
    parsed = gdt.parse("09980006302\r\n")   # says 99, the line is 11 + CRLF

    assert parsed["record_type"] == "6302"   # the content is still read
    assert any("declared length" in warning for warning in parsed["warnings"])


def test_the_field_map_reads_a_site_specific_order_number(client):
    client.put("/api/v1/settings/gdt_field_map", json={
        "value": json.dumps({"accession": "6200", "RequestingPhysician": "0102"}),
    })
    record = _record(
        ("8000", "6302"), ("8316", "PVS1"), ("3000", "P-100"),
        ("3101", "Muster"), ("8402", "MR01"),
        ("6200", "A-42"), ("0102", "House^Gregory"),
    )
    parsed = gdt.parse(record)

    assert parsed["accession"] == "A-42"                 # the configured field wins
    # a non-semantic key is a DICOM keyword → an extra worklist attribute
    assert parsed["mapped"] == {"RequestingPhysician": "House^Gregory"}


def test_the_field_map_setting_must_be_a_json_object(client):
    assert client.put("/api/v1/settings/gdt_field_map",
                      json={"value": "not json"}).status_code == 422
    assert client.put("/api/v1/settings/gdt_field_map",
                      json={"value": json.dumps({"accession": 6200})}).status_code == 422


# ── the endpoint ───────────────────────────────────────────────────────


def test_dry_run_reports_without_writing(client):
    plan = _post(client, ORDER, dry_run=True).json()

    assert plan["dry_run"] is True
    assert plan["record_type"] == "6302"
    assert plan["parsed"]["patient_id"] == "P-100"
    assert client.get("/api/v1/local-items").json() == []


def test_apply_creates_a_local_item_with_gdt_provenance(client):
    applied = _post(client, ORDER).json()

    assert applied["dry_run"] is False
    assert applied["action"] == "created"
    assert applied["item"]["origin"] == "gdt"
    assert applied["item"]["procedure_description"] == "CT01"

    items = client.get("/api/v1/local-items").json()
    assert len(items) == 1
    assert items[0]["accession"] == applied["accession"]


def test_the_same_record_is_idempotent(client):
    first = _post(client, ORDER).json()
    second = _post(client, ORDER).json()

    assert first["action"] == "created"
    assert second["action"] == "updated"
    assert first["accession"] == second["accession"]
    assert len(client.get("/api/v1/local-items").json()) == 1


def test_a_refused_record_is_logged_for_troubleshooting(client):
    result = _post(client, _record(("8000", "6310"), ("3000", "P-1")))

    assert result.status_code == 422
    messages = client.get("/api/v1/hl7/messages?limit=10").json()
    assert any(row["transport"] == "gdt" and row["action"] == "rejected" for row in messages)
    # the raw record is PHI and is never stored
    assert all(row.get("raw", "") == "" for row in messages)


def test_the_intake_can_be_switched_off(client):
    client.put("/api/v1/settings/gdt_enabled", json={"value": "false"})
    assert _post(client, ORDER).status_code == 422
    client.put("/api/v1/settings/gdt_enabled", json={"value": "true"})
    assert _post(client, ORDER).status_code == 200


def test_an_order_without_patient_or_number_is_refused(client):
    result = _post(client, _record(("8000", "6302"), ("8402", "CT01")))

    assert result.status_code == 422
