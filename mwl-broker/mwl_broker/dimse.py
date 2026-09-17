"""DICOM SCP: C-FIND MWL proxy/aggregator + C-STORE router.

Handlers run on pynetdicom worker threads — keep them synchronous, open a
fresh DB session per operation, never hold ORM objects across threads.
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from pydicom.dataset import Dataset
from pynetdicom import AE, StoragePresentationContexts, evt
from pynetdicom.presentation import build_context
from pynetdicom.sop_class import ModalityWorklistInformationFind, Verification
from sqlalchemy import select

from . import breaker, metrics, settings_service, transforms
from .config import Settings
from .db import session_factory
from .models import QueryLog, RoutingRule, SeenItem, StoreLog, MwlSource, PacsTarget
from .upstream import SourceCfg, merge_answers, query_source

log = logging.getLogger("mwl_broker.dimse")

# Query keys worth logging — deliberately excludes PatientName/PatientID (PHI).
LOGGABLE_QUERY_KEYS = (
    "AccessionNumber",
    "StudyInstanceUID",
    "RequestedProcedureID",
    "Modality",
)
LOGGABLE_SPS_KEYS = (
    "Modality",
    "ScheduledStationAETitle",
    "ScheduledProcedureStepStartDate",
    "ScheduledProcedureStepStartTime",
)

# DIMSE status codes
S_SUCCESS = 0x0000
S_PENDING = 0xFF00
S_OUT_OF_RESOURCES = 0xA700
S_CANNOT_UNDERSTAND = 0xC000


class BrokerSCP:
    """Owns the AE + listener so main.py can report/shutdown cleanly."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.server = None
        self.ae = self._build_ae(settings)

    @staticmethod
    def _build_ae(settings: Settings) -> AE:
        ae = AE(ae_title=settings.broker_aet)
        ae.add_supported_context(ModalityWorklistInformationFind)
        ae.add_supported_context(Verification)
        for cx in StoragePresentationContexts:
            ae.add_supported_context(cx.abstract_syntax)
        ae.maximum_associations = settings.max_associations
        return ae

    def start(self) -> None:
        handlers = [
            (evt.EVT_C_FIND, self.handle_find),
            (evt.EVT_C_STORE, self.handle_store),
        ]
        self.server = self.ae.start_server(
            ("0.0.0.0", self.settings.dicom_port),
            block=False,
            evt_handlers=handlers,
        )
        log.info(
            "DICOM SCP listening: AET=%s port=%s",
            self.settings.broker_aet,
            self.settings.dicom_port,
        )

    @property
    def listening(self) -> bool:
        return self.server is not None

    def shutdown(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server = None

    # ------------------------------------------------------------------
    def _calling_allowed(self, calling_aet: str) -> bool:
        allowed = settings_service.get_aets()
        return not allowed or calling_aet in allowed

    def _enabled_sources(self) -> list[SourceCfg]:
        with session_factory()() as s:
            rows = s.scalars(
                select(MwlSource)
                .where(MwlSource.enabled.is_(True))
                .order_by(MwlSource.priority, MwlSource.id)
            ).all()
        return [
            SourceCfg(
                id=r.id, name=r.name, aet=r.aet, host=r.host, port=r.port,
                calling_aet=r.calling_aet, charset=r.charset, timeout_s=r.timeout_s,
            )
            for r in rows
        ]

    @staticmethod
    def _query_summary(identifier: Dataset) -> dict:
        keys = {k: str(identifier.get(k)) for k in LOGGABLE_QUERY_KEYS if identifier.get(k)}
        sps_seq = identifier.get("ScheduledProcedureStepSequence") or []
        if sps_seq:
            keys["SPS"] = {k: str(sps_seq[0].get(k)) for k in LOGGABLE_SPS_KEYS if sps_seq[0].get(k)}
        return keys

    # ------------------------------------------------------------------
    def handle_find(self, event):
        """C-FIND: fan out to all enabled sources, merge, stream answers."""
        calling = event.assoc.requestor.ae_title
        started = time.monotonic()
        identifier = event.identifier

        if not self._calling_allowed(calling):
            log.warning("C-FIND rejected: calling AET %r not allowed", calling)
            yield S_OUT_OF_RESOURCES, None
            return

        sources = self._enabled_sources()
        per_source: dict[str, int | str] = {}
        collected: list[tuple[SourceCfg, list[Dataset]]] = []

        # Circuit breaker: skip sources that are known to be down instead of
        # paying their timeout on every single query.
        active = [src for src in sources if breaker.is_available(src.id)]
        for src in sources:
            if src not in active:
                per_source[src.name] = breaker.SKIPPED

        if active:
            with ThreadPoolExecutor(max_workers=len(active)) as pool:
                futures = {
                    pool.submit(query_source, src, identifier): src for src in active
                }
                for fut in as_completed(futures):
                    src = futures[fut]
                    try:
                        answers = fut.result(timeout=src.timeout_s + 5)
                        per_source[src.name] = len(answers)
                        metrics.UPSTREAM_ANSWERS.labels(source=src.name).inc(len(answers))
                        breaker.record_success(src.id)
                        collected.append((src, answers))
                    except Exception as exc:  # dead RIS must not break the query
                        log.warning("upstream %s query failed: %s", src.name, exc)
                        per_source[src.name] = "error"
                        breaker.record_failure(src.id, str(exc))

        # restore priority order for deterministic merge
        order = {src.id: i for i, src in enumerate(sources)}
        collected.sort(key=lambda t: order[t[0].id])
        merged = merge_answers(collected)

        self._record_seen_items(merged)

        duration_ms = int((time.monotonic() - started) * 1000)
        # "error" (query failed) and "breaker_open" (skipped) are both
        # non-answer outcomes; any int means a source actually answered.
        bad = [v for v in per_source.values() if isinstance(v, str)]
        answered = [v for v in per_source.values() if isinstance(v, int)]
        status = (
            "success" if not bad
            else "partial" if answered
            else "failed"
        )
        metrics.CFIND_REQUESTS.labels(result=status).inc()
        metrics.CFIND_DURATION.observe(duration_ms / 1000)
        self._write_query_log(calling, identifier, len(merged), per_source, duration_ms, status)

        for ds, _src in merged:
            yield S_PENDING, ds
        yield S_SUCCESS, None

    def _record_seen_items(self, merged: list[tuple[Dataset, SourceCfg]]) -> None:
        if not merged:
            return
        try:
            with session_factory()() as s:
                for ds, src in merged:
                    sps_seq = ds.get("ScheduledProcedureStepSequence") or []
                    sps_id = str(sps_seq[0].get("ScheduledProcedureStepID", "")) if sps_seq else ""
                    s.add(
                        SeenItem(
                            accession=str(ds.get("AccessionNumber", "")),
                            sps_id=sps_id,
                            study_uid=str(ds.get("StudyInstanceUID", "")),
                            patient_id=str(ds.get("PatientID", "")),
                            source_id=src.id,
                        )
                    )
                s.commit()
                metrics.SEEN_ITEMS.set(s.query(SeenItem).count())
        except Exception as exc:
            log.error("seen_items write failed: %s", exc)

    def _write_query_log(self, calling, identifier, answers, per_source, duration_ms, status):
        try:
            with session_factory()() as s:
                s.add(
                    QueryLog(
                        calling_aet=calling,
                        query_keys=self._query_summary(identifier),
                        answers=answers,
                        per_source=per_source,
                        duration_ms=duration_ms,
                        status=status,
                    )
                )
                s.commit()
        except Exception as exc:
            log.error("query_log write failed: %s", exc)

    # ------------------------------------------------------------------
    def handle_store(self, event):
        """C-STORE: route to PACS target based on originating worklist source."""
        calling = event.assoc.requestor.ae_title
        if not self._calling_allowed(calling):
            log.warning("C-STORE rejected: calling AET %r not allowed", calling)
            return S_OUT_OF_RESOURCES

        try:
            ds = event.dataset
            ds.file_meta = event.file_meta
        except Exception as exc:
            log.error("C-STORE: cannot read dataset: %s", exc)
            return S_CANNOT_UNDERSTAND

        accession = str(getattr(ds, "AccessionNumber", "") or "")
        study_uid = str(getattr(ds, "StudyInstanceUID", "") or "")
        sop_uid = str(getattr(ds, "SOPInstanceUID", "") or "")

        strict = settings_service.get_bool("strict_store_status")
        source_id, target = self._resolve_target(accession, study_uid)
        if target is None:
            self._write_store_log(calling, sop_uid, study_uid, accession, source_id, None, "unrouted", "no target")
            metrics.CSTORE_TOTAL.labels(target="none", status="unrouted").inc()
            log.warning("C-STORE unrouted: acc=%s study=%s", accession, study_uid)
            return S_OUT_OF_RESOURCES if strict else S_SUCCESS

        applied = self._apply_transforms(ds, source_id, target.id)

        error = ""
        try:
            self._forward_store(ds, target)
        except Exception as exc:
            error = str(exc)
            log.error("forward to %s failed: %s", target.name, exc)

        status_str = "success" if not error else "failed"
        self._write_store_log(calling, sop_uid, study_uid, accession, source_id, target.id,
                              status_str, error, applied)
        metrics.CSTORE_TOTAL.labels(target=target.name, status=status_str).inc()
        if error:
            return S_OUT_OF_RESOURCES if strict else S_SUCCESS
        return S_SUCCESS

    @staticmethod
    def _apply_transforms(ds: Dataset, source_id: int | None, target_id: int) -> list[str]:
        """Apply all matching transform rules before forwarding."""
        try:
            with session_factory()() as s:
                rules = transforms.applicable(s, source_id, target_id)
        except Exception as exc:
            log.error("transform lookup failed: %s", exc)
            return []
        applied, errors = transforms.apply_transforms(ds, rules)
        if applied:
            log.info("transforms applied (acc=%s): %s%s",
                     getattr(ds, "AccessionNumber", ""), ", ".join(applied),
                     f" — {len(errors)} op(s) failed" if errors else "")
        return applied

    def _resolve_target(self, accession: str, study_uid: str):
        """seen_items lookup → routing rule → target; else default target."""
        with session_factory()() as s:
            seen = None
            if accession:
                seen = s.scalars(
                    select(SeenItem)
                    .where(SeenItem.accession == accession)
                    .order_by(SeenItem.ts.desc())
                ).first()
            if seen is None and study_uid:
                seen = s.scalars(
                    select(SeenItem)
                    .where(SeenItem.study_uid == study_uid)
                    .order_by(SeenItem.ts.desc())
                ).first()

            target = None
            if seen is not None:
                rule = s.scalars(
                    select(RoutingRule)
                    .where(RoutingRule.source_id == seen.source_id, RoutingRule.enabled.is_(True))
                    .order_by(RoutingRule.priority, RoutingRule.id)
                ).first()
                if rule is not None:
                    target = s.get(PacsTarget, rule.target_id)
            if target is None:
                target = s.scalars(
                    select(PacsTarget).where(
                        PacsTarget.is_default.is_(True), PacsTarget.enabled.is_(True)
                    )
                ).first()
            if target is not None and not target.enabled:
                target = None
            # detach
            if target is not None:
                t = PacsTarget(
                    id=target.id, name=target.name, aet=target.aet, host=target.host,
                    port=target.port, calling_aet=target.calling_aet, enabled=target.enabled,
                    is_default=target.is_default,
                )
                return (seen.source_id if seen else None), t
            return (seen.source_id if seen else None), None

    @staticmethod
    def _forward_store(ds: Dataset, target: PacsTarget) -> None:
        ae = AE(ae_title=target.calling_aet)
        ctx = build_context(ds.SOPClassUID, [ds.file_meta.TransferSyntaxUID])
        assoc = ae.associate(target.host, target.port, ae_title=target.aet, contexts=[ctx])
        if not assoc.is_established:
            raise ConnectionError("association rejected")
        try:
            status = assoc.send_c_store(ds)
            if status is None or status.Status != 0x0000:
                raise ConnectionError(f"C-STORE status {getattr(status, 'Status', 'none')}")
        finally:
            assoc.release()

    @staticmethod
    def _write_store_log(calling, sop_uid, study_uid, accession, source_id, target_id,
                         status, error, applied_transforms=None):
        try:
            with session_factory()() as s:
                s.add(
                    StoreLog(
                        calling_aet=calling, sop_instance_uid=sop_uid, study_uid=study_uid,
                        accession=accession, source_id=source_id, target_id=target_id,
                        status=status, error=error[:512],
                        applied_transforms=list(applied_transforms or []),
                    )
                )
                s.commit()
        except Exception as exc:
            log.error("store_log write failed: %s", exc)
