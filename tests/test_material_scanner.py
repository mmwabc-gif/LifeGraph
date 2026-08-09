from __future__ import annotations

import os
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_client(data_dir: Path) -> TestClient:
    return TestClient(create_app(Settings(data_dir=data_dir, session_ttl_seconds=60)))


def initialize(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/initialize",
        json={
            "display_name": "自动扫描测试用户",
            "birth_date": "1990-01-01",
            "target_age": 100,
            "timezone": "Asia/Shanghai",
            "pin": "123456",
            "recovery_secret": "material-scanner-test-recovery-secret",
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


def wait_for_scan(client: TestClient, headers: dict[str, str], timeout: float = 8.0) -> dict:
    deadline = time.monotonic() + timeout
    latest = None
    while time.monotonic() < deadline:
        response = client.get("/api/v1/materials/scanner", headers=headers)
        assert response.status_code == 200, response.text
        latest = response.json()["data"]
        if latest.get("state") not in {"waiting", "running", "pausing"}:
            return latest
        time.sleep(0.03)
    raise AssertionError(f"material scan did not finish: {latest}")


def add_source(client: TestClient, headers: dict[str, str], path: Path) -> dict:
    response = client.post(
        "/api/v1/materials/scan-sources",
        headers=headers,
        json={"path": str(path), "include_subdirectories": True},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def start_scan(client: TestClient, headers: dict[str, str], source_id: str | None = None) -> dict:
    response = client.post(
        "/api/v1/materials/scanner/start",
        headers=headers,
        json={"source_id": source_id},
    )
    assert response.status_code == 200, response.text
    return wait_for_scan(client, headers)


def browse_materials(client: TestClient, headers: dict[str, str]) -> list[dict]:
    response = client.get(
        "/api/v1/materials/browse?category=document&category=other&limit=100",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["items"]


def test_scan_source_path_is_encrypted_and_incremental_scan_skips_unchanged_file(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    source_dir = tmp_path / "photos"
    source_dir.mkdir()
    source_file = source_dir / "IMG_20190506_071122.txt"
    source_file.write_text("first payload", encoding="utf-8")

    client = make_client(data_dir)
    headers = initialize(client)
    source = add_source(client, headers, source_dir)
    assert source["available"] is True
    assert source["enabled"] is True

    first = start_scan(client, headers, source["id"])
    assert first["state"] == "completed"
    assert first["imported_files"] == 1
    items = browse_materials(client, headers)
    assert len(items) == 1
    assert items[0]["filename"] == source_file.name
    assert items[0]["timeline_at"].startswith("2019-05-06T07:11:22")
    assert items[0]["time_source"] == "filename:date"

    # Absolute source paths and relative filenames are encrypted metadata; the
    # incremental table stores only a one-way path hash plus stat facts.
    db_bytes = (data_dir / "lifegraph.db").read_bytes()
    assert str(source_dir).encode("utf-8") not in db_bytes
    assert source_file.name.encode("utf-8") not in db_bytes

    second = start_scan(client, headers, source["id"])
    assert second["state"] == "completed"
    assert second["imported_files"] == 0
    assert second["skipped_files"] == 1
    assert len(browse_materials(client, headers)) == 1


def test_scanner_tracks_rename_and_missing_without_deleting_imported_material(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    source_dir = tmp_path / "archive"
    source_dir.mkdir()
    original = source_dir / "2020-01-02_note.txt"
    original.write_text("keep me", encoding="utf-8")

    client = make_client(data_dir)
    headers = initialize(client)
    source = add_source(client, headers, source_dir)
    first = start_scan(client, headers, source["id"])
    assert first["imported_files"] == 1
    attachment_id = browse_materials(client, headers)[0]["id"]

    renamed = source_dir / "2020-01-02_note-renamed.txt"
    original.rename(renamed)
    second = start_scan(client, headers, source["id"])
    assert second["imported_files"] == 0
    assert second["skipped_files"] == 1
    items = browse_materials(client, headers)
    assert len(items) == 1
    assert items[0]["id"] == attachment_id

    renamed.unlink()
    third = start_scan(client, headers, source["id"])
    assert third["missing_files"] == 1
    # LifeGraph is an archive, not a destructive mirror: source deletion keeps
    # the already encrypted material available.
    items = browse_materials(client, headers)
    assert len(items) == 1
    assert items[0]["id"] == attachment_id

    sources = client.get("/api/v1/materials/scan-sources", headers=headers).json()["data"]
    assert sources[0]["file_counts"]["missing"] == 1


def test_scanner_replaces_its_previous_copy_when_source_file_changes(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    source_dir = tmp_path / "docs"
    source_dir.mkdir()
    source_file = source_dir / "2022-03-04_record.txt"
    source_file.write_text("version one", encoding="utf-8")

    client = make_client(data_dir)
    headers = initialize(client)
    source = add_source(client, headers, source_dir)
    start_scan(client, headers, source["id"])
    first_items = browse_materials(client, headers)
    assert len(first_items) == 1
    first_id = first_items[0]["id"]

    source_file.write_text("version two is different", encoding="utf-8")
    # Ensure mtime_ns changes even on coarse filesystems used by CI.
    future_ns = source_file.stat().st_mtime_ns + 2_000_000_000
    os.utime(source_file, ns=(future_ns, future_ns))
    result = start_scan(client, headers, source["id"])
    assert result["imported_files"] == 1

    items = browse_materials(client, headers)
    assert len(items) == 1
    assert items[0]["id"] != first_id
    downloaded = client.get(f"/api/v1/attachments/{items[0]['id']}/download", headers=headers)
    assert downloaded.status_code == 200
    assert downloaded.content == b"version two is different"


def test_scan_source_can_be_disabled_and_removed_without_deleting_material(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "one.txt").write_text("one", encoding="utf-8")

    client = make_client(data_dir)
    headers = initialize(client)
    source = add_source(client, headers, source_dir)
    start_scan(client, headers, source["id"])
    attachment_id = browse_materials(client, headers)[0]["id"]

    disabled = client.put(
        f"/api/v1/materials/scan-sources/{source['id']}",
        headers=headers,
        json={"enabled": False},
    )
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["data"]["enabled"] is False

    removed = client.delete(f"/api/v1/materials/scan-sources/{source['id']}", headers=headers)
    assert removed.status_code == 200, removed.text
    assert removed.json()["data"]["materials_preserved"] is True
    assert client.get("/api/v1/materials/scan-sources", headers=headers).json()["data"] == []
    items = browse_materials(client, headers)
    assert [item["id"] for item in items] == [attachment_id]


def test_scanner_streams_large_source_file_into_existing_chunk_store(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    source_dir = tmp_path / "videos"
    source_dir.mkdir()
    source_file = source_dir / "2021-02-03_large.bin"
    # Just above the ordinary attachment limit: this must take the chunked path.
    with source_file.open("wb") as stream:
        stream.truncate(50 * 1024 * 1024 + 1)

    client = make_client(data_dir)
    headers = initialize(client)
    source = add_source(client, headers, source_dir)
    result = start_scan(client, headers, source["id"])
    assert result["state"] == "completed"
    assert result["imported_files"] == 1

    items = browse_materials(client, headers)
    assert len(items) == 1
    assert items[0]["storage_kind"] == "chunked-v1"
    assert items[0]["is_large"] is True
    media_id = items[0]["media_id"]
    media_dir = data_dir / "media" / media_id[:2].lower() / media_id
    assert (media_dir / "manifest.lgmedia").is_file()
    assert list((media_dir / "chunks").glob("*.lgchunk"))


def test_scan_source_configuration_survives_lifevault_restore(tmp_path: Path) -> None:
    source_data_dir = tmp_path / "source-vault"
    watched_dir = tmp_path / "watched-empty"
    watched_dir.mkdir()

    source_client = make_client(source_data_dir)
    source_headers = initialize(source_client)
    created = add_source(source_client, source_headers, watched_dir)
    assert created["path"] == str(watched_dir.resolve())

    exported = source_client.get("/api/v1/backup/export", headers=source_headers)
    assert exported.status_code == 200, exported.text

    target_client = make_client(tmp_path / "target-vault")
    target_headers = initialize(target_client)
    restored = target_client.post(
        "/api/v1/backup/import",
        headers=target_headers,
        files={
            "backup_file": (
                "scanner-config.lifevault",
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
    assert restored.json()["data"]["restored_schema_version"] == 11

    unlocked = target_client.post(
        "/api/v1/auth/unlock",
        json={"method": "pin", "secret": "123456"},
    )
    assert unlocked.status_code == 200, unlocked.text
    restored_headers = {
        "Authorization": f"Bearer {unlocked.json()['data']['token']}"
    }
    sources = target_client.get(
        "/api/v1/materials/scan-sources", headers=restored_headers
    )
    assert sources.status_code == 200, sources.text
    restored_sources = sources.json()["data"]
    assert len(restored_sources) == 1
    assert restored_sources[0]["path"] == str(watched_dir.resolve())
    assert restored_sources[0]["enabled"] is True
    assert restored_sources[0]["available"] is True
