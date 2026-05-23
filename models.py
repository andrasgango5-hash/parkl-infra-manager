from datetime import datetime, timezone

from app import db


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
    status = db.Column(db.String(40), default="unassigned", nullable=False)
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
