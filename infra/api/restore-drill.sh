#!/usr/bin/env bash
# Restore drill (ENG-04 acceptance "restorable backups", README.md "Backups"): restores the newest daily dump
# into a throwaway PostgreSQL container, checks the schema version and row counts, prints them, removes the
# container. Run monthly on the VM and after every change to the backup service.
#
#   infra/api/restore-drill.sh [dump.sql.gz]
set -euo pipefail

backup_dir=${VERST_BACKUP_DIR:-/srv/verst/backups}
dump=${1:-$(find "$backup_dir/daily" -type f -name '*.sql.gz' -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)}
[ -n "$dump" ] && [ -f "$dump" ] || { echo "no dump found in $backup_dir/daily" >&2; exit 1; }
gzip -t "$dump"

name=verst-restore-drill-$$
docker run -d --rm --name "$name" -e POSTGRES_PASSWORD=drill -e POSTGRES_DB=verst postgres:16.14-trixie >/dev/null
trap 'docker rm -f "$name" >/dev/null 2>&1 || true' EXIT
for _ in $(seq 60); do
  docker exec "$name" pg_isready -U postgres -d verst -q && break
  sleep 1
done

gunzip -c "$dump" | docker exec -i "$name" psql -q -v ON_ERROR_STOP=1 -U postgres -d verst >/dev/null
docker exec "$name" psql -U postgres -d verst -At -F ' ' -c "
  SELECT 'migration', max(version) FROM api.schema_migration
  UNION ALL SELECT 'devices', count(*) FROM api.device
  UNION ALL SELECT 'trips', count(*) FROM api.trip
  UNION ALL SELECT 'feedback', count(*) FROM api.feedback"
echo "restore drill OK: $dump ($(du -h "$dump" | cut -f1))"
