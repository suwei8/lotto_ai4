# HitComboFrequencyAnalysis - 功能需求文档（新版本）

## 1. 页面背景
用于对“多期命中组合 × 出现次数”进行分析：在所选期号集合与玩法下，统计专家推荐组合（numbers）的出现次数，并计算各“出现次数”组的命中率，输出命中组合列表与“未命中出现次数分布（Top3）”。
固定彩种：福彩3D；权限：只读；数据来源：lotto_3d 单库；免登录

## 2. 功能需求

模块A：期号与玩法选择
- 功能描述
  - 多选期号；选择单一玩法作为分析口径。
- 输入与输出
  - 输入：
    - 期号集合 selected_issues（多选）
    - 玩法 selected_playtype（单选）
  - 输出：作为后续查询统计的参数。
- 使用场景
  - 批量复盘多个历史期的“推荐组合出现次数”与命中表现。
- 系统依赖（数据库表/字段）
  - lotto_3d.expert_predictions: issue_name, playtype_id, user_id, numbers
  - lotto_3d.playtype_dict: playtype_id, playtype_name
  - 期号选项可从 lottery_results 或 expert_predictions 取 DISTINCT issue_name
- 新数据库映射
  - 玩法名称通过 playtype_dict(playtype_id → playtype_name)


模块B：命中组合统计（跨期）
- 功能描述
  - 对每个被选期号：
    - 取当期指定玩法的专家推荐 numbers，统计组合出现次数（去重策略：默认对完整“numbers”文本去重；如需严格去重，按 user_id + playtype_id + numbers）。
    - 根据命中规则判断组合是否命中，输出命中组合、出现次数与开奖号码。
- 输入与输出
  - 输入：selected_issues, selected_playtype
  - 输出：命中组合清单（期号、命中组合、出现次数、开奖号码）
- 使用场景
  - 找出高频且命中的推荐组合，辅助选号/回测。
- 系统依赖
  - lotto_3d.expert_predictions: issue_name, playtype_id, numbers, user_id
  - lotto_3d.lottery_results: issue_name, open_code, open_time
  - 命中规则引擎：依据 playtype_id、numbers 与 open_code 做判定（应用层）。
- 新数据库映射
  - 使用 open_code 进行判定


模块C：出现次数组 × 命中率分析
- 功能描述
  - 对每期将所有组合按“出现次数”分组，计算每组的“推荐组合数”“命中组合数”“命中率”，并输出各期未命中表现较差的若干组（Top3）。
- 输入与输出
  - 输入：selected_issues, selected_playtype
  - 输出：每期的（出现次数、推荐组合数、命中组合数、命中率）统计；并列出“未命中出现次数分布（Top3）”。
- 使用场景
  - 识别“高频但命中差”的组合出现次数阈值，为策略修正提供依据。
- 系统依赖
  - 同模块B。
- 新数据库映射
  - 依赖 expert_predictions 与 lottery_results 的对照

模块D：交互与展示
- 功能描述
  - 筛选控件：多选期号、单选玩法
  - 按钮：触发批量分析
  - 表格：
    - 命中组合统计（支持按期号/出现次数排序）
    - 未命中出现次数分布（Top3）
- 输出
  - 可视化表格。

模块E：参数与规则口径
- 功能描述
  - “多命中模式”推断：若推荐组合位数 < 开奖位数，则允许同期命中多条组合；否则命中一条即跳出。
- 说明
  - 位数判断通过 numbers 文本与 open_code 的数字位计数完成（应用层实现）。

## 3. 非功能性需求
- 技术栈：Python 3.12 + Streamlit 最新版本
- 使用 Streamlit 的 session_state、组件扩展、st.cache_data 缓存优化交互与性能
- 性能
  - 取数按条件索引：建议在 expert_predictions 建立 (issue_name, playtype_id, user_id) 或 (issue_name, playtype_id) 复合索引；在 lottery_results 建立 (issue_name) 索引。
  - 分期批处理：先确定期号列表，再逐期独立取数与判定，避免跨期大聚合。
  - 去重策略：在取数阶段按业务口径去重（如按 user_id + playtype_id + numbers），减少内存与重复计算。
- 技术
  - 基于 Streamlit 最新版本，使用 session_state、组件扩展、st.cache_data 等优化交互与性能
- 安全
  - 只读访问；最小权限仅授 lotto_3d 的 SELECT。
- 可扩展性
  - 玩法命中判定以 playtype_id 作为入口，新玩法仅需扩展规则映射。
  - 支持未来多彩种扩展：抽象命中规则与数据读取层，可按彩种配置适配

## 4. 风险与限制
- 已知问题


- 数据迁移/一致性风险

  - 命中规则与 numbers 文本格式需一致（如“逗号分隔”）；若历史数据格式不一，需统一清洗或在应用层做兼容解析。
  - 若某期无对应开奖记录（open_code 为空），该期判定需跳过或标记为“不可判定”。

## 5. 系统依赖与新数据库映射清单
- 期号选项：从 lottery_results 或 expert_predictions 取 DISTINCT issue_name（推荐 lottery_results 结合 open_time 排序）
- 玩法字典：playtype_dict(playtype_id, playtype_name)
- 预测数据：expert_predictions(issue_name, playtype_id, user_id, numbers)
- 开奖数据：lottery_results(issue_name, open_code, open_time)

## 附录A：SQL 示例
- 最新期号
```sql
SELECT issue_name
FROM lotto_3d.lottery_results
ORDER BY open_time DESC, issue_name DESC
LIMIT 1;
```
- 本期可用玩法
```sql
SELECT DISTINCT playtype_id
FROM lotto_3d.expert_predictions
WHERE issue_name = :issue_name
ORDER BY playtype_id;
```
- 玩法名称
```sql
SELECT playtype_id, playtype_name
FROM lotto_3d.playtype_dict
WHERE playtype_id IN (:playtype_ids)
ORDER BY playtype_id;
```
- 多期预测明细（指定玩法）
```sql
SELECT user_id, issue_name, numbers
FROM lotto_3d.expert_predictions
WHERE issue_name IN (:issue_list)
  AND playtype_id = :playtype_id;
```
- 开奖数据
```sql
SELECT issue_name, open_code, open_time
FROM lotto_3d.lottery_results
WHERE issue_name IN (:issue_list);
```

## 附录B：校验样例（可选，lotto_3d）
- 最新期号：2025249
- 本期可用玩法：[1001, 1002, 1003, 1005, 1006, 1007, 2001, 2002, 3013, 3014, 3015, 3016, 3017, 3018, 30031, 30032, 30033, 30041, 30042, 30043, 30051, 30052, 30053]
- 样例行（issue=2025249, playtype_id in 1001/1002/1003）
  - (user_id=555, 1001, '0')
  - (user_id=555, 1002, '0,6')
  - (user_id=555, 1003, '0,2,6')
  - (user_id=1010, 1001, '2')
  - (user_id=1010, 1002, '2,8')

## 附录C：玩法命中判定口径（按 playtype_id，福彩3D）
- 1001 独胆：numbers 为单个数字；命中=开奖号码任一位等于该数字
- 1002 双胆：'d1,d2'；命中=开奖号码中出现 d1 或 d2（如需“同时出现两胆”，可作为参数收紧）
- 1003 三胆：'d1,d2,d3'；命中=开奖号码中包含任一/两/三胆（默认任一，可参数化）
- 1005/1006/1007（5/6/7码组选）：命中=开奖号码三位均属于候选集合（允许重复）
- 2001/2002（杀一/杀二）：命中=开奖号码中不包含被“杀”的数字（杀二需两者均不出现）
- 3013/3014/3015（百/十/个 定3）：该位开奖号码 ∈ 长度为3的集合
- 3016/3017/3018（百/十/个 定1）：该位开奖号码等于指定数字
- 30031/30032/30033（百/十/个 3×3×3）：该位开奖号码 ∈ 长度=3集合
- 30041/30042/30043（4×4×4）、30051/30052/30053（5×5×5）：同上，集合长度=4/5
- 备注：未列出的玩法在 playtype_dict 出现时标记“需配置命中规则”，在命中引擎中扩展。