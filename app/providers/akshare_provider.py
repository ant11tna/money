from __future__ import annotations

import time
from typing import List, Tuple

from app.providers.base import Holding, HoldingsProvider, ProviderError

try:
    import akshare as ak  # type: ignore
except Exception:  # noqa: BLE001
    ak = None


def is_available() -> bool:
    return ak is not None


class AkshareHoldingsProvider(HoldingsProvider):
    def get_fund_name(self, code: str) -> str:
        if ak is None:
            raise ProviderError("akshare 不可用")

        # 用 Eastmoney 名称口径保持行为一致
        from app.providers.eastmoney import EastmoneyHoldingsProvider

        return EastmoneyHoldingsProvider().get_fund_name(code)

    def get_latest_holdings(self, code: str) -> Tuple[List[Holding], str, str]:
        if ak is None:
            raise ProviderError("akshare 不可用")

        current_year = time.localtime().tm_year
        best: List[Holding] = []
        best_period = ""

        try:
            for year in [current_year, current_year - 1, current_year - 2]:
                df = ak.fund_portfolio_hold_em(symbol=code, date=str(year))
                if df is None or df.empty:
                    continue

                cols = set(df.columns)
                code_col = "股票代码" if "股票代码" in cols else None
                name_col = "股票名称" if "股票名称" in cols else None
                weight_col = "占净值比例" if "占净值比例" in cols else None
                period_col = "季度" if "季度" in cols else ("报告期" if "报告期" in cols else None)
                if not code_col or not name_col or not weight_col:
                    continue

                if period_col:
                    latest_period = str(df[period_col].iloc[0])
                    sub_df = df[df[period_col].astype(str) == latest_period].copy()
                else:
                    latest_period = f"{year} 年"
                    sub_df = df.copy()

                holdings: List[Holding] = []
                for _, row in sub_df.iterrows():
                    symbol = str(row[code_col]).strip()
                    name = str(row[name_col]).strip()
                    weight_txt = str(row[weight_col]).replace("%", "").strip() or "0"
                    try:
                        weight = float(weight_txt)
                    except ValueError:
                        continue
                    if symbol and symbol.lower() != "nan":
                        holdings.append(Holding(symbol=symbol, name=name, weight=weight))

                if holdings:
                    best = holdings
                    best_period = latest_period
                    break
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"akshare 抓持仓失败: {exc}") from exc

        if not best:
            raise ProviderError("akshare 无可用持仓数据")

        return best, best_period, "akshare"
