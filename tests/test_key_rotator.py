import pytest

from core.key_rotator import KeyRotator


def test_empty_keys():
    rotator = KeyRotator([])
    assert not rotator.has_keys()
    with pytest.raises(ValueError):
        rotator.get_current_key()


def test_single_key_stops_on_429():
    rotator = KeyRotator(["KEY_A"])
    rotator.start_chunk_attempt()
    assert rotator.get_current_key() == "KEY_A"
    assert rotator.try_next_key() is None


def test_multiple_keys_rotation():
    rotator = KeyRotator(["KEY_1", "KEY_2", "KEY_3"])
    rotator.start_chunk_attempt()
    assert rotator.get_current_key() == "KEY_1"
    assert rotator.try_next_key() == "KEY_2"
    assert rotator.try_next_key() == "KEY_3"
    assert rotator.try_next_key() is None


def test_reset_chunk_attempt():
    rotator = KeyRotator(["KEY_1", "KEY_2"])
    rotator.start_chunk_attempt()
    rotator.try_next_key()
    rotator.start_chunk_attempt()
    assert rotator.try_next_key() is not None


def test_dedup_and_whitespace():
    rotator = KeyRotator(["  KEY_A ", "KEY_A", "", "KEY_B", "KEY_B  "])
    assert rotator.keys == ["KEY_A", "KEY_B"]


def test_reuse_last_successful_key_next_chunk():
    rotator = KeyRotator(["K1", "K2", "K3"])
    rotator.start_chunk_attempt()
    rotator.try_next_key()
    assert rotator.get_current_key() == "K2"
    rotator.start_chunk_attempt()  # chunk mới: giữ key đang dùng, reset đã-thử
    assert rotator.get_current_key() == "K2"
    assert rotator.try_next_key() == "K3"
