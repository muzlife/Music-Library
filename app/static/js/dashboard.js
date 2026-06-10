    let dashboardDraggedOwnedItemId = null;
    let dashboardDraggedSelectionIds = [];
    let dashboardDraggedSlotCode = null;
    let dashboardDraggedSizeGroup = null;
    let dashboardDraggedTitle = null;
    let dashboardPointerSelectionState = null;
    let dashboardPointerSelectionPreviewIds = [];
    let dashboardPointerSelectionSuppressClickUntil = 0;

    function dashboardMoveKindLabel(value) {
      const code = String(value || "").trim().toUpperCase();
      if (code === "INITIAL_ASSIGN") return t("common.movement.initial_assign");
      if (code === "ASSIGN") return t("common.movement.assign");
      if (code === "MOVE") return t("common.movement.move");
      if (code === "UNASSIGN") return t("common.movement.unassign");
      if (code === "CABINET_DELETE") return t("common.movement.cabinet_delete");
      return code || "-";
    }

    function dashboardMoveKindClass(value) {
      const code = String(value || "").trim().toUpperCase();
      if (code === "INITIAL_ASSIGN") return "initial";
      if (code === "ASSIGN") return "assign";
      if (code === "MOVE") return "move";
      if (code === "UNASSIGN") return "unassign";
      if (code === "CABINET_DELETE") return "cabinet-delete";
      return "";
    }

    function dashboardMoveDisplayKind(row) {
      const note = String(row?.note || "").trim();
      if (note === "직전 위치 복구") {
        return { label: t("common.movement.restore"), className: "restore" };
      }
      return {
        label: dashboardMoveKindLabel(row?.movement_kind),
        className: dashboardMoveKindClass(row?.movement_kind),
      };
    }

    function dashboardDomainLabel(value) {
      const code = String(value || "").trim().toUpperCase();
      if (code === "KOREA") return t("common.domain.korea");
      if (code === "JAPAN") return t("common.domain.japan");
      if (code === "GREATER_CHINA") return t("common.domain.greater_china");
      if (code === "WESTERN") return t("common.domain.western");
      if (code === "OTHER_ASIA") return t("common.domain.other_asia");
      if (code === "WORLD") return t("common.domain.world");
      if (code === "UNKNOWN") return t("common.domain.unknown");
      if (code === "UNASSIGNED") return t("common.unspecified");
      return code || "-";
    }

    function dashboardUnnamedCabinetLabel() {
      return t("dashboard.cabinet.unnamed");
    }

    function dashboardUnassignedAssetsLabel() {
      return t("dashboard.workbench.unslotted_assets");
    }

    function dashboardConnectedCabinetsLabel(count) {
      return t("dashboard.cabinet.meta.connected_short", { count: formatCount(count) });
    }

    function dashboardFloorsLabel(count) {
      return t("dashboard.cabinet.meta.floors", { count: formatCount(count) });
    }

    function dashboardCellCountLabel(count) {
      const safeCount = formatCount(count);
      if (appLocale === "en") return `${safeCount} cells`;
      if (appLocale === "ja") return `${safeCount}段`;
      return `${safeCount}칸`;
    }

    function dashboardMaxCellsLabel(count) {
      return t("dashboard.cabinet.meta.max_cells", { count: formatCount(count) });
    }

    function dashboardSlotsLabel(count) {
      return t("dashboard.cabinet.meta.slots", { count: formatCount(count) });
    }

    function dashboardUsedSlotsLabel(count) {
      return t("dashboard.cabinet.meta.used_slots", { count: formatCount(count) });
    }

    function dashboardStoredItemsLabel(count) {
      return t("dashboard.cabinet.meta.stored_items", { count: countWithUnit(count) });
    }

    function dashboardDomainMetaLabel(value) {
      return t("dashboard.cabinet.meta.domain", { value });
    }

    function dashboardSizeGroupMetaLabel(value) {
      return t("dashboard.cabinet.meta.size_group", { value });
    }

    function dashboardSelectionPositionNumber(index) {
      return t("dashboard.selection.position_number", { index });
    }

    function dashboardSelectionToggleLabel(checked, short = false) {
      if (short) {
        return checked
          ? t("dashboard.selection.action.deselect_short")
          : t("dashboard.selection.action.select_short");
      }
      return checked
        ? t("dashboard.selection.action.deselect")
        : t("dashboard.selection.action.select");
    }

    function dashboardEditItemLabel() {
      return t("media.manage.search.action.open_detail_manage");
    }

    function dashboardColumnCodeLabel(code) {
      const text = String(code || "").trim();
      if (!text) return "";
      if (appLocale === "en") return `Col ${text}`;
      if (appLocale === "ja") return `${text}列`;
      return `${text}열`;
    }

    function dashboardCellCodeLabel(code) {
      const text = String(code || "").trim();
      if (!text) return "";
      if (appLocale === "en") return `Cell ${text}`;
      if (appLocale === "ja") return `${text}段`;
      return `${text}칸`;
    }

    function formatDashboardFloorSummaryLines(summaryText) {
      const source = String(summaryText || "").trim();
      if (!source || source === "-") return [];
      const parts = source.split(" / ").map((part) => part.trim()).filter((part) => part);
      if (parts.length <= 2) return [parts.join(" / ")];
      const midpoint = Math.ceil(parts.length / 2);
      return [
        parts.slice(0, midpoint).join(" / "),
        parts.slice(midpoint).join(" / "),
      ].filter((line) => line);
    }

    function dashboardReleaseTypeLabel(value) {
      const code = String(value || "").trim().toUpperCase();
      if (code === "ALBUM") return t("common.release_type.album");
      if (code === "EP") return "EP";
      if (code === "SINGLE") return t("common.release_type.single");
      if (code === "UNASSIGNED") return t("common.unspecified");
      return code || "-";
    }

    function dashboardSizeGroupLabel(value) {
      const code = String(value || "").trim().toUpperCase();
      if (code === "STD") return t("common.size_group.std");
      if (code === "BOOK") return t("common.size_group.book");
      if (code === "LP") return t("common.size_group.lp");
      if (code === "LP10") return t("common.size_group.lp10");
      if (code === "LP7") return t("common.size_group.lp7");
      if (code === "OVERSIZE") return t("common.size_group.oversize");
      if (code === "CASSETTE") return t("common.size_group.cassette");
      if (code === "8TRACK") return "8-track";
      if (code === "REEL_TO_REEL") return "Reel-to-reel";
      if (code === "GOODS") return t("common.size_group.goods");
      if (code === "UNASSIGNED") return t("common.unspecified");
      return code || "-";
    }

    function dashboardSourceLabel(value) {
      const code = String(value || "").trim().toUpperCase();
      if (!code || code === "MANUAL") return t("common.source.manual");
      if (code === "DISCOGS") return "Discogs";
      if (code === "MANIADB") return "ManiaDB";
      if (code === "ALADIN") return "Aladin";
      return code;
    }

    function dashboardStatusLabel(value) {
      const code = String(value || "").trim().toUpperCase();
      if (code === "IN_COLLECTION") return t("common.status.in_collection");
      if (code === "LOANED") return t("common.status.loaned");
      if (code === "SOLD") return t("common.status.sold");
      if (code === "LOST") return t("common.status.lost");
      if (code === "ARCHIVED") return t("common.status.archived");
      return code || "-";
    }

    function dashboardCabinetKey(row) {
      const slotCode = String(row?.slot_code || "").trim();
      if (slotCode === "UNASSIGNED") return "__UNASSIGNED__";
      if (row?.is_overflow_zone) return "__OVERFLOW__";
      const cabinetGroupName = String(row?.cabinet_group_name || "").trim();
      if (cabinetGroupName) return `GROUP:${cabinetGroupName}`;
      const cabinetName = String(row?.cabinet_name || "").trim() || dashboardUnnamedCabinetLabel();
      return `CABINET:${cabinetName}`;
    }

    function getStorageSlotById(slotId) {
      const id = Number(slotId || 0);
      if (id <= 0) return null;
      return storageSlotCache.find((item) => Number(item?.id || 0) === id) || null;
    }

    function updateDashboardMasterSortArtistNameLocally(masterId, sortArtistName) {
      const normalizedMasterId = Number(masterId || 0);
      const normalizedSortArtistName = String(sortArtistName || "").trim() || null;
      if (normalizedMasterId <= 0) return;
      const pools = [
        homeDashboardSlotItems,
        homeDashboardSlotSelectionSnapshot,
        homeDashboardUnassignedItems,
        homeDashboardSearchItems,
      ];
      for (const pool of pools) {
        if (!Array.isArray(pool)) continue;
        for (const row of pool) {
          if (Number(row?.linked_album_master_id || row?.album_master_id || 0) !== normalizedMasterId) continue;
          row.master_sort_artist_name = normalizedSortArtistName;
        }
      }
    }

    function getSlotMismatchRows(items, targetSlot) {
      const targetSizeGroup = String(targetSlot?.allowed_size_group || "").trim();
      if (!targetSizeGroup) return [];
      return (Array.isArray(items) ? items : []).filter((row) => {
        const sizeGroup = ownedPreferredStorageSizeGroup(row);
        return Boolean(sizeGroup) && sizeGroup !== targetSizeGroup;
      });
    }

    function dashboardPointerSelectionConfig(scope) {
      const nextScope = String(scope || "").trim().toUpperCase() === "WORKBENCH" ? "WORKBENCH" : "SLOT";
      const root = nextScope === "WORKBENCH" ? $("homeDashWorkbenchList") : $("homeDashSlotItems");
      const overlay = nextScope === "WORKBENCH" ? $("homeDashWorkbenchSelectionBox") : $("homeDashSlotSelectionBox");
      const surface = root?.closest(".dashboard-slot-rack-surface");
      return { scope: nextScope, root, overlay, surface };
    }

    function startDashboardPointerSelection(e, scope) {
      if (isShellReadOnly() || !e || e.button !== 0) return;
      const config = dashboardPointerSelectionConfig(scope);
      if (!config.root || !config.overlay || !config.surface) return;
      dashboardPointerSelectionState = {
        scope: config.scope,
        pointerId: Number(e.pointerId || 0),
        root: config.root,
        overlay: config.overlay,
        surface: config.surface,
        startX: Number(e.clientX || 0),
        startY: Number(e.clientY || 0),
        currentX: Number(e.clientX || 0),
        currentY: Number(e.clientY || 0),
        currentRect: {
          left: Number(e.clientX || 0),
          right: Number(e.clientX || 0),
          top: Number(e.clientY || 0),
          bottom: Number(e.clientY || 0),
        },
        didMove: false,
      };
      clearDashboardPointerSelectionVisuals();
      try {
        config.root.setPointerCapture?.(e.pointerId);
      } catch (_) {}
      e.preventDefault();
    }

    function updateDashboardPointerSelection(clientX, clientY) {
      const state = dashboardPointerSelectionState;
      if (!state?.root || !state?.overlay || !state?.surface) return;
      state.currentX = Number(clientX || 0);
      state.currentY = Number(clientY || 0);
      const label = state.scope === "WORKBENCH"
        ? $("homeDashWorkbenchSelectionBoxLabel")
        : $("homeDashSlotSelectionBoxLabel");
      const rootRect = state.root.getBoundingClientRect();
      const surfaceRect = state.surface.getBoundingClientRect();
      const rawLeft = Math.min(state.startX, state.currentX);
      const rawRight = Math.max(state.startX, state.currentX);
      const rawTop = Math.min(state.startY, state.currentY);
      const rawBottom = Math.max(state.startY, state.currentY);
      const left = Math.max(rootRect.left, Math.min(rawLeft, rootRect.right));
      const right = Math.max(rootRect.left, Math.min(rawRight, rootRect.right));
      const top = Math.max(rootRect.top, Math.min(rawTop, rootRect.bottom));
      const bottom = Math.max(rootRect.top, Math.min(rawBottom, rootRect.bottom));
      const nextRect = { left, right, top, bottom };
      const width = Math.max(0, right - left);
      const height = Math.max(0, bottom - top);
      const movedEnough = width >= 6 || height >= 6;
      state.didMove = state.didMove || movedEnough;
      state.currentRect = nextRect;
      if (!state.didMove) {
        clearDashboardPointerSelectionVisuals();
        return;
      }
      state.overlay.hidden = false;
      state.overlay.style.left = `${Math.max(0, left - surfaceRect.left)}px`;
      state.overlay.style.top = `${Math.max(0, top - surfaceRect.top)}px`;
      state.overlay.style.width = `${width}px`;
      state.overlay.style.height = `${height}px`;
      const previewIds = [];
      state.root.querySelectorAll("[data-dashboard-selectable-id]").forEach((node) => {
        const nodeRect = node.getBoundingClientRect();
        const overlaps = nodeRect.right >= left
          && nodeRect.left <= right
          && nodeRect.bottom >= top
          && nodeRect.top <= bottom;
        node.classList.toggle("dashboard-selection-preview", overlaps);
        if (overlaps) {
          const ownedItemId = Number(node.getAttribute("data-dashboard-selectable-id") || 0);
          if (ownedItemId > 0) previewIds.push(ownedItemId);
        }
      });
      dashboardPointerSelectionPreviewIds = previewIds;
      if (label) {
        const isDeselectMode = nextRect.left < state.startX;
        if (previewIds.length > 0) {
          label.hidden = false;
          label.textContent = isDeselectMode
            ? t("dashboard.selection.preview.remove", { count: countWithUnit(previewIds.length) })
            : t("dashboard.selection.preview.add", { count: countWithUnit(previewIds.length) });
        } else {
          label.hidden = true;
          label.textContent = "";
        }
      }
      renderDashboardSelectionSummary();
    }

    function cancelDashboardPointerSelection() {
      const state = dashboardPointerSelectionState;
      if (!state) {
        clearDashboardPointerSelectionVisuals();
        return;
      }
      try {
        state.root?.releasePointerCapture?.(state.pointerId);
      } catch (_) {}
      dashboardPointerSelectionState = null;
      clearDashboardPointerSelectionVisuals();
      renderDashboardSelectionSummary();
    }

    function dashboardSlotGridMode(slotRow) {
      const code = String(slotRow?.allowed_size_group || "").trim().toUpperCase();
      if (code === "LP" || code === "LP10" || code === "LP7" || code === "OVERSIZE") return "LP";
      return "DEFAULT";
    }

    function dashboardSlotSupportsPaging() {
      return homeDashboardSlotViewMode === "THUMB";
    }

    function dashboardSlotUsesShelfScroll() {
      return homeDashboardSlotViewMode === "SHELF";
    }

    function syncDashboardSlotViewButtons() {
      $("homeDashSlotViewShelfBtn")?.classList.toggle("active", homeDashboardSlotViewMode === "SHELF");
      $("homeDashSlotViewThumbBtn")?.classList.toggle("active", homeDashboardSlotViewMode === "THUMB");
      $("homeDashSlotViewListBtn")?.classList.toggle("active", homeDashboardSlotViewMode === "LIST");
    }

    function applyDashboardSlotViewMode(root, slotRow) {
      if (!root) return;
      root.classList.remove(
        "dashboard-cabinet-overview-grid",
        "dashboard-slot-pagegrid",
        "dashboard-slot-pagegrid--lp",
        "dashboard-slot-listview",
        "dashboard-slot-shelfview",
        "dashboard-slot-shelfview--lp",
      );
      if (homeDashboardSlotViewMode === "LIST") {
        root.classList.add("dashboard-slot-listview");
        return;
      }
      if (homeDashboardSlotViewMode === "SHELF") {
        root.classList.add("dashboard-slot-shelfview");
        if (dashboardSlotGridMode(slotRow) === "LP") root.classList.add("dashboard-slot-shelfview--lp");
        return;
      }
      root.classList.add("dashboard-slot-pagegrid");
      if (dashboardSlotGridMode(slotRow) === "LP") {
        root.classList.add("dashboard-slot-pagegrid--lp");
      }
    }

    function dashboardSlotPageSize(slotRow) {
      if (!dashboardSlotSupportsPaging()) return Number.MAX_SAFE_INTEGER;
      const override = Number(homeDashboardSlotPageSizeOverride || 0);
      if (override > 0) return override;
      const code = String(slotRow?.allowed_size_group || "").trim().toUpperCase();
      if (homeDashboardSlotViewMode === "SHELF") {
        if (code === "LP" || code === "LP10" || code === "LP7" || code === "OVERSIZE") return 15;
        if (code === "BOOK") return 18;
        return 20;
      }
      if (code === "LP" || code === "LP10" || code === "LP7" || code === "OVERSIZE") return 12;
      if (code === "BOOK") return 15;
      return 18;
    }

    function dashboardSlotPageSlice(items, slotRow) {
      const list = Array.isArray(items) ? items : [];
      if (!dashboardSlotSupportsPaging()) {
        return {
          items: list,
          pageSize: Math.max(1, list.length || 1),
          pageCount: 1,
          page: 0,
          start: 0,
          end: list.length,
          total: list.length,
        };
      }
      const pageSize = Math.max(1, dashboardSlotPageSize(slotRow));
      const pageCount = Math.max(1, Math.ceil(list.length / pageSize));
      const nextPage = Math.min(Math.max(0, homeDashboardSlotPage), pageCount - 1);
      homeDashboardSlotPage = nextPage;
      const start = nextPage * pageSize;
      const end = Math.min(list.length, start + pageSize);
      return {
        items: list.slice(start, end),
        pageSize,
        pageCount,
        page: nextPage,
        start,
        end,
        total: list.length,
      };
    }

    function dashboardShelfVisibleRange(root, total) {
      const container = root || $("homeDashSlotItems");
      const itemTotal = Math.max(0, Number(total || 0));
      if (!container || itemTotal <= 0) {
        return { start: 0, end: 0, total: itemTotal };
      }
      const nodes = Array.from(container.querySelectorAll(".dashboard-slot-shelfcard"));
      if (!nodes.length) {
        return { start: 0, end: 0, total: itemTotal };
      }
      const viewportLeft = Number(container.scrollLeft || 0);
      const viewportRight = viewportLeft + Number(container.clientWidth || 0);
      let firstIndex = -1;
      let lastIndex = -1;
      nodes.forEach((node, idx) => {
        const left = Number(node.offsetLeft || 0);
        const right = left + Number(node.offsetWidth || 0);
        if (right >= viewportLeft + 8 && left <= viewportRight - 8) {
          if (firstIndex < 0) firstIndex = idx;
          lastIndex = idx;
        }
      });
      if (firstIndex < 0) {
        firstIndex = 0;
        lastIndex = Math.min(nodes.length - 1, 0);
      }
      return {
        start: firstIndex + 1,
        end: Math.max(firstIndex + 1, lastIndex + 1),
        total: itemTotal,
      };
    }

    function applyDashboardShelfNeighborHighlight(root) {
      const container = root || $("homeDashSlotItems");
      if (!container) return;
      container.querySelectorAll(".dashboard-slot-shelfcard.near-pick").forEach((node) => node.classList.remove("near-pick"));
    }

    function updateDashboardSlotPageControls(sliceInfo) {
      const prevBtn = $("homeDashSlotPagePrevBtn");
      const nextBtn = $("homeDashSlotPageNextBtn");
      const info = $("homeDashSlotPageInfo");
      const shelfRoot = $("homeDashSlotItems");
      const total = Number(sliceInfo?.total || 0);
      const pageCount = Math.max(1, Number(sliceInfo?.pageCount || 1));
      const page = Math.max(0, Number(sliceInfo?.page || 0));
      const start = total > 0 ? Number(sliceInfo?.start || 0) + 1 : 0;
      const end = total > 0 ? Number(sliceInfo?.end || 0) : 0;
      const pagingEnabled = dashboardSlotSupportsPaging();
      const shelfScrollEnabled = dashboardSlotUsesShelfScroll();
      if (shelfScrollEnabled) {
        const maxScrollLeft = Math.max(0, Number((shelfRoot?.scrollWidth || 0) - (shelfRoot?.clientWidth || 0)));
        const scrollLeft = Math.max(0, Number(shelfRoot?.scrollLeft || homeDashboardSlotShelfScrollLeft || 0));
        if (info) {
          const visible = dashboardShelfVisibleRange(shelfRoot, total);
          info.textContent = total > 0
            ? t("dashboard.cover_flow.meta.current_range", {
              start: visible.start,
              end: visible.end,
              total: formatCount(total),
            })
            : "0 / 0";
        }
        if (prevBtn) prevBtn.disabled = total <= 0 || scrollLeft <= 2;
        if (nextBtn) nextBtn.disabled = total <= 0 || scrollLeft >= maxScrollLeft - 2;
        syncDashboardSlotViewButtons();
        return;
      }
      if (info) {
        info.textContent = pagingEnabled
          ? (total > 0 ? t("dashboard.cover_flow.meta.current_range", {
            start,
            end,
            total: formatCount(total),
          }) : "0 / 0")
          : t("dashboard.cover_flow.meta.all_count", { count: countWithUnit(total) });
      }
      if (prevBtn) prevBtn.disabled = !pagingEnabled || page <= 0 || total <= 0;
      if (nextBtn) nextBtn.disabled = !pagingEnabled || total <= 0 || page >= pageCount - 1;
      syncDashboardSlotViewButtons();
    }

    function moveDashboardShelfViewport(direction) {
      const root = $("homeDashSlotItems");
      if (!root || !dashboardSlotUsesShelfScroll()) return;
      const delta = Math.max(120, Math.floor(root.clientWidth * 0.84));
      const nextLeft = Math.max(0, root.scrollLeft + (direction === "PREV" ? -delta : delta));
      root.scrollTo({ left: nextLeft, behavior: "smooth" });
      window.setTimeout(() => {
        homeDashboardSlotShelfScrollLeft = root.scrollLeft;
        updateDashboardSlotPageControls({
          total: Array.isArray(homeDashboardSlotItems) ? homeDashboardSlotItems.length : 0,
        });
      }, 160);
    }

    function dashboardSlotMediaFilterValue() {
      return String($("homeDashSlotMediaFilter")?.value || "ANY").trim().toUpperCase() || "ANY";
    }

    function dashboardSlotSortModeValue() {
      return String($("homeDashSlotSortMode")?.value || "NAME_ASC").trim().toUpperCase() || "NAME_ASC";
    }

    function normalizeArtistSortKey(text) {
      const v = String(text || "").trim().replace(/\s+/g, " ").toLocaleLowerCase();
      return v.replace(/^(the|an?)\s+(.+)$/, "$2, $1");
    }

    function normalizeTitleSortKey(text) {
      const v = String(text || "").trim().replace(/\s+/g, " ").toLocaleLowerCase();
      return v.replace(/^(the|an?)\s+(.+)$/, "$2, $1");
    }

    function normalizeDashboardReleaseSortValue(value) {
      const text = String(value || "").trim();
      if (!text) return "";
      if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
      if (/^\d{4}-\d{2}$/.test(text)) return `${text}-00`;
      if (/^\d{4}$/.test(text)) return `${text}-00-00`;
      return text;
    }

    function dashboardPreferredReleaseSortValue(row) {
      const masterRelease = normalizeDashboardReleaseSortValue(row?.master_release_date || row?.master_release_year || "");
      const itemRelease = normalizeDashboardReleaseSortValue(row?.released_date || row?.release_year || "");
      const candidates = [masterRelease, itemRelease].filter(Boolean).sort();
      return candidates[0] || "9999-99-99";
    }

    function dashboardWorkbenchPageSlice(items, slotRow) {
      const list = Array.isArray(items) ? items : [];
      if (!dashboardSlotSupportsPaging()) {
        return {
          items: list,
          pageSize: Math.max(1, list.length || 1),
          pageCount: 1,
          page: 0,
          start: 0,
          end: list.length,
          total: list.length,
        };
      }
      const pageSize = Math.max(1, dashboardSlotPageSize(slotRow));
      const pageCount = Math.max(1, Math.ceil(list.length / pageSize));
      const nextPage = Math.min(Math.max(0, homeDashboardWorkbenchPage), pageCount - 1);
      homeDashboardWorkbenchPage = nextPage;
      const start = nextPage * pageSize;
      const end = Math.min(list.length, start + pageSize);
      return {
        items: list.slice(start, end),
        pageSize,
        pageCount,
        page: nextPage,
        start,
        end,
        total: list.length,
      };
    }

    function updateDashboardWorkbenchPageControls(sliceInfo) {
      const prevBtn = $("homeDashWorkbenchPagePrevBtn");
      const nextBtn = $("homeDashWorkbenchPageNextBtn");
      const info = $("homeDashWorkbenchPageInfo");
      const shelfRoot = $("homeDashWorkbenchList");
      const total = Number(sliceInfo?.total || 0);
      const pageCount = Math.max(1, Number(sliceInfo?.pageCount || 1));
      const page = Math.max(0, Number(sliceInfo?.page || 0));
      const start = total > 0 ? Number(sliceInfo?.start || 0) + 1 : 0;
      const end = total > 0 ? Number(sliceInfo?.end || 0) : 0;
      const pagingEnabled = dashboardSlotSupportsPaging();
      const shelfScrollEnabled = dashboardSlotUsesShelfScroll();
      if (shelfScrollEnabled) {
        const maxScrollLeft = Math.max(0, Number((shelfRoot?.scrollWidth || 0) - (shelfRoot?.clientWidth || 0)));
        const scrollLeft = Math.max(0, Number(shelfRoot?.scrollLeft || homeDashboardWorkbenchShelfScrollLeft || 0));
        if (info) {
          const visible = dashboardShelfVisibleRange(shelfRoot, total);
          info.textContent = total > 0
            ? t("dashboard.cover_flow.meta.current_range", {
              start: visible.start,
              end: visible.end,
              total: formatCount(total),
            })
            : "0 / 0";
        }
        if (prevBtn) prevBtn.disabled = total <= 0 || scrollLeft <= 2;
        if (nextBtn) nextBtn.disabled = total <= 0 || scrollLeft >= maxScrollLeft - 2;
        return;
      }
      if (info) {
        info.textContent = pagingEnabled
          ? (total > 0 ? t("dashboard.cover_flow.meta.current_range", {
            start,
            end,
            total: formatCount(total),
          }) : "0 / 0")
          : t("dashboard.cover_flow.meta.all_count", { count: countWithUnit(total) });
      }
      if (prevBtn) prevBtn.disabled = !pagingEnabled || page <= 0 || total <= 0;
      if (nextBtn) nextBtn.disabled = !pagingEnabled || total <= 0 || page >= pageCount - 1;
    }

    function moveDashboardWorkbenchViewport(direction) {
      const root = $("homeDashWorkbenchList");
      if (!root || !dashboardSlotUsesShelfScroll()) return;
      const delta = Math.max(120, Math.floor(root.clientWidth * 0.84));
      const nextLeft = Math.max(0, root.scrollLeft + (direction === "PREV" ? -delta : delta));
      root.scrollTo({ left: nextLeft, behavior: "smooth" });
      window.setTimeout(() => {
        homeDashboardWorkbenchShelfScrollLeft = root.scrollLeft;
        updateDashboardWorkbenchPageControls({
          total: getDashboardWorkbenchRows().length,
        });
      }, 160);
    }

    function getDashboardWorkbenchRows() {
      if (homeDashboardWorkbenchMode === "SEARCH") {
        return sortDashboardWorkbenchItems(filterDashboardWorkbenchItemsByMedia(homeDashboardSearchItems));
      }
      return sortDashboardWorkbenchItems(filterDashboardWorkbenchItemsByMedia(homeDashboardUnassignedItems));
    }

    function getDashboardWorkbenchSelectedIds() {
      const visibleIds = new Set(
        getDashboardWorkbenchRows()
          .map((row) => Number(row?.id || 0))
          .filter((ownedItemId) => ownedItemId > 0)
      );
      const rawSelectedIds = homeDashboardWorkbenchMode === "SEARCH"
        ? homeDashboardSearchSelectedIds
        : homeDashboardUnassignedSelectedIds;
      return new Set(
        Array.from(rawSelectedIds)
          .map((ownedItemId) => Number(ownedItemId || 0))
          .filter((ownedItemId) => ownedItemId > 0 && visibleIds.has(ownedItemId))
      );
    }

    function getDashboardSelectionSourceKind() {
      if (homeDashboardSlotSelectedIds.size > 0) return "SLOT";
      if (homeDashboardWorkbenchMode === "SEARCH" && getDashboardWorkbenchSelectedIds().size > 0) return "SEARCH";
      if (homeDashboardWorkbenchMode === "UNASSIGNED" && getDashboardWorkbenchSelectedIds().size > 0) return "UNASSIGNED";
      return "NONE";
    }

    function isDashboardClickMoveModeActive() {
      return !isShellReadOnly() && homeDashboardClickMoveMode && getDashboardSelectionSourceKind() !== "NONE";
    }

    function startDashboardClickMoveMode() {
      if (getDashboardSelectionSourceKind() === "NONE") {
        setStatus("homeDashboardStatus", "err", t("dashboard.selection.status.move_mode_requires_selection"));
        return;
      }
      homeDashboardClickMoveMode = true;
      renderDashboardSelectionSummary();
      setStatus("homeDashboardStatus", "ok", t("dashboard.selection.status.move_mode_started"));
    }

    function cancelDashboardClickMoveMode(options = {}) {
      const wasActive = homeDashboardClickMoveMode;
      homeDashboardClickMoveMode = false;
      if (options.render !== false) {
        renderDashboardSelectionSummary();
      }
      if (!options.silent && wasActive) {
        setStatus("homeDashboardStatus", "ok", t("dashboard.selection.status.move_mode_cancelled"));
      }
    }

    function updateDashboardSlotSelectionSnapshot() {
      homeDashboardSlotSelectionSnapshot = (Array.isArray(homeDashboardSlotItems) ? homeDashboardSlotItems : [])
        .filter((row) => homeDashboardSlotSelectedIds.has(Number(row?.id || 0)));
    }

    function dashboardSlotIndexHintForRow(targetRow) {
      const selectedId = Number(targetRow?.id || 0);
      if (!selectedId) return "";
      const currentRows = Array.isArray(homeDashboardSlotItems) ? homeDashboardSlotItems : [];
      const currentIdx = currentRows.findIndex((row) => Number(row?.id || 0) === selectedId);
      if (currentIdx >= 0) return dashboardSelectionPositionNumber(currentIdx + 1);
      const snapshotRows = Array.isArray(homeDashboardSlotSelectionSnapshot) ? homeDashboardSlotSelectionSnapshot : [];
      const snapshotIdx = snapshotRows.findIndex((row) => Number(row?.id || 0) === selectedId);
      if (snapshotIdx >= 0) return dashboardSelectionPositionNumber(snapshotIdx + 1);
      return "";
    }

    function dashboardSelectedSlotIndexHint() {
      return dashboardSlotIndexHintForRow(getDashboardSingleSelectedRow());
    }

    function dashboardSlotHoverMetaOverlayEnabled() {
      if (getDashboardSelectionSourceKind() !== "SLOT") return false;
      if (!(homeDashboardSlotViewMode === "THUMB" || homeDashboardSlotViewMode === "SHELF")) return false;
      return typeof window !== "undefined"
        && typeof window.matchMedia === "function"
        && window.matchMedia("(hover: hover) and (pointer: fine)").matches;
    }

    function getDashboardHoveredSlotRow() {
      const hoveredId = Number(homeDashboardHoveredItemId || 0);
      if (hoveredId <= 0) return null;
      const rows = Array.isArray(homeDashboardSlotItems) ? homeDashboardSlotItems : [];
      return rows.find((row) => Number(row?.id || 0) === hoveredId) || null;
    }

    function renderDashboardSelectedItemMeta() {
      const el = $("homeDashSelectedItemMeta");
      const textEl = $("homeDashSelectedItemMetaText");
      if (!el) return;
      el.classList.remove("dashboard-selected-item-meta--overlay");
      setDisplayMode(el, "none");
      if (textEl) textEl.textContent = "";
      syncDashboardSelectedSortArtistEditor();
    }

    function syncDashboardSelectedSortArtistEditor() {
      const sourceKind = getDashboardSelectionSourceKind();
      const slotEditor = {
        row: $("homeDashSelectedSortArtistRow"),
        input: $("homeDashSelectedSortArtistName"),
        saveBtn: $("homeDashSelectedSortArtistSaveBtn"),
        displayEl: $("homeDashSelectedSortArtistDisplay"),
        statusId: "homeDashSelectedSortArtistStatus",
        sourceKinds: ["SLOT"],
      };
      const workbenchEditor = {
        row: $("homeDashWorkbenchSortArtistRow"),
        input: $("homeDashWorkbenchSortArtistName"),
        saveBtn: $("homeDashWorkbenchSortArtistSaveBtn"),
        displayEl: $("homeDashWorkbenchSortArtistDisplay"),
        statusId: "homeDashWorkbenchSortArtistStatus",
        sourceKinds: ["UNASSIGNED", "SEARCH"],
      };
      const editors = [slotEditor, workbenchEditor];
      const selectedRow = getDashboardSingleSelectedRow();
      const masterId = Number(selectedRow?.linked_album_master_id || selectedRow?.album_master_id || 0);
      const displayArtist = String(selectedRow?.artist_or_brand || selectedRow?.linked_artist_name || selectedRow?.master_artist_or_brand || "-").trim() || "-";
      editors.forEach((editor) => {
        if (!editor.row || !editor.input || !editor.saveBtn) return;
        const isVisible = editor.sourceKinds.includes(sourceKind);
        if (!selectedRow || masterId <= 0 || !isVisible) {
          setDisplayMode(editor.row, "none");
          editor.input.value = "";
          if (editor.displayEl) editor.displayEl.textContent = "";
          editor.saveBtn.disabled = true;
          setStatus(editor.statusId, "ok", "");
          return;
        }
        setDisplayMode(editor.row, "grid");
        editor.input.value = String(selectedRow?.master_sort_artist_name || "").trim();
        if (editor.displayEl) editor.displayEl.textContent = t("dashboard.selection.sort_artist.display_artist", { value: displayArtist });
        editor.saveBtn.disabled = false;
      });
    }

    function getActiveDashboardSelectedSortArtistEditor() {
      const sourceKind = getDashboardSelectionSourceKind();
      if (sourceKind === "SLOT") {
        return {
          row: $("homeDashSelectedSortArtistRow"),
          input: $("homeDashSelectedSortArtistName"),
          saveBtn: $("homeDashSelectedSortArtistSaveBtn"),
          displayEl: $("homeDashSelectedSortArtistDisplay"),
          statusId: "homeDashSelectedSortArtistStatus",
        };
      }
      if (sourceKind === "UNASSIGNED" || sourceKind === "SEARCH") {
        return {
          row: $("homeDashWorkbenchSortArtistRow"),
          input: $("homeDashWorkbenchSortArtistName"),
          saveBtn: $("homeDashWorkbenchSortArtistSaveBtn"),
          displayEl: $("homeDashWorkbenchSortArtistDisplay"),
          statusId: "homeDashWorkbenchSortArtistStatus",
        };
      }
      return null;
    }

    function syncDashboardSelectionControls() {
      const slotLoaded = String(homeDashboardSelectedSlotCode || "").trim()
        && String(homeDashboardSlotItemsSlotCode || "").trim() === String(homeDashboardSelectedSlotCode || "").trim();
      const slotRows = Array.isArray(homeDashboardSlotItems) ? homeDashboardSlotItems : [];
      const workbenchRows = getDashboardWorkbenchRows();
      const slotSelectedCount = homeDashboardSlotSelectedIds.size;
      const workbenchSelectedCount = getDashboardWorkbenchSelectedIds().size;
      const restoreEnabled = slotSelectedCount === 1;
      const slotClearEnabled = slotSelectedCount > 0 || Boolean(String(homeDashboardSelectedSlotCode || "").trim());
      const hasSelection = getDashboardSelectionSourceKind() !== "NONE";
      if (!hasSelection) {
        homeDashboardClickMoveMode = false;
      }
      const clickMoveActive = isDashboardClickMoveModeActive();

      if ($("homeDashSlotRestoreBtn")) $("homeDashSlotRestoreBtn").disabled = !restoreEnabled;
      if ($("homeDashSelectedItemEditBtn")) $("homeDashSelectedItemEditBtn").disabled = slotSelectedCount !== 1;
      if ($("homeDashSlotSelectAllBtn")) $("homeDashSlotSelectAllBtn").disabled = !(slotLoaded && slotRows.length > 0);
      if ($("homeDashSlotClearBtn")) $("homeDashSlotClearBtn").disabled = !slotClearEnabled;
      if ($("homeDashSlotMoveModeBtn")) {
        $("homeDashSlotMoveModeBtn").disabled = !hasSelection || clickMoveActive;
        $("homeDashSlotMoveModeBtn").hidden = clickMoveActive;
      }
      if ($("homeDashSlotMoveCancelBtn")) {
        $("homeDashSlotMoveCancelBtn").disabled = !clickMoveActive;
        $("homeDashSlotMoveCancelBtn").hidden = !clickMoveActive;
      }
      if ($("homeDashWorkbenchEditBtn")) $("homeDashWorkbenchEditBtn").disabled = workbenchSelectedCount !== 1;
      if ($("homeDashWorkbenchSelectAllBtn")) $("homeDashWorkbenchSelectAllBtn").disabled = workbenchRows.length <= 0;
      if ($("homeDashWorkbenchClearBtn")) $("homeDashWorkbenchClearBtn").disabled = workbenchSelectedCount <= 0;
      if ($("homeDashWorkbenchRecommendBtn")) $("homeDashWorkbenchRecommendBtn").disabled = workbenchRows.length <= 0;
      if ($("homeDashWorkbenchMoveModeBtn")) {
        $("homeDashWorkbenchMoveModeBtn").disabled = !hasSelection || clickMoveActive;
        $("homeDashWorkbenchMoveModeBtn").hidden = clickMoveActive;
      }
      if ($("homeDashWorkbenchMoveCancelBtn")) {
        $("homeDashWorkbenchMoveCancelBtn").disabled = !clickMoveActive;
        $("homeDashWorkbenchMoveCancelBtn").hidden = !clickMoveActive;
      }
      if ($("homeDashBulkApplyBtn")) $("homeDashBulkApplyBtn").disabled = !hasSelection;
      const hasBulkInput = Boolean(
        $("homeDashBulkStatus")?.value
        || $("homeDashBulkDomainCode")?.value
        || $("homeDashBulkReleaseType")?.value
        || $("homeDashBulkSecondHand")?.value
        || $("homeDashBulkPurchaseSource")?.value.trim()
        || $("homeDashBulkPreferredSize")?.value
        || $("homeDashBulkMemoryNote")?.value.trim()
      );
      if ($("homeDashBulkResetBtn")) $("homeDashBulkResetBtn").disabled = !hasBulkInput;
    }

    function renderDashboardSelectionSummary() {
      const slotSummary = $("homeDashSlotSelectionSummary");
      const previewSummary = dashboardPointerSelectionState?.didMove && dashboardPointerSelectionPreviewIds.length
        ? ((dashboardPointerSelectionState.currentRect.left < dashboardPointerSelectionState.startX)
          ? t("dashboard.selection.summary.preview_remove", { count: countWithUnit(dashboardPointerSelectionPreviewIds.length) })
          : t("dashboard.selection.summary.preview_add", { count: countWithUnit(dashboardPointerSelectionPreviewIds.length) }))
        : "";
      if (slotSummary) {
        const slotLoaded = String(homeDashboardSelectedSlotCode || "").trim()
          && String(homeDashboardSlotItemsSlotCode || "").trim() === String(homeDashboardSelectedSlotCode || "").trim();
        const slotTotal = slotLoaded
          ? formatCount((Array.isArray(homeDashboardSlotItems) ? homeDashboardSlotItems.length : 0))
          : formatCount(homeDashboardSlotSelectedIds.size);
        const moveHint = homeDashboardSlotSelectedIds.size > 0
          ? t(
            isDashboardClickMoveModeActive()
              ? "dashboard.selection.summary.move_active"
              : "dashboard.selection.summary.move_guard"
          )
          : null;
        const restoreHint = homeDashboardSlotSelectedIds.size === 1 ? t("dashboard.selection.summary.restore_available") : null;
        const selectedRow = getDashboardSingleSelectedRow();
        const previousLocation = selectedRow
          ? (localizeOperatorSlotDisplayName(selectedRow.previous_slot_display_name) || String(selectedRow.previous_slot_code || "").trim())
          : "";
        const previousHint = previousLocation ? t("dashboard.selection.summary.previous", { value: previousLocation }) : null;
        const orderHint = dashboardSelectedSlotIndexHint();
        const orderLabel = orderHint ? t("dashboard.selection.summary.position", { value: orderHint }) : null;
        slotSummary.textContent = slotLoaded
          ? [
              t("dashboard.selection.summary.current_slot", { count: countWithUnit(slotTotal) }),
              t("dashboard.selection.summary.selected", { count: countWithUnit(homeDashboardSlotSelectedIds.size) }),
              moveHint,
              dashboardPointerSelectionState?.scope === "SLOT" ? previewSummary : null,
              orderLabel,
              previousHint,
              restoreHint,
            ].filter(Boolean).join(" | ")
          : (homeDashboardSlotSelectedIds.size > 0
            ? [
                t("dashboard.selection.summary.keep_selected", { count: countWithUnit(slotTotal) }),
                moveHint,
                dashboardPointerSelectionState?.scope === "SLOT" ? previewSummary : null,
                orderLabel,
                previousHint,
                restoreHint,
              ].filter(Boolean).join(" | ")
            : t("dashboard.selection.summary.zero"));
      }
      const workbenchSummary = $("homeDashWorkbenchSummary");
      if (workbenchSummary) {
        const rows = getDashboardWorkbenchRows();
        const selectedIds = getDashboardWorkbenchSelectedIds();
        const modeLabel = homeDashboardWorkbenchMode === "SEARCH" ? t("dashboard.workbench.mode.search_results") : t("dashboard.workbench.mode.unslotted");
        const moveHint = selectedIds.size > 0
          ? t(
            isDashboardClickMoveModeActive()
              ? "dashboard.selection.summary.move_active"
              : "dashboard.selection.summary.move_guard"
          )
          : null;
        workbenchSummary.textContent = [
          t("dashboard.workbench.summary", {
          mode: modeLabel,
          total: formatCount(rows.length),
          selected: formatCount(selectedIds.size),
          }),
          moveHint,
          dashboardPointerSelectionState?.scope === "WORKBENCH" ? previewSummary : null,
        ].filter(Boolean).join(" | ");
      }
      renderDashboardSelectedItemMeta();
      syncDashboardSelectionControls();
    }

    function applyDashboardBulkUpdateToRow(row, payload) {
      if (!row || typeof row !== "object") return;
      if (payload.status) row.status = payload.status;
      if (payload.domain_code) row.domain_code = payload.domain_code;
      if (payload.release_type) row.release_type = payload.release_type;
      if (payload.is_second_hand != null) row.is_second_hand = payload.is_second_hand;
      if (payload.purchase_source != null) row.purchase_source = payload.purchase_source;
      if (payload.preferred_storage_size_group) row.preferred_storage_size_group = payload.preferred_storage_size_group;
      if (payload.append_memory_note) {
        const existing = String(row.memory_note || "").trim();
        row.memory_note = existing
          ? `${existing}\n${payload.append_memory_note}`
          : payload.append_memory_note;
      }
    }

    function applyDashboardBulkUpdateLocal(updatedIds, payload) {
      const targetIds = new Set((Array.isArray(updatedIds) ? updatedIds : []).map((v) => Number(v || 0)).filter((v) => v > 0));
      if (!targetIds.size) return;
      const pools = [
        homeDashboardSlotItems,
        homeDashboardSlotSelectionSnapshot,
        homeDashboardUnassignedItems,
        homeDashboardSearchItems,
      ];
      for (const pool of pools) {
        if (!Array.isArray(pool)) continue;
        for (const row of pool) {
          if (!targetIds.has(Number(row?.id || 0))) continue;
          applyDashboardBulkUpdateToRow(row, payload);
        }
      }
      renderDashboardCabinetDetail();
      renderDashboardWorkbench();
    }

    function getDashboardSelectableTitle(row) {
      return resolveOwnedAlbumName(row);
    }

    function dashboardSlotTooltipText(row, index) {
      const recentMoveText = dashboardRecentMoveText(row);
      const bits = [
        `${index + 1}. ${getDashboardSelectableTitle(row)}`,
        `owned_item_id: ${row.id}`,
        `label_id: ${row.label_id || "-"}`,
        t("dashboard.item.meta.artist", { value: row.artist_or_brand || row.linked_artist_name || "-" }),
        t("dashboard.item.meta.master_release", { value: row.master_release_year || row.release_year || "-" }),
        t("dashboard.item.meta.format", { value: mediaDisplayLabel(row.format_name || row.category || "-") }),
        `status: ${row.status || "-"}`,
        `order: ${row.order_key || "-"}`,
        `display: ${row.display_rank ?? "-"}`,
        t("dashboard.item.meta.release_date", { value: row.released_date || row.release_year || "-" }),
        t("dashboard.item.meta.genre", { value: Array.isArray(row.genres) && row.genres.length ? row.genres.join(", ") : "-" }),
        `label/cat#: ${row.label_name || "-"} / ${row.catalog_no || "-"}${row.barcode ? ` (${row.barcode})` : ""}`,
        recentMoveText ? t("dashboard.item.meta.recent_move", { value: recentMoveText }) : null,
        t("dashboard.item.meta.memo", { value: row.memory_note || "-" }),
      ].filter(Boolean);
      return bits.join("\n");
    }

    function dashboardRecentMoveText(row) {
      if (!row?.recently_moved_to_current_slot) return "";
      const previousLocation = localizeOperatorSlotDisplayName(row?.previous_slot_display_name) || String(row?.previous_slot_code || "").trim();
      return previousLocation
        ? t("dashboard.item.recent_move.from", { value: previousLocation })
        : t("dashboard.item.recent_move.short");
    }

    function dashboardRecentMoveInlineHtml(row, extraClass = "") {
      const recentMoveText = dashboardRecentMoveText(row);
      if (!recentMoveText) return "";
      const className = ["dashboard-slot-recentmove", extraClass].filter(Boolean).join(" ");
      return `<div class="${className}" title="${escapeHtml(recentMoveText)}">${escapeHtml(t("dashboard.item.recent_move.inline", { value: recentMoveText }))}</div>`;
    }

    function dashboardItemReleasedText(row) {
      return String(row?.released_date || row?.release_year || "").trim() || "-";
    }

    function dashboardItemLabelCatalogText(row) {
      const labelName = String(row?.label_name || "").trim() || "-";
      const catalogText = String(row?.catalog_no || "").trim();
      const barcodeText = String(row?.barcode || "").trim();
      return `${labelName} / ${catalogText || "-"}${barcodeText ? ` (${barcodeText})` : ""}`;
    }

    function dashboardItemFlagIcons(row) {
      const formatLabel = mediaDisplayLabel(row?.format_name || row?.category || "-");
      const statusCode = String(row?.status || "").trim();
      const coverCondition = normalizeConditionGradeValue(row?.cover_condition || "");
      const discCondition = normalizeConditionGradeValue(row?.disc_condition || "");
      const formatIcon = formatLabel && formatLabel !== "-"
        ? `<span class="dashboard-slot-flag-icon dashboard-slot-flag-icon--media" title="${escapeHtml(formatLabel)}">${escapeHtml(mediaIconLabel(row?.format_name || row?.category || "-"))}</span>`
        : "";
      const coverConditionIcon = coverCondition
        ? `<span class="dashboard-slot-flag-icon dashboard-slot-flag-icon--condition" title="${escapeHtml(t("dashboard.item.flag.cover_condition", { value: coverCondition }))}">${escapeHtml(conditionIconLabel("C", coverCondition))}</span>`
        : "";
      const discConditionIcon = discCondition
        ? `<span class="dashboard-slot-flag-icon dashboard-slot-flag-icon--condition" title="${escapeHtml(t("dashboard.item.flag.disc_condition", { value: discCondition }))}">${escapeHtml(conditionIconLabel("D", discCondition))}</span>`
        : "";
      const statusIcon = statusCode && statusCode !== "IN_COLLECTION"
        ? `<span class="dashboard-slot-flag-icon" title="${escapeHtml(dashboardStatusLabel(statusCode))}">${escapeHtml(statusIconLabel(statusCode) || statusCode.slice(0, 2).toUpperCase())}</span>`
        : "";
      return [
        formatIcon,
        coverConditionIcon,
        discConditionIcon,
        statusIcon,
      ].filter(Boolean).join("");
    }

    function dashboardItemCoverHtml(row, title) {
      const formatLabel = mediaDisplayLabel(row?.format_name || row?.category || "-");
      const coverUrl = normalizeRenderableCoverUrl(row?.cover_image_url);
      const signatureBadge = signatureCoverBadgeHtml(row?.signature_type, "dashboard-cover-signature-badge");
      return coverUrl
        ? `${signatureBadge}<img src="${escapeHtml(coverUrl)}" alt="${escapeHtml(title)}" />`
        : `${signatureBadge}${escapeHtml(formatLabel)}`;
    }

    function dashboardShelfSizeClass(row) {
      const code = String(ownedPreferredStorageSizeGroup(row) || row?.size_group || "").trim().toUpperCase();
      if (code === "STD") return "size-std";
      if (code === "BOOK") return "size-book";
      if (code === "OVERSIZE") return "size-oversize";
      if (code === "CASSETTE") return "size-std";
      if (code === "8TRACK") return "size-std";
      if (code === "REEL_TO_REEL") return "size-oversize";
      return "size-lp";
    }

    function dashboardSlotItemHtml(row, index) {
      const title = getDashboardSelectableTitle(row);
      const ownedItemId = Number(row.id || 0);
      const checked = homeDashboardSlotSelectedIds.has(ownedItemId);
      const tooltip = dashboardSlotTooltipText(row, index);
      const coverHtml = dashboardItemCoverHtml(row, title);
      const releasedDate = dashboardItemReleasedText(row);
      const labelCatalogText = dashboardItemLabelCatalogText(row);
      const rightMetaTags = dashboardItemFlagIcons(row);
      const memoryNote = String(row.memory_note || "").trim();
      const slotRow = getDashboardSlotRow(String(row?.slot_code || homeDashboardSelectedSlotCode || "").trim()) || null;
      const warningHtml = dashboardSlotWarningHtml(row, slotRow);
      const readOnlyShell = isShellReadOnly();
      return `
        <div
          class="result-item home-location-slot-item dashboard-slot-covercard ${checked ? "pick" : ""}"
          data-dashboard-owned-item-id="${ownedItemId}"
          data-dashboard-selectable-id="${ownedItemId}"
          data-dashboard-slot-code="${escapeHtml(String(row.slot_code || homeDashboardSelectedSlotCode || "").trim())}"
          data-dashboard-size-group="${escapeHtml(ownedPreferredStorageSizeGroup(row))}"
          data-dashboard-item-title="${escapeHtml(title)}"
          title="${escapeHtml(tooltip)}"
          draggable="${readOnlyShell ? "false" : "true"}"
        >
          <div class="dashboard-slot-covercard-cover">
            ${readOnlyShell ? "" : `<button class="dashboard-slot-selectbtn ${checked ? "is-selected" : ""}" type="button" aria-label="${escapeHtml(dashboardSelectionToggleLabel(checked))}" data-dashboard-slot-select="${ownedItemId}" title="${escapeHtml(dashboardSelectionToggleLabel(checked))}"></button>`}
            ${readOnlyShell ? "" : `<button class="dashboard-slot-editbtn" type="button" aria-label="${escapeHtml(dashboardEditItemLabel())}" data-dashboard-slot-edit="${ownedItemId}" title="${escapeHtml(dashboardEditItemLabel())}">✎</button>`}
            <div class="dashboard-slot-covercard-index">${index + 1}</div>
            ${rightMetaTags ? `<div class="dashboard-slot-covercard-badges">${rightMetaTags}</div>` : ""}
            ${coverHtml}
          </div>
          <div class="dashboard-slot-covercard-main">
            <div class="dashboard-slot-covercard-title">${escapeHtml(title)}</div>
            <div class="dashboard-slot-covercard-sub">${escapeHtml(releasedDate)}</div>
            <div class="dashboard-slot-covercard-sub">${escapeHtml(labelCatalogText)}</div>
            ${dashboardRecentMoveInlineHtml(row, "dashboard-slot-covercard-recentmove")}
            ${memoryNote ? `<div class="dashboard-slot-covercard-note">${escapeHtml(memoryNote)}</div>` : ""}
            ${warningHtml}
          </div>
        </div>
      `;
    }

    function dashboardSlotListItemHtml(row, index) {
      const title = getDashboardSelectableTitle(row);
      const ownedItemId = Number(row.id || 0);
      const checked = homeDashboardSlotSelectedIds.has(ownedItemId);
      const tooltip = dashboardSlotTooltipText(row, index);
      const flagIcons = dashboardItemFlagIcons(row);
      const memoryNote = String(row.memory_note || "").trim();
      const releasedDate = dashboardItemReleasedText(row);
      const slotRow = getDashboardSlotRow(String(row?.slot_code || homeDashboardSelectedSlotCode || "").trim()) || null;
      const warningHtml = dashboardSlotWarningHtml(row, slotRow);
      const readOnlyShell = isShellReadOnly();
      return `
        <div
          class="result-item home-location-slot-item dashboard-slot-listitem ${checked ? "pick" : ""}"
          data-dashboard-owned-item-id="${ownedItemId}"
          data-dashboard-selectable-id="${ownedItemId}"
          data-dashboard-slot-code="${escapeHtml(String(row.slot_code || homeDashboardSelectedSlotCode || "").trim())}"
          data-dashboard-size-group="${escapeHtml(ownedPreferredStorageSizeGroup(row))}"
          data-dashboard-item-title="${escapeHtml(title)}"
          title="${escapeHtml(tooltip)}"
          draggable="${readOnlyShell ? "false" : "true"}"
        >
          ${readOnlyShell ? "" : `<button class="dashboard-slot-selectbtn ${checked ? "is-selected" : ""}" type="button" data-dashboard-slot-select="${ownedItemId}" title="${escapeHtml(dashboardSelectionToggleLabel(checked, true))}">${escapeHtml(dashboardSelectionToggleLabel(checked, true))}</button>`}
          <div class="dashboard-slot-listitem-order">${index + 1}</div>
          <div class="dashboard-slot-listitem-cover">
            ${dashboardItemCoverHtml(row, title)}
          </div>
          <div class="dashboard-slot-listitem-main">
            <div class="dashboard-slot-listitem-head">
              <div class="dashboard-slot-listitem-title">${escapeHtml(title)}</div>
              <div class="dashboard-slot-listitem-date">${escapeHtml(releasedDate)}</div>
            </div>
            <div class="dashboard-slot-listitem-sub">${escapeHtml(dashboardItemLabelCatalogText(row))}</div>
            ${dashboardRecentMoveInlineHtml(row, "dashboard-slot-listitem-recentmove")}
            ${memoryNote ? `<div class="dashboard-slot-listitem-note">${escapeHtml(memoryNote)}</div>` : ""}
            ${warningHtml}
          </div>
          ${readOnlyShell ? "" : `<button class="dashboard-slot-editbtn" type="button" aria-label="${escapeHtml(dashboardEditItemLabel())}" data-dashboard-slot-edit="${ownedItemId}" title="${escapeHtml(dashboardEditItemLabel())}">✎</button>`}
          <div class="dashboard-slot-listitem-flags">${flagIcons}</div>
        </div>
      `;
    }

    function dashboardSlotShelfItemHtml(row, index) {
      const title = getDashboardSelectableTitle(row);
      const ownedItemId = Number(row.id || 0);
      const checked = homeDashboardSlotSelectedIds.has(ownedItemId);
      const tooltip = dashboardSlotTooltipText(row, index);
      const flagIcons = dashboardItemFlagIcons(row);
      const sizeClass = dashboardShelfSizeClass(row);
      const slotRow = getDashboardSlotRow(String(row?.slot_code || homeDashboardSelectedSlotCode || "").trim()) || null;
      const warningHtml = dashboardSlotWarningHtml(row, slotRow);
      const readOnlyShell = isShellReadOnly();
      return `
        <div
          class="result-item home-location-slot-item dashboard-slot-shelfcard ${sizeClass} ${checked ? "pick" : ""}"
          data-dashboard-owned-item-id="${ownedItemId}"
          data-dashboard-selectable-id="${ownedItemId}"
          data-dashboard-slot-code="${escapeHtml(String(row.slot_code || homeDashboardSelectedSlotCode || "").trim())}"
          data-dashboard-size-group="${escapeHtml(ownedPreferredStorageSizeGroup(row))}"
          data-dashboard-item-title="${escapeHtml(title)}"
          title="${escapeHtml(tooltip)}"
          draggable="${readOnlyShell ? "false" : "true"}"
        >
          ${readOnlyShell ? "" : `<button class="dashboard-slot-selectbtn ${checked ? "is-selected" : ""}" type="button" aria-label="${escapeHtml(dashboardSelectionToggleLabel(checked))}" data-dashboard-slot-select="${ownedItemId}" title="${escapeHtml(dashboardSelectionToggleLabel(checked))}"></button>`}
          ${readOnlyShell ? "" : `<button class="dashboard-slot-editbtn" type="button" aria-label="${escapeHtml(dashboardEditItemLabel())}" data-dashboard-slot-edit="${ownedItemId}" title="${escapeHtml(dashboardEditItemLabel())}">✎</button>`}
          <div class="dashboard-slot-shelfcover">
            <div class="dashboard-slot-covercard-index">${index + 1}</div>
            ${flagIcons ? `<div class="dashboard-slot-covercard-badges">${flagIcons}</div>` : ""}
            ${dashboardRecentMoveInlineHtml(row, "dashboard-slot-shelfrecentmove")}
            ${dashboardItemCoverHtml(row, title)}
          </div>
          ${warningHtml}
        </div>
      `;
    }

    function dashboardWorkbenchListItemHtml(row, source, index = 0) {
      const title = getDashboardSelectableTitle(row);
      const ownedItemId = Number(row.id || 0);
      const mode = String(source || "").trim().toUpperCase() === "SEARCH" ? "SEARCH" : "UNASSIGNED";
      const checked = mode === "SEARCH"
        ? homeDashboardSearchSelectedIds.has(ownedItemId)
        : homeDashboardUnassignedSelectedIds.has(ownedItemId);
      const tooltip = dashboardSlotTooltipText(row, index);
      const flagIcons = dashboardItemFlagIcons(row);
      const memoryNote = String(row.memory_note || "").trim();
      const releasedDate = dashboardItemReleasedText(row);
      const locationAction = getDashboardWorkbenchLocationAction(row, mode);
      const locationText = dashboardWorkbenchLocationText(row, mode);
      const readOnlyShell = isShellReadOnly();
      const warningHtml = dashboardWorkbenchWarningHtml(row);
      return `
        <div
          class="result-item home-location-slot-item dashboard-slot-listitem ${checked ? "pick" : ""}"
          data-dashboard-workbench-owned-item-id="${ownedItemId}"
          data-dashboard-selectable-id="${ownedItemId}"
          data-dashboard-workbench-source="${mode}"
          data-dashboard-slot-code="${escapeHtml(String(row?.slot_code || "").trim())}"
          data-dashboard-size-group="${escapeHtml(ownedPreferredStorageSizeGroup(row))}"
          data-dashboard-item-title="${escapeHtml(title)}"
          title="${escapeHtml(tooltip)}"
          draggable="${readOnlyShell ? "false" : "true"}"
        >
          ${readOnlyShell ? "" : `<button class="dashboard-slot-selectbtn ${checked ? "is-selected" : ""}" type="button" data-dashboard-workbench-select="${ownedItemId}" data-dashboard-workbench-source="${mode}" title="${escapeHtml(dashboardSelectionToggleLabel(checked, true))}">${escapeHtml(dashboardSelectionToggleLabel(checked, true))}</button>`}
          <div class="dashboard-slot-listitem-order">${index + 1}</div>
          <div class="dashboard-slot-listitem-cover">
            ${dashboardItemCoverHtml(row, title)}
          </div>
          <div class="dashboard-slot-listitem-main">
            <div class="dashboard-slot-listitem-head">
              <div class="dashboard-slot-listitem-title">${escapeHtml(title)}</div>
              <div class="dashboard-slot-listitem-date">${escapeHtml(releasedDate)}</div>
            </div>
            <div class="dashboard-slot-listitem-sub">${escapeHtml(dashboardItemLabelCatalogText(row))}</div>
            ${locationText ? `<div class="dashboard-slot-listitem-sub">${escapeHtml(locationText)}</div>` : ""}
            ${memoryNote ? `<div class="dashboard-slot-listitem-note">${escapeHtml(memoryNote)}</div>` : ""}
            ${warningHtml}
          </div>
          ${locationAction ? dashboardWorkbenchLocateButtonHtml(locationAction) : ""}
          ${readOnlyShell ? "" : `<button class="dashboard-slot-editbtn" type="button" aria-label="${escapeHtml(dashboardEditItemLabel())}" data-dashboard-workbench-edit="${ownedItemId}" title="${escapeHtml(dashboardEditItemLabel())}">✎</button>`}
          <div class="dashboard-slot-listitem-flags">${flagIcons}</div>
        </div>
      `;
    }

    function dashboardWorkbenchShelfItemHtml(row, source, index = 0) {
      const title = getDashboardSelectableTitle(row);
      const ownedItemId = Number(row.id || 0);
      const mode = String(source || "").trim().toUpperCase() === "SEARCH" ? "SEARCH" : "UNASSIGNED";
      const checked = mode === "SEARCH"
        ? homeDashboardSearchSelectedIds.has(ownedItemId)
        : homeDashboardUnassignedSelectedIds.has(ownedItemId);
      const tooltip = dashboardSlotTooltipText(row, index);
      const flagIcons = dashboardItemFlagIcons(row);
      const locationAction = getDashboardWorkbenchLocationAction(row, mode);
      const locationText = dashboardWorkbenchLocationText(row, mode);
      const sizeClass = dashboardShelfSizeClass(row);
      const readOnlyShell = isShellReadOnly();
      const warningHtml = dashboardWorkbenchWarningHtml(row);
      return `
        <div
          class="result-item home-location-slot-item dashboard-slot-shelfcard ${sizeClass} ${checked ? "pick" : ""}"
          data-dashboard-workbench-owned-item-id="${ownedItemId}"
          data-dashboard-selectable-id="${ownedItemId}"
          data-dashboard-workbench-source="${mode}"
          data-dashboard-slot-code="${escapeHtml(String(row?.slot_code || "").trim())}"
          data-dashboard-size-group="${escapeHtml(ownedPreferredStorageSizeGroup(row))}"
          data-dashboard-item-title="${escapeHtml(title)}"
          title="${escapeHtml(tooltip)}"
          draggable="${readOnlyShell ? "false" : "true"}"
        >
          ${readOnlyShell ? "" : `<button class="dashboard-slot-selectbtn ${checked ? "is-selected" : ""}" type="button" aria-label="${escapeHtml(dashboardSelectionToggleLabel(checked))}" data-dashboard-workbench-select="${ownedItemId}" data-dashboard-workbench-source="${mode}" title="${escapeHtml(dashboardSelectionToggleLabel(checked))}"></button>`}
          ${readOnlyShell ? "" : `<button class="dashboard-slot-editbtn" type="button" aria-label="${escapeHtml(dashboardEditItemLabel())}" data-dashboard-workbench-edit="${ownedItemId}" title="${escapeHtml(dashboardEditItemLabel())}">✎</button>`}
          ${locationAction ? dashboardWorkbenchLocateButtonHtml(locationAction) : ""}
          <div class="dashboard-slot-shelfcover">
            <div class="dashboard-slot-covercard-index">${index + 1}</div>
            ${flagIcons ? `<div class="dashboard-slot-covercard-badges">${flagIcons}</div>` : ""}
            ${dashboardItemCoverHtml(row, title)}
            ${locationText ? `<div class="dashboard-slot-shelfhint" title="${escapeHtml(locationText)}">${escapeHtml(locationText)}</div>` : ""}
          </div>
          ${warningHtml}
        </div>
      `;
    }

    function getDashboardWorkbenchRecommendation(ownedItemId) {
      const nextId = Number(ownedItemId || 0);
      if (nextId <= 0) return null;
      const raw = homeDashboardWorkbenchRecommendations?.[nextId];
      return raw && typeof raw === "object" ? raw : null;
    }

    function getDashboardWorkbenchRecommendationCandidates(recommendation) {
      if (!recommendation || !Array.isArray(recommendation.candidate_slots)) return [];
      return recommendation.candidate_slots.filter((item) => item && typeof item === "object");
    }

    function formatDashboardWorkbenchRecommendationDisplay(recommendation) {
      if (!recommendation) return "";
      const base = String(
        recommendation.display_name
        || formatDashboardSlotDisplay(recommendation)
        || recommendation.slot_code
        || ""
      ).trim();
      const candidates = getDashboardWorkbenchRecommendationCandidates(recommendation);
      if (!base) return "";
      if (candidates.length <= 1) return base;
      return t("dashboard.workbench.recommendation.more", {
        base,
        count: formatCount(candidates.length - 1),
      });
    }

    function dashboardWorkbenchRecommendationDetailText(recommendation) {
      const candidates = getDashboardWorkbenchRecommendationCandidates(recommendation);
      if (!candidates.length) return "";
      return candidates
        .map((item) => String(item.display_name || formatDashboardSlotDisplay(item) || item.slot_code || "").trim())
        .filter(Boolean)
        .join(" | ");
    }

    function formatDashboardSlotDisplay(item) {
      const cabinetName = String(item?.cabinet_name || "").trim();
      const columnCode = String(item?.column_code || "").trim();
      const cellCode = String(item?.cell_code || "").trim();
      const slotCode = String(item?.slot_code || "").trim();
      if (cabinetName) {
        return [
          cabinetName,
          columnCode ? dashboardColumnCodeLabel(columnCode) : null,
          cellCode ? dashboardCellCodeLabel(cellCode) : null,
        ].filter(Boolean).join(" / ");
      }
      return slotCode || "";
    }

    function getDashboardWorkbenchLocationAction(row, source) {
      const mode = String(source || "").trim().toUpperCase();
      if (mode === "SEARCH") {
        const storageSlotId = Number(row?.storage_slot_id || 0);
        const slotCode = String(row?.slot_code || "").trim();
        if (storageSlotId > 0 || slotCode) {
          return {
            action: "CURRENT",
            slotId: storageSlotId || null,
            slotCode: slotCode || null,
        displayName: slotCode || t("dashboard.workbench.location.current_fallback"),
          };
        }
      }
      const recommendation = getDashboardWorkbenchRecommendation(Number(row?.id || 0));
      if (recommendation?.recommended_storage_slot_id || recommendation?.slot_code) {
        return {
          action: "RECOMMEND",
          slotId: Number(recommendation.recommended_storage_slot_id || 0) || null,
          slotCode: String(recommendation.slot_code || "").trim() || null,
          displayName: formatDashboardWorkbenchRecommendationDisplay(recommendation) || t("dashboard.workbench.location.recommend_fallback"),
          detailText: dashboardWorkbenchRecommendationDetailText(recommendation),
        };
      }
      return null;
    }

    function dashboardWorkbenchLocationText(row, source) {
      const action = getDashboardWorkbenchLocationAction(row, source);
      if (!action) return "";
      const label = String(action.displayName || action.slotCode || "").trim();
      if (!label) return "";
      return action.action === "CURRENT"
        ? t("dashboard.workbench.location.current", { name: label })
        : t("dashboard.workbench.location.recommend", { name: label });
    }

    function dashboardWorkbenchLocateButtonHtml(action) {
      const mode = String(action?.action || "").trim().toUpperCase();
      const displayName = String(action.displayName || action.slotCode || "-");
      const title = mode === "CURRENT"
        ? t("dashboard.workbench.tooltip.current", { name: displayName })
        : (action?.detailText
          ? t("dashboard.workbench.tooltip.recommend_with_detail", { name: displayName, detail: String(action.detailText) })
          : t("dashboard.workbench.tooltip.recommend", { name: displayName }));
      return `<button class="dashboard-slot-locatebtn" type="button" data-dashboard-workbench-open-slot="${escapeHtml(String(action.slotId || ""))}" data-dashboard-workbench-open-slot-code="${escapeHtml(String(action.slotCode || ""))}" title="${escapeHtml(title)}">${mode === "CURRENT" ? "↗" : "⌖"}</button>`;
    }

    function dashboardWorkbenchItemHtml(row, source) {
      const ownedItemId = Number(row?.id || 0);
      const mode = String(source || "").trim().toUpperCase() === "SEARCH" ? "SEARCH" : "UNASSIGNED";
      const checked = mode === "SEARCH"
        ? homeDashboardSearchSelectedIds.has(ownedItemId)
        : homeDashboardUnassignedSelectedIds.has(ownedItemId);
      const title = getDashboardSelectableTitle(row);
      const releasedDate = dashboardItemReleasedText(row);
      const labelCatalogText = dashboardItemLabelCatalogText(row);
      const flagIcons = dashboardItemFlagIcons(row);
      const location = String(row?.slot_code || "").trim() || t("common.unslotted");
      const memoryNote = String(row?.memory_note || "").trim();
      const locationAction = getDashboardWorkbenchLocationAction(row, mode);
      const locationText = dashboardWorkbenchLocationText(row, mode);
      const readOnlyShell = isShellReadOnly();
      const warningHtml = dashboardWorkbenchWarningHtml(row);
      const tooltipBits = [
        title,
        `owned_item_id: ${ownedItemId}`,
        t("dashboard.item.meta.release_date", { value: releasedDate }),
        `label/cat#: ${labelCatalogText}`,
        mode === "SEARCH"
          ? t("dashboard.item.meta.location", { value: location })
          : t("dashboard.item.meta.location", { value: t("common.unslotted") }),
        locationText ? `${locationText}` : null,
        t("dashboard.item.meta.memo", { value: memoryNote || "-" }),
      ];
      return `
        <div
          class="result-item home-location-slot-item dashboard-slot-covercard ${checked ? "pick" : ""}"
          data-dashboard-workbench-owned-item-id="${ownedItemId}"
          data-dashboard-selectable-id="${ownedItemId}"
          data-dashboard-workbench-source="${mode}"
          data-dashboard-slot-code="${escapeHtml(String(row?.slot_code || "").trim())}"
          data-dashboard-size-group="${escapeHtml(ownedPreferredStorageSizeGroup(row))}"
          data-dashboard-item-title="${escapeHtml(title)}"
          title="${escapeHtml(tooltipBits.join("\n"))}"
          draggable="${readOnlyShell ? "false" : "true"}"
        >
          <div class="dashboard-slot-covercard-cover">
            ${readOnlyShell ? "" : `<button class="dashboard-slot-selectbtn ${checked ? "is-selected" : ""}" type="button" data-dashboard-workbench-select="${ownedItemId}" data-dashboard-workbench-source="${mode}" title="${escapeHtml(dashboardSelectionToggleLabel(checked, true))}">${escapeHtml(dashboardSelectionToggleLabel(checked, true))}</button>`}
            ${readOnlyShell ? "" : `<button class="dashboard-slot-editbtn" type="button" aria-label="${escapeHtml(dashboardEditItemLabel())}" data-dashboard-workbench-edit="${ownedItemId}" title="${escapeHtml(dashboardEditItemLabel())}">✎</button>`}
            ${locationAction ? dashboardWorkbenchLocateButtonHtml(locationAction) : ""}
            ${flagIcons ? `<div class="dashboard-slot-covercard-badges">${flagIcons}</div>` : ""}
            ${dashboardItemCoverHtml(row, title)}
          </div>
          <div class="dashboard-slot-covercard-main">
            <div class="dashboard-slot-covercard-title">${escapeHtml(title)}</div>
            <div class="dashboard-slot-covercard-sub">${escapeHtml(releasedDate)}</div>
            <div class="dashboard-slot-covercard-sub">${escapeHtml(labelCatalogText)}</div>
            ${mode === "SEARCH" ? `<div class="dashboard-slot-covercard-sub">${escapeHtml(t("dashboard.item.meta.location", { value: location }))}</div>` : ""}
            ${locationText ? `<div class="dashboard-slot-covercard-sub">${escapeHtml(locationText)}</div>` : ""}
            ${memoryNote ? `<div class="dashboard-slot-covercard-note">${escapeHtml(memoryNote)}</div>` : ""}
            ${warningHtml}
          </div>
        </div>
      `;
    }

    function dashboardWorkbenchMediaFilterValue() {
      return String($("homeDashMediaFilter")?.value || "ANY").trim().toUpperCase() || "ANY";
    }

    function dashboardWorkbenchSignatureModeValue() {
      return String($("homeDashSignatureMode")?.value || "ANY").trim().toUpperCase() || "ANY";
    }

    function dashboardWorkbenchSortModeValue() {
      return String($("homeDashWorkbenchSortMode")?.value || "NAME_ASC").trim().toUpperCase() || "NAME_ASC";
    }

    function dashboardWorkbenchSortWarningOnlyValue() {
      return Boolean($("homeDashSortWarningOnly")?.checked);
    }

    function dashboardWorkbenchDomainFilterValue() {
      const field = $("homeDashWorkbenchDomainFilter");
      const select = field?.querySelector("select");
      return String(select?.value || "ANY").trim().toUpperCase() || "ANY";
    }

    function dashboardWorkbenchArtistSortText(row) {
      return String(
        row?.master_sort_artist_name
        || row?.linked_artist_name
        || row?.artist_or_brand
        || row?.master_artist_or_brand
        || ""
      ).trim().replace(/\s+/g, " ");
    }

    function dashboardWorkbenchDisplayArtistText(row) {
      return String(
        row?.artist_or_brand
        || row?.linked_artist_name
        || row?.master_artist_or_brand
        || ""
      ).trim().replace(/\s+/g, " ");
    }

    function dashboardWorkbenchHasLatinDominantArtist(text) {
      const value = String(text || "").trim();
      if (!value) return false;
      const latinCount = (value.match(/[A-Za-z\u00C0-\u024F]/g) || []).length;
      if (!latinCount) return false;
      const nonLatinCount = (value.match(/[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af]/g) || []).length;
      return latinCount >= Math.max(1, nonLatinCount);
    }

    function dashboardWorkbenchSortArtistMatchesDomain(row) {
      const domainCode = String(row?.domain_code || "").trim().toUpperCase();
      const explicitSortArtist = String(row?.master_sort_artist_name || "").trim();
      if (!explicitSortArtist) return false;
      if (domainCode === "KOREA") return /[\uac00-\ud7af]/.test(explicitSortArtist);
      if (domainCode === "JAPAN") return /[\u3040-\u30ff\u4e00-\u9fff]/.test(explicitSortArtist);
      if (["GREATER_CHINA", "OTHER_ASIA"].includes(domainCode)) return /[\u3400-\u4dbf\u4e00-\u9fff]/.test(explicitSortArtist);
      return false;
    }

    function dashboardWorkbenchNeedsSortWarning(row) {
      const domainCode = String(row?.domain_code || "").trim().toUpperCase();
      if (!["KOREA", "JAPAN", "GREATER_CHINA", "OTHER_ASIA"].includes(domainCode)) return false;
      const normalizedArtist = dashboardWorkbenchArtistSortText(row).toUpperCase();
      if (normalizedArtist === "VARIOUS" || normalizedArtist === "VARIOUS ARTISTS") return false;
      if (dashboardWorkbenchSortArtistMatchesDomain(row)) return false;
      return dashboardWorkbenchHasLatinDominantArtist(dashboardWorkbenchArtistSortText(row));
    }

    function dashboardWorkbenchWarningInfo(row) {
      if (!dashboardWorkbenchNeedsSortWarning(row)) return null;
      return {
        badges: [
          t("dashboard.workbench.warning.badge.sort"),
          t("dashboard.workbench.warning.badge.domain_name_mismatch"),
        ],
      };
    }

    function dashboardSlotWarningInfo(row, slotRow) {
      if (!row || !slotRow) return null;
      const warnings = [];
      const slotSizeGroup = String(slotRow?.allowed_size_group || "").trim().toUpperCase();
      const itemSizeGroup = String(ownedPreferredStorageSizeGroup(row) || row?.size_group || "").trim().toUpperCase();
      const slotDomainCode = String(slotRow?.cabinet_domain_code || "").trim().toUpperCase();
      const itemDomainCode = String(row?.domain_code || "").trim().toUpperCase();
      if (slotSizeGroup && itemSizeGroup && slotSizeGroup !== itemSizeGroup) {
        warnings.push({
          kind: "SIZE_MISMATCH",
          badge: t("dashboard.slot.warning.badge.size_mismatch"),
          detail: t("dashboard.slot.warning.detail.size_mismatch"),
        });
      }
      if (
        slotDomainCode
        && itemDomainCode
        && !["UNKNOWN", "UNASSIGNED"].includes(slotDomainCode)
        && !["UNKNOWN", "UNASSIGNED"].includes(itemDomainCode)
        && slotDomainCode !== itemDomainCode
      ) {
        warnings.push({
          kind: "DOMAIN_MISMATCH",
          badge: t("dashboard.slot.warning.badge.domain_mismatch"),
          detail: t("dashboard.slot.warning.detail.domain_mismatch"),
        });
      }
      if (dashboardWorkbenchNeedsSortWarning(row)) {
        warnings.push({
          kind: "DOMAIN_NAME_MISMATCH",
          badge: t("dashboard.slot.warning.badge.domain_name_mismatch"),
          detail: t("dashboard.slot.warning.detail.domain_name_mismatch"),
        });
      }
      return warnings.length ? warnings : null;
    }

    function dashboardWorkbenchMatchesDomainFilter(row) {
      const domainFilter = dashboardWorkbenchDomainFilterValue();
      if (domainFilter === "ANY") return true;
      return String(row?.domain_code || "").trim().toUpperCase() === domainFilter;
    }

    function dashboardWorkbenchWarningHtml(row) {
      const warning = dashboardWorkbenchWarningInfo(row);
      if (!warning) return "";
      return `
        <div class="dashboard-workbench-warning">
          <div class="dashboard-workbench-warning-badges">
            ${warning.badges.map((label, index) => `<span class="dashboard-workbench-warning-badge${index > 0 ? " dashboard-workbench-warning-badge--muted" : ""}">${escapeHtml(label)}</span>`).join("")}
          </div>
        </div>
      `;
    }

    function dashboardSlotWarningHtml(row, slotRow) {
      const warnings = dashboardSlotWarningInfo(row, slotRow);
      if (!warnings?.length) return "";
      return `
        <div class="dashboard-workbench-warning">
          <div class="dashboard-workbench-warning-badges">
            <span class="dashboard-workbench-warning-badge">${escapeHtml(t("dashboard.slot.warning.badge.general"))}</span>
            ${warnings.map((warning) => `<span class="dashboard-workbench-warning-badge dashboard-workbench-warning-badge--muted">${escapeHtml(warning.badge)}</span>`).join("")}
          </div>
          ${warnings.map((warning) => `<div class="dashboard-workbench-warning-reason">${escapeHtml(warning.detail)}</div>`).join("")}
        </div>
      `;
    }

    function loadDashboardWorkbenchPreferences() {
      const role = currentSessionRoleCode();
      const map = loadRoleScopedMap(DASHBOARD_WORKBENCH_PREFS_KEY);
      const value = map?.[role];
      return value && typeof value === "object" && !Array.isArray(value) ? value : {};
    }

    function applyDashboardWorkbenchPreferences() {
      const prefs = loadDashboardWorkbenchPreferences();
      const category = String(prefs?.category || "ANY").trim().toUpperCase();
      const signatureMode = String(prefs?.signature_mode || "ANY").trim().toUpperCase();
      const sortMode = String(prefs?.sort_mode || "NAME_ASC").trim().toUpperCase();
      const sortWarningOnly = Boolean(prefs?.sort_warning_only);
      const domainFilter = String(prefs?.domain_filter || "ANY").trim().toUpperCase();
      const slotSortMode = String(prefs?.slot_sort_mode || "NAME_ASC").trim().toUpperCase();
      if ($("homeDashMediaFilter")) {
        $("homeDashMediaFilter").value = ["ANY", "LP", "CD", "CASSETTE", "8TRACK", "DIGITAL", "REEL_TO_REEL"].includes(category) ? category : "ANY";
      }
      if ($("homeDashSignatureMode")) {
        $("homeDashSignatureMode").value = ["ANY", "DIRECT", "PURCHASE"].includes(signatureMode) ? signatureMode : "ANY";
      }
      if ($("homeDashWorkbenchSortMode")) {
        $("homeDashWorkbenchSortMode").value = ["CREATED_DESC", "NAME_ASC"].includes(sortMode) ? sortMode : "NAME_ASC";
      }
      if ($("homeDashSortWarningOnly")) {
        $("homeDashSortWarningOnly").checked = sortWarningOnly;
      }
      if ($("homeDashWorkbenchDomainFilter")) {
        const select = $("homeDashWorkbenchDomainFilter").querySelector("select");
        if (select) {
          select.value = ["ANY", "KOREA", "JAPAN", "GREATER_CHINA", "OTHER_ASIA"].includes(domainFilter) ? domainFilter : "ANY";
        }
      }
      // homeDashSlotSortMode removed — no pref restore needed
      if ($("homeDashSearchArtist")) {
        $("homeDashSearchArtist").value = String(prefs?.artist || "");
      }
      if ($("homeDashSearchTitle")) {
        $("homeDashSearchTitle").value = String(prefs?.title || "");
      }
      if ($("homeDashSearchCatalogNo")) {
        $("homeDashSearchCatalogNo").value = String(prefs?.catalog_no || "");
      }
      if ($("homeDashSearchBarcode")) {
        $("homeDashSearchBarcode").value = String(prefs?.barcode || "");
      }
    }

    function renderDashboardUnassignedItems() {
      const root = $("homeDashWorkbenchList");
      const meta = $("homeDashWorkbenchMeta");
      if (!root) return;
      if (homeDashboardWorkbenchMode !== "UNASSIGNED") return;
      if (homeDashboardUnassignedLoading) {
        root.innerHTML = `<div class='mini muted'>${escapeHtml(t("dashboard.workbench.status.loading_unslotted"))}</div>`;
        updateDashboardWorkbenchPageControls(null);
        renderDashboardSelectionSummary();
        return;
      }
      const items = getDashboardWorkbenchRows();
      if (meta) {
        meta.textContent = t("dashboard.workbench.meta.unslotted_ready");
      }
      if (!items.length) {
        root.innerHTML = `<div class='mini muted'>${escapeHtml(t("dashboard.workbench.status.empty_unslotted"))}</div>`;
        updateDashboardWorkbenchPageControls(null);
        renderDashboardSelectionSummary();
        return;
      }
      const sourceSlotRow = getDashboardSlotRow(homeDashboardSelectedSlotCode);
      const sliceInfo = dashboardWorkbenchPageSlice(items, sourceSlotRow);
      applyDashboardSlotViewMode(root, sourceSlotRow);
      if (homeDashboardSlotViewMode === "LIST") {
        root.innerHTML = sliceInfo.items.map((row, index) => dashboardWorkbenchListItemHtml(row, "UNASSIGNED", sliceInfo.start + index)).join("");
      } else if (homeDashboardSlotViewMode === "SHELF") {
        root.innerHTML = sliceInfo.items.map((row, index) => dashboardWorkbenchShelfItemHtml(row, "UNASSIGNED", sliceInfo.start + index)).join("");
        applyDashboardShelfNeighborHighlight(root);
        restoreDashboardWorkbenchShelfScroll(root);
        const skipSelectionScroll = homeDashboardWorkbenchSuppressSelectionScrollOnce;
        homeDashboardWorkbenchSuppressSelectionScrollOnce = false;
        if (!skipSelectionScroll) {
          requestAnimationFrame(() => scrollDashboardShelfSelectionIntoView(root));
        }
      } else {
        root.innerHTML = sliceInfo.items.map((row) => dashboardWorkbenchItemHtml(row, "UNASSIGNED")).join("");
      }
      updateDashboardWorkbenchPageControls(sliceInfo);
      renderDashboardSelectionSummary();
    }

    function renderDashboardWorkbench() {
      const root = $("homeDashWorkbenchList");
      const meta = $("homeDashWorkbenchMeta");
      if (!root || !meta) return;

      $("homeDashModeUnassignedBtn")?.classList.toggle("active", homeDashboardWorkbenchMode === "UNASSIGNED");
      $("homeDashModeSearchBtn")?.classList.toggle("active", homeDashboardWorkbenchMode === "SEARCH");

      if (homeDashboardWorkbenchMode === "UNASSIGNED") {
        renderDashboardUnassignedItems();
        return;
      }

      meta.textContent = t("dashboard.workbench.meta.search_ready");
      if (homeDashboardSearchLoading) {
        root.innerHTML = `<div class='mini muted'>${escapeHtml(t("dashboard.workbench.status.loading_search"))}</div>`;
        updateDashboardWorkbenchPageControls(null);
        renderDashboardSelectionSummary();
        return;
      }
      const items = getDashboardWorkbenchRows();
      if (!items.length) {
        root.innerHTML = `<div class='mini muted'>${escapeHtml(t("dashboard.workbench.status.empty_search"))}</div>`;
        updateDashboardWorkbenchPageControls(null);
        renderDashboardSelectionSummary();
        return;
      }
      const sourceSlotRow = getDashboardSlotRow(homeDashboardSelectedSlotCode);
      const sliceInfo = dashboardWorkbenchPageSlice(items, sourceSlotRow);
      applyDashboardSlotViewMode(root, sourceSlotRow);
      if (homeDashboardSlotViewMode === "LIST") {
        root.innerHTML = sliceInfo.items.map((row, index) => dashboardWorkbenchListItemHtml(row, "SEARCH", sliceInfo.start + index)).join("");
      } else if (homeDashboardSlotViewMode === "SHELF") {
        root.innerHTML = sliceInfo.items.map((row, index) => dashboardWorkbenchShelfItemHtml(row, "SEARCH", sliceInfo.start + index)).join("");
        applyDashboardShelfNeighborHighlight(root);
        restoreDashboardWorkbenchShelfScroll(root);
        const skipSelectionScroll = homeDashboardWorkbenchSuppressSelectionScrollOnce;
        homeDashboardWorkbenchSuppressSelectionScrollOnce = false;
        if (!skipSelectionScroll) {
          requestAnimationFrame(() => scrollDashboardShelfSelectionIntoView(root));
        }
      } else {
        root.innerHTML = sliceInfo.items.map((row) => dashboardWorkbenchItemHtml(row, "SEARCH")).join("");
      }
      updateDashboardWorkbenchPageControls(sliceInfo);
      renderDashboardSelectionSummary();
    }

    function getDashboardSelectedWorkbenchRows() {
      const sourceKind = getDashboardSelectionSourceKind();
      if (sourceKind === "SLOT") {
        const source = Array.isArray(homeDashboardSlotSelectionSnapshot) && homeDashboardSlotSelectionSnapshot.length
          ? homeDashboardSlotSelectionSnapshot
          : (Array.isArray(homeDashboardSlotItems) ? homeDashboardSlotItems : []);
        return source.filter((row) => homeDashboardSlotSelectedIds.has(Number(row?.id || 0)));
      }
      if (sourceKind === "UNASSIGNED") {
        return filterDashboardWorkbenchItems(homeDashboardUnassignedItems)
          .filter((row) => homeDashboardUnassignedSelectedIds.has(Number(row?.id || 0)));
      }
      if (sourceKind === "SEARCH") {
        return filterDashboardWorkbenchItems(homeDashboardSearchItems)
          .filter((row) => homeDashboardSearchSelectedIds.has(Number(row?.id || 0)));
      }
      return [];
    }

    function getDashboardSingleSelectedRow() {
      const rows = getDashboardSelectedWorkbenchRows();
      return rows.length === 1 ? rows[0] : null;
    }

    function getDashboardSingleSelectedRowBySourceKind(sourceKind) {
      const normalizedSourceKind = String(sourceKind || "").trim().toUpperCase();
      if (normalizedSourceKind === "SLOT") {
        const source = Array.isArray(homeDashboardSlotSelectionSnapshot) && homeDashboardSlotSelectionSnapshot.length
          ? homeDashboardSlotSelectionSnapshot
          : (Array.isArray(homeDashboardSlotItems) ? homeDashboardSlotItems : []);
        const rows = source.filter((row) => homeDashboardSlotSelectedIds.has(Number(row?.id || 0)));
        return rows.length === 1 ? rows[0] : null;
      }
      if (normalizedSourceKind === "UNASSIGNED") {
        const rows = filterDashboardWorkbenchItems(homeDashboardUnassignedItems)
          .filter((row) => homeDashboardUnassignedSelectedIds.has(Number(row?.id || 0)));
        return rows.length === 1 ? rows[0] : null;
      }
      if (normalizedSourceKind === "SEARCH") {
        const rows = filterDashboardWorkbenchItems(homeDashboardSearchItems)
          .filter((row) => homeDashboardSearchSelectedIds.has(Number(row?.id || 0)));
        return rows.length === 1 ? rows[0] : null;
      }
      return null;
    }

    function getDashboardSlotRow(slotCode) {
      const code = String(slotCode || "").trim();
      if (!code) return null;
      return homeDashboardBySlot.find((row) => String(row?.slot_code || "").trim() === code) || null;
    }

    function dashboardSlotAllowsManualOrder(slotRow) {
      return String(slotRow?.cabinet_sort_policy || "ARTIST_RELEASE_TITLE").trim().toUpperCase() === "LABEL_ID";
    }

    function getDashboardDraggedOwnedItemId(event) {
      const stateId = Number(dashboardDraggedOwnedItemId || 0);
      if (stateId > 0) return stateId;
      const raw = event?.dataTransfer?.getData("text/plain") || "";
      const value = Number(raw || 0);
      return value > 0 ? value : 0;
    }

    function getDashboardDraggedSelectionIds(event) {
      const stateIds = Array.isArray(dashboardDraggedSelectionIds)
        ? dashboardDraggedSelectionIds.map((value) => Number(value || 0)).filter((value) => value > 0)
        : [];
      if (stateIds.length) return stateIds;
      const raw = String(event?.dataTransfer?.getData("text/x-dashboard-selection-ids") || "").trim();
      if (!raw) return [];
      try {
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed)
          ? parsed.map((value) => Number(value || 0)).filter((value) => value > 0)
          : [];
      } catch (_) {
        return [];
      }
    }

    function getDashboardDraggedSlotCode(event) {
      const stateCode = String(dashboardDraggedSlotCode || "").trim();
      if (stateCode) return stateCode;
      const raw = event?.dataTransfer?.getData("text/x-dashboard-slot-code") || "";
      return String(raw || "").trim();
    }

    function getDashboardDraggedSizeGroup(event) {
      const stateCode = String(dashboardDraggedSizeGroup || "").trim();
      if (stateCode) return stateCode;
      const raw = event?.dataTransfer?.getData("text/x-dashboard-size-group") || "";
      return String(raw || "").trim();
    }

    function getDashboardDraggedRows(event) {
      const selectedIds = getDashboardDraggedSelectionIds(event);
      if (!selectedIds.length) return [];
      return selectedIds
        .map((ownedItemId) => findDashboardOwnedItemRow(ownedItemId))
        .filter((row) => row && Number(row?.id || 0) > 0);
    }

    function renderDashboardMoveTargets() {
      return;
    }

    function applyDashboardSlotLocalOrder(orderedIds) {
      const currentItems = Array.isArray(homeDashboardSlotItems) ? homeDashboardSlotItems : [];
      const wanted = Array.isArray(orderedIds)
        ? orderedIds.map((value) => Number(value || 0)).filter((value) => value > 0)
        : [];
      if (!currentItems.length || !wanted.length) return;
      const currentById = new Map(currentItems.map((row) => [Number(row?.id || 0), row]));
      const nextItems = [];
      for (const ownedItemId of wanted) {
        const row = currentById.get(ownedItemId);
        if (row) nextItems.push({ ...row });
      }
      for (const row of currentItems) {
        const ownedItemId = Number(row?.id || 0);
        if (ownedItemId > 0 && wanted.includes(ownedItemId)) continue;
        nextItems.push({ ...row });
      }
      homeDashboardSlotItems = nextItems.map((row, index) => ({
        ...row,
        display_rank: (index + 1) * 10,
      }));
      updateDashboardSlotSelectionSnapshot();
      renderDashboardCabinetDetail();
    }

    function renderDashboardSlotItems(slotRow, cabinetGroup = null) {
      const titleEl = $("homeDashSlotItemsTitle");
      const metaEl = $("homeDashSlotItemsMeta");
      const root = $("homeDashSlotItems");
      if (!titleEl || !metaEl || !root) return;
      homeDashboardHoveredItemId = null;
      const policyLabelEl = $("homeDashSlotSortPolicyLabel");
      if (policyLabelEl) {
        policyLabelEl.textContent = slotRow ? cabinetSortPolicyLabel(slotRow.cabinet_sort_policy) : "—";
      }
      root.classList.remove(
        "dashboard-cabinet-overview-grid",
        "dashboard-slot-pagegrid",
        "dashboard-slot-pagegrid--lp",
        "dashboard-slot-listview",
        "dashboard-slot-shelfview",
        "dashboard-slot-shelfview--lp",
        "dashboard-cabinet-overview-grid--surface",
      );
      const occupancy = slotRow ? dashboardCabinetOccupancyLabel(slotRow) : null;
      const isUnassignedSlot = String(slotRow?.slot_code || "").trim() === "UNASSIGNED";
      const occupancyText = occupancy
        ? t("dashboard.cover_flow.meta.occupancy", {
          percent: occupancy.percentText,
          used: occupancy.usedText ? ` (${occupancy.usedText})` : "",
        })
        : "";
      const setSlotMeta = (statusText = "", includeOccupancy = true) => {
        const metaBits = [(includeOccupancy ? occupancyText : ""), statusText].filter(Boolean);
        setHiddenState(metaEl, false);
        metaEl.textContent = metaBits.join(" | ");
      };

      if (!slotRow && cabinetGroup && !cabinetGroup.isUnassigned && !cabinetGroup.isOverflow) {
        titleEl.textContent = t("dashboard.cabinet.overview_title", { title: cabinetGroup.title });
        metaEl.textContent = t("dashboard.cover_flow.meta_idle");
        root.classList.add("dashboard-cabinet-overview-grid");
        root.classList.add("dashboard-cabinet-overview-grid--surface");
        const freeSlots = Math.max(0, Number(cabinetGroup.slotCount || 0) - Number(cabinetGroup.filledSlotCount || 0));
        root.innerHTML = [
          { label: t("dashboard.cabinet.meta.stored_items", { count: "" }).trim(), value: countWithUnit(cabinetGroup.total) },
          { label: t("dashboard.cabinet.meta.used_slots", { count: "" }).trim(), value: formatCount(cabinetGroup.filledSlotCount) },
          { label: t("dashboard.cabinet.meta.free_slots", { count: "" }).trim(), value: formatCount(freeSlots) },
          { label: t("dashboard.cabinet.meta.floors", { count: "" }).trim(), value: dashboardFloorsLabel(cabinetGroup.floorCount) },
          { label: t("dashboard.cabinet.meta.max_cells", { count: "" }).trim(), value: dashboardMaxCellsLabel(cabinetGroup.cellCount) },
          { label: t("dashboard.cabinet.meta.size_group", { value: "" }).trim(), value: cabinetGroup.sizeGroupText !== "-" ? cabinetGroup.sizeGroupText : t("common.mixed") },
        ].map((item) => `
          <div class="dashboard-cabinet-overview-card">
            <span>${escapeHtml(item.label)}</span>
            <strong>${escapeHtml(item.value)}</strong>
          </div>
        `).join("");
        updateDashboardSlotPageControls(null);
        renderDashboardSelectionSummary();
        return;
      }

      if (!slotRow) {
        const snapshotItems = Array.isArray(homeDashboardSlotSelectionSnapshot) ? homeDashboardSlotSelectionSnapshot : [];
        const sourceSlotCode = String(snapshotItems[0]?.slot_code || "").trim();
        const sourceSlotRow = sourceSlotCode ? getDashboardSlotRow(sourceSlotCode) : null;
        const visibleSnapshotItems = sortDashboardSlotItems(filterDashboardSlotItemsByMedia(snapshotItems), sourceSlotRow);
        if (visibleSnapshotItems.length && sourceSlotRow) {
          const sliceInfo = dashboardSlotPageSlice(visibleSnapshotItems, sourceSlotRow);
          titleEl.textContent = t("dashboard.selection.title");
          const rangeText = dashboardSlotSupportsPaging()
            ? `${sliceInfo.start + 1}-${sliceInfo.end}/${formatCount(sliceInfo.total)}`
            : t("dashboard.cover_flow.meta.all_count", { count: countWithUnit(sliceInfo.total) });
          metaEl.textContent = [
            t("dashboard.selection.summary.keep_selected", { count: countWithUnit(homeDashboardSlotSelectedIds.size) }),
            rangeText,
            t("dashboard.selection.meta.pick_other_slot"),
          ].join(" | ");
          setHiddenState(metaEl, false);
          applyDashboardSlotViewMode(root, sourceSlotRow);
          if (homeDashboardSlotViewMode === "LIST") {
            root.innerHTML = sliceInfo.items.map((row, pageIndex) => dashboardSlotListItemHtml(row, sliceInfo.start + pageIndex)).join("");
          } else if (homeDashboardSlotViewMode === "SHELF") {
            root.innerHTML = sliceInfo.items.map((row, pageIndex) => dashboardSlotShelfItemHtml(row, sliceInfo.start + pageIndex)).join("");
            applyDashboardShelfNeighborHighlight(root);
            restoreDashboardShelfScroll(root);
            requestAnimationFrame(() => scrollDashboardShelfSelectionIntoView(root));
          } else {
            root.innerHTML = sliceInfo.items.map((row, pageIndex) => dashboardSlotItemHtml(row, sliceInfo.start + pageIndex)).join("");
          }
          updateDashboardSlotPageControls(sliceInfo);
          renderDashboardSelectionSummary();
          return;
        }
        titleEl.textContent = t("dashboard.selection.slot_title");
        metaEl.textContent = isShellReadOnly()
          ? t("dashboard.cover_flow.meta.read_only")
          : t("dashboard.cover_flow.meta.select_and_open");
        setHiddenState(metaEl, false);
        root.innerHTML = `<div class='mini muted'>${escapeHtml(t("dashboard.selection.state.no_slot"))}</div>`;
        updateDashboardSlotPageControls(null);
        renderDashboardSelectionSummary();
        return;
      }

      titleEl.textContent = t("dashboard.cover_flow.title");

      if (isUnassignedSlot) {
        root.innerHTML = `<div class='mini muted'>${escapeHtml(t("dashboard.cover_flow.state.unslotted_block"))}</div>`;
        setSlotMeta(t("dashboard.cover_flow.state.unslotted_block"), false);
        updateDashboardSlotPageControls(null);
        renderDashboardSelectionSummary();
        return;
      }

      if (homeDashboardSlotItemsLoading && homeDashboardSelectedSlotCode === String(slotRow.slot_code || "").trim()) {
        root.innerHTML = `<div class='mini muted'>${escapeHtml(t("dashboard.cover_flow.state.loading"))}</div>`;
        setSlotMeta(t("dashboard.cover_flow.state.loading"));
        updateDashboardSlotPageControls(null);
        renderDashboardSelectionSummary();
        return;
      }

      if (homeDashboardSlotItemsSlotCode !== String(slotRow.slot_code || "").trim()) {
        root.innerHTML = `<div class='mini muted'>${escapeHtml(t("dashboard.cover_flow.state.click_to_load"))}</div>`;
        setSlotMeta(t("dashboard.cover_flow.state.click_to_load"));
        updateDashboardSlotPageControls(null);
        renderDashboardSelectionSummary();
        return;
      }

      const items = sortDashboardSlotItems(filterDashboardSlotItemsByMedia(Array.isArray(homeDashboardSlotItems) ? homeDashboardSlotItems : []), slotRow);
      if (!items.length) {
        root.innerHTML = `<div class='mini muted'>${escapeHtml(t("dashboard.cover_flow.state.empty"))}</div>`;
        setSlotMeta(t("dashboard.cover_flow.state.empty"));
        updateDashboardSlotPageControls(null);
        renderDashboardSelectionSummary();
        return;
      }

      const sliceInfo = dashboardSlotPageSlice(items, slotRow);
      applyDashboardSlotViewMode(root, slotRow);
      if (homeDashboardSlotViewMode === "LIST") {
        root.innerHTML = sliceInfo.items.map((row, pageIndex) => dashboardSlotListItemHtml(row, sliceInfo.start + pageIndex)).join("");
      } else if (homeDashboardSlotViewMode === "SHELF") {
        root.innerHTML = sliceInfo.items.map((row, pageIndex) => dashboardSlotShelfItemHtml(row, sliceInfo.start + pageIndex)).join("");
        applyDashboardShelfNeighborHighlight(root);
        restoreDashboardShelfScroll(root);
        requestAnimationFrame(() => scrollDashboardShelfSelectionIntoView(root));
      } else {
        root.innerHTML = sliceInfo.items.map((row, pageIndex) => dashboardSlotItemHtml(row, sliceInfo.start + pageIndex)).join("");
      }
      updateDashboardSlotPageControls(sliceInfo);
      const rangeText = dashboardSlotSupportsPaging()
        ? `${sliceInfo.start + 1}-${sliceInfo.end}/${formatCount(sliceInfo.total)}`
        : t("dashboard.cover_flow.meta.all_count", { count: countWithUnit(sliceInfo.total) });
      setSlotMeta(rangeText);
      renderDashboardSelectionSummary();
    }

    function syncDashboardConsoleFocusState(expanded) {
      const root = $("homeDashboardCard");
      if (!root) return;
      root.classList.toggle("dashboard-console-shell--cabinet-focus", Boolean(expanded));
    }

    function syncDashboardCabinetSelectionMemory() {
      try {
        const cabinetKey = String(homeDashboardSelectedCabinetKey || "").trim();
        const slotCode = String(homeDashboardSelectedSlotCode || "").trim();
        if (!cabinetKey) {
          window.sessionStorage.removeItem(DASHBOARD_CABINET_SELECTION_STORAGE_KEY);
          return;
        }
        const payload = { cabinet_key: cabinetKey };
        if (slotCode) payload.slot_code = slotCode;
        window.sessionStorage.setItem(DASHBOARD_CABINET_SELECTION_STORAGE_KEY, JSON.stringify(payload));
        try { window.localStorage.setItem(DASHBOARD_CABINET_SELECTION_STORAGE_KEY + '_persist', JSON.stringify(payload)); } catch (_) {}
      } catch (_err) {
        // ignore sessionStorage write errors
      }
    }

    function renderDashboardCabinetDetail() {
      const panel = $("homeDashCabinetDetail");
      const titleEl = $("homeDashCabinetTitle");
      const metaEl = $("homeDashCabinetMeta");
      const floorsRoot = $("homeDashCabinetFloors");
      if (!panel || !titleEl || !metaEl || !floorsRoot) return;

      const groups = buildDashboardCabinetGroups(homeDashboardBySlot);
      const group = groups.find((item) => item.key === homeDashboardSelectedCabinetKey) || null;
      if (!group) {
        syncDashboardCabinetSelectionMemory();
        syncDashboardConsoleFocusState(false);
        setHiddenState(panel, true);
        homeDashSurfacePanel = "";
        renderDashboardSurfaceDock();
        renderDashboardSlotItems(null);
        return;
      }

      syncDashboardConsoleFocusState(true);
      setDisplayMode(panel, "grid");
      titleEl.textContent = group.title;
      setHiddenState(floorsRoot, true);
      floorsRoot.innerHTML = "";
      const metaBits = [
        !group.isUnassigned && !group.isOverflow && group.cabinetCount > 1 ? t("dashboard.cabinet.meta.connected_cabinets", { count: formatCount(group.cabinetCount) }) : null,
        !group.isUnassigned && !group.isOverflow ? dashboardFloorsLabel(group.floorCount) : null,
        !group.isUnassigned && !group.isOverflow ? dashboardMaxCellsLabel(group.cellCount) : null,
        dashboardSlotsLabel(group.slotCount),
        dashboardUsedSlotsLabel(group.filledSlotCount),
        dashboardStoredItemsLabel(group.total),
        !group.isUnassigned && !group.isOverflow && group.domainText && group.domainText !== "-" ? dashboardDomainMetaLabel(group.domainText) : null,
        group.sizeGroupText !== "-" ? dashboardSizeGroupMetaLabel(group.sizeGroupText) : null,
      ].filter(Boolean);
      metaEl.innerHTML = metaBits.map((text) => `<span>${escapeHtml(text)}</span>`).join("");
      renderDashboardSurfaceDock();

      if (!group.rows.some((row) => String(row.slot_code || "").trim() === String(homeDashboardSelectedSlotCode || "").trim())) {
        homeDashboardSelectedSlotCode = null;
        homeDashboardSlotItems = [];
        homeDashboardSlotItemsSlotCode = null;
      }

      syncDashboardCabinetSelectionMemory();

      if (group.isUnassigned) {
        renderDashboardSlotItems(group.rows[0] || null);
        return;
      }

      if (group.isOverflow) {
        const activeRow = group.rows.find((row) => String(row.slot_code || "").trim() === String(homeDashboardSelectedSlotCode || "").trim()) || null;
        renderDashboardSlotItems(activeRow);
        return;
      }

      const activeRow = group.rows.find((row) => String(row.slot_code || "").trim() === String(homeDashboardSelectedSlotCode || "").trim()) || null;
      renderDashboardSlotItems(activeRow, group);
    }

    function summarizeStorageCabinets(rows) {
      const grouped = new Map();
      for (const raw of Array.isArray(rows) ? rows : []) {
        if (!raw || raw.is_overflow_zone) continue;
        const cabinetName = String(raw.cabinet_name || "").trim();
        if (!cabinetName) continue;
        if (!grouped.has(cabinetName)) {
          grouped.set(cabinetName, {
            cabinet_name: cabinetName,
            group_names: new Set(),
            group_orders: new Set(),
            domain_codes: new Set(),
            floors: new Set(),
            cellsByFloor: new Map(),
            slot_count: 0,
            size_groups: new Set(),
            sort_policies: new Set(),
            max_thickness_values: new Set(),
          });
        }
        const item = grouped.get(cabinetName);
        if (raw.cabinet_group_name) item.group_names.add(String(raw.cabinet_group_name));
        if (raw.cabinet_group_order !== null && raw.cabinet_group_order !== undefined && String(raw.cabinet_group_order).trim() !== "") {
          const order = Number(raw.cabinet_group_order || 0);
          if (Number.isFinite(order) && order > 0) item.group_orders.add(order);
        }
        if (raw.cabinet_domain_code) item.domain_codes.add(String(raw.cabinet_domain_code));
        const floorCode = String(raw.column_code || "").trim();
        const cellCode = String(raw.cell_code || "").trim();
        if (floorCode) {
          item.floors.add(floorCode);
          if (!item.cellsByFloor.has(floorCode)) item.cellsByFloor.set(floorCode, new Set());
          if (cellCode) item.cellsByFloor.get(floorCode).add(cellCode);
        }
        if (raw.allowed_size_group) item.size_groups.add(String(raw.allowed_size_group));
        if (raw.cabinet_sort_policy) item.sort_policies.add(String(raw.cabinet_sort_policy));
        if (raw.max_thickness_mm !== null && raw.max_thickness_mm !== undefined && String(raw.max_thickness_mm).trim() !== "") {
          const mm = Number(raw.max_thickness_mm || 0);
          if (Number.isFinite(mm) && mm > 0) item.max_thickness_values.add(mm);
        }
        item.slot_count += 1;
      }

      return Array.from(grouped.values())
        .map((item) => {
          const floorCodes = Array.from(item.floors.values()).sort(compareCodeValue);
          const cellCodes = Array.from(
            new Set(
              Array.from(item.cellsByFloor.values()).flatMap((set) => Array.from(set.values()))
            )
          ).sort(compareCodeValue);
          let maxCellCount = 0;
          let minCellCount = Number.MAX_SAFE_INTEGER;
          for (const set of item.cellsByFloor.values()) {
            maxCellCount = Math.max(maxCellCount, set.size);
            minCellCount = Math.min(minCellCount, set.size);
          }
          const sizeGroups = Array.from(item.size_groups.values());
          const domainCodes = Array.from(item.domain_codes.values());
          const maxThicknessValues = Array.from(item.max_thickness_values.values());
          const sizeGroupCode = sizeGroups.length === 1 ? String(sizeGroups[0] || "").trim().toUpperCase() : "";
          const floorStart = Number.parseInt(String(floorCodes[0] || "1"), 10) || 1;
          const cellStart = Number.parseInt(String(cellCodes[0] || "1"), 10) || 1;
          const isRectangular = !item.floors.size || minCellCount === maxCellCount;
          return {
            cabinet_name: item.cabinet_name,
            cabinet_domain_code: domainCodes.length === 1 ? String(domainCodes[0] || "").trim().toUpperCase() : "",
            cabinet_group_name: item.group_names.size === 1 ? Array.from(item.group_names.values())[0] : "",
            cabinet_group_order: item.group_orders.size === 1 ? Number(Array.from(item.group_orders.values())[0] || 0) : 0,
            floor_count: item.floors.size,
            cell_count: maxCellCount,
            slot_count: item.slot_count,
            floor_start: floorStart,
            cell_start: cellStart,
            cabinet_sort_policy: item.sort_policies.size === 1
              ? Array.from(item.sort_policies.values())[0]
              : "ARTIST_RELEASE_TITLE",
            max_thickness_mm: maxThicknessValues.length === 1 ? Number(maxThicknessValues[0] || 0) : 0,
            size_group_code: sizeGroupCode || "STD",
            size_group: sizeGroups.length === 1
              ? dashboardSizeGroupLabel(sizeGroups[0])
              : sizeGroups.map((value) => dashboardSizeGroupLabel(value)).join(", "),
            domain_text: domainCodes.length === 1
              ? dashboardDomainLabel(domainCodes[0])
              : domainCodes.length ? domainCodes.map((value) => dashboardDomainLabel(value)).join(", ") : "-",
            can_safe_edit: Boolean(sizeGroupCode) && isRectangular,
          };
        })
        .sort((a, b) => {
          const groupCompare = compareCodeValue(a.cabinet_group_name || a.cabinet_name, b.cabinet_group_name || b.cabinet_name);
          if (groupCompare !== 0) return groupCompare;
          const orderCompare = compareCodeValue(a.cabinet_group_order || 0, b.cabinet_group_order || 0);
          if (orderCompare !== 0) return orderCompare;
          return a.cabinet_name.localeCompare(b.cabinet_name, "ko");
        });
    }

    function renderDashboardChipGroup(containerId, rows, labelFn) {
      const root = $(containerId);
      if (!root) return;
      let list = Array.isArray(rows) ? rows : [];
      list = list.filter((row) => (row.count ?? 0) > 0);
      if (!list.length) {
        root.innerHTML = `<div class='mini muted'>${escapeHtml(t("common.data_empty"))}</div>`;
        return;
      }
      const _chipTotal = list.reduce((s, r) => s + (r.count ?? 0), 0);
      root.innerHTML = list.map((row) => {
        const _barPct = _chipTotal > 0 ? Math.round((row.count / _chipTotal) * 100) : 0;
        return `<div class="dashboard-chip">
          <span>${escapeHtml(labelFn(row.value ?? row.status ?? row.category))}</span>
          <strong>${formatCount(row.count)}</strong>
          <span class="dashboard-chip-bar" style="width:${_barPct}%" title="${_barPct}%"></span>
        </div>`;
      }).join("");
    }

    function dashboardCabinetVisualCapacity(slotRow) {
      const sizeGroup = String(slotRow?.allowed_size_group || "").trim().toUpperCase();
      const slotCode = String(slotRow?.slot_code || "").trim().toUpperCase();
      const cabinetName = String(slotRow?.cabinet_name || "").trim().toUpperCase();
      if (slotCode.startsWith("LP") || cabinetName.includes("LP") || sizeGroup === "LP" || sizeGroup === "LP10" || sizeGroup === "LP7" || sizeGroup === "OVERSIZE") return 50;
      if (slotCode.startsWith("CD") || cabinetName.includes("CD") || sizeGroup === "STD") return 40;
      if (sizeGroup === "CASSETTE") return 28;
      if (sizeGroup === "8TRACK") return 28;
      if (sizeGroup === "REEL_TO_REEL") return 32;
      if (sizeGroup === "BOOK") return 30;
      if (sizeGroup === "GOODS") return 20;
      return 40;
    }

    function dashboardCabinetOccupancyRatio(slotRow) {
      const occupancyRatio = Number(slotRow?.occupancy_ratio);
      if (Number.isFinite(occupancyRatio)) return Math.max(0, occupancyRatio);
      const occupancyPercent = Number(slotRow?.occupancy_percent);
      if (Number.isFinite(occupancyPercent)) return Math.max(0, occupancyPercent / 100);
      return 0;
    }

    function dashboardCabinetOccupancyLabel(slotRow) {
      const ratio = dashboardCabinetOccupancyRatio(slotRow);
      const percentText = `${Math.max(0, Math.floor(ratio * 100)).toFixed(0)}%`;
      const capacity = Number(slotRow?.capacity_mm);
      const usedThickness = Number(slotRow?.used_thickness_mm);
      const usedText = Number.isFinite(usedThickness) && Number.isFinite(capacity) && capacity > 0
        ? `${Math.round(usedThickness)}/${Math.round(capacity)}mm`
        : "";
      return {
        percentText,
        usedText,
      };
    }

    function dashboardCabinetMapCellTone(slotRow) {
      const ratio = dashboardCabinetOccupancyRatio(slotRow);
      const highOccupancy = ratio >= 0.7;
      const overCapacity = ratio >= 1;
      if (overCapacity) return "tone-over";
      if (highOccupancy) return "tone-high";
      if (ratio > 0) return "tone-filled";
      return "tone-empty";
    }

    function dashboardCabinetMapSizeClass(slotRow) {
      const sizeGroup = String(slotRow?.allowed_size_group || "").trim().toUpperCase();
      if (sizeGroup === "LP") return "size-lp";
      if (sizeGroup === "LP10") return "size-lp10";
      if (sizeGroup === "LP7") return "size-lp7";
      if (sizeGroup === "OVERSIZE") return "size-oversize";
      if (sizeGroup === "BOOK") return "size-book";
      if (sizeGroup === "CASSETTE") return "size-cassette";
      if (sizeGroup === "8TRACK" || sizeGroup === "REEL_TO_REEL") return "size-tape";
      if (sizeGroup === "GOODS") return "size-goods";
      return "size-std";
    }

    function dashboardCabinetMapTypeStamp(slotRow) {
      const sizeGroup = String(slotRow?.allowed_size_group || "").trim().toUpperCase();
      if (sizeGroup === "LP") return "LP";
      if (sizeGroup === "LP10") return '10"';
      if (sizeGroup === "LP7") return '7"';
      if (sizeGroup === "OVERSIZE") return "BX";
      if (sizeGroup === "BOOK") return "BK";
      if (sizeGroup === "CASSETTE") return "CS";
      if (sizeGroup === "8TRACK" || sizeGroup === "REEL_TO_REEL") return "TP";
      if (sizeGroup === "GOODS") return "GD";
      return "CD";
    }

    function dashboardCabinetGroupSizeClass(group) {
      const sizeGroups = Array.from(new Set(
        (Array.isArray(group?.rows) ? group.rows : [])
          .map((row) => String(row?.allowed_size_group || "").trim().toUpperCase())
          .filter(Boolean)
      ));
      if (sizeGroups.length !== 1) return "size-std";
      return dashboardCabinetMapSizeClass({ allowed_size_group: sizeGroups[0] });
    }

    function dashboardCabinetGroupTypeStamp(group) {
      const sizeGroups = Array.from(new Set(
        (Array.isArray(group?.rows) ? group.rows : [])
          .map((row) => String(row?.allowed_size_group || "").trim().toUpperCase())
          .filter(Boolean)
      ));
      if (sizeGroups.length !== 1) return "MIX";
      return dashboardCabinetMapTypeStamp({ allowed_size_group: sizeGroups[0] });
    }

    function dashboardSlotLegendEntries(rows) {
      const groups = buildDashboardCabinetGroups(Array.isArray(rows) ? rows : [])
        .filter((group) => !group.isUnassigned && !group.isOverflow);
      const presentCodes = new Set();
      groups.forEach((group) => {
        (Array.isArray(group?.rows) ? group.rows : []).forEach((row) => {
          const code = String(row?.allowed_size_group || "STD").trim().toUpperCase() || "STD";
          presentCodes.add(code);
        });
      });
      const order = ["STD", "BOOK", "LP", "LP10", "LP7", "OVERSIZE", "CASSETTE", "8TRACK", "REEL_TO_REEL", "GOODS"];
      const metaByCode = {
        STD: { sizeClass: "size-std", label: t("common.size_group.std") },
        BOOK: { sizeClass: "size-book", label: t("common.size_group.book") },
        LP: { sizeClass: "size-lp", label: t("common.size_group.lp") },
        LP10: { sizeClass: "size-lp10", label: t("common.size_group.lp10") },
        LP7: { sizeClass: "size-lp7", label: t("common.size_group.lp7") },
        OVERSIZE: { sizeClass: "size-oversize", label: t("common.size_group.oversize") },
        CASSETTE: { sizeClass: "size-cassette", label: t("common.size_group.cassette") },
        "8TRACK": { sizeClass: "size-tape", label: t("common.size_group.8track") },
        REEL_TO_REEL: { sizeClass: "size-tape", label: t("common.size_group.reel_to_reel") },
        GOODS: { sizeClass: "size-goods", label: t("common.size_group.goods") },
      };
      return order
        .filter((code) => presentCodes.has(code) && metaByCode[code])
        .map((code) => ({ code, ...metaByCode[code] }));
    }

    function renderDashboardSlotMapLegend(rows) {
      const legendRoot = $("homeDashSlotMapLegend");
      if (!legendRoot) return;
      const entries = dashboardSlotLegendEntries(rows);
      legendRoot.hidden = entries.length === 0;
      legendRoot.innerHTML = entries.map((entry) => `
        <span class="dashboard-slot-legend-chip ${entry.sizeClass}">${escapeHtml(entry.label)}</span>
      `).join("");
    }

    function dashboardCabinetMapCellLabel(slotRow, group = null) {
      const groupedOrdering = Boolean(group?.groupName && Number(group?.cabinetCount || 0) > 1);
      if (groupedOrdering) {
        const floorCode = String(slotRow?.column_code || "").trim();
        const slotCode = String(slotRow?.slot_code || "").trim();
        if (floorCode && slotCode) {
          const floorRows = group.rows.filter((row) => String(row?.column_code || "").trim() === floorCode);
          const index = floorRows.findIndex((row) => String(row?.slot_code || "").trim() === slotCode);
          if (index >= 0) {
            return dashboardCellCodeLabel(String(index + 1).padStart(2, "0"));
          }
        }
      }
      const cellCode = String(slotRow?.cell_code || "").trim();
      if (cellCode) return dashboardCellCodeLabel(cellCode);
      const slotCode = String(slotRow?.slot_code || "").trim();
      return slotCode || t("common.cell");
    }

    function dashboardSlotFirstItemHintText(slotRow) {
      const artist = String(slotRow?.first_item_artist_or_brand || "").trim();
      let title = String(slotRow?.first_item_title || "").trim();
      const releaseYear = Number(slotRow?.first_item_release_year || 0) || 0;
      if (!artist || !title) return "";
      const artistPrefix = `${artist} - `.toLowerCase();
      if (title.toLowerCase().startsWith(artistPrefix)) {
        title = title.slice(artistPrefix.length).trim() || title;
      }
      return releaseYear > 0
        ? `${artist} - ${title} (${releaseYear})`
        : `${artist} - ${title}`;
    }

    function dashboardSlotHoverHintText(slotRow, group = null) {
      const displayLabel = dashboardCabinetMapCellLabel(slotRow, group);
      const summary = slotRow?.stored_items_summary || "";
      const count = Number(slotRow?.count || 0);
      if (summary) {
        return `${displayLabel} (${count}개 상품 진열됨)\n----------------------------------------\n${summary}`;
      }
      return `${displayLabel} · 빈 슬롯`;
    }

    function updateDashboardSlotGridControls(groups, pageEntries, page) {
      const prevBtn = $("homeDashSlotGridPrevBtn");
      const nextBtn = $("homeDashSlotGridNextBtn");
      const infoEl = $("homeDashSlotGridInfo");
      const total = Array.isArray(groups) ? groups.length : 0;
      const pages = Array.isArray(pageEntries) && pageEntries.length
        ? pageEntries
        : [{ start: 0, end: Math.min(total, 1), items: [] }];
      const pageIndex = Math.min(Math.max(0, Number(page || 0)), Math.max(0, pages.length - 1));
      const currentPage = pages[pageIndex] || { start: 0, end: 0, items: [] };
      const visibleStart = total > 0 ? Number(currentPage.start || 0) + 1 : 0;
      const visibleEnd = total > 0 ? Number(currentPage.end || 0) : 0;
      if (infoEl) {
        infoEl.textContent = total > 0
          ? `${visibleStart}-${visibleEnd} / ${formatCount(total)}`
          : "0-0 / 0";
      }
      if (prevBtn) prevBtn.disabled = pages.length <= 1 || pageIndex <= 0;
      if (nextBtn) nextBtn.disabled = pages.length <= 1 || pageIndex >= pages.length - 1;
    }

    function renderDashboardSlotCards(rows, totalInCollection) {
      const root = $("homeDashSlotGrid");
      if (!root) return;
      const list = Array.isArray(rows) ? rows : [];
      homeDashboardBySlot = list;
      homeDashboardInCollectionItems = Math.max(0, Number(totalInCollection || 0));
      renderDashboardSlotMapLegend(list);
      if (!list.length) {
        root.classList.remove("is-single-board");
        root.innerHTML = `<div class='mini muted'>${escapeHtml(t("dashboard.mapping.empty"))}</div>`;
        homeDashboardSelectedCabinetKey = null;
        homeDashboardSelectedSlotCode = null;
        homeDashboardSlotItems = [];
        homeDashboardSlotItemsSlotCode = null;
        resetDashboardSlotPage();
        renderDashboardCabinetDetail();
        updateDashboardSlotGridControls([], [], 0);
        return;
      }
      const groups = buildDashboardCabinetGroups(list).filter((group) => !group.isUnassigned);
      if (homeDashboardSelectedCabinetKey && !groups.some((group) => group.key === homeDashboardSelectedCabinetKey)) {
        homeDashboardSelectedCabinetKey = null;
        homeDashboardSelectedSlotCode = null;
        homeDashboardSlotItems = [];
        homeDashboardSlotItemsSlotCode = null;
        resetDashboardSlotPage();
        resetDashboardSlotSelection();
      }
      const pages = buildDashboardSlotGroupPages(groups);
      const selectedGroupIndex = homeDashboardSelectedCabinetKey
        ? groups.findIndex((group) => group.key === homeDashboardSelectedCabinetKey)
        : -1;
      const pageCount = Math.max(1, pages.length);
      if (selectedGroupIndex >= 0 && homeDashboardSlotGridFollowSelection) {
        homeDashboardSlotGridPage = Math.max(0, pages.findIndex((page) => selectedGroupIndex >= page.start && selectedGroupIndex < page.end));
      } else {
        homeDashboardSlotGridPage = Math.min(Math.max(0, homeDashboardSlotGridPage), pageCount - 1);
      }
      const currentPage = pages[homeDashboardSlotGridPage] || pages[0] || { items: [] };
      const visibleGroups = Array.isArray(currentPage.items) ? currentPage.items : [];
      updateDashboardSlotGridControls(groups, pages, homeDashboardSlotGridPage);
      root.classList.toggle("is-single-board", visibleGroups.length <= 1);

      root.innerHTML = visibleGroups.map((group) => {
        const boardClass = [
          "dashboard-cabinet-board",
          homeDashboardSelectedCabinetKey === group.key ? "active" : "",
          group.isOverflow ? "overflow" : "",
          group.isUnassigned ? "unassigned" : "",
        ].filter(Boolean).join(" ");
        const _groupAvgRatio = (group.isOverflow || group.isUnassigned || !group.rows.length)
          ? 0
          : group.rows.reduce((s, r) => s + dashboardCabinetOccupancyRatio(r), 0) / group.rows.length;
        const _groupFillPct = Math.min(100, Math.round(_groupAvgRatio * 100));
        const _groupFillTone = _groupAvgRatio >= 1 ? "tone-over" : _groupAvgRatio >= 0.7 ? "tone-high" : _groupAvgRatio > 0 ? "tone-filled" : "tone-empty";
        const fillBarHtml = (group.isOverflow || group.isUnassigned)
          ? ""
          : `<div class="dashboard-cabinet-fillbar-wrap"><div class="dashboard-cabinet-fillbar ${_groupFillTone}" style="width:${_groupFillPct}%"></div></div>`;
        const metaHtml = group.isOverflow
          ? [
              `<span>${escapeHtml(t("dashboard.cabinet.meta.slots", { count: formatCount(group.slotCount) }))}</span>`,
              `<span>${escapeHtml(t("dashboard.cabinet.meta.stored_items", { count: countWithUnit(group.total) }))}</span>`
            ].join("")
          : [
              group.cabinetCount > 1 ? `<span>${escapeHtml(t("dashboard.cabinet.meta.connected_cabinets", { count: formatCount(group.cabinetCount) }))}</span>` : null,
              `<span>${escapeHtml(dashboardFloorsLabel(group.floorCount))}</span>`,
              `<span>${escapeHtml(t("dashboard.cabinet.meta.used_slots", { count: `${formatCount(group.filledSlotCount)} / ${formatCount(group.slotCount)}` }))}</span>`,
              `<span>${escapeHtml(dashboardStoredItemsLabel(group.total))}</span>`,
              group.domainText && group.domainText !== "-" ? `<span>${escapeHtml(dashboardDomainMetaLabel(group.domainText))}</span>` : null,
            ].filter(Boolean).join("");
      const mapHtml = group.isOverflow
        ? ""
        : `
            <div class="dashboard-cabinet-map">
              ${group.floorCodes.map((floorCode) => {
                const floorRows = group.rows.filter((row) => String(row?.column_code || "").trim() === floorCode);
                return `
                  <div class="dashboard-cabinet-map-floor">
                    <div class="dashboard-cabinet-map-floorcode">${escapeHtml(dashboardColumnCodeLabel(floorCode))}</div>
                <div class="dashboard-cabinet-map-cells cell-count-${Math.max(1, floorRows.length)}">
                    ${floorRows.map((row) => {
                        const slotCode = String(row?.slot_code || "").trim();
                        const occupancy = dashboardCabinetOccupancyLabel(row);
                        const toneClass = dashboardCabinetMapCellTone(row);
                        const active = slotCode && slotCode === String(homeDashboardSelectedSlotCode || "").trim();
                        const sizeClass = dashboardCabinetMapSizeClass(row);
                        const typeStamp = dashboardCabinetMapTypeStamp(row);
                        const hoverTitle = dashboardSlotHoverHintText(row, group);
                        const occupancyMetaText = occupancy.usedText
                          ? `(${occupancy.usedText})`
                          : "";
                        const _cellRatio = dashboardCabinetOccupancyRatio(row);
                        const _cellFillPct = Math.min(200, Math.round(_cellRatio * 100));
                        return `
                          <button
                            class="dashboard-cabinet-map-cell ${toneClass} ${active ? "active" : ""} ${sizeClass}"
                            type="button"
                            data-dashboard-map-slot-code="${escapeHtml(slotCode)}"
                            aria-label="${escapeHtml(`${dashboardCabinetMapCellLabel(row, group)} ${occupancy.percentText} / ${occupancy.usedText || ""}`)}"
                            title="${escapeHtml(hoverTitle)}"
                            style="--cell-fill:${_cellFillPct}%"
                          >
                            <span class="dashboard-cabinet-map-celltype ${sizeClass}">${escapeHtml(typeStamp)}</span>
                            <span class="dashboard-cabinet-map-cellcode">${escapeHtml(dashboardCabinetMapCellLabel(row, group))}</span>
                            <strong class="dashboard-cabinet-map-cellcount">${escapeHtml(occupancy.percentText)}</strong>
                            <span class="dashboard-cabinet-map-cellmeta">${escapeHtml(occupancyMetaText)}</span>
                          </button>
                        `;
                      }).join("")}
                    </div>
                  </div>
                `;
              }).join("")}
            </div>
          `;
        return `
          <section class="${boardClass}">
            <div class="dashboard-cabinet-headbar">
              <button class="dashboard-cabinet-headbtn" type="button" data-dashboard-cabinet-key="${encodeURIComponent(group.key)}">
                <div class="dashboard-cabinet-head">
                  <div class="dashboard-cabinet-head-copy">
                    <div class="dashboard-cabinet-headline">
                      <span class="dashboard-cabinet-type-stamp ${dashboardCabinetGroupSizeClass(group)}">${escapeHtml(dashboardCabinetGroupTypeStamp(group))}</span>
                      <strong>${escapeHtml(group.title)}</strong>
                    </div>
                    ${(group.isOverflow || group.isUnassigned)
                      ? `<div class="dashboard-cabinet-head-flags">
                          ${group.isOverflow ? `<span class="dashboard-cabinet-head-flag dashboard-cabinet-head-flag--overflow">${escapeHtml(t("dashboard.cabinet.flag.overflow"))}</span>` : ""}
                          ${group.isUnassigned ? `<span class="dashboard-cabinet-head-flag dashboard-cabinet-head-flag--unassigned">${escapeHtml(t("dashboard.cabinet.flag.unassigned"))}</span>` : ""}
                        </div>`
                      : ""}
                    ${group.cabinetCount > 1 && group.cabinetNamesText
                      ? `<span class="dashboard-cabinet-head-sub">${escapeHtml(group.cabinetNamesText)}</span>`
                      : ""}
                  </div>
                </div>
                <div class="dashboard-cabinet-summary-meta">${metaHtml}</div>
                ${fillBarHtml}
              </button>
              <button
                class="btn ghost tiny dashboard-slot-actionbtn dashboard-cabinet-refreshbtn"
                type="button"
                data-dashboard-cabinet-refresh="${encodeURIComponent(group.key)}"
                title="${escapeHtml(t("dashboard.cover_flow.action.refresh"))}"
                aria-label="${escapeHtml(t("dashboard.cover_flow.action.refresh"))}"
              ><span class="dashboard-cabinet-refreshicon" aria-hidden="true">↻</span></button>
            </div>
            ${mapHtml}
          </section>
        `;
      }).join("");
      renderDashboardCabinetDetail();
      if (homePreviewContextItem || homeSelectedContextItem) renderOpsLibraryContextDefault();
    }

    function renderDashboardRecentMoves(rows, windowDays, totalMoves) {
      const root = $("homeDashRecentMoves");
      const info = $("homeDashMoveWindow");
      const slotInfo = $("homeDashSlotWindow");
      const list = Array.isArray(rows) ? rows : [];
      const safeWindowDays = Math.max(1, Number(windowDays || 1));
      const safeTotalMoves = Math.max(0, Number(totalMoves || 0));
      if (info) info.textContent = t("dashboard.recent.window", { days: formatCount(safeWindowDays), count: countWithUnit(safeTotalMoves) });
      if (slotInfo) slotInfo.textContent = t("dashboard.recent.in_out_window", { days: formatCount(safeWindowDays) });
      if (!root) return;
      if (!list.length) {
        root.innerHTML = `<div class='mini muted'>${escapeHtml(t("dashboard.recent.empty"))}</div>`;
        return;
      }

      root.innerHTML = list.map((row) => {
        const coverUrl = String(row.cover_image_url || "").trim();
        const title = String(row.item_title || "").trim() || t("common.item_name_missing");
        const artist = String(row.artist_or_brand || "").trim();
        const route = t("dashboard.recent.route", {
          from: buildOperatorSlotDisplayLabel(row.from_display_name, row.from_slot_code, "", "", ""),
          to: buildOperatorSlotDisplayLabel(row.to_display_name, row.to_slot_code, "", "", ""),
        });
        const note = String(row.note || "").trim();
        const kindInfo = dashboardMoveDisplayKind(row);
        const coverHtml = coverUrl
          ? `<img src="${escapeHtml(coverUrl)}" alt="">`
          : escapeHtml(mediaDisplayLabel(row.category || ""));
        return `
          <div class="dashboard-move-row" data-move-item-id="${Number(row.owned_item_id || 0)}">
            <div class="dashboard-move-cover">${coverHtml}</div>
            <div class="dashboard-move-main">
              <div class="dashboard-move-title">${escapeHtml(title)}</div>
              <div class="dashboard-move-meta">${escapeHtml([artist, row.label_id].filter(Boolean).join(" | "))}</div>
              <div class="dashboard-move-route">${escapeHtml(route)}${note ? ` / ${escapeHtml(note)}` : ""}</div>
            </div>
            <div class="dashboard-move-side">
              <span class="dashboard-move-kind ${escapeHtml(kindInfo.className)}">${escapeHtml(kindInfo.label)}</span>
              <span class="dashboard-move-time">${escapeHtml(formatDateTimeCompact(row.created_at))}</span>
            </div>
          </div>
        `;
      }).join("");

      root.querySelectorAll("[data-move-item-id]").forEach((node) => {
        node.addEventListener("click", () => {
          if (isShellReadOnly()) return;
          const ownedItemId = Number(node.getAttribute("data-move-item-id") || 0);
          const row = list.find((item) => Number(item?.owned_item_id || 0) === ownedItemId) || null;
          const masterId = Number(row?.linked_album_master_id || row?.album_master_id || 0);
          if (ownedItemId > 0) void openMediaSearchDetailManage(masterId, ownedItemId);
        });
      });
    }

    function renderDashboardSnapshot(d) {
      var b=document.getElementById('homeDashSnapshotBody'); if(!b)return;
      var m=d.music_items||0, g=d.goods_items||0, t=m+g;
      var sl=d.slotted_in_collection_items||0, us=d.unslotted_in_collection_items||0;
      var sp=(sl+us)>0?Math.round(sl/(sl+us)*100):0, kr=null, we=null;
      for(var i=0;i<(d.by_domain||[]).length;i++){if(d.by_domain[i].value==='KOREA')kr=d.by_domain[i];if(d.by_domain[i].value==='WESTERN')we=d.by_domain[i];}
      var fc=formatCount;
      b.innerHTML=
       '<div class="dash-snapshot-row">'+
        '<div class="dash-snapshot-stat"><span class="stat-value">'+fc(t)+'</span><span class="stat-label">전체</span><span class="stat-sub">음반 '+fc(m)+' · 수집품 '+fc(g)+'</span></div>'+
        '<div class="dash-snapshot-stat"><span class="stat-value">'+sp+'%</span><span class="stat-label">배치율</span><span class="stat-sub">'+fc(sl)+' / '+fc(sl+us)+'</span></div>'+
        '<div class="dash-snapshot-stat"><span class="stat-value">'+fc(d.signed_items||0)+'</span><span class="stat-label">싸인본</span><span class="stat-sub">직접 '+fc(d.direct_signed_items||0)+' · 구매 '+fc(d.purchase_signed_items||0)+'</span></div>'+
        '<div class="dash-snapshot-stat"><span class="stat-value">'+fc(d.registered_last_30_days||0)+'</span><span class="stat-label">30일 신규</span><span class="stat-sub">오늘 '+fc(d.registered_today||0)+' · 7일 '+fc(d.registered_last_7_days||0)+'</span></div>'+
        '<div class="dash-snapshot-stat"><span class="stat-value">'+fc(kr?kr.count:0)+'</span><span class="stat-label">KOREA</span><span class="stat-sub">WESTERN '+fc(we?we.count:0)+'</span></div>'+
       '</div>'+
       '<div class="dash-snapshot-chip-row">'+
        '<span class="dash-snapshot-chip" data-dash-drilldown="ownership_in_collection" style="cursor:pointer;">소장 '+fc(d.in_collection_items||0)+'</span>'+
        '<span class="dash-snapshot-chip" data-dash-drilldown="ownership_loaned" style="cursor:pointer;">대출 '+fc(d.loaned_items||0)+'</span>'+
        '<span class="dash-snapshot-chip" data-dash-drilldown="ownership_sold" style="cursor:pointer;">판매 '+fc(d.sold_items||0)+'</span>'+
        '<span class="dash-snapshot-chip" data-dash-drilldown="ownership_lost" style="cursor:pointer;">분실 '+fc(d.lost_items||0)+'</span>'+
        '<span class="dash-snapshot-chip is-new" data-dash-drilldown="new_items" style="cursor:pointer;">새상품 '+fc(d.new_items||0)+'</span>'+
        '<span class="dash-snapshot-chip" data-dash-drilldown="other_items" style="cursor:pointer;">중고 '+fc(d.second_hand_items||0)+'</span>'+
        '<span class="dash-snapshot-chip" data-dash-drilldown="limited_edition" style="cursor:pointer;">한정반 '+fc(d.limited_items||0)+'</span>'+
        '<span class="dash-snapshot-chip" data-dash-drilldown="promo_items" style="cursor:pointer;">홍보반 '+fc(d.promo_items||0)+'</span>'+
       '</div>';
    }

    function renderDashboardHeatmap(d) {
      var b=document.getElementById('homeDashHeatmapBody'); if(!b)return;
      var r=d.by_domain_decade||[], decs=[1960,1970,1980,1990,2000,2010,2020];
      var cd=['KOREA','WESTERN','WORLD','JAPAN','GREATER_CHINA','UNASSIGNED'];
      var lu={}, mv=1;
      for(var i=0;i<r.length;i++){var k=r[i].domain+'|'+r[i].decade;lu[k]=r[i].count||0;if(lu[k]>mv)mv=lu[k];}
      var ad=[];
      for(var d2=0;d2<cd.length;d2++){for(var dc=0;dc<decs.length;dc++){if((lu[cd[d2]+'|'+decs[dc]]||0)>0){ad.push(cd[d2]);break;}}}
      var dc2={KOREA:'#4caf50',WESTERN:'#3a8fd6',WORLD:'#9c6fd6',JAPAN:'#e05a1a',GREATER_CHINA:'#f97316',UNASSIGNED:'#888'};
      var h='<table class="dash-heatmap"><thead><tr><th></th>';
      for(var j=0;j<decs.length;j++)h+='<th>'+decs[j]+'s</th>';
      h+='<th>합계</th></tr></thead><tbody>';
      for(var a=0;a<ad.length;a++){
        var dm=ad[a]; h+='<tr><td>'+_dLabel(dm)+'</td>'; var rt=0;
        for(var k2=0;k2<decs.length;k2++){
          var v=lu[dm+'|'+decs[k2]]||0; rt+=v;
          var inten=v/mv, al=Math.round(15+inten*85);
          var cl=dc2[dm]||'#888';
          h+='<td><span class="dash-heatmap-cell" style="background:rgba('+hexToRgb(cl)+','+(al/100)+');" title="'+dm+' '+decs[k2]+'s: '+v+'">'+(v>0?v:'')+'</span></td>';}
        h+='<td style="font-weight:700;text-align:center;">'+rt+'</td></tr>';}
      h+='<tr style="border-top:2px solid var(--theme-dashboard-border);"><td style="opacity:0.5;">합계</td>';
      for(var m2=0;m2<decs.length;m2++){var ct=0;for(var n=0;n<ad.length;n++)ct+=lu[ad[n]+'|'+decs[m2]]||0;h+='<td style="opacity:0.5;text-align:center;">'+ct+'</td>';}
      h+='<td></td></tr></tbody></table>'; b.innerHTML=h;
    }

    function renderDashboardFinance(d) {
      var b = document.getElementById('homeDashFinanceBody'); if (!b) return;
      var bc = d.by_currency_spend||[], bd = d.by_domain_spend||[];
      var rt = {KRW:1, USD:1, GBP:1, JPY:1}, tKRW = 0, pi = 0;
      for (var i = 0; i < bc.length; i++) {
        tKRW += (bc[i].total_spend||0) * (rt[bc[i].currency_code]||1);
        pi += bc[i].items || 0;
      }
      var ap = pi > 0 ? Math.round(tKRW / pi) : 0;
      var ms = 1;
      for (var j = 0; j < bd.length; j++) { if ((bd[j].total_spend||0) > ms) ms = bd[j].total_spend; }
      var cl = {KOREA:'#4ade80', WESTERN:'#60a5fa', JAPAN:'#fb923c', GREATER_CHINA:'#f97316', WORLD:'#a78bfa', UNASSIGNED:'#6b7280'};
      var fc = formatCount;
      var krwEntry = bc.filter(function(x){return x.currency_code==='KRW';})[0];
      var krwPct = tKRW > 0 && krwEntry ? Math.round((krwEntry.total_spend||0)/tKRW*100) : 0;
      var h = '<div class="dash-fin-hero">' +
        '<div class="dash-fin-hero__num">₩'+fc(tKRW)+'</div>' +
        '<div class="dash-fin-hero__sub">총 구매액 (≈원화) &middot; '+fc(pi)+'/'+fc(d.total_items)+'건 가격 정보</div>' +
        '</div>' +
        '<div class="dash-fin-stats">' +
        '<div class="dash-fin-stat"><div class="dash-fin-stat__lbl">평균 단가</div><div class="dash-fin-stat__val">₩'+fc(ap)+'</div></div>' +
        '<div class="dash-fin-stat"><div class="dash-fin-stat__lbl">주요 통화</div><div class="dash-fin-stat__val" style="font-size:0.82rem;">KRW '+krwPct+'%</div></div>' +
        '</div>' +
        '<hr class="dash-kpi-divider" style="margin:4px 0;">';
      // 가요(KOREA)를 기준 max로 고정
      var koreaEntry = bd.filter(function(x){return x.domain==='KOREA';})[0];
      var baseMax = koreaEntry ? (koreaEntry.total_spend||1) : ms;
      for (var q = 0; q < bd.length; q++) {
        var dd = bd[q];
        var pct = baseMax > 0 ? Math.min(100, Math.round((dd.total_spend||0) / baseMax * 100)) : 0;
        var color = cl[dd.domain]||'#888';
        h += '<div class="dash-fin-bar-row">' +
          '<span class="dash-fin-bar-row__lbl">'+escapeHtml(_dLabel(dd.domain))+'</span>' +
          '<div class="dash-fin-bar-row__track"><div class="dash-fin-bar-row__fill" style="width:'+pct+'%;background:'+color+'"></div></div>' +
          '<span class="dash-fin-bar-row__val" style="text-align:right;line-height:1.3;">' +
            '<span style="display:block;font-size:0.66rem;opacity:0.9;">₩'+fc(dd.total_spend)+'</span>' +
            '<span style="display:block;font-size:0.58rem;opacity:0.55;">avg ₩'+fc(dd.avg_price)+'</span>' +
          '</span>' +
          '</div>';
      }
      b.innerHTML = h;
    }

    function renderDashboardGenreDomain(d) {
      var b = document.getElementById('homeDashGenreDomainBody'); if (!b) return;
      var r = d.by_genre_domain || [], kg = [], wg = [];
      for (var i = 0; i < r.length; i++) {
        if (r[i].domain === 'KOREA'   && kg.length < 6) kg.push(r[i]);
        if (r[i].domain === 'WESTERN' && wg.length < 6) wg.push(r[i]);
      }
      var mk = Math.max(1, kg.reduce(function(m,x){return Math.max(m,x.count||0);}, 0));
      var mw = Math.max(1, wg.reduce(function(m,x){return Math.max(m,x.count||0);}, 0));
      var fc = formatCount;
      function col(items, max, color, domain) {
        return '<div>' +
          '<div style="font-size:0.72rem;font-weight:800;letter-spacing:0.03em;text-transform:uppercase;'+
               'color:'+color+';margin-bottom:8px;padding-bottom:5px;border-bottom:2px solid '+color+';">'+domain+'</div>' +
          items.map(function(it) {
            var pct = Math.round((it.count||0) / max * 100);
            return '<div class="dash-compare-row">' +
              '<span class="name" title="'+escapeHtml(it.genre||'')+'">'+escapeHtml(it.genre||'')+'</span>' +
              '<div class="dash-compare-bar"><div class="dash-compare-bar-fill" style="width:'+pct+'%;background:'+color+';"></div></div>' +
              '<span class="count" style="color:'+color+';">'+fc(it.count)+'</span>' +
              '</div>';
          }).join('') +
          '</div>';
      }
      b.innerHTML = '<div class="dash-compare-grid">' +
        col(kg, mk, '#4ade80', 'KOREA') +
        col(wg, mw, '#60a5fa', 'WESTERN') +
        '</div>';
    }

    function renderDashboardFormatPressing(d) {
      var b = document.getElementById('homeDashFormatPressingBody'); if (!b) return;
      var pr = d.by_pressing_domain||[];
      if (!pr.length) { b.innerHTML = '<div class="mini muted">데이터 없음</div>'; return; }
      var fc = formatCount;
      var dc = {KOREA:'#4ade80', WESTERN:'#60a5fa', WORLD:'#a78bfa', JAPAN:'#fb923c', GREATER_CHINA:'#f97316', UNASSIGNED:'#6b7280'};

      // 국가별로 도메인 묶기
      var groups = {}, order = [];
      for (var i = 0; i < pr.length; i++) {
        var r = pr[i], ctry = r.pressing_country || '(미상)';
        if (!groups[ctry]) { groups[ctry] = { total: 0, domains: {} }; order.push(ctry); }
        groups[ctry].domains[r.domain] = (groups[ctry].domains[r.domain]||0) + (r.count||0);
        groups[ctry].total += (r.count||0);
      }
      // total 내림차순 상위 10
      order.sort(function(a,b){ return groups[b].total - groups[a].total; });
      order = order.slice(0, 10);
      var maxTotal = Math.max(1, groups[order[0]] ? groups[order[0]].total : 1);

      var h = '';
      for (var j = 0; j < order.length; j++) {
        var ctry = order[j], g = groups[ctry];
        var short = ctry.length > 16 ? ctry.substring(0,15)+'…' : ctry;
        var barPct = Math.round(g.total / maxTotal * 100);
        // 스택 세그먼트
        var segs = '', dks = Object.keys(g.domains).sort(function(a,b){return g.domains[b]-g.domains[a];});
        for (var k = 0; k < dks.length; k++) {
          var dm = dks[k], cnt = g.domains[dm];
          var segPct = Math.round(cnt / g.total * 100);
          segs += '<div title="'+escapeHtml(_dLabel(dm))+': '+fc(cnt)+'" style="height:100%;width:'+segPct+'%;background:'+(dc[dm]||'#6b7280')+';flex-shrink:0;transition:width 0.4s;"></div>';
        }
        h += '<div class="dash-fin-bar-row" style="margin-bottom:3px;">' +
          '<span class="dash-fin-bar-row__lbl" style="width:88px;font-size:0.67rem;" title="'+escapeHtml(ctry)+'">'+escapeHtml(short)+'</span>' +
          '<div class="dash-fin-bar-row__track" style="overflow:hidden;">' +
            '<div style="height:100%;width:'+barPct+'%;display:flex;border-radius:3px;overflow:hidden;">'+segs+'</div>' +
          '</div>' +
          '<span class="dash-fin-bar-row__val" style="width:36px;">'+fc(g.total)+'</span>' +
          '</div>';
      }
      // 범례
      var usedDomains = [];
      for (var j2 = 0; j2 < order.length; j2++) {
        var dks2 = Object.keys(groups[order[j2]].domains);
        for (var k2 = 0; k2 < dks2.length; k2++) {
          if (usedDomains.indexOf(dks2[k2]) < 0) usedDomains.push(dks2[k2]);
        }
      }
      usedDomains.sort();
      h += '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;">';
      for (var m = 0; m < usedDomains.length; m++) {
        var dm2 = usedDomains[m];
        h += '<span style="display:flex;align-items:center;gap:3px;font-size:0.6rem;opacity:0.7;">' +
          '<span style="width:8px;height:8px;border-radius:2px;background:'+(dc[dm2]||'#6b7280')+';flex-shrink:0;"></span>' +
          escapeHtml(_dLabel(dm2))+'</span>';
      }
      h += '</div>';
      b.innerHTML = h;
    }

    function renderDashboardArtistTimeline(d) {
      var b=document.getElementById('homeDashArtistTimelineBody'); if(!b)return;
      var artists=(d.by_artist_decade||[]).slice(0,10);
      if(!artists.length){b.innerHTML='<div class="mini muted">데이터 없음</div>';return;}
      var minD=3000,maxD=0;
      for(var i=0;i<artists.length;i++){if(artists[i].min_decade<minD)minD=artists[i].min_decade;if(artists[i].max_decade>maxD)maxD=artists[i].max_decade;}
      if(minD>=maxD)maxD=minD+20;
      var range=maxD-minD, fc=formatCount, h='';
      for(var j=0;j<artists.length;j++){
        var a=artists[j];
        var left=range>0?((a.min_decade-minD)/range*100):0;
        var w=range>0?((a.max_decade-a.min_decade)/range*100):5;
        w=Math.max(5,w);
        var colors=['#3a8fd6','#4caf50','#e05a1a','#9c6fd6','#b45309','#0f766e','#f97316','#8b5cf6','#ec4899','#c47b30','#5d89b4','#7a7aa8'];
        h+='<div class="dash-artist-row"><span class="dash-artist-name" title="'+escapeHtml(a.artist||'')+'">'+escapeHtml(a.artist||'')+'</span><div class="dash-artist-timeline"><div class="dash-artist-span" style="left:'+left+'%;width:'+w+'%;background:'+colors[j%12]+';"></div></div><span class="dash-artist-decades">'+a.min_decade+'s~'+a.max_decade+'s</span><span class="dash-artist-count">'+fc(a.total)+'</span></div>';
      }
      h+='<div style="font-size:0.58rem;opacity:0.35;margin-top:4px;display:flex;justify-content:space-between;"><span>'+minD+'s</span><span>'+maxD+'s</span></div>';
      b.innerHTML=h;
    }

    function renderDashboardMetaSource(d) {
      var b = document.getElementById('homeDashMetaSourceBody'); if (!b) return;
      var rows = d.by_source_completeness || [];
      if (!rows.length) { b.innerHTML = '<div class="mini muted">데이터 없음</div>'; return; }
      function pctClass(p) { return p >= 95 ? 'high' : p >= 70 ? 'mid' : 'low'; }
      function barLine(tag, pct) {
        return '<div class="dash-meta-bar-line">' +
          '<span class="dash-meta-bar-tag">'+tag+'</span>' +
          '<div class="dash-meta-bar-track"><div class="dash-meta-bar-fill '+pctClass(pct)+'" style="width:'+pct+'%"></div></div>' +
          '<span class="dash-meta-bar-pct">'+pct+'%</span>' +
          '</div>';
      }
      var h = '<div class="dash-meta-src-group">';
      for (var i = 0; i < rows.length; i++) {
        var r = rows[i];
        var mp  = r.total > 0 ? Math.round(r.master_linked  / r.total * 100) : 0;
        var cp  = r.total > 0 ? Math.round(r.cover_present  / r.total * 100) : 0;
        var gp  = r.total > 0 ? Math.round(r.genre_present  / r.total * 100) : 0;
        // 구분선은 CSS border-top으로 처리
        h += '<div class="dash-meta-src-row">' +
          '<span class="dash-meta-src-name">'+escapeHtml(r.source||'')+'</span>' +
          '<div class="dash-meta-bars">' +
            barLine('마스터', mp) + barLine('커버', cp) + barLine('장르', gp) +
          '</div>' +
          '</div>';
      }
      h += '</div>';
      b.innerHTML = h;
    }

    function renderDashboardCollector(d) {
      var b = document.getElementById('homeDashCollectorBody'); if (!b) return;
      var fc = formatCount;
      var items = [
        { num: d.signed_items||0,     lbl:'싸인본',    color:'#fbbf24', drill:'sig_direct'      },
        { num: d.limited_items||0,    lbl:'한정반',    color:'#a78bfa', drill:'limited_edition'  },
        { num: d.multi_disc_items||0, lbl:'멀티디스크', color:'#22d3ee', drill:null              },
        { num: d.obi_items||0,        lbl:'OBI',       color:'#f9a8d4', drill:null              },
        { num: d.promo_items||0,      lbl:'홍보반',    color:'#fb923c', drill:'promo_items'      },
        { num: d.box_set_items||0,    lbl:'박스세트',   color:'#6b7280', drill:'box_set'         },
      ];
      b.innerHTML = '<div class="dash-tile-grid">' +
        items.map(function(it) {
          var drill = it.drill ? ' data-dash-drilldown="'+it.drill+'"' : '';
          return '<div class="dash-tile"'+drill+'>' +
            '<div class="dash-tile__num" style="color:'+it.color+';">'+fc(it.num)+'</div>' +
            '<div class="dash-tile__lbl">'+it.lbl+'</div>' +
            '</div>';
        }).join('') +
        '</div>';
    }

    function renderDashboardAlerts(d) {
      var b = document.getElementById('homeDashAlertsBody'); if (!b) return;
      var fc = formatCount;
      var unassigned = 0;
      for (var i = 0; i < (d.by_domain||[]).length; i++) {
        if (d.by_domain[i].value === 'UNASSIGNED') unassigned = d.by_domain[i].count;
      }
      function alertColor(count, severity) {
        if (count === 0) return '#4ade80';
        if (severity === 'critical') return '#f87171';
        if (severity === 'warning')  return '#fb923c';
        return '#60a5fa';
      }
      var items = [
        { lbl:'소스 미연결',   c: d.source_unlinked_items||0,         sev:'critical', drill:'source_unlinked' },
        { lbl:'커버 없음',     c: d.cover_missing_items||0,           sev:'warning',  drill:'cover_missing'   },
        { lbl:'장르 없음',     c: d.genre_missing_items||0,           sev:'warning',  drill:'genre_missing'   },
        { lbl:'규격 불일치',   c: d.category_size_mismatch_items||0,  sev:'warning',  drill:'size_mismatch'   },
        { lbl:'미배치',        c: d.unslotted_in_collection_items||0, sev:'warning',  drill:'unslotted'       },
        { lbl:'도메인 미지정', c: unassigned,                          sev:'info',     drill:'genre_missing'   },
      ];
      b.innerHTML = '<div class="dash-tile-grid">' +
        items.map(function(it) {
          return '<div class="dash-tile" data-dash-drilldown="'+it.drill+'">' +
            '<div class="dash-tile__num" style="color:'+alertColor(it.c, it.sev)+';">'+fc(it.c)+'</div>' +
            '<div class="dash-tile__lbl">'+it.lbl+'</div>' +
            '</div>';
        }).join('') +
        '</div>';
    }

    function renderDashboardRegImport(d) {
      var b = document.getElementById('homeDashRegImportBody'); if (!b) return;
      var months = (d.by_registration_month || []).slice(-10);
      var maxReg = Math.max(1, months.reduce(function(m,x){return Math.max(m,x.count||0);}, 0));
      var fc = formatCount;
      var h = '<div class="dash-reg-pace">';
      for (var j = 0; j < months.length; j++) {
        var m = months[j], pct = Math.round((m.count||0) / maxReg * 100);
        h += '<div class="dash-reg-month">' +
          '<span class="dash-reg-month-label">'+m.month+'</span>' +
          '<div class="dash-reg-month-bar"><div class="dash-reg-month-fill" style="width:'+pct+'%"></div></div>' +
          '<span class="dash-reg-month-count" style="font-weight:700;opacity:'+(pct===100?'1':'0.6')+';">'+fc(m.count)+'</span>' +
          '</div>';
      }
      h += '</div>';
      var qSize = d.import_queue_size || 0;
      h += '<div class="dash-import-panel">' +
        '<div class="dash-import-panel__num">'+fc(qSize)+'</div>' +
        '<div><div class="dash-import-panel__lbl">구매 수입 대기</div>' +
        '<span class="dash-import-panel__badge">'+(qSize > 0 ? '처리 필요' : '완료')+'</span>' +
        '</div></div>';
      b.innerHTML = h;
    }

    function renderDashboardMoveHeatmap(d) {
      var b=document.getElementById('homeDashMoveHeatmapBody'); if(!b)return;
      var rows=d.by_slot_moves||[];
      if(!rows.length){b.innerHTML='<div class="mini muted">30일 내 이동 없음</div>';return;}
      // Group by slot, sum all movement kinds
      var slotMap={}, maxCnt=1;
      for(var i=0;i<rows.length;i++){var s=rows[i].slot_code||'UNASSIGNED';slotMap[s]=(slotMap[s]||0)+rows[i].count;if(slotMap[s]>maxCnt)maxCnt=slotMap[s];}
      var slots=Object.keys(slotMap).sort(function(a,b){return slotMap[b]-slotMap[a];}).slice(0,12);
      var h='<div style="display:flex;flex-direction:column;gap:4px;">';
      for(var j=0;j<slots.length;j++){
        var s=slots[j], cnt=slotMap[s], pct=Math.round(cnt/maxCnt*100);
        var intensity=pct>70?'#e05a1a':pct>30?'#f97316':'#3a8fd6';
        h+='<div style="display:flex;align-items:center;gap:6px;font-size:0.7rem;"><span style="width:110px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;opacity:0.7;" title="'+escapeHtml(s)+'">'+escapeHtml(s)+'</span><div class="dash-compare-bar" style="flex:1;"><div class="dash-compare-bar-fill" style="width:'+pct+'%;background:'+intensity+'"></div></div><span style="font-family:var(--font-mono);font-size:0.68rem;">'+formatCount(cnt)+'</span></div>';
      }
      h+='</div>';
      b.innerHTML=h;
    }

    function renderDashboardRecentReg(d) {
      var b = document.getElementById('homeDashRecentRegBody'); if (!b) return;
      var regTotal = d.registered_last_30_days||0;
      var byDomain = d.by_recent_reg_domain||[];
      var byDD = d.by_recent_reg_domain_decade||[];
      var fc = formatCount;
      var dc = {KOREA:'#4ade80', WESTERN:'#60a5fa', WORLD:'#a78bfa', JAPAN:'#fb923c', GREATER_CHINA:'#f97316', UNASSIGNED:'#6b7280'};
      // Hero 수치
      var h = '<div style="margin-bottom:8px;">' +
        '<span style="font-family:var(--font-mono);font-size:1.8rem;font-weight:800;letter-spacing:-0.05em;line-height:1;">'+fc(regTotal)+'</span>' +
        '<span style="font-size:0.68rem;opacity:0.5;margin-left:4px;">건 (30일)</span>' +
        '</div>';
      // 도메인 칩
      if (byDomain.length) {
        h += '<div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:8px;">';
        for (var i = 0; i < byDomain.length; i++) {
          var dm = byDomain[i];
          h += '<span style="font-size:0.65rem;padding:2px 8px;border-radius:20px;' +
               'background:rgba(128,128,128,0.1);border:1px solid rgba(128,128,128,0.15);' +
               'color:'+(dc[dm.value]||'#888')+';">' +
               _dLabel(dm.value)+' <strong style="font-family:var(--font-mono);">'+fc(dm.count)+'</strong></span>';
        }
        h += '</div>';
      }
      // 연대 분포: 히트맵 대신 bar 행
      if (byDD.length) {
        h += '<div class="dash-kpi-sub-label" style="margin-bottom:5px;">연대 분포</div>';
        var decs = [1960,1970,1980,1990,2000,2010,2020];
        var lu = {}, mv2 = 1;
        for (var j = 0; j < byDD.length; j++) {
          var k = byDD[j].domain+'|'+byDD[j].decade; lu[k]=byDD[j].count||0; if(lu[k]>mv2)mv2=lu[k];
        }
        var ad = ['KOREA','WESTERN'].filter(function(domain){
          return decs.some(function(dec){return(lu[domain+'|'+dec]||0)>0;});
        });
        for (var a = 0; a < ad.length; a++) {
          var color = dc[ad[a]]||'#888';
          h += '<div style="margin-bottom:4px;">' +
            '<div style="font-size:0.62rem;font-weight:700;color:'+color+';margin-bottom:3px;">'+_dLabel(ad[a])+'</div>' +
            '<div style="display:flex;gap:2px;align-items:flex-end;height:20px;">';
          for (var d2 = 0; d2 < decs.length; d2++) {
            var v = lu[ad[a]+'|'+decs[d2]]||0;
            var hPct = v > 0 ? Math.round(v/mv2*100) : 0;
            h += '<div title="'+decs[d2]+'s: '+v+'" style="flex:1;background:'+(hPct?color:'rgba(128,128,128,0.1)')+';' +
                 'height:'+hPct+'%;min-height:'+(hPct?'3px':'3px')+';border-radius:2px 2px 0 0;opacity:'+(hPct?0.85:0.3)+';transition:height 0.4s;"></div>';
          }
          h += '</div>' +
            '<div style="display:flex;gap:2px;margin-top:1px;">';
          for (var d3 = 0; d3 < decs.length; d3++) {
            h += '<div style="flex:1;font-size:0.5rem;text-align:center;opacity:0.3;letter-spacing:-0.02em;">'+String(decs[d3]).slice(2)+'s</div>';
          }
          h += '</div></div>';
        }
      }
      b.innerHTML = h;
    }

    function renderDashboardPurchaseFlow(d) {
      var b = document.getElementById('homeDashPurchaseFlowBody'); if (!b) return;
      var rows = (d.by_purchase_flow||[]);
      if (!rows.length) { b.innerHTML = '<div class="mini muted">구매 데이터 없음</div>'; return; }
      var fc = formatCount;
      var dc = {KOREA:'#4ade80', WESTERN:'#60a5fa', WORLD:'#a78bfa', JAPAN:'#fb923c', GREATER_CHINA:'#f97316', UNASSIGNED:'#6b7280'};

      // source별로 domain 묶기 (Ebay (XXX) → Ebay 통합)
      var groups = {}, order = [];
      for (var i = 0; i < rows.length; i++) {
        var r = rows[i], src = r.source || '(알 수 없음)';
        if (/^Ebay\s*\(/.test(src)) src = 'Ebay';
        if (!groups[src]) { groups[src] = { total: 0, domains: {} }; order.push(src); }
        groups[src].domains[r.domain] = (groups[src].domains[r.domain] || 0) + (r.items || 0);
        groups[src].total += (r.items || 0);
      }
      // total 내림차순, 상위 10개
      order.sort(function(a,b){ return groups[b].total - groups[a].total; });
      order = order.slice(0, 10);
      var maxTotal = Math.max(1, groups[order[0]] ? groups[order[0]].total : 1);

      var h = '';
      for (var j = 0; j < order.length; j++) {
        var src = order[j], g = groups[src];
        var short = src.length > 32 ? src.substring(0, 30) + '…' : src;
        // 스택 바 세그먼트
        var segs = '', domKeys = Object.keys(g.domains).sort(function(a,b){return g.domains[b]-g.domains[a];});
        var barTotal = g.total;
        for (var k = 0; k < domKeys.length; k++) {
          var dm = domKeys[k], cnt = g.domains[dm];
          var segPct = Math.round(cnt / barTotal * 100);
          var color = dc[dm] || '#6b7280';
          segs += '<div title="'+escapeHtml(_dLabel(dm))+': '+fc(cnt)+'" style="height:100%;width:'+segPct+'%;background:'+color+';flex-shrink:0;transition:width 0.4s;"></div>';
        }
        var barPct = Math.round(g.total / maxTotal * 100);
        h += '<div style="padding:4px 0;border-bottom:1px solid rgba(128,128,128,0.07);">' +
          '<div style="display:flex;align-items:center;gap:6px;margin-bottom:3px;">' +
          '<span style="flex:1;font-size:0.68rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="'+escapeHtml(src)+'">'+escapeHtml(short)+'</span>' +
          '<span style="font-family:var(--font-mono);font-size:0.7rem;font-weight:700;opacity:0.8;flex-shrink:0;min-width:28px;text-align:right;">'+fc(g.total)+'</span>' +
          '</div>' +
          '<div style="height:6px;background:rgba(128,128,128,0.1);border-radius:3px;overflow:hidden;">' +
          '<div style="height:100%;width:'+barPct+'%;display:flex;border-radius:3px;overflow:hidden;">' + segs + '</div>' +
          '</div>' +
          '</div>';
      }
      // 범례
      var legend = '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;">';
      var usedDomains = [];
      for (var j2 = 0; j2 < order.length; j2++) {
        var dks = Object.keys(groups[order[j2]].domains);
        for (var k2 = 0; k2 < dks.length; k2++) {
          if (usedDomains.indexOf(dks[k2]) < 0) usedDomains.push(dks[k2]);
        }
      }
      usedDomains.sort();
      for (var m = 0; m < usedDomains.length; m++) {
        var dm2 = usedDomains[m];
        legend += '<span style="display:flex;align-items:center;gap:3px;font-size:0.6rem;opacity:0.7;">' +
          '<span style="width:8px;height:8px;border-radius:2px;background:'+(dc[dm2]||'#6b7280')+';flex-shrink:0;"></span>' +
          escapeHtml(_dLabel(dm2)) + '</span>';
      }
      legend += '</div>';
      b.innerHTML = h + legend;
    }
    function renderDashboardSourceRows(rows, totalItems) {
      const root = $("homeDashBySource");
      const summaryRoot = $("homeDashSourceSummary");
      const list = Array.isArray(rows) ? rows : [];
      const externalRows = list.filter((row) => {
        const sourceValue = String(row?.value || "").trim().toUpperCase();
        if (!sourceValue || sourceValue === "MANUAL") return false;
        return SOURCE_MANAGED_CODES.has(sourceValue);
      });
      setTextIfPresent("homeDashSourceCount", formatCount(externalRows.length));
      const externalLinkedEl = $("homeDashExternalSourceItems");
      if (externalLinkedEl) {
        const externalLinkedCount = externalRows.reduce((sum, row) => {
          const sourceValue = String(row?.value || "").trim().toUpperCase();
          if (!sourceValue) return sum;
          return sum + Math.max(0, Number(row?.count || 0));
        }, 0);
        externalLinkedEl.textContent = formatCount(externalLinkedCount);
      }
      if (summaryRoot) {
        const topRows = externalRows.slice(0, 3);
        summaryRoot.innerHTML = topRows.length
          ? topRows.map((row) => `
              <span class="dashboard-source-row"><span class="dashboard-source-name">${escapeHtml(dashboardSourceLabel(row.value))}</span> <em class="dashboard-source-count">${formatCount(Number(row.count || 0))}</em></span>
            `).join("")
          : `<div class='mini muted'>${escapeHtml(t("common.data_empty"))}</div>`;
      }
      if (!root) return;
      if (!list.length) {
        root.innerHTML = `<div class='mini muted'>${escapeHtml(t("common.data_empty"))}</div>`;
        return;
      }
      const total = Math.max(1, Number(totalItems || 0));
      root.innerHTML = list.map((row) => {
        const count = Number(row.count || 0);
        const width = Math.max(4, Math.round((count / total) * 100));
        return `
          <div class="dashboard-source-row">
            <strong>${escapeHtml(dashboardSourceLabel(row.value))}</strong>
            <div class="dashboard-source-bar"><span data-fill-width="${width}"></span></div>
            <span>${formatCount(count)}</span>
          </div>
        `;
      }).join("");
      root.querySelectorAll(".dashboard-source-bar > span[data-fill-width]").forEach((bar) => {
        const width = Number(bar.getAttribute("data-fill-width") || 0);
        bar.style.width = `${Math.max(0, Math.min(100, width))}%`;
      });
    }

    function dashboardContainsAnyToken(value, tokens) {
      const text = String(value || "").trim().toLowerCase();
      if (!text) return false;
      return (Array.isArray(tokens) ? tokens : []).some((token) => text.includes(String(token || "").trim().toLowerCase()));
    }

    function dashboardResolveOwnedItemThicknessMm(row, slotRow) {
      const sizeGroup = String(row?.size_group || "").trim().toUpperCase();
      const slotSizeGroup = String(slotRow?.allowed_size_group || "").trim().toUpperCase();
      const formatName = String(row?.format_name || "").trim();
      const formatNameUpper = formatName.toUpperCase();
      const hintValues = [row?.format_name, row?.package_hint, row?.notes, row?.item_name_override];
      const hintIsSlim = hintValues.some((value) => dashboardContainsAnyToken(value, ["slim", "슬림"]));
      const hintIsGatefold = hintValues.some((value) => dashboardContainsAnyToken(value, ["gatefold", "게이트폴드"]));
      const hintIsBox = hintValues.some((value) => dashboardContainsAnyToken(value, ["box", "박스", "확장", "digipak"]));
      const hintIs10inch = hintValues.some((value) => dashboardContainsAnyToken(value, ['10"', "10inch", "10-inch", "10인치"]));
      const hintIs7inch = hintValues.some((value) => dashboardContainsAnyToken(value, ['7"', "7inch", "7-inch", "7인치"]));
      const slotIsBoxSet = slotSizeGroup === "OVERSIZE";
      const rawFormatItems = Array.isArray(row?.format_items)
        ? row.format_items
        : (() => {
            if (!row?.format_items_json) return [];
            try {
              const parsed = JSON.parse(String(row.format_items_json || "[]"));
              return Array.isArray(parsed) ? parsed : [];
            } catch (_) {
              return [];
            }
          })();
      let lpCount = 0;
      let lp10Count = 0;
      let lp7Count = 0;
      let cdCount = 0;
      for (const item of rawFormatItems) {
        if (!item || typeof item !== "object") continue;
        const qtyRaw = Number.parseInt(String(item.qty || "").trim(), 10);
        const qty = Number.isFinite(qtyRaw) && qtyRaw > 0 ? qtyRaw : 1;
        const values = [item.name, item.text, item.display, ...(Array.isArray(item.descriptions) ? item.descriptions : [])];
        if (values.some((value) => dashboardContainsAnyToken(value, ["cd", "compact disc", "compactdisc"]))) {
          cdCount += qty;
          continue;
        }
        if (values.some((value) => dashboardContainsAnyToken(value, ['7"', "7inch", "7-inch", "7인치"]))) {
          lp7Count += qty;
          continue;
        }
        if (values.some((value) => dashboardContainsAnyToken(value, ['10"', "10inch", "10-inch", "10인치"]))) {
          lp10Count += qty;
          continue;
        }
        if (values.some((value) => dashboardContainsAnyToken(value, ["lp", "vinyl", "엘피"]))) {
          lpCount += qty;
        }
      }
      const discCount = Number(row?.disc_count || 0);
      const normalizedDiscCount = Number.isFinite(discCount) && discCount > 0 ? Math.floor(discCount) : 0;
      const parsedTotalCount = lpCount + lp10Count + lp7Count + cdCount;
      const missingCount = Math.max(0, normalizedDiscCount - parsedTotalCount);
      if (missingCount > 0) {
        if (sizeGroup === "LP7" || hintIs7inch) lp7Count += missingCount;
        else if (sizeGroup === "LP10" || hintIs10inch) lp10Count += missingCount;
        else if (["STD", "BOOK"].includes(sizeGroup) || formatNameUpper === "CD") cdCount += missingCount;
        else lpCount += missingCount;
      }
      const boxSetSlotItem = slotIsBoxSet && (
        ["LP", "LP10", "LP7", "OVERSIZE"].includes(sizeGroup)
        || ["STD", "BOOK"].includes(sizeGroup)
        || formatNameUpper === "LP"
        || formatNameUpper === "CD"
        || hintIs10inch
        || hintIs7inch
        || rawFormatItems.length > 0
      );
      const explicitThickness = Number(row?.thickness_mm || 0);
      if (Number.isFinite(explicitThickness) && explicitThickness > 0 && !boxSetSlotItem) {
        return explicitThickness;
      }
      const vinylBoxThickness = (baseThickness) => (
        normalizedDiscCount > 0 ? Math.max(1, Math.ceil(baseThickness * normalizedDiscCount * 1.2)) : 12
      );
      if (slotIsBoxSet) {
        let baseThickness = (lpCount * 4) + (lp10Count * 4) + (lp7Count * 3) + (Math.ceil(cdCount / 4) * 10);
        if (baseThickness <= 0 && normalizedDiscCount > 0) {
          if (sizeGroup === "LP7" || hintIs7inch) baseThickness = 3 * normalizedDiscCount;
          else if (sizeGroup === "LP10" || hintIs10inch) baseThickness = 4 * normalizedDiscCount;
          else if (["STD", "BOOK"].includes(sizeGroup) || formatNameUpper === "CD") baseThickness = Math.ceil(normalizedDiscCount / 4) * 10;
          else baseThickness = 4 * normalizedDiscCount;
        }
        if (baseThickness > 0) return Math.max(1, Math.ceil(baseThickness * 1.2));
      }
      if (sizeGroup === "BOOK") return 12;
      if (sizeGroup === "GOODS") return 12;
      if (sizeGroup === "CASSETTE" || dashboardContainsAnyToken(formatName, ["cassette", "카세트", "tape", "mc"])) return 11;
      if (sizeGroup === "8TRACK" || dashboardContainsAnyToken(formatName, ["8-track", "8 track", "8track"])) return 22;
      if (sizeGroup === "REEL_TO_REEL" || dashboardContainsAnyToken(formatName, ["reel-to-reel", "reel to reel", "open reel"])) return 25;
      if (sizeGroup === "LP7" || hintIs7inch) {
        if (hintIsBox || slotIsBoxSet) return vinylBoxThickness(3);
        return 3;
      }
      if (sizeGroup === "LP10" || hintIs10inch) {
        if (hintIsBox || slotIsBoxSet) return vinylBoxThickness(4);
        if (hintIsGatefold) return 7;
        return 4;
      }
      if (formatNameUpper === "LP" || ["LP", "OVERSIZE"].includes(sizeGroup)) {
        if (hintIsBox || sizeGroup === "OVERSIZE" || slotIsBoxSet) return vinylBoxThickness(4);
        if (hintIsGatefold) return 7;
        return 4;
      }
      if (hintIsSlim) return 5;
      if (hintIsBox || sizeGroup === "OVERSIZE") return 18;
      return 10;
    }

    function dashboardApplySlotOccupancyDelta(slotRow, deltaMm) {
      if (!slotRow) return;
      const capacity = Number(slotRow?.capacity_mm || 0);
      const currentUsed = Number(slotRow?.used_thickness_mm || 0);
      const nextUsed = Math.max(0, currentUsed + Number(deltaMm || 0));
      const nextFree = capacity > 0 ? Math.max(capacity - nextUsed, 0) : 0;
      const nextRatio = capacity > 0 ? nextUsed / capacity : 0;
      slotRow.used_thickness_mm = nextUsed;
      slotRow.free_thickness_mm = nextFree;
      slotRow.occupancy_ratio = nextRatio;
      slotRow.occupancy_percent = Math.round(nextRatio * 100);
    }

    function updateDashboardSlotCountsAfterMove(items, targetRow) {
      const targetSlotCode = String(targetRow?.slot_code || "").trim();
      if (!targetSlotCode) return;
      let movedIntoTarget = 0;
      for (const row of Array.isArray(items) ? items : []) {
        const sourceSlotCode = String(row?.slot_code || "").trim();
        if (sourceSlotCode && sourceSlotCode !== targetSlotCode) {
          const sourceRow = getDashboardSlotRow(sourceSlotCode);
          if (sourceRow) {
            sourceRow.count = Math.max(0, Number(sourceRow.count || 0) - 1);
            sourceRow.recent_out_count = Math.max(0, Number(sourceRow.recent_out_count || 0) + 1);
            dashboardApplySlotOccupancyDelta(sourceRow, -dashboardResolveOwnedItemThicknessMm(row, sourceRow));
          }
        }
        if (sourceSlotCode !== targetSlotCode) {
          movedIntoTarget += 1;
          dashboardApplySlotOccupancyDelta(targetRow, dashboardResolveOwnedItemThicknessMm(row, targetRow));
        }
      }
      if (movedIntoTarget > 0) {
        targetRow.count = Math.max(0, Number(targetRow.count || 0) + movedIntoTarget);
        targetRow.recent_in_count = Math.max(0, Number(targetRow.recent_in_count || 0) + movedIntoTarget);
      }
    }

    function updateDashboardOwnedItemLocation(ownedItemId, targetRow) {
      const id = Number(ownedItemId || 0);
      if (id <= 0) return;
      const targetSlotId = Number(resolveDashboardStorageSlotId(targetRow) || 0);
      const targetSlotCode = String(targetRow?.slot_code || "").trim() || null;
      const pools = [
        homeDashboardSlotItems,
        homeDashboardSlotSelectionSnapshot,
        homeDashboardUnassignedItems,
        homeDashboardSearchItems,
      ];
      for (const pool of pools) {
        if (!Array.isArray(pool)) continue;
        for (const row of pool) {
          if (Number(row?.id || 0) !== id) continue;
          row.storage_slot_id = targetSlotId || null;
          row.slot_code = targetSlotCode;
        }
      }
    }

    function renderDashboardSurfaceDock() {
      const bulkBtn = $("homeDashSlotBulkBtn");
      const bulkPanel = $("homeDashBulkEditPanel");
      const readOnlyShell = isShellReadOnly();
      if (readOnlyShell && homeDashSurfacePanel === "BULK") homeDashSurfacePanel = "";
      if (bulkBtn) {
        setHiddenState(bulkBtn, readOnlyShell);
        bulkBtn.classList.toggle("active", !readOnlyShell && homeDashSurfacePanel === "BULK");
      }
      if (bulkPanel) {
        setDisplayMode(bulkPanel, !readOnlyShell && homeDashSurfacePanel === "BULK" ? "grid" : "none");
        bulkPanel.classList.toggle("active", !readOnlyShell && homeDashSurfacePanel === "BULK");
      }
    }

    function toggleDashboardSurfacePanel(panelName) {
      const next = String(panelName || "").trim().toUpperCase();
      if (!next) return;
      homeDashSurfacePanel = homeDashSurfacePanel === next ? "" : next;
      renderDashboardSurfaceDock();
    }


    function storageSlotDisplayLabel(slot) {
      if (!slot) return "-";
      const localizedTriplet = buildOperatorCabinetTripletLabel(slot.cabinet_name, slot.column_code, slot.cell_code);
      if (localizedTriplet) return localizedTriplet;
      const displayName = localizeOperatorSlotDisplayName(slot.display_name);
      if (displayName) return displayName;
      const slotCode = String(slot.slot_code || "").trim();
      if (!slotCode) return "-";
      if (slotCode === "UNASSIGNED") return t("common.unslotted");
      return slotCode;
    }

    function cabinetSortPolicyLabel(value) {
      const code = String(value || "").trim().toUpperCase();
      if (code === "LABEL_ID") return t("common.sort_policy.label_id");
      if (code === "TITLE_RELEASE") return t("common.sort_policy.title_release");
      return t("common.sort_policy.artist_release_title");
    }

    function compareCodeValue(a, b) {
      return String(a || "").localeCompare(String(b || ""), "ko", {
        numeric: true,
        sensitivity: "base",
      });
    }

    function buildDashboardCabinetGroups(rows) {
      const grouped = [];
      const byKey = new Map();
      for (const row of Array.isArray(rows) ? rows : []) {
        const key = dashboardCabinetKey(row);
        if (!byKey.has(key)) {
          const slotCode = String(row?.slot_code || "").trim();
          const cabinetGroupName = String(row?.cabinet_group_name || "").trim();
          byKey.set(key, {
            key,
            title: slotCode === "UNASSIGNED"
              ? dashboardUnassignedAssetsLabel()
              : (row?.is_overflow_zone ? "Overflow" : (cabinetGroupName || String(row?.cabinet_name || "").trim() || dashboardUnnamedCabinetLabel())),
            groupName: cabinetGroupName,
            groupOrder: Number(row?.cabinet_group_order || 0) || 0,
            isOverflow: Boolean(row?.is_overflow_zone),
            isUnassigned: slotCode === "UNASSIGNED",
            rows: [],
            total: 0,
            slotCount: 0,
            filledSlotCount: 0,
            recentInTotal: 0,
            recentOutTotal: 0,
            floors: new Set(),
            cellsByFloor: new Map(),
            sizeGroups: new Set(),
            domainCodes: new Set(),
            cabinetNames: new Set(),
          });
          grouped.push(byKey.get(key));
        }
        const group = byKey.get(key);
        group.rows.push(row);
        group.total += Number(row?.count || 0);
        group.slotCount += 1;
        group.recentInTotal += Number(row?.recent_in_count || 0);
        group.recentOutTotal += Number(row?.recent_out_count || 0);
        if (Number(row?.count || 0) > 0) group.filledSlotCount += 1;
        if (row?.allowed_size_group) group.sizeGroups.add(String(row.allowed_size_group));
        if (row?.cabinet_domain_code) group.domainCodes.add(String(row.cabinet_domain_code));
        if (row?.cabinet_name) group.cabinetNames.add(String(row.cabinet_name));
        const floorCode = String(row?.column_code || "").trim();
        if (floorCode) {
          group.floors.add(floorCode);
          if (!group.cellsByFloor.has(floorCode)) group.cellsByFloor.set(floorCode, 0);
          group.cellsByFloor.set(floorCode, Number(group.cellsByFloor.get(floorCode) || 0) + 1);
        }
      }

      return grouped
        .map((group) => {
          const floorCodes = Array.from(group.floors).sort(compareCodeValue);
          let maxCellCount = 0;
          for (const count of group.cellsByFloor.values()) {
            maxCellCount = Math.max(maxCellCount, Number(count || 0));
          }
          const sizeCodes = Array.from(group.sizeGroups).sort(compareCodeValue);
          const domainCodes = Array.from(group.domainCodes).sort(compareCodeValue);
          const cabinetNamesText = Array.from(group.cabinetNames).sort(compareCodeValue).join(" · ");
          const floorCellSummary = floorCodes.length
            ? floorCodes.map((code) => `${code}:${formatCount(group.cellsByFloor.get(code) || 0)}`).join(" / ")
            : "-";
          const cabinetCount = group.cabinetNames.size;
          const groupedOrdering = Boolean(group.groupName && cabinetCount > 1);
          const sortedRows = [...group.rows].sort((a, b) => {
            const floorCompare = compareCodeValue(a?.column_code, b?.column_code);
            if (floorCompare !== 0) return floorCompare;
            if (groupedOrdering) {
              const cabinetOrderCompare = compareCodeValue(a?.cabinet_group_order || 0, b?.cabinet_group_order || 0);
              if (cabinetOrderCompare !== 0) return cabinetOrderCompare;
              const cabinetNameCompare = compareCodeValue(a?.cabinet_name, b?.cabinet_name);
              if (cabinetNameCompare !== 0) return cabinetNameCompare;
            }
            const cellCompare = compareCodeValue(a?.cell_code, b?.cell_code);
            if (cellCompare !== 0) return cellCompare;
            return compareCodeValue(a?.slot_code, b?.slot_code);
          });
          return {
            ...group,
            rows: sortedRows,
            floorCodes,
            floorCount: floorCodes.length,
            cellCount: maxCellCount,
            cabinetCount: group.cabinetNames.size,
            cabinetNamesText,
            floorCellSummary,
            domainText: domainCodes.length
              ? domainCodes.map((value) => dashboardDomainLabel(value)).join(", ")
              : "-",
            sizeGroupText: sizeCodes.length
              ? sizeCodes.map((value) => dashboardSizeGroupLabel(value)).join(", ")
              : "-",
          };
        })
        .sort((a, b) => {
          const rank = (group) => {
            if (group.isUnassigned) return 2;
            if (group.isOverflow) return 1;
            return 0;
          };
          const rankDiff = rank(a) - rank(b);
          if (rankDiff !== 0) return rankDiff;
          const groupCompare = compareCodeValue(a.groupName || a.title, b.groupName || b.title);
          if (groupCompare !== 0) return groupCompare;
          const orderCompare = compareCodeValue(a.groupOrder || 0, b.groupOrder || 0);
          if (orderCompare !== 0) return orderCompare;
          return compareCodeValue(a.title, b.title);
        });
    }

    function resolveDashboardStorageSlotId(slotRow) {
      const slotCode = String(slotRow?.slot_code || "").trim();
      if (!slotCode || slotCode === "UNASSIGNED") return 0;
      const slot = storageSlotCache.find((item) => String(item?.slot_code || "").trim() === slotCode);
      return Number(slot?.id || 0);
    }

    function findDashboardOwnedItemRow(ownedItemId) {
      const id = Number(ownedItemId || 0);
      if (id <= 0) return null;
      const pools = [
        Array.isArray(homeDashboardSlotItems) ? homeDashboardSlotItems : [],
        Array.isArray(homeDashboardSlotSelectionSnapshot) ? homeDashboardSlotSelectionSnapshot : [],
        Array.isArray(homeDashboardUnassignedItems) ? homeDashboardUnassignedItems : [],
        Array.isArray(homeDashboardSearchItems) ? homeDashboardSearchItems : [],
      ];
      for (const pool of pools) {
        const row = pool.find((item) => Number(item?.id || 0) === id);
        if (row) return row;
      }
      return null;
    }

    function ownedPreferredStorageSizeGroup(row) {
      return String(row?.preferred_storage_size_group || row?.size_group || "").trim();
    }

    function confirmSlotMismatchMove(targetSlot, items, actionLabel = t("common.action.move")) {
      const mismatches = getSlotMismatchRows(items, targetSlot);
      if (!mismatches.length) return true;
      const preview = mismatches.slice(0, 5).map((row) => {
        const label = String(row?.label_id || row?.id || "-").trim();
        const title = String(resolveOwnedAlbumName(row) || "-").trim();
        return `- ${label} | ${title} | ${dashboardSizeGroupLabel(ownedPreferredStorageSizeGroup(row) || "-")}`;
      }).join("\n");
      const moreText = mismatches.length > 5
        ? `\n${t("dashboard.slot_mismatch.more", { count: countWithUnit(mismatches.length - 5) })}`
        : "";
      return window.confirm(t("dashboard.slot_mismatch.confirm", {
        action: actionLabel,
        slot: storageSlotDisplayLabel(targetSlot),
        size_group: dashboardSizeGroupLabel(targetSlot?.allowed_size_group || "-"),
        count: countWithUnit(mismatches.length),
        preview: `${preview}${moreText}`,
      }));
    }

    function confirmSlotMismatchById(storageSlotId, items, actionLabel = t("common.action.save")) {
      const slot = getStorageSlotById(storageSlotId);
      if (!slot) return true;
      return confirmSlotMismatchMove(slot, items, actionLabel);
    }

    function clearDashboardDragHints() {
      document.querySelectorAll(".dashboard-floor-cell.drag-over, .dashboard-floor-cell.drop-ready").forEach((node) => node.classList.remove("drag-over", "drop-ready"));
      document.querySelectorAll(".dashboard-cabinet-map-cell.drag-over, .dashboard-cabinet-map-cell.drop-ready").forEach((node) => node.classList.remove("drag-over", "drop-ready"));
      document.querySelectorAll(".dashboard-slot-item-row.drag-before, .dashboard-slot-item-row.drag-after, .home-location-slot-item.drag-before, .home-location-slot-item.drag-after")
        .forEach((node) => node.classList.remove("drag-before", "drag-after"));
      $("homeDashSlotItems")?.classList.remove("drop-ready");
    }

    function resetDashboardDragState() {
      dashboardDraggedOwnedItemId = null;
      dashboardDraggedSelectionIds = [];
      dashboardDraggedSlotCode = null;
      dashboardDraggedSizeGroup = null;
      dashboardDraggedTitle = null;
      clearDashboardDragHints();
      document.querySelectorAll(".dashboard-slot-item-row.dragging, .home-location-slot-item.dragging")
        .forEach((node) => node.classList.remove("dragging"));
    }

    function shouldSuppressDashboardSelectionClick() {
      return dashboardPointerSelectionSuppressClickUntil > Date.now();
    }

    function clearDashboardPointerSelectionVisuals() {
      dashboardPointerSelectionPreviewIds = [];
      document.querySelectorAll(".dashboard-selection-preview").forEach((node) => node.classList.remove("dashboard-selection-preview"));
      ["homeDashSlotSelectionBoxLabel", "homeDashWorkbenchSelectionBoxLabel"].forEach((id) => {
        const label = $(id);
        if (!label) return;
        label.hidden = true;
        label.textContent = "";
      });
      ["homeDashSlotSelectionBox", "homeDashWorkbenchSelectionBox"].forEach((id) => {
        const node = $(id);
        if (!node) return;
        node.hidden = true;
        node.style.left = "0px";
        node.style.top = "0px";
        node.style.width = "0px";
        node.style.height = "0px";
      });
    }

    function finishDashboardPointerSelection() {
      const state = dashboardPointerSelectionState;
      if (!state) {
        clearDashboardPointerSelectionVisuals();
        return;
      }
      const previewIds = Array.from(new Set(dashboardPointerSelectionPreviewIds.map((value) => Number(value || 0)).filter((value) => value > 0)));
      const isDeselectMode = state.currentRect.left < state.startX;
      let appliedPreviewCount = 0;
      if (state.didMove && previewIds.length) {
        appliedPreviewCount = previewIds.length;
        clearDashboardDragHints();
        if (state.scope === "SLOT") {
          resetDashboardUnassignedSelection();
          resetDashboardSearchSelection();
          const nextSelected = new Set(homeDashboardSlotSelectedIds);
          previewIds.forEach((ownedItemId) => {
            if (isDeselectMode) nextSelected.delete(ownedItemId);
            else nextSelected.add(ownedItemId);
          });
          homeDashboardSlotSelectedIds = nextSelected;
          updateDashboardSlotSelectionSnapshot();
          renderDashboardSlotItems(getDashboardSlotRow(homeDashboardSelectedSlotCode));
          renderDashboardWorkbench();
        } else {
          resetDashboardSlotSelection();
          if (homeDashboardWorkbenchMode === "SEARCH") {
            resetDashboardUnassignedSelection();
            const nextSelected = new Set(homeDashboardSearchSelectedIds);
            previewIds.forEach((ownedItemId) => {
              if (isDeselectMode) nextSelected.delete(ownedItemId);
              else nextSelected.add(ownedItemId);
            });
            homeDashboardSearchSelectedIds = nextSelected;
          } else {
            resetDashboardSearchSelection();
            const nextSelected = new Set(homeDashboardUnassignedSelectedIds);
            previewIds.forEach((ownedItemId) => {
              if (isDeselectMode) nextSelected.delete(ownedItemId);
              else nextSelected.add(ownedItemId);
            });
            homeDashboardUnassignedSelectedIds = nextSelected;
          }
          renderDashboardWorkbench();
        }
        dashboardPointerSelectionSuppressClickUntil = Date.now() + 180;
      }
      try {
        state.root?.releasePointerCapture?.(state.pointerId);
      } catch (_) {}
      dashboardPointerSelectionState = null;
      clearDashboardPointerSelectionVisuals();
      renderDashboardSelectionSummary();
      if (state.didMove && appliedPreviewCount > 0) {
        setStatus(
          "homeDashboardStatus",
          "ok",
          isDeselectMode
            ? t("dashboard.selection.status.preview_removed", { count: countWithUnit(appliedPreviewCount) })
            : t("dashboard.selection.status.preview_added", { count: countWithUnit(appliedPreviewCount) })
        );
      }
    }

    function resetDashboardSlotSelection() {
      homeDashboardSlotSelectedIds = new Set();
      homeDashboardSlotSelectionSnapshot = [];
      homeDashboardSlotSelectionAnchorId = 0;
    }

    function resetDashboardUnassignedSelection() {
      homeDashboardUnassignedSelectedIds = new Set();
      homeDashboardUnassignedSelectionAnchorId = 0;
    }

    function resetDashboardSearchSelection() {
      homeDashboardSearchSelectedIds = new Set();
      homeDashboardSearchSelectionAnchorId = 0;
    }

    function toggleDashboardSlotSelectionById(ownedItemId) {
      if (isShellReadOnly()) return;
      const nextId = Number(ownedItemId || 0);
      if (!nextId) return;
      resetDashboardUnassignedSelection();
      resetDashboardSearchSelection();
      resetDashboardDragState();
      if (homeDashboardSlotSelectedIds.has(nextId)) homeDashboardSlotSelectedIds.delete(nextId);
      else homeDashboardSlotSelectedIds.add(nextId);
      homeDashboardSlotSelectionAnchorId = nextId;
      updateDashboardSlotSelectionSnapshot();
      renderDashboardSlotItems(getDashboardSlotRow(homeDashboardSelectedSlotCode));
      renderDashboardWorkbench();
    }

    function selectDashboardSingleSlotItemById(ownedItemId) {
      if (isShellReadOnly()) return;
      const nextId = Number(ownedItemId || 0);
      if (!nextId) return;
      resetDashboardUnassignedSelection();
      resetDashboardSearchSelection();
      resetDashboardDragState();
      homeDashboardSlotSelectedIds = new Set([nextId]);
      homeDashboardSlotSelectionAnchorId = nextId;
      updateDashboardSlotSelectionSnapshot();
      renderDashboardSlotItems(getDashboardSlotRow(homeDashboardSelectedSlotCode));
      renderDashboardWorkbench();
    }

    function selectDashboardSlotRangeToId(ownedItemId) {
      if (isShellReadOnly()) return;
      const nextId = Number(ownedItemId || 0);
      if (!nextId) return;
      const rows = Array.isArray(homeDashboardSlotItems) ? homeDashboardSlotItems : [];
      const targetIndex = rows.findIndex((row) => Number(row?.id || 0) === nextId);
      const anchorId = Number(homeDashboardSlotSelectionAnchorId || 0);
      const anchorIndex = rows.findIndex((row) => Number(row?.id || 0) === anchorId);
      if (targetIndex < 0 || anchorIndex < 0) {
        selectDashboardSingleSlotItemById(nextId);
        return;
      }
      resetDashboardUnassignedSelection();
      resetDashboardSearchSelection();
      resetDashboardDragState();
      const nextSelected = new Set(homeDashboardSlotSelectedIds);
      const start = Math.min(anchorIndex, targetIndex);
      const end = Math.max(anchorIndex, targetIndex);
      rows.slice(start, end + 1).forEach((row) => {
        const rowId = Number(row?.id || 0);
        if (rowId > 0) nextSelected.add(rowId);
      });
      homeDashboardSlotSelectedIds = nextSelected;
      updateDashboardSlotSelectionSnapshot();
      renderDashboardSlotItems(getDashboardSlotRow(homeDashboardSelectedSlotCode));
      renderDashboardWorkbench();
    }

    function toggleDashboardWorkbenchSelectionById(ownedItemId, source) {
      if (isShellReadOnly()) return;
      const nextId = Number(ownedItemId || 0);
      const nextSource = String(source || "").trim().toUpperCase();
      if (!nextId || !nextSource) return;
      resetDashboardDragState();
      if (nextSource === "SEARCH") {
        resetDashboardSlotSelection();
        resetDashboardUnassignedSelection();
        if (homeDashboardSearchSelectedIds.has(nextId)) homeDashboardSearchSelectedIds.delete(nextId);
        else homeDashboardSearchSelectedIds.add(nextId);
        homeDashboardSearchSelectionAnchorId = nextId;
      } else {
        resetDashboardSlotSelection();
        resetDashboardSearchSelection();
        if (homeDashboardUnassignedSelectedIds.has(nextId)) homeDashboardUnassignedSelectedIds.delete(nextId);
        else homeDashboardUnassignedSelectedIds.add(nextId);
        homeDashboardUnassignedSelectionAnchorId = nextId;
      }
      renderDashboardWorkbench();
    }

    function selectDashboardSingleWorkbenchItemById(ownedItemId, source) {
      if (isShellReadOnly()) return;
      const nextId = Number(ownedItemId || 0);
      const nextSource = String(source || "").trim().toUpperCase();
      if (!nextId || !nextSource) return;
      resetDashboardDragState();
      if (nextSource === "SEARCH") {
        resetDashboardSlotSelection();
        resetDashboardUnassignedSelection();
        homeDashboardSearchSelectedIds = new Set([nextId]);
        homeDashboardSearchSelectionAnchorId = nextId;
      } else {
        resetDashboardSlotSelection();
        resetDashboardSearchSelection();
        homeDashboardUnassignedSelectedIds = new Set([nextId]);
        homeDashboardUnassignedSelectionAnchorId = nextId;
      }
      renderDashboardWorkbench();
    }

    function selectDashboardWorkbenchRangeToId(ownedItemId, source) {
      if (isShellReadOnly()) return;
      const nextId = Number(ownedItemId || 0);
      const nextSource = String(source || "").trim().toUpperCase();
      if (!nextId || !nextSource) return;
      const rows = getDashboardWorkbenchRows();
      const targetIndex = rows.findIndex((row) => Number(row?.id || 0) === nextId);
      const anchorId = nextSource === "SEARCH"
        ? Number(homeDashboardSearchSelectionAnchorId || 0)
        : Number(homeDashboardUnassignedSelectionAnchorId || 0);
      const anchorIndex = rows.findIndex((row) => Number(row?.id || 0) === anchorId);
      if (targetIndex < 0 || anchorIndex < 0) {
        selectDashboardSingleWorkbenchItemById(nextId, nextSource);
        return;
      }
      resetDashboardDragState();
      if (nextSource === "SEARCH") {
        resetDashboardSlotSelection();
        resetDashboardUnassignedSelection();
        const nextSelected = new Set(homeDashboardSearchSelectedIds);
        const start = Math.min(anchorIndex, targetIndex);
        const end = Math.max(anchorIndex, targetIndex);
        rows.slice(start, end + 1).forEach((row) => {
          const rowId = Number(row?.id || 0);
          if (rowId > 0) nextSelected.add(rowId);
        });
        homeDashboardSearchSelectedIds = nextSelected;
      } else {
        resetDashboardSlotSelection();
        resetDashboardSearchSelection();
        const nextSelected = new Set(homeDashboardUnassignedSelectedIds);
        const start = Math.min(anchorIndex, targetIndex);
        const end = Math.max(anchorIndex, targetIndex);
        rows.slice(start, end + 1).forEach((row) => {
          const rowId = Number(row?.id || 0);
          if (rowId > 0) nextSelected.add(rowId);
        });
        homeDashboardUnassignedSelectedIds = nextSelected;
      }
      renderDashboardWorkbench();
    }

    function resetDashboardSlotPage() {
      homeDashboardSlotPage = 0;
      homeDashboardSlotShelfScrollLeft = 0;
    }

    function resetDashboardWorkbenchPage() {
      homeDashboardWorkbenchPage = 0;
      homeDashboardWorkbenchShelfScrollLeft = 0;
    }

    function setDashboardSlotViewMode(mode) {
      const next = String(mode || "").trim().toUpperCase();
      if (!["SHELF", "THUMB", "LIST"].includes(next)) return;
      if (homeDashboardSlotViewMode === next) {
        syncDashboardSlotViewButtons();
        return;
      }
      homeDashboardSlotViewMode = next;
      homeDashboardHoveredItemId = null;
      resetDashboardSlotPage();
      resetDashboardWorkbenchPage();
      syncDashboardSlotViewButtons();
      renderDashboardSlotItems(getDashboardSlotRow(homeDashboardSelectedSlotCode));
      renderDashboardWorkbench();
    }

    function scrollDashboardShelfSelectionIntoView(root) {
      const container = root || $("homeDashSlotItems");
      if (!container || !dashboardSlotUsesShelfScroll()) return;
      const selected = container.querySelector(".dashboard-slot-shelfcard.pick");
      if (!selected) return;
      const cardLeft = Number(selected.offsetLeft || 0);
      const cardRight = cardLeft + Number(selected.offsetWidth || 0);
      const viewportLeft = Number(container.scrollLeft || 0);
      const viewportRight = viewportLeft + Number(container.clientWidth || 0);
      const padding = 18;
      if (cardLeft >= viewportLeft + padding && cardRight <= viewportRight - padding) return;
      const nextLeft = Math.max(0, cardLeft - padding);
      container.scrollTo({ left: nextLeft, behavior: "smooth" });
    }

    function restoreDashboardShelfScroll(root) {
      if (!root || !dashboardSlotUsesShelfScroll()) return;
      const maxScrollLeft = Math.max(0, root.scrollWidth - root.clientWidth);
      root.scrollLeft = Math.min(Math.max(0, homeDashboardSlotShelfScrollLeft), maxScrollLeft);
    }

    function filterDashboardSlotItemsByMedia(items) {
      const list = Array.isArray(items) ? items : [];
      const category = dashboardSlotMediaFilterValue();
      if (category === "ANY") return list;
      return list.filter((row) => String(row?.category || "").trim().toUpperCase() === category);
    }

    function sortDashboardSlotItems(items, slotRow) {
      const list = Array.isArray(items) ? [...items] : [];
      const cabinetPolicy = String(slotRow?.cabinet_sort_policy || "ARTIST_RELEASE_TITLE").trim().toUpperCase();
      list.sort((a, b) => {
        if (cabinetPolicy === "LABEL_ID") {
          const labelA = String(a?.label_id || "").trim().toLocaleLowerCase();
          const labelB = String(b?.label_id || "").trim().toLocaleLowerCase();
          const labelCompare = labelA.localeCompare(labelB);
          if (labelCompare !== 0) return labelCompare;
        } else if (cabinetPolicy === "TITLE_RELEASE") {
          const titleA = normalizeTitleSortKey(a?.master_title || a?.item_title || a?.item_name_override || "");
          const titleB = normalizeTitleSortKey(b?.master_title || b?.item_title || b?.item_name_override || "");
          const titleCompare = titleA.localeCompare(titleB);
          if (titleCompare !== 0) return titleCompare;
          const releaseA = dashboardPreferredReleaseSortValue(a);
          const releaseB = dashboardPreferredReleaseSortValue(b);
          const releaseCompare = releaseA.localeCompare(releaseB);
          if (releaseCompare !== 0) return releaseCompare;
        } else {
          // ARTIST_RELEASE_TITLE (default) — article-stripped
          const artistA = normalizeArtistSortKey(a?.master_sort_artist_name || a?.artist_or_brand || a?.linked_artist_name || a?.master_artist_or_brand || "");
          const artistB = normalizeArtistSortKey(b?.master_sort_artist_name || b?.artist_or_brand || b?.linked_artist_name || b?.master_artist_or_brand || "");
          const artistCompare = artistA.localeCompare(artistB);
          if (artistCompare !== 0) return artistCompare;
          const releaseA = dashboardPreferredReleaseSortValue(a);
          const releaseB = dashboardPreferredReleaseSortValue(b);
          const releaseCompare = releaseA.localeCompare(releaseB);
          if (releaseCompare !== 0) return releaseCompare;
          const titleA = normalizeTitleSortKey(a?.master_title || a?.item_title || a?.item_name_override || "");
          const titleB = normalizeTitleSortKey(b?.master_title || b?.item_title || b?.item_name_override || "");
          const titleCompare = titleA.localeCompare(titleB);
          if (titleCompare !== 0) return titleCompare;
        }
        const createdA = String(a?.created_at || "").trim();
        const createdB = String(b?.created_at || "").trim();
        const createdCompare = createdB.localeCompare(createdA);
        if (createdCompare !== 0) return createdCompare;
        return Number(b?.id || 0) - Number(a?.id || 0);
      });
      return list;
    }

    function restoreDashboardWorkbenchShelfScroll(root) {
      if (!root || !dashboardSlotUsesShelfScroll()) return;
      const maxScrollLeft = Math.max(0, root.scrollWidth - root.clientWidth);
      root.scrollLeft = Math.min(Math.max(0, homeDashboardWorkbenchShelfScrollLeft), maxScrollLeft);
    }

    function setDashboardWorkbenchMode(mode) {
      const next = String(mode || "").trim().toUpperCase();
      if (!["UNASSIGNED", "SEARCH"].includes(next)) return;
      homeDashboardWorkbenchMode = next;
      resetDashboardWorkbenchPage();
      renderDashboardWorkbench();
    }

    function resetDashboardBulkEditForm() {
      if ($("homeDashBulkStatus")) $("homeDashBulkStatus").value = "";
      if ($("homeDashBulkDomainCode")) $("homeDashBulkDomainCode").value = "";
      if ($("homeDashBulkReleaseType")) $("homeDashBulkReleaseType").value = "";
      if ($("homeDashBulkSecondHand")) $("homeDashBulkSecondHand").value = "";
      if ($("homeDashBulkPurchaseSource")) $("homeDashBulkPurchaseSource").value = "";
      if ($("homeDashBulkPreferredSize")) $("homeDashBulkPreferredSize").value = "";
      if ($("homeDashBulkMemoryNote")) $("homeDashBulkMemoryNote").value = "";
    }

    async function restoreDashboardSelectedPreviousLocation() {
      const selectedRow = getDashboardSingleSelectedRow();
      if (!selectedRow) {
        setStatus("homeDashboardStatus", "err", t("dashboard.selection.status.restore_requires_one"));
        return;
      }
      const ownedItemId = Number(selectedRow?.id || 0);
      if (ownedItemId <= 0) {
        setStatus("homeDashboardStatus", "err", t("dashboard.selection.status.restore_missing_item"));
        return;
      }
      try {
        setStatus("homeDashboardStatus", "ok", t("dashboard.selection.status.restore_progress", { id: ownedItemId }));
        const res = await fetch(`/owned-items/${ownedItemId}/restore-previous-slot`, { method: "POST" });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("dashboard.selection.status.restore_failed"));

        resetDashboardSlotSelection();
        resetDashboardUnassignedSelection();
        resetDashboardSearchSelection();
        resetDashboardDragState();
        resetDashboardSlotPage();

        await loadHomeDashboard({ silent: true });

        const restoredSlotId = Number(data?.storage_slot_id || 0);
        const restoredSlot = restoredSlotId > 0
          ? (
            storageSlotCache.find((row) => Number(row?.id || 0) === restoredSlotId)
            || homeDashboardBySlot.find((row) => Number(row?.id || 0) === restoredSlotId)
            || null
          )
          : null;

        if (restoredSlot) {
          homeDashboardSelectedCabinetKey = dashboardCabinetKey(restoredSlot);
          homeDashboardSelectedSlotCode = String(restoredSlot.slot_code || "").trim();
          renderDashboardSlotCards(homeDashboardBySlot, homeDashboardInCollectionItems);
          await loadDashboardSlotItems(restoredSlot, { silent: true });
          setStatus("homeDashboardStatus", "ok", t("dashboard.selection.status.restore_done_slot", {
            slot: storageSlotDisplayLabel(restoredSlot),
          }));
        } else {
          setDashboardWorkbenchMode("UNASSIGNED");
          renderDashboardSlotCards(homeDashboardBySlot, homeDashboardInCollectionItems);
          renderDashboardWorkbench();
          setStatus("homeDashboardStatus", "ok", t("dashboard.selection.status.restore_done_unslotted"));
        }

        refreshOpsExceptionInBackground();
        if (Number(homeSelectedItemId || 0) === ownedItemId) {
          refreshHomeManageContext(ownedItemId, {
            keepMasterContext: Boolean(homeSelectedMasterId),
            masterId: homeSelectedMasterId,
            reloadMaster: Boolean(homeSelectedMasterId),
          }).catch(() => {});
        }
      } catch (err) {
        setStatus("homeDashboardStatus", "err", err.message);
      }
    }

    async function applyDashboardBulkEdit() {
      const selectedRows = getDashboardSelectedWorkbenchRows();
      const ownedItemIds = selectedRows.map((row) => Number(row?.id || 0)).filter((id) => id > 0);
      if (!ownedItemIds.length) {
        setStatus("homeDashboardStatus", "err", t("dashboard.bulk.status.select_first"));
        return;
      }
      const payload = {
        owned_item_ids: ownedItemIds,
        status: $("homeDashBulkStatus").value || null,
        domain_code: $("homeDashBulkDomainCode").value || null,
        release_type: $("homeDashBulkReleaseType").value || null,
        is_second_hand: $("homeDashBulkSecondHand").value === "" ? null : $("homeDashBulkSecondHand").value === "1",
        purchase_source: $("homeDashBulkPurchaseSource").value.trim() || null,
        preferred_storage_size_group: $("homeDashBulkPreferredSize").value || null,
        append_memory_note: $("homeDashBulkMemoryNote").value.trim() || null,
      };
      if (
        !payload.status
        && !payload.domain_code
        && !payload.release_type
        && payload.is_second_hand == null
        && !payload.purchase_source
        && !payload.preferred_storage_size_group
        && !payload.append_memory_note
      ) {
        setStatus("homeDashboardStatus", "err", t("dashboard.bulk.status.require_field"));
        return;
      }
      try {
        setStatus("homeDashboardStatus", "ok", t("dashboard.bulk.status.progress", { count: countWithUnit(ownedItemIds.length) }));
        const res = await fetch("/owned-items/bulk-update", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("dashboard.bulk.status.failed"));
        applyDashboardBulkUpdateLocal(data.updated_item_ids || [], payload);
        setStatus("homeDashboardStatus", "ok", t("dashboard.bulk.status.complete", {
          count: countWithUnit(data.updated_count || 0),
        }));
        resetDashboardBulkEditForm();
        refreshOpsExceptionInBackground();
        if ($("tabManage")?.classList.contains("active") && data.updated_item_ids?.includes(Number(homeSelectedItemId || 0))) {
          refreshHomeManageContext(Number(homeSelectedItemId), {
            keepMasterContext: Boolean(homeSelectedMasterId),
            masterId: homeSelectedMasterId,
            reloadMaster: Boolean(homeSelectedMasterId),
          }).catch(() => {});
        }
      } catch (err) {
        setStatus("homeDashboardStatus", "err", err.message);
      }
    }

    function filterDashboardWorkbenchItems(items) {
      return filterDashboardWorkbenchItemsByMedia(items);
    }

    function filterDashboardWorkbenchItemsByMedia(items) {
      let list = Array.isArray(items) ? items : [];
      const category = dashboardWorkbenchMediaFilterValue();
      if (category !== "ANY") {
        list = list.filter((row) => String(row?.category || "").trim().toUpperCase() === category);
      }
      list = list.filter((row) => dashboardWorkbenchMatchesDomainFilter(row));
      if (dashboardWorkbenchSortWarningOnlyValue()) {
        list = list.filter((row) => dashboardWorkbenchNeedsSortWarning(row));
      }
      return list;
    }

    function sortDashboardWorkbenchItems(items) {
      const list = Array.isArray(items) ? [...items] : [];
      const sortMode = dashboardWorkbenchSortModeValue();
      list.sort((a, b) => {
        const warningCompare = Number(dashboardWorkbenchNeedsSortWarning(b)) - Number(dashboardWorkbenchNeedsSortWarning(a));
        if (warningCompare !== 0) return warningCompare;
        if (sortMode === "NAME_ASC") {
          const artistA = normalizeArtistSortKey(a?.master_sort_artist_name || a?.artist_or_brand || a?.linked_artist_name || a?.master_artist_or_brand || "");
          const artistB = normalizeArtistSortKey(b?.master_sort_artist_name || b?.artist_or_brand || b?.linked_artist_name || b?.master_artist_or_brand || "");
          const artistCompare = artistA.localeCompare(artistB);
          if (artistCompare !== 0) return artistCompare;
          const releaseA = dashboardPreferredReleaseSortValue(a);
          const releaseB = dashboardPreferredReleaseSortValue(b);
          const releaseCompare = releaseA.localeCompare(releaseB);
          if (releaseCompare !== 0) return releaseCompare;
          const titleA = normalizeTitleSortKey(a?.master_title || a?.item_title || a?.item_name_override || "");
          const titleB = normalizeTitleSortKey(b?.master_title || b?.item_title || b?.item_name_override || "");
          const titleCompare = titleA.localeCompare(titleB);
          if (titleCompare !== 0) return titleCompare;
        }
        const createdA = String(a?.created_at || "").trim();
        const createdB = String(b?.created_at || "").trim();
        const createdCompare = createdB.localeCompare(createdA);
        if (createdCompare !== 0) return createdCompare;
        return Number(b?.id || 0) - Number(a?.id || 0);
      });
      return list;
    }

    function saveDashboardWorkbenchPreferences() {
      const role = currentSessionRoleCode();
      const map = loadRoleScopedMap(DASHBOARD_WORKBENCH_PREFS_KEY);
      map[role] = {
        category: dashboardWorkbenchMediaFilterValue(),
        signature_mode: dashboardWorkbenchSignatureModeValue(),
        sort_mode: dashboardWorkbenchSortModeValue(),
        sort_warning_only: dashboardWorkbenchSortWarningOnlyValue(),
        domain_filter: dashboardWorkbenchDomainFilterValue(),
        slot_sort_mode: dashboardSlotSortModeValue(),
        artist: String($("homeDashSearchArtist")?.value || "").trim(),
        title: String($("homeDashSearchTitle")?.value || "").trim(),
        catalog_no: String($("homeDashSearchCatalogNo")?.value || "").trim(),
        barcode: String($("homeDashSearchBarcode")?.value || "").trim(),
      };
      saveRoleScopedMap(DASHBOARD_WORKBENCH_PREFS_KEY, map);
    }

    async function loadDashboardUnassignedItems(opts = {}) {
      const silent = Boolean(opts?.silent);
      try {
        homeDashboardUnassignedLoading = true;
        resetDashboardWorkbenchPage();
        renderDashboardUnassignedItems();
        const category = String($("homeDashMediaFilter")?.value || "ANY").trim().toUpperCase() || "ANY";
        const signatureMode = dashboardWorkbenchSignatureModeValue();
        const params = new URLSearchParams({
          status: "IN_COLLECTION",
          slot_state: "UNSLOTTED",
          sort: "DISPLAY",
          limit: "300",
        });
        if (category !== "ANY") params.set("category", category);
        if (signatureMode !== "ANY") params.set("signature_mode", signatureMode);
        const res = await fetch(`/owned-items?${params.toString()}`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("dashboard.workbench.status.unslotted_load_failed"));
        homeDashboardUnassignedItems = Array.isArray(data) ? data : [];
        const nextSelected = new Set();
        for (const row of homeDashboardUnassignedItems) {
          const ownedItemId = Number(row?.id || 0);
          if (ownedItemId > 0 && homeDashboardUnassignedSelectedIds.has(ownedItemId)) {
            nextSelected.add(ownedItemId);
          }
        }
        homeDashboardUnassignedSelectedIds = nextSelected;
        renderDashboardUnassignedItems();
      } catch (err) {
        homeDashboardUnassignedItems = [];
        renderDashboardUnassignedItems();
        if (!silent) setStatus("homeDashboardStatus", "err", err.message);
      } finally {
        homeDashboardUnassignedLoading = false;
        renderDashboardUnassignedItems();
      }
    }

    async function loadDashboardSearchItems(opts = {}) {
      const silent = Boolean(opts?.silent);
      try {
        homeDashboardWorkbenchMode = "SEARCH";
        homeDashboardSearchLoading = true;
        resetDashboardWorkbenchPage();
        renderDashboardWorkbench();
        if (!silent) setStatus("homeDashboardStatus", "ok", t("dashboard.workbench.status.search_loading"));
        const params = new URLSearchParams({
          status: "IN_COLLECTION",
          sort: "DISPLAY",
          limit: "100",
        });
        const category = String($("homeDashMediaFilter")?.value || "ANY").trim().toUpperCase() || "ANY";
        const signatureMode = dashboardWorkbenchSignatureModeValue();
        const artist = $("homeDashSearchArtist")?.value.trim() || "";
        const title = $("homeDashSearchTitle")?.value.trim() || "";
        const catalogNo = $("homeDashSearchCatalogNo")?.value.trim() || "";
        const barcode = $("homeDashSearchBarcode")?.value.trim() || "";
        if (category !== "ANY") params.set("category", category);
        if (signatureMode !== "ANY") params.set("signature_mode", signatureMode);
        if (artist) params.set("artist_or_brand", artist);
        if (title) params.set("item_name", title);
        if (catalogNo) params.set("catalog_no", catalogNo);
        if (barcode) params.set("barcode", barcode);
        const res = await fetch(`/owned-items?${params.toString()}`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("dashboard.workbench.status.search_load_failed"));
        homeDashboardSearchItems = Array.isArray(data) ? data : [];
        const nextSelected = new Set();
        for (const row of homeDashboardSearchItems) {
          const ownedItemId = Number(row?.id || 0);
          if (ownedItemId > 0 && homeDashboardSearchSelectedIds.has(ownedItemId)) nextSelected.add(ownedItemId);
        }
        homeDashboardSearchSelectedIds = nextSelected;
        homeDashboardWorkbenchMode = "SEARCH";
        renderDashboardWorkbench();
        if (!silent) {
          setStatus("homeDashboardStatus", "ok", t("dashboard.workbench.status.search_complete", { count: formatCount(homeDashboardSearchItems.length) }));
          $("homeDashWorkbenchList")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
      } catch (err) {
        homeDashboardSearchItems = [];
        renderDashboardWorkbench();
        if (!silent) setStatus("homeDashboardStatus", "err", err.message);
      } finally {
        homeDashboardSearchLoading = false;
        renderDashboardWorkbench();
      }
    }

    async function openDashboardSelectedItemForEdit() {
      const row = getDashboardSingleSelectedRow();
      const ownedItemId = Number(row?.id || 0);
      if (ownedItemId <= 0) {
        setStatus("homeDashboardStatus", "err", t("dashboard.selection.status.select_one_item_to_edit"));
        return;
      }
      const masterId = Number(row?.linked_album_master_id || row?.album_master_id || 0);
      await openMediaSearchDetailManage(masterId, ownedItemId);
    }

    function findDashboardOwnedItemRowById(ownedItemId, sourceKind = "SLOT") {
      const targetOwnedItemId = Number(ownedItemId || 0);
      if (targetOwnedItemId <= 0) return null;
      const normalizedSourceKind = String(sourceKind || "").trim().toUpperCase();
      if (normalizedSourceKind === "SLOT") {
        const source = Array.isArray(homeDashboardSlotSelectionSnapshot) && homeDashboardSlotSelectionSnapshot.length
          ? homeDashboardSlotSelectionSnapshot
          : (Array.isArray(homeDashboardSlotItems) ? homeDashboardSlotItems : []);
        return source.find((row) => Number(row?.id || 0) === targetOwnedItemId) || null;
      }
      if (normalizedSourceKind === "UNASSIGNED") {
        return filterDashboardWorkbenchItems(homeDashboardUnassignedItems)
          .find((row) => Number(row?.id || 0) === targetOwnedItemId) || null;
      }
      if (normalizedSourceKind === "SEARCH") {
        return filterDashboardWorkbenchItems(homeDashboardSearchItems)
          .find((row) => Number(row?.id || 0) === targetOwnedItemId) || null;
      }
      return null;
    }

    async function openDashboardOwnedItemDetailManage(ownedItemId, sourceKind = "SLOT") {
      const targetOwnedItemId = Number(ownedItemId || 0);
      if (targetOwnedItemId <= 0) return;
      const row = findDashboardOwnedItemRowById(targetOwnedItemId, sourceKind);
      const masterId = Number(row?.linked_album_master_id || row?.album_master_id || 0);
      await openMediaSearchDetailManage(masterId, targetOwnedItemId);
    }

    async function refreshDashboardSelectedSlotDetail() {
      const currentSlotCode = String(homeDashboardSelectedSlotCode || "").trim();
      try {
        setStatus("homeDashboardStatus", "ok", t("dashboard.cover_flow.status.refreshing"));
        await loadHomeDashboard({ silent: true });
        const nextSlotRow = currentSlotCode ? getDashboardSlotRow(currentSlotCode) : null;
        if (currentSlotCode && nextSlotRow) {
          await loadDashboardSlotItems(nextSlotRow, { silent: true });
        }
        setStatus("homeDashboardStatus", "ok", t("dashboard.cover_flow.status.refreshed"));
      } catch (err) {
        setStatus("homeDashboardStatus", "err", errorMessageText(err, t("dashboard.status.load_failed")));
      }
    }

    async function refreshDashboardCabinetGroup(groupKey) {
      const cabinetKey = String(groupKey || "").trim();
      if (!cabinetKey) return;
      try {
        setStatus("homeDashboardStatus", "ok", t("dashboard.cover_flow.status.refreshing"));
        await loadHomeDashboard({ silent: true });
        setStatus("homeDashboardStatus", "ok", t("dashboard.cover_flow.status.refreshed"));
      } catch (err) {
        setStatus("homeDashboardStatus", "err", errorMessageText(err, t("dashboard.status.load_failed")));
      }
    }

    async function moveDashboardOwnedItemsToSlot(items, targetSlotCode, opts = {}) {
      const targetRow = getDashboardSlotRow(targetSlotCode);
      const targetSlotId = resolveDashboardStorageSlotId(targetRow);
      if (!targetRow || !targetSlotId) {
        setStatus("homeDashboardStatus", "err", t("dashboard.move.target_slot_id_missing"));
        return;
      }
      const list = Array.isArray(items) ? items : [];
      const eligible = list.filter((row) => Number(row?.id || 0) > 0);
      if (!eligible.length) {
        setStatus("homeDashboardStatus", "err", t("dashboard.move.no_items"));
        return;
      }
      const sourceKind = getDashboardSelectionSourceKind();
      const mismatchRows = getSlotMismatchRows(eligible, targetRow);
      const warningRows = eligible.filter((row) => dashboardWorkbenchNeedsSortWarning(row));
      if (mismatchRows.length && !confirmSlotMismatchMove(targetRow, eligible, t("common.action.move"))) {
        setStatus("homeDashboardStatus", "ok", t("dashboard.move.cancelled"));
        return;
      }

      previewDashboardTargetSlot(targetSlotCode);
      setStatus(
        "homeDashboardStatus",
        "ok",
        t("dashboard.move.progress", {
          count: formatCount(eligible.length),
          slot: storageSlotDisplayLabel(targetRow),
          warning: [
            mismatchRows.length ? t("dashboard.move.progress_warning", { count: formatCount(mismatchRows.length) }) : "",
            warningRows.length ? t("dashboard.move.progress_sort_warning", { count: formatCount(warningRows.length) }) : "",
          ].filter(Boolean).join(""),
        })
      );

      let moved = 0;
      const failed = [];
      const failedIds = new Set();
      for (const row of eligible) {
        const ownedItemId = Number(row?.id || 0);
        try {
          const res = await fetch(`/owned-items/${ownedItemId}/slot`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ storage_slot_id: targetSlotId }),
          });
          const data = await safeJson(res);
          if (!res.ok) throw new Error(data.detail || t("dashboard.move.failed"));
          moved += 1;
        } catch (err) {
          failedIds.add(ownedItemId);
          failed.push(`${row?.label_id || ownedItemId}: ${err.message}`);
        }
      }

      const movedIds = new Set(eligible
        .filter((row) => Number(row?.id || 0) > 0 && !failedIds.has(Number(row?.id || 0)))
        .map((row) => Number(row.id)));
      const movedWarningRows = eligible.filter((row) => {
        const ownedItemId = Number(row?.id || 0);
        return ownedItemId > 0 && movedIds.has(ownedItemId) && dashboardWorkbenchNeedsSortWarning(row);
      });
      if (movedIds.size) {
        cancelDashboardClickMoveMode({ silent: true, render: false });
        updateDashboardSlotCountsAfterMove(
          eligible.filter((row) => movedIds.has(Number(row?.id || 0))),
          targetRow
        );
        for (const ownedItemId of movedIds) {
          updateDashboardOwnedItemLocation(ownedItemId, targetRow);
        }
        homeDashboardUnassignedItems = (Array.isArray(homeDashboardUnassignedItems) ? homeDashboardUnassignedItems : [])
          .filter((row) => !movedIds.has(Number(row?.id || 0)));
        if (sourceKind === "SLOT") {
          homeDashboardSlotItems = (Array.isArray(homeDashboardSlotItems) ? homeDashboardSlotItems : [])
            .filter((row) => !movedIds.has(Number(row?.id || 0)));
          homeDashboardSlotItemsSlotCode = null;
        }
      }

      resetDashboardSlotSelection();
      resetDashboardUnassignedSelection();
      resetDashboardSearchSelection();
      homeDashboardSelectedCabinetKey = dashboardCabinetKey(targetRow);
      homeDashboardSelectedSlotCode = String(targetRow.slot_code || "").trim();
      renderDashboardSlotCards(homeDashboardBySlot, homeDashboardInCollectionItems);
      renderDashboardWorkbench();
      await loadDashboardSlotItems(targetRow, { silent: true });
      refreshOpsExceptionInBackground();

      const statusParts = [
        t("dashboard.move.done_bulk", { count: formatCount(moved), slot: storageSlotDisplayLabel(targetRow) }),
        mismatchRows.length ? t("dashboard.move.done_warning", { count: formatCount(mismatchRows.length) }) : null,
        movedWarningRows.length ? t("dashboard.move.done_sort_warning_followup", { count: formatCount(movedWarningRows.length) }) : null,
        failed.length ? t("dashboard.move.done_failed", { count: formatCount(failed.length) }) : null,
      ].filter(Boolean);
      setStatus("homeDashboardStatus", failed.length ? "err" : "ok", statusParts.join(" | "));
    }

    function setDashboardMoveSource(source) {
      dashboardDraggedOwnedItemId = Number(source?.ownedItemId || 0) || null;
      dashboardDraggedSlotCode = String(source?.slotCode || "").trim() || null;
      dashboardDraggedSizeGroup = String(source?.sizeGroup || "").trim() || null;
      dashboardDraggedTitle = String(source?.title || "").trim() || null;
      clearDashboardDragHints();
      const slotRow = getDashboardSlotRow(dashboardDraggedSlotCode);
      renderDashboardMoveTargets(slotRow);
      renderDashboardCabinetDetail();
    }

    function previewDashboardTargetSlot(slotCode) {
      const targetRow = getDashboardSlotRow(slotCode);
      if (!targetRow) return;
      homeDashboardSelectedCabinetKey = dashboardCabinetKey(targetRow);
      homeDashboardSelectedSlotCode = String(targetRow.slot_code || "").trim();
      homeDashboardSlotItems = [];
      homeDashboardSlotItemsSlotCode = null;
      renderDashboardSlotCards(homeDashboardBySlot, homeDashboardInCollectionItems);
    }

    async function moveDashboardOwnedItemToSlot(ownedItemId, targetSlotCode) {
      const sourceOwnedItemId = Number(ownedItemId || 0);
      const slotCode = String(targetSlotCode || "").trim();
      if (!sourceOwnedItemId || !slotCode) {
        setStatus("homeDashboardStatus", "err", t("dashboard.move.item_missing_target"));
        return;
      }
      const sourceSlotCode = getDashboardDraggedSlotCode();
      const sourceRow = getDashboardSlotRow(sourceSlotCode);
      const targetRow = getDashboardSlotRow(slotCode);
      const targetSlotId = resolveDashboardStorageSlotId(targetRow);
      if (!targetRow || !targetSlotId) {
        setStatus("homeDashboardStatus", "err", t("dashboard.move.target_slot_id_missing"));
        return;
      }
      const sourceItem = findDashboardOwnedItemRow(sourceOwnedItemId) || {
        id: sourceOwnedItemId,
        size_group: getDashboardDraggedSizeGroup() || "",
        item_name_override: dashboardDraggedTitle || `owned_item_id=${sourceOwnedItemId}`,
      };
      if (!confirmSlotMismatchMove(targetRow, [sourceItem], t("common.action.move"))) {
        setStatus("homeDashboardStatus", "ok", t("dashboard.move.cancelled"));
        resetDashboardDragState();
        return;
      }
      try {
        setStatus("homeDashboardStatus", "ok", t("dashboard.move.item_progress", { id: sourceOwnedItemId, slot: storageSlotDisplayLabel(targetRow) }));
        const res = await fetch(`/owned-items/${sourceOwnedItemId}/slot`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ storage_slot_id: targetSlotId }),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("dashboard.move.failed"));
        updateDashboardSlotCountsAfterMove([sourceItem], targetRow);
        updateDashboardOwnedItemLocation(sourceOwnedItemId, targetRow);
        homeDashboardUnassignedItems = (Array.isArray(homeDashboardUnassignedItems) ? homeDashboardUnassignedItems : [])
          .filter((row) => Number(row?.id || 0) !== sourceOwnedItemId);
        homeDashboardSelectedCabinetKey = dashboardCabinetKey(targetRow);
        homeDashboardSelectedSlotCode = slotCode;
        homeDashboardSlotItems = [];
        homeDashboardSlotItemsSlotCode = null;
        cancelDashboardClickMoveMode({ silent: true, render: false });
        renderDashboardSlotCards(homeDashboardBySlot, homeDashboardInCollectionItems);
        await loadDashboardSlotItems(targetRow, { silent: true });
        setStatus("homeDashboardStatus", "ok", t("dashboard.move.item_done", { id: data.owned_item_id, slot: storageSlotDisplayLabel(targetRow) }));
        refreshOpsExceptionInBackground();
      } catch (err) {
        setStatus("homeDashboardStatus", "err", err.message);
      } finally {
        resetDashboardDragState();
      }
    }

    async function moveDashboardOwnedItemRelative(ownedItemId, targetOwnedItemId, position) {
      const sourceOwnedItemId = Number(ownedItemId || 0);
      const targetId = Number(targetOwnedItemId || 0);
      const currentSlotRow = getDashboardSlotRow(String(homeDashboardSelectedSlotCode || "").trim());
      const currentSlotId = resolveDashboardStorageSlotId(currentSlotRow);
      const currentOrder = (Array.isArray(homeDashboardSlotItems) ? homeDashboardSlotItems : [])
        .map((row) => Number(row?.id || 0))
        .filter((id) => id > 0);
      if (!sourceOwnedItemId || !targetId) {
        setStatus("homeDashboardStatus", "err", t("dashboard.order.need_item_and_target"));
        return;
      }
      if (sourceOwnedItemId === targetId) {
        setStatus("homeDashboardStatus", "err", t("dashboard.order.same_item"));
        return;
      }
      if (!currentSlotId) {
        setStatus("homeDashboardStatus", "err", t("dashboard.order.missing_slot"));
        return;
      }
      if (!dashboardSlotAllowsManualOrder(currentSlotRow)) {
        setStatus("homeDashboardStatus", "err", t("dashboard.order.locked_artist_slot"));
        return;
      }
      const nextOrderedIds = currentOrder.slice();
      const sourceIndex = nextOrderedIds.indexOf(sourceOwnedItemId);
      if (sourceIndex >= 0) nextOrderedIds.splice(sourceIndex, 1);
      const targetIndex = nextOrderedIds.indexOf(targetId);
      if (targetIndex >= 0) {
        const insertIndex = position === "BEFORE" ? targetIndex : targetIndex + 1;
        nextOrderedIds.splice(Math.max(0, insertIndex), 0, sourceOwnedItemId);
      }
      try {
        setStatus("homeDashboardStatus", "ok", t("dashboard.order.progress", { source: sourceOwnedItemId, target: targetId, position }));
        const res = await fetch(`/storage-slots/${currentSlotId}/owned-items/${sourceOwnedItemId}/order`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target_owned_item_id: targetId,
            position,
          }),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("dashboard.order.failed"));
        applyDashboardSlotLocalOrder(nextOrderedIds);
        if (currentSlotRow) {
          await loadDashboardSlotItems(currentSlotRow, { silent: true });
        }
        setStatus("homeDashboardStatus", "ok", t("dashboard.order.done", { id: data.owned_item_id, rank: data.display_rank }));
      } catch (err) {
        setStatus("homeDashboardStatus", "err", err.message);
      } finally {
        resetDashboardDragState();
      }
    }

    async function moveDashboardSlotSelectionToEdge(direction) {
      const mode = String(direction || "").trim().toUpperCase();
      const currentSlotCode = String(homeDashboardSelectedSlotCode || "").trim();
      const loadedSlotCode = String(homeDashboardSlotItemsSlotCode || "").trim();
      const items = Array.isArray(homeDashboardSlotItems) ? homeDashboardSlotItems : [];
      if (!currentSlotCode || currentSlotCode !== loadedSlotCode || !items.length) {
        setStatus("homeDashboardStatus", "err", t("dashboard.order.need_current_slot"));
        return;
      }
      if (!["FRONT", "BACK"].includes(mode)) {
        setStatus("homeDashboardStatus", "err", t("dashboard.order.invalid_direction"));
        return;
      }
      const selected = items.filter((row) => homeDashboardSlotSelectedIds.has(Number(row?.id || 0)));
      if (!selected.length) {
        setStatus("homeDashboardStatus", "err", t("dashboard.order.need_checked_items"));
        return;
      }
      const unselected = items.filter((row) => !homeDashboardSlotSelectedIds.has(Number(row?.id || 0)));
      if (!unselected.length) {
        setStatus("homeDashboardStatus", "ok", t("dashboard.order.already_full_selection"));
        return;
      }

      const anchor = mode === "FRONT" ? unselected[0] : unselected[unselected.length - 1];
      const sequence = mode === "FRONT" ? selected : [...selected].reverse();
      const position = mode === "FRONT" ? "BEFORE" : "AFTER";
      const slotRow = getDashboardSlotRow(currentSlotCode);
      const currentSlotId = resolveDashboardStorageSlotId(slotRow);
      const nextOrderedIds = mode === "FRONT"
        ? [...selected.map((row) => Number(row?.id || 0)), ...unselected.map((row) => Number(row?.id || 0))]
        : [...unselected.map((row) => Number(row?.id || 0)), ...selected.map((row) => Number(row?.id || 0))];
      let moved = 0;

      if (!currentSlotId) {
        setStatus("homeDashboardStatus", "err", t("dashboard.order.missing_slot"));
        return;
      }
      if (!dashboardSlotAllowsManualOrder(slotRow)) {
        setStatus("homeDashboardStatus", "err", t("dashboard.order.locked_artist_slot"));
        return;
      }

      try {
        setStatus("homeDashboardStatus", "ok", t("dashboard.order.edge_progress", {
          mode: mode === "FRONT" ? t("dashboard.order.edge.front") : t("dashboard.order.edge.back"),
          count: formatCount(sequence.length),
        }));
        for (const row of sequence) {
          const ownedItemId = Number(row?.id || 0);
          if (!ownedItemId || ownedItemId === Number(anchor?.id || 0)) continue;
          const res = await fetch(`/storage-slots/${currentSlotId}/owned-items/${ownedItemId}/order`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              target_owned_item_id: Number(anchor.id),
              position,
            }),
          });
          const data = await safeJson(res);
          if (!res.ok) throw new Error(data.detail || t("dashboard.order.failed"));
          moved += 1;
        }
        applyDashboardSlotLocalOrder(nextOrderedIds);
        homeDashboardSlotPage = mode === "FRONT" ? 0 : Number.MAX_SAFE_INTEGER;
        homeDashboardSlotShelfScrollLeft = mode === "FRONT" ? 0 : Number.MAX_SAFE_INTEGER;
        const nextSlotRow = getDashboardSlotRow(currentSlotCode) || slotRow;
        if (nextSlotRow) {
          homeDashboardSelectedCabinetKey = dashboardCabinetKey(nextSlotRow);
          homeDashboardSelectedSlotCode = currentSlotCode;
          await loadDashboardSlotItems(nextSlotRow, { silent: true });
        }
        setStatus("homeDashboardStatus", "ok", t("dashboard.order.edge_done", {
          mode: mode === "FRONT" ? t("dashboard.order.edge.front") : t("dashboard.order.edge.back"),
          count: formatCount(moved),
        }));
      } catch (err) {
        setStatus("homeDashboardStatus", "err", err.message);
      }
    }

    function _saveDashboardCabinetMemory(cabinetKey, slotCode) {
      try { localStorage.setItem("__PROJECT_SLUG___dash_cabinet", JSON.stringify({ cabinetKey, slotCode, ts: Date.now() })); } catch(_) {}
    }
    function _loadDashboardCabinetMemory() {
      try { const v = localStorage.getItem("__PROJECT_SLUG___dash_cabinet"); return v ? JSON.parse(v) : null; } catch(_) { return null; }
    }
    function restoreDashboardCabinetSelectionMemory() {
      try {
        const raw = window.sessionStorage.getItem(DASHBOARD_CABINET_SELECTION_STORAGE_KEY);
        const parsed = JSON.parse(raw || "null");
        const cabinetKey = String(parsed?.cabinet_key || "").trim();
        const slotCode = String(parsed?.slot_code || "").trim();
        if (!cabinetKey) return;
        homeDashboardSelectedCabinetKey = cabinetKey;
        homeDashboardSelectedSlotCode = slotCode || null;
      } catch (_err) {
        // ignore sessionStorage read errors
      }
      // localStorage fallback (세션 간 기억)
      if (!homeDashboardSelectedCabinetKey) {
        try {
          const raw2 = window.localStorage.getItem(DASHBOARD_CABINET_SELECTION_STORAGE_KEY + '_persist');
          const parsed2 = JSON.parse(raw2 || 'null');
          const cabinetKey2 = String(parsed2?.cabinet_key || '').trim();
          const slotCode2 = String(parsed2?.slot_code || '').trim();
          if (cabinetKey2) {
            homeDashboardSelectedCabinetKey = cabinetKey2;
            homeDashboardSelectedSlotCode = slotCode2 || null;
          }
        } catch (_) {}
      }
    }

    function buildDashboardSlotGroupPages(groups) {
      const list = Array.isArray(groups) ? groups : [];
      const pages = [];
      for (let index = 0; index < list.length; index += 1) {
        const current = list[index];
        const currentSlotCount = Math.max(0, Number(current?.slotCount || 0));
        if (currentSlotCount >= 10) {
          pages.push({ start: index, end: index + 1, items: [current] });
          continue;
        }
        const next = list[index + 1];
        const nextSlotCount = Math.max(0, Number(next?.slotCount || 0));
        if (next && nextSlotCount < 10) {
          pages.push({ start: index, end: index + 2, items: [current, next] });
          index += 1;
          continue;
        }
        pages.push({ start: index, end: index + 1, items: [current] });
      }
      return pages;
    }

    async function loadDashboardSlotItems(slotRow, opts = {}) {
      const slotCode = String(slotRow?.slot_code || "").trim();
      const silent = Boolean(opts.silent);
      if (!slotRow || !slotCode) return;
      if (slotCode === "UNASSIGNED") {
        homeDashboardSlotItems = [];
        homeDashboardSlotItemsSlotCode = null;
        homeDashboardSlotItemsLoading = false;
        resetDashboardSlotPage();
        resetDashboardSlotSelection();
        renderDashboardCabinetDetail();
        if (!silent) setStatus("homeDashboardStatus", "ok", t("dashboard.slot.status.unslotted_block"));
        return;
      }

      const slotId = resolveDashboardStorageSlotId(slotRow);
      if (!slotId) {
        homeDashboardSlotItems = [];
        homeDashboardSlotItemsSlotCode = null;
        homeDashboardSlotItemsLoading = false;
        resetDashboardSlotPage();
        resetDashboardSlotSelection();
        renderDashboardCabinetDetail();
        if (!silent) setStatus("homeDashboardStatus", "err", t("dashboard.slot.status.missing_slot_id"));
        return;
      }

      try {
        homeDashboardSlotItemsLoading = true;
        renderDashboardCabinetDetail();
        if (!silent) {
          setStatus("homeDashboardStatus", "ok", t("dashboard.slot.status.loading", { slot: storageSlotDisplayLabel(slotRow) }));
        }
        const requestedSlotCode = slotCode;
        const res = await fetch(`/storage-slots/${slotId}/owned-items?limit=300`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("dashboard.slot.status.load_failed")));
        if (homeDashboardSelectedSlotCode !== requestedSlotCode) return;
        homeDashboardSlotItems = Array.isArray(data) ? data : [];
        homeDashboardSlotItemsSlotCode = requestedSlotCode;
        const nextSelected = new Set();
        for (const row of homeDashboardSlotItems) {
          const ownedItemId = Number(row?.id || 0);
          if (ownedItemId > 0 && homeDashboardSlotSelectedIds.has(ownedItemId)) nextSelected.add(ownedItemId);
        }
        homeDashboardSlotSelectedIds = nextSelected;
        updateDashboardSlotSelectionSnapshot();
        renderDashboardCabinetDetail();
        if (!silent) {
          setStatus("homeDashboardStatus", "ok", t("dashboard.slot.status.load_complete", {
            slot: storageSlotDisplayLabel(slotRow),
            count: countWithUnit(homeDashboardSlotItems.length),
          }));
        }
        renderDashboardWorkbench();
      } catch (err) {
        homeDashboardSlotItems = [];
        homeDashboardSlotItemsSlotCode = null;
        resetDashboardSlotPage();
        resetDashboardSlotSelection();
        renderDashboardCabinetDetail();
        renderDashboardWorkbench();
        if (!silent) setStatus("homeDashboardStatus", "err", err.message);
      } finally {
        homeDashboardSlotItemsLoading = false;
        renderDashboardCabinetDetail();
        renderDashboardWorkbench();
      }
    }

    function toggleDashboardCabinet(groupKey) {
      homeDashboardSlotGridFollowSelection = true;
      const nextKey = homeDashboardSelectedCabinetKey === groupKey ? null : groupKey;
      const preserveSlotSelection = homeDashboardSlotSelectedIds.size > 0;
      homeDashboardSelectedCabinetKey = nextKey;
      homeDashboardSelectedSlotCode = null;
      resetDashboardSlotPage();
      if (!preserveSlotSelection) {
        homeDashboardSlotItems = [];
        homeDashboardSlotItemsSlotCode = null;
        resetDashboardSlotSelection();
      }
      homeDashboardSlotItemsLoading = false;
      renderDashboardSlotCards(homeDashboardBySlot, homeDashboardInCollectionItems);
    }

    async function selectDashboardSlot(slotCode) {
      const groups = buildDashboardCabinetGroups(homeDashboardBySlot);
      const group = groups.find((item) => item.key === homeDashboardSelectedCabinetKey) || null;
      if (!group) return;
      const slotRow = group.rows.find((row) => String(row.slot_code || "").trim() === String(slotCode || "").trim()) || null;
      if (!slotRow) return;
      await openDashboardForResolvedSlot(slotRow);
    }

    function _dashThumb(url, title) {
      if (url) return `<img class="dash-activity-thumb" src="${url}" alt="" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><div class="dash-activity-thumb-placeholder" style="display:none">🎵</div>`;
      return `<div class="dash-activity-thumb-placeholder">🎵</div>`;
    }

    function _dashSizeChip(sg) {
      const map = { LP:"LP", LP10:'10"', LP7:'7"', CD:"CD", CASSETTE:"Tape", GOODS:"굿즈" };
      return map[sg] || sg || "";
    }

    async function loadDashboardRecentActivity() {
      try {
        const [regRes, buyRes, updRes] = await Promise.all([
          fetch("/dashboard/recent-registered"),
          fetch("/dashboard/recent-purchased"),
          fetch("/dashboard/recent-updated"),
        ]);
        const [reg, buy, upd] = await Promise.all([
          regRes.ok ? safeJson(regRes) : [],
          buyRes.ok ? safeJson(buyRes) : [],
          updRes.ok ? safeJson(updRes) : [],
        ]);

        // 최근 등록
        const regEl = document.getElementById("dashRecentRegistered");
        if (regEl) {
          if (!reg.length) { regEl.innerHTML = `<div class="mini" style="opacity:.4">없음</div>`; }
          else regEl.innerHTML = reg.map(r => `
            <div class="dash-activity-item" style="cursor:pointer" onclick="openDashboardOwnedItemDetailManage(${r.id})">
              ${_dashThumb(r.cover_image_url, r.title)}
              <div class="dash-activity-meta">
                <div class="dash-activity-title">${escapeHtml(r.title || "—")}</div>
                <div class="dash-activity-sub">${escapeHtml(r.artist || "")}</div>
                <div class="dash-activity-chips">
                  ${r.size_group ? `<span class="dash-activity-chip">${_dashSizeChip(r.size_group)}</span>` : ""}
                </div>
              </div>
            </div>`).join("");
        }

        // 최근 구매 (새상품)
        const buyEl = document.getElementById("dashRecentPurchased");
        if (buyEl) {
          if (!buy.length) { buyEl.innerHTML = `<div class="mini" style="opacity:.4">없음</div>`; }
          else buyEl.innerHTML = buy.map(r => `
            <div class="dash-activity-item" style="cursor:pointer" onclick="openDashboardOwnedItemDetailManage(${r.id})">
              ${_dashThumb(r.cover_image_url, r.title)}
              <div class="dash-activity-meta">
                <div class="dash-activity-title">${escapeHtml(r.title || "—")}${r.release_year ? ` (${r.release_year})` : ""}</div>
                <div class="dash-activity-sub">${escapeHtml(r.artist || "")}</div>
                <div class="dash-activity-chips">
                  <span class="dash-activity-chip is-new">새상품</span>
                  ${r.size_group ? `<span class="dash-activity-chip">${_dashSizeChip(r.size_group)}</span>` : ""}
                </div>
              </div>
            </div>`).join("");
        }

        // 최근 업데이트
        const updEl = document.getElementById("dashRecentUpdated");
        if (updEl) {
          if (!upd.length) { updEl.innerHTML = `<div class="mini" style="opacity:.4">없음</div>`; }
          else updEl.innerHTML = upd.map(r => {
            let genres = [];
            try { genres = JSON.parse(r.genres_json || "[]"); } catch(e) {}
            const chips = [];
            if (genres.length) chips.push(`<span class="dash-activity-chip has-genre">장르</span>`);
            if (r.catalog_no) chips.push(`<span class="dash-activity-chip has-catalog">카탈로그</span>`);
            if (r.media_type) chips.push(`<span class="dash-activity-chip has-media">미디어</span>`);
            if (r.source_code) chips.push(`<span class="dash-activity-chip has-source">${escapeHtml(r.source_code)}</span>`);
            return `
            <div class="dash-activity-item" style="cursor:pointer" onclick="openDashboardOwnedItemDetailManage(${r.id})">
              ${_dashThumb(r.cover_image_url, r.title)}
              <div class="dash-activity-meta">
                <div class="dash-activity-title">${escapeHtml(r.title || "—")}${r.release_year ? ` (${r.release_year})` : ""}</div>
                <div class="dash-activity-sub">${escapeHtml(r.artist || "")}</div>
                <div class="dash-activity-chips">${chips.join("")}</div>
              </div>
            </div>`;
          }).join("");
        }
      } catch(e) {
        console.warn("loadDashboardRecentActivity error", e);
      }
    }

    function _loadChartJs(cb) {
      if (window.Chart) { cb(); return; }
      const s = document.createElement("script");
      s.src = "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js";
      s.onload = cb;
      document.head.appendChild(s);
    }

    function _isDarkTheme() {
      const t = document.body.getAttribute("data-theme") || "";
      return ["night","ink","moss"].includes(t);
    }

    function initDashGauge(pct) {
      const ctx = document.getElementById("dashGaugeChart");
      if (!ctx) return;
      const dark = _isDarkTheme();
      const color = pct >= 90 ? "#4caf50" : pct >= 70 ? "#e05a1a" : "#e53935";
      const data = { datasets: [{ data: [pct, 100 - pct], backgroundColor: [color, dark ? "#2a2a2a" : "#e0e0e0"], borderWidth: 0, circumference: 180, rotation: 270 }] };
      const opts = { responsive: true, maintainAspectRatio: false, cutout: "72%", plugins: { legend: { display: false }, tooltip: { enabled: false } } };
      if (_dashCharts.gauge) { _dashCharts.gauge.destroy(); }
      _dashCharts.gauge = new Chart(ctx, { type: "doughnut", data, options: opts });
    }

    function initDashDomainChart(domainRows, domainCategoryRows) {
      const ctx = document.getElementById("dashDomainChart");
      if (!ctx) return;
      const dark = _isDarkTheme();

      const filteredDomains = (domainRows || [])
        .filter(r => r.value !== "UNASSIGNED")
        .slice(0, 8);

      const domainKeys = filteredDomains.map(r => r.value);
      const labels = filteredDomains.map(r => {
        const map = { WESTERN:"팝/웨스턴", KOREA:"가요", JAPAN:"J-POP", GREATER_CHINA:"중화권", OTHER_ASIA:"아시아", WORLD:"기타", UNKNOWN:"미분류" };
        return map[r.value] || r.value;
      });

      const categories = ["CD", "LP", "CASSETTE", "REEL_TO_REEL", "DIGITAL", "8TRACK"];
      const mediaColors = {
        CD: "#3a8fd6",
        LP: "#e05a1a",
        CASSETTE: "#9c6fd6",
        REEL_TO_REEL: "#4caf50",
        DIGITAL: "#888",
        "8TRACK": "#d6a63a"
      };
      const mediaLabels = {
        CD: "CD",
        LP: "LP",
        CASSETTE: "Tape",
        REEL_TO_REEL: "Reel",
        DIGITAL: "Digital",
        "8TRACK": "8-Track"
      };

      const datasets = categories.map(cat => {
        const data = domainKeys.map(dom => {
          const match = (domainCategoryRows || []).find(r => r.domain === dom && r.category === cat);
          return match ? match.count : 0;
        });
        return {
          label: mediaLabels[cat] || cat,
          data: data,
          backgroundColor: mediaColors[cat] || "#ccc",
          borderWidth: 0
        };
      }).filter(ds => ds.data.some(val => val > 0));

      const opts = {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: "y",
        plugins: {
          legend: {
            display: true,
            position: "top",
            labels: {
              boxWidth: 12,
              color: dark ? "#ccc" : "#333",
              font: { size: 10 }
            }
          },
          tooltip: {
            mode: "index",
            intersect: false,
            callbacks: {
              label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.x}장`
            }
          }
        },
        scales: {
          x: {
            stacked: true,
            beginAtZero: true,
            grid: { color: dark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)" },
            ticks: { color: dark ? "#888" : "#666" }
          },
          y: {
            stacked: true,
            grid: { display: false },
            ticks: { color: dark ? "#aaa" : "#555", font: { size: 11 } }
          }
        }
      };

      const stackedTotalsPlugin = {
        id: "stackedTotals",
        afterDatasetsDraw(chart) {
          const { ctx, data } = chart;
          const fmtCount = typeof formatCount === "function" ? formatCount : String;
          const textColor = dark ? "rgba(255,255,255,0.7)" : "rgba(0,0,0,0.55)";
          data.labels.forEach((_, i) => {
            const total = data.datasets.reduce((s, ds) => s + (Number(ds.data[i]) || 0), 0);
            if (!total) return;
            let maxX = 0;
            data.datasets.forEach((_, dsIdx) => {
              const meta = chart.getDatasetMeta(dsIdx);
              if (meta.hidden) return;
              const bar = meta.data[i];
              if (bar && bar.x > maxX) maxX = bar.x;
            });
            const bar0 = chart.getDatasetMeta(0).data[i];
            ctx.save();
            ctx.font = "bold 10px sans-serif";
            ctx.fillStyle = textColor;
            ctx.textAlign = "left";
            ctx.textBaseline = "middle";
            ctx.fillText(fmtCount(total), maxX + 5, bar0 ? bar0.y : 0);
            ctx.restore();
          });
        }
      };

      if (_dashCharts.domain) { _dashCharts.domain.destroy(); }
      _dashCharts.domain = new Chart(ctx, {
        type: "bar",
        data: { labels, datasets },
        options: opts,
        plugins: [stackedTotalsPlugin]
      });
    }

    function initDashMediaChart(rows) {
      const ctx = document.getElementById("dashMediaChart");
      const legendEl = document.getElementById("dashMediaLegend");
      if (!ctx) return;
      const palette = { LP:"#e05a1a", CD:"#3a8fd6", CASSETTE:"#9c6fd6", REEL_TO_REEL:"#4caf50", DIGITAL:"#888", GOODS:"#d6a63a" };
      const labelMap = { LP:"LP", CD:"CD", CASSETTE:"Tape", REEL_TO_REEL:"Reel", DIGITAL:"Digital", GOODS:"Goods" };
      const filtered = (rows || []).filter(r => r.count > 0);
      const getKey = r => r.value ?? r.category ?? r.status ?? Object.values(r)[0];
      const labels = filtered.map(r => { const k = getKey(r); return labelMap[k] || k || '?'; });
      const data = filtered.map(r => r.count);
      const colors = filtered.map(r => palette[getKey(r)] || "#888");
      const total = data.reduce((a, b) => a + b, 0);
      const opts = {
        responsive: true, maintainAspectRatio: false, cutout: "62%",
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => " " + ctx.label + ": " + ctx.parsed } } }
      };
      if (_dashCharts.media) { _dashCharts.media.destroy(); }
      _dashCharts.media = new Chart(ctx, { type: "doughnut", data: { labels, datasets: [{ data, backgroundColor: colors, borderWidth: 0 }] }, options: opts });
      if (legendEl) {
        legendEl.innerHTML = filtered.map((r, i) =>
          `<div class="dash-media-legend-item"><span class="dash-media-legend-dot" style="background:${colors[i]}"></span>${labels[i]} ${total ? Math.round(data[i]/total*100) : 0}%</div>`
        ).join("");
      }
    }

    function updateDashMetaBars(data, musicTotal) {
      const setBar = (barId, val, total, color) => {
        const el = document.getElementById(barId);
        if (!el) return;
        const pct = total > 0 ? Math.min(Math.round(val / total * 100), 100) : 0;
        el.style.width = pct + "%";
      };
      const m = Number(musicTotal || 0);
      setBar("dashMetaGenreBar",   Number(data.genre_missing_items   || 0), m);
      setBar("dashMetaCatalogBar", Number(data.catalog_missing_items || 0), m);
      setBar("dashMetaMediaBar",   Number(data.media_missing_items   || 0), m);
      setBar("dashMetaCoverBar",   Number(data.cover_missing_items   || 0), m);
      setBar("dashMetaSourceBar",  Number(data.source_unlinked_items || 0), m);
      setBar("dashMetaMasterBar",  Number(data.master_unlinked_items || 0), m);
    }

    function updateDashCharts(data) {
      _loadChartJs(() => {
        const pct = Number(data.in_collection_items || 0) > 0
          ? Math.round(Number(data.slotted_in_collection_items || 0) / Number(data.in_collection_items || 0) * 100) : 0;
        initDashGauge(pct);
        initDashDomainChart(data.by_domain || [], data.by_domain_category || []);
        initDashSourceDomainChart(data.by_source_domain || []);
        initDashSourceMediaChart(data.by_source_category || []);
        initDashCategoryChart(data.by_category || []);
        initDashReleaseTypeChart(data.by_release_type || []);
      });
    }

    function _makeMiniDoughnut(canvasId, rows, labelFn, colorFn) {
      const canvas = document.getElementById(canvasId);
      if (!canvas) return;
      const filtered = (rows || []).filter(r => Number(r.count || 0) > 0);
      if (!filtered.length) return;
      const dark = _isDarkTheme();
      const labels = filtered.map(r => labelFn(r.value));
      const data   = filtered.map(r => Number(r.count || 0));
      const bgColors = filtered.map((r, i) => colorFn(r.value, i));
      const fmtCount = typeof formatCount === "function" ? formatCount : String;
      const prev = canvas._miniChart;
      if (prev) { try { prev.destroy(); } catch (_) {} }
      canvas._miniChart = new Chart(canvas, {
        type: "doughnut",
        data: { labels, datasets: [{ data, backgroundColor: bgColors, borderWidth: 0 }] },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: "52%",
          plugins: {
            legend: {
              position: "right",
              labels: {
                color: dark ? "rgba(255,255,255,0.65)" : "rgba(0,0,0,0.6)",
                font: { size: 9 },
                boxWidth: 8,
                padding: 5,
              },
            },
            tooltip: {
              callbacks: {
                label: ctx => {
                  const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                  const pct = total > 0 ? Math.round((ctx.raw / total) * 100) : 0;
                  return `${ctx.label}: ${fmtCount(ctx.raw)} (${pct}%)`;
                },
              },
            },
          },
        },
      });
    }

    function initDashCategoryChart(rows) {
      const CAT_COLORS = { LP:"#e05a1a", CD:"#3a8fd6", CASSETTE:"#9c6fd6", REEL_TO_REEL:"#4caf50", DIGITAL:"#888", "8TRACK":"#d6a63a" };
      const FALLBACK = ["#3b82f6","#8b5cf6","#10b981","#f59e0b","#ef4444","#6366f1"];
      const normalized = (rows || []).map(r => ({ value: r.category ?? r.value, count: r.count }));
      _makeMiniDoughnut(
        "dashCategoryChart",
        normalized,
        v => (typeof mediaDisplayLabel === "function" ? mediaDisplayLabel(v) : v),
        (v, i) => CAT_COLORS[v] || FALLBACK[i % FALLBACK.length]
      );
    }

    function initDashReleaseTypeChart(rows) {
      const RT_COLORS = { ALBUM:"#3b82f6", EP:"#8b5cf6", SINGLE:"#10b981", UNASSIGNED:"#888" };
      const RT_LABELS = { ALBUM:"정규", EP:"EP", SINGLE:"싱글", UNASSIGNED:"미분류" };
      const FALLBACK = ["#f59e0b","#ef4444","#6366f1","#ec4899"];
      _makeMiniDoughnut(
        "dashReleaseTypeChart",
        rows,
        v => RT_LABELS[v] || (typeof dashboardReleaseTypeLabel === "function" ? dashboardReleaseTypeLabel(v) : v),
        (v, i) => RT_COLORS[v] || FALLBACK[i % FALLBACK.length]
      );
    }

    function initDashSourceDomainChart(rows) {
      const canvas = $("dashSourceDomainChart");
      if (!canvas) return;
      const sourceMap = {};
      (rows || []).forEach(row => {
        const src = row.source || "MANUAL";
        if (!sourceMap[src]) sourceMap[src] = { domains: {} };
        sourceMap[src].domains[row.domain] = (sourceMap[src].domains[row.domain] || 0) + Number(row.count || 0);
      });
      const sourceTotals = Object.entries(sourceMap).map(([k, v]) => ({
        key: k,
        label: (typeof dashboardSourceLabel === "function") ? dashboardSourceLabel(k) : k,
        total: Object.values(v.domains).reduce((a, b) => a + b, 0),
        domains: v.domains,
      })).sort((a, b) => b.total - a.total).slice(0, 8);
      if (!sourceTotals.length) return;
      const allDomains = [...new Set(sourceTotals.flatMap(s => Object.keys(s.domains)))];
      const DOMAIN_COLORS = ["#3b82f6","#8b5cf6","#10b981","#f59e0b","#ef4444","#6366f1","#ec4899","#14b8a6","#f97316","#84cc16"];
      const datasets = allDomains.map((domain, i) => ({
        label: (typeof dashboardDomainLabel === "function") ? dashboardDomainLabel(domain) : domain,
        data: sourceTotals.map(s => s.domains[domain] || 0),
        backgroundColor: DOMAIN_COLORS[i % DOMAIN_COLORS.length],
        borderWidth: 0,
        borderRadius: 2,
      }));
      const isDark = ["night","ink","moss"].includes(document.documentElement.getAttribute("data-theme") || "");
      const textColor = isDark ? "rgba(255,255,255,0.6)" : "rgba(0,0,0,0.6)";
      const gridColor = isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)";
      if (window._dashSourceDomainChart) { try { window._dashSourceDomainChart.destroy(); } catch (_) {} window._dashSourceDomainChart = null; }
      window._dashSourceDomainChart = new Chart(canvas, {
        type: "bar",
        data: { labels: sourceTotals.map(s => s.label), datasets },
        options: {
          indexAxis: "y",
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${typeof formatCount === "function" ? formatCount(ctx.raw) : ctx.raw}` } },
          },
          scales: {
            x: { stacked: true, grid: { color: gridColor }, ticks: { color: textColor, font: { size: 10 }, maxTicksLimit: 5 } },
            y: { stacked: true, grid: { display: false }, ticks: { color: textColor, font: { size: 10 } } },
          },
        },
      });
    }

    function initDashSourceMediaChart(rows) {
      const canvas = $("dashSourceMediaChart");
      if (!canvas) return;
      const sourceMap = {};
      (rows || []).forEach(row => {
        const src = row.source || "MANUAL";
        if (!sourceMap[src]) sourceMap[src] = { categories: {} };
        sourceMap[src].categories[row.category] = (sourceMap[src].categories[row.category] || 0) + Number(row.count || 0);
      });
      const sourceTotals = Object.entries(sourceMap).map(([k, v]) => ({
        key: k,
        label: (typeof dashboardSourceLabel === "function") ? dashboardSourceLabel(k) : k,
        total: Object.values(v.categories).reduce((a, b) => a + b, 0),
        categories: v.categories,
      })).sort((a, b) => b.total - a.total).slice(0, 8);
      if (!sourceTotals.length) return;
      const CATEGORY_ORDER = ["LP", "CD", "CASSETTE", "8TRACK", "DIGITAL", "REEL_TO_REEL"];
      const CATEGORY_COLORS = { LP: "#8b5cf6", CD: "#3b82f6", CASSETTE: "#f59e0b", "8TRACK": "#ef4444", DIGITAL: "#10b981", REEL_TO_REEL: "#6366f1" };
      const allCategories = [...new Set([...CATEGORY_ORDER, ...sourceTotals.flatMap(s => Object.keys(s.categories))])].filter(c => sourceTotals.some(s => s.categories[c]));
      const datasets = allCategories.map((cat, i) => ({
        label: (typeof mediaDisplayLabel === "function") ? mediaDisplayLabel(cat) : cat,
        data: sourceTotals.map(s => s.categories[cat] || 0),
        backgroundColor: CATEGORY_COLORS[cat] || ["#14b8a6","#f97316","#84cc16","#ec4899"][i % 4],
        borderWidth: 0,
        borderRadius: 2,
      }));
      const isDark = ["night","ink","moss"].includes(document.documentElement.getAttribute("data-theme") || "");
      const textColor = isDark ? "rgba(255,255,255,0.6)" : "rgba(0,0,0,0.6)";
      const gridColor = isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)";
      if (window._dashSourceMediaChart) { try { window._dashSourceMediaChart.destroy(); } catch (_) {} window._dashSourceMediaChart = null; }
      window._dashSourceMediaChart = new Chart(canvas, {
        type: "bar",
        data: { labels: sourceTotals.map(s => s.label), datasets },
        options: {
          indexAxis: "y",
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${typeof formatCount === "function" ? formatCount(ctx.raw) : ctx.raw}` } },
          },
          scales: {
            x: { stacked: true, grid: { color: gridColor }, ticks: { color: textColor, font: { size: 10 }, maxTicksLimit: 5 } },
            y: { stacked: true, grid: { display: false }, ticks: { color: textColor, font: { size: 10 } } },
          },
        },
      });
    }

    function hexToRgb(hex) {
      var m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
      return m ? parseInt(m[1],16)+','+parseInt(m[2],16)+','+parseInt(m[3],16) : '128,128,128';
    }

    function initDashboardWidgets() {
      const settingsEl = $("homeDashWidgetSettings");
      const toggleBtn = $("homeDashWidgetSettingsBtn");
      if (!settingsEl || !toggleBtn) return;
      const gridEl = document.querySelector(".dashboard-widget-grid");
      const STORAGE_KEY = "homeDashWidgetVisibility";
      const ORDER_KEY = "homeDashWidgetOrder";

      function getCards() { return Array.from((gridEl || document).querySelectorAll("[data-widget-id]")); }
      function getMap() { try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"); } catch (_) { return {}; } }
      function saveMap(map) { try { localStorage.setItem(STORAGE_KEY, JSON.stringify(map)); } catch (_) {} }
      function getOrder() { try { return JSON.parse(localStorage.getItem(ORDER_KEY) || "[]"); } catch (_) { return []; } }
      function saveOrder(order) { try { localStorage.setItem(ORDER_KEY, JSON.stringify(order)); } catch (_) {} }

      function applyVisibility() {
        const map = getMap();
        getCards().forEach(card => {
          const id = card.dataset.widgetId;
          const defaultHidden = card.dataset.widgetDefaultHidden === "true";
          const stored = map[id];
          const isHidden = stored !== undefined ? stored === false : defaultHidden;
          card.dataset.widgetHidden = isHidden ? "true" : "false";
        });
      }

      function applyOrder() {
        if (!gridEl) return;
        const order = getOrder();
        if (!order.length) return;
        const cards = getCards();
        const cardMap = {};
        cards.forEach(c => { cardMap[c.dataset.widgetId] = c; });
        // Reorder: move cards matching the stored order to the front
        order.slice().reverse().forEach(id => {
          const card = cardMap[id];
          if (card && card.parentNode === gridEl) {
            gridEl.insertBefore(card, gridEl.firstChild);
          }
        });
      }


      function buildPanel() {
        const map = getMap();
        const cards = getCards();
        settingsEl.innerHTML = '<span class="dash-card-settings-label">카드 표시</span>';
        cards.forEach((card, idx) => {
          const id = card.dataset.widgetId;
          const label = card.dataset.widgetLabel || id;
          const defaultHidden = card.dataset.widgetDefaultHidden === "true";
          const stored = map[id];
          const isVisible = stored !== undefined ? stored !== false : !defaultHidden;

          const group = document.createElement("span");
          group.className = "dash-card-settings-group";

          // Toggle button
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "dash-card-toggle-btn" + (isVisible ? " active" : "");
          btn.textContent = label;
          btn.addEventListener("click", (e) => {
            e.stopPropagation();
            const m = getMap();
            m[id] = !isVisible;
            saveMap(m);
            applyVisibility();
            buildPanel();
          });

          group.appendChild(btn);
          settingsEl.appendChild(group);
        });
      }

      toggleBtn.addEventListener("click", () => {
        const visible = settingsEl.style.display !== "none";
        if (visible) { settingsEl.style.display = "none"; } else { buildPanel(); settingsEl.style.display = ""; }
      });

      /* ── drag & drop reordering ── */
      function initDashboardWidgetDragDrop() {
        if (!gridEl) return;
        let dragCard = null;

        getCards().forEach(card => {
          card.setAttribute("draggable", "true");

          card.addEventListener("dragstart", function(e) {
            dragCard = this;
            this.style.opacity = "0.4";
            e.dataTransfer.effectAllowed = "move";
            e.dataTransfer.setData("text/plain", this.dataset.widgetId);
          });

          card.addEventListener("dragend", function(e) {
            this.style.opacity = "";
            dragCard = null;
            document.querySelectorAll(".dash-card").forEach(c => c.classList.remove("drag-over"));
          });

          card.addEventListener("dragover", function(e) {
            e.preventDefault();
            e.dataTransfer.dropEffect = "move";
            if (this !== dragCard) {
              this.classList.add("drag-over");
            }
          });

          card.addEventListener("dragleave", function(e) {
            this.classList.remove("drag-over");
          });

          card.addEventListener("drop", function(e) {
            e.preventDefault();
            e.stopPropagation();
            this.classList.remove("drag-over");
            if (!dragCard || dragCard === this) return;

            const cards = Array.from(gridEl.querySelectorAll("[data-widget-id]"));
            const fromIdx = cards.indexOf(dragCard);
            const toIdx = cards.indexOf(this);

            // Swap DOM positions: move dragCard next to drop target
            if (fromIdx < toIdx) {
              this.parentNode.insertBefore(dragCard, this.nextSibling);
            } else {
              this.parentNode.insertBefore(dragCard, this);
            }

            // Save new order after DOM settled
            requestAnimationFrame(() => {
              const newOrder = Array.from(gridEl.querySelectorAll("[data-widget-id]")).map(c => c.dataset.widgetId);
              saveOrder(newOrder);
              buildPanel();
            });
          });
        });
      }

      initDashboardWidgetDragDrop();
      applyVisibility();
      applyOrder();
    }

    
    function _resetAllSearchFilters() {
      ["homeNewProduct","homePromo","homeLimitEd","homeSigDirect","homeSigPurchase"].forEach(id => {
        const el = document.getElementById(id); if (el) el.checked = false;
      });
      const osEl = document.getElementById("homeOwnershipStatus"); if (osEl) osEl.value = "";
      const domainEl = document.getElementById("homeSearchDomain"); if (domainEl) domainEl.value = "";
      const pkgList = document.getElementById("homePackagingList");
      if (pkgList) pkgList.querySelectorAll('input[type="checkbox"]').forEach(cb => { cb.checked = false; });
    }

    function initDashboardDrilldown() {
      // 소스보강 탭으로 이동하고 미연결 대상 로드
      function _goSource() {
        openAdminConsole("source");
        setTimeout(() => {
          const stateEl = document.getElementById("sourceWorkbenchSourceState");
          if (stateEl) stateEl.value = "MISSING";
          if (typeof loadSourceWorkbenchTargets === "function") loadSourceWorkbenchTargets();
        }, 200);
      }
      // 예외큐 탭으로 이동하고 특정 타입 로드
      function _goException(type) {
        openAdminConsole("ops");
        setTimeout(async () => {
          if (typeof switchSubTab === "function") switchSubTab("ops", "exception");
          const typeEl = document.getElementById("opsExceptionType");
          if (typeEl) typeEl.value = type;
          if (typeof loadOpsExceptionItems === "function") await loadOpsExceptionItems();
        }, 200);
      }
      // 검색 탭으로 이동하고 메타 결핍 체크박스 활성화
      function _goSearch(checkboxId) {
        openAdminConsole("search");
        setTimeout(() => {
          // 기존 메타 필터 체크박스 모두 초기화

          const target = document.getElementById(checkboxId);
          if (target) {
            target.checked = true;
            const details = document.getElementById("homeSearchAdvancedDetails");
            if (details) details.open = true;
          }
          if (typeof homeSearchOwnedItems === "function") homeSearchOwnedItems({ resetPage: true, suppressEmptyCta: true });
        }, 200);
      }
      function _goSearchProductFlag(checkboxId) {
        openAdminConsole("search");
        setTimeout(() => {
          ["homeNewProduct","homePromo","homeLimitEd"].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.checked = false;
          });
          const osEl = document.getElementById("homeOwnershipStatus");
          if (osEl) osEl.value = "";
          const target = document.getElementById(checkboxId);
          if (target) {
            target.checked = true;
            const details = document.getElementById("homeSearchAdvancedDetails");
            if (details) details.open = true;
          }
          if (typeof homeSearchOwnedItems === "function") homeSearchOwnedItems({ resetPage: true, suppressEmptyCta: true });
        }, 200);
      }
      function _goSearchOwnership(status) {
        openAdminConsole("search");
        setTimeout(() => {
          ["homeNewProduct","homePromo","homeLimitEd"].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.checked = false;
          });
          const osEl = document.getElementById("homeOwnershipStatus");
          if (osEl) osEl.value = status;
          const details = document.getElementById("homeSearchAdvancedDetails");
          if (details) details.open = true;
          if (typeof homeSearchOwnedItems === "function") homeSearchOwnedItems({ resetPage: true, suppressEmptyCta: true });
        }, 200);
      }
      const filterMap = {
        source_unlinked:         () => _goSource(),
        master_unlinked:         () => _goException("MASTER_MISSING"),
        cover_missing:           () => _goException("COVER_MISSING"),
        genre_missing:           () => { openAdminConsole("ops"); setTimeout(() => { const tabs=document.querySelectorAll(".subtab-btn"); tabs.forEach(b=>{if(b.textContent.includes("예외"))b.click();}); setTimeout(()=>{ const sel=document.getElementById("opsExceptionType"); if(sel){sel.value="GENRE_MISSING";sel.dispatchEvent(new Event("change"));} document.getElementById("opsExceptionLoadBtn")?.click(); },300); },200); },
        media_missing:           () => { openAdminConsole("ops"); setTimeout(() => { const tabs=document.querySelectorAll(".subtab-btn"); tabs.forEach(b=>{if(b.textContent.includes("예외"))b.click();}); setTimeout(()=>{ const sel=document.getElementById("opsExceptionType"); if(sel){sel.value="MEDIA_MISSING";sel.dispatchEvent(new Event("change"));} document.getElementById("opsExceptionLoadBtn")?.click(); },300); },200); },
        catalog_missing:         () => { openAdminConsole("ops"); setTimeout(() => { const tabs=document.querySelectorAll(".subtab-btn"); tabs.forEach(b=>{if(b.textContent.includes("예외"))b.click();}); setTimeout(()=>{ const sel=document.getElementById("opsExceptionType"); if(sel){sel.value="CATALOG_MISSING";sel.dispatchEvent(new Event("change"));} document.getElementById("opsExceptionLoadBtn")?.click(); },300); },200); },
        new_items:               () => _goSearchProductFlag("homeNewProduct"),
        promo_items:             () => { openAdminConsole("search"); setTimeout(() => { _resetAllSearchFilters(); const el=document.getElementById("homePromo");if(el)el.checked=true; const d=document.getElementById("homeSearchAdvancedDetails");if(d)d.open=true; if(typeof homeSearchOwnedItems==="function") homeSearchOwnedItems({resetPage:true,suppressEmptyCta:true}); },200); },
        other_items:             () => { openAdminConsole("search"); setTimeout(() => { ["homeNewProduct","homePromo","homeLimitEd"].forEach(id=>{const e=document.getElementById(id);if(e)e.checked=false;}); const o=document.getElementById("homeOwnershipStatus");if(o)o.value=""; if(typeof homeSearchOwnedItems==="function") homeSearchOwnedItems({resetPage:true,suppressEmptyCta:true}); },200); },
        ownership_in_collection: () => _goSearchOwnership("IN_COLLECTION"),
        ownership_loaned:        () => _goSearchOwnership("LOANED"),
        ownership_sold:          () => _goSearchOwnership("SOLD"),
        ownership_lost:          () => _goSearchOwnership("LOST"),
        limited_edition:         () => { openAdminConsole("search"); setTimeout(() => { _resetAllSearchFilters(); const el=document.getElementById("homeLimitEd");if(el)el.checked=true; const d=document.getElementById("homeSearchAdvancedDetails");if(d)d.open=true; if(typeof homeSearchOwnedItems==="function") homeSearchOwnedItems({resetPage:true,suppressEmptyCta:true}); },200); },
        sig_direct:              () => {
          openAdminConsole("search");
          setTimeout(() => {
            _resetAllSearchFilters();
            const sigD = document.getElementById("homeSigDirect");
            if (sigD) sigD.checked = true;
            const sigP = document.getElementById("homeSigPurchase");
            if (sigP) sigP.checked = true;
            const details = document.getElementById("homeSearchAdvancedDetails");
            if (details) details.open = true;
            if (typeof homeSearchOwnedItems === "function") homeSearchOwnedItems({ resetPage: true, suppressEmptyCta: true });
          }, 200);
        },
        box_set:                 () => {
          openAdminConsole("search");
          setTimeout(() => {
            _resetAllSearchFilters();
            const pkgList = document.getElementById("homePackagingList");
            if (pkgList) pkgList.querySelectorAll('input[type="checkbox"]').forEach(cb => {
              if (cb.value === "Box Set") cb.checked = true;
            });
            const details = document.getElementById("homeSearchAdvancedDetails");
            if (details) details.open = true;
            if (typeof homeSearchOwnedItems === "function") homeSearchOwnedItems({ resetPage: true, suppressEmptyCta: true });
          }, 200);
        },
        sig_purchase:            () => {
          openAdminConsole("search");
          setTimeout(() => {
            ["homeNewProduct","homePromo","homeLimitEd"].forEach(id => {
              const el = document.getElementById(id);
              if (el) el.checked = false;
            });
            const osEl = document.getElementById("homeOwnershipStatus");
            if (osEl) osEl.value = "";
            const sigD = document.getElementById("homeSigDirect");
            if (sigD) sigD.checked = false;
            const sigP = document.getElementById("homeSigPurchase");
            if (sigP) sigP.checked = true;
            const details = document.getElementById("homeSearchAdvancedDetails");
            if (details) details.open = true;
            if (typeof homeSearchOwnedItems === "function") homeSearchOwnedItems({ resetPage: true, suppressEmptyCta: true });
          }, 200);
        },
        unslotted:               () => {
          openAdminConsole("cabinet");
          setTimeout(() => {
            const unassignedBtn = document.getElementById("homeDashModeUnassignedBtn");
            if (unassignedBtn) unassignedBtn.click();
          }, 200);
        }
      };

      document.querySelectorAll("[data-dash-drilldown]").forEach(el => {
        el.onclick = null;
        el.addEventListener("click", () => {
          const key = el.dataset.dashDrilldown;
          if (filterMap[key]) { try { filterMap[key](); } catch(_) {} }
        });
      });
    }
      function humClass(h) {
        if (h == null) return "";
        if (h > 70 || h < 35) return "hum-alert";
        if (h >= 60 || h < 43) return "hum-warn";
        return "hum-ideal";
      }

    function initDashCardInteractions() {
      /* sparkline draw animation */
      document.querySelectorAll(".dash-card__spark polyline").forEach(poly => {
        const len = poly.getTotalLength();
        if (!len) return;
        poly.style.strokeDasharray = len;
        poly.style.strokeDashoffset = len;
        poly.style.transition = "stroke-dashoffset 1s ease-out";
        requestAnimationFrame(() => { poly.style.strokeDashoffset = "0"; });
      });

      /* bar-list click → filter navigation */
      document.querySelectorAll('.dash-card[data-role="bar-list"] .dash-bar-row').forEach(row => {
        row.addEventListener("click", function() {
          const filter = this.dataset.filter;
          if (filter && typeof applySearchFilter === "function") {
            applySearchFilter(filter);
          }
        });
      });

      /* alert click → exception queue */
      document.querySelectorAll('.dash-card[data-role="alerts"] .dash-card__alert-item').forEach(item => {
        item.addEventListener("click", function() {
          const alertType = this.dataset.alertType;
          if (alertType && typeof navigateToExceptionTab === "function") {
            navigateToExceptionTab(alertType);
          }
        });
      });
    }
    function _dLabel(code) { return _DOMAIN_LABEL[String(code||'').toUpperCase()] || code || ''; }

        async function loadAlbumOfDay() {
      try {
        const res = await fetch("/random-album");
        const data = await safeJson(res);
        if (!data.title) return;
        const artist = data.artist || "";
        const year = data.year ? "(" + data.year + ")" : "";
        const titleText = artist ? artist + " — " + data.title : data.title;
        const metaText = year;
        setTextIfPresent("homeDashAlbumOfDay", titleText);
        setTextIfPresent("homeDashAlbumOfDayMeta", metaText);
        const cover = document.getElementById("homeDashAlbumCover");
        const placeholder = document.getElementById("homeDashAlbumPlaceholder");
        if (cover && data.cover_url) {
          cover.src = data.cover_url;
        }
        // 장식장 이동 클릭 핸들러
        const card = document.getElementById("homeDashAlbumCard");
        if (card && (data.slot_code || data.owned_item_id)) {
          card.addEventListener("click", function() {
            if (typeof openCabinetLocationAction === "function") {
              openCabinetLocationAction(0, data.slot_code || "", "", "", "");
            }
          });
          card.title = data.slot_code ? data.slot_code + "에 배치됨" : "장식장으로 이동";
        }
        if (placeholder && data.cover_url) placeholder.style.display = "none";
      } catch (_) {}
    }

    var _DOMAIN_LABEL = {
      KOREA:'가요', JAPAN:'J-POP', WESTERN:'팝/웨스턴',
      GREATER_CHINA:'C-Pop', OTHER_ASIA:'아시아', WORLD:'월드',
      UNASSIGNED:'미분류', UNKNOWN:'미분류',
    };

async function loadDashboardClimate() {
      const outdoorTemp  = document.getElementById("homeDashOutdoorTemp");
      const outdoorHumid = document.getElementById("homeDashOutdoorHumid");
      const indoorTemp   = document.getElementById("homeDashIndoorTemp");
      const indoorHumid  = document.getElementById("homeDashIndoorHumid");
      const indoorBadge  = document.getElementById("homeDashIndoorBadge");
      const humGauge     = document.getElementById("homeDashHumGauge");
      if (!outdoorTemp && !indoorTemp) return;
      try {
        const res = await fetch("/operator/climate-compare");
        if (!res.ok) return;
        const d = await safeJson(res);
        const oh = d.outdoor_humidity_percent != null ? Math.round(d.outdoor_humidity_percent) : null;
        const ih = d.indoor_humidity_percent  != null ? Math.round(d.indoor_humidity_percent)  : null;
        if (outdoorTemp)  outdoorTemp.textContent = d.outdoor_temperature_c != null ? Number(d.outdoor_temperature_c).toFixed(1) : "--";
        if (outdoorHumid) { outdoorHumid.textContent = oh != null ? oh + "%" : "--%"; outdoorHumid.className = "climate-hum-sm " + humClass(oh); }
        if (indoorTemp)   indoorTemp.textContent  = d.indoor_temperature_c  != null ? Number(d.indoor_temperature_c).toFixed(1)  : "--";
        if (indoorHumid)  { indoorHumid.textContent = ih != null ? ih + "%" : "--%"; indoorHumid.className = "climate-hum-main " + humClass(ih); }
        if (humGauge && ih != null) {
          humGauge.style.width = Math.min(ih, 100) + "%";
          humGauge.className = "climate-gauge-fill " + humClass(ih);
        }
        if (indoorBadge && d.indoor_comfort_label) {
          indoorBadge.textContent = d.indoor_comfort_label;
          const cl = d.indoor_comfort_label;
          indoorBadge.className = "dashboard-climate-badge " + (cl === "쾌적" ? "ideal" : (cl === "건조" || cl === "습함") ? "warn" : "alert");
          indoorBadge.hidden = false;
        }
      } catch (_) {}
    }
