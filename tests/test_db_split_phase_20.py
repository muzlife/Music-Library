"""Pin the twentieth slice of the db.py → app/db/ package split.

  * `app.db.album_master_read` exposes the album-master read surface
    plus the dual `set_owned_item_linked_album_master` write —
    `list_album_masters`, `count_album_masters`,
    `get_album_master_binding_for_owned_item`,
    `get_album_master_domain_hint`,
    `list_owned_items_by_album_master`,
    `set_owned_item_linked_album_master`, and the private
    `_build_album_master_filter_sql` helper that powers
    list/count.
  * `app.db` re-exports every public symbol so existing call sites
    (`app/main.py`, the album-master admin routes, the test suite)
    keep working unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import album_master_read as amr_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = (
    "list_album_masters",
    "count_album_masters",
    "get_album_master_binding_for_owned_item",
    "get_album_master_domain_hint",
    "list_owned_items_by_album_master",
    "set_owned_item_linked_album_master",
)
_INTERNAL_SYMBOLS = ("_build_album_master_filter_sql",)


def test_album_master_read_submodule_exposes_expected_surface() -> None:
    expected = set(_PUBLIC_SYMBOLS) | set(_INTERNAL_SYMBOLS)
    missing = [name for name in expected if not hasattr(amr_module, name)]
    assert not missing, f"app.db.album_master_read missing: {missing}"


def test_db_package_reexports_album_master_read_callables() -> None:
    for name in _PUBLIC_SYMBOLS:
        from_pkg = getattr(db, name, None)
        from_sub = getattr(amr_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as "
            f"db.album_master_read.{name}"
        )


def test_init_py_no_longer_redefines_album_master_read_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in (*_PUBLIC_SYMBOLS, *_INTERNAL_SYMBOLS):
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/album_master_read.py"
        )


def test_cross_cutting_helpers_still_in_init_py() -> None:
    """The album_master_read submodule pulls a half-dozen helpers
    via the package surface. They MUST remain in __init__.py."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in (
        "_normalize_domain_code_value",
        "_normalize_owned_item_row",
        "_owned_item_select_query",
        "_search_token_groups",
        "_build_compact_token_match_sql",
        "_column_exists",
    ):
        assert f"def {name}(" in init_src, (
            f"{name} must remain in app/db/__init__.py — "
            f"album_master_read pulls it via the package surface"
        )


def test_legacy_album_master_read_paths_still_work() -> None:
    from app.db import (  # noqa: F401
        count_album_masters,
        get_album_master_binding_for_owned_item,
        get_album_master_domain_hint,
        list_album_masters,
        list_owned_items_by_album_master,
        set_owned_item_linked_album_master,
    )


def test_get_binding_returns_none_for_missing_owned_item() -> None:
    db.ensure_startup_db_ready()
    assert db.get_album_master_binding_for_owned_item(0) is None
    assert db.get_album_master_binding_for_owned_item(-1) is None
    assert db.get_album_master_binding_for_owned_item(-99999) is None


def test_get_domain_hint_returns_none_for_missing_master() -> None:
    db.ensure_startup_db_ready()
    assert db.get_album_master_domain_hint(0) is None
    assert db.get_album_master_domain_hint(-1) is None
    assert db.get_album_master_domain_hint(-99999) is None


def test_list_owned_items_by_album_master_returns_empty_for_unknown() -> None:
    db.ensure_startup_db_ready()
    assert db.list_owned_items_by_album_master(album_master_id=-99999) == []


def test_set_owned_item_linked_master_returns_false_for_invalid_owned() -> None:
    """Write contract — invalid owned_item id must return False, not raise."""
    db.ensure_startup_db_ready()
    assert db.set_owned_item_linked_album_master(0, None) is False
    assert db.set_owned_item_linked_album_master(-1, 1) is False


def _empty_filters() -> dict[str, Any]:
    """Shared no-filter argument set for list/count probes — the
    signatures require many positional axes (q, source_code, artist,
    item_name, catalog_no, barcode, release_year, category,
    media_only, domain_code, release_type)."""
    return {
        "source_code": None,
        "q": None,
        "artist_or_brand": None,
        "item_name": None,
        "catalog_no": None,
        "barcode": None,
        "release_year": None,
        "category": None,
        "media_only": False,
        "domain_code": None,
        "release_type": None,
    }


def test_list_and_count_album_masters_smoke() -> None:
    """Smoke — list and count must both succeed under the same
    no-filter inputs."""
    db.ensure_startup_db_ready()
    filters = _empty_filters()
    rows = db.list_album_masters(**filters, limit=1, offset=0)
    total = db.count_album_masters(**filters)
    assert isinstance(rows, list)
    assert isinstance(total, int)
    assert total >= 0
    assert len(rows) <= 1


def test_list_album_masters_pagination_smoke() -> None:
    """Smoke — pagination shouldn't blow up with extreme offsets."""
    db.ensure_startup_db_ready()
    rows = db.list_album_masters(**_empty_filters(), limit=10, offset=10_000_000)
    assert rows == []


def test_set_owned_item_linked_master_round_trip() -> None:
    """Round trip on the owned_item.linked_album_master_id column —
    create temp owned_item + master, set the link, verify the
    column took the value, clear it, verify it's None. Cleanup at
    the end.

    NOTE: `get_album_master_binding_for_owned_item` reads via the
    `album_master_member` JOIN, NOT the linked_album_master_id
    column — those are two different things in the schema. We
    deliberately don't test the binding read here since linking via
    `set_owned_item_linked_album_master` doesn't populate the member
    table; that's done by `bind_album_master_members` (covered in
    Phase 15)."""
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
                VALUES ('MANUAL', 'phase20-link-probe-key',
                        'phase-20 link probe master', NULL, NULL,
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
                VALUES ('MUSIC', 'IN_COLLECTION', 1, 'phase-20 link probe item',
                        'STD', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            owned_item_id = int(cur.lastrowid)

        ok = db.set_owned_item_linked_album_master(owned_item_id, master_id)
        assert ok is True

        with db.get_conn() as conn:
            row = conn.execute(
                "SELECT linked_album_master_id FROM owned_item WHERE id = ?",
                (owned_item_id,),
            ).fetchone()
        assert row is not None
        assert int(row["linked_album_master_id"] or 0) == master_id

        # Unlink — pass None.
        ok2 = db.set_owned_item_linked_album_master(owned_item_id, None)
        assert ok2 is True

        with db.get_conn() as conn:
            row = conn.execute(
                "SELECT linked_album_master_id FROM owned_item WHERE id = ?",
                (owned_item_id,),
            ).fetchone()
        assert row is not None
        assert row["linked_album_master_id"] is None
    finally:
        with db.get_write_conn() as conn:
            if owned_item_id is not None:
                conn.execute("DELETE FROM owned_item WHERE id = ?", (owned_item_id,))
            if master_id is not None:
                conn.execute("DELETE FROM album_master WHERE id = ?", (master_id,))
