from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(Settings(data_dir=tmp_path / "vault", session_ttl_seconds=60))
    return TestClient(app)


def initialize(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/initialize",
        json={
            "display_name": "富文本记忆测试",
            "birth_date": "1990-01-01",
            "target_age": 100,
            "timezone": "Asia/Shanghai",
            "pin": "123456",
            "recovery_secret": "a-long-recovery-secret",
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


def test_memory_html_content_is_sanitized_and_encrypted(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    headers = initialize(client)
    rich_html = (
        '<p onclick="alert(1)">今天看到<strong>晚霞</strong></p>'
        '<script>alert(1)</script>'
        '<p><a href="javascript:alert(1)" style="color:red">危险链接</a></p>'
        '<p><a href="https://example.com" title="示例">安全链接</a></p>'
        '<blockquote>此刻值得记住</blockquote>'
    )

    created = client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "time_scope": "day",
            "period_key": "2026-08-07",
            "title": "富文本今日小记",
            "content": rich_html,
            "content_format": "html",
        },
    )
    assert created.status_code == 200
    item = created.json()["data"]
    assert item["content_format"] == "html"
    assert "<strong>晚霞</strong>" in item["content"]
    assert "<blockquote>此刻值得记住</blockquote>" in item["content"]
    assert "script" not in item["content"].lower()
    assert "onclick" not in item["content"].lower()
    assert "style" not in item["content"].lower()
    assert "javascript:" not in item["content"].lower()
    assert 'href="https://example.com"' in item["content"]
    assert 'target="_blank"' in item["content"]
    assert 'rel="noopener noreferrer"' in item["content"]

    detail = client.get("/api/v1/dates/2026-08-07", headers=headers)
    assert detail.status_code == 200
    memory = detail.json()["data"]["memories"][0]
    assert memory["content_format"] == "html"
    assert memory["content"] == item["content"]

    stored_bytes = b""
    data_dir = tmp_path / "vault"
    for candidate in (
        data_dir / "lifegraph.db",
        data_dir / "lifegraph.db-wal",
        data_dir / "lifegraph.db-shm",
    ):
        if candidate.exists():
            stored_bytes += candidate.read_bytes()
    assert "富文本今日小记".encode("utf-8") not in stored_bytes
    assert "晚霞".encode("utf-8") not in stored_bytes


def test_legacy_plain_memory_still_defaults_to_plain_format(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    headers = initialize(client)
    created = client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "time_scope": "day",
            "period_key": "2026-08-08",
            "title": "旧格式记忆",
            "content": "这是一段普通文本。",
        },
    )
    assert created.status_code == 200
    item = created.json()["data"]
    assert item["content_format"] == "plain"
    assert item["content"] == "这是一段普通文本。"
