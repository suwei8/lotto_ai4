"""Streamlit caching utilities used across the application."""
from __future__ import annotations

from typing import Any, Callable, Optional, TypeVar

import streamlit as st

F = TypeVar("F", bound=Callable[..., Any])


def cache_data(ttl: Optional[int] = 600, **kwargs: Any) -> Callable[[F], F]:
    """A thin wrapper around :func:`streamlit.cache_data`.

    The wrapper applies a sensible default TTL and keeps the API consistent
    across the codebase.  Additional keyword arguments are forwarded directly to
    ``st.cache_data`` for fine-grained control when required.

    Args:
        ttl: Time-to-live for the cached data in seconds. ``None`` disables
            expiration. Defaults to ``600`` seconds (10 minutes).
        **kwargs: Additional options passed to :func:`streamlit.cache_data`.

    Returns:
        Callable: A decorator that can be applied to data loading functions.
    """

    def decorator(func: F) -> F:
        cached_function = st.cache_data(ttl=ttl, **kwargs)(func)
        return cached_function  # type: ignore[return-value]

    return decorator


__all__ = ["cache_data"]
