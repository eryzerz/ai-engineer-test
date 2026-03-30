from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import psycopg
from mcp.server.fastmcp import FastMCP
from psycopg.rows import dict_row

FORBIDDEN_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


def _validate_select_only(sql: str) -> str:
    raw = sql.strip()
    if not raw:
        raise ValueError("Empty SQL")
    lowered = raw.lower()
    if not lowered.startswith("select"):
        raise ValueError("Only a single SELECT statement is allowed")
    core = raw.rstrip().rstrip(";").strip()
    if ";" in core:
        raise ValueError("Semicolons are not allowed (no multiple statements)")
    if FORBIDDEN_SQL.search(core):
        raise ValueError("Forbidden SQL keyword in query")
    return raw


def _cell_json_value(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def _connect():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg.connect(url, row_factory=dict_row)


mcp = FastMCP(
    "receipt-db",
    host=os.environ.get("FASTMCP_HOST", "0.0.0.0"),
    port=int(os.environ.get("FASTMCP_PORT", "8000")),
)


@mcp.tool()
def query_postgres(sql: str) -> str:
    safe_sql = _validate_select_only(sql)
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(safe_sql)
            rows = cur.fetchall()
    # JSON-serialize (Decimal -> str for safety)
    out: list[dict[str, Any]] = []
    for row in rows:
        item = {k: _cell_json_value(v) for k, v in row.items()}
        out.append(item)
    return json.dumps(out)


@mcp.tool()
def insert_receipt(
    store_name: str,
    receipt_date: str,
    total_amount: float,
    tax_amount: float,
    items: str,
) -> str:
    try:
        parsed = json.loads(items)
    except json.JSONDecodeError as e:
        raise ValueError(f"items must be valid JSON: {e}") from e
    if not isinstance(parsed, list):
        raise ValueError("items JSON must be an array")

    insert_sql = """
        INSERT INTO receipts (store_name, receipt_date, total_amount, tax_amount, items)
        VALUES (%s, %s, %s, %s, %s::jsonb)
        RETURNING id
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                insert_sql,
                (store_name, receipt_date, total_amount, tax_amount, json.dumps(parsed)),
            )
            row = cur.fetchone()
        conn.commit()
    return json.dumps({"id": row["id"] if row else None, "status": "ok"})


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
