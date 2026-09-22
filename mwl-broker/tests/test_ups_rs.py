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
