# Global Day/Night Theme Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a manual day/night theme toggle for the full shell and persist the choice in the browser.

**Architecture:** Use a single `body[data-theme]` switch and existing console color tokens. Keep the current night palette as default and layer a day palette plus narrow overrides for hard-coded dark/light surfaces.

**Tech Stack:** Static HTML/CSS/JavaScript in `app/static/index.html`, pytest snapshot-style tests in `tests/test_ops_shell_bootstrap.py`

---

### Task 1: Add theme toggle contract tests

**Files:**
- Modify: `app/static/index.html`
- Test: `tests/test_ops_shell_bootstrap.py`

- [ ] **Step 1: Write the failing test**

Add assertions for:
- `shellThemeToggleBtn` markup near `shellLocaleSelect`
- `APP_THEME_STORAGE_KEY`
- `loadStoredAppTheme`, `applyAppTheme`, `toggleAppTheme`
- `body.dataset.theme`

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_ops_shell_bootstrap.py -q -k "theme_toggle"`

- [ ] **Step 3: Write minimal implementation**

Add the header button and theme helpers without changing broad styling yet.

- [ ] **Step 4: Run test to verify it passes**

Run the same command and confirm green.

### Task 2: Wire persisted theme state into shell boot

**Files:**
- Modify: `app/static/index.html`
- Test: `tests/test_ops_shell_bootstrap.py`

- [ ] **Step 1: Write the failing test**

Add assertions that shell boot and locale boot call theme restore/apply.

- [ ] **Step 2: Run test to verify it fails**

Run targeted pytest.

- [ ] **Step 3: Write minimal implementation**

Initialize theme during shell startup and bind button click.

- [ ] **Step 4: Run test to verify it passes**

Run targeted pytest.

### Task 3: Add day palette and full-shell token overrides

**Files:**
- Modify: `app/static/index.html`
- Test: `tests/test_ops_shell_bootstrap.py`

- [ ] **Step 1: Write the failing test**

Assert `body[data-theme="day"]` token block exists and key shell selectors consume tokens.

- [ ] **Step 2: Run test to verify it fails**

Run targeted pytest.

- [ ] **Step 3: Write minimal implementation**

Add day token block and targeted overrides for header, dashboard, manage/search/register, collectibles, source workbench, exception queue.

- [ ] **Step 4: Run test to verify it passes**

Run full targeted pytest for theme selectors.

### Task 4: QA verification

**Files:**
- Modify: `app/static/index.html`

- [ ] **Step 1: Copy updated static file to QA app root**
- [ ] **Step 2: Restart QA app**
- [ ] **Step 3: Verify `/health`**
- [ ] **Step 4: Inspect QA in browser and toggle day/night**

