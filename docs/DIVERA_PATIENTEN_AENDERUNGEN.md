# DIVERA-Einstellungen und Patienten-Disposition (Entwicklungsstand)

## Voraussetzungen für die Inbetriebnahme

Die ELS-MHD-Weboberfläche unter `/einstellungen` ermöglicht den Betrieb ohne
erneutes Bearbeiten des DIVERA-Keys über SSH. Einmalig müssen bei der Installation
jedoch **zwei Server-Secrets** im Backend gesetzt sein:

- `ELS_ADMIN_PASSWORD`: nur dem berechtigten Administrator bekanntes Passwort.
- `ELS_SETTINGS_ENCRYPTION_KEY`: ein dauerhaftes Fernet-Key-Material, separat
  von der Datenbank geschützt; Erzeugung z. B. auf dem Zielsystem:
  `python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`.

Die Werte gehören in die geschützte Deployment-Umgebung, **nicht** ins Git-Repository
oder in Frontend-Build-Variablen. Eine Änderung von
`ELS_SETTINGS_ENCRYPTION_KEY` ohne Re-Encryption des Datenbank-Eintrags macht
den gespeicherten DIVERA-Key unlesbar. Daher muss er mit dem Backup gesichert werden.
Die Administration sollte ausschließlich per **HTTPS** erreichbar sein.
Bis zur späteren Benutzerverwaltung ist das separate Admin-Passwort nur ein
Übergang; die aktuelle Browser-Rollenwahl stellt **keine Authentifizierung** dar.

Der bisherige `DIVERA_API_KEY` wird als Fallback gelesen, bis ein verschlüsselter
Schlüssel über die Oberfläche gespeichert wurde. Die bestehende `.env` wird nicht
automatisch verändert. Bestehende Polling-Aktivierungen pro Incident bleiben
in der Datenbank erhalten. Intervall-Presets: 5, 10, 20, 30, 60, 120, 300 Sekunden,
Standard 30 s. Vor 5-s-Produktivbetrieb DIVERA-Rate-Limits bestätigen.

## Patientenmanagement

- Neue Schnellerfassung unter `/patienten/schnell`, eine Kachel pro aktivem
  Abschnitt plus `unbekannt`. Tasten 1/2/3/0/D gelten für ausgewählten Abschnitt.
- Neu gemeldete Patienten bleiben `wartend` und ohne disponierte Ressource.
  Eine Sichtung ist vorläufig, bis eine Funkbestätigung eingetragen wird.
  Die Bestätigung wird auch ohne Sichtungsänderung protokolliert.
- Organisatorischer Abschnitt und beschreibender Auffindeort werden getrennt
  von behandelnder bzw. disponierter Ressource geführt.
- Ressourcenvorschläge: freier eigener Abschnitt, aktuelle geografische Nähe
  (Positionsstempel bis 5 Minuten), benachbarte Abschnittspolygone, sonstige
  freie Ressourcen. Die Nähe ist Luftlinie, keine Anfahrtszeit.
- Maximal eine aktive Patientenbindung pro Ressource im Normalbetrieb,
  mit atomarer Reservierung in MongoDB. Patientenabschluss oder Übergabe
  lösen **keine automatische Freimeldung** aus.
- Freimeldung bedarf des Server-Admin-Passworts und ändert keinen DIVERA-FMS-Status.
  Der spätere Login soll diese Übergangslösung durch echte EL-Rechte ersetzen.
- Ein MANV-Modus mit zwei Patienten pro Ressource ist **nicht aktiviert/implementiert**;
  die Datenstruktur bleibt durch eigenständige Dispositionshistorie erweiterbar.

## Noch bewusst offen / vor Produktivfreigabe

1. Echte Anmeldung und administrierbare Rollen mit verifizierten Klarnamen.
   `entered_by` wird derzeit **null** protokolliert; keine Scheinidentitäten.
2. Exakte Rollenberechtigungen für EL/FüAss werden mit dem Login festgelegt.
   Momentan bietet das Frontend die Aktionen für diese Rollen an; außerhalb der
   Administrator-Schutzfunktion besteht noch kein vollständiger Backend-RBAC.
3. Übergabe an eine zweite behandelnde Ressource, während die erste intern
   gebunden bleibt, wird erst nach gesonderter fachlicher Entscheidung entwickelt.
4. Dedizierter MANV-Modus mit einzelnen Personalzuordnungen wird später abgestimmt.
5. Gemeinsamer Polling-Task koordiniert derzeit **einen Backend-Prozess**.
   Für mehrere Uvicorn-Worker/Replicas wäre eine verteilte Sperre bzw. externer
   Scheduler erforderlich.
6. Systemtests mit echter MongoDB, DIVERA-Testkonto, Frontend-Browser und
   Raspberry-Pi-Deployment sind zusätzlich zu Syntax/Build-Checks notwendig.

## Manuelle Akzeptanzprüfung

- Ohne DIVERA-Key erscheint der Konfigurationshinweis und die Einstellungsseite.
- Mit Admin-Zugang Key testen; beim ungültigen Key keine Überschreibung.
- Gültigen Key speichern; laufende Synchronisierung verwendet ihn ohne Neustart.
- Intervall ändern; Backend-Neustart übersteht die Speicherung.
- Mit zwei aktiven Incidents prüfen: ein Fahrzeugabruf pro Durchlauf.
- S2-Schnellanlage in Abschnitt Nord ergibt `wartend`, `vorläufig`,
  ohne disponierte/behandelnde Ressource.
- S2 mit meldender Streife bestätigen; Bestätigung auch ohne Wechsel protokolliert.
- Dieselbe Ressource einem zweiten Pat. zuweisen → Konflikt statt Doppelbindung.
- Pat. abschließen → Ressource bleibt gebunden, bis explizite Freimeldung.
- DIVERA unterbrechen → Vorschlag nur auf Abschnitts-/freien Ressourcendaten basieren.
- Patient mit Bett löschen → Bett und aktive Ressourcenzuordnung freigegeben.
