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


# Must match docker/postgres/init/02-receipt-embeddings.sql (text-embedding-004).
EXPECTED_EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIMENSION", "768"))


def _parse_embedding_json(embedding_json: str) -> list[float]:
    try:
        vec = json.loads(embedding_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"embedding_json must be JSON array of floats: {e}") from e
    if not isinstance(vec, list):
        raise ValueError("embedding_json must be a JSON array")
    out: list[float] = []
    for x in vec:
        if isinstance(x, bool) or not isinstance(x, (int, float)):
            raise ValueError("embedding values must be numbers")
        out.append(float(x))
    if len(out) != EXPECTED_EMBEDDING_DIM:
        raise ValueError(f"Expected {EXPECTED_EMBEDDING_DIM} dimensions, got {len(out)}")
    return out


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(v) for v in values) + "]"


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
    # JSON-serialize (Decimal to str for safety)
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


@mcp.tool()
def upsert_receipt_embedding(receipt_id: int, content: str, embedding_json: str) -> str:
    vec = _parse_embedding_json(embedding_json)
    lit = _vector_literal(vec)
    sql = """
        INSERT INTO receipt_embeddings (receipt_id, content, embedding)
        VALUES (%s, %s, %s::vector)
        ON CONFLICT (receipt_id) DO UPDATE SET
            content = EXCLUDED.content,
            embedding = EXCLUDED.embedding
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (receipt_id, content, lit))
        conn.commit()
    return json.dumps({"receipt_id": receipt_id, "status": "ok"})


@mcp.tool()
def search_receipts_by_vector(embedding_json: str, match_count: int = 5) -> str:
    vec = _parse_embedding_json(embedding_json)
    lit = _vector_literal(vec)
    k = max(1, min(int(match_count), 50))
    sql = """
        SELECT receipt_id, content, embedding <=> %s::vector AS distance
        FROM receipt_embeddings
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (lit, lit, k))
            rows = cur.fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        d = float(row["distance"]) if row["distance"] is not None else 0.0
        out.append(
            {
                "receipt_id": row["receipt_id"],
                "content": row["content"],
                "distance": d,
            }
        )
    return json.dumps(out)


@mcp.tool()
def list_receipts_missing_embeddings() -> str:
    sql = """
        SELECT r.id, r.store_name, r.receipt_date, r.total_amount, r.tax_amount, r.items
        FROM receipts r
        LEFT JOIN receipt_embeddings e ON r.id = e.receipt_id
        WHERE e.receipt_id IS NULL
        ORDER BY r.id
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = {k: _cell_json_value(v) for k, v in row.items()}
        out.append(item)
    return json.dumps(out)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
