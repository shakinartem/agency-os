"""Content Factory — FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import config
from .routers import auth, content, factory, health, knowledge, model_routing, performance, projects, settings, strategy, users

app = FastAPI(
    title=config.app_name,
    version=config.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Content Factory runtime. Legacy CRM/dialog/report routes remain in the repository for
# safe migration rollback, but are deliberately not mounted in the application.
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(projects.router)
app.include_router(content.router)
app.include_router(factory.router)
app.include_router(strategy.router)
app.include_router(knowledge.router)
app.include_router(performance.router)
app.include_router(model_routing.router)
app.include_router(settings.router)
