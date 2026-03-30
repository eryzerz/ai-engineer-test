from __future__ import annotations

from datetime import date

import streamlit as st

import mcp_client
import qa_flow
import receipt_rag

st.set_page_config(page_title="Receipt Q&A", layout="wide")
st.title("Receipt Q&A")

use_sql = False
top_k = 5

question = st.text_area("Your question", placeholder="e.g. When did I last use a taxi?", height=100)

if st.button("Ask", disabled=not question.strip()):
    q = question.strip()
    if use_sql:
        try:
            sql = qa_flow.generate_select_sql(q, today_iso=date.today().isoformat())
        except Exception as e:
            st.error(f"Could not generate SQL: {e}")
        else:
            with st.expander("Generated SQL", expanded=True):
                st.code(sql, language="sql")
            try:
                rows = mcp_client.query_rows_json(sql)
            except Exception as e:
                st.error(f"MCP query failed: {e}")
            else:
                try:
                    answer = qa_flow.synthesize_answer(q, rows)
                except Exception as e:
                    st.error(f"Could not synthesize answer: {e}")
                else:
                    st.markdown("### Answer")
                    st.markdown(answer)
                    if rows:
                        with st.expander("Raw rows (preview)"):
                            preview = []
                            for r in rows[:50]:
                                row = dict(r)
                                if "items" in row:
                                    row["items"] = mcp_client.format_item_names(row.get("items"))
                                preview.append(row)
                            st.dataframe(preview, use_container_width=True)
    else:
        try:
            qvec = receipt_rag.embed_query(q)
        except Exception as e:
            st.error(f"Could not embed question: {e}")
        else:
            try:
                hits = mcp_client.search_receipts_by_vector(qvec, match_count=top_k)
            except Exception as e:
                st.error(f"Semantic search failed: {e}")
            else:
                with st.expander("Semantic matches (pgvector)", expanded=True):
                    if not hits:
                        st.caption("No embedding rows matched. Index receipts on the Receipts page if needed.")
                    for h in hits:
                        st.markdown(f"**receipt_id={h.get('receipt_id')}** · distance={float(h.get('distance', 0)):.4f}")
                        st.text((h.get("content") or "")[:800])
                if not hits:
                    st.warning(
                        "No indexed receipts found. Use **Index receipts missing embeddings** on the Receipts page, "
                        "or try **Use SQL generation**."
                    )
                else:
                    ids = [int(h["receipt_id"]) for h in hits]
                    id_list = ",".join(str(i) for i in ids)
                    sql = (
                        "SELECT id, store_name, receipt_date, total_amount, tax_amount, items, created_at "
                        f"FROM receipts WHERE id IN ({id_list})"
                    )
                    try:
                        rows = mcp_client.query_rows_json(sql)
                    except Exception as e:
                        st.error(f"MCP query failed: {e}")
                    else:
                        order = {rid: i for i, rid in enumerate(ids)}
                        rows = sorted(rows, key=lambda r: order.get(int(r.get("id", 0)), 999))
                        note = (
                            "These rows were retrieved by semantic similarity over embedded receipt text (pgvector), "
                            "not by filtering SQL on the user's exact words."
                        )
                        try:
                            answer = qa_flow.synthesize_answer(q, rows, context_note=note)
                        except Exception as e:
                            st.error(f"Could not synthesize answer: {e}")
                        else:
                            st.markdown("### Answer")
                            st.markdown(answer)
                            if rows:
                                with st.expander("Receipt rows (preview)"):
                                    preview = []
                                    for r in rows[:50]:
                                        row = dict(r)
                                        if "items" in row:
                                            row["items"] = mcp_client.format_item_names(row.get("items"))
                                        preview.append(row)
                                    st.dataframe(preview, use_container_width=True)
