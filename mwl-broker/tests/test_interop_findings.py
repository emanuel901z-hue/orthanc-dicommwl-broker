"""What the DCMTK interop test found (`deploy/interop-test.sh`).

Our own mock RIS never sent a **multi-valued** attribute, so two things went
unnoticed until real foreign software was on the other end:

1. DCMTK's example worklist carries `ScheduledStationAETitle` with several
   stations per step (legal, and common in real RIS answers). Writing that into
   a metadata column raised `value too long for character varying(16)`, and
   because the cache write sat inside the same `try` as the query, the **whole
   answer was lost** and the working source was counted as failed.
2. A cache write failure in general must not cost the answer: the cache is an
   outage bridge, the RIS answer is what the modality needs.
"""
from pydicom.dataset import Dataset
from pydicom.multival import MultiValue

from mwl_broker import aggregation, cache, settings_service
from mwl_broker.db import session_factory
from mwl_broker.models import MwlSource, SeenItem, WorklistCache
from mwl_broker.upstream import meta_text, outgoing_identifier


def _source(name: str = "foreign-ris", priority: int = 1) -> int:
    with session_factory()() as s:
        row = MwlSource(name=name, aet="OFFIS", host="127.0.0.1", port=11116,
                        calling_aet="MWLBROKER", charset="ISO_IR 100",
                        enabled=True, timeout_s=1, priority=priority)
        s.add(row)
        s.commit()
        s.refresh(row)
        return row.id


def _foreign_answer(accession: str = "00003", stations=("CC56", "NN77", "GH67"),
                    sps_id: str = "SPD1234") -> Dataset:
    """One item in the shape DCMTK's example worklist has."""
    sps = Dataset()
    sps.ScheduledStationAETitle = list(stations) if len(stations) > 1 else stations[0]
    sps.Modality = "CT"
    sps.ScheduledProcedureStepStatus = "SCHEDULED"
    sps.ScheduledProcedureStepID = sps_id
    sps.ScheduledProcedureStepStartDate = "19960123"
    ds = Dataset()
    ds.AccessionNumber = accession
    ds.PatientID = "PAT-FOREIGN"
    ds.PatientName = "VIVALDI^ANTONIO"
    ds.StudyInstanceUID = "1.2.3.4.5"
    ds.ScheduledProcedureStepSequence = [sps]
    return ds


# ── mehrwertige Attribute ─────────────────────────────────────────────────


def test_meta_text_takes_the_first_value_and_stays_within_the_column():
    value = MultiValue(str, ["CC56", "NN77", "GH67"])
    assert meta_text(value, 16) == "CC56"
    assert meta_text("A" * 40, 16) == "A" * 16
    assert meta_text(None, 16) == ""
    assert meta_text(MultiValue(str, []), 16) == ""


def test_a_foreign_answer_with_several_stations_is_served(client, monkeypatch):
    _source()
    answer = _foreign_answer()
    monkeypatch.setattr(aggregation, "query_source", lambda src, ident: [answer])
    settings_service.set_value("cache_enabled", "true")

    result = aggregation.collect(Dataset())

    assert [ds.AccessionNumber for ds, _src in result.merged] == ["00003"]
    assert result.per_source == {"foreign-ris": 1}, "the source must not be an error"
    assert result.outcomes[0].ok is True


def test_the_cache_index_keeps_one_bounded_station(client, monkeypatch):
    source_id = _source()
    monkeypatch.setattr(aggregation, "query_source",
                        lambda src, ident: [_foreign_answer()])
    settings_service.set_value("cache_enabled", "true")

    aggregation.collect(Dataset())

    with session_factory()() as s:
        row = s.query(WorklistCache).filter_by(source_id=source_id).one()
    assert row.station_aet == "CC56"          # first value, fits the column
    assert row.accession == "00003"
    assert "VIVALDI" in row.payload["json"]   # the payload keeps everything


def test_seen_items_survive_a_multi_valued_step_id(client):
    """The routing provenance is written from the same answer."""
    from mwl_broker.config import Settings
    from mwl_broker.dimse import BrokerSCP

    source_id = _source()
    answer = _foreign_answer(sps_id="SPD-1234-5678-9012-3456-7890")
    scp = BrokerSCP(Settings())
    with session_factory()() as s:
        source = s.get(MwlSource, source_id)

    scp._record_seen_items([(answer, source)])

    with session_factory()() as s:
        row = s.query(SeenItem).one()
    assert row.accession == "00003"
    assert row.sps_id == "SPD-1234-5678-9012-3456-7890"[:64]


# ── ein Cache-Fehler darf die Antwort nicht kosten ────────────────────────


def test_a_broken_cache_still_serves_the_answer(client, monkeypatch):
    """The cache is the outage bridge — not the truth the modality needs."""
    _source()
    monkeypatch.setattr(aggregation, "query_source", lambda src, ident: [_foreign_answer()])
    settings_service.set_value("cache_enabled", "true")

    def boom(_source_id, _answers):
        raise RuntimeError("column too small")

    monkeypatch.setattr(cache, "store_snapshot", boom)

    result = aggregation.collect(Dataset())

    assert [ds.AccessionNumber for ds, _src in result.merged] == ["00003"], \
        "the answer must arrive even when the cache write fails"
    assert result.per_source == {"foreign-ris": 1}
    assert result.outcomes[0].ok is True, "a working source must not be counted as failed"


def test_a_broken_cache_does_not_open_the_breaker(client, monkeypatch):
    """Three 'failures' used to skip a healthy source for a minute."""
    from mwl_broker import breaker

    source_id = _source()
    monkeypatch.setattr(aggregation, "query_source", lambda src, ident: [_foreign_answer()])
    monkeypatch.setattr(cache, "store_snapshot",
                        lambda _sid, _answers: (_ for _ in ()).throw(RuntimeError("boom")))
    settings_service.set_value("cache_enabled", "true")
    settings_service.set_value("breaker_fail_threshold", "1")

    for _ in range(3):
        aggregation.collect(Dataset())

    assert breaker.is_available(source_id) is True


def test_query_retrieve_level_is_forwarded_unchanged_by_default():
    """The modality's identifier goes upstream as it came in.

    Keeping it unchanged is the whole point of the fan-out: a filter the
    modality set must not disappear because we felt like cleaning up.
    """
    ident = Dataset()
    ident.QueryRetrieveLevel = "MODALITY WORKLIST"
    ident.PatientID = "P1001"

    out = outgoing_identifier(ident, "ISO_IR 100")

    assert out.QueryRetrieveLevel == "MODALITY WORKLIST"
    assert out.PatientID == "P1001"
    # the incoming dataset is never touched
    assert ident.QueryRetrieveLevel == "MODALITY WORKLIST"


def test_query_retrieve_level_can_be_left_out_per_source():
    """Some foreign MWL SCPs match on (0008,0052) and then answer nothing.

    DVTk's RIS emulator does exactly that. The attribute is not part of the
    Modality Worklist information model, so leaving it out is conforming; it is
    a per-source switch (default off), not a silent rewrite.

    Measured: directly against the emulator 6 answers without it and 0 with it;
    through our broker with a QRL-sending modality 3 entries (switch off) vs 7
    (switch on, 4 of them from the foreign RIS).
    """
    ident = Dataset()
    ident.QueryRetrieveLevel = "MODALITY WORKLIST"
    ident.PatientID = "P1001"

    out = outgoing_identifier(ident, "ISO_IR 100", strip_query_retrieve_level=True)

    assert "QueryRetrieveLevel" not in out
    assert out.PatientID == "P1001"


def test_the_switch_reaches_the_upstream_client(client, monkeypatch):
    """The flag on the source row must arrive at the C-FIND SCU."""
    source_id = _source(name="dvtk-ris", priority=1)
    with session_factory()() as s:
        row = s.get(MwlSource, source_id)
        row.strip_query_retrieve_level = True
        s.commit()

    seen: dict = {}

    def fake_query_source(src, identifier):
        seen["flag"] = src.strip_query_retrieve_level
        return []

    monkeypatch.setattr(aggregation, "query_source", fake_query_source)
    aggregation.query_one(aggregation.source_config(source_id), Dataset())

    assert seen["flag"] is True
