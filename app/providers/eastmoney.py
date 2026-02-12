from __future__ import annotations

import json
import re
import time
import urllib.request
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple

from app.providers.base import Holding, HoldingsProvider, ProviderError, QuoteProvider


class _SimpleTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_tr = False
        self.in_cell = False
        self.cell_text: List[str] = []
        self.current_row: List[str] = []
        self.rows: List[List[str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag == "tr":
            self.in_tr = True
            self.current_row = []
        elif self.in_tr and tag in {"td", "th"}:
            self.in_cell = True
            self.cell_text = []

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.in_tr and tag in {"td", "th"} and self.in_cell:
            txt = "".join(self.cell_text).strip()
            self.current_row.append(re.sub(r"\s+", " ", txt))
            self.in_cell = False
        elif tag == "tr" and self.in_tr:
            if self.current_row:
                self.rows.append(self.current_row)
            self.in_tr = False


def _http_get(url: str, timeout: int = 12) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://fundf10.eastmoney.com/",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


class EastmoneyHoldingsProvider(HoldingsProvider):
    def get_fund_name(self, code: str) -> str:
        text = _http_get(f"https://fund.eastmoney.com/pingzhongdata/{code}.js?v={int(time.time()*1000)}")
        match = re.search(r"fS_name\s*=\s*\"(.*?)\"", text)
        return match.group(1) if match else code

    def get_latest_holdings(self, code: str) -> Tuple[List[Holding], str, str]:
        text = _http_get(
            f"https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=jjcc&code={code}&topline=200&year=&month=&rt={time.time():.8f}"
        )
        period_match = re.search(r"<label class='left'>(.*?)</label>", text)
        period = period_match.group(1).strip() if period_match else "最新披露期"

        html_match = re.search(r"content:\"(.*)\",arryear", text, flags=re.S)
        if not html_match:
            raise ProviderError("未解析到持仓内容")

        table_html = html_match.group(1).replace('\\"', '"').replace("\\n", "").replace("\\/", "/")
        parser = _SimpleTableParser()
        parser.feed(table_html)
        if not parser.rows:
            raise ProviderError("持仓表为空")

        header = parser.rows[0]
        idx_code = idx_name = idx_weight = -1
        for i, col in enumerate(header):
            if "股票代码" in col:
                idx_code = i
            elif "股票名称" in col:
                idx_name = i
            elif "占净值" in col:
                idx_weight = i
        if min(idx_code, idx_name, idx_weight) < 0:
            raise ProviderError("持仓表字段不完整")

        holdings: List[Holding] = []
        for row in parser.rows[1:]:
            if max(idx_code, idx_name, idx_weight) >= len(row):
                continue
            symbol = row[idx_code].strip()
            name = row[idx_name].strip()
            weight_txt = row[idx_weight].replace("%", "").replace("--", "0").strip() or "0"
            try:
                weight = float(weight_txt)
            except ValueError:
                continue
            if symbol:
                holdings.append(Holding(symbol=symbol, name=name, weight=weight))

        return holdings, period, "eastmoney"


class EastmoneyQuoteProvider(QuoteProvider):
    def __init__(self, quote_cache: Optional[Dict[str, Optional[float]]] = None) -> None:
        self.quote_cache = quote_cache if quote_cache is not None else {}

    def get_pct_change(self, symbol: str) -> Optional[float]:
        if symbol in self.quote_cache:
            return self.quote_cache[symbol]

        for secid in _candidate_secids(symbol):
            try:
                # 行为保持旧版：push2 + f170 字段
                text = _http_get(f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f170")
                data = json.loads(text).get("data")
                if not data or data.get("f170") is None:
                    continue
                self.quote_cache[symbol] = float(data["f170"]) / 100.0
                return self.quote_cache[symbol]
            except Exception:
                continue

        self.quote_cache[symbol] = None
        return None


def _candidate_secids(symbol: str) -> List[str]:
    s = symbol.upper().strip()
    if s.isdigit() and len(s) == 6:
        if s.startswith(("6", "5", "9")):
            return [f"1.{s}"]
        if s.startswith(("0", "3", "8", "4")):
            return [f"0.{s}", f"1.{s}"]
    if s.isdigit() and len(s) == 5:
        return [f"116.{s}"]
    if re.fullmatch(r"[A-Z.]{1,10}", s):
        return [f"105.{s}"]
    return []
