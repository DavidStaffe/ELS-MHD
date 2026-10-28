# Lokale Validierung am 28. Oktober 2026

* Backend: 82 Tests bestanden in den sechs unten genannten isolierten
  Vertragssuiten. Danach ergänzte Prüfung der Abschnittstransporte und
  Wiederholung von Größenlimit/Demo: drei gezielte Tests bestanden.
* Frontend: acht Tests in drei Suiten bestanden; Produktionsbuild mit
  `CI=true` erfolgreich. Die vorhandenen Deprecation-Warnungen sind keine
  Aussage über fachliche oder betriebliche Freigabe.
* Python-Syntaxprüfung erfolgreich. Neue Sicherheitsmodule auf undefinierte
  Namen geprüft. Git-Whitespaceprüfung erfolgreich.
* Beide Baselines erneut abgerufen: PR #6 und Docker-Branch sind weiterhin
  Vorfahren des Integrationsbranches. Die bestehende PR ist offen und Draft.
* Abhängigkeitsscans und deren verbleibende Befunde:
  [Sicherheitsreview](review.md).

Backend, mit `PYTHONPATH=backend`:

```text
python -m pytest backend/tests/test_identity_access.py backend/tests/test_divera_global_settings.py backend/tests/test_system_updates.py backend/tests/test_dispatch_geometry_unit.py backend/tests/test_update_bootstrap.py backend/tests/test_update_agent.py -q
python -m compileall -q backend
```

Frontend, im Verzeichnis `frontend`, mit `CI=true`:

```text
npm run build
npm test -- --watch=false --runInBand --testPathPattern='(RoleContext|SystemUpdatesPage|EinstellungenPage).test'
```

Die neuen API-Tests verwenden die tatsächliche FastAPI-App mit isolierter
Mongo-kompatibler Testdatenbank. Die alten netzwerkabhängigen API-Suiten gegen
einen laufenden Server werden nicht als ausgeführt behauptet. Docker/ARM64,
echtes MongoDB, Zertifikatsvertrauen, reale Browserexporte und Pi-Neustart-
Randfälle sind weiterhin Gegenstand der separat dokumentierten Betriebsabnahme.
