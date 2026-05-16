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
- **2026-05-16 (Echtzeit-SSE-FMS + Auto-Live-Position + Sidebar-Alarm-Panel)**: User-Wunsch 'Sprechwuensche in Echtzeit + Sidebar groesser, Standorte automatisch auf Karte updaten' komplett umgesetzt. Backend: (1) `services/fms_audit.py.record_fms_change()` publisht jetzt nach jedem Event `publish_incident_event({kind:'fms_event', action:'created', is_alert, event:doc})` → SSE-Push in <1s (gemessen 0.53s end-to-end). (2) `services/divera.py.sync_incident()` ueberschreibt lat/lng **immer** wenn Resource an Divera verknuepft und Divera-Vehicle Position liefert (vorher: nur einmalig). Plausibilitaetscheck `abs(lat)>0.01 || abs(lng)>0.01` filtert 0/0-no-fix Eintraege raus. Frontend: (3) Neuer Hook `useFmsAlerts` (components/fms/useFmsAlerts.js) konsolidiert Polling 10s + SSE-Listener auf /incidents/stream + Beep + Quittierung. Zentral nutzbar von mehreren Komponenten. (4) `FmsAlertCenter` (Header-Glocke) auf den Hook umgestellt — slim, ~180 LOC. (5) Neue Komponente `FmsAlertSidebarPanel`: prominentes ROTES pulsierendes Panel ganz oben in der KartePage-Sidebar (`data-testid='fms-alert-sidebar-panel'`). Erscheint NUR bei offenen Sprechwuenschen. Pro Alarm: grosser farbiger FMS-Kreis (h-9 w-9), Fahrzeugname, Zeit, prominenter Quittieren-Button. Sound-Toggle integriert. (6) `OpsContext` bekommt eigenen SSE-Listener: bei `kind='resource'` (Divera-Sync) oder `kind='fms_event'` fuer aktiven Incident → debounced `refreshResources()` (250ms) → Map-Pin-Positionen updaten automatisch ohne Reload. Header-Glocke und Sidebar-Panel teilen sich State (Quittierung in einem entfernt aus beiden gleichzeitig). Testing: 4/4 neue pytest (test_realtime_sse_fms.py) + 6/6 Frontend (iteration_20), keine Regressionen, SSE-Latenz 0.5s gemessen.
- **2026-05-16 (Divera-Verknuepfung auf /ressourcen)**: Bisher war die Verknuepfung von ELS-Ressourcen mit Divera-Fahrzeugen nur auf der KartePage moeglich – fuer User unauffindbar. `ResourceList.jsx` erweitert: (1) Neue `DiveraInlineSelect`-Komponente direkt in der `ResourceRow` zwischen Name und Abschnitt-Select (`data-testid='resource-divera-select-<id>'`). Zeigt RadioTower-Icon + Fahrzeugname + FMS-Code (farbig) wenn verknuepft, italic 'Divera' sonst. Dropdown listet alle verfuegbaren Divera-Fahrzeuge mit FMS-Anzeige + Option 'nicht verknuepft'. (2) `ResourceDialog` (Anlegen/Bearbeiten) hat neue Sektion 'Divera-Fahrzeug verknuepfen' (`data-testid='resource-divera-dialog'`) mit Live-Hinweis (FMS aktuell). (3) Status-Select wird automatisch disabled wenn Resource an Divera verknuepft ist (Tooltip 'Status wird vom Divera-Polling gesteuert'). (4) Zwei amber Konfigurations-Banner: `divera-not-configured` bei fehlendem API-Key, `divera-no-vehicles` bei leerer Fahrzeugliste. (5) Fahrzeugliste wird alle 30s neu geladen (Live-FMS). UX-Polish: Selects auf w-32/w-24 reduziert, redundanter Status-Badge entfernt, damit Resource-Name nicht abschneidet. Backend unveraendert (PATCH /api/resources/{id} mit divera_id ist seit Phase 3 implementiert). Testing: 9/9 Spec-Szenarien gruen via testing_agent (iteration_19). Keine Regressionen.
- **2026-05-16 (FMS-Sprechwunsch-Alarm + Quittierung + Incident-Edit-Dialog)**: 3 Features in einer Iteration: (1) `EditIncidentDialog` finalisiert in `IncidentList.jsx` eingebunden – Pencil-Button auf jeder IncidentCard oeffnet Vollbearbeitung von Name/Typ/Ort/Adresse/MapPicker/Beschreibung inkl. Lat/Lng/Zoom (Permission `incident.update` = EL + FA). (2) Backend FMS-Quittierung: `services/fms_audit.py.acknowledge_fms_event()` + `ALERT_FMS_CODES={0,5}` + neue Felder `is_alert`/`acknowledged_by_role`/`acknowledged_at` auf jedem fms_event. Neuer Endpoint `POST /api/fms-events/{event_id}/acknowledge` (Body `{role}`) — nur EL/FA erlaubt (403 sonst), 404 wenn unbekannt, 409 bei Doppelquittierung oder Nicht-Alert-Event. SSE-Event `fms_event_acknowledged` wird published. (3) Frontend `FmsAlertCenter` (Glocke im GlobalHeader): polled 10s, filtert unquittierte to_fms in {0,5}, roter pulsierender Bell + Badge (Anzahl). Popover-Liste zeigt Fahrzeug + FMS + Zeit + Quittieren-Button (disabled fuer Nicht-EL/FA mit Warnbanner). Web-Audio-API generiert 2-Ton-Beep, Wiederholung alle 5s solange Alarme offen. Sound-Toggle persistiert in localStorage. Erstes Laden markiert vorhandene Alerts als gesehen (kein Spam-Beep beim Refresh). Bei archiviertem Incident oder ohne aktiven Incident: Glocke unsichtbar. `FmsHistory.jsx` zeigt unter quittierten Alerts „quittiert von [EL/FA] um HH:MM:SS". Permission `fms.acknowledge` ergaenzt in `RoleContext.jsx`. Pulsanimation `@keyframes fms-bell-pulse` in `index.css`. Testing: 7/7 neue pytest + 8/8 FMS-Audit-Regression = 15/15 gruen, 100% Frontend (iteration_18). Keine Regressionen.
- **2026-05-16 (FMS-Audit-Trail – Fahrzeug-Verlauf)**: Neue MongoDB-Collection `fms_events` mit Audit-Eintraegen bei jeder FMS-Aenderung (Divera-Sync ODER manueller PATCH). Service `services/fms_audit.py` mit `record_fms_change()` (skip wenn from==to, auch beide None). `services/divera.py.sync_incident()` schreibt Events mit `source='divera'` inkl. `vehicle_name` und `divera_id`. `routes/resources.py.PATCH` liest 'before'-State und schreibt `source='manual'` Events (skip wenn Resource an Divera verknuepft — Doppel-Logging-Vermeidung). Neue Route `GET /api/incidents/{id}/fms-events` mit `resource_id`-Filter und `limit` (1-1000, default 200). Response sortiert ts DESC. Frontend: neue `FmsHistory.jsx` mit Refresh-Button, Source-Icons (RadioTower/Hand), Color-coded FMS-Zahlen, Dauer-Berechnung pro Resource zwischen aufeinanderfolgenden Events. Eingebettet (a) in der KartePage-Sidebar als Full-Incident-View (limit 20) zwischen DiveraPanel und Abschnitte, (b) im `EditResourceDialog` als per-Resource Verlauf (showResourceName=false, compact). Testing: 8/8 neue pytest + 11/11 Phase-3-Regression + 199/206 voller Backend-Suite (iteration_17). Keine Bugs, keine Regressionen.
- **2026-05-15 (Lagekarte Phase 3 – Divera 24/7 Integration)**: Live-FMS-Polling von Divera 24/7. Backend: `services/divera.py` mit `fetch_vehicles()`, `sync_incident()` (Matching via `Resource.divera_id` → `Vehicle.id`, automatisches FMS→Status-Mapping nach BOS), `start_polling()` / `stop_polling()` als asyncio Background-Tasks pro Incident. Polling-Interval 30s konfigurierbar via `DIVERA_POLL_INTERVAL_SECONDS`. `routes/divera.py` mit 6 Endpoints: GET `/divera/configured`, GET `/divera/vehicles`, GET/POST `/incidents/{id}/divera/{status|start|stop|sync}`. Auto-Resume nach Backend-Restart fuer Incidents mit `divera_enabled=true`. Polling stoppt automatisch wenn Incident archiviert wird. `Incident` Model erweitert um `divera_enabled`, `divera_last_poll_at`, `divera_last_poll_status`, `divera_last_match_count`. Frontend: neue `DiveraPanel.jsx` mit Toggle (Start/Stop), Sync-Now-Button, Status-Badge (ok/Fehler), Last-Poll-Timestamp; eingebettet oben in der KartePage-Sidebar. `EditResourceDialog` erweitert: Divera-Vehicle-Dropdown (statt freiem Text-Input) listet alle 5 verfuegbaren Fahrzeuge; bei aktiver Verknuepfung wird der manuelle FMS-Select deaktiviert (Polling ueberschreibt). Resource-Pins auf der Karte zeigen automatisch die FMS-Farbe nach Sync. **Bug-Fix durch testing-agent**: `publish_incident_event`-Aufruf in `services/divera.py` hatte falsche Signatur und brach jeden Sync mit 500 — gefixt auf Dict-Payload. Testing: 11/11 neue pytest-Tests + 100% Frontend-Flows (iteration_16). Backend-Regression 182/189 (7 vorgelagerte Fails unveraendert).
- **2026-05-15 (Lagekarte Phase 2 – Abschnitts-Polygone)**: Polygone fuer Einsatzabschnitte zeichnen, editieren und entfernen. Backend: `Abschnitt.polygon: List[List[float]] | None` (Liste von [lat,lng]-Paaren). PATCH-Route nutzt `exclude_unset=True` damit `polygon=null` das Polygon clearen kann. Frontend: `@geoman-io/leaflet-geoman-free` fuer Vertex-Editing eingebunden. `IncidentMap.jsx` rendert `<Polygon>` mit Abschnitts-Farbe (15-25% fill, full stroke), permanenter Tooltip mit Abschnitts-Namen. Inaktive Abschnitte gedimmt + dashed. Neue Komponenten in `IncidentMap`: `GeomanController` (Draw-Mode), `EditablePolygon` (Vertex-Drag). `KartePage` bekommt Abschnitte-Sidebar mit „Zeichnen"-/„Editieren"-Buttons, `AbschnittPickerDialog` (neuer/bestehender Abschnitt + 10-Farb-Palette) und `EditAbschnittDialog` (Name/Farbe/aktiv + Neu zeichnen + Polygon entfernen). 3 Modi (place/draw/edit) sind mutually exclusive. LagePage-Mini-Map zeigt Polygone read-only mit. `abschnitt-meta.js` um `hex` ergaenzt fuer direkte Map-Verwendung. Testing: 7/7 neue pytest + 21/21 Frontend-Selektoren (iteration_15).
- **2026-05-15 (Lagekarte Phase 1 – OSM)**: Komplettes Map-Feature auf Basis von `react-leaflet` + OSM-Tiles + Nominatim-Geocoding. Backend: `Incident.ort_lat/ort_lng/ort_zoom` und `Resource.lat/lng/divera_id/fms_status` als optionale Felder, validiert via Pydantic-`ge/le`. PATCH-Routen nutzen `exclude_unset=True` damit explizite `null`-Werte Felder clearen koennen. Frontend: neue Komponenten `components/map/IncidentMap.jsx` (Karten-Container mit Marker, Drag, Klick) und `components/map/MapPicker.jsx` (Dialog-Embed mit Nominatim-Suche, Reverse-Geocoding). Neue Seite `/karte` mit fullscreen-Map, KPI-Strip, Sidebar (unplatzierte Ressourcen + FMS-Legende), Place-Mode und Edit-Resource-Dialog (FMS-Status-Auswahl + Divera-ID). `LagePage` zeigt eingebettete Mini-Karte. `NewIncidentDialog` hat MapPicker unter dem Adressfeld. Sidebar bekam Eintrag „Karte". FMS-Mapping (`lib/fms-status.js`): BOS 0–9 mit korrekten dt. Labels und Farben. Testing: 17/17 neue pytest-Tests + 100% Frontend-Flows (iteration_14).
- **2026-05-15 (Sync von github.com/DavidStaffe/ELS-MHD)**: Wholesale-Sync der lokal weiterentwickelten Repository-Version. Hauptaenderungen:
  - **Realtime / SSE**: neuer Service `backend/services/realtime.py` (In-Memory Pub/Sub), zwei neue SSE-Endpoints `GET /api/incidents/stream` und `GET /api/incidents/{id}/patients/stream`. Frontend-Contexte (`IncidentContext`, `PatientContext`) verbinden sich per `EventSource` mit Auto-Reconnect (2s) und debounced refresh (300ms). Mutationen publishen `created/updated/deleted/reopened` Events fuer Cross-Client-Sync.
  - **Status-Lebenszyklus "geplant" → "operativ"**: Incidents koennen als `geplant` angelegt werden (Checkbox im `NewIncidentDialog`). Patienten- und Transport-POSTs liefern 409 wenn Incident `geplant` ist. Beim Wechsel auf `operativ` wird `start_at` automatisch gesetzt. `IncidentList` hat neuen Filter "Geplant", `Sidebar` deaktiviert Patienten/Transport-Module im geplant-Status.
  - **Patient-Behandlungsressource**: neue Felder `behandlung_ressource_id`, `behandlung_ressource_name` + Audit-Trails `behandlung_ressource_events` und `sichtung_events` (jeweils List[dict] mit ts/from/to/action). `PatientDetail` hat ein Select fuer die Behandlungsressource, `PatientTimeline` rendert Sichtungs- und Ressourcenwechsel-Historie chronologisch.
  - **Transport-Auto-Sync**: `ensure_transport_for_patient` synchronisiert aktive Transporte bei Patient-Aenderungen (Kennung/Sichtung/Typ/Ziel) und gibt Ressourcen via `release_resource_if_unused` frei.
  - **UI/Branding**: Custom SVG-Favicon, `<html lang="de">`, Theme-Color `#0f3638`, Title "ELS MHD – Einsatzleitsystem". `@emergentbase/visual-edits` aus package.json/craco entfernt, `ajv` als neue Dep.
  - **Code-Style**: Komplettes Repository ist Prettier-formatiert (2-space, single quotes, trailing commas).
  - Pytest: 156/163 gruen. 7 fails sind pre-existing (5x Version-Hardcodes, 2x S4-Sichtung + Behandlungsressourcen-Timeline-Test) und stammen aus dem upstream-Repo.
- **2026-04-19 (Radstreife→EVT + App-weite Loesch-Persistenz)**: Ressourcen-Kategorie `bike` / "Radstreife" umbenannt in `evt` / "EVT" (Backend Literal, Default-Seed "EVT 1", Frontend-Label + Icon `Users`). Startup-Migration in `server.py` migriert vorhandene `kategorie=bike` und Namen `Radstreife N` → `EVT N`. **Bugfix**: `list_resources` ruft nicht mehr `seed_default_resources` auf → geloeschte Ressourcen bleiben geloescht (auch wenn alle geloescht wurden). `transport-meta.js` hartkodierter `RESOURCE_POOL` entfernt; `ResourceBar.jsx` und `TransportDialogs.jsx` (Assign + NewTransport) lesen jetzt live aus `useOps().resources` → Loeschungen in `/ressourcen` wirken app-weit. Testing: 4/4 neue pytest-Regression-Tests + 100% Frontend (iteration_12).
- **2026-04-19 (Archiv + Lage-Dashboard + Geschuetztes Loeschen)**: Abgeschlossene Incidents werden aus `/` ausgeblendet und in neuer Seite `/archiv` lesend gefuehrt. Dashboard (KPIs + SectionCards) aus "Auswertung" in `/lage` verschoben (schnelle Lage-Uebersicht). Neue `DeleteArchivModal` mit verpflichtender Texteingabe `LÖSCHEN`; Loeschen nur fuer Rolle `einsatzleiter`. Sidebar sperrt operative Module (Patienten, Transport, Ressourcen, Abschnitte, Betten, Funk, Konflikte) fuer archivierte Incidents; `Lage` + `Auswertung` bleiben lesend. `AbschlussPage`: Dashboard-Tab entfernt; fuer Archiv nur Berichtsvorschau + Versionen sichtbar. Testing: 100% Frontend, 139/144 Backend-pytest (5 unveraenderte Versions-Asserts). Neue Dateien: `components/lage/Dashboard.jsx`, `components/incidents/DeleteArchivModal.jsx`, `pages/ArchivPage.jsx`, `pages/LagePage.jsx`.
- **2026-04-19 (Schritt 13 – Funktagebuch + Ressourcen-CRUD)**: Module Kommunikation zu **Funktagebuch** erweitert. Backend: 7 Funk-Typen (funk_ein/funk_aus/lage/auftrag/rueckmeldung/vorkommnis/system), Confirm/Finalize-Endpoints, unveraenderliche System-Eintraege, Auto-Logs bei Patient-Create/Fallabschluss/Transport-Status. PATCH/DELETE gesperrt fuer system+finalisierte Eintraege (409). Frontend: neue Seite mit KPIs, 4 Filter-Achsen (Typ/Prio/Quelle/Abschnitt), Volltextsuche, Detail-Dialog, @media print. Ressourcen: CRUD-UI (Create/Edit/Delete) mit Dialog. 2 neue Rollen (fuehrungsassistenz, abschnittleitung). Testing: 9/9 neue pytest-Tests gruen, 100% Frontend.
- **2026-04-19 (Backend-Refactor + DB-Cleanup)**: server.py 2162 -> 70 Zeilen. Neue Struktur: core/, models.py, routes/ (8 Domain-Router), services/.
- **2026-04-19 (Schritte 10-12)**: Abschnitte + Betten-Modul.
- **2026-04-19 (Schritte 07-09)**: Rollen, Demo, Abschluss-Dashboard.
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
