# Full Admin Console Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the hard-edge console shell from the redesigned dashboard and master-merge surfaces to the rest of the admin tabs while preserving all existing workflows and route/state behavior.

**Architecture:** Keep the work inside `app/static/index.html`, reusing the existing dashboard/master console tokens and expanding them into shared admin-console shell helpers plus tab-scoped panel rules. Validate the rollout with static shell assertions in `tests/test_ops_shell_bootstrap.py` and keep `tests/test_master_merge_workbench_ui.py` green so the existing master-merge console contract does not regress.

**Tech Stack:** Static HTML/CSS/vanilla JS in `app/static/index.html`, pytest string-based UI assertions, manual QA in the browser/QA environment.

---

## File Map & Ownership

**Modify**
- `/Volumes/Data/Works/07.__PROJECT_SLUG__/app/static/index.html`
  - Extend shared admin console tokens and shell helpers.
  - Apply common panel grammar to `#tabSimple`, `#tabCamera`, `#tabMedia`, `#tabCollectibles`, and `#tabOps`.
  - Keep prior-phase dashboard/master-merge behavior unchanged except for shared shell normalization.
- `/Volumes/Data/Works/07.__PROJECT_SLUG__/tests/test_ops_shell_bootstrap.py`
  - Add static assertions for the new admin-wide console shell, tab anchors, responsive thresholds, and hard-edge panel rules.
- `/Volumes/Data/Works/07.__PROJECT_SLUG__/tests/test_master_merge_workbench_ui.py`
  - Only update if the shared shell extension changes existing root selectors or scoped workspace rules used by the current master-merge console assertions.

**Do Not Modify Unless A Test Forces It**
- Backend files
- Routing logic outside existing shell/tab behavior
- Data or API layers

---

### Task 1: Add Failing Tests For Admin-Wide Console Shell Expansion

**Files:**
- Modify: `/Volumes/Data/Works/07.__PROJECT_SLUG__/tests/test_ops_shell_bootstrap.py`
- Optional: `/Volumes/Data/Works/07.__PROJECT_SLUG__/tests/test_master_merge_workbench_ui.py`

- [ ] **Step 1: Add a failing test for shared admin console roots and anchors**

Create a new test near the current dashboard console tests, for example:

```python
def test_index_admin_console_shell_roots_exist_outside_dashboard():
    html = read_static_html("index.html")
    assert 'id="opsHomeLayout" class="ops-home-layout operator-shell admin-console-shell"' in html
    assert 'class="card shared-camera-shell admin-console-shell"' in html
    assert 'id="tabMedia" class="tab-panel page-column admin-console-shell"' in html
    assert 'class="card goods-shell admin-console-shell"' in html
    assert 'id="tabOps" class="tab-panel admin-console-shell"' in html
```

- [ ] **Step 2: Add a failing test for shared admin console tokens and responsive thresholds**

Add a second test that asserts the presence of new shared selectors and explicit breakpoints:

```python
def test_index_admin_console_shell_has_shared_tokens_and_breakpoints():
    html = read_static_html("index.html")
    assert ".admin-console-shell {" in html
    assert "--admin-console-panel-bg:" in html
    assert "--admin-console-panel-border:" in html
    assert "--admin-console-text:" in html
    assert "@media (max-width: 1280px)" in html
    assert "@media (max-width: 1120px)" in html
```

- [ ] **Step 3: Add a failing test for hard-edge admin surfaces outside dashboard/master-merge**

Add assertions for tabs that still use legacy card shells today:

```python
def test_index_admin_console_extension_removes_rounded_tab_surfaces():
    html = read_static_html("index.html")
    for selector in [
        ".admin-console-shell .card {",
        ".admin-console-shell input,",
        ".admin-console-shell select,",
        ".admin-console-shell textarea {",
    ]:
        assert selector in html
    shell_block = html.split(".admin-console-shell .card {", 1)[1].split("}", 1)[0]
    assert "border-radius: 0;" in shell_block
```

- [ ] **Step 4: Run tests to verify they fail**

Run:
```bash
pytest -q tests/test_ops_shell_bootstrap.py -k 'admin_console_shell_roots_exist_outside_dashboard or admin_console_shell_has_shared_tokens_and_breakpoints or admin_console_extension_removes_rounded_tab_surfaces'
```
Expected: FAIL because the new shared shell selectors do not exist yet.

- [ ] **Step 5: Do not commit yet**

Keep the tree red until Task 2 turns these targeted tests green. Commit the tests together with the matching implementation.

---

### Task 2: Implement Shared Admin Console Shell Helpers

**Files:**
- Modify: `/Volumes/Data/Works/07.__PROJECT_SLUG__/app/static/index.html`

- [ ] **Step 1: Add the shared admin console shell class to in-scope tab roots**

Apply `admin-console-shell` to the roots defined by the spec:
- `#opsHomeLayout`
- `.shared-camera-shell`
- `#tabMedia`
- `.goods-shell`
- `#tabOps`

Representative edits:

```html
<section id="opsHomeLayout" class="ops-home-layout operator-shell admin-console-shell">
<section class="card shared-camera-shell admin-console-shell">
<div id="tabMedia" class="tab-panel page-column admin-console-shell">
<section class="card goods-shell admin-console-shell">
<div id="tabOps" class="tab-panel admin-console-shell">
```

- [ ] **Step 2: Add shared token definitions and shell helpers**

Under the existing console-shell CSS area, define admin-wide helpers such as:

```css
.admin-console-shell {
  --admin-console-panel-bg: rgba(18, 23, 29, 0.98);
  --admin-console-panel-bg-2: rgba(22, 28, 36, 0.98);
  --admin-console-panel-border: rgba(108, 124, 142, 0.24);
  --admin-console-text: #f3f6fb;
  --admin-console-text-muted: #c2ccd7;
  --admin-console-text-meta: #8e99a7;
  --admin-console-accent: #ff7a1a;
}

.admin-console-shell .card,
.admin-console-shell .manual-block,
.admin-console-shell .table-wrap,
.admin-console-shell .result-list,
.admin-console-shell .result-item {
  border-radius: 0;
  background: var(--admin-console-panel-bg);
  border: 1px solid var(--admin-console-panel-border);
  box-shadow: none;
}
```

- [ ] **Step 3: Extend form and control normalization**

Add admin-shell-scoped rules for:
- `input`, `select`, `textarea`
- inline chips/badges/mini panels
- `result-head`, `status`, `compact-line`, `manual-block`

Representative rule set:

```css
.admin-console-shell :is(input, select, textarea) {
  border-radius: 0;
  background: rgba(15, 20, 26, 0.98);
  color: var(--admin-console-text);
  border: 1px solid rgba(108, 124, 142, 0.22);
}
```

- [ ] **Step 4: Add responsive shell rules**

Introduce explicit thresholds from the spec:

```css
@media (max-width: 1280px) {
  .admin-console-shell .admin-console-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 1120px) {
  .admin-console-shell .admin-console-secondary,
  .admin-console-shell .admin-console-rail {
    grid-column: 1;
  }
}
```

Use the actual class names that fit the final implementation, but keep the two explicit breakpoints.

- [ ] **Step 5: Run the targeted tests**

Run:
```bash
pytest -q tests/test_ops_shell_bootstrap.py -k 'admin_console_shell_roots_exist_outside_dashboard or admin_console_shell_has_shared_tokens_and_breakpoints or admin_console_extension_removes_rounded_tab_surfaces'
```
Expected: PASS.

- [ ] **Step 6: Commit the shared shell implementation and tests**

```bash
git add app/static/index.html tests/test_ops_shell_bootstrap.py
git commit -m "style: extend shared admin console shell"
```

---

### Task 3: Reframe `#tabSimple` And `#tabCamera` Into Console Surfaces

**Files:**
- Modify: `/Volumes/Data/Works/07.__PROJECT_SLUG__/app/static/index.html`
- Modify: `/Volumes/Data/Works/07.__PROJECT_SLUG__/tests/test_ops_shell_bootstrap.py`

- [ ] **Step 1: Add failing tests for `#tabSimple` and `#tabCamera` shell regions**

Add/extend tests with assertions like:

```python
def test_index_operator_home_and_camera_use_console_region_markup():
    html = read_static_html("index.html")
    assert 'class="ops-home-main operator-shell-main admin-console-main"' in html
    assert 'id="opsLibraryContextPanel" class="ops-library-context-panel operator-shell-sidebar admin-console-secondary"' in html
    assert 'class="shared-camera-layout admin-console-grid"' in html
    assert 'class="shared-camera-list-panel admin-console-secondary"' in html
    assert 'id="sharedCameraPreview" class="shared-camera-preview-panel admin-console-main"' in html
```

- [ ] **Step 2: Run the new test to verify it fails**

Run:
```bash
pytest -q tests/test_ops_shell_bootstrap.py -k 'operator_home_and_camera_use_console_region_markup'
```
Expected: FAIL because the new region classes are not applied yet.

- [ ] **Step 3: Apply region classes and panel hierarchy in `index.html`**

Make minimal DOM changes only where needed, for example:

```html
<div class="ops-home-main operator-shell-main admin-console-main">
<aside id="opsLibraryContextPanel" class="ops-library-context-panel operator-shell-sidebar admin-console-secondary">
<div class="shared-camera-layout admin-console-grid">
<aside class="shared-camera-list-panel admin-console-secondary">
<section id="sharedCameraPreview" class="shared-camera-preview-panel admin-console-main">
```

- [ ] **Step 4: Add tab-scoped CSS to align these surfaces with the console grammar**

Add targeted rules for:
- `#opsHomeLayout.admin-console-shell`
- `.shared-camera-shell.admin-console-shell`
- `.operator-home-card`
- `.operator-weather-card`
- `.shared-camera-list-panel`
- `.shared-camera-preview-panel`

Keep behavior intact; only change framing, spacing, borders, and surface contrast.

- [ ] **Step 5: Run the targeted tests**

Run:
```bash
pytest -q tests/test_ops_shell_bootstrap.py -k 'operator_home_and_camera_use_console_region_markup or operator_home_search_uses_curator_shell_markup'
```
Expected: PASS.

- [ ] **Step 6: Commit the tab-specific changes**

```bash
git add app/static/index.html tests/test_ops_shell_bootstrap.py
git commit -m "style: bring operator home and camera into console shell"
```

---

### Task 4: Reframe `#tabMedia`, `#tabSearch`, `#tabManage`, `#tabRegister`, and `#tabSource` Without Changing Submode Behavior

**Files:**
- Modify: `/Volumes/Data/Works/07.__PROJECT_SLUG__/app/static/index.html`
- Modify: `/Volumes/Data/Works/07.__PROJECT_SLUG__/tests/test_ops_shell_bootstrap.py`
- Optional: `/Volumes/Data/Works/07.__PROJECT_SLUG__/tests/test_master_merge_workbench_ui.py`

- [ ] **Step 1: Add failing tests for media shell coverage**

Add a test that asserts media shell roots and major submode anchors remain present but pick up console framing:

```python
def test_index_media_admin_surfaces_share_console_shell_helpers():
    html = read_static_html("index.html")
    assert 'id="tabMedia" class="tab-panel page-column admin-console-shell"' in html
    assert 'id="adminSearchSurface" class="admin-manage-surface active media-search-layout admin-console-grid"' in html
    assert 'id="adminSearchContextPanel" class="media-search-context-panel admin-console-secondary"' in html
    assert 'id="adminManageSurface" class="admin-manage-surface active admin-console-main"' in html
    assert 'id="tabRegister" class="tab-panel admin-console-shell"' in html or 'id="tabRegister" class="tab-panel page-column admin-console-shell"' in html
    assert 'id="registerCollectPanel" class="subtab-panel active admin-console-main"' in html or 'id="registerCollectPanel" class="subtab-panel admin-console-main"' in html
    assert 'id="registerPurchasePanel" class="subtab-panel admin-console-main"' in html
    assert 'id="registerBatchPanel" class="subtab-panel admin-console-main"' in html
    assert 'id="registerMasterPanel" class="subtab-panel admin-console-main"' in html
    assert 'id="sourceWorkbenchCard" class="card admin-console-shell"' in html or 'id="sourceWorkbenchCard" class="card source-workbench-console"' in html
```

- [ ] **Step 2: Run the media test to verify failure**

Run:
```bash
pytest -q tests/test_ops_shell_bootstrap.py -k 'media_admin_surfaces_share_console_shell_helpers'
```
Expected: FAIL before the new shell helpers are applied.

- [ ] **Step 3: Apply minimal shell grouping classes to media submode roots**

Use wrappers and class additions only; do not rewire submode behavior.

Representative edits:

```html
<div id="adminSearchSurface" class="admin-manage-surface active media-search-layout admin-console-grid">
<aside id="adminSearchContextPanel" class="media-search-context-panel admin-console-secondary">
<div id="adminManageSurface" class="admin-manage-surface active admin-console-main">
<div id="tabRegister" class="tab-panel admin-console-shell">
<div id="registerCollectPanel" class="subtab-panel active admin-console-main">
<div id="registerPurchasePanel" class="subtab-panel admin-console-main">
<div id="registerBatchPanel" class="subtab-panel admin-console-main">
<div id="registerMasterPanel" class="subtab-panel admin-console-main">
<section id="sourceWorkbenchCard" class="card source-workbench-console admin-console-shell">
```

- [ ] **Step 4: Add CSS for media search/manage/source surfaces**

Add tab-scoped rules for:
- `#tabMedia.admin-console-shell`
- `#tabSearch .admin-console-grid`
- `#tabManage .admin-console-main`
- `#tabRegister.admin-console-shell`
- `#registerCollectPanel`
- `#registerPurchasePanel`
- `#registerBatchPanel`
- `#registerMasterPanel`
- `#sourceWorkbenchCard`
- media mode tabs and page-help blocks

Do not alter form wiring, search semantics, or source workbench behavior.

- [ ] **Step 5: Keep master-merge console assertions green**

Run:
```bash
pytest -q tests/test_master_merge_workbench_ui.py
```
Expected: PASS.

If any selector broke because of shared shell additions, update the test file minimally without changing behavior coverage.

- [ ] **Step 6: Run the media shell tests**

Run:
```bash
pytest -q tests/test_ops_shell_bootstrap.py -k 'media_admin_surfaces_share_console_shell_helpers or dashboard_console_shell_roots_exist'
```
Expected: PASS.

- [ ] **Step 6.1: Run the master-merge regression again**

Run:
```bash
pytest -q tests/test_master_merge_workbench_ui.py
```
Expected: PASS.

- [ ] **Step 7: Commit the media shell changes**

```bash
git add app/static/index.html tests/test_ops_shell_bootstrap.py tests/test_master_merge_workbench_ui.py
git commit -m "style: extend console shell across media admin surfaces"
```

---

### Task 5: Reframe `#tabCollectibles` And Every In-Scope `#tabOps` Subpanel Using The Same Panel Grammar

**Files:**
- Modify: `/Volumes/Data/Works/07.__PROJECT_SLUG__/app/static/index.html`
- Modify: `/Volumes/Data/Works/07.__PROJECT_SLUG__/tests/test_ops_shell_bootstrap.py`

- [ ] **Step 1: Add failing tests for collectibles and ops console regions**

Add tests such as:

```python
def test_index_collectibles_and_ops_use_console_panel_grammar():
    html = read_static_html("index.html")
    assert 'class="card goods-shell admin-console-shell"' in html
    assert 'id="goodsSearchSurface" class="goods-surface active admin-console-main"' in html
    assert 'id="goodsManageSurface" class="goods-surface admin-console-main"' in html
    assert 'id="goodsRegisterSurface" class="goods-surface admin-console-main"' in html
    assert 'id="tabOps" class="tab-panel admin-console-shell"' in html
    for marker in [
        'id="opsCabinetPanel" class="subtab-panel admin-console-main"',
        'id="opsCameraPanel" class="subtab-panel admin-console-main"',
        'id="opsSlotPanel" class="subtab-panel admin-console-main"',
        'id="opsExceptionPanel" class="subtab-panel admin-console-main"',
        'id="opsAccountPanel" class="subtab-panel admin-console-main"',
        'id="opsProviderPanel" class="subtab-panel admin-console-main"',
        'id="opsExportPanel" class="subtab-panel admin-console-main"',
        'id="opsMetaSyncPanel" class="subtab-panel admin-console-main"',
    ]:
        assert marker in html or marker.replace('class="subtab-panel admin-console-main"', 'class="subtab-panel active admin-console-main"') in html
```

Also add a focused test for ops subtab/status anchors:

```python
def test_index_ops_console_status_and_exception_anchors_remain_present():
    html = read_static_html("index.html")
    for marker in [
        'id="opsSystemStatusSummary"',
        'id="opsSystemStatusLine"',
        'id="opsExceptionSummary"',
        'id="opsExceptionList"',
        'id="opsExceptionSelectionSummary"',
    ]:
        assert marker in html
```

- [ ] **Step 2: Run the new tests to verify failure**

Run:
```bash
pytest -q tests/test_ops_shell_bootstrap.py -k 'collectibles_and_ops_use_console_panel_grammar or ops_console_status_and_exception_anchors_remain_present'
```
Expected: FAIL because the new console region classes are not present yet.

- [ ] **Step 3: Apply minimal class additions to collectibles and ops roots**

Representative edits:

```html
<div id="goodsSearchSurface" class="goods-surface active admin-console-main">
<div id="goodsManageSurface" class="goods-surface admin-console-main">
<div id="goodsRegisterSurface" class="goods-surface admin-console-main">
<div id="opsCabinetPanel" class="subtab-panel admin-console-main">
<div id="opsCameraPanel" class="subtab-panel admin-console-main">
<div id="opsSlotPanel" class="subtab-panel admin-console-main">
<div id="opsExceptionPanel" class="subtab-panel admin-console-main">
<div id="opsAccountPanel" class="subtab-panel admin-console-main">
<div id="opsProviderPanel" class="subtab-panel admin-console-main">
<div id="opsExportPanel" class="subtab-panel admin-console-main">
<div id="opsMetaSyncPanel" class="subtab-panel admin-console-main">
```

For ops, use additional wrapper classes only if needed to define status strip / primary surface / secondary rail boundaries.

- [ ] **Step 4: Add CSS for collectibles and ops surfaces**

Add tab-scoped styling for:
- `.goods-shell.admin-console-shell`
- `.goods-surface`
- `#tabOps.admin-console-shell`
- ops system-status block
- ops subtabs
- `#opsCabinetPanel`
- `#opsCameraPanel`
- `#opsSlotPanel`
- ops exception list, summary, and batch-action strip
- `#opsAccountPanel`
- `#opsProviderPanel`
- `#opsExportPanel`
- `#opsMetaSyncPanel`

Preserve current subtab behavior and exception/workbench actions.

- [ ] **Step 5: Run targeted tests**

Run:
```bash
pytest -q tests/test_ops_shell_bootstrap.py -k 'collectibles_and_ops_use_console_panel_grammar or ops_console_status_and_exception_anchors_remain_present'
```
Expected: PASS.

- [ ] **Step 6: Commit the collectibles/ops shell changes**

```bash
git add app/static/index.html tests/test_ops_shell_bootstrap.py
git commit -m "style: extend console shell across collectibles and ops tabs"
```

---

### Task 6: Final Regression, Responsive QA, Accessibility QA, And QA Deployment

**Files:**
- Modify only if regressions force follow-up edits.

- [ ] **Step 1: Run the full targeted regression suite**

Run:
```bash
pytest -q tests/test_ops_shell_bootstrap.py tests/test_master_merge_workbench_ui.py
```
Expected: PASS.

- [ ] **Step 2: Verify inline script parsing**

Run:
```bash
node - <<'NODE'
const fs = require('fs');
const html = fs.readFileSync('app/static/index.html', 'utf8');
for (const m of html.matchAll(/<script>([\s\S]*?)<\/script>/g)) {
  new Function(m[1]);
}
console.log('inline script parse ok');
NODE
```
Expected: `inline script parse ok`

- [ ] **Step 3: Manual QA checklist in browser/QA**

Verify these screens visually and behaviorally:
- `대시보드` still matches the current console treatment.
- `미디어 > 등록/수집 > 마스터 정리` still matches the current console treatment and workflows.
- `운영 홈` uses the new shell but keeps operator lookup/feed behavior.
- `카메라` uses the new shell while preview selection still works.
- `미디어` search/manage/register/source modes still switch and render correctly.
- `컬렉터블` search/manage/register modes still switch and render correctly.
- `운영/연계` system status, subtabs, and exception queue still work and read as one console.

- [ ] **Step 3.1: Responsive QA matrix**

Verify at these widths:
- `1280px`
  - no horizontal clipping in `운영 홈`, `카메라`, `미디어`, `컬렉터블`, `운영/연계`
  - primary work surface remains dominant
- `1120px`
  - secondary rails stack without losing controls
  - search/context/preview panels remain reachable without overflow

- [ ] **Step 3.2: Keyboard and non-color-only state QA**

Verify with keyboard tabbing:
- visible focus on representative controls in each tab
- active/selected states remain understandable without relying only on color
- action buttons remain legible against dark surfaces

- [ ] **Step 4: QA deployment smoke**

If implementation is complete, sync to QA and verify:
```bash
rsync -a --delete --exclude '.git/' --exclude '.venv/' --exclude '.mypy_cache/' --exclude '.pytest_cache/' --exclude '__pycache__/' --exclude 'data/' --exclude 'logs/' --exclude 'test-results/' --exclude 'app/static/uploads/' --exclude 'Purchases/' --exclude '.superpowers/' --exclude '.env.local' /Volumes/Data/Works/07.__PROJECT_SLUG__/ /Users/__DEV_USER__/apps/__PROJECT_SLUG__-qa/
launchctl kickstart -k gui/$(id -u)/com.muzlife.library-qa
curl -s http://127.0.0.1:8100/health
curl -s https://__QA_DOMAIN__/health
```
Expected: both return `{\"status\":\"ok\"}`.

- [ ] **Step 5: Final commit for any regression fixes**

```bash
git status -sb
# commit only if Task 6 required follow-up edits
```

---

## Notes
- Preserve all current tab/subtab routing and selection state behavior.
- Do not widen this phase into new workflow changes for dashboard or master merge.
- Prefer adding shell/helper classes over rewriting existing DOM trees.
- Keep changes surgical: shared shell first, then tab-scoped panels, then final polish only if tests or QA require it.
