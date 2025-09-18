# 项目介绍文档

## 1. 项目概述
本项目是一个面向实战的数据采集与分析平台，聚焦彩票领域的预测辅助与研判。平台以“数据采集 → 统计分析 → 可视化与决策支持”为主线，提供高效的指标统计、灵活的筛选分析与清晰的图表呈现，帮助业务快速完成专家预测对比、玩法维度分析与命中规律洞察。

## 3. 技术栈说明
- 语言与版本：Python 3.12  
  - 理由：启动与运行时性能提升、原生 typing 增强、与主流数据科学生态（pandas/numpy/sqlalchemy）长期兼容性更好。
- Web 框架：Streamlit 1.49.0（latest）  
  - 优势：以最少代码构建交互式数据分析界面；天然支持数据应用的布局与组件生态；快速迭代与可视化能力强。
  - 最新特性与最佳实践（基于官方文档要点）：
    - 会话状态 Session State：通过 `st.session_state` 管理跨交互的参数与用户上下文，避免重复计算与状态丢失。
    - 缓存机制：`st.cache_data` 用于纯数据缓存，`st.cache_resource` 用于连接/模型等资源级缓存，帮助提升性能与稳定性。
    - 组件扩展：通过 `components` 生态集成图表与高级交互（如 AgGrid、Option Menu 等）以增强可视化与操作性。
    - 性能优化：控制缓存失效策略、拆分长计算为增量计算、减少不必要的 `st.*` 重新渲染。
- 数据库：MySQL 8.0  
  - 以分库分表方式承载不同彩种的数据集，在高并发/大数据量下依赖组合索引与预聚合表达到查询稳定低延迟。
- 其他依赖（按需）：pandas、numpy、sqlalchemy、matplotlib、plotly、pydantic、tenacity 等。

## 4. 系统架构概览
- 前端层：基于 Streamlit 的交互式单页应用（SPA-style），承担筛选输入、结果渲染、图表展示与轻量交互。
- 应用层：Python 3.11 实现查询组织、指标口径计算与缓存调度（含 `st.cache_data` 与 `st.cache_resource`）。
- 数据层：MySQL 8.0（当前使用库：`lotto_3d`）。  
- 架构演进思路：多彩种 → 多库多站点。当前落地为福彩3D（`lotto_3d`），其他彩种可按同构模式平滑扩展。

## 5. 功能模块
- 专家命中率排行榜：按期号/玩法聚合专家命中表现，支持排序与分页。
- 专家详情下钻（逐期预测对照）：展示某专家在窗口内的逐期预测与开奖号码对照，标记命中。
- 玩法维度热力图与分布统计：提供玩法-数字热度、遗漏、和值/跨度等维度可视化。
- 数据导出（CSV）：将当前查询结果导出为 CSV 以便二次分析（如需在新版本中禁用可直接下线该入口，保留服务端接口以满足任务需求）。
- 注：登录与多彩种选择功能已从页面侧移除（当前页面聚焦福彩3D；多彩种通过多库多站点实现）。

## 6. 非功能性目标
- 高性能
  - 预聚合：对命中率等重计算指标采用周期性预聚合（如 expert_hit_stat），显著降低线上查询延迟。
  - 索引：为高频过滤/关联字段建立复合索引（如 `expert_predictions(issue_name, playtype_id, user_id)`、`lottery_results(issue_name)`）与统计需要的辅助索引。
  - 缓存：前端使用 `st.cache_data`（数据）与 `st.cache_resource`（连接/模型），并设置过期策略。
- 安全性
  - 分库隔离：不同彩种物理隔离，降低数据串扰与权限风险。
  - 只读查询：数据面向分析的读路径默认只读，敏感操作需显式授权。
- 可扩展性
  - 按彩种维度横向扩展：复制站点与库连接配置即可承载新彩种。
  - 玩法可配置：玩法与命中规则映射以配置/策略模式实现，新增/调整玩法成本低。

## 7. 版本与部署
- 推荐运行环境
  - Python 3.11
  - Streamlit 1.49.0（latest）
  - MySQL 8.0
- 部署方式
  - 本地与云端均可运行；生产推荐容器化部署：
    - Docker Compose：定义 `app`（Streamlit）与 `db`（MySQL/或连接外部 RDS）服务，使用环境变量注入连接信息与缓存策略。
  - 运行示例
    - 安装依赖：`pip install -r requirements.txt`
    - 启动应用：`streamlit run Home.py --server.address=0.0.0.0 --server.port=8501`

---

附录 A：数据表与字段（当前允许运行时依赖）
- expert_predictions：user_id, issue_name, playtype_id, numbers, ...
- expert_info：user_id, nick_name, ...
- expert_hit_stat：user_id, playtype_id（或 name 显示映射）, total_count, hit_count, ...
- lottery_results：issue_name, open_code, open_time, sum, span, odd_even_ratio, big_small_ratio, ...
- playtype_dict：playtype_id, playtype_name, ...
- red_val_list / red_val_list_v2：issue_name, playtype_id, num, val, user_id, id, ...

附录 B：性能建议速记
- SQL：优先走覆盖索引；避免跨期大范围全表扫描；使用窗口期/玩法维度的 IN 列表收敛范围。
- 缓存：对“期号列表”“玩法字典”“顶部榜单”等设置短期缓存；对静态字典设置长缓存。
- 前端：将重计算切分为增量计算，减少无关组件的重复渲染；必要时使用自定义组件优化表格/图表交互。