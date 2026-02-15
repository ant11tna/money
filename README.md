## 基金持仓动态预估工具（工程化重构阶段 C：SQLite 持仓层）

本项目主入口为 **FastAPI + Uvicorn**，并已实现：
- 可选择数据源 Provider（akshare/eastmoney/mock）
- SQLite 持仓数据层（标准库 `sqlite3`）

> 说明：旧的 `python fund_dashboard.py` **不再作为主入口**，保留为兼容/参考实现。

## 安装依赖

```bash
python -m pip install -r requirements.txt
```

## 启动

### FastAPI 模式（推荐）

```bash
python -m pip install -r requirements.txt
HOLDINGS_PROVIDER=mock QUOTE_PROVIDER=mock INDEX_PROVIDER=mock GOLD_PROVIDER=mock \
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

浏览器访问：`http://127.0.0.1:8000`

## 受限环境启动方式（无依赖/离线测试）

当环境无法安装 `fastapi/uvicorn`（例如代理或离线限制）时，可使用标准库启动：

```bash
python app/serve_stdlib.py
```

说明：
- 该模式仅用于无依赖/离线测试与页面预览。
- 完整功能与生产部署仍建议使用 `python -m pip install -r requirements.txt` + `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`。


## Provider 配置（环境变量）

- `HOLDINGS_PROVIDER=auto|akshare|eastmoney|mock`
- `QUOTE_PROVIDER=auto|eastmoney|mock`
- `INDEX_PROVIDER=mock`（当前默认 mock，非 mock 当前会自动回退并标注 fallback）
- `GOLD_PROVIDER=mock`（当前默认 mock，非 mock 当前会自动回退并标注 fallback）

示例：

```bash
INDEX_PROVIDER=mock GOLD_PROVIDER=mock
```

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

## 前端使用流程（V2 阶段1：三大页面/视图）

页面仍为「单 HTML + 原生 JS」，通过顶部 Tab（并支持 hash）切换：

- `#assets`：资产统计（汇总卡片 + 下钻占位弹窗）
- `#holdings`：持仓（我的持仓 + 基金估值结果）
- `#market`：行情中心（A股/港股/美股/黄金）

支持直接地址切换：

- `http://127.0.0.1:8000/#assets`
- `http://127.0.0.1:8000/#holdings`
- `http://127.0.0.1:8000/#market`

说明：

- 行情中心中的自动刷新(10s)只在 `#market` 视图生效，离开视图自动停止。
- 资产统计卡片可点击打开占位弹窗（阶段2/4预留历史曲线与交易流水能力）。

## 持仓操作流程

1. 页面初始化：优先加载数据库持仓；若为空则使用默认 codes 渲染并提示可同步。
2. 点击“从输入导入到持仓”：调用 `/api/portfolio/sync`。
3. 编辑份额/成本/当前持有收益后点击“保存持仓”：调用 `/api/portfolio/positions`。
4. 点击“抓取并预估”：
   - 调用 `/api/estimate`
   - 同时读取 `/api/portfolio`
   - 计算 `estimatePnL = share * cost * (estimated_pct/100)` 并展示。

## V2 阶段1 验收命令

### 启动

```bash
python -m pip install -r requirements.txt
HOLDINGS_PROVIDER=mock QUOTE_PROVIDER=mock INDEX_PROVIDER=mock GOLD_PROVIDER=mock \
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### curl 验收

```bash
# 基础静态资源
curl -I http://127.0.0.1:8000/
curl -I http://127.0.0.1:8000/app.js
curl -I http://127.0.0.1:8000/styles.css

# 首页资源引用
curl -s http://127.0.0.1:8000/ | head -n 40

# 1) 健康检查
curl -s http://127.0.0.1:8000/api/health

# 2) 点击/切换 “行情中心”（#market）后可验证
curl -s "http://127.0.0.1:8000/api/indexes?market=cn"
curl -s "http://127.0.0.1:8000/api/gold/realtime"

# 3) 点击/切换 “持仓”（#holdings）后可验证
curl -s -X POST http://127.0.0.1:8000/api/portfolio/sync \
  -H 'Content-Type: application/json' \
  -d '{"codes":["270042","006479"]}'

# 4) 保存一条持仓
curl -s -X POST http://127.0.0.1:8000/api/portfolio/positions \
  -H 'Content-Type: application/json' \
  -d '{"code":"270042","name":"广发纳指","share":1000,"cost":1.25,"current_profit":88.5}'

# 5) 查看持仓
curl -s http://127.0.0.1:8000/api/portfolio

# 6) 发起估值（结构保持 {results, failures}）
curl -s "http://127.0.0.1:8000/api/estimate?codes=270042,006479"
```

手工验收路径：

1. 访问 `/`，默认进入“持仓”页（或根据 hash 进入对应视图）。
2. 点击“行情中心”，验证指数/黄金切换、手动刷新与自动刷新行为。
3. 点击“持仓”，验证保存持仓、运行估值、基金详情弹窗。
4. 点击“资产统计”，验证每张卡片均可点击并打开占位弹窗。


## 新增：行情中心 + 黄金估值 API

- `GET /api/indexes?market=cn|hk|us`
- `GET /api/gold/realtime`

说明：
- 指数接口优先使用 `INDEX_PROVIDER` 对应 Provider（当前默认 mock）
- 黄金接口优先使用 `GOLD_PROVIDER` 对应 Provider（当前默认 mock）

## 阶段 D 验收命令

```bash
# 启动（示例）
python -m pip install -r requirements.txt || { echo "pip install failed"; exit 1; }
HOLDINGS_PROVIDER=mock QUOTE_PROVIDER=mock INDEX_PROVIDER=mock GOLD_PROVIDER=mock python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

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

## Tabs 切换展示验证（基金详情弹窗）

1. 点击估值结果中的“详情”按钮，弹出基金详情窗口。
2. 依次点击「历史业绩 / 阶段涨幅 / 历史净值 / 持仓详情」四个 tab。
3. 验证每个 tab 内容均可正常展示，切回「历史净值」时折线图应保持清晰（已按 devicePixelRatio 适配 canvas 渲染）。
4. 可重复切换多次，确认没有空白或模糊重绘。

## 阶段 E 验收命令

```bash
# 启动
python -m pip install -r requirements.txt || { echo "pip install failed"; exit 1; }
HOLDINGS_PROVIDER=mock QUOTE_PROVIDER=mock INDEX_PROVIDER=mock GOLD_PROVIDER=mock python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 基金详情
curl -s "http://127.0.0.1:8000/api/funds/270042/detail"

# 仍保持兼容
curl -s "http://127.0.0.1:8000/api/estimate?codes=270042,006479"
```


## Windows 快速启动

### 推荐方式（FastAPI 正式版）

在 PowerShell 中执行：

```powershell
.\scripts\run.ps1
```

脚本会自动完成：创建/激活 `.venv`、安装依赖、设置默认 Provider（`mock`）、并用 `uvicorn` 启动服务。

### 受限方式（stdlib 版本）

```powershell
.\scripts\run-stdlib.ps1
```

### 手动方式（FastAPI）

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:HOLDINGS_PROVIDER='mock'
$env:QUOTE_PROVIDER='mock'
$env:INDEX_PROVIDER='mock'
$env:GOLD_PROVIDER='mock'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

补充：Windows 上如需提升本地并发，可使用：

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
```
