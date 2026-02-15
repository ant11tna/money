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


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row["name"]) for row in rows}


def _migrate_positions_table(conn: sqlite3.Connection) -> None:
    columns = _table_columns(conn, "positions")
    if "is_active" not in columns:
        conn.execute("ALTER TABLE positions ADD COLUMN is_active INTEGER DEFAULT 1")
    if "created_at" not in columns:
        conn.execute("ALTER TABLE positions ADD COLUMN created_at INTEGER")
    conn.execute("UPDATE positions SET is_active=1 WHERE is_active IS NULL")
    conn.execute("UPDATE positions SET created_at=updated_at WHERE created_at IS NULL")


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
              is_active INTEGER DEFAULT 1,
              created_at INTEGER,
              updated_at INTEGER
            )
            """
        )
        _migrate_positions_table(conn)
        conn.commit()


def list_positions(active_only: bool = True) -> Dict[str, object]:
    with get_conn() as conn:
        where_sql = "WHERE is_active=1" if active_only else ""
        rows = conn.execute(
            f"""
            SELECT code, name, share, cost, current_profit, is_active, created_at, updated_at
            FROM positions
            {where_sql}
            ORDER BY code
            """
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
                "is_active": int(r["is_active"] or 0),
                "created_at": int(r["created_at"] or 0),
            }
        )

    return {"positions": positions, "updated_at": max_updated_at}


def upsert_position(
    code: str,
    share: float,
    cost: float,
    current_profit: float,
    name: Optional[str] = None,
    is_active: Optional[int] = None,
) -> None:
    now = int(time.time())
    with get_conn() as conn:
        existing = conn.execute("SELECT code, name, is_active, created_at FROM positions WHERE code=?", (code,)).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO positions(code, name, share, cost, current_profit, is_active, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (code, name, share, cost, current_profit, 1 if is_active is None else int(bool(is_active)), now, now),
            )
        else:
            final_name = name if name is not None else existing["name"]
            final_active = int(bool(existing["is_active"])) if is_active is None else int(bool(is_active))
            conn.execute(
                """
                UPDATE positions
                SET name=?, share=?, cost=?, current_profit=?, is_active=?, updated_at=?
                WHERE code=?
                """,
                (final_name, share, cost, current_profit, final_active, now, code),
            )
        conn.commit()


def bulk_upsert_positions(positions: List[Dict[str, object]]) -> int:
    now = int(time.time())
    count = 0
    with get_conn() as conn:
        for item in positions:
            code = str(item.get("code", "")).strip()
            if not code:
                continue
            existing = conn.execute("SELECT code, name, is_active FROM positions WHERE code=?", (code,)).fetchone()
            name = item.get("name")
            share = float(item.get("share") or 0)
            cost = float(item.get("cost") or 0)
            current_profit = float(item.get("current_profit") or 0)
            is_active = int(bool(item.get("is_active", 1)))
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO positions(code, name, share, cost, current_profit, is_active, created_at, updated_at)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (code, name, share, cost, current_profit, is_active, now, now),
                )
            else:
                final_name = name if name is not None else existing["name"]
                conn.execute(
                    """
                    UPDATE positions
                    SET name=?, share=?, cost=?, current_profit=?, is_active=?, updated_at=?
                    WHERE code=?
                    """,
                    (final_name, share, cost, current_profit, is_active, now, code),
                )
            count += 1
        conn.commit()
    return count


def set_position_active(code: str, is_active: int) -> bool:
    now = int(time.time())
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE positions SET is_active=?, updated_at=? WHERE code=?",
            (int(bool(is_active)), now, code),
        )
        conn.commit()
        return cur.rowcount > 0


def delete_position(code: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM positions WHERE code=?", (code,))
        conn.commit()
        return cur.rowcount > 0


def sync_positions(codes: List[str]) -> None:
    now = int(time.time())
    with get_conn() as conn:
        for code in codes:
            row = conn.execute("SELECT code FROM positions WHERE code=?", (code,)).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO positions(code, name, share, cost, current_profit, is_active, created_at, updated_at)
                    VALUES(?, NULL, 0, 0, 0, 1, ?, ?)
                    """,
                    (code, now, now),
                )
            else:
                conn.execute(
                    "UPDATE positions SET is_active=1, updated_at=? WHERE code=?",
                    (now, code),
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
