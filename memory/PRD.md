# ELS MHD – Einsatzleitsystem Malteser Hilfsdienst

## Problem Statement (Original)
Entwirf die hochwertigste Tablet-/Desktop-App fuer ein sanitaetsdienstliches Einsatzleitsystem (ELS MHD).
Gliederung urspruenglich in 9 Schritten, jetzt erweitert um Schritte 10-12 (Abschnitte, UHS/Betten, Integration).

Spezifikationen: `github.com/DavidStaffe/els-app-dokumentation` (Ordner `/aktuell/`).
Produktionsnah, keine Showcase-Anwendung.

## Zielbild
Tablet- & Desktop-Web-App (Smartphone in spaeterer Version) zur Steuerung sanitaetsdienstlicher
Einsaetze bei Grossveranstaltungen: Patienten, Ressourcen, Transporte, Kommunikation, Konflikte,
Einsatzabschnitte, UHS-Betten, Abschlussbericht mit PDF-Export.

## Rollen
- **Einsatzleiter (EL)**: Vollzugriff, Freigabe, alle Modulerstellungen
- **Sanitaeter / Helfer**: Patientenerfassung, Transportanforderung, Bett-Zuweisung, Meldungen
- **Dokumentar**: Nachbearbeitung, Berichtsvorschau, PDF-Export, Lesezugriff

## Tech-Stack
- Frontend: React 19, React Router 7, Tailwind CSS 3, shadcn/ui + Radix Primitives, Lucide Icons, sonner
- Backend: FastAPI, Motor (MongoDB Async), Pydantic
- Persistenz: MongoDB (Collections: incidents, patients, transports, resources, messages, abschnitte, betten, report_versions)

## Status – Schritte
| Schritt | Inhalt | Status |
|---------|--------|--------|
| 01 | Produktbasis & Designsystem (Dark-Cockpit, Command-Palette) | ✅ |
| 02 | Incident Entry & Selection | ✅ |
| 03 | Patient List & QuickEntry | ✅ |
| 04 | Patient Detail (S4→S0 Rename) | ✅ |
| 05 | Transport-Uebersicht (Intern/Extern, DnD) | ✅ |
| 06 | Ressourcen, Kommunikation, Konflikte (Auto-Detection) | ✅ |
| 07 | Rollenauswahl + Permission-Matrix | ✅ |
| 08 | Demo-Integration (Vordaten mit Abschnitten/Betten) | ✅ |
| 09 | Auswertungs-Dashboard, A4-Bericht, Versionen | ✅ |
| 10 | Einsatzabschnitte (Kachel, Farbe, Ressourcen-Zuordnung) | ✅ |
| 11 | UHS / Behandlungsbetten (Raster, Typ, Status, Patient-Assign) | ✅ |
| 12 | Integration (Nav, PatientDetail-Bett, Ressource-Abschnitt, Dashboard-KPIs, Hybrid-Wizard) | ✅ |

## Architektur
```
/app/
├── backend/
│   ├── server.py              # FastAPI + MongoDB (2162 Zeilen – Split empfohlen)
│   └── tests/
│       └── test_step10_12_abschnitte_betten.py   # pytest, 15/15 gruen
├── frontend/src/
│   ├── App.js                 # RoleProvider → Context → AppShell + Routes
│   ├── index.css              # Tokens + .report-a4 + @media print
│   ├── context/
│   │   ├── RoleContext.jsx    # PERMS-Matrix (inkl. abschnitt.*/bett.*)
│   │   ├── IncidentContext.jsx
│   │   ├── PatientContext.jsx
│   │   ├── TransportContext.jsx
│   │   └── OpsContext.jsx
│   ├── components/
│   │   ├── shell/             # AppShell, Sidebar (+nav-abschnitte/betten), GlobalHeader, RoleSelector
│   │   ├── command/           # CommandPalette (+Einsatzabschnitte/Behandlungsplaetze)
│   │   ├── primitives/        # StatusBadge, KpiTile, SectionCard, DataTable, FilterChip, ConfirmModal
│   │   ├── incidents/patients/transports/resources/messages/
│   │   └── ui/                # shadcn
│   ├── lib/
│   │   ├── api.js             # + Abschnitt + Bett Endpoints
│   │   ├── abschnitt-meta.js  # ABSCHNITT_FARBEN, BETT_TYPEN, BETT_STATUS
│   │   └── ...
│   └── pages/
│       ├── IncidentList.jsx   # + Hybrid-Wizard Redirect auf /abschnitte
│       ├── PatientList.jsx / PatientDetail.jsx  # + section-bett + BettPickDialog
│       ├── TransportList.jsx
│       ├── ResourceList.jsx   # + Abschnitt-Select je Zeile (intern+extern)
│       ├── MessageList.jsx
│       ├── KonfliktList.jsx
│       ├── AbschnittList.jsx  # Schritt 10
│       ├── BettenPage.jsx     # Schritt 11
│       └── AbschlussPage.jsx  # + kpi-abschnitte/betten-auslastung/betten-dauer/ohne-abschnitt + card-abschnitte
```

## Wichtige API-Endpunkte
### Bestehend
- `GET/POST /api/incidents`, `GET/PATCH/DELETE /api/incidents/{id}`
- `POST /api/incidents/demo` – Seed (jetzt mit 2 Abschnitten + 6 Betten)
- `GET/POST /api/incidents/{id}/patients`, `PATCH/DELETE /api/patients/{id}`
- `GET/POST /api/incidents/{id}/transports`, `PATCH/DELETE /api/transports/{id}`
- `GET/POST /api/incidents/{id}/resources`, `PATCH/DELETE /api/resources/{id}` (mit abschnitt_id)
- `GET/POST /api/incidents/{id}/messages`, `POST /api/messages/{id}/ack`
- `GET /api/incidents/{id}/konflikte`
- `GET /api/incidents/{id}/auswertung` – inkl. G_abschnitte + A.betten (Schritt 12)
- `GET /api/incidents/{id}/abschluss-check` – erweiterte Blocker/Warnungen (Schritt 12)
- `GET /api/incidents/{id}/report` – 14 Kapitel inkl. Abschnitte (Kap 2) + Betten (Kap 8)
- `GET/POST /api/incidents/{id}/report-versions`
- `PATCH /api/incidents/{id}/meta`

### Neu (Schritt 10 + 11)
- `GET/POST /api/incidents/{id}/abschnitte` – Liste + Create (optional aktiv-Filter)
- `GET/PATCH/DELETE /api/abschnitte/{id}` – Detail, Update, Delete (409 bei laufendem Incident)
- `GET/POST /api/incidents/{id}/betten` – Liste + Create (Filter: status, abschnitt_id)
- `POST /api/incidents/{id}/betten/bulk` – Bulk-Anlage (anzahl/typ/praefix)
- `GET/PATCH/DELETE /api/betten/{id}` – Detail, Update, Delete (409 wenn belegt)
- `POST /api/betten/{id}/assign` – Patient zuweisen (setzt belegt_seit + patient.bett_id)
- `POST /api/betten/{id}/release` – Bett freigeben (automatisch bei Transport-Abschluss + Fallabschluss)

## Rollen-Berechtigungen (Schritt 12 Update)
| Aktion | EL | Helfer | Dokumentar |
|--------|----|---------|------------|
| abschnitt.create / update / delete | ✅ | ❌ | ❌ |
| abschnitt.assign_resource | ✅ | ✅ | ❌ |
| bett.create / delete | ✅ | ❌ | ❌ |
| bett.update / assign_patient / release | ✅ | ✅ | ❌ |
| Lesezugriff (view) auf alle | ✅ | ✅ | ✅ |

## Key Features
- **Schritt 10 – Einsatzabschnitte**: 10 Farbkodierungen, Kachelansicht mit Ampel, Ressourcen-Zuweisung, Detail-Modal, Inaktiv-Toggle
- **Schritt 11 – UHS-Betten**: Rasteransicht mit Status-Farbcodierung, 5 Bett-Typen (Liegend/Sitzend/Schockraum/Beobachtung/Sonstiges), Schnell-Setup (Bulk), Filter-Chips, Patient-Picker, Auto-Release bei Transport-Abschluss
- **Schritt 12 – Integration**:
  - Ressourcen-Matrix hat Abschnitt-Select pro Zeile + Farbpunkt
  - PatientDetail: neue Bett-Zuweisungs-Sektion
  - Dashboard: 4 neue KPIs (Abschnitte, Bett-Auslastung, Ø Belegungsdauer, Ress. ohne Abschnitt) + card-abschnitte
  - Abschluss-Check: 1 neuer Blocker + 3 neue Warnungen
  - Hybrid-Wizard: nach Incident-Create Redirect auf /abschnitte mit Toast "Abschnitte konfigurieren"
  - Demo-Seed: 2 Abschnitte + 6 Betten (4 belegt)
- Bestehende Features (Dark-Cockpit, Command-Palette, DnD, Konflikte, A4-Print, Rollen, Versionen) unveraendert

## Changelog
- **2026-04-19 (Schritte 10-12)**: Abschnitte + Betten-Modul komplett. Backend: 8 neue Endpunkte, Demo-Seed erweitert, Auswertung/Check/Report integriert, Auto-Release-Logik. Frontend: 2 neue Seiten, Nav-Links, Dashboard-KPIs, PatientDetail-Section, ResourceRow-Erweiterung, Hybrid-Wizard-Redirect. Tests: 15/15 pytest + Frontend-Playwright gruen.
- **2026-04-19 (Schritte 07-09)**: Rollen, Demo, Abschluss-Dashboard mit A4-Bericht.
- Fruehere Sessions: Schritte 01-06 + Backend fuer 08/09.

## Roadmap / Backlog
### P1 – Empfohlen
- **server.py-Refactor**: Split in `routes/` + `models/` + `services/` (aktuell 2162 Zeilen).
- **Aktiven Incident persistieren** (localStorage-Fix nach Reload).
- **DRY-Refactor ResourceList**: intern/extern in gemeinsame ResourceSection-Komponente auslagern.
- **Bulk-Insert**: `insert_many` statt Loop in `create_betten_bulk`.

### P2 – Nice-to-have
- Echter serverseitiger PDF-Export (WeasyPrint).
- Voller Multi-Step-Wizard fuer Incident-Setup (aktuell nur Hybrid-Redirect).
- Mobile-Layout, WebSocket-Push, Auth + Multi-User.
- CSV/JSON-Export der Auswertung, erweiterte Konfliktregeln (Bett-Kapazitaet, Sichtung-Skew).
