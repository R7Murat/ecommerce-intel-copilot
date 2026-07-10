"""Single LLM entry point: primary model with automatic fallback."""
import sys

from dotenv import load_dotenv
from litellm import completion

from copilot.config import FALLBACK_MODEL, PRIMARY_MODEL

load_dotenv()


def _call(model: str, system: str, user: str) -> str:
    resp = completion(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0,
    )
    return resp.choices[0].message.content


def ask_llm(system: str, user: str, model: str | None = None) -> str:
    """Call the LLM; on failure retry once on the fallback — loudly, not silently."""
    try:
        return _call(model or PRIMARY_MODEL, system, user)
    except Exception as e:
        print(f"[llm] primary failed ({type(e).__name__}): {e}", file=sys.stderr)
        return _call(FALLBACK_MODEL, system, user)