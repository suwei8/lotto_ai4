# 系统总体需求说明书（SRS）— lotto_ai3_v2（福彩3D/lotto_3d）

## 1. 项目背景
本项目是一个“专家预测数据采集与统计分析”的实战型平台。为解决旧版单库臃肿、查询缓慢的问题，lotto_ai3_v2 重构遵循“多彩种 + 多库 + 多站点”原则，本说明书聚焦福彩3D（数据库：lotto_3d，站点固定为福彩3D），规范各页面功能、数据依赖、非功能要求和风险，作为新系统开发的统一蓝本。

约束与原则：
- 固定彩种：福彩3D；免登录；只读权限；仅访问 lotto_3d
- 禁用废弃对象：不使用旧表（如 dansha_result 等）与废弃字段（如 lottery_name、expert_predictions.playtype_name、expert_predictions.lottery_name）
- 聚合优先读快表：优先使用 expert_hit_stat 提供的聚合指标，避免在大表 expert_predictions 上即席聚合
- 统一技术栈：Python 3.12 + Streamlit 最新版，利用 session_state、组件扩展、st.cache_data 提升交互与性能

---

## 2. 系统功能概览（按模块归类）

### 2.1 专家表现分析
- ExpertHitTop（专家命中排行）
  - 作用：在指定期段/玩法下，按专家展示命中率、命中次数、总推荐次数、平均命中间隔，支持排序与分页；支持明细下钻
  - 主要输入：期号范围（近 N 期或自定义）、玩法集合、排序项、分页参数
  - 输出：排行榜表格、可选玩法热力图；明细下钻（逐期推荐 vs 开奖）
  - 依赖：expert_hit_stat（聚合）、expert_info（昵称）、expert_predictions（明细）、lottery_results（开奖）、playtype_dict（玩法名）

- UserExpertHitStat（专家命中统计）
  - 作用：按期段/玩法维度汇总专家命中表现，按命中指标筛选后可反查指定期号的推荐记录
  - 依赖：expert_hit_stat、expert_predictions、expert_info、lottery_results、playtype_dict

- UserHitAnalysis（专家个人多期分析）
  - 作用：针对指定专家，在所选期段/玩法维度统计其命中趋势与画像（命中期数、命中数量、平均间隔）
  - 依赖：expert_predictions、lottery_results、playtype_dict

- Userid_Query（按期号+专家查询）
  - 作用：按“期号 + user_id”查看该专家在该期所有玩法的推荐、对应开奖与结果表格
  - 依赖：expert_predictions、lottery_results、playtype_dict、expert_info

### 2.2 推荐数据探查与可视化
- UserExpertFilterPlus（数字特征+命中特征过滤）
  - 作用：对本期推荐进行“推荐数字过滤 + 往期命中特征过滤”，产出专家集合及其推荐明细、数字热力图和命中详情
  - 依赖：expert_predictions、lottery_results、playtype_dict、expert_info

- NumberAnalysis（号码组合分析与筛选）
  - 作用：对指定期号/玩法的专家推荐进行组合统计、配对/全排列转换与投注展示
  - 依赖：expert_predictions、lottery_results、playtype_dict

- NumberHeatmap_All_v2（单期热力图）
  - 作用：单期维度展示“数字频次 × 命中状态”热力图，并提供排行榜命中位次检测
  - 依赖：expert_predictions、lottery_results、playtype_dict

- NumberHeatmap_Simplified_v2_all（多期简化热力图）
  - 作用：多期维度展示“按期 × 数字频次 × 命中状态”的热力图（如每4期一行）
  - 依赖：expert_predictions、lottery_results、playtype_dict

- Playtype_CombinationView（多玩法对比视图）
  - 作用：在同一视图对多个玩法的推荐数据进行对比与组合分析，观察分布与命中表现
  - 依赖：expert_predictions、playtype_dict、lottery_results

### 2.3 开奖走势与选号分布
- HotCold（冷热分析）
  - 作用：对近 N 期或指定区间开奖做总体与分位（百/十/个）频次统计，输出热/冷榜与趋势
  - 依赖：lottery_results

- RedValList（选号分布 v1）
  - 作用：指定期次下，按玩法展示专家推荐的“号码集合”分布，可导入“排行榜位置数字统计器”做位次分析
  - 依赖：red_val_list、playtype_dict、lottery_results
  - 注意：若 red_val_list.id 非唯一，请增加二排序字段（如 playtype_id, issue_name）确保稳定性

- RedValList_v2（选号分布 v2）
  - 作用：在期号/玩法维度下展示号码集合分布与连红/连黑等统计（v2 提供 *_map 与 rank_count 字段）
  - 依赖：red_val_list_v2、playtype_dict、lottery_results
  - 注意：若 id 非唯一，同上增加二排序字段保证稳定排序

### 2.4 辅助工具与组合分析
- FilterTool_MissV2（组合缺失工具）
  - 作用：针对组合/位次的“缺失/未命中”视角做探查与筛选，支持回溯期范围
  - 依赖：expert_predictions、playtype_dict、lottery_results、（可选）expert_info

- HitComboFrequencyAnalysis（命中组合×出现次数分析）
  - 作用：统计多期内“命中组合 × 出现次数”，并输出未命中出现次数分布（TopN）
  - 依赖：expert_predictions、lottery_results、playtype_dict

- FusionRecommendation（融合推荐）
  - 作用：在多策略/多玩法之间融合推荐结果（如去重、合并、权重），辅助决策
  - 依赖：expert_predictions、lottery_results、playtype_dict

- Xuanhao_3D_P3（选号器·3D/P3）
  - 作用：为 3D（与 P3 口径相近）提供选号交互与规则适配（本份 SRS 仅落地到 3D）
  - 依赖：playtype_dict（规则）、lottery_results（校验）

---

## 3. 数据库依赖（统一说明，基于 lotto_3d 实测）
- expert_hit_stat
  - 字段：id, issue_name, user_id, playtype_name, total_count, hit_count, hit_number_count, avg_hit_gap
  - 用途：专家命中指标快表（聚合源）
  - 索引建议：现状有 PRIMARY(id, issue_name)/idx_issue_name(issue_name)；短期沿用 playtype_name 时建议增 (issue_name, playtype_name, user_id)；演进后改为 (issue_name, playtype_id, user_id)

- expert_info
  - 字段：user_id, nick_name
  - 用途：专家信息与昵称映射

- expert_predictions
  - 字段：id, user_id, issue_name, playtype_id, numbers
  - 用途：专家预测明细，明细对照与可视化、回溯分析
  - 索引建议：增 (issue_name, playtype_id, user_id)；避免以明细做大范围聚合

- lottery_results
  - 字段：id, issue_name, open_code, sum, span, odd_even_ratio, big_small_ratio, open_time
  - 用途：开奖号码、时间序列、校验与统计
  - 索引建议：增 (open_time, issue_name) 或 (issue_name)

- playtype_dict
  - 字段：playtype_id, playtype_name
  - 用途：玩法字典与命名标准化；建议以 playtype_id 为主键引用

- red_val_list / red_val_list_v2
  - 字段：v1: id, user_id, playtype_id, issue_name, num, val；v2: 在 v1 基础上含 type, rank_count, 各 *_map 等
  - 用途：号码集合分布、位置统计、连红/连黑等分析
  - 排序注意：若 id 非唯一，请增加二排序字段（如 playtype_id, issue_name）

字段/表使用限制：
- 不允许使用废弃字段：lottery_name、expert_predictions.playtype_name、expert_predictions.lottery_name
- 不使用被移除的旧表（如 dansha_result、source_tags、expert_performance_by_source、sim_bets、script_recommend_results）

---

## 4. 非功能性需求（全局统一）
- 性能优化（统一标准）
  - 聚合指标优先读取 expert_hit_stat，避免对 expert_predictions 做大范围联表
  - 复合索引建议：
    - expert_hit_stat: (issue_name, user_id, playtype_name) 或演进为 (issue_name, playtype_id, user_id)
    - expert_predictions: (issue_name, playtype_id, user_id)
    - lottery_results: (open_time, issue_name) 或 (issue_name)
  - 分页/TopN：所有页面默认限制行数（如 Top 100 或 LIMIT 分页），图表按 TopN 或自适应，避免大数据渲染阻塞

- 安全
  - 数据隔离：仅连接与查询 lotto_3d，不允许跨库
  - 最小授权：数据库账号仅授予 SELECT
  - 输入校验：参数化查询与白名单字段排序，防注入

- 可扩展性
  - 多库/多站：通过配置化接入其它彩种分库（lotto_p3/p5/ssq/klb/dlt）
  - 字典治理：玩法名统一以 playtype_dict 维护，优先以 playtype_id 做关联
  - 预聚合演进：expert_hit_stat 可平滑扩展字段（如最大连中、稳定性评分等）；前端以动态列适配

- 技术栈与工程
  - Python 3.11 + Streamlit 最新版
  - Streamlit session_state 管理交互状态；组件扩展（自定义组件）丰富交互；st.cache_data 对数据查询与统计结果缓存
  - 代码规范：参数化 SQL；日志最小化（不落敏感数据）；错误边界明确

---

## 5. 风险与限制
- 字段演进风险
  - expert_hit_stat 现存 playtype_name 字段存在字典漂移隐患；建议演进为 playtype_id 并关联 playtype_dict 取名
- 索引变更影响
  - 新增复合索引会带来写入与存储开销，但对读性能提升显著；需 DBA 结合 QPS/磁盘评估
- 历史数据质量
  - 开奖 open_code 格式不一致（空格/分隔符等）可能影响解析；需在应用层健壮处理或统一清洗
- 排序稳定性
  - red_val_list 与 v2 若 id 非唯一，必须增加二排序字段（如 playtype_id, issue_name）

---

## 6. 附录：代表性参数化 SQL 模板

- 最新期号（开奖表为基准）
```sql
SELECT issue_name
FROM lotto_3d.lottery_results
ORDER BY open_time DESC, issue_name DESC
LIMIT 1;
```

- 近 N 期（开奖数据）
```sql
SELECT issue_name, open_code, open_time
FROM lotto_3d.lottery_results
ORDER BY open_time DESC, issue_name DESC
LIMIT :N;
```

- 玩法列表（按字典顺序）
```sql
SELECT playtype_id, playtype_name
FROM lotto_3d.playtype_dict
ORDER BY playtype_id;
```

- 专家命中排行榜（聚合快表）
```sql
SELECT s.user_id,
       i.nick_name,
       s.playtype_name,                         -- 演进后可改为 playtype_id 再关联取名
       s.total_count, s.hit_count,
       s.hit_number_count, s.avg_hit_gap,
       ROUND(s.hit_count / NULLIF(s.total_count,0), 4) AS hit_rate
FROM lotto_3d.expert_hit_stat s
LEFT JOIN lotto_3d.expert_info i ON i.user_id = s.user_id
WHERE s.issue_name BETWEEN :start_issue AND :end_issue
  /* AND (:playtype_name IS NULL OR s.playtype_name = :playtype_name) */
ORDER BY hit_rate DESC, s.hit_count DESC, s.avg_hit_gap ASC
LIMIT :limit OFFSET :offset;
```

- 明细下钻：专家逐期推荐 vs 开奖
```sql
SELECT p.issue_name, p.playtype_id, p.numbers,
       r.open_code, r.open_time
FROM lotto_3d.expert_predictions p
JOIN lotto_3d.lottery_results r
  ON r.issue_name = p.issue_name
WHERE p.user_id = :user_id
  AND p.playtype_id = :playtype_id
  AND p.issue_name BETWEEN :start_issue AND :end_issue
ORDER BY p.issue_name DESC;
```

- 选号分布 v2（按期号+玩法取 TopN）
```sql
SELECT id, user_id, playtype_id, issue_name,
       num, val, type, rank_count
FROM lotto_3d.red_val_list_v2
WHERE issue_name = :issue_name
  AND playtype_id = :playtype_id
ORDER BY id DESC, playtype_id ASC, issue_name DESC
LIMIT :limit OFFSET :offset;
```

- 冷热分析：指定区间开奖
```sql
SELECT issue_name, open_code, open_time
FROM lotto_3d.lottery_results
WHERE issue_name BETWEEN :issue_start AND :issue_end
ORDER BY issue_name DESC;
```

## 7. 版本与里程碑

### 7.1 版本信息
- 系统版本：lotto_ai3_v2
- 技术栈：Python 3.11 + Streamlit 最新版本 + MySQL 8.0
- 数据库范围：lotto_3d（福彩3D 独立库）
- 文档状态：系统总体需求说明书（SRS）v2.0

### 7.2 开发里程碑
- M1（需求确认，2025-Q1）  
  - 完成需求分析与 SRS 定稿  
  - 数据库重构（lotto_3d）上线  

- M2（核心功能开发，2025-Q2）  
  - 专家表现分析模块上线（ExpertHitTop、UserExpertHitStat 等）  
  - 开奖数据处理与冷热分析（HotCold、lottery_results 对接）  

- M3（可视化与工具增强，2025-Q3）  
  - 热力图、选号分布、过滤工具功能上线  
  - 缓存与 session_state 优化  

- M4（测试与发布，2025-Q4）  
  - 集成测试、性能压测  
  - Docker 部署与运维方案交付  
  - 正式发布 lotto_ai3_v2  

### 7.3 未来演进
- 扩展至多彩种分库（lotto_p3, lotto_p5, lotto_ssq, lotto_klb, lotto_dlt）  
- 增加专家稳定性评分、最大连中/连黑指标  
- 引入机器学习模型进行预测推荐增强

以上模板可按页面具体参数裁剪组合，均应以参数化方式执行，并结合缓存与索引以保障性能。

—— 说明书完 ——