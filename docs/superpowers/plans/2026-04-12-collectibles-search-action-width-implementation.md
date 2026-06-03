# Collectibles Search Action Width Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Widen the action column and search/clear buttons in the Collectibles Search secondary row while slightly reducing input minimum widths.

**Architecture:** Update the Collectibles Search secondary-row grid template and action button flex sizing in the CSS block inside `app/static/index.html`. Add a small regression test in `tests/test_admin_density_compaction.py` to assert the grid template and button sizing rules are present.

**Tech Stack:** HTML/CSS (`app/static/index.html`), Python pytest (`tests/test_admin_density_compaction.py`).

---

## File Map

**Modify:**
- `/Volumes/Data/Works/07.__PROJECT_SLUG__/app/static/index.html`
- `/Volumes/Data/Works/07.__PROJECT_SLUG__/tests/test_admin_density_compaction.py`

---

### Task 1: Add Regression Test for Collectibles Search Action Width

**Files:**
- Modify: `/Volumes/Data/Works/07.__PROJECT_SLUG__/tests/test_admin_density_compaction.py`

- [ ] **Step 1: Add a failing test**

```python
def test_collectibles_search_action_width_rules():
    html = read_static_html("index.html")
    assert (
        "grid-template-columns: repeat(6, minmax(110px, 1fr)) minmax(220px, 1.35fr);" in html
        or "grid-template-columns: repeat(6, minmax(110px, 1fr)) minmax(200px, 1.35fr);" in html
    )
    action_block = html.split(".goods-search-actions > .btn", 1)[1].split("}", 1)[0]
    assert "flex: 1;" in action_block
    assert "min-width: 110px;" in action_block
```

- [ ] **Step 2: Run the test to confirm it fails**

Run:
```bash
pytest -q tests/test_admin_density_compaction.py::test_collectibles_search_action_width_rules
```
Expected: FAIL (rule not present yet).

---

### Task 2: Update Collectibles Search Grid and Action Button Sizing

**Files:**
- Modify: `/Volumes/Data/Works/07.__PROJECT_SLUG__/app/static/index.html`

- [ ] **Step 1: Update secondary-row grid template**

In the CSS block that defines `.goods-search-compact-row--secondary`, change to:
```css
.goods-search-compact-row--secondary {
  grid-template-columns: repeat(6, minmax(110px, 1fr)) minmax(220px, 1.35fr);
}
```

- [ ] **Step 2: Check for overflow between 1080px and 1440px**

If the collectibles search card shows horizontal scroll at desktop widths,
reduce the action column minimum to 200px:
```css
.goods-search-compact-row--secondary {
  grid-template-columns: repeat(6, minmax(110px, 1fr)) minmax(200px, 1.35fr);
}
```

- [ ] **Step 3: Expand search/clear buttons in the action cluster**

Add/adjust the rule for the action buttons:
```css
.goods-search-actions > .btn,
.goods-search-actions > .icon-btn,
.goods-search-actions > .icon-symbol-btn {
  flex: 1;
  min-width: 110px;
}
```

- [ ] **Step 4: Run the test to confirm it passes**

Run:
```bash
pytest -q tests/test_admin_density_compaction.py::test_collectibles_search_action_width_rules
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add /Volumes/Data/Works/07.__PROJECT_SLUG__/app/static/index.html \
        /Volumes/Data/Works/07.__PROJECT_SLUG__/tests/test_admin_density_compaction.py
git commit -m "style: widen collectibles search actions"
```

---

### Task 3: Verification

- [ ] **Step 1: Run the full admin density compaction tests**

Run:
```bash
pytest -q tests/test_admin_density_compaction.py
```
Expected: PASS.

- [ ] **Step 2: Manual visual check**

At widths 1440px, 1080px, 760px:
- Collectibles Search secondary row shows a wider action column.
- Search/Clear buttons are equal width and larger than before.
- No horizontal scrolling in the collectibles search card.

- [ ] **Step 3: Commit any follow-up fixes**

```bash
git status -sb
```
If fixes are needed, commit them with a small follow-up message.
