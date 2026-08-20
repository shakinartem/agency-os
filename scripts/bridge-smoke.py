#!/usr/bin/env python3
"""No-LLM deployment smoke test for Content Factory -> Autoposter contract.

Checks acceptance, idempotent replay, and changed-payload conflict. Optionally checks
Autoposter -> Factory performance ingestion when an existing Factory content ID is supplied.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import uuid
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request_json(url: str, payload: dict, headers: dict[str, str]) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        with urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body = {"raw": raw}
        return exc.code, body
    except URLError as exc:
        raise RuntimeError(f"Unable to reach {url}: {exc}") from exc


def package(content_id: str, project_id: str) -> dict:
    return {
        "schema_version": "content-package/1.0",
        "content_id": content_id,
        "project_id": project_id,
        "status": "approved",
        "canonical": {
            "content_type": "post",
            "topic": "Bridge smoke test",
            "goal": "Verify delivery contract",
            "title": "Smoke test",
            "body": "This package validates the Content Factory to Autoposter boundary.",
            "hook": "Contract first.",
            "cta": "No action required.",
        },
        "variants": [{
            "platform": "telegram",
            "title": "Smoke test",
            "plain_text": "This package validates the Content Factory to Autoposter boundary.",
            "cta": "No action required.",
            "hashtags": ["#smoke"],
            "blocks": [],
            "media": [],
        }],
        "sources": [],
        "quality": {"overall": 1.0, "factuality": 1.0, "brand_voice": 1.0, "media": None},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--autoposter-url", required=True, help="Full Content Factory ingest endpoint")
    parser.add_argument("--autoposter-token", required=True)
    parser.add_argument("--project-id", default=str(uuid.uuid4()))
    parser.add_argument("--content-id", default=str(uuid.uuid4()))
    parser.add_argument("--factory-performance-url")
    parser.add_argument("--performance-token")
    args = parser.parse_args()

    key = f"bridge-smoke:{uuid.uuid4()}"
    headers = {"Authorization": f"Bearer {args.autoposter_token}", "Idempotency-Key": key}
    payload = package(args.content_id, args.project_id)

    status, first = request_json(args.autoposter_url, payload, headers)
    if status not in {200, 202} or first.get("status") != "accepted":
        raise RuntimeError(f"First ingest failed: HTTP {status} {first}")
    print(f"OK ingest: receipt={first.get('receipt_id')} workspace={first.get('workspace_id')}")

    status, replay = request_json(args.autoposter_url, payload, headers)
    if status not in {200, 202} or not replay.get("idempotent_replay"):
        raise RuntimeError(f"Idempotent replay failed: HTTP {status} {replay}")
    if replay.get("receipt_id") != first.get("receipt_id"):
        raise RuntimeError("Replay returned a different receipt")
    print("OK idempotent replay")

    changed = copy.deepcopy(payload)
    changed["canonical"]["body"] += " Changed payload."
    changed["variants"][0]["plain_text"] += " Changed payload."
    status, conflict = request_json(args.autoposter_url, changed, headers)
    if status != 409:
        raise RuntimeError(f"Changed-payload conflict expected HTTP 409, got {status}: {conflict}")
    print("OK idempotency conflict")

    if args.factory_performance_url or args.performance_token:
        if not (args.factory_performance_url and args.performance_token):
            raise RuntimeError("Both --factory-performance-url and --performance-token are required together")
        event_id = f"bridge-smoke-performance:{uuid.uuid4()}"
        perf = {
            "event_id": event_id,
            "source": "autoposter",
            "content_id": args.content_id,
            "external_publication_id": f"smoke-{uuid.uuid4()}",
            "platform": "telegram",
            "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "metrics": {"views": 100, "clicks": 5, "leads": 1},
            "metadata": {"smoke_test": True},
        }
        perf_headers = {"X-Performance-Token": args.performance_token}
        status, accepted = request_json(args.factory_performance_url, perf, perf_headers)
        if status != 202 or accepted.get("status") != "accepted":
            raise RuntimeError(f"Performance ingest failed: HTTP {status} {accepted}")
        status, duplicate = request_json(args.factory_performance_url, perf, perf_headers)
        if status != 202 or duplicate.get("status") != "duplicate":
            raise RuntimeError(f"Performance dedupe failed: HTTP {status} {duplicate}")
        print("OK performance callback + dedupe")

    print("PASS Content Factory <-> Autoposter smoke test")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
