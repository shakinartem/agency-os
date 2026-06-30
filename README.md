# Agency OS

**Agency OS** is a unified orchestration platform that connects, normalises, and manages five existing AI/automation bots under a single web interface and API.

Instead of running five separate scripts, admins get one dashboard to manage projects, leads, content, publishing, and reports across all bots.

---

## What is Agency OS?

Agency OS acts as the central brain over five independent repositories:

1. **[bot1_crm](https://github.com/shakinartem/bot1_crm)** — Telegram CRM bot (lead capture & management)
2. **[bot2_consultation_ai](https://github.com/shakinartem/bot2_consultation_ai)** — AI consultation engine (chat + intent detection)
3. **[bot3_content_farm](https://github.com/shakinartem/bot3_content_farm)** — AI content generation (posts, articles, scripts)
4. **[autoposter_bot](https://github.com/shakinartem/autoposter_bot)** — Cross-platform auto-publisher (Telegram, Instagram, Facebook, VK)
5. **[bot5_otchet](https://github.com/shakinartem/bot5_otchet)** — Reporting & analytics bot

Agency OS provides:
- A **shared database** (projects, leads, conversations, content, publications, reports, integrations)
- A **REST API** (FastAPI) with JWT auth + role-based access
- A **web dashboard** (Next.js) for non-technical users
- **Integration adapters** that translate between each bot & the core schema
- **Scheduled background tasks** (Celery) for sync, push, and reporting

---

## Integrated Repositories

| # | Bot | GitHub | Role in Agency OS |
|---|-----|--------|-------------------|
| 1 | bot1_crm | [shakinartem/bot1_crm](https://github.com/shakinartem/bot1_crm) | Lead & contact sync |
| 2 | bot2_consultation_ai | [shakinartem/bot2_consultation_ai](https://github.com/shakinartem/bot2_consultation_ai) | AI dialogs & intent |
| 3 | bot3_content_farm | [shakinartem/bot3_content_farm](https://github.com/shakinartem/bot3_content_farm) | Content generation |
| 4 | autoposter_bot | [shakinartem/autoposter_bot](https://github.com/shakinartem/autoposter_bot) | Publishing scheduler |
| 5 | bot5_otchet | [shakinartem/bot5_otchet](https://github.com/shakinartem/bot5_otchet) | Reports & analytics |

---

## Architecture (text diagram)

```
┌─────────────────────────────────────────────────────────────────┐
│                        Agency OS Monorepo                        │
├────────────────┬────────────────┬───────────────────────────────┤
│   Frontend     │   Backend      │   Background                  │
│   Next.js 14   │   FastAPI      │   Celery Worker               │
│   + React Query│   + SQLAlchemy │   + Redis Broker              │
│   + shadcn/ui  │   + Alembic    │                               │
└────────┬───────┴───────┬────────┴───────────┬───────────────────┘
         │               │                     │
         ▼               ▼                     ▼
   ┌─────────┐   ┌──────────┐   ┌──────────────────────┐
   │ Nginx / │   │ Postgres │   │ Redis                │
   │ Traefik │   │ 15       │   │ 7 (celery broker)    │
   └─────────┘   └──────────┘   └──────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────┐
│                   Adapter Layer                        │
│  integrations/crm  ──► CRMIntegration                   │
│  integrations/consultation  ──► ConsultationIntegration │
│  integrations/content  ──► ContentFarmIntegration       │
│  integrations/autoposter  ──► AutoposterIntegration     │
│  integrations/reports  ──► ReportsIntegration           │
└──────────────────────┬─────────────────────────────────┘
                       │ HTTP / Webhook
                       ▼
   ┌───────────────┬───────────────┬───────────────┬───────────────┬───────────────┐
   │  bot1_crm     │bot2_consultation│bot3_content   │autoposter_bot │bot5_otchet     │
   │  (Telegram)   │  (AI chat)      │_farm (AI)     │ (multi-platform│ (reports)      │
   └───────────────┴───────────────┴───────────────┴───────────────┴───────────────┘
```

**Data flow:**

1. Each bot pushes/pulls data via its adapter (`pull()` / `push()`)
2. Adapters normalize raw bot formats into core ORM models
3. Workers run on schedule or on-demand (manual sync button in UI)
4. Frontend reads/writes via FastAPI REST endpoints
5. All state is persisted in Postgres; async tasks use Redis + Celery

---

## Project Structure

```
agency-os/
├── apps/
│   ├── web/                  # Next.js 14 frontend
│   │   ├── src/app/
│   │   │   ├── (dashboard)/
│   │   │   │   ├── layout.tsx        # Protected shell
│   │   │   │   ├── dashboard/page.tsx
│   │   │   │   ├── clinics/page.tsx
│   │   │   │   ├── crm/page.tsx
│   │   │   │   ├── dialogs/page.tsx
│   │   │   │   ├── content/page.tsx
│   │   │   │   ├── publishing/page.tsx
│   │   │   │   ├── reports/page.tsx
│   │   │   │   ├── integrations/page.tsx
│   │   │   │   ├── users/page.tsx
│   │   │   │   │   └── settings/page.tsx
│   │   │   └── login/page.tsx
│   │   ├── src/components/
│   │   │   ├── layout/        # Sidebar, TopBar, DashboardLayout
│   │   │   └── ui/            # Button, Card, Badge, Input, Table, Avatar…
│   │   ├── src/context/       # AuthContext, ProjectContext
│   │   └── src/lib/           # api.ts (typed fetch), utils.ts (cn)
│   │
│   ├── api/                  # FastAPI backend
│   │   └── app/
│   │       ├── main.py       # CORS + all routers
│   │       ├── config.py     # AppConfig (env)
│   │       ├── database.py   # AsyncSession DI
│   │       ├── auth.py       # JWT + password hashing
│   │       ├── dependencies.py  # get_current_user, require_role
│   │       ├── schemas/      # Pydantic request/response DTOs
│   │       │   ├── auth, user, project, lead, conversation,
│   │       │   ├── content, publication, report, integration, settings
│   │       └── routers/      # Route handlers
│   │           ├── auth, users, projects, leads, conversations,
│   │           ├── content, publications, reports, integrations, settings
│   │
│   └── worker/               # Celery background worker
│       └── tasks/worker.py   # Celery app + placeholder tasks
│
├── packages/
│   ├── shared/               # Shared Python types & enums
│   │   └── src/types.py
│   └── database/             # SQLAlchemy ORM + Alembic
│       ├── alembic/
│       │   └── versions/
│       │       ├── 0001_create_all_tables.py
│       │       └── 0002_add_password_hash.py
│       ├── models/           # 13 ORM models
│       ├── enums.py
│       ├── base.py
│       └── config.py
│
├── integrations/
│   ├── base.py               # BaseIntegration (abstract adapter)
│   ├── crm/__init__.py       # CRMIntegration (bot1_crm)
│   ├── consultation/__init__.py  # ConsultationIntegration (bot2)
│   ├── content/__init__.py   # ContentFarmIntegration (bot3)
│   ├── autoposter/__init__.py    # AutoposterIntegration
│   └── reports/__init__.py   # ReportsIntegration (bot5)
│
├── docker/
│   ├── Dockerfile.api        # Python 3.12-slim + FastAPI + Uvicorn
│   ├── Dockerfile.web        # Node 20-alpine + Next.js
│   └── Dockerfile.worker     # Python 3.12-slim + Celery
│
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Run Full Stack (Docker Compose)

The fastest way to run the entire Agency OS stack locally.

### Prerequisites

- Docker + Docker Compose
- At least 4 GB RAM available for Docker

### 1. Configure environment

```bash
cp .env.example .env
```

The default values in `.env` work out of the box for a local Docker setup.
If you need to change ports, edit:

```env
API_PORT=8010          # API port on host
NEXT_PUBLIC_API_URL=http://localhost:8010  # Frontend -> API
```

### 2. Start everything

```powershell
docker compose up --build
```

This single command will:

1. Start **postgres** (port `5433`) and **redis** (port `6380`)
2. Run database migrations via the `migrate` service
3. Start **api** (port `8010`), **web** (port `3010`), and **worker**

### 3. Verify

| Service | URL |
|---------|-----|
| API docs | http://localhost:8010/docs |
| API health | http://localhost:8010/health |
| Web UI | http://localhost:3010 |
| Postgres | `localhost:5433` (user: `agency`, db: `agency_os`) |
| Redis | `localhost:6380` |

Or run the included smoke-test:

```powershell
.\scripts\smoke-test.ps1
```

### 4. Stop

```powershell
docker compose down
```

To also delete the database volume (fresh start):

```powershell
docker compose down -v
```

---

## How to Run Locally (without Docker)

---

## How to Configure .env

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | General app secret | `change-me-in-production` |
| `JWT_SECRET` | JWT signing key | `change-me-in-production` |
| `APP_ENV` | `development` / `production` | `development` |
| `APP_DEBUG` | Enable debug mode | `true` |
| `DATABASE_URL` | Postgres async DSN | `postgresql+asyncpg://agency:agency_secret@postgres:5433/agency_os` |
| `REDIS_URL` | Redis broker URL | `redis://redis:6380/0` |
| `API_URL` | Internal API URL (for worker) | `http://api:8010` |
| `API_PORT` | API port mapping | `8010` |
| `NEXT_PUBLIC_API_URL` | Frontend API URL (browser) | `http://localhost:8010` |
| `CRM_URL` | bot1_crm base URL | *(empty = mock)* |
| `CRM_TOKEN` | bot1_crm API token | *(empty)* |
| `CONSULTATION_URL` | bot2_consultation_ai base URL | *(empty)* |
| `CONSULTATION_TOKEN` | bot2 token | *(empty)* |
| `CONTENT_URL` | bot3_content_farm base URL | *(empty)* |
| `CONTENT_TOKEN` | bot3 token | *(empty)* |
| `AUTOPOSTER_URL` | autoposter_bot base URL | *(empty)* |
| `AUTOPOSTER_TOKEN` | autoposter token | *(empty)* |
| `REPORTS_URL` | bot5_otchet base URL | *(empty)* |
| `REPORTS_TOKEN` | bot5 token | *(empty)* |

---

## How to Run Migrations

Migrations live in `packages/database/alembic/versions/`.

**Current migrations:**
- `0001_create_all_tables.py` -- all 13 tables
- `0002_add_password_hash.py` -- `password_hash` column on `users`

### Run:

```bash
# Upgrade to latest:
alembic upgrade head

# Downgrade one step:
alembic downgrade -1

# Generate a new migration after model changes:
alembic revision --autogenerate -m "describe change"
```

> **Note:** Alembic `env.py` is pre-configured to import all models from `packages/database/models/` so `--autogenerate` detects schema changes automatically.

---

## How to Seed Database

Seeds are stored as Python scripts in `packages/database/seeds/`.

To seed:

```bash
python packages/database/seeds/run.py
```

*(Seeder script is a future task -- current repo contains empty `__init__.py` placeholder.)*

---

## How to Connect Real Integrations

Each integration has two sides:

### A. Backend adapter (`integrations/<service>/__init__.py`)

Each adapter extends `BaseIntegration` (from `integrations/base.py`) and implements:
- `pull()` -> fetch records from bot's API
- `push(data)` -> send data to bot's API
- `normalize(raw_data)` -> map bot format -> Agency OS DTO

To connect a real bot:

1. Set the bot's URL in `.env`:
   ```env
   CRM_URL=https://your-bot1-instance.herokuapp.com/api
   CRM_TOKEN=eyJhbGciOi...
   ```
2. Implement `pull()` / `push()` in `integrations/crm/__init__.py` using `httpx`:
   ```python
   async def pull(self):
       client = await self._get_http_client()
       resp = await client.get("/leads", params={"status": "new"})
       resp.raise_for_status()
       return [self.normalize(r) for r in resp.json()]
   ```
3. The `healthcheck()` method (already in `BaseIntegration`) will ping `/health` on the bot.

### B. Frontend (Integrations page)

The `/integrations` page already calls:
- `POST /integrations/:id/healthcheck`
- `POST /integrations/:id/sync`
- `GET /integrations/:id/logs`

So once the backend stores `IntegrationConfig` rows, the UI works out of the box.

---

## What Is Implemented

### Backend (FastAPI)

- **Auth**: JWT login/logout/me, bcrypt password hashing, bearer middleware
- **Role-based access**: `admin`, `manager`, `viewer` -- enforced via `require_role()`
- **CRUD API**:
  - `GET/POST /projects`
  - `GET/POST/PUT/DELETE /leads`, `GET/POST /leads/:id/events`
  - `GET/POST/PUT/DELETE /conversations`, `GET/POST /conversations/:id/messages`
  - `GET/POST/PUT/DELETE /content`, `GET /content/plans`
  - `GET/POST/PUT/DELETE /publications`
  - `GET /reports/snapshots`
  - `GET/POST/PUT/DELETE /integrations`, `POST /:id/healthcheck`, `POST /:id/sync`, `GET /:id/logs`
  - `GET/POST/PUT/DELETE /users`
  - `GET/PUT/DELETE /settings` (key-value)
- **Database**: 13 SQLAlchemy models, 2 Alembic migrations, async session DI
- **CORS**: Configurable via `CORS_ORIGINS`
- **OpenAPI docs**: auto-generated at `/docs`

### Frontend (Next.js 14)

- **Layout**: fixed Sidebar (10 sections) + TopBar (project selector, user avatar, logout, integration badges)
- **Pages**: Dashboard, Clinics, CRM, AI Dialogs, Content Studio, Publishing, Reports, Integrations, Users, Settings
- **Auth**: context + protected route group, redirect to `/login`
- **Data fetching**: React Query `useQuery` / `useMutation` with typed `ApiClient`
- **UI**: shadcn/ui components (Button, Card, Badge, Input, Table, Avatar, Separator) + Tailwind

### Integrations

- Abstract `BaseIntegration` class with `healthcheck()`, `sync()`, `pull()`, `push()`, `normalize()`, `log_error()`
- 5 mock adapters ready to be connected to real APIs:
  - `CRMIntegration` (bot1_crm)
  - `ConsultationIntegration` (bot2_consultation_ai)
  - `ContentFarmIntegration` (bot3_content_farm)
  - `AutoposterIntegration` (autoposter_bot)
  - `ReportsIntegration` (bot5_otchet)

---

## Roadmap

- [ ] **Real adapter implementations** -- replace mock data with `httpx` calls to actual bot APIs
- [ ] **Seeder scripts** -- populate DB with demo projects, users, and leads
- [ ] **Celery beat scheduler** -- periodic sync tasks for each integration
- [ ] **Webhook receivers** -- bots push events to Agency OS webhooks
- [ ] **File uploads** -- media library for content & publications
- [ ] **Audit log** -- track all CRUD changes
- [ ] **Multi-tenancy** -- row-level security per project
- [ ] **Docker Compose full stack** -- one-command `docker compose up` for everything
- [ ] **CLI tool** -- `agency-os` command for migrations, seeds, users
- [ ] **Unit & integration tests** -- pytest + Playwright
- [ ] **CI/CD** -- GitHub Actions build + deploy

---

## License

MIT


 
