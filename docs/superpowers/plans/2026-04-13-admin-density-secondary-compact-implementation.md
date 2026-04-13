# Admin Density Secondary Compaction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tighten admin-only density for media/collectibles manage surfaces and the admin search context panel while preserving two-row layouts at 1320px and keeping ops/operator UI unchanged.

**Architecture:** Use admin-scoped CSS overrides under `body[data-shell-mode="admin"]` to reduce margins/padding/gaps and shrink the admin search context artist card. Remove inline `margin-top` attributes on targeted admin blocks where needed so admin-only CSS can govern spacing. Add tests that assert the presence of these admin-only rules and required two-row structure markers.

**Tech Stack:** Static HTML/CSS in `app/static/index.html`, pytest string-based HTML/CSS assertions in `tests/test_admin_density_compaction.py`.

---

## Files & Ownership

**Modify**
- `app/static/index.html`
- `tests/test_admin_density_compaction.py`

---

### Task 1: Add Admin Secondary Density Tests (TDD)

**Files:**
- Modify: `tests/test_admin_density_compaction.py`

- [ ] **Step 1: Write failing test for admin secondary compaction rules**

Add a new test near other admin density checks (example name: `test_admin_secondary_compaction_rules_present`) with assertions like:

```python

def test_admin_secondary_compaction_rules_present():
    html = read_static_html("index.html")
    admin_block = html.split('body[data-shell-mode="admin"] {', 1)[1].split("}", 1)[0]
    assert "--compact-gap:" in admin_block

    for selector in [
        'body[data-shell-mode="admin"] #homeEditMusicMetaFieldsB',
        'body[data-shell-mode="admin"] #homeEditMusicMetaFieldsC',
        'body[data-shell-mode="admin"] #homeEditTrackListWrap',
        'body[data-shell-mode="admin"] #homeEditorStandaloneMount',
        'body[data-shell-mode="admin"] #homeEditorActionRow',
        'body[data-shell-mode="admin"] #homeMasterAddActionRow',
    ]:
        block = html.split(f'{selector} {{', 1)[1].split("}", 1)[0]
        assert "margin-top:" in block

    source_block = html.split('body[data-shell-mode="admin"] .source-meta-summary {', 1)[1].split("}", 1)[0]
    assert "margin-bottom:" in source_block
    assert "padding:" in source_block

    context_body_block = html.split('body[data-shell-mode="admin"] #adminSearchContextBody {', 1)[1].split("}", 1)[0]
    assert "padding:" in context_body_block
    assert "gap:" in context_body_block

    plugin_block = html.split('body[data-shell-mode="admin"] #adminSearchContextBody .ops-plugin-section {', 1)[1].split("}", 1)[0]
    assert "padding:" in plugin_block
    assert "gap:" in plugin_block

    plugin_cards_block = html.split('body[data-shell-mode="admin"] #adminSearchContextBody .ops-plugin-section-cards {', 1)[1].split("}", 1)[0]
    assert "gap:" in plugin_cards_block

    artist_card_block = html.split('body[data-shell-mode="admin"] #adminSearchContextBody .ops-artist-context-card {', 1)[1].split("}", 1)[0]
    assert "padding:" in artist_card_block
    assert "gap:" in artist_card_block

    artist_grid_block = html.split('body[data-shell-mode="admin"] #adminSearchContextBody .ops-artist-context-card.has-image {', 1)[1].split("}", 1)[0]
    assert "grid-template-columns:" in artist_grid_block

    artist_media_block = html.split('body[data-shell-mode="admin"] #adminSearchContextBody .ops-artist-context-media {', 1)[1].split("}", 1)[0]
    assert "width:" in artist_media_block
```

- [ ] **Step 2: Run the new test to verify it fails**

Run:
```bash
pytest tests/test_admin_density_compaction.py::test_admin_secondary_compaction_rules_present -v
```
Expected: FAIL (admin-only rules not yet defined).

- [ ] **Step 3: Commit failing test**

```bash
git add tests/test_admin_density_compaction.py
git commit -m "test: add admin secondary density rules"
```

---

### Task 2: Implement Admin-Only Spacing + Search Context Compaction

**Files:**
- Modify: `app/static/index.html`

- [ ] **Step 1: Remove inline margin-top styles on targeted admin blocks**

Remove inline `style="margin-top:..."` from:
- `#homeEditMusicMetaFieldsB`
- `#homeEditMusicMetaFieldsC`
- `#homeEditTrackListWrap`
- `#homeEditorStandaloneMount`
- `#homeEditorActionRow`
- `#homeMasterAddActionRow`

- [ ] **Step 2: Add admin-only spacing overrides**

Under the existing admin compact CSS block (near other `body[data-shell-mode="admin"]` rules), add:

```css
body[data-shell-mode="admin"] #homeEditMusicMetaFieldsB,
body[data-shell-mode="admin"] #homeEditMusicMetaFieldsC,
body[data-shell-mode="admin"] #homeEditTrackListWrap,
body[data-shell-mode="admin"] #homeEditorStandaloneMount,
body[data-shell-mode="admin"] #homeEditorActionRow,
body[data-shell-mode="admin"] #homeMasterAddActionRow {
  margin-top: var(--compact-gap);
}

body[data-shell-mode="admin"] .source-meta-summary {
  margin-bottom: var(--compact-gap);
  padding: 6px 8px;
}

body[data-shell-mode="admin"] .source-meta-summary-head {
  margin-bottom: 3px;
  gap: 6px;
}

body[data-shell-mode="admin"] .source-meta-summary .compact-line {
  margin-top: 3px;
  gap: 4px 6px;
}
```

- [ ] **Step 3: Add admin-only search context compaction rules**

```css
body[data-shell-mode="admin"] #adminSearchContextBody {
  padding: 10px;
  gap: var(--compact-gap);
}

body[data-shell-mode="admin"] #adminSearchContextBody .ops-library-context-head {
  gap: 6px;
}

body[data-shell-mode="admin"] #adminSearchContextBody .ops-library-context-head-actions {
  gap: 4px;
}

body[data-shell-mode="admin"] #adminSearchContextBody .ops-plugin-section {
  padding: 8px;
  gap: 6px;
}

body[data-shell-mode="admin"] #adminSearchContextBody .ops-plugin-section-cards {
  gap: 6px;
}

body[data-shell-mode="admin"] #adminSearchContextBody .ops-artist-context-card {
  padding: 8px;
  gap: 6px;
}

body[data-shell-mode="admin"] #adminSearchContextBody .ops-artist-context-card.has-image {
  grid-template-columns: 88px minmax(0, 1fr);
}

body[data-shell-mode="admin"] #adminSearchContextBody .ops-artist-context-media {
  width: 88px;
}
```

- [ ] **Step 4: Run tests to confirm pass**

Run:
```bash
pytest tests/test_admin_density_compaction.py::test_admin_secondary_compaction_rules_present -v
```
Expected: PASS

- [ ] **Step 5: Commit CSS changes**

```bash
git add app/static/index.html
git commit -m "style: tighten admin secondary density"
```

---

### Task 3: Manual Visual Verification (1320px)

- [ ] **Step 1: Set viewport to 1320px and verify**
  - `#homeEditProductCoreRowA/B` and `#goodsManageCoreRowA/B` remain two rows.
  - Admin search context panel shows smaller artist image and tighter spacing, without removing content.

- [ ] **Step 2: Document any exceptions**
  - If any block still wraps, adjust `grid-template-columns` minimally and record the exception in the spec’s Acceptance Criteria or notes.

---

### Task 4: Full Regression

- [ ] **Step 1: Run regression tests**

```bash
pytest tests/test_admin_density_compaction.py tests/test_ops_shell_bootstrap.py -v
```
Expected: PASS

- [ ] **Step 2: Commit if test-only adjustments were required**

```bash
git status -sb
# commit only if required
```

---

## Notes
- Keep ops/operator UI untouched by scoping all CSS to `body[data-shell-mode="admin"]`.
- Avoid `!important`; remove inline margins instead.
- Manual 1320px verification is required for final sign-off.
