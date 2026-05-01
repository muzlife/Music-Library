"""Pin the nineteenth slice of the db.py → app/db/ package split.

  * `app.db.album_master_core` exposes the four core album-master
    writers — `upsert_album_master`, `normalize_album_master_source_id`,
    `promote_album_master_source`, `merge_album_masters` — plus the
    cross-cutting helpers they share
    (`_sync_album_master_domain_code_in_conn`, the three snapshot
    builders).
  * `app.db` re-exports every public/internal symbol so existing
    callers (`app/main.py`, `app/api/album_masters.py`, the test
    suite, AND the still-in-__init__.py owned-item update path that
    calls `_sync_album_master_domain_code_in_conn` by bare name)
    keep working unchanged.

Re-export ordering invariant
  album_master_core MUST be re-exported BEFORE album_master_member,
  because `album_master_member.bind_album_master_members` imports
  `_sync_album_master_domain_code_in_conn` from the package surface
  at module-load time, and that helper now lives in
  album_master_core. The pin below verifies the ordering survives
  any future re-write of __init__.py.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import album_master_core as amc_module
from app.db import album_master_member as amm_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = (
    "upsert_album_master",
    "normalize_album_master_source_id",
    "promote_album_master_source",
    "merge_album_masters",
)
_INTERNAL_SYMBOLS = (
    "_sync_album_master_domain_code_in_conn",
    "_snapshot_album_master_record",
    "_snapshot_member_link_records",
    "_snapshot_external_ref_records",
)


def test_album_master_core_submodule_exposes_expected_surface() -> None:
    expected = set(_PUBLIC_SYMBOLS) | set(_INTERNAL_SYMBOLS)
    missing = [name for name in expected if not hasattr(amc_module, name)]
    assert not missing, f"app.db.album_master_core missing: {missing}"


def test_db_package_reexports_album_master_core_callables() -> None:
    for name in (*_PUBLIC_SYMBOLS, *_INTERNAL_SYMBOLS):
        from_pkg = getattr(db, name, None)
        from_sub = getattr(amc_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as "
            f"db.album_master_core.{name}"
        )


def test_init_py_no_longer_redefines_album_master_core_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in (*_PUBLIC_SYMBOLS, *_INTERNAL_SYMBOLS):
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/album_master_core.py"
        )


def test_album_master_member_resolves_sync_helper_through_package() -> None:
    """`album_master_member.bind_album_master_members` calls
    `_sync_album_master_domain_code_in_conn` via the package surface.
    After Phase 19 moved that helper into album_master_core, the
    package surface MUST still expose the same callable."""
    assert amm_module._sync_album_master_domain_code_in_conn is db._sync_album_master_domain_code_in_conn
    assert amm_module._sync_album_master_domain_code_in_conn is amc_module._sync_album_master_domain_code_in_conn


def test_reexport_ordering_album_master_core_before_member() -> None:
    """Critical invariant — album_master_core re-export MUST appear
    BEFORE album_master_member re-export in __init__.py. Otherwise
    album_master_member.py fails to import at package-load time."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    core_pos = init_src.find("from .album_master_core import")
    member_pos = init_src.find("from .album_master_member import")
    assert core_pos > 0, "album_master_core re-export missing from __init__.py"
    assert member_pos > 0, "album_master_member re-export missing from __init__.py"
    assert core_pos < member_pos, (
        "album_master_core re-export MUST come BEFORE album_master_member "
        "re-export in __init__.py — album_master_member depends on "
        "_sync_album_master_domain_code_in_conn which now lives in core."
    )


def test_normalize_domain_code_value_still_in_init_py() -> None:
    """`_normalize_domain_code_value` is used 25+ times across the
    package. The album_master_core submodule pulls it via the
    package surface — the helper itself MUST stay in __init__.py."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    assert "def _normalize_domain_code_value(" in init_src


def test_legacy_album_master_core_paths_still_work() -> None:
    from app.db import (  # noqa: F401
        merge_album_masters,
        normalize_album_master_source_id,
        promote_album_master_source,
        upsert_album_master,
    )


def test_upsert_album_master_round_trip_through_package_surface() -> None:
    """upsert → re-upsert(idempotent on same key) → external_ref auto-
    populated, all via the package surface. Cleanup at the end."""
    db.ensure_startup_db_ready()

    source_master_id = "phase-19-upsert-probe-id"
    cleanup_master_id: int | None = None
    try:
        master_id_1 = db.upsert_album_master(
            source_code="MANUAL",
            source_master_id=source_master_id,
            title="phase-19 upsert probe",
            artist_or_brand="phase-19 artist",
            domain_code="WESTERN",
            release_year=2026,
            raw={"probe": "phase-19"},
        )
        assert isinstance(master_id_1, int) and master_id_1 > 0
        cleanup_master_id = master_id_1

        # Idempotent — second upsert on the same key returns the same id.
        master_id_2 = db.upsert_album_master(
            source_code="MANUAL",
            source_master_id=source_master_id,
            title="phase-19 upsert probe v2",
            artist_or_brand="phase-19 artist",
            domain_code="WESTERN",
            release_year=2027,
            raw={"probe": "phase-19", "version": 2},
        )
        assert master_id_2 == master_id_1

        # external_ref must have been auto-populated by the upsert.
        ref_id = db.get_album_master_id_by_external_ref("MANUAL", source_master_id)
        assert ref_id == master_id_1
    finally:
        if cleanup_master_id is not None:
            with db.get_write_conn() as conn:
                conn.execute(
                    "DELETE FROM album_master_external_ref WHERE album_master_id = ?",
                    (cleanup_master_id,),
                )
                conn.execute(
                    "DELETE FROM album_master WHERE id = ?",
                    (cleanup_master_id,),
                )


def test_normalize_album_master_source_id_smoke() -> None:
    """Smoke — call normalize with no-op inputs (master_id <= 0 etc.)
    and confirm the no-op contracts hold (returns master_id unchanged)."""
    db.ensure_startup_db_ready()
    # master_id <= 0 must short-circuit.
    assert db.normalize_album_master_source_id(0, "DISCOGS", "x") == 0
    assert db.normalize_album_master_source_id(-1, "DISCOGS", "x") == -1
    # blank source_code or source_master_id must short-circuit.
    assert db.normalize_album_master_source_id(1, "", "x") == 1
    assert db.normalize_album_master_source_id(1, "DISCOGS", "") == 1


def test_promote_album_master_source_smoke() -> None:
    """Smoke — promote with invalid arguments must return 0."""
    db.ensure_startup_db_ready()
    result = db.promote_album_master_source(
        album_master_id=0,
        source_code="DISCOGS",
        source_master_id="x",
        title="anything",
        artist_or_brand=None,
        domain_code=None,
        release_year=None,
        raw={},
    )
    assert result == 0


def test_merge_album_masters_validates_positive_ids() -> None:
    """Contract — merge with source/target <= 0 must raise ValueError."""
    import pytest

    db.ensure_startup_db_ready()
    with pytest.raises(ValueError):
        db.merge_album_masters(0, 1)
    with pytest.raises(ValueError):
        db.merge_album_masters(1, 0)
    with pytest.raises(ValueError):
        db.merge_album_masters(-1, -2)


def test_merge_album_masters_raises_lookup_when_target_missing() -> None:
    """Contract — merge with positive ids but missing target raises
    LookupError so the route can return 404."""
    import pytest

    db.ensure_startup_db_ready()
    with pytest.raises(LookupError):
        db.merge_album_masters(99999998, 99999999)
