"""UPS-RS: the worklist as a DICOMweb resource (pragmatic subset).

Search, retrieve, create and state change — mapped onto the same data the DIMSE
path serves, so a REST client can never see a different worklist than a modality.
Subscriptions and event reports are deliberately absent (documented boundary).
"""
import pytest

from mwl_broker import ups


def _workitem(accession="ACC-UPS-1", patient_id="P-1", station="CT_01",
              modality="CT", name="Muster^Max") -> dict:
    return {
        "00080050": {"vr": "SH", "Value": [accession]},
        "00100020": {"vr": "LO", "Value": [patient_id]},
        "00100010": {"vr": "PN", "Value": [{"Alphabetic": name}]},
        "00400001": {"vr": "AE", "Value": [station]},
        "00080060": {"vr": "CS", "Value": [modality]},
        "00400002": {"vr": "DA", "Value": ["20260922"]},
        "00401001": {"vr": "SH", "Value": ["SPS-1"]},
    }


def test_create_retrieve_and_search(client):
    created = client.post("/api/v1/dicom-web/workitems", json=_workitem())
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["00080050"]["Value"] == ["ACC-UPS-1"]
    assert body["00404041"]["Value"] == ["SCHEDULED"]
    uid = body["00081190"]["Value"][0].rsplit("/", 1)[-1]

    fetched = client.get(f"/api/v1/dicom-web/workitems/{uid}")
    assert fetched.status_code == 200
    assert fetched.json()["00100020"]["Value"] == ["P-1"]

    found = client.get("/api/v1/dicom-web/workitems",
                       params={"AccessionNumber": "ACC-UPS"}).json()
    assert [w["00080050"]["Value"][0] for w in found] == ["ACC-UPS-1"]

    # a search that matches nothing returns an empty list, not an error
    assert client.get("/api/v1/dicom-web/workitems",
                      params={"AccessionNumber": "NOPE"}).json() == []


def test_creating_the_same_work_item_twice_updates_it(client):
    first = client.post("/api/v1/dicom-web/workitems", json=_workitem()).json()
    again = client.post("/api/v1/dicom-web/workitems",
                        json=_workitem(station="MR_01", modality="MR")).json()

    assert first["00081190"]["Value"] == again["00081190"]["Value"]
    assert again["00400001"]["Value"] == ["MR_01"]
    assert again["00080060"]["Value"] == ["MR"]
    # still only one work item
    assert len(client.get("/api/v1/dicom-web/workitems").json()) == 1


def test_state_change_takes_the_item_out_of_the_worklist(client):
    created = client.post("/api/v1/dicom-web/workitems", json=_workitem()).json()
    uid = created["00081190"]["Value"][0].rsplit("/", 1)[-1]

    started = client.put(f"/api/v1/dicom-web/workitems/{uid}/state",
                         json={"state": "IN PROGRESS"})
    assert started.status_code == 200
    assert started.json()["00404041"]["Value"] == ["IN PROGRESS"]

    done = client.put(f"/api/v1/dicom-web/workitems/{uid}/state",
                      json={"state": "COMPLETED"})
    assert done.json()["00404041"]["Value"] == ["COMPLETED"]

    # the worklist a modality sees no longer contains it
    from pydicom.dataset import Dataset
    from mwl_broker import aggregation

    result = aggregation.collect(Dataset())
    assert not any(ds.AccessionNumber == "ACC-UPS-1" for ds in result.items)


def test_state_change_accepts_the_dicom_json_form(client):
    created = client.post("/api/v1/dicom-web/workitems", json=_workitem()).json()
    uid = created["00081190"]["Value"][0].rsplit("/", 1)[-1]

    body = {"00404041": {"vr": "CS", "Value": ["CANCELED"]}}
    result = client.put(f"/api/v1/dicom-web/workitems/{uid}/state", json=body)

    assert result.status_code == 200
    assert result.json()["00404041"]["Value"] == ["CANCELED"]


def test_validation_is_plain_language(client):
    missing = client.post("/api/v1/dicom-web/workitems", json={"00080060": {"Value": ["CT"]}})
    assert missing.status_code == 422
    assert "AccessionNumber" in missing.json()["detail"]

    created = client.post("/api/v1/dicom-web/workitems", json=_workitem()).json()
    uid = created["00081190"]["Value"][0].rsplit("/", 1)[-1]
    bad_state = client.put(f"/api/v1/dicom-web/workitems/{uid}/state",
                           json={"state": "NONSENSE"})
    assert bad_state.status_code == 422
    assert "unknown state" in bad_state.json()["detail"]

    assert client.get("/api/v1/dicom-web/workitems/does-not-exist").status_code == 404
    assert client.put("/api/v1/dicom-web/workitems/does-not-exist/state",
                      json={"state": "COMPLETED"}).status_code == 404


def test_mapped_hl7_fields_appear_in_the_work_item(client):
    """Extra attributes from a local HL7 mapping belong in the work item too."""
    client.post("/api/v1/hl7/field-maps", json={
        "segment": "ZDS", "field": 3, "target_tag": "RequestedContrastAgent"})
    orm = (
        "MSH|^~\\&|RIS|KH|MWLBROKER|KH|20260922100000||ORM^O01|MSG-UPS-1|P|2.4\r"
        "PID|1||P-9||Muster^Max||19800101|M\r"
        "ORC|NW|ACC-UPS-2\r"
        "OBR|1|ACC-UPS-2||CT\r"
        "ZDS|1.2.3.4.5|CT_01|BARIUM\r"
    )
    client.post("/api/v1/hl7/orm?dry_run=false", content=orm,
                headers={"Content-Type": "text/plain"})

    found = client.get("/api/v1/dicom-web/workitems",
                       params={"AccessionNumber": "ACC-UPS-2"}).json()

    assert found, "the item created from HL7 is not searchable"
    # compute the tag key from the keyword so the test cannot drift
    from pydicom.datadict import tag_for_keyword

    key = f"{tag_for_keyword('RequestedContrastAgent'):08X}"
    assert found[0][key]["Value"] == ["BARIUM"]


def test_work_item_uid_is_stable(client):
    created = client.post("/api/v1/dicom-web/workitems", json=_workitem()).json()
    uid = created["00081190"]["Value"][0].rsplit("/", 1)[-1]

    again = client.get(f"/api/v1/dicom-web/workitems/{uid}").json()
    assert again["00081190"]["Value"][0].endswith(uid)
    # and the module computes the same UID from the same row
    assert ups.get_workitem(uid) is not None


# ── the full attribute set ─────────────────────────────────────────────


def test_the_full_ups_attribute_set_is_served(client):
    body = _workitem()
    body.update({
        "00100030": {"vr": "DA", "Value": ["19401218"]},   # birth date
        "00100040": {"vr": "CS", "Value": ["M"]},          # sex
        "00400003": {"vr": "TM", "Value": ["093000"]},     # start time
        "00321060": {"vr": "LO", "Value": ["CT Thorax"]},  # requested procedure
    })
    created = client.post("/api/v1/dicom-web/workitems", json=body).json()

    assert created["00100030"]["Value"] == ["19401218"]
    assert created["00100040"]["Value"] == ["M"]
    assert created["00400003"]["Value"] == ["093000"]
    assert created["00321060"]["Value"] == ["CT Thorax"]
    assert created["00400007"]["Value"] == ["CT Thorax"]
    # the standard UPS state attribute is served next to the legacy one
    assert created["00741000"]["Value"] == ["SCHEDULED"]


def test_a_work_item_can_be_searched_by_its_standard_state(client):
    client.post("/api/v1/dicom-web/workitems", json=_workitem())

    found = client.get("/api/v1/dicom-web/workitems",
                       params={"UnifiedProcedureStepState": "SCHEDULED"}).json()

    assert [w["00080050"]["Value"][0] for w in found] == ["ACC-UPS-1"]


# ── searching the upstream sources ─────────────────────────────────────


def _upstream_dataset(accession="ACC-UP-1"):
    from pydicom.dataset import Dataset

    ds = Dataset()
    ds.AccessionNumber = accession
    ds.PatientID = "P-7"
    ds.PatientName = "Muster^Max"
    ds.StudyInstanceUID = "1.2.3.4"
    sps = Dataset()
    sps.ScheduledProcedureStepID = "SPS-7"
    sps.Modality = "CT"
    sps.ScheduledStationAETitle = "CT_01"
    sps.ScheduledProcedureStepStartDate = "20260930"
    ds.ScheduledProcedureStepSequence = [sps]
    return ds


def _seed_source(client) -> None:
    client.post("/api/v1/sources", json={
        "name": "ris-ups", "aet": "RIS_UPS", "host": "127.0.0.1", "port": 1,
        "calling_aet": "MWLBROKER", "charset": "ISO_IR 100",
        "enabled": True, "timeout_s": 1, "priority": 10,
    })


def test_search_can_include_the_upstream_sources(client, monkeypatch):
    from mwl_broker import aggregation

    _seed_source(client)
    monkeypatch.setattr(aggregation, "query_source",
                        lambda cfg, identifier: [_upstream_dataset()])

    found = client.get("/api/v1/dicom-web/workitems",
                       params={"AccessionNumber": "ACC-UP"}).json()

    assert [w["00080050"]["Value"][0] for w in found] == ["ACC-UP-1"]
    item = found[0]
    # flattened into the same shape a local work item has — no SPS sequence
    assert item["00400001"]["Value"] == ["CT_01"]
    assert item["00080060"]["Value"] == ["CT"]
    assert item["00400002"]["Value"] == ["20260930"]
    assert item["00401001"]["Value"] == ["SPS-7"]
    assert "00400100" not in item


def test_a_bare_listing_does_not_fan_out_to_the_sources(client, monkeypatch):
    from mwl_broker import aggregation

    _seed_source(client)
    called: list[str] = []
    monkeypatch.setattr(aggregation, "query_source",
                        lambda cfg, identifier: called.append(cfg.name) or [])

    client.get("/api/v1/dicom-web/workitems")           # no DICOM keys
    assert called == []

    client.get("/api/v1/dicom-web/workitems", params={"Modality": "CT"})
    assert called == ["ris-ups"]                        # a real query does fan out


# ── subscriptions and the event channel ────────────────────────────────


def test_a_subscription_can_be_created_listed_and_removed(client):
    created = client.post("/api/v1/dicom-web/workitems/subscriptions",
                          json={"subscriber_aet": "ct_01", "deletion_lock": True})
    assert created.status_code == 201, created.text
    assert created.json()["subscriber_aet"] == "CT_01"   # normalised to upper case

    listed = client.get("/api/v1/dicom-web/workitems/subscriptions").json()
    assert [s["subscriber_aet"] for s in listed] == ["CT_01"]

    assert client.delete("/api/v1/dicom-web/workitems/subscriptions/CT_01").status_code == 204
    assert client.get("/api/v1/dicom-web/workitems/subscriptions").json() == []
    assert client.delete("/api/v1/dicom-web/workitems/subscriptions/CT_01").status_code == 404


def test_a_subscriber_receives_state_changes_on_the_event_channel(client):
    created = client.post("/api/v1/dicom-web/workitems", json=_workitem()).json()
    uid = created["00081190"]["Value"][0].rsplit("/", 1)[-1]
    client.post("/api/v1/dicom-web/workitems/subscriptions",
                json={"subscriber_aet": "CT_01"})

    with client.websocket_connect(
            "/api/v1/dicom-web/workitems/ws?subscriber=CT_01") as websocket:
        client.put(f"/api/v1/dicom-web/workitems/{uid}/state",
                   json={"state": "IN PROGRESS"})
        event = websocket.receive_json()

    assert event["event"] == "workitem-state-change"
    assert event["workitem_uid"] == uid
    assert event["state"] == "IN PROGRESS"
    assert event["workitem"]["00404041"]["Value"] == ["IN PROGRESS"]


def test_a_subscription_can_be_scoped_to_one_work_item(client):
    import asyncio

    class _ImmediateLoop:
        """Runs the callback at once — a stand-in for the event loop."""

        def call_soon_threadsafe(self, callback, *args):
            callback(*args)

    client.post("/api/v1/dicom-web/workitems/subscriptions",
                json={"subscriber_aet": "CT_01", "workitem_uid": "UID-1"})
    client.post("/api/v1/dicom-web/workitems/subscriptions",
                json={"subscriber_aet": "MR_01"})           # all work items

    scoped, everywhere = asyncio.Queue(), asyncio.Queue()
    ups.hub.bind_loop(_ImmediateLoop())
    ups.hub.subscribe("CT_01", scoped)
    ups.hub.subscribe("MR_01", everywhere)

    ups.hub.publish({"event": "workitem-state-change", "workitem_uid": "UID-2"})

    assert scoped.empty()               # scoped to UID-1, not interested in UID-2
    assert everywhere.qsize() == 1      # subscribed to every work item


def test_a_subscription_needs_a_subscriber(client):
    assert client.post("/api/v1/dicom-web/workitems/subscriptions",
                       json={"subscriber_aet": ""}).status_code == 422


# ── Randfälle, die die Oberfläche und die Ereignisse betreffen ──────────


def test_a_disabled_item_without_a_known_state_reads_as_canceled(client):
    """`sps_status` is free text — an unknown value must not invent a state."""
    from mwl_broker.db import session_factory
    from mwl_broker.models import LocalWorklistItem

    with session_factory()() as s:
        s.add(LocalWorklistItem(accession="ACC-ODD", patient_id="P-1",
                                sps_status="NONSENSE", enabled=False))
        s.commit()

    found = client.get("/api/v1/dicom-web/workitems",
                       params={"AccessionNumber": "ACC-ODD"}).json()

    assert found[0]["00404041"]["Value"] == ["CANCELED"]


def test_the_search_ignores_an_empty_query_value(client):
    client.post("/api/v1/dicom-web/workitems", json=_workitem())

    assert ups._pushdown_clauses({"00080050": ""}) == []
    assert len(ups.search({"00080050": ""})) == 1        # still matches everything


def test_the_search_stops_at_the_limit(client):
    for n in range(3):
        client.post("/api/v1/dicom-web/workitems",
                    json=_workitem(accession=f"ACC-LIM-{n}"))

    assert len(client.get("/api/v1/dicom-web/workitems",
                          params={"AccessionNumber": "ACC-LIM", "limit": 2}).json()) == 2


def test_an_upstream_item_is_flattened_with_its_start_time(client, monkeypatch):
    """The MWL answer carries a Scheduled Procedure Step sequence; the work item
    is flat — including the start time, or the reader sees the wrong slot."""
    from mwl_broker import aggregation

    _seed_source(client)
    dataset = _upstream_dataset()
    dataset.ScheduledProcedureStepSequence[0].ScheduledProcedureStepStartTime = "093000"
    monkeypatch.setattr(aggregation, "query_source", lambda cfg, ident: [dataset])

    found = client.get("/api/v1/dicom-web/workitems",
                       params={"AccessionNumber": "ACC-UP"}).json()

    assert found[0]["00400003"]["Value"] == ["093000"]
    assert found[0]["00741000"]["Value"] == ["SCHEDULED"]


def test_a_flattened_item_survives_empty_values(client):
    from pydicom.dataset import Dataset

    workitem = ups.dataset_to_workitem(Dataset())

    assert workitem["00080050"]["Value"] == [""]
    assert workitem["00404041"]["Value"] == ["SCHEDULED"]
    assert "00100010" not in workitem                   # nothing to invent


def test_a_subscription_needs_a_subscriber_at_module_level(client):
    with pytest.raises(ValueError, match="subscriber_aet is required"):
        ups.upsert_subscription("   ")


def test_the_event_channel_needs_a_subscription(client):
    """PS3.18 §11.6: the subscription comes first — no subscription, no events."""
    import asyncio

    assert ups.hub.subscribe("NOT_SUBSCRIBED", asyncio.Queue()) is False


def test_the_event_hub_refuses_more_than_its_limit(client, monkeypatch):
    import asyncio

    client.post("/api/v1/dicom-web/workitems/subscriptions",
                json={"subscriber_aet": "CT_01"})
    client.post("/api/v1/dicom-web/workitems/subscriptions",
                json={"subscriber_aet": "MR_01"})
    monkeypatch.setattr(ups._EventHub, "MAX_SUBSCRIBERS", 1)

    assert ups.hub.subscribe("CT_01", asyncio.Queue()) is True
    assert ups.hub.subscribe("MR_01", asyncio.Queue()) is False


def test_publishing_without_a_loop_and_to_a_dead_loop_is_harmless(client):
    """A state change may happen before the event loop is bound (or during
    shutdown) — it must never raise on the DIMSE/request thread."""
    import asyncio

    ups.hub.reset_for_tests()                                # explicitly no loop
    ups.hub.publish({"event": "x", "workitem_uid": "1"})     # no loop bound

    class _DeadLoop:
        def call_soon_threadsafe(self, *_args):
            raise RuntimeError("loop is closed")

    client.post("/api/v1/dicom-web/workitems/subscriptions",
                json={"subscriber_aet": "CT_01"})
    ups.hub.bind_loop(_DeadLoop())
    assert ups.hub.subscribe("CT_01", asyncio.Queue()) is True

    ups.hub.publish({"event": "x", "workitem_uid": "1"})     # must not raise


def test_removing_an_unknown_subscriber_is_a_no_op(client):
    import asyncio

    ups.hub.unsubscribe("NEVER_THERE", asyncio.Queue())
    ups.hub.forget("NEVER_THERE")
    assert ups.delete_subscription("NEVER_THERE") is False


def test_an_unknown_step_status_reads_as_scheduled(client):
    """`ScheduledProcedureStepStatus` is free text — an unknown value must not
    invent a state the standard does not have."""
    from pydicom.dataset import Dataset

    ds = Dataset()
    ds.AccessionNumber = "ACC-UP-9"
    sps = Dataset()
    sps.ScheduledProcedureStepStatus = "WHATEVER"
    ds.ScheduledProcedureStepSequence = [sps]

    assert ups.dataset_to_workitem(ds)["00404041"]["Value"] == ["SCHEDULED"]


def test_the_search_skips_local_items_that_do_not_match(client):
    client.post("/api/v1/dicom-web/workitems", json=_workitem(accession="ACC-ONE"))

    assert ups.search({"00080050": "ACC-TWO"}) == []


def test_the_upstream_search_stops_at_the_limit(client, monkeypatch):
    from mwl_broker import aggregation

    _seed_source(client)
    monkeypatch.setattr(aggregation, "query_source", lambda cfg, ident: [
        _upstream_dataset("ACC-UP-1"), _upstream_dataset("ACC-UP-2")])

    found = ups.search({"00080050": "ACC-UP"}, limit=1, include_upstream=True)

    assert [w["00080050"]["Value"][0] for w in found] == ["ACC-UP-1"]


def test_set_state_survives_an_item_that_disappeared(client):
    """Between finding the row and loading it another request may have deleted
    it — that is a 404, not a crash."""
    from mwl_broker.models import LocalWorklistItem

    ghost = LocalWorklistItem(id=999999, accession="GONE", sps_id="1")
    monkeypatch = None
    original = ups._find
    ups._find = lambda uid: ghost                      # type: ignore[assignment]
    try:
        with pytest.raises(LookupError):
            ups.set_state("1.2.840.113619.6.500.999999", "COMPLETED")
    finally:
        ups._find = original                           # type: ignore[assignment]
