# Album Master Genres/Styles Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate `genres_json`/`styles_json` from `music_item_detail` (per-owned-item) to `album_master` (canonical per-master), update Discogs/ManiaDB ingestion to write genres to the master table, and update all reads accordingly.

**Architecture:** Add `genres_json`/`styles_json` columns to `album_master`; add a non-destructive `update_album_master_genres()` writer; call it from the metadata-sync and correction paths. The `music_item_detail` columns are kept as-is (no removal) so existing per-item data is not lost. Reads switch from subqueries on `music_item_detail` to direct `am.genres_json` lookups.

**Tech Stack:** SQLite (raw SQL), FastAPI, Python 3.11, Pydantic v2, vanilla JS

---

## File Map

| File | Change |
|------|--------|
| `app/db/schema_migration.py` | Add migration step 31: ALTER TABLE + backfill |
| `app/db/album_master_core.py` | New `update_album_master_genres()` function |
| `app/db/__init__.py` | Re-export `update_album_master_genres` |
| `app/db/album_master_read.py` | Replace subqueries with `am.genres_json`; fix `genre_missing` filter |
| `app/db/metadata_sync.py` | Update `only_missing` genre check to use `am.genres_json` |
| `app/db/album_master_correction.py` | Add genres/styles to get + update correction |
| `app/main.py` | Call `update_album_master_genres` after `upsert_music_detail` in both sync paths |
| `app/schemas.py` | Add genres/styles to `AlbumMasterCorrectionUpdateRequest/Response` |
| `app/api/album_masters.py` | Pass genres/styles to `db.update_album_master_correction` |
| `app/static/index.html` | Add genres/styles input rows to master edit panel |

---

## Task 1: DB Migration — add columns + backfill

**Files:**
- Modify: `app/db/schema_migration.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_schema_migration.py  (add to existing file or create)
import sqlite3
import pytest
from app.db.schema_migration import run_migrations

def test_album_master_has_genres_columns(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    # bootstrap minimal tables so migration can run
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS migration_version (version INTEGER);
        CREATE TABLE IF NOT EXISTS album_master (
            id INTEGER PRIMARY KEY,
            source_code TEXT, source_master_id TEXT, title TEXT,
            artist_or_brand TEXT, domain_code TEXT, release_year INTEGER,
            raw_json TEXT, created_at TEXT, updated_at TEXT
        );
    """)
    conn.commit()
    run_migrations(conn)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(album_master)")}
    assert "genres_json" in cols
    assert "styles_json" in cols
    conn.close()
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd /Volumes/Data/Works/07.__PROJECT_SLUG__
python -m pytest tests/test_schema_migration.py::test_album_master_has_genres_columns -v
```
Expected: FAIL (columns don't exist yet)

- [ ] **Step 3: Find the last migration version number**

```bash
grep -n "def _run_step_\|_CURRENT_VERSION\|version.*=.*[0-9]" app/db/schema_migration.py | tail -20
```
Note the current max step number (e.g. 30). New step = max + 1.

- [ ] **Step 4: Add migration step (example assumes current max is 30, adjust if different)**

In `app/db/schema_migration.py`, find the `_run_migrations` function (or equivalent loop) and add a new step. The pattern used in this file is a series of versioned steps. Add after the last step:

```python
# Step 31 — album_master.genres_json / styles_json
if version < 31:
    if not _column_exists(conn, "album_master", "genres_json"):
        conn.execute("ALTER TABLE album_master ADD COLUMN genres_json TEXT")
    if not _column_exists(conn, "album_master", "styles_json"):
        conn.execute("ALTER TABLE album_master ADD COLUMN styles_json TEXT")
    # Backfill from the first music_item_detail record per master (order by owned_item.order_key)
    conn.execute("""
        UPDATE album_master
        SET
          genres_json = (
            SELECT mid.genres_json
            FROM album_master_member amm
            JOIN owned_item oi ON oi.id = amm.owned_item_id
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            WHERE amm.album_master_id = album_master.id
              AND mid.genres_json IS NOT NULL
              AND mid.genres_json <> '[]'
              AND TRIM(mid.genres_json) <> ''
            ORDER BY
              CASE WHEN oi.order_key IS NULL OR TRIM(oi.order_key) = '' THEN 1 ELSE 0 END,
              oi.order_key ASC, oi.id ASC
            LIMIT 1
          ),
          styles_json = (
            SELECT mid.styles_json
            FROM album_master_member amm
            JOIN owned_item oi ON oi.id = amm.owned_item_id
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            WHERE amm.album_master_id = album_master.id
              AND mid.styles_json IS NOT NULL
              AND mid.styles_json <> '[]'
              AND TRIM(mid.styles_json) <> ''
            ORDER BY
              CASE WHEN oi.order_key IS NULL OR TRIM(oi.order_key) = '' THEN 1 ELSE 0 END,
              oi.order_key ASC, oi.id ASC
            LIMIT 1
          )
        WHERE genres_json IS NULL OR styles_json IS NULL
    """)
    conn.execute("UPDATE migration_version SET version = 31")
    conn.commit()
```

> NOTE: Look at how the actual step increment works in the file (some files use `UPDATE migration_version`, others increment a counter) and follow that exact pattern.

- [ ] **Step 5: Run test to confirm it passes**

```bash
python -m pytest tests/test_schema_migration.py::test_album_master_has_genres_columns -v
```
Expected: PASS

- [ ] **Step 6: Verify backfill runs on real DB without error**

```bash
python -c "
from app.db import get_conn
from app.db.schema_migration import run_migrations
with get_conn() as conn:
    run_migrations(conn)
print('migration OK')
"
```
Expected: `migration OK` with no exceptions

- [ ] **Step 7: Commit**

```bash
git add app/db/schema_migration.py tests/test_schema_migration.py
git commit -m "feat(db): add genres_json/styles_json columns to album_master with backfill"
```

---

## Task 2: New `update_album_master_genres()` writer

**Files:**
- Modify: `app/db/album_master_core.py`
- Modify: `app/db/__init__.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_album_master_genres.py  (new file)
import sqlite3, json, pytest
from unittest.mock import patch

def _make_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE album_master (
            id INTEGER PRIMARY KEY,
            source_code TEXT, source_master_id TEXT,
            title TEXT, artist_or_brand TEXT,
            domain_code TEXT, release_year INTEGER,
            raw_json TEXT, genres_json TEXT, styles_json TEXT,
            created_at TEXT, updated_at TEXT
        );
        INSERT INTO album_master VALUES
          (1,'DISCOGS','123','Title','Artist',NULL,2000,'{}',NULL,NULL,
           '2024-01-01','2024-01-01');
    """)
    return conn

def test_update_album_master_genres_writes_when_empty():
    from app.db.album_master_core import update_album_master_genres
    conn = _make_conn()
    with patch("app.db.album_master_core.get_conn") as mock_get_conn:
        mock_get_conn.return_value.__enter__ = lambda s: conn
        mock_get_conn.return_value.__exit__ = lambda s, *a: None
        update_album_master_genres(1, ["Rock"], ["Indie Rock"])
    row = conn.execute("SELECT genres_json, styles_json FROM album_master WHERE id=1").fetchone()
    assert json.loads(row["genres_json"]) == ["Rock"]
    assert json.loads(row["styles_json"]) == ["Indie Rock"]
    conn.close()

def test_update_album_master_genres_does_not_overwrite_with_empty():
    from app.db.album_master_core import update_album_master_genres
    conn = _make_conn()
    conn.execute("UPDATE album_master SET genres_json='[\"Rock\"]', styles_json='[\"Indie Rock\"]' WHERE id=1")
    with patch("app.db.album_master_core.get_conn") as mock_get_conn:
        mock_get_conn.return_value.__enter__ = lambda s: conn
        mock_get_conn.return_value.__exit__ = lambda s, *a: None
        update_album_master_genres(1, [], [])  # empty — must not overwrite
    row = conn.execute("SELECT genres_json, styles_json FROM album_master WHERE id=1").fetchone()
    assert json.loads(row["genres_json"]) == ["Rock"]
    conn.close()
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
python -m pytest tests/test_album_master_genres.py -v
```
Expected: FAIL (function doesn't exist)

- [ ] **Step 3: Add `update_album_master_genres` to `album_master_core.py`**

Add the following function after `get_album_master_basic` (around line 140, before `upsert_album_master`):

```python
def update_album_master_genres(
    album_master_id: int,
    genres: list[str],
    styles: list[str],
) -> None:
    """Write genres/styles to album_master.  No-op if both lists are empty."""
    clean_genres = [str(v).strip() for v in (genres or []) if str(v).strip()]
    clean_styles = [str(v).strip() for v in (styles or []) if str(v).strip()]
    if not clean_genres and not clean_styles:
        return
    now = utc_now_iso()
    with get_conn() as conn:
        if clean_genres:
            conn.execute(
                "UPDATE album_master SET genres_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(clean_genres, ensure_ascii=True), now, int(album_master_id)),
            )
        if clean_styles:
            conn.execute(
                "UPDATE album_master SET styles_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(clean_styles, ensure_ascii=True), now, int(album_master_id)),
            )
```

Also add `"update_album_master_genres"` to the `__all__` list at the bottom of `album_master_core.py`.

- [ ] **Step 4: Re-export from `app/db/__init__.py`**

Find the block where `album_master_core` symbols are imported (around line 2005) and add:

```python
from app.db.album_master_core import (
    ...
    update_album_master_genres,   # add this line
)
```

Also add `"update_album_master_genres"` to the `__all__` list in `__init__.py` if one exists.

- [ ] **Step 5: Run test to confirm it passes**

```bash
python -m pytest tests/test_album_master_genres.py -v
```
Expected: PASS (both tests)

- [ ] **Step 6: Commit**

```bash
git add app/db/album_master_core.py app/db/__init__.py tests/test_album_master_genres.py
git commit -m "feat(db): add update_album_master_genres writer for master-level genre storage"
```

---

## Task 3: Update album_master_read.py — direct column reads + genre_missing filter

**Files:**
- Modify: `app/db/album_master_read.py`

- [ ] **Step 1: Find the two subquery blocks for genres_json / styles_json**

```bash
grep -n "genres_json\|styles_json" app/db/album_master_read.py
```
The output shows two subquery blocks (around lines 668–696) and one `genre_missing` filter (around line 423).

- [ ] **Step 2: Replace the genres_json subquery with a direct column reference**

Find and replace the entire subquery block (about 13 lines):

```sql
-- OLD (remove this entire subquery block):
        (
          SELECT mid.genres_json
          FROM album_master_member amm_gen
          JOIN owned_item oi_gen ON oi_gen.id = amm_gen.owned_item_id
          LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi_gen.id
          WHERE amm_gen.album_master_id = am.id
            AND mid.genres_json IS NOT NULL
            AND mid.genres_json <> '[]'
            AND TRIM(mid.genres_json) <> ''
          ORDER BY
            CASE WHEN oi_gen.order_key IS NULL OR TRIM(oi_gen.order_key) = '' THEN 1 ELSE 0 END,
            oi_gen.order_key ASC,
            oi_gen.id ASC
          LIMIT 1
        ) AS genres_json,
```

Replace with:

```sql
        am.genres_json,
```

- [ ] **Step 3: Replace the styles_json subquery with a direct column reference**

Find and replace the entire styles_json subquery block:

```sql
-- OLD (remove this entire subquery block):
        (
          SELECT mid.styles_json
          FROM album_master_member amm_sty
          JOIN owned_item oi_sty ON oi_sty.id = amm_sty.owned_item_id
          LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi_sty.id
          WHERE amm_sty.album_master_id = am.id
            AND mid.styles_json IS NOT NULL
            AND mid.styles_json <> '[]'
            AND TRIM(mid.styles_json) <> ''
          ORDER BY
            CASE WHEN oi_sty.order_key IS NULL OR TRIM(oi_sty.order_key) = '' THEN 1 ELSE 0 END,
            oi_sty.order_key ASC,
            oi_sty.id ASC
          LIMIT 1
        ) AS styles_json,
```

Replace with:

```sql
        am.styles_json,
```

- [ ] **Step 4: Update the genre_missing filter**

Find the `genre_missing` filter (around line 423):

```sql
-- OLD:
              AND (midg.genres_json IS NULL OR TRIM(midg.genres_json) = '' OR midg.genres_json = '[]')
```

This filter is part of a subquery or join involving `music_item_detail midg`. Replace the entire genre_missing JOIN/subquery block with a direct check on `am.genres_json`. The surrounding code looks like:

```python
    if genre_missing:
        query += """
          AND am.id IN (
            SELECT amm_g.album_master_id
            FROM album_master_member amm_g
            JOIN owned_item oi_g ON oi_g.id = amm_g.owned_item_id
            LEFT JOIN music_item_detail midg ON midg.owned_item_id = oi_g.id
            WHERE amm_g.album_master_id = am.id
              AND (midg.genres_json IS NULL OR TRIM(midg.genres_json) = '' OR midg.genres_json = '[]')
          )
        """
```

Replace with:

```python
    if genre_missing:
        query += """
          AND (am.genres_json IS NULL OR TRIM(am.genres_json) = '' OR am.genres_json = '[]')
        """
```

(The exact surrounding Python context may differ — match to what you see in the file.)

- [ ] **Step 5: Verify no remaining music_item_detail subqueries for genres in album_master_read.py**

```bash
grep -n "genres_json\|styles_json" app/db/album_master_read.py
```
Expected: only `am.genres_json` and `am.styles_json` references, no `mid.genres_json` subqueries.

- [ ] **Step 6: Run the server and test the masters list endpoint**

```bash
curl -s http://localhost:8100/album-masters?limit=5 | python3 -m json.tool | grep -A2 '"genres"'
```
Expected: genres appear as before (now from master column).

- [ ] **Step 7: Commit**

```bash
git add app/db/album_master_read.py
git commit -m "refactor(db): read genres/styles from album_master directly instead of music_item_detail subquery"
```

---

## Task 4: Update metadata_sync.py — genre_missing candidate filter

**Files:**
- Modify: `app/db/metadata_sync.py`

- [ ] **Step 1: Locate the genre_missing filter in `list_metadata_sync_candidates`**

```bash
grep -n "genres_json\|styles_json" app/db/metadata_sync.py
```
The `only_missing` block (around lines 108–113) checks `mid.genres_json`.

- [ ] **Step 2: Verify the query already JOINs album_master**

```bash
grep -n "LEFT JOIN album_master\|album_master am" app/db/metadata_sync.py
```
Confirm there is a `LEFT JOIN album_master am ON am.id = oi.linked_album_master_id` in the query.

- [ ] **Step 3: Replace the genre check inside the `only_missing` block**

Find:

```python
            OR mid.genres_json IS NULL
            OR TRIM(COALESCE(mid.genres_json, '')) = ''
            OR TRIM(COALESCE(mid.genres_json, '')) = '[]'
            OR mid.styles_json IS NULL
            OR TRIM(COALESCE(mid.styles_json, '')) = ''
            OR TRIM(COALESCE(mid.styles_json, '')) = '[]'
```

Replace with:

```python
            OR am.genres_json IS NULL
            OR TRIM(COALESCE(am.genres_json, '')) = ''
            OR TRIM(COALESCE(am.genres_json, '')) = '[]'
            OR am.styles_json IS NULL
            OR TRIM(COALESCE(am.styles_json, '')) = ''
            OR TRIM(COALESCE(am.styles_json, '')) = '[]'
```

- [ ] **Step 4: Verify the change**

```bash
grep -n "genres_json\|styles_json" app/db/metadata_sync.py
```
Expected: the `only_missing` block now references `am.genres_json`/`am.styles_json`. The SELECT list still references `mid.genres_json`/`mid.styles_json` (those are returned for the candidate display — that's fine, leave them).

- [ ] **Step 5: Commit**

```bash
git add app/db/metadata_sync.py
git commit -m "fix(db): genre_missing sync filter checks album_master.genres_json instead of music_item_detail"
```

---

## Task 5: Call `update_album_master_genres` after metadata sync writes

**Files:**
- Modify: `app/main.py`

The two sync paths are:
- `_run_metadata_sync` batch loop: `db.upsert_music_detail(...)` at line ~2960
- `_sync_one_item` single sync: `db.upsert_music_detail(...)` at line ~4471

Both paths have access to `music_detail` (which contains `genres` and `styles`) and `row["linked_album_master_id"]`.

- [ ] **Step 1: Add the genre update call in the batch loop**

Find in `_run_metadata_sync` (around line 2960):

```python
            db.upsert_music_detail(owned_item_id=owned_item_id, music_detail=music_detail, note_append=note_append)
            updated_count += 1
```

Replace with:

```python
            db.upsert_music_detail(owned_item_id=owned_item_id, music_detail=music_detail, note_append=note_append)
            linked_master_id = int(row.get("linked_album_master_id") or 0)
            if linked_master_id > 0:
                db.update_album_master_genres(
                    album_master_id=linked_master_id,
                    genres=music_detail.get("genres") or [],
                    styles=music_detail.get("styles") or [],
                )
            updated_count += 1
```

- [ ] **Step 2: Add the genre update call in `_sync_one_item`**

Find in `_sync_one_item` (around line 4471):

```python
    db.upsert_music_detail(owned_item_id=owned_item_id, music_detail=music_detail, note_append=note_append)
```

After that line, add:

```python
    linked_master_id = int(row.get("linked_album_master_id") or 0)
    if linked_master_id > 0:
        db.update_album_master_genres(
            album_master_id=linked_master_id,
            genres=music_detail.get("genres") or [],
            styles=music_detail.get("styles") or [],
        )
```

- [ ] **Step 3: Verify `db.update_album_master_genres` is importable**

```bash
python -c "import app.db as db; print(hasattr(db, 'update_album_master_genres'))"
```
Expected: `True`

- [ ] **Step 4: Quick integration smoke test**

Start the QA server and trigger a single-item sync for an item that has Discogs source and a linked master:
```bash
# Find a DISCOGS item with a linked master
sqlite3 ~/apps/__PROJECT_SLUG__-qa/library.db \
  "SELECT oi.id FROM owned_item oi WHERE oi.source_code='DISCOGS' AND oi.linked_album_master_id IS NOT NULL LIMIT 1;"

# Check current master genres (should be populated from backfill, but verify)
sqlite3 ~/apps/__PROJECT_SLUG__-qa/library.db \
  "SELECT am.id, am.genres_json, am.styles_json FROM album_master am JOIN owned_item oi ON oi.linked_album_master_id=am.id WHERE oi.source_code='DISCOGS' LIMIT 3;"
```

- [ ] **Step 5: Commit**

```bash
git add app/main.py
git commit -m "feat(sync): propagate genres/styles to album_master after metadata sync"
```

---

## Task 6: Add genres/styles to the master correction flow

**Files:**
- Modify: `app/db/album_master_correction.py`
- Modify: `app/schemas.py`
- Modify: `app/api/album_masters.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_album_master_correction_genres.py (new file)
import sqlite3, json, pytest
from unittest.mock import patch

def _make_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE album_master (
            id INTEGER PRIMARY KEY,
            source_code TEXT, source_master_id TEXT,
            title TEXT, artist_or_brand TEXT, domain_code TEXT,
            release_year INTEGER, raw_json TEXT,
            genres_json TEXT, styles_json TEXT,
            override_title TEXT, override_artist_or_brand TEXT,
            override_release_year INTEGER, override_domain_code TEXT,
            override_note TEXT, source_release_year INTEGER,
            source_domain_code TEXT, sort_artist_name TEXT,
            created_at TEXT, updated_at TEXT
        );
        INSERT INTO album_master VALUES
          (1,'DISCOGS','123','Title','Artist',NULL,2000,'{}',
           '["Rock"]','["Indie Rock"]',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,
           '2024-01-01','2024-01-01');
    """)
    return conn

def test_get_correction_state_includes_genres():
    from app.db.album_master_correction import get_album_master_correction_state
    conn = _make_conn()
    with patch("app.db.album_master_correction.get_conn") as m:
        m.return_value.__enter__ = lambda s: conn
        m.return_value.__exit__ = lambda s, *a: None
        result = get_album_master_correction_state(1)
    assert result["genres"] == ["Rock"]
    assert result["styles"] == ["Indie Rock"]
    conn.close()

def test_update_correction_sets_genres():
    from app.db.album_master_correction import update_album_master_correction
    conn = _make_conn()
    with patch("app.db.album_master_correction.get_conn") as m:
        m.return_value.__enter__ = lambda s: conn
        m.return_value.__exit__ = lambda s, *a: None
        result = update_album_master_correction(
            1, release_year=None, domain_code=None, override_note=None,
            genres=["Jazz"], styles=["Bebop"]
        )
    row = conn.execute("SELECT genres_json, styles_json FROM album_master WHERE id=1").fetchone()
    assert json.loads(row["genres_json"]) == ["Jazz"]
    assert json.loads(row["styles_json"]) == ["Bebop"]
    conn.close()
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
python -m pytest tests/test_album_master_correction_genres.py -v
```
Expected: FAIL

- [ ] **Step 3: Update `get_album_master_correction_state` to select and parse genres/styles**

In `app/db/album_master_correction.py`, find `get_album_master_correction_state`. Update the SELECT query to include `genres_json` and `styles_json`:

```python
            SELECT
              id,
              release_year,
              domain_code,
              source_release_year,
              source_domain_code,
              override_release_year,
              override_domain_code,
              override_note,
              override_title,
              override_artist_or_brand,
              genres_json,
              styles_json
            FROM album_master
```

After `data = dict(row)`, add parsing for genres/styles:

```python
    raw_genres = data.pop("genres_json", None)
    data["genres"] = json.loads(raw_genres) if isinstance(raw_genres, str) and raw_genres.strip() else []
    raw_styles = data.pop("styles_json", None)
    data["styles"] = json.loads(raw_styles) if isinstance(raw_styles, str) and raw_styles.strip() else []
```

Add `import json` at the top of the file if not already present.

- [ ] **Step 4: Update `update_album_master_correction` to accept and store genres/styles**

Add optional params to the function signature:

```python
def update_album_master_correction(
    album_master_id: int,
    *,
    release_year: int | None,
    domain_code: str | None,
    override_note: str | None,
    override_title: str | None = None,
    override_artist_or_brand: str | None = None,
    genres: list[str] | None = None,
    styles: list[str] | None = None,
) -> dict[str, Any] | None:
```

In the function body, before the `UPDATE` statement, add:

```python
    clean_genres = [str(v).strip() for v in (genres or []) if str(v).strip()] if genres is not None else None
    clean_styles = [str(v).strip() for v in (styles or []) if str(v).strip()] if styles is not None else None
```

In the UPDATE statement, add the SET clauses for genres/styles (after `override_artist_or_brand = ?`):

```python
            UPDATE album_master
            SET release_year = ?,
                domain_code = ?,
                source_release_year = ?,
                source_domain_code = ?,
                override_release_year = ?,
                override_domain_code = ?,
                override_note = ?,
                override_title = ?,
                override_artist_or_brand = ?,
                title = COALESCE(?, title),
                artist_or_brand = COALESCE(?, artist_or_brand),
                genres_json = CASE WHEN ? IS NOT NULL THEN ? ELSE genres_json END,
                styles_json = CASE WHEN ? IS NOT NULL THEN ? ELSE styles_json END,
                updated_at = ?
            WHERE id = ?
```

And the parameter tuple:

```python
            (
                effective_release_year,
                effective_domain_code,
                source_release_year,
                source_domain_code,
                release_year_value,
                normalized_domain_code,
                normalized_note,
                normalized_title,
                normalized_artist,
                normalized_title,
                normalized_artist,
                json.dumps(clean_genres, ensure_ascii=True) if clean_genres is not None else None,
                json.dumps(clean_genres, ensure_ascii=True) if clean_genres is not None else None,
                json.dumps(clean_styles, ensure_ascii=True) if clean_styles is not None else None,
                json.dumps(clean_styles, ensure_ascii=True) if clean_styles is not None else None,
                now,
                master_id,
            )
```

- [ ] **Step 5: Run test to confirm it passes**

```bash
python -m pytest tests/test_album_master_correction_genres.py -v
```
Expected: PASS

- [ ] **Step 6: Update `app/schemas.py` — AlbumMasterCorrectionUpdateRequest / Response**

Find `AlbumMasterCorrectionUpdateRequest` (around line 1495) and add:

```python
class AlbumMasterCorrectionUpdateRequest(BaseModel):
    release_year: int | None = Field(default=None, ge=1900, le=2100)
    domain_code: DomainCode | None = None
    override_note: str | None = None
    override_title: str | None = None
    override_artist_or_brand: str | None = None
    genres: list[str] | None = None
    styles: list[str] | None = None
```

Find `AlbumMasterCorrectionUpdateResponse` (around line 1503) and add:

```python
class AlbumMasterCorrectionUpdateResponse(BaseModel):
    album_master_id: int
    release_year: int | None = None
    domain_code: DomainCode | None = None
    source_release_year: int | None = None
    source_domain_code: DomainCode | None = None
    override_release_year: int | None = None
    override_domain_code: DomainCode | None = None
    override_note: str | None = None
    override_title: str | None = None
    override_artist_or_brand: str | None = None
    has_manual_correction: bool = False
    genres: list[str] = Field(default_factory=list)
    styles: list[str] = Field(default_factory=list)
```

- [ ] **Step 7: Update `app/api/album_masters.py` — pass genres/styles to db call and return them**

Find `update_album_master_correction` endpoint (around line 746):

```python
    updated = db.update_album_master_correction(
        album_master_id=album_master_id,
        release_year=payload.release_year,
        domain_code=payload.domain_code,
        override_note=payload.override_note,
        override_title=payload.override_title,
        override_artist_or_brand=payload.override_artist_or_brand,
    )
```

Add genres/styles:

```python
    updated = db.update_album_master_correction(
        album_master_id=album_master_id,
        release_year=payload.release_year,
        domain_code=payload.domain_code,
        override_note=payload.override_note,
        override_title=payload.override_title,
        override_artist_or_brand=payload.override_artist_or_brand,
        genres=payload.genres,
        styles=payload.styles,
    )
```

In the response construction, add:

```python
    return AlbumMasterCorrectionUpdateResponse(
        ...
        genres=updated.get("genres") or [],
        styles=updated.get("styles") or [],
    )
```

- [ ] **Step 8: Commit**

```bash
git add app/db/album_master_correction.py app/schemas.py app/api/album_masters.py \
        tests/test_album_master_correction_genres.py
git commit -m "feat: genres/styles in album_master correction API"
```

---

## Task 7: UI — genres/styles inputs in master edit panel

**Files:**
- Modify: `app/static/index.html`

The master edit panel is `#homeMasterEditDetails` → `#homeMasterCorrectionRow`. We need to add two input rows for genres and styles, wire them to the save button handler, and load them when a master is selected.

- [ ] **Step 1: Find the correction row and save button**

```bash
grep -n "homeMasterCorrectionRow\|homeMasterCorrectionSaveBtn\|homeMasterCorrectionArtist" app/static/index.html | head -10
```

- [ ] **Step 2: Add genres and styles inputs after the note input (before the save button)**

Find the correction note input section:

```html
                  <div style="display:flex; flex-direction:column; gap:2px; flex:2; min-width:120px;">
                    <div class="dashboard-selected-sort-artist-label mini" style="margin:0;">
                      <span data-i18n="media.manage.master.correction.field.note.label">교정 메모</span><span class="help-dot" tabindex="0" data-help="왜 운영 기준을 따로 쓰는지 남기는 메모입니다.">?</span>
                    </div>
                    <input id="homeMasterCorrectionNote" type="text" placeholder="예: Discogs는 재반 기준, 내부 정렬은 원발매 기준" />
                  </div>
                  <button id="homeMasterCorrectionSaveBtn" ...>교정 저장</button>
```

Insert between the note div and the save button:

```html
                  <div style="display:flex; flex-direction:column; gap:2px; flex:1; min-width:100px;">
                    <div class="dashboard-selected-sort-artist-label mini" style="margin:0;">
                      <span>장르 (쉼표 구분)</span>
                    </div>
                    <input id="homeMasterCorrectionGenres" type="text" placeholder="예: Rock, Pop" />
                  </div>
                  <div style="display:flex; flex-direction:column; gap:2px; flex:1; min-width:100px;">
                    <div class="dashboard-selected-sort-artist-label mini" style="margin:0;">
                      <span>스타일 (쉼표 구분)</span>
                    </div>
                    <input id="homeMasterCorrectionStyles" type="text" placeholder="예: Indie Rock, Prog Rock" />
                  </div>
```

- [ ] **Step 3: Find where the correction fields are populated when a master is loaded**

```bash
grep -n "homeMasterCorrectionArtist\|homeMasterCorrectionNote\|homeMasterCorrectionReleaseYear" app/static/index.html | grep "\.value\s*=" | head -10
```

- [ ] **Step 4: Add genre/style field loading in the load handler**

After the line that sets `homeMasterCorrectionNote`, add:

```javascript
$("homeMasterCorrectionGenres").value = joinCommaList(correctionData?.genres || []);
$("homeMasterCorrectionStyles").value = joinCommaList(correctionData?.styles || []);
```

(The exact variable name for the correction data depends on context — use what the surrounding code uses.)

- [ ] **Step 5: Find the save button handler and add genres/styles to the payload**

```bash
grep -n "homeMasterCorrectionSaveBtn\|correction.*save\|saveMasterCorrection" app/static/index.html | grep -v "i18n\|label" | head -10
```

In the save handler, find where the PATCH body is built (it contains `release_year`, `domain_code`, `override_note`, etc.) and add:

```javascript
genres: splitCommaList($("homeMasterCorrectionGenres").value),
styles: splitCommaList($("homeMasterCorrectionStyles").value),
```

- [ ] **Step 6: Find where the correction panel is cleared/reset**

```bash
grep -n "homeMasterCorrectionArtist.*value.*=.*\"\"\|homeMasterCorrectionNote.*value.*=" app/static/index.html | head -5
```

Add clearing for the new fields in the same reset block:

```javascript
$("homeMasterCorrectionGenres").value = "";
$("homeMasterCorrectionStyles").value = "";
```

- [ ] **Step 7: Restart QA server and manually test**

```bash
PID=$(pgrep -f 'uvicorn.*8100'); kill -TERM $PID
sleep 6
ps -eo pid,etime,command | grep 'uvicorn.*8100' | grep -v grep
```

Open http://localhost:8100, navigate to a master with genres, open "마스터 메타 수정", confirm genres/styles appear, edit, save, and verify the values persist.

- [ ] **Step 8: Commit**

```bash
git add app/static/index.html
git commit -m "feat(ui): add genres/styles inputs to master correction panel"
```

---

## Self-Review Checklist

- [x] **Migration**: `album_master.genres_json`/`styles_json` columns added + backfill from `music_item_detail`
- [x] **Write path**: `update_album_master_genres()` writes non-destructively; called after metadata sync
- [x] **Read path**: `album_master_read.py` uses `am.genres_json` directly (no subquery)
- [x] **genre_missing filter**: Updated in both `album_master_read.py` and `metadata_sync.py`
- [x] **Correction API**: genres/styles readable and writable via `PATCH /album-masters/{id}/correction`
- [x] **UI**: master edit panel shows and saves genres/styles
- [x] **No placeholders**: all code is complete
- [x] **Backward compat**: `music_item_detail.genres_json`/`styles_json` unchanged; per-item edit still works
