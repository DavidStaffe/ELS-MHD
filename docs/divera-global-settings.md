# Globale DIVERA-Einstellungen

## Bedienung

`/einstellungen` ist ohne gewählten Einsatz erreichbar. Dort stehen der globale
DIVERA-Key, der Verbindungsstatus und das feste Abrufintervall. Der Link zur
bestehenden Seite „System & Updates“ bleibt erhalten; diese verlinkt zurück.
Die Lagekarte enthält ausschließlich Betriebsstatus und Start/Stop/manuelle
Synchronisierung. „Aktiviert“ ist unabhängig vom Erfolg des letzten Abrufs.

Ein gesondertes Administratorpasswort schaltet Konfigurationsänderungen für zehn
Minuten frei. Die Rolle aus der Einsatzoberfläche verleiht diese Berechtigung
nicht. Passwort, eingegebener Key und Sitzungstoken werden nicht in Browser-
Speichern abgelegt. Abmelden widerruft die Sitzung serverseitig.

Ein neuer Key wird zuerst getestet und beim Speichern erneut mit genau dem
übermittelten Wert geprüft. Fehlschläge ersetzen den bisherigen Key nicht.
HTTP 401/403 werden als ungültig/unberechtigt gemeldet; Netzwerkfehler und andere
Antworten als derzeit nicht prüfbar. Der gespeicherte Key wird nie zurückgegeben.

Intervalle: 10, 20, 30 (Standard), 60, 120, 300 Sekunden. 5 Sekunden sind in der
Auswahl vorgesehen, aber in UI **und Backend gesperrt**. Die am 27.10.2026 geprüfte
[offizielle Pull-Spezifikation](https://api.divera247.com/docs/api_v2_pull.yaml)
und [DIVERA-FAQ](https://help.divera247.com/pages/viewpage.action?pageId=96240307)
nennen keine ausdrückliche Freigabe für einen Fahrzeugstatusabruf alle fünf
Sekunden. Die Beschränkung für Alarmierungen ist keine solche Freigabe.
Eine spätere Aktivierung erfordert eine bestätigte zulässige Frequenz und eine
bewusste Codeänderung; es gibt keinen ungesicherten Freischalter im Frontend.

## Persistenz und gemeinsame Abfrage

MongoDB `system_settings` enthält `divera` (Fernet-verschlüsselter Key, Intervall,
Prüfzeit) und `divera_poll` (letzter Abruf/Erfolg, Fehler, Fehlversuche,
Wiederholungsfrist und gemeinsamer Fahrzeug-Snapshot). `incidents.divera_enabled`
bleibt die persistierte gewünschte Teilnahme am Polling.

Jeder API-Prozess hat höchstens einen Scheduler. Automatische Abrufe laufen nur,
wenn mindestens ein aktivierter, nicht abgeschlossener Einsatz existiert.
Ein installationsweiter MongoDB-Lock serialisiert Scheduler, manuelle Abrufe,
Fahrzeugauswahl und Key-Prüfung/-Wechsel auch über mehrere API-Worker hinweg.
Die eindeutige `_id` des Lockdokuments verhindert doppelte Besitzer. Operationen
haben ein 55-Sekunden-Limit bei einer 90-Sekunden-Lease; nach einem Prozessabbruch
wird die Lease spätestens nach 90 Sekunden wieder verfügbar.

Alle aktivierten Einsätze erhalten denselben Snapshot, behalten aber ihre eigenen
Ressourcenzuordnungen. Manuelle Synchronisierung und Fahrzeugauswahl nutzen einen
noch aktuellen Snapshot weiter. Sie umgehen auch keine Wiederholungsfrist.
Fehler führen zu exponentiellem Backoff bis maximal einer Stunde; ein numerischer
`Retry-After` bei HTTP 429 kann diesen Abstand bis auf einen Tag verlängern.
Ein erfolgreicher Abruf setzt den Fehlerzähler zurück. Gespeicherte Fristen und
Teilnahmezustände werden nach einem Neustart weiterverwendet.

Key- und Intervalländerungen werden unter demselben Lock gespeichert und ohne
Neustart übernommen. Bei aktivem Polling erfolgt unmittelbar ein neuer Abruf.
Ein vorhandener `DIVERA_API_KEY` dient beim Übergang als Fallback und wird bei
eingerichteter Verschlüsselung beim Start einmalig verschlüsselt übernommen.
Eine bereits gespeicherte Konfiguration wird dabei nicht überschrieben.

## Einmalige Einrichtung (vor Deployment prüfen)

Es wurden keine Befehle auf dem Pi ausgeführt. Die folgenden Schritte sind eine
Bereitstellungsanleitung, kein automatisch ausgeführtes Update.

Benötigt werden zwei getrennte Geheimnisse:

- `ELS_ADMIN_PASSWORD_HASH_FILE`: Datei mit `scrypt$<salt-hex>$<digest-hex>`.
- `ELS_CONFIG_ENCRYPTION_KEY_FILE`: Datei mit einem Fernet-Schlüssel.

Alternativ werden die gleichnamigen Variablen ohne `_FILE` unterstützt. Dateien
sind vorzuziehen, damit Schlüssel nicht in Container-Umgebungsanzeigen erscheinen.
Keine Klartextpasswörter und keine echten Schlüssel in Git oder Shell-Historien.

Das interaktive Hilfsprogramm `backend/provision_admin.py <Secret-Verzeichnis>`
erzeugt beide Dateien, fragt das Passwort verdeckt ab und gibt keine Geheimnisse
aus. Es überschreibt keine vorhandenen Dateien. Mindestens 14 Passwortzeichen.
Das Programm benötigt Python und die bereits verwendete Bibliothek cryptography.

Die optionale Datei `deploy/compose.admin.yaml` bindet die Dateien aus
`deploy/secrets/` ein. Beim später geprüften Deployment müssen **beide** Compose-
Dateien mitgegeben werden. Die Dateien müssen für den API-Containerbenutzer
UID 10001 lesbar sein. Auf Linux beispielsweise die Dateien mit Eigentümer
10001 und Modus 0400 versehen; das Hostverzeichnis bleibt für die Verwaltung
geschützt. Nicht pauschal für alle Benutzer lesbar machen. Die im Compose-
Overlay angegebenen Secret-Pfade sind relativ zum Deploy-Verzeichnis.

Administrationszugriffe ausschließlich über HTTPS oder den bestehenden lokalen
SSH-Tunnel. Der Browser verwendet explizite Bearer-Header; es gibt keine
automatisch mitgesendeten Sitzungscookies. Der globale Login-Limiter erlaubt
fünf Versuche in fünf Minuten und funktioniert über API-Worker hinweg.
`admin_audit` protokolliert Anmeldungen sowie Beginn, Erfolg und Fehlschlag von
Key-Prüfung, Key-Wechsel und Intervalländerungen, jeweils ohne Zugangsdaten.

Verschlüsselungsschlüssel **getrennt von der Datenbank sichern** und bei Restore
zusammen mit deren passender Konfiguration wieder bereitstellen. Der Key wird
nicht automatisch neu generiert. Geht er verloren, ist der gespeicherte DIVERA-
Key nicht mehr lesbar; ein Administrator kann dann einen neuen DIVERA-Key prüfen
und mit einem bewusst bereitgestellten Verschlüsselungsschlüssel speichern.
Nach erfolgreicher Migration den alten DIVERA-Key aus der Umgebungsdatei entfernen.

Die vorhandene Update-/Rollback-Ausführung bleibt gesperrt, bis der separate
geschützte Host-Dienst implementiert und geprüft ist. Ihre Änderungsendpunkte
verwenden bereits dieselbe echte Administratorprüfung. Docker-Socket und
Hostkommandos werden nicht in die API eingebunden.

## Verifikation

Offline-Backendtests (aus dem Repository, `PYTHONPATH=backend` setzen):

```text
python -m pytest backend/tests/test_divera_global_settings.py -q
```

Benötigt Backend-Abhängigkeiten sowie `backend/tests/requirements-offline.txt`.
Diese Tests benutzen eine simulierte Datenbank und keine echte DIVERA-Verbindung.
Sie prüfen Authentifizierung, gefälschte Client-Rollen, Sperrfristen, Sitzungsende,
verschlüsselte Speicherung, fehlgeschlagene Key-Wechsel, feste Intervalle,
Migration, gemeinsame Abrufe, Incident-Trennung, Backoff und Worker-Leases.
Vor Produktivbetrieb zusätzlich mit einer DIVERA-Testeinheit und dem tatsächlichen
MongoDB-/Container-Aufbau testen, insbesondere Neustart und Secret-Dateirechte.
