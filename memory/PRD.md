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
- Command-Palette: dynamische "Incident wechseln"-Gruppe (ein Eintrag pro Incident),
  `handleStartDemo`/`handleNewIncident` realgeschaltet
- LagePlaceholder (`/lage`): Uebersicht mit Modulen, Hinweis auf Folge-Schritte
- Backend-Test (13/13 passed), Frontend-E2E (95%+, nur 2 LOW Issues gefunden und gefixt)

### 🔜 Backlog (Schritte 03–09)
- **Schritt 03 (P0)**: Patientenliste (Kennung, Sichtung S1–S4, Status, Verbleib, Filter)
- **Schritt 04 (P0)**: Patientendetail (Zeitstempel, Behandlungsstart, Fallabschluss)
- **Schritt 05 (P0)**: Transportuebersicht (intern/extern, Ressource, Ziel, Status)
- **Schritt 06 (P1)**: Ressourcen + Kommunikation + Konflikte
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
