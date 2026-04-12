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
- Minimize the top header to retain only lightweight context/actions.
- On narrow screens, the sidebar collapses to **icon-only** and then to a **hidden overlay** to maximize content space.

## Layout Structure
### Desktop (>= 1200px)
- Left sidebar width: **180–200px**
- Top-level nav items: Dashboard / Media / Collectibles / Ops
- Header row minimized (context label + utility actions only)

### Medium (<= 1080px)
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

## Accessibility
- Icon-only mode includes `aria-label` and tooltip text.
- Drawer mode traps focus and closes on `Esc`.

## Acceptance Criteria
1. Top-level navigation is rendered in a left sidebar in desktop view.
2. Sub-tabs remain in their current positions in the main content area.
3. At <=1080px, the sidebar collapses to icon-only without reducing content width.
4. At <=760px, the sidebar is hidden by default and accessible via a menu button.
5. No regression to existing tab behavior and routing.

## Testing/Verification
- Visual check at 1440px, 1080px, 760px.
- Verify tab switching still opens correct main panels.
- Confirm sub-tabs remain unchanged.
- Keyboard navigation in icon-only + drawer modes.
