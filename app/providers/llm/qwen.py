"""Ollama-compatible Qwen HTTP adapter; never starts or pulls a model."""

import json
import logging
from time import perf_counter
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from app.config.settings import Settings
from app.providers.health import ProviderHealth
from app.providers.llm.base import LLMRequest, ResponseT
from app.providers.metrics import ProviderOperationMetrics
from app.utils.errors import (
    ConfigurationError,
    ProviderInferenceError,
    ProviderResponseValidationError,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)
_MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class QwenProvider:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        if settings.app_env != "lightning":
            raise ConfigurationError("Qwen is available only in explicit Lightning mode.")
        url = urlsplit(settings.llm_base_url)
        if url.scheme not in {"http", "https"} or not url.netloc or url.username or url.password:
            raise ConfigurationError(
                "LLM_BASE_URL must be an HTTP(S) server URL without credentials."
            )
        self.settings = settings
        self.client = client
        self.last_metrics: ProviderOperationMetrics | None = None

    @property
    def _chat_url(self) -> str:
        return self.settings.llm_base_url.rstrip("/") + "/api/chat"

    @property
    def _tags_url(self) -> str:
        return self.settings.llm_base_url.rstrip("/") + "/api/tags"

    async def _post(self, payload: dict[str, object]) -> httpx.Response:
        if self.client is not None:
            return await self.client.post(
                self._chat_url, json=payload, timeout=self.settings.llm_timeout_seconds
            )
        async with httpx.AsyncClient(trust_env=False) as client:
            return await client.post(
                self._chat_url, json=payload, timeout=self.settings.llm_timeout_seconds
            )

    async def _get_health(self) -> httpx.Response:
        if self.client is not None:
            return await self.client.get(self._tags_url, timeout=self.settings.llm_timeout_seconds)
        async with httpx.AsyncClient(trust_env=False) as client:
            return await client.get(self._tags_url, timeout=self.settings.llm_timeout_seconds)

    async def _request(self, request: LLMRequest, schema: dict | None = None) -> str:
        payload: dict[str, object] = {
            "model": self.settings.llm_model,
            "stream": False,
            "messages": [
                {"role": "system", "content": request.instructions},
                {"role": "user", "content": request.context_json},
            ],
            "options": {
                "temperature": self.settings.llm_temperature,
                "num_predict": self.settings.llm_max_output_tokens,
            },
        }
        if schema is not None:
            payload["format"] = schema
        started = perf_counter()
        try:
            response = await self._post(payload)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderUnavailableError(
                f"Qwen service timed out at {self.settings.llm_base_url}."
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(
                f"Qwen service unavailable at {self.settings.llm_base_url}."
            ) from exc

        elapsed = perf_counter() - started
        try:
            if len(response.content) > _MAX_RESPONSE_BYTES:
                raise ProviderResponseValidationError("Qwen response exceeds the permitted size.")
            envelope = response.json()
            content = envelope["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ProviderResponseValidationError("Qwen returned an empty response.")
            token_count = envelope.get("eval_count")
            eval_duration = envelope.get("eval_duration")
            tokens_per_second = None
            if (
                isinstance(token_count, int)
                and isinstance(eval_duration, int)
                and eval_duration > 0
            ):
                tokens_per_second = token_count / (eval_duration / 1_000_000_000)
            self.last_metrics = ProviderOperationMetrics(
                operation=request.task.value,
                duration_seconds=elapsed,
                token_count=token_count if isinstance(token_count, int) else None,
                tokens_per_second=tokens_per_second,
            )
            logger.info(
                "provider=qwen operation=%s model=%s duration_ms=%.1f success=true",
                request.task.value,
                self.settings.llm_model,
                elapsed * 1000,
            )
            return content.strip()
        except ProviderResponseValidationError:
            raise
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderResponseValidationError(
                "Qwen returned a malformed response envelope."
            ) from exc

    async def generate(self, request: LLMRequest) -> str:
        try:
            return await self._request(request)
        except (ProviderUnavailableError, ProviderResponseValidationError):
            raise
        except Exception as exc:
            raise ProviderInferenceError("Qwen generation failed.") from exc

    async def generate_structured(self, request: LLMRequest, schema: type[ResponseT]) -> ResponseT:
        text = await self._request(request, schema.model_json_schema())
        try:
            return schema.model_validate_json(text)
        except (ValidationError, json.JSONDecodeError) as exc:
            raise ProviderResponseValidationError(
                "Qwen response failed JSON schema validation."
            ) from exc

    async def health_check(self) -> ProviderHealth:
        started = perf_counter()
        try:
            response = await self._get_health()
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload.get("models"), list):
                raise ValueError("invalid tags envelope")
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise ProviderUnavailableError(
                f"Qwen service unavailable at {self.settings.llm_base_url}."
            ) from exc
        elapsed = perf_counter() - started
        return ProviderHealth(
            provider="qwen",
            status="healthy",
            mode="real",
            latency_ms=elapsed * 1000,
            model=self.settings.llm_model,
            device=self.settings.llm_device,
            detail="Ollama-compatible endpoint reachable",
        )
