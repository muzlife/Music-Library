"""Pin the seventh slice of the db.py → app/db/ package split.

  * `app.db.cabinet_camera` exposes the cabinet-camera CRUD surface
    (list / get / get_by_cabinet / upsert / delete).
  * `app.db` re-exports every public symbol so existing call sites
    (the cabinet-camera routes, dashboard snapshot URL helpers, the
    test suite) continue to work unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import cabinet_camera as cc_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = (
    "list_cabinet_cameras",
    "get_cabinet_camera",
    "get_cabinet_camera_by_cabinet",
    "upsert_cabinet_camera",
    "delete_cabinet_camera",
)


def test_cabinet_camera_submodule_exposes_expected_surface() -> None:
    missing = [name for name in _PUBLIC_SYMBOLS if not hasattr(cc_module, name)]
    assert not missing, f"app.db.cabinet_camera missing: {missing}"


def test_db_package_reexports_cabinet_camera_callables() -> None:
    for name in _PUBLIC_SYMBOLS:
        from_pkg = getattr(db, name, None)
        from_sub = getattr(cc_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as db.cabinet_camera.{name}"
        )


def test_init_py_no_longer_redefines_cabinet_camera_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in _PUBLIC_SYMBOLS:
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/cabinet_camera.py"
        )


def test_legacy_cabinet_camera_paths_still_work() -> None:
    from app.db import (  # noqa: F401
        delete_cabinet_camera,
        get_cabinet_camera,
        get_cabinet_camera_by_cabinet,
        list_cabinet_cameras,
        upsert_cabinet_camera,
    )


def test_cabinet_camera_round_trip_through_package_surface() -> None:
    """upsert → list → get → get_by_cabinet → delete via package surface."""
    db.ensure_startup_db_ready()
    cabinet = "phase-7-probe-cabinet"
    camera_name = "phase-7 probe cam"

    created = db.upsert_cabinet_camera(
        cabinet_name=cabinet,
        camera_name=camera_name,
        snapshot_url="http://probe.local/snap.jpg",
    )
    assert created is not None
    camera_id = int(created["id"])

    listed_ids = {int(item["id"]) for item in db.list_cabinet_cameras()}
    assert camera_id in listed_ids

    fetched_by_id = db.get_cabinet_camera(camera_id)
    fetched_by_cabinet = db.get_cabinet_camera_by_cabinet(cabinet)
    assert fetched_by_id is not None
    assert fetched_by_cabinet is not None
    assert int(fetched_by_id["id"]) == int(fetched_by_cabinet["id"]) == camera_id

    assert db.delete_cabinet_camera(camera_id) is True
    assert db.get_cabinet_camera(camera_id) is None
