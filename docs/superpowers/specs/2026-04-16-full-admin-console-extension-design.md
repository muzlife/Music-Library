# Full Admin Console Extension Design

**Date:** 2026-04-16  
**Owner:** Codex + Admin Ops

## Goal
Extend the `Nexus OS / operational console` visual language from the already redesigned `대시보드` and `마스터 정리` surfaces to the rest of the admin application. The result should make the full admin experience feel like one coherent control system rather than a mix of legacy card layouts and newer console surfaces.

## Relationship To Existing Spec
This document extends:
- [2026-04-16-dashboard-and-master-console-redesign-design.md](/Volumes/Data/Works/07.__PROJECT_SLUG__/docs/superpowers/specs/2026-04-16-dashboard-and-master-console-redesign-design.md)

That earlier spec remains the design source for:
- `#tabHome`
- `#homeDashboardCard`
- `#registeredMasterMergeCard`

This document covers the rest of the admin tabs and the shared shell rules needed to unify them.

## Scope
- Shared admin shell in `/Volumes/Data/Works/07.__PROJECT_SLUG__/app/static/index.html`
  - top header
  - tab navigation
  - shared tab panel framing
- Admin tabs:
  - `#tabSimple`
  - `#tabCamera`
  - `#tabMedia`
  - `#tabCollectibles`
  - `#tabOps`
- Existing `#tabHome` and `#registeredMasterMergeCard` may receive shared-shell adjustments only if needed for consistency

## Non-Goals
- No route changes
- No backend or API changes
- No data-model changes
- No workflow rewrite for search, registration, exceptions, source workbench, or collectibles flows
- No per-feature information architecture rewrite beyond panel grouping and shell consistency
- No second visual theme for specific tabs

## Hard Boundary For Prior-Phase Screens
This phase does **not** reopen the already redesigned dashboard or master-merge workflow as independent redesign projects.

Allowed adjustments on prior-phase screens:
- shared header/nav alignment
- shared console token alignment
- minor spacing or border normalization needed so adjacent tabs do not break visual consistency

Not allowed in this phase:
- new dashboard layout experiments
- new master-merge workflow changes
- changing cabinet/detail/workbench information hierarchy beyond shared shell normalization
- changing merge interaction behavior, history behavior, or rollback behavior

## Problem Statement
The admin application still uses multiple visual dialects:
- legacy rounded cards
- isolated form boxes
- tab-specific local styling
- newer hard-edge console surfaces on `대시보드` and `마스터 정리`

This inconsistency causes three problems:
1. Tabs do not feel like parts of the same product.
2. Dense operational tabs still read like generic forms instead of work surfaces.
3. The new dashboard/master cleanup direction cannot scale unless the rest of the shell adopts the same grammar.

## Design Direction
Use one console grammar across the full admin app:
- near-black shell background
- hard-edge panels instead of rounded cards
- restrained grayscale surfaces
- orange as the primary active/selection accent
- high-contrast typography with clear primary/secondary/meta hierarchy
- panel headers and state strips that emphasize operator context over decorative hero treatment

## Shared Shell Rules

### 1. One Console Shell
All admin tabs should feel like they belong to one shell:
- shared dark header
- shared hard-edge tab navigation
- shared tab-panel frame treatment
- shared utility/status treatment

The goal is not identical tab layouts. The goal is consistent shape language, spacing rhythm, border treatment, and color hierarchy.

### 2. Panel Grammar
Each admin tab should use the same four surface roles where applicable:
- **status strip**
  - compact state, counts, active selection, or last-run summary
- **primary surface**
  - the main search table, camera feed, workspace, or form
- **secondary rail**
  - supporting filters, summaries, side controls, or auxiliary detail
- **action dock**
  - actions that commit, apply, fetch, or move work

Not every tab needs all four roles, but every tab should map its content into this grammar instead of ad-hoc cards.

### 3. Hard Edges
- Buttons may keep a slight radius for tap clarity.
- Panels, cards, inputs, chips, badges, and section containers should move to hard-edge or near-zero radius.
- Rounded card islands should be removed from admin tabs unless a specific control requires a small radius for usability.

### 4. Visual Separation
Panel separation should come from:
- thin borders
- graphite tone changes
- compact spacing bands
- subtle accent rules on important states

Panel separation should not depend on:
- big shadows
- soft floating cards
- overfilled tinted boxes
- excessive background gradients

### 5. Text Hierarchy
Standardize to three text levels:
- **Primary text**
  - titles, labels, names, main values
- **Secondary text**
  - supporting context, sublabels, helper copy
- **Meta text**
  - ids, timestamps, auxiliary counts, low-priority status

Use the same color mapping and spacing rhythm across all admin tabs.

## Shared Responsive Rule
- Desktop first, optimized for wide admin screens.
- Minimum supported admin width for the redesigned shell is `1280px`.
- Below `1120px`, secondary rails may stack below the primary surface.
- At narrower widths:
  - secondary rails may stack below primary surfaces
  - status strips may wrap into multiple rows
  - action docks may compress before core work areas
- Search results, editor surfaces, camera preview, and workbench regions must remain fully usable without horizontal clipping.

## DOM / Screen Anchor Mapping

### Shared Shell Anchors
- `#adminTabs`
- `#tabHome`
- `#tabSimple`
- `#tabCamera`
- `#tabMedia`
- `#tabCollectibles`
- `#tabOps`
- shared tab/button routing and shell utility areas already handled in `/Volumes/Data/Works/07.__PROJECT_SLUG__/app/static/index.html`

### `#tabSimple` Anchors
- `#opsHomeLayout`
- `#operatorLookupStatus`
- `#operatorHelperSummary`
- `#operatorLookupResults`
- `#operatorRecentSections`
- `#opsLibraryContextPanel`
- `#opsLibraryContextClimate`
- `#opsLibraryContextBody`

### `#tabCamera` Anchors
- `.shared-camera-shell`
- `#sharedCameraList`
- `#sharedCameraPreview`
- `#sharedCameraPreviewBody`
- `#sharedCameraStatus`

### `#tabMedia` Anchors
- `#tabMedia` shell section and mode tabs
- `#tabSearch`
- `#tabManage`
- `#registerMasterPanel`
- `#tabSource`
- `#sourceWorkbenchCard`

### `#tabCollectibles` Anchors
- `.goods-shell`
- `#goodsSearchSurface`
- `#goodsManageSurface`
- `#goodsRegisterSurface`
- `#goodsSearchResults`
- `#goodsManageContent`

### `#tabOps` Anchors
- `#tabOps`
- `#opsSystemStatusSummary`
- `#opsSystemStatusLine`
- `#opsCabinetPanel`
- `#opsCameraPanel`
- `#opsSlotPanel`
- `#opsExceptionPanel`
- `#opsExceptionSummary`
- `#opsExceptionList`
- `#opsExceptionSelectionSummary`
- `#opsAccountPanel`
- `#opsProviderPanel`
- `#opsExportPanel`
- `#opsMetaSyncPanel`

The plan should prefer these anchors for shell grouping and selector scope rather than broad global overrides.

## Tab-Specific Design

### `#tabSimple` — Operations Home
Purpose:
- quick operator lookup
- recent activity
- request context and operator-side support context

Design approach:
- convert the current search + feed layout into a console workspace
- use a compact status strip above the feed/search area
- make operator results feel like work rows rather than independent cards
- push helper summaries and request status into a secondary rail or support panel group

Key outcome:
- the tab should feel like a live operator console, not a search page with stacked result cards

Preserved interaction rules:
- lookup query, sort mode, and signature filters stay in place
- search vs recent feed behavior stays intact
- current location jump/open behavior remains unchanged
- request context and weather/context side panel remain supportive, not primary action surfaces

### `#tabCamera` — Camera Monitoring
Purpose:
- camera list, preview, and cabinet monitoring state

Design approach:
- treat the page like a surveillance console
- camera list becomes a narrow instrument rail
- active preview becomes the primary surface
- camera health, timestamps, and capture metadata become compact telemetry rows

Key outcome:
- the preview must be visually dominant
- camera controls should look like a monitoring panel, not a standard form card

Preserved interaction rules:
- selecting a camera must still update the active preview
- list, preview body, and status line stay on the same tab
- no camera transport or snapshot behavior changes in this phase

### `#tabMedia` — Media Admin
Purpose:
- search
- manage
- register
- source workflows

Design approach:
- keep each media submode intact, but place them inside one consistent console shell
- replace local boxed forms and result cards with surface panels that match dashboard/master cleanup
- unify search headers, result containers, and action zones across submodes

Submode notes:
- **search**
  - results should read as operational rows/panels
- **manage**
  - detail/editor surfaces should feel like one instrument panel, not multiple detached cards
- **register**
  - intake forms should look embedded into a control surface
- **source**
  - source workbench and diff review should lean into command/workspace/log framing

Key outcome:
- switching media submodes should still feel like staying inside one console application

Preserved interaction rules:
- media submode switching remains exactly as-is
- search keeps the same query/filter/result semantics
- manage keeps the same editor, location, source-meta, track-map, and delete flows
- register keeps the current grouped form workflow
- source workbench keeps current queue, candidate, diff review, and apply behavior
- the already redesigned `#registerMasterPanel` and `#registeredMasterMergeCard` keep their current interaction model

### `#tabCollectibles` — Collectibles Admin
Purpose:
- collectible search and management

Design approach:
- mirror the same shell grammar used for media
- unify shared controls, result lists, and detail panes with the media/admin console style
- reduce the visual gap between media and collectibles so they feel like sibling modules

Key outcome:
- collectibles should no longer feel like a separate older interface

Preserved interaction rules:
- collectibles submode switching remains exactly as-is
- search filter semantics remain unchanged
- manage keeps current save/delete/mapping/relation flows
- register keeps the current intake flow and optional mappings

### `#tabOps` — Operations / Integrations
Purpose:
- exceptions
- workbench flows
- system and sync-oriented operator actions

Design approach:
- lean fully into command surface styling
- structure the tab as:
  - status strip
  - primary workspace
  - exception or queue rail
  - action dock / system log area
- make active exception and batch actions visually clear without filling the screen with warning boxes

Key outcome:
- the tab should read as an operator workflow console with explicit state, not a patchwork of utilities

Preserved interaction rules:
- exception queue behavior remains unchanged
- workbench batch and review actions remain unchanged
- no exception taxonomy or queue-routing logic changes in this phase
- this tab owns exception/workbench/operator integration utilities; `#tabSimple` remains the quick operator lookup and context entry surface

## Shared Styling Requirements

### Color
- Background shell: near-black
- Primary surfaces: dark graphite
- Secondary surfaces: blue-graphite / steel-graphite variants
- Borders: muted gray-blue
- Accent: orange
- Success/info/warning variants should stay within the restrained console palette

### Inputs and Filters
- Inputs, selects, and filter groups should be visually embedded into panels
- Avoid the old “white/gray form field inside soft card” feel
- Keep contrast high enough for dense operational use

### Tables, Rows, and Lists
- Replace soft card repetition with framed row systems where appropriate
- Large result sets should prioritize scan speed:
  - stronger row boundaries
  - denser metadata columns
  - lower reliance on shadows and rounded containers

### Empty and Loading States
- Use compact console-state messaging
- Avoid large friendly empty cards that break the system tone

## Accessibility & Readability
- Contrast must remain high on dark backgrounds
- Active/selected states must not rely on color alone
- Keyboard focus must remain obvious
- Smaller metadata text must still be readable on desktop admin displays

## Implementation Strategy

### CSS First, DOM Second
Prefer:
- extending shared console tokens
- introducing shared admin-console helper classes
- wrapping existing tab sections with minimal shell containers where needed

Avoid:
- rewriting entire tab DOM structures if CSS and limited wrappers can solve the problem

### Minimal Structural Changes
DOM changes are allowed when necessary to define:
- status strips
- primary/secondary panel grouping
- action docks

But the redesign should not turn into a tab-by-tab feature rewrite.

### Screen-Scoped Changes
Keep styles scoped to the admin shell and specific tab roots. Do not let this redesign spill into unrelated public or auth surfaces.

## Acceptance Criteria
1. All admin tabs visually belong to the same console system.
2. Legacy rounded-card language is removed from admin tab bodies except for slight-radius buttons.
3. Media, collectibles, camera, and ops tabs use the same panel grammar and contrast hierarchy as dashboard/master cleanup.
4. Existing workflows remain intact with no route or backend changes.
5. Each tab has clearer state separation between status, main work area, support context, and actions.

## Risks
- **Risk:** A full-shell restyle could unintentionally reduce readability on dense tabs.  
  **Mitigation:** Keep text hierarchy strict and verify contrast against the darkest surfaces.

- **Risk:** CSS-only unification may miss some deeply nested legacy boxes.  
  **Mitigation:** Audit each tab root and add minimal wrapper classes where needed.

- **Risk:** Over-normalizing layouts could make distinct workflows feel cramped.  
  **Mitigation:** Keep the panel grammar shared, but let each tab retain its natural information density and component sizing.

## Verification Expectations
- Visual QA on each admin tab:
  - header/nav consistency
  - panel framing consistency
  - text contrast
  - removal of rounded legacy cards
- Regression QA for:
  - media submode switching
  - collectibles flow
  - operator lookup flow
  - camera selection/preview
  - exceptions/workbench actions
- Update static shell tests so the new admin-wide console framing is asserted explicitly
