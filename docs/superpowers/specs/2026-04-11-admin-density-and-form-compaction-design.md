# Admin Density & Form Compaction Design

**Date:** 2026-04-11  
**Owner:** Codex + Admin Ops

## Goal
Increase information density across the entire admin area while preserving readability, and reflow registration/edit forms so all fields remain visible without meaningless splits. The direct registration block should fit into two rows (desktop widths) with all fields visible.

## Scope
- Admin UI only (`/admin` route, `body[data-shell-mode="admin"]`).
- Admin media search/list, manage, register, and source workbench surfaces.
- Search list “상품 수정” button: add inline up/down arrow state to indicate expanded/collapsed quick edit.
- Direct register form layout: all fields remain visible, arranged to ≤2 rows at desktop widths (>=1280px).
- Master/Item edit blocks: reduce vertical density and minimize rows while keeping all fields visible.

## Non-Goals
- No changes to data models or API behavior.
- No changes to ops home or cabinet routes.
- No new advanced/hidden field sections (all fields remain visible).

## UX Principles
1. **No meaningless splits**: keep related fields on the same row; avoid breaking a logical group across lines.
2. **Two-row direct register**: on desktop widths, all fields should fit in two rows; on narrower widths, wrapping is allowed.
3. **Consistent density**: apply a single compact token set across admin screens to avoid visual mismatch.
4. **State clarity**: quick edit button visually communicates expand/collapse with arrows.

## Layout Design

### 1) Admin Density Tokens (High)
Apply to admin-only scope via `body[data-shell-mode="admin"][data-admin-density="high"]`:
- Input height: 26–28px
- Input padding: 2px 6px
- Label font-size: 0.68–0.70rem
- Grid gap: 4px (down from 6px)
- Section/card vertical padding: reduce by ~25%
- Button height: 32–34px (tiny: 26–28px)

### 2) Direct Register Form (2-row layout)
Adopt a 12-column grid for the direct registration form at desktop widths.

**Row 1 (12 columns total):**
- 포맷 (2)
- 수량 (1)
- 아티스트명 (3)
- 상품명 (4)
- 보관 슬롯 (2)

**Row 2 (12 columns total):**
- 레이블 (2)
- 발매일 (2)
- 커버 이미지 URL (2)
- 메모 (2)
- 도메인 (2)
- 구매 가격 (1)
- 통화 (1)

Notes:
- All fields remain visible.
- Narrow widths may wrap to 3+ rows.

### 3) Master / Item Edit Blocks
Keep all fields visible, but reduce row count and spacing:
- Convert key sections to 12-column grid where feasible.
- Group related fields (status/signature, price/currency, domain/size) on the same row.
- Reduce spacing between section dividers and form groups using admin density tokens.

### 4) Search List “상품 수정” Button
Add an arrow marker inside the button:
- Collapsed: `▼`
- Expanded: `▲`
- Use `aria-expanded` to reflect state.

## Interaction Notes
- Quick edit toggle behavior unchanged; only visual indicator added.
- Density changes are visual only, no validation behavior changes.

## Success Criteria
- Admin area feels ~20–30% denser without harming readability.
- Direct register form shows all fields within 2 rows at desktop widths.
- All admin screens use the same density tokens and do not feel mismatched.
- “상품 수정” button clearly indicates expanded/collapsed state.

## Risks & Mitigations
- **Risk:** Visual crowding on narrow widths.  
  **Mitigation:** Allow natural wrap on smaller breakpoints; avoid forcing two rows outside desktop widths.
- **Risk:** Uneven density if some sections miss admin scope.  
  **Mitigation:** Apply tokens at admin root and verify key panels visually.
