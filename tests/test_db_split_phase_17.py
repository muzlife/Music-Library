"""Pin the seventeenth slice of the db.py → app/db/ package split.

  * `app.db.digital_link` exposes `insert_digital_link` — the
    atomic two-row insert (digital_asset + owned_item_digital_link)
    used by the purchase-import / metadata-sync paths in main.py
    and the operator owned-item routes in app/api/owned_items.py.
  * `app.db` re-exports the public symbol so existing call sites
    keep working unchanged.

Reads against the digital_asset / owned_item_digital_link tables
are inlined into other surfaces (owned_item detail, album_master
tracks, etc.) and are deliberately NOT moved with this slice — only
the write path is migrated.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app import db
from app.db import digital_link as dl_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = ("insert_digital_link",)


def test_digital_link_submodule_exposes_expected_surface() -> None:
    missing = [name for name in _PUBLIC_SYMBOLS if not hasattr(dl_module, name)]
    assert not missing, f"app.db.digital_link missing: {missing}"


def test_db_package_reexports_insert_digital_link_callable() -> None:
    for name in _PUBLIC_SYMBOLS:
        from_pkg = getattr(db, name, None)
        from_sub = getattr(dl_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as "
            f"db.digital_link.{name}"
        )


def test_init_py_no_longer_redefines_insert_digital_link() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in _PUBLIC_SYMBOLS:
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/digital_link.py"
        )


def test_legacy_digital_link_path_still_works() -> None:
    from app.db import insert_digital_link  # noqa: F401


def test_insert_digital_link_round_trip_through_package_surface() -> None:
    """Insert a temp owned_item, then call insert_digital_link with
    a representative payload. Confirm both the digital_asset row and
    the owned_item_digital_link row land with the right column
    values, then clean up."""
    db.ensure_startup_db_ready()

    owned_item_id: int | None = None
    digital_asset_id: int | None = None
    link_id: int | None = None
    try:
        with db.get_write_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO owned_item
                  (category, status, quantity, item_name_override,
                   size_group, created_at, updated_at)
                VALUES ('MUSIC', 'IN_COLLECTION', 1, 'phase-17 digital probe',
                        'STD', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            owned_item_id = int(cur.lastrowid)

        payload = {
            "asset_type": "AUDIO",
            "file_path": "/tmp/phase-17/probe.flac",
            "file_hash": "sha256:phase-17-probe-hash",
            "file_size_bytes": 12345678,
            "duration_sec": 215,
            "metadata_json": {"bitrate": 1411, "channels": 2},
            "link_type": "FULL_ALBUM",
            "track_no": None,
            "note": "phase-17 round-trip probe",
        }

        ids = db.insert_digital_link(owned_item_id, payload)
        assert isinstance(ids, dict)
        digital_asset_id = int(ids["digital_asset_id"])
        link_id = int(ids["link_id"])
        assert digital_asset_id > 0
        assert link_id > 0

        # Verify both rows landed correctly.
        with db.get_conn() as conn:
            asset_row = conn.execute(
                """
                SELECT asset_type, file_path, file_hash, file_size_bytes,
                       duration_sec, metadata_json
                FROM digital_asset
                WHERE id = ?
                """,
                (digital_asset_id,),
            ).fetchone()
            link_row = conn.execute(
                """
                SELECT owned_item_id, digital_asset_id, link_type,
                       track_no, note
                FROM owned_item_digital_link
                WHERE id = ?
                """,
                (link_id,),
            ).fetchone()

        assert asset_row is not None
        assert asset_row["asset_type"] == "AUDIO"
        assert asset_row["file_path"] == "/tmp/phase-17/probe.flac"
        assert asset_row["file_hash"] == "sha256:phase-17-probe-hash"
        assert int(asset_row["file_size_bytes"]) == 12345678
        assert int(asset_row["duration_sec"]) == 215
        parsed_metadata = json.loads(asset_row["metadata_json"])
        assert parsed_metadata == {"bitrate": 1411, "channels": 2}

        assert link_row is not None
        assert int(link_row["owned_item_id"]) == owned_item_id
        assert int(link_row["digital_asset_id"]) == digital_asset_id
        assert link_row["link_type"] == "FULL_ALBUM"
        assert link_row["track_no"] is None
        assert link_row["note"] == "phase-17 round-trip probe"
    finally:
        with db.get_write_conn() as conn:
            if link_id is not None:
                conn.execute("DELETE FROM owned_item_digital_link WHERE id = ?", (link_id,))
            if digital_asset_id is not None:
                conn.execute("DELETE FROM digital_asset WHERE id = ?", (digital_asset_id,))
            if owned_item_id is not None:
                conn.execute("DELETE FROM owned_item WHERE id = ?", (owned_item_id,))


def test_insert_digital_link_handles_missing_optional_keys() -> None:
    """The payload's `metadata_json` defaults to {} when not present;
    the optional fields (file_hash, file_size_bytes, duration_sec,
    track_no, note) all silently default to None."""
    db.ensure_startup_db_ready()

    owned_item_id: int | None = None
    digital_asset_id: int | None = None
    link_id: int | None = None
    try:
        with db.get_write_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO owned_item
                  (category, status, quantity, item_name_override,
                   size_group, created_at, updated_at)
                VALUES ('MUSIC', 'IN_COLLECTION', 1, 'phase-17 minimal probe',
                        'STD', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            owned_item_id = int(cur.lastrowid)

        # Minimal payload — only the four required keys.
        payload = {
            "asset_type": "AUDIO",
            "file_path": "/tmp/phase-17/minimal.mp3",
            "link_type": "TRACK",
        }

        ids = db.insert_digital_link(owned_item_id, payload)
        digital_asset_id = int(ids["digital_asset_id"])
        link_id = int(ids["link_id"])

        with db.get_conn() as conn:
            asset_row = conn.execute(
                """
                SELECT file_hash, file_size_bytes, duration_sec, metadata_json
                FROM digital_asset WHERE id = ?
                """,
                (digital_asset_id,),
            ).fetchone()
            link_row = conn.execute(
                """
                SELECT track_no, note FROM owned_item_digital_link WHERE id = ?
                """,
                (link_id,),
            ).fetchone()

        assert asset_row["file_hash"] is None
        assert asset_row["file_size_bytes"] is None
        assert asset_row["duration_sec"] is None
        assert json.loads(asset_row["metadata_json"]) == {}
        assert link_row["track_no"] is None
        assert link_row["note"] is None
    finally:
        with db.get_write_conn() as conn:
            if link_id is not None:
                conn.execute("DELETE FROM owned_item_digital_link WHERE id = ?", (link_id,))
            if digital_asset_id is not None:
                conn.execute("DELETE FROM digital_asset WHERE id = ?", (digital_asset_id,))
            if owned_item_id is not None:
                conn.execute("DELETE FROM owned_item WHERE id = ?", (owned_item_id,))
