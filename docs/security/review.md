# Sicherheitsprüfung – 28. Oktober 2026

## Ergebnis

Der Branch ist ein Draft zur Prüfung. Er ersetzt die frei wählbare Browserrolle
durch serverseitige Identität und prüft Anwendungs-APIs zentral. Ein bestandener
Vertragstest oder ein Scan ohne Befund ist kein Nachweis der Produktionsreife.

Die Prüfung umfasste den tatsächlichen FastAPI-Anwendungseinstieg, direkte
Patienten-/Objekt-URLs, Session-/CSRF- und Sperrverhalten, berechtigungsabhängige
Übersichten, EL-/FüAss-/AL-/Dokumentar-/Helfer-Grenzen, Medizinleserecht,
Archivfreigaben und deren Ablauf, begründete Versionierung, Closure/Reopen,
Bootstrap/Recovery, Kontosperrung und letzte Administration. Zusätzlich wurden
die bestehenden isolierten DIVERA-, Geometrie- und Updateverträge ausgeführt.

## Abhängigkeitsscans

| Prüfung | Vor Änderungen | Nach Änderungen |
|---|---:|---:|
| Python `pip-audit` (Testumgebung einschließlich Tools) | 24 gemeldete Einträge in vier Paketen, teilweise doppelte Advisory-IDs | Keine bekannten Befunde |
| `npm audit --omit=dev` | 61: 3 kritisch, 31 hoch, 10 mittel, 17 niedrig | 35: 0 kritisch, 13 hoch, 6 mittel, 16 niedrig |

Maschinenlesbare Vorher-/Nachherberichte liegen in diesem Verzeichnis. Erfasst
wird der Zustand der jeweiligen Advisory-Dienste beim Lauf, keine Garantie
gegen unbekannte oder später veröffentlichte Schwachstellen.

FastAPI/Starlette und Motor/PyMongo wurden auf gemeinsam auflösbare korrigierte
Versionen aktualisiert und erneut getestet. Nicht benutzte frühere JWT-/bcrypt-
Bibliotheken wurden aus den Backendanforderungen entfernt. Auf dem Frontend
wurden verfügbare kompatible Updates angewendet; Zod wurde als ungenutzte direkte
Anwendungsabhängigkeit auf die korrigierte Version 4 aktualisiert. Lockfile
und anschließend Build/Tests wurden erneuert.

Verbleibende npm-Befunde stammen aus der `react-scripts`-/CRA-Werkzeugkette;
`react-scripts` ist die einzige direkt eingebundene weiterhin gemeldete
Abhängigkeit im `--omit=dev`-Bericht. CRA steht historisch unter `dependencies`,
obwohl das Docker-Laufzeitimage nur statische Dateien mit nginx ausliefert.
Das macht die Befunde **nicht automatisch harmlos**: Build-/Testumgebung und
Lieferkette bleiben betroffen. Kein erzwungenes `react-scripts@0.0.0`-„Fix“
wurde angewendet. Die Migration der Werkzeugkette und erneute vollständige
Browserregression sind vor einer uneingeschränkten Sicherheitsfreigabe offen.

## Abgewehrte Umgehungen

* Selbst gewählte localStorage-Rolle und Klarname etablieren keine Identität.
  Unbekannte Berechtigungen erlauben keine Aktion.
* Admin und Archivverwalter erhalten keine implizite medizinische oder operative
  Einsicht. Konten-/Eignungslisten und minimale Verwaltungskataloge sind davon
  getrennt.
* Geschützte Direktlinks, Aggregate, Berichte und Streams müssen zuerst die
  aktuelle serverseitige Session und den Incidentzugriff bestehen.
* Helferzugriff nutzt die aktuelle Ressourcenbindung; Wechsel/Übergabe wird
  bei jedem Zugriff neu geprüft. Selbstzuordnung und fremde Patienten sind
  gesperrt. Querverweise in Schreibdaten müssen zum Incident passen.
* Der Legacy-Admin-Passwortweg ist am produktiven Anwendungseinstieg gesperrt.
  Der zusätzliche rootgeschützte Updatepasswort-/Digestmechanismus bleibt
  bestehen. Ein ausdrücklicher Identity-Mindeststand blockiert Schema-1-Rollback.
* Abschluss/Wiedereröffnung ändern weder Patienten-/Ressourcenbindung noch
  Transport/Disposition und führen keine FMS-/DIVERA-Schreibaktion aus.
* Eine globale abschließende Person verleiht der bisherigen EL kein persönliches
  Wiedereröffnungsrecht. Alle übrigen Rollen bleiben nach Wiedereröffnung inaktiv.
* Unbegründeter Tagebuch-PATCH und physische Löschung werden verweigert.
  Korrekturen sind begründet, versioniert und für Archive auf Dokumentationsfelder
  beschränkt. Kein Vier-Augen-Zwang für medizinische Archivkorrekturen.
* Späte Pollingantworten dürfen einen gesperrten Bildschirm nicht wieder öffnen.
  Hintergrundaktivität verhindert die Zehn-Minuten-Sperre nicht.

## Offene Risiken und Releaseblocker

1. Echtes ARM64-/Raspberry-Pi-/Docker-/MongoDB- und Mehrbrowserverhalten ist hier
   nicht ausgeführt worden. Insbesondere Wiederanlauf, Stromausfall, Backup,
   lokales TLS-Vertrauen und Offline-Rollback müssen im isolierten Testsystem
   geprüft werden. Vorlagen und Operatorverfahren allein ersetzen das nicht.
2. Die große Änderung benötigt unabhängiges Code- und fachliches Matrixreview.
   Die zusätzliche Medizinfreigabe zu `incidents.all.read` ist als konservative
   Auslegung dokumentiert und fachlich zu bestätigen.
3. MongoDB-Mutexe bleiben nach Abbruch absichtlich geschlossen. Dies kann
   manuelle Betriebsintervention erfordern. Mehrdokument-Operationen besitzen
   keine Transaktionsgarantie; Start-/Ergebnis-Audit und eingebettete Revisionen
   müssen bei Unterbrechung abgeglichen werden. Ein zusätzlicher Event-Outbox-
   Ansatz beziehungsweise ein geprüfter Replica-Set-Betrieb wäre robuster.
4. Die MongoDB-Dokumentgröße begrenzt eingebettete vollständige Historien.
   Es gibt keine automatische Kürzung; bei Erreichen des Limits müssen
   Schreiboperationen geschlossen scheitern. Last-/Langzeitprüfung und eine
   atomar abgesicherte externe Historienablage stehen aus.
5. Auditdaten sind über die Anwendung nicht löschbar, jedoch gegenüber
   privilegierten DB-Operatoren nicht kryptografisch unveränderbar. Externe
   append-only Sicherung und organisatorischer Zugriffsschutz sind offen.
6. Physische Löschfunktionen bleiben gesperrt. Eine fachlich korrekte
   Stornierung mit vollständiger Historie ist noch auszuarbeiten. Der Demo-
   Schnellstart verlangt eigene EL-Eignung und Incident-Erstellungsrecht.
7. Verbleibende CRA-Lieferkettenbefunde sind nicht behoben. Es wird keine
   Freigabe zum öffentlichen oder produktiven Einsatz ausgesprochen.

Migration und sichere Rückfallgrenze sind in
[identity-migration.md](../identity-migration.md) beschrieben; Rollenmatrix und
Implementierungsumfang in [identity-rbac.md](../identity-rbac.md).
