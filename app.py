from functools import wraps
from datetime import date, datetime, timezone
import json
import os
import re
import unicodedata
from uuid import uuid4

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
from openpyxl import load_workbook
from sqlalchemy import or_
from werkzeug.utils import secure_filename
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

IMPORT_STATUS_LABELS = {
    "running": "Fut",
    "completed": "Kész",
    "rolled_back": "Visszavonva",
    "partial_rollback": "Részben visszavonva",
}

INVENTORY_SHEETS = {
    "tolto",
    "toltok",
    "bmw tolto",
    "kioszk",
    "kamera",
    "egyeb",
    "nyito",
    "matricak",
}
ORPHAN_INVOICE_SHEET = "gazdatlanul"
IGNORED_IMPORT_SHEETS = {"workflow", "dashboard", "seged", "onkoltseg", "sheet1"}
UPLOAD_SUBDIR = "uploads"


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
        ImportBatch,
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
            "import_status_label": import_status_label,
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
        for location in Location.query.all():
            if location.name == "Main Warehouse":
                location.name = "Fő raktár"
            elif location.name.startswith("Stock Room"):
                location.name = location.name.replace("Stock Room", "Raktár", 1)
            elif location.name.startswith("Site"):
                location.name = location.name.replace("Site", "Helyszín", 1)
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
            "projects": Project.query.filter(Project.archived_at.is_(None)).count(),
            "devices": Device.query.filter(Device.archived_at.is_(None)).count(),
            "locations": Location.query.filter(Location.archived_at.is_(None)).count(),
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

        search = request.args.get("q", "").strip()
        selected_status = request.args.get("status", "").strip()
        project_query = Project.query.filter(Project.archived_at.is_(None))
        if search:
            term = f"%{search}%"
            project_query = project_query.filter(
                or_(
                    Project.code.ilike(term),
                    Project.name.ilike(term),
                    Project.customer.ilike(term),
                )
            )
        if selected_status in PROJECT_STATUS_LABELS:
            project_query = project_query.filter(Project.status == selected_status)

        project_list = project_query.order_by(Project.created_at.desc()).all()
        return render_template(
            "projects.html",
            projects=project_list,
            project_statuses=PROJECT_STATUS_LABELS,
            search=search,
            selected_status=selected_status,
        )

    @app.route("/projects/<int:project_id>")
    @login_required
    def project_detail(project_id):
        project = Project.query.get_or_404(project_id)
        devices = (
            Device.query.filter_by(project_id=project.id)
            .filter(Device.archived_at.is_(None))
            .order_by(Device.asset_tag.asc())
            .all()
        )
        movements = (
            StockMovement.query.filter_by(project_id=project.id)
            .order_by(StockMovement.created_at.desc())
            .limit(50)
            .all()
        )
        finance_summary = {
            "device_count": len(devices),
            "quantity": sum(device.quantity or 0 for device in devices),
            "huf_value": sum(device.huf_value or 0 for device in devices),
            "invoice_value": sum(device.invoice_value or 0 for device in devices),
            "ordered": sum(1 for device in devices if device.is_ordered),
            "arrived": sum(1 for device in devices if device.has_arrived),
        }
        return render_template(
            "project_detail.html",
            project=project,
            devices=devices,
            movements=movements,
            finance_summary=finance_summary,
        )

    @app.route("/projects/<int:project_id>/edit", methods=["GET", "POST"])
    @login_required
    def project_edit(project_id):
        project = Project.query.get_or_404(project_id)
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            code = request.form.get("code", "").strip()
            if not name or not code:
                flash("A projekt neve és kódja kötelező.", "danger")
            elif (
                Project.query.filter(Project.id != project.id)
                .filter(Project.code == code)
                .first()
            ):
                flash("Ezzel a kóddal már létezik másik projekt.", "danger")
            else:
                project.name = name
                project.code = code
                project.customer = request.form.get("customer", "").strip()
                project.status = request.form.get("status", "planned").strip()
                project.notes = request.form.get("notes", "").strip()
                db.session.commit()
                flash("A projekt módosítva.", "success")
                return redirect(url_for("project_detail", project_id=project.id))
        return render_template(
            "project_edit.html",
            project=project,
            project_statuses=PROJECT_STATUS_LABELS,
        )

    @app.route("/projects/<int:project_id>/archive", methods=["POST"])
    @login_required
    def project_archive(project_id):
        project = Project.query.get_or_404(project_id)
        project.archived_at = now_utc()
        db.session.commit()
        flash("A projekt archiválva.", "info")
        return redirect(url_for("projects"))

    @app.route("/devices", methods=["GET", "POST"])
    @login_required
    def devices():
        projects = Project.query.filter(Project.archived_at.is_(None)).order_by(Project.name.asc()).all()
        locations = Location.query.filter(Location.archived_at.is_(None)).order_by(Location.name.asc()).all()
        source_sheets = [
            row[0]
            for row in db.session.query(Device.source_sheet)
            .filter(Device.source_sheet.isnot(None))
            .distinct()
            .order_by(Device.source_sheet.asc())
            .all()
        ]
        selected_status = request.args.get("status", "").strip()
        selected_category = request.args.get("category", "").strip()
        selected_source_sheet = request.args.get("source_sheet", "").strip()
        selected_project_id = optional_int(request.args.get("project_id"))
        selected_location_id = optional_int(request.args.get("location_id"))
        search = request.args.get("q", "").strip()
        if request.method == "POST":
            data = device_form_data(request.form)

            if not data["asset_tag"] or not data["device_type"]:
                flash("Az eszközazonosító és a kategória kötelező.", "danger")
            elif data["device_type"] not in DEVICE_CATEGORIES:
                flash("Érvénytelen eszközkategória.", "danger")
            elif Device.query.filter_by(asset_tag=data["asset_tag"]).first():
                flash("Ezzel az eszközazonosítóval már létezik eszköz.", "danger")
            else:
                device = Device(**data, status="IN_STOCK")
                db.session.add(device)
                db.session.flush()
                create_movement(
                    device=device,
                    movement_type="INBOUND",
                    to_location_id=device.location_id,
                    project_id=device.project_id,
                    notes="Kezdeti eszközrögzítés.",
                    user_id=session["user_id"],
                )
                db.session.commit()
                flash("Az eszköz létrejött, a készletmozgás rögzítve.", "success")
                return redirect(url_for("devices"))

        device_query = Device.query.filter(Device.archived_at.is_(None))
        if search:
            term = f"%{search}%"
            device_query = device_query.filter(
                or_(
                    Device.product_name.ilike(term),
                    Device.asset_tag.ilike(term),
                    Device.serial_number.ilike(term),
                    Device.supplier_manufacturer.ilike(term),
                    Device.project.has(Project.code.ilike(term)),
                )
            )
        if selected_status in DEVICE_STATUSES:
            device_query = device_query.filter(Device.status == selected_status)
        if selected_category in DEVICE_CATEGORIES:
            device_query = device_query.filter(Device.device_type == selected_category)
        if selected_source_sheet:
            device_query = device_query.filter(Device.source_sheet == selected_source_sheet)
        if selected_project_id:
            device_query = device_query.filter(Device.project_id == selected_project_id)
        if selected_location_id:
            device_query = device_query.filter(Device.location_id == selected_location_id)

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
            source_sheets=source_sheets,
            selected_source_sheet=selected_source_sheet,
            selected_project_id=selected_project_id,
            selected_location_id=selected_location_id,
            search=search,
        )

    @app.route("/devices/<int:device_id>")
    @login_required
    def device_detail(device_id):
        device = Device.query.get_or_404(device_id)
        projects = Project.query.filter(Project.archived_at.is_(None)).order_by(Project.name.asc()).all()
        locations = Location.query.filter(Location.archived_at.is_(None)).order_by(Location.name.asc()).all()
        movements = (
            StockMovement.query.filter_by(device_id=device.id)
            .order_by(StockMovement.created_at.desc())
            .all()
        )
        return render_template(
            "device_detail.html",
            device=device,
            movements=movements,
            projects=projects,
            locations=locations,
        )

    @app.route("/devices/<int:device_id>/edit", methods=["GET", "POST"])
    @login_required
    def device_edit(device_id):
        device = Device.query.get_or_404(device_id)
        projects = Project.query.filter(Project.archived_at.is_(None)).order_by(Project.name.asc()).all()
        locations = Location.query.filter(Location.archived_at.is_(None)).order_by(Location.name.asc()).all()
        if request.method == "POST":
            data = device_form_data(request.form)
            if not data["asset_tag"] or not data["device_type"]:
                flash("Az eszközazonosító és a kategória kötelező.", "danger")
            elif data["device_type"] not in DEVICE_CATEGORIES:
                flash("Érvénytelen eszközkategória.", "danger")
            elif (
                Device.query.filter(Device.id != device.id)
                .filter(Device.asset_tag == data["asset_tag"])
                .first()
            ):
                flash("Ezzel az eszközazonosítóval már létezik másik eszköz.", "danger")
            else:
                for field, value in data.items():
                    setattr(device, field, value)
                db.session.commit()
                flash("Az eszköz módosítva. A státusz nem változott.", "success")
                return redirect(url_for("device_detail", device_id=device.id))
        return render_template(
            "device_edit.html",
            device=device,
            projects=projects,
            locations=locations,
            categories=DEVICE_CATEGORIES,
        )

    @app.route("/devices/<int:device_id>/archive", methods=["POST"])
    @login_required
    def device_archive(device_id):
        device = Device.query.get_or_404(device_id)
        device.archived_at = now_utc()
        db.session.commit()
        flash("Az eszköz archiválva.", "info")
        return redirect(url_for("devices"))

    @app.route("/devices/<int:device_id>/actions", methods=["POST"])
    @login_required
    def device_action(device_id):
        device = Device.query.get_or_404(device_id)
        movement_type = request.form.get("movement_type", "").strip()
        to_location_id = optional_int(request.form.get("to_location_id"))
        project_id = optional_int(request.form.get("project_id"))
        notes = request.form.get("notes", "").strip()
        from_location_id = device.location_id
        if movement_type not in MOVEMENT_TYPES:
            flash("Érvénytelen készletművelet.", "danger")
            return redirect(url_for("device_detail", device_id=device.id))
        error = validate_movement(device, movement_type)
        if error:
            flash(error, "danger")
            return redirect(url_for("device_detail", device_id=device.id))
        create_movement(
            device=device,
            movement_type=movement_type,
            from_location_id=from_location_id,
            to_location_id=to_location_id,
            project_id=project_id,
            notes=notes,
            user_id=session["user_id"],
        )
        apply_device_state(device, movement_type, to_location_id, project_id)
        db.session.commit()
        flash(f"Készletművelet rögzítve: {movement_type_label(movement_type)}.", "success")
        return redirect(url_for("device_detail", device_id=device.id))

    @app.route("/unassigned-invoices", methods=["GET", "POST"])
    @login_required
    def unassigned_invoices():
        projects = Project.query.filter(Project.archived_at.is_(None)).order_by(Project.name.asc()).all()
        devices = Device.query.filter(Device.archived_at.is_(None)).order_by(Device.asset_tag.asc()).all()
        selected_assignment_status = request.args.get("assignment_status", "").strip()
        search = request.args.get("q", "").strip()

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

        invoice_query = UnassignedInvoiceItem.query.filter(
            UnassignedInvoiceItem.archived_at.is_(None)
        )
        if search:
            term = f"%{search}%"
            invoice_query = invoice_query.filter(
                or_(
                    UnassignedInvoiceItem.invoice_number.ilike(term),
                    UnassignedInvoiceItem.partner.ilike(term),
                    UnassignedInvoiceItem.description.ilike(term),
                )
            )
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
            search=search,
        )

    @app.route("/unassigned-invoices/<int:item_id>/edit", methods=["GET", "POST"])
    @login_required
    def unassigned_invoice_edit(item_id):
        item = UnassignedInvoiceItem.query.get_or_404(item_id)
        projects = Project.query.filter(Project.archived_at.is_(None)).order_by(Project.name.asc()).all()
        devices = Device.query.filter(Device.archived_at.is_(None)).order_by(Device.asset_tag.asc()).all()
        if request.method == "POST":
            update_unassigned_invoice_from_form(item, request.form)
            db.session.commit()
            flash("A számlasor módosítva.", "success")
            return redirect(url_for("unassigned_invoices"))
        return render_template(
            "unassigned_invoice_edit.html",
            item=item,
            projects=projects,
            devices=devices,
            assignment_statuses=ASSIGNMENT_STATUS_LABELS,
        )

    @app.route("/unassigned-invoices/<int:item_id>/archive", methods=["POST"])
    @login_required
    def unassigned_invoice_archive(item_id):
        item = UnassignedInvoiceItem.query.get_or_404(item_id)
        item.archived_at = now_utc()
        db.session.commit()
        flash("A számlasor archiválva.", "info")
        return redirect(url_for("unassigned_invoices"))

    @app.route("/import", methods=["GET", "POST"])
    @login_required
    def excel_import():
        pending_import = session.get("pending_import")
        preview = None

        if request.method == "POST":
            action = request.form.get("action", "dry_run")
            if action == "confirm":
                if request.form.get("execute_import") != "on":
                    flash("Az importálás végrehajtásához jelöld be a megerősítést.", "danger")
                    return redirect(url_for("excel_import"))
                if not pending_import or not os.path.exists(pending_import["path"]):
                    flash("Nincs érvényes előnézeti import. Töltsd fel újra a fájlt.", "danger")
                    return redirect(url_for("excel_import"))

                summary = parse_inventory_workbook(pending_import["path"])
                batch = ImportBatch(
                    filename=pending_import["filename"],
                    imported_by_user_id=session.get("user_id"),
                    dry_run_summary_json=json.dumps(
                        summary, ensure_ascii=False, default=str
                    ),
                    warning_count=summary["warning_count"],
                    status="running",
                )
                db.session.add(batch)
                db.session.flush()
                result = import_parsed_workbook(summary, batch.id, session["user_id"])
                batch.created_count = result["created_count"]
                batch.skipped_count = result["skipped_count"]
                batch.updated_count = result["updated_count"]
                batch.status = "completed"
                db.session.commit()
                session.pop("pending_import", None)
                flash(
                    "Importálás kész: "
                    f"{batch.created_count} létrehozva, "
                    f"{batch.skipped_count} kihagyva, "
                    f"{batch.updated_count} frissítve.",
                    "success",
                )
                return redirect(url_for("excel_import", batch_id=batch.id))

            upload = request.files.get("excel_file")
            if not upload or upload.filename == "":
                flash("Válassz ki egy .xlsx fájlt.", "danger")
                return redirect(url_for("excel_import"))
            if not upload.filename.lower().endswith(".xlsx"):
                flash("Csak .xlsx fájl tölthető fel.", "danger")
                return redirect(url_for("excel_import"))

            upload_dir = os.path.join(app.instance_path, UPLOAD_SUBDIR)
            os.makedirs(upload_dir, exist_ok=True)
            safe_name = secure_filename(upload.filename)
            filename = f"{uuid4().hex}_{safe_name}"
            upload_path = os.path.join(upload_dir, filename)
            upload.save(upload_path)
            preview = parse_inventory_workbook(upload_path)
            session["pending_import"] = {
                "path": upload_path,
                "filename": safe_name,
            }
            flash("Előnézet elkészült. Az adatbázis még nem módosult.", "info")

        batch = None
        batch_id = optional_int(request.args.get("batch_id"))
        if batch_id:
            batch = db.session.get(ImportBatch, batch_id)
        if preview is None and pending_import and os.path.exists(pending_import["path"]):
            preview = parse_inventory_workbook(pending_import["path"])

        recent_batches = (
            ImportBatch.query.filter(ImportBatch.archived_at.is_(None))
            .order_by(ImportBatch.created_at.desc())
            .limit(8)
            .all()
        )
        return render_template(
            "import.html",
            preview=preview,
            batch=batch,
            pending_import=session.get("pending_import"),
            recent_batches=recent_batches,
        )

    @app.route("/import-batches/<int:batch_id>")
    @login_required
    def import_batch_detail(batch_id):
        batch = ImportBatch.query.get_or_404(batch_id)
        devices = (
            Device.query.filter_by(import_batch_id=batch.id)
            .order_by(Device.source_row_number.asc())
            .all()
        )
        invoice_items = (
            UnassignedInvoiceItem.query.filter_by(import_batch_id=batch.id)
            .order_by(UnassignedInvoiceItem.source_row_number.asc())
            .all()
        )
        warnings = []
        if batch.dry_run_summary_json:
            try:
                summary = json.loads(batch.dry_run_summary_json)
                warnings = summary.get("warnings", [])
                for sheet in summary.get("sheets", []):
                    warnings.extend(sheet.get("warnings", []))
            except json.JSONDecodeError:
                warnings = []
        return render_template(
            "import_batch_detail.html",
            batch=batch,
            devices=devices,
            invoice_items=invoice_items,
            warnings=warnings,
        )

    @app.route("/import-batches/<int:batch_id>/rollback", methods=["POST"])
    @login_required
    def import_batch_rollback(batch_id):
        batch = ImportBatch.query.get_or_404(batch_id)
        archived_devices = 0
        unsafe_devices = 0
        archived_invoice_items = 0
        for device in batch.devices:
            if device.archived_at:
                continue
            if len(device.movements) <= 1:
                device.archived_at = now_utc()
                archived_devices += 1
            else:
                unsafe_devices += 1
        for item in batch.unassigned_invoice_items:
            if not item.archived_at:
                item.archived_at = now_utc()
                archived_invoice_items += 1
        batch.status = "rolled_back" if unsafe_devices == 0 else "partial_rollback"
        batch.archived_at = now_utc()
        db.session.commit()
        if unsafe_devices:
            flash(
                "Import részben visszavonva. "
                f"{archived_devices} eszköz és {archived_invoice_items} számlasor archiválva, "
                f"{unsafe_devices} eszköz kézi mozgások miatt megmaradt.",
                "warning",
            )
        else:
            flash(
                f"Import visszavonva: {archived_devices} eszköz és "
                f"{archived_invoice_items} számlasor archiválva.",
                "success",
            )
        return redirect(url_for("import_batch_detail", batch_id=batch.id))

    @app.route("/import-batches/<int:batch_id>/archive", methods=["POST"])
    @login_required
    def import_batch_archive(batch_id):
        batch = ImportBatch.query.get_or_404(batch_id)
        batch.archived_at = now_utc()
        db.session.commit()
        flash("Az importcsomag archiválva.", "info")
        return redirect(url_for("excel_import"))

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

        selected_type = request.args.get("location_type", "").strip()
        location_query = Location.query.filter(Location.archived_at.is_(None))
        if selected_type in LOCATION_TYPE_LABELS:
            location_query = location_query.filter(Location.location_type == selected_type)
        location_list = location_query.order_by(Location.name.asc()).all()
        return render_template(
            "locations.html",
            locations=location_list,
            location_types=LOCATION_TYPE_LABELS,
            selected_type=selected_type,
        )

    @app.route("/locations/<int:location_id>")
    @login_required
    def location_detail(location_id):
        location = Location.query.get_or_404(location_id)
        devices = (
            Device.query.filter_by(location_id=location.id)
            .filter(Device.archived_at.is_(None))
            .order_by(Device.asset_tag.asc())
            .all()
        )
        movements = (
            StockMovement.query.filter(
                or_(
                    StockMovement.from_location_id == location.id,
                    StockMovement.to_location_id == location.id,
                )
            )
            .order_by(StockMovement.created_at.desc())
            .limit(50)
            .all()
        )
        return render_template(
            "location_detail.html",
            location=location,
            devices=devices,
            movements=movements,
        )

    @app.route("/locations/<int:location_id>/edit", methods=["GET", "POST"])
    @login_required
    def location_edit(location_id):
        location = Location.query.get_or_404(location_id)
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            if not name:
                flash("A készlethely neve kötelező.", "danger")
            else:
                location.name = name
                location.location_type = request.form.get("location_type", "warehouse").strip()
                location.address = request.form.get("address", "").strip()
                location.notes = request.form.get("notes", "").strip()
                db.session.commit()
                flash("A készlethely módosítva.", "success")
                return redirect(url_for("location_detail", location_id=location.id))
        return render_template(
            "location_edit.html",
            location=location,
            location_types=LOCATION_TYPE_LABELS,
        )

    @app.route("/locations/<int:location_id>/archive", methods=["POST"])
    @login_required
    def location_archive(location_id):
        location = Location.query.get_or_404(location_id)
        location.archived_at = now_utc()
        db.session.commit()
        flash("A készlethely archiválva.", "info")
        return redirect(url_for("locations"))

    @app.route("/movements", methods=["GET", "POST"])
    @login_required
    def movements():
        devices = Device.query.filter(Device.archived_at.is_(None)).order_by(Device.asset_tag.asc()).all()
        locations = Location.query.filter(Location.archived_at.is_(None)).order_by(Location.name.asc()).all()
        projects = Project.query.filter(Project.archived_at.is_(None)).order_by(Project.name.asc()).all()

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


def import_status_label(value):
    return IMPORT_STATUS_LABELS.get(value, value)


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


def now_utc():
    return datetime.now(timezone.utc)


def device_form_data(form):
    quantity = optional_float(form.get("quantity"))
    unit_net_price = optional_float(form.get("unit_net_price"))
    currency = form.get("currency", "").strip().upper() or None
    huf_value = optional_float(form.get("huf_value"))
    return {
        "asset_tag": form.get("asset_tag", "").strip(),
        "serial_number": form.get("serial_number", "").strip(),
        "device_type": form.get("device_type", "").strip(),
        "manufacturer": form.get("manufacturer", "").strip(),
        "model": form.get("model", "").strip(),
        "product_name": form.get("product_name", "").strip() or None,
        "subtype_note": form.get("subtype_note", "").strip() or None,
        "supplier_manufacturer": form.get("supplier_manufacturer", "").strip() or None,
        "version": form.get("version", "").strip() or None,
        "quantity": quantity,
        "unit_net_price": unit_net_price,
        "currency": currency,
        "huf_value": huf_value
        if huf_value is not None
        else calculate_huf_value(quantity, unit_net_price, currency),
        "assignment_quantity": optional_float(form.get("assignment_quantity")),
        "assignment_notes": form.get("assignment_notes", "").strip() or None,
        "order_date": optional_date(form.get("order_date")),
        "is_ordered": checkbox_value(form.get("is_ordered")),
        "planned_arrival_date": optional_date(form.get("planned_arrival_date")),
        "actual_arrival_date": optional_date(form.get("actual_arrival_date")),
        "has_arrived": checkbox_value(form.get("has_arrived")),
        "shipping_cost": optional_float(form.get("shipping_cost")),
        "shipping_date": optional_date(form.get("shipping_date")),
        "supplier_invoice_number": form.get("supplier_invoice_number", "").strip() or None,
        "supplier_invoice_paid": checkbox_value(form.get("supplier_invoice_paid")),
        "invoice_value": optional_float(form.get("invoice_value")),
        "shipping_invoice_number": form.get("shipping_invoice_number", "").strip() or None,
        "shipping_invoice_paid": checkbox_value(form.get("shipping_invoice_paid")),
        "project_id": optional_int(form.get("project_id")),
        "location_id": optional_int(form.get("location_id")),
    }


def update_unassigned_invoice_from_form(item, form):
    assigned_project_id = optional_int(form.get("assigned_project_id"))
    assigned_device_id = optional_int(form.get("assigned_device_id"))
    assignment_status = form.get("assignment_status", "unassigned").strip()
    if assignment_status not in ASSIGNMENT_STATUS_LABELS:
        assignment_status = "unassigned"
    if assigned_project_id or assigned_device_id:
        assignment_status = "assigned"
    item.invoice_number = form.get("invoice_number", "").strip() or None
    item.partner = form.get("partner", "").strip() or None
    item.invoice_date = optional_date(form.get("invoice_date"))
    item.accounting_fulfillment_date = optional_date(
        form.get("accounting_fulfillment_date")
    )
    item.payment_deadline = optional_date(form.get("payment_deadline"))
    item.gross_amount_huf = optional_float(form.get("gross_amount_huf"))
    item.currency = form.get("currency", "").strip().upper() or None
    item.description = form.get("description", "").strip() or None
    item.quantity = optional_float(form.get("quantity"))
    item.unit_price_huf = optional_float(form.get("unit_price_huf"))
    item.net_amount_huf = optional_float(form.get("net_amount_huf"))
    item.vat_amount_huf = optional_float(form.get("vat_amount_huf"))
    item.line_gross_amount_huf = optional_float(form.get("line_gross_amount_huf"))
    item.assignment_status = assignment_status
    item.notes = form.get("notes", "").strip() or None
    item.assigned_project_id = assigned_project_id
    item.assigned_device_id = assigned_device_id


def parse_inventory_workbook(path):
    workbook = load_workbook(path, read_only=True, data_only=True)
    summary = {
        "sheets": [],
        "preview_rows": [],
        "warnings": [],
        "warning_count": 0,
        "total_rows": 0,
        "total_skipped": 0,
        "inventory_rows": [],
        "invoice_rows": [],
    }

    for sheet in workbook.worksheets:
        normalized_sheet = normalize_key(sheet.title)
        if normalized_sheet in IGNORED_IMPORT_SHEETS:
            continue
        if normalized_sheet == ORPHAN_INVOICE_SHEET:
            sheet_summary = parse_unassigned_invoice_sheet(sheet, summary)
        elif normalized_sheet in INVENTORY_SHEETS:
            sheet_summary = parse_inventory_sheet(sheet, summary)
        else:
            sheet_summary = {
                "sheet_name": sheet.title,
                "type": "kihagyva",
                "parsed_count": 0,
                "skipped_count": 0,
                "warnings": [f"A(z) {sheet.title} munkalap importálása nincs beállítva."],
            }
        summary["sheets"].append(sheet_summary)

    summary["warning_count"] = len(summary["warnings"]) + sum(
        len(sheet["warnings"]) for sheet in summary["sheets"]
    )
    return summary


def parse_inventory_sheet(sheet, summary):
    header_row, header_map = find_header_map(sheet, max_scan_rows=12)
    warnings = []
    parsed_count = 0
    skipped_count = 0
    if not header_row:
        warning = f"A(z) {sheet.title} munkalapon nem található fejlécsor."
        summary["warnings"].append(warning)
        return {
            "sheet_name": sheet.title,
            "type": "eszköz",
            "parsed_count": 0,
            "skipped_count": 0,
            "warnings": [warning],
        }

    required_candidates = [
        ("termék vagy típus", ["termek", "tipus", "tolto tipusa", "kamera tipusa"]),
        ("mennyiség", ["mennyiseg"]),
        ("projekt kód", ["projekt kod", "projekt kod"]),
    ]
    for label, candidates in required_candidates:
        if not any(candidate in header_map for candidate in candidates):
            warnings.append(f"Hiányzó vagy eltérő fejléc: {label}.")

    for row_number, row in iter_sheet_rows(sheet, header_row + 1):
        parsed = parse_inventory_row(sheet.title, row_number, row, header_map)
        if parsed is None:
            skipped_count += 1
            continue
        parsed_count += 1
        summary["inventory_rows"].append(parsed)
        if len(summary["preview_rows"]) < 10:
            summary["preview_rows"].append(preview_row("Eszköz", parsed))

    summary["total_rows"] += parsed_count
    summary["total_skipped"] += skipped_count
    return {
        "sheet_name": sheet.title,
        "type": "eszköz",
        "parsed_count": parsed_count,
        "skipped_count": skipped_count,
        "warnings": warnings,
    }


def parse_unassigned_invoice_sheet(sheet, summary):
    header_row, header_map = find_header_map(sheet, max_scan_rows=5)
    warnings = []
    parsed_count = 0
    skipped_count = 0
    if not header_row:
        warning = "A Gazdátlanul munkalapon nem található fejlécsor."
        summary["warnings"].append(warning)
        return {
            "sheet_name": sheet.title,
            "type": "gazdátlan számlasor",
            "parsed_count": 0,
            "skipped_count": 0,
            "warnings": [warning],
        }

    for label in ["szamlaszam", "partner", "megnevezes"]:
        if label not in header_map:
            warnings.append(f"Hiányzó vagy eltérő fejléc: {label}.")

    for row_number, row in iter_sheet_rows(sheet, header_row + 1):
        parsed = parse_unassigned_invoice_row(sheet.title, row_number, row, header_map)
        if parsed is None:
            skipped_count += 1
            continue
        parsed_count += 1
        summary["invoice_rows"].append(parsed)
        if len(summary["preview_rows"]) < 10:
            summary["preview_rows"].append(preview_row("Gazdátlan számlasor", parsed))

    summary["total_rows"] += parsed_count
    summary["total_skipped"] += skipped_count
    return {
        "sheet_name": sheet.title,
        "type": "gazdátlan számlasor",
        "parsed_count": parsed_count,
        "skipped_count": skipped_count,
        "warnings": warnings,
    }


def parse_inventory_row(sheet_name, row_number, row, header_map):
    product_name = first_value(row, header_map, ["termek", "tolto marka"])
    type_value = first_value(row, header_map, ["tipus", "tolto tipusa", "kamera tipusa"])
    subtype_note = first_value(row, header_map, ["altipus", "altipus megjegyzes"])
    row_note = first_value(row, header_map, ["megjegyzes"])
    supplier = first_value(
        row,
        header_map,
        ["beszallito", "gyartasert felelos", "gyarto", "maganszemely neve"],
    )
    quantity = number_value(first_value(row, header_map, ["mennyiseg"]))
    unit_net_price = number_value(first_value(row, header_map, ["netto egysegar"]))
    currency = clean_string(first_value(row, header_map, ["deviza", "penznem"]))
    huf_value = number_value(first_value(row, header_map, ["ertek huf", "ertek"]))
    project_code = clean_project_code(
        first_value(row, header_map, ["projekt kod", "projekt kód"])
    )
    internal_id = clean_string(first_value(row, header_map, ["id", "po szam", "po"]))
    version = clean_string(first_value(row, header_map, ["verzio"]))
    supplier_invoice_number = clean_string(
        first_value(
            row,
            header_map,
            [
                "kapcsolodo szamla sorszama beszallito",
                "kapcsolodo eloleg szamla sorszama beszallito",
                "kapcsolodo elolegszamla szamla sorszama beszallito",
                "kapcsolodo vegszamla szamla sorszama beszallito",
                "kapcsolodo elolegszamla sorszama beszallito",
                "kapcsolodo vegszamla sorszama beszallito",
            ],
        )
    )
    shipping_invoice_number = clean_string(
        first_value(
            row,
            header_map,
            [
                "kapcsolodo szamla sorszama szallitmanyozo",
                "kapcsolodo szallitmanyozoi szamla sorszama",
            ],
        )
    )
    invoice_value = number_value(first_value(row, header_map, ["szamla erteke"]))

    if not any(
        [
            product_name,
            type_value,
            subtype_note,
            supplier,
            quantity,
            project_code,
            supplier_invoice_number,
            shipping_invoice_number,
            internal_id,
        ]
    ):
        return None

    asset_tag = internal_id or f"{normalize_key(sheet_name).replace(' ', '-').upper()}-{row_number}"
    category = infer_device_type(sheet_name, type_value, product_name)
    return {
        "source_sheet": sheet_name,
        "source_row_number": row_number,
        "asset_tag": asset_tag,
        "serial_number": internal_id or "",
        "device_type": category,
        "manufacturer": supplier or "",
        "model": clean_string(product_name or type_value or subtype_note) or "",
        "product_name": clean_string(product_name or type_value),
        "subtype_note": clean_string(subtype_note),
        "supplier_manufacturer": supplier,
        "version": version,
        "quantity": quantity,
        "unit_net_price": unit_net_price,
        "currency": currency.upper() if currency else None,
        "huf_value": huf_value,
        "project_code": project_code,
        "notes": clean_string(row_note),
        "order_date": date_value(first_value(row, header_map, ["rendeles napja"])),
        "is_ordered": bool_value(first_value(row, header_map, ["megrendelve"])),
        "planned_arrival_date": date_value(
            first_value(row, header_map, ["tervezett erkezes napja"])
        ),
        "actual_arrival_date": date_value(first_value(row, header_map, ["erkezes napja"])),
        "has_arrived": bool_value(first_value(row, header_map, ["megerkezett"])),
        "shipping_cost": number_value(
            first_value(
                row,
                header_map,
                ["szallitasi ktg", "netto szallitasi ktg eur huf", "szallitasi koltseg"],
            )
        ),
        "shipping_date": date_value(first_value(row, header_map, ["elszallitas napja"])),
        "supplier_invoice_number": supplier_invoice_number,
        "supplier_invoice_paid": bool_value(
            first_value(
                row,
                header_map,
                [
                    "beszallito szamla fizetve",
                    "beszallito elolegszamla fizetve",
                    "beszallito vegszamla fizetve",
                ],
            )
        ),
        "invoice_value": invoice_value,
        "shipping_invoice_number": shipping_invoice_number,
        "shipping_invoice_paid": bool_value(
            first_value(row, header_map, ["szallitmanyozo szamla fizetve"])
        ),
    }


def parse_unassigned_invoice_row(sheet_name, row_number, row, header_map):
    invoice_number = clean_string(first_value(row, header_map, ["szamlaszam"]))
    partner = clean_string(first_value(row, header_map, ["partner"]))
    description = clean_string(first_value(row, header_map, ["megnevezes"]))
    line_gross_amount_huf = number_value(
        first_value(row, header_map, ["szamla sor brutto osszeg huf"])
    )
    if not any([invoice_number, partner, description, line_gross_amount_huf]):
        return None

    return {
        "source_sheet": sheet_name,
        "source_row_number": row_number,
        "invoice_number": invoice_number,
        "partner": partner,
        "invoice_date": date_value(first_value(row, header_map, ["szamla kelte"])),
        "accounting_fulfillment_date": date_value(
            first_value(row, header_map, ["szamviteli teljesites datuma"])
        ),
        "payment_deadline": date_value(first_value(row, header_map, ["fizetesi hatarido"])),
        "gross_amount_huf": number_value(
            first_value(row, header_map, ["brutto osszeg huf"])
        ),
        "currency": clean_string(first_value(row, header_map, ["penznem", "deviza"])),
        "description": description,
        "quantity": number_value(first_value(row, header_map, ["mennyiseg"])),
        "unit_price_huf": number_value(first_value(row, header_map, ["egysegar huf"])),
        "net_amount_huf": number_value(
            first_value(row, header_map, ["szamla sor netto osszeg huf"])
        ),
        "vat_amount_huf": number_value(
            first_value(row, header_map, ["szamla sor afa osszeg huf"])
        ),
        "line_gross_amount_huf": line_gross_amount_huf,
        "assignment_status": "unassigned",
    }


def import_parsed_workbook(summary, import_batch_id, user_id):
    from models import Device, Project, UnassignedInvoiceItem

    created = 0
    skipped = 0
    updated = 0
    imported_at = datetime.now(timezone.utc)

    for row in summary["inventory_rows"]:
        existing = Device.query.filter_by(
            source_sheet=row["source_sheet"],
            asset_tag=row["asset_tag"],
            product_name=row["product_name"],
            supplier_invoice_number=row["supplier_invoice_number"],
        ).first()
        asset_tag_conflict = Device.query.filter_by(asset_tag=row["asset_tag"]).first()
        if existing or asset_tag_conflict:
            skipped += 1
            continue

        project = get_or_create_project(row.get("project_code"))
        device = Device(
            asset_tag=row["asset_tag"],
            serial_number=row["serial_number"],
            device_type=row["device_type"],
            manufacturer=row["manufacturer"],
            model=row["model"],
            product_name=row["product_name"],
            subtype_note=row["subtype_note"],
            supplier_manufacturer=row["supplier_manufacturer"],
            version=row["version"],
            quantity=row["quantity"],
            unit_net_price=row["unit_net_price"],
            currency=row["currency"],
            huf_value=row["huf_value"]
            if row["huf_value"] is not None
            else calculate_huf_value(row["quantity"], row["unit_net_price"], row["currency"]),
            assignment_quantity=row["quantity"],
            assignment_notes=row["notes"],
            order_date=row["order_date"],
            is_ordered=row["is_ordered"],
            planned_arrival_date=row["planned_arrival_date"],
            actual_arrival_date=row["actual_arrival_date"],
            has_arrived=row["has_arrived"],
            shipping_cost=row["shipping_cost"],
            shipping_date=row["shipping_date"],
            supplier_invoice_number=row["supplier_invoice_number"],
            supplier_invoice_paid=row["supplier_invoice_paid"],
            invoice_value=row["invoice_value"],
            shipping_invoice_number=row["shipping_invoice_number"],
            shipping_invoice_paid=row["shipping_invoice_paid"],
            project_id=project.id if project else None,
            status="IN_STOCK",
            source_sheet=row["source_sheet"],
            source_row_number=row["source_row_number"],
            import_batch_id=import_batch_id,
            imported_at=imported_at,
        )
        db.session.add(device)
        db.session.flush()
        create_movement(
            device=device,
            movement_type="INBOUND",
            project_id=device.project_id,
            notes=f"Excel import: {row['source_sheet']} #{row['source_row_number']}",
            user_id=user_id,
        )
        created += 1

    for row in summary["invoice_rows"]:
        existing = UnassignedInvoiceItem.query.filter_by(
            invoice_number=row["invoice_number"],
            partner=row["partner"],
            description=row["description"],
            line_gross_amount_huf=row["line_gross_amount_huf"],
        ).first()
        if existing:
            skipped += 1
            continue
        item = UnassignedInvoiceItem(
            invoice_number=row["invoice_number"],
            partner=row["partner"],
            invoice_date=row["invoice_date"],
            accounting_fulfillment_date=row["accounting_fulfillment_date"],
            payment_deadline=row["payment_deadline"],
            gross_amount_huf=row["gross_amount_huf"],
            currency=row["currency"],
            description=row["description"],
            quantity=row["quantity"],
            unit_price_huf=row["unit_price_huf"],
            net_amount_huf=row["net_amount_huf"],
            vat_amount_huf=row["vat_amount_huf"],
            line_gross_amount_huf=row["line_gross_amount_huf"],
            assignment_status=row["assignment_status"],
            source_sheet=row["source_sheet"],
            source_row_number=row["source_row_number"],
            import_batch_id=import_batch_id,
            imported_at=imported_at,
        )
        db.session.add(item)
        created += 1

    return {
        "created_count": created,
        "skipped_count": skipped,
        "updated_count": updated,
    }


def get_or_create_project(project_code):
    from models import Project

    if not project_code:
        return None
    project = Project.query.filter_by(code=project_code).first()
    if project:
        return project
    project = Project(name=project_code, code=project_code, status="active")
    db.session.add(project)
    db.session.flush()
    return project


def normalize_key(value):
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def find_header_map(sheet, max_scan_rows=12):
    for row_number, cells in enumerate(
        sheet.iter_rows(min_row=1, max_row=max_scan_rows, values_only=True), start=1
    ):
        normalized = [normalize_key(value) for value in cells]
        if any(
            key in normalized
            for key in ["termek", "tipus", "szamlaszam", "projekt kod", "mennyiseg"]
        ):
            header_map = {}
            for index, key in enumerate(normalized):
                if key:
                    header_map.setdefault(key, []).append(index)
            return row_number, header_map
    return None, {}


def iter_sheet_rows(sheet, start_row):
    for row_number, row in enumerate(
        sheet.iter_rows(min_row=start_row, values_only=True), start=start_row
    ):
        yield row_number, list(row)


def first_value(row, header_map, candidates):
    for candidate in candidates:
        key = normalize_key(candidate)
        for index in header_map.get(key, []):
            if index < len(row):
                value = row[index]
                if meaningful_value(value):
                    return value
    return None


def meaningful_value(value):
    if value is None:
        return False
    if isinstance(value, str):
        stripped = value.strip()
        return bool(stripped) and stripped not in {"-", "#"}
    return True


def clean_string(value):
    if not meaningful_value(value):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    return str(value).strip()


def clean_project_code(value):
    text = clean_string(value)
    if not text:
        return None
    return text


def date_value(value):
    if not meaningful_value(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip().replace(".", "-")
    for fmt in ("%Y-%m-%d", "%Y-%m-%d-", "%Y %m %d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def number_value(value):
    if not meaningful_value(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    text = text.replace("\xa0", "").replace(" ", "").replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def bool_value(value):
    if not meaningful_value(value):
        return None
    text = normalize_key(value)
    if text in {"igen", "yes", "true", "1", "ok"}:
        return True
    if text in {"nem", "no", "false", "0", "nok"}:
        return False
    return None


def infer_device_type(sheet_name, type_value, product_name):
    sheet_key = normalize_key(sheet_name)
    if sheet_key in {"tolto", "toltok", "bmw tolto", "matricak"}:
        return "EV charger"
    if sheet_key == "kamera":
        return "Sensor"
    if sheet_key == "kioszk":
        return "Cabinet"
    if sheet_key == "nyito":
        return "Network device"
    value = clean_string(type_value or product_name)
    return value or "Other"


def preview_row(kind, row):
    if kind == "Gazdátlan számlasor":
        return {
            "tipus": kind,
            "munkalap": row["source_sheet"],
            "sor": row["source_row_number"],
            "azonosito": row["invoice_number"],
            "nev": row["description"],
            "partner": row["partner"],
            "ertek": row["line_gross_amount_huf"] or row["gross_amount_huf"],
        }
    return {
        "tipus": kind,
        "munkalap": row["source_sheet"],
        "sor": row["source_row_number"],
        "azonosito": row["asset_tag"],
        "nev": row["product_name"],
        "partner": row["supplier_manufacturer"],
        "ertek": row["huf_value"],
    }


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
