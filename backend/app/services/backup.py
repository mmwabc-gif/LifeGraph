from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import tempfile
import zipfile
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.security.crypto import decrypt_bytes
from app.services.attachments import AttachmentStore, attachment_aad
from app.storage.database import Database, LATEST_SCHEMA_VERSION


LIFEVAULT_FORMAT = "lifegraph-lifevault"
LIFEVAULT_FORMAT_VERSION = 2
SUPPORTED_LIFEVAULT_FORMAT_VERSIONS = {1, 2}
LIFEVAULT_MEDIA_TYPE = "application/vnd.lifegraph.lifevault+zip"
LIFEVAULT_BASE_PATHS = {
    "manifest.json",
    "repository/vault.json",
    "repository/lifegraph.db",
}
MAX_LIFEVAULT_BYTES = 512 * 1024 * 1024
MAX_LIFEVAULT_IMPORT_BYTES = 2 * 1024 * 1024 * 1024 * 1024
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
class BackupFileArtifact:
    filename: str
    path: Path
    manifest: dict[str, Any]
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class LifeVaultPackage:
    manifest: dict[str, Any]
    metadata_bytes: bytes
    database_bytes: bytes
    attachment_files: dict[str, bytes]
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
    attachment_dir: Path | None = None,
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
    attachment_records = database.list_all_attachments(master_key)
    if attachment_records:
        if attachment_dir is None:
            raise DatabaseIntegrityError("仓库包含附件，但未提供附件目录")
        attachment_store = AttachmentStore(attachment_dir)
        for record in attachment_records:
            attachment_id = record["id"]
            encrypted = attachment_store.encrypted_bytes(attachment_id)
            try:
                plaintext = decrypt_bytes(
                    master_key,
                    record["file_nonce"],
                    encrypted,
                    aad=attachment_aad(attachment_id),
                )
            except Exception as exc:
                raise DatabaseIntegrityError(f"附件 {attachment_id} 无法解密验证") from exc
            if len(plaintext) != int(record.get("size_bytes") or -1):
                raise DatabaseIntegrityError(f"附件 {attachment_id} 大小校验失败")
            if hashlib.sha256(plaintext).hexdigest() != record.get("sha256"):
                raise DatabaseIntegrityError(f"附件 {attachment_id} SHA-256 校验失败")
            files[f"repository/attachments/{attachment_id}.lgatt"] = encrypted

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
            "storage_mode": "sqlite+aead-field-encryption+encrypted-attachments",
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



def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _path_file_entry(archive_path: str, path: Path) -> dict[str, Any]:
    return {
        "path": archive_path,
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def build_lifevault_backup_file(
    *,
    database: Database,
    metadata_path: Path,
    master_key: bytes,
    app_version: str,
    output_path: Path,
    attachment_dir: Path | None = None,
) -> BackupFileArtifact:
    """Build a .lifevault directly on disk with bounded memory usage.

    The package format remains v2. Attachment ciphertext is verified one file at
    a time, then ZipFile streams the encrypted blob from disk into the archive.
    Memory usage therefore scales with one attachment (currently capped at 50 MB),
    not with the total repository size.
    """

    created_at = datetime.now(timezone.utc)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output_path.with_name(output_path.name + ".tmp")
    temp_output.unlink(missing_ok=True)

    with tempfile.TemporaryDirectory(prefix="lifegraph-backup-") as temporary_dir:
        snapshot_path = Path(temporary_dir) / "lifegraph.db"
        database.create_consistent_snapshot(snapshot_path)
        integrity = database.verify_encrypted_snapshot(snapshot_path, master_key)

        metadata_bytes = metadata_path.read_bytes()
        json.loads(metadata_bytes.decode("utf-8"))

        file_entries = [
            {
                "path": "repository/vault.json",
                "size": len(metadata_bytes),
                "sha256": sha256_bytes(metadata_bytes),
            },
            _path_file_entry("repository/lifegraph.db", snapshot_path),
        ]
        attachment_paths: list[tuple[str, Path]] = []
        attachment_store = AttachmentStore(attachment_dir) if attachment_dir is not None else None
        for record in database.iter_all_attachments(master_key):
            if attachment_store is None:
                raise DatabaseIntegrityError("仓库包含附件，但未提供附件目录")
            attachment_id = record["id"]
            encrypted_path = attachment_store.encrypted_path(attachment_id)
            encrypted = encrypted_path.read_bytes()
            try:
                plaintext = decrypt_bytes(
                    master_key,
                    record["file_nonce"],
                    encrypted,
                    aad=attachment_aad(attachment_id),
                )
            except Exception as exc:
                raise DatabaseIntegrityError(f"附件 {attachment_id} 无法解密验证") from exc
            if len(plaintext) != int(record.get("size_bytes") or -1):
                raise DatabaseIntegrityError(f"附件 {attachment_id} 大小校验失败")
            if hashlib.sha256(plaintext).hexdigest() != record.get("sha256"):
                raise DatabaseIntegrityError(f"附件 {attachment_id} SHA-256 校验失败")
            archive_name = f"repository/attachments/{attachment_id}.lgatt"
            file_entries.append(
                {
                    "path": archive_name,
                    "size": len(encrypted),
                    "sha256": sha256_bytes(encrypted),
                }
            )
            attachment_paths.append((archive_name, encrypted_path))
            del encrypted, plaintext

        manifest = {
            "format": LIFEVAULT_FORMAT,
            "format_version": LIFEVAULT_FORMAT_VERSION,
            "created_at": created_at.isoformat(),
            "producer": {"name": "LifeGraph", "version": app_version},
            "repository": {
                "schema_version": integrity["schema_version"],
                "storage_mode": "sqlite+aead-field-encryption+encrypted-attachments",
            },
            "integrity": {
                "sqlite_quick_check": integrity["sqlite_quick_check"],
                "foreign_key_errors": integrity["foreign_key_errors"],
                "encrypted_records_verified": integrity["encrypted_records_verified"],
            },
            "files": file_entries,
        }

        try:
            with zipfile.ZipFile(
                temp_output,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=6,
                allowZip64=True,
            ) as archive:
                archive.writestr(
                    "manifest.json",
                    json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
                )
                archive.writestr("repository/vault.json", metadata_bytes)
                archive.write(snapshot_path, "repository/lifegraph.db")
                for archive_name, encrypted_path in attachment_paths:
                    archive.write(encrypted_path, archive_name)
            with temp_output.open("rb") as stream:
                os.fsync(stream.fileno())
            os.replace(temp_output, output_path)
        finally:
            temp_output.unlink(missing_ok=True)

    filename = created_at.strftime("lifegraph-backup-%Y%m%d-%H%M%S.lifevault")
    return BackupFileArtifact(
        filename=filename,
        path=output_path,
        manifest=manifest,
        size=output_path.stat().st_size,
        sha256=sha256_file(output_path),
    )


def inspect_lifevault_file(path: Path, *, verify_checksums: bool = True) -> dict[str, Any]:
    """Inspect a disk-backed .lifevault without loading the whole package."""
    if not path.is_file() or path.stat().st_size <= 0:
        raise LifeVaultPackageError("备份文件为空")
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            if len(names) != len(set(names)):
                raise LifeVaultPackageError("备份包包含重复文件")
            name_set = set(names)
            if not LIFEVAULT_BASE_PATHS.issubset(name_set):
                raise LifeVaultPackageError("备份包缺少 LifeGraph 核心文件")
            for item in infos:
                if item.flag_bits & 0x1:
                    raise LifeVaultPackageError("不支持 ZIP 层加密的备份包")
                if item.is_dir():
                    raise LifeVaultPackageError("备份包包含不应出现的目录项")
            manifest_bytes = archive.read("manifest.json")
            if len(manifest_bytes) > MAX_MANIFEST_BYTES:
                raise LifeVaultPackageError("manifest.json 过大")
            manifest = _require_mapping(json.loads(manifest_bytes.decode("utf-8")), "manifest.json")
            if manifest.get("format") != LIFEVAULT_FORMAT:
                raise LifeVaultPackageError("备份包格式标识不正确")
            format_version = manifest.get("format_version")
            if format_version not in SUPPORTED_LIFEVAULT_FORMAT_VERSIONS:
                raise LifeVaultPackageError("暂不支持此 .lifevault 格式版本")
            attachment_paths = {
                name for name in name_set
                if name.startswith("repository/attachments/") and name.endswith(".lgatt")
            }
            if format_version == 1:
                if name_set != LIFEVAULT_BASE_PATHS:
                    raise LifeVaultPackageError("v1 备份包目录结构无效")
            else:
                if name_set != LIFEVAULT_BASE_PATHS | attachment_paths:
                    raise LifeVaultPackageError("v2 备份包含无效文件路径")
                for name in attachment_paths:
                    attachment_id = name.removeprefix("repository/attachments/").removesuffix(".lgatt")
                    if not attachment_id or "/" in attachment_id or "\\" in attachment_id:
                        raise LifeVaultPackageError("附件备份路径无效")
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
            entries = manifest.get("files")
            if not isinstance(entries, list):
                raise LifeVaultPackageError("备份包文件清单无效")
            entry_map = {entry.get("path"): entry for entry in entries if isinstance(entry, dict)}
            expected_payloads = name_set - {"manifest.json"}
            if set(entry_map) != expected_payloads:
                raise LifeVaultPackageError("备份包文件清单不完整")
            if verify_checksums:
                for info in infos:
                    if info.filename == "manifest.json":
                        continue
                    entry = entry_map.get(info.filename)
                    if entry is None or int(entry.get("size", -1)) != info.file_size:
                        raise LifeVaultPackageError(f"{info.filename} 文件大小校验失败")
                    digest = hashlib.sha256()
                    with archive.open(info, "r") as stream:
                        while chunk := stream.read(1024 * 1024):
                            digest.update(chunk)
                    if digest.hexdigest() != entry.get("sha256"):
                        raise LifeVaultPackageError(f"{info.filename} SHA-256 校验失败")
            metadata_bytes = archive.read("repository/vault.json")
            if len(metadata_bytes) > MAX_METADATA_BYTES:
                raise LifeVaultPackageError("vault.json 过大")
            try:
                json.loads(metadata_bytes.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise LifeVaultPackageError("vault.json 不是有效 JSON") from exc
            return {
                "manifest": manifest,
                "metadata_bytes": metadata_bytes,
                "package_sha256": sha256_file(path),
            }
    except LifeVaultPackageError:
        raise
    except (zipfile.BadZipFile, KeyError, OSError, RuntimeError, EOFError, zlib.error, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LifeVaultPackageError("无法读取 .lifevault 备份包") from exc


def verify_lifevault_file(path: Path, master_key: bytes) -> dict[str, Any]:
    """Fully verify a disk-backed package while reading attachments one at a time."""
    inspected = inspect_lifevault_file(path, verify_checksums=True)
    manifest = inspected["manifest"]
    with tempfile.TemporaryDirectory(prefix="lifegraph-file-verify-") as temporary_dir:
        database_path = Path(temporary_dir) / "lifegraph.db"
        try:
            with zipfile.ZipFile(path) as archive:
                with archive.open("repository/lifegraph.db") as source, database_path.open("wb") as target:
                    shutil.copyfileobj(source, target, length=1024 * 1024)
                database = Database(database_path)
                actual_schema = database.schema_version()
                declared_schema = int(manifest["repository"]["schema_version"])
                if actual_schema != declared_schema:
                    raise LifeVaultPackageError(
                        f"清单 schema v{declared_schema} 与数据库 schema v{actual_schema} 不一致"
                    )
                database.initialize_schema()
                result = database.verify_encrypted_snapshot(database_path, master_key)
                remaining_names = {
                    name for name in archive.namelist()
                    if name.startswith("repository/attachments/") and name.endswith(".lgatt")
                }
                attachment_count = 0
                for record in database.iter_all_attachments(master_key):
                    attachment_id = record["id"]
                    archive_name = f"repository/attachments/{attachment_id}.lgatt"
                    if archive_name not in remaining_names:
                        raise LifeVaultPackageError("备份附件文件与数据库附件记录不一致")
                    remaining_names.remove(archive_name)
                    encrypted = archive.read(archive_name)
                    try:
                        plaintext = decrypt_bytes(
                            master_key,
                            record["file_nonce"],
                            encrypted,
                            aad=attachment_aad(attachment_id),
                        )
                    except Exception as exc:
                        raise LifeVaultPackageError(f"附件 {attachment_id} 无法解密验证") from exc
                    if len(plaintext) != int(record.get("size_bytes") or -1):
                        raise LifeVaultPackageError(f"附件 {attachment_id} 大小校验失败")
                    if hashlib.sha256(plaintext).hexdigest() != record.get("sha256"):
                        raise LifeVaultPackageError(f"附件 {attachment_id} SHA-256 校验失败")
                    del encrypted, plaintext
                    attachment_count += 1
                if remaining_names:
                    raise LifeVaultPackageError("备份附件文件与数据库附件记录不一致")
                result["attachment_files_verified"] = attachment_count
                result["source_schema_version"] = actual_schema
                result["package_sha256"] = inspected["package_sha256"]
                result["manifest"] = manifest
                return result
        except LifeVaultPackageError:
            raise
        except Exception as exc:
            raise LifeVaultPackageError(f"备份数据库无法验证：{exc}") from exc

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
            name_set = set(names)
            if not LIFEVAULT_BASE_PATHS.issubset(name_set):
                raise LifeVaultPackageError("备份包缺少 LifeGraph 核心文件")
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
            attachment_files = {
                name.removeprefix("repository/attachments/").removesuffix(".lgatt"): archive.read(name)
                for name in names
                if name.startswith("repository/attachments/") and name.endswith(".lgatt")
            }
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
    format_version = manifest.get("format_version")
    if format_version not in SUPPORTED_LIFEVAULT_FORMAT_VERSIONS:
        raise LifeVaultPackageError("暂不支持此 .lifevault 格式版本")

    actual_paths = set(names)
    attachment_paths = {
        f"repository/attachments/{attachment_id}.lgatt"
        for attachment_id in attachment_files
    }
    if format_version == 1:
        if actual_paths != LIFEVAULT_BASE_PATHS:
            raise LifeVaultPackageError("v1 备份包目录结构无效")
        if attachment_files:
            raise LifeVaultPackageError("v1 备份包不能包含附件文件")
    else:
        if actual_paths != LIFEVAULT_BASE_PATHS | attachment_paths:
            raise LifeVaultPackageError("v2 备份包含无效文件路径")
        for name in actual_paths - LIFEVAULT_BASE_PATHS:
            attachment_id = name.removeprefix("repository/attachments/").removesuffix(".lgatt")
            if not attachment_id or "/" in attachment_id or "\\" in attachment_id:
                raise LifeVaultPackageError("附件备份路径无效")

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
    if not isinstance(file_entries, list):
        raise LifeVaultPackageError("备份包文件清单无效")
    expected_values = {
        "repository/vault.json": metadata_bytes,
        "repository/lifegraph.db": database_bytes,
        **{
            f"repository/attachments/{attachment_id}.lgatt": value
            for attachment_id, value in attachment_files.items()
        },
    }
    if len(file_entries) != len(expected_values):
        raise LifeVaultPackageError("备份包文件清单数量无效")
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
        attachment_files=attachment_files,
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
            attachment_records = database.list_all_attachments(master_key)
            expected_ids = {record["id"] for record in attachment_records}
            if expected_ids != set(package.attachment_files):
                raise LifeVaultPackageError("备份附件文件与数据库附件记录不一致")
            for record in attachment_records:
                attachment_id = record["id"]
                try:
                    plaintext = decrypt_bytes(
                        master_key,
                        record["file_nonce"],
                        package.attachment_files[attachment_id],
                        aad=attachment_aad(attachment_id),
                    )
                except Exception as exc:
                    raise LifeVaultPackageError(
                        f"附件 {attachment_id} 无法解密验证"
                    ) from exc
                if len(plaintext) != int(record.get("size_bytes") or -1):
                    raise LifeVaultPackageError(f"附件 {attachment_id} 大小校验失败")
                if hashlib.sha256(plaintext).hexdigest() != record.get("sha256"):
                    raise LifeVaultPackageError(f"附件 {attachment_id} SHA-256 校验失败")
            result["attachment_files_verified"] = len(attachment_records)
            result["source_schema_version"] = actual_schema
            return result
        except LifeVaultPackageError:
            raise
        except Exception as exc:
            raise LifeVaultPackageError(f"备份数据库无法验证：{exc}") from exc
