# Production server deployment

Use this compose file for internet-facing deployments. The root `docker-compose.yml` is a developer stack with host ports and intentionally convenient defaults.

1. Create the shared private network once: `docker network create qualive-backbone || true`.
2. Copy `.env.example` to `.env` and replace every production secret. Use long random URL-safe passwords/secrets.
3. Set `FACTORY_DOMAIN`, `FACTORY_ASSETS_DOMAIN`, `DATABASE_URL`, `POSTGRES_PASSWORD`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_APP_USER`, `MINIO_APP_PASSWORD`, `SECRET_KEY`, paired Autoposter tokens and provider credentials.
4. Run `python scripts/server-preflight.py --env .env`.
5. From `deploy/`, run `docker compose -f docker-compose.prod.yml config` and then `docker compose -f docker-compose.prod.yml up -d --build`.
6. Verify `https://$FACTORY_DOMAIN/api/health` and `https://$FACTORY_DOMAIN/api/ready` through the same-origin Next.js proxy.

PostgreSQL, Redis, MinIO console and the FastAPI service are not published on host ports. Browser sessions are HttpOnly/Secure and all browser API calls go through the same-origin Next.js `/api/*` rewrite. The API also joins `qualive-backbone` under alias `content-factory-api` so Autoposter can call it without exposing an API subdomain.

## Backups and restore

Create a consistent operational backup before upgrades and on a schedule:

```bash
cd deploy
./backup.sh
```

The backup contains a PostgreSQL custom-format dump, an S3-level export of `content-assets`, and `SHA256SUMS`. Store copies off-server with access controls.

Restores are deliberately destructive and require an explicit acknowledgement:

```bash
CONFIRM_RESTORE=YES ./restore.sh ./backups/<timestamp>
```

Test restore on a non-production host periodically; an untested backup is not a recovery plan.
