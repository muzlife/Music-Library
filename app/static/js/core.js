const _originalFetch = window.fetch;
    window.fetch = async function(...args) {
      let [resource, config] = args;
      if (!config) config = {};
      const newConfig = { ...config };
      if (!newConfig.credentials) {
        newConfig.credentials = "include";
      }
      return _originalFetch(resource, newConfig);
    };

    const MUSIC_CATEGORIES = new Set(["LP", "CD", "CASSETTE", "8TRACK", "DIGITAL", "REEL_TO_REEL"]);
    const SOURCE_MANAGED_CODES = new Set(["DISCOGS", "MANIADB", "ALADIN"]);
    const DOMAIN_CODES = new Set(["KOREA", "JAPAN", "GREATER_CHINA", "WESTERN", "OTHER_ASIA", "WORLD", "UNKNOWN"]);
    const RELEASE_TYPES = new Set(["ALBUM", "EP", "SINGLE"]);
    const SOURCE_WORKBENCH_QUEUE_KEY = "sourceWorkbenchQueue.v1";
    const DASHBOARD_SLOT_DEFAULT_VIEW_MODE = "SHELF";
    const MEDIA_DISPLAY_LABEL = Object.freeze({
      LP: "Vinyl",
      CD: "CD",
      CASSETTE: "Cassette",
      "8TRACK": "8Track",
      DIGITAL: "Digital",
      REEL_TO_REEL: "Reel To Reel",
    });
    let selectedCandidate = null;
    let registerLookupCandidates = [];
    let registerLookupLocationState = {};
    let registerLookupSaveQueue = [];
    let registerLookupSaveInFlight = false;
    let registerLookupSavingKey = "";
    let registerLookupQueuedKeys = new Set();
    let adminBarcodeConfirmToken = "";
    let adminBarcodeConfirmCandidateKey = "";
    let adminBarcodePlacementToken = 0;
    const adminBarcodePlacementCache = new Map();
    const adminBarcodePlacementPending = new Map();
    const adminBarcodePlacementSelectionByCandidateKey = new Map();
    const BARCODE_SCAN_COOLDOWN_MS = 1200;
    let barcodeSearchInFlight = false;
    let barcodeSearchLastToken = "";
    let barcodeSearchLastTriggeredAt = 0;
    let barcodeSearchPendingToken = "";
    let barcodeSearchPendingValue = "";
    let purchaseImportPreviewItems = [];
    let purchaseImportQueueItems = [];
    let purchaseImportQueueCandidateState = {};
    let purchaseImportFileContent = "";
    let purchaseImportFileContentBase64 = "";
    let purchaseImportFileName = "";
    let masterMergeSearchResults = [];
    let masterMergeQueueItems = [];
    let masterMergeBaseId = 0;
    let masterMergeHasSearched = false;
    let registeredMasterMergeSearchResults = [];
    let registeredMasterMergeTargetItems = [];
    let registeredMasterMergeRepresentativeItem = null;
    let registeredMasterMergeHasSearched = false;
    let registeredMasterMergeHistoryItems = [];
    let selectedAlbumMaster = null;
    let masterVariantItems = [];
    let masterVariantPage = 1;
    let masterVariantPageSize = 50;
    let masterVariantHasNext = false;
    let masterVariantTotalCount = null;
    let masterVariantTruncated = false;
    let albumSearchResults = [];
    let homeSearchResults = [];
    let homeSearchTotalCount = 0;
    let homeSearchPage = 1;
    let homeSearchPageSize = 30;
    let homeSelectedMasterId = null;
    const _localLinkedIds = new Set();
    async function _loadLocalLinkedIds() {
      try {
        const res = await fetch("/local-music/linked-ids");
        if (!res.ok) return;
        const data = await res.json();
        _localLinkedIds.clear();
        (data.ids || []).forEach(id => _localLinkedIds.add(Number(id)));
      } catch (_) {}
    }
    _loadLocalLinkedIds();
    let homeExpandedMasterPreviewIds = new Set();
    const mediaSearchExpandedPreviewByMaster = new Map();
    const mediaSearchInlineEditorDetailCache = new Map();
    const mediaSearchInlineEditorLoadingOwnedIds = new Set();
    const mediaSearchInlineEditorSavingOwnedIds = new Set();
    const mediaSearchInlineEditorStatusByOwnedItem = new Map();
    let homeSelectedItemId = null;
    let homeEditRequestSeq = 0;
    let homeInlineEditorCollapsed = false;
    let homeSelectedSourceCode = null;
    let homeSelectedSourceExternalId = null;
    let homeMetaCandidates = [];
    let homeEditShelfItems = [];
    let homeEditShelfSelectedId = null;
    let homeEditShelfPrevId = null;
    let homeEditShelfNextId = null;
    let homeLocationSlotItems = [];
    let homeLocationSlotId = null;
    let homeLocationSlotLoading = false;
    let homeMasterInfo = null;
    let homeLinkedCollectibles = [];
    let homeLinkedCollectiblesLoading = false;
    let homeProductLinkedGoods = [];
    let homeProductLinkedGoodsLoading = false;
    let homeOwnedItemRelationView = null;
    let homeOwnedItemRelationMasterEntries = [];
    let homeOwnedItemEditableRelations = [];
    let homeMasterAddVariants = [];
    let homeMasterAddPage = 1;
    let homeMasterAddPageSize = 50;
    let homeMasterAddHasNext = false;
    let homeMasterAddTotalCount = null;
    let homeMasterAddTruncated = false;
    let homeAudioDirectoryMappings = [];
    let homeAudioDirectoryFiles = [];
    let homeTrackMapSaveInFlight = false;
    let homeLoadedMusicDetail = null;
    let homeLinkedGoodsImageEntries = [];
    let homeDashboardBySlot = [];
    let homeDashboardInCollectionItems = 0;
    let homeDashboardSelectedCabinetKey = null;
    let homeDashboardSelectedSlotCode = null;
    let homeDashboardSlotGridPage = 0;
    let homeDashboardSlotGridFollowSelection = true;
    let homeDashboardSlotItems = [];
    let homeDashboardSlotItemsSlotCode = null;
    let homeDashboardSlotItemsLoading = false;
    let homeDashboardSlotPage = 0;
    let homeDashboardSlotShelfScrollLeft = 0;
    let homeDashboardSlotPageSizeOverride = "";
    let homeDashboardSlotViewMode = DASHBOARD_SLOT_DEFAULT_VIEW_MODE;
    let homeDashboardHoveredItemId = null;
    let homeDashboardSlotAttentionTimer = null;
    let homeDashboardSlotSelectedIds = new Set();
    let homeDashboardSlotSelectionSnapshot = [];
    let homeDashboardSlotSelectionAnchorId = 0;
    let homeDashboardUnassignedItems = [];
    let homeDashSurfacePanel = "";
    let homeDashboardUnassignedLoading = false;
    let homeDashboardUnassignedSelectedIds = new Set();
    let homeDashboardUnassignedSelectionAnchorId = 0;
    let homeDashboardSearchItems = [];
    let homeDashboardSearchLoading = false;
    let homeDashboardSearchSelectedIds = new Set();
    let homeDashboardSearchSelectionAnchorId = 0;
    let homeDashboardClickMoveMode = false;
    let homeDashboardWorkbenchPage = 0;
    let homeDashboardWorkbenchShelfScrollLeft = 0;
    let homeDashboardWorkbenchSuppressSelectionScrollOnce = false;
    let homeDashboardWorkbenchRecommendations = {};
    let homeDashboardWorkbenchMode = "UNASSIGNED";
    let sharedCameraSelectedId = null;
    let masterOwnedItems = [];
    let opsExceptionCounts = {
      UNSLOTTED: 0,
      SOURCE_MISSING: 0,
      MASTER_MISSING: 0,
      COVER_MISSING: 0,
      PREFERRED_SIZE_MISMATCH: 0,
      TRACK_MISSING: 0,
      SPOTIFY_UNMATCHED: 0,
      MEDIA_MISSING: 0,
      SIZE_MISMATCH: 0,
      GENRE_MISSING: 0,
      CATALOG_MISSING: 0,
    };
    let opsExceptionItems = [];
    let opsExceptionTotalCount = 0;
    let opsExceptionLoading = false;
    let opsExceptionSelectedIds = new Set();
    let opsExceptionOffset = 0;
    let masterOwnedPrefilledIds = new Set();
    const OPS_EXCEPTION_PRESET_KEY = "__PROJECT_SLUG__.opsExceptionPresets.v1";
    const OPS_EXCEPTION_PRESET_DEFAULT_KEY = "__PROJECT_SLUG__.opsExceptionPresets.default.v1";
    const APP_MAIN_TAB_MEMORY_KEY = "__PROJECT_SLUG__.mainTabByRole.v1";
    const APP_SUBTAB_MEMORY_KEY = "__PROJECT_SLUG__.subTabByRole.v1";
    const DASHBOARD_WORKBENCH_PREFS_KEY = "__PROJECT_SLUG__.dashboardWorkbenchPrefsByRole.v1";
    const DASHBOARD_CABINET_SELECTION_STORAGE_KEY = "__PROJECT_SLUG__.dashboardCabinetSelection.v1";
    const APP_LOCALE_STORAGE_KEY = "__PROJECT_SLUG__.appLocale.v1";
    const APP_THEME_STORAGE_KEY = "__PROJECT_SLUG__.uiTheme.v1";
    const SUPPORTED_APP_LOCALES = new Set(["ko", "en", "ja"]);
    let appLocale = "ko";
    let appTheme = "night";


    function rerenderLocaleSensitiveViews() {
      const rerender = (callback) => {
        try {
          callback();
        } catch (_) {}
      };
      rerender(() => renderOpsProviderSettings(opsProviderSettingsSnapshot));
      rerender(() => renderOpsHomeHeroStats(opsHomeHeroStats));
      rerender(() => updateOperatorFeedControls());
      rerender(() => renderOperatorLookupResults());
      rerender(() => renderOperatorHomeRecentSections());
      rerender(() => renderPurchaseImportPreview(purchaseImportPreviewItems));
      rerender(() => renderPurchaseImportQueue(purchaseImportQueueItems));
      rerender(() => renderBarcodeResults(registerLookupCandidates, { resetLocationState: false }));
      rerender(() => renderAlbumSearchResults(albumSearchResults));
      rerender(() => renderMasterMergeRows(masterMergeSearchResults));
      rerender(() => renderMasterMergeQueueRows());
      rerender(() => renderHomeSearchResults(homeSearchResults));
      rerender(() => renderHomePagination());
      rerender(() => renderHomeMetaCandidates(homeMetaCandidates));
      rerender(() => renderHomeSourceManagedMetaSummary());
      rerender(() => renderAdminManageSurface());
      rerender(() => renderHomeLinkedCollectiblesSection());
      rerender(() => renderHomeRelatedVersions());
      rerender(() => renderHomeProductRelationSection());
      rerender(() => renderHomeMasterAddVariants(homeMasterAddVariants, homeMasterVariantPlaceholderText()));
      rerender(() => renderHomeMasterAddPager());
      rerender(() => renderHomeEditShelfTrack());
      rerender(() => renderHomeLocationInfo(homeLocationSlotItems.find((row) => Number(row?.id || 0) === Number(homeSelectedItemId || 0)) || null));
      rerender(() => renderHomeLocationSlotList());
      rerender(() => renderGoodsSearchResults());
      if (homeDashboardBySlot.length) {
        rerender(() => renderDashboardSlotCards(homeDashboardBySlot, homeDashboardInCollectionItems));
        rerender(() => renderDashboardCabinetDetail());
        rerender(() => renderDashboardWorkbench());
        rerender(() => renderDashboardSelectionSummary());
      }
      rerender(() => renderSourceWorkbenchList());
      rerender(() => renderSourceWorkbenchQueue());
      rerender(() => renderOpsExceptionSummary());
      rerender(() => renderOpsExceptionList());
      rerender(() => syncMasterExceptionBanner());
      rerender(() => renderMediaSearchContextDefault());
      rerender(() => renderOpsLibraryContextDefault());
      if (sourceWorkbenchDiffReviewState) {
        rerender(() => renderSourceWorkbenchDiffReview());
      }
    }

    function applyLocale(locale = appLocale) {
      appLocale = saveLocale(locale);
      document.documentElement.lang = appLocale;
      syncShellLocaleSelect();
      syncShellThemeToggle();
      syncLocalizedToolDocLinks();
      document.querySelectorAll("[data-i18n]").forEach((el) => {
        const key = String(el.getAttribute("data-i18n") || "").trim();
        if (!key) return;
        el.textContent = t(key);
      });
      document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
        const key = String(el.getAttribute("data-i18n-placeholder") || "").trim();
        if (!key) return;
        el.setAttribute("placeholder", t(key));
      });
      document.querySelectorAll("[data-i18n-title]").forEach((el) => {
        const key = String(el.getAttribute("data-i18n-title") || "").trim();
        if (!key) return;
        el.setAttribute("title", t(key));
      });
      document.querySelectorAll("[data-i18n-aria-label]").forEach((el) => {
        const key = String(el.getAttribute("data-i18n-aria-label") || "").trim();
        if (!key) return;
        el.setAttribute("aria-label", t(key));
      });
      document.querySelectorAll("[data-help-key]").forEach((el) => {
        const key = String(el.getAttribute("data-help-key") || "").trim();
        if (!key) return;
        el.setAttribute("data-help", t(key));
        el.setAttribute("title", t(key));
      });
      applyFieldHelpTooltips();
      if (pageHelpDrawerState.open) {
        renderPageHelpDrawer(pageHelpDrawerState.helpId);
        syncPageHelpTriggerState();
      }
      rerenderLocaleSensitiveViews();
    }
