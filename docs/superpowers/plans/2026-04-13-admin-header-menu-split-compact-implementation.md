# Admin Header/Menu Split Compact Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the admin header from the body layout, tighten the left nav card (width, spacing, font size), enforce single-open accordion behavior, and move the media section intro copy into a tooltip to reclaim vertical space.

**Architecture:** Adjust static HTML/CSS in `app/static/index.html` to shrink header height, reposition the fixed left nav below the header, and compact nav typography/spacing. Update JS click behavior to explicitly collapse other sections. Replace the inline media section subtitle with a help tooltip using existing `section-help-dot` and i18n help keys.

**Tech Stack:** Static HTML/CSS/JS, pytest string-based UI tests.

---

## Files to Touch
- Modify: `/Volumes/Data/Works/07.__PROJECT_SLUG__/.worktrees/admin-density-compact/app/static/index.html`
- Modify: `/Volumes/Data/Works/07.__PROJECT_SLUG__/.worktrees/admin-density-compact/tests/test_admin_density_compaction.py`
- Modify: `/Volumes/Data/Works/07.__PROJECT_SLUG__/.worktrees/admin-density-compact/tests/test_ops_shell_bootstrap.py` (only if a selector collision appears after CSS changes)

---

### Task 1: Add failing tests for compact header/nav + media tooltip

**Files:**
- Modify: `/Volumes/Data/Works/07.__PROJECT_SLUG__/.worktrees/admin-density-compact/tests/test_admin_density_compaction.py`

- [ ] **Step 1: Write failing tests**

```python

def test_admin_header_menu_split_compact_nav_tokens():
    html = read_static_html("index.html")
    root_block = html.split(":root {", 1)[1].split("}", 1)[0]
    assert "--admin-side-nav-width: 200px;" in root_block
    assert "--admin-side-nav-gap: 12px;" in root_block

    admin_root = html.split('body[data-shell-mode="admin"] {', 1)[1].split("}", 1)[0]
    assert "--admin-shell-header-height: 56px;" in admin_root

    nav_block = html.split(".admin-side-nav {", 1)[1].split("}", 1)[0]
    assert "top: calc(var(--admin-shell-header-height) + 12px);" in nav_block
    assert "position: fixed;" in nav_block

    card_block = html.split(".admin-side-nav-card {", 1)[1].split("}", 1)[0]
    assert "background:" in card_block
    assert "padding:" in card_block
    assert "border:" in card_block

    button_block = html.split(".admin-side-nav-button {", 1)[1].split("}", 1)[0]
    subitem_block = html.split(".admin-side-nav-subitem {", 1)[1].split("}", 1)[0]
    assert "font-size: 0.86rem;" in button_block
    assert "font-size: 0.78rem;" in subitem_block


def test_media_section_intro_moves_to_help_tooltip():
    html = read_static_html("index.html")
    media_block = html.split('id="tabMedia"', 1)[1].split('id="tabSearch"', 1)[0]
    assert 'data-i18n="media.subtitle"' not in media_block
    assert 'data-help-key="help.media.summary"' in media_block
    assert html.count('"help.media.summary":') == 3


def test_admin_side_nav_click_collapses_other_sections():
    html = read_static_html("index.html")
    handler_block = html.split('$("adminSideNav")?.addEventListener("click"', 1)[1].split("});", 1)[0]
    assert "collapseAdminSideNavAccordions" in handler_block
```

- [ ] **Step 2: Run tests to verify failures**

Run:
```bash
pytest tests/test_admin_density_compaction.py::test_admin_header_menu_split_compact_nav_tokens -v
```
Expected: FAIL (missing new tokens and CSS).

Run:
```bash
pytest tests/test_admin_density_compaction.py::test_media_section_intro_moves_to_help_tooltip -v
```
Expected: FAIL (still uses inline subtitle / missing help key).

Run:
```bash
pytest tests/test_admin_density_compaction.py::test_admin_side_nav_click_collapses_other_sections -v
```
Expected: FAIL (no accordion collapse helper).

- [ ] **Step 3: Commit failing tests**

```bash
git add tests/test_admin_density_compaction.py
git commit -m "test: cover compact admin header/nav and media help tooltip"
```

---

### Task 2: Implement compact header + nav card + tooltip

**Files:**
- Modify: `/Volumes/Data/Works/07.__PROJECT_SLUG__/.worktrees/admin-density-compact/app/static/index.html`

- [ ] **Step 1: Update layout tokens and header height**

Add/update tokens:
```css
:root {
  --admin-side-nav-width: 200px;
  --admin-side-nav-gap: 12px;
}

body[data-shell-mode="admin"] {
  --admin-shell-header-height: 56px;
}
```

Compact header styling (admin only):
```css
body[data-shell-mode="admin"] .admin-shell-hero {
  margin: 6px 0 8px;
  padding: 6px 10px;
  border-radius: 16px;
}
body[data-shell-mode="admin"] .admin-shell-kicker,
body[data-shell-mode="admin"] .admin-shell-hero p {
  display: none;
}
body[data-shell-mode="admin"] .admin-shell-hero-head {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
}
```

- [ ] **Step 2: Reposition and compact the nav card**

Keep nav fixed, but align below header and tighten layout:
```css
.admin-side-nav {
  position: fixed;
  top: calc(var(--admin-shell-header-height) + 12px);
  left: 12px;
  width: var(--admin-side-nav-width);
}

.admin-side-nav-card {
  background: rgba(255,255,255,0.92);
  border-radius: 14px;
  padding: 8px;
  border: 1px solid rgba(148, 163, 184, 0.32);
  box-shadow: var(--shadow);
  gap: 6px;
}

.admin-side-nav-group { gap: 6px; }
.admin-side-nav-submenu { gap: 4px; padding-left: 10px; margin-left: 4px; }
.admin-side-nav-submenu--docs { margin-top: 6px; padding-top: 6px; }

.admin-side-nav-button {
  padding: 8px 10px;
  font-size: 0.86rem;
}
.admin-side-nav-subitem {
  padding: 6px 8px;
  font-size: 0.78rem;
}
```

- [ ] **Step 3: Replace media subtitle with tooltip**

Update media intro:
```html
<strong data-i18n="media.title">미디어</strong>
<span class="section-help-dot" tabindex="0" data-help-key="help.media.summary">?</span>
```

Remove:
```html
<div class="mini" data-i18n="media.subtitle">...</div>
```

Add i18n help text (ko/en/ja):
```js
"help.media.summary": "검색, 관리, 등록/수집, 소스 보강을 한 흐름으로 묶습니다.",
```

- [ ] **Step 4: Run tests (green)**

```bash
pytest tests/test_admin_density_compaction.py::test_admin_header_menu_split_compact_nav_tokens -v
pytest tests/test_admin_density_compaction.py::test_media_section_intro_moves_to_help_tooltip -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/static/index.html
git commit -m "feat: compact admin header/nav and move media intro to tooltip"
```

---

### Task 3: Enforce accordion collapse on top-level click

**Files:**
- Modify: `/Volumes/Data/Works/07.__PROJECT_SLUG__/.worktrees/admin-density-compact/app/static/index.html`

- [ ] **Step 1: Add helper to collapse other sections**

```js
function collapseAdminSideNavAccordions(activeId) {
  const nav = $("adminSideNav");
  if (!nav) return;
  nav.querySelectorAll("[data-admin-nav]").forEach((btn) => {
    const id = String(btn.getAttribute("data-admin-nav") || "").trim();
    if (btn.classList.contains("admin-side-nav-button--leaf")) return;
    const controls = btn.getAttribute("aria-controls");
    const submenu = controls ? $(controls) : null;
    const isActive = id === activeId;
    btn.setAttribute("aria-expanded", String(Boolean(isActive && submenu)));
    if (submenu) submenu.hidden = !isActive;
  });
}
```

Call this before routing:
```js
if (navId) {
  collapseAdminSideNavAccordions(navId);
  routeAdminSideNavTop(navId);
  return;
}
```

- [ ] **Step 2: Run test (green)**

```bash
pytest tests/test_admin_density_compaction.py::test_admin_side_nav_click_collapses_other_sections -v
```
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add app/static/index.html
git commit -m "feat: collapse admin nav accordions on top-level click"
```

---

### Task 4: Full verification

- [ ] **Run the targeted suite**

```bash
pytest tests/test_admin_density_compaction.py tests/test_ops_shell_bootstrap.py -v
```
Expected: PASS.

- [ ] **Manual visual check (1320px)**

Verify:
- Header height is visibly reduced.
- Left nav starts below header and is compact.
- Media subtitle replaced by tooltip.
- Clicking a top-level menu collapses others.

---

## Execution Choice
Plan complete and saved to `docs/superpowers/plans/2026-04-13-admin-header-menu-split-compact-implementation.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — requires using `superpowers:subagent-driven-development`
2. **Inline Execution** — run in this session using `superpowers:executing-plans`

Which approach do you want?
