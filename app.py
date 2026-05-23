from functools import wraps
from datetime import datetime, timezone
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


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)

    from models import Device, Location, Project, StockMovement, User

    @app.context_processor
    def inject_current_user():
        user = None
        if session.get("user_id"):
            user = db.session.get(User, session["user_id"])
        return {"current_user": user}

    def login_required(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if not session.get("user_id"):
                flash("Please sign in to continue.", "warning")
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
            action = "Created"
        else:
            user.password_hash = generate_password_hash(password)
            user.is_admin = True
            action = "Updated"
        db.session.commit()
        print(f"{action} admin user '{username}'.")

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
                flash("Signed in successfully.", "success")
                return redirect(url_for("dashboard"))
            flash("Invalid username or password.", "danger")
        return render_template("login.html")

    @app.route("/logout", methods=["POST"])
    @login_required
    def logout():
        session.clear()
        flash("Signed out.", "info")
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
                flash("Project name and code are required.", "danger")
            elif Project.query.filter_by(code=code).first():
                flash("A project with this code already exists.", "danger")
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
                flash("Project created.", "success")
                return redirect(url_for("projects"))

        project_list = Project.query.order_by(Project.created_at.desc()).all()
        return render_template("projects.html", projects=project_list)

    @app.route("/devices", methods=["GET", "POST"])
    @login_required
    def devices():
        projects = Project.query.order_by(Project.name.asc()).all()
        locations = Location.query.order_by(Location.name.asc()).all()
        if request.method == "POST":
            asset_tag = request.form.get("asset_tag", "").strip()
            serial_number = request.form.get("serial_number", "").strip()
            device_type = request.form.get("device_type", "").strip()
            manufacturer = request.form.get("manufacturer", "").strip()
            model = request.form.get("model", "").strip()
            project_id = optional_int(request.form.get("project_id"))
            location_id = optional_int(request.form.get("location_id"))

            if not asset_tag or not device_type:
                flash("Asset tag and device type are required.", "danger")
            elif Device.query.filter_by(asset_tag=asset_tag).first():
                flash("A device with this asset tag already exists.", "danger")
            else:
                device = Device(
                    asset_tag=asset_tag,
                    serial_number=serial_number,
                    device_type=device_type,
                    manufacturer=manufacturer,
                    model=model,
                    project_id=project_id,
                    location_id=location_id,
                    status="in_stock" if location_id else "unassigned",
                )
                db.session.add(device)
                db.session.flush()
                create_movement(
                    device=device,
                    movement_type="created",
                    to_location_id=location_id,
                    project_id=project_id,
                    notes="Initial device registration.",
                    user_id=session["user_id"],
                )
                db.session.commit()
                flash("Device created and inventory movement recorded.", "success")
                return redirect(url_for("devices"))

        device_list = Device.query.order_by(Device.created_at.desc()).all()
        return render_template(
            "devices.html",
            devices=device_list,
            projects=projects,
            locations=locations,
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
                flash("Location name is required.", "danger")
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
                flash("Location created.", "success")
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
                flash("Device and movement type are required.", "danger")
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
                apply_device_state(device, movement_type, to_location_id, project_id)
                db.session.commit()
                flash("Stock movement recorded.", "success")
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
        )

    return app


def optional_int(value):
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


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


def apply_device_state(device, movement_type, to_location_id=None, project_id=None):
    device.location_id = to_location_id
    device.project_id = project_id
    device.updated_at = datetime.now(timezone.utc)

    if movement_type == "installed":
        device.status = "installed"
    elif movement_type == "retired":
        device.status = "retired"
    elif to_location_id:
        device.status = "in_stock"
    else:
        device.status = "in_transit"


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
