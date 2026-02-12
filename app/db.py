from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional

DB_PATH = Path("data") / "app.db"


def _ensure_db_dir() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_conn() -> sqlite3.Connection:
    _ensure_db_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_tables() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS positions(
              code TEXT PRIMARY KEY,
              name TEXT,
              share REAL DEFAULT 0,
              cost REAL DEFAULT 0,
              current_profit REAL DEFAULT 0,
              updated_at INTEGER
            )
            """
        )
        conn.commit()


def list_positions() -> Dict[str, object]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT code, name, share, cost, current_profit, updated_at FROM positions ORDER BY code"
        ).fetchall()

    positions: List[Dict[str, object]] = []
    max_updated_at = 0
    for r in rows:
        updated = int(r["updated_at"] or 0)
        if updated > max_updated_at:
            max_updated_at = updated
        positions.append(
            {
                "code": r["code"],
                "name": r["name"],
                "share": float(r["share"] or 0),
                "cost": float(r["cost"] or 0),
                "current_profit": float(r["current_profit"] or 0),
            }
        )

    return {"positions": positions, "updated_at": max_updated_at}


def upsert_position(code: str, share: float, cost: float, current_profit: float, name: Optional[str] = None) -> None:
    now = int(time.time())
    with get_conn() as conn:
        existing = conn.execute("SELECT code, name FROM positions WHERE code=?", (code,)).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO positions(code, name, share, cost, current_profit, updated_at)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (code, name, share, cost, current_profit, now),
            )
        else:
            final_name = name if name is not None else existing["name"]
            conn.execute(
                """
                UPDATE positions
                SET name=?, share=?, cost=?, current_profit=?, updated_at=?
                WHERE code=?
                """,
                (final_name, share, cost, current_profit, now, code),
            )
        conn.commit()


def sync_positions(codes: List[str]) -> None:
    now = int(time.time())
    with get_conn() as conn:
        for code in codes:
            row = conn.execute("SELECT code FROM positions WHERE code=?", (code,)).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO positions(code, name, share, cost, current_profit, updated_at)
                    VALUES(?, NULL, 0, 0, 0, ?)
                    """,
                    (code, now),
                )
        conn.commit()


def update_position_name_if_empty(code: str, name: str) -> None:
    if not name:
        return
    with get_conn() as conn:
        row = conn.execute("SELECT name FROM positions WHERE code=?", (code,)).fetchone()
        if row is None:
            return
        existing = (row["name"] or "").strip()
        if existing:
            return
        conn.execute("UPDATE positions SET name=?, updated_at=? WHERE code=?", (name, int(time.time()), code))
        conn.commit()
