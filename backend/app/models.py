from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


TimeScope = Literal["day", "month", "year"]


class InitializeRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    birth_date: date
    target_age: int = Field(default=100, ge=1, le=150)
    timezone: str = Field(default="UTC", min_length=1, max_length=100)
    pin: str
    recovery_secret: str | None = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        cleaned = (value or "UTC").strip()
        if cleaned in {"timezone.utc", "dt_timezone.utc"}:
            return "UTC"
        return cleaned or "UTC"

    @field_validator("pin")
    @classmethod
    def validate_pin(cls, value: str) -> str:
        if not value.isdigit() or not 6 <= len(value) <= 12:
            raise ValueError("PIN 必须为 6—12 位数字")
        return value


class UnlockRequest(BaseModel):
    method: Literal["pin", "recovery"] = "pin"
    secret: str = Field(min_length=1, max_length=256)


class ScopedContentRequest(BaseModel):
    time_scope: TimeScope = "day"
    period_key: str | None = Field(default=None, max_length=10)
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(default="", max_length=20_000)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("标题不能为空")
        return cleaned

    @field_validator("content")
    @classmethod
    def clean_content(cls, value: str) -> str:
        return value.strip()

    @field_validator("period_key")
    @classmethod
    def clean_period_key(cls, value: str | None) -> str | None:
        return value.strip() if value else None

    def validate_scope_key(self, legacy_date: date | None) -> "ScopedContentRequest":
        if self.period_key is None:
            if legacy_date is None:
                raise ValueError("必须提供时间范围")
            self.time_scope = "day"
            self.period_key = legacy_date.isoformat()

        patterns = {
            "year": r"^\d{4}$",
            "month": r"^\d{4}-(0[1-9]|1[0-2])$",
            "day": r"^\d{4}-(0[1-9]|1[0-2])-([0-2]\d|3[01])$",
        }
        if not re.fullmatch(patterns[self.time_scope], self.period_key or ""):
            raise ValueError("时间范围格式与层级不匹配")
        if self.time_scope == "day":
            try:
                date.fromisoformat(self.period_key)
            except ValueError as exc:
                raise ValueError("日期格式无效") from exc
        return self


class EventCreateRequest(ScopedContentRequest):
    event_date: date | None = None

    @model_validator(mode="after")
    def validate_target(self) -> "EventCreateRequest":
        self.validate_scope_key(self.event_date)
        return self


class MemoryCreateRequest(ScopedContentRequest):
    memory_date: date | None = None

    @model_validator(mode="after")
    def validate_target(self) -> "MemoryCreateRequest":
        self.validate_scope_key(self.memory_date)
        return self


class PlanCreateRequest(ScopedContentRequest):
    plan_date: date | None = None

    @model_validator(mode="after")
    def validate_target(self) -> "PlanCreateRequest":
        self.validate_scope_key(self.plan_date)
        return self
