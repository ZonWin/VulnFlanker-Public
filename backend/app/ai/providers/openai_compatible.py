from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.ai.base import AICompletionRequest, AICompletionResult


KIMI_PRESEARCH_TIMEOUT_SECONDS = 60
KIMI_PRESEARCH_MAX_TOKENS = 96
KIMI_FINAL_WEB_TIMEOUT_SECONDS = 120


class OpenAICompatibleProviderClient:
    def complete_json(self, request: AICompletionRequest) -> AICompletionResult:
        if not request.base_url:
            return AICompletionResult(
                status="failed",
                model=request.model,
                error_message="base_url is required for openai_compatible provider.",
            )
        if not request.api_key:
            return AICompletionResult(
                status="failed",
                model=request.model,
                error_message="api_key is required for openai_compatible provider.",
            )

        endpoint = _completion_endpoint(request.base_url)
        body = _completion_body(request)

        if request.allow_web_search and _model_vendor(request) == "kimi":
            return _complete_kimi_web_search(endpoint, request, body)
        return _complete_once(endpoint, request, body)


def _complete_once(
    endpoint: str,
    request: AICompletionRequest,
    body: dict[str, Any],
) -> AICompletionResult:
    response = _post_completion(endpoint, request, body)
    if isinstance(response, AICompletionResult):
        return response
    payload, response_text, provider_request_id = response
    return _completion_result_from_payload(
        payload,
        response_text,
        request,
        provider_request_id,
    )


def _complete_kimi_web_search(
    endpoint: str,
    request: AICompletionRequest,
    body: dict[str, Any],
) -> AICompletionResult:
    usage_totals: dict[str, int] = {}
    provider_request_id: str | None = None

    presearch = _kimi_preload_web_search(endpoint, request)
    if isinstance(presearch, AICompletionResult):
        return presearch
    search_messages, search_usage = presearch
    _accumulate_usage(usage_totals, search_usage)
    if search_messages:
        body["messages"] = _inject_kimi_search_messages(body["messages"], search_messages)
    else:
        body.pop("tools", None)
        body["messages"] = _inject_kimi_no_search_notice(body["messages"])

    for _ in range(5):
        response = _post_completion(
            endpoint,
            request,
            body,
            timeout_seconds=max(
                request.timeout_seconds,
                KIMI_FINAL_WEB_TIMEOUT_SECONDS,
            ),
        )
        if isinstance(response, AICompletionResult):
            return response

        payload, response_text, provider_request_id = response
        _accumulate_usage(usage_totals, payload.get("usage"))
        choice = _first_choice(payload)
        message = choice.get("message") if choice else None
        if (
            isinstance(message, dict)
            and choice.get("finish_reason") == "tool_calls"
            and isinstance(message.get("tool_calls"), list)
        ):
            body["messages"].append(_assistant_tool_call_message(message))
            for tool_call in message["tool_calls"]:
                body["messages"].append(_kimi_tool_result_message(tool_call))
            continue

        return _completion_result_from_payload(
            payload,
            response_text,
            request,
            provider_request_id,
            usage_totals,
        )

    return AICompletionResult(
        status="failed",
        model=request.model,
        error_message="Kimi web search tool loop exceeded the maximum number of rounds.",
        provider_request_id=provider_request_id,
    )


def _kimi_preload_web_search(
    endpoint: str,
    request: AICompletionRequest,
) -> tuple[list[dict[str, Any]], Any] | AICompletionResult:
    search_prompt = _kimi_search_prompt(request)
    if not search_prompt:
        return [], {}

    body: dict[str, Any] = {
        "model": request.model,
        "messages": [{"role": "user", "content": search_prompt}],
        "tools": _web_search_tools(request),
        "thinking": {"type": "disabled"},
        "temperature": request.temperature,
        "max_tokens": KIMI_PRESEARCH_MAX_TOKENS,
    }
    if request.max_tokens is not None:
        body["max_tokens"] = min(request.max_tokens, KIMI_PRESEARCH_MAX_TOKENS)

    response = _post_completion(
        endpoint,
        request,
        body,
        timeout_seconds=max(request.timeout_seconds, KIMI_PRESEARCH_TIMEOUT_SECONDS),
    )
    if isinstance(response, AICompletionResult):
        return response

    payload, _response_text, _provider_request_id = response
    choice = _first_choice(payload)
    message = choice.get("message") if choice else None
    if (
        not isinstance(message, dict)
        or choice.get("finish_reason") != "tool_calls"
        or not isinstance(message.get("tool_calls"), list)
    ):
        return [], payload.get("usage")

    messages: list[dict[str, Any]] = [
        {"role": "user", "content": search_prompt},
        _assistant_tool_call_message(message),
    ]
    for tool_call in message["tool_calls"]:
        messages.append(_kimi_tool_result_message(tool_call))
    return messages, payload.get("usage")


def _post_completion(
    endpoint: str,
    request: AICompletionRequest,
    body: dict[str, Any],
    *,
    timeout_seconds: int | None = None,
) -> tuple[dict[str, Any], str, str | None] | AICompletionResult:
    http_request = Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {request.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(
            http_request,
            timeout=timeout_seconds or request.timeout_seconds,
        ) as response:
            response_text = response.read().decode("utf-8", errors="replace")
            provider_request_id = response.headers.get("x-request-id")
    except HTTPError as exc:
        error_text = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
        return AICompletionResult(
            status="failed",
            model=request.model,
            error_message=_compact_error(error_text or str(exc)),
        )
    except URLError as exc:
        return AICompletionResult(
            status="failed",
            model=request.model,
            error_message=_compact_error(str(exc.reason)),
        )
    except TimeoutError:
        return AICompletionResult(
            status="timeout",
            model=request.model,
            error_message="AI provider request timed out.",
        )

    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        return AICompletionResult(
            status="failed",
            raw_text=response_text,
            model=request.model,
            error_message=f"Invalid AI provider response: {exc}",
            provider_request_id=provider_request_id,
        )
    if not isinstance(payload, dict):
        return AICompletionResult(
            status="failed",
            raw_text=response_text,
            model=request.model,
            error_message="Invalid AI provider response: root payload is not an object.",
            provider_request_id=provider_request_id,
        )
    return payload, response_text, provider_request_id


def _completion_body(request: AICompletionRequest) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": request.model,
        "messages": [
            {"role": message.role, "content": message.content}
            for message in request.messages
        ],
        "temperature": request.temperature,
    }
    if request.max_tokens is not None:
        body["max_tokens"] = request.max_tokens
    if request.json_mode:
        body["response_format"] = {"type": "json_object"}
    if request.allow_web_search:
        body["tools"] = _web_search_tools(request)
        if _model_vendor(request) == "kimi":
            body["thinking"] = {"type": "disabled"}
    return body


def _completion_result_from_payload(
    payload: dict[str, Any],
    response_text: str,
    request: AICompletionRequest,
    provider_request_id: str | None,
    usage_override: dict[str, int] | None = None,
) -> AICompletionResult:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        return AICompletionResult(
            status="failed",
            raw_text=response_text,
            model=request.model,
            error_message=f"Invalid AI provider response: {exc}",
            provider_request_id=provider_request_id,
        )
    if not isinstance(content, str):
        return AICompletionResult(
            status="failed",
            raw_text=response_text,
            model=payload.get("model") or request.model,
            error_message="Invalid AI provider response: message.content is not a string.",
            provider_request_id=provider_request_id,
        )

    try:
        parsed_json = _parse_json_content(content)
    except json.JSONDecodeError as exc:
        return AICompletionResult(
            status="failed",
            raw_text=content,
            model=payload.get("model") or request.model,
            error_message=f"AI provider did not return valid JSON: {exc}",
            provider_request_id=provider_request_id,
        )

    usage = usage_override or payload.get("usage")
    if not isinstance(usage, dict):
        usage = {}
    return AICompletionResult(
        status="success",
        raw_text=content,
        parsed_json=parsed_json,
        model=payload.get("model") or request.model,
        prompt_tokens=_optional_int(usage.get("prompt_tokens")),
        completion_tokens=_optional_int(usage.get("completion_tokens")),
        total_tokens=_optional_int(usage.get("total_tokens")),
        provider_request_id=provider_request_id,
    )


def _parse_json_content(content: str) -> Any:
    try:
        return json.loads(content)
    except json.JSONDecodeError as original_exc:
        stripped = content.strip()
        candidates: list[str] = []
        fenced = re.search(
            r"```(?:json)?\s*(.*?)\s*```",
            stripped,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if fenced:
            candidates.append(fenced.group(1).strip())
        first_object = stripped.find("{")
        last_object = stripped.rfind("}")
        if 0 <= first_object < last_object:
            candidates.append(stripped[first_object : last_object + 1])

        for candidate in candidates:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
        raise original_exc


def _model_vendor(request: AICompletionRequest) -> str:
    return (request.model_vendor or "openai").strip().lower()


def _web_search_tools(request: AICompletionRequest) -> list[dict[str, Any]]:
    if _model_vendor(request) == "kimi":
        return [
            {
                "type": "builtin_function",
                "function": {"name": "$web_search"},
            }
        ]
    return [{"type": "web_search"}]


def _kimi_search_prompt(request: AICompletionRequest) -> str | None:
    query = _kimi_search_query_from_metadata(request.metadata)
    if not query:
        query = _kimi_search_query_from_messages(request.messages)
    if not query:
        return None
    return (
        "请联网搜索以下漏洞的受影响版本、修复版本、官方公告和发行版公告。"
        "优先查 vendor advisory、NVD、CVE.org、GitHub Advisory、OSV、distribution advisory。"
        "只需要执行搜索并保留搜索结果，后续会再要求结构化 JSON。\n\n"
        f"查询关键词：{query}"
    )


def _kimi_search_query_from_metadata(metadata: dict[str, Any]) -> str | None:
    enrichment_input = metadata.get("enrichment_input")
    if not isinstance(enrichment_input, dict):
        return None

    terms: list[str | None] = []
    vulnerability = enrichment_input.get("vulnerability")
    if isinstance(vulnerability, dict):
        terms.extend(
            [
                _optional_text(vulnerability.get("canonical_id")),
                _optional_text(vulnerability.get("title")),
                _optional_text(vulnerability.get("vendor")),
                _optional_text(vulnerability.get("product")),
            ]
        )

    for source in _list_of_dicts(enrichment_input.get("sources")):
        terms.extend(
            [
                _optional_text(source.get("external_id")),
                _optional_text(source.get("title")),
            ]
        )

    for raw_event in _list_of_dicts(enrichment_input.get("raw_events")):
        terms.append(_optional_text(raw_event.get("external_key")))
        payload = raw_event.get("payload")
        if not isinstance(payload, dict):
            continue
        content = payload.get("content")
        if not isinstance(content, dict):
            continue
        terms.extend(
            [
                _optional_text(content.get("cve")),
                _optional_text(content.get("unique_key")),
                _optional_text(content.get("title")),
            ]
        )
        tags = content.get("tags")
        if isinstance(tags, list):
            terms.extend(_optional_text(tag) for tag in tags[:6])

    return _join_search_terms(terms)


def _kimi_search_query_from_messages(messages: list[Any]) -> str | None:
    chunks: list[str] = []
    for message in messages:
        content = getattr(message, "content", None)
        if isinstance(content, str):
            chunks.append(content)
    text = " ".join(chunks)
    cves = re.findall(r"\bCVE-\d{4}-\d{4,}\b", text, flags=re.IGNORECASE)
    qvds = re.findall(r"\bQVD-\d{4}-\d{4,}\b", text, flags=re.IGNORECASE)
    title_match = re.search(r'"title"\s*:\s*"([^"]{4,180})"', text)
    terms: list[str | None] = [*cves, *qvds]
    if title_match:
        terms.append(title_match.group(1))
    return _join_search_terms(terms)


def _join_search_terms(terms: list[str | None]) -> str | None:
    seen: set[str] = set()
    selected: list[str] = []
    for term in terms:
        if not term:
            continue
        normalized = " ".join(term.split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        selected.append(normalized)
        if len(selected) >= 12:
            break
    if not selected:
        return None
    selected.extend(["affected versions", "fixed versions", "official advisory"])
    return " ".join(selected)[:900]


def _inject_kimi_search_messages(
    messages: list[dict[str, Any]],
    search_messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not messages or messages[0].get("role") != "system":
        return [*search_messages, *messages]
    return [messages[0], *search_messages, *messages[1:]]


def _inject_kimi_no_search_notice(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    notice = {
        "role": "user",
        "content": (
            "KIMI web_search did not return a tool search_result in this run. "
            "Do not claim that new public web evidence was found. Use the supplied "
            "input only, and return status insufficient unless the supplied sources "
            "already contain reliable affected_versions evidence."
        ),
    }
    if not messages or messages[0].get("role") != "system":
        return [notice, *messages]
    return [messages[0], notice, *messages[1:]]


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first_choice(payload: dict[str, Any]) -> dict[str, Any] | None:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    choice = choices[0]
    return choice if isinstance(choice, dict) else None


def _assistant_tool_call_message(message: dict[str, Any]) -> dict[str, Any]:
    tool_message: dict[str, Any] = {
        "role": "assistant",
        "content": message.get("content"),
        "tool_calls": message.get("tool_calls"),
    }
    if "reasoning_content" in message:
        tool_message["reasoning_content"] = message["reasoning_content"]
    return tool_message


def _kimi_tool_result_message(tool_call: Any) -> dict[str, Any]:
    if not isinstance(tool_call, dict):
        return {
            "role": "tool",
            "tool_call_id": None,
            "name": "$web_search",
            "content": json.dumps({"error": "invalid tool_call"}, ensure_ascii=False),
        }

    function = tool_call.get("function")
    if not isinstance(function, dict):
        function = {}
    name = str(function.get("name") or "$web_search")
    arguments = function.get("arguments")
    if isinstance(arguments, str):
        try:
            content = json.dumps(json.loads(arguments), ensure_ascii=False)
        except json.JSONDecodeError:
            content = arguments
    else:
        content = json.dumps(arguments or {}, ensure_ascii=False)
    return {
        "role": "tool",
        "tool_call_id": tool_call.get("id"),
        "name": name,
        "content": content,
    }


def _accumulate_usage(totals: dict[str, int], usage: Any) -> None:
    if not isinstance(usage, dict):
        return
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = _optional_int(usage.get(key))
        if value is not None:
            totals[key] = totals.get(key, 0) + value


def _completion_endpoint(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def _compact_error(value: str) -> str:
    normalized = " ".join(value.split())
    if len(normalized) > 500:
        return normalized[:497] + "..."
    return normalized


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
