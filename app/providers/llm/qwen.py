"""Ollama-compatible Qwen HTTP adapter; never starts a server or pulls models."""

import json
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from app.config.settings import Settings
from app.providers.llm.base import LLMRequest, LLMTask, ResponseT
from app.utils.errors import ConfigurationError, ProviderError


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

    async def _request(self, request: LLMRequest, schema: dict | None = None) -> str:
        payload = {
            "model": self.settings.llm_model,
            "stream": False,
            "messages": [
                {"role": "system", "content": request.instructions},
                {"role": "user", "content": request.context_json},
            ],
            "options": {
                "temperature": 0,
                "num_predict": 16384 if request.task == LLMTask.FINAL_EVALUATION else 4096,
            },
        }
        if schema is not None:
            payload["format"] = schema
        try:
            if self.client is not None:
                response = await self.client.post(
                    self.settings.llm_base_url.rstrip("/") + "/api/chat",
                    json=payload,
                    timeout=self.settings.provider_timeout_seconds,
                )
            else:
                async with httpx.AsyncClient(trust_env=False) as client:
                    response = await client.post(
                        self.settings.llm_base_url.rstrip("/") + "/api/chat",
                        json=payload,
                        timeout=self.settings.provider_timeout_seconds,
                    )
            response.raise_for_status()
            if len(response.content) > 2 * 1024 * 1024:
                raise ProviderError("Language provider response exceeds the size limit.")
            content = response.json()["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ProviderError("Language provider returned an empty response.")
            return content
        except httpx.TimeoutException as exc:
            raise ProviderError(
                "Language provider timed out. Please retry or end the interview."
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                "Language provider is unavailable. Check the cloud service."
            ) from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError("Language provider returned a malformed response.") from exc

    async def generate(self, request: LLMRequest) -> str:
        return await self._request(request)

    async def generate_structured(self, request: LLMRequest, schema: type[ResponseT]) -> ResponseT:
        text = await self._request(request, schema.model_json_schema())
        try:
            return schema.model_validate_json(text)
        except (ValidationError, json.JSONDecodeError) as exc:
            raise ProviderError("Language provider response failed schema validation.") from exc
