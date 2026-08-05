from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def add_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        # 2 月 29 日在非闰年按 2 月 28 日处理。
        return value.replace(year=value.year + years, month=2, day=28)


def normalize_timezone_name(value: str | None) -> str:
    name = (value or "UTC").strip()
    # 兼容早期 Python 3.10 修复包误写入的字符串。
    if name in {"timezone.utc", "dt_timezone.utc"}:
        return "UTC"
    return name or "UTC"


def now_for_timezone(value: str | None) -> tuple[datetime, str]:
    timezone_name = normalize_timezone_name(value)
    try:
        return datetime.now(ZoneInfo(timezone_name)), timezone_name
    except ZoneInfoNotFoundError:
        # 若系统缺失时区数据库或用户填入了无效时区，回退到 Python 内置 UTC。
        return datetime.now(dt_timezone.utc), "UTC"


def today_for_timezone(value: str | None) -> tuple[date, str]:
    current, timezone_name = now_for_timezone(value)
    return current.date(), timezone_name


def format_remaining(total_seconds: float) -> str:
    seconds = max(0, int(round(total_seconds)))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60

    if days >= 1:
        if hours > 0:
            return f"{days} 天 {hours} 小时"
        return f"{days} 天"
    if hours >= 1:
        if minutes > 0:
            return f"{hours} 小时 {minutes} 分钟"
        return f"{hours} 小时"
    return f"{minutes} 分钟"


def calculate_progress(profile: dict) -> dict:
    birth_date = date.fromisoformat(profile["birth_date"])
    target_age = int(profile["target_age"])
    current_dt, timezone_name = now_for_timezone(profile.get("timezone"))
    today = current_dt.date()

    target_date = add_years(birth_date, target_age)
    total_days = max(1, (target_date - birth_date).days)
    elapsed_days = min(total_days, max(0, (today - birth_date).days))
    remaining_days = max(0, total_days - elapsed_days)

    current_age = today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )
    current_age = max(0, current_age)

    # 年/月进度用当前时刻精确到秒计算，而不是只按日期整数计算。
    # 这样 8 月 5 日晚上不会仍显示“还剩 27 天”。
    year_start_dt = datetime(current_dt.year, 1, 1, tzinfo=current_dt.tzinfo)
    year_end_dt = datetime(current_dt.year + 1, 1, 1, tzinfo=current_dt.tzinfo)
    year_total_seconds = max(1.0, (year_end_dt - year_start_dt).total_seconds())
    year_elapsed_seconds = min(
        year_total_seconds,
        max(0.0, (current_dt - year_start_dt).total_seconds()),
    )
    year_remaining_seconds = max(0.0, year_total_seconds - year_elapsed_seconds)
    year_total_days = int(year_total_seconds // 86400)

    month_start_dt = datetime(current_dt.year, current_dt.month, 1, tzinfo=current_dt.tzinfo)
    if current_dt.month == 12:
        month_end_dt = datetime(current_dt.year + 1, 1, 1, tzinfo=current_dt.tzinfo)
    else:
        month_end_dt = datetime(current_dt.year, current_dt.month + 1, 1, tzinfo=current_dt.tzinfo)
    month_total_seconds = max(1.0, (month_end_dt - month_start_dt).total_seconds())
    month_elapsed_seconds = min(
        month_total_seconds,
        max(0.0, (current_dt - month_start_dt).total_seconds()),
    )
    month_remaining_seconds = max(0.0, month_total_seconds - month_elapsed_seconds)
    month_days = monthrange(current_dt.year, current_dt.month)[1]

    return {
        "today": today.isoformat(),
        "now": current_dt.isoformat(timespec="seconds"),
        "timezone": timezone_name,
        "birth_date": birth_date.isoformat(),
        "target_date": target_date.isoformat(),
        "target_age": target_age,
        "current_age": current_age,
        "life_day_number": elapsed_days + 1 if today >= birth_date else 0,
        "life": {
            "elapsed_days": elapsed_days,
            "remaining_days": remaining_days,
            "total_days": total_days,
            "percent": round(elapsed_days / total_days * 100, 4),
        },
        "year": {
            "year": current_dt.year,
            "elapsed_days": round(year_elapsed_seconds / 86400, 3),
            "remaining_days": int(year_remaining_seconds // 86400),
            "remaining_text": format_remaining(year_remaining_seconds),
            "total_days": year_total_days,
            "percent": round(year_elapsed_seconds / year_total_seconds * 100, 4),
        },
        "month": {
            "year": current_dt.year,
            "month": current_dt.month,
            "elapsed_days": round(month_elapsed_seconds / 86400, 3),
            "remaining_days": int(month_remaining_seconds // 86400),
            "remaining_text": format_remaining(month_remaining_seconds),
            "total_days": month_days,
            "percent": round(month_elapsed_seconds / month_total_seconds * 100, 4),
        },
    }
