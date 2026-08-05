from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator


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
