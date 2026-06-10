let opsAuthItems = [];
    let opsAuthSelectedUsername = "";
    let opsCameraItems = [];
    let opsCameraSelectedId = null;
    let opsCameraDiscoverItems = [];
    let opsProviderSettingsSnapshot = null;
    let appAuthSession = null;
    let appAuthSessionResolved = false;
    let appShellMode = "ops";
    let pendingOpsCabinetSelection = null;
    let mediaSearchSelectedContextItem = null;
    const discogsRepairEligibilityCache = new Map();
    let storageSlotCache = [];
    let mediaMode = "search";
    let adminBarcodeToastTimer = 0;
    let shellBarcodeToastTimer = 0;
    let adminBarcodeInputPulseTimer = 0;
    let imageGalleryRegistry = new Map();
    let imageGalleryCurrentKey = "";
    let imageGalleryCurrentItems = [];
    let imageGalleryCurrentIndex = 0;
    let shelfItems = [];
    let shelfSelectedId = null;
    let shelfPrevId = null;
    let shelfNextId = null;
    let shelfRelatedInfo = null;

    // 패키징 옵션 풍선도움말 (KO/EN/JA)

    // 구(한국어) 패키지 구성 값 → 신(영문) 변환 맵 (하위 호환)


    /* ── dashboard card interactions ── */

    /* call after dashboard render */
    if (typeof initDashCardInteractions === "function") {
      setTimeout(initDashCardInteractions, 300);
    }

    // ── 로컬 이미지 관리 ──────────────────────────────────────────
    // ─────────────────────────────────────────────────────────────

    /* ── Ops hero background catalog grid ── */
    (function buildOpsHeroGrid() {
      const grid = document.getElementById("opsHeroGrid");
      if (!grid) return;
      // Fill enough cells: 16 cols × rows determined by container height.
      // We generate 16×6 = 96 cells; extras are clipped by overflow:hidden.
      const TOTAL = 96;
      const ACCENT = new Set([3, 11, 18, 26, 34, 42, 50, 59, 67, 75, 83]);
      const SKY    = new Set([7, 15, 23, 31, 39, 47, 55, 63, 71, 79, 87]);
      const DURS   = [3.2, 4.4, 5.0, 3.8, 4.6, 2.9, 5.4, 3.5, 4.1, 2.7];
      const DELAYS = [-0.4, -1.2, -2.0, -2.8, -0.8, -1.6, -2.4, -3.2, -0.2, -1.8, -2.6, -0.6, -1.4, -3.0, -0.0, -2.2];
      for (let i = 0; i < TOTAL; i++) {
        const cell = document.createElement("span");
        cell.className = "ops-cell" +
          (ACCENT.has(i) ? " is-accent" : "") +
          (SKY.has(i)    ? " is-sky"    : "");
        cell.style.setProperty("--cell-dur",   DURS[i % DURS.length] + "s");
        cell.style.setProperty("--cell-delay", DELAYS[i % DELAYS.length] + "s");
        grid.appendChild(cell);
      }
    })();

    /* ── Ops home live clock ── */
    (function startOpsHeroClock() {
      const el = document.getElementById("opsHeroClock");
      if (!el) return;
      const fmt = new Intl.DateTimeFormat("ko-KR", {
        month: "numeric", day: "numeric", weekday: "short",
        hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
      });
      function tick() { el.textContent = fmt.format(new Date()); }
      tick();
      setInterval(tick, 1000);
    })();

    // Nav contract:
    // - operator: 운영 홈, 장식장
    // - admin: 운영 홈, 장식장, 관리
    // - non-admin shells stay read-only and must not expose request-write actions

    // 소스별 개별 상품(릴리즈) 링크 — DISCOGS·MANIADB·ALADIN 통합





    let _dashCharts = {};



    // ══════════════════════════════════════════════════════
    // ══════════════════════════════════════════════════════
    // Dashboard Card Renderers v2 — Cross-dimensional insights
    // ══════════════════════════════════════════════════════

    // ══════════════════════════════════════════════════════
    // Dashboard Card Renderers v2
    // ══════════════════════════════════════════════════════

    // ══════════════════════════════════════════════════════
    // Dashboard Card Renderers v2 — Cross-dimensional insights
    // ══════════════════════════════════════════════════════

    /* 대시보드 카드 공용 — 도메인 코드 → 표시명 */


    // -----------------------------------------------------------------------
    // 알라딘 → Discogs 마스터 매칭 백필
    // -----------------------------------------------------------------------
    let _aladinDiscogsBackfillPoller = null;

    let _spotifyBatchPoller = null;

    // ── Permission management ──────────────────────────────────────────────

    $("permSaveRoleBtn").addEventListener("click", saveRolePermissions);
    $("permLoadAccountBtn").addEventListener("click", loadAccountPermissions);
    $("permClearAccountBtn").addEventListener("click", clearAllPermOverrides);
    // ── End permission management ──────────────────────────────────────────

    (function initOpsExAdvancedFilters() {
      const opsExPkg = $("opsExPackagingList");
      if (opsExPkg) {
        const allPackaging = new Set();
        for (const mediaType in PACKAGING_OPTIONS_BY_MEDIA) {
          let mt = mediaType;
          if (mt === "CDr" || mt === "SACD") mt = "CD";
          if (mt === "All Media") mt = "VINYL";
          (PACKAGING_OPTIONS_BY_MEDIA[mt] || []).forEach(opt => allPackaging.add(opt));
        }
        opsExPkg.innerHTML = Array.from(allPackaging).sort().map(opt =>
          `<label><input type="checkbox" value="${escapeHtml(opt)}" /><span>${escapeHtml(opt)}</span></label>`
        ).join("");
        opsExPkg.querySelectorAll("input").forEach(cb =>
          cb.addEventListener("change", () => loadOpsExceptionItems())
        );
      }
      const opsExContents = $("opsExPackageContentsList");
      if (opsExContents) {
        const allContents = [
          "Inner Sleeve","Insert","Leaflet","Booklet","Photo Book",
          "Mini Poster / Tabloid","Postcard","Sticker","Bookmark",
          "Lenticular / Hologram Card","Photo Card","Film Cut",
          "CD Holder","Lyric Book","Poster","Scrapbook / Diary","Receipt",
        ];
        opsExContents.innerHTML = allContents.map(opt =>
          `<label><input type="checkbox" value="${escapeHtml(opt)}" /><span>${escapeHtml(opt)}</span></label>`
        ).join("");
        opsExContents.querySelectorAll("input").forEach(cb =>
          cb.addEventListener("change", () => loadOpsExceptionItems())
        );
      }
      ["opsExSigDirect","opsExSigPurchase","opsExNewProduct","opsExPromo","opsExLimitEd"].forEach(id => {
        $(id)?.addEventListener("change", () => loadOpsExceptionItems());
      });
    })();

    // ── 2-3: 상품 연계 수집품 ─────────────────────────────────────────────

    $("tabHomeBtn").addEventListener("click", () => openAdminConsole("home"));
    $("tabCabinetBtn").addEventListener("click", () => openAdminConsole("cabinet"));
    $("tabSimpleBtn").addEventListener("click", () => switchShellMode("ops"));
    $("tabMediaBtn").addEventListener("click", () => openAdminConsole("media"));
    $("tabCollectiblesBtn").addEventListener("click", () => openAdminConsole("collectibles"));
    $("shellCabinetsBtn").addEventListener("click", () => switchShellMode("cabinets"));
    $("tabOpsBtn").addEventListener("click", () => openAdminConsole("ops"));
    $("tabLogsBtn").addEventListener("click", () => {
      switchMainTab("logs");
      switchSubTab("logs", "err");
      loadErrorLog(true);
      loadErrorBadge();
    });
    $("opsSystemStatusReloadBtn")?.addEventListener("click", loadOpsSystemStatus);
    $("opsAutoBackupSaveBtn")?.addEventListener("click", saveOpsBackupSettings);
    $("opsRestoreDbBtn")?.addEventListener("click", restoreOpsDatabase);
    $("opsExportFullBtn")?.addEventListener("click", downloadOpsFullBackup);
    $("opsRestoreBundleBtn")?.addEventListener("click", restoreOpsBundle);
    $("opsExportDbBtn")?.addEventListener("click", downloadOpsDbBackup);
    $("opsExportOwnedBtn")?.addEventListener("click", downloadOpsOwnedCsv);
    $("opsExportMasterBtn")?.addEventListener("click", downloadOpsMasterCsv);
    $("appLogoutBtn").addEventListener("click", logoutAppSession);
    $("appPrefsResetBtn")?.addEventListener("click", async () => {
      clearCurrentRoleDefaultPreferences();
      renderOpsExceptionPresetOptions();
      setStatus("opsExceptionStatus", "ok", t("ops.exception.status.reset_defaults"));
      if ($("opsExceptionPanel")?.classList.contains("active")) {
        await loadOpsExceptionCounts({ silent: true });
        await loadOpsExceptionItems({ silent: true });
      }
    });
    $("operatorLookupBtn").addEventListener("click", loadOperatorLookupResults);
    $("operatorLookupResetBtn").addEventListener("click", async () => {
      operatorLookupRequestSeq += 1;
      $("operatorLookupQuery").value = "";
      $("operatorLookupSignatureMode").value = "ANY";
      $("operatorLookupSortMode").value = "CREATED_DESC";
      setStatus("operatorLookupStatus", "", "");
      await loadOperatorHomeFeed({ kind: operatorFeedKindFromSortMode("CREATED_DESC"), page: 1 });
    });
    $("operatorFeedPager").addEventListener("click", (e) => {
      const button = e.target.closest("[data-operator-feed-page]");
      if (!button || button.disabled) return;
      const nextPage = Number(button.getAttribute("data-operator-feed-page") || 0);
      if (nextPage > 0 && nextPage !== operatorFeedPage) {
        loadOperatorHomeFeed({ kind: operatorFeedKind, page: nextPage });
      }
    });
    $("operatorFeedPagerBottom").addEventListener("click", (e) => {
      const button = e.target.closest("[data-operator-feed-page]");
      if (!button || button.disabled) return;
      const nextPage = Number(button.getAttribute("data-operator-feed-page") || 0);
      if (nextPage > 0 && nextPage !== operatorFeedPage) {
        loadOperatorHomeFeed({ kind: operatorFeedKind, page: nextPage });
      }
    });
    $("operatorLookupQuery").addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      e.preventDefault();
      loadOperatorLookupResults();
    });
    $("operatorLookupSortMode").addEventListener("change", () => {
      if (normalizeOpsLookupQuery($("operatorLookupQuery").value)) return;
      loadOperatorHomeFeed({ kind: operatorFeedKindFromSortMode($("operatorLookupSortMode").value), page: 1 });
    });
    $("operatorHelperSummary").addEventListener("click", handleOperatorLookupAction);
    $("opsLibraryContextBody").addEventListener("click", handleOperatorLookupAction);
    $("adminSearchContextBody").addEventListener("click", handleMediaSearchContextAction);
    $("operatorLookupResults").addEventListener("click", handleOperatorLookupAction);
    $("operatorRecentSections").addEventListener("click", handleOperatorLookupAction);
    $("sharedCameraList").addEventListener("click", (e) => {
      const button = e.target.closest("[data-shared-camera-id]");
      if (!button) return;
      sharedCameraSelectedId = Number(button.getAttribute("data-shared-camera-id") || 0) || null;
      renderSharedCameraPage();
    });
    /* homeOpenManageBtn & homeOpenRegisterBtn removed */
    $("mediaSearchModeBtn").addEventListener("click", () => switchMediaMode("search"));
    $("mediaManageModeBtn").addEventListener("click", () => switchMediaMode("manage"));
    $("mediaRegisterModeBtn").addEventListener("click", () => switchMediaMode("register"));
    $("mediaSourceModeBtn").addEventListener("click", () => switchMediaMode("source"));
    $("goodsSearchModeBtn").addEventListener("click", () => switchGoodsMode("search"));
    $("goodsManageModeBtn").addEventListener("click", () => switchGoodsMode("manage"));
    $("goodsRegisterModeBtn").addEventListener("click", () => switchGoodsMode("register"));
    $("goodsSearchRunBtn").addEventListener("click", () => loadGoodsSearchResults());
    $("goodsSearchResetBtn").addEventListener("click", async () => {
      $("goodsSearchQuery").value = "";
      $("goodsSearchCategory").value = "";
      $("goodsSearchStatusFilter").value = "";
      $("goodsSearchDomainCode").value = "";
      $("goodsSearchAlbumMasterId").value = "";
      $("goodsSearchStorageSlotId").value = "";
      $("goodsSearchLinkedState").value = "ANY";
      $("goodsSearchCollectibleRelationState").value = "ANY";
      $("goodsSearchCollectibleRelationType").value = "";
      setStatus("goodsSearchStatus", "", "");
      await loadGoodsSearchResults({ silent: true });
    });
    ["goodsSearchQuery", "goodsSearchAlbumMasterId"].forEach((id) => {
      $(id).addEventListener("keydown", (e) => {
        if (e.key !== "Enter") return;
        e.preventDefault();
        loadGoodsSearchResults();
      });
    });
    $("goodsSearchResults").addEventListener("click", (e) => {
      const button = e.target.closest("[data-goods-open]");
      if (!button) return;
      openGoodsItemForManage(button.getAttribute("data-goods-open"));
    });
    $("goodsManageSaveBtn").addEventListener("click", saveGoodsManageItem);
    $("goodsManageDeleteBtn").addEventListener("click", deleteGoodsManageItem);
    $("goodsManageAlbumMasterSearchBtn").addEventListener("click", searchGoodsAlbumMasterTargets);
    $("goodsManageAlbumMasterQuery").addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      e.preventDefault();
      searchGoodsAlbumMasterTargets();
    });
    $("goodsManageCollectibleSearchBtn").addEventListener("click", searchGoodsCollectibleTargets);
    $("goodsManageCollectibleQuery").addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      e.preventDefault();
      searchGoodsCollectibleTargets();
    });
    $("goodsManageAlbumMasterResults").addEventListener("click", (e) => {
      const button = e.target.closest("[data-goods-add-album-master]");
      if (!button) return;
      addUniqueGoodsMappingValue("album_master", button.getAttribute("data-goods-add-album-master"), {
        album_master_id: button.getAttribute("data-goods-add-album-master"),
        title: button.getAttribute("data-goods-add-album-master-title"),
        artist_or_brand: button.getAttribute("data-goods-add-album-master-artist"),
      });
      setHtmlIfPresent("goodsManageAlbumMasterResults", "");
      $("goodsManageAlbumMasterQuery").value = "";
      setStatus("goodsManageMappingStatus", "", "");
    });
    $("goodsManageCollectibleResults").addEventListener("click", (e) => {
      const button = e.target.closest("[data-goods-add-collectible]");
      if (!button) return;
      const linkedGoodsItemId = Number(button.getAttribute("data-goods-add-collectible") || 0);
      if (linkedGoodsItemId <= 0) return;
      const relationType = String($("goodsManageRelationType").value || "SERIES").trim().toUpperCase() || "SERIES";
      const note = String($("goodsManageRelationNote").value || "").trim();
      const existing = goodsManageCollectibleRelations.some((row) =>
        Number(row.linked_goods_item_id || 0) === linkedGoodsItemId && String(row.relation_type || "").trim().toUpperCase() === relationType
      );
      if (!existing) {
        goodsManageCollectibleRelations.push({
          relation_type: relationType,
          direction: "OUTGOING",
          linked_goods_item_id: linkedGoodsItemId,
          linked_goods_name: String(button.getAttribute("data-goods-add-collectible-name") || "").trim(),
          linked_category: String(button.getAttribute("data-goods-add-collectible-category") || "").trim().toUpperCase() || null,
          note: note || null,
          display_order: goodsManageCollectibleRelations.length,
        });
      }
      renderGoodsCollectibleRelationList();
      setHtmlIfPresent("goodsManageCollectibleResults", "");
      $("goodsManageCollectibleQuery").value = "";
      $("goodsManageRelationNote").value = "";
      setStatus("goodsManageRelationStatus", "", "");
    });
    $("goodsManageContent").addEventListener("click", (e) => {
      const removeBtn = e.target.closest("[data-goods-remove-map]");
      if (!removeBtn) return;
      const mapType = String(removeBtn.getAttribute("data-goods-remove-map") || "").trim();
      const index = Number(removeBtn.getAttribute("data-goods-map-index") || -1);
      if (index < 0) return;
      if (mapType === "album_master") goodsManageAlbumMasterMappings.splice(index, 1);
      if (mapType === "artist") goodsManageArtistMappings.splice(index, 1);
      if (mapType === "label") goodsManageLabelMappings.splice(index, 1);
      if (mapType === "collectible") goodsManageCollectibleRelations.splice(index, 1);
      renderGoodsManageMappings();
      setStatus("goodsManageMappingStatus", "", "");
      setStatus("goodsManageRelationStatus", "", "");
    });
    $("goodsManageSaveMappingsBtn").addEventListener("click", saveGoodsManageMappings);
    $("goodsManageSaveRelationsBtn").addEventListener("click", saveGoodsManageRelations);
    // Register image upload
    var _regImageUrls = [];
    var _regFileInput = document.getElementById("goodsRegisterImageFile");
    if (_regFileInput) {
      _regFileInput.addEventListener("change", async function() {
        if (!this.files.length) return;
        try {
          var uploaded = await uploadUiImageFiles(this.files);
          uploaded.forEach(function(url) { if (url) { _regImageUrls.push(url); addRegImagePreview(url); } });
          var hi = document.getElementById("goodsRegisterImageUrls");
          if (hi) hi.value = _regImageUrls.join("\n");
        } catch(e) { console.error("Image upload failed", e); } finally { this.value = ""; }
      });
    }
    if ($("goodsRegisterImagePaste")) {
      $("goodsRegisterImagePaste").addEventListener("paste", onGoodsRegisterImagePaste);
      $("goodsRegisterImagePaste").addEventListener("change", () => {
        const urls = extractUrlCandidates($("goodsRegisterImagePaste").value);
        if (!urls.length) return;
        urls.forEach(url => { _regImageUrls.push(url); addRegImagePreview(url); });
        $("goodsRegisterImageUrls").value = _regImageUrls.join("\n");
        $("goodsRegisterImagePaste").value = "";
      });
    }
    if ($("goodsRegisterImageUrlInput")) {
      $("goodsRegisterImageUrlInput").addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); applyGoodsRegisterImageUrl(); } });
    }
    $("goodsRegisterSaveBtn").addEventListener("click", createGoodsRegisterItem);
    $("registerCollectTabBtn").addEventListener("click", () => switchSubTab("register", "collect"));
    $("registerPurchaseTabBtn").addEventListener("click", async () => {
      switchSubTab("register", "purchase");
      await loadPurchaseImportQueue({ silent: true });
    });
    $("registerBatchTabBtn").addEventListener("click", () => switchSubTab("register", "batch"));
    $("registerMasterTabBtn").addEventListener("click", () => switchSubTab("register", "master"));
    $("registerTrackTabBtn").addEventListener("click", () => switchSubTab("register", "track"));
    $("purchaseImportPreviewBtn").addEventListener("click", previewPurchaseImport);
    $("purchaseImportSaveBtn").addEventListener("click", savePurchaseImportQueue);
    $("purchaseImportResetBtn").addEventListener("click", resetPurchaseImportForm);
    $("purchaseImportFile").addEventListener("change", handlePurchaseImportFileChange);
    $("purchaseImportQueueLoadBtn").addEventListener("click", () => loadPurchaseImportQueue());
    $("purchaseImportQueueFetchAllCandidatesBtn").addEventListener("click", () => loadAllPurchaseImportCandidates());
    $("purchaseImportQueueBody").addEventListener("click", async (e) => {
      const enrichBtn = e.target.closest("[data-purchase-import-enrich]");
      if (enrichBtn) {
        await enrichPurchaseImportFromItemPage(enrichBtn.getAttribute("data-purchase-import-enrich"));
        return;
      }
      const candidatesBtn = e.target.closest("[data-purchase-import-candidates]");
      if (candidatesBtn) {
        await loadPurchaseImportCandidates(candidatesBtn.getAttribute("data-purchase-import-candidates"));
        return;
      }
      const applyArtistBtn = e.target.closest("[data-purchase-import-apply-artist]");
      if (applyArtistBtn) {
        applyPurchaseImportCandidateArtist(applyArtistBtn.getAttribute("data-purchase-import-apply-artist"));
        return;
      }
      const sourceQueryBtn = e.target.closest("[data-purchase-import-candidates-source]");
      if (sourceQueryBtn) {
        const parts = String(sourceQueryBtn.getAttribute("data-purchase-import-candidates-source") || "").split(":");
        await loadPurchaseImportCandidates(parts[0], { source: parts[1] });
        return;
      }
      const createDirectBtn = e.target.closest("[data-purchase-import-create-direct]");
      if (createDirectBtn) {
        const parts = String(createDirectBtn.getAttribute("data-purchase-import-create-direct") || "").split(":");
        await createOwnedItemFromPurchaseQueueCandidate(parts[0], Number(parts[1]));
        return;
      }
      const createBtn = e.target.closest("[data-purchase-import-create]");
      if (createBtn) {
        await createOwnedItemFromPurchaseQueue(createBtn.getAttribute("data-purchase-import-create"));
        return;
      }
      const ignoreBtn = e.target.closest("[data-purchase-import-ignore]");
      if (ignoreBtn) {
        await ignorePurchaseImportRow(ignoreBtn.getAttribute("data-purchase-import-ignore"));
      }
    });
    $("purchaseImportQueueBody").addEventListener("input", (e) => {
      const artistInput = e.target.closest("[data-purchase-import-artist]");
      if (artistInput) {
        updatePurchaseImportCandidateSearchText(artistInput.getAttribute("data-purchase-import-artist"), "artist", artistInput.value);
        return;
      }
      const itemInput = e.target.closest("[data-purchase-import-item]");
      if (itemInput) {
        updatePurchaseImportCandidateSearchText(itemInput.getAttribute("data-purchase-import-item"), "item", itemInput.value);
        return;
      }
      const queryInput = e.target.closest("[data-purchase-import-query]");
      if (queryInput) {
        updatePurchaseImportCandidateSearchText(queryInput.getAttribute("data-purchase-import-query"), "query", queryInput.value);
      }
    });
    $("purchaseImportQueueBody").addEventListener("keydown", async (e) => {
      if (e.key !== "Enter") return;
      const artistInput = e.target.closest("[data-purchase-import-artist]");
      const itemInput = e.target.closest("[data-purchase-import-item]");
      const queryInput = e.target.closest("[data-purchase-import-query]");
      if (!artistInput && !itemInput && !queryInput) return;
      e.preventDefault();
      const queueId = String(
        artistInput?.getAttribute("data-purchase-import-artist")
        || itemInput?.getAttribute("data-purchase-import-item")
        || queryInput?.getAttribute("data-purchase-import-query")
        || ""
      ).trim();
      if (!queueId) return;
      await loadPurchaseImportCandidates(queueId);
    });
    $("opsCabinetTabBtn").addEventListener("click", () => switchSubTab("ops", "cabinet"));
    $("opsCameraTabBtn").addEventListener("click", async () => {
      switchSubTab("ops", "camera");
      await loadOpsCameras({ silent: true });
    });
    $("opsProviderTabBtn")?.addEventListener("click", async () => {
      switchSubTab("ops", "providers");
      await loadOpsProviderSettings();
    });
    $("opsExportTabBtn").addEventListener("click", async () => {
      switchSubTab("ops", "export");
      await loadOpsBackupSettings();
    });
    $("opsSlotTabBtn").addEventListener("click", () => switchSubTab("ops", "slot"));
    $("opsExceptionTabBtn").addEventListener("click", async () => {
      switchSubTab("ops", "exception");
      applyDefaultOpsExceptionPreset();
      await loadOpsExceptionCounts({ silent: true });
      await loadOpsExceptionItems();
    });
    $("opsAccountTabBtn").addEventListener("click", async () => {
      switchSubTab("ops", "account");
      await loadOpsAuthAccounts();
    });
    $("opsPermissionsTabBtn").addEventListener("click", async () => {
      switchSubTab("ops", "permissions");
      await loadPermissionData();
    });
    $("acctTabUsersBtn").addEventListener("click", () => {
      $("acctTabUsersBtn").classList.add("active");
      $("acctTabGroupsBtn").classList.remove("active");
      $("acctUsersPanel").style.display = "";
      $("acctGroupsPanel").style.display = "none";
    });
    $("acctTabGroupsBtn").addEventListener("click", async () => {
      $("acctTabUsersBtn").classList.remove("active");
      $("acctTabGroupsBtn").classList.add("active");
      $("acctUsersPanel").style.display = "none";
      $("acctGroupsPanel").style.display = "";
      await loadPermissionData();
    });
    $("opsActivityTabBtn").addEventListener("click", () => switchSubTab("ops", "activity"));

    // ── 이력 & 로그 subtab buttons ─────────────────────────────────────
    $("logErrTabBtn").addEventListener("click", () => { switchSubTab("logs", "err"); loadErrorLog(true); loadErrorBadge(); });
    $("logAuditTabBtn").addEventListener("click", () => { switchSubTab("logs", "audit"); loadActivityAudit(true); });
    $("logPerfTabBtn").addEventListener("click", () => { switchSubTab("logs", "perf"); loadPerfLog(); });
    $("logLocTabBtn").addEventListener("click", () => { switchSubTab("logs", "loc"); loadActivityLocation(true); });
    $("logSrvTabBtn").addEventListener("click", () => { switchSubTab("logs", "srv"); });

    // stderr/stdout toggle
    $("logSrvStderr").addEventListener("click", () => {
      $("actLogStream").value = "stderr";
      $("logSrvStderr").classList.add("active");
      $("logSrvStdout").classList.remove("active");
    });
    $("logSrvStdout").addEventListener("click", () => {
      $("actLogStream").value = "stdout";
      $("logSrvStdout").classList.add("active");
      $("logSrvStderr").classList.remove("active");
    });

    // ── Error Log ──────────────────────────────────────────────────────
    let _actErrOffset = 0, _actErrLimit = 50;

    let _errAutoRefreshTimer = null;

    $("actErrLoadBtn").addEventListener("click", () => loadErrorLog(true));
    $("actErrAckBtn").addEventListener("click", async () => {
      const res = await fetchWithRetry("/admin/error-log/acknowledge", { method: "POST" });
      if (res.ok) { await loadErrorLog(true); await loadErrorBadge(); }
    });
    $("actErrTbody").addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-ack-id]");
      if (!btn) return;
      const id = btn.getAttribute("data-ack-id");
      const res = await fetchWithRetry(`/admin/error-log/${id}/acknowledge`, { method: "PATCH" });
      if (res.ok) { await loadErrorLog(false); await loadErrorBadge(); }
    });
    $("actErrPrevBtn").addEventListener("click", () => { _actErrOffset = Math.max(0, _actErrOffset - _actErrLimit); loadErrorLog(false); });
    $("actErrNextBtn").addEventListener("click", () => { _actErrOffset += _actErrLimit; loadErrorLog(false); });
    $("logErrAutoRefresh").addEventListener("change", function() {
      clearInterval(_errAutoRefreshTimer);
      if (this.checked) { _errAutoRefreshTimer = setInterval(() => loadErrorLog(false), 30000); }
    });

    // ── Perf Log ───────────────────────────────────────────────────────

    $("actPerfLoadBtn").addEventListener("click", () => loadPerfLog());
    $("actPerfTbody").addEventListener("click", async (e) => {
      const row = e.target.closest("tr[data-perf-name]");
      if (!row) return;
      const name = row.getAttribute("data-perf-name");
      const kind = row.getAttribute("data-perf-kind") || "";
      let url = `/admin/perf-log/detail?name=${encodeURIComponent(name)}&limit=50`;
      if (kind) url += `&kind=${encodeURIComponent(kind)}`;
      const res = await fetchWithRetry(url);
      if (!res.ok) return;
      const data = await res.json();
      $("logPerfDrillTitle").textContent = `${name} — 최근 ${data.items.length}건`;
      const fmtMs = (ms) => ms >= 1000 ? `${(ms/1000).toFixed(1)}s` : `${ms}ms`;
      $("logPerfDrillTbody").innerHTML = data.items.length
        ? data.items.map(r => `<tr>
            <td style="font-size:0.74rem;white-space:nowrap">${(r.created_at||"").slice(0,16).replace("T"," ")}</td>
            <td style="font-size:0.74rem;font-weight:${r.is_slow?700:400};color:${r.is_slow?"#dc2626":"inherit"}">${fmtMs(r.duration_ms)}</td>
            <td>${r.is_slow ? '<span style="background:#fee2e2;color:#b91c1c;font-size:0.7rem;padding:1px 5px;border-radius:3px">느림</span>' : '<span style="color:var(--text-muted);font-size:0.7rem">—</span>'}</td>
          </tr>`).join("")
        : '<tr><td colspan="3" style="text-align:center;color:var(--text-muted)">없음</td></tr>';
      $("logPerfDrilldown").style.display = "";
    });

    // ── Activity Log ──────────────────────────────────────────────
    $("actAuditLoadBtn").addEventListener("click", () => loadActivityAudit(true));
    $("actAuditPrevBtn").addEventListener("click", () => { _actAuditOffset = Math.max(0, _actAuditOffset - _actAuditLimit); loadActivityAudit(false); });
    $("actAuditNextBtn").addEventListener("click", () => { _actAuditOffset += _actAuditLimit; loadActivityAudit(false); });
    $("actLocLoadBtn").addEventListener("click", () => loadActivityLocation(true));
    $("actLocPrevBtn").addEventListener("click", () => { _actLocOffset = Math.max(0, _actLocOffset - _actLocLimit); loadActivityLocation(false); });
    $("actLocNextBtn").addEventListener("click", () => { _actLocOffset += _actLocLimit; loadActivityLocation(false); });
    $("actLogLoadBtn").addEventListener("click", loadServerLog);
    $("actLogRefreshBtn").addEventListener("click", loadServerLog);
    $("logSrvAutoRefresh").addEventListener("change", function() {
      clearInterval(_srvAutoRefreshTimer);
      if (this.checked) { _srvAutoRefreshTimer = setInterval(loadServerLog, 15000); }
    });

    $("opsMetaSyncTabBtn").addEventListener("click", () => switchSubTab("ops", "metasync"));
    $("opsCabinetSizeGroup").addEventListener("change", () => maybeAutofillOpsCabinetSlotCapacity(false));
    $("opsCabinetSlotCapacityMm").addEventListener("input", renderOpsCabinetSlotCapacityHint);
    $("opsCabinetSaveBtn").addEventListener("click", saveOpsStorageCabinet);
    $("opsCabinetDeleteBtn").addEventListener("click", deleteOpsStorageCabinet);
    $("opsCabinetResetBtn").addEventListener("click", resetOpsCabinetForm);
    $("opsCameraSaveBtn").addEventListener("click", saveOpsCamera);
    $("opsCameraDeleteBtn").addEventListener("click", deleteOpsCamera);
    $("opsCameraResetBtn").addEventListener("click", resetOpsCameraForm);
    $("opsCameraReloadBtn").addEventListener("click", () => loadOpsCameras());
    $("opsCameraDiscoverBtn").addEventListener("click", discoverOpsCameras);
    $("opsCameraTestBtn").addEventListener("click", testOpsCameraConnection);
    $("opsSlotSaveBtn").addEventListener("click", saveOpsStorageSlot);
    $("opsSlotResetBtn").addEventListener("click", resetOpsSlotForm);
    $("opsSlotReloadBtn").addEventListener("click", loadStorageSlots);
    $("opsCameraDiscoverTableBody").addEventListener("click", (e) => {
      const button = e.target.closest("[data-ops-camera-discover-use]");
      if (!button) return;
      const index = Number(button.getAttribute("data-ops-camera-discover-use") || -1);
      if (index < 0) return;
      const item = opsCameraDiscoverItems[index] || null;
      if (item) applyDiscoveredCamera(item);
    });
    $("opsCameraTableBody").addEventListener("click", (e) => {
      const row = e.target.closest("tr[data-camera-id]");
      if (!row) return;
      const cameraId = Number(row.getAttribute("data-camera-id") || 0);
      const item = opsCameraItems.find((entry) => Number(entry.id) === cameraId) || null;
      if (item) fillOpsCameraForm(item);
    });
    $("opsAuthSaveBtn").addEventListener("click", saveOpsAuthAccount);
    $("opsAuthDeleteBtn").addEventListener("click", deleteOpsAuthAccount);
    $("opsAuthResetBtn").addEventListener("click", resetOpsAuthForm);
    $("opsAuthReloadBtn").addEventListener("click", loadOpsAuthAccounts);
    $("opsProviderDiscogsSaveBtn")?.addEventListener("click", () => saveOpsProviderSettingsFields([
      "discogs_token",
      "discogs_user_agent",
    ]));
    $("opsProviderAladinSaveBtn")?.addEventListener("click", () => saveOpsProviderSettingsFields([
      "aladin_ttb_key",
      "aladin_base_url",
    ]));
    $("opsProviderManiadbSaveBtn")?.addEventListener("click", () => saveOpsProviderSettingsFields([
      "maniadb_base_url",
    ]));
    $("opsProviderDeeplSaveBtn")?.addEventListener("click", () => saveOpsProviderSettingsFields([
      "deepl_auth_key",
      "deepl_base_url",
    ]));
    $("opsProviderDeeplTestBtn")?.addEventListener("click", testOpsProviderDeeplConnection);
    $("opsProviderResetBtn")?.addEventListener("click", loadOpsProviderSettings);
    $("opsExceptionLoadBtn").addEventListener("click", () => loadOpsExceptionItems());
    $("opsExSearchResetBtn")?.addEventListener("click", () => {
      ["opsExArtist","opsExTitle","opsExBarcode","opsExCatalogNo","opsExReleaseYear"].forEach(id => {
        const el = $(id); if (el) el.value = "";
      });
      $("opsExPackagingList")?.querySelectorAll("input").forEach(cb => { cb.checked = false; });
      $("opsExPackageContentsList")?.querySelectorAll("input").forEach(cb => { cb.checked = false; });
      ["opsExSigDirect","opsExSigPurchase","opsExNewProduct","opsExPromo","opsExLimitEd"].forEach(id => {
        const el = $(id); if (el) el.checked = false;
      });
    });
    ["opsExArtist","opsExTitle","opsExBarcode","opsExCatalogNo","opsExReleaseYear"].forEach(id => {
      $(id)?.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { e.preventDefault(); loadOpsExceptionItems(); }
      });
    });
    $("opsExceptionCountBtn").addEventListener("click", async () => {
      await loadOpsExceptionCounts();
      await loadOpsExceptionItems({ silent: true });
    });
    $("opsExceptionPresetSaveBtn").addEventListener("click", () => {
      const name = String($("opsExceptionPresetName").value || "").trim();
      if (!name) {
        setStatus("opsExceptionStatus", "err", t("ops.exception.status.preset_name_required"));
        return;
      }
      const payload = currentOpsExceptionPresetPayload();
      const rows = loadOpsExceptionPresets();
      const normalized = name.toLowerCase();
      const nextRows = rows.filter((row) => String(row?.name || "").trim().toLowerCase() !== normalized);
      nextRows.unshift({ name, ...payload });
      saveOpsExceptionPresets(nextRows.slice(0, 20));
      renderOpsExceptionPresetOptions();
      const savedIndex = loadOpsExceptionPresets().findIndex((row) => String(row?.name || "").trim().toLowerCase() === normalized);
      $("opsExceptionPresetSelect").value = savedIndex >= 0 ? String(savedIndex) : "";
      setStatus("opsExceptionStatus", "ok", t("ops.exception.status.preset_saved", { name }));
    });
    $("opsExceptionPresetApplyBtn").addEventListener("click", async () => {
      const value = String($("opsExceptionPresetSelect").value || "");
      if (!applyOpsExceptionPresetByIndex(value)) {
        setStatus("opsExceptionStatus", "err", t("ops.exception.status.preset_select_required"));
        return;
      }
      opsExceptionSelectedIds = new Set();
      renderOpsExceptionSummary();
      syncOpsExceptionSelectionControls();
      await loadOpsExceptionItems();
      const rows = loadOpsExceptionPresets();
      const preset = rows[Number(value)];
      setStatus(
        "opsExceptionStatus",
        "ok",
        t("ops.exception.status.preset_applied", { name: String(preset?.name || t("ops.exception.field.preset.saved_name")) })
      );
    });
    $("opsExceptionPresetDefaultBtn").addEventListener("click", () => {
      const value = String($("opsExceptionPresetSelect").value || "");
      const rows = loadOpsExceptionPresets();
      const preset = rows[Number(value)];
      if (!preset) {
        setStatus("opsExceptionStatus", "err", t("ops.exception.status.preset_default_required"));
        return;
      }
      const name = String(preset.name || "").trim();
      saveDefaultOpsExceptionPresetName(name);
      renderOpsExceptionPresetOptions();
      $("opsExceptionPresetSelect").value = value;
      setStatus("opsExceptionStatus", "ok", t("ops.exception.status.preset_default_saved", { name }));
    });
    $("opsExceptionPresetDeleteBtn").addEventListener("click", () => {
      const value = String($("opsExceptionPresetSelect").value || "");
      const idx = Number(value);
      const rows = loadOpsExceptionPresets();
      if (!Number.isInteger(idx) || idx < 0 || !rows[idx]) {
        setStatus("opsExceptionStatus", "err", t("ops.exception.status.preset_delete_required"));
        return;
      }
      const name = String(rows[idx]?.name || t("ops.exception.field.preset.saved_name"));
      const defaultName = loadDefaultOpsExceptionPresetName().toLowerCase();
      rows.splice(idx, 1);
      saveOpsExceptionPresets(rows);
      if (defaultName && name.trim().toLowerCase() === defaultName) {
        saveDefaultOpsExceptionPresetName("");
      }
      renderOpsExceptionPresetOptions();
      $("opsExceptionPresetSelect").value = "";
      setStatus("opsExceptionStatus", "ok", t("ops.exception.status.preset_deleted", { name }));
    });
    $("opsExceptionPresetSelect").addEventListener("change", () => {
      const idx = String($("opsExceptionPresetSelect").value || "");
      if (!idx) return;
      applyOpsExceptionPresetByIndex(idx);
    });
    $("opsExceptionPresetChips").addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-ops-exception-preset-chip]");
      if (!btn) return;
      const idx = String(btn.getAttribute("data-ops-exception-preset-chip") || "");
      if (!applyOpsExceptionPresetByIndex(idx)) return;
      $("opsExceptionPresetSelect").value = idx;
      opsExceptionSelectedIds = new Set();
      renderOpsExceptionSummary();
      syncOpsExceptionSelectionControls();
      await loadOpsExceptionItems();
      const rows = loadOpsExceptionPresets();
      const preset = rows[Number(idx)];
      setStatus("opsExceptionStatus", "ok", t("ops.exception.status.preset_applied", { name: String(preset?.name || t("ops.exception.field.preset.saved_name")) }));
    });
    $("opsExceptionType").addEventListener("change", () => {
      renderOpsExceptionContextPanel(null, "");
      opsExceptionSelectedIds = new Set();
      renderOpsExceptionSummary();
      syncOpsExceptionSelectionControls();
      loadOpsExceptionItems({ silent: true });
    });
    $("opsExceptionSummary").addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-ops-exception-summary]");
      if (!btn) return;
      $("opsExceptionType").value = btn.getAttribute("data-ops-exception-summary") || "UNSLOTTED";
      opsExceptionSelectedIds = new Set();
      renderOpsExceptionSummary();
      await loadOpsExceptionItems();
    });
    $("opsExceptionList").addEventListener("click", async (e) => {
      const selectInput = e.target.closest("[data-ops-exception-select]");
      if (selectInput) {
        const ownedItemId = Number(selectInput.getAttribute("data-ops-exception-select") || 0);
        if (ownedItemId > 0) {
          if (opsExceptionSelectedIds.has(ownedItemId)) opsExceptionSelectedIds.delete(ownedItemId);
          else opsExceptionSelectedIds.add(ownedItemId);
          renderOpsExceptionList();
        }
        return;
      }
      const openBtn = e.target.closest("[data-ops-exception-open]");
      if (openBtn) {
        const ownedItemId = Number(openBtn.getAttribute("data-ops-exception-open") || 0);
        const row = (Array.isArray(opsExceptionItems) ? opsExceptionItems : []).find((item) => Number(item?.id || 0) === ownedItemId);
        const masterId = Number(row?.linked_album_master_id || row?.album_master_id || 0);
        if (ownedItemId > 0) await openMediaSearchDetailManage(masterId, ownedItemId);
        return;
      }
      const alignBtn = e.target.closest("[data-ops-exception-align-size]");
      if (alignBtn) {
        const ownedItemId = Number(alignBtn.getAttribute("data-ops-exception-align-size") || 0);
        if (ownedItemId > 0) await alignPreferredStorageFromException(ownedItemId);
        return;
      }
      const sourceBtn = e.target.closest("[data-ops-exception-source]");
      if (sourceBtn) {
        const ownedItemId = Number(sourceBtn.getAttribute("data-ops-exception-source") || 0);
        if (ownedItemId > 0) await openSourceWorkbenchFromException(ownedItemId);
        return;
      }
      const masterBtn = e.target.closest("[data-ops-exception-master]");
      if (masterBtn) {
        const ownedItemId = Number(masterBtn.getAttribute("data-ops-exception-master") || 0);
        const row = (Array.isArray(opsExceptionItems) ? opsExceptionItems : []).find((item) => Number(item?.id || 0) === ownedItemId);
        if (row) loadMasterOwnedRowsFromItems([row], t("ops.exception.status.master_loaded", { name: resolveOwnedAlbumName(row) }));
      }
    });
    $("opsExceptionSelectAllBtn").addEventListener("click", () => {
      opsExceptionSelectedIds = new Set((Array.isArray(opsExceptionItems) ? opsExceptionItems : []).map((row) => Number(row?.id || 0)).filter((id) => id > 0));
      renderOpsExceptionList();
    });
    $("opsExceptionBulkReviewBtn").addEventListener("click", async () => {
      const selected = Array.from(opsExceptionSelectedIds);
      if (!selected.length) return;
      const btn = $("opsExceptionBulkReviewBtn");
      const statusEl = $("opsExceptionStatus");
      btn.disabled = true;
      let ok = 0, fail = 0;
      for (const masterId of selected) {
        statusEl.textContent = `소스 자동수집 중... (${ok + fail + 1}/${selected.length}) 성공: ${ok} 실패: ${fail}`;
        try {
          const res = await fetchWithRetry(`/album-masters/${masterId}/review/auto`, { method: "POST" });
          if (res.ok) { ok++; opsExceptionSelectedIds.delete(masterId); }
          else fail++;
        } catch (_) { fail++; }
      }
      statusEl.textContent = `완료 — 성공: ${ok}건 / 실패: ${fail}건`;
      btn.disabled = false;
      await loadOpsExceptionItems({ silent: true });
    });
    $("opsExceptionClearBtn").addEventListener("click", () => {
      opsExceptionSelectedIds = new Set();
      renderOpsExceptionList();
    });
    $("opsExceptionBulkSourceBtn").addEventListener("click", bulkSendExceptionsToSourceWorkbench);
    $("opsExceptionBulkAlignBtn").addEventListener("click", bulkAlignPreferredStorageFromExceptions);
    $("opsExceptionBulkMasterBtn").addEventListener("click", bulkSendExceptionsToMasterWorkbench);
    $("metaSyncStatusBtn").addEventListener("click", loadMetadataSyncStatus);
    $("metaSyncRunBtn").addEventListener("click", runMetadataSyncNow);
    $("aladinDiscogsBackfillStatusBtn").addEventListener("click", loadAladinDiscogsBackfillStatus);
    $("aladinDiscogsBackfillRunBtn").addEventListener("click", runAladinDiscogsBackfill);
    $("spotifyBatchStatusBtn").addEventListener("click", loadSpotifyBatchStatus);
    $("spotifyBatchRunBtn").addEventListener("click", runSpotifyBatch);
    $("reviewBatchStatusBtn")?.addEventListener("click", async () => {
      const status = $("reviewBatchStatus");
      status.textContent = "상태 조회 중...";
      try {
        const res = await fetchWithRetry("/album-masters/review/batch", { method: "POST" });
        const data = await res.json();
        $("reviewBatchRemainingCount").textContent = `미수집 약 ${data.remaining}건`;
        status.textContent = `처리: ${data.processed}건 / 성공: ${data.succeeded}건 / 실패: ${data.failed}건 / 잔여: ${data.remaining}건`;
      } catch (e) {
        status.textContent = String(e);
      }
    });
    $("reviewBatchPreviewBtn")?.addEventListener("click", async () => {
      const btn = $("reviewBatchPreviewBtn");
      const status = $("reviewBatchStatus");
      const previewArea = $("reviewBatchPreviewResults");
      btn.disabled = true;
      status.textContent = "샘플 5건 번역 중... (DeepL)";
      previewArea.style.display = "none";
      previewArea.innerHTML = "";
      try {
        const res = await fetchWithRetry("/album-masters/review/batch-preview?limit=5", { method: "POST" });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "preview failed");
        const rows = Array.isArray(data.results) ? data.results : [];
        if (!rows.length) { status.textContent = "미수집 마스터가 없습니다."; }
        else {
          status.textContent = `샘플 ${rows.length}건 번역 완료 — 아래에서 확인 후 일괄 실행하세요.`;
          previewArea.innerHTML = rows.map((r) => {
            const title = escapeHtml(`${r.artist} - ${r.title} (master_id=${r.master_id})`);
            if (r.error) return `<div style="margin-bottom:12px;padding:8px;border:1px solid var(--err,#dc3545);border-radius:6px;"><strong>${title}</strong><div class="mini" style="color:var(--err)">오류: ${escapeHtml(r.error)}</div></div>`;
            const translated = escapeHtml(r.translated_text || "");
            const url = r.review_url ? `<a href="${escapeHtml(r.review_url)}" target="_blank" rel="noopener" style="font-size:0.7rem;">원문↗</a>` : "";
            return `<div style="margin-bottom:12px;padding:8px;border:1px solid var(--line);border-radius:6px;">
              <div style="font-size:0.75rem;font-weight:600;margin-bottom:4px;">${title} ${url}</div>
              <div style="font-size:0.8rem;line-height:1.5;">${translated}</div>
            </div>`;
          }).join("");
          previewArea.style.display = "";
        }
      } catch (e) {
        status.textContent = `오류: ${String(e)}`;
      }
      btn.disabled = false;
    });
    $("reviewBatchRunBtn")?.addEventListener("click", async () => {
      const btn = $("reviewBatchRunBtn");
      const status = $("reviewBatchStatus");
      btn.disabled = true;
      status.textContent = "자동수집 실행 중... (최대 수 분 소요)";
      try {
        const res = await fetchWithRetry("/album-masters/review/batch?limit=50", { method: "POST" });
        const data = await res.json();
        $("reviewBatchRemainingCount").textContent = `미수집 약 ${data.remaining}건`;
        status.textContent = `완료 — 처리: ${data.processed}건 / 성공: ${data.succeeded}건 / 실패: ${data.failed}건 / 잔여: ${data.remaining}건`;
      } catch (e) {
        status.textContent = String(e);
      }
      btn.disabled = false;
    });
    $("quickCategory").addEventListener("change", syncQuickSizeGroup);
    $("quickCreateBtn").addEventListener("click", createQuickOwnedItem);
    $("quickResetBtn").addEventListener("click", resetQuickForm);
    $("quickItemName").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); createQuickOwnedItem(); }});
    $("homeSearchBtn").addEventListener("click", () => homeSearchOwnedItems({ resetPage: true }));
    $("homeResetBtn").addEventListener("click", async () => {
      resetHomeSearchForm();
      await homeSearchOwnedItems({ resetPage: true });
    });
    $("homeNewBtn").addEventListener("click", goToRegisterFromHome);
    $("homeNoResultCreateBtn").addEventListener("click", goToRegisterFromHome);
    $("adminManageEmptyStateSearchBtn").addEventListener("click", showHomeSearchView);
    $("homeArtist").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); homeSearchOwnedItems({ resetPage: true }); }});
    $("homeItemName").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); homeSearchOwnedItems({ resetPage: true }); }});
    $("homeCatalogNo").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); homeSearchOwnedItems({ resetPage: true }); }});
    $("homeBarcode").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); homeSearchOwnedItems({ resetPage: true }); }});
    $("homeReleaseYear").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); homeSearchOwnedItems({ resetPage: true }); }});
    $("homeItemId").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); homeSearchOwnedItems({ resetPage: true }); }});
    initSearchOptionsCheckboxes();
    $("homeSortMode").addEventListener("change", () => homeSearchOwnedItems({ resetPage: true }));
    $("homeSigDirect").addEventListener("change", () => homeSearchOwnedItems({ resetPage: true }));
    $("homeSigPurchase").addEventListener("change", () => homeSearchOwnedItems({ resetPage: true }));
    $("homeLimitEd").addEventListener("change", () => homeSearchOwnedItems({ resetPage: true }));
    $("homeNewProduct").addEventListener("change", () => homeSearchOwnedItems({ resetPage: true }));
    $("homePromo").addEventListener("change", () => homeSearchOwnedItems({ resetPage: true }));
    // 메타 결핍 체크박스는 예외 큐로 이동됨
    $("homePageSize").addEventListener("change", () => {
      homeSearchPageSize = Math.max(1, Math.min(500, Number($("homePageSize").value || 30)));
      homeSearchOwnedItems({ resetPage: true });
    });
    $("homeSearchPager").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-home-search-page]");
      if (!btn) return;
      const page = Math.max(1, Number(btn.getAttribute("data-home-search-page") || 1));
      const totalPages = Math.max(1, Math.ceil(homeSearchTotalCount / homeSearchPageSize));
      if (page === homeSearchPage || page < 1 || page > totalPages) return;
      homeSearchPage = page;
      homeSearchOwnedItems();
    });
    $("homeSearchPagerBottom").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-home-search-page]");
      if (!btn) return;
      const page = Math.max(1, Number(btn.getAttribute("data-home-search-page") || 1));
      const totalPages = Math.max(1, Math.ceil(homeSearchTotalCount / homeSearchPageSize));
      if (page === homeSearchPage || page < 1 || page > totalPages) return;
      homeSearchPage = page;
      homeSearchOwnedItems();
    });
    $("homeDashCabinetCloseBtn").addEventListener("click", () => {
      const preserveSlotSelection = homeDashboardSlotSelectedIds.size > 0;
      homeDashboardSelectedCabinetKey = null;
      homeDashboardSelectedSlotCode = null;
      homeDashSurfacePanel = "";
      if (!preserveSlotSelection) {
        homeDashboardSlotItems = [];
        homeDashboardSlotItemsSlotCode = null;
        resetDashboardSlotSelection();
      }
      homeDashboardSlotItemsLoading = false;
      renderDashboardSlotCards(homeDashboardBySlot, homeDashboardInCollectionItems);
    });
    $("homeDashSlotBulkBtn").addEventListener("click", () => toggleDashboardSurfacePanel("BULK"));
    $("homeDashBulkCloseBtn").addEventListener("click", () => toggleDashboardSurfacePanel("BULK"));
    $("homeDashBulkApplyBtn").addEventListener("click", applyDashboardBulkEdit);
    $("homeDashBulkResetBtn").addEventListener("click", () => {
      resetDashboardBulkEditForm();
      syncDashboardSelectionControls();
    });
    $("homeDashBulkStatus").addEventListener("change", syncDashboardSelectionControls);
    $("homeDashBulkDomainCode").addEventListener("change", syncDashboardSelectionControls);
    $("homeDashBulkReleaseType").addEventListener("change", syncDashboardSelectionControls);
    $("homeDashBulkSecondHand").addEventListener("change", syncDashboardSelectionControls);
    $("homeDashBulkPurchaseSource").addEventListener("input", syncDashboardSelectionControls);
    $("homeDashBulkPreferredSize").addEventListener("change", syncDashboardSelectionControls);
    $("homeDashBulkMemoryNote").addEventListener("input", syncDashboardSelectionControls);
    $("sourceWorkbenchLoadBtn").addEventListener("click", loadSourceWorkbenchTargets);
    $("sourceWorkbenchFetchAllBtn").addEventListener("click", fetchAllSourceWorkbenchCandidates);
    $("sourceWorkbenchAutoApplyBtn").addEventListener("click", runAutoReadySourceWorkbench);
    $("sourceWorkbenchApplyBtn").addEventListener("click", openSourceWorkbenchDiffReviewForSelections);
    $("sourceWorkbenchDiffReviewSelectAllBtn").addEventListener("click", () => updateSourceWorkbenchDiffSelections("ALL"));
    $("sourceWorkbenchDiffReviewSelectEmptyBtn").addEventListener("click", () => updateSourceWorkbenchDiffSelections("EMPTY_ONLY"));
    $("sourceWorkbenchDiffReviewClearBtn").addEventListener("click", () => updateSourceWorkbenchDiffSelections("CLEAR"));
    $("sourceWorkbenchDiffReviewCancelBtn").addEventListener("click", closeSourceWorkbenchDiffReview);
    $("sourceWorkbenchDiffReviewApplyBtn").addEventListener("click", submitSourceWorkbenchDiffReviewSelection);
    $("sourceWorkbenchQueueClearBtn").addEventListener("click", () => {
      if (!window.confirm(t("media.source.confirm.clear_queue"))) return;
      sourceWorkbenchQueue = [];
      saveSourceWorkbenchQueue();
      renderSourceWorkbenchQueue();
      setStatus("sourceWorkbenchStatus", "ok", t("media.source.status.queue_cleared"));
    });
    $("editCategory").addEventListener("change", () => {
      syncHomeEditorMusicVisibility();
      renderHomeProductRelationSection();
    });
    $("editMediaType").addEventListener("change", function() { if ($("editFormatName")) $("editFormatName").value = ""; _syncVinylOnlyFields(); _syncCategoryFromMedia(); });
    $("editIsLimitedEdition").addEventListener("change", function() {
      setHiddenIfPresent("editEditionNumberWrap", !this.checked);
    });
    $("editPackageContentsOtherCheck").addEventListener("change", function() {
      const otherText = $("editPackageContentsOtherText");
      if (otherText) otherText.style.display = this.checked ? "" : "none";
    });
    $("editItemName").addEventListener("input", syncHomeMasterInlineEditor);
    $("homeMasterCorrectionSaveBtn").addEventListener("click", saveHomeMasterCorrection);
    $("homeMasterSortArtistSaveBtn").addEventListener("click", saveHomeMasterSortArtistName);
    $("homeMasterMetaSpotifyEditBtn")?.addEventListener("click", openSpotifyEditMode);
    $("homeMasterMetaSpotifyCancelBtn")?.addEventListener("click", closeSpotifyEditMode);
    $("homeMasterMetaSpotifySaveBtn")?.addEventListener("click", async () => {
      await linkHomeMasterSpotify();
      const statusEl = $("homeMasterSpotifyMatchStatus");
      if (!statusEl?.classList.contains("is-error")) closeSpotifyEditMode();
    });
    $("homeMasterMetaSpotifyUnlinkBtn")?.addEventListener("click", async () => {
      await unlinkHomeMasterSpotify();
      const statusEl = $("homeMasterSpotifyMatchStatus");
      if (!statusEl?.classList.contains("is-error")) closeSpotifyEditMode();
    });

    // ── 로컬 경로 핸들러 ──────────────────────────────────────────────────────
    $("homeMasterLocalText")?.addEventListener("click", () => {
      const masterId = Number(homeMasterInfo?.album_master_id || homeSelectedMasterId || 0);
      if (!masterId) return;
      const spSlot = document.getElementById("homeMasterSpotifyEmbed");
      if (spSlot) { spSlot.hidden = true; spSlot.innerHTML = ""; delete spSlot.dataset.albumId; }
      _lp._slotId = "homeMasterLocalPlayer";
      _lp.hide();
      _lp.load(masterId).catch(() => {});
    });
    $("homeMasterLocalEditBtn")?.addEventListener("click", () => {
      const localRow = $("homeMasterLocalRow");
      const localEditRow = $("homeMasterLocalEditRow");
      const pathInput = $("homeMasterLocalPath");
      if (localRow) localRow.style.display = "none";
      if (localEditRow) localEditRow.style.display = "flex";
      if (pathInput) {
        // 현재 경로 prefill
        const txt = $("homeMasterLocalText")?.textContent || "";
        const match = txt.match(/♪ Local: (.+)/);
        if (match && match[1] !== "미연결") {
          pathInput.value = match[1].replace(/^…\//, "/Volumes/Music/");
        } else {
          pathInput.value = "";
        }
        pathInput.focus();
      }
    });
    $("homeMasterLocalCancelBtn")?.addEventListener("click", () => {
      $("homeMasterLocalRow").style.display = "flex";
      $("homeMasterLocalEditRow").style.display = "none";
      if ($("homeMasterLocalStatus")) $("homeMasterLocalStatus").textContent = "";
    });
    $("homeMasterLocalSaveBtn")?.addEventListener("click", saveLocalPath);
    $("homeMasterLocalPath")?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); saveLocalPath(); }
      if (e.key === "Escape") { _hideLocalDirResults(); }
    });

    // ── 디렉토리 검색 자동완성 ──────────────────────────────────────────────
    let _localDirSearchTimer = null;

    let _localDirComposing = false;
    $("homeMasterLocalPath")?.addEventListener("compositionstart", () => { _localDirComposing = true; });
    $("homeMasterLocalPath")?.addEventListener("compositionend", () => {
      _localDirComposing = false;
      $("homeMasterLocalPath")?.dispatchEvent(new Event("input"));
    });
    $("homeMasterLocalPath")?.addEventListener("input", () => {
      if (_localDirComposing) return;
      clearTimeout(_localDirSearchTimer);
      const q = ($("homeMasterLocalPath")?.value || "").trim();
      if (q.length < 2) { _hideLocalDirResults(); return; }
      _localDirSearchTimer = setTimeout(async () => {
        try {
          const res = await fetchWithRetry(`/local-music/search-dirs?q=${encodeURIComponent(q)}&limit=20`);
          if (!res.ok) return;
          const data = await safeJson(res);
          _showLocalDirResults(data.dirs || []);
        } catch (_) {}
      }, 250);
    });

    $("homeMasterLocalPath")?.addEventListener("blur", () => {
      setTimeout(_hideLocalDirResults, 150);
    });
    $("homeMasterLocalUnlinkBtn")?.addEventListener("click", async () => {
      const masterIdVal = Number(homeMasterInfo?.album_master_id || 0);
      if (!masterIdVal) return;
      const statusEl = $("homeMasterLocalStatus");
      await fetchWithRetry(`/album-masters/${masterIdVal}/local-link`, { method: "DELETE" });
      _localLinkedIds.delete(masterIdVal);
      const localText = $("homeMasterLocalText");
      if (localText) { localText.textContent = "♪ Local: 미연결"; localText.style.cursor = ""; }
      if (statusEl) statusEl.textContent = "";
      _lp._slotId = "homeMasterLocalPlayer";
      _lp.hide();
    });
    $("homeMasterSpotifyMatchId")?.addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      e.preventDefault();
      $("homeMasterMetaSpotifySaveBtn")?.click();
    });
    $("homeMasterCorrectionNote").addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      e.preventDefault();
      saveHomeMasterCorrection();
    });
    $("homeMasterSortArtistName").addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      e.preventDefault();
      saveHomeMasterSortArtistName();
    });
    $("editLabelName").addEventListener("input", syncHomeRelatedSelectedMetaPreview);
    $("editCatalogNo").addEventListener("input", syncHomeRelatedSelectedMetaPreview);
    $("editBarcode").addEventListener("input", syncHomeRelatedSelectedMetaPreview);
    $("editLabelName").addEventListener("change", syncHomeRelatedSelectedMetaPreview);
    $("editCatalogNo").addEventListener("change", syncHomeRelatedSelectedMetaPreview);
    $("editBarcode").addEventListener("change", syncHomeRelatedSelectedMetaPreview);
    $("editSignatureType").addEventListener("change", syncHomeSourceManagedMetaUi);
    $("editMemoryNote").addEventListener("input", syncHomeSourceManagedMetaUi);
    $("homeEditCoverImageFile").addEventListener("change", onHomeEditCoverImageFileChange);
    $("homeEditCoverImagePaste").addEventListener("paste", onHomeEditCoverImagePaste);
    $("homeEditCoverImagePaste").addEventListener("change", () => {
      const urls = extractUrlCandidates($("homeEditCoverImagePaste").value);
      if (!urls.length) return;
      applyHomeEditCoverImageUrl(urls[0], t("media.manage.cover.status.url_applied"));
      $("homeEditCoverImagePaste").value = "";
    });
    if ($("homeEditCoverImageUrlInput")) {
      $("homeEditCoverImageUrlInput").addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); handleHomeEditCoverImageUrlApply(); } });
    }
    if ($("editImagePasteInput")) {
      $("editImagePasteInput").addEventListener("paste", onEditImagePaste);
      $("editImagePasteInput").addEventListener("change", async () => {
        const urls = extractUrlCandidates($("editImagePasteInput").value);
        if (!urls.length) return;
        $("editImagePasteInput").value = "";
        if ($("editImageUrlInput")) $("editImageUrlInput").value = urls[0];
        await handleEditImageUrlAdd();
      });
    }
    if ($("editImageUrlInput")) {
      $("editImageUrlInput").addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); handleEditImageUrlAdd(); } });
    }
    $("homeProductRelationSeriesSearchBtn").addEventListener("click", searchHomeProductRelationSeriesTargets);
    $("homeProductRelationSeriesQuery").addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      e.preventDefault();
      searchHomeProductRelationSeriesTargets();
    });
    $("homeProductRelationCreateGroupBtn").addEventListener("click", createHomeProductRelationSeriesGroup);
    $("homeProductRelationSearchBtn").addEventListener("click", searchHomeProductRelationReleaseTargets);
    $("homeProductRelationReleaseQuery").addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      e.preventDefault();
      searchHomeProductRelationReleaseTargets();
    });
    $("homeProductRelationSaveBtn").addEventListener("click", saveHomeOwnedItemRelations);
    $("homeProductRelationSection").addEventListener("click", (e) => {
      const removeBtn = e.target.closest("[data-home-remove-product-relation]");
      if (removeBtn) {
        const index = Number(removeBtn.getAttribute("data-home-product-relation-index") || -1);
        if (Number.isInteger(index) && index >= 0 && index < homeOwnedItemEditableRelations.length) {
          homeOwnedItemEditableRelations.splice(index, 1);
          renderHomeProductRelationSection();
          setStatus("homeProductRelationStatus", "", "");
        }
        return;
      }

      const addSeriesBtn = e.target.closest("[data-home-add-product-series]");
      if (addSeriesBtn) {
        addHomeOwnedItemRelationDraft({
          relation_type: "SERIES_MEMBER",
          target_kind: "PRODUCT_GROUP",
          target_ref: String(addSeriesBtn.getAttribute("data-home-add-product-series") || "").trim(),
          target_label: String(addSeriesBtn.getAttribute("data-home-add-product-series-name") || "").trim() || null,
          product_group_id: Number(addSeriesBtn.getAttribute("data-home-add-product-series") || 0) || null,
          product_group_type: String(addSeriesBtn.getAttribute("data-home-add-product-series-type") || "SERIES").trim().toUpperCase(),
        });
        setHtmlIfPresent("homeProductRelationSeriesResults", "");
        if ($("homeProductRelationSeriesQuery")) $("homeProductRelationSeriesQuery").value = "";
        setStatus("homeProductRelationStatus", "", "");
        return;
      }

      const addReleaseBtn = e.target.closest("[data-home-add-product-release]");
      if (!addReleaseBtn) return;
      addHomeOwnedItemRelationDraft({
        relation_type: String($("homeProductRelationType")?.value || "BOX_MEMBER_OF").trim().toUpperCase(),
        target_kind: "OWNED_ITEM",
        target_ref: String(addReleaseBtn.getAttribute("data-home-add-product-release") || "").trim(),
        target_label: String(addReleaseBtn.getAttribute("data-home-add-product-release-name") || "").trim() || null,
        target_owned_item_id: Number(addReleaseBtn.getAttribute("data-home-add-product-release") || 0) || null,
        target_category: String(addReleaseBtn.getAttribute("data-home-add-product-release-category") || "").trim().toUpperCase() || null,
        note: String($("homeProductRelationNote")?.value || "").trim() || null,
      });
      setHtmlIfPresent("homeProductRelationReleaseResults", "");
      if ($("homeProductRelationReleaseQuery")) $("homeProductRelationReleaseQuery").value = "";
      if ($("homeProductRelationNote")) $("homeProductRelationNote").value = "";
      setStatus("homeProductRelationStatus", "", "");
    });
    $("homeEditSaveBtn").addEventListener("click", saveHomeEditedItem);
    $("homeEditTrackSaveBtn")?.addEventListener("click", saveHomeEditedItem);
    $("editTrackList")?.addEventListener("input", () => renderHomeTrackInfoPanel());
    $("homeEditDeleteBtn").addEventListener("click", deleteHomeSelectedItem);
    $("homeMasterDeleteBtn").addEventListener("click", () => {
      const panel = $("homeMasterDeleteConfirm");
      if (panel) panel.style.display = panel.style.display === "none" ? "" : "none";
    });
    $("homeMasterDeleteConfirmBtn").addEventListener("click", () => deleteHomeSelectedMaster());
    $("homeMasterDeleteCancelBtn").addEventListener("click", () => {
      const panel = $("homeMasterDeleteConfirm");
      if (panel) panel.style.display = "none";
    });
    $("homeMasterReviewToggleBtn")?.addEventListener("click", () => {
      const preview = $("homeMasterReviewPreview");
      const btn = $("homeMasterReviewToggleBtn");
      if (!preview || !btn) return;
      const expanded = btn.dataset.expanded === "true";
      const MANAGE_PREVIEW_LEN = 200;
      const fullText = preview.dataset.fullText || "";
      if (expanded) {
        preview.textContent = fullText.slice(0, MANAGE_PREVIEW_LEN) + "…";
        btn.textContent = "더보기 ▼";
        btn.dataset.expanded = "false";
      } else {
        preview.textContent = fullText;
        btn.textContent = "접기 ▲";
        btn.dataset.expanded = "true";
      }
    });
    $("homeMasterReviewAutoBtn")?.addEventListener("click", async () => {
      const masterId = currentHomeMasterId();
      if (!masterId) return;
      const btn = $("homeMasterReviewAutoBtn");
      const status = $("homeMasterReviewStatus");
      btn.disabled = true;

      const steps = [
        "① Wikipedia 검색 중...",
        "② 앨범 페이지 확인 중...",
        "③ 텍스트 추출 중...",
        "④ 한국어 요약 중 (DeepSeek)...",
      ];
      let stepIdx = 0;
      status.textContent = steps[0];
      const stepTimer = setInterval(() => {
        stepIdx = Math.min(stepIdx + 1, steps.length - 1);
        status.textContent = steps[stepIdx];
      }, 2500);

      try {
        const res = await fetchWithRetry(`/album-masters/${masterId}/review/auto`, { method: "POST" });
        clearInterval(stepTimer);
        const data = await res.json();
        if (data.ok) {
          const charCount = String(data.review_text || "").length;
          const preview = String(data.review_text || "").slice(0, 80).replace(/\n/g, " ");
          const sourceLabel = data.source || "WIKIPEDIA";
          const urlPart = data.review_url ? ` <a href="${data.review_url}" target="_blank" rel="noopener" style="font-size:0.7rem">원문↗</a>` : "";
          status.innerHTML = `✅ 수집 완료 — 출처: <strong>${sourceLabel}</strong> · ${charCount}자${urlPart}<br><span style="font-size:0.75rem;color:var(--muted)">${preview}${charCount > 80 ? "…" : ""}</span>`;
          await refreshCurrentMasterReview(masterId);
        } else {
          const detail = data.detail || "수집 실패";
          if (res.status === 404) {
            status.textContent = `⚠️ Wikipedia에서 앨범 페이지를 찾지 못했습니다 (${detail})`;
          } else {
            status.textContent = `❌ ${detail}`;
          }
        }
      } catch (e) {
        clearInterval(stepTimer);
        status.textContent = `❌ 오류: ${String(e)}`;
      }
      btn.disabled = false;
    });
    $("homeMasterReviewUrlBtn")?.addEventListener("click", () => {
      $("homeMasterReviewUrlForm").style.display = "";
      $("homeMasterReviewManualForm").style.display = "none";
    });
    $("homeMasterReviewUrlCancelBtn")?.addEventListener("click", () => {
      $("homeMasterReviewUrlForm").style.display = "none";
    });
    $("homeMasterReviewUrlSubmitBtn")?.addEventListener("click", async () => {
      const masterId = currentHomeMasterId();
      const url = ($("homeMasterReviewUrlInput").value || "").trim();
      if (!masterId || !url) return;
      const btn = $("homeMasterReviewUrlSubmitBtn");
      const status = $("homeMasterReviewStatus");
      btn.disabled = true;
      status.textContent = "URL에서 수집 중...";
      try {
        const res = await fetchWithRetry(`/album-masters/${masterId}/review/url`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url }),
        });
        const data = await res.json();
        if (data.ok) {
          status.textContent = `완료 (출처: ${data.source})`;
          $("homeMasterReviewUrlForm").style.display = "none";
          await refreshCurrentMasterReview(masterId);
        } else {
          status.textContent = data.detail || "실패";
        }
      } catch (e) {
        status.textContent = String(e);
      }
      btn.disabled = false;
    });
    $("homeMasterReviewManualBtn")?.addEventListener("click", () => {
      $("homeMasterReviewManualForm").style.display = "";
      $("homeMasterReviewUrlForm").style.display = "none";
    });
    $("homeMasterReviewManualCancelBtn")?.addEventListener("click", () => {
      $("homeMasterReviewManualForm").style.display = "none";
    });
    $("homeMasterReviewManualSubmitBtn")?.addEventListener("click", async () => {
      const masterId = currentHomeMasterId();
      const text = ($("homeMasterReviewManualText").value || "").trim();
      const source = ($("homeMasterReviewManualSource").value || "MANUAL").trim();
      if (!masterId || !text) return;
      const btn = $("homeMasterReviewManualSubmitBtn");
      const status = $("homeMasterReviewStatus");
      btn.disabled = true;
      status.textContent = "저장 중...";
      try {
        const res = await fetchWithRetry(`/album-masters/${masterId}/review/manual`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, source }),
        });
        const data = await res.json();
        if (data.ok) {
          status.textContent = "저장 완료";
          $("homeMasterReviewManualForm").style.display = "none";
          await refreshCurrentMasterReview(masterId);
        } else {
          status.textContent = data.detail || "실패";
        }
      } catch (e) {
        status.textContent = String(e);
      }
      btn.disabled = false;
    });
    $("homeMasterReviewDeleteBtn")?.addEventListener("click", async () => {
      const masterId = currentHomeMasterId();
      if (!masterId || !confirm("리뷰를 삭제하시겠습니까?")) return;
      const status = $("homeMasterReviewStatus");
      status.textContent = "삭제 중...";
      try {
        const res = await fetchWithRetry(`/album-masters/${masterId}/review`, { method: "DELETE" });
        const data = await res.json();
        if (data.ok) {
          status.textContent = "삭제 완료";
          await refreshCurrentMasterReview(masterId);
        } else {
          status.textContent = data.detail || "실패";
        }
      } catch (e) {
        status.textContent = String(e);
      }
    });
    $("homeMasterAddLoadBtn").addEventListener("click", () => loadHomeManageMasterLookup({ resetPage: true }));
    $("homeMasterAddResetBtn").addEventListener("click", () => {
      resetHomeMasterLookupUi({ clearInputs: true });
      loadHomeManageMasterLookup({ resetPage: true });
    });
    $("homeMasterAddPrevBtn").addEventListener("click", () => {
      if (homeMasterAddPage <= 1) return;
      homeMasterAddPage -= 1;
      loadHomeMasterAddVariants();
    });
    $("homeMasterAddNextBtn").addEventListener("click", () => {
      if (!homeMasterAddHasNext) return;
      homeMasterAddPage += 1;
      loadHomeMasterAddVariants();
    });
    $("homeMasterAddCatalogNo").addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      e.preventDefault();
      loadHomeMasterAddVariants({ resetPage: true });
    });
    $("homeMasterAddBarcode").addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      e.preventDefault();
      loadHomeMasterAddVariants({ resetPage: true });
    });
    $("homeLinkedGoodsCategory").addEventListener("change", syncHomeLinkedGoodsSpecVisibility);
    $("homeLinkedGoodsImageFiles").addEventListener("change", onHomeLinkedGoodsImageFileChange);
    $("homeLinkedGoodsImagePaste").addEventListener("paste", onHomeLinkedGoodsImagePaste);
    $("homeLinkedGoodsImagePaste").addEventListener("change", () => {
      const urls = extractUrlCandidates($("homeLinkedGoodsImagePaste").value);
      if (!urls.length) return;
      addHomeLinkedGoodsImageEntries(urls);
      $("homeLinkedGoodsImagePaste").value = "";
      setStatus("homeLinkedGoodsStatus", "ok", t("media.manage.collectibles.image.status.urls_applied", { count: urls.length }));
    });
    $("homeLinkedGoodsImageList").addEventListener("click", (e) => {
      const btn = e.target.closest(".home-linked-image-remove");
      if (!btn) return;
      const idx = Number(btn.getAttribute("data-idx") || -1);
      if (!Number.isInteger(idx) || idx < 0 || idx >= homeLinkedGoodsImageEntries.length) return;
      const next = homeLinkedGoodsImageEntries.filter((_, i) => i !== idx);
      setHomeLinkedGoodsImageEntries(next);
    });
    $("homeLinkedGoodsCreateBtn").addEventListener("click", openGoodsRegisterFromManageContext);
    $("homeProductLinkedGoodsOpenBtn")?.addEventListener("click", openGoodsRegisterFromProductContext);
    $("homeEditShelfPrevBtn").addEventListener("click", () => moveHomeEditShelf(-1));
    $("homeEditShelfNextBtn").addEventListener("click", () => moveHomeEditShelf(1));
    $("homeMetaBarcodeBtn").addEventListener("click", searchHomeMetadataByBarcode);
    $("homeMetaQueryBtn").addEventListener("click", searchHomeMetadataByQuery);
    $("homeTrackMapPickDirBtn").addEventListener("click", pickHomeTrackMapDirectory);
    $("homeTrackMapDir").addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      e.preventDefault();
      bulkMapHomeTrackMappings();
    });
    $("homeTrackMapDir").addEventListener("change", () => {
      const directoryPath = $("homeTrackMapDir").value.trim();
      if (!directoryPath) {
        renderHomeTrackFileList([], null);
        return;
      }
      bulkMapHomeTrackMappings();
    });
    $("homeMetaBarcode").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); searchHomeMetadataByBarcode(); }});
    $("homeMetaQuery").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); searchHomeMetadataByQuery(); }});
    $("homeSearchResults").addEventListener("click", async (e) => {
      const togglePreviewBtn = e.target.closest("[data-home-toggle-member-preview]");
      if (togglePreviewBtn) {
        e.preventDefault();
        e.stopPropagation();
        const masterId = Number(togglePreviewBtn.getAttribute("data-home-toggle-member-preview") || 0);
        if (masterId > 0) {
          if (homeExpandedMasterPreviewIds.has(masterId)) homeExpandedMasterPreviewIds.delete(masterId);
          else homeExpandedMasterPreviewIds.add(masterId);
          renderHomeSearchResults(homeSearchResults);
        }
        return;
      }
      const repairDiscogsMasterBtn = e.target.closest("[data-home-repair-discogs-master]");
      if (repairDiscogsMasterBtn) {
        e.preventDefault();
        e.stopPropagation();
        const ownedItemId = Number(repairDiscogsMasterBtn.getAttribute("data-home-repair-discogs-master") || 0);
        if (ownedItemId > 0) {
          const progressStatusText = t("media.manage.search.repair_discogs_master.progress");
          try {
            setStatus("homeSearchStatus", "ok", progressStatusText);
            const res = await fetchWithRetry(`/owned-items/${ownedItemId}/repair-discogs-master-link`, { method: "POST" }, {
              retries: 2,
              retryDelayMs: 250,
              onRetry: (attempt, total) => setStatus("homeSearchStatus", "ok", retryingStatusText(progressStatusText, attempt, total)),
            });
            const data = await safeJson(res);
            if (!res.ok) throw new Error(data.detail || t("media.manage.search.repair_discogs_master.failed"));
            discogsRepairEligibilityCache.delete(ownedItemId);
            await homeSearchOwnedItems({ allowPageAdjust: false });
            setMediaSearchContextSelectionByOwnedItem(ownedItemId);
            const notices = Array.isArray(data?.notices) ? data.notices.map((value) => String(value || "").trim()).filter((value) => value) : [];
            setStatus("homeSearchStatus", "ok", notices[0] || t("media.manage.search.repair_discogs_master.done"));
          } catch (err) {
            setStatus("homeSearchStatus", "err", err.message || t("media.manage.search.repair_discogs_master.failed"));
          }
        }
        return;
      }
      const inlineSaveBtn = e.target.closest("[data-media-search-inline-save]");
      if (inlineSaveBtn) {
        e.preventDefault();
        e.stopPropagation();
        const ownedItemId = Number(inlineSaveBtn.getAttribute("data-media-search-inline-save") || 0);
        const masterId = Number(inlineSaveBtn.getAttribute("data-media-search-inline-save-master-id") || 0);
        if (ownedItemId > 0 && masterId > 0) {
          await saveMediaSearchInlineEditor(masterId, ownedItemId);
        }
        return;
      }
      const inlineCancelBtn = e.target.closest("[data-media-search-inline-cancel]");
      if (inlineCancelBtn) {
        e.preventDefault();
        e.stopPropagation();
        const masterId = Number(inlineCancelBtn.getAttribute("data-media-search-inline-cancel") || 0);
        if (masterId > 0) {
          cancelMediaSearchInlineEditor(masterId);
        }
        return;
      }
      const inlineEditorRoot = e.target.closest("[data-media-search-inline-editor]");
      if (inlineEditorRoot) {
        e.stopPropagation();
        return;
      }
      const openLocationBtn = e.target.closest("[data-home-open-dashboard-location]");
      if (openLocationBtn) {
        e.preventDefault();
        e.stopPropagation();
        const slotId = Number(openLocationBtn.getAttribute("data-home-open-dashboard-location") || 0);
        const slotCode = String(openLocationBtn.getAttribute("data-home-open-dashboard-slot-code") || "");
        const cabinetName = String(openLocationBtn.getAttribute("data-home-open-cabinet-name") || "").trim();
        const columnCode = String(openLocationBtn.getAttribute("data-home-open-column-code") || "").trim();
        const cellCode = String(openLocationBtn.getAttribute("data-home-open-cell-code") || "").trim();
        await openCabinetLocationAction(slotId, slotCode, cabinetName, columnCode, cellCode);
        return;
      }
      const previewEditBtn = e.target.closest("[data-home-preview-edit]");
      if (previewEditBtn) {
        e.preventDefault();
        e.stopPropagation();
        const ownedItemId = Number(previewEditBtn.getAttribute("data-home-preview-edit") || 0);
        const masterId = Number(previewEditBtn.getAttribute("data-home-preview-edit-master-id") || 0);
        await openMediaSearchInlineEditor(masterId, ownedItemId);
        return;
      }
      const detailManageBtn = e.target.closest("[data-home-open-detail-manage]");
      if (detailManageBtn) {
        e.preventDefault();
        e.stopPropagation();
        const ownedItemId = Number(detailManageBtn.getAttribute("data-home-open-detail-manage") || 0);
        const masterId = Number(detailManageBtn.getAttribute("data-home-open-detail-master-id") || 0);
        await openMediaSearchDetailManage(masterId, ownedItemId);
        return;
      }
      const previewSelectBtn = e.target.closest("[data-home-member-preview-select]");
      if (previewSelectBtn) {
        e.preventDefault();
        e.stopPropagation();
        const ownedItemId = Number(previewSelectBtn.getAttribute("data-home-member-preview-select") || 0);
        if (ownedItemId > 0) {
          setMediaSearchContextSelectionByOwnedItem(ownedItemId);
        }
        return;
      }
      const metaSyncBtn = e.target.closest("[data-home-meta-sync]");
      if (metaSyncBtn) {
        e.preventDefault();
        e.stopPropagation();
        const ownedItemId = Number(metaSyncBtn.getAttribute("data-home-meta-sync") || 0);
        if (ownedItemId > 0) {
          executeMetadataSyncAction(ownedItemId, metaSyncBtn, async () => {
            await refreshHomeSearchResultCard(0).catch(() => {});
          });
        }
        return;
      }
    });
    $("homeDashSlotGrid").addEventListener("click", async (e) => {
      const refreshBtn = e.target.closest("[data-dashboard-cabinet-refresh]");
      if (refreshBtn) {
        const cabinetKey = decodeURIComponent(refreshBtn.getAttribute("data-dashboard-cabinet-refresh") || "");
        if (!cabinetKey) return;
        e.preventDefault();
        e.stopPropagation();
        await refreshDashboardCabinetGroup(cabinetKey);
        return;
      }
      const slotTile = e.target.closest("[data-dashboard-map-slot-code]");
      if (slotTile) {
        const slotCode = String(slotTile.getAttribute("data-dashboard-map-slot-code") || "").trim();
        if (!slotCode) return;
        const groups = buildDashboardCabinetGroups(homeDashboardBySlot);
        const slotRow = groups
          .flatMap((group) => group.rows)
          .find((row) => String(row?.slot_code || "").trim() === slotCode) || null;
        if (!slotRow) return;
        if (isShellReadOnly()) {
          resetDashboardDragState();
          await openDashboardForResolvedSlot(slotRow);
          return;
        }
        const selectedWorkbenchItems = getDashboardSelectedWorkbenchRows();
        const selectionSourceKind = getDashboardSelectionSourceKind();
        const clickMoveActive = isDashboardClickMoveModeActive();
        const sourceSlotCode = selectionSourceKind === "SLOT"
          ? String(homeDashboardSlotItemsSlotCode || homeDashboardSlotSelectionSnapshot[0]?.slot_code || "").trim()
          : "";
        if (selectedWorkbenchItems.length && !clickMoveActive) {
          resetDashboardDragState();
          await openDashboardForResolvedSlot(slotRow);
          return;
        }
        if (
          selectedWorkbenchItems.length
          && (
            selectionSourceKind === "SLOT"
              ? (sourceSlotCode && sourceSlotCode !== slotCode)
              : true
          )
        ) {
          resetDashboardDragState();
          await moveDashboardOwnedItemsToSlot(selectedWorkbenchItems, slotCode, { trigger: "click" });
          return;
        }
        const sourceOwnedItemId = Number(dashboardDraggedOwnedItemId || 0);
        const draggedSlotCode = String(dashboardDraggedSlotCode || "").trim();
        if (sourceOwnedItemId && draggedSlotCode && draggedSlotCode !== slotCode) {
          previewDashboardTargetSlot(slotCode);
          await moveDashboardOwnedItemToSlot(sourceOwnedItemId, slotCode);
          return;
        }
        await openDashboardForResolvedSlot(slotRow);
        return;
      }
      const btn = e.target.closest("[data-dashboard-cabinet-key]");
      if (!btn) return;
      const cabinetKey = decodeURIComponent(btn.getAttribute("data-dashboard-cabinet-key") || "");
      if (!cabinetKey) return;
      toggleDashboardCabinet(cabinetKey);
    });
    $("homeDashSlotGrid").addEventListener("dragover", (e) => {
      if (isShellReadOnly()) return;
      const slotTile = e.target.closest("[data-dashboard-map-slot-code]");
      const selectedRows = getDashboardDraggedRows(e);
      const sourceOwnedItemId = getDashboardDraggedOwnedItemId(e);
      if (!slotTile || (!selectedRows.length && !sourceOwnedItemId)) return;
      e.preventDefault();
      clearDashboardDragHints();
      slotTile.classList.add("drag-over", "drop-ready");
      if (e.dataTransfer) e.dataTransfer.dropEffect = "move";
    });
    $("homeDashSlotGrid").addEventListener("dragleave", (e) => {
      if (isShellReadOnly()) return;
      const slotTile = e.target.closest("[data-dashboard-map-slot-code]");
      if (!slotTile) return;
      slotTile.classList.remove("drag-over");
    });
    $("homeDashSlotGrid").addEventListener("drop", async (e) => {
      if (isShellReadOnly()) return;
      const slotTile = e.target.closest("[data-dashboard-map-slot-code]");
      const selectedRows = getDashboardDraggedRows(e);
      const sourceOwnedItemId = getDashboardDraggedOwnedItemId(e);
      if (!slotTile || (!selectedRows.length && !sourceOwnedItemId)) return;
      e.preventDefault();
      const targetSlotCode = String(slotTile.getAttribute("data-dashboard-map-slot-code") || "").trim();
      if (!targetSlotCode) {
        resetDashboardDragState();
        return;
      }
      if (selectedRows.length > 1) {
        if (selectedRows.every((row) => String(row?.slot_code || "").trim() === targetSlotCode)) {
          resetDashboardDragState();
          return;
        }
        try {
          await moveDashboardOwnedItemsToSlot(selectedRows, targetSlotCode);
        } finally {
          resetDashboardDragState();
        }
        return;
      }
      const sourceSlotCode = selectedRows.length === 1
        ? String(selectedRows[0]?.slot_code || "").trim()
        : getDashboardDraggedSlotCode(e);
      const draggedOwnedItemId = selectedRows.length === 1
        ? Number(selectedRows[0]?.id || 0)
        : sourceOwnedItemId;
      if (!draggedOwnedItemId || (sourceSlotCode && sourceSlotCode === targetSlotCode)) {
        resetDashboardDragState();
        return;
      }
      await moveDashboardOwnedItemToSlot(draggedOwnedItemId, targetSlotCode);
    });
    $("homeDashSlotGridPrevBtn").addEventListener("click", () => {
      homeDashboardSlotGridFollowSelection = false;
      homeDashboardSlotGridPage = Math.max(0, homeDashboardSlotGridPage - 1);
      renderDashboardSlotCards(homeDashboardBySlot, homeDashboardInCollectionItems);
    });
    $("homeDashSlotGridNextBtn").addEventListener("click", () => {
      homeDashboardSlotGridFollowSelection = false;
      homeDashboardSlotGridPage += 1;
      renderDashboardSlotCards(homeDashboardBySlot, homeDashboardInCollectionItems);
    });
    $("homeDashCabinetFloors").addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-dashboard-slot-code]");
      if (!btn) return;
      if (isShellReadOnly()) {
        resetDashboardDragState();
        await selectDashboardSlot(String(btn.getAttribute("data-dashboard-slot-code") || "").trim());
        return;
      }
      const slotCode = String(btn.getAttribute("data-dashboard-slot-code") || "").trim();
      if (!slotCode) return;
      const selectedWorkbenchItems = getDashboardSelectedWorkbenchRows();
      const selectionSourceKind = getDashboardSelectionSourceKind();
      const clickMoveActive = isDashboardClickMoveModeActive();
      const sourceSlotCode = selectionSourceKind === "SLOT"
        ? String(homeDashboardSlotItemsSlotCode || homeDashboardSlotSelectionSnapshot[0]?.slot_code || "").trim()
        : "";
      if (selectedWorkbenchItems.length && !clickMoveActive) {
        resetDashboardDragState();
        await selectDashboardSlot(slotCode);
        return;
      }
      if (
        selectedWorkbenchItems.length
        && (
          selectionSourceKind === "SLOT"
            ? (sourceSlotCode && sourceSlotCode !== slotCode)
            : true
        )
      ) {
        resetDashboardDragState();
        await moveDashboardOwnedItemsToSlot(selectedWorkbenchItems, slotCode, { trigger: "click" });
        return;
      }
      const sourceOwnedItemId = Number(dashboardDraggedOwnedItemId || 0);
      const draggedSlotCode = String(dashboardDraggedSlotCode || "").trim();
      if (sourceOwnedItemId && draggedSlotCode && draggedSlotCode !== slotCode) {
        previewDashboardTargetSlot(slotCode);
        await moveDashboardOwnedItemToSlot(sourceOwnedItemId, slotCode);
        return;
      }
      await selectDashboardSlot(slotCode);
    });
    $("homeDashCabinetFloors").addEventListener("dragover", (e) => {
      if (isShellReadOnly()) return;
      const btn = e.target.closest("[data-dashboard-slot-code]");
      const selectedRows = getDashboardDraggedRows(e);
      const sourceOwnedItemId = getDashboardDraggedOwnedItemId(e);
      if (!btn || (!selectedRows.length && !sourceOwnedItemId)) return;
      e.preventDefault();
      clearDashboardDragHints();
      btn.classList.add("drag-over", "drop-ready");
      if (e.dataTransfer) e.dataTransfer.dropEffect = "move";
    });
    $("homeDashCabinetFloors").addEventListener("dragleave", (e) => {
      if (isShellReadOnly()) return;
      const btn = e.target.closest("[data-dashboard-slot-code]");
      if (!btn) return;
      btn.classList.remove("drag-over");
    });
    $("homeDashCabinetFloors").addEventListener("drop", async (e) => {
      if (isShellReadOnly()) return;
      const btn = e.target.closest("[data-dashboard-slot-code]");
      const selectedRows = getDashboardDraggedRows(e);
      const sourceOwnedItemId = getDashboardDraggedOwnedItemId(e);
      if (!btn || (!selectedRows.length && !sourceOwnedItemId)) return;
      e.preventDefault();
      const targetSlotCode = String(btn.getAttribute("data-dashboard-slot-code") || "").trim();
      if (!targetSlotCode) {
        resetDashboardDragState();
        return;
      }
      if (selectedRows.length > 1) {
        if (selectedRows.every((row) => String(row?.slot_code || "").trim() === targetSlotCode)) {
          resetDashboardDragState();
          return;
        }
        try {
          await moveDashboardOwnedItemsToSlot(selectedRows, targetSlotCode);
        } finally {
          resetDashboardDragState();
        }
        return;
      }
      const sourceSlotCode = selectedRows.length === 1
        ? String(selectedRows[0]?.slot_code || "").trim()
        : getDashboardDraggedSlotCode(e);
      const draggedOwnedItemId = selectedRows.length === 1
        ? Number(selectedRows[0]?.id || 0)
        : sourceOwnedItemId;
      if (!draggedOwnedItemId || (sourceSlotCode && sourceSlotCode === targetSlotCode)) {
        resetDashboardDragState();
        return;
      }
      await moveDashboardOwnedItemToSlot(draggedOwnedItemId, targetSlotCode);
    });
    $("homeDashSlotItems").addEventListener("pointerdown", (e) => {
      if (isShellReadOnly()) return;
      if (e.target.closest("[data-dashboard-selectable-id]")) return;
      startDashboardPointerSelection(e, "SLOT");
    });
    $("homeDashSlotItems").addEventListener("pointerover", (e) => {
      if (!dashboardSlotHoverMetaOverlayEnabled()) return;
      const row = e.target.closest("[data-dashboard-owned-item-id]");
      const hoveredId = Number(row?.getAttribute("data-dashboard-owned-item-id") || 0);
      const nextId = hoveredId > 0 ? hoveredId : null;
      if (homeDashboardHoveredItemId === nextId) return;
      homeDashboardHoveredItemId = nextId;
      renderDashboardSelectedItemMeta();
    });
    $("homeDashSlotItems").addEventListener("pointerleave", () => {
      if (!dashboardSlotHoverMetaOverlayEnabled()) return;
      if (homeDashboardHoveredItemId === null) return;
      homeDashboardHoveredItemId = null;
      renderDashboardSelectedItemMeta();
    });
    $("homeDashSlotItems").addEventListener("focusin", (e) => {
      if (!dashboardSlotHoverMetaOverlayEnabled()) return;
      const row = e.target.closest("[data-dashboard-owned-item-id]");
      const focusedId = Number(row?.getAttribute("data-dashboard-owned-item-id") || 0);
      const nextId = focusedId > 0 ? focusedId : null;
      if (homeDashboardHoveredItemId === nextId) return;
      homeDashboardHoveredItemId = nextId;
      renderDashboardSelectedItemMeta();
    });
    $("homeDashSlotItems").addEventListener("focusout", (e) => {
      if (!dashboardSlotHoverMetaOverlayEnabled()) return;
      const nextRow = e.relatedTarget?.closest?.("[data-dashboard-owned-item-id]") || null;
      const nextId = Number(nextRow?.getAttribute?.("data-dashboard-owned-item-id") || 0);
      homeDashboardHoveredItemId = nextId > 0 ? nextId : null;
      renderDashboardSelectedItemMeta();
    });
    $("homeDashSlotItems").addEventListener("click", (e) => {
      if (shouldSuppressDashboardSelectionClick()) {
        e.preventDefault();
        e.stopPropagation();
        return;
      }
      if (isShellReadOnly()) return;
      const check = e.target.closest("[data-dashboard-slot-select]");
      if (check) {
        e.stopPropagation();
        const ownedItemId = Number(check.getAttribute("data-dashboard-slot-select") || 0);
        if (e.shiftKey) {
          selectDashboardSlotRangeToId(ownedItemId);
          return;
        }
        toggleDashboardSlotSelectionById(ownedItemId);
        return;
      }
      const editBtn = e.target.closest("[data-dashboard-slot-edit]");
      if (editBtn) {
        e.stopPropagation();
        const ownedItemId = Number(editBtn.getAttribute("data-dashboard-slot-edit") || 0);
        if (ownedItemId > 0) {
          void openDashboardOwnedItemDetailManage(ownedItemId, "SLOT");
        }
        return;
      }
      const row = e.target.closest("[data-dashboard-owned-item-id]");
      if (!row) return;
      const ownedItemId = Number(row.getAttribute("data-dashboard-owned-item-id") || 0);
      if (e.shiftKey) {
        selectDashboardSlotRangeToId(ownedItemId);
        return;
      }
      selectDashboardSingleSlotItemById(ownedItemId);
    });
    $("homeDashWorkbenchList").addEventListener("pointerdown", (e) => {
      if (isShellReadOnly()) return;
      if (e.target.closest("[data-dashboard-selectable-id]")) return;
      startDashboardPointerSelection(e, "WORKBENCH");
    });
    $("homeDashWorkbenchList").addEventListener("click", (e) => {
      if (shouldSuppressDashboardSelectionClick()) {
        e.preventDefault();
        e.stopPropagation();
        return;
      }
      const locateBtn = e.target.closest("[data-dashboard-workbench-open-slot]");
      if (locateBtn) {
        e.stopPropagation();
        const slotId = Number(locateBtn.getAttribute("data-dashboard-workbench-open-slot") || 0);
        const slotCode = String(locateBtn.getAttribute("data-dashboard-workbench-open-slot-code") || "");
        openCabinetLocationAction(slotId, slotCode, "", "", "");
        return;
      }
      if (isShellReadOnly()) return;
      const check = e.target.closest("[data-dashboard-workbench-select]");
      if (check) {
        e.stopPropagation();
        const ownedItemId = Number(check.getAttribute("data-dashboard-workbench-select") || 0);
        const source = String(check.getAttribute("data-dashboard-workbench-source") || "").trim().toUpperCase();
        if (e.shiftKey) {
          selectDashboardWorkbenchRangeToId(ownedItemId, source);
          return;
        }
        toggleDashboardWorkbenchSelectionById(ownedItemId, source);
        return;
      }
      const editBtn = e.target.closest("[data-dashboard-workbench-edit]");
      if (editBtn) {
        e.stopPropagation();
        const ownedItemId = Number(editBtn.getAttribute("data-dashboard-workbench-edit") || 0);
        const source = String(editBtn.getAttribute("data-dashboard-workbench-source") || "").trim().toUpperCase();
        if (ownedItemId > 0) {
          void openDashboardOwnedItemDetailManage(ownedItemId, source);
        }
        return;
      }
      const row = e.target.closest("[data-dashboard-workbench-owned-item-id]");
      if (!row) return;
      const ownedItemId = Number(row.getAttribute("data-dashboard-workbench-owned-item-id") || 0);
      const source = String(row.getAttribute("data-dashboard-workbench-source") || "").trim().toUpperCase();
      if (e.shiftKey) {
        selectDashboardWorkbenchRangeToId(ownedItemId, source);
        return;
      }
      selectDashboardSingleWorkbenchItemById(ownedItemId, source);
    });
    $("homeDashWorkbenchList").addEventListener("dragstart", (e) => {
      if (isShellReadOnly()) return;
      const row = e.target.closest("[data-dashboard-workbench-owned-item-id]");
      if (!row) return;
      const ownedItemId = Number(row.getAttribute("data-dashboard-workbench-owned-item-id") || 0);
      const slotCode = String(row.getAttribute("data-dashboard-slot-code") || "").trim();
      const sizeGroup = String(row.getAttribute("data-dashboard-size-group") || "").trim();
      const itemTitle = String(row.getAttribute("data-dashboard-item-title") || "").trim();
      if (!ownedItemId) return;
      const selectedIds = Array.from(getDashboardWorkbenchSelectedIds())
        .map((value) => Number(value || 0))
        .filter((value) => value > 0);
      if (!selectedIds.includes(ownedItemId)) {
        selectedIds.length = 0;
        selectedIds.push(ownedItemId);
      }
      dashboardDraggedOwnedItemId = ownedItemId;
      dashboardDraggedSelectionIds = selectedIds;
      dashboardDraggedSlotCode = slotCode;
      dashboardDraggedSizeGroup = sizeGroup;
      dashboardDraggedTitle = itemTitle;
      clearDashboardDragHints();
      row.classList.add("dragging");
      if (e.dataTransfer) {
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", String(ownedItemId));
        e.dataTransfer.setData("text/x-dashboard-selection-ids", JSON.stringify(selectedIds));
        e.dataTransfer.setData("text/x-dashboard-drag-source", "WORKBENCH");
        if (slotCode) e.dataTransfer.setData("text/x-dashboard-slot-code", slotCode);
        if (sizeGroup) e.dataTransfer.setData("text/x-dashboard-size-group", sizeGroup);
      }
    });
    $("homeDashWorkbenchList").addEventListener("dragend", () => {
      resetDashboardDragState();
    });
    $("homeDashSlotSelectAllBtn").addEventListener("click", () => {
      resetDashboardUnassignedSelection();
      resetDashboardSearchSelection();
      resetDashboardDragState();
      homeDashboardSlotSelectedIds = new Set((Array.isArray(homeDashboardSlotItems) ? homeDashboardSlotItems : []).map((row) => Number(row?.id || 0)).filter((id) => id > 0));
      updateDashboardSlotSelectionSnapshot();
      renderDashboardSlotItems(getDashboardSlotRow(homeDashboardSelectedSlotCode));
      renderDashboardWorkbench();
    });
    $("homeDashSlotClearBtn").addEventListener("click", () => {
      if (homeDashboardSlotSelectedIds.size > 0) {
        resetDashboardSlotSelection();
        renderDashboardSlotItems(getDashboardSlotRow(homeDashboardSelectedSlotCode));
        renderDashboardWorkbench();
        return;
      }
      if (!String(homeDashboardSelectedSlotCode || "").trim()) return;
      homeDashboardSelectedSlotCode = null;
      homeDashboardSlotItems = [];
      homeDashboardSlotItemsSlotCode = null;
      resetDashboardSlotPage();
      resetDashboardSlotSelection();
      renderDashboardCabinetDetail();
      renderDashboardWorkbench();
    });
    $("homeDashSlotPagePrevBtn").addEventListener("click", () => {
      if (dashboardSlotUsesShelfScroll()) {
        moveDashboardShelfViewport("PREV");
        return;
      }
      homeDashboardSlotPage = Math.max(0, homeDashboardSlotPage - 1);
      renderDashboardSlotItems(getDashboardSlotRow(homeDashboardSelectedSlotCode));
    });
    $("homeDashSlotViewShelfBtn").addEventListener("click", () => setDashboardSlotViewMode("SHELF"));
    $("homeDashSlotViewThumbBtn").addEventListener("click", () => setDashboardSlotViewMode("THUMB"));
    $("homeDashSlotViewListBtn").addEventListener("click", () => setDashboardSlotViewMode("LIST"));
    $("homeDashSlotMediaFilter").addEventListener("change", () => {
      resetDashboardSlotPage();
      renderDashboardSlotItems(getDashboardSlotRow(homeDashboardSelectedSlotCode));
    });
    // homeDashSlotSortMode removed — sort order is now determined by cabinet_sort_policy
    $("homeDashSlotPageSize")?.addEventListener("change", (e) => {
      homeDashboardSlotPageSizeOverride = String(e.target.value || "").trim();
      resetDashboardSlotPage();
      renderDashboardSlotItems(getDashboardSlotRow(homeDashboardSelectedSlotCode));
    });
    $("homeDashSlotPageNextBtn").addEventListener("click", () => {
      if (dashboardSlotUsesShelfScroll()) {
        moveDashboardShelfViewport("NEXT");
        return;
      }
      homeDashboardSlotPage += 1;
      renderDashboardSlotItems(getDashboardSlotRow(homeDashboardSelectedSlotCode));
    });
    $("homeDashSlotRestoreBtn").addEventListener("click", restoreDashboardSelectedPreviousLocation);
    $("homeDashSlotMoveModeBtn").addEventListener("click", startDashboardClickMoveMode);
    $("homeDashSlotMoveCancelBtn").addEventListener("click", () => cancelDashboardClickMoveMode());
    $("homeDashSelectedItemEditBtn").addEventListener("click", openDashboardSelectedItemForEdit);
    $("homeDashSelectedSortArtistSaveBtn").addEventListener("click", saveDashboardSelectedSortArtistName);
    $("homeDashSelectedSortArtistName").addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      e.preventDefault();
      saveDashboardSelectedSortArtistName();
    });
    $("homeDashWorkbenchSortArtistSaveBtn").addEventListener("click", saveDashboardSelectedSortArtistName);
    $("homeDashWorkbenchSortArtistName").addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      e.preventDefault();
      saveDashboardSelectedSortArtistName();
    });
    $("homeDashWorkbenchEditBtn").addEventListener("click", openDashboardSelectedItemForEdit);
    $("homeDashWorkbenchMoveModeBtn").addEventListener("click", startDashboardClickMoveMode);
    $("homeDashWorkbenchMoveCancelBtn").addEventListener("click", () => cancelDashboardClickMoveMode());
    $("homeDashModeUnassignedBtn").addEventListener("click", () => setDashboardWorkbenchMode("UNASSIGNED"));
    $("homeDashModeSearchBtn").addEventListener("click", () => setDashboardWorkbenchMode("SEARCH"));
    $("homeDashWorkbenchSelectAllBtn").addEventListener("click", () => {
      resetDashboardDragState();
      if (homeDashboardWorkbenchMode === "SEARCH") {
        resetDashboardSlotSelection();
        resetDashboardUnassignedSelection();
        homeDashboardSearchSelectedIds = new Set(getDashboardWorkbenchRows().map((row) => Number(row?.id || 0)).filter((id) => id > 0));
      } else {
        resetDashboardSlotSelection();
        resetDashboardSearchSelection();
        homeDashboardUnassignedSelectedIds = new Set(getDashboardWorkbenchRows().map((row) => Number(row?.id || 0)).filter((id) => id > 0));
      }
      renderDashboardSlotItems(getDashboardSlotRow(homeDashboardSelectedSlotCode));
      renderDashboardWorkbench();
    });
    $("homeDashWorkbenchClearBtn").addEventListener("click", () => {
      if (homeDashboardWorkbenchMode === "SEARCH") {
        resetDashboardSearchSelection();
      } else {
        resetDashboardUnassignedSelection();
      }
      renderDashboardWorkbench();
    });
    $("homeDashWorkbenchPagePrevBtn").addEventListener("click", () => {
      if (dashboardSlotUsesShelfScroll()) {
        moveDashboardWorkbenchViewport("PREV");
        return;
      }
      homeDashboardWorkbenchPage = Math.max(0, homeDashboardWorkbenchPage - 1);
      renderDashboardWorkbench();
    });
    $("homeDashWorkbenchPageNextBtn").addEventListener("click", () => {
      if (dashboardSlotUsesShelfScroll()) {
        moveDashboardWorkbenchViewport("NEXT");
        return;
      }
      homeDashboardWorkbenchPage += 1;
      renderDashboardWorkbench();
    });
    $("homeDashWorkbenchRecommendBtn").addEventListener("click", loadDashboardWorkbenchRecommendations);
    $("homeDashSearchRunBtn").addEventListener("click", loadDashboardSearchItems);
    $("homeDashSearchArtist").addEventListener("input", saveDashboardWorkbenchPreferences);
    $("homeDashSearchTitle").addEventListener("input", saveDashboardWorkbenchPreferences);
    $("homeDashSearchCatalogNo").addEventListener("input", saveDashboardWorkbenchPreferences);
    $("homeDashSearchBarcode").addEventListener("input", saveDashboardWorkbenchPreferences);
    $("homeDashSearchArtist").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); loadDashboardSearchItems(); }});
    $("homeDashSearchTitle").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); loadDashboardSearchItems(); }});
    $("homeDashSearchCatalogNo").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); loadDashboardSearchItems(); }});
    $("homeDashSearchBarcode").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); loadDashboardSearchItems(); }});
    $("homeDashMediaFilter").addEventListener("change", () => {
      saveDashboardWorkbenchPreferences();
      resetDashboardWorkbenchPage();
      if (homeDashboardWorkbenchMode === "SEARCH") {
        loadDashboardSearchItems({ silent: true });
        return;
      }
      loadDashboardUnassignedItems({ silent: true });
    });
    $("homeDashSignatureMode").addEventListener("change", () => {
      saveDashboardWorkbenchPreferences();
      resetDashboardWorkbenchPage();
      if (homeDashboardWorkbenchMode === "SEARCH") {
        loadDashboardSearchItems({ silent: true });
        return;
      }
      loadDashboardUnassignedItems({ silent: true });
    });
    $("homeDashWorkbenchSortMode").addEventListener("change", () => {
      saveDashboardWorkbenchPreferences();
      resetDashboardWorkbenchPage();
      renderDashboardWorkbench();
    });
    $("homeDashSortWarningOnly")?.addEventListener("change", () => {
      saveDashboardWorkbenchPreferences();
      resetDashboardWorkbenchPage();
      renderDashboardWorkbench();
    });
    $("homeDashWorkbenchDomainFilter")?.querySelector("select")?.addEventListener("change", () => {
      saveDashboardWorkbenchPreferences();
      resetDashboardWorkbenchPage();
      renderDashboardWorkbench();
    });
    $("homeOpenDashboardSlotBtn").addEventListener("click", openDashboardForCurrentLocation);
    $("homeRestorePreviousSlotBtn").addEventListener("click", restoreHomePreviousLocation);
    document.addEventListener("pointermove", (e) => {
      if (!dashboardPointerSelectionState) return;
      if (Number(dashboardPointerSelectionState.pointerId || 0) !== Number(e.pointerId || 0)) return;
      updateDashboardPointerSelection(e.clientX, e.clientY);
    });
    document.addEventListener("pointerup", (e) => {
      if (!dashboardPointerSelectionState) return;
      if (Number(dashboardPointerSelectionState.pointerId || 0) !== Number(e.pointerId || 0)) return;
      finishDashboardPointerSelection();
    });
    document.addEventListener("pointercancel", (e) => {
      if (!dashboardPointerSelectionState) return;
      if (Number(dashboardPointerSelectionState.pointerId || 0) !== Number(e.pointerId || 0)) return;
      finishDashboardPointerSelection();
    });
    $("homeDashSlotItems").addEventListener("scroll", () => {
      if (!dashboardSlotUsesShelfScroll()) return;
      const root = $("homeDashSlotItems");
      if (!root) return;
      homeDashboardSlotShelfScrollLeft = root.scrollLeft;
      updateDashboardSlotPageControls({
        total: Array.isArray(homeDashboardSlotItems) ? homeDashboardSlotItems.length : 0,
      });
    });
    $("homeDashWorkbenchList").addEventListener("scroll", () => {
      if (!dashboardSlotUsesShelfScroll()) return;
      const root = $("homeDashWorkbenchList");
      if (!root) return;
      homeDashboardWorkbenchShelfScrollLeft = root.scrollLeft;
      updateDashboardWorkbenchPageControls({
        total: getDashboardWorkbenchRows().length,
      });
    });
    $("homeDashSlotItems").addEventListener("dragstart", (e) => {
      const row = e.target.closest("[data-dashboard-owned-item-id]");
      if (!row) return;
      const ownedItemId = Number(row.getAttribute("data-dashboard-owned-item-id") || 0);
      const slotCode = String(row.getAttribute("data-dashboard-slot-code") || "").trim();
      const sizeGroup = String(row.getAttribute("data-dashboard-size-group") || "").trim();
      const itemTitle = String(row.getAttribute("data-dashboard-item-title") || "").trim();
      if (!ownedItemId || !slotCode) return;
      const selectedIds = Array.from(homeDashboardSlotSelectedIds)
        .map((value) => Number(value || 0))
        .filter((value) => value > 0);
      if (!selectedIds.includes(ownedItemId)) {
        selectedIds.length = 0;
        selectedIds.push(ownedItemId);
      }
      dashboardDraggedOwnedItemId = ownedItemId;
      dashboardDraggedSelectionIds = selectedIds;
      dashboardDraggedSlotCode = slotCode;
      dashboardDraggedSizeGroup = sizeGroup;
      dashboardDraggedTitle = itemTitle;
      clearDashboardDragHints();
      row.classList.add("dragging");
      if (e.dataTransfer) {
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", String(ownedItemId));
        e.dataTransfer.setData("text/x-dashboard-selection-ids", JSON.stringify(selectedIds));
        e.dataTransfer.setData("text/x-dashboard-slot-code", slotCode);
        if (sizeGroup) e.dataTransfer.setData("text/x-dashboard-size-group", sizeGroup);
      }
    });
    $("homeDashSlotItems").addEventListener("dragend", () => {
      resetDashboardDragState();
    });
    $("homeDashSlotItems").addEventListener("dragover", (e) => {
      const currentSlotCode = String(homeDashboardSelectedSlotCode || "").trim();
      const currentSlotRow = getDashboardSlotRow(currentSlotCode);
      const selectedRows = getDashboardDraggedRows(e);
      const row = e.target.closest("[data-dashboard-owned-item-id]");
      const sourceOwnedItemId = getDashboardDraggedOwnedItemId(e);
      const sourceSlotCode = selectedRows.length === 1
        ? String(selectedRows[0]?.slot_code || "").trim()
        : getDashboardDraggedSlotCode(e);
      if (currentSlotCode && (selectedRows.length > 1 || !sourceSlotCode || sourceSlotCode !== currentSlotCode)) {
        if (!selectedRows.length && !sourceOwnedItemId) return;
        e.preventDefault();
        clearDashboardDragHints();
        $("homeDashSlotItems")?.classList.add("drop-ready");
        if (e.dataTransfer) e.dataTransfer.dropEffect = "move";
        return;
      }
      if (!row || !sourceOwnedItemId) return;
      if (
        currentSlotCode
        && sourceSlotCode === currentSlotCode
        && dashboardSlotAllowsManualOrder(currentSlotRow) === false
      ) return;
      const targetOwnedItemId = Number(row.getAttribute("data-dashboard-owned-item-id") || 0);
      if (!targetOwnedItemId || targetOwnedItemId === sourceOwnedItemId) return;
      e.preventDefault();
      clearDashboardDragHints();
      const rect = row.getBoundingClientRect();
      const position = (e.clientY - rect.top) < (rect.height / 2) ? "BEFORE" : "AFTER";
      row.classList.add(position === "BEFORE" ? "drag-before" : "drag-after");
      if (e.dataTransfer) e.dataTransfer.dropEffect = "move";
    });
    $("homeDashSlotItems").addEventListener("dragleave", (e) => {
      const row = e.target.closest("[data-dashboard-owned-item-id]");
      if (!row) return;
      row.classList.remove("drag-before", "drag-after");
    });
    $("homeDashSlotItems").addEventListener("drop", async (e) => {
      const selectedRows = getDashboardDraggedRows(e);
      const currentSlotCode = String(homeDashboardSelectedSlotCode || "").trim();
      const currentSlotRow = getDashboardSlotRow(currentSlotCode);
      const row = e.target.closest("[data-dashboard-owned-item-id]");
      const sourceOwnedItemId = getDashboardDraggedOwnedItemId(e);
      const sourceSlotCode = selectedRows.length === 1
        ? String(selectedRows[0]?.slot_code || "").trim()
        : getDashboardDraggedSlotCode(e);
      if (
        currentSlotCode
        && (selectedRows.length > 1 || !sourceSlotCode || sourceSlotCode !== currentSlotCode)
        && (selectedRows.length || sourceOwnedItemId)
      ) {
        e.preventDefault();
        if (selectedRows.length > 1) {
          await moveDashboardOwnedItemsToSlot(selectedRows, currentSlotCode);
          resetDashboardDragState();
          return;
        }
        const draggedOwnedItemId = selectedRows.length === 1
          ? Number(selectedRows[0]?.id || 0)
          : sourceOwnedItemId;
        if (!draggedOwnedItemId) {
          resetDashboardDragState();
          return;
        }
        await moveDashboardOwnedItemToSlot(draggedOwnedItemId, currentSlotCode);
        return;
      }
      if (!row || !sourceOwnedItemId) return;
      if (
        currentSlotCode
        && sourceSlotCode === currentSlotCode
        && dashboardSlotAllowsManualOrder(currentSlotRow) === false
      ) {
        setStatus("homeDashboardStatus", "err", t("dashboard.order.locked_artist_slot"));
        resetDashboardDragState();
        return;
      }
      e.preventDefault();
      const targetOwnedItemId = Number(row.getAttribute("data-dashboard-owned-item-id") || 0);
      if (!sourceOwnedItemId || !targetOwnedItemId || sourceOwnedItemId === targetOwnedItemId) {
        resetDashboardDragState();
        return;
      }
      const rect = row.getBoundingClientRect();
      const position = (e.clientY - rect.top) < (rect.height / 2) ? "BEFORE" : "AFTER";
      await moveDashboardOwnedItemRelative(sourceOwnedItemId, targetOwnedItemId, position);
    });
    $("opsSlotTableBody").addEventListener("click", (e) => {
      const row = e.target.closest("tr[data-slot-id]");
      if (!row) return;
      const slotId = Number(row.getAttribute("data-slot-id") || 0);
      const slot = storageSlotCache.find((item) => Number(item.id) === slotId);
      if (slot) {
        fillOpsSlotForm(slot);
        setStatus("opsSlotStatus", "ok", t("ops.slot.status.selected", { slot: storageSlotDisplayLabel(slot) }));
      }
    });
    $("opsCabinetTableBody").addEventListener("click", (e) => {
      const row = e.target.closest("tr[data-cabinet-name]");
      if (!row) return;
      const cabinetName = decodeURIComponent(row.getAttribute("data-cabinet-name") || "");
      if (!cabinetName) return;
      const summary = getOpsCabinetSummary(cabinetName);
      fillOpsCabinetForm(summary);
      setStatus("opsCabinetStatus", "ok", t("ops.cabinet.status.selected", { cabinet: cabinetName }));
    });
    $("opsAuthTableBody").addEventListener("click", (e) => {
      const rowEl = e.target.closest("tr[data-ops-auth-username]");
      if (!rowEl) return;
      const username = decodeURIComponent(rowEl.getAttribute("data-ops-auth-username") || "");
      if (!username) return;
      const row = (Array.isArray(opsAuthItems) ? opsAuthItems : []).find((entry) => String(entry.username || "").trim() === username);
      if (!row) return;
      fillOpsAuthForm(row);
      if (!row.editable) {
        setStatus("opsAuthStatus", "ok", t("ops.account.status.default_readonly", { username }));
      }
    });
    $("homeMasterAddResults").addEventListener("click", async (e) => {
      const editBtn = e.target.closest(".homeMasterVariantEditBtn");
      if (editBtn) {
        const ownedItemId = Number(editBtn.getAttribute("data-owned-id") || 0);
        const masterId = Number(homeSelectedMasterId || 0);
        if (ownedItemId > 0) {
          await openMediaSearchDetailManage(masterId, ownedItemId);
        }
        return;
      }

      const registerBtn = e.target.closest(".homeMasterVariantRegisterBtn");
      if (registerBtn) {
        const externalId = String(registerBtn.getAttribute("data-external-id") || "").trim();
        await registerHomeMasterVariant(externalId);
      }
    });
    $("homeMetaResults").addEventListener("click", (e) => {
      const addBtn = e.target.closest(".home-meta-add-linked-btn");
      if (!addBtn) return;
      const idx = Number(addBtn.getAttribute("data-idx") || -1);
      if (!Number.isInteger(idx) || idx < 0 || idx >= homeMetaCandidates.length) return;
      const candidate = homeMetaCandidates[idx];
      addLinkedItemFromHomeMetaCandidate(candidate);
    });
    $("sourceWorkbenchList").addEventListener("click", (e) => {
      const refindBtn = e.target.closest("[data-workbench-refind]");
      if (refindBtn) {
        const rowIndex = Number(refindBtn.getAttribute("data-workbench-refind") || -1);
        if (!Number.isInteger(rowIndex) || rowIndex < 0) return;
        syncSourceWorkbenchSearchInputs(rowIndex);
        loadSourceWorkbenchCandidatesForRow(rowIndex, { force: true, forceTextSearch: true });
        return;
      }

      const resetBtn = e.target.closest("[data-workbench-reset]");
      if (resetBtn) {
        const rowIndex = Number(resetBtn.getAttribute("data-workbench-reset") || -1);
        const entry = sourceWorkbenchRows[rowIndex];
        if (!entry) return;
        const row = entry.item || {};
        entry.searchArtistName = String(row.artist_or_brand || row.linked_artist_name || "").trim();
        entry.searchItemName = String(sourceWorkbenchCandidateTitle(row) || "").trim();
        renderSourceWorkbenchList();
        setStatus("sourceWorkbenchStatus", "ok", t("media.source.status.search_reset"));
        return;
      }

      const selectBtn = e.target.closest("[data-workbench-select]");
      if (selectBtn) {
        const raw = String(selectBtn.getAttribute("data-workbench-select") || "");
        const [rowIndexText, candidateIndexText] = raw.split(":");
        const rowIndex = Number(rowIndexText);
        const candidateIndex = Number(candidateIndexText);
        const entry = sourceWorkbenchRows[rowIndex];
        if (!entry) return;
        if (!Array.isArray(entry.candidates) || !entry.candidates[candidateIndex]) return;
        entry.selectedIdx = candidateIndex;
        entry.selectionMode = "MANUAL";
        renderSourceWorkbenchList();
        return;
      }

      const findBtn = e.target.closest("[data-workbench-find]");
      if (findBtn) {
        const rowIndex = Number(findBtn.getAttribute("data-workbench-find") || -1);
        if (!Number.isInteger(rowIndex) || rowIndex < 0) return;
        syncSourceWorkbenchSearchInputs(rowIndex);
        loadSourceWorkbenchCandidatesForRow(rowIndex, { force: true });
        return;
      }

      const applyBtn = e.target.closest("[data-workbench-apply]");
      if (applyBtn) {
        const rowIndex = Number(applyBtn.getAttribute("data-workbench-apply") || -1);
        if (!Number.isInteger(rowIndex) || rowIndex < 0) return;
        applySingleSourceWorkbenchRow(rowIndex);
      }
    });
    $("sourceWorkbenchList").addEventListener("input", (e) => {
      const artistInput = e.target.closest("[data-workbench-artist-input]");
      if (artistInput) {
        const rowIndex = Number(artistInput.getAttribute("data-workbench-artist-input") || -1);
        const entry = sourceWorkbenchRows[rowIndex];
        if (!entry) return;
        entry.searchArtistName = String(artistInput.value || "");
        return;
      }

      const titleInput = e.target.closest("[data-workbench-title-input]");
      if (titleInput) {
        const rowIndex = Number(titleInput.getAttribute("data-workbench-title-input") || -1);
        const entry = sourceWorkbenchRows[rowIndex];
        if (!entry) return;
        entry.searchItemName = String(titleInput.value || "");
      }
    });
    $("sourceWorkbenchQueue").addEventListener("click", (e) => {
      const openBtn = e.target.closest("[data-source-queue-open]");
      if (openBtn) {
        const ownedItemId = Number(openBtn.getAttribute("data-source-queue-open") || 0);
        const entry = (Array.isArray(sourceWorkbenchQueue) ? sourceWorkbenchQueue : []).find((row) => Number(row?.owned_item_id || 0) === ownedItemId) || null;
        const masterId = Number(entry?.linked_album_master_id || entry?.album_master_id || 0);
        if (ownedItemId > 0) void openMediaSearchDetailManage(masterId, ownedItemId);
        return;
      }

      const removeBtn = e.target.closest("[data-source-queue-remove]");
      if (removeBtn) {
        const idx = Number(removeBtn.getAttribute("data-source-queue-remove") || -1);
        if (!Number.isInteger(idx) || idx < 0 || idx >= sourceWorkbenchQueue.length) return;
        sourceWorkbenchQueue = sourceWorkbenchQueue.filter((_, queueIndex) => queueIndex !== idx);
        saveSourceWorkbenchQueue();
        renderSourceWorkbenchQueue();
      }
    });
    $("sourceWorkbenchDiffReview").addEventListener("click", (e) => {
      const closeBtn = e.target.closest("[data-source-workbench-diff-close]");
      if (closeBtn || e.target.id === "sourceWorkbenchDiffReview") {
        closeSourceWorkbenchDiffReview();
      }
    });
    $("sourceWorkbenchDiffReviewList").addEventListener("input", (e) => {
      const toggle = e.target.closest("[data-source-workbench-diff-toggle]");
      if (!toggle) return;
      const raw = String(toggle.getAttribute("data-source-workbench-diff-toggle") || "");
      const [itemIndexText, fieldKey] = raw.split(":");
      const itemIndex = Number(itemIndexText);
      if (!Number.isInteger(itemIndex) || itemIndex < 0 || !fieldKey) return;
      updateSourceWorkbenchDiffFieldSelection(itemIndex, fieldKey, Boolean(toggle.checked));
    });
    const handleHomeRelatedListClick = (e) => {
      if (e.target.closest("#homeMasterInlineEditorHost")) return;
      const metaSyncBtn = e.target.closest("[data-home-meta-sync]");
      if (metaSyncBtn) {
        e.preventDefault();
        e.stopPropagation();
        const ownedItemId = Number(metaSyncBtn.getAttribute("data-home-meta-sync") || 0);
        if (ownedItemId > 0) {
          executeMetadataSyncAction(ownedItemId, metaSyncBtn, async () => {
            const masterId = Number(homeSelectedMasterId || homeMasterInfo?.album_master_id || 0);
            const selectedItemId = Number(homeSelectedItemId || 0);
            await openMediaSearchDetailManage(masterId, selectedItemId).catch(() => {});
            await refreshHomeSearchResultCard(masterId).catch(() => {});
          });
        }
        return;
      }
      const goodsManageBtn = e.target.closest(".home-master-collectible-manage-btn");
      if (goodsManageBtn) {
        const goodsItemId = Number(goodsManageBtn.getAttribute("data-home-related-goods-id") || 0);
        if (goodsItemId > 0) {
          openAdminConsole("collectibles");
          openGoodsItemForManage(goodsItemId);
        }
        return;
      }
      const dupBtn = e.target.closest(".home-related-dup-btn");
      if (dupBtn) {
        const ownedItemId = Number(dupBtn.getAttribute("data-owned-id") || 0);
        const groupItem = dupBtn.closest(".home-related-item");
        const countInput = groupItem ? groupItem.querySelector(".home-related-dup-count") : null;
        let count = Number(countInput?.value || 1);
        if (!Number.isFinite(count)) count = 1;
        count = Math.max(1, Math.min(100, Math.floor(count)));
        if (countInput) countInput.value = String(count);
        duplicateHomeRelatedItem(ownedItemId, count);
        return;
      }
      const delBtn = e.target.closest(".home-related-del-btn");
      if (delBtn) {
        const ownedItemId = Number(delBtn.getAttribute("data-owned-id") || 0);
        deleteHomeRelatedItem(ownedItemId);
        return;
      }
      if (e.target.closest(".home-related-dup-count")) return;
      const item = e.target.closest(".home-related-item");
      if (!item) return;
      const ownedItemId = Number(item.getAttribute("data-owned-id") || 0);
      const isSameItem = ownedItemId > 0 && ownedItemId === Number(homeSelectedItemId || 0);
      if (isSameItem) {
        homeInlineEditorCollapsed = !homeInlineEditorCollapsed;
        syncHomeMasterInlineEditor();
        renderHomeSearchResults(homeSearchResults);
        return;
      }
      openHomeOwnedItemFromManageContext(ownedItemId);
    };
    $("homeMasterRelatedList").addEventListener("click", handleHomeRelatedListClick);
    $("homeMasterGoodsList").addEventListener("click", handleHomeRelatedListClick);
    $("homeProductLinkedGoodsList")?.addEventListener("click", handleHomeRelatedListClick);
    $("homeMasterInlineEditorHost").addEventListener("click", (e) => {
      e.stopPropagation();
    });
    $("homeMasterInlineEditorHost").addEventListener("mousedown", (e) => {
      e.stopPropagation();
    });

    $("albumSearchBtn").addEventListener("click", searchOwnedAlbums);
    $("albumSearchQuery").addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        searchOwnedAlbums();
      }
    });
    $("shelfPrevBtn").addEventListener("click", () => moveShelf(-1));
    $("shelfNextBtn").addEventListener("click", () => moveShelf(1));
    $("shelfMoveLeftBtn").addEventListener("click", () => moveShelfPosition(-1));
    $("shelfMoveRightBtn").addEventListener("click", () => moveShelfPosition(1));
    $("albumSearchResults").addEventListener("click", (e) => {
      const row = e.target.closest(".result-item.album-result");
      if (!row) return;
      const ownedItemId = Number(row.getAttribute("data-owned-id") || 0);
      openShelfWindow(ownedItemId);
    });
    $("shelfRelatedList").addEventListener("click", (e) => {
      const row = e.target.closest(".result-item.album-result");
      if (!row) return;
      const ownedItemId = Number(row.getAttribute("data-owned-id") || 0);
      openShelfWindow(ownedItemId);
    });

    $("barcodeInput").addEventListener("keydown", (e) => {
      if (e.isComposing || e.key !== "Enter") return;
      e.preventDefault();
      pulseAdminBarcodeInput();
      submitAdminBarcodeIntake();
    });
    document.addEventListener("keydown", handleGlobalBarcodeScannerKeydown, true);
    $("barcodeResults").addEventListener("input", (e) => {
      const artistInput = e.target.closest("[data-register-lookup-artist]");
      if (!artistInput) return;
      const idx = Number(artistInput.getAttribute("data-register-lookup-artist") || -1);
      const candidate = registerLookupCandidates[idx];
      if (!candidate) return;
      candidate.artist_or_brand = String(artistInput.value || "").trim() || null;
    });
    $("barcodeResults").addEventListener("change", (e) => {
      const domainSel = e.target.closest("[data-register-lookup-domain]");
      if (domainSel) {
        const idx = Number(domainSel.getAttribute("data-register-lookup-domain") || -1);
        const candidate = registerLookupCandidates[idx];
        if (!candidate) return;
        const newDc = String(domainSel.value || "").trim().toUpperCase() || null;
        candidate.domain_code = newDc;
        domainSel.className = `ingest-domain-select operator-domain-badge${newDc ? ` domain-${newDc}` : ""}`;
      }
    });
    $("barcodeResults").addEventListener("click", (e) => {
      const saveBtn = e.target.closest("[data-register-lookup-save]");
      if (saveBtn) {
        e.preventDefault();
        queueRegisterLookupCandidate(Number(saveBtn.getAttribute("data-register-lookup-save") || -1));
        return;
      }
      if (e.target.closest("button, select, option, input, label, a")) return;
      const row = e.target.closest("[data-register-lookup-index]");
      if (!row) return;
      selectRegisterLookupCandidate(Number(row.getAttribute("data-register-lookup-index") || -1), {
        focus: true,
        preventScroll: true,
        scroll: false,
      });
    });
    $("barcodeResults").addEventListener("keydown", (e) => {
      if (e.isComposing || !["Enter", " "].includes(e.key)) return;
      const row = e.target.closest("[data-register-lookup-index]");
      if (!row) return;
      e.preventDefault();
      selectRegisterLookupCandidate(Number(row.getAttribute("data-register-lookup-index") || -1), {
        focus: true,
        preventScroll: true,
        scroll: false,
      });
    });
    $("adminBarcodePlacementSummary").addEventListener("click", (e) => {
      const placementBtn = e.target.closest("[data-admin-barcode-placement-slot-id]");
      if (!placementBtn || !selectedCandidate) return;
      syncAdminBarcodePlacementSelection(selectedCandidate,
        Number(placementBtn.getAttribute("data-admin-barcode-placement-slot-id") || 0),
        Number(placementBtn.getAttribute("data-admin-barcode-placement-rank") || 0));
    });
    $("queryArtist").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); submitAdminRegisterLookupSearch(); } });
    $("queryTitle").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); submitAdminRegisterLookupSearch(); } });
    $("queryCatalog").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); submitAdminRegisterLookupSearch(); } });
    $("querySourceRef").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); submitAdminRegisterLookupSearch(); } });
    $("registerLookupSearchBtn").addEventListener("click", submitAdminRegisterLookupSearch);
    $("createOwnedBtn").addEventListener("click", createOwnedItem);
    $("csvUploadBtn").addEventListener("click", uploadCsv);
    $("queueLoadBtn").addEventListener("click", loadReviewQueue);
    $("ownedLoadBtn").addEventListener("click", loadOwnedItems);
    $("masterSearchBtn").addEventListener("click", searchAlbumMasters);
    $("masterVariantsBtn").addEventListener("click", () => loadMasterVariants({ resetPage: true }));
    $("masterVariantResetBtn").addEventListener("click", () => {
      resetMasterVariantPager({ clearInputs: true });
      loadMasterVariants({ resetPage: true });
    });
    $("masterVariantPrevBtn").addEventListener("click", () => {
      if (masterVariantPage <= 1) return;
      masterVariantPage -= 1;
      loadMasterVariants();
    });
    $("masterVariantNextBtn").addEventListener("click", () => {
      if (!masterVariantHasNext) return;
      masterVariantPage += 1;
      loadMasterVariants();
    });
    $("masterVariantCatalogNo").addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      e.preventDefault();
      loadMasterVariants({ resetPage: true });
    });
    $("masterVariantBarcode").addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      e.preventDefault();
      loadMasterVariants({ resetPage: true });
    });
    $("masterVariantSelectAllBtn").addEventListener("click", () => markMasterVariantSelection("ALL"));
    $("masterVariantSelectMissingBtn").addEventListener("click", () => markMasterVariantSelection("MISSING"));
    $("masterVariantClearBtn").addEventListener("click", () => markMasterVariantSelection("NONE"));
    $("masterImportVariantsBtn").addEventListener("click", importMasterVariants);
    $("masterOwnedLoadBtn").addEventListener("click", loadMasterOwnedItems);
    $("bindMasterBtn").addEventListener("click", bindAlbumMaster);
    $("masterMergeSearchBtn").addEventListener("click", searchInternalAlbumMastersForMerge);
    $("masterMergeClearBtn").addEventListener("click", clearInternalAlbumMasterMergeSearch);
    $("masterMergeQueueClearBtn").addEventListener("click", clearInternalAlbumMasterMergeQueue);
    $("masterMergeRunBtn").addEventListener("click", runInternalAlbumMasterMerge);
    $("masterMergeQuery").addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      e.preventDefault();
      searchInternalAlbumMastersForMerge();
    });
    $("masterMergeBody").addEventListener("click", (e) => {
      const addBtn = e.target.closest("[data-master-merge-add-id]");
      if (!addBtn) return;
      const rowId = normalizeMasterMergeId(addBtn.getAttribute("data-master-merge-add-id"));
      const row = masterMergeSearchResults.find((item) => normalizeMasterMergeId(item?.id) === rowId);
      if (!row) return;
      appendMasterMergeQueueItems([row], { preferBaseId: masterMergeBaseId || rowId });
    });
    $("masterMergeQueueBody").addEventListener("click", (e) => {
      const removeBtn = e.target.closest("[data-master-merge-remove-id]");
      if (!removeBtn) return;
      const rowId = normalizeMasterMergeId(removeBtn.getAttribute("data-master-merge-remove-id"));
      masterMergeQueueItems = masterMergeQueueItems.filter((row) => normalizeMasterMergeId(row?.id) !== rowId);
      if (masterMergeBaseId === rowId) masterMergeBaseId = 0;
      renderMasterMergeRows(masterMergeSearchResults);
      renderMasterMergeQueueRows();
    });
    $("masterMergeQueueBody").addEventListener("change", (e) => {
      const baseRadio = e.target.closest("[data-master-merge-base-id]");
      if (baseRadio) {
        const rowId = normalizeMasterMergeId(baseRadio.getAttribute("data-master-merge-base-id"));
        if (rowId > 0 && isQueuedMasterMergeId(rowId)) {
          masterMergeBaseId = rowId;
        }
        renderMasterMergeQueueRows();
      }
    });
    $("registeredMasterMergeSearchBtn").addEventListener("click", searchRegisteredAlbumMastersForMerge);
    $("registeredMasterMergeClearBtn").addEventListener("click", clearRegisteredMasterMergeSearch);
    $("registeredMasterMergeRunBtn").addEventListener("click", runRegisteredAlbumMasterMerge);
    $("registeredMasterMergeQuery").addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      e.preventDefault();
      searchRegisteredAlbumMastersForMerge();
    });
    $("registeredMasterMergeBody").addEventListener("click", (e) => {
      const addBtn = e.target.closest("[data-registered-master-merge-add-id]");
      if (addBtn) {
        const rowId = normalizeRegisteredMasterMergeId(addBtn.getAttribute("data-registered-master-merge-add-id"));
        const row = registeredMasterMergeSearchResults.find((item) => normalizeRegisteredMasterMergeId(item?.id) === rowId);
        if (!row) return;
        addRegisteredMasterMergeTarget(row);
        return;
      }
      const representativeBtn = e.target.closest("[data-registered-master-merge-representative-id]");
      if (!representativeBtn) return;
      const rowId = normalizeRegisteredMasterMergeId(representativeBtn.getAttribute("data-registered-master-merge-representative-id"));
      const row = registeredMasterMergeSearchResults.find((item) => normalizeRegisteredMasterMergeId(item?.id) === rowId);
      if (!row) return;
      setRegisteredMasterMergeRepresentative(row);
    });
    $("registeredMasterMergeRepresentativeBody").addEventListener("click", (e) => {
      const clearBtn = e.target.closest("[data-registered-master-merge-clear-representative]");
      if (!clearBtn) return;
      clearRegisteredMasterMergeRepresentative();
    });
    $("registeredMasterMergeTargetBody").addEventListener("click", (e) => {
      const removeBtn = e.target.closest("[data-registered-master-merge-remove-id]");
      if (!removeBtn) return;
      const rowId = normalizeRegisteredMasterMergeId(removeBtn.getAttribute("data-registered-master-merge-remove-id"));
      removeRegisteredMasterMergeTarget(rowId);
    });
    $("registeredMasterMergeHistoryBody").addEventListener("click", (e) => {
      const rollbackBtn = e.target.closest("[data-registered-master-merge-rollback-id]");
      if (!rollbackBtn) return;
      rollbackLatestRegisteredAlbumMasterMerge();
    });
    syncRegisteredMasterMergeUi();
    loadRegisteredMasterMergeHistory();
    $("masterGroupLoadBtn").addEventListener("click", loadAlbumMasterGroups);
    $("trackMapLoadBtn").addEventListener("click", loadTrackMappings);
    $("trackMapSaveBtn").addEventListener("click", saveTrackMapping);
    $("ownedTableBody").addEventListener("click", (e) => {
      const syncBtn = e.target.closest(".sync-discogs-btn");
      if (syncBtn) {
        const ownedItemId = Number(syncBtn.getAttribute("data-owned-id") || 0);
        syncDiscogsOwned(ownedItemId);
        return;
      }

      const beforeBtn = e.target.closest(".order-before-btn");
      if (beforeBtn) {
        const targetOwnedItemId = Number(beforeBtn.getAttribute("data-target-id") || 0);
        const ownedItemId = Number($("orderMoveItemId").value || 0);
        moveOwnedItemOrder(ownedItemId, targetOwnedItemId, "BEFORE");
        return;
      }

      const afterBtn = e.target.closest(".order-after-btn");
      if (afterBtn) {
        const targetOwnedItemId = Number(afterBtn.getAttribute("data-target-id") || 0);
        const ownedItemId = Number($("orderMoveItemId").value || 0);
        moveOwnedItemOrder(ownedItemId, targetOwnedItemId, "AFTER");
      }
    });

    document.addEventListener("click", (e) => {
      const artistContextToggle = e.target.closest("[data-ops-artist-context-toggle]");
      if (artistContextToggle) {
        e.preventDefault();
        const card = artistContextToggle.closest(".ops-artist-context-card");
        const originalBlock = card?.querySelector("[data-ops-artist-context-original]");
        if (!originalBlock) return;
        const willOpen = originalBlock.hasAttribute("hidden");
        if (willOpen) {
          originalBlock.removeAttribute("hidden");
        } else {
          originalBlock.setAttribute("hidden", "");
        }
        artistContextToggle.textContent = willOpen
          ? String(artistContextToggle.getAttribute("data-hide-label") || "")
          : String(artistContextToggle.getAttribute("data-show-label") || "");
        artistContextToggle.setAttribute("aria-expanded", willOpen ? "true" : "false");
        return;
      }
      const bulkPopover = $("homeDashBulkEditPanel");
      const bulkToggleBtn = $("homeDashSlotBulkBtn");
      if (homeDashSurfacePanel === "BULK") {
        const insideBulkPopover = bulkPopover?.contains(e.target);
        const clickedBulkToggle = bulkToggleBtn?.contains(e.target);
        if (!insideBulkPopover && !clickedBulkToggle) {
          homeDashSurfacePanel = "";
          renderDashboardSurfaceDock();
        }
      }
      const openBtn = e.target.closest("[data-open-image-gallery]");
      if (openBtn) {
        e.preventDefault();
        e.stopPropagation();
        openImageGallery(openBtn.getAttribute("data-open-image-gallery") || "");
        return;
      }
      const thumbBtn = e.target.closest("[data-image-gallery-index]");
      if (thumbBtn) {
        e.preventDefault();
        e.stopPropagation();
        const idx = Number(thumbBtn.getAttribute("data-image-gallery-index") || -1);
        if (Number.isInteger(idx) && idx >= 0 && idx < imageGalleryCurrentItems.length) {
          imageGalleryCurrentIndex = idx;
          renderImageGalleryModal();
        }
        return;
      }
      if (e.target.id === "imageGalleryCloseBtn" || e.target.id === "imageGalleryModal") {
        closeImageGallery();
      }
    });
    document.addEventListener("keydown", (e) => {
      if (dashboardPointerSelectionState?.didMove && e.key === "Escape") {
        e.preventDefault();
        cancelDashboardPointerSelection();
        return;
      }
    });
    document.addEventListener("error", (e) => {
      applyBrokenCoverFallback(e.target);
    }, true);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && $("imageGalleryModal").classList.contains("open")) {
        closeImageGallery();
      }
    });

    // ── Inline entity history (toggle lazy-load) ──────────────────────────

    // 한글 필드명 매핑

    document.addEventListener("toggle", (e) => {
      const details = e.target.closest(".inline-entity-history");
      if (!details || !details.open) return;
      const body = details.querySelector(".inline-entity-history-body");
      if (body && !body.innerHTML.trim()) _loadInlineHistory(details);
      else if (body && body.innerHTML.trim() && !_inlineHistoryCache.has(`${details.dataset.historyType}:${details.dataset.historyId}`)) _loadInlineHistory(details);
    }, true);

    // ── Spotify Match Modal ─────────────────────────────────────────────────
    let _spotifyMatchMasterId = 0;

    // Delegated click handler for spotify match button in exception list
    document.addEventListener("click", async (e) => {
      // Review auto-collect
      const reviewBtn = e.target.closest("[data-ops-exception-review-auto]");
      if (reviewBtn) {
        e.preventDefault();
        const masterId = reviewBtn.getAttribute("data-ops-exception-review-auto");
        reviewBtn.disabled = true;
        reviewBtn.textContent = "수집 중...";
        try {
          const res = await fetchWithRetry(`/album-masters/${masterId}/review/auto`, { method: "POST" });
          const data = await res.json();
          if (data.ok) {
            reviewBtn.textContent = "완료";
            reviewBtn.classList.remove("ghost");
          } else {
            reviewBtn.disabled = false;
            reviewBtn.textContent = data.detail || "실패";
          }
        } catch (err) {
          reviewBtn.disabled = false;
          reviewBtn.textContent = String(err);
        }
        return;
      }
      // Open modal
      const matchBtn = e.target.closest("[data-ops-exception-spotify-match]");
      if (matchBtn) {
        e.preventDefault();
        const masterId = matchBtn.getAttribute("data-ops-exception-spotify-match");
        const title = matchBtn.getAttribute("data-spotify-match-title") || "";
        const artist = matchBtn.getAttribute("data-spotify-match-artist") || "";
        openSpotifyMatchModal(masterId, title, artist);
        return;
      }
      // Close modal
      if (e.target.id === "spotifyMatchCloseBtn" || e.target.id === "spotifyMatchModal") {
        closeSpotifyMatchModal();
        return;
      }
      // Search button
      if (e.target.id === "spotifyMatchSearchBtn") {
        e.preventDefault();
        doSpotifyMatchSearch();
        return;
      }
      // Direct save button
      if (e.target.id === "spotifyMatchDirectSaveBtn") {
        e.preventDefault();
        const raw = String($("spotifyMatchDirectInput")?.value || "").trim();
        // Accept full URI or bare ID
        const albumId = raw.startsWith("spotify:album:")
          ? raw.replace("spotify:album:", "").trim()
          : raw.replace(/^https?:\/\/open\.spotify\.com\/album\//,"").split("?")[0].trim();
        if (!albumId) return;
        saveSpotifyMatch(albumId);
        return;
      }
      // Pick from search results
      const pickBtn = e.target.closest("[data-spotify-match-pick]");
      if (pickBtn) {
        const albumId = pickBtn.getAttribute("data-spotify-match-pick");
        if (albumId) saveSpotifyMatch(albumId);
        return;
      }
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && $("spotifyMatchModal").classList.contains("open")) {
        closeSpotifyMatchModal();
      }
      if (e.key === "Enter" && document.activeElement?.id === "spotifyMatchSearchInput") {
        e.preventDefault();
        doSpotifyMatchSearch();
      }
    });
    // ── End Spotify Match Modal ─────────────────────────────────────────────

    document.addEventListener("click", (e) => {
      const helpTrigger = e.target.closest("[data-page-help-open]");
      if (helpTrigger) {
        e.preventDefault();
        const helpId = String(helpTrigger.getAttribute("data-page-help-open") || "").trim();
        if (!helpId) return;
        if (pageHelpDrawerState.open && pageHelpDrawerState.helpId === helpId) {
          closePageHelpDrawer();
          return;
        }
        openPageHelpDrawer(helpId, helpTrigger);
        return;
      }
      const closeBtn = e.target.closest("[data-page-help-close]");
      if (closeBtn) {
        e.preventDefault();
        closePageHelpDrawer();
        return;
      }
      if (pageHelpDrawerState.open) {
        const overlay = $("pageHelpOverlay");
        if (overlay && e.target === overlay) {
          closePageHelpDrawer();
        }
      }
    });
    document.addEventListener("keydown", (e) => {
      if (pageHelpDrawerState.open) {
        if (e.key === "Escape") {
          e.preventDefault();
          closePageHelpDrawer();
          return;
        }
      }
    });
    $("shellLocaleSelect").addEventListener("change", (e) => {
      applyLocale(e.target.value);
      applyShellNavigation(appAuthSession);
    });
    $("shellThemeToggle").addEventListener("click", toggleAppTheme);
    $("resetFormBtn").addEventListener("click", resetForm);
    $("category").addEventListener("change", () => {
      const c = $("category").value;
      if (MUSIC_CATEGORIES.has(c)) {
        $("formatName").value = c;
      }
      syncMusicVisibility();
    });

    appLocale = loadSavedLocale();
    appTheme = loadSavedTheme();
    const initialShellMode = shellModeFromPath();
    appShellMode = initialShellMode;
    restoreDashboardCabinetSelectionMemory();
    applyAppTheme(appTheme);

    initMediaLabelUi();
    applyFieldHelpTooltips();
    syncMusicVisibility();
    resetQuickForm();
    resetPurchaseImportForm();
    switchMediaMode("search", { remember: false });
    switchSubTab("register", "collect", { remember: false });
    switchSubTab("ops", "cabinet", { remember: false });
    applyShellNavigation(appAuthSession);
    applyRouteSelectedShellMode(initialShellMode);
    clearInternalAlbumMasterMergeWorkbench();
    applyLocale(appLocale);
    syncShelfNavButtons();
    renderShelfTrack();
    renderShelfDetail();
    renderShelfRelatedVersions();
    resetMasterVariantPager({ clearInputs: true });
    clearHomeEditor();
    syncHomeLinkedSourceText();
    syncHomeEditorMusicVisibility();
    mountHomeMasterActionBlocks();
    mountHomeMasterInlineEditor();
    syncHomeMasterInlineEditor();
    syncHomeLinkedGoodsSpecVisibility();
    renderHomePagination();
    loadSourceWorkbenchQueue();
    renderSourceWorkbenchList();
    renderSourceWorkbenchQueue();
    renderOpsExceptionPresetOptions();
    applyDefaultOpsExceptionPreset();
    renderOpsExceptionSummary();
    renderOpsExceptionList();
    syncMasterExceptionBanner();
    renderOperatorLookupResults();
    renderOperatorHomeRecentSections();
    renderPurchaseImportPreview([]);
    renderPurchaseImportQueue([]);
    resetDashboardBulkEditForm();
    syncDashboardSelectionControls();
    loadStorageSlots();
    loadAuthSession(initialShellMode);
    initDashboardWidgets();
    loadHomeDashboard();
    homeSearchOwnedItems({ resetPage: true });
    loadMasterOwnedItems();
    window.addEventListener("popstate", () => {
      const routeShellMode = shellModeFromPath();
      appShellMode = routeShellMode;
      applyRouteSelectedShellMode(routeShellMode);
      // hash 변경 시 아이템 복원
      const hashItemId = _hashItemId();
      if (hashItemId && hashItemId !== Number(homeSelectedItemId || 0)) {
        refreshHomeManageContext(hashItemId, { _fromHash: true });
      }
    });

    // ── hash 라우팅 헬퍼 ──────────────────────────────────────────────────────
    function _hashItemId() {
      const m = window.location.hash.match(/^#item\/(\d+)$/);
      return m ? Number(m[1]) : null;
    }

    // 페이지 로드 시 hash로 직접 이동
    (function _restoreHashRoute() {
      const itemId = _hashItemId();
      if (!itemId) return;
      // 초기화 완료 후 약간의 딜레이를 두고 열기 (탭·세션 초기화 대기)
      setTimeout(() => {
        switchMediaMode("manage");
        refreshHomeManageContext(itemId, { _fromHash: true });
      }, 800);
    })();
