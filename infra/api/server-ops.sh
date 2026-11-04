#!/usr/bin/env bash
# The test server's whitelisted actions for Claude (D-IR-29, CEO 03.11 «будешь сам выполнять эти команды»).
#
# The forced command of the GitHub Actions key in /root/.ssh/authorized_keys:
#   restrict,command="/srv/verst/src/infra/api/server-ops.sh" ssh-ed25519 AAAA… verst-github-actions
# so that key runs this script and nothing else; the action is the SSH command line ($SSH_ORIGINAL_COMMAND).
# Workflow: .github/workflows/test-server.yml. Anything not listed here stays with the CEO.
#
#   status    branch and commit, containers, /healthz
#   update    git pull (fast-forward only), rebuild and restart the api, wait for /healthz
#   recreate  restart the api with the current .env (after the CEO edited it)
#   errors    the api log's WARNING / ERROR lines of the last 2 hours (no request bodies, no secrets)
#   rollback  run the api image that served before the last `update` again (D-IR-33): `update` keeps it as
#             verst-api:previous; the code checkout stays on main, so the next `update` rebuilds from main.
#             Refused when the last update brought a database migration (the old code may not fit the schema).
set -euo pipefail

# `update` may pull a new copy of this file: run from a private copy so bash never reads a changed script
if [ -z "${VERST_OPS_COPY:-}" ]; then
    copy="$(mktemp)"
    cp "$0" "$copy"
    VERST_OPS_COPY="$copy" exec bash "$copy"
fi
trap 'rm -f "$VERST_OPS_COPY"' EXIT

ACTION="${SSH_ORIGINAL_COMMAND:-status}"
SRC=/srv/verst/src
API="$SRC/infra/api"
C=(docker compose -f docker-compose.yml -f docker-compose.host-nginx.yml)
STATE=/srv/verst/ops-state
migrations() { find "$SRC/backend/api/migrations" -name '*.sql' ! -name '*.down.sql' 2>/dev/null | sort; }

health() {
    for _ in $(seq 1 30); do
        if out="$(curl -fsS --max-time 5 http://127.0.0.1:8000/healthz 2>/dev/null)"; then
            echo "healthz: $out"
            return 0
        fi
        sleep 4
    done
    echo "healthz: no answer after 2 minutes" >&2
    return 1
}

case "$ACTION" in
    status)
        cd "$SRC"
        echo "branch: $(git branch --show-current) · $(git log -1 --format='%h %ad %s' --date=format:'%d.%m %H:%M')"
        cd "$API"
        "${C[@]}" ps --format 'table {{.Service}}\t{{.State}}\t{{.Status}}'
        health
        ;;
    update)
        cd "$SRC"
        mkdir -p "$STATE"
        before="$(git rev-parse --short HEAD)"
        migrations > "$STATE/migrations-before"
        # D-IR-33: the image serving now is the rollback target
        if docker image inspect verst-api:local > /dev/null 2>&1; then
            docker tag verst-api:local verst-api:previous
            echo "$before" > "$STATE/previous-commit"
        fi
        git pull -q --ff-only
        echo "code: $before → $(git log -1 --format='%h %s')"
        if migrations | cmp -s - "$STATE/migrations-before"; then
            echo "no" > "$STATE/schema-changed"
        else
            echo "yes" > "$STATE/schema-changed"
            echo "note: this update brings a database migration — a rollback will be refused"
        fi
        cd "$API"
        "${C[@]}" build api
        "${C[@]}" up -d api
        health
        ;;
    rollback)
        if ! docker image inspect verst-api:previous > /dev/null 2>&1; then
            echo "no previous image: nothing to roll back to (no update ran since D-IR-33)" >&2
            exit 3
        fi
        if [ "$(cat "$STATE/schema-changed" 2>/dev/null || echo unknown)" != "no" ]; then
            echo "refused: the last update changed the database schema (or it is unknown); a rollback is the CEO's" >&2
            exit 4
        fi
        echo "rolling back the api to the image of $(cat "$STATE/previous-commit" 2>/dev/null || echo '?')"
        docker tag verst-api:local verst-api:rolled-back
        docker tag verst-api:previous verst-api:local
        cd "$API"
        "${C[@]}" up -d --force-recreate --no-build api
        health
        echo "the code checkout stays on $(cd "$SRC" && git rev-parse --short HEAD); the next update rebuilds from main"
        ;;
    recreate)
        cd "$API"
        "${C[@]}" up -d --force-recreate api
        health
        ;;
    errors)
        cd "$API"
        "${C[@]}" logs --since 2h --no-color api 2>&1 | grep -E 'WARNING|ERROR|CRITICAL|Traceback' | tail -n 80 || echo "no warnings or errors in the last 2 hours"
        ;;
    *)
        echo "unknown action «$ACTION»: status | update | recreate | errors | rollback" >&2
        exit 2
        ;;
esac
