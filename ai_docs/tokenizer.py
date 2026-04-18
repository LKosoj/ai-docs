from functools import lru_cache
from typing import List

import tiktoken


class _ByteEncoding:
    def encode(self, text: str):
        return list(text.encode("utf-8", errors="ignore"))

    def decode(self, tokens):
        return bytes(tokens).decode("utf-8", errors="ignore")


@lru_cache(maxsize=None)
def get_encoding(model: str):
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        try:
            return tiktoken.get_encoding("cl100k_base")
        except Exception:
            return _ByteEncoding()


@lru_cache(maxsize=2048)
def _encode_tokens(text: str, model: str) -> tuple[int, ...]:
    enc = get_encoding(model)
    return tuple(enc.encode(text))


@lru_cache(maxsize=512)
def _chunk_text_cached(text: str, model: str, max_tokens: int) -> tuple[str, ...]:
    enc = get_encoding(model)
    tokens = _encode_tokens(text, model)
    chunks = []
    for i in range(0, len(tokens), max_tokens):
        chunk = tokens[i:i + max_tokens]
        chunks.append(enc.decode(chunk))
    return tuple(chunks)


def count_tokens(text: str, model: str) -> int:
    return len(_encode_tokens(text, model))


def chunk_text(text: str, model: str, max_tokens: int) -> List[str]:
    return list(_chunk_text_cached(text, model, max_tokens))
