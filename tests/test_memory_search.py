from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(Settings(data_dir=tmp_path / "vault", session_ttl_seconds=60)))


def initialize(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/initialize",
        json={
            "display_name": "搜索测试",
            "birth_date": "1990-01-01",
            "target_age": 100,
            "timezone": "Asia/Shanghai",
            "pin": "123456",
            "recovery_secret": "a-long-recovery-secret",
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


def create_memory(client: TestClient, headers: dict[str, str], **overrides) -> dict:
    payload = {
        "memory_date": "2026-08-08",
        "title": "东京旅行",
        "content": "第一次在夏天去看海。",
    }
    payload.update(overrides)
    response = client.post("/api/v1/memories", headers=headers, json=payload)
    assert response.status_code == 200
    return response.json()["data"]


def test_search_memories_by_keyword_date_and_tags(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    headers = initialize(client)

    travel = client.post("/api/v1/tags", headers=headers, json={"name": "旅行"}).json()["data"]
    family = client.post("/api/v1/tags", headers=headers, json={"name": "家庭"}).json()["data"]

    tokyo = create_memory(client, headers)
    family_memory = create_memory(
        client, headers, memory_date="2025-05-01", title="家庭聚会", content="大家一起吃饭。"
    )
    client.post(f"/api/v1/memories/{tokyo['id']}/tags/{travel['id']}", headers=headers)
    client.post(f"/api/v1/memories/{tokyo['id']}/tags/{family['id']}", headers=headers)
    client.post(f"/api/v1/memories/{family_memory['id']}/tags/{family['id']}", headers=headers)

    rich = create_memory(
        client,
        headers,
        memory_date="2026-06-01",
        title="富文本记忆",
        content="<p>看到了 <strong>夏日晚霞</strong> &amp; 海风。</p>",
        content_format="html",
    )

    by_keyword = client.get("/api/v1/memories/search?q=第一次", headers=headers)
    assert by_keyword.status_code == 200
    data = by_keyword.json()["data"]
    assert data["count"] == 1
    assert data["items"][0]["id"] == tokyo["id"]
    assert {tag["name"] for tag in data["items"][0]["tags"]} == {"旅行", "家庭"}

    by_html_text = client.get("/api/v1/memories/search", headers=headers, params={"q": "晚霞 & 海风"})
    assert by_html_text.status_code == 200
    assert [item["id"] for item in by_html_text.json()["data"]["items"]] == [rich["id"]]

    by_date = client.get(
        "/api/v1/memories/search?date_from=2026-01-01&date_to=2026-12-31", headers=headers
    )
    assert [item["id"] for item in by_date.json()["data"]["items"]] == [tokyo["id"], rich["id"]]

    by_all_tags = client.get(
        f"/api/v1/memories/search?tag_id={travel['id']}&tag_id={family['id']}", headers=headers
    )
    assert [item["id"] for item in by_all_tags.json()["data"]["items"]] == [tokyo["id"]]


def test_search_memories_supports_period_scope_and_rejects_bad_range(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    headers = initialize(client)

    response = client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "time_scope": "month",
            "period_key": "2026-07",
            "title": "七月总结",
            "content": "这个月完成了很多整理。",
        },
    )
    assert response.status_code == 200

    result = client.get("/api/v1/memories/search?q=整理", headers=headers)
    assert result.status_code == 200
    item = result.json()["data"]["items"][0]
    assert item["time_scope"] == "month"
    assert item["period_key"] == "2026-07"

    bad = client.get(
        "/api/v1/memories/search?date_from=2026-08-09&date_to=2026-08-08", headers=headers
    )
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "INVALID_SEARCH_RANGE"


def test_search_memories_requires_unlock(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    headers = initialize(client)
    assert client.post("/api/v1/auth/lock").status_code == 200
    assert client.get("/api/v1/memories/search?q=test", headers=headers).status_code == 401
