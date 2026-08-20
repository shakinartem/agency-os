#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
ENV_FILE=${ENV_FILE:-$ROOT_DIR/.env}
BACKUP_ROOT=${BACKUP_ROOT:-$SCRIPT_DIR/backups}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
DEST="$BACKUP_ROOT/$STAMP"

if [ ! -f "$ENV_FILE" ]; then echo "Missing env file: $ENV_FILE" >&2; exit 1; fi
mkdir -p "$DEST"
chmod 700 "$BACKUP_ROOT" "$DEST" 2>/dev/null || true

compose() {
  docker compose --env-file "$ENV_FILE" -f "$SCRIPT_DIR/docker-compose.prod.yml" "$@"
}

# Database: execute with credentials already present inside the PostgreSQL container.
compose exec -T postgres sh -ec 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$DEST/database.dump"

# Object storage: export through S3 API rather than copying MinIO's internal volume layout.
compose run --rm --no-deps --entrypoint /bin/sh \
  -v "$DEST:/backup" minio-init -ec '
    mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null;
    mkdir -p /backup/content-assets;
    mc mirror --overwrite local/content-assets /backup/content-assets;
  '

(
  cd "$DEST"
  sha256sum database.dump > SHA256SUMS
  find content-assets -type f -print0 | sort -z | xargs -0 -r sha256sum >> SHA256SUMS
)
printf '%s\n' "$STAMP" > "$DEST/BACKUP_UTC"
chmod -R go-rwx "$DEST" 2>/dev/null || true

echo "Backup completed: $DEST"
