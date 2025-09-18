# HotCold - 功能需求文档（新版本）

## 1. 页面背景
HotCold（冷热分析）用于对近 N 期（或指定期段）的开奖号码做频次统计与可视化，对比“热号”“冷号”，支持总体与百/十/个位视图。
固定彩种：福彩3D；权限：只读；数据来源：lotto_3d 单库；免登录

## 2. 功能需求

模块 A：区间选择
- 功能描述
  - 支持选择统计范围（最近 X 期；或按期号/日期范围）。默认：最近 30 期。
- 输入与输出
  - 输入：
    - 统计范围类型：最近 N 期 / 期号范围 / 日期范围（至少支持“最近 N 期”，其余可按需扩展）
    - N（整数，默认 30，上限建议 200）
  - 输出：作为后续统计查询的条件。
- 使用场景
  - 用户快速查看近期冷热走势，或回溯指定历史区间。
- 系统依赖（数据库表/字段/API）
  - lotto_3d.lottery_results: issue_name, open_code, open_time
- 新数据库映射
  - 统计字段：issue_name, open_code, open_time
  - 不涉及任何导出功能

模块 B：总体冷热分析（不分位）
- 功能描述
  - 将每期开奖号码 open_code 解析为三位数字（0-9），合并统计所有位的出现频次；计算：
    - 每个数字的出现次数、占比（次数 / 样本总位数）
    - 热榜（Top K，默认 K=5）与冷榜（Bottom K）
- 输入与输出
  - 输入：统计期集合（由模块 A 确定）
  - 输出：数字 0-9 的频次表，热榜与冷榜列表
- 使用场景
  - 评估近期整体数字偏热/偏冷态势
- 系统依赖
  - lotto_3d.lottery_results: issue_name, open_code
- 新数据库映射
  - 不使用 sum、span 等衍生列，避免混淆冷热口径

模块 C：分位冷热分析（百/十/个）
- 功能描述
  - 对百位、十位、个位分别统计数字 0-9 的出现次数、占比；输出各位的热榜/冷榜
- 输入与输出
  - 输入：统计期集合
  - 输出：每个位的 0-9 频次表与热/冷榜
- 使用场景
  - 评估各位独立走势，为定位玩法提供参考
- 系统依赖
  - lotto_3d.lottery_results: issue_name, open_code
- 新数据库映射
  - 仅依赖开奖数据，不依赖 expert_predictions

模块 D：近态对比与趋势
- 功能描述
  - 在“最近 M 期滑窗”（如最近 10 期）上，对总体与分位分别计算滑窗内的热/冷变化趋势（例如：本窗 vs 上个窗的频次差）
  - 输出：各数字的近期涨跌（频次差/占比差）
- 输入与输出
  - 输入：滑窗长度 M（默认 10，建议不超过 N/2）
  - 输出：频次差异表（可按差异值排序查看）
- 使用场景
  - 识别短期热度变化，为临场策略提供依据
- 系统依赖
  - 同模块 B/C
- 新数据库映射
  - 仅依赖 lottery_results

模块 E：交互与展示
- 功能描述
  - 控件：统计范围选择（最近 N 期）；滑窗长度（M，可选）
  - 展示：
    - 总体冷热表与热/冷榜
    - 分位冷热表与热/冷榜
    - 趋势对比（近态 vs 上一窗）
- 输入与输出
  - 输出为页面表格/图表（柱状/折线均可）；不包含导出功能
- 系统依赖
  - 复用模块 B/C/D 结果

## 3. 非功能性需求
- 技术栈：Python 3.11 + Streamlit 最新版本
- 使用 Streamlit 的 session_state、组件扩展、st.cache_data 等优化交互与性能
- 性能
  - 读取近 N 期数据：通过 ORDER BY open_time DESC, issue_name DESC LIMIT N 获取；避免全表扫描
  - 解析 open_code 在应用层完成；一次查询拉取区间内所需字段（issue_name, open_code, open_time）
  - 索引建议：lottery_results(issue_name), lottery_results(open_time)（排序/过滤用）
- 技术
  - 基于 Streamlit 最新版本，使用 session_state、组件扩展、st.cache_data 等优化交互与性能
- 安全
  - 只读权限：仅授予 SELECT 对 lotto_3d.lottery_results
- 可扩展性
  - 支持未来多彩种扩展：通过配置化适配位数解析规则与玩法字典，复用逻辑
  - 统计口径通过参数化（N, M, Top/Bottom K）灵活调整

## 4. 风险与限制
- 已知问题
  - 历史数据若存在 open_code 格式不一致（如空格/分隔符异常），需在应用层健壮解析或清洗
- 数据迁移风险
  - 使用现有字段进行统计与展示
  - 对于无 open_time 的历史记录（若存在），按 issue_name 降序兜底排序
- 统计解释限制
  - 冷热仅反映频次变化，不代表概率因果；需在页面注明“仅统计参考”

## 5. 系统依赖与新数据库映射清单
- 开奖数据：lotto_3d.lottery_results(issue_name, open_code, open_time)
- 解析逻辑：将 open_code 按逗号分割为 3 位数字，并分别计入总体与分位统计

## 附录A：SQL 示例与参数模板
- 最新期号
SELECT issue_name
FROM lotto_3d.lottery_results
ORDER BY open_time DESC, issue_name DESC
LIMIT 1;

- 最近 N 期（含期号、开奖、时间）
SELECT issue_name, open_code, open_time
FROM lotto_3d.lottery_results
ORDER BY open_time DESC, issue_name DESC
LIMIT :N;

- 指定期段
SELECT issue_name, open_code, open_time
FROM lotto_3d.lottery_results
WHERE issue_name BETWEEN :issue_start AND :issue_end
ORDER BY issue_name DESC;

- 指定日期范围
SELECT issue_name, open_code, open_time
FROM lotto_3d.lottery_results
WHERE open_time BETWEEN :start_dt AND :end_dt
ORDER BY open_time DESC, issue_name DESC;

## 附录B：校验样例（可选，lotto_3d）
- 最新期号：2025249
- 最近样例（按时间倒序，部分）：
  - 2025249 → open_code=9,5,2, open_time=2025-09-15 16:00:00
  - 2025248 → open_code=5,2,6, open_time=2025-09-14 16:00:00
  - 2025247 → open_code=2,6,2, open_time=2025-09-13 16:00:00
  - 2025246 → open_code=9,9,7, open_time=2025-09-12 16:00:00