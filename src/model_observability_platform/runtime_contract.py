from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from . import __version__

MODEL_NAME = "credit-risk-router"
SERVER_VERSION = __version__
IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$"
MODEL_VERSION_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{1,63}$"


class TelemetryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    window: str = Field(min_length=1, max_length=32)
    request_id: str = Field(pattern=IDENTIFIER_PATTERN)
    model_version: str = Field(pattern=MODEL_VERSION_PATTERN)
    status: Literal["success", "error"]
    latency_ms: float = Field(ge=0, le=60_000)
    prediction: Literal[0, 1] | None
    risk_score: float | None = Field(ge=0, le=1)
    age: int | None = Field(ge=18, le=120)
    income: float | None = Field(ge=0, le=100_000_000)
    debt_ratio: float | None = Field(ge=0, le=10)
    utilization: float | None = Field(ge=0, le=10)
    delinquencies: int | None = Field(ge=0, le=10_000)

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone offset")
        return value


class EvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluation_id: str = Field(pattern=IDENTIFIER_PATTERN)
    model_name: Literal[MODEL_NAME] = MODEL_NAME
    model_version: str = Field(pattern=MODEL_VERSION_PATTERN)
    policy_version: str = Field(default="1", pattern=MODEL_VERSION_PATTERN)
    reference_window: list[TelemetryRecord] = Field(min_length=20, max_length=2_000)
    current_window: list[TelemetryRecord] = Field(min_length=20, max_length=2_000)

    @model_validator(mode="after")
    def validate_window_versions(self) -> EvaluationRequest:
        records = [*self.reference_window, *self.current_window]
        versions = {record.model_version for record in records}
        if versions != {self.model_version}:
            raise ValueError("every telemetry record must match the requested model_version")
        return self


class TransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transition_id: str = Field(pattern=IDENTIFIER_PATTERN)
    expected_version: int = Field(ge=1)
    actor: str = Field(pattern=IDENTIFIER_PATTERN)
    note: str | None = Field(default=None, max_length=500)
