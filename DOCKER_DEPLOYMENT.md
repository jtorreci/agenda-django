# Garnocex Docker deployment runbook

This repository provides a production Compose definition, but no automated deployment workflow. Deployment remains manual until GitHub Actions secrets and a restricted deploy identity are provisioned.

## Server preparation

1. Clone the repository into a server-owned directory.
2. Copy `.env.example` to `.env.garnocex`, then set every blank value. `ALLOWED_HOSTS` is a comma-separated host list and `CSRF_TRUSTED_ORIGINS` contains full HTTPS origins, for example `https://agenda.example.edu`.
3. Put TLS termination in front of the container and forward `X-Forwarded-Proto: https`. The Compose port binds only to `127.0.0.1`.
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
