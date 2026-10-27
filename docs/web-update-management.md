# Web-based update management — security and implementation design

Status: design only; no unauthenticated management endpoints.

## User experience
- New "System & Updates" entry under settings.
- "Auf Updates prüfen" reads current deployed image/commit, approved release and changelog, reports up-to-date/update/error.
- "Update installieren" is enabled only when an approved release exists, a dedicated administrator re-authentication succeeded, no deployment is ongoing and operations are in a safe state.
- Show progress: verification, backup, build, controlled deployment, health checks, rollback or complete.
- Offer password-protected rollback and show last update, outcome, and logs with secrets redacted.
- UI must recover state after refresh or connection loss.

## Trust boundary
- Do not mount /var/run/docker.sock into FastAPI, expose Docker TCP, allow general shell execution, or place a sudo/root password in frontend JS.
- Build a separate local host update-agent with narrowly scoped RPC. Restrict socket permissions and origin of requests. Do not give FastAPI arbitrary command execution.
- Protect BOTH update and check metadata from untrusted input. Use fixed allowlist of signed/approved releases/commit SHAs and trusted Git remote; do not blindly deploy newest branch commit.
- Separate update password: salt+memory-hard hash at rest, securely generated and managed locally, never included in repo, API responses or logs. Rate limit and lock out repeated guessing. No persistent browser storage.
- Only allow authenticated authorized administrators to access privileged actions. Dedicated confirmation and CSRF defenses if cookie sessions are used.
- Prevent simultaneous updates using locks, log every administrative action.

## Update safety
- Refuse update while active incidents exist unless explicitly confirmed by administrator under a documented emergency procedure; prefer maintenance outside operations.
- Preserve checkpoint of exact API/web image digests and Compose, config and Git revision; check backup integrity before updating.
- Build release-tagged images; persist active pinned compose override for reboot and future compose commands; never update MongoDB container or volumes implicitly.
- Handle SIGINT/SIGTERM and crash/power interruption with persisted transaction state and startup reconciliation; verify health and attempt bounded rollback.
- Verify HTTP and relevant API/data tests; monitor live status. Automatic rollback must not silently restore incompatible database state.
- Ensure user can recover with SSH if host agent is unavailable.
- Update control capability should only be considered complete after tests incl. wrong password, unauthorized API call, missing USB disk, backup failure, network failure, failed build, missing checkpoint, power loss and reboot.

## Suggested API contract
- GET /api/system/updates/check — returns status and approved release metadata, not a remote shell command.
- GET /api/system/updates/status — current operation state.
- POST /api/system/updates/apply — password-protected step-up with single-use authorization.
- POST /api/system/updates/rollback — step-up authorization and explicit confirmation.

Implementation order: host agent + tests; backend authorization; web UI; integration and fault tests. Keep the web update controls disabled until the host agent and permission model are verified.
