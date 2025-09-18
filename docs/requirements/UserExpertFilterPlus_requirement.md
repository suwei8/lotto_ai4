# 【专家推荐筛选器 Pro】UserExpertFilterPlus - 功能需求文档

## 1. 页面背景
面向“本期专家推荐”的检索与分析：通过“推荐数字过滤器 + 往期命中特征过滤器”，筛出专家集合并输出本期推荐记录、推荐数字热力图与命中详情，辅助决策。
固定彩种：福彩3D；权限：只读；数据来源：lotto_3d 单库；免登录

## 2. 功能需求

模块A：基础筛选
- 功能描述：选择期号与目标玩法（用于本期推荐查询与可视化）。
- 输入与输出
  - 输入：issue_name（单值）、target_playtype_id（单值）
  - 输出：选中期号与目标玩法
- 使用场景：执行查询前的必选项
- 系统依赖（数据库表/字段）
  - lotto_3d.expert_predictions(issue_name, playtype_id)
  - lotto_3d.playtype_dict(playtype_id, playtype_name)
- 新数据库映射（示例SQL）
  - 期号列表（按期号倒序）：
    SELECT DISTINCT issue_name FROM expert_predictions ORDER BY issue_name DESC;
  - 玩法列表（按字典表顺序）：
    SELECT playtype_id, playtype_name FROM playtype_dict ORDER BY playtype_id;

模块B：推荐数字过滤器（支持多条条件）
- 功能描述：按玩法和推荐数字对本期专家进行“包含/不包含”过滤，支持“全部匹配/任意匹配”两种模式。
- 输入与输出
  - 输入：conditions[]，元素结构：
    - playtypes: playtype_id[] 或 playtype_name[]（推荐以 playtype_id 驱动）
    - mode: “包含”/“不包含”
    - match_mode: “全部匹配”/“任意匹配”（不包含时固定为“全部匹配”）
    - numbers: 字符串数组，取值范围 0~9
  - 输出：按条件计算的 user_id 集合（多个条件合并为交集）
- 使用场景：基于推荐数字特征筛选专家
- 系统依赖（数据库表/字段）
  - lotto_3d.expert_predictions(user_id, issue_name, playtype_id, numbers)
- 新数据库映射（示例SQL片段，建议用 playtype_id 过滤）
  - 包含-任意匹配：
    SELECT DISTINCT user_id
    FROM expert_predictions
    WHERE issue_name = ?
      AND playtype_id = ?
      AND (numbers LIKE ? OR numbers LIKE ? ...);
  - 包含-全部匹配：
    SELECT DISTINCT user_id
    FROM expert_predictions
    WHERE issue_name = ?
      AND playtype_id = ?
      AND (numbers LIKE ? AND numbers LIKE ? ...);
  - 不包含（全部不出现）：
    SELECT DISTINCT user_id
    FROM expert_predictions
    WHERE issue_name = ?
      AND playtype_id = ?
      AND (numbers NOT LIKE ? AND numbers NOT LIKE ? ...);

模块C：往期命中特征过滤器
- 功能描述：按专家在往期的命中表现过滤 user_id，支持：
  - 上期命中
  - 上期未命中
  - 近N期命中M次（含运算符 ≥, =, >, <）
- 输入与输出
  - 输入：hit_conditions[]，元素结构：
    - playtype_id
    - mode: “上期命中”/“上期未命中”/“近N期命中M次”
    - recent_n, hit_n, op（当 mode=近N期命中M次 时）
  - 输出：满足条件的 user_id 集合
- 使用场景：叠加历史命中特征进行过滤
- 系统依赖（数据库表/字段/函数）
  - lotto_3d.expert_predictions(issue_name, playtype_id, user_id, numbers)
  - lotto_3d.lottery_results(issue_name, open_code)
  - 命中判断方法：应用层命中规则引擎（按 playtype 判定）
  - 可复用：应用层命中条件评估器
- 新数据库映射（实现要点）
  - 命中计算以期次 join 开奖数据，对比 open_code，按 playtype_id 的规则判定
  - “近N期命中M次”统计应按 issue_name 倒序窗口取近N条，再聚合计数与比较符过滤

模块D：执行筛选与结果展示
- 功能描述：基于模块B与模块C得到的 user_id 交集，查询本期推荐记录，输出推荐热力图与详情。
- 输入与输出
  - 输入：issue_name、target_playtype_id、final_user_ids（B∩C）
  - 输出：
    - 推荐数字热力图（数字→出现次数，标注是否命中）
    - 推荐详情表格（user_id, nick_name, numbers, 命中数量, 是否命中）
- 使用场景：展示本期结果与可视化
- 系统依赖（数据库表/字段/函数）
  - lotto_3d.expert_predictions(user_id, issue_name, playtype_id, numbers)
  - lotto_3d.expert_info(user_id, nick_name)
  - lotto_3d.lottery_results(issue_name, open_code)
  - 应用层命中规则引擎（按 playtype 判定）
- 新数据库映射（示例SQL）
  - 本期推荐记录（限定 user_id 集合）：
    -- placeholder 由 user_ids 大小动态生成
    SELECT user_id, numbers
    FROM expert_predictions
    WHERE issue_name = ?
      AND playtype_id = ?
      AND user_id IN (?, ?, ...);
  - 专家昵称映射：
    SELECT user_id, nick_name FROM expert_info;

模块E：可视化与交互
- 功能描述：
  - 热力图：以推荐数字为维度统计出现次数，高亮命中数字
  - 详情表：按“命中数量”降序（若开奖缺失则不排序）
- 输入与输出
  - 输入：rec_df（本期记录）、open_info、nick_map
  - 输出：Altair 柱状热力图 + DataFrame 详情表
- 系统依赖（函数）
  - 开奖信息读取：从 lottery_results 取 open_code
  - 命中规则引擎：应用层实现命中与命中数量

## 3. 非功能性需求
- 技术栈：Python 3.11 + Streamlit 最新版本
- 使用 Streamlit 的 session_state、组件扩展、st.cache_data 等优化交互与性能
- 性能
  - 索引建议：
    - expert_predictions(issue_name, playtype_id)
    - expert_predictions(user_id)（查询昵称映射时可减少二次扫描）
    - playtype_dict(playtype_id)
    - lottery_results(issue_name)
  - 查询与缓存：
    - 期号、玩法字典一次性拉取并缓存
    - 推荐数字过滤尽量在 SQL 侧合并 LIKE 条件，减少往返
- 技术
  - 基于 Streamlit 最新版本，使用 session_state、组件扩展、st.cache_data 等优化交互与性能
- 安全
  - 仅读操作；避免在页面中暴露内部实现细节与非必要字段
- 可扩展性
  - 过滤条件以数据驱动（操作符、近N期参数可配置）
  - 命中判断封装在 hit_rule，便于玩法扩展与调整

## 4. 风险与限制
- 字段选择
  - expert_predictions 以 playtype_id 作为过滤键；展示名称通过字典表映射（playtype_dict）
- 开奖缺失
  - 当期未开奖时，热力图仅展示次数统计，命中列展示为占位“—”
- 复杂度与性能
  - 多条件 + 跨期命中特征会导致 SQL/计算复杂度提升；需控制 N、M 参数上限并启用必要索引

新数据库映射速查（lotto_3d）
- 玩法字典：
  FROM playtype_dict ORDER BY playtype_id ⇒ playtype_id, playtype_name
- 期号来源：
  FROM expert_predictions DISTINCT issue_name
- 本期推荐：
  FROM expert_predictions WHERE issue_name = ? AND playtype_id = ? AND user_id IN (...)
  ⇒ user_id, numbers
- 专家昵称：
  FROM expert_info ⇒ user_id, nick_name
- 开奖信息：
  FROM lottery_results WHERE issue_name = ? ⇒ open_code, sum, span, odd_even_ratio, big_small_ratio, open_time