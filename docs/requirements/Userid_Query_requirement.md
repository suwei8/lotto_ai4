# 【专家推荐数据查询工具】Userid_Query - 功能需求文档

## 1. 页面背景
按“期号 + 专家 user_id”查询该专家在该期所有玩法的推荐记录，并展示开奖信息与结果表格；支持按自定义玩法序排序展示。
固定彩种：福彩3D；权限：只读；数据来源：lotto_3d 单库；免登录

## 2. 功能需求

模块A：基础选择
- 功能描述：选择期号、输入专家 user_id。
- 输入与输出
  - 输入：issue_name、user_id
  - 输出：当前选择（issue_name/user_id）
- 系统依赖（表/字段）
  - lotto_3d.expert_predictions(issue_name, user_id, playtype_id, numbers)
  - lotto_3d.playtype_dict(playtype_id, playtype_name)
  - lotto_3d.expert_info(user_id, nick_name)
  - lotto_3d.lottery_results(issue_name, open_code[, open_time 等])
- 实现要点（示例SQL）
  - 期号列表（按期号倒序）：
    SELECT DISTINCT issue_name FROM expert_predictions ORDER BY issue_name DESC;
  - 专家昵称（可选展示）：
    SELECT nick_name FROM expert_info WHERE user_id = ? LIMIT 1;

模块B：查询专家本期所有玩法的推荐记录
- 功能描述：输入 user_id 与期号后，查询该专家在该期所有玩法的推荐组合，玩法名称通过字典映射。
- 输入与输出
  - 输入：issue_name、user_id
  - 输出：表格列（建议）：playtype_name, numbers
- 系统依赖（表/字段）
  - expert_predictions(issue_name, user_id, playtype_id, numbers)
  - playtype_dict(playtype_id, playtype_name)
- 实现要点
  - 使用 playtype_id 关联到 playtype_dict 获取 playtype_name
  - 去重规则：按(playtype_id, numbers)去重
- 示例SQL
  SELECT DISTINCT pd.playtype_name, ep.numbers
  FROM expert_predictions ep
  JOIN playtype_dict pd ON pd.playtype_id = ep.playtype_id
  WHERE ep.issue_name = ? AND ep.user_id = ?
  ORDER BY pd.playtype_id;

模块C：开奖信息展示
- 功能描述：展示当前选定期号的开奖号码（等派生字段如和值/跨度如有可展示）。
- 输入与输出
  - 输入：issue_name
  - 输出：open_code[, sum, span, odd_even_ratio, big_small_ratio, open_time]
- 系统依赖（表/字段）
  - lottery_results(issue_name, open_code[, …])
- 示例SQL
  SELECT open_code, sum, span, odd_even_ratio, big_small_ratio, open_time
  FROM lottery_results
  WHERE issue_name = ?
  LIMIT 1;

模块D：表格排序与展示
- 功能描述：按预设“玩法排序表”对结果进行排序后展示。
- 输入与输出
  - 输入：结果 DataFrame（playtype_name, numbers）
  - 输出：按指定顺序排序后的表格
- 实现要点
  - 客户端定义玩法顺序数组（如：独胆/双胆/三胆/…/百位定/十位定/个位定等）
  - 将 playtype_name 映射为排序权重并据此排序

## 3. 非功能性需求
- 技术栈：Python 3.11 + Streamlit 最新版本
- 使用 Streamlit 的 session_state、组件扩展、st.cache_data 等优化交互与性能
- 性能
  - 索引建议：
    - expert_predictions(issue_name, user_id, playtype_id)
    - playtype_dict(playtype_id)
    - expert_info(user_id)
    - lottery_results(issue_name)
  - 查询最小化：
    - 玩法名称一次性通过 join 映射，不对每行单独查询
- 技术
  - 基于 Streamlit 最新版本，使用 session_state、组件扩展、st.cache_data 等优化交互与性能
- 安全
  - 只读查询
- 可扩展性
  - 玩法名称/顺序由字典与前端数组驱动，新增玩法仅需维护字典与排序数组

## 4. 风险与限制
- 数据口径
  - numbers 存储为文本，可能存在空格/分隔符差异；展示前可进行标准化（去空格）
- 展示一致性
  - 若需跨页面统一玩法顺序，请抽取公共排序表/配置

新数据库映射速查（lotto_3d）
- 专家本期玩法推荐：
  FROM expert_predictions JOIN playtype_dict ON playtype_id
  WHERE issue_name = ? AND user_id = ?
  ⇒ playtype_name, numbers
- 开奖信息：
  FROM lottery_results WHERE issue_name = ?
  ⇒ open_code[, sum, span, odd_even_ratio, big_small_ratio, open_time]
- 昵称（可选）：
  FROM expert_info WHERE user_id = ? ⇒ nick_name