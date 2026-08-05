from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_client(tmp_path: Path) -> tuple[TestClient, Path]:
    data_dir = tmp_path / "vault"
    app = create_app(Settings(data_dir=data_dir, session_ttl_seconds=60))
    return TestClient(app), data_dir


def initialize(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/initialize",
        json={
            "display_name": "内容闭环测试",
            "birth_date": "1990-01-01",
            "target_age": 100,
            "timezone": "Asia/Shanghai",
            "pin": "123456",
            "recovery_secret": "a-long-recovery-secret",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["token"]


def test_event_date_detail_status_and_encryption(tmp_path: Path) -> None:
    client, data_dir = make_client(tmp_path)
    token = initialize(client)
    headers = {"Authorization": f"Bearer {token}"}

    title = "完成 LifeGraph v0.0.2 事件闭环"
    content = "这段正文必须只存在于 AES-GCM 密文中。"
    created = client.post(
        "/api/v1/events",
        headers=headers,
        json={
            "event_date": "2026-08-05",
            "title": title,
            "content": content,
        },
    )
    assert created.status_code == 200
    assert created.json()["data"]["title"] == title

    detail = client.get("/api/v1/dates/2026-08-05", headers=headers)
    assert detail.status_code == 200
    detail_data = detail.json()["data"]
    assert detail_data["content_state"]["has_event"] is True
    assert detail_data["events"][0]["title"] == title
    assert detail_data["events"][0]["content"] == content

    statuses = client.get(
        "/api/v1/dates/content-status?start=2026-01-01&end=2026-12-31",
        headers=headers,
    )
    assert statuses.status_code == 200
    assert statuses.json()["data"]["dates"]["2026-08-05"] == {
        "has_event": True,
        "has_memory": False,
        "has_plan": False,
    }

    stored_bytes = b""
    for candidate in (
        data_dir / "lifegraph.db",
        data_dir / "lifegraph.db-wal",
        data_dir / "lifegraph.db-shm",
    ):
        if candidate.exists():
            stored_bytes += candidate.read_bytes()
    assert title.encode("utf-8") not in stored_bytes
    assert content.encode("utf-8") not in stored_bytes

    assert client.post("/api/v1/auth/lock").status_code == 200
    assert client.get("/api/v1/dates/2026-08-05", headers=headers).status_code == 401


def test_event_date_must_be_inside_life_range(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    token = initialize(client)
    response = client.post(
        "/api/v1/events",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "event_date": "1989-12-31",
            "title": "出生前事件",
            "content": "",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "DATE_OUT_OF_RANGE"


def test_memory_date_detail_status_and_encryption(tmp_path: Path) -> None:
    client, data_dir = make_client(tmp_path)
    token = initialize(client)
    headers = {"Authorization": f"Bearer {token}"}

    title = "第一次真正感到 LifeGraph 成形"
    content = "这段主观记忆也必须只存在于 AES-GCM 密文中。"
    created = client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "memory_date": "2026-08-05",
            "title": title,
            "content": content,
        },
    )
    assert created.status_code == 200
    assert created.json()["data"]["title"] == title

    detail = client.get("/api/v1/dates/2026-08-05", headers=headers)
    assert detail.status_code == 200
    detail_data = detail.json()["data"]
    assert detail_data["content_state"]["has_memory"] is True
    assert detail_data["memories"][0]["title"] == title
    assert detail_data["memories"][0]["content"] == content

    statuses = client.get(
        "/api/v1/dates/content-status?start=2026-01-01&end=2026-12-31",
        headers=headers,
    )
    assert statuses.status_code == 200
    assert statuses.json()["data"]["dates"]["2026-08-05"] == {
        "has_event": False,
        "has_memory": True,
        "has_plan": False,
    }

    stored_bytes = b""
    for candidate in (
        data_dir / "lifegraph.db",
        data_dir / "lifegraph.db-wal",
        data_dir / "lifegraph.db-shm",
    ):
        if candidate.exists():
            stored_bytes += candidate.read_bytes()
    assert title.encode("utf-8") not in stored_bytes
    assert content.encode("utf-8") not in stored_bytes


def test_memory_date_must_be_inside_life_range(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    token = initialize(client)
    response = client.post(
        "/api/v1/memories",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "memory_date": "1989-12-31",
            "title": "出生前记忆",
            "content": "",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "DATE_OUT_OF_RANGE"


def test_event_and_memory_can_share_the_same_date(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    token = initialize(client)
    headers = {"Authorization": f"Bearer {token}"}

    assert client.post(
        "/api/v1/events",
        headers=headers,
        json={
            "event_date": "2026-08-05",
            "title": "正式事件",
            "content": "发生了什么",
        },
    ).status_code == 200
    assert client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "memory_date": "2026-08-05",
            "title": "个人记忆",
            "content": "我如何记得它",
        },
    ).status_code == 200

    detail = client.get("/api/v1/dates/2026-08-05", headers=headers).json()["data"]
    assert detail["content_state"] == {
        "has_event": True,
        "has_memory": True,
        "has_plan": False,
    }
    assert [item["title"] for item in detail["events"]] == ["正式事件"]
    assert [item["title"] for item in detail["memories"]] == ["个人记忆"]


def test_future_plan_date_detail_status_and_encryption(tmp_path: Path) -> None:
    client, data_dir = make_client(tmp_path)
    token = initialize(client)
    headers = {"Authorization": f"Bearer {token}"}

    title = "发布 LifeGraph v0.0.2 正式稳定版"
    content = "这份未来计划的目标和准备事项必须只存在于 AES-GCM 密文中。"
    plan_date = "2080-01-01"
    created = client.post(
        "/api/v1/plans",
        headers=headers,
        json={
            "plan_date": plan_date,
            "title": title,
            "content": content,
        },
    )
    assert created.status_code == 200
    assert created.json()["data"]["title"] == title

    detail = client.get(f"/api/v1/dates/{plan_date}", headers=headers)
    assert detail.status_code == 200
    detail_data = detail.json()["data"]
    assert detail_data["time_state"] == "future"
    assert detail_data["content_state"]["has_plan"] is True
    assert detail_data["plans"][0]["title"] == title
    assert detail_data["plans"][0]["content"] == content

    statuses = client.get(
        "/api/v1/dates/content-status?start=2079-01-01&end=2080-12-31",
        headers=headers,
    )
    assert statuses.status_code == 200
    assert statuses.json()["data"]["dates"][plan_date] == {
        "has_event": False,
        "has_memory": False,
        "has_plan": True,
    }

    stored_bytes = b""
    for candidate in (
        data_dir / "lifegraph.db",
        data_dir / "lifegraph.db-wal",
        data_dir / "lifegraph.db-shm",
    ):
        if candidate.exists():
            stored_bytes += candidate.read_bytes()
    assert title.encode("utf-8") not in stored_bytes
    assert content.encode("utf-8") not in stored_bytes


def test_plan_date_cannot_be_in_the_past(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    token = initialize(client)
    response = client.post(
        "/api/v1/plans",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "plan_date": "2020-01-01",
            "title": "过去日期上的未来计划",
            "content": "不应被保存",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PLAN_DATE_IN_PAST"


def test_event_memory_and_plan_can_share_the_same_future_date(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    token = initialize(client)
    headers = {"Authorization": f"Bearer {token}"}
    content_date = "2080-02-02"

    assert client.post(
        "/api/v1/events",
        headers=headers,
        json={
            "event_date": content_date,
            "title": "预先登记的正式事件",
            "content": "事件内容",
        },
    ).status_code == 200
    assert client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "memory_date": content_date,
            "title": "预先写下的个人记忆",
            "content": "记忆内容",
        },
    ).status_code == 200
    assert client.post(
        "/api/v1/plans",
        headers=headers,
        json={
            "plan_date": content_date,
            "title": "真正的未来计划",
            "content": "计划内容",
        },
    ).status_code == 200

    detail = client.get(f"/api/v1/dates/{content_date}", headers=headers).json()["data"]
    assert detail["content_state"] == {
        "has_event": True,
        "has_memory": True,
        "has_plan": True,
    }
    assert [item["title"] for item in detail["events"]] == ["预先登记的正式事件"]
    assert [item["title"] for item in detail["memories"]] == ["预先写下的个人记忆"]
    assert [item["title"] for item in detail["plans"]] == ["真正的未来计划"]

