from __future__ import annotations

import json
import os
import re
from typing import Any

from google import genai
from google.genai import types
from pydantic import BaseModel, ConfigDict, Field, field_validator

EXTRACTION_PROMPT = """You are an expert OCR and data extraction pipeline. 
Your only job is to analyze the provided image of a receipt and extract the data into a strict JSON format.

RULES:
1. Output ONLY valid JSON. Do not include markdown formatting, code blocks, or conversational text.
2. If a specific field is unreadable or missing from the receipt, return `null` for that field.
3. Ensure all mathematical fields (prices, quantities) are returned as numbers (floats/integers), not strings.
   Quantity may be fractional (e.g. fuel gallons, weighted produce) — use a float when needed, not rounded to a whole number.
4. Date must be formatted strictly as YYYY-MM-DD. If the year is missing, assume the current year.

SCHEMA:
{
  "store_name": "string",
  "receipt_date": "YYYY-MM-DD",
  "total_amount": float,
  "tax_amount": float,
  "items": [
    {
      "item_name": "string",
      "quantity": float,
      "unit_price": float,
      "total_price": float
    }
  ]
}
"""


class LineItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    item_name: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    total_price: float | None = None


class ReceiptPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_name: str | None = None
    receipt_date: str | None = None
    total_amount: float | None = None
    tax_amount: float | None = None
    items: list[LineItem] = Field(default_factory=list)

    @field_validator("receipt_date")
    @classmethod
    def date_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            raise ValueError("receipt_date must be YYYY-MM-DD")
        return v


def _strip_json_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s*```\s*$", "", t)
    return t.strip()


def parse_and_validate(raw_text: str) -> dict[str, Any]:
    """Strip fences, parse JSON, validate to schema. Returns plain dict for MCP / display."""
    cleaned = _strip_json_fence(raw_text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON from model: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("Top-level JSON must be an object")
    model = ReceiptPayload.model_validate(data)
    return model.model_dump()


def extract_receipt_from_image(image_bytes: bytes, mime_type: str) -> dict[str, Any]:
    """Call Gemini with image + prompt; return validated dict (includes `items` as list of dicts)."""
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("Set GOOGLE_API_KEY or GEMINI_API_KEY for receipt extraction.")
    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    client = genai.Client(api_key=key)
    response = client.models.generate_content(
        model=model,
        contents=[
            EXTRACTION_PROMPT,
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type or "image/jpeg"),
        ],
    )
    raw = (response.text or "").strip()
    if not raw:
        raise ValueError("Empty response from Gemini")
    return parse_and_validate(raw)
