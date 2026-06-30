"""Agency OS — FastAPI application entry point.

Registers CORS middleware, auth middleware, and all routers.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import config
from .routers import (
    auth,
    content,
    conversations,
    health,
    integrations,
    leads,
    projects,
    publications,
    reports,
    settings,
    users,
)

app = FastAPI(
    title=config.app_name,
    version=config.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(projects.router)
app.include_router(leads.router)
app.include_router(conversations.router)
app.include_router(content.router)
app.include_router(publications.router)
app.include_router(reports.router)
app.include_router(integrations.router)
app.include_router(settings.router)

