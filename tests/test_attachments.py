from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_client(data_dir: Path) -> TestClient:
    return TestClient(create_app(Settings(data_dir=data_dir, session_ttl_seconds=60)))


def initialize(client: TestClient, *, pin: str = "123456") -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/initialize",
        json={
            "display_name": "附件测试用户",
            "birth_date": "1990-01-01",
            "target_age": 100,
            "timezone": "Asia/Shanghai",
            "pin": pin,
            "recovery_secret": "attachment-test-recovery-secret",
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


def create_memory(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "time_scope": "day",
            "period_key": "2026-08-08",
            "title": "有附件的记忆",
            "content": "正文",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]


def upload_attachment(
    client: TestClient,
    headers: dict[str, str],
    memory_id: str,
    *,
    filename: str = "旅行照片.txt",
    content: bytes = b"lifegraph attachment payload",
    media_type: str = "text/plain",
    file_last_modified_ms: int | None = None,
) -> dict:
    response = client.post(
        f"/api/v1/content/memory/{memory_id}/attachments",
        headers=headers,
        files={"attachment_file": (filename, content, media_type)},
        data={} if file_last_modified_ms is None else {"file_last_modified_ms": str(file_last_modified_ms)},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_legacy_flat_attachment_is_migrated_on_restart_and_remains_readable(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)
    memory = create_memory(client, headers)
    plaintext = b"legacy flat attachment"
    attachment = upload_attachment(client, headers, memory["id"], content=plaintext)

    sharded_path = (
        data_dir
        / "attachments"
        / attachment["id"][:2].lower()
        / f"{attachment['id']}.lgatt"
    )
    legacy_path = data_dir / "attachments" / f"{attachment['id']}.lgatt"
    assert sharded_path.is_file()
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    sharded_path.replace(legacy_path)
    assert legacy_path.is_file()
    assert not sharded_path.exists()

    restarted = make_client(data_dir)
    assert sharded_path.is_file()
    assert not legacy_path.exists()

    unlocked = restarted.post(
        "/api/v1/auth/unlock", json={"method": "pin", "secret": "123456"}
    )
    assert unlocked.status_code == 200
    restarted_headers = {"Authorization": f"Bearer {unlocked.json()['data']['token']}"}
    downloaded = restarted.get(
        f"/api/v1/attachments/{attachment['id']}/download", headers=restarted_headers
    )
    assert downloaded.status_code == 200
    assert downloaded.content == plaintext


def test_attachment_upload_list_download_delete_is_encrypted_on_disk(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)
    memory = create_memory(client, headers)
    plaintext = "这是附件里的明文内容。".encode("utf-8")

    attachment = upload_attachment(
        client,
        headers,
        memory["id"],
        filename="中文附件.txt",
        content=plaintext,
    )
    assert attachment["filename"] == "中文附件.txt"
    assert attachment["size_bytes"] == len(plaintext)
    assert attachment["media_type"].startswith("text/plain")
    assert "file_nonce" not in attachment
    assert "profile_id" not in attachment

    encrypted_path = data_dir / "attachments" / attachment["id"][:2].lower() / f"{attachment['id']}.lgatt"
    assert encrypted_path.exists()
    encrypted_bytes = encrypted_path.read_bytes()
    assert plaintext not in encrypted_bytes
    assert "中文附件.txt".encode("utf-8") not in encrypted_bytes

    listed = client.get(
        f"/api/v1/content/memory/{memory['id']}/attachments", headers=headers
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["data"]] == [attachment["id"]]

    downloaded = client.get(
        f"/api/v1/attachments/{attachment['id']}/download", headers=headers
    )
    assert downloaded.status_code == 200
    assert downloaded.content == plaintext
    assert "filename*=UTF-8''" in downloaded.headers["content-disposition"]

    deleted = client.delete(
        f"/api/v1/content/memory/{memory['id']}/attachments/{attachment['id']}",
        headers=headers,
    )
    assert deleted.status_code == 200
    assert not encrypted_path.exists()
    assert client.get(
        f"/api/v1/attachments/{attachment['id']}/download", headers=headers
    ).status_code == 404


def test_attachment_survives_soft_delete_and_is_removed_on_permanent_delete(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)
    memory = create_memory(client, headers)
    attachment = upload_attachment(client, headers, memory["id"], content=b"keep-with-trash")
    encrypted_path = data_dir / "attachments" / attachment["id"][:2].lower() / f"{attachment['id']}.lgatt"

    moved = client.request(
        "DELETE",
        f"/api/v1/memories/{memory['id']}",
        headers=headers,
        json={"revision": memory["revision"]},
    )
    assert moved.status_code == 200
    assert encrypted_path.exists()

    trash = client.get("/api/v1/trash", headers=headers).json()["data"]["items"]
    trashed = next(item for item in trash if item["id"] == memory["id"])
    purged = client.request(
        "DELETE",
        f"/api/v1/trash/memory/{memory['id']}",
        headers=headers,
        json={"revision": trashed["revision"]},
    )
    assert purged.status_code == 200
    assert not encrypted_path.exists()


def test_lifevault_v3_contains_and_restores_encrypted_attachments(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source = make_client(source_dir)
    source_headers = initialize(source, pin="654321")
    memory = create_memory(source, source_headers)
    plaintext = b"backup attachment bytes"
    attachment = upload_attachment(
        source,
        source_headers,
        memory["id"],
        filename="backup-note.bin",
        content=plaintext,
        media_type="application/octet-stream",
    )

    exported = source.get("/api/v1/backup/export", headers=source_headers)
    assert exported.status_code == 200
    assert exported.headers["x-lifegraph-backup-format"] == "lifegraph-lifevault-v3"
    assert plaintext not in exported.content

    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["format_version"] == 3
        assert "repository/media-inventory.lgindex" in archive.namelist()
        attachment_path = f"repository/attachments/{attachment['id']}.lgatt"
        assert attachment_path in archive.namelist()
        assert plaintext not in archive.read(attachment_path)

    target_dir = tmp_path / "target"
    target = make_client(target_dir)
    target_headers = initialize(target)
    checked = target.post(
        "/api/v1/backup/import/check",
        headers=target_headers,
        files={
            "backup_file": (
                "source.lifevault",
                exported.content,
                "application/vnd.lifegraph.lifevault+zip",
            )
        },
        data={"credential_method": "pin", "credential_secret": "654321"},
    )
    assert checked.status_code == 200, checked.text
    assert checked.json()["data"]["attachment_files_verified"] == 1

    restored = target.post(
        "/api/v1/backup/import",
        headers=target_headers,
        files={
            "backup_file": (
                "source.lifevault",
                exported.content,
                "application/vnd.lifegraph.lifevault+zip",
            )
        },
        data={
            "credential_method": "pin",
            "credential_secret": "654321",
            "confirm": "REPLACE_REPOSITORY",
        },
    )
    assert restored.status_code == 200, restored.text

    unlocked = target.post(
        "/api/v1/auth/unlock", json={"method": "pin", "secret": "654321"}
    )
    assert unlocked.status_code == 200
    restored_headers = {"Authorization": f"Bearer {unlocked.json()['data']['token']}"}
    listed = target.get(
        f"/api/v1/content/memory/{memory['id']}/attachments", headers=restored_headers
    )
    assert listed.status_code == 200
    restored_blob = (
        target_dir
        / "attachments"
        / attachment["id"][:2].lower()
        / f"{attachment['id']}.lgatt"
    )
    assert restored_blob.is_file()
    assert not (target_dir / "attachments" / f"{attachment['id']}.lgatt").exists()
    assert listed.json()["data"][0]["filename"] == "backup-note.bin"
    downloaded = target.get(
        f"/api/v1/attachments/{attachment['id']}/download", headers=restored_headers
    )
    assert downloaded.status_code == 200
    assert downloaded.content == plaintext


def test_legacy_lifevault_v2_with_encrypted_attachment_remains_importable(tmp_path: Path) -> None:
    source = make_client(tmp_path / "source-v2")
    source_headers = initialize(source, pin="654321")
    memory = create_memory(source, source_headers)
    attachment = upload_attachment(
        source, source_headers, memory["id"], filename="legacy-v2.bin", content=b"legacy-v2-bytes"
    )
    current = source.get("/api/v1/backup/export", headers=source_headers).content
    with zipfile.ZipFile(io.BytesIO(current)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        attachment_path = f"repository/attachments/{attachment['id']}.lgatt"
        legacy_paths = {"repository/vault.json", "repository/lifegraph.db", attachment_path}
        manifest["format_version"] = 2
        manifest["files"] = [entry for entry in manifest.get("files", []) if entry.get("path") in legacy_paths]
        payloads = {name: archive.read(name) for name in legacy_paths}

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for name, value in payloads.items():
            archive.writestr(name, value)

    target = make_client(tmp_path / "target-v2")
    target_headers = initialize(target)
    checked = target.post(
        "/api/v1/backup/import/check",
        headers=target_headers,
        files={"backup_file": ("legacy.lifevault", buffer.getvalue(), "application/vnd.lifegraph.lifevault+zip")},
        data={"credential_method": "pin", "credential_secret": "654321"},
    )
    assert checked.status_code == 200, checked.text
    assert checked.json()["data"]["format_version"] == 2
    assert checked.json()["data"]["attachment_files_verified"] == 1


def test_attachment_upload_limit_is_enforced(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    memory = create_memory(client, headers)
    response = client.post(
        f"/api/v1/content/memory/{memory['id']}/attachments",
        headers=headers,
        files={"attachment_file": ("large.bin", b"x" * (50 * 1024 * 1024 + 1), "application/octet-stream")},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "ATTACHMENT_TOO_LARGE"


def test_period_detail_includes_attachment_count_before_panel_is_opened(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    memory = create_memory(client, headers)

    before = client.get("/api/v1/dates/2026-08-08", headers=headers)
    assert before.status_code == 200
    memory_before = next(item for item in before.json()["data"]["memories"] if item["id"] == memory["id"])
    assert memory_before["attachment_count"] == 0

    upload_attachment(client, headers, memory["id"], filename="one.txt", content=b"one")
    upload_attachment(client, headers, memory["id"], filename="two.txt", content=b"two")

    after = client.get("/api/v1/dates/2026-08-08", headers=headers)
    assert after.status_code == 200
    memory_after = next(item for item in after.json()["data"]["memories"] if item["id"] == memory["id"])
    assert memory_after["attachment_count"] == 2


def jpeg_with_exif_datetime(
    value: str = "2020:05:06 07:08:09",
    offset: str = "+08:00",
) -> bytes:
    import struct

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
    # IFD0: one ExifIFDPointer entry.
    tiff.extend(struct.pack("<H", 1))
    tiff.extend(struct.pack("<HHII", 0x8769, 4, 1, exif_ifd_offset))
    tiff.extend(struct.pack("<I", 0))
    # EXIF IFD: DateTimeOriginal + OffsetTimeOriginal.
    tiff.extend(struct.pack("<H", 2))
    tiff.extend(struct.pack("<HHII", 0x9003, 2, len(datetime_bytes), datetime_offset))
    tiff.extend(struct.pack("<HHII", 0x9011, 2, len(offset_bytes), offset_time_offset))
    tiff.extend(struct.pack("<I", 0))
    tiff.extend(datetime_bytes)
    tiff.extend(offset_bytes)

    exif_segment = b"Exif\x00\x00" + bytes(tiff)
    app1 = b"\xff\xe1" + struct.pack(">H", len(exif_segment) + 2) + exif_segment
    return b"\xff\xd8" + app1 + b"\xff\xd9"


def test_image_attachment_extracts_exif_capture_date(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)
    memory = create_memory(client, headers)
    photo = jpeg_with_exif_datetime()

    attachment = upload_attachment(
        client,
        headers,
        memory["id"],
        filename="camera.jpg",
        content=photo,
        media_type="image/jpeg",
    )
    assert attachment["captured_date"] == "2020-05-06"
    assert attachment["captured_at"] == "2020-05-06T07:08:09+08:00"
    assert attachment["capture_source"] == "DateTimeOriginal"
    assert attachment["timeline_date"] == "2020-05-06"
    assert attachment["timeline_at"] == "2020-05-06T07:08:09+08:00"
    assert attachment["timeline_time_source"] == "exif:DateTimeOriginal"
    assert attachment["exif_checked"] is True
    assert attachment["time_metadata_checked"] is True

    listed = client.get(
        f"/api/v1/content/memory/{memory['id']}/attachments", headers=headers
    )
    assert listed.status_code == 200
    assert listed.json()["data"][0]["captured_date"] == "2020-05-06"

    # v0.0.10.1 deliberately mirrors only normalized timeline facts into
    # queryable SQLite columns. Raw EXIF strings and human-readable attachment
    # metadata remain encrypted, while timeline_at can now drive indexed range
    # queries without decrypting every attachment.
    database_bytes = (data_dir / "lifegraph.db").read_bytes()
    assert b"2020:05:06 07:08:09" not in database_bytes
    assert b"camera.jpg" not in database_bytes
    with client.app.state.vault.database.connect() as connection:
        row = connection.execute(
            """
            SELECT timeline_at, time_precision, time_source, time_confidence, timezone_offset
            FROM attachments WHERE id=?
            """,
            (attachment["id"],),
        ).fetchone()
    assert tuple(row) == (
        "2020-05-06T07:08:09+08:00",
        "second",
        "exif:DateTimeOriginal",
        "high",
        "+08:00",
    )


def test_existing_attachment_lazily_backfills_exif_metadata(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)
    memory = create_memory(client, headers)
    photo = jpeg_with_exif_datetime("2018:03:04 05:06:07", "+09:00")
    attachment = upload_attachment(
        client,
        headers,
        memory["id"],
        filename="old-photo.jpg",
        content=photo,
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
    legacy_metadata = {
        "filename": stored["filename"],
        "media_type": stored["media_type"],
        "size_bytes": stored["size_bytes"],
        "sha256": stored["sha256"],
    }
    vault.database.update_attachment_metadata(
        master_key,
        profile_id=profile["id"],
        attachment_id=attachment["id"],
        metadata=legacy_metadata,
        timestamp=stored["updated_at"],
    )

    listed = client.get(
        f"/api/v1/content/memory/{memory['id']}/attachments", headers=headers
    )
    assert listed.status_code == 200
    item = listed.json()["data"][0]
    assert item["captured_date"] == "2018-03-04"
    assert item["captured_at"] == "2018-03-04T05:06:07+09:00"
    assert item["exif_checked"] is True


def test_attachment_timeline_date_is_independent_from_parent_content_date(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    memory = create_memory(client, headers)
    photo = jpeg_with_exif_datetime("2020:05:06 07:08:09", "+08:00")
    attachment = upload_attachment(
        client,
        headers,
        memory["id"],
        filename="timeline-photo.jpg",
        content=photo,
        media_type="image/jpeg",
    )

    original_detail = client.get("/api/v1/dates/2026-08-08", headers=headers)
    assert original_detail.status_code == 200
    original_memory = next(item for item in original_detail.json()["data"]["memories"] if item["id"] == memory["id"])
    assert original_memory["attachment_count"] == 1

    timeline_detail = client.get("/api/v1/dates/2020-05-06", headers=headers)
    assert timeline_detail.status_code == 200
    data = timeline_detail.json()["data"]
    assert all(item["id"] != memory["id"] for item in data["memories"])
    material = next(item for item in data["materials"] if item["id"] == attachment["id"])
    assert material["timeline_date"] == "2020-05-06"
    assert material["source_content"] == {
        "kind": "memory",
        "id": memory["id"],
        "title": "有附件的记忆",
        "time_scope": "day",
        "period_key": "2026-08-08",
    }
    assert data["content_state"]["has_material"] is True

    statuses = client.get(
        "/api/v1/dates/content-status?start=2020-05-01&end=2020-05-31",
        headers=headers,
    )
    assert statuses.status_code == 200
    status_data = statuses.json()["data"]
    assert status_data["dates"]["2020-05-06"]["has_material"] is True
    assert status_data["months"]["2020-05"]["has_material"] is True
    assert status_data["years"]["2020"]["has_material"] is True


def office_document_with_core_dates(
    *,
    created: str = "2023-12-28T09:30:00+08:00",
    modified: str = "2024-01-02T18:20:00+08:00",
) -> bytes:
    payload = io.BytesIO()
    core = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
 <dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created>
 <dcterms:modified xsi:type="dcterms:W3CDTF">{modified}</dcterms:modified>
</cp:coreProperties>'''.encode("utf-8")
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("docProps/core.xml", core)
        archive.writestr("word/document.xml", b"<document/>")
    return payload.getvalue()


def test_document_internal_created_time_becomes_independent_timeline_date(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    memory = create_memory(client, headers)
    attachment = upload_attachment(
        client,
        headers,
        memory["id"],
        filename="年度总结.docx",
        content=office_document_with_core_dates(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert attachment["document_created_at"] == "2023-12-28T09:30:00+08:00"
    assert attachment["document_modified_at"] == "2024-01-02T18:20:00+08:00"
    assert attachment["timeline_date"] == "2023-12-28"
    assert attachment["timeline_time_source"] == "document:created"

    detail = client.get("/api/v1/dates/2023-12-28", headers=headers)
    assert detail.status_code == 200
    material = next(item for item in detail.json()["data"]["materials"] if item["id"] == attachment["id"])
    assert material["source_content"]["period_key"] == "2026-08-08"


def test_plain_file_uses_browser_last_modified_time_as_timeline_fallback(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    memory = create_memory(client, headers)
    last_modified = datetime(2022, 6, 15, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    attachment = upload_attachment(
        client,
        headers,
        memory["id"],
        filename="old-note.txt",
        content=b"old file",
        media_type="text/plain",
        file_last_modified_ms=int(last_modified.timestamp() * 1000),
    )
    assert attachment["timeline_date"] == "2022-06-15"
    assert attachment["timeline_time_source"] == "file:last_modified"
    assert attachment["file_modified_at"].startswith("2022-06-15T12:00:00")

    detail = client.get("/api/v1/dates/2022-06-15", headers=headers)
    assert detail.status_code == 200
    assert any(item["id"] == attachment["id"] for item in detail.json()["data"]["materials"])


def test_soft_deleted_parent_hides_material_from_timeline(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    memory = create_memory(client, headers)
    attachment = upload_attachment(
        client,
        headers,
        memory["id"],
        filename="hidden.jpg",
        content=jpeg_with_exif_datetime("2020:05:06 07:08:09", "+08:00"),
        media_type="image/jpeg",
    )
    before = client.get("/api/v1/dates/2020-05-06", headers=headers).json()["data"]
    assert any(item["id"] == attachment["id"] for item in before["materials"])

    deleted = client.request(
        "DELETE",
        f"/api/v1/memories/{memory['id']}",
        headers=headers,
        json={"revision": memory["revision"]},
    )
    assert deleted.status_code == 200
    after = client.get("/api/v1/dates/2020-05-06", headers=headers).json()["data"]
    assert all(item["id"] != attachment["id"] for item in after["materials"])



def test_material_center_browses_filters_and_keeps_source_relation(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    memory = create_memory(client, headers)

    image_ms = int(datetime(2025, 3, 19, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai")).timestamp() * 1000)
    doc_ms = int(datetime(2024, 12, 28, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai")).timestamp() * 1000)
    image = upload_attachment(
        client,
        headers,
        memory["id"],
        filename="春游照片.jpg",
        content=b"not-real-jpeg-but-valid-attachment",
        media_type="image/jpeg",
        file_last_modified_ms=image_ms,
    )
    document = upload_attachment(
        client,
        headers,
        memory["id"],
        filename="旅行说明.txt",
        content=b"travel notes",
        media_type="text/plain",
        file_last_modified_ms=doc_ms,
    )

    response = client.get("/api/v1/materials/browse", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["total"] == 2
    assert data["counts"]["image"] == 1
    assert data["counts"]["document"] == 1
    by_id = {item["id"]: item for item in data["items"]}
    assert by_id[image["id"]]["category"] == "image"
    assert by_id[image["id"]]["timeline_date"] == "2025-03-19"
    assert by_id[document["id"]]["category"] == "document"
    assert by_id[document["id"]]["timeline_date"] == "2024-12-28"
    assert by_id[image["id"]]["source_content"]["id"] == memory["id"]
    assert by_id[image["id"]]["source_content"]["period_key"] == "2026-08-08"

    images_only = client.get(
        "/api/v1/materials/browse?category=image", headers=headers
    ).json()["data"]
    assert images_only["total"] == 1
    assert images_only["items"][0]["filename"] == "春游照片.jpg"

    searched = client.get(
        "/api/v1/materials/browse?q=%E6%97%85%E8%A1%8C%E8%AF%B4%E6%98%8E",
        headers=headers,
    ).json()["data"]
    assert searched["total"] == 1
    assert searched["items"][0]["id"] == document["id"]

    in_range = client.get(
        "/api/v1/materials/browse?date_from=2025-01-01&date_to=2025-12-31",
        headers=headers,
    ).json()["data"]
    assert [item["id"] for item in in_range["items"]] == [image["id"]]



def test_material_center_paginates_without_losing_total_counts(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    memory = create_memory(client, headers)
    created_ids = []
    for index in range(5):
        item = upload_attachment(
            client,
            headers,
            memory["id"],
            filename=f"page-{index}.txt",
            content=f"payload-{index}".encode(),
            media_type="text/plain",
            file_last_modified_ms=int(datetime(2025, 1, index + 1, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai")).timestamp() * 1000),
        )
        created_ids.append(item["id"])

    first = client.get("/api/v1/materials/browse?limit=2&offset=0", headers=headers)
    assert first.status_code == 200, first.text
    first_data = first.json()["data"]
    assert first_data["total"] == 5
    assert first_data["counts"]["document"] == 5
    assert len(first_data["items"]) == 2
    assert first_data["has_more"] is True
    assert first_data["next_offset"] == 2

    second = client.get("/api/v1/materials/browse?limit=2&offset=2", headers=headers)
    assert second.status_code == 200, second.text
    second_data = second.json()["data"]
    assert second_data["total"] == 5
    assert len(second_data["items"]) == 2
    assert second_data["next_offset"] == 4
    assert {item["id"] for item in first_data["items"]}.isdisjoint(
        {item["id"] for item in second_data["items"]}
    )

def test_material_center_rejects_reversed_date_range(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    response = client.get(
        "/api/v1/materials/browse?date_from=2025-12-31&date_to=2025-01-01",
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_MATERIAL_RANGE"


def test_attachment_without_file_time_falls_back_to_parent_day(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    memory = create_memory(client, headers)
    attachment = upload_attachment(
        client,
        headers,
        memory["id"],
        filename="unknown-time.bin",
        content=b"no embedded timestamp",
        media_type="application/octet-stream",
    )

    assert attachment["timeline_date"] == "2026-08-08"
    assert attachment["timeline_time_source"] == "content:date"

    detail = client.get("/api/v1/dates/2026-08-08", headers=headers)
    assert detail.status_code == 200
    assert any(item["id"] == attachment["id"] for item in detail.json()["data"]["materials"])


def test_attachment_without_exact_parent_day_uses_attachment_added_time(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    month_memory_response = client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "time_scope": "month",
            "period_key": "2026-08",
            "title": "整月资料",
            "content": "没有精确到日",
        },
    )
    assert month_memory_response.status_code == 200
    month_memory = month_memory_response.json()["data"]
    response = client.post(
        f"/api/v1/content/memory/{month_memory['id']}/attachments",
        headers=headers,
        files={"attachment_file": ("unknown-time.bin", b"payload", "application/octet-stream")},
    )
    assert response.status_code == 200, response.text
    attachment = response.json()["data"]

    expected_date = datetime.fromisoformat(attachment["created_at"]).astimezone(
        ZoneInfo("Asia/Shanghai")
    ).date().isoformat()
    assert attachment["timeline_date"] == expected_date
    assert attachment["timeline_time_source"] == "attachment:added"


def test_manual_timeline_fallback_repairs_exceptionally_undated_attachment(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    memory = create_memory(client, headers)
    attachment = upload_attachment(
        client,
        headers,
        memory["id"],
        filename="repair-me.bin",
        content=b"payload",
        media_type="application/octet-stream",
    )

    vault = client.app.state.vault
    master_key = vault.require_master_key()
    profile = vault.get_profile()
    stored = vault.database.get_attachment(
        master_key,
        profile_id=profile["id"],
        attachment_id=attachment["id"],
    )
    metadata = vault._attachment_metadata_payload(stored)
    for key in ("timeline_at", "timeline_date", "timeline_time_source"):
        metadata.pop(key, None)
    metadata["time_metadata_checked"] = True
    vault.database.update_attachment_metadata(
        master_key,
        profile_id=profile["id"],
        attachment_id=attachment["id"],
        metadata=metadata,
        timestamp=stored["updated_at"],
    )

    repaired = client.post(
        f"/api/v1/attachments/{attachment['id']}/timeline-fallback",
        headers=headers,
    )
    assert repaired.status_code == 200, repaired.text
    repaired_attachment = repaired.json()["data"]
    assert repaired_attachment["timeline_date"] == "2026-08-08"
    assert repaired_attachment["timeline_time_source"] == "content:date"
    assert repaired_attachment["timeline_fallback_manual"] is True


def test_independent_material_import_browse_timeline_download_and_delete(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)
    plaintext = b"standalone life material"
    modified_ms = int(datetime(2024, 3, 19, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai")).timestamp() * 1000)

    imported = client.post(
        "/api/v1/materials/import",
        headers=headers,
        files={"material_file": ("standalone.txt", plaintext, "text/plain")},
        data={"file_last_modified_ms": str(modified_ms)},
    )
    assert imported.status_code == 200, imported.text
    material = imported.json()["data"]
    assert material["kind"] is None
    assert material["content_id"] is None
    assert material["is_independent"] is True
    assert material["timeline_date"] == "2024-03-19"
    assert material["material_origin"] == "independent"

    encrypted_path = data_dir / "attachments" / material["id"][:2].lower() / f"{material['id']}.lgatt"
    assert encrypted_path.exists()
    assert plaintext not in encrypted_path.read_bytes()

    browsed = client.get("/api/v1/materials/browse", headers=headers)
    assert browsed.status_code == 200
    item = next(value for value in browsed.json()["data"]["items"] if value["id"] == material["id"])
    assert item["source_content"] is None
    assert item["is_independent"] is True

    dated = client.get("/api/v1/dates/2024-03-19", headers=headers)
    assert dated.status_code == 200
    date_material = next(value for value in dated.json()["data"]["materials"] if value["id"] == material["id"])
    assert date_material["source_content"] is None

    downloaded = client.get(f"/api/v1/attachments/{material['id']}/download", headers=headers)
    assert downloaded.status_code == 200
    assert downloaded.content == plaintext

    deleted = client.delete(f"/api/v1/materials/{material['id']}", headers=headers)
    assert deleted.status_code == 200
    assert not encrypted_path.exists()
    assert client.get(f"/api/v1/attachments/{material['id']}/download", headers=headers).status_code == 404



def test_directory_import_preserves_relative_path_and_rejects_duplicates(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    content = b"same directory material"
    digest = hashlib.sha256(content).hexdigest()

    imported = client.post(
        "/api/v1/materials/import",
        headers=headers,
        files={"material_file": ("photo.txt", content, "text/plain")},
        data={
            "source_relative_path": "Photos/2026/photo.txt",
            "source_directory_name": "Photos",
            "reject_duplicate": "true",
        },
    )
    assert imported.status_code == 200, imported.text
    material = imported.json()["data"]
    assert material["material_origin"] == "directory_import"
    assert material["source_relative_path"] == "Photos/2026/photo.txt"
    assert material["source_directory_name"] == "Photos"
    assert material["sha256"] == digest

    checked = client.post(
        "/api/v1/materials/duplicates",
        headers=headers,
        json={"sha256": [digest]},
    )
    assert checked.status_code == 200, checked.text
    matches = checked.json()["data"]["matches"][digest]
    assert matches[0]["id"] == material["id"]
    assert matches[0]["filename"] == "photo.txt"

    duplicate = client.post(
        "/api/v1/materials/import",
        headers=headers,
        files={"material_file": ("copy.txt", content, "text/plain")},
        data={
            "source_relative_path": "Photos/copy.txt",
            "source_directory_name": "Photos",
            "reject_duplicate": "true",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "MATERIAL_DUPLICATE"


def test_material_duplicate_check_rejects_invalid_hash_payload(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    response = client.post(
        "/api/v1/materials/duplicates",
        headers=headers,
        json={"sha256": ["not-a-hash"]},
    )
    assert response.status_code == 422

def test_linked_attachment_cannot_be_deleted_through_independent_material_api(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    memory = create_memory(client, headers)
    attachment = upload_attachment(client, headers, memory["id"], content=b"linked")

    response = client.delete(f"/api/v1/materials/{attachment['id']}", headers=headers)
    assert response.status_code == 404
    assert client.get(f"/api/v1/attachments/{attachment['id']}/download", headers=headers).status_code == 200


def test_independent_material_is_preserved_in_lifevault_backup_restore(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source = make_client(source_dir)
    headers = initialize(source, pin="654321")
    imported = source.post(
        "/api/v1/materials/import",
        headers=headers,
        files={"material_file": ("archive.bin", b"independent-backup", "application/octet-stream")},
    )
    assert imported.status_code == 200
    material = imported.json()["data"]

    exported = source.get("/api/v1/backup/export", headers=headers)
    assert exported.status_code == 200

    target = make_client(tmp_path / "target")
    target_headers = initialize(target)
    restored = target.post(
        "/api/v1/backup/import",
        headers=target_headers,
        files={"backup_file": ("source.lifevault", exported.content, "application/vnd.lifegraph.lifevault+zip")},
        data={
            "credential_method": "pin",
            "credential_secret": "654321",
            "confirm": "REPLACE_REPOSITORY",
        },
    )
    assert restored.status_code == 200, restored.text
    unlocked = target.post("/api/v1/auth/unlock", json={"method": "pin", "secret": "654321"})
    assert unlocked.status_code == 200
    restored_headers = {"Authorization": f"Bearer {unlocked.json()['data']['token']}"}
    browsed = target.get("/api/v1/materials/browse", headers=restored_headers)
    assert browsed.status_code == 200
    restored_material = next(item for item in browsed.json()["data"]["items"] if item["id"] == material["id"])
    assert restored_material["is_independent"] is True
    assert restored_material["source_content"] is None


def test_content_status_material_presence_uses_structured_timeline_without_decrypting_all_metadata(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    memory = create_memory(client, headers)
    attachment = upload_attachment(
        client,
        headers,
        memory["id"],
        filename="indexed-photo.jpg",
        content=jpeg_with_exif_datetime("2020:05:06 07:08:09", "+08:00"),
        media_type="image/jpeg",
    )
    assert attachment["timeline_date"] == "2020-05-06"

    def fail_full_metadata_decrypt(*args, **kwargs):
        raise AssertionError("content-status must not decrypt every attachment metadata row")

    monkeypatch.setattr(client.app.state.vault.database, "list_all_attachments", fail_full_metadata_decrypt)
    response = client.get(
        "/api/v1/dates/content-status?start=2020-05-01&end=2020-05-31",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["dates"]["2020-05-06"]["has_material"] is True
    assert data["months"]["2020-05"]["has_material"] is True
    assert data["years"]["2020"]["has_material"] is True


def test_attachment_timeline_can_be_manually_corrected_and_moves_material_presence(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    memory = create_memory(client, headers)
    attachment = upload_attachment(
        client,
        headers,
        memory["id"],
        filename="wrong-clock.jpg",
        content=jpeg_with_exif_datetime("2020:05:06 07:08:09", "+08:00"),
        media_type="image/jpeg",
    )

    before = client.get(
        "/api/v1/dates/content-status?start=2020-01-01&end=2024-12-31",
        headers=headers,
    )
    assert before.status_code == 200
    assert before.json()["data"]["dates"]["2020-05-06"]["has_material"] is True

    corrected = client.put(
        f"/api/v1/attachments/{attachment['id']}/timeline",
        headers=headers,
        json={"timeline_date": "2024-07-08", "timeline_time": "09:10:11"},
    )
    assert corrected.status_code == 200, corrected.text
    data = corrected.json()["data"]
    assert data["timeline_date"] == "2024-07-08"
    assert data["timeline_at"].startswith("2024-07-08T09:10:11+08:00")
    assert data["timeline_time_source"] == "manual"
    assert data["time_source"] == "manual"
    assert data["time_precision"] == "second"
    assert data["time_confidence"] == "high"
    assert data["timeline_manual"] is True
    assert data["original_time"]["timeline_at"].startswith("2020-05-06T07:08:09+08:00")

    after = client.get(
        "/api/v1/dates/content-status?start=2020-01-01&end=2024-12-31",
        headers=headers,
    )
    assert after.status_code == 200
    statuses = after.json()["data"]["dates"]
    assert "2020-05-06" not in statuses or statuses["2020-05-06"].get("has_material") is not True
    assert statuses["2024-07-08"]["has_material"] is True


def test_material_time_review_filter_surfaces_low_confidence_fallback_and_clears_after_manual_fix(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    imported = client.post(
        "/api/v1/materials/import",
        headers=headers,
        files={"material_file": ("unknown-time.bin", b"unknown time payload", "application/octet-stream")},
    )
    assert imported.status_code == 200, imported.text
    material = imported.json()["data"]
    assert material["timeline_time_source"] == "attachment:added"
    assert material["time_confidence"] == "low"

    review = client.get(
        "/api/v1/materials/browse?time_status=review&category=other&limit=48&offset=0",
        headers=headers,
    )
    assert review.status_code == 200, review.text
    review_data = review.json()["data"]
    assert any(item["id"] == material["id"] for item in review_data["items"])
    assert review_data["counts"]["review"] >= 1

    corrected = client.put(
        f"/api/v1/attachments/{material['id']}/timeline",
        headers=headers,
        json={"timeline_date": "2025-02-03", "timeline_time": None},
    )
    assert corrected.status_code == 200, corrected.text
    corrected_data = corrected.json()["data"]
    assert corrected_data["time_precision"] == "day"
    assert corrected_data["time_confidence"] == "high"

    review_after = client.get(
        "/api/v1/materials/browse?time_status=review&category=other&limit=48&offset=0",
        headers=headers,
    )
    assert review_after.status_code == 200, review_after.text
    assert all(item["id"] != material["id"] for item in review_after.json()["data"]["items"])


def test_period_drawer_materials_are_index_filtered_and_paged(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    memory = create_memory(client, headers)
    target_time = datetime(2022, 6, 15, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    modified_ms = int(target_time.timestamp() * 1000)

    for index in range(15):
        upload_attachment(
            client,
            headers,
            memory["id"],
            filename=f"paged-{index:02d}.txt",
            content=f"payload-{index}".encode("utf-8"),
            media_type="text/plain",
            file_last_modified_ms=modified_ms + index * 1000,
        )

    def fail_full_library_decrypt(*args, **kwargs):
        raise AssertionError("period drawer must not decrypt the whole attachment library")

    monkeypatch.setattr(client.app.state.vault.database, "list_all_attachments", fail_full_library_decrypt)

    detail = client.get(
        "/api/v1/periods/day/2022-06-15?material_limit=5",
        headers=headers,
    )
    assert detail.status_code == 200, detail.text
    data = detail.json()["data"]
    assert len(data["materials"]) == 5
    assert data["materials_total"] == 15
    assert data["materials_has_more"] is True
    assert data["materials_next_offset"] == 5

    second = client.get(
        "/api/v1/periods/day/2022-06-15/materials?limit=5&offset=5",
        headers=headers,
    )
    assert second.status_code == 200, second.text
    page = second.json()["data"]
    assert len(page["items"]) == 5
    assert page["total"] == 15
    assert page["next_offset"] == 10
    assert page["has_more"] is True
