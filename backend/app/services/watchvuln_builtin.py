from __future__ import annotations

import json
import os
import shlex
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import IntelCollectionRun
from app.schemas.intel import WatchVulnWebhookEnvelope
from app.services.intel_ingestion import IngestionStats, ingest_watchvuln_webhook
from app.services.intel_normalization import normalize_raw_event
from app.services.intel_tracking import (
    complete_collection_run,
    create_collection_run,
    fail_collection_run,
)

CommandRunner = Callable[[Sequence[str], int, Path], subprocess.CompletedProcess[str]]

WATCHVULN_SOURCE_LABELS = {
    "avd": "阿里云漏洞库",
    "chaitin": "长亭漏洞库",
    "oscs": "OSCS 开源安全情报预警",
    "ti": "奇安信威胁情报中心",
    "threatbook": "微步在线研究响应中心",
    "seebug": "Seebug 漏洞平台",
    "struts2": "Apache Struts2 Security Bulletins",
    "kev": "CISA KEV",
    "venustech": "启明星辰漏洞通告",
}


def collect_watchvuln_builtin(
    db: Session,
    *,
    limit: int | None = None,
    run_id: str | None = None,
    trigger_type: str = "manual",
    settings: Settings | None = None,
    command_runner: CommandRunner | None = None,
) -> IngestionStats:
    settings = settings or get_settings()
    run = db.get(IntelCollectionRun, run_id) if run_id else None
    parameters = {
        "mode": "builtin",
        "limit": limit,
        "sources": settings.watchvuln_sources,
        "page_limit": settings.watchvuln_page_limit,
        "valuable_only": settings.watchvuln_valuable_only,
    }
    if run is None:
        run = create_collection_run(
            db,
            source_name="watchvuln",
            trigger_type=trigger_type,
            parameters=parameters,
        )
    else:
        run.status = "running"
        run.error_message = None
        run.parameters_json = parameters
        db.add(run)
    db.commit()

    stats = IngestionStats(source_name="watchvuln", run_id=run.id)
    try:
        if settings.watchvuln_collector_command:
            completed = _run_watchvuln_collector(
                settings=settings,
                limit=limit,
                command_runner=command_runner,
            )
            if completed.returncode != 0:
                raise RuntimeError(_format_failed_process(completed))
            _ingest_collector_stdout(db, completed.stdout or "", stats)
        else:
            remaining_limit = limit
            for source in parse_watchvuln_sources(settings.watchvuln_sources):
                if remaining_limit is not None and remaining_limit <= 0:
                    break
                child_stats = _collect_watchvuln_source(
                    db,
                    source=source,
                    parent_run_id=run.id,
                    limit=remaining_limit,
                    trigger_type=trigger_type,
                    settings=settings,
                    command_runner=command_runner,
                )
                stats.fetched_count += child_stats.fetched_count
                stats.stored_count += child_stats.stored_count
                stats.processed_count += child_stats.processed_count
                stats.skipped_count += child_stats.skipped_count
                stats.failed_count += child_stats.failed_count
                if remaining_limit is not None:
                    remaining_limit -= child_stats.fetched_count
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


def parse_watchvuln_sources(sources: str) -> list[str]:
    parsed = []
    for source in sources.split(","):
        normalized = _normalize_watchvuln_source(source)
        if normalized and normalized not in parsed:
            parsed.append(normalized)
    return parsed


def build_watchvuln_collector_command(
    *,
    settings: Settings | None = None,
    limit: int | None = None,
    sources: str | None = None,
) -> list[str]:
    settings = settings or get_settings()
    if settings.watchvuln_collector_command:
        return shlex.split(settings.watchvuln_collector_command)

    collector_path = _collector_path(settings)
    command = [
        str(collector_path),
        "--sources",
        sources or settings.watchvuln_sources,
        "--page-limit",
        str(settings.watchvuln_page_limit),
        "--timeout",
        f"{settings.watchvuln_collector_timeout_seconds}s",
        f"--valuable-only={str(settings.watchvuln_valuable_only).lower()}",
    ]
    if limit is not None:
        command.extend(["--limit", str(limit)])
    if settings.watchvuln_proxy:
        command.extend(["--proxy", settings.watchvuln_proxy])
    if settings.watchvuln_skip_tls_verify:
        command.append("--skip-tls-verify")
    return command


def _collect_watchvuln_source(
    db: Session,
    *,
    source: str,
    parent_run_id: str,
    limit: int | None,
    trigger_type: str,
    settings: Settings,
    command_runner: CommandRunner | None,
) -> IngestionStats:
    run = create_collection_run(
        db,
        source_name=f"watchvuln:{source}",
        trigger_type=trigger_type,
        parameters={
            "mode": "builtin",
            "parent_run_id": parent_run_id,
            "limit": limit,
            "sources": source,
            "page_limit": settings.watchvuln_page_limit,
            "valuable_only": settings.watchvuln_valuable_only,
        },
    )
    db.commit()
    stats = IngestionStats(source_name=f"watchvuln:{source}", run_id=run.id)
    try:
        completed = _run_watchvuln_collector(
            settings=settings,
            limit=limit,
            sources=source,
            command_runner=command_runner,
        )
        if completed.returncode != 0:
            raise RuntimeError(_format_failed_process(completed))
        _ingest_collector_stdout(db, completed.stdout or "", stats, default_source=source)
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


def _run_watchvuln_collector(
    *,
    settings: Settings,
    limit: int | None,
    sources: str | None = None,
    command_runner: CommandRunner | None = None,
) -> subprocess.CompletedProcess[str]:
    command = build_watchvuln_collector_command(
        settings=settings,
        limit=limit,
        sources=sources,
    )
    runner = command_runner or _run_command
    try:
        return runner(
            command,
            settings.watchvuln_collector_timeout_seconds,
            _repo_root(),
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "内置 WatchVuln collector 不存在，请先构建 bin/watchvuln-collector，"
            "或配置 VULNFLANKER_WATCHVULN_COLLECTOR_COMMAND。"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("内置 WatchVuln collector 执行超时。") from exc


def _run_command(
    command: Sequence[str],
    timeout_seconds: int,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=str(cwd),
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )


def _ingest_collector_stdout(
    db: Session,
    stdout: str,
    stats: IngestionStats,
    *,
    default_source: str | None = None,
) -> None:
    for line_number, line in enumerate(stdout.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        stats.fetched_count += 1
        try:
            payload = json.loads(line)
            if default_source and isinstance(payload, dict):
                content = payload.get("content")
                if isinstance(content, dict) and not content.get("watchvuln_source"):
                    content["watchvuln_source"] = default_source
                    content["watchvuln_source_display_name"] = WATCHVULN_SOURCE_LABELS.get(
                        default_source,
                        default_source,
                    )
            envelope = WatchVulnWebhookEnvelope.model_validate(payload)
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            stats.failed_count += 1
            raise RuntimeError(f"WatchVuln collector 第 {line_number} 行输出不是有效事件。") from exc

        raw_event, created = ingest_watchvuln_webhook(db, envelope)
        if created:
            stats.stored_count += 1
        if not created and raw_event.processing_status != "pending":
            stats.skipped_count += 1
            continue

        result = normalize_raw_event(db, raw_event)
        if result.status == "processed":
            stats.processed_count += 1
        else:
            stats.skipped_count += 1


def _format_failed_process(completed: subprocess.CompletedProcess[str]) -> str:
    output = (completed.stderr or completed.stdout or "").strip()
    if len(output) > 1000:
        output = output[-1000:]
    command_text = " ".join(str(arg) for arg in completed.args)
    if not output:
        return f"内置 WatchVuln collector 执行失败，退出码 {completed.returncode}: {command_text}"
    return f"内置 WatchVuln collector 执行失败，退出码 {completed.returncode}: {output}"


def _collector_path(settings: Settings) -> Path:
    if settings.watchvuln_collector_path:
        path = Path(settings.watchvuln_collector_path)
    else:
        binary_name = "watchvuln-collector.exe" if os.name == "nt" else "watchvuln-collector"
        path = Path("bin") / binary_name
    if path.is_absolute():
        return path
    return _repo_root() / path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _normalize_watchvuln_source(source: str) -> str:
    normalized = source.strip().lower()
    if normalized in {"aliyun-avd", "avd"}:
        return "avd"
    if normalized in {"qianxin-ti", "nox", "ti"}:
        return "ti"
    if normalized in {"structs2", "struts2"}:
        return "struts2"
    if normalized in WATCHVULN_SOURCE_LABELS:
        return normalized
    return normalized
