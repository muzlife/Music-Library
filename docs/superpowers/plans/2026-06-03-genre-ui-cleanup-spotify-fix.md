# Genre UI Cleanup + Spotify Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove genre from per-item display, move genre edit to master correction only, wire genre ingestion on create/update, and restore Spotify player in search and manage.

**Architecture:** All UI changes are in `app/static/index.html` (HTML + JS). Backend change is `app/db/owned_item_write.py` — inline SQL UPDATE on the same `conn` already open during create/update. No new functions needed.

**Tech Stack:** FastAPI, SQLite, vanilla JS, HTML

---

## File Map

| File | Change |
|------|--------|
| `app/static/index.html` | Remove genre span (1 line), remove editStyles/editGenres HTML+JS (8 sites), fix Spotify badge attributes, add Spotify player button in manage panel |
| `app/db/owned_item_write.py` | Add `import json`, UPDATE album_master genres inline after `_upsert_music_item_detail_in_conn` (create + update paths) |

---

## Task 1: Remove genre from owned-item card

**Files:**
- Modify: `app/static/index.html:49129,49184`

The function `homeMasterRelatedItemHtml` renders each owned item row in the "보유 상품" list. Line 49129 builds `genreText`, line 49184 renders it. Both become dead code once the genre span is removed.

- [ ] **Step 1: Remove the genre span and its variable**

Find (line 49129):
```javascript
      const genreText = joinCommaList(row.genres || []) || "-";
```
Delete that line entirely.

Find (line 49184):
```html
                <span>${escapeHtml(t("common.meta.genre"))}: ${escapeHtml(genreText)}</span>
```
Delete that line entirely.

- [ ] **Step 2: Verify no remaining reference to genreText in that function**

```bash
grep -n "genreText" /Volumes/Data/Works/07.hahahoho/app/static/index.html
```
Expected: 0 results.

- [ ] **Step 3: Commit**

```bash
git add app/static/index.html
git commit -m "feat(ui): remove genre from owned item card in manage panel"
```

---

## Task 2: Remove editGenres/editStyles from item edit form

**Files:**
- Modify: `app/static/index.html` (8 sites listed below)

The item edit form has `#editStyles` (visible input, lines 18308–18309) and `#editGenres` (hidden input, line 18573). Genres are now edited via master correction only (`#homeMasterCorrectionGenres`/`#homeMasterCorrectionStyles`, already added in a prior task). Remove all references to the item-level fields.

**Sites to change:**

| Line | What | Action |
|------|------|--------|
| 18308–18309 | `<label for="editStyles">` + `<input id="editStyles">` — inside a `<div class="span-2">` | Remove the entire `<div class="span-2">` wrapper |
| 18573 | `<input id="editGenres" type="hidden" />` | Remove this line |
| 46835–46836 | `$("editGenres").value = "";` / `$("editStyles").value = "";` | Remove both lines |
| 47138–47139 | `$("editGenres").value = joinCommaList(c.genres);` / `$("editStyles").value = joinCommaList(c.styles);` | Remove both lines |
| 49909–49910 | `$("editGenres").value = joinCommaList(data.music_detail?.genres \|\| []);` / `$("editStyles").value = ...` | Remove both lines |
| 50095–50096 | `genres: splitCommaList($("editGenres").value),` / `styles: splitCommaList($("editStyles").value),` | Remove both lines |

- [ ] **Step 1: Remove the editStyles HTML block (lines 18308–18309 + wrapper div)**

Find the block:
```html
                        <div class="span-2">
                          <label for="editStyles" data-i18n="media.manage.field.styles.label">스타일 (쉼표 구분)</label>
                          <input id="editStyles" data-i18n-placeholder="media.manage.field.styles.placeholder" placeholder="예: K-Rock, Prog Rock" />
                        </div>
```
Delete the entire `<div class="span-2">` block (3 lines).

- [ ] **Step 2: Remove the editGenres hidden input (line 18573)**

Find:
```html
                          <input id="editGenres" type="hidden" />
```
Delete that line.

- [ ] **Step 3: Remove clear references (lines 46835–46836)**

Find:
```javascript
      $("editGenres").value = "";
      $("editStyles").value = "";
```
Delete both lines.

- [ ] **Step 4: Remove load-from-master references (lines 47138–47139)**

Find:
```javascript
        $("editGenres").value = joinCommaList(c.genres);
        $("editStyles").value = joinCommaList(c.styles);
```
Delete both lines.

- [ ] **Step 5: Remove load-from-item-detail references (lines 49909–49910)**

Find:
```javascript
      $("editGenres").value = joinCommaList(data.music_detail?.genres || []);
      $("editStyles").value = joinCommaList(data.music_detail?.styles || []);
```
Delete both lines.

- [ ] **Step 6: Remove save/submit references (lines 50095–50096)**

Find:
```javascript
          genres: splitCommaList($("editGenres").value),
          styles: splitCommaList($("editStyles").value),
```
Delete both lines.

- [ ] **Step 7: Verify no remaining editGenres/editStyles outside master correction**

```bash
grep -n "editGenres\|editStyles" /Volumes/Data/Works/07.hahahoho/app/static/index.html | grep -v "homeMasterCorrection"
```
Expected: 0 results.

- [ ] **Step 8: Commit**

```bash
git add app/static/index.html
git commit -m "feat(ui): remove genre/style fields from item edit form (now master-level only)"
```

---

## Task 3: Write genres to album_master on create/update owned item

**Files:**
- Modify: `app/db/owned_item_write.py:47,138,296`

When an owned item is created or updated with `music_detail` that contains genres/styles AND a `linked_album_master_id`, write those genres/styles to `album_master.genres_json`/`styles_json` using the same open `conn` (stays inside the transaction).

- [ ] **Step 1: Add `import json` after the existing imports**

Find (line 47):
```python
import sqlite3
from typing import Any
```
Replace with:
```python
import json
import sqlite3
from typing import Any
```

- [ ] **Step 2: Add genre update after the create path's `_upsert_music_item_detail_in_conn` call**

Find (lines 136–141 — create path):
```python
        music_detail = payload.get("music_detail")
        if music_detail:
            _upsert_music_item_detail_in_conn(conn, owned_item_id=owned_item_id, music_detail=music_detail, now=now)
        goods_detail = payload.get("goods_detail")
```
Replace with:
```python
        music_detail = payload.get("music_detail")
        if music_detail:
            _upsert_music_item_detail_in_conn(conn, owned_item_id=owned_item_id, music_detail=music_detail, now=now)
            _sync_music_detail_genres_to_master_in_conn(conn, payload, music_detail, now)
        goods_detail = payload.get("goods_detail")
```

- [ ] **Step 3: Add genre update after the update path's `_upsert_music_item_detail_in_conn` call**

Find (lines 294–298 — update path):
```python
        music_detail = payload.get("music_detail")
        if music_detail:
            _upsert_music_item_detail_in_conn(conn, owned_item_id=owned_item_id, music_detail=music_detail, now=now)
        else:
```
Replace with:
```python
        music_detail = payload.get("music_detail")
        if music_detail:
            _upsert_music_item_detail_in_conn(conn, owned_item_id=owned_item_id, music_detail=music_detail, now=now)
            _sync_music_detail_genres_to_master_in_conn(conn, payload, music_detail, now)
        else:
```

- [ ] **Step 4: Add the helper function near the top of the module (after imports, before the first `def`)**

Add this function right before the first `def` in the file (after all imports):

```python
def _sync_music_detail_genres_to_master_in_conn(
    conn: "sqlite3.Connection",
    payload: dict,
    music_detail: dict,
    now: str,
) -> None:
    linked_master_id = int(payload.get("linked_album_master_id") or 0)
    if linked_master_id <= 0:
        return
    clean_genres = [str(v).strip() for v in (music_detail.get("genres") or []) if str(v).strip()]
    clean_styles = [str(v).strip() for v in (music_detail.get("styles") or []) if str(v).strip()]
    if clean_genres:
        conn.execute(
            "UPDATE album_master SET genres_json = ?, updated_at = ? WHERE id = ?",
            (json.dumps(clean_genres, ensure_ascii=True), now, linked_master_id),
        )
    if clean_styles:
        conn.execute(
            "UPDATE album_master SET styles_json = ?, updated_at = ? WHERE id = ?",
            (json.dumps(clean_styles, ensure_ascii=True), now, linked_master_id),
        )
```

- [ ] **Step 5: Syntax check**

```bash
python3 -m py_compile /Volumes/Data/Works/07.hahahoho/app/db/owned_item_write.py && echo "OK"
```
Expected: `OK`

- [ ] **Step 6: Smoke test**

```bash
cd /Volumes/Data/Works/07.hahahoho
python3 -c "
from app.db import get_conn
from app.db.owned_item_write import _sync_music_detail_genres_to_master_in_conn
import json

# Find a master with a linked owned item
with get_conn() as conn:
    row = conn.execute(
        'SELECT oi.id, oi.linked_album_master_id FROM owned_item oi WHERE oi.linked_album_master_id IS NOT NULL LIMIT 1'
    ).fetchone()

if row:
    master_id = row['linked_album_master_id']
    payload = {'linked_album_master_id': master_id}
    detail = {'genres': ['TestGenre'], 'styles': ['TestStyle']}
    with get_conn() as conn:
        _sync_music_detail_genres_to_master_in_conn(conn, payload, detail, '2024-01-01T00:00:00Z')
        r = conn.execute('SELECT genres_json FROM album_master WHERE id=?', (master_id,)).fetchone()
        print('genres_json:', r['genres_json'])
        # restore
        conn.execute('UPDATE album_master SET genres_json=NULL WHERE id=?', (master_id,))
    print('smoke test passed')
"
```
Expected: `genres_json: [\"TestGenre\"]` then `smoke test passed`.

- [ ] **Step 7: Commit**

```bash
git add app/db/owned_item_write.py
git commit -m "feat(db): sync genres to album_master on create/update owned item"
```

---

## Task 4: Fix Spotify — search badge + manage player button

**Files:**
- Modify: `app/static/index.html:47752,49344-49351`

Two separate sub-fixes in one task:

**4a — Search badge (미디어>검색):** The `.spotify-badge` in `homeResultItemHtml` (line 47752) has no `data-sp-master`/`data-sp-album` attributes. The click handler at line 41391 reads those attributes and calls `spotifyTogglePanel(mid, aid)`. Without them nothing happens — and the badge may not even render if any guard around it depends on the attributes.

**4b — Manage panel player (미디어>관리):** `#homeMasterMetaSpotifyText` displays the Spotify album ID as plain text (line 49348). Need to replace the plain text with a clickable Spotify badge that calls `spotifyTogglePanel(masterIdVal, spId)`. `masterIdVal` is in scope at that code point.

- [ ] **Step 1: Fix search badge — add data attributes (line 47752)**

Find:
```javascript
${row.spotify_album_id ? `<span class="spotify-badge">Spotify</span>` : ""}
```
Replace with:
```javascript
${row.spotify_album_id ? `<span class="spotify-badge" data-sp-master="${escapeHtml(String(row.id))}" data-sp-album="${escapeHtml(row.spotify_album_id)}">Spotify</span>` : ""}
```

- [ ] **Step 2: Fix manage panel — replace plain text with badge + player toggle (lines 49344–49351)**

Find:
```javascript
      const spEditRow = $("homeMasterMetaSpotifyEditRow");
      if (!spEditRow || spEditRow.style.display === "none") {
        const spId = String(homeMasterInfo?.spotify_album_id || "").trim();
        const spText = $("homeMasterMetaSpotifyText");
        if (spText) spText.textContent = `Spotify Album Code: ${spId || "-"}`;
        const spRow = $("homeMasterMetaSpotifyRow");
        if (spRow) spRow.style.display = "flex";
      }
```
Replace with:
```javascript
      const spEditRow = $("homeMasterMetaSpotifyEditRow");
      if (!spEditRow || spEditRow.style.display === "none") {
        const spId = String(homeMasterInfo?.spotify_album_id || "").trim();
        const spText = $("homeMasterMetaSpotifyText");
        if (spText) {
          if (spId) {
            spText.innerHTML = `Spotify: ${escapeHtml(spId)} <span class="spotify-badge" data-sp-master="${masterIdVal}" data-sp-album="${escapeHtml(spId)}" style="cursor:pointer;vertical-align:middle;">▶</span>`;
          } else {
            spText.textContent = "Spotify Album Code: -";
          }
        }
        const spRow = $("homeMasterMetaSpotifyRow");
        if (spRow) spRow.style.display = "flex";
      }
```

- [ ] **Step 3: Verify the badge click handler will work**

The click handler at line ~41387 does:
```javascript
var mid = b.getAttribute('data-sp-master');
var aid = b.getAttribute('data-sp-album');
if (mid && aid) spotifyTogglePanel(mid, aid);
```

`spotifyTogglePanel` for the manage tab (`inManage`) targets `#homeMasterSpotifyEmbed` (exists at line 18038). For the search tab (`inSearch`) targets `#searchSpotifyPanel` + `#searchSpotifyEmbed` (exist at line 17921-17922). ✅ No handler changes needed.

- [ ] **Step 4: Restart QA server and manual smoke test**

```bash
PID=$(pgrep -f 'uvicorn.*8100'); kill -TERM $PID; sleep 5
nohup python3 -m uvicorn app.main:app --port 8100 --host 127.0.0.1 \
  --app-dir /Volumes/Data/Works/07.hahahoho > /tmp/qa_test.log 2>&1 &
sleep 4
curl -s http://localhost:8100/ | head -3
```

Manual checks:
1. **검색 탭**: 마스터 검색 → Spotify 연계 마스터의 "Spotify" 배지 클릭 → 우측 패널에 플레이어 노출
2. **관리 탭**: 마스터 선택 → Spotify Album Code 옆 "▶" 배지 클릭 → `#homeMasterSpotifyEmbed`에 플레이어 노출

- [ ] **Step 5: Commit**

```bash
git add app/static/index.html
git commit -m "fix(ui): restore Spotify player — search badge data attrs + manage panel play button"
```

---

## Self-Review

- [x] Task 1: removes `genreText` variable and render span — no orphan refs
- [x] Task 2: all 8 `editGenres`/`editStyles` sites removed, master correction fields untouched
- [x] Task 3: helper function uses same `conn` (no new connection), placed before first `def`, `import json` added
- [x] Task 4: `data-sp-master`/`data-sp-album` match what the existing click handler reads (`getAttribute`); `masterIdVal` is defined at line ~49337 (in same block); `innerHTML` uses `escapeHtml` for untrusted values
- [x] No placeholders, no TBDs
