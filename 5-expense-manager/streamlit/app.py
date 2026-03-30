import streamlit as st

st.set_page_config(page_title="Receipt intelligence", layout="wide")
st.title("Receipt Management System")

st.subheader("Menu")
st.page_link("pages/1_Receipts.py", label="Receipts", icon="🧾", use_container_width=True)
st.page_link(
    "pages/2_QA.py",
    label="Q&A",
    icon="💬",
    use_container_width=True,
    help="Ask questions in plain language over saved receipts",
)
st.markdown(
    """
- **Receipts** — upload images & view the uploaded receiptstable  
- **Q&A** — AI Q&A over saved receipts
"""
)
