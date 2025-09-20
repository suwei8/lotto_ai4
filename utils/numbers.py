from __future__ import annotations

import re
from typing import Iterable, List, Sequence, Tuple

TOKEN_PATTERN = re.compile(r"[\s,|;]+")


def normalize_code(code: str | None) -> str:
    if not code:
        return ""
    return re.sub(r"[^0-9]", "", code)


def parse_tokens(numbers: str | None) -> List[str]:
    if not numbers:
        return []
    parts = [part.strip() for part in TOKEN_PATTERN.split(numbers) if part.strip()]
    return [normalize_code(part) or part for part in parts]


def count_hits(tokens: Iterable[str], open_code: str | None) -> int:
    target = normalize_code(open_code)
    if not target:
        return 0
    count = 0
    for token in tokens:
        if normalize_code(token) == target:
            count += 1
    return count


def _flatten_digit_tokens(numbers: str) -> List[str]:
    digits: List[str] = []
    for token in parse_tokens(numbers):
        normalized = normalize_code(token)
        if normalized:
            digits.extend(list(normalized))
    return digits


def match_prediction_hit(playtype_name: str, numbers: str, open_code: str) -> bool:
    """Return True when the prediction for the given playtype hits the open code.

    This helper currently focuses on 3D / 排列3 / 排列5 类玩法所需的命中规则，
    覆盖常见的胆、杀、定位等玩法名称。
    """
    open_code_normalized = normalize_code(open_code)
    if not open_code_normalized:
        return False

    open_digits = list(open_code_normalized)
    digits = _flatten_digit_tokens(numbers)
    if not digits:
        return False

    digit_set = set(digits)
    open_set = set(open_digits)

    # 杀码类：命中即失败
    if playtype_name.startswith("杀"):
        return digit_set.isdisjoint(open_set)

    # 定位类：根据位置判断
    position_map = {"百位": 0, "十位": 1, "个位": 2}
    for position, idx in position_map.items():
        if position in playtype_name:
            if "杀" in playtype_name:
                return open_digits[idx] not in digit_set
            if "定" in playtype_name or "定位" in playtype_name:
                return open_digits[idx] in digit_set

    hit_count = len(digit_set & open_set)
    unique_open_count = len(open_set)

    if "独胆" in playtype_name:
        return hit_count >= 1
    if "双胆" in playtype_name:
        return hit_count >= 2
    if "三胆" in playtype_name or any(keyword in playtype_name for keyword in ["五码", "六码", "七码"]):
        if unique_open_count == 1:
            return open_digits[0] in digit_set
        if unique_open_count == 2:
            return hit_count >= 2
        return hit_count == 3

    return False


def count_digit_hits(tokens: Iterable[str], open_code: str | None) -> int:
    target = normalize_code(open_code)
    if not target:
        return 0
    digits = set(target)
    hit_digits = set()
    for token in tokens:
        for char in normalize_code(token):
            if char in digits:
                hit_digits.add(char)
    return len(hit_digits)


def token_to_digits(token: str) -> List[int]:
    clean = normalize_code(token)
    return [int(ch) for ch in clean] if clean else []


def aggregate_digits(tokens: Iterable[str]) -> List[int]:
    digits: List[int] = []
    for token in tokens:
        digits.extend(token_to_digits(token))
    return digits


def digit_sum(digits: Sequence[int]) -> int:
    return sum(digits)


def digit_span(digits: Sequence[int]) -> int:
    return max(digits) - min(digits) if digits else 0


def ratio(digits: Sequence[int], predicate) -> str:
    true_count = sum(1 for d in digits if predicate(d))
    return f"{true_count}:{max(len(digits) - true_count, 0)}"


def has_consecutive_digits(digits: Sequence[int]) -> bool:
    if not digits:
        return False
    ordered = sorted(set(digits))
    return any(b - a == 1 for a, b in zip(ordered, ordered[1:]))


def to_triplet(combo: Sequence[int]) -> Tuple[int, int, int]:
    if len(combo) != 3:
        raise ValueError("Expected a three-digit sequence")
    return tuple(int(x) for x in combo)
