"""Version 1 translation extension contract; no LLM-specific fields."""

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Protocol

CONTRACT_VERSION = 1
ADAPTER_VERSION = 1


def digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class TranslationError(Exception):
    def __init__(self, code, message, retryable=False, retry_after=0):
        super().__init__(message)
        self.code, self.retryable, self.retry_after = code, retryable, retry_after

    def result(self):
        return {
            "status": "failed",
            "error_code": self.code,
            "message": str(self),
            "retryable": self.retryable,
            "next_retry_at": time.time() + (self.retry_after or 60) if self.retryable else 0,
        }


class Stop:
    def __init__(self, *events):
        self.events = events

    def is_set(self):
        return any(e is not None and e.is_set() for e in self.events)


@dataclass(frozen=True)
class TextItem:
    id: str
    text: str
    source_language: str | None = None


@dataclass
class TranslationRequest:
    items: list[TextItem]
    target_language: str
    context: dict = field(default_factory=dict)
    deadline: float = 0
    stop: object = None

    def check(self):
        if self.stop and self.stop.is_set():
            raise TranslationError("cancelled", "任务已停止")
        if self.deadline and time.monotonic() >= self.deadline:
            raise TranslationError("timeout", "翻译请求超时", True)


class TranslationProvider(Protocol):
    def capabilities(self) -> dict: ...
    def validate_config(self) -> None: ...
    def translate_batch(self, request: TranslationRequest) -> dict[str, dict]: ...
    def close(self) -> None: ...
