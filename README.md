# Lotto AI 4 Dashboard

Lotto AI 4 是一个基于 Streamlit 的福彩 3D 数据分析平台，聚焦专家推荐表现、开奖冷热走势、号码分布及高级选号辅助。应用通过 SQLAlchemy + PyMySQL 访问 Docker 中的只读 MySQL 8.0 数据库，并在页面层实现缓存、分页、图表和导出等常用数据应用能力。

## 功能亮点
- **专家表现分析**：ExpertHitTop、UserExpertHitStat、UserHitAnalysis、Userid_Query 等页面提供命中排行榜、走势画像与逐期下钻。
- **推荐过滤与组合工具**：UserExpertFilterPlus、FilterTool_MissV2、HitComboFrequencyAnalysis、FusionRecommendation、Xuanhao_3D_P3 等组件支持多维筛选、频次统计、组合模拟与收益预估。
- **开奖趋势与可视化**：HotCold、NumberAnalysis、Playtype_CombinationView、NumberHeatmap 系列、RedValList(v1/v2) 等模块展示冷热走势、玩法热力图、号码分布及排行榜位次分析。
- **统一的缓存与分页**：通过 `utils/cache.py` 与 `utils/pagination.py` 复用 `st.cache_data`、分页控件，保证页面一致性与性能。
- **健壮的数据库访问封装**：所有 SQL 通过 `db/connection.py::query_db` 执行，统一连接池与参数化查询，页面只接受只读操作。

完整页面列表位于 `pages/` 目录（新增诊断页便于探活）：
```
ExpertHitTop.py
FilterTool_MissV2.py
FusionRecommendation.py
HitComboFrequencyAnalysis.py
HotCold.py
NumberAnalysis.py
NumberHeatmap_All_v2.py
NumberHeatmap_Simplified_v2_all.py
Playtype_CombinationView.py
RedValList.py
RedValList_v2.py
UserExpertFilterPlus.py
UserExpertHitStat.py
UserHitAnalysis.py
Userid_Query.py
Xuanhao_3D_P3.py
Diagnostics.py
```

## 快速开始
1. **创建虚拟环境并安装依赖**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. **配置数据库**
   - MySQL 运行在 Docker 容器 `mysql`，只读账号：`root`/`sw63828`，数据库：`lotto_3d`。
   - 应用与数据库需处于同一 Docker network，连接串位于 `db/connection.py`：
     ```
     mysql+pymysql://root:sw63828@mysql:3306/lotto_3d?charset=utf8mb4
     ```
   - 若容器通过宿主端口暴露，请将连接地址改为 `127.0.0.1:3306`。
3. **运行应用**
   ```bash
   streamlit run app.py
   ```

启动后首页会执行 `SELECT 1` 检查数据库连通性，并自动列出所有页面入口。
若数据库暂不可达，页面会给出提示但仍可浏览静态结构。
`Diagnostics` 页面可随时查看数据库版本、表清单并执行一键探活脚本。

## 测试
- 单元测试（默认跳过真实数据库）：
  ```bash
  python -m pytest
  ```
- 需连真实 MySQL 时设置环境变量：
  ```bash
  RUN_DB_TESTS=1 python -m pytest
  ```

测试覆盖内容：
- `tests/test_connection.py`：数据库连通与参数化校验（默认跳过）。
- `tests/test_pagination.py`：分页工具页码与边界逻辑。
- `tests/test_cache.py`：缓存键策略与参数化缓存命中验证。
- `tests/test_numbers.py`：号码解析、命中计算等纯算法函数。

## 目录结构速览
```
app.py                 # Streamlit 入口
.db/connection.py      # SQLAlchemy 引擎与 query_db 封装
utils/                 # 公共工具（缓存、分页、数据获取、命中计算等）
pages/                 # 所有页面脚本
.tests/                # pytest 测试用例
docs/                  # SRS 与各页面需求文档
.streamlit/config.toml # Streamlit 主题设置
```

## 常见问题
- **数据库连不上**：确认应用与 `mysql` 容器在同一网络；若通过宿主端口访问需修改连接串。
- **字符集问题**：连接串强制 `charset=utf8mb4`；若看到乱码，请检查底层表的字符集设置。
- **数据库只读限制**：默认账号仅授予 SELECT 权限，任何写操作都会失败，是预期行为。
- **组合页面数据量大**：部分筛选页面提供 TopN 或分页控制，必要时收紧期号/玩法范围以避免大数据渲染阻塞。

## 下一步建议
- 在 CI 中补充格式化 / Ruff 检查以约束提交质量。
- 将命中规则抽象为可配置策略，未来对接 `lotto_p3/lotto_p5/lotto_ssq` 时仅需调整规则映射。
- 结合 `st.experimental_fragment` 或自定义组件优化高交互页面性能。

> 所有 SQL 必须通过 `query_db` 调用，并确保使用参数化（`:param`）语法，以满足只读、可审计与性能要求。
