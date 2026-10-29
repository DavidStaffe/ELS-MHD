# Lokale Zertifikats-Einrichtung (Schema 2)

## Architektur und Vertrauensgrenze

`http://10.0.0.1:8081/` ist ausschließlich ein öffentlicher Bootstrap-Endpunkt.
Keine Weiterleitung zu API/Web, keine Datenbank, Sessions, Cookies, Eingabemasken,
Telemetrie, externen Fonts, Skripte oder Internet-Ressourcen. Vier exakt erlaubte
GET/HEAD-Pfade: `/`, `/ca.crt`, `/qr.svg`, `/fingerprint.txt`. Der Download ist ein
kanonisches DER-X.509-Zertifikat; der SHA-256 bezieht sich auf DER, nicht auf die
PEM-Dateibytes. Private Schlüssel, PEM-Bundles und Nicht-CA-Zertifikate werden
abgelehnt. Der QR-Code enthält nur die feste Einrichtungsadresse.

HTTP authentifiziert weder Seite noch Fingerabdruck. Deshalb den Fingerabdruck
über einen **unabhängigen vertrauenswürdigen Kanal** vergleichen, beispielsweise
direkt am Pi-Bildschirm oder als persönlich übergebenen Ausdruck. Weder ein
Screenshot dieser HTTP-Seite noch ihr QR-Code ersetzt diese Prüfung.

Der systemd-Socket bindet ausschließlich `10.0.0.1:8081`, zusätzlich an `wlan0`,
ohne FreeBind. Vor Installation muss dort tatsächlich `10.0.0.1/24` liegen.
Bei anderer Hotspot-Schnittstelle ist eine separat geprüfte Anpassung erforderlich;
kein Fallback auf `0.0.0.0`. Hotspot-Routing/Firewall darf eingehenden Verkehr aus
anderen Netzen nicht auf dieses Interface umleiten. Der Dienst beschränkt IP-Verkehr
zusätzlich auf `10.0.0.0/24`. Ein Netzwerktest von einem anderen Interface ist Pflicht.

Der unprivilegierte DynamicUser-Prozess erhält über systemd LoadCredential nur
`/opt/els-mhd/config/tls/ca.crt`. `/opt`, Home-Verzeichnisse und Docker-Socket sind
gesperrt; keine privaten TLS-Schlüssel werden gemountet. Die CA wird beim
Dienststart geprüft und für dessen Laufzeit im Speicher gehalten. Nach CA-Wechsel
den Dienst neu starten und Fingerabdruck/Ausdruck sowie HTTPS-Kette neu prüfen.
HTTP ist keine Anmeldeseite und darf nicht für produktive Daten verwendet werden.

## Lebenszyklus

Geprüfter Stand: `deploy/agent/agent.py` nutzt `runtime/compose.yaml` und prüft
dessen Hash gegen `update-state/bundle.json`; `active.json` fixiert API/Web-Images.
`Engine.install()` und Recovery/Rollback erstellen ausschließlich API/Web neu.
Die Einrichtungsseite läuft daher als eigener Hostdienst, unabhängig von den drei
Containern api/web/db. Das eingefrorene Compose-Bundle, sein Hash, Releaseschema,
Images und Datenvolumes werden **nicht verändert**. Auch der Stackdienst kann
weiter seine bisherige Schema-2-Runtime starten. Der aktivierte Socket überlebt
Neustarts; bei fehlendem Hotspot gibt es keinen breiteren Ersatzlistener.

Hostkomponenten gehören nicht zum API/Web-Releasevertrag: Installation und spätere
Änderungen dieser Seite erfolgen explizit aus einem geprüften Host-Snapshot,
nicht durch einen gewöhnlichen Web-Update-Lauf. App-Rollback lässt sie unverändert.
Für einen Hostumzug müssen die beiden Units und `/usr/local/lib/els-mhd-onboarding`
zusätzlich zum bisherigen Host-Backup gesichert bzw. aus dem geprüften Commit
rekonstruiert werden. Die bestehenden Installer/Migrationen werden nicht erneut
ausgeführt. Kein automatischer Hostinstaller im Container oder Update-Agenten.

## Installation nach Merge – bewusst separat vom produktiven Update

1. ARM64/Raspberry Pi OS mit systemd LoadCredential und BindToDevice prüfen.
   Benötigte Betriebssystempakete aus den vertrauenswürdigen Distributionsquellen:
   `python3`, `python3-cryptography`, `python3-qrcode`, `openssl`, `iproute2`,
   `util-linux`. Vorab auf einem Test-Pi installieren und die Units dort prüfen.
2. Den gemergten Commit in einen separaten root-eigenen, nicht gruppen-/weltweit
   schreibbaren Quell-Snapshot unter root-eigenen Elternverzeichnissen übernehmen.
   Alle Dateien dieses Snapshots müssen root gehören; keine Symlinks. Keine
   Secrets in den Snapshot kopieren. Commit-ID prüfen und dokumentieren.
3. Vorhandene Onboarding-Units und Programmdateien (falls vorhanden) separat
   sichern. Schema 2, unveränderten Runtime-Hash, abgeschlossene Transaktion,
   Hotspot und belegten Port prüfen. Das Installationsskript prüft diese Grenzen
   nochmals und verwendet dieselbe Deploy-Sperre wie der Agent. Bei Abbruch keine
   aktive Update-Transaktion reparieren oder Sperren löschen.
4. Aus dem geprüften Snapshot lokal ausführen:
   `sudo sh deploy/onboarding/install.sh --apply`.
   Es verändert nur die Onboarding-Programmdateien und Units; weder Docker noch
   Datenbank noch Anwendungsdienst werden gestartet oder neu erstellt.
5. Unabhängigen Fingerabdruck direkt über die vertrauenswürdige Pi-Konsole bilden:

   ```sh
   sudo openssl x509 -in /opt/els-mhd/config/tls/ca.crt -noout -fingerprint -sha256
   ```

   Diesen Wert persönlich ausgeben, beispielsweise zusammen mit dem QR-Code auf
   einem kontrolliert erstellten Ausdruck. Kein privater Schlüssel auf den Ausdruck.

## Abnahme und risikoarmer Rollout

Zuerst Test-Pi mit synthetischer CA und Schema-2-Fixture, dann ein kontrolliertes
Wartungsfenster. Auf dem echten Pi keine Testpatienten oder DB-Schreibtests.
Vorher/nachher Runtime-Hash und Container-IDs vergleichen: müssen gleich bleiben.

* `systemctl status els-mhd-onboarding.socket` und nach erstem Abruf auch `.service`;
  `ss -ltnp` darf für Port 8081 nur `10.0.0.1` zeigen.
* Im Hotspot Seite, QR-Scan auf einem zweiten Gerät und Download offline testen.
  Download-Fingerprint unabhängig vergleichen, danach auf einem Testgerät installieren.
* iOS/iPadOS, Android und Windows/Chromium jeweils tatsächlich prüfen; Menütexte
  und Richtlinien können variieren. HTTPS muss ohne Ausnahme/Warnung funktionieren.
* `/api/meta`, `/login`, `/ca.key`, Traversal, fremder Host und POST dürfen keine
  produktiven Inhalte liefern; kein Set-Cookie/CORS. Von Ethernet/anderem WLAN
  darf 8081 nicht erreichbar sein, auch nicht durch Routing zur Hotspot-IP.
* Test-Pi neu starten: Hotspot, Onboarding und bisheriger Stack müssen starten.
  Erst auf dem Test-Pi einen normalen Schema-2-App-Update-/Rollback-Zyklus prüfen:
  Onboarding bleibt unverändert; Runtime-Hash bleibt gültig. Produktiver Update-Test
  erfolgt erst nach Merge gemeinsam mit dem Nutzer.
* Fehlende/abgelaufene CA: Dienst muss geschlossen fehlschlagen, keinen Ersatzinhalt
  oder privaten Schlüssel liefern. Bei Socket-Startfehler Hotspot herstellen und
  `systemctl restart els-mhd-onboarding.socket` ausführen; keinen Wildcard-Bind setzen.

## Rollback ausschließlich der Einrichtung

`sudo systemctl disable --now els-mhd-onboarding.socket` und
`sudo systemctl stop els-mhd-onboarding.service`. Damit ist HTTP geschlossen.
Bei einer Aktualisierung gesicherte Onboarding-Dateien/Units wiederherstellen,
`systemctl daemon-reload`, anschließend Socket nur nach Prüfung erneut aktivieren.
App, CA, private Schlüssel, Runtime-Bundle, Agent und Datenvolumes unverändert
lassen. Clientseitiges CA-Vertrauen bei Bedarf separat anhand des Fingerabdrucks
entfernen; es wird durch Abschalten der Seite nicht widerrufen.

## Automatisierte lokale Prüfung

`python -m pytest backend/tests/test_certificate_onboarding.py` benötigt pytest,
cryptography und qrcode (lokal mit qrcode 8.2 geprüft). Tests verwenden nur
synthetische Zertifikate und einen zufälligen Loopback-Port, keine Produktion.
ARM64/systemd-, Firewall-, Reboot- und echte Clientprüfungen bleiben explizite
Abnahmeschritte; Windows-Unit-Tests ersetzen sie nicht.

Anleitungen abgeglichen mit [Apple](https://support.apple.com/en-ca/102390),
[Android](https://support.google.com/pixelphone/answer/2844832),
[Chrome Zertifikatsverwaltung](https://support.google.com/chrome/answer/10468685)
und [Chromium lokale Vertrauensentscheidungen](https://chromium.googlesource.com/chromium/src/+/main/net/data/ssl/chrome_root_store/faq.md).
