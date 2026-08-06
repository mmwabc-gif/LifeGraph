from __future__ import annotations

import hashlib
import io
import json
import tempfile
import zipfile
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.storage.database import Database, LATEST_SCHEMA_VERSION


LIFEVAULT_FORMAT = "lifegraph-lifevault"
LIFEVAULT_FORMAT_VERSION = 1
LIFEVAULT_MEDIA_TYPE = "application/vnd.lifegraph.lifevault+zip"
LIFEVAULT_REQUIRED_PATHS = {
    "manifest.json",
    "repository/vault.json",
    "repository/lifegraph.db",
}
MAX_LIFEVAULT_BYTES = 512 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_METADATA_BYTES = 5 * 1024 * 1024


class LifeVaultPackageError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BackupArtifact:
    filename: str
    content: bytes
    manifest: dict[str, Any]


@dataclass(frozen=True, slots=True)
class LifeVaultPackage:
    manifest: dict[str, Any]
    metadata_bytes: bytes
    database_bytes: bytes
    package_sha256: str


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_entry(path: str, value: bytes) -> dict[str, Any]:
    return {
        "path": path,
        "size": len(value),
        "sha256": sha256_bytes(value),
    }


def build_lifevault_backup(
    *,
    database: Database,
    metadata_path: Path,
    master_key: bytes,
    app_version: str,
) -> BackupArtifact:
    """Create one consistent encrypted repository package.

    The SQLite backup API captures one committed database state even when the live
    repository uses WAL mode. The package contains only the encrypted database,
    wrapped-key metadata, and a plaintext integrity manifest without profile data.
    """

    created_at = datetime.now(timezone.utc)
    with tempfile.TemporaryDirectory(prefix="lifegraph-backup-") as temporary_dir:
        snapshot_path = Path(temporary_dir) / "lifegraph.db"
        database.create_consistent_snapshot(snapshot_path)
        integrity = database.verify_encrypted_snapshot(snapshot_path, master_key)
        database_bytes = snapshot_path.read_bytes()

    metadata_bytes = metadata_path.read_bytes()
    # Validate that metadata is valid JSON before placing it in the package. The
    # wrapped keys and verification ciphertext remain unchanged.
    json.loads(metadata_bytes.decode("utf-8"))

    files = {
        "repository/vault.json": metadata_bytes,
        "repository/lifegraph.db": database_bytes,
    }
    file_entries = [_file_entry(path, value) for path, value in files.items()]
    manifest = {
        "format": LIFEVAULT_FORMAT,
        "format_version": LIFEVAULT_FORMAT_VERSION,
        "created_at": created_at.isoformat(),
        "producer": {
            "name": "LifeGraph",
            "version": app_version,
        },
        "repository": {
            "schema_version": integrity["schema_version"],
            "storage_mode": "sqlite+aead-field-encryption",
        },
        "integrity": {
            "sqlite_quick_check": integrity["sqlite_quick_check"],
            "foreign_key_errors": integrity["foreign_key_errors"],
            "encrypted_records_verified": integrity["encrypted_records_verified"],
        },
        "files": file_entries,
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
    ) as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
        )
        for path, value in files.items():
            archive.writestr(path, value)

    filename = created_at.strftime("lifegraph-backup-%Y%m%d-%H%M%S.lifevault")
    return BackupArtifact(filename=filename, content=buffer.getvalue(), manifest=manifest)


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LifeVaultPackageError(f"{label} 格式无效")
    return value


def inspect_lifevault_package(content: bytes) -> LifeVaultPackage:
    """Validate package structure and checksums without decrypting repository rows."""

    if not content:
        raise LifeVaultPackageError("备份文件为空")
    if len(content) > MAX_LIFEVAULT_BYTES:
        raise LifeVaultPackageError("备份文件超过 512 MB 限制")

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            if len(names) != len(set(names)):
                raise LifeVaultPackageError("备份包包含重复文件")
            if set(names) != LIFEVAULT_REQUIRED_PATHS:
                raise LifeVaultPackageError("备份包目录结构不符合 LifeGraph 格式")
            if sum(item.file_size for item in infos) > MAX_LIFEVAULT_BYTES:
                raise LifeVaultPackageError("备份包解压后超过 512 MB 限制")
            for item in infos:
                if item.flag_bits & 0x1:
                    raise LifeVaultPackageError("不支持 ZIP 层加密的备份包")
                if item.is_dir():
                    raise LifeVaultPackageError("备份包包含不应出现的目录项")
                if item.file_size > MAX_LIFEVAULT_BYTES:
                    raise LifeVaultPackageError("备份包内文件过大")

            manifest_info = archive.getinfo("manifest.json")
            if manifest_info.file_size > MAX_MANIFEST_BYTES:
                raise LifeVaultPackageError("manifest.json 过大")
            metadata_info = archive.getinfo("repository/vault.json")
            if metadata_info.file_size > MAX_METADATA_BYTES:
                raise LifeVaultPackageError("vault.json 过大")
            manifest_bytes = archive.read("manifest.json")
            metadata_bytes = archive.read("repository/vault.json")
            database_bytes = archive.read("repository/lifegraph.db")
    except LifeVaultPackageError:
        raise
    except (zipfile.BadZipFile, KeyError, OSError, RuntimeError, EOFError, zlib.error) as exc:
        raise LifeVaultPackageError("无法读取 .lifevault 备份包") from exc

    try:
        manifest = _require_mapping(
            json.loads(manifest_bytes.decode("utf-8")), "manifest.json"
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LifeVaultPackageError("manifest.json 不是有效 JSON") from exc

    if manifest.get("format") != LIFEVAULT_FORMAT:
        raise LifeVaultPackageError("备份包格式标识不正确")
    if manifest.get("format_version") != LIFEVAULT_FORMAT_VERSION:
        raise LifeVaultPackageError("暂不支持此 .lifevault 格式版本")

    repository = _require_mapping(manifest.get("repository"), "repository")
    try:
        schema_version = int(repository.get("schema_version"))
    except (TypeError, ValueError) as exc:
        raise LifeVaultPackageError("备份包缺少有效 schema 版本") from exc
    if schema_version < 1:
        raise LifeVaultPackageError("备份包 schema 版本无效")
    if schema_version > LATEST_SCHEMA_VERSION:
        raise LifeVaultPackageError(
            f"备份包 schema v{schema_version} 高于当前程序支持的 v{LATEST_SCHEMA_VERSION}"
        )

    file_entries = manifest.get("files")
    if not isinstance(file_entries, list) or len(file_entries) != 2:
        raise LifeVaultPackageError("备份包文件清单无效")
    expected_values = {
        "repository/vault.json": metadata_bytes,
        "repository/lifegraph.db": database_bytes,
    }
    seen: set[str] = set()
    for raw_entry in file_entries:
        entry = _require_mapping(raw_entry, "文件清单项")
        path = entry.get("path")
        if path not in expected_values or path in seen:
            raise LifeVaultPackageError("备份包文件清单路径无效")
        seen.add(path)
        value = expected_values[path]
        if entry.get("size") != len(value):
            raise LifeVaultPackageError(f"{path} 文件大小校验失败")
        if entry.get("sha256") != sha256_bytes(value):
            raise LifeVaultPackageError(f"{path} SHA-256 校验失败")
    if seen != set(expected_values):
        raise LifeVaultPackageError("备份包文件清单不完整")

    try:
        metadata = _require_mapping(
            json.loads(metadata_bytes.decode("utf-8")), "vault.json"
        )
        key_slots = _require_mapping(metadata.get("key_slots"), "vault.json key_slots")
        _require_mapping(key_slots.get("pin"), "PIN 密钥槽")
        _require_mapping(key_slots.get("recovery"), "恢复密钥槽")
        verification = _require_mapping(
            metadata.get("verification"), "vault.json verification"
        )
        if not verification.get("nonce") or not verification.get("ciphertext"):
            raise LifeVaultPackageError("vault.json 验证字段不完整")
    except LifeVaultPackageError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LifeVaultPackageError("vault.json 不是有效 JSON") from exc

    if not database_bytes.startswith(b"SQLite format 3\x00"):
        raise LifeVaultPackageError("lifegraph.db 不是有效 SQLite 数据库")

    return LifeVaultPackage(
        manifest=manifest,
        metadata_bytes=metadata_bytes,
        database_bytes=database_bytes,
        package_sha256=sha256_bytes(content),
    )


def verify_lifevault_database(
    package: LifeVaultPackage, master_key: bytes
) -> dict[str, Any]:
    """Decrypt and verify every repository row from an inspected package."""

    with tempfile.TemporaryDirectory(prefix="lifegraph-import-check-") as temporary_dir:
        database_path = Path(temporary_dir) / "lifegraph.db"
        database_path.write_bytes(package.database_bytes)
        database = Database(database_path)
        try:
            actual_schema = database.schema_version()
            declared_schema = int(package.manifest["repository"]["schema_version"])
            if actual_schema != declared_schema:
                raise LifeVaultPackageError(
                    f"清单 schema v{declared_schema} 与数据库 schema v{actual_schema} 不一致"
                )
            # Rehearse the same additive migration that will run after a real restore.
            database.initialize_schema()
            result = database.verify_encrypted_snapshot(database_path, master_key)
            result["source_schema_version"] = actual_schema
            return result
        except LifeVaultPackageError:
            raise
        except Exception as exc:
            raise LifeVaultPackageError(f"备份数据库无法验证：{exc}") from exc
