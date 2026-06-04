from __future__ import annotations

from typing import Any

from app.db import _normalize_domain_code_value, get_conn, utc_now_iso


def _label_key(label_name: Any) -> str:
    return str(label_name or "").strip().lower()


def lookup_label_domain(label_name: Any) -> str | None:
    key = _label_key(label_name)
    if not key:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT domain_code FROM label_domain_registry WHERE label_name_key = ? LIMIT 1",
            (key,),
        ).fetchone()
    if row is None:
        return None
    return _normalize_domain_code_value(row["domain_code"])


def upsert_label_domain(label_name: Any, domain_code: Any) -> None:
    key = _label_key(label_name)
    domain = _normalize_domain_code_value(domain_code)
    if not key or not domain:
        return
    now = utc_now_iso()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO label_domain_registry
              (label_name_key, label_name, domain_code, confirmed_count, created_at, updated_at)
            VALUES (?, ?, ?, 1, ?, ?)
            ON CONFLICT(label_name_key) DO UPDATE SET
              domain_code     = excluded.domain_code,
              confirmed_count = confirmed_count + 1,
              updated_at      = excluded.updated_at
            """,
            (key, str(label_name).strip(), domain, now, now),
        )


__all__ = ["lookup_label_domain", "upsert_label_domain"]
