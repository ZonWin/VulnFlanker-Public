from __future__ import annotations

import html
import json
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

from app.connectors.base import RawIntelRecord, VulnerabilitySourceConnector
from app.core.config import get_settings
from app.db.base import utcnow


ALIYUN_AVD_EVENT_TYPE = "aliyun-avd-high-risk"
DETAIL_URL_TEMPLATE = "https://avd.aliyun.com/detail?id={avd_id}"

_AVD_ID_RE = re.compile(r"AVD-\d{4}-[A-Za-z0-9._-]+", re.IGNORECASE)
_CVE_ID_RE = re.compile(r"CVE-\d{4}-\d{4,}", re.IGNORECASE)
_DATE_RE = re.compile(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:\s+\d{1,2}:\d{1,2}:\d{1,2})?")
_SCORE_RE = re.compile(r"(?<!\d)(10(?:\.0)?|[0-9](?:\.[0-9])?)(?!\d)")
_URL_RE = re.compile(r"https?://[^\s\"'<>]+")


class AliyunAvdConnector(VulnerabilitySourceConnector):
    source_name = "aliyun-avd"

    def __init__(
        self,
        high_risk_url: str | None = None,
        detail_url_template: str = DETAIL_URL_TEMPLATE,
        timeout: int = 30,
        max_pages: int = 10,
        detail_fetch: bool = True,
    ) -> None:
        settings = get_settings()
        self.high_risk_url = high_risk_url or settings.aliyun_avd_high_risk_url
        self.detail_url_template = detail_url_template
        self.timeout = timeout
        self.max_pages = max_pages
        self.detail_fetch = detail_fetch

    def fetch(self, limit: int | None = None, min_score: float | None = None) -> list[RawIntelRecord]:
        fetched_at = utcnow()
        records: list[RawIntelRecord] = []
        seen: set[str] = set()

        for page in range(1, self.max_pages + 1):
            page_html = self.fetch_list_page(page)
            if _looks_like_waf_challenge(page_html):
                raise RuntimeError("阿里云 AVD 返回了访问校验页，未能获取漏洞列表。")
            page_records = parse_avd_list_html(
                page_html,
                base_url=self.high_risk_url,
            )
            if not page_records:
                break

            for item in page_records:
                avd_id = _clean_text(item.get("avd_id"))
                if not avd_id or avd_id in seen:
                    continue
                seen.add(avd_id)

                score = _to_float(item.get("score"))
                if min_score is not None and score is not None and score < min_score:
                    continue

                if self.detail_fetch and self._needs_detail(item, min_score):
                    item = _merge_records(item, self.fetch_detail(avd_id))

                score = _to_float(item.get("score"))
                if min_score is not None and (score is None or score < min_score):
                    continue

                normalized = _normalize_record(item, avd_id)
                title = normalized.get("title") or normalized.get("cve_id") or avd_id
                records.append(
                    RawIntelRecord(
                        source_name=self.source_name,
                        external_id=avd_id,
                        title=title,
                        payload={
                            "source": "high-risk-list",
                            "record": normalized,
                        },
                        fetched_at=fetched_at,
                        references=normalized["references"],
                        event_type=ALIYUN_AVD_EVENT_TYPE,
                        source_url=normalized.get("source_url"),
                    )
                )

                if limit is not None and len(records) >= limit:
                    return records

        return records

    def fetch_list_page(self, page: int = 1) -> str:
        return self._fetch_text(_with_page(self.high_risk_url, page))

    def fetch_detail_page(self, avd_id: str) -> str:
        return self._fetch_text(self.detail_url_template.format(avd_id=avd_id))

    def fetch_detail(self, avd_id: str) -> dict[str, Any]:
        detail_html = self.fetch_detail_page(avd_id)
        if _looks_like_waf_challenge(detail_html):
            return {}
        return parse_avd_detail_html(
            detail_html,
            source_url=self.detail_url_template.format(avd_id=avd_id),
        )

    def _fetch_text(self, url: str) -> str:
        request = Request(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": "https://avd.aliyun.com/",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36 VulnFlanker/0.1"
                ),
            },
        )
        with urlopen(request, timeout=self.timeout) as response:
            return response.read().decode("utf-8", errors="replace")

    @staticmethod
    def _needs_detail(item: dict[str, Any], min_score: float | None) -> bool:
        if min_score is not None and _to_float(item.get("score")) is None:
            return True
        return any(
            not _clean_text(item.get(field_name))
            for field_name in ("description", "remediation", "product")
        )


def parse_avd_list_html(html_text: str, base_url: str = "https://avd.aliyun.com/") -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for payload in _iter_json_payloads(html_text):
        for item in _iter_dicts(payload):
            record = _record_from_mapping(item, base_url)
            if record is not None:
                records.append(record)

    records.extend(_record_from_links(html_text, base_url))
    return _dedupe_records(records)


def parse_avd_detail_html(
    html_text: str,
    source_url: str | None = None,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for payload in _iter_json_payloads(html_text):
        for item in _iter_dicts(payload):
            record = _record_from_mapping(item, source_url or "https://avd.aliyun.com/")
            if record is not None:
                records.append(record)

    text = _html_to_text(html_text)
    detail: dict[str, Any] = {}
    avd_id = _first_match(_AVD_ID_RE, text)
    if avd_id:
        detail["avd_id"] = avd_id
    cve_id = _first_match(_CVE_ID_RE, text)
    if cve_id:
        detail["cve_id"] = cve_id

    title = _label_value(text, "漏洞名称", "标题", "名称")
    if title:
        detail["title"] = title
    severity = _label_value(text, "漏洞评级", "风险等级", "危害等级", "漏洞等级")
    if severity:
        detail["severity"] = severity
    score = _label_value(text, "漏洞评分", "CVSS评分", "CVSS Score", "CVSS")
    if score:
        detail["score"] = score
    product = _label_value(text, "影响产品", "受影响产品", "产品")
    if product:
        detail["product"] = product
    affected = _label_value(text, "影响版本", "受影响版本", "影响范围")
    if affected:
        detail["affected_versions"] = affected
    description = _label_value(text, "漏洞描述", "漏洞详情", "漏洞简介")
    if description:
        detail["description"] = description
    remediation = _label_value(text, "修复建议", "解决建议", "解决方案")
    if remediation:
        detail["remediation"] = remediation
    published_at = _label_value(text, "披露时间", "公开时间", "发布时间", "更新时间")
    if published_at:
        detail["published_at"] = published_at

    references = _extract_links(html_text)
    if references:
        detail["references"] = references
    if source_url:
        detail["source_url"] = source_url

    if records:
        return _merge_records(records[0], detail)
    return detail


def _with_page(url: str, page: int) -> str:
    if page <= 1:
        return url
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["page"] = str(page)
    return urlunparse(parsed._replace(query=urlencode(query)))


def _looks_like_waf_challenge(html_text: str) -> bool:
    return "_waf_" in html_text and "renderData" in html_text and "AVD-" not in html_text


def _iter_json_payloads(html_text: str) -> list[Any]:
    payloads: list[Any] = []
    for pattern in (
        r"<script[^>]*>(?P<body>.*?)</script>",
        r"<textarea[^>]*>(?P<body>.*?)</textarea>",
    ):
        for match in re.finditer(pattern, html_text, flags=re.IGNORECASE | re.DOTALL):
            body = html.unescape(match.group("body")).strip()
            if "AVD-" not in body:
                continue
            parsed = _load_json_fragment(body)
            if parsed is not None:
                payloads.append(parsed)
    return payloads


def _load_json_fragment(value: str) -> Any | None:
    candidates = [value]
    object_match = re.search(r"({.*})", value, flags=re.DOTALL)
    array_match = re.search(r"(\[.*\])", value, flags=re.DOTALL)
    if object_match:
        candidates.append(object_match.group(1))
    if array_match:
        candidates.append(array_match.group(1))

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _iter_dicts(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        nested = [value]
        for item in value.values():
            nested.extend(_iter_dicts(item))
        return nested
    if isinstance(value, list):
        nested: list[dict[str, Any]] = []
        for item in value:
            nested.extend(_iter_dicts(item))
        return nested
    return []


def _record_from_mapping(item: dict[str, Any], base_url: str) -> dict[str, Any] | None:
    avd_id = _find_first_value(item, "avd_id", "avdId", "avdNo", "avd_no", "avd", "id")
    if not _looks_like_avd(avd_id):
        avd_id = _find_pattern_in_value(item, _AVD_ID_RE)
    if not avd_id:
        return None

    source_url = _find_first_value(item, "url", "link", "href", "source_url", "detailUrl")
    if source_url and not str(source_url).startswith("http"):
        source_url = urljoin(base_url, str(source_url))
    if not source_url:
        source_url = DETAIL_URL_TEMPLATE.format(avd_id=avd_id)

    record = {
        "avd_id": avd_id,
        "title": _find_first_value(
            item,
            "title",
            "name",
            "vulnName",
            "vulnerabilityName",
            "vuln_name",
        ),
        "cve_id": _find_first_value(item, "cve", "cveId", "cve_id", "cveNo", "cve_no"),
        "severity": _find_first_value(
            item,
            "severity",
            "riskLevel",
            "risk_level",
            "level",
            "grade",
        ),
        "score": _find_first_value(
            item,
            "score",
            "cvss",
            "cvssScore",
            "cvss_score",
            "baseScore",
            "base_score",
        ),
        "published_at": _find_first_value(
            item,
            "published_at",
            "publishTime",
            "publish_time",
            "publishDate",
            "disclosureTime",
            "disclosure_time",
            "gmtCreate",
            "gmt_create",
            "updateTime",
            "update_time",
        ),
        "vendor": _find_first_value(item, "vendor", "vendorProject", "vendor_project"),
        "product": _find_first_value(item, "product", "affectedProduct", "affected_product"),
        "description": _find_first_value(item, "description", "desc", "summary", "detail"),
        "affected_versions": _find_first_value(
            item,
            "affected_versions",
            "affectedVersion",
            "affected_version",
            "influence",
            "scope",
        ),
        "fixed_versions": _find_first_value(item, "fixed_versions", "fixedVersion", "fixed_version"),
        "remediation": _find_first_value(item, "remediation", "solution", "suggestion", "repair"),
        "source_url": source_url,
        "references": _extract_links(item),
        "tags": _extract_tags(item),
    }
    return _normalize_record(record, avd_id)


def _record_from_links(html_text: str, base_url: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    link_pattern = re.compile(
        r"<a[^>]+href=[\"'](?P<href>[^\"']*detail\?id=(?P<id>AVD-\d{4}-[^\"'&#]+)[^\"']*)[\"'][^>]*>"
        r"(?P<title>.*?)</a>",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in link_pattern.finditer(html_text):
        avd_id = match.group("id")
        context = _html_to_text(
            html_text[max(0, match.start() - 1000) : min(len(html_text), match.end() + 1000)]
        )
        record = {
            "avd_id": avd_id,
            "title": _html_to_text(match.group("title")) or _title_from_context(context, avd_id),
            "cve_id": _first_match(_CVE_ID_RE, context),
            "severity": _severity_from_text(context),
            "score": _score_from_text(context),
            "published_at": _first_match(_DATE_RE, context),
            "source_url": urljoin(base_url, html.unescape(match.group("href"))),
            "references": _extract_links(match.group(0)),
            "tags": ["high-risk"],
        }
        records.append(_normalize_record(record, avd_id))
    return records


def _normalize_record(item: dict[str, Any], avd_id: str) -> dict[str, Any]:
    cve_id = _normalize_cve(_clean_text(item.get("cve_id")) or _find_pattern_in_value(item, _CVE_ID_RE))
    references = _as_list(item.get("references"))
    source_url = _clean_text(item.get("source_url")) or DETAIL_URL_TEMPLATE.format(avd_id=avd_id)
    tags = _as_list(item.get("tags"))
    if "high-risk" not in tags:
        tags.append("high-risk")
    if item.get("severity") and str(item["severity"]) not in tags:
        tags.append(str(item["severity"]))

    return {
        "avd_id": avd_id,
        "title": _clean_text(item.get("title")) or cve_id or avd_id,
        "cve_id": cve_id,
        "severity": _clean_text(item.get("severity")),
        "score": _to_float(item.get("score")),
        "published_at": _clean_text(item.get("published_at")),
        "vendor": _clean_text(item.get("vendor")),
        "product": _clean_text(item.get("product")),
        "description": _clean_text(item.get("description")),
        "affected_versions": _clean_text(item.get("affected_versions")),
        "fixed_versions": _clean_text(item.get("fixed_versions")),
        "remediation": _clean_text(item.get("remediation")),
        "source_url": source_url,
        "references": references,
        "tags": tags,
    }


def _merge_records(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    merged = dict(primary)
    for key, value in secondary.items():
        if key in {"references", "tags"}:
            merged[key] = _merge_lists(merged.get(key), value)
        elif value not in (None, "", []):
            merged[key] = value
    return merged


def _dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for record in records:
        avd_id = _clean_text(record.get("avd_id"))
        if not avd_id:
            continue
        if avd_id in deduped:
            deduped[avd_id] = _merge_records(deduped[avd_id], record)
        else:
            deduped[avd_id] = record
    return list(deduped.values())


def _find_first_value(item: dict[str, Any], *field_names: str) -> Any | None:
    for field_name in field_names:
        if field_name in item and item[field_name] not in (None, "", []):
            return item[field_name]
    lowered = {key.lower(): value for key, value in item.items()}
    for field_name in field_names:
        value = lowered.get(field_name.lower())
        if value not in (None, "", []):
            return value
    return None


def _find_pattern_in_value(value: Any, pattern: re.Pattern[str]) -> str | None:
    if isinstance(value, dict):
        for item in value.values():
            matched = _find_pattern_in_value(item, pattern)
            if matched:
                return matched
    elif isinstance(value, list):
        for item in value:
            matched = _find_pattern_in_value(item, pattern)
            if matched:
                return matched
    elif value is not None:
        return _first_match(pattern, str(value))
    return None


def _extract_links(value: Any) -> list[str]:
    links: list[str] = []
    if isinstance(value, dict):
        for item in value.values():
            links.extend(_extract_links(item))
    elif isinstance(value, list):
        for item in value:
            links.extend(_extract_links(item))
    elif value is not None:
        text = html.unescape(str(value))
        links.extend(match.rstrip(".,;") for match in _URL_RE.findall(text))
    return list(dict.fromkeys(links))


def _extract_tags(item: dict[str, Any]) -> list[str]:
    tags = _as_list(_find_first_value(item, "tags", "tag", "labels", "label"))
    severity = _find_first_value(item, "severity", "riskLevel", "risk_level", "level", "grade")
    if severity:
        tags.append(str(severity))
    return list(dict.fromkeys(tag for tag in tags if tag))


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_cleaned for item in value if (_cleaned := _clean_text(item))]
    if isinstance(value, tuple | set):
        return [_cleaned for item in value if (_cleaned := _clean_text(item))]
    text = _clean_text(value)
    if not text:
        return []
    return [part.strip() for part in re.split(r"[;,，；]\s*", text) if part.strip()]


def _merge_lists(first: Any, second: Any) -> list[str]:
    merged = _as_list(first) + _as_list(second)
    return list(dict.fromkeys(merged))


def _html_to_text(html_text: str) -> str:
    without_scripts = re.sub(
        r"<(script|style)[^>]*>.*?</\1>",
        "\n",
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    block_spaced = re.sub(
        r"</?(?:tr|td|th|div|p|li|br|dt|dd|h[1-6]|section|article)[^>]*>",
        "\n",
        without_scripts,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"<[^>]+>", " ", block_spaced)
    lines = [re.sub(r"\s+", " ", html.unescape(line)).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _label_value(text: str, *labels: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        for label in labels:
            if label not in line:
                continue
            suffix = line.split(label, 1)[1].lstrip(":： \t")
            if suffix:
                return suffix
            if index + 1 < len(lines):
                return lines[index + 1]
    return None


def _title_from_context(context: str, avd_id: str) -> str | None:
    for line in context.splitlines():
        if avd_id in line:
            title = line.replace(avd_id, "").strip(" -:：")
            return title or None
    return None


def _severity_from_text(text: str) -> str | None:
    for severity in ("严重", "高危", "中危", "低危", "critical", "high", "medium", "low"):
        if severity.lower() in text.lower():
            return severity
    return None


def _score_from_text(text: str) -> float | None:
    for line in text.splitlines():
        if any(keyword in line.lower() for keyword in ("cvss", "评分", "score")):
            score = _to_float(line)
            if score is not None:
                return score
    return None


def _to_float(value: Any) -> float | None:
    if isinstance(value, int | float):
        score = float(value)
    else:
        text = _clean_text(value)
        if text is None:
            return None
        match = _SCORE_RE.search(text)
        if not match:
            return None
        score = float(match.group(1))
    if 0 <= score <= 10:
        return score
    return None


def _normalize_cve(value: str | None) -> str | None:
    if not value:
        return None
    match = _CVE_ID_RE.search(value)
    return match.group(0).upper() if match else None


def _looks_like_avd(value: Any) -> bool:
    return bool(value and _AVD_ID_RE.fullmatch(str(value).strip()))


def _first_match(pattern: re.Pattern[str], value: str) -> str | None:
    match = pattern.search(value)
    return match.group(0) if match else None


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list | tuple | set):
        return ", ".join(str(item).strip() for item in value if str(item).strip()) or None
    text = html.unescape(str(value)).strip()
    return re.sub(r"\s+", " ", text) or None
