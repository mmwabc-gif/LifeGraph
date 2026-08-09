from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(
        Settings(data_dir=tmp_path / "vault", session_ttl_seconds=60)
    )
    return TestClient(app)


def test_release_version_is_consistent(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["version"] == "0.0.10"

    status = client.get("/api/v1/system/status")
    assert status.status_code == 200
    assert status.json()["data"]["version"] == "0.0.10"



def test_initialize_lock_and_unlock(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    status = client.get("/api/v1/system/status").json()["data"]
    assert status["initialized"] is False

    response = client.post(
        "/api/v1/auth/initialize",
        json={
            "display_name": "测试人生",
            "birth_date": "1990-01-01",
            "target_age": 100,
            "timezone": "Asia/Shanghai",
            "pin": "123456",
            "recovery_secret": "a-long-recovery-secret",
        },
    )
    assert response.status_code == 200
    token = response.json()["data"]["token"]

    headers = {"Authorization": f"Bearer {token}"}
    profile = client.get("/api/v1/profile", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["data"]["display_name"] == "测试人生"

    assert client.post("/api/v1/auth/lock").status_code == 200
    assert client.get("/api/v1/profile", headers=headers).status_code == 401

    bad = client.post(
        "/api/v1/auth/unlock", json={"method": "pin", "secret": "654321"}
    )
    assert bad.status_code == 401

    good = client.post(
        "/api/v1/auth/unlock", json={"method": "pin", "secret": "123456"}
    )
    assert good.status_code == 200
    new_token = good.json()["data"]["token"]
    progress = client.get(
        "/api/v1/progress/life",
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert progress.status_code == 200
    assert progress.json()["data"]["target_age"] == 100
