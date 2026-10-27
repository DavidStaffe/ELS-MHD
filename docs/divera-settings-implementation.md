# Verbindliche DIVERA-24/7-Anforderungen und Umsetzungsstand

Quelle: Vereinbarungen aus dem separaten ELS-MHD-Projektchat, vom Nutzer hier bereitgestellt.

## Fachliche Festlegungen
- Zentrale Einstellungsseite `/einstellungen`, unabhängig vom aktiven Incident; DIVERA und System-Updates als getrennte Bereiche.
- Genau ein globaler DIVERA API-Key für die Installation, gültig für sämtliche Incidents. Der Key darf im Frontend nie im Klartext angezeigt werden.
- Admin kann neuen Key verdeckt eingeben und gegen echte Fahrzeugabfrage testen, **bevor** der alte überschrieben wird. Ungültiger oder nicht prüfbarer Key darf alte Konfiguration nicht verändern.
- Validierten Key dauerhaft und verschlüsselt im Backend verwahren; dedizierten Verschlüsselungsschlüssel außerhalb von Git und Datenbank bereithalten. Altwert aus Umgebungsvariable bei Migration berücksichtigen.
- Neuen Key sofort ohne App- oder Pi-Neustart aktivieren, und aktive Abfrage läuft damit weiter; Neustart behält Key.
- Intervall als feste Auswahl 5, 10, 20, 30, 60, 120, 300 Sekunden; Standard 30 Sekunden. 5 Sekunden erst produktiv aktivieren, wenn DIVERA-Ratenlimit verifiziert ist.
- Eine zentrale DIVERA-Abfrage pro Installation, deren Ergebnis auf verknüpfte Ressourcen aller dafür aktivierten, nicht abgeschlossenen Incidents verteilt wird. Verknüpfungen bleiben incident-spezifisch.
- Abfrage nur, wenn mindestens ein Incident sie benötigt; Synchronisierungsstatus je Incident persistent; nach Neustart fortsetzen.
- Keine überlappenden Fetches; nach Fehlern begrenzter Retry mit Backoff, Unterscheidung zwischen Aktivierung und erfolgreichem Abruf.
- Lagekarte bleibt operational: Pollingstatus, letzter Abruf, Anzahl Verknüpfungen, manuelle Synchronisation, Start/Stopp. Kein Key-Eingabefeld auf Lagekarte.
- Administratorauthentifizierung muss serverseitig verifiziert werden, nicht nur Frontend-Rollenauswahl.

## Aktueller Implementierungsstand (Phase 1)
- `frontend/src/pages/EinstellungenPage.jsx`: read-only zentrale Anzeige für konfigurierte DIVERA-Anbindung, Intervallwerte und Link zur Updateverwaltung.
- Route und Navigation auf `/einstellungen` vorhanden.
- Schreiben/Prüfen von API-Keys und Ändern des Intervalls **noch bewusst gesperrt**, damit keine ungeschützte API entsteht.
- Legacy-Backend `backend/services/divera.py` liest derzeit Key und Intervall beim Import und nutzt pro Incident einen eigenen Polling-Task; die gewünschte zentrale Polling-Architektur ist **noch nicht umgesetzt**.

## Nächste Implementierungsschritte
1. Gemeinsame, echte Admin-Anmeldung/Step-up-Prüfung für DIVERA-Key und Updates mit Begrenzung von Fehlversuchen, Auditprotokoll, CSRF-Schutz je Sessionmodell.
2. Verschlüsselte, persistente Konfiguration mit Key-Rotation und Laufzeit-Reload; Fehlerantworten ohne Secret-Leaks.
3. Zentraler, serialized Fetch mit Incident-Verteilung und dynamischem Intervall, Persistenz, Backoff und Tests.
4. Aktivierung der Passwort- und Intervall-Controls, Integrationstests (Key ungültig, DIVERA offline, Neustart, mehrere Incidents und Abfragefrequenz).
5. Sichere Freigabe über kontrolliertes Deployment und Rückrolltest; bis dahin nur synthetische Daten.
