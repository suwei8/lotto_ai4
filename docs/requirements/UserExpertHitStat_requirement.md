# 【AI命中统计分析】UserExpertHitStat - 功能需求文档

## 1. 页面背景
按期号集合与玩法维度，聚合展示专家的命中表现（命中期数、命中数字数量、命中率等），并支持按命中维度筛选后反查指定期号的推荐记录与可视化（热力图、推荐详情）。
固定彩种：福彩3D；权限：只读；数据来源：lotto_3d 单库；免登录

## 2. 功能需求

模块A：基础选择
- 功能描述：选择期号集合与玩法，用于统计与反查。
- 输入与输出
  - 输入：issues[]（多选）、playtype_name（单选）
  - 输出：已选 issues 与玩法
- 系统依赖（lotto_3d 表/字段）
  - expert_hit_stat(issue_name, user_id, playtype_name, total_count, hit_count, hit_number_count, avg_hit_gap)
  - playtype_dict(playtype_id, playtype_name) 用于构建玩法列表（可选）
- 映射与示例
  - 期号列表（统计源）：SELECT DISTINCT issue_name FROM expert_hit_stat ORDER BY issue_name DESC;
  - 玩法列表（当前期）：SELECT DISTINCT playtype_name FROM expert_hit_stat WHERE issue_name = ?;

模块B：命中统计聚合
- 功能描述：按 user_id 聚合多期统计，得到命中指标并排序展示。
- 输入与输出
  - 输入：issues[]、playtype_name
  - 输出：表格字段
    - user_id
    - AI昵称（expert_info.nick_name）
    - 命中期数（Σ hit_count）
    - 预测期数（Σ total_count）
    - 命中数字数量（Σ hit_number_count）
    - 命中率（命中数字数量 / 预测期数，四舍五入4位）
- 系统依赖（lotto_3d 表/字段）
  - expert_hit_stat(user_id, total_count, hit_count, hit_number_count)
  - expert_info(user_id, nick_name)
- 示例（按 user_id 聚合求和）
  SELECT user_id,
         SUM(total_count) AS total_count,
         SUM(hit_count) AS hit_count,
         SUM(hit_number_count) AS hit_number_count
  FROM expert_hit_stat
  WHERE issue_name IN (?, ?, ...)
    AND playtype_name = ?
  GROUP BY user_id;

模块C：命中期数/命中数字数量分布
- 功能描述：统计区间内“命中期数”与“命中数字数量”的分布并可视化。
- 输入与输出
  - 输入：B模块聚合结果
  - 输出：两组分布数据（值→人数、占比），支持并列分栏展示
- 依赖：B模块结果数据（前端聚合）

模块D：筛选并反查推荐记录
- 功能描述：基于“命中期数”“命中数字数量”以及“上期命中状态”的筛选，反查指定期号的专家推荐记录，并可视化数字频次与命中高亮。
- 输入与输出
  - 输入：
    - 命中期数筛选值[]（来自B结果）
    - 命中数字数量筛选值[]（来自B结果）
    - 上期命中状态：不过滤 / 上期命中 / 上期未命中
    - 查询期号 query_issue（下拉）
    - 查询玩法 query_playtype（与A的玩法集合一致）
  - 输出：
    - 推荐热力图（数字→出现次数，命中高亮）
    - 推荐详情表格（user_id, nick_name, numbers, 命中数量, 是否命中）
- 系统依赖（lotto_3d 表/字段/函数）
  - expert_predictions(issue_name, playtype_id/或按名称, user_id, numbers)
  - expert_info(user_id, nick_name)
  - lottery_results(issue_name, open_code)
  - expert_hit_stat(issue_name, user_id, playtype_name, hit_count) 用于“上期命中状态”
  - 命中规则：应用层命中规则引擎（按 playtype 判定）
- 映射与示例
  - 查询期号候选（统计期号 ∪ 预测期号）：
    SELECT DISTINCT issue_name FROM expert_hit_stat
    UNION
    SELECT DISTINCT issue_name FROM expert_predictions
    ORDER BY issue_name DESC;
  - 上期命中状态（基于上一期汇总）：
    SELECT user_id, hit_count
    FROM expert_hit_stat
    WHERE issue_name = ? AND playtype_name = ?;
    -- 命中：hit_count > 0；未命中：hit_count = 0
  - 名称/ID映射：playtype_name 与 playtype_id 通过 playtype_dict 互转，避免歧义。
  - 本期推荐记录（限定 user_ids）：
    SELECT user_id, numbers
    FROM expert_predictions
    WHERE issue_name = ?
      AND playtype_id = ? -- 或以名称等价过滤
      AND user_id IN (?, ?, ...);

模块E：可视化与详情
- 功能描述：
  - 热力图：数字出现次数，命中数字高亮
  - 详情表：按“命中数量”降序（若开奖缺失则不排序）
- 输入与输出
  - 输入：rec_df（推荐记录）、开奖信息、昵称映射
  - 输出：Altair 柱状图 + 推荐详情 DataFrame
- 系统依赖（函数）
  - 开奖信息读取：从 lottery_results 取 open_code
  - 命中规则引擎：应用层实现

## 3. 非功能性需求
- 技术栈：Python 3.12 + Streamlit 最新版本
- 使用 Streamlit 的 session_state、组件扩展、st.cache_data 等优化交互与性能
- 性能
  - 索引建议：
    - expert_hit_stat(issue_name, playtype_name, user_id)
    - expert_predictions(issue_name, playtype_id, user_id)
    - expert_info(user_id)
    - lottery_results(issue_name)
  - 查询合并：
    - 期号、玩法一次性拉取；聚合在 SQL 侧完成
    - 反查推荐记录按 user_ids 生成占位符一次查询
- 技术
  - 基于 Streamlit 最新版本，使用 session_state、组件扩展、st.cache_data 等优化交互与性能
- 安全
  - 只读查询
- 可扩展性
  - 命中特征与筛选参数（近N期、上期状态、操作符）可配置
  - 命中规则集中在 hit_rule，便于玩法扩展

## 4. 风险与限制
- 统计口径
  - 命中率=命中数字数量/预测期数；请与业务确认是否需改为“命中期数/预测期数”
- 开奖缺失
  - 当期未开奖时，热力图仅展示次数统计，命中列使用占位
- 数据体量
  - 多期 × 多玩法聚合可能较大，建议分页/分段渲染与必要缓存

新数据库映射速查（lotto_3d）
- 统计源：
  FROM expert_hit_stat WHERE issue_name IN (...) AND playtype_name = ? ⇒ user_id, total_count, hit_count, hit_number_count
- 推荐反查：
  FROM expert_predictions WHERE issue_name = ? AND playtype_id = ? AND user_id IN (...)
  ⇒ user_id, numbers
- 昵称映射：
  FROM expert_info ⇒ user_id, nick_name
- 开奖信息：
  FROM lottery_results WHERE issue_name = ?
  ⇒ open_code, sum, span, odd_even_ratio, big_small_ratio, open_time