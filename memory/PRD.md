# ELS MHD – Einsatzleitsystem Malteser Hilfsdienst

## Problem Statement (Original)
Entwirf die hochwertigste Tablet-/Desktop-App fuer ein sanitaetsdienstliches Einsatzleitsystem (ELS MHD).
Gliederung in 9 Schritte. **Aktuell: Schritt 01 – Produktbasis & Designsystem.**

Spezifikationen: `github.com/DavidStaffe/els-app-dokumentation` (Ordner `/aktuell/`).
Produktionsnah, keine Showcase-Anwendung.

## Zielbild
Tablet- & Desktop-Web-App (Smartphone in spaeterer Version) zur Steuerung sanitaetsdienstlicher
Einsaetze bei Grossveranstaltungen: Patienten, Ressourcen, Transporte, Kommunikation, Konflikte,
Abschlussbericht mit PDF-Export.

## Rollen
- **Einsatzleiter (EL)**: Startet/beendet Incidents, Vollzugriff, Freigabe Abschlussbericht
- **Sanitaeter / Helfer**: Patientenerfassung, Zeitstempel, Transportanforderung, Konfliktmeldung
- **Dokumentar**: Nachbearbeitung, Berichtsvorschau, PDF-Export

## Tech-Stack
- Frontend: React 19, React Router 7, Tailwind CSS 3, shadcn/ui + Radix Primitives, Lucide Icons
- Backend: FastAPI, Motor (MongoDB Async), Pydantic
- Fonts: IBM Plex Sans + IBM Plex Mono
- Design-Tokens: CSS Variables (HSL), Dark-Mode Standard + Light-Mode Toggle

## Architektur – Aktueller Stand
```
/app/frontend/src/
├── App.js                          # BrowserRouter + AppShell
├── index.css                       # Design-Tokens (HSL), 4px-Raster, 3 Typo-Groessen
├── components/
│   ├── shell/
│   │   ├── AppShell.jsx            # Layout + Theme-Persistenz
│   │   ├── Sidebar.jsx             # Modul-Navigation (disabled fuer Schritt 02–09)
│   │   └── GlobalHeader.jsx        # Incident-Kontext, Rolle, Uhrzeit, Theme-Toggle
│   ├── primitives/
│   │   ├── StatusBadge.jsx         # + SichtungBadge (S1–S4)
│   │   ├── KpiTile.jsx
│   │   ├── FilterChip.jsx
│   │   ├── SectionCard.jsx
│   │   ├── DataTable.jsx
│   │   ├── ConfirmModal.jsx
│   │   └── index.js
│   └── ui/                         # shadcn primitives (unveraendert)
├── pages/
│   └── Home.jsx                    # Einstieg + Designsystem-Referenz (credit-sparsam)
└── lib/utils.js

/app/backend/
├── server.py                       # GET /api/ , GET /api/meta , POST/GET /api/status
└── .env
```

## Designsystem (Schritt 01 – V0.1)
- **Farben**: Primary BOS-Blau (HSL 205 90% 55%), Status rot/gelb/gruen/grau + info, Dark/Light
- **Typografie**: 3 Groessen laut Spec (0.8 / 0.9 / 1 rem) + Display + KPI
- **Fonts**: IBM Plex Sans (UI), IBM Plex Mono (Kennungen, Zahlen, Zeitstempel)
- **Spacing**: 4px-Raster (Tailwind-nativ)
- **Radius**: 0.375rem default, 0.5rem large, 0.25rem small
- **Komponenten**: Karte (SectionCard), Badge (StatusBadge, SichtungBadge), Chip (FilterChip),
  Button (shadcn), Modal (ConfirmModal), Tabelle (DataTable), KpiTile

## Implementierungsstatus

### ✅ Schritt 01 – Produktbasis & Designsystem (2026-04)
- CSS-Design-Tokens (Dark+Light), Tailwind-Erweiterung (Status-Farben, Fonts, Typo-Skalen)
- App-Shell mit persistenter Theme-Wahl (localStorage)
- Sidebar mit Modul-Navigation (Platzhalter fuer Schritt 02–09)
- GlobalHeader mit Incident-Kontext, Rolle, Uhrzeit, Demo-Badge-Support
- 6 Primitives: StatusBadge, SichtungBadge, KpiTile, FilterChip, SectionCard, DataTable, ConfirmModal
- Home-Screen als Einstieg + Designsystem-Referenz (kompakt, produktionsnah)
- Backend: `/api/meta` Endpoint
- data-testid auf allen interaktiven Elementen

### ✅ Schritt 02 – Einstieg & Incident-Auswahl (2026-04)
- Backend: Incident-Modell + CRUD (GET/POST/PATCH/DELETE /api/incidents, POST /api/incidents/demo),
  Query-Filter (?status, ?demo), automatisches `end_at` bei Status-Wechsel auf abgeschlossen
- Frontend: `IncidentContext` + Provider (listet, erstellt, aktiviert, schliesst, reaktiviert, loescht,
  Demo-Start), aktive ID persistiert in localStorage (`els-active-incident`)
- `IncidentList` Seite (`/`) mit Filter-Chips (alle/operativ/geplant/abgeschlossen/demo + Counts),
  Suche (Name/Ort/Typ), Loading-Skeleton, Empty-State
- `IncidentCard` mit Typ-Icon, DEMO-Badge, Status-Badge (operativ-Puls), Live-Dauer,
  Aktionen: Aktivieren, Lage oeffnen, Abschliessen, Reaktivieren, Loeschen (nur DEMO)
- `NewIncidentDialog` (Name, Typ, Ort, Startzeit, Beschreibung) mit Validierung, Fehleranzeige
- GlobalHeader: klickbarer Incident-Context (navigiert zu `/`), Live-Dauer-Anzeige, DEMO-Badge
- Sidebar: "Aktiver Incident"-Gruppe mit Lage aktiv nur bei gesetztem Incident
- Command-Palette: dynamische "Incident wechseln"-Gruppe (ein Eintrag pro Incident)
- Backend-Test (13/13 passed), Frontend-E2E (100% nach LOW-Issue-Fix)

### ✅ Schritt 03 – Patientenliste + Schnellerfassung (2026-04)
- Backend: Patient-CRUD pro Incident (GET/POST `/api/incidents/{id}/patients`, GET/PATCH/DELETE `/api/patients/{id}`)
- Auto-Kennung sequenziell pro Incident (atomic counter in Incident-Doc): P-0001, P-0002, ...
- Automatische Zeitstempel: sichtung_at, behandlung_start_at (bei Sichtung gesetzt),
  transport_angefordert_at (bei status=transportbereit), fallabschluss_at (bei entlassen/uebergeben)
- Cascade-Delete: Incident loeschen entfernt alle Patienten
- Frontend: `PatientContext` scoped auf activeIncident, KPI-Ableitung (total, S1-S3+S0, wartend/beh/transport)
- `PatientList`: DataTable mit Kennung (mono), SichtungBadge, Status-Badge, Verbleib, Live-Dauer,
  Notiz-Preview, Delete-Action, Row-Klick navigiert zu Detail
- Filter-Chips: Sichtung (multi, S1-S3+S0 mit counts) + Status (single select)
- KPI-Leiste: 8 Kacheln (Total, S1-S3+S0, Wartend, In Beh., Transport)
- `QuickEntryBar` (Smart Enhancement): Sticky bottom, 4 Sichtungs-Buttons mit Shortcuts 1/2/3/0
- `PatientDialog`: Sichtung-Grid-Auswahl, Status-/Verbleib-Select, Notiz
- Command-Palette: dynamische Gruppe "Patienten" mit Navigation zu Detail
- Sidebar: Patienten-Modul aktiv wenn Incident gesetzt
- Backend-Tests (22/22 passed), Frontend-E2E (100%)

### ✅ Schritt 04 – Patientendetail + Smart Enhancement (2026-04)
- **GLOBALE Umbenennung S4 → S0** (rueckwirkend): Backend Literal, idempotente DB-Migration on startup,
  Frontend-Konstanten, KPIs, Filter, QuickEntryBar-Shortcut `0`, Grid-Reihenfolge S1/S2/S3/S0
- Backend: Felder `transport_typ` + `fallabschluss_typ`, PATCH mit automatischer Status-Progression
  und Default-Verbleib
- Frontend `/patienten/:id`: Kopf (Kennung, SichtungBadge, Status, DEMO), 3 Prozesszeiten-KPIs,
  Sichtungs-Grid, Notiz mit debounced Auto-Save, Transport-Panel + Dialog, Fallabschluss-Panel +
  Dialog, Verbleib-Dropdown, vertikale Timeline mit 5 Events und Dauer-Deltas, Deep-Link-Support
- **Smart Enhancement Ein-Klick-Progression**: Dynamischer Next-Step-Button passt sich an Status an,
  oeffnet bei Bedarf Transport-/Fallabschluss-Dialog
- Backend-Tests (18/18 passed), Frontend-E2E (100%)

### ✅ Schritt 05 – Transportuebersicht + Drag & Drop (2026-04)
- **Fix QuickEntryBar**: Sichtungs-Buttons zentriert (flex-1 justify-center), rechter Spacer w-44
  reserviert Platz fuer Made-with-Emergent-Badge
- Backend: Transport-Modell + CRUD, **Auto-Create** beim Setzen von patient.transport_typ,
  **Auto-Complete** bei Patient-Fallabschluss, Cascade-Delete
- Frontend `/transport`: 2-Spalten Intern/Extern, je 4 Status-Buckets, 6 KPIs, draggable
  TransportCards, "N ohne Ressource"-Warnung
- **Smart Enhancement Drag & Drop ResourceBar**: 9 Drop-Targets, Drag Card auf Ressource weist zu,
  Typ-Mismatch verhindert Drop. Alternative Click: `ResourceAssignDialog`
- `NewTransportDialog` fuer manuelle Anlage
- Backend-Tests (19/19 passed), Frontend-E2E (100%)

### ✅ Schritt 06 – Ressourcen, Kommunikation & Konflikte (2026-04)
- **Backend**: 3 neue Modelle (Resource, Message) + Konflikt-Auto-Detection (nicht persistiert)
  - Resource-CRUD mit Lazy-Seed (9 Standard-Ressourcen on first GET: UHS Team 1-3, Radstreife 1,
    RTW 1-2, KTW 1-2, NEF 1)
  - **Resource-Sync**: Transport-Zuweisung → Ressource auf `im_einsatz`, Transport-Abschluss
    bzw. Ressource-Wechsel → `verfuegbar` (wenn nicht anderweitig belegt), sowohl bei POST als PATCH
  - Message-CRUD mit `POST /messages/{id}/ack` (quittiert_at + quittiert_von), Filter `?open_only=true`
  - **Konflikt-Auto-Detection** (`GET /incidents/{id}/konflikte`) mit 4 Regeln:
    1. S1-Patient wartend >5min (rot)
    2. Transport offen ohne Ressource >10min (gelb)
    3. Transport unterwegs >60min (gelb)
    4. Kritische Meldung unquittiert (rot)
  - Cascade-Delete: Incident entfernt auch resources + messages
- **Frontend** (shared `OpsContext` + 3 Seiten):
  - `/ressourcen` mit **Statusmatrix** (5 Kategorien × 4 Status farbkodiert mit Counts), 5 KPIs,
    zwei Spalten (Intern/Extern) mit inline Status-Select
  - `/kommunikation` mit priorisierter Liste (rot für kritisch mit linker Seitenleiste, gelb für
    dringend), 4 KPIs, Filter-Chips (alle/offen/kritisch), Neu-Dialog mit Prio/Kat/Von/Text,
    Quittieren + Delete
  - `/konflikte` mit Auto-Refresh (30s), farbkodierte Cards (data-schwere=rot/gelb/info), Live-Dauer,
    "Oeffnen" navigiert zu Bezug (Patient/Transport/Kommunikation), "Quittieren" fuer Meldungs-Konflikte
- Sidebar + Command-Palette: Ressourcen/Kommunikation/Konflikte aktiv (Shortcuts G R / G K / G X)
- LagePlaceholder: alle Module verlinkt
- Backend-Tests (27/27 passed), Frontend-E2E (100%, null Issues; ein LOW-Priority-Hinweis zu
  POST-Sync direkt gefixt)
- **Fix QuickEntryBar**: Sichtungs-Buttons zentriert (flex-1 justify-center), rechter Spacer w-44
  reserviert Platz fuer "Made with Emergent"-Badge (S0-Button >180px vom rechten Rand)
- Backend: `Transport`-Modell (typ, ziel, ressource, status, 4 Zeitstempel), CRUD-Endpoints
  `/api/incidents/{id}/transports` + `/api/transports/{id}`, Filter `?typ=` `?status=`
- **Auto-Create**: Setzen von `patient.transport_typ` legt automatisch Transport-Eintrag
  (status=offen, ziel=uhs bei intern / rd bei extern, patient_kennung+sichtung kopiert) an
- **Auto-Complete**: Patient-Status-Wechsel auf entlassen/uebergeben schliesst zugehoerige
  Transporte automatisch ab
- Cascade-Delete: Incident loeschen entfernt Patienten UND Transporte
- Automatische Zeitstempel: `zugewiesen_at` (bei Ressource), `gestartet_at` (status=unterwegs),
  `abgeschlossen_at` (status=abgeschlossen)
- Frontend: `TransportContext` scoped auf activeIncident, 6 KPIs
- `/transport` 2-Spalten-Layout (Intern UHS / Extern RD+KH), je 4 Status-Buckets
- `TransportCard`: Sichtung, Kennung (Link zu Patient), Ziel, Ressource (rot wenn fehlt),
  Live-Dauer, Draggable, Action-Buttons (Abfahrt, Abschliessen, Ressource...)
- **Smart Enhancement – Drag & Drop Ressourcen-Zuweisung**: `ResourceBar` sticky bottom mit
  9 Drop-Targets (4 UHS-Teams + 5 Rettungsmittel), Drag einer Karte weist Ressource zu +
  setzt status=zugewiesen. Typ-Mismatch (intern/extern) verhindert Drop. Alternative:
  Click auf "Ressource..." oeffnet `ResourceAssignDialog` mit Grid-Auswahl
- `NewTransportDialog` fuer manuelle Anlage (ohne Patient, z.B. Materialfahrten)
- Spalten-Kopf zeigt "N ohne Ressource"-Warnung fuer fehlende Zuweisungen
- Bucket Dropping: Transport kann zurueck in "Offen"-Bucket gedroppt werden → entfernt Ressource
- Sidebar: Transport-Modul aktiv bei Incident
- Command-Palette: Transport-Navigation ueber "G T"
- Backend-Tests (19/19 passed inkl. Auto-Create + Auto-Complete + Cascade), Frontend-E2E (100%, null Issues)
- **GLOBALE Umbenennung S4 → S0** (rueckwirkend): Backend Literal, DB-Migration (idempotent on startup,
  alle S4-Eintraege -> S0), Frontend-Konstanten, KPIs, Filter, QuickEntryBar-Shortcuts (0 = S0),
  SichtungsGrid-Reihenfolge S1/S2/S3/S0
- Backend: Neue Felder `transport_typ` (intern/extern), `fallabschluss_typ` (rd_uebergabe/entlassung/manuell),
  PATCH-Logik mit automatischer Status-Progression + Default-Verbleib (rd bei RD-Uebergabe, event bei Entlassung)
- Frontend `/patienten/:id`:
  - Kopf: Kennung (mono, display), SichtungBadge, Status, DEMO, Incident-Name
  - 3 Prozesszeiten-KPIs (Seit Sichtung, Behandlungsdauer, Seit Transport-Anforderung) mit Live-Timer
  - **Smart Enhancement Ein-Klick-Progression** (pd-next-step): Passt sich dynamisch an Status an,
    oeffnet bei Bedarf Transport-Dialog oder Fallabschluss-Dialog
  - Sichtungs-Grid (S1/S2/S3/S0, farbkodiert)
  - Notiz mit debounced Auto-Save (800ms)
  - Transport-Panel + Dialog (intern/extern)
  - Fallabschluss-Panel + Dialog (rd_uebergabe/entlassung/manuell)
  - Verbleib-Dropdown mit Sofort-Save
  - Vertikale Timeline mit 5 Events + Dauer-Deltas zwischen Ereignissen + Live-Dauer seit letztem Event
  - Deep-Link-Support: Direkt via URL ladbar, setzt activeIncident automatisch
- Command-Palette: Patient-Sprungziel navigiert nun zu Detail-Screen
- Backend-Tests (18/18 passed), Frontend-E2E (100%, null Issues)
- Backend: Patient-CRUD pro Incident (GET/POST `/api/incidents/{id}/patients`, GET/PATCH/DELETE `/api/patients/{id}`)
- Auto-Kennung sequenziell pro Incident (atomic counter in Incident-Doc): P-0001, P-0002, ...
- Automatische Zeitstempel: sichtung_at, behandlung_start_at (bei Sichtung gesetzt),
  transport_angefordert_at (bei status=transportbereit), fallabschluss_at (bei entlassen/uebergeben)
- Cascade-Delete: Incident loeschen entfernt alle Patienten
- Frontend: `PatientContext` scoped auf activeIncident, KPI-Ableitung (total, S1-S4, wartend/beh/transport)
- `PatientList`: DataTable mit Kennung (mono), SichtungBadge, Status-Badge, Verbleib, Live-Dauer,
  Notiz-Preview, Delete-Action
- Filter-Chips: Sichtung (multi, S1-S4 mit counts) + Status (single select)
- KPI-Leiste: 8 Kacheln (Total, S1-S4, Wartend, In Beh., Transport)
- **`QuickEntryBar` (Smart Enhancement)**: Sticky bottom, 4 grosse farbkodierte Sichtungs-Buttons,
  Tastaturkuerzel 1/2/3/4 (legt Patient sofort mit Sichtung+status=in_behandlung an),
  N-Taste oeffnet Detail-Dialog. Shortcuts in Inputs/Textarea deaktiviert
- `PatientDialog`: Sichtung-Grid-Auswahl, Status-/Verbleib-Select, Notiz-Feld. Fuer Neu + Edit
- Command-Palette: dynamische Gruppe "Patienten" mit je einem Eintrag pro Patient (Scroll-Highlight)
- Sidebar: Patienten-Modul aktiv wenn Incident gesetzt
- Backend-Tests (22/22 passed), Frontend-E2E (100%)
- Backend: Incident-Modell + CRUD (GET/POST/PATCH/DELETE /api/incidents, POST /api/incidents/demo),
  Query-Filter (?status, ?demo), automatisches `end_at` bei Status-Wechsel auf abgeschlossen
- Frontend: `IncidentContext` + Provider (listet, erstellt, aktiviert, schliesst, reaktiviert, loescht,
  Demo-Start), aktive ID persistiert in localStorage (`els-active-incident`)
- `IncidentList` Seite (`/`) mit Filter-Chips (alle/operativ/geplant/abgeschlossen/demo + Counts),
  Suche (Name/Ort/Typ), Loading-Skeleton, Empty-State
- `IncidentCard` mit Typ-Icon, DEMO-Badge, Status-Badge (operativ-Puls), Live-Dauer,
  Aktionen: Aktivieren, Lage oeffnen, Abschliessen, Reaktivieren, Loeschen (nur DEMO)
- `NewIncidentDialog` (Name, Typ, Ort, Startzeit, Beschreibung) mit Validierung, Fehleranzeige
- GlobalHeader: klickbarer Incident-Context (navigiert zu `/`), Live-Dauer-Anzeige, DEMO-Badge
- Sidebar: "Aktiver Incident"-Gruppe mit Lage aktiv nur bei gesetztem Incident
- Command-Palette: dynamische "Incident wechseln"-Gruppe (ein Eintrag pro Incident),
  `handleStartDemo`/`handleNewIncident` realgeschaltet
- LagePlaceholder (`/lage`): Uebersicht mit Modulen, Hinweis auf Folge-Schritte
- Backend-Test (13/13 passed), Frontend-E2E (95%+, nur 2 LOW Issues gefunden und gefixt)

### 🔜 Backlog (Schritte 07–09)
- **Schritt 07 (P1)**: Produktreife – Leer-/Fehler-/Loading-States, Navigation
- **Schritt 08 (P2)**: Demo-Integration – realistische Vordaten (Patienten, Transporte etc.)
- **Schritt 09 (P1)**: Auswertung & Abschluss – 14-Kapitel-Bericht, PDF-Export, Blocker-Check

## Next Actions
1. Schritt 02 starten: Incident-Modell (Backend), Incident-Liste-Screen (Frontend), Incident-Context
2. Persistenz-Strategie festlegen (MongoDB-Collections fuer Incidents/Patienten/Transporte)
3. Spec-Detaildateien einbinden: Feldkatalog, Kapitelstruktur, Kennzahlenkatalog

## Referenzen
- Figma-Komponenten-Briefing V0.1
- Handlungsablauf & Rollen V0.1
- Screens & UX V0.1
- Gesamtspezifikation V1.0
