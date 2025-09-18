from pathlib import Path

import streamlit as st

from db.connection import query_db

st.set_page_config(page_title="Lotto AI 4", layout="wide")

st.title("Lotto AI 4 Dashboard")
st.caption("Data source: MySQL Docker container `mysql:3306` (db: lotto_3d)")

try:
    ok = query_db("SELECT 1 AS ok")
    st.success(f"DB OK: {ok[0]['ok']}")
except Exception as exc:
    st.error(f"Database not reachable: {exc}")
    st.stop()

st.write("请从左侧选择页面。")

pages_dir = Path("pages")
if pages_dir.exists():
    available_pages = sorted(p.stem for p in pages_dir.glob("*.py"))
    if available_pages:
        st.subheader("可用页面")
        for name in available_pages:
            st.markdown(f"- {name}")
else:
    st.info("尚未创建任何页面文件。")
