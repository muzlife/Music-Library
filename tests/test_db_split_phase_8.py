"""Pin the eighth slice of the db.py → app/db/ package split.

  * `app.db.classification_option` exposes the SUBTYPE/SOUNDTRACK
    lookup CRUD plus the seed helper.
  * `app.db` re-exports every symbol so existing call sites (the
    registration UI router, the init/migration chain) keep working.
"""

from __future__ import annotations

import re
from pathlib import Path

from app import db
from app.db import classification_option as co_module


REPO_ROOT = Path(__file__).resolve().parents[1]


_PUBLIC_SYMBOLS = (
    "list_classification_options",
    "upsert_classification_option",
)
_INTERNAL_SYMBOLS = (
    "_seed_classification_options",
)


def test_classification_option_submodule_exposes_expected_surface() -> None:
    expected = set(_PUBLIC_SYMBOLS) | set(_INTERNAL_SYMBOLS)
    missing = [name for name in expected if not hasattr(co_module, name)]
    assert not missing, f"app.db.classification_option missing: {missing}"


def test_db_package_reexports_classification_option_callables() -> None:
    for name in (*_PUBLIC_SYMBOLS, *_INTERNAL_SYMBOLS):
        from_pkg = getattr(db, name, None)
        from_sub = getattr(co_module, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as db.classification_option.{name}"
        )


def test_init_py_no_longer_redefines_classification_option_callables() -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in (*_PUBLIC_SYMBOLS, *_INTERNAL_SYMBOLS):
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/classification_option.py"
        )


def test_legacy_classification_option_paths_still_work() -> None:
    from app.db import (  # noqa: F401
        _seed_classification_options,
        list_classification_options,
        upsert_classification_option,
    )


def test_classification_option_round_trip_through_package_surface() -> None:
    """upsert → list → upsert (idempotent) via the package surface."""
    db.ensure_startup_db_ready()

    label = "phase-8-probe"
    upserted = db.upsert_classification_option("SUBTYPE", label, sort_order=999)
    assert upserted["label"] == label
    assert upserted["is_active"] == 1

    listed_labels = {item["label"] for item in db.list_classification_options("SUBTYPE")}
    assert label in listed_labels

    # Idempotent — second call must not raise.
    again = db.upsert_classification_option("SUBTYPE", label, sort_order=998)
    assert int(again["id"]) == int(upserted["id"])

    # Cleanup so the probe label doesn't pollute fixtures downstream.
    with db.get_write_conn() as conn:
        conn.execute(
            "DELETE FROM classification_option WHERE option_group = ? AND label = ?",
            ("SUBTYPE", label),
        )


def test_seed_helper_idempotent_through_package_surface() -> None:
    """`_seed_classification_options` is the bare-name init helper. Make
    sure the re-export still resolves it AND running it twice doesn't
    raise (it's INSERT...ON CONFLICT)."""
    db.ensure_startup_db_ready()
    with db.get_write_conn() as conn:
        db._seed_classification_options(conn)
        db._seed_classification_options(conn)
