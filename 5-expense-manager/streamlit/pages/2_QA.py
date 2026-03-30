from __future__ import annotations

from datetime import date

import streamlit as st

import mcp_client
import qa_flow

st.set_page_config(page_title="Receipt Q&A", layout="wide")
st.title("Receipt Q&A")
st.caption("NOTE: Only support English for now.")

question = st.text_area("Your question", placeholder="e.g. What stores appear in my receipts?", height=100)

if st.button("Ask", disabled=not question.strip()):
    q = question.strip()
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
