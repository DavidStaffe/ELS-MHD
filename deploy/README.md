# ELS-MHD Docker development smoke test (not production)

Für die separate öffentliche CA-Einrichtung am Hotspot siehe
[Zertifikats-Onboarding mit QR-Code](../docs/certificate-onboarding.md).

**Aktueller persönlicher Login und Installation für 10.0.0.1:**
Die folgende historische Smoke-Anleitung ist keine Installationsanleitung für
den abgesicherten Stand. Verwende [den geprüften Migrationsweg](../docs/installation-10.0.0.1.md).
Der alte Shared-Admin-Bootstrap ist für Identity-Images gesperrt. Die API besitzt
in diesem Stand serverseitige Authentifizierung; Secure-Cookies benötigen HTTPS.
For the opt-in secured web update supervisor, installation, release approval and recovery, see [System & Updates](../docs/web-update-management.md). After adopting it, use its pinned start path rather than the build commands below.
The stack binds the web UI to **127.0.0.1:8080 only**; do not expose it to the LAN. The API currently lacks server-side authentication; use dummy/test data only.

On the Raspberry Pi in the repository's feature branch:

```bash
sudo install -d -m 700 /opt/els-mhd/config
sudo sh -c 'printf "MONGO_PASSWORD=%s\n" "$(openssl rand -hex 32)" > /opt/els-mhd/config/docker.env'
sudo chmod 600 /opt/els-mhd/config/docker.env
sudo docker compose --env-file /opt/els-mhd/config/docker.env -f deploy/compose.yaml config --quiet
sudo docker compose --env-file /opt/els-mhd/config/docker.env -f deploy/compose.yaml up -d --build
sudo docker compose --env-file /opt/els-mhd/config/docker.env -f deploy/compose.yaml ps
curl -fsS http://127.0.0.1:8080/api/meta
```

Access from an SSH local tunnel on the PC: `ssh -L 8080:127.0.0.1:8080 els-mhd@192.168.178.145`, then browse http://127.0.0.1:8080.

Never run `docker compose down -v` unless deliberately deleting the database.
Follow-ups needed before production: authentication/authorization, HTTPS, backup/restore testing, dependency audit, CI builds, deployment and rollback.
