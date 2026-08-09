from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_client(data_dir: Path) -> TestClient:
    return TestClient(create_app(Settings(data_dir=data_dir, session_ttl_seconds=60)))


def initialize(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/initialize",
        json={
            "display_name": "时间统计测试用户",
            "birth_date": "1990-01-01",
            "target_age": 100,
            "timezone": "Asia/Shanghai",
            "pin": "123456",
            "recovery_secret": "timeline-stats-test-recovery-secret",
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


def epoch_ms(value: str) -> int:
    parsed = datetime.fromisoformat(value).replace(tzinfo=ZoneInfo("Asia/Shanghai"))
    return int(parsed.timestamp() * 1000)


def import_material(
    client: TestClient,
    headers: dict[str, str],
    *,
    filename: str,
    when: str,
    content: bytes | None = None,
    media_type: str = "text/plain",
) -> dict:
    response = client.post(
        "/api/v1/materials/import",
        headers=headers,
        data={"file_last_modified_ms": str(epoch_ms(when))},
        files={"material_file": (filename, content or filename.encode(), media_type)},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_timeline_stats_build_lazily_then_update_incrementally(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    first = import_material(client, headers, filename="a.txt", when="2020-05-01T08:15:20")
    second = import_material(client, headers, filename="b.txt", when="2020-05-01T09:30:10")
    import_material(client, headers, filename="c.txt", when="2021-06-02T10:00:00")

    vault = client.app.state.vault
    profile = vault.get_profile()
    with vault.database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM attachment_timeline_stats_meta WHERE profile_id=?",
            (profile["id"],),
        ).fetchone()[0] == 0

    years = client.get(
        "/api/v1/materials/timeline/years?start_year=2019&end_year=2022",
        headers=headers,
    )
    assert years.status_code == 200, years.text
    items = years.json()["data"]["items"]
    assert [item["total_count"] for item in items] == [0, 2, 1, 0]

    with vault.database.connect() as connection:
        built_at = connection.execute(
            "SELECT built_at FROM attachment_timeline_stats_meta WHERE profile_id=?",
            (profile["id"],),
        ).fetchone()[0]

    import_material(client, headers, filename="d.txt", when="2020-05-02T11:01:02")
    months = client.get("/api/v1/materials/timeline/months?year=2020", headers=headers)
    assert months.status_code == 200, months.text
    assert months.json()["data"]["items"][4]["total_count"] == 3

    deleted = client.delete(f"/api/v1/materials/{first['id']}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    days = client.get("/api/v1/materials/timeline/days?year=2020&month=5", headers=headers)
    assert days.status_code == 200, days.text
    assert days.json()["data"]["items"][0]["total_count"] == 1
    assert days.json()["data"]["items"][1]["total_count"] == 1

    with vault.database.connect() as connection:
        assert connection.execute(
            "SELECT built_at FROM attachment_timeline_stats_meta WHERE profile_id=?",
            (profile["id"],),
        ).fetchone()[0] == built_at
        year_count = connection.execute(
            """
            SELECT total_count FROM attachment_timeline_stats
            WHERE profile_id=? AND level='year' AND period_key='2020'
            """,
            (profile["id"],),
        ).fetchone()[0]
    assert year_count == 2
    assert second["id"]


def test_timeline_month_day_hour_endpoints_return_zero_filled_axes(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    import_material(client, headers, filename="morning.jpg", when="2026-08-09T08:16:23", media_type="image/jpeg")
    import_material(client, headers, filename="evening.mp4", when="2026-08-09T18:45:01", media_type="video/mp4")

    months = client.get("/api/v1/materials/timeline/months?year=2026", headers=headers).json()["data"]
    assert len(months["items"]) == 12
    assert months["items"][7] == {"period_key": "2026-08", "month": 8, "total_count": 2}

    days = client.get("/api/v1/materials/timeline/days?year=2026&month=8", headers=headers).json()["data"]
    assert len(days["items"]) == 31
    assert days["items"][8] == {"period_key": "2026-08-09", "day": 9, "total_count": 2}

    hours = client.get("/api/v1/materials/timeline/hours?date=2026-08-09", headers=headers).json()["data"]
    assert len(hours["items"]) == 24
    assert hours["items"][8]["total_count"] == 1
    assert hours["items"][18]["total_count"] == 1
    assert hours["items"][12]["total_count"] == 0


def test_day_timeline_decrypts_only_page_metadata_and_never_reads_media(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    import_material(client, headers, filename="first.txt", when="2026-08-09T08:00:01")
    import_material(client, headers, filename="second.txt", when="2026-08-09T08:00:02")
    import_material(client, headers, filename="other-day.txt", when="2026-08-10T08:00:00")

    vault = client.app.state.vault

    def fail_media_read(*args, **kwargs):
        raise AssertionError("day timeline must not read original media")

    monkeypatch.setattr(vault.attachment_store, "read", fail_media_read)

    response = client.get(
        "/api/v1/materials/timeline/day?date=2026-08-09&limit=1&offset=0",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["total"] == 2
    assert data["has_more"] is True
    assert data["next_offset"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["filename"] == "first.txt"
    assert data["items"][0]["timeline_at"].startswith("2026-08-09T08:00:01")
    assert set(data["items"][0]) >= {
        "id", "timeline_at", "filename", "media_type", "size_bytes", "category", "is_large"
    }

    second_page = client.get(
        "/api/v1/materials/timeline/day?date=2026-08-09&limit=1&offset=1",
        headers=headers,
    ).json()["data"]
    assert second_page["items"][0]["filename"] == "second.txt"
    assert second_page["has_more"] is False


def test_timeline_stats_follow_time_correction_after_stats_are_ready(tmp_path: Path) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    material = import_material(client, headers, filename="move-me.txt", when="2020-05-01T08:00:00")
    client.get("/api/v1/materials/timeline/years?start_year=2020&end_year=2021", headers=headers)

    vault = client.app.state.vault
    master_key = vault.require_master_key()
    profile = vault.get_profile()
    current = vault.database.get_attachment(master_key, profile_id=profile["id"], attachment_id=material["id"])
    metadata = vault._attachment_metadata_payload(current)
    metadata.update(
        {
            "timeline_at": "2021-06-02T09:10:11+08:00",
            "timeline_date": "2021-06-02",
            "timeline_time_source": "manual",
            "time_precision": "second",
            "time_confidence": "high",
        }
    )
    vault.database.update_attachment_metadata(
        master_key,
        profile_id=profile["id"],
        attachment_id=material["id"],
        metadata=metadata,
        timestamp=current["updated_at"],
    )

    years = client.get(
        "/api/v1/materials/timeline/years?start_year=2020&end_year=2021",
        headers=headers,
    ).json()["data"]["items"]
    assert years == [
        {"period_key": "2020", "year": 2020, "total_count": 0},
        {"period_key": "2021", "year": 2021, "total_count": 1},
    ]


def test_timeline_minutes_and_neighbor_dates_are_lightweight(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path / "vault")
    headers = initialize(client)
    import_material(client, headers, filename="prev.txt", when="2026-08-08T09:00:00")
    import_material(client, headers, filename="a.txt", when="2026-08-09T15:09:01")
    import_material(client, headers, filename="b.txt", when="2026-08-09T15:09:55")
    import_material(client, headers, filename="c.txt", when="2026-08-09T15:10:00")
    import_material(client, headers, filename="next.txt", when="2026-08-12T12:00:00")

    vault = client.app.state.vault

    def fail_media_read(*args, **kwargs):
        raise AssertionError("timeline summaries must not read original media")

    monkeypatch.setattr(vault.attachment_store, "read", fail_media_read)

    minutes = client.get("/api/v1/materials/timeline/minutes?date=2026-08-09", headers=headers)
    assert minutes.status_code == 200, minutes.text
    assert minutes.json()["data"]["items"] == [
        {"period_key": "2026-08-09T15:09", "time": "15:09", "total_count": 2},
        {"period_key": "2026-08-09T15:10", "time": "15:10", "total_count": 1},
    ]

    day = client.get("/api/v1/materials/timeline/day?date=2026-08-09&limit=2&offset=0", headers=headers)
    assert day.status_code == 200, day.text
    data = day.json()["data"]
    assert data["previous_date"] == "2026-08-08"
    assert data["next_date"] == "2026-08-12"
    assert data["has_more"] is True
    assert len(data["items"]) == 2
