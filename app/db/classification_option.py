"""Classification option DB surface.

Eighth slice extracted from the legacy `app/db.py`. Owns the
`classification_option` table — the lookup that backs SUBTYPE / SOUNDTRACK
chips on the registration screen. Tiny domain (3 functions, only
`get_conn` and `utc_now_iso` from the package surface).

Public exports
  * list_classification_options
  * upsert_classification_option

Module-private exports (re-exported from `app.db.__init__` so the
init/seed chain finds it by bare name)
  * _seed_classification_options

`app/db/__init__.py` re-exports every symbol below so existing call
sites (the registration UI router, init/migration chain) keep working
unchanged.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from app.db import get_conn, utc_now_iso  # noqa: E402  — package surface


def _seed_classification_options(conn: sqlite3.Connection) -> None:
    now = utc_now_iso()
    rows = [
        ("SUBTYPE", "박스셋", 10, 1, now, now),
        ("SUBTYPE", "한정판", 20, 1, now, now),
        ("SUBTYPE", "컴필레이션", 30, 1, now, now),
        ("SUBTYPE", "언플러그드", 40, 1, now, now),
        ("SUBTYPE", "리메이크", 50, 1, now, now),
        ("SUBTYPE", "헌정", 60, 1, now, now),
        ("SUBTYPE", "옴니버스", 70, 1, now, now),
        ("SUBTYPE", "데모", 80, 1, now, now),
        ("SUBTYPE", "동요", 90, 1, now, now),
        ("SOUNDTRACK", "드라마", 10, 1, now, now),
        ("SOUNDTRACK", "영화", 20, 1, now, now),
        ("SOUNDTRACK", "애니메이션", 30, 1, now, now),
        ("SOUNDTRACK", "뮤지컬", 40, 1, now, now),
        ("SOUNDTRACK", "연극", 50, 1, now, now),
        ("SOUNDTRACK", "게임", 60, 1, now, now),
    ]
    conn.executemany(
        """
        INSERT INTO classification_option
          (option_group, label, sort_order, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(option_group, label) DO UPDATE SET
          sort_order = excluded.sort_order,
          is_active = 1,
          updated_at = excluded.updated_at
        """,
        rows,
    )


def list_classification_options(option_group: str, include_inactive: bool = False) -> list[dict[str, Any]]:
    query = """
      SELECT id, option_group, label, sort_order, is_active
      FROM classification_option
      WHERE option_group = ?
    """
    params: list[Any] = [option_group]
    if not include_inactive:
        query += " AND is_active = 1"
    query += " ORDER BY sort_order ASC, label ASC, id ASC"

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def upsert_classification_option(option_group: str, label: str, sort_order: int = 100) -> dict[str, Any]:
    now = utc_now_iso()
    clean_label = str(label or "").strip()
    if not clean_label:
        raise ValueError("label is required")

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO classification_option
              (option_group, label, sort_order, is_active, created_at, updated_at)
            VALUES (?, ?, ?, 1, ?, ?)
            ON CONFLICT(option_group, label) DO UPDATE SET
              sort_order = excluded.sort_order,
              is_active = 1,
              updated_at = excluded.updated_at
            """,
            (option_group, clean_label, int(sort_order), now, now),
        )
        row = conn.execute(
            """
            SELECT id, option_group, label, sort_order, is_active
            FROM classification_option
            WHERE option_group = ? AND label = ?
            LIMIT 1
            """,
            (option_group, clean_label),
        ).fetchone()
    if row is None:
        raise RuntimeError("classification option upsert failed")
    return dict(row)


__all__ = [
    "_seed_classification_options",
    "list_classification_options",
    "upsert_classification_option",
]
