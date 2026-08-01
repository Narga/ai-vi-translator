import pytest
import sys
from unittest.mock import patch, MagicMock
from services.openai_client import OpenAIClient
from backend.infrastructure.providers.endpoint_policy import CloudflareGatewayPolicy, NativeOpenAIPolicy

class MockModel:
    def __init__(self, model_id, name=None):
        self.id = model_id
        if name:
            self.name = name

@pytest.fixture
def mock_openai():
    with patch.object(OpenAIClient, "_initialize_client") as mock_init:
        yield mock_init

def test_list_models_cloudflare_filter(mock_openai):
    # Setup mock models
    # Test Cloudflare Gateway Policy
    policy = CloudflareGatewayPolicy(provider_kind="cloudflare_ai_gateway", normalized_base_url="https://gateway.ai.cloudflare.com/v1/a/b/compat")
    client = OpenAIClient(api_key="test", policy=policy)
    client._client = MagicMock()
    
    mock_response = MagicMock()
    mock_response.data = [
        MockModel("@cf/meta/llama-3-8b-instruct"),
        MockModel("workers-ai/@cf/google/gemma-7b-it"),
        MockModel("deepseek/deepseek-chat"),
        MockModel("gpt-4o-mini")
    ]
    client._client.models.list.return_value = mock_response
    
    models = client.list_models()
    # Should contain all models
    assert len(models) == 4
    assert "@cf/meta/llama-3-8b-instruct" in models
    assert "deepseek/deepseek-chat" in models
def test_list_models_native_no_filter(mock_openai):
    # Test Native OpenAI Policy
    policy = NativeOpenAIPolicy(provider_kind="native_openai", normalized_base_url="https://api.openai.com/v1")
    client = OpenAIClient(api_key="test", policy=policy)
    client._client = MagicMock()
    
    mock_response = MagicMock()
    mock_response.data = [
        MockModel("@cf/meta/llama-3-8b-instruct"),
        MockModel("deepseek/deepseek-chat"),
        MockModel("gpt-4o-mini")
    ]
    client._client.models.list.return_value = mock_response
    
    models = client.list_models()
    
    # Should contain all models
    assert len(models) == 3

def test_list_models_full_cloudflare_filter(mock_openai):
    policy = CloudflareGatewayPolicy(provider_kind="cloudflare_ai_gateway", normalized_base_url="https://gateway.ai.cloudflare.com/v1/a/b/compat")
    client = OpenAIClient(api_key="test", policy=policy)
    client._client = MagicMock()
    
    mock_response = MagicMock()
    mock_response.data = [
        MockModel("@cf/meta/llama-3-8b-instruct", name="Llama 3 8B"),
        MockModel("openai/gpt-4o")
    ]
    client._client.models.list.return_value = mock_response
    
    models_full = client.list_models_full()
    
    assert len(models_full) == 2
    
    cf_model = next(m for m in models_full if m["id"] == "@cf/meta/llama-3-8b-instruct")
    assert cf_model["source"] == "cloudflare_workers_ai"
    assert "docs_url" in cf_model
    
    openai_model = next(m for m in models_full if m["id"] == "openai/gpt-4o")
    assert "source" not in openai_model


def test_local_openai_compatible_client_can_initialize_without_api_key():
    fake_openai = MagicMock()
    fake_openai.OpenAI.return_value = MagicMock()

    with patch.dict(sys.modules, {"openai": fake_openai}):
        client = OpenAIClient(api_key="", base_url="http://localhost:20128/v1")

    assert client.policy.requires_api_key() is False
    fake_openai.OpenAI.assert_called_once()
    kwargs = fake_openai.OpenAI.call_args.kwargs
    assert kwargs["base_url"] == "http://localhost:20128/v1"
    assert "default_headers" not in kwargs
