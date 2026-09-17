"""Pydantic API schemas.

Field descriptions feed the generated OpenAPI documentation — keep them
up to date (Swagger UI at /docs, spec at /openapi.json).
"""
from datetime import datetime

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
    status: str = Field(description="success | partial | failed.")


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
    status: str = Field(description="success | failed | unrouted.")
    error: str = Field(default="", description="Forward error detail, if any.")


class EchoResult(BaseModel):
    """Last C-ECHO result for one source or target."""

    kind: str = Field(description="'source' or 'target'.")
    id: int = Field(description="Row ID of the source/target.")
    name: str = Field(description="Display name of the source/target.")
    ok: bool = Field(description="Whether the last C-ECHO succeeded.")
    rtt_ms: int | None = Field(default=None, description="Round-trip time in ms (null on failure).")
    last_check: datetime | None = Field(default=None, description="Timestamp of the last check (null = never checked).")
    error: str | None = Field(default=None, description="Error detail when ok=false.")


class StatusOut(BaseModel):
    """Aggregated broker status snapshot for dashboards."""

    scp_listening: bool = Field(description="Whether the DICOM SCP is listening.")
    db_ok: bool = Field(description="Whether the config/log database is reachable.")
    sources: list[EchoResult] = Field(description="All sources with their last echo result.")
    targets: list[EchoResult] = Field(description="All targets with their last echo result.")
    counts: dict = Field(
        description="Row counts: queries (C-FIND), stores (C-STORE), seen_items.",
    )
