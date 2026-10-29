# Incident-Lifecycle: Release-Abnahme und Pi-Update

## Bestand und fokussierter Umfang

Auf main (44695ee) sind Abschluss/Wiedereröffnung bereits in
`backend/routes/governance.py`, `core/identity.py`, `core/access.py` und dem
LifecycleDialog implementiert. Es gibt bereits Begründungspflicht, explizite
Bestätigung offener Vorgänge, Abschluss-Snapshot, atomare Incident-Historie,
Berechtigungsprüfung, Eignungsprüfung und ausschließlich EL-Wiedereinsetzung.
Diese Logik wird nicht doppelt implementiert.

Die nächste fehlende Funktion innerhalb dieser Anforderungen ist die konsistente
Bedienbarkeit an mehreren Arbeitsplätzen: Lifecycle-Änderungen veröffentlichten
keine Incident-Benachrichtigung. Dadurch blieben Listen und Rollenanzeigen bis
zum nächsten Refresh veraltet. Der vorhandene SSE-Kanal erhält jetzt nach einem
erfolgreichen Abschluss oder einer Wiedereröffnung eine Benachrichtigung; der
Browser lädt die Liste mit seinen aktuellen Berechtigungen erneut. Auf dem
öffentlichen Stream bleibt ausschließlich die bestehende anonyme Invalidierung.
Es werden keine Gründe, Patienteninformationen oder Rollen-Snapshots übertragen.

Zusätzlich steuert die API die Abschluss-/Wiedereröffnungsschaltflächen. Ein
explizit global Abschlussberechtigter erhält `can_close` auch in der reduzierten
Incident-Liste, ohne damit ein Leserecht auf Einsatzinhalte zu erhalten. Andere
Benutzer erhalten keine nutzlose Abschlussaktion; die API bleibt maßgeblich.
Ein noch verspätet eintreffendes Prüfergebnis eines anderen Dialogs kann den
aktuellen Abschluss nicht freischalten. Die Begründung ist auf 2000 Zeichen
begrenzt, passend zur bestehenden API.

## Akzeptanzkriterien

- Aktuelle EL oder explizites `incidents.close` darf abschließen. Adminstatus
  allein verleiht keine operative Berechtigung.
- Bei offenen Patienten, Transporten, Ressourcenbindungen oder Dispositionen
  erscheint die Warnung. Ohne ausdrückliche Bestätigung bleibt Abschluss
  gesperrt; ohne nichtleere Begründung verwirft die API die Anfrage.
- Nur die persönlich abschließende ehemalige EL oder `incidents.reopen` darf
  wiedereröffnen. Globaler Abschluss gibt der früheren EL kein Wiederöffnungsrecht.
- Frühere EL wird nur aktiv und weiterhin EL-geeignet wieder eingesetzt. Andernfalls
  bleibt der Incident geschlossen, bis ein zusätzlich zur Ernennung Berechtigter
  eine geeignete Ersatz-EL angibt. Andere Rollen bleiben inaktiv.
- Patienten-, Ressourcen- und Transportdokumente sind vor/nach beiden Aktionen
  unverändert. Beginn bleibt erhalten; Wiedereröffnung entfernt das Incident-Ende.
- Abschluss und Wiedereröffnung stehen mit Zeitpunkt, Akteur, Grund und Änderung
  atomar in `security_history`. Fehlgeschlagene Aktionen erzeugen kein
  erfolgreiches Lifecycle-Ereignis.
- Ein zweiter angemeldeter Arbeitsplatz aktualisiert nach Abschluss und
  Wiedereröffnung seine Liste; unberechtigte Inhalte werden nicht freigegeben.
- Alte Dialogantworten dürfen einen anderen Incident nicht zur Bestätigung freigeben.

## Validierung

Backend aus `backend/` mit der Projektumgebung:

```text
python -m pytest tests/test_identity_access.py -q
python -m pytest tests/test_identity_install.py tests/test_update_agent.py tests/test_update_bootstrap.py tests/test_system_updates.py tests/test_divera_global_settings.py tests/test_dispatch_geometry_unit.py tests/test_certificate_onboarding.py -q
```

Frontend aus `frontend/`:

```text
npm test -- --watchAll=false --runInBand
npm run build
```

Die neuen Frontendtests sind in der bestehenden Update-CI eingeschlossen. Die
bestehende Installations-CI baut ARM64-Images und prüft die isolierte Installation.
Lokale ASGI-Tests verwenden ausschließlich eine isolierte Mongo-kompatible
Testdatenbank; ein realer Pi-/Docker-Test wird dadurch nicht ersetzt.

## Kompatibilität und Freigabe

Keine Datenmigration, keine neuen Abhängigkeiten, keine Änderung am Schema-2-Agent,
an der persistenten Runtime-Compose oder an Volumes/CA-Onboarding. `can_close`
ist ein additives Antwortfeld. Alte Clients können weiterhin dieselben Endpunkte
verwenden. Das bisherige main ist das vorgesehene Image-Rollbackziel und kennt
alle gespeicherten Lifecycle-Felder bereits.

Kein Release wird durch diesen PR veröffentlicht oder produktiv installiert.
Nach Merge nur Images des geprüften Commits für linux/arm64 bauen; API/Web-Digests,
CI-Ergebnisse und Releasekennung festhalten. Schema-2-Freigabe gemäß
[Updateverwaltung](web-update-management.md) und dem [manuellen Releaseprozess](manual-release.md)
vorbereiten. Keine Platzhalter-Digests freigeben. Vorhandene Sicherheitsblocker aus
[Security Review](security/review.md) bleiben separate Freigabebedingungen.

## Gemeinsamer Update-/Rollbacktest am Raspberry Pi 5

1. Wartungsfenster ohne aktiven realen Einsatz wählen, zuerst mit synthetischen
   Daten auf separater Testinstallation. Exakten Ausgangscommit, API/Web-Digests,
   Agentversion, geprüften Schema-2-Release und verfügbares Offline-Rollbackziel
   dokumentieren. Keine Zugangsdaten oder Patientendaten in Protokolle übernehmen.
2. Vorhandene Sicherung und Wiederherstellbarkeit prüfen. Rootgeschützte
   Runtime-Compose, Konfiguration und Identitätsmaterial gesichert halten.
   MongoDB-, Identitäts- und TLS-Volumezuordnungen lokal kontrollieren; weder
   Compose neu generieren noch Volumes ersetzen/löschen.
3. Zwei Arbeitsplätze und synthetischen Incident mit EL, weiterer Rolle, offenem
   Patienten, gebundener Ressource und laufendem Transport vorbereiten. Zustand
   geschützt erfassen; Vergleich der Dokumente ohne Veröffentlichung ihrer Inhalte.
4. Geprüften Schema-2-Release ausschließlich über den bestehenden Update-Agent
   ausdrücklich installieren. Laufende Digests, Health und Anmeldung prüfen.
   CA-Onboarding auf Port 8081, CA-Fingerabdruck und HTTPS-Vertrauen vergleichen.
5. Akzeptanzkriterien mit getrennten Benutzerkonten prüfen. Abschluss ohne
   Bestätigung/Grund verwerfen lassen; bestätigt abschließen, fremde Wiedereröffnung
   verweigern, berechtigt wiedereröffnen. Zweiten Arbeitsplatz und Audit prüfen.
6. Nach Update zusätzliche synthetische Datenänderung speichern. Über den Agent
   auf die zuvor festgehaltenen API/Web-Images zurückkehren. Medizinische Daten,
   Identitäten, CA und Lifecycle-Historie müssen einschließlich dieser neuen
   Änderung erhalten bleiben. KEIN Datenbank-Restore, kein `down --volumes`, kein
   Neuaufsetzen der Identitätsvolumes. Rollback ist ausschließlich Image-Rückkehr.
7. Denselben geprüften Release erneut installieren. Vollständigen Pi-Neustart
   durchführen. Aktive Digests, persistente Runtime-Compose, Agent-Socket,
   MongoDB/Identitäten, Anmeldung, Onboarding und beide Arbeitsplätze erneut prüfen.
8. Bei `recovery_required`, abweichenden Digests, fehlenden Volumes oder
   Datenabweichung abbrechen und lokal die bestehende Recovery-Anleitung verwenden.
   Keine medizinischen Daten automatisch auf einen älteren Stand zurücksetzen.

Erst nach erfolgreicher gemeinsamer Abnahme den tatsächlichen Pi-Test als bestanden
kennzeichnen. Ein grüner PR ist keine Aussage über einen bereits erfolgten Deploy.
