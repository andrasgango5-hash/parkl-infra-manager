from datetime import datetime, timezone

from sqlalchemy import event, inspect
from sqlalchemy.orm import object_session

from app import db

DEVICE_STATUSES = (
    "IN_STOCK",
    "RESERVED",
    "ISSUED",
    "INSTALLED",
    "RETURNED",
    "IN_SERVICE",
    "SCRAPPED",
)

MOVEMENT_TYPES = (
    "INBOUND",
    "RESERVE",
    "ISSUE",
    "INSTALL",
    "RETURN",
    "SERVICE",
    "SCRAP",
    "TRANSFER",
)

DEVICE_CATEGORIES = (
    "EV charger",
    "Parking controller",
    "Barrier gate",
    "Sensor",
    "Energy meter",
    "Network device",
    "Cabinet",
)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    movements = db.relationship("StockMovement", back_populates="created_by")


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    code = db.Column(db.String(60), unique=True, nullable=False, index=True)
    customer = db.Column(db.String(160), default="", nullable=False)
    status = db.Column(db.String(40), default="planned", nullable=False)
    notes = db.Column(db.Text, default="", nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    devices = db.relationship("Device", back_populates="project")
    movements = db.relationship("StockMovement", back_populates="project")
    unassigned_invoice_items = db.relationship(
        "UnassignedInvoiceItem", back_populates="assigned_project"
    )


class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    location_type = db.Column(db.String(40), default="warehouse", nullable=False)
    address = db.Column(db.String(255), default="", nullable=False)
    notes = db.Column(db.Text, default="", nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    devices = db.relationship("Device", back_populates="location")
    outgoing_movements = db.relationship(
        "StockMovement",
        foreign_keys="StockMovement.from_location_id",
        back_populates="from_location",
    )
    incoming_movements = db.relationship(
        "StockMovement",
        foreign_keys="StockMovement.to_location_id",
        back_populates="to_location",
    )


class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_tag = db.Column(db.String(80), unique=True, nullable=False, index=True)
    serial_number = db.Column(db.String(120), default="", nullable=False)
    device_type = db.Column(db.String(80), nullable=False)
    manufacturer = db.Column(db.String(120), default="", nullable=False)
    model = db.Column(db.String(120), default="", nullable=False)
    product_name = db.Column(db.String(160), nullable=True)
    subtype_note = db.Column(db.String(255), nullable=True)
    supplier_manufacturer = db.Column(db.String(160), nullable=True)
    version = db.Column(db.String(80), nullable=True)
    quantity = db.Column(db.Float, nullable=True)
    unit_net_price = db.Column(db.Float, nullable=True)
    currency = db.Column(db.String(12), nullable=True)
    huf_value = db.Column(db.Float, nullable=True)
    assignment_quantity = db.Column(db.Float, nullable=True)
    assignment_notes = db.Column(db.Text, nullable=True)
    order_date = db.Column(db.Date, nullable=True)
    is_ordered = db.Column(db.Boolean, nullable=True)
    planned_arrival_date = db.Column(db.Date, nullable=True)
    actual_arrival_date = db.Column(db.Date, nullable=True)
    has_arrived = db.Column(db.Boolean, nullable=True)
    shipping_cost = db.Column(db.Float, nullable=True)
    shipping_date = db.Column(db.Date, nullable=True)
    supplier_invoice_number = db.Column(db.String(120), nullable=True)
    supplier_invoice_paid = db.Column(db.Boolean, nullable=True)
    invoice_value = db.Column(db.Float, nullable=True)
    shipping_invoice_number = db.Column(db.String(120), nullable=True)
    shipping_invoice_paid = db.Column(db.Boolean, nullable=True)
    status = db.Column(db.String(40), default="IN_STOCK", nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=True)
    location_id = db.Column(db.Integer, db.ForeignKey("location.id"), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    project = db.relationship("Project", back_populates="devices")
    location = db.relationship("Location", back_populates="devices")
    movements = db.relationship(
        "StockMovement", back_populates="device", cascade="all, delete-orphan"
    )
    unassigned_invoice_items = db.relationship(
        "UnassignedInvoiceItem", back_populates="assigned_device"
    )


class StockMovement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey("device.id"), nullable=False)
    movement_type = db.Column(db.String(40), nullable=False)
    from_location_id = db.Column(
        db.Integer, db.ForeignKey("location.id"), nullable=True
    )
    to_location_id = db.Column(db.Integer, db.ForeignKey("location.id"), nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=True)
    notes = db.Column(db.Text, default="", nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    device = db.relationship("Device", back_populates="movements")
    from_location = db.relationship(
        "Location", foreign_keys=[from_location_id], back_populates="outgoing_movements"
    )
    to_location = db.relationship(
        "Location", foreign_keys=[to_location_id], back_populates="incoming_movements"
    )
    project = db.relationship("Project", back_populates="movements")
    created_by = db.relationship("User", back_populates="movements")


class UnassignedInvoiceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(120), nullable=True, index=True)
    partner = db.Column(db.String(160), nullable=True)
    invoice_date = db.Column(db.Date, nullable=True)
    accounting_fulfillment_date = db.Column(db.Date, nullable=True)
    payment_deadline = db.Column(db.Date, nullable=True)
    gross_amount_huf = db.Column(db.Float, nullable=True)
    currency = db.Column(db.String(12), nullable=True)
    description = db.Column(db.Text, nullable=True)
    quantity = db.Column(db.Float, nullable=True)
    unit_price_huf = db.Column(db.Float, nullable=True)
    net_amount_huf = db.Column(db.Float, nullable=True)
    vat_amount_huf = db.Column(db.Float, nullable=True)
    line_gross_amount_huf = db.Column(db.Float, nullable=True)
    assignment_status = db.Column(
        db.String(40), default="unassigned", nullable=False, index=True
    )
    notes = db.Column(db.Text, nullable=True)
    assigned_project_id = db.Column(
        db.Integer, db.ForeignKey("project.id"), nullable=True
    )
    assigned_device_id = db.Column(db.Integer, db.ForeignKey("device.id"), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    assigned_project = db.relationship(
        "Project", back_populates="unassigned_invoice_items"
    )
    assigned_device = db.relationship(
        "Device", back_populates="unassigned_invoice_items"
    )


@event.listens_for(StockMovement, "before_update")
def prevent_stock_movement_update(mapper, connection, target):
    raise ValueError("A StockMovement rekordok nem módosíthatók.")


@event.listens_for(StockMovement, "before_delete")
def prevent_stock_movement_delete(mapper, connection, target):
    raise ValueError("A StockMovement rekordok nem törölhetők.")


@event.listens_for(Device, "before_update")
def prevent_direct_device_status_update(mapper, connection, target):
    status_history = inspect(target).attrs.status.history
    if not status_history.has_changes():
        return

    session = object_session(target)
    has_new_movement = session is not None and any(
        isinstance(item, StockMovement)
        and (item.device is target or item.device_id == target.id)
        for item in session.new
    )
    if not has_new_movement:
        raise ValueError("Az eszköz státusza csak StockMovement létrehozásával változhat.")
