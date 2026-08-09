from __future__ import annotations

import hashlib
import heapq
import json
import os
import secrets
import shutil
import threading
import uuid
import zipfile
from collections import OrderedDict
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
from app.services.attachments import (
    AttachmentFileError,
    AttachmentStore,
    MAX_ATTACHMENT_BYTES,
    extract_attachment_time_metadata,
    fallback_attachment_timeline_metadata,
)
from app.services.large_files import LargeFileConflict, LargeFileError, LargeUploadManager
from app.services.media_previews import MediaPreviewError, MediaPreviewStore
from app.services.media_inventory import build_media_inventory, inspect_chunked_asset, verify_original_media_library
from app.services.media_backup import (
    MediaBackupError,
    inspect_media_backup_target,
    sync_media_backup,
    verify_media_backup,
)
from app.services.audio_compat import (
    AUDIO_PROBE_BYTES,
    AudioCompatibilityCancelled,
    AudioCompatibilityError,
    AudioCompatibilityManager,
    codec_label as audio_codec_label,
    codec_needs_compat,
    normalize_codec_id,
)
from app.services.backup import (
    BackupArtifact,
    BackupFileArtifact,
    LifeVaultPackage,
    LifeVaultPackageError,
    build_lifevault_backup,
    build_lifevault_backup_file,
    inspect_lifevault_file,
    inspect_lifevault_package,
    sha256_bytes,
    verify_lifevault_database,
    verify_lifevault_file,
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
MEDIA_BACKUP_TARGET_MAGIC = b"LGMBT001"
MEDIA_BACKUP_TARGET_AAD = b"lifegraph:v1:media-backup-target"
SECURITY_AUDIT_LIMIT = 50
MEDIA_STREAM_CACHE_MAX_BYTES = 64 * 1024 * 1024

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


class MaterialDuplicate(VaultError):
    pass


class VaultManager:
    def __init__(
        self,
        data_dir: Path,
        session_ttl_seconds: int = 1800,
        app_version: str = "0.0.9",
    ) -> None:
        self.data_dir = data_dir
        self.metadata_path = data_dir / "vault.json"
        self.database = Database(data_dir / "lifegraph.db")
        self.attachment_store = AttachmentStore(data_dir / "attachments")
        self.attachment_store.migrate_legacy_layout()
        # v0.0.9 large-media work uses a physically separate chunked store.
        # It is intentionally not part of the v0.0.8 attachment directory so
        # core .lifevault backups can later exclude huge media by policy.
        self.large_uploads = LargeUploadManager(data_dir / "media")
        self.preview_store = MediaPreviewStore(data_dir / "previews")
        self.audio_compat = AudioCompatibilityManager(data_dir / "audio_compat")
        self._audio_jobs: dict[str, dict[str, Any]] = {}
        self._audio_jobs_mutex = threading.RLock()
        self.media_backup_config_path = data_dir / ".media-backup-target.lgcfg"
        self._media_backup_job: dict[str, Any] | None = None
        self._media_backup_job_mutex = threading.RLock()
        self._media_chunk_cache: OrderedDict[tuple[str, int], bytes] = OrderedDict()
        self._media_chunk_cache_bytes = 0
        self._media_chunk_cache_mutex = threading.RLock()
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

    def _clear_media_chunk_cache(self) -> None:
        with self._media_chunk_cache_mutex:
            self._media_chunk_cache.clear()
            self._media_chunk_cache_bytes = 0

    def _read_original_media_chunk_cached(
        self, master_key: bytes, media_id: str, index: int
    ) -> bytes:
        if self._master_key != master_key:
            raise VaultError("数据仓库当前已锁定")
        key = (str(media_id), int(index))
        with self._media_chunk_cache_mutex:
            cached = self._media_chunk_cache.get(key)
            if cached is not None:
                self._media_chunk_cache.move_to_end(key)
                return cached
        plaintext = self.large_uploads.store.read_chunk(master_key, media_id, index)
        if len(plaintext) > MEDIA_STREAM_CACHE_MAX_BYTES:
            if self._master_key != master_key:
                raise VaultError("数据仓库当前已锁定")
            return plaintext
        with self._media_chunk_cache_mutex:
            if self._master_key != master_key:
                raise VaultError("数据仓库当前已锁定")
            previous = self._media_chunk_cache.pop(key, None)
            if previous is not None:
                self._media_chunk_cache_bytes -= len(previous)
            self._media_chunk_cache[key] = plaintext
            self._media_chunk_cache_bytes += len(plaintext)
            while self._media_chunk_cache and self._media_chunk_cache_bytes > MEDIA_STREAM_CACHE_MAX_BYTES:
                _, evicted = self._media_chunk_cache.popitem(last=False)
                self._media_chunk_cache_bytes -= len(evicted)
        return plaintext

    def _iter_original_media_range_cached(
        self,
        master_key: bytes,
        media_id: str,
        *,
        total_size: int,
        chunk_size: int,
        start: int,
        end_exclusive: int,
    ):
        first = start // chunk_size
        last = (end_exclusive - 1) // chunk_size
        for index in range(first, last + 1):
            plaintext = self._read_original_media_chunk_cached(master_key, media_id, index)
            expected = min(chunk_size, total_size - index * chunk_size)
            if len(plaintext) != expected:
                raise VaultError(f"媒体分块 {index} 明文大小校验失败")
            left = start - index * chunk_size if index == first else 0
            right = end_exclusive - index * chunk_size if index == last else len(plaintext)
            yield plaintext[left:right]

    def lock(self) -> None:
        with self._media_backup_job_mutex:
            if self._media_backup_job:
                cancel_event = self._media_backup_job.get("cancel_event")
                if isinstance(cancel_event, threading.Event):
                    cancel_event.set()
        with self._audio_jobs_mutex:
            for job in self._audio_jobs.values():
                cancel_event = job.get("cancel_event")
                if isinstance(cancel_event, threading.Event):
                    cancel_event.set()
        with self._mutex:
            self.sessions.revoke_all()
            self._clear_media_chunk_cache()
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
                    inspected = inspect_lifevault_file(path, verify_checksums=True)
                    manifest = inspected["manifest"]
                    producer = manifest.get("producer") or {}
                    entry.update(
                        {
                            "valid": True,
                            "created_at": manifest.get("created_at"),
                            "producer_version": producer.get("version"),
                            "schema_version": (manifest.get("repository") or {}).get(
                                "schema_version"
                            ),
                            "sha256": inspected["package_sha256"],
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
        elif latest.get("valid") is False:
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

    def _lightweight_auto_backup_history(
        self, policy: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Return file-stat-only backup history for hot-path reminders.

        This deliberately does not open or hash .lifevault payloads. Full package
        verification remains available through the backup settings and explicit
        verification actions.
        """
        if not self.auto_backup_dir.exists():
            return []
        entries: list[dict[str, Any]] = []
        verified_filename = str(policy.get("last_verified_filename") or "")
        verification_error = str(policy.get("last_verification_error") or "")
        last_filename = str(policy.get("last_filename") or "")
        last_success_at = policy.get("last_success_at")
        for path in self.auto_backup_dir.glob("*.lifevault"):
            try:
                if not path.is_file():
                    continue
                stat = path.stat()
            except OSError:
                continue
            valid: bool | None = None
            if path.name == verified_filename:
                valid = not bool(verification_error)
            entry: dict[str, Any] = {
                "filename": path.name,
                "size": stat.st_size,
                "modified_at": datetime.fromtimestamp(
                    stat.st_mtime, tz=dt_timezone.utc
                ).isoformat(),
                "valid": valid,
                "integrity_checked": valid is not None,
            }
            if path.name == last_filename and last_success_at:
                entry["created_at"] = last_success_at
            entries.append(entry)
        entries.sort(
            key=lambda item: item.get("created_at") or item["modified_at"],
            reverse=True,
        )
        return entries

    def get_auto_backup_reminder_status(self) -> dict[str, Any]:
        """Cheap status used on the home page without scanning backup payloads."""
        with self._mutex:
            self.require_master_key()
            metadata = self._read_metadata()
            policy = self._normalized_backup_policy(metadata)
            history = self._lightweight_auto_backup_history(policy)
            return {
                **policy,
                "next_due_at": self._backup_next_due_at(policy),
                "history_count": len(history),
                "history_size": sum(int(item.get("size") or 0) for item in history),
                "backup_directory": str(self.auto_backup_dir),
                "health": self._auto_backup_health(policy, history),
                "lightweight": True,
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
                "lightweight": False,
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
                timestamp = now.strftime("%Y%m%d-%H%M%S")
                filename = f"lifegraph-auto-{timestamp}.lifevault"
                path = self.auto_backup_dir / filename
                if path.exists():
                    path = self.auto_backup_dir / (
                        f"lifegraph-auto-{timestamp}-{secrets.token_hex(3)}.lifevault"
                    )
                artifact = build_lifevault_backup_file(
                    database=self.database,
                    metadata_path=self.metadata_path,
                    master_key=master_key,
                    app_version=self.app_version,
                    attachment_dir=self.attachment_store.root,
                    media_dir=self.large_uploads.store.root,
                    preview_dir=self.preview_store.root,
                    audio_compat_dir=self.audio_compat.store.root,
                    output_path=path,
                )
                # Re-open and decrypt the exact disk-backed package before recording success.
                verify_lifevault_file(path, master_key)
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
                    "sha256": artifact.sha256,
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
                integrity = verify_lifevault_file(path, master_key)
                manifest = integrity.get("manifest") or {}
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
                    "sha256": integrity.get("package_sha256"),
                    "created_at": manifest.get("created_at"),
                    "schema_version": integrity.get("schema_version"),
                    "sqlite_quick_check": integrity.get("sqlite_quick_check"),
                    "foreign_key_errors": integrity.get("foreign_key_errors"),
                    "encrypted_records_verified": integrity.get(
                        "encrypted_records_verified"
                    ),
                    "attachment_files_verified": integrity.get(
                        "attachment_files_verified", 0
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
        """Best-effort due check used after successful API activity.

        The overwhelmingly common not-due path must remain metadata-only. Older
        versions called ``create_automatic_backup`` for every request, whose
        not-due return value built a fully verified backup history and repeatedly
        re-hashed every .lifevault file. That made login and material browsing scale
        with backup size rather than with the requested data.
        """
        if not self.is_unlocked or self._restore_in_progress:
            return None
        try:
            with self._mutex:
                self.require_master_key()
                metadata = self._read_metadata()
                policy = self._normalized_backup_policy(metadata)
                if not policy["enabled"]:
                    return None
                now = datetime.now(dt_timezone.utc)
                last_success = self._parse_utc_timestamp(policy.get("last_success_at"))
                if last_success and now < last_success + self._backup_interval(policy["frequency"]):
                    return None
                last_attempt = self._parse_utc_timestamp(policy.get("last_attempt_at"))
                if policy.get("last_error") and last_attempt and now < last_attempt + timedelta(hours=1):
                    return None
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

    def _read_media_backup_target(self, master_key: bytes) -> str | None:
        path = self.media_backup_config_path
        if not path.is_file():
            return None
        try:
            payload = path.read_bytes()
            if len(payload) <= len(MEDIA_BACKUP_TARGET_MAGIC) + 12 or not payload.startswith(MEDIA_BACKUP_TARGET_MAGIC):
                raise VaultError("大型媒体备份目录配置损坏")
            offset = len(MEDIA_BACKUP_TARGET_MAGIC)
            nonce = payload[offset:offset + 12]
            ciphertext = payload[offset + 12:]
            plaintext = decrypt_bytes(master_key, nonce, ciphertext, aad=MEDIA_BACKUP_TARGET_AAD)
            value = plaintext.decode("utf-8").strip()
            return value or None
        except (OSError, UnicodeDecodeError, CryptoError) as exc:
            raise VaultError("大型媒体备份目录配置无法读取") from exc

    def _write_media_backup_target(self, master_key: bytes, target: Path) -> None:
        nonce, ciphertext = encrypt_bytes(
            master_key,
            str(target).encode("utf-8"),
            aad=MEDIA_BACKUP_TARGET_AAD,
        )
        temp = self.media_backup_config_path.with_suffix(".tmp")
        try:
            temp.write_bytes(MEDIA_BACKUP_TARGET_MAGIC + nonce + ciphertext)
            os.replace(temp, self.media_backup_config_path)
        except OSError as exc:
            temp.unlink(missing_ok=True)
            raise VaultError(f"无法保存大型媒体备份目录：{exc}") from exc

    def _resolve_media_backup_target(self, raw_target: str) -> Path:
        value = os.path.expandvars(str(raw_target or "").strip())
        if not value:
            raise VaultError("请先填写大型媒体备份目录")
        target = Path(value).expanduser().resolve(strict=False)
        data_root = self.data_dir.resolve(strict=False)
        try:
            common = Path(os.path.commonpath([str(target), str(data_root)]))
        except ValueError:
            common = None
        if common == data_root:
            raise VaultError("大型媒体备份目录不能放在当前 data 目录内部")
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise VaultError(f"大型媒体备份目录无法创建或访问：{exc}") from exc
        if not target.is_dir():
            raise VaultError("大型媒体备份目标必须是目录")
        return target

    def _media_backup_public_job(self) -> dict[str, Any] | None:
        with self._media_backup_job_mutex:
            job = self._media_backup_job
            if not job:
                return None
            return {
                key: value
                for key, value in job.items()
                if key not in {"cancel_event", "thread"}
            }

    def media_backup_job_status(self) -> dict[str, Any]:
        self.require_master_key()
        return self._media_backup_public_job() or {"state": "idle"}

    def start_media_backup_job(self, *, target_path: str | None = None, mode: str = "sync") -> dict[str, Any]:
        if mode not in {"sync", "verify", "source-verify"}:
            raise VaultError("大型媒体备份任务类型无效")
        with self._mutex:
            master_key = self.require_master_key()
            configured = self._read_media_backup_target(master_key)
            target = None if mode == "source-verify" else self._resolve_media_backup_target(target_path or configured or "")
            media = self._media_library_status_for_key(master_key, include_items=True)
            if int(media.get("offline") or 0) or int(media.get("incomplete") or 0) or int(media.get("invalid") or 0):
                action = "校验" if mode == "source-verify" else "备份"
                raise VaultError(f"大型媒体库存在离线、不完整或异常项目，请先处理后再{action}")
            original_media = list(media.get("original_media") or [])
            if target is not None:
                self._write_media_backup_target(master_key, target)

        with self._media_backup_job_mutex:
            if self._media_backup_job and self._media_backup_job.get("state") in {"running", "cancelling"}:
                raise VaultError("已有大型媒体备份任务正在执行")
            cancel_event = threading.Event()
            now = datetime.now(dt_timezone.utc).isoformat()
            self._media_backup_job = {
                "state": "running",
                "mode": mode,
                "target_path": str(target) if target is not None else None,
                "started_at": now,
                "finished_at": None,
                "error": None,
                "total_files": (
                    sum(int(item.get("chunk_count") or 0) for item in original_media)
                    if mode == "source-verify"
                    else sum(int(item.get("chunk_count") or 0) + 1 for item in original_media)
                ),
                "completed_files": 0,
                "total_bytes": sum(int(item.get("size_bytes") or 0) for item in original_media) if mode == "source-verify" else 0,
                "completed_bytes": 0,
                "copied_files": 0,
                "copied_bytes": 0,
                "skipped_files": 0,
                "verified_files": 0,
                "verified_media": 0,
                "current_file": "",
                "cancel_event": cancel_event,
            }

            def update_progress(values: dict[str, Any]) -> None:
                with self._media_backup_job_mutex:
                    if not self._media_backup_job:
                        return
                    for key in (
                        "total_files", "completed_files", "total_bytes", "completed_bytes",
                        "copied_files", "copied_bytes", "skipped_files", "verified_files", "verified_media", "current_file",
                    ):
                        if key in values:
                            self._media_backup_job[key] = values[key]

            def worker() -> None:
                try:
                    if mode == "sync":
                        assert target is not None
                        result = sync_media_backup(
                            source_root=self.large_uploads.store.root,
                            target_root=target,
                            original_media=original_media,
                            progress=update_progress,
                            cancel_event=cancel_event,
                        )
                    elif mode == "verify":
                        assert target is not None
                        result = verify_media_backup(
                            target_root=target,
                            original_media=original_media,
                            progress=update_progress,
                            cancel_event=cancel_event,
                        )
                    else:
                        result = verify_original_media_library(
                            store=self.large_uploads.store,
                            master_key=master_key,
                            original_media=original_media,
                            progress=update_progress,
                            cancel_event=cancel_event,
                        )
                    with self._media_backup_job_mutex:
                        if self._media_backup_job:
                            self._media_backup_job.update(result)
                            self._media_backup_job["state"] = "completed"
                            self._media_backup_job["finished_at"] = datetime.now(dt_timezone.utc).isoformat()
                except Exception as exc:
                    with self._media_backup_job_mutex:
                        if self._media_backup_job:
                            self._media_backup_job["state"] = "cancelled" if cancel_event.is_set() else "failed"
                            self._media_backup_job["error"] = str(exc)
                            self._media_backup_job["finished_at"] = datetime.now(dt_timezone.utc).isoformat()

            thread = threading.Thread(target=worker, name=f"lifegraph-media-backup-{mode}", daemon=True)
            self._media_backup_job["thread"] = thread
            thread.start()
            return self._media_backup_public_job() or {"state": "running"}

    def cancel_media_backup_job(self) -> dict[str, Any]:
        self.require_master_key()
        with self._media_backup_job_mutex:
            if not self._media_backup_job or self._media_backup_job.get("state") not in {"running", "cancelling"}:
                return self._media_backup_public_job() or {"state": "idle"}
            cancel_event = self._media_backup_job.get("cancel_event")
            if isinstance(cancel_event, threading.Event):
                cancel_event.set()
            self._media_backup_job["state"] = "cancelling"
            return self._media_backup_public_job() or {"state": "cancelling"}

    def _media_library_status_for_key(
        self, master_key: bytes, *, include_items: bool = False
    ) -> dict[str, Any]:
        records = self.database.list_all_attachments(master_key)
        inventory = build_media_inventory(
            records=records,
            master_key=master_key,
            original_store=self.large_uploads.store,
            audio_store=self.audio_compat.store,
            check_chunks=True,
        )
        summary = dict(inventory.get("summary") or {})
        originals = list(inventory.get("original_media") or [])
        result = {
            "backup_scope": "core+external-media",
            "core_backup_format": "lifevault-v3",
            "media_root": "data/media",
            "audio_compat_root": "data/audio_compat",
            "previews_policy": "embedded-in-core",
            "audio_compat_policy": "regenerable-excluded",
            "full_backup_ready": (
                int(summary.get("offline") or 0) == 0
                and int(summary.get("incomplete") or 0) == 0
                and int(summary.get("invalid") or 0) == 0
            ),
            **summary,
            "checked_at": datetime.now(dt_timezone.utc).isoformat(),
        }
        try:
            configured_target = self._read_media_backup_target(master_key)
            if configured_target:
                result["external_backup"] = inspect_media_backup_target(Path(configured_target), originals)
            else:
                result["external_backup"] = {
                    "configured": False,
                    "state": "unconfigured",
                    "current": False,
                    "message": "尚未设置大型媒体独立备份目录",
                }
        except VaultError as exc:
            result["external_backup"] = {
                "configured": False,
                "state": "invalid",
                "current": False,
                "message": str(exc),
            }
        result["backup_job"] = self._media_backup_public_job() or {"state": "idle"}
        if include_items:
            result["original_media"] = originals
            result["derivatives"] = list(inventory.get("derivatives") or [])
        return result

    def media_library_status(self, *, include_items: bool = False) -> dict[str, Any]:
        """Return structural status for external originals and derived audio."""
        with self._mutex:
            return self._media_library_status_for_key(
                self.require_master_key(), include_items=include_items
            )

    def check_backup_integrity(self) -> dict[str, Any]:
        """Verify core repository plus structural availability of external media."""
        with self._mutex:
            master_key = self.require_master_key()
            if not self.metadata_path.exists() or not self.database.path.exists():
                raise VaultError("加密仓库文件不完整")
            self._read_metadata()
            import tempfile

            with tempfile.TemporaryDirectory(prefix="lifegraph-check-") as temporary_dir:
                snapshot_path = Path(temporary_dir) / "lifegraph.db"
                self.database.create_consistent_snapshot(snapshot_path)
                try:
                    result = self.database.verify_encrypted_snapshot(snapshot_path, master_key)
                except DatabaseIntegrityError as exc:
                    raise VaultError(str(exc)) from exc

            attachment_records = self.database.list_all_attachments(master_key)
            blob_records = [
                record for record in attachment_records
                if str(record.get("storage_kind") or "blob-v1") == "blob-v1"
            ]
            preview_verified = 0
            preview_missing = 0
            preview_invalid = 0
            for record in attachment_records:
                if str(record.get("storage_kind") or "blob-v1") == "blob-v1":
                    try:
                        content = self.attachment_store.read(master_key, record["id"], record["file_nonce"])
                    except AttachmentFileError as exc:
                        raise VaultError(f"附件完整性检查失败：{exc}") from exc
                    if len(content) != int(record.get("size_bytes") or -1):
                        raise VaultError("附件完整性检查失败：附件大小不一致")
                    if hashlib.sha256(content).hexdigest() != record.get("sha256"):
                        raise VaultError("附件完整性检查失败：附件摘要不一致")
                nonce_text = str(record.get("preview_nonce") or "").strip()
                if nonce_text and record.get("preview_media_type"):
                    preview_path = self.preview_store.path_for(str(record["id"]))
                    if not preview_path.is_file():
                        preview_missing += 1
                    else:
                        try:
                            preview = self.preview_store.read(master_key, record["id"], b64d(nonce_text))
                            if len(preview) != int(record.get("preview_size_bytes") or -1):
                                preview_invalid += 1
                            elif hashlib.sha256(preview).hexdigest() != str(record.get("preview_sha256") or ""):
                                preview_invalid += 1
                            else:
                                preview_verified += 1
                        except (MediaPreviewError, CryptoError, ValueError, OSError):
                            # Preview files are regenerable derivatives. Report them
                            # as degraded instead of blocking the core backup path.
                            preview_invalid += 1

            media = self.media_library_status(include_items=False)
            return {
                "ready": True,
                **result,
                "backup_format": "lifevault-v3",
                "backup_scope": "core",
                "attachment_files_verified": len(blob_records),
                "preview_files_verified": preview_verified,
                "preview_files_missing": preview_missing,
                "preview_files_invalid": preview_invalid,
                "external_media_records": int(media.get("original_records") or 0),
                "external_media_bytes": int(media.get("original_bytes") or 0),
                "external_media_online": int(media.get("online") or 0),
                "external_media_offline": int(media.get("offline") or 0),
                "external_media_incomplete": int(media.get("incomplete") or 0),
                "external_media_invalid": int(media.get("invalid") or 0),
                "audio_compat_records": int(media.get("audio_compat_records") or 0),
                "full_backup_ready": bool(media.get("full_backup_ready")),
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
                    attachment_dir=self.attachment_store.root,
                    media_dir=self.large_uploads.store.root,
                    preview_dir=self.preview_store.root,
                    audio_compat_dir=self.audio_compat.store.root,
                )
            except (DatabaseIntegrityError, OSError, ValueError, json.JSONDecodeError) as exc:
                raise VaultError(f"备份导出失败：{exc}") from exc

    def export_lifevault_file(self, *, app_version: str) -> BackupFileArtifact:
        """Export to a temporary disk-backed package for streaming HTTP download."""
        with self._mutex:
            master_key = self.require_master_key()
            if not self.metadata_path.exists() or not self.database.path.exists():
                raise VaultError("加密仓库文件不完整")
            export_dir = self.data_dir / ".exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(dt_timezone.utc).strftime("%Y%m%d-%H%M%S")
            path = export_dir / f"lifegraph-export-{timestamp}-{secrets.token_hex(4)}.lifevault"
            try:
                artifact = build_lifevault_backup_file(
                    database=self.database,
                    metadata_path=self.metadata_path,
                    master_key=master_key,
                    app_version=app_version,
                    attachment_dir=self.attachment_store.root,
                    media_dir=self.large_uploads.store.root,
                    preview_dir=self.preview_store.root,
                    audio_compat_dir=self.audio_compat.store.root,
                    output_path=path,
                )
                verify_lifevault_file(path, master_key)
                return artifact
            except (DatabaseIntegrityError, LifeVaultPackageError, OSError, ValueError, json.JSONDecodeError) as exc:
                path.unlink(missing_ok=True)
                raise VaultError(f"备份导出失败：{exc}") from exc

    @staticmethod
    def _external_master_key_from_metadata_bytes(
        metadata_bytes: bytes,
        *,
        credential_method: Literal["pin", "recovery"],
        credential_secret: str,
    ) -> bytes:
        try:
            metadata = json.loads(metadata_bytes.decode("utf-8"))
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
    def _external_master_key(
        package: LifeVaultPackage,
        *,
        credential_method: Literal["pin", "recovery"],
        credential_secret: str,
    ) -> bytes:
        return VaultManager._external_master_key_from_metadata_bytes(
            package.metadata_bytes,
            credential_method=credential_method,
            credential_secret=credential_secret,
        )

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
            "attachment_files_verified": integrity.get("attachment_files_verified", 0),
            "external_media_records": integrity.get("external_media_records", 0),
            "external_media_bytes": integrity.get("external_media_bytes", 0),
            "external_media_online_at_backup": integrity.get("external_media_online_at_backup", 0),
            "external_media_offline_at_backup": integrity.get("external_media_offline_at_backup", 0),
            "external_media_incomplete_at_backup": integrity.get("external_media_incomplete_at_backup", 0),
            "external_media_invalid_at_backup": integrity.get("external_media_invalid_at_backup", 0),
            "preview_files_verified": integrity.get("preview_files_verified", 0),
            "audio_compat_records": integrity.get("audio_compat_records", 0),
            "backup_scope": (package.manifest.get("repository") or {}).get("backup_scope", "legacy"),
            "record_counts": integrity.get("record_counts", {}),
            "package_sha256": package.package_sha256,
            "credential_method": credential_method,
        }

    @staticmethod
    def _import_report_values(
        *,
        manifest: dict[str, Any],
        package_sha256: str,
        integrity: dict[str, Any],
        credential_method: str,
    ) -> dict[str, Any]:
        producer = manifest.get("producer") or {}
        return {
            "valid": True,
            "format": manifest.get("format"),
            "format_version": manifest.get("format_version"),
            "created_at": manifest.get("created_at"),
            "producer_version": producer.get("version"),
            "schema_version": integrity.get("source_schema_version", integrity["schema_version"]),
            "compatible_schema_version": integrity["schema_version"],
            "encrypted_records_verified": integrity["encrypted_records_verified"],
            "attachment_files_verified": integrity.get("attachment_files_verified", 0),
            "external_media_records": integrity.get("external_media_records", 0),
            "external_media_bytes": integrity.get("external_media_bytes", 0),
            "external_media_online_at_backup": integrity.get("external_media_online_at_backup", 0),
            "external_media_offline_at_backup": integrity.get("external_media_offline_at_backup", 0),
            "external_media_incomplete_at_backup": integrity.get("external_media_incomplete_at_backup", 0),
            "external_media_invalid_at_backup": integrity.get("external_media_invalid_at_backup", 0),
            "preview_files_verified": integrity.get("preview_files_verified", 0),
            "audio_compat_records": integrity.get("audio_compat_records", 0),
            "backup_scope": (manifest.get("repository") or {}).get("backup_scope", "legacy"),
            "record_counts": integrity.get("record_counts", {}),
            "package_sha256": package_sha256,
            "credential_method": credential_method,
        }

    def inspect_lifevault_import_file(
        self,
        *,
        path: Path,
        credential_method: Literal["pin", "recovery"],
        credential_secret: str,
    ) -> dict[str, Any]:
        """Run a full disk-backed restore rehearsal with bounded memory."""
        with self._mutex:
            self.require_master_key()
            try:
                inspected = inspect_lifevault_file(path, verify_checksums=True)
                imported_key = self._external_master_key_from_metadata_bytes(
                    inspected["metadata_bytes"],
                    credential_method=credential_method,
                    credential_secret=credential_secret,
                )
                integrity = verify_lifevault_file(path, imported_key)
            except (LifeVaultPackageError, DatabaseIntegrityError) as exc:
                raise VaultError(f"备份包验证失败：{exc}") from exc
            return self._import_report_values(
                manifest=inspected["manifest"],
                package_sha256=inspected["package_sha256"],
                integrity=integrity,
                credential_method=credential_method,
            )

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
                    attachment_dir=self.attachment_store.root,
                    media_dir=self.large_uploads.store.root,
                    preview_dir=self.preview_store.root,
                    audio_compat_dir=self.audio_compat.store.root,
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
            incoming_attachments = self.data_dir / ".restore-attachments"
            previous_attachments = self.data_dir / ".restore-attachments-previous"
            incoming_previews = self.data_dir / ".restore-previews"
            previous_previews = self.data_dir / ".restore-previews-previous"
            shutil.rmtree(incoming_attachments, ignore_errors=True)
            shutil.rmtree(previous_attachments, ignore_errors=True)
            shutil.rmtree(incoming_previews, ignore_errors=True)
            shutil.rmtree(previous_previews, ignore_errors=True)
            incoming_store = AttachmentStore(incoming_attachments)
            incoming_preview_store = MediaPreviewStore(incoming_previews)
            incoming_attachments.mkdir(parents=True, exist_ok=True)
            incoming_previews.mkdir(parents=True, exist_ok=True)
            for attachment_id, encrypted in package.attachment_files.items():
                incoming_store.write_encrypted_bytes(attachment_id, encrypted)
            for attachment_id, encrypted in package.preview_files.items():
                self._atomic_write(incoming_preview_store.path_for(attachment_id), encrypted)

            self._atomic_write(incoming_metadata, package.metadata_bytes)
            self._atomic_write(incoming_database, package.database_bytes)
            # Verify that the exact candidate bytes reached disk before replacement.
            if (
                incoming_metadata.read_bytes() != package.metadata_bytes
                or incoming_database.read_bytes() != package.database_bytes
                or {
                    path.stem: path.read_bytes()
                    for path in incoming_attachments.rglob("*.lgatt")
                } != package.attachment_files
                or {
                    path.stem: path.read_bytes()
                    for path in incoming_previews.rglob("*.lgpreview")
                } != package.preview_files
            ):
                incoming_metadata.unlink(missing_ok=True)
                incoming_database.unlink(missing_ok=True)
                shutil.rmtree(incoming_attachments, ignore_errors=True)
                shutil.rmtree(incoming_previews, ignore_errors=True)
                raise VaultError("恢复候选文件写入校验失败")

            self._restore_in_progress = True
            had_live_attachments = self.attachment_store.root.exists()
            had_live_previews = self.preview_store.root.exists()
            try:
                if had_live_attachments:
                    os.replace(self.attachment_store.root, previous_attachments)
                if had_live_previews:
                    os.replace(self.preview_store.root, previous_previews)
                os.replace(incoming_attachments, self.attachment_store.root)
                os.replace(incoming_previews, self.preview_store.root)
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
                shutil.rmtree(previous_attachments, ignore_errors=True)
                shutil.rmtree(previous_previews, ignore_errors=True)
            except Exception as exc:
                # Roll back from the already verified pre-restore package.
                try:
                    shutil.rmtree(self.attachment_store.root, ignore_errors=True)
                    shutil.rmtree(self.preview_store.root, ignore_errors=True)
                    if had_live_attachments and previous_attachments.exists():
                        os.replace(previous_attachments, self.attachment_store.root)
                    if had_live_previews and previous_previews.exists():
                        os.replace(previous_previews, self.preview_store.root)
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
                shutil.rmtree(incoming_attachments, ignore_errors=True)
                shutil.rmtree(previous_attachments, ignore_errors=True)
                shutil.rmtree(incoming_previews, ignore_errors=True)
                shutil.rmtree(previous_previews, ignore_errors=True)
                self._restore_in_progress = False

            # A restored repository must always be unlocked again with its own credential.
            self.sessions.revoke_all()
            self._clear_media_chunk_cache()
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

    def restore_lifevault_file(
        self,
        *,
        path: Path,
        credential_method: Literal["pin", "recovery"],
        credential_secret: str,
        confirm: str,
        app_version: str,
    ) -> dict[str, Any]:
        """Replace the live repository from a disk-backed package using bounded memory."""
        if confirm != "REPLACE_REPOSITORY":
            raise VaultError("恢复确认口令无效")
        with self._mutex:
            current_master_key = self.require_master_key()
            try:
                inspected = inspect_lifevault_file(path, verify_checksums=True)
                imported_key = self._external_master_key_from_metadata_bytes(
                    inspected["metadata_bytes"],
                    credential_method=credential_method,
                    credential_secret=credential_secret,
                )
                source_integrity = verify_lifevault_file(path, imported_key)
            except (LifeVaultPackageError, DatabaseIntegrityError) as exc:
                raise VaultError(f"备份包验证失败：{exc}") from exc

            recovery_dir = self.data_dir / "recovery"
            timestamp = datetime.now(dt_timezone.utc).strftime("%Y%m%d-%H%M%S")
            rescue_path = recovery_dir / f"lifegraph-before-restore-{timestamp}.lifevault"
            if rescue_path.exists():
                rescue_path = recovery_dir / (
                    f"lifegraph-before-restore-{timestamp}-{secrets.token_hex(3)}.lifevault"
                )
            try:
                build_lifevault_backup_file(
                    database=self.database,
                    metadata_path=self.metadata_path,
                    master_key=current_master_key,
                    app_version=app_version,
                    attachment_dir=self.attachment_store.root,
                    media_dir=self.large_uploads.store.root,
                    preview_dir=self.preview_store.root,
                    audio_compat_dir=self.audio_compat.store.root,
                    output_path=rescue_path,
                )
                verify_lifevault_file(rescue_path, current_master_key)
            except (DatabaseIntegrityError, LifeVaultPackageError, OSError, ValueError, json.JSONDecodeError) as exc:
                raise VaultError(f"无法创建恢复前安全备份：{exc}") from exc

            incoming_metadata = self.data_dir / ".restore-vault.json"
            incoming_database = self.data_dir / ".restore-lifegraph.db"
            incoming_attachments = self.data_dir / ".restore-attachments"
            previous_attachments = self.data_dir / ".restore-attachments-previous"
            incoming_previews = self.data_dir / ".restore-previews"
            previous_previews = self.data_dir / ".restore-previews-previous"
            shutil.rmtree(incoming_attachments, ignore_errors=True)
            shutil.rmtree(previous_attachments, ignore_errors=True)
            shutil.rmtree(incoming_previews, ignore_errors=True)
            shutil.rmtree(previous_previews, ignore_errors=True)
            incoming_attachments.mkdir(parents=True, exist_ok=True)
            incoming_previews.mkdir(parents=True, exist_ok=True)
            incoming_store = AttachmentStore(incoming_attachments)
            incoming_preview_store = MediaPreviewStore(incoming_previews)
            entry_map = {
                entry.get("path"): entry
                for entry in inspected["manifest"].get("files", [])
                if isinstance(entry, dict)
            }

            try:
                with zipfile.ZipFile(path) as archive:
                    metadata_bytes = archive.read("repository/vault.json")
                    self._atomic_write(incoming_metadata, metadata_bytes)
                    db_entry = entry_map.get("repository/lifegraph.db") or {}
                    db_digest = hashlib.sha256()
                    db_size = 0
                    with archive.open("repository/lifegraph.db") as source, incoming_database.open("wb") as target:
                        while chunk := source.read(1024 * 1024):
                            target.write(chunk)
                            db_digest.update(chunk)
                            db_size += len(chunk)
                        target.flush()
                        os.fsync(target.fileno())
                    if db_size != int(db_entry.get("size", -1)) or db_digest.hexdigest() != db_entry.get("sha256"):
                        raise VaultError("恢复候选数据库写入校验失败")

                    for archive_name in archive.namelist():
                        if archive_name.startswith("repository/attachments/") and archive_name.endswith(".lgatt"):
                            attachment_id = archive_name.removeprefix("repository/attachments/").removesuffix(".lgatt")
                            entry = entry_map.get(archive_name) or {}
                            with archive.open(archive_name) as source:
                                size, digest = incoming_store.write_encrypted_stream(attachment_id, source)
                            if size != int(entry.get("size", -1)) or digest != entry.get("sha256"):
                                raise VaultError(f"恢复候选附件 {attachment_id} 写入校验失败")
                        elif archive_name.startswith("repository/previews/") and archive_name.endswith(".lgpreview"):
                            attachment_id = archive_name.removeprefix("repository/previews/").removesuffix(".lgpreview")
                            entry = entry_map.get(archive_name) or {}
                            content = archive.read(archive_name)
                            if len(content) != int(entry.get("size", -1)) or hashlib.sha256(content).hexdigest() != entry.get("sha256"):
                                raise VaultError(f"恢复候选视频封面 {attachment_id} 写入校验失败")
                            preview_path = incoming_preview_store.path_for(attachment_id)
                            self._atomic_write(preview_path, content)
            except Exception:
                incoming_metadata.unlink(missing_ok=True)
                incoming_database.unlink(missing_ok=True)
                shutil.rmtree(incoming_attachments, ignore_errors=True)
                shutil.rmtree(incoming_previews, ignore_errors=True)
                raise

            self._restore_in_progress = True
            had_live_attachments = self.attachment_store.root.exists()
            had_live_previews = self.preview_store.root.exists()
            try:
                if had_live_attachments:
                    os.replace(self.attachment_store.root, previous_attachments)
                if had_live_previews:
                    os.replace(self.preview_store.root, previous_previews)
                os.replace(incoming_attachments, self.attachment_store.root)
                os.replace(incoming_previews, self.preview_store.root)
                for suffix in ("-wal", "-shm"):
                    self.database.path.with_name(self.database.path.name + suffix).unlink(missing_ok=True)
                os.replace(incoming_metadata, self.metadata_path)
                os.replace(incoming_database, self.database.path)
                self.database.initialize_schema()
                restored_integrity = self.database.verify_encrypted_snapshot(self.database.path, imported_key)
                restored_metadata = self._read_metadata()
                self._append_security_audit(restored_metadata, "repository_restored")
                self._write_metadata(restored_metadata)
                shutil.rmtree(previous_attachments, ignore_errors=True)
                shutil.rmtree(previous_previews, ignore_errors=True)
            except Exception as exc:
                try:
                    shutil.rmtree(self.attachment_store.root, ignore_errors=True)
                    shutil.rmtree(self.preview_store.root, ignore_errors=True)
                    if had_live_attachments and previous_attachments.exists():
                        os.replace(previous_attachments, self.attachment_store.root)
                    if had_live_previews and previous_previews.exists():
                        os.replace(previous_previews, self.preview_store.root)
                    rollback_metadata = self.data_dir / ".rollback-vault.json"
                    rollback_database = self.data_dir / ".rollback-lifegraph.db"
                    with zipfile.ZipFile(rescue_path) as archive:
                        self._atomic_write(rollback_metadata, archive.read("repository/vault.json"))
                        with archive.open("repository/lifegraph.db") as source, rollback_database.open("wb") as target:
                            shutil.copyfileobj(source, target, length=1024 * 1024)
                            target.flush()
                            os.fsync(target.fileno())
                    os.replace(rollback_metadata, self.metadata_path)
                    os.replace(rollback_database, self.database.path)
                    for suffix in ("-wal", "-shm"):
                        self.database.path.with_name(self.database.path.name + suffix).unlink(missing_ok=True)
                    self.database.initialize_schema()
                    self.database.verify_encrypted_snapshot(self.database.path, current_master_key)
                    self._master_key = current_master_key
                except Exception as rollback_exc:  # pragma: no cover - catastrophic I/O
                    self._master_key = None
                    self.sessions.revoke_all()
                    raise VaultError(f"仓库恢复失败且自动回滚失败：{rollback_exc}") from exc
                raise VaultError(f"仓库恢复失败，已自动回滚：{exc}") from exc
            finally:
                incoming_metadata.unlink(missing_ok=True)
                incoming_database.unlink(missing_ok=True)
                shutil.rmtree(incoming_attachments, ignore_errors=True)
                shutil.rmtree(previous_attachments, ignore_errors=True)
                shutil.rmtree(incoming_previews, ignore_errors=True)
                shutil.rmtree(previous_previews, ignore_errors=True)
                self._restore_in_progress = False

            self.sessions.revoke_all()
            self._clear_media_chunk_cache()
            self._master_key = None
            report = self._import_report_values(
                manifest=inspected["manifest"],
                package_sha256=inspected["package_sha256"],
                integrity=source_integrity,
                credential_method=credential_method,
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

    def move_content_period(
        self,
        *,
        kind: str,
        content_id: str,
        anchor_date: str,
        time_scope: str,
        period_key: str,
        revision: int,
    ) -> dict[str, Any]:
        with self._mutex:
            self.require_master_key()
            profile = self.get_profile()
            now = datetime.now(dt_timezone.utc).isoformat()
            try:
                return self.database.move_content_period(
                    kind=kind,
                    content_id=content_id,
                    profile_id=profile["id"],
                    anchor_date=anchor_date,
                    time_scope=time_scope,
                    period_key=period_key,
                    expected_revision=revision,
                    timestamp=now,
                )
            except DatabaseContentNotFound as exc:
                raise ContentNotFound(str(exc)) from exc
            except DatabaseRevisionConflict as exc:
                raise ContentRevisionConflict(str(exc)) from exc

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

    def browse_content(
        self,
        *,
        kinds: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        sort: str = "date_desc",
        limit: int = 100,
    ) -> dict[str, Any]:
        master_key = self.require_master_key()
        profile = self.get_profile()
        return self.database.browse_content(
            master_key,
            profile_id=profile["id"],
            kinds=kinds,
            date_from=date_from,
            date_to=date_to,
            sort=sort,
            limit=limit,
        )

    def search_content(
        self,
        *,
        query: str = "",
        kinds: list[str] | None = None,
        tag_ids: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        sort: str = "date_desc",
        limit: int = 100,
    ) -> dict[str, Any]:
        master_key = self.require_master_key()
        profile = self.get_profile()
        return self.database.search_content(
            master_key,
            profile_id=profile["id"],
            query=query,
            kinds=kinds,
            tag_ids=tag_ids,
            date_from=date_from,
            date_to=date_to,
            sort=sort,
            limit=limit,
        )

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

    def get_content_tag_map(
        self,
        *,
        tag_ids: list[str],
        start_date: str,
        end_date: str,
        kinds: list[str] | None = None,
    ) -> dict[str, Any]:
        self.require_master_key()
        profile = self.get_profile()
        return self.database.get_content_tag_map(
            profile_id=profile["id"],
            tag_ids=tag_ids,
            start_date=start_date,
            end_date=end_date,
            kinds=kinds,
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

    def attach_content_tag(self, *, kind: str, content_id: str, tag_id: str) -> None:
        profile = self.get_profile()
        now = datetime.now(dt_timezone.utc).isoformat()
        attached = self.database.attach_content_tag(
            profile_id=profile["id"],
            kind=kind,
            content_id=content_id,
            tag_id=tag_id,
            timestamp=now,
        )
        if not attached:
            raise ContentNotFound("内容或标签不存在")

    def detach_content_tag(self, *, kind: str, content_id: str, tag_id: str) -> None:
        profile = self.get_profile()
        self.database.detach_content_tag(
            profile_id=profile["id"], kind=kind, content_id=content_id, tag_id=tag_id
        )

    def replace_content_tags(
        self, *, kind: str, content_id: str, tag_ids: list[str]
    ) -> list[dict[str, Any]]:
        profile = self.get_profile()
        now = datetime.now(dt_timezone.utc).isoformat()
        try:
            return self.database.replace_content_tags(
                profile_id=profile["id"],
                kind=kind,
                content_id=content_id,
                tag_ids=tag_ids,
                timestamp=now,
            )
        except DatabaseContentNotFound as exc:
            raise ContentNotFound(str(exc)) from exc

    def bulk_update_content_tags(
        self,
        *,
        items: list[dict[str, str]],
        tag_ids: list[str],
        operation: str,
    ) -> list[dict[str, Any]]:
        profile = self.get_profile()
        now = datetime.now(dt_timezone.utc).isoformat()
        try:
            return self.database.bulk_update_content_tags(
                profile_id=profile["id"],
                items=items,
                tag_ids=tag_ids,
                operation=operation,
                timestamp=now,
            )
        except DatabaseContentNotFound as exc:
            raise ContentNotFound(str(exc)) from exc

    def list_content_tags(self, *, kind: str, content_id: str) -> list[dict[str, Any]]:
        profile = self.get_profile()
        return self.database.list_content_tags(
            profile_id=profile["id"], kind=kind, content_id=content_id
        )

    def list_content_tags_for_items(
        self, *, kind: str, content_ids: list[str]
    ) -> dict[str, list[dict[str, Any]]]:
        profile = self.get_profile()
        return self.database.list_content_tags_for_items(
            profile_id=profile["id"], kind=kind, content_ids=content_ids
        )

    # Memory-specific wrappers are retained for the v0.0.6 search/filter APIs.
    def attach_memory_tag(self, *, memory_id: str, tag_id: str) -> None:
        self.attach_content_tag(kind="memory", content_id=memory_id, tag_id=tag_id)

    def detach_memory_tag(self, *, memory_id: str, tag_id: str) -> None:
        self.detach_content_tag(kind="memory", content_id=memory_id, tag_id=tag_id)

    def list_memory_tags(self, *, memory_id: str) -> list[dict[str, Any]]:
        return self.list_content_tags(kind="memory", content_id=memory_id)

    def list_memory_tags_for_memories(
        self, *, memory_ids: list[str]
    ) -> dict[str, list[dict[str, Any]]]:
        return self.list_content_tags_for_items(kind="memory", content_ids=memory_ids)

    def _public_attachment(self, value: dict[str, Any]) -> dict[str, Any]:
        public = {
            key: item
            for key, item in value.items()
            if key not in {
                "file_nonce", "profile_id", "preview_nonce", "preview_sha256",
                "audio_compat_media_id", "audio_compat_sha256",
            }
        }
        public["is_independent"] = not bool(value.get("kind") and value.get("content_id"))
        is_large = str(value.get("storage_kind") or "blob-v1") == "chunked-v1"
        public["is_large"] = is_large
        try:
            public["has_preview"] = bool(
                value.get("preview_nonce")
                and value.get("preview_media_type")
                and self.preview_store.path_for(str(value.get("id") or "")).is_file()
            )
        except (MediaPreviewError, OSError):
            public["has_preview"] = False
        compat_id = str(value.get("audio_compat_media_id") or "").strip()
        public["has_audio_compat"] = bool(
            compat_id and value.get("audio_compat_media_type") and self.audio_compat.asset_exists(compat_id)
        )
        if is_large:
            media_id = str(value.get("media_id") or "").strip()
            status = inspect_chunked_asset(
                self.large_uploads.store,
                self.require_master_key(),
                media_id=media_id,
                expected_size=int(value.get("size_bytes") or 0),
                expected_sha256=str(value.get("sha256") or ""),
                expected_chunk_size=int(value.get("chunk_size") or 0),
                expected_chunk_count=int(value.get("chunk_count") or 0),
                check_chunks=False,
            )
            public["media_state"] = str(status.get("state") or "invalid")
            public["media_available"] = public["media_state"] == "online"
        else:
            public["media_state"] = "embedded"
            public["media_available"] = True
        return public

    @staticmethod
    def _normalize_video_metadata(
        media_type: str | None,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        clean_type = str(media_type or "").lower()
        if not clean_type.startswith("video/") and not metadata:
            return {}
        raw = dict(metadata or {})
        result: dict[str, Any] = {}
        try:
            duration = float(raw.get("duration_seconds"))
            if 0 <= duration <= 366 * 24 * 3600:
                result["duration_seconds"] = round(duration, 3)
        except (TypeError, ValueError):
            pass
        for source_key, target_key in (("video_width", "video_width"), ("video_height", "video_height")):
            try:
                value = int(raw.get(source_key))
                if 1 <= value <= 32768:
                    result[target_key] = value
            except (TypeError, ValueError):
                pass
        for source_key, target_key, limit in (
            ("video_codec", "video_codec", 80),
            ("audio_codec", "audio_codec", 80),
            ("audio_codec_id", "audio_codec_id", 80),
            ("audio_channel_layout", "audio_channel_layout", 80),
            ("metadata_source", "video_metadata_source", 80),
            ("poster_source", "video_poster_source", 80),
        ):
            value = str(raw.get(source_key) or "").strip()
            if value:
                result[target_key] = value[:limit]
        for source_key, target_key, low, high in (
            ("audio_channels", "audio_channels", 1, 64),
            ("audio_sample_rate", "audio_sample_rate", 1000, 768000),
        ):
            try:
                value = int(raw.get(source_key))
                if low <= value <= high:
                    result[target_key] = value
            except (TypeError, ValueError):
                pass
        return result

    def _write_video_preview(
        self,
        *,
        master_key: bytes,
        attachment_id: str,
        preview_content: bytes | None,
        preview_media_type: str | None,
    ) -> dict[str, Any]:
        if not preview_content:
            return {}
        nonce, digest, clean_type = self.preview_store.write(
            master_key,
            attachment_id,
            preview_content,
            media_type=preview_media_type,
        )
        return {
            "preview_nonce": b64e(nonce),
            "preview_sha256": digest,
            "preview_media_type": clean_type,
            "preview_size_bytes": len(preview_content),
        }

    def create_attachment(
        self,
        *,
        kind: str,
        content_id: str,
        filename: str,
        media_type: str | None,
        content: bytes,
        file_last_modified_ms: int | None = None,
        video_metadata: dict[str, Any] | None = None,
        preview_content: bytes | None = None,
        preview_media_type: str | None = None,
    ) -> dict[str, Any]:
        with self._mutex:
            master_key = self.require_master_key()
            profile = self.get_profile()
            if kind not in {"event", "memory", "plan"}:
                raise VaultError("不支持的内容类型")
            clean_name = Path(filename or "").name.strip()
            if not clean_name:
                clean_name = "未命名附件"
            if len(clean_name) > 240:
                raise VaultError("附件文件名过长")
            if not content:
                raise VaultError("附件文件为空")
            if len(content) > MAX_ATTACHMENT_BYTES:
                raise VaultError("单个附件不能超过 50 MB")
            if not self.database.content_exists(
                profile_id=profile["id"],
                kind=kind,
                content_id=content_id,
                include_deleted=False,
            ):
                raise ContentNotFound("内容不存在或已经被删除")

            attachment_id = str(uuid.uuid4())
            now = datetime.now(dt_timezone.utc).isoformat()
            timezone_name = str(profile.get("timezone") or "UTC")
            try:
                source = self.database.get_content_reference(
                    master_key,
                    profile_id=profile["id"],
                    kind=kind,
                    content_id=content_id,
                    include_deleted=False,
                )
                time_metadata = extract_attachment_time_metadata(
                    content,
                    filename=clean_name,
                    media_type=media_type,
                    file_last_modified_ms=file_last_modified_ms,
                    timezone_name=timezone_name,
                )
                if not time_metadata.get("timeline_date"):
                    time_metadata.update(
                        fallback_attachment_timeline_metadata(
                            source_time_scope=str(source.get("time_scope") or ""),
                            source_period_key=str(source.get("period_key") or ""),
                            attachment_created_at=now,
                            timezone_name=timezone_name,
                        )
                    )
                file_nonce, sha256 = self.attachment_store.write(
                    master_key, attachment_id, content
                )
                preview_metadata = self._write_video_preview(
                    master_key=master_key,
                    attachment_id=attachment_id,
                    preview_content=preview_content,
                    preview_media_type=preview_media_type,
                )
                value = self.database.create_attachment(
                    master_key,
                    attachment_id=attachment_id,
                    profile_id=profile["id"],
                    kind=kind,
                    content_id=content_id,
                    file_nonce=file_nonce,
                    metadata={
                        "filename": clean_name,
                        "media_type": (media_type or "application/octet-stream")[:200],
                        "size_bytes": len(content),
                        "sha256": sha256,
                        **self._normalize_video_metadata(media_type, video_metadata),
                        **preview_metadata,
                        **time_metadata,
                    },
                    timestamp=now,
                )
            except DatabaseContentNotFound as exc:
                self.attachment_store.delete(attachment_id)
                self.preview_store.delete(attachment_id)
                raise ContentNotFound(str(exc)) from exc
            except (AttachmentFileError, MediaPreviewError) as exc:
                self.attachment_store.delete(attachment_id)
                self.preview_store.delete(attachment_id)
                raise VaultError(str(exc)) from exc
            except Exception:
                self.attachment_store.delete(attachment_id)
                self.preview_store.delete(attachment_id)
                raise
            return self._public_attachment(value)

    def import_material(
        self,
        *,
        filename: str,
        media_type: str | None,
        content: bytes,
        file_last_modified_ms: int | None = None,
        source_relative_path: str | None = None,
        source_directory_name: str | None = None,
        reject_duplicate: bool = False,
        video_metadata: dict[str, Any] | None = None,
        preview_content: bytes | None = None,
        preview_media_type: str | None = None,
    ) -> dict[str, Any]:
        """Import one encrypted material without requiring a parent content item.

        Directory imports may preserve a browser-provided relative source path and
        request duplicate rejection. The path is metadata only; LifeGraph never
        reads or writes the original source path on the user's filesystem.
        """
        with self._mutex:
            master_key = self.require_master_key()
            profile = self.get_profile()
            clean_name = Path(filename or "").name.strip() or "未命名资料"
            if len(clean_name) > 240:
                raise VaultError("资料文件名过长")
            if not content:
                raise VaultError("资料文件为空")
            if len(content) > MAX_ATTACHMENT_BYTES:
                raise VaultError("单个资料不能超过 50 MB")

            incoming_sha256 = hashlib.sha256(content).hexdigest()
            if reject_duplicate:
                duplicate = self.find_material_duplicates([incoming_sha256]).get("matches", {}).get(incoming_sha256, [])
                if duplicate:
                    raise MaterialDuplicate("相同文件已经存在于人生资料库中")

            clean_relative_path = str(source_relative_path or "").replace("\\", "/").strip().lstrip("/")
            if clean_relative_path:
                parts = [part for part in clean_relative_path.split("/") if part not in {"", ".", ".."}]
                clean_relative_path = "/".join(parts)[:1000]
            clean_directory_name = Path(str(source_directory_name or "").strip()).name[:120]

            attachment_id = str(uuid.uuid4())
            now = datetime.now(dt_timezone.utc).isoformat()
            timezone_name = str(profile.get("timezone") or "UTC")
            time_metadata = extract_attachment_time_metadata(
                content,
                filename=clean_name,
                media_type=media_type,
                file_last_modified_ms=file_last_modified_ms,
                timezone_name=timezone_name,
            )
            if not time_metadata.get("timeline_date"):
                time_metadata.update(
                    fallback_attachment_timeline_metadata(
                        source_time_scope=None,
                        source_period_key=None,
                        attachment_created_at=now,
                        timezone_name=timezone_name,
                    )
                )
            try:
                file_nonce, sha256 = self.attachment_store.write(
                    master_key, attachment_id, content
                )
                preview_metadata = self._write_video_preview(
                    master_key=master_key,
                    attachment_id=attachment_id,
                    preview_content=preview_content,
                    preview_media_type=preview_media_type,
                )
                value = self.database.create_attachment(
                    master_key,
                    attachment_id=attachment_id,
                    profile_id=profile["id"],
                    kind=None,
                    content_id=None,
                    file_nonce=file_nonce,
                    metadata={
                        "filename": clean_name,
                        "media_type": (media_type or "application/octet-stream")[:200],
                        "size_bytes": len(content),
                        "sha256": sha256,
                        **self._normalize_video_metadata(media_type, video_metadata),
                        **preview_metadata,
                        "material_origin": "directory_import" if clean_relative_path else "independent",
                        **({"source_relative_path": clean_relative_path} if clean_relative_path else {}),
                        **({"source_directory_name": clean_directory_name} if clean_directory_name else {}),
                        **time_metadata,
                    },
                    timestamp=now,
                )
            except (AttachmentFileError, MediaPreviewError) as exc:
                self.attachment_store.delete(attachment_id)
                self.preview_store.delete(attachment_id)
                raise VaultError(str(exc)) from exc
            except Exception:
                self.attachment_store.delete(attachment_id)
                self.preview_store.delete(attachment_id)
                raise
            return self._public_attachment(value)

    def create_large_material_upload(
        self,
        *,
        filename: str,
        media_type: str | None,
        size_bytes: int,
        chunk_size: int | None = None,
        file_last_modified_ms: int | None = None,
        source_relative_path: str | None = None,
        source_directory_name: str | None = None,
        quick_fingerprint: str | None = None,
        reject_duplicate: bool = False,
    ) -> dict[str, Any]:
        """Create one persistent resumable upload session for independent material.

        Large files cannot be hashed in full in the browser without defeating the
        bounded-memory upload path.  When duplicate rejection is requested, use a
        lightweight sampled fingerprint first and retain a filename/size/mtime
        fallback for media created before sampled fingerprints existed.  Finalize
        still performs the authoritative whole-file SHA-256 check.
        """
        master_key = self.require_master_key()
        if reject_duplicate:
            candidates = self.find_large_material_duplicate_candidates(
                filename=filename,
                size_bytes=size_bytes,
                file_last_modified_ms=file_last_modified_ms,
                quick_fingerprint=quick_fingerprint,
            )
            if candidates:
                raise MaterialDuplicate("相同文件已经存在于人生资料库中")
        try:
            return self.large_uploads.create_session(
                master_key,
                filename=filename,
                media_type=media_type,
                size_bytes=size_bytes,
                chunk_size=chunk_size,
                file_last_modified_ms=file_last_modified_ms,
                source_relative_path=source_relative_path,
                source_directory_name=source_directory_name,
                quick_fingerprint=quick_fingerprint,
                reject_duplicate=reject_duplicate,
            )
        except LargeFileError as exc:
            raise VaultError(str(exc)) from exc

    def find_large_material_duplicate_candidates(
        self,
        *,
        filename: str,
        size_bytes: int,
        file_last_modified_ms: int | None,
        quick_fingerprint: str | None,
    ) -> list[dict[str, Any]]:
        """Find likely duplicate large media without reading multi-GB payloads."""
        master_key = self.require_master_key()
        profile = self.get_profile()
        clean_name = Path(filename or "").name.strip()
        size_value = int(size_bytes)
        mtime_value = int(file_last_modified_ms) if file_last_modified_ms is not None else None
        quick_value = str(quick_fingerprint or "").strip().lower()
        matches: list[dict[str, Any]] = []
        for value in self.database.list_all_attachments(master_key, profile_id=profile["id"]):
            if int(value.get("size_bytes") or 0) != size_value:
                continue
            stored_quick = str(value.get("quick_fingerprint") or "").strip().lower()
            sampled_match = bool(quick_value and stored_quick and quick_value == stored_quick)
            legacy_match = (
                not stored_quick
                and clean_name == str(value.get("filename") or "")
                and mtime_value is not None
                and int(value.get("file_last_modified_ms") or -1) == mtime_value
            )
            if not (sampled_match or legacy_match):
                continue
            matches.append(
                {
                    "id": value.get("id"),
                    "filename": value.get("filename") or "未命名资料",
                    "storage_kind": value.get("storage_kind") or "blob-v1",
                }
            )
        return matches

    def get_large_material_upload(self, *, session_id: str) -> dict[str, Any]:
        master_key = self.require_master_key()
        try:
            return self.large_uploads.status(master_key, session_id)
        except LargeFileError as exc:
            raise ContentNotFound(str(exc)) from exc

    def update_large_material_video_metadata(
        self,
        *,
        session_id: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        master_key = self.require_master_key()
        try:
            session = self.large_uploads.get_session(master_key, session_id)
            normalized = self._normalize_video_metadata(
                str(session.get("media_type") or "application/octet-stream"),
                metadata,
            )
            return self.large_uploads.update_video_metadata(master_key, session_id, normalized)
        except LargeFileError as exc:
            raise ContentNotFound(str(exc)) from exc

    def put_large_material_preview(
        self,
        *,
        session_id: str,
        content: bytes,
        media_type: str | None,
    ) -> dict[str, Any]:
        master_key = self.require_master_key()
        try:
            return self.large_uploads.put_preview(
                master_key,
                session_id,
                content,
                media_type=media_type,
            )
        except LargeFileError as exc:
            raise VaultError(str(exc)) from exc

    def large_upload_maintenance_status(self, *, stale_days: int = 30) -> dict[str, Any]:
        master_key = self.require_master_key()
        try:
            return self.large_uploads.maintenance_status(master_key, stale_days=stale_days)
        except LargeFileError as exc:
            raise VaultError(str(exc)) from exc

    def cleanup_stale_large_uploads(self, *, stale_days: int = 30) -> dict[str, Any]:
        master_key = self.require_master_key()
        try:
            return self.large_uploads.cleanup_stale_sessions(master_key, stale_days=stale_days)
        except LargeFileError as exc:
            raise VaultError(str(exc)) from exc

    def put_large_material_chunk(
        self,
        *,
        session_id: str,
        index: int,
        content: bytes,
    ) -> dict[str, Any]:
        master_key = self.require_master_key()
        try:
            return self.large_uploads.put_chunk(master_key, session_id, index, content)
        except LargeFileConflict as exc:
            raise MaterialDuplicate(str(exc)) from exc
        except LargeFileError as exc:
            raise VaultError(str(exc)) from exc

    def cancel_large_material_upload(self, *, session_id: str) -> dict[str, Any]:
        master_key = self.require_master_key()
        try:
            session = self.large_uploads.get_session(master_key, session_id)
        except LargeFileError as exc:
            raise ContentNotFound(str(exc)) from exc
        self.large_uploads.cancel(session_id)
        return {
            "session_id": session_id,
            "media_id": session.get("media_id"),
            "cancelled": True,
        }

    def finalize_large_material_upload(self, *, session_id: str) -> dict[str, Any]:
        """Finalize encrypted chunks and register the material in schema v8.

        The expensive whole-file SHA-256 pass is performed against decrypted chunks
        without joining the file in memory. Only after that succeeds is the media
        directory committed and the encrypted material metadata inserted.
        """
        master_key = self.require_master_key()
        try:
            manifest = self.large_uploads.finalize(master_key, session_id)
        except LargeFileConflict as exc:
            raise MaterialDuplicate(str(exc)) from exc
        except LargeFileError as exc:
            raise VaultError(str(exc)) from exc

        media_id = str(manifest["media_id"])
        try:
            if bool(manifest.get("reject_duplicate")):
                duplicates = self.find_material_duplicates([str(manifest["sha256"])])
                if duplicates.get("matched_hashes"):
                    raise MaterialDuplicate("相同文件已经存在于人生资料库中")

            with self._mutex:
                profile = self.get_profile()
                attachment_id = str(uuid.uuid4())
                now = datetime.now(dt_timezone.utc).isoformat()
                timezone_name = str(profile.get("timezone") or "UTC")
                timeline = extract_attachment_time_metadata(
                    b"",
                    filename=str(manifest.get("filename") or "未命名大型资料"),
                    media_type=str(manifest.get("media_type") or "application/octet-stream"),
                    file_last_modified_ms=manifest.get("file_last_modified_ms"),
                    timezone_name=timezone_name,
                )
                if not timeline.get("timeline_date"):
                    timeline.update(
                        fallback_attachment_timeline_metadata(
                            source_time_scope=None,
                            source_period_key=None,
                            attachment_created_at=str(manifest.get("created_at") or now),
                            timezone_name=timezone_name,
                        )
                    )
                relative_path = str(manifest.get("source_relative_path") or "").strip()
                directory_name = str(manifest.get("source_directory_name") or "").strip()
                preview_metadata: dict[str, Any] = {}
                try:
                    pending_preview = self.large_uploads.read_committed_preview(master_key, media_id)
                except LargeFileError:
                    # A derivative thumbnail must never invalidate a successfully
                    # uploaded multi-GB original. Keep the media and simply fall
                    # back to the generic video card when preview recovery fails.
                    pending_preview = None
                    self.large_uploads.delete_committed_preview(media_id)
                if pending_preview:
                    preview_type, preview_content = pending_preview
                    preview_metadata = self._write_video_preview(
                        master_key=master_key,
                        attachment_id=attachment_id,
                        preview_content=preview_content,
                        preview_media_type=preview_type,
                    )
                value = self.database.create_attachment(
                    master_key,
                    attachment_id=attachment_id,
                    profile_id=profile["id"],
                    kind=None,
                    content_id=None,
                    storage_kind="chunked-v1",
                    file_nonce=None,
                    media_id=media_id,
                    metadata={
                        "filename": str(manifest.get("filename") or "未命名大型资料"),
                        "media_type": str(manifest.get("media_type") or "application/octet-stream"),
                        "size_bytes": int(manifest["size_bytes"]),
                        "sha256": str(manifest["sha256"]),
                        "chunk_size": int(manifest["chunk_size"]),
                        "chunk_count": int(manifest["chunk_count"]),
                        "chunked_format_version": int(manifest.get("format_version") or 1),
                        "file_last_modified_ms": manifest.get("file_last_modified_ms"),
                        "quick_fingerprint": manifest.get("quick_fingerprint"),
                        **dict(manifest.get("video_metadata") or {}),
                        **preview_metadata,
                        "material_origin": "directory_import" if relative_path else "independent",
                        **({"source_relative_path": relative_path} if relative_path else {}),
                        **({"source_directory_name": directory_name} if directory_name else {}),
                        "time_metadata_checked": True,
                        **timeline,
                    },
                    timestamp=now,
                )
                self.large_uploads.delete_committed_preview(media_id)
                return self._public_attachment(value)
        except Exception:
            try:
                self.preview_store.delete(locals().get("attachment_id", ""))
            except Exception:
                pass
            self.large_uploads.store.delete(media_id)
            raise

    def find_material_duplicates(self, sha256_values: list[str]) -> dict[str, Any]:
        master_key = self.require_master_key()
        profile = self.get_profile()
        wanted = {str(value or "").strip().lower() for value in sha256_values}
        wanted = {value for value in wanted if len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)}
        matches: dict[str, list[dict[str, Any]]] = {value: [] for value in wanted}
        if not wanted:
            return {"matches": {}, "matched_hashes": 0}
        for value in self.database.list_all_attachments(master_key, profile_id=profile["id"]):
            digest = str(value.get("sha256") or "").strip().lower()
            if digest not in wanted:
                continue
            matches[digest].append(
                {
                    "id": value.get("id"),
                    "filename": value.get("filename") or "未命名资料",
                    "is_independent": not bool(value.get("kind") and value.get("content_id")),
                }
            )
        compact = {key: values for key, values in matches.items() if values}
        return {"matches": compact, "matched_hashes": len(compact)}

    def list_attachment_counts_for_items(
        self, *, kind: str, content_ids: list[str]
    ) -> dict[str, int]:
        self.require_master_key()
        profile = self.get_profile()
        return self.database.list_attachment_counts_for_items(
            profile_id=profile["id"], kind=kind, content_ids=content_ids
        )

    @staticmethod
    def _attachment_metadata_payload(value: dict[str, Any]) -> dict[str, Any]:
        private_keys = {
            "id",
            "profile_id",
            "kind",
            "content_id",
            "file_nonce",
            "storage_kind",
            "media_id",
            "created_at",
            "updated_at",
        }
        return {key: item for key, item in value.items() if key not in private_keys}

    def _attachment_context_fallback_metadata(
        self,
        *,
        master_key: bytes,
        profile_id: str,
        timezone_name: str,
        value: dict[str, Any],
    ) -> dict[str, str]:
        source = None
        if value.get("kind") and value.get("content_id"):
            try:
                source = self.database.get_content_reference(
                    master_key,
                    profile_id=profile_id,
                    kind=str(value.get("kind")),
                    content_id=str(value.get("content_id")),
                    include_deleted=True,
                )
            except DatabaseContentNotFound:
                source = None
        return fallback_attachment_timeline_metadata(
            source_time_scope=str(source.get("time_scope") or "") if source else None,
            source_period_key=str(source.get("period_key") or "") if source else None,
            attachment_created_at=str(value.get("created_at") or ""),
            timezone_name=timezone_name,
        )

    def _ensure_attachment_time_metadata(
        self,
        *,
        master_key: bytes,
        profile_id: str,
        timezone_name: str,
        value: dict[str, Any],
    ) -> dict[str, Any]:
        metadata = self._attachment_metadata_payload(value)
        if value.get("time_metadata_checked") is True and value.get("timeline_date"):
            return value

        # Historical records may already be marked as checked even though no
        # reliable file time was found. Apply the contextual fallback without
        # decrypting the blob again.
        if value.get("time_metadata_checked") is True:
            fallback = self._attachment_context_fallback_metadata(
                master_key=master_key,
                profile_id=profile_id,
                timezone_name=timezone_name,
                value=value,
            )
            if not fallback:
                return value
            metadata.update(fallback)
            return self.database.update_attachment_metadata(
                master_key,
                profile_id=profile_id,
                attachment_id=value["id"],
                metadata=metadata,
                timestamp=datetime.now(dt_timezone.utc).isoformat(),
            )

        if str(value.get("storage_kind") or "blob-v1") == "chunked-v1":
            metadata["time_metadata_checked"] = True
            if not metadata.get("timeline_date"):
                metadata.update(
                    self._attachment_context_fallback_metadata(
                        master_key=master_key,
                        profile_id=profile_id,
                        timezone_name=timezone_name,
                        value=value,
                    )
                )
            return self.database.update_attachment_metadata(
                master_key,
                profile_id=profile_id,
                attachment_id=value["id"],
                metadata=metadata,
                timestamp=datetime.now(dt_timezone.utc).isoformat(),
            )

        try:
            content = self.attachment_store.read(master_key, value["id"], value["file_nonce"])
            extracted = extract_attachment_time_metadata(
                content,
                filename=str(value.get("filename") or ""),
                media_type=str(value.get("media_type") or "application/octet-stream"),
                file_last_modified_ms=None,
                timezone_name=timezone_name,
            )
            # Preserve any capture metadata already written by v0.0.8.3 while
            # adding the independent timeline relationship.
            for key in ("captured_at", "captured_date", "capture_source"):
                if value.get(key) and not extracted.get(key):
                    extracted[key] = value[key]
            if not extracted.get("timeline_at") and value.get("captured_at"):
                extracted["timeline_at"] = value["captured_at"]
                extracted["timeline_date"] = value.get("captured_date")
                extracted["timeline_time_source"] = f"exif:{value.get('capture_source') or 'capture'}"
            metadata.update(extracted)
        except AttachmentFileError:
            metadata["time_metadata_checked"] = True

        if not metadata.get("timeline_date"):
            metadata.update(
                self._attachment_context_fallback_metadata(
                    master_key=master_key,
                    profile_id=profile_id,
                    timezone_name=timezone_name,
                    value=value,
                )
            )
        return self.database.update_attachment_metadata(
            master_key,
            profile_id=profile_id,
            attachment_id=value["id"],
            metadata=metadata,
            timestamp=datetime.now(dt_timezone.utc).isoformat(),
        )

    def assign_attachment_timeline_fallback(self, *, attachment_id: str) -> dict[str, Any]:
        """Repair an undated attachment using parent day or attachment-added time."""
        with self._mutex:
            master_key = self.require_master_key()
            profile = self.get_profile()
            try:
                value = self.database.get_attachment(
                    master_key,
                    profile_id=profile["id"],
                    attachment_id=attachment_id,
                )
            except DatabaseContentNotFound as exc:
                raise ContentNotFound(str(exc)) from exc
            if value.get("timeline_date"):
                return self._public_attachment(value)
            fallback = self._attachment_context_fallback_metadata(
                master_key=master_key,
                profile_id=profile["id"],
                timezone_name=str(profile.get("timezone") or "UTC"),
                value=value,
            )
            if not fallback:
                raise VaultError("无法从来源内容日期或附件添加时间确定归属日期")
            metadata = self._attachment_metadata_payload(value)
            metadata.update(fallback)
            metadata["time_metadata_checked"] = True
            metadata["timeline_fallback_manual"] = True
            updated = self.database.update_attachment_metadata(
                master_key,
                profile_id=profile["id"],
                attachment_id=attachment_id,
                metadata=metadata,
                timestamp=datetime.now(dt_timezone.utc).isoformat(),
            )
            return self._public_attachment(updated)


    def list_attachments(self, *, kind: str, content_id: str) -> list[dict[str, Any]]:
        master_key = self.require_master_key()
        profile = self.get_profile()
        try:
            values = self.database.list_attachments(
                master_key,
                profile_id=profile["id"],
                kind=kind,
                content_id=content_id,
            )
        except DatabaseContentNotFound as exc:
            raise ContentNotFound(str(exc)) from exc
        values = [
            self._ensure_attachment_time_metadata(
                master_key=master_key,
                profile_id=profile["id"],
                timezone_name=str(profile.get("timezone") or "UTC"),
                value=value,
            )
            for value in values
        ]
        return [self._public_attachment(value) for value in values]

    @staticmethod
    def _attachment_matches_period(value: dict[str, Any], scope: str, period_key: str) -> bool:
        timeline_date = str(value.get("timeline_date") or "")
        if not timeline_date:
            return False
        if scope == "day":
            return timeline_date == period_key
        if scope == "month":
            return timeline_date[:7] == period_key
        if scope == "year":
            return timeline_date[:4] == period_key
        return False

    def list_materials_for_period(self, *, scope: str, period_key: str) -> list[dict[str, Any]]:
        master_key = self.require_master_key()
        profile = self.get_profile()
        values = self.database.list_all_attachments(master_key, profile_id=profile["id"])
        materials: list[dict[str, Any]] = []
        for raw_value in values:
            value = self._ensure_attachment_time_metadata(
                master_key=master_key,
                profile_id=profile["id"],
                timezone_name=str(profile.get("timezone") or "UTC"),
                value=raw_value,
            )
            if not self._attachment_matches_period(value, scope, period_key):
                continue
            source = None
            if value.get("kind") and value.get("content_id"):
                try:
                    source = self.database.get_content_reference(
                        master_key,
                        profile_id=profile["id"],
                        kind=str(value["kind"]),
                        content_id=str(value["content_id"]),
                        include_deleted=False,
                    )
                except DatabaseContentNotFound:
                    continue
            public = self._public_attachment(value)
            public["source_content"] = (
                {
                    "kind": source["kind"],
                    "id": source["id"],
                    "title": source["title"],
                    "time_scope": source["time_scope"],
                    "period_key": source["period_key"],
                }
                if source
                else None
            )
            materials.append(public)
        materials.sort(
            key=lambda item: (str(item.get("timeline_at") or ""), str(item.get("filename") or "")),
            reverse=True,
        )
        return materials

    @staticmethod
    def _material_category(value: dict[str, Any]) -> str:
        media_type = str(value.get("media_type") or "").lower()
        filename = str(value.get("filename") or "").lower()
        suffix = Path(filename).suffix.lower()
        if media_type.startswith("image/") or suffix in {
            ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".heif",
        }:
            return "image"
        if media_type.startswith("video/") or suffix in {
            ".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi", ".wmv", ".flv", ".mpeg", ".mpg", ".ts", ".mts", ".m2ts",
        }:
            return "video"
        if (
            media_type.startswith("text/")
            or media_type in {"application/pdf", "application/rtf"}
            or "officedocument" in media_type
            or "msword" in media_type
            or "ms-excel" in media_type
            or "ms-powerpoint" in media_type
            or "opendocument" in media_type
            or suffix in {
                ".pdf", ".txt", ".md", ".rtf", ".doc", ".docx", ".xls", ".xlsx",
                ".ppt", ".pptx", ".odt", ".ods", ".odp", ".csv",
            }
        ):
            return "document"
        return "other"

    def browse_materials(
        self,
        *,
        query: str = "",
        categories: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        sort: str = "timeline_desc",
        limit: int = 48,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Browse encrypted material metadata with bounded-memory pagination.

        Because filename/timeline metadata is encrypted at rest, broad filters still
        decrypt candidate metadata rows. The iterator and top-K selection avoid
        materializing the entire decrypted library in memory, while the API returns
        only the requested page.
        """
        master_key = self.require_master_key()
        profile = self.get_profile()
        allowed_categories = {"image", "video", "document", "other"}
        category_set = {value for value in (categories or ["image", "video", "document", "other"]) if value in allowed_categories}
        if not category_set:
            category_set = set(allowed_categories)
        needle = query.strip().casefold()
        counts = {"image": 0, "video": 0, "document": 0, "other": 0, "undated": 0}
        total = 0
        page_cap = max(0, int(offset)) + max(1, int(limit))

        def matched_items():
            nonlocal total
            for raw_value in self.database.iter_all_attachments(master_key, profile_id=profile["id"]):
                value = self._ensure_attachment_time_metadata(
                    master_key=master_key,
                    profile_id=profile["id"],
                    timezone_name=str(profile.get("timezone") or "UTC"),
                    value=raw_value,
                )
                source = None
                if value.get("kind") and value.get("content_id"):
                    try:
                        source = self.database.get_content_reference(
                            master_key,
                            profile_id=profile["id"],
                            kind=str(value["kind"]),
                            content_id=str(value["content_id"]),
                            include_deleted=False,
                        )
                    except DatabaseContentNotFound:
                        continue

                category = self._material_category(value)
                timeline_date = str(value.get("timeline_date") or "")
                if category not in category_set:
                    continue
                if date_from and (not timeline_date or timeline_date < date_from):
                    continue
                if date_to and (not timeline_date or timeline_date > date_to):
                    continue
                if needle:
                    haystack = "\n".join(
                        [
                            str(value.get("filename") or ""),
                            str(value.get("media_type") or ""),
                            str(source.get("title") or "") if source else "独立资料",
                        ]
                    ).casefold()
                    if needle not in haystack:
                        continue

                public = self._public_attachment(value)
                public["category"] = category
                public["source_content"] = (
                    {
                        "kind": source["kind"],
                        "id": source["id"],
                        "title": source["title"],
                        "time_scope": source["time_scope"],
                        "period_key": source["period_key"],
                    }
                    if source
                    else None
                )
                counts[category] += 1
                if not timeline_date:
                    counts["undated"] += 1
                total += 1
                yield public

        if sort == "timeline_asc":
            key = lambda item: (
                not bool(item.get("timeline_at")),
                str(item.get("timeline_at") or "9999-12-31T23:59:59"),
                str(item.get("filename") or ""),
                str(item.get("id") or ""),
            )
            selected = heapq.nsmallest(page_cap, matched_items(), key=key)
        elif sort == "added_desc":
            key = lambda item: (str(item.get("created_at") or ""), str(item.get("filename") or ""), str(item.get("id") or ""))
            selected = heapq.nlargest(page_cap, matched_items(), key=key)
        else:
            key = lambda item: (
                bool(item.get("timeline_at")),
                str(item.get("timeline_at") or ""),
                str(item.get("filename") or ""),
                str(item.get("id") or ""),
            )
            selected = heapq.nlargest(page_cap, matched_items(), key=key)

        page = selected[offset : offset + limit]
        next_offset = offset + len(page)
        return {
            "items": page,
            "total": total,
            "offset": offset,
            "limit": limit,
            "next_offset": next_offset if next_offset < total else None,
            "has_more": next_offset < total,
            "counts": counts,
        }

    def delete_independent_material(self, *, attachment_id: str) -> dict[str, Any]:
        with self._mutex:
            master_key = self.require_master_key()
            profile = self.get_profile()
            try:
                value = self.database.get_attachment(
                    master_key,
                    profile_id=profile["id"],
                    attachment_id=attachment_id,
                )
                result = self.database.delete_independent_material(
                    profile_id=profile["id"], attachment_id=attachment_id
                )
            except DatabaseContentNotFound as exc:
                raise ContentNotFound(str(exc)) from exc
            storage_kind = str(result.pop("storage_kind", "blob-v1"))
            media_id = result.pop("media_id", None)
            compat_media_id = str(value.get("audio_compat_media_id") or "").strip()
            self._cancel_audio_compat_job(attachment_id)
            if storage_kind == "chunked-v1" and media_id:
                self.large_uploads.store.delete(str(media_id))
            else:
                self.attachment_store.delete(attachment_id)
            self.preview_store.delete(attachment_id)
            self.audio_compat.delete(compat_media_id)
            return result

    def read_attachment_preview(self, *, attachment_id: str) -> tuple[dict[str, Any], bytes]:
        with self._mutex:
            master_key = self.require_master_key()
            profile = self.get_profile()
            try:
                value = self.database.get_attachment(
                    master_key,
                    profile_id=profile["id"],
                    attachment_id=attachment_id,
                )
            except DatabaseContentNotFound as exc:
                raise ContentNotFound(str(exc)) from exc
            nonce_text = str(value.get("preview_nonce") or "").strip()
            if not nonce_text or not value.get("preview_media_type"):
                raise ContentNotFound("该视频暂无封面")
            try:
                content = self.preview_store.read(master_key, attachment_id, b64d(nonce_text))
            except (MediaPreviewError, CryptoError, ValueError) as exc:
                raise VaultError(str(exc)) from exc
            if len(content) != int(value.get("preview_size_bytes") or -1):
                raise VaultError("视频封面大小校验失败")
            if hashlib.sha256(content).hexdigest() != str(value.get("preview_sha256") or ""):
                raise VaultError("视频封面完整性校验失败")
            return self._public_attachment(value), content

    def get_attachment_stream_metadata(self, *, attachment_id: str) -> dict[str, Any]:
        """Return verified metadata needed to serve an attachment over HTTP Range."""
        with self._mutex:
            master_key = self.require_master_key()
            profile = self.get_profile()
            try:
                value = self.database.get_attachment(
                    master_key,
                    profile_id=profile["id"],
                    attachment_id=attachment_id,
                )
            except DatabaseContentNotFound as exc:
                raise ContentNotFound(str(exc)) from exc

            total_size = int(value.get("size_bytes") or 0)
            if total_size <= 0:
                raise VaultError("附件大小信息无效")
            if str(value.get("storage_kind") or "blob-v1") == "chunked-v1":
                media_id = str(value.get("media_id") or "").strip()
                if not media_id:
                    raise VaultError("大型资料缺少媒体标识")
                if not self.large_uploads.store.manifest_path(media_id).is_file():
                    raise VaultError("大型媒体文件离线，请恢复 data/media 媒体库后重试")
                try:
                    manifest = self.large_uploads.store.read_manifest(master_key, media_id)
                except LargeFileError as exc:
                    raise VaultError(f"大型媒体文件无法验证：{exc}") from exc
                if int(manifest.get("size_bytes") or -1) != total_size:
                    raise VaultError("大型资料清单大小与索引不一致")
                if int(manifest.get("chunk_size") or -1) != int(value.get("chunk_size") or -2):
                    raise VaultError("大型资料分块参数与索引不一致")
            return self._public_attachment(value)

    def iter_attachment_stream_range(
        self,
        *,
        attachment_id: str,
        start: int,
        end_exclusive: int,
    ):
        """Yield only the requested plaintext bytes without materializing large media."""
        with self._mutex:
            master_key = self.require_master_key()
            profile = self.get_profile()
            try:
                value = self.database.get_attachment(
                    master_key,
                    profile_id=profile["id"],
                    attachment_id=attachment_id,
                )
            except DatabaseContentNotFound as exc:
                raise ContentNotFound(str(exc)) from exc

            total_size = int(value.get("size_bytes") or 0)
            start = int(start)
            end_exclusive = int(end_exclusive)
            if total_size <= 0 or start < 0 or end_exclusive <= start or end_exclusive > total_size:
                raise VaultError("请求的附件字节范围无效")

            if str(value.get("storage_kind") or "blob-v1") != "chunked-v1":
                try:
                    content = self.attachment_store.read(master_key, attachment_id, value["file_nonce"])
                except AttachmentFileError as exc:
                    raise VaultError(str(exc)) from exc
                if len(content) != total_size:
                    raise VaultError("附件大小校验失败")
                if hashlib.sha256(content).hexdigest() != str(value.get("sha256") or ""):
                    raise VaultError("附件完整性校验失败")
                return iter((content[start:end_exclusive],))

            media_id = str(value.get("media_id") or "").strip()
            chunk_size = int(value.get("chunk_size") or 0)
            if not media_id or chunk_size <= 0:
                raise VaultError("大型资料分块索引无效")
            if not self.large_uploads.store.manifest_path(media_id).is_file():
                raise VaultError("大型媒体文件离线，请恢复 data/media 媒体库后重试")

        # Do not hold the vault-wide mutex while StreamingResponse iterates a
        # potentially multi-GB range. Each chunk authenticates independently.
        return self._iter_original_media_range_cached(
            master_key,
            media_id,
            total_size=total_size,
            chunk_size=chunk_size,
            start=start,
            end_exclusive=end_exclusive,
        )

    def _attachment_audio_source_iter(
        self,
        *,
        master_key: bytes,
        value: dict[str, Any],
    ):
        total_size = int(value.get("size_bytes") or 0)
        if str(value.get("storage_kind") or "blob-v1") == "chunked-v1":
            media_id = str(value.get("media_id") or "").strip()
            chunk_size = int(value.get("chunk_size") or 0)
            if not media_id or chunk_size <= 0:
                raise VaultError("大型资料分块索引无效")
            return self.large_uploads.store.iter_plain_chunks_buffered(
                master_key,
                media_id,
                total_size=total_size,
                chunk_size=chunk_size,
                buffer_chunks=3,
            )
        try:
            content = self.attachment_store.read(master_key, value["id"], value["file_nonce"])
        except AttachmentFileError as exc:
            raise VaultError(str(exc)) from exc
        if len(content) != total_size:
            raise VaultError("附件大小校验失败")
        return iter((content,))

    def _read_attachment_probe_prefix(
        self,
        *,
        master_key: bytes,
        value: dict[str, Any],
    ) -> bytes:
        total_size = int(value.get("size_bytes") or 0)
        if total_size <= 0:
            return b""
        end = min(total_size, AUDIO_PROBE_BYTES)
        if str(value.get("storage_kind") or "blob-v1") == "chunked-v1":
            media_id = str(value.get("media_id") or "").strip()
            chunk_size = int(value.get("chunk_size") or 0)
            if not media_id or chunk_size <= 0:
                return b""
            try:
                return b"".join(
                    self.large_uploads.store.iter_plain_range(
                        master_key,
                        media_id,
                        total_size=total_size,
                        chunk_size=chunk_size,
                        start=0,
                        end_exclusive=end,
                    )
                )
            except LargeFileError:
                return b""
        try:
            content = self.attachment_store.read(master_key, value["id"], value["file_nonce"])
        except AttachmentFileError:
            return b""
        return content[:end]

    def _probe_attachment_audio_metadata(
        self,
        *,
        master_key: bytes,
        profile_id: str,
        value: dict[str, Any],
    ) -> dict[str, Any]:
        if value.get("audio_codec_id") or value.get("audio_codec"):
            return value
        media_type = str(value.get("media_type") or "").lower()
        filename = str(value.get("filename") or "").lower()
        if not media_type.startswith("video/") and not filename.endswith(
            (".mkv", ".webm", ".mp4", ".m4v", ".mov", ".avi", ".ts", ".m2ts", ".mts")
        ):
            return value
        prefix = self._read_attachment_probe_prefix(master_key=master_key, value=value)
        probe = self.audio_compat.probe_prefix(prefix)
        if probe is None or not probe.codec_id:
            return value
        metadata = self._attachment_metadata_payload(value)
        metadata.update({key: item for key, item in probe.as_dict().items() if item is not None})
        metadata["audio_metadata_source"] = "server:ffprobe-prefix"
        return self.database.update_attachment_metadata(
            master_key,
            profile_id=profile_id,
            attachment_id=value["id"],
            metadata=metadata,
            timestamp=datetime.now(dt_timezone.utc).isoformat(),
        )

    def _audio_job_snapshot(self, attachment_id: str) -> dict[str, Any] | None:
        with self._audio_jobs_mutex:
            job = self._audio_jobs.get(str(attachment_id))
            if not job:
                return None
            return {
                "state": str(job.get("state") or "building"),
                "progress_percent": round(float(job.get("progress_percent") or 0.0), 1),
                "processed_bytes": int(job.get("processed_bytes") or 0),
                "source_size_bytes": int(job.get("source_size_bytes") or 0),
                "error": str(job.get("error") or "") or None,
                "target_codec": str(job.get("target_codec") or "") or None,
                "target_media_type": str(job.get("target_media_type") or "") or None,
            }

    def get_attachment_audio_compat_status(self, *, attachment_id: str) -> dict[str, Any]:
        with self._mutex:
            master_key = self.require_master_key()
            profile = self.get_profile()
            try:
                value = self.database.get_attachment(
                    master_key,
                    profile_id=profile["id"],
                    attachment_id=attachment_id,
                )
            except DatabaseContentNotFound as exc:
                raise ContentNotFound(str(exc)) from exc
            value = self._probe_attachment_audio_metadata(
                master_key=master_key,
                profile_id=profile["id"],
                value=value,
            )
            tools = self.audio_compat.refresh_tools()
            codec_id = normalize_codec_id(value.get("audio_codec_id") or value.get("audio_codec"))
            label = str(value.get("audio_codec") or audio_codec_label(codec_id) or "").strip()
            compat_id = str(value.get("audio_compat_media_id") or "").strip()
            has_compat = bool(compat_id and self.audio_compat.asset_exists(compat_id))
            compat_size = int(value.get("audio_compat_size_bytes") or 0) if has_compat else 0
            compat_chunk = int(value.get("audio_compat_chunk_size") or 0) if has_compat else 0
            compat_media_type = str(value.get("audio_compat_media_type") or "").strip() if has_compat else ""
            compat_codec = str(value.get("audio_compat_codec") or "").strip() if has_compat else ""
            needs_compat = codec_needs_compat(codec_id)

        job = self._audio_job_snapshot(attachment_id)
        if has_compat:
            state = "ready"
        elif job and job.get("state") == "building":
            state = "building"
        elif job and job.get("state") in {"error", "cancelled"}:
            state = str(job["state"])
        elif needs_compat and not tools.available:
            state = "unavailable"
        elif needs_compat:
            state = "idle"
        elif codec_id:
            state = "not_needed"
        else:
            state = "unknown"
        return {
            "attachment_id": attachment_id,
            "state": state,
            "ffmpeg_available": bool(tools.ffmpeg),
            "ffprobe_available": bool(tools.ffprobe),
            "audio_codec_id": codec_id or None,
            "audio_codec": label or None,
            "audio_channels": value.get("audio_channels"),
            "audio_channel_layout": value.get("audio_channel_layout"),
            "audio_sample_rate": value.get("audio_sample_rate"),
            "needs_compat": needs_compat,
            "has_compat_audio": has_compat,
            "compat_media_type": compat_media_type or None,
            "compat_codec": compat_codec or None,
            "compat_size_bytes": compat_size or None,
            "compat_chunk_size": compat_chunk or None,
            **(job or {}),
        }

    def _cancel_audio_compat_job(self, attachment_id: str) -> None:
        with self._audio_jobs_mutex:
            job = self._audio_jobs.get(str(attachment_id))
            if job:
                cancel_event = job.get("cancel_event")
                if isinstance(cancel_event, threading.Event):
                    cancel_event.set()

    def start_attachment_audio_compat(self, *, attachment_id: str) -> dict[str, Any]:
        with self._mutex:
            master_key = self.require_master_key()
            profile = self.get_profile()
            try:
                value = self.database.get_attachment(
                    master_key,
                    profile_id=profile["id"],
                    attachment_id=attachment_id,
                )
            except DatabaseContentNotFound as exc:
                raise ContentNotFound(str(exc)) from exc
            value = self._probe_attachment_audio_metadata(
                master_key=master_key,
                profile_id=profile["id"],
                value=value,
            )
            codec_id = normalize_codec_id(value.get("audio_codec_id") or value.get("audio_codec"))
            if not codec_needs_compat(codec_id):
                if codec_id:
                    return self.get_attachment_audio_compat_status(attachment_id=attachment_id)
                raise VaultError("暂未识别到需要兼容转换的音轨")
            tools = self.audio_compat.refresh_tools()
            if not tools.ffmpeg:
                raise VaultError("未找到 FFmpeg；当前会自动检测 C:\\ffmpeg\\bin\\ffmpeg.exe、C:\\ffmpeg\\ffmpeg.exe 和系统 PATH")
            existing_id = str(value.get("audio_compat_media_id") or "").strip()
            if existing_id and self.audio_compat.asset_exists(existing_id):
                return self.get_attachment_audio_compat_status(attachment_id=attachment_id)
            source_size = int(value.get("size_bytes") or 0)
            compat_target = self.audio_compat.preferred_target()
            captured_value = dict(value)
            captured_key = bytes(master_key)
            profile_id = str(profile["id"])

        with self._audio_jobs_mutex:
            existing_job = self._audio_jobs.get(attachment_id)
            if existing_job and existing_job.get("state") == "building":
                return self.get_attachment_audio_compat_status(attachment_id=attachment_id)
            cancel_event = threading.Event()
            compat_media_id = f"aud_{uuid.uuid4().hex}"
            self._audio_jobs[attachment_id] = {
                "state": "building",
                "progress_percent": 0.0,
                "processed_bytes": 0,
                "source_size_bytes": source_size,
                "error": None,
                "cancel_event": cancel_event,
                "compat_media_id": compat_media_id,
                "target_codec": compat_target.codec_label,
                "target_media_type": compat_target.media_type,
            }

        def progress(processed: int, total: int) -> None:
            with self._audio_jobs_mutex:
                job = self._audio_jobs.get(attachment_id)
                if not job or job.get("compat_media_id") != compat_media_id:
                    return
                job["processed_bytes"] = int(processed)
                job["source_size_bytes"] = int(total)
                job["progress_percent"] = min(99.5, max(0.0, processed * 100.0 / max(1, total)))

        def worker() -> None:
            try:
                source_iter = self._attachment_audio_source_iter(
                    master_key=captured_key,
                    value=captured_value,
                )
                manifest = self.audio_compat.transcode_browser_audio(
                    master_key=captured_key,
                    media_id=compat_media_id,
                    source_iter=source_iter,
                    source_size=source_size,
                    cancel_event=cancel_event,
                    progress=progress,
                    target=compat_target,
                )
                if cancel_event.is_set():
                    raise AudioCompatibilityCancelled("兼容音轨生成已取消")
                with self._mutex:
                    current = self.database.get_attachment(
                        captured_key,
                        profile_id=profile_id,
                        attachment_id=attachment_id,
                    )
                    metadata = self._attachment_metadata_payload(current)
                    old_compat = str(metadata.get("audio_compat_media_id") or "").strip()
                    metadata.update(
                        {
                            "audio_compat_media_id": compat_media_id,
                            "audio_compat_media_type": str(manifest.get("media_type") or compat_target.media_type),
                            "audio_compat_codec": str(manifest.get("audio_codec") or compat_target.codec_label),
                            "audio_compat_size_bytes": int(manifest["size_bytes"]),
                            "audio_compat_chunk_size": int(manifest["chunk_size"]),
                            "audio_compat_sha256": str(manifest["sha256"]),
                            "audio_compat_created_at": datetime.now(dt_timezone.utc).isoformat(),
                            "audio_compat_source_codec": normalize_codec_id(
                                current.get("audio_codec_id") or current.get("audio_codec")
                            ),
                        }
                    )
                    self.database.update_attachment_metadata(
                        captured_key,
                        profile_id=profile_id,
                        attachment_id=attachment_id,
                        metadata=metadata,
                        timestamp=datetime.now(dt_timezone.utc).isoformat(),
                    )
                    if old_compat and old_compat != compat_media_id:
                        self.audio_compat.delete(old_compat)
                with self._audio_jobs_mutex:
                    job = self._audio_jobs.get(attachment_id)
                    if job and job.get("compat_media_id") == compat_media_id:
                        job.update(
                            {
                                "state": "ready",
                                "progress_percent": 100.0,
                                "processed_bytes": source_size,
                                "error": None,
                            }
                        )
            except AudioCompatibilityCancelled as exc:
                self.audio_compat.delete(compat_media_id)
                with self._audio_jobs_mutex:
                    job = self._audio_jobs.get(attachment_id)
                    if job and job.get("compat_media_id") == compat_media_id:
                        job.update({"state": "cancelled", "error": str(exc)})
            except (AudioCompatibilityError, LargeFileError, AttachmentFileError, DatabaseContentNotFound, VaultError, OSError) as exc:
                self.audio_compat.delete(compat_media_id)
                with self._audio_jobs_mutex:
                    job = self._audio_jobs.get(attachment_id)
                    if job and job.get("compat_media_id") == compat_media_id:
                        job.update({"state": "error", "error": str(exc)})
            except Exception as exc:  # keep background failure visible without crashing the app
                self.audio_compat.delete(compat_media_id)
                with self._audio_jobs_mutex:
                    job = self._audio_jobs.get(attachment_id)
                    if job and job.get("compat_media_id") == compat_media_id:
                        job.update({"state": "error", "error": f"{exc.__class__.__name__}: {exc}"})

        threading.Thread(
            target=worker,
            name=f"lifegraph-audio-compat-{attachment_id[:8]}",
            daemon=True,
        ).start()
        return self.get_attachment_audio_compat_status(attachment_id=attachment_id)

    def get_attachment_audio_compat_stream_metadata(self, *, attachment_id: str) -> dict[str, Any]:
        with self._mutex:
            master_key = self.require_master_key()
            profile = self.get_profile()
            try:
                value = self.database.get_attachment(
                    master_key,
                    profile_id=profile["id"],
                    attachment_id=attachment_id,
                )
            except DatabaseContentNotFound as exc:
                raise ContentNotFound(str(exc)) from exc
            media_id = str(value.get("audio_compat_media_id") or "").strip()
            if not media_id:
                raise ContentNotFound("该视频尚未生成兼容音轨")
            try:
                manifest = self.audio_compat.read_manifest(master_key, media_id)
            except LargeFileError as exc:
                raise ContentNotFound("兼容音轨文件缺失，可重新生成") from exc
            original_name = str(value.get("filename") or "video")
            base_name = original_name.rsplit(".", 1)[0] if "." in original_name else original_name
            media_type = str(
                value.get("audio_compat_media_type")
                or manifest.get("media_type")
                or "audio/mp4"
            ).strip()
            codec = str(
                value.get("audio_compat_codec")
                or manifest.get("audio_codec")
                or "AAC"
            ).strip()
            extension = "mp3" if media_type == "audio/mpeg" or codec.upper() == "MP3" else "m4a"
            return {
                "attachment_id": attachment_id,
                "media_id": media_id,
                "filename": f"{base_name}.browser-audio.{extension}",
                "media_type": media_type,
                "audio_codec": codec,
                "size_bytes": int(manifest.get("size_bytes") or 0),
                "chunk_size": int(manifest.get("chunk_size") or 0),
            }

    def iter_attachment_audio_compat_range(
        self,
        *,
        attachment_id: str,
        start: int,
        end_exclusive: int,
    ):
        with self._mutex:
            master_key = self.require_master_key()
            metadata = self.get_attachment_audio_compat_stream_metadata(attachment_id=attachment_id)
            total_size = int(metadata["size_bytes"])
            chunk_size = int(metadata["chunk_size"])
            media_id = str(metadata["media_id"])
            if start < 0 or end_exclusive <= start or end_exclusive > total_size:
                raise VaultError("请求的兼容音轨字节范围无效")
        return self.audio_compat.store.iter_plain_range(
            master_key,
            media_id,
            total_size=total_size,
            chunk_size=chunk_size,
            start=start,
            end_exclusive=end_exclusive,
        )

    def create_attachment_playback_ticket(self, *, attachment_id: str) -> dict[str, Any]:
        metadata = self.get_attachment_stream_metadata(attachment_id=attachment_id)
        ticket = self.sessions.create_media_ticket(attachment_id)
        return {
            "attachment_id": attachment_id,
            "ticket": ticket.token,
            "expires_at": ticket.expires_at,
            "filename": metadata.get("filename") or "attachment",
            "media_type": metadata.get("media_type") or "application/octet-stream",
            "size_bytes": int(metadata.get("size_bytes") or 0),
            "is_large": bool(metadata.get("is_large")),
        }

    def read_attachment(self, *, attachment_id: str) -> tuple[dict[str, Any], bytes]:
        with self._mutex:
            master_key = self.require_master_key()
            profile = self.get_profile()
            try:
                value = self.database.get_attachment(
                    master_key,
                    profile_id=profile["id"],
                    attachment_id=attachment_id,
                )
                if str(value.get("storage_kind") or "blob-v1") == "chunked-v1":
                    raise VaultError("大型资料需使用分块媒体读取接口")
                content = self.attachment_store.read(
                    master_key, attachment_id, value["file_nonce"]
                )
            except DatabaseContentNotFound as exc:
                raise ContentNotFound(str(exc)) from exc
            except AttachmentFileError as exc:
                raise VaultError(str(exc)) from exc

            if len(content) != int(value.get("size_bytes") or -1):
                raise VaultError("附件大小校验失败")
            import hashlib
            if hashlib.sha256(content).hexdigest() != value.get("sha256"):
                raise VaultError("附件完整性校验失败")
            return self._public_attachment(value), content

    def delete_attachment(
        self,
        *,
        kind: str,
        content_id: str,
        attachment_id: str,
    ) -> dict[str, Any]:
        with self._mutex:
            master_key = self.require_master_key()
            profile = self.get_profile()
            try:
                value = self.database.get_attachment(
                    master_key,
                    profile_id=profile["id"],
                    attachment_id=attachment_id,
                )
                result = self.database.delete_attachment(
                    profile_id=profile["id"],
                    kind=kind,
                    content_id=content_id,
                    attachment_id=attachment_id,
                )
            except DatabaseContentNotFound as exc:
                raise ContentNotFound(str(exc)) from exc
            storage_kind = str(result.pop("storage_kind", "blob-v1"))
            media_id = result.pop("media_id", None)
            compat_media_id = str(value.get("audio_compat_media_id") or "").strip()
            self._cancel_audio_compat_job(attachment_id)
            if storage_kind == "chunked-v1" and media_id:
                self.large_uploads.store.delete(str(media_id))
            else:
                self.attachment_store.delete(attachment_id)
            self.preview_store.delete(attachment_id)
            self.audio_compat.delete(compat_media_id)
            return result

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
                result = self.database.permanently_delete_content(
                    kind=kind,
                    content_id=content_id,
                    profile_id=profile["id"],
                    expected_revision=revision,
                )
                for attachment_id in result.pop("attachment_ids", []):
                    self.attachment_store.delete(attachment_id)
                return result
            except DatabaseContentNotFound as exc:
                raise ContentNotFound(str(exc)) from exc
            except DatabaseRevisionConflict as exc:
                raise ContentRevisionConflict(str(exc)) from exc

    def empty_trash(self) -> dict[str, Any]:
        with self._mutex:
            self.require_master_key()
            profile = self.get_profile()
            result = self.database.empty_trash(profile_id=profile["id"])
            for attachment_id in result.pop("attachment_ids", []):
                self.attachment_store.delete(attachment_id)
            return result

    def get_content_status(self, *, start_date: str, end_date: str) -> dict[str, dict[str, dict[str, bool]]]:
        master_key = self.require_master_key()
        profile = self.get_profile()
        result = self.database.get_content_status(
            profile_id=profile["id"],
            start_date=start_date,
            end_date=end_date,
        )
        for raw_value in self.database.list_all_attachments(master_key, profile_id=profile["id"]):
            value = self._ensure_attachment_time_metadata(
                master_key=master_key,
                profile_id=profile["id"],
                timezone_name=str(profile.get("timezone") or "UTC"),
                value=raw_value,
            )
            timeline_date = str(value.get("timeline_date") or "")
            if not timeline_date or timeline_date < start_date or timeline_date > end_date:
                continue
            if not self.database.content_exists(
                profile_id=profile["id"],
                kind=str(value.get("kind") or ""),
                content_id=str(value.get("content_id") or ""),
                include_deleted=False,
            ):
                continue
            for map_name, map_key in (("dates", timeline_date), ("months", timeline_date[:7]), ("years", timeline_date[:4])):
                state = result[map_name].setdefault(
                    map_key,
                    {"has_event": False, "has_memory": False, "has_plan": False},
                )
                state["has_material"] = True
        return result
