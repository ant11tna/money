# Money 项目 Codex 执行指引

## 项目结构（关键入口）
- FastAPI 主入口：`app/main.py`
- 前端静态文件目录：`app/web/`
  - 首页：`app/web/index.html`
  - 脚本：`app/web/app.js`
  - 样式：`app/web/styles.css`
- 受限环境（无三方依赖）启动入口：`app/serve_stdlib.py`

## 推荐启动命令（最稳）
优先使用 FastAPI + Uvicorn：

```bash
python -m pip install -r requirements.txt
HOLDINGS_PROVIDER=mock QUOTE_PROVIDER=mock INDEX_PROVIDER=mock GOLD_PROVIDER=mock \
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

说明：
- 这是功能最完整、与生产行为一致的启动方式。
- `mock` Provider 可降低外部网络依赖，适合 Codex 预览与回归验证。

## 何时使用 stdlib 启动脚本
当当前环境无法安装 `fastapi/uvicorn`（离线、网络受限、依赖冲突）时，使用：

```bash
python app/serve_stdlib.py
```

说明：
- 该模式主要用于页面预览与基础 API 验证。
- 若需要完整能力与一致性验证，优先回到 FastAPI 模式。

## 验证步骤（Codex 必跑）
服务启动后，请至少执行以下检查：

```bash
curl -I http://127.0.0.1:8000/
curl -I http://127.0.0.1:8000/app.js
curl -I http://127.0.0.1:8000/styles.css
```

预期：
- 三项都应返回 `200 OK`（至少不应是 `404 Not Found`）。

进一步验证首页与资源引用关系：

```bash
curl -s http://127.0.0.1:8000/ | head -n 40
```

确认 HTML 内存在：
- `href="/styles.css"`
- `src="/app.js"`
