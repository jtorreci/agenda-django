# Agenda behind the shared garnocex proxy

Agenda is published at `https://garnocex.unex.es/agenda/` behind a shared Caddy proxy
that also serves other apps. The proxy strips `/agenda` before forwarding; Django adds
it back to every URL it emits. This document is the agenda side of the shared contract
and the starting point for any other app that joins the proxy later.

> **Source of truth:** `CONTRACT.md`, `Caddyfile`, `docker-compose.yml` and `README.md`
> in `/mnt/nas/Dropbox/Universidad/Investigacion/Convenios/DGAP/app/garnocex-proxy`
> (server: `/opt/proxy`). Those files are shared: change their site-level parts only
> after agreement with every affected app owner. Agenda edits only its own blocks.

> **Server-wide reference:** decisions, routes and open issues for everything deployed on
> Garnocex live in the PCC node `desarrollo.garnocex_infra`
> (`/mnt/nas/Dropbox/Universidad/Desarrollo/garnocex-infra/README.md`).

## Quick path

1. On Garnocex, once: `docker network create proxy`. Without it the agenda deploy fails,
   because `compose.production.yml` joins that external network.
2. Deploy agenda as usual (merge to `master`, GitHub Actions). This works **before and
   after** the Caddy cut-over, because host nginx strips `/agenda` exactly like Caddy.
3. Verify: `curl -I https://garnocex.unex.es/agenda/` returns `200` or a redirect to
   `/agenda/login/`, and `curl -I https://garnocex.unex.es/login/` never serves the app.

## Routing

| Public path | Handled by | Upstream sees | Notes |
|---|---|---|---|
| `/` | shared | — | `302 → /agenda/` |
| `/agenda/media/*` | Caddy `file_server` | — | volume `agenda_media_files`, read-only |
| `/agenda/*` | `agenda-app:8000` | path without `/agenda` | `handle_path` strips the prefix |
| `/login/`, `/static/`… | shared fallback | — | `404` by design: exposes prefix bugs |

## Agenda configuration

| Area | Decision | Where |
|---|---|---|
| Prefix | `DJANGO_SCRIPT_NAME` (blank → `/agenda`, `/` → root). `FORCE_SCRIPT_NAME`, `STATIC_URL`, `MEDIA_URL` and cookie paths all derive from it | `settings_production.py` |
| Hosts | `ALLOWED_HOSTS` defaults to `garnocex.unex.es`; `CSRF_TRUSTED_ORIGINS` to `https://garnocex.unex.es`; both env-overridable | `settings_production.py` |
| Cookies | Session, CSRF and language cookies scoped to `Path=/agenda` so other apps on the domain never receive them | `settings_production.py` |
| HTTPS | `SECURE_PROXY_SSL_HEADER` trusts `X-Forwarded-Proto` set by the proxy; `USE_X_FORWARDED_HOST=False` because the proxy forwards `Host` unchanged | `settings_production.py` |
| Static files | WhiteNoise with `WHITENOISE_STATIC_PREFIX="/static/"`. Required: WhiteNoise's own prefix detection runs before Gunicorn sets the script prefix and would 404 every static file | `settings_production.py` |
| Media | Public via Caddy. Acceptable because no model stores uploads and PDFs are streamed, never saved. If private uploads appear, route media through Django and drop the Caddy media block (shared change) | contract |
| URLs | Never write root paths. Templates use `{% url %}`; JS with ids renders the pattern with id `0` and calls `urlWithId()` from `templates/base.html`; settings use URL names (`LOGIN_URL = 'login'`) | templates, `settings.py` |
| Network | `agenda` service joins external network `proxy` with alias `agenda-app`, keeps `agenda_network` and the `127.0.0.1:8000` binding used by host nginx until cut-over | `compose.production.yml` |
| CI/CD | Deploys the agenda stack only; never touches `/opt/proxy` | `.github/workflows/ci.yml` |

Regression tests in `agenda_academica/tests.py` fail if a page emits an unprefixed URL or
if the production prefix settings drift.

## Local end-to-end test

The stack in `deploy/proxy-test/` runs Postgres, the production image and Caddy with the
agenda blocks copied verbatim from the shared `Caddyfile` (site address changed to
`https://localhost:18443` with `tls internal`). Names are prefixed `agenda-proxytest`.

```sh
cd deploy/proxy-test
cp test.env.example .env
docker compose -f compose.test.yml up -d --build
docker compose -f compose.test.yml exec agenda \
  sh -c 'DB_NAME=$POSTGRES_DB DB_USER=$POSTGRES_USER DB_PASSWORD=$POSTGRES_PASSWORD DB_HOST=db DB_PORT=5432 \
  DJANGO_SUPERUSER_PASSWORD=Proxytest-Pass-2026 python manage.py createsuperuser --noinput --username proxyadmin --email proxyadmin@example.com'
docker compose -f compose.test.yml exec agenda sh -c 'echo proxytest > /app/media/proxytest.txt'
./verify.sh
docker compose -f compose.test.yml down -v
```

Expected results (verified 2026-09-14):

| Request | Expected |
|---|---|
| `/`, `/agenda` | `302 → /agenda/` |
| `/login/`, `/static/…` | `404` |
| anonymous dashboard | `302 → /agenda/login/?next=/agenda/…` |
| login page | `200`, form action `/agenda/login/`, cookies `Path=/agenda; Secure` |
| POST login | `302 → /agenda/users/dashboard_redirect/` |
| `/agenda/admin/` login | works, admin CSS `200 text/css` |
| `/agenda/media/proxytest.txt` | `200` from the volume |
| POST `/agenda/logout/` | `302 → /agenda/logout_success/`, session cleared |

## Cut-over impact on Garnocex

Host nginx (`/etc/nginx/sites-enabled/`) publishes more than the contract routes. Stopping
nginx at cut-over affects:

| Current nginx route | After cut-over | Status |
|---|---|---|
| `/agenda/` → `127.0.0.1:8000` | Caddy → `agenda-app:8000` | migrated |
| `/calculadora/` → static `/home/jtorreci/calculadora/` | not published | accepted: app in development |
| `/horarios/` → `127.0.0.1:8001` | not published | accepted: app in development |
| vhost `50aniversario.unex.es` | not published | no impact: the name has no DNS record |

Cut-over and rollback steps live in the proxy `README.md`.

## Adding another app to the proxy

Use this when `calculadora`, `horarios` or any new app is ready to publish.

1. **Claim a prefix first.** Add a row to the route table in the shared `CONTRACT.md` and
   agree it with the other owners before editing the `Caddyfile`.
2. **Pick the pattern:**

   | App type | Caddy block | App requirements |
   |---|---|---|
   | Static site (e.g. `calculadora`) | `handle_path /calculadora/* { root * /srv/calculadora; try_files {path} /index.html; file_server }` | Build output in a volume or directory mounted read-only into the Caddy container (shared `docker-compose.yml` change). Assets must use relative paths or the `/calculadora/` base |
   | Server app, prefix stripped (e.g. `horarios`) | `handle_path /horarios/* { reverse_proxy horarios-app:<port> }` | Join network `proxy` with a unique alias. Emit every URL with its prefix (Django: same settings as agenda). Trust `X-Forwarded-Proto` |
   | Server app, prefix kept (e.g. `digibic`) | `handle /digibic/* { reverse_proxy digibic-app:5000 }` | App is mounted under its prefix itself |

3. **Never target host loopback.** An upstream listening on `127.0.0.1` of the host (as
   `horarios` does under nginx today) is unreachable from the Caddy container. Join the
   `proxy` network instead.
4. **Do not publish ports 80/443.** A `127.0.0.1` debug binding is allowed.
5. **Validate and reload, never restart** the proxy:
   ```sh
   docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
   docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
   ```
6. **Test locally** by copying `deploy/proxy-test/` and replacing the agenda blocks with
   the new app's blocks, copied verbatim from the proposed `Caddyfile`.

## Known mismatches with the shared README

- It places the agenda in `/opt/agenda` and deploys with `docker compose up`. The real
  stack uses `compose.production.yml`, `.env.garnocex`, project `agenda`, network
  `agenda_agenda_network` and container `agenda_app`, in the production checkout on
  Garnocex. Report to the proxy owner; do not edit the
  shared file unilaterally.
