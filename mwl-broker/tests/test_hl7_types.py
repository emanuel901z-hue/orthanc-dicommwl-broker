"""Which HL7 messages may become a worklist entry — and which must never.

The parser reads ORC/OBR/PID, and an `ORU^R01` (a **result**) carries OBR
segments too. Before this check the broker applied it: `order_control` fell back
to `NW`, the accession came from OBR-3, and no warning was raised — a RIS that
broadcasts reports would have quietly filled the worklist. `ORM^O01` and
`OMG^O19` (the general clinical order, same layout) are the orders; everything
else is refused with a reason.
"""
import pytest

from mwl_broker import hl7, local_worklist, mllp
from mwl_broker.db import session_factory
from mwl_broker.models import LocalWorklistItem

ORM = ("MSH|^~\\&|RIS|KH|MWLBROKER|KH|20260922190000||ORM^O01|MSG-ORM|P|2.5\r"
       "PID|1||P-1||Muster^Max||19800101|M\r"
       "ORC|NW|ACC-T-1\r"
       "OBR|1|ACC-T-1||CT^CT Thorax\r")
OMG = ("MSH|^~\\&|KIS|KH|MWLBROKER|KH|20260922190000||OMG^O19|MSG-OMG|P|2.5\r"
       "PID|1||P-2||Musterfrau^Erika||19800203|F\r"
       "ORC|NW|ACC-T-2\r"
       "OBR|1|ACC-T-2||MR^MR Schädel\r")
ORU = ("MSH|^~\\&|RIS|KH|MWLBROKER|KH|20260922190000||ORU^R01|MSG-ORU|P|2.5\r"
       "PID|1||P-3||Muster^Max||19800101|M\r"
       "OBR|1|ORD-77|ACC-T-3|CT^CT Thorax\r"
       "OBX|1|ST|FINDING||Kein Nachweis\r")
ORDER_RESPONSE = ("MSH|^~\\&|PACS|KH|MWLBROKER|KH|20260922190000||ORM^O02|MSG-O02|P|2.5\r"
                  "PID|1||P-4||Muster^Max\r"
                  "ORC|OK|ACC-T-4\r"
                  "OBR|1|ACC-T-4||CT\r")
ADT = ("MSH|^~\\&|RIS|KH|MWLBROKER|KH|20260922190000||ADT^A24|MSG-ADT|P|2.4\r"
       "PID|1||12345^^^KH^MR||Muster^Max\r"
       "MRG|ALT-T-1\r")


def _items() -> list[LocalWorklistItem]:
    with session_factory()() as s:
        return s.query(LocalWorklistItem).all()


# ── der Parser sagt, was er für eine Nachricht hält ───────────────────────


def test_the_parser_marks_a_report_as_not_an_order(client):
    parsed = hl7.parse(ORU)

    assert parsed["supported"] is False
    assert "result/report" in parsed["reject_reason"]
    # …and it *did* parse fields out of it — that is exactly the danger
    assert parsed["accession"] == "ACC-T-3"


def test_the_parser_accepts_both_order_types(client):
    for message in (ORM, OMG):
        parsed = hl7.parse(message)
        assert parsed["supported"] is True
        assert parsed["reject_reason"] == ""


def test_the_message_structure_component_does_not_change_the_verdict(client):
    """MSH-9 is `code^trigger^structure` — dcm4che's samples always carry it.

    Comparing the whole string rejected a valid OMG^O19 from foreign software.
    """
    assert hl7.is_order_message("OMG^O19^OMG_O19") is True
    assert hl7.is_order_message("ORM^O01^ORM_O01") is True
    assert hl7.is_order_message("ORU^R01^ORU_R01") is False
    assert "result/report" in hl7.describe_message_type("ORU^R01^ORU_R01")


def test_an_order_response_is_not_an_order(client):
    parsed = hl7.parse(ORDER_RESPONSE)

    assert parsed["supported"] is False
    assert "response" in parsed["reject_reason"]


# ── die Anwendung lehnt ab (beide Transporte) ────────────────────────────


@pytest.mark.parametrize("message,expected", [
    (ORU, "result/report"),
    (ORDER_RESPONSE, "response"),
    (ADT, "patient event"),
])
def test_a_message_that_is_not_an_order_never_creates_an_item(client, message, expected):
    response = client.post("/api/v1/hl7/orm?dry_run=false", content=message,
                           headers={"Content-Type": "text/plain"})

    assert response.status_code == 422
    assert expected in response.text
    assert _items() == [], "no worklist entry may come out of this"


def test_a_dry_run_refuses_it_the_same_way(client):
    """The check before wiring up an interface must not say 'would be created'."""
    response = client.post("/api/v1/hl7/orm?dry_run=true", content=ORU,
                           headers={"Content-Type": "text/plain"})

    assert response.status_code == 422
    assert "result/report" in response.text


def test_the_refusal_is_in_the_message_log(client):
    """The operator has to find it afterwards — and the metric counts it."""
    client.post("/api/v1/hl7/orm?dry_run=false", content=ORU,
                headers={"Content-Type": "text/plain"})

    entry = client.get("/api/v1/hl7/messages").json()[0]
    assert entry["message_type"] == "ORU^R01"
    assert entry["action"] == "rejected"
    assert "result/report" in entry["error"]


def test_mllp_answers_a_report_with_a_nak(client):
    ok, control_id, error = mllp.handle_message(ORU, transport="mllp")

    assert ok is False
    assert control_id == "MSG-ORU"
    assert "result/report" in error
    assert _items() == []


# ── und die Aufträge gehen weiterhin durch ───────────────────────────────


def test_omg_creates_a_worklist_entry_like_orm(client):
    """The general clinical order — same ORC/OBR layout, same code path."""
    result = client.post("/api/v1/hl7/orm?dry_run=false", content=OMG,
                         headers={"Content-Type": "text/plain"}).json()

    assert result["action"] == "created"
    item = _items()[0]
    assert item.accession == "ACC-T-2"
    assert item.patient_name == "Musterfrau^Erika"
    assert item.modality == "MR"
    assert item.patient_id == "P-2"


def test_both_order_types_reach_the_same_path(client):
    for message in (ORM, OMG):
        assert mllp.handle_message(message, transport="mllp")[0] is True

    assert sorted(item.accession for item in _items()) == ["ACC-T-1", "ACC-T-2"]


def test_a_cancel_over_omg_still_cancels(client):
    """ORC-1 is the order control, whatever the message type is."""
    client.post("/api/v1/hl7/orm?dry_run=false", content=OMG,
                headers={"Content-Type": "text/plain"})
    cancelled = OMG.replace("ORC|NW|", "ORC|CA|")

    result = client.post("/api/v1/hl7/orm?dry_run=false", content=cancelled,
                         headers={"Content-Type": "text/plain"}).json()

    assert result["action"] == "cancelled"
    assert _items() == []


# ── Replay: derselbe Weg wie auf der Leitung ─────────────────────────────


def test_a_replayed_patient_event_goes_to_the_pir_path(client):
    """ADT messages are in the log too — replaying them must not fail."""
    from mwl_broker import adt

    adt.apply(ADT, actor="tester", transport="http", dry_run=False)
    entry = client.get("/api/v1/hl7/messages").json()[0]
    assert entry["message_type"] == "ADT^A24"

    client.put("/api/v1/settings/hl7_store_raw", json={"value": "true"})
    adt.apply(ADT, actor="tester", transport="http", dry_run=False)
    entry = client.get("/api/v1/hl7/messages").json()[0]

    replayed = client.post(f"/api/v1/hl7/messages/{entry['id']}/reprocess?dry_run=false").json()

    assert replayed["action"] in {"linked", "merged"}
    assert client.get("/api/v1/merges").json() != []


def test_a_replayed_report_is_refused_with_a_reason(client):
    client.put("/api/v1/settings/hl7_store_raw", json={"value": "true"})
    local_worklist.log_hl7("http", hl7.parse(ORU), "rejected", raw=ORU)
    entry = client.get("/api/v1/hl7/messages").json()[0]

    response = client.post(f"/api/v1/hl7/messages/{entry['id']}/reprocess")

    assert response.status_code == 422
    assert "result/report" in response.text
