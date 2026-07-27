from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from app.db.models import (
    IntelCollectionRun,
    IntelRawEvent,
    MatchEvidence,
    MatchResult,
    MatchResultHandlingRecord,
    VerificationEvidence,
    VerificationTask,
    Vulnerability,
    VulnerabilityAffectedScope,
    VulnerabilityAIEnrichment,
    VulnerabilityReviewResolution,
    VulnerabilitySource,
)


@dataclass(frozen=True)
class SourceVulnerabilityCleanupStats:
    source_links_deleted: int = 0
    vulnerabilities_deleted: int = 0
    shared_vulnerabilities_retained: int = 0
    raw_events_deleted: int = 0
    collection_runs_deleted: int = 0
    match_results_deleted: int = 0
    verification_tasks_deleted: int = 0
    ai_enrichments_deleted: int = 0
    affected_scopes_deleted: int = 0
    review_resolutions_deleted: int = 0


def clear_source_vulnerabilities(
    db: Session,
    *,
    source_name: str,
) -> SourceVulnerabilityCleanupStats:
    """Remove one source's data while retaining vulnerabilities from other sources."""
    source_filter = _source_name_filter(VulnerabilitySource.source_name, source_name)
    source_links = db.scalars(
        select(VulnerabilitySource).where(source_filter)
    ).all()
    vulnerability_ids = {link.vulnerability_id for link in source_links}
    source_link_ids = [link.id for link in source_links]

    raw_event_ids = _source_raw_event_ids(db, source_name)
    source_links_deleted = _delete_by_ids(db, VulnerabilitySource, source_link_ids)
    db.flush()

    orphan_vulnerability_ids = _orphan_vulnerability_ids(db, vulnerability_ids)
    shared_vulnerabilities_retained = len(vulnerability_ids - orphan_vulnerability_ids)

    affected_scopes_deleted = _delete_source_affected_scopes(
        db,
        source_name=source_name,
        raw_event_ids=raw_event_ids,
    )
    if orphan_vulnerability_ids:
        affected_scopes_deleted += _execute_delete(
            db,
            delete(VulnerabilityAffectedScope).where(
                VulnerabilityAffectedScope.vulnerability_id.in_(orphan_vulnerability_ids)
            ),
        )
        review_resolutions_deleted = _execute_delete(
            db,
            delete(VulnerabilityReviewResolution).where(
                VulnerabilityReviewResolution.vulnerability_id.in_(orphan_vulnerability_ids)
            ),
        )
    else:
        review_resolutions_deleted = 0

    match_result_ids = set(
        db.scalars(
            select(MatchResult.id).where(
                MatchResult.vulnerability_id.in_(orphan_vulnerability_ids)
            )
        ).all()
    ) if orphan_vulnerability_ids else set()
    verification_task_ids = set(
        db.scalars(
            select(VerificationTask.id).where(
                VerificationTask.match_result_id.in_(match_result_ids)
            )
        ).all()
    ) if match_result_ids else set()

    if match_result_ids:
        db.execute(
            delete(VerificationEvidence).where(
                VerificationEvidence.match_result_id.in_(match_result_ids)
            )
        )
        db.execute(
            delete(MatchEvidence).where(MatchEvidence.match_result_id.in_(match_result_ids))
        )
        db.execute(
            delete(MatchResultHandlingRecord).where(
                MatchResultHandlingRecord.match_result_id.in_(match_result_ids)
            )
        )
    if verification_task_ids:
        db.execute(
            update(VerificationTask)
            .where(VerificationTask.id.in_(verification_task_ids))
            .values(previous_task_id=None)
        )
        db.execute(
            delete(VerificationTask).where(VerificationTask.id.in_(verification_task_ids))
        )
    if match_result_ids:
        db.execute(delete(MatchResult).where(MatchResult.id.in_(match_result_ids)))

    ai_enrichments_deleted = 0
    if orphan_vulnerability_ids:
        ai_enrichments_deleted = _execute_delete(
            db,
            delete(VulnerabilityAIEnrichment).where(
                VulnerabilityAIEnrichment.vulnerability_id.in_(orphan_vulnerability_ids)
            ),
        )

    raw_events_deleted = _delete_by_ids(db, IntelRawEvent, raw_event_ids)
    if orphan_vulnerability_ids:
        raw_events_deleted += _execute_delete(
            db,
            delete(IntelRawEvent).where(
                IntelRawEvent.vulnerability_id.in_(orphan_vulnerability_ids)
            ),
        )
        vulnerabilities_deleted = _execute_delete(
            db,
            delete(Vulnerability).where(Vulnerability.id.in_(orphan_vulnerability_ids)),
        )
    else:
        vulnerabilities_deleted = 0

    collection_runs_deleted = _execute_delete(
        db,
        delete(IntelCollectionRun).where(
            _source_name_filter(IntelCollectionRun.source_name, source_name)
        ),
    )
    db.flush()
    return SourceVulnerabilityCleanupStats(
        source_links_deleted=source_links_deleted,
        vulnerabilities_deleted=vulnerabilities_deleted,
        shared_vulnerabilities_retained=shared_vulnerabilities_retained,
        raw_events_deleted=raw_events_deleted,
        collection_runs_deleted=collection_runs_deleted,
        match_results_deleted=len(match_result_ids),
        verification_tasks_deleted=len(verification_task_ids),
        ai_enrichments_deleted=ai_enrichments_deleted,
        affected_scopes_deleted=affected_scopes_deleted,
        review_resolutions_deleted=review_resolutions_deleted,
    )


def _source_name_filter(column, source_name: str):
    if source_name == "watchvuln":
        return or_(column == "watchvuln", column.startswith("watchvuln:"))
    return column == source_name


def _source_raw_event_ids(db: Session, source_name: str) -> list[str]:
    if source_name != "watchvuln" and not source_name.startswith("watchvuln:"):
        return list(
            db.scalars(
                select(IntelRawEvent.id).where(IntelRawEvent.provider == source_name)
            ).all()
        )

    raw_events = db.scalars(
        select(IntelRawEvent).where(IntelRawEvent.provider == "watchvuln")
    ).all()
    return [
        raw_event.id
        for raw_event in raw_events
        if source_name == "watchvuln"
        or _watchvuln_source_name(raw_event.payload) == source_name
    ]


def _watchvuln_source_name(payload: dict | None) -> str | None:
    content = payload.get("content") if isinstance(payload, dict) else None
    if not isinstance(content, dict):
        return None
    source = str(content.get("watchvuln_source") or "").strip().lower()
    if source in {"avd", "aliyun-avd"}:
        source = "avd"
    elif source in {"ti", "nox", "qianxin-ti"}:
        source = "ti"
    elif source in {"struts2", "structs2"}:
        source = "struts2"
    return f"watchvuln:{source}" if source else None


def _delete_source_affected_scopes(
    db: Session,
    *,
    source_name: str,
    raw_event_ids: list[str],
) -> int:
    conditions = [_source_name_filter(VulnerabilityAffectedScope.source_name, source_name)]
    if raw_event_ids:
        conditions.append(VulnerabilityAffectedScope.raw_event_id.in_(raw_event_ids))
    return _execute_delete(
        db,
        delete(VulnerabilityAffectedScope).where(or_(*conditions)),
    )


def _orphan_vulnerability_ids(
    db: Session,
    vulnerability_ids: set[str],
) -> set[str]:
    if not vulnerability_ids:
        return set()
    return set(
        db.scalars(
            select(Vulnerability.id).where(
                Vulnerability.id.in_(vulnerability_ids),
                ~select(VulnerabilitySource.id)
                .where(VulnerabilitySource.vulnerability_id == Vulnerability.id)
                .exists(),
            )
        ).all()
    )


def _delete_by_ids(db: Session, model, ids: list[str]) -> int:
    if not ids:
        return 0
    return _execute_delete(db, delete(model).where(model.id.in_(ids)))


def _execute_delete(db: Session, statement) -> int:
    return int(db.execute(statement).rowcount or 0)
