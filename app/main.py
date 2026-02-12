from __future__ import annotations

import urllib.parse
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse

from app.config import DEFAULT_FUND_CODES, get_gold_provider, get_index_provider
from app.db import ensure_tables, list_positions, sync_positions, update_position_name_if_empty, upsert_position
from app.schemas import EstimateResponse, GoldQuote, IndexQuote, PortfolioSyncRequest, PositionUpsertRequest
from app.services.estimate import build_fund_detail, estimate_codes

app = FastAPI(title="Fund Dashboard API")
WEB_DIR = Path(__file__).parent / "web"


@app.on_event("startup")
def startup() -> None:
    ensure_tables()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/app.js")
def app_js() -> FileResponse:
    return FileResponse(WEB_DIR / "app.js", media_type="application/javascript")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


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
def api_portfolio() -> dict:
    return list_positions()


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
    )
    return {"ok": True}


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
