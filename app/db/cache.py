"""External response cache DB surface.

Second slice extracted from the legacy `app/db.py`. Stores the bodies of
stable detail fetches from Discogs / MusicBrainz / Aladin /
CoverArtArchive so:
  * steady-state outbound traffic drops to a fraction of what it was,
  * the metadata sync worker keeps making progress (using slightly stale
    data) when a provider 5xx's, and
  * repeated UI lookups feel instant.

TTL is enforced at read time — see `providers.cached_fetch_json` for the
reader-side handling of expired-but-still-useful rows.

`app/db/__init__.py` re-exports every public symbol below so existing
callers (`db.get_cached_external_response(...)`,
`from app.db import upsert_cached_external_response`) keep working.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.db import get_conn, get_write_conn  # noqa: E402  — package surface


def get_cached_external_response(cache_key: str) -> dict[str, Any] | None:
    """Return the cached row for `cache_key` or None.

    The caller is responsible for honouring `expires_at`; this helper
    returns whatever is stored so we can fall back to a stale entry when
    the upstream provider is unhealthy.
    """
    key = str(cache_key or "").strip()
    if not key:
        return None
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT cache_key, source_code, body_json, status_code,
                   fetched_at, expires_at, etag, last_modified
            FROM external_response_cache
            WHERE cache_key = ?
            LIMIT 1
            """,
            (key,),
        ).fetchone()
    if row is None:
        return None
    return dict(row)


def upsert_cached_external_response(
    *,
    cache_key: str,
    source_code: str,
    body_json: str,
    status_code: int,
    ttl_seconds: int,
    etag: str | None = None,
    last_modified: str | None = None,
) -> None:
    """Insert or replace a cached body. `body_json` is expected to already
    be a JSON-serialised string; we don't reserialize so callers can store
    raw provider payloads verbatim.
    """
    key = str(cache_key or "").strip()
    if not key:
        return
    now_dt = datetime.now(timezone.utc)
    expires_dt = now_dt + timedelta(seconds=max(0, int(ttl_seconds)))
    with get_write_conn() as conn:
        conn.execute(
            """
            INSERT INTO external_response_cache
              (cache_key, source_code, body_json, status_code,
               fetched_at, expires_at, etag, last_modified)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
              source_code = excluded.source_code,
              body_json = excluded.body_json,
              status_code = excluded.status_code,
              fetched_at = excluded.fetched_at,
              expires_at = excluded.expires_at,
              etag = excluded.etag,
              last_modified = excluded.last_modified
            """,
            (
                key,
                str(source_code or "").strip().upper() or "UNKNOWN",
                str(body_json or ""),
                int(status_code or 200),
                now_dt.isoformat(),
                expires_dt.isoformat(),
                str(etag or "").strip() or None,
                str(last_modified or "").strip() or None,
            ),
        )


def touch_cached_external_response_expiry(cache_key: str, ttl_seconds: int) -> None:
    """Refresh the `expires_at` of an existing cached row without rewriting
    its body. Useful when a provider returns 304 Not Modified."""
    key = str(cache_key or "").strip()
    if not key:
        return
    now_dt = datetime.now(timezone.utc)
    expires_dt = now_dt + timedelta(seconds=max(0, int(ttl_seconds)))
    with get_write_conn() as conn:
        conn.execute(
            """
            UPDATE external_response_cache
            SET expires_at = ?, fetched_at = ?
            WHERE cache_key = ?
            """,
            (expires_dt.isoformat(), now_dt.isoformat(), key),
        )


def purge_expired_external_responses() -> int:
    """Delete cache rows whose `expires_at` is before `now`. Returns the
    number of rows removed. Safe to call from a periodic job."""
    now_text = datetime.now(timezone.utc).isoformat()
    with get_write_conn() as conn:
        cur = conn.execute(
            "DELETE FROM external_response_cache "
            "WHERE expires_at IS NOT NULL AND expires_at < ?",
            (now_text,),
        )
        return int(cur.rowcount or 0)


__all__ = [
    "get_cached_external_response",
    "upsert_cached_external_response",
    "touch_cached_external_response_expiry",
    "purge_expired_external_responses",
]
