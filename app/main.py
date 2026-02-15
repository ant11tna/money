from __future__ import annotations

import urllib.parse
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse

from app.config import (
    DEFAULT_FUND_CODES,
    GOLD_PROVIDER,
    HOLDINGS_PROVIDER,
    INDEX_PROVIDER,
    QUOTE_PROVIDER,
    get_gold_provider,
    get_index_provider,
)
from app.db import (
    bulk_upsert_positions,
    delete_position,
    ensure_tables,
    list_positions,
    set_position_active,
    sync_positions,
    update_position_name_if_empty,
    upsert_position,
)
from app.schemas import (
    EstimateResponse,
    GoldQuote,
    IndexQuote,
    PortfolioBulkUpsertRequest,
    PortfolioSyncRequest,
    PositionUpsertRequest,
)
from app.services.estimate import build_fund_detail, estimate_codes

app = FastAPI(title="Fund Dashboard API")
WEB_DIR = Path(__file__).parent / "web"


def _web_file(filename: str, media_type: str | None = None) -> FileResponse:
    return FileResponse(WEB_DIR / filename, media_type=media_type)


@app.on_event("startup")
def startup() -> None:
    ensure_tables()


@app.get("/")
def index() -> FileResponse:
    return _web_file("index.html")


@app.head("/")
def index_head() -> FileResponse:
    return _web_file("index.html")


@app.get("/app.js")
def app_js() -> FileResponse:
    return _web_file("app.js", media_type="application/javascript")


@app.head("/app.js")
def app_js_head() -> FileResponse:
    return _web_file("app.js", media_type="application/javascript")


@app.get("/styles.css")
def styles_css() -> FileResponse:
    return _web_file("styles.css", media_type="text/css")


@app.head("/styles.css")
def styles_css_head() -> FileResponse:
    return _web_file("styles.css", media_type="text/css")


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "mode": "fastapi",
        "holdings_provider": HOLDINGS_PROVIDER,
        "quote_provider": QUOTE_PROVIDER,
        "index_provider": INDEX_PROVIDER,
        "gold_provider": GOLD_PROVIDER,
    }


@app.get("/api/default-codes")
def default_codes() -> dict:
    return {"codes": DEFAULT_FUND_CODES}


@app.get("/api/indexes")
def api_indexes(market: str = Query(default="cn")) -> dict:
    provider = get_index_provider()
    rows = provider.get_indexes(market)
    quotes = [IndexQuote(**row.__dict__).model_dump() for row in rows]
    return {"market": market, "quotes": quotes}


@app.get("/api/gold/realtime")
def api_gold_realtime() -> dict:
    provider = get_gold_provider()
    rows = provider.get_gold_quotes()
    quotes = [GoldQuote(**row.__dict__).model_dump() for row in rows]
    return {"quotes": quotes}




@app.get("/api/funds/{code}/detail")
def api_fund_detail(code: str) -> dict:
    return build_fund_detail(code.strip())

@app.get("/api/portfolio")
def api_portfolio(active_only: int = Query(default=1)) -> dict:
    return list_positions(active_only=active_only != 0)


@app.post("/api/portfolio/positions")
def api_upsert_position(payload: PositionUpsertRequest) -> dict:
    code = payload.code.strip()
    if not code:
        return {"ok": False, "error": "code 不能为空"}

    upsert_position(
        code=code,
        name=payload.name,
        share=payload.share,
        cost=payload.cost,
        current_profit=payload.current_profit,
        is_active=payload.is_active,
    )
    return {"ok": True}


@app.post("/api/portfolio/positions/bulk_upsert")
def api_bulk_upsert_positions(payload: PortfolioBulkUpsertRequest) -> dict:
    count = bulk_upsert_positions([item.model_dump() for item in payload.positions])
    return {"ok": True, "count": count}


@app.delete("/api/portfolio/positions/{code}")
def api_delete_position(code: str) -> dict:
    cleaned = code.strip()
    if not cleaned:
        return {"ok": False, "error": "code 不能为空"}
    ok = delete_position(cleaned)
    return {"ok": ok}


@app.post("/api/portfolio/positions/{code}/archive")
def api_archive_position(code: str) -> dict:
    cleaned = code.strip()
    if not cleaned:
        return {"ok": False, "error": "code 不能为空"}
    ok = set_position_active(cleaned, 0)
    return {"ok": ok}


@app.post("/api/portfolio/positions/{code}/activate")
def api_activate_position(code: str) -> dict:
    cleaned = code.strip()
    if not cleaned:
        return {"ok": False, "error": "code 不能为空"}
    ok = set_position_active(cleaned, 1)
    return {"ok": ok}


@app.post("/api/portfolio/sync")
def api_sync_portfolio(payload: PortfolioSyncRequest) -> dict:
    codes = [c.strip() for c in payload.codes if c and c.strip()]
    sync_positions(codes)
    return {"ok": True, "count": len(codes)}


@app.get("/api/estimate", response_model=EstimateResponse)
def api_estimate(codes: str = Query(default="")) -> JSONResponse:
    raw_codes = urllib.parse.unquote(codes)
    code_list = [c.strip() for c in raw_codes.split(",") if c.strip()]
    result = estimate_codes(code_list)

    for item in result.get("results", []):
        update_position_name_if_empty(item.get("code", ""), item.get("name", ""))

    return JSONResponse(content=result)
