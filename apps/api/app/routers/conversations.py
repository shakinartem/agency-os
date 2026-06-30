"""CRUD /conversations + /conversations/:id/messages."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.enums import UserRole
from database.models import Conversation, ConversationMessage, User

from ..database import get_db
from ..dependencies import get_current_user, require_role
from ..schemas.conversation import (
    ConversationCreate,
    ConversationRead,
    ConversationUpdate,
    MessageCreate,
    MessageRead,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("/", response_model=list[ConversationRead])
async def list_conversations(
    lead_id: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Conversation)
    if lead_id:
        stmt = stmt.where(Conversation.lead_id == uuid.UUID(lead_id))
    if status:
        stmt = stmt.where(Conversation.status == status)
    stmt = stmt.order_by(Conversation.updated_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{conv_id}", response_model=ConversationRead)
async def get_conversation(
    conv_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Conversation).where(Conversation.id == conv_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conv


@router.post("/", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.manager)),
):
    conv = Conversation(**body.model_dump())
    db.add(conv)
    await db.flush()
    await db.refresh(conv)
    return conv


@router.put("/{conv_id}", response_model=ConversationRead)
async def update_conversation(
    conv_id: uuid.UUID,
    body: ConversationUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.manager)),
):
    result = await db.execute(select(Conversation).where(Conversation.id == conv_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(conv, field, value)
    await db.flush()
    await db.refresh(conv)
    return conv


@router.delete("/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conv_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    result = await db.execute(select(Conversation).where(Conversation.id == conv_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    await db.delete(conv)


# ── Messages ─────────────────────────────────────────────


@router.get("/{conv_id}/messages", response_model=list[MessageRead])
async def list_messages(
    conv_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conv_id)
        .order_by(ConversationMessage.created_at)
    )
    return result.scalars().all()


@router.post("/{conv_id}/messages", response_model=MessageRead,
             status_code=status.HTTP_201_CREATED)
async def add_message(
    conv_id: uuid.UUID,
    body: MessageCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.manager)),
):
    msg = ConversationMessage(
        conversation_id=conv_id,
        role=body.role,
        content=body.content,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(msg)

    # update parent conversation
    conv_result = await db.execute(select(Conversation).where(Conversation.id == conv_id))
    conv = conv_result.scalar_one_or_none()
    if conv:
        conv.last_message = body.content

    await db.flush()
    await db.refresh(msg)
    return msg
