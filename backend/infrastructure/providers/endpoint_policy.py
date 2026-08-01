import re
import urllib.parse
from dataclasses import dataclass
from typing import Optional, Dict, Any

class ProviderRequestError(Exception):
    def __init__(self, message: str, http_status: Optional[int], error_code: Optional[str], retryable: bool, provider_kind: str, request_id: Optional[str], safe_message: str):
        super().__init__(message)
        self.http_status = http_status
        self.error_code = error_code
        self.retryable = retryable
        self.provider_kind = provider_kind
        self.request_id = request_id
        self.safe_message = safe_message

@dataclass
class EndpointPolicy:
    provider_kind: str
    normalized_base_url: str

    def build_headers(self, provider_api_key: Optional[str], gateway_api_key: Optional[str], credential_mode: str) -> Dict[str, str]:
        raise NotImplementedError()

    def normalize_model(self, model: str) -> str:
        return model

    def validate_model(self, model: str) -> bool:
        return bool(model and model.strip() and not any(c.isspace() for c in model))

    def classify_error(self, status: int, body: Any) -> ProviderRequestError:
        raise NotImplementedError()

    def get_retry_policy(self) -> Dict[str, Any]:
        return {"max_retries": 3, "backoff_factor": 2.0}

    def supports_feature(self, feature: str) -> bool:
        return False

    def requires_api_key(self) -> bool:
        """Whether the endpoint requires credentials before creating a client."""
        return True

class CloudflareGatewayPolicy(EndpointPolicy):
    def build_headers(self, provider_api_key: Optional[str], gateway_api_key: Optional[str], credential_mode: str) -> Dict[str, str]:
        headers = {}
        mode = (credential_mode or "default").lower()
        use_provider = mode in ("default", "provider", "both")
        use_gateway = mode in ("gateway", "both") or (mode == "default" and bool(gateway_api_key))
        if provider_api_key and use_provider:
            headers["Authorization"] = f"Bearer {provider_api_key}"
        if gateway_api_key and use_gateway:
            headers["cf-aig-authorization"] = f"Bearer {gateway_api_key}"
        return headers

    def normalize_model(self, model: str) -> str:
        return model

    def validate_model(self, model: str) -> bool:
        # :free is an OpenRouter routing suffix and is not a Cloudflare model id.
        return super().validate_model(model) and not model.endswith(":free")

    def classify_error(self, status: int, body: Any) -> ProviderRequestError:
        retryable = status in (408, 429) or status >= 500
        safe_message = f"Cloudflare Gateway error {status}"
        return ProviderRequestError(
            message=safe_message,
            http_status=status,
            error_code=str(status),
            retryable=retryable,
            provider_kind=self.provider_kind,
            request_id=None,
            safe_message=safe_message
        )

class VercelGatewayPolicy(EndpointPolicy):
    def build_headers(self, provider_api_key: Optional[str], gateway_api_key: Optional[str], credential_mode: str) -> Dict[str, str]:
        headers = {}
        key = gateway_api_key or provider_api_key
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def classify_error(self, status: int, body: Any) -> ProviderRequestError:
        retryable = status in (408, 429) or status >= 500
        safe_message = f"Vercel Gateway error {status}"
        return ProviderRequestError(
            message=safe_message,
            http_status=status,
            error_code=str(status),
            retryable=retryable,
            provider_kind=self.provider_kind,
            request_id=None,
            safe_message=safe_message
        )

    def validate_model(self, model: str) -> bool:
        return super().validate_model(model)

class NativeOpenAIPolicy(EndpointPolicy):
    def build_headers(self, provider_api_key: Optional[str], gateway_api_key: Optional[str], credential_mode: str) -> Dict[str, str]:
        headers = {}
        if provider_api_key:
            headers["Authorization"] = f"Bearer {provider_api_key}"
        return headers

    def classify_error(self, status: int, body: Any) -> ProviderRequestError:
        retryable = status in (408, 429) or status >= 500
        safe_message = f"OpenAI native error {status}"
        return ProviderRequestError(
            message=safe_message,
            http_status=status,
            error_code=str(status),
            retryable=retryable,
            provider_kind=self.provider_kind,
            request_id=None,
            safe_message=safe_message
        )

class OpenAICompatiblePolicy(EndpointPolicy):
    def build_headers(self, provider_api_key: Optional[str], gateway_api_key: Optional[str], credential_mode: str) -> Dict[str, str]:
        headers = {}
        if provider_api_key:
            headers["Authorization"] = f"Bearer {provider_api_key}"
        return headers

    def classify_error(self, status: int, body: Any) -> ProviderRequestError:
        retryable = status in (408, 429) or status >= 500
        safe_message = f"OpenAI compatible error {status}"
        return ProviderRequestError(
            message=safe_message,
            http_status=status,
            error_code=str(status),
            retryable=retryable,
            provider_kind=self.provider_kind,
            request_id=None,
            safe_message=safe_message
        )

class LocalOpenAICompatiblePolicy(OpenAICompatiblePolicy):
    """OpenAI-compatible service bound to loopback (for example 9router)."""

    def requires_api_key(self) -> bool:
        return False

def classify_endpoint(base_url: Optional[str]) -> EndpointPolicy:
    if not base_url:
        return NativeOpenAIPolicy(provider_kind="native_openai", normalized_base_url="https://api.openai.com/v1")
    
    parsed = urllib.parse.urlparse(base_url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"Base URL không hợp lệ: {base_url!r}")
    if parsed.query or parsed.fragment:
        raise ValueError("Base URL không được chứa query string hoặc fragment")
    hostname = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/")

    # Preserve a non-default port. Dropping it would turn e.g.
    # http://localhost:20128/v1 into http://localhost/v1.
    port = f":{parsed.port}" if parsed.port else ""
    host_for_url = f"[{hostname}]" if ":" in hostname and not hostname.startswith("[") else hostname
    normalized_url = f"{parsed.scheme}://{host_for_url}{port}{path}"
    
    if hostname == "gateway.ai.cloudflare.com" and re.fullmatch(r"/v1/[^/]+/[^/]+/compat", path):
        return CloudflareGatewayPolicy(provider_kind="cloudflare_ai_gateway", normalized_base_url=normalized_url)

    if hostname == "gateway.ai.cloudflare.com":
        raise ValueError("Cloudflare AI Gateway base URL phải có dạng /v1/<account>/<gateway>/compat")
    
    if hostname == "ai-gateway.vercel.sh":
        return VercelGatewayPolicy(provider_kind="vercel_ai_gateway", normalized_base_url=normalized_url)
    
    if hostname == "api.openai.com":
        return NativeOpenAIPolicy(provider_kind="native_openai", normalized_base_url=normalized_url)

    if hostname in ("localhost", "127.0.0.1", "::1"):
        return LocalOpenAICompatiblePolicy(
            provider_kind="local_openai_compatible",
            normalized_base_url=normalized_url,
        )
    
    return OpenAICompatiblePolicy(provider_kind="openai_compatible", normalized_base_url=normalized_url)
