from app.services.progress import calculate_progress, normalize_timezone_name


def test_normalize_bad_utc_string():
    assert normalize_timezone_name("timezone.utc") == "UTC"


def test_progress_falls_back_for_invalid_timezone():
    profile = {
        "birth_date": "2000-01-01",
        "target_age": 100,
        "timezone": "timezone.utc",
    }
    result = calculate_progress(profile)
    assert result["timezone"] == "UTC"
    assert "life" in result
