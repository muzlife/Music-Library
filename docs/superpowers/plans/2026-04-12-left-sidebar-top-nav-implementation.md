# Left Sidebar Primary Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the top-level navigation into a left sidebar with responsive collapse (icon-only and drawer) while keeping sub-tabs in the main content area.

**Architecture:** Update `app/static/index.html` layout structure to wrap the current header + content in a two-column shell (sidebar + main). Add CSS rules for desktop/sidebar widths and responsive icon-only + drawer behaviors. Add minimal JS to control drawer open/close state and accessibility focus handling. Expand tests in `tests/test_ops_shell_bootstrap.py` to assert new sidebar structure, button semantics, and breakpoints.

**Tech Stack:** HTML/CSS/JS in `app/static/index.html`, pytest in `tests/test_ops_shell_bootstrap.py`.

---

## File Map

**Modify:**
- `/Volumes/Data/Works/07.__PROJECT_SLUG__/app/static/index.html`
- `/Volumes/Data/Works/07.__PROJECT_SLUG__/tests/test_ops_shell_bootstrap.py`

---

### Task 1: Add Failing Tests for Left Sidebar Navigation

**Files:**
- Modify: `/Volumes/Data/Works/07.__PROJECT_SLUG__/tests/test_ops_shell_bootstrap.py`

- [ ] **Step 1: Add failing tests**

```python
def test_primary_navigation_moves_to_left_sidebar():
    html = read_static_html("index.html")
    assert "primary-side-nav" in html
    assert "nav.dashboard" in html
    assert "nav.media" in html
    assert "nav.collectibles" in html
    assert "nav.ops" in html
    assert "aria-current=\"page\"" in html


def test_sidebar_responsive_states_defined():
    html = read_static_html("index.html")
    assert "@media (max-width: 1199px)" in html
    assert "@media (max-width: 760px)" in html
    assert "primary-side-nav--icon" in html
    assert "primary-side-drawer" in html


def test_sidebar_drawer_menu_button_accessibility():
    html = read_static_html("index.html")
    assert "data-nav-drawer-toggle" in html
    assert "aria-label=\"Open navigation\"" in html
    assert "data-nav-tooltip" in html
    assert "role=\"dialog\"" in html
    assert "aria-modal=\"true\"" in html
```

- [ ] **Step 2: Run tests to verify failure**

Run:
```bash
pytest -q tests/test_ops_shell_bootstrap.py::test_primary_navigation_moves_to_left_sidebar
```
Expected: FAIL (sidebar structure not yet present).

---

### Task 2: Implement Left Sidebar Layout + Responsive Behavior

**Files:**
- Modify: `/Volumes/Data/Works/07.__PROJECT_SLUG__/app/static/index.html`

- [ ] **Step 1: Add structural wrapper**

Wrap the existing shell header + tab panels in a new two-column container:
```html
<div class="primary-shell">
  <nav class="primary-side-nav" aria-label="Primary">
    <!-- top-level nav buttons -->
  </nav>
  <div class="primary-shell-main">
    <!-- existing header + tabs content -->
  </div>
</div>
```

- [ ] **Step 2: Move top-level nav buttons into sidebar**

Move the four top-level buttons (Dashboard/Media/Collectibles/Ops) into the sidebar nav list.

- [ ] **Step 3: Wire active state and semantics**

Ensure the active top-level item gets `aria-current="page"` and an active style that still reads in icon-only mode.

- [ ] **Step 4: Minimize header footprint**

Reduce the header to a compact context label plus help and notifications/user menu if present.

- [ ] **Step 5: Add CSS for sidebar widths and icon-only state**

Add desktop sidebar width and icon-only collapse state for 761–1199px:
```css
.primary-shell { display: grid; grid-template-columns: 200px minmax(0, 1fr); }
.primary-side-nav { width: 200px; }
@media (max-width: 1199px) {
  .primary-shell { grid-template-columns: 64px minmax(0, 1fr); }
  .primary-side-nav--icon { width: 64px; }
}
```

- [ ] **Step 6: Add icon-only labels and tooltips**

Ensure nav items provide `aria-label` and a keyboard-focus tooltip in icon-only mode
using a `data-nav-tooltip` attribute and CSS that shows the tooltip on hover + focus-visible.

- [ ] **Step 7: Allow sidebar overflow scrolling**

Set `overflow-y: auto` on the sidebar so tall menus stay usable.

- [ ] **Step 8: Add drawer mode for <=760px**

Implement hidden drawer + scrim + menu button placement, with explicit dialog semantics:
```html
<div class="primary-side-drawer" role="dialog" aria-modal="true" aria-label="Primary navigation">
  <div class="primary-side-drawer__scrim" data-nav-drawer-close></div>
  <div class="primary-side-drawer__panel">
    <!-- nav buttons -->
  </div>
</div>
```

```css
@media (max-width: 760px) {
  .primary-shell { grid-template-columns: 1fr; }
  .primary-side-nav { display: none; }
  .primary-side-drawer { display: block; }
}
```

- [ ] **Step 9: Add JS to toggle drawer**

Add a small script to open/close drawer, lock body scroll, close on Esc/scrim, close on selection, focus trap inside drawer, and return focus to toggle button.

- [ ] **Step 10: Run tests to verify pass**

Run:
```bash
pytest -q tests/test_ops_shell_bootstrap.py::test_primary_navigation_moves_to_left_sidebar
```
Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add /Volumes/Data/Works/07.__PROJECT_SLUG__/app/static/index.html \
        /Volumes/Data/Works/07.__PROJECT_SLUG__/tests/test_ops_shell_bootstrap.py
git commit -m "style: move primary nav to left sidebar"
```

---

### Task 3: Verification

- [ ] **Step 1: Run focused test set**

Run:
```bash
pytest -q tests/test_ops_shell_bootstrap.py
```
Expected: PASS (note: repo has unrelated failures; document any pre-existing fails).

- [ ] **Step 2: Manual visual checks**

Verify at 1440px, 1200px, 1199px, 1080px, 761px, 760px:
- Sidebar renders left and does not push sub-tabs out of main content.
- Icon-only mode shows tooltips + aria-labels.
- Drawer opens/closes, locks scroll, traps focus, closes on Esc/scrim, and returns focus.
- Sidebar overflow scroll works when nav list exceeds viewport height.

- [ ] **Step 3: Commit any follow-ups**

```bash
git status -sb
```
Commit any fixes with a small follow-up message.
