# Admin Density & Form Compaction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the admin area ~20–30% denser, reflow direct registration into two rows, minimize edit form rows, and add a clear expand/collapse arrow to the “상품 수정” button.

**Architecture:** Apply admin-only CSS density tokens via `body[data-shell-mode="admin"]` and reflow specific admin media forms to 12-column grids. Update search list edit button rendering to show ▲/▼ with `aria-expanded` state using the existing admin search list event wiring.

**Tech Stack:** HTML/CSS/JS in `app/static/index.html`, Python pytest for HTML string assertions.

---

## File Map

**Modify:**
- `/Volumes/Works/07.hahahoho/.worktrees/admin-density-plan/app/static/index.html`

**Create:**
- `/Volumes/Works/07.hahahoho/.worktrees/admin-density-plan/tests/test_admin_density_compaction.py`

---

### Task 1: Add Admin Density Tokens + Tests

**Files:**
- Create: `/Volumes/Works/07.hahahoho/.worktrees/admin-density-plan/tests/test_admin_density_compaction.py`
- Modify: `/Volumes/Works/07.hahahoho/.worktrees/admin-density-plan/app/static/index.html`

- [ ] **Step 1: Write failing tests for admin density CSS**

```python
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "app" / "static"


def read_static_html(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


def test_admin_density_overrides_define_compact_tokens():
    html = read_static_html("index.html")
    assert 'body[data-shell-mode="admin"] input' in html
    assert 'body[data-shell-mode="admin"] label' in html
    assert 'body[data-shell-mode="admin"] .btn' in html
    assert 'body[data-shell-mode="admin"] .section-divider' in html
```

- [ ] **Step 2: Run tests to see them fail**

Run:
```bash
cd /Volumes/Works/07.hahahoho/.worktrees/admin-density-plan
pytest -q tests/test_admin_density_compaction.py::test_admin_density_overrides_define_compact_tokens
```
Expected: FAIL (selectors not present yet)

- [ ] **Step 3: Implement admin density tokens**

Add CSS overrides scoped to admin (ensure every selector is prefixed with `body[data-shell-mode="admin"]`):
- `body[data-shell-mode="admin"] label` → `font-size: 0.68rem; margin-bottom: 1px;`
- `body[data-shell-mode="admin"] input, select, textarea` → `min-height: 28px; padding: 2px 6px; font-size: 0.86rem; line-height: 1.1;`
- `body[data-shell-mode="admin"] .btn` → `min-height: 32px; padding: 0 10px; font-size: 0.86rem;`
- `body[data-shell-mode="admin"] .btn.tiny` → `min-height: 26px; padding: 0 8px; font-size: 0.66rem;`
- `body[data-shell-mode="admin"] .section-divider` → `margin: 6px 0 4px; padding-top: 4px;`
- `body[data-shell-mode="admin"] .card` → `padding: 6px;`
- `body[data-shell-mode="admin"] .grid, .grid-3, .grid-6, .home-edit-grid-6, .home-search-grid-top, .home-search-grid-bottom` → `gap: 4px;`
Add explicit overrides to exclude non-text inputs from the compact text-input sizing:
- `body[data-shell-mode="admin"] input[type="checkbox"], input[type="radio"], input[type="file"], input[type="hidden"]` → reset `min-height`, `padding`, `line-height`, `font-size` to defaults.

Note: keep other styles unchanged; only admin scope changes.

- [ ] **Step 4: Run tests to confirm pass**

Run:
```bash
cd /Volumes/Works/07.hahahoho/.worktrees/admin-density-plan
pytest -q tests/test_admin_density_compaction.py::test_admin_density_overrides_define_compact_tokens
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add /Volumes/Works/07.hahahoho/.worktrees/admin-density-plan/app/static/index.html \
        /Volumes/Works/07.hahahoho/.worktrees/admin-density-plan/tests/test_admin_density_compaction.py
git commit -m "style: add admin density tokens"
```

---

### Task 2: Reflow Direct Register (2 rows) + Tests

**Files:**
- Modify: `/Volumes/Works/07.hahahoho/.worktrees/admin-density-plan/app/static/index.html`
- Modify: `/Volumes/Works/07.hahahoho/.worktrees/admin-density-plan/tests/test_admin_density_compaction.py`

- [ ] **Step 1: Add failing test for direct register two-row layout**

```python
def test_direct_register_uses_two_grid_rows_for_all_fields():
    html = read_static_html("index.html")
    block = html.split('data-i18n="media.register.direct.title"', 1)[1].split('id="quickSizeGroup"', 1)[0]
    assert block.count('class="grid-12"') == 2
    assert 'id="quickItemName"' in block and 'span-4' in block
```

- [ ] **Step 2: Run test (expect fail)**

```bash
cd /Volumes/Works/07.hahahoho/.worktrees/admin-density-plan
pytest -q tests/test_admin_density_compaction.py::test_direct_register_uses_two_grid_rows_for_all_fields
```
Expected: FAIL

- [ ] **Step 3: Implement 12-column grid + consolidate wrappers**

Add CSS:
- `.grid-12 { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 4px; }`
- `.span-4 { grid-column: span 4; }`

Replace the three separate direct-register grids with **two** `grid-12` wrappers:
- Move all fields from the third grid (domain, purchase price, currency) into the second row.
- Resulting layout:
  - Row 1: category (span-2), quantity (default), artist (span-3), item_name (span-4), slot (span-2)
  - Row 2: label (span-2), release date (span-2), cover url (span-2), memory note (span-2), domain (span-2), purchase price (default), currency (default)

- [ ] **Step 4: Add responsive handling for `grid-12` and span reset**

In existing breakpoints (`@media (max-width: 1280px)` and `@media (max-width: 1080px)`), add:
- `grid-12` → `repeat(8, minmax(0, 1fr))` at 1280
- `grid-12` → `repeat(6, minmax(0, 1fr))` at 1080

At `@media (max-width: 760px)`:
- Set `.grid-12 { grid-template-columns: 1fr; }`
- Reset span helpers inside grid-12 to prevent overflow:
  - `.grid-12 > * { grid-column: auto; }`
  - `.grid-12--from-6 > * { grid-column: auto; }`

- [ ] **Step 5: Run test (expect pass)**

```bash
cd /Volumes/Works/07.hahahoho/.worktrees/admin-density-plan
pytest -q tests/test_admin_density_compaction.py::test_direct_register_uses_two_grid_rows_for_all_fields
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add /Volumes/Works/07.hahahoho/.worktrees/admin-density-plan/app/static/index.html \
        /Volumes/Works/07.hahahoho/.worktrees/admin-density-plan/tests/test_admin_density_compaction.py
git commit -m "ui: reflow direct register to two rows"
```

---

### Task 3: Compact Master/Item Edit Grids + Tests

**Files:**
- Modify: `/Volumes/Works/07.hahahoho/.worktrees/admin-density-plan/app/static/index.html`
- Modify: `/Volumes/Works/07.hahahoho/.worktrees/admin-density-plan/tests/test_admin_density_compaction.py`

- [ ] **Step 1: Add failing test for edit grid compaction**

```python
def test_manage_edit_grids_use_grid12_mapping():
    html = read_static_html("index.html")
    assert 'id="homeEditMusicMetaFieldsA" class="grid-12 grid-12--from-6"' in html
    assert 'home-product-grid" class="grid-12 grid-12--from-6' in html
```

- [ ] **Step 2: Run test (expect fail)**

```bash
cd /Volumes/Works/07.hahahoho/.worktrees/admin-density-plan
pytest -q tests/test_admin_density_compaction.py::test_manage_edit_grids_use_grid12_mapping
```
Expected: FAIL

- [ ] **Step 3: Implement 6→12 mapping helper and apply to edit grids**

Add CSS mapping helper:
- `.grid-12--from-6 > * { grid-column: span 2; }`
- `.grid-12--from-6 .span-2 { grid-column: span 4; }`
- `.grid-12--from-6 .span-3 { grid-column: span 6; }`
- `.grid-12--from-6 .span-4 { grid-column: span 8; }`
- `.grid-12--from-6 .span-5 { grid-column: span 10; }`

Update manage/edit grids to `grid-12 grid-12--from-6`:
- `#homeEditMusicMetaFieldsA`, `#homeEditMusicMetaFieldsB`, `#homeEditMusicMetaFieldsC`, `#homeEditMusicInfoRow`
- `.home-edit-grid-6.home-product-grid` blocks

This keeps legacy “6-column” sizing while reducing rows when combined with denser gaps.

- [ ] **Step 4: Run test (expect pass)**

```bash
cd /Volumes/Works/07.hahahoho/.worktrees/admin-density-plan
pytest -q tests/test_admin_density_compaction.py::test_manage_edit_grids_use_grid12_mapping
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add /Volumes/Works/07.hahahoho/.worktrees/admin-density-plan/app/static/index.html \
        /Volumes/Works/07.hahahoho/.worktrees/admin-density-plan/tests/test_admin_density_compaction.py
git commit -m "ui: compact manage edit grids"
```

---

### Task 4: Search List Edit Button Arrow + Tests

**Files:**
- Modify: `/Volumes/Works/07.hahahoho/.worktrees/admin-density-plan/app/static/index.html`
- Modify: `/Volumes/Works/07.hahahoho/.worktrees/admin-density-plan/tests/test_admin_density_compaction.py`

- [ ] **Step 1: Add failing test for arrow indicator**

```python
def test_search_list_edit_button_has_arrow_indicator():
    html = read_static_html("index.html")
    block = html.split("function homeMasterMemberPreviewHtml(item", 1)[1].split("function getHomeMasterVisiblePreviewItems", 1)[0]
    assert 'data-home-open-owned-editor' in block
    assert 'class="edit-arrow"' in block
    assert 'aria-expanded' in block
```

- [ ] **Step 2: Run test (expect fail)**

```bash
cd /Volumes/Works/07.hahahoho/.worktrees/admin-density-plan
pytest -q tests/test_admin_density_compaction.py::test_search_list_edit_button_has_arrow_indicator
```
Expected: FAIL

- [ ] **Step 3: Implement arrow indicator using current state model**

Update `homeMasterMemberPreviewHtml`:
- Add expanded state derived from current inline editor:
  - `const isInlineExpanded = ownedItemId > 0 && ownedItemId === Number(homeSelectedItemId || 0) && !homeInlineEditorCollapsed;`
- Render a **new** edit button to preserve label-id display:
  - Keep label id as non-button or separate span
  - Add `<button ... data-home-open-owned-editor="${ownedItemId}" aria-expanded="${isInlineExpanded ? "true" : "false"}">상품 수정 <span class="edit-arrow">${isInlineExpanded ? "▲" : "▼"}</span></button>`
- Add minimal CSS for `.edit-arrow` (font-size 0.7rem, margin-left 4px, opacity 0.7)
- When toggling inline editor in `handleHomeRelatedListClick`, add `renderHomeSearchResults(homeSearchResults);` after `syncHomeMasterInlineEditor();` so the arrow updates immediately.

- [ ] **Step 4: Run test (expect pass)**

```bash
cd /Volumes/Works/07.hahahoho/.worktrees/admin-density-plan
pytest -q tests/test_admin_density_compaction.py::test_search_list_edit_button_has_arrow_indicator
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add /Volumes/Works/07.hahahoho/.worktrees/admin-density-plan/app/static/index.html \
        /Volumes/Works/07.hahahoho/.worktrees/admin-density-plan/tests/test_admin_density_compaction.py
git commit -m "ui: show edit expand arrow in search list"
```

---

### Task 5: Targeted Test Pass + Visual Spot Checks

- [ ] **Step 1: Run the new test file**

```bash
cd /Volumes/Works/07.hahahoho/.worktrees/admin-density-plan
pytest -q tests/test_admin_density_compaction.py
```
Expected: PASS

- [ ] **Step 2: Visual verification (admin only)**

Open admin and verify:
- Desktop width >=1280px: direct register shows 2 rows with all fields visible.
- Narrower width ~1080px: direct register wraps naturally without overlaps.
- `/ops` and `/ops/cabinets` unchanged (admin-scoped CSS not leaking).

- [ ] **Step 3: Commit any final tweaks**

```bash
git status -sb
```
If clean, no commit needed; otherwise commit with a small fix message.

---

## Notes
- Baseline `pytest -q` currently fails (pre-existing). Use targeted tests from this plan to validate changes.
- If any fields become too narrow at desktop widths, adjust `span-*` values within the 12-col grid while keeping the 2-row constraint for direct register.
