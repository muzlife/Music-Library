import pytest
import sqlite3
from app.db.album_master_review import (
    get_masters_without_review,
    save_review,
    clear_review,
    count_masters_without_review,
)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("""
        CREATE TABLE album_master (
            id INTEGER PRIMARY KEY,
            artist_or_brand TEXT,
            title TEXT,
            release_year INTEGER,
            review_text TEXT,
            review_source TEXT,
            review_url TEXT,
            updated_at TEXT
        )
    """)
    c.executemany(
        "INSERT INTO album_master (id, artist_or_brand, title) VALUES (?, ?, ?)",
        [(1, "Artist A", "Album One"), (2, "Artist B", "Album Two")],
    )
    c.commit()
    yield c
    c.close()


def test_count_masters_without_review(conn):
    assert count_masters_without_review(conn) == 2


def test_get_masters_without_review_returns_up_to_limit(conn):
    rows = get_masters_without_review(conn, limit=1)
    assert len(rows) == 1
    assert rows[0]["id"] in (1, 2)


def test_save_review(conn):
    save_review(conn, 1, "한국어 요약", "WIKIPEDIA", "https://en.wikipedia.org/wiki/Album_One")
    row = conn.execute("SELECT review_text, review_source, review_url FROM album_master WHERE id=1").fetchone()
    assert row["review_text"] == "한국어 요약"
    assert row["review_source"] == "WIKIPEDIA"
    assert row["review_url"] == "https://en.wikipedia.org/wiki/Album_One"


def test_save_review_with_null_url(conn):
    save_review(conn, 1, "직접 입력한 리뷰", "MANUAL", None)
    row = conn.execute("SELECT review_url FROM album_master WHERE id=1").fetchone()
    assert row["review_url"] is None


def test_clear_review(conn):
    save_review(conn, 1, "요약", "WIKIPEDIA", "https://url")
    clear_review(conn, 1)
    row = conn.execute("SELECT review_text FROM album_master WHERE id=1").fetchone()
    assert row["review_text"] is None


def test_masters_without_review_excludes_existing(conn):
    save_review(conn, 1, "요약", "WIKIPEDIA", None)
    rows = get_masters_without_review(conn, limit=10)
    ids = [r["id"] for r in rows]
    assert 1 not in ids
    assert 2 in ids
    assert count_masters_without_review(conn) == 1
