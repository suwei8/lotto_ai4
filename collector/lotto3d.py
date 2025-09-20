from __future__ import annotations

import argparse
import logging
from collections import Counter
from typing import Sequence

from config.settings import configure_logging
from utils.cache_control import bump_cache_token

from .api import CollectorAPIError, DetailClient, LeaderboardClient
from .config import DEFAULT_ISSUE_COUNT, DEFAULT_LIMIT, LOTTERY_ID, PLAYTYPE_SPECS
from .storage import expand_scheme, upsert_expert_info, upsert_prediction

logger = logging.getLogger(__name__)


def collect_lotto3d(
    *,
    limit: int = DEFAULT_LIMIT,
    issue_count: int = DEFAULT_ISSUE_COUNT,
    sort_types: Sequence[int] | None = None,
) -> None:
    leaderboard_client = LeaderboardClient()
    detail_client = DetailClient()

    known_users: dict[int, str] = {}
    stats = Counter()
    issue_name: str | None = None
    lottery_id = LOTTERY_ID

    for spec in PLAYTYPE_SPECS:
        sort_candidates = tuple(sort_types) if sort_types else spec.sort_types
        for sort_type in sort_candidates:
            try:
                result = leaderboard_client.fetch(
                    lottery_id=LOTTERY_ID,
                    playtype_id=spec.playtype_id,
                    sort_type=sort_type,
                    limit=limit,
                    issue_count=issue_count,
                )
            except CollectorAPIError as exc:
                logger.warning(
                    "排行榜获取失败 playtype=%s sort=%s: %s",
                    spec.playtype_id,
                    sort_type,
                    exc,
                )
                continue

            if result.issue_name:
                issue_name = issue_name or result.issue_name
            lottery_id = result.lottery_id or lottery_id

            for entry in result.entries:
                known_users.setdefault(entry.user_id, entry.nick_name)
                upsert_expert_info(entry.user_id, entry.nick_name)
            stats["leaderboard_calls"] += 1
            stats["leaderboard_users"] += len(result.entries)

    if not known_users:
        raise RuntimeError("未从排行榜获取到任何专家数据")

    if not issue_name:
        logger.warning("排行榜未返回期号，将在明细接口中获取 issue_name")

    logger.info("🏁 本次采集覆盖 %s 位专家，目标期号 %s", len(known_users), issue_name or "未知")

    for idx, (user_id, _nick_name) in enumerate(known_users.items(), start=1):
        try:
            detail = detail_client.fetch(
                lottery_id=lottery_id,
                user_id=user_id,
                issue_name=issue_name,
            )
        except CollectorAPIError as exc:
            logger.warning("明细获取失败 user=%s: %s", user_id, exc)
            continue

        resolved_issue = detail.issue_name or issue_name
        if not resolved_issue:
            logger.warning("无法获取期号，跳过专家 %s", user_id)
            continue
        for scheme in detail.schemes:
            for expanded in expand_scheme(scheme.playtype_id, scheme.playtype_name, scheme.numbers):
                upsert_prediction(
                    user_id=user_id,
                    issue_name=resolved_issue,
                    lottery_id=lottery_id,
                    scheme=expanded,
                )
                stats["predictions"] += 1
        stats["detail_calls"] += 1
        if idx % 20 == 0:
            logger.info("……已完成 %s 位专家采集", idx)

    logger.info(
        "✅ 采集完成：排行榜请求 %s 次，明细请求 %s 次，写入方案 %s 条",
        stats["leaderboard_calls"],
        stats["detail_calls"],
        stats["predictions"],
    )

    bump_cache_token()
    logger.info("🔄 已刷新前端缓存标记，Streamlit 将在下次请求时获取最新数据。")


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="采集福彩3D专家预测数据")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="排行榜人数上限")
    parser.add_argument("--issue-count", type=int, default=DEFAULT_ISSUE_COUNT, help="参考期数")
    parser.add_argument(
        "--sort-types",
        type=str,
        default="",
        help="可选：指定 sortType 列表，逗号分隔。例如 '4' 或 '2,4'",
    )
    args = parser.parse_args()
    chosen_sorts = None
    if args.sort_types:
        chosen_sorts = tuple(int(x) for x in args.sort_types.split(",") if x.strip())
    collect_lotto3d(limit=args.limit, issue_count=args.issue_count, sort_types=chosen_sorts)


if __name__ == "__main__":
    main()
