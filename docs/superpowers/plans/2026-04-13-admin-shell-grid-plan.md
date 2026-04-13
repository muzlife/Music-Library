# Admin Shell Grid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the admin shell into a header + left-nav + content grid, add menu accordion persistence, and collapse section descriptions by default while keeping ops scope removals minimal.

**Architecture:** All changes land in `app/static/index.html` (HTML/CSS/JS) plus string-based pytest assertions in `tests/`. The admin shell uses a two-row grid: header spans full width; row 2 is nav + content. Nav/content scroll independently. Menu accordion state persists in sessionStorage and deep-linking opens the parent.

**Tech Stack:** HTML, CSS, vanilla JS, pytest.

---

## File Map

**Modify**
- `/Volumes/Works/07.hahahoho/.worktrees/admin-density-compact/app/static/index.html`
  - Admin shell grid CSS (`body[data-shell-mode="admin"] .wrap`, `#adminSideNav`, `.primary-shell`, `#appHero`)
  - Header positioning (grid placement)
  - Nav icon-only rail CSS at `<=1080px`
  - Menu accordion behavior (sessionStorage + deep-link open)
  - Section description toggle wiring
  - Remove Ops left nav slot and collectibles panel

**Modify Tests**
- `/Volumes/Works/07.hahahoho/.worktrees/admin-density-compact/tests/test_ops_shell_bootstrap.py`
- `/Volumes/Works/07.hahahoho/.worktrees/admin-density-compact/tests/test_admin_density_compaction.py`

---

### Task 1: Add failing tests for admin grid + ops removals

**Files:**
- Modify: `/Volumes/Works/07.hahahoho/.worktrees/admin-density-compact/tests/test_ops_shell_bootstrap.py`
- Modify: `/Volumes/Works/07.hahahoho/.worktrees/admin-density-compact/tests/test_admin_density_compaction.py`

- [ ] **Step 1: Add new failing assertions in `test_ops_shell_bootstrap.py`**

```python
# new test (or extend existing)

def test_index_admin_shell_grid_uses_header_and_body_rows():
    html = read_static_html("index.html")
    wrap_block = html.split('<div class="wrap">', 1)[1].split('<div class="primary-shell">', 1)[0]
    assert 'id="appHero"' in wrap_block
    assert 'id="adminSideNav"' in html
    wrap_block = html.split('body[data-shell-mode="admin"] .wrap {', 1)[1].split("}", 1)[0]
    assert "display: grid;" in wrap_block
    assert "grid-template-rows: auto minmax(0, 1fr);" in wrap_block
    assert "grid-template-columns: var(--admin-side-nav-width) minmax(0, 1fr);" in wrap_block

    hero_block = html.split('body[data-shell-mode="admin"] #appHero {', 1)[1].split("}", 1)[0]
    assert "grid-column: 1 / -1;" in hero_block
    assert "grid-row: 1;" in hero_block

    nav_block = html.split('body[data-shell-mode="admin"] #adminSideNav {', 1)[1].split("}", 1)[0]
    assert "grid-column: 1;" in nav_block
    assert "grid-row: 2;" in nav_block
    assert "overflow-y: auto;" in nav_block

    main_block = html.split('body[data-shell-mode="admin"] .primary-shell {', 1)[1].split("}", 1)[0]
    assert "grid-column: 2;" in main_block
    assert "grid-row: 2;" in main_block
    assert "overflow-y: auto;" in main_block
```

- [ ] **Step 2: Add failing assertions for ops removals**

```python

def test_ops_home_hides_primary_side_nav_slot():
    html = read_static_html("index.html")
    ops_block = html.split('body[data-shell-mode="ops"] .primary-side-nav-slot {', 1)[1].split("}", 1)[0]
    assert "display: none;" in ops_block


def test_admin_removes_linked_collectibles_panel():
    html = read_static_html("index.html")
    assert 'id="homeMasterGoodsSection"' not in html
    assert 'id="homeLinkedGoodsPanel"' not in html
```

- [ ] **Step 3: Add failing assertion for icon-only rail**

```python

def test_admin_nav_icon_rail_at_1080():
    html = read_static_html("index.html")
    block_1080 = html.split("@media (max-width: 1080px)", 1)[1].split("@media", 1)[0]
    assert "body[data-shell-mode=\"admin\"] #adminSideNav.admin-side-nav--icon" in block_1080
    assert "width: var(--admin-side-nav-icon-width);" in block_1080
```

- [ ] **Step 4: Run the tests to confirm failure**

Run: `pytest /Volumes/Works/07.hahahoho/.worktrees/admin-density-compact/tests/test_ops_shell_bootstrap.py::test_index_admin_shell_grid_uses_header_and_body_rows /Volumes/Works/07.hahahoho/.worktrees/admin-density-compact/tests/test_ops_shell_bootstrap.py::test_ops_home_hides_primary_side_nav_slot /Volumes/Works/07.hahahoho/.worktrees/admin-density-compact/tests/test_ops_shell_bootstrap.py::test_admin_removes_linked_collectibles_panel /Volumes/Works/07.hahahoho/.worktrees/admin-density-compact/tests/test_ops_shell_bootstrap.py::test_admin_nav_icon_rail_at_1080 -v`

Expected: FAIL (new selectors not yet present).

- [ ] **Step 5: Commit tests**

```bash
git add tests/test_ops_shell_bootstrap.py tests/test_admin_density_compaction.py
git commit -m "test: define admin shell grid + ops removal expectations"
```

---

### Task 2: Implement admin shell grid (header + nav + content)

**Files:**
- Modify: `/Volumes/Works/07.hahahoho/.worktrees/admin-density-compact/app/static/index.html`

- [ ] **Step 1: Move header/nav nodes to be direct grid items**

Move these nodes so they are direct children of `.wrap`:
- `#appHero`
- `#opsHomeHero`
- `#shellUtilityBar`
- `#adminSideNav`

This ensures the grid placement rules apply to header/nav/content.

- [ ] **Step 2: Update admin `.wrap` grid and remove left margin**

```css
body[data-shell-mode="admin"] .wrap {
  display: grid;
  grid-template-columns: var(--admin-side-nav-width) minmax(0, 1fr);
  grid-template-rows: auto minmax(0, 1fr);
  gap: var(--admin-side-nav-gap);
  width: 100%;
  margin: 8px 12px 16px;
  min-height: 100vh;
}
```

- [ ] **Step 3: Place header in row 1 spanning full width**

```css
body[data-shell-mode="admin"] #appHero {
  grid-column: 1 / -1;
  grid-row: 1;
}
```

- [ ] **Step 4: Place admin nav + content in row 2 and enable independent scroll**

```css
body[data-shell-mode="admin"] #adminSideNav {
  grid-column: 1;
  grid-row: 2;
  align-self: stretch;
  overflow-y: auto;
  max-height: 100%;
}

body[data-shell-mode="admin"] .primary-shell {
  grid-column: 2;
  grid-row: 2;
  min-width: 0;
  overflow-y: auto;
  max-height: 100%;
}
```

- [ ] **Step 5: Remove nav fixed positioning + top offset**

```css
.admin-side-nav {
  position: static;
  top: auto;
  left: auto;
}
```

- [ ] **Step 6: Run tests from Task 1**

Run: same pytest command from Task 1.
Expected: PASS for grid and nav placement checks (ops removal still failing until Task 4).

- [ ] **Step 7: Commit**

```bash
git add app/static/index.html
git commit -m "feat: move admin shell to header+nav+content grid"
```

---

### Task 3: Menu accordion persistence + icon-only rail (<=1080)

**Files:**
- Modify: `/Volumes/Works/07.hahahoho/.worktrees/admin-density-compact/app/static/index.html`

- [ ] **Step 1: Add sessionStorage helpers**

```js
const ADMIN_NAV_STATE_KEY = "adminNavOpen";
function readAdminNavState() {
  try { return sessionStorage.getItem(ADMIN_NAV_STATE_KEY) || ""; } catch (_) { return ""; }
}
function writeAdminNavState(value) {
  try { sessionStorage.setItem(ADMIN_NAV_STATE_KEY, value); } catch (_) {}
}
```

- [ ] **Step 2: Update `syncAdminSidebarNav()` to respect stored open state and deep-link**

```js
const storedMain = readAdminNavState();
const activeMain = activeAdminMainTab();
const activeSub = resolveActiveAdminSubnavKey();
const targetMain = activeSub ? activeMain : (storedMain || activeMain);

// ensure parent opens on deep-link
const mainToOpen = activeSub ? activeMain : targetMain;
```

- [ ] **Step 3: When top-level buttons are clicked, store the open state**

```js
if (navId) {
  writeAdminNavState(navId);
  collapseAdminSideNavAccordions(navId);
  routeAdminSideNavTop(navId);
}
```

- [ ] **Step 4: Add icon-only rail styles**

```css
:root { --admin-side-nav-icon-width: 56px; }

@media (max-width: 1080px) {
  body[data-shell-mode="admin"] #adminSideNav.admin-side-nav--icon {
    width: var(--admin-side-nav-icon-width);
  }
  body[data-shell-mode="admin"] #adminSideNav.admin-side-nav--icon .admin-side-nav-button,
  body[data-shell-mode="admin"] #adminSideNav.admin-side-nav--icon .admin-side-nav-subitem {
    justify-content: center;
    padding-left: 0;
    padding-right: 0;
    font-size: 0;
  }
  body[data-shell-mode="admin"] #adminSideNav.admin-side-nav--icon .admin-side-nav-button::before {
    content: attr(data-admin-nav-icon);
    font-size: 0.78rem;
  }
  body[data-shell-mode="admin"] #adminSideNav.admin-side-nav--icon .admin-side-nav-submenu {
    display: none !important;
  }
}
```

- [ ] **Step 5: Add `data-admin-nav-icon` attributes to top buttons**

```html
<button class="admin-side-nav-button" data-admin-nav="media" data-admin-nav-icon="M" ...>미디어</button>
<button class="admin-side-nav-button" data-admin-nav="collectibles" data-admin-nav-icon="C" ...>컬렉터블</button>
<button class="admin-side-nav-button" data-admin-nav="ops" data-admin-nav-icon="O" ...>운영/연계</button>
```

- [ ] **Step 6: Add a media query toggle hook in JS**

```js
const adminNav = $("adminSideNav");
const navMql = window.matchMedia("(max-width: 1080px)");
function syncAdminNavIconMode() {
  if (!adminNav) return;
  adminNav.classList.toggle("admin-side-nav--icon", navMql.matches);
}
navMql.addEventListener("change", syncAdminNavIconMode);
syncAdminNavIconMode();
```

- [ ] **Step 7: Run tests**

Run: pytest command from Task 1.
Expected: PASS for icon rail assertion and new storage logic (string checks only).

- [ ] **Step 8: Commit**

```bash
git add app/static/index.html
git commit -m "feat: persist admin nav accordion + icon rail"
```

---

### Task 4: Section description toggles (collapsed by default)

**Files:**
- Modify: `/Volumes/Works/07.hahahoho/.worktrees/admin-density-compact/app/static/index.html`
- Modify: `/Volumes/Works/07.hahahoho/.worktrees/admin-density-compact/tests/test_ops_shell_bootstrap.py`

- [ ] **Step 1: Mark description blocks and add toggle buttons**

Apply to these top-level description blocks (collapsed by default):
- `data-i18n="media.subtitle"`
- `data-i18n="media.search.subtitle"`
- `data-i18n="media.search.context.subtitle"`
- `data-i18n="collectibles.subtitle"`
- `data-i18n="media.source.subtitle"`
- `data-i18n="ops.system.subtitle"`

Example near `media.search.subtitle`:

```html
<div class="page-help-title-row">
  <h2><span data-i18n="media.search.title">검색 / 리스트</span></h2>
  <button class="page-help-trigger" ...>도움말</button>
  <button class="section-desc-toggle" type="button" aria-expanded="false" aria-controls="mediaSearchDesc" aria-label="설명 펼치기">∨</button>
</div>
<div id="mediaSearchDesc" class="section-desc mini" data-section-desc>리스트는 마스터 기준입니다...</div>
```

- [ ] **Step 2: Add CSS for collapsed state**

```css
.section-desc[hidden] { display: none; }
.section-desc-toggle { /* small button styling aligned to header */ }
```

- [ ] **Step 3: Add JS toggle logic with sessionStorage**

```js
const DESC_STATE_KEY = "adminSectionDesc";
function getDescState() { try { return JSON.parse(sessionStorage.getItem(DESC_STATE_KEY) || "{}"); } catch { return {}; } }
function setDescState(state) { try { sessionStorage.setItem(DESC_STATE_KEY, JSON.stringify(state)); } catch {} }

function syncSectionDescToggles() {
  const state = getDescState();
  document.querySelectorAll(".section-desc-toggle").forEach((btn) => {
    const id = btn.getAttribute("aria-controls");
    const target = id ? document.getElementById(id) : null;
    if (!target) return;
    const isOpen = Boolean(state[id]);
    btn.setAttribute("aria-expanded", String(isOpen));
    target.hidden = !isOpen;
  });
}

function bindSectionDescToggles() {
  document.addEventListener("click", (event) => {
    const btn = event.target.closest(".section-desc-toggle");
    if (!btn) return;
    const id = btn.getAttribute("aria-controls");
    if (!id) return;
    const state = getDescState();
    state[id] = !state[id];
    setDescState(state);
    syncSectionDescToggles();
  });
}

// init on load
bindSectionDescToggles();
syncSectionDescToggles();
```

- [ ] **Step 4: Add tests to confirm new toggle markup**

```python

def test_section_desc_toggle_present_on_media_search():
    html = read_static_html("index.html")
    assert 'class="section-desc-toggle"' in html
    assert 'id="mediaSearchDesc"' in html
    assert 'data-section-desc' in html
    assert 'aria-label="설명 펼치기"' in html
```

- [ ] **Step 5: Run tests**

Run: `pytest /Volumes/Works/07.hahahoho/.worktrees/admin-density-compact/tests/test_ops_shell_bootstrap.py::test_section_desc_toggle_present_on_media_search -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/static/index.html tests/test_ops_shell_bootstrap.py
git commit -m "feat: add section description toggles"
```

---

### Task 5: Remove ops left nav slot + linked collectibles sections

**Files:**
- Modify: `/Volumes/Works/07.hahahoho/.worktrees/admin-density-compact/app/static/index.html`

- [ ] **Step 1: Hide ops left nav slot**

```css
body[data-shell-mode="ops"] .primary-side-nav-slot {
  display: none;
}
```

- [ ] **Step 2: Remove `homeMasterGoodsSection` and `homeLinkedGoodsPanel` markup**

Delete the entire blocks with these IDs in the media manage section.

- [ ] **Step 3: Make JS tolerant of removed nodes**

Ensure any code referencing these nodes guards for null (wrap lookups in `if ($("homeMasterGoodsSection")) { ... }`).

- [ ] **Step 4: Run tests (from Task 1)**

Run: pytest command from Task 1.
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/static/index.html
git commit -m "feat: remove ops left nav slot and collectibles panel"
```

---

## Final Verification
- [ ] Run full targeted suite:

```bash
pytest /Volumes/Works/07.hahahoho/.worktrees/admin-density-compact/tests/test_ops_shell_bootstrap.py /Volumes/Works/07.hahahoho/.worktrees/admin-density-compact/tests/test_admin_density_compaction.py -v
```

Expected: PASS.

---

## Execution Handoff
Plan complete and saved to `docs/superpowers/plans/2026-04-13-admin-shell-grid-plan.md`.

Two execution options:
1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks
2. **Inline Execution** — Execute tasks in this session using executing-plans

Which approach?
