"""SQL Analyst agent: natural language -> guarded SQL -> read-only execution."""
import sqlite3

from copilot.config import DB_URI, SCHEMA_DESCRIPTION
from copilot.llm import ask_llm
from copilot.tools.sql_guard import GuardError, validate_sql

SYSTEM_PROMPT = f"""You are a SQL analyst for a SQLite database.
{SCHEMA_DESCRIPTION}
Rules:
- Output ONLY the SQL statement. No markdown fences, no explanation.
- One single SELECT statement. Never modify data.
- Prefer explicit column lists over SELECT *.
"""


def _clean(raw: str) -> str:
    """Strip markdown fences the LLM sometimes adds despite instructions."""
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        s = s.rsplit("```", 1)[0]
    return s.strip()


def run_sql_analyst(question: str) -> dict:
    """Returns {'query': ..., 'rows': ..., 'error': ...} — never raises."""
    raw = ask_llm(SYSTEM_PROMPT, question)
    try:
        safe_sql = validate_sql(_clean(raw))
    except GuardError as e:
        return {"query": raw, "rows": None, "error": f"guard rejected: {e}"}

    try:
        conn = sqlite3.connect(DB_URI, uri=True)
        rows = conn.execute(safe_sql).fetchall()
        conn.close()
        return {"query": safe_sql, "rows": rows, "error": None}
    except sqlite3.Error as e:
        # one self-correction attempt: show the LLM its error
        retry_raw = ask_llm(
            SYSTEM_PROMPT,
            f"{question}\n\nYour previous SQL failed:\n{safe_sql}\nError: {e}\nFix it.",
        )
        try:
            safe_retry = validate_sql(_clean(retry_raw))
            conn = sqlite3.connect(DB_URI, uri=True)
            rows = conn.execute(safe_retry).fetchall()
            conn.close()
            return {"query": safe_retry, "rows": rows, "error": None}
        except (GuardError, sqlite3.Error) as e2:
            return {"query": retry_raw, "rows": None, "error": str(e2)}