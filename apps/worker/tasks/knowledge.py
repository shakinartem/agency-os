"""Knowledge Base retrieval for Content Factory workers.

V1 uses PostgreSQL full-text retrieval with a GIN index. This keeps deployment simple and
fast enough for substantial project knowledge bases. Embeddings can later be added as a
second retrieval signal without changing the document/chunk lineage model.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text

KNOWLEDGE_TOP_K = 8
KNOWLEDGE_CHAR_BUDGET = 9000


async def retrieve_knowledge(
    session,
    project_id: uuid.UUID,
    query: str,
    *,
    limit: int = KNOWLEDGE_TOP_K,
    char_budget: int = KNOWLEDGE_CHAR_BUDGET,
) -> list[dict[str, Any]]:
    cleaned_query = " ".join(query.split()).strip()
    if not cleaned_query:
        return []

    statement = text(
        """
        WITH q AS (
            SELECT websearch_to_tsquery('simple', :query) AS query
        )
        SELECT
            kc.id AS chunk_id,
            kc.document_id AS document_id,
            kd.name AS document_name,
            kc.position AS position,
            kc.content AS content,
            ts_rank_cd(kc.search_vector, q.query) AS rank
        FROM knowledge_chunks kc
        JOIN knowledge_documents kd ON kd.id = kc.document_id
        CROSS JOIN q
        WHERE kc.project_id = CAST(:project_id AS uuid)
          AND kd.status = 'active'
          AND kc.search_vector @@ q.query
        ORDER BY rank DESC, kc.created_at DESC
        LIMIT :limit
        """
    )
    result = await session.execute(
        statement,
        {"query": cleaned_query, "project_id": str(project_id), "limit": limit},
    )

    rows: list[dict[str, Any]] = []
    used_chars = 0
    for row in result.mappings():
        content = str(row["content"] or "").strip()
        if not content:
            continue
        remaining = char_budget - used_chars
        if remaining <= 0:
            break
        if len(content) > remaining:
            content = content[:remaining].rsplit(" ", 1)[0].strip()
        rows.append({
            "chunk_id": str(row["chunk_id"]),
            "document_id": str(row["document_id"]),
            "document_name": row["document_name"],
            "position": int(row["position"]),
            "rank": float(row["rank"] or 0),
            "content": content,
        })
        used_chars += len(content)
    return rows


def knowledge_refs(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Persist compact internal lineage without duplicating whole knowledge chunks."""
    return [
        {
            "chunk_id": chunk["chunk_id"],
            "document_id": chunk["document_id"],
            "document_name": chunk["document_name"],
            "position": chunk["position"],
            "rank": chunk["rank"],
            "excerpt": chunk["content"][:400],
        }
        for chunk in chunks
    ]
