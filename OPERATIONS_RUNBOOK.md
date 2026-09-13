# Agenda Django Operations Runbook

Agenda Django is deployed on Garnocex through GitHub Actions and protected by
verified local and encrypted off-site backups. This document is the operating
reference for deployment, recovery, credentials, and project context.

## Quick path

1. Develop only in a clean local Git worktree; never in the production checkout.
2. Push a branch and use the GitHub pull request workflow.
3. Merge to `master` only after CI passes; GitHub Actions deploys it.
4. Check the public endpoint and the deployment audit on Garnocex.
5. Keep the scheduled backups and the Vaultwarden GPG recovery item intact.

## Operating boundaries

| Location | Responsibility | Do not do here |
|---|---|---|
| Local minipc | Development, Git publication, off-site backup pull and encryption | Store production secrets in a repository |
| Garnocex | Docker production stack, nginx reverse proxy, local recovery snapshots | Use a personal GitHub token or edit application code directly |
| NAS | Encrypted off-site backup destination and manual recovery copies | Treat it as a POSIX-permission-enforcing store |
| GitHub | Source of truth, CI validation, deployment trigger | Store environment values in the repository |

The NAS mount may emulate POSIX modes. Its access policy is not a substitute for
encryption. Off-site copies are encrypted before being retained there.

## Production deployment

### Live topology

| Component | Location / rule |
|---|---|
| Canonical production checkout | `/srv/agenda-django` on Garnocex |
| Application | `agenda_app` Docker container |
| Database | `agenda_db` PostgreSQL 16 Docker container and persistent volume |
| Public routing | nginx → `127.0.0.1:8000` → Gunicorn |
| Public URL | `https://garnocex.unex.es/agenda/` |
| Last independently verified release | `09202e2`, public HTTP 200 |

The application port is intentionally loopback-only. Do not expose port 8000
to the network; nginx owns public HTTP/HTTPS access.

### GitHub Actions deployment flow

The workflow at `.github/workflows/ci.yml` runs Django validation on pushes and
pull requests. A push to `master` additionally runs the protected deploy job.

1. GitHub Actions authenticates as `agenda_deploy` on Garnocex with the deploy
   SSH key stored in GitHub environment secrets.
2. The forced SSH command runs `/usr/local/sbin/agenda-deploy` through a narrow
   passwordless sudo rule.
3. The wrapper fetches `master` using a separate **read-only** GitHub deploy key,
   builds/recreates the application container, and checks the public endpoint.

The server does not hold a GitHub personal access token. The deploy SSH key is
restricted with `restrict`, a forced command, and no forwarding or PTY.

### Deployment checks

Run these on **GARNOCEX** after a deployment:

```bash
sudo bash /tmp/audit-agenda-github-deploy.sh
sudo docker port agenda_app
curl -I https://garnocex.unex.es/agenda/
```

Expected result: the audit reports the intended commit and HTTP 200; Docker maps
the app only to `127.0.0.1:8000`.

## Credential and key inventory

Never paste a private key, password, token, webhook URL, `.env` value, or GPG
passphrase into Git, shell history shared with others, issues, or chat.

| Purpose | Custodian | Rule |
|---|---|---|
| Local GitHub publishing key | Local minipc SSH agent / Vaultwarden recovery record | Used by the developer only; no PAT on Garnocex |
| GitHub Actions → Garnocex deploy key | GitHub environment secret | Restricted to forced deployment command |
| Garnocex → GitHub read key | Root-owned server file | GitHub deploy key with read-only repository permission |
| Production environment | Root-owned `/srv/agenda-django/.env.garnocex` | Never print or commit it |
| Off-site pull key | Local minipc private key | May only invoke the restricted backup export endpoint |
| GPG off-site recovery material | Vaultwarden secure note | Keep secret-key export, public key, revocation certificate, checksums, and passphrase together |

Use `SECURITY_ROTATION.md` when rotating an application secret. If a credential
is found in source control, treat it as exposed: rotate it first, then remove it
from the working tree and remediate history according to repository exposure.

## Backup and recovery

### Garnocex local recovery snapshots

`agenda-backup.timer` runs daily on Garnocex at approximately 03:20 (plus a
small randomized delay). It creates a verified snapshot under:

`/var/backups/agenda-django/automated/`

Each snapshot includes:

- PostgreSQL custom dump (`agenda_db.dump`);
- PostgreSQL globals (`globals.sql`);
- static and media archives;
- SHA-256 manifest and verification evidence.

Retention: **30 daily snapshots**.

Checks on **GARNOCEX**:

```bash
sudo systemctl status agenda-backup.timer --no-pager
sudo systemctl start agenda-backup.service
sudo journalctl -u agenda-backup.service -n 30 --no-pager
```

An `inactive (dead)` result for the oneshot service after a successful run is
expected.

### Encrypted off-site copies on the NAS

The minipc user timer `agenda-offsite-backup.timer` pulls the most recent
verified Garnocex snapshot through the restricted `agenda_backup_export`
account, encrypts it with the dedicated GPG public key, and writes it to:

`/mnt/nas/Dropbox/Universidad/Desarrollo/agenda-django/Backup/automated/`

Retention: **60 encrypted daily copies**.

Checks on **LOCAL minipc**:

```bash
systemctl --user status agenda-offsite-backup.timer --no-pager
systemctl --user start agenda-offsite-backup.service
bash /tmp/audit-agenda-offsite-backup.sh
bash /tmp/verify-agenda-offsite-decrypt.sh
```

The GPG secret-key recovery package was attached to the Vaultwarden item
`Agenda Django — recuperación GPG`. Temporary local and NAS staging copies were
removed after verification. If the minipc is replaced, recover the GPG key from
Vaultwarden before attempting to decrypt an off-site artifact.

### Recovery evidence already completed

- Historical host PostgreSQL database was dumped and restored into a disposable
  verification database.
- Legacy and Docker database business-table counts were compared; the only
  difference was three later failed login attempts.
- An isolated Docker disaster-recovery environment restored database, static,
  and media artifacts and passed the critical data parity check.
- Latest off-site encrypted archive was interactively decrypted and listed
  without materializing plaintext on disk.

## PCC and Graphify

| Tool | Current state |
|---|---|
| PCC node | `desarrollo.agenda_estudiante` |
| PCC path | `/mnt/nas/Dropbox/Universidad/Desarrollo/agenda-django` |
| Graphify | A repository graph was generated and used to map the application domain |

PCC uses dot notation for the canonical node ID. Do not create
`desarrollo:agenda_estudiante`; it collides with the existing project path.

## Current product evolution

The next product phase deliberately excludes Power Apps, Power Automate, and
external login. It includes:

1. Multi-academic-year catalogue and year-specific subject offerings.
2. Administrator import wizard: draft import, validation, preview, explicit
   activation, and activation blocked until every offering has curricular year
   and semester.
3. Teacher-managed current-year teaching assignments; institutional catalogues
   never import teachers or personal identifiers.
4. Historical 2025-26 activities kept read-only for teachers, with controlled
   copy-to-next-year drafts and explicit accept/reject/date editing.
5. Native `.ics` upload: choose a current teaching offering, preview parsed
   events, accept/reject/edit, then create audited Agenda activities. Event UID
   prevents duplicate imports.

Plan and subject codes are immutable business keys. Use the composite
`(plan_code, subject_code)` identity; never match subjects across plans by name.

The current `16.csv` is a useful 2024-25 coded catalogue sample but contains
personal and student metrics that must not be imported. It also lacks curricular
year and semester, so it can seed a draft only. Future inputs should be retained
as separate year-stamped catalogue snapshots, not overwrite prior data.

## Handoff checklist

- [ ] Work from a clean Git checkout based on current `origin/master`.
- [ ] Keep generated graphs, backups, local `.env` files, and CSV source exports
      out of commits unless a deliberately sanitized fixture is needed.
- [ ] Run tests from a fresh database before merging schema changes.
- [ ] Confirm GitHub Actions CI passes before merging.
- [ ] Confirm the GitHub deployment audit and public HTTP response after merge.
- [ ] Check both backup timers after any Docker, database, or secret change.
- [ ] Test decryption and restore periodically, not only archive creation.
