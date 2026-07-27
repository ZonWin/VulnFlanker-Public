from __future__ import annotations

from app.ai.prompts import (
    build_extract_from_existing_messages,
    build_web_search_messages,
)


def test_existing_data_prompt_requires_strict_candidate_shape() -> None:
    messages = build_extract_from_existing_messages({"vulnerability": {"title": "test"}})
    prompt = "\n".join(message.content for message in messages)

    assert "confidence: number between 0.0 and 1.0" in prompt
    assert 'Do not return confidence labels such as high/medium/low' in prompt
    assert "evidence: array of evidence objects" in prompt
    assert "Do not return evidence as an object" in prompt
    assert "Do not omit required top-level keys" in prompt
    assert "affected_versions as the primary basis for impact matching" in prompt
    assert "Sufficient results must include affected_versions" in prompt
    assert 'return "Balbooa Forms", not\n  "Forms"' in prompt
    assert "backend-parseable version range formats" in prompt
    assert '"before 1.83.14", "prior to 7.9.2"' in prompt
    assert '"4.11 <= Linux Kernel < 5.10.255"' in prompt
    assert "comma-separated version list" in prompt
    assert '"9.1.6, 9.2.3, 12.0.1"' in prompt
    assert "fixed_versions must be null" in prompt
    assert "must start with \"{\" and end with \"}\"" in prompt
    assert "Do not wrap JSON in markdown fences" in prompt


def test_web_prompt_requires_strict_candidate_shape() -> None:
    messages = build_web_search_messages({"vulnerability": {"title": "test"}})
    prompt = "\n".join(message.content for message in messages)

    assert "confidence: number between 0.0 and 1.0" in prompt
    assert 'Do not return confidence labels such as high/medium/low' in prompt
    assert "evidence: array of evidence objects" in prompt
    assert "source_urls: array of strings" in prompt
    assert "affected_versions as the primary basis for impact matching" in prompt
    assert "Sufficient results must include affected_versions" in prompt
    assert "backend-parseable version range formats" in prompt
    assert '"< 1.83.14"' in prompt
    assert "Put explanatory prose in notes instead" in prompt
    assert "comma-separated version list" in prompt
    assert '"9.1.6, 9.2.3, 12.0.1"' in prompt
    assert "fixed_versions must be null" in prompt
    assert "must start with \"{\" and end with \"}\"" in prompt
    assert "Do not wrap JSON in markdown fences" in prompt
