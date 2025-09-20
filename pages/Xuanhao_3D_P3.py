# pages/Xuanhao_3D_P3.py
# 组选/直选号码生成器 + 盈利模拟
import streamlit as st
from itertools import combinations, product, permutations

st.set_page_config("🎰 老苏组选/直选号码生成器", layout="wide")
st.title("🎰 老苏组选/直选号码生成器 + 盈利模拟")

mode = st.selectbox("选号模式", ["组选", "直选"])
# ===== 高级过滤器设置（保留原选号逻辑）=====
st.markdown("🔍 **高级过滤条件扩展（和值/跨度/奇偶/大小/连号）**")
col1, col2 = st.columns(2)
with col1:
    sum_filters = st.multiselect("和值过滤（排除）", list(range(28)), default=[])
    sum_range = st.slider("和值范围（保留）", 0, 27, (0, 27))
with col2:
    span_filters = st.multiselect("跨度过滤（排除）", list(range(10)), default=[])
    span_range = st.slider("跨度范围（保留）", 0, 9, (0, 9))

col3, col4 = st.columns(2)
with col3:
    allowed_odd_even = st.multiselect("奇偶比（保留）", ["3:0", "2:1", "1:2", "0:3"], default=[])
with col4:
    allowed_big_small = st.multiselect("大小比（保留）", ["3:0", "2:1", "1:2", "0:3"], default=[])

exclude_lianhao = st.checkbox("❌ 排除包含连续数字组合", value=False)

# ===== 组选输入 =====
if mode == "组选":
    col1, col2, col3 = st.columns(3)
    with col1:
        group_type = st.selectbox("组选类型", ["组六", "组三"])
    with col2:
        include_digits = st.multiselect("包含数字", list(range(10)), default=[9])
    with col3:
        exclude_digits = st.multiselect("排除数字", list(range(10)), default=[])

# ===== 直选输入 =====
if mode == "直选":
    col_f3, col_f4, col_f5 = st.columns(3)
    with col_f3:
        filter_group3 = st.checkbox("过滤组三", value=False)
    with col_f4:
        filter_baozi = st.checkbox("过滤豹子", value=False)
    with col_f5:
        filter_group6 = st.checkbox("过滤组六", value=False)

    st.markdown("📍 **设置直选每一位上的候选数字**")
    col_b, col_s, col_g = st.columns(3)
    with col_b:
        bai_list = st.multiselect("百位", list(range(10)), default=list(range(10)))
    with col_s:
        shi_list = st.multiselect("十位", list(range(10)), default=list(range(10)))
    with col_g:
        ge_list = st.multiselect("个位", list(range(10)), default=list(range(10)))

    st.markdown("🔍 **过滤条件（任选）**")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        include_digits = st.multiselect("包含数字", list(range(10)), default=[])
    with col_f2:
        exclude_digits = st.multiselect("排除数字", list(range(10)), default=[])

# ===== 生成函数 =====
def generate_group6(include_digits, exclude):
    result = []
    for d in include_digits:
        pool = [x for x in range(10) if x != d and x not in exclude]
        result += [tuple(sorted((a, b, d))) for a, b in combinations(pool, 2)]
    return sorted(set(result))

def get_odd_even_ratio(digits):
    odd = sum(1 for d in digits if d % 2 == 1)
    even = 3 - odd
    return f"{odd}:{even}"

def get_big_small_ratio(digits):
    big = sum(1 for d in digits if d >= 5)
    small = 3 - big
    return f"{big}:{small}"

def has_consecutive(digits):
    digits = sorted(digits)
    return any(digits[i + 1] - digits[i] == 1 for i in range(2))

def filter_advanced(numbers):
    result = []
    for code in numbers:
        digits = list(code)
        s = sum(digits)
        sp = max(digits) - min(digits)
        if s in sum_filters or sp in span_filters:
            continue
        if not (sum_range[0] <= s <= sum_range[1]):
            continue
        if not (span_range[0] <= sp <= span_range[1]):
            continue
        if allowed_odd_even and get_odd_even_ratio(digits) not in allowed_odd_even:
            continue
        if allowed_big_small and get_big_small_ratio(digits) not in allowed_big_small:
            continue
        if exclude_lianhao and has_consecutive(digits):
            continue
        result.append(code)
    return result

def generate_group3(include_digits, exclude):
    result = []
    for d in include_digits:
        pool = [x for x in range(10) if x != d and x not in exclude]
        for x in pool:
            result.append(tuple(sorted([d, d, x])))
            result.append(tuple(sorted([x, x, d])))
    return sorted(set(result))

def generate_zhixuan(bai, shi, ge, include_digits=None, exclude_digits=None,
                      filter_group3=False, filter_baozi=False, filter_group6=False):
    include_digits = include_digits or []
    exclude_digits = exclude_digits or []
    result = []
    for b, s, g in product(bai, shi, ge):
        digits = [b, s, g]
        if include_digits and not any(d in digits for d in include_digits):
            continue
        if any(d in digits for d in exclude_digits):
            continue
        if filter_group3 and (b == s or s == g or b == g) and not (b == s == g):
            continue
        if filter_baozi and b == s == g:
            continue
        if filter_group6 and len(set(digits)) == 3:
            continue
        result.append((b, s, g))
    return result

# ===== 生成号码 =====
numbers = []
if mode == "组选":
    if group_type == "组六":
        numbers = generate_group6(include_digits, exclude_digits)
        numbers = filter_advanced(numbers)
        prize_per_win = 280
    else:
        numbers = generate_group3(include_digits, exclude_digits)
        numbers = filter_advanced(numbers)
        prize_per_win = 550
else:
    numbers = generate_zhixuan(
        bai_list,
        shi_list,
        ge_list,
        include_digits,
        exclude_digits,
        filter_group3=filter_group3,
        filter_baozi=filter_baozi,
        filter_group6=filter_group6,
    )
    numbers = filter_advanced(numbers)
    prize_per_win = 1700

# ===== 倍数与成本 =====
col1, col2 = st.columns(2)
with col1:
    group_multiplier = st.number_input("组选倍数", min_value=0, max_value=100000, value=2)
with col2:
    zhixuan_multiplier = st.number_input("直选倍数", min_value=0, max_value=100000, value=1)

group_count = len(numbers) * group_multiplier
zhixuan_count = len(numbers) * zhixuan_multiplier
total_count = group_count + zhixuan_count
bet_cost = total_count * 2

# ===== 奖金估算 =====
group_bonus = 0
zhixuan_bonus = 0
bonus_note = ""
if mode == "组选":
    if group_multiplier > 0:
        group_bonus = group_multiplier * (280 if group_type == "组六" else 550)
        if zhixuan_multiplier > 0:
            zhixuan_bonus = zhixuan_multiplier * 1700
            bonus_note = "假设组选与直选各命中1注"
        else:
            bonus_note = "假设组选命中1注"
    elif zhixuan_multiplier > 0:
        zhixuan_bonus = zhixuan_multiplier * 1700
        bonus_note = "假设直选命中1注"
    else:
        bonus_note = "无奖金（无投注）"
else:
    if zhixuan_multiplier > 0:
        zhixuan_bonus = zhixuan_multiplier * 1700
        if group_multiplier > 0:
            group_bonus = group_multiplier * 280
            bonus_note = "假设组选与直选各命中1注"
        else:
            bonus_note = "假设直选命中1注"
    elif group_multiplier > 0:
        group_bonus = group_multiplier * 280
        bonus_note = "假设组选命中1注"
    else:
        bonus_note = "无奖金（无投注）"

bonus_total = group_bonus + zhixuan_bonus
profit = bonus_total - bet_cost

# ===== 文本输出 =====
number_str_list = ["".join(map(str, row)) for row in numbers]
number_text = ",".join(number_str_list)
st.text_area(
    "生成号码（可复制）",
    f"{number_text} 共{len(numbers)}注，组选{group_multiplier}倍，直选{zhixuan_multiplier}倍，{bet_cost}元",
    height=100,
)

st.markdown(f"**投注注数：{total_count} 注（组选 {group_count} 注 + 直选 {zhixuan_count} 注）**")
st.markdown(f"**投注成本：{bet_cost} 元**")
st.markdown(f"**奖金合计：{bonus_total} 元（{bonus_note}）**")
st.markdown(f"**纯收益：{'盈利' if profit >= 0 else '亏损'} {abs(profit)} 元**")

# ===== 定位调整器 =====
if mode == "组选":
    with st.expander("🎯 指定百/十/个位数字进行定位调整（批量变换器）", expanded=False):
        col_bai, col_shi, col_ge = st.columns(3)
        with col_bai:
            bai_digits = st.multiselect("百位应包含", list(range(10)), default=[], key="pos_bai")
        with col_shi:
            shi_digits = st.multiselect("十位应包含", list(range(10)), default=[], key="pos_shi")
        with col_ge:
            ge_digits = st.multiselect("个位应包含", list(range(10)), default=[], key="pos_ge")

        index_map = {0: bai_digits, 1: shi_digits, 2: ge_digits}
        use_position_filter = any(index_map.values())

        if use_position_filter:
            adjusted = []
            for code in numbers:
                digits = list(code)
                for perm in set(permutations(digits)):
                    if all(not index_map[i] or perm[i] in index_map[i] for i in range(3)):
                        adjusted.append("".join(map(str, perm)))
                        break
                else:
                    adjusted.append("".join(map(str, code)))
            result_text = ",".join(adjusted)
        else:
            result_text = number_text

        tail_note = f"共{len(numbers)}注，组选{group_multiplier}倍，直选{zhixuan_multiplier}倍，{bet_cost}元"
        st.text_area(
            "✅ 定位调整后排列（可复制）",
            f"{result_text} {tail_note}",
            height=100,
        )
