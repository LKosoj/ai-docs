from typing import List

import tiktoken


class _ByteEncoding:
    def encode(self, text: str):
        return list(text.encode("utf-8", errors="ignore"))

    def decode(self, tokens):
        return bytes(tokens).decode("utf-8", errors="ignore")


def get_encoding(model: str):
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        try:
            return tiktoken.get_encoding("cl100k_base")
        except Exception:
            return _ByteEncoding()


def count_tokens(text: str, model: str) -> int:
    enc = get_encoding(model)
    return len(enc.encode(text))


def chunk_text(text: str, model: str, max_tokens: int) -> List[str]:
    enc = get_encoding(model)
    tokens = enc.encode(text)
    chunks = []
    for i in range(0, len(tokens), max_tokens):
        chunk = tokens[i:i + max_tokens]
        chunks.append(enc.decode(chunk))
    return chunks
