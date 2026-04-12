# Admin Density Compaction (32px) Across Management UI

Date: 2026-04-13

## Summary
Apply a **32px compact control system** across the entire **management (admin) UI** so operators can view and edit more information per screen without losing clarity. This is **admin-only**, scoped to `body[data-shell-mode="admin"]`, and keeps behavior unchanged. The emphasis is on **consistent control height, tighter spacing, and two-row layouts** for dense forms where possible.

## Scope
- **In scope**: Management/admin UI for Media, Collectibles, Ops/Integration, and dashboard management panels.
- **Out of scope**: Operator/ops read-only screens, backend services, data models, routing behavior.

## Goals
1. Use **32px** as the default height for inputs, selects, and buttons in admin screens.
2. Reduce vertical slack via smaller gaps, consistent padding, and compact labels.
3. Keep each core registration/edit block **within 2 rows** when feasible without removing fields.
4. Preserve existing behavior, validation, and field semantics.
5. Keep **visual alignment**: labels and controls align; action buttons match input height.

## Non-Goals
- No change to operations (ops) or operator UI density.
- No new features or backend changes.
- No removal of fields.

## Design Tokens (Admin-only)
Apply to `body[data-shell-mode="admin"]`:
- `--compact-control-height: 32px`
- `--compact-control-pad: 6px 10px`
- `--compact-label-size: 0.72rem`
- `--compact-gap: 6px`
- `--compact-line-height: 1.25`

## Layout Rules
1. **Control height and padding**
   - `input/select/button/.btn` use `min-height: var(--compact-control-height)` and compact padding.
   - `line-height` and font-size scale to keep labels legible.

2. **Unified row height**
   - Input rows, chip rows, and action toolbars are vertically aligned.
   - Any button adjacent to an input matches the input height.

3. **Two-row rule (where feasible)**
   - Core registration/edit blocks should fit into **2 rows** without hiding or removing fields.
   - Fields are grouped by logical affinity (identity, classification, source/metadata) to avoid meaningless splits.

4. **Gaps and margins**
   - Use `gap: var(--compact-gap)` across grid and flex rows.
   - Reduce card padding/margins only in admin mode.

5. **Action bar alignment**
   - Search/clear/submit buttons become **same height as inputs**.
   - Buttons expand in width only when needed for visibility; input widths stay readable.

## Target Areas (Priority Order)
1. **Media > Register / Edit panels**
2. **Media > Manage (inline edit blocks)**
3. **Collectibles register/manage panels**
4. **Ops/Integration forms (admin-only)**

## Accessibility
- Preserve label associations (`for` + `id`).
- Ensure `min-height: 32px` still provides acceptable target size; focus rings unchanged.
- Maintain keyboard tab order; no hidden focusable elements.

## Implementation Notes
- Prefer **CSS-only compaction** with admin scope to minimize HTML changes.
- Use `grid-12` or existing grid utilities to compress into two rows without breaking semantics.
- Where two-row layout is not feasible, do **not** drop fields; instead reduce padding and gaps further.
- Keep tests aligned with new class names and tokens.

## Acceptance Criteria
- Admin screens show **consistent 32px controls** across inputs/selects/buttons.
- Core registration/edit sections fit into **2 rows** when feasible without removing fields.
- Buttons adjacent to inputs **match height** and align cleanly.
- No change to ops/operator UI.
- Existing behavior and routing unchanged.

## Test Plan
- Run existing UI structure tests (admin density, ops shell bootstrap).
- Spot-check Media Register, Media Manage, Collectibles, Ops/Integration forms for alignment.
