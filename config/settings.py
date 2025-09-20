"""Settings loader for the Lotto AI application."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache

try:  # pragma: no cover - optional dependency in production images
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


if load_dotenv is not None:  # pragma: no branch
    load_dotenv()


class MissingSettingError(RuntimeError):
    """Raised when a required environment variable is missing."""


def _get_env(
    name: str,
    *,
    default: str | None = None,
    required: bool = False,
    warn_if_default: bool = False,
) -> str:
    value = os.getenv(name, default)
    if required and not value:
        raise MissingSettingError(f"环境变量 {name} 未设置。请在 .env 或部署环境中配置此参数。")
    if not value and default is not None:
        value = default
        if warn_if_default:
            logging.getLogger(__name__).warning(
                "环境变量 %s 未设置，使用默认值。请在生产环境中显式配置。", name
            )
    return value or ""


def _get_int_env(name: str, default: int) -> int:
    raw_value = _get_env(name, default=str(default))
    try:
        return int(raw_value)
    except ValueError as exc:  # pragma: no cover - configuration error
        raise MissingSettingError(f"环境变量 {name} 必须是整数，当前值为 {raw_value!r}") from exc


@dataclass(frozen=True)
class DatabaseSettings:
    url: str
    pool_size: int
    max_overflow: int
    pool_recycle: int
    connect_timeout: int


@dataclass(frozen=True)
class CollectorSettings:
    primary_domain: str
    secondary_domain: str
    endpoint_path: str
    token: str
    aes_key_hex: str
    aes_iv: str
    user_agent: str


@dataclass(frozen=True)
class Settings:
    database: DatabaseSettings
    collector: CollectorSettings
    log_level: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings from environment variables (cached)."""

    database_url = _get_env(
        "LOTTO_DB_URL",
        default="mysql+pymysql://root:sw63828@127.0.0.1:3306/lotto_3d?charset=utf8mb4",
        warn_if_default=True,
    )
    database_settings = DatabaseSettings(
        url=database_url,
        pool_size=_get_int_env("LOTTO_DB_POOL_SIZE", 5),
        max_overflow=_get_int_env("LOTTO_DB_MAX_OVERFLOW", 10),
        pool_recycle=_get_int_env("LOTTO_DB_POOL_RECYCLE", 1800),
        connect_timeout=_get_int_env("LOTTO_DB_CONNECT_TIMEOUT", 10),
    )

    collector = CollectorSettings(
        primary_domain=_get_env(
            "COLLECTOR_PRIMARY_DOMAIN", default="api.91bixin.com", warn_if_default=True
        ),
        secondary_domain=_get_env(
            "COLLECTOR_SECONDARY_DOMAIN", default="api.17chdd.com", warn_if_default=True
        ),
        endpoint_path=_get_env(
            "COLLECTOR_ENDPOINT_PATH",
            default="/jddods/recom/unct/public/handler",
            warn_if_default=True,
        ),
        token=_get_env(
            "COLLECTOR_TOKEN",
            default="eyJ0eXBlIjoiSldUIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiJqc2NwIiwiaXNzIjoiamRkLmNvbSJ9.eyJleHQiOnsiYnJhbmRDb2RlIjoic3pjYXBwIiwicGxhdGZvcm1Db2RlIjoiYW5kcm9pZCJ9LCJ1c2VySWQiOjE4ODM4MDExLCJ1c2VyVHlwZSI6MSwidXVpZCI6ImUyYzI0ZmI4LWIwZTgtMzkxNS04ZWQzLTE2MzkxZDhlYmU0YyJ9.7a37c4913e1940192f3249cf3b5f10f5.M2EyNWE3OGEtZGNhNy00YTk0LWI0MzQtNDg1MjgzOTcxNTg0",
            warn_if_default=True,
        ),
        aes_key_hex=_get_env(
            "COLLECTOR_AES_KEY_HEX",
            default="6433596d493142554f5345325332596d616c42565a55513d",
            warn_if_default=True,
        ),
        aes_iv=_get_env("COLLECTOR_AES_IV", default="0000000000000000", warn_if_default=True),
        user_agent=_get_env("COLLECTOR_USER_AGENT", default="okhttp/4.12.0", warn_if_default=True),
    )

    log_level = _get_env("LOTTO_LOG_LEVEL", default="INFO")

    return Settings(database=database_settings, collector=collector, log_level=log_level.upper())


def configure_logging() -> None:
    """Initialise base logging configuration once."""

    settings = get_settings()
    root_logger = logging.getLogger()
    if root_logger.handlers:  # 已经配置过
        return

    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
