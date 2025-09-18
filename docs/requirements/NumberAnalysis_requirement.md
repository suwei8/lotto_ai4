# NumberAnalysis - 功能需求文档（新版本）

## 1. 页面背景
对指定期号与玩法的专家推荐数据做“号码组合统计与筛选”，并提供配对、全排列转换与投注计算展示（无导出）。
固定彩种：福彩3D；权限：只读；数据来源：lotto_3d 单库；免登录

## 2. 功能需求

模块A：期号与玩法选择
- 功能描述
  - 选择单期 issue_name 与单一玩法 playtype，作为统计口径。
- 输入与输出
  - 输入：issue_name（单选）、playtype（单选）
  - 输出：用于后续查询与统计的参数
- 使用场景
  - 针对某期某玩法进行组合分析与筛选
- 系统依赖（数据库表/字段）
  - lotto_3d.lottery_results: issue_name, open_code, open_time
  - lotto_3d.expert_predictions: issue_name, playtype_id, user_id, numbers
  - lotto_3d.playtype_dict: playtype_id, playtype_name
- 新数据库映射
  - 玩法名称来自 playtype_dict


模块B：组合统计与筛选
- 功能描述
  - 对选定期号与玩法的推荐记录，按“user_id + playtype_id + numbers”去重后统计“号码组合”出现次数；提供多维筛选：
    - 排除包含数字、排除和值、排除跨度
    - 保留奇偶比、保留大小比、必须包含的数字
    - 可选排除连续数字
  - 通过区间滑块限定“出现次数范围”
- 输入与输出
  - 输入：issue_name, playtype_id；筛选条件（数字、和值、跨度、奇偶比、大小比、是否排除连续、出现次数范围）
  - 输出：组合统计表（字段：号码组合、出现次数）
- 使用场景
  - 快速定位高频或符合条件的组合清单
- 系统依赖（数据库表/字段）
  - expert_predictions(issue_name, playtype_id, user_id, numbers)
- 新数据库映射
  - 仅使用 numbers 文本进行组合与筛选；过滤逻辑在应用层实现

模块C：开奖信息展示
- 功能描述
  - 同屏显示所选期的开奖信息（issue_name, open_code），便于对照
- 输入与输出
  - 输入：issue_name
  - 输出：open_code, open_time
- 系统依赖
  - lottery_results(issue_name, open_code, open_time)

模块D：号码配对器
- 功能描述
  - 根据“出现次数”排序（高/低），自上而下选择若干组合，累计不同数字不超过设置的最大位数（默认建议≤9）；输出配对结果、未参与数字与被选组合清单
- 输入与输出
  - 输入：排序模式（高/低）、最大配对位数（上限<=10）
  - 输出：配对组合文本、未参与数字列表、选中组合列表
- 系统依赖
  - 使用模块B的过滤结果

模块E：全排列转换（组选）
- 功能描述
  - 对过滤后的组合做全排列（如“123”→“123,132,213,231,312,321”），用于组选投注场景的扩展查看
- 输入与输出
  - 输入：是否启用；可独立设置组选/直选倍数（仅用于展示计算）
  - 输出：排列后的号码文本与对应的投注计算展示
- 系统依赖
  - 仅在前端进行组合排列和计数

模块F：投注计算展示
- 功能描述
  - 基于过滤结果的组合数与用户输入的倍数（组选、直选），展示注数、成本、奖金与收益估算（展示用途，非交易）
- 输入与输出
  - 输入：组选倍数、直选倍数
  - 输出：注数、成本、奖金估算、纯收益估算
- 系统依赖
  - 无额外数据库依赖

## 3. 非功能性需求
- 技术栈：Python 3.12 + Streamlit 最新版本
- 使用 Streamlit 的 session_state、组件扩展、st.cache_data 等优化交互与性能
- 性能
  - 索引建议：expert_predictions(issue_name, playtype_id), lottery_results(issue_name)
  - 单期单玩法查询，避免全期段扫描；仅选择必要字段
- 技术
  - 基于 Streamlit 最新版本，使用 session_state、组件扩展、st.cache_data 等优化交互与性能
- 安全
  - 只读权限：SELECT 访问必要表
- 可扩展性
  - 新玩法支持：通过 playtype_id 自然兼容；仅需在命中/解析工具层补充口径（若后续新增）

## 4. 风险与限制

- numbers 格式需统一（逗号分隔、仅数字）；如历史数据存在异常，需在应用层做健壮解析
- 全排列数量增长快，应限制在可控范围，避免浏览器卡顿（如上限 5 千条展示）

## 5. 系统依赖与新数据库映射清单
- 玩法字典：playtype_dict(playtype_id, playtype_name)
- 预测数据：expert_predictions(issue_name, playtype_id, user_id, numbers)
- 开奖数据：lottery_results(issue_name, open_code, open_time)

## 6. 示例查询（可直接用于开发）
- 最新期号
SELECT issue_name FROM lotto_3d.lottery_results ORDER BY open_time DESC, issue_name DESC LIMIT 1;

- 本期可用玩法
SELECT DISTINCT playtype_id FROM lotto_3d.expert_predictions WHERE issue_name = :issue_name ORDER BY playtype_id;

- 玩法名称
SELECT playtype_id, playtype_name FROM lotto_3d.playtype_dict WHERE playtype_id IN (:playtype_ids) ORDER BY playtype_id;

- 单期单玩法推荐明细（去重在应用层）
SELECT user_id, numbers FROM lotto_3d.expert_predictions WHERE issue_name = :issue_name AND playtype_id = :playtype_id;

- 开奖数据
SELECT issue_name, open_code, open_time FROM lotto_3d.lottery_results WHERE issue_name = :issue_name;

## 7. 示例SQL校验结果（实时，lotto_3d）
- 最新期号：2025249
- 本期可用玩法（playtype_id）：[1001,1002,1003,1005,1006,1007,2001,2002,3013,3014,3015,3016,3017,3018,30031,30032,30033,30041,30042,30043,30051,30052,30053]
- 玩法名称映射（样例）：
  - 1001=独胆，1002=双胆，1003=三胆
  - 1005=五码组选，1006=六码组选，1007=七码组选
  - 2001=杀一，2002=杀二
  - 3013=百位定3，3014=十位定3，3015=个位定3
  - 3016=百位定1，3017=十位定1，3018=个位定1
  - 30031/30032/30033=定位3*3*3-百/十/个
  - 30041/30042/30043=定位4*4*4-百/十/个
  - 30051/30052/30053=定位5*5*5-百/十/个
- 样例推荐行（issue=2025249）
  - (user_id=555, playtype_id=1001, numbers='0')
  - (user_id=555, playtype_id=1002, numbers='0,6')
  - (user_id=555, playtype_id=1003, numbers='0,2,6')
  - (user_id=555, playtype_id=1005, numbers='0,2,4,6,8')
  - (user_id=555, playtype_id=30031, numbers='1,4,6')