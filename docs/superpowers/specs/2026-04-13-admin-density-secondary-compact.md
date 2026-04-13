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

### R3. Admin Search Context Panel Compaction (Admin Only)
- Target the admin media search context panel only:
  - `#adminSearchContextPanel` / `#adminSearchContextBody`
  - Nested context elements rendered by `renderMediaSearchContextSelection`:
    - `.ops-library-context-head`, `.ops-library-context-head-actions`
    - `.operator-mini-list` (current location line)
    - `.ops-artist-context-card`, `.ops-artist-context-media`, `.ops-artist-context-image`
- Tighten vertical spacing without changing behavior or forcing nowrap:
  - Reduce `#adminSearchContextBody` internal `gap`/`padding` (admin-only override).
  - Reduce `.ops-library-context-head` / `.ops-library-context-head-actions` gap (admin-only override); keep existing `flex-wrap` behavior.
  - Reduce artist image footprint **only inside the admin search context panel** (e.g., 104px → 88px) and update the matching grid template columns for `.ops-artist-context-card.has-image` in admin scope.
- Optional (only if needed to eliminate excessive vertical whitespace): reduce outer margin/gap on `.ops-library-mini-map` and `.ops-library-slot-preview` **without** changing their internal layout.
- No changes to data fields, labels, or behavior; only layout/spacing in admin search context.

### R4. Consistent Compact Tokens
- Use existing admin compact tokens defined under `body[data-shell-mode="admin"]`:\n  `--compact-control-height`, `--compact-control-pad`, `--compact-font-size`, `--compact-line-height`, `--compact-gap`.\n- Use `var(--compact-gap)` (or the nearest existing compact token) for new admin-only spacing overrides.
- Do not introduce new tokens.

### R5. Tests + Manual Check
- Add/extend tests in `tests/test_admin_density_compaction.py` to assert:
  - Admin-only spacing overrides for the blocks in R2.
  - Two-row structure for `#homeEditProductCoreRowA/B` and `#goodsManageCoreRowA/B` at 1320px (via existing row markers and grid templates).
  - Presence of compact gap usage on any new admin-only grid rules introduced.
  - Admin search context panel compaction rules exist under `body[data-shell-mode="admin"]` (e.g., `#adminSearchContextBody` spacing override and artist image size override in admin scope).
- Manual verification (visual): at **1320px width**, confirm the two-row blocks stay at two rows and the admin search context panel is visibly tighter while preserving wrapping behavior.

---

## Acceptance Criteria
- Admin pages remain two-row for the specified compact blocks at **1320px width** (manual visual check completed).
- Admin search context panel is visibly denser with a smaller artist image and tighter spacing in header/actions and location line, without changing content or behavior.
- Operator/ops pages unchanged.
- Tests pass:
  - `pytest tests/test_admin_density_compaction.py -v`
  - `pytest tests/test_ops_shell_bootstrap.py -v`
