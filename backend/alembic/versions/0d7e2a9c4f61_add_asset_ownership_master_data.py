"""add asset ownership master data

Revision ID: 0d7e2a9c4f61
Revises: fc39a7b1d0e2
Create Date: 2026-07-20 16:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0d7e2a9c4f61"
down_revision = "fc39a7b1d0e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "responsibility_teams",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_responsibility_teams_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_responsibility_teams_code"),
        "responsibility_teams",
        ["code"],
        unique=True,
    )
    op.create_index(
        op.f("ix_responsibility_teams_normalized_name"),
        "responsibility_teams",
        ["normalized_name"],
        unique=True,
    )
    op.create_index(
        op.f("ix_responsibility_teams_status"),
        "responsibility_teams",
        ["status"],
        unique=False,
    )

    op.create_table(
        "people",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("employee_no", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("team_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_people_status",
        ),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["responsibility_teams.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_people_email"), "people", ["email"], unique=False)
    op.create_index(
        op.f("ix_people_employee_no"),
        "people",
        ["employee_no"],
        unique=True,
    )
    op.create_index(op.f("ix_people_name"), "people", ["name"], unique=False)
    op.create_index(op.f("ix_people_status"), "people", ["status"], unique=False)
    op.create_index(op.f("ix_people_team_id"), "people", ["team_id"], unique=False)

    op.create_table(
        "business_systems",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("responsible_person_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'inactive')",
            name="ck_business_systems_status",
        ),
        sa.ForeignKeyConstraint(
            ["responsible_person_id"],
            ["people.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_business_systems_code"),
        "business_systems",
        ["code"],
        unique=True,
    )
    op.create_index(
        op.f("ix_business_systems_normalized_name"),
        "business_systems",
        ["normalized_name"],
        unique=True,
    )
    op.create_index(
        op.f("ix_business_systems_responsible_person_id"),
        "business_systems",
        ["responsible_person_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_business_systems_status"),
        "business_systems",
        ["status"],
        unique=False,
    )

    op.add_column(
        "assets",
        sa.Column("business_system_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "assets",
        sa.Column("ownership_source", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "assets",
        sa.Column("ownership_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_assets_business_system_id"),
        "assets",
        ["business_system_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_assets_business_system_id_business_systems",
        "assets",
        "business_systems",
        ["business_system_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_assets_business_system_id_business_systems",
        "assets",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_assets_business_system_id"), table_name="assets")
    op.drop_column("assets", "ownership_updated_at")
    op.drop_column("assets", "ownership_source")
    op.drop_column("assets", "business_system_id")

    op.drop_index(
        op.f("ix_business_systems_status"),
        table_name="business_systems",
    )
    op.drop_index(
        op.f("ix_business_systems_responsible_person_id"),
        table_name="business_systems",
    )
    op.drop_index(
        op.f("ix_business_systems_normalized_name"),
        table_name="business_systems",
    )
    op.drop_index(
        op.f("ix_business_systems_code"),
        table_name="business_systems",
    )
    op.drop_table("business_systems")

    op.drop_index(op.f("ix_people_team_id"), table_name="people")
    op.drop_index(op.f("ix_people_status"), table_name="people")
    op.drop_index(op.f("ix_people_name"), table_name="people")
    op.drop_index(op.f("ix_people_employee_no"), table_name="people")
    op.drop_index(op.f("ix_people_email"), table_name="people")
    op.drop_table("people")

    op.drop_index(
        op.f("ix_responsibility_teams_status"),
        table_name="responsibility_teams",
    )
    op.drop_index(
        op.f("ix_responsibility_teams_normalized_name"),
        table_name="responsibility_teams",
    )
    op.drop_index(
        op.f("ix_responsibility_teams_code"),
        table_name="responsibility_teams",
    )
    op.drop_table("responsibility_teams")
