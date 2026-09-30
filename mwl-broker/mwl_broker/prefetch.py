"""Prior-study prefetch: find a patient's earlier studies and pull them in.

A radiologist reading a new CT wants the old ones at the reporting station. The
broker asks the PACS for them (study-level C-FIND) and triggers the transfer
(C-MOVE) — it acts as an **SCU** here.

It still does **not offer** C-MOVE: no modality or RIS can ask the broker to move
anything, and no presentation context for C-MOVE is accepted on the broker's own
port. The direction matters and is stated in the conformance statement: the
broker is a query/retrieve *client* for prefetch, never a query/retrieve *server*.

Two nodes are involved, both rows of the existing `pacs_target` table:

* the **query node** — where the priors are looked up *and* the node that runs
  the move (the Q/R provider),
* the **destination** — the AE title the images should land on. The query node
  must know it as a move destination; that is the one thing the broker cannot
  check for you (it is configured on the PACS side).

PHI: the prefetch result lists study UIDs, dates and descriptions — no patient
name. The query itself carries the patient ID (that is what identifies the
priors), and it is never logged.
"""
import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass

from pydicom.dataset import Dataset
from pynetdicom import AE
from pynetdicom.sop_class import (
    StudyRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelMove,
)

from . import metrics, settings_service
from .db import session_factory
from .models import PacsTarget

log = logging.getLogger("mwl_broker.prefetch")

# A move that gets less than this many seconds is not started — better to report
# "not attempted" than to open an association that is cut off mid-transfer. Kept
# below the smallest allowed budget (5 s), otherwise the first study would never
# start.
MIN_MOVE_S = 3

# a few C-MOVE/C-FIND status codes worth naming in plain words
STATUS_TEXT = {
    0x0000: "",
    0xA700: "out of resources",
    0xA701: "out of resources — unable to calculate the number of matches",
    0xA702: "out of resources — unable to perform the sub-operations",
    0xA801: "move destination unknown to the query node",
    0xA900: "identifier does not match SOP class",
    0xB000: "some sub-operations had warnings",
    0xC000: "unable to process",
    0xC511: "the query node's move handler failed",
    0xC515: "invalid move destination",
}


@dataclass(frozen=True)
class NodeCfg:
    """Detached copy of a PacsTarget row — safe to use across threads."""

    id: int
    name: str
    aet: str
    host: str
    port: int
    calling_aet: str = "MWLBROKER"
    tls: bool = False
    tls_verify: bool = True


def _node(row: PacsTarget) -> NodeCfg:
    return NodeCfg(id=row.id, name=row.name, aet=row.aet, host=row.host, port=row.port,
                   calling_aet=row.calling_aet or "MWLBROKER",
                   tls=row.tls, tls_verify=row.tls_verify)


def node_config(target_id: int) -> NodeCfg | None:
    with session_factory()() as s:
        row = s.get(PacsTarget, target_id)
        return _node(row) if row is not None else None


def node_by_name(name: str) -> NodeCfg | None:
    from sqlalchemy import select

    with session_factory()() as s:
        row = s.scalars(select(PacsTarget).where(
            PacsTarget.name == (name or "").strip())).first()
        return _node(row) if row is not None else None


def _tls_args(node: NodeCfg) -> tuple | None:
    if not node.tls:
        return None
    from . import tls as tls_module

    return tls_module.client_tls_args(verify=node.tls_verify, server_name=node.host)


def _associate(ae: AE, node: NodeCfg, timeout_s: int):
    # pynetdicom 3.x: timeouts are AE attributes, not associate() kwargs
    ae.acse_timeout = timeout_s
    ae.dimse_timeout = timeout_s
    ae.network_timeout = timeout_s
    return ae.associate(node.host, node.port, ae_title=node.aet, tls_args=_tls_args(node))


def _study_dict(ds: Dataset) -> dict:
    def value(name: str) -> str:
        raw = ds.get(name, "")
        return str(raw).strip() if raw not in (None, "") else ""

    return {
        "study_uid": value("StudyInstanceUID"),
        "study_date": value("StudyDate"),
        "description": value("StudyDescription"),
        "modalities": value("ModalitiesInStudy"),
        "instances": value("NumberOfStudyRelatedInstances"),
    }


def find_studies(node: NodeCfg, patient_id: str, *, modality: str = "",
                 exclude_study_uid: str = "", limit: int = 20,
                 timeout_s: int = 10) -> list[dict]:
    """Study-level C-FIND: the patient's earlier studies, newest first."""
    ae = AE(ae_title=node.calling_aet)
    ae.add_requested_context(StudyRootQueryRetrieveInformationModelFind)
    assoc = _associate(ae, node, timeout_s)
    if not assoc.is_established:
        raise ConnectionError("association rejected")

    identifier = Dataset()
    identifier.QueryRetrieveLevel = "STUDY"
    identifier.PatientID = patient_id
    # return keys: empty means "give me these"
    identifier.StudyInstanceUID = ""
    identifier.StudyDate = ""
    identifier.StudyDescription = ""
    identifier.ModalitiesInStudy = modality or ""
    identifier.NumberOfStudyRelatedInstances = ""

    studies: list[dict] = []
    try:
        for status, ds in assoc.send_c_find(identifier,
                                            StudyRootQueryRetrieveInformationModelFind):
            if status is None or ds is None:
                continue
            if status.Status in (0xFF00, 0xFF01):
                studies.append(_study_dict(ds))
    finally:
        assoc.release()

    if exclude_study_uid:
        studies = [study for study in studies if study["study_uid"] != exclude_study_uid]
    # newest first — the current examination is what the reader starts from
    studies.sort(key=lambda study: study["study_date"], reverse=True)
    return studies[:limit]


def move_study(node: NodeCfg, study_uid: str, destination_aet: str, *,
               timeout_s: int = 120) -> dict:
    """C-MOVE one study to the destination AE title; returns the final status."""
    ae = AE(ae_title=node.calling_aet)
    ae.add_requested_context(StudyRootQueryRetrieveInformationModelMove)
    assoc = _associate(ae, node, timeout_s)
    if not assoc.is_established:
        raise ConnectionError("association rejected")

    identifier = Dataset()
    identifier.QueryRetrieveLevel = "STUDY"
    identifier.StudyInstanceUID = study_uid

    final = None
    try:
        for status, _ds in assoc.send_c_move(identifier, destination_aet,
                                             StudyRootQueryRetrieveInformationModelMove):
            if status is not None:
                final = status
    finally:
        assoc.release()

    code = getattr(final, "Status", None)
    ok = code in (0x0000, 0xB000)
    return {
        "study_uid": study_uid,
        "status": code,
        "completed": getattr(final, "NumberOfCompletedSuboperations", 0) or 0,
        "failed": getattr(final, "NumberOfFailedSuboperations", 0) or 0,
        "warning": getattr(final, "NumberOfWarningSuboperations", 0) or 0,
        "ok": ok,
        "error": "" if ok else STATUS_TEXT.get(code, f"C-MOVE status 0x{code:04X}"
                                               if code is not None else "no response"),
    }


class PrefetchBusy(RuntimeError):
    """Too many prefetch calls are running — the caller should come back later."""


_running = 0
_running_lock = threading.Lock()


@contextmanager
def _slot():
    """Bound how many prefetch calls run at once.

    Each call occupies a request worker and a PACS association for up to the
    whole time budget. Without a limit, a handful of concurrent calls would tie
    up the API (and with it `/healthz`) for everyone — the broker would look
    dead while it is only busy prefetching. The limit is a runtime setting, so a
    busy house can raise it without a restart.
    """
    global _running
    limit = max(1, settings_service.get_int("prefetch_max_concurrency"))
    with _running_lock:
        if _running >= limit:
            raise PrefetchBusy(
                f"{_running} prefetch call(s) already running (limit {limit}) — "
                "try again shortly or raise `prefetch_max_concurrency`"
            )
        _running += 1
    try:
        yield
    finally:
        with _running_lock:
            _running -= 1


def reset_for_tests() -> None:
    global _running
    with _running_lock:
        _running = 0


def prefetch(patient_id: str, *, query_node: str, destination: str, modality: str = "",
             exclude_study_uid: str = "", max_studies: int = 5, dry_run: bool = True) -> dict:
    """Plan (dry run) or perform the prefetch of a patient's prior studies.

    The whole call is bounded by `prefetch_timeout_s`; studies that no longer fit
    are reported as `skipped` instead of being started and cut off. Raises
    ValueError for an unknown node or a missing patient ID — the API turns that
    into a 422 with the same plain-language message.
    """
    patient_id = (patient_id or "").strip()
    if not patient_id:
        raise ValueError("patient_id is required")
    node = node_by_name(query_node)
    if node is None:
        raise ValueError(f"unknown query node {query_node!r} (a PACS target name)")
    target = node_by_name(destination)
    if target is None:
        raise ValueError(f"unknown destination {destination!r} (a PACS target name)")

    studies = find_studies(
        node, patient_id, modality=modality, exclude_study_uid=exclude_study_uid,
        limit=max_studies, timeout_s=settings_service.get_int("upstream_timeout_s"),
    )

    result = {
        "dry_run": dry_run,
        "query_node": node.name,
        "destination": target.name,
        "destination_aet": target.aet,
        "patient_id": patient_id,
        "studies": studies,
        "moved": [],
        "skipped": [],
    }
    if dry_run or not studies:
        metrics.PREFETCH_RUNS.labels(result="dry_run" if dry_run else "ok").inc()
        return result

    budget_s = settings_service.get_int("prefetch_timeout_s")
    deadline = time.monotonic() + budget_s
    with _slot():
        moved = []
        skipped = []
        for study in studies:
            remaining = deadline - time.monotonic()
            if remaining < MIN_MOVE_S:
                # the budget is spent: report it instead of starting a move that
                # would be cut off mid-transfer
                skipped.append(study["study_uid"])
                continue
            moved.append(move_study(node, study["study_uid"], target.aet,
                                    timeout_s=int(remaining)))
        result["moved"] = moved
        result["skipped"] = skipped

    delivered = sum(1 for move in moved if move["ok"])
    failed = len(moved) - delivered
    metrics.PREFETCH_STUDIES.labels(result="moved").inc(delivered)
    metrics.PREFETCH_STUDIES.labels(result="failed").inc(failed)
    metrics.PREFETCH_STUDIES.labels(result="skipped").inc(len(skipped))
    metrics.PREFETCH_RUNS.labels(
        result="ok" if not failed and not skipped else "partial").inc()
    log.info("prefetch: %d of %d prior study/studies sent to %s (%d skipped)",
             delivered, len(moved), target.name, len(skipped))
    return result
