from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import struct
import tempfile
import zipfile
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.security.crypto import CryptoError, b64d, decrypt_bytes, decrypt_json, encrypt_json
from app.services.attachments import AttachmentStore, attachment_aad
from app.services.large_files import ChunkedMediaStore
from app.services.media_inventory import build_media_inventory, validate_inventory_against_records
from app.services.media_previews import MediaPreviewStore, media_preview_aad
from app.storage.database import Database, DatabaseIntegrityError, LATEST_SCHEMA_VERSION


LIFEVAULT_FORMAT = "lifegraph-lifevault"
LIFEVAULT_FORMAT_VERSION = 3
SUPPORTED_LIFEVAULT_FORMAT_VERSIONS = {1, 2, 3}
LIFEVAULT_MEDIA_TYPE = "application/vnd.lifegraph.lifevault+zip"
LIFEVAULT_BASE_PATHS = {
    "manifest.json",
    "repository/vault.json",
    "repository/lifegraph.db",
}
MEDIA_INVENTORY_ARCHIVE_PATH = "repository/media-inventory.lgindex"
MEDIA_INVENTORY_MAGIC = b"LGMINV01"
MEDIA_INVENTORY_HEADER = struct.Struct(">8s12s")
MEDIA_INVENTORY_AAD = b"lifegraph:v3:media-inventory"
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
    preview_files: dict[str, bytes]
    media_inventory_bytes: bytes | None
    package_sha256: str




def encode_media_inventory(master_key: bytes, inventory: dict[str, Any]) -> bytes:
    nonce, ciphertext = encrypt_json(master_key, inventory, aad=MEDIA_INVENTORY_AAD)
    return MEDIA_INVENTORY_HEADER.pack(MEDIA_INVENTORY_MAGIC, nonce) + ciphertext


def decode_media_inventory(master_key: bytes, content: bytes) -> dict[str, Any]:
    if len(content) <= MEDIA_INVENTORY_HEADER.size:
        raise LifeVaultPackageError("媒体清单为空或损坏")
    try:
        magic, nonce = MEDIA_INVENTORY_HEADER.unpack(content[: MEDIA_INVENTORY_HEADER.size])
        if magic != MEDIA_INVENTORY_MAGIC:
            raise LifeVaultPackageError("媒体清单格式不受支持")
        value = decrypt_json(
            master_key,
            nonce,
            content[MEDIA_INVENTORY_HEADER.size :],
            aad=MEDIA_INVENTORY_AAD,
        )
        if not isinstance(value, dict):
            raise LifeVaultPackageError("媒体清单格式无效")
        return value
    except LifeVaultPackageError:
        raise
    except (CryptoError, ValueError, json.JSONDecodeError) as exc:
        raise LifeVaultPackageError("媒体清单无法解密或验证") from exc


def _preview_archive_name(attachment_id: str) -> str:
    return f"repository/previews/{attachment_id}.lgpreview"


def _collect_verified_preview(
    *,
    preview_store: MediaPreviewStore | None,
    master_key: bytes,
    record: dict[str, Any],
) -> tuple[str, Path] | None:
    """Return a verified preview when available without blocking core backup.

    Preview images are derived convenience artifacts. Historical restores, manual
    cleanup, or an interrupted preview write can leave encrypted attachment metadata
    pointing at a preview file that no longer exists. A missing or corrupt preview
    must therefore degrade the core backup, not make the encrypted database and
    ordinary attachments impossible to export.
    """

    nonce_text = str(record.get("preview_nonce") or "").strip()
    if not nonce_text or not record.get("preview_media_type"):
        return None
    if preview_store is None:
        return None
    attachment_id = str(record.get("id") or "")
    try:
        path = preview_store.path_for(attachment_id)
        if not path.is_file():
            return None
        plaintext = decrypt_bytes(
            master_key,
            b64d(nonce_text),
            path.read_bytes(),
            aad=media_preview_aad(attachment_id),
        )
        if len(plaintext) != int(record.get("preview_size_bytes") or -1):
            return None
        if hashlib.sha256(plaintext).hexdigest() != str(record.get("preview_sha256") or ""):
            return None
        return _preview_archive_name(attachment_id), path
    except (OSError, ValueError, CryptoError):
        return None


def _build_inventory_bytes(
    *,
    records: list[dict[str, Any]],
    master_key: bytes,
    media_dir: Path | None,
    audio_compat_dir: Path | None,
) -> tuple[bytes, dict[str, Any]]:
    original_store = ChunkedMediaStore(media_dir or Path("__missing_media__"))
    audio_store = ChunkedMediaStore(audio_compat_dir or Path("__missing_audio_compat__"))
    inventory = build_media_inventory(
        records=records,
        master_key=master_key,
        original_store=original_store,
        audio_store=audio_store,
        check_chunks=True,
    )
    return encode_media_inventory(master_key, inventory), inventory

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
    media_dir: Path | None = None,
    preview_dir: Path | None = None,
    audio_compat_dir: Path | None = None,
) -> BackupArtifact:
    """Create one verified core .lifevault v3 package in memory.

    v3 deliberately embeds the encrypted database, ordinary attachment ciphertext
    and small encrypted video previews, while original chunked media remain external.
    An encrypted media inventory records the external-media relationship needed for
    a full restore without leaking filenames or timeline metadata in the ZIP manifest.
    """

    created_at = datetime.now(timezone.utc)
    with tempfile.TemporaryDirectory(prefix="lifegraph-backup-") as temporary_dir:
        snapshot_path = Path(temporary_dir) / "lifegraph.db"
        database.create_consistent_snapshot(snapshot_path)
        integrity = database.verify_encrypted_snapshot(snapshot_path, master_key)
        database_bytes = snapshot_path.read_bytes()

    metadata_bytes = metadata_path.read_bytes()
    json.loads(metadata_bytes.decode("utf-8"))

    files: dict[str, bytes] = {
        "repository/vault.json": metadata_bytes,
        "repository/lifegraph.db": database_bytes,
    }
    records = database.list_all_attachments(master_key)
    attachment_store = AttachmentStore(attachment_dir) if attachment_dir is not None else None
    preview_store = MediaPreviewStore(preview_dir) if preview_dir is not None else None
    blob_count = 0
    preview_count = 0
    preview_skipped = 0

    for record in records:
        attachment_id = str(record["id"])
        if str(record.get("storage_kind") or "blob-v1") == "blob-v1":
            if attachment_store is None:
                raise DatabaseIntegrityError("仓库包含普通附件，但未提供附件目录")
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
            blob_count += 1

        preview_expected = bool(str(record.get("preview_nonce") or "").strip() and record.get("preview_media_type"))
        preview = _collect_verified_preview(
            preview_store=preview_store, master_key=master_key, record=record
        )
        if preview is not None:
            archive_name, path = preview
            files[archive_name] = path.read_bytes()
            preview_count += 1
        elif preview_expected:
            preview_skipped += 1

    inventory_bytes, inventory = _build_inventory_bytes(
        records=records,
        master_key=master_key,
        media_dir=media_dir,
        audio_compat_dir=audio_compat_dir,
    )
    files[MEDIA_INVENTORY_ARCHIVE_PATH] = inventory_bytes
    inventory_summary = dict(inventory.get("summary") or {})

    manifest = {
        "format": LIFEVAULT_FORMAT,
        "format_version": LIFEVAULT_FORMAT_VERSION,
        "created_at": created_at.isoformat(),
        "producer": {"name": "LifeGraph", "version": app_version},
        "repository": {
            "schema_version": integrity["schema_version"],
            "storage_mode": "sqlite+aead-field-encryption+encrypted-attachments",
            "backup_scope": "core",
            "external_media_policy": "chunked-v1-encrypted-inventory+external-mirror",
            "preview_policy": "embedded-core",
            "derived_media_policy": "regenerable-excluded",
            "full_backup_requires": ["core-lifevault", "data/media"],
        },
        "integrity": {
            "sqlite_quick_check": integrity["sqlite_quick_check"],
            "foreign_key_errors": integrity["foreign_key_errors"],
            "encrypted_records_verified": integrity["encrypted_records_verified"],
            "attachment_files_verified": blob_count,
            "preview_files_embedded": preview_count,
            "preview_files_skipped": preview_skipped,
            "external_media_records": int(inventory_summary.get("original_records") or 0),
            "external_media_bytes": int(inventory_summary.get("original_bytes") or 0),
            "external_media_online_at_backup": int(inventory_summary.get("online") or 0),
            "external_media_offline_at_backup": int(inventory_summary.get("offline") or 0),
            "external_media_incomplete_at_backup": int(inventory_summary.get("incomplete") or 0),
            "external_media_invalid_at_backup": int(inventory_summary.get("invalid") or 0),
            "audio_compat_records": int(inventory_summary.get("audio_compat_records") or 0),
        },
        "files": [_file_entry(path, value) for path, value in files.items()],
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
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
    media_dir: Path | None = None,
    preview_dir: Path | None = None,
    audio_compat_dir: Path | None = None,
) -> BackupFileArtifact:
    """Build a disk-backed .lifevault v3 core backup with bounded memory."""

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
        records = list(database.iter_all_attachments(master_key))
        attachment_store = AttachmentStore(attachment_dir) if attachment_dir is not None else None
        preview_store = MediaPreviewStore(preview_dir) if preview_dir is not None else None

        file_entries = [
            {
                "path": "repository/vault.json",
                "size": len(metadata_bytes),
                "sha256": sha256_bytes(metadata_bytes),
            },
            _path_file_entry("repository/lifegraph.db", snapshot_path),
        ]
        attachment_paths: list[tuple[str, Path]] = []
        preview_paths: list[tuple[str, Path]] = []
        blob_count = 0
        preview_count = 0
        preview_skipped = 0

        for record in records:
            attachment_id = str(record["id"])
            if str(record.get("storage_kind") or "blob-v1") == "blob-v1":
                if attachment_store is None:
                    raise DatabaseIntegrityError("仓库包含普通附件，但未提供附件目录")
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
                file_entries.append(_path_file_entry(archive_name, encrypted_path))
                attachment_paths.append((archive_name, encrypted_path))
                blob_count += 1
                del encrypted, plaintext

            preview_expected = bool(str(record.get("preview_nonce") or "").strip() and record.get("preview_media_type"))
            preview = _collect_verified_preview(
                preview_store=preview_store, master_key=master_key, record=record
            )
            if preview is not None:
                archive_name, path = preview
                file_entries.append(_path_file_entry(archive_name, path))
                preview_paths.append((archive_name, path))
                preview_count += 1
            elif preview_expected:
                preview_skipped += 1

        inventory_bytes, inventory = _build_inventory_bytes(
            records=records,
            master_key=master_key,
            media_dir=media_dir,
            audio_compat_dir=audio_compat_dir,
        )
        file_entries.append(_file_entry(MEDIA_INVENTORY_ARCHIVE_PATH, inventory_bytes))
        inventory_summary = dict(inventory.get("summary") or {})

        manifest = {
            "format": LIFEVAULT_FORMAT,
            "format_version": LIFEVAULT_FORMAT_VERSION,
            "created_at": created_at.isoformat(),
            "producer": {"name": "LifeGraph", "version": app_version},
            "repository": {
                "schema_version": integrity["schema_version"],
                "storage_mode": "sqlite+aead-field-encryption+encrypted-attachments",
                "backup_scope": "core",
                "external_media_policy": "chunked-v1-encrypted-inventory+external-mirror",
                "preview_policy": "embedded-core",
                "derived_media_policy": "regenerable-excluded",
                "full_backup_requires": ["core-lifevault", "data/media"],
            },
            "integrity": {
                "sqlite_quick_check": integrity["sqlite_quick_check"],
                "foreign_key_errors": integrity["foreign_key_errors"],
                "encrypted_records_verified": integrity["encrypted_records_verified"],
                "attachment_files_verified": blob_count,
                "preview_files_embedded": preview_count,
                "preview_files_skipped": preview_skipped,
                "external_media_records": int(inventory_summary.get("original_records") or 0),
                "external_media_bytes": int(inventory_summary.get("original_bytes") or 0),
                "external_media_online_at_backup": int(inventory_summary.get("online") or 0),
                "external_media_offline_at_backup": int(inventory_summary.get("offline") or 0),
                "external_media_incomplete_at_backup": int(inventory_summary.get("incomplete") or 0),
                "external_media_invalid_at_backup": int(inventory_summary.get("invalid") or 0),
                "audio_compat_records": int(inventory_summary.get("audio_compat_records") or 0),
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
                archive.writestr(MEDIA_INVENTORY_ARCHIVE_PATH, inventory_bytes)
                for archive_name, encrypted_path in attachment_paths:
                    archive.write(encrypted_path, archive_name)
                for archive_name, preview_path in preview_paths:
                    archive.write(preview_path, archive_name)
            # Windows may reject FlushFileBuffers/fsync on a read-only handle.
            # Re-open writable before the durability barrier so disk-backed export
            # behaves consistently across Windows and POSIX.
            with temp_output.open("r+b") as stream:
                stream.flush()
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
    """Inspect a disk-backed .lifevault without loading large payloads."""
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
            preview_paths = {
                name for name in name_set
                if name.startswith("repository/previews/") and name.endswith(".lgpreview")
            }
            if format_version == 1:
                if name_set != LIFEVAULT_BASE_PATHS:
                    raise LifeVaultPackageError("v1 备份包目录结构无效")
            elif format_version == 2:
                if name_set != LIFEVAULT_BASE_PATHS | attachment_paths:
                    raise LifeVaultPackageError("v2 备份包含无效文件路径")
            else:
                required = LIFEVAULT_BASE_PATHS | {MEDIA_INVENTORY_ARCHIVE_PATH}
                if name_set != required | attachment_paths | preview_paths:
                    raise LifeVaultPackageError("v3 备份包含无效文件路径")
            for name in attachment_paths:
                attachment_id = name.removeprefix("repository/attachments/").removesuffix(".lgatt")
                if not attachment_id or "/" in attachment_id or "\\" in attachment_id:
                    raise LifeVaultPackageError("附件备份路径无效")
            for name in preview_paths:
                attachment_id = name.removeprefix("repository/previews/").removesuffix(".lgpreview")
                if not attachment_id or "/" in attachment_id or "\\" in attachment_id:
                    raise LifeVaultPackageError("视频封面备份路径无效")

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
            media_inventory_bytes = (
                archive.read(MEDIA_INVENTORY_ARCHIVE_PATH)
                if format_version == 3 else None
            )
            return {
                "manifest": manifest,
                "metadata_bytes": metadata_bytes,
                "media_inventory_bytes": media_inventory_bytes,
                "package_sha256": sha256_file(path),
            }
    except LifeVaultPackageError:
        raise
    except (zipfile.BadZipFile, KeyError, OSError, RuntimeError, EOFError, zlib.error, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LifeVaultPackageError("无法读取 .lifevault 备份包") from exc


def verify_lifevault_file(path: Path, master_key: bytes) -> dict[str, Any]:
    """Fully verify a disk-backed package while keeping external media external."""
    inspected = inspect_lifevault_file(path, verify_checksums=True)
    manifest = inspected["manifest"]
    format_version = int(manifest.get("format_version") or 0)
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
                records = list(database.iter_all_attachments(master_key))

                remaining_attachments = {
                    name for name in archive.namelist()
                    if name.startswith("repository/attachments/") and name.endswith(".lgatt")
                }
                remaining_previews = {
                    name for name in archive.namelist()
                    if name.startswith("repository/previews/") and name.endswith(".lgpreview")
                }
                attachment_count = 0
                preview_count = 0
                preview_missing = 0
                external_media_records = 0
                for record in records:
                    attachment_id = str(record["id"])
                    if str(record.get("storage_kind") or "blob-v1") == "blob-v1":
                        archive_name = f"repository/attachments/{attachment_id}.lgatt"
                        if archive_name not in remaining_attachments:
                            raise LifeVaultPackageError("备份附件文件与数据库附件记录不一致")
                        remaining_attachments.remove(archive_name)
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
                        attachment_count += 1
                    else:
                        external_media_records += 1

                    nonce_text = str(record.get("preview_nonce") or "").strip()
                    if format_version >= 3 and nonce_text and record.get("preview_media_type"):
                        preview_name = _preview_archive_name(attachment_id)
                        if preview_name not in remaining_previews:
                            # v3 core backups may intentionally omit a missing or
                            # corrupt derived preview. The encrypted source record
                            # and original media remain recoverable; the preview can
                            # be regenerated later.
                            preview_missing += 1
                        else:
                            remaining_previews.remove(preview_name)
                            encrypted_preview = archive.read(preview_name)
                            try:
                                preview = decrypt_bytes(
                                    master_key,
                                    b64d(nonce_text),
                                    encrypted_preview,
                                    aad=media_preview_aad(attachment_id),
                                )
                            except Exception as exc:
                                raise LifeVaultPackageError(f"视频封面 {attachment_id} 无法解密验证") from exc
                            if len(preview) != int(record.get("preview_size_bytes") or -1):
                                raise LifeVaultPackageError(f"视频封面 {attachment_id} 大小校验失败")
                            if hashlib.sha256(preview).hexdigest() != str(record.get("preview_sha256") or ""):
                                raise LifeVaultPackageError(f"视频封面 {attachment_id} SHA-256 校验失败")
                            preview_count += 1

                if remaining_attachments:
                    raise LifeVaultPackageError("备份附件文件与数据库附件记录不一致")
                if remaining_previews:
                    raise LifeVaultPackageError("备份视频封面与数据库记录不一致")

                inventory_report: dict[str, Any] = {
                    "external_media_records": external_media_records,
                    "external_media_bytes": sum(
                        int(record.get("size_bytes") or 0)
                        for record in records
                        if str(record.get("storage_kind") or "blob-v1") == "chunked-v1"
                    ),
                    "audio_compat_records": sum(1 for record in records if record.get("audio_compat_media_id")),
                }
                if format_version >= 3:
                    raw_inventory = inspected.get("media_inventory_bytes")
                    if not raw_inventory:
                        raise LifeVaultPackageError("v3 备份缺少媒体清单")
                    inventory = decode_media_inventory(master_key, raw_inventory)
                    try:
                        inventory_report.update(validate_inventory_against_records(inventory, records))
                    except ValueError as exc:
                        raise LifeVaultPackageError(str(exc)) from exc
                    summary = inventory.get("summary") if isinstance(inventory.get("summary"), dict) else {}
                    inventory_report.update({
                        "external_media_online_at_backup": int(summary.get("online") or 0),
                        "external_media_offline_at_backup": int(summary.get("offline") or 0),
                        "external_media_incomplete_at_backup": int(summary.get("incomplete") or 0),
                        "external_media_invalid_at_backup": int(summary.get("invalid") or 0),
                    })

                result["attachment_files_verified"] = attachment_count
                result["preview_files_verified"] = preview_count
                result["preview_files_missing"] = preview_missing
                result.update(inventory_report)
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
    """Validate an in-memory package structure and checksums before decryption."""

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
            preview_files = {
                name.removeprefix("repository/previews/").removesuffix(".lgpreview"): archive.read(name)
                for name in names
                if name.startswith("repository/previews/") and name.endswith(".lgpreview")
            }
            media_inventory_bytes = (
                archive.read(MEDIA_INVENTORY_ARCHIVE_PATH)
                if MEDIA_INVENTORY_ARCHIVE_PATH in name_set else None
            )
    except LifeVaultPackageError:
        raise
    except (zipfile.BadZipFile, KeyError, OSError, RuntimeError, EOFError, zlib.error) as exc:
        raise LifeVaultPackageError("无法读取 .lifevault 备份包") from exc

    try:
        manifest = _require_mapping(json.loads(manifest_bytes.decode("utf-8")), "manifest.json")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LifeVaultPackageError("manifest.json 不是有效 JSON") from exc

    if manifest.get("format") != LIFEVAULT_FORMAT:
        raise LifeVaultPackageError("备份包格式标识不正确")
    format_version = manifest.get("format_version")
    if format_version not in SUPPORTED_LIFEVAULT_FORMAT_VERSIONS:
        raise LifeVaultPackageError("暂不支持此 .lifevault 格式版本")

    actual_paths = set(names)
    attachment_paths = {f"repository/attachments/{attachment_id}.lgatt" for attachment_id in attachment_files}
    preview_paths = {f"repository/previews/{attachment_id}.lgpreview" for attachment_id in preview_files}
    if format_version == 1:
        if actual_paths != LIFEVAULT_BASE_PATHS or attachment_files or preview_files:
            raise LifeVaultPackageError("v1 备份包目录结构无效")
    elif format_version == 2:
        if actual_paths != LIFEVAULT_BASE_PATHS | attachment_paths or preview_files:
            raise LifeVaultPackageError("v2 备份包含无效文件路径")
    else:
        expected = LIFEVAULT_BASE_PATHS | {MEDIA_INVENTORY_ARCHIVE_PATH} | attachment_paths | preview_paths
        if actual_paths != expected or media_inventory_bytes is None:
            raise LifeVaultPackageError("v3 备份包含无效文件路径")

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
        **{f"repository/attachments/{attachment_id}.lgatt": value for attachment_id, value in attachment_files.items()},
        **{f"repository/previews/{attachment_id}.lgpreview": value for attachment_id, value in preview_files.items()},
    }
    if media_inventory_bytes is not None:
        expected_values[MEDIA_INVENTORY_ARCHIVE_PATH] = media_inventory_bytes
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
        metadata = _require_mapping(json.loads(metadata_bytes.decode("utf-8")), "vault.json")
        key_slots = _require_mapping(metadata.get("key_slots"), "vault.json key_slots")
        _require_mapping(key_slots.get("pin"), "PIN 密钥槽")
        _require_mapping(key_slots.get("recovery"), "恢复密钥槽")
        verification = _require_mapping(metadata.get("verification"), "vault.json verification")
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
        preview_files=preview_files,
        media_inventory_bytes=media_inventory_bytes,
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
            database.initialize_schema()
            result = database.verify_encrypted_snapshot(database_path, master_key)
            records = database.list_all_attachments(master_key)
            blob_records = [
                record for record in records
                if str(record.get("storage_kind") or "blob-v1") == "blob-v1"
            ]
            expected_ids = {str(record["id"]) for record in blob_records}
            if expected_ids != set(package.attachment_files):
                raise LifeVaultPackageError("备份普通附件文件与数据库附件记录不一致")
            for record in blob_records:
                attachment_id = str(record["id"])
                try:
                    plaintext = decrypt_bytes(
                        master_key,
                        record["file_nonce"],
                        package.attachment_files[attachment_id],
                        aad=attachment_aad(attachment_id),
                    )
                except Exception as exc:
                    raise LifeVaultPackageError(f"附件 {attachment_id} 无法解密验证") from exc
                if len(plaintext) != int(record.get("size_bytes") or -1):
                    raise LifeVaultPackageError(f"附件 {attachment_id} 大小校验失败")
                if hashlib.sha256(plaintext).hexdigest() != record.get("sha256"):
                    raise LifeVaultPackageError(f"附件 {attachment_id} SHA-256 校验失败")

            format_version = int(package.manifest.get("format_version") or 0)
            preview_records = [
                record for record in records
                if str(record.get("preview_nonce") or "").strip() and record.get("preview_media_type")
            ]
            if format_version >= 3:
                preview_by_id = {str(record["id"]): record for record in preview_records}
                if not set(package.preview_files).issubset(preview_by_id):
                    raise LifeVaultPackageError("备份视频封面文件与数据库记录不一致")
                for attachment_id, encrypted_preview in package.preview_files.items():
                    record = preview_by_id[attachment_id]
                    try:
                        preview = decrypt_bytes(
                            master_key,
                            b64d(str(record["preview_nonce"])),
                            encrypted_preview,
                            aad=media_preview_aad(attachment_id),
                        )
                    except Exception as exc:
                        raise LifeVaultPackageError(f"视频封面 {attachment_id} 无法解密验证") from exc
                    if len(preview) != int(record.get("preview_size_bytes") or -1):
                        raise LifeVaultPackageError(f"视频封面 {attachment_id} 大小校验失败")
                    if hashlib.sha256(preview).hexdigest() != str(record.get("preview_sha256") or ""):
                        raise LifeVaultPackageError(f"视频封面 {attachment_id} SHA-256 校验失败")

            inventory_report = {
                "external_media_records": sum(
                    1 for record in records
                    if str(record.get("storage_kind") or "blob-v1") == "chunked-v1"
                ),
                "external_media_bytes": sum(
                    int(record.get("size_bytes") or 0) for record in records
                    if str(record.get("storage_kind") or "blob-v1") == "chunked-v1"
                ),
                "audio_compat_records": sum(1 for record in records if record.get("audio_compat_media_id")),
            }
            if format_version >= 3:
                if not package.media_inventory_bytes:
                    raise LifeVaultPackageError("v3 备份缺少媒体清单")
                inventory = decode_media_inventory(master_key, package.media_inventory_bytes)
                try:
                    inventory_report.update(validate_inventory_against_records(inventory, records))
                except ValueError as exc:
                    raise LifeVaultPackageError(str(exc)) from exc
                summary = inventory.get("summary") if isinstance(inventory.get("summary"), dict) else {}
                inventory_report.update({
                    "external_media_online_at_backup": int(summary.get("online") or 0),
                    "external_media_offline_at_backup": int(summary.get("offline") or 0),
                    "external_media_incomplete_at_backup": int(summary.get("incomplete") or 0),
                    "external_media_invalid_at_backup": int(summary.get("invalid") or 0),
                })

            result["attachment_files_verified"] = len(blob_records)
            result["preview_files_verified"] = len(package.preview_files) if format_version >= 3 else 0
            result.update(inventory_report)
            result["source_schema_version"] = actual_schema
            return result
        except LifeVaultPackageError:
            raise
        except Exception as exc:
            raise LifeVaultPackageError(f"备份数据库无法验证：{exc}") from exc

