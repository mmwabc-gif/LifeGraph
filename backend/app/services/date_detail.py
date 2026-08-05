from __future__ import annotations

from datetime import date

from app.services.progress import add_years, today_for_timezone


WEEKDAY_NAMES = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")


class DateOutOfLifeRange(ValueError):
    pass


def describe_date(profile: dict, selected_date: date) -> dict:
    birth_date = date.fromisoformat(profile["birth_date"])
    target_date = add_years(birth_date, int(profile["target_age"]))
    if selected_date < birth_date or selected_date >= target_date:
        raise DateOutOfLifeRange("所选日期不在当前人生图谱范围内")

    today, timezone_name = today_for_timezone(profile.get("timezone"))
    if selected_date < today:
        time_state = "past"
        time_state_label = "过去"
    elif selected_date > today:
        time_state = "future"
        time_state_label = "未来"
    else:
        time_state = "today"
        time_state_label = "今天"

    age = selected_date.year - birth_date.year - (
        (selected_date.month, selected_date.day) < (birth_date.month, birth_date.day)
    )
    return {
        "date": selected_date.isoformat(),
        "weekday": WEEKDAY_NAMES[selected_date.weekday()],
        "time_state": time_state,
        "time_state_label": time_state_label,
        "age": max(0, age),
        "life_day_number": (selected_date - birth_date).days + 1,
        "timezone": timezone_name,
    }
