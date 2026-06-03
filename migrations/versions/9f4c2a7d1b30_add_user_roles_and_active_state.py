"""add user roles and active state

Revision ID: 9f4c2a7d1b30
Revises: e7c4a9d2b1f0
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa


revision = "9f4c2a7d1b30"
down_revision = "e7c4a9d2b1f0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(
            sa.Column("role", sa.String(length=20), nullable=False, server_default="viewer")
        )
        batch_op.add_column(
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch_op.create_index("ix_user_role", ["role"], unique=False)
        batch_op.create_index("ix_user_is_active", ["is_active"], unique=False)

    op.execute("UPDATE user SET role = 'admin' WHERE is_admin = 1")
    op.execute("UPDATE user SET role = 'viewer' WHERE is_admin = 0 OR is_admin IS NULL")


def downgrade():
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_index("ix_user_is_active")
        batch_op.drop_index("ix_user_role")
        batch_op.drop_column("is_active")
        batch_op.drop_column("role")
