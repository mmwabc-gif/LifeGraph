from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from typing import Literal

from app.services.date_detail import DateOutOfLifeRange, describe_date
from app.services.progress import add_years, today_for_timezone


TimeScope = Literal["day", "month", "year"]


def _next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def resolve_period(profile: dict, scope: TimeScope, period_key: str) -> dict:
    birth = date.fromisoformat(profile["birth_date"])
    target = add_years(birth, int(profile["target_age"]))

    if scope == "day":
        try:
            selected = date.fromisoformat(period_key)
        except ValueError as exc:
            raise ValueError("时间范围格式无效") from exc
        description = describe_date(profile, selected)
        description.update(
            {
                "scope": "day",
                "scope_label": "日期",
                "period_key": period_key,
                "label": period_key,
                "start_date": period_key,
                "end_date": period_key,
                "anchor_date": period_key,
                "plan_allowed": description["time_state"] != "past",
            }
        )
        return description

    try:
        if scope == "month":
            year_text, month_text = period_key.split("-", 1)
            year = int(year_text)
            month = int(month_text)
            raw_start = date(year, month, 1)
            raw_end = _next_month(raw_start)
            label = f"{year}年{month}月"
            scope_label = "月份"
        elif scope == "year":
            year = int(period_key)
            raw_start = date(year, 1, 1)
            raw_end = date(year + 1, 1, 1)
            label = f"{year}年"
            scope_label = "年份"
        else:
            raise ValueError("不支持的时间层级")
    except (ValueError, TypeError) as exc:
        raise ValueError("时间范围格式无效") from exc

    start = max(raw_start, birth)
    end_exclusive = min(raw_end, target)
    if start >= end_exclusive:
        raise DateOutOfLifeRange("所选时间范围不在当前人生图谱范围内")

    today, timezone_name = today_for_timezone(profile.get("timezone"))
    if end_exclusive <= today:
        time_state = "past"
        time_state_label = "过去"
    elif start > today:
        time_state = "future"
        time_state_label = "未来"
    else:
        time_state = "current"
        time_state_label = "当前"

    return {
        "scope": scope,
        "scope_label": scope_label,
        "period_key": period_key,
        "label": label,
        "start_date": start.isoformat(),
        "end_date": (end_exclusive - timedelta(days=1)).isoformat(),
        "anchor_date": start.isoformat(),
        "time_state": time_state,
        "time_state_label": time_state_label,
        "timezone": timezone_name,
        "plan_allowed": end_exclusive > today,
        "days_in_period": (end_exclusive - start).days,
    }


def child_periods(profile: dict, description: dict) -> list[dict]:
    scope = description["scope"]
    if scope == "year":
        year = int(description["period_key"])
        children = []
        for month in range(1, 13):
            key = f"{year:04d}-{month:02d}"
            try:
                item = resolve_period(profile, "month", key)
            except DateOutOfLifeRange:
                continue
            children.append(
                {
                    "scope": "month",
                    "period_key": key,
                    "label": f"{month}月",
                    "time_state": item["time_state"],
                }
            )
        return children

    if scope == "month":
        year_text, month_text = description["period_key"].split("-", 1)
        year = int(year_text)
        month = int(month_text)
        children = []
        for day_number in range(1, monthrange(year, month)[1] + 1):
            key = f"{year:04d}-{month:02d}-{day_number:02d}"
            try:
                item = resolve_period(profile, "day", key)
            except DateOutOfLifeRange:
                continue
            children.append(
                {
                    "scope": "day",
                    "period_key": key,
                    "label": f"{day_number:02d}",
                    "time_state": item["time_state"],
                }
            )
        return children

    return []
