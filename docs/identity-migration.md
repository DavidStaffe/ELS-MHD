# Identitätsmigration und kontrollierter Rückfall

## Status und Voraussetzungen

Dies ist ein prüfbarer Entwicklungsstand, keine Freigabe zur Installation.
Es wurden weder der Raspberry Pi noch Produktionsdaten verändert. Die erste
Umstellung ist wegen Identitätszustand, TLS, persistentem Volume und sicherem
Rollback-Checkpoint eine **manuelle Migration**. Der bestehende Web-Updater
darf diese Erstumstellung nicht als schema-kompatibles Routineupdate ausführen.

Vor dem Pilotbetrieb müssen Betreiber das Release reviewen, auf einem
isolierten Wiederherstellungsklon testen und ein Wartungsfenster freigeben.
Patienten-, Ressourcen-, Transport-, Tagebuch- und DIVERA-Daten bleiben in
ihren vorhandenen Collections. Nie `docker compose down -v` oder eine leere
Datenbank als Reparaturmaßnahme verwenden.

## Ablauf im isolierten Testsystem

1. Bestehenden MongoDB-Dump inklusive Konten/Sessions/Audit, Konfigurations-
   und Verschlüsselungsschlüssel sowie Image-Digests sichern. Wiederherstellung
   isoliert prüfen. Bereits vorhandene `global_settings.divera`-Daten aus PR #6
   und deren `ELS_SETTINGS_ENCRYPTION_KEY` ebenfalls sichern.
2. Neue Images aus dem Integrationsbranch bauen und als ARM64-Images prüfen.
   Docker ist in dieser Windows-Arbeitsumgebung nicht verfügbar; dieser Schritt
   wurde hier nicht ausgeführt. Keine automatischen Build-/Deployfreigaben
   oder GitHub-Merges werden durch diesen Branch ausgelöst.
3. `identity_state:/var/lib/els` dauerhaft für die API einbinden. Den
   `ELS_IDENTITY_STATE_FILE`-Pfad nicht im Container-Dateisystem ohne Volume
   ablegen. Die Datei ist gemeinsam mit MongoDB und Konfiguration zu sichern.
   Bei Wiederherstellung darf eine abgeschlossene Datei nicht durch eine
   `pending`-Datei ersetzt werden. Fehlende/inkonsistente Marker oder DB
   öffnen niemals automatisch einen öffentlichen Setupzugang.
4. LAN-HTTPS mit vertrauenswürdigem lokalem CA-Zertifikat einrichten. SAN muss
   dem tatsächlichen Hostnamen beziehungsweise der IP entsprechen. Optionales
   Compose-Overlay `deploy/compose.https.yaml` verwendet
   `deploy/secrets/tls/server.crt` und `server.key` sowie die genaue
   `ELS_HTTPS_ORIGIN`, z.B. `https://els.example.lan`. CA-Vertrauen auf allen
   Arbeitsplätzen vorher installieren. Ein öffentliches Zertifikat oder
   Internetzugang sind nicht notwendig. Private Schlüssel nicht committen.
   HTTP ist kein unterstützter Anmeldebetrieb: Secure-Cookies werden nicht
   absichtlich aufgeweicht. Das Basis-Compose allein liefert noch kein TLS.
5. Auf einer **echten Neuinstallation** bewusst im API-Container
   `python identity_setup.py --new-install` ausführen. Auf einer vorhandenen
   Installation ohne persönliche Konten stattdessen ausdrücklich
   `python identity_setup.py --adopt-existing`. Letzteres ist eine lokale
   Betreiberentscheidung, kein öffentlicher Legacy-Passwort-Bypass. Beide
   Befehle verweigern erneute Einrichtung, vorhandene Benutzer oder bestehenden
   Einrichtungszustand. Nicht versuchen, diese Sicherung durch Löschen von
   Collections/Dateien zu umgehen. Bei bereits vorhandenen persönlichen
   Legacy-Konten ist eine gesonderte geprüfte Zuordnung/Migration nötig.
6. Den einmalig ausgegebenen Setup-Code über die HTTPS-Ersteinrichtung
   verwenden. Die Einrichtung beansprucht den DB-Zustand vor weiteren
   Schreibvorgängen dauerhaft. Ein Fehler danach bleibt gesperrt und erfordert
   lokale Diagnose; es wird kein neuer öffentlicher Setupweg erzeugt.
7. Einmalig angezeigtes Erstpasswort und Recovery-Code sicher verwahren.
   Mit Erstpasswort anmelden und eigenes Passwort setzen. Administrator hat
   zunächst `users.manage`, `settings.manage`, `archives.manage`, jedoch weder
   operative Rolle noch medizinisches Leserecht. Weitere globale Rechte und
   Eignungen bewusst in „Einstellungen → Benutzer und globale Rechte“ vergeben.
8. Alt-Incidents ohne verlässliche Identitätszuordnung werden nicht anhand
   frei eingegebener Namen automatisch einem Konto zugeordnet. Eine geeignete
   EL für offene Alt-Incidents ausdrücklich durch `incidents.roles.assign`
   ernennen. Alte Archive über explizite Freigaben beziehungsweise globale
   Leserechte erschließen. Unbekannte historische Ersteller/Abschließende
   bleiben unbekannt; persönliche Wiedereröffnungsrechte werden nicht erfunden.
9. DIVERA-Konfiguration prüfen. Neue `system_settings` haben Vorrang. Fehlen
   sie, kann die alte verschlüsselte `global_settings`-Konfiguration mit ihrem
   ursprünglichen Schlüssel gelesen und beim Initialisieren in die neue
   Verschlüsselung übernommen werden. Ursprüngliche Daten werden nicht
   gelöscht. Fehler beim Entschlüsseln sind sichtbar und führen nicht zur
   stillen Verwendung eines anderen Keys. `DIVERA_API_KEY` bleibt nur ein
   Legacy-Fallback, bis ein persönlicher Berechtigter den Key ersetzt.
10. `ELS_ADMIN_PASSWORD` und frühere Installation-Bearer-Sessions etablieren
    keine persönliche Identität. Die Produktions-App blockiert den alten
    `/api/admin/login`-Weg. Nach Prüfung alte Shared-Login-Secrets aus der
    Laufzeitkonfiguration entfernen. Das **separate Host-Updatepasswort** und
    die rootgeschützte Releasefreigabe bleiben erhalten. Web-Updates verlangen
    persönliche `settings.manage`-Session und weiterhin Host-Freigabe.

## Rollback darf keine Zugriffskontrolle entfernen

Der mitgelieferte Host-Agent besitzt eine zusätzliche Sicherheitsgrenze:
Existiert die rootgeschützte Datei `/opt/els-mhd/config/identity-required`,
akzeptiert er nur Release-Manifeste mit `schema: 2`. Das gilt für Freigabe,
expliziten Rollback, Installation und Wiederanlauf einer unterbrochenen
Installation. Ohne bewusst migrierten Host bleiben alte Schema-1-Verfahren
für bestehende Installationen kompatibel.

Bei der manuell geprüften Erstumstellung müssen Betreiber daher auch den
rootgeschützten Agenten und dessen eingefrorenes Compose-Bundle aktualisieren,
die Bundle-Prüfsumme neu bestätigen, den Identity-Mindeststand setzen und
einen getesteten **Schema-2-Checkpoint** anlegen. Der bisherige Schema-1-
Checkpoint ist danach kein zulässiger Web-Rollback mehr. Die Anwendung kann
das rootgeschützte Flag nicht setzen oder entfernen. Diese Schritte wurden
nicht remote ausgeführt und müssen vor Freigabe separat abgenommen werden.

Die Schema-Zahl ist eine explizite Betreiberzusicherung, kein automatischer
Codebeweis. Niemals ein altes ungeschütztes Image lediglich als Schema 2
umetikettieren. Image-Digests weiterhin rootgeschützt freigeben. Ein
Image-Rollback stellt keine Datenbank zurück und darf den Einrichtungsmarker,
Sessionsicherheitszustand oder Auditdaten nicht zurücksetzen.

## Störungen

* **DB fehlt/nicht erreichbar:** Startup oder Anmeldung schlägt geschlossen
  fehl. Es gibt keine automatische Neuinitialisierung und keine Defaultrolle.
* **Setup unterbrochen:** Datei und DB-Zustand lokal abgleichen. `claimed` oder
  `complete` nie einfach auf `pending` zurücksetzen. Bestehendes Konto kann
  unabhängig vom öffentlichen Setup anmelden; Recovery nutzen, falls vorhanden.
* **Mutex nach Crash:** Genau den zugehörigen Vorgang in `identity_locks`,
  `security_audit`, Incidenthistorie und Datensatzversionen untersuchen. Erst
  nach abgeschlossener Diagnose diese einzelne Sperre freigeben. Die sichere
  Voreinstellung ist blockierte Änderung, nicht ein automatisch ablaufender
  möglicherweise noch aktiver Schreibschutz.
* **Sicherheitsnotfallsperre:** Sessions werden sofort widerrufen. Vorhandene
  Führungsfunktionen werden als zeitnah zu übergebende Aufgaben aufgeführt.
  Aktive EL durch globalen Rollenvergeber ersetzen; AL/FüAss über die jeweils
  berechtigte Funktion übergeben/aufheben. Deaktivierte Konten können ihre
  verbliebenen Rollen begründet aufgehoben bekommen. Wiederaktivierung
  reaktiviert keine zurückgelassenen Einsatzrollen.
* **Abmeldung ohne Verbindung:** Oberfläche bleibt gesperrt und meldet, dass
  der Server die Abmeldung noch nicht bestätigt hat. Erneut abmelden, sobald
  die Verbindung wieder besteht. Keine bestätigte Sessionwiderrufung vortäuschen.

## Noch erforderliche Betriebsabnahme

Echter MongoDB-Test mit konkurrierenden Browsern, während Sperre/Entzug laufende
Streams und Exporte, Stromausfall in Ernennung/Abschluss/Korrektur/Bootstrap,
Containerneustart, leeres/falsches DB-Ziel, Image-Rollback, Backup/Restore von
DB und Marker, Zertifikatswechsel, offline gebaute ARM64-Images und Pi-
Speicher-/Hashlast. Wartungsbackup und dabei zulässige Session-Auditänderungen
müssen gemeinsam mit dem Host-Agenten getestet werden. Es wird keine
automatische Produktionsreife aus Unit-/Vertragstests abgeleitet.
