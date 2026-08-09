from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import subprocess
from datetime import datetime, timezone as dt_timezone
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.services.audio_compat import discover_ffmpeg_tools
from app.services.large_files import MAX_LARGE_MEDIA_BYTES


EXCLUDED_FILE_NAMES = {
    ".ds_store", "thumbs.db", "desktop.ini", ".stfolder",
}
EXCLUDED_DIRECTORY_NAMES = {
    "$recycle.bin", "system volume information", "node_modules", "__pycache__",
    ".git", ".svn", ".hg", "@eadir",
}
IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".heif",
}
VIDEO_EXTENSIONS = {
    ".mp4", ".m4v", ".mov", ".webm", ".mkv", ".avi", ".wmv", ".flv", ".mpeg", ".mpg", ".ts", ".mts", ".m2ts",
}
DOCUMENT_EXTENSIONS = {
    ".pdf", ".txt", ".md", ".rtf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".odt", ".ods", ".odp", ".csv",
}


class MaterialScanError(ValueError):
    pass


def normalized_source_path(value: str) -> Path:
    raw = str(value or "").strip().strip('"')
    if not raw:
        raise MaterialScanError("扫描目录不能为空")
    path = Path(raw).expanduser()
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise MaterialScanError(f"扫描目录不存在或无法访问：{raw}") from exc
    if not resolved.is_dir():
        raise MaterialScanError("扫描路径必须是目录")
    return resolved


def is_path_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError, RuntimeError):
        return False


def normalized_relative_path(value: str) -> str:
    raw = str(value or "").replace("\\", "/").strip().lstrip("/")
    parts = [part for part in raw.split("/") if part not in {"", ".", ".."}]
    return "/".join(parts)[:2000]


def relative_path_hash(value: str) -> str:
    normalized = normalized_relative_path(value).casefold()
    return hashlib.sha256(normalized.encode("utf-8", errors="surrogatepass")).hexdigest()


def stat_file_identity(stat_result: os.stat_result) -> str | None:
    try:
        inode = int(getattr(stat_result, "st_ino", 0) or 0)
        device = int(getattr(stat_result, "st_dev", 0) or 0)
    except (TypeError, ValueError, OverflowError):
        return None
    if inode <= 0:
        return None
    return f"{device}:{inode}"


def material_category(path: Path, media_type: str | None = None) -> str:
    clean_type = str(media_type or "").lower()
    ext = path.suffix.lower()
    if clean_type.startswith("image/") or ext in IMAGE_EXTENSIONS:
        return "image"
    if clean_type.startswith("video/") or ext in VIDEO_EXTENSIONS:
        return "video"
    if (
        clean_type.startswith("text/")
        or clean_type == "application/pdf"
        or "office" in clean_type
        or "msword" in clean_type
        or "excel" in clean_type
        or "powerpoint" in clean_type
        or "opendocument" in clean_type
        or ext in DOCUMENT_EXTENSIONS
    ):
        return "document"
    return "other"


def guessed_media_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def should_skip_file(path: Path, stat_result: os.stat_result) -> str | None:
    name = path.name.casefold()
    if name in EXCLUDED_FILE_NAMES or name.startswith("~$"):
        return "系统/临时文件"
    try:
        size = int(stat_result.st_size)
    except (TypeError, ValueError, OverflowError):
        return "文件大小无效"
    if size <= 0:
        return "空文件"
    if size > MAX_LARGE_MEDIA_BYTES:
        return "超过 2 TB"
    return None


def iter_source_files(
    source_root: Path,
    *,
    include_subdirectories: bool = True,
    excluded_roots: tuple[Path, ...] = (),
) -> Iterator[tuple[Path, str, os.stat_result]]:
    root = source_root.resolve()
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            entries = list(os.scandir(directory))
        except OSError:
            continue
        entries.sort(key=lambda item: item.name.casefold())
        for entry in entries:
            try:
                if entry.is_symlink():
                    continue
                path = Path(entry.path)
                if any(is_path_within(path, excluded) for excluded in excluded_roots):
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if not include_subdirectories:
                        continue
                    name = entry.name.casefold()
                    if name.startswith(".") or name in EXCLUDED_DIRECTORY_NAMES:
                        continue
                    stack.append(path)
                    continue
                if not entry.is_file(follow_symlinks=False):
                    continue
                stat_result = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            if should_skip_file(path, stat_result):
                continue
            try:
                relative = path.relative_to(root).as_posix()
            except ValueError:
                continue
            yield path, normalized_relative_path(relative), stat_result


def compute_large_quick_fingerprint(path: Path, size_bytes: int | None = None) -> str:
    size = int(size_bytes if size_bytes is not None else path.stat().st_size)
    sample_size = 1024 * 1024
    ranges = [
        (0, min(size, sample_size)),
        (max(0, size // 2 - sample_size // 2), min(size, max(0, size // 2 - sample_size // 2) + sample_size)),
        (max(0, size - sample_size), size),
    ]
    unique: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for start, end in ranges:
        marker = (int(start), int(end))
        if end > start and marker not in seen:
            seen.add(marker)
            unique.append(marker)
    digest = hashlib.sha256()
    digest.update(f"LifeGraph-quick-v1:{size}:".encode("utf-8"))
    with path.open("rb") as stream:
        for start, end in unique:
            stream.seek(start)
            remaining = end - start
            while remaining > 0:
                chunk = stream.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                digest.update(chunk)
                remaining -= len(chunk)
    return digest.hexdigest()


def _normalized_iso_time(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if not 1800 <= parsed.year <= 2200:
        return None
    return parsed.isoformat(timespec="seconds")


def probe_video_path(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    tools = discover_ffmpeg_tools()
    if not tools.ffprobe:
        return {}, {}
    command = [
        str(tools.ffprobe),
        "-v", "error",
        "-show_entries",
        "format=duration:format_tags=creation_time:stream=codec_type,codec_name,width,height,channels,channel_layout,sample_rate:stream_tags=creation_time",
        "-of", "json",
        str(path),
    ]
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
        payload = json.loads((completed.stdout or b"{}").decode("utf-8", errors="replace"))
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return {}, {}
    if not isinstance(payload, dict):
        return {}, {}

    metadata: dict[str, Any] = {"metadata_source": "server:ffprobe-file"}
    fmt = payload.get("format") if isinstance(payload.get("format"), dict) else {}
    try:
        duration = float(fmt.get("duration"))
        if 0 <= duration <= 366 * 24 * 3600:
            metadata["duration_seconds"] = round(duration, 3)
    except (TypeError, ValueError):
        pass

    creation_candidates: list[Any] = []
    format_tags = fmt.get("tags") if isinstance(fmt.get("tags"), dict) else {}
    creation_candidates.append(format_tags.get("creation_time"))
    streams = payload.get("streams") if isinstance(payload.get("streams"), list) else []
    for stream in streams:
        if not isinstance(stream, dict):
            continue
        stream_type = str(stream.get("codec_type") or "").lower()
        if stream_type == "video" and "video_codec" not in metadata:
            codec = str(stream.get("codec_name") or "").strip()
            if codec:
                metadata["video_codec"] = codec
            try:
                width = int(stream.get("width"))
                if 1 <= width <= 32768:
                    metadata["video_width"] = width
            except (TypeError, ValueError):
                pass
            try:
                height = int(stream.get("height"))
                if 1 <= height <= 32768:
                    metadata["video_height"] = height
            except (TypeError, ValueError):
                pass
        elif stream_type == "audio" and "audio_codec_id" not in metadata:
            codec = str(stream.get("codec_name") or "").strip()
            if codec:
                metadata["audio_codec_id"] = codec
                metadata["audio_codec"] = codec
            try:
                channels = int(stream.get("channels"))
                if 1 <= channels <= 64:
                    metadata["audio_channels"] = channels
            except (TypeError, ValueError):
                pass
            layout = str(stream.get("channel_layout") or "").strip()
            if layout:
                metadata["audio_channel_layout"] = layout
            try:
                sample_rate = int(stream.get("sample_rate"))
                if 1000 <= sample_rate <= 768000:
                    metadata["audio_sample_rate"] = sample_rate
            except (TypeError, ValueError):
                pass
        tags = stream.get("tags") if isinstance(stream.get("tags"), dict) else {}
        creation_candidates.append(tags.get("creation_time"))

    timeline: dict[str, Any] = {}
    for candidate in creation_candidates:
        normalized = _normalized_iso_time(candidate)
        if normalized:
            timeline = {
                "timeline_at": normalized,
                "timeline_date": normalized[:10],
                "timeline_time_source": "media:creation_time",
                "time_precision": "second",
                "time_source": "media:creation_time",
                "time_confidence": "high",
            }
            break
    return metadata, timeline


_FILENAME_PATTERNS = (
    re.compile(r"(?<!\d)(?P<y>19\d{2}|20\d{2})(?P<m>0[1-9]|1[0-2])(?P<d>0[1-9]|[12]\d|3[01])[_\- .T]?(?P<h>[01]\d|2[0-3])(?P<mi>[0-5]\d)(?P<s>[0-5]\d)(?!\d)"),
    re.compile(r"(?<!\d)(?P<y>19\d{2}|20\d{2})[-_.](?P<m>0?[1-9]|1[0-2])[-_.](?P<d>0?[1-9]|[12]\d|3[01])[ T_-](?P<h>[01]?\d|2[0-3])[:._-](?P<mi>[0-5]?\d)(?:[:._-](?P<s>[0-5]?\d))?(?!\d)"),
    re.compile(r"(?<!\d)(?P<y>19\d{2}|20\d{2})(?P<m>0[1-9]|1[0-2])(?P<d>0[1-9]|[12]\d|3[01])(?!\d)"),
    re.compile(r"(?<!\d)(?P<y>19\d{2}|20\d{2})[-_.](?P<m>0?[1-9]|1[0-2])[-_.](?P<d>0?[1-9]|[12]\d|3[01])(?!\d)"),
)


def filename_time_metadata(filename: str, timezone_name: str) -> dict[str, Any]:
    stem = Path(filename or "").stem
    match = next((pattern.search(stem) for pattern in _FILENAME_PATTERNS if pattern.search(stem)), None)
    if match is None:
        return {}
    groups = match.groupdict()
    try:
        hour = int(groups.get("h") or 0)
        minute = int(groups.get("mi") or 0)
        second = int(groups.get("s") or 0)
        parsed = datetime(
            int(groups["y"]), int(groups["m"]), int(groups["d"]),
            hour, minute, second,
        )
    except (TypeError, ValueError):
        return {}
    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        tz = dt_timezone.utc
    parsed = parsed.replace(tzinfo=tz)
    has_time = bool(groups.get("h") is not None)
    return {
        "timeline_at": parsed.isoformat(timespec="seconds"),
        "timeline_date": parsed.date().isoformat(),
        "timeline_time_source": "filename:date",
        "time_precision": "second" if has_time else "day",
        "time_source": "filename:date",
        "time_confidence": "medium",
    }


def preferred_scanned_timeline(
    existing: dict[str, Any],
    *,
    media_timeline: dict[str, Any] | None = None,
    filename_timeline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current_source = str(existing.get("time_source") or existing.get("timeline_time_source") or "")
    if current_source.startswith("exif:") or current_source.startswith("document:"):
        return {}
    if media_timeline:
        return dict(media_timeline)
    if filename_timeline and current_source in {"", "file:last_modified", "attachment:added", "undetermined"}:
        return dict(filename_timeline)
    return {}
