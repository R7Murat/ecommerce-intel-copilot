"""Knowledge (RAG) agent: semantic retrieval + grounded answering with sources."""
import chromadb
from chromadb.utils import embedding_functions

from copilot.config import REPO_ROOT
from copilot.llm import ask_llm

TOP_K = 6

SYSTEM_PROMPT = """You answer questions about home-appliance products using ONLY the
provided context passages. Rules:
- Every claim must cite its source as [asin] using the parent_asin given with each passage.
- If the context does not contain the answer, say exactly: "The data does not contain this information."
- Be concise. Do not use outside knowledge.
"""

_embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)
_client = chromadb.PersistentClient(path=str(REPO_ROOT / "data" / "chroma"))


def run_knowledge(question: str, where: dict | None = None) -> dict:
    """Returns {'answer': ..., 'sources': [...], 'error': ...} — never raises."""
    try:
        coll = _client.get_collection("reviews_full", embedding_function=_embed_fn)
        res = coll.query(query_texts=[question], n_results=TOP_K, where=where)
        docs = res["documents"][0]
        metas = res["metadatas"][0]
        if not docs:
            return {"answer": "The data does not contain this information.",
                    "sources": [], "error": None}

        context = "\n\n".join(
            f"[{m['parent_asin']}] {d}" for d, m in zip(docs, metas)
        )
        answer = ask_llm(SYSTEM_PROMPT, f"Context:\n{context}\n\nQuestion: {question}")
        sources = sorted({m["parent_asin"] for m in metas})
        return {"answer": answer, "sources": sources, "context": context, "error": None}
    except Exception as e:
        return {"answer": None, "sources": [], "context": "", "error": str(e)}