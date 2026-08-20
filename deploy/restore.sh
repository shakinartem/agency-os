#!/bin/sh
set -eu

if [ "${CONFIRM_RESTORE:-}" != "YES" ]; then
  echo "Restore is destructive. Re-run with CONFIRM_RESTORE=YES." >&2
  exit 2
fi
if [ $# -ne 1 ]; then echo "Usage: CONFIRM_RESTORE=YES $0 /path/to/backup" >&2; exit 2; fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
ENV_FILE=${ENV_FILE:-$ROOT_DIR/.env}
SRC=$(CDPATH= cd -- "$1" && pwd)

[ -f "$ENV_FILE" ] || { echo "Missing env file: $ENV_FILE" >&2; exit 1; }
[ -f "$SRC/database.dump" ] || { echo "Missing database.dump" >&2; exit 1; }
[ -f "$SRC/SHA256SUMS" ] || { echo "Missing SHA256SUMS" >&2; exit 1; }
(cd "$SRC" && sha256sum -c SHA256SUMS)

compose() {
  docker compose --env-file "$ENV_FILE" -f "$SCRIPT_DIR/docker-compose.prod.yml" "$@"
}

# Stop application writers while restoring state.
compose stop api worker beat web || true
cat "$SRC/database.dump" | compose exec -T postgres sh -ec \
  'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner'

compose run --rm --no-deps --entrypoint /bin/sh \
  -v "$SRC:/backup:ro" minio-init -ec '
    mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null;
    mc mirror --overwrite --remove /backup/content-assets local/content-assets;
  '

compose up -d api worker beat web

echo "Restore completed from: $SRC"
