"""Tiny disk cache: question hash -> final answer. Eval runs must bypass this."""
import hashlib
import json

from copilot.config import REPO_ROOT

CACHE_PATH = REPO_ROOT / "data" / "answer_cache.json"


def _key(question: str) -> str:
    return hashlib.sha256(question.strip().lower().encode()).hexdigest()[:16]


def get(question: str) -> str | None:
    if not CACHE_PATH.exists():
        return None
    return json.loads(CACHE_PATH.read_text(encoding="utf-8")).get(_key(question))


def put(question: str, answer: str) -> None:
    data = {}
    if CACHE_PATH.exists():
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    data[_key(question)] = answer
    CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")