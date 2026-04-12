# Admin Density Compaction (32px) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply a 32px compact control system across the admin management UI while preserving behavior and keeping operator/ops UI untouched.

**Architecture:** Use admin-scoped CSS tokens (`body[data-shell-mode="admin"]`) to drive uniform heights, padding, fonts, and gaps; update compact layout helpers and action bars to align with the tokens. Only adjust HTML/classes when necessary to hit two-row layouts.

**Tech Stack:** Static HTML/CSS (`app/static/index.html`), Python tests (`pytest`).

---

## Files & Ownership

**Modify**
- `app/static/index.html` (admin density tokens + compact layout rules)
- `tests/test_admin_density_compaction.py` (assert new tokens + compaction rules)

**Optional/If needed**
- `tests/test_ops_shell_bootstrap.py` (only if compact rules affect expected ops/admin shell snippets)

---

### Task 1: Update Tests For 32px Compact Tokens

**Files:**
- Modify: `tests/test_admin_density_compaction.py`

- [ ] **Step 1: Write the failing test updates**
  - Add/adjust assertions for:
    - `--compact-control-height: 32px;`
    - `--compact-control-pad: 6px 10px;`
    - `--compact-label-size: 0.72rem;`
    - `--compact-font-size: 0.82rem;`
    - `--compact-gap: 6px;`
    - `--compact-line-height: 1.25;`
  - Assert admin inputs/buttons use `var(--compact-control-height)` and admin grids use `var(--compact-gap)`.

- [ ] **Step 2: Run test to verify it fails**

  Run:
  ```bash
  pytest tests/test_admin_density_compaction.py::test_admin_density_overrides_define_compact_tokens -v
  ```
  Expected: FAIL (old token values still present).

- [ ] **Step 3: Commit test changes**

  ```bash
  git add tests/test_admin_density_compaction.py
  git commit -m "test: expect 32px admin compact tokens"
  ```

---

### Task 2: Apply 32px Compact Tokens + Admin Spacing Rules

**Files:**
- Modify: `app/static/index.html`

- [ ] **Step 1: Implement token updates in admin scope**
  - Update `body[data-shell-mode="admin"]` block to define:
    - `--compact-control-height: 32px;`
    - `--compact-control-pad: 6px 10px;`
    - `--compact-label-size: 0.72rem;`
    - `--compact-font-size: 0.82rem;`
    - `--compact-gap: 6px;`
    - `--compact-line-height: 1.25;`

- [ ] **Step 2: Align controls to tokens**
  - Update admin-scoped rules for `input/select/textarea`, `.btn`, and action rows to use:
    - `min-height: var(--compact-control-height)`
    - `padding: var(--compact-control-pad)` (or row-appropriate variants)
    - `font-size: var(--compact-font-size)`
    - `line-height: var(--compact-line-height)`

- [ ] **Step 3: Apply compact gap and padding**
  - Update admin-scoped grid/flex gaps to `var(--compact-gap)`:
    - `.grid`, `.grid-3`, `.grid-6`, `.home-edit-grid-6`, `.home-search-grid-*`
    - `.ops-compact-form-grid`, `.ops-compact-form-row`, `.compact-stack`, `.compact-stack-grid`, `.compact-stack-actions`
  - Reduce admin-only padding where safe:
    - `.card` padding and `.section-divider` spacing
    - `.ops-compact-extra-fields` padding/margins (admin-only override)

- [ ] **Step 4: Run tests**

  Run:
  ```bash
  pytest tests/test_admin_density_compaction.py::test_admin_density_overrides_define_compact_tokens -v
  ```
  Expected: PASS

- [ ] **Step 5: Commit CSS changes**

  ```bash
  git add app/static/index.html
  git commit -m "style: apply 32px admin compact tokens"
  ```

---

### Task 3: Two-Row Layout Verification + Adjustments

**Files:**
- Modify: `app/static/index.html` (if needed)
- Optional: `tests/test_admin_density_compaction.py`

- [ ] **Step 1: Verify core 2-row blocks**
  - Inspect these sections in `app/static/index.html`:
    - `quickRegisterCoreRowA/B` (미디어 > 직접 등록)
    - `goodsRegisterCoreRowA/B` (컬렉터블 등록)
    - `homeEditProductCoreRowA/B` (미디어 관리 > 수정)
  - Ensure all fields remain in **two rows** at 1320px width.

- [ ] **Step 2: If any block overflows, adjust grid templates**
  - Update `grid-template-columns` only as needed to keep logical grouping intact.
  - Record any 3-row exceptions in plan notes and add a test assertion for that exception.

- [ ] **Step 3: Optional test coverage for exceptions**

  If a 3-row exception is required, add a test in
  `tests/test_admin_density_compaction.py` that asserts the specific block uses the 3-row template.

- [ ] **Step 4: Run targeted tests**

  ```bash
  pytest tests/test_admin_density_compaction.py -v
  ```
  Expected: PASS

- [ ] **Step 5: Commit any layout adjustments**

  ```bash
  git add app/static/index.html tests/test_admin_density_compaction.py
  git commit -m "style: tighten admin compact form rows"
  ```

---

### Task 4: Full Regression Pass (Admin UI)

- [ ] **Step 1: Run core UI regression tests**

  ```bash
  pytest tests/test_admin_density_compaction.py tests/test_ops_shell_bootstrap.py -v
  ```
  Expected: PASS

- [ ] **Step 2: Commit if test-only adjustments were required**

  ```bash
  git status -sb
  # commit only if any test tweaks were needed
  ```

---

## Notes for Visual Verification
- After code changes, visually verify:
  - Admin forms show consistent 32px height controls
  - Search/clear/save buttons align with input height
  - Core sections display in two rows
  - Operator/ops read-only UI is unchanged

(If needed, use Chrome CDP to capture screenshots after enabling remote debugging.)
