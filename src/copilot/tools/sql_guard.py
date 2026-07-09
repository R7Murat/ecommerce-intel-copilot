"""SQL safety guard: only plain, single, capped SELECT statements pass."""
import re

ROW_CAP = 50

FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|PRAGMA|ATTACH)\b",
    re.IGNORECASE,
)


class GuardError(Exception):
    """Raised when a SQL statement violates the guard rules."""


def validate_sql(sql: str) -> str:
    """Validate and normalize a SQL statement. Returns the safe statement or raises."""
    stmt = sql.strip().rstrip(";")

    # Rule 1: multi-statement injection ("SELECT 1; DROP ...")
    if ";" in stmt:
        raise GuardError("multiple statements are not allowed")

    # Rule 2: must be a SELECT
    if not stmt.upper().startswith("SELECT"):
        raise GuardError("only SELECT statements are allowed")

    # Rule 3: no destructive keywords anywhere in the statement
    if FORBIDDEN.search(stmt):
        raise GuardError("forbidden keyword detected")

    # Rule 4: enforce a row cap
    if not re.search(r"\bLIMIT\b", stmt, re.IGNORECASE):
        stmt += f" LIMIT {ROW_CAP}"

    return stmt