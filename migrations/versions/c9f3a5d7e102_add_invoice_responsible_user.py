"""add responsible user to invoice clarification items

Revision ID: c9f3a5d7e102
Revises: b8e2f4c6d901
Create Date: 2026-06-07
"""

import sqlalchemy as sa
from alembic import op


revision = "c9f3a5d7e102"
down_revision = "b8e2f4c6d901"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("unassigned_invoice_item", schema=None) as batch_op:
        batch_op.add_column(sa.Column("responsible_user_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_unassigned_invoice_item_responsible_user_id"),
            ["responsible_user_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "fk_unassigned_invoice_item_responsible_user_id_user",
            "user",
            ["responsible_user_id"],
            ["id"],
        )


def downgrade():
    with op.batch_alter_table("unassigned_invoice_item", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_unassigned_invoice_item_responsible_user_id_user",
            type_="foreignkey",
        )
        batch_op.drop_index(
            batch_op.f("ix_unassigned_invoice_item_responsible_user_id")
        )
        batch_op.drop_column("responsible_user_id")

