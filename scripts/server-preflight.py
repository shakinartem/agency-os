#!/usr/bin/env python3
"""Fail-fast production configuration validation without importing application code."""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from pathlib import Path
from urllib.parse import urlparse


def load_env(path: Path) -> dict[str, str]:
    values = dict(os.environ)
    if path.exists():
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values.setdefault(key.strip(), value.strip().strip('"\''))
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    args = parser.parse_args()
    values = load_env(Path(args.env))
    errors: list[str] = []
    warnings: list[str] = []

    required = [
        "FACTORY_DOMAIN", "FACTORY_ASSETS_DOMAIN", "DATABASE_URL", "POSTGRES_PASSWORD",
        "MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD", "MINIO_APP_USER", "MINIO_APP_PASSWORD", "SECRET_KEY",
        "AUTOPOSTER_TOKEN", "PERFORMANCE_INGEST_TOKEN",
    ]
    for key in required:
        if not values.get(key):
            errors.append(f"{key} is required")

    for key in ("SECRET_KEY", "POSTGRES_PASSWORD", "MINIO_ROOT_PASSWORD", "MINIO_APP_PASSWORD", "AUTOPOSTER_TOKEN", "PERFORMANCE_INGEST_TOKEN"):
        value = values.get(key, "")
        if value in {"change-me-in-production", "agency_secret", "contentfactory-secret"}:
            errors.append(f"{key} still uses a development default")
        if value and len(value) < 24:
            errors.append(f"{key} is too short (<24 chars)")

    db = values.get("DATABASE_URL", "")
    if db:
        parsed = urlparse(db.replace("postgresql+asyncpg://", "postgresql://"))
        if parsed.scheme != "postgresql": errors.append("DATABASE_URL must be PostgreSQL")
        if parsed.hostname == "postgres" and parsed.password and values.get("POSTGRES_PASSWORD") and parsed.password != values.get("POSTGRES_PASSWORD"):
            errors.append("DATABASE_URL password does not match POSTGRES_PASSWORD for the bundled PostgreSQL service")
        if parsed.hostname not in {"postgres", "localhost", "127.0.0.1"}:
            warnings.append("DATABASE_URL host is external; ensure TLS/private networking")

    if values.get("APP_DEBUG", "false").lower() in {"1", "true", "yes", "on"}:
        errors.append("APP_DEBUG must be false for production")
    if values.get("SESSION_COOKIE_SECURE", "true").lower() not in {"1", "true", "yes", "on"}:
        errors.append("SESSION_COOKIE_SECURE must be true")

    if not values.get("LLM_API_KEY"):
        warnings.append("LLM_API_KEY is empty: generation will fail explicitly")

    budgets_enabled = any(
        float(values.get(name, "0") or 0) > 0
        for name in ("GENERATION_MAX_RUN_COST_USD", "GENERATION_DAILY_BUDGET_USD", "GENERATION_MONTHLY_BUDGET_USD")
    )
    pricing_required = values.get("GENERATION_BUDGET_REQUIRE_PRICING", "true").lower() in {"1", "true", "yes", "on"}
    default_llm_priced = (
        float(values.get("LLM_INPUT_COST_PER_1M_USD", "0") or 0) > 0
        or float(values.get("LLM_OUTPUT_COST_PER_1M_USD", "0") or 0) > 0
    )
    model_pricing = values.get("LLM_MODEL_PRICING_JSON", "{}").strip()
    any_llm_pricing = default_llm_priced or model_pricing not in {"", "{}"}
    if not any_llm_pricing:
        message = "LLM model pricing is not configured; cost guardrails cannot make priced decisions"
        (errors if budgets_enabled and pricing_required else warnings).append(message)
    if values.get("FACTORY_IMAGE_ENABLED", "true").lower() in {"1", "true", "yes", "on"}:
        if float(values.get("IMAGE_COST_PER_GENERATION_USD", "0") or 0) <= 0:
            message = "IMAGE_COST_PER_GENERATION_USD is required for fully priced image budgets"
            (errors if budgets_enabled and pricing_required else warnings).append(message)
    if values.get("FACTORY_RESEARCH_ENABLED", "false").lower() in {"1", "true", "yes", "on"}:
        if float(values.get("TAVILY_COST_PER_REQUEST_USD", "0") or 0) <= 0:
            message = "TAVILY_COST_PER_REQUEST_USD is required for fully priced research budgets"
            (errors if budgets_enabled and pricing_required else warnings).append(message)

    if errors:
        print("SERVER PREFLIGHT FAILED", file=sys.stderr)
        for error in errors: print(f"ERROR: {error}", file=sys.stderr)
        for warning in warnings: print(f"WARN: {warning}", file=sys.stderr)
        return 1
    print("SERVER PREFLIGHT OK")
    for warning in warnings: print(f"WARN: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
