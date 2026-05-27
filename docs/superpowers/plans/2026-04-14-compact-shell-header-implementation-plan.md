# Compact Shell Header Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce header + menu height by ~30–40% across admin and ops while keeping only Language + Ops/Admin toggle + User/Logout in the header and preserving icon+text tabs.

**Architecture:** Apply a compact-density scale via CSS tokens and a shell-level density flag, then tighten hero/header/tab/utility styles in `app/static/index.html`. Remove header-level doc links/extra actions so the utility bar only includes language + mode switch + logout.

**Tech Stack:** HTML/CSS/JS in `app/static/index.html`, pytest string-based UI tests in `tests/test_ops_shell_bootstrap.py`.

---

## Baseline (pre-existing) test failures
`pytest -q` currently fails 13 tests before any changes (DB migration + ops feed fixtures). These are unrelated to this header compaction. For this plan, run **targeted tests only** for modified tests.

---

## File Map
- Modify: `/Volumes/Data/Works/07.hahahoho/.worktrees/compact-shell-plan/app/static/index.html`
  - CSS: shell header + utility sizing tokens
  - HTML: shell utility bar (remove doc links) and body density flag
  - JS: shell density sync to apply compact class/flag
- Modify: `/Volumes/Data/Works/07.hahahoho/.worktrees/compact-shell-plan/tests/test_ops_shell_bootstrap.py`
  - Update header/utility expectations for compact mode
  - Add/adjust assertions for compact density flag

---

### Task 1: Introduce compact density flag + tokens

**Files:**
- Modify: `/Volumes/Data/Works/07.hahahoho/.worktrees/compact-shell-plan/app/static/index.html`
- Test: `/Volumes/Data/Works/07.hahahoho/.worktrees/compact-shell-plan/tests/test_ops_shell_bootstrap.py`

- [ ] **Step 1: Write failing test for compact density flag**

```python
# tests/test_ops_shell_bootstrap.py

def test_index_shell_compact_density_flag_present():
    html = read_static_html("index.html")
    assert 'data-shell-density="compact"' in html
    assert 'document.body.dataset.shellDensity = "compact";' in html
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
pytest tests/test_ops_shell_bootstrap.py::test_index_shell_compact_density_flag_present -q
```
Expected: FAIL (flag not present)

- [ ] **Step 3: Implement compact density flag**

Add to `<body>` and JS `syncShellDensityClasses`:
```html
<body data-shell-mode="ops" data-shell-readonly="true" data-shell-density="compact">
```

```js
function syncShellDensityClasses() {
  document.body.dataset.shellDensity = "compact";
  // existing compact class toggles remain
}
```

- [ ] **Step 4: Add compact sizing tokens (CSS)**

Introduce CSS variables scoped to `body[data-shell-density="compact"]` and use them in:
- `.admin-shell-hero`
- `.ops-home-hero`
- `.shell-header-row .tab-btn`
- `.shell-utility .chip` / `.shell-utility .tab-btn`
- `.shell-locale-picker`

Example snippet (values refined during implementation):
```css
body[data-shell-density="compact"] {
  --shell-tab-height: 28px;
  --shell-tab-font: 0.76rem;
  --shell-tab-pad-x: 9px;
  --shell-tab-pad-y: 4px;
  --shell-utility-height: 26px;
  --shell-utility-font: 0.74rem;
}
```

- [ ] **Step 5: Run the test and confirm pass**

Run:
```bash
pytest tests/test_ops_shell_bootstrap.py::test_index_shell_compact_density_flag_present -q
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/static/index.html tests/test_ops_shell_bootstrap.py
git commit -m "ui: add compact shell density flag"
```

---

### Task 2: Compact header + tabs to 30–40% reduction

**Files:**
- Modify: `/Volumes/Data/Works/07.hahahoho/.worktrees/compact-shell-plan/app/static/index.html`
- Test: `/Volumes/Data/Works/07.hahahoho/.worktrees/compact-shell-plan/tests/test_ops_shell_bootstrap.py`

- [ ] **Step 1: Update failing tests for new compact sizes**

Adjust the assertions in these tests to the new compact sizes:
- `test_index_header_utility_stacks_docs_and_locale_above_session_actions`
- `test_index_ops_home_compacts_hero_art_and_focus_chip_grid`
- `test_index_compact_hero_variants_reduce_padding_one_more_step`

Update expected values to match the new compact token targets:
```python
assert "min-height: 28px;" in utility_btn_block
assert "font-size: 0.76rem;" in utility_btn_block
```

- [ ] **Step 2: Run the updated tests (should fail before CSS changes)**

Run:
```bash
pytest tests/test_ops_shell_bootstrap.py::test_index_header_utility_stacks_docs_and_locale_above_session_actions -q
```
Expected: FAIL (CSS not yet updated)

- [ ] **Step 3: Apply compact sizing CSS**

Update CSS blocks to use the new compact tokens for:
- `.admin-shell-hero`, `.admin-shell-hero--compact`
- `.ops-home-hero`, `.ops-home-hero--compact`
- `.shell-utility`, `.shell-utility-main`, `.shell-utility-tools`
- `.shell-utility .tab-btn`, `.shell-utility .chip`
- `.shell-header-row .tab-btn`

- [ ] **Step 4: Re-run the updated tests**

Run:
```bash
pytest tests/test_ops_shell_bootstrap.py::test_index_header_utility_stacks_docs_and_locale_above_session_actions -q
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/static/index.html tests/test_ops_shell_bootstrap.py
git commit -m "ui: compact header and tab sizing"
```

---

### Task 3: Remove header doc links + extra actions (keep only language/admin/logout)

**Files:**
- Modify: `/Volumes/Data/Works/07.hahahoho/.worktrees/compact-shell-plan/app/static/index.html`
- Test: `/Volumes/Data/Works/07.hahahoho/.worktrees/compact-shell-plan/tests/test_ops_shell_bootstrap.py`

- [ ] **Step 1: Update tests to reflect doc-link removal**

Adjust tests that assert doc-link presence (remove or update assertions):
- `test_index_admin_docs_box_becomes_compact_trigger_panel`
- `test_index_shell_utility_exposes_direct_doc_links_with_routes`
- `test_index_header_utility_stacks_docs_and_locale_above_session_actions`

Replace with a new expectation:
```python
assert 'class="shell-doc-links admin-shell-docs"' not in utility_block
```

- [ ] **Step 2: Run one of the updated tests (should fail)**

Run:
```bash
pytest tests/test_ops_shell_bootstrap.py::test_index_shell_utility_exposes_direct_doc_links_with_routes -q
```
Expected: FAIL (doc links still present)

- [ ] **Step 3: Remove doc links + extra actions from header utility**

In `shellUtilityBar`:
- Remove `.shell-doc-links` container entirely
- Keep only:
  - `shellLocaleSelect`
  - `shellAdminBtn` (ops/admin toggle)
  - `appLogoutBtn`
- Hide/remove `tabCameraBtn`, `appPrefsResetBtn`, `shellOpsHomeBtn` from header

- [ ] **Step 4: Update `syncShellUtilityRowSizing` list**

Only include active buttons (admin + logout) to avoid resizing hidden elements.

- [ ] **Step 5: Re-run the updated tests**

Run:
```bash
pytest tests/test_ops_shell_bootstrap.py::test_index_shell_utility_exposes_direct_doc_links_with_routes -q
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/static/index.html tests/test_ops_shell_bootstrap.py
git commit -m "ui: reduce header controls to language + mode + logout"
```

---

## Verification (Targeted)
Because baseline tests already fail, run only the tests touched above:

```bash
pytest tests/test_ops_shell_bootstrap.py::test_index_shell_compact_density_flag_present \
  tests/test_ops_shell_bootstrap.py::test_index_header_utility_stacks_docs_and_locale_above_session_actions \
  tests/test_ops_shell_bootstrap.py::test_index_shell_utility_exposes_direct_doc_links_with_routes -q
```

Expected: PASS

---

## Rollback Plan
If layout regression appears:
- Revert the most recent commit(s) in order: 
  1) doc-link removal commit
  2) compact header sizing commit
  3) density-flag commit

---
