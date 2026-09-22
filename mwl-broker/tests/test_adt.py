"""ADT events beyond the merge: A08 (update), A24 (link), A47 (unlink).

The merge (`A40`) is covered in `test_merges.py` — it is the event the broker was
built around. These tests pin the three that were missing, and above all the
difference between a merge and a link: **only a merge retires an identifier**,
so only a merge may rewrite a worklist answer.
"""
from pydicom.dataset import Dataset

from mwl_broker import adt, hl7, mllp, settings_service
from mwl_broker.db import session_factory
from mwl_broker.models import LocalWorklistItem, MwlSource, PatientMerge, SeenItem

ADT_A08 = ("MSH|^~\\&|RIS|KH|MWLBROKER|KH|20260922120000||ADT^A08|MSG-A08|P|2.4\r"
           "PID|1||4711^^^KH^MR||Musterfrau^Erika^^^||19800203|F\r")
ADT_A08_NAME_ONLY = ("MSH|^~\\&|RIS|KH|MWLBROKER|KH|20260922120100||ADT^A08|MSG-A08B|P|2.4\r"
                     "PID|1||4711^^^KH^MR||Musterfrau^Erika\r")
ADT_A24 = ("MSH|^~\\&|RIS|KH|MWLBROKER|KH|20260922120000||ADT^A24|MSG-A24|P|2.4\r"
           "PID|1||12345^^^KH^MR||Muster^Max\r"
           "MRG|ALT-4711\r")
ADT_A47 = ("MSH|^~\\&|RIS|KH|MWLBROKER|KH|20260922120000||ADT^A47|MSG-A47|P|2.4\r"
           "PID|1||12345^^^KH^MR||Muster^Max\r"
           "MRG|ALT-4711\r")
ADT_A03 = ("MSH|^~\\&|RIS|KH|MWLBROKER|KH|20260922120000||ADT^A03|MSG-A03|P|2.4\r"
           "PID|1||4711^^^KH^MR||Muster^Max\r")


def _local_item(patient_id: str, accession: str = "ACC-ADT-1", name: str = "Alt^Name",
                birth: str = "19700101", sex: str = "M") -> int:
    with session_factory()() as s:
        row = LocalWorklistItem(accession=accession, sps_id="1", patient_id=patient_id,
                                patient_name=name, birth_date=birth, sex=sex,
                                modality="CT", station_aet="CT_01", origin="manual")
        s.add(row)
        s.commit()
        s.refresh(row)
        return row.id


def _item(item_id: int) -> LocalWorklistItem:
    with session_factory()() as s:
        return s.get(LocalWorklistItem, item_id)


# ── A08: Patientendaten aktualisieren ─────────────────────────────────────


def test_a08_updates_the_demographics_of_the_brokers_own_entries(client):
    """A corrected name must reach the entry the modality is about to read."""
    item_id = _local_item("4711")

    result = client.post("/api/v1/hl7/adt?dry_run=false", content=ADT_A08,
                         headers={"Content-Type": "text/plain"}).json()

    assert result["action"] == "updated"
    assert result["updated_items"] == 1
    item = _item(item_id)
    assert item.patient_name == "Musterfrau^Erika^^^"
    assert item.birth_date == "1980-02-03"
    assert item.sex == "F"
    assert item.patient_id == "4711", "an A08 does not change identifiers"


def test_a08_only_overwrites_what_the_message_carries(client):
    """An A08 with a name only must not blank the birth date."""
    item_id = _local_item("4711", name="Alt^Name", birth="19700101", sex="M")

    client.post("/api/v1/hl7/adt?dry_run=false", content=ADT_A08_NAME_ONLY,
                headers={"Content-Type": "text/plain"})

    item = _item(item_id)
    assert item.patient_name == "Musterfrau^Erika"
    assert item.birth_date == "19700101"
    assert item.sex == "M"


def test_a08_without_demographics_is_refused(client):
    """Nothing to update is a message error, not a silent no-op."""
    empty = ("MSH|^~\\&|RIS|KH|MWLBROKER|KH|20260922120000||ADT^A08|MSG-A08C|P|2.4\r"
             "PID|1||4711^^^KH^MR\r")

    response = client.post("/api/v1/hl7/adt?dry_run=false", content=empty,
                           headers={"Content-Type": "text/plain"})

    assert response.status_code == 422
    assert "PID-5" in response.text


def test_a08_for_a_merged_id_reaches_the_current_one(client):
    """The RIS may still send the old ID for a while — the entries moved already."""
    from mwl_broker import merges

    item_id = _local_item("NEU-1")
    merges.merge("ALT-1", "NEU-1", actor="tester")
    message = ("MSH|^~\\&|RIS|KH|MWLBROKER|KH|20260922120000||ADT^A08|MSG-A08D|P|2.4\r"
               "PID|1||ALT-1^^^KH^MR||Musterfrau^Erika||19800203|F\r")

    result = client.post("/api/v1/hl7/adt?dry_run=false", content=message,
                         headers={"Content-Type": "text/plain"}).json()

    assert result["updated_items"] == 1
    assert _item(item_id).patient_name == "Musterfrau^Erika"


def test_a08_does_not_follow_a_link(client):
    """A link keeps both IDs valid — an update for one must not touch the other."""
    from mwl_broker import merges

    linked_id = _local_item("LINK-A", accession="ACC-ADT-LINK")
    merges.link("LINK-A", "LINK-B", actor="tester")
    message = ("MSH|^~\\&|RIS|KH|MWLBROKER|KH|20260922120000||ADT^A08|MSG-A08E|P|2.4\r"
               "PID|1||LINK-A^^^KH^MR||Musterfrau^Erika\r")

    client.post("/api/v1/hl7/adt?dry_run=false", content=message,
                headers={"Content-Type": "text/plain"})

    assert _item(linked_id).patient_name == "Musterfrau^Erika"


# ── A24: verknüpfen (kein Zusammenführen) ─────────────────────────────────


def test_a24_records_a_link_and_not_a_merge(client):
    result = client.post("/api/v1/hl7/adt?dry_run=false", content=ADT_A24,
                         headers={"Content-Type": "text/plain"}).json()

    assert result["action"] == "linked"
    rows = client.get("/api/v1/merges").json()
    assert len(rows) == 1
    assert rows[0]["kind"] == "link"
    assert (rows[0]["old_patient_id"], rows[0]["new_patient_id"]) == ("ALT-4711", "12345")


def test_a_link_resolves_but_moves_nothing(client):
    """Both identifiers stay valid: no data moves, the provenance stays put."""
    from mwl_broker import merges

    with session_factory()() as s:
        source = MwlSource(name="ris-a", aet="RIS_A", host="127.0.0.1", port=11112,
                           calling_aet="MWLBROKER", charset="ISO_IR 100",
                           enabled=True, timeout_s=1, priority=10)
        s.add(source)
        s.commit()
        s.refresh(source)
        source_id = source.id
    item_id = _local_item("ALT-4711")
    with session_factory()() as s:
        s.add(SeenItem(accession="ACC-ADT-1", patient_id="ALT-4711", source_id=source_id))
        s.commit()

    merges.link("ALT-4711", "12345", actor="tester")

    assert merges.resolve("ALT-4711") == "12345"
    assert _item(item_id).patient_id == "ALT-4711", "a link must not rewrite the entry"
    with session_factory()() as s:
        assert s.query(SeenItem).filter_by(accession="ACC-ADT-1").one().patient_id == "ALT-4711"


def test_a_link_does_not_rewrite_the_worklist_answer(client, monkeypatch):
    """The decisive difference to a merge: the modality's own ID stays valid."""
    from mwl_broker import aggregation, merges

    with session_factory()() as s:
        s.add(MwlSource(name="ris-a", aet="RIS_A", host="127.0.0.1", port=11112,
                        calling_aet="MWLBROKER", charset="ISO_IR 100",
                        enabled=True, timeout_s=1, priority=10))
        s.commit()

    answer = Dataset()
    answer.PatientID = "LINK-A"
    answer.AccessionNumber = "ACC-LINK-1"
    answer.StudyInstanceUID = "1.2.3.9"
    sps = Dataset()
    sps.ScheduledProcedureStepID = "SPS-1"
    sps.ScheduledStationAETitle = "CT_01"
    sps.ScheduledProcedureStepStartDate = "20260922"
    answer.ScheduledProcedureStepSequence = [sps]

    monkeypatch.setattr(aggregation, "query_source", lambda src, ident: [answer])
    settings_service.set_value("cache_enabled", "false")
    merges.link("LINK-A", "LINK-B", actor="tester")

    served = [ds for ds, _src in aggregation.collect(Dataset()).merged]

    assert served and served[0].PatientID == "LINK-A"
    # …while a merge does rewrite it (same code path, different kind)
    merges.merge("LINK-A", "LINK-B", actor="tester")
    assert merges.answer_mapping(["LINK-A"]) == {"LINK-A": "LINK-B"}


def test_a_link_and_a_merge_do_not_contradict_each_other(client):
    """In real life the A24 comes first and the A40 later — for the same pair.

    The merge must still take effect: recording "already linked" and doing
    nothing would leave the old identifier in place forever.
    """
    from mwl_broker import merges

    item_id = _local_item("ALT-4711", accession="ACC-ADT-UPGRADE")
    client.post("/api/v1/hl7/adt?dry_run=false", content=ADT_A24,
                headers={"Content-Type": "text/plain"})

    merged = client.post("/api/v1/hl7/adt?dry_run=false",
                         content=ADT_A24.replace("ADT^A24", "ADT^A40"),
                         headers={"Content-Type": "text/plain"}).json()

    assert merged["action"] == "merged"
    rows = client.get("/api/v1/merges").json()
    assert [row["kind"] for row in rows] == ["merge"], "the link was upgraded"
    assert merges.answer_mapping(["ALT-4711"]) == {"ALT-4711": "12345"}
    assert _item(item_id).patient_id == "12345", "the merge's effect must happen"


# ── A47: Verknüpfung zurücknehmen ─────────────────────────────────────────


def test_a47_takes_a_link_back(client):
    client.post("/api/v1/hl7/adt?dry_run=false", content=ADT_A24,
                headers={"Content-Type": "text/plain"})

    result = client.post("/api/v1/hl7/adt?dry_run=false", content=ADT_A47,
                         headers={"Content-Type": "text/plain"}).json()

    assert result["action"] == "unlinked"
    assert result["updated_items"] == 1
    assert client.get("/api/v1/merges").json() == []
    # the entry stays for the audit trail
    assert len(client.get("/api/v1/merges?active_only=false").json()) == 1


def test_a47_never_undoes_a_merge(client):
    """An unlink is about a link — a merge is not something an A47 may remove."""
    from mwl_broker import merges

    merges.merge("ALT-9", "NEU-9", actor="tester")

    result = client.post("/api/v1/hl7/adt?dry_run=false",
                         content=ADT_A47.replace("ALT-4711", "ALT-9"),
                         headers={"Content-Type": "text/plain"}).json()

    assert result["updated_items"] == 0
    assert merges.resolve("ALT-9") == "NEU-9"


def test_a47_for_something_unknown_is_not_an_error(client):
    """The RIS may unlink something the broker never knew — that is not a failure."""
    result = client.post("/api/v1/hl7/adt?dry_run=false",
                         content=ADT_A47.replace("ALT-4711", "NEVER-SEEN"),
                         headers={"Content-Type": "text/plain"}).json()

    assert result["action"] == "unlinked" and result["updated_items"] == 0


# ── Transport, Audit, Schema ──────────────────────────────────────────────


def test_adt_arrives_over_mllp_too(client):
    """A real RIS sends ADT over the same MLLP link as the orders."""
    ok, control_id, error = mllp.handle_message(ADT_A24, transport="mllp")

    assert ok is True and error == ""
    assert control_id == "MSG-A24"
    rows = client.get("/api/v1/merges").json()
    assert rows and rows[0]["kind"] == "link" and rows[0]["origin"] == "adt"


def test_mllp_refuses_an_unusable_adt_with_an_error(client):
    ok, _control_id, error = mllp.handle_message(
        ADT_A24.replace("MRG|ALT-4711\r", ""), transport="mllp")

    assert ok is False
    assert "MRG-1" in error
    assert client.get("/api/v1/merges").json() == []


def test_an_applied_event_is_in_the_change_log(client):
    """Every write is traceable — including the ones the RIS triggers."""
    client.post("/api/v1/hl7/adt?dry_run=false", content=ADT_A24,
                headers={"Content-Type": "text/plain", "X-OE3-User": "ris-bot"})

    rows = client.get("/api/v1/audit/config").json()
    items = rows["items"] if isinstance(rows, dict) else rows
    actions = [row["action"] for row in items]
    assert "patient.linked" in actions, actions
    entry = next(row for row in items if row["action"] == "patient.linked")
    assert entry["actor"] == "ris-bot"


def test_a_dry_run_changes_nothing_at_all(client):
    """Not even the message log: a dry run must leave no trace."""
    before = client.get("/api/v1/hl7/messages").json()

    client.post("/api/v1/hl7/adt?dry_run=true", content=ADT_A24,
                headers={"Content-Type": "text/plain"})

    assert client.get("/api/v1/merges").json() == []
    assert len(client.get("/api/v1/hl7/messages").json()) == len(before)


def test_manual_link_through_the_api(client):
    created = client.post("/api/v1/merges", json={
        "old_patient_id": "M-1", "new_patient_id": "M-2", "kind": "link",
        "reason": "zwei MRN, gleiche Person"})

    assert created.status_code == 201
    assert created.json()["kind"] == "link"
    assert client.get("/api/v1/merges/resolve/M-1").json()["resolved"] == "M-2"


def test_the_parser_reads_the_demographics_fields(client):
    parsed = hl7.parse_adt(ADT_A08)

    assert parsed["event"] == "A08"
    assert parsed["new_patient_id"] == "4711"
    # trailing empty components stay, exactly like the ORM path (PID-5 is passed
    # through unchanged — DICOM renders the carets as spaces)
    assert parsed["patient_name"] == "Musterfrau^Erika^^^"
    assert parsed["birth_date"] == "1980-02-03"
    assert parsed["sex"] == "F"
    assert parsed["warnings"] == []


def test_the_link_kind_reaches_the_database(client):
    """`create_all` and the migration must agree on the new column."""
    adt.apply(ADT_A24, actor="tester", dry_run=False)

    with session_factory()() as s:
        row = s.query(PatientMerge).one()
    assert row.kind == "link"


# ── Was hat das jetzt bewirkt? ────────────────────────────────────────────


def test_an_a40_over_rest_moves_the_entries_and_says_so(client):
    """'What did that do?' — a merge retires an ID, so it has to answer that."""
    item_id = _local_item("ALT-MOVED", accession="ACC-ADT-MOVED")
    with session_factory()() as s:
        source = MwlSource(name="ris-moved", aet="RIS_M", host="127.0.0.1", port=11112,
                           calling_aet="MWLBROKER", charset="ISO_IR 100",
                           enabled=True, timeout_s=1, priority=10)
        s.add(source)
        s.commit()
        s.refresh(source)
        s.add(SeenItem(accession="ACC-ADT-MOVED", patient_id="ALT-MOVED",
                       source_id=source.id))
        s.commit()

    result = client.post("/api/v1/hl7/adt?dry_run=false",
                         content=ADT_A24.replace("ADT^A24", "ADT^A40")
                                          .replace("ALT-4711", "ALT-MOVED")
                                          .replace("12345", "NEU-MOVED"),
                         headers={"Content-Type": "text/plain"}).json()

    assert result["action"] == "merged"
    assert _item(item_id).patient_id == "NEU-MOVED"
    with session_factory()() as s:
        assert s.query(SeenItem).filter_by(
            accession="ACC-ADT-MOVED").one().patient_id == "NEU-MOVED"


def test_the_merge_response_says_how_much_moved(client):
    """The API answers 'what did that do?' — not just 'ok'."""
    _local_item("ALT-COUNT", accession="ACC-ADT-COUNT")

    created = client.post("/api/v1/merges", json={
        "old_patient_id": "ALT-COUNT", "new_patient_id": "NEU-COUNT",
        "kind": "merge", "reason": "test"}).json()

    assert created["kind"] == "merge"
    assert created["moved_items"] == 1
    assert created["moved_seen"] == 0


def test_a_link_reports_that_nothing_moved(client):
    _local_item("ALT-LINK-COUNT", accession="ACC-ADT-LINK-COUNT")

    created = client.post("/api/v1/merges", json={
        "old_patient_id": "ALT-LINK-COUNT", "new_patient_id": "NEU-LINK-COUNT",
        "kind": "link"}).json()

    assert created["kind"] == "link"
    assert created["moved_items"] == 0
    assert created["moved_seen"] == 0
    with session_factory()() as s:
        assert s.query(LocalWorklistItem).filter_by(
            accession="ACC-ADT-LINK-COUNT").one().patient_id == "ALT-LINK-COUNT"


def test_an_a31_updates_demographics_like_an_a08(client):
    """A31 ("update person information") is what some houses send instead of A08.

    Found in a foreign sample set (dcm4che/MESA): we refused it as "not handled".
    """
    item_id = _local_item("P-A31", accession="ACC-ADT-A31")
    a31 = ("MSH|^~\\&|RIS|KH|MWLBROKER|KH|20260922190000||ADT^A31^ADT_A05|MSG-A31|P|2.5\r"
           "PID|1||P-A31^^^KH^MR||Musterfrau^Erika||19800203|F\r")

    result = client.post("/api/v1/hl7/adt?dry_run=false", content=a31,
                         headers={"Content-Type": "text/plain"}).json()

    assert result["action"] == "updated"
    assert result["updated_items"] == 1
    assert _item(item_id).patient_name == "Musterfrau^Erika"
