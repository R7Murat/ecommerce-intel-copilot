"""Deterministic analytics over the reviews database. No LLM involvement."""
import sqlite3


def rating_trend(conn: sqlite3.Connection, parent_asin: str) -> list[tuple]:
    """Yearly (year, avg_rating, review_count) for one product."""
    return [
        (y, round(avg, 2), n)
        for y, avg, n in conn.execute(
            """SELECT strftime('%Y', ts, 'unixepoch') AS y, AVG(rating), COUNT(*)
               FROM reviews WHERE parent_asin = ? GROUP BY y ORDER BY y""",
            (parent_asin,),
        )
    ]


def review_volume(conn: sqlite3.Connection, parent_asin: str | None = None) -> list[tuple]:
    """Yearly (year, count), for one product or the whole corpus."""
    if parent_asin:
        q = """SELECT strftime('%Y', ts, 'unixepoch') AS y, COUNT(*)
               FROM reviews WHERE parent_asin = ? GROUP BY y ORDER BY y"""
        return conn.execute(q, (parent_asin,)).fetchall()
    q = """SELECT strftime('%Y', ts, 'unixepoch') AS y, COUNT(*)
           FROM reviews GROUP BY y ORDER BY y"""
    return conn.execute(q).fetchall()


def sentiment_summary(conn: sqlite3.Connection, parent_asin: str) -> dict:
    """Rating distribution and verified-purchase ratio for one product."""
    dist = dict(conn.execute(
        "SELECT rating, COUNT(*) FROM reviews WHERE parent_asin = ? GROUP BY rating",
        (parent_asin,),
    ).fetchall())
    ratio = conn.execute(
        "SELECT ROUND(AVG(verified), 3) FROM reviews WHERE parent_asin = ?",
        (parent_asin,),
    ).fetchone()[0]
    return {"distribution": dist, "verified_ratio": ratio}


def top_movers(conn: sqlite3.Connection, n: int = 5) -> list[tuple]:
    """Products with the largest rating change between their first and last year.
    Returns (parent_asin, first_year_avg, last_year_avg, change), sorted by |change|."""
    rows = conn.execute(
        """WITH yearly AS (
               SELECT parent_asin, strftime('%Y', ts, 'unixepoch') AS y,
                      AVG(rating) AS avg_r
               FROM reviews GROUP BY parent_asin, y
           ),
           bounds AS (
               SELECT parent_asin, MIN(y) AS first_y, MAX(y) AS last_y
               FROM yearly GROUP BY parent_asin HAVING first_y != last_y
           )
           SELECT b.parent_asin,
                  ROUND(f.avg_r, 2), ROUND(l.avg_r, 2),
                  ROUND(l.avg_r - f.avg_r, 2) AS change
           FROM bounds b
           JOIN yearly f ON f.parent_asin = b.parent_asin AND f.y = b.first_y
           JOIN yearly l ON l.parent_asin = b.parent_asin AND l.y = b.last_y
           ORDER BY ABS(change) DESC LIMIT ?""",
        (n,),
    ).fetchall()
    return rows