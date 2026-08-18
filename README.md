# Qualive Content Factory

AI production system for strategy, grounded content generation, human review, media QA, Autoposter handoff and downstream learning.

The product is deliberately split into two services:

- **Content Factory** decides **what should be published**.
- **Autoposter** owns platform rendering, scheduling, durable media and publication.

The operating loop is:

`Brand Brain + Project Knowledge → Strategy → Production → QA → Review → Autoposter → Performance → Learning → Better Production`

## Product workspaces

- **Factory** — one-off production runs from a high-level objective.
- **Batches** — validated multi-item plans with exact content mix and independent child runs.
- **Brand Brain** — positioning, audience, products, tone, rules and forbidden claims.
- **Knowledge Base** — project-isolated first-party RAG with bounded uploads, dedupe, archive/restore and retrieval lineage.
- **Strategy & Rubrics** — AI-generated reusable content lanes with critic/revision.
- **Content Review** — canonical content, immutable versions, QA, evidence, variants, media and structured review decisions.
- **Autoposter Outbox** — strict `content-package/1.0` deliveries with idempotent retry.
- **Performance** — downstream outcomes, performance-informed planning and generation economics.
- **Model Router** — shadow/live evidence and conservative per-stage model selection.

## Production pipeline

`Project Knowledge → optional live research → typed draft → evaluate/revise → humanize → platform adaptation → image generation → vision QA → final QA / human review → content-package/1.0 → Autoposter`

Every meaningful stage is persisted. Provider failures never masquerade as success.

## First-party Knowledge / RAG

Knowledge documents are project-isolated and split into searchable chunks. The first version uses PostgreSQL full-text search and GIN indexes instead of introducing a separate vector service prematurely.

Supported bounded ingestion includes TXT, Markdown, JSON, PDF and DOCX. Private Knowledge references are available to internal review/audit but are deliberately excluded from the external Autoposter package.

## Typed content contracts

The factory does not treat every format as the same generic text prompt.

- **Post** — hook, body, CTA and takeaways.
- **Article** — outline, body, metadata, SEO and FAQ.
- **Commercial proposal** — recipient context, problem, desired outcome, solution, scope, deliverables, process, assumptions/risks and next step. Pricing is never invented.
- **Carousel** — coherent multi-slide narrative and visual ideas.
- **Video script** — duration, scenes, voiceover/on-screen copy and editing instructions.

Contract errors are fed back into revision and block auto-approval.

## Performance learning

Autoposter sends idempotent metric snapshots back to Factory. Only the newest snapshot per downstream publication contributes to current totals, so periodic snapshots are not double-counted.

Historical performance is a **prior**, not automatic truth:

- outcome priority is conversions → leads → clicks → views;
- recommendations are sample-gated;
- rubrics, content types and platforms are compared against project baseline;
- performance-informed Batches retain at least **25% exploration**;
- the exploration floor is enforced deterministically, not only through prompt wording;
- every planned item records `exploit` or `explore` lineage.

## Human review data

Review decisions are structured training/evaluation signals, not just UI button clicks. The system stores the exact content version, reviewer, action, reason codes and optional note.

Examples of reason codes include weak hook, generic AI style, off-brand language, unsupported claim and excessive sales pressure.

## Generation economics

Provider telemetry is stored in `GenerationStep` traces:

- provider and model;
- input/output/total tokens when available;
- request latency;
- estimated cost only when operator-configured pricing exists.

The application does **not** hard-code vendor pricing. Unknown prices remain visible as unpriced requests instead of being treated as free.

Default-model rates can be configured with:

```env
LLM_INPUT_COST_PER_1M_USD=0
LLM_OUTPUT_COST_PER_1M_USD=0
```

Per-model rates for Model Router candidates use:

```env
LLM_MODEL_PRICING_JSON={}
```

## Conservative Model Router

Model Router is intentionally staged to avoid switching production traffic from weak or non-causal evidence.

### 1. Shadow evidence

Default mode:

```env
MODEL_ROUTER_MODE=shadow
```

Production output always comes from the default model. On a small, retry-stable sample of run/stage families, Factory also calls one under-sampled candidate in parallel. A blinded A/B judge compares the control and candidate.

Candidate output is **never** used downstream. The trace keeps only compact hashes, quality scores and provider telemetry rather than storing a second unpublished content body.

### 2. Controlled live exploration

A candidate must first clear total-sample and quality gates before it is even allowed to receive the small live exploration share in `active` mode.

```env
MODEL_ROUTER_MIN_SAMPLES_PER_MODEL=10
MODEL_ROUTER_QUALITY_FLOOR=0.84
MODEL_ROUTER_EXPLORATION_RATE=0.10
```

### 3. Full production routing

A candidate cannot become the full-routing winner merely because an offline judge likes it.

For content-producing stages (`draft`, `evaluate`, `revise`, `humanize`, `adapt`) it also needs live use **and real downstream performance snapshots**:

```env
MODEL_ROUTER_MIN_LIVE_SAMPLES=3
MODEL_ROUTER_MIN_DOWNSTREAM_SAMPLES=3
```

Strategy and batch-planning stages do not pretend to have direct publication-level causal attribution; they retain quality/live gates without manufacturing a false downstream relationship.

The Model Router UI separately displays shadow samples, live samples, shadow leader, live recommendation and production eligibility.

## Media

Generated media is reviewed before acceptance and stored in S3-compatible object storage. Local development uses MinIO. Buckets are private by default and delivery URLs are presigned unless a deliberate public CDN is configured.

Autoposter copies accepted media into its own storage boundary, so publication does not depend on an expiring Factory URL.

## Autoposter contract

Factory exports strict `content-package/1.0` payloads. Delivery is delivery-scoped and idempotent.

The separate Autoposter bridge owns:

- package ingestion;
- workspace mapping;
- durable media copying;
- platform rendering/scheduling;
- publication;
- analytics feedback.

Use `scripts/bridge-smoke.py` to validate acceptance/replay/conflict semantics without spending LLM credits.

## Reliability boundaries

- PostgreSQL state is committed before broker dispatch.
- A durable task outbox closes the DB → Redis/Celery gap.
- Provider failures are explicit.
- Manual edits create immutable versions.
- Private Knowledge lineage does not leave Factory packages.
- Performance ingestion is disabled until an explicit shared token is configured.
- Model Router fails open to the default model.
- Shadow candidate failures never replace or fail an otherwise successful production response.

## Local start

```bash
cp .env.example .env
docker compose up -d --build
```

Then open the configured Next.js frontend and API docs.

Before unattended publishing or active model routing, complete the real deployment acceptance checklist in the verified bundle `DEPLOY.md`.

## Validation

PR CI covers:

- Python compilation;
- Alembic migrations on PostgreSQL;
- API and worker imports/tests;
- Knowledge isolation/retrieval;
- content-package and typed-format contracts;
- task outbox behavior;
- performance snapshot dedupe and learning policy;
- generation economics;
- Model Router policy, shadow/live evidence and downstream gates;
- Next.js production build;
- Docker Compose contract.

## Product moat

The long-term advantage is not another generic agent UI. It is the accumulated closed-loop dataset:

`first-party knowledge + strategy lineage + prompt/model/stage lineage + immutable versions + human decisions + provider economics + downstream outcomes`

That dataset allows the system to learn **what content production decision is most likely to produce the desired business action, at what cost, and with what confidence**.
