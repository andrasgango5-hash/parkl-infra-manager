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
    "Sticker",
    "Camera",
    "Kiosk",
    "Opener",
    "Router",
    "Parkl box",
    "Other",
)

DEVICE_STATUS_LABELS = {
    "IN_STOCK": "Raktáron",
    "RESERVED": "Előjegyezve",
    "ISSUED": "Kiadva",
    "INSTALLED": "Telepítve",
    "RETURNED": "Visszavéve",
    "IN_SERVICE": "Szervizben",
    "SCRAPPED": "Selejtezve",
}

DEVICE_CATEGORY_LABELS = {
    "EV charger": "EV töltő",
    "Parking controller": "Parkolásvezérlő",
    "Barrier gate": "Sorompó",
    "Sensor": "Szenzor",
    "Energy meter": "Fogyasztásmérő",
    "Network device": "Hálózati eszköz",
    "Cabinet": "Szekrény",
    "Sticker": "Matrica",
    "Camera": "Kamera",
    "Kiosk": "Kioszk",
    "Opener": "Nyitó eszköz",
    "Router": "Router",
    "Parkl box": "Parkl box",
    "Other": "Egyéb",
}


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
    import_batches = db.relationship("ImportBatch", back_populates="imported_by")
    work_orders = db.relationship("WorkOrder", back_populates="created_by")


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
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)

    devices = db.relationship("Device", back_populates="project")
    movements = db.relationship("StockMovement", back_populates="project")
    unassigned_invoice_items = db.relationship(
        "UnassignedInvoiceItem", back_populates="assigned_project"
    )
    drawings = db.relationship(
        "ProjectDrawing", back_populates="project", cascade="all, delete-orphan"
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
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)

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
    vat_rate = db.Column(db.Float, nullable=True)
    qr_mode = db.Column(db.String(20), default="group", nullable=False)
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
    source_sheet = db.Column(db.String(120), nullable=True, index=True)
    import_batch_id = db.Column(db.Integer, db.ForeignKey("import_batch.id"), nullable=True)
    source_row_number = db.Column(db.Integer, nullable=True)
    imported_at = db.Column(db.DateTime(timezone=True), nullable=True)
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
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)

    project = db.relationship("Project", back_populates="devices")
    location = db.relationship("Location", back_populates="devices")
    movements = db.relationship(
        "StockMovement", back_populates="device", cascade="all, delete-orphan"
    )
    unassigned_invoice_items = db.relationship(
        "UnassignedInvoiceItem", back_populates="assigned_device"
    )
    import_batch = db.relationship("ImportBatch", back_populates="devices")
    units = db.relationship(
        "DeviceUnit",
        back_populates="device",
        cascade="all, delete-orphan",
        order_by="DeviceUnit.unit_code",
    )

    @property
    def human_label(self):
        parts = []
        identifier = self.asset_tag or self.serial_number or f"#{self.id}"
        product = self.product_name or self.model
        category = DEVICE_CATEGORY_LABELS.get(self.device_type, self.device_type)
        project_name = None
        if self.project:
            project_name = self.project.code or self.project.name
        status = DEVICE_STATUS_LABELS.get(self.status, self.status)
        location_name = self.location.name if self.location else None

        for value in (identifier, product, category, project_name, status, location_name):
            if value and value not in parts:
                parts.append(value)

        return " – ".join(parts) if parts else f"Eszköz #{self.id}"

    @property
    def display_name(self):
        return self.human_label

    @property
    def total_net_price(self):
        if self.currency not in {"HUF", "EUR"}:
            return None
        if self.quantity is not None and self.unit_net_price is not None:
            return self.quantity * self.unit_net_price
        if self.currency == "HUF" and self.huf_value is not None:
            return self.huf_value
        return None

    @property
    def unit_gross_price(self):
        if (
            self.currency not in {"HUF", "EUR"}
            or self.unit_net_price is None
            or self.vat_rate is None
        ):
            return None
        return self.unit_net_price * (1 + self.vat_rate / 100)

    @property
    def total_gross_price(self):
        if self.total_net_price is None or self.vat_rate is None:
            return None
        return self.total_net_price * (1 + self.vat_rate / 100)


class DeviceUnit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey("device.id"), nullable=False, index=True)
    unit_code = db.Column(db.String(120), unique=True, nullable=False, index=True)
    serial_number = db.Column(db.String(120), nullable=True, index=True)
    asset_tag = db.Column(db.String(80), nullable=True, index=True)
    notes = db.Column(db.Text, nullable=True)
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
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)

    device = db.relationship("Device", back_populates="units")

    @property
    def human_label(self):
        parts = [self.unit_code]
        for value in (
            self.asset_tag,
            self.serial_number,
            self.device.product_name if self.device else None,
        ):
            if value and value not in parts:
                parts.append(value)
        return " – ".join(parts)


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


class ProjectDrawing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    background_filename = db.Column(db.String(255), nullable=True)
    canvas_json = db.Column(db.Text, nullable=True)
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

    project = db.relationship("Project", back_populates="drawings")


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
    source_sheet = db.Column(db.String(120), nullable=True)
    import_batch_id = db.Column(db.Integer, db.ForeignKey("import_batch.id"), nullable=True)
    source_row_number = db.Column(db.Integer, nullable=True)
    imported_at = db.Column(db.DateTime(timezone=True), nullable=True)
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
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)

    assigned_project = db.relationship(
        "Project", back_populates="unassigned_invoice_items"
    )
    assigned_device = db.relationship(
        "Device", back_populates="unassigned_invoice_items"
    )
    import_batch = db.relationship(
        "ImportBatch", back_populates="unassigned_invoice_items"
    )


class ImportBatch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    imported_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    dry_run_summary_json = db.Column(db.Text, nullable=True)
    created_count = db.Column(db.Integer, default=0, nullable=False)
    skipped_count = db.Column(db.Integer, default=0, nullable=False)
    updated_count = db.Column(db.Integer, default=0, nullable=False)
    warning_count = db.Column(db.Integer, default=0, nullable=False)
    status = db.Column(db.String(40), default="completed", nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)

    imported_by = db.relationship("User", back_populates="import_batches")
    devices = db.relationship("Device", back_populates="import_batch")
    unassigned_invoice_items = db.relationship(
        "UnassignedInvoiceItem", back_populates="import_batch"
    )


class WorkOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(80), unique=True, nullable=False, index=True)
    work_type = db.Column(db.String(40), nullable=False, index=True)
    created_date = db.Column(db.Date, nullable=False)
    work_date = db.Column(db.Date, nullable=True, index=True)
    status = db.Column(db.String(40), default="draft", nullable=False, index=True)

    customer_name = db.Column(db.String(160), nullable=True, index=True)
    customer_address = db.Column(db.String(255), nullable=True)
    contact_name = db.Column(db.String(160), nullable=True)
    phone = db.Column(db.String(80), nullable=True)
    email = db.Column(db.String(160), nullable=True)

    site_name = db.Column(db.String(160), nullable=True, index=True)
    site_address = db.Column(db.String(255), nullable=True)
    site_city = db.Column(db.String(120), nullable=True)
    site_notes = db.Column(db.Text, nullable=True)

    device_manufacturer = db.Column(db.String(160), nullable=True)
    device_type = db.Column(db.String(160), nullable=True)
    device_serial_number = db.Column(db.String(160), nullable=True)
    device_purchase_date = db.Column(db.Date, nullable=True)

    arrival_time = db.Column(db.Time, nullable=True)
    departure_time = db.Column(db.Time, nullable=True)
    fault_description = db.Column(db.Text, nullable=True)
    work_performed = db.Column(db.Text, nullable=True)
    labor_settlement = db.Column(db.String(80), nullable=True)
    material_settlement = db.Column(db.String(80), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    technician_name = db.Column(db.String(160), nullable=True, index=True)
    second_technician = db.Column(db.String(160), nullable=True)
    subcontractor = db.Column(db.String(160), nullable=True)
    technician_signature_filename = db.Column(db.String(255), nullable=True)
    customer_signature_filename = db.Column(db.String(255), nullable=True)
    pdf_generated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
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
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)

    created_by = db.relationship("User", back_populates="work_orders")
    materials = db.relationship(
        "WorkOrderMaterial",
        back_populates="work_order",
        cascade="all, delete-orphan",
        order_by="WorkOrderMaterial.id",
    )
    measurements = db.relationship(
        "WorkOrderMeasurement",
        back_populates="work_order",
        cascade="all, delete-orphan",
        order_by="WorkOrderMeasurement.id",
    )
    photos = db.relationship(
        "WorkOrderPhoto",
        back_populates="work_order",
        cascade="all, delete-orphan",
        order_by="WorkOrderPhoto.id",
    )

    @property
    def duration_minutes(self):
        if self.arrival_time is None or self.departure_time is None:
            return None
        start = datetime.combine(datetime.today(), self.arrival_time)
        end = datetime.combine(datetime.today(), self.departure_time)
        if end < start:
            return None
        return int((end - start).total_seconds() // 60)


class WorkOrderMaterial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(db.Integer, db.ForeignKey("work_order.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    item_number = db.Column(db.String(120), nullable=True)
    quantity = db.Column(db.Float, nullable=True)
    unit = db.Column(db.String(40), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    work_order = db.relationship("WorkOrder", back_populates="materials")


class WorkOrderMeasurement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(db.Integer, db.ForeignKey("work_order.id"), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    value = db.Column(db.String(120), nullable=True)
    unit = db.Column(db.String(40), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    work_order = db.relationship("WorkOrder", back_populates="measurements")


class WorkOrderPhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(db.Integer, db.ForeignKey("work_order.id"), nullable=False)
    category = db.Column(db.String(40), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    caption = db.Column(db.String(255), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    work_order = db.relationship("WorkOrder", back_populates="photos")


class WorkOrderTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), unique=True, nullable=False, index=True)
    work_type = db.Column(db.String(40), nullable=True)
    fault_description = db.Column(db.Text, nullable=True)
    work_performed = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    materials_json = db.Column(db.Text, nullable=True)
    measurements_json = db.Column(db.Text, nullable=True)
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
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)


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
