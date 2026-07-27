from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.aliyun_avd import AliyunAvdConnector
from app.connectors.base import RawIntelRecord, VulnerabilitySourceConnector
from app.connectors.cisa_kev import CisaKevConnector
from app.db.models import IntelCollectionRun, IntelRawEvent
from app.schemas.intel import WatchVulnWebhookEnvelope
from app.services.intel_normalization import normalize_raw_event

CISA_KEV_LATEST_INITIAL_LIMIT = 100


@dataclass(slots=True)
class IngestionStats:
    source_name: str
    run_id: str | None = None
    fetched_count: int = 0
    stored_count: int = 0
    processed_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    status: str = "completed"
    error_message: str | None = None


def collect_cisa_kev(
    db: Session,
    limit: int | None = None,
    connector: CisaKevConnector | None = None,
    run_id: str | None = None,
    trigger_type: str = "manual",
    latest_only: bool = False,
) -> IngestionStats:
    connector = connector or CisaKevConnector()
    effective_limit = _normalize_limit(limit)
    effective_latest_only = latest_only and limit != 0
    fetch_kwargs: dict[str, Any] = {"latest_only": effective_latest_only}
    if effective_latest_only:
        watermark = _cisa_kev_latest_watermark(db)
        fetch_kwargs.update(
            {
                "known_after_date": watermark[0],
                "known_external_ids": watermark[1],
            }
        )
        if watermark[0] is None and effective_limit is None:
            effective_limit = CISA_KEV_LATEST_INITIAL_LIMIT
    return _collect_connector(
        db,
        connector=connector,
        limit=effective_limit,
        run_id=run_id,
        trigger_type=trigger_type,
        fetch_kwargs=fetch_kwargs,
        parameters={"limit": effective_limit, "latest_only": effective_latest_only},
    )


def collect_aliyun_avd(
    db: Session,
    limit: int | None = None,
    min_score: float | None = None,
    connector: AliyunAvdConnector | None = None,
    run_id: str | None = None,
    trigger_type: str = "manual",
) -> IngestionStats:
    connector = connector or AliyunAvdConnector()
    effective_limit = _normalize_limit(limit)
    return _collect_connector(
        db,
        connector=connector,
        limit=effective_limit,
        run_id=run_id,
        trigger_type=trigger_type,
        fetch_kwargs={"min_score": min_score},
        parameters={"limit": effective_limit, "min_score": min_score},
    )


def _collect_connector(
    db: Session,
    *,
    connector: VulnerabilitySourceConnector,
    limit: int | None = None,
    run_id: str | None = None,
    trigger_type: str = "manual",
    fetch_kwargs: dict[str, Any] | None = None,
    parameters: dict[str, Any] | None = None,
) -> IngestionStats:
    from app.services.intel_tracking import (
        complete_collection_run,
        create_collection_run,
        fail_collection_run,
    )

    run = db.get(IntelCollectionRun, run_id) if run_id else None
    if run is None:
        run = create_collection_run(
            db,
            source_name=connector.source_name,
            trigger_type=trigger_type,
            parameters=parameters or {"limit": limit},
        )
    else:
        run.status = "running"
        run.error_message = None
        db.add(run)
    db.commit()

    try:
        records = connector.fetch(limit=limit, **(fetch_kwargs or {}))
        stats = IngestionStats(
            source_name=connector.source_name,
            run_id=run.id,
            fetched_count=len(records),
        )

        for record in records:
            raw_event, created = ingest_connector_record(db, record)
            if created:
                stats.stored_count += 1
            try:
                result = normalize_raw_event(db, raw_event)
            except Exception:
                stats.failed_count += 1
                raise
            if result.status == "processed":
                stats.processed_count += 1
            else:
                stats.skipped_count += 1

        complete_collection_run(
            db,
            run,
            fetched_count=stats.fetched_count,
            stored_count=stats.stored_count,
            processed_count=stats.processed_count,
            skipped_count=stats.skipped_count,
            failed_count=stats.failed_count,
        )
        db.commit()
        return stats
    except Exception as exc:
        fail_collection_run(db, run, exc)
        db.commit()
        raise


def ingest_connector_record(db: Session, record: RawIntelRecord) -> tuple[IntelRawEvent, bool]:
    return store_raw_event(
        db,
        provider=record.source_name,
        event_type=record.event_type,
        external_key=record.external_id,
        payload=record.payload,
        source_url=record.source_url,
        dedupe_by_external_key=record.source_name == "cisa-kev",
    )


def ingest_watchvuln_webhook(
    db: Session,
    envelope: WatchVulnWebhookEnvelope,
) -> tuple[IntelRawEvent, bool]:
    payload = envelope.model_dump(mode="json", by_alias=True)
    content = payload.get("content", {})
    payload_hash = compute_payload_hash(payload)
    external_key = _derive_watchvuln_external_key(envelope.type, content, payload_hash)
    source_url = None
    if isinstance(content, dict):
        source_url = _clean_text(content.get("from"))

    return store_raw_event(
        db,
        provider="watchvuln",
        event_type=envelope.type,
        external_key=external_key,
        payload=payload,
        source_url=source_url,
    )


def store_raw_event(
    db: Session,
    *,
    provider: str,
    event_type: str,
    external_key: str,
    payload: dict[str, Any],
    source_url: str | None = None,
    dedupe_by_external_key: bool = False,
) -> tuple[IntelRawEvent, bool]:
    payload_hash = compute_payload_hash(payload)
    if dedupe_by_external_key:
        existing_by_key = db.scalar(
            select(IntelRawEvent)
            .where(
                IntelRawEvent.provider == provider,
                IntelRawEvent.external_key == external_key,
            )
            .order_by(IntelRawEvent.received_at.desc(), IntelRawEvent.created_at.desc())
        )
        if existing_by_key is not None:
            if existing_by_key.payload_hash != payload_hash:
                existing_by_key.event_type = event_type
                existing_by_key.source_url = source_url or existing_by_key.source_url
                existing_by_key.payload = payload
                existing_by_key.payload_hash = payload_hash
                existing_by_key.processing_status = "pending"
                existing_by_key.last_error = None
                db.add(existing_by_key)
                db.commit()
                db.refresh(existing_by_key)
            return existing_by_key, False

    existing = db.scalar(
        select(IntelRawEvent).where(
            IntelRawEvent.provider == provider,
            IntelRawEvent.payload_hash == payload_hash,
        )
    )
    if existing is not None:
        return existing, False

    raw_event = IntelRawEvent(
        provider=provider,
        event_type=event_type,
        external_key=external_key,
        source_url=source_url,
        payload=payload,
        payload_hash=payload_hash,
        processing_status="pending",
    )
    db.add(raw_event)
    db.commit()
    db.refresh(raw_event)
    return raw_event, True


def compute_payload_hash(payload: Any) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _derive_watchvuln_external_key(
    event_type: str,
    content: dict[str, Any],
    payload_hash: str,
) -> str:
    if event_type == "watchvuln-vulninfo":
        for field_name in ("unique_key", "cve", "title"):
            value = _clean_text(content.get(field_name))
            if value:
                return value
    return f"{event_type}:{payload_hash[:16]}"


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_limit(limit: int | None) -> int | None:
    if limit == 0:
        return None
    return limit


def _cisa_kev_latest_watermark(db: Session) -> tuple[str | None, set[str]]:
    raw_events = db.scalars(
        select(IntelRawEvent).where(IntelRawEvent.provider == "cisa-kev")
    ).all()
    latest_date: str | None = None
    external_ids: set[str] = set()

    for raw_event in raw_events:
        external_key = _clean_text(raw_event.external_key)
        if external_key:
            external_ids.add(external_key)

        payload = raw_event.payload if isinstance(raw_event.payload, dict) else {}
        record = payload.get("record")
        if not isinstance(record, dict):
            continue
        date_added = _clean_text(record.get("dateAdded"))
        if date_added and (latest_date is None or date_added > latest_date):
            latest_date = date_added

    return latest_date, external_ids
