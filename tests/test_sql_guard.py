"""Guard must reject anything that is not a plain, single SELECT."""
import pytest

from copilot.tools.sql_guard import GuardError, validate_sql


DESTRUCTIVE = [
    "DROP TABLE products",
    "DELETE FROM reviews",
    "UPDATE products SET price = 0",
    "INSERT INTO reviews VALUES (1)",
    "ALTER TABLE products ADD COLUMN x",
    "PRAGMA writable_schema = ON",
    "ATTACH DATABASE 'evil.db' AS evil",
]


@pytest.mark.parametrize("sql", DESTRUCTIVE)
def test_destructive_statements_rejected(sql):
    with pytest.raises(GuardError):
        validate_sql(sql)


def test_multi_statement_rejected():
    with pytest.raises(GuardError):
        validate_sql("SELECT 1; DROP TABLE products")


def test_sneaky_case_and_whitespace_rejected():
    with pytest.raises(GuardError):
        validate_sql("  dRoP   TABLE products")


def test_plain_select_passes():
    assert validate_sql("SELECT title FROM products LIMIT 5") is not None


def test_select_gets_row_cap():
    out = validate_sql("SELECT title FROM products")
    assert "LIMIT" in out.upper()