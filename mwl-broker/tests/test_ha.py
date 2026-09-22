"""High availability (B1): the spool claim and the instance heartbeat.

Two broker instances on one database and one spool volume are only safe if the
*work* is not done twice. These tests pin the two mechanisms that make that true:

* `spool.claim_items` — one claim per entry, atomically, with a lease that an
  expired instance gives back.
* `instances` — a heartbeat per process, so the operator sees who is running.

The decisive test is `test_two_instances_deliver_every_entry_exactly_once`: it
runs two workers concurrently over the same queue and counts deliveries per
instance UID. Without the claim it fails with duplicates.
"""
import threading
from datetime import datetime, timedelta, timezone

from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, generate_uid

from mwl_broker import cstore, health_checks, instances, settings_service, spool
from mwl_broker.config import get_settings
from mwl_broker.db import get_session, session_factory
from mwl_broker.models import BrokerInstance, PacsTarget, StoreSpool

INSTANCE_A = "broker-a"
INSTANCE_B = "broker-b"


def _dataset(accession="ACC-HA", sop_uid: str | None = None) -> FileDataset:
    sop_uid = sop_uid or generate_uid()
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = CTImageStorage
    meta.MediaStorageSOPInstanceUID = sop_uid
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset("ha.dcm", {}, file_meta=meta, preamble=b"\0" * 128)
    ds.SOPClassUID = CTImageStorage
    ds.SOPInstanceUID = sop_uid
    ds.AccessionNumber = accession
    ds.StudyInstanceUID = generate_uid()
    ds.PatientID = "P1"
    ds.PatientName = "Mueller^Hans"
    ds.Modality = "CT"
    return ds


def _target(name="pacs", host="127.0.0.1", port=1) -> int:
    with session_factory()() as s:
        row = PacsTarget(name=name, aet="PACS", host=host, port=port,
                         calling_aet="MWLBROKER", is_default=True, enabled=True)
        s.add(row)
        s.commit()
        return row.id


def _queue(count: int) -> list[str]:
    """Put `count` instances into the spool (as if the target were down)."""
    target_id = _target()
    sop_uids = []
    for index in range(count):
        ds = _dataset(accession=f"ACC-HA-{index}")
        spool.enqueue(ds, None, target_id, "pacs", "connection refused")
        sop_uids.append(str(ds.SOPInstanceUID))
    return sop_uids


def _rows() -> list[StoreSpool]:
    with session_factory()() as s:
        return s.query(StoreSpool).order_by(StoreSpool.id).all()


def _instance_row(instance_id: str, age_s: int = 0) -> None:
    when = datetime.now(timezone.utc) - timedelta(seconds=age_s)
    with session_factory()() as s:
        s.add(BrokerInstance(instance_id=instance_id, started_at=when, last_seen=when,
                             version="1.0.0", hostname="test", pid=1))
        s.commit()


# ── der Claim: ein Eintrag, eine Zustellung ───────────────────────────────


def test_a_claimed_entry_is_not_claimed_twice():
    _queue(3)

    first = spool.claim_items(limit=3, instance_id=INSTANCE_A)
    second = spool.claim_items(limit=3, instance_id=INSTANCE_B)

    assert len(first) == 3
    assert second == [], "the second instance must not see claimed entries"


def test_two_instances_share_the_queue():
    _queue(6)

    a = spool.claim_items(limit=3, instance_id=INSTANCE_A)
    b = spool.claim_items(limit=3, instance_id=INSTANCE_B)

    assert len(a) == 3 and len(b) == 3
    assert set(a).isdisjoint(b), "each entry belongs to exactly one instance"


def test_an_expired_lease_can_be_taken_over():
    """The instance that held the claim died — the entry returns to the pool."""
    _queue(1)
    spool.claim_items(limit=1, instance_id=INSTANCE_A)
    assert spool.claim_items(limit=1, instance_id=INSTANCE_B) == []

    with session_factory()() as s:
        row = s.query(StoreSpool).one()
        row.lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        s.commit()

    assert len(spool.claim_items(limit=1, instance_id=INSTANCE_B)) == 1


def test_the_claim_is_released_after_a_success(monkeypatch):
    _queue(1)
    monkeypatch.setattr(cstore, "send_store", lambda ds, target: None)

    spool.run_once(limit=5, instance_id=INSTANCE_A)

    row = _rows()[0]
    assert row.status == "sent"
    assert row.claimed_by == "" and row.lease_until is None


def test_the_claim_is_released_after_a_failure(monkeypatch):
    _queue(1)

    def boom(_ds, _target):
        raise ConnectionError("still down")

    monkeypatch.setattr(cstore, "send_store", boom)
    spool.run_once(limit=5, instance_id=INSTANCE_A)

    row = _rows()[0]
    assert row.status == "failed"
    assert row.claimed_by == "", "a failed entry must be claimable again later"


def test_forward_leaves_an_entry_that_another_instance_holds():
    """Direct calls (operator retry, a second worker) must not steal work."""
    _queue(1)
    item_id = spool.claim_items(limit=1, instance_id=INSTANCE_A)[0]
    sent: list[str] = []

    import mwl_broker.cstore as cstore_module
    original = cstore_module.send_store
    cstore_module.send_store = lambda ds, target: sent.append(str(ds.SOPInstanceUID))
    try:
        assert spool.forward(item_id) == spool.STATUS_CLAIMED
    finally:
        cstore_module.send_store = original

    assert sent == [], "the other instance's entry must not be delivered here"


def test_the_operator_retry_frees_a_stale_claim():
    """A lease must never block the operator's 'try again'."""
    _queue(1)
    item_id = spool.claim_items(limit=1, instance_id=INSTANCE_A)[0]

    assert spool.retry(item_id) is True

    row = _rows()[0]
    assert row.claimed_by == "" and row.lease_until is None
    assert len(spool.claim_items(limit=1, instance_id=INSTANCE_B)) == 1


def test_stats_show_what_is_being_worked_on():
    _queue(2)
    spool.claim_items(limit=2, instance_id=INSTANCE_A)

    assert spool.stats()["claimed"] == 2


def test_two_instances_deliver_every_entry_exactly_once(monkeypatch):
    """The reason the claim exists — run two workers at the same time."""
    count = 12
    sop_uids = _queue(count)
    delivered: list[str] = []
    lock = threading.Lock()

    def send(ds, _target):
        # a tiny delay makes the race real instead of theoretical
        with lock:
            delivered.append(str(ds.SOPInstanceUID))

    monkeypatch.setattr(cstore, "send_store", send)
    settings_service.set_value("spool_lease_s", "300")

    start = threading.Barrier(2)
    errors: list[str] = []

    def worker(instance_id: str):
        start.wait(timeout=10)
        try:
            for _ in range(20):                      # keep polling, like the loop
                spool.run_once(limit=4, instance_id=instance_id)
        except Exception as exc:  # noqa: BLE001 - that is what we are testing
            errors.append(repr(exc))

    threads = [threading.Thread(target=worker, args=(name,))
               for name in (INSTANCE_A, INSTANCE_B)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert errors == []
    assert sorted(delivered) == sorted(sop_uids), "every instance exactly once"
    assert len(delivered) == count, f"{count - len(delivered)} missing"
    assert len(set(delivered)) == count, "an instance was delivered twice"


# ── Instanzen: Sichtbarkeit ───────────────────────────────────────────────


def test_the_heartbeat_creates_one_row_and_refreshes_it(client):
    instances.heartbeat()
    instances.heartbeat()

    rows = instances.known()
    assert len(rows) == 1
    assert rows[0]["instance_id"] == instances.instance_id()
    assert rows[0]["active"] is True and rows[0]["current"] is True


def test_a_second_instance_is_visible_and_warned_about(client):
    instances.heartbeat()
    _instance_row(INSTANCE_B)

    body = client.get("/api/v1/status").json()

    assert body["instance_id"] == instances.instance_id()
    assert body["instances_active"] == 2
    assert {row["instance_id"] for row in body["instances"]} == {
        instances.instance_id(), INSTANCE_B}

    codes = [f["code"] for f in client.get("/api/v1/health/config").json()["findings"]]
    assert "ha_multiple_instances" in codes


def test_a_single_instance_produces_no_ha_finding(client):
    """A normal installation must not look like a problem."""
    instances.heartbeat()

    codes = [f["code"] for f in client.get("/api/v1/health/config").json()["findings"]]

    assert not [code for code in codes if code.startswith("ha_")], codes


def test_an_instance_that_stopped_is_reported(client):
    """'Where did the other instance go?' is exactly what the operator asks."""
    instances.heartbeat()
    _instance_row(INSTANCE_B, age_s=instances.timeout_s() + 30)

    body = client.get("/api/v1/health/config").json()
    finding = next(f for f in body["findings"] if f["code"] == "ha_instance_gone")

    assert finding["severity"] == "warning"
    assert finding["details"]["instance_id"] == INSTANCE_B
    assert INSTANCE_B in finding["message"]


def test_the_instance_name_can_be_configured(client):
    settings_service.set_value("instance_id", "ct-broker-01")
    instances.reset_for_tests()

    try:
        assert instances.instance_id() == "ct-broker-01"
        assert client.get("/api/v1/status").json()["instance_id"] == "ct-broker-01"
    finally:
        instances.reset_for_tests()


def test_stale_instance_rows_are_forgotten(client):
    """A decommissioned host must not stay in the list forever."""
    instances.heartbeat()
    _instance_row("old-host", age_s=90000)

    assert instances.forget_stale(older_than_s=86400) == 1
    assert [row["instance_id"] for row in instances.known()] == [instances.instance_id()]


def test_the_spool_stats_expose_the_claim_fields(client):
    """The UI shows 'claimed by' — a stuck claim must be diagnosable."""
    _queue(1)
    spool.claim_items(limit=1, instance_id=INSTANCE_A)

    body = client.get("/api/v1/spool/stats").json()

    assert body["claimed"] == 1
