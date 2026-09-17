"""Upstream C-FIND SCU + merge/dedupe helpers.

Pure logic lives in dedupe_key()/merge_answers() — unit-testable without
network. query_source() is the only network-touching function.
"""
import copy
import logging
from dataclasses import dataclass

from pydicom.dataset import Dataset
from pynetdicom import AE
from pynetdicom.sop_class import ModalityWorklistInformationFind

log = logging.getLogger("mwl_broker.upstream")


@dataclass(frozen=True)
class SourceCfg:
    """Detached copy of an MwlSource row — safe to use across threads."""

    id: int
    name: str
    aet: str
    host: str
    port: int
    calling_aet: str
    charset: str
    timeout_s: int
    # merge order across sources (lower wins); station rules may override it
    priority: int = 100


def dedupe_key(ds: Dataset) -> tuple[str, str, str]:
    """Merge key: PatientID + AccessionNumber + first SPS ID."""
    sps_seq = ds.get("ScheduledProcedureStepSequence") or []
    sps_id = ""
    if sps_seq:
        sps_id = str(sps_seq[0].get("ScheduledProcedureStepID", ""))
    return (
        str(ds.get("PatientID", "")),
        str(ds.get("AccessionNumber", "")),
        sps_id,
    )


def merge_answers(
    per_source: list[tuple[SourceCfg, list[Dataset]]],
) -> list[tuple[Dataset, SourceCfg]]:
    """Merge upstream answers, dedupe by dedupe_key. Sources are already
    priority-ordered; first occurrence wins. Returns (dataset, source)
    pairs so callers can populate seen_items."""
    seen: set[tuple[str, str, str]] = set()
    merged: list[tuple[Dataset, SourceCfg]] = []
    for src, answers in per_source:
        for ds in answers:
            key = dedupe_key(ds)
            if key in seen:
                continue
            seen.add(key)
            merged.append((ds, src))
    return merged


def outgoing_identifier(incoming: Dataset, charset: str) -> Dataset:
    """Copy the incoming query identifier and retarget the charset for
    this specific upstream source."""
    ident = copy.deepcopy(incoming)
    ident.SpecificCharacterSet = charset
    if hasattr(ident, "set_original_encoding"):
        try:
            ident.set_original_encoding(charset)
        except Exception:
            pass
    return ident


def query_source(src: SourceCfg, incoming_identifier: Dataset) -> list[Dataset]:
    """Send C-FIND to one upstream source, return collected answer datasets."""
    ae = AE(ae_title=src.calling_aet)
    ae.add_requested_context(ModalityWorklistInformationFind)
    # pynetdicom 3.x: timeouts are AE attributes, not associate() kwargs
    ae.acse_timeout = src.timeout_s
    ae.dimse_timeout = src.timeout_s
    ae.network_timeout = src.timeout_s
    ident = outgoing_identifier(incoming_identifier, src.charset)
    assoc = ae.associate(src.host, src.port, ae_title=src.aet)
    answers: list[Dataset] = []
    if not assoc.is_established:
        # Raise so the caller records "error" — an unreachable source must
        # count as failure, not as "zero answers".
        raise ConnectionError("association rejected")
    try:
        for status, ds in assoc.send_c_find(ident, ModalityWorklistInformationFind):
            if status is None:
                continue
            if status.Status in (0xFF00, 0xFF01) and ds is not None:
                answers.append(ds)
    finally:
        assoc.release()
    return answers


def c_echo(aet: str, host: str, port: int, calling_aet: str, timeout_s: int = 10) -> None:
    """Raise on failure, return None on success."""
    ae = AE(ae_title=calling_aet)
    from pynetdicom.sop_class import Verification

    ae.add_requested_context(Verification)
    ae.acse_timeout = timeout_s
    ae.dimse_timeout = timeout_s
    ae.network_timeout = timeout_s
    assoc = ae.associate(host, port, ae_title=aet)
    if not assoc.is_established:
        raise ConnectionError("association rejected")
    try:
        status = assoc.send_c_echo()
        if not status or status.Status != 0x0000:
            raise ConnectionError(f"C-ECHO status {getattr(status, 'Status', 'none')}")
    finally:
        assoc.release()
