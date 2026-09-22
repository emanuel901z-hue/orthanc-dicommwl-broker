"""HL7 v2 ORM^O01 parser: segments, fields, Z-segments, warnings, ACK."""
from mwl_broker import hl7

ORM = (
    "MSH|^~\\&|RIS|HOSPITAL|MWLBROKER|RAD|20260917103000||ORM^O01|MSG0001|P|2.5\r"
    "PID|1||P1001||Mueller^Hans||19800101|M\r"
    "ORC|NW|PLACER1|FILLER1\r"
    "OBR|1|PLACER1|ACC-A-001|CT^CT Thorax|R|20260917120000\r"
    "ZDS|1.2.840.113619.2.55.3.1|CT_01\r"
)


def test_parse_maps_the_standard_fields():
    parsed = hl7.parse(ORM)

    assert parsed["message_type"] == "ORM^O01"
    assert parsed["control_id"] == "MSG0001"
    assert parsed["order_control"] == "NW"
    assert parsed["accession"] == "ACC-A-001"
    assert parsed["patient_id"] == "P1001"
    assert parsed["patient_name"] == "Mueller^Hans"
    assert parsed["birth_date"] == "1980-01-01"
    assert parsed["sex"] == "M"
    assert parsed["modality"] == "CT"
    assert parsed["procedure_description"] == "CT Thorax"
    assert parsed["scheduled_date"] == "2026-09-17"
    assert parsed["scheduled_time"] == "12:00"
    assert parsed["study_uid"] == "1.2.840.113619.2.55.3.1"
    assert parsed["station_aet"] == "CT_01"
    assert parsed["warnings"] == []


def test_parse_handles_line_endings_and_blank_lines():
    for text in (ORM.replace("\r", "\n"), ORM.replace("\r", "\r\n"), ORM + "\r\r\n"):
        assert hl7.parse(text)["accession"] == "ACC-A-001"


def test_parse_falls_back_for_missing_fields():
    minimal = (
        "MSH|^~\\&|RIS|||MWLBROKER||20260917103000||ORM^O01|C1|P|2.5\r"
        "ORC|NW\r"
        "OBR|1|||MR\r"
    )
    parsed = hl7.parse(minimal)

    assert parsed["accession"] == ""          # nothing to fall back to
    assert parsed["modality"] == "MR"
    assert parsed["order_control"] == "NW"
    assert any("accession" in warning for warning in parsed["warnings"])
    assert any("patient ID" in warning for warning in parsed["warnings"])


def test_parse_uses_orc3_when_obr3_is_empty():
    text = ("MSH|^~\\&|RIS|||MWLBROKER||20260917103000||ORM^O01|C2|P|2.5\r"
            "ORC|NW||ACC-FROM-ORC\r"
            "OBR|1||||R|20260917120000\r")
    assert hl7.parse(text)["accession"] == "ACC-FROM-ORC"


def test_parse_accepts_the_date_in_obr7():
    """Many RIS send the requested start in OBR-7 (observation date)."""
    text = ("MSH|^~\\&|RIS|||MWLBROKER||20260917103000||ORM^O01|C4|P|2.5\r"
            "ORC|NW\r"
            "OBR|1||ACC-9|CT|R||20260918101500\r")
    assert hl7.parse(text)["scheduled_date"] == "2026-09-18"


def test_parse_takes_the_station_from_zdb_when_zds_is_absent():
    text = ("MSH|^~\\&|RIS|||MWLBROKER||20260917103000||ORM^O01|C3|P|2.5\r"
            "ORC|NW\r"
            "OBR|1||ACC-1|CT\r"
            "ZDB|1|2|3|MR_02\r")
    assert hl7.parse(text)["station_aet"] == "MR_02"


def test_parse_warns_about_unknown_order_control():
    text = ORM.replace("ORC|NW|", "ORC|ZZ|")
    parsed = hl7.parse(text)

    assert any("order control" in warning for warning in parsed["warnings"])


def test_cancel_and_change_codes():
    assert hl7.is_cancel(hl7.parse(ORM.replace("ORC|NW|", "ORC|CA|")))
    assert hl7.is_cancel(hl7.parse(ORM.replace("ORC|NW|", "ORC|OC|")))
    assert not hl7.is_cancel(hl7.parse(ORM.replace("ORC|NW|", "ORC|XO|")))
    assert not hl7.is_cancel(hl7.parse(ORM))


def test_parse_survives_garbage():
    parsed = hl7.parse("this is not HL7 at all")
    assert parsed["accession"] == ""
    assert parsed["warnings"]
    assert hl7.parse("")["accession"] == ""


def test_the_ack_has_the_fields_an_engine_expects():
    """Found by a foreign HL7 stack: our ACK was shifted by two fields.

    MSH-9 has to be the message type and MSH-10 the control ID; the addressing
    fields swap (the sender of the incoming message becomes the receiver of the
    acknowledgement).
    """
    incoming = ("MSH|^~\\&|RIS|KH|MWLBROKER|BROKER|20260922120000||ORM^O01|CTRL-9|P|2.5\r"
                "PID|1||P-1||Muster^Max\rORC|NW|ACC-1\rOBR|1|ACC-1||CT\r")

    fields = hl7.build_ack("CTRL-9", incoming=incoming).split("\r")[0].split("|")
    assert fields[8] == "ACK", "MSH-9 must be the message type"
    assert fields[9] == "CTRL-9", "MSH-10 must be the control ID"
    assert fields[2] == "MWLBROKER"          # MSH-3: we are the sender now
    assert fields[4] == "RIS" and fields[5] == "KH", "the sender becomes the receiver"


def test_the_ack_still_works_without_the_incoming_message():
    fields = hl7.build_ack("CTRL-1").split("\r")[0].split("|")
    assert fields[8] == "ACK" and fields[9] == "CTRL-1"
    assert fields[5], "MSH-6 must not be empty (strict engines reject that)"


def test_build_ack():
    ack = hl7.build_ack("MSG0001", ok=True)
    assert ack.startswith("MSH|^~\\&|MWLBROKER|")
    assert "MSA|AA|MSG0001" in ack

    nak = hl7.build_ack("MSG0001", ok=False, error="no accession|bad")
    assert "MSA|AE|MSG0001|no accession/bad" in nak   # pipes are escaped
