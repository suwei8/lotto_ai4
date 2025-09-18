# 【选号分布（V2）】RedValList_v2 - 功能需求文档

## 1. 页面背景
在指定期号与玩法维度下，展示“号码集合分布”和命中/连红/连黑等统计信息，并支持将号码集合导入“排行榜位置数字统计器”进行位次分析。页面数据来源于 lotto_3d 的 red_val_list_v2、playtype_dict 与 lottery_results。
固定彩种：福彩3D；权限：只读；数据来源：lotto_3d 单库；免登录

## 2. 功能需求

模块A：期号选择
- 功能描述：选择一个期号作为筛选范围。
- 输入与输出：
  - 输入：issue_name（单值）
  - 输出：当前选中期号
- 使用场景：进入页面后先选择期号
- 系统依赖：
  - lotto_3d.red_val_list_v2(issue_name)
  - lotto_3d.lottery_results(issue_name) 用于开奖信息
- 新数据库映射与示例：
  - 期号列表（按时间/期号倒序，推荐以开奖表为基准或以 v2 表的存在数据为准）：
    SELECT DISTINCT issue_name
    FROM red_val_list_v2
    ORDER BY issue_name DESC;

模块B：玩法选择
- 功能描述：加载当前期号下出现过的玩法，供多选。
- 输入与输出：
  - 输入：issue_name
  - 输出：选中的 playtype_id 列表
- 使用场景：用户可筛选需要查看的玩法
- 系统依赖：
  - lotto_3d.red_val_list_v2(issue_name, playtype_id)
  - lotto_3d.playtype_dict(playtype_id, playtype_name, lottery_id)
- 新数据库映射与示例：
  - 获取有数据的玩法及名称（以当期有记录的玩法为准）：
    SELECT DISTINCT v2.playtype_id, pd.playtype_name
    FROM red_val_list_v2 v2
    JOIN playtype_dict pd ON pd.playtype_id = v2.playtype_id
    WHERE v2.issue_name = ?
    ORDER BY v2.playtype_id;

模块C：选号分布表（主体）
- 功能描述：按所选玩法展示“号码集合”和多种命中/连红/连黑统计信息。
- 输入与输出：
  - 输入：issue_name，playtype_id IN (...)
  - 输出：表格列（建议）：
    - 玩法（playtype_name，经字典映射）
    - 号码集合（num）
    - rank_count
    - hit_count_map
    - serial_hit_count_map
    - series_not_hit_count_map
    - max_serial_hit_count_map
    - max_series_not_hit_count_map
    - his_max_serial_hit_count_map
    - his_max_series_not_hit_count_map
- 使用场景：查看当期各玩法推荐的号码集合与统计分布
- 系统依赖：
  - lotto_3d.red_val_list_v2：
    id, user_id, lottery_id, playtype_id, issue_name, num, val, type,
    rank_count,
    hit_count_map,
    serial_hit_count_map,
    series_not_hit_count_map,
    max_serial_hit_count_map,
    max_series_not_hit_count_map,
    his_max_serial_hit_count_map,
    his_max_series_not_hit_count_map
  - lotto_3d.playtype_dict(playtype_id, playtype_name)
- 新数据库映射与示例：
  - 拉取数据（按 id 倒序，red_val_list_v2 不含 create_time）：
    SELECT id, user_id, playtype_id, issue_name,
           num, val, type,
           rank_count,
           hit_count_map,
           serial_hit_count_map,
           series_not_hit_count_map,
           max_serial_hit_count_map,
           max_series_not_hit_count_map,
           his_max_serial_hit_count_map,
           his_max_series_not_hit_count_map
    FROM red_val_list_v2
    WHERE issue_name = ?
      AND playtype_id IN (?, ?, ...)
    ORDER BY id DESC;
  - 前端以 playtype_id 关联 playtype_dict 获取 playtype_name 并展示“玩法”列

模块D：开奖信息展示（当期）
- 功能描述：展示当前期次的开奖号码与派生统计（和值、跨度、奇偶比、大小比）。
- 输入与输出：
  - 输入：issue_name
  - 输出：open_code、sum、span、odd_even_ratio、big_small_ratio、open_time
- 系统依赖：
  - lotto_3d.lottery_results(issue_name, open_code, sum, span, odd_even_ratio, big_small_ratio, open_time)
- 示例：
  SELECT open_code, sum, span, odd_even_ratio, big_small_ratio, open_time
  FROM lottery_results
  WHERE issue_name = ?
  LIMIT 1;

模块E：排行榜位置数字统计器（组合分析）
- 功能描述：将“号码集合”转为以空格分隔的“数字字符串”，按选中玩法生成若干输入项，交给计算器统计位次出现次数。
- 输入与输出：
  - 输入：若干条“玩法 + 数字字符串”
  - 输出：位次数字出现次数统计表
- 系统依赖：
  - 前端计算组件（不依赖数据库）
- 数据准备说明：
  - 将 num 按英文逗号分割、去除空白，拼接为空格分隔的数字字符串
  - 为每个玩法构建一行供计算器使用

## 3. 非功能性需求
- 技术栈：Python 3.11 + Streamlit 最新版本
- 使用 Streamlit 的 session_state、组件扩展、st.cache_data 等优化交互与性能
- 性能
  - 建议索引：
    - red_val_list_v2(issue_name, playtype_id)
    - playtype_dict(playtype_id) UNIQUE
    - lottery_results(issue_name)
  - 查询合并：
    - 玩法列表一次性查询并建立映射，避免多次重复查询
    - v2 数据使用 IN 批量拉取，前端分组展示
- 技术
  - 基于 Streamlit 最新版本，使用 session_state、组件扩展、st.cache_data 等优化交互与性能
- 安全
  - 页面仅执行只读查询
- 可扩展性
  - 玩法、期号均数据驱动（distinct/字典映射），新增玩法无需调整查询结构
  - 统计字段采用 JSON 文本存储（*_map），前端可直接展示或解析

## 4. 风险与限制
- 字段与排序
  - red_val_list_v2 不包含 create_time，排序建议使用 id DESC 或前端自定义排序；若 id 非唯一，请增加二排序字段（如 playtype_id, issue_name）以确保稳定性
- 玩法名称映射
  - playtype_name 由 playtype_dict 提供，展示前需以 playtype_id 映射
- 数据体量
  - 如期号与玩法组合数据量较大，建议分页或按玩法分段渲染，必要时增加缓存

新数据库映射速查（lotto_3d）
- 玩法列表与名称：
  FROM red_val_list_v2 v2
  JOIN playtype_dict pd ON pd.playtype_id = v2.playtype_id
  WHERE v2.issue_name = ?
  ⇒ playtype_id, playtype_name
- 选号分布数据（v2）：
  FROM red_val_list_v2
  WHERE issue_name = ? AND playtype_id IN (...)
  ⇒ num, val, type, rank_count, *_map 字段
- 开奖信息：
  FROM lottery_results
  WHERE issue_name = ?
  ⇒ open_code, sum, span, odd_even_ratio, big_small_ratio, open_time