import asyncio
import inspect
import json
import os
import random
from typing import Dict, List, Optional, Protocol

import httpx
from openai import AsyncOpenAI

from .config import ConfigError, parse_bool_env, parse_float_env, parse_int_env
from .logging_utils import get_logger
from .utils import sha256_text


class LLMProtocol(Protocol):
    model: str
    max_tokens: int
    context_limit: int
    concurrency: int

    async def chat(self, messages: List[Dict[str, str]], cache: Optional[Dict[str, str]] = None) -> str:
        ...


class LLMClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 1200,
        context_limit: int = 8192,
        concurrency: int = 5,
        verify: bool = True,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.context_limit = context_limit
        self.concurrency = max(1, int(concurrency))
        self.verify = verify
        self._cache_lock = asyncio.Lock()
        self._request_sem = asyncio.Semaphore(self.concurrency)
        self._http_client = httpx.AsyncClient(verify=verify)
        client_kwargs = {"api_key": self.api_key, "timeout": 1200.0, "http_client": self._http_client}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        self._client = AsyncOpenAI(**client_kwargs)

    async def __aenter__(self) -> "LLMClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        close_client = getattr(self._client, "aclose", None) or getattr(self._client, "close", None)
        if callable(close_client):
            result = close_client()
            if inspect.isawaitable(result):
                await result
        await self._http_client.aclose()

    def _estimate_input_tokens(self, messages: List[Dict[str, str]]) -> int:
        # Approximation is sufficient for timeout scaling; exact tiktoken
        # counting on every request is expensive for large payloads.
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            total += (len(content) // 4) + 4
        return total

    def _compute_read_timeout(self, input_tokens: int) -> float:
        t_min = 1000
        t_max = 250000
        timeout_min = 60.0
        timeout_max = 1200.0
        if input_tokens <= t_min:
            return timeout_min
        if input_tokens >= t_max:
            return timeout_max
        ratio = (input_tokens - t_min) / (t_max - t_min)
        return timeout_min + ratio * (timeout_max - timeout_min)

    def _cache_key(self, payload: Dict) -> str:
        return sha256_text(json.dumps(payload, sort_keys=True))

    def _validate_content(self, response) -> str:
        choices = getattr(response, "choices", None)
        if not choices:
            raise RuntimeError("LLM response is missing choices")
        choice = choices[0]
        finish_reason = getattr(choice, "finish_reason", None)
        if finish_reason not in (None, "stop"):
            raise RuntimeError(f"LLM response finish_reason is {finish_reason!r}")
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None)
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("LLM response has empty content")
        return content

    async def chat(self, messages: List[Dict[str, str]], cache: Optional[Dict[str, str]] = None) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        key = self._cache_key(payload)
        if cache is not None:
            async with self._cache_lock:
                if key in cache:
                    cached = cache[key]
                    if not isinstance(cached, str) or not cached.strip():
                        raise RuntimeError(f"Invalid cached LLM response for key {key}")
                    return cached

        input_tokens = self._estimate_input_tokens(messages)
        read_timeout = self._compute_read_timeout(input_tokens)
        max_read_timeout = 1200.0
        max_retries = 5
        backoff = 1.0
        content: Optional[str] = None
        timeout = httpx.Timeout(read=read_timeout, connect=7.0, write=30.0, pool=read_timeout)
        # Global LLM concurrency cap: at most self.concurrency in-flight
        # requests across the whole process (including retry backoff).
        async with self._request_sem:
            for attempt in range(1, max_retries + 1):
                try:
                    response = await self._client.chat.completions.create(**payload, timeout=timeout)
                    content = self._validate_content(response)
                    break
                except Exception as exc:
                    status = getattr(exc, "status_code", None)
                    if status is None:
                        response = getattr(exc, "response", None)
                        status = getattr(response, "status_code", None)
                    message = str(exc).lower()
                    is_timeout = isinstance(exc, httpx.TimeoutException) or "timeout" in message
                    retryable = status in {408, 429} or (status is not None and 500 <= status < 600) or is_timeout
                    if not retryable or attempt >= max_retries:
                        raise RuntimeError(f"LLM request failed: {exc}") from exc
                    if status == 408 or is_timeout:
                        read_timeout = min(read_timeout * 1.5, max_read_timeout)
                        timeout = httpx.Timeout(read=read_timeout, connect=7.0, write=30.0, pool=read_timeout)
                    jitter = random.uniform(0, backoff * 0.1)
                    await asyncio.sleep(backoff + jitter)
                    backoff = min(backoff * 2, 60.0)
        if content is None:
            raise RuntimeError("LLM request failed: empty response")
        if cache is not None:
            async with self._cache_lock:
                cache[key] = content
        return content


def from_env(concurrency: Optional[int] = None) -> LLMClient:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ConfigError("OPENAI_API_KEY is not set")
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    temperature = parse_float_env("OPENAI_TEMPERATURE", 0.2)
    max_tokens = parse_int_env("OPENAI_MAX_TOKENS", 1200)
    context_limit = parse_int_env("OPENAI_CONTEXT_TOKENS", 8192)
    if concurrency is None:
        concurrency = parse_int_env("AI_DOCS_THREADS", 5)
    insecure_ssl = parse_bool_env("AI_DOCS_INSECURE_SSL", default=False)
    if insecure_ssl:
        get_logger().warning("AI_DOCS_INSECURE_SSL=true disables TLS certificate verification")
    return LLMClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        context_limit=context_limit,
        concurrency=concurrency,
        verify=not insecure_ssl,
    )
