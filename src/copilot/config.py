"""Central configuration: models, paths, schema description."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # must run before any os.getenv below

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "data" / "products.db"
DB_URI = f"file:{DB_PATH}?mode=ro"

# Override via PRIMARY_MODEL / FALLBACK_MODEL in .env (litellm model IDs).
PRIMARY_MODEL = os.getenv("PRIMARY_MODEL", "groq/openai/gpt-oss-20b")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "gemini/gemini-2.5-flash")

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