# ExpertHitTop - 功能需求文档（新版本）

## 1. 页面背景
ExpertHitTop 对应“福彩3D”的专家命中表现分析页面，数据来自 lotto_3d。目标是在指定期段与玩法维度下，以排行榜与图表方式展现专家的命中率、命中次数、稳定性等核心指标，并支持明细下钻。

说明：
- 技术栈：基于 Streamlit 最新版本开发（前后端同构、快速原型与数据可视化）。

- 数据合规：严格禁用已废弃表/字段（详见“风险与限制”）。
- 固定彩种：福彩3D；权限：只读；数据来源：lotto_3d 单库；免登录

## 2. 功能需求

模块 A：期号与玩法筛选
- 功能描述
  - 固定彩种为“福彩3D”，提供期号范围与玩法筛选，驱动后续统计与展示。
- 输入与输出
  - 输入：
    - 期号范围：支持“最新 N 期（10/30/50/100）”或“自定义起止期号/单期”。
    - 玩法：下拉多选/单选。
  - 输出：
    - 回显当前统计窗口（起止期号或“近 N 期”）与玩法集合。
- 使用场景
  - 用户快速限定分析时间窗与玩法维度。
- 系统依赖（仅新数据库）
  - 表：lotto_3d.lottery_results
    - 字段：issue_name, open_time（用于获取最新期、期号序与最近 N 期）
  - 表：lotto_3d.playtype_dict
    - 字段：playtype_id, playtype_name
  - 说明：以 playtype_id + playtype_dict 获取名称。
- 新数据库映射
  - “期号范围”来源：lottery_results.issue_name（结合 open_time 做最近 N 期计算）
  - “玩法下拉”来源：playtype_dict；显示 playtype_name，提交 playtype_id

模块 B：专家命中排行榜
- 功能描述
  - 汇总筛选范围下专家表现，展示命中率、命中次数、预测次数、平均命中间隔等核心指标，可排序、分页。
- 输入与输出
  - 输入：期号范围、玩法集合、排序项（命中率/命中次数/平均间隔）、分页参数。
  - 输出：表格列建议
    - 用户ID（user_id）
    - 专家昵称（nick_name）
    - 玩法（playtype_name，或用 playtype_id 关联字典得到）
    - 预测次数（total_count）
    - 命中次数（hit_count）
    - 命中率（hit_count/total_count，保留 2 位小数）
    - 命中号码覆盖数（hit_number_count，针对 3D 的覆盖维度）
    - 平均命中间隔（avg_hit_gap，数值越小越密集）
- 使用场景
  - 快速筛选高命中专家，辅助选择与复盘。
- 系统依赖（仅新数据库）
  - 表：lotto_3d.expert_hit_stat（预聚合快表，优先读取以避免即席聚合）
    - 字段：id, issue_name, user_id, playtype_name, total_count, hit_count, hit_number_count, avg_hit_gap
    - 建议演进：将 playtype_name 调整为 playtype_id，查询时关联 playtype_dict 获取名称（降低字典漂移风险）。
  - 表：lotto_3d.expert_info
    - 字段：user_id, nick_name
- 新数据库映射
  - 列映射：user_id -> expert_info.user_id；nick_name -> expert_info.nick_name
  - 指标来源：total_count/hit_count/hit_number_count/avg_hit_gap -> expert_hit_stat
  - 玩法名：由 expert_hit_stat.playtype_name（现状）或通过 playtype_id 关联 playtype_dict.playtype_name（演进方案）

模块 C：专家详情下钻（逐期对照）
- 功能描述
  - 点击某专家行，展示其在期段内的逐期预测与开奖结果对照，并标注是否命中。
- 输入与输出
  - 输入：user_id、playtype_id、期号范围。
  - 输出：明细列
    - 期号（issue_name）
    - 预测内容（numbers）
    - 开奖号码（open_code）
    - 开奖时间（open_time）
    - 命中标记（基于 3D 玩法规则对比 numbers 与 open_code）
- 使用场景
  - 验证排行榜指标、复盘策略可信度。
- 系统依赖（仅新数据库）
  - 表：lotto_3d.expert_predictions
    - 字段：id, user_id, issue_name, playtype_id, numbers
  - 表：lotto_3d.lottery_results
    - 字段：issue_name, open_code, open_time
  - 表：lotto_3d.playtype_dict
    - 字段：playtype_id, playtype_name
  - 说明：以现有字段进行统计。
- 新数据库映射
  - 明细：expert_predictions.issue_name/numbers 与 lottery_results.issue_name/open_code/open_time 做期号对照
  - 玩法：expert_predictions.playtype_id -> playtype_dict 获取 playtype_name

模块 D：玩法维度统计与可视化
- 功能描述
  - 玩法命中率热力图：展示每个玩法的整体命中率、命中专家数/专家数等摘要。
  - 推荐位置命中分布：对于每个玩法，统计“推荐位置”的出现次数、命中次数、命中率，用柱状图展示。
- 输入与输出
  - 输入：玩法集合、期号范围。
  - 输出：
    - 热力图（命中率默认降序）
    - 推荐位置命中分布图（每玩法一图，可按 4 图一行排版）

- 使用场景
  - 观察玩法稳定性，探索对策略优化有指导意义的结构性特征。
- 系统依赖（仅新数据库）
  - 数据源：优先 expert_hit_stat（聚合），必要时从 expert_predictions 明细与 lottery_results 校验命中。

- 新数据库映射
  - 玩法热力图：按 playtype_name（现状）或 playtype_id 汇总 expert_hit_stat 命中率/次数
  - 推荐位置分布：如需号码位次统计，可参考 red_val_list_v2 拓展（本页非必需）



模块 F：统计范围提示
- 功能描述
  - 页头/页脚展示“统计范围（近 N 期/自定义区间）与截止期号”提示。
- 输入与输出
  - 输入：期号范围、最新期信息。
  - 输出：文本提示。
- 系统依赖（仅新数据库）
  - 表：lotto_3d.lottery_results（issue_name, open_time）

## 3. 非功能性需求
- 技术栈：Python 3.12 + Streamlit 最新版本
- 使用 Streamlit 的 session_state、组件扩展、st.cache_data 缓存优化交互与性能

- 性能优化（统一标准）：
  - 聚合指标优先读取 expert_hit_stat，避免对 expert_predictions 做大范围联表
  - 复合索引建议：
    - expert_hit_stat: (issue_name, user_id, playtype_name) 或演进为 (issue_name, playtype_id, user_id)
    - expert_predictions: (issue_name, playtype_id, user_id)
    - lottery_results: (open_time, issue_name) 或 (issue_name)
  - 分页/TopN：所有查询需限制默认行数（如 Top 100 或 LIMIT 分页）

- 安全
  - 数据隔离：服务端仅连接与查询 lotto_3d；不允许跨库。
  - 只读接口：页面只涉及 SELECT；禁止写操作。
  - 最小授权：数据库账号仅授予 lotto_3d 的读权限。

- 可扩展性
  - 支持未来多彩种：通过配置化适配不同玩法与规则。
  - 字典治理：玩法名统一以 playtype_dict 维护，避免在预测表冗余。
  - 指标扩展：expert_hit_stat 可平滑增加字段（如最大连中/最大连挂），前端以动态列驱动。

- 技术栈
  - 基于 Streamlit 最新版本构建，Altair/Matplotlib 绘图，Pandas 数据处理；组件与布局按最新 API 规范实现。

## 4. 风险与限制

- 已知问题
  - expert_hit_stat 当前保存 playtype_name（非 playtype_id），存在字典漂移隐患；建议在后续版本迁移为 playtype_id，并在查询时关联 playtype_dict 获取名称。

- 数据迁移风险


  - 索引变更：新增复合索引需评估写入与存储成本，但可显著改善读性能。

---

## 5. 页面-数据库字段清单与用途映射

模块 A：期号与玩法筛选
- 功能要点：获取最新期/最近N期、提供玩法下拉（仅3D）
- 表与字段
  - lottery_results: issue_name, open_time
  - playtype_dict: playtype_id, playtype_name
- 主要用途
  - 近N期计算：基于 open_time 确定时间窗，取对应 issue_name 序列
  - 玩法下拉：展示 playtype_name，提交 playtype_id

模块 B：专家命中排行榜
- 功能要点：命中率、命中次数、预测次数、平均命中间隔，排序分页展示
- 表与字段
  - expert_hit_stat: id, issue_name, user_id, playtype_name, total_count, hit_count, hit_number_count, avg_hit_gap
  - expert_info: user_id, nick_name
  - playtype_dict（可选，用于名称标准化演进）：playtype_id, playtype_name
- 主要用途
  - 指标计算：直接使用 expert_hit_stat 聚合结果
  - 专家昵称：expert_info.nick_name
  - 玩法名：现状用 playtype_name（后续演进为 playtype_id 关联字典）

模块 C：专家详情下钻（逐期对照）
- 功能要点：逐期展示预测与开奖结果，并标注命中
- 表与字段
  - expert_predictions: id, user_id, issue_name, playtype_id, numbers
  - lottery_results: issue_name, open_code, open_time
  - playtype_dict: playtype_id, playtype_name
- 主要用途
  - 明细对照：expert_predictions.issue_name = lottery_results.issue_name
  - 命中判断：按 3D 玩法规则比对 numbers 与 open_code
  - 玩法名：playtype_id -> playtype_dict.playtype_name

模块 D：玩法维度统计与可视化
- 功能要点：玩法命中率热力图、推荐位置命中分布（可选）
- 表与字段
  - 优先 expert_hit_stat（聚合）；必要时 expert_predictions + lottery_results 校验
  - red_val_list_v2（可选扩展）：type, rank_count, 各种 *_map 统计字段（JSON）
- 主要用途
  - 热力汇总：按 playtype 分组统计命中率/次数
  - 扩展：如需号码权重/分布，结合 red_val_list_v2 拓展，不作为本页必需依赖



模块 F：统计范围提示
- 功能要点：显示“统计范围与截止期号”
- 表与字段
  - lottery_results: issue_name, open_time
- 主要用途
  - 显示起止期号或“近N期”与最新开奖时间

索引与性能（字段层级建议，基于实时结构）
- expert_hit_stat：PRIMARY(id, issue_name), idx_issue_name(issue_name)
  - 建议：若沿用 playtype_name，增 (issue_name, playtype_name, user_id)；若演进 playtype_id，增 (issue_name, playtype_id, user_id)
- expert_predictions：PRIMARY(id, issue_name), idx_user_id(user_id)
  - 建议：增 (issue_name, playtype_id, user_id)
- lottery_results：当前仅 PRIMARY(id)
  - 建议：增 (issue_name)（唯一或普通视业务）
- 外键：信息架构未登记外键关系，按逻辑关联进行 JOIN

附录 A：实时数据库结构（lotto_3d，经实查）
- expert_hit_stat
  - 字段：id, issue_name, user_id, playtype_name, total_count, hit_count, hit_number_count, avg_hit_gap
  - 索引：PRIMARY(id, issue_name), idx_issue_name(issue_name)
- expert_info
  - 字段：user_id, nick_name
- expert_predictions
  - 字段：id, user_id, issue_name, playtype_id, numbers
- lottery_results
  - 字段：id, issue_name, open_code, sum, span, odd_even_ratio, big_small_ratio, open_time
- playtype_dict
  - 字段：playtype_id, playtype_name
- red_val_list / red_val_list_v2
  - 字段：用于号码值统计存档（本页非必需；保留为后续扩展的可选依赖）

附录 B：关键 SQL（示例）
- 榜单（快表优先）
```sql
SELECT s.user_id,
       i.nick_name,
       s.playtype_name,                  -- 若演进为 playtype_id，则关联字典取名
       s.total_count,
       s.hit_count,
       s.hit_number_count,
       s.avg_hit_gap,
       ROUND(s.hit_count / NULLIF(s.total_count,0), 4) AS hit_rate
FROM lotto_3d.expert_hit_stat s
LEFT JOIN lotto_3d.expert_info i ON i.user_id = s.user_id
WHERE s.issue_name BETWEEN :start_issue AND :end_issue
  /* AND (:playtype_name IS NULL OR s.playtype_name = :playtype_name) */
ORDER BY hit_rate DESC, s.hit_count DESC, s.avg_hit_gap ASC
LIMIT :limit OFFSET :offset;
```

- 下钻（逐期）
```sql
SELECT p.issue_name, p.numbers, r.open_code, r.open_time
FROM lotto_3d.expert_predictions p
JOIN lotto_3d.lottery_results r ON r.issue_name = p.issue_name
WHERE p.user_id = :user_id
  AND p.playtype_id = :playtype_id
  AND p.issue_name BETWEEN :start_issue AND :end_issue
ORDER BY p.issue_name DESC;
```

- 玩法下拉
```sql
SELECT playtype_id, playtype_name
FROM lotto_3d.playtype_dict

ORDER BY playtype_id;
```


