"""Pin the fifteenth slice of the db.py → app/db/ package split.

  * `app.db.album_master_member` exposes the member-management surface
    on `album_master_member` plus the related single-master
    writes/reads — `bind_album_master_members`, `album_master_exists`,
    `update_album_master_sort_artist_name`, `list_album_master_members`,
    `delete_album_master`.
  * `app.db` re-exports every public symbol so existing call sites
    (the album-master admin routes, the metadata sync that calls
    `bind_album_master_members`, the test suite) keep working
    unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import album_master_member as amm_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = (
    "bind_album_master_members",
    "album_master_exists",
    "update_album_master_sort_artist_name",
    "list_album_master_members",
    "delete_album_master",
)


def test_album_master_member_submodule_exposes_expected_surface() -> None:
    missing = [name for name in _PUBLIC_SYMBOLS if not hasattr(amm_module, name)]
    assert not missing, f"app.db.album_master_member missing: {missing}"


def test_db_package_reexports_album_master_member_callables() -> None:
    for name in _PUBLIC_SYMBOLS:
        from_pkg = getattr(db, name, None)
        from_sub = getattr(amm_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as "
            f"db.album_master_member.{name}"
        )


def test_init_py_no_longer_redefines_member_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in _PUBLIC_SYMBOLS:
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/album_master_member.py"
        )


def test_sync_domain_code_helper_still_in_init_py() -> None:
    """`_sync_album_master_domain_code_in_conn` is shared with the
    promote / normalise / merge writers and a legacy migration path
    that all stay in __init__.py. The bind path here imports it from
    the package surface."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    assert "def _sync_album_master_domain_code_in_conn(" in init_src, (
        "_sync_album_master_domain_code_in_conn must remain in "
        "app/db/__init__.py — it's used by promote/normalise/merge "
        "writers that haven't been moved yet"
    )


def test_legacy_member_paths_still_work() -> None:
    from app.db import (  # noqa: F401
        album_master_exists,
        bind_album_master_members,
        delete_album_master,
        list_album_master_members,
        update_album_master_sort_artist_name,
    )


def test_album_master_exists_returns_false_for_invalid_id() -> None:
    """Read-only contract — non-positive or unknown master ids must
    return False, not raise."""
    db.ensure_startup_db_ready()
    assert db.album_master_exists(0) is False
    assert db.album_master_exists(-1) is False
    assert db.album_master_exists(-99999) is False


def test_update_sort_artist_name_returns_none_for_missing_master() -> None:
    """Write contract — updating a master that doesn't exist must
    return None so the route can convert it to 404."""
    db.ensure_startup_db_ready()
    assert db.update_album_master_sort_artist_name(-99999, "test") is None
    assert db.update_album_master_sort_artist_name(0, "test") is None


def test_delete_returns_none_for_invalid_id() -> None:
    """Write contract — DELETE on a non-existent master returns None."""
    db.ensure_startup_db_ready()
    assert db.delete_album_master(-99999) is None
    assert db.delete_album_master(0) is None


def test_list_members_returns_empty_for_unknown_master() -> None:
    """Read-only contract — listing members for a master that has none
    (or doesn't exist) must return [], not raise."""
    db.ensure_startup_db_ready()
    assert db.list_album_master_members(album_master_id=-99999) == []


def test_member_admin_round_trip_through_package_surface() -> None:
    """Create a temp master + temp owned_item, bind, list, update sort,
    confirm exists, delete with cascade, confirm gone."""
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
                VALUES ('MANUAL', 'phase15-probe-master-key',
                        'phase-15 member probe master', NULL, NULL,
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
                VALUES ('MUSIC', 'IN_COLLECTION', 1, 'phase-15 probe item',
                        'STD', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            owned_item_id = int(cur.lastrowid)

        assert db.album_master_exists(master_id) is True

        bound_count = db.bind_album_master_members(master_id, [owned_item_id])
        assert bound_count == 1

        members = db.list_album_master_members(master_id)
        assert any(int(m["owned_item_id"]) == owned_item_id for m in members)

        sort_updated = db.update_album_master_sort_artist_name(master_id, "  Phase 15 Sort  ")
        assert sort_updated is not None
        assert sort_updated["sort_artist_name"] == "Phase 15 Sort"

        # Clearing the sort name should write None.
        sort_cleared = db.update_album_master_sort_artist_name(master_id, "")
        assert sort_cleared is not None
        assert sort_cleared["sort_artist_name"] is None

        result = db.delete_album_master(master_id, cascade_items=True)
        assert result is not None
        assert result["removed_member_links"] == 1
        assert result["deleted_owned_item_count"] == 1

        # After cascade-delete, both rows are gone.
        assert db.album_master_exists(master_id) is False
        master_id = None
        owned_item_id = None
    finally:
        with db.get_write_conn() as conn:
            if master_id is not None:
                conn.execute("DELETE FROM album_master_member WHERE album_master_id = ?", (master_id,))
                conn.execute("DELETE FROM album_master WHERE id = ?", (master_id,))
            if owned_item_id is not None:
                conn.execute("DELETE FROM owned_item WHERE id = ?", (owned_item_id,))


def test_bind_with_invalid_owned_item_ids_filters_them_out() -> None:
    """`bind_album_master_members` should silently drop owned_item ids
    that don't exist (the DB-level subselect filter), not raise."""
    db.ensure_startup_db_ready()

    master_id: int | None = None
    try:
        with db.get_write_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO album_master
                  (source_code, source_master_id, title, artist_or_brand,
                   sort_artist_name, domain_code, release_year, raw_json,
                   created_at, updated_at)
                VALUES ('MANUAL', 'phase15-bind-probe-key',
                        'phase-15 bind probe master', NULL, NULL,
                        'UNKNOWN', NULL, '{}', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            master_id = int(cur.lastrowid)

        # All ids invalid — bind should result in 0 members, no error.
        count = db.bind_album_master_members(master_id, [-1, -99999, 0])
        assert count == 0
    finally:
        if master_id is not None:
            with db.get_write_conn() as conn:
                conn.execute("DELETE FROM album_master_member WHERE album_master_id = ?", (master_id,))
                conn.execute("DELETE FROM album_master WHERE id = ?", (master_id,))
