from pydicom.dataset import Dataset

from mwl_broker.upstream import SourceCfg, dedupe_key, merge_answers


def _ds(patient_id="P1", accession="A1", sps_id="S1"):
    ds = Dataset()
    ds.PatientID = patient_id
    ds.AccessionNumber = accession
    sps = Dataset()
    sps.ScheduledProcedureStepID = sps_id
    ds.ScheduledProcedureStepSequence = [sps]
    return ds


def _src(id_, name="s"):
    return SourceCfg(
        id=id_, name=f"{name}{id_}", aet="A", host="h", port=1,
        calling_aet="C", charset="ISO_IR 100", timeout_s=5,
    )


def test_dedupe_key_uses_patient_accession_sps():
    ds = _ds()
    assert dedupe_key(ds) == ("P1", "A1", "S1")


def test_dedupe_key_empty_sps():
    ds = Dataset()
    ds.PatientID = "P"
    ds.AccessionNumber = "A"
    assert dedupe_key(ds) == ("P", "A", "")


def test_merge_first_source_wins():
    a = _src(1)
    b = _src(2)
    dupe = _ds()
    merged = merge_answers([(a, [_ds()]), (b, [dupe, _ds(accession="A2", sps_id="S2")])])
    assert len(merged) == 2
    assert merged[0][1] is a
    assert merged[1][0].AccessionNumber == "A2"


def test_merge_empty():
    assert merge_answers([]) == []
