# System & Updates: Installation, Freigabe und Wiederherstellung

Implementiert auf `feature/docker-deployment`. Kein automatisches Deployment durch diese Änderung. Vor produktiver Aktivierung ist die unten beschriebene Abnahme auf einem separaten Pi mit ausschließlich synthetischen Daten erforderlich.

## Sicherheitsmodell

FastAPI bleibt UID 10001 ohne Docker-Socket, sudo oder Host-Schreibzugriff. Es kann über einen Unix-Socket nur `status`, `check`, `apply`, `rollback` anfordern. Der Host prüft Linux-Peer-Credentials (root oder UID 10001), feste Requestfelder, ein separates Updatepasswort und die lokale Releasefreigabe. Kein Request darf Shellbefehle, Pfade, Compose-Dateien, Registry-Namen oder Image-Tags bestimmen. Der Dienst besitzt wegen Docker Hostprivilegien; er ist keine Isolation gegenüber einem kompromittierten Docker-Daemon. Code, Konfiguration und deren übergeordnete Verzeichnisse müssen root gehören und dürfen von App-UID/Deploy-Benutzer nicht beschreibbar sein. Docker userns-remap/rootless wird von dieser Installation nicht unterstützt.

Die bestehende DIVERA-Admin-Anmeldung bleibt erhalten: scrypt, gehashte kurzlebige Bearer-Tokens, globales MongoDB-Ratelimit. Jede Update-/Rollback-Aktion verlangt eine neue Anmeldung und zusätzlich das separate, ausschließlich auf dem Host gespeicherte scrypt-Updatepasswort. Der Host begrenzt Freigabeversuche persistent auf fünf pro fünf Minuten, auch nach Neustart. Browser speichern weder Token noch Passwörter dauerhaft. Es werden keine Cookies für Autorisierung verwendet. Administration ausschließlich über HTTPS oder SSH-Tunnel. Status enthält nur Versionen, Vorgangskennung und feste Fehlermeldungen; keine Containerlogs oder Einsatzdaten. API-Aktionen werden in `admin_audit`, Host-Phasen in `update-state/audit.jsonl` protokolliert. Host-Audit regelmäßig geschützt extern sichern/rotieren; es ist kein manipulationssicheres Fernprotokoll.

`check` liest die **lokal vom Administrator freigegebene** Releaseversion. Es fragt nicht ungeprüft den neuesten GitHub-Commit ab. Ein Release besteht aus zwei exakten GHCR-Digests (API/Web) und Schema 1. Nur rückwärtskompatible, migrationsfreie Releases freigeben. Schema-/MongoDB-/Compose-/Secret-Änderungen benötigen eine gesonderte SSH-Migration. Ein Freigabemanifest ist die bewusste lokale Vertrauensentscheidung des Administrators; dessen Herkunft/CI-Nachweise vor Freigabe überprüfen.

## Transaktion und Ausfallverhalten

1. Aufträge bekommen eine persistierte Kennung; eine Prozesssperre schützt auch gegen die alten SSH-Skripte. Parallele Aufträge und Wiederholungen für die bereits aktive Version werden abgelehnt.
2. Eine persistente Host-Wartungssperre blockiert App-Zugriffe und DIVERA-Polling. Unlesbare Sperrzustände sperren die App. Status, Admin-Anmeldung und Gesundheitsprüfung bleiben erreichbar.
3. Prüfung von Compose-Prüfsumme, laufenden Image-IDs, HTTP/DB und aktiven Einsätzen. Ein Fehler hier verändert keine Container. Anschließend Pull ausschließlich der freigegebenen Digests.
4. Web/API kontrolliert stoppen, damit auch bereits laufende Schreibzugriffe auslaufen; Einsatzstatus nochmals direkt in MongoDB prüfen. Operative oder unbekannte Einsatzstatus sperren Updates und Rollbacks. Keine Notfall-Umgehung in der WebApp.
5. Die bewährten lokalen und externen Backupskripte werden verwendet. Zusätzlich: frisches Archiv, vollständiger Parserlauf, tatsächliche Wiederherstellung in eine temporäre DB, Vergleich der Dokumentzahlen, anschließendes Löschen der temporären DB, SHA-256-Manifest und vollständiges Lesen des verschlüsselten Restic-Backups. Fehlendes USB-Laufwerk oder ein fehlerhafter Schritt bricht ab. Bei abgebrochenem Restore-Test können `els_mhd_verify_*`-Datenbanken zurückbleiben; nach Prüfung über SSH löschen.
6. Vorherige Image-IDs/Releaseinformationen werden gespeichert. `active.json` ist die atomar mit fsync geschriebene Versionsautorität. Compose wird daraus bei **jedem** Start erzeugt. Nur API/Web werden mit `--no-deps --no-build --pull never` neu erstellt; MongoDB/Volumes bleiben erhalten.
7. Erst nach HTTP- und DB-Prüfung wird der Vorgang abgeschlossen und das Wartungsfenster beendet. Bei Fehler oder Prozess-/Stromausfall werden vorherige Images wiederhergestellt und geprüft. Schlägt dies fehl: `recovery_required`, Wartung bleibt aktiv, keine weiteren Web-Aufträge.

Der Web-Status ist während des Containerwechsels vorübergehend nicht erreichbar. Die Seite verbindet sich alle drei Sekunden erneut; der Auftrag läuft auf dem Host weiter. Es wird Phasenfortschritt angezeigt, kein erfundener Prozentwert. Nach dem Neustart liest der Dienst zuerst die Transaktion und führt Wiederherstellung aus. Rollback ist ein reiner Anwendungsrollback; die Datenbank wird niemals automatisch auf einen älteren Stand zurückgesetzt. Die letzte erfolgreiche Version wird als nächster Checkpoint erhalten; keine Image-Prune-Jobs ohne Ausschluss dieser Images verwenden.

## Pi vorbereiten (64 Bit Debian/Raspberry Pi OS, Python >= 3.11)

Vorausgesetzt: Docker Engine mit Compose v2, curl, MongoDB Database Tools im vorhandenen DB-Image, restic, getestetes externes Backup und die bestehende Admin-/DIVERA-Secret-Konfiguration. Vorab den bisherigen Installations- und Backupanleitungen folgen. Alle Befehle lokal auf dem Test-Pi prüfen. Die Installation ersetzt keine Absicherung der übrigen Einsatz-API.

Aus einem geprüften Checkout dieses Branches, in einem geplanten Wartungsfenster:

```bash
sudo install -d -m 700 /opt/els-mhd/config /opt/els-mhd/runtime /opt/els-mhd/update-state /opt/els-mhd/rollback /opt/els-mhd/backups
sudo install -d -m 755 /opt/els-mhd/update-public /usr/local/lib/els-mhd
sudo install -o root -g root -m 644 deploy/agent/*.py /usr/local/lib/els-mhd/
sudo install -o root -g root -m 700 scripts/backup-mongodb.sh scripts/backup-external.sh /usr/local/lib/els-mhd/
sudo install -o root -g root -m 644 deploy/systemd/els-mhd-update-agent.service /etc/systemd/system/
```

Das externe Backupskript enthält die bisher getestete Datenträger-UUID. Diese **nur in der installierten Hostkopie** an die konkrete USB-Platte anpassen und Mount/Restic-Passwort/Repository prüfen. Der Dienst verlangt `/mnt/els-mhd-backup`. Keine Passwörter in Befehlszeilen oder Repo-Dateien einfügen. Die bestehende `deploy/secrets`-Konfiguration aus der DIVERA-Anleitung muss verfügbar sein; vor dem Rendern auf rootgeschützte Hostpfade legen. Docker-Compose-Secrets werden beim Rendern auf absolute Pfade aufgelöst.

Eine eingefrorene Compose-Konfiguration einschließlich Admin- und Update-Overlay erstellen. Der gerenderte Inhalt enthält möglicherweise Secrets und darf **nie** ins Repo oder in Logs gelangen:

```bash
sudo sh -c 'umask 077; docker compose --project-name els-mhd --env-file /opt/els-mhd/config/docker.env -f deploy/compose.yaml -f deploy/compose.admin.yaml -f deploy/compose.updates.yaml config > /opt/els-mhd/runtime/compose.yaml'
sudo chown -R root:root /opt/els-mhd/runtime /usr/local/lib/els-mhd
sudo chmod 700 /opt/els-mhd/runtime
sudo python3 /usr/local/lib/els-mhd/provision.py initial-reviewed-version
```

`provision.py` setzt kein Update um; es erfasst die tatsächlichen Images der laufenden Container und fragt ein neues separates Updatepasswort ab. Zuerst müssen die laufenden API/Web-Images diese Updateimplementierung enthalten; diesen einmaligen Bootstrap auf dem Test-Pi separat bauen und installieren. Er darf nicht während eines Einsatzes stattfinden. Keine unbekannten Images per `latest` als Ausgangszustand akzeptieren. Bei teilweiser Provisionierung Dateien nicht blind löschen; vorhandenen Secret-/Versionszustand prüfen.

Danach API/Web einmalig aus der eingefrorenen Konfiguration und dem erfassten Zustand starten (nimmt die Socket-/Wartungs-Mounts auf), prüfen, erst dann Dienst aktivieren:

```bash
sudo python3 /usr/local/lib/els-mhd/compose.py start
sudo systemctl daemon-reload
sudo systemctl enable --now els-mhd-update-agent.service
sudo systemctl status els-mhd-update-agent.service
curl --fail http://127.0.0.1:8080/api/system/updates/status
```

Der Dienst muss für Laufzeitverzeichnis und Socket zuständig bleiben; nicht den einzelnen Socket als Docker-Bind-Mount einhängen. Die App mountet die Verzeichnisse nur lesbar. Bei `recovery_required` ist SSH nötig. Images, Runtime-Compose, `docker.env`, Admin-/Verschlüsselungs-/Restic-Secrets und Versionszustände geschützt außerhalb des Repo sichern. Restic-Datenbankbackups ersetzen diese Konfigurationssicherung nicht.

## Releases bauen und bewusst freigeben

In einer vertrauenswürdigen Buildumgebung einen geprüften Commit auschecken, Tests ausführen und für den Pi bauen. Beispiel mit bewusst gewähltem Release-Tag, kein automatischer Installationsbefehl:

```bash
docker buildx build --platform linux/arm64 -t ghcr.io/davidstaffe/els-mhd-api:RELEASE --push backend
docker buildx build --platform linux/arm64 -t ghcr.io/davidstaffe/els-mhd-web:RELEASE --push frontend
docker buildx imagetools inspect ghcr.io/davidstaffe/els-mhd-api:RELEASE
docker buildx imagetools inspect ghcr.io/davidstaffe/els-mhd-web:RELEASE
```

Commit, Testergebnisse, ARM64-Unterstützung und beide Digests verifizieren. Bei privaten GHCR-Images die Registryanmeldung mit `sudo docker --config /opt/els-mhd/config/docker-client login ghcr.io` ausschließlich lokal für root konfigurieren (Verzeichnis 700, Dateien 600). Der gehärtete Dienst liest kein Home-Verzeichnis. Freigabe mit `sudoedit /opt/els-mhd/config/approved-release.json` erstellen, root:root und Modus 600; anschließend atomar ersetzen. Muster (Platzhalter **durch echte geprüfte Digests ersetzen**, keine gültige Freigabe im Repo):

```json
{"version":"v1.2.3","api":"ghcr.io/davidstaffe/els-mhd-api@sha256:API_DIGEST","web":"ghcr.io/davidstaffe/els-mhd-web@sha256:WEB_DIGEST","schema":1,"notes":"Geprüfte Änderungen und bekannte Einschränkungen"}
```

Die WebApp zeigt diese Freigabe unter Einstellungen → System & Updates → Auf Updates prüfen. Installation oder Rollback verlangen Administratorpasswort, separates Updatepasswort und ausdrückliche Bestätigung. Ein inzwischen geändertes Freigabemanifest wird nicht unter der alten Versionsbestätigung installiert. Bei Änderungen an einem Release stets eine neue Versionskennung verwenden.

## SSH- und Datenwiederherstellung

Für normale Image-Rückkehr Web-Rollback verwenden. `active.json` und `previous.json` enthalten die Images; `transaction.json` enthält den Zustand und vorherigen Stand. Bei Ausfall zuerst `journalctl -u els-mhd-update-agent` sowie diese Dateien lokal prüfen, ohne Secrets/Patientendaten zu veröffentlichen. Ein Neustart des Dienstes versucht unterbrochene Transaktionen wiederherzustellen. Bei `recovery_required` die Ursache beheben und nach Prüfung der Transaktion deren Zustand lokal auf `recover` setzen, Dienst erneut starten. Zustand nicht auf `complete` umbenennen, um die Sperre zu umgehen.

Für einen manuellen Start der bereits festgeschriebenen Version den Agent stoppen und `sudo python3 /usr/local/lib/els-mhd/compose.py start` verwenden. Alte `deploy-update.sh`, `rollback-application.sh` und `create-rollback-checkpoint.sh` gehören zum bisherigen SSH-Verfahren und sind **nicht** mit dem neuen Versionszustand zu mischen; der laufende Agent hält ihre gemeinsame Sperre. Neue Versionen ausschließlich über den Agent installieren. Keine einfachen `docker compose up --build` gegen das alte Checkout-Compose nach dem Wechsel benutzen.

Datenwiederherstellung ist ausdrücklich **kein Web-Rollback**. Sie verwirft neuere Daten und benötigt eine separate Entscheidung. Das rootgeschützte `restore.py` verlangt eine gesicherte Vorgangskennung, prüft Pfad/Archivprüfsumme, aktive Einsätze und Archivparser und stoppt API/Web. Es stellt nur `els_mhd.*` mit `--drop --stopOnError` wieder her. Es darf nur bei gleichem, geprüften Schema verwendet werden; nicht im Backup enthaltene zusätzliche Sammlungen werden nicht automatisch gelöscht. Dienst vorher stoppen. Beispiel:

```bash
sudo systemctl stop els-mhd-update-agent
sudo python3 /usr/local/lib/els-mhd/restore.py VORGANGSKENNUNG
```

Nach Wiederherstellung bleibt Wartung absichtlich aktiv. Daten und passende Imageversion lokal prüfen; erst danach über den geprüften Startpfad öffnen. Ein fehlgeschlagener Restore bleibt gesperrt und benötigt eine erneute SSH-Wiederherstellung. Für externe Wiederherstellung zuerst das gewählte Restic-Snapshot in ein separates rootgeschütztes Verzeichnis zurücklesen und SHA-256 gegen das gesicherte Manifest prüfen; niemals ungeprüft direkt über die Live-Daten schreiben. Vor einem destruktiven Restore nach Möglichkeit den beschädigten aktuellen Stand separat sichern.

## Tests und verbindliche Pi-Abnahme

Automatische Tests ohne echte Daten/Netzwerkdienste:

```bash
PYTHONPATH=backend python -m pytest backend/tests/test_update_agent.py backend/tests/test_system_updates.py backend/tests/test_divera_global_settings.py -q
cd frontend
CI=true npm test -- --watch=false --runInBand --testPathPattern='(SystemUpdatesPage|EinstellungenPage).test'
```

CI führt die isolierten Tests zusätzlich unter Linux aus. Die Fehlertests simulieren Hostaktionen; sie beweisen keinen echten Docker-/USB-/Stromausfalltest. Vor Aktivierung am Einsatzsystem auf einem separaten ARM64-Pi dokumentiert abnehmen:

- Unberechtigte API-Aufrufe, falsches Admin-/Updatepasswort, sechster Versuch, Ablauf und Neustart des Ratelimits; keine Secrets in Antworten/Logs.
- Fremde Socket-UID und beliebige Befehle/Pfade/Registry-Digests ablehnen; FastAPI besitzt keinen Docker-/Host-Schreibzugriff.
- Update A→B, Rollback B→A, weiteres Update A→C; UI-Refresh/Verbindungsabbruch; nach Reboot exakte Images und DIVERA-Key/Intervall erhalten.
- Aktiven Einsatz anlegen und beide Aktionen sperren; zusätzlich einen bereits laufenden Schreibrequest während Wartungsbeginn testen.
- USB abziehen/falsche UUID, leeres/korruptes Archiv, fehlendes Secret, Restic-Fehler, wenig Plattenplatz, Pull-/Registryausfall, fehlerhafte Kandidatenimages und fehlenden Checkpoint testen.
- Prozessabbruch/Reboot in jeder Transaktionsphase; vorherige Images und Wartungszustand prüfen. Bei fehlgeschlagener automatischer Rückkehr muss SSH-Sperre bestehen bleiben.
- Tatsächlichen Backup-Restore mit ausschließlich synthetischen Daten und abweichenden Datenständen prüfen. Auch externe Restic-Wiederherstellung und Konfigurations-/Secretsicherung testen.

Quellen für die verwendeten Optionen: [Docker Compose up](https://docs.docker.com/reference/cli/docker/compose/up/), [MongoDB mongorestore](https://www.mongodb.com/docs/database-tools/mongorestore/).
