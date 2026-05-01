"""Pin the sixteenth slice of the db.py → app/db/ package split.

  * `app.db.album_master_tracks` exposes
    `list_album_master_track_matches` — the fuzzy track-name
    relevance lookup that the album-master admin route uses to
    populate the "관련 트랙" 힌트 panel.
  * `app.db` re-exports the public symbol so existing call sites
    (`app/api/album_masters.py`, the test suite) keep working
    unchanged.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app import db
from app.db import album_master_tracks as amt_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = ("list_album_master_track_matches",)


def test_album_master_tracks_submodule_exposes_expected_surface() -> None:
    missing = [name for name in _PUBLIC_SYMBOLS if not hasattr(amt_module, name)]
    assert not missing, f"app.db.album_master_tracks missing: {missing}"


def test_db_package_reexports_track_match_callable() -> None:
    for name in _PUBLIC_SYMBOLS:
        from_pkg = getattr(db, name, None)
        from_sub = getattr(amt_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as "
            f"db.album_master_tracks.{name}"
        )


def test_init_py_no_longer_redefines_track_match_callable() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in _PUBLIC_SYMBOLS:
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/album_master_tracks.py"
        )


def test_search_helpers_still_in_init_py() -> None:
    """`_search_token_groups` and `_matches_search_text` are used by
    half a dozen other lookups in __init__.py — they MUST stay there.
    The track-match submodule pulls them via the package surface."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    assert "def _search_token_groups(" in init_src, (
        "_search_token_groups must remain in app/db/__init__.py"
    )
    assert "def _matches_search_text(" in init_src, (
        "_matches_search_text must remain in app/db/__init__.py"
    )


def test_legacy_track_match_path_still_works() -> None:
    from app.db import list_album_master_track_matches  # noqa: F401


def test_track_matches_returns_empty_for_invalid_master() -> None:
    """Read-only contract — non-positive or unknown master ids must
    return [] regardless of the query string."""
    db.ensure_startup_db_ready()
    assert db.list_album_master_track_matches(album_master_id=0, query_text="anything") == []
    assert db.list_album_master_track_matches(album_master_id=-1, query_text="anything") == []
    assert db.list_album_master_track_matches(album_master_id=-99999, query_text="x") == []


def test_track_matches_returns_empty_for_blank_query() -> None:
    """Read-only contract — blank/whitespace queries must return []
    even when the master id is positive."""
    db.ensure_startup_db_ready()
    assert db.list_album_master_track_matches(album_master_id=1, query_text="") == []
    assert db.list_album_master_track_matches(album_master_id=1, query_text="   ") == []


def test_track_matches_round_trip_through_package_surface() -> None:
    """Insert a temp master + owned_item + music_item_detail with
    a known track_list_json/track_items_json, then verify the fuzzy
    matcher returns hits for tokens contained in the track list and
    no hits for tokens that aren't there. Cleanup at the end."""
    db.ensure_startup_db_ready()

    master_id: int | None = None
    owned_item_id: int | None = None
    try:
        with db.get_write_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO album_master
                  (source_code, source_master_id, title, artist_or_brand,
                   sort_artist_name, domain_code, release_year, raw_json,
                   created_at, updated_at)
                VALUES ('MANUAL', 'phase16-track-master',
                        'phase-16 track probe master', NULL, NULL,
                        'UNKNOWN', NULL, '{}', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            master_id = int(cur.lastrowid)

            cur = conn.execute(
                """
                INSERT INTO owned_item
                  (category, status, quantity, item_name_override,
                   size_group, created_at, updated_at)
                VALUES ('MUSIC', 'IN_COLLECTION', 1, 'phase-16 probe item',
                        'STD', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            owned_item_id = int(cur.lastrowid)

            conn.execute(
                """
                INSERT INTO album_master_member
                  (album_master_id, owned_item_id, created_at)
                VALUES (?, ?, ?)
                """,
                (master_id, owned_item_id, db.utc_now_iso()),
            )

            track_list = ["Phase Sixteen Probe Song", "Hidden Phase Sixteen Lullaby"]
            track_items = [
                {"display": "Phase Sixteen Probe Song", "title": "Phase Sixteen Probe Song"},
                {"display": "Phase Sixteen Encore Variation", "title": "Phase Sixteen Encore Variation"},
            ]
            conn.execute(
                """
                INSERT INTO music_item_detail
                  (owned_item_id, format_name, track_list_json, track_items_json,
                   created_at, updated_at)
                VALUES (?, 'CD', ?, ?, ?, ?)
                """,
                (
                    owned_item_id,
                    json.dumps(track_list, ensure_ascii=True),
                    json.dumps(track_items, ensure_ascii=True),
                    db.utc_now_iso(),
                    db.utc_now_iso(),
                ),
            )

        # Token "Lullaby" should hit the second track in track_list.
        hits = db.list_album_master_track_matches(master_id, "Lullaby", limit=5)
        assert "Hidden Phase Sixteen Lullaby" in hits

        # Token "Encore" should hit the second track_item display name.
        hits_encore = db.list_album_master_track_matches(master_id, "Encore", limit=5)
        assert "Phase Sixteen Encore Variation" in hits_encore

        # Token that's not in any track must return [].
        hits_miss = db.list_album_master_track_matches(master_id, "ZZNOMATCHZZ", limit=5)
        assert hits_miss == []

        # Limit must be respected — request 1, get at most 1 even when
        # multiple tracks could match.
        hits_one = db.list_album_master_track_matches(master_id, "Phase", limit=1)
        assert len(hits_one) <= 1
    finally:
        with db.get_write_conn() as conn:
            if owned_item_id is not None:
                conn.execute("DELETE FROM music_item_detail WHERE owned_item_id = ?", (owned_item_id,))
                conn.execute("DELETE FROM album_master_member WHERE owned_item_id = ?", (owned_item_id,))
                conn.execute("DELETE FROM owned_item WHERE id = ?", (owned_item_id,))
            if master_id is not None:
                conn.execute("DELETE FROM album_master_member WHERE album_master_id = ?", (master_id,))
                conn.execute("DELETE FROM album_master WHERE id = ?", (master_id,))


def test_track_matches_handles_corrupt_json_gracefully() -> None:
    """Defensive contract — track_list_json / track_items_json that
    aren't valid JSON (or aren't lists) must be silently treated as
    empty, NOT raise."""
    db.ensure_startup_db_ready()

    master_id: int | None = None
    owned_item_id: int | None = None
    try:
        with db.get_write_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO album_master
                  (source_code, source_master_id, title, artist_or_brand,
                   sort_artist_name, domain_code, release_year, raw_json,
                   created_at, updated_at)
                VALUES ('MANUAL', 'phase16-corrupt-master',
                        'phase-16 corrupt-json probe', NULL, NULL,
                        'UNKNOWN', NULL, '{}', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            master_id = int(cur.lastrowid)

            cur = conn.execute(
                """
                INSERT INTO owned_item
                  (category, status, quantity, item_name_override,
                   size_group, created_at, updated_at)
                VALUES ('MUSIC', 'IN_COLLECTION', 1, 'phase-16 corrupt probe',
                        'STD', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            owned_item_id = int(cur.lastrowid)

            conn.execute(
                """
                INSERT INTO album_master_member
                  (album_master_id, owned_item_id, created_at)
                VALUES (?, ?, ?)
                """,
                (master_id, owned_item_id, db.utc_now_iso()),
            )

            conn.execute(
                """
                INSERT INTO music_item_detail
                  (owned_item_id, format_name, track_list_json, track_items_json,
                   created_at, updated_at)
                VALUES (?, 'CD', '{not valid json', 'also not json',
                        ?, ?)
                """,
                (owned_item_id, db.utc_now_iso(), db.utc_now_iso()),
            )

        # No raise — just an empty result.
        result = db.list_album_master_track_matches(master_id, "anything", limit=5)
        assert result == []
    finally:
        with db.get_write_conn() as conn:
            if owned_item_id is not None:
                conn.execute("DELETE FROM music_item_detail WHERE owned_item_id = ?", (owned_item_id,))
                conn.execute("DELETE FROM album_master_member WHERE owned_item_id = ?", (owned_item_id,))
                conn.execute("DELETE FROM owned_item WHERE id = ?", (owned_item_id,))
            if master_id is not None:
                conn.execute("DELETE FROM album_master_member WHERE album_master_id = ?", (master_id,))
                conn.execute("DELETE FROM album_master WHERE id = ?", (master_id,))
