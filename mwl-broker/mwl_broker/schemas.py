"""Pydantic API schemas.

Field descriptions feed the generated OpenAPI documentation — keep them
up to date (Swagger UI at /docs, spec at /openapi.json).
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SourceIn(BaseModel):
    """Upstream MWL source (RIS/KIS) the broker fans C-FIND queries out to."""

    name: str = Field(
        min_length=1, max_length=64, examples=["ris-a"],
        description="Unique display name used in logs and monitoring.",
    )
    aet: str = Field(
        min_length=1, max_length=16, examples=["RIS_A"],
        description="Called AE title of the upstream MWL SCP.",
    )
    host: str = Field(
        min_length=1, examples=["ris-a.hospital.local"],
        description="Hostname/IP of the upstream system (docker service name works too).",
    )
    port: int = Field(
        ge=1, le=65535, examples=[104],
        description="DICOM port of the upstream MWL SCP.",
    )
    calling_aet: str = Field(
        default="MWLBROKER",
        description="Calling AE title used for outgoing associations.",
    )
    charset: str = Field(
        default="ISO_IR 100", examples=["ISO_IR 100", "ISO_IR 192"],
        description="SpecificCharacterSet negotiated with this source "
                    "(ISO_IR 100 = Latin-1, ISO_IR 192 = UTF-8).",
    )
    enabled: bool = Field(
        default=True,
        description="Disabled sources are skipped in the C-FIND fan-out and echo monitoring.",
    )
    timeout_s: int = Field(
        default=10, ge=1, le=120,
        description="DIMSE/network timeout per association in seconds.",
    )
    priority: int = Field(
        default=100,
        description="Merge order: lower values are queried first and win during deduplication.",
    )
    cache_stale_on_error: bool = Field(
        default=True,
        description="Answer this source from the worklist cache while it is "
                    "unreachable (bounded by the stale window).",
    )
    cache_refresh_s: int = Field(
        default=0, ge=0, le=86400,
        description="Background refresh interval for the cached snapshot in "
                    "seconds (0 = off, refreshed only by live queries).",
    )


class SourceOut(SourceIn):
    model_config = ConfigDict(from_attributes=True)
    id: int = Field(description="Row ID.")
    created_at: datetime = Field(description="Creation timestamp (UTC).")


class TargetIn(BaseModel):
    """PACS target that receives forwarded C-STORE traffic."""

    name: str = Field(
        min_length=1, max_length=64, examples=["pacs-kh"],
        description="Unique display name used in logs and monitoring.",
    )
    aet: str = Field(
        min_length=1, max_length=16, examples=["PACS_KH"],
        description="Called AE title of the PACS storage SCP.",
    )
    host: str = Field(
        min_length=1, examples=["pacs.hospital.local"],
        description="Hostname/IP of the PACS (docker service name works too).",
    )
    port: int = Field(
        ge=1, le=65535, examples=[104],
        description="DICOM port of the PACS storage SCP.",
    )
    calling_aet: str = Field(
        default="MWLBROKER",
        description="Calling AE title used for forwarded C-STORE associations.",
    )
    enabled: bool = Field(
        default=True,
        description="Disabled targets are never selected for forwarding.",
    )
    is_default: bool = Field(
        default=False,
        description="Fallback target for stores without a matching routing rule "
                    "(exactly one target should be the default).",
    )


class TargetOut(TargetIn):
    model_config = ConfigDict(from_attributes=True)
    id: int = Field(description="Row ID.")
    created_at: datetime = Field(description="Creation timestamp (UTC).")


class RuleIn(BaseModel):
    """Routing rule: instances whose worklist came from `source_id` are
    forwarded to `target_id`."""

    source_id: int = Field(description="ID of the originating MWL source.")
    target_id: int = Field(description="ID of the PACS target to forward to.")
    priority: int = Field(
        default=100,
        description="Lower values win when several rules match the same source.",
    )
    enabled: bool = Field(default=True, description="Disabled rules are ignored.")


class RuleOut(RuleIn):
    model_config = ConfigDict(from_attributes=True)
    id: int = Field(description="Row ID.")


class TransformOperation(BaseModel):
    """One DICOM attribute modification.

    `tag` must be a real DICOM keyword (validated against the data
    dictionary). SOP/Study/Series UIDs are rejected — rewriting them would
    break PACS linkage.
    """

    op: Literal["set", "remove", "prefix", "suffix", "replace", "copy"] = Field(
        description="set = replace value · remove = delete tag · prefix/suffix = "
                    "wrap the existing value · replace = regex substitution · "
                    "copy = take the value of another tag.",
        examples=["prefix"],
    )
    tag: str = Field(
        description="DICOM keyword to modify.", examples=["PatientID"],
    )
    value: str | None = Field(
        default=None,
        description="Value for set/prefix/suffix; replacement for replace.",
        examples=["KH_"],
    )
    pattern: str | None = Field(
        default=None,
        description="Regular expression searched in the existing value (op=replace).",
        examples=["^ALT"],
    )
    from_tag: str | None = Field(
        default=None,
        description="Source keyword to copy from (op=copy).",
        examples=["RequestedProcedureDescription"],
    )


class TransformIn(BaseModel):
    """DICOM attribute modifications applied before forwarding a C-STORE.

    Scope: `source_id` / `target_id` may be null (= any). All applicable,
    enabled rules are applied in priority order.
    """

    name: str = Field(
        min_length=1, max_length=64, examples=["kh-accession-prefix"],
        description="Unique rule name (also recorded in the store log).",
    )
    enabled: bool = Field(default=True, description="Disabled rules are not applied.")
    priority: int = Field(
        default=100, description="Application order — lower values run first.",
    )
    source_id: int | None = Field(
        default=None, description="Only apply to stores from this source (null = any).",
    )
    target_id: int | None = Field(
        default=None, description="Only apply to stores forwarded to this target (null = any).",
    )
    operations: list[TransformOperation] = Field(
        description="Operations applied in order; a failing operation is logged "
                    "and skipped (the instance is still forwarded).",
    )


class TransformOut(TransformIn):
    model_config = ConfigDict(from_attributes=True)
    id: int = Field(description="Row ID.")
    created_at: datetime = Field(description="Creation timestamp (UTC).")


class RuleByNameIn(BaseModel):
    """Routing rule in the portable export format (referenced by name)."""

    source: str = Field(description="Name of the upstream source.")
    target: str = Field(description="Name of the store target.")
    priority: int = Field(default=100, description="Lower values win.")
    enabled: bool = Field(default=True, description="Disabled rules are ignored.")


class TransformImportIn(BaseModel):
    """Modify rule in the portable export format (scope referenced by name)."""

    name: str = Field(min_length=1, max_length=64, description="Unique rule name.")
    enabled: bool = Field(default=True, description="Disabled rules are not applied.")
    priority: int = Field(default=100, description="Application order — lower runs first.")
    source: str | None = Field(default=None, description="Scope: source name (null = any).")
    target: str | None = Field(default=None, description="Scope: target name (null = any).")
    operations: list[TransformOperation] = Field(description="DICOM modifications in order.")


class ConfigImportIn(BaseModel):
    """Portable configuration document (see GET /config/export)."""

    schema_version: int = Field(description="Export format version — must match the broker's.")
    sources: list[SourceIn] = Field(default_factory=list, description="Upstream sources.")
    targets: list[TargetIn] = Field(default_factory=list, description="Store targets.")
    rules: list[RuleByNameIn] = Field(default_factory=list, description="Routing rules.")
    transforms: list[TransformImportIn] = Field(default_factory=list, description="Modify rules.")
    settings: dict[str, str] = Field(
        default_factory=dict, description="Runtime setting overrides (key → value).",
    )


class ConfigExportOut(ConfigImportIn):
    """Full configuration as exported by the broker."""

    exported_at: datetime | None = Field(
        default=None, description="When the document was created (UTC).",
    )


class ImportChangeOut(BaseModel):
    """One change an import would make."""

    entity: str = Field(description="source | target | rule | transform | setting.")
    action: str = Field(description="create | update.")
    name: str = Field(description="Name (or key) of the affected entry.")
    fields: dict = Field(description="Field values the import would apply.")


class ImportPlanOut(BaseModel):
    """Result of an import: the dry-run diff or the applied changes."""

    schema_version: int = Field(description="Format version of the document.")
    dry_run: bool = Field(description="True when nothing was written.")
    changes: list[ImportChangeOut] = Field(description="Planned/applied changes.")
    skipped: list[str] = Field(description="Entries that could not be applied (with reason).")
    summary: dict = Field(description="Counts: create / update / skipped.")


class AuditEntryOut(BaseModel):
    """One configuration change-log entry."""

    id: int = Field(description="Row ID (use it for rollback).")
    ts: datetime = Field(description="When the change happened (UTC).")
    actor: str = Field(description="Operator identity (header) or 'api'.")
    action: str = Field(description="e.g. create.source, update.rule, import.transform.")
    entity: str = Field(description="source | target | rule | transform | setting.")
    entity_id: int | None = Field(default=None, description="Row ID of the affected entry.")
    before_json: dict | None = Field(default=None, description="State before the change.")
    after_json: dict | None = Field(default=None, description="State after the change.")
    correlation_id: str = Field(default="", description="Request correlation ID.")


class RollbackOut(BaseModel):
    """Result of rolling a change-log entry back."""

    audit_id: int = Field(description="The change-log entry that was rolled back.")
    entity: str = Field(description="Affected entity type.")
    action: str = Field(description="What the rollback did (delete | recreate | restore).")
    message: str = Field(description="Human-readable result.")


class SimulateRouteIn(BaseModel):
    """A case to check against the routing rules."""

    accession: str = Field(default="", description="Accession number of the case.", examples=["ACC-A-001"])
    study_uid: str = Field(default="", description="Study Instance UID (used if the accession is unknown).")


class SimulateRouteOut(BaseModel):
    """Where an instance would go and why."""

    accession: str = Field(description="Accession that was checked.")
    study_uid: str = Field(description="Study UID that was checked.")
    matched_via: str = Field(description="accession | study_uid | default | none.")
    source_id: int | None = Field(default=None, description="Worklist source the case came from.")
    source_name: str | None = Field(default=None, description="Name of that source.")
    target_id: int | None = Field(default=None, description="Target the instance would be sent to.")
    target_name: str | None = Field(default=None, description="Name of that target.")
    rule_id: int | None = Field(default=None, description="Rule that matched (null = default target).")
    reason: str = Field(description="Human-readable explanation of the decision.")


class SimulateTransformIn(BaseModel):
    """A case plus tag values to test the modify rules against."""

    accession: str = Field(default="", description="Accession number of the case.")
    study_uid: str = Field(default="", description="Study Instance UID of the case.")
    source_id: int | None = Field(default=None, description="Override the source scope.")
    target_id: int | None = Field(default=None, description="Override the target scope.")
    values: dict[str, str] = Field(
        default_factory=dict,
        description="Tag/value pairs to run the rules against, e.g. {PatientID: 'P1'}.",
        examples=[{"PatientID": "P1", "InstitutionName": "ALT"}],
    )


class TagChangeOut(BaseModel):
    """One tag modification the rules would apply."""

    tag: str = Field(description="DICOM keyword.")
    before: str = Field(description="Value before the rules.")
    after: str = Field(description="Value after the rules.")


class SimulateTransformOut(SimulateRouteOut):
    """Which modify rules would apply and how the tags would change."""

    rules_applied: list[str] = Field(description="Names of the rules that would run.")
    changes: list[TagChangeOut] = Field(description="Tag changes the rules would make.")
    errors: list[str] = Field(description="Operations/tags that would fail (they are skipped).")


class SettingOut(BaseModel):
    """One runtime setting: DB override if present, otherwise the ENV default."""

    key: str = Field(description="Setting key (mirrors the ENV variable name).")
    value: str = Field(description="Currently effective value.")
    default: str = Field(description="Value from the deployment ENV (fallback).")
    source: str = Field(description="'db' = UI override active, 'env' = deployment default.")
    kind: str = Field(description="Value type: bool | int | aets.")
    description: str = Field(description="What the setting does.")


class SettingUpdateIn(BaseModel):
    value: str = Field(
        description="New value (validated per key).",
        examples=["CT_01,MR_01"],
    )


class SpoolStatsOut(BaseModel):
    """Backlog overview of the C-STORE spool (store and forward)."""

    queued: int = Field(description="Instances waiting for the first/next retry.")
    failed: int = Field(description="Instances whose last attempt failed (retry scheduled).")
    dead: int = Field(description="Instances that gave up — they need operator attention.")
    sent: int = Field(description="Delivered instances still kept as a duplicate guard.")
    open: int = Field(description="queued + failed (the actual backlog).")
    bytes: int = Field(description="Bytes held on disk by queued/failed/dead instances.")
    oldest_age_s: int | None = Field(
        default=None, description="Age of the oldest undelivered instance (null = empty).",
    )
    capacity: dict = Field(description="Usage and limits: {items, bytes, max_items, max_bytes, full}.")
    enabled: bool = Field(description="Whether the spool accepts instances at all.")
    accept_when_queued: bool = Field(
        description="Whether the modality is told 'success' once an instance is spooled.",
    )


class SpoolItemOut(BaseModel):
    """One spooled C-STORE instance (metadata only — the payload stays on disk)."""

    id: int = Field(description="Row ID (used for retry/discard).")
    sop_instance_uid: str = Field(description="SOP Instance UID (the duplicate guard).")
    study_uid: str = Field(description="Study Instance UID.")
    accession: str = Field(description="Accession number (allowed by the PHI policy).")
    source_id: int | None = Field(default=None, description="Originating worklist source.")
    target_id: int | None = Field(default=None, description="Target it has to reach.")
    target_name: str = Field(description="Name of that target (for the operator).")
    status: str = Field(description="queued | failed | dead | sent.")
    attempts: int = Field(description="Forwarding attempts so far.")
    last_error: str = Field(description="Reason of the last failure.")
    payload_bytes: int = Field(description="Size of the spooled payload (0 once delivered).")
    age_s: int = Field(description="Age of the entry in seconds.")
    next_attempt_at: datetime | None = Field(
        default=None, description="When the next retry is due (UTC).",
    )
    sent_at: datetime | None = Field(default=None, description="When it was delivered (UTC).")


class SpoolRetryOut(BaseModel):
    """Result of a manual retry."""

    requeued: int = Field(description="Number of instances put back into the queue.")


class CacheSourceOut(BaseModel):
    """Cache state of one upstream source."""

    source_id: int = Field(description="Row ID of the source.")
    source_name: str = Field(description="Display name of the source.")
    entries: int = Field(description="Number of cached worklist items.")
    age_s: int | None = Field(
        default=None, description="Age of the newest cached answer in seconds (null = empty).",
    )
    state: str = Field(
        description="empty | available | expired — 'expired' means an outage could "
                    "no longer be bridged (older than the stale window).",
    )
    stale_on_error: bool = Field(description="Whether this source may be served stale.")
    refresh_s: int = Field(description="Background refresh interval (0 = off).")
    newest_fetched_at: datetime | None = Field(
        default=None, description="Timestamp of the newest cached answer (UTC).",
    )


class CacheItemOut(BaseModel):
    """One cached worklist item — metadata only, deliberately without PHI."""

    source_id: int = Field(description="Row ID of the source the item came from.")
    source_name: str = Field(description="Name of that source.")
    accession: str = Field(description="Accession number (allowed by the PHI policy).")
    study_uid: str = Field(description="Study Instance UID.")
    modality: str = Field(description="Modality of the scheduled step.")
    station_aet: str = Field(description="Scheduled station AE title.")
    sps_status: str = Field(
        description="SPS status (0040,0020) — COMPLETED/DISCONTINUED items are never "
                    "served from the cache.",
    )
    age_s: int = Field(description="Age of the cached item in seconds.")
    fetched_at: datetime = Field(description="When the item was cached (UTC).")


class QueryLogOut(BaseModel):
    """One incoming C-FIND request (audit log, PHI-free)."""

    model_config = ConfigDict(from_attributes=True)
    id: int = Field(description="Row ID.")
    ts: datetime = Field(description="When the query was answered (UTC).")
    calling_aet: str = Field(description="AE title of the requesting modality.")
    query_keys: dict = Field(
        description="Non-PHI subset of the query identifier "
                    "(never contains PatientName/PatientID).",
    )
    answers: int = Field(description="Number of deduplicated answers returned.")
    per_source: dict = Field(
        description="Answer count per source; value is the string 'error' "
                    "when a source could not be reached.",
    )
    duration_ms: int = Field(description="End-to-end duration across all upstreams (ms).")
    status: str = Field(description="success | partial (a source failed, was skipped or served stale) | failed.")
    served_stale: list[str] | None = Field(
        default=None,
        description="Sources that had to be answered from the worklist cache.",
    )


class StoreLogOut(BaseModel):
    """One incoming C-STORE forward attempt."""

    model_config = ConfigDict(from_attributes=True)
    id: int = Field(description="Row ID.")
    ts: datetime = Field(description="When the store was handled (UTC).")
    calling_aet: str = Field(description="AE title of the sending modality.")
    sop_instance_uid: str = Field(description="SOP Instance UID of the received instance.")
    study_uid: str = Field(description="Study Instance UID of the received instance.")
    accession: str = Field(description="Accession number used for routing.")
    source_id: int | None = Field(
        description="Matched worklist source (null = no seen_items match).",
    )
    target_id: int | None = Field(
        description="Chosen routing target (null = unrouted, nothing forwarded).",
    )
    status: str = Field(
        description="success | queued (spooled for retry) | duplicate (already "
                    "spooled or delivered) | failed | unrouted.",
    )
    error: str = Field(default="", description="Forward error detail, if any.")
    applied_transforms: list[str] = Field(
        default_factory=list,
        description="Names of the transform rules applied to this instance.",
    )


class BreakerStateOut(BaseModel):
    """Circuit-breaker state of one upstream source."""

    source_id: int = Field(description="Row ID of the source.")
    name: str = Field(description="Display name of the source.")
    state: str = Field(description="closed | half_open | open.")
    failures: int = Field(description="Consecutive failures since the last success.")
    retry_in_s: int | None = Field(
        default=None, description="Seconds until the next probe (null unless open).",
    )
    last_error: str = Field(default="", description="Last upstream error message.")


class FindingOut(BaseModel):
    """One configuration consistency finding."""

    code: str = Field(
        description="Stable machine-readable code (the UI translates it).",
        examples=["no_default_target"],
    )
    severity: str = Field(description="error | warning | info.")
    message: str = Field(description="English fallback message.")
    entity: dict = Field(
        default_factory=dict,
        description="Affected object for deep-linking: {kind, id, name}.",
    )
    details: dict = Field(
        default_factory=dict, description="Check-specific values (counts, names, …).",
    )


class ReadyOut(BaseModel):
    """Readiness of the broker for orchestration probes."""

    ready: bool = Field(description="True when every required component is up.")
    checks: dict = Field(description="Per-component result, e.g. {db: true, scp: true}.")


class HealthOut(BaseModel):
    """Result of the configuration consistency checks."""

    findings: list[FindingOut] = Field(description="Findings, sorted by severity.")
    summary: dict = Field(description="Counts per severity: error/warning/info.")


class EchoResult(BaseModel):
    """Last C-ECHO result for one source or target."""

    kind: str = Field(description="'source' or 'target'.")
    id: int = Field(description="Row ID of the source/target.")
    name: str = Field(description="Display name of the source/target.")
    ok: bool = Field(description="Whether the last C-ECHO succeeded.")
    rtt_ms: int | None = Field(default=None, description="Round-trip time in ms (null on failure).")
    last_check: datetime | None = Field(default=None, description="Timestamp of the last check (null = never checked).")
    error: str | None = Field(default=None, description="Error detail when ok=false.")
    breaker_state: str | None = Field(
        default=None,
        description="Circuit-breaker state (sources only): closed | half_open | open.",
    )
    breaker_retry_in_s: int | None = Field(
        default=None,
        description="Seconds until the breaker probes the source again (sources only).",
    )


class StatusOut(BaseModel):
    """Aggregated broker status snapshot for dashboards."""

    scp_listening: bool = Field(description="Whether the DICOM SCP is listening.")
    db_ok: bool = Field(description="Whether the config/log database is reachable.")
    sources: list[EchoResult] = Field(description="All sources with their last echo result.")
    targets: list[EchoResult] = Field(description="All targets with their last echo result.")
    counts: dict = Field(
        description="Row counts: queries (C-FIND), stores (C-STORE), seen_items.",
    )
