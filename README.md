# Content Factory

Content Factory is an AI production system that turns a high-level content task into a reviewed, versioned, platform-adapted content package ready for the separate Autoposter application.

This repository is the refactored successor of Agency OS. CRM, lead processing, AI consultation and reporting are no longer part of the product runtime.

## Product workspaces

- **Brand Brain** — positioning, audience, products, tone of voice, mandatory rules and forbidden claims.
- **Strategy & Rubrics** — AI-generated reusable content lanes with critic/revision, audience-stage rationale and generation lineage.
- **Factory** — high-level task launcher and live production pipeline.
- **Content Review** — canonical copy, versions, quality scores, research sources, platform variants, media and human approval/regeneration.
- **Autoposter Outbox** — validated `content-package/1.0` deliveries with Send/Retry.

## Product boundary

Content Factory owns **what should be published**:

- brand context and rules;
- content strategy and reusable rubrics;
- research and source provenance;
- canonical content generation;
- critic / quality evaluation;
- revision loops;
- humanization;
- platform variants;
- visual generation and visual QA;
- immutable version history;
- export package validation;
- handoff to Autoposter.

Autoposter owns **how and when it is technically published**:

- platform credentials;
- platform-specific rendering;
- scheduling;
- API delivery to Telegram / VK / Instagram / Dzen / other destinations;
- publication status and delivery retries on the platform side.

## Production flow

```text
High-level task
    ↓
Brand Brain
    ↓
Live research (optional)
    ↓
Canonical draft
    ↓
Quality evaluation
    ↓
Revision loop (threshold-based)
    ↓
Humanize
    ↓
Platform variants
    ↓
Image generation
    ↓
Vision QA / regeneration loop
    ↓
Final QA / human review when required
    ↓
content-package/1.0
    ↓
Autoposter Outbox
    ↓
Autoposter
```

The pipeline is intentionally deterministic rather than a swarm of opaque autonomous agents. Every significant stage is persisted so failures can be inspected, retried and measured.

## Strategy flow

Rubric generation is a separate strategy workflow:

```text
Brand Brain + strategy goal
    ↓
Optional live research
    ↓
Rubric system generation
    ↓
Strategy critic
    ↓
Revision when overlap / coverage / actionability are weak
    ↓
Quality gate
    ↓
Activate new AI rubric set
```

Older AI rubric sets are deactivated rather than deleted, preserving lineage for the future performance-learning loop.

## Architecture

```text
apps/web       Next.js strategy, factory, review and outbox UI
apps/api       FastAPI auth, projects and Content Factory APIs
apps/worker    Celery production / review / strategy pipelines
packages/database
               SQLAlchemy models + Alembic migrations
PostgreSQL     content, versions, sources, evaluations, runs and export state
Redis          Celery broker
MinIO / S3     private generated media assets
Tavily         optional live research provider
LLM endpoint   OpenAI-compatible text + vision endpoint
Image endpoint OpenAI-compatible image generation endpoint
Autoposter     separate application accepting content-package/1.0
```

## Core data model

- `Project` — isolated content workspace.
- `BrandProfile` — positioning, audience, products, tone of voice, brand rules and forbidden claims.
- `Rubric` — reusable content category with AI/manual origin and generation lineage.
- `GenerationRun` — one high-level production or strategy job.
- `GenerationStep` — persisted trace of each pipeline stage.
- `ContentItem` — current canonical content representation plus research provenance.
- `ContentVersion` — immutable history of AI and human revisions.
- `ContentVariant` — adapted copy for a specific destination platform.
- `Evaluation` — structured quality scores and review notes.
- `MediaAsset` — generated visual stored outside PostgreSQL.
- `ExportDelivery` — validated package and Autoposter delivery state.

Legacy Agency OS tables are intentionally not dropped yet. They are no longer mounted in the runtime and may be removed with a destructive cleanup migration only after the new deployment is verified.

## Quality gates

The default text thresholds are configurable:

```env
QUALITY_THRESHOLD=0.87
FACTUALITY_THRESHOLD=0.95
BRAND_VOICE_THRESHOLD=0.85
MAX_REVISION_ATTEMPTS=2
```

Content that cannot reach the thresholds is routed to review instead of being silently approved. Human approval overrides the canonical-copy gate, but does **not** bypass platform adaptation, media QA or package validation.

Visuals use their own quality threshold and retry budget:

```env
MEDIA_QUALITY_THRESHOLD=0.86
MAX_IMAGE_ATTEMPTS=2
```

If image generation, vision QA or object storage is unavailable, the pipeline does not fake success; the item stops for review.

## Research provenance

Live research is optional per generation run. When enabled and configured, the worker stores source title, URL, snippet and relevance score with the canonical content and exports source metadata in the final content package.

If the research provider is not configured, the stage is persisted as `skipped`. No synthetic URLs or fake search results are generated.

## Private media storage

Generated image bytes are never stored in PostgreSQL. Accepted media is uploaded to a private S3-compatible object store.

Local Docker Compose includes MinIO:

- S3 API: `http://localhost:9000`
- MinIO console: `http://localhost:9001`
- private bucket: `content-assets`

By default Content Factory returns time-limited presigned media URLs. Configure `S3_PUBLIC_ENDPOINT_URL` with the address that browsers/Autoposter can reach. `S3_PUBLIC_BASE_URL` should only be set deliberately when using a public CDN origin.

Autoposter should ingest/copy media during package acceptance instead of treating a presigned URL as a permanent publication asset.

## Autoposter contract

Content Factory validates every outgoing payload against `content-package/1.0` before it is persisted to the Outbox.

Example shape:

```json
{
  "schema_version": "content-package/1.0",
  "content_id": "...",
  "project_id": "...",
  "status": "approved",
  "canonical": {
    "content_type": "post",
    "topic": "...",
    "goal": "...",
    "title": "...",
    "body": "...",
    "hook": "...",
    "cta": "..."
  },
  "variants": [
    {
      "platform": "telegram",
      "plain_text": "...",
      "hashtags": [],
      "blocks": [],
      "media": []
    }
  ],
  "sources": [],
  "quality": {
    "overall": 0.94,
    "factuality": 0.98,
    "brand_voice": 0.91,
    "media": 0.93
  }
}
```

Manual and retry deliveries use an `Idempotency-Key` header. Autoposter should persist and enforce this key so retries cannot create duplicate publications.

## API

Main Content Factory endpoints:

```text
GET  /factory/capabilities
POST /factory/runs
GET  /factory/runs
GET  /factory/runs/{run_id}
GET  /factory/content/{content_id}/detail
POST /factory/content/{content_id}/approve
POST /factory/content/{content_id}/regenerate

GET  /factory/brand/{project_id}
PUT  /factory/brand/{project_id}

POST /strategy/rubrics/generate
GET  /strategy/rubrics?project_id=...
POST /strategy/rubrics/{rubric_id}/archive

GET  /factory/outbox?project_id=...
POST /factory/outbox/{delivery_id}/send
```

API docs are available at `/docs` when the API is running.

## Environment

Create the local environment file:

```bash
cp .env.example .env
```

At minimum, configure the text model:

```env
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=...
LLM_MODEL=...
```

Optional live research:

```env
TAVILY_API_KEY=...
```

Image generation:

```env
IMAGE_API_URL=...
IMAGE_API_KEY=...
IMAGE_MODEL=...
```

Private object storage uses the `S3_*` variables documented in `.env.example`.

Autoposter handoff:

```env
AUTOPOSTER_URL=...
AUTOPOSTER_TOKEN=...
```

## Local Docker run

Prerequisites:

- Docker Engine / Docker Desktop;
- Docker Compose v2.

Start the stack:

```bash
cp .env.example .env
docker compose up --build
```

Services:

```text
Web             http://localhost:3010
API             http://localhost:8010
API docs        http://localhost:8010/docs
PostgreSQL      localhost:5433
Redis           localhost:6380
MinIO S3        http://localhost:9000
MinIO console   http://localhost:9001
```

Database migrations are run by the `migrate` service before API/worker startup.

Stop:

```bash
docker compose down
```

Delete local data as well:

```bash
docker compose down -v
```

## Worker

Celery task families:

```text
content_factory.process_run
content_factory.approve_content
content_factory.generate_rubrics
content_factory.send_delivery
```

## CI

`.github/workflows/ci.yml` validates:

- Python compilation;
- API/worker/strategy task imports;
- Alembic migrations against a real PostgreSQL 15 service;
- Content Package contract tests;
- provider fallback safety tests;
- Next.js production build;
- Docker Compose configuration.

Real model/image/research/Autoposter E2E tests require credentials and should be protected deployment checks rather than exposing production keys to ordinary pull-request jobs.

## Deployment acceptance checklist

Before merging/deploying a Content Factory release, verify:

1. CI is green.
2. Alembic upgrades cleanly on a copy of the target database.
3. `GET /factory/capabilities` shows expected providers as ready.
4. A test project has a complete `BrandProfile`.
5. AI Rubrics generate and the accepted set becomes active.
6. One production run completes from task → ready content.
7. Research sources are visible in persisted content when research is enabled.
8. Generated media resolves through the configured presigned/public asset origin.
9. Human approval continues through adaptation/media/package rather than skipping downstream checks.
10. Outbox payload validates as `content-package/1.0`.
11. Autoposter accepts the package and returns an external identifier.
12. Re-sending the same delivery does not create a duplicate on the Autoposter side.

## Next product layers

After this vertical production path is stable, the highest-value additions are:

- Knowledge Base / RAG from project files and approved materials;
- AI-generated content plans/calendar built from the active rubric system;
- specialized generation schemas for articles, commercial proposals, posts and video scripts;
- performance metrics returned from Autoposter;
- feedback learning by brand, rubric, hook, format and visual style;
- measured model/prompt routing by quality, latency and cost;
- transactional queue outbox so DB commits and Celery dispatch cannot diverge.

The long-term moat is the closed learning loop: brand/strategy decisions + generation lineage + version history + source provenance + human feedback + downstream performance.
