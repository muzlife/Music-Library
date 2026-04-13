# Admin Header/Menu Split & Compact Left Nav (Management Only)

Date: 2026-04-13

## Summary
Separate the header from the management body so that **navigation lives below the header**, with a **compact left nav card** and a **pure content column**. Reduce header height, tighten menu spacing and typography, and enforce **single-open accordion behavior**. Replace body section description copy with a **help icon tooltip** to reclaim vertical space.

## Scope
- **In scope**: Admin/management shell screens (Dashboard, Media, Collectibles, Ops/Integration).
- **Out of scope**: Operator/ops shell, backend/auth, data models.

## Goals
1. Maximize vertical space for management content.
2. Keep navigation entirely in the left sidebar below the header.
3. Compact menu density (spacing, font size, width) without losing clarity.
4. Accordion behavior: one section open at a time; opening a section closes others.
5. Replace section intro copy with tooltip-only help.

## Non-Goals
- No change to operator/ops UI.
- No routing/auth changes.
- No new content or features beyond layout/visual adjustments.

## Layout & Structure
- **Header**: Top row only, reduced height (~48–56px). Contains: title, language, utility buttons (login/meta/ops/camera/logout) only.
- **Below header**: Two-column layout.
  - **Left column**: Compact nav card.
  - **Right column**: Management content only (no inline tabs/chips).
- **Menu spacing**: Reduce vertical gaps between items and groups (~25–35%).
- **Menu width**: Narrower card width (~190–210px) while keeping labels readable.

## Navigation Card (Left)
- **Card wrapper** remains, but with tighter padding.
- **Top-level items**: Slightly smaller font size than current.
- **Sub-items**: One step smaller than top-level.
- **Active state**: Applied only in left nav.
- **Accordion behavior**:
  - Clicking a top-level section closes other sections.
  - One section always open.
  - If no child active in the newly opened section, auto-select the first child.

## Body Section Description Handling
Replace the inline copy block such as:

"미디어\n검색, 관리, 등록/수집, 소스 보강을 한 흐름으로 묶습니다."

with:
- A **help icon** next to the section title.
- Tooltip shows the full copy on hover/focus.
- No persistent inline text, reclaiming vertical space.

## Accessibility
- Accordion buttons use `aria-expanded` + `aria-controls`.
- Active items use `aria-current`.
- Tooltip is keyboard accessible (focus/escape).
- Hidden body menus are `display: none` and `aria-hidden`.

## Responsive
- On narrow widths: nav collapses into drawer, but still maintains single-open accordion logic.
- Content column remains the primary vertical space; nav never overlays header.

## Acceptance Criteria
- Header height reduced and visually separated from nav/body.
- Left nav card appears **below header**, narrower and tighter than before.
- Sub-menu font size smaller than top-level.
- Clicking a top-level menu collapses others.
- Inline section description is removed and available only via tooltip.
- Body shows management content only; no in-body menus.
- Operator/ops shell unchanged.
