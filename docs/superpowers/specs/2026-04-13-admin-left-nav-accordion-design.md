# Admin Left Nav Accordion & Body Menu Removal (Management Only)

Date: 2026-04-13

## Summary
Rebuild the **management UI navigation** so that all menus live exclusively in the left sidebar with a hierarchical accordion. The **body should show only management information** (panels and content) without any menu chips/tabs. The **operations UI remains unchanged**. The navigation must always keep one top-level section open, and opening a section auto-selects its first subtab. ERD/Manual links are moved into the Ops main panel body.

## Scope
- **In scope**: Admin/management shell screens (the admin UI that includes Dashboard, Media, Collectibles, Ops/Integration).
- **Out of scope**: Operator/ops UI screens (read-only ops home and operator views), backend routes, data model changes.

## Goals
1. Maximize vertical space for management content by removing body menus.
2. Single-source navigation from the left sidebar with clear hierarchy.
3. Keep existing content and state logic stable (no behavior regressions).
4. Move ERD/Manual links to the Ops content area (not the nav).

## Non-Goals
- No redesign of ops UI or operator pages.
- No backend/auth/data changes.
- No new routing system.

## Information Architecture
Left sidebar top-level (accordion, one open at a time):
- Dashboard
- Media
- Collectibles
- Ops/Integration

Subtabs (default is first item):
- **Media**: Search / Manage / Register·Collect / Source Enhance
- **Collectibles**: Search / Manage / Register
- **Ops/Integration**: System Status / Cabinet / Slot / Camera / Exception Queue / Accounts / Providers / Export / Meta Sync
- **Dashboard**: Leaf item (single implicit subtab “Overview”).

Behavior rules:
- Clicking a top-level section **opens it** and **auto-selects its first subtab**.
- Only **one** top-level section expanded at a time.
- A top-level section is **never fully closed** (one always open).
- Active state is shown **only in the left sidebar** (top + sub item).
- Body shows **no menu elements** (tabs/chips/subtabs) – content only.
- Initial load respects existing state with precedence: **deep link/route** > **saved state** > **default first subtab**. Auto-select first subtab only when the user switches to a different top-level section that has no active child yet.

## Layout & Visual Behavior
- Left sidebar is a fixed column; body uses remaining width.
- Body retains panels, headings, help blocks, warnings, etc.
- Menu elements in body are **hidden, not removed** (DOM retained for state logic).
- Ops main panel shows an **ERD/Manual links block** at the top.

## Accessibility
- Sidebar items are keyboard focusable.
- Active items use both color and weight.
- `aria-current` is set on active items.
- Accordion uses `aria-expanded` + `aria-controls` on top-level buttons; hidden submenus are not focusable.
- Body menus hidden from layout **and** assistive tech (`display: none` / `aria-hidden`), so they do not duplicate navigation semantics.
- Keyboard: `Tab` moves through visible top-level items and their visible children. `Enter`/`Space` on a top-level item opens it (and selects its default child if needed). `Enter`/`Space` on a child activates that subtab.

## Error/Edge Handling
- “admin access required” warnings remain as normal body content.
- Hiding body menus must not collapse spacing or break scrolling.
- Preserve current admin UI state on navigation: active top/subtab, current filters, selections, and unsaved edits. Scroll behavior should follow the **current implementation** (no new scroll-reset logic introduced).

## Implementation Notes
- Prefer reusing existing state logic by binding sidebar actions to the same tab/subtab handlers.
- For body menus, apply `display: none` or a specific “admin-hide-menu” utility class.
- The Ops ERD/Manual block should render in **Ops/Integration > System Status** view, above the system status content.
- Docs block includes the existing admin links: **ERD Summary**, **ERD Detail**, **Tool Manual** (localized labels preserved). Language toggle stays in header.
- Responsive: On narrow widths where the sidebar collapses to a rail or drawer, the hierarchy must still be accessible. Opening the drawer shows top-level items with expandable children; one top-level section expanded at a time; selecting a top-level section without an active child auto-selects its first child.

## Acceptance Criteria
- Management screens show **no in-body navigation menus**.
- Left sidebar controls all navigation, with **hierarchy and accordion behavior**.
- First subtab auto-selected on top-level click.
- Exactly one top-level section open at all times.
- ERD/Manual links visible at top of Ops main panel.
- Operator/ops pages outside management remain unchanged.
- Deep links or previously selected subtabs are respected on load (no unwanted reset).
- Dashboard behaves as a leaf item with a single implicit subtab, and counts as the “open” section when active.
- Hidden body menus are not focusable/announced by assistive tech.
