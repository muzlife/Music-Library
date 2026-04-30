"""Album master operator-correction DB surface.

Thirteenth slice extracted from the legacy `app/db.py`. Owns the
"운영자 수동 보정" (manual correction) layer on `album_master` —
the operator can override `release_year` and `domain_code` when
provider metadata is wrong, and we keep the original provider
values in the `source_release_year` / `source_domain_code` columns
so we can revert later.

Public exports
  * get_album_master_correction_state — read-only snapshot of the
    effective values + source values + override values + a derived
    `has_manual_correction` flag for the operator UI.
  * update_album_master_correction — write the override columns;
    when an override is None, the effective value falls back to the
    stored source value. Returns the resulting `correction_state`
    or None if the master id doesn't exist.

Cross-package dependencies kept on the package surface
  * `_normalize_domain_code_value` is used 25+ times across the
    package and stays in `app/db/__init__.py`. The submodule pulls
    it in via the package surface.

`app/db/__init__.py` re-exports both public functions so existing
callers (the `/admin/album-masters/{id}/correction` route in
`app/api/album_masters.py`, the test suite) keep working
unchanged.
"""

from __future__ import annotations

from typing import Any

from app.db import (  # noqa: E402  — package surface
    _normalize_domain_code_value,
    get_conn,
    utc_now_iso,
)


def get_album_master_correction_state(album_master_id: int) -> dict[str, Any] | None:
    master_id = int(album_master_id or 0)
    if master_id <= 0:
        return None
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT
              id,
              release_year,
              domain_code,
              source_release_year,
              source_domain_code,
              override_release_year,
              override_domain_code,
              override_note
            FROM album_master
            WHERE id = ?
            LIMIT 1
            """,
            (master_id,),
        ).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["domain_code"] = _normalize_domain_code_value(data.get("domain_code"))
    data["source_domain_code"] = _normalize_domain_code_value(data.get("source_domain_code")) or data["domain_code"]
    data["override_domain_code"] = _normalize_domain_code_value(data.get("override_domain_code"))
    data["source_release_year"] = (
        int(data["source_release_year"]) if data.get("source_release_year") not in (None, "") else data.get("release_year")
    )
    data["override_release_year"] = (
        int(data["override_release_year"]) if data.get("override_release_year") not in (None, "") else None
    )
    data["release_year"] = int(data["release_year"]) if data.get("release_year") not in (None, "") else None
    data["override_note"] = str(data.get("override_note") or "").strip() or None
    data["has_manual_correction"] = bool(
        data.get("override_release_year") is not None
        or data.get("override_domain_code")
        or data.get("override_note")
    )
    return data


def update_album_master_correction(
    album_master_id: int,
    *,
    release_year: int | None,
    domain_code: str | None,
    override_note: str | None,
) -> dict[str, Any] | None:
    master_id = int(album_master_id or 0)
    if master_id <= 0:
        return None
    normalized_domain_code = _normalize_domain_code_value(domain_code)
    normalized_note = str(override_note or "").strip() or None
    release_year_value = int(release_year) if release_year is not None else None
    now = utc_now_iso()

    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT
              id,
              release_year,
              domain_code,
              source_release_year,
              source_domain_code
            FROM album_master
            WHERE id = ?
            LIMIT 1
            """,
            (master_id,),
        ).fetchone()
        if row is None:
            return None
        current = dict(row)
        source_release_year = (
            int(current["source_release_year"])
            if current.get("source_release_year") not in (None, "")
            else (int(current["release_year"]) if current.get("release_year") not in (None, "") else None)
        )
        source_domain_code = _normalize_domain_code_value(current.get("source_domain_code")) or _normalize_domain_code_value(
            current.get("domain_code")
        )
        effective_release_year = release_year_value if release_year_value is not None else source_release_year
        effective_domain_code = normalized_domain_code if normalized_domain_code else source_domain_code

        cur = conn.execute(
            """
            UPDATE album_master
            SET release_year = ?,
                domain_code = ?,
                source_release_year = ?,
                source_domain_code = ?,
                override_release_year = ?,
                override_domain_code = ?,
                override_note = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                effective_release_year,
                effective_domain_code,
                source_release_year,
                source_domain_code,
                release_year_value,
                normalized_domain_code,
                normalized_note,
                now,
                master_id,
            ),
        )
        if int(cur.rowcount or 0) <= 0:
            return None

    return get_album_master_correction_state(master_id)


__all__ = [
    "get_album_master_correction_state",
    "update_album_master_correction",
]
