from __future__ import annotations

import json
import os
import re
from datetime import date
from typing import Any

from google import genai

FORBIDDEN_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)

NL_TO_SQL_INSTRUCTIONS = """You translate the user's question into one read-only SQL query for PostgreSQL.

TABLE receipts:
- id SERIAL PRIMARY KEY
- store_name VARCHAR(255)
- receipt_date DATE (purchase date, YYYY-MM-DD)
- total_amount NUMERIC(10,2)
- tax_amount NUMERIC(10,2)
- items JSONB — array of objects: item_name (string), quantity (float, may be fractional e.g. gallons), unit_price (float), total_price (float)
- created_at TIMESTAMP (row insert time)

RULES:
1. Output ONLY valid JSON with a single key "sql" whose value is the full SELECT query string.
2. No markdown fences or commentary outside the JSON.
3. Exactly one SELECT statement; no trailing semicolon; do not use semicolons inside the query body.
4. Do not use INSERT, UPDATE, DELETE, DDL, or any statement other than SELECT.
5. Query only the receipts table (and literals/subqueries if needed for dates/aggregates).

STORE / MERCHANT NAME FILTERING (important):
- Do NOT rely on a single ILIKE '%phrase%' when the user gives multiple words (e.g. "harbor cafe"). That fails when
  the real store_name has other words between them (e.g. "Harbor Lane Cafe" does not contain the contiguous substring "harbor cafe").
- For questions about which store / merchant / place, prefer PostgreSQL full-text search on store_name using the **simple**
  text config (good for proper nouns):
  to_tsvector('simple', coalesce(store_name, '')) @@ plainto_tsquery('simple', 'keywords here')
- Put only the distilled search words inside plainto_tsquery's string (e.g. harbor cafe), not the full English question.
  Escape any single quote in that string by doubling it ('' inside SQL).
- You may still use ILIKE '%one_distinct_word%' when a single token is enough.

Today's date: {today_iso}
Use this date for relative phrases like "today", "yesterday", "last week".

USER QUESTION:
{question}
"""

ANSWER_SYNTHESIS_INSTRUCTIONS = """You answer the user's question using ONLY the data in the JSON array below.
If the array is empty, say clearly that no matching receipts were found. Do not invent stores, amounts, or dates.
If the result set was truncated for size, mention that briefly.

USER QUESTION:
{question}

RESULT ROWS (JSON array, up to {row_count} rows):
{rows_json}
"""


def _strip_json_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s*```\s*$", "", t)
    return t.strip()


def validate_select_sql(sql: str) -> str:
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


def parse_sql_json_response(raw_text: str) -> str:
    cleaned = _strip_json_fence(raw_text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON from model: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("Top-level JSON must be an object")
    if "sql" not in data:
        raise ValueError('JSON must contain key "sql"')
    q = data["sql"]
    if not isinstance(q, str) or not q.strip():
        raise ValueError('"sql" must be a non-empty string')
    return q.strip()


def _genai_client() -> genai.Client:
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("Set GOOGLE_API_KEY or GEMINI_API_KEY for Q&A.")
    return genai.Client(api_key=key)


def generate_select_sql(user_question: str, *, today_iso: str | None = None) -> str:
    today = today_iso or date.today().isoformat()
    prompt = NL_TO_SQL_INSTRUCTIONS.format(today_iso=today, question=user_question.strip())
    model = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")
    client = _genai_client()
    response = client.models.generate_content(model=model, contents=[prompt])
    raw = (response.text or "").strip()
    if not raw:
        raise ValueError("Empty response from Gemini (SQL step)")
    sql = parse_sql_json_response(raw)
    return validate_select_sql(sql)


def synthesize_answer(
    user_question: str,
    rows: list[dict[str, Any]],
    *,
    max_rows: int = 100,
) -> str:
    truncated = rows[:max_rows]
    truncated_note = len(rows) > max_rows
    rows_json = json.dumps(truncated, indent=2, default=str)
    prompt = ANSWER_SYNTHESIS_INSTRUCTIONS.format(
        question=user_question.strip(),
        row_count=len(truncated),
        rows_json=rows_json,
    )
    if truncated_note:
        prompt += f"\nNote: Total rows from query was {len(rows)}; only the first {max_rows} are shown above.\n"

    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    client = _genai_client()
    response = client.models.generate_content(model=model, contents=[prompt])
    out = (response.text or "").strip()
    if not out:
        raise ValueError("Empty response from Gemini (answer step)")
    return out
