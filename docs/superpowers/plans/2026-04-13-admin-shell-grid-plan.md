# Admin Shell Grid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the admin shell into a header + left-nav + content grid, add menu accordion persistence, and collapse section descriptions by default while keeping ops scope removals minimal.

**Architecture:** All changes land in `app/static/index.html` (HTML/CSS/JS) plus string-based pytest assertions in `tests/`. The admin shell uses a two-row grid: header spans full width; row 2 is nav + content. Nav/content scroll independently. Menu accordion state persists in sessionStorage and deep-linking opens the parent.

**Tech Stack:** HTML, CSS, vanilla JS, pytest.

---

## File Map

**Modify**
- `/Volumes/Data/Works/07.hahahoho/.worktrees/admin-density-compact/app/static/index.html`
  - Admin shell grid CSS (`body[data-shell-mode="admin"] .wrap`, `#adminSideNav`, `.primary-shell`, `#appHero`)
  - Header positioning (grid placement)
  - Nav icon-only rail CSS at `<=1080px`
  - Menu accordion behavior (sessionStorage + deep-link open)
  - Section description toggle wiring
  - Remove Ops left nav slot and collectibles panel

**Modify Tests**
- `/Volumes/Data/Works/07.hahahoho/.worktrees/admin-density-compact/tests/test_ops_shell_bootstrap.py`
- `/Volumes/Data/Works/07.hahahoho/.worktrees/admin-density-compact/tests/test_admin_density_compaction.py`

---

### Task 1: Add failing tests for admin grid + ops removals

**Files:**
- Modify: `/Volumes/Data/Works/07.hahahoho/.worktrees/admin-density-compact/tests/test_ops_shell_bootstrap.py`
- Modify: `/Volumes/Data/Works/07.hahahoho/.worktrees/admin-density-compact/tests/test_admin_density_compaction.py`

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
    ops_block = html.split('body[data-shell-mode="ops"] #opsHomeLayout .primary-side-nav-slot {', 1)[1].split("}", 1)[0]
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
    assert "body[data-shell-mode=\"admin\"] #adminSideNav.primary-side-nav--icon" in block_1080
    assert "width: var(--admin-side-nav-icon-width);" in block_1080
```

- [ ] **Step 4: Run the tests to confirm failure**

Run: `pytest /Volumes/Data/Works/07.hahahoho/.worktrees/admin-density-compact/tests/test_ops_shell_bootstrap.py::test_index_admin_shell_grid_uses_header_and_body_rows /Volumes/Data/Works/07.hahahoho/.worktrees/admin-density-compact/tests/test_ops_shell_bootstrap.py::test_ops_home_hides_primary_side_nav_slot /Volumes/Data/Works/07.hahahoho/.worktrees/admin-density-compact/tests/test_ops_shell_bootstrap.py::test_admin_removes_linked_collectibles_panel /Volumes/Data/Works/07.hahahoho/.worktrees/admin-density-compact/tests/test_ops_shell_bootstrap.py::test_admin_nav_icon_rail_at_1080 -v`

Expected: FAIL (new selectors not yet present).

- [ ] **Step 5: Commit tests**

```bash
git add tests/test_ops_shell_bootstrap.py tests/test_admin_density_compaction.py
git commit -m "test: define admin shell grid + ops removal expectations"
```

---

### Task 2: Implement admin shell grid (header + nav + content)

**Files:**
- Modify: `/Volumes/Data/Works/07.hahahoho/.worktrees/admin-density-compact/app/static/index.html`
- Modify: `/Volumes/Data/Works/07.hahahoho/.worktrees/admin-density-compact/tests/test_ops_shell_bootstrap.py`

- [ ] **Step 1: Move admin header/nav nodes to be direct grid items**

Move these nodes so they are direct children of `.wrap` (admin-only grid items):
- `#appHero`
- `#adminSideNav`

Keep `#opsHomeHero` and `#shellUtilityBar` in their current structure to avoid ops layout changes.

- [ ] **Step 1.1: Confirm `.primary-shell` wraps admin content**

Verify `.primary-shell` already wraps the main admin content. If it does not exist, introduce it so Task 1 tests and grid placement apply correctly.

- [ ] **Step 2: Update admin `.wrap` grid and remove left margin**

```css
body[data-shell-mode="admin"] .wrap {
  display: grid;
  grid-template-columns: var(--admin-side-nav-width) minmax(0, 1fr);
  grid-template-rows: auto minmax(0, 1fr);
  gap: var(--admin-side-nav-gap);
  width: 100%;
  margin: 8px 12px 16px;
  height: 100dvh;
  min-height: 100vh;
  overflow: hidden;
}
```

- [ ] **Step 3: Place header in row 1 spanning full width**

```css
body[data-shell-mode="admin"] #appHero {
  grid-column: 1 / -1;
  grid-row: 1;
}

body[data-shell-mode="admin"] #appHero {
  position: static;
  top: auto;
}
```

- [ ] **Step 4: Place admin nav + content in row 2 and enable independent scroll**

```css
body[data-shell-mode="admin"] #adminSideNav {
  grid-column: 1;
  grid-row: 2;
  align-self: stretch;
  overflow-y: auto;
  min-height: 0;
  max-height: 100%;
}

body[data-shell-mode="admin"] .primary-shell {
  grid-column: 2;
  grid-row: 2;
  min-width: 0;
  overflow-y: auto;
  min-height: 0;
  max-height: 100%;
}
```

- [ ] **Step 5: Remove nav fixed positioning + top offset + header height dependency**

```css
.admin-side-nav {
  position: static;
  top: auto;
  left: auto;
}

/* remove header height dependency (no longer needed in grid) */
:root { --admin-shell-header-height: auto; }
```

- [ ] **Step 6: Verify no redundant menu rendering inside content**

Ensure existing admin-only rules still hide in-content menus:
```
body[data-shell-mode=\"admin\"] .goods-mode-tabs,
body[data-shell-mode=\"admin\"] .subtabs { display: none; }
```

- [ ] **Step 7: Run tests from Task 1**

Run: same pytest command from Task 1.
Expected: PASS for grid/nav placement checks. Icon-rail test still fails until Task 3; ops-removal tests still fail until Task 5.

- [ ] **Step 8: Commit**

```bash
git add app/static/index.html
git commit -m "feat: move admin shell to header+nav+content grid"
```

---

### Task 3: Menu accordion persistence + icon-only rail (<=1080)

**Files:**
- Modify: `/Volumes/Data/Works/07.hahahoho/.worktrees/admin-density-compact/app/static/index.html`

- [ ] **Step 1: Confirm existing admin nav helpers and reuse**

Audit these helpers (already present today) and confirm names before edits:
- `syncAdminSidebarNav`
- `activeAdminMainTab`
- `resolveActiveAdminSubnavKey`
- `collapseAdminSideNavAccordions`

If any are missing or renamed, add minimal equivalents before proceeding.

- [ ] **Step 2: Ensure left-menu IA + child styling match spec**

Update `#adminSideNav` markup to match the spec’s parent/child mapping exactly, and ensure child items are smaller and indented (via `.admin-side-nav-subitem`). If any labels or groupings are off, correct the HTML before behavior changes. Use this exact structure:

```html
<div class="admin-side-nav-group">
  <button class="admin-side-nav-button admin-side-nav-button--leaf" type="button" data-admin-nav="home" data-i18n="nav.dashboard">대시보드</button>
</div>
<div class="admin-side-nav-group">
  <button class="admin-side-nav-button" type="button" data-admin-nav="media" aria-expanded="false" aria-controls="adminNavMedia" data-i18n="nav.media">미디어</button>
  <div id="adminNavMedia" class="admin-side-nav-submenu" hidden>
    <button class="admin-side-nav-subitem" type="button" data-admin-subnav="media:search" data-i18n="media.mode.search">검색</button>
    <button class="admin-side-nav-subitem" type="button" data-admin-subnav="media:manage" data-i18n="media.mode.manage">관리</button>
    <button class="admin-side-nav-subitem" type="button" data-admin-subnav="media:register" data-i18n="media.mode.register">등록/수집</button>
    <div class="admin-side-nav-submenu admin-side-nav-submenu--nested" data-admin-subgroup="media:register" hidden>
      <button class="admin-side-nav-subitem" type="button" data-admin-subnav="media:register:collect" data-i18n="media.register.subtab.direct">직접 등록</button>
      <button class="admin-side-nav-subitem" type="button" data-admin-subnav="media:register:purchase" data-i18n="media.register.subtab.purchase">구매 내역</button>
      <button class="admin-side-nav-subitem" type="button" data-admin-subnav="media:register:batch" data-i18n="media.register.subtab.batch">대량 등록</button>
      <button class="admin-side-nav-subitem" type="button" data-admin-subnav="media:register:master" data-i18n="media.register.subtab.master">마스터 정리</button>
    </div>
    <button class="admin-side-nav-subitem" type="button" data-admin-subnav="media:source" data-i18n="media.mode.source">소스 보강</button>
  </div>
</div>
<div class="admin-side-nav-group">
  <button class="admin-side-nav-button" type="button" data-admin-nav="collectibles" aria-expanded="false" aria-controls="adminNavCollectibles" data-i18n="nav.collectibles">컬렉터블</button>
  <div id="adminNavCollectibles" class="admin-side-nav-submenu" hidden>
    <button class="admin-side-nav-subitem" type="button" data-admin-subnav="collectibles:search" data-i18n="collectibles.mode.search">컬렉터블 검색</button>
    <button class="admin-side-nav-subitem" type="button" data-admin-subnav="collectibles:manage" data-i18n="collectibles.mode.manage">컬렉터블 관리</button>
    <button class="admin-side-nav-subitem" type="button" data-admin-subnav="collectibles:register" data-i18n="collectibles.mode.register">컬렉터블 등록</button>
  </div>
</div>
<div class="admin-side-nav-group">
  <button class="admin-side-nav-button" type="button" data-admin-nav="ops" aria-expanded="false" aria-controls="adminNavOps" data-i18n="nav.ops">운영/연계</button>
  <div id="adminNavOps" class="admin-side-nav-submenu" hidden>
    <button class="admin-side-nav-subitem" type="button" data-admin-subnav="ops:system" data-i18n="ops.system.title">시스템 상태</button>
    <button class="admin-side-nav-subitem" type="button" data-admin-subnav="ops:cabinet" data-i18n="ops.subtab.cabinet">장식장</button>
    <button class="admin-side-nav-subitem" type="button" data-admin-subnav="ops:slot" data-i18n="ops.subtab.slot">슬롯</button>
    <button class="admin-side-nav-subitem" type="button" data-admin-subnav="ops:camera" data-i18n="ops.subtab.camera">카메라</button>
    <button class="admin-side-nav-subitem" type="button" data-admin-subnav="ops:exception" data-i18n="ops.subtab.exception">예외 큐</button>
    <button class="admin-side-nav-subitem" type="button" data-admin-subnav="ops:account" data-i18n="ops.subtab.account">계정</button>
    <button class="admin-side-nav-subitem" type="button" data-admin-subnav="ops:providers" data-i18n="ops.subtab.providers">연동/API 설정</button>
    <button class="admin-side-nav-subitem" type="button" data-admin-subnav="ops:export" data-i18n="ops.subtab.export">백업/내보내기</button>
    <button class="admin-side-nav-subitem" type="button" data-admin-subnav="ops:metasync" data-i18n="ops.subtab.meta_sync">메타 동기화</button>
    <div class="admin-side-nav-submenu admin-side-nav-submenu--docs">
      <span class="admin-side-nav-subtitle" data-i18n="shell.admin.docs_summary">문서 / ERD / 활용 매뉴얼</span>
      <a class="admin-side-nav-subitem" href="/tool-docs/erd-summary" target="_blank" rel="noreferrer" data-tool-doc-key="erd-summary" data-i18n="shell.admin.doc_link.erd_summary">ERD 요약</a>
      <a class="admin-side-nav-subitem" href="/tool-docs/erd-detail" target="_blank" rel="noreferrer" data-tool-doc-key="erd-detail" data-i18n="shell.admin.doc_link.erd_detail">ERD 상세</a>
      <a class="admin-side-nav-subitem" href="/tool-docs/manual" target="_blank" rel="noreferrer" data-tool-doc-key="manual" data-i18n="shell.admin.doc_link.manual">툴 활용 매뉴얼</a>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Add sessionStorage helpers**

```js
const ADMIN_NAV_STATE_KEY = "adminNavOpen";
function readAdminNavState() {
  try { return sessionStorage.getItem(ADMIN_NAV_STATE_KEY) || ""; } catch (_) { return ""; }
}
function writeAdminNavState(value) {
  try { sessionStorage.setItem(ADMIN_NAV_STATE_KEY, value); } catch (_) {}
}
```

- [ ] **Step 4: Update `syncAdminSidebarNav()` to respect stored open state and deep-link**

```js
const storedMain = readAdminNavState();
const activeMain = activeAdminMainTab();
const activeSub = resolveActiveAdminSubnavKey();
const targetMain = activeSub ? activeMain : (storedMain || activeMain);

// ensure parent opens on deep-link
const mainToOpen = activeSub ? activeMain : targetMain;
```

- [ ] **Step 5: When top-level buttons are clicked, store the open state**

```js
if (navId) {
  writeAdminNavState(navId);
  collapseAdminSideNavAccordions(navId);
  routeAdminSideNavTop(navId);
}
```

- [ ] **Step 6: Add icon-only rail styles (reuse existing icon-rail patterns)**

```css
:root { --admin-side-nav-icon-width: 56px; }

@media (max-width: 1080px) {
  body[data-shell-mode="admin"] #adminSideNav.primary-side-nav--icon {
    width: var(--admin-side-nav-icon-width);
  }
  body[data-shell-mode="admin"] #adminSideNav.primary-side-nav--icon .admin-side-nav-button,
  body[data-shell-mode="admin"] #adminSideNav.primary-side-nav--icon .admin-side-nav-subitem {
    justify-content: center;
    padding-left: 0;
    padding-right: 0;
    font-size: 0;
  }
  body[data-shell-mode="admin"] #adminSideNav.primary-side-nav--icon .admin-side-nav-button::before {
    content: attr(data-nav-icon);
    font-size: 0.78rem;
  }
  body[data-shell-mode="admin"] #adminSideNav.primary-side-nav--icon .admin-side-nav-submenu {
    display: none !important;
  }
}
```

- [ ] **Step 7: Add `data-nav-icon` attributes to top buttons**

```html
<button class="admin-side-nav-button admin-side-nav-button--leaf" data-admin-nav="home" data-nav-icon="D" ...>대시보드</button>
<button class="admin-side-nav-button" data-admin-nav="media" data-nav-icon="M" ...>미디어</button>
<button class="admin-side-nav-button" data-admin-nav="collectibles" data-nav-icon="C" ...>컬렉터블</button>
<button class="admin-side-nav-button" data-admin-nav="ops" data-nav-icon="O" ...>운영/연계</button>
```

- [ ] **Step 8: Add a media query toggle hook in JS**

```js
const adminNav = $("adminSideNav");
const navMql = window.matchMedia("(max-width: 1080px)");
function syncAdminNavIconMode() {
  if (!adminNav) return;
  adminNav.classList.toggle("primary-side-nav--icon", navMql.matches);
}
navMql.addEventListener("change", syncAdminNavIconMode);
syncAdminNavIconMode();
```

- [ ] **Step 9: Verify IA + ARIA expectations**

Add/confirm these attributes in markup:\n
- Parent buttons include `aria-expanded` + `aria-controls`.\n
- Child buttons are focusable only when expanded.\n
- Submenu mapping matches the spec list.\n
- Parent buttons include `aria-label` that reflects expand/collapse (e.g., “미디어 메뉴 펼치기/접기”).\n

Add a test to assert all parent items exist:\n
\n```python\n\ndef test_admin_nav_contains_all_parent_groups():\n    html = read_static_html(\"index.html\")\n    for label in [\"nav.dashboard\", \"nav.media\", \"nav.collectibles\", \"nav.ops\"]:\n        assert f'data-i18n=\"{label}\"' in html\n```\n+
- [ ] **Step 10: Run tests**

Run: pytest command from Task 1.
Expected: PASS for icon rail assertion and new storage logic (string checks only).

- [ ] **Step 11: Commit**

```bash
git add app/static/index.html tests/test_ops_shell_bootstrap.py
git commit -m "feat: persist admin nav accordion + icon rail"
```

---

### Task 4: Section description toggles (collapsed by default)

**Files:**
- Modify: `/Volumes/Data/Works/07.hahahoho/.worktrees/admin-density-compact/app/static/index.html`
- Modify: `/Volumes/Data/Works/07.hahahoho/.worktrees/admin-density-compact/tests/test_ops_shell_bootstrap.py`

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

Run: `pytest /Volumes/Data/Works/07.hahahoho/.worktrees/admin-density-compact/tests/test_ops_shell_bootstrap.py::test_section_desc_toggle_present_on_media_search -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/static/index.html tests/test_ops_shell_bootstrap.py
git commit -m "feat: add section description toggles"
```

---

### Task 5: Remove ops left nav slot + linked collectibles sections

**Files:**
- Modify: `/Volumes/Data/Works/07.hahahoho/.worktrees/admin-density-compact/app/static/index.html`

- [ ] **Step 1: Hide ops left nav slot**

```css
body[data-shell-mode="ops"] #opsHomeLayout .primary-side-nav-slot {
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
pytest /Volumes/Data/Works/07.hahahoho/.worktrees/admin-density-compact/tests/test_ops_shell_bootstrap.py /Volumes/Data/Works/07.hahahoho/.worktrees/admin-density-compact/tests/test_admin_density_compaction.py -v
```

Expected: PASS.

- [ ] Manual checks (admin UI):
  - Header is static (not sticky) while nav/content scroll independently.
  - Description toggles default-collapsed and expand/collapse changes layout.
  - Keyboard: Tab through parent menu buttons, confirm `aria-expanded` updates and children become focusable only when expanded.
  - Persistence: Expand a parent, navigate to another admin subpage, verify parent remains open (same tab).
  - Deep-link: Open a URL that routes directly to a child subpage; verify its parent opens.
  - Icon rail: Resize <=1080px; confirm nav collapses to icon-only and submenu is hidden.

---

## Execution Handoff
Plan complete and saved to `docs/superpowers/plans/2026-04-13-admin-shell-grid-plan.md`.

Two execution options:
1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks
2. **Inline Execution** — Execute tasks in this session using executing-plans

Which approach?
