# FusionRecommendation - 功能需求文档（新版本）

## 1. 页面背景
为福彩3D提供“融合推荐分析”：聚合同期多专家、多玩法的推荐结果，形成“共识推荐数字”与“按玩法的推荐热力图”，并展示开奖号码提示。

技术栈：Streamlit 最新版本（layout=wide）。
固定彩种：福彩3D；权限：只读；数据来源：lotto_3d 单库；免登录

## 2. 功能需求

模块A：期号选择与开奖号码提示
- 功能描述
  - 选择当前分析期号，展示该期开奖号码（若已开奖）。
- 输入与输出
  - 输入：issue_name（单选，按最新到最旧排序）
  - 输出：open_code（若存在则展示为“x、y、z”）
- 系统依赖（数据库）
  - lotto_3d.expert_predictions(issue_name) 用于获取期号集合（去重）
  - lotto_3d.lottery_results(issue_name, open_code)
- 新数据库映射
  - 使用 expert_predictions.issue_name 生成期号列表
  - 使用 lottery_results.issue_name/open_code 显示开奖号码


模块B：玩法与推荐数据聚合（融合推荐）
- 功能描述
  - 汇集所选期的专家推荐数据，生成“共识推荐数字”列表（按被推荐次数降序）。
  - 对于福彩3D（单区）：只统计红区（单区）数字；过滤“杀号”类玩法。
- 输入与输出
  - 输入：issue_name
  - 输出：单区共识推荐数字的频次表（字段：数字、被推荐次数、排名）
- 系统依赖（数据库）
  - lotto_3d.expert_predictions(issue_name, playtype_id, numbers, user_id)
  - lotto_3d.playtype_dict(playtype_id, playtype_name)
  - lotto_3d.expert_info(user_id, nick_name)（用于显示专家昵称的场景可选）
- 新数据库映射
  - 玩法名通过 playtype_dict 映射
  - repeat_mode 权重=1
  - 过滤规则（单区）：playtype_name 含“杀”的记录不参与“共识推荐数字”累计
  - 数字拆分：numbers 可能含“|”分区（兼容历史格式）；统一拆分后对“0-9”计数

模块C：按玩法的推荐热力图
- 功能描述
  - 将同一期、同玩法下的所有推荐数字进行统计，生成玩法维度的“数字-推荐次数”条形图（或热力图）。
- 输入与输出
  - 输入：issue_name
  - 输出：按 playtype 分组的数字推荐次数数据集与图表
- 系统依赖（数据库）
  - lotto_3d.expert_predictions(issue_name, playtype_id, numbers)
  - lotto_3d.playtype_dict(playtype_id, playtype_name)
- 新数据库映射与差异
  - 名称通过 playtype_dict 映射获取（基于 playtype_id）
  - 单区：依据出现的最大数字动态确定 x 轴范围（默认 0..9）

模块D：专家列表（可选）
- 功能描述
  - 可选显示本期参与融合统计的专家与其推荐项摘要（拼接 numbers）。
- 输入与输出
  - 输入：issue_name
  - 输出：表格（user_id、nick_name、推荐项摘要）
- 系统依赖（数据库）
  - lotto_3d.expert_predictions(user_id, numbers)
  - lotto_3d.expert_info(user_id, nick_name)

## 3. 非功能性需求
- 技术栈：Python 3.11 + Streamlit 最新版本
- 使用 Streamlit 的 session_state、组件扩展、st.cache_data 缓存优化交互与性能
- 性能
  - 优先按期号筛选，避免全表扫描。
  - 建议索引：
    - expert_predictions: (issue_name, playtype_id), (issue_name, playtype_id, user_id)
    - lottery_results: (issue_name)
    - playtype_dict: (playtype_id)
  - 查询流程：先取本期 predictions → 应用层拆分/过滤 → 统计聚合，避免跨期大聚合。
- 技术
  - 基于 Streamlit 最新版本，使用 session_state、组件扩展、st.cache_data 等优化交互与性能
- 安全
  - 全部只读查询；不执行写操作。


## 4. 风险与限制
- 已知问题
  - 若 numbers 格式包含“|”或空白，需要统一拆分与清洗。
  - 若缺少 playtype_dict 映射，展示层需兜底显示 playtype_id。
- 数据迁移限制


## 5. 页面-数据库字段清单与用途映射
- 期号列表：expert_predictions(issue_name) → DISTINCT + 排序
- 开奖提示：lottery_results(issue_name, open_code)
- 融合推荐（单区）：
  - expert_predictions(issue_name, playtype_id, numbers)
  - playtype_dict(playtype_id → playtype_name) 用于名称展示与过滤“杀号”类玩法
- 热力图（按玩法）：
  - expert_predictions(issue_name, playtype_id, numbers) → 数字计数
  - playtype_dict(playtype_id → playtype_name)

## 附录A：SQL 示例
- 获取某期玩法及名称
```sql
SELECT DISTINCT p.playtype_id, d.playtype_name
FROM lotto_3d.expert_predictions p
LEFT JOIN lotto_3d.playtype_dict d
  ON d.playtype_id = p.playtype_id
WHERE p.issue_name = :issue_name
ORDER BY d.playtype_id;
```

- 获取某期预测数据（用于融合与热力图）
```sql
SELECT p.user_id, p.playtype_id, p.numbers
FROM lotto_3d.expert_predictions p
WHERE p.issue_name = :issue_name;
```

- 开奖号码（用于页面提示）
```sql
SELECT open_code
FROM lotto_3d.lottery_results
WHERE issue_name = :issue_name
LIMIT 1;
```

## 7. 融合与热力图口径（单区，福彩3D）
- 共识推荐数字（融合）
  - 过滤掉 playtype_name 包含“杀”的玩法
  - 对每条 numbers：
    - 若含“|”，按“|”拆分后再按“,”拆分；否则直接按“,”拆分
    - 去空格、保留 0-9 的数字，逐个累计次数
  - 输出按次数降序，附带排名
- 按玩法热力图
  - 先按 playtype_id 分组，再对组内所有 numbers 进行同上拆分与计数
  - x 轴为“推荐次数”，y 轴为“数字”，按次数降序
  - 标题显示“玩法：{playtype_name或playtype_id}”

## 8. 索引与查询建议（lotto_3d 实态）
- 现有索引（节选）
  - expert_predictions: PRIMARY(id, issue_name), idx_user_id(user_id)
  - lottery_results: PRIMARY(id)
  - expert_hit_stat: PRIMARY(id, issue_name), idx_issue_name(issue_name)
- 建议补充
  - expert_predictions: (issue_name, playtype_id)、(issue_name, playtype_id, user_id)
  - lottery_results: (issue_name)
  - playtype_dict: (playtype_id)

## 9. 兼容性注意
- 如需关联专家昵称展示，建议使用派生表/临时表替代“LIMIT + IN 子查询”写法，避免部分 MySQL 版本报错。

## 附录B：校验样例（可选，lotto_3d）
- 最新期号（lotto_3d.lottery_results）：2025249
- 本期可用玩法（expert_predictions DISTINCT playtype_id）：
  [1001, 1002, 1003, 1005, 1006, 1007, 2001, 2002, 3013, 3014, 3015, 3016, 3017, 3018, 30031, 30032, 30033, 30041, 30042, 30043, 30051, 30052, 30053]
- 本期预测记录数：
  SELECT COUNT(*) FROM lotto_3d.expert_predictions WHERE issue_name = '2025249' → 34500
- 样例行（issue_name = 2025249）：
  - (user_id=555, playtype_id=1001, numbers='0')
  - (user_id=555, playtype_id=1002, numbers='0,6')
  - (user_id=555, playtype_id=1003, numbers='0,2,6')
  - (user_id=555, playtype_id=1005, numbers='0,2,4,6,8')
  - (user_id=555, playtype_id=1006, numbers='0,1,2,4,6,8')
  - (user_id=555, playtype_id=1007, numbers='0,1,2,4,6,7,8')
  - (user_id=555, playtype_id=2001, numbers='3')
  - (user_id=555, playtype_id=2002, numbers='3,5')
  - (user_id=555, playtype_id=30031, numbers='1,4,6')
  - (user_id=555, playtype_id=30032, numbers='0,1,6')

说明：
- 全部基于新库 lotto_3d 的实时查询，不涉及任何旧版字段或表。
- 示例仅用于验证口径与数据存在性；实际页面实现按本需求文档的字段与索引建议执行。