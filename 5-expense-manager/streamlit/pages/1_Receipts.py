from __future__ import annotations

import json
from datetime import date

import streamlit as st

import mcp_client
import receipt_extract
import receipt_rag

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
            continue

        try:
            info = json.loads(mcp_client.tool_result_text(res))
            rid = info.get("id")
        except (json.JSONDecodeError, TypeError):
            rid = None
        if rid is not None:
            doc_data = {
                "store_name": store_name,
                "receipt_date": receipt_date,
                "total_amount": total_amount,
                "tax_amount": tax_amount,
                "items": items_list,
            }
            try:
                doc = receipt_rag.build_receipt_document(doc_data)
                vec = receipt_rag.embed_receipt_document(doc)
                mcp_client.upsert_receipt_embedding(int(rid), doc, vec)
            except Exception as emb_e:
                st.warning(f"{name}: receipt saved but semantic index failed — {emb_e}")

# st.subheader("Semantic index (RAG)")
# if st.button("Index receipts missing embeddings"):
#     try:
#         missing = mcp_client.list_receipts_missing_embeddings()
#     except Exception as e:
#         st.error(f"Could not list unindexed receipts: {e}")
#     else:
#         if not missing:
#             st.info("All receipts already have embeddings.")
#         else:
#             bar = st.progress(0, text="Indexing…")
#             done = 0
#             for row in missing:
#                 try:
#                     doc = receipt_rag.build_receipt_document(row)
#                     vec = receipt_rag.embed_receipt_document(doc)
#                     mcp_client.upsert_receipt_embedding(int(row["id"]), doc, vec)
#                     done += 1
#                 except Exception as ex:
#                     st.warning(f"Receipt id={row.get('id')}: {ex}")
#                 bar.progress(done / len(missing), text=f"Indexed {done}/{len(missing)}")
#             st.success(f"Indexed {done} receipt(s).")

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
