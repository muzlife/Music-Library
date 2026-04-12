# Collectibles Search Action Width Design

**Date:** 2026-04-12

## Goal
Improve usability in the Collectibles Search screen by reducing input widths slightly and widening the search/clear action buttons so they are more prominent and easier to click.

## Scope
- **In scope:** Collectibles Search (검색) filter rows, specifically the secondary row action cluster that contains the Search and Clear buttons.
- **Out of scope:** Other tabs, other search forms, and non-collectibles screens.

## Current State
- The secondary row uses a 6-field grid plus an auto-sized action cluster.
- Search/Clear buttons appear narrow compared to the field columns.

## Design Summary
- Shrink the minimum width of the 6 secondary-row fields slightly.
- Expand the action column and make its two buttons the same width.
- Preserve existing responsive stacking for 1080px/760px breakpoints.

## Proposed Layout Changes
### Grid ratio (secondary row)
Update the secondary-row grid columns to allocate more space to actions:
- From: `repeat(6, minmax(120px, 1fr)) auto`
- To: `repeat(6, minmax(110px, 1fr)) minmax(220px, 1.35fr)`

**Implementation detail:** Update the desktop rule for
` .goods-search-compact-row--secondary `
in `/Volumes/Works/07.hahahoho/app/static/index.html` (CSS section).

### Action buttons (search/clear)
Inside `.goods-search-actions`:
- Keep the container as a flex row.
- Make both buttons equal width with a minimum width for legibility.

Proposed CSS (scoped to collectibles search rules):
```css
.goods-search-actions > .btn,
.goods-search-actions > .icon-btn,
.goods-search-actions > .icon-symbol-btn {
  flex: 1;
  min-width: 110px;
}
```

## Responsive Behavior
- At 1080px and 760px breakpoints, existing stacking rules remain unchanged.
- The action cluster should stack naturally with the row when the grid collapses.
- Between desktop and 1080px, there should be no horizontal scroll in the
  collectibles search card. If overflow appears, reduce the action column
  minimum to 200px before changing breakpoints.

## Acceptance Criteria
1. In desktop grid layout (>= 1080px), the action column minimum width is 220px.
   If overflow occurs between 1080px and 1440px, the minimum may be reduced to 200px.
2. Search and Clear buttons are equal width and each has at least 110px width.
3. No overlap or layout break at 1440px, 1080px, and 760px widths.
4. No horizontal scrolling in the collectibles search card between desktop and 1080px.
5. No changes outside Collectibles Search.

## Testing/Verification
- Visual check at 1440px, 1080px, and 760px widths in Collectibles Search.
- Confirm no regression in other sections of the collectibles screen.
