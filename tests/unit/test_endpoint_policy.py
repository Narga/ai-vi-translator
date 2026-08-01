import pytest

from backend.infrastructure.providers.endpoint_policy import (
    CloudflareGatewayPolicy,
    classify_endpoint,
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

