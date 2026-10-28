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

## Aktueller Implementierungsstand
- Die globale Einstellungsseite unterstützt Administratoranmeldung, verdeckte Key-Eingabe, Verbindungstest, geprüfte Speicherung und Intervalländerungen.
- Serverseitige Anmeldung mit scrypt-Passworthash, kurzlebigen widerrufbaren Bearer-Sitzungen und datenbankgestützter Begrenzung der Anmeldeversuche. Verwaltungsoperationen werden ohne Geheimnisse protokolliert.
- Fernet-verschlüsselte Konfiguration in MongoDB; Verschlüsselungsschlüssel separat als Secret-Datei. Migration eines vorhandenen Umgebungskeys und dynamische Übernahme aller Änderungen.
- Gemeinsamer Scheduler mit installationsweiter MongoDB-Lease, Snapshot-Verteilung, festem globalen Intervall und persistierter Wiederholungsfrist. Manuelle Abrufe und Fahrzeugauswahl nutzen denselben Datenbestand.
- 5 Sekunden bleiben serverseitig und in der Auswahl gesperrt. Für diese Abruffrequenz liegt keine bestätigte Freigabe vor.
- Die vorhandene Update-/Rollback-Oberfläche ist integriert. Ausführung bleibt bis zur Einrichtung und Prüfung des geschützten Host-Dienstes gesperrt; die Änderungsendpunkte verlangen bereits echte Administratorauthentifizierung.

## Bereitstellung und Prüfung
Die Einzelheiten zu Einrichtung, Verschlüsselung, Betriebsverhalten und Offline-Tests stehen in [divera-global-settings.md](divera-global-settings.md).
Vor Produktivfreigabe sind Tests mit einer DIVERA-Testeinheit, echten Container-Secrets und MongoDB sowie ein kontrollierter Neustart erforderlich. Es erfolgt kein automatisches Deployment auf den Pi.
