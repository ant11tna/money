# 升级前现状梳理与差距清单

## 1) 仓库目录结构

```text
.
├── .git/
├── .gitkeep
├── README.md
├── fund_dashboard.py
├── fund_estimator.py
└── examples/
    ├── gf_nasdaq_270042_holdings.csv
    └── intraday_changes.json
```

## 2) 已阅读文件

- README.md
- fund_dashboard.py
- fund_estimator.py

## 3) 现状总结

### 3.1 现有功能点

- 提供单文件 HTTP 服务页面（`python3 fund_dashboard.py`），支持输入基金代码列表并发起估值。
- 支持“同步基金列表到持仓表”，在表格内手工维护：持有份额、成本价、当前持有收益。
- 支持批量抓取每只基金最新披露持仓，并根据成分实时涨跌估算基金当日涨跌。
- 支持计算并展示：
  - 预估涨跌(%)
  - 行情覆盖权重(%)
  - 预估当日盈亏(元)
- 支持展开“计算明细”，查看每只基金成分股的权重、涨跌、贡献。
- 命令行工具 `fund_estimator.py` 支持通过 CSV 持仓 + JSON 行情输入，离线计算基金预估涨跌。

### 3.2 现有 API（fund_dashboard.py 内建）

- `GET /`：返回内嵌 HTML 页面。
- `GET /api/estimate?codes=xxxx,yyyy`：返回 JSON：
  - `results[]`: 每只基金的估算结果（code/name/report_period/source/estimated_pct/matched_weight/missing_symbols/details）
  - `failures[]`: 失败基金及异常

> 当前无独立 REST 分层，无持久化 API（如 `/api/portfolio/save`、`/api/market/index` 等）。

### 3.3 页面结构（当前单页）

- 标题：基金持仓动态预估。
- 输入区：基金代码文本框。
- 操作按钮：
  - 同步基金列表到持仓表
  - 抓取最新持仓并预估
- 持仓编辑表：基金代码、持有份额、成本价、当前持有收益(元)。
- 结果区：
  - 预估结果汇总表
  - 计算明细（`<details>` 折叠）

> 当前没有导航栏/多模块（行情中心、黄金估值、基金详情 Tabs 等）。

### 3.4 数据源（akshare / eastmoney）调用位置

#### AkShare 调用位置

- `fund_dashboard.py::_fetch_latest_holdings_akshare(code)`
  - `ak.fund_portfolio_hold_em(symbol=code, date=str(year))`
  - 用途：抓基金最新披露股票持仓（优先）

#### Eastmoney 调用位置

- `fund_dashboard.py::fetch_fund_name(code)`
  - `https://fund.eastmoney.com/pingzhongdata/{code}.js`
  - 用途：基金名称
- `fund_dashboard.py::_fetch_latest_holdings_eastmoney(code)`
  - `https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=jjcc...`
  - 用途：基金持仓回退来源
- `fund_dashboard.py::fetch_pct_change(symbol, ...)`
  - `https://push2.eastmoney.com/api/qt/stock/get?secid=...&fields=f170`
  - 用途：成分实时涨跌

## 4) 目标能力差距清单（按优先级）

> 优先级定义：P0=上线阻断，P1=核心能力，P2=体验增强。

### P0：数据与架构基础差距（先补）

1. **缺少持仓持久化（DB）**
   - 现状：持仓只在前端内存，刷新丢失。
   - 目标：持仓落库、可编辑保存。
   - 差距：
     - 需新增数据模型（用户/账户/持仓/历史快照）。
     - 需新增 CRUD API（查询、保存、删除、批量更新）。
     - 需考虑字段：基金代码、份额、成本、累计收益、更新时间。

2. **缺少模块化后端 API 分层**
   - 现状：仅 `BaseHTTPRequestHandler` + 内嵌 HTML。
   - 目标：行情中心、黄金估值、基金详情等多域能力。
   - 差距：
     - 需拆分服务层（market/gold/fund/portfolio）。
     - 需新增统一响应格式、错误码、超时重试、缓存。

3. **缺少可扩展数据源适配层**
   - 现状：基金估值场景里硬编码 akshare/eastmoney。
   - 目标：黄金三平台（招商/浙商/民生）且可扩展。
   - 差距：
     - 需定义 Provider 接口（`get_quote/get_nav/get_fee/...`）。
     - 需实现多平台 adapter + fallback + 健康检查。

### P1：目标功能核心差距

4. **行情中心（A/HK/US 指数切换）缺失**
   - 现状：只有成分股涨跌查询，无独立指数行情页。
   - 差距：
     - 需新增指数列表与分组（A/HK/US）。
     - 需新增切换 UI、列表/卡片组件、定时刷新。
     - 需处理不同市场代码规范与交易时段。

5. **黄金估值（三平台 + 可扩展）缺失**
   - 现状：无黄金模块。
   - 差距：
     - 需新增黄金产品模型（平台、品种、持仓克数/份额、成本）。
     - 需新增估值逻辑（最新价、涨跌、盈亏、总资产）。
     - 需接入招商/浙商/民生数据并支持新增 provider。

6. **我的持仓（总资产、当日盈亏）能力不完整**
   - 现状：仅针对基金输入份额和成本，展示单次估算盈亏；不汇总总资产/当日盈亏，不落库。
   - 差距：
     - 需新增资产总览卡片：总资产、当日盈亏、累计收益。
     - 需实现持仓保存与读取（用户维度/本地数据库）。
     - 需支持编辑后保存与历史版本。

7. **基金估值总览卡片缺失**
   - 现状：只有表格，无总览卡片。
   - 差距：
     - 需新增“预估总资产/收益”卡片。
     - 需统一口径（盘中估值 + 已有持仓收益）。

8. **基金详情页（Tabs + 折线图）缺失**
   - 现状：只有明细表，无详情页结构。
   - 差距：
     - 需新增详情路由/弹窗。
     - 需新增 Tabs：历史业绩、阶段涨幅、历史净值、持仓详情。
     - 需新增历史净值折线图（时间序列数据接口 + 前端图表库）。

### P2：可用性与工程化差距

9. **前端结构单体化，难扩展**
   - 现状：内嵌 HTML+JS 字符串。
   - 差距：
     - 建议拆分为前后端分离或模板化。
     - 便于实现多页面/组件化状态管理。

10. **无缓存、限流、失败降级策略**
   - 现状：请求实时透传外部接口，失败直接报错。
   - 差距：
     - 增加行情缓存（秒级）、持仓缓存（日级）。
     - 增加重试、熔断、provider 切换策略。

11. **缺少测试与监控**
   - 现状：无单元测试/集成测试。
   - 差距：
     - 增加估值逻辑单测、provider 契约测试。
     - 增加关键接口可用性监控与日志追踪。

## 建议实施顺序（简）

1. 先做 **P0 基础设施**：数据库 + API 分层 + provider 接口。
2. 再做 **P1 核心功能**：行情中心、黄金估值、持仓中心、基金详情。
3. 最后做 **P2 工程化**：前端重构、缓存降级、测试监控。
