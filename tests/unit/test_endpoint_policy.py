import pytest

from backend.infrastructure.providers.endpoint_policy import (
    CloudflareGatewayPolicy,
    LocalOpenAICompatiblePolicy,
    NativeOpenAIPolicy,
    OpenAICompatiblePolicy,
    classify_endpoint,
    _is_censorship_blocked,
)


def test_cloudflare_endpoint_and_gateway_headers():
    policy = classify_endpoint(
        "https://gateway.ai.cloudflare.com/v1/account/gateway/compat/"
    )

    assert isinstance(policy, CloudflareGatewayPolicy)
    assert policy.provider_kind == "cloudflare_ai_gateway"
    assert policy.normalized_base_url.endswith("/compat")
    assert policy.build_headers("provider-key", "gateway-key", "default") == {
        "Authorization": "Bearer provider-key",
        "cf-aig-authorization": "Bearer gateway-key",
    }


def test_cloudflare_gateway_only_does_not_send_provider_header():
    policy = classify_endpoint(
        "https://gateway.ai.cloudflare.com/v1/account/gateway/compat"
    )
    assert policy.build_headers("provider-key", "gateway-key", "gateway") == {
        "cf-aig-authorization": "Bearer gateway-key"
    }


def test_cloudflare_rejects_openrouter_free_suffix():
    policy = classify_endpoint(
        "https://gateway.ai.cloudflare.com/v1/account/gateway/compat"
    )
    assert not policy.validate_model("deepseek/deepseek-chat:free")


def test_cloudflare_url_must_use_compat_path():
    with pytest.raises(ValueError):
        classify_endpoint("https://gateway.ai.cloudflare.com/v1/account/gateway")


def test_local_endpoint_preserves_port_and_allows_anonymous_access():
    policy = classify_endpoint("http://localhost:20128/v1/")

    assert isinstance(policy, LocalOpenAICompatiblePolicy)
    assert policy.normalized_base_url == "http://localhost:20128/v1"
    assert policy.requires_api_key() is False
    assert policy.build_headers("", "", "default") == {}


def test_is_censorship_blocked_detects_451():
    assert _is_censorship_blocked(451) is True
    assert _is_censorship_blocked(451, {"error": {"type": "censorship_blocked"}}) is True
    assert _is_censorship_blocked(451, {"error": {"type": "content_policy_violation"}}) is True
    assert _is_censorship_blocked(400) is False
    assert _is_censorship_blocked(500) is False


def test_cloudflare_451_is_non_retryable():
    policy = CloudflareGatewayPolicy(provider_kind="cloudflare", normalized_base_url="https://example.com")
    err = policy.classify_error(451, {})
    assert err.http_status == 451
    assert err.retryable is False
    assert err.error_code == "censorship_blocked"


def test_openai_compatible_451_is_non_retryable():
    policy = OpenAICompatiblePolicy(provider_kind="openai_compatible", normalized_base_url="https://example.com")
    err = policy.classify_error(451, {})
    assert err.http_status == 451
    assert err.retryable is False
    assert err.error_code == "censorship_blocked"


def test_native_openai_451_is_non_retryable():
    policy = NativeOpenAIPolicy(provider_kind="native_openai", normalized_base_url="https://api.openai.com/v1")
    err = policy.classify_error(451, {})
    assert err.http_status == 451
    assert err.retryable is False
    assert err.error_code == "censorship_blocked"
