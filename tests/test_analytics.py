"""Analytics tools must return exact, deterministic numbers on a known fixture."""
import sqlite3

import pytest

from copilot.tools.analytics import rating_trend, review_volume, sentiment_summary, top_movers


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.executescript("""
        CREATE TABLE products (parent_asin TEXT PRIMARY KEY, title TEXT,
                               average_rating REAL, rating_number INTEGER);
        CREATE TABLE reviews (review_id INTEGER PRIMARY KEY, parent_asin TEXT,
                              rating REAL, verified INTEGER, ts INTEGER);
    """)
    c.execute("INSERT INTO products VALUES ('A1', 'Widget', 4.0, 6)")
    c.execute("INSERT INTO products VALUES ('A2', 'Gadget', 3.0, 4)")
    rows = [
        # A1: 2021 -> ratings 5,5 (avg 5.0) ; 2022 -> 3,3,3,3 (avg 3.0)  => falling
        ("A1", 5.0, 1, 1609459200), ("A1", 5.0, 1, 1612137600),
        ("A1", 3.0, 1, 1641038400), ("A1", 3.0, 0, 1643716800),
        ("A1", 3.0, 1, 1646092800), ("A1", 3.0, 1, 1648771200),
        # A2: 2021 -> 3,3 (avg 3.0) ; 2022 -> 4,4 (avg 4.0)  => rising
        ("A2", 3.0, 1, 1609459200), ("A2", 3.0, 1, 1612137600),
        ("A2", 4.0, 0, 1641038400), ("A2", 4.0, 1, 1643716800),
    ]
    c.executemany("INSERT INTO reviews (parent_asin, rating, verified, ts) VALUES (?,?,?,?)", rows)
    return c


def test_rating_trend_yearly_averages(conn):
    t = rating_trend(conn, "A1")
    assert t == [("2021", 5.0, 2), ("2022", 3.0, 4)]


def test_review_volume_by_year(conn):
    v = review_volume(conn)
    assert v == [("2021", 4), ("2022", 6)]


def test_sentiment_summary_distribution_and_verified(conn):
    s = sentiment_summary(conn, "A1")
    assert s["distribution"] == {3.0: 4, 5.0: 2}
    assert s["verified_ratio"] == round(5 / 6, 3)


def test_top_movers_direction_and_magnitude(conn):
    m = top_movers(conn, n=2)
    # A1 fell 2.0 points, A2 rose 1.0 -> A1 first by absolute change
    assert m[0][0] == "A1" and m[0][3] == -2.0
    assert m[1][0] == "A2" and m[1][3] == 1.0