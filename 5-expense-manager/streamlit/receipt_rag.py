from __future__ import annotations

import json
import os
from typing import Any

from google import genai
from google.genai import types

# Must match docker/postgres/init/02-receipt-embeddings.sql
EMBEDDING_DIM = 768


def build_receipt_document(data: dict[str, Any]) -> str:
    lines: list[str] = []
    store = data.get("store_name") or "Unknown"
    lines.append(f"Store: {store}")

    rd = data.get("receipt_date")
    if rd is not None:
        lines.append(f"Date: {rd}")

    ta = data.get("total_amount")
    if ta is not None:
        lines.append(f"Total amount: {ta}")

    tax = data.get("tax_amount")
    if tax is not None:
        lines.append(f"Tax amount: {tax}")

    items = data.get("items") or []
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except json.JSONDecodeError:
            items = []
    lines.append("Purchases / line items:")
    if isinstance(items, list):
        for it in items:
            if not isinstance(it, dict):
                continue
            name = (it.get("item_name") or "").strip()
            q = it.get("quantity")
            up = it.get("unit_price")
            tp = it.get("total_price")
            parts: list[str] = []
            if name:
                parts.append(name)
            if q is not None:
                parts.append(f"quantity {q}")
            if up is not None:
                parts.append(f"unit price {up}")
            if tp is not None:
                parts.append(f"line total {tp}")
            if parts:
                lines.append(" - " + ", ".join(parts))
    return "\n".join(lines)


def _client() -> genai.Client:
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("Set GOOGLE_API_KEY or GEMINI_API_KEY for embeddings.")
    return genai.Client(api_key=key)


def _embed(text: str, task_type: str) -> list[float]:
    model = os.environ.get("GEMINI_EMBEDDING_MODEL", "text-embedding-004")
    client = _client()
    # convert 3072 (gemini) to 768 dim
    cfg = types.EmbedContentConfig(
        task_type=task_type,
        output_dimensionality=EMBEDDING_DIM,
    )
    response = client.models.embed_content(model=model, contents=text, config=cfg)
    if not response.embeddings:
        raise ValueError("Empty embeddings from model")
    vals = list(response.embeddings[0].values)
    if len(vals) != EMBEDDING_DIM:
        raise ValueError(
            f"Expected {EMBEDDING_DIM} dims, got {len(vals)} — set GEMINI_EMBEDDING_MODEL to a model "
            f"that supports output_dimensionality={EMBEDDING_DIM}, or align EMBEDDING_DIMENSION / DB schema."
        )
    return vals


def embed_receipt_document(text: str) -> list[float]:
    return _embed(text, "RETRIEVAL_DOCUMENT")


def embed_query(text: str) -> list[float]:
    return _embed(text, "RETRIEVAL_QUERY")
