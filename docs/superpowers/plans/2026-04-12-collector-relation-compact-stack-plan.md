# Collector/Relation Compact Stack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure collector/relation sections in admin manage view into compact two-column layouts with tighter spacing while keeping all fields visible.

**Architecture:** Update `app/static/index.html` to apply new grid classes and spacing rules to the collector/relation blocks. Use small CSS helpers to group actions and align inputs without changing data flow or behavior. Add regression tests that assert layout class changes and compact rules in the HTML template.

**Tech Stack:** HTML/CSS/JS in `app/static/index.html`, Python pytest for HTML string assertions.

---

## File Map

**Modify:**
- `/Volumes/Works/07.hahahoho/app/static/index.html`
- `/Volumes/Works/07.hahahoho/tests/test_admin_density_compaction.py`

---

### Task 1: Add Compact Stack CSS Helpers + Tests

**Files:**
- Modify: `/Volumes/Works/07.hahahoho/app/static/index.html`
- Modify: `/Volumes/Works/07.hahahoho/tests/test_admin_density_compaction.py`

- [ ] **Step 1: Write failing test for compact stack helper rules**

```python
def test_collector_relation_compact_stack_helpers():
    html = read_static_html("index.html")
    block_1080 = html.split("@media (max-width: 1080px)", 1)[1].split("@media", 1)[0]
    assert ".compact-stack" in html
    assert ".compact-stack-actions" in html
    assert ".compact-stack-grid" in html
    assert ".compact-stack { grid-template-columns: 1fr; }" in block_1080
```

- [ ] **Step 2: Run test to verify failure**

Run:
```bash
pytest -q tests/test_admin_density_compaction.py::test_collector_relation_compact_stack_helpers
```
Expected: FAIL

- [ ] **Step 3: Add CSS helpers**

Add minimal CSS (near existing admin layout helpers):
- `.compact-stack { display: grid; grid-template-columns: minmax(0, 1fr) minmax(220px, 0.6fr); gap: 8px; align-items: center; }`
- `.compact-stack-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; }`
- `.compact-stack-actions { display: flex; gap: 6px; justify-content: flex-end; align-items: center; flex-wrap: wrap; }`
- `.compact-stack-note { margin-top: 4px; }`
- At `@media (max-width: 1080px)`, reduce to single column: `.compact-stack { grid-template-columns: 1fr; }`

Keep spacing aligned with recent admin density tokens (no font-size changes).

- [ ] **Step 4: Run test to verify pass**

Run:
```bash
pytest -q tests/test_admin_density_compaction.py::test_collector_relation_compact_stack_helpers
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add /Volumes/Works/07.hahahoho/app/static/index.html \
        /Volumes/Works/07.hahahoho/tests/test_admin_density_compaction.py
git commit -m "style: add compact stack helpers"
```

---

### Task 2: Apply Compact Stack to Collector Relation Blocks

**Files:**
- Modify: `/Volumes/Works/07.hahahoho/app/static/index.html`
- Modify: `/Volumes/Works/07.hahahoho/tests/test_admin_density_compaction.py`

- [ ] **Step 1: Add failing test for collector relation layout**

```python
def test_collector_relation_blocks_use_compact_stack():
    html = read_static_html("index.html")
    goods_section = html.split('id="homeMasterGoodsSection"', 1)[1].split('id="homeLinkedGoodsPanel"', 1)[0]
    linked_section = html.split('id="homeLinkedGoodsPanel"', 1)[1].split('id="homeManageMasterSection"', 1)[0]
    assert "compact-stack" in goods_section
    assert "compact-stack-actions" in goods_section
    assert "compact-stack" in linked_section
    assert "compact-stack-actions" in linked_section
```

- [ ] **Step 2: Run test to verify failure**

Run:
```bash
pytest -q tests/test_admin_density_compaction.py::test_collector_relation_blocks_use_compact_stack
```
Expected: FAIL

- [ ] **Step 3: Update collector relation markup**

Wrap collector relation + master-linked collector relation blocks with:
- Outer container: `class="compact-stack"`
- Left column: title/description + inputs grouped in `class="compact-stack-grid"`
- Right column: action buttons and short helper fields (e.g., “등록 방식”) grouped in `class="compact-stack-actions"`

Keep all inputs and text visible; do not remove fields.

- [ ] **Step 4: Run test to verify pass**

Run:
```bash
pytest -q tests/test_admin_density_compaction.py::test_collector_relation_blocks_use_compact_stack
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add /Volumes/Works/07.hahahoho/app/static/index.html \
        /Volumes/Works/07.hahahoho/tests/test_admin_density_compaction.py
git commit -m "ui: compact collector relation blocks"
```

---

### Task 3: Apply Compact Stack to Product Relationship Blocks

**Files:**
- Modify: `/Volumes/Works/07.hahahoho/app/static/index.html`
- Modify: `/Volumes/Works/07.hahahoho/tests/test_admin_density_compaction.py`

- [ ] **Step 1: Add failing test for product relation layout**

```python
def test_product_relation_blocks_use_compact_stack():
    html = read_static_html("index.html")
    section = html.split("homeProductRelationSection", 1)[1].split("homeEditorActionBlock", 1)[0]
    assert section.count("goods-map-section compact-stack") >= 4
    assert 'id="homeProductRelationMasterList"' in section
    assert 'id="homeProductRelationSeriesList"' in section
    assert 'id="homeProductRelationReleaseList"' in section
    assert 'id="homeProductRelationComponentList"' in section
    assert 'id="homeProductRelationSaveBtn"' in section
    assert 'id="homeProductRelationStatus"' in section
    assert "compact-stack-grid" in section
    assert "compact-stack-actions" in section
```

- [ ] **Step 2: Run test to verify failure**

Run:
```bash
pytest -q tests/test_admin_density_compaction.py::test_product_relation_blocks_use_compact_stack
```
Expected: FAIL

- [ ] **Step 3: Update product relation markup**

Apply compact stack layout to:
- 마스터 하위
- 시리즈 소속
- 박스세트 / 연관 발매
- 박스 구성품
- Save/status rows within product relationship section

Group inputs into `compact-stack-grid`, place action buttons into `compact-stack-actions`.

- [ ] **Step 4: Run test to verify pass**

Run:
```bash
pytest -q tests/test_admin_density_compaction.py::test_product_relation_blocks_use_compact_stack
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add /Volumes/Works/07.hahahoho/app/static/index.html \
        /Volumes/Works/07.hahahoho/tests/test_admin_density_compaction.py
git commit -m "ui: compact product relation blocks"
```

---

### Task 4: Full Targeted Verification

- [ ] **Step 1: Run full compact stack test suite**

Run:
```bash
pytest -q tests/test_admin_density_compaction.py
```
Expected: PASS

- [ ] **Step 2: Visual check at 1080px and 760px**

Confirm:
- No overlap/overflow in collector and product relation blocks
- Action buttons remain aligned with relevant inputs
- Empty whitespace visibly reduced

- [ ] **Step 3: Manual smoke check (no functional regression)**  
Click the following buttons to confirm behavior unchanged:\n
  - Collector relation: “컬렉터블 탭에서 연계 컬렉터블 등록”\n
  - Product relation: “조회”, “시리즈 생성”, “상품 관계 저장”
  - Confirm inputs are editable: series query, release query, relation note

- [ ] **Step 4: Commit any final tweaks**

```bash
git status -sb
```
If clean, no commit needed; otherwise commit with a small fix message.
