from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
TESTS_ROOT = BACKEND_ROOT / "tests"
for path in (BACKEND_ROOT, TESTS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from ai_enrichment_eval.dataset import load_ai_enrichment_eval_dataset
from ai_enrichment_eval.runner import run_ai_enrichment_eval
from app.db.base import Base
from app.db.models import AIProfile, PlatformSettings
from app.services.ai_completion import encode_api_key


DEFAULT_BASE_URL = "https://api.moonshot.cn/v1"


def main() -> int:
    args = _parse_args()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    Base.metadata.create_all(bind=engine)

    with session_factory() as db:
        _seed_platform_settings(db)
        if args.provider_mode == "openai_compatible":
            _seed_openai_compatible_profile(db, args)

        report = run_ai_enrichment_eval(
            db,
            load_ai_enrichment_eval_dataset(),
            profile_key=args.profile_key,
            provider_mode=args.provider_mode,
            limit=args.limit,
            sample_ids=set(args.sample_id) if args.sample_id else None,
        )

    payload = report.to_dict()
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialized + "\n", encoding="utf-8")
    if not args.quiet:
        print(serialized)
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run S3-Q3.5 AI enrichment evaluation against fixture samples."
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--sample-id",
        action="append",
        default=[],
        help="Run only the selected sample id. Can be passed multiple times.",
    )
    parser.add_argument(
        "--provider-mode",
        choices=("fake", "openai_compatible"),
        default="fake",
    )
    parser.add_argument(
        "--profile-key",
        default="basic_extraction_profile",
        help="AI profile key used by the enrichment service.",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("KIMI_BASE_URL", DEFAULT_BASE_URL),
        help="OpenAI-compatible base URL for real model experiments.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("KIMI_MODEL"),
        help="Model name for real model experiments. Required for openai_compatible.",
    )
    parser.add_argument(
        "--api-key-env",
        default="KIMI_API_KEY",
        help="Environment variable containing the API key.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=float(os.getenv("KIMI_TEMPERATURE", "1.0")),
        help="Temperature for real model experiments. Kimi k2.5 currently requires 1.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=int(os.getenv("KIMI_MAX_TOKENS", "4096")),
        help="Maximum completion tokens for real model experiments.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path for writing a JSON report.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout when --output is used.",
    )
    return parser.parse_args()


def _seed_platform_settings(db) -> None:
    db.add(
        PlatformSettings(
            id="default",
            ai_enabled=True,
            ai_auto_enrich_enabled=False,
            ai_auto_accept_enabled=False,
            ai_auto_accept_confidence=0.85,
            ai_layer2_daily_limit=100,
            ai_batch_max_size=100,
            ai_allow_web_enrichment_default=False,
        )
    )
    db.commit()


def _seed_openai_compatible_profile(db, args: argparse.Namespace) -> None:
    if not args.model:
        raise SystemExit("--model or KIMI_MODEL is required for openai_compatible mode.")
    api_key = os.getenv(args.api_key_env)
    if not api_key:
        raise SystemExit(
            f"{args.api_key_env} is required for openai_compatible mode."
        )
    profile = AIProfile(
        profile_key=args.profile_key,
        display_name="S3-Q3.5 real model eval",
        provider="openai_compatible",
        model_vendor="kimi",
        base_url=args.base_url,
        api_key_ciphertext=encode_api_key(api_key),
        model=args.model,
        enabled=True,
        supports_web_search=False,
        allow_external_network=True,
        json_mode=True,
        timeout_seconds=120,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
    )
    db.add(profile)
    db.commit()


if __name__ == "__main__":
    raise SystemExit(main())
