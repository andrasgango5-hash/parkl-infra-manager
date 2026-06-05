from functools import wraps
from datetime import date, datetime, timezone
from io import BytesIO
import base64
import json
import os
import re
import unicodedata
from uuid import uuid4

import click
import qrcode
import reportlab
from flask import (
    abort,
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from openpyxl import Workbook, load_workbook
from PIL import Image as PILImage, UnidentifiedImageError
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
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
    "Sticker": "Matrica",
    "Camera": "Kamera",
    "Kiosk": "Kioszk",
    "Opener": "Nyitó eszköz",
    "Router": "Router",
    "Parkl box": "Parkl box",
    "Other": "Egyéb",
}

LOCATION_TYPE_LABELS = {
    "warehouse": "Raktár",
    "project_site": "Projekt helyszín",
    "service_vehicle": "Szervizautó",
    "installed": "Telepített helyszín",
    "service": "Szerviz / javítás",
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

DEVICE_CURRENCIES = {"HUF", "EUR"}
DEVICE_QR_MODE_LABELS = {
    "none": "Nincs QR",
    "group": "Csoport QR",
    "individual": "Egyedi QR példányonként",
}

TEMPLATE_PROJECT_HEADERS = [
    "project_code", "project_name", "customer_name", "site_name", "address", "status", "notes"
]
TEMPLATE_DEVICE_HEADERS = [
    "project_code", "category", "product_name", "manufacturer", "model", "serial_number",
    "asset_tag", "quantity", "currency", "unit_net_price", "total_net_price", "vat_rate",
    "unit_gross_price", "total_gross_price", "location_name", "status", "notes",
]
TEMPLATE_LOCATION_HEADERS = ["location_name", "location_type", "address", "notes"]

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
DRAWING_UPLOAD_SUBDIR = "drawings"
WORK_ORDER_UPLOAD_SUBDIR = "work_orders"
ALLOWED_DRAWING_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
ALLOWED_PHOTO_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

WORK_ORDER_TYPE_LABELS = {
    "maintenance": "Karbantartás",
    "troubleshooting": "Hibaelhárítás",
    "cable_replacement": "Kábelcsere",
    "installation": "Telepítés",
    "site_visit": "Helyszíni kiszállás",
    "inspection": "Felülvizsgálat",
    "other": "Egyéb",
}

WORK_ORDER_STATUS_LABELS = {
    "draft": "Tervezet",
    "in_progress": "Folyamatban",
    "closed": "Lezárt",
    "pdf_generated": "PDF generálva",
}

WORK_ORDER_PHOTO_CATEGORY_LABELS = {
    "before": "Hiba előtti állapot",
    "during": "Munka közbeni állapot",
    "after": "Javítás utáni állapot",
}

PDF_FONT_REGULAR = "ParklSans"
PDF_FONT_BOLD = "ParklSans-Bold"

DRAWING_ICON_CATEGORIES = {
    "Parking/access": [
        ("barrier", "Sorompó"),
        ("entry_barrier", "Bejárati sorompó"),
        ("exit_barrier", "Kijárati sorompó"),
        ("loop_detector", "Hurokdetektor"),
        ("rfid_reader", "RFID olvasó"),
        ("parking_space", "Parkolóhely"),
        ("direction_arrow", "Irány nyíl"),
    ],
    "Cameras": [
        ("entry_anpr_camera", "Belépő ANPR kamera"),
        ("exit_anpr_camera", "Kilépő ANPR kamera"),
        ("overview_camera", "Áttekintő kamera"),
    ],
    "Charging": [
        ("ac_charger", "AC töltő"),
        ("dc_charger", "DC töltő"),
        ("charger_pedestal", "Töltőoszlop"),
        ("dlm_controller", "DLM vezérlő"),
        ("energy_meter", "Fogyasztásmérő"),
        ("ct", "Áramváltó"),
    ],
    "Network/IT": [
        ("rack", "Rack"),
        ("switch", "Switch"),
        ("poe_switch", "PoE switch"),
        ("router", "Router"),
        ("teltonika", "Teltonika"),
        ("parkl_box", "Raspberry Pi / Parkl box"),
        ("patch_panel", "Patch panel"),
    ],
    "Electrical": [
        ("distribution_board", "Elosztószekrény"),
        ("power_supply", "Tápegység"),
        ("breaker", "Kismegszakító"),
        ("busbar", "Sín / trunking"),
        ("cable_tray", "Kábeltálca"),
        ("wall_penetration", "Falfúrás"),
        ("floor_penetration", "Födémáttörés"),
        ("junction_box", "Kötődoboz"),
    ],
}

DRAWING_LINE_TYPES = [
    ("cat5e", "CAT5e / UTP", "#2563eb"),
    ("power", "Erősáramú kábel", "#dc2626"),
    ("barrier_control", "Sorompó vezérlés", "#f59e0b"),
    ("camera_network", "Kamera hálózat", "#7c3aed"),
    ("dlm", "DLM kommunikáció", "#0891b2"),
    ("main_supply", "Fő betáp", "#111827"),
    ("spare_conduit", "Tartalék védőcső", "#64748b"),
]


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
        USER_ROLES,
        USER_ROLE_LABELS,
        Device,
        DeviceUnit,
        ImportBatch,
        Location,
        Project,
        ProjectDrawing,
        StockMovement,
        UnassignedInvoiceItem,
        User,
        WorkOrder,
        WorkOrderMaterial,
        WorkOrderMeasurement,
        WorkOrderPhoto,
        WorkOrderTemplate,
    )

    def get_current_user():
        user_id = session.get("user_id")
        if not user_id:
            return None
        return db.session.get(User, user_id)

    def user_can(*roles):
        user = get_current_user()
        return bool(user and user.is_active and user.has_role(*roles))

    @app.context_processor
    def inject_current_user():
        user = get_current_user()
        return {
            "current_user": user,
            "can_write": user_can("admin", "manager"),
            "can_manage_work_orders": user_can("admin", "manager", "technician"),
            "can_export": user_can("admin", "manager"),
            "can_view_finance": user_can("admin", "manager"),
            "can_manage_users": user_can("admin"),
            "user_role_label": lambda value: USER_ROLE_LABELS.get(value, value or "–"),
            "status_label": status_label,
            "movement_type_label": movement_type_label,
            "category_label": category_label,
            "location_type_label": location_type_label,
            "project_status_label": project_status_label,
            "assignment_status_label": assignment_status_label,
            "import_status_label": import_status_label,
            "yes_no_label": yes_no_label,
            "format_number": format_number,
            "format_vat_rate": format_vat_rate,
            "line_net_amount": line_net_amount,
            "device_display_label": device_display_label,
            "device_primary_label": device_primary_label,
            "device_money_text": device_money_text,
            "device_qr_mode_label": device_qr_mode_label,
            "status_badge_class": status_badge_class,
            "movement_badge_class": movement_badge_class,
            "work_order_type_label": work_order_type_label,
            "work_order_status_label": work_order_status_label,
            "work_order_photo_category_label": work_order_photo_category_label,
            "format_duration": format_duration,
            "template_json_rows": template_json_rows,
            "available_device_movements": available_device_movements,
            "current_date": date.today().isoformat(),
        }

    def login_required(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            user = get_current_user()
            if user is None:
                session.clear()
                flash("A folytatáshoz jelentkezz be.", "warning")
                return redirect(url_for("login"))
            if not user.is_active:
                session.clear()
                flash("A felhasználói fiók inaktív. Fordulj egy adminisztrátorhoz.", "danger")
                return redirect(url_for("login"))
            return view(*args, **kwargs)

        return wrapped_view

    def role_required(*roles):
        def decorator(view):
            @wraps(view)
            @login_required
            def wrapped_view(*args, **kwargs):
                if not user_can(*roles):
                    abort(403)
                return view(*args, **kwargs)

            return wrapped_view

        return decorator

    def method_role_required(*roles):
        def decorator(view):
            @wraps(view)
            @login_required
            def wrapped_view(*args, **kwargs):
                if request.method not in {"GET", "HEAD", "OPTIONS"} and not user_can(*roles):
                    abort(403)
                return view(*args, **kwargs)

            return wrapped_view

        return decorator

    def admin_required(view):
        return role_required("admin")(view)

    def write_required(view):
        return method_role_required("admin", "manager")(view)

    def export_required(view):
        return role_required("admin", "manager")(view)

    def finance_required(view):
        return role_required("admin", "manager")(view)

    def work_order_write_required(view):
        return method_role_required("admin", "manager", "technician")(view)

    def work_order_edit_required(view):
        return role_required("admin", "manager", "technician")(view)

    def manager_write_required(view):
        return role_required("admin", "manager")(view)

    @app.errorhandler(403)
    def forbidden(_error):
        if session.get("user_id"):
            flash("Ehhez a művelethez nincs jogosultságod.", "danger")
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

    @app.cli.command("seed-role-users")
    def seed_role_users():
        """Create local role test users. Do not use in production."""
        if os.environ.get("FLASK_ENV", "").lower() == "production":
            raise click.ClickException(
                "A seed-role-users parancs production környezetben nem futtatható."
            )
        demo_users = {
            "admin": ("admin", "AdminDemo123!"),
            "manager": ("manager", "ManagerDemo123!"),
            "technician": ("technician", "TechnicianDemo123!"),
            "viewer": ("viewer", "ViewerDemo123!"),
        }
        for username, (role, password) in demo_users.items():
            user = User.query.filter_by(username=username).first()
            if user is None:
                user = User(username=username)
                db.session.add(user)
            user.password_hash = generate_password_hash(password)
            user.role = role
            user.is_admin = role == "admin"
            user.is_active = True
        db.session.commit()
        click.echo("Szerepkör tesztfelhasználók létrehozva/frissítve.")
        for username, (role, password) in demo_users.items():
            click.echo(f"- {username} / {password} ({role})")

    def validate_user_role(role):
        if role not in USER_ROLES:
            abort(400)
        return role

    def sync_admin_flag(user):
        user.is_admin = user.role == "admin"

    def prevent_last_active_admin_change(user, new_role=None, new_active=None):
        removes_admin = new_role is not None and new_role != "admin"
        deactivates_admin = new_active is False
        if user.effective_role != "admin" or not user.is_active:
            return
        if not removes_admin and not deactivates_admin:
            return
        active_admin_count = User.query.filter_by(role="admin", is_active=True).count()
        if active_admin_count <= 1:
            flash("Az utolsó aktív adminisztrátor nem módosítható vagy deaktiválható.", "danger")
            return False
        return True

    def get_user_or_404(user_id):
        user = db.session.get(User, user_id)
        if user is None:
            abort(404)
        return user

    def set_user_role(user, role):
        user.role = validate_user_role(role)
        sync_admin_flag(user)

    def set_user_active(user, is_active):
        user.is_active = is_active

    def current_user_is(user):
        current = get_current_user()
        return bool(current and current.id == user.id)

    def protect_current_user_deactivation(user, is_active):
        if current_user_is(user) and not is_active:
            flash("A saját felhasználói fiókodat nem deaktiválhatod.", "danger")
            return False
        return True

    def protect_current_user_role_change(user, role):
        if current_user_is(user) and role != "admin":
            flash("A saját admin szerepkörödet nem módosíthatod.", "danger")
            return False
        return True

    def apply_user_management_change(user, role=None, is_active=None):
        if role is not None:
            if not protect_current_user_role_change(user, role):
                return False
            if prevent_last_active_admin_change(user, new_role=role) is False:
                return False
            set_user_role(user, role)
        if is_active is not None:
            if not protect_current_user_deactivation(user, is_active):
                return False
            if prevent_last_active_admin_change(user, new_active=is_active) is False:
                return False
            set_user_active(user, is_active)
        return True

    def user_search_query(search):
        query = User.query
        if search:
            query = query.filter(User.username.ilike(f"%{search}%"))
        return query.order_by(User.username.asc())

    def reject_inactive_login(user):
        if user and not user.is_active:
            flash("A felhasználói fiók inaktív. Fordulj egy adminisztrátorhoz.", "danger")
            return True
        return False

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
                role="admin",
                is_active=True,
            )
            db.session.add(user)
            action = "Létrehozva"
        else:
            user.password_hash = generate_password_hash(password)
            user.is_admin = True
            user.role = "admin"
            user.is_active = True
            action = "Frissítve"
        for location in Location.query.all():
            if location.name == "Main Warehouse":
                location.name = "Fő raktár"
            elif location.name.startswith("Stock Room"):
                location.name = location.name.replace("Stock Room", "Raktár", 1)
            elif location.name.startswith("Site"):
                location.name = location.name.replace("Site", "Helyszín", 1)
        seed_work_order_templates(WorkOrderTemplate)
        db.session.commit()
        print(f"{action}: '{username}' admin felhasználó.")

    @app.cli.command("reset-demo-data")
    @click.option("--yes", is_flag=True, help="Megerősítés bekérésének kihagyása.")
    def reset_demo_data_command(yes):
        """Reset local business data and create a small Parkl demo dataset."""
        if os.environ.get("FLASK_ENV", "").lower() == "production":
            raise click.ClickException(
                "A reset-demo-data parancs production környezetben nem futtatható."
            )
        if not yes and not click.confirm(
            "Ez törli a helyi projekt-, eszköz-, lokáció-, import- és mozgásadatokat. Folytatod?"
        ):
            click.echo("Megszakítva.")
            return

        summary = reset_demo_dataset(
            app,
            User,
            Project,
            Location,
            Device,
            DeviceUnit,
            StockMovement,
            UnassignedInvoiceItem,
            ImportBatch,
            ProjectDrawing,
            WorkOrder,
            WorkOrderMaterial,
            WorkOrderMeasurement,
            WorkOrderPhoto,
            WorkOrderTemplate,
        )
        click.echo(
            "Demo adatbázis újraépítve: "
            f"{summary['projects']} projekt, {summary['locations']} készlethely, "
            f"{summary['devices']} eszköz, {summary['movements']} mozgás, "
            f"{summary['invoice_items']} gazdátlan számlasor."
        )

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
            if reject_inactive_login(user):
                return render_template("login.html")
            if user and check_password_hash(user.password_hash, password):
                if user.is_admin and user.role != "admin":
                    user.role = "admin"
                    db.session.commit()
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
        active_devices = Device.query.filter(Device.archived_at.is_(None)).all()
        finance_visible = user_can("admin", "manager")
        active_invoice_items = (
            UnassignedInvoiceItem.query.filter(UnassignedInvoiceItem.archived_at.is_(None)).all()
            if finance_visible
            else []
        )
        attention_items = build_attention_items(
            active_devices, active_invoice_items, include_finance=finance_visible
        )
        stats = {
            "projects": Project.query.filter(Project.archived_at.is_(None)).count(),
            "locations": Location.query.filter(Location.archived_at.is_(None)).count(),
            "movements": StockMovement.query.count(),
            "in_stock": sum(1 for device in active_devices if device.status == "IN_STOCK"),
            "reserved": sum(1 for device in active_devices if device.status == "RESERVED"),
            "issued": sum(1 for device in active_devices if device.status == "ISSUED"),
            "installed": sum(1 for device in active_devices if device.status == "INSTALLED"),
            "awaiting_arrival": sum(1 for device in active_devices if is_awaiting_arrival(device)),
            "unassigned_invoices": sum(
                1
                for item in active_invoice_items
                if item.assignment_status == "unassigned"
            ),
            "financial_open": sum(1 for device in active_devices if is_financially_open(device)),
            "attention": len(attention_items),
        }
        recent_movements = (
            StockMovement.query.order_by(StockMovement.created_at.desc()).limit(6).all()
        )
        return render_template(
            "dashboard.html",
            stats=stats,
            recent_movements=recent_movements,
            attention_items=attention_items[:8],
        )

    @app.route("/attention")
    @login_required
    def attention():
        devices = Device.query.filter(Device.archived_at.is_(None)).all()
        finance_visible = user_can("admin", "manager")
        invoice_items = (
            UnassignedInvoiceItem.query.filter(UnassignedInvoiceItem.archived_at.is_(None)).all()
            if finance_visible
            else []
        )
        attention_items = build_attention_items(
            devices, invoice_items, include_finance=finance_visible
        )
        return render_template("attention.html", attention_items=attention_items)

    @app.route("/labels")
    @login_required
    def labels():
        active_devices = Device.query.filter(Device.archived_at.is_(None)).count()
        active_units = DeviceUnit.query.filter(DeviceUnit.archived_at.is_(None)).count()
        return render_template(
            "labels.html",
            active_devices=active_devices,
            active_units=active_units,
        )

    @app.route("/drawings")
    @login_required
    def drawings():
        drawing_list = (
            ProjectDrawing.query.join(Project)
            .filter(Project.archived_at.is_(None))
            .order_by(ProjectDrawing.updated_at.desc())
            .all()
        )
        projects_with_drawings = Project.query.filter(
            Project.archived_at.is_(None),
            Project.drawings.any(),
        ).order_by(Project.name.asc()).all()
        return render_template(
            "drawings.html",
            drawings=drawing_list,
            projects=projects_with_drawings,
        )

    @app.route("/import-export", methods=["GET", "POST"])
    @export_required
    def import_export():
        pending_import = session.get("pending_template_import")
        preview = None
        if request.method == "POST":
            action = request.form.get("action", "dry_run")
            if action == "confirm":
                if request.form.get("execute_import") != "on":
                    flash("Az importálás végrehajtásához jelöld be a megerősítést.", "danger")
                    return redirect(url_for("import_export"))
                if not pending_import or not os.path.exists(pending_import["path"]):
                    flash("Nincs érvényes előnézeti import. Töltsd fel újra a sablont.", "danger")
                    return redirect(url_for("import_export"))
                preview = parse_template_workbook(
                    pending_import["path"], Project, Device, Location
                )
                if preview["critical_error_count"]:
                    flash("Az import nem véglegesíthető, mert kritikus hibák vannak.", "danger")
                    return redirect(url_for("import_export"))
                result = import_template_workbook(
                    preview, Project, Device, Location, session["user_id"]
                )
                db.session.commit()
                session.pop("pending_template_import", None)
                flash(
                    "Sablonimport kész: "
                    f"{result['projects_created']} projekt, "
                    f"{result['locations_created']} készlethely és "
                    f"{result['devices_created']} eszköz létrehozva.",
                    "success",
                )
                return redirect(url_for("import_export"))

            upload = request.files.get("template_file")
            if not upload or upload.filename == "":
                flash("Válassz ki egy .xlsx sablonfájlt.", "danger")
                return redirect(url_for("import_export"))
            if not upload.filename.lower().endswith(".xlsx"):
                flash("Csak .xlsx fájl tölthető fel.", "danger")
                return redirect(url_for("import_export"))
            upload_dir = os.path.join(app.instance_path, UPLOAD_SUBDIR)
            os.makedirs(upload_dir, exist_ok=True)
            safe_name = secure_filename(upload.filename)
            upload_path = os.path.join(upload_dir, f"template_{uuid4().hex}_{safe_name}")
            upload.save(upload_path)
            preview = parse_template_workbook(upload_path, Project, Device, Location)
            session["pending_template_import"] = {"path": upload_path, "filename": safe_name}
            flash("Sablonimport előnézet elkészült. Az adatbázis még nem módosult.", "info")

        if preview is None and pending_import and os.path.exists(pending_import["path"]):
            preview = parse_template_workbook(
                pending_import["path"], Project, Device, Location
            )
        return render_template(
            "import_export.html",
            preview=preview,
            pending_import=session.get("pending_template_import"),
        )

    @app.route("/import-export/template")
    @export_required
    def import_template_download():
        return send_file(
            build_import_template_workbook(),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="Parkl_Infra_Manager_import_sablon.xlsx",
        )

    @app.route("/import-export/export/<export_type>")
    @export_required
    def data_export(export_type):
        if export_type not in {"devices", "projects", "locations"}:
            abort(404)
        return send_file(
            build_data_export_workbook(export_type, Project, Device, Location),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"Parkl_{export_type}_export.xlsx",
        )

    @app.route("/help")
    @login_required
    def help_page():
        return render_template("help.html")

    @app.route("/documents")
    @export_required
    def documents():
        return render_template("documents.html")

    @app.route("/admin")
    @admin_required
    def admin_tools():
        return render_template("admin_tools.html")

    @app.route("/admin/users")
    @admin_required
    def admin_users():
        search = request.args.get("q", "").strip()
        users = user_search_query(search).all()
        return render_template(
            "admin_users.html",
            users=users,
            search=search,
            roles=USER_ROLES,
            role_labels=USER_ROLE_LABELS,
        )

    @app.route("/admin/users/<int:user_id>/role", methods=["POST"])
    @admin_required
    def admin_user_role(user_id):
        user = get_user_or_404(user_id)
        role = validate_user_role(request.form.get("role", ""))
        if not apply_user_management_change(user, role=role):
            return redirect(url_for("admin_users"))
        db.session.commit()
        flash(f"{user.username} szerepköre módosítva.", "success")
        return redirect(url_for("admin_users"))

    @app.route("/admin/users/<int:user_id>/toggle-active", methods=["POST"])
    @admin_required
    def admin_user_toggle_active(user_id):
        user = get_user_or_404(user_id)
        new_active = not user.is_active
        if not apply_user_management_change(user, is_active=new_active):
            return redirect(url_for("admin_users"))
        db.session.commit()
        state = "aktiválva" if user.is_active else "deaktiválva"
        flash(f"{user.username} felhasználó {state}.", "success")
        return redirect(url_for("admin_users"))

    @app.route("/legacy")
    @admin_required
    def legacy():
        recent_batches = (
            ImportBatch.query.filter(ImportBatch.archived_at.is_(None))
            .order_by(ImportBatch.created_at.desc())
            .limit(8)
            .all()
        )
        return render_template("legacy.html", recent_batches=recent_batches)

    @app.route("/work-orders")
    @login_required
    def work_orders():
        query = WorkOrder.query.filter(WorkOrder.archived_at.is_(None))
        search = request.args.get("q", "").strip()
        work_type = request.args.get("work_type", "").strip()
        status = request.args.get("status", "").strip()
        date_from = optional_date(request.args.get("date_from"))
        date_to = optional_date(request.args.get("date_to"))
        if search:
            term = f"%{search}%"
            query = query.filter(
                or_(
                    WorkOrder.number.ilike(term),
                    WorkOrder.customer_name.ilike(term),
                    WorkOrder.site_name.ilike(term),
                    WorkOrder.technician_name.ilike(term),
                )
            )
        if work_type in WORK_ORDER_TYPE_LABELS:
            query = query.filter(WorkOrder.work_type == work_type)
        if status in WORK_ORDER_STATUS_LABELS:
            query = query.filter(WorkOrder.status == status)
        if date_from:
            query = query.filter(WorkOrder.work_date >= date_from)
        if date_to:
            query = query.filter(WorkOrder.work_date <= date_to)
        return render_template(
            "work_orders.html",
            work_orders=query.order_by(WorkOrder.created_at.desc()).all(),
            work_order_types=WORK_ORDER_TYPE_LABELS,
            work_order_statuses=WORK_ORDER_STATUS_LABELS,
            search=search,
            selected_work_type=work_type,
            selected_status=status,
            date_from=date_from,
            date_to=date_to,
        )

    @app.route("/work-orders/new", methods=["GET", "POST"])
    @work_order_edit_required
    def work_order_new():
        template = None
        template_id = optional_int(request.args.get("template_id"))
        if template_id:
            template = WorkOrderTemplate.query.get_or_404(template_id)
        if request.method == "POST":
            work_order = WorkOrder(
                number=request.form.get("number", "").strip(),
                work_type=request.form.get("work_type", "").strip(),
                created_date=optional_date(request.form.get("created_date")) or date.today(),
                created_by_id=session["user_id"],
            )
            error = update_work_order_from_form(work_order, request.form)
            if error:
                flash(error, "danger")
            elif WorkOrder.query.filter_by(number=work_order.number).first():
                flash("Ezzel a munkalapszámmal már létezik munkalap.", "danger")
            else:
                db.session.add(work_order)
                db.session.flush()
                replace_work_order_rows(work_order, request.form, WorkOrderMaterial, WorkOrderMeasurement)
                save_work_order_uploads(app, work_order, request.files, request.form, WorkOrderPhoto)
                db.session.commit()
                flash("A munkalap létrejött.", "success")
                return redirect(url_for("work_order_detail", work_order_id=work_order.id))
        return render_template(
            "work_order_form.html",
            work_order=None,
            template=template,
            template_materials=template_json_rows(template, "materials_json"),
            template_measurements=template_json_rows(template, "measurements_json"),
            suggested_number=next_work_order_number(WorkOrder),
            work_order_types=WORK_ORDER_TYPE_LABELS,
            work_order_statuses=WORK_ORDER_STATUS_LABELS,
            photo_categories=WORK_ORDER_PHOTO_CATEGORY_LABELS,
        )

    @app.route("/work-orders/<int:work_order_id>")
    @login_required
    def work_order_detail(work_order_id):
        work_order = WorkOrder.query.get_or_404(work_order_id)
        return render_template(
            "work_order_detail.html",
            work_order=work_order,
            photo_categories=WORK_ORDER_PHOTO_CATEGORY_LABELS,
        )

    @app.route("/work-orders/<int:work_order_id>/edit", methods=["GET", "POST"])
    @work_order_edit_required
    def work_order_edit(work_order_id):
        work_order = WorkOrder.query.get_or_404(work_order_id)
        if request.method == "POST":
            old_number = work_order.number
            error = update_work_order_from_form(work_order, request.form)
            duplicate = (
                WorkOrder.query.filter(WorkOrder.id != work_order.id)
                .filter(WorkOrder.number == work_order.number)
                .first()
            )
            if error:
                work_order.number = old_number
                flash(error, "danger")
            elif duplicate:
                work_order.number = old_number
                flash("Ezzel a munkalapszámmal már létezik másik munkalap.", "danger")
            else:
                replace_work_order_rows(work_order, request.form, WorkOrderMaterial, WorkOrderMeasurement)
                save_work_order_uploads(app, work_order, request.files, request.form, WorkOrderPhoto)
                db.session.commit()
                flash("A munkalap módosítva.", "success")
                return redirect(url_for("work_order_detail", work_order_id=work_order.id))
        return render_template(
            "work_order_form.html",
            work_order=work_order,
            template=None,
            template_materials=[],
            template_measurements=[],
            work_order_types=WORK_ORDER_TYPE_LABELS,
            work_order_statuses=WORK_ORDER_STATUS_LABELS,
            photo_categories=WORK_ORDER_PHOTO_CATEGORY_LABELS,
        )

    @app.route("/work-orders/<int:work_order_id>/copy", methods=["POST"])
    @work_order_edit_required
    def work_order_copy(work_order_id):
        source = WorkOrder.query.get_or_404(work_order_id)
        copied = copy_work_order(source, session["user_id"], WorkOrder, WorkOrderMaterial, WorkOrderMeasurement)
        db.session.add(copied)
        db.session.commit()
        flash("A munkalap másolata létrejött tervezetként.", "success")
        return redirect(url_for("work_order_edit", work_order_id=copied.id))

    @app.route("/work-orders/<int:work_order_id>/archive", methods=["POST"])
    @work_order_edit_required
    def work_order_archive(work_order_id):
        work_order = WorkOrder.query.get_or_404(work_order_id)
        work_order.archived_at = now_utc()
        db.session.commit()
        flash("A munkalap archiválva.", "info")
        return redirect(url_for("work_orders"))

    @app.route("/work-orders/<int:work_order_id>/pdf")
    @export_required
    def work_order_pdf(work_order_id):
        work_order = WorkOrder.query.get_or_404(work_order_id)
        pdf_buffer = build_work_order_pdf(app, work_order)
        work_order.status = "pdf_generated"
        work_order.pdf_generated_at = now_utc()
        db.session.commit()
        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=secure_filename(f"MUNKALAP_{work_order.number}.pdf"),
        )

    @app.route("/work-orders/files/<path:filename>")
    @login_required
    def work_order_file(filename):
        return send_from_directory(
            os.path.join(app.instance_path, WORK_ORDER_UPLOAD_SUBDIR),
            filename,
        )

    @app.route("/work-order-templates")
    @login_required
    def work_order_templates():
        templates = (
            WorkOrderTemplate.query.filter(WorkOrderTemplate.archived_at.is_(None))
            .order_by(WorkOrderTemplate.name.asc())
            .all()
        )
        return render_template(
            "work_order_templates.html",
            templates=templates,
            work_order_types=WORK_ORDER_TYPE_LABELS,
        )

    @app.route("/work-order-templates/new", methods=["GET", "POST"])
    @manager_write_required
    def work_order_template_new():
        template = WorkOrderTemplate()
        if request.method == "POST":
            error = update_work_order_template_from_form(template, request.form)
            if error:
                flash(error, "danger")
            elif WorkOrderTemplate.query.filter_by(name=template.name).first():
                flash("Ezzel a névvel már létezik sablon.", "danger")
            else:
                db.session.add(template)
                db.session.commit()
                flash("A munkalap sablon létrejött.", "success")
                return redirect(url_for("work_order_templates"))
        return render_template(
            "work_order_template_form.html",
            template=None,
            work_order_types=WORK_ORDER_TYPE_LABELS,
        )

    @app.route("/work-order-templates/<int:template_id>/edit", methods=["GET", "POST"])
    @manager_write_required
    def work_order_template_edit(template_id):
        template = WorkOrderTemplate.query.get_or_404(template_id)
        if request.method == "POST":
            error = update_work_order_template_from_form(template, request.form)
            duplicate = (
                WorkOrderTemplate.query.filter(WorkOrderTemplate.id != template.id)
                .filter(WorkOrderTemplate.name == template.name)
                .first()
            )
            if error:
                flash(error, "danger")
            elif duplicate:
                flash("Ezzel a névvel már létezik másik sablon.", "danger")
            else:
                db.session.commit()
                flash("A munkalap sablon módosítva.", "success")
                return redirect(url_for("work_order_templates"))
        return render_template(
            "work_order_template_form.html",
            template=template,
            work_order_types=WORK_ORDER_TYPE_LABELS,
        )

    @app.route("/work-order-templates/<int:template_id>/archive", methods=["POST"])
    @manager_write_required
    def work_order_template_archive(template_id):
        template = WorkOrderTemplate.query.get_or_404(template_id)
        template.archived_at = now_utc()
        db.session.commit()
        flash("A munkalap sablon archiválva.", "info")
        return redirect(url_for("work_order_templates"))

    @app.route("/projects")
    @write_required
    def projects():
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

    @app.route("/projects/new", methods=["GET", "POST"])
    @manager_write_required
    def project_new():
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
                project = Project(
                    name=name,
                    code=code,
                    customer=customer,
                    status=status,
                    notes=notes,
                )
                db.session.add(project)
                db.session.commit()
                flash("A projekt létrejött.", "success")
                return redirect(url_for("project_detail", project_id=project.id))
        return render_template(
            "project_form.html",
            project=None,
            project_statuses=PROJECT_STATUS_LABELS,
            form_title="Új projekt",
            submit_label="Projekt létrehozása",
            cancel_url=url_for("projects"),
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
        drawings = (
            ProjectDrawing.query.filter_by(project_id=project.id)
            .order_by(ProjectDrawing.updated_at.desc())
            .all()
        )
        finance_summary = {
            "device_count": len(devices),
            "quantity": sum(device.quantity or 0 for device in devices),
            **device_currency_totals(devices),
            "invoice_value": sum(device.invoice_value or 0 for device in devices),
            "ordered": sum(1 for device in devices if device.is_ordered),
            "arrived": sum(1 for device in devices if device.has_arrived),
            "issued": sum(1 for device in devices if device.status == "ISSUED"),
            "installed": sum(1 for device in devices if device.status == "INSTALLED"),
            "returned": sum(1 for device in devices if device.status == "RETURNED"),
            "unpaid_supplier_invoice_count": sum(
                1
                for device in devices
                if device.supplier_invoice_number and device.supplier_invoice_paid is not True
            ),
            "awaiting_arrival_count": sum(1 for device in devices if is_awaiting_arrival(device)),
        }
        finance_visible = user_can("admin", "manager")
        attention_items = [
            {
                "device": device,
                "reasons": device_attention_reasons(device, include_finance=finance_visible),
            }
            for device in devices
            if device_attention_reasons(device, include_finance=finance_visible)
        ]
        return render_template(
            "project_detail.html",
            project=project,
            devices=devices,
            movements=movements,
            drawings=drawings,
            finance_summary=finance_summary,
            attention_items=attention_items,
        )

    @app.route("/projects/<int:project_id>/pdf/<pdf_type>")
    @export_required
    def project_pdf(project_id, pdf_type):
        project = Project.query.get_or_404(project_id)
        devices = (
            Device.query.filter_by(project_id=project.id)
            .filter(Device.archived_at.is_(None))
            .order_by(Device.asset_tag.asc())
            .all()
        )
        if pdf_type not in {"equipment", "issue", "installation", "finance"}:
            abort(404)

        pdf_buffer = build_project_pdf(project, devices, pdf_type)
        filenames = {
            "equipment": "projekt-eszkozlista",
            "issue": "kiadasi-lista",
            "installation": "telepitesi-lista",
            "finance": "penzugyi-osszesito",
        }
        filename = f"{project.code}-{filenames[pdf_type]}.pdf"
        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )

    @app.route("/projects/<int:project_id>/qr")
    @login_required
    def project_qr(project_id):
        project = Project.query.get_or_404(project_id)
        return qr_png_response(
            url_for("project_detail", project_id=project.id, _external=True),
            f"{project.code}-qr.png",
        )

    @app.route("/projects/<int:project_id>/drawings", methods=["POST"])
    @manager_write_required
    def project_drawing_create(project_id):
        project = Project.query.get_or_404(project_id)
        name = request.form.get("name", "").strip() or "Helyszíni rajz"
        upload = request.files.get("background_image")
        background_filename = None
        if upload and upload.filename:
            if not allowed_drawing_file(upload.filename):
                flash("Csak PNG, JPG, JPEG vagy WEBP alaprajz tölthető fel.", "danger")
                return redirect(url_for("project_detail", project_id=project.id) + "#drawings")
            background_filename = save_drawing_background(app, upload, project.id)

        drawing = ProjectDrawing(
            project_id=project.id,
            name=name,
            background_filename=background_filename,
            canvas_json=json.dumps({"version": "5.3.0", "objects": []}),
        )
        db.session.add(drawing)
        db.session.commit()
        flash("A rajz létrejött.", "success")
        return redirect(
            url_for("project_drawing_editor", project_id=project.id, drawing_id=drawing.id)
        )

    @app.route("/projects/<int:project_id>/drawings/<int:drawing_id>")
    @manager_write_required
    def project_drawing_editor(project_id, drawing_id):
        project = Project.query.get_or_404(project_id)
        drawing = ProjectDrawing.query.filter_by(
            id=drawing_id, project_id=project.id
        ).first_or_404()
        background_url = None
        if drawing.background_filename:
            background_url = url_for(
                "drawing_background", filename=drawing.background_filename
            )
        return render_template(
            "drawing_editor.html",
            project=project,
            drawing=drawing,
            background_url=background_url,
            icon_categories=DRAWING_ICON_CATEGORIES,
            line_types=DRAWING_LINE_TYPES,
        )

    @app.route("/projects/<int:project_id>/drawings/<int:drawing_id>/save", methods=["POST"])
    @manager_write_required
    def project_drawing_save(project_id, drawing_id):
        drawing = ProjectDrawing.query.filter_by(
            id=drawing_id, project_id=project_id
        ).first_or_404()
        payload = request.get_json(silent=True) or {}
        canvas_json = payload.get("canvas_json")
        if not isinstance(canvas_json, str):
            return jsonify({"ok": False, "error": "Hiányzó rajz JSON."}), 400
        drawing.canvas_json = canvas_json
        drawing.updated_at = now_utc()
        db.session.commit()
        return jsonify({"ok": True, "updated_at": drawing.updated_at.isoformat()})

    @app.route("/drawing-backgrounds/<path:filename>")
    @login_required
    def drawing_background(filename):
        upload_dir = os.path.join(app.instance_path, DRAWING_UPLOAD_SUBDIR)
        return send_from_directory(upload_dir, filename)

    @app.route("/projects/<int:project_id>/edit", methods=["GET", "POST"])
    @manager_write_required
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
            "project_form.html",
            project=project,
            project_statuses=PROJECT_STATUS_LABELS,
            form_title="Projekt szerkesztése",
            submit_label="Mentés",
            cancel_url=url_for("project_detail", project_id=project.id),
        )

    @app.route("/projects/<int:project_id>/archive", methods=["POST"])
    @manager_write_required
    def project_archive(project_id):
        project = Project.query.get_or_404(project_id)
        project.archived_at = now_utc()
        db.session.commit()
        flash("A projekt archiválva.", "info")
        return redirect(url_for("projects"))

    @app.route("/devices")
    @write_required
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
        selected_view = request.args.get("view", "all").strip() or "all"

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
        quick_filter = request.args.get("quick_filter", "").strip()
        workflow_filter = quick_filter or selected_view
        if workflow_filter == "financial_open" and not user_can("admin", "manager"):
            abort(403)
        if workflow_filter == "in_stock":
            device_list = [device for device in device_list if device.status == "IN_STOCK"]
        elif workflow_filter == "assigned":
            device_list = [device for device in device_list if device.project_id]
        elif workflow_filter == "issued":
            device_list = [device for device in device_list if device.status == "ISSUED"]
        elif workflow_filter == "installed":
            device_list = [device for device in device_list if device.status == "INSTALLED"]
        elif workflow_filter == "attention":
            device_list = [
                device
                for device in device_list
                if device_attention_reasons(device, include_finance=user_can("admin", "manager"))
            ]
        elif workflow_filter == "financial_open":
            device_list = [device for device in device_list if is_financially_open(device)]
        elif workflow_filter == "awaiting_arrival":
            device_list = [device for device in device_list if is_awaiting_arrival(device)]
        elif workflow_filter == "arrived_unassigned":
            device_list = [device for device in device_list if is_arrived_unassigned(device)]
        visible_summary = {
            "count": len(device_list),
            **device_currency_totals(device_list),
            "unpaid_invoice_count": (
                sum(1 for device in device_list if is_financially_open(device))
                if user_can("admin", "manager")
                else 0
            ),
            "awaiting_arrival_count": sum(1 for device in device_list if is_awaiting_arrival(device)),
        }
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
            quick_filter=quick_filter,
            selected_view=selected_view,
            visible_summary=visible_summary,
        )

    @app.route("/devices/new", methods=["GET", "POST"])
    @manager_write_required
    def device_new():
        projects = Project.query.filter(Project.archived_at.is_(None)).order_by(Project.name.asc()).all()
        locations = Location.query.filter(Location.archived_at.is_(None)).order_by(Location.name.asc()).all()
        if request.method == "POST":
            data = device_form_data(request.form)

            if not data["asset_tag"] or not data["device_type"]:
                flash("Az eszközazonosító és a kategória kötelező.", "danger")
            elif data["device_type"] not in DEVICE_CATEGORIES:
                flash("Érvénytelen eszközkategória.", "danger")
            elif data["currency"] and data["currency"] not in DEVICE_CURRENCIES:
                flash("Érvénytelen deviza. Válassz HUF vagy EUR értéket.", "danger")
            elif data["qr_mode"] not in DEVICE_QR_MODE_LABELS:
                flash("Érvénytelen QR mód.", "danger")
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
                return redirect(url_for("device_detail", device_id=device.id))
        return render_template(
            "device_new.html",
            projects=projects,
            locations=locations,
            categories=DEVICE_CATEGORIES,
        )

    @app.route("/devices/<int:device_id>")
    @login_required
    def device_detail(device_id):
        device = Device.query.get_or_404(device_id)
        projects = Project.query.filter(Project.archived_at.is_(None)).order_by(Project.name.asc()).all()
        locations = Location.query.filter(Location.archived_at.is_(None)).order_by(Location.name.asc()).all()
        units = (
            DeviceUnit.query.filter_by(device_id=device.id)
            .filter(DeviceUnit.archived_at.is_(None))
            .order_by(DeviceUnit.unit_code.asc())
            .all()
        )
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
            units=units,
        )

    @app.route("/devices/<int:device_id>/edit", methods=["GET", "POST"])
    @manager_write_required
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
            elif data["currency"] and data["currency"] not in DEVICE_CURRENCIES:
                flash("Érvénytelen deviza. Válassz HUF vagy EUR értéket.", "danger")
            elif data["qr_mode"] not in DEVICE_QR_MODE_LABELS:
                flash("Érvénytelen QR mód.", "danger")
            elif not device_quantity_supports_existing_units(device, data["quantity"]):
                flash(
                    "A mennyiség nem lehet kisebb a már létrehozott aktív példányok számánál.",
                    "danger",
                )
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

    @app.route("/devices/<int:device_id>/qr")
    @login_required
    def device_qr(device_id):
        device = Device.query.get_or_404(device_id)
        return qr_png_response(
            url_for("device_detail", device_id=device.id, _external=True),
            f"{device.asset_tag}-qr.png",
        )

    @app.route("/devices/<int:device_id>/label")
    @login_required
    def device_label(device_id):
        device = Device.query.get_or_404(device_id)
        return render_template("device_label.html", device=device)

    @app.route("/devices/<int:device_id>/units")
    @login_required
    def device_units(device_id):
        device = Device.query.get_or_404(device_id)
        units = (
            DeviceUnit.query.filter_by(device_id=device.id)
            .filter(DeviceUnit.archived_at.is_(None))
            .order_by(DeviceUnit.unit_code.asc())
            .all()
        )
        return render_template("device_units.html", device=device, units=units)

    @app.route("/devices/<int:device_id>/units/create", methods=["GET", "POST"])
    @manager_write_required
    def device_units_create(device_id):
        device = Device.query.get_or_404(device_id)
        quantity = whole_device_quantity(device)
        active_units = (
            DeviceUnit.query.filter_by(device_id=device.id)
            .filter(DeviceUnit.archived_at.is_(None))
            .count()
        )
        if quantity is None:
            flash("Példányok csak pozitív egész mennyiségű tételből hozhatók létre.", "warning")
            return redirect(url_for("device_detail", device_id=device.id))
        missing_count = max(quantity - active_units, 0)
        if missing_count == 0:
            flash("Ehhez a tételhez már minden példány létrejött.", "info")
            return redirect(url_for("device_units", device_id=device.id))

        prefix = request.form.get("prefix", "").strip() or default_unit_code_prefix(device)
        start_number = optional_int(request.form.get("start_number")) or 1
        generated_codes = available_unit_codes(DeviceUnit, prefix, start_number, missing_count)

        if request.method == "POST":
            if request.form.get("confirm") != "1":
                flash("A példányok létrehozásához erősítsd meg a műveletet.", "warning")
            else:
                for unit_code in generated_codes:
                    db.session.add(DeviceUnit(device=device, unit_code=unit_code))
                if device.qr_mode != "individual":
                    device.qr_mode = "individual"
                db.session.commit()
                flash(f"{len(generated_codes)} eszközpéldány létrejött.", "success")
                return redirect(url_for("device_units", device_id=device.id))

        return render_template(
            "device_units_create.html",
            device=device,
            quantity=quantity,
            active_units=active_units,
            missing_count=missing_count,
            prefix=prefix,
            start_number=start_number,
            generated_codes=generated_codes,
        )

    @app.route("/devices/<int:device_id>/unit-labels.pdf")
    @login_required
    def device_unit_labels_pdf(device_id):
        device = Device.query.get_or_404(device_id)
        units = (
            DeviceUnit.query.filter_by(device_id=device.id)
            .filter(DeviceUnit.archived_at.is_(None))
            .order_by(DeviceUnit.unit_code.asc())
            .all()
        )
        if not units:
            flash("Nincs nyomtatható eszközpéldány.", "warning")
            return redirect(url_for("device_detail", device_id=device.id))
        unit_urls = {
            unit.id: url_for("device_unit_detail", unit_id=unit.id, _external=True)
            for unit in units
        }
        buffer = build_device_unit_labels_pdf(device, units, unit_urls)
        return send_file(
            buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=secure_filename(f"{device.asset_tag}_QR_cimkek.pdf"),
        )

    @app.route("/device-units/<int:unit_id>")
    @login_required
    def device_unit_detail(unit_id):
        unit = DeviceUnit.query.get_or_404(unit_id)
        return render_template("device_unit_detail.html", unit=unit, device=unit.device)

    @app.route("/device-units/<int:unit_id>/edit", methods=["GET", "POST"])
    @manager_write_required
    def device_unit_edit(unit_id):
        unit = DeviceUnit.query.get_or_404(unit_id)
        if request.method == "POST":
            unit_code = request.form.get("unit_code", "").strip()
            asset_tag = request.form.get("asset_tag", "").strip() or None
            serial_number = request.form.get("serial_number", "").strip() or None
            if not unit_code:
                flash("A példányazonosító kötelező.", "danger")
            elif DeviceUnit.query.filter(DeviceUnit.id != unit.id, DeviceUnit.unit_code == unit_code).first():
                flash("Ezzel a példányazonosítóval már létezik másik példány.", "danger")
            elif asset_tag and Device.query.filter_by(asset_tag=asset_tag).first():
                flash("Ez az eszközazonosító már egy csoportos tételhez tartozik.", "danger")
            elif asset_tag and DeviceUnit.query.filter(
                DeviceUnit.id != unit.id, DeviceUnit.asset_tag == asset_tag
            ).first():
                flash("Ez az eszközazonosító már másik példányhoz tartozik.", "danger")
            else:
                unit.unit_code = unit_code
                unit.asset_tag = asset_tag
                unit.serial_number = serial_number
                unit.notes = request.form.get("notes", "").strip() or None
                db.session.commit()
                flash("Az eszközpéldány módosítva.", "success")
                return redirect(url_for("device_unit_detail", unit_id=unit.id))
        return render_template("device_unit_edit.html", unit=unit, device=unit.device)

    @app.route("/device-units/<int:unit_id>/qr")
    @login_required
    def device_unit_qr(unit_id):
        unit = DeviceUnit.query.get_or_404(unit_id)
        return qr_png_response(
            url_for("device_unit_detail", unit_id=unit.id, _external=True),
            f"{unit.unit_code}-qr.png",
        )

    @app.route("/device-units/<int:unit_id>/label")
    @login_required
    def device_unit_label(unit_id):
        unit = DeviceUnit.query.get_or_404(unit_id)
        return render_template("device_unit_label.html", unit=unit, device=unit.device)

    @app.route("/device-units/<int:unit_id>/archive", methods=["POST"])
    @manager_write_required
    def device_unit_archive(unit_id):
        unit = DeviceUnit.query.get_or_404(unit_id)
        unit.archived_at = now_utc()
        db.session.commit()
        flash("Az eszközpéldány archiválva.", "info")
        return redirect(url_for("device_units", device_id=unit.device_id))

    @app.route("/devices/<int:device_id>/archive", methods=["POST"])
    @manager_write_required
    def device_archive(device_id):
        device = Device.query.get_or_404(device_id)
        device.archived_at = now_utc()
        db.session.commit()
        flash("Az eszköz archiválva.", "info")
        return redirect(url_for("devices"))

    @app.route("/devices/<int:device_id>/actions", methods=["POST"])
    @manager_write_required
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
        error = validate_movement(device, movement_type, to_location_id, project_id)
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
    @finance_required
    def unassigned_invoices():
        projects = Project.query.filter(Project.archived_at.is_(None)).order_by(Project.name.asc()).all()
        devices = (
            Device.query.filter(Device.archived_at.is_(None))
            .order_by(Device.device_type.asc(), Device.product_name.asc(), Device.asset_tag.asc())
            .all()
        )
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
                quantity = optional_float(request.form.get("quantity"))
                unit_price_huf = optional_float(request.form.get("unit_price_huf"))
                net_amount_huf = optional_float(request.form.get("net_amount_huf"))
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
                    quantity=quantity,
                    unit_price_huf=unit_price_huf,
                    net_amount_huf=net_amount_huf
                    if net_amount_huf is not None
                    else calculate_line_net_amount(quantity, unit_price_huf),
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
    @finance_required
    def unassigned_invoice_edit(item_id):
        item = UnassignedInvoiceItem.query.get_or_404(item_id)
        projects = Project.query.filter(Project.archived_at.is_(None)).order_by(Project.name.asc()).all()
        devices = (
            Device.query.filter(Device.archived_at.is_(None))
            .order_by(Device.device_type.asc(), Device.product_name.asc(), Device.asset_tag.asc())
            .all()
        )
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
    @finance_required
    def unassigned_invoice_archive(item_id):
        item = UnassignedInvoiceItem.query.get_or_404(item_id)
        item.archived_at = now_utc()
        db.session.commit()
        flash("A számlasor archiválva.", "info")
        return redirect(url_for("unassigned_invoices"))

    @app.route("/import", methods=["GET", "POST"])
    @app.route("/legacy/parkl-excel-import", methods=["GET", "POST"])
    @admin_required
    def legacy_parkl_excel_import():
        pending_import = session.get("pending_import")
        preview = None

        if request.method == "POST":
            action = request.form.get("action", "dry_run")
            if action == "confirm":
                if request.form.get("execute_import") != "on":
                    flash("Az importálás végrehajtásához jelöld be a megerősítést.", "danger")
                    return redirect(url_for("legacy_parkl_excel_import"))
                if not pending_import or not os.path.exists(pending_import["path"]):
                    flash("Nincs érvényes előnézeti import. Töltsd fel újra a fájlt.", "danger")
                    return redirect(url_for("legacy_parkl_excel_import"))

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
                return redirect(url_for("legacy_parkl_excel_import", batch_id=batch.id))

            upload = request.files.get("excel_file")
            if not upload or upload.filename == "":
                flash("Válassz ki egy .xlsx fájlt.", "danger")
                return redirect(url_for("legacy_parkl_excel_import"))
            if not upload.filename.lower().endswith(".xlsx"):
                flash("Csak .xlsx fájl tölthető fel.", "danger")
                return redirect(url_for("legacy_parkl_excel_import"))

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
    @app.route("/legacy/import-batches/<int:batch_id>")
    @admin_required
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
    @app.route("/legacy/import-batches/<int:batch_id>/rollback", methods=["POST"])
    @admin_required
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
    @app.route("/legacy/import-batches/<int:batch_id>/archive", methods=["POST"])
    @admin_required
    def import_batch_archive(batch_id):
        batch = ImportBatch.query.get_or_404(batch_id)
        batch.archived_at = now_utc()
        db.session.commit()
        flash("Az importcsomag archiválva.", "info")
        return redirect(url_for("legacy_parkl_excel_import"))

    @app.route("/locations")
    @write_required
    def locations():
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

    @app.route("/locations/new", methods=["GET", "POST"])
    @manager_write_required
    def location_new():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            location_type = request.form.get("location_type", "warehouse").strip()
            address = request.form.get("address", "").strip()
            notes = request.form.get("notes", "").strip()
            if not name:
                flash("A készlethely neve kötelező.", "danger")
            else:
                location = Location(
                    name=name,
                    location_type=location_type,
                    address=address,
                    notes=notes,
                )
                db.session.add(location)
                db.session.commit()
                flash("A készlethely létrejött.", "success")
                return redirect(url_for("location_detail", location_id=location.id))
        return render_template(
            "location_form.html",
            location=None,
            location_types=LOCATION_TYPE_LABELS,
            form_title="Új készlethely",
            submit_label="Készlethely létrehozása",
            cancel_url=url_for("locations"),
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
            location_summary={
                "quantity": sum(device.quantity or 0 for device in devices),
                **device_currency_totals(devices),
            },
        )

    @app.route("/locations/<int:location_id>/edit", methods=["GET", "POST"])
    @manager_write_required
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
            "location_form.html",
            location=location,
            location_types=LOCATION_TYPE_LABELS,
            form_title="Készlethely szerkesztése",
            submit_label="Mentés",
            cancel_url=url_for("location_detail", location_id=location.id),
        )

    @app.route("/locations/<int:location_id>/qr")
    @login_required
    def location_qr(location_id):
        location = Location.query.get_or_404(location_id)
        return qr_png_response(
            url_for("location_detail", location_id=location.id, _external=True),
            f"keszlethely-{location.id}-qr.png",
        )

    @app.route("/locations/<int:location_id>/archive", methods=["POST"])
    @manager_write_required
    def location_archive(location_id):
        location = Location.query.get_or_404(location_id)
        location.archived_at = now_utc()
        db.session.commit()
        flash("A készlethely archiválva.", "info")
        return redirect(url_for("locations"))

    @app.route("/movements", methods=["GET", "POST"])
    @write_required
    def movements():
        devices = (
            Device.query.filter(Device.archived_at.is_(None))
            .order_by(Device.device_type.asc(), Device.product_name.asc(), Device.asset_tag.asc())
            .all()
        )
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
                error = validate_movement(device, movement_type, to_location_id, project_id)
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


def reset_demo_dataset(
    app,
    User,
    Project,
    Location,
    Device,
    DeviceUnit,
    StockMovement,
    UnassignedInvoiceItem,
    ImportBatch,
    ProjectDrawing,
    WorkOrder,
    WorkOrderMaterial,
    WorkOrderMeasurement,
    WorkOrderPhoto,
    WorkOrderTemplate,
):
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
        db.session.flush()

    ProjectDrawing.query.delete()
    WorkOrderPhoto.query.delete()
    WorkOrderMeasurement.query.delete()
    WorkOrderMaterial.query.delete()
    WorkOrder.query.delete()
    WorkOrderTemplate.query.delete()
    UnassignedInvoiceItem.query.delete()
    StockMovement.query.delete()
    DeviceUnit.query.delete()
    Device.query.delete()
    ImportBatch.query.delete()
    Project.query.delete()
    Location.query.delete()
    db.session.flush()
    seed_work_order_templates(WorkOrderTemplate)

    projects = {
        "PRK-001": Project(
            code="PRK-001",
            name="Arena EV Upgrade",
            customer="Arena",
            status="active",
            notes="Demó EV-töltő bővítési projekt.",
        ),
        "PRK-002": Project(
            code="PRK-002",
            name="Office Park Sorompó projekt",
            customer="Office Park",
            status="active",
            notes="Demó sorompó és beléptetési projekt.",
        ),
    }
    db.session.add_all(projects.values())

    locations = {
        "warehouse": Location(name="Fő raktár", location_type="warehouse"),
        "service_car": Location(name="Szervizautó 1", location_type="service_vehicle"),
        "arena": Location(name="Arena helyszín", location_type="project_site"),
        "office": Location(name="Office Park helyszín", location_type="project_site"),
        "service": Location(name="Szerviz / javítás", location_type="service"),
    }
    db.session.add_all(locations.values())
    db.session.flush()

    devices = {
        "EV-001": Device(
            asset_tag="EV-001",
            device_type="EV charger",
            product_name="ABB Terra AC 22 kW charger",
            manufacturer="ABB",
            model="Terra AC 22 kW",
            quantity=1,
            currency="HUF",
            huf_value=420000,
        ),
        "NET-001": Device(
            asset_tag="NET-001",
            device_type="Router",
            product_name="Teltonika RUTX11 router",
            manufacturer="Teltonika",
            model="RUTX11",
            quantity=1,
            currency="HUF",
            huf_value=89000,
        ),
        "BOX-001": Device(
            asset_tag="BOX-001",
            device_type="Parkl box",
            product_name="Parkl Gate Controller Box",
            manufacturer="Parkl",
            model="Gate Controller Box",
            quantity=1,
            currency="HUF",
            huf_value=180000,
        ),
        "BAR-001": Device(
            asset_tag="BAR-001",
            device_type="Barrier gate",
            product_name="Sorompó vezérlő",
            manufacturer="Parkl",
            model="Sorompó vezérlő",
            quantity=1,
            currency="HUF",
            huf_value=240000,
        ),
        "CAM-001": Device(
            asset_tag="CAM-001",
            device_type="Camera",
            product_name="Hikvision ANPR kamera",
            manufacturer="Hikvision",
            model="ANPR",
            quantity=1,
            currency="HUF",
            huf_value=160000,
        ),
        "MAT-001": Device(
            asset_tag="MAT-001",
            device_type="Sticker",
            product_name="Matrica csomag",
            manufacturer="Parkl",
            model="Matrica csomag",
            quantity=50,
            currency="HUF",
            huf_value=25000,
        ),
    }
    db.session.add_all(devices.values())
    db.session.flush()

    warehouse_id = locations["warehouse"].id
    for device in devices.values():
        create_movement(
            device=device,
            movement_type="INBOUND",
            to_location_id=warehouse_id,
            notes="Demo kezdő bevételezés.",
            user_id=user.id,
        )
        apply_device_state(device, "INBOUND", warehouse_id, None)

    demo_actions = [
        (
            devices["NET-001"],
            "RESERVE",
            warehouse_id,
            projects["PRK-001"].id,
            "Demo előjegyzés Arena projektre.",
        ),
        (
            devices["BOX-001"],
            "ISSUE",
            locations["service_car"].id,
            projects["PRK-002"].id,
            "Demo kiadás szervizautóra.",
        ),
        (
            devices["BAR-001"],
            "ISSUE",
            locations["office"].id,
            projects["PRK-002"].id,
            "Demo kiadás telepítés előkészítéséhez.",
        ),
        (
            devices["BAR-001"],
            "INSTALL",
            locations["office"].id,
            projects["PRK-002"].id,
            "Demo telepítés Office Park helyszínen.",
        ),
        (
            devices["CAM-001"],
            "SERVICE",
            locations["service"].id,
            None,
            "Demo szervizbe küldés.",
        ),
    ]
    for device, movement_type, to_location_id, project_id, notes in demo_actions:
        create_movement(
            device=device,
            movement_type=movement_type,
            from_location_id=device.location_id,
            to_location_id=to_location_id,
            project_id=project_id,
            notes=notes,
            user_id=user.id,
        )
        apply_device_state(device, movement_type, to_location_id, project_id)

    invoice_items = [
        UnassignedInvoiceItem(
            invoice_number="TEL-2026-001",
            partner="Teltonika",
            invoice_date=date.today(),
            payment_deadline=date.today(),
            gross_amount_huf=113030,
            currency="HUF",
            description="Teltonika RUTX11 router számla",
            quantity=1,
            unit_price_huf=89000,
            net_amount_huf=89000,
            vat_amount_huf=24030,
            line_gross_amount_huf=113030,
            assignment_status="unassigned",
            notes="Demo nyitott, még nem hozzárendelt számlasor.",
        ),
        UnassignedInvoiceItem(
            invoice_number="SERV-2026-014",
            partner="Kamera Szerviz Kft.",
            invoice_date=date.today(),
            payment_deadline=date.today(),
            gross_amount_huf=63500,
            currency="HUF",
            description="Hikvision ANPR kamera szervizdíj",
            quantity=1,
            unit_price_huf=50000,
            net_amount_huf=50000,
            vat_amount_huf=13500,
            line_gross_amount_huf=63500,
            assignment_status="unassigned",
            notes="Demo nyitott szerviz számlasor.",
        ),
    ]
    db.session.add_all(invoice_items)
    db.session.commit()

    return {
        "projects": len(projects),
        "locations": len(locations),
        "devices": len(devices),
        "movements": StockMovement.query.count(),
        "invoice_items": len(invoice_items),
    }


def allowed_drawing_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_DRAWING_EXTENSIONS


def save_drawing_background(app, upload, project_id):
    upload_dir = os.path.join(app.instance_path, DRAWING_UPLOAD_SUBDIR)
    os.makedirs(upload_dir, exist_ok=True)
    extension = upload.filename.rsplit(".", 1)[1].lower()
    base_name = secure_filename(upload.filename.rsplit(".", 1)[0]) or "alaprajz"
    filename = f"project-{project_id}-{uuid4().hex}-{base_name}.{extension}"
    upload.save(os.path.join(upload_dir, filename))
    return filename


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


def optional_time(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError:
        return None


def work_order_type_label(value):
    return WORK_ORDER_TYPE_LABELS.get(value, value)


def work_order_status_label(value):
    return WORK_ORDER_STATUS_LABELS.get(value, value)


def work_order_photo_category_label(value):
    return WORK_ORDER_PHOTO_CATEGORY_LABELS.get(value, value)


def format_duration(minutes):
    if minutes is None:
        return "-"
    hours, remaining = divmod(minutes, 60)
    if hours and remaining:
        return f"{hours} óra {remaining} perc"
    if hours:
        return f"{hours} óra"
    return f"{remaining} perc"


def next_work_order_number(work_order_model):
    prefix = date.today().strftime("%Y%m%d")
    count = work_order_model.query.filter(work_order_model.number.like(f"{prefix}%")).count()
    return f"{prefix}_{count + 1:03d}"


def seed_work_order_templates(template_model):
    defaults = [
        ("AC töltő karbantartás", "maintenance"),
        ("Schneider hibaelhárítás", "troubleshooting"),
        ("Circontrol hibaelhárítás", "troubleshooting"),
        ("Teltonika csere", "troubleshooting"),
        ("Kábelcsere", "cable_replacement"),
        ("Helyszíni felmérés", "inspection"),
    ]
    existing = {item.name for item in template_model.query.all()}
    for name, work_type in defaults:
        if name not in existing:
            db.session.add(template_model(name=name, work_type=work_type))


def update_work_order_from_form(work_order, form):
    number = form.get("number", "").strip()
    work_type = form.get("work_type", "").strip()
    status = form.get("status", "draft").strip()
    if not number:
        return "A munkalap száma kötelező."
    if work_type not in WORK_ORDER_TYPE_LABELS:
        return "Válassz érvényes munkalap típust."
    if status not in WORK_ORDER_STATUS_LABELS:
        return "Válassz érvényes munkalap státuszt."

    work_order.number = number
    work_order.work_type = work_type
    work_order.created_date = optional_date(form.get("created_date")) or date.today()
    work_order.work_date = optional_date(form.get("work_date"))
    work_order.status = status
    work_order.customer_name = form.get("customer_name", "").strip() or None
    work_order.customer_address = form.get("customer_address", "").strip() or None
    work_order.contact_name = form.get("contact_name", "").strip() or None
    work_order.phone = form.get("phone", "").strip() or None
    work_order.email = form.get("email", "").strip() or None
    work_order.site_name = form.get("site_name", "").strip() or None
    work_order.site_address = form.get("site_address", "").strip() or None
    work_order.site_city = form.get("site_city", "").strip() or None
    work_order.site_notes = form.get("site_notes", "").strip() or None
    work_order.device_manufacturer = form.get("device_manufacturer", "").strip() or None
    work_order.device_type = form.get("device_type", "").strip() or None
    work_order.device_serial_number = form.get("device_serial_number", "").strip() or None
    work_order.device_purchase_date = optional_date(form.get("device_purchase_date"))
    work_order.arrival_time = optional_time(form.get("arrival_time"))
    work_order.departure_time = optional_time(form.get("departure_time"))
    work_order.fault_description = form.get("fault_description", "").strip() or None
    work_order.work_performed = form.get("work_performed", "").strip() or None
    work_order.labor_settlement = form.get("labor_settlement", "").strip() or None
    work_order.material_settlement = form.get("material_settlement", "").strip() or None
    work_order.notes = form.get("notes", "").strip() or None
    work_order.technician_name = form.get("technician_name", "").strip() or None
    work_order.second_technician = form.get("second_technician", "").strip() or None
    work_order.subcontractor = form.get("subcontractor", "").strip() or None
    return None


def replace_work_order_rows(work_order, form, material_model, measurement_model):
    work_order.materials.clear()
    material_names = form.getlist("material_name[]")
    for index, name in enumerate(material_names):
        name = name.strip()
        if not name:
            continue
        work_order.materials.append(
            material_model(
                name=name,
                item_number=list_value(form, "material_item_number[]", index),
                quantity=optional_float(list_value(form, "material_quantity[]", index)),
                unit=list_value(form, "material_unit[]", index),
                notes=list_value(form, "material_notes[]", index),
            )
        )

    work_order.measurements.clear()
    measurement_names = form.getlist("measurement_name[]")
    for index, name in enumerate(measurement_names):
        name = name.strip()
        if not name:
            continue
        work_order.measurements.append(
            measurement_model(
                name=name,
                value=list_value(form, "measurement_value[]", index),
                unit=list_value(form, "measurement_unit[]", index),
                notes=list_value(form, "measurement_notes[]", index),
            )
        )


def list_value(form, key, index):
    values = form.getlist(key)
    if index >= len(values):
        return None
    return values[index].strip() or None


def save_work_order_uploads(app, work_order, files, form, photo_model):
    upload_dir = os.path.join(app.instance_path, WORK_ORDER_UPLOAD_SUBDIR)
    os.makedirs(upload_dir, exist_ok=True)

    delete_ids = {optional_int(value) for value in form.getlist("delete_photo_ids[]")}
    for photo in list(work_order.photos):
        if photo.id in delete_ids:
            work_order.photos.remove(photo)

    for category in WORK_ORDER_PHOTO_CATEGORY_LABELS:
        for upload in files.getlist(f"photos_{category}"):
            if not upload or not upload.filename or not allowed_photo_file(upload.filename):
                continue
            extension = upload.filename.rsplit(".", 1)[1].lower()
            filename = secure_filename(f"{work_order.number}_{category}_{uuid4().hex}.{extension}")
            path = os.path.join(upload_dir, filename)
            upload.save(path)
            if valid_image_file(path):
                work_order.photos.append(photo_model(category=category, filename=filename))
            else:
                os.remove(path)

    for field, attribute in (
        ("technician_signature", "technician_signature_filename"),
        ("customer_signature", "customer_signature_filename"),
    ):
        data_url = form.get(field, "")
        if data_url.startswith("data:image/png;base64,"):
            filename = secure_filename(f"{work_order.number}_{field}_{uuid4().hex}.png")
            path = os.path.join(upload_dir, filename)
            with open(path, "wb") as output:
                output.write(base64.b64decode(data_url.split(",", 1)[1]))
            if valid_image_file(path):
                setattr(work_order, attribute, filename)
            else:
                os.remove(path)


def allowed_photo_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_PHOTO_EXTENSIONS


def valid_image_file(path):
    try:
        with PILImage.open(path) as image:
            image.verify()
        return True
    except (UnidentifiedImageError, OSError, ValueError):
        return False


def template_json_rows(template, attribute):
    if template is None:
        return []
    try:
        return json.loads(getattr(template, attribute) or "[]")
    except json.JSONDecodeError:
        return []


def update_work_order_template_from_form(template, form):
    name = form.get("name", "").strip()
    work_type = form.get("work_type", "").strip() or None
    if not name:
        return "A sablon neve kötelező."
    if work_type and work_type not in WORK_ORDER_TYPE_LABELS:
        return "Válassz érvényes munkalap típust."
    template.name = name
    template.work_type = work_type
    template.fault_description = form.get("fault_description", "").strip() or None
    template.work_performed = form.get("work_performed", "").strip() or None
    template.notes = form.get("notes", "").strip() or None
    template.materials_json = json.dumps(form_rows_to_dicts(form, "material"), ensure_ascii=False)
    template.measurements_json = json.dumps(form_rows_to_dicts(form, "measurement"), ensure_ascii=False)
    return None


def form_rows_to_dicts(form, prefix):
    names = form.getlist(f"{prefix}_name[]")
    keys = (
        ("item_number", f"{prefix}_item_number[]"),
        ("quantity", f"{prefix}_quantity[]"),
        ("unit", f"{prefix}_unit[]"),
        ("value", f"{prefix}_value[]"),
        ("notes", f"{prefix}_notes[]"),
    )
    rows = []
    for index, name in enumerate(names):
        if not name.strip():
            continue
        row = {"name": name.strip()}
        for output_key, form_key in keys:
            value = list_value(form, form_key, index)
            if value is not None:
                row[output_key] = value
        rows.append(row)
    return rows


def copy_work_order(source, user_id, work_order_model, material_model, measurement_model):
    copied = work_order_model(
        number=f"{source.number}-M-{uuid4().hex[:4].upper()}",
        work_type=source.work_type,
        created_date=date.today(),
        work_date=source.work_date,
        status="draft",
        customer_name=source.customer_name,
        customer_address=source.customer_address,
        contact_name=source.contact_name,
        phone=source.phone,
        email=source.email,
        site_name=source.site_name,
        site_address=source.site_address,
        site_city=source.site_city,
        site_notes=source.site_notes,
        device_manufacturer=source.device_manufacturer,
        device_type=source.device_type,
        device_serial_number=source.device_serial_number,
        device_purchase_date=source.device_purchase_date,
        fault_description=source.fault_description,
        work_performed=source.work_performed,
        labor_settlement=source.labor_settlement,
        material_settlement=source.material_settlement,
        notes=source.notes,
        technician_name=source.technician_name,
        second_technician=source.second_technician,
        subcontractor=source.subcontractor,
        created_by_id=user_id,
    )
    copied.materials = [
        material_model(
            name=item.name,
            item_number=item.item_number,
            quantity=item.quantity,
            unit=item.unit,
            notes=item.notes,
        )
        for item in source.materials
    ]
    copied.measurements = [
        measurement_model(name=item.name, value=item.value, unit=item.unit, notes=item.notes)
        for item in source.measurements
    ]
    return copied


def calculate_huf_value(quantity, unit_net_price, currency):
    if currency == "HUF" and quantity is not None and unit_net_price is not None:
        return quantity * unit_net_price
    return None


def calculate_imported_huf_value(quantity, unit_net_price, currency, excel_huf_value):
    if excel_huf_value is not None:
        if quantity is not None and unit_net_price is not None:
            return quantity * excel_huf_value
        return excel_huf_value
    return calculate_huf_value(quantity, unit_net_price, currency)


def calculate_line_net_amount(quantity, unit_price):
    if quantity is not None and unit_price is not None:
        return quantity * unit_price
    return None


def device_currency_totals(devices):
    totals = {
        "net_huf": 0,
        "net_eur": 0,
        "gross_huf": 0,
        "gross_eur": 0,
        "missing_currency_count": 0,
    }
    for device in devices:
        if device.currency not in {"HUF", "EUR"}:
            totals["missing_currency_count"] += 1
            continue
        currency_key = device.currency.lower()
        if device.total_net_price is not None:
            totals[f"net_{currency_key}"] += device.total_net_price
        if device.total_gross_price is not None:
            totals[f"gross_{currency_key}"] += device.total_gross_price
    return totals


def line_net_amount(item):
    if item.net_amount_huf is not None:
        return item.net_amount_huf
    return calculate_line_net_amount(item.quantity, item.unit_price_huf)


def status_label(value):
    return STATUS_LABELS.get(value, value)


def movement_type_label(value):
    return MOVEMENT_TYPE_LABELS.get(value, value)


def category_label(value):
    return CATEGORY_LABELS.get(value, value)


def device_display_label(device):
    return device.human_label


def device_primary_label(device):
    return device.primary_label


def device_qr_mode_label(value):
    return DEVICE_QR_MODE_LABELS.get(value, value)


def available_device_movements(device):
    transitions = {
        "IN_STOCK": ["RESERVE", "ISSUE", "TRANSFER", "SERVICE", "SCRAP"],
        "RESERVED": ["ISSUE", "RETURN", "SCRAP"],
        "ISSUED": ["INSTALL", "RETURN", "TRANSFER"],
        "INSTALLED": ["RETURN", "SERVICE", "SCRAP"],
        "RETURNED": ["INBOUND", "TRANSFER", "ISSUE", "INSTALL"],
        "IN_SERVICE": ["RETURN", "SCRAP"],
        "SCRAPPED": [],
    }
    return transitions.get(device.status, [])


def whole_device_quantity(device):
    if device.quantity is None or device.quantity <= 0 or not float(device.quantity).is_integer():
        return None
    return int(device.quantity)


def device_quantity_supports_existing_units(device, quantity):
    active_unit_count = sum(1 for unit in device.units if unit.archived_at is None)
    if active_unit_count == 0:
        return True
    return (
        quantity is not None
        and float(quantity).is_integer()
        and int(quantity) >= active_unit_count
    )


def default_unit_code_prefix(device):
    value = device.asset_tag or f"DEVICE-{device.id}"
    return re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").upper()


def available_unit_codes(device_unit_model, prefix, start_number, count):
    clean_prefix = re.sub(r"[^A-Za-z0-9]+", "-", prefix).strip("-").upper() or "UNIT"
    width = max(3, len(str(start_number + count - 1)))
    codes = []
    number = max(start_number, 1)
    while len(codes) < count:
        code = f"{clean_prefix}-{number:0{width}d}"
        if not device_unit_model.query.filter_by(unit_code=code).first():
            codes.append(code)
        number += 1
    return codes


def status_badge_class(value):
    return {
        "IN_STOCK": "status-in-stock",
        "RESERVED": "status-reserved",
        "ISSUED": "status-issued",
        "INSTALLED": "status-installed",
        "RETURNED": "status-returned",
        "IN_SERVICE": "status-service",
        "SCRAPPED": "status-scrapped",
    }.get(value, "status-neutral")


def movement_badge_class(value):
    return {
        "INBOUND": "movement-inbound",
        "RESERVE": "movement-reserve",
        "ISSUE": "movement-issue",
        "INSTALL": "movement-install",
        "RETURN": "movement-return",
        "SERVICE": "movement-service",
        "SCRAP": "movement-scrap",
        "TRANSFER": "movement-transfer",
    }.get(value, "movement-neutral")


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


def format_vat_rate(value):
    if value is None:
        return "Nincs megadva"
    return f"{format_number(value)}%"


def device_money_text(device, field):
    value_map = {
        "unit_net": device.unit_net_price,
        "total_net": device.total_net_price,
        "unit_gross": device.unit_gross_price,
        "total_gross": device.total_gross_price,
    }
    value = value_map.get(field)
    if value is not None:
        currency = f" {device.currency}" if device.currency in DEVICE_CURRENCIES else ""
        suffix = "" if currency else " (deviza hiányzik)"
        return f"{format_number(value)}{currency}{suffix}"

    if device.currency not in DEVICE_CURRENCIES:
        return "Nem számolható: hiányzik a deviza"
    if field == "total_net":
        if device.quantity is None:
            return "Nem számolható: hiányzik a mennyiség"
        if device.unit_net_price is None and device.huf_value is None:
            return "Nem számolható: hiányzik az egységár"
    if field in {"unit_gross", "total_gross"}:
        if device.vat_rate is None:
            return "Nem számolható: hiányzik az ÁFA"
        if device.unit_net_price is None:
            return "Nem számolható: hiányzik az egységár"
        if field == "total_gross" and device.quantity is None and device.huf_value is None:
            return "Nem számolható: hiányzik a mennyiség"
    if field == "unit_net":
        return "Nincs megadva"
    return "Nem számolható"


def is_awaiting_arrival(device):
    return device.is_ordered is True and device.has_arrived is not True


def is_arrived_unassigned(device):
    return device.has_arrived is True and not device.project_id and not device.location_id


def is_financially_open(device):
    return (
        bool(device.supplier_invoice_number) and device.supplier_invoice_paid is not True
    ) or (
        bool(device.shipping_invoice_number) and device.shipping_invoice_paid is not True
    )


def device_attention_reasons(device, include_finance=True):
    reasons = []
    today = date.today()
    if (
        device.is_ordered is True
        and device.has_arrived is not True
        and device.planned_arrival_date
        and device.planned_arrival_date < today
    ):
        reasons.append("Megrendelve, de a tervezett érkezési dátum lejárt.")
    if is_arrived_unassigned(device):
        reasons.append("Megérkezett, de nincs projekthez vagy készlethelyhez rendelve.")
    if include_finance and device.supplier_invoice_number and device.supplier_invoice_paid is not True:
        reasons.append("Beszállítói számla van, de nincs fizetettként jelölve.")
    if include_finance and device.shipping_invoice_number and device.shipping_invoice_paid is not True:
        reasons.append("Szállítmányozói számla van, de nincs fizetettként jelölve.")
    if device.project and (
        not device.project.code
        or not device.project.name
        or device.project.name == device.project.code
        or not device.project.customer
    ):
        reasons.append("A kapcsolódó projekt adatai hiányosak.")
    if device.source_sheet and not device.product_name:
        reasons.append("Importált sorból hiányzik a terméknév.")
    if not device.device_type or device.device_type not in CATEGORY_LABELS:
        reasons.append("Hiányzó vagy ismeretlen kategória.")
    if device.source_sheet and (device.quantity is None or device.quantity <= 0):
        reasons.append("Hiányzó vagy nulla mennyiség.")
    if device.status not in STATUS_LABELS:
        reasons.append("Ismeretlen státusz.")
    if device.status == "INSTALLED" and not device.project_id:
        reasons.append("Telepített eszköz projekthozzárendelés nélkül.")
    if device.status in {"ISSUED", "INSTALLED"} and not device.location_id:
        reasons.append("Kiadott vagy telepített eszköz lokáció nélkül.")
    return reasons


def invoice_attention_reasons(item):
    reasons = []
    if item.assignment_status == "unassigned":
        reasons.append("A számlasor nincs hozzárendelve.")
    if not item.invoice_number:
        reasons.append("Hiányzik a számlaszám.")
    if not item.partner:
        reasons.append("Hiányzik a partner.")
    if not item.description:
        reasons.append("Hiányzik a megnevezés.")
    if item.line_gross_amount_huf is None and item.gross_amount_huf is None:
        reasons.append("Hiányzik a bruttó összeg.")
    return reasons


def build_attention_items(devices, invoice_items, include_finance=True):
    items = []
    for device in devices:
        reasons = device_attention_reasons(device, include_finance=include_finance)
        if reasons:
            items.append(
                {
                    "type": "Eszköz",
                    "name": device_primary_label(device),
                    "reasons": reasons,
                    "project": device.project.code if device.project else "-",
                    "supplier": device.supplier_manufacturer or device.manufacturer or "-",
                    "invoice": (
                        device.supplier_invoice_number
                        or device.shipping_invoice_number
                        or "-"
                        if include_finance
                        else "-"
                    ),
                    "source": f"{device.source_sheet or '-'} / {device.source_row_number or '-'}",
                    "detail_url": url_for("device_detail", device_id=device.id),
                    "edit_url": url_for("device_edit", device_id=device.id),
                }
            )
    for item in invoice_items:
        reasons = invoice_attention_reasons(item)
        if reasons:
            items.append(
                {
                    "type": "Számlasor",
                    "name": item.description or item.invoice_number or "Névtelen számlasor",
                    "reasons": reasons,
                    "project": item.assigned_project.code if item.assigned_project else "-",
                    "supplier": item.partner or "-",
                    "invoice": item.invoice_number or "-",
                    "source": f"{item.source_sheet or '-'} / {item.source_row_number or '-'}",
                    "detail_url": None,
                    "edit_url": url_for("unassigned_invoice_edit", item_id=item.id),
                }
            )
    return items


def build_project_pdf(project, devices, pdf_type):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.2 * cm,
        leftMargin=1.2 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
    )
    styles = unicode_pdf_styles()
    story = []
    titles = {
        "equipment": "Projekt eszközlista",
        "issue": "Kiadási lista",
        "installation": "Telepítési lista",
        "finance": "Pénzügyi összesítő",
    }
    story.append(Paragraph(pdf_escape(titles[pdf_type]), styles["Title"]))
    story.append(Paragraph(pdf_escape(f"{project.code} - {project.name}"), styles["Heading2"]))
    story.append(Paragraph(pdf_escape(f"Ügyfél: {project.customer or '-'}"), styles["Normal"]))
    story.append(Paragraph(pdf_escape(f"Dátum: {date.today().isoformat()}"), styles["Normal"]))
    story.append(Spacer(1, 0.4 * cm))

    if pdf_type == "equipment":
        rows = [
            [
                "Tétel",
                "Mennyiség",
                "Deviza",
                "Egység nettó",
                "Összes nettó",
                "ÁFA %",
                "Egység bruttó",
                "Összes bruttó",
                "Státusz",
                "Lokáció",
                "Megjegyzés",
            ]
        ]
        pdf_devices = devices
        for device in pdf_devices:
            rows.append(
                [
                    device_primary_label(device),
                    format_number(device.quantity),
                    device.currency or "hiányzik",
                    device_money_text(device, "unit_net"),
                    device_money_text(device, "total_net"),
                    format_vat_rate(device.vat_rate),
                    device_money_text(device, "unit_gross"),
                    device_money_text(device, "total_gross"),
                    status_label(device.status),
                    device.location.name if device.location else "-",
                    device.assignment_notes or device.subtype_note or "-",
                ]
            )
    elif pdf_type in {"issue", "installation"}:
        wanted_status = "ISSUED" if pdf_type == "issue" else "INSTALLED"
        rows = [["Azonosító", "Termék", "Mennyiség", "Lokáció", "Megjegyzés"]]
        pdf_devices = [device for device in devices if device.status == wanted_status]
        for device in pdf_devices:
            rows.append(
                [
                    device.asset_tag or "-",
                    device.product_name or device.model or "-",
                    format_number(device.quantity),
                    device.location.name if device.location else "-",
                    device.assignment_notes or device.subtype_note or "-",
                ]
            )
    else:
        rows = [["Beszállító", "Számlaszám", "Fizetve", "Deviza", "Egység nettó", "Összes nettó", "ÁFA %", "Egység bruttó", "Összes bruttó", "Tétel"]]
        pdf_devices = devices
        for device in pdf_devices:
            invoice_number = device.supplier_invoice_number or device.shipping_invoice_number or "-"
            paid = "Igen" if (device.supplier_invoice_paid or device.shipping_invoice_paid) else "Nem"
            rows.append(
                [
                    device.supplier_manufacturer or device.manufacturer or "-",
                    invoice_number,
                    paid,
                    device.currency or "hiányzik",
                    device_money_text(device, "unit_net"),
                    device_money_text(device, "total_net"),
                    format_vat_rate(device.vat_rate),
                    device_money_text(device, "unit_gross"),
                    device_money_text(device, "total_gross"),
                    device.product_name or device.model or device.asset_tag or "-",
                ]
            )
        totals = device_currency_totals(devices)
        unpaid_count = sum(1 for device in devices if is_financially_open(device))
        story.append(
            Paragraph(
                pdf_escape(
                    "Összes nettó projektérték: "
                    f"{format_number(totals['net_huf'])} HUF, "
                    f"{format_number(totals['net_eur'])} EUR; "
                    f"nyitott számlás tételek: {unpaid_count}"
                ),
                styles["Normal"],
            )
        )
        story.append(Spacer(1, 0.3 * cm))

    if len(rows) == 1:
        rows.append(["Nincs megjeleníthető tétel."] + [""] * (len(rows[0]) - 1))

    table = Table([[pdf_cell(cell, styles) for cell in row] for row in rows], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9eef5")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1d2733")),
                ("FONTNAME", (0, 0), (-1, 0), PDF_FONT_BOLD),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd3df")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f9fb")]),
            ]
        )
    )
    story.append(table)

    if pdf_type in {"issue", "installation"}:
        story.append(Spacer(1, 1.2 * cm))
        signature_rows = [
            ["Előkészítette", "Átvette"],
            ["\n\n____________________________", "\n\n____________________________"],
        ]
        signature_table = Table(signature_rows, colWidths=[8 * cm, 8 * cm])
        signature_table.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
        story.append(signature_table)

    doc.build(story)
    buffer.seek(0)
    return buffer


def build_device_unit_labels_pdf(device, units, unit_urls):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.2 * cm,
        leftMargin=1.2 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
    )
    styles = unicode_pdf_styles()
    rows = []
    current_row = []
    for unit in units:
        qr_buffer = BytesIO()
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=3,
        )
        qr.add_data(unit_urls[unit.id])
        qr.make(fit=True)
        qr.make_image(fill_color="#21182f", back_color="white").save(qr_buffer, format="PNG")
        qr_buffer.seek(0)
        qr_image = Image(qr_buffer, width=3.3 * cm, height=3.3 * cm)
        title = unit.asset_tag or unit.unit_code
        details = [
            Paragraph(pdf_escape(title), styles["Heading3"]),
            Paragraph(pdf_escape(device.product_name or device.model or device.asset_tag), styles["BodyText"]),
            Paragraph(pdf_escape(f"Példány: {unit.unit_code}"), styles["BodyText"]),
            Paragraph(pdf_escape(f"Sorozatszám: {unit.serial_number or '-'}"), styles["BodyText"]),
            qr_image,
        ]
        current_row.append(details)
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []
    if current_row:
        current_row.append("")
        rows.append(current_row)

    table = Table(rows, colWidths=[9.1 * cm, 9.1 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#6f42c1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d8d0e5")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    doc.build([table])
    buffer.seek(0)
    return buffer


def build_work_order_pdf(app, work_order):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.4 * cm,
        leftMargin=1.4 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.8 * cm,
        title=f"Munkalap {work_order.number}",
    )
    styles = unicode_pdf_styles()
    styles["Title"].textColor = colors.HexColor("#5b3f92")
    styles["Heading2"].textColor = colors.HexColor("#5b3f92")
    story = []

    logo_path = os.path.join(app.static_folder, "parkl-logo.png")
    if os.path.exists(logo_path):
        story.append(cropped_pdf_image(logo_path, max_width=3 * cm, max_height=1.8 * cm))
        story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph("Szerviz megrendelő / Munkalap / Jegyzőkönyv", styles["Title"]))
    story.append(Paragraph("Parkl Digital Technologies Kft. · 1051 Budapest, Arany János utca 15.", styles["Normal"]))
    story.append(Spacer(1, 0.35 * cm))

    story.append(
        work_order_pdf_key_value_table(
            [
                ("Munkalap száma", work_order.number),
                ("Munkalap típusa", work_order_type_label(work_order.work_type)),
                ("Létrehozás dátuma", work_order.created_date),
                ("Munkavégzés dátuma", work_order.work_date),
                ("Státusz", work_order_status_label(work_order.status)),
            ],
            styles,
        )
    )
    story.append(Spacer(1, 0.3 * cm))

    add_work_order_pdf_section(
        story,
        "Ügyfél adatok",
        [
            ("Ügyfél neve", work_order.customer_name),
            ("Cím", work_order.customer_address),
            ("Kapcsolattartó", work_order.contact_name),
            ("Telefonszám", work_order.phone),
            ("E-mail", work_order.email),
        ],
        styles,
    )
    add_work_order_pdf_section(
        story,
        "Helyszín",
        [
            ("Helyszín neve", work_order.site_name),
            ("Cím", work_order.site_address),
            ("Város", work_order.site_city),
            ("Megjegyzés", work_order.site_notes),
        ],
        styles,
    )
    add_work_order_pdf_section(
        story,
        "Készülék adatok",
        [
            ("Gyártó", work_order.device_manufacturer),
            ("Típus", work_order.device_type),
            ("Gyári szám", work_order.device_serial_number),
            ("Vásárlás dátuma", work_order.device_purchase_date),
        ],
        styles,
    )
    add_work_order_pdf_section(
        story,
        "Munkavégzés",
        [
            ("Érkezés időpontja", format_pdf_time(work_order.arrival_time)),
            ("Távozás időpontja", format_pdf_time(work_order.departure_time)),
            ("Helyszínen töltött idő", format_duration(work_order.duration_minutes)),
            ("Munkát végezte", work_order.technician_name),
            ("Második technikus", work_order.second_technician),
            ("Alvállalkozó", work_order.subcontractor),
        ],
        styles,
    )
    add_work_order_pdf_text(story, "Hiba leírása", work_order.fault_description, styles)
    add_work_order_pdf_text(story, "Elvégzett munka", work_order.work_performed, styles)
    add_work_order_pdf_section(
        story,
        "Elszámolás és megjegyzés",
        [
            ("Munka elszámolása", work_order.labor_settlement),
            ("Anyag elszámolása", work_order.material_settlement),
            ("Megjegyzés", work_order.notes),
        ],
        styles,
    )

    story.append(Paragraph("Felhasznált anyagok", styles["Heading2"]))
    material_rows = [["Anyag megnevezése", "Cikkszám", "Mennyiség", "Mértékegység", "Megjegyzés"]]
    for item in work_order.materials:
        material_rows.append(
            [item.name, item.item_number or "-", format_number(item.quantity), item.unit or "-", item.notes or "-"]
        )
    if len(material_rows) == 1:
        material_rows.append(["Nincs rögzített anyag.", "", "", "", ""])
    story.append(work_order_pdf_table(material_rows, styles))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("Mérések", styles["Heading2"]))
    measurement_rows = [["Mérés", "Érték", "Mértékegység", "Megjegyzés"]]
    for item in work_order.measurements:
        measurement_rows.append([item.name, item.value or "-", item.unit or "-", item.notes or "-"])
    if len(measurement_rows) == 1:
        measurement_rows.append(["Nincs rögzített mérés.", "", "", ""])
    story.append(work_order_pdf_table(measurement_rows, styles))
    story.append(Spacer(1, 0.4 * cm))

    upload_dir = os.path.join(app.instance_path, WORK_ORDER_UPLOAD_SUBDIR)
    signature_cells = []
    for label, filename in (
        ("Technikus aláírása", work_order.technician_signature_filename),
        ("Ügyfél aláírása", work_order.customer_signature_filename),
    ):
        content = [Paragraph(pdf_escape(label), styles["Normal"])]
        path = os.path.join(upload_dir, filename) if filename else None
        if path and os.path.exists(path) and valid_image_file(path):
            content.append(Image(path, width=6.5 * cm, height=2.4 * cm))
        else:
            content.append(Spacer(1, 2.4 * cm))
        signature_cells.append(content)
    signature_table = Table([signature_cells], colWidths=[8.5 * cm, 8.5 * cm])
    signature_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cfc6df")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(signature_table)

    if work_order.photos:
        story.append(PageBreak())
        story.append(Paragraph("Fotódokumentáció", styles["Title"]))
        for photo in work_order.photos:
            path = os.path.join(upload_dir, photo.filename)
            if not os.path.exists(path) or not valid_image_file(path):
                continue
            story.append(Paragraph(pdf_escape(work_order_photo_category_label(photo.category)), styles["Heading2"]))
            story.append(Image(path, width=16 * cm, height=10 * cm, kind="proportional"))
            story.append(Spacer(1, 0.35 * cm))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont(PDF_FONT_REGULAR, 8)
        canvas.setFillColor(colors.HexColor("#6e647d"))
        canvas.drawString(1.4 * cm, 0.8 * cm, f"Munkalap: {work_order.number}")
        canvas.drawRightString(A4[0] - 1.4 * cm, 0.8 * cm, f"{document.page}. oldal")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    return buffer


def add_work_order_pdf_section(story, title, rows, styles):
    story.append(Paragraph(pdf_escape(title), styles["Heading2"]))
    story.append(work_order_pdf_key_value_table(rows, styles))
    story.append(Spacer(1, 0.3 * cm))


def add_work_order_pdf_text(story, title, text, styles):
    story.append(Paragraph(pdf_escape(title), styles["Heading2"]))
    story.append(Paragraph(pdf_escape(text or "-").replace("\n", "<br/>"), styles["BodyText"]))
    story.append(Spacer(1, 0.3 * cm))


def work_order_pdf_key_value_table(rows, styles):
    data = [
        [pdf_cell(label, styles), pdf_cell(value if value not in (None, "") else "-", styles)]
        for label, value in rows
    ]
    table = Table(data, colWidths=[5 * cm, 12 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f2eef8")),
                ("FONTNAME", (0, 0), (0, -1), PDF_FONT_BOLD),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d8d0e5")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def work_order_pdf_table(rows, styles):
    table = Table([[pdf_cell(cell, styles) for cell in row] for row in rows], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#5b3f92")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), PDF_FONT_BOLD),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d8d0e5")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#faf8fd")]),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def format_pdf_time(value):
    return value.strftime("%H:%M") if value else "-"


def unicode_pdf_styles():
    register_pdf_fonts()
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = PDF_FONT_REGULAR
        if style.name in {"Title", "Heading1", "Heading2", "Heading3", "Heading4"}:
            style.fontName = PDF_FONT_BOLD
    return styles


def register_pdf_fonts():
    if PDF_FONT_REGULAR in pdfmetrics.getRegisteredFontNames():
        return
    font_dir = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
    regular_path = first_existing_path(
        [
            os.environ.get("PDF_FONT_REGULAR_PATH"),
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            os.path.join(font_dir, "Vera.ttf"),
        ]
    )
    bold_path = first_existing_path(
        [
            os.environ.get("PDF_FONT_BOLD_PATH"),
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            os.path.join(font_dir, "VeraBd.ttf"),
        ]
    )
    pdfmetrics.registerFont(TTFont(PDF_FONT_REGULAR, regular_path))
    pdfmetrics.registerFont(TTFont(PDF_FONT_BOLD, bold_path))
    pdfmetrics.registerFontFamily(
        PDF_FONT_REGULAR,
        normal=PDF_FONT_REGULAR,
        bold=PDF_FONT_BOLD,
        italic=PDF_FONT_REGULAR,
        boldItalic=PDF_FONT_BOLD,
    )


def first_existing_path(paths):
    for path in paths:
        if path and os.path.exists(path):
            return path
    raise RuntimeError("Nem található használható PDF betűkészlet.")


def cropped_pdf_image(path, max_width, max_height):
    with PILImage.open(path) as source:
        source.load()
        if source.mode in {"RGBA", "LA"}:
            alpha = source.getchannel("A")
            bounding_box = alpha.getbbox()
        else:
            bounding_box = source.getbbox()
        cropped = source.crop(bounding_box) if bounding_box else source.copy()
        image_buffer = BytesIO()
        cropped.save(image_buffer, format="PNG")
        image_buffer.seek(0)
        width, height = cropped.size
    scale = min(max_width / width, max_height / height)
    return Image(image_buffer, width=width * scale, height=height * scale)


def pdf_escape(value):
    text = "" if value is None else str(value)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def pdf_cell(value, styles):
    return Paragraph(pdf_escape(value), styles["BodyText"])


def now_utc():
    return datetime.now(timezone.utc)


def qr_png_response(target_url, filename):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(target_url)
    qr.make(fit=True)
    image = qr.make_image(fill_color="#21182f", back_color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(
        buffer,
        mimetype="image/png",
        as_attachment=request.args.get("download") == "1",
        download_name=secure_filename(filename),
    )


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
        "vat_rate": optional_float(form.get("vat_rate")),
        "qr_mode": form.get("qr_mode", "group").strip() or "group",
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
    net_amount_huf = optional_float(form.get("net_amount_huf"))
    item.net_amount_huf = (
        net_amount_huf
        if net_amount_huf is not None
        else calculate_line_net_amount(item.quantity, item.unit_price_huf)
    )
    item.vat_amount_huf = optional_float(form.get("vat_amount_huf"))
    item.line_gross_amount_huf = optional_float(form.get("line_gross_amount_huf"))
    item.assignment_status = assignment_status
    item.notes = form.get("notes", "").strip() or None
    item.assigned_project_id = assigned_project_id
    item.assigned_device_id = assigned_device_id


def build_import_template_workbook():
    workbook = Workbook()
    projects = workbook.active
    projects.title = "Projects"
    projects.append(TEMPLATE_PROJECT_HEADERS)
    projects.append(["PRK-100", "Minta EV projekt", "Minta Ügyfél Kft.", "Minta helyszín", "Budapest, Minta utca 1.", "active", "Példasor, import előtt törölhető."])

    devices = workbook.create_sheet("Devices")
    devices.append(TEMPLATE_DEVICE_HEADERS)
    devices.append(["PRK-100", "EV charger", "Schneider EVlink Pro AC", "Schneider", "EVB3S22N4", "", "EV-MINTA-001", 2, "HUF", 250000, 500000, 27, 317500, 635000, "Fő raktár", "IN_STOCK", "Példasor, import előtt törölhető."])

    locations = workbook.create_sheet("Locations")
    locations.append(TEMPLATE_LOCATION_HEADERS)
    locations.append(["Fő raktár", "warehouse", "Budapest", "Példa készlethely."])

    instructions = workbook.create_sheet("Instructions")
    instructions.append(["Parkl Infra Manager import sablon"])
    instructions.append(["A Projects és Devices munkalap használható. A Locations munkalap opcionális."])
    instructions.append(["Kötelező Project mezők: project_code, project_name új projekt esetén."])
    instructions.append(["Kötelező Device mezők: project_code, product_name, quantity, currency."])
    instructions.append(["Elfogadott deviza: HUF, EUR. Elfogadott Device státuszok: " + ", ".join(sorted(STATUS_LABELS))])
    instructions.append(["Elfogadott projekt státuszok: " + ", ".join(sorted(PROJECT_STATUS_LABELS))])
    instructions.append(["A példa sorokat import előtt töröld vagy írd át."])

    style_workbook_headers(workbook)
    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


def style_workbook_headers(workbook):
    from openpyxl.styles import Font, PatternFill

    for sheet in workbook.worksheets:
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="5B3F92")
        sheet.freeze_panes = "A2"
        for column in sheet.columns:
            width = max(len(str(cell.value or "")) for cell in column) + 2
            sheet.column_dimensions[column[0].column_letter].width = min(max(width, 14), 34)


def build_data_export_workbook(export_type, Project, Device, Location):
    workbook = Workbook()
    sheet = workbook.active
    if export_type == "projects":
        sheet.title = "Projects"
        sheet.append(TEMPLATE_PROJECT_HEADERS)
        for project in Project.query.filter(Project.archived_at.is_(None)).order_by(Project.code).all():
            sheet.append([project.code, project.name, project.customer, "", "", project.status, project.notes])
    elif export_type == "locations":
        sheet.title = "Locations"
        sheet.append(TEMPLATE_LOCATION_HEADERS)
        for location in Location.query.filter(Location.archived_at.is_(None)).order_by(Location.name).all():
            sheet.append([location.name, location.location_type, location.address, location.notes])
    else:
        sheet.title = "Devices"
        sheet.append(TEMPLATE_DEVICE_HEADERS)
        for device in Device.query.filter(Device.archived_at.is_(None)).order_by(Device.asset_tag).all():
            sheet.append([
                device.project.code if device.project else "",
                device.device_type,
                device.product_name or "",
                device.manufacturer,
                device.model,
                device.serial_number,
                device.asset_tag,
                device.quantity,
                device.currency,
                device.unit_net_price,
                device.total_net_price,
                device.vat_rate,
                device.unit_gross_price,
                device.total_gross_price,
                device.location.name if device.location else "",
                device.status,
                device.subtype_note or "",
            ])
    style_workbook_headers(workbook)
    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


def parse_template_workbook(path, Project, Device, Location):
    workbook = load_workbook(path, read_only=True, data_only=True)
    summary = {
        "projects": [],
        "devices": [],
        "locations": [],
        "errors": [],
        "new_project_count": 0,
        "existing_project_count": 0,
        "new_device_count": 0,
        "new_location_count": 0,
        "critical_error_count": 0,
    }
    sheets = {sheet.title.lower(): sheet for sheet in workbook.worksheets}
    project_sheet = sheets.get("projects")
    device_sheet = sheets.get("devices")
    location_sheet = sheets.get("locations")
    if project_sheet is None:
        summary["errors"].append({"sheet": "Projects", "row": "-", "message": "Hiányzik a Projects munkalap."})
    if device_sheet is None:
        summary["errors"].append({"sheet": "Devices", "row": "-", "message": "Hiányzik a Devices munkalap."})

    existing_projects = {project.code: project for project in Project.query.all()}
    existing_locations = {location.name.lower(): location for location in Location.query.all()}
    existing_asset_tags = {value for (value,) in db.session.query(Device.asset_tag).all() if value}
    existing_serials = {value for (value,) in db.session.query(Device.serial_number).all() if value}
    seen_project_codes, seen_asset_tags, seen_serials, seen_locations = set(), set(), set(), set()

    if project_sheet:
        rows, errors = template_sheet_rows(project_sheet, TEMPLATE_PROJECT_HEADERS)
        summary["errors"].extend(errors)
        for row_number, row in rows:
            code = clean_string(row.get("project_code"))
            name = clean_string(row.get("project_name"))
            if not code:
                add_template_error(summary, "Projects", row_number, "Hiányzó project_code.")
                continue
            if code in seen_project_codes:
                add_template_error(summary, "Projects", row_number, f"Duplikált project_code a fájlban: {code}.")
                continue
            seen_project_codes.add(code)
            if code not in existing_projects and not name:
                add_template_error(summary, "Projects", row_number, "Hiányzó project_name új projektnél.")
                continue
            status = clean_string(row.get("status")) or "planned"
            if status not in PROJECT_STATUS_LABELS:
                add_template_error(summary, "Projects", row_number, f"Ismeretlen projekt státusz: {status}.")
                continue
            parsed = {key: clean_string(value) for key, value in row.items()}
            parsed.update({"project_code": code, "project_name": name, "status": status})
            summary["projects"].append(parsed)
            if code in existing_projects:
                summary["existing_project_count"] += 1
            else:
                summary["new_project_count"] += 1
            site_name = parsed.get("site_name")
            if site_name and site_name.lower() not in existing_locations and site_name.lower() not in seen_locations:
                seen_locations.add(site_name.lower())
                summary["new_location_count"] += 1

    project_rows_by_code = {row["project_code"]: row for row in summary["projects"]}

    if location_sheet:
        rows, errors = template_sheet_rows(location_sheet, TEMPLATE_LOCATION_HEADERS)
        summary["errors"].extend(errors)
        for row_number, row in rows:
            name = clean_string(row.get("location_name"))
            if not name:
                add_template_error(summary, "Locations", row_number, "Hiányzó location_name.")
                continue
            key = name.lower()
            if key in seen_locations:
                add_template_error(summary, "Locations", row_number, f"Duplikált location_name a fájlban: {name}.")
                continue
            seen_locations.add(key)
            parsed = {field: clean_string(value) for field, value in row.items()}
            parsed["location_name"] = name
            parsed["location_type"] = parsed.get("location_type") or "warehouse"
            summary["locations"].append(parsed)
            if key not in existing_locations:
                summary["new_location_count"] += 1

    if device_sheet:
        rows, errors = template_sheet_rows(device_sheet, TEMPLATE_DEVICE_HEADERS)
        summary["errors"].extend(errors)
        for row_number, row in rows:
            parsed = parse_template_device_row(
                row_number, row, existing_projects, project_rows_by_code,
                existing_asset_tags, existing_serials, seen_asset_tags, seen_serials, summary
            )
            if parsed:
                summary["devices"].append(parsed)
                summary["new_device_count"] += 1
                location_name = parsed.get("location_name")
                if location_name and location_name.lower() not in existing_locations and location_name.lower() not in seen_locations:
                    seen_locations.add(location_name.lower())
                    summary["new_location_count"] += 1

    used_project_codes = {
        row["project_code"] for row in summary["projects"]
    } | {
        row["project_code"] for row in summary["devices"]
    }
    summary["existing_project_count"] = sum(
        1 for code in used_project_codes if code in existing_projects
    )
    summary["new_project_count"] = sum(
        1 for code in used_project_codes if code not in existing_projects
    )
    summary["critical_error_count"] = len(summary["errors"])
    return summary


def template_sheet_rows(sheet, expected_headers):
    values = list(sheet.iter_rows(values_only=True))
    if not values:
        return [], [{"sheet": sheet.title, "row": "-", "message": "Üres munkalap."}]
    headers = [clean_string(value) or "" for value in values[0]]
    missing = [header for header in expected_headers if header not in headers]
    errors = [{"sheet": sheet.title, "row": 1, "message": f"Hiányzó oszlop: {header}."} for header in missing]
    rows = []
    for row_number, values_row in enumerate(values[1:], start=2):
        row = {header: values_row[index] if index < len(values_row) else None for index, header in enumerate(headers) if header}
        if any(meaningful_value(value) for value in row.values()):
            rows.append((row_number, row))
    return rows, errors


def add_template_error(summary, sheet, row, message):
    summary["errors"].append({"sheet": sheet, "row": row, "message": message})


def parse_template_device_row(row_number, row, existing_projects, project_rows_by_code, existing_asset_tags, existing_serials, seen_asset_tags, seen_serials, summary):
    project_code = clean_string(row.get("project_code"))
    product_name = clean_string(row.get("product_name"))
    currency = (clean_string(row.get("currency")) or "").upper()
    quantity = number_value(row.get("quantity"))
    if not project_code:
        add_template_error(summary, "Devices", row_number, "Hiányzó project_code.")
    elif project_code not in existing_projects and project_code not in project_rows_by_code:
        add_template_error(summary, "Devices", row_number, f"A projekt nem létezik és nincs a Projects lapon: {project_code}.")
    if not product_name:
        add_template_error(summary, "Devices", row_number, "Hiányzó product_name.")
    if not meaningful_value(row.get("quantity")):
        add_template_error(summary, "Devices", row_number, "Hiányzó quantity.")
    elif quantity is None or quantity <= 0:
        add_template_error(summary, "Devices", row_number, "Hibás quantity.")
    if not currency:
        add_template_error(summary, "Devices", row_number, "Hiányzó currency.")
    elif currency not in DEVICE_CURRENCIES:
        add_template_error(summary, "Devices", row_number, f"Ismeretlen currency érték: {currency}.")

    numeric_fields = {}
    for field in ["unit_net_price", "total_net_price", "vat_rate", "unit_gross_price", "total_gross_price"]:
        raw = row.get(field)
        value = number_value(raw)
        if meaningful_value(raw) and value is None:
            add_template_error(summary, "Devices", row_number, f"Nem numerikus ár mező: {field}.")
        numeric_fields[field] = value

    asset_tag = clean_string(row.get("asset_tag"))
    serial_number = clean_string(row.get("serial_number"))
    if asset_tag and (asset_tag in existing_asset_tags or asset_tag in seen_asset_tags):
        add_template_error(summary, "Devices", row_number, f"Duplikált asset_tag: {asset_tag}.")
    if serial_number and (serial_number in existing_serials or serial_number in seen_serials):
        add_template_error(summary, "Devices", row_number, f"Duplikált serial_number: {serial_number}.")
    if asset_tag:
        seen_asset_tags.add(asset_tag)
    if serial_number:
        seen_serials.add(serial_number)

    status = clean_string(row.get("status")) or "IN_STOCK"
    if status not in STATUS_LABELS:
        add_template_error(summary, "Devices", row_number, f"Ismeretlen status érték: {status}.")
    category = clean_string(row.get("category")) or "Other"
    if category not in CATEGORY_LABELS:
        add_template_error(summary, "Devices", row_number, f"Ismeretlen category érték: {category}.")

    unit_net = numeric_fields["unit_net_price"]
    total_net = numeric_fields["total_net_price"]
    if quantity and unit_net is not None and total_net is None:
        total_net = quantity * unit_net
    elif quantity and total_net is not None and unit_net is None:
        unit_net = total_net / quantity
    elif quantity and unit_net is not None and total_net is not None and abs(quantity * unit_net - total_net) > 0.01:
        add_template_error(summary, "Devices", row_number, "A quantity × unit_net_price nem egyezik a total_net_price értékkel.")

    vat_rate = numeric_fields["vat_rate"]
    unit_gross = unit_net * (1 + vat_rate / 100) if unit_net is not None and vat_rate is not None else None
    total_gross = total_net * (1 + vat_rate / 100) if total_net is not None and vat_rate is not None else None
    if numeric_fields["unit_gross_price"] is not None and unit_gross is not None and abs(numeric_fields["unit_gross_price"] - unit_gross) > 0.01:
        add_template_error(summary, "Devices", row_number, "A unit_gross_price nem egyezik a nettó érték és ÁFA alapján számolt értékkel.")
    if numeric_fields["total_gross_price"] is not None and total_gross is not None and abs(numeric_fields["total_gross_price"] - total_gross) > 0.01:
        add_template_error(summary, "Devices", row_number, "A total_gross_price nem egyezik a nettó érték és ÁFA alapján számolt értékkel.")

    if any(error["sheet"] == "Devices" and error["row"] == row_number for error in summary["errors"]):
        return None
    return {
        "project_code": project_code,
        "category": category,
        "product_name": product_name,
        "manufacturer": clean_string(row.get("manufacturer")) or "",
        "model": clean_string(row.get("model")) or "",
        "serial_number": serial_number or "",
        "asset_tag": asset_tag,
        "quantity": quantity,
        "currency": currency,
        "unit_net_price": unit_net,
        "total_net_price": total_net,
        "vat_rate": vat_rate,
        "location_name": clean_string(row.get("location_name")),
        "status": status,
        "notes": clean_string(row.get("notes")),
    }


def import_template_workbook(summary, Project, Device, Location, user_id):
    projects = {project.code: project for project in Project.query.all()}
    locations = {location.name.lower(): location for location in Location.query.all()}
    result = {"projects_created": 0, "locations_created": 0, "devices_created": 0}
    for row in summary["projects"]:
        if row["project_code"] in projects:
            continue
        project = Project(
            code=row["project_code"],
            name=row["project_name"],
            customer=row.get("customer_name") or "",
            status=row.get("status") or "planned",
            notes=row.get("notes") or "",
        )
        db.session.add(project)
        db.session.flush()
        projects[project.code] = project
        result["projects_created"] += 1
        site_name = row.get("site_name")
        if site_name and site_name.lower() not in locations:
            location = Location(name=site_name, location_type="project_site", address=row.get("address") or "", notes=f"Projekt: {project.code}")
            db.session.add(location)
            db.session.flush()
            locations[site_name.lower()] = location
            result["locations_created"] += 1
    for row in summary["locations"]:
        key = row["location_name"].lower()
        if key in locations:
            continue
        location = Location(name=row["location_name"], location_type=row.get("location_type") or "warehouse", address=row.get("address") or "", notes=row.get("notes") or "")
        db.session.add(location)
        db.session.flush()
        locations[key] = location
        result["locations_created"] += 1
    for row in summary["devices"]:
        location = None
        if row.get("location_name"):
            key = row["location_name"].lower()
            location = locations.get(key)
            if location is None:
                location = Location(name=row["location_name"], location_type="warehouse")
                db.session.add(location)
                db.session.flush()
                locations[key] = location
                result["locations_created"] += 1
        asset_tag = row.get("asset_tag") or unique_import_asset_tag(Device)
        device = Device(
            asset_tag=asset_tag,
            serial_number=row.get("serial_number") or "",
            device_type=row.get("category") or "Other",
            manufacturer=row.get("manufacturer") or "",
            model=row.get("model") or "",
            product_name=row.get("product_name"),
            subtype_note=row.get("notes"),
            quantity=row.get("quantity"),
            currency=row.get("currency"),
            unit_net_price=row.get("unit_net_price"),
            huf_value=row.get("total_net_price") if row.get("currency") == "HUF" else None,
            vat_rate=row.get("vat_rate"),
            status="IN_STOCK",
            project=projects[row["project_code"]],
            location=location,
        )
        db.session.add(device)
        db.session.flush()
        create_movement(device=device, movement_type="INBOUND", to_location_id=device.location_id, project_id=device.project_id, notes="Sablon alapú import.", user_id=user_id)
        apply_imported_device_status(device, row.get("status") or "IN_STOCK", user_id)
        result["devices_created"] += 1
    return result


def apply_imported_device_status(device, target_status, user_id):
    movement_path = {
        "IN_STOCK": [],
        "RESERVED": ["RESERVE"],
        "ISSUED": ["ISSUE"],
        "INSTALLED": ["ISSUE", "INSTALL"],
        "RETURNED": ["ISSUE", "RETURN"],
        "IN_SERVICE": ["SERVICE"],
        "SCRAPPED": ["SCRAP"],
    }
    for movement_type in movement_path.get(target_status, []):
        create_movement(
            device=device,
            movement_type=movement_type,
            from_location_id=device.location_id,
            to_location_id=device.location_id,
            project_id=device.project_id,
            notes="Sablon alapú import státuszbeállítás.",
            user_id=user_id,
        )
        apply_device_state(device, movement_type, device.location_id, device.project_id)


def unique_import_asset_tag(Device):
    while True:
        asset_tag = f"IMP-{uuid4().hex[:10].upper()}"
        if not Device.query.filter_by(asset_tag=asset_tag).first():
            return asset_tag


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
        "huf_value": calculate_imported_huf_value(
            quantity,
            unit_net_price,
            currency.upper() if currency else None,
            huf_value,
        ),
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
    quantity = number_value(first_value(row, header_map, ["mennyiseg"]))
    unit_price_huf = number_value(first_value(row, header_map, ["egysegar huf"]))
    net_amount_huf = number_value(
        first_value(row, header_map, ["szamla sor netto osszeg huf"])
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
        "quantity": quantity,
        "unit_price_huf": unit_price_huf,
        "net_amount_huf": net_amount_huf
        if net_amount_huf is not None
        else calculate_line_net_amount(quantity, unit_price_huf),
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
    if sheet_key in {"tolto", "toltok", "bmw tolto"}:
        return "EV charger"
    if sheet_key == "matricak":
        return "Sticker"
    if sheet_key == "kamera":
        return "Camera"
    if sheet_key == "kioszk":
        return "Kiosk"
    if sheet_key == "nyito":
        return "Opener"
    if sheet_key == "egyeb":
        return "Other"
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


def validate_movement(device, movement_type, to_location_id=None, project_id=None):
    from models import MOVEMENT_TYPES

    if movement_type not in MOVEMENT_TYPES:
        return "Érvénytelen mozgástípus."

    if device.status == "SCRAPPED":
        return "Selejtezett eszköz nem mozgatható tovább."

    allowed_statuses = {
        "INBOUND": {"RETURNED", "IN_SERVICE"},
        "RESERVE": {"IN_STOCK"},
        "ISSUE": {"IN_STOCK", "RESERVED", "RETURNED"},
        "INSTALL": {"ISSUED", "RETURNED"},
        "RETURN": {"RESERVED", "ISSUED", "INSTALLED", "IN_SERVICE"},
        "SERVICE": {"IN_STOCK", "RETURNED", "ISSUED", "INSTALLED"},
        "SCRAP": None,
        "TRANSFER": {"IN_STOCK", "RETURNED", "ISSUED"},
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
    if movement_type in {"RETURN", "INBOUND", "TRANSFER"} and not to_location_id:
        return f"A(z) {movement_type_label(movement_type)} művelethez cél készlethely megadása kötelező."
    if movement_type == "ISSUE" and not (project_id or device.project_id):
        return "Kiadáshoz projekt megadása kötelező."
    if movement_type == "INSTALL":
        if not (project_id or device.project_id):
            return "Telepítéshez projekt megadása kötelező."
        if not to_location_id:
            return "Telepítéshez cél helyszín / készlethely megadása kötelező."
    return None


def apply_device_state(device, movement_type, to_location_id=None, project_id=None):
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

    if movement_type == "RESERVE":
        if project_id is not None:
            device.project_id = project_id
        return

    if movement_type == "ISSUE":
        if project_id is not None:
            device.project_id = project_id
        if to_location_id is not None:
            device.location_id = to_location_id
        return

    if movement_type == "INSTALL":
        device.project_id = project_id if project_id is not None else device.project_id
        device.location_id = to_location_id
        return

    if movement_type in {"RETURN", "INBOUND"}:
        device.location_id = to_location_id
        device.project_id = None
        return

    if movement_type == "TRANSFER":
        device.location_id = to_location_id
        if project_id is not None:
            device.project_id = project_id
        return

    if movement_type == "SERVICE":
        if to_location_id is not None:
            device.location_id = to_location_id
        return

    if movement_type == "SCRAP":
        return


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
