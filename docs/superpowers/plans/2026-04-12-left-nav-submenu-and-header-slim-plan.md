# Left Nav Submenu + Header Slim Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add left-nav submenus and docs links in admin mode while slimming the header to language + ops/admin controls, keeping camera access in ops header only.

**Architecture:** Extend the existing `primary-side-nav` markup with a submenu + docs section, wire it to existing `openAdminConsole`/`switchSubTab` flows, and tighten header utility composition. Keep routing and existing panels unchanged; only UI wiring and visibility change.

**Tech Stack:** Static HTML/CSS/JS in `app/static/index.html`

---

## Assumptions
- Submenu labels map directly to existing modes/routes (no new routes).
- Docs links keep their existing URLs; they only move location.
- Ops mode should **not** show Docs links.
- Camera stays accessible in ops header utility (not in ops left nav).
- Admin mobile still needs a nav toggle for the drawer.

## File Map
**Modify:**
- `/Volumes/Works/07.hahahoho/.worktrees/deploy-left-sidebar/app/static/index.html`
  - Left nav markup + submenu + docs links
  - Header utility markup + visibility rules
  - CSS for new nav sections and slim header
  - JS for submenu state sync and click routing

**Tests:** No automated UI tests exist for this static HTML. Verification will be manual (see each task).

---

### Task 1: Slim Header Utility to Language + Ops/Admin Only

**Files:**
- Modify: `/Volumes/Works/07.hahahoho/.worktrees/deploy-left-sidebar/app/static/index.html`

- [ ] **Step 1: Add/confirm nav-only header class usage**

```html
<header id="appHero" class="hero admin-shell-hero admin-shell-hero--nav-only">
...
<section id="opsHomeHero" class="ops-home-hero ops-home-hero--nav-only" style="display:none;">
```

- [ ] **Step 2: Remove docs links from header utility**

```html
<div class="shell-utility-tools shell-utility-tools--meta">
  <!-- remove .shell-doc-links here -->
  <label class="shell-locale-picker" for="shellLocaleSelect">...</label>
</div>
```

- [ ] **Step 3: Restrict utility buttons in header**
  - Keep: `shellAdminBtn`, `shellOpsHomeBtn`, `shellLocaleSelect`, `tabCameraBtn` (ops mode only), `shellNavToggleBtn` (admin mobile only)
  - Hide: `appPrefsResetBtn`, `appSessionInfo`, `appLogoutBtn` in header row

```js
setDisplayIfPresent("appLogoutBtn", "none");
setDisplayIfPresent("appPrefsResetBtn", "none");
setDisplayIfPresent("appSessionInfo", "none");
```

- [ ] **Step 4: Manual verification**
  - Admin mode: only language + “hahahoho” button visible in header.
  - Ops mode: only language + “관리” button + camera button visible in header.
  - Mobile admin: menu toggle remains visible.

- [ ] **Step 5: Commit**

```bash
git add app/static/index.html
git commit -m "Slim header utilities to language and ops/admin controls"
```

---

### Task 2: Add Left Nav Submenu + Docs Section Markup

**Files:**
- Modify: `/Volumes/Works/07.hahahoho/.worktrees/deploy-left-sidebar/app/static/index.html`

- [ ] **Step 1: Add submenu container under primary tabs**

```html
<div class="primary-side-subnav" data-primary-subnav>
  <div class="primary-side-subnav__group" data-primary-subnav-group="media">
    <span class="primary-side-subnav__label">미디어</span>
    <button data-primary-subnav-action="media:search">검색</button>
    <button data-primary-subnav-action="media:manage">관리</button>
    <button data-primary-subnav-action="media:register">등록</button>
    <button data-primary-subnav-action="media:source">소스</button>
  </div>
  <div class="primary-side-subnav__group" data-primary-subnav-group="collectibles">
    <span class="primary-side-subnav__label">컬렉터블</span>
    <button data-primary-subnav-action="collectibles:search">검색</button>
    <button data-primary-subnav-action="collectibles:manage">관리</button>
    <button data-primary-subnav-action="collectibles:register">등록</button>
  </div>
  <div class="primary-side-subnav__group" data-primary-subnav-group="ops">
    <span class="primary-side-subnav__label">운영/연계</span>
    <button data-primary-subnav-action="ops:cabinet">장식장</button>
    <button data-primary-subnav-action="ops:slot">슬롯</button>
    <button data-primary-subnav-action="ops:exception">예외 큐</button>
    <button data-primary-subnav-action="ops:account">계정</button>
    <button data-primary-subnav-action="ops:providers">연동/API 설정</button>
    <button data-primary-subnav-action="ops:export">백업/내보내기</button>
    <button data-primary-subnav-action="ops:meta_sync">메타 동기화</button>
  </div>
</div>
```

- [ ] **Step 2: Add docs section at bottom of left nav**

```html
<div class="primary-side-docs" data-primary-docs>
  <span class="primary-side-docs__label">Docs</span>
  <a href="/tool-docs/erd-summary" target="_blank" rel="noreferrer">ERD 요약</a>
  <a href="/tool-docs/erd-detail" target="_blank" rel="noreferrer">ERD 상세</a>
  <a href="/tool-docs/manual" target="_blank" rel="noreferrer">툴 활용 매뉴얼</a>
</div>
```

- [ ] **Step 3: Add CSS for submenu + docs**

```css
.primary-side-subnav { display: grid; gap: 8px; margin-top: 10px; }
.primary-side-subnav__group { display: grid; gap: 4px; }
.primary-side-subnav__label { font-size: 0.72rem; font-weight: 700; color: #64748b; }
.primary-side-subnav button { text-align: left; padding: 6px 10px; border-radius: 8px; }
.primary-side-subnav button.active { background: #0f766e; color: #fff; }
.primary-side-docs { margin-top: auto; display: grid; gap: 6px; padding-top: 10px; border-top: 1px solid #e2e8f0; }
.primary-side-docs a { font-size: 0.78rem; color: #475569; }
```

- [ ] **Step 4: Manual verification**
  - Admin mode: submenu appears under active primary tab; docs appear at bottom.
  - Ops mode: left nav hidden → docs hidden.

- [ ] **Step 5: Commit**

```bash
git add app/static/index.html
git commit -m "Add left nav submenu and docs section markup"
```

---

### Task 3: Wire Submenu Actions + Active State Sync

**Files:**
- Modify: `/Volumes/Works/07.hahahoho/.worktrees/deploy-left-sidebar/app/static/index.html`

- [ ] **Step 1: Extend primaryNavElements()**

```js
return {
  nav: document.querySelector(".primary-side-nav"),
  tabs: $("adminTabs"),
  subnav: document.querySelector("[data-primary-subnav]"),
  docs: document.querySelector("[data-primary-docs]"),
  ...
};
```

- [ ] **Step 2: Add submenu click handler**

```js
document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-primary-subnav-action]");
  if (!btn) return;
  const action = btn.getAttribute("data-primary-subnav-action") || "";
  const [section, key] = action.split(":");
  if (section === "media") openAdminConsole(key);
  if (section === "collectibles") { openAdminConsole("collectibles"); switchGoodsMode(key); }
  if (section === "ops") { openAdminConsole("ops"); switchSubTab("ops", key); }
});
```

- [ ] **Step 3: Add `syncPrimarySubnavActiveState()`**
  - Show only submenu group for active primary tab.
  - If no group is active, hide the entire submenu container to avoid blank space.
  - Highlight active item based on `mediaMode`, `goodsMode`, or active ops subtab.

```js
function syncPrimarySubnavActiveState() {
  const activePrimary = PRIMARY_NAV_ITEMS.find(({ btn }) => $(btn)?.hasAttribute("aria-current"))?.id || "home";
  document.querySelectorAll("[data-primary-subnav-group]").forEach((group) => {
    const match = group.getAttribute("data-primary-subnav-group") === activePrimary;
    group.style.display = match ? "grid" : "none";
  });
  const subnav = document.querySelector("[data-primary-subnav]");
  if (subnav) subnav.style.display = ["media", "collectibles", "ops"].includes(activePrimary) ? "grid" : "none";
  // set active buttons for media/goods/ops based on current state
}
```

- [ ] **Step 4: Tie sync into existing flow**
  - Call `syncPrimarySubnavActiveState()` from `syncPrimaryNavActiveState()` and after `switchSubTab` calls.

- [ ] **Step 5: Manual verification**
  - Clicking submenu switches to correct panel.
  - Active submenu item updates when tabs change.

- [ ] **Step 6: Commit**

```bash
git add app/static/index.html
git commit -m "Wire left nav submenus to existing tab flows"
```

---

### Task 4: Camera Placement + Ops Subtab Cleanup

**Files:**
- Modify: `/Volumes/Works/07.hahahoho/.worktrees/deploy-left-sidebar/app/static/index.html`

- [ ] **Step 1: Add camera primary tab to left nav (admin only)**
  - Add a **new** button id (e.g., `tabCameraNavBtn`) in left nav primary tab list to avoid collisions with the ops-header `tabCameraBtn`.
  - `tabCameraBtn` remains the ops-header button.
  - Ensure `PRIMARY_NAV_ITEMS` and `normalizePrimaryNavTab()` include `"camera"`.

- [ ] **Step 2: Remove camera from ops subtab line**

```html
<!-- Remove -->
<button id="opsCameraTabBtn" ...>카메라</button>
```

- [ ] **Step 3: Keep ops header camera button visible only in ops mode**
  - `tabCameraBtn` in header should show only for ops mode.

- [ ] **Step 4: Manual verification**
  - Admin mode: camera visible in left nav primary tabs.
  - Ops mode: camera button still in header utility.

- [ ] **Step 5: Commit**

```bash
git add app/static/index.html
git commit -m "Move camera to admin left nav and remove ops subtab"
```

---

### Task 5: Drawer Behavior on Mobile

**Files:**
- Modify: `/Volumes/Works/07.hahahoho/.worktrees/deploy-left-sidebar/app/static/index.html`

- [ ] **Step 1: Ensure submenu moves into drawer with tabs**
  - Update `syncPrimaryNavLayout()` to move submenu + docs into drawer panel when in drawer mode.

- [ ] **Step 2: Restrict drawer submenu to active primary tab**
  - Reuse `syncPrimarySubnavActiveState()` logic to hide non-active groups.

- [ ] **Step 3: Manual verification**
  - On mobile width: drawer shows primary tabs + active submenu + docs.

- [ ] **Step 4: Commit**

```bash
git add app/static/index.html
git commit -m "Ensure drawer shows active submenu only on mobile"
```

---

## Final Manual Verification
- Admin mode:
  - Left nav shows primary tabs + active submenu + Docs at bottom.
  - Header shows only language + “hahahoho” button.
- Ops mode:
  - Header shows only language + “관리” + camera button.
  - Docs not shown.
- Mobile:
  - Drawer includes primary tabs + active submenu + Docs.
