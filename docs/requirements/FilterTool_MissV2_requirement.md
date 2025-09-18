# FilterTool_MissV2 - 功能需求文档（新版本）

## 1. 页面背景
面向福彩3D提供“AI智体筛选 + 推荐频次统计”的辅助工具，支持按期号、玩法与回溯窗口，对专家预测进行筛选与统计，输出推荐数字的频次排名，并列出参与统计的专家与其推荐项。

技术栈：基于 Streamlit 最新版本开发（layout=wide）。
固定彩种：福彩3D；权限：只读；数据来源：lotto_3d 单库；免登录

## 2. 功能需求

模块A：期号与玩法选择
- 功能描述
  - 选择当前统计期号与本期参与统计的玩法集合，多选支持。
- 输入与输出
  - 输入：
    - 当前期号 issue_name（单选）
    - 当前期统计玩法（多选）
  - 输出：
    - 作为统计入口参数传递给后续查询与统计逻辑
- 使用场景
  - 用户选择某一期开奖前后，对该期专家推荐数据进行频次统计。
- 系统依赖（新库表/字段）
  - lotto_3d.expert_predictions
    - 字段：issue_name, playtype_id, user_id, numbers
    - 用途：获取当前期可选玩法（distinct playtype_id）与对应的预测数据
  - lotto_3d.playtype_dict
    - 字段：playtype_id, playtype_name
    - 用途：玩法名展示（playtype_id → playtype_name）
- 新数据库映射
  - 玩法取自 expert_predictions.playtype_id，名称通过关联 playtype_dict 获取


模块B：回溯窗口与筛选阈值
- 功能描述
  - 设定回溯统计的截止期、回溯期数（Lookback N），并可选启用“未命中次数区间”作为过滤阈值；支持启用/停用筛选、去重同专家同玩法记录。
- 输入与输出
  - 输入：
    - 回溯截止期 ref_issue（基于期号序）
    - 回溯期数 lookback_n（1..最大可回溯）
    - 启用“未命中次数”区间：miss_threshold_low, miss_threshold_high
    - 是否去重 remove_duplicates（按 user_id + playtype_id + numbers）
    - 回溯玩法集合（用于统计筛选）
    - 是否启用筛选 enable_filter
  - 输出：
    - 生成回溯期号列表 issue_list（按时间/期序降序取近 N 期）
- 使用场景
  - 控制统计窗口、筛出高命中/连续不中等特征专家。
- 系统依赖（新库表/字段）
  - lotto_3d.lottery_results
    - 字段：issue_name, open_time
    - 用途：依据 open_time/issue_name 推导近 N 期 issue_list；用于命中比对时读取开奖号码 open_code
  - lotto_3d.expert_predictions
    - 字段：issue_name, playtype_id, user_id, numbers
- 新数据库映射

  - 去重依据：user_id + playtype_id + numbers。

模块C：筛选模式（命中/未命中规则）
- 功能描述
  - 提供若干筛选模式，根据回溯窗口内的逐期命中结果统计未命中次数，从而筛出专家：
    - 未命中次数 ≤ X（高命中）
    - L ≤ 未命中次数 ≤ H（中命中）
    - 连续必中（未命中=0）
    - 连续未命中（回溯期内无一次命中）
- 输入与输出
  - 输入：issue_list、回溯玩法集合、阈值设置
  - 输出：通过筛选的专家 user_id 列表（kept_users）
- 使用场景
  - 快速定位稳定/高命中/连挂类专家，供本期频次统计。
- 系统依赖（新库表/字段）
  - lotto_3d.expert_predictions：issue_name, playtype_id, user_id, numbers
  - lotto_3d.lottery_results：issue_name, open_code
  - 命中规则：针对福彩3D的玩法规则，使用应用层命中判定（playtype_id + numbers vs open_code），命中与否返回布尔值
- 新数据库映射
  - 筛选仅基于命中结果与阈值

模块D：推荐数字频次统计
- 功能描述
  - 对通过筛选的专家在“当前期 + 当前选中玩法”的推荐 numbers 按数字进行频次统计，支持“重复统计模式”（repeat_mode：按权重叠加；新版本默认权重=1）。
- 输入与输出
  - 输入：
    - 当前期 issue_name
    - 当前期统计玩法 selected_playtypes（按 playtype_id）
    - 通过筛选的专家 user_id 列表（若未启用筛选则取全部）
    - remove_duplicates：是否去重同专家同玩法同 numbers
  - 输出：
    - 统计表：数字（0-9）与推荐次数，按次数降序展示
- 使用场景
  - 汇总各专家在本期的数字推荐强度，辅助选号。
- 系统依赖（新库表/字段）
  - lotto_3d.expert_predictions：user_id, issue_name, playtype_id, numbers
- 新数据库映射
  - repeat_mode 下每条记录权重=1

模块E：参与统计专家列表
- 功能描述
  - 展示参与当前统计的专家清单（数量与昵称），并给出其推荐项汇总（以“numbers”拼接表示）。
- 输入与输出
  - 输入：参与统计的 user_id 列表与其本期预测
  - 输出：表格（用户ID、专家昵称、推荐项汇总）
- 使用场景
  - 便于人工核验与后续人工二次判断。
- 系统依赖（新库表/字段）
  - lotto_3d.expert_predictions：user_id, numbers
  - lotto_3d.expert_info：user_id, nick_name

## 3. 非功能性需求
- 技术栈：Python 3.11 + Streamlit 最新版本
- 使用 Streamlit 的 session_state、组件扩展、st.cache_data 缓存优化交互与性能
- 性能
  - 基于期号与玩法的索引化读取，避免全表扫描：
    - expert_predictions 建议索引：
      - 复合索引 (issue_name, playtype_id, user_id)
      - 复合索引 (issue_name, playtype_id)（用于获取本期玩法、查询过滤）
      - 已有 idx_user_id 可保留
    - lottery_results 建议索引：
      - 普通或唯一索引 (issue_name)（快速回溯与结果映射）
  - 避免跨期联表大聚合：先取 issue_list，再分批查询 predictions 与 results，并在应用层计算命中。
  - 去重操作在应用层执行，尽量在取数时按 (user_id, playtype_id, numbers) 去重。
- 安全
  - 只读查询；不涉及任何写操作。

- 可扩展性
  - 支持未来多彩种扩展：通过配置化切换目标彩种，对应玩法字典独立维护。
  - 命中规则抽象：以 playtype_id 作为规则入口，新增玩法仅需扩展命中规则映射。

## 4. 风险与限制
- 已知问题
  - 期号排序口径需统一：如 issue_name 非严格字典序，需要结合 open_time 或独立的期序映射。
  - 若数据源不全（numbers/open_code 为空），命中判定将跳过该条记录。
- 数据迁移风险



## 5. 页面-数据库字段清单与用途映射
- 当前期玩法选择
  - expert_predictions(issue_name, playtype_id) → distinct → playtype_dict(playtype_id → playtype_name)
- 回溯窗口
  - lottery_results(issue_name, open_time) → 近 N 期 issue_list；lottery_results(issue_name, open_code) → 命中比对
- 筛选（命中/未命中）
  - expert_predictions(user_id, issue_name, playtype_id, numbers) + lottery_results(issue_name, open_code) → 命中布尔序列 → 未命中次数
- 推荐频次统计
  - expert_predictions(user_id, playtype_id, numbers)（限定当前期与所选玩法）→ 数字拆分与计数
- 参与统计专家列表
  - expert_predictions(user_id, numbers) + expert_info(user_id, nick_name)

## 附录A：SQL 示例
- 获取本期可选玩法
```sql
SELECT DISTINCT p.playtype_id, d.playtype_name
FROM lotto_3d.expert_predictions p
LEFT JOIN lotto_3d.playtype_dict d
  ON d.playtype_id = p.playtype_id
WHERE p.issue_name = :issue_name
ORDER BY d.playtype_id;
```
- 获取回溯期列表（按开奖时间倒序取近 N 期）
```sql
SELECT issue_name
FROM lotto_3d.lottery_results
ORDER BY open_time DESC, issue_name DESC
LIMIT :N;
```
- 回溯期内的预测（用于命中统计）
```sql
SELECT user_id, issue_name, playtype_id, numbers
FROM lotto_3d.expert_predictions
WHERE issue_name IN (:issue_list) AND playtype_id IN (:playtype_ids);
```
- 当前期预测（用于频次统计）
```sql
SELECT user_id, playtype_id, numbers
FROM lotto_3d.expert_predictions
WHERE issue_name = :issue_name AND playtype_id IN (:playtype_ids);
```
- 专家昵称
```sql
SELECT user_id, nick_name
FROM lotto_3d.expert_info
WHERE user_id IN (:user_ids);
```

## 附录B：校验样例（可选）
- 最新期号（lotto_3d.lottery_results）：2025249
- 本期可用玩法（lotto_3d.expert_predictions.distinct playtype_id）：[1001, 1002, 1003, 1005, 1006, 1007, 2001, 2002, 3013, 3014, 3015, 3016, 3017, 3018, 30031, 30032, 30033, 30041, 30042, 30043, 30051, 30052, 30053]
- 校验计数
  - SELECT COUNT(*) FROM expert_predictions WHERE issue_name='2025249' AND playtype_id IN (1001,1002,1003) → 4500
- 样例行（issue=2025249, playtype_id in 1001/1002/1003）
  - (user_id=555, playtype_id=1001, numbers='0')
  - (user_id=555, playtype_id=1002, numbers='0,6')
  - (user_id=555, playtype_id=1003, numbers='0,2,6')
  - (user_id=1010, playtype_id=1001, numbers='2') 等
- 版本兼容注意
  - 某些 MySQL 版本对 “LIMIT 与 IN 子查询”不兼容（报错：This version of MySQL doesn't yet support 'LIMIT & IN/ALL/ANY/SOME subquery'）
  - 替代写法（两步/派生表 JOIN）：
```sql
-- Step1: 先取 user_id 列表（限制数量）
SELECT DISTINCT user_id
INTO TEMPORARY TABLE tmp_users
FROM lotto_3d.expert_predictions
WHERE issue_name = :issue_name AND playtype_id IN (:playtype_ids)
LIMIT :M;

-- Step2: 再用 JOIN 获取昵称（避免在 IN 中出现 LIMIT）
SELECT i.user_id, i.nick_name
FROM lotto_3d.expert_info i
JOIN tmp_users u ON u.user_id = i.user_id
LIMIT :M;

-- 或者无需临时表的派生表 JOIN
SELECT i.user_id, i.nick_name
FROM lotto_3d.expert_info i
JOIN (
  SELECT DISTINCT user_id
  FROM lotto_3d.expert_predictions
  WHERE issue_name = :issue_name AND playtype_id IN (:playtype_ids)
  LIMIT :M
) u ON u.user_id = i.user_id
LIMIT :M;
```

## 附录C：玩法命中判定口径（按 playtype_id，福彩3D）
说明：命中判定在应用层实现，基于开奖 open_code（三位数字，允许重复）与预测 numbers（逗号分隔的数字集合或定位集合）。以下为可执行口径，未覆盖的玩法标记为“需配置命中规则”。

- 1001 独胆
  - 预测：numbers 形如 'd'，d ∈ [0..9]
  - 命中：open_code 三位中任意一位等于 d
- 1002 双胆
  - 预测：'d1,d2'
  - 命中：open_code 中至少包含 {d1,d2} 中任意一个数字（若业务要求“同时出现两胆”可切换为必须同时出现）
- 1003 三胆
  - 预测：'d1,d2,d3'
  - 命中：open_code 中至少包含三胆中的任意一个（或按需切换为“至少包含两个/全部”）
- 1005/1006/1007 五/六/七码组选
  - 预测：一组候选数字集合（长度为5/6/7）
  - 命中：open_code 三位数字均属于该集合（允许重复，如 0,0,1 也属命中，只要 0 和 1 在集合中）
- 2001/2002 杀一/杀二
  - 预测：'d1' 或 'd1,d2'
  - 命中：open_code 中不包含任一被“杀”的数字（杀二则二者皆不能出现）
- 3013/3014/3015 定位定3（百/十/个）
  - 预测：对应位置允许的数字集合，长度为3
  - 命中：该位置开奖号码 ∈ 集合
- 3016/3017/3018 定位定1（百/十/个）
  - 预测：对应位置的单一数字
  - 命中：该位置开奖号码等于该数字
- 30031/30032/30033 定位3×3×3（百/十/个）
  - 预测：对应位置集合长度=3
  - 命中：该位置开奖号码 ∈ 集合
- 30041/30042/30043 定位4×4×4（百/十/个）
  - 同上，集合长度=4
- 30051/30052/30053 定位5×5×5（百/十/个）
  - 同上，集合长度=5

备注：
- 上述“胆类命中口径”（至少包含一个）与“是否区分组三/组六”可作为页面参数或系统配置，默认采用“至少包含一个”的宽松口径，满足筛选与频次统计的主需求。
- 未列出的 playtype_id 或特殊玩法，请在 playtype_dict 中出现时标记为“需配置命中规则”，并在命中引擎中扩展。