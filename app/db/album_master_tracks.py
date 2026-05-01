"""Album master track-match search DB surface.

Sixteenth slice extracted from the legacy `app/db.py`. Owns the
fuzzy "이 마스터의 멤버 음반들에서 이 검색어와 매치되는 트랙
이름 찾기" lookup that the album-master admin route uses to power
the "관련 트랙" 힌트 panel — small, single function, but
gnarly enough (track_list_json + track_items_json defensive parse,
search-token group matching) to deserve its own home.

Public exports
  * list_album_master_track_matches — given a master id and a
    free-form `query_text`, return up to `limit` track titles from
    its bound owned_items' music_item_detail rows that fuzzy-match
    the query.

Cross-package dependencies kept on the package surface
  * `_search_token_groups` and `_matches_search_text` are the search
    helpers used by half a dozen other lookups in `app/db/__init__.py`.
    They stay in __init__.py and the submodule pulls them via the
    package surface.

`app/db/__init__.py` re-exports the public function so existing
callers (`app/api/album_masters.py`'s relevance-search path, the
test suite) keep working unchanged.
"""

from __future__ import annotations

import json
from typing import Any

from app.db import (  # noqa: E402  — package surface
    _matches_search_text,
    _search_token_groups,
    get_conn,
)


def list_album_master_track_matches(album_master_id: int, query_text: str, limit: int = 3) -> list[str]:
    master_id = int(album_master_id or 0)
    clean_query = str(query_text or "").strip()
    if master_id <= 0 or not clean_query:
        return []

    token_groups = _search_token_groups(clean_query)
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
              mid.track_list_json,
              mid.track_items_json
            FROM album_master_member amm
            JOIN music_item_detail mid ON mid.owned_item_id = amm.owned_item_id
            WHERE amm.album_master_id = ?
            ORDER BY amm.id ASC
            """,
            (master_id,),
        ).fetchall()

    matches: list[str] = []
    seen: set[str] = set()

    def _push(value: Any) -> None:
        text = str(value or "").strip()
        key = text.lower()
        if not text or key in seen:
            return
        if not _matches_search_text(text, clean_query, token_groups):
            return
        seen.add(key)
        matches.append(text)

    def _parse_json_string_list(raw: Any) -> list[str]:
        if not raw:
            return []
        try:
            parsed = json.loads(str(raw))
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        return [str(v).strip() for v in parsed if str(v).strip()]

    def _parse_json_dict_list(raw: Any) -> list[dict[str, Any]]:
        if not raw:
            return []
        try:
            parsed = json.loads(str(raw))
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        return [row for row in parsed if isinstance(row, dict)]

    for row in rows:
        track_list = _parse_json_string_list(row["track_list_json"])
        track_items = _parse_json_dict_list(row["track_items_json"])
        for track in track_list:
            _push(track)
        for item in track_items:
            if not isinstance(item, dict):
                continue
            _push(item.get("display"))
            _push(item.get("title"))
        if len(matches) >= max(1, int(limit)):
            break

    return matches[: max(1, int(limit))]


__all__ = [
    "list_album_master_track_matches",
]
