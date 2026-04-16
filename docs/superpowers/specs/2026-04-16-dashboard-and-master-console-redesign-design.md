# Dashboard & Master Console Redesign Design

**Date:** 2026-04-16  
**Owner:** Codex + Admin Ops

## Goal
Apply a `Nexus OS / operational console` visual language to the admin `대시보드` and `마스터 정리` screens, while preserving the current workflows and data behavior. The result should feel denser, more deliberate, and more like an operations surface than a generic back-office card UI.

## Scope
- Admin `대시보드` screen in `/Volumes/Works/07.hahahoho/app/static/index.html`
  - `#tabHome`
  - `#homeDashboardCard`
  - related dashboard panels, toolbars, and selection surfaces
- Admin `등록/수집 > 마스터 정리` screen in `/Volumes/Works/07.hahahoho/app/static/index.html`
  - `#registerMasterPanel`
  - `#registeredMasterMergeCard`
- Shared visual tokens needed by those two screens only

## Non-Goals
- No route changes
- No API or data model changes
- No workflow rewrite for cabinet placement, search, merge, or rollback logic
- No full-app redesign in this phase
- No marketing-style hero visuals or ornamental motion that slows operations

## Source Direction
Visual reference: [Neuform - Nexus OS Operational Intelligence](https://neuform.ai/page/nexus-os-operational-intelligence)

What to borrow:
- near-black matte background
- thin framed panels instead of soft cards
- single orange accent with restrained grayscale hierarchy
- console-like density, labels, telemetry, and state emphasis
- mono/data typography for counts, ids, and status

What not to borrow:
- landing-page scale hero composition
- oversized decorative 3D visuals
- low-contrast typography that harms scan speed
- presentation-first interactions that slow routine operations

## Current Screen Anchors

### Dashboard
Current dashboard already has the right functional primitives:
- top summary cards
- cabinet/slot occupancy panel
- central cabinet detail and rack surface
- right-side workbench with unslotted/search modes
- selected item sort-artist editing inside slot/workbench contexts

The issue is not missing functionality. The issue is that the screen still reads like stacked cards rather than a coherent control surface.

### Master Cleanup
Current `등록 마스터 병합` already has the correct workflow:
- single search input
- search results with `병합` / `대표`
- representative workspace
- merge target workspace
- merge execution, recent history, safe rollback

The issue is visual framing and hierarchy. Search results and workspace feel like repeated list blocks rather than a command surface with a live target state.

## Design Principles
1. **Operations first**
- Every visual change must improve scanning, targeting, or state clarity.
- Decorative treatment must stay secondary to counts, labels, item identity, and action state.

2. **One shell, clear roles**
- Each screen should read as a composed surface with clear role boundaries:
  - context/state
  - main working area
  - action/secondary workspace

3. **Hard edges over soft cards**
- Prefer framed panels, rails, and thin separators over rounded generic cards.
- Use orange to mark activity, focus, and armed actions, not as a fill color everywhere.

4. **Dense but readable**
- Compress empty space, but keep enough rhythm for fast scanning.
- Titles should shrink; metadata, ids, counts, and status should become more legible.

5. **Behavior stays stable**
- Existing event wiring, filtering, selection, merge history, and rollback behavior should survive the restyle intact.

## Shared Visual System

### Color
- Background base: very dark charcoal / black
- Panel surface: slightly lighter graphite
- Border/frame: desaturated gray-blue or steel gray
- Text primary: off-white
- Text secondary: muted cool gray
- Accent primary: orange
- Accent alert: orange-red, derived from the same family

### Typography
- Section labels and status chips: condensed or tighter sans feel
- Counts, ids, timestamps, master ids: mono or mono-like styling
- Reduce oversized page titles; elevate small uppercase or compact labels instead

### Surfaces
- Replace soft card feel with framed console panels
- Introduce subtle inner glow / edge highlight only where it helps focus
- Add restrained grid/noise treatment in backgrounds, scoped to these screens

### Controls
- Buttons should skew toward outline / low-fill styles
- Active / selected / armed states should be clearer than hover states
- Inputs and filters should look embedded in instrument panels, not isolated form cards

## Dashboard Layout Redesign

### Target Structure
The dashboard should be reorganized into four visual bands:

1. **Top status bar**
- Compact strip showing current cabinet context, slot context, selection count, and recent movement state
- Existing header title/subtitle remains, but compressed into console-style metadata rather than hero copy

2. **Left rail**
- Cabinet map summary
- slot occupancy context
- mode/help labels
- compact telemetry blocks

3. **Central spatial surface**
- Cabinet detail
- rack surface
- cover flow / shelf / thumbnail / list views
- selected item focus frame

4. **Right action rail**
- move workbench
- unslotted/search result source switching
- selection summary
- sort-artist editing
- recommendation / move actions

### Mapping to Existing DOM
- Keep `#homeDashboardCard` as the root surface
- Convert `.dashboard-hero-grid` from five equal promo cards into tighter telemetry panels
- Reframe `.dashboard-main-grid` into a left/center/right console composition
- Keep slot and workbench internals, but visually unify them under the same console framing rules

### Dashboard Visual Direction
- Cabinet grid becomes the most spatially prominent element
- Workbench becomes a darker instrument rail with high state clarity
- Selection, move mode, and sort warnings should look like system state, not inline form clutter

### Dashboard Responsive Rule
- Desktop first: left rail, central surface, right rail
- Mid widths: left rail compresses first, right rail stacks underneath central surface only if necessary
- Mobile/narrow admin widths:
  - keep function intact
  - collapse telemetry blocks
  - stack rails vertically
  - do not invent a separate mobile workflow

## Master Cleanup Layout Redesign

### Target Structure
The master cleanup surface should read as a command console:

1. **Command bar**
- one search field
- search action / clear action
- current representative summary
- merge target count
- primary `병합 실행` button

2. **Search results panel**
- result cards with cover, title, source, id, year, member count
- actions aligned to the right
- `대표` state visibly locked when one representative exists

3. **Workspace panel**
- representative master panel
- merge target stack
- recent merge history
- latest safe rollback action

4. **System status strip**
- merge ready / blocked reason / completed / rollback available
- current status messages should be reframed as operator log or state line

### Mapping to Existing DOM
- Keep `#registeredMasterMergeCard` as the feature root
- Preserve:
  - `#registeredMasterMergeQuery`
  - `#registeredMasterMergeBody`
  - `#registeredMasterMergeRepresentativeBody`
  - `#registeredMasterMergeTargetBody`
  - `#registeredMasterMergeHistoryBody`
- Change layout and visual grouping around those nodes rather than rewriting merge logic

### Master Cleanup Visual Direction
- Search results and workspace should feel like two connected halves of one system
- Representative master should have the strongest focus treatment
- Merge targets should look armed but secondary
- History should read like a console action log, not another generic list

### Interaction Rules To Preserve
- Search input remains single-source
- `대표` remains single-select
- `병합` remains multi-select and preserves insertion order
- Representative and merge targets cannot overlap in the current session
- Confirmation, history, and safe rollback remain intact

## Motion & Feedback
- Use light transitions only for:
  - panel reveal
  - state chip changes
  - focus/selection frames
- Avoid long fades, parallax, or presentation-style choreography
- Success/error feedback should feel like console state updates

## Accessibility & Readability
- Contrast must improve over the current UI, not degrade
- Orange accent should not be the only active-state cue
- Buttons and focus rings must remain keyboard-legible
- Cover art cannot be the only identifier; title/id/source remain always visible

## Implementation Notes
- Keep this phase inside `/Volumes/Works/07.hahahoho/app/static/index.html`
- Prefer adding screen-scoped CSS hooks rather than rewriting unrelated global admin styles
- Avoid touching backend logic for this redesign phase
- If a shared token is introduced, scope it to dashboard/master-cleanup surfaces first

## Acceptance Criteria
1. Dashboard and master cleanup visibly share the same console language.
2. Existing workflows remain usable without retraining:
   - dashboard placement and workbench operations
   - master search, representative selection, merge, history, rollback
3. The screens feel denser and more deliberate, with clearer state hierarchy.
4. Search results, workspaces, and telemetry become easier to scan than in the current card-stack layout.
5. No unrelated admin screens change in this phase.

## Risks
- **Risk:** The new tone could reduce readability if contrast is over-stylized.  
  **Mitigation:** Favor grayscale clarity first, accent second.

- **Risk:** Restyling could leak into unrelated admin screens.  
  **Mitigation:** Scope selectors tightly to the two target roots.

- **Risk:** Dashboard can become visually heavy because it already contains many tools.  
  **Mitigation:** Use layout hierarchy and panel grouping before adding extra ornament.

## Validation Plan
- Visual check on both screens at desktop and mid-width admin sizes
- Confirm unchanged behavior for:
  - dashboard cabinet selection
  - slot/workbench selection and move mode
  - sort-artist editing affordances
  - registered master search
  - representative selection
  - merge target accumulation
  - merge confirmation/history/rollback visibility
