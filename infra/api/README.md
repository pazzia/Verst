# verst-api on the beta VM (ENG-04)

One VM in Russia runs the whole beta backend with Docker Compose ([ADR-0020](../../docs/adr/0020-minimal-beta-backend.md)):

```
phone ──HTTPS──▶ proxy (Caddy 2.11, Let's Encrypt) ──▶ api (verst-api, 2 uvicorn workers, non-root, read-only FS)
                                                          ├─▶ postgres (16, volume pgdata) ◀── backup (daily dumps)
                                                          └─▶ graphhopper (profile "routing", ADR-0017) — or the maps VM
```

Only the proxy publishes ports (80, 443). `/metrics`, `/readyz`, `/docs` and `/openapi.json` answer 404 from
outside; Prometheus (when added) scrapes `api:8000/metrics` on the compose network.

## Files

| File | What |
| --- | --- |
| `Dockerfile` (+ `Dockerfile.dockerignore`) | The API image; build context = repository root. Dependencies from `backend/api/requirements.lock` with `--require-hashes`. Runs as uid 10002. |
| `entrypoint.sh` | uvicorn with `--proxy-headers`, `--no-access-log` (R-07), `VERST_WORKERS` workers. |
| `docker-compose.yml` | proxy, api, postgres, backup; graphhopper under the `routing` profile (extends `infra/routing/docker-compose.yml`, port not published). |
| `Caddyfile` | TLS, 2 MB body limit, no compression for SSE, no access log (URIs carry coordinates). |
| `.env.example` | Every setting, no secrets. Copy to `.env` (git-ignored). |
| `restore-drill.sh` | Restores the newest dump into a throwaway container and prints row counts. |

## First install

Prerequisites: Ubuntu 24.04 LTS, Docker Engine with the compose plugin ≥ 2.24 (`!reset` in the compose file),
a DNS A record for the API name pointing at the VM, ports 80 and 443 open, 22 restricted to the team.

```sh
sudo install -d -m 0700 /srv/verst/backups            # dumps contain the beta data: root only
sudo install -d -m 0755 /srv/verst/routing             # GraphHopper graph (infra/routing/README.md)
git clone <repo> /srv/verst/src && cd /srv/verst/src/infra/api
cp .env.example .env && chmod 600 .env
#   fill: VERST_DOMAIN, VERST_ACME_EMAIL, VERST_PUBLIC_BASE_URL (https://<VERST_DOMAIN>),
#         POSTGRES_PASSWORD=$(openssl rand -hex 32), VERST_RATE_KEY_SECRET=$(openssl rand -hex 32)
docker compose build api
docker compose --profile routing up -d                # without --profile if GraphHopper runs on the maps VM
docker compose ps                                     # api "healthy", postgres "healthy"
curl -fsS https://$VERST_DOMAIN/healthz               # {"status":"ok"}
docker compose exec api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/readyz').read().decode())"
```

The API applies its migrations at start (advisory lock, `backend/api/migrations`). By hand:
`docker compose exec api python -m verst_api.db status | up | down <version>`.

GraphHopper needs a graph in `/srv/verst/routing/current` first: follow `infra/routing/README.md` (weekly
rebuild). Until it serves, set `VERST_ROUTING=road_model` (plans carry `approxDistances`, `POST /v1/route`
answers 503 and the phone applies its offline rule, ADR-0017 §5).

## Test VM with its own nginx (the Netherlands VM, tests only)

The CEO's test VM already serves other sites with nginx on 80/443 and has ~3 GB free memory. Caddy is not
started; the host nginx proxies `212-108-82-26.sslip.io` (sslip.io resolves the name to the IP, so Let's
Encrypt works without a domain) to verst-api on `127.0.0.1:8000`; routing stays on the road model until a
graph fits (`VERST_ROUTING=road_model`). Trips and feedback stored here are friends-and-team test data only:
the beta with real users runs in Russia (152-FZ).

```sh
docker compose -f docker-compose.yml -f docker-compose.host-nginx.yml build api
docker compose -f docker-compose.yml -f docker-compose.host-nginx.yml up -d api postgres backup
curl -fsS http://127.0.0.1:8000/healthz                 # {"status":"ok"}
# nginx: nginx-verst.conf.example (sed the domain in), then certbot --nginx -d <domain>
```

## Release (update)

```sh
cd /srv/verst/src && git fetch && git checkout <tag>
cd infra/api && docker compose build api && docker compose up -d api   # ~10 s of 502 while workers restart
docker compose logs --since 5m api | grep -v '"level": "INFO"'           # no errors expected
```

Pin the base images by digest before the first public build (`docker buildx imagetools inspect
python:3.12.14-slim-trixie` → `FROM python:3.12.14-slim-trixie@sha256:…`; same for postgres, caddy, backup).

## Backups and restore

- `backup` dumps the `verst` database every day at 03:00 Moscow time (`pg_dump -Z6 --no-owner
  --no-privileges`) into `/srv/verst/backups/{daily,weekly,monthly}`; it keeps 14 daily, 4 weekly and 3
  monthly dumps (SPEC §11). Take one now: `docker compose exec backup /backup.sh`.
- **Off-site copy (open question, ADR-0020 §11):** until the CEO picks the storage, copy the newest weekly
  dump to the team's Yandex Object Storage bucket by hand after each Sunday rebuild. Dumps hold no exact
  coordinates, labels, tokens or IPs (R-07), but they are still personal-data-adjacent: keep them in Russia.
- **Restore drill (acceptance "restorable backups")**, monthly and after any change to the backup service:

  ```sh
  VERST_BACKUP_DIR=/srv/verst/backups ./restore-drill.sh
  # migration 1 / devices N / trips N / feedback N / "restore drill OK: …"
  ```

- **Real restore:** `docker compose stop api`, then
  `gunzip -c <dump> | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U verst_api -d verst` into an
  empty database (`docker compose rm -sf postgres && docker volume rm verst_pgdata && docker compose up -d
  postgres` first), then `docker compose up -d api`.

## Uptime (acceptance ≥ 99 %)

- Every container has `restart: unless-stopped`; api and postgres have health checks; Docker starts on boot.
- External check (open question, default applied in ADR-0020 §11): an HTTPS monitor on `/healthz` every
  minute from outside the VM with a Telegram alert; the monthly uptime it reports is the acceptance number.
- Planned downtime: a GraphHopper rebuild on a 16 GB VM stops routing for 30–90 min a week (≈ 0.5 %);
  `VERST_SYNTHETIC_FALLBACK=true` during that window keeps planning available with flagged distances.

## Privacy checklist (R-07)

- No access logs in Caddy or uvicorn; verst-api logs route templates, an 8-char device hash and coordinates
  rounded to 2 decimals. PostgreSQL logs slow statements without bind values.
- Stored trips: towns instead of user points and labels, all coordinates rounded to 2 decimals; feedback text
  masked for phones and e-mails and cleared after `VERST_FEEDBACK_TEXT_DAYS` (180); rate-limit keys hold an
  HMAC of the IP and are deleted after two days.
- The VM, its disks and the backup copies stay in Russia.
