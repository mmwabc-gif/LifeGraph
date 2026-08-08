from __future__ import annotations

import json
import os
import secrets
import threading
import uuid
from datetime import date, datetime, timedelta, timezone as dt_timezone
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
from app.services.backup import (
    BackupArtifact,
    LifeVaultPackage,
    LifeVaultPackageError,
    build_lifevault_backup,
    inspect_lifevault_package,
    sha256_bytes,
    verify_lifevault_database,
)
from app.services.progress import add_years, today_for_timezone
from app.storage.database import (
    Database,
    DatabaseContentNotFound,
    DatabaseIntegrityError,
    DatabaseRevisionConflict,
)


PIN_AAD = b"lifegraph:v1:key-slot:pin"
RECOVERY_AAD = b"lifegraph:v1:key-slot:recovery"
VERIFY_AAD = b"lifegraph:v1:verification"
VERIFY_TEXT = b"lifegraph-vault-ok-v1"
SECURITY_AUDIT_LIMIT = 50

SECURITY_ACTION_LABELS = {
    "vault_initialized": "加密仓库已初始化",
    "pin_changed": "PIN 已修改",
    "pin_reset_with_recovery": "已使用恢复凭据重置 PIN",
    "recovery_credential_changed": "恢复凭据已更换",
    "repository_restored": "已从 .lifevault 恢复仓库",
    "legacy_security_update": "安全设置曾被更新",
}


class VaultError(ValueError):
    pass


class CredentialError(VaultError):
    pass


class ContentNotFound(VaultError):
    pass


class ContentRevisionConflict(VaultError):
    pass


class TagConflict(VaultError):
    pass


class VaultManager:
    def __init__(
        self,
        data_dir: Path,
        session_ttl_seconds: int = 1800,
        app_version: str = "0.0.6",
    ) -> None:
        self.data_dir = data_dir
        self.metadata_path = data_dir / "vault.json"
        self.database = Database(data_dir / "lifegraph.db")
        self.auto_backup_dir = data_dir / "backups" / "auto"
        self.app_version = app_version
        self.sessions = SessionManager(session_ttl_seconds)
        self._master_key: bytes | None = None
        self._restore_in_progress = False
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
                "backup_policy": self._default_backup_policy(),
                "key_slot_updated_at": {"pin": now, "recovery": now},
                "security_updated_at": now,
                "security_audit": [
                    {"action": "vault_initialized", "at": now, "result": "success"}
                ],
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
        if self._restore_in_progress:
            raise VaultError("仓库正在恢复，请稍后重试")
        key = self._master_key
        if key is None:
            raise VaultError("数据仓库当前已锁定")
        return key

    def get_profile(self) -> dict[str, Any]:
        profile = self.database.load_profile(self.require_master_key())
        if profile is None:
            raise VaultError("个人档案不存在")
        return profile

    @staticmethod
    def _normalized_security_audit(metadata: dict[str, Any]) -> list[dict[str, str]]:
        raw = metadata.get("security_audit")
        entries: list[dict[str, str]] = []
        if isinstance(raw, list):
            for item in raw[-SECURITY_AUDIT_LIMIT:]:
                if not isinstance(item, dict):
                    continue
                action = str(item.get("action") or "").strip()
                at = str(item.get("at") or "").strip()
                result = str(item.get("result") or "success").strip()
                if action and at:
                    entries.append({"action": action, "at": at, "result": result})
        if not entries:
            created_at = metadata.get("created_at")
            if isinstance(created_at, str) and created_at:
                entries.append(
                    {"action": "vault_initialized", "at": created_at, "result": "success"}
                )
            security_updated_at = metadata.get("security_updated_at")
            if (
                isinstance(security_updated_at, str)
                and security_updated_at
                and security_updated_at != created_at
            ):
                entries.append(
                    {
                        "action": "legacy_security_update",
                        "at": security_updated_at,
                        "result": "success",
                    }
                )
        return entries[-SECURITY_AUDIT_LIMIT:]

    @classmethod
    def _append_security_audit(
        cls, metadata: dict[str, Any], action: str, *, at: str | None = None
    ) -> str:
        timestamp = at or datetime.now(dt_timezone.utc).isoformat()
        entries = cls._normalized_security_audit(metadata)
        entries.append({"action": action, "at": timestamp, "result": "success"})
        metadata["security_audit"] = entries[-SECURITY_AUDIT_LIMIT:]
        metadata["security_updated_at"] = timestamp
        return timestamp

    @staticmethod
    def _key_slot_summary(
        metadata: dict[str, Any], slot_name: Literal["pin", "recovery"]
    ) -> dict[str, Any]:
        slot = metadata.get("key_slots", {}).get(slot_name)
        if not isinstance(slot, dict):
            return {"configured": False, "kdf": None, "updated_at": None}
        kdf = slot.get("kdf") if isinstance(slot.get("kdf"), dict) else {}
        timestamps = metadata.get("key_slot_updated_at")
        updated_at = None
        if isinstance(timestamps, dict):
            value = timestamps.get(slot_name)
            if isinstance(value, str):
                updated_at = value
        if not updated_at:
            updated_at = metadata.get("security_updated_at") or metadata.get("created_at")
        return {
            "configured": True,
            "kdf": kdf.get("name") or "unknown",
            "updated_at": updated_at,
        }

    def get_security_summary(self) -> dict[str, Any]:
        self.require_master_key()
        metadata = self._read_metadata()
        audit = self._normalized_security_audit(metadata)
        rendered_audit = [
            {
                **entry,
                "label": SECURITY_ACTION_LABELS.get(entry["action"], "安全设置已更新"),
            }
            for entry in reversed(audit[-20:])
        ]
        return {
            "format_version": metadata.get("format_version"),
            "vault_created_at": metadata.get("created_at"),
            "security_updated_at": metadata.get("security_updated_at")
            or metadata.get("created_at"),
            "key_slots": {
                "pin": self._key_slot_summary(metadata, "pin"),
                "recovery": self._key_slot_summary(metadata, "recovery"),
            },
            "audit": rendered_audit,
            "audit_count": len(audit),
            "audit_limit": SECURITY_AUDIT_LIMIT,
        }

    @staticmethod
    def _default_backup_policy() -> dict[str, Any]:
        return {
            "enabled": False,
            "frequency": "daily",
            "retention_count": 10,
            "last_attempt_at": None,
            "last_success_at": None,
            "last_filename": None,
            "last_error": None,
            "last_verified_at": None,
            "last_verified_filename": None,
            "last_verification_error": None,
        }

    @classmethod
    def _normalized_backup_policy(cls, metadata: dict[str, Any]) -> dict[str, Any]:
        policy = cls._default_backup_policy()
        raw = metadata.get("backup_policy")
        if isinstance(raw, dict):
            policy.update({key: raw.get(key) for key in policy if key in raw})
        policy["enabled"] = bool(policy.get("enabled"))
        if policy.get("frequency") not in {"daily", "weekly"}:
            policy["frequency"] = "daily"
        try:
            retention = int(policy.get("retention_count", 10))
        except (TypeError, ValueError):
            retention = 10
        policy["retention_count"] = min(50, max(3, retention))
        for key in (
            "last_attempt_at",
            "last_success_at",
            "last_filename",
            "last_error",
            "last_verified_at",
            "last_verified_filename",
            "last_verification_error",
        ):
            if policy.get(key) is not None and not isinstance(policy.get(key), str):
                policy[key] = str(policy[key])
        return policy

    @staticmethod
    def _parse_utc_timestamp(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt_timezone.utc)
        return parsed.astimezone(dt_timezone.utc)

    @staticmethod
    def _backup_interval(frequency: str) -> timedelta:
        return timedelta(days=7 if frequency == "weekly" else 1)

    def _backup_next_due_at(self, policy: dict[str, Any]) -> str | None:
        if not policy["enabled"]:
            return None
        last_success = self._parse_utc_timestamp(policy.get("last_success_at"))
        if last_success is None:
            return datetime.now(dt_timezone.utc).isoformat()
        return (last_success + self._backup_interval(policy["frequency"])).isoformat()

    def list_auto_backup_history(self) -> list[dict[str, Any]]:
        """List local automatic backup packages without exposing repository plaintext."""
        with self._mutex:
            self.require_master_key()
            if not self.auto_backup_dir.exists():
                return []
            entries: list[dict[str, Any]] = []
            for path in self.auto_backup_dir.glob("*.lifevault"):
                if not path.is_file():
                    continue
                stat = path.stat()
                entry: dict[str, Any] = {
                    "filename": path.name,
                    "size": stat.st_size,
                    "modified_at": datetime.fromtimestamp(
                        stat.st_mtime, tz=dt_timezone.utc
                    ).isoformat(),
                    "valid": False,
                }
                try:
                    package = inspect_lifevault_package(path.read_bytes())
                    producer = package.manifest.get("producer") or {}
                    entry.update(
                        {
                            "valid": True,
                            "created_at": package.manifest.get("created_at"),
                            "producer_version": producer.get("version"),
                            "schema_version": (package.manifest.get("repository") or {}).get(
                                "schema_version"
                            ),
                            "sha256": package.package_sha256,
                        }
                    )
                except (LifeVaultPackageError, OSError) as exc:
                    entry["error"] = str(exc)
                entries.append(entry)
            entries.sort(
                key=lambda item: item.get("created_at") or item["modified_at"],
                reverse=True,
            )
            return entries

    def _auto_backup_health(
        self, policy: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        now = datetime.now(dt_timezone.utc)
        next_due_at = self._backup_next_due_at(policy)
        next_due = self._parse_utc_timestamp(next_due_at)
        overdue_seconds = (
            max(0, int((now - next_due).total_seconds()))
            if policy["enabled"] and next_due is not None and now > next_due
            else 0
        )
        latest = history[0] if history else None
        verified_current = bool(
            latest
            and latest.get("valid")
            and policy.get("last_verified_filename") == latest.get("filename")
            and policy.get("last_verified_at")
            and not policy.get("last_verification_error")
        )

        if not policy["enabled"]:
            code, level, message = (
                "disabled",
                "neutral",
                "自动备份未启用，可随时手动生成或开启周期备份。",
            )
        elif latest is None:
            code, level, message = (
                "missing",
                "warning",
                "尚无可用的自动备份，请立即生成首个备份。",
            )
        elif not latest.get("valid"):
            code, level, message = (
                "invalid",
                "error",
                "最近备份文件结构或校验值异常，请重新生成备份。",
            )
        elif policy.get("last_error"):
            code, level, message = (
                "failed",
                "error",
                "最近一次自动备份失败，请检查存储空间或文件权限。",
            )
        elif overdue_seconds > 0:
            code, level, message = (
                "overdue",
                "warning",
                "自动备份已经超过计划时间，LifeGraph 会在正常使用时补做。",
            )
        elif not verified_current:
            code, level, message = (
                "verification_due",
                "warning",
                "最近备份结构正常，但尚未完成针对落盘文件的恢复验证。",
            )
        else:
            code, level, message = (
                "healthy",
                "success",
                "最近备份已通过结构、校验和与加密内容恢复验证。",
            )

        last_success = self._parse_utc_timestamp(policy.get("last_success_at"))
        age_seconds = (
            max(0, int((now - last_success).total_seconds()))
            if last_success is not None
            else None
        )
        return {
            "code": code,
            "level": level,
            "message": message,
            "checked_at": now.isoformat(),
            "overdue": overdue_seconds > 0,
            "overdue_seconds": overdue_seconds,
            "last_backup_age_seconds": age_seconds,
            "latest_backup": latest,
            "verification": {
                "verified": verified_current,
                "verified_at": policy.get("last_verified_at"),
                "filename": policy.get("last_verified_filename"),
                "error": policy.get("last_verification_error"),
            },
        }

    def get_auto_backup_status(self) -> dict[str, Any]:
        with self._mutex:
            self.require_master_key()
            metadata = self._read_metadata()
            policy = self._normalized_backup_policy(metadata)
            history = self.list_auto_backup_history()
            next_due_at = self._backup_next_due_at(policy)
            return {
                **policy,
                "next_due_at": next_due_at,
                "history_count": len(history),
                "history_size": sum(item["size"] for item in history),
                "backup_directory": str(self.auto_backup_dir),
                "health": self._auto_backup_health(policy, history),
            }

    def _write_backup_policy(self, metadata: dict[str, Any], policy: dict[str, Any]) -> None:
        metadata["backup_policy"] = self._normalized_backup_policy(
            {"backup_policy": policy}
        )
        self._write_metadata(metadata)

    def _prune_auto_backup_history(self, retention_count: int) -> list[str]:
        if not self.auto_backup_dir.exists():
            return []
        candidates = [path for path in self.auto_backup_dir.glob("*.lifevault") if path.is_file()]
        candidates.sort(key=lambda path: (path.stat().st_mtime_ns, path.name), reverse=True)
        deleted: list[str] = []
        for path in candidates[retention_count:]:
            path.unlink(missing_ok=True)
            deleted.append(path.name)
        return deleted

    def update_auto_backup_policy(
        self,
        *,
        enabled: bool,
        frequency: Literal["daily", "weekly"],
        retention_count: int,
        create_initial_backup: bool = True,
    ) -> dict[str, Any]:
        with self._mutex:
            self.require_master_key()
            if frequency not in {"daily", "weekly"}:
                raise VaultError("自动备份周期无效")
            if not 3 <= retention_count <= 50:
                raise VaultError("自动备份保留数量必须为 3—50")
            metadata = self._read_metadata()
            previous = self._normalized_backup_policy(metadata)
            policy = {**previous, "enabled": enabled, "frequency": frequency, "retention_count": retention_count}
            self._write_backup_policy(metadata, policy)
            self._prune_auto_backup_history(retention_count)
            if enabled and create_initial_backup and (
                not previous["enabled"] or not previous.get("last_success_at")
            ):
                self.create_automatic_backup(force=True, reason="policy-enabled")
            return self.get_auto_backup_status()

    def create_automatic_backup(
        self,
        *,
        force: bool = False,
        reason: str = "scheduled",
        raise_on_error: bool = True,
    ) -> dict[str, Any]:
        """Create a verified local .lifevault backup when policy is due."""
        with self._mutex:
            master_key = self.require_master_key()
            metadata = self._read_metadata()
            policy = self._normalized_backup_policy(metadata)
            now = datetime.now(dt_timezone.utc)
            if not force:
                if not policy["enabled"]:
                    return {"created": False, "reason": "disabled", **self.get_auto_backup_status()}
                last_success = self._parse_utc_timestamp(policy.get("last_success_at"))
                if last_success and now < last_success + self._backup_interval(policy["frequency"]):
                    return {"created": False, "reason": "not-due", **self.get_auto_backup_status()}
                last_attempt = self._parse_utc_timestamp(policy.get("last_attempt_at"))
                if policy.get("last_error") and last_attempt and now < last_attempt + timedelta(hours=1):
                    return {"created": False, "reason": "retry-later", **self.get_auto_backup_status()}

            policy["last_attempt_at"] = now.isoformat()
            policy["last_error"] = None
            self._write_backup_policy(metadata, policy)
            try:
                artifact = build_lifevault_backup(
                    database=self.database,
                    metadata_path=self.metadata_path,
                    master_key=master_key,
                    app_version=self.app_version,
                )
                timestamp = now.strftime("%Y%m%d-%H%M%S")
                filename = f"lifegraph-auto-{timestamp}.lifevault"
                path = self.auto_backup_dir / filename
                if path.exists():
                    path = self.auto_backup_dir / (
                        f"lifegraph-auto-{timestamp}-{secrets.token_hex(3)}.lifevault"
                    )
                self._atomic_write(path, artifact.content)
                # Re-open and decrypt the exact bytes written to disk before recording success.
                package = inspect_lifevault_package(path.read_bytes())
                verify_lifevault_database(package, master_key)
                verified_at = datetime.now(dt_timezone.utc).isoformat()
                policy["last_success_at"] = verified_at
                policy["last_filename"] = path.name
                policy["last_error"] = None
                policy["last_verified_at"] = verified_at
                policy["last_verified_filename"] = path.name
                policy["last_verification_error"] = None
                metadata = self._read_metadata()
                self._write_backup_policy(metadata, policy)
                deleted = self._prune_auto_backup_history(policy["retention_count"])
                return {
                    "created": True,
                    "reason": reason,
                    "filename": path.name,
                    "size": path.stat().st_size,
                    "sha256": sha256_bytes(path.read_bytes()),
                    "pruned_filenames": deleted,
                    **self.get_auto_backup_status(),
                }
            except Exception as exc:
                policy["last_error"] = str(exc)
                policy["last_verification_error"] = str(exc)
                metadata = self._read_metadata()
                self._write_backup_policy(metadata, policy)
                if raise_on_error:
                    raise VaultError(f"自动备份失败：{exc}") from exc
                return {"created": False, "reason": "failed", **self.get_auto_backup_status()}

    def verify_latest_auto_backup(self) -> dict[str, Any]:
        """Fully verify the newest local automatic backup from its exact disk bytes."""
        with self._mutex:
            master_key = self.require_master_key()
            history = self.list_auto_backup_history()
            if not history:
                raise VaultError("尚无可验证的自动备份")
            latest = history[0]
            filename = str(latest.get("filename") or "")
            metadata = self._read_metadata()
            policy = self._normalized_backup_policy(metadata)
            try:
                path = self.auto_backup_path(filename)
                package = inspect_lifevault_package(path.read_bytes())
                integrity = verify_lifevault_database(package, master_key)
                verified_at = datetime.now(dt_timezone.utc).isoformat()
                policy["last_verified_at"] = verified_at
                policy["last_verified_filename"] = filename
                policy["last_verification_error"] = None
                self._write_backup_policy(metadata, policy)
                return {
                    "verified": True,
                    "filename": filename,
                    "verified_at": verified_at,
                    "size": path.stat().st_size,
                    "sha256": package.package_sha256,
                    "created_at": package.manifest.get("created_at"),
                    "schema_version": integrity.get("schema_version"),
                    "sqlite_quick_check": integrity.get("sqlite_quick_check"),
                    "foreign_key_errors": integrity.get("foreign_key_errors"),
                    "encrypted_records_verified": integrity.get(
                        "encrypted_records_verified"
                    ),
                    "status": self.get_auto_backup_status(),
                }
            except Exception as exc:
                policy["last_verified_at"] = datetime.now(dt_timezone.utc).isoformat()
                policy["last_verified_filename"] = filename or None
                policy["last_verification_error"] = str(exc)
                self._write_backup_policy(metadata, policy)
                if isinstance(exc, VaultError):
                    raise
                raise VaultError(f"最近备份验证失败：{exc}") from exc

    def maybe_create_automatic_backup(self, *, reason: str = "activity") -> dict[str, Any] | None:
        """Best-effort hook used after successful API activity."""
        if not self.is_unlocked or self._restore_in_progress:
            return None
        try:
            return self.create_automatic_backup(
                force=False,
                reason=reason,
                raise_on_error=False,
            )
        except VaultError:
            return None

    def auto_backup_path(self, filename: str) -> Path:
        with self._mutex:
            self.require_master_key()
            if not filename or Path(filename).name != filename or not filename.endswith(".lifevault"):
                raise VaultError("自动备份文件名无效")
            path = self.auto_backup_dir / filename
            if not path.is_file():
                raise VaultError("自动备份文件不存在")
            return path

    def delete_auto_backup(self, *, filename: str) -> dict[str, Any]:
        with self._mutex:
            path = self.auto_backup_path(filename)
            path.unlink()
            metadata = self._read_metadata()
            policy = self._normalized_backup_policy(metadata)
            if policy.get("last_filename") == filename:
                history = self.list_auto_backup_history()
                newest = history[0] if history else None
                policy["last_filename"] = newest["filename"] if newest else None
                policy["last_success_at"] = newest.get("created_at") if newest else None
                policy["last_verified_at"] = None
                policy["last_verified_filename"] = None
                policy["last_verification_error"] = None
                self._write_backup_policy(metadata, policy)
            return {"deleted": True, "filename": filename, **self.get_auto_backup_status()}

    def clear_auto_backup_history(self) -> dict[str, Any]:
        with self._mutex:
            self.require_master_key()
            deleted: list[str] = []
            if self.auto_backup_dir.exists():
                for path in self.auto_backup_dir.glob("*.lifevault"):
                    if path.is_file():
                        path.unlink()
                        deleted.append(path.name)
            metadata = self._read_metadata()
            policy = self._normalized_backup_policy(metadata)
            policy["last_success_at"] = None
            policy["last_filename"] = None
            policy["last_verified_at"] = None
            policy["last_verified_filename"] = None
            policy["last_verification_error"] = None
            self._write_backup_policy(metadata, policy)
            return {"deleted_count": len(deleted), "deleted_filenames": sorted(deleted), **self.get_auto_backup_status()}

    def check_backup_integrity(self) -> dict[str, Any]:
        """Create and verify a temporary consistent snapshot without exporting it."""
        with self._mutex:
            master_key = self.require_master_key()
            if not self.metadata_path.exists() or not self.database.path.exists():
                raise VaultError("加密仓库文件不完整")
            # Reading metadata here verifies that the wrapped-key document is valid JSON.
            self._read_metadata()
            import tempfile

            with tempfile.TemporaryDirectory(prefix="lifegraph-check-") as temporary_dir:
                snapshot_path = Path(temporary_dir) / "lifegraph.db"
                self.database.create_consistent_snapshot(snapshot_path)
                try:
                    result = self.database.verify_encrypted_snapshot(
                        snapshot_path, master_key
                    )
                except DatabaseIntegrityError as exc:
                    raise VaultError(str(exc)) from exc
            return {
                "ready": True,
                **result,
                "checked_at": datetime.now(dt_timezone.utc).isoformat(),
            }

    def export_lifevault(self, *, app_version: str) -> BackupArtifact:
        """Export the current encrypted repository as a verified .lifevault package."""
        with self._mutex:
            master_key = self.require_master_key()
            if not self.metadata_path.exists() or not self.database.path.exists():
                raise VaultError("加密仓库文件不完整")
            try:
                return build_lifevault_backup(
                    database=self.database,
                    metadata_path=self.metadata_path,
                    master_key=master_key,
                    app_version=app_version,
                )
            except (DatabaseIntegrityError, OSError, ValueError, json.JSONDecodeError) as exc:
                raise VaultError(f"备份导出失败：{exc}") from exc

    @staticmethod
    def _external_master_key(
        package: LifeVaultPackage,
        *,
        credential_method: Literal["pin", "recovery"],
        credential_secret: str,
    ) -> bytes:
        try:
            metadata = json.loads(package.metadata_bytes.decode("utf-8"))
            if credential_method == "pin":
                slot = metadata["key_slots"]["pin"]
                aad = PIN_AAD
                label = "备份 PIN"
            elif credential_method == "recovery":
                slot = metadata["key_slots"]["recovery"]
                aad = RECOVERY_AAD
                label = "备份恢复凭据"
            else:
                raise VaultError("不支持的备份凭据类型")
            master_key = unwrap_master_key(slot, credential_secret, aad=aad)
            verification = metadata["verification"]
            plain = decrypt_bytes(
                master_key,
                b64d(verification["nonce"]),
                b64d(verification["ciphertext"]),
                aad=VERIFY_AAD,
            )
            if plain != VERIFY_TEXT:
                raise CredentialError(f"{label}不正确")
            return master_key
        except CredentialError:
            raise
        except (CryptoError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            label = "备份 PIN" if credential_method == "pin" else "备份恢复凭据"
            raise CredentialError(f"{label}不正确") from exc

    @staticmethod
    def _import_report(
        package: LifeVaultPackage,
        integrity: dict[str, Any],
        *,
        credential_method: str,
    ) -> dict[str, Any]:
        producer = package.manifest.get("producer") or {}
        return {
            "valid": True,
            "format": package.manifest.get("format"),
            "format_version": package.manifest.get("format_version"),
            "created_at": package.manifest.get("created_at"),
            "producer_version": producer.get("version"),
            "schema_version": integrity.get(
                "source_schema_version", integrity["schema_version"]
            ),
            "compatible_schema_version": integrity["schema_version"],
            "encrypted_records_verified": integrity["encrypted_records_verified"],
            "record_counts": integrity.get("record_counts", {}),
            "package_sha256": package.package_sha256,
            "credential_method": credential_method,
        }

    def inspect_lifevault_import(
        self,
        *,
        content: bytes,
        credential_method: Literal["pin", "recovery"],
        credential_secret: str,
    ) -> dict[str, Any]:
        """Run a full restore rehearsal without changing the live repository."""
        with self._mutex:
            self.require_master_key()
            try:
                package = inspect_lifevault_package(content)
                imported_key = self._external_master_key(
                    package,
                    credential_method=credential_method,
                    credential_secret=credential_secret,
                )
                integrity = verify_lifevault_database(package, imported_key)
            except (LifeVaultPackageError, DatabaseIntegrityError) as exc:
                raise VaultError(f"备份包验证失败：{exc}") from exc
            return self._import_report(
                package, integrity, credential_method=credential_method
            )

    @staticmethod
    def _atomic_write(path: Path, value: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(path.name + ".tmp")
        with temp_path.open("wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)

    def restore_lifevault(
        self,
        *,
        content: bytes,
        credential_method: Literal["pin", "recovery"],
        credential_secret: str,
        confirm: str,
        app_version: str,
    ) -> dict[str, Any]:
        """Replace the live repository after rehearsal and automatic rescue backup."""
        if confirm != "REPLACE_REPOSITORY":
            raise VaultError("恢复确认口令无效")
        with self._mutex:
            current_master_key = self.require_master_key()
            try:
                package = inspect_lifevault_package(content)
                imported_key = self._external_master_key(
                    package,
                    credential_method=credential_method,
                    credential_secret=credential_secret,
                )
                source_integrity = verify_lifevault_database(package, imported_key)
            except (LifeVaultPackageError, DatabaseIntegrityError) as exc:
                raise VaultError(f"备份包验证失败：{exc}") from exc

            # Save a verified rescue package outside the two live repository files.
            try:
                rescue = build_lifevault_backup(
                    database=self.database,
                    metadata_path=self.metadata_path,
                    master_key=current_master_key,
                    app_version=app_version,
                )
            except (DatabaseIntegrityError, OSError, ValueError, json.JSONDecodeError) as exc:
                raise VaultError(f"无法创建恢复前安全备份：{exc}") from exc
            recovery_dir = self.data_dir / "recovery"
            timestamp = datetime.now(dt_timezone.utc).strftime("%Y%m%d-%H%M%S")
            rescue_path = recovery_dir / f"lifegraph-before-restore-{timestamp}.lifevault"
            if rescue_path.exists():
                rescue_path = recovery_dir / (
                    f"lifegraph-before-restore-{timestamp}-{secrets.token_hex(3)}.lifevault"
                )
            self._atomic_write(rescue_path, rescue.content)

            # The rescue package is also the rollback source if replacing either file fails.
            try:
                rollback_package = inspect_lifevault_package(rescue.content)
            except LifeVaultPackageError as exc:  # pragma: no cover - build output invariant
                raise VaultError(f"恢复前安全备份无法重新读取：{exc}") from exc

            incoming_metadata = self.data_dir / ".restore-vault.json"
            incoming_database = self.data_dir / ".restore-lifegraph.db"
            self._atomic_write(incoming_metadata, package.metadata_bytes)
            self._atomic_write(incoming_database, package.database_bytes)
            # Verify that the exact candidate bytes reached disk before replacement.
            if (
                incoming_metadata.read_bytes() != package.metadata_bytes
                or incoming_database.read_bytes() != package.database_bytes
            ):
                incoming_metadata.unlink(missing_ok=True)
                incoming_database.unlink(missing_ok=True)
                raise VaultError("恢复候选文件写入校验失败")

            self._restore_in_progress = True
            try:
                for suffix in ("-wal", "-shm"):
                    self.database.path.with_name(self.database.path.name + suffix).unlink(
                        missing_ok=True
                    )
                os.replace(incoming_metadata, self.metadata_path)
                os.replace(incoming_database, self.database.path)
                self.database.initialize_schema()
                restored_integrity = self.database.verify_encrypted_snapshot(
                    self.database.path, imported_key
                )
                restored_metadata = self._read_metadata()
                self._append_security_audit(
                    restored_metadata, "repository_restored"
                )
                self._write_metadata(restored_metadata)
            except Exception as exc:
                # Roll back from the already verified pre-restore package.
                try:
                    self._atomic_write(self.metadata_path, rollback_package.metadata_bytes)
                    self._atomic_write(self.database.path, rollback_package.database_bytes)
                    for suffix in ("-wal", "-shm"):
                        self.database.path.with_name(
                            self.database.path.name + suffix
                        ).unlink(missing_ok=True)
                    self.database.initialize_schema()
                    self.database.verify_encrypted_snapshot(
                        self.database.path, current_master_key
                    )
                    self._master_key = current_master_key
                except Exception as rollback_exc:  # pragma: no cover - catastrophic I/O
                    self._master_key = None
                    self.sessions.revoke_all()
                    raise VaultError(
                        f"仓库恢复失败且自动回滚失败：{rollback_exc}"
                    ) from exc
                raise VaultError(f"仓库恢复失败，已自动回滚：{exc}") from exc
            finally:
                incoming_metadata.unlink(missing_ok=True)
                incoming_database.unlink(missing_ok=True)
                self._restore_in_progress = False

            # A restored repository must always be unlocked again with its own credential.
            self.sessions.revoke_all()
            self._master_key = None
            report = self._import_report(
                package, source_integrity, credential_method=credential_method
            )
            report.update(
                {
                    "restored": True,
                    "locked": True,
                    "restored_schema_version": restored_integrity["schema_version"],
                    "rescue_backup_filename": rescue_path.name,
                }
            )
            return report

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
            timestamp = self._append_security_audit(metadata, "pin_changed")
            metadata.setdefault("key_slot_updated_at", {})["pin"] = timestamp
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
            timestamp = self._append_security_audit(
                metadata, "pin_reset_with_recovery"
            )
            metadata.setdefault("key_slot_updated_at", {})["pin"] = timestamp
            self._write_metadata(metadata)
            self.lock()

    def change_recovery_credential(
        self,
        *,
        current_pin: str,
        new_recovery_secret: str | None = None,
        generate: bool = True,
    ) -> dict[str, Any]:
        with self._mutex:
            self._validate_pin_value(current_pin, "当前 PIN")
            master_key = self.require_master_key()
            metadata, verified_key = self._verify_slot_secret(
                slot_name="pin", secret=current_pin, expected_master_key=master_key
            )
            generated_secret: str | None = None
            if generate:
                generated_secret = "LG-RECOVERY-" + secrets.token_urlsafe(24)
                recovery_secret = generated_secret
            else:
                recovery_secret = (new_recovery_secret or "").strip()
            if len(recovery_secret) < 12:
                raise VaultError("新恢复凭据至少需要 12 个字符")
            try:
                params = KdfParams.from_dict(
                    metadata["key_slots"]["recovery"]["kdf"]
                )
            except (CryptoError, KeyError, TypeError) as exc:
                raise VaultError("恢复密钥槽元数据损坏") from exc
            metadata["key_slots"]["recovery"] = wrap_master_key(
                verified_key, recovery_secret, aad=RECOVERY_AAD, params=params
            )
            timestamp = self._append_security_audit(
                metadata, "recovery_credential_changed"
            )
            metadata.setdefault("key_slot_updated_at", {})["recovery"] = timestamp
            self._write_metadata(metadata)
            return {
                "changed": True,
                "generated_recovery_secret": generated_secret,
                "security": self.get_security_summary(),
            }

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
        content_format: str = "plain",
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
                payload={"title": title, "content": content, "content_format": content_format},
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

    def search_memories(
        self,
        *,
        query: str = "",
        tag_ids: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        master_key = self.require_master_key()
        profile = self.get_profile()
        return self.database.search_memories(
            master_key,
            profile_id=profile["id"],
            query=query,
            tag_ids=tag_ids,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )

    def get_memory_tag_map(
        self,
        *,
        tag_ids: list[str],
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        self.require_master_key()
        profile = self.get_profile()
        return self.database.get_memory_tag_map(
            profile_id=profile["id"],
            tag_ids=tag_ids,
            start_date=start_date,
            end_date=end_date,
        )

    def update_memory(
        self,
        *,
        memory_id: str,
        title: str,
        content: str,
        revision: int,
        content_format: str = "plain",
    ) -> dict[str, Any]:
        return self._update_content(
            kind="memory",
            content_id=memory_id,
            title=title,
            content=content,
            revision=revision,
            content_format=content_format,
        )

    def delete_memory(self, *, memory_id: str, revision: int) -> dict[str, Any]:
        return self._delete_content(kind="memory", content_id=memory_id, revision=revision)

    def _ensure_tag_name_available(
        self,
        *,
        profile_id: str,
        name: str,
        exclude_tag_id: str | None = None,
    ) -> None:
        normalized = name.strip().casefold()
        for tag in self.database.list_tags(profile_id=profile_id):
            if exclude_tag_id and tag["id"] == exclude_tag_id:
                continue
            if str(tag["name"]).strip().casefold() == normalized:
                raise TagConflict(f"标签 #{name.strip()} 已存在")

    def create_tag(self, *, name: str, color: str | None = None) -> dict[str, Any]:
        with self._mutex:
            profile = self.get_profile()
            clean_name = name.strip()
            self._ensure_tag_name_available(profile_id=profile["id"], name=clean_name)
            now = datetime.now(dt_timezone.utc).isoformat()
            return self.database.create_tag(
                profile_id=profile["id"],
                tag_id=str(uuid.uuid4()),
                name=clean_name,
                color=color,
                timestamp=now,
            )

    def list_tags(self) -> list[dict[str, Any]]:
        profile = self.get_profile()
        return self.database.list_tags(profile_id=profile["id"])

    def update_tag(
        self, *, tag_id: str, name: str, color: str | None = None
    ) -> dict[str, Any]:
        with self._mutex:
            profile = self.get_profile()
            clean_name = name.strip()
            self._ensure_tag_name_available(
                profile_id=profile["id"],
                name=clean_name,
                exclude_tag_id=tag_id,
            )
            now = datetime.now(dt_timezone.utc).isoformat()
            try:
                return self.database.update_tag(
                    profile_id=profile["id"],
                    tag_id=tag_id,
                    name=clean_name,
                    color=color,
                    timestamp=now,
                )
            except DatabaseContentNotFound as exc:
                raise ContentNotFound(str(exc)) from exc

    def delete_tag(self, *, tag_id: str) -> dict[str, Any]:
        with self._mutex:
            profile = self.get_profile()
            try:
                return self.database.delete_tag(profile_id=profile["id"], tag_id=tag_id)
            except DatabaseContentNotFound as exc:
                raise ContentNotFound(str(exc)) from exc

    def attach_memory_tag(self, *, memory_id: str, tag_id: str) -> None:
        profile = self.get_profile()
        now = datetime.now(dt_timezone.utc).isoformat()
        attached = self.database.attach_memory_tag(
            profile_id=profile["id"], memory_id=memory_id, tag_id=tag_id, timestamp=now
        )
        if not attached:
            raise ContentNotFound("记忆或标签不存在")

    def detach_memory_tag(self, *, memory_id: str, tag_id: str) -> None:
        profile = self.get_profile()
        self.database.detach_memory_tag(
            profile_id=profile["id"], memory_id=memory_id, tag_id=tag_id
        )

    def list_memory_tags(self, *, memory_id: str) -> list[dict[str, Any]]:
        profile = self.get_profile()
        return self.database.list_memory_tags(profile_id=profile["id"], memory_id=memory_id)

    def list_memory_tags_for_memories(
        self, *, memory_ids: list[str]
    ) -> dict[str, list[dict[str, Any]]]:
        profile = self.get_profile()
        return self.database.list_memory_tags_for_memories(
            profile_id=profile["id"], memory_ids=memory_ids
        )

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
        content_format: str | None = None,
    ) -> dict[str, Any]:
        with self._mutex:
            master_key = self.require_master_key()
            profile = self.get_profile()
            now = datetime.now(dt_timezone.utc).isoformat()
            method = getattr(self.database, f"update_{kind}")
            id_name = f"{kind}_id"
            payload = {"title": title, "content": content}
            if content_format is not None:
                payload["content_format"] = content_format
            try:
                return method(
                    master_key,
                    **{
                        id_name: content_id,
                        "profile_id": profile["id"],
                        "payload": payload,
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
