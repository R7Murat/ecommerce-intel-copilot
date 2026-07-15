"""Gradio UI for HF Spaces deployment. Local dev uses the Streamlit app instead."""
import sys
sys.path.insert(0, "src")

import time
from pathlib import Path

import gradio as gr
from huggingface_hub import hf_hub_download, snapshot_download

# --- Fetch data on first startup (HF Space storage limit: data lives in a dataset repo) ---
DATA_DIR = Path("data")
if not (DATA_DIR / "products.db").exists():
    print("Downloading products.db from dataset repo...")
    hf_hub_download(
        repo_id="R7Murat/ecommerce-intel-data", filename="products.db",
        repo_type="dataset", local_dir=DATA_DIR,
    )
if not (DATA_DIR / "chroma").exists():
    print("Downloading Chroma index from dataset repo...")
    snapshot_download(
        repo_id="R7Murat/ecommerce-intel-data", allow_patterns="chroma/**",
        repo_type="dataset", local_dir=DATA_DIR,
    )
# -------------------------------------------------------------------------------------------

from copilot.graph import build_graph

GRAPH = build_graph()

EXAMPLES = [
    "What are the 5 highest-rated stores with at least 10 products?",
    "What do users complain about regarding ice makers?",
    "How has review volume changed over the years?",
    "Which product declined the most in rating and why?",
]


def ask(question: str):
    if not question.strip():
        return "Please enter a question.", ""
    t0 = time.time()
    result = GRAPH.invoke({"question": question.strip(), "trace": []})
    path = " → ".join(
        f"{s.get('agent', '?')}"
        + (f" ({s.get('route') or s.get('verdict') or s.get('action')})"
           if (s.get('route') or s.get('verdict') or s.get('action')) else "")
        for s in result.get("trace", [])
    )
    path += f"\n\nLatency: {time.time() - t0:.1f}s"
    return result["final_answer"], path


with gr.Blocks(title="E-Commerce Product Intelligence Copilot") as demo:
    gr.Markdown("# 🛒 E-Commerce Product Intelligence Copilot\n"
                "Multi-agent RAG over Amazon Appliances reviews (2003–2023). "
                "Routes: SQL · RAG · Analyst · Hybrid — critic-gated, source-cited.")
    q = gr.Textbox(label="Ask a question about appliance products and reviews")
    btn = gr.Button("Ask", variant="primary")
    with gr.Row():
        answer = gr.Markdown(label="Answer")
        path = gr.Textbox(label="Agent path", lines=6)
    gr.Examples(EXAMPLES, inputs=q)
    btn.click(ask, inputs=q, outputs=[answer, path])
    q.submit(ask, inputs=q, outputs=[answer, path])

demo.launch(server_name="0.0.0.0", server_port=8080)