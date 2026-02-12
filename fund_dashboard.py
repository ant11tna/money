from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Optional, Tuple

DEFAULT_FUND_CODES = [
    "270042", "006479", "005698", "161128", "161130", "018993", "016452",
    "019455", "019454", "539001", "017091", "018043", "019172", "019547",
]

try:
    import akshare as ak  # type: ignore
except Exception:  # noqa: BLE001
    ak = None


@dataclass
class Holding:
    symbol: str
    name: str
    weight: float


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


def fetch_fund_name(code: str) -> str:
    text = _http_get(f"https://fund.eastmoney.com/pingzhongdata/{code}.js?v={int(time.time()*1000)}")
    match = re.search(r"fS_name\s*=\s*\"(.*?)\"", text)
    return match.group(1) if match else code


def _fetch_latest_holdings_akshare(code: str) -> Optional[Tuple[List[Holding], str]]:
    if ak is None:
        return None
    try:
        current_year = time.localtime().tm_year
        best: List[Holding] = []
        best_period = ""
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

        if best:
            return best, best_period
    except Exception:
        return None
    return None


def _fetch_latest_holdings_eastmoney(code: str) -> Tuple[List[Holding], str]:
    text = _http_get(
        f"https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=jjcc&code={code}&topline=200&year=&month=&rt={time.time():.8f}"
    )
    period_match = re.search(r"<label class='left'>(.*?)</label>", text)
    period = period_match.group(1).strip() if period_match else "最新披露期"

    html_match = re.search(r"content:\"(.*)\",arryear", text, flags=re.S)
    if not html_match:
        raise ValueError("未解析到持仓内容")
    table_html = html_match.group(1).replace('\\"', '"').replace("\\n", "").replace("\\/", "/")

    parser = _SimpleTableParser()
    parser.feed(table_html)
    if not parser.rows:
        raise ValueError("持仓表为空")

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
        raise ValueError("持仓表字段不完整")

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

    return holdings, period


def fetch_latest_holdings(code: str) -> Tuple[List[Holding], str, str]:
    ak_data = _fetch_latest_holdings_akshare(code)
    if ak_data:
        holdings, period = ak_data
        return holdings, period, "akshare"

    holdings, period = _fetch_latest_holdings_eastmoney(code)
    return holdings, period, "eastmoney"


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


def fetch_pct_change(symbol: str, quote_cache: Dict[str, Optional[float]]) -> Optional[float]:
    if symbol in quote_cache:
        return quote_cache[symbol]

    for secid in _candidate_secids(symbol):
        try:
            text = _http_get(f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f170")
            data = json.loads(text).get("data")
            if not data or data.get("f170") is None:
                continue
            quote_cache[symbol] = float(data["f170"]) / 100.0
            return quote_cache[symbol]
        except Exception:
            continue

    quote_cache[symbol] = None
    return None


def estimate_fund(code: str, quote_cache: Dict[str, Optional[float]]) -> dict:
    name = fetch_fund_name(code)
    holdings, period, source = fetch_latest_holdings(code)

    details = []
    estimated_pct = 0.0
    matched_weight = 0.0
    missing_symbols = []

    for h in holdings:
        pct = fetch_pct_change(h.symbol, quote_cache)
        if pct is None:
            pct = 0.0
            missing_symbols.append(h.symbol)
        else:
            matched_weight += h.weight

        contribution = h.weight * pct / 100.0
        estimated_pct += contribution
        details.append(
            {
                "symbol": h.symbol,
                "name": h.name,
                "weight": round(h.weight, 4),
                "change": round(pct, 4),
                "contribution": round(contribution, 4),
            }
        )

    details.sort(key=lambda x: x["contribution"], reverse=True)
    return {
        "code": code,
        "name": name,
        "report_period": period,
        "estimated_pct": round(estimated_pct, 4),
        "matched_weight": round(matched_weight, 4),
        "missing_symbols": missing_symbols,
        "details": details,
        "source": source,
    }


INDEX_HTML = """
<!doctype html><html><head><meta charset='utf-8'/><title>基金动态预估</title>
<style>
body{font-family:Arial,"Microsoft YaHei";margin:20px} textarea{width:100%;height:70px}
table{border-collapse:collapse;width:100%;margin:10px 0}th,td{border:1px solid #ddd;padding:6px} details{margin:8px 0}
input[type=number]{width:120px} .muted{color:#666;font-size:12px}
</style></head><body>
<h2>基金持仓动态预估（最新披露持仓）</h2>
<p>基金代码（空格/逗号分隔）</p>
<textarea id='codes'></textarea><br/>
<button onclick='syncPortfolio()'>同步基金列表到持仓表</button>
<button onclick='runEstimate()'>抓取最新持仓并预估</button>
<p class='muted'>优先用 akshare 抓持仓（若环境已安装），否则回退 Eastmoney；成本价是纯数值，不带 %。</p>

<h3>我的持仓（可改持有收益；成本价不带%）</h3>
<table id='portfolio'>
<thead><tr><th>基金代码</th><th>持有份额</th><th>成本价</th><th>当前持有收益(元,可编辑)</th></tr></thead>
<tbody></tbody>
</table>

<div id='msg'></div>
<h3>预估结果</h3><div id='summary'></div>
<h3>计算明细（点开查看）</h3><div id='details'></div>

<script>
const defaultCodes = __DEFAULT_CODES__;
document.getElementById('codes').value = defaultCodes.join(' ');
initPortfolio(defaultCodes);

function initPortfolio(codes){
  const tb=document.querySelector('#portfolio tbody');
  tb.innerHTML='';
  codes.forEach(c=>{
    const tr=document.createElement('tr');
    tr.innerHTML=`<td><input class='code' value='${c}'/></td>
      <td><input type='number' class='share' step='0.01' value='0'/></td>
      <td><input type='number' class='cost' step='0.0001' value='0'/></td>
      <td><input type='number' class='profit' step='0.01' value='0'/></td>`;
    tb.appendChild(tr);
  });
}

function syncPortfolio(){
  const codes=document.getElementById('codes').value.split(/[\\s,，]+/).filter(Boolean);
  initPortfolio(codes);
}

function readPortfolio(){
  const map={};
  document.querySelectorAll('#portfolio tbody tr').forEach(tr=>{
    const code=tr.querySelector('.code').value.trim();
    if(!code) return;
    map[code]={
      share: Number(tr.querySelector('.share').value||0),
      cost: Number(tr.querySelector('.cost').value||0),
      profit: Number(tr.querySelector('.profit').value||0),
    };
  });
  return map;
}

async function runEstimate(){
  const codes=document.getElementById('codes').value.split(/[\\s,，]+/).filter(Boolean);
  const portfolio=readPortfolio();

  document.getElementById('msg').innerText='抓取中，请稍候...';
  const resp=await fetch('/api/estimate?codes='+encodeURIComponent(codes.join(',')));
  const data=await resp.json();

  document.getElementById('msg').innerText=data.failures.length
    ? ('部分失败: '+data.failures.join(' | '))
    : '抓取完成';

  const summaryDiv=document.getElementById('summary');
  summaryDiv.innerHTML='';
  let html='<table><tr><th>基金代码</th><th>基金名称</th><th>披露期</th><th>持仓源</th><th>预估涨跌(%)</th><th>行情覆盖权重(%)</th><th>当前持有收益(元)</th><th>预估当日盈亏(元)</th></tr>';
  data.results.forEach(r=>{
    const p=portfolio[r.code] || {share:0,cost:0,profit:0};
    const estimatePnL = p.share * p.cost * (r.estimated_pct/100);
    html += `<tr><td>${r.code}</td><td>${r.name}</td><td>${r.report_period}</td><td>${r.source}</td>
      <td>${r.estimated_pct.toFixed(3)}</td><td>${r.matched_weight.toFixed(2)}</td>
      <td>${p.profit.toFixed(2)}</td><td>${estimatePnL.toFixed(2)}</td></tr>`;
  });
  html+='</table>';
  summaryDiv.innerHTML=html;

  const detailDiv=document.getElementById('details');
  detailDiv.innerHTML='';
  data.results.forEach(r=>{
    let inner='';
    if(r.missing_symbols.length){
      inner += `<p>以下成分未匹配行情，按 0% 处理：${r.missing_symbols.join(', ')}</p>`;
    }
    inner += '<table><tr><th>代码</th><th>名称</th><th>权重(%)</th><th>实时涨跌(%)</th><th>贡献(%)</th></tr>';
    r.details.forEach(x=>{
      inner += `<tr><td>${x.symbol}</td><td>${x.name}</td><td>${x.weight}</td><td>${x.change}</td><td>${x.contribution}</td></tr>`;
    });
    inner += '</table>';

    const d=document.createElement('details');
    d.innerHTML=`<summary>${r.name}（${r.code}）| 预估 ${r.estimated_pct.toFixed(3)}% | 披露期: ${r.report_period} | 源: ${r.source}</summary>${inner}`;
    detailDiv.appendChild(d);
  });
}
</script></body></html>
"""
INDEX_HTML = INDEX_HTML.replace("__DEFAULT_CODES__", json.dumps(DEFAULT_FUND_CODES, ensure_ascii=False))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/":
            body = INDEX_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/estimate":
            query = urllib.parse.parse_qs(parsed.query)
            codes = [c.strip() for c in query.get("codes", [""])[0].split(",") if c.strip()]

            quote_cache: Dict[str, Optional[float]] = {}
            results = []
            failures = []
            for code in codes:
                try:
                    results.append(estimate_fund(code, quote_cache))
                except Exception as exc:  # noqa: BLE001
                    failures.append(f"{code}:{exc}")

            body = json.dumps({"results": results, "failures": failures}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 8000), Handler)
    print("Open http://localhost:8000")
    server.serve_forever()


if __name__ == "__main__":
    main()
