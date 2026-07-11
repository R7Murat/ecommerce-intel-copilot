"""Streamlit UI: question -> multi-agent answer, with agent-path trace panel."""
import time
from pathlib import Path

import streamlit as st
from huggingface_hub import hf_hub_download, snapshot_download

# --- Fetch data on first startup (cloud deploys have no local data) ---
DATA_DIR = Path("data")
if not (DATA_DIR / "products.db").exists():
    hf_hub_download(repo_id="R7Murat/ecommerce-intel-data", filename="products.db",
                    repo_type="dataset", local_dir=DATA_DIR)
if not (DATA_DIR / "chroma").exists():
    snapshot_download(repo_id="R7Murat/ecommerce-intel-data", allow_patterns="chroma/**",
                      repo_type="dataset", local_dir=DATA_DIR)
# ----------------------------------------------------------------------

from copilot.graph import build_graph

st.set_page_config(page_title="E-Commerce Intelligence Copilot", page_icon="🛒", layout="wide")
st.title("🛒 E-Commerce Product Intelligence Copilot")
st.caption("Multi-agent RAG over Amazon Appliances reviews (2003–2023). "
           "Routes: SQL · RAG · Analyst · Hybrid — critic-gated, source-cited.")


@st.cache_resource
def get_graph():
    return build_graph()


with st.sidebar:
    st.header("Example questions")
    examples = [
        "What are the 5 highest-rated stores with at least 10 products?",
        "What do users complain about regarding ice makers?",
        "How has review volume changed over the years?",
        "Which product declined the most in rating and why?",
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True):
            st.session_state["q"] = ex

q = st.text_input("Ask a question about appliance products and reviews:",
                  value=st.session_state.get("q", ""))

if st.button("Ask", type="primary") and q.strip():
    t0 = time.time()
    with st.spinner("Agents working..."):
        result = get_graph().invoke({"question": q.strip(), "trace": []})
    latency = time.time() - t0

    col_a, col_t = st.columns([2, 1])
    with col_a:
        st.subheader("Answer")
        st.markdown(result["final_answer"])
    with col_t:
        st.subheader("Agent path")
        for step in result.get("trace", []):
            label = step.get("agent", "?")
            extra = step.get("route") or step.get("verdict") or step.get("action") or ""
            st.markdown(f"→ **{label}**" + (f" · `{extra}`" if extra else ""))
        st.metric("Latency", f"{latency:.1f}s")
        if result.get("critic_verdict"):
            st.caption(f"Critic: {result['critic_verdict']['verdict']}")