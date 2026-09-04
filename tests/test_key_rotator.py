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
