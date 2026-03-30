from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

MCP_URL = os.environ.get("MCP_SERVER_URL", "http://mcp:8000/mcp").rstrip("/")


def tool_result_text(result) -> str:
    if not result.content:
        return str(result)
    parts: list[str] = []
    for block in result.content:
        if hasattr(block, "text"):
            parts.append(block.text)
        else:
            parts.append(str(block))
    return "\n".join(parts)


async def _with_session(coro: Callable[[ClientSession], Awaitable[Any]]):
    async with streamable_http_client(MCP_URL) as (read, write, _get_sid):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await coro(session)


async def list_tools():
    async def inner(session: ClientSession):
        return await session.list_tools()

    return await _with_session(inner)


async def call_query_postgres(sql: str):
    async def inner(session: ClientSession):
        return await session.call_tool("query_postgres", {"sql": sql})

    return await _with_session(inner)


async def call_insert_receipt(
    store_name: str,
    receipt_date: str,
    total_amount: float,
    tax_amount: float,
    items_json: str,
):
    async def inner(session: ClientSession):
        return await session.call_tool(
            "insert_receipt",
            {
                "store_name": store_name,
                "receipt_date": receipt_date,
                "total_amount": total_amount,
                "tax_amount": tax_amount,
                "items": items_json,
            },
        )

    return await _with_session(inner)


def run(coro):
    return asyncio.run(coro)


def query_rows_json(sql: str) -> list[dict[str, Any]]:
    res = run(call_query_postgres(sql))
    text = tool_result_text(res).strip()
    if not text:
        raise ValueError("Empty response from query_postgres (MCP server may have errored during JSON encoding)")
    rows = json.loads(text)
    if not isinstance(rows, list):
        raise ValueError("Expected list from query_postgres")
    return rows


def query_receipts_rows() -> list[dict[str, Any]]:
    sql = (
        "SELECT id, store_name, receipt_date, total_amount, tax_amount, items, created_at "
        "FROM receipts ORDER BY id DESC"
    )
    return query_rows_json(sql)


def format_item_names(items_val: Any) -> str:
    if items_val is None:
        return ""
    if isinstance(items_val, str):
        try:
            items_val = json.loads(items_val)
        except json.JSONDecodeError:
            return ""
    if not isinstance(items_val, list):
        return ""
    names: list[str] = []
    for x in items_val:
        if isinstance(x, dict):
            n = x.get("item_name")
            if n is not None and str(n).strip():
                names.append(str(n).strip())
    return ", ".join(names)
