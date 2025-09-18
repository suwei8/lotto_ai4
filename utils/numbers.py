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
