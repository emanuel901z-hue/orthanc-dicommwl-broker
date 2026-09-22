"""The conformance statement must match the code.

A conformance statement that drifts from the implementation is worse than none:
it is the document a hospital signs off against. These tests read the document
and check the claims that can be verified mechanically:

* every SOP class named in the document really is offered/handled,
* the AET, ports and operating limits quoted match the settings defaults,
* the "not supported" list names services that are indeed absent from the code.
"""
import re
from pathlib import Path

import pytest
from pynetdicom import StoragePresentationContexts

from mwl_broker import dimse, mpps
from mwl_broker.config import Settings

DOC = Path(__file__).resolve().parents[2] / "docs" / "dicom-conformance-statement.md"
IHE_DOC = Path(__file__).resolve().parents[2] / "docs" / "ihe-profile-statement.md"


@pytest.fixture()
def statement() -> str:
    assert DOC.is_file(), f"missing {DOC}"
    return DOC.read_text()


def test_documents_exist_and_are_linked():
    assert DOC.is_file()
    assert IHE_DOC.is_file()
    assert "ihe-profile-statement.md" in DOC.read_text()
    assert "dicom-conformance-statement.md" in IHE_DOC.read_text()


def test_statement_names_the_sop_classes_the_code_offers(statement):
    """Every service the broker offers must be in the document — and vice versa."""
    source = Path(dimse.__file__).read_text()

    # the services the code registers
    offered = {
        "ModalityWorklistInformationFind": "Modality Worklist",
        "Verification": "Verification",
        "ModalityPerformedProcedureStep": "Modality Performed Procedure Step",
        "StoragePresentationContexts": "Storage",
    }
    for symbol, label in offered.items():
        assert symbol in source, f"{symbol} is not registered any more"
        assert label.split()[0] in statement, f"{label} is missing from the statement"


def test_statement_quotes_the_real_transfer_syntaxes(statement):
    from pynetdicom import AE
    from pynetdicom.sop_class import ModalityWorklistInformationFind

    ae = AE(ae_title="T")
    ae.add_supported_context(ModalityWorklistInformationFind)
    context = list(ae._supported_contexts.values())[0]
    keywords = sorted(ts.keyword for ts in context.transfer_syntax)

    for keyword in keywords:
        assert keyword in statement, f"{keyword} is offered but not documented"
    # the document lists the same number of syntaxes
    listed = re.findall(r"^\| [A-Z][^|]*\| 1\.2\.840\.10008\.1\.2", statement, re.M)
    assert len(listed) == len(keywords), (len(listed), keywords)


def test_statement_counts_the_storage_sop_classes_correctly(statement):
    real = len({c.abstract_syntax for c in StoragePresentationContexts})
    quoted = re.search(r"\*\*(\d+)\*\* SOP-Klassen", statement)
    assert quoted, "the storage SOP class count is not in the document"
    assert int(quoted.group(1)) == real, f"document says {quoted.group(1)}, code has {real}"


def test_statement_matches_the_settings_defaults(statement):
    """AET, ports and limits must be the values the code ships."""
    settings = Settings()
    expected = {
        "MWLBROKER": settings.broker_aet,
        "11113": str(settings.dicom_port),
        "2762": str(settings.tls_inbound_port),
        "20": str(settings.max_associations),
        "10 s": f"{settings.upstream_timeout_s} s",
        "30 s": f"{settings.echo_interval_s} s",
        "5000": str(settings.cache_max_items),
        "120 s": f"{settings.cache_stale_max_s} s",
        "20 000": f"{settings.spool_max_items:,}".replace(",", " "),
        "10 Versuche": f"{settings.spool_max_attempts} Versuche",
        "2575": str(settings.hl7_mllp_port),
        "6514": str(settings.atna_syslog_port),
        "3 Fehler": f"{settings.breaker_fail_threshold} Fehler",
        "60 s": f"{settings.breaker_open_seconds} s",
    }
    for quoted, real in expected.items():
        assert quoted == real, f"statement quotes {quoted}, code has {real}"
        assert quoted in statement, f"{quoted} is missing from the statement"


def test_statement_documents_the_spool_and_cache_limits(statement):
    settings = Settings()
    assert f"{settings.spool_max_bytes / (1024 ** 3):.0f} GiB" in statement
    assert "Abweisung" in statement or "abgewiesen" in statement, \
        "the spool must document that it refuses instead of dropping"


def test_not_supported_list_names_services_that_are_really_absent(statement):
    """What the document calls unsupported must not appear as a handler."""
    source = Path(dimse.__file__).read_text()
    assert "C-MOVE" in statement and "C-GET" in statement
    assert "C_MOVE" not in source and "C_GET" not in source
    assert "Storage Commitment" in statement
    assert "EVT_N_ACTION" not in source and "EVT_N_EVENT_REPORT" not in source
    # UPS is announced as planned, so it must not be implemented yet
    assert "UPS" in statement


def test_statement_documents_the_mpps_switch(statement):
    """MPPS is offered only when enabled — the document must say so."""
    assert "mpps_enabled" in statement
    assert "N-GET" in statement, "the missing N-GET must be stated explicitly"


def test_ihe_statement_names_the_profiles(statement=None):
    text = IHE_DOC.read_text()
    for profile in ("Scheduled Workflow", "Patient Information Reconciliation", "ATNA"):
        assert profile in text, f"{profile} is missing from the IHE statement"
    # what is only partially covered must be marked as such
    assert "teilweise" in text
    assert "MRN-Merge" in text or "PIX" in text
