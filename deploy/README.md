# ELS-MHD Docker development smoke test (not production)
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
