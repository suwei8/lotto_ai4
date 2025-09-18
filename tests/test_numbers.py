from __future__ import annotations

from utils import numbers


def test_parse_tokens_handles_mixed_delimiters():
    tokens = numbers.parse_tokens("1,2|3 4")
    assert tokens == ["1", "2", "3", "4"]


def test_aggregate_digits_and_metrics():
    tokens = ["12", "34"]
    digits = numbers.aggregate_digits(tokens)
    assert digits == [1, 2, 3, 4]
    assert numbers.digit_sum(digits) == 10
    assert numbers.digit_span(digits) == 3
    assert numbers.ratio(digits, lambda d: d % 2 == 1) == "2:2"
    assert numbers.has_consecutive_digits(digits) is True


def test_count_hits_and_digit_hits():
    tokens = ["123"]
    assert numbers.count_hits(tokens, "123") == 1
    assert numbers.count_digit_hits(tokens, "132") == 3
