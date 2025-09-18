 **开发任务清单（backlog）**

---

## 📌 开发任务清单（lotto\_ai4）

### 1. 项目基础环境

* [ ] **初始化项目结构**

  * 目录：`pages/`, `utils/`, `db/`, `tests/`, `docs/`
  * 配置 Python 3.12，使用 `requirements.txt` 或 `pyproject.toml`
  * 加入基础依赖：`streamlit`, `sqlalchemy`, `pandas`, `numpy`, `matplotlib`, `mysqlclient` 或 `pymysql`
* [ ] **数据库连接层**

  * 在 `db/connection.py` 实现连接 `lotto_3d` 的函数（参数化，支持配置文件/环境变量）
  * 建立通用的 `query_db(sql: str, params: dict)` 工具函数，所有模块统一调用
* [ ] **通用工具**

  * 在 `utils/` 实现分页函数、TopN 限制函数、缓存装饰器（基于 `st.cache_data`）

---

### 2. 专家表现分析模块

* [ ] **ExpertHitTop 页面**

  * UI：期号范围选择、玩法选择、排序条件、分页器
  * 数据查询：基于 `expert_hit_stat`，JOIN `expert_info`、`playtype_dict`
  * 输出：排行榜表格 + 命中率排序 + 下钻查看专家推荐明细
* [ ] **UserExpertHitStat 页面**

  * 输入：期段/玩法范围、专家筛选
  * 输出：专家命中统计表 + 可点击反查推荐记录
* [ ] **UserHitAnalysis 页面**

  * 输入：专家 ID、期段/玩法
  * 输出：命中趋势图（柱状/折线）
* [ ] **Userid\_Query 页面**

  * 输入：期号 + 用户 ID
  * 输出：该专家在该期的推荐 vs 开奖对照表

---

### 3. 推荐数据探查与可视化

* [ ] **UserExpertFilterPlus 页面**

  * 输入：推荐数字过滤条件 + 往期命中特征过滤条件
  * 输出：符合条件的专家集合 + 热力图 + 命中详情
* [ ] **NumberAnalysis 页面**

  * 输入：期号/玩法
  * 输出：组合统计、配对/排列展示、投注模拟表格
* [ ] **NumberHeatmap\_All\_v2 页面**

  * 输入：单期数据
  * 输出：热力图（数字频次 × 命中状态）
* [ ] **NumberHeatmap\_Simplified\_v2\_all 页面**

  * 输入：期段（多期）
  * 输出：简化热力图（例如每 4 期一行）
* [ ] **Playtype\_CombinationView 页面**

  * 输入：多个玩法
  * 输出：玩法推荐对比视图（表格/图表）

---

### 4. 开奖走势与选号分布

* [ ] **HotCold 页面**

  * 输入：近 N 期或区间
  * 输出：冷热榜（数字频次统计 + 趋势图）
* [ ] **RedValList 页面**

  * 输入：期号 + 玩法
  * 输出：号码集合分布（柱状/热力表格）
* [ ] **RedValList\_v2 页面**

  * 输入：期号 + 玩法
  * 输出：号码集合分布 + 连红/连黑统计

---

### 5. 辅助工具与组合分析

* [ ] **FilterTool\_MissV2 页面**

  * 输入：组合/位次缺失条件 + 回溯期数
  * 输出：缺失组合分布表
* [ ] **HitComboFrequencyAnalysis 页面**

  * 输入：期段
  * 输出：命中组合 × 出现次数分布（TopN）
* [ ] **FusionRecommendation 页面**

  * 输入：多个策略/玩法
  * 输出：融合推荐（去重、合并、权重规则）
* [ ] **Xuanhao\_3D\_P3 页面**

  * 输入：选号规则参数
  * 输出：交互式选号界面（按钮/输入框）

---

### 6. 非功能性支持

* [ ] **缓存与性能优化**

  * 所有查询加 `st.cache_data` 缓存
  * 聚合查询优先走 `expert_hit_stat`
  * 默认分页 + TopN 限制
* [ ] **安全性**

  * 数据库连接仅 `SELECT` 权限
  * 所有查询参数化，避免 SQL 注入
* [ ] **测试与部署**

  * 单元测试：对 utils 和 db 层
  * 集成测试：模拟页面输入输出
  * 部署：Streamlit + Dockerfile（或 docker-compose）
