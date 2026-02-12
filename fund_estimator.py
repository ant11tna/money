from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True)
class Holding:
    """单个持仓信息。"""

    symbol: str
    name: str
    weight: float


@dataclass(frozen=True)
class EstimateResult:
    fund_name: str
    fund_code: str
    estimated_change_pct: float
    direction: str
    contributions: Dict[str, float]


class FundEstimator:
    """根据持仓权重与成分涨跌估算基金日内涨跌幅。"""

    def __init__(self, fund_name: str, fund_code: str, holdings: Iterable[Holding], cash_weight: float = 0.0):
        self.fund_name = fund_name
        self.fund_code = fund_code
        self.holdings = list(holdings)
        self.cash_weight = cash_weight
        self._validate_weights()

    def _validate_weights(self) -> None:
        total_weight = sum(h.weight for h in self.holdings) + self.cash_weight
        if total_weight > 100.0 + 1e-9:
            raise ValueError(f"持仓+现金权重超过100%，当前={total_weight:.2f}%")

    def estimate(self, pct_changes: Dict[str, float]) -> EstimateResult:
        contributions: Dict[str, float] = {}
        estimated_change = 0.0

        for h in self.holdings:
            change = pct_changes.get(h.symbol)
            if change is None:
                # 未提供行情时保守按 0 处理
                change = 0.0
            contribution = h.weight / 100.0 * change
            contributions[h.symbol] = contribution
            estimated_change += contribution

        if estimated_change > 0:
            direction = "上涨"
        elif estimated_change < 0:
            direction = "下跌"
        else:
            direction = "持平"

        return EstimateResult(
            fund_name=self.fund_name,
            fund_code=self.fund_code,
            estimated_change_pct=estimated_change,
            direction=direction,
            contributions=contributions,
        )


def load_holdings_csv(path: Path) -> List[Holding]:
    holdings: List[Holding] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"symbol", "name", "weight"}
        if not required.issubset(reader.fieldnames or set()):
            raise ValueError("CSV 必须包含列：symbol,name,weight")

        for row in reader:
            holdings.append(
                Holding(
                    symbol=row["symbol"].strip(),
                    name=row["name"].strip(),
                    weight=float(row["weight"]),
                )
            )
    return holdings


def load_changes_json(path: Optional[Path]) -> Dict[str, float]:
    if path is None:
        return {}
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ValueError("changes JSON 必须为对象，如 {'AAPL': 1.2}")
    return {str(k): float(v) for k, v in raw.items()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="根据持仓估算基金涨跌")
    parser.add_argument("--fund-name", required=True, help="基金名")
    parser.add_argument("--fund-code", required=True, help="基金代码")
    parser.add_argument("--holdings", required=True, type=Path, help="持仓CSV路径")
    parser.add_argument("--changes", type=Path, default=None, help="实时涨跌JSON路径")
    parser.add_argument("--cash-weight", type=float, default=0.0, help="现金仓位(%)")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    holdings = load_holdings_csv(args.holdings)
    changes = load_changes_json(args.changes)

    estimator = FundEstimator(
        fund_name=args.fund_name,
        fund_code=args.fund_code,
        holdings=holdings,
        cash_weight=args.cash_weight,
    )
    result = estimator.estimate(changes)

    print(f"基金：{result.fund_name}（{result.fund_code}）")
    print(f"预估涨跌：{result.estimated_change_pct:+.3f}%（{result.direction}）")
    print("贡献拆分：")
    for symbol, contribution in sorted(result.contributions.items(), key=lambda x: x[1], reverse=True):
        print(f"- {symbol}: {contribution:+.3f}%")


if __name__ == "__main__":
    main()
