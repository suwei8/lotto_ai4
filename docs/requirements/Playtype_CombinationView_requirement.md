# Playtype_CombinationView - 功能需求文档

## 1. 页面背景
在同一视图中对多个玩法的推荐数据进行对比展示与组合分析，便于观察不同玩法的数字分布、命中表现与互补关系。
固定彩种：福彩3D；权限：只读；数据来源：lotto_3d 单库；免登录
固定彩种：福彩3D；权限：只读；数据来源：lotto_3d 单库；免登录

## 2. 功能需求
模块A：期号与玩法选择
- 功能描述
  - 选择单期 issue_name；多选若干玩法进行并行对比。
- 输入与输出
  - 输入：issue_name（单选）、playtype_id 列表（多选）
  - 输出：用于查询与统计的参数
- 系统依赖（数据库表/字段）
  - lotto_3d.expert_predictions(issue_name, playtype_id, user_id, numbers)
  - lotto_3d.playtype_dict(playtype_id, playtype_name)
  - lotto_3d.lottery_results(issue_name, open_code, open_time)

模块B：玩法对比视图（数字频次 × 命中）
- 功能描述
  - 对每个选中玩法：
    - 拆分 numbers 为单个数字，统计“推荐次数”
    - 结合当期 open_code 判定“命中/未命中”
    - 以条形热力图展示（颜色区分命中状态）
  - 支持定位与非定位两种命中口径：
    - 定位类（含“百位/十位/个位”等）：对应位置与开奖号码比对
    - 非定位类：任意位包含该数字视为命中
- 输入与输出
  - 输入：issue_name，playtype_id
  - 输出：字段=数字、推荐次数、命中状态 的数据集与图表
- 系统依赖
  - expert_predictions(issue_name, playtype_id, numbers)
  - lottery_results(issue_name, open_code)

模块C：交叉组合观察（玩法间互补）
- 功能描述
  - 在玩法间对比：展示各玩法的“高频数字”集合与交集/并集（例如：各玩法TopK高频数字的交集/并集）
  - 可选择TopK（默认5），输出交集、并集列表与计数
- 输入与输出
  - 输入：playtype_id 列表、TopK
  - 输出：高频数字交集/并集及其规模
- 系统依赖
  - 使用模块B生成的频次表在应用层计算

模块D：排行榜命中位次（Top10）
- 功能描述
  - 对每个玩法分别计算数字频次排行榜前10，判断是否命中并输出柱状图（位置→命中次数）
- 输入与输出
  - 输入：playtype_id 列表
  - 输出：位置（1-10）命中次数分布
- 系统依赖
  - expert_predictions(issue_name, playtype_id, numbers)
  - lottery_results(issue_name, open_code)

模块E：开奖信息展示
- 功能描述
  - 同屏展示 issue_name, open_code, open_time
- 系统依赖
  - lottery_results(issue_name, open_code, open_time)

## 3. 非功能性需求
- 技术栈：Python 3.12 + Streamlit 最新版本
- 使用 Streamlit 的 session_state、组件扩展、st.cache_data 等优化交互与性能
- 性能
  - 索引建议：expert_predictions(issue_name, playtype_id), lottery_results(issue_name)
  - 单期取数，解析 numbers 于应用层完成
- 技术
  - 基于 Streamlit 最新版本，使用 session_state、组件扩展、st.cache_data 等优化交互与性能
- 安全
  - 只读访问：对上述表执行 SELECT
- 可扩展性
  - 新玩法通过 playtype_id 即可接入；定位/非定位命中规则可在规则层扩展

## 4. 风险与限制
- numbers 解析需健壮（逗号分隔）
- 定位玩法位序需与开奖一致

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
- 单期多玩法推荐明细
SELECT user_id, playtype_id, numbers FROM lotto_3d.expert_predictions WHERE issue_name = :issue_name AND playtype_id IN (:playtype_ids);
- 开奖数据
SELECT issue_name, open_code, open_time FROM lotto_3d.lottery_results WHERE issue_name = :issue_name;

## 7. 示例SQL校验结果（实时，lotto_3d）
- 最新期号：2025249
- 本期可用玩法（样例）：[1001, 1002, 1003, 1005, 1006, 1007, 2001, 2002, 3013, 3014, 3015, 3016, 3017, 3018, 30031, 30032, 30033, 30041, 30042, 30043, 30051, 30052, 30053]
- 玩法名称映射（样例）：
  - 1001=独胆，1002=双胆，1003=三胆
  - 1005=五码组选，1006=六码组选，1007=七码组选
  - 2001=杀一，2002=杀二
  - 3013=百位定3，3014=十位定3，3015=个位定3
  - 3016=百位定1，3017=十位定1，3018=个位定1
  - 30031=定位3*3*3-百位，30032=定位3*3*3-十位，30033=定位3*3*3-个位
  - 30041=定位4*4*4-百位，30042=定位4*4*4-十位，30043=定位4*4*4-个位
  - 30051=定位5*5*5-百位，30052=定位5*5*5-十位，30053=定位5*5*5-个位
- 样例推荐（issue=2025249，取前5行）：
  - (user_id=555, playtype_id=1001, numbers='0')
  - (user_id=555, playtype_id=1002, numbers='0,6')
  - (user_id=555, playtype_id=1003, numbers='0,2,6')
  - (user_id=555, playtype_id=1005, numbers='0,2,4,6,8')
  - (user_id=555, playtype_id=1006, numbers='0,1,2,4,6,8')
- 最近样例开奖（倒序，最多4条）：
  - 2025249 → open_code=9,5,2, open_time=2025-09-15 16:00:00
  - 2025248 → open_code=5,2,6, open_time=2025-09-14 16:00:00
  - 2025247 → open_code=2,6,2, open_time=2025-09-13 16:00:00
  - 2025246 → open_code=9,9,7, open_time=2025-09-12 16:00:00