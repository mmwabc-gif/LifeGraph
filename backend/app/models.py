from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .html_sanitizer import sanitize_rich_html


TimeScope = Literal["day", "month", "year"]
ContentFormat = Literal["plain", "html"]


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




class ProfileImpactRequest(BaseModel):
    birth_date: date


class ProfileUpdateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    birth_date: date
    current_pin: str
    revision: int = Field(ge=1)

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("姓名不能为空")
        return cleaned

    @field_validator("current_pin")
    @classmethod
    def validate_current_pin(cls, value: str) -> str:
        if not value.isdigit() or not 6 <= len(value) <= 12:
            raise ValueError("当前 PIN 必须为 6—12 位数字")
        return value


class PinChangeRequest(BaseModel):
    current_pin: str
    new_pin: str
    confirm_new_pin: str

    @model_validator(mode="after")
    def validate_pins(self) -> "PinChangeRequest":
        for label, value in (("当前 PIN", self.current_pin), ("新 PIN", self.new_pin)):
            if not value.isdigit() or not 6 <= len(value) <= 12:
                raise ValueError(f"{label} 必须为 6—12 位数字")
        if self.new_pin != self.confirm_new_pin:
            raise ValueError("两次输入的新 PIN 不一致")
        if self.new_pin == self.current_pin:
            raise ValueError("新 PIN 不能与当前 PIN 相同")
        return self


class PinResetRequest(BaseModel):
    recovery_secret: str = Field(min_length=12, max_length=256)
    new_pin: str
    confirm_new_pin: str

    @model_validator(mode="after")
    def validate_pins(self) -> "PinResetRequest":
        if not self.new_pin.isdigit() or not 6 <= len(self.new_pin) <= 12:
            raise ValueError("新 PIN 必须为 6—12 位数字")
        if self.new_pin != self.confirm_new_pin:
            raise ValueError("两次输入的新 PIN 不一致")
        return self


class RecoveryCredentialChangeRequest(BaseModel):
    current_pin: str
    generate: bool = True
    new_recovery_secret: str | None = Field(default=None, max_length=256)
    confirm_new_recovery_secret: str | None = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def validate_credentials(self) -> "RecoveryCredentialChangeRequest":
        if not self.current_pin.isdigit() or not 6 <= len(self.current_pin) <= 12:
            raise ValueError("当前 PIN 必须为 6—12 位数字")
        if self.generate:
            return self
        secret = (self.new_recovery_secret or "").strip()
        confirmation = (self.confirm_new_recovery_secret or "").strip()
        if len(secret) < 12:
            raise ValueError("新恢复凭据至少需要 12 个字符")
        if secret != confirmation:
            raise ValueError("两次输入的新恢复凭据不一致")
        self.new_recovery_secret = secret
        self.confirm_new_recovery_secret = confirmation
        return self


class AutoBackupPolicyUpdateRequest(BaseModel):
    enabled: bool = False
    frequency: Literal["daily", "weekly"] = "daily"
    retention_count: int = Field(default=10, ge=3, le=50)
    create_initial_backup: bool = True


class AutoBackupHistoryClearRequest(BaseModel):
    confirm: Literal["CLEAR_AUTO_BACKUPS"]


class ScopedContentRequest(BaseModel):
    time_scope: TimeScope = "day"
    period_key: str | None = Field(default=None, max_length=10)
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(default="", max_length=20_000)
    content_format: ContentFormat = "plain"

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("标题不能为空")
        return cleaned

    @model_validator(mode="after")
    def clean_body_content(self) -> "ScopedContentRequest":
        self.content = sanitize_rich_html(self.content) if self.content_format == "html" else self.content.strip()
        return self

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


class ContentUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(default="", max_length=20_000)
    content_format: ContentFormat = "plain"
    revision: int = Field(ge=1)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("标题不能为空")
        return cleaned

    @model_validator(mode="after")
    def clean_body_content(self) -> "ContentUpdateRequest":
        self.content = sanitize_rich_html(self.content) if self.content_format == "html" else self.content.strip()
        return self


class ContentDeleteRequest(BaseModel):
    revision: int = Field(ge=1)


class TrashClearRequest(BaseModel):
    confirm: Literal["EMPTY_TRASH"]


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


class TagCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    color: str | None = Field(default=None, max_length=20)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("标签名称不能为空")
        return value


class TagUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    color: str | None = Field(default=None, max_length=20)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("标签名称不能为空")
        return value


class ContentTagSelectionRequest(BaseModel):
    tag_ids: list[str] = Field(default_factory=list)

    @field_validator("tag_ids")
    @classmethod
    def clean_tag_ids(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in value:
            tag_id = str(raw or "").strip()
            if not tag_id or tag_id in seen:
                continue
            seen.add(tag_id)
            cleaned.append(tag_id)
        if len(cleaned) > 100:
            raise ValueError("一次最多设置 100 个标签")
        return cleaned


class ContentBulkTagTarget(BaseModel):
    kind: Literal["event", "memory", "plan"]
    content_id: str = Field(min_length=1, max_length=120)

    @field_validator("content_id")
    @classmethod
    def clean_content_id(cls, value: str) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            raise ValueError("内容 ID 不能为空")
        return cleaned


class ContentBulkTagRequest(BaseModel):
    operation: Literal["add", "remove"]
    items: list[ContentBulkTagTarget] = Field(min_length=1, max_length=100)
    tag_ids: list[str] = Field(min_length=1, max_length=100)

    @field_validator("items")
    @classmethod
    def clean_items(cls, value: list[ContentBulkTagTarget]) -> list[ContentBulkTagTarget]:
        cleaned: list[ContentBulkTagTarget] = []
        seen: set[tuple[str, str]] = set()
        for item in value:
            key = (item.kind, item.content_id)
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(item)
        if not cleaned:
            raise ValueError("请至少选择一条内容")
        return cleaned

    @field_validator("tag_ids")
    @classmethod
    def clean_bulk_tag_ids(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in value:
            tag_id = str(raw or "").strip()
            if not tag_id or tag_id in seen:
                continue
            seen.add(tag_id)
            cleaned.append(tag_id)
        if not cleaned:
            raise ValueError("请至少选择一个标签")
        return cleaned
