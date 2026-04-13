# Admin Shell Grid Layout + Menu Hierarchy

Date: 2026-04-13
Owner: Codex
Scope: Admin UI shell layout + left menu hierarchy + section description toggles

## Background
The admin UI shell is currently offset by left-nav width. The header lives inside the body wrapper, so it inherits the left margin and appears shifted. The left menu uses a fixed top offset that does not match the actual header height, which causes overlap. We also need to remove redundant menu rendering inside the main content and reduce vertical space usage with toggled section descriptions.

## Goals
- Header spans full width and never shifts with left nav.
- Left menu sits directly under the header and does not overlap it.
- Main content is isolated from menu rendering (menu only appears in the left column).
- Left menu shows a strict hierarchy (parent -> child) with accordion behavior.
- Section description text is collapsed by default via a toggle.
- Ops scope: remove left menu placeholder in Ops home and remove the bottom collectibles registration area (Ops home + Admin dashboard).

## Non-Goals
- Large structural refactors beyond the shell layout.
- Rewriting data logic for menu content or page routing.
- Visual redesign beyond spacing/structure needed for the layout fix.

## Design Summary
### 1) Admin Shell Grid
- Introduce a grid container for admin pages:
  - Row 1: header (auto height, full width)
  - Row 2: main content (fills remaining space)
- Main content row uses a 2-column grid:
  - Left: nav (fixed width)
  - Right: content (fluid)
- Header is moved outside the content wrapper, so it always uses full width and is unaffected by nav width.
- Remove header height hard-coding; allow the header to size naturally. Nav is anchored to the main row rather than using a top offset.

### 2) Left Menu Hierarchy + Accordion
- Left menu shows only parent items; children appear only when a parent is active/open.
- Clicking a parent expands its children and collapses any other open parent.
- Child items use smaller font + tighter spacing and a subtle indent.
- Menu content is rendered only in the left column; no menu elements appear in the main content area.

### 3) Section Description Toggle
- Section description text is collapsed by default.
- Title row includes a toggle button (chevron).
- Toggle state stored in session (page session only).
- Collapsed state removes the description height entirely.

### 4) Ops Scope (Minimal Change)
- Ops home: remove the left menu placeholder/slot so content can use full width.
- Ops home + Admin dashboard: remove the bottom collectibles registration block that was added unintentionally.

## Information Architecture
- Left menu categories: Dashboard, Media, Collectibles, Ops/Integration.
- “ERD Summary / ERD Detail / Manual” links move into Ops/Integration.
- Submenu labels are smaller than parent labels.

## Interaction Details
- Accordion: only one parent open at a time.
- Toggle button uses `aria-expanded` and is keyboard reachable.
- Collapsed descriptions can be expanded without reflowing other layout elements incorrectly.

## Risks / Mitigations
- Risk: Existing CSS may assume header inside body wrapper.
  - Mitigation: Update selectors to target the new header placement; keep class names stable.
- Risk: Menu state lost on navigation.
  - Mitigation: Keep state in session storage keyed by menu ID.

## Testing / Verification
- Admin page: header stays full width, menu sits below header, content aligns under header.
- Admin page: menu accordion works; only one parent open.
- Admin page: description toggles collapse/expand; default is collapsed.
- Ops home: left menu placeholder removed; layout width correct.
- Ops home + Admin dashboard: collectibles registration block removed.

## Success Criteria
- Header no longer shifts when left menu is present.
- Left menu aligns under header without overlap.
- Menu hierarchy is visible only on the left, not inside content.
- Description text does not consume vertical space by default.
- Ops home shows no left menu placeholder and no bottom collectibles registration block.

