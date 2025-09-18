# 【选号分布】RedValList - 功能需求文档

## 1. 页面背景
“选号分布”用于在指定期次下，按玩法展示专家推荐的“号码集合”分布，辅助用户对同一期内多玩法的推荐数字进行快速浏览与对比，并可把不同玩法的数字导入“排行榜位置数字统计器”做组合位次分析。本页面对应福彩3D。
固定彩种：福彩3D；权限：只读；数据来源：lotto_3d 单库；免登录

## 2. 功能需求


模块B：期次选择（固定彩种：福彩3D）
- 功能描述：选择“期号”作为查询范围；彩种固定为福彩3D。
- 输入与输出：
  - 输入：issue_name（单值）
  - 输出：当前选中期号
- 使用场景：用户需先选定一个期次
- 系统依赖（数据库表/字段）：
  - lotto_3d.expert_predictions(issue_name)
  - lotto_3d.lottery_results(issue_name) 用于开奖信息展示
- 新数据库映射：

  - 期次列表建议来源：
    SELECT DISTINCT issue_name FROM expert_predictions ORDER BY issue_name DESC

模块C：玩法选择
- 功能描述：加载当前期次下出现过的所有玩法，按“玩法名称”多选。
- 输入与输出：
  - 输入：issue_name
  - 输出：选中的 playtype_id 列表
- 使用场景：用户可过滤要查看的玩法
- 系统依赖（数据库表/字段）：
  - lotto_3d.expert_predictions(issue_name, playtype_id)
  - lotto_3d.playtype_dict(playtype_id, playtype_name)
- 新数据库映射：
  - 不从 expert_predictions 读 playtype_name；用 playtype_id 关联 playtype_dict 获取 playtype_name
  - 示例SQL：
    SELECT DISTINCT ep.playtype_id, pd.playtype_name
    FROM expert_predictions ep
    JOIN playtype_dict pd ON pd.playtype_id = ep.playtype_id
    WHERE ep.issue_name = ?
    ORDER BY ep.playtype_id;

模块D：选号分布表（主体展示）
- 功能描述：按用户所选玩法，展示每个玩法的“号码集合”分布（只展示号码集合）。
- 输入与输出：
  - 输入：issue_name，playtype_id IN (...)
  - 输出：表格列：
    - 玩法（来自 playtype_dict.playtype_name）
    - 号码集合（来自 red_val_list.num）
- 使用场景：浏览各玩法号码推荐
- 系统依赖（数据库表/字段）：
  - lotto_3d.red_val_list(user_id, playtype_id, issue_name, num, val, id)
  - lotto_3d.playtype_dict(playtype_id, playtype_name)
- 新数据库映射与约束：
  - 查询条件：issue_name + playtype_id
  - 排序：id DESC 或前端排序；若 id 非唯一，请增加二排序字段（如 playtype_id, issue_name）以确保稳定性
  - 示例SQL：
    SELECT playtype_id, issue_name, num, val, user_id, id
    FROM red_val_list
    WHERE issue_name = ?
      AND playtype_id IN (?, ?, ...)
    ORDER BY id DESC;

模块E：开奖信息展示（当期）
- 功能描述：展示当前期次的开奖号码与统计信息（和值、跨度、奇偶比、大小比）。
- 输入与输出：
  - 输入：issue_name
  - 输出：open_code、sum、span、odd_even_ratio、big_small_ratio、open_time
- 使用场景：辅助用户对比推荐与开奖号
- 系统依赖（数据库表/字段）：
  - lotto_3d.lottery_results(issue_name, open_code, sum, span, odd_even_ratio, big_small_ratio, open_time)
- 新数据库映射：
  - 查询示例：
    SELECT open_code, sum, span, odd_even_ratio, big_small_ratio, open_time
    FROM lottery_results
    WHERE issue_name = ?
    LIMIT 1;

模块F：排行榜位置数字统计器（组合分析）
- 功能描述：将每个选中“玩法”的一条“数字字符串”（由号码集合加工）输入组件，按“指定名次位”统计出现次数。
- 输入与输出：
  - 输入：玩法名称列表，对应数字字符串（以空格分隔）
  - 输出：数字出现次数统计表
- 使用场景：用于跨玩法的位次数字频次分析
- 系统依赖：前端计算组件
- 新数据库映射：无直接DB依赖；输入数据来自模块D的号码集合

## 3. 非功能性需求
- 技术栈：Python 3.12 + Streamlit 最新版本
- 使用 Streamlit 的 session_state、组件扩展、st.cache_data 等优化交互与性能

- 性能
  - 建议索引（lotto_3d）：
    - expert_predictions(issue_name, playtype_id)
    - red_val_list(issue_name, playtype_id)
    - playtype_dict(playtype_id) UNIQUE
    - lottery_results(issue_name)
  - 查询最小化：
    - 玩法映射一次性通过 join 获取
    - red_val_list 使用 IN 批量拉取，前端按玩法分组展示
- 技术
  - 基于 Streamlit 最新版本，使用 session_state、组件扩展、st.cache_data 等优化交互与性能
- 安全

  - 仅读取公开字段；不展示用户隐私信息
  - 仅访问 lotto_3d，不跨库；数据库账号最小权限只读
- 可扩展性
  - 玩法、期次均由数据驱动（distinct/字典表）
  - 支持未来多彩种扩展：通过配置化适配不同玩法字典与位数规则，复用同一查询结构

## 4. 风险与限制

- 已知问题
  - 玩法名称需通过 playtype_dict 映射
  - red_val_list 排序使用 id DESC 或前端排序
- 数据迁移风险
  - 字段缺失带来的代码改造（映射/排序）
  - 索引不足：当前 expert_predictions 未见 issue_name+playtype_id 复合索引；red_val_list 未见索引，需补建以避免大数据量下查询缓慢


——

新数据库映射速查（lotto_3d）
- 玩法列表与名称：
  FROM expert_predictions(ep) JOIN playtype_dict(pd) ON pd.playtype_id = ep.playtype_id
  WHERE ep.issue_name = ?
  输出：playtype_id, playtype_name
- 选号分布数据：
  FROM red_val_list
  WHERE issue_name = ? AND playtype_id IN (...)
  输出：num, val（页面仅需 num；排序建议 ORDER BY id DESC）
- 开奖信息：
  FROM lottery_results
  WHERE issue_name = ?
  输出：open_code, sum, span, odd_even_ratio, big_small_ratio, open_time

开发注意


- 页面“玩法名称”必须通过 playtype_dict 映射得到