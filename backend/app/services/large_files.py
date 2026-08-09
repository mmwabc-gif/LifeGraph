from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import shutil
import struct
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator
from queue import Full, Queue

from app.security.crypto import CryptoError, decrypt_bytes, decrypt_json, encrypt_bytes, encrypt_json


CHUNKED_MEDIA_FORMAT_VERSION = 1
CHUNK_MAGIC = b"LGCHNK01"
UPLOAD_META_MAGIC = b"LGUPM001"
MEDIA_MANIFEST_MAGIC = b"LGMAN001"
UPLOAD_PREVIEW_MAGIC = b"LGPVW001"
CHUNK_HEADER = struct.Struct(">8sQQ12s")
ENCRYPTED_JSON_HEADER = struct.Struct(">8s12s")

DEFAULT_MEDIA_CHUNK_SIZE = 8 * 1024 * 1024
MIN_MEDIA_CHUNK_SIZE = 1 * 1024 * 1024
MAX_MEDIA_CHUNK_SIZE = 32 * 1024 * 1024
MAX_LARGE_MEDIA_BYTES = 2 * 1024 * 1024 * 1024 * 1024
MAX_LARGE_MEDIA_CHUNKS = 65_536
MAX_CONCURRENT_CHUNK_WRITES = 6
MEDIA_DISK_RESERVE_MIN_BYTES = 256 * 1024 * 1024
MEDIA_DISK_RESERVE_MAX_BYTES = 2 * 1024 * 1024 * 1024
MEDIA_CHUNK_WRITE_RESERVE_BYTES = 64 * 1024 * 1024
DEFAULT_STALE_UPLOAD_DAYS = 30

CHUNK_AAD_PREFIX = b"lifegraph:v1:chunked-media-chunk:"
UPLOAD_META_AAD_PREFIX = b"lifegraph:v1:chunked-media-upload:"
MEDIA_MANIFEST_AAD_PREFIX = b"lifegraph:v1:chunked-media-manifest:"
UPLOAD_PREVIEW_AAD_PREFIX = b"lifegraph:v1:chunked-media-preview:"

MAX_UPLOAD_PREVIEW_BYTES = 512 * 1024

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_CHUNK_NAME = re.compile(r"^(\d{8})\.lgchunk$")


class LargeFileError(ValueError):
    pass


class LargeFileConflict(LargeFileError):
    pass


def choose_media_chunk_size(total_size: int) -> int:
    """Choose a bounded chunk size that keeps huge files from creating excessive files.

    The defaults favor 4-8 MiB chunks for ordinary large videos so HTTP Range seeks
    remain reasonably fine-grained. Very large files gradually increase the chunk
    size, capping the number of chunk files at a manageable level.
    """

    size = int(total_size)
    if size <= 0:
        raise LargeFileError("大文件大小必须大于 0")
    if size > MAX_LARGE_MEDIA_BYTES:
        raise LargeFileError("单个大型资料暂不能超过 2 TB")
    if size <= 1 * 1024**3:
        return 4 * 1024 * 1024
    if size <= 16 * 1024**3:
        return 8 * 1024 * 1024
    if size <= 128 * 1024**3:
        return 16 * 1024 * 1024
    return 32 * 1024 * 1024


def _clean_id(value: str, label: str) -> str:
    cleaned = str(value or "").strip()
    if not _SAFE_ID.fullmatch(cleaned):
        raise LargeFileError(f"{label}无效")
    return cleaned


def _chunk_aad(media_id: str, index: int, plaintext_size: int) -> bytes:
    return (
        CHUNK_AAD_PREFIX
        + media_id.encode("utf-8")
        + b":"
        + int(index).to_bytes(8, "big", signed=False)
        + int(plaintext_size).to_bytes(8, "big", signed=False)
    )


def _upload_meta_aad(session_id: str) -> bytes:
    return UPLOAD_META_AAD_PREFIX + session_id.encode("utf-8")


def _manifest_aad(media_id: str) -> bytes:
    return MEDIA_MANIFEST_AAD_PREFIX + media_id.encode("utf-8")


def _preview_aad(media_id: str) -> bytes:
    return UPLOAD_PREVIEW_AAD_PREFIX + media_id.encode("utf-8")


def _atomic_write(path: Path, content: bytes, *, durable: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    try:
        with temp.open("wb") as stream:
            stream.write(content)
            stream.flush()
            if durable:
                os.fsync(stream.fileno())
        os.replace(temp, path)
    except OSError as exc:
        raise LargeFileError(f"媒体存储写入失败：{exc}") from exc
    finally:
        temp.unlink(missing_ok=True)


def _write_encrypted_json(
    path: Path,
    *,
    master_key: bytes,
    value: dict[str, Any],
    aad: bytes,
    magic: bytes,
) -> None:
    nonce, ciphertext = encrypt_json(master_key, value, aad=aad)
    _atomic_write(path, ENCRYPTED_JSON_HEADER.pack(magic, nonce) + ciphertext)


def _read_encrypted_json(
    path: Path,
    *,
    master_key: bytes,
    aad: bytes,
    magic: bytes,
) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            header = stream.read(ENCRYPTED_JSON_HEADER.size)
            if len(header) != ENCRYPTED_JSON_HEADER.size:
                raise LargeFileError("大文件元数据损坏")
            actual_magic, nonce = ENCRYPTED_JSON_HEADER.unpack(header)
            if actual_magic != magic:
                raise LargeFileError("大文件元数据格式不受支持")
            ciphertext = stream.read()
        if not ciphertext:
            raise LargeFileError("大文件元数据为空")
        return decrypt_json(master_key, nonce, ciphertext, aad=aad)
    except FileNotFoundError as exc:
        raise LargeFileError("大文件元数据不存在") from exc
    except (OSError, CryptoError, json.JSONDecodeError) as exc:
        raise LargeFileError("大文件元数据无法读取或验证") from exc


def _compact_ranges(indices: list[int]) -> list[list[int]]:
    if not indices:
        return []
    ordered = sorted(set(indices))
    ranges: list[list[int]] = []
    start = previous = ordered[0]
    for index in ordered[1:]:
        if index == previous + 1:
            previous = index
            continue
        ranges.append([start, previous])
        start = previous = index
    ranges.append([start, previous])
    return ranges


def _existing_path_for_disk_usage(path: Path) -> Path:
    candidate = Path(path)
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate


def _disk_reserve_for(total_size: int) -> int:
    adaptive = max(MEDIA_DISK_RESERVE_MIN_BYTES, int(max(0, total_size) * 0.01))
    return min(MEDIA_DISK_RESERVE_MAX_BYTES, adaptive)


def disk_space_report(path: Path, required_payload_bytes: int, *, reserve_bytes: int | None = None) -> dict[str, int | bool]:
    required_payload_bytes = max(0, int(required_payload_bytes))
    reserve = _disk_reserve_for(required_payload_bytes) if reserve_bytes is None else max(0, int(reserve_bytes))
    try:
        usage = shutil.disk_usage(_existing_path_for_disk_usage(path))
    except OSError as exc:
        raise LargeFileError(f"无法读取媒体存储磁盘剩余空间：{exc}") from exc
    required = required_payload_bytes + reserve
    return {
        "total_bytes": int(usage.total),
        "used_bytes": int(usage.used),
        "free_bytes": int(usage.free),
        "payload_bytes": required_payload_bytes,
        "reserve_bytes": reserve,
        "required_bytes": required,
        "sufficient": int(usage.free) >= required,
    }


def ensure_disk_space(path: Path, required_payload_bytes: int, *, reserve_bytes: int | None = None) -> dict[str, int | bool]:
    report = disk_space_report(path, required_payload_bytes, reserve_bytes=reserve_bytes)
    if not bool(report["sufficient"]):
        free_gib = int(report["free_bytes"]) / 1024**3
        required_gib = int(report["required_bytes"]) / 1024**3
        raise LargeFileError(
            f"磁盘剩余空间不足：当前约 {free_gib:.2f} GB，可安全写入至少需要 {required_gib:.2f} GB"
        )
    return report


class ChunkedMediaStore:
    """Random-access authenticated encrypted storage for finalized large media.

    Each plaintext chunk is independently AES-GCM encrypted. The chunk header
    stores only structural information (index, plaintext length and random nonce),
    while the filename and other human-readable metadata stay encrypted elsewhere.
    """

    def __init__(self, root: Path) -> None:
        self.root = root

    @staticmethod
    def shard_for(media_id: str) -> str:
        value = _clean_id(media_id, "媒体标识")
        return value[:2].lower()

    def media_dir(self, media_id: str) -> Path:
        value = _clean_id(media_id, "媒体标识")
        return self.root / self.shard_for(value) / value

    def chunk_dir(self, media_id: str) -> Path:
        return self.media_dir(media_id) / "chunks"

    def chunk_path(self, media_id: str, index: int) -> Path:
        if int(index) < 0:
            raise LargeFileError("分块序号无效")
        return self.chunk_dir(media_id) / f"{int(index):08d}.lgchunk"

    def manifest_path(self, media_id: str) -> Path:
        return self.media_dir(media_id) / "manifest.lgmedia"

    @staticmethod
    def _write_chunk_path(
        path: Path,
        *,
        master_key: bytes,
        media_id: str,
        index: int,
        plaintext: bytes,
        durable: bool = True,
    ) -> dict[str, Any]:
        media_id = _clean_id(media_id, "媒体标识")
        index = int(index)
        if index < 0:
            raise LargeFileError("分块序号无效")
        if not plaintext:
            raise LargeFileError("分块不能为空")
        if len(plaintext) > MAX_MEDIA_CHUNK_SIZE:
            raise LargeFileError("单个分块不能超过 32 MB")
        nonce, ciphertext = encrypt_bytes(
            master_key,
            plaintext,
            aad=_chunk_aad(media_id, index, len(plaintext)),
        )
        payload = CHUNK_HEADER.pack(CHUNK_MAGIC, index, len(plaintext), nonce) + ciphertext
        _atomic_write(path, payload, durable=durable)
        return {
            "index": index,
            "size_bytes": len(plaintext),
            "sha256": hashlib.sha256(plaintext).hexdigest(),
            "encrypted_size_bytes": len(payload),
        }

    @staticmethod
    def _read_chunk_path(
        path: Path,
        *,
        master_key: bytes,
        media_id: str,
        expected_index: int | None = None,
    ) -> bytes:
        media_id = _clean_id(media_id, "媒体标识")
        try:
            with path.open("rb") as stream:
                header = stream.read(CHUNK_HEADER.size)
                if len(header) != CHUNK_HEADER.size:
                    raise LargeFileError("媒体分块头损坏")
                magic, index, plaintext_size, nonce = CHUNK_HEADER.unpack(header)
                if magic != CHUNK_MAGIC:
                    raise LargeFileError("媒体分块格式不受支持")
                if expected_index is not None and index != int(expected_index):
                    raise LargeFileError("媒体分块序号不匹配")
                if plaintext_size <= 0 or plaintext_size > MAX_MEDIA_CHUNK_SIZE:
                    raise LargeFileError("媒体分块大小无效")
                ciphertext = stream.read()
            if len(ciphertext) != plaintext_size + 16:
                raise LargeFileError("媒体分块长度校验失败")
            return decrypt_bytes(
                master_key,
                nonce,
                ciphertext,
                aad=_chunk_aad(media_id, index, plaintext_size),
            )
        except FileNotFoundError as exc:
            raise LargeFileError("媒体分块不存在") from exc
        except OSError as exc:
            raise LargeFileError("媒体分块无法读取") from exc
        except CryptoError as exc:
            raise LargeFileError("媒体分块完整性验证失败") from exc

    def write_chunk(
        self,
        master_key: bytes,
        media_id: str,
        index: int,
        plaintext: bytes,
        *,
        durable: bool = True,
    ) -> dict[str, Any]:
        return self._write_chunk_path(
            self.chunk_path(media_id, index),
            master_key=master_key,
            media_id=media_id,
            index=index,
            plaintext=plaintext,
            durable=durable,
        )

    def read_chunk(self, master_key: bytes, media_id: str, index: int) -> bytes:
        return self._read_chunk_path(
            self.chunk_path(media_id, index),
            master_key=master_key,
            media_id=media_id,
            expected_index=index,
        )

    def read_manifest(self, master_key: bytes, media_id: str) -> dict[str, Any]:
        media_id = _clean_id(media_id, "媒体标识")
        value = _read_encrypted_json(
            self.manifest_path(media_id),
            master_key=master_key,
            aad=_manifest_aad(media_id),
            magic=MEDIA_MANIFEST_MAGIC,
        )
        if value.get("format_version") != CHUNKED_MEDIA_FORMAT_VERSION:
            raise LargeFileError("大型媒体格式版本不受支持")
        if value.get("media_id") != media_id:
            raise LargeFileError("大型媒体清单与目录不匹配")
        return value

    def iter_plain_chunks(
        self,
        master_key: bytes,
        media_id: str,
        *,
        total_size: int,
        chunk_size: int,
    ) -> Iterator[bytes]:
        total_size = int(total_size)
        chunk_size = int(chunk_size)
        if total_size <= 0 or chunk_size <= 0:
            raise LargeFileError("大型媒体结构参数无效")
        chunk_count = math.ceil(total_size / chunk_size)
        for index in range(chunk_count):
            plaintext = self.read_chunk(master_key, media_id, index)
            expected = min(chunk_size, total_size - index * chunk_size)
            if len(plaintext) != expected:
                raise LargeFileError(f"媒体分块 {index} 明文大小校验失败")
            yield plaintext

    def iter_plain_chunks_buffered(
        self,
        master_key: bytes,
        media_id: str,
        *,
        total_size: int,
        chunk_size: int,
        buffer_chunks: int = 3,
    ) -> Iterator[bytes]:
        """Sequential read/decrypt with a small producer buffer.

        Disk access remains strictly ordered and single-reader. The producer may
        prepare the next few chunks while a slow consumer is blocked writing the
        current chunk to FFmpeg. This avoids the Windows multi-file contention of
        parallel prefetch while still overlapping I/O/AES-GCM with pipe output.
        """
        total_size = int(total_size)
        chunk_size = int(chunk_size)
        if total_size <= 0 or chunk_size <= 0:
            raise LargeFileError("大型媒体结构参数无效")
        chunk_count = math.ceil(total_size / chunk_size)
        buffer_chunks = max(1, min(6, int(buffer_chunks)))
        if chunk_count <= 1:
            yield from self.iter_plain_chunks(
                master_key,
                media_id,
                total_size=total_size,
                chunk_size=chunk_size,
            )
            return

        queue: Queue[tuple[str, Any]] = Queue(maxsize=buffer_chunks)
        stop_event = threading.Event()

        def offer(item: tuple[str, Any]) -> bool:
            while not stop_event.is_set():
                try:
                    queue.put(item, timeout=0.1)
                    return True
                except Full:
                    continue
            return False

        def producer() -> None:
            try:
                for index in range(chunk_count):
                    if stop_event.is_set():
                        return
                    plaintext = self.read_chunk(master_key, media_id, index)
                    expected = min(chunk_size, total_size - index * chunk_size)
                    if len(plaintext) != expected:
                        raise LargeFileError(f"媒体分块 {index} 明文大小校验失败")
                    if not offer(("data", plaintext)):
                        return
            except BaseException as exc:
                offer(("error", exc))
            finally:
                offer(("done", None))

        producer_thread = threading.Thread(
            target=producer,
            name="lifegraph-media-sequential-read",
            daemon=True,
        )
        producer_thread.start()
        try:
            while True:
                kind, payload = queue.get()
                if kind == "data":
                    yield payload
                    continue
                if kind == "error":
                    raise payload
                break
        finally:
            stop_event.set()
            producer_thread.join(timeout=2)

    def iter_plain_range(
        self,
        master_key: bytes,
        media_id: str,
        *,
        total_size: int,
        chunk_size: int,
        start: int,
        end_exclusive: int,
    ) -> Iterator[bytes]:
        total_size = int(total_size)
        chunk_size = int(chunk_size)
        start = int(start)
        end_exclusive = int(end_exclusive)
        if total_size <= 0 or chunk_size <= 0:
            raise LargeFileError("大型媒体结构参数无效")
        if start < 0 or end_exclusive < start or end_exclusive > total_size:
            raise LargeFileError("请求的媒体字节范围无效")
        if start == end_exclusive:
            return
        first = start // chunk_size
        last = (end_exclusive - 1) // chunk_size
        for index in range(first, last + 1):
            plaintext = self.read_chunk(master_key, media_id, index)
            expected = min(chunk_size, total_size - index * chunk_size)
            if len(plaintext) != expected:
                raise LargeFileError(f"媒体分块 {index} 明文大小校验失败")
            left = start - index * chunk_size if index == first else 0
            right = end_exclusive - index * chunk_size if index == last else len(plaintext)
            yield plaintext[left:right]

    def verify_media(
        self,
        master_key: bytes,
        media_id: str,
        *,
        total_size: int,
        chunk_size: int,
        expected_sha256: str = "",
        progress: Callable[[dict[str, Any]], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> dict[str, Any]:
        """Deep-verify every encrypted chunk and the whole plaintext SHA-256."""
        total_size = int(total_size)
        chunk_size = int(chunk_size)
        if total_size <= 0 or chunk_size <= 0:
            raise LargeFileError("大型媒体结构参数无效")
        manifest = self.read_manifest(master_key, media_id)
        if int(manifest.get("size_bytes") or -1) != total_size:
            raise LargeFileError("大型媒体清单大小与索引不一致")
        if int(manifest.get("chunk_size") or -1) != chunk_size:
            raise LargeFileError("大型媒体清单分块大小与索引不一致")
        chunk_count = math.ceil(total_size / chunk_size)
        manifest_count = int(manifest.get("chunk_count") or chunk_count)
        if manifest_count != chunk_count:
            raise LargeFileError("大型媒体清单分块数量与索引不一致")
        digest = hashlib.sha256()
        verified_bytes = 0
        for index in range(chunk_count):
            if cancel_event is not None and cancel_event.is_set():
                raise LargeFileError("媒体校验任务已取消")
            plaintext = self.read_chunk(master_key, media_id, index)
            expected = min(chunk_size, total_size - index * chunk_size)
            if len(plaintext) != expected:
                raise LargeFileError(f"媒体分块 {index} 明文大小校验失败")
            digest.update(plaintext)
            verified_bytes += len(plaintext)
            if progress:
                progress({
                    "verified_chunks": index + 1,
                    "chunk_count": chunk_count,
                    "verified_bytes": verified_bytes,
                    "total_bytes": total_size,
                    "chunk_index": index,
                })
        actual_sha = digest.hexdigest()
        wanted = str(expected_sha256 or manifest.get("sha256") or "").strip().lower()
        if wanted and actual_sha != wanted:
            raise LargeFileError("大型媒体整文件 SHA-256 校验失败")
        return {
            "media_id": media_id,
            "verified_chunks": chunk_count,
            "verified_bytes": verified_bytes,
            "sha256": actual_sha,
        }

    def write_stream(
        self,
        master_key: bytes,
        media_id: str,
        source: Iterator[bytes],
        *,
        chunk_size: int = DEFAULT_MEDIA_CHUNK_SIZE,
        manifest_extra: dict[str, Any] | None = None,
        durable_chunks: bool = True,
    ) -> dict[str, Any]:
        """Encrypt a plaintext byte stream directly into finalized lgchunk media.

        Used by derived media such as browser-compatible audio so no large
        plaintext temporary file is required.
        """
        media_id = _clean_id(media_id, "媒体标识")
        chunk_size = int(chunk_size)
        if not MIN_MEDIA_CHUNK_SIZE <= chunk_size <= MAX_MEDIA_CHUNK_SIZE:
            raise LargeFileError("媒体分块大小无效")
        target = self.media_dir(media_id)
        if target.exists():
            raise LargeFileConflict("大型媒体目标目录已经存在")
        digest = hashlib.sha256()
        buffer = bytearray()
        total_size = 0
        chunk_count = 0
        try:
            for block in source:
                if not block:
                    continue
                buffer.extend(block)
                while len(buffer) >= chunk_size:
                    plaintext = bytes(buffer[:chunk_size])
                    del buffer[:chunk_size]
                    self.write_chunk(
                        master_key, media_id, chunk_count, plaintext, durable=durable_chunks
                    )
                    digest.update(plaintext)
                    total_size += len(plaintext)
                    chunk_count += 1
            if buffer:
                plaintext = bytes(buffer)
                self.write_chunk(
                    master_key, media_id, chunk_count, plaintext, durable=durable_chunks
                )
                digest.update(plaintext)
                total_size += len(plaintext)
                chunk_count += 1
            if total_size <= 0 or chunk_count <= 0:
                raise LargeFileError("媒体输出为空")
            manifest = {
                "format_version": CHUNKED_MEDIA_FORMAT_VERSION,
                "storage_kind": "chunked-v1",
                "media_id": media_id,
                "size_bytes": total_size,
                "chunk_size": chunk_size,
                "chunk_count": chunk_count,
                "sha256": digest.hexdigest(),
                "finalized_at": datetime.now(timezone.utc).isoformat(),
                **dict(manifest_extra or {}),
            }
            _write_encrypted_json(
                self.manifest_path(media_id),
                master_key=master_key,
                value=manifest,
                aad=_manifest_aad(media_id),
                magic=MEDIA_MANIFEST_MAGIC,
            )
            return manifest
        except BaseException:
            self.delete(media_id)
            raise

    def verify(self, master_key: bytes, media_id: str) -> dict[str, Any]:
        manifest = self.read_manifest(master_key, media_id)
        digest = hashlib.sha256()
        total = 0
        chunk_count = 0
        for plaintext in self.iter_plain_chunks(
            master_key,
            media_id,
            total_size=int(manifest["size_bytes"]),
            chunk_size=int(manifest["chunk_size"]),
        ):
            digest.update(plaintext)
            total += len(plaintext)
            chunk_count += 1
        if total != int(manifest["size_bytes"]):
            raise LargeFileError("大型媒体总大小校验失败")
        if chunk_count != int(manifest["chunk_count"]):
            raise LargeFileError("大型媒体分块数量校验失败")
        if digest.hexdigest() != str(manifest.get("sha256") or ""):
            raise LargeFileError("大型媒体 SHA-256 校验失败")
        return {
            "verified": True,
            "media_id": media_id,
            "size_bytes": total,
            "chunk_count": chunk_count,
            "sha256": digest.hexdigest(),
        }

    def delete(self, media_id: str) -> None:
        directory = self.media_dir(media_id)
        shutil.rmtree(directory, ignore_errors=True)
        try:
            directory.parent.rmdir()
        except OSError:
            pass


class LargeUploadManager:
    """Persistent resumable upload sessions backed by encrypted chunk files."""

    def __init__(self, media_root: Path) -> None:
        self.media_root = media_root
        self.store = ChunkedMediaStore(media_root)
        self.incoming_root = media_root / ".incoming"
        # Allow different chunks from the same upload to be encrypted/written in
        # parallel while still making cancel/finalize exclusive against in-flight
        # writers. A small per-chunk lock preserves idempotence if the exact same
        # chunk is retried concurrently.
        self._state = threading.Condition(threading.RLock())
        self._active_writers: dict[str, int] = {}
        self._blocked_sessions: set[str] = set()
        self._chunk_locks: dict[tuple[str, int], threading.Lock] = {}
        self._writer_slots = threading.BoundedSemaphore(MAX_CONCURRENT_CHUNK_WRITES)

    def _session_dir(self, session_id: str) -> Path:
        session_id = _clean_id(session_id, "上传会话标识")
        return self.incoming_root / session_id

    def _session_meta_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "session.lgup"

    def _session_chunk_dir(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "chunks"

    def _session_preview_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "preview.lgpending"

    def _media_preview_path(self, media_id: str) -> Path:
        return self.store.media_dir(media_id) / "preview.lgpending"

    def _session_chunk_path(self, session_id: str, index: int) -> Path:
        if int(index) < 0:
            raise LargeFileError("分块序号无效")
        return self._session_chunk_dir(session_id) / f"{int(index):08d}.lgchunk"

    def create_session(
        self,
        master_key: bytes,
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
        total_size = int(size_bytes)
        if total_size <= 0:
            raise LargeFileError("大型资料文件不能为空")
        if total_size > MAX_LARGE_MEDIA_BYTES:
            raise LargeFileError("单个大型资料暂不能超过 2 TB")
        selected_chunk_size = int(chunk_size or choose_media_chunk_size(total_size))
        if not MIN_MEDIA_CHUNK_SIZE <= selected_chunk_size <= MAX_MEDIA_CHUNK_SIZE:
            raise LargeFileError("分块大小必须在 1 MB—32 MB 之间")
        chunk_count = math.ceil(total_size / selected_chunk_size)
        if chunk_count > MAX_LARGE_MEDIA_CHUNKS:
            raise LargeFileError("分块数量过多，请增大分块大小")

        capacity = ensure_disk_space(self.media_root, total_size)
        clean_name = Path(str(filename or "")).name.strip() or "未命名大型资料"
        if len(clean_name) > 240:
            raise LargeFileError("资料文件名过长")
        clean_relative = str(source_relative_path or "").replace("\\", "/").strip().lstrip("/")
        if clean_relative:
            clean_relative = "/".join(
                part for part in clean_relative.split("/") if part not in {"", ".", ".."}
            )[:1000]
        clean_directory = Path(str(source_directory_name or "").strip()).name[:120]

        session_id = str(uuid.uuid4())
        media_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        value: dict[str, Any] = {
            "format_version": CHUNKED_MEDIA_FORMAT_VERSION,
            "session_id": session_id,
            "media_id": media_id,
            "filename": clean_name,
            "media_type": (media_type or "application/octet-stream")[:200],
            "size_bytes": total_size,
            "chunk_size": selected_chunk_size,
            "chunk_count": chunk_count,
            "file_last_modified_ms": file_last_modified_ms,
            "source_relative_path": clean_relative or None,
            "source_directory_name": clean_directory or None,
            "quick_fingerprint": str(quick_fingerprint or "").strip().lower() or None,
            "reject_duplicate": bool(reject_duplicate),
            "created_at": now,
            "updated_at": now,
        }
        session_dir = self._session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=False)
        self._session_chunk_dir(session_id).mkdir(parents=True, exist_ok=True)
        try:
            _write_encrypted_json(
                self._session_meta_path(session_id),
                master_key=master_key,
                value=value,
                aad=_upload_meta_aad(session_id),
                magic=UPLOAD_META_MAGIC,
            )
        except Exception:
            shutil.rmtree(session_dir, ignore_errors=True)
            raise
        return {
            **value,
            "completed_chunks": 0,
            "completed_ranges": [],
            "storage_free_bytes": int(capacity["free_bytes"]),
            "storage_reserve_bytes": int(capacity["reserve_bytes"]),
        }

    def get_session(self, master_key: bytes, session_id: str) -> dict[str, Any]:
        session_id = _clean_id(session_id, "上传会话标识")
        value = _read_encrypted_json(
            self._session_meta_path(session_id),
            master_key=master_key,
            aad=_upload_meta_aad(session_id),
            magic=UPLOAD_META_MAGIC,
        )
        if value.get("format_version") != CHUNKED_MEDIA_FORMAT_VERSION:
            raise LargeFileError("上传会话格式版本不受支持")
        if value.get("session_id") != session_id:
            raise LargeFileError("上传会话元数据不匹配")
        return value

    def _completed_indices(self, session_id: str, *, chunk_count: int) -> list[int]:
        directory = self._session_chunk_dir(session_id)
        if not directory.is_dir():
            return []
        indices: list[int] = []
        for path in directory.iterdir():
            if not path.is_file():
                continue
            match = _CHUNK_NAME.fullmatch(path.name)
            if not match:
                continue
            index = int(match.group(1))
            if 0 <= index < chunk_count:
                indices.append(index)
        return sorted(set(indices))

    def status(self, master_key: bytes, session_id: str) -> dict[str, Any]:
        value = self.get_session(master_key, session_id)
        indices = self._completed_indices(session_id, chunk_count=int(value["chunk_count"]))
        completed_bytes = 0
        chunk_size = int(value["chunk_size"])
        total_size = int(value["size_bytes"])
        for index in indices:
            completed_bytes += min(chunk_size, total_size - index * chunk_size)
        return {
            **value,
            "completed_chunks": len(indices),
            "completed_bytes": completed_bytes,
            "completed_ranges": _compact_ranges(indices),
            "complete": len(indices) == int(value["chunk_count"]),
        }

    def update_video_metadata(
        self,
        master_key: bytes,
        session_id: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Persist lightweight video metadata inside the encrypted upload session."""
        value = self.get_session(master_key, session_id)
        value["video_metadata"] = dict(metadata or {})
        value["updated_at"] = datetime.now(timezone.utc).isoformat()
        _write_encrypted_json(
            self._session_meta_path(session_id),
            master_key=master_key,
            value=value,
            aad=_upload_meta_aad(session_id),
            magic=UPLOAD_META_MAGIC,
        )
        return self.status(master_key, session_id)

    def put_preview(
        self,
        master_key: bytes,
        session_id: str,
        content: bytes,
        *,
        media_type: str | None,
    ) -> dict[str, Any]:
        value = self.get_session(master_key, session_id)
        if not content:
            raise LargeFileError("视频封面为空")
        if len(content) > MAX_UPLOAD_PREVIEW_BYTES:
            raise LargeFileError("视频封面不能超过 512 KB")
        clean_type = str(media_type or "").split(";", 1)[0].strip().lower()
        if clean_type not in {"image/jpeg", "image/webp", "image/png"}:
            raise LargeFileError("视频封面仅支持 JPEG、WebP 或 PNG")
        media_id = str(value["media_id"])
        _write_encrypted_json(
            self._session_preview_path(session_id),
            master_key=master_key,
            value={
                "media_id": media_id,
                "media_type": clean_type,
                "content_b64": base64.b64encode(content).decode("ascii"),
            },
            aad=_preview_aad(media_id),
            magic=UPLOAD_PREVIEW_MAGIC,
        )
        return {
            "session_id": session_id,
            "media_id": media_id,
            "media_type": clean_type,
            "size_bytes": len(content),
            "stored": True,
        }

    def read_committed_preview(
        self,
        master_key: bytes,
        media_id: str,
    ) -> tuple[str, bytes] | None:
        path = self._media_preview_path(media_id)
        if not path.is_file():
            return None
        value = _read_encrypted_json(
            path,
            master_key=master_key,
            aad=_preview_aad(media_id),
            magic=UPLOAD_PREVIEW_MAGIC,
        )
        if str(value.get("media_id") or "") != str(media_id):
            raise LargeFileError("视频封面元数据不匹配")
        try:
            content = base64.b64decode(str(value.get("content_b64") or ""), validate=True)
        except Exception as exc:
            raise LargeFileError("视频封面数据损坏") from exc
        if not content or len(content) > MAX_UPLOAD_PREVIEW_BYTES:
            raise LargeFileError("视频封面数据无效")
        return str(value.get("media_type") or "image/jpeg"), content

    def delete_committed_preview(self, media_id: str) -> None:
        self._media_preview_path(media_id).unlink(missing_ok=True)

    def _begin_chunk_write(self, session_id: str, index: int) -> threading.Lock:
        session_id = _clean_id(session_id, "上传会话标识")
        index = int(index)
        if not self._writer_slots.acquire(timeout=60):
            raise LargeFileError("大型资料上传并发繁忙，请稍后重试")
        try:
            with self._state:
                if session_id in self._blocked_sessions:
                    raise LargeFileError("上传会话正在结束，请稍后重试")
                self._active_writers[session_id] = self._active_writers.get(session_id, 0) + 1
                return self._chunk_locks.setdefault((session_id, index), threading.Lock())
        except Exception:
            self._writer_slots.release()
            raise

    def _end_chunk_write(self, session_id: str) -> None:
        try:
            with self._state:
                remaining = max(0, self._active_writers.get(session_id, 0) - 1)
                if remaining:
                    self._active_writers[session_id] = remaining
                else:
                    self._active_writers.pop(session_id, None)
                    self._state.notify_all()
        finally:
            self._writer_slots.release()

    def _block_session_and_wait(self, session_id: str) -> str:
        session_id = _clean_id(session_id, "上传会话标识")
        with self._state:
            if session_id in self._blocked_sessions:
                raise LargeFileError("上传会话正在结束，请稍后重试")
            self._blocked_sessions.add(session_id)
            while self._active_writers.get(session_id, 0):
                self._state.wait()
        return session_id

    def _release_blocked_session(self, session_id: str) -> None:
        with self._state:
            self._blocked_sessions.discard(session_id)
            stale = [key for key in self._chunk_locks if key[0] == session_id]
            for key in stale:
                self._chunk_locks.pop(key, None)
            self._state.notify_all()

    def put_chunk(
        self,
        master_key: bytes,
        session_id: str,
        index: int,
        plaintext: bytes,
    ) -> dict[str, Any]:
        session_id = _clean_id(session_id, "上传会话标识")
        chunk_lock = self._begin_chunk_write(session_id, index)
        try:
            # Only identical chunk indexes serialize. Different indexes can use
            # separate request threads and disk/encryption capacity concurrently.
            with chunk_lock:
                value = self.get_session(master_key, session_id)
                index = int(index)
                chunk_count = int(value["chunk_count"])
                if not 0 <= index < chunk_count:
                    raise LargeFileError("分块序号超出上传会话范围")
                chunk_size = int(value["chunk_size"])
                total_size = int(value["size_bytes"])
                expected_size = min(chunk_size, total_size - index * chunk_size)
                if len(plaintext) != expected_size:
                    raise LargeFileError(
                        f"分块大小不正确：应为 {expected_size} 字节，实际为 {len(plaintext)} 字节"
                    )
                path = self._session_chunk_path(session_id, index)
                incoming_sha256 = hashlib.sha256(plaintext).hexdigest()
                if path.is_file():
                    existing = ChunkedMediaStore._read_chunk_path(
                        path,
                        master_key=master_key,
                        media_id=str(value["media_id"]),
                        expected_index=index,
                    )
                    if len(existing) == len(plaintext) and hashlib.sha256(existing).hexdigest() == incoming_sha256:
                        return {
                            "index": index,
                            "size_bytes": len(plaintext),
                            "sha256": incoming_sha256,
                            "already_present": True,
                        }
                    raise LargeFileConflict("该分块已存在，但内容与本次上传不一致")

                ensure_disk_space(
                    path.parent,
                    len(plaintext) + CHUNK_HEADER.size + 16,
                    reserve_bytes=MEDIA_CHUNK_WRITE_RESERVE_BYTES,
                )
                result = ChunkedMediaStore._write_chunk_path(
                    path,
                    master_key=master_key,
                    media_id=str(value["media_id"]),
                    index=index,
                    plaintext=plaintext,
                )
                result["already_present"] = False
                return result
        finally:
            self._end_chunk_write(session_id)


    def finalize(self, master_key: bytes, session_id: str) -> dict[str, Any]:
        session_id = self._block_session_and_wait(session_id)
        try:
            value = self.get_session(master_key, session_id)
            chunk_count = int(value["chunk_count"])
            indices = self._completed_indices(session_id, chunk_count=chunk_count)
            if indices != list(range(chunk_count)):
                raise LargeFileError("上传尚未完成，不能合并入媒体库")

            media_id = str(value["media_id"])
            chunk_size = int(value["chunk_size"])
            total_size = int(value["size_bytes"])
            digest = hashlib.sha256()
            verified_size = 0
            for index in range(chunk_count):
                plaintext = ChunkedMediaStore._read_chunk_path(
                    self._session_chunk_path(session_id, index),
                    master_key=master_key,
                    media_id=media_id,
                    expected_index=index,
                )
                expected = min(chunk_size, total_size - index * chunk_size)
                if len(plaintext) != expected:
                    raise LargeFileError(f"分块 {index} 大小校验失败")
                digest.update(plaintext)
                verified_size += len(plaintext)

            if verified_size != total_size:
                raise LargeFileError("大型资料总大小校验失败")
            finished_at = datetime.now(timezone.utc).isoformat()
            manifest = {
                **value,
                "format_version": CHUNKED_MEDIA_FORMAT_VERSION,
                "storage_kind": "chunked-v1",
                "sha256": digest.hexdigest(),
                "finalized_at": finished_at,
            }
            _write_encrypted_json(
                self._session_dir(session_id) / "manifest.lgmedia",
                master_key=master_key,
                value=manifest,
                aad=_manifest_aad(media_id),
                magic=MEDIA_MANIFEST_MAGIC,
            )
            self._session_meta_path(session_id).unlink(missing_ok=True)

            target = self.store.media_dir(media_id)
            if target.exists():
                raise LargeFileConflict("大型媒体目标目录已经存在")
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.replace(self._session_dir(session_id), target)
            except OSError as exc:
                raise LargeFileError("无法将上传会话提交到大型媒体库") from exc
            return manifest
        finally:
            self._release_blocked_session(session_id)


    def _session_last_activity_timestamp(self, session_id: str) -> float:
        directory = self._session_dir(session_id)
        candidates = [directory, self._session_meta_path(session_id), self._session_chunk_dir(session_id), self._session_preview_path(session_id)]
        latest = 0.0
        for path in candidates:
            try:
                latest = max(latest, path.stat().st_mtime)
            except OSError:
                continue
        return latest

    def maintenance_status(self, master_key: bytes, *, stale_days: int = DEFAULT_STALE_UPLOAD_DAYS) -> dict[str, Any]:
        stale_days = max(7, min(365, int(stale_days)))
        cutoff = datetime.now(timezone.utc).timestamp() - stale_days * 86400
        pending = stale = invalid = 0
        pending_bytes = stale_bytes = 0
        if not self.incoming_root.is_dir():
            return {
                "pending_sessions": 0, "pending_bytes": 0, "stale_sessions": 0,
                "stale_bytes": 0, "invalid_sessions": 0, "stale_days": stale_days,
            }
        for directory in self.incoming_root.iterdir():
            if not directory.is_dir() or not _SAFE_ID.fullmatch(directory.name):
                continue
            session_id = directory.name
            try:
                value = self.get_session(master_key, session_id)
                total = int(value.get("size_bytes") or 0)
            except LargeFileError:
                invalid += 1
                total = 0
            pending += 1
            pending_bytes += max(0, total)
            if self._session_last_activity_timestamp(session_id) < cutoff:
                stale += 1
                stale_bytes += max(0, total)
        return {
            "pending_sessions": pending,
            "pending_bytes": pending_bytes,
            "stale_sessions": stale,
            "stale_bytes": stale_bytes,
            "invalid_sessions": invalid,
            "stale_days": stale_days,
        }

    def cleanup_stale_sessions(self, master_key: bytes, *, stale_days: int = DEFAULT_STALE_UPLOAD_DAYS) -> dict[str, Any]:
        stale_days = max(7, min(365, int(stale_days)))
        cutoff = datetime.now(timezone.utc).timestamp() - stale_days * 86400
        removed = 0
        removed_bytes = 0
        skipped_active = 0
        if not self.incoming_root.is_dir():
            return {"removed_sessions": 0, "removed_bytes": 0, "skipped_active": 0, "stale_days": stale_days}
        for directory in list(self.incoming_root.iterdir()):
            if not directory.is_dir() or not _SAFE_ID.fullmatch(directory.name):
                continue
            session_id = directory.name
            if self._session_last_activity_timestamp(session_id) >= cutoff:
                continue
            with self._state:
                if self._active_writers.get(session_id, 0) or session_id in self._blocked_sessions:
                    skipped_active += 1
                    continue
            try:
                value = self.get_session(master_key, session_id)
                removed_bytes += max(0, int(value.get("size_bytes") or 0))
            except LargeFileError:
                pass
            try:
                self.cancel(session_id)
                removed += 1
            except LargeFileError:
                skipped_active += 1
        return {
            "removed_sessions": removed,
            "removed_bytes": removed_bytes,
            "skipped_active": skipped_active,
            "stale_days": stale_days,
        }

    def cancel(self, session_id: str) -> None:
        session_id = self._block_session_and_wait(session_id)
        try:
            shutil.rmtree(self._session_dir(session_id), ignore_errors=True)
            try:
                self.incoming_root.rmdir()
            except OSError:
                pass
        finally:
            self._release_blocked_session(session_id)
