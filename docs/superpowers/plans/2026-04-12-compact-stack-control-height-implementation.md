# Compact Stack Control Height Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align input/select/button heights inside admin-shell `.compact-stack-actions` to the input height baseline for consistent vertical rhythm.

**Architecture:** Add scoped CSS rules under `body[data-shell-mode="admin"] .compact-stack-actions` to apply a shared control-height token and consistent padding. Add regression tests for the scoped selector, exclusions, and `.compact-line` alignment, plus manual visual checks for key rows.

**Tech Stack:** HTML/CSS in `app/static/index.html`, Python pytest in `tests/test_admin_density_compaction.py`.

---

## File Map

**Modify:**
- `/Volumes/Works/07.hahahoho/app/static/index.html`
- `/Volumes/Works/07.hahahoho/tests/test_admin_density_compaction.py`

---

### Task 1: Add Regression Test for Scoped Control Height Rules

**Files:**
- Modify: `/Volumes/Works/07.hahahoho/tests/test_admin_density_compaction.py`

- [ ] **Step 1: Write the failing test**

```python
def test_compact_stack_actions_control_height_rules():
    html = read_static_html("index.html")
    assert "body[data-shell-mode=\"admin\"] .compact-stack-actions" in html
    assert "--compact-control-height" in html
    assert "body[data-shell-mode=\"admin\"] .compact-stack-actions input:not([type=\"checkbox\"]):not([type=\"radio\"]):not([type=\"file\"]):not([type=\"hidden\"])" in html
    assert "body[data-shell-mode=\"admin\"] .compact-stack-actions select" in html
    assert "body[data-shell-mode=\"admin\"] .compact-stack-actions button" in html
    assert "body[data-shell-mode=\"admin\"] .compact-stack-actions .btn" in html
    assert "body[data-shell-mode=\"admin\"] .compact-stack-actions .compact-line" in html
    assert ".compact-stack-actions textarea" not in html
    assert ".compact-stack-actions input[type=\"checkbox\"]" not in html
    assert ".compact-stack-actions input[type=\"radio\"]" not in html
    assert ".compact-stack-actions input[type=\"file\"]" not in html
    assert ".compact-stack-actions input[type=\"hidden\"]" not in html
```

- [ ] **Step 2: Run test to verify failure**

Run:
```bash
pytest -q tests/test_admin_density_compaction.py::test_compact_stack_actions_control_height_rules
```
Expected: FAIL

---

### Task 2: Add Scoped Control Height CSS Rules

**Files:**
- Modify: `/Volumes/Works/07.hahahoho/app/static/index.html`

- [ ] **Step 1: Add scoped token**

Add in the admin shell CSS area (near existing admin density rules):
```css
body[data-shell-mode="admin"] {
  --compact-control-height: 28px;
}
```

- [ ] **Step 2: Add scoped rules for compact-stack-actions (after admin .btn overrides)**

Place the scoped rules **after** the admin `.btn` / `.btn.tiny` overrides (so they win the cascade), or explicitly add an override for `.compact-stack-actions .btn.tiny`. Prefer placing the block after the admin overrides to keep specificity low and predictable.
```css
body[data-shell-mode="admin"] .compact-stack-actions input:not([type="checkbox"]):not([type="radio"]):not([type="file"]):not([type="hidden"]),
body[data-shell-mode="admin"] .compact-stack-actions select {
  min-height: var(--compact-control-height);
  padding: 2px 6px;
  line-height: 1.1;
}

body[data-shell-mode="admin"] .compact-stack-actions button,
body[data-shell-mode="admin"] .compact-stack-actions .btn {
  min-height: var(--compact-control-height);
  padding: 2px 8px;
  line-height: 1.1;
}

body[data-shell-mode="admin"] .compact-stack-actions .btn.tiny {
  min-height: var(--compact-control-height);
  padding: 2px 8px;
  line-height: 1.1;
}

body[data-shell-mode="admin"] .compact-stack-actions .compact-line {
  min-height: var(--compact-control-height);
  display: flex;
  align-items: center;
}
```

- [ ] **Step 3: Run test to verify pass**

Run:
```bash
pytest -q tests/test_admin_density_compaction.py::test_compact_stack_actions_control_height_rules
```
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add /Volumes/Works/07.hahahoho/app/static/index.html \
        /Volumes/Works/07.hahahoho/tests/test_admin_density_compaction.py
git commit -m "style: align compact stack action control heights"
```

---

### Task 3: Targeted Verification

- [ ] **Step 1: Run full admin density compaction suite**

```bash
pytest -q tests/test_admin_density_compaction.py
```
Expected: PASS

- [ ] **Step 2: Manual visual checks at 1080px and 760px**

Verify no clipping/overlap and height alignment for:
- Linked goods “등록 방식” row
- Product relation action rows
- Collectibles manage mapping/action rows
- One long-label/icon-button case
- One wrapped `.compact-line` case

- [ ] **Step 3: Commit any follow-up tweaks (if needed)**

```bash
git status -sb
```
If additional changes are required, commit with a small fix message.
