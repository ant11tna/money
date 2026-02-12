from __future__ import annotations

import hashlib
import time
from typing import Dict, List, Optional, Tuple

from app.providers.base import GoldProvider, GoldQuote, Holding, HoldingsProvider, IndexProvider, IndexQuote, QuoteProvider


def _stable_pct(seed: str, min_value: float = -1.2, max_value: float = 1.2) -> float:
    digest = hashlib.md5(seed.encode("utf-8")).hexdigest()
    raw = int(digest[:8], 16) / 0xFFFFFFFF
    return round(min_value + (max_value - min_value) * raw, 4)


def _stable_base(seed: str, min_value: float, max_value: float) -> float:
    digest = hashlib.md5((seed + "_base").encode("utf-8")).hexdigest()
    raw = int(digest[:8], 16) / 0xFFFFFFFF
    return round(min_value + (max_value - min_value) * raw, 2)


class MockHoldingsProvider(HoldingsProvider):
    def get_fund_name(self, code: str) -> str:
        return f"Mock基金{code}"

    def get_latest_holdings(self, code: str) -> Tuple[List[Holding], str, str]:
        holdings = [
            Holding(symbol="600000", name="浦发银行", weight=8.0),
            Holding(symbol="000001", name="平安银行", weight=6.2),
            Holding(symbol="600519", name="贵州茅台", weight=5.1),
            Holding(symbol="000333", name="美的集团", weight=4.6),
        ]
        return holdings, "Mock季度", "mock"


class MockQuoteProvider(QuoteProvider):
    def __init__(self, quote_cache: Optional[Dict[str, Optional[float]]] = None) -> None:
        self.quote_cache = quote_cache if quote_cache is not None else {}

    def get_pct_change(self, symbol: str) -> Optional[float]:
        if symbol in self.quote_cache:
            return self.quote_cache[symbol]
        self.quote_cache[symbol] = _stable_pct(symbol, -2.0, 2.0)
        return self.quote_cache[symbol]


class MockIndexProvider(IndexProvider):
    _INDEXES = {
        "cn": [
            ("000001", "上证指数"),
            ("399001", "深证成指"),
            ("399006", "创业板指"),
            ("000300", "沪深300"),
            ("000688", "科创50"),
            ("000016", "上证50"),
        ],
        "hk": [
            ("HSI", "恒生指数"),
            ("HSCEI", "恒生中国企业指数"),
            ("HSTECH", "恒生科技指数"),
        ],
        "us": [
            ("DJI", "道琼斯"),
            ("IXIC", "纳斯达克"),
            ("GSPC", "标普500"),
        ],
    }

    def get_indexes(self, market: str) -> List[IndexQuote]:
        normalized = (market or "cn").lower()
        rows = self._INDEXES.get(normalized, self._INDEXES["cn"])
        now = int(time.time())

        quotes: List[IndexQuote] = []
        for code, name in rows:
            change_percent = _stable_pct(code + normalized, -2.2, 2.2)
            current = _stable_base(code + normalized, 1000, 30000)
            change_value = round(current * change_percent / 100.0, 2)
            quotes.append(
                IndexQuote(
                    code=code,
                    name=name,
                    current=current,
                    change_percent=change_percent,
                    change_value=change_value,
                    market=normalized,
                    status="open",
                    updated_at=now,
                )
            )
        return quotes


class MockGoldProvider(GoldProvider):
    def get_gold_quotes(self) -> List[GoldQuote]:
        platforms = ["招商", "浙商", "民生"]
        now = int(time.time())
        result: List[GoldQuote] = []
        for platform in platforms:
            price = _stable_base(platform, 520, 620)
            change_percent = _stable_pct(platform, -1.0, 1.0)
            change = round(price * change_percent / 100.0, 2)
            result.append(
                GoldQuote(
                    platform=platform,
                    price=price,
                    change=change,
                    change_percent=change_percent,
                    status="tradable",
                    updated_at=now,
                )
            )
        return result
