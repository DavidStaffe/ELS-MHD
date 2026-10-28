# Persönliche Identität, Einsatzrollen und Archiv – Integrationsstand

Dieser Branch baut auf dem vollständigen Kopf der offenen Draft-PR #6
(`0d0aa78`) und dem Docker-/Update-Branch (`7a96ab1`) auf. Beide sind Vorfahren
des Integrationscommits; PR #6 wurde nicht als gemergt behandelt. Keine
Produktivinstallation oder Datenbank wurde verändert. Der frühere Branch
`Rechte-Beta` wurde geprüft, wegen abweichender JWT-/bcrypt-Architektur jedoch
nicht übernommen. Der neue PR bleibt bis zur Integrationsabnahme ein Draft.

## Sicherheitsmodell

Persönliche Benutzerkonten besitzen UUID, normalisierten Benutzernamen,
Klarname, Aktivstatus, explizite globale Rechte, Eignungen und eine
Sessiongeneration. Argon2id: 64 MiB, drei Durchläufe, Parallelität eins;
maximal zwei Passwortarbeiten gleichzeitig pro Prozess, außerhalb der
Ereignisschleife. Die Pi-Zielhardware muss dafür noch vermessen werden.

`__Host-els-session` ist ein zufälliges, serverseitiges Session-Token im
HttpOnly-/Secure-/SameSite=Strict-Cookie ohne Domainattribut. MongoDB speichert
nur seinen SHA-256-Digest, CSRF-Token, Sessiongeneration, Sperrstatus,
Ablaufzeit und Zeitpunkt echter Benutzeraktivität. Absolute Laufzeit zwölf
Stunden, Inaktivitätssperre nach zehn Minuten. Änderungen brauchen einen
CSRF-Header; browserseitige Schreibanfragen prüfen zusätzlich die Herkunft.
Keine wildcard-CORS-Freigabe mit Credentials. Nur echte Zeiger-, Tastatur-,
Touch- und Radereignisse melden Aktivität; SSE und Polling tun das nicht.

Alle registrierten Anwendungsrouten durchlaufen `core/access.py`.
Unbekannte Aktionen werden abgelehnt. Direktreferenzen werden zum Incident
aufgelöst, Querverweise auf fremde Incidents abgewiesen. Gesperrte Sessions
erhalten für geschützte Endpunkte 423; Passwortwechselpflicht verhindert
operative Nutzung mit 428. Deaktivierung und Passwortreset widerrufen
Sessions über die Generation und löschen deren Datensätze.

Die Oberfläche entfernt bei Sperre den gesamten geschützten Komponentenbaum.
Verspätete Identitätsantworten können eine lokale Sperre nicht überschreiben.
Nach Entsperrung werden Daten und Berechtigungen neu geladen. Der Sperrbildschirm
zeigt ausschließlich einen allgemeinen Ereignishinweis ohne Zähler oder IDs.
Streams prüfen vor jeder Ereignisausgabe die aktuelle Session und Berechtigung;
sie übertragen nur anonyme Aktualisierungshinweise, keine Patientenereignisse.

## Globale Einzelrechte

| Recht | Wirkung |
|---|---|
| `users.manage` | Konten auflisten/resetten/sperren; Erstellen und Rechte-/Eignungsänderungen zusätzlich nur durch Admin |
| `settings.manage` | Globale DIVERA-Einstellungen und geschützter Updatebereich |
| `incidents.create` | Erstellung mit zwingender geeigneter Initial-EL |
| `incidents.roles.assign` | EL/FüAss ernennen/ersetzen/abberufen |
| `incidents.all.read` | Incidentübergreifendes Leserecht ohne operative Rolle |
| `incidents.close` | Begründeter Abschluss ohne EL-Rolle |
| `incidents.reopen` | Begründete Wiedereröffnung |
| `archives.manage` | Individuelle Archivlesefreigaben verwalten |
| `archives.correct` | Tagebuch und allgemeine Archivdokumentation korrigieren, zusätzlich Archivleserecht nötig |
| `archives.patients.correct` | Medizinische Archivkorrektur, zusätzlich Archiv- und Medizinleserecht nötig |
| `patients.read` | Zusätzlicher medizinischer Leseumfang, ohne eigenständigen Incidentzugang und ohne Schreibrechte |
| `helpers.patients.create` | Zugeordneten Helfern neue Patientenmeldung erlauben |
| `helpers.patients.update` | Zugeordneten Helfern beschränkte Bearbeitung aktuell betreuter Patienten erlauben |

`patients.read` ersetzt kein Incident-/Archivleserecht. `incidents.all.read`
verleiht allein keine medizinische Sonderfreigabe für Personen ohne passende
Einsatzrolle. Dies ist eine bewusst strenge Auslegung; die Produktabnahme
muss diese Kombination ausdrücklich bestätigen. Der Ersteller behält den
vereinbarten vollständigen Leseumfang einschließlich medizinischer Daten.

Admin ist kein operativer Superuser. Ein Admin benötigt ebenfalls separate
Incident- und Medizinleserechte. Archivverwaltung darf Identifikatoren/Titel
zur Freigabeverwaltung sehen, ohne Archivinhalt zu erhalten. Benutzer-IDs und
Eignungen in Ernennungslisten sind Verwaltungsdaten, keine Lage-/Patientendaten.
Ein Administratorkonto muss `users.manage` behalten.

## Aktive Einsatzrollen

| Rolle | Lesen | Schreiben / Ernennen |
|---|---|---|
| EL | Incidentweit einschließlich Patienten | Operativ; allein Ressourcenfreigabe; AL/Dokumentar aus geeigneten Konten; bestehende FüAss organisatorisch umhängen |
| FüAss | Incidentweit einschließlich Patienten, unabhängig von Unterstützung EL/AL | Operativ und Dokumentation; Helferressourcen zuweisen; keine eigene Ernennung EL/FüAss; keine Ressourcenfreigabe |
| AL | Incidentweit einschließlich Patienten | Nur eigener Abschnitt; keine Helferzuordnung und keine Ressourcenfreigabe |
| Dokumentar | Gesamtlage und Tagebuch; Medizin nur mit `patients.read` | Meldungen erstellen, nur eigene Tagebucheinträge korrigieren; keine Disposition/Führungsrechte |
| Helfer | Eigene Ressource und deren aktuell gebundener Patient | Nur ausdrücklich freigegebene Patientenfelder/-meldungen; keine Selbstzuordnung, Disposition oder Führung |

Pro Benutzer und Incident enthält `assignments` genau einen Eintrag. Eine
EL, maximal zwei zentrale FüAss, je Abschnitt maximal eine AL und eine FüAss.
EL/FüAss/AL/Dokumentar verlangen vorherige globale Eignung. Eine Eignung allein
öffnet keinen Incident. Unterschiedliche Incidents dürfen unterschiedliche
Rollen desselben Kontos haben. Ernennung und organisatorische FüAss-Zuordnung
sind getrennte Vorgänge. Der bisherige Rollenpicker und seine localStorage-
Identität werden entfernt; unbekannte UI-Aktionen werden ebenfalls abgelehnt.

Nichtzugeordnete Konten erhalten für offene Incidents nur ID, Titel, groben
Status und eine Einschränkungsmarkierung. Der Ersteller ist getrennt von EL
gespeichert und erhält keine impliziten operativen Schreibrechte.

## Dokumentation und Archiv

Tagebucheinträge sind zentral (`abschnitt_id = null`) oder genau einem
existierenden Abschnitt zugeordnet. Identität und damalige Rolle werden aus
der Session abgeleitet. Stille Löschungen und der alte unbegründete PATCH-
Korrekturpfad werden am zentralen Gate verweigert. Korrekturen laufen über
`/api/incidents/{id}/corrections/{messages|patients|incidents}/{record_id}`.

Jede Korrektur verlangt eine nichtleere Begründung und speichert vor/nach,
Benutzer-ID, Benutzer-/Klarname, damalige Rolle und UTC-Zeit im selben
Datensatz wie die neue Revision. Compare-and-swap verhindert verlorene
Revisionen. Sichtbare Markierung `corrected`/„korrigiert“. EL/FüAss korrigieren
alle Tagebucheinträge, AL eigene Abschnitte, Dokumentar eigene Einträge.
Nur EL/FüAss dürfen die organisatorische Abschnittszuordnung korrigieren.
Historische Einträge ohne sichere Urheber-ID werden keinem heutigen
Dokumentar automatisch zugeschrieben.

Abschluss hat einen eigenen begründeten Endpunkt samt Vorschau, expliziter
Bestätigung offener Vorgänge und erneuter Backendprüfung. Patienten,
Transporte, Ressourcenbindungen und offene Dispositionen werden als Snapshot
festgehalten. Es werden ausschließlich Incidentstatus und Rollenzuordnungen
umgestellt. Kein automatischer Abschluss, keine Freigabe, keine FMS-Schreib-
oder DIVERA-Anfrage durch Abschluss/Wiedereröffnung.

Nach Abschluss öffnen nur Ersteller, `incidents.all.read` oder eine explizite
nicht abgelaufene Archivfreigabe das Archiv. Ehemalige Beteiligung genügt nicht.
Freigaben gelten standardmäßig 30 Tage, werden bei jedem Zugriff serverseitig
auf Ablauf/Widerruf geprüft und benötigen einen Grund.

Persönliche Wiedereröffnung ist nur für dieselbe Benutzer-ID zulässig, die
als aktive EL selbst abgeschlossen hat. Andernfalls braucht es das globale
Wiedereröffnungsrecht. Bisherige EL wird nur aktiv/geeignet reaktiviert;
Ersatz-EL braucht `incidents.roles.assign`. Andere Rollen bleiben inaktiv.
Eine minimale Wiedereröffnungsanzeige verleiht noch kein Archivleserecht.

Archivkorrekturen sind Einzelkorrekturen ohne Vier-Augen-Prinzip, ohne
Wiedereröffnung und ohne operative Feldänderungen. Backend-Feldlisten sperren
Status, Ressourcenbindung, Transport und Disposition. Die Oberfläche bietet
getrennte allgemeine und medizinische Korrekturen mit Historie.

## Parallelität und Audit

Incidentänderungen werden durch einen MongoDB-Mutex serialisiert und danach
erneut autorisiert. Benutzeränderung und Ernennung derselben Person teilen
einen Benutzermutex. Rollenwechsel/Abschluss verwenden zusätzlich eine
Incidentrevision und eingebettete unveränderbare Historie. Korrekturen haben
eigene Revisionen. Dies funktioniert mit MongoDB standalone ohne Transaktionen.

Mutexe haben bewusst keinen automatischen Ablauf. Nach Prozessabbruch bleibt
das betroffene Objekt sicher gesperrt. Betreiber müssen den unterbrochenen
Vorgang untersuchen und erst dann genau dessen `identity_locks`-Eintrag
entfernen. Nicht pauschal alle Sperren löschen. Dieser Verfügbarkeitsnachteil
ist vor Produktivbetrieb durch echte Crash-/Neustarttests zu bewerten.

`security_audit` enthält Anmeldung/Fehler, Kontenänderung, Reset, Sperre,
Wiederherstellung und autorisierte Schreibanfragen samt Ergebnis. Es existiert
keine Änderungs-/Lösch-API für Audit- oder Versionsdaten. Datenbankoperatoren
bleiben technisch privilegiert; externe unveränderbare Auditablage ist noch
nicht eingerichtet. Mehrdokument-Operationen und Audit-Finalisierung sind
nicht transaktional. Unterbrechungen müssen anhand Start-/Ergebnisereignissen,
Versionen und Sperren geprüft werden. Kein Compliance-/Manipulationsschutz-
Zertifikat wird behauptet.

## Bekannte Abnahmegrenzen

* Die Tests verwenden für neue API-Verträge Mongo-kompatible isolierte
  Testdaten, kein echtes MongoDB auf ARM. Docker, lokales CA-Vertrauen,
  Stromausfall, Browserdruck/-export und lange SSE-Verbindungen müssen im
  Raspberry-Pi-Testsystem abgenommen werden.
* Automatische Ressourcenfreigaben durch Transportabschluss werden unterbunden.
  Die Ein-Patienten-Bindung aus PR #6 bleibt bestehen. MANV mit zwei Patienten
  ist kein aktivierter Betriebsmodus dieses Branches und benötigt eine eigene
  bewusste Implementierung/Abnahme.
* Der Demo-Schnellstart verlangt `incidents.create` und eine eigene EL-Eignung;
  seine eigene Initial-EL wird vor dem Seed dauerhaft gesetzt. Historische
  physische Lösch-Endpunkte bleiben gesperrt; eine fachliche Stornierung mit
  vollständiger Historie ist separat zu gestalten.
* Die globalen Textfelder dürfen nicht als Ersatz für medizinische Dokumentation
  verwendet werden. Freitext kann nicht automatisch zuverlässig klassifiziert
  werden. Die medizinischen APIs sind separat gesichert.
* Vollständige adversariale Browser-/Penetrationstests und unabhängiges Review
  stehen aus. Erfolgreiche Builds/Vertragstests sind keine Produktionsfreigabe.

Siehe [Migrations- und Rückfallverfahren](identity-migration.md).
