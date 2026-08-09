from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.services.large_files import (
    CHUNK_HEADER,
    ChunkedMediaStore,
    LargeFileConflict,
    LargeFileError,
    LargeUploadManager,
    choose_media_chunk_size,
)


def test_adaptive_chunk_size_for_large_files() -> None:
    assert choose_media_chunk_size(1 * 1024**3) == 4 * 1024**2
    assert choose_media_chunk_size(7 * 1024**3) == 8 * 1024**2
    assert choose_media_chunk_size(16 * 1024**3) == 8 * 1024**2
    assert choose_media_chunk_size(100 * 1024**3) == 16 * 1024**2
    assert choose_media_chunk_size(300 * 1024**3) == 32 * 1024**2
    with pytest.raises(LargeFileError):
        choose_media_chunk_size(0)


def test_resumable_session_tracks_chunks_and_accepts_idempotent_retry(tmp_path: Path) -> None:
    manager = LargeUploadManager(tmp_path / "media")
    key = os.urandom(32)
    chunk_size = 1024 * 1024
    payload = b"a" * chunk_size + b"b" * chunk_size + b"c" * 12345
    session = manager.create_session(
        key,
        filename="旅行视频.mp4",
        media_type="video/mp4",
        size_bytes=len(payload),
        chunk_size=chunk_size,
    )

    first = manager.put_chunk(key, session["session_id"], 0, payload[:chunk_size])
    assert first["already_present"] is False
    retried = manager.put_chunk(key, session["session_id"], 0, payload[:chunk_size])
    assert retried["already_present"] is True

    manager.put_chunk(key, session["session_id"], 2, payload[2 * chunk_size :])
    status = manager.status(key, session["session_id"])
    assert status["completed_chunks"] == 2
    assert status["completed_ranges"] == [[0, 0], [2, 2]]
    assert status["complete"] is False

    with pytest.raises(LargeFileConflict):
        manager.put_chunk(key, session["session_id"], 0, b"z" * chunk_size)



def test_different_chunks_can_write_concurrently(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager = LargeUploadManager(tmp_path / "media")
    key = os.urandom(32)
    chunk_size = 1024 * 1024
    session = manager.create_session(
        key,
        filename="parallel.bin",
        media_type="application/octet-stream",
        size_bytes=chunk_size * 2,
        chunk_size=chunk_size,
    )

    barrier = threading.Barrier(2)
    original = ChunkedMediaStore._write_chunk_path

    def synchronized_write(path: Path, **kwargs):
        barrier.wait(timeout=2)
        return original(path, **kwargs)

    monkeypatch.setattr(ChunkedMediaStore, "_write_chunk_path", staticmethod(synchronized_write))
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(manager.put_chunk, key, session["session_id"], 0, b"a" * chunk_size),
            pool.submit(manager.put_chunk, key, session["session_id"], 1, b"b" * chunk_size),
        ]
        results = [future.result(timeout=5) for future in futures]

    assert {item["index"] for item in results} == {0, 1}
    assert manager.status(key, session["session_id"])["completed_ranges"] == [[0, 1]]

def test_finalize_random_range_and_full_verify(tmp_path: Path) -> None:
    manager = LargeUploadManager(tmp_path / "media")
    key = os.urandom(32)
    chunk_size = 1024 * 1024
    payload = (b"0123456789abcdef" * 160000) + b"tail"
    session = manager.create_session(
        key,
        filename="big-video.mp4",
        media_type="video/mp4",
        size_bytes=len(payload),
        chunk_size=chunk_size,
    )

    for index in reversed(range(session["chunk_count"])):
        start = index * chunk_size
        end = min(len(payload), start + chunk_size)
        manager.put_chunk(key, session["session_id"], index, payload[start:end])

    manifest = manager.finalize(key, session["session_id"])
    assert manifest["storage_kind"] == "chunked-v1"
    assert manifest["size_bytes"] == len(payload)
    assert manager.store.read_manifest(key, manifest["media_id"])["sha256"] == manifest["sha256"]

    start = chunk_size - 111
    end = chunk_size * 2 + 333
    ranged = b"".join(
        manager.store.iter_plain_range(
            key,
            manifest["media_id"],
            total_size=len(payload),
            chunk_size=chunk_size,
            start=start,
            end_exclusive=end,
        )
    )
    assert ranged == payload[start:end]

    report = manager.store.verify(key, manifest["media_id"])
    assert report["verified"] is True
    assert report["size_bytes"] == len(payload)


def test_chunk_ciphertext_hides_plaintext_and_tamper_is_detected(tmp_path: Path) -> None:
    manager = LargeUploadManager(tmp_path / "media")
    key = os.urandom(32)
    chunk_size = 1024 * 1024
    plaintext = b"secret-video-frame-" * 50000
    session = manager.create_session(
        key,
        filename="secret.mp4",
        media_type="video/mp4",
        size_bytes=len(plaintext),
        chunk_size=chunk_size,
    )
    manager.put_chunk(key, session["session_id"], 0, plaintext)
    manager.finalize(key, session["session_id"])

    chunk_path = manager.store.chunk_path(session["media_id"], 0)
    encrypted = chunk_path.read_bytes()
    assert plaintext[:128] not in encrypted
    assert len(encrypted) == CHUNK_HEADER.size + len(plaintext) + 16

    damaged = bytearray(encrypted)
    damaged[-1] ^= 0x01
    chunk_path.write_bytes(damaged)
    with pytest.raises(LargeFileError, match="完整性验证失败"):
        manager.store.read_chunk(key, session["media_id"], 0)


def test_cancel_removes_unfinished_upload(tmp_path: Path) -> None:
    manager = LargeUploadManager(tmp_path / "media")
    key = os.urandom(32)
    session = manager.create_session(
        key,
        filename="cancel.bin",
        media_type="application/octet-stream",
        size_bytes=1024 * 1024,
        chunk_size=1024 * 1024,
    )
    session_dir = manager.incoming_root / session["session_id"]
    assert session_dir.is_dir()
    manager.cancel(session["session_id"])
    assert not session_dir.exists()


def test_chunked_media_store_can_encrypt_stream_without_plaintext_temp_file(tmp_path: Path) -> None:
    store = ChunkedMediaStore(tmp_path / "derived")
    key = os.urandom(32)
    chunk_size = 1024 * 1024
    parts = [b"a" * 700_000, b"b" * 900_000, b"c" * 321_000]
    payload = b"".join(parts)

    manifest = store.write_stream(
        key,
        "aud_test_stream",
        iter(parts),
        chunk_size=chunk_size,
        manifest_extra={"asset_kind": "audio-compat", "media_type": "audio/mp4"},
    )

    assert manifest["size_bytes"] == len(payload)
    assert manifest["chunk_count"] == 2
    restored = b"".join(
        store.iter_plain_chunks(
            key,
            "aud_test_stream",
            total_size=manifest["size_bytes"],
            chunk_size=manifest["chunk_size"],
        )
    )
    assert restored == payload
    assert payload[:128] not in store.chunk_path("aud_test_stream", 0).read_bytes()


def test_buffered_plain_chunks_prefetch_sequentially_without_parallel_disk_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ChunkedMediaStore(tmp_path / "media")
    key = os.urandom(32)
    chunk_size = 1024 * 1024
    media_id = "buffered_test"
    payloads = [bytes([index + 1]) * chunk_size for index in range(4)]
    for index, payload in enumerate(payloads):
        store.write_chunk(key, media_id, index, payload)

    original = store.read_chunk
    entered: list[int] = []
    active = 0
    max_active = 0
    state_lock = threading.Lock()

    def tracked_read(master_key: bytes, target_media_id: str, index: int) -> bytes:
        nonlocal active, max_active
        with state_lock:
            active += 1
            max_active = max(max_active, active)
            entered.append(index)
        try:
            time.sleep(0.02)
            return original(master_key, target_media_id, index)
        finally:
            with state_lock:
                active -= 1

    monkeypatch.setattr(store, "read_chunk", tracked_read)
    iterator = store.iter_plain_chunks_buffered(
        key,
        media_id,
        total_size=chunk_size * len(payloads),
        chunk_size=chunk_size,
        buffer_chunks=2,
    )
    first = next(iterator)
    time.sleep(0.08)
    with state_lock:
        already_prepared = len(entered)
    restored = [first, *list(iterator)]

    assert restored == payloads
    assert entered == [0, 1, 2, 3]
    assert already_prepared >= 2
    assert max_active == 1


def test_regenerable_stream_can_skip_per_chunk_fsync_but_manifest_stays_durable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.services.large_files as large_files_module

    store = ChunkedMediaStore(tmp_path / "derived")
    key = os.urandom(32)
    original_atomic_write = large_files_module._atomic_write
    durable_flags: list[bool] = []

    def recording_atomic_write(path: Path, content: bytes, *, durable: bool = True) -> None:
        durable_flags.append(bool(durable))
        original_atomic_write(path, content, durable=durable)

    monkeypatch.setattr(large_files_module, "_atomic_write", recording_atomic_write)
    payload = b"z" * (1024 * 1024 + 123)
    manifest = store.write_stream(
        key,
        "aud_nondurable_chunks",
        iter((payload,)),
        chunk_size=1024 * 1024,
        durable_chunks=False,
    )

    assert manifest["chunk_count"] == 2
    assert durable_flags.count(False) == 2
    assert durable_flags[-1] is True
