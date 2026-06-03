# Admin Left Nav Accordion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace admin in-body menus with a left sidebar accordion navigation and move ERD/Manual links into Ops > System Status while keeping operator UI unchanged.

**Architecture:** Keep existing admin tab/subtab state logic and bind the new left sidebar to those handlers. In-body menus remain in the DOM but are hidden for admin mode to preserve state logic. Sidebar uses an accordion with one expanded section and auto-selects first subtab when needed.

**Tech Stack:** Static HTML/CSS/vanilla JS in `app/static/index.html`, pytest-style static HTML tests in `tests/`.

---

## File Structure & Ownership

**Modify**
- `/Volumes/Data/Works/07.__PROJECT_SLUG__/.worktrees/admin-left-nav-accordion/app/static/index.html`
  - Add admin sidebar markup and CSS rules.
  - Hide in-body menus for admin mode.
  - Add Ops docs block above System Status.
  - Add JS to sync sidebar state with existing tab/subtab logic.

**Modify tests**
- `/Volumes/Data/Works/07.__PROJECT_SLUG__/.worktrees/admin-left-nav-accordion/tests/test_admin_density_compaction.py`
  - Add static HTML assertions for sidebar markup, admin-only menu hiding selectors, and Ops docs block.

---

### Task 1: Add failing tests for new admin left-nav structure

**Files:**
- Modify: `/Volumes/Data/Works/07.__PROJECT_SLUG__/.worktrees/admin-left-nav-accordion/tests/test_admin_density_compaction.py`

- [ ] **Step 1: Write the failing tests**

```python

def test_admin_left_sidebar_nav_structure():
    html = read_static_html("index.html")
    assert 'id="adminSideNav"' in html
    assert 'data-admin-nav="home"' in html
    assert 'data-admin-nav="media"' in html
    assert 'data-admin-nav="collectibles"' in html
    assert 'data-admin-nav="ops"' in html
    assert 'data-admin-subnav="media:search"' in html
    assert 'data-admin-subnav="media:manage"' in html
    assert 'data-admin-subnav="media:register"' in html
    assert 'data-admin-subnav="media:source"' in html
    assert 'data-admin-subnav="collectibles:search"' in html
    assert 'data-admin-subnav="collectibles:manage"' in html
    assert 'data-admin-subnav="collectibles:register"' in html
    assert 'data-admin-subnav="ops:system"' in html


def test_admin_body_menus_hidden_in_admin_mode():
    html = read_static_html("index.html")
    assert 'body[data-shell-mode="admin"] .goods-mode-tabs' in html
    assert 'body[data-shell-mode="admin"] .subtabs' in html
    assert 'display: none' in html


def test_ops_system_docs_block_present():
    html = read_static_html("index.html")
    block = html.split('id="tabOps"', 1)[1].split('id="opsSystemStatusSummary"', 1)[0]
    assert 'id="opsDocsBlock"' in block
    assert 'data-i18n="shell.admin.docs_summary"' in block
    assert 'data-tool-doc-key="erd-summary"' in block
    assert 'data-tool-doc-key="erd-detail"' in block
    assert 'data-tool-doc-key="manual"' in block
```

- [ ] **Step 2: Run tests to confirm they fail**

Run:
```bash
pytest tests/test_admin_density_compaction.py::test_admin_left_sidebar_nav_structure -v
```
Expected: FAIL (sidebar/nav ids not present yet)

- [ ] **Step 3: Commit failing tests**

```bash
git add tests/test_admin_density_compaction.py
git commit -m "test: expect admin left nav structure"
```

---

### Task 2: Add admin left sidebar markup + Ops docs block

**Files:**
- Modify: `/Volumes/Data/Works/07.__PROJECT_SLUG__/.worktrees/admin-left-nav-accordion/app/static/index.html`

- [ ] **Step 1: Add sidebar markup**
  - Insert an `<aside id="adminSideNav">` inside the admin shell wrapper.
  - Create top-level items with `data-admin-nav="home|media|collectibles|ops"`.
  - Create subnav groups with `data-admin-subnav` entries for each section.
  - Use `aria-expanded`, `aria-controls`, and `aria-current` placeholders.

- [ ] **Step 2: Add Ops docs block**
  - In `#tabOps`, insert a small block at the top of System Status (before `opsSystemStatusSummary`).
  - Use existing i18n keys `shell.admin.docs_summary` and `shell.admin.docs_body`.
  - Include the three doc links with `data-tool-doc-key` values.

- [ ] **Step 3: Run the new tests**

Run:
```bash
pytest tests/test_admin_density_compaction.py::test_admin_left_sidebar_nav_structure -v
pytest tests/test_admin_density_compaction.py::test_ops_system_docs_block_present -v
```
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/static/index.html
git commit -m "feat: add admin left nav markup"
```

---

### Task 3: Hide in-body menus for admin mode via CSS

**Files:**
- Modify: `/Volumes/Data/Works/07.__PROJECT_SLUG__/.worktrees/admin-left-nav-accordion/app/static/index.html`

- [ ] **Step 1: Add admin-only CSS rules**
  - Add rules that hide `.goods-mode-tabs` and `.subtabs` only when `body[data-shell-mode="admin"]`.
  - Ensure rules use `display: none;` so they are removed from layout and assistive tech.

- [ ] **Step 2: Run tests**

Run:
```bash
pytest tests/test_admin_density_compaction.py::test_admin_body_menus_hidden_in_admin_mode -v
```
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add app/static/index.html
git commit -m "style: hide admin body menus"
```

---

### Task 4: Sidebar styles (layout + accordion)

**Files:**
- Modify: `/Volumes/Data/Works/07.__PROJECT_SLUG__/.worktrees/admin-left-nav-accordion/app/static/index.html`

- [ ] **Step 1: Add sidebar layout CSS**
  - Fixed left column for admin mode, body content uses remaining width.
  - Style top-level items + subitems, active states.
  - Ensure one-open accordion visuals.

- [ ] **Step 2: Add responsive rules**
  - For narrow widths, sidebar collapses to a rail/drawer but still exposes subitems.

- [ ] **Step 3: Manual verification (smoke)**
  - Load admin view and confirm sidebar occupies left column and content flows to the right.

- [ ] **Step 4: Commit**

```bash
git add app/static/index.html
git commit -m "style: admin sidebar layout"
```

---

### Task 5: JS sync for sidebar (state + accordion behavior)

**Files:**
- Modify: `/Volumes/Data/Works/07.__PROJECT_SLUG__/.worktrees/admin-left-nav-accordion/app/static/index.html`

- [ ] **Step 1: Add sidebar state helpers**
  - Build `syncAdminSidebarNav()` that reads the current active admin tab + subtab (media/goods/ops).
  - Apply `aria-current` and active classes to left nav items.
  - Ensure dashboard counts as a leaf item (no subnav list shown).

- [ ] **Step 2: Add event wiring**
  - Top-level click: openAdminConsole with the right tab and auto-select first subtab if needed.
  - Subitem click: call switchMediaMode/switchGoodsMode/switchSubTab and sync sidebar.
  - Respect state precedence: deep link > saved > default (already handled by openAdminConsole/switchMainTab logic).

- [ ] **Step 3: Ensure one section open**
  - Toggle expanded class on only the active top-level section.

- [ ] **Step 4: Manual verification**
  - Switch between top-level items; verify first subtab auto-selects.
  - Verify deep link/saved state doesn’t reset.

- [ ] **Step 5: Commit**

```bash
git add app/static/index.html
git commit -m "feat: sync admin left nav accordion"
```

---

### Task 6: Full verification

- [ ] **Step 1: Run targeted tests**

```bash
pytest tests/test_admin_density_compaction.py -v
```
Expected: PASS

- [ ] **Step 2: Run broader smoke test if time allows**

```bash
pytest tests/test_ops_shell_bootstrap.py::test_admin_shell_bootstrap -v
```
Expected: PASS (admin shell still loads)

- [ ] **Step 3: Commit any final fixes**

```bash
git status -sb
```

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-13-admin-left-nav-accordion-implementation.md`. Two execution options:

1. **Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
