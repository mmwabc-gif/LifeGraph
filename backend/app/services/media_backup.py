from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from typing import Any, Callable


MEDIA_BACKUP_FORMAT = "lifegraph-media-backup"
MEDIA_BACKUP_VERSION = 1
MEDIA_BACKUP_MANIFEST = "lifegraph-media-backup.json"
_COPY_BUFFER = 1024 * 1024
_BACKUP_DISK_RESERVE_MIN = 256 * 1024 * 1024
_BACKUP_DISK_RESERVE_MAX = 2 * 1024 * 1024 * 1024


class MediaBackupError(ValueError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def inventory_fingerprint(original_media: list[dict[str, Any]]) -> str:
    canonical = [
        {
            "media_id": str(item.get("media_id") or ""),
            "size_bytes": _safe_int(item.get("size_bytes")),
            "sha256": str(item.get("sha256") or ""),
            "chunk_size": _safe_int(item.get("chunk_size")),
            "chunk_count": _safe_int(item.get("chunk_count")),
        }
        for item in original_media
    ]
    canonical.sort(key=lambda item: item["media_id"])
    payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _read_manifest(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise MediaBackupError(f"媒体备份清单无法读取：{exc}") from exc
    if not isinstance(value, dict) or value.get("format") != MEDIA_BACKUP_FORMAT or value.get("version") != MEDIA_BACKUP_VERSION:
        raise MediaBackupError("媒体备份清单格式不受支持")
    return value


def _write_manifest(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, path)
    except OSError as exc:
        temp.unlink(missing_ok=True)
        raise MediaBackupError(f"媒体备份清单无法写入：{exc}") from exc


def _sha256_file(path: Path, *, cancel_event: Event | None = None) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    raise MediaBackupError("媒体备份任务已取消")
                block = stream.read(_COPY_BUFFER)
                if not block:
                    break
                digest.update(block)
    except OSError as exc:
        raise MediaBackupError(f"文件无法读取：{path.name}：{exc}") from exc
    return digest.hexdigest()


def _copy_file_atomic(
    source: Path,
    destination: Path,
    *,
    cancel_event: Event | None = None,
) -> tuple[int, str]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name(destination.name + ".part")
    digest = hashlib.sha256()
    copied = 0
    try:
        with source.open("rb") as src, temp.open("wb") as dst:
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    raise MediaBackupError("媒体备份任务已取消")
                block = src.read(_COPY_BUFFER)
                if not block:
                    break
                dst.write(block)
                digest.update(block)
                copied += len(block)
        try:
            shutil.copystat(source, temp)
        except OSError:
            pass
        os.replace(temp, destination)
    except MediaBackupError:
        temp.unlink(missing_ok=True)
        raise
    except OSError as exc:
        temp.unlink(missing_ok=True)
        raise MediaBackupError(f"媒体文件复制失败：{source.name}：{exc}") from exc
    return copied, digest.hexdigest()


def _source_files(source_root: Path, original_media: list[dict[str, Any]]) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for item in original_media:
        if str(item.get("state_at_backup") or "") != "online":
            raise MediaBackupError("大型媒体库存在离线、不完整或异常项目，请先修复后再执行独立备份")
        relative_dir = str(item.get("relative_path") or "").replace("\\", "/").strip("/")
        media_id = str(item.get("media_id") or "")
        chunk_count = _safe_int(item.get("chunk_count"))
        candidates = [(f"{relative_dir}/manifest.lgmedia", source_root / relative_dir / "manifest.lgmedia")]
        candidates.extend(
            (f"{relative_dir}/chunks/{index:08d}.lgchunk", source_root / relative_dir / "chunks" / f"{index:08d}.lgchunk")
            for index in range(chunk_count)
        )
        for relative_path, path in candidates:
            try:
                stat = path.stat()
            except OSError as exc:
                raise MediaBackupError(f"大型媒体 {media_id} 缺少必要文件：{path.name}") from exc
            if not path.is_file():
                raise MediaBackupError(f"大型媒体 {media_id} 缺少必要文件：{path.name}")
            files.append(
                {
                    "path": relative_path,
                    "source": path,
                    "size": stat.st_size,
                    "source_mtime_ns": stat.st_mtime_ns,
                }
            )
    return files


def inspect_media_backup_target(target_root: Path, original_media: list[dict[str, Any]]) -> dict[str, Any]:
    target = Path(target_root)
    manifest_path = target / MEDIA_BACKUP_MANIFEST
    fingerprint = inventory_fingerprint(original_media)
    result: dict[str, Any] = {
        "configured": True,
        "target_path": str(target),
        "state": "missing",
        "current": False,
        "last_synced_at": None,
        "last_verified_at": None,
        "backup_files": 0,
        "backup_bytes": 0,
    }
    try:
        manifest = _read_manifest(manifest_path)
    except MediaBackupError as exc:
        result.update({"state": "invalid", "message": str(exc)})
        return result
    if manifest is None:
        result["message"] = "尚未在该目录建立大型媒体备份"
        return result
    current = str(manifest.get("inventory_fingerprint") or "") == fingerprint
    files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    result.update(
        {
            "state": "synced" if current else "stale",
            "current": current,
            "message": "大型媒体备份已与当前仓库同步" if current else "备份目录存在，但媒体库已有变化，需要再次增量备份",
            "last_synced_at": manifest.get("generated_at"),
            "last_verified_at": manifest.get("verified_at"),
            "backup_files": len(files),
            "backup_bytes": sum(_safe_int(item.get("size")) for item in files if isinstance(item, dict)),
        }
    )
    return result


def sync_media_backup(
    *,
    source_root: Path,
    target_root: Path,
    original_media: list[dict[str, Any]],
    progress: Callable[[dict[str, Any]], None] | None = None,
    cancel_event: Event | None = None,
) -> dict[str, Any]:
    source_root = source_root.resolve()
    target_root = target_root.resolve()
    try:
        target_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise MediaBackupError(f"媒体备份目录无法创建或访问：{exc}") from exc
    files = _source_files(source_root, original_media)
    target_media = target_root / "media"
    manifest_path = target_root / MEDIA_BACKUP_MANIFEST
    previous = _read_manifest(manifest_path)
    previous_by_path = {
        str(item.get("path") or ""): item
        for item in ((previous or {}).get("files") or [])
        if isinstance(item, dict)
    }
    total_bytes = sum(item["size"] for item in files)
    plan: list[tuple[dict[str, Any], bool]] = []
    required_copy_bytes = 0
    for item in files:
        relative_path = item["path"]
        destination = target_media / Path(relative_path)
        previous_item = previous_by_path.get(relative_path)
        can_skip = False
        if previous_item:
            try:
                can_skip = (
                    _safe_int(previous_item.get("size")) == item["size"]
                    and _safe_int(previous_item.get("source_mtime_ns")) == item["source_mtime_ns"]
                    and destination.is_file()
                    and destination.stat().st_size == item["size"]
                    and bool(previous_item.get("sha256"))
                )
            except OSError:
                can_skip = False
        plan.append((item, can_skip))
        if not can_skip:
            required_copy_bytes += item["size"]

    if required_copy_bytes:
        reserve = min(
            _BACKUP_DISK_RESERVE_MAX,
            max(_BACKUP_DISK_RESERVE_MIN, int(required_copy_bytes * 0.01)),
        )
        try:
            free_bytes = int(shutil.disk_usage(target_root).free)
        except OSError as exc:
            raise MediaBackupError(f"无法读取备份磁盘剩余空间：{exc}") from exc
        if free_bytes < required_copy_bytes + reserve:
            raise MediaBackupError(
                f"备份磁盘剩余空间不足：当前约 {free_bytes / 1024**3:.2f} GB，"
                f"本次增量复制安全需要约 {(required_copy_bytes + reserve) / 1024**3:.2f} GB"
            )

    done_bytes = 0
    copied_bytes = 0
    copied_files = 0
    skipped_files = 0
    output_files: list[dict[str, Any]] = []

    def emit(current: str = "") -> None:
        if progress:
            progress(
                {
                    "total_files": len(files),
                    "completed_files": copied_files + skipped_files,
                    "total_bytes": total_bytes,
                    "completed_bytes": done_bytes,
                    "copied_files": copied_files,
                    "copied_bytes": copied_bytes,
                    "skipped_files": skipped_files,
                    "current_file": current,
                }
            )

    emit()
    for item, can_skip in plan:
        if cancel_event is not None and cancel_event.is_set():
            raise MediaBackupError("媒体备份任务已取消")
        relative_path = item["path"]
        destination = target_media / Path(relative_path)
        previous_item = previous_by_path.get(relative_path)
        if can_skip:
            sha256 = str(previous_item.get("sha256") or "")
            skipped_files += 1
        else:
            _, sha256 = _copy_file_atomic(item["source"], destination, cancel_event=cancel_event)
            copied_files += 1
            copied_bytes += item["size"]
        done_bytes += item["size"]
        output_files.append(
            {
                "path": relative_path,
                "size": item["size"],
                "source_mtime_ns": item["source_mtime_ns"],
                "sha256": sha256,
            }
        )
        emit(relative_path)

    manifest = {
        "format": MEDIA_BACKUP_FORMAT,
        "version": MEDIA_BACKUP_VERSION,
        "generated_at": _utc_now(),
        "verified_at": None,
        "inventory_fingerprint": inventory_fingerprint(original_media),
        "media_records": len(original_media),
        "plaintext_bytes": sum(_safe_int(item.get("size_bytes")) for item in original_media),
        "files": output_files,
    }
    _write_manifest(manifest_path, manifest)
    return {
        "state": "synced",
        "current": True,
        "target_path": str(target_root),
        "last_synced_at": manifest["generated_at"],
        "backup_files": len(output_files),
        "backup_bytes": total_bytes,
        "copied_files": copied_files,
        "copied_bytes": copied_bytes,
        "skipped_files": skipped_files,
    }


def verify_media_backup(
    *,
    target_root: Path,
    original_media: list[dict[str, Any]],
    progress: Callable[[dict[str, Any]], None] | None = None,
    cancel_event: Event | None = None,
) -> dict[str, Any]:
    target_root = target_root.resolve()
    manifest_path = target_root / MEDIA_BACKUP_MANIFEST
    manifest = _read_manifest(manifest_path)
    if manifest is None:
        raise MediaBackupError("该目录尚未建立大型媒体备份")
    if str(manifest.get("inventory_fingerprint") or "") != inventory_fingerprint(original_media):
        raise MediaBackupError("媒体备份已落后于当前仓库，请先执行增量备份")
    files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    total_bytes = sum(_safe_int(item.get("size")) for item in files if isinstance(item, dict))
    done_bytes = 0
    verified_files = 0
    for item in files:
        if not isinstance(item, dict):
            continue
        if cancel_event is not None and cancel_event.is_set():
            raise MediaBackupError("媒体备份任务已取消")
        relative_path = str(item.get("path") or "")
        path = target_root / "media" / Path(relative_path)
        expected_size = _safe_int(item.get("size"))
        expected_hash = str(item.get("sha256") or "")
        try:
            if not path.is_file() or path.stat().st_size != expected_size:
                raise MediaBackupError(f"媒体备份文件缺失或大小异常：{relative_path}")
        except OSError as exc:
            raise MediaBackupError(f"媒体备份文件无法访问：{relative_path}") from exc
        actual_hash = _sha256_file(path, cancel_event=cancel_event)
        if actual_hash != expected_hash:
            raise MediaBackupError(f"媒体备份校验失败：{relative_path}")
        done_bytes += expected_size
        verified_files += 1
        if progress:
            progress(
                {
                    "total_files": len(files),
                    "completed_files": verified_files,
                    "total_bytes": total_bytes,
                    "completed_bytes": done_bytes,
                    "verified_files": verified_files,
                    "current_file": relative_path,
                }
            )
    verified_at = _utc_now()
    manifest["verified_at"] = verified_at
    _write_manifest(manifest_path, manifest)
    return {
        "state": "verified",
        "current": True,
        "target_path": str(target_root),
        "last_synced_at": manifest.get("generated_at"),
        "last_verified_at": verified_at,
        "backup_files": len(files),
        "backup_bytes": total_bytes,
        "verified_files": verified_files,
    }
