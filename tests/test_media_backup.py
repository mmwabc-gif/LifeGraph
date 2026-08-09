from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services import media_backup as media_backup_module
from app.services.media_backup import (
    MEDIA_BACKUP_MANIFEST,
    MediaBackupError,
    inspect_media_backup_target,
    sync_media_backup,
    verify_media_backup,
)


def _media_item(media_id: str = "ab-media-001", *, size_bytes: int = 12) -> dict:
    return {
        "attachment_id": "attachment-1",
        "media_id": media_id,
        "size_bytes": size_bytes,
        "sha256": "plain-sha",
        "chunk_size": 8,
        "chunk_count": 2,
        "state_at_backup": "online",
        "relative_path": f"{media_id[:2]}/{media_id}",
    }


def _prepare_source(root: Path, item: dict) -> None:
    media_dir = root / item["relative_path"]
    chunks = media_dir / "chunks"
    chunks.mkdir(parents=True)
    (media_dir / "manifest.lgmedia").write_bytes(b"encrypted-manifest")
    (chunks / "00000000.lgchunk").write_bytes(b"encrypted-chunk-0")
    (chunks / "00000001.lgchunk").write_bytes(b"encrypted-chunk-1")


def test_media_backup_is_incremental_and_verifiable(tmp_path: Path) -> None:
    source = tmp_path / "source-media"
    target = tmp_path / "external-backup"
    item = _media_item()
    _prepare_source(source, item)

    first = sync_media_backup(source_root=source, target_root=target, original_media=[item])
    assert first["copied_files"] == 3
    assert first["skipped_files"] == 0
    assert (target / "media" / item["relative_path"] / "chunks" / "00000001.lgchunk").is_file()
    assert (target / MEDIA_BACKUP_MANIFEST).is_file()

    second = sync_media_backup(source_root=source, target_root=target, original_media=[item])
    assert second["copied_files"] == 0
    assert second["skipped_files"] == 3

    verified = verify_media_backup(target_root=target, original_media=[item])
    assert verified["verified_files"] == 3
    status = inspect_media_backup_target(target, [item])
    assert status["state"] == "synced"
    assert status["current"] is True
    assert status["last_verified_at"]

    backup_chunk = target / "media" / item["relative_path"] / "chunks" / "00000000.lgchunk"
    backup_chunk.write_bytes(b"corrupted")
    try:
        verify_media_backup(target_root=target, original_media=[item])
    except MediaBackupError as exc:
        assert "大小异常" in str(exc) or "校验失败" in str(exc)
    else:
        raise AssertionError("corrupted media backup should fail verification")




def test_media_backup_checks_incremental_target_free_space(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source-media"
    target = tmp_path / "external-backup"
    item = _media_item()
    _prepare_source(source, item)
    monkeypatch.setattr(
        media_backup_module.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=1024, used=512, free=512),
    )
    try:
        sync_media_backup(source_root=source, target_root=target, original_media=[item])
    except MediaBackupError as exc:
        assert "剩余空间不足" in str(exc)
    else:
        raise AssertionError("insufficient backup disk space should fail before copy")

def test_media_backup_manifest_becomes_stale_when_inventory_changes(tmp_path: Path) -> None:
    source = tmp_path / "source-media"
    target = tmp_path / "external-backup"
    item = _media_item()
    _prepare_source(source, item)
    sync_media_backup(source_root=source, target_root=target, original_media=[item])

    changed = dict(item)
    changed["sha256"] = "new-plain-sha"
    status = inspect_media_backup_target(target, [changed])
    assert status["state"] == "stale"
    assert status["current"] is False


def _make_client(data_dir: Path) -> TestClient:
    return TestClient(create_app(Settings(data_dir=data_dir, session_ttl_seconds=60)))


def _initialize(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/initialize",
        json={
            "display_name": "媒体备份测试",
            "birth_date": "1990-01-01",
            "target_age": 100,
            "timezone": "Asia/Shanghai",
            "pin": "123456",
            "recovery_secret": "media-backup-recovery-secret",
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


def test_media_backup_api_accepts_target_and_reports_job(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    target = tmp_path / "external"
    client = _make_client(data_dir)
    headers = _initialize(client)

    started = client.post(
        "/api/v1/backup/media/sync",
        headers=headers,
        json={"target_path": str(target)},
    )
    assert started.status_code == 200, started.text

    deadline = time.time() + 5
    job = {}
    while time.time() < deadline:
        response = client.get("/api/v1/backup/media/job", headers=headers)
        assert response.status_code == 200, response.text
        job = response.json()["data"]
        if job.get("state") not in {"running", "cancelling"}:
            break
        time.sleep(0.02)
    assert job.get("state") == "completed", job

    status = client.get("/api/v1/backup/media/status", headers=headers)
    assert status.status_code == 200, status.text
    external = status.json()["data"]["external_backup"]
    assert external["configured"] is True
    assert external["current"] is True
    assert Path(external["target_path"]) == target.resolve()
    assert (data_dir / ".media-backup-target.lgcfg").is_file()
    assert str(target).encode("utf-8") not in (data_dir / ".media-backup-target.lgcfg").read_bytes()
