from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from app.services.large_files import ChunkedMediaStore, LargeFileError


MEDIA_INVENTORY_FORMAT = "lifegraph-media-inventory"
MEDIA_INVENTORY_FORMAT_VERSION = 1


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def inspect_chunked_asset(
    store: ChunkedMediaStore,
    master_key: bytes,
    *,
    media_id: str,
    expected_size: int | None = None,
    expected_sha256: str | None = None,
    expected_chunk_size: int | None = None,
    expected_chunk_count: int | None = None,
    check_chunks: bool = False,
) -> dict[str, Any]:
    """Inspect one encrypted chunked asset without reading its plaintext payload.

    `online` means the encrypted manifest exists, authenticates, matches the database
    index, and (when requested) all expected chunk files are present. It intentionally
    avoids decrypting every multi-GB chunk; deep payload verification remains a
    separate expensive operation.
    """

    clean_id = str(media_id or "").strip()
    if not clean_id:
        return {"state": "invalid", "message": "媒体标识缺失", "media_id": clean_id}

    try:
        media_dir = store.media_dir(clean_id)
        manifest_path = store.manifest_path(clean_id)
    except LargeFileError as exc:
        return {"state": "invalid", "message": str(exc), "media_id": clean_id}

    try:
        if not media_dir.exists() or not manifest_path.is_file():
            return {
                "state": "offline",
                "message": "媒体文件离线或尚未恢复",
                "media_id": clean_id,
                "chunk_files_present": 0,
            }
    except OSError as exc:
        return {
            "state": "invalid",
            "message": f"媒体目录无法访问：{exc}",
            "media_id": clean_id,
        }

    try:
        manifest = store.read_manifest(master_key, clean_id)
    except LargeFileError as exc:
        return {
            "state": "invalid",
            "message": f"媒体清单无法验证：{exc}",
            "media_id": clean_id,
        }

    size_bytes = _safe_int(manifest.get("size_bytes"))
    chunk_size = _safe_int(manifest.get("chunk_size"))
    chunk_count = _safe_int(manifest.get("chunk_count"))
    sha256 = str(manifest.get("sha256") or "")
    expected_values = (
        ("size_bytes", expected_size, size_bytes),
        ("chunk_size", expected_chunk_size, chunk_size),
        ("chunk_count", expected_chunk_count, chunk_count),
        ("sha256", expected_sha256, sha256),
    )
    mismatches = [name for name, expected, actual in expected_values if expected not in (None, "") and expected != actual]
    if mismatches:
        return {
            "state": "invalid",
            "message": f"媒体清单与资料索引不一致：{', '.join(mismatches)}",
            "media_id": clean_id,
            "size_bytes": size_bytes,
            "chunk_size": chunk_size,
            "chunk_count": chunk_count,
            "sha256": sha256,
        }

    result: dict[str, Any] = {
        "state": "online",
        "message": "媒体库在线",
        "media_id": clean_id,
        "size_bytes": size_bytes,
        "chunk_size": chunk_size,
        "chunk_count": chunk_count,
        "sha256": sha256,
        "relative_path": f"{store.shard_for(clean_id)}/{clean_id}",
    }
    if not check_chunks:
        return result

    present = 0
    missing = 0
    try:
        encrypted_bytes = manifest_path.stat().st_size
    except OSError:
        encrypted_bytes = 0
    for index in range(max(0, chunk_count)):
        path = store.chunk_path(clean_id, index)
        try:
            exists = path.is_file()
        except OSError:
            exists = False
        if exists:
            present += 1
            try:
                encrypted_bytes += path.stat().st_size
            except OSError:
                pass
        else:
            missing += 1
    result["chunk_files_present"] = present
    result["chunk_files_missing"] = missing
    result["encrypted_bytes_on_disk"] = encrypted_bytes
    if missing:
        result["state"] = "incomplete"
        result["message"] = f"媒体库缺少 {missing} 个分块"
    return result




def _relative_media_path(store: ChunkedMediaStore, media_id: str) -> str | None:
    if not media_id:
        return None
    try:
        return f"{store.shard_for(media_id)}/{media_id}"
    except LargeFileError:
        return None


def build_media_inventory(
    *,
    records: Iterable[dict[str, Any]],
    master_key: bytes,
    original_store: ChunkedMediaStore,
    audio_store: ChunkedMediaStore | None = None,
    check_chunks: bool = True,
) -> dict[str, Any]:
    """Build an opaque-ID inventory for the external media layer.

    Filenames, timeline dates and content titles are deliberately excluded. The
    inventory is itself encrypted before being placed in .lifevault v3.
    """

    originals: list[dict[str, Any]] = []
    derivatives: list[dict[str, Any]] = []
    summary = {
        "original_records": 0,
        "original_bytes": 0,
        "original_chunks": 0,
        "online": 0,
        "offline": 0,
        "incomplete": 0,
        "invalid": 0,
        "audio_compat_records": 0,
        "audio_compat_bytes": 0,
        "audio_compat_online": 0,
        "audio_compat_offline": 0,
    }

    for record in records:
        if str(record.get("storage_kind") or "blob-v1") == "chunked-v1":
            media_id = str(record.get("media_id") or "").strip()
            expected_size = _safe_int(record.get("size_bytes"))
            expected_chunk_size = _safe_int(record.get("chunk_size"))
            expected_chunk_count = _safe_int(record.get("chunk_count")) or (
                math.ceil(expected_size / expected_chunk_size)
                if expected_size > 0 and expected_chunk_size > 0 else 0
            )
            status = inspect_chunked_asset(
                original_store,
                master_key,
                media_id=media_id,
                expected_size=expected_size,
                expected_sha256=str(record.get("sha256") or ""),
                expected_chunk_size=expected_chunk_size,
                expected_chunk_count=expected_chunk_count,
                check_chunks=check_chunks,
            )
            state = str(status.get("state") or "invalid")
            entry = {
                "attachment_id": str(record.get("id") or ""),
                "media_id": media_id,
                "size_bytes": expected_size,
                "sha256": str(record.get("sha256") or ""),
                "chunk_size": expected_chunk_size,
                "chunk_count": expected_chunk_count,
                "state_at_backup": state,
                "relative_path": status.get("relative_path") or _relative_media_path(original_store, media_id),
            }
            if "chunk_files_present" in status:
                entry["chunk_files_present"] = _safe_int(status.get("chunk_files_present"))
                entry["chunk_files_missing"] = _safe_int(status.get("chunk_files_missing"))
            originals.append(entry)
            summary["original_records"] += 1
            summary["original_bytes"] += max(0, expected_size)
            summary["original_chunks"] += max(0, expected_chunk_count)
            summary[state] = summary.get(state, 0) + 1

        compat_id = str(record.get("audio_compat_media_id") or "").strip()
        if compat_id:
            compat_size = _safe_int(record.get("audio_compat_size_bytes"))
            compat_chunk_size = _safe_int(record.get("audio_compat_chunk_size"))
            compat_sha = str(record.get("audio_compat_sha256") or "")
            compat_status = (
                inspect_chunked_asset(
                    audio_store,
                    master_key,
                    media_id=compat_id,
                    expected_size=compat_size,
                    expected_sha256=compat_sha,
                    expected_chunk_size=compat_chunk_size,
                    check_chunks=check_chunks,
                )
                if audio_store is not None
                else {"state": "offline"}
            )
            compat_state = str(compat_status.get("state") or "offline")
            derivatives.append(
                {
                    "attachment_id": str(record.get("id") or ""),
                    "kind": "browser-audio-compat",
                    "media_id": compat_id,
                    "size_bytes": compat_size,
                    "sha256": compat_sha,
                    "chunk_size": compat_chunk_size,
                    "codec": str(record.get("audio_compat_codec") or ""),
                    "state_at_backup": compat_state,
                    "backup_policy": "regenerable-excluded",
                }
            )
            summary["audio_compat_records"] += 1
            summary["audio_compat_bytes"] += max(0, compat_size)
            if compat_state == "online":
                summary["audio_compat_online"] += 1
            else:
                summary["audio_compat_offline"] += 1

    return {
        "format": MEDIA_INVENTORY_FORMAT,
        "format_version": MEDIA_INVENTORY_FORMAT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": {
            "core_backup": "lifevault-v3",
            "original_media": "external-required-for-full-restore",
            "previews": "embedded-in-core",
            "audio_compat": "regenerable-excluded",
        },
        "original_media": originals,
        "derivatives": derivatives,
        "summary": summary,
    }


def validate_inventory_against_records(
    inventory: dict[str, Any], records: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    if inventory.get("format") != MEDIA_INVENTORY_FORMAT:
        raise ValueError("媒体清单格式标识不正确")
    if inventory.get("format_version") != MEDIA_INVENTORY_FORMAT_VERSION:
        raise ValueError("媒体清单格式版本不受支持")

    records_list = list(records)
    expected_originals = {
        str(record.get("id") or ""): record
        for record in records_list
        if str(record.get("storage_kind") or "blob-v1") == "chunked-v1"
    }
    actual_originals = {
        str(item.get("attachment_id") or ""): item
        for item in inventory.get("original_media") or []
        if isinstance(item, dict)
    }
    if set(expected_originals) != set(actual_originals):
        raise ValueError("媒体清单与数据库大型资料记录不一致")
    for attachment_id, record in expected_originals.items():
        item = actual_originals[attachment_id]
        comparisons = {
            "media_id": str(record.get("media_id") or ""),
            "size_bytes": _safe_int(record.get("size_bytes")),
            "sha256": str(record.get("sha256") or ""),
            "chunk_size": _safe_int(record.get("chunk_size")),
            "chunk_count": _safe_int(record.get("chunk_count")),
        }
        for key, expected in comparisons.items():
            if item.get(key) != expected:
                raise ValueError(f"媒体清单 {attachment_id} 的 {key} 与数据库不一致")

    expected_derivatives = {
        str(record.get("id") or ""): record
        for record in records_list
        if str(record.get("audio_compat_media_id") or "").strip()
    }
    actual_derivatives = {
        str(item.get("attachment_id") or ""): item
        for item in inventory.get("derivatives") or []
        if isinstance(item, dict) and item.get("kind") == "browser-audio-compat"
    }
    if set(expected_derivatives) != set(actual_derivatives):
        raise ValueError("媒体清单与数据库兼容音轨记录不一致")
    for attachment_id, record in expected_derivatives.items():
        item = actual_derivatives[attachment_id]
        if item.get("media_id") != str(record.get("audio_compat_media_id") or ""):
            raise ValueError(f"媒体清单 {attachment_id} 的兼容音轨标识不一致")
        if _safe_int(item.get("size_bytes")) != _safe_int(record.get("audio_compat_size_bytes")):
            raise ValueError(f"媒体清单 {attachment_id} 的兼容音轨大小不一致")
        if str(item.get("sha256") or "") != str(record.get("audio_compat_sha256") or ""):
            raise ValueError(f"媒体清单 {attachment_id} 的兼容音轨摘要不一致")

    summary = inventory.get("summary") if isinstance(inventory.get("summary"), dict) else {}
    return {
        "external_media_records": len(expected_originals),
        "external_media_bytes": sum(_safe_int(record.get("size_bytes")) for record in expected_originals.values()),
        "external_media_online_at_backup": _safe_int(summary.get("online")),
        "external_media_offline_at_backup": _safe_int(summary.get("offline")),
        "external_media_incomplete_at_backup": _safe_int(summary.get("incomplete")),
        "external_media_invalid_at_backup": _safe_int(summary.get("invalid")),
        "audio_compat_records": len(expected_derivatives),
    }


def verify_original_media_library(
    *,
    store: ChunkedMediaStore,
    master_key: bytes,
    original_media: list[dict[str, Any]],
    progress: Callable[[dict[str, Any]], None] | None = None,
    cancel_event: Any | None = None,
) -> dict[str, Any]:
    """Deep-verify all original media by decrypting every chunk and recomputing SHA-256."""
    total_bytes = sum(max(0, _safe_int(item.get("size_bytes"))) for item in original_media)
    total_chunks = sum(max(0, _safe_int(item.get("chunk_count"))) for item in original_media)
    completed_bytes = 0
    completed_chunks = 0
    verified_media = 0

    if progress:
        progress({
            "total_files": total_chunks,
            "completed_files": 0,
            "total_bytes": total_bytes,
            "completed_bytes": 0,
            "verified_files": 0,
            "verified_media": 0,
            "current_file": "",
        })

    for item in original_media:
        if cancel_event is not None and cancel_event.is_set():
            raise LargeFileError("媒体校验任务已取消")
        if str(item.get("state_at_backup") or item.get("state") or "") != "online":
            raise LargeFileError("大型媒体库存在离线、不完整或异常项目，请先修复后再完整校验")
        media_id = str(item.get("media_id") or "").strip()
        size_bytes = _safe_int(item.get("size_bytes"))
        chunk_size = _safe_int(item.get("chunk_size"))
        expected_sha = str(item.get("sha256") or "")
        media_chunk_count = _safe_int(item.get("chunk_count"))

        def on_media_progress(values: dict[str, Any]) -> None:
            current_verified_bytes = _safe_int(values.get("verified_bytes"))
            current_verified_chunks = _safe_int(values.get("verified_chunks"))
            if progress:
                progress({
                    "total_files": total_chunks,
                    "completed_files": completed_chunks + current_verified_chunks,
                    "total_bytes": total_bytes,
                    "completed_bytes": completed_bytes + current_verified_bytes,
                    "verified_files": completed_chunks + current_verified_chunks,
                    "verified_media": verified_media,
                    "current_file": f"{media_id}:{_safe_int(values.get('chunk_index')):08d}",
                })

        store.verify_media(
            master_key,
            media_id,
            total_size=size_bytes,
            chunk_size=chunk_size,
            expected_sha256=expected_sha,
            progress=on_media_progress,
            cancel_event=cancel_event,
        )
        completed_bytes += size_bytes
        completed_chunks += media_chunk_count
        verified_media += 1
        if progress:
            progress({
                "total_files": total_chunks,
                "completed_files": completed_chunks,
                "total_bytes": total_bytes,
                "completed_bytes": completed_bytes,
                "verified_files": completed_chunks,
                "verified_media": verified_media,
                "current_file": media_id,
            })

    return {
        "state": "verified",
        "verified_media": verified_media,
        "verified_files": completed_chunks,
        "verified_bytes": completed_bytes,
        "total_files": total_chunks,
        "completed_files": completed_chunks,
        "total_bytes": total_bytes,
        "completed_bytes": completed_bytes,
    }
