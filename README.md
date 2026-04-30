# ELS MHD

ELS MHD ist ein Einsatzleitsystem fuer sanitaetsdienstliche Lagen bei Veranstaltungen.
Lauffähig auf Raspberry Pi 5
Die Anwendung bildet den operativen Einsatzablauf ab:

- Incident-Steuerung
- Patientenmanagement
- Transporte
- Ressourcen
- Kommunikation/Funktagebuch
- Konflikt-Erkennung
- Einsatzabschnitte
- UHS/Behandlungsbetten
- Abschlussauswertung und Report-Versionen

## Architektur

- Backend: FastAPI + Motor (MongoDB, async)
- Frontend: React 19 + React Router 7 + Tailwind + Radix/shadcn
- API-Basis: /api

Projektstruktur (vereinfacht):

- backend/
  - server.py (FastAPI Bootstrap, Router, Startup-Migrationen)
  - core/ (DB, Zeit-Utilities, Types)
  - routes/ (Domain-Endpunkte)
  - services/ (Business-Logik)
  - tests/ (pytest)
- frontend/
  - src/App.js (Routing + Provider)
  - src/lib/api.js (HTTP Client und Endpunkt-Funktionen)

## Projektanalyse (Kurzfassung)

Stand: 2026-04-25

Starke Punkte:

- Klare modulare Trennung im Backend (core/routes/services/models)
- Umfangreiche fachliche Abdeckung ueber den gesamten Einsatz-Lifecycle
- Gute Konsistenz zwischen Frontend-Routen und Backend-API-Domaenen
- Umfangreiche Backend-Testsuite

Wichtigste Risiken:

- Dokumentation war teilweise veraltet/generisch
- Potenzieller Versions-Drift zwischen API-Version und alten Tests
- Frontend benoetigt REACT_APP_BACKEND_URL ohne Fallback

Details siehe project-overview.md.

## Voraussetzungen

- Python 3.10+
- Node.js 18+ (empfohlen) und npm
- MongoDB (lokal oder remote)

## Umgebungsvariablen

Backend (Datei: backend/.env):

MONGO_URL=mongodb://localhost:27017
DB_NAME=els_mhd
CORS_ORIGINS=http://localhost:3000

Frontend (Datei: frontend/.env):

REACT_APP_BACKEND_URL=http://localhost:8000

## Lokaler Start

### 1) Backend starten

In backend/:

python3 -m venv .venv

# Hinweis (macOS/Homebrew): falls noetig explizit python3.14 verwenden.

# Beispiel: python3.14 -m venv .venv

source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --reload --host 0.0.0.0 --port 8000

Backend pruefen:

- http://localhost:8000/api/meta

### 2) Frontend starten

In frontend/:

npm install
npm start

Frontend:

- http://localhost:3000

### 3) Backend + Frontend zusammen starten (Node.js)

Im Projekt-Root:

npm run dev

Hinweise:

- Der Script-Launcher startet Backend (uvicorn) und Frontend parallel.
- Wenn vorhanden, wird backend/.venv/bin/python verwendet, sonst python3.
- REACT_APP_BACKEND_URL wird automatisch auf http://localhost:8000 gesetzt, falls nicht vorhanden.

## Tests

Backend-Tests (in backend/):

pytest -q

Frontend-Tests (in frontend/):

npm test

## Build

Frontend Production Build (in frontend/):

npm run build

## Troubleshooting (Quick)

### Backend startet nicht (ImportError oder Modul nicht gefunden)

Symptom:

- Fehler wie No module named fastapi oder No module named motor.

Fix:

- In backend/ wechseln.
- Virtual Environment aktivieren.
- Abhaengigkeiten neu installieren: pip install -r requirements.txt

### KeyError: MONGO_URL oder DB_NAME

Symptom:

- Backend bricht beim Start mit KeyError auf Umgebungsvariablen ab.

Fix:

- Datei backend/.env anlegen/pruefen.
- Mindestens setzen:
  - MONGO_URL=mongodb://localhost:27017
  - DB_NAME=els_mhd
- Danach Backend neu starten.

### Verbindung zu MongoDB fehlgeschlagen

Symptom:

- Timeout/Connection refused beim API-Zugriff.

Fix:

- Pruefen, ob MongoDB lokal laeuft (oder ob die Remote-URL korrekt ist).
- MONGO_URL in backend/.env verifizieren.
- Bei lokalem Setup: Dienst starten und dann Backend neu starten.

### Frontend zeigt keine Daten / API Requests schlagen fehl

Symptom:

- Leere Listen oder Netzwerkfehler im Browser.

Fix:

- Datei frontend/.env pruefen:
  - REACT_APP_BACKEND_URL=http://localhost:8000
- Backend muss erreichbar sein: http://localhost:8000/api/meta
- Frontend nach .env-Aenderung neu starten.

### CORS Fehler im Browser

Symptom:

- Browser meldet CORS blocked request.

Fix:

- In backend/.env CORS_ORIGINS korrekt setzen, z. B.:
  - CORS_ORIGINS=http://localhost:3000
- Backend neu starten.

### npm install oder npm start fehlschlaegt im Frontend

Symptom:

- Abhaengigkeiten lassen sich nicht aufloesen oder Start bricht ab.

Fix:

- Node-Version pruefen (empfohlen: 18+).
- In frontend/ erneut ausfuehren:
  - npm install
  - npm start
- Bei hartnaeckigen Problemen node_modules entfernen und erneut installieren.

### Port bereits belegt (3000 oder 8000)

Symptom:

- Start meldet Address already in use.

Fix:

- Anderen Prozess auf dem Port beenden oder einen anderen Port waehlen.
- Bei Portwechsel im Backend auch REACT_APP_BACKEND_URL im Frontend anpassen.

## API-Bereiche (Auszug)

- incidents
- patients
- transports
- resources
- messages/funktagebuch
- abschnitte
- betten
- analytics (auswertung, report, abschluss-check)

## Hinweise

- Beim Backend-Start laufen idempotente Migrationen in server.py.
- Wenn das Frontend keine Daten laedt, zuerst REACT_APP_BACKEND_URL pruefen.
- Eine ausfuehrliche technische Analyse ist in project-overview.md dokumentiert.
