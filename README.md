# Parkl Infra Manager

Parkl-specifikus belső ERP/készletkezelő webalkalmazás első működő MVP váza. Parkolási és EV-töltési infrastruktúra projektek, eszközök, készlethelyek és készletmozgások kezelésére szolgál.

## Technológia

- Python 3
- Flask
- Flask-SQLAlchemy
- Flask-Migrate
- Alapértelmezés szerint SQLite
- PostgreSQL-kompatibilis konfiguráció `DATABASE_URL` alapján
- Bootstrap 5
- Vanilla JavaScript
- Flask session alapú hitelesítés
- Werkzeug jelszó-hash-elés

## Telepítés

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Adatbázis inicializálása:

```bash
flask --app app db init
flask --app app db migrate -m "Initial schema"
flask --app app db upgrade
```

Alapértelmezett admin felhasználó létrehozása:

```bash
flask --app app seed-admin
```

Alkalmazás indítása:

```bash
flask --app app run --debug
```

Nyisd meg: http://127.0.0.1:5000, majd jelentkezz be a `.env` fájlban megadott adatokkal.

Alapértelmezett helyi belépési adatok a `.env.example` alapján:

- Felhasználónév: `admin`
- Jelszó: `admin123`

## Konfiguráció

Alapértelmezés szerint SQLite fut:

```env
DATABASE_URL=sqlite:///instance/parkl.db
```

Későbbi PostgreSQL használathoz ezt állítsd be:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/parkl_infra
```

Helyi fejlesztésen kívül állíts be valódi titkos kulcsot is:

```env
SECRET_KEY=replace-with-a-long-random-value
```

## Magyar használat

Az alkalmazás böngészőben látható felülete magyar nyelvű. A fő menüpontok:

- `Áttekintés` - összesített darabszámok és legutóbbi készletmozgások
- `Projektek` - projektek listázása és létrehozása
- `Eszközök` - eszközök listázása, szűrése és létrehozása
- `Készlethelyek` - raktárak, helyszínek és egyéb készlethelyek kezelése
- `Mozgások` - készletmozgások rögzítése és megtekintése
- `Gazdátlan számlasorok` - projekthez vagy eszközhöz még nem rendelt számlasorok nyilvántartása

## Excel megfeleltetés

A jelenlegi Parkl készletkezelő Excel nem csak készletet tartalmaz, hanem beszerzést, projekt-hozzárendelést, érkezési állapotot és pénzügyi számlainformációkat is. Az MVP ezt az adatmodellt készíti elő, de Excel import még nincs implementálva.

A termék/készlet munkalapok nagy része az `Eszközök` oldalra és a `Device` modellre képezhető le:

- `Töltő`, `BMW töltő`, `Kioszk`, `Kamera`, `Egyéb`, `Nyitó`, `Matricák` - többnyire eszköz- vagy terméksorok
- `Termék`, `Töltő típusa`, `Kamera típusa`, `Típus` - kategória és terméknév
- `Altípus`, `Altípus/Megjegyzés`, `Megjegyzés` - altípus és megjegyzés mezők
- `Beszállító`, `Gyártásért felelős` - beszállító / gyártó
- `ID`, `PO szám`, sorozatszám jellegű mezők - eszközazonosító vagy sorozatszám
- `Mennyiség`, `Nettó egységár`, `Deviza`, `Érték (HUF)` - mennyiség és érték mezők
- `Projekt - Kód` - meglévő `Project.code` szerinti projekt-hozzárendelés
- `Rendelés napja`, `Megrendelve?`, `Tervezett érkezés napja`, `Érkezés napja`, `Megérkezett?`, `Szállítási ktg.`, `Elszállítás napja` - rendelés és érkezés követése
- `Kapcsolódó számla sorszáma`, `... fizetve?`, `Számla értéke` - pénzügyi adatok az eszköz/terméksoron

A `Gazdátlanul` munkalap az új `Gazdátlan számlasorok` oldalra és az `UnassignedInvoiceItem` modellre képezhető le:

- `Számlaszám`, `Partner`, `Számla kelte`, `Számviteli teljesítés dátuma`, `Fizetési határidő`
- `Bruttó összeg (HUF)`, `Pénznem`, `Megnevezés`, `Mennyiség`
- `Egységár HUF`, `Számla sor nettó összeg HUF`, `Számla sor ÁFA összeg HUF`, `Számla sor bruttó összeg HUF`
- hozzárendelési státusz, opcionális projekt- és eszközkapcsolat

Az Excel import későbbi lépés. A mostani cél az, hogy az alkalmazás adatmodellje és kézi felülete már képes legyen fogadni az Excelben szereplő fő üzleti fogalmakat.

## Készletszabályok

A tartós készletadatok adatbázisban tárolódnak. CSV fájlokat az alkalmazás nem használ.

Minden eszközrögzítés létrehoz egy `INBOUND` típusú `StockMovement` rekordot, és minden kézi készletművelet a Mozgások oldalon újabb `StockMovement` rekordot hoz létre. Az eszköz státusza csak készletmozgás létrehozásával változhat. A `StockMovement` rekordok nem módosíthatók, auditnaplóként kezelendők.

Eszközstátuszok:

- `IN_STOCK` - Raktáron
- `RESERVED` - Előjegyezve
- `ISSUED` - Kiadva
- `INSTALLED` - Telepítve
- `RETURNED` - Visszavéve
- `IN_SERVICE` - Szervizben
- `SCRAPPED` - Selejtezve

Mozgástípusok:

- `INBOUND` - Bevételezés
- `RESERVE` - Előjegyzés
- `ISSUE` - Kiadás
- `INSTALL` - Telepítés
- `RETURN` - Visszavétel
- `SERVICE` - Szervizbe küldés
- `SCRAP` - Selejtezés
- `TRANSFER` - Áthelyezés

Státuszváltási szabályok:

- Eszköz csak `IN_STOCK` státuszból jegyezhető elő.
- Eszköz csak `IN_STOCK` vagy `RESERVED` státuszból adható ki.
- Eszköz csak `ISSUED` státuszból telepíthető.
- Eszköz csak `ISSUED` vagy `INSTALLED` státuszból vehető vissza.
- Eszköz csak `IN_STOCK`, `RETURNED`, `ISSUED` vagy `INSTALLED` státuszból küldhető szervizbe.
- Eszköz csak akkor selejtezhető, ha még nem `SCRAPPED`.
- Selejtezett eszköz nem mozgatható tovább.
- A `TRANSFER` megtartja az aktuális státuszt, és a lokáció/projekt hozzárendelést frissíti.
- Az `INBOUND` visszaállítja az eszközt `IN_STOCK` státuszra, kivéve ha már `SCRAPPED`.

## MVP oldalak

- `/login` - bejelentkezés
- `/dashboard` - darabszámok és legutóbbi készletmozgások
- `/projects` - projektek listázása és létrehozása
- `/devices` - eszközök listázása, szűrése és létrehozása
- `/locations` - készlethelyek listázása és létrehozása
- `/movements` - készletmozgások listázása és létrehozása
- `/unassigned-invoices` - gazdátlan számlasorok listázása és létrehozása

## Fejlesztési megjegyzés

A `forms.py` fájl egyelőre szándékosan minimális. Az MVP a validációt az `app.py` fájlban tartja, így nincs extra függőség, de később van hely WTForms vagy más validációs segédek számára.
