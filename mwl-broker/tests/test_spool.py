"""C-STORE spool: store-and-forward, retries, dead letters, capacity."""
from datetime import datetime, timedelta, timezone

from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, generate_uid

from mwl_broker import cstore, settings_service, spool
from mwl_broker.db import session_factory
from mwl_broker.models import PacsTarget, StoreSpool


def _dataset(accession="ACC-1", sop_uid: str | None = None) -> FileDataset:
    sop_uid = sop_uid or generate_uid()
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = CTImageStorage
    meta.MediaStorageSOPInstanceUID = sop_uid
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset("spool.dcm", {}, file_meta=meta, preamble=b"\0" * 128)
    ds.SOPClassUID = CTImageStorage
    ds.SOPInstanceUID = sop_uid
    ds.AccessionNumber = accession
    ds.StudyInstanceUID = generate_uid()
    ds.PatientID = "P1"
    ds.PatientName = "Mueller^Hans"
    ds.Modality = "CT"
    return ds


def _target(name="pacs", host="127.0.0.1", port=1, enabled=True) -> int:
    with session_factory()() as s:
        row = PacsTarget(name=name, aet="PACS", host=host, port=port,
                         calling_aet="MWLBROKER", is_default=True, enabled=enabled)
        s.add(row)
        s.commit()
        return row.id


def _rows() -> list[StoreSpool]:
    with session_factory()() as s:
        return s.query(StoreSpool).order_by(StoreSpool.id).all()


# ── enqueue ────────────────────────────────────────────────────────────


def test_enqueue_writes_the_payload_and_the_row():
    target_id = _target()
    ds = _dataset()

    assert spool.enqueue(ds, None, target_id, "pacs", "connection refused") == "queued"

    rows = _rows()
    assert len(rows) == 1
    row = rows[0]
    assert row.status == "queued"
    assert row.sop_instance_uid == str(ds.SOPInstanceUID)
    assert row.accession == "ACC-1"
    assert row.payload_bytes > 0
    assert row.last_error == "connection refused"
    # the payload really is on disk and readable
    stored = spool._read_payload(row.payload_path)
    assert str(stored.SOPInstanceUID) == str(ds.SOPInstanceUID)
    assert str(stored.PatientName) == "Mueller^Hans"


def test_enqueue_deduplicates_by_sop_instance_uid():
    target_id = _target()
    ds = _dataset()

    assert spool.enqueue(ds, None, target_id, "pacs", "boom") == "queued"
    assert spool.enqueue(ds, None, target_id, "pacs", "boom") == "duplicate"
    assert spool.enqueue(ds, None, target_id, "pacs", "boom") == "duplicate"

    assert len(_rows()) == 1


def test_enqueue_is_disabled_by_setting():
    target_id = _target()
    settings_service.set_value("spool_enabled", "false")

    assert spool.enqueue(_dataset(), None, target_id, "pacs", "boom") == "disabled"
    assert _rows() == []


def test_enqueue_refuses_when_the_spool_is_full():
    target_id = _target()
    settings_service.set_value("spool_max_items", "1")
    assert spool.enqueue(_dataset(), None, target_id, "pacs", "boom") == "queued"

    assert spool.enqueue(_dataset(), None, target_id, "pacs", "boom") == "full"
    assert len(_rows()) == 1


def test_enqueue_refuses_when_the_byte_budget_is_exhausted():
    target_id = _target()
    settings_service.set_value("spool_max_bytes", "1048576")  # 1 MiB minimum
    settings_service.set_value("spool_max_items", "1000")
    ds = _dataset()
    # pretend the spool already holds a large instance
    with session_factory()() as s:
        s.add(StoreSpool(sop_instance_uid="1.2.3", target_id=target_id, status="queued",
                         payload_bytes=2_000_000))
        s.commit()

    assert spool.enqueue(ds, None, target_id, "pacs", "boom") == "full"


def test_enqueue_rejects_an_instance_without_sop_uid():
    target_id = _target()
    ds = Dataset()
    ds.AccessionNumber = "ACC-X"

    assert spool.enqueue(ds, None, target_id, "pacs", "boom") == "error"


def test_enqueue_reports_a_write_failure(monkeypatch):
    target_id = _target()
    settings_service.set_value("spool_dir", "/proc/definitely-not-writable")

    assert spool.enqueue(_dataset(), None, target_id, "pacs", "boom") == "error"
    assert _rows() == []


# ── forwarding ─────────────────────────────────────────────────────────


def test_forward_marks_sent_and_removes_the_payload(monkeypatch):
    target_id = _target()
    ds = _dataset()
    spool.enqueue(ds, None, target_id, "pacs", "boom")
    sent: list[str] = []
    monkeypatch.setattr(cstore, "send_store", lambda d, t: sent.append(str(d.SOPInstanceUID)))

    outcome = spool.forward(_rows()[0].id)

    assert outcome == "sent"
    assert sent == [str(ds.SOPInstanceUID)]
    row = _rows()[0]
    assert row.status == "sent"
    assert row.payload_path == ""
    assert row.sent_at is not None
    # the payload is gone, the row stays as a duplicate guard
    import os
    assert not os.path.exists(spool._payload_path(str(ds.SOPInstanceUID)))


def test_forward_schedules_a_backoff_on_failure(monkeypatch):
    settings_service.set_value("spool_backoff_s", "60")
    target_id = _target()
    spool.enqueue(_dataset(), None, target_id, "pacs", "boom")

    def boom(_ds, _target):
        raise ConnectionError("still down")

    monkeypatch.setattr(cstore, "send_store", boom)

    assert spool.forward(_rows()[0].id) == "failed"
    row = _rows()[0]
    assert row.attempts == 1
    assert row.last_error == "still down"
    assert row.next_attempt_at is not None
    # ~60 s in the future (naive datetimes come back from sqlite)
    delta = (row.next_attempt_at.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc))
    assert 30 < delta.total_seconds() <= 65


def test_backoff_grows_exponentially(monkeypatch):
    settings_service.set_value("spool_backoff_s", "60")
    target_id = _target()
    spool.enqueue(_dataset(), None, target_id, "pacs", "boom")
    monkeypatch.setattr(cstore, "send_store",
                        lambda *_: (_ for _ in ()).throw(ConnectionError("down")))

    item_id = _rows()[0].id
    delays = []
    for _ in range(3):
        spool.forward(item_id)
        row = _rows()[0]
        if row.next_attempt_at is None:
            break
        delta = row.next_attempt_at.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)
        delays.append(round(delta.total_seconds()))
        # simulate the backoff having elapsed
        with session_factory()() as s:
            s.get(StoreSpool, item_id).next_attempt_at = datetime.now(timezone.utc)
            s.commit()

    assert delays[0] < delays[1] < delays[2]


def test_forward_gives_up_after_max_attempts(monkeypatch):
    settings_service.set_value("spool_max_attempts", "2")
    target_id = _target()
    spool.enqueue(_dataset(), None, target_id, "pacs", "boom")
    monkeypatch.setattr(cstore, "send_store",
                        lambda *_: (_ for _ in ()).throw(ConnectionError("down")))
    item_id = _rows()[0].id

    assert spool.forward(item_id) == "failed"
    with session_factory()() as s:
        s.get(StoreSpool, item_id).next_attempt_at = datetime.now(timezone.utc)
        s.commit()
    assert spool.forward(item_id) == "dead"

    assert _rows()[0].status == "dead"
    assert spool.stats()["dead"] == 1


def test_forward_turns_a_missing_target_into_a_dead_letter():
    target_id = _target()
    spool.enqueue(_dataset(), None, target_id, "pacs", "boom")
    with session_factory()() as s:
        s.delete(s.get(PacsTarget, target_id))
        s.commit()

    assert spool.forward(_rows()[0].id) == "dead"
    assert "target is missing" in _rows()[0].last_error


def test_forward_turns_an_unreadable_payload_into_a_dead_letter():
    target_id = _target()
    spool.enqueue(_dataset(), None, target_id, "pacs", "boom")
    item_id = _rows()[0].id
    with session_factory()() as s:
        s.get(StoreSpool, item_id).payload_path = "/nonexistent/file.dcm"
        s.commit()

    assert spool.forward(item_id) == "dead"
    assert "unreadable" in _rows()[0].last_error


def test_due_items_respect_the_backoff():
    target_id = _target()
    spool.enqueue(_dataset(), None, target_id, "pacs", "boom")
    item_id = _rows()[0].id

    assert spool.due_items() == [item_id]
    with session_factory()() as s:
        s.get(StoreSpool, item_id).next_attempt_at = datetime.now(timezone.utc) + timedelta(hours=1)
        s.commit()

    assert spool.due_items() == []


def test_run_once_forwards_everything_that_is_due(monkeypatch):
    target_id = _target()
    for index in range(3):
        spool.enqueue(_dataset(accession=f"ACC-{index}"), None, target_id, "pacs", "boom")
    monkeypatch.setattr(cstore, "send_store", lambda *_: None)

    result = spool.run_once()

    assert result == {"attempted": 3, "sent": 3, "failed": 0, "dead": 0,
                      "skipped": 0}
    assert spool.stats()["sent"] == 3
    assert spool.stats()["open"] == 0


def test_run_once_is_a_noop_when_disabled():
    settings_service.set_value("spool_enabled", "false")
    assert spool.run_once()["disabled"] == 1


def test_worker_stops(monkeypatch):
    import threading
    import time

    settings_service.set_value("spool_poll_s", "1")
    calls: list[int] = []
    monkeypatch.setattr(spool, "run_once", lambda *_: calls.append(1) or {})

    stop = threading.Event()
    thread = threading.Thread(target=spool.worker, args=(stop,), daemon=True)
    thread.start()
    deadline = time.time() + 3
    while not calls and time.time() < deadline:
        time.sleep(0.02)
    stop.set()
    thread.join(timeout=2)

    assert calls, "the worker never ran"
    assert not thread.is_alive()


# ── operator actions ───────────────────────────────────────────────────


def test_retry_requeues_an_entry(monkeypatch):
    target_id = _target()
    spool.enqueue(_dataset(), None, target_id, "pacs", "boom")
    monkeypatch.setattr(cstore, "send_store",
                        lambda *_: (_ for _ in ()).throw(ConnectionError("down")))
    item_id = _rows()[0].id
    spool.forward(item_id)
    assert _rows()[0].status == "failed"

    assert spool.retry(item_id) is True

    row = _rows()[0]
    assert row.status == "queued" and row.attempts == 0
    assert row.next_attempt_at is not None


def test_retry_refuses_an_unknown_or_delivered_entry(monkeypatch):
    target_id = _target()
    spool.enqueue(_dataset(), None, target_id, "pacs", "boom")
    monkeypatch.setattr(cstore, "send_store", lambda *_: None)
    item_id = _rows()[0].id
    spool.forward(item_id)

    assert spool.retry(999) is False
    assert spool.retry(item_id) is False  # already delivered


def test_retry_all_requeues_failed_and_dead(monkeypatch):
    settings_service.set_value("spool_max_attempts", "1")
    target_id = _target()
    for index in range(3):
        spool.enqueue(_dataset(accession=f"ACC-{index}"), None, target_id, "pacs", "boom")
    monkeypatch.setattr(cstore, "send_store",
                        lambda *_: (_ for _ in ()).throw(ConnectionError("down")))
    spool.run_once()
    assert spool.stats()["dead"] == 3

    assert spool.retry_all() == 3

    assert spool.stats()["queued"] == 3 and spool.stats()["dead"] == 0


def test_discard_removes_the_entry_and_the_payload():
    import os

    target_id = _target()
    ds = _dataset()
    spool.enqueue(ds, None, target_id, "pacs", "boom")
    item_id = _rows()[0].id
    path = spool._payload_path(str(ds.SOPInstanceUID))
    assert os.path.exists(path)

    assert spool.discard(item_id, "duplicate of a manual import") is True

    assert _rows() == []
    assert not os.path.exists(path)
    assert spool.discard(item_id, "again") is False


def test_purge_drops_delivered_entries_after_retention(monkeypatch):
    settings_service.set_value("spool_retention_s", "60")
    target_id = _target()
    spool.enqueue(_dataset(), None, target_id, "pacs", "boom")
    monkeypatch.setattr(cstore, "send_store", lambda *_: None)
    spool.forward(_rows()[0].id)

    assert spool.purge() == 0  # just delivered

    with session_factory()() as s:
        s.get(StoreSpool, _rows()[0].id).sent_at = datetime.now(timezone.utc) - timedelta(hours=2)
        s.commit()
    assert spool.purge() == 1
    assert _rows() == []


# ── views ──────────────────────────────────────────────────────────────


def test_stats_and_capacity(monkeypatch):
    target_id = _target()
    spool.enqueue(_dataset(), None, target_id, "pacs", "boom")
    monkeypatch.setattr(cstore, "send_store", lambda *_: None)
    spool.enqueue(_dataset(), None, target_id, "pacs", "boom")
    spool.forward(_rows()[0].id)

    data = spool.stats()

    assert data["sent"] == 1 and data["open"] == 1 and data["queued"] == 1
    assert data["bytes"] > 0
    assert data["oldest_age_s"] is not None
    assert data["capacity"]["items"] == 1
    assert data["capacity"]["full"] is False
    assert data["enabled"] is True and data["accept_when_queued"] is True


def test_items_filter_by_status():
    target_id = _target()
    spool.enqueue(_dataset(accession="ACC-1"), None, target_id, "pacs", "boom")

    assert len(spool.items()) == 1
    assert len(spool.items(status="queued")) == 1
    assert spool.items(status="dead") == []
    entry = spool.items()[0]
    assert entry["accession"] == "ACC-1"
    assert entry["target_name"] == "pacs"
    assert "Mueller" not in str(entry)  # no PHI in the operator view
