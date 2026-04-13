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

## Scope (Routes / Shells)
- **Applies to:** all admin pages rendered with `body[data-shell-mode=\"admin\"]` (admin shell).
- **Excluded from grid refactor:** ops shell/pages (e.g., `/ops`), except for the explicit removals listed in “Ops Scope (Minimal Change)”.

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
- Header behavior: **not sticky** (no `position: sticky/fixed`). Header is static in layout; nav/content scroll independently below it.
- Scroll behavior: left nav and main content are **independent scroll containers** within the main row.

### 2) Left Menu Hierarchy + Accordion
- Left menu shows only parent items; children appear only when a parent is active/open.
- Clicking a parent expands its children and collapses any other open parent.
- Child items use smaller font + tighter spacing and a subtle indent.
- Menu content is rendered only in the left column; no menu elements appear in the main content area.
- Menu open state persists within the **same tab** via `sessionStorage`. It resets on a new tab/session.
- Deep-linking to a child auto-opens its parent.

### 3) Section Description Toggle
- Section description text is collapsed by default.
- Title row includes a toggle button (chevron).
- Toggle state stored in `sessionStorage` (same-tab persistence only).
- Collapsed state removes the description height entirely.

### 4) Ops Scope (Minimal Change)
- Ops home: remove the left menu placeholder/slot so content can use full width (`.primary-side-nav-slot[data-primary-nav-slot]`).
- Ops home + Admin dashboard: remove the bottom collectibles registration block (`#homeMasterGoodsSection`, `#homeLinkedGoodsPanel`).

### 5) Responsive Behavior
- `<=1080px`: collapse left nav to icon-only rail (use existing icon-rail styling such as `.primary-side-nav--icon`).
- No overlay/drawer for admin shell; icon-only rail remains visible at small widths.

## Information Architecture
Left menu categories and exact mapping:
- **Dashboard**
  - 대시보드
- **Media**
  - 검색
  - 관리
  - 등록/수집
    - 직접 등록
    - 구매 내역
    - 대량 등록
    - 마스터 정리
  - 소스 보강
- **Collectibles**
  - 컬렉터블 검색
  - 컬렉터블 관리
  - 컬렉터블 등록
- **Ops/Integration**
  - 시스템 상태
  - 장식장
  - 슬롯
  - 카메라
  - 예외 큐
  - 계정
  - 연동/API 설정
  - 백업/내보내기
  - 메타 동기화
  - 문서 / ERD / 활용 매뉴얼
    - ERD 요약
    - ERD 상세
    - 툴 활용 매뉴얼

Submenu labels are smaller than parent labels, with a subtle indent.

## Interaction Details
- Accordion: only one parent open at a time.
- Menu buttons and toggles are `<button>` elements with `aria-expanded`, `aria-controls`, and accessible labels (e.g., “미디어 메뉴 펼치기/접기”).
- Toggle button for description uses `aria-expanded` and is keyboard reachable.
- Focus order: parent button first; child items only focusable when expanded.
- Collapsed descriptions can be expanded without reflowing other layout elements incorrectly.

## Risks / Mitigations
- Risk: Existing CSS may assume header inside body wrapper.
  - Mitigation: Update selectors to target the new header placement; keep class names stable.
- Risk: Menu state lost on navigation.
  - Mitigation: Keep state in `sessionStorage` keyed by menu ID; open parent on child deep-link.

## Testing / Verification
- Admin page: header stays full width, menu sits below header, content aligns under header.
- Admin page: header remains static (no sticky/fixed), nav/content scroll independently.
- Admin page: menu accordion works; only one parent open.
- Admin page: description toggles collapse/expand; default is collapsed.
- Admin page: menu open state persists across route changes in the same tab.
- Admin page: deep-link to a child auto-opens its parent.
- Admin page: icon-only rail appears at <=1080px.
- Admin page: keyboard navigation reaches all menu buttons and toggles (aria-expanded reflects state).
- Ops home: left menu placeholder removed; layout width correct.
- Ops home + Admin dashboard: collectibles registration block removed.

## Success Criteria
- Header no longer shifts when left menu is present.
- Left menu aligns under header without overlap.
- Menu hierarchy is visible only on the left, not inside content.
- Description text does not consume vertical space by default.
- Ops home shows no left menu placeholder and no bottom collectibles registration block.
- Nav/content scroll independently while header remains static in layout.
