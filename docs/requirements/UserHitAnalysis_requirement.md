# 【专家多期命中分析】UserHitAnalysis - 功能需求文档

## 1. 页面背景
针对指定专家，在所选期号集合与玩法维度下，统计其多期命中表现（命中期数、命中数字数量、趋势），并输出综合画像（各玩法命中概览与平均命中间隔）。
固定彩种：福彩3D；权限：只读；数据来源：lotto_3d 单库；免登录

## 2. 功能需求

模块A：基础选择
- 功能描述：选择期号集合、玩法、目标专家 user_id。
- 输入与输出
  - 输入：issue_names[]（多选）、playtype（单选，名称或ID皆可，但推荐以 playtype_id 驱动）、user_id（单值）
  - 输出：所选条件
- 系统依赖（表/字段）
  - lotto_3d.expert_predictions(issue_name, user_id, playtype_id, numbers)
  - lotto_3d.playtype_dict(playtype_id, playtype_name)
- 新数据库映射（示例SQL）
  - 期号集合：
    SELECT DISTINCT issue_name FROM expert_predictions ORDER BY issue_name DESC;
  - 玩法列表：
    SELECT playtype_id, playtype_name FROM playtype_dict ORDER BY playtype_id;

模块B：多期命中统计（按期汇总）
- 功能描述：对目标 user_id 在所选 issues × 玩法 下的每一期，计算命中情况与命中数字数量。
- 输入与输出
  - 输入：issue_names[]、playtype_id、user_id
  - 输出：每期记录字段
    - 期号、推荐组合（合并展示）、推荐组合数
    - 命中数（当期该玩法命中组合数量）
    - 命中数字数量（count_hit_numbers_by_playtype 结果累加）
    - 开奖号码（open_code）
- 系统依赖（表/字段/函数）
  - expert_predictions(issue_name, playtype_id, user_id, numbers)
  - lottery_results(issue_name, open_code)
  - 命中规则引擎：应用层按 playtype 判定
  - 命中数字统计：应用层实现
- 新数据库映射（示例SQL）
  - 单期拉取该专家该玩法的推荐：
    SELECT numbers
    FROM expert_predictions
    WHERE issue_name = ? AND user_id = ? AND playtype_id = ?;
  - 获取开奖号码：
    SELECT open_code FROM lottery_results WHERE issue_name = ?;

模块C：趋势与汇总展示
- 功能描述：展示“命中数/命中数字数量”多期趋势折线图；统计总期数、命中期数、未命中期数。
- 输入与输出
  - 输入：B模块每期统计结果
  - 输出：折线图（x=期号，y1=命中数，y2=命中数字数量）、期汇总统计
- 系统依赖：前端可视化（Altair）

模块D：专家综合画像（按玩法聚合）
- 功能描述：在所选 issues 范围内，统计该专家在各玩法的推荐数、命中期数、命中数字数量与“平均命中间隔”（以命中的期号自然差均值表达）。
- 输入与输出
  - 输入：issue_names[]、user_id
  - 输出：玩法画像表（字段：玩法、推荐数、命中期数、命中数字数量、平均命中间隔）
- 系统依赖（表/字段/函数）
  - expert_predictions(issue_name, playtype_id, user_id, numbers)
  - playtype_dict(playtype_id, playtype_name)
  - lottery_results(issue_name, open_code)
  - 命中规则引擎：应用层按 playtype 判定；命中数字统计：应用层实现
- 新数据库映射（示例SQL）
  - 拉取该专家在所选期内的所有推荐（附玩法名）：
    SELECT ep.issue_name, ep.playtype_id, pd.playtype_name, ep.numbers
    FROM expert_predictions ep
    JOIN playtype_dict pd ON pd.playtype_id = ep.playtype_id
    WHERE ep.user_id = ? AND ep.issue_name IN (?,?,...);

- 平均命中间隔计算说明：
  - 取该玩法命中的所有期号，按数值排序，按相邻差分求均值；仅1次命中可显示“1命中”，0次命中显示“∞”。

模块E：详情与交互
- 功能描述：
  - 表格：展示B模块每期统计结果；可按期号倒序
  - 画像表：展示D模块玩法聚合结果；条形图 + 文本标注（平均命中间隔）
- 输入与输出
  - 输入：B/D模块数据
  - 输出：DataFrame + Altair 图表

## 3. 非功能性需求
- 技术栈：Python 3.11 + Streamlit 最新版本
- 使用 Streamlit 的 session_state、组件扩展、st.cache_data 等优化交互与性能
- 性能
  - 索引建议：
    - expert_predictions(issue_name, playtype_id, user_id)
    - playtype_dict(playtype_id)
    - lottery_results(issue_name)
  - 查询策略：
    - issues 集合适当限长；批量 IN 查询减少往返
    - 开奖信息可按 issues 一次性批量读取缓存于内存映射
- 安全
  - 仅读操作
- 可扩展性
  - 命中判定集中在应用层规则引擎，新增玩法仅需补充规则

## 4. 风险与限制
- 口径一致性：命中数与命中数字数量定义需与业务确认（如同一期多组合命中时的计数口径）
- 开奖缺失：当期缺少 open_code 时，仅展示次数统计，不进行命中高亮
- 数据规模：多期 × 多玩法计算量较大时需分页或分段渲染
- 技术
  - 基于 Streamlit 最新版本，使用 session_state、组件扩展、缓存优化（如 st.cache_data）提升交互与性能

新数据库映射速查（lotto_3d）
- 期号/玩法：
  FROM expert_predictions ⇒ DISTINCT issue_name; JOIN playtype_dict ⇒ (playtype_id, playtype_name)
- 多期推荐（单专家单玩法）：
  FROM expert_predictions WHERE issue_name IN (...) AND user_id = ? AND playtype_id = ? ⇒ numbers
- 开奖信息：
  FROM lottery_results WHERE issue_name = ? ⇒ open_code
- 画像（单专家多玩法）：
  FROM expert_predictions JOIN playtype_dict ON playtype_id ⇒ (issue_name, playtype_id, playtype_name, numbers)