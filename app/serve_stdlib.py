from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import DEFAULT_FUND_CODES
from app.db import ensure_tables, list_positions, sync_positions, update_position_name_if_empty, upsert_position
from app.providers.mock import MockGoldProvider, MockIndexProvider

WEB_DIR = Path(__file__).parent / "web"
INDEX_PROVIDER = MockIndexProvider()
GOLD_PROVIDER = MockGoldProvider()


def _json(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _send_file(handler: BaseHTTPRequestHandler, file_path: Path, content_type: str) -> None:
    if not file_path.exists():
        _json(handler, 404, {"ok": False, "error": "not found"})
        return

    content = file_path.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(content)))
    handler.end_headers()
    handler.wfile.write(content)


def _safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _fallback_estimate(codes: list[str]) -> dict:
    failures = [f"{code}:stdlib fallback mode" for code in codes]
    return {"results": [], "failures": failures}


class StdlibHandler(BaseHTTPRequestHandler):
    server_version = "FundStdlibHTTP/1.0"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            _send_file(self, WEB_DIR / "index.html", "text/html; charset=utf-8")
            return
        if path == "/app.js":
            _send_file(self, WEB_DIR / "app.js", "application/javascript; charset=utf-8")
            return
        if path == "/styles.css":
            _send_file(self, WEB_DIR / "styles.css", "text/css; charset=utf-8")
            return

        if path == "/api/health":
            _json(self, 200, {"ok": True, "mode": "stdlib"})
            return

        if path == "/api/default-codes":
            _json(self, 200, {"codes": DEFAULT_FUND_CODES})
            return

        if path == "/api/indexes":
            market = parse_qs(parsed.query).get("market", ["cn"])[0]
            quotes = [x.__dict__ for x in INDEX_PROVIDER.get_indexes(market)]
            _json(self, 200, {"market": market, "quotes": quotes})
            return

        if path == "/api/gold/realtime":
            quotes = [x.__dict__ for x in GOLD_PROVIDER.get_gold_quotes()]
            _json(self, 200, {"quotes": quotes})
            return

        if path == "/api/portfolio":
            _json(self, 200, list_positions())
            return


        if path.startswith("/api/funds/") and path.endswith("/detail"):
            code = path[len("/api/funds/") : -len("/detail")].strip().strip("/")
            if not code:
                _json(self, 400, {"ok": False, "error": "code 不能为空"})
                return
            try:
                from app.services.estimate import build_fund_detail

                _json(self, 200, build_fund_detail(code))
            except Exception:
                _json(
                    self,
                    200,
                    {
                        "code": code,
                        "name": f"Mock基金{code}",
                        "estimated_pct": 0.0,
                        "matched_weight": 0.0,
                        "report_period": "stdlib-fallback",
                        "source": "mock",
                        "holdings": [],
                        "stage_performance": [],
                        "nav_history": [],
                    },
                )
            return

        if path == "/api/estimate":
            code_raw = parse_qs(parsed.query).get("codes", [""])[0]
            codes = [c.strip() for c in unquote(code_raw).split(",") if c.strip()]
            try:
                from app.services.estimate import estimate_codes

                data = estimate_codes(codes)
                for item in data.get("results", []):
                    update_position_name_if_empty(item.get("code", ""), item.get("name", ""))
                _json(self, 200, data)
            except Exception:
                _json(self, 200, _fallback_estimate(codes))
            return

        _json(self, 404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            content_length = 0
        body = self.rfile.read(max(0, content_length))

        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            _json(self, 400, {"ok": False, "error": "invalid json"})
            return

        if path == "/api/portfolio/positions":
            code = str(payload.get("code", "")).strip()
            if not code:
                _json(self, 400, {"ok": False, "error": "code 不能为空"})
                return

            upsert_position(
                code=code,
                name=payload.get("name"),
                share=_safe_float(payload.get("share", 0)),
                cost=_safe_float(payload.get("cost", 0)),
                current_profit=_safe_float(payload.get("current_profit", 0)),
            )
            _json(self, 200, {"ok": True})
            return

        if path == "/api/portfolio/sync":
            raw_codes = payload.get("codes") or []
            codes = [str(c).strip() for c in raw_codes if str(c).strip()]
            sync_positions(codes)
            _json(self, 200, {"ok": True, "count": len(codes)})
            return

        _json(self, 404, {"ok": False, "error": "not found"})

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


def main() -> None:
    ensure_tables()
    port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), StdlibHandler)
    print(f"[stdlib] serving on http://0.0.0.0:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
