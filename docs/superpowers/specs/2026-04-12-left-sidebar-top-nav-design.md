# Left Sidebar Primary Navigation Design

**Date:** 2026-04-12

## Goal
Move the top-level navigation (Dashboard / Media / Collectibles / Ops) into a left sidebar to free horizontal space in the main management area, while keeping sub-tabs in the main content and maximizing content area on narrow screens.

## Scope
- **In scope:** Top-level nav placement, layout container changes, responsive behavior for the left sidebar.
- **Out of scope:** Sub-tab UI/logic, page-specific layouts, and content density changes unrelated to navigation.

## Current State
- Top-level nav is horizontal across the header row.
- Content area shares horizontal space with header elements, reducing usable width.

## Design Summary
- Introduce a **left sidebar** for top-level navigation only.
- Keep **sub-tabs** in the main content area (right side) exactly where they are.
- Minimize the top header to retain only lightweight context/actions
  (page context label + help + notifications/user menu if present; no new header features).
- On narrow screens, the sidebar collapses to **icon-only** and then to a **hidden overlay** to maximize content space.

## Layout Structure
### Desktop (>= 1200px)
- Left sidebar width: **180–200px**
- Top-level nav items: Dashboard / Media / Collectibles / Ops
- Header row minimized (page context label + help + notifications/user menu if present)

### Medium (761–1199px)
- Sidebar becomes **icon-only**
- Width reduced to ~**56–64px** to maximize content
- Each icon retains tooltip + aria-label

### Small (<= 760px)
- Sidebar hidden by default
- Opened via a floating **menu button** (top-left) that slides in an overlay drawer
- Drawer closes on item selection

## Interaction Rules
- Only top-level nav moves; sub-tabs remain in the right content column.
- Active top-level item is highlighted in the sidebar.
- Sidebar collapse state is automatic based on breakpoints (no manual toggle).
- If the menu grows beyond available height, the sidebar scrolls (no clipping).
- Deep links still highlight the active top-level item even when the drawer is closed.

## Accessibility
- Menu button has `aria-label="Open navigation"` and visible focus.
- Drawer uses `role="dialog"` + `aria-modal="true"` and returns focus to the menu button on close.
- Icon-only mode includes `aria-label`, tooltip text, and `aria-current="page"` on the active item.
- Tooltips appear on hover and keyboard focus.
- Drawer mode traps focus and closes on `Esc` or scrim click.
- Background scroll is locked while the drawer is open.

## Acceptance Criteria
1. Top-level navigation is rendered in a left sidebar in desktop view (>=1200px).
2. Sub-tabs remain in their current positions in the main content area.
3. At 761–1199px, the sidebar collapses to icon-only (56–64px wide) with tooltips.
4. At <=760px, the sidebar is hidden by default and accessible via a menu button.
5. The content area is only reduced by the sidebar width (no additional width loss).
6. No regression to existing tab behavior and routing.

## Testing/Verification
- Visual check at 1440px, 1200px, 1199px, 1080px, 761px, 760px.
- Verify tab switching still opens correct main panels.
- Confirm sub-tabs remain unchanged.
- Keyboard navigation in icon-only + drawer modes.
