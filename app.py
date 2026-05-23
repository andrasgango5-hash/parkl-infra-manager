from functools import wraps
from datetime import date, datetime, timezone
import os

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config

db = SQLAlchemy()
migrate = Migrate()

STATUS_LABELS = {
    "IN_STOCK": "Raktáron",
    "RESERVED": "Előjegyezve",
    "ISSUED": "Kiadva",
    "INSTALLED": "Telepítve",
    "RETURNED": "Visszavéve",
    "IN_SERVICE": "Szervizben",
    "SCRAPPED": "Selejtezve",
}

MOVEMENT_TYPE_LABELS = {
    "INBOUND": "Bevételezés",
    "RESERVE": "Előjegyzés",
    "ISSUE": "Kiadás",
    "INSTALL": "Telepítés",
    "RETURN": "Visszavétel",
    "SERVICE": "Szervizbe küldés",
    "SCRAP": "Selejtezés",
    "TRANSFER": "Áthelyezés",
}

CATEGORY_LABELS = {
    "EV charger": "EV töltő",
    "Parking controller": "Parkolásvezérlő",
    "Barrier gate": "Sorompó",
    "Sensor": "Szenzor",
    "Energy meter": "Fogyasztásmérő",
    "Network device": "Hálózati eszköz",
    "Cabinet": "Szekrény",
}

LOCATION_TYPE_LABELS = {
    "warehouse": "Raktár",
    "project_site": "Projekt helyszín",
    "service_vehicle": "Szervizautó",
    "installed": "Telepített helyszín",
    "supplier": "Beszállító",
}

PROJECT_STATUS_LABELS = {
    "planned": "Tervezett",
    "active": "Aktív",
    "handover": "Átadás alatt",
    "completed": "Lezárt",
}

ASSIGNMENT_STATUS_LABELS = {
    "unassigned": "Nincs hozzárendelve",
    "assigned": "Hozzárendelve",
    "ignored": "Nem releváns",
}


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)

    from models import (
        DEVICE_CATEGORIES,
        DEVICE_STATUSES,
        MOVEMENT_TYPES,
        Device,
        Location,
        Project,
        StockMovement,
        UnassignedInvoiceItem,
        User,
    )

    @app.context_processor
    def inject_current_user():
        user = None
        if session.get("user_id"):
            user = db.session.get(User, session["user_id"])
        return {
            "current_user": user,
            "status_label": status_label,
            "movement_type_label": movement_type_label,
            "category_label": category_label,
            "location_type_label": location_type_label,
            "project_status_label": project_status_label,
            "assignment_status_label": assignment_status_label,
            "yes_no_label": yes_no_label,
            "format_number": format_number,
        }

    def login_required(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if not session.get("user_id"):
                flash("A folytatáshoz jelentkezz be.", "warning")
                return redirect(url_for("login"))
            return view(*args, **kwargs)

        return wrapped_view

    @app.cli.command("seed-admin")
    def seed_admin():
        """Create or update the default admin user."""
        username = app.config["ADMIN_USERNAME"]
        password = app.config["ADMIN_PASSWORD"]
        user = User.query.filter_by(username=username).first()
        if user is None:
            user = User(
                username=username,
                password_hash=generate_password_hash(password),
                is_admin=True,
            )
            db.session.add(user)
            action = "Létrehozva"
        else:
            user.password_hash = generate_password_hash(password)
            user.is_admin = True
            action = "Frissítve"
        db.session.commit()
        print(f"{action}: '{username}' admin felhasználó.")

    @app.route("/")
    def index():
        if session.get("user_id"):
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password_hash, password):
                session.clear()
                session["user_id"] = user.id
                flash("Sikeres bejelentkezés.", "success")
                return redirect(url_for("dashboard"))
            flash("Hibás felhasználónév vagy jelszó.", "danger")
        return render_template("login.html")

    @app.route("/logout", methods=["POST"])
    @login_required
    def logout():
        session.clear()
        flash("Kijelentkeztél.", "info")
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        stats = {
            "projects": Project.query.count(),
            "devices": Device.query.count(),
            "locations": Location.query.count(),
            "movements": StockMovement.query.count(),
        }
        recent_movements = (
            StockMovement.query.order_by(StockMovement.created_at.desc()).limit(6).all()
        )
        return render_template(
            "dashboard.html", stats=stats, recent_movements=recent_movements
        )

    @app.route("/projects", methods=["GET", "POST"])
    @login_required
    def projects():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            code = request.form.get("code", "").strip()
            customer = request.form.get("customer", "").strip()
            status = request.form.get("status", "planned").strip() or "planned"
            notes = request.form.get("notes", "").strip()
            if not name or not code:
                flash("A projekt neve és kódja kötelező.", "danger")
            elif Project.query.filter_by(code=code).first():
                flash("Ezzel a kóddal már létezik projekt.", "danger")
            else:
                db.session.add(
                    Project(
                        name=name,
                        code=code,
                        customer=customer,
                        status=status,
                        notes=notes,
                    )
                )
                db.session.commit()
                flash("A projekt létrejött.", "success")
                return redirect(url_for("projects"))

        project_list = Project.query.order_by(Project.created_at.desc()).all()
        return render_template("projects.html", projects=project_list)

    @app.route("/devices", methods=["GET", "POST"])
    @login_required
    def devices():
        projects = Project.query.order_by(Project.name.asc()).all()
        locations = Location.query.order_by(Location.name.asc()).all()
        selected_status = request.args.get("status", "").strip()
        selected_category = request.args.get("category", "").strip()
        if request.method == "POST":
            asset_tag = request.form.get("asset_tag", "").strip()
            serial_number = request.form.get("serial_number", "").strip()
            device_type = request.form.get("device_type", "").strip()
            manufacturer = request.form.get("manufacturer", "").strip()
            model = request.form.get("model", "").strip()
            product_name = request.form.get("product_name", "").strip()
            subtype_note = request.form.get("subtype_note", "").strip()
            supplier_manufacturer = request.form.get("supplier_manufacturer", "").strip()
            version = request.form.get("version", "").strip()
            quantity = optional_float(request.form.get("quantity"))
            unit_net_price = optional_float(request.form.get("unit_net_price"))
            currency = request.form.get("currency", "").strip().upper() or None
            huf_value = optional_float(request.form.get("huf_value"))
            assignment_quantity = optional_float(request.form.get("assignment_quantity"))
            assignment_notes = request.form.get("assignment_notes", "").strip()
            order_date = optional_date(request.form.get("order_date"))
            is_ordered = checkbox_value(request.form.get("is_ordered"))
            planned_arrival_date = optional_date(request.form.get("planned_arrival_date"))
            actual_arrival_date = optional_date(request.form.get("actual_arrival_date"))
            has_arrived = checkbox_value(request.form.get("has_arrived"))
            shipping_cost = optional_float(request.form.get("shipping_cost"))
            shipping_date = optional_date(request.form.get("shipping_date"))
            supplier_invoice_number = request.form.get("supplier_invoice_number", "").strip()
            supplier_invoice_paid = checkbox_value(request.form.get("supplier_invoice_paid"))
            invoice_value = optional_float(request.form.get("invoice_value"))
            shipping_invoice_number = request.form.get("shipping_invoice_number", "").strip()
            shipping_invoice_paid = checkbox_value(request.form.get("shipping_invoice_paid"))
            project_id = optional_int(request.form.get("project_id"))
            location_id = optional_int(request.form.get("location_id"))

            if not asset_tag or not device_type:
                flash("Az eszközazonosító és a kategória kötelező.", "danger")
            elif device_type not in DEVICE_CATEGORIES:
                flash("Érvénytelen eszközkategória.", "danger")
            elif Device.query.filter_by(asset_tag=asset_tag).first():
                flash("Ezzel az eszközazonosítóval már létezik eszköz.", "danger")
            else:
                device = Device(
                    asset_tag=asset_tag,
                    serial_number=serial_number,
                    device_type=device_type,
                    manufacturer=manufacturer,
                    model=model,
                    product_name=product_name or None,
                    subtype_note=subtype_note or None,
                    supplier_manufacturer=supplier_manufacturer or None,
                    version=version or None,
                    quantity=quantity,
                    unit_net_price=unit_net_price,
                    currency=currency,
                    huf_value=huf_value
                    if huf_value is not None
                    else calculate_huf_value(quantity, unit_net_price, currency),
                    assignment_quantity=assignment_quantity,
                    assignment_notes=assignment_notes or None,
                    order_date=order_date,
                    is_ordered=is_ordered,
                    planned_arrival_date=planned_arrival_date,
                    actual_arrival_date=actual_arrival_date,
                    has_arrived=has_arrived,
                    shipping_cost=shipping_cost,
                    shipping_date=shipping_date,
                    supplier_invoice_number=supplier_invoice_number or None,
                    supplier_invoice_paid=supplier_invoice_paid,
                    invoice_value=invoice_value,
                    shipping_invoice_number=shipping_invoice_number or None,
                    shipping_invoice_paid=shipping_invoice_paid,
                    project_id=project_id,
                    location_id=location_id,
                    status="IN_STOCK",
                )
                db.session.add(device)
                db.session.flush()
                create_movement(
                    device=device,
                    movement_type="INBOUND",
                    to_location_id=location_id,
                    project_id=project_id,
                    notes="Kezdeti eszközrögzítés.",
                    user_id=session["user_id"],
                )
                db.session.commit()
                flash("Az eszköz létrejött, a készletmozgás rögzítve.", "success")
                return redirect(url_for("devices"))

        device_query = Device.query
        if selected_status in DEVICE_STATUSES:
            device_query = device_query.filter(Device.status == selected_status)
        if selected_category in DEVICE_CATEGORIES:
            device_query = device_query.filter(Device.device_type == selected_category)

        device_list = device_query.order_by(Device.created_at.desc()).all()
        return render_template(
            "devices.html",
            devices=device_list,
            projects=projects,
            locations=locations,
            statuses=DEVICE_STATUSES,
            categories=DEVICE_CATEGORIES,
            selected_status=selected_status,
            selected_category=selected_category,
        )

    @app.route("/unassigned-invoices", methods=["GET", "POST"])
    @login_required
    def unassigned_invoices():
        projects = Project.query.order_by(Project.name.asc()).all()
        devices = Device.query.order_by(Device.asset_tag.asc()).all()
        selected_assignment_status = request.args.get("assignment_status", "").strip()

        if request.method == "POST":
            invoice_number = request.form.get("invoice_number", "").strip()
            partner = request.form.get("partner", "").strip()
            description = request.form.get("description", "").strip()
            assigned_project_id = optional_int(request.form.get("assigned_project_id"))
            assigned_device_id = optional_int(request.form.get("assigned_device_id"))
            assignment_status = request.form.get(
                "assignment_status", "unassigned"
            ).strip()
            if assignment_status not in ASSIGNMENT_STATUS_LABELS:
                assignment_status = "unassigned"
            if assigned_project_id or assigned_device_id:
                assignment_status = "assigned"

            if not invoice_number and not description:
                flash("A számlaszám vagy a megnevezés megadása kötelező.", "danger")
            else:
                invoice_item = UnassignedInvoiceItem(
                    invoice_number=invoice_number or None,
                    partner=partner or None,
                    invoice_date=optional_date(request.form.get("invoice_date")),
                    accounting_fulfillment_date=optional_date(
                        request.form.get("accounting_fulfillment_date")
                    ),
                    payment_deadline=optional_date(request.form.get("payment_deadline")),
                    gross_amount_huf=optional_float(request.form.get("gross_amount_huf")),
                    currency=request.form.get("currency", "").strip().upper() or None,
                    description=description or None,
                    quantity=optional_float(request.form.get("quantity")),
                    unit_price_huf=optional_float(request.form.get("unit_price_huf")),
                    net_amount_huf=optional_float(request.form.get("net_amount_huf")),
                    vat_amount_huf=optional_float(request.form.get("vat_amount_huf")),
                    line_gross_amount_huf=optional_float(
                        request.form.get("line_gross_amount_huf")
                    ),
                    assignment_status=assignment_status,
                    notes=request.form.get("notes", "").strip() or None,
                    assigned_project_id=assigned_project_id,
                    assigned_device_id=assigned_device_id,
                )
                db.session.add(invoice_item)
                db.session.commit()
                flash("A gazdátlan számlasor létrejött.", "success")
                return redirect(url_for("unassigned_invoices"))

        invoice_query = UnassignedInvoiceItem.query
        if selected_assignment_status in ASSIGNMENT_STATUS_LABELS:
            invoice_query = invoice_query.filter(
                UnassignedInvoiceItem.assignment_status
                == selected_assignment_status
            )
        invoice_items = invoice_query.order_by(
            UnassignedInvoiceItem.created_at.desc()
        ).all()
        return render_template(
            "unassigned_invoices.html",
            invoice_items=invoice_items,
            projects=projects,
            devices=devices,
            assignment_statuses=ASSIGNMENT_STATUS_LABELS,
            selected_assignment_status=selected_assignment_status,
        )

    @app.route("/locations", methods=["GET", "POST"])
    @login_required
    def locations():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            location_type = request.form.get("location_type", "warehouse").strip()
            address = request.form.get("address", "").strip()
            notes = request.form.get("notes", "").strip()
            if not name:
                flash("A készlethely neve kötelező.", "danger")
            else:
                db.session.add(
                    Location(
                        name=name,
                        location_type=location_type,
                        address=address,
                        notes=notes,
                    )
                )
                db.session.commit()
                flash("A készlethely létrejött.", "success")
                return redirect(url_for("locations"))

        location_list = Location.query.order_by(Location.name.asc()).all()
        return render_template("locations.html", locations=location_list)

    @app.route("/movements", methods=["GET", "POST"])
    @login_required
    def movements():
        devices = Device.query.order_by(Device.asset_tag.asc()).all()
        locations = Location.query.order_by(Location.name.asc()).all()
        projects = Project.query.order_by(Project.name.asc()).all()

        if request.method == "POST":
            device_id = optional_int(request.form.get("device_id"))
            movement_type = request.form.get("movement_type", "").strip()
            from_location_id = optional_int(request.form.get("from_location_id"))
            to_location_id = optional_int(request.form.get("to_location_id"))
            project_id = optional_int(request.form.get("project_id"))
            notes = request.form.get("notes", "").strip()

            device = db.session.get(Device, device_id) if device_id else None
            if device is None or not movement_type:
                flash("Az eszköz és a mozgástípus kötelező.", "danger")
            else:
                error = validate_movement(device, movement_type)
                if error:
                    flash(error, "danger")
                else:
                    create_movement(
                        device=device,
                        movement_type=movement_type,
                        from_location_id=from_location_id,
                        to_location_id=to_location_id,
                        project_id=project_id,
                        notes=notes,
                        user_id=session["user_id"],
                    )
                    apply_device_state(
                        device, movement_type, to_location_id, project_id
                    )
                    db.session.commit()
                    flash("A készletmozgás rögzítve.", "success")
                    return redirect(url_for("movements"))

        movement_list = StockMovement.query.order_by(
            StockMovement.created_at.desc()
        ).all()
        return render_template(
            "movements.html",
            movements=movement_list,
            devices=devices,
            locations=locations,
            projects=projects,
            movement_types=MOVEMENT_TYPES,
        )

    return app


def optional_int(value):
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def optional_float(value):
    if value in (None, ""):
        return None
    normalized = str(value).strip().replace(" ", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return None


def optional_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def checkbox_value(value):
    return True if value == "on" else False


def calculate_huf_value(quantity, unit_net_price, currency):
    if currency == "HUF" and quantity is not None and unit_net_price is not None:
        return quantity * unit_net_price
    return None


def status_label(value):
    return STATUS_LABELS.get(value, value)


def movement_type_label(value):
    return MOVEMENT_TYPE_LABELS.get(value, value)


def category_label(value):
    return CATEGORY_LABELS.get(value, value)


def location_type_label(value):
    return LOCATION_TYPE_LABELS.get(value, value)


def project_status_label(value):
    return PROJECT_STATUS_LABELS.get(value, value)


def assignment_status_label(value):
    return ASSIGNMENT_STATUS_LABELS.get(value, value)


def yes_no_label(value):
    if value is True:
        return "Igen"
    if value is False:
        return "Nem"
    return "-"


def format_number(value):
    if value is None:
        return "-"
    if float(value).is_integer():
        return f"{int(value):,}".replace(",", " ")
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


def create_movement(
    device,
    movement_type,
    user_id,
    from_location_id=None,
    to_location_id=None,
    project_id=None,
    notes="",
):
    from models import StockMovement

    movement = StockMovement(
        device=device,
        movement_type=movement_type,
        from_location_id=from_location_id,
        to_location_id=to_location_id,
        project_id=project_id,
        notes=notes,
        created_by_id=user_id,
    )
    db.session.add(movement)
    return movement


def validate_movement(device, movement_type):
    from models import MOVEMENT_TYPES

    if movement_type not in MOVEMENT_TYPES:
        return "Érvénytelen mozgástípus."

    if device.status == "SCRAPPED":
        return "Selejtezett eszköz nem mozgatható tovább."

    allowed_statuses = {
        "INBOUND": None,
        "RESERVE": {"IN_STOCK"},
        "ISSUE": {"IN_STOCK", "RESERVED"},
        "INSTALL": {"ISSUED"},
        "RETURN": {"ISSUED", "INSTALLED"},
        "SERVICE": {"IN_STOCK", "RETURNED", "ISSUED", "INSTALLED"},
        "SCRAP": None,
        "TRANSFER": None,
    }
    allowed = allowed_statuses[movement_type]
    if allowed is not None and device.status not in allowed:
        readable = ", ".join(status_label(status) for status in sorted(allowed))
        return (
            f"A(z) {movement_type_label(movement_type)} nem engedélyezett "
            f"a(z) {device.asset_tag} eszköznél, mert jelenlegi státusza: "
            f"{status_label(device.status)}. Engedélyezett aktuális státusz: "
            f"{readable}."
        )
    return None


def apply_device_state(device, movement_type, to_location_id=None, project_id=None):
    device.location_id = to_location_id
    device.project_id = project_id
    device.updated_at = datetime.now(timezone.utc)

    status_by_movement = {
        "INBOUND": "IN_STOCK",
        "RESERVE": "RESERVED",
        "ISSUE": "ISSUED",
        "INSTALL": "INSTALLED",
        "RETURN": "RETURNED",
        "SERVICE": "IN_SERVICE",
        "SCRAP": "SCRAPPED",
    }
    if movement_type in status_by_movement:
        device.status = status_by_movement[movement_type]


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
