from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any


def _normalize_topic(value: str) -> str:
    return re.sub(r"[^\w\s]+", " ", value.casefold()).strip()


def validate_batch_plan(
    items: list[dict[str, Any]],
    content_mix: dict[str, int],
    allowed_rubric_ids: set[str],
    *,
    min_exploration_share: float = 0.0,
) -> list[str]:
    errors: list[str] = []
    expected_total = sum(content_mix.values())
    if len(items) != expected_total:
        errors.append(f"expected {expected_total} items, got {len(items)}")
    actual = Counter(str(item.get("content_type") or "").strip().lower() for item in items)
    for content_type, count in content_mix.items():
        if actual.get(content_type, 0) != count:
            errors.append(f"content_type {content_type}: expected {count}, got {actual.get(content_type, 0)}")
    unexpected = {key: value for key, value in actual.items() if key not in content_mix and value}
    if unexpected:
        errors.append(f"unexpected content types: {unexpected}")
    topics = [_normalize_topic(str(item.get("topic") or "")) for item in items]
    if any(not topic for topic in topics):
        errors.append("every item must have a non-empty topic")
    if len(set(topics)) != len([topic for topic in topics if topic]):
        errors.append("topics must be distinct")
    for item in items:
        rubric_id = str(item.get("rubric_id") or "").strip()
        if rubric_id and rubric_id not in allowed_rubric_ids:
            errors.append(f"unknown rubric_id: {rubric_id}")

    if min_exploration_share > 0 and items:
        share = max(0.0, min(1.0, float(min_exploration_share)))
        required = max(1, math.ceil(len(items) * share))
        modes = [str(item.get("learning_mode") or "").strip().lower() for item in items]
        unknown_modes = [mode for mode in modes if mode not in {"exploit", "explore"}]
        if unknown_modes:
            errors.append("every performance-informed item must declare learning_mode=exploit|explore")
        exploration_count = sum(mode == "explore" for mode in modes)
        if exploration_count < required:
            errors.append(f"exploration floor: expected at least {required} explore items, got {exploration_count}")
    return errors
