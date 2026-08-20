"""PostgreSQL integration tests for project-isolated Knowledge Base retrieval."""

import asyncio
import uuid

from sqlalchemy import delete

from database.base import get_async_session_maker
from database.models import KnowledgeChunk, KnowledgeDocument, Project
from apps.worker.tasks.knowledge import retrieve_knowledge


async def _scenario():
    maker = get_async_session_maker()
    suffix = uuid.uuid4().hex[:10]
    async with maker() as session:
        project = Project(name=f"Knowledge test {suffix}", slug=f"knowledge-test-{suffix}")
        other = Project(name=f"Other knowledge {suffix}", slug=f"other-knowledge-{suffix}")
        session.add_all([project, other])
        await session.flush()

        active_doc = KnowledgeDocument(
            project_id=project.id,
            name="Product facts",
            checksum=("a" * 54) + suffix,
            status="active",
            char_count=80,
            chunk_count=1,
            content="Qualive predicts buyer intent and readiness from behavioral signals.",
        )
        archived_doc = KnowledgeDocument(
            project_id=project.id,
            name="Archived facts",
            checksum=("b" * 54) + suffix,
            status="archived",
            char_count=80,
            chunk_count=1,
            content="Archived buyer intent material must not be retrieved.",
        )
        foreign_doc = KnowledgeDocument(
            project_id=other.id,
            name="Foreign project facts",
            checksum=("c" * 54) + suffix,
            status="active",
            char_count=80,
            chunk_count=1,
            content="Buyer intent exists here but belongs to another project.",
        )
        session.add_all([active_doc, archived_doc, foreign_doc])
        await session.flush()
        session.add_all([
            KnowledgeChunk(
                project_id=project.id,
                document_id=active_doc.id,
                position=0,
                content="Qualive predicts buyer intent and readiness from behavioral signals.",
                token_estimate=16,
            ),
            KnowledgeChunk(
                project_id=project.id,
                document_id=archived_doc.id,
                position=0,
                content="Archived buyer intent material must not be retrieved.",
                token_estimate=12,
            ),
            KnowledgeChunk(
                project_id=other.id,
                document_id=foreign_doc.id,
                position=0,
                content="Buyer intent exists here but belongs to another project.",
                token_estimate=14,
            ),
        ])
        await session.commit()

        rows = await retrieve_knowledge(session, project.id, "buyer intent readiness")
        assert rows, "Expected the active project knowledge chunk to be retrieved"
        assert all(row["document_id"] == str(active_doc.id) for row in rows)
        assert any("readiness" in row["content"].lower() for row in rows)
        assert all(row["document_id"] != str(archived_doc.id) for row in rows)
        assert all(row["document_id"] != str(foreign_doc.id) for row in rows)

        await session.execute(delete(Project).where(Project.id.in_([project.id, other.id])))
        await session.commit()


def test_retrieval_is_project_scoped_and_ignores_archived_documents():
    asyncio.run(_scenario())
