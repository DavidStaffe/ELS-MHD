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
│   ├── server.py                  # 70 Zeilen Bootstrap: FastAPI + CORS + Router-Include + Migrations
│   ├── models.py                  # Alle Pydantic-Models (~270 Zeilen)
│   ├── core/
│   │   ├── db.py                  # MongoDB Client + db-Handle
│   │   ├── time.py                # now_utc, iso, parse_iso, _duration_ms, _avg_minutes
│   │   └── types.py               # Literal-Typen (SichtungStufe, IncidentStatus, BettTyp, ...)
│   ├── routes/
│   │   ├── incidents.py           # CRUD + Demo-Trigger + Meta-Patch
│   │   ├── patients.py            # CRUD + Auto-Progression + Bett-Auto-Release
│   │   ├── transports.py          # CRUD + Ressource-Status-Sync + Bett-Auto-Release
│   │   ├── resources.py           # CRUD + Abschnitt-Zuweisung
│   │   ├── messages.py            # CRUD + /ack
│   │   ├── abschnitte.py          # CRUD (409 bei aktivem Incident)
│   │   ├── betten.py              # CRUD + Bulk + Assign/Release
│   │   └── analytics.py           # konflikte/auswertung/abschluss-check/report/versions
│   ├── services/
│   │   ├── seeds.py               # Default-Ressourcen, Kennung-Counter, Transport-Ensure, Bett-Release-Helper
│   │   ├── demo.py                # Demo-Incident-Seeder (2 Abschnitte + 6 Betten + 7 Patienten + 3 Meldungen)
│   │   └── analytics.py           # detect_konflikte, get_auswertung, get_abschluss_check, get_report
│   └── tests/                     # pytest-Suite (130/135 gruen; 5 pre-existing Versions-Asserts)
├── frontend/src/                  # unveraendert (siehe oben)
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
- **2026-04-19 (Backend-Refactor + DB-Cleanup)**: server.py von 2162 -> 70 Zeilen (Bootstrap only). Neue Struktur: `core/` (db/time/types), `models.py`, `routes/` (8 Domain-Router), `services/` (seeds/demo/analytics). API + Verhalten identisch. pytest: 130/135 gruen (5 Fails pre-existing Versions-Asserts). Frontend-Regression: 100% (alle 9 Routen + PatientDetail fehlerfrei). Alle Nicht-Demo-Incidents geloescht, nur 1 frischer Demo-Incident in DB.
- **2026-04-19 (Schritte 10-12)**: Abschnitte + Betten-Modul komplett. Backend: 8 neue Endpunkte, Demo-Seed erweitert, Auswertung/Check/Report integriert, Auto-Release-Logik. Frontend: 2 neue Seiten, Nav-Links, Dashboard-KPIs, PatientDetail-Section, ResourceRow-Erweiterung, Hybrid-Wizard-Redirect. Tests: 15/15 pytest + Frontend-Playwright gruen.
- **2026-04-19 (Schritte 07-09)**: Rollen, Demo, Abschluss-Dashboard mit A4-Bericht.
- Fruehere Sessions: Schritte 01-06 + Backend fuer 08/09.

## Roadmap / Backlog
### P1 – Empfohlen
- **Aktiven Incident persistieren** (localStorage-Fix nach Reload).
- **5 alte Versions-Asserts in pytest-Tests auf "1.0.0" umstellen** oder auf `meta['version'] is not None`.
- **DRY-Refactor ResourceList**: intern/extern in gemeinsame ResourceSection-Komponente auslagern.
- **Serverseitiger PDF-Export** (WeasyPrint) auf Basis der neuen `services/analytics.get_report()`-Funktion – jetzt sauber testbar dank Refactor.

### P2 – Nice-to-have
- Voller Multi-Step-Wizard fuer Incident-Setup (aktuell nur Hybrid-Redirect).
- Mobile-Layout, WebSocket-Push, Auth + Multi-User.
- CSV/JSON-Export der Auswertung, erweiterte Konfliktregeln (Bett-Kapazitaet, Sichtung-Skew).
- conftest.py in `/app/backend/tests/` mit `load_dotenv('/app/frontend/.env')` fuer bessere pytest-Ergonomie.
