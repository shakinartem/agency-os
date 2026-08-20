"""Shared prompt cohort identity for routing evidence."""
from __future__ import annotations

import os

DEFAULT_CONTENT_PROMPT_VERSION = "factory-v3-knowledge-research-media"


def current_content_prompt_version() -> str:
    value = os.getenv("CONTENT_PROMPT_VERSION", DEFAULT_CONTENT_PROMPT_VERSION).strip()
    return value or DEFAULT_CONTENT_PROMPT_VERSION
