from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import QueuePool

from config import settings

logger = logging.getLogger(__name__)

_engine = create_engine(
    settings.database.url,
    poolclass=QueuePool,
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
    pool_pre_ping=True,
    pool_recycle=settings.database.pool_recycle,
    future=True,
    connect_args={"connect_timeout": settings.database.connect_timeout},
)


def get_engine():
    """Return the shared SQLAlchemy engine for the application."""
    return _engine


def query_db(sql: str, params: dict[str, Any] | None = None):
    """Execute a parameterised SQL statement and return rows or metadata."""
    params = params or {}
    logger.debug("Executing query", extra={"sql": sql, "params": params})
    try:
        with _engine.connect() as conn:
            result = conn.execute(text(sql), params)
            if result.returns_rows:
                return [dict(r._mapping) for r in result]
            return {"rowcount": result.rowcount}
    except SQLAlchemyError:
        logger.exception("Database query failed: %s", sql)
        raise
