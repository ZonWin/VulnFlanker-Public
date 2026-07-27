"""strip watchvuln canonical prefix

Revision ID: d4e5f60718a9
Revises: c3d4e5f60718
Create Date: 2026-07-13 00:00:00.000000
"""

from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "d4e5f60718a9"
down_revision = "c3d4e5f60718"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE vulnerabilities AS vuln
        SET canonical_id = substring(vuln.canonical_id from 11)
        WHERE vuln.canonical_id LIKE 'WATCHVULN:%'
          AND NOT EXISTS (
            SELECT 1
            FROM vulnerabilities AS existing
            WHERE existing.canonical_id = substring(vuln.canonical_id from 11)
              AND existing.id <> vuln.id
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE vulnerabilities AS vuln
        SET canonical_id = 'WATCHVULN:' || vuln.canonical_id
        WHERE vuln.canonical_id NOT LIKE 'WATCHVULN:%'
          AND EXISTS (
            SELECT 1
            FROM vulnerability_sources AS source
            WHERE source.vulnerability_id = vuln.id
              AND source.source_name LIKE 'watchvuln%'
              AND source.external_id = vuln.canonical_id
          )
          AND NOT EXISTS (
            SELECT 1
            FROM vulnerabilities AS existing
            WHERE existing.canonical_id = 'WATCHVULN:' || vuln.canonical_id
              AND existing.id <> vuln.id
          )
        """
    )
