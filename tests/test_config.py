"""normalize_prefs dùng chung cho AppConfig.get_config() và PUT /api/settings."""

from core.config import normalize_prefs


def test_defaults_when_empty():
    assert normalize_prefs({}) == {
        "max_chunk_chars": 16000, "timeout_seconds": 90, "api_delay_seconds": 2.0}


def test_garbage_falls_back_to_default():
    d = normalize_prefs({"max_chunk_chars": -5, "timeout_seconds": "rác", "api_delay_seconds": -1})
    assert d == {"max_chunk_chars": 16000, "timeout_seconds": 90, "api_delay_seconds": 2.0}


def test_valid_values_kept_with_types():
    d = normalize_prefs({"max_chunk_chars": 8000.0, "timeout_seconds": 60, "api_delay_seconds": 0})
    assert d == {"max_chunk_chars": 8000, "timeout_seconds": 60.0, "api_delay_seconds": 0.0}
    assert isinstance(d["max_chunk_chars"], int)


def test_extra_keys_ignored():
    d = normalize_prefs({"max_chunk_chars": 8000, "REQUEST_TIMEOUT_SECONDS": 999})
    assert d["max_chunk_chars"] == 8000 and "REQUEST_TIMEOUT_SECONDS" not in d
