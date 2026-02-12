from __future__ import annotations

import os
from typing import Dict, Optional

from app.providers.akshare_provider import AkshareHoldingsProvider, is_available as akshare_available
from app.providers.base import GoldProvider, HoldingsProvider, IndexProvider, QuoteProvider
from app.providers.eastmoney import EastmoneyHoldingsProvider, EastmoneyQuoteProvider
from app.providers.mock import MockGoldProvider, MockHoldingsProvider, MockIndexProvider, MockQuoteProvider

DEFAULT_FUND_CODES = [
    "270042", "006479", "005698", "161128", "161130", "018993", "016452",
    "019455", "019454", "539001", "017091", "018043", "019172", "019547",
]

HTTP_TIMEOUT = 12

HOLDINGS_PROVIDER = os.getenv("HOLDINGS_PROVIDER", "auto").strip().lower()
QUOTE_PROVIDER = os.getenv("QUOTE_PROVIDER", "auto").strip().lower()
INDEX_PROVIDER = os.getenv("INDEX_PROVIDER", "mock").strip().lower()
GOLD_PROVIDER = os.getenv("GOLD_PROVIDER", "mock").strip().lower()


def get_holdings_provider() -> HoldingsProvider:
    if HOLDINGS_PROVIDER == "mock":
        return MockHoldingsProvider()
    if HOLDINGS_PROVIDER == "eastmoney":
        return EastmoneyHoldingsProvider()
    if HOLDINGS_PROVIDER == "akshare":
        return AkshareHoldingsProvider()
    if HOLDINGS_PROVIDER == "auto":
        if akshare_available():
            return AkshareHoldingsProvider()
        return EastmoneyHoldingsProvider()

    return EastmoneyHoldingsProvider()


def get_quote_provider(quote_cache: Optional[Dict[str, Optional[float]]] = None) -> QuoteProvider:
    if QUOTE_PROVIDER == "mock":
        return MockQuoteProvider(quote_cache)
    if QUOTE_PROVIDER == "eastmoney":
        return EastmoneyQuoteProvider(quote_cache)
    if QUOTE_PROVIDER == "auto":
        # auto: 优先 eastmoney，失败后在运行期由 service 自动回退 mock
        return EastmoneyQuoteProvider(quote_cache)

    return EastmoneyQuoteProvider(quote_cache)


def get_index_provider() -> IndexProvider:
    # 当前仅 mock
    _ = INDEX_PROVIDER
    return MockIndexProvider()


def get_gold_provider() -> GoldProvider:
    # 当前仅 mock
    _ = GOLD_PROVIDER
    return MockGoldProvider()
