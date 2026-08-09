from __future__ import annotations

import hashlib
import io
import json
import math
import shutil
import time
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.audio_compat import AudioProbe, BrowserAudioTarget, FFmpegTools


MIB = 1024 * 1024


def make_client(data_dir: Path) -> TestClient:
    return TestClient(create_app(Settings(data_dir=data_dir, session_ttl_seconds=60)))


def initialize(client: TestClient, *, pin: str = "123456") -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/initialize",
        json={
            "display_name": "大型资料测试",
            "birth_date": "1990-01-01",
            "target_age": 100,
            "timezone": "Asia/Shanghai",
            "pin": pin,
            "recovery_secret": "large-media-recovery-secret",
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


def create_upload(
    client: TestClient,
    headers: dict[str, str],
    *,
    filename: str,
    size_bytes: int,
    media_type: str = "video/mp4",
    chunk_size: int = MIB,
    reject_duplicate: bool = False,
    quick_fingerprint: str | None = None,
) -> dict:
    response = client.post(
        "/api/v1/materials/large/uploads",
        headers=headers,
        json={
            "filename": filename,
            "media_type": media_type,
            "size_bytes": size_bytes,
            "chunk_size": chunk_size,
            "file_last_modified_ms": 1786248000000,
            "source_relative_path": f"videos/{filename}",
            "source_directory_name": "videos",
            "quick_fingerprint": quick_fingerprint,
            "reject_duplicate": reject_duplicate,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def upload_chunk(
    client: TestClient,
    headers: dict[str, str],
    session_id: str,
    index: int,
    content: bytes,
) -> dict:
    response = client.put(
        f"/api/v1/materials/large/uploads/{session_id}/chunks/{index}",
        headers={**headers, "Content-Type": "application/octet-stream"},
        content=content,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_large_material_resumable_upload_finalize_browse_backup_and_delete(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)

    payload = (b"LifeGraph-large-media-" * 140_000)[: 2 * MIB + 333_333]
    upload = create_upload(
        client,
        headers,
        filename="family-video.mp4",
        size_bytes=len(payload),
    )
    assert upload["chunk_size"] == MIB
    assert upload["chunk_count"] == math.ceil(len(payload) / MIB)
    assert upload["completed_ranges"] == []

    chunks = [
        payload[offset : offset + MIB]
        for offset in range(0, len(payload), MIB)
    ]

    second = upload_chunk(client, headers, upload["session_id"], 1, chunks[1])
    assert second["already_present"] is False

    status = client.get(
        f"/api/v1/materials/large/uploads/{upload['session_id']}",
        headers=headers,
    )
    assert status.status_code == 200
    status_data = status.json()["data"]
    assert status_data["completed_chunks"] == 1
    assert status_data["completed_ranges"] == [[1, 1]]
    assert status_data["complete"] is False

    first = upload_chunk(client, headers, upload["session_id"], 0, chunks[0])
    assert first["already_present"] is False
    repeated = upload_chunk(client, headers, upload["session_id"], 0, chunks[0])
    assert repeated["already_present"] is True

    incomplete = client.post(
        f"/api/v1/materials/large/uploads/{upload['session_id']}/finalize",
        headers=headers,
    )
    assert incomplete.status_code == 400

    for index in range(2, len(chunks)):
        upload_chunk(client, headers, upload["session_id"], index, chunks[index])

    finalized = client.post(
        f"/api/v1/materials/large/uploads/{upload['session_id']}/finalize",
        headers=headers,
    )
    assert finalized.status_code == 200, finalized.text
    material = finalized.json()["data"]
    assert material["filename"] == "family-video.mp4"
    assert material["storage_kind"] == "chunked-v1"
    assert material["is_large"] is True
    assert material["size_bytes"] == len(payload)
    assert material["sha256"] == hashlib.sha256(payload).hexdigest()
    assert material["timeline_date"] == "2026-08-09"
    assert material["timeline_time_source"] == "file:last_modified"
    assert material["category"] if "category" in material else True

    media_dir = data_dir / "media" / material["media_id"][:2].lower() / material["media_id"]
    assert media_dir.is_dir()
    encrypted_chunks = sorted((media_dir / "chunks").glob("*.lgchunk"))
    assert len(encrypted_chunks) == len(chunks)
    assert payload[:128] not in encrypted_chunks[0].read_bytes()

    browse = client.get(
        "/api/v1/materials/browse",
        headers=headers,
        params=[("category", "video")],
    )
    assert browse.status_code == 200, browse.text
    items = browse.json()["data"]["items"]
    listed = next(item for item in items if item["id"] == material["id"])
    assert listed["storage_kind"] == "chunked-v1"
    assert listed["is_large"] is True
    assert listed["media_state"] == "online"
    assert listed["media_available"] is True
    assert listed["category"] == "video"
    assert browse.json()["data"]["counts"]["video"] == 1

    integrity = client.get("/api/v1/backup/check", headers=headers)
    assert integrity.status_code == 200, integrity.text
    assert integrity.json()["data"]["external_media_records"] == 1
    assert integrity.json()["data"]["external_media_online"] == 1
    assert integrity.json()["data"]["full_backup_ready"] is True
    assert integrity.json()["data"]["attachment_files_verified"] == 0

    media_status = client.get("/api/v1/backup/media/status", headers=headers)
    assert media_status.status_code == 200, media_status.text
    assert media_status.json()["data"]["original_records"] == 1
    assert media_status.json()["data"]["original_chunks"] == len(chunks)
    assert media_status.json()["data"]["online"] == 1
    assert media_status.json()["data"]["full_backup_ready"] is True
    assert media_status.json()["data"]["external_backup"]["configured"] is False

    exported = client.get("/api/v1/backup/export", headers=headers)
    assert exported.status_code == 200, exported.text
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))
        assert not any(name.startswith("repository/media/") for name in names)
        assert not any(name.endswith(".lgchunk") for name in names)
        assert "repository/media-inventory.lgindex" in names
        assert manifest["format_version"] == 3
        assert manifest["repository"]["backup_scope"] == "core"
        assert manifest["repository"]["external_media_policy"] == "chunked-v1-encrypted-inventory+external-mirror"
        assert manifest["repository"]["full_backup_requires"] == ["core-lifevault", "data/media"]
        assert manifest["integrity"]["external_media_records"] == 1
        assert manifest["integrity"]["external_media_online_at_backup"] == 1

    target_dir = tmp_path / "restored"
    target = make_client(target_dir)
    target_headers = initialize(target)
    checked = target.post(
        "/api/v1/backup/import/check",
        headers=target_headers,
        files={
            "backup_file": (
                "large-index.lifevault",
                exported.content,
                "application/vnd.lifegraph.lifevault+zip",
            )
        },
        data={"credential_method": "pin", "credential_secret": "123456"},
    )
    assert checked.status_code == 200, checked.text
    assert checked.json()["data"]["external_media_records"] == 1
    assert checked.json()["data"]["attachment_files_verified"] == 0
    assert checked.json()["data"]["backup_scope"] == "core"

    restored = target.post(
        "/api/v1/backup/import",
        headers=target_headers,
        files={
            "backup_file": (
                "large-index.lifevault",
                exported.content,
                "application/vnd.lifegraph.lifevault+zip",
            )
        },
        data={
            "credential_method": "pin",
            "credential_secret": "123456",
            "confirm": "REPLACE_REPOSITORY",
        },
    )
    assert restored.status_code == 200, restored.text
    unlocked = target.post("/api/v1/auth/unlock", json={"method": "pin", "secret": "123456"})
    assert unlocked.status_code == 200, unlocked.text
    restored_headers = {"Authorization": f"Bearer {unlocked.json()['data']['token']}"}

    restored_browse = target.get(
        "/api/v1/materials/browse", headers=restored_headers, params=[("category", "video")]
    )
    assert restored_browse.status_code == 200, restored_browse.text
    restored_item = next(
        item for item in restored_browse.json()["data"]["items"] if item["id"] == material["id"]
    )
    assert restored_item["media_state"] == "offline"
    assert restored_item["media_available"] is False
    restored_media_status = target.get("/api/v1/backup/media/status", headers=restored_headers)
    assert restored_media_status.json()["data"]["offline"] == 1
    assert restored_media_status.json()["data"]["full_backup_ready"] is False

    restored_media_dir = target_dir / "media" / material["media_id"][:2].lower() / material["media_id"]
    restored_media_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(media_dir, restored_media_dir)

    reattached = target.get(
        "/api/v1/materials/browse", headers=restored_headers, params=[("category", "video")]
    )
    reattached_item = next(
        item for item in reattached.json()["data"]["items"] if item["id"] == material["id"]
    )
    assert reattached_item["media_state"] == "online"
    assert reattached_item["media_available"] is True

    deleted = client.delete(f"/api/v1/materials/{material['id']}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert not media_dir.exists()


def test_large_material_upload_can_be_cancelled(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)

    upload = create_upload(
        client,
        headers,
        filename="cancel-me.bin",
        size_bytes=MIB + 10,
        media_type="application/octet-stream",
    )
    upload_chunk(client, headers, upload["session_id"], 0, b"x" * MIB)

    session_dir = data_dir / "media" / ".incoming" / upload["session_id"]
    assert session_dir.is_dir()

    cancelled = client.delete(
        f"/api/v1/materials/large/uploads/{upload['session_id']}",
        headers=headers,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["cancelled"] is True
    assert not session_dir.exists()

    missing = client.get(
        f"/api/v1/materials/large/uploads/{upload['session_id']}",
        headers=headers,
    )
    assert missing.status_code == 404


def test_large_material_chunk_conflict_is_rejected(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)

    upload = create_upload(
        client,
        headers,
        filename="conflict.bin",
        size_bytes=MIB,
        media_type="application/octet-stream",
    )
    upload_chunk(client, headers, upload["session_id"], 0, b"a" * MIB)

    conflict = client.put(
        f"/api/v1/materials/large/uploads/{upload['session_id']}/chunks/0",
        headers={**headers, "Content-Type": "application/octet-stream"},
        content=b"b" * MIB,
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "LARGE_UPLOAD_CHUNK_CONFLICT"


def test_large_material_duplicate_is_rejected_before_chunks_are_uploaded(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)
    payload = b"q" * MIB
    quick = hashlib.sha256(b"sampled-fingerprint").hexdigest()

    first = create_upload(
        client,
        headers,
        filename="duplicate-video.mp4",
        size_bytes=len(payload),
        reject_duplicate=True,
        quick_fingerprint=quick,
    )
    upload_chunk(client, headers, first["session_id"], 0, payload)
    finalized = client.post(
        f"/api/v1/materials/large/uploads/{first['session_id']}/finalize",
        headers=headers,
    )
    assert finalized.status_code == 200, finalized.text
    assert finalized.json()["data"]["quick_fingerprint"] == quick

    duplicate = client.post(
        "/api/v1/materials/large/uploads",
        headers=headers,
        json={
            "filename": "duplicate-video.mp4",
            "media_type": "video/mp4",
            "size_bytes": len(payload),
            "chunk_size": MIB,
            "file_last_modified_ms": 1786248000000,
            "quick_fingerprint": quick,
            "reject_duplicate": True,
        },
    )
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["error"]["code"] == "MATERIAL_DUPLICATE"


def test_large_material_legacy_duplicate_metadata_is_rejected(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)
    payload = b"l" * MIB

    first = create_upload(
        client, headers, filename="legacy-duplicate.mkv", size_bytes=len(payload)
    )
    upload_chunk(client, headers, first["session_id"], 0, payload)
    finalized = client.post(
        f"/api/v1/materials/large/uploads/{first['session_id']}/finalize",
        headers=headers,
    )
    assert finalized.status_code == 200, finalized.text

    duplicate = client.post(
        "/api/v1/materials/large/uploads",
        headers=headers,
        json={
            "filename": "legacy-duplicate.mkv",
            "media_type": "video/x-matroska",
            "size_bytes": len(payload),
            "chunk_size": MIB,
            "file_last_modified_ms": 1786248000000,
            "reject_duplicate": True,
        },
    )
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["error"]["code"] == "MATERIAL_DUPLICATE"


def test_large_video_metadata_and_preview_are_persisted(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)

    payload = (b"video-metadata-test" * 150_000)[: 2 * MIB + 111]
    upload = create_upload(
        client,
        headers,
        filename="movie.mkv",
        size_bytes=len(payload),
        media_type="video/x-matroska",
    )

    metadata = client.put(
        f"/api/v1/materials/large/uploads/{upload['session_id']}/video-metadata",
        headers=headers,
        json={
            "duration_seconds": 7322.4,
            "video_width": 1920,
            "video_height": 1080,
            "video_codec": "H.265 / HEVC",
            "metadata_source": "browser:matroska-ebml",
            "poster_source": "generated:video-info",
        },
    )
    assert metadata.status_code == 200, metadata.text
    assert metadata.json()["data"]["video_metadata"]["duration_seconds"] == 7322.4

    preview_bytes = b"fake-jpeg-preview" * 100
    preview = client.put(
        f"/api/v1/materials/large/uploads/{upload['session_id']}/preview",
        headers={**headers, "Content-Type": "image/jpeg"},
        content=preview_bytes,
    )
    assert preview.status_code == 200, preview.text

    chunks = [payload[offset : offset + MIB] for offset in range(0, len(payload), MIB)]
    for index, chunk in enumerate(chunks):
        upload_chunk(client, headers, upload["session_id"], index, chunk)

    finalized = client.post(
        f"/api/v1/materials/large/uploads/{upload['session_id']}/finalize",
        headers=headers,
    )
    assert finalized.status_code == 200, finalized.text
    material = finalized.json()["data"]
    assert material["duration_seconds"] == 7322.4
    assert material["video_width"] == 1920
    assert material["video_height"] == 1080
    assert material["video_codec"] == "H.265 / HEVC"
    assert material["video_metadata_source"] == "browser:matroska-ebml"
    assert material["video_poster_source"] == "generated:video-info"
    assert material["has_preview"] is True
    assert "preview_nonce" not in material

    preview_response = client.get(
        f"/api/v1/attachments/{material['id']}/preview",
        headers=headers,
    )
    assert preview_response.status_code == 200, preview_response.text
    assert preview_response.headers["content-type"].startswith("image/jpeg")
    assert preview_response.content == preview_bytes

    preview_path = data_dir / "previews" / material["id"][:2].lower() / f"{material['id']}.lgpreview"
    assert preview_path.is_file()
    assert preview_bytes not in preview_path.read_bytes()

    exported = client.get("/api/v1/backup/export", headers=headers)
    assert exported.status_code == 200, exported.text
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        preview_archive_path = f"repository/previews/{material['id']}.lgpreview"
        assert preview_archive_path in archive.namelist()
        assert archive.read(preview_archive_path) == preview_path.read_bytes()
        assert preview_bytes not in archive.read(preview_archive_path)
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["integrity"]["preview_files_embedded"] == 1

    deleted = client.delete(f"/api/v1/materials/{material['id']}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert not preview_path.exists()


def test_small_video_material_accepts_metadata_and_preview(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)

    content = b"small-video-placeholder"
    preview_bytes = b"small-preview" * 50
    response = client.post(
        "/api/v1/materials/import",
        headers=headers,
        files={
            "material_file": ("clip.mp4", content, "video/mp4"),
            "video_preview": ("video-preview.jpg", preview_bytes, "image/jpeg"),
        },
        data={
            "video_metadata_json": json.dumps(
                {
                    "duration_seconds": 12.6,
                    "video_width": 1280,
                    "video_height": 720,
                    "metadata_source": "browser:html-video",
                    "poster_source": "browser:video-frame",
                }
            ),
        },
    )
    assert response.status_code == 200, response.text
    material = response.json()["data"]
    assert material["has_preview"] is True
    assert material["duration_seconds"] == 12.6
    assert material["video_width"] == 1280
    assert material["video_height"] == 720

    preview_response = client.get(
        f"/api/v1/attachments/{material['id']}/preview",
        headers=headers,
    )
    assert preview_response.status_code == 200
    assert preview_response.content == preview_bytes


def test_large_material_http_range_stream_and_playback_ticket(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)

    payload = bytes((index % 251 for index in range(2 * MIB + 333_333)))
    upload = create_upload(
        client,
        headers,
        filename="range-test.mp4",
        size_bytes=len(payload),
        media_type="video/mp4",
        chunk_size=MIB,
    )
    for index, offset in enumerate(range(0, len(payload), MIB)):
        upload_chunk(
            client,
            headers,
            upload["session_id"],
            index,
            payload[offset : offset + MIB],
        )
    finalized = client.post(
        f"/api/v1/materials/large/uploads/{upload['session_id']}/finalize",
        headers=headers,
    )
    assert finalized.status_code == 200, finalized.text
    material = finalized.json()["data"]

    ticket_response = client.post(
        f"/api/v1/attachments/{material['id']}/playback-ticket",
        headers=headers,
    )
    assert ticket_response.status_code == 200, ticket_response.text
    ticket = ticket_response.json()["data"]["ticket"]
    stream_url = f"/api/v1/attachments/{material['id']}/stream?ticket={ticket}"

    # Cross the encrypted chunk boundary to prove the response is assembled from
    # only the required authenticated chunks.
    start = MIB - 37
    end = MIB + 83
    ranged = client.get(
        stream_url,
        headers={"Range": f"bytes={start}-{end}"},
    )
    assert ranged.status_code == 206, ranged.text
    assert ranged.content == payload[start : end + 1]
    assert ranged.headers["accept-ranges"] == "bytes"
    assert ranged.headers["content-range"] == f"bytes {start}-{end}/{len(payload)}"
    assert ranged.headers["content-length"] == str(end - start + 1)
    assert ranged.headers["content-type"].startswith("video/mp4")
    assert ranged.headers["content-disposition"].startswith("inline;")

    suffix = client.get(stream_url, headers={"Range": "bytes=-91"})
    assert suffix.status_code == 206
    assert suffix.content == payload[-91:]
    assert suffix.headers["content-range"] == f"bytes {len(payload) - 91}-{len(payload) - 1}/{len(payload)}"

    open_ended = client.get(stream_url, headers={"Range": f"bytes={len(payload) - 137}-"})
    assert open_ended.status_code == 206
    assert open_ended.content == payload[-137:]

    head = client.head(stream_url, headers={"Range": "bytes=0-1023"})
    assert head.status_code == 206
    assert head.content == b""
    assert head.headers["content-range"] == f"bytes 0-1023/{len(payload)}"
    assert head.headers["content-length"] == "1024"

    download = client.get(
        stream_url + "&download=true",
        headers={"Range": "bytes=0-31"},
    )
    assert download.status_code == 206
    assert download.content == payload[:32]
    assert download.headers["content-disposition"].startswith("attachment;")

    unsatisfied = client.get(stream_url, headers={"Range": f"bytes={len(payload)}-"})
    assert unsatisfied.status_code == 416
    assert unsatisfied.headers["content-range"] == f"bytes */{len(payload)}"

    multiple = client.get(stream_url, headers={"Range": "bytes=0-3,9-12"})
    assert multiple.status_code == 416

    wrong_ticket = client.get(
        f"/api/v1/attachments/{material['id']}/stream?ticket={'x' * 32}",
        headers={"Range": "bytes=0-10"},
    )
    assert wrong_ticket.status_code == 401

    assert client.post("/api/v1/auth/lock").status_code == 200
    revoked = client.get(stream_url, headers={"Range": "bytes=0-10"})
    assert revoked.status_code == 401


def test_http_range_stream_supports_small_blob_video(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)
    payload = b"small-video-bytes-" * 400

    imported = client.post(
        "/api/v1/materials/import",
        headers=headers,
        files={"material_file": ("clip.mp4", payload, "video/mp4")},
        data={"file_last_modified_ms": "1786248000000"},
    )
    assert imported.status_code == 200, imported.text
    material = imported.json()["data"]
    assert material["is_large"] is False

    ticket_response = client.post(
        f"/api/v1/attachments/{material['id']}/playback-ticket",
        headers=headers,
    )
    assert ticket_response.status_code == 200
    ticket = ticket_response.json()["data"]["ticket"]
    ranged = client.get(
        f"/api/v1/attachments/{material['id']}/stream?ticket={ticket}",
        headers={"Range": "bytes=17-119"},
    )
    assert ranged.status_code == 206
    assert ranged.content == payload[17:120]


def test_dts_audio_compat_job_persists_encrypted_derivative_and_supports_range(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)
    source = b"fake-matroska-with-dts" * 5000

    imported = client.post(
        "/api/v1/materials/import",
        headers=headers,
        files={"material_file": ("movie.mkv", source, "video/x-matroska")},
        data={"file_last_modified_ms": "1786248000000"},
    )
    assert imported.status_code == 200, imported.text
    material = imported.json()["data"]
    vault = client.app.state.vault

    monkeypatch.setattr(
        vault.audio_compat,
        "probe_prefix",
        lambda _content: AudioProbe(codec_id="dts", codec_label="DTS", channels=6, channel_layout="5.1", sample_rate=48000),
    )
    monkeypatch.setattr(
        vault.audio_compat,
        "refresh_tools",
        lambda: FFmpegTools(ffmpeg=Path("C:/ffmpeg/bin/ffmpeg.exe"), ffprobe=Path("C:/ffmpeg/bin/ffprobe.exe")),
    )
    compat_payload = (b"browser-compatible-mp3-frame" * 60000)[: 1024 * 1024 + 12345]
    mp3_target = BrowserAudioTarget(
        codec_id="mp3",
        codec_label="MP3",
        encoder="libmp3lame",
        media_type="audio/mpeg",
        format_name="mp3",
        extension="mp3",
        bitrate="224k",
    )
    monkeypatch.setattr(vault.audio_compat, "preferred_target", lambda: mp3_target)

    def fake_transcode(**kwargs):
        progress = kwargs.get("progress")
        if progress:
            progress(len(source), len(source))
        return vault.audio_compat.store.write_stream(
            kwargs["master_key"],
            kwargs["media_id"],
            iter((compat_payload,)),
            chunk_size=MIB,
            manifest_extra={
                "asset_kind": "audio-compat",
                "audio_codec": "MP3",
                "audio_codec_id": "mp3",
                "media_type": "audio/mpeg",
            },
        )

    monkeypatch.setattr(vault.audio_compat, "transcode_browser_audio", fake_transcode)

    status_response = client.get(
        f"/api/v1/attachments/{material['id']}/audio-compat",
        headers=headers,
    )
    assert status_response.status_code == 200, status_response.text
    detected = status_response.json()["data"]
    assert detected["audio_codec"] == "DTS"
    assert detected["needs_compat"] is True
    assert detected["state"] == "idle"

    started = client.post(
        f"/api/v1/attachments/{material['id']}/audio-compat",
        headers=headers,
    )
    assert started.status_code == 200, started.text
    ready = None
    for _ in range(50):
        response = client.get(
            f"/api/v1/attachments/{material['id']}/audio-compat",
            headers=headers,
        )
        assert response.status_code == 200
        ready = response.json()["data"]
        if ready["state"] == "ready":
            break
        time.sleep(0.01)
    assert ready is not None and ready["state"] == "ready", ready
    assert ready["has_compat_audio"] is True
    assert ready["compat_media_type"] == "audio/mpeg"
    assert ready["compat_codec"] == "MP3"

    ticket = client.post(
        f"/api/v1/attachments/{material['id']}/playback-ticket",
        headers=headers,
    ).json()["data"]["ticket"]
    ranged = client.get(
        f"/api/v1/attachments/{material['id']}/audio-compat/stream?ticket={ticket}",
        headers={"Range": "bytes=17-207"},
    )
    assert ranged.status_code == 206, ranged.text
    assert ranged.content == compat_payload[17:208]
    assert ranged.headers["content-type"].startswith("audio/mpeg")
    assert ranged.headers["x-lifegraph-audio-compat"] == "mp3"

    # The derivative is encrypted at rest and is removed with the source record.
    with vault._mutex:
        key = vault.require_master_key()
        profile = vault.get_profile()
        record = vault.database.get_attachment(key, profile_id=profile["id"], attachment_id=material["id"])
    compat_id = record["audio_compat_media_id"]
    chunk_path = vault.audio_compat.store.chunk_path(compat_id, 0)
    assert chunk_path.is_file()
    assert compat_payload[:128] not in chunk_path.read_bytes()

    exported = client.get("/api/v1/backup/export", headers=headers)
    assert exported.status_code == 200, exported.text
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        names = set(archive.namelist())
        assert not any("audio_compat" in name or "audio-compat" in name for name in names)
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["repository"]["derived_media_policy"] == "regenerable-excluded"
        assert manifest["integrity"]["audio_compat_records"] == 1

    deleted = client.delete(f"/api/v1/materials/{material['id']}", headers=headers)
    assert deleted.status_code == 200
    assert not vault.audio_compat.store.media_dir(compat_id).exists()
