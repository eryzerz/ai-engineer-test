"""Receipt upload, Gemini extraction, MCP persist, receipts table (REC-01..04)."""

from __future__ import annotations

import json
from datetime import date

import streamlit as st

import mcp_client
import receipt_extract

st.set_page_config(page_title="Receipts", layout="wide")
st.title("Receipts")

uploaded = st.file_uploader(
    "Receipt images",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True,
)

if st.button("Extract & save all", disabled=not uploaded):
    for f in uploaded:
        name = f.name
        try:
            data = receipt_extract.extract_receipt_from_image(f.getvalue(), f.type or "image/jpeg")
        except Exception as e:
            st.error(f"{name}: {e}")
            continue

        store_name = data.get("store_name") or "Unknown"
        receipt_date = data.get("receipt_date") or date.today().isoformat()
        total_amount = float(data["total_amount"]) if data.get("total_amount") is not None else 0.0
        tax_amount = float(data["tax_amount"]) if data.get("tax_amount") is not None else 0.0
        items_list = data.get("items") or []
        items_json = json.dumps(items_list)

        try:
            res = mcp_client.run(
                mcp_client.call_insert_receipt(
                    store_name,
                    receipt_date,
                    total_amount,
                    tax_amount,
                    items_json,
                )
            )
            st.success(f"{name}: saved — {mcp_client.tool_result_text(res)}")
        except Exception as e:
            st.error(f"{name}: MCP insert failed — {e}")

st.subheader("Saved receipts")
try:
    rows = mcp_client.query_receipts_rows()
except Exception as e:
    st.warning(f"Could not load table: {e}")
else:
    display = []
    for r in rows:
        row = dict(r)
        row["items_display"] = mcp_client.format_item_names(row.get("items"))
        if "items" in row:
            del row["items"]
        display.append(row)
    st.dataframe(display, use_container_width=True)
