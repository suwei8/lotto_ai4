from __future__ import annotations

import itertools
from typing import Iterable, List, Sequence, Tuple

import pandas as pd
import streamlit as st


def sum_digits(combo: Sequence[int]) -> int:
    return sum(combo)


def span_digits(combo: Sequence[int]) -> int:
    return max(combo) - min(combo)


def ratio(combo: Sequence[int], predicate) -> str:
    count = sum(1 for d in combo if predicate(d))
    return f"{count}:{len(combo) - count}"


def has_consecutive(combo: Sequence[int]) -> bool:
    sorted_digits = sorted(combo)
    return any(b - a == 1 for a, b in zip(sorted_digits, sorted_digits[1:]))


def apply_filters(
    combos: Iterable[Tuple[int, int, int]],
    exclude_sums: set[int],
    sum_range: Tuple[int, int],
    exclude_span: set[int],
    span_range: Tuple[int, int],
    odd_even_keep: set[str],
    big_small_keep: set[str],
    exclude_consecutive: bool,
) -> List[Tuple[int, int, int]]:
    result: List[Tuple[int, int, int]] = []
    for combo in combos:
        digits = tuple(combo)
        total = sum_digits(digits)
        if exclude_sums and total in exclude_sums:
            continue
        if not (sum_range[0] <= total <= sum_range[1]):
            continue
        span = span_digits(digits)
        if exclude_span and span in exclude_span:
            continue
        if not (span_range[0] <= span <= span_range[1]):
            continue
        odd_even = ratio(digits, lambda d: d % 2 == 1)
        big_small = ratio(digits, lambda d: d >= 5)
        if odd_even_keep and odd_even not in odd_even_keep:
            continue
        if big_small_keep and big_small not in big_small_keep:
            continue
        if exclude_consecutive and has_consecutive(digits):
            continue
        result.append(digits)
    return result


def generate_zu6(include: set[int], exclude: set[int]) -> List[Tuple[int, int, int]]:
    pool = (set(range(10)) - exclude) | include
    combos = [tuple(sorted(c)) for c in itertools.combinations(sorted(pool), 3)]
    if include:
        combos = [c for c in combos if include.issubset(set(c))]
    return combos


def generate_zu3(include: set[int], exclude: set[int]) -> List[Tuple[int, int, int]]:
    pool = (set(range(10)) - exclude) | include
    combos: List[Tuple[int, int, int]] = []
    for repeated in pool:
        for single in pool - {repeated}:
            combo = tuple(sorted((repeated, repeated, single)))
            if include and not include.issubset(set(combo)):
                continue
            combos.append(combo)
    return list({combo for combo in combos})


def generate_direct(
    hundreds: Sequence[int],
    tens: Sequence[int],
    units: Sequence[int],
    filter_zu3: bool,
    filter_baozi: bool,
    filter_zu6: bool,
    include_digits: set[int],
    exclude_digits: set[int],
) -> List[Tuple[int, int, int]]:
    combos: List[Tuple[int, int, int]] = []
    for h, t, u in itertools.product(hundreds, tens, units):
        digits = (h, t, u)
        unique = len(set(digits))
        if filter_baozi and unique == 1:
            continue
        if filter_zu3 and unique == 2:
            continue
        if filter_zu6 and unique == 3:
            continue
        if include_digits and not include_digits.intersection(digits):
            continue
        if exclude_digits and exclude_digits.intersection(digits):
            continue
        combos.append(digits)
    return combos


def format_combo(combo: Tuple[int, int, int]) -> str:
    return "".join(str(d) for d in combo)


st.header("Xuanhao 3D / P3 选号器")
mode = st.radio("选号模式", options=("组选", "直选"), horizontal=True)

sum_exclude = set(st.multiselect("排除和值", options=list(range(28))))
sum_min, sum_max = st.slider("和值范围", 0, 27, (0, 27))
span_exclude = set(st.multiselect("排除跨度", options=list(range(10))))
span_min, span_max = st.slider("跨度范围", 0, 9, (0, 9))
odd_even = set(st.multiselect("保留奇偶比", options=["3:0", "2:1", "1:2", "0:3"]))
big_small = set(st.multiselect("保留大小比", options=["3:0", "2:1", "1:2", "0:3"]))
exclude_consecutive = st.checkbox("排除连号", value=False)

combos: List[Tuple[int, int, int]] = []
mode_description = ""
bonus_per_bet = 0

if mode == "组选":
    zu_type = st.selectbox("组选类型", options=("组六", "组三"))
    include_digits = set(
        int(d) for d in st.multiselect("包含数字", options=list(range(10)))
    )
    exclude_digits = set(
        int(d) for d in st.multiselect("排除数字", options=list(range(10)))
    )
    if zu_type == "组六":
        source = generate_zu6(include_digits, exclude_digits)
        bonus_per_bet = 280
        mode_description = "组六"
    else:
        source = generate_zu3(include_digits, exclude_digits)
        bonus_per_bet = 550
        mode_description = "组三"
    combos = apply_filters(
        source,
        sum_exclude,
        (sum_min, sum_max),
        span_exclude,
        (span_min, span_max),
        odd_even,
        big_small,
        exclude_consecutive,
    )
else:
    filter_zu3 = st.checkbox("过滤组三", value=False)
    filter_baozi = st.checkbox("过滤豹子", value=False)
    filter_zu6 = st.checkbox("过滤组六", value=False)
    hundreds = st.multiselect(
        "百位候选", options=list(range(10)), default=list(range(10))
    )
    tens = st.multiselect("十位候选", options=list(range(10)), default=list(range(10)))
    units = st.multiselect("个位候选", options=list(range(10)), default=list(range(10)))
    include_digits = set(
        int(d) for d in st.multiselect("至少包含数字", options=list(range(10)))
    )
    exclude_digits = set(
        int(d) for d in st.multiselect("排除出现数字", options=list(range(10)))
    )
    if not hundreds or not tens or not units:
        st.warning("请为百位、十位、个位至少选择一个数字。")
        combos = []
    else:
        source = generate_direct(
            hundreds,
            tens,
            units,
            filter_zu3,
            filter_baozi,
            filter_zu6,
            include_digits,
            exclude_digits,
        )
        combos = apply_filters(
            source,
            sum_exclude,
            (sum_min, sum_max),
            span_exclude,
            (span_min, span_max),
            odd_even,
            big_small,
            exclude_consecutive,
        )
    bonus_per_bet = 0  # 直选奖金单独计算
    mode_description = "直选"

max_display = 5000
if len(combos) > max_display:
    st.warning(
        f"组合数量较大（{len(combos)} 条），仅展示前 {max_display} 条。请收紧过滤条件。"
    )
combos = combos[:max_display]

combos_df = pd.DataFrame(
    [
        {
            "组合": format_combo(combo),
            "和值": sum_digits(combo),
            "跨度": span_digits(combo),
            "奇偶比": ratio(combo, lambda d: d % 2 == 1),
            "大小比": ratio(combo, lambda d: d >= 5),
            "有连号": has_consecutive(combo),
        }
        for combo in combos
    ]
)

st.subheader("生成组合")
st.dataframe(combos_df, use_container_width=True)

st.subheader("组合导出")
st.text_area(
    "组合列表",
    value=", ".join(combos_df["组合"].tolist()),
    height=120,
)

if mode == "组选":
    st.subheader("定位调整器")
    hundred_filter = set(
        int(d)
        for d in st.multiselect(
            "百位需包含", options=list(range(10)), key="hundred_filter"
        )
    )
    ten_filter = set(
        int(d)
        for d in st.multiselect("十位需包含", options=list(range(10)), key="ten_filter")
    )
    unit_filter = set(
        int(d)
        for d in st.multiselect(
            "个位需包含", options=list(range(10)), key="unit_filter"
        )
    )

    adjusted: List[str] = []
    for combo in combos:
        matched = None
        for perm in set(itertools.permutations(combo)):
            if hundred_filter and perm[0] not in hundred_filter:
                continue
            if ten_filter and perm[1] not in ten_filter:
                continue
            if unit_filter and perm[2] not in unit_filter:
                continue
            matched = perm
            break
        adjusted.append(format_combo(matched or combo))

    st.text_area("定位调整结果", value=", ".join(adjusted), height=120)

st.subheader("全排列转换（组选）")
permutation_enabled = st.checkbox("启用全排列转换", value=False)
max_permutations = 5000
permutation_results: List[str] = []

if permutation_enabled:
    for combo in combos:
        digits = list(combo)
        if len(digits) > 6:
            continue
        perms = {"".join(p) for p in itertools.permutations(digits)}
        permutation_results.extend(sorted(perms))
        if len(permutation_results) >= max_permutations:
            break
    permutation_results = permutation_results[:max_permutations]
    if permutation_results:
        st.write(
            f"展示前 {len(permutation_results)} 项全排列结果（上限 {max_permutations}）。"
        )
        st.text_area("全排列列表", value=", ".join(permutation_results), height=120)
    else:
        st.info("未生成任何全排列结果（可能组合位数过大）。")

st.subheader("投注与收益估算")
if mode == "组选":
    default_group = 1
    default_direct = 0
else:
    default_group = 0
    default_direct = 1

group_multiplier = st.number_input("组选倍数", min_value=0, value=default_group, step=1)
direct_multiplier = st.number_input(
    "直选倍数", min_value=0, value=default_direct, step=1
)

group_bonus = bonus_per_bet

group_bets = len(combos) * group_multiplier
permutation_base = (
    len(permutation_results)
    if permutation_enabled and permutation_results
    else len(combos)
)
direct_bets = permutation_base * direct_multiplier

total_bets = group_bets + direct_bets
cost = total_bets * 2
reward = group_multiplier * group_bonus + direct_multiplier * 1700
profit = reward - cost

st.write(
    f"模式：{mode_description}丨组合数：{len(combos)}丨排列数：{permutation_base}丨组选倍数：{group_multiplier}丨直选倍数：{direct_multiplier}"
)
st.write(f"预计投入：¥{cost:.2f}丨假设命中奖金：¥{reward:.2f}丨收益：¥{profit:.2f}")
