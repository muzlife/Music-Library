
    function currentAppPath() {
      return window.location.pathname || "/";
    }

    function currentAppRouteKey() {
      return `${currentAppPath()}${window.location.search || ""}`;
    }

    function shellModeFromPath() {
      const path = currentAppPath();
      if (path === "/ops/cabinets") return "cabinets";
      if (path === "/ops") return "ops";
      return "admin";
    }

    function normalizeCabinetRouteSelection(cabinetName, columnCode, cellCode) {
      const nextCabinetName = String(cabinetName || "").trim();
      const nextColumnCode = String(columnCode || "").trim();
      const nextCellCode = String(cellCode || "").trim();
      if (!(nextCabinetName && nextColumnCode && nextCellCode)) return null;
      return {
        cabinet_name: nextCabinetName,
        column_code: nextColumnCode,
        cell_code: nextCellCode,
      };
    }

    function cabinetRouteSelectionFromLocation() {
      const params = new URLSearchParams(window.location.search || "");
      return normalizeCabinetRouteSelection(
        params.get("cabinet_name"),
        params.get("column_code"),
        params.get("cell_code"),
      );
    }

    function cabinetRoutePath(selection = null) {
      const normalized = normalizeCabinetRouteSelection(
        selection?.cabinet_name,
        selection?.column_code,
        selection?.cell_code,
      );
      if (!normalized) return "/ops/cabinets";
      const params = new URLSearchParams({
        cabinet_name: normalized.cabinet_name,
        column_code: normalized.column_code,
        cell_code: normalized.cell_code,
      });
      return `/ops/cabinets?${params.toString()}`;
    }

    function resolveCabinetRouteSelection(selection = null) {
      return normalizeCabinetRouteSelection(
        selection?.cabinet_name,
        selection?.column_code,
        selection?.cell_code,
      );
    }

    function isAdminSession(session = appAuthSession) {
      if (!session || !session.authenticated) return false;
      return String(session.role || "").trim().toUpperCase() === "ADMIN";
    }

    function normalizeShellMode(mode, session = appAuthSession) {
      const requested = String(mode || "").trim().toLowerCase();
      const authenticated = Boolean(session?.authenticated);
      if (!authenticated) {
        if (!appAuthSessionResolved) {
          if (requested === "admin") return "admin";
          if (requested === "cabinets") return "cabinets";
        }
        return "ops";
      }
      if (requested === "admin") return isAdminSession(session) ? "admin" : "ops";
      if (requested === "cabinets") return "cabinets";
      return "ops";
    }

    function currentShellMode() {
      return normalizeShellMode(appShellMode, appAuthSession);
    }

    function isShellReadOnly(mode = currentShellMode()) {
      return String(mode || "").trim().toLowerCase() !== "admin" || !isAdminSession(appAuthSession);
    }

    function shellRoutePath(mode, options = {}) {
      if (mode === "admin") return "/admin";
      if (mode === "cabinets") {
        return cabinetRoutePath(resolveCabinetRouteSelection(options.cabinetSelection) || pendingOpsCabinetSelection);
      }
      return "/ops";
    }

    function syncShellReadonlyState() {
      const mode = currentShellMode();
      document.body.dataset.shellMode = mode;
      document.body.dataset.shellReadonly = isShellReadOnly(mode) ? "true" : "false";
      /* 대시보드 가시성은 CSS body:not([data-shell-mode="admin"]) 셀렉터가 처리 */
    }

    function syncShellButtons() {
      const mode = currentShellMode();
      $("tabSimpleBtn")?.classList.toggle("active", mode === "ops");
      $("shellCabinetsBtn")?.classList.toggle("active", mode === "cabinets");
    }

    function syncShellDensityClasses() {
      document.body.dataset.shellDensity = "compact";
      $("appHero")?.classList.remove("admin-shell-hero--compact");
      $("opsHomeHero")?.classList.remove("ops-home-hero--compact");
    }

    const pageHelpDrawerState = {
      open: false,
      helpId: "",
      trigger: null,
    };

    function syncPageHelpTriggerState() {
      document.querySelectorAll("[data-page-help-open]").forEach((btn) => {
        const active = pageHelpDrawerState.open
          && String(btn.getAttribute("data-page-help-open") || "").trim() === pageHelpDrawerState.helpId;
        btn.setAttribute("aria-expanded", active ? "true" : "false");
      });
    }

    function findPageHelpSource(helpId) {
      const normalized = String(helpId || "").trim();
      if (!normalized) return null;
      return Array.from(document.querySelectorAll("[data-page-help-source]"))
        .find((node) => String(node.getAttribute("data-page-help-source") || "").trim() === normalized) || null;
    }

    function renderPageHelpDrawer(helpId) {
      const titleEl = $("pageHelpTitle");
      const bodyEl = $("pageHelpBody");
      const closeBtn = $("pageHelpCloseBtn");
      if (!titleEl || !bodyEl) return false;
      const source = findPageHelpSource(helpId);
      const title = source?.querySelector("summary")?.textContent?.trim() || t("page_help.empty");
      const body = source?.querySelector(".manual-block-body");
      titleEl.textContent = title;
      if (closeBtn) {
        closeBtn.setAttribute("aria-label", t("common.close"));
        closeBtn.setAttribute("title", t("common.close"));
      }
      bodyEl.innerHTML = body
        ? body.innerHTML
        : `<div class="mini muted">${escapeHtml(t("page_help.empty"))}</div>`;
      return Boolean(source && body);
    }

    function openPageHelpDrawer(helpId, trigger = null) {
      const overlay = $("pageHelpOverlay");
      const drawer = $("pageHelpDrawer");
      if (!overlay || !drawer) return;
      pageHelpDrawerState.open = true;
      pageHelpDrawerState.helpId = String(helpId || "").trim();
      pageHelpDrawerState.trigger = trigger || document.activeElement;
      renderPageHelpDrawer(pageHelpDrawerState.helpId);
      overlay.hidden = false;
      drawer.hidden = false;
      document.body.classList.add("page-help-open");
      syncPageHelpTriggerState();
      requestAnimationFrame(() => {
        overlay.classList.add("open");
        drawer.classList.add("open");
        $("pageHelpCloseBtn")?.focus();
      });
    }

    function closePageHelpDrawer(options = {}) {
      if (!pageHelpDrawerState.open) return;
      const overlay = $("pageHelpOverlay");
      const drawer = $("pageHelpDrawer");
      const restoreTarget = pageHelpDrawerState.trigger;
      pageHelpDrawerState.open = false;
      pageHelpDrawerState.helpId = "";
      pageHelpDrawerState.trigger = null;
      document.body.classList.remove("page-help-open");
      overlay?.classList.remove("open");
      drawer?.classList.remove("open");
      if (overlay) overlay.hidden = true;
      if (drawer) drawer.hidden = true;
      syncPageHelpTriggerState();
      if (options.restoreFocus === false) return;
      if (restoreTarget && typeof restoreTarget.focus === "function") {
        restoreTarget.focus();
      }
    }

    function placeShellUtilityBar(mode = currentShellMode()) {
      const utilityBar = $("shellUtilityBar");
      const utilityMainRow = $("shellUtilityMainRow");
      if (!utilityBar || !utilityMainRow) return;
      const targetMount = mode === "admin" ? $("adminUtilityMount") : $("opsUtilityMount");
      const targetMainMount = mode === "admin" ? $("adminUtilityMainMount") : $("opsUtilityMainMount");
      if (targetMount && utilityBar.parentElement !== targetMount) {
        targetMount.appendChild(utilityBar);
      }
      if (targetMainMount && utilityMainRow.parentElement !== targetMainMount) {
        targetMainMount.appendChild(utilityMainRow);
      }
    }

    function syncShellUtilityRowSizing() {
      const utilityRowSelectors = ["appSessionRoleTag", "appLogoutBtn"];
      if (document.body?.dataset?.shellDensity === "compact") return;
      utilityRowSelectors.forEach((id) => {
        const el = $(id);
        if (!el) return;
        const iconOnlySessionPill = id === "appSessionRoleTag" || id === "appLogoutBtn";
        if (iconOnlySessionPill) {
          el.style.width = "26px";
          el.style.minWidth = "26px";
          el.style.minHeight = "26px";
          el.style.padding = "0";
          el.style.fontSize = "0";
          el.style.lineHeight = "0";
          return;
        }
        el.style.minHeight = "26px";
        el.style.padding = "4px 9px";
        el.style.fontSize = "0.84rem";
        el.style.fontWeight = "700";
        el.style.lineHeight = "1.2";
      });
    }

    function resetReadOnlyShellState() {
      resetDashboardSlotSelection();
      resetDashboardUnassignedSelection();
      resetDashboardSearchSelection();
      resetDashboardDragState();
      renderDashboardSlotItems(getDashboardSlotRow(homeDashboardSelectedSlotCode));
      renderDashboardCabinetDetail();
      renderDashboardWorkbench();
    }

    function focusOpsHomeSearchInput() {
      const input = $("operatorLookupQuery");
      if (!input || currentShellMode() !== "ops") return;
      requestAnimationFrame(() => {
        if (currentShellMode() !== "ops") return;
        input.focus();
        input.select();
      });
    }

    function updateShellRoute(mode, options = {}) {
      const nextPath = shellRoutePath(mode, options);
      if (currentAppRouteKey() === nextPath) return;
      if (options.pushHistory === false && options.replaceHistory !== true) return;
      if (options.replaceHistory === true) {
        window.history.replaceState({}, "", nextPath);
        return;
      }
      window.history.pushState({}, "", nextPath);
    }
    function applyShellNavigation(session) {
      const authenticated = Boolean(session?.authenticated);
      const isAdmin = isAdminSession(session);
      const mode = currentShellMode();
      setTextIfPresent("tabSimpleBtn", t("nav.ops_home"));
      setTextIfPresent("shellCabinetsBtn", t("nav.cabinets"));
      placeShellUtilityBar(mode);
      setDisplayIfPresent("appHero", authenticated && isAdmin && mode === "admin" ? "block" : "none");
      setDisplayIfPresent("opsHomeHero", authenticated && mode !== "admin" ? "grid" : "none");
      setDisplayIfPresent("shellTabs", authenticated ? "flex" : "none");
      setDisplayIfPresent("shellUtilityBar", authenticated ? "grid" : "none");
      setDisplayIfPresent("adminUtilityMainMount", authenticated && isAdmin && mode === "admin" ? "flex" : "none");
      setDisplayIfPresent("opsUtilityMainMount", authenticated && mode !== "admin" ? "flex" : "none");
      setDisplayIfPresent("tabSimpleBtn", authenticated ? "inline-flex" : "none");
      setDisplayIfPresent("shellCabinetsBtn", authenticated ? "inline-flex" : "none");
      setDisplayIfPresent("adminTabs", authenticated && isAdmin && mode === "admin" ? "flex" : "none");
      syncShellButtons();
      syncShellDensityClasses();
      syncShellUtilityRowSizing();
      syncShellReadonlyState();
    }

    function openAdminConsole(tab = "home", options = {}) {
      if (!isAdminSession()) return;
      const requestedTab = String(tab || "").trim();
      const requestedMediaMode = String(options.mediaMode || "").trim();
      let nextTab = "home";
      let nextMediaMode = mediaMode;
      if (["search", "manage", "register", "source"].includes(requestedTab)) {
        nextTab = "media";
        nextMediaMode = requestedTab;
      } else if (requestedTab === "goods") {
        nextTab = "collectibles";
      } else if (["home", "media", "collectibles", "ops", "cabinet", "logs"].includes(requestedTab)) {
        nextTab = requestedTab;
      }
      if (nextTab === "media" && ["search", "manage", "register", "source"].includes(requestedMediaMode)) {
        nextMediaMode = requestedMediaMode;
      }
      appShellMode = "admin";
      applyShellNavigation(appAuthSession);
      switchMainTab(nextTab, { remember: options.remember !== false });
      if (nextTab === "media") {
        switchMediaMode(nextMediaMode, { remember: options.remember !== false });
      }
      renderOperatorLookupResults();
      renderOperatorRequestList();
      updateShellRoute("admin", options);
    }

    function switchShellMode(mode, options = {}) {
      const nextMode = normalizeShellMode(mode, appAuthSession);
      appShellMode = nextMode;
      pendingOpsCabinetSelection = nextMode === "cabinets"
        ? (resolveCabinetRouteSelection(options.cabinetSelection) || pendingOpsCabinetSelection)
        : null;
      if (nextMode === "admin") {
        openAdminConsole(options.adminTab || "home", {
          remember: false,
          pushHistory: options.pushHistory,
          replaceHistory: options.replaceHistory,
        });
        return;
      }
      if (
        nextMode === "cabinets"
        && !pendingOpsCabinetSelection
        && !String(homeDashboardSelectedCabinetKey || "").trim()
      ) {
        homeDashboardSelectedCabinetKey = null;
        homeDashboardSelectedSlotCode = null;
        homeDashboardSlotItems = [];
        homeDashboardSlotItemsSlotCode = null;
        homeDashboardSlotItemsLoading = false;
        resetDashboardSlotPage();
      }
      applyShellNavigation(appAuthSession);
      switchMainTab(nextMode === "cabinets" ? "cabinet" : "simple", { remember: false });
      resetReadOnlyShellState();
      renderOperatorLookupResults();
      renderOperatorRequestList();
      updateShellRoute(nextMode, options);
      if (nextMode === "cabinets" && pendingOpsCabinetSelection && homeDashboardBySlot.length) {
        applyPendingOpsCabinetSelection({ silent: true }).catch(() => {});
      }
      if (nextMode === "ops") {
        if (appAuthSessionResolved && appAuthSession?.authenticated) {
          loadOperatorHomeRecentSections();
          if (!normalizeOpsLookupQuery($("operatorLookupQuery")?.value || "")) {
            loadOperatorHomeFeed({ kind: operatorFeedKind, page: operatorFeedPage });
          }
          loadOperatorWeather();
        }
        focusOpsHomeSearchInput();
      }
    }

    function switchMainTab(tab, options = {}) {
      const remember = options.remember !== false;
      const requestedTab = String(tab || "").trim();
      const adminParentTabs = ["home", "cabinet", "media", "collectibles", "ops", "logs"];
      let nextTab = requestedTab;
      let nextMediaMode = null;
      if (["search", "manage", "register", "source"].includes(requestedTab)) {
        nextTab = "media";
        nextMediaMode = requestedTab;
      } else if (requestedTab === "goods") {
        nextTab = "collectibles";
      }
      const tabs = [
        { id: "home", btn: "tabHomeBtn", panel: "tabHome" },
        { id: "simple", btn: "tabSimpleBtn", panel: "tabSimple" },
        { id: "cabinet", btn: "tabCabinetBtn", panel: "tabCabinet" },
        { id: "media", btn: "tabMediaBtn", panel: "tabMedia" },
        { id: "collectibles", btn: "tabCollectiblesBtn", panel: "tabCollectibles" },
        { id: "ops", btn: "tabOpsBtn", panel: "tabOps" },
        { id: "logs", btn: "tabLogsBtn", panel: "tabLogs" }
      ];
      for (const t of tabs) {
        const active = t.id === nextTab;
        const btn = $(t.btn);
        const panel = $(t.panel);
        if (!btn || !panel) continue;
        btn.classList.toggle("active", active);
        panel.classList.toggle("active", active);
      }
      if (remember) {
        saveRoleScopedValue(APP_MAIN_TAB_MEMORY_KEY, nextTab);
      }
      if (nextTab === "home") { setTimeout(() => { if (typeof initDashboardWidgetDragDrop === "function") initDashboardWidgetDragDrop(); }, 500); }
      if (nextTab === "camera" && appAuthSessionResolved && appAuthSession?.authenticated) {
        loadOpsCameras({ silent: true });
      }
      if (nextTab === "cabinet" && appAuthSessionResolved && appAuthSession?.authenticated) {
        if (typeof renderDashboardHeroStats === "function") renderDashboardHeroStats();
        if (typeof renderDashboardSlotOccupancy === "function") renderDashboardSlotOccupancy();
        if (typeof loadDashboardWorkbench === "function") loadDashboardWorkbench({ silent: true });
      }
      if (nextTab === "media") {
        if (nextMediaMode) mediaMode = nextMediaMode;
        syncMediaModeUi();
      } else {
        syncMediaModeUi();
      }
      if (nextTab === "collectibles") {
        syncGoodsModeUi();
        if (!goodsSearchLoading && !goodsSearchResults.length) {
          loadGoodsSearchResults({ silent: true }).catch(() => {});
        }
      }
      syncShellDensityClasses();
    }

    function switchSubTab(group, tab, options = {}) {
      const remember = options.remember !== false;
      const groups = {
        register: [
          { id: "collect", btn: "registerCollectTabBtn", panel: "registerCollectPanel" },
          { id: "purchase", btn: "registerPurchaseTabBtn", panel: "registerPurchasePanel" },
          { id: "batch", btn: "registerBatchTabBtn", panel: "registerBatchPanel" },
          { id: "master", btn: "registerMasterTabBtn", panel: "registerMasterPanel" },
          { id: "track", btn: "registerTrackTabBtn", panel: "registerTrackPanel" },
        ],
        ops: [
          { id: "cabinet", btn: "opsCabinetTabBtn", panel: "opsCabinetPanel" },
          { id: "camera", btn: "opsCameraTabBtn", panel: "opsCameraPanel" },
          { id: "slot", btn: "opsSlotTabBtn", panel: "opsSlotPanel" },
          { id: "exception", btn: "opsExceptionTabBtn", panel: "opsExceptionPanel" },
          { id: "account", btn: "opsAccountTabBtn", panel: "opsAccountPanel" },
          { id: "permissions", btn: "opsPermissionsTabBtn", panel: "opsPermissionsPanel" },
          { id: "activity", btn: "opsActivityTabBtn", panel: "opsActivityPanel" },
          { id: "providers", btn: "opsProviderTabBtn", panel: "opsProviderPanel" },
          { id: "export", btn: "opsExportTabBtn", panel: "opsExportPanel" },
          { id: "metasync", btn: "opsMetaSyncTabBtn", panel: "opsMetaSyncPanel" },
        ],
        logs: [
          { id: "err", btn: "logErrTabBtn", panel: "logErrPanel" },
          { id: "audit", btn: "logAuditTabBtn", panel: "logAuditPanel" },
          { id: "perf", btn: "logPerfTabBtn", panel: "logPerfPanel" },
          { id: "loc", btn: "logLocTabBtn", panel: "logLocPanel" },
          { id: "srv", btn: "logSrvTabBtn", panel: "logSrvPanel" },
        ],
      };
      const tabs = groups[group];
      if (!tabs) return;
      for (const item of tabs) {
        const active = item.id === tab;
        const btn = $(item.btn);
        const panel = $(item.panel);
        if (!btn || !panel) continue;
        btn.classList.toggle("active", active);
        panel.classList.toggle("active", active);
      }
      if (remember) {
        saveRoleScopedValue(APP_SUBTAB_MEMORY_KEY, `${group}:${tab}`);
      }
    }

    function switchMediaMode(mode, options = {}) {
      const nextMode = ["search", "manage", "register", "source"].includes(String(mode || "").trim())
        ? String(mode || "").trim()
        : "search";
      mediaMode = nextMode;
      syncMediaModeUi();
      if (options.remember !== false) {
        saveRoleScopedValue(APP_SUBTAB_MEMORY_KEY, `media:${nextMode}`);
      }
    }

    function syncMediaModeUi() {
      const items = [
        { id: "search", btn: "mediaSearchModeBtn", panel: "tabSearch" },
        { id: "manage", btn: "mediaManageModeBtn", panel: "tabManage" },
        { id: "register", btn: "mediaRegisterModeBtn", panel: "tabRegister" },
        { id: "source", btn: "mediaSourceModeBtn", panel: "tabSource" },
      ];
      const mediaActive = $("tabMedia")?.classList.contains("active");
      for (const item of items) {
        const active = mediaActive && item.id === mediaMode;
        $(item.btn)?.classList.toggle("active", active);
        $(item.panel)?.classList.toggle("active", active);
      }
    }

    function applyRouteSelectedShellMode(mode) {
      const resolvedMode = normalizeShellMode(mode, appAuthSession);
      const cabinetSelection = resolvedMode === "cabinets" ? cabinetRouteSelectionFromLocation() : null;
      switchShellMode(mode, {
        remember: false,
        pushHistory: false,
        adminTab: "home",
        cabinetSelection,
      });
      if (appAuthSessionResolved) {
        updateShellRoute(resolvedMode, { replaceHistory: true, cabinetSelection });
      }
    }
