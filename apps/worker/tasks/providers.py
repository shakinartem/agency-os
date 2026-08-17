"""External provider adapters for Content Factory workers.

All integrations fail explicitly: a missing provider configuration returns a skipped result
rather than fabricated research/media success.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import uuid
from typing import Any

import boto3
import httpx

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-5.6")

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
TAVILY_API_URL = os.getenv("TAVILY_API_URL", "https://api.tavily.com/search")
RESEARCH_MAX_RESULTS = int(os.getenv("RESEARCH_MAX_RESULTS", "5"))
RESEARCH_MIN_SCORE = float(os.getenv("RESEARCH_MIN_SCORE", "0.45"))

IMAGE_API_URL = os.getenv("IMAGE_API_URL") or f"{LLM_BASE_URL}/images/generations"
IMAGE_API_KEY = os.getenv("IMAGE_API_KEY") or LLM_API_KEY
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gpt-image-1.5")
IMAGE_SIZE = os.getenv("IMAGE_SIZE", "1024x1024")
MEDIA_QUALITY_THRESHOLD = float(os.getenv("MEDIA_QUALITY_THRESHOLD", "0.86"))
MAX_IMAGE_ATTEMPTS = int(os.getenv("MAX_IMAGE_ATTEMPTS", "2"))

S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")
S3_PUBLIC_ENDPOINT_URL = os.getenv("S3_PUBLIC_ENDPOINT_URL")
S3_PUBLIC_BASE_URL = os.getenv("S3_PUBLIC_BASE_URL")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_REGION = os.getenv("S3_REGION", "us-east-1")
S3_BUCKET = os.getenv("S3_BUCKET", "content-assets")
MEDIA_URL_TTL_SECONDS = int(os.getenv("MEDIA_URL_TTL_SECONDS", str(7 * 24 * 60 * 60)))

AUTOPOSTER_URL = os.getenv("AUTOPOSTER_URL")
AUTOPOSTER_TOKEN = os.getenv("AUTOPOSTER_TOKEN")


def parse_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
    return {"body": text}


async def chat_json(system: str, prompt: str) -> dict[str, Any]:
    if not LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY is not configured")
    headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(f"{LLM_BASE_URL}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    return parse_json(data["choices"][0]["message"]["content"])


async def research_web(query: str) -> dict[str, Any]:
    """Ground a task in live sources using Tavily Search when configured."""
    if not TAVILY_API_KEY:
        return {"status": "skipped", "reason": "TAVILY_API_KEY is not configured", "sources": []}

    headers = {"Authorization": f"Bearer {TAVILY_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "query": query,
        "search_depth": "basic",
        "max_results": RESEARCH_MAX_RESULTS,
        "include_answer": False,
        "include_raw_content": False,
    }
    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(TAVILY_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    sources = []
    for index, result in enumerate(data.get("results") or [], 1):
        score = float(result.get("score") or 0)
        if score < RESEARCH_MIN_SCORE:
            continue
        sources.append({
            "id": f"S{index}",
            "title": result.get("title") or "Untitled source",
            "url": result.get("url"),
            "snippet": result.get("content") or "",
            "score": score,
        })
    return {
        "status": "passed" if sources else "skipped",
        "query": query,
        "sources": sources,
        "request_id": data.get("request_id"),
        "response_time": data.get("response_time"),
    }


async def generate_image_bytes(prompt: str) -> dict[str, Any]:
    if not IMAGE_API_KEY:
        return {"status": "skipped", "reason": "IMAGE_API_KEY/LLM_API_KEY is not configured"}

    headers = {"Authorization": f"Bearer {IMAGE_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": IMAGE_MODEL, "prompt": prompt, "size": IMAGE_SIZE}
    async with httpx.AsyncClient(timeout=240) as client:
        response = await client.post(IMAGE_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        first = (data.get("data") or [{}])[0]
        if first.get("b64_json"):
            return {
                "status": "passed",
                "bytes": base64.b64decode(first["b64_json"]),
                "mime_type": "image/png",
                "provider_payload": {"revised_prompt": first.get("revised_prompt")},
            }
        if first.get("url"):
            image_response = await client.get(first["url"])
            image_response.raise_for_status()
            return {
                "status": "passed",
                "bytes": image_response.content,
                "mime_type": image_response.headers.get("content-type", "image/png").split(";")[0],
                "provider_payload": {"revised_prompt": first.get("revised_prompt")},
            }
    return {"status": "skipped", "reason": "Image provider returned neither b64_json nor url"}


async def review_image(image_bytes: bytes, mime_type: str, content_context: str, visual_prompt: str) -> dict[str, Any]:
    """Vision QA. Provider incompatibility leaves the asset in review, never fake-approved."""
    if not LLM_API_KEY:
        return {"overall": 0.0, "passed": False, "notes": ["LLM_API_KEY is not configured for visual QA"]}

    encoded = base64.b64encode(image_bytes).decode("ascii")
    headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "You are a strict art director and visual QA reviewer. Return JSON only."},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Review this generated image for the supplied content. Score 0..1 for relevance, "
                            "artifact_free, brand_fit, composition and text_safety. text_safety must fail if "
                            "there is malformed/unrequested text. Return exactly "
                            '{"overall":0.0,"relevance":0.0,"artifact_free":0.0,"brand_fit":0.0,'
                            '"composition":0.0,"text_safety":0.0,"notes":[]}.'
                            f"\nContent: {content_context}\nVisual prompt: {visual_prompt}"
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}},
                ],
            },
        ],
        "response_format": {"type": "json_object"},
    }
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(f"{LLM_BASE_URL}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        result = parse_json(data["choices"][0]["message"]["content"])
        result["passed"] = (
            float(result.get("overall", 0)) >= MEDIA_QUALITY_THRESHOLD
            and float(result.get("artifact_free", 0)) >= MEDIA_QUALITY_THRESHOLD
            and float(result.get("text_safety", 0)) >= MEDIA_QUALITY_THRESHOLD
        )
        return result
    except Exception as exc:
        return {"overall": 0.0, "passed": False, "notes": [f"visual QA failed: {exc}"]}


def _s3_client(endpoint_url: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name=S3_REGION,
    )


async def store_media(image_bytes: bytes, mime_type: str, content_item_id: str) -> dict[str, Any]:
    """Store an accepted asset privately and return a public or time-limited delivery URL."""
    if not (S3_ENDPOINT_URL and S3_ACCESS_KEY and S3_SECRET_KEY):
        return {"status": "skipped", "reason": "S3 storage is not configured"}

    extension = "jpg" if mime_type in {"image/jpeg", "image/jpg"} else "png"
    key = f"content/{content_item_id}/{uuid.uuid4().hex}.{extension}"

    def _put_and_url() -> tuple[str, str]:
        internal_client = _s3_client(S3_ENDPOINT_URL)
        internal_client.put_object(Bucket=S3_BUCKET, Key=key, Body=image_bytes, ContentType=mime_type)

        if S3_PUBLIC_BASE_URL:
            return f"{S3_PUBLIC_BASE_URL.rstrip('/')}/{key}", "public"

        signing_endpoint = S3_PUBLIC_ENDPOINT_URL or S3_ENDPOINT_URL
        signing_client = _s3_client(signing_endpoint)
        signed_url = signing_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": key},
            ExpiresIn=MEDIA_URL_TTL_SECONDS,
        )
        return signed_url, "presigned"

    url, access_mode = await asyncio.to_thread(_put_and_url)
    return {
        "status": "passed",
        "url": url,
        "key": key,
        "bucket": S3_BUCKET,
        "access_mode": access_mode,
        "expires_in": MEDIA_URL_TTL_SECONDS if access_mode == "presigned" else None,
    }


async def create_reviewed_media(prompt: str, content_context: str, content_item_id: str) -> dict[str, Any]:
    history: list[dict[str, Any]] = []
    current_prompt = prompt
    for attempt in range(1, MAX_IMAGE_ATTEMPTS + 1):
        generated = await generate_image_bytes(current_prompt)
        if generated.get("status") != "passed":
            return {**generated, "attempts": history}

        review = await review_image(generated["bytes"], generated["mime_type"], content_context, current_prompt)
        history.append({"attempt": attempt, "prompt": current_prompt, "review": review})
        if review.get("passed"):
            stored = await store_media(generated["bytes"], generated["mime_type"], content_item_id)
            if stored.get("status") != "passed":
                return {**stored, "review": review, "attempts": history}
            return {
                "status": "passed",
                "url": stored["url"],
                "storage": {k: v for k, v in stored.items() if k not in {"url", "status"}},
                "mime_type": generated["mime_type"],
                "review": review,
                "attempts": history,
            }

        notes = "; ".join(str(x) for x in (review.get("notes") or []))
        current_prompt = f"{prompt}\nRegenerate and fix these QA issues: {notes or 'improve artifacts, relevance and composition'}"

    return {"status": "review", "reason": "visual QA threshold not reached", "attempts": history}


async def send_to_autoposter(payload: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
    if not AUTOPOSTER_URL:
        return {"status": "skipped", "reason": "AUTOPOSTER_URL is not configured"}

    headers = {"Content-Type": "application/json", "Idempotency-Key": idempotency_key}
    if AUTOPOSTER_TOKEN:
        headers["Authorization"] = f"Bearer {AUTOPOSTER_TOKEN}"
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(AUTOPOSTER_URL, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json() if response.content else {}
    return {"status": "accepted", "response": result}
