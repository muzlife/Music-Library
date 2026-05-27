# Dashboard & Master Console Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the admin `대시보드` and `마스터 정리` screens into a shared operational-console UI without changing their underlying workflows, ids, or event behavior.

**Architecture:** Keep all behavior in place and implement the redesign entirely inside `app/static/index.html` by adding tightly scoped console tokens, shell classes, and layout wrappers around the existing dashboard and registered-master-merge DOM anchors. Protect the redesign with static HTML/CSS/JS assertions in targeted pytest files rather than broad end-to-end changes.

**Tech Stack:** HTML/CSS/vanilla JS in `app/static/index.html`, pytest static markup tests in `tests/test_ops_shell_bootstrap.py` and `tests/test_master_merge_workbench_ui.py`, Node-based inline script parse check.

---

## Scope Notes
- Only the following surfaces change in this phase:
  - `#homeDashboardCard`
  - `#registeredMasterMergeCard`
- Preserve all existing ids used by runtime JS.
- Do not touch backend routes or merge logic in this plan.
- Because the repository can contain unrelated failing tests, use targeted tests only for this work.

## File Map
- Modify: `/Volumes/Data/Works/07.hahahoho/app/static/index.html`
  - Add shared console tokens scoped to dashboard/master surfaces
  - Reframe dashboard shell into status/telemetry/main/action rails
  - Reframe registered master merge shell into command/results/workspace/log regions
  - Keep existing ids and runtime event anchors intact
- Modify: `/Volumes/Data/Works/07.hahahoho/tests/test_ops_shell_bootstrap.py`
  - Add/adjust assertions for dashboard console shell classes and scoped CSS tokens
  - Add/adjust assertions for dashboard responsive console rules
- Modify: `/Volumes/Data/Works/07.hahahoho/tests/test_master_merge_workbench_ui.py`
  - Add/adjust assertions for registered master merge command/workspace/log shell structure
  - Keep existing state/function/event binding assertions intact

---

### Task 1: Introduce shared console tokens and root shell hooks

**Files:**
- Modify: `/Volumes/Data/Works/07.hahahoho/app/static/index.html`
- Test: `/Volumes/Data/Works/07.hahahoho/tests/test_ops_shell_bootstrap.py`
- Test: `/Volumes/Data/Works/07.hahahoho/tests/test_master_merge_workbench_ui.py`

- [ ] **Step 1: Write failing tests for the new root shell hooks**

```python
# tests/test_ops_shell_bootstrap.py
def test_index_dashboard_console_shell_roots_exist():
    html = read_static_html("index.html")
    assert 'id="homeDashboardCard" class="card dashboard-screen dashboard-console-shell"' in html
    assert "--console-bg:" in html
    assert "--console-panel:" in html


# tests/test_master_merge_workbench_ui.py
def test_registered_master_merge_console_shell_roots_exist():
    html = read_index_html()
    assert 'id="registeredMasterMergeCard" class="card registered-master-merge-console"' in html
    assert 'class="registered-master-merge-console-shell"' in html
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:
```bash
pytest tests/test_ops_shell_bootstrap.py::test_index_dashboard_console_shell_roots_exist \
  tests/test_master_merge_workbench_ui.py::test_registered_master_merge_console_shell_roots_exist -q
```
Expected: FAIL because the shell classes and console tokens do not exist yet.

- [ ] **Step 3: Add minimal console tokens and root classes**

In `/Volumes/Data/Works/07.hahahoho/app/static/index.html`:
- add `dashboard-console-shell` to `#homeDashboardCard`
- add `registered-master-merge-console` to `#registeredMasterMergeCard`
- introduce tightly scoped CSS tokens, for example:

```css
#homeDashboardCard.dashboard-console-shell,
#registeredMasterMergeCard.registered-master-merge-console {
  --console-bg: #0b0e12;
  --console-panel: #11161d;
  --console-panel-soft: #171d25;
  --console-border: rgba(137, 151, 171, 0.24);
  --console-accent: #ff7a1a;
  --console-text: #edf2f7;
  --console-text-dim: #95a2b3;
}
```

- [ ] **Step 4: Add a shared shell wrapper without changing ids**

Wrap existing dashboard and master sections in new shell containers/classes only. Do not rename or remove runtime ids.

Example:
```html
<section id="registeredMasterMergeCard" class="card registered-master-merge-console">
  <div class="registered-master-merge-console-shell">
    ...
  </div>
</section>
```

- [ ] **Step 5: Re-run the targeted tests**

Run:
```bash
pytest tests/test_ops_shell_bootstrap.py::test_index_dashboard_console_shell_roots_exist \
  tests/test_master_merge_workbench_ui.py::test_registered_master_merge_console_shell_roots_exist -q
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/static/index.html tests/test_ops_shell_bootstrap.py tests/test_master_merge_workbench_ui.py
git commit -m "ui: add console shell tokens for dashboard and master merge"
```

---

### Task 2: Reframe dashboard into console status, telemetry, and dual-rail layout

**Files:**
- Modify: `/Volumes/Data/Works/07.hahahoho/app/static/index.html`
- Test: `/Volumes/Data/Works/07.hahahoho/tests/test_ops_shell_bootstrap.py`

- [ ] **Step 1: Write failing tests for the dashboard console layout**

```python
def test_index_dashboard_console_layout_regions_exist():
    html = read_static_html("index.html")
    assert 'class="dashboard-topbar dashboard-console-statusbar"' in html
    assert 'class="dashboard-hero-grid dashboard-console-telemetry"' in html
    assert 'class="dashboard-main-grid dashboard-console-main"' in html
    assert 'class="dashboard-panel dashboard-slot-panel dashboard-console-panel dashboard-console-panel--primary"' in html
    assert 'class="dashboard-panel dashboard-workbench-panel dashboard-console-panel dashboard-console-panel--rail"' in html
```

- [ ] **Step 2: Run the dashboard layout test to confirm failure**

Run:
```bash
pytest tests/test_ops_shell_bootstrap.py::test_index_dashboard_console_layout_regions_exist -q
```
Expected: FAIL because the new layout classes are not present.

- [ ] **Step 3: Add dashboard shell classes and panel roles**

In `/Volumes/Data/Works/07.hahahoho/app/static/index.html`:
- add `dashboard-console-statusbar` to `.dashboard-topbar`
- add `dashboard-console-telemetry` to `.dashboard-hero-grid`
- add `dashboard-console-main` to `.dashboard-main-grid`
- add panel role classes to slot/workbench panels

Example:
```html
<div class="dashboard-topbar dashboard-console-statusbar">
...
<div class="dashboard-hero-grid dashboard-console-telemetry">
...
<div class="dashboard-main-grid dashboard-console-main">
...
<section class="dashboard-panel dashboard-slot-panel dashboard-console-panel dashboard-console-panel--primary">
...
<section class="dashboard-panel dashboard-workbench-panel dashboard-console-panel dashboard-console-panel--rail">
```

- [ ] **Step 4: Apply console-specific dashboard CSS**

Add scoped CSS for:
- status bar framing
- telemetry tiles with harder panel borders
- central/rail grid balance
- darker workbench rail treatment
- selected/focus states using orange edge emphasis rather than teal card fill

Keep the existing interactive rules and ids untouched.

- [ ] **Step 5: Add/adjust responsive rules for the dashboard console shell**

Add targeted breakpoint rules so:
- desktop keeps status + telemetry + main rails
- medium widths compress telemetry first
- narrower admin widths stack the workbench below the primary slot panel

Do not change phone behavior outside the dashboard shell.

- [ ] **Step 6: Re-run targeted dashboard tests**

Run:
```bash
pytest tests/test_ops_shell_bootstrap.py::test_index_dashboard_console_layout_regions_exist \
  tests/test_ops_shell_bootstrap.py::test_index_dashboard_cabinet_detail_hides_floor_grid_below_cover_flow \
  tests/test_ops_shell_bootstrap.py::test_index_dashboard_runtime_sections_use_i18n_keys -q
```
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/static/index.html tests/test_ops_shell_bootstrap.py
git commit -m "ui: reshape dashboard into console layout"
```

---

### Task 3: Reframe registered master merge into command/results/workspace/log console

**Files:**
- Modify: `/Volumes/Data/Works/07.hahahoho/app/static/index.html`
- Test: `/Volumes/Data/Works/07.hahahoho/tests/test_master_merge_workbench_ui.py`

- [ ] **Step 1: Write failing tests for the master console regions**

```python
def test_registered_master_merge_console_regions_exist():
    html = read_index_html()
    assert 'class="registered-master-merge-commandbar"' in html
    assert 'class="registered-master-merge-console-grid"' in html
    assert 'class="registered-master-merge-results-panel"' in html
    assert 'class="registered-master-merge-workspace-panel"' in html
    assert 'class="registered-master-merge-log-panel"' in html
```

- [ ] **Step 2: Run the target test to confirm failure**

Run:
```bash
pytest tests/test_master_merge_workbench_ui.py::test_registered_master_merge_console_regions_exist -q
```
Expected: FAIL because the shell region classes do not exist yet.

- [ ] **Step 3: Wrap the existing registered master merge DOM in console regions**

In `/Volumes/Data/Works/07.hahahoho/app/static/index.html`, keep all ids intact but add wrappers:

```html
<div class="registered-master-merge-commandbar">
  <!-- query, search/clear, representative summary, target summary, run button -->
</div>

<div class="registered-master-merge-console-grid">
  <section class="registered-master-merge-results-panel">...</section>
  <section class="registered-master-merge-workspace-panel">...</section>
</div>

<section class="registered-master-merge-log-panel">...</section>
```

- [ ] **Step 4: Move summary lines into the command/workspace hierarchy without changing ids**

Keep:
- `registeredMasterMergeQuery`
- `registeredMasterMergeSearchBtn`
- `registeredMasterMergeClearBtn`
- `registeredMasterMergeRepresentativeSummary`
- `registeredMasterMergeTargetSummary`
- `registeredMasterMergeRunBtn`
- `registeredMasterMergeHistoryBody`

Only re-group them visually so the command bar reads as a control strip and the history block reads as an operator log.

- [ ] **Step 5: Add scoped CSS for the master console**

Add styles for:
- command bar framing
- right-aligned result actions
- stronger representative focus card
- armed but secondary merge target stack
- history/log styling

Do not change merge state, fetch logic, or rollback logic.

- [ ] **Step 6: Re-run master merge tests**

Run:
```bash
pytest tests/test_master_merge_workbench_ui.py -q
```
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/static/index.html tests/test_master_merge_workbench_ui.py
git commit -m "ui: reshape master merge into console workspace"
```

---

### Task 4: Final responsive polish and verification

**Files:**
- Modify: `/Volumes/Data/Works/07.hahahoho/app/static/index.html`
- Modify: `/Volumes/Data/Works/07.hahahoho/tests/test_ops_shell_bootstrap.py`
- Modify: `/Volumes/Data/Works/07.hahahoho/tests/test_master_merge_workbench_ui.py`

- [ ] **Step 1: Add final failing tests for console-specific responsive hooks**

```python
# tests/test_ops_shell_bootstrap.py
def test_index_dashboard_console_shell_has_scoped_responsive_rules():
    html = read_static_html("index.html")
    assert ".dashboard-console-main {" in html
    assert ".dashboard-console-telemetry {" in html


# tests/test_master_merge_workbench_ui.py
def test_registered_master_merge_console_has_scoped_workspace_responsive_rules():
    html = read_index_html()
    assert ".registered-master-merge-console-grid {" in html
    assert ".registered-master-merge-commandbar {" in html
```

- [ ] **Step 2: Run the new responsive tests to verify they fail if rules are absent**

Run:
```bash
pytest tests/test_ops_shell_bootstrap.py::test_index_dashboard_console_shell_has_scoped_responsive_rules \
  tests/test_master_merge_workbench_ui.py::test_registered_master_merge_console_has_scoped_workspace_responsive_rules -q
```
Expected: FAIL if the scoped rules are not present yet.

- [ ] **Step 3: Finish breakpoint tuning**

Adjust only the scoped classes added in this feature so:
- dashboard telemetry collapses gracefully
- dashboard rails stack in smaller admin widths
- master merge results/workspace stack cleanly
- command bar keeps the search field and primary action readable

- [ ] **Step 4: Run targeted verification**

Run:
```bash
pytest tests/test_master_merge_workbench_ui.py -q
pytest tests/test_ops_shell_bootstrap.py -k 'dashboard_console_layout_regions_exist or dashboard_console_shell_roots_exist or dashboard_console_shell_has_scoped_responsive_rules or index_dashboard_runtime_sections_use_i18n_keys or index_dashboard_cabinet_detail_hides_floor_grid_below_cover_flow' -q
node - <<'NODE'
const fs = require('fs');
const html = fs.readFileSync('app/static/index.html', 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
for (const script of scripts) new Function(script);
console.log('inline script parse ok');
NODE
```
Expected:
- targeted pytest checks PASS
- Node prints `inline script parse ok`

- [ ] **Step 5: Commit**

```bash
git add app/static/index.html tests/test_ops_shell_bootstrap.py tests/test_master_merge_workbench_ui.py
git commit -m "ui: finish console redesign polish for dashboard and master merge"
```

---

## Final Verification

Run:
```bash
pytest tests/test_master_merge_workbench_ui.py -q
pytest tests/test_ops_shell_bootstrap.py -k 'dashboard_console_layout_regions_exist or dashboard_console_shell_roots_exist or dashboard_console_shell_has_scoped_responsive_rules or index_dashboard_runtime_sections_use_i18n_keys or index_dashboard_cabinet_detail_hides_floor_grid_below_cover_flow' -q
node - <<'NODE'
const fs = require('fs');
const html = fs.readFileSync('app/static/index.html', 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
for (const script of scripts) new Function(script);
console.log('inline script parse ok');
NODE
```

Expected:
- all targeted tests PASS
- inline script parse succeeds

## Rollback Plan
- Revert commits in reverse order:
  1. console polish
  2. master merge console workspace
  3. dashboard console layout
  4. console shell tokens
- If only one screen regresses, revert only the corresponding commit and keep the other surface intact.
