"""Unit cho error taxonomy chuẩn (docs/07 Phase 2.5a-2): rotate / retry_same / fatal."""

from core.errors import MAX_SAME_KEY_ATTEMPTS, classify


def test_429_rotates_key():
    assert classify(status_code=429) == "rotate"


def test_transient_statuses_retry_same_key():
    for s in (408, 500, 502, 503, 504):
        assert classify(status_code=s) == "retry_same"


def test_auth_and_client_errors_are_fatal():
    for s in (400, 401, 403, 404):
        assert classify(status_code=s) == "fatal"


def test_network_blips_retry_same_key():
    assert classify(exc=TimeoutError("x")) == "retry_same"
    assert classify(exc=ConnectionError("x")) == "retry_same"


def test_bad_payload_errors_are_fatal():
    assert classify(exc=ValueError("rỗng")) == "fatal"
    assert classify(exc=RuntimeError("lạ")) == "fatal"


def test_same_key_attempt_budget():
    assert MAX_SAME_KEY_ATTEMPTS == 2
