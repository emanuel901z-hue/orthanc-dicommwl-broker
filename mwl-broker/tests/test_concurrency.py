"""What the load test found: two write paths that lost a race.

At shift start many modalities query at once. Two of them failing on the same
dead source, or two of them writing the same cache snapshot, used to collide on a
primary/unique key — and inside the C-FIND handler that IntegrityError was
answered to the modality as a DIMSE failure (`0xC311`), i.e. a worklist query the
broker could have served.

The mechanism is `db.upsert` (INSERT … ON CONFLICT); these tests pin both the
mechanism and the two call sites. See `docs/loadtest.md`.
"""
import threading

from sqlalchemy import select

from mwl_broker import breaker, cache, db
from mwl_broker.db import session_factory
from mwl_broker.models import MwlSource, SourceBreaker, WorklistCache

from pydicom.dataset import Dataset


def _source(name: str = "ris-a") -> int:
    with session_factory()() as s:
        row = MwlSource(name=name, aet="RIS_A", host="127.0.0.1", port=11112,
                        calling_aet="MWLBROKER", charset="ISO_IR 100",
                        enabled=True, timeout_s=1, priority=10)
        s.add(row)
        s.commit()
        s.refresh(row)
        return row.id


def _item(accession: str, sps: str = "SPS-1") -> Dataset:
    ds = Dataset()
    ds.AccessionNumber = accession
    ds.PatientID = "PAT-1"
    ds.StudyInstanceUID = f"1.2.3.{accession}"
    ds.Modality = "CT"
    ds.ScheduledProcedureStepSequence = [Dataset()]
    ds.ScheduledProcedureStepSequence[0].ScheduledProcedureStepID = sps
    return ds


# ── das Werkzeug ──────────────────────────────────────────────────────────


def test_upsert_creates_then_updates_the_same_row():
    """The whole point: the second writer must not raise."""
    source_id = _source()
    with session_factory()() as s:
        for _ in range(2):
            db.upsert(s, SourceBreaker,
                      {"source_id": source_id, "failures": 1, "state": "closed"},
                      index_elements=[SourceBreaker.source_id],
                      update_values={"failures": SourceBreaker.failures + 1})
        s.commit()

    with session_factory()() as s:
        rows = s.scalars(select(SourceBreaker)).all()
    assert len(rows) == 1
    assert rows[0].failures == 2


def test_upsert_updates_named_columns_from_the_new_row():
    """`update_columns` takes the incoming value (`excluded.<column>`)."""
    source_id = _source()
    payload = {"source_id": source_id, "dedupe_key": "k", "accession": "ACC-1",
               "modality": "CT", "payload": {"json": "{}"}}
    with session_factory()() as s:
        db.upsert(s, WorklistCache, payload,
                  index_elements=[WorklistCache.source_id, WorklistCache.dedupe_key],
                  update_columns=["accession", "modality"])
        db.upsert(s, WorklistCache, {**payload, "accession": "ACC-2", "modality": "MR"},
                  index_elements=[WorklistCache.source_id, WorklistCache.dedupe_key],
                  update_columns=["accession", "modality"])
        s.commit()

    with session_factory()() as s:
        row = s.scalars(select(WorklistCache)).one()
    assert (row.accession, row.modality) == ("ACC-2", "MR")


def test_upsert_takes_a_whole_batch():
    """The cache writes a snapshot in one statement, not row by row."""
    source_id = _source()
    rows = [{"source_id": source_id, "dedupe_key": f"k{i}", "accession": f"ACC-{i}",
             "payload": {"json": "{}"}} for i in range(50)]
    with session_factory()() as s:
        for _ in range(2):
            db.upsert(s, WorklistCache, rows,
                      index_elements=[WorklistCache.source_id, WorklistCache.dedupe_key],
                      update_columns=["accession"])
        s.commit()

    with session_factory()() as s:
        assert len(s.scalars(select(WorklistCache)).all()) == 50


# ── die beiden Aufrufstellen ──────────────────────────────────────────────


def test_concurrent_failures_do_not_collide_on_the_breaker_row():
    """Eight modalities failing on one dead source: one row, eight failures.

    Before the fix this raised `IntegrityError: source_breaker_pkey` out of the
    C-FIND handler — the modality got `0xC311` instead of a worklist.
    """
    source_id = _source()
    threads = 8
    start = threading.Barrier(threads)
    errors: list[str] = []

    def fail():
        start.wait(timeout=10)
        try:
            breaker.record_failure(source_id, "boom")
        except Exception as exc:  # noqa: BLE001 - that is what we are testing
            errors.append(repr(exc))

    workers = [threading.Thread(target=fail) for _ in range(threads)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=30)

    assert errors == []
    with session_factory()() as s:
        rows = s.scalars(select(SourceBreaker)).all()
    assert len(rows) == 1, "a breaker row per thread would mean the race is back"
    assert rows[0].failures == threads, "an increment was lost"
    # and the state decision still happened
    assert rows[0].state == breaker.STATE_OPEN


def test_concurrent_snapshots_do_not_collide_on_the_cache_row():
    """Two modalities querying one source at the same instant write the same rows."""
    source_id = _source()
    answers = [_item("ACC-1"), _item("ACC-2")]
    threads = 6
    start = threading.Barrier(threads)
    errors: list[str] = []
    stored: list[int] = []

    def store():
        start.wait(timeout=10)
        try:
            stored.append(cache.store_snapshot(source_id, answers))
        except Exception as exc:  # noqa: BLE001
            errors.append(repr(exc))

    workers = [threading.Thread(target=store) for _ in range(threads)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=30)

    assert errors == []
    assert stored == [2] * threads
    with session_factory()() as s:
        rows = s.scalars(select(WorklistCache)).all()
    assert len(rows) == 2


def test_a_snapshot_still_replaces_the_previous_one():
    """The upsert must not weaken the cache semantics: gone items disappear."""
    source_id = _source()
    cache.store_snapshot(source_id, [_item("ACC-1"), _item("ACC-2")])
    cache.store_snapshot(source_id, [_item("ACC-2")])

    with session_factory()() as s:
        accessions = sorted(r.accession for r in s.scalars(select(WorklistCache)).all())
    assert accessions == ["ACC-2"]


def test_a_snapshot_updates_the_payload_of_an_existing_item():
    """The RIS is the source of truth — a changed field must land."""
    source_id = _source()
    first = _item("ACC-1")
    first.PatientID = "PAT-OLD"
    cache.store_snapshot(source_id, [first])

    second = _item("ACC-1")
    second.PatientID = "PAT-NEW"
    cache.store_snapshot(source_id, [second])

    with session_factory()() as s:
        rows = s.scalars(select(WorklistCache)).all()
    assert len(rows) == 1
    assert "PAT-NEW" in rows[0].payload["json"]
