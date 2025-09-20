 **开发任务清单（backlog）**

---

## ♻️ 最近更新
- 引入 `.env.example` 与 `config/settings.py`，启动时自动加载环境变量并提供默认值/校验。
- 新增 `pyproject.toml` 统一 `black`、`ruff`、`pytest` 配置，配合 `requirements.txt` 中的 dev 依赖即可完成本地检查。
- 首页（`app.py`）拆分至 `app_sections/`，方便后续维护复用的 Streamlit 模块。

## 📌 开发任务清单（lotto\_ai4）

### 1. 项目基础环境

* [x] **初始化项目结构**

  * 目录：`pages/`, `utils/`, `db/`, `tests/`, `docs/`, `config/`, `app_sections/`
  * 配置 Python 3.12，使用 `requirements.txt` 与 `pyproject.toml`
  * 加入基础依赖：`streamlit`, `sqlalchemy`, `pandas`, `numpy`, `mysqlclient`/`pymysql`，并补充 `black`、`ruff`、`pytest`
* [x] **数据库连接层**

  * 在 `db/connection.py` 实现连接 `lotto_3d` 的函数（参数化，支持环境变量配置）
  * 建立通用的 `query_db(sql: str, params: dict)` 工具函数，所有模块统一调用
* [x] **通用工具**

  * 在 `utils/` 实现分页函数、TopN 限制函数、缓存装饰器（基于 `st.cache_data`）
  * 提供 Streamlit 复用组件与图表封装，统一风格与交互

---

### 2. 专家表现分析模块（已上线、持续优化）

* [x] **ExpertHitTop 页面**（已上线，提供排行榜与命中明细下钻）

  * UI：期号范围选择、玩法选择、排序条件、分页器
  * 数据查询：基于 `expert_hit_stat`，JOIN `expert_info`、`playtype_dict`
  * 输出：排行榜表格 + 命中率排序 + 下钻查看专家推荐明细
* [x] **UserExpertHitStat 页面**

  * 输入：期段/玩法范围、专家筛选
  * 输出：专家命中统计表 + 可点击反查推荐记录
* [x] **UserHitAnalysis 页面**

  * 输入：专家 ID、期段/玩法
  * 输出：命中趋势图（柱状/折线）
* [x] **Userid\_Query 页面**

  * 输入：期号 + 用户 ID
  * 输出：该专家在该期的推荐 vs 开奖对照表

---

### 3. 推荐数据探查与可视化

* [x] **UserExpertFilterPlus 页面**

  * 输入：推荐数字过滤条件 + 往期命中特征过滤条件
  * 输出：符合条件的专家集合 + 热力图 + 命中详情
* [x] **NumberAnalysis 页面**

  * 输入：期号/玩法
  * 输出：组合统计、配对/排列展示、投注模拟表格
* [x] **NumberHeatmap\_All\_v2 页面**

  * 输入：单期数据
  * 输出：热力图（数字频次 × 命中状态）
* [x] **NumberHeatmap\_Simplified\_v2\_all 页面**

  * 输入：期段（多期）
  * 输出：简化热力图（例如每 4 期一行）
* [x] **Playtype\_CombinationView 页面**

  * 输入：多个玩法
  * 输出：玩法推荐对比视图（表格/图表）

---

### 4. 开奖走势与选号分布

* [x] **HotCold 页面**

  * 输入：近 N 期或区间
  * 输出：冷热榜（数字频次统计 + 趋势图）
* [x] **RedValList 页面**

  * 输入：期号 + 玩法
  * 输出：号码集合分布（柱状/热力表格）
* [x] **RedValList\_v2 页面**

  * 输入：期号 + 玩法
  * 输出：号码集合分布 + 连红/连黑统计

---

### 5. 辅助工具与组合分析

* [x] **FilterTool\_MissV2 页面**

  * 输入：组合/位次缺失条件 + 回溯期数
  * 输出：缺失组合分布表
* [x] **HitComboFrequencyAnalysis 页面**

  * 输入：期段
  * 输出：命中组合 × 出现次数分布（TopN）
* [x] **FusionRecommendation 页面**

  * 输入：多个策略/玩法
  * 输出：融合推荐（去重、合并、权重规则）
* [x] **Xuanhao\_3D\_P3 页面**

  * 输入：选号规则参数
  * 输出：交互式选号界面（按钮/输入框）

---

### 6. 非功能性支持

* [x] **缓存与性能优化**

  * 所有查询加 `st.cache_data` 缓存
  * 聚合查询优先走 `expert_hit_stat`
  * 默认分页 + TopN 限制
* [x] **安全性**

  * 数据库连接仅 `SELECT` 权限
  * 所有查询参数化，避免 SQL 注入
* [x] **测试与部署**

  * 单元测试：对 utils 和 db 层
  * 集成测试：模拟页面输入输出
  * 部署：Streamlit + Dockerfile（或 docker-compose）

---

## 🚀 后续方向（建议）
- 优化命中趋势、热力图等高交互页面的渲染性能，评估 `st.experimental_fragment`/服务端缓存。
- 将 Ruff 旧版 `select/ignore` 配置迁移至 `lint.*`，并在 CI 中固定 linter 版本。
- 继续完善 `docs/` 下的模块说明与使用案例，方便新成员快速上手。
