import json
import os
import threading
from typing import Dict, List, Optional

import requests

from .utils import sha256_text


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
        self._cache_lock = threading.Lock()

    def _cache_key(self, payload: Dict) -> str:
        return sha256_text(json.dumps(payload, sort_keys=True))

    def chat(self, messages: List[Dict[str, str]], cache: Optional[Dict[str, str]] = None) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        key = self._cache_key(payload)
        if cache is not None:
            with self._cache_lock:
                if key in cache:
                    return cache[key]

        if self.base_url.endswith("/v1"):
            url = f"{self.base_url}/chat/completions"
        else:
            url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        response = requests.post(url, headers=headers, json=payload, timeout=(120, 480))
        response.raise_for_status()
        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except Exception as exc:
            raise RuntimeError(f"LLM response missing content: {data}") from exc
        if cache is not None:
            with self._cache_lock:
                cache[key] = content
        return content


def from_env() -> LLMClient:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
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
