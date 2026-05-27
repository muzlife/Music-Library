"""Pin the fifth slice of the main.py → APIRouter split.

  * `app.api.owned_items` exposes an `APIRouter` for all 22 owned-items
    routes — listing, detail, create / patch / delete, relations, copies,
    location recommendations, bulk source replace, bulk update, slot
    moves, restore-previous-slot, order moves, digital links, track
    mappings, related-versions, shelf-window, and the
    /owned-item-relation-targets search endpoint.
  * main.py no longer carries those routes inline.
  * The four ops/storage-slots endpoints that mention owned-items
    (/ops/export, /ops/owned-items/{id}/collector-info,
    /storage-slots/{id}/owned-items, …/order) stay in main.py — they
    belong to ops/storage-slot domains, not owned-items CRUD.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.api import owned_items as oi_module


REPO_ROOT = Path(__file__).resolve().parents[1]

_EXPECTED = {
    ("/owned-items", frozenset({"GET"})),
    ("/owned-items", frozenset({"POST"})),
    ("/owned-items/location-recommendations", frozenset({"POST"})),
    ("/owned-items/{owned_item_id}/shelf-window", frozenset({"GET"})),
    ("/owned-items/{owned_item_id}/related-versions", frozenset({"GET"})),
    ("/owned-items/{owned_item_id}/relations", frozenset({"GET"})),
    ("/owned-items/{owned_item_id}/relations", frozenset({"PUT"})),
    ("/owned-item-relation-targets", frozenset({"GET"})),
    ("/owned-items/{owned_item_id}/copies", frozenset({"GET"})),
    ("/owned-items/{owned_item_id}/duplicate", frozenset({"POST"})),
    ("/owned-items/{owned_item_id}/auto-master", frozenset({"POST"})),
    ("/owned-items/{owned_item_id}", frozenset({"GET"})),
    ("/owned-items/{owned_item_id}", frozenset({"PATCH"})),
    ("/owned-items/source-replace-bulk", frozenset({"POST"})),
    ("/owned-items/bulk-update", frozenset({"POST"})),
    ("/owned-items/{owned_item_id}", frozenset({"DELETE"})),
    ("/owned-items/{owned_item_id}/slot", frozenset({"PATCH"})),
    ("/owned-items/{owned_item_id}/restore-previous-slot", frozenset({"POST"})),
    ("/owned-items/{owned_item_id}/order", frozenset({"PATCH"})),
    ("/owned-items/{owned_item_id}/digital-links", frozenset({"POST"})),
    ("/owned-items/{owned_item_id}/track-mappings", frozenset({"GET"})),
    ("/owned-items/{owned_item_id}/track-mappings", frozenset({"POST"})),
}


def test_router_module_exposes_all_owned_items_routes() -> None:
    assert isinstance(oi_module.router, APIRouter)
    actual: set[tuple[str, frozenset[str]]] = set()
    for route in oi_module.router.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None) or set()
        if path is None:
            continue
        actual.add((path, frozenset(methods)))
    missing = _EXPECTED - actual
    assert not missing, f"router missing routes: {sorted(missing)}"


def test_main_py_no_longer_defines_owned_items_routes() -> None:
    main_src = (REPO_ROOT / "app" / "main.py").read_text("utf-8")
    forbidden_paths = (
        '"/owned-items"',
        '"/owned-items/location-recommendations"',
        '"/owned-items/{owned_item_id}/shelf-window"',
        '"/owned-items/{owned_item_id}/related-versions"',
        '"/owned-items/{owned_item_id}/relations"',
        '"/owned-item-relation-targets"',
        '"/owned-items/{owned_item_id}/copies"',
        '"/owned-items/{owned_item_id}/duplicate"',
        '"/owned-items/{owned_item_id}/auto-master"',
        '"/owned-items/{owned_item_id}"',
        '"/owned-items/source-replace-bulk"',
        '"/owned-items/bulk-update"',
        '"/owned-items/{owned_item_id}/slot"',
        '"/owned-items/{owned_item_id}/restore-previous-slot"',
        '"/owned-items/{owned_item_id}/order"',
        '"/owned-items/{owned_item_id}/digital-links"',
        '"/owned-items/{owned_item_id}/track-mappings"',
    )
    for path in forbidden_paths:
        # Each path may legitimately appear in module-level comments or
        # docstrings. Only flag patterns that look like actual `@app.*(`
        # decorators.
        for verb in ("get", "post", "patch", "put", "delete"):
            decorator_signature = f"@app.{verb}({path}"
            assert decorator_signature not in main_src, (
                f"main.py still has {decorator_signature!r}"
            )


def test_main_py_imports_owned_items_router() -> None:
    main_src = (REPO_ROOT / "app" / "main.py").read_text("utf-8")
    assert "from .api.owned_items import router as owned_items_router" in main_src
    assert "app.include_router(owned_items_router)" in main_src


def test_storage_slot_owned_items_endpoints_moved_to_storage_router() -> None:
    """/storage-slots/{id}/owned-items and order route moved to app.api.storage."""
    main_src = (REPO_ROOT / "app" / "main.py").read_text("utf-8")
    storage_src = (REPO_ROOT / "app" / "api" / "storage.py").read_text("utf-8")
    assert '@app.get("/storage-slots/{storage_slot_id}/owned-items"' not in main_src
    assert '@app.patch("/storage-slots/{storage_slot_id}/owned-items/{owned_item_id}/order"' not in main_src
    assert '@router.get("/storage-slots/{storage_slot_id}/owned-items"' in storage_src
    assert '@router.patch("/storage-slots/{storage_slot_id}/owned-items/{owned_item_id}/order"' in storage_src


def test_ops_owned_items_endpoints_moved_to_ops_system() -> None:
    main_src = (REPO_ROOT / "app" / "main.py").read_text("utf-8")
    ops_sys_src = (REPO_ROOT / "app" / "api" / "ops_system.py").read_text("utf-8")
    assert '@app.get("/ops/export/owned-items.csv")' not in main_src
    assert '@router.get("/ops/export/owned-items.csv")' in ops_sys_src


def test_owned_items_list_works_through_new_router(admin_client: TestClient) -> None:
    response = admin_client.get("/owned-items?limit=5")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)


def test_owned_item_relation_targets_works_through_new_router(
    admin_client: TestClient,
) -> None:
    response = admin_client.get("/owned-item-relation-targets?q=test&limit=5")
    assert response.status_code == 200


def test_main_py_dropped_unused_owned_item_schema_imports() -> None:
    """Schemas that the old route signatures used should be gone from
    main.py once their routes moved to app/api/owned_items.py.

    Word-boundary regex (``\\b``) is required so legitimately-retained
    symbols (e.g. SlotOrderMoveResponse used by the storage-slot route)
    don't trigger a false positive against the OrderMoveResponse orphan.
    """
    import re

    main_src = (REPO_ROOT / "app" / "main.py").read_text("utf-8")
    for orphan in (
        "DigitalLinkCreate",
        "DigitalLinkCreateResponse",
        "OrderMoveResponse",
        "OwnedAlbumShelfWindowResponse",
        "OwnedItemAutoMasterResponse",
        "OwnedItemBulkUpdateRequest",
        "OwnedItemBulkUpdateResponse",
        "OwnedItemDeleteResponse",
        "OwnedItemDetailResponse",
        "OwnedItemDuplicateRequest",
        "OwnedItemDuplicateResponse",
        "OwnedItemLocationRecommendationCandidateSlot",
        "OwnedItemLocationRecommendationItem",
        "OwnedItemLocationRecommendationRequest",
        "OwnedItemSourceReplaceBulkRequest",
        "OwnedItemSourceReplaceBulkResponse",
        "OwnedItemSourceReplaceResult",
        "RelatedAlbumVersionsResponse",
        "SlotUpdateRequest",
        "SlotUpdateResponse",
        "SourceLinkState",
        "TrackMappedAssetItem",
        "TrackMappingCreateRequest",
        "TrackMappingCreateResponse",
        "TrackMappingItem",
        "TrackMappingListResponse",
    ):
        pattern = re.compile(rf"\b{re.escape(orphan)}\b")
        assert not pattern.search(main_src), (
            f"main.py still imports {orphan} but no longer uses it"
        )
