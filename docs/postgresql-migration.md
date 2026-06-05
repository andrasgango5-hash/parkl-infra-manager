# PostgreSQL migráció

Ez az alkalmazás SQLAlchemy és Flask-Migrate/Alembic alapján működik, ezért SQLite és PostgreSQL alatt ugyanazokat a modelleket és migrációkat használja.

## Helyi PostgreSQL indítása Dockerrel

```bash
docker compose up -d postgres
```

`.env` példa:

```env
DATABASE_URL=postgresql://parkl:parkl_dev_password@localhost:5432/parkl_infra
SECRET_KEY=replace-with-a-long-random-secret
ADMIN_USERNAME=admin
ADMIN_PASSWORD=temporary-initial-admin-password
SESSION_COOKIE_SECURE=false
```

Production környezetben:

```env
SESSION_COOKIE_SECURE=true
```

## Séma létrehozása PostgreSQL-ben

```bash
source .venv/bin/activate
flask --app app db upgrade
flask --app app seed-admin
```

A `seed-admin` nem tartalmaz hardcoded jelszót. Az admin jelszót add meg `ADMIN_PASSWORD` környezeti változóval vagy interaktívan a parancs futtatásakor. Az első belépéskor kötelező jelszócsere történik.

## SQLite adatok átvitele

Az automatikus SQLite -> PostgreSQL adatdump nincs beépítve, mert a feltöltött fájlok, munkalap fotók, QR/PDF mellékletek és import batch-ek miatt érdemes kontrollált migrációt futtatni.

Ajánlott biztonságos folyamat:

1. Állítsd le az alkalmazást.
2. Készíts mentést az SQLite fájlról és az `instance/` könyvtárról.
3. Indítsd el a PostgreSQL-t.
4. Futtasd a migrációkat PostgreSQL-re: `flask --app app db upgrade`.
5. Hozd létre az admint: `flask --app app seed-admin`.
6. Az üzleti adatokat export/import folyamaton vagy dedikált migrációs script alapján töltsd át.

## Alembic kompatibilitás

- A migrációk `DATABASE_URL` alapján arra az adatbázisra futnak, amelyet a környezet megad.
- A `postgres://` URL automatikusan `postgresql://` formára normalizálódik.
- SQLite fejlesztői fallback továbbra is használható, ha nincs `DATABASE_URL`.
