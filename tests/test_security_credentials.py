from __future__ import annotations

import json
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
            "display_name": "安全设置测试者",
            "birth_date": "1990-01-01",
            "target_age": 100,
            "timezone": "Asia/Shanghai",
            "pin": "123456",
            "recovery_secret": "original-recovery-credential",
        },
    )
    assert response.status_code == 200
    token = response.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


def test_security_summary_exposes_only_slot_metadata_and_audit(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)

    response = client.get("/api/v1/security/summary", headers=headers)
    assert response.status_code == 200
    summary = response.json()["data"]
    assert summary["format_version"] == 1
    assert summary["key_slots"]["pin"]["configured"] is True
    assert summary["key_slots"]["pin"]["kdf"] == "argon2id"
    assert summary["key_slots"]["recovery"]["configured"] is True
    assert summary["audit_count"] == 1
    assert summary["audit"][0]["action"] == "vault_initialized"
    serialized = json.dumps(summary, ensure_ascii=False)
    assert "123456" not in serialized
    assert "original-recovery-credential" not in serialized
    assert "安全设置测试者" not in serialized


def test_generated_recovery_credential_rewraps_only_recovery_slot(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)
    metadata_before = json.loads((data_dir / "vault.json").read_text(encoding="utf-8"))
    old_backup = client.get("/api/v1/backup/export", headers=headers).content
    database_before = (data_dir / "lifegraph.db").read_bytes()

    changed = client.post(
        "/api/v1/auth/change-recovery",
        headers=headers,
        json={"current_pin": "123456", "generate": True},
    )
    assert changed.status_code == 200
    payload = changed.json()["data"]
    generated = payload["generated_recovery_secret"]
    assert generated.startswith("LG-RECOVERY-")
    assert payload["security"]["audit"][0]["action"] == "recovery_credential_changed"

    metadata_after = json.loads((data_dir / "vault.json").read_text(encoding="utf-8"))
    assert metadata_after["key_slots"]["pin"] == metadata_before["key_slots"]["pin"]
    assert metadata_after["key_slots"]["recovery"] != metadata_before["key_slots"]["recovery"]
    assert (data_dir / "lifegraph.db").read_bytes() == database_before
    raw_metadata = (data_dir / "vault.json").read_text(encoding="utf-8")
    assert "123456" not in raw_metadata
    assert generated not in raw_metadata
    assert "original-recovery-credential" not in raw_metadata
    new_backup = client.get("/api/v1/backup/export", headers=headers).content

    assert client.post("/api/v1/auth/lock").status_code == 200
    old_recovery = client.post(
        "/api/v1/auth/unlock",
        json={"method": "recovery", "secret": "original-recovery-credential"},
    )
    assert old_recovery.status_code == 401
    new_recovery = client.post(
        "/api/v1/auth/unlock",
        json={"method": "recovery", "secret": generated},
    )
    assert new_recovery.status_code == 200
    new_headers = {
        "Authorization": f"Bearer {new_recovery.json()['data']['token']}"
    }

    def rehearse(content: bytes, secret: str):
        return client.post(
            "/api/v1/backup/import/check",
            headers=new_headers,
            files={
                "backup_file": (
                    "credential-history.lifevault",
                    content,
                    "application/vnd.lifegraph.lifevault+zip",
                )
            },
            data={
                "credential_method": "recovery",
                "credential_secret": secret,
            },
        )

    assert rehearse(old_backup, "original-recovery-credential").status_code == 200
    assert rehearse(old_backup, generated).status_code == 401
    assert rehearse(new_backup, generated).status_code == 200

    assert client.post("/api/v1/auth/lock").status_code == 200
    pin_unlock = client.post(
        "/api/v1/auth/unlock", json={"method": "pin", "secret": "123456"}
    )
    assert pin_unlock.status_code == 200


def test_custom_recovery_credential_and_validation(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)

    wrong_pin = client.post(
        "/api/v1/auth/change-recovery",
        headers=headers,
        json={
            "current_pin": "654321",
            "generate": False,
            "new_recovery_secret": "new-custom-recovery-secret",
            "confirm_new_recovery_secret": "new-custom-recovery-secret",
        },
    )
    assert wrong_pin.status_code == 401
    assert wrong_pin.json()["error"]["code"] == "INVALID_CURRENT_PIN"

    mismatch = client.post(
        "/api/v1/auth/change-recovery",
        headers=headers,
        json={
            "current_pin": "123456",
            "generate": False,
            "new_recovery_secret": "new-custom-recovery-secret",
            "confirm_new_recovery_secret": "different-recovery-secret",
        },
    )
    assert mismatch.status_code == 422

    changed = client.post(
        "/api/v1/auth/change-recovery",
        headers=headers,
        json={
            "current_pin": "123456",
            "generate": False,
            "new_recovery_secret": "new-custom-recovery-secret",
            "confirm_new_recovery_secret": "new-custom-recovery-secret",
        },
    )
    assert changed.status_code == 200
    assert changed.json()["data"]["generated_recovery_secret"] is None

    assert client.post("/api/v1/auth/lock").status_code == 200
    unlocked = client.post(
        "/api/v1/auth/unlock",
        json={"method": "recovery", "secret": "new-custom-recovery-secret"},
    )
    assert unlocked.status_code == 200


def test_pin_changes_are_recorded_without_secrets(tmp_path: Path) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)

    changed = client.post(
        "/api/v1/auth/change-pin",
        headers=headers,
        json={
            "current_pin": "123456",
            "new_pin": "246810",
            "confirm_new_pin": "246810",
        },
    )
    assert changed.status_code == 200
    unlocked = client.post(
        "/api/v1/auth/unlock", json={"method": "pin", "secret": "246810"}
    )
    assert unlocked.status_code == 200
    summary = client.get(
        "/api/v1/security/summary",
        headers={"Authorization": f"Bearer {unlocked.json()['data']['token']}"},
    ).json()["data"]
    assert summary["audit"][0]["action"] == "pin_changed"
    assert summary["key_slots"]["pin"]["updated_at"] == summary["audit"][0]["at"]
    metadata_text = (data_dir / "vault.json").read_text(encoding="utf-8")
    assert "123456" not in metadata_text
    assert "246810" not in metadata_text


def test_security_endpoints_require_session_and_legacy_metadata_is_supported(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "vault"
    client = make_client(data_dir)
    headers = initialize(client)
    assert client.get("/api/v1/security/summary").status_code == 401
    assert client.post(
        "/api/v1/auth/change-recovery",
        json={"current_pin": "123456", "generate": True},
    ).status_code == 401

    metadata_path = data_dir / "vault.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.pop("security_audit", None)
    metadata.pop("key_slot_updated_at", None)
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    summary = client.get("/api/v1/security/summary", headers=headers)
    assert summary.status_code == 200
    value = summary.json()["data"]
    assert value["audit"][0]["action"] == "vault_initialized"
    assert value["key_slots"]["pin"]["updated_at"] == metadata["security_updated_at"]
