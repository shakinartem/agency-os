from __future__ import annotations

import json
from typing import Any


def generation_prompt(*, objective: str, platforms: list[str], content_mix: dict[str, int], brand: dict[str, Any], rubrics: list[dict[str, Any]], knowledge: list[dict[str, Any]], research: list[dict[str, Any]]) -> str:
    return f"""Plan a content production batch.
Objective: {objective}
Platforms: {platforms}
Exact content mix (MUST match exactly): {json.dumps(content_mix, ensure_ascii=False)}
Brand: {json.dumps(brand, ensure_ascii=False)}
Active rubrics: {json.dumps(rubrics, ensure_ascii=False)}
Private first-party knowledge: {json.dumps(knowledge, ensure_ascii=False)}
Optional web research: {json.dumps(research, ensure_ascii=False)}

Rules:
- every topic must be materially distinct;
- distribute items across useful audience stages and rubrics;
- do not invent company facts;
- rubric_id must be one of the supplied rubric IDs or null;
- content_type counts must match the requested mix exactly.

Return exactly:
{{
  "strategy_summary": "...",
  "items": [
    {{
      "content_type": "post",
      "topic": "...",
      "goal": "...",
      "rubric_id": null,
      "angle": "...",
      "audience_stage": "...",
      "brief": "..."
    }}
  ]
}}"""


def revision_prompt(*, objective: str, content_mix: dict[str, int], rubrics: list[dict[str, Any]], errors: list[str], plan: dict[str, Any]) -> str:
    return f"""Fix the plan so it passes every validation error.
Objective: {objective}
Exact content mix: {json.dumps(content_mix, ensure_ascii=False)}
Allowed rubrics: {json.dumps(rubrics, ensure_ascii=False)}
Validation errors: {json.dumps(errors, ensure_ascii=False)}
Current plan: {json.dumps(plan, ensure_ascii=False)}
Return the same schema with exactly {sum(content_mix.values())} distinct items."""
