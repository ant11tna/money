from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple


class ProviderError(RuntimeError):
    """可控的 provider 异常，供上层回退或降级。"""


@dataclass(frozen=True)
class Holding:
    symbol: str
    name: str
    weight: float


@dataclass(frozen=True)
class IndexQuote:
    code: str
    name: str
    current: float
    change_percent: float
    change_value: float
    market: str
    status: str
    updated_at: int


@dataclass(frozen=True)
class GoldQuote:
    platform: str
    price: float
    change: float
    change_percent: float
    status: str
    updated_at: int


class HoldingsProvider(ABC):
    @abstractmethod
    def get_fund_name(self, code: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_latest_holdings(self, code: str) -> Tuple[List[Holding], str, str]:
        raise NotImplementedError


class QuoteProvider(ABC):
    @abstractmethod
    def get_pct_change(self, symbol: str) -> Optional[float]:
        raise NotImplementedError


class IndexProvider(ABC):
    @abstractmethod
    def get_indexes(self, market: str) -> List[IndexQuote]:
        raise NotImplementedError


class GoldProvider(ABC):
    @abstractmethod
    def get_gold_quotes(self) -> List[GoldQuote]:
        raise NotImplementedError
