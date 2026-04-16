# Compact Shell Header & Menu (Admin + Ops)

**Date:** 2026-04-14  
**Owner:** Codex + Admin Ops

## Goal
Reduce header + menu vertical footprint by ~30–40% across **both admin and ops** while preserving the icon+text navigation style and keeping only essential controls visible in the header.

## Scope
- Admin (`/admin`) and Ops (`/ops`) shells.
- Header + top navigation + utility controls.
- No layout reflow inside main content cards in this phase (those come in later steps).

## Non-Goals
- No changes to content/section density inside pages (handled in later phases).
- No changes to navigation structure or routes.
- No changes to business logic, data loading, or API behavior.

## Decisions (Locked)
- **Compaction strength:** 30–40% vertical reduction.
- **Header content:** keep **Language**, **Ops/Admin mode toggle**, **User/Logout** only.
- **Nav style:** **icon + text** (smaller font and tighter padding).
- **Consistency:** same compact scale applied to both Admin and Ops.

## Approach Options (Reviewed)
1. **Token-based compact shell (recommended)**
   - Introduce compact sizing tokens for shell header + tabs + utility elements.
   - Apply the same compact scale to both Admin and Ops.
2. Component split
   - Separate compact components and recompose header/menus per screen.
3. Page-by-page manual tuning
   - Quick but inconsistent, not maintainable.

**Chosen:** Option 1 (token-based compact shell)

## Layout / Visual Design
### 1) Header Height
- Reduce hero/header padding by ~30–40%.
- Tighten hero typography (kicker + title + subtitle) and row spacing.
- Keep the header visually minimal while retaining existing theme.

### 2) Navigation Buttons
- Reduce tab height and padding while keeping icon+text.
- All shell tabs (admin & ops) use the same min-height and font size.

### 3) Utility Controls
- Keep language selector and auth controls in header.
- Remove/move any other header chips or doc-link controls out of the header.

## Size Tokens (Target Range)
Applied to both admin/ops shells:
- **Header padding (y):** -30–40%
- **Tab height:** 26–30px
- **Tab padding:** ~4–6px vertical, 8–10px horizontal
- **Tab font size:** 0.74–0.78rem
- **Utility chip height:** 24–28px
- **Utility chip font size:** 0.70–0.76rem

(Exact values set during implementation after quick visual check.)

## Interaction Rules
- All existing navigation behavior remains unchanged.
- Visual density only; no logic changes.

## Success Criteria
- Header height visibly reduced by ~30–40% on both admin and ops.
- Only Language + Ops/Admin + User/Logout remain in header.
- Icon+text tabs remain readable and consistent between admin/ops.
- No layout collisions or wrapping regressions in common widths (>=1280px).

## Risks & Mitigations
- **Risk:** Excessive wrapping on smaller widths.  
  **Mitigation:** Allow wrap; avoid hard min-widths.
- **Risk:** Inconsistent density across shells.  
  **Mitigation:** Shared compact tokens applied globally.

