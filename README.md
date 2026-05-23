# Parkl Infra Manager

First working MVP skeleton for a Parkl-specific internal ERP/inventory web application. It manages parking and EV-charging infrastructure projects, devices, locations, and stock movements.

## Stack

- Python 3
- Flask
- Flask-SQLAlchemy
- Flask-Migrate
- SQLite by default
- PostgreSQL-ready through `DATABASE_URL`
- Bootstrap 5
- Vanilla JavaScript
- Flask sessions
- Werkzeug password hashing

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Initialize the database:

```bash
flask --app app db init
flask --app app db migrate -m "Initial schema"
flask --app app db upgrade
```

Create the default admin user:

```bash
flask --app app seed-admin
```

Start the app:

```bash
flask --app app run --debug
```

Open http://127.0.0.1:5000 and sign in with the credentials from `.env`.

Default local credentials from `.env.example`:

- Username: `admin`
- Password: `admin123`

## Configuration

SQLite is used by default:

```env
DATABASE_URL=sqlite:///instance/parkl.db
```

To use PostgreSQL later, set:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/parkl_infra
```

Also set a real secret key before using the application outside local development:

```env
SECRET_KEY=replace-with-a-long-random-value
```

## Inventory Rule

Persistent inventory storage is database-backed. CSV files are not used.

Every device registration creates a `StockMovement` record, and every manual inventory action on the movements page creates another `StockMovement` record. This keeps a simple audit trail for received, transferred, installed, returned, maintenance, and retired devices.

## MVP Pages

- `/login` - session login
- `/dashboard` - counts and recent stock movements
- `/projects` - list and create projects
- `/devices` - list and create devices
- `/locations` - list and create locations
- `/movements` - list and create stock movements

## Development Notes

The `forms.py` file is intentionally minimal for now. The MVP keeps validation in `app.py` to avoid extra dependencies while preserving a place for future WTForms or validation helpers.
