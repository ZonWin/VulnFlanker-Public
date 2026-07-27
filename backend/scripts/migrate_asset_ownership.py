from __future__ import annotations

import argparse
import json

from app.db.session import SessionLocal
from app.services.ownership_migration import migrate_legacy_asset_ownership


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize legacy asset ownership text into structured master data."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and print the migration report, then roll back all changes.",
    )
    args = parser.parse_args()
    with SessionLocal() as db:
        report = migrate_legacy_asset_ownership(db, commit=not args.dry_run)
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
