import asyncio
import json
import os
from typing import Dict, List, Optional

import httpx
import random
from openai import AsyncOpenAI

from .utils import sha256_text
from .tokenizer import count_tokens


class LLMClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 1200,
        context_limit: int = 8192,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.context_limit = context_limit
        self._cache_lock = asyncio.Lock()
        client_kwargs = {"api_key": self.api_key, "timeout": 1200.0}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        self._client = AsyncOpenAI(**client_kwargs)

    def _estimate_input_tokens(self, messages: List[Dict[str, str]]) -> int:
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            total += count_tokens(content, self.model)
            total += 4
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
                    return cache[key]

        input_tokens = self._estimate_input_tokens(messages)
        read_timeout = self._compute_read_timeout(input_tokens)
        max_read_timeout = 1200.0
        max_retries = 5
        backoff = 1.0
        last_exc: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                timeout = httpx.Timeout(read=read_timeout, connect=7.0, write=30.0, pool=read_timeout)
                response = await self._client.chat.completions.create(**payload, timeout=timeout)
                content = response.choices[0].message.content
                break
            except Exception as exc:
                last_exc = exc
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
                jitter = random.uniform(0, backoff * 0.1)
                await asyncio.sleep(backoff + jitter)
                backoff = min(backoff * 2, 60.0)
        else:
            raise RuntimeError(f"LLM request failed: {last_exc}") from last_exc
        if cache is not None:
            async with self._cache_lock:
                cache[key] = content
        return content


def from_env() -> LLMClient:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))
    max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", "1200"))
    context_limit = int(os.getenv("OPENAI_CONTEXT_TOKENS", "8192"))
    return LLMClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        context_limit=context_limit,
    )
