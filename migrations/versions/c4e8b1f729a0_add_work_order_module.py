"""Add work order module

Revision ID: c4e8b1f729a0
Revises: a2c7e51b8d90
Create Date: 2026-06-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c4e8b1f729a0"
down_revision = "a2c7e51b8d90"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "work_order_template",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("work_type", sa.String(length=40), nullable=True),
        sa.Column("fault_description", sa.Text(), nullable=True),
        sa.Column("work_performed", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("materials_json", sa.Text(), nullable=True),
        sa.Column("measurements_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_work_order_template_name"), "work_order_template", ["name"], unique=True)

    op.create_table(
        "work_order",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("number", sa.String(length=80), nullable=False),
        sa.Column("work_type", sa.String(length=40), nullable=False),
        sa.Column("created_date", sa.Date(), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("customer_name", sa.String(length=160), nullable=True),
        sa.Column("customer_address", sa.String(length=255), nullable=True),
        sa.Column("contact_name", sa.String(length=160), nullable=True),
        sa.Column("phone", sa.String(length=80), nullable=True),
        sa.Column("email", sa.String(length=160), nullable=True),
        sa.Column("site_name", sa.String(length=160), nullable=True),
        sa.Column("site_address", sa.String(length=255), nullable=True),
        sa.Column("site_city", sa.String(length=120), nullable=True),
        sa.Column("site_notes", sa.Text(), nullable=True),
        sa.Column("device_manufacturer", sa.String(length=160), nullable=True),
        sa.Column("device_type", sa.String(length=160), nullable=True),
        sa.Column("device_serial_number", sa.String(length=160), nullable=True),
        sa.Column("device_purchase_date", sa.Date(), nullable=True),
        sa.Column("arrival_time", sa.Time(), nullable=True),
        sa.Column("departure_time", sa.Time(), nullable=True),
        sa.Column("fault_description", sa.Text(), nullable=True),
        sa.Column("work_performed", sa.Text(), nullable=True),
        sa.Column("labor_settlement", sa.String(length=80), nullable=True),
        sa.Column("material_settlement", sa.String(length=80), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("technician_name", sa.String(length=160), nullable=True),
        sa.Column("second_technician", sa.String(length=160), nullable=True),
        sa.Column("subcontractor", sa.String(length=160), nullable=True),
        sa.Column("technician_signature_filename", sa.String(length=255), nullable=True),
        sa.Column("customer_signature_filename", sa.String(length=255), nullable=True),
        sa.Column("pdf_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_work_order_number"), "work_order", ["number"], unique=True)
    op.create_index(op.f("ix_work_order_work_type"), "work_order", ["work_type"], unique=False)
    op.create_index(op.f("ix_work_order_work_date"), "work_order", ["work_date"], unique=False)
    op.create_index(op.f("ix_work_order_status"), "work_order", ["status"], unique=False)
    op.create_index(op.f("ix_work_order_customer_name"), "work_order", ["customer_name"], unique=False)
    op.create_index(op.f("ix_work_order_site_name"), "work_order", ["site_name"], unique=False)
    op.create_index(op.f("ix_work_order_technician_name"), "work_order", ["technician_name"], unique=False)

    op.create_table(
        "work_order_material",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("item_number", sa.String(length=120), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_order.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "work_order_measurement",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("value", sa.String(length=120), nullable=True),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_order.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "work_order_photo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("caption", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_order.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("work_order_photo")
    op.drop_table("work_order_measurement")
    op.drop_table("work_order_material")
    op.drop_index(op.f("ix_work_order_technician_name"), table_name="work_order")
    op.drop_index(op.f("ix_work_order_site_name"), table_name="work_order")
    op.drop_index(op.f("ix_work_order_customer_name"), table_name="work_order")
    op.drop_index(op.f("ix_work_order_status"), table_name="work_order")
    op.drop_index(op.f("ix_work_order_work_date"), table_name="work_order")
    op.drop_index(op.f("ix_work_order_work_type"), table_name="work_order")
    op.drop_index(op.f("ix_work_order_number"), table_name="work_order")
    op.drop_table("work_order")
    op.drop_index(op.f("ix_work_order_template_name"), table_name="work_order_template")
    op.drop_table("work_order_template")
