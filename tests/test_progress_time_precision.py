from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.services import progress as progress_module


def test_month_remaining_uses_current_time(monkeypatch):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 8, 5, 23, 0, 0, tzinfo=tz or ZoneInfo("Asia/Shanghai"))

    monkeypatch.setattr(progress_module, "datetime", FixedDateTime)

    result = progress_module.calculate_progress(
        {
            "birth_date": "1973-01-01",
            "target_age": 100,
            "timezone": "Asia/Shanghai",
        }
    )

    assert result["month"]["percent"] == pytest.approx(15.9946, abs=0.01)
    assert result["month"]["remaining_days"] == 26
    assert result["month"]["remaining_text"] == "26 天 1 小时"
