# Garnocex Docker deployment runbook

This repository provides a production Compose definition, but no automated deployment workflow. Deployment remains manual until GitHub Actions secrets and a restricted deploy identity are provisioned.

## Server preparation

1. Clone the repository into a server-owned directory.
2. Copy `.env.example` to `.env.garnocex`, then set `POSTGRES_PASSWORD` and `DJANGO_SECRET_KEY`. `ALLOWED_HOSTS` (comma-separated hosts) defaults to `garnocex.unex.es` and `CSRF_TRUSTED_ORIGINS` (full HTTPS origins) defaults to `https://garnocex.unex.es`; set them only to override those defaults.
3. The app is published by the shared garnocex Caddy proxy under `https://garnocex.unex.es/agenda/` (see the proxy's `CONTRACT.md`). Caddy strips the `/agenda` prefix, forwards the original `Host`, and sets `X-Forwarded-Proto`; Django re-adds the prefix through `FORCE_SCRIPT_NAME` (`DJANGO_SCRIPT_NAME`, default `/agenda`), so static files live under `/agenda/static/`, media under `/agenda/media/`, and cookies are scoped to `/agenda`.
   - Create the shared network once on the host before starting this stack: `docker network create proxy`. The `agenda` service joins it with the alias `agenda-app`.
   - Caddy serves `/agenda/media/*` directly from the `agenda_media_files` volume, publicly and without Django permission checks. Do not store private uploads there.
   - The Compose port still binds only to `127.0.0.1:8000` for the transition from host nginx. A proxy that mounts the app at the domain root instead must set `DJANGO_SCRIPT_NAME=/` and forward `Host` and `X-Forwarded-Proto: https`.
4. Validate configuration without printing secrets:

   ```bash
   docker compose --env-file .env.garnocex -f compose.production.yml config --quiet
   ```

5. Build and start:

   ```bash
   docker compose --env-file .env.garnocex -f compose.production.yml up -d --build
   ```

The web container applies migrations and collects static files before Gunicorn starts. PostgreSQL and uploaded media use named Docker volumes; include both in the backup plan.

## Future GitHub Actions deployment

Before adding a manual `workflow_dispatch` deployment workflow, create a dedicated restricted server account and store only these GitHub repository secrets: `DEPLOY_SSH_HOST`, `DEPLOY_SSH_USER`, `DEPLOY_SSH_PRIVATE_KEY`, and (if non-default) `DEPLOY_SSH_PORT`. The account should be limited to the repository's deployment command. Do not store `.env.garnocex`, database credentials, or Django secrets in GitHub Actions.
