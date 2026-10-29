# Manuelle Veröffentlichung eines Schema-2-Updates

Der Workflow **Publish reviewed schema-2 images** veröffentlicht ausschließlich
bereits CI-geprüfte ARM64-Images nach GHCR. Er verbindet sich nicht mit einem Pi,
ändert keine Installation und veröffentlicht kein GitHub Release. Insbesondere
bleiben Runtime-Compose, MongoDB-, Identitäts- und CA-Volumes unverändert.

## Voraussetzungen und bewusster Start

1. Diesen Workflow zuerst nach `main` mergen. Danach die drei **push**-Prüfungen
   des gewünschten exakten main-Commits abwarten: Update management contracts,
   Certificate onboarding, Installation and ARM64 verification. Grüne PR-Prüfungen
   allein reichen nicht. Das ARM64-Artefakt ist derzeit 14 Tage verfügbar.
2. Schema-2-Kompatibilität fachlich prüfen: persönliche Zugriffskontrolle erhalten,
   keine Daten-/Hostmigration, Rückkehr zu den bisherigen Images ohne DB-Restore
   möglich. Die Schema-Zahl ist eine Betreiberzusicherung, kein Codebeweis.
3. GitHub → Actions → **Publish reviewed schema-2 images** → **Run workflow**.
   Branch `main`, eine neue Versionskennung (1–64 Zeichen aus Buchstaben, Ziffern,
   Punkt, Unterstrich, Bindestrich; erstes Zeichen Buchstabe/Ziffer) und den
   vollständigen 40-stelligen Commit-SHA angeben. Schema-2-Prüfung bestätigen.
   Beispielversion: `v2026.10.29-incident.1`.

Der erwartete SHA muss dem beim Start festgehaltenen main-Commit entsprechen.
Andere Branches werden nicht veröffentlicht. Ein neuer main-Stand während der
Ausführung ändert den ausgewählten Commit nicht. Ein ausstehender/fehlgeschlagener
neuerer CI-Lauf für denselben Commit wird nicht durch einen älteren grünen Lauf
ersetzt. Abgelaufene Artefakte verlangen einen erneuten erfolgreichen CI-Lauf.

## Was geprüft und veröffentlicht wird

- Das exakt zugehörige Installations-Artefakt herunterladen und dessen innere
  SHA-256-Prüfsumme prüfen; nicht aus fremden Runs oder PR-Artefakten auswählen.
- ARM64-Images laden und Argon2id/API-Import sowie `nginx -t` nochmals testen.
- Linux/ARM64 und OCI-Revisionslabel beider Images gegen den main-SHA prüfen.
- Beide Images mit temporärem `GITHUB_TOKEN` (`packages: write`) veröffentlichen.
  Tags enthalten Version, Run-ID und Versuch; keine beweglichen `latest`-Tags.
- Beide Registry-Digests zurückladen und Architektur, Commit und Image-ID mit den
  getesteten Images vergleichen. Erst danach eine Freigabedatei erzeugen.

Ergebnis ist das Actions-Artefakt `schema2-release-RUNID-VERSUCH` (90 Tage):

* `approved-release.json`: exakt die fünf vom Agent akzeptierten Felder,
  `schema: 2`, Version, Hinweise und feste API/Web-GHCR-Digests.
* `provenance.json`: Quellcommit, geprüfte Image-IDs, CI-Run und Veröffentlichung.
* `SHA256SUMS`: Prüfsummen dieser Dateien.

Dies ist **keine kryptografische Release-Signatur**. Vertrauen entsteht aus dem
geprüften main-Commit, GitHub-Workflow/Artefakt, Digestvergleich und der bewussten
lokalen rootgeschützten Freigabe. Prüfsummen nicht als Signaturen bezeichnen.

Scheitert die Veröffentlichung nach dem ersten Image, kann ein einzelnes Image
in GHCR verbleiben. Es entsteht keine neue Freigabedatei; nichts wird installiert.
Fehler beheben und erneut manuell starten. Keine Teilfreigabe erstellen. Bei
bereits vorhandenen Packages muss das Repository in deren Actions-Zugriffsrechten
Schreibzugriff besitzen; keine zusätzlichen Tokens ins Repository einchecken.

## Separate Freigabe und gemeinsamer Pi-Test

Neu angelegte GHCR-Pakete sind standardmäßig privat. Auf dem Pi den lesenden
Registryzugriff für root unter `/opt/els-mhd/config/docker-client` einrichten bzw.
prüfen, bevor ein Update angefordert wird. Ein erforderliches Registry-Token nur
lokal mit `docker login --password-stdin`/interaktiver Anmeldung verwenden, niemals
hier im Chat oder als Befehlsargument weitergeben. Keine automatische Änderung
der Paketsichtbarkeit und keine Docker-Anmeldung mit dem kurzlebigen CI-Token.

Vor lokaler Freigabe Commit, beide Digests, Herkunft, Prüfsummen, Images und
Schema-2-Rollbackziel prüfen. Freigabedatei geschützt zum Pi übertragen und erst
nach Prüfung rootgeschützt (root:root, 0600) atomar als
`/opt/els-mhd/config/approved-release.json` übernehmen. Dieser Workflow erledigt
diesen Schritt ausdrücklich nicht. Bestehende Host-/Identitätskonfiguration nicht
ersetzen und den Agenten zur Statusabfrage nicht stoppen.

Danach dem [Lifecycle-Abnahmeplan](incident-lifecycle-release.md) folgen:
kein aktiver Einsatz, Backup prüfen, Ausgangsdigests festhalten, bewusstes Update,
zwei Arbeitsplätze und Fachregeln prüfen, Image-Rollback mit erhaltenen neuen Daten,
erneutes Update und Pi-Neustart. Medizinische Daten niemals automatisch zurücksetzen.
Der erste echte GHCR-Publikationslauf ist erst nach Merge manuell möglich; reine
PR-Tests weisen noch keinen erfolgreichen Registry-Push oder Pi-Deploy nach.

Referenzen: [GitHub-Publishing](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images),
[GHCR-Zugriff und Sichtbarkeit](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).
