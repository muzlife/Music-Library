# Admin Density Secondary Compaction Spec

**Goal**
Continue the admin-only density tightening to keep core management forms at two rows wherever possible (1320px baseline), reduce vertical whitespace in edit/detail areas, and compact the right-side detail panel (artist image + temperature/humidity + location lines). Operator/ops UI must remain unchanged.

**Scope**
- Admin shell only (`body[data-shell-mode="admin"]`).
- Targeted areas in `관리 > 미디어 > 관리` and `관리 > 컬렉터블 > 관리` plus shared compact form helpers.
- No changes to data flow, JavaScript behavior, or server endpoints.

**Non-Goals**
- Do not alter operator/ops layouts.
- Do not hide/remove fields or introduce new field groupings beyond layout adjustments.
- Do not change text, labels, or i18n keys.

---

## Requirements

### R1. Two-Row Form Integrity (1320px)
- For admin-only compact form grids, ensure primary/secondary rows remain at two rows at 1320px width:
  - `#homeEditProductCoreRowA/B` (미디어 관리 상품 정보)
  - `#goodsManageCoreRowA/B` (컬렉터블 관리)
- If any row overflows to 3+ lines at 1320px, adjust `grid-template-columns` or `grid-column` spans minimally to restore two rows without hiding fields.

### R2. Vertical Density Tightening (Admin Only)
- Reduce admin-only vertical whitespace in edit/detail areas by minimizing margins/padding (admin override only):
  - `#homeEditMusicMetaFieldsA/B/C` blocks
  - `#homeEditTrackListWrap`
  - `#homeEditMusicSourceSummary*` block stack (main/sub/extra/ops)
  - `#homeEditorActionRow` and `#homeMasterAddActionRow`
- Keep the overall hierarchy and grouping; only tighten spacing.

### R3. Right-Side Detail Panel Compaction (Admin Only)
- In the right detail panel (artist image/context + temperature/humidity + location lines), tighten vertical spacing and keep key lines on single rows where possible:
  - Artist image size slightly reduced.
  - Temperature/Humidity and Status align on the same row.
  - Current/Previous location aligned on the same row.
- No changes to data fields or labels; only layout/spacing.

### R4. Consistent Compact Tokens
- Use existing admin compact tokens and `var(--compact-gap)` for spacing when adjusting gaps.
- Do not introduce new tokens.

### R5. Tests
- Add/extend tests in `tests/test_admin_density_compaction.py` to assert:
  - Admin-only spacing overrides for the blocks in R2.
  - Two-row structure for `#homeEditProductCoreRowA/B` and `#goodsManageCoreRowA/B` at 1320px (via existing row markers and grid templates).
  - Presence of compact gap usage on any new admin-only grid rules introduced.

---

## Acceptance Criteria
- Admin pages remain two-row for the specified compact blocks at 1320px width.
- Right detail panel is visibly denser with smaller artist image and paired lines for temperature/humidity and locations.
- Operator/ops pages unchanged.
- Tests pass:
  - `pytest tests/test_admin_density_compaction.py -v`
  - `pytest tests/test_ops_shell_bootstrap.py -v`

