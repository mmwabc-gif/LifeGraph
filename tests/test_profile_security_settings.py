from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(Settings(data_dir=tmp_path / "vault", session_ttl_seconds=60))
    return TestClient(app)


def initialize(client: TestClient) -> tuple[str, dict[str, str]]:
    response = client.post(
        "/api/v1/auth/initialize",
        json={
            "display_name": "旧名字",
            "birth_date": "1990-01-01",
            "target_age": 100,
            "timezone": "Asia/Shanghai",
            "pin": "123456",
            "recovery_secret": "profile-settings-recovery-secret",
        },
    )
    assert response.status_code == 200
    token = response.json()["data"]["token"]
    return token, {"Authorization": f"Bearer {token}"}


def test_profile_name_birth_date_and_impact(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    _token, headers = initialize(client)

    created = client.post(
        "/api/v1/events",
        headers=headers,
        json={
            "time_scope": "day",
            "period_key": "1991-02-03",
            "title": "旧范围事件",
            "content": "出生日期调整后暂时隐藏",
        },
    )
    assert created.status_code == 200

    profile = client.get("/api/v1/profile", headers=headers).json()["data"]
    impact = client.post(
        "/api/v1/profile/change-impact",
        headers=headers,
        json={"birth_date": "2000-01-01"},
    )
    assert impact.status_code == 200
    assert impact.json()["data"]["hidden_content_count"] == 1
    assert impact.json()["data"]["hidden_counts"]["event"] == 1

    wrong_pin = client.put(
        "/api/v1/profile",
        headers=headers,
        json={
            "display_name": "新名字",
            "birth_date": "2000-01-01",
            "current_pin": "654321",
            "revision": profile["revision"],
        },
    )
    assert wrong_pin.status_code == 401
    assert wrong_pin.json()["error"]["code"] == "INVALID_CURRENT_PIN"

    updated = client.put(
        "/api/v1/profile",
        headers=headers,
        json={
            "display_name": "新名字",
            "birth_date": "2000-01-01",
            "current_pin": "123456",
            "revision": profile["revision"],
        },
    )
    assert updated.status_code == 200
    updated_profile = updated.json()["data"]
    assert updated_profile["display_name"] == "新名字"
    assert updated_profile["birth_date"] == "2000-01-01"
    assert updated_profile["revision"] == profile["revision"] + 1
    stale = client.put(
        "/api/v1/profile",
        headers=headers,
        json={
            "display_name": "过期修改",
            "birth_date": "2000-01-01",
            "current_pin": "123456",
            "revision": profile["revision"],
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "REVISION_CONFLICT"
    for candidate in (
        tmp_path / "vault" / "lifegraph.db",
        tmp_path / "vault" / "lifegraph.db-wal",
        tmp_path / "vault" / "lifegraph.db-shm",
    ):
        if candidate.exists():
            raw = candidate.read_bytes()
            assert "新名字".encode("utf-8") not in raw
            assert b"2000-01-01" not in raw

    progress = client.get("/api/v1/progress/life", headers=headers).json()["data"]
    assert progress["birth_date"] == "2000-01-01"

    # 改回原出生日期后，原公历日期内容仍然存在。
    restored_profile = client.put(
        "/api/v1/profile",
        headers=headers,
        json={
            "display_name": "新名字",
            "birth_date": "1990-01-01",
            "current_pin": "123456",
            "revision": updated_profile["revision"],
        },
    )
    assert restored_profile.status_code == 200
    detail = client.get("/api/v1/dates/1991-02-03", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["events"][0]["title"] == "旧范围事件"


def test_change_pin_rewraps_master_key_and_forces_reunlock(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    token, headers = initialize(client)
    vault_dir = tmp_path / "vault"
    with sqlite3.connect(vault_dir / "lifegraph.db") as connection:
        profile_crypto_before = connection.execute(
            "SELECT nonce, ciphertext FROM profiles LIMIT 1"
        ).fetchone()
    import json
    metadata_before = json.loads((vault_dir / "vault.json").read_text(encoding="utf-8"))

    response = client.post(
        "/api/v1/auth/change-pin",
        headers=headers,
        json={
            "current_pin": "123456",
            "new_pin": "246810",
            "confirm_new_pin": "246810",
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["locked"] is True
    assert client.get("/api/v1/profile", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    with sqlite3.connect(vault_dir / "lifegraph.db") as connection:
        profile_crypto_after = connection.execute(
            "SELECT nonce, ciphertext FROM profiles LIMIT 1"
        ).fetchone()
    assert profile_crypto_after == profile_crypto_before
    metadata_after = json.loads((vault_dir / "vault.json").read_text(encoding="utf-8"))
    assert metadata_after["key_slots"]["pin"] != metadata_before["key_slots"]["pin"]
    assert metadata_after["key_slots"]["recovery"] == metadata_before["key_slots"]["recovery"]
    metadata_text = (vault_dir / "vault.json").read_text(encoding="utf-8")
    assert "123456" not in metadata_text
    assert "246810" not in metadata_text

    old_pin = client.post(
        "/api/v1/auth/unlock", json={"method": "pin", "secret": "123456"}
    )
    assert old_pin.status_code == 401
    new_pin = client.post(
        "/api/v1/auth/unlock", json={"method": "pin", "secret": "246810"}
    )
    assert new_pin.status_code == 200


def test_recovery_credential_can_reset_pin(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    _token, headers = initialize(client)
    created = client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "time_scope": "day",
            "period_key": "2001-01-01",
            "title": "重置前记忆",
            "content": "主密钥保持不变",
        },
    )
    assert created.status_code == 200
    assert client.post("/api/v1/auth/lock").status_code == 200

    wrong = client.post(
        "/api/v1/auth/reset-pin",
        json={
            "recovery_secret": "wrong-recovery-secret",
            "new_pin": "112233",
            "confirm_new_pin": "112233",
        },
    )
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "INVALID_RECOVERY_CREDENTIAL"

    reset = client.post(
        "/api/v1/auth/reset-pin",
        json={
            "recovery_secret": "profile-settings-recovery-secret",
            "new_pin": "112233",
            "confirm_new_pin": "112233",
        },
    )
    assert reset.status_code == 200
    assert reset.json()["data"]["reset"] is True

    assert client.post(
        "/api/v1/auth/unlock", json={"method": "pin", "secret": "123456"}
    ).status_code == 401
    unlocked = client.post(
        "/api/v1/auth/unlock", json={"method": "pin", "secret": "112233"}
    )
    assert unlocked.status_code == 200
    new_headers = {"Authorization": f"Bearer {unlocked.json()['data']['token']}"}
    detail = client.get("/api/v1/dates/2001-01-01", headers=new_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["memories"][0]["title"] == "重置前记忆"


def test_period_content_stays_visible_when_new_birth_date_still_intersects_period(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    _token, headers = initialize(client)

    created = client.post(
        "/api/v1/events",
        headers=headers,
        json={
            "time_scope": "year",
            "period_key": "1990",
            "title": "出生年度事件",
            "content": "仍与新人生范围相交",
        },
    )
    assert created.status_code == 200
    profile = client.get("/api/v1/profile", headers=headers).json()["data"]

    impact = client.post(
        "/api/v1/profile/change-impact",
        headers=headers,
        json={"birth_date": "1990-06-01"},
    ).json()["data"]
    assert impact["hidden_content_count"] == 0

    updated = client.put(
        "/api/v1/profile",
        headers=headers,
        json={
            "display_name": "旧名字",
            "birth_date": "1990-06-01",
            "current_pin": "123456",
            "revision": profile["revision"],
        },
    )
    assert updated.status_code == 200
    progress = client.get("/api/v1/progress/life", headers=headers).json()["data"]
    statuses = client.get(
        f"/api/v1/dates/content-status?start={progress['birth_date']}&end={progress['target_date']}",
        headers=headers,
    ).json()["data"]
    assert statuses["years"]["1990"]["has_event"] is True
