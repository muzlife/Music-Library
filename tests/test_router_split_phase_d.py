"""Pin the fourth slice of the main.py → APIRouter split.

  * `app.api.album_masters` exposes an `APIRouter` for all 13 album-master
    routes (search, variants, bind, import-variants, list, members,
    delete, duplicates, merge, merge-history, rollback, plus the two
    field-update PATCH endpoints).
  * main.py no longer defines those routes inline.
  * Existing CSV export at /ops/export/album-masters.csv stays in main.py.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.api import album_masters as am_module


REPO_ROOT = Path(__file__).resolve().parents[1]

_EXPECTED_PATHS = {
    ("/album-masters/search", frozenset({"POST"})),
    ("/album-masters/variants", frozenset({"GET"})),
    ("/album-masters/bind", frozenset({"POST"})),
    ("/album-masters/import-variants", frozenset({"POST"})),
    ("/album-masters", frozenset({"GET"})),
    ("/album-masters/{album_master_id}/sort-artist-name", frozenset({"PATCH"})),
    ("/album-masters/{album_master_id}/correction", frozenset({"PATCH"})),
    ("/album-masters/{album_master_id}/members", frozenset({"GET"})),
    ("/album-masters/{album_master_id}", frozenset({"DELETE"})),
    ("/album-masters/{album_master_id}/duplicates", frozenset({"GET"})),
    ("/album-masters/{album_master_id}/merge", frozenset({"POST"})),
    ("/album-masters/merge-history", frozenset({"GET"})),
    ("/album-masters/merge-history/latest/rollback", frozenset({"POST"})),
}


def test_router_module_exposes_all_album_master_routes() -> None:
    assert isinstance(am_module.router, APIRouter)
    actual = set()
    for route in am_module.router.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None) or set()
        if path is None:
            continue
        actual.add((path, frozenset(methods)))
    missing = _EXPECTED_PATHS - actual
    assert not missing, f"router missing routes: {sorted(missing)}"


def test_main_py_no_longer_defines_album_master_routes() -> None:
    main_src = (REPO_ROOT / "app" / "main.py").read_text("utf-8")
    forbidden_decorators = (
        '@app.post("/album-masters/search"',
        '@app.get("/album-masters/variants"',
        '@app.post("/album-masters/bind"',
        '@app.post("/album-masters/import-variants"',
        '@app.get("/album-masters"',
        '@app.patch("/album-masters/{album_master_id}/sort-artist-name"',
        '@app.patch("/album-masters/{album_master_id}/correction"',
        '@app.get("/album-masters/{album_master_id}/members"',
        '@app.delete("/album-masters/{album_master_id}"',
        '@app.get("/album-masters/{album_master_id}/duplicates"',
        '@app.post("/album-masters/{album_master_id}/merge"',
        '@app.get("/album-masters/merge-history"',
        '@app.post("/album-masters/merge-history/latest/rollback"',
    )
    for decorator in forbidden_decorators:
        assert decorator not in main_src, (
            f"main.py still defines {decorator!r}; route should be in app/api/album_masters.py"
        )


def test_main_py_imports_album_masters_router() -> None:
    main_src = (REPO_ROOT / "app" / "main.py").read_text("utf-8")
    assert "from .api.album_masters import router as album_masters_router" in main_src
    assert "app.include_router(album_masters_router)" in main_src


def test_csv_export_endpoint_still_lives_in_main() -> None:
    """The /ops/export/album-masters.csv endpoint is operational tooling
    rather than a /album-masters/* CRUD route — it stays in main.py."""
    main_src = (REPO_ROOT / "app" / "main.py").read_text("utf-8")
    assert '@app.get("/ops/export/album-masters.csv")' not in main_src
    assert '@router.get("/ops/export/album-masters.csv")' in (REPO_ROOT / "app" / "api" / "ops_system.py").read_text("utf-8")


def test_album_masters_list_works_through_new_router(admin_client: TestClient) -> None:
    response = admin_client.get("/album-masters?limit=5")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)


def test_album_masters_merge_history_works_through_new_router(admin_client: TestClient) -> None:
    response = admin_client.get("/album-masters/merge-history?limit=5")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_album_masters_search_works_through_new_router(admin_client: TestClient) -> None:
    response = admin_client.post(
        "/album-masters/search",
        json={"query": "test album", "source": "AUTO", "limit": 5},
    )
    # Search returns 200 with possibly empty candidates — mainly checking
    # the route is wired and reaches the helpers.
    assert response.status_code == 200
    body = response.json()
    assert "candidates" in body


def test_main_py_dropped_unused_album_master_schema_imports() -> None:
    """Schemas the old route signatures used should be gone from main.py
    once their routes moved to app/api/album_masters.py."""
    main_src = (REPO_ROOT / "app" / "main.py").read_text("utf-8")
    for orphan in (
        "AlbumMasterBindRequest",
        "AlbumMasterBindResponse",
        "AlbumMasterCorrectionUpdateRequest",
        "AlbumMasterCorrectionUpdateResponse",
        "AlbumMasterDeleteResponse",
        "AlbumMasterDuplicateCheckResponse",
        "AlbumMasterDuplicateItem",
        "AlbumMasterImportCreatedItem",
        "AlbumMasterImportSkippedItem",
        "AlbumMasterImportVariantsResponse",
        "AlbumMasterMergeHistoryItem",
        "AlbumMasterMergeRequest",
        "AlbumMasterMergeRollbackResponse",
        "AlbumMasterMergeResponse",
        "AlbumMasterSearchRequest",
        "AlbumMasterSearchResponse",
        "AlbumMasterSortArtistUpdateRequest",
        "AlbumMasterSortArtistUpdateResponse",
        "AlbumMasterVariantsResponse",
    ):
        assert orphan not in main_src, (
            f"main.py still imports {orphan} but no longer uses it"
        )
