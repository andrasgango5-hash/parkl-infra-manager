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
- ReportLab alapú PDF export
- Fabric.js alapú projekt rajzszerkesztő

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

Tiszta helyi demóadatok létrehozása:

```bash
flask --app app reset-demo-data --yes
```

Ez a parancs csak akkor fut, ha `FLASK_ENV` nem `production`. A meglévő projekt-, eszköz-, készlethely-, készletmozgás-, import-, munkalap- és gazdátlan számlasor adatokat törli, az admin felhasználót viszont megtartja vagy létrehozza. `--yes` nélkül megerősítést kér.

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

- `Áttekintés` - workflow indítópontok, figyelmet igénylő tételek és legutóbbi mozgások
- `Projektek` - projektek listázása és létrehozása
- `Eszközök` - eszközök, bulk anyagok és importált készletsorok keresése, workflow nézetekkel
- `Készlethelyek` - raktárak, helyszínek és egyéb készlethelyek kezelése
- `Mozgások` - készletmozgások rögzítése és megtekintése
- `Munkalapok` - önálló karbantartási, hibaelhárítási, kábelcsere- és helyszíni jegyzőkönyvek
- `Gazdátlan számlasorok` - projekthez vagy eszközhöz még nem rendelt számlasorok nyilvántartása
- `Excel import` - Parkl készletkezelő `.xlsx` feltöltése, dry-run előnézet és megerősített import

## Hogyan használd az appot

Az app célja, hogy az Excelből átvett készlet-, beszerzési, projekt- és számlainformációk ne nyers táblázatként, hanem napi Parkl operációs folyamatként legyenek kezelhetők.

Javasolt Parkl munkafolyamat:

1. Hozd létre a projektet a `Projektek` oldalon.
2. Rögzíts kézzel eszközt, vagy töltsd be a Parkl Excel fájlt az `Excel import` oldalon.
3. Az `Eszközök` oldalon használd a workflow nézeteket: `Raktáron`, `Projekthez rendelve`, `Kiadva`, `Telepítve`, `Beérkezésre vár`, `Pénzügyileg nyitott`, `Figyelmet igényel`.
4. Az eszköz részletein foglald, add ki, telepítsd, vedd vissza, küldd szervizbe, helyezd át vagy selejtezd.
5. A projekt részletező oldalon ellenőrizd a hozzárendelt tételeket, az összértéket, a nyitott számlákat és a mozgástörténetet.
6. Generálj PDF projektlistát, kiadási listát, telepítési listát vagy pénzügyi összesítőt.
7. A `Gazdátlan számlasorok` és `Figyelmet igényel` oldalakkal zárd le a tisztázatlan pénzügyi és beszerzési tételeket.
8. Téves vagy tesztimport esetén az importcsomag részletein használd az `Import visszavonása` gombot.

## Munkalapok és jegyzőkönyvek

A `Munkalapok` modul a korábbi Excel alapú szerviz megrendelő / munkalap / jegyzőkönyv fájlokat váltja ki. A munkalap önálló entitás, nem szükséges projekthez kapcsolni, ezért régi munkák, karbantartások, kiszállások, kábelcserék és hibajavítások dokumentálására is használható.

A munkalapon rögzíthető:

- munkalapszám, típus, dátum és státusz
- ügyfél, kapcsolattartó és helyszín
- opcionális készülékadatok: gyártó, típus, gyári szám, vásárlás dátuma
- érkezés, távozás és automatikusan számított helyszíni idő
- hiba leírása, elvégzett munka, elszámolási mód és megjegyzés
- szabad szöveges anyaglista és dinamikus mérési sorok
- technikusok, alvállalkozó, fotódokumentáció és digitális aláírások

Használat:

1. Nyisd meg a `Munkalapok` menüpontot.
2. Hozz létre új munkalapot, vagy indulj a `Munkalap sablonok` egyikéből.
3. Töltsd ki a helyszíni adatokat, anyagokat, méréseket, fotókat és aláírásokat.
4. A munkalap részletein generáld a `MUNKALAP_<azonosító>.pdf` hivatalos jegyzőkönyvet.
5. A lezárt vagy régi munkalapokat archiváld; ezek nem törlődnek fizikailag.

Helyi kipróbáláshoz érdemes a `reset-demo-data` paranccsal indulni. A demo két projektet hoz létre (`PRK-001 - Arena EV Upgrade`, `PRK-002 - Office Park Sorompó projekt`), öt hasznos készlethelyet, hat érthető eszközt, hozzájuk tartozó bevételezési/készletmozgási naplót és két gazdátlan számlasort.

A törlés jellegű műveletek alapértelmezés szerint archiválnak. Készletmozgással rendelkező eszközök és importált adatok így nem vesznek el, de eltűnnek az aktív listákból.

Workflow fókuszú nézetek:

- Az `Áttekintés` oldalon a fő műveletek indulnak: új projekt, Excel import, eszközkeresés, projektlista, figyelmet igénylő tételek és gazdátlan számlasorok.
- Az `Eszközök` oldalon nézetgombok segítenek: `Összes`, `Raktáron`, `Projekthez rendelve`, `Kiadva`, `Telepítve`, `Beérkezésre vár`, `Pénzügyileg nyitott`, `Figyelmet igényel`.
- A `Figyelmet igényel` oldal összegyűjti a problémás eszközöket és gazdátlan számlasorokat, például lejárt tervezett érkezést, nyitott számlát, hiányos projektadatot vagy hiányzó importált mezőt.
- A projekt részletező oldal a fő munkalap: megmutatja a projekthez tartozó eszközöket, HUF értéket, kiadott/telepített/visszavett darabszámokat, nyitott beszállítói számlákat, beérkezésre váró tételeket, mozgástörténetet és PDF dokumentumokat generál.
- A projekt részletező oldalon a `Rajzok` tabon parkoló- vagy alaprajz képre készíthető egyszerű megvalósítási vázlat. A szerkesztő Fabric.js-t használ, támogatja a zoomot, pan módot, infrastruktúra ikonokat, kábelvonalakat, címkéket, JSON mentést és PNG/PDF exportot.

PDF dokumentumok projekt oldalról:

- `PDF projektlista generálása` - teljes hozzárendelt eszköz- és anyaglista mennyiséggel, státusszal, lokációval, HUF értékkel és megjegyzéssel.
- `Kiadási lista PDF` - kiadott tételek aláírási résszel.
- `Telepítési lista PDF` - telepített tételek aláírási résszel.
- `Pénzügyi összesítő PDF` - projektérték, számlaszámok, fizetettség, beszállító és HUF értékek.

## Excel megfeleltetés

A jelenlegi Parkl készletkezelő Excel nem csak készletet tartalmaz, hanem beszerzést, projekt-hozzárendelést, érkezési állapotot és pénzügyi számlainformációkat is. Az MVP az `Excel import` oldalon `.xlsx` fájlból tud dry-run előnézetet készíteni, majd külön megerősítés után adatbázisba importálni.

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

Az import jelenleg ezeket a normál készlet/termék munkalapokat kezeli: `Töltő`, `Töltők`, `BMW töltő`, `Kioszk`, `Kamera`, `Egyéb`, `Nyitó`, `Matricák`. A lapnév alapján az importált kategóriák érthetőbb címkéket kapnak: `Matricák` → `Matrica`, `Kamera` → `Kamera`, `Kioszk` → `Kioszk`, `Nyitó` → `Nyitó eszköz`, `Egyéb` → `Egyéb`. A `Gazdátlanul` munkalap külön `UnassignedInvoiceItem` rekordokként kerül be. A `Segéd`, `Önköltség`, `Dashboard`, `WORKFLOW` és hasonló segédlapok nem kerülnek normál készletsorként importálásra.

Import használata:

1. Lépj az `Excel import` oldalra.
2. Tölts fel egy `.xlsx` fájlt.
3. Ellenőrizd a dry-run előnézetet: munkalaponkénti sorok, kihagyások, figyelmeztetések és az első 10 feldolgozott sor.
4. Jelöld be az `Importálás végrehajtása` mezőt.
5. Kattints az `Adatbázisba importálás` gombra.

Az import nem használ CSV-t és nem használ pandast. A `.xlsx` fájlt `openpyxl` olvassa. Duplikált eszközsor esetén az import kihagyja a sort, ha már létezik azonos importkulcs vagy ütköző eszközazonosító. Importált eszköz létrehozásakor automatikus `INBOUND` készletmozgás is létrejön.

## Készletszabályok

A tartós készletadatok adatbázisban tárolódnak. CSV fájlokat az alkalmazás nem használ.

Minden eszközrögzítés létrehoz egy `INBOUND` típusú `StockMovement` rekordot, és minden kézi készletművelet a Mozgások oldalon újabb `StockMovement` rekordot hoz létre. Az eszköz státusza csak készletmozgás létrehozásával változhat. A `StockMovement` rekordok nem módosíthatók, auditnaplóként kezelendők.

### Csoportos eszköztételek és egyedi példányok

A `Device` a beszerzési és készletnyilvántartási csoportos tétel. Több darabos fizikai eszköznél az eszköz adatlapján a **Példányok létrehozása** művelettel külön `DeviceUnit` példányok hozhatók létre.

- A csoportos tétel mennyisége nem változik a példányok létrehozásakor.
- Minden példány saját példányazonosítót, sorozatszámot, eszközazonosítót, QR-kódot és címkét kaphat.
- A példányok státusza, projektje és készlethelye jelenleg a szülő eszköztételből származik.
- A csoportos QR-kódok és a korábbi `/devices/<id>/qr` linkek továbbra is működnek.
- A QR mód lehet: nincs QR, csoport QR vagy egyedi QR példányonként.
- A példánylistából az összes egyedi QR-címke egy PDF-ben nyomtatható.

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
- `/dashboard` - workflow indítópult, gyors műveletek, figyelmet igénylő tételek és legutóbbi készletmozgások
- `/projects` - projektek listázása és létrehozása
- `/devices` - eszközök listázása, szűrése és létrehozása
- `/devices/<id>/units` - egy csoportos eszköztétel egyedi fizikai példányai
- `/devices/<id>/units/create` - példányok előnézete és megerősített létrehozása
- `/devices/<id>/unit-labels.pdf` - az összes aktív példány QR-címkéje PDF-ben
- `/device-units/<id>` - egyedi eszközpéldány adatlapja
- `/device-units/<id>/qr` - egyedi eszközpéldány QR-kódja
- `/device-units/<id>/label` - egyedi eszközpéldány nyomtatható címkéje
- `/locations` - készlethelyek listázása és létrehozása
- `/movements` - készletmozgások listázása és létrehozása
- `/unassigned-invoices` - gazdátlan számlasorok listázása és létrehozása
- `/import` - Excel import előnézet és végrehajtás
- `/attention` - figyelmet igénylő készlet-, projekt-, beszerzési és pénzügyi tételek
- `/projects/<id>/pdf/equipment` - projekt eszközlista PDF
- `/projects/<id>/pdf/issue` - kiadási lista PDF
- `/projects/<id>/pdf/installation` - telepítési lista PDF
- `/projects/<id>/pdf/finance` - pénzügyi összesítő PDF

## Fejlesztési megjegyzés

A `forms.py` fájl egyelőre szándékosan minimális. Az MVP a validációt az `app.py` fájlban tartja, így nincs extra függőség, de később van hely WTForms vagy más validációs segédek számára.
