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
            "display_name": "时间范围测试",
            "birth_date": "1990-01-01",
            "target_age": 100,
            "timezone": "Asia/Shanghai",
            "pin": "123456",
            "recovery_secret": "a-long-recovery-secret",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["token"]


def test_year_month_and_day_content_are_independent_and_aggregated(tmp_path: Path) -> None:
    client, data_dir = make_client(tmp_path)
    token = initialize(client)
    headers = {"Authorization": f"Bearer {token}"}

    year_title = "2026 年年度事件"
    month_title = "2026 年 8 月记忆"
    day_title = "2026 年 8 月 5 日事件"
    future_plan = "2080 年年度计划"

    assert client.post(
        "/api/v1/events",
        headers=headers,
        json={"time_scope": "year", "period_key": "2026", "title": year_title, "content": "整年内容"},
    ).status_code == 200
    assert client.post(
        "/api/v1/memories",
        headers=headers,
        json={"time_scope": "month", "period_key": "2026-08", "title": month_title, "content": "整月内容"},
    ).status_code == 200
    assert client.post(
        "/api/v1/events",
        headers=headers,
        json={"time_scope": "day", "period_key": "2026-08-05", "title": day_title, "content": "单日内容"},
    ).status_code == 200
    assert client.post(
        "/api/v1/plans",
        headers=headers,
        json={"time_scope": "year", "period_key": "2080", "title": future_plan, "content": "未来整年"},
    ).status_code == 200

    year = client.get("/api/v1/periods/year/2026", headers=headers).json()["data"]
    assert [item["title"] for item in year["events"]] == [year_title]
    assert year["memories"] == []
    assert len(year["children"]) == 12

    month = client.get("/api/v1/periods/month/2026-08", headers=headers).json()["data"]
    assert [item["title"] for item in month["memories"]] == [month_title]
    assert month["events"] == []
    assert len(month["children"]) == 31

    day = client.get("/api/v1/periods/day/2026-08-05", headers=headers).json()["data"]
    assert [item["title"] for item in day["events"]] == [day_title]
    assert day["memories"] == []

    statuses = client.get(
        "/api/v1/dates/content-status?start=1990-01-01&end=2090-01-01",
        headers=headers,
    ).json()["data"]
    assert statuses["dates"]["2026-08-05"]["has_event"] is True
    assert statuses["months"]["2026-08"]["has_event"] is True
    assert statuses["months"]["2026-08"]["has_memory"] is True
    assert statuses["years"]["2026"]["has_event"] is True
    assert statuses["years"]["2026"]["has_memory"] is True
    assert statuses["years"]["2080"]["has_plan"] is True

    stored = b"".join(
        path.read_bytes()
        for path in (data_dir / "lifegraph.db", data_dir / "lifegraph.db-wal", data_dir / "lifegraph.db-shm")
        if path.exists()
    )
    for plaintext in (year_title, month_title, day_title, future_plan, "整年内容", "整月内容"):
        assert plaintext.encode("utf-8") not in stored


def test_plan_cannot_target_a_finished_year_or_month(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    token = initialize(client)
    headers = {"Authorization": f"Bearer {token}"}

    for scope, key in (("year", "2020"), ("month", "2020-08")):
        response = client.post(
            "/api/v1/plans",
            headers=headers,
            json={"time_scope": scope, "period_key": key, "title": "过期计划", "content": ""},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "PLAN_PERIOD_IN_PAST"
