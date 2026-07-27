from __future__ import annotations

import json
import re
from typing import Any

from app.ai.base import AICompletionRequest, AICompletionResult


class FakeAIProviderClient:
    def complete_json(self, request: AICompletionRequest) -> AICompletionResult:
        if request.metadata.get("force_error"):
            return AICompletionResult(
                status="failed",
                model=request.model,
                error_message="Fake provider forced failure.",
            )

        payload = request.metadata.get("fake_response")
        if payload is None and (
            request.metadata.get("task_template")
            == "vuln_enrichment.extract_from_existing_v1"
        ):
            payload = _fake_vulnerability_enrichment(
                request.metadata.get("enrichment_input")
            )
        if payload is None and request.metadata.get("task_template") == "vuln_enrichment.web_search_v1":
            payload = _fake_web_enrichment(request.metadata.get("enrichment_input"))
        if not isinstance(payload, dict):
            payload = {
                "status": "ok",
                "provider": "fake",
                "model": request.model,
            }
        return AICompletionResult(
            status="success",
            parsed_json=payload,
            raw_text=json.dumps(payload, ensure_ascii=False),
            model=request.model,
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
        )


def _fake_vulnerability_enrichment(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"status": "insufficient", "confidence": 0.2, "evidence": []}

    vulnerability = value.get("vulnerability")
    if not isinstance(vulnerability, dict):
        vulnerability = {}
    source_urls = _collect_urls(value)
    text = _joined_text(value)

    vendor = _clean(vulnerability.get("vendor")) or _field_from_payload(value, "vendor")
    product = _clean(vulnerability.get("product")) or _field_from_payload(value, "product")
    affected_versions = _clean(vulnerability.get("affected_versions"))
    fixed_versions = _clean(vulnerability.get("fixed_versions"))
    remediation = _clean(vulnerability.get("remediation"))

    before_match = re.search(
        r"(?:before|prior to|earlier than|低于|早于)\s+v?([0-9][0-9A-Za-z.\-_+]*)",
        text,
        re.IGNORECASE,
    )
    upgrade_match = re.search(
        r"(?:upgrade to|fixed in|修复版本|升级到|升级至)\s+(?:version\s+|v)?([0-9][0-9A-Za-z.\-_+]*)",
        text,
        re.IGNORECASE,
    )
    if affected_versions is None and before_match:
        affected_versions = f"< {before_match.group(1)}"
    if fixed_versions is None:
        if upgrade_match:
            fixed_versions = f">= {upgrade_match.group(1)}"
        elif before_match:
            fixed_versions = f">= {before_match.group(1)}"
    if remediation is None and fixed_versions:
        remediation = f"Upgrade to {fixed_versions.removeprefix('>= ').strip()} or later."

    suggested = {
        "vendor": vendor,
        "product": product,
        "affected_versions": affected_versions,
        "fixed_versions": fixed_versions,
        "remediation": remediation,
    }
    if not any(suggested.values()):
        return {
            "status": "insufficient",
            "confidence": 0.2,
            "evidence": [],
            "source_urls": source_urls,
            "conflicts": [],
        }

    first_url = source_urls[0] if source_urls else None
    evidence = [
        {
            "field": field,
            "source_type": "existing_raw",
            "source_url": first_url,
            "quote": _quote_for_field(text, field),
            "confidence": 0.8,
        }
        for field, item in suggested.items()
        if item
    ]
    return {
        "status": "sufficient",
        **suggested,
        "confidence": 0.82,
        "evidence": evidence,
        "source_urls": source_urls,
        "conflicts": [],
        "notes": "Fake provider generated this deterministic local response.",
    }


def _fake_web_enrichment(value: Any) -> dict[str, Any]:
    payload = _fake_vulnerability_enrichment(value)
    if payload.get("status") == "insufficient":
        source_urls = _collect_urls(value)
        if not source_urls:
            return payload
        payload = {
            **payload,
            "status": "sufficient",
            "product": _field_from_payload(value, "product") or "Unknown product",
            "fixed_versions": ">= 1.0.0",
            "remediation": "Review the referenced public advisory and apply the fixed release.",
            "confidence": 0.78,
        }
    source_urls = payload.get("source_urls")
    if not isinstance(source_urls, list) or not source_urls:
        source_urls = _collect_urls(value)
    if not source_urls:
        source_urls = ["https://example.test/public-advisory"]
    payload["source_urls"] = source_urls
    payload["evidence"] = [
        {
            **item,
            "source_type": item.get("source_type") or "web_search",
            "source_url": item.get("source_url") or source_urls[0],
            "quote": item.get("quote") or "Public advisory confirms the affected range.",
        }
        for item in payload.get("evidence", [])
        if isinstance(item, dict)
    ] or [
        {
            "field": "fixed_versions",
            "source_type": "web_search",
            "source_url": source_urls[0],
            "quote": "Public advisory confirms the fixed version.",
            "confidence": 0.8,
        }
    ]
    payload["notes"] = "Fake provider generated this deterministic web enrichment response."
    return payload


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _field_from_payload(value: Any, field: str) -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() == field:
                return _clean(item)
            found = _field_from_payload(item, field)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _field_from_payload(item, field)
            if found:
                return found
    return None


def _collect_urls(value: Any) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    if isinstance(value, dict):
        for item in value.values():
            for url in _collect_urls(item):
                if url not in seen:
                    seen.add(url)
                    urls.append(url)
    elif isinstance(value, list):
        for item in value:
            for url in _collect_urls(item):
                if url not in seen:
                    seen.add(url)
                    urls.append(url)
    elif isinstance(value, str):
        for match in re.findall(r"https?://[^\s\"'<>）)]+", value, flags=re.IGNORECASE):
            normalized = match.strip().rstrip(".,;，；。)]}")
            if normalized and normalized not in seen:
                seen.add(normalized)
                urls.append(normalized)
    return urls


def _joined_text(value: Any) -> str:
    chunks: list[str] = []

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
        elif isinstance(item, str):
            chunks.append(item)

    visit(value)
    return " ".join(chunks)


def _quote_for_field(text: str, field: str) -> str:
    if not text:
        return "Existing vulnerability intelligence contains this field."
    if field in {"affected_versions", "fixed_versions", "remediation"}:
        match = re.search(r"[^.。]{0,80}(?:before|prior to|upgrade|fixed|修复|升级)[^.。]{0,120}", text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return text[:180].strip()
