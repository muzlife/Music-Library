from __future__ import annotations

import sqlite3
from typing import Any

from .connection import utc_now_iso


def get_masters_without_review(conn: sqlite3.Connection, limit: int) -> list[dict[str, Any]]:
    """review_text IS NULL인 album_master 행을 limit건 반환."""
    rows = conn.execute(
        """
        SELECT id, artist_or_brand, title
        FROM album_master
        WHERE review_text IS NULL OR TRIM(review_text) = ''
        ORDER BY id
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def save_review(
    conn: sqlite3.Connection,
    master_id: int,
    review_text: str,
    review_source: str,
    review_url: str | None,
) -> None:
    """review_text, review_source, review_url, updated_at을 업데이트."""
    conn.execute(
        """
        UPDATE album_master
        SET review_text = ?, review_source = ?, review_url = ?, updated_at = ?
        WHERE id = ?
        """,
        (review_text, review_source, review_url, utc_now_iso(), master_id),
    )
    conn.commit()


def clear_review(conn: sqlite3.Connection, master_id: int) -> None:
    """review 3개 컬럼을 NULL로 초기화."""
    conn.execute(
        """
        UPDATE album_master
        SET review_text = NULL, review_source = NULL, review_url = NULL, updated_at = ?
        WHERE id = ?
        """,
        (utc_now_iso(), master_id),
    )
    conn.commit()


def count_masters_without_review(conn: sqlite3.Connection) -> int:
    """review_text가 없는 마스터 건수 반환."""
    row = conn.execute(
        """
        SELECT COUNT(*) FROM album_master
        WHERE review_text IS NULL OR TRIM(review_text) = ''
        """
    ).fetchone()
    return row[0] if row else 0
