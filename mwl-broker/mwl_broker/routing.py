"""Store-routing resolution — shared by the live C-STORE path and the simulator.

The simulator must not re-implement this: whatever `resolve()` returns is
exactly what a real instance would do.
"""
from dataclasses import dataclass

from sqlalchemy import select

from .models import PacsTarget, RoutingRule, SeenItem


@dataclass(frozen=True)
class TargetCfg:
    """Detached copy of a PACS target (safe across DIMSE worker threads)."""

    id: int
    name: str
    aet: str
    host: str
    port: int
    calling_aet: str
    enabled: bool
    is_default: bool
    tls: bool = False
    tls_verify: bool = True


@dataclass(frozen=True)
class RoutingDecision:
    """Where an instance would go and why."""

    source_id: int | None
    target: TargetCfg | None
    rule_id: int | None
    matched_via: str  # accession | study_uid | default | none
    reason: str


def _target_cfg(row: PacsTarget | None) -> TargetCfg | None:
    if row is None or not row.enabled:
        return None
    return TargetCfg(
        id=row.id, name=row.name, aet=row.aet, host=row.host, port=row.port,
        calling_aet=row.calling_aet, enabled=row.enabled, is_default=row.is_default,
        tls=row.tls, tls_verify=row.tls_verify,
    )


def resolve(session, accession: str = "", study_uid: str = "") -> RoutingDecision:
    """seen_items lookup → routing rule → default target."""
    seen = None
    matched_via = "none"
    if accession:
        seen = session.scalars(
            select(SeenItem)
            .where(SeenItem.accession == accession)
            .order_by(SeenItem.ts.desc())
        ).first()
        if seen is not None:
            matched_via = "accession"
    if seen is None and study_uid:
        seen = session.scalars(
            select(SeenItem)
            .where(SeenItem.study_uid == study_uid)
            .order_by(SeenItem.ts.desc())
        ).first()
        if seen is not None:
            matched_via = "study_uid"

    source_id = seen.source_id if seen is not None else None

    if seen is not None:
        rule = session.scalars(
            select(RoutingRule)
            .where(RoutingRule.source_id == seen.source_id, RoutingRule.enabled.is_(True))
            .order_by(RoutingRule.priority, RoutingRule.id)
        ).first()
        if rule is not None:
            target = _target_cfg(session.get(PacsTarget, rule.target_id))
            if target is not None:
                return RoutingDecision(
                    source_id=source_id, target=target, rule_id=rule.id,
                    matched_via=matched_via,
                    reason=f"rule {rule.id} ({rule.priority}) matched via {matched_via}",
                )

    default = session.scalars(
        select(PacsTarget).where(
            PacsTarget.is_default.is_(True), PacsTarget.enabled.is_(True)
        )
    ).first()
    target = _target_cfg(default)
    if target is None:
        return RoutingDecision(
            source_id=source_id, target=None, rule_id=None, matched_via="none",
            reason="no matching rule and no enabled default target — the store is rejected",
        )
    return RoutingDecision(
        source_id=source_id, target=target, rule_id=None, matched_via="default",
        reason=f"no matching rule — default target '{target.name}'",
    )
