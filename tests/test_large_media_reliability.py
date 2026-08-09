from __future__ import annotations

import os
import time
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services import large_files as large_files_module


MIB = 1024 * 1024


def make_client(data_dir: Path) -> TestClient:
    return TestClient(create_app(Settings(data_dir=data_dir, session_ttl_seconds=60)))


def initialize(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/initialize",
        json={
            "display_name": "大媒体可靠性测试",
            "birth_date": "1990-01-01",
            "target_age": 100,
            "timezone": "Asia/Shanghai",
            "pin": "123456",
            "recovery_secret": "large-media-reliability-secret",
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


def create_upload(client: TestClient, headers: dict[str, str], payload: bytes, *, filename: str = "video.mp4") -> dict:
    response = client.post(
        "/api/v1/materials/large/uploads",
        headers=headers,
        json={
            "filename": filename,
            "media_type": "video/mp4",
            "size_bytes": len(payload),
            "chunk_size": MIB,
            "file_last_modified_ms": 1786248000000,
            "reject_duplicate": False,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def finalize_payload(client: TestClient, headers: dict[str, str], payload: bytes, *, filename: str = "video.mp4") -> dict:
    upload = create_upload(client, headers, payload, filename=filename)
    for index, offset in enumerate(range(0, len(payload), MIB)):
        response = client.put(
            f"/api/v1/materials/large/uploads/{upload['session_id']}/chunks/{index}",
            headers={**headers, "Content-Type": "application/octet-stream"},
            content=payload[offset : offset + MIB],
        )
        assert response.status_code == 200, response.text
    finalized = client.post(
        f"/api/v1/materials/large/uploads/{upload['session_id']}/finalize",
        headers=headers,
    )
    assert finalized.status_code == 200, finalized.text
    return finalized.json()["data"]


def wait_media_job(client: TestClient, headers: dict[str, str], *, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    last = {}
    while time.monotonic() < deadline:
        response = client.get("/api/v1/backup/media/job", headers=headers)
        assert response.status_code == 200, response.text
        last = response.json()["data"]
        if last.get("state") not in {"running", "cancelling"}:
            return last
        time.sleep(0.02)
    raise AssertionError(f"media job timeout: {last}")


def test_large_upload_disk_space_preflight_rejects_before_session_creation(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)

    monkeypatch.setattr(
        large_files_module.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=2 * MIB, used=MIB, free=MIB),
    )
    response = client.post(
        "/api/v1/materials/large/uploads",
        headers=headers,
        json={
            "filename": "too-large.mp4",
            "media_type": "video/mp4",
            "size_bytes": 100 * MIB,
            "chunk_size": MIB,
            "reject_duplicate": False,
        },
    )
    assert response.status_code == 400
    assert "磁盘剩余空间不足" in response.json()["error"]["message"]
    assert not (tmp_path / "vault" / "media" / ".incoming").exists()


def test_stale_large_upload_cleanup_api_removes_only_old_session(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)
    payload = b"x" * (MIB + 17)
    upload = create_upload(client, headers, payload, filename="paused.mp4")

    vault = client.app.state.vault
    session_dir = vault.large_uploads._session_dir(upload["session_id"])
    old = time.time() - 45 * 86400
    for path in (
        session_dir,
        vault.large_uploads._session_meta_path(upload["session_id"]),
        vault.large_uploads._session_chunk_dir(upload["session_id"]),
    ):
        os.utime(path, (old, old))

    status = client.get(
        "/api/v1/materials/large/uploads/maintenance?stale_days=30",
        headers=headers,
    )
    assert status.status_code == 200, status.text
    assert status.json()["data"]["stale_sessions"] == 1

    cleaned = client.post(
        "/api/v1/materials/large/uploads/cleanup",
        headers=headers,
        json={"stale_days": 30},
    )
    assert cleaned.status_code == 200, cleaned.text
    assert cleaned.json()["data"]["removed_sessions"] == 1
    assert not session_dir.exists()

    missing = client.get(
        f"/api/v1/materials/large/uploads/{upload['session_id']}",
        headers=headers,
    )
    assert missing.status_code == 404


def test_original_media_deep_verify_detects_encrypted_chunk_tampering(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)
    payload = bytes((index % 251 for index in range(MIB + 123_456)))
    material = finalize_payload(client, headers, payload, filename="verify.mp4")

    started = client.post("/api/v1/backup/media/verify-library", headers=headers)
    assert started.status_code == 200, started.text
    verified = wait_media_job(client, headers)
    assert verified["state"] == "completed"
    assert verified["verified_media"] == 1
    assert verified["verified_files"] == 2

    vault = client.app.state.vault
    chunk = vault.large_uploads.store.chunk_path(material["media_id"], 0)
    damaged = bytearray(chunk.read_bytes())
    damaged[-1] ^= 0x01
    chunk.write_bytes(damaged)

    restarted = client.post("/api/v1/backup/media/verify-library", headers=headers)
    assert restarted.status_code == 200, restarted.text
    failed = wait_media_job(client, headers)
    assert failed["state"] == "failed"
    assert "完整性" in str(failed.get("error") or "") or "校验" in str(failed.get("error") or "")


def test_range_stream_uses_bounded_plaintext_cache_and_lock_clears_it(tmp_path: Path, monkeypatch) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)
    payload = bytes((index % 239 for index in range(2 * MIB + 99)))
    material = finalize_payload(client, headers, payload, filename="cache.mp4")
    vault = client.app.state.vault

    original_read_chunk = vault.large_uploads.store.read_chunk
    calls: list[int] = []

    def counted_read_chunk(master_key: bytes, media_id: str, index: int) -> bytes:
        calls.append(index)
        return original_read_chunk(master_key, media_id, index)

    monkeypatch.setattr(vault.large_uploads.store, "read_chunk", counted_read_chunk)
    ticket_response = client.post(
        f"/api/v1/attachments/{material['id']}/playback-ticket",
        headers=headers,
    )
    assert ticket_response.status_code == 200, ticket_response.text
    ticket = ticket_response.json()["data"]["ticket"]
    url = f"/api/v1/attachments/{material['id']}/stream?ticket={ticket}"

    first = client.get(url, headers={"Range": "bytes=100-999"})
    assert first.status_code == 206
    second = client.get(url, headers={"Range": "bytes=2000-2999"})
    assert second.status_code == 206
    assert calls == [0]
    assert vault._media_chunk_cache_bytes > 0
    assert vault._media_chunk_cache_bytes <= 64 * MIB

    locked = client.post("/api/v1/auth/lock")
    assert locked.status_code == 200
    assert vault._media_chunk_cache_bytes == 0
    assert not vault._media_chunk_cache
