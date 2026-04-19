# ELS MHD – Einsatzleitsystem Malteser Hilfsdienst

## Problem Statement (Original)
Entwirf die hochwertigste Tablet-/Desktop-App fuer ein sanitaetsdienstliches Einsatzleitsystem (ELS MHD).
Gliederung in 9 Schritte. **Aktuell: Alle 9 Schritte MVP-komplett.**

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
- Frontend: React 19, React Router 7, Tailwind CSS 3, shadcn/ui + Radix Primitives, Lucide Icons, sonner
- Backend: FastAPI, Motor (MongoDB Async), Pydantic
- Persistenz: MongoDB (Collections: incidents, patients, transports, resources, messages, report_versions)

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
| 08 | Demo-Integration (7 Patienten, 2 Transporte, Meldungen) | ✅ |
| 09 | Auswertungs-Dashboard, Abschluss-Check, A4-Bericht, Versionen, Nachbearbeitung | ✅ |

## Architektur
```
/app/
├── backend/
│   ├── server.py              # FastAPI + MongoDB (1596 Zeilen – Split empfohlen)
│   └── tests/                 # pytest-Suite (21 Tests gruen)
├── frontend/src/
│   ├── App.js                 # RoleProvider → IncidentProvider → AppShell + Routes
│   ├── index.css              # Tokens + .report-a4 + @media print
│   ├── context/
│   │   ├── RoleContext.jsx    # PERMS-Matrix, can(), useRole()
│   │   ├── IncidentContext.jsx
│   │   ├── PatientContext.jsx
│   │   ├── TransportContext.jsx
│   │   └── OpsContext.jsx
│   ├── components/
│   │   ├── shell/             # AppShell, Sidebar, GlobalHeader, RoleSelector
│   │   ├── command/           # CommandPalette (Cmd+K)
│   │   ├── primitives/        # StatusBadge, KpiTile, SectionCard, DataTable, FilterChip, ConfirmModal
│   │   ├── incidents/
│   │   ├── patients/
│   │   ├── transports/
│   │   ├── resources/
│   │   ├── messages/
│   │   └── ui/                # shadcn
│   ├── lib/                   # api.js, patient-meta, transport-meta, ops-meta, time, utils
│   └── pages/
│       ├── IncidentList.jsx
│       ├── LagePlaceholder.jsx
│       ├── PatientList.jsx / PatientDetail.jsx
│       ├── TransportList.jsx
│       ├── ResourceList.jsx
│       ├── MessageList.jsx
│       ├── KonfliktList.jsx
│       └── AbschlussPage.jsx  # NEU in Schritt 09
```

## Wichtige API-Endpunkte
- `GET/POST /api/incidents`, `GET/PATCH/DELETE /api/incidents/{id}`
- `POST /api/incidents/demo` – Seed mit Vordaten (Schritt 08)
- `GET/POST /api/incidents/{id}/patients`, `GET/PATCH/DELETE /api/patients/{id}`
- `GET/POST /api/incidents/{id}/transports`, `GET/PATCH/DELETE /api/transports/{id}`
- `GET/POST /api/incidents/{id}/resources`, `GET/PATCH/DELETE /api/resources/{id}`
- `GET/POST /api/incidents/{id}/messages`, `POST /api/messages/{id}/ack`, `DELETE /api/messages/{id}`
- `GET /api/incidents/{id}/konflikte` – Auto-Detection (Schritt 06)
- `GET /api/incidents/{id}/auswertung` – Bloecke A–F (Schritt 09)
- `GET /api/incidents/{id}/abschluss-check` – Blocker + Warnungen (Schritt 09)
- `GET /api/incidents/{id}/report` – 14 Kapitel (Schritt 09)
- `GET/POST /api/incidents/{id}/report-versions` – Snapshots + Freigabe-Meta (Schritt 09)
- `PATCH /api/incidents/{id}/meta` – besondere_vorkommnisse / nachbearbeitung (Schritt 09)

## Rollen-Berechtigungen (Frontend PERMS)
| Aktion | EL | Helfer | Dokumentar |
|--------|----|---------|------------|
| incident.create / delete / close | ✅ | ❌ | ❌ |
| incident.demo_start | ✅ | ✅ | ✅ |
| patient.create / progress | ✅ | ✅ | ❌ |
| transport.assign / status | ✅ | ✅ | ❌ |
| message.create / ack | ✅ | ✅ | ❌ |
| abschluss.freigabe / version_create | ✅ | ❌ | ❌ |
| abschluss.export_pdf / edit_meta | ✅ | ❌ | ✅ |

## Key Features
- **Dark-Cockpit Theme** mit BOS-Farbcodierung (S1-rot, S2-gelb, S3-gruen, S0-grau)
- **Command-Palette** (Cmd+K/Ctrl+K) mit Navigation, Aktionen, Rollenwechsel, Incident-Switch
- **Ein-Klick-Progression** fuer Patienten (Sichtung → Behandlung → Transport → Abschluss)
- **Drag & Drop** bei Transporten
- **Konflikt-Auto-Detection** (z.B. gleichzeitig zugewiesene Ressource)
- **Demo-Seed** erzeugt realistischen Incident mit 7 Patienten, 2 Transporten, 3 Meldungen
- **A4-Bericht-Vorschau** mit `@media print` fuer PDF-Export ueber Browser-Druckdialog
- **Rollen-basierte UI-Sichtbarkeiten** via `can(action)`
- **Report-Versionierung** mit freigabe_von/freigabe_at-Meta

## Changelog (komprimiert)
- 2026-04-19: **Schritt 07/08/09 Frontend komplett**: RoleProvider in App.js, RoleSelectorDialog im AppShell, Header-Role-Badge, AbschlussPage mit 5 Tabs (Dashboard/Check/Bericht/Versionen/Meta), A4-Print-CSS, Role-Gates auf IncidentList und AbschlussPage, CommandPalette-Eintrag "Rolle wechseln". Backend: Report-Version setzt Freigabe-Meta. 21/21 Backend-Tests gruen.
- Fruehere Sessions: Schritte 01–06 + Backend fuer 08/09 (Demo-Seed, Auswertung, Report, AbschlussCheck, Versionen, Meta).

## Roadmap / Backlog
### P1 – Empfohlen
- **Persistenz aktiver Incident**: localStorage-Key `els-active-incident` bei `closeIncident` nicht loeschen (nur, wenn Incident geloescht). UX-Verbesserung nach Seitenreload.
- **server.py-Refactor**: Split in `/app/backend/routes/` (incidents, patients, transports, resources, messages, report) + `/app/backend/models/` + `/app/backend/services/`.
- **PatchMeta Validation**: `Field(max_length=...)` auf `besondere_vorkommnisse` und `nachbearbeitung`.

### P2 – Nice-to-have
- Echter serverseitiger PDF-Export (z.B. WeasyPrint) als Alternative zum Browser-Druck.
- Sidebar-Link "Auswertung" auch ohne aktiven Incident erlauben (Uebersicht aller Incidents).
- Mobile/Smartphone-Layout.
- Authentifizierung + Multi-User-Rollen (derzeit rein client-seitig).
- WebSocket-Push fuer Live-Updates mehrerer Geraete am gleichen Incident.
- Export als CSV/JSON der Auswertung.
