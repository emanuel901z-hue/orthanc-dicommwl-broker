"""DICOM SCP: C-FIND MWL proxy/aggregator + C-STORE router.

Handlers run on pynetdicom worker threads — keep them synchronous, open a
fresh DB session per operation, never hold ORM objects across threads.
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from pydicom.dataset import Dataset
from pydicom.uid import generate_uid
from pynetdicom import AE, StoragePresentationContexts, evt
from pynetdicom.presentation import build_context
from pynetdicom.sop_class import (ModalityPerformedProcedureStep, ModalityWorklistInformationFind,
                                  Verification)
from sqlalchemy import select

from . import (aggregation, atna, breaker, cache, cstore, local_worklist, metrics,
               mpps, routing, settings_service, spool, station_rules, tls, transforms)
from .config import Settings
from .db import session_factory
from .models import QueryLog, RoutingRule, SeenItem, StoreLog, MwlSource, PacsTarget
from .upstream import SourceCfg, merge_answers, meta_text, query_source

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
S_NOT_FOUND = 0x0112


class BrokerSCP:
    """Owns the AE + listener so main.py can report/shutdown cleanly."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.server = None
        self.tls_server = None
        self.ae = self._build_ae(settings)

    @staticmethod
    def _build_ae(settings: Settings) -> AE:
        ae = AE(ae_title=settings.broker_aet)
        ae.add_supported_context(ModalityWorklistInformationFind)
        ae.add_supported_context(Verification)
        # MPPS: the modality reports the performed procedure step (N-CREATE/N-SET).
        # Offered only when switched on — a broker that does not report the state
        # back should not accept the step, otherwise the RIS waits forever.
        if mpps.enabled():
            ae.add_supported_context(ModalityPerformedProcedureStep)
        for cx in StoragePresentationContexts:
            ae.add_supported_context(cx.abstract_syntax)
        ae.maximum_associations = settings.max_associations
        return ae

    def start(self) -> None:
        handlers = [
            (evt.EVT_C_FIND, self.handle_find),
            (evt.EVT_C_STORE, self.handle_store),
            (evt.EVT_N_CREATE, self.handle_mpps_create),
            (evt.EVT_N_SET, self.handle_mpps_update),
            (evt.EVT_N_GET, self.handle_mpps_get),
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

        # Optional TLS listener *next to* the plain one: a staged rollout can
        # move one modality at a time without touching the others.
        self.tls_server = None
        if tls.inbound_enabled():
            try:
                context = tls.build_server_context()
            except Exception as exc:
                log.error("DICOM TLS listener not started: %s", exc)
            else:
                self.tls_server = self.ae.start_server(
                    ("0.0.0.0", tls.inbound_port()),
                    block=False,
                    evt_handlers=handlers,
                    ssl_context=context,
                )
                log.info("DICOM SCP with TLS listening: AET=%s port=%s (client auth: %s)",
                         self.settings.broker_aet, tls.inbound_port(),
                         tls.describe()["inbound_client_auth"])

    @property
    def listening(self) -> bool:
        return self.server is not None

    @property
    def tls_listening(self) -> bool:
        return self.tls_server is not None

    def shutdown(self) -> None:
        if self.tls_server is not None:
            self.tls_server.shutdown()
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
                priority=r.priority,
                tls=r.tls,
                tls_verify=r.tls_verify,
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    def handle_find(self, event):
        """C-FIND: fan out to all enabled sources, merge, stream answers.

        The aggregation itself lives in `aggregation.collect` — the operator's
        preview endpoint runs the same function, so a dry-run really shows what
        a modality would get.
        """
        calling = event.assoc.requestor.ae_title
        identifier = event.identifier

        if not self._calling_allowed(calling):
            log.warning("C-FIND rejected: calling AET %r not allowed", calling)
            atna.audit(atna.EVENT_SECURITY, outcome="8", broker_aet=self.settings.broker_aet,
                       source_aet=calling, query="C-FIND rejected (calling AET not allowed)",
                       event_type=("ITI-19", "Node Authentication"))
            yield S_OUT_OF_RESOURCES, None
            return

        result = aggregation.collect(identifier)
        merged = result.merged

        self._record_seen_items(merged)
        self._write_query_log(calling, identifier, len(merged), result.per_source,
                              result.duration_ms, result.status, result.served_stale)
        self._audit_query(calling, identifier, merged)

        for ds in result.items:
            yield S_PENDING, ds
        yield S_SUCCESS, None

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
            atna.audit(atna.EVENT_SECURITY, outcome="8", broker_aet=self.settings.broker_aet,
                       source_aet=calling, query="C-FIND rejected (calling AET not allowed)",
                       event_type=("ITI-19", "Node Authentication"))
            yield S_OUT_OF_RESOURCES, None
            return

        sources = self._enabled_sources()
        per_source: dict[str, int | str] = {}
        collected: list[tuple[SourceCfg, list[Dataset]]] = []
        served_stale: list[str] = []

        # Per-station rules: the console's priority override decides who wins the
        # dedupe, and its visibility filter is applied after the merge.
        station = station_rules.query_station(identifier)
        rule = station_rules.matching_rule(station)
        sources = station_rules.order_sources(sources, rule)

        # Circuit breaker: skip sources that are known to be down instead of
        # paying their timeout on every single query.
        active = [src for src in sources if breaker.is_available(src.id)]
        for src in sources:
            if src in active:
                continue
            # Known to be down: skip the timeout — but serve the snapshot if we
            # have one, because that is exactly the outage case the cache is for.
            cached, _age = cache.stale_answers(src.id)
            if cached:
                per_source[src.name] = len(cached)
                served_stale.append(src.name)
                collected.append((src, cached))
            else:
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
                        # a live answer replaces the cached snapshot — completed
                        # orders disappear with it (the RIS is the truth)
                        cache.store_snapshot(src.id, answers)
                        collected.append((src, answers))
                    except Exception as exc:  # dead RIS must not break the query
                        log.warning("upstream %s query failed: %s", src.name, exc)
                        breaker.record_failure(src.id, str(exc))
                        cached, age = cache.stale_answers(src.id)
                        if cached:
                            per_source[src.name] = len(cached)
                            served_stale.append(src.name)
                            collected.append((src, cached))
                        else:
                            per_source[src.name] = "error"

        # Local items (emergencies) participate with the highest priority — the
        # pseudo source is not part of the fan-out, so it sorts first.
        local = local_worklist.answers_for(identifier)
        if local is not None:
            collected.append(local)
            per_source[local[0].name] = len(local[1])
            metrics.UPSTREAM_ANSWERS.labels(source=local[0].name).inc(len(local[1]))

        # restore priority order for deterministic merge
        order = {src.id: i for i, src in enumerate(sources)}
        collected.sort(key=lambda t: order.get(t[0].id, local_worklist.local_priority()))
        merged = merge_answers(collected)

        merged, hidden = station_rules.filter_merged(merged, rule)
        if hidden:
            log.info("C-FIND for station %s: %d answer(s) hidden by rule '%s'",
                     station or "(any)", hidden, rule["name"])

        self._record_seen_items(merged)

        duration_ms = int((time.monotonic() - started) * 1000)
        # "error" (query failed) and "breaker_open" (skipped) are both
        # non-answer outcomes; any int means a source actually answered.
        bad = [v for v in per_source.values() if isinstance(v, str)]
        answered = [v for v in per_source.values() if isinstance(v, int)]
        status = (
            "success" if not bad and not served_stale
            else "partial" if answered
            else "failed"
        )
        metrics.CFIND_REQUESTS.labels(result=status).inc()
        metrics.CFIND_DURATION.observe(duration_ms / 1000)
        self._write_query_log(calling, identifier, len(merged), per_source, duration_ms,
                              status, served_stale)

        self._audit_query(calling, identifier, merged)

        for ds, _src in merged:
            yield S_PENDING, ds
        yield S_SUCCESS, None

    def _audit_query(self, calling: str, identifier: Dataset,
                     merged: list[tuple[Dataset, SourceCfg]]) -> None:
        """One ATNA Query message per C-FIND, including the patients disclosed."""
        summary = self._query_summary(identifier)
        flat: dict[str, str] = {}
        for key, value in summary.items():
            if isinstance(value, dict):
                flat.update({k: str(v) for k, v in value.items()})
            else:
                flat[key] = str(value)
        keys = " ".join(f"{k}={v}" for k, v in flat.items())
        patients = [str(ds.get("PatientID", "") or "") for ds, _src in merged]
        patients = [pid for pid in dict.fromkeys(patients) if pid][:50]
        atna.audit(
            atna.EVENT_QUERY, broker_aet=self.settings.broker_aet,
            source_aet=calling, query=keys[:400],
            event_type=("ITI-20", "Modality Worklist Query"),
        )
        for patient_id in patients:
            atna.audit(
                atna.EVENT_QUERY, broker_aet=self.settings.broker_aet,
                source_aet=calling, patient_id=patient_id,
                query=f"worklist disclosure {keys[:120]}",
                event_type=("ITI-20", "Modality Worklist Query"),
            )

    # ------------------------------------------------------------------
    def handle_mpps_create(self, event):
        """N-CREATE: the modality started an examination (MPPS IN PROGRESS).

        The SCU may **omit** the SOP Instance UID and leave it to the SCP
        (DICOM PS3.7): dcm4che's `mppsscu` does exactly that, and this handler
        answered "Cannot understand" — the examination never reached the RIS.
        We assign a UID and return it in the response (pynetdicom takes it from
        the returned dataset), so the following N-SET can name the step.
        """
        if not mpps.enabled():
            return S_CANNOT_UNDERSTAND, None
        sop_uid = str(getattr(event.request, "AffectedSOPInstanceUID", "") or "")
        assigned = None
        if not sop_uid:
            sop_uid = generate_uid()
            assigned = Dataset()
            assigned.AffectedSOPInstanceUID = sop_uid
            log.info("MPPS: SCU left the SOP Instance UID to us — assigned %s", sop_uid)
        try:
            mpps.record_create(sop_uid, event.attribute_list)
        except Exception as exc:  # never kill the association over bookkeeping
            log.warning("MPPS create failed: %s", exc)
            return S_CANNOT_UNDERSTAND, None
        return S_SUCCESS, assigned

    def handle_mpps_update(self, event):
        """N-SET: status change of a performed procedure step."""
        if not mpps.enabled():
            return S_CANNOT_UNDERSTAND, None
        sop_uid = str(getattr(event.request, "RequestedSOPInstanceUID", "") or "")
        if not sop_uid:
            return S_CANNOT_UNDERSTAND, None
        try:
            mpps.record_update(sop_uid, event.attribute_list)
        except Exception as exc:
            log.warning("MPPS update failed: %s", exc)
            return S_CANNOT_UNDERSTAND, None
        return S_SUCCESS, None

    def handle_mpps_get(self, event):
        """N-GET: a modality reads back its performed procedure step.

        Some modalities verify what the broker stored (status, identifiers)
        before they continue — without N-GET they cannot.
        """
        if not mpps.enabled():
            return S_CANNOT_UNDERSTAND, None
        sop_uid = str(getattr(event.request, "RequestedSOPInstanceUID", "") or "")
        step = mpps.get_step_by_uid(sop_uid)
        if step is None:
            return S_NOT_FOUND, None
        return S_SUCCESS, mpps.to_dataset(step)

    def _record_seen_items(self, merged: list[tuple[Dataset, SourceCfg]]) -> None:
        if not merged:
            return
        try:
            with session_factory()() as s:
                for ds, src in merged:
                    sps_seq = ds.get("ScheduledProcedureStepSequence") or []
                    sps_id = meta_text(
                        sps_seq[0].get("ScheduledProcedureStepID") if sps_seq else "", 64,
                    )
                    s.add(
                        SeenItem(
                            accession=meta_text(ds.get("AccessionNumber"), 64),
                            sps_id=sps_id,
                            study_uid=meta_text(ds.get("StudyInstanceUID"), 128),
                            patient_id=meta_text(ds.get("PatientID"), 64),
                            source_id=src.id,
                        )
                    )
                s.commit()
                metrics.SEEN_ITEMS.set(s.query(SeenItem).count())
        except Exception as exc:
            log.error("seen_items write failed: %s", exc)

    def _write_query_log(self, calling, identifier, answers, per_source, duration_ms, status,
                         served_stale: list[str] | None = None):
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
                        served_stale=served_stale or None,
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
            atna.audit(atna.EVENT_SECURITY, outcome="8", broker_aet=self.settings.broker_aet,
                       source_aet=calling, query="C-STORE rejected (calling AET not allowed)",
                       event_type=("ITI-19", "Node Authentication"))
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
        patient_id = str(getattr(ds, "PatientID", "") or "")

        strict = settings_service.get_bool("strict_store_status")
        source_id, target = self._resolve_target(accession, study_uid)
        if target is None:
            self._write_store_log(calling, sop_uid, study_uid, accession, source_id, None, "unrouted", "no target")
            metrics.CSTORE_TOTAL.labels(target="none", status="unrouted").inc()
            log.warning("C-STORE unrouted: acc=%s study=%s", accession, study_uid)
            return S_OUT_OF_RESOURCES if strict else S_SUCCESS

        applied = self._apply_transforms(ds, source_id, target.id)

        # ATNA: the instance arrived (Import) and is forwarded (Export)
        atna.audit(atna.EVENT_IMPORT, broker_aet=self.settings.broker_aet,
                   source_aet=calling, destination_aet=target.aet,
                   patient_id=patient_id, study_uid=study_uid, accession=accession,
                   event_type=("ITI-41", "DICOM Instance Received"))
        atna.audit(atna.EVENT_EXPORT, broker_aet=self.settings.broker_aet,
                   source_aet=self.settings.broker_aet, destination_aet=target.aet,
                   patient_id=patient_id, study_uid=study_uid, accession=accession,
                   event_type=("ITI-41", "DICOM Instance Forwarded"))

        # The instance is already spooled or was delivered before: a repeated
        # C-STORE (the modality never saw a confirmation) must not store it twice.
        if spool.is_duplicate(sop_uid):
            self._write_store_log(calling, sop_uid, study_uid, accession, source_id,
                                  target.id, "duplicate", "already spooled or delivered",
                                  applied)
            metrics.CSTORE_TOTAL.labels(target=target.name, status="duplicate").inc()
            log.info("C-STORE %s is a duplicate — acknowledged without forwarding", sop_uid)
            return S_SUCCESS

        error = ""
        try:
            self._forward_store(ds, target)
        except Exception as exc:
            error = str(exc)
            log.error("forward to %s failed: %s", target.name, exc)

        if error:
            # Store and forward: keep the instance instead of losing it.
            outcome = spool.enqueue(ds, source_id, target.id, target.name, error)
            if outcome in ("queued", "duplicate"):
                self._write_store_log(calling, sop_uid, study_uid, accession, source_id,
                                      target.id, "queued", error, applied)
                metrics.CSTORE_TOTAL.labels(target=target.name, status="queued").inc()
                log.warning("C-STORE spooled for %s (%s) — %s", target.name, outcome, error)
                # the instance is safe: telling the modality "success" stops it
                # from retrying what we will deliver anyway
                if spool.accept_when_queued():
                    return S_SUCCESS
                return S_OUT_OF_RESOURCES if strict else S_SUCCESS
            log.error("C-STORE not spooled (%s) — falling back to the store policy", outcome)

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

    @staticmethod
    def _resolve_target(accession: str, study_uid: str):
        """seen_items lookup → routing rule → default target.

        Uses the shared resolver in `routing.py` — the simulator runs exactly
        the same code, so a dry-run cannot drift from the live path.
        """
        with session_factory()() as s:
            decision = routing.resolve(s, accession, study_uid)
        return decision.source_id, decision.target

    @staticmethod
    def _forward_store(ds: Dataset, target: routing.TargetCfg) -> None:
        """Live forwarding — shares the code with the spool retry worker."""
        cstore.send_store(ds, target)

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
