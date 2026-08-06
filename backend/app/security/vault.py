from __future__ import annotations

import json
import os
import secrets
import threading
import uuid
from datetime import date, datetime, timezone as dt_timezone
from pathlib import Path
from typing import Any, Literal

from app.security.crypto import (
    CryptoError,
    KdfParams,
    b64d,
    b64e,
    decrypt_bytes,
    encrypt_bytes,
    unwrap_master_key,
    wrap_master_key,
)
from app.security.sessions import Session, SessionManager
from app.services.progress import add_years, today_for_timezone
from app.storage.database import (
    Database,
    DatabaseContentNotFound,
    DatabaseRevisionConflict,
)


PIN_AAD = b"lifegraph:v1:key-slot:pin"
RECOVERY_AAD = b"lifegraph:v1:key-slot:recovery"
VERIFY_AAD = b"lifegraph:v1:verification"
VERIFY_TEXT = b"lifegraph-vault-ok-v1"


class VaultError(ValueError):
    pass


class CredentialError(VaultError):
    pass


class ContentNotFound(VaultError):
    pass


class ContentRevisionConflict(VaultError):
    pass


class VaultManager:
    def __init__(self, data_dir: Path, session_ttl_seconds: int = 1800) -> None:
        self.data_dir = data_dir
        self.metadata_path = data_dir / "vault.json"
        self.database = Database(data_dir / "lifegraph.db")
        self.sessions = SessionManager(session_ttl_seconds)
        self._master_key: bytes | None = None
        self._mutex = threading.RLock()
        if self.database.path.exists():
            self.database.initialize_schema()

    @property
    def is_initialized(self) -> bool:
        return self.metadata_path.exists() and self.database.path.exists()

    @property
    def is_unlocked(self) -> bool:
        return self._master_key is not None

    def _read_metadata(self) -> dict[str, Any]:
        try:
            return json.loads(self.metadata_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise VaultError("仓库尚未初始化") from exc
        except (json.JSONDecodeError, OSError) as exc:
            raise VaultError("仓库元数据损坏") from exc

    def _write_metadata(self, value: dict[str, Any]) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        temp_path = self.metadata_path.with_suffix(".json.tmp")
        temp_path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(temp_path, self.metadata_path)

    def initialize(
        self,
        *,
        display_name: str,
        birth_date: str,
        target_age: int,
        timezone: str,
        pin: str,
        recovery_secret: str | None,
    ) -> tuple[Session, str | None]:
        with self._mutex:
            if self.is_initialized:
                raise VaultError("仓库已经初始化")
            if not pin.isdigit() or not 6 <= len(pin) <= 12:
                raise VaultError("PIN 必须为 6—12 位数字")

            generated_recovery: str | None = None
            if not recovery_secret:
                generated_recovery = "LG-RECOVERY-" + secrets.token_urlsafe(24)
                recovery_secret = generated_recovery
            if len(recovery_secret) < 12:
                raise VaultError("恢复凭据至少需要 12 个字符")

            self.data_dir.mkdir(parents=True, exist_ok=True)
            master_key = os.urandom(32)
            params = KdfParams()
            verify_nonce, verify_ciphertext = encrypt_bytes(
                master_key, VERIFY_TEXT, aad=VERIFY_AAD
            )
            now = datetime.now(dt_timezone.utc).isoformat()
            metadata = {
                "format_version": 1,
                "created_at": now,
                "key_slots": {
                    "pin": wrap_master_key(master_key, pin, aad=PIN_AAD, params=params),
                    "recovery": wrap_master_key(
                        master_key, recovery_secret, aad=RECOVERY_AAD, params=params
                    ),
                },
                "verification": {
                    "nonce": b64e(verify_nonce),
                    "ciphertext": b64e(verify_ciphertext),
                },
            }

            try:
                self._write_metadata(metadata)
                self.database.initialize_schema()
                self.database.save_profile(
                    master_key,
                    str(uuid.uuid4()),
                    {
                        "display_name": display_name.strip(),
                        "birth_date": birth_date,
                        "target_age": target_age,
                        "timezone": "UTC"
                        if timezone in {"timezone.utc", "dt_timezone.utc"}
                        else timezone,
                        "calendar_mode": "dual",
                        "show_remaining_life": True,
                    },
                    now,
                )
            except Exception:
                self._master_key = None
                for candidate in (
                    self.metadata_path,
                    self.database.path,
                    self.database.path.with_name(self.database.path.name + "-wal"),
                    self.database.path.with_name(self.database.path.name + "-shm"),
                ):
                    candidate.unlink(missing_ok=True)
                raise

            self._master_key = master_key
            return self.sessions.create(), generated_recovery

    def unlock(self, method: Literal["pin", "recovery"], secret: str) -> Session:
        with self._mutex:
            if not self.is_initialized:
                raise VaultError("仓库尚未初始化")
            self.database.initialize_schema()
            metadata = self._read_metadata()
            try:
                if method == "pin":
                    master_key = unwrap_master_key(
                        metadata["key_slots"]["pin"], secret, aad=PIN_AAD
                    )
                elif method == "recovery":
                    master_key = unwrap_master_key(
                        metadata["key_slots"]["recovery"], secret, aad=RECOVERY_AAD
                    )
                else:
                    raise VaultError("不支持的解锁方式")
                verification = metadata["verification"]
                plain = decrypt_bytes(
                    master_key,
                    b64d(verification["nonce"]),
                    b64d(verification["ciphertext"]),
                    aad=VERIFY_AAD,
                )
                if plain != VERIFY_TEXT:
                    raise VaultError("仓库验证失败")
            except CryptoError as exc:
                raise VaultError(str(exc)) from exc

            self._master_key = master_key
            return self.sessions.create()

    def lock(self) -> None:
        with self._mutex:
            self.sessions.revoke_all()
            self._master_key = None

    def require_master_key(self) -> bytes:
        key = self._master_key
        if key is None:
            raise VaultError("数据仓库当前已锁定")
        return key

    def get_profile(self) -> dict[str, Any]:
        profile = self.database.load_profile(self.require_master_key())
        if profile is None:
            raise VaultError("个人档案不存在")
        return profile

    def _verify_slot_secret(
        self,
        *,
        slot_name: Literal["pin", "recovery"],
        secret: str,
        expected_master_key: bytes | None = None,
    ) -> tuple[dict[str, Any], bytes]:
        metadata = self._read_metadata()
        aad = PIN_AAD if slot_name == "pin" else RECOVERY_AAD
        try:
            master_key = unwrap_master_key(metadata["key_slots"][slot_name], secret, aad=aad)
            verification = metadata["verification"]
            plain = decrypt_bytes(
                master_key,
                b64d(verification["nonce"]),
                b64d(verification["ciphertext"]),
                aad=VERIFY_AAD,
            )
            if plain != VERIFY_TEXT:
                raise CredentialError("凭据验证失败")
            if expected_master_key is not None and not secrets.compare_digest(
                master_key, expected_master_key
            ):
                raise CredentialError("凭据与当前仓库不匹配")
        except (CryptoError, KeyError, TypeError) as exc:
            label = "当前 PIN" if slot_name == "pin" else "恢复凭据"
            raise CredentialError(f"{label}不正确") from exc
        return metadata, master_key

    @staticmethod
    def _validate_pin_value(pin: str, label: str = "PIN") -> None:
        if not pin.isdigit() or not 6 <= len(pin) <= 12:
            raise VaultError(f"{label} 必须为 6—12 位数字")

    @staticmethod
    def _profile_payload(profile: dict[str, Any]) -> dict[str, Any]:
        metadata_keys = {"id", "created_at", "updated_at", "revision"}
        return {key: value for key, value in profile.items() if key not in metadata_keys}

    @staticmethod
    def _period_intersects_life(
        *,
        time_scope: str,
        period_key: str,
        birth_date: date,
        target_date: date,
    ) -> bool:
        try:
            if time_scope == "day":
                start = date.fromisoformat(period_key)
                end = date.fromordinal(start.toordinal() + 1)
            elif time_scope == "month":
                year, month = map(int, period_key.split("-", 1))
                start = date(year, month, 1)
                if month == 12:
                    end = date(year + 1, 1, 1)
                else:
                    end = date(year, month + 1, 1)
            elif time_scope == "year":
                year = int(period_key)
                start = date(year, 1, 1)
                end = date(year + 1, 1, 1)
            else:
                return False
        except (TypeError, ValueError):
            return False
        return start < target_date and end > birth_date

    def profile_change_impact(self, *, birth_date: str) -> dict[str, Any]:
        profile = self.get_profile()
        new_birth = date.fromisoformat(birth_date)
        today, _ = today_for_timezone(profile.get("timezone"))
        if new_birth > today:
            raise VaultError("出生日期不能晚于今天")
        new_target = add_years(new_birth, int(profile["target_age"]))
        references = self.database.list_active_period_references(profile_id=profile["id"])
        counts = {"event": 0, "memory": 0, "plan": 0}
        for item in references:
            if not self._period_intersects_life(
                time_scope=item["time_scope"],
                period_key=item["period_key"],
                birth_date=new_birth,
                target_date=new_target,
            ):
                counts[item["kind"]] += 1
        return {
            "birth_date": birth_date,
            "target_date": new_target.isoformat(),
            "hidden_content_count": sum(counts.values()),
            "hidden_counts": counts,
        }

    def update_profile(
        self,
        *,
        display_name: str,
        birth_date: str,
        current_pin: str,
        revision: int,
    ) -> dict[str, Any]:
        with self._mutex:
            master_key = self.require_master_key()
            self._verify_slot_secret(
                slot_name="pin", secret=current_pin, expected_master_key=master_key
            )
            profile = self.get_profile()
            new_birth = date.fromisoformat(birth_date)
            today, _ = today_for_timezone(profile.get("timezone"))
            if new_birth > today:
                raise VaultError("出生日期不能晚于今天")
            payload = self._profile_payload(profile)
            payload["display_name"] = display_name.strip()
            payload["birth_date"] = birth_date
            now = datetime.now(dt_timezone.utc).isoformat()
            try:
                return self.database.update_profile(
                    master_key,
                    profile_id=profile["id"],
                    payload=payload,
                    expected_revision=revision,
                    timestamp=now,
                )
            except DatabaseContentNotFound as exc:
                raise ContentNotFound(str(exc)) from exc
            except DatabaseRevisionConflict as exc:
                raise ContentRevisionConflict(str(exc)) from exc

    def change_pin(self, *, current_pin: str, new_pin: str) -> None:
        with self._mutex:
            self._validate_pin_value(current_pin, "当前 PIN")
            self._validate_pin_value(new_pin, "新 PIN")
            master_key = self.require_master_key()
            metadata, verified_key = self._verify_slot_secret(
                slot_name="pin", secret=current_pin, expected_master_key=master_key
            )
            if current_pin == new_pin:
                raise VaultError("新 PIN 不能与当前 PIN 相同")
            try:
                params = KdfParams.from_dict(metadata["key_slots"]["pin"]["kdf"])
            except (CryptoError, KeyError, TypeError) as exc:
                raise VaultError("PIN 密钥槽元数据损坏") from exc
            metadata["key_slots"]["pin"] = wrap_master_key(
                verified_key, new_pin, aad=PIN_AAD, params=params
            )
            metadata["security_updated_at"] = datetime.now(dt_timezone.utc).isoformat()
            self._write_metadata(metadata)
            self.lock()

    def reset_pin_with_recovery(self, *, recovery_secret: str, new_pin: str) -> None:
        with self._mutex:
            self._validate_pin_value(new_pin, "新 PIN")
            if not self.is_initialized:
                raise VaultError("仓库尚未初始化")
            metadata, master_key = self._verify_slot_secret(
                slot_name="recovery", secret=recovery_secret
            )
            try:
                params = KdfParams.from_dict(metadata["key_slots"]["pin"]["kdf"])
            except (CryptoError, KeyError, TypeError) as exc:
                raise VaultError("PIN 密钥槽元数据损坏") from exc
            metadata["key_slots"]["pin"] = wrap_master_key(
                master_key, new_pin, aad=PIN_AAD, params=params
            )
            metadata["security_updated_at"] = datetime.now(dt_timezone.utc).isoformat()
            self._write_metadata(metadata)
            self.lock()

    def create_event(
        self,
        *,
        event_date: str,
        title: str,
        content: str,
        time_scope: str = "day",
        period_key: str | None = None,
    ) -> dict[str, Any]:
        with self._mutex:
            master_key = self.require_master_key()
            profile = self.get_profile()
            now = datetime.now(dt_timezone.utc).isoformat()
            return self.database.create_event(
                master_key,
                event_id=str(uuid.uuid4()),
                profile_id=profile["id"],
                event_date=event_date,
                time_scope=time_scope,
                period_key=period_key or event_date,
                payload={"title": title, "content": content},
                timestamp=now,
            )

    def list_events_for_period(self, time_scope: str, period_key: str) -> list[dict[str, Any]]:
        master_key = self.require_master_key()
        profile = self.get_profile()
        return self.database.list_events_for_period(
            master_key,
            profile_id=profile["id"],
            time_scope=time_scope,
            period_key=period_key,
        )

    def list_events_for_date(self, event_date: str) -> list[dict[str, Any]]:
        return self.list_events_for_period("day", event_date)

    def update_event(
        self,
        *,
        event_id: str,
        title: str,
        content: str,
        revision: int,
    ) -> dict[str, Any]:
        return self._update_content(
            kind="event",
            content_id=event_id,
            title=title,
            content=content,
            revision=revision,
        )

    def delete_event(self, *, event_id: str, revision: int) -> dict[str, Any]:
        return self._delete_content(kind="event", content_id=event_id, revision=revision)

    def create_memory(
        self,
        *,
        memory_date: str,
        title: str,
        content: str,
        time_scope: str = "day",
        period_key: str | None = None,
    ) -> dict[str, Any]:
        with self._mutex:
            master_key = self.require_master_key()
            profile = self.get_profile()
            now = datetime.now(dt_timezone.utc).isoformat()
            return self.database.create_memory(
                master_key,
                memory_id=str(uuid.uuid4()),
                profile_id=profile["id"],
                memory_date=memory_date,
                time_scope=time_scope,
                period_key=period_key or memory_date,
                payload={"title": title, "content": content},
                timestamp=now,
            )

    def list_memories_for_period(self, time_scope: str, period_key: str) -> list[dict[str, Any]]:
        master_key = self.require_master_key()
        profile = self.get_profile()
        return self.database.list_memories_for_period(
            master_key,
            profile_id=profile["id"],
            time_scope=time_scope,
            period_key=period_key,
        )

    def list_memories_for_date(self, memory_date: str) -> list[dict[str, Any]]:
        return self.list_memories_for_period("day", memory_date)

    def update_memory(
        self,
        *,
        memory_id: str,
        title: str,
        content: str,
        revision: int,
    ) -> dict[str, Any]:
        return self._update_content(
            kind="memory",
            content_id=memory_id,
            title=title,
            content=content,
            revision=revision,
        )

    def delete_memory(self, *, memory_id: str, revision: int) -> dict[str, Any]:
        return self._delete_content(kind="memory", content_id=memory_id, revision=revision)

    def create_plan(
        self,
        *,
        plan_date: str,
        title: str,
        content: str,
        time_scope: str = "day",
        period_key: str | None = None,
    ) -> dict[str, Any]:
        with self._mutex:
            master_key = self.require_master_key()
            profile = self.get_profile()
            now = datetime.now(dt_timezone.utc).isoformat()
            return self.database.create_plan(
                master_key,
                plan_id=str(uuid.uuid4()),
                profile_id=profile["id"],
                plan_date=plan_date,
                time_scope=time_scope,
                period_key=period_key or plan_date,
                payload={"title": title, "content": content},
                timestamp=now,
            )

    def list_plans_for_period(self, time_scope: str, period_key: str) -> list[dict[str, Any]]:
        master_key = self.require_master_key()
        profile = self.get_profile()
        return self.database.list_plans_for_period(
            master_key,
            profile_id=profile["id"],
            time_scope=time_scope,
            period_key=period_key,
        )

    def list_plans_for_date(self, plan_date: str) -> list[dict[str, Any]]:
        return self.list_plans_for_period("day", plan_date)

    def update_plan(
        self,
        *,
        plan_id: str,
        title: str,
        content: str,
        revision: int,
    ) -> dict[str, Any]:
        return self._update_content(
            kind="plan",
            content_id=plan_id,
            title=title,
            content=content,
            revision=revision,
        )

    def delete_plan(self, *, plan_id: str, revision: int) -> dict[str, Any]:
        return self._delete_content(kind="plan", content_id=plan_id, revision=revision)

    def _delete_content(
        self,
        *,
        kind: str,
        content_id: str,
        revision: int,
    ) -> dict[str, Any]:
        with self._mutex:
            self.require_master_key()
            profile = self.get_profile()
            now = datetime.now(dt_timezone.utc).isoformat()
            method = getattr(self.database, f"delete_{kind}")
            id_name = f"{kind}_id"
            try:
                return method(
                    **{
                        id_name: content_id,
                        "profile_id": profile["id"],
                        "expected_revision": revision,
                        "timestamp": now,
                    },
                )
            except DatabaseContentNotFound as exc:
                raise ContentNotFound(str(exc)) from exc
            except DatabaseRevisionConflict as exc:
                raise ContentRevisionConflict(str(exc)) from exc

    def _update_content(
        self,
        *,
        kind: str,
        content_id: str,
        title: str,
        content: str,
        revision: int,
    ) -> dict[str, Any]:
        with self._mutex:
            master_key = self.require_master_key()
            profile = self.get_profile()
            now = datetime.now(dt_timezone.utc).isoformat()
            method = getattr(self.database, f"update_{kind}")
            id_name = f"{kind}_id"
            try:
                return method(
                    master_key,
                    **{
                        id_name: content_id,
                        "profile_id": profile["id"],
                        "payload": {"title": title, "content": content},
                        "expected_revision": revision,
                        "timestamp": now,
                    },
                )
            except DatabaseContentNotFound as exc:
                raise ContentNotFound(str(exc)) from exc
            except DatabaseRevisionConflict as exc:
                raise ContentRevisionConflict(str(exc)) from exc

    def list_trash(self) -> list[dict[str, Any]]:
        master_key = self.require_master_key()
        profile = self.get_profile()
        return self.database.list_deleted_content(master_key, profile_id=profile["id"])

    def restore_trash_item(
        self,
        *,
        kind: str,
        content_id: str,
        revision: int,
    ) -> dict[str, Any]:
        with self._mutex:
            self.require_master_key()
            profile = self.get_profile()
            now = datetime.now(dt_timezone.utc).isoformat()
            try:
                return self.database.restore_deleted_content(
                    kind=kind,
                    content_id=content_id,
                    profile_id=profile["id"],
                    expected_revision=revision,
                    timestamp=now,
                )
            except DatabaseContentNotFound as exc:
                raise ContentNotFound(str(exc)) from exc
            except DatabaseRevisionConflict as exc:
                raise ContentRevisionConflict(str(exc)) from exc

    def permanently_delete_trash_item(
        self,
        *,
        kind: str,
        content_id: str,
        revision: int,
    ) -> dict[str, Any]:
        with self._mutex:
            self.require_master_key()
            profile = self.get_profile()
            try:
                return self.database.permanently_delete_content(
                    kind=kind,
                    content_id=content_id,
                    profile_id=profile["id"],
                    expected_revision=revision,
                )
            except DatabaseContentNotFound as exc:
                raise ContentNotFound(str(exc)) from exc
            except DatabaseRevisionConflict as exc:
                raise ContentRevisionConflict(str(exc)) from exc

    def empty_trash(self) -> dict[str, Any]:
        with self._mutex:
            self.require_master_key()
            profile = self.get_profile()
            return self.database.empty_trash(profile_id=profile["id"])

    def get_content_status(self, *, start_date: str, end_date: str) -> dict[str, dict[str, dict[str, bool]]]:
        self.require_master_key()
        profile = self.get_profile()
        return self.database.get_content_status(
            profile_id=profile["id"],
            start_date=start_date,
            end_date=end_date,
        )
