from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.request import Request, urlopen

from app.connectors.base import RawIntelRecord, VulnerabilitySourceConnector
from app.core.config import get_settings
from app.db.base import utcnow


CVE_RECORD_URL_TEMPLATE = "https://cveawg.mitre.org/api/cve/{cve_id}"
CVE_RECORD_PAGE_TEMPLATE = "https://www.cve.org/CVERecord?id={cve_id}"

def _split_notes(notes: str | None) -> list[str]:
    if not notes:
        return []
    return [part.strip() for part in notes.split(";") if part.strip()]


class CisaKevConnector(VulnerabilitySourceConnector):
    source_name = "cisa-kev"

    def __init__(
        self,
        feed_url: str | None = None,
        catalog_url: str | None = None,
        cve_record_url_template: str | None = None,
        cve_record_fetch: bool | None = None,
        cve_record_workers: int | None = None,
        timeout: int = 30,
    ) -> None:
        settings = get_settings()
        self.feed_url = feed_url or settings.cisa_kev_feed_url
        self.catalog_url = catalog_url or settings.cisa_kev_catalog_url
        self.cve_record_url_template = (
            cve_record_url_template or settings.cisa_kev_cve_record_url_template
        )
        self.cve_record_fetch = (
            settings.cisa_kev_cve_record_fetch
            if cve_record_fetch is None
            else cve_record_fetch
        )
        self.cve_record_workers = (
            cve_record_workers or settings.cisa_kev_cve_record_workers
        )
        self.timeout = timeout

    def fetch_catalog(self) -> dict[str, Any]:
        request = Request(
            self.feed_url,
            headers={
                "Accept": "application/json",
                "Referer": self.catalog_url,
                "User-Agent": "VulnFlanker/0.1",
            },
        )
        with urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def fetch_cve_record(self, cve_id: str) -> dict[str, Any] | None:
        url = self.cve_record_url_template.format(cve_id=cve_id)
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "Referer": self.catalog_url,
                "User-Agent": "VulnFlanker/0.1",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            # CVE Record enrichment is supplementary: a transient upstream
            # failure must not prevent the authoritative CISA KEV record from
            # entering the catalog.
            return None
        return payload if isinstance(payload, dict) else None

    def fetch(
        self,
        limit: int | None = None,
        latest_only: bool = False,
        known_after_date: str | None = None,
        known_external_ids: set[str] | None = None,
    ) -> list[RawIntelRecord]:
        catalog = self.fetch_catalog()
        fetched_at = utcnow()
        vulnerabilities = sorted(
            catalog.get("vulnerabilities", []),
            key=lambda item: str(item.get("dateAdded") or ""),
            reverse=True,
        )
        if latest_only:
            vulnerabilities = _filter_latest_vulnerabilities(
                vulnerabilities,
                known_after_date=known_after_date,
                known_external_ids=known_external_ids or set(),
            )
        if limit is not None:
            vulnerabilities = vulnerabilities[:limit]

        cve_ids = [
            str(item.get("cveID") or "").strip()
            for item in vulnerabilities
            if str(item.get("cveID") or "").strip()
        ]
        cve_records = self._fetch_cve_records(cve_ids)

        records: list[RawIntelRecord] = []
        for item in vulnerabilities:
            cve_id = str(item.get("cveID") or "").strip()
            if not cve_id:
                continue

            cve_record = cve_records.get(cve_id)
            references = _split_notes(str(item.get("notes") or ""))
            cve_record_page = CVE_RECORD_PAGE_TEMPLATE.format(cve_id=cve_id)
            if cve_record and cve_record_page not in references:
                references.append(cve_record_page)

            records.append(
                RawIntelRecord(
                    source_name=self.source_name,
                    external_id=cve_id,
                    title=str(item.get("vulnerabilityName") or cve_id).strip(),
                    payload={
                        "catalog_version": catalog.get("catalogVersion"),
                        "date_released": catalog.get("dateReleased"),
                        "record": item,
                        **(
                            {
                                "cve_record": cve_record,
                                "cve_record_url": cve_record_page,
                            }
                            if cve_record
                            else {}
                        ),
                    },
                    fetched_at=fetched_at,
                    references=references,
                    event_type="cisa-kev-vulnerability",
                    source_url=self.catalog_url,
                )
            )

        return records

    def _fetch_cve_records(self, cve_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not self.cve_record_fetch or not cve_ids:
            return {}

        details: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=max(1, self.cve_record_workers)) as executor:
            futures = {
                executor.submit(self.fetch_cve_record, cve_id): cve_id
                for cve_id in cve_ids
            }
            for future in as_completed(futures):
                cve_id = futures[future]
                try:
                    record = future.result()
                except Exception:
                    continue
                if record:
                    details[cve_id] = record
        return details


def _filter_latest_vulnerabilities(
    vulnerabilities: list[dict[str, Any]],
    *,
    known_after_date: str | None,
    known_external_ids: set[str],
) -> list[dict[str, Any]]:
    if not known_after_date:
        return vulnerabilities

    filtered: list[dict[str, Any]] = []
    for item in vulnerabilities:
        date_added = str(item.get("dateAdded") or "").strip()
        cve_id = str(item.get("cveID") or "").strip()
        if date_added > known_after_date:
            filtered.append(item)
        elif date_added == known_after_date and cve_id and cve_id not in known_external_ids:
            filtered.append(item)
    return filtered
