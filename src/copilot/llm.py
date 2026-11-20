"""Single LLM entry point: primary model with automatic fallback."""
import sys
from urllib.parse import urlparse

from dotenv import load_dotenv
from litellm import completion

from copilot.config import API_BASE, FALLBACK_MODEL, PRIMARY_MODEL, PROFILE
from copilot.observability import set_attrs, span

load_dotenv()


def _list_price(resp) -> float | None:
    """Provider list price in USD (free tiers bill 0); None when litellm has no price.

    litellm computes it at call time with the request's provider; recomputing from
    resp.model fails on Groq because the response drops the "groq/" prefix.
    """
    cost = (getattr(resp, "_hidden_params", None) or {}).get("response_cost")
    return float(cost) if cost is not None else None


def _call(model: str, system: str, user: str, is_fallback: bool) -> str:
    with span("chat", model):
        set_attrs({
            "gen_ai.request.model": model,
            "copilot.profile": PROFILE,
            "copilot.fallback": is_fallback,
            "server.address": urlparse(API_BASE).hostname if API_BASE else None,
        })
        resp = completion(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0,
            api_base=API_BASE,  # None in cloud profile: provider default
        )
        usage = getattr(resp, "usage", None)
        price = _list_price(resp)
        set_attrs({
            "gen_ai.response.model": getattr(resp, "model", None),
            "gen_ai.usage.input_tokens": getattr(usage, "prompt_tokens", None),
            "gen_ai.usage.output_tokens": getattr(usage, "completion_tokens", None),
            "copilot.cost_usd_list_price": price,
            "gen_ai.usage.cost": price,  # read by Langfuse as cost; still list price, not billed
        })
        return resp.choices[0].message.content


def ask_llm(system: str, user: str, model: str | None = None) -> str:
    """Call the LLM; on failure retry once on the fallback — loudly, not silently."""
    try:
        return _call(model or PRIMARY_MODEL, system, user, is_fallback=False)
    except Exception as e:
        print(f"[llm] primary failed ({type(e).__name__}): {e}", file=sys.stderr)
        if not FALLBACK_MODEL:  # local profile: no fallback, fail closed
            raise
        return _call(FALLBACK_MODEL, system, user, is_fallback=True)
