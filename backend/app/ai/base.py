from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class AIMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class AICompletionRequest:
    provider: str
    base_url: str | None
    api_key: str | None
    model: str
    messages: list[AIMessage]
    model_vendor: str = "openai"
    json_mode: bool = True
    timeout_seconds: int = 30
    max_tokens: int | None = None
    temperature: float = 0.0
    allow_web_search: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AICompletionResult:
    status: str
    raw_text: str | None = None
    parsed_json: dict[str, Any] | None = None
    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: int | None = None
    error_message: str | None = None
    provider_request_id: str | None = None


class AIProviderClient(Protocol):
    def complete_json(self, request: AICompletionRequest) -> AICompletionResult:
        """Run a JSON-oriented completion request."""
