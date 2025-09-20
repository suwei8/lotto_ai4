from __future__ import annotations

import argparse
import random
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence

import requests
from sqlalchemy import text

from db.connection import get_engine
from utils.cache_control import bump_cache_token

BASE_URL = "https://mix.lottery.sina.com.cn/gateway/index/entry"
DEFAULT_PARAMS: Dict[str, str] = {
    "format": "json",
    "__caller__": "wap",
    "__version__": "1.0.0",
    "__verno__": "10000",
    "cat1": "gameOpenList",
    "paginationType": "1",
    "dpc": "1",
}


class LotteryCollectorError(RuntimeError):
    """上游接口返回异常或响应解析失败时抛出。"""


@dataclass(slots=True)
class LotteryResult:
    lottery_name: str
    issue_name: str
    open_code: str
    total_sum: int
    span: int
    odd_even_ratio: str
    big_small_ratio: str
    open_time: Optional[datetime]


def _remove_leading_zero(values: Sequence[object] | str) -> List[str]:
    if isinstance(values, str):
        candidates: Iterable[object] = values.split(",")
    else:
        candidates = values
    cleaned: List[str] = []
    for token in candidates:
        token_str = str(token).strip()
        if not token_str:
            continue
        if not token_str.isdigit():
            continue
        cleaned.append(str(int(token_str)))
    return cleaned


def _normalize_issue(issue: str) -> str:
    if issue and len(issue) == 5 and issue.startswith("25"):
        return f"20{issue}"
    return issue


def _parse_open_time(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _compute_metrics(numbers: Sequence[int]) -> Dict[str, object]:
    if not numbers:
        raise ValueError("numbers must not be empty")
    total_sum = sum(numbers)
    span = max(numbers) - min(numbers)
    odd_count = sum(1 for num in numbers if num % 2)
    even_count = len(numbers) - odd_count
    big_count = sum(1 for num in numbers if num >= 5)
    small_count = len(numbers) - big_count
    return {
        "total_sum": total_sum,
        "span": span,
        "odd_even_ratio": f"{odd_count}:{even_count}",
        "big_small_ratio": f"{big_count}:{small_count}",
    }


def _extract_result(item: Dict[str, object], lottery_name: str) -> Optional[LotteryResult]:
    issue_no = _normalize_issue(str(item.get("issueNo", "")).strip())
    if not issue_no:
        return None

    open_time_raw = str(item.get("openTime") or "").strip()
    open_time = _parse_open_time(open_time_raw)

    if lottery_name in {"双色球", "大乐透"}:
        reds = _remove_leading_zero(item.get("redResults") or ())
        blues = _remove_leading_zero(item.get("blueResults") or ())
        open_numbers = reds + blues
    else:
        open_numbers = _remove_leading_zero(item.get("openResults") or ())

    if not open_numbers:
        return None

    digits = [int(value) for value in open_numbers]
    metrics = _compute_metrics(digits)
    open_code = ",".join(open_numbers)

    return LotteryResult(
        lottery_name=lottery_name,
        issue_name=issue_no,
        open_code=open_code,
        total_sum=int(metrics["total_sum"]),
        span=int(metrics["span"]),
        odd_even_ratio=str(metrics["odd_even_ratio"]),
        big_small_ratio=str(metrics["big_small_ratio"]),
        open_time=open_time,
    )


def _request_page(session: requests.Session, params: Dict[str, str], page: int) -> Dict[str, object]:
    payload = dict(params)
    payload["page"] = str(page)
    response = session.get(BASE_URL, params=payload, timeout=10)
    if response.status_code != 200:
        raise LotteryCollectorError(f"HTTP {response.status_code} @ page {page}")
    data = response.json()
    if not data.get("result"):
        raise LotteryCollectorError(f"unexpected response structure: {data}")
    return data["result"]


def _yield_results(
    session: requests.Session,
    base_params: Dict[str, str],
    lottery_name: str,
    max_pages: Optional[int],
    sleep_range: Optional[tuple[float, float]],
) -> Iterable[LotteryResult]:
    page = 1
    total_page = None
    while max_pages is None or page <= max_pages:
        print(f"📄 正在采集第 {page} 页开奖数据…")
        if sleep_range:
            delay = random.uniform(*sleep_range)
            print(f"😴 休息 {delay:.2f} 秒后请求")
            time.sleep(delay)
        try:
            result_block = _request_page(session, base_params, page)
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️ 请求第 {page} 页失败：{exc}")
            break
        items = result_block.get("data") or []
        if not items:
            print("ℹ️ 没有更多数据，提前结束。")
            break
        for raw in items:
            parsed = _extract_result(raw, lottery_name)
            if parsed is None:
                continue
            yield parsed
        if total_page is None:
            pagination = result_block.get("pagination") or {}
            try:
                total_page = int(pagination.get("totalPage", 1))
            except (TypeError, ValueError):
                total_page = 1
        page += 1
        if total_page and page > total_page:
            print("✅ 已达到接口的最大页数。")
            break


def _persist_results(results: Iterable[LotteryResult]) -> Dict[str, int]:
    engine = get_engine()
    inserted = 0
    skipped = 0
    updated = 0
    with engine.begin() as conn:
        for record in results:
            existing = conn.execute(
                text(
                    "SELECT id, open_code FROM lottery_results WHERE issue_name = :issue AND lottery_name = :lottery LIMIT 1"
                ),
                {"issue": record.issue_name, "lottery": record.lottery_name},
            ).mappings().first()
            payload = {
                "lottery_name": record.lottery_name,
                "issue_name": record.issue_name,
                "open_code": record.open_code,
                "sum": record.total_sum,
                "span": record.span,
                "odd_even_ratio": record.odd_even_ratio,
                "big_small_ratio": record.big_small_ratio,
                "open_time": record.open_time,
            }
            if existing:
                if existing.get("open_code") == record.open_code:
                    skipped += 1
                    continue
                conn.execute(
                    text(
                        """
                        UPDATE lottery_results
                        SET open_code = :open_code,
                            `sum` = :sum,
                            span = :span,
                            odd_even_ratio = :odd_even_ratio,
                            big_small_ratio = :big_small_ratio,
                            open_time = :open_time
                        WHERE id = :id
                        """
                    ),
                    {**payload, "id": existing["id"]},
                )
                updated += 1
            else:
                conn.execute(
                    text(
                        """
                        INSERT INTO lottery_results (
                            lottery_name, issue_name, open_code, `sum`, span,
                            odd_even_ratio, big_small_ratio, open_time
                        ) VALUES (:lottery_name, :issue_name, :open_code, :sum, :span,
                                 :odd_even_ratio, :big_small_ratio, :open_time)
                        """
                    ),
                    payload,
                )
                inserted += 1
    return {"inserted": inserted, "updated": updated, "skipped": skipped}


def collect_lottery_results(
    *,
    lottery_name: str = "福彩3D",
    lotto_type: str = "102",
    page_size: int = 5,
    max_pages: Optional[int] = None,
    sleep_min: float = 1.2,
    sleep_max: float = 2.4,
) -> Dict[str, int]:
    params = {**DEFAULT_PARAMS}
    params.update({"lottoType": str(lotto_type), "pageSize": str(page_size)})
    session = requests.Session()
    sleep_range: Optional[tuple[float, float]] = None
    if sleep_min > 0 and sleep_max > 0 and sleep_max >= sleep_min:
        sleep_range = (sleep_min, sleep_max)
    results = list(
        _yield_results(
            session,
            params,
            lottery_name,
            max_pages,
            sleep_range,
        )
    )
    if not results:
        print("⚠️ 未获取到任何开奖数据。")
        return {"inserted": 0, "updated": 0, "skipped": 0}
    stats = _persist_results(results)
    bump_cache_token()
    print("🔄 已刷新前端缓存标记。")
    print(
        "✅ 开奖采集完成："
        f"新增 {stats['inserted']} 条，"
        f"更新 {stats['updated']} 条，"
        f"跳过 {stats['skipped']} 条。"
    )
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="采集开奖数据并写入 lottery_results 表")
    parser.add_argument("--lottery-name", default="福彩3D", help="彩票名称，用于标记数据库记录")
    parser.add_argument("--lotto-type", default="102", help="Sina 接口的 lottoType 参数")
    parser.add_argument("--page-size", type=int, default=5, help="每页抓取条数")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=1,
        help="最大抓取页数；0 或负数表示抓取所有可用页",
    )
    parser.add_argument("--sleep-min", type=float, default=1.2, help="请求前最小等待秒数")
    parser.add_argument("--sleep-max", type=float, default=2.4, help="请求前最大等待秒数")
    args = parser.parse_args()

    max_pages = None if args.max_pages is None or args.max_pages <= 0 else args.max_pages
    collect_lottery_results(
        lottery_name=args.lottery_name,
        lotto_type=args.lotto_type,
        page_size=args.page_size,
        max_pages=max_pages,
        sleep_min=args.sleep_min,
        sleep_max=args.sleep_max,
    )


if __name__ == "__main__":
    main()
