"""Add project drawings

Revision ID: d8e4f2a91c7b
Revises: b6b4db2a2f35
Create Date: 2026-05-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "d8e4f2a91c7b"
down_revision = "b6b4db2a2f35"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "project_drawing",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("background_filename", sa.String(length=255), nullable=True),
        sa.Column("canvas_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_project_drawing_project_id"),
        "project_drawing",
        ["project_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_project_drawing_project_id"), table_name="project_drawing")
    op.drop_table("project_drawing")
