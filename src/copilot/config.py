"""Central configuration: models, paths, schema description."""
import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()  # must run before any os.getenv below

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "data" / "products.db"
DB_URI = f"file:{DB_PATH}?mode=ro"

# Profile selects provider defaults; PRIMARY_MODEL / FALLBACK_MODEL in .env override them.
PROFILES = {
    "cloud": {"primary": "groq/openai/gpt-oss-20b", "fallback": "gemini/gemini-2.5-flash",
              "api_base": None},
    # local: no fallback, since any fallback would leave the machine
    "local": {"primary": "ollama_chat/gpt-oss:20b", "fallback": "",
              "api_base": "http://localhost:11434"},
}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
LOCAL_MODEL_PREFIXES = ("ollama/", "ollama_chat/")

PROFILE = os.getenv("COPILOT_PROFILE", "cloud").strip().lower()
if PROFILE not in PROFILES:
    raise ValueError(f"COPILOT_PROFILE must be one of {sorted(PROFILES)}, got {PROFILE!r}")
_p = PROFILES[PROFILE]
PRIMARY_MODEL = os.getenv("PRIMARY_MODEL", _p["primary"])
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", _p["fallback"])
API_BASE = os.getenv("OLLAMA_API_BASE", _p["api_base"]) if PROFILE == "local" else None
# gpt-oss reasoning level for the primary model (D10); empty = provider default
REASONING_EFFORT = os.getenv("REASONING_EFFORT", "low").strip().lower() or None
if REASONING_EFFORT not in {None, "low", "medium", "high"}:
    raise ValueError(f"REASONING_EFFORT must be low, medium or high, got {REASONING_EFFORT!r}")


def check_local_profile(primary: str, fallback: str, api_base: str | None,
                        no_cloud: str | None) -> None:
    """Fail closed: raise unless every local-profile call stays on this machine."""
    problems = []
    if no_cloud != "1":
        problems.append("OLLAMA_NO_CLOUD must be 1")
    host = urlparse(api_base or "").hostname
    if host not in LOCAL_HOSTS:
        problems.append(f"api_base host must be local, got {host!r}")
    if not primary.startswith(LOCAL_MODEL_PREFIXES):
        problems.append(f"primary model must be an Ollama model, got {primary!r}")
    if primary.endswith("-cloud"):
        problems.append(f"cloud-offloaded model not allowed: {primary!r}")
    if fallback:
        problems.append(f"fallback must be empty in local profile, got {fallback!r}")
    if problems:
        raise RuntimeError("local profile refused: " + "; ".join(problems))


if PROFILE == "local":
    check_local_profile(PRIMARY_MODEL, FALLBACK_MODEL, API_BASE, os.getenv("OLLAMA_NO_CLOUD"))

SCHEMA_DESCRIPTION = """
Tables:
  products(parent_asin TEXT PK, title TEXT, store TEXT, main_category TEXT,
           price REAL nullable, average_rating REAL, rating_number INTEGER,
           details_json TEXT)
  reviews(review_id INTEGER PK, parent_asin TEXT FK->products, rating REAL,
          title TEXT, text TEXT, helpful_vote INTEGER, verified INTEGER 0/1,
          ts INTEGER epoch seconds)
Notes:
  - price is NULL for ~23% of products; filter with IS NOT NULL when averaging.
  - Use strftime('%Y', ts, 'unixepoch') for year extraction.
"""