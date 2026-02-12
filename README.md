## 基金持仓动态预估工具（工程化重构阶段 C：SQLite 持仓层）

本项目主入口为 **FastAPI + Uvicorn**，并已实现：
- 可选择数据源 Provider（akshare/eastmoney/mock）
- SQLite 持仓数据层（标准库 `sqlite3`）

> 说明：旧的 `python fund_dashboard.py` **不再作为主入口**，保留为兼容/参考实现。

## 安装依赖

```bash
pip install -r requirements.txt
```

## 启动

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

浏览器访问：`http://localhost:8000`

## Provider 配置（环境变量）

- `HOLDINGS_PROVIDER=auto|akshare|eastmoney|mock`
- `QUOTE_PROVIDER=auto|eastmoney|mock`
- `INDEX_PROVIDER=mock`（当前默认 mock）
- `GOLD_PROVIDER=mock`（当前默认 mock）

### auto 规则

- holdings：优先 akshare（可用则用）否则 eastmoney
- quote：优先 eastmoney，失败时自动回退 mock

## SQLite 持仓库

- 数据库文件：`data/app.db`
- 启动时自动建表：`positions`

表结构：

```sql
positions(
  code TEXT PRIMARY KEY,
  name TEXT,
  share REAL DEFAULT 0,
  cost REAL DEFAULT 0,
  current_profit REAL DEFAULT 0,
  updated_at INTEGER
)
```

## API

- `GET /api/health` -> `{"ok": true}`
- `GET /api/default-codes` -> 默认基金代码
- `GET /api/estimate?codes=...` -> `{results, failures}`（保持兼容）
- `GET /api/portfolio` -> `{"positions":[...], "updated_at": ...}`
- `POST /api/portfolio/positions` -> 单条持仓 upsert
- `POST /api/portfolio/sync` -> 按 codes 同步入库（不存在则插入，已存在不改 share/cost/current_profit）

## 前端使用流程（阶段 C）

1. 页面初始化：优先加载数据库持仓；若为空则使用默认 codes 渲染并提示可同步。
2. 点击“同步基金列表到持仓表”：调用 `/api/portfolio/sync`。
3. 编辑份额/成本/当前持有收益后点击“保存持仓”：调用 `/api/portfolio/positions`。
4. 点击“抓取最新持仓并预估”：
   - 调用 `/api/estimate`
   - 同时读取 `/api/portfolio`
   - 计算 `estimatePnL = share * cost * (estimated_pct/100)` 并展示。

## 阶段 C 验收命令

### 启动

```bash
HOLDINGS_PROVIDER=mock QUOTE_PROVIDER=mock uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### curl 验收

```bash
# 1) 健康检查
curl -s http://127.0.0.1:8000/api/health

# 2) 同步代码到持仓库
curl -s -X POST http://127.0.0.1:8000/api/portfolio/sync \
  -H 'Content-Type: application/json' \
  -d '{"codes":["270042","006479"]}'

# 3) 保存一条持仓
curl -s -X POST http://127.0.0.1:8000/api/portfolio/positions \
  -H 'Content-Type: application/json' \
  -d '{"code":"270042","name":"广发纳指","share":1000,"cost":1.25,"current_profit":88.5}'

# 4) 查看持仓
curl -s http://127.0.0.1:8000/api/portfolio

# 5) 发起估值（结构保持 {results, failures}）
curl -s "http://127.0.0.1:8000/api/estimate?codes=270042,006479"
```


## 新增：行情中心 + 黄金估值 API

- `GET /api/indexes?market=cn|hk|us`
- `GET /api/gold/realtime`

说明：
- 指数接口优先使用 `INDEX_PROVIDER` 对应 Provider（当前默认 mock）
- 黄金接口优先使用 `GOLD_PROVIDER` 对应 Provider（当前默认 mock）

## 阶段 D 验收命令

```bash
# 启动（示例）
HOLDINGS_PROVIDER=mock QUOTE_PROVIDER=mock INDEX_PROVIDER=mock GOLD_PROVIDER=mock uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 指数
curl -s "http://127.0.0.1:8000/api/indexes?market=cn"
curl -s "http://127.0.0.1:8000/api/indexes?market=hk"
curl -s "http://127.0.0.1:8000/api/indexes?market=us"

# 黄金
curl -s "http://127.0.0.1:8000/api/gold/realtime"
```


## 新增：基金详情 API 与弹窗 Tabs

- `GET /api/funds/{code}/detail`

返回包含：
- 基金基本信息：`code,name`
- 当前预估：`estimated_pct,matched_weight,report_period,source`
- 持仓明细：`holdings[]`
- 阶段涨幅：`stage_performance[]`（mock 稳定数据）
- 历史净值：`nav_history[]`（mock 稳定数据）

前端：
- summary 表格新增“详情”按钮
- 点击弹窗，包含 Tabs：历史业绩 / 阶段涨幅 / 历史净值 / 持仓详情
- 历史净值使用原生 `canvas` 折线图

## 阶段 E 验收命令

```bash
# 启动
HOLDINGS_PROVIDER=mock QUOTE_PROVIDER=mock INDEX_PROVIDER=mock GOLD_PROVIDER=mock uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 基金详情
curl -s "http://127.0.0.1:8000/api/funds/270042/detail"

# 仍保持兼容
curl -s "http://127.0.0.1:8000/api/estimate?codes=270042,006479"
```
