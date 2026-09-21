"""Pydantic API schemas.

Field descriptions feed the generated OpenAPI documentation — keep them
up to date (Swagger UI at /docs, spec at /openapi.json).
"""
import re

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Hostname, IP address or docker service name — no scheme, no spaces, no path.
_HOST_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?$")
# DICOM AE titles are upper case, 1-16 characters of A-Z 0-9 _ -
_AET_RE = re.compile(r"^[A-Z0-9_-]{1,16}$")


def validate_node_fields(host: str, aet: str, calling_aet: str | None = None) -> list[str]:
    """Checks for a DICOM node — applied to *input* only.

    The same rules must not run on responses: an old row that predates the rule
    would break the list endpoint. The API layer calls this for create/update.
    """
    errors: list[str] = []
    host = (host or "").strip()
    if "://" in host:
        errors.append("enter the host only, without http:// or https://")
    elif "/" in host or " " in host:
        errors.append("the host must not contain spaces or slashes")
    elif not _HOST_RE.match(host):
        errors.append("not a valid host name or IP address")
    if not _AET_RE.match((aet or "").strip()):
        errors.append("an AE title has 1-16 characters: A-Z, 0-9, _ or - (upper case)")
    if calling_aet and not _AET_RE.match(calling_aet.strip()):
        errors.append("the calling AE title has 1-16 characters: A-Z, 0-9, _ or -")
    return errors


# Hostname, IP address or docker service name — no scheme, no spaces, no path.
# DICOM AE titles are upper case, 1-16 characters of A-Z 0-9 _ -
_AET_RE = re.compile(r"^[A-Z0-9_-]{1,16}$")


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
    tls: bool = Field(
        default=False,
        description="Use DICOM TLS towards this source (off = the plain LAN/VPN default).",
    )
    tls_verify: bool = Field(
        default=True,
        description="Verify the server certificate. Only switch off for a "
                    "self-signed lab system — the connection is then encrypted "
                    "but the peer is not authenticated.",
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
    tls: bool = Field(
        default=False,
        description="Use DICOM TLS towards this PACS (off = the plain LAN/VPN default).",
    )
    tls_verify: bool = Field(
        default=True,
        description="Verify the PACS certificate. Only switch off for a "
                    "self-signed lab system.",
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


class WorklistPreviewIn(BaseModel):
    """The C-FIND query to run: station plus any of the usual filter fields."""

    station_aet: str = Field(default="", description="Station that would query (drives the station rules).",
                             examples=["CT_01"])
    accession: str = Field(default="", description="Only this accession (empty = all scheduled steps).")
    study_uid: str = Field(default="", description="Only this study.")
    modality: str = Field(default="", description="Only this modality, e.g. CT.")
    scheduled_date: str = Field(default="", description="Only steps on this date (YYYYMMDD or a range 20260901-20260930).")
    patient_id: str = Field(default="", description="Only this patient ID (matching key, not shown in the result).")


class SourceQueryIn(BaseModel):
    """What to ask a single source (all fields optional — empty means everything)."""

    accession: str = Field(default="", description="Only this accession.")
    modality: str = Field(default="", description="Only this modality.")
    scheduled_date: str = Field(default="", description="Only steps on this date (YYYYMMDD).")
    patient_id: str = Field(default="", description="Only this patient ID.")


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
    kind: str = Field(
        description="Value type: bool | int | aets | url | path | events | enum:<choices>.",
    )
    description: str = Field(description="What the setting does.")
    min: int | None = Field(default=None, description="Lower bound for integer settings.")
    max: int | None = Field(default=None, description="Upper bound for integer settings.")
    choices: list[str] = Field(
        default_factory=list, description="Allowed values for enum settings.",
    )


class SettingUpdateIn(BaseModel):
    value: str = Field(
        description="New value (validated per key).",
        examples=["CT_01,MR_01"],
    )


class RbacStatusOut(BaseModel):
    """Access mode for the caller (read vs. write)."""

    mode: str = Field(description="off | enforce.")
    enforced: bool = Field(description="Whether writes are restricted.")
    roles_header: str = Field(description="Header the proxy passes the roles in.")
    write_role: str = Field(description="Role that allows configuration changes.")
    roles: list[str] = Field(description="Roles the caller presented.")
    can_write: bool = Field(description="Whether this caller may change the configuration.")


class RetentionTableOut(BaseModel):
    """Retention state of one table."""

    table: str = Field(description="Table name.")
    description: str = Field(description="What the rows are.")
    rows: int = Field(description="Current row count.")
    oldest: datetime | None = Field(default=None, description="Oldest row (UTC).")
    retention_days: int = Field(description="Configured retention (0 = keep forever).")
    will_delete: int = Field(description="Rows a cleanup would remove right now.")


class RetentionOut(BaseModel):
    """Retention overview for the UI."""

    tables: list[RetentionTableOut] = Field(description="One entry per table.")


class RetentionPurgeOut(BaseModel):
    """Result of a manual cleanup."""

    removed: dict = Field(description="Removed rows per table.")
    total: int = Field(description="Total removed rows.")


class TlsCertificateOut(BaseModel):
    """State of one configured certificate file (never key material)."""

    path: str = Field(description="Configured file path.")
    exists: bool = Field(description="Whether the file is there.")
    ok: bool = Field(description="Whether it could be read as a certificate.")
    error: str = Field(default="", description="Why it could not be used.")
    subject: str = Field(default="", description="Subject (CN, O, OU, C).")
    issuer: str = Field(default="", description="Issuer — equals the subject for self-signed.")
    self_signed: bool = Field(default=False, description="Subject == issuer.")
    serial: str = Field(default="", description="Serial number (hex).")
    not_before: str = Field(default="", description="Valid from (ISO 8601, UTC).")
    not_after: str = Field(default="", description="Valid until (ISO 8601, UTC).")
    days_left: int | None = Field(default=None, description="Days until expiry (negative = expired).")
    expired: bool = Field(default=False, description="Already expired.")
    expiring_soon: bool = Field(default=False, description="Expires within 30 days.")
    san: list[str] = Field(default_factory=list, description="Subject alternative names.")
    is_ca: bool = Field(default=False, description="Whether it is a CA certificate.")
    signature_algorithm: str = Field(default="", description="Signature algorithm.")


class TlsKeyOut(BaseModel):
    """State of one private key file — never the key itself."""

    path: str = Field(description="Configured file path.")
    exists: bool = Field(description="Whether the file is there.")
    ok: bool = Field(description="Whether it could be read as an unencrypted key.")
    error: str = Field(default="", description="Why it could not be used.")
    mode: str = Field(default="", description="File permissions (octal).")
    world_readable: bool = Field(default=False, description="Readable by other users — should not be.")
    type: str = Field(default="", description="Key type, e.g. RSAPrivateKey.")
    bits: int | None = Field(default=None, description="Key size.")


class TlsOverviewOut(BaseModel):
    """Certificate management overview."""

    inbound_enabled: bool = Field(description="Whether the TLS listener is switched on.")
    inbound_port: int = Field(description="Port of the TLS listener.")
    inbound_client_auth: str = Field(description="none | optional | required (mTLS).")
    outbound_verify: bool = Field(description="Whether outgoing certificates are verified.")
    directory: str = Field(description="Directory for self-generated certificates.")
    entries: dict = Field(description="State of every configured file (certificates and keys).")
    certificates: list[dict] = Field(description="Short list of the usable certificates.")


class TlsSelfSignedIn(BaseModel):
    """Request to generate a self-signed certificate."""

    common_name: str = Field(min_length=1, max_length=128,
                             description="Name the modality will see (e.g. the broker host).",
                             examples=["mwl-broker.hospital.local"])
    days: int = Field(default=3650, ge=1, le=36500, description="Validity in days.")
    san: list[str] = Field(default_factory=list,
                           description="Additional names/IPs the certificate is valid for.")
    is_ca: bool = Field(default=False,
                        description="Also usable as a trust anchor for several devices.")
    filename: str = Field(default="mwl-broker", max_length=64,
                          description="Base name of the generated files.")


class TlsSelfSignedOut(BaseModel):
    """The generated certificate — the public part only."""

    certificate_path: str = Field(description="Path of the generated certificate.")
    key_path: str = Field(description="Path of the generated private key (mode 0600).")
    certificate_pem: str = Field(description="The public certificate — hand this to the vendor.")
    certificate: TlsCertificateOut = Field(description="What was generated.")
    key: TlsKeyOut = Field(description="State of the private key file.")
    is_ca: bool = Field(description="Whether it was generated as a CA.")


class TlsTestIn(BaseModel):
    """Check an endpoint: handshake, certificate, optional C-ECHO."""

    host: str = Field(min_length=1, description="Host to check.")
    port: int = Field(ge=1, le=65535, description="Port to check.")
    verify: bool | None = Field(
        default=None, description="Override verification for this check (null = the configured default).",
    )
    ca_file: str = Field(default="", description="CA bundle for this check (empty = configured/system).")
    server_name: str = Field(default="", description="Name to verify against (empty = the host).")
    echo_aet: str = Field(default="", description="If set, also run a C-ECHO against this AE title.")
    calling_aet: str = Field(default="", description="Calling AE title for the C-ECHO.")
    timeout_s: int = Field(default=10, ge=1, le=120, description="Timeout in seconds.")


class TlsTestOut(BaseModel):
    """Result of an endpoint check."""

    host: str = Field(description="Checked host.")
    port: int = Field(description="Checked port.")
    ok: bool = Field(description="Whether the handshake succeeded.")
    error: str = Field(default="", description="What went wrong (in plain words).")
    protocol: str = Field(default="", description="Negotiated TLS version.")
    cipher: str = Field(default="", description="Negotiated cipher.")
    peer_subject: str = Field(default="", description="Common name of the peer certificate.")
    peer_issuer: str = Field(default="", description="Issuer of the peer certificate.")
    peer_not_after: str = Field(default="", description="Peer certificate expiry.")
    peer_san: list[str] = Field(default_factory=list, description="Peer subject alternative names.")
    echo_ok: bool | None = Field(default=None, description="Result of the C-ECHO, if requested.")
    echo_error: str = Field(default="", description="C-ECHO error, if any.")


class LocalItemIn(BaseModel):
    """A locally maintained worklist item (emergency / unscheduled exam)."""

    accession: str = Field(min_length=1, max_length=64, description="Accession number.",
                           examples=["EMERG-001"])
    sps_id: str = Field(default="1", max_length=64,
                        description="Scheduled Procedure Step ID (unique per accession).")
    patient_id: str = Field(default="", max_length=64, description="Patient ID (0010,0020).")
    patient_name: str = Field(default="", max_length=128,
                              description="Patient name in DICOM form: 'Last^First'.")
    birth_date: str = Field(default="", max_length=16, description="Birth date (YYYY-MM-DD).")
    sex: str = Field(default="", max_length=4, description="Sex (M/F/O).")
    modality: str = Field(default="", max_length=16, description="Modality, e.g. CT.")
    station_aet: str = Field(default="", max_length=16,
                             description="Scheduled station AE title (empty = any station).")
    procedure_description: str = Field(default="", max_length=128,
                                       description="What has to be done (shown to the operator).")
    scheduled_date: str = Field(default="", max_length=16, description="Scheduled date (YYYY-MM-DD).")
    scheduled_time: str = Field(default="", max_length=16, description="Scheduled time (HH:MM).")
    study_uid: str = Field(default="", max_length=128, description="Study Instance UID, if known.")
    sps_status: str = Field(default="SCHEDULED", max_length=16,
                            description="SPS status (0040,0020) sent to the modality.")
    valid_until: datetime | None = Field(
        default=None, description="Expiry — after this the item is purged (null = never).",
    )
    enabled: bool = Field(default=True, description="Disabled items are not returned.")


class LocalItemOut(LocalItemIn):
    model_config = ConfigDict(from_attributes=True)
    id: int = Field(description="Row ID.")
    origin: str = Field(description="manual | hl7 — how the item was created.")
    created_at: datetime = Field(description="Creation timestamp (UTC).")
    updated_at: datetime = Field(description="Last modification (UTC).")


class Hl7MessageOut(BaseModel):
    """One inbound HL7 message (troubleshooting log)."""

    id: int = Field(description="Row ID.")
    ts: datetime = Field(description="When it arrived (UTC).")
    transport: str = Field(description="http | mllp.")
    message_type: str = Field(description="MSH-9, e.g. ORM^O01.")
    control_id: str = Field(description="MSH-10.")
    order_control: str = Field(description="ORC-1, e.g. NW / CA.")
    accession: str = Field(description="Accession number found in the message.")
    action: str = Field(description="created | updated | cancelled | rejected | error.")
    error: str = Field(default="", description="Reason when the message was not applied.")


class Hl7ParseOut(BaseModel):
    """Result of an ORM message (dry-run shows what would happen)."""

    dry_run: bool = Field(description="True when nothing was written.")
    message_type: str = Field(description="MSH-9.")
    control_id: str = Field(description="MSH-10 (used for the ACK).")
    order_control: str = Field(description="ORC-1 — NW creates, CA cancels.")
    accession: str = Field(description="Accession number parsed from the message.")
    action: str = Field(description="planned/applied action, e.g. created | cancelled.")
    item: LocalItemOut | None = Field(default=None, description="The affected local item.")
    parsed: dict = Field(description="All fields the parser mapped.")
    warnings: list[str] = Field(description="What could not be mapped (the UI shows it).")


class AtnaStatsOut(BaseModel):
    """State of the ATNA audit trail."""

    enabled: bool = Field(description="Whether auditing is switched on.")
    configured: bool = Field(description="True when enabled *and* a repository host is set.")
    host: str = Field(description="Audit repository host.")
    port: int = Field(description="Audit repository port.")
    protocol: str = Field(description="tcp | tls.")
    queue_size: int = Field(description="Buffered messages waiting for delivery.")
    queue_max: int = Field(description="Buffer limit before the oldest are dropped.")
    worker_running: bool = Field(description="Whether the drain worker is alive.")


class AtnaTestOut(BaseModel):
    """Result of a test audit message."""

    ok: bool = Field(description="True when the repository accepted the message.")
    error: str = Field(default="", description="Delivery error, if any.")


class AtnaSampleOut(BaseModel):
    """An example audit message — for the receiving team."""

    xml: str = Field(description="A complete PS3.15 audit message (Query event).")


class StationRuleIn(BaseModel):
    """Per-station worklist rule (filter + priority override)."""

    name: str = Field(min_length=1, max_length=64, description="Unique rule name.")
    station_aet: str = Field(
        default="*", max_length=16, pattern=r"^(\*|[A-Za-z0-9_-]{1,16})$",
        description="ScheduledStationAETitle this rule applies to ('*' = fallback).",
        examples=["CT_01"],
    )
    mode: Literal["allow", "deny"] = Field(
        default="deny", description="deny: hide the listed sources; allow: show only them.",
    )
    source_ids: list[int] = Field(
        default_factory=list, description="Source IDs the rule applies to.",
    )
    source_priority: dict = Field(
        default_factory=dict,
        description="Priority override for this station: {source_id: priority}.",
    )
    priority: int = Field(default=100, description="Rule order — lower wins.")
    enabled: bool = Field(default=True, description="Disabled rules are ignored.")


class StationRuleOut(StationRuleIn):
    model_config = ConfigDict(from_attributes=True)
    id: int = Field(description="Row ID.")
    created_at: datetime = Field(description="Creation timestamp (UTC).")


class StationSimulateIn(BaseModel):
    """A station to check against the per-station rules."""

    station_aet: str = Field(
        default="", max_length=16,
        description="ScheduledStationAETitle of the console (empty = no station filter).",
        examples=["CT_01"],
    )


class StationPreviewSourceOut(BaseModel):
    """One source as the station would see it."""

    id: int = Field(description="Source row ID.")
    name: str = Field(description="Source name.")
    visible: bool = Field(description="Whether this source's answers reach the station.")
    effective_priority: int = Field(description="Priority used for the merge (override applied).")


class StationPreviewOut(BaseModel):
    """What a station would see — a dry-run of the station rules."""

    station_aet: str = Field(description="Station that was checked.")
    rule_id: int | None = Field(default=None, description="Matching rule (null = none).")
    rule_name: str | None = Field(default=None, description="Name of that rule.")
    mode: str | None = Field(default=None, description="allow | deny.")
    sources: list[StationPreviewSourceOut] = Field(description="Sources with visibility and order.")
    reason: str = Field(description="Human-readable explanation.")


class NotifyEventOut(BaseModel):
    """One alerting event the broker can send."""

    code: str = Field(description="Event code used in `notify_events`.", examples=["source_down"])
    severity: str = Field(description="error | warning | info.")
    description: str = Field(description="What the event means (English, for the UI).")


class NotifyTestOut(BaseModel):
    """Result of a test alert."""

    ok: bool = Field(description="True when the webhook accepted the message.")
    error: str = Field(default="", description="Delivery error, if any.")


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

    version: str = Field(description="Broker version that is running (which build).")
    started_at: str = Field(description="ISO timestamp the process started.")
    uptime_s: int = Field(description="Seconds since the process started.")
    scp_listening: bool = Field(description="Whether the DICOM SCP is listening.")
    db_ok: bool = Field(description="Whether the config/log database is reachable.")
    sources: list[EchoResult] = Field(description="All sources with their last echo result.")
    targets: list[EchoResult] = Field(description="All targets with their last echo result.")
    counts: dict = Field(
        description="Row counts: queries (C-FIND), stores (C-STORE), seen_items.",
    )


class WorklistPreviewItem(BaseModel):
    """One merged worklist item as the preview shows it (PHI-free by default)."""

    accession: str = Field(default="", description="Accession number (the routing key).")
    study_uid: str = Field(default="", description="StudyInstanceUID, when the source sends one.")
    requested_procedure_id: str = Field(default="", description="Requested procedure ID.")
    sps_id: str = Field(default="", description="Scheduled procedure step ID.")
    station_aet: str = Field(default="", description="Station the step is scheduled for.")
    modality: str = Field(default="", description="Modality of the scheduled step.")
    start_date: str = Field(default="", description="Scheduled start date (DICOM DA).")
    start_time: str = Field(default="", description="Scheduled start time (DICOM TM).")
    source: str = Field(description="Source that won the merge for this item.")
    also_in: list[str] = Field(default_factory=list,
                               description="Other sources that answered the same case (deduplicated).")
    patient_name: str | None = Field(default=None, description="Only with `simulate_show_phi` on (PHI).")
    patient_id: str | None = Field(default=None, description="Only with `simulate_show_phi` on (PHI).")


class WorklistPreviewSource(BaseModel):
    """What one upstream contributed to the preview."""

    name: str = Field(description="Source name.")
    source_id: int | None = Field(default=None, description="Source ID (null for the local items).")
    answers: int | str = Field(description="Number of answers, or 'error' / 'skipped' (breaker open).")
    stale: bool = Field(default=False, description="True when a cached snapshot was served instead.")
    breaker_state: str | None = Field(default=None, description="Circuit-breaker state when skipped.")


class WorklistPreviewOut(BaseModel):
    """Result of running the real C-FIND aggregation without a modality."""

    station: str = Field(description="Station AET taken from the query (empty = any).")
    rule: str | None = Field(default=None, description="Station rule that applied, if any.")
    status: str = Field(description="success | partial | failed — same wording as the query log.")
    duration_ms: int = Field(description="Wall-clock time of the whole fan-out.")
    answers: int = Field(description="Number of merged items a modality would receive.")
    hidden: int = Field(description="Items hidden by the station rule's visibility filter.")
    phi: bool = Field(description="Whether patient name/ID are included (setting `simulate_show_phi`).")
    served_stale: list[str] = Field(default_factory=list,
                                    description="Sources answered from the cache (they were down).")
    sources: list[WorklistPreviewSource] = Field(description="Per-source contribution and timing.")
    items: list[WorklistPreviewItem] = Field(description="The merged items (capped, see `truncated`).")
    truncated: bool = Field(description="True when more items exist than were returned.")


class SourceQueryOut(BaseModel):
    """Result of a direct C-FIND against one source (the sources page's test)."""

    source_id: int = Field(description="Source that was asked.")
    name: str = Field(description="Source name.")
    ok: bool = Field(description="Whether the query succeeded.")
    error: str = Field(default="", description="Plain-language failure reason (empty on success).")
    answers: int = Field(description="Number of answers the source returned.")
    duration_ms: int = Field(description="Round-trip time of the query.")
    phi: bool = Field(description="Whether patient name/ID are included (setting `simulate_show_phi`).")
    items: list[WorklistPreviewItem] = Field(description="The answers (capped, see `truncated`).")
    truncated: bool = Field(description="True when more answers exist than were returned.")


class Hl7MessageDetailOut(BaseModel):
    """One inbound HL7 message as the log sees it."""

    id: int = Field(description="Log entry ID.")
    ts: datetime = Field(description="When the message arrived.")
    transport: str = Field(description="http | mllp | replay:<transport>.")
    message_type: str = Field(description="HL7 message type, e.g. ORM^O01.")
    control_id: str = Field(description="MSH-10 message control ID.")
    order_control: str = Field(description="ORC-1 order control (NW, CA, …).")
    accession: str = Field(description="Accession number the message carried.")
    action: str = Field(description="created-or-updated | cancelled | rejected | cancel-unknown | error.")
    error: str = Field(description="Why the message was rejected (empty when it worked).")
    raw: str = Field(description="The raw message — only when `hl7_store_raw` is on (PHI!).")
    replayable: bool = Field(description="Whether the raw message is stored, so a replay is possible.")


class Hl7ReprocessOut(BaseModel):
    """Result of replaying a stored HL7 message."""

    dry_run: bool = Field(description="True when nothing was written.")
    action: str = Field(description="What the replay did (or would do).")
    item_id: int | None = Field(default=None, description="Local worklist item that was touched.")
    error: str = Field(default="", description="Why the replay failed, if it did.")


class CacheRefreshSource(BaseModel):
    """One source's contribution to a manual cache refresh."""

    name: str = Field(description="Source name.")
    source_id: int = Field(description="Source ID.")
    items: int = Field(description="Items that were cached (0 when the query failed).")
    duration_ms: int = Field(description="Query duration.")
    ok: bool = Field(description="Whether the source answered.")
    error: str = Field(default="", description="Failure reason, if any.")


class CacheRefreshOut(BaseModel):
    """Result of a manual cache refresh."""

    sources: list[CacheRefreshSource] = Field(description="Per-source result of the refresh.")


class TlsUploadIn(BaseModel):
    """A certificate/key pair that came from the hospital PKI."""

    certificate_pem: str = Field(description="The certificate in PEM form (the server certificate).",
                                 examples=["-----BEGIN CERTIFICATE-----\n…"])
    key_pem: str = Field(description="The matching private key in PEM form (unencrypted). "
                                     "It is never returned again.")
    ca_pem: str = Field(default="", description="Optional CA bundle (PEM) to verify the other side.")
    filename: str = Field(default="uploaded", description="Base name of the stored files (no path).")
    is_ca: bool = Field(default=False, description="Set when the certificate itself is a CA certificate.")


class TlsUploadOut(BaseModel):
    """Where the uploaded material was stored (never the key itself)."""

    certificate_path: str = Field(description="Where the certificate was stored.")
    key_path: str = Field(description="Where the private key was stored (mode 0600).")
    ca_path: str = Field(default="", description="Where the CA bundle was stored (empty when none).")
    certificate: dict = Field(description="Subject, validity and SANs of the certificate.")
    key: dict = Field(description="Type and size of the key (no key material).")
    is_ca: bool = Field(description="Whether the certificate was marked as a CA certificate.")


class MppsStepOut(BaseModel):
    """A performed procedure step reported by a modality."""

    id: int = Field(description="Row ID.")
    ts: datetime = Field(description="When the broker received the message.")
    sop_instance_uid: str = Field(description="MPPS SOP instance UID (the step's identity).")
    status: str = Field(description="IN PROGRESS | COMPLETED | DISCONTINUED.")
    accession: str = Field(description="Accession number — the key the RIS needs.")
    patient_id: str = Field(description="Patient ID (no name: PHI stays out of the logs).")
    sps_id: str = Field(description="Scheduled procedure step ID.")
    station_aet: str = Field(description="Station that performed the step.")
    modality: str = Field(description="Modality.")
    study_uid: str = Field(description="Study instance UID, when reported.")
    performed_procedure_step_id: str = Field(description="Performed procedure step ID.")
    started_at: datetime | None = Field(default=None, description="Start as reported by the modality.")
    ended_at: datetime | None = Field(default=None, description="End as reported by the modality.")
    forwarded: bool = Field(description="Whether the state reached the RIS.")
    forward_error: str = Field(default="", description="Why the last delivery failed (empty = ok).")
    forward_attempts: int = Field(description="Delivery attempts so far.")
    forwarded_at: datetime | None = Field(default=None, description="When it was delivered.")


class MppsStatsOut(BaseModel):
    """How many steps arrived, how many went back to the RIS."""

    total: int = Field(description="Steps stored.")
    by_status: dict = Field(description="Counts per MPPS status.")
    forwarded: int = Field(description="Steps whose state reached the RIS.")
    pending_forward: int = Field(description="Finished steps that were not delivered yet.")
    last_error: str = Field(default="", description="The most recent delivery error.")
    forward_enabled: bool = Field(description="Whether forwarding is switched on.")
    hide_completed: bool = Field(description="Whether finished steps are hidden from the worklist.")


class MppsForwardOut(BaseModel):
    """Result of a manual delivery attempt (single step or batch)."""

    ok: bool = Field(default=False,
                     description="Whether the RIS accepted the message (single step).")
    error: str = Field(default="", description="Reason for a failure.")
    attempted: int = Field(default=0, description="Steps tried (batch only).")
    sent: int = Field(default=0, description="Steps delivered (batch only).")
    failed: int = Field(default=0, description="Steps that failed (batch only).")
