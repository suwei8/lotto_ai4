# NumberHeatmap_Simplified_v2_all（多期版）- 功能需求文档

## 1. 页面背景
对多期数据进行“按期 × 数字频次 × 命中状态”的热力图展示，并支持每4期为一行的分栏布局。
固定彩种：福彩3D；权限：只读；数据来源：lotto_3d 单库；免登录

## 2. 功能需求
模块A：期号与玩法选择
- 功能描述
  - 多选期号；选择单一玩法作为统计口径。
- 输入与输出
  - 输入：issue_name 列表（多选）、playtype（单选）
  - 输出：用于后续查询与统计的参数
- 系统依赖（数据库表/字段）
  - lotto_3d.expert_predictions(issue_name, playtype_id, user_id, numbers)
  - lotto_3d.playtype_dict(playtype_id, playtype_name)
  - lotto_3d.lottery_results(issue_name, open_code)

模块B：多期热力图渲染
- 功能描述
  - 对每个所选期号，拆分 numbers 中的数字，统计每个数字的“推荐次数”，并结合当期 open_code 判定命中状态，绘制条形热力图；按每行最多4张卡片分栏展示（期号+开奖号码标题）。
  - 定位玩法按位比对；非定位按任意包含判定命中。
- 输入与输出
  - 输入：issue_name 列表、playtype
  - 输出：每期的字段=数字、推荐次数、命中状态 的数据集及图表
- 系统依赖
  - expert_predictions(issue_name, playtype_id, numbers)
  - lottery_results(issue_name, open_code)

模块C：排行榜命中检测（多期Top10）
- 功能描述
  - 对每期重算数字频次排行榜（Top10），判断是否命中，累计各“排行榜位置”的命中次数，输出柱状图。
- 输入与输出
  - 输入：issue_name 列表、playtype
  - 输出：排行榜位置（1-10）命中次数分布
- 系统依赖
  - 同模块B

模块D：交互与展示
- 功能描述
  - 控件：多选期号；单选玩法；按钮触发“排行榜命中检测”
  - 展示：分期热力图、排行榜位置命中柱状图

## 3. 非功能性需求
- 技术栈：Python 3.12 + Streamlit 最新版本
- 使用 Streamlit 的 session_state、组件扩展、st.cache_data 等优化交互与性能
- 性能
  - 建议索引：expert_predictions(issue_name, playtype_id), lottery_results(issue_name)
  - 通过 IN (:issues) 查询批量获取推荐与开奖号码；在应用层解析 numbers
- 技术
  - 基于 Streamlit 最新版本，使用 session_state、组件扩展、st.cache_data 等优化交互与性能
- 安全
  - 只读访问：对上述表执行 SELECT
- 可扩展性
  - 新玩法通过 playtype_id 接入；定位/非定位命中规则可扩展

## 4. 风险与限制
- numbers 解析需健壮（逗号分隔）
- 定位玩法位序需与开奖一致

## 5. 系统依赖与新数据库映射清单
- 玩法：playtype_dict(playtype_id, playtype_name)
- 预测：expert_predictions(issue_name, playtype_id, user_id, numbers)
- 开奖：lottery_results(issue_name, open_code)

## 6. 示例查询（可直接用于开发）
- 最近N期开奖
SELECT issue_name, open_code, open_time
FROM lotto_3d.lottery_results
ORDER BY open_time DESC, issue_name DESC
LIMIT :N;

- 多期推荐（按玩法）
SELECT issue_name, user_id, numbers
FROM lotto_3d.expert_predictions
WHERE issue_name IN (:issues) AND playtype_id = :playtype_id;

- 玩法名称
SELECT playtype_id, playtype_name
FROM lotto_3d.playtype_dict
WHERE playtype_id IN (:playtype_ids)
ORDER BY playtype_id;

## 7. 示例SQL校验结果（实时，lotto_3d）
- 最近样例开奖（倒序，最多4条）：
  - 2025249 → open_code=9,5,2, open_time=2025-09-15 16:00:00
  - 2025248 → open_code=5,2,6, open_time=2025-09-14 16:00:00
  - 2025247 → open_code=2,6,2, open_time=2025-09-13 16:00:00
  - 2025246 → open_code=9,9,7, open_time=2025-09-12 16:00:00
- 最新期号：2025249
- 本期可用玩法（样例）：[1001, 1002, 1003, 1005, 1006, 1007, 2001, 2002, 3013, 3014, 3015, 3016, 3017, 3018, 30031, 30032, 30033, 30041, 30042, 30043, 30051, 30052, 30053]