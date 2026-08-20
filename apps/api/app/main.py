"""Content Factory — FastAPI application entry point."""
from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from .config import config
from .routers import audit, auth, content, factory, health, knowledge, model_routing, performance, projects, settings, strategy, users

app = FastAPI(
    title=config.app_name,
    version=config.app_version,
    docs_url="/docs" if config.api_docs_enabled else None,
    redoc_url="/redoc" if config.api_docs_enabled else None,
    openapi_url="/openapi.json" if config.api_docs_enabled else None,
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.allowed_hosts)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Performance-Token", "X-Request-ID"],
)


@app.middleware("http")
async def security_and_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    if request.method.upper() not in {"GET", "HEAD", "OPTIONS"} and request.cookies.get(config.session_cookie_name):
        origin = request.headers.get("origin")
        if not origin or origin not in set(config.cors_origins):
            response = JSONResponse(status_code=403, content={"detail": "Invalid request origin"})
            response.headers["X-Request-ID"] = request_id
            return response
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if config.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# Content Factory runtime. Legacy CRM/dialog/report routes remain in the repository for
# safe migration rollback, but are deliberately not mounted in the application.
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(audit.router)
app.include_router(users.router)
app.include_router(projects.router)
app.include_router(content.router)
app.include_router(factory.router)
app.include_router(strategy.router)
app.include_router(knowledge.router)
app.include_router(performance.router)
app.include_router(model_routing.router)
app.include_router(settings.router)
