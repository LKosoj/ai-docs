import hashlib
import os
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8", errors="ignore"))


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def safe_slug(path: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in path).strip("_").lower()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def is_binary_file(path: Path, sample_size: int = 2048) -> bool:
    try:
        with path.open("rb") as f:
            chunk = f.read(sample_size)
        if b"\x00" in chunk:
            return True
        return False
    except OSError:
        return True


def is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://") or value.startswith("git@")


def to_posix(path: Path) -> str:
    return path.as_posix()

