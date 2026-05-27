"""Pin the sixth slice of the db.py → app/db/ package split.

  * `app.db.goods_item` exposes the goods-item CRUD + mapping +
    collectible-relations + search surface.
  * `app.db` re-exports every public + module-private symbol so existing
    call sites (the goods routes, init_db's CHECK-constraint helpers,
    and the migration chain) continue to work unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import goods_item as gi_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = (
    "create_goods_item",
    "update_goods_item",
    "get_goods_item",
    "delete_goods_item",
    "replace_goods_item_mappings",
    "replace_goods_item_collectible_relations",
    "search_goods_collectible_targets",
    "count_goods_items",
    "search_goods_items",
    "list_goods_artist_name_candidates",
    "list_goods_label_name_candidates",
)
_INTERNAL_SYMBOLS = (
    "_goods_category_check_sql",
    "_goods_status_check_sql",
    "_goods_relation_type_check_sql",
    "_normalize_goods_category_value",
    "_normalize_goods_status_value",
    "_normalize_goods_relation_type_value",
    "_normalize_goods_mapping_text",
    "_goods_item_select_query",
    "_normalize_goods_item_row",
    "_list_goods_item_album_master_mappings_in_conn",
    "_list_goods_item_artist_mappings_in_conn",
    "_list_goods_item_label_mappings_in_conn",
    "_list_goods_item_collectible_relations_in_conn",
    "_build_goods_item_with_mappings",
    "_replace_goods_item_collectible_relations_in_conn",
    "_replace_goods_item_mappings_in_conn",
    "_build_goods_search_where",
)


def test_goods_item_submodule_exposes_expected_surface() -> None:
    expected = set(_PUBLIC_SYMBOLS) | set(_INTERNAL_SYMBOLS)
    missing = [name for name in expected if not hasattr(gi_module, name)]
    assert not missing, f"app.db.goods_item missing: {missing}"


def test_db_package_reexports_goods_item_callables() -> None:
    for name in (*_PUBLIC_SYMBOLS, *_INTERNAL_SYMBOLS):
        from_pkg = getattr(db, name, None)
        from_sub = getattr(gi_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as db.goods_item.{name}"
        )


def test_init_py_no_longer_redefines_goods_item_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in (*_PUBLIC_SYMBOLS, *_INTERNAL_SYMBOLS):
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/goods_item.py"
        )


def test_owned_item_goods_bridge_helpers_remain_in_init() -> None:
    """`_owned_item_allows_goods`, `_migrate_owned_item_allow_goods`, and
    `_upsert_goods_item_detail_in_conn` are owned-item-side helpers that
    happen to involve goods schema. They must be reachable via the package."""
    for stays in (
        "_owned_item_allows_goods",
        "_migrate_owned_item_allow_goods",
        "_upsert_goods_item_detail_in_conn",
    ):
        assert hasattr(db, stays), (
            f"{stays} unexpectedly removed from app.db surface"
        )


def test_legacy_goods_item_paths_still_work() -> None:
    from app.db import (  # noqa: F401
        count_goods_items,
        create_goods_item,
        delete_goods_item,
        get_goods_item,
        list_goods_artist_name_candidates,
        list_goods_label_name_candidates,
        replace_goods_item_collectible_relations,
        replace_goods_item_mappings,
        search_goods_collectible_targets,
        search_goods_items,
        update_goods_item,
    )


def test_goods_item_round_trip_through_package_surface() -> None:
    """create → get → search → count → delete via package surface."""
    db.ensure_startup_db_ready()

    payload = {
        "category": "POSTER",
        "status": "ACTIVE",
        "goods_name": "phase-6 probe poster",
        "domain_code": "KOREA",
    }
    created = db.create_goods_item(payload)
    assert created is not None
    goods_id = int(created["id"])

    fetched = db.get_goods_item(goods_id)
    assert fetched is not None
    assert fetched["goods_name"] == "phase-6 probe poster"

    search_results = db.search_goods_items(query="phase-6 probe", limit=10)
    listed_ids = {int(item["id"]) for item in search_results}
    assert goods_id in listed_ids

    count_before = db.count_goods_items()
    assert count_before >= 1

    assert db.delete_goods_item(goods_id) is True
    assert db.get_goods_item(goods_id) is None
