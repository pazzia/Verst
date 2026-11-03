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
        before="$(git rev-parse --short HEAD)"
        git pull -q --ff-only
        echo "code: $before → $(git log -1 --format='%h %s')"
        cd "$API"
        "${C[@]}" build api
        "${C[@]}" up -d api
        health
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
        echo "unknown action «$ACTION»: status | update | recreate | errors" >&2
        exit 2
        ;;
esac
