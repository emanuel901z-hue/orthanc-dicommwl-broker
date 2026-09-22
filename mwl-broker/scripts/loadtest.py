#!/usr/bin/env python3
"""Load test: how much can this broker take, and *how* does it fail?

This runs against a **running** broker over the wire (DIMSE + REST), so it
measures the deployed thing rather than a unit test. Two scenarios:

  cfind    N modality clients × M C-FIND queries at a chosen concurrency
  cstore   N C-STORE instances (fills the spool when the target is unreachable)

Both report latency percentiles and, more importantly, the **shape** of the
limits — the numbers depend on the host, the behaviour does not:

* Does latency stay flat as concurrency rises, or does it collapse?
* What happens above `max_associations` — queueing or rejection?
* At the spool budget: does the broker refuse, or does it drop silently?
* Do the monitoring endpoints stay answerable while the DIMSE path is busy?

`--json FILE` writes the raw numbers for `docs/loadtest.md`. Nothing here is a
unit test: run it against an **isolated** stack (the numbers are worthless on a
host that is already busy, and the spool fill leaves data behind).

Usage:
  python3 scripts/loadtest.py cfind --api http://127.0.0.1:19081 \\
      --host 127.0.0.1 --port 11123 --clients 24 --queries 5 --concurrency 24
  python3 scripts/loadtest.py cstore --host 127.0.0.1 --port 11123 \\
      --instances 200 --concurrency 8 --payload-kb 64
"""
import argparse
import json
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, generate_uid
from pynetdicom import AE
from pynetdicom.sop_class import ModalityWorklistInformationFind

CALLING_AET = "LOADTEST"


# ── measuring ─────────────────────────────────────────────────────────────


class Report:
    """Latencies plus what actually happened — a mean alone hides the failure."""

    def __init__(self, name: str):
        self.name = name
        self.latencies: list[float] = []
        self.errors: list[str] = []
        self.answers = 0
        self.lock = threading.Lock()

    def add(self, seconds: float) -> None:
        with self.lock:
            self.latencies.append(seconds)

    def error(self, text: str) -> None:
        with self.lock:
            self.errors.append(text)

    def add_answers(self, count: int) -> None:
        with self.lock:
            self.answers += count

    def summary(self) -> dict:
        values = sorted(self.latencies)
        if not values:
            return {"scenario": self.name, "requests": 0, "errors": len(self.errors)}
        return {
            "scenario": self.name,
            "requests": len(values),
            "errors": len(self.errors),
            "answers": self.answers,
            "ok_rate": round(len(values) / (len(values) + len(self.errors)), 4),
            "p50_ms": round(statistics.median(values) * 1000, 1),
            "p95_ms": round(values[int(len(values) * 0.95) - 1] * 1000, 1),
            "p99_ms": round(values[int(len(values) * 0.99) - 1] * 1000, 1),
            "max_ms": round(values[-1] * 1000, 1),
            "mean_ms": round(statistics.fmean(values) * 1000, 1),
        }


def print_report(summary: dict) -> None:
    if not summary.get("requests"):
        print(f"  {summary['scenario']}: no successful request "
              f"({summary['errors']} error(s))")
    else:
        print(f"  {summary['scenario']}: {summary['requests']} requests, "
              f"{summary['errors']} error(s), {summary['answers']} answer(s)")
        print(f"    p50 {summary['p50_ms']} ms · p95 {summary['p95_ms']} ms · "
              f"p99 {summary['p99_ms']} ms · max {summary['max_ms']} ms")
    for text in summary.get("error_samples", []):
        print(f"    ! {text}")


# ── REST helpers ──────────────────────────────────────────────────────────


def api_get(url: str, timeout: float = 10.0):
    import urllib.request

    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read())


def api_put(url: str, payload: dict) -> None:
    import urllib.request

    request = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="PUT",
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(request, timeout=10).read()


def probe_rest(api: str, stop: threading.Event, report: Report) -> None:
    """Poll the monitoring endpoints while the DIMSE path is under load.

    'The UI must stay answerable' is the requirement the DB pool incident broke:
    a saturated pool answered 500 on a plain read.
    """
    for path in ("/status", "/health/config", "/stats/overview"):
        url = f"{api}/api/v1{path}"
        while not stop.is_set():
            started = time.perf_counter()
            try:
                api_get(url, timeout=10)
                report.add(time.perf_counter() - started)
            except Exception as exc:  # noqa: BLE001 - the point is to record it
                report.error(f"{path}: {exc}")
            stop.wait(1.0)


# ── C-FIND ────────────────────────────────────────────────────────────────


def mwl_query() -> Dataset:
    query = Dataset()
    query.SpecificCharacterSet = "ISO_IR 100"
    sps = Dataset()
    sps.ScheduledStationAETitle = ""
    sps.ScheduledProcedureStepStartDate = ""
    sps.Modality = ""
    query.ScheduledProcedureStepSequence = [sps]
    query.PatientName = ""
    query.PatientID = ""
    query.AccessionNumber = ""
    return query


def one_cfind(host: str, port: int, aet: str, report: Report) -> None:
    """One modality query — one association, like a console that just started up."""
    ae = AE(ae_title=CALLING_AET)
    ae.add_requested_context(ModalityWorklistInformationFind)
    started = time.perf_counter()
    try:
        assoc = ae.associate(host, port, ae_title=aet)
        if not assoc.is_established:
            report.error("association rejected")
            return
        try:
            answers = 0
            for status, _ds in assoc.send_c_find(mwl_query(), ModalityWorklistInformationFind):
                if status is None:
                    report.error("no status (association lost)")
                    return
                if status.Status in (0xFF00, 0xFF01):
                    answers += 1
                elif status.Status != 0x0000:
                    report.error(f"C-FIND status 0x{status.Status:04x}")
                    return
            report.add(time.perf_counter() - started)
            report.add_answers(answers)
        finally:
            assoc.release()
    except Exception as exc:  # noqa: BLE001
        report.error(str(exc)[:120])


def scenario_cfind(args) -> dict:
    report = Report(f"cfind {args.clients}x{args.queries} @{args.concurrency}")
    print(f"── C-FIND: {args.clients} clients × {args.queries} queries, "
          f"concurrency {args.concurrency} ──")

    if args.dead_source:
        print("   adding a dead upstream (the timeout/breaker path)")
        api_put(f"{args.api}/api/v1/sources", {
            "name": "loadtest-dead", "aet": "DEAD", "host": args.dead_host,
            "port": args.dead_port, "calling_aet": "MWLBROKER",
            "charset": "ISO_IR 100", "enabled": True, "timeout_s": 2, "priority": 1,
        })

    stop = threading.Event()
    probes = Report("rest during cfind")
    probe_thread = threading.Thread(target=probe_rest, args=(args.api, stop, probes))
    probe_thread.start()

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [
            pool.submit(one_cfind, args.host, args.port, args.aet, report)
            for _ in range(args.clients * args.queries)
        ]
        for future in futures:
            future.result()
    elapsed = time.perf_counter() - started

    stop.set()
    probe_thread.join(timeout=15)

    summary = report.summary()
    summary["seconds"] = round(elapsed, 2)
    summary["throughput_q_s"] = round(summary.get("requests", 0) / elapsed, 2)
    summary["error_samples"] = report.errors[:5]
    summary["rest"] = probes.summary()
    print_report(summary)
    print(f"    {summary['throughput_q_s']} queries/s over {summary['seconds']} s")
    print(f"    REST while busy: p95 {summary['rest'].get('p95_ms')} ms, "
          f"{summary['rest'].get('errors')} error(s)")
    return summary


# ── C-STORE ───────────────────────────────────────────────────────────────


def instance(accession: str, study_uid: str, payload_kb: int) -> FileDataset:
    """A small but plausible CT instance — the broker routes on metadata only."""
    sop_uid = generate_uid()
    meta = FileMetaDataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID = CTImageStorage
    meta.MediaStorageSOPInstanceUID = sop_uid

    ds = FileDataset(None, {}, file_meta=meta, preamble=b"\0" * 128)
    ds.SOPClassUID = CTImageStorage
    ds.SOPInstanceUID = sop_uid
    ds.Modality = "CT"
    ds.AccessionNumber = accession
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = generate_uid()
    ds.SeriesNumber = "1"
    ds.InstanceNumber = "1"
    ds.PatientID = "LOADTEST"
    ds.PatientName = "Load^Test"
    ds.Rows = 8
    ds.Columns = 8
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.SamplesPerPixel = 1
    ds.PixelData = b"\0" * (payload_kb * 1024) if payload_kb else b"\0" * 128
    return ds


def one_cstore(host: str, port: int, aet: str, index: int, args, report: Report,
               refused: list) -> None:
    ds = instance(args.accession, args.study_uid, args.payload_kb)
    ae = AE(ae_title=CALLING_AET)
    ae.add_requested_context(CTImageStorage)
    started = time.perf_counter()
    try:
        assoc = ae.associate(host, port, ae_title=aet)
        if not assoc.is_established:
            report.error("association rejected")
            return
        try:
            status = assoc.send_c_store(ds)
        finally:
            assoc.release()
        if status is None:
            report.error("no C-STORE response")
            return
        report.add(time.perf_counter() - started)
        if status.Status != 0x0000:
            # A refusal at the spool budget is *documented* behaviour, not a bug —
            # count it separately instead of calling it an error.
            with report.lock:
                refused.append(status.Status)
    except Exception as exc:  # noqa: BLE001
        report.error(str(exc)[:120])


def scenario_cstore(args) -> dict:
    report = Report(f"cstore {args.instances}x{args.payload_kb}kB")
    print(f"── C-STORE: {args.instances} instances, {args.payload_kb} kB each, "
          f"concurrency {args.concurrency} ──")

    before = api_get(f"{args.api}/api/v1/spool/stats")
    print(f"   spool before: {before['queued']} queued, {before['dead']} dead, "
          f"budget {before['max_items']} items / {before['max_bytes']} bytes")

    stop = threading.Event()
    probes = Report("rest during cstore")
    probe_thread = threading.Thread(target=probe_rest, args=(args.api, stop, probes))
    probe_thread.start()

    refused: list = []
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [
            pool.submit(one_cstore, args.host, args.port, args.aet, index, args,
                        report, refused)
            for index in range(args.instances)
        ]
        for future in futures:
            future.result()
    elapsed = time.perf_counter() - started

    stop.set()
    probe_thread.join(timeout=15)

    after = api_get(f"{args.api}/api/v1/spool/stats")
    summary = report.summary()
    summary["seconds"] = round(elapsed, 2)
    summary["instances_s"] = round(summary.get("requests", 0) / elapsed, 2)
    summary["error_samples"] = report.errors[:5]
    summary["refused"] = len(refused)
    summary["refused_statuses"] = sorted({f"0x{s:04x}" for s in refused})
    summary["spool_before"] = before
    summary["spool_after"] = after
    summary["rest"] = probes.summary()

    print_report(summary)
    print(f"    {summary['instances_s']} instances/s over {summary['seconds']} s")
    print(f"    refused: {summary['refused']} "
          f"({', '.join(summary['refused_statuses']) or 'none'})")
    print(f"    spool after: {after['queued']} queued, {after['failed']} failed, "
          f"{after['dead']} dead, {after['bytes']} bytes")
    print(f"    REST while busy: p95 {summary['rest'].get('p95_ms')} ms, "
          f"{summary['rest'].get('errors')} error(s)")
    return summary


# ── entry point ───────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="scenario", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--host", default="127.0.0.1")
    common.add_argument("--port", type=int, default=11123)
    common.add_argument("--aet", default="MWLBROKER")
    common.add_argument("--api", default="http://127.0.0.1:19081")
    common.add_argument("--json", default="", help="write the raw numbers here")

    cfind = sub.add_parser("cfind", parents=[common], help="C-FIND fan-out under load")
    cfind.add_argument("--clients", type=int, default=20)
    cfind.add_argument("--queries", type=int, default=5)
    cfind.add_argument("--concurrency", type=int, default=20)
    cfind.add_argument("--dead-source", action="store_true",
                       help="add an upstream that hangs (timeout + breaker path)")
    cfind.add_argument("--dead-host", default="orthanc")
    cfind.add_argument("--dead-port", type=int, default=8042)
    cfind.set_defaults(func=scenario_cfind)

    cstore = sub.add_parser("cstore", parents=[common], help="C-STORE ingest / spool fill")
    cstore.add_argument("--instances", type=int, default=200)
    cstore.add_argument("--concurrency", type=int, default=8)
    cstore.add_argument("--payload-kb", type=int, default=64)
    cstore.add_argument("--accession", default="ACC-LOAD")
    cstore.add_argument("--study-uid", default="1.2.826.0.1.3680043.8.498.9999")
    cstore.set_defaults(func=scenario_cstore)

    args = parser.parse_args()
    summary = args.func(args)

    if args.json:
        with open(args.json, "w") as handle:
            json.dump(summary, handle, indent=2)
        print(f"    written: {args.json}")

    # A run that could not talk to the broker at all is a failure, not a result.
    return 0 if summary.get("requests") else 1


if __name__ == "__main__":
    sys.exit(main())
