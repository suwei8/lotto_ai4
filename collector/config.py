from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


LOTTERY_ID = 6  # 福彩3D
DEFAULT_LIMIT = 1000
DEFAULT_ISSUE_COUNT = 5
DEFAULT_SORT_TYPES = (2, 4, 5)  # 红连、综合、黑连


@dataclass(frozen=True)
class PlaytypeSpec:
    playtype_id: int
    sort_types: Sequence[int] = DEFAULT_SORT_TYPES


PLAYTYPE_SPECS: tuple[PlaytypeSpec, ...] = (
    PlaytypeSpec(1001),  # 独胆
    PlaytypeSpec(1002),  # 双胆
    PlaytypeSpec(1003),  # 三胆
    PlaytypeSpec(1005),  # 五码组选
    PlaytypeSpec(1006),  # 六码组选
    PlaytypeSpec(1007),  # 七码组选
    PlaytypeSpec(2001),  # 杀一
    PlaytypeSpec(2002),  # 杀二
    PlaytypeSpec(3013),  # 百位定3
    PlaytypeSpec(3014),  # 十位定3
    PlaytypeSpec(3015),  # 个位定3
    PlaytypeSpec(3016),  # 百位定1
    PlaytypeSpec(3017),  # 十位定1
    PlaytypeSpec(3018),  # 个位定1
    PlaytypeSpec(3003),  # 定位3*3*3（后续拆分）
    PlaytypeSpec(3004),  # 定位4*4*4（后续拆分）
    PlaytypeSpec(3005),  # 定位5*5*5（后续拆分）
)
