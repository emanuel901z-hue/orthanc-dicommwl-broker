"""Mock-RIS query filtering — used by the demo stack for C-FIND fan-out tests."""
from mwl_broker.mock_ris import VARIANTS, _matches


def _query(**kwargs) -> dict:
    """Plain mappings — `_matches` only uses `.get(keyword, default)`."""
    sps: dict = {}
    q: dict = {"ScheduledProcedureStepSequence": [sps]}
    for key, value in kwargs.items():
        (sps if key in (
            "Modality", "ScheduledStationAETitle", "ScheduledProcedureStepStartDate"
        ) else q)[key] = value
    return q


def test_empty_query_matches_everything():
    item = VARIANTS["a"][0]
    assert _matches(_query(), item) is True


def test_accession_and_patient_filters():
    item = VARIANTS["a"][0]  # ACC-A-001 / P1001
    assert _matches(_query(AccessionNumber="ACC-A-001"), item) is True
    assert _matches(_query(AccessionNumber="ACC-B-*"), item) is False
    assert _matches(_query(PatientID="P1001"), item) is True
    assert _matches(_query(PatientID="P9999"), item) is False


def test_sps_filters_modality_and_station():
    item = VARIANTS["a"][0]  # CT / CT_01
    assert _matches(_query(Modality="CT"), item) is True
    assert _matches(_query(Modality="MR"), item) is False
    assert _matches(_query(ScheduledStationAETitle="CT_*"), item) is True
    assert _matches(_query(ScheduledStationAETitle="XR_01"), item) is False


def test_wildcard_date_filter():
    item = VARIANTS["a"][0]
    assert _matches(_query(ScheduledProcedureStepStartDate="2026*"), item) is True
    assert _matches(_query(ScheduledProcedureStepStartDate="20200101"), item) is False


def test_variants_share_a_duplicate_for_dedupe_tests():
    acc_a = {i.AccessionNumber for i in VARIANTS["a"]}
    acc_b = {i.AccessionNumber for i in VARIANTS["b"]}
    assert acc_a & acc_b, "variants must overlap so dedupe can be exercised"
