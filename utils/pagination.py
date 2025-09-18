"""Utility helpers for paginating database result sets."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Pagination:
    """Represents pagination parameters derived from page settings."""

    page: int
    page_size: int
    limit: int
    offset: int


def paginate(page: int, page_size: int) -> Pagination:
    """Calculate pagination information.

    Args:
        page: 1-based index of the requested page.
        page_size: Number of records per page.

    Returns:
        Pagination: Dataclass containing page, page_size, limit and offset.

    Raises:
        ValueError: If ``page`` or ``page_size`` are less than 1.
    """

    if page < 1:
        raise ValueError("page must be greater than or equal to 1")
    if page_size < 1:
        raise ValueError("page_size must be greater than or equal to 1")

    limit = page_size
    offset = (page - 1) * page_size

    return Pagination(page=page, page_size=page_size, limit=limit, offset=offset)


__all__ = ["Pagination", "paginate"]
