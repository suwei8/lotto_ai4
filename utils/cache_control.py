from __future__ import annotations

import os
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_CACHE_TOKEN_FILE = _PROJECT_ROOT / "logs" / ".cache_token"


def _ensure_token_file() -> None:
    try:
        _CACHE_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


def get_cache_token() -> str:
    """Return the monotonic token used to bust cached DB queries."""
    try:
        return str(int(_CACHE_TOKEN_FILE.stat().st_mtime))
    except FileNotFoundError:
        return bump_cache_token()


def bump_cache_token() -> str:
    """Update the token so cached queries are invalidated on next run."""
    _ensure_token_file()
    now = time.time()
    try:
        os.utime(_CACHE_TOKEN_FILE, (now, now))
    except OSError:
        try:
            _CACHE_TOKEN_FILE.write_text(str(int(now)))
        except OSError:
            pass
    try:
        return str(int(_CACHE_TOKEN_FILE.stat().st_mtime))
    except OSError:
        return str(int(now))
