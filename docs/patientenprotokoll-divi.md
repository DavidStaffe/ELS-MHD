# Patientenprotokoll (DIVI-orientiert, ohne Klardaten)

## Umfang

Erweiterung der vorhandenen Patientenakte, **kein neuer Patientendatensatz**.
Referenz: \`7.1_DIVI_NFEP_Protokoll.pdf\`, Seite 1 (Befund, Maßnahmen,
Verlauf, Transport) und Seite 2 (xABCDE, SAMPLER(S), NEWS2, BEFAST, SINNHAFT).
Das PDF wird **nicht** als Original-DIVI-Dokument nachgebildet.

Im Patientendetail erscheint das Protokoll oberhalb des normalen
Disposition-/Transport-Workflows. Die Kennung (z.B. P-0001) bleibt der
Schlüssel; Verknüpfungen zu Sichtung, Abschnitt, Bett und Transport
bleiben unverändert.

## Datenschutz und Berechtigungen

- **Zulässige persönliche Stammdaten:** \`geburtsdatum\`, \`geschlecht\`.
- Kein Datenmodell für Patientenname, Adresse, Krankenkasse,
  Versichertennummer, Telefonnummer, Unterschrift oder Zeugenklardaten.
- Medizinische Freitextfelder können unerlaubte personenbezogene
  Angaben enthalten. Die Oberfläche warnt; eine technische, vollständige
  Freitext-Anonymisierung ist ausdrücklich **nicht** zugesichert.
- Geburtsdatum + medizinischer Kontext erlauben unter Umständen
  Reidentifikation. Das Verfahren ist datensparsam/pseudonymisiert,
  **nicht garantiert anonym** nach DSGVO.
- Route: \`PATCH /api/patients/{patient_id}/protocol\`.
- Nutzt den bestehenden globalen Default-Deny-Zugriffsgate. EL, FueAss,
  berechtigte AL sowie ausdrücklich berechtigte Helfer für das eigene
  gebundene Patientenobjekt; die Archivsicht bleibt unverändert.
- Kein Editieren eines abgeschlossenen Incidents. Ergänzungen nach
  *Patientenfallabschluss* innerhalb eines operativen Incidents benötigen
  mindestens 10 Zeichen Begründung.

## Protokollfelder

| Abschnitt | Inhalt |
| --- | --- |
| stammdaten | Geburtsdatum, Geschlecht |
| anamnese | Leitsymptom, SAMPLER(S) |
| erstbefund | xABCDE, BEFAST |
| verlauf | Reihen von Uhrzeit, RR, Puls, AF, SpO2, Temperatur, GCS, BZ, NRS, O2-Gabe, SpO2-Skala |
| massnahmen | Zeit, Maßnahmen-/Medikamententyp, Inhalt, Dosis, Weg, Wirkung |
| uebergabe | Art, Zeit, Ziel, empfangende **Funktion**, SINNHAFT, Verweigerungsvermerk |

NEWS2 wird **nicht** automatisch berechnet. Das PDF enthält auch
Scores und eine unterschriebene Transportverweigerung; die erste Version
nutzt diese ausschließlich als Erhebungs-/Übergabehilfen. Es gibt
weder digitale Signatur noch die Behauptung einer rechtssicheren
Transportverweigerung.

## Speicherung und Konflikte

Der gesamte aktuelle Stand liegt unter \`patients.protokoll\` mit
\`version\` und \`updated_at\`. Jede Änderung schreibt atomar eine
Append-only-Protokollversion innerhalb des Patientendokuments unter
\`patients.protokoll_history\` mit:
\`version\`, \`at\`, \`actor_id\`, \`section\`, \`before\`, \`after\`,
\`reason\`. Zusätzlich: nicht-medizinischer Sicherheits-Auditeintrag
und anonymisierte SSE-Invalidierung.

Die UI speichert **abschnittsweise**, nicht jede Tastatureingabe.
Optimistisches Locking (\`expected_version\`) ergibt HTTP 409 bei
konkurrierender Änderung. Dies verhindert stilles Überschreiben; die
Benutzerin/der Benutzer muss neu laden und die Änderung prüfen.
Durch Einbettung bleibt die Dokumentation Bestandteil der bestehenden
Patienten-Archiv- und Exportdaten.

## Tests und Abnahme

Unit-Tests in \`backend/tests/test_patient_protocol_validation.py\`.
Vor produktivem Update im Staging prüfen:

1. Protokoll für einen aktiven Patienten öffnen und alle sechs Tabs speichern.
2. Nach Neuladen: Inhalte und Versionshistorie vollständig erhalten.
3. In zwei Browsern dieselbe Revision ändern: zweite Speicherung muss 409 melden.
4. Als unberechtigter Nutzer und als Helfer mit fremdem Patienten Zugriff ablehnen.
5. Keine zusätzlichen Klartext-Stammdaten über API zulassen (422).
6. Geburtsdatum in der Zukunft, Vitalwert außerhalb plausibler Grenzen ablehnen.
7. Archivierte Incidents schreibgeschützt; nach Patientenabschluss
   begründete Korrektur nur solange Incident noch operativ.
8. Transport/Abschluss weiterhin über die bisherigen Module disponieren.
9. Kein Patientennamen-/Krankenkassenfeld im Form oder API.

**Offene technische Abnahme:** E2E-Rollenprüfung, echte MongoDB-Integration
und Frontend-Produktionsbuild müssen in einer testbaren ELS-MHD-Umgebung
ausgeführt werden. Dieses Feature ist bis dahin ein Review-/Staging-Kandidat.

**Nächste Ausbaustufe:** getrennte langfristige Historienablage und
medizinische Archivkorrektur über das bestehende freigabepflichtige
Archivkorrekturverfahren; außerdem optional strukturierter NEWS2-Score
mit Skala-2-Indikationsprüfung und klinischer Freigabe.
