"""Pin the thirteenth slice of the db.py → app/db/ package split.

  * `app.db.album_master_correction` exposes the operator manual-
    correction layer on `album_master` —
    `get_album_master_correction_state` for read, and
    `update_album_master_correction` for the override write path.
  * `app.db` re-exports both public functions so existing call sites
    (the `/admin/album-masters/{id}/correction` route, the test
    suite) keep working unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import album_master_correction as ac_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = (
    "get_album_master_correction_state",
    "update_album_master_correction",
)


def test_album_master_correction_submodule_exposes_expected_surface() -> None:
    missing = [name for name in _PUBLIC_SYMBOLS if not hasattr(ac_module, name)]
    assert not missing, f"app.db.album_master_correction missing: {missing}"


def test_db_package_reexports_album_master_correction_callables() -> None:
    for name in _PUBLIC_SYMBOLS:
        from_pkg = getattr(db, name, None)
        from_sub = getattr(ac_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as "
            f"db.album_master_correction.{name}"
        )


def test_init_py_no_longer_redefines_correction_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in _PUBLIC_SYMBOLS:
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/album_master_correction.py"
        )


def test_normalize_domain_code_value_still_lives_in_init() -> None:
    """`_normalize_domain_code_value` is used 25+ times across the
    package. The correction submodule imports it from the package
    surface — the helper itself MUST stay in __init__.py."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    assert "def _normalize_domain_code_value(" in init_src, (
        "_normalize_domain_code_value must remain in app/db/__init__.py "
        "as a cross-cutting helper"
    )


def test_legacy_correction_paths_still_work() -> None:
    from app.db import (  # noqa: F401
        get_album_master_correction_state,
        update_album_master_correction,
    )


def test_correction_state_returns_none_for_missing_master() -> None:
    """Read-only contract — looking up a master that doesn't exist
    must return None, not raise."""
    db.ensure_startup_db_ready()
    assert db.get_album_master_correction_state(album_master_id=-99999) is None
    assert db.get_album_master_correction_state(album_master_id=0) is None


def test_update_correction_returns_none_for_missing_master() -> None:
    """Write contract — updating a master that doesn't exist must
    return None (not raise) so the route can convert it to 404."""
    db.ensure_startup_db_ready()
    result = db.update_album_master_correction(
        album_master_id=-99999,
        release_year=1985,
        domain_code="WESTERN",
        override_note="phase-13 probe",
    )
    assert result is None


def test_correction_round_trip_through_package_surface() -> None:
    """Pick (or create) a real album_master row, write an override,
    confirm correction_state reflects it, then clear the override and
    confirm the source values come back. Cleanup at the end."""
    db.ensure_startup_db_ready()

    cleanup_master_id: int | None = None
    with db.get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM album_master ORDER BY id ASC LIMIT 1"
        ).fetchone()

    if existing is None:
        with db.get_write_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO album_master
                  (source_code, source_master_id, title, artist_or_brand,
                   sort_artist_name, domain_code, release_year, raw_json,
                   created_at, updated_at)
                VALUES ('MANUAL', 'phase13-probe-master-key',
                        'phase-13 correction probe master', NULL, NULL,
                        'UNKNOWN', 2000, '{}', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            cleanup_master_id = int(cur.lastrowid)
        master_id = cleanup_master_id
    else:
        master_id = int(existing["id"])

    try:
        # Capture pre-state so we can restore later.
        before = db.get_album_master_correction_state(master_id)
        assert before is not None

        # Write override.
        updated = db.update_album_master_correction(
            album_master_id=master_id,
            release_year=1985,
            domain_code="WESTERN",
            override_note="phase-13 probe override",
        )
        assert updated is not None
        assert updated["override_release_year"] == 1985
        assert updated["override_domain_code"] == "WESTERN"
        assert updated["override_note"] == "phase-13 probe override"
        assert updated["release_year"] == 1985
        assert updated["domain_code"] == "WESTERN"
        assert updated["has_manual_correction"] is True

        # Confirm state matches via the read-only function too.
        fetched = db.get_album_master_correction_state(master_id)
        assert fetched is not None
        assert fetched["override_release_year"] == 1985
        assert fetched["has_manual_correction"] is True

        # Clear override — pass None for everything, effective values
        # should fall back to source values.
        cleared = db.update_album_master_correction(
            album_master_id=master_id,
            release_year=None,
            domain_code=None,
            override_note=None,
        )
        assert cleared is not None
        assert cleared["override_release_year"] is None
        assert cleared["override_domain_code"] is None
        assert cleared["override_note"] is None
        assert cleared["has_manual_correction"] is False
    finally:
        if cleanup_master_id is not None:
            with db.get_write_conn() as conn:
                conn.execute(
                    "DELETE FROM album_master WHERE id = ?",
                    (cleanup_master_id,),
                )
        else:
            # We didn't create the master, so restore its original
            # correction state if it had any.
            if before is not None:
                db.update_album_master_correction(
                    album_master_id=master_id,
                    release_year=before.get("override_release_year"),
                    domain_code=before.get("override_domain_code"),
                    override_note=before.get("override_note"),
                )
