"""The C-FIND aggregation: fan-out, merge, dedupe, station rules, cache, breaker.

Both the live DIMSE path (`dimse.BrokerSCP.handle_find`) and the operator's
preview (`POST /api/v1/simulate/worklist`) run **this** code — a preview that
used its own copy would prove nothing. The differences are explicit flags:

* `store_cache` — a preview may refresh the outage bridge with real answers.
* `count_metrics` — a preview is not a modality query, so it does not move the
  C-FIND counters.
* `record_seen` — provenance for C-STORE routing. A preview must never write it,
  otherwise looking at a case would change where its images are routed.
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from pydicom.dataset import Dataset
from sqlalchemy import select

from . import breaker, cache, local_worklist, merge_rules, merges, metrics, mpps, station_rules
from .db import session_factory
from .models import MwlSource
from .upstream import SourceCfg, merge_answers, query_source

log = logging.getLogger("mwl_broker.aggregation")

# Outcome markers per source (same strings the query log has always used).
ERROR = "error"
SKIPPED = breaker.SKIPPED


@dataclass
class SourceOutcome:
    """What one upstream contributed to this query (for the operator's view)."""

    name: str
    source_id: int | None
    answers: int | str
    stale: bool = False
    duration_ms: int | None = None
    breaker_state: str | None = None

    @property
    def ok(self) -> bool:
        return isinstance(self.answers, int)


@dataclass
class AggregationResult:
    """Everything a caller needs — merged answers plus how they came about."""

    items: list[Dataset] = field(default_factory=list)
    merged: list[tuple[Dataset, SourceCfg]] = field(default_factory=list)
    # raw per-source answers, in merge order — the preview shows which sources
    # knew a case and who won the dedupe
    collected: list[tuple[SourceCfg, list[Dataset]]] = field(default_factory=list)
    per_source: dict[str, int | str] = field(default_factory=dict)
    served_stale: list[str] = field(default_factory=list)
    hidden: int = 0
    # what the field-level merge rules changed (shown in the preview)
    field_changes: list[dict] = field(default_factory=list)
    station: str = ""
    rule_name: str | None = None
    duration_ms: int = 0
    outcomes: list[SourceOutcome] = field(default_factory=list)

    @property
    def status(self) -> str:
        """success (everything answered live) | partial | failed — as logged."""
        bad = [v for v in self.per_source.values() if isinstance(v, str)]
        answered = [v for v in self.per_source.values() if isinstance(v, int)]
        if not bad and not self.served_stale:
            return "success"
        return "partial" if answered else "failed"


def enabled_sources() -> list[SourceCfg]:
    """All enabled sources in priority order (deterministic merge order)."""
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
                priority=r.priority, tls=r.tls, tls_verify=r.tls_verify,
            )
            for r in rows
        ]


def source_config(source_id: int) -> SourceCfg | None:
    """One source as a query target (used by the per-source C-FIND test)."""
    with session_factory()() as s:
        r = s.get(MwlSource, source_id)
        if r is None:
            return None
        return SourceCfg(
            id=r.id, name=r.name, aet=r.aet, host=r.host, port=r.port,
            calling_aet=r.calling_aet, charset=r.charset, timeout_s=r.timeout_s,
            priority=r.priority, tls=r.tls, tls_verify=r.tls_verify,
        )


def query_one(src: SourceCfg, identifier: Dataset) -> tuple[list[Dataset], int, str]:
    """Ask a single source. Returns (answers, duration_ms, error)."""
    started = time.monotonic()
    try:
        answers = query_source(src, identifier)
        return answers, int((time.monotonic() - started) * 1000), ""
    except Exception as exc:  # a dead RIS is a result, not a crash
        return [], int((time.monotonic() - started) * 1000), str(exc)


def collect(
    identifier: Dataset,
    *,
    store_cache: bool = True,
    count_metrics: bool = True,
    only_source_id: int | None = None,
) -> AggregationResult:
    """Fan out, merge, dedupe and apply the station rule.

    `only_source_id` restricts the fan-out to one source (the C-FIND test on the
    sources page); the merge then has a single contributor, which is exactly what
    "what does this RIS answer?" means.
    """
    started = time.monotonic()
    result = AggregationResult()

    sources = enabled_sources()
    if only_source_id is not None:
        sources = [s for s in sources if s.id == only_source_id]
        if not sources:
            single = source_config(only_source_id)
            sources = [single] if single is not None else []

    # Per-station rules: the console's priority override decides who wins the
    # dedupe, and its visibility filter is applied after the merge.
    station = station_rules.query_station(identifier)
    rule = station_rules.matching_rule(station)
    sources = station_rules.order_sources(sources, rule)
    result.station = station
    result.rule_name = (rule or {}).get("name")

    collected: list[tuple[SourceCfg, list[Dataset]]] = []

    # Circuit breaker: skip sources that are known to be down instead of paying
    # their timeout on every single query.
    active = [src for src in sources if breaker.is_available(src.id)]
    for src in sources:
        if src in active:
            continue
        # Known to be down: skip the timeout — but serve the snapshot if we have
        # one, because that is exactly the outage case the cache is for.
        cached, _age = cache.stale_answers(src.id)
        if cached:
            result.per_source[src.name] = len(cached)
            result.served_stale.append(src.name)
            collected.append((src, cached))
            result.outcomes.append(SourceOutcome(src.name, src.id, len(cached), stale=True))
        else:
            result.per_source[src.name] = SKIPPED
            result.outcomes.append(
                SourceOutcome(src.name, src.id, SKIPPED,
                              breaker_state=breaker.state_of(src.id)),
            )

    if active:
        with ThreadPoolExecutor(max_workers=len(active)) as pool:
            futures = {pool.submit(query_source, src, identifier): src for src in active}
            for fut in as_completed(futures):
                src = futures[fut]
                try:
                    answers = fut.result(timeout=src.timeout_s + 5)
                    result.per_source[src.name] = len(answers)
                    if count_metrics:
                        metrics.UPSTREAM_ANSWERS.labels(source=src.name).inc(len(answers))
                    breaker.record_success(src.id)
                    # a live answer replaces the cached snapshot — completed
                    # orders disappear with it (the RIS is the truth)
                    if store_cache:
                        cache.store_snapshot(src.id, answers)
                    collected.append((src, answers))
                    result.outcomes.append(SourceOutcome(src.name, src.id, len(answers)))
                except Exception as exc:  # dead RIS must not break the query
                    log.warning("upstream %s query failed: %s", src.name, exc)
                    breaker.record_failure(src.id, str(exc))
                    cached, _age = cache.stale_answers(src.id)
                    if cached:
                        result.per_source[src.name] = len(cached)
                        result.served_stale.append(src.name)
                        collected.append((src, cached))
                        result.outcomes.append(
                            SourceOutcome(src.name, src.id, len(cached), stale=True),
                        )
                    else:
                        result.per_source[src.name] = ERROR
                        result.outcomes.append(SourceOutcome(src.name, src.id, ERROR))

    # Local items (emergencies) participate with the highest priority — the
    # pseudo source is not part of the fan-out, so it sorts first.
    local = local_worklist.answers_for(identifier)
    if local is not None:
        collected.append(local)
        result.per_source[local[0].name] = len(local[1])
        if count_metrics:
            metrics.UPSTREAM_ANSWERS.labels(source=local[0].name).inc(len(local[1]))
        result.outcomes.append(
            SourceOutcome(local[0].name, None, len(local[1])),
        )

    # restore priority order for deterministic merge
    order = {src.id: i for i, src in enumerate(sources)}
    collected.sort(key=lambda t: order.get(t[0].id, local_worklist.local_priority()))
    merged = merge_answers(collected)

    # Field-level merge rules may take single attributes from another source
    # (demographics from the HIS feed, study description from the RIS …). They
    # run before the station filter, so visibility rules see the final item.
    merged, field_changes = merge_rules.apply_field_rules(merged, collected)
    result.field_changes = field_changes

    merged, hidden = station_rules.filter_merged(merged, rule)

    # A performed step that the modality reported as COMPLETED/DISCONTINUED must
    # not come back on the worklist — that is the whole point of accepting MPPS.
    completed_hidden = 0
    if mpps.hide_completed():
        done = mpps.completed_identifiers()
        if done:
            kept = [(ds, src_) for ds, src_ in merged
                    if str(ds.get("AccessionNumber", "") or "") not in done]
            completed_hidden = len(merged) - len(kept)
            merged = kept

    result.hidden = hidden + completed_hidden
    if hidden:
        log.info("C-FIND for station %s: %d answer(s) hidden by rule '%s'",
                 station or "(any)", hidden, (rule or {}).get("name"))

    # IHE PIR: an image acquired under an old patient ID belongs to the current
    # one — the modality must see the resolved ID
    patient_ids = [str(ds.get("PatientID", "") or "") for ds in (item for item, _ in merged)]
    mapping = merges.resolve_many([pid for pid in patient_ids if pid])
    rewritten = merges.rewrite_datasets([ds for ds, _src in merged], mapping)
    if rewritten:
        log.info("patient merge: %d worklist item(s) served under the current ID", rewritten)

    result.collected = collected
    result.merged = merged
    result.items = [ds for ds, _src in merged]
    result.duration_ms = int((time.monotonic() - started) * 1000)
    if count_metrics:
        metrics.CFIND_REQUESTS.labels(result=result.status).inc()
        metrics.CFIND_DURATION.observe(result.duration_ms / 1000)
    return result
