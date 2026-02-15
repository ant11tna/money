from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class EstimateResponse(BaseModel):
    results: List[Dict[str, Any]]
    failures: List[str]


class PositionUpsertRequest(BaseModel):
    code: str
    name: Optional[str] = None
    share: float = 0
    cost: float = 0
    current_profit: float = 0
    is_active: Optional[int] = None


class PortfolioBulkUpsertRequest(BaseModel):
    positions: List[PositionUpsertRequest]


class PortfolioSyncRequest(BaseModel):
    codes: List[str]


class IndexQuote(BaseModel):
    code: str
    name: str
    current: float
    change_percent: float
    change_value: float
    market: str
    status: str
    updated_at: int


class GoldQuote(BaseModel):
    platform: str
    price: float
    change: float
    change_percent: float
    status: str
    updated_at: int
