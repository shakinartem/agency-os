"""Shared SQLAlchemy column types for ORM models."""

from enum import Enum as PyEnum

from sqlalchemy import Enum as SAEnum


def enum_type(enum_cls: type[PyEnum]) -> SAEnum:
    """Persist enums as strings while returning enum members from ORM rows."""
    return SAEnum(
        enum_cls,
        native_enum=False,
        values_callable=lambda members: [member.value for member in members],
    )
