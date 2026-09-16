"""Pydantic API schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    aet: str = Field(min_length=1, max_length=16)
    host: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)
    calling_aet: str = "MWLBROKER"
    charset: str = "ISO_IR 100"
    enabled: bool = True
    timeout_s: int = Field(default=10, ge=1, le=120)
    priority: int = 100


class SourceOut(SourceIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class TargetIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    aet: str = Field(min_length=1, max_length=16)
    host: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)
    calling_aet: str = "MWLBROKER"
    enabled: bool = True
    is_default: bool = False


class TargetOut(TargetIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class RuleIn(BaseModel):
    source_id: int
    target_id: int
    priority: int = 100
    enabled: bool = True


class RuleOut(RuleIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class QueryLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ts: datetime
    calling_aet: str
    query_keys: dict
    answers: int
    per_source: dict
    duration_ms: int
    status: str


class StoreLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ts: datetime
    calling_aet: str
    sop_instance_uid: str
    study_uid: str
    accession: str
    source_id: int | None
    target_id: int | None
    status: str
    error: str


class EchoResult(BaseModel):
    kind: str  # source | target
    id: int
    name: str
    ok: bool
    rtt_ms: int | None = None
    last_check: datetime | None = None
    error: str | None = None


class StatusOut(BaseModel):
    scp_listening: bool
    db_ok: bool
    sources: list[EchoResult]
    targets: list[EchoResult]
    counts: dict
