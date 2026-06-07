# Parkl Infra Manager

Parkl-specifikus belső ERP/készletkezelő webalkalmazás első működő MVP váza. Parkolási és EV-töltési infrastruktúra projektek, eszközök, készlethelyek és készletmozgások kezelésére szolgál.

## Technológia

- Python 3
- Flask
- Flask-SQLAlchemy
- Flask-Migrate
- Helyi fejlesztésben SQLite fallback
- PostgreSQL production konfiguráció `DATABASE_URL` alapján
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

PostgreSQL indítása helyi Dockerrel:

```bash
docker compose up -d postgres
```

Adatbázis inicializálása / migrálása:

```bash
flask --app app db upgrade
```

Alapértelmezett admin felhasználó létrehozása:

```bash
flask --app app seed-admin --password
```

Production környezetben inkább `ADMIN_PASSWORD` környezeti változóval futtasd a seedet, majd töröld/forgasd az értéket. Az admin első belépéskor kötelező jelszócserét kap.

Tiszta helyi demóadatok létrehozása:

```bash
flask --app app reset-demo-data --yes
```

Ez a parancs csak akkor fut, ha `FLASK_ENV` nem `production`. A meglévő projekt-, eszköz-, készlethely-, készletmozgás-, import-, munkalap- és gazdátlan számlasor adatokat törli, az admin felhasználót viszont megtartja vagy létrehozza. `--yes` nélkül megerősítést kér.

Alkalmazás indítása:

```bash
flask --app app run --debug
```

Nyisd meg: http://127.0.0.1:5000, majd jelentkezz be az általad seedelt admin adatokkal.

## Konfiguráció

Helyi fejlesztéshez használható SQLite fallback, ha nincs `DATABASE_URL`:

```env
DATABASE_URL=sqlite:///instance/parkl.db
```

Production / Docker PostgreSQL használathoz:

```env
DATABASE_URL=postgresql://parkl:parkl_dev_password@localhost:5432/parkl_infra
```

Helyi fejlesztésen kívül állíts be valódi titkos kulcsot is:

```env
SECRET_KEY=replace-with-a-long-random-value
```

Biztonsági beállítások:

```env
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=Lax
LOGIN_MAX_FAILED_ATTEMPTS=5
LOGIN_LOCKOUT_MINUTES=15
```

## Production authentikáció

- A jelszavak Werkzeug hash formában tárolódnak.
- 5 hibás login próbálkozás után 15 perces tiltás lép életbe.
- A session 8 óra inaktivitás után lejár.
- Az admin jelszó nincs hardcode-olva; `seed-admin` jelszót kér vagy `ADMIN_PASSWORD`-t használ.
- Új/admin seedelt felhasználónál első belépéskor kötelező jelszócsere van.
- A Felhasználók admin oldalon új felhasználó hozható létre ideiglenes jelszóval.
- A login, logout, lockout és jelszócsere események audit logba kerülnek.

PostgreSQL migrációs részletek: [docs/postgresql-migration.md](docs/postgresql-migration.md)

## Magyar használat

Az alkalmazás böngészőben látható felülete magyar nyelvű. A fő menüpontok:

- `Áttekintés` - workflow indítópontok, figyelmet igénylő tételek és legutóbbi mozgások
- `Projektek` - projektek listázása, új projekt külön `/projects/new` oldalon
- `Eszközök` - eszközök, bulk anyagok és importált készletsorok keresése, új eszköz külön `/devices/new` oldalon
- `Készlethelyek` - raktárak, helyszínek és egyéb készlethelyek kezelése
- `Mozgások` - készletmozgások rögzítése és megtekintése
- `Munkalapok` - önálló karbantartási, hibaelhárítási, kábelcsere- és helyszíni jegyzőkönyvek
- `Gazdátlan számlasorok` - projekthez vagy eszközhöz még nem rendelt számlasorok nyilvántartása
- `Import / Export` - sablon alapú napi import/export; a régi Parkl Excel import admin Legacy funkció

## Hogyan használd az appot

Az app célja, hogy az Excelből átvett készlet-, beszerzési, projekt- és számlainformációk ne nyers táblázatként, hanem napi Parkl operációs folyamatként legyenek kezelhetők.

Javasolt Parkl munkafolyamat:

1. Hozd létre a projektet a `Projektek` oldalon.
2. Rögzíts kézzel eszközt a `/devices/new` oldalon, vagy töltsd be a normál import sablont az `Import / Export` oldalon.
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

Helyi kipróbáláshoz érdemes a `reset-demo-data` paranccsal indulni. A demo két, saját telepítési helyszínadatokkal rendelkező projektet, három logisztikai készlethelyet, egy három példányos EV-töltő tételt és egy 50 darabos bulk matrica tételt hoz létre. Egy töltőpéldány és 20 matrica a `PRK-001` projektre van előfoglalva, így a projekt- és raktárnézetek azonnal ellenőrizhetők. A parancs két gazdátlan számlasort is létrehoz.

A törlés jellegű műveletek alapértelmezés szerint archiválnak. Aktív készlettel, projekthez rendelt példánnyal vagy nem selejtezett állománnyal rendelkező rekord nem archiválható; a felület felsorolja a rendezendő blokkoló tételeket.

Workflow fókuszú nézetek:

- Az `Áttekintés` oldalon a fő műveletek indulnak: új projekt, Excel import, eszközkeresés, projektlista, figyelmet igénylő tételek és gazdátlan számlasorok.
- Az `Eszközök` oldalon nézetgombok segítenek: `Összes`, `Raktáron`, `Projekthez rendelve`, `Kiadva`, `Telepítve`, `Beérkezésre vár`, `Pénzügyileg nyitott`, `Figyelmet igényel`.
- A `Figyelmet igényel` oldal összegyűjti a problémás eszközöket és gazdátlan számlasorokat, például lejárt tervezett érkezést, nyitott számlát, hiányos projektadatot vagy hiányzó importált mezőt.
- A projekt részletező oldal a fő munkalap: megmutatja a projekthez tartozó eszközöket, HUF értéket, kiadott/telepített/visszavett darabszámokat, nyitott beszállítói számlákat, beérkezésre váró tételeket, mozgástörténetet és PDF dokumentumokat generál.
- A projekt részletező oldalon a `Rajzok` tabon parkoló- vagy alaprajz képre készíthető egyszerű megvalósítási vázlat. A szerkesztő Fabric.js-t használ, támogatja a zoomot, pan módot, infrastruktúra ikonokat, kábelvonalakat, címkéket, JSON mentést és PNG/PDF exportot.

## Készletállapot és foglalás

A `Device` a termék- vagy beszerzési tétel. Egyedi követésnél a fizikai állapotot a `DeviceUnit`, mennyiségi követésnél a `BulkStockBalance` tartalmazza. Projekt- és készlethely-összesítés nem a legacy `Device.project_id` vagy `Device.location_id` mezőkből készül.

- `Raktáron`: készlethely kötelező, aktív projekt nincs.
- `Előjegyezve`: fizikailag készlethelyen marad, de projekthez foglalt és nem számít szabad készletnek.
- `Kiadva` és `Telepítve`: projekt kötelező, aktív készlethely nincs.
- `Visszavéve`: újra készlethelyen van, aktív projekt nincs; raktárra vétellel `Raktáron` állapotba tehető.
- `Szervizben`: szerviz vagy raktár típusú helyen fizikailag megtalálható, de nem számít szabad készletnek.
- `Selejtezve`: sem aktív projektje, sem aktív készlethelye nincs, és tovább nem mozgatható.

Előfoglalásból csak ugyanarra a projektre indítható kiadás. Másik projekthez történő kiadás előtt a `Foglalás feloldása` auditált készletmozgást kell használni. A mozgások nem módosíthatók és nem törölhetők; hibás mozgás csak külön ellenmozgással vonható vissza. Az állapot pontos visszaállítása érdekében csak az adott példány vagy bulk tétel legutolsó mozgása vonható vissza.

## Projekt és készlethely

A `Project` az ügyfél és a telepítési hely gazdája. A projektben tárolható a helyszín neve, címe, városa, országa, GPS-koordinátája, Google Maps linkje és helyszíni megjegyzése. A kiadott vagy telepített készlet a projekthez tartozik, aktív készlethelye nincs.

A `Location` kizárólag logisztikai készlethely: raktár, szervizautó, szerviz/javítás, beszállító vagy alvállalkozói raktár. Az új sablon alapú import `Projects` lapjának `site_name` és `address` mezői közvetlenül a projektre kerülnek, és nem hoznak létre projekt-helyszín típusú készlethelyet.

Az egyszerű Device export egy sorban tartja a terméktörzset. Ha a tétel példányai vagy bulk egyenlegei több projekt, lokáció vagy státusz között oszlanak meg, az export `MIXED` jelzést ír az érintett mezőbe. Ez szándékosan nem importálható vissza automatikusan: előbb egyértelmű allokációra vagy későbbi, példány-/egyenlegsoros exportformátumra van szükség.

Az új sablonimport készletkövetési mezői:

- `tracking_mode`: `bulk` vagy `unit`; üresen hagyva `bulk`.
- `unit_generation`: unit követésnél `yes`, bulk követésnél `no`.
- `unit_code_prefix`: opcionális prefix a generált példányazonosítókhoz.

Bulk importnál egyetlen `INBOUND` mozgás és pontosan a megadott mennyiségű `BulkStockBalance` jön létre. Unit importnál a Device terméktörzs mellé `quantity` darab `DeviceUnit` és példányonként egy bevételezési mozgás készül. A terméktörzs-szintű export nem őrzi meg a már létező példányok egyedi sorozatszámát vagy asset tagjét; ehhez később külön DeviceUnit export/import munkalap szükséges.

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

### Normál sablon alapú import és export

A napi használatú adatkezelés az `/import-export` oldalon érhető el. Innen letölthető egy egyszerű Excel sablon `Projects`, `Devices`, opcionális `Locations` és `Instructions` munkalappal.

1. Töltsd le az import sablont.
2. Töltsd ki a projekt-, eszköz- és opcionális készlethelyadatokat.
3. Töltsd fel a kitöltött `.xlsx` fájlt.
4. Ellenőrizd a dry-run eredményt és a soronkénti hibalistát.
5. Kritikus hiba nélkül erősítsd meg az importot.

Az oldalról a projektek, eszközök és készlethelyek Excel exportja is letölthető. A régi, több munkalapos Parkl Excel import nem része a normál folyamatnak: admin felhasználóknak a `/legacy/parkl-excel-import` oldalon marad elérhető.

## Készletszabályok

A tartós készletadatok adatbázisban tárolódnak. CSV fájlokat az alkalmazás nem használ.

A mennyiségi eszközrögzítés `INBOUND` típusú `StockMovement` rekordot hoz létre. Egyedi követésnél a terméktörzs létrehozása még nem fizikai készletmozgás; a létrehozott `DeviceUnit` példányok kapják a saját mozgásaikat. Minden kézi készletművelet új `StockMovement` rekordot hoz létre. A státusz csak készletmozgással változhat, a `StockMovement` rekordok pedig nem módosíthatók.

### Csoportos eszköztételek és egyedi példányok

A `Device` a termék-, beszerzési és készlettétel törzs. A `tracking_mode` határozza meg a követést:

- `bulk`: a mozgás egy kiválasztott készletegyenlegből von le pozitív mennyiséget, és a célállapothoz/helyhez/projekthez tartozó egyenleghez adja;
- `unit`: minden mozgáshoz konkrét `DeviceUnit` szükséges, a mozgási mennyiség mindig 1.

A bulk készlet aktuális állapotát a `BulkStockBalance` sorok adják meg. Egy Device ezért egyszerre több státuszban, projekten vagy készlethelyen is rendelkezhet mennyiséggel. Például 60 darabból 10 kiadható úgy, hogy 50 továbbra is raktáron marad. A rendszer nem enged a kiválasztott egyenlegnél nagyobb mennyiséget mozgatni.

A projekt adatlap külön mutatja az egyedi `DeviceUnit` példányokat és a bulk készletegyenlegeket. Innen konkrét példány vagy részleges bulk mennyiség vehető vissza egy kiválasztott raktárba.

Hibás készletmozgás nem módosítható és nem törölhető. A **Mozgás visszavonása** művelet új `REVERSAL` ellenmozgást hoz létre, amely a `reversal_of_movement_id` mezővel hivatkozik az eredeti rekordra. A visszavonás csak akkor engedélyezett, ha az érintett példány vagy mennyiség még az eredeti mozgás célállapotában található.

Az archiválás, selejtezés és visszavonás külön művelet:

- archiválás: készlet nélküli, már nem aktív törzsadat elrejtése;
- selejtezés: `SCRAP` készletmozgás, amely lezárja az érintett készlet életciklusát;
- visszavonás: hibás naplóbejegyzés korrekciója ellenmozgással, az eredeti rekord megtartásával.

Több darabos fizikai eszköznél az eszköz adatlapján a **Példányok létrehozása** művelettel külön `DeviceUnit` példányok hozhatók létre.

- A csoportos tétel mennyisége nem változik a példányok létrehozásakor.
- Minden példány saját példányazonosítót, sorozatszámot, eszközazonosítót, QR-kódot és címkét kaphat.
- Minden példánynak saját státusza, projektje és készlethelye van.
- A példányosításkor ezek az értékek a szülő tétel aktuális állapotából indulnak, később csak példányszintű készletmozgással változnak.
- A mozgásnapló a forrás- és célprojektet is megőrzi; a régi rekordok hiányzó mennyisége történeti okból üres marad.
- A Device és DeviceUnit QR-kódja a megfelelő adatlapra vezet, ahonnan jogosultság esetén közvetlenül indítható készletművelet.
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

## Felhasználói szerepkörök

Az alkalmazás egyszerű, központi szerepkör alapú jogosultságkezelést használ:

- Alap biztonsági szint: `Admin` vagy `User`
- `admin` - teljes hozzáférés, felhasználókezelés, Legacy funkciók, import/export és pénzügyi adatok
- `manager` - projektek, eszközök, készlethelyek, mozgások, munkalapok, PDF-ek és import/export kezelése
- `technician` - eszközök, QR-kódok és munkalapok megtekintése; munkalap létrehozása és szerkesztése; pénzügyi adatok és import/export nélkül
- `viewer` - csak olvasási hozzáférés, írási műveletek, import/export és pénzügyi oldalak nélkül

A route-védelem az elsődleges: a tiltott műveletek akkor sem hajthatók végre, ha valaki közvetlenül próbálja megnyitni az URL-t. A sidebar és a műveleti gombok ugyanezekhez a jogokhoz igazodnak.

Helyi tesztfelhasználók létrehozása:

```bash
flask --app app seed-role-users
```

Ez a fejlesztési parancs létrehozza vagy frissíti az `admin`, `manager`, `technician` és `viewer` tesztfelhasználókat, és kiírja a hozzájuk tartozó helyi jelszavakat. Production környezetben ne használd.

## MVP oldalak

- `/login` - bejelentkezés
- `/dashboard` - workflow indítópult, gyors műveletek, figyelmet igénylő tételek és legutóbbi készletmozgások
- `/projects` - projektek listázása és szűrése
- `/projects/new` - új projekt létrehozása
- `/devices` - eszközök listázása és szűrése
- `/devices/new` - új eszköz létrehozása
- `/devices/<id>/units` - egy csoportos eszköztétel egyedi fizikai példányai
- `/devices/<id>/units/create` - példányok előnézete és megerősített létrehozása
- `/devices/<id>/unit-labels.pdf` - az összes aktív példány QR-címkéje PDF-ben
- `/device-units/<id>` - egyedi eszközpéldány adatlapja
- `/device-units/<id>/qr` - egyedi eszközpéldány QR-kódja
- `/device-units/<id>/label` - egyedi eszközpéldány nyomtatható címkéje
- `/locations` - készlethelyek listázása és szűrése
- `/locations/new` - új készlethely létrehozása
- `/movements` - készletmozgások listázása és létrehozása
- `/unassigned-invoices` - gazdátlan számlasorok listázása és létrehozása
- `/import` - Legacy Parkl Excel import kompatibilitási URL, csak admin felhasználóknak
- `/attention` - figyelmet igénylő készlet-, projekt-, beszerzési és pénzügyi tételek
- `/labels` - QR-kódok és eszköz-/példánycímkék belépési oldala
- `/documents` - projekt PDF-ek és munkalap-jegyzőkönyvek belépési oldala
- `/import-export` - normál import- és exportfolyamatok belépési oldala
- `/import-export/template` - új import sablon letöltése
- `/import-export/export/<export_type>` - projekt-, eszköz- vagy készlethelyexport
- `/help` - súgó és használati dokumentáció
- `/admin` - adminisztrációs eszközök, csak admin felhasználóknak
- `/admin/users` - felhasználói szerepkörök és aktív állapot kezelése, csak admin felhasználóknak
- `/legacy` - régi Parkl Excel import és import batch-ek, csak admin felhasználóknak
- `/legacy/parkl-excel-import` - régi Parkl Excel struktúra importja, csak admin felhasználóknak
- `/projects/<id>/pdf/equipment` - projekt eszközlista PDF
- `/projects/<id>/pdf/issue` - kiadási lista PDF
- `/projects/<id>/pdf/installation` - telepítési lista PDF
- `/projects/<id>/pdf/finance` - pénzügyi összesítő PDF

## Fejlesztési megjegyzés

A `forms.py` fájl egyelőre szándékosan minimális. Az MVP a validációt az `app.py` fájlban tartja, így nincs extra függőség, de később van hely WTForms vagy más validációs segédek számára.
