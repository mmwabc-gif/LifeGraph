from __future__ import annotations

import struct
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_client(data_dir: Path) -> TestClient:
    return TestClient(create_app(Settings(data_dir=data_dir, session_ttl_seconds=60)))


def initialize(client: TestClient, *, pin: str = "123456") -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/initialize",
        json={
            "display_name": "时间索引测试用户",
            "birth_date": "1990-01-01",
            "target_age": 100,
            "timezone": "Asia/Shanghai",
            "pin": pin,
            "recovery_secret": "timeline-backfill-test-recovery-secret",
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


def create_memory(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "time_scope": "day",
            "period_key": "2026-08-08",
            "title": "时间索引测试",
            "content": "正文",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def upload_attachment(
    client: TestClient,
    headers: dict[str, str],
    memory_id: str,
    *,
    filename: str,
    content: bytes,
    media_type: str,
) -> dict:
    response = client.post(
        f"/api/v1/content/memory/{memory_id}/attachments",
        headers=headers,
        files={"attachment_file": (filename, content, media_type)},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def jpeg_with_exif_datetime(value: str, offset: str) -> bytes:
    datetime_bytes = value.encode("ascii") + b"\x00"
    offset_bytes = offset.encode("ascii") + b"\x00"
    ifd0_offset = 8
    exif_ifd_offset = 26
    datetime_offset = 56
    offset_time_offset = datetime_offset + len(datetime_bytes)
    tiff = bytearray()
    tiff.extend(b"II")
    tiff.extend(struct.pack("<H", 42))
    tiff.extend(struct.pack("<I", ifd0_offset))
    tiff.extend(struct.pack("<H", 1))
    tiff.extend(struct.pack("<HHII", 0x8769, 4, 1, exif_ifd_offset))
    tiff.extend(struct.pack("<I", 0))
    tiff.extend(struct.pack("<H", 2))
    tiff.extend(struct.pack("<HHII", 0x9003, 2, len(datetime_bytes), datetime_offset))
    tiff.extend(struct.pack("<HHII", 0x9011, 2, len(offset_bytes), offset_time_offset))
    tiff.extend(struct.pack("<I", 0))
    tiff.extend(datetime_bytes)
    tiff.extend(offset_bytes)
    exif_segment = b"Exif\x00\x00" + bytes(tiff)
    app1 = b"\xff\xe1" + struct.pack(">H", len(exif_segment) + 2) + exif_segment
    return b"\xff\xd8" + app1 + b"\xff\xd9"


def wait_for_backfill(client: TestClient, headers: dict[str, str], timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    latest = None
    while time.monotonic() < deadline:
        response = client.get("/api/v1/materials/timeline-backfill", headers=headers)
        assert response.status_code == 200, response.text
        latest = response.json()["data"]
        if latest["state"] != "running":
            return latest
        time.sleep(0.03)
    raise AssertionError(f"timeline backfill did not finish: {latest}")


def test_timeline_backfill_mirrors_existing_encrypted_metadata_without_rewriting_it(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)
    memory = create_memory(client, headers)
    attachment = upload_attachment(
        client,
        headers,
        memory["id"],
        filename="legacy-camera.jpg",
        content=jpeg_with_exif_datetime("2017:04:05 06:07:08", "+08:00"),
        media_type="image/jpeg",
    )

    vault = client.app.state.vault
    with vault.database.connect() as connection:
        before = connection.execute(
            "SELECT metadata_nonce, metadata_ciphertext, updated_at FROM attachments WHERE id=?",
            (attachment["id"],),
        ).fetchone()
        connection.execute(
            """
            UPDATE attachments
            SET timeline_at=NULL, timeline_end_at=NULL, time_precision=NULL,
                time_source=NULL, time_confidence=NULL, timezone_offset=NULL
            WHERE id=?
            """,
            (attachment["id"],),
        )

    status = client.get("/api/v1/materials/timeline-backfill", headers=headers)
    assert status.status_code == 200
    assert status.json()["data"]["pending"] == 1

    started = client.post("/api/v1/materials/timeline-backfill/start", headers=headers)
    assert started.status_code == 200, started.text
    finished = wait_for_backfill(client, headers)
    assert finished["state"] == "completed"
    assert finished["pending"] == 0
    assert finished["indexed"] == 1

    with vault.database.connect() as connection:
        after = connection.execute(
            """
            SELECT timeline_at, time_precision, time_source, time_confidence,
                   timezone_offset, metadata_nonce, metadata_ciphertext, updated_at
            FROM attachments WHERE id=?
            """,
            (attachment["id"],),
        ).fetchone()
    assert after["timeline_at"] == "2017-04-05T06:07:08+08:00"
    assert after["time_precision"] == "second"
    assert after["time_source"] == "exif:DateTimeOriginal"
    assert after["time_confidence"] == "high"
    assert after["timezone_offset"] == "+08:00"
    assert after["metadata_nonce"] == before["metadata_nonce"]
    assert after["metadata_ciphertext"] == before["metadata_ciphertext"]
    assert after["updated_at"] == before["updated_at"]


def test_timeline_backfill_reextracts_time_for_genuinely_legacy_metadata(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)
    memory = create_memory(client, headers)
    attachment = upload_attachment(
        client,
        headers,
        memory["id"],
        filename="old-camera.jpg",
        content=jpeg_with_exif_datetime("2016:03:04 05:06:07", "+09:00"),
        media_type="image/jpeg",
    )

    vault = client.app.state.vault
    master_key = vault.require_master_key()
    profile = vault.get_profile()
    stored = vault.database.get_attachment(
        master_key,
        profile_id=profile["id"],
        attachment_id=attachment["id"],
    )
    vault.database.update_attachment_metadata(
        master_key,
        profile_id=profile["id"],
        attachment_id=attachment["id"],
        metadata={
            "filename": stored["filename"],
            "media_type": stored["media_type"],
            "size_bytes": stored["size_bytes"],
            "sha256": stored["sha256"],
        },
        timestamp=stored["updated_at"],
    )

    with vault.database.connect() as connection:
        row = connection.execute(
            "SELECT timeline_at, time_precision FROM attachments WHERE id=?",
            (attachment["id"],),
        ).fetchone()
    assert row["timeline_at"] is None
    assert row["time_precision"] is None

    started = client.post("/api/v1/materials/timeline-backfill/start", headers=headers)
    assert started.status_code == 200, started.text
    finished = wait_for_backfill(client, headers)
    assert finished["state"] == "completed"
    assert finished["indexed"] == 1

    with vault.database.connect() as connection:
        row = connection.execute(
            """
            SELECT timeline_at, time_precision, time_source, time_confidence, timezone_offset
            FROM attachments WHERE id=?
            """,
            (attachment["id"],),
        ).fetchone()
    assert tuple(row) == (
        "2016-03-04T05:06:07+09:00",
        "second",
        "exif:DateTimeOriginal",
        "high",
        "+09:00",
    )


def test_timeline_backfill_status_is_completed_when_library_is_already_indexed(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    memory = create_memory(client, headers)
    upload_attachment(client, headers, memory["id"], filename="ready.txt", content=b"ready", media_type="text/plain")

    response = client.get("/api/v1/materials/timeline-backfill", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert data["indexed"] == 1
    assert data["pending"] == 0
    assert data["state"] == "completed"
    assert data["progress_percent"] == 100.0


def test_timeline_backfill_can_pause_and_continue(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    memory = create_memory(client, headers)
    attachment_ids = []
    for index in range(8):
        attachment = upload_attachment(
            client,
            headers,
            memory["id"],
            filename=f"pause-{index}.txt",
            content=f"pause-{index}".encode(),
            media_type="text/plain",
        )
        attachment_ids.append(attachment["id"])

    vault = client.app.state.vault
    with vault.database.connect() as connection:
        connection.executemany(
            """
            UPDATE attachments
            SET timeline_at=NULL, timeline_end_at=NULL, time_precision=NULL,
                time_source=NULL, time_confidence=NULL, timezone_offset=NULL
            WHERE id=?
            """,
            [(value,) for value in attachment_ids],
        )

    original_get_attachment = vault.database.get_attachment

    def slow_get_attachment(*args, **kwargs):
        time.sleep(0.04)
        return original_get_attachment(*args, **kwargs)

    monkeypatch.setattr(vault.database, "get_attachment", slow_get_attachment)

    started = client.post("/api/v1/materials/timeline-backfill/start", headers=headers)
    assert started.status_code == 200
    assert started.json()["data"]["state"] == "running"

    time.sleep(0.06)
    paused = client.post("/api/v1/materials/timeline-backfill/pause", headers=headers)
    assert paused.status_code == 200
    assert paused.json()["data"]["state"] == "paused"
    time.sleep(0.08)

    paused_status = client.get("/api/v1/materials/timeline-backfill", headers=headers).json()["data"]
    assert paused_status["state"] == "paused"
    assert paused_status["pending"] > 0

    resumed = client.post("/api/v1/materials/timeline-backfill/start", headers=headers)
    assert resumed.status_code == 200
    finished = wait_for_backfill(client, headers, timeout=8.0)
    assert finished["state"] == "completed"
    assert finished["pending"] == 0
    assert finished["indexed"] == 8
