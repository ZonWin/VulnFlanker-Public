from __future__ import annotations

import json
from typing import Any

from app.ai.base import AICompletionRequest, AIMessage
from app.ai.providers.openai_compatible import OpenAICompatibleProviderClient
import app.ai.providers.openai_compatible as provider_module


class _FakeResponse:
    def __init__(self, payload: dict[str, Any], request_id: str = "req-test") -> None:
        self._payload = payload
        self.headers = {"x-request-id": request_id}

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def _request(
    *,
    model_vendor: str = "openai",
    metadata: dict[str, Any] | None = None,
) -> AICompletionRequest:
    return AICompletionRequest(
        provider="openai_compatible",
        model_vendor=model_vendor,
        base_url="https://llm.example.test/v1",
        api_key="test-key",
        model="test-model",
        messages=[AIMessage(role="user", content="return json")],
        allow_web_search=True,
        metadata=metadata or {},
    )


def test_openai_vendor_keeps_openai_web_search_tool(monkeypatch) -> None:
    captured_bodies: list[dict[str, Any]] = []

    def fake_urlopen(http_request, timeout):
        captured_bodies.append(json.loads(http_request.data.decode("utf-8")))
        return _FakeResponse(
            {
                "model": "test-model",
                "choices": [
                    {"message": {"content": json.dumps({"status": "ok"})}},
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            }
        )

    monkeypatch.setattr(provider_module, "urlopen", fake_urlopen)

    result = OpenAICompatibleProviderClient().complete_json(_request(model_vendor="openai"))

    assert result.status == "success"
    assert result.parsed_json == {"status": "ok"}
    assert captured_bodies[0]["tools"] == [{"type": "web_search"}]
    assert "thinking" not in captured_bodies[0]


def test_provider_accepts_json_wrapped_in_markdown_fence(monkeypatch) -> None:
    def fake_urlopen(http_request, timeout):
        return _FakeResponse(
            {
                "model": "test-model",
                "choices": [
                    {
                        "message": {
                            "content": '```json\n{"status": "ok", "confidence": 0.8}\n```'
                        }
                    },
                ],
            }
        )

    monkeypatch.setattr(provider_module, "urlopen", fake_urlopen)

    result = OpenAICompatibleProviderClient().complete_json(_request())

    assert result.status == "success"
    assert result.parsed_json == {"status": "ok", "confidence": 0.8}


def test_provider_accepts_json_with_surrounding_text(monkeypatch) -> None:
    def fake_urlopen(http_request, timeout):
        return _FakeResponse(
            {
                "model": "test-model",
                "choices": [
                    {
                        "message": {
                            "content": 'Result:\n{"status": "ok", "source_urls": []}\nDone.'
                        }
                    },
                ],
            }
        )

    monkeypatch.setattr(provider_module, "urlopen", fake_urlopen)

    result = OpenAICompatibleProviderClient().complete_json(_request())

    assert result.status == "success"
    assert result.parsed_json == {"status": "ok", "source_urls": []}


def test_kimi_vendor_preloads_builtin_web_search_context(monkeypatch) -> None:
    captured_bodies: list[dict[str, Any]] = []
    captured_timeouts: list[int] = []
    responses = [
        {
            "model": "kimi-k2.6",
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "$web_search",
                                    "arguments": json.dumps(
                                        {"query": "CVE-2026-0001 affected versions"}
                                    ),
                                },
                            }
                        ],
                    },
                }
            ],
            "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
        },
        {
            "model": "kimi-k2.6",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(
                            {
                                "status": "sufficient",
                                "affected_versions": "< 1.2.3",
                                "confidence": 0.82,
                                "evidence": [],
                                "source_urls": [],
                                "conflicts": [],
                            }
                        ),
                    },
                }
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 6, "total_tokens": 11},
        },
    ]

    def fake_urlopen(http_request, timeout):
        captured_bodies.append(json.loads(http_request.data.decode("utf-8")))
        captured_timeouts.append(timeout)
        return _FakeResponse(responses.pop(0), request_id=f"req-{len(captured_bodies)}")

    monkeypatch.setattr(provider_module, "urlopen", fake_urlopen)

    result = OpenAICompatibleProviderClient().complete_json(
        _request(
            model_vendor="kimi",
            metadata={
                "enrichment_input": {
                    "vulnerability": {
                        "canonical_id": "CVE-2026-0001",
                        "title": "Example package vulnerability",
                    },
                    "sources": [{"external_id": "QVD-2026-0001"}],
                    "raw_events": [],
                }
            },
        )
    )

    assert result.status == "success"
    assert result.parsed_json["affected_versions"] == "< 1.2.3"
    assert result.provider_request_id == "req-2"
    assert result.total_tokens == 18
    assert len(captured_bodies) == 2
    assert captured_timeouts == [60, 120]
    assert captured_bodies[0]["tools"] == [
        {"type": "builtin_function", "function": {"name": "$web_search"}}
    ]
    assert captured_bodies[0]["thinking"] == {"type": "disabled"}
    assert captured_bodies[0]["max_tokens"] == 96
    assert "response_format" not in captured_bodies[0]
    assert "CVE-2026-0001" in captured_bodies[0]["messages"][0]["content"]
    assert captured_bodies[1]["response_format"] == {"type": "json_object"}
    assert [message["role"] for message in captured_bodies[1]["messages"]] == [
        "user",
        "assistant",
        "tool",
        "user",
    ]
    assert captured_bodies[1]["messages"][2] == {
        "role": "tool",
        "tool_call_id": "call_1",
        "name": "$web_search",
        "content": json.dumps(
            {"query": "CVE-2026-0001 affected versions"},
            ensure_ascii=False,
        ),
    }


def test_kimi_vendor_falls_back_without_tools_when_presearch_does_not_call_tool(
    monkeypatch,
) -> None:
    captured_bodies: list[dict[str, Any]] = []
    responses = [
        {
            "model": "kimi-k2.6",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": "I cannot find that CVE.",
                    },
                }
            ],
            "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
        },
        {
            "model": "kimi-k2.6",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(
                            {
                                "status": "insufficient",
                                "affected_versions": None,
                                "confidence": 0.3,
                                "evidence": [],
                                "source_urls": [],
                                "conflicts": [],
                            }
                        ),
                    },
                }
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 6, "total_tokens": 11},
        },
    ]

    def fake_urlopen(http_request, timeout):
        captured_bodies.append(json.loads(http_request.data.decode("utf-8")))
        return _FakeResponse(responses.pop(0), request_id=f"req-{len(captured_bodies)}")

    monkeypatch.setattr(provider_module, "urlopen", fake_urlopen)

    result = OpenAICompatibleProviderClient().complete_json(
        _request(
            model_vendor="kimi",
            metadata={
                "enrichment_input": {
                    "vulnerability": {"canonical_id": "CVE-2026-0002"},
                    "sources": [],
                    "raw_events": [],
                }
            },
        )
    )

    assert result.status == "success"
    assert result.parsed_json["status"] == "insufficient"
    assert result.total_tokens == 18
    assert len(captured_bodies) == 2
    assert "tools" in captured_bodies[0]
    assert "response_format" not in captured_bodies[0]
    assert "tools" not in captured_bodies[1]
    assert captured_bodies[1]["response_format"] == {"type": "json_object"}
    assert captured_bodies[1]["messages"][0]["role"] == "user"
    assert "web_search did not return" in captured_bodies[1]["messages"][0]["content"]
