# Geprüfter Installationsweg für https://10.0.0.1

Diese Anleitung gehört zur Main-Integrations-PR. Erst nach deren erfolgreicher
Prüfung und Merge verwenden. **Der Merge installiert nichts auf dem Pi.**
Ziel ist die bestehende Docker-Installation mit rootgeschützter
Updateverwaltung unter `/opt/els-mhd`. Die Datenbank wird nicht ersetzt,
zurückgesetzt oder in ein neues Volume verschoben.

## Vorher

* Pi mit 64-Bit Raspberry Pi OS/Debian, Python 3.11+, Docker/Compose v2,
  OpenSSL und mindestens 8 GiB freiem Speicher. Der Pi muss die Adresse
  **10.0.0.1 tatsächlich selbst besitzen**. Arbeitsplätze müssen ihn dort
  erreichen können. Die Vorprüfung kontrolliert die lokale Adresse.
* Alle operativen Einsätze einschließlich Demos vorher abschließen. Offene
  Einsätze sperren die Installation; sie werden niemals automatisch geschlossen.
* Die vorhandene rootgeschützte Compose-Konfiguration, laufenden Container
  `els-mhd-{db,api,web}-1`, Versionszustand und getestete externe Restic-
  Sicherung müssen vorhanden sein. `/mnt/els-mhd-backup` muss eingehängt sein.
  Das separate Host-Updatepasswort bleibt unverändert.
* Auf Port 443 darf kein anderer Dienst laufen. Kein `docker compose down -v`,
  keine Volume-Löschung und kein Kopieren einer leeren Beispieldatenbank.
* Die Erstmigration verlangt noch keine persönlichen Konten in `els_mhd.users`.
  Sind solche vorhanden, stoppt sie zur gesonderten Zuordnung. Das betrifft
  beispielsweise manuell installierte frühere Auth-Experimente.

Fehlt eine Voraussetzung, nur die Vorprüfung ausführen und den Fehler klären.
Der alte `bootstrap.py` ist für diesen Stand ausdrücklich gesperrt; er würde
sonst das abgeschaffte gemeinsame Admin-Login testen. Ein nicht eingerichteter
Host-Supervisor wird nicht heimlich durch eine zweite Installation ersetzt.

## 1. Nach dem Merge einen unveränderlichen Quellstand bereitstellen

Im vorhandenen Repository-Checkout auf dem Pi:

```bash
git fetch origin main
git status --short
git rev-parse origin/main
```

Den ausgegebenen Commit mit der gemergten und erfolgreich getesteten PR
abgleichen. Nicht einen beliebigen, inzwischen weiterentwickelten Stand
installieren. Der folgende Snapshot wird aus genau diesem Commit erstellt.
Vorhandene eigene Änderungen im Checkout bleiben unangetastet.

```bash
revision=$(git rev-parse origin/main)
snapshot="/opt/els-mhd/identity-source-$revision"
sudo install -d -o root -g root -m 700 "$snapshot"
git archive "$revision" | sudo tar -x -C "$snapshot"
printf '%s\n' "$revision" | sudo tee "$snapshot/BOOTSTRAP_REVISION" >/dev/null
sudo chown -R root:root "$snapshot"
sudo chmod -R go-w "$snapshot"
```

Der Installer erwartet den geprüften Snapshot unter
`/opt/els-mhd/bootstrap-source`. Eine schon vorhandene Kopie wird **nicht
gelöscht**. Im geplanten Wartungsfenster, bevor eine Installation gestartet ist:

```bash
if sudo test -e /opt/els-mhd/bootstrap-source; then
  sudo mv /opt/els-mhd/bootstrap-source "/opt/els-mhd/bootstrap-source-before-$(date +%Y%m%d-%H%M%S)"
fi
sudo mv "$snapshot" /opt/els-mhd/bootstrap-source
```

Keinen Symlink auf einen benutzerbeschreibbaren Checkout verwenden. Der
Installer kontrolliert root-Eigentum und Schreibrechte des gesamten Snapshots.

## 2. Erst nur prüfen

```bash
sudo python3 /opt/els-mhd/bootstrap-source/deploy/agent/migrate_identity.py --hostname 10.0.0.1
```

Ohne `--apply` werden weder Container umgestellt noch Setup-Codes erzeugt.
Geprüft werden unter anderem bestehender Versionsstand, DB-Volume, aktive
Einsätze, vorhandene persönliche Konten, Backup-Laufwerk, lokale IP und Platz.
Bei Fehlern nicht Dateien/Collections löschen und nicht den Schutz umgehen.

## 3. Bewusste Installation im Wartungsfenster

Der Standardweg baut auf dem Pi und benötigt einmalig Zugriff auf die
Image-/Paketregistries. Der spätere LAN-Betrieb und Rückfall auf vorhandene
geprüfte Images benötigen diesen Zugriff nicht. Für einen vollständig offline
installierten Pi ist unten ein Weg mit vorgebauten ARM64-Images beschrieben.

```bash
sudo python3 /opt/els-mhd/bootstrap-source/deploy/agent/migrate_identity.py --hostname 10.0.0.1 --apply
```

Zur Bestätigung muss lokal `INSTALLIEREN` eingegeben werden. Der Ablauf:

1. Lokale CA und Serverzertifikat für 10.0.0.1 erzeugen beziehungsweise vorhandene
   passende rootgeschützte Zertifikate prüfen. Kein Internet-Zertifikatsdienst
   und keine dauerhaft abgeschaltete Zertifikatsprüfung.
2. Beide Images aus dem geprüften Snapshot auf dem Pi bauen und ihre tatsächlichen
   Image-IDs erfassen. Bis hier bleiben bisherige Container aktiv.
3. Host-Updatedienst stoppen, dieselbe Deploysperre erwerben, Wartung einschalten,
   API/Web stoppen und aktive Einsätze erneut prüfen. MongoDB bleibt laufen.
4. Lokales/external verschlüsseltes Backup und Wiederherstellungsprüfung über
   den vorhandenen Host-Mechanismus durchführen. Alte Konfiguration und Images
   für die Diagnose sichern; neue CA/Schlüssel ebenfalls verschlüsselt sichern.
5. Nur API/Web mit vorhandener DB-Konfiguration und vorhandenem DB-Volume
   umstellen. Dauerhaftes separates Identitätsvolume einbinden. Beide bisherigen
   DIVERA-Schlüsselgenerationen bleiben erhalten. Der CA-Privatschlüssel wird
   **nicht** in den Webcontainer gemountet.
6. HTTPS mit CA-Prüfung, API und DB prüfen. Den Identity-Mindeststand Schema 2
   dauerhaft setzen; die alte ungeschützte Version wird kein Web-Rollbackziel.
7. Einmaliges explizites Setup für die vorhandene Installation vorbereiten und
   den Setup-Code ausschließlich im lokalen Terminal anzeigen. Wartung beenden
   und den aktualisierten Host-Dienst starten. Das bisherige separate
   Updatepasswort bleibt bestehen.

Keinen dieser Befehle mit `tee` in eine ungeschützte Datei oder Chatnachricht
protokollieren: Der letzte Schritt zeigt einen einmaligen Setup-Code.

### Alternative: Images auf einem PC laden, auf dem Pi offline installieren

Nach dem Merge den erfolgreichen **Main-Lauf** „Installation and ARM64
verification“ für genau den geprüften Main-Commit öffnen. Dessen Artefakt
`els-mhd-arm64-COMMIT` herunterladen und entpacken. Es enthält
`els-mhd-arm64.tar.gz` und `els-mhd-arm64.sha256`. Nur Artefakte dieses
Repositorys, dieses Commits und eines erfolgreichen Laufs verwenden; ein
beliebiges gleichnamiges Image ist keine vertrauenswürdige Releasequelle.

Beide Dateien auf den Pi übertragen. Im entsprechenden Verzeichnis:

```bash
sha256sum -c els-mhd-arm64.sha256
sudo docker load -i els-mhd-arm64.tar.gz
sudo python3 /opt/els-mhd/bootstrap-source/deploy/agent/migrate_identity.py --hostname 10.0.0.1 --api-image els-mhd-api:arm64-test --web-image els-mhd-web:arm64-test
sudo python3 /opt/els-mhd/bootstrap-source/deploy/agent/migrate_identity.py --hostname 10.0.0.1 --api-image els-mhd-api:arm64-test --web-image els-mhd-web:arm64-test --apply
```

Der Installer kontrolliert Architektur, unveränderliche Image-ID und den
eingebetteten Quellcommit beider Images. Passt der Commit nicht zum
rootgeschützten Quellsnapshot, bricht er ab. In diesem Modus wird kein Image
gezogen oder gebaut. Die Prüfsumme sichert den Transfer; die Herkunft muss
zusätzlich anhand des GitHub-Laufs geprüft werden.

Ist auch `git fetch` auf dem Pi nicht möglich, den identischen Quellcommit
auf dem PC mit `git archive --format=tar --output=els-mhd-source.tar COMMIT`
exportieren, ebenfalls übertragen und im neuen rootgeschützten Snapshotordner
entpacken. `BOOTSTRAP_REVISION` muss genau diesen geprüften Commit enthalten.
Danach gelten Eigentumsprüfung und Snapshotwechsel aus Abschnitt 1 unverändert.
Artefakte werden 14 Tage aufbewahrt; bei Bedarf den passenden Workflow erneut
ausführen. CA-Vertrauen ist auch bei Offlineinstallation erforderlich.

## 4. Zertifikat auf den Arbeitsplätzen vertrauen

Die **öffentliche** Datei `/opt/els-mhd/config/tls/ca.crt` auf den Arbeitsplatz
übertragen und ihre Herkunft/Fingerabdruck lokal abgleichen:

```bash
sudo openssl x509 -in /opt/els-mhd/config/tls/ca.crt -noout -fingerprint -sha256
sudo cat /opt/els-mhd/config/tls/ca.crt
```

Nur den öffentlichen PEM-Zertifikatstext in eine Datei `ELS-MHD-CA.crt`
übernehmen. Unter Windows für den eigenen Benutzer über die Zertifikatsverwaltung
in „Vertrauenswürdige Stammzertifizierungsstellen“ importieren. Firefox benötigt
gegebenenfalls einen eigenen CA-Import. **Niemals `ca.key` oder `server.key`
übertragen.** Anschließend `https://10.0.0.1` ohne Zertifikatswarnung öffnen.
Die lokale CA bleibt über Neustarts/Updates erhalten; das Serverzertifikat ist
397 Tage gültig und muss vor Ablauf kontrolliert erneuert werden.

## 5. Ersteinrichtung und Datenzugriff

Über „Ersteinrichtung“ den Setup-Code eingeben und das erste persönliche
Administratorkonto anlegen. Einmaliges Erstpasswort und Recovery-Code sicher
verwahren. Danach anmelden und eigenes Passwort setzen. Administrator ist
absichtlich kein automatischer Einsatzleiter oder medizinischer Leser.

In „Einstellungen → Benutzer und globale Rechte“ die benötigten Rechte und
Eignungen bewusst vergeben. Alt-Incidents behalten sämtliche Daten, besitzen
aber keine nachträglich erfundene Ersteller-/Führungsidentität. Offenen
Alt-Incidents geeignete EL über `incidents.roles.assign` zuweisen; Archive
über begründete Freigaben erschließen. `patients.read` ersetzt dabei kein
Incident-/Archivleserecht.

Nach erfolgreichem Setup den Einrichtungsmarker als Teil der Konfigurations-
sicherung privat sichern und die regelmäßige MongoDB-/Restic-Sicherung prüfen:

```bash
sudo docker cp els-mhd-api-1:/var/lib/els/identity-state.json /opt/els-mhd/config/identity-state-backup.json
sudo chmod 600 /opt/els-mhd/config/identity-state-backup.json
sudo systemctl status els-mhd-update-agent.service --no-pager
```

Der laufende Marker bleibt im Docker-Volume; die Kopie ist nur eine Sicherung.
Ein Image-Rollback setzt DB, Konten, Audit oder Einrichtungsmarker nicht zurück.

## Bei Abbruch

Sobald Wartung eingeschaltet wurde, erfolgt kein automatischer Rückfall auf
alte ungeschützte Images. Das rootgeschützte Journal
`/opt/els-mhd/update-state/identity-migration.json` zeigt die erreichte Phase.
Nicht blind erneut starten, das Journal löschen oder Schema 1 erlauben.
DB-/Konfigurationsbackup, Image-IDs und Setupzustand lokal prüfen. Der
Vorprüfungs-/Installerprozess führt keine DB-Löschung oder DB-Rücksicherung aus.

## Was die PR prüft – und was lokal noch zu prüfen ist

GitHub prüft echte Docker-Images mit MongoDB, vertrauenswürdig geprüftem TLS,
Bootstrap, erzwungenem Passwortwechsel, RBAC, Ressourcenkapazität, Sperre,
Archivkorrektur, Wiedereröffnung und Containerneustart. Ein separater Job baut
ARM64-Images und führt API-Import sowie natives Argon2id unter ARM64-Emulation aus.

Das ersetzt nicht die Prüfung der **konkreten** Pi-Netzwerk-, USB-/Restic- und
rootgeschützten Alt-Konfiguration. Dafür ist die lokale Vorprüfung Pflicht.
Verbleibende CRA-Werkzeugkettenbefunde und Grenzen der Audit-/Mehrdokument-
Atomarität bleiben im [Sicherheitsbericht](security/review.md) dokumentiert.
