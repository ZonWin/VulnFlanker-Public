from __future__ import annotations

import re
from typing import Iterable


CANONICAL_SEVERITY_LABELS = ("critical", "high", "medium", "low", "info")

KNOWN_EXPLOITED_MARKERS = {
    "knownexploited",
    "knownexploitedvulnerability",
    "knownexploitedvulnerabilities",
    "kev",
    "cisakev",
    "已知利用",
    "已知被利用",
    "已知存在利用",
    "已知有利用",
}

KNOWN_EXPLOITED_QUERY_VALUES = {
    "known_exploited",
    "known-exploited",
    "known exploited",
    "known exploited vulnerability",
    "known exploited vulnerabilities",
    "kev",
    "cisa kev",
    "cisa-kev",
    "已知利用",
    "已知被利用",
    "已知存在利用",
    "已知有利用",
}

EMPTY_SEVERITY_MARKERS = {
    "unknown",
    "unk",
    "none",
    "null",
    "na",
    "n/a",
    "-",
    "未知",
    "不详",
    "暂无",
    "无",
}

SEVERITY_ALIASES: dict[str, tuple[str, ...]] = {
    "critical": (
        "critical",
        "crit",
        "severe",
        "serious",
        "严重",
        "超危",
        "严重 / critical",
        "critical / 严重",
        "严重critical",
        "critical严重",
    ),
    "high": (
        "high",
        "important",
        "高",
        "高危",
        "高风险",
        "highrisk",
        "高危 / high",
        "high / 高危",
        "高危high",
        "high高危",
    ),
    "medium": (
        "medium",
        "moderate",
        "中",
        "中危",
        "中风险",
        "mediumrisk",
        "中危 / medium",
        "medium / 中危",
        "中危medium",
        "medium中危",
    ),
    "low": (
        "low",
        "低",
        "低危",
        "低风险",
        "lowrisk",
        "低危 / low",
        "low / 低危",
        "低危low",
        "low低危",
    ),
    "info": (
        "info",
        "informational",
        "information",
        "信息",
        "提示",
        "信息 / info",
        "info / 信息",
        "信息info",
        "info信息",
    ),
}

_ALIAS_TO_CANONICAL = {
    alias: canonical
    for canonical, aliases in SEVERITY_ALIASES.items()
    for alias in aliases
}


def normalize_severity_label(value: object | None) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None

    key = _compact_key(text)
    if (
        key in KNOWN_EXPLOITED_MARKERS
        or key in EMPTY_SEVERITY_MARKERS
        or text.lower() in EMPTY_SEVERITY_MARKERS
    ):
        return None
    return _ALIAS_TO_CANONICAL.get(key, text.lower())


def is_known_exploited_marker(value: object | None) -> bool:
    text = _clean_text(value)
    return bool(text and _compact_key(text) in KNOWN_EXPLOITED_MARKERS)


def severity_query_values(labels: Iterable[object]) -> set[str]:
    values: set[str] = set()
    for label in labels:
        text = _clean_text(label)
        if text is None or is_known_exploited_marker(text):
            continue

        normalized = normalize_severity_label(text)
        if normalized is None:
            continue

        aliases = SEVERITY_ALIASES.get(normalized)
        if aliases is None:
            values.add(text.lower())
            continue

        values.update(alias.lower() for alias in aliases)
        values.add(normalized)
    return values


def _clean_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _compact_key(value: str) -> str:
    return re.sub(r"[\s/_\-.]+", "", value.strip().lower())
