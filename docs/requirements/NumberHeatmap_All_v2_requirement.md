# NumberHeatmap_All_v2（单期版）- 功能需求文档

## 1. 页面背景
对单期专家推荐数据进行“数字频次 × 命中状态”的热力图展示，并提供排行榜命中位次检测。
固定彩种：福彩3D；权限：只读；数据来源：lotto_3d 单库；免登录

## 2. 功能需求
模块A：期号与玩法选择
- 功能描述
  - 选择单期 issue_name 和一个或多个玩法进行展示。
- 输入与输出
  - 输入：issue_name（单选）、playtype（单/多选）
  - 输出：用于后续查询与统计的参数
- 系统依赖（数据库表/字段）
  - lotto_3d.expert_predictions(issue_name, playtype_id, user_id, numbers)
  - lotto_3d.playtype_dict(playtype_id, playtype_name)
  - lotto_3d.lottery_results(issue_name, open_code, open_time)
- 新数据库映射
  - 玩法名称以 playtype_dict 为准

模块B：数字热力图（单期）
- 功能描述
  - 对所选玩法的推荐记录，拆分 numbers 中的各个数字，统计每个数字的“推荐次数”；结合当期 open_code 判定“命中/未命中”，绘制条形热力图（色彩区分命中状态）。
  - 若玩法为定位类（含“百位/十位/个位”等），按对应位置与开奖对比判定命中；否则以“任意位包含该数字”为命中口径。
- 输入与输出
  - 输入：issue_name、playtype
  - 输出：字段=数字、推荐次数、命中状态 的数据集与可视化图表
- 系统依赖
  - expert_predictions(issue_name, playtype_id, numbers)
  - lottery_results(issue_name, open_code)

模块C：排行榜命中检测（Top10）
- 功能描述
  - 基于当前期的数字频次表，取前10位，统计各“排行榜位置”的命中次数（按定位或非定位命中口径）。
- 输入与输出
  - 输入：issue_name、playtype
  - 输出：排行榜位置（1-10）对应的命中次数分布图
- 系统依赖
  - 同模块B

模块D：交互与展示
- 功能描述
  - 控件：玩法多选；按钮触发“排行榜命中检测”
  - 展示：热力图（数字×命中）、排行榜位置命中条形图

## 3. 非功能性需求
- 技术栈：Python 3.12 + Streamlit 最新版本
- 使用 Streamlit 的 session_state、组件扩展、st.cache_data 等优化交互与性能
- 性能
  - 建议索引：expert_predictions(issue_name, playtype_id), lottery_results(issue_name)
  - 仅选择必要字段；在应用层解析 numbers
- 技术
  - 基于 Streamlit 最新版本，使用 session_state、组件扩展、st.cache_data 等优化交互与性能
- 安全
  - 只读访问：对上述表执行 SELECT
- 可扩展性
  - 新玩法通过 playtype_id 即可接入；定位与非定位命中规则可在规则层扩展

## 4. 风险与限制
- numbers 格式须为“逗号分隔的数字”；需做健壮解析
- 定位玩法需确保与开奖位序一致（百/十/个）

## 5. 系统依赖与新数据库映射清单
- 玩法：playtype_dict(playtype_id, playtype_name)
- 预测：expert_predictions(issue_name, playtype_id, user_id, numbers)
- 开奖：lottery_results(issue_name, open_code, open_time)

## 6. 示例查询（可直接用于开发）
- 最新期号
SELECT issue_name FROM lotto_3d.lottery_results ORDER BY open_time DESC, issue_name DESC LIMIT 1;
- 本期可用玩法
SELECT DISTINCT playtype_id FROM lotto_3d.expert_predictions WHERE issue_name = :issue_name ORDER BY playtype_id;
- 玩法名称
SELECT playtype_id, playtype_name FROM lotto_3d.playtype_dict WHERE playtype_id IN (:playtype_ids) ORDER BY playtype_id;
- 单期推荐明细（按玩法）
SELECT user_id, numbers FROM lotto_3d.expert_predictions WHERE issue_name = :issue_name AND playtype_id = :playtype_id;
- 开奖数据
SELECT issue_name, open_code, open_time FROM lotto_3d.lottery_results WHERE issue_name = :issue_name;

## 7. 示例SQL校验结果（实时，lotto_3d）
- 最新期号：2025249
- 本期可用玩法（样例）：[1001, 1002, 1003, 1005, 1006, 1007, 2001, 2002, 3013, 3014, 3015, 3016, 3017, 3018, 30031, 30032, 30033, 30041, 30042, 30043, 30051, 30052, 30053]
- 样例推荐（issue=2025249，取前5行）：
  - (user_id=555, playtype_id=1001, numbers='0')
  - (user_id=555, playtype_id=1002, numbers='0,6')
  - (user_id=555, playtype_id=1003, numbers='0,2,6')
  - (user_id=555, playtype_id=1005, numbers='0,2,4,6,8')
  - (user_id=555, playtype_id=1006, numbers='0,1,2,4,6,8')