# 组件使用速览

统一的 Streamlit 组件封装可以帮助我们在业务页面中快速接入期号/玩法选择、开奖信息、数字频次图等能力，实现“一处修改，全站生效”。以下示例展示了常用组件的使用方法。

## 期号选择器 `issue_picker`
```python
from utils.ui import issue_picker

# 单选，默认使用 lottery_results 中的最新 200 期
iqueu = issue_picker("sample_issue")

# 多选，从预测数据源获取期号，并指定默认值
issues = issue_picker(
    "sample_multi_issue",
    mode="multi",
    source="predictions",
    default=["2025250", "2025249"],
)

# 使用自定义期号列表（如某张视图返回的专用期号序列）
custom_issues = issue_picker(
    "sample_custom_issue",
    options=["2025253", "2025252", "2025251"],
)
```

## 玩法选择器 `playtype_picker`
```python
from utils.ui import playtype_picker

# 多选（默认全选）
playtypes = playtype_picker("sample_playtypes")

# 单选，并限制在给定玩法 ID 范围内
playtype_id = playtype_picker(
    "sample_playtype",
    mode="single",
    include=["1003", "1005", "3016"],
)

# 按分组排序展示（group_labels 中的 key 必须是字符串 ID）
playtype_id = playtype_picker(
    "sample_grouped_playtype",
    mode="single",
    group_labels={"1003": "胆码", "3016": "定位"},
)
```

## 开奖信息组件 `render_open_info`
```python
from utils.ui import render_open_info

# 渲染开奖号码/和值/跨度，可通过指标或 caption 控制展示形式
render_open_info("2025253", key="demo_open")
render_open_info("2025253", key="demo_open_light", show_metrics=False)
```

## 专家选择器 `expert_picker`
```python
from utils.ui import expert_picker

# 根据指定期号列出已推荐专家，并支持手动输入
user_id, expert_map = expert_picker(
    "sample_expert_picker",
    issue="2025253",
    allow_manual=True,
)

# 仅允许从列表选择（不支持手动输入）
user_id, expert_map = expert_picker(
    "sample_expert_fixed",
    issue="2025253",
    allow_manual=False,
)
```

## 数字频次图 `render_digit_frequency_chart`
```python
from utils.charts import render_digit_frequency_chart

freq_df = pd.DataFrame({"数字": list("012345"), "被推荐次数": [5, 8, 3, 6, 2, 4]})
chart = render_digit_frequency_chart(freq_df, hit_digits=["1", "3"])
if chart is not None:
    st.altair_chart(chart, use_container_width=True)
```

## 排行榜位置数字计算器 `render_rank_position_calculator`
```python
from utils.ui import render_rank_position_calculator

entries = [
    ("三胆", ["1", "2", "3", "4"]),
    ("百位定1", ["5", "6", "7"]),
]
render_rank_position_calculator(entries, key="sample_rank")
```

## 建议接入步骤
1. **替换期号/玩法选择**：优先使用 `issue_picker`、`playtype_picker`，减少直接调用 `st.selectbox`。  
2. **统一开奖信息展示**：在查询页顶部调用 `render_open_info(issue)`，保持指标一致。  
3. **数字类图表**：凡是生成数字频次条形图的场景，改用 `render_digit_frequency_chart`。  
4. **排行榜相关逻辑**：使用 `render_rank_position_calculator`，自动处理玩法筛选与统计计算。  
5. **专家选择**：在需要选择/输入专家 `user_id` 的场景，使用 `expert_picker`。  
6. **编写新页面** 时，参考以上组件组合即可快速搭建基础结构。  

如需扩展组件功能（例如新增样式、更多图表类型），只需更新组件实现即可全局生效。欢迎在 `utils/ui.py` 与 `utils/charts.py` 中继续迭代。