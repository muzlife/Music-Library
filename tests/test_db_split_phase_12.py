"""Pin the twelfth slice of the db.py → app/db/ package split.

  * `app.db.album_master_external_ref` exposes the
    `(source_code, source_master_id) ↔ album_master_id` lookup
    surface — `get_album_master_id_by_external_ref` for reads and
    the metadata sync, `list_album_master_external_refs` for the
    "외부 ID" panel, and `ensure_album_master_external_ref` for the
    upsert path.
  * `app.db` re-exports every public symbol so existing call sites
    (the album-master admin route, the metadata-sync providers, AND
    the still-in-__init__.py callers — `upsert_album_master`,
    `normalize_album_master_source_id`, `promote_album_master_source`
    — which resolve `ensure_album_master_external_ref` via the
    package surface at call time) keep working unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import album_master_external_ref as aer_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = (
    "get_album_master_id_by_external_ref",
    "list_album_master_external_refs",
    "ensure_album_master_external_ref",
)


def test_album_master_external_ref_submodule_exposes_expected_surface() -> None:
    missing = [name for name in _PUBLIC_SYMBOLS if not hasattr(aer_module, name)]
    assert not missing, f"app.db.album_master_external_ref missing: {missing}"


def test_db_package_reexports_album_master_external_ref_callables() -> None:
    for name in _PUBLIC_SYMBOLS:
        from_pkg = getattr(db, name, None)
        from_sub = getattr(aer_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as "
            f"db.album_master_external_ref.{name}"
        )


def test_init_py_no_longer_redefines_external_ref_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in _PUBLIC_SYMBOLS:
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/album_master_external_ref.py"
        )


def test_internal_callers_still_invoke_ensure_through_package_surface() -> None:
    """`upsert_album_master`, `normalize_album_master_source_id`, and
    `promote_album_master_source` still call `ensure_album_master_external_ref`
    by bare name — that name must resolve via the package's bottom-of-file
    re-exports at call time, not via a local def."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    # We expect at least 3 bare-name call sites left in __init__.py.
    call_pattern = re.compile(r"\bensure_album_master_external_ref\(")
    matches = call_pattern.findall(init_src)
    assert len(matches) >= 3, (
        f"expected ≥3 internal `ensure_album_master_external_ref(` call "
        f"sites left in app/db/__init__.py, found {len(matches)}"
    )
    # And the function MUST be re-exported from the bottom of __init__.py.
    assert "from .album_master_external_ref import" in init_src, (
        "app/db/__init__.py is missing the album_master_external_ref re-export"
    )


def test_legacy_external_ref_paths_still_work() -> None:
    from app.db import (  # noqa: F401
        ensure_album_master_external_ref,
        get_album_master_id_by_external_ref,
        list_album_master_external_refs,
    )


def test_external_ref_round_trip_through_package_surface() -> None:
    """ensure → get → list → ensure (idempotent) via the package surface,
    using a synthetic source/master id that won't collide with real data."""
    db.ensure_startup_db_ready()

    # We need a real album_master row to attach refs to. Pick the smallest
    # existing one if any, otherwise create a temp one.
    with db.get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM album_master ORDER BY id ASC LIMIT 1"
        ).fetchone()

    cleanup_master_id: int | None = None
    if existing is None:
        # Create a temp master for the round trip. The album_master
        # CHECK constraint restricts source_code to a known set, so we
        # use 'MANUAL' which is always allowed for hand-curated rows.
        with db.get_write_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO album_master
                  (source_code, source_master_id, title, artist_or_brand,
                   sort_artist_name, domain_code, release_year, raw_json,
                   created_at, updated_at)
                VALUES ('MANUAL', 'phase12-probe-master-key', 'phase-12 probe master',
                        NULL, NULL, 'UNKNOWN', NULL, '{}', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            cleanup_master_id = int(cur.lastrowid)
        master_id = cleanup_master_id
    else:
        master_id = int(existing["id"])

    # Both album_master and album_master_external_ref enforce the same
    # CHECK constraint on source_code. Use 'DISCOGS' with a probe-only
    # source_master_id that won't collide with real data.
    source_code = "DISCOGS"
    source_master = "phase-12-probe-discogs-master-id"

    try:
        ref_id_first = db.ensure_album_master_external_ref(
            album_master_id=master_id,
            source_code=source_code,
            source_master_id=source_master,
            title_hint="phase-12 hint",
        )
        assert ref_id_first > 0

        looked_up = db.get_album_master_id_by_external_ref(source_code, source_master)
        assert looked_up == master_id

        listed = db.list_album_master_external_refs(master_id, source_code=source_code)
        assert any(int(item["id"]) == ref_id_first for item in listed)

        ref_id_second = db.ensure_album_master_external_ref(
            album_master_id=master_id,
            source_code=source_code,
            source_master_id=source_master,
            title_hint="phase-12 hint v2",
        )
        assert ref_id_second == ref_id_first  # idempotent on the same key
    finally:
        with db.get_write_conn() as conn:
            conn.execute(
                "DELETE FROM album_master_external_ref WHERE source_code = ? AND source_master_id = ?",
                (source_code, source_master),
            )
            if cleanup_master_id is not None:
                conn.execute(
                    "DELETE FROM album_master WHERE id = ?",
                    (cleanup_master_id,),
                )


def test_get_external_ref_returns_none_for_unknown_keys() -> None:
    """Read-only contract probe — looking up a key that has never been
    inserted must return None, not raise. Pure SELECT, so source_code
    isn't subject to the album_master CHECK constraint here."""
    db.ensure_startup_db_ready()
    result = db.get_album_master_id_by_external_ref(
        "DISCOGS",
        "completely-fake-master-id-phase-12-never-used",
    )
    assert result is None


def test_list_external_refs_returns_empty_for_unknown_master() -> None:
    """Read-only contract probe — listing refs for a master that has
    never had any must return [] (not raise, not None)."""
    db.ensure_startup_db_ready()
    refs = db.list_album_master_external_refs(album_master_id=-99999)
    assert refs == []


def test_ensure_external_ref_validates_required_fields() -> None:
    """`ensure_album_master_external_ref` must raise ValueError when any
    of the required keys (album_master_id > 0, source_code, source_master_id)
    is missing — that's the contract the metadata-sync providers depend
    on for early failure."""
    import pytest

    db.ensure_startup_db_ready()
    with pytest.raises(ValueError):
        db.ensure_album_master_external_ref(
            album_master_id=0,
            source_code="DISCOGS",
            source_master_id="x",
        )
    with pytest.raises(ValueError):
        db.ensure_album_master_external_ref(
            album_master_id=1,
            source_code="",
            source_master_id="x",
        )
    with pytest.raises(ValueError):
        db.ensure_album_master_external_ref(
            album_master_id=1,
            source_code="DISCOGS",
            source_master_id="",
        )
