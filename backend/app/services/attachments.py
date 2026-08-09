from __future__ import annotations

import hashlib
import io
import os
import re
import shutil
import struct
import zipfile
from xml.etree import ElementTree
from datetime import date, datetime, time, timezone as dt_timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.security.crypto import decrypt_bytes, encrypt_bytes


ATTACHMENT_FILE_AAD_PREFIX = b"lifegraph:v1:attachment-file:"
MAX_ATTACHMENT_BYTES = 50 * 1024 * 1024


class AttachmentFileError(ValueError):
    pass


def attachment_aad(attachment_id: str) -> bytes:
    return ATTACHMENT_FILE_AAD_PREFIX + attachment_id.encode("utf-8")


def _read_tiff_ascii(
    payload: bytes,
    *,
    tiff_start: int,
    endian: str,
    value_type: int,
    count: int,
    entry_offset: int,
) -> str | None:
    if value_type != 2 or count <= 0:
        return None
    size = count
    value_field = payload[entry_offset + 8 : entry_offset + 12]
    if size <= 4:
        raw = value_field[:size]
    else:
        relative = struct.unpack_from(f"{endian}I", payload, entry_offset + 8)[0]
        start = tiff_start + relative
        end = start + size
        if start < 0 or end > len(payload):
            return None
        raw = payload[start:end]
    try:
        return raw.split(b"\x00", 1)[0].decode("ascii", errors="strict").strip() or None
    except UnicodeDecodeError:
        return None


def _read_ifd_entries(
    payload: bytes,
    *,
    tiff_start: int,
    ifd_relative_offset: int,
    endian: str,
) -> dict[int, tuple[int, int, int]]:
    ifd_offset = tiff_start + ifd_relative_offset
    if ifd_offset < 0 or ifd_offset + 2 > len(payload):
        return {}
    count = struct.unpack_from(f"{endian}H", payload, ifd_offset)[0]
    entries: dict[int, tuple[int, int, int]] = {}
    for index in range(count):
        entry_offset = ifd_offset + 2 + index * 12
        if entry_offset + 12 > len(payload):
            break
        tag, value_type, value_count = struct.unpack_from(f"{endian}HHI", payload, entry_offset)
        entries[tag] = (value_type, value_count, entry_offset)
    return entries


def _parse_exif_datetime(value: str | None, offset: str | None = None) -> dict[str, str] | None:
    if not value:
        return None
    raw = value.strip()
    try:
        parsed = datetime.strptime(raw[:19], "%Y:%m:%d %H:%M:%S")
    except (TypeError, ValueError):
        return None
    if parsed.year < 1800 or parsed.year > 2200:
        return None
    iso_value = parsed.isoformat(timespec="seconds")
    clean_offset = (offset or "").strip()
    if clean_offset and len(clean_offset) == 6 and clean_offset[0] in {"+", "-"} and clean_offset[3] == ":":
        try:
            hours = int(clean_offset[1:3])
            minutes = int(clean_offset[4:6])
            if 0 <= hours <= 23 and 0 <= minutes <= 59:
                iso_value += clean_offset
        except ValueError:
            pass
    return {
        "captured_at": iso_value,
        "captured_date": parsed.date().isoformat(),
    }


def _extract_tiff_exif(payload: bytes, *, tiff_start: int = 0) -> dict[str, str] | None:
    if tiff_start < 0 or tiff_start + 8 > len(payload):
        return None
    byte_order = payload[tiff_start : tiff_start + 2]
    if byte_order == b"II":
        endian = "<"
    elif byte_order == b"MM":
        endian = ">"
    else:
        return None
    if struct.unpack_from(f"{endian}H", payload, tiff_start + 2)[0] != 42:
        return None
    ifd0_relative = struct.unpack_from(f"{endian}I", payload, tiff_start + 4)[0]
    ifd0 = _read_ifd_entries(
        payload,
        tiff_start=tiff_start,
        ifd_relative_offset=ifd0_relative,
        endian=endian,
    )

    candidates: list[tuple[str, str | None, str]] = []
    # IFD0 DateTime is a useful fallback when DateTimeOriginal is unavailable.
    if 0x0132 in ifd0:
        value_type, count, entry_offset = ifd0[0x0132]
        value = _read_tiff_ascii(
            payload,
            tiff_start=tiff_start,
            endian=endian,
            value_type=value_type,
            count=count,
            entry_offset=entry_offset,
        )
        if value:
            candidates.append((value, None, "DateTime"))

    exif_pointer = ifd0.get(0x8769)
    if exif_pointer:
        value_type, count, entry_offset = exif_pointer
        if value_type == 4 and count == 1:
            exif_relative = struct.unpack_from(f"{endian}I", payload, entry_offset + 8)[0]
            exif_ifd = _read_ifd_entries(
                payload,
                tiff_start=tiff_start,
                ifd_relative_offset=exif_relative,
                endian=endian,
            )
            offset_value = None
            if 0x9011 in exif_ifd:
                o_type, o_count, o_entry = exif_ifd[0x9011]
                offset_value = _read_tiff_ascii(
                    payload,
                    tiff_start=tiff_start,
                    endian=endian,
                    value_type=o_type,
                    count=o_count,
                    entry_offset=o_entry,
                )
            for tag, source in ((0x9004, "DateTimeDigitized"), (0x9003, "DateTimeOriginal")):
                entry = exif_ifd.get(tag)
                if not entry:
                    continue
                value_type, count, entry_offset = entry
                value = _read_tiff_ascii(
                    payload,
                    tiff_start=tiff_start,
                    endian=endian,
                    value_type=value_type,
                    count=count,
                    entry_offset=entry_offset,
                )
                if value:
                    candidates.insert(0, (value, offset_value, source))

    for raw_value, offset_value, source in candidates:
        parsed = _parse_exif_datetime(raw_value, offset_value)
        if parsed:
            parsed["capture_source"] = source
            return parsed
    return None


def _jpeg_exif_tiff_start(content: bytes) -> tuple[bytes, int] | None:
    if not content.startswith(b"\xff\xd8"):
        return None
    offset = 2
    length = len(content)
    while offset + 4 <= length:
        if content[offset] != 0xFF:
            offset += 1
            continue
        while offset < length and content[offset] == 0xFF:
            offset += 1
        if offset >= length:
            break
        marker = content[offset]
        offset += 1
        if marker in {0xD8, 0xD9}:
            continue
        if marker == 0xDA:  # Start of scan: metadata segments have ended.
            break
        if offset + 2 > length:
            break
        segment_length = struct.unpack_from(">H", content, offset)[0]
        if segment_length < 2 or offset + segment_length > length:
            break
        payload_start = offset + 2
        payload_end = offset + segment_length
        segment = content[payload_start:payload_end]
        if marker == 0xE1 and segment.startswith(b"Exif\x00\x00"):
            return segment, 6
        offset = payload_end
    return None


def _png_exif_payload(content: bytes) -> bytes | None:
    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    offset = 8
    while offset + 12 <= len(content):
        chunk_length = struct.unpack_from(">I", content, offset)[0]
        chunk_type = content[offset + 4 : offset + 8]
        data_start = offset + 8
        data_end = data_start + chunk_length
        if data_end + 4 > len(content):
            break
        if chunk_type == b"eXIf":
            return content[data_start:data_end]
        offset = data_end + 4
    return None


def _webp_exif_payload(content: bytes) -> tuple[bytes, int] | None:
    if len(content) < 12 or content[:4] != b"RIFF" or content[8:12] != b"WEBP":
        return None
    offset = 12
    while offset + 8 <= len(content):
        chunk_type = content[offset : offset + 4]
        chunk_length = struct.unpack_from("<I", content, offset + 4)[0]
        data_start = offset + 8
        data_end = data_start + chunk_length
        if data_end > len(content):
            break
        if chunk_type == b"EXIF":
            segment = content[data_start:data_end]
            if segment.startswith(b"Exif\x00\x00"):
                return segment, 6
            return segment, 0
        offset = data_end + (chunk_length % 2)
    return None


def extract_photo_capture_metadata(content: bytes) -> dict[str, Any]:
    """Return normalized EXIF capture information when a supported image contains it.

    This deliberately uses only the standard library so LifeGraph does not need a
    heavyweight image dependency just to read capture dates. JPEG, TIFF, PNG eXIf
    and WebP EXIF containers are supported. Missing/invalid EXIF simply returns
    an empty mapping.
    """

    try:
        jpeg = _jpeg_exif_tiff_start(content)
        if jpeg:
            segment, tiff_start = jpeg
            value = _extract_tiff_exif(segment, tiff_start=tiff_start)
            return value or {}

        if content[:2] in {b"II", b"MM"}:
            value = _extract_tiff_exif(content, tiff_start=0)
            return value or {}

        png = _png_exif_payload(content)
        if png:
            value = _extract_tiff_exif(png, tiff_start=0)
            return value or {}

        webp = _webp_exif_payload(content)
        if webp:
            segment, tiff_start = webp
            value = _extract_tiff_exif(segment, tiff_start=tiff_start)
            return value or {}
    except (IndexError, struct.error, OverflowError, ValueError):
        return {}
    return {}



def _normalize_metadata_datetime(value: str | None) -> dict[str, str] | None:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    candidate = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.year < 1800 or parsed.year > 2200:
        return None
    return {
        "value": parsed.isoformat(timespec="seconds"),
        "date": parsed.date().isoformat(),
    }


def _extract_office_core_time_metadata(content: bytes, filename: str) -> dict[str, str]:
    extension = Path(filename or "").suffix.lower()
    if extension not in {".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp"}:
        return {}
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            candidate_paths = ["docProps/core.xml", "meta.xml"]
            xml_bytes = None
            for path in candidate_paths:
                try:
                    xml_bytes = archive.read(path)
                    break
                except KeyError:
                    continue
            if not xml_bytes:
                return {}
        root = ElementTree.fromstring(xml_bytes)
    except (zipfile.BadZipFile, ElementTree.ParseError, OSError):
        return {}

    values: dict[str, str] = {}
    for element in root.iter():
        local_name = element.tag.rsplit("}", 1)[-1].lower()
        text = (element.text or "").strip()
        if not text:
            continue
        if local_name in {"created", "creation-date"} and "created" not in values:
            values["created"] = text
        elif local_name in {"modified", "date"} and "modified" not in values:
            values["modified"] = text

    result: dict[str, str] = {}
    created = _normalize_metadata_datetime(values.get("created"))
    modified = _normalize_metadata_datetime(values.get("modified"))
    if created:
        result["document_created_at"] = created["value"]
    if modified:
        result["document_modified_at"] = modified["value"]
    return result


def _parse_pdf_datetime(raw_value: str | None) -> dict[str, str] | None:
    if not raw_value:
        return None
    raw = raw_value.strip()
    if raw.startswith("D:"):
        raw = raw[2:]
    match = re.match(
        r"^(?P<year>\d{4})(?P<month>\d{2})?(?P<day>\d{2})?(?P<hour>\d{2})?(?P<minute>\d{2})?(?P<second>\d{2})?(?P<tz>Z|[+-]\d{2}'?\d{2}'?)?",
        raw,
    )
    if not match:
        return None
    parts = match.groupdict()
    try:
        parsed = datetime(
            int(parts["year"]),
            int(parts["month"] or 1),
            int(parts["day"] or 1),
            int(parts["hour"] or 0),
            int(parts["minute"] or 0),
            int(parts["second"] or 0),
        )
    except ValueError:
        return None
    if parsed.year < 1800 or parsed.year > 2200:
        return None
    tz_value = parts.get("tz") or ""
    iso_value = parsed.isoformat(timespec="seconds")
    if tz_value == "Z":
        iso_value += "+00:00"
    elif tz_value:
        clean = tz_value.replace("'", "")
        if len(clean) == 5:
            iso_value += f"{clean[:3]}:{clean[3:]}"
    return {"value": iso_value, "date": parsed.date().isoformat()}


def _extract_pdf_time_metadata(content: bytes, filename: str, media_type: str | None) -> dict[str, str]:
    extension = Path(filename or "").suffix.lower()
    if extension != ".pdf" and str(media_type or "").lower() != "application/pdf":
        return {}
    # PDF Info dictionaries are ASCII-compatible. Search a bounded prefix/suffix
    # to avoid decoding large binary bodies unnecessarily.
    sample = content if len(content) <= 4 * 1024 * 1024 else content[:2 * 1024 * 1024] + content[-2 * 1024 * 1024 :]
    result: dict[str, str] = {}
    for key, target in ((b"CreationDate", "document_created_at"), (b"ModDate", "document_modified_at")):
        match = re.search(rb"/" + key + rb"\s*\(([^)]{4,64})\)", sample)
        if not match:
            continue
        try:
            raw = match.group(1).decode("latin-1", errors="ignore")
        except Exception:
            continue
        parsed = _parse_pdf_datetime(raw)
        if parsed:
            result[target] = parsed["value"]
    return result


def _client_file_modified_metadata(last_modified_ms: int | None, timezone_name: str) -> dict[str, str]:
    if last_modified_ms is None or last_modified_ms <= 0:
        return {}
    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        from datetime import timezone
        tz = timezone.utc
    try:
        parsed = datetime.fromtimestamp(last_modified_ms / 1000, tz=tz)
    except (OSError, OverflowError, ValueError):
        return {}
    if parsed.year < 1800 or parsed.year > 2200:
        return {}
    return {
        "file_modified_at": parsed.isoformat(timespec="seconds"),
    }


def fallback_attachment_timeline_metadata(
    *,
    source_time_scope: str | None,
    source_period_key: str | None,
    attachment_created_at: str | None,
    timezone_name: str = "UTC",
) -> dict[str, str]:
    """Choose a safe contextual timeline fallback when file metadata has no usable time.

    Prefer an exact day from the parent event/memory/plan. If the parent is only
    month/year scoped (or malformed), fall back to the attachment's own added
    timestamp converted to the profile timezone. This fallback never changes the
    parent content relationship and is explicitly marked by `timeline_time_source`.
    """

    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        tz = dt_timezone.utc

    if source_time_scope == "day" and source_period_key:
        try:
            source_date = date.fromisoformat(source_period_key)
        except ValueError:
            source_date = None
        if source_date is not None:
            value = datetime.combine(source_date, time.min, tzinfo=tz)
            return {
                "timeline_at": value.isoformat(timespec="seconds"),
                "timeline_date": source_date.isoformat(),
                "timeline_time_source": "content:date",
            }

    if attachment_created_at:
        try:
            parsed = datetime.fromisoformat(str(attachment_created_at).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt_timezone.utc)
            parsed = parsed.astimezone(tz)
        except (TypeError, ValueError, OSError, OverflowError):
            parsed = None
        if parsed is not None and 1800 <= parsed.year <= 2200:
            return {
                "timeline_at": parsed.isoformat(timespec="seconds"),
                "timeline_date": parsed.date().isoformat(),
                "timeline_time_source": "attachment:added",
            }

    return {}


def extract_attachment_time_metadata(
    content: bytes,
    *,
    filename: str,
    media_type: str | None,
    file_last_modified_ms: int | None = None,
    timezone_name: str = "UTC",
) -> dict[str, Any]:
    """Extract raw file dates and choose an independent LifeGraph timeline date.

    The attachment/content relationship is never changed here. `timeline_*`
    describes where the file itself belongs on the life timeline. Source priority:
    photo EXIF capture time, document-internal creation/modified time, then the
    browser-provided filesystem last-modified time.
    """

    metadata: dict[str, Any] = {"exif_checked": True}
    photo = extract_photo_capture_metadata(content)
    metadata.update(photo)

    document: dict[str, str] = {}
    document.update(_extract_office_core_time_metadata(content, filename))
    if not document:
        document.update(_extract_pdf_time_metadata(content, filename, media_type))
    metadata.update(document)

    file_times = _client_file_modified_metadata(file_last_modified_ms, timezone_name)
    metadata.update(file_times)

    timeline_at = None
    timeline_source = None
    if metadata.get("captured_at"):
        timeline_at = metadata["captured_at"]
        timeline_source = f"exif:{metadata.get('capture_source') or 'capture'}"
    elif metadata.get("document_created_at"):
        timeline_at = metadata["document_created_at"]
        timeline_source = "document:created"
    elif metadata.get("document_modified_at"):
        timeline_at = metadata["document_modified_at"]
        timeline_source = "document:modified"
    elif metadata.get("file_modified_at"):
        timeline_at = metadata["file_modified_at"]
        timeline_source = "file:last_modified"

    normalized = _normalize_metadata_datetime(str(timeline_at)) if timeline_at else None
    if normalized:
        metadata["timeline_at"] = normalized["value"]
        metadata["timeline_date"] = normalized["date"]
        metadata["timeline_time_source"] = timeline_source
    metadata["time_metadata_checked"] = True
    return metadata


class AttachmentStore:
    """Encrypted attachment blob storage outside SQLite.

    Physical files are sharded by the first two characters of the attachment
    UUID so a long-lived repository does not accumulate every blob in one
    filesystem directory. Legacy flat files remain readable and are migrated
    lazily; VaultManager also performs a best-effort migration at startup.
    """

    _SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

    def __init__(self, root: Path) -> None:
        self.root = root

    @classmethod
    def _safe_id(cls, attachment_id: str) -> str:
        value = str(attachment_id or "").strip()
        if not cls._SAFE_ID.fullmatch(value):
            raise AttachmentFileError("附件标识无效")
        return value

    def shard_for(self, attachment_id: str) -> str:
        value = self._safe_id(attachment_id)
        return value[:2].lower()

    def path_for(self, attachment_id: str) -> Path:
        value = self._safe_id(attachment_id)
        return self.root / self.shard_for(value) / f"{value}.lgatt"

    def legacy_path_for(self, attachment_id: str) -> Path:
        value = self._safe_id(attachment_id)
        return self.root / f"{value}.lgatt"

    def _migrate_legacy_file(self, attachment_id: str) -> Path | None:
        target = self.path_for(attachment_id)
        if target.is_file():
            return target
        legacy = self.legacy_path_for(attachment_id)
        if not legacy.is_file():
            return None
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(legacy, target)
            return target
        except OSError:
            # Keep the legacy file usable when migration cannot be completed
            # (for example because another process temporarily holds it).
            return legacy

    def migrate_legacy_layout(self) -> dict[str, int]:
        """Best-effort migration from ``attachments/<id>.lgatt`` to shards."""

        result = {"migrated": 0, "already_sharded": 0, "failed": 0}
        if not self.root.exists():
            return result
        for legacy in self.root.glob("*.lgatt"):
            attachment_id = legacy.stem
            try:
                self._safe_id(attachment_id)
                target = self.path_for(attachment_id)
                if target.is_file():
                    result["already_sharded"] += 1
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(legacy, target)
                result["migrated"] += 1
            except (AttachmentFileError, OSError):
                result["failed"] += 1
        return result

    def _existing_path(self, attachment_id: str) -> Path | None:
        path = self.path_for(attachment_id)
        if path.is_file():
            return path
        return self._migrate_legacy_file(attachment_id)

    def write(self, master_key: bytes, attachment_id: str, plaintext: bytes) -> tuple[bytes, str]:
        if len(plaintext) > MAX_ATTACHMENT_BYTES:
            raise AttachmentFileError("单个附件不能超过 50 MB")
        nonce, ciphertext = encrypt_bytes(
            master_key,
            plaintext,
            aad=attachment_aad(attachment_id),
        )
        path = self.path_for(attachment_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        try:
            with temp_path.open("wb") as stream:
                stream.write(ciphertext)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, path)
            self.legacy_path_for(attachment_id).unlink(missing_ok=True)
        finally:
            temp_path.unlink(missing_ok=True)
        return nonce, hashlib.sha256(plaintext).hexdigest()

    def read(self, master_key: bytes, attachment_id: str, nonce: bytes) -> bytes:
        path = self._existing_path(attachment_id)
        if path is None:
            raise AttachmentFileError("附件文件不存在")
        ciphertext = path.read_bytes()
        return decrypt_bytes(
            master_key,
            nonce,
            ciphertext,
            aad=attachment_aad(attachment_id),
        )

    def encrypted_path(self, attachment_id: str) -> Path:
        """Return the existing encrypted blob path without reading its contents."""
        path = self._existing_path(attachment_id)
        if path is None:
            raise AttachmentFileError("附件文件不存在")
        return path

    def encrypted_bytes(self, attachment_id: str) -> bytes:
        return self.encrypted_path(attachment_id).read_bytes()

    def write_encrypted_bytes(self, attachment_id: str, ciphertext: bytes) -> None:
        path = self.path_for(attachment_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        try:
            with temp_path.open("wb") as stream:
                stream.write(ciphertext)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, path)
            self.legacy_path_for(attachment_id).unlink(missing_ok=True)
        finally:
            temp_path.unlink(missing_ok=True)

    def write_encrypted_stream(self, attachment_id: str, source, *, chunk_size: int = 1024 * 1024) -> tuple[int, str]:
        """Copy an encrypted blob stream to its sharded location with bounded memory."""
        path = self.path_for(attachment_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        digest = hashlib.sha256()
        size = 0
        try:
            with temp_path.open("wb") as target:
                while chunk := source.read(chunk_size):
                    target.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temp_path, path)
            self.legacy_path_for(attachment_id).unlink(missing_ok=True)
            return size, digest.hexdigest()
        finally:
            temp_path.unlink(missing_ok=True)

    def delete(self, attachment_id: str) -> None:
        path = self.path_for(attachment_id)
        legacy = self.legacy_path_for(attachment_id)
        path.unlink(missing_ok=True)
        legacy.unlink(missing_ok=True)
        try:
            path.parent.rmdir()
        except OSError:
            pass

