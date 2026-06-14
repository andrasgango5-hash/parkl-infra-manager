DOC_GROUPS = [
    {
        "id": "start",
        "title": "Kezdés",
        "description": "A rendszer célja, alapfogalmai és az első napi használat.",
        "icon": "bi-compass",
        "pages": ["overview", "quick-start"],
    },
    {
        "id": "modules",
        "title": "Modulok",
        "description": "Az ERP üzleti moduljainak részletes használata.",
        "icon": "bi-grid",
        "pages": [
            "dashboard",
            "devices",
            "locations",
            "movements",
            "projects",
            "drawings",
            "qr-labels",
            "m2m",
            "finance",
        ],
    },
    {
        "id": "workflows",
        "title": "Munkafolyamatok",
        "description": "Lépésről lépésre követhető napi use-case-ek.",
        "icon": "bi-signpost-split",
        "pages": ["workflows"],
    },
    {
        "id": "platform",
        "title": "Platform",
        "description": "Integrációk, architektúra és rendszerverzió.",
        "icon": "bi-diagram-3",
        "pages": ["integrations", "technology", "version"],
    },
    {
        "id": "support",
        "title": "Támogatás",
        "description": "Gyakori kérdések és tervezett fejlesztések.",
        "icon": "bi-life-preserver",
        "pages": ["faq", "roadmap"],
    },
]


DOC_PAGES = {
    "overview": {
        "title": "Rendszer áttekintés",
        "summary": "A Parkl Infra Manager célja, fő fogalmai és teljes üzleti életciklusa.",
        "icon": "bi-building-gear",
        "keywords": ["ERP", "Parkl", "EV", "infrastruktúra", "életciklus"],
        "sections": [
            {
                "title": "Mi a Parkl Infra Manager?",
                "paragraphs": [
                    "A Parkl Infra Manager egy belső üzemeltetési ERP a parkolási, beléptetési és EV-töltési infrastruktúra projektjeinek kezelésére.",
                    "Egy rendszerben kapcsolja össze a beszerzést, a fizikai készletet, a projekteket, az egyedi eszközpéldányokat, a pénzügyi adatokat és a helyszíni dokumentációt.",
                ],
                "bullets": [
                    "EV infrastruktúra projektek és telepítési helyszínek kezelése",
                    "Bulk készlet és egyedi DeviceUnit példányok nyilvántartása",
                    "Projektkövetés és auditált készletmozgások",
                    "Pénzügyi, beszállítói és számlasor-riportok",
                    "QR-alapú eszközazonosítás és címkenyomtatás",
                    "M2M SIM és Teltonika RMS adatforgalom-kezelés",
                    "Munkalapok, projekt PDF-ek és helyszíni rajzok",
                ],
            },
            {
                "title": "Az infrastruktúra életciklusa",
                "diagram": [
                    "Beszerzés",
                    "Raktár",
                    "Projekt",
                    "Telepítés",
                    "Üzemeltetés",
                    "Szerviz",
                    "Selejtezés",
                ],
                "paragraphs": [
                    "Minden állapotváltás auditált StockMovement rekordot hoz létre. Egyedi követésnél a DeviceUnit, mennyiségi követésnél a BulkStockBalance az aktuális valós készletforrás."
                ],
            },
            {
                "title": "Alapfogalmak",
                "definitions": [
                    ("Device", "Termék- vagy beszerzési törzs, amely a közös műszaki és pénzügyi adatokat tárolja."),
                    ("DeviceUnit", "Konkrét fizikai példány saját azonosítóval, QR-kóddal, státusszal, projekttel és készlethellyel."),
                    ("Készlethely", "Fizikai logisztikai hely, például raktár, szervizautó, szerviz vagy beszállító."),
                    ("Projekt", "Ügyfélmunka és telepítési helyszín; a kiadott és telepített infrastruktúra aktív gazdája."),
                    ("StockMovement", "Nem módosítható történeti napló minden készletműveletről."),
                ],
            },
        ],
    },
    "quick-start": {
        "title": "Gyors kezdés",
        "summary": "Az első projekt, készlethely, eszköz és mozgás rögzítése.",
        "icon": "bi-rocket-takeoff",
        "keywords": ["első lépések", "kezdés", "projekt", "eszköz"],
        "sections": [
            {
                "title": "Első napi ellenőrzőlista",
                "steps": [
                    ("Nyisd meg a Dashboardot", "Ellenőrizd a figyelmet igénylő és pénzügyileg nyitott tételeket."),
                    ("Hozz létre logisztikai készlethelyet", "Például Fő raktár vagy Szervizautó."),
                    ("Hozz létre projektet", "Add meg az ügyfelet és a telepítési helyszín adatait."),
                    ("Rögzíts vagy importálj eszközt", "Válassz egyedi példányos vagy mennyiségi készletet."),
                    ("Indíts üzleti műveletet", "Foglalás, kiadás, telepítés vagy visszavétel mindig az eszköz/projekt adatlapjáról induljon."),
                    ("Készíts dokumentációt", "Nyomtass QR-címkét, projekt PDF-et vagy munkalapot."),
                ],
            },
            {
                "title": "Melyik nézetből induljak?",
                "definitions": [
                    ("Projektvezető", "Projektek → projekt adatlap → eszközök, pénzügy, rajzok és PDF-ek."),
                    ("Raktáros", "Eszközök vagy Készlethelyek → konkrét tétel/példány → készletművelet."),
                    ("Technikus", "QR-kód → DeviceUnit adatlap, illetve Munkalapok → új helyszíni jegyzőkönyv."),
                    ("Pénzügy", "Pénzügyi áttekintés → projekt, beszállító, számla vagy tisztázandó számlasor."),
                ],
            },
        ],
    },
    "dashboard": {
        "title": "Dashboard",
        "summary": "A napi munkakezdő felület KPI-kkal, figyelmeztetésekkel és gyorsműveletekkel.",
        "icon": "bi-speedometer2",
        "keywords": ["KPI", "áttekintés", "figyelmeztetés", "dashboard"],
        "sections": [
            {
                "title": "Mire szolgál?",
                "paragraphs": ["A Dashboard a napi állapotfelmérés kiindulópontja. Nem teljes riport, hanem a következő intézkedést segítő vezetői és operatív összefoglaló."],
                "bullets": [
                    "Raktáron, előjegyezve, kiadva és telepítve lévő készlet",
                    "Beérkezésre váró és pénzügyileg nyitott tételek",
                    "Gazdátlan számlasorok és figyelmet igénylő rekordok",
                    "Gyors elérés projektekhez, importhoz, eszközökhöz és dokumentációhoz",
                ],
            },
            {
                "title": "Mire figyelj?",
                "callout": "A Dashboard számai az aktív DeviceUnit és BulkStockBalance állományból készülnek. A Device legacy státuszmezői nem a valós készletforrások.",
            },
            {"title": "Képernyőkép helye", "media": "Dashboard KPI-k és figyelmet igénylő lista képernyőképe."},
        ],
    },
    "devices": {
        "title": "Eszközök",
        "summary": "Terméktörzs, bulk készlet, egyedi példányok és életciklus-státuszok.",
        "icon": "bi-boxes",
        "keywords": ["Device", "DeviceUnit", "asset tag", "sorozatszám", "bulk", "unit"],
        "sections": [
            {
                "title": "Device és DeviceUnit",
                "definitions": [
                    ("Device", "A terméktörzs és beszerzési tétel. Itt vannak az árak, beszállító, kategória és közös termékadatok."),
                    ("DeviceUnit", "Egyedi fizikai példány. Saját unit code, asset tag, sorozatszám, QR, státusz, projekt és készlethely tartozik hozzá."),
                    ("Bulk tétel", "Mennyiségben kezelt fogyó- vagy segédanyag, amelyet részleges mennyiséggel lehet mozgatni."),
                ],
            },
            {
                "title": "Azonosítók",
                "bullets": [
                    "Asset tag: belső Parkl eszközazonosító.",
                    "Sorozatszám: gyártói azonosító, unit követésnél később is megadható.",
                    "Unit code: a rendszerben egyedi példányazonosító.",
                    "Kategória: a keresést, riportot és vizuális csoportosítást segíti.",
                ],
            },
            {
                "title": "Életciklus-státuszok",
                "definitions": [
                    ("IN_STOCK – Raktáron", "Fizikailag logisztikai készlethelyen, projekthez nem rendelve."),
                    ("RESERVED – Előjegyezve", "Fizikailag raktárban marad, de egy konkrét projekthez le van foglalva."),
                    ("ISSUED – Kiadva", "Aktív projekten van, logisztikai készlethelye nincs."),
                    ("INSTALLED – Telepítve", "A projekt helyszínén telepített infrastruktúra."),
                    ("RETURNED – Visszavéve", "Visszaérkezett, raktárra helyezhető vagy újra kiadható."),
                    ("IN_SERVICE – Szervizben", "Szerviz vagy javítás alatt, aktív projektkészletnek nem számít."),
                    ("SCRAPPED – Selejtezve", "Nem mozgatható és aktív készletbe nem számít."),
                ],
            },
            {"title": "Képes magyarázat helye", "media": "Eszközlista, Device adatlap és DeviceUnit állapotkártyák képernyőképei."},
        ],
    },
    "locations": {
        "title": "Készlethelyek",
        "summary": "A fizikai logisztikai tárolási helyek és a projekt-helyszín elkülönítése.",
        "icon": "bi-buildings",
        "keywords": ["raktár", "készlethely", "szervizautó", "szerviz", "beszállító"],
        "sections": [
            {
                "title": "Mit jelent a készlethely?",
                "paragraphs": ["A Location kizárólag fizikai logisztikai hely. A projekt telepítési címe és GPS-adatai a Project rekord részei, nem készlethelyek."],
                "bullets": ["Raktár", "Szervizautó", "Szerviz / javítás", "Beszállító", "Alvállalkozó raktár"],
            },
            {
                "title": "Projekt és telepítési hely",
                "callout": "Kiadott vagy telepített eszköznél project_id van, location_id nincs. A telepítési helyszín adatait a projekt tartalmazza.",
            },
            {
                "title": "Készlethely adatlap",
                "paragraphs": ["Az adatlap csak a ténylegesen ott található unitokat és bulk egyenlegeket mutatja. A RESERVED készlet fizikailag látszik, de foglaltként elkülönül."],
            },
            {"title": "Képernyőkép helye", "media": "Készlethely detail szabad és előjegyzett készlet bontással."},
        ],
    },
    "movements": {
        "title": "Mozgások",
        "summary": "A készlet történeti auditnaplója és a támogatott állapotátmenetek.",
        "icon": "bi-arrow-left-right",
        "keywords": ["kiadás", "visszavétel", "áthelyezés", "selejtezés", "StockMovement"],
        "sections": [
            {
                "title": "Alapelv",
                "callout": "Státuszt és készlethelyet nem szabad közvetlenül átírni. Minden üzleti változás StockMovement rekorddal történik; a mozgás nem módosítható és nem törölhető.",
            },
            {
                "title": "Gyakori műveletek",
                "definitions": [
                    ("Előjegyzés", "Raktáron maradó készlet lefoglalása konkrét projekthez."),
                    ("Kiadás", "Készlet átadása projektnek; a logisztikai készlethely megszűnik."),
                    ("Telepítés", "Kiadott készlet telepített státuszba helyezése."),
                    ("Visszavétel", "Projektből logisztikai helyre történő visszahozás."),
                    ("Áthelyezés", "Készlet mozgatása logisztikai helyek között, státusz indokolatlan módosítása nélkül."),
                    ("Szerviz", "Eszköz kivonása projektből és szervizhelyre mozgatása."),
                    ("Selejtezés", "Végleges kivonás az aktív készletből."),
                ],
            },
            {
                "title": "Példa",
                "steps": [
                    ("Raktáron", "EV-001 a Fő raktárban van."),
                    ("Előjegyzés", "EV-001 lefoglalva PRK-001 részére, de még fizikailag a raktárban."),
                    ("Kiadás", "EV-001 projektkészlet, location_id nélkül."),
                    ("Telepítés", "EV-001 telepítve a projekt helyszínén."),
                    ("Visszavétel", "EV-001 visszakerül a Fő raktárba és kikerül a projektből."),
                ],
            },
        ],
    },
    "projects": {
        "title": "Projektek",
        "summary": "Ügyfél, telepítési hely, projektkészlet, dokumentáció és pénzügyi kapcsolatok.",
        "icon": "bi-kanban",
        "keywords": ["projekt", "helyszín", "ügyfél", "BOM", "PDF"],
        "sections": [
            {
                "title": "Projekt létrehozása",
                "bullets": [
                    "Egyedi projektkód és név",
                    "Ügyfél és kapcsolattartási adatok",
                    "Helyszín neve, cím, város, ország",
                    "GPS koordináta és Google Maps link",
                    "Projektstátusz és helyszíni megjegyzés",
                ],
            },
            {
                "title": "Projektkészlet",
                "paragraphs": ["A projekt adatlap külön mutatja az előjegyzett, kiadott, telepített unitokat és a bulk mennyiségi tételeket. A forrás DeviceUnit.project_id és BulkStockBalance.project_id."],
            },
            {
                "title": "Kapcsolódó funkciók",
                "bullets": ["Helyszíni rajzok", "Projekt eszközlista és BOM", "Kiadási és telepítési PDF", "Pénzügyi összesítő", "Mozgástörténet"],
            },
            {"title": "Képernyőkép helye", "media": "Projekt detail összesítő, készlet és PDF műveletek."},
        ],
    },
    "drawings": {
        "title": "Rajzok / tervező",
        "summary": "Projektalapú helyszíni felmérési és infrastruktúra-vázlatok Fabric.js vásznon.",
        "icon": "bi-layers",
        "keywords": ["Fabric.js", "rajz", "kábel", "réteg", "alaprajz"],
        "sections": [
            {
                "title": "Szerkesztőfelület",
                "bullets": ["Nagyítható és pásztázható vászon", "Ikonpaletta infrastruktúra-elemekkel", "Objektumtulajdonságok", "Grid és snap", "Rétegkezelés"],
            },
            {
                "title": "Infrastruktúra és kábelek",
                "paragraphs": ["EV töltők, kamerák, sorompók, hálózati és elektromos elemek helyezhetők el. A kábelvonalak típusa, színe, felirata és műszaki jelentése mentésre kerül."],
            },
            {
                "title": "ERP-kapcsolat",
                "paragraphs": ["A projekthez rendelt eszközök elhelyezhetők a rajzon, és az objektum megőrizheti a kapcsolatot a rendszerbeli eszközzel."],
            },
            {"title": "Képernyőkép helye", "media": "Teljes rajzszerkesztő, ikonpaletta, tulajdonságpanel és kábelrajzolás."},
            {"title": "Workflow ábra helye", "media": "Alaprajz feltöltése → elemek elhelyezése → kábelezés → mentés → PNG/PDF export."},
        ],
    },
    "qr-labels": {
        "title": "QR / Címkék",
        "summary": "Eszköz- és DeviceUnit-azonosítás stabil adatlap-URL-lel és PDF-címkékkel.",
        "icon": "bi-qr-code",
        "keywords": ["QR", "címke", "PDF", "DeviceUnit", "asset tag"],
        "sections": [
            {
                "title": "QR-stratégia",
                "definitions": [
                    ("Eszköztörzs QR", "A Device adatlapjára mutat; bulk vagy közös terméktételnél használható."),
                    ("DeviceUnit QR", "A konkrét fizikai példány adatlapjára mutat; töltő, router, kamera és más egyedi eszköz esetén ajánlott."),
                    ("Címke PDF", "Kisméretű, nyomtatható Parkl címke azonosítóval és QR-kóddal."),
                ],
            },
            {
                "title": "Címkeközpont",
                "paragraphs": ["Az Eszközcímkék és DeviceUnit címkék külön kereshető listában érhetők el. A QR előnézet PNG, az egyedi címke PDF formátumban nyitható meg."],
            },
            {"title": "Képernyőkép helye", "media": "DeviceUnit címkelista és nyomtatható QR-címke."},
        ],
    },
    "m2m": {
        "title": "M2M SIM-ek",
        "summary": "Mobil előfizetések, ICCID-k, adatcsomagok és Teltonika RMS szinkron.",
        "icon": "bi-sim",
        "keywords": ["M2M", "SIM", "ICCID", "Teltonika", "RMS", "adatforgalom"],
        "sections": [
            {
                "title": "Előfizetés és SIM",
                "bullets": ["Előfizető és szerződés adatai", "Hívószám, eszközszám és ICCID", "Helyszín és kapcsolódó Teltonika eszköz", "Aktuális csomag, havidíj és státusz"],
            },
            {
                "title": "RMS összekötés",
                "paragraphs": ["Az elsődleges üzleti kapcsolat az ICCID. Az RMS device ID technikai azonosító, mert routercsere esetén változhat, miközben a SIM követése folytatódik."],
                "callout": "Az RMS token környezeti változóból érkezik. A havi fogyasztás a data-usage endpoint napi rekordjainak összegzése, nem a /devices diagnosztikai sent/received mezője.",
            },
            {
                "title": "Adatforgalom",
                "bullets": ["Havi usage történet", "80%-os csomaglimit figyelmeztetés", "Túlforgalmazás piros jelzéssel", "Manual, import és teltonika_api források"],
            },
        ],
    },
    "finance": {
        "title": "Pénzügyi modul",
        "summary": "Projektköltségek, készletérték, beszállítók, számlák és tisztázandó sorok.",
        "icon": "bi-graph-up-arrow",
        "keywords": ["pénzügy", "számla", "BOM", "beszállító", "készletérték", "ÁFA"],
        "sections": [
            {
                "title": "Pénzügyi áttekintés",
                "bullets": ["Legértékesebb projektek", "Készletérték készlethelyenként", "Beszállítói költések", "Fizetetlen számlák", "Hiányos pénzügyi adatok"],
            },
            {
                "title": "Drill-down nézetek",
                "definitions": [
                    ("Projekt pénzügy", "Aktív projektkészlet, számlasorok, költségösszesítő és BOM."),
                    ("Készletérték", "Fizikailag logisztikai készlethelyen lévő unit és bulk állomány."),
                    ("Beszállítók", "Beszerzési érték és számlaállapot beszállítónként."),
                    ("Számlák", "Eszközszámlák és importált/manuális számlasorok."),
                    ("Gazdátlan számlasorok", "Pénzügyi tisztázólista projekthez vagy eszközhöz rendeléshez."),
                ],
            },
            {
                "title": "Ár- és devizalogika",
                "paragraphs": ["HUF és EUR külön összesül, automatikus árfolyamváltás nincs. A quantity × unit net adja a nettó összesent; opcionális vat_rate esetén számolható a bruttó érték."],
            },
        ],
    },
    "workflows": {
        "title": "Munkafolyamatok",
        "summary": "A leggyakoribb operatív feladatok lépésről lépésre.",
        "icon": "bi-signpost-split",
        "keywords": ["use-case", "kiadás", "visszavétel", "QR", "M2M"],
        "sections": [
            {
                "title": "Új eszköz felvétele",
                "steps": [
                    ("Eszközök → Új eszköz", "Válaszd az egyedi nyilvántartott eszköz vagy mennyiségi készlet típust."),
                    ("Add meg a termékadatokat", "Terméknév, kategória, gyártó, modell és darabszám/mennyiség."),
                    ("Válassz kezdő állapotot", "Raktárkészlet, projektre előfoglalás vagy közvetlen projektkiadás."),
                    ("Ellenőrizd a létrehozást", "Unit követésnél automatikusan létrejönnek az egyedi példányok."),
                ],
            },
            {
                "title": "Eszköz kiadása projektre",
                "steps": [
                    ("Nyisd meg az eszközt vagy példányt", "Unit esetén mindig a konkrét DeviceUnitot válaszd."),
                    ("Válaszd a Kiadás műveletet", "Add meg a célprojektet."),
                    ("Ellenőrizd a foglalást", "RESERVED példány csak ugyanarra a projektre adható ki."),
                    ("Mentsd a műveletet", "A készlethely megszűnik, az eszköz megjelenik a projekt alatt."),
                ],
            },
            {
                "title": "Telepített eszköz visszavétele",
                "steps": [
                    ("Nyisd meg a projektet vagy DeviceUnitot", "Válaszd ki a telepített eszközt."),
                    ("Indíts Visszavétel műveletet", "A cél logisztikai készlethely kötelező."),
                    ("Ellenőrizd az eredményt", "A project_id törlődik, a location_id a kiválasztott raktár vagy szervizautó lesz."),
                ],
            },
            {
                "title": "QR címke generálás",
                "steps": [
                    ("Nyisd meg a QR / címkék modult", "Válassz Eszköztörzs vagy DeviceUnit listát."),
                    ("Keress azonosítóra", "Asset tag, unit code vagy sorozatszám alapján."),
                    ("Nyisd meg vagy töltsd le", "A QR előnézet és a címke PDF külön művelet."),
                ],
            },
            {
                "title": "M2M SIM felvétele",
                "steps": [
                    ("M2M SIM-ek → Új előfizetés", "Rögzítsd a szerződés- és SIM-adatokat."),
                    ("Add meg az ICCID-t", "Ez az RMS összekötés elsődleges üzleti kulcsa."),
                    ("Rögzíts csomagot", "Add meg a havidíjat és adatcsomagot."),
                    ("Indíts RMS szinkront", "Admin/manager jogosultsággal frissítsd az eszköz- és havi usage adatokat."),
                ],
            },
        ],
    },
    "integrations": {
        "title": "Integrációk",
        "summary": "Excel, Teltonika RMS, QR, PDF és térképi kapcsolatok.",
        "icon": "bi-plug",
        "keywords": ["integráció", "Excel", "RMS", "PDF", "Google Maps"],
        "sections": [
            {
                "title": "Excel import / export",
                "paragraphs": ["A napi import sablon Projects, Devices és Locations munkalapokat kezel dry-run előnézettel. A régi Parkl Excel import külön, admin-only Legacy funkció."],
            },
            {
                "title": "Teltonika RMS",
                "paragraphs": ["A /devices adatok ICCID alapján kapcsolódnak az M2M előfizetésekhez. A havi data usage 7 napos chunkokban kérdeződik le és havi rekordként frissül."],
            },
            {
                "title": "Dokumentum és azonosítás",
                "bullets": ["ReportLab PDF-ek", "QR-kódok belső adatlap-URL-lel", "Projekt Google Maps link", "Fabric.js rajz JSON és PNG/PDF export"],
            },
        ],
    },
    "technology": {
        "title": "Technológiai háttér",
        "summary": "Az alkalmazás backendje, adatbázisa, frontendje és üzemeltetési környezete.",
        "icon": "bi-cpu",
        "keywords": ["Flask", "SQLAlchemy", "Alembic", "Bootstrap", "Fabric.js", "Hetzner"],
        "sections": [
            {
                "title": "Backend",
                "bullets": ["Python 3", "Flask", "Flask-SQLAlchemy", "Flask-Migrate / Alembic", "Gunicorn production WSGI"],
            },
            {
                "title": "Adatbázis",
                "bullets": ["SQLite helyi fejlesztési fallback", "PostgreSQL-ready DATABASE_URL konfiguráció", "Alembic migrációk", "SQLAlchemy-kompatibilis üzleti logika"],
            },
            {
                "title": "Frontend",
                "bullets": ["Jinja2 szerveroldali template-ek", "Bootstrap 5", "Vanilla JavaScript", "Chart.js pénzügyi és M2M grafikonok", "Fabric.js helyszíni rajzszerkesztő"],
            },
            {
                "title": "Infrastruktúra",
                "bullets": ["Hetzner VPS", "Ubuntu", "GitHub verziókezelés", "Deploy script és környezeti változók", "Feltöltött fájlok és adatbázis külön mentési stratégiája"],
            },
            {
                "title": "Architektúra",
                "diagram": ["Böngésző", "Flask / Jinja", "SQLAlchemy", "SQLite / PostgreSQL", "RMS és fájltárolás"],
            },
        ],
    },
    "version": {
        "title": "Verzióinformáció",
        "summary": "Az aktuálisan futó build, Git commit és adatbázis-migráció állapota.",
        "icon": "bi-git",
        "keywords": ["verzió", "build", "commit", "migráció", "release"],
        "sections": [
            {
                "title": "Futásidejű rendszeradatok",
                "version_info": True,
            },
            {
                "title": "Hibajegyhez mit adj meg?",
                "bullets": ["Aktuális verzió", "Git commit", "Adatbázis migráció", "Érintett URL", "Pontos reprodukciós lépések", "Képernyőkép és időpont"],
            },
        ],
    },
    "faq": {
        "title": "Gyakori kérdések",
        "summary": "Rövid válaszok a leggyakoribb üzleti és technikai kérdésekre.",
        "icon": "bi-question-circle",
        "keywords": ["GYIK", "hiba", "segítség", "jogosultság"],
        "sections": [
            {
                "title": "Készlet és eszközök",
                "definitions": [
                    ("Miért nem szerkeszthető közvetlenül a státusz?", "Mert minden változásnak auditált StockMovement rekorddal kell történnie."),
                    ("Mikor használjak DeviceUnitot?", "Ha minden fizikai példányhoz külön QR, sorozatszám, projekt vagy státusz szükséges."),
                    ("Miért látszik a RESERVED eszköz a raktárban?", "Mert fizikailag ott van, de a projekt számára lefoglalt, ezért nem szabad készlet."),
                    ("Miért nem látszik a telepített eszköz a készlethelyen?", "Mert aktív projekten van, location_id nélkül."),
                ],
            },
            {
                "title": "Pénzügy és integráció",
                "definitions": [
                    ("Miért nem adódik össze HUF és EUR?", "Nincs automatikus árfolyamkezelés; a devizák külön riportálódnak."),
                    ("Miért nem kapcsolódik RMS eszköz a SIM-hez?", "Elsőként ellenőrizd az ICCID egyezését és a szükséges RMS scope-okat."),
                    ("Ki látja a pénzügyi modult?", "Admin és manager szerepkör."),
                    ("Törölhető egy készletmozgás?", "Nem. Szükség esetén auditált ellenmozgással vonható vissza."),
                ],
            },
        ],
    },
    "roadmap": {
        "title": "Roadmap",
        "summary": "A rendszer tervezett hosszabb távú fejlesztési irányai.",
        "icon": "bi-map",
        "keywords": ["roadmap", "mobil", "REST API", "közös szerkesztés"],
        "sections": [
            {
                "title": "Tervezett fejlesztések",
                "bullets": [
                    "Mobil alkalmazás technikusok és terepi üzemeltetés számára",
                    "PostgreSQL teljes production átállás és automatizált backup",
                    "Dokumentált REST API és külső rendszercsatlakozások",
                    "Offline terepi munkalap és QR workflow",
                    "Közös, verziózott rajzszerkesztés és kommentek",
                    "További beszállítói, pénzügyi és hálózati integrációk",
                ],
            },
            {
                "title": "Dokumentációs roadmap",
                "paragraphs": ["A képernyőkép-helyek később verziózott, feltöltött illusztrációkkal bővíthetők. A cikkregiszter támogatja új moduloldalak, kulcsszavak és workflow-k hozzáadását."],
            },
        ],
    },
}


def documentation_navigation():
    return [
        {
            **group,
            "pages": [
                {"slug": slug, **DOC_PAGES[slug]}
                for slug in group["pages"]
            ],
        }
        for group in DOC_GROUPS
    ]


def search_documentation(query):
    normalized = (query or "").strip().casefold()
    if not normalized:
        return []
    results = []
    for slug, page in DOC_PAGES.items():
        text_parts = [
            page["title"],
            page["summary"],
            *page.get("keywords", []),
        ]
        for section in page.get("sections", []):
            text_parts.append(section.get("title", ""))
            text_parts.extend(section.get("paragraphs", []))
            text_parts.extend(section.get("bullets", []))
            text_parts.extend(
                f"{term} {definition}"
                for term, definition in section.get("definitions", [])
            )
            text_parts.extend(
                f"{step} {description}"
                for step, description in section.get("steps", [])
            )
        haystack = " ".join(text_parts).casefold()
        if normalized in haystack:
            results.append({"slug": slug, **page})
    return results
