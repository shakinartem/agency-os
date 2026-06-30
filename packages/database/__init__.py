"""Agency OS — Database package.

SQLAlchemy declarative base, session factory, and model imports.
"""
from .base import Base, get_session

# engine and async_session are available via lazy accessors:
#   from database.base import engine, async_session

__all__ = ["Base", "get_session"]