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

    const PACKAGING_OPTIONS_BY_MEDIA = {
      VINYL: ["Single Jacket", "Gatefold", "Triple-fold", "Gimmick Sleeve", "Die-Cut Sleeve", "Pop-up Sleeve", "Box Set"],
      CD: ["Jewel Case", "Double Jewel", "Slim Jewel", "Digipak", "Paper Sleeve", "Slipcase", "Digibook", "Eco-pack", "DVD Size Digipak", "Keep Case", "Gimmick Case", "LP-Style Packaging", "Box Set"],
      CASSETTE: ["Standard Case", "Slipcase", "LP-Style Packaging", "Box Set"],
      EIGHT_TRACK: ["Standard"],
      REEL: ["Standard Box"],
    };

    // 패키징 옵션 풍선도움말 (KO/EN/JA)
    const PACKAGING_TOOLTIPS = {
      ko: {
        VINYL: {
          "Single Jacket": "가장 일반적인 LP 커버. 앞면·뒷면 한 장 구성.",
          "Gatefold": "두 겹으로 펼쳐지는 커버. 2LP나 특별 에디션에 주로 사용.",
          "Triple-fold": "세 패널로 펼쳐지는 커버 (삼절 커버).",
          "Gimmick Sleeve": "이형·반투명·홀로그램 등 특수 제작 슬리브.",
          "Die-Cut Sleeve": "커버에 모양대로 구멍을 뚫은 다이컷 슬리브.",
          "Pop-up Sleeve": "펼치면 입체물이 나타나는 팝업 슬리브.",
          "Box Set": "여러 LP와 부속물을 박스에 담은 에디션.",
        },
        CD: {
          "Jewel Case": "표준 투명 플라스틱 CD 케이스.",
          "Double Jewel": "2CD용 또는 두꺼운 더블 케이스.",
          "Slim Jewel": "더 얇은 슬림 플라스틱 케이스.",
          "Digipak": "트레이가 내장된 종이(보드) 소재 케이스.",
          "Paper Sleeve": "단순 종이 슬리브만 있는 포장.",
          "Slipcase": "케이스에 끼워 넣는 외부 종이 슬립케이스.",
          "Digibook": "하드커버 책자 형태의 케이스.",
          "Eco-pack": "재활용 소재 또는 미니멀 패키징.",
          "DVD Size Digipak": "DVD 크기의 대형 디지팩.",
          "Keep Case": "DVD 케이스 형태의 플라스틱 케이스.",
          "Gimmick Case": "특수 가공된 이형 케이스.",
          "LP-Style Packaging": "LP 크기 슬리브에 담긴 CD. LP 장에 보관 가능.",
          "Box Set": "박스에 담은 멀티 CD 에디션.",
        },
        CASSETTE: {
          "Standard Case": "일반 플라스틱 카세트 케이스.",
          "Slipcase": "케이스를 감싸는 외부 종이 슬립케이스.",
          "LP-Style Packaging": "LP 크기 슬리브에 담긴 카세트. LP 장에 보관 가능.",
          "Box Set": "여러 카세트를 담은 박스 에디션.",
        },
        EIGHT_TRACK: {
          "Standard": "표준 8트랙 카트리지 케이스.",
        },
        REEL: {
          "Standard Box": "릴투릴 테이프용 표준 박스 케이스.",
        },
      },
      en: {
        VINYL: {
          "Single Jacket": "Standard single LP cover with front and back panels.",
          "Gatefold": "Two-panel fold-open cover. Common for 2LP and special editions.",
          "Triple-fold": "Three-panel fold-open cover.",
          "Gimmick Sleeve": "Special-effect sleeve: die-cut, translucent, holographic, etc.",
          "Die-Cut Sleeve": "Cover with a decorative die-cut cutout.",
          "Pop-up Sleeve": "Sleeve with a 3D pop-up element when opened.",
          "Box Set": "Multi-LP edition packaged in a box with extras.",
        },
        CD: {
          "Jewel Case": "Standard transparent plastic CD case.",
          "Double Jewel": "Double-width case for 2 CDs.",
          "Slim Jewel": "Thinner version of the standard plastic jewel case.",
          "Digipak": "Paper/board case with an integrated plastic tray.",
          "Paper Sleeve": "Simple paper envelope sleeve only.",
          "Slipcase": "Outer cardboard slip-in box around another case.",
          "Digibook": "Hardcover book-style case.",
          "Eco-pack": "Recycled material or minimal packaging.",
          "DVD Size Digipak": "Larger digipak in DVD dimensions.",
          "Keep Case": "Plastic case in DVD keep-case form.",
          "Gimmick Case": "Special-effect or novelty case.",
          "LP-Style Packaging": "CD packaged in an LP-sized sleeve. Can be stored in an LP shelf.",
          "Box Set": "Multi-CD edition packaged in a box.",
        },
        CASSETTE: {
          "Standard Case": "Standard plastic cassette case.",
          "Slipcase": "Outer cardboard slip-in sleeve over the case.",
          "LP-Style Packaging": "Cassette in an LP-sized sleeve. Can be stored in an LP shelf.",
          "Box Set": "Multi-cassette edition in a box.",
        },
        EIGHT_TRACK: {
          "Standard": "Standard 8-track cartridge housing.",
        },
        REEL: {
          "Standard Box": "Standard reel-to-reel tape storage box.",
        },
      },
      ja: {
        VINYL: {
          "Single Jacket": "最も一般的な LP カバー。表と裏の 1 枚構成。",
          "Gatefold": "見開きカバー。2LP や特別版によく使われます。",
          "Triple-fold": "3 折りパネルのカバー（三折ジャケット）。",
          "Gimmick Sleeve": "型抜き・半透明・ホログラムなど特殊加工スリーブ。",
          "Die-Cut Sleeve": "型抜きで穴を開けたカバー。",
          "Pop-up Sleeve": "開くと立体物が飛び出すスリーブ。",
          "Box Set": "複数 LP と付属品をまとめたボックスセット。",
        },
        CD: {
          "Jewel Case": "標準の透明プラスチック CD ケース。",
          "Double Jewel": "2 枚組 CD 用または厚めのダブルケース。",
          "Slim Jewel": "薄型スリムプラスチックケース。",
          "Digipak": "トレイ付きの紙（ボード）製ケース。",
          "Paper Sleeve": "シンプルな紙スリーブのみ。",
          "Slipcase": "ケースに差し込む外装紙スリップケース。",
          "Digibook": "ハードカバー本型ケース。",
          "Eco-pack": "リサイクル素材またはミニマルパッケージ。",
          "DVD Size Digipak": "DVD サイズの大型デジパック。",
          "Keep Case": "DVD ケース形状のプラスチックケース。",
          "Gimmick Case": "特殊加工の異形ケース。",
          "LP-Style Packaging": "LP サイズのスリーブに入った CD。LP ラックに収納可能。",
          "Box Set": "複数 CD をまとめたボックスセット。",
        },
        CASSETTE: {
          "Standard Case": "標準のプラスチックカセットケース。",
          "Slipcase": "ケースを包む外装紙スリップケース。",
          "LP-Style Packaging": "LP サイズのスリーブに入ったカセット。LP ラックに収納可能。",
          "Box Set": "複数カセットをまとめたボックスセット。",
        },
        EIGHT_TRACK: {
          "Standard": "標準の 8 トラックカートリッジケース。",
        },
        REEL: {
          "Standard Box": "リールテープ用標準ボックスケース。",
        },
      },
    };

    function _getPackagingTooltip(key, opt) {
      const locale = (typeof appLocale !== "undefined" ? appLocale : "ko") || "ko";
      const byLocale = PACKAGING_TOOLTIPS[locale] || PACKAGING_TOOLTIPS.ko || {};
      return (byLocale[key] || {})[opt] || (PACKAGING_TOOLTIPS.en[key] || {})[opt] || "";
    }

    function _mediaTypeToPackagingKey(mediaType) {
      const v = String(mediaType || "").toLowerCase().trim();
      if (/vinyl|lp|7"|10"|all\s*media/.test(v)) return "VINYL";
      if (/\bcd\b|compact\s*disc|^cdr$|sacd|dvd|blu.ray|cd.rom/.test(v)) return "CD";
      if (/cassette/.test(v)) return "CASSETTE";
      if (/8track|8-track/.test(v)) return "EIGHT_TRACK";
      if (/reel/.test(v)) return "REEL";
      return null;
    }

    function _renderPackagingOptions(mediaType) {
      const container = $("editFormatNameOptions");
      if (!container) return;
      const key = _mediaTypeToPackagingKey(mediaType);
      const options = key ? (PACKAGING_OPTIONS_BY_MEDIA[key] || []) : [];
      const currentValues = String($("editFormatName")?.value || "").split(",").map(s => s.trim()).filter(Boolean);
      if (!options.length) {
        container.innerHTML = '<span class="muted mini">미디어 타입 선택 시 옵션 표시</span>';
        return;
      }
      container.innerHTML = options.map(opt => {
        const checked = currentValues.includes(opt) ? " checked" : "";
        const tip = _getPackagingTooltip(key, opt);
        const tipAttr = tip ? ` title="${escapeHtml(tip)}"` : "";
        return `<label class="edit-format-name-option"${tipAttr}><input type="checkbox" value="${escapeHtml(opt)}"${checked}> ${escapeHtml(opt)}</label>`;
      }).join("");
      container.querySelectorAll('input[type="checkbox"]').forEach(cb => {
        cb.addEventListener("change", _onPackagingChange);
      });
    }

    function _onPackagingChange() {
      const container = $("editFormatNameOptions");
      if (!container) return;
      const vals = Array.from(container.querySelectorAll('input[type="checkbox"]:checked')).map(cb => cb.value);
      $("editFormatName").value = vals.join(", ");
    }

    function _syncVinylOnlyFields() {
      const mediaVal = String($("editMediaType")?.value || "").trim();
      const isVinyl = /vinyl|7"|10"|all\s*media/i.test(mediaVal);
      setHiddenIfPresent("homeEditSpeedRpmWrap", !isVinyl);
      setHiddenIfPresent("homeEditDiscTypeWrap", !isVinyl);
      setHiddenIfPresent("homeEditVinylMetaRow", !isVinyl);
      _renderPackagingOptions(mediaVal);
    }

    // 구(한국어) 패키지 구성 값 → 신(영문) 변환 맵 (하위 호환)
    const _PKG_CONTENTS_KO_TO_EN = {
      "부클릿": "Booklet",
      "리플릿": "Leaflet",
      "미니포스터/타블로이드": "Mini Poster / Tabloid",
      "엽서": "Postcard",
      "스티커": "Sticker",
      "북마크": "Bookmark",
      "렌티큘러/홀로그램카드": "Lenticular / Hologram Card",
      "포토카드": "Photo Card",
      "필름컷": "Film Cut",
      "보증서": "Warranty Card",
      "응모권": "Entry Form",
      "Insert / Inner Sleeve": "Inner Sleeve",
    };

    function _loadPackageContents(value) {
      const rawValues = String(value || "").split(",").map(s => s.trim()).filter(Boolean);
      // 구 한국어 값이 있으면 영문으로 자동 변환
      const savedValues = rawValues.map(v => _PKG_CONTENTS_KO_TO_EN[v] || v);
      const container = $("editPackageContentsOptions");
      if (!container) return;
      const knownValues = new Set();
      container.querySelectorAll('input[type="checkbox"]:not(#editPackageContentsOtherCheck)').forEach(cb => {
        knownValues.add(cb.value);
        cb.checked = savedValues.includes(cb.value);
      });
      const otherVals = savedValues.filter(v => !knownValues.has(v));
      const otherCheck = $("editPackageContentsOtherCheck");
      const otherText = $("editPackageContentsOtherText");
      if (otherVals.length) {
        if (otherCheck) otherCheck.checked = true;
        if (otherText) { otherText.value = otherVals.join(", "); otherText.style.display = ""; }
      } else {
        if (otherCheck) otherCheck.checked = false;
        if (otherText) { otherText.value = ""; otherText.style.display = "none"; }
      }
    }

    function _collectPackageContents() {
      const container = $("editPackageContentsOptions");
      if (!container) return "";
      const vals = [];
      container.querySelectorAll('input[type="checkbox"]:not(#editPackageContentsOtherCheck):checked').forEach(cb => vals.push(cb.value));
      const otherCheck = $("editPackageContentsOtherCheck");
      const otherText = $("editPackageContentsOtherText");
      if (otherCheck?.checked) {
        const otherVals = String(otherText?.value || "").split(",").map(s => s.trim()).filter(Boolean);
        vals.push(...otherVals);
      }
      return vals.join(", ");
    }


    /* ── dashboard card interactions ── */
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

    /* call after dashboard render */
    if (typeof initDashCardInteractions === "function") {
      setTimeout(initDashCardInteractions, 300);
    }

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

    function setConditionSelectValue(selectId, rawValue) {
      const el = $(selectId);
      if (!el) return;
      const raw = String(rawValue || "").trim();
      const normalized = normalizeConditionGradeValue(raw);
      const customOpt = el.querySelector('option[data-custom-condition="true"]');
      if (customOpt) customOpt.remove();
      if (!normalized) {
        el.value = "";
        return;
      }
      const matched = Array.from(el.options).some((opt) => String(opt.value || "") === normalized);
      if (matched) {
        el.value = normalized;
        return;
      }
      const opt = document.createElement("option");
      opt.value = normalized;
      opt.textContent = normalized;
      opt.dataset.customCondition = "true";
      el.appendChild(opt);
      el.value = normalized;
    }

    function relabelMediaSelectOptions(selectId) {
      const el = $(selectId);
      if (!el || !el.options) return;
      for (const opt of Array.from(el.options)) {
        const raw = String(opt.value || opt.textContent || "").trim();
        const code = raw.toUpperCase();
        if (!MUSIC_CATEGORIES.has(code)) continue;
        opt.value = code;
        opt.textContent = mediaDisplayLabel(code);
      }
    }

    function initMediaLabelUi() {
      const targets = [
        "quickCategory",
        "category",
        "editCategory",
        "csvDefaultCategory",
        "ownedCategory",
        "formatName",
        "editFormatName",
      ];
      for (const id of targets) relabelMediaSelectOptions(id);
    }

    function _labelHelpText(labelEl) {
      if (!labelEl) return "";
      const clone = labelEl.cloneNode(true);
      clone.querySelectorAll("input, select, textarea, button, .help-dot, .section-help-dot").forEach((el) => el.remove());
      const text = String(clone.textContent || "").replace(/\s+/g, " ").trim();
      if (text) return text;
      const spanText = String(labelEl.querySelector("span")?.textContent || "").replace(/\s+/g, " ").trim();
      return spanText;
    }

    const FIELD_HELP_MESSAGES = {
      ko: {
        aria: "필드 도움말",
        slot_id: "보관 슬롯 자체를 식별하는 내부 ID입니다. 새 슬롯 생성 시 비워두고, 기존 슬롯을 수정할 때 자동으로 채워집니다.",
        owned_item_id: "보유 상품 1건을 식별하는 내부 ID입니다. 수정, 삭제, 연계 작업의 기준값입니다.",
        album_master_id: "같은 앨범 묶음을 식별하는 내부 ID입니다. LP, CD, 카세트처럼 다른 상품을 하나의 앨범으로 연결할 때 사용합니다.",
        storage_slot: "실제 장식장 위치입니다. 장식장 등록에서 만든 장식장, 열, 칸 슬롯 중 하나를 선택합니다.",
        cabinet_name: "장식장 단위 이름입니다. 예: LP 주문제작장 01, CD 알루미늄장 03",
        floor_count: "이 장식장을 몇 개의 열로 나눌지 입력합니다. 입력한 수만큼 슬롯이 일괄 생성됩니다.",
        cell_count: "각 열에 몇 개의 칸을 만들지 입력합니다. 열 수와 곱해져 전체 슬롯 수가 결정됩니다.",
        floor_start: "열 번호 시작값입니다. 보통 1로 두고, 기존 번호 체계를 이어갈 때만 조정합니다.",
        cell_start: "칸 번호 시작값입니다. 보통 1로 두고, 기존 번호 체계를 이어갈 때만 조정합니다.",
        column_code: "장식장 안에서 위에서 아래로 내려가는 단위를 구분하는 열 번호입니다. 예: 01, 02, 03",
        cell_code: "해당 열 안에서 좌우 배치 위치를 구분하는 칸 번호입니다. 예: 01, 02, 03",
        domain_code: "장식장 대분류 기준입니다. 가요, 제이팝, 그 외 중 어디에 배치할지 정하는 값입니다.",
        release_type: "발매 성격 구분입니다. 정규 앨범, EP, 싱글처럼 앨범 단위 분류에 사용합니다.",
        size_group: "장식장에 들어가는 물리 규격입니다. CD, CD 확장형, LP, 10인치, 7인치, LP 박스셋, 카세트, 8-track, Reel-to-reel, 수집품을 구분합니다.",
        format_name: "내가 보유한 상품의 포맷입니다. LP, CD, Cassette 같은 실제 매체 구분입니다.",
        media_type: "원본 소스가 가진 매체 표기입니다. Discogs 등의 원문을 그대로 보존할 때 사용합니다.",
        released_date: "현재 선택한 상품 버전의 발매일입니다. 최초 발매일이 아니라 해당 버전 기준 날짜를 넣습니다.",
        barcode: "상품 식별용 바코드입니다. 최신 음반은 정확한 단건 조회에 가장 유효합니다.",
        catalog_no: "레이블이 붙인 발매 고유 번호입니다. 같은 앨범의 다른 버전을 구분할 때 중요합니다.",
        label_name: "발매사 또는 레이블 이름입니다. 카탈로그 번호와 함께 버전 구분의 핵심 기준입니다.",
        runout: "음반 데드왁스나 안쪽 링에 적힌 매트릭스 정보입니다. 같은 카탈로그 번호 내 세부 버전 구분에 유효합니다.",
        pressing_country: "이 상품이 실제로 프레싱된 국가입니다. 아티스트 국적이나 발매국과 다를 수 있습니다.",
        display_rank: "같은 위치권 안에서 화면상 노출 순서를 미세 조정할 때 쓰는 값입니다. 논리 순서(order_key) 보조용입니다.",
        purchase_source: "어디서 구했는지 기록합니다. 매장명, 사이트명, 행사 현장 같은 출처를 남길 때 사용합니다.",
        condition_grade: "커버/알판 개별 상태 외에 전체적으로 남길 컨디션 메모입니다. 예: 보관감 있음, 모서리 마모",
        memory_note: "구매 계기, 버전 특징, 기억할 만한 포인트를 자유롭게 적는 운영 메모입니다.",
        signature_type: "싸인 여부와 출처를 구분합니다. 직접 받았는지, 구매 시 포함이었는지 나눠 기록합니다.",
        meta_source: "메타를 어느 외부 소스에서 조회할지 정합니다. AUTO는 사용 가능한 소스를 순차적으로 사용합니다.",
        barcode_limit: "한 번에 불러올 메타 후보 수입니다. 결과가 많을 때 목록 길이를 조절합니다.",
        meta_query: "바코드가 없을 때 사용할 키워드입니다. 보통 아티스트명, 상품명, 카탈로그 번호를 함께 넣습니다.",
        artist: "아티스트명입니다. 조건 조회와 장식장 분류 기준으로 함께 사용합니다.",
        item_name: "화면과 리스트에 직접 보여줄 이름입니다. 필요하면 아티스트 - 상품명 형태로 정리합니다.",
        cover_condition: "중고 상품일 때 커버 상태를 따로 적습니다. 예: NM, VG+, 모서리 마모",
        disc_condition: "중고 상품일 때 알판이나 디스크 상태를 따로 적습니다. 예: EX, 스크래치 소량",
        cover_image_url: "대표 커버 이미지 주소입니다. 후보 교체 시 자동으로 채울 수 있고, 직접 교체할 수도 있습니다.",
        track_list: "트랙 목록입니다. 한 줄에 1곡씩 입력하며, 실제 상품 구성 확인용으로 관리합니다.",
        disc_count: "한 상품 안에 들어 있는 디스크 수입니다. 2LP, 2CD 같은 구성일 때 사용합니다.",
        speed_rpm: "LP나 싱글의 재생 속도입니다. 예: 33, 45",
        limited_edition: "음반의 한정 수량 에디션입니다. 체크 시 넘버링 항목이 활성화됩니다.",
        new_product: "개봉하지 않은 미개봉 새 상품입니다. 중고 여부를 구분하는 기준이 됩니다.",
        promo: "정규 판매용이 아닌 홍보 목적으로 제작된 음반입니다. 프로모 스탬프나 컷이 있는 경우가 많습니다.",
        sig_direct: "아티스트로부터 현장에서 직접 받은 친필 싸인입니다.",
        sig_purchase: "구매 시 앨범에 기본 포함된 인쇄 싸인입니다.",
        genre_missing: "장르 정보가 비어 있는 상품만 표시합니다.",
        format_missing: "미디어 포맷 정보가 없는 상품만 표시합니다.",
        catalog_missing: "카탈로그 번호가 없는 상품만 표시합니다.",
        checkbox: "{label} 여부를 설정합니다.",
        select: "{label} 값을 선택합니다.",
        textarea_with_example: "{label}을 입력합니다. 예: {example}",
        textarea: "{label}을 입력합니다.",
        number_with_example: "{label} 숫자를 입력합니다. 예: {example}",
        number: "{label} 숫자를 입력합니다.",
        input_with_example: "{label} 값을 입력합니다. 예: {example}",
        input: "{label} 값을 입력합니다.",
      },
      en: {
        aria: "Field help",
        slot_id: "This is the internal ID for the storage slot itself. Leave it blank for a new slot, and it fills automatically when editing an existing slot.",
        owned_item_id: "This is the internal ID for one owned item. It is the reference value for edit, delete, and link actions.",
        album_master_id: "This is the internal ID for one album grouping. Use it to connect LP, CD, cassette, and other variants under the same album.",
        storage_slot: "This is the actual cabinet location. Choose one of the cabinet, column, and cell slots created in cabinet setup.",
        cabinet_name: "This is the cabinet-level name. Example: LP custom cabinet 01, CD aluminum cabinet 03.",
        floor_count: "Enter how many columns this cabinet should have. That many slots are created in bulk.",
        cell_count: "Enter how many cells each column should have. Together with the column count, this determines the total slot count.",
        floor_start: "This is the starting column number. Usually keep it at 1 unless you are continuing an existing numbering scheme.",
        cell_start: "This is the starting cell number. Usually keep it at 1 unless you are continuing an existing numbering scheme.",
        column_code: "This is the column number inside the cabinet, used to distinguish vertical sections. Example: 01, 02, 03.",
        cell_code: "This is the cell number inside the selected column, used to distinguish left-right positions. Example: 01, 02, 03.",
        domain_code: "This is the cabinet domain grouping. It decides whether the cabinet is used for K-pop, J-pop, or another area.",
        release_type: "This is the release type. Use it to classify the album as a full album, EP, single, and so on.",
        size_group: "This is the physical storage size for the cabinet. It distinguishes CD, expanded CD, LP, 10-inch, 7-inch, LP box set, cassette, 8-track, reel-to-reel, and collectible.",
        format_name: "This is the format of the item you own. It is the actual media type such as LP, CD, or cassette.",
        media_type: "This is the media label from the source itself. Use it when preserving the original wording from Discogs or another provider.",
        released_date: "This is the release date of the currently selected product version. Enter the version date, not the first-ever release date.",
        barcode: "This is the product barcode. For modern releases it is usually the most reliable single-item lookup key.",
        catalog_no: "This is the release catalog number assigned by the label. It is important when distinguishing different versions of the same album.",
        label_name: "This is the label or publisher name. Together with the catalog number, it is a core clue for version identification.",
        runout: "This is the matrix or runout information written in the dead wax or inner ring. It helps distinguish detailed variants under the same catalog number.",
        pressing_country: "This is the country where this item was actually pressed. It can differ from the artist's country or release market.",
        display_rank: "Use this to fine-tune the on-screen order within the same location. It acts as a helper next to the logical order key.",
        purchase_source: "Record where the item came from. Use it for store names, websites, live events, and similar sources.",
        condition_grade: "This is the overall condition memo beyond separate cover/disc grades. Example: storage wear, corner wear.",
        memory_note: "This is a free-form operations note for purchase context, version traits, or anything worth remembering.",
        signature_type: "Use this to distinguish whether the item is signed and where the signature came from, such as signed in person or included at purchase.",
        meta_source: "Choose which external source to use for metadata lookup. AUTO tries available sources in sequence.",
        barcode_limit: "This is how many metadata candidates to load at once. Adjust it when result lists become too long.",
        meta_query: "This is the keyword query to use when no barcode is available. Usually combine artist name, item title, and catalog number.",
        artist: "This is the artist name. It is used together for lookup and cabinet classification.",
        item_name: "This is the display name shown in screens and lists. If needed, format it as Artist - Title.",
        cover_condition: "Use this to record the cover condition for second-hand items. Example: NM, VG+, corner wear.",
        disc_condition: "Use this to record the disc condition for second-hand items. Example: EX, light scratches.",
        cover_image_url: "This is the main cover image URL. It can be filled automatically during source replacement or changed manually.",
        track_list: "This is the track list. Enter one track per line for actual product composition reference.",
        disc_count: "This is the number of discs included in one product, such as 2LP or 2CD.",
        speed_rpm: "This is the playback speed for LPs and singles. Example: 33, 45.",
        limited_edition: "A limited-print edition. Checking this enables the edition numbering field.",
        new_product: "A sealed, never-opened item. This is the primary flag distinguishing new from used.",
        promo: "A release made for promotional use, not regular retail. Often stamped or cut.",
        sig_direct: "A handwritten signature received directly from the artist in person.",
        sig_purchase: "A printed or pre-applied signature included with the album at purchase.",
        genre_missing: "Show only items with no genre assigned.",
        format_missing: "Show only items with no media format assigned.",
        catalog_missing: "Show only items with no catalog number assigned.",
        checkbox: "Sets whether {label} is enabled.",
        select: "Select a value for {label}.",
        textarea_with_example: "Enter {label}. Example: {example}",
        textarea: "Enter {label}.",
        number_with_example: "Enter a number for {label}. Example: {example}",
        number: "Enter a number for {label}.",
        input_with_example: "Enter a value for {label}. Example: {example}",
        input: "Enter a value for {label}.",
      },
      ja: {
        aria: "フィールドヘルプ",
        slot_id: "保管スロット自体を識別する内部 ID です。新規スロット作成時は空欄のままにし、既存スロットを編集するときは自動入力されます。",
        owned_item_id: "保有商品 1 件を識別する内部 ID です。編集、削除、連携作業の基準値になります。",
        album_master_id: "同じアルバム束を識別する内部 ID です。LP、CD、カセットなど別商品を 1 つのアルバムとして結び付けるときに使います。",
        storage_slot: "実際のキャビネット位置です。キャビネット登録で作成したキャビネット・列・段のスロットから選択します。",
        cabinet_name: "キャビネット単位の名前です。例: LP 注文製作棚 01、CD アルミ棚 03。",
        floor_count: "このキャビネットを何列に分けるか入力します。入力した数だけスロットが一括生成されます。",
        cell_count: "各列に何段作るか入力します。列数と掛け合わせて全スロット数が決まります。",
        floor_start: "列番号の開始値です。通常は 1 のままにし、既存番号体系を続けるときだけ調整します。",
        cell_start: "段番号の開始値です。通常は 1 のままにし、既存番号体系を続けるときだけ調整します。",
        column_code: "キャビネット内で上下方向の区分を表す列番号です。例: 01、02、03。",
        cell_code: "その列の中で左右位置を区別する段番号です。例: 01、02、03。",
        domain_code: "キャビネットの大分類基準です。K-pop、J-pop、そのほかのどこへ配置するかを決めます。",
        release_type: "発売タイプの区分です。正規アルバム、EP、シングルなどアルバム単位の分類に使います。",
        size_group: "キャビネットに入る物理規格です。CD、拡張 CD、LP、10 インチ、7 インチ、LP ボックスセット、カセット、8-track、Reel-to-reel、コレクタブルを区別します。",
        format_name: "保有している商品のフォーマットです。LP、CD、Cassette など実際の媒体区分です。",
        media_type: "元ソースが持つ媒体表記です。Discogs などの原文表記をそのまま残したいときに使います。",
        released_date: "現在選択している商品バージョンの発売日です。初回発売日ではなく、そのバージョン基準の日付を入力します。",
        barcode: "商品の識別用バーコードです。最近の音源では単品照会で最も有効です。",
        catalog_no: "レーベルが付けた発売固有番号です。同じアルバムの別バージョンを区別するときに重要です。",
        label_name: "発売元またはレーベル名です。カタログ番号とあわせてバージョン判別の重要な基準になります。",
        runout: "盤のデッドワックスや内周リングに記載されたマトリクス情報です。同じカタログ番号内の細かなバージョン判別に有効です。",
        pressing_country: "この商品が実際にプレスされた国です。アーティスト国籍や発売国と異なる場合があります。",
        display_rank: "同じ位置圏内で画面表示順を微調整するための値です。論理順序(order_key)の補助として使います。",
        purchase_source: "どこで入手したかを記録します。店舗名、サイト名、イベント会場などの出所を残すときに使います。",
        condition_grade: "カバー/盤の個別状態とは別に残す全体コンディションメモです。例: 保管感あり、角スレ。",
        memory_note: "購入のきっかけ、バージョン特徴、覚えておきたいポイントを自由に書く運用メモです。",
        signature_type: "サインの有無と入手経路を区別します。直接受けたか、購入時に含まれていたかを分けて記録します。",
        meta_source: "どの外部ソースでメタデータを照会するかを選びます。AUTO は使えるソースを順に試します。",
        barcode_limit: "一度に読み込むメタ候補数です。結果が多いときに一覧の長さを調整します。",
        meta_query: "バーコードがないときに使うキーワードです。通常はアーティスト名、商品名、カタログ番号を一緒に入れます。",
        artist: "アーティスト名です。条件照会とキャビネット分類の両方に使います。",
        item_name: "画面や一覧に直接表示する名前です。必要ならアーティスト - 商品名の形で整えます。",
        cover_condition: "中古商品のカバー状態を別途記録します。例: NM、VG+、角スレ。",
        disc_condition: "中古商品の盤やディスク状態を別途記録します。例: EX、軽い擦り傷。",
        cover_image_url: "代表カバー画像 URL です。候補置換時に自動入力したり、手動で差し替えたりできます。",
        track_list: "トラック一覧です。1 行に 1 曲ずつ入力し、実際の商品構成確認用に管理します。",
        disc_count: "1 商品に含まれるディスク数です。2LP、2CD などの構成時に使います。",
        speed_rpm: "LP やシングルの再生速度です。例: 33、45。",
        limited_edition: "限定数量のエディションです。チェックするとナンバリング項目が有効になります。",
        new_product: "未開封の新品です。中古かどうかを区別する基準になります。",
        promo: "通常販売用ではなく、プロモーション目的で制作された音盤です。",
        sig_direct: "アーティストから直接もらった直筆サインです。",
        sig_purchase: "購入時にアルバムに含まれている印刷サインです。",
        genre_missing: "ジャンル情報がない商品のみ表示します。",
        format_missing: "メディアフォーマット情報がない商品のみ表示します。",
        catalog_missing: "カタログ番号がない商品のみ表示します。",
        checkbox: "{label} の有無を設定します。",
        select: "{label} の値を選択します。",
        textarea_with_example: "{label} を入力します。例: {example}",
        textarea: "{label} を入力します。",
        number_with_example: "{label} の数値を入力します。例: {example}",
        number: "{label} の数値を入力します。",
        input_with_example: "{label} の値を入力します。例: {example}",
        input: "{label} の値を入力します。",
      },
    };

    function fieldHelpT(key, params = {}) {
      const localeMessages = FIELD_HELP_MESSAGES[appLocale] || FIELD_HELP_MESSAGES.ko || {};
      const fallbackMessages = FIELD_HELP_MESSAGES.ko || {};
      const message = Object.prototype.hasOwnProperty.call(localeMessages, key)
        ? localeMessages[key]
        : fallbackMessages[key];
      if (typeof message !== "string") return key;
      return interpolateI18nMessage(message, params);
    }

    const FIELD_HELP_OVERRIDES = [
      {
        match: ({ id, label }) => id === "opsSlotId" || /slot_id/i.test(label),
        key: "slot_id",
      },
      {
        match: ({ id, label }) => /owned_item_id/i.test(label) || /OwnedId$/.test(id),
        key: "owned_item_id",
      },
      {
        match: ({ id, label }) => /album_master_id/i.test(label) || /연계 앨범 마스터 id/i.test(label) || /LinkedAlbumMasterId$/.test(id),
        key: "album_master_id",
      },
      {
        match: ({ id, label }) => /보관 슬롯/.test(label) || /SlotId$/.test(id),
        key: "storage_slot",
      },
      {
        match: ({ id, label }) => /장식장명/.test(label) || /CabinetName$/.test(id),
        key: "cabinet_name",
      },
      {
        match: ({ id, label }) => /열 수/.test(label) || /FloorCount$/.test(id),
        key: "floor_count",
      },
      {
        match: ({ id, label }) => /칸 수/.test(label) || /CellCount$/.test(id),
        key: "cell_count",
      },
      {
        match: ({ id, label }) => /열 시작/.test(label) || /FloorStart$/.test(id),
        key: "floor_start",
      },
      {
        match: ({ id, label }) => /칸 시작/.test(label) || /CellStart$/.test(id),
        key: "cell_start",
      },
      {
        match: ({ id, label }) => label === "열" || /ColumnCode$/.test(id),
        key: "column_code",
      },
      {
        match: ({ id, label }) => label === "칸" || /CellCode$/.test(id),
        key: "cell_code",
      },
      {
        match: ({ id, label }) => /도메인/.test(label) || /DomainCode$/.test(id),
        key: "domain_code",
      },
      {
        match: ({ id, label }) => /^타입$/.test(label) || /ReleaseType$/.test(id),
        key: "release_type",
      },
      {
        match: ({ id, label }) => /보관 규격/.test(label) || /SizeGroup$/.test(id),
        key: "size_group",
      },
      {
        match: ({ id, label }) => /^포맷$/.test(label) || /FormatName$/.test(id),
        key: "format_name",
      },
      {
        match: ({ id, label }) => /미디어 타입/.test(label) || /MediaType$/.test(id),
        key: "media_type",
      },
      {
        match: ({ id, label }) => /^발매일$/.test(label) || /ReleasedDate$/.test(id),
        key: "released_date",
      },
      {
        match: ({ id, label }) => /바코드/.test(label) || /Barcode/.test(id),
        key: "barcode",
      },
      {
        match: ({ id, label }) => /카탈로그 번호|카탈로그번호|cat#/.test(label) || /Catalog/.test(id),
        key: "catalog_no",
      },
      {
        match: ({ id, label }) => /^레이블$/.test(label) || /LabelName$/.test(id),
        key: "label_name",
      },
      {
        match: ({ id, label }) => /런아웃/.test(label) || /Runout/.test(id),
        key: "runout",
      },
      {
        match: ({ id, label }) => /프레싱 국가/.test(label) || /PressingCountry$/.test(id),
        key: "pressing_country",
      },
      {
        match: ({ id, label }) => /진열 순서/.test(label) || /DisplayRank$/.test(id),
        key: "display_rank",
      },
      {
        match: ({ id, label }) => /구매처/.test(label) || /PurchaseSource$/.test(id),
        key: "purchase_source",
      },
      {
        match: ({ id, label }) => /일반 컨디션 메모/.test(label) || /ConditionGrade$/.test(id),
        key: "condition_grade",
      },
      {
        match: ({ id, label }) => /기억 메모|메모/.test(label) || /MemoryNote$/.test(id),
        key: "memory_note",
      },
      {
        match: ({ id, label }) => /싸인 유형/.test(label) || /SignatureType$/.test(id),
        key: "signature_type",
      },
      {
        match: ({ id, label }) => /검색 소스/.test(label) || /MetaSource/.test(id) || /metaSourceFilter/.test(id),
        key: "meta_source",
      },
      {
        match: ({ id, label }) => /^개수$/.test(label) || /barcodeLimit/.test(id),
        key: "barcode_limit",
      },
      {
        match: ({ id, label }) => /조회어/.test(label) || /MetaQuery$/.test(id),
        key: "meta_query",
      },
      {
        match: ({ id, label }) => /^아티스트/.test(label) || /Artist/.test(id),
        key: "artist",
      },
      {
        match: ({ id, label }) => /표시명/.test(label) || /ItemName/.test(id),
        key: "item_name",
      },
      {
        match: ({ id, label }) => /커버 컨디션/.test(label) || /CoverCondition$/.test(id),
        key: "cover_condition",
      },
      {
        match: ({ id, label }) => /알판 컨디션/.test(label) || /DiscCondition$/.test(id),
        key: "disc_condition",
      },
      {
        match: ({ id, label }) => /커버 이미지 URL/.test(label) || /CoverImageUrl$/.test(id),
        key: "cover_image_url",
      },
      {
        match: ({ id, label }) => /곡 리스트/.test(label) || /TrackList$/.test(id),
        key: "track_list",
      },
      {
        match: ({ id, label }) => /디스크 수/.test(label) || /DiscCount$/.test(id),
        key: "disc_count",
      },
      {
        match: ({ id, label }) => /RPM/.test(label) || /SpeedRpm$/.test(id),
        key: "speed_rpm",
      },
      {
        match: ({ id, label }) => /한정판|Limited/.test(label) || /LimitEd|LimitedEdition/.test(id),
        key: "limited_edition",
      },
      {
        match: ({ id, label }) => /새상품/.test(label) || /NewProduct/.test(id),
        key: "new_product",
      },
      {
        match: ({ id, label }) => /홍보반/.test(label) || /Promo/.test(id),
        key: "promo",
      },
      {
        match: ({ id, label }) => /^직접$/.test(label) || /SigDirect/.test(id),
        key: "sig_direct",
      },
      {
        match: ({ id, label }) => /^구매$/.test(label) || /SigPurchase/.test(id),
        key: "sig_purchase",
      },
      {
        match: ({ id, label }) => /장르 없음/.test(label) || /GenreMissing/.test(id),
        key: "genre_missing",
      },
      {
        match: ({ id, label }) => /미디어 없음/.test(label) || /FormatMissing/.test(id),
        key: "format_missing",
      },
      {
        match: ({ id, label }) => /카탈로그 없음/.test(label) || /CatalogMissing/.test(id),
        key: "catalog_missing",
      },
    ];

    function _fieldHelpOverride(labelText, controlEl) {
      const info = {
        id: String(controlEl?.id || "").trim(),
        label: String(labelText || "").replace(/\s+/g, " ").trim(),
      };
      for (const item of FIELD_HELP_OVERRIDES) {
        if (item.match(info)) return fieldHelpT(item.key);
      }
      return "";
    }

    function trimFieldHelpExamplePrefix(value) {
      return String(value || "").trim().replace(/^(예:|e\\.g\\.?[:]?|例[:：]?)\s*/i, "").trim();
    }

    function _fieldHelpFromLabel(labelText, controlEl) {
      const label = String(labelText || "").replace(/\s+/g, " ").trim();
      if (!label || !controlEl) return "";
      const overrideText = _fieldHelpOverride(label, controlEl);
      if (overrideText) return overrideText;
      const placeholderRaw = String(controlEl.getAttribute("placeholder") || "").trim();
      const placeholder = trimFieldHelpExamplePrefix(placeholderRaw);

      const tag = String(controlEl.tagName || "").toUpperCase();
      const type = String(controlEl.getAttribute("type") || "").toLowerCase();
      if (type === "checkbox" || type === "radio") {
        return fieldHelpT("checkbox", { label });
      }
      if (tag === "SELECT") {
        return fieldHelpT("select", { label });
      }
      if (tag === "TEXTAREA") {
        return placeholder
          ? fieldHelpT("textarea_with_example", { label, example: placeholder })
          : fieldHelpT("textarea", { label });
      }
      if (type === "number") {
        return placeholder
          ? fieldHelpT("number_with_example", { label, example: placeholder })
          : fieldHelpT("number", { label });
      }
      return placeholder
        ? fieldHelpT("input_with_example", { label, example: placeholder })
        : fieldHelpT("input", { label });
    }

    function _ensureFieldHelpBubble(labelEl, helpText) {
      if (!labelEl || !helpText) return;
      if (labelEl.classList.contains("option-pill")) return;
      let badge = labelEl.querySelector(".help-dot");
      if (!badge) {
        badge = document.createElement("span");
        badge.className = "help-dot";
        badge.textContent = "?";
        badge.setAttribute("tabindex", "-1");
        badge.setAttribute("role", "button");
        badge.setAttribute("aria-label", fieldHelpT("aria"));
        labelEl.appendChild(badge);
      }
      badge.setAttribute("data-help", helpText);
      badge.setAttribute("title", helpText);
      badge.setAttribute("tabindex", "-1");
      badge.setAttribute("aria-label", fieldHelpT("aria"));
    }

    function removeHelpDotsFromTabOrder(scope = document) {
      const root = scope && scope.querySelectorAll ? scope : document;
      root.querySelectorAll(".help-dot, .section-help-dot").forEach((badge) => {
        badge.setAttribute("tabindex", "-1");
      });
    }

    function applyFieldHelpTooltips(scope = document) {
      const root = scope && scope.querySelectorAll ? scope : document;
      const labels = Array.from(root.querySelectorAll("label"));
      for (const labelEl of labels) {
        const _i18nTitleKey = String(labelEl.getAttribute("data-i18n-title") || "").trim();
        if (_i18nTitleKey) {
          const _customHelp = t(_i18nTitleKey);
          if (_customHelp && _customHelp !== _i18nTitleKey) {
            const _ctrl = labelEl.querySelector("input, select, textarea");
            _ensureFieldHelpBubble(labelEl, _customHelp);
            if (_ctrl) _ctrl.setAttribute("title", _customHelp);
            labelEl.setAttribute("title", _customHelp);
            continue;
          }
        }
        const _pkgTipOpt = String(labelEl.getAttribute("data-packaging-tip") || "").trim();
        if (_pkgTipOpt) {
          const _lang = document.documentElement.getAttribute("data-lang") || "ko";
          const _allPkgTips = (typeof PACKAGING_TOOLTIPS !== "undefined" && PACKAGING_TOOLTIPS) || {};
          const _langTips = _allPkgTips[_lang] || _allPkgTips.ko || {};
          let _pkgHelp = "";
          for (const _mt in _langTips) { if (_langTips[_mt][_pkgTipOpt]) { _pkgHelp = _langTips[_mt][_pkgTipOpt]; break; } }
          if (_pkgHelp) {
            const _ctrl = labelEl.querySelector("input, select, textarea");
            _ensureFieldHelpBubble(labelEl, _pkgHelp);
            if (_ctrl) _ctrl.setAttribute("title", _pkgHelp);
            labelEl.setAttribute("title", _pkgHelp);
            continue;
          }
        }
        const htmlFor = String(labelEl.getAttribute("for") || "").trim();
        let controlEl = null;
        if (htmlFor) {
          controlEl = document.getElementById(htmlFor);
        }
        if (!controlEl) {
          controlEl = labelEl.querySelector("input, select, textarea");
        }
        if (!controlEl) continue;

        const labelText = _labelHelpText(labelEl);
        const helpText = _fieldHelpFromLabel(labelText, controlEl);
        if (!helpText) continue;

        _ensureFieldHelpBubble(labelEl, helpText);
        controlEl.setAttribute("title", helpText);
        labelEl.setAttribute("title", helpText);
      }
      removeHelpDotsFromTabOrder(root);
    }

    function selectedRegisterLookupCandidateKey() {
      return selectedCandidate ? registerLookupCandidateKey(selectedCandidate) : "";
    }

    function focusRegisterLookupCandidate(index, opts = {}) {
      const root = $("barcodeResults");
      if (!root) return;
      const candidateIndex = Number(index);
      if (!Number.isInteger(candidateIndex) || candidateIndex < 0) return;
      const row = root.querySelector(`[data-register-lookup-index="${candidateIndex}"]`);
      if (!row || typeof row.focus !== "function") return;
      row.focus({ preventScroll: opts.preventScroll !== false });
    }

    function selectRegisterLookupCandidate(index, opts = {}) {
      const candidateIndex = Number(index);
      if (!Number.isInteger(candidateIndex) || candidateIndex < 0) return;
      const candidate = registerLookupCandidates[candidateIndex];
      if (!candidate) return;
      applyCandidateToForm(candidate, { scroll: opts.scroll === true });
      if (adminBarcodeConfirmToken) {
        adminBarcodeConfirmCandidateKey = registerLookupCandidateKey(candidate, candidateIndex);
      }
      renderBarcodeResults(registerLookupCandidates, { resetLocationState: false });
      if (opts.focus !== false) {
        requestAnimationFrame(() => focusRegisterLookupCandidate(candidateIndex, { preventScroll: opts.preventScroll !== false }));
      }
    }

    function syncAdminBarcodeInputReadyState(mode = "idle") {
      const input = $("barcodeInput");
      const state = $("adminBarcodeInputState");
      if (!input) return;
      input.classList.toggle("is-confirm-armed", mode === "confirm");
      input.classList.toggle("is-ready", mode === "ready");
      if (!state) return;
      state.textContent = mode === "ready"
        ? t("media.register.api_lookup.field.barcode.ready")
        : (mode === "confirm"
          ? t("media.register.api_lookup.field.barcode.confirm")
          : "");
      state.classList.toggle("confirm", mode === "confirm");
      state.classList.toggle("ready", mode === "ready");
    }

    function pulseAdminBarcodeInput() {
      const input = $("barcodeInput");
      if (!input) return;
      window.clearTimeout(adminBarcodeInputPulseTimer);
      input.classList.remove("scan-pulse");
      // Force restart when the scanner fires Enter repeatedly.
      void input.offsetWidth;
      input.classList.add("scan-pulse");
      adminBarcodeInputPulseTimer = window.setTimeout(() => {
        input.classList.remove("scan-pulse");
      }, 240);
    }

    function showAdminBarcodeToast(message) {
      const el = $("adminBarcodeToast");
      if (!el || !message) return;
      const safeMessage = escapeHtml(String(message || "").trim());
      const safeSlotLabel = escapeHtml(String(arguments[1] || "").trim());
      el.innerHTML = safeSlotLabel
        ? `${safeMessage}<strong class="admin-barcode-toast-slot"><span class="admin-barcode-toast-slot-label">${escapeHtml(t("media.register.api_lookup.toast.slot_label"))}</span>${safeSlotLabel}</strong>`
        : safeMessage;
      el.classList.add("show");
      window.clearTimeout(adminBarcodeToastTimer);
      adminBarcodeToastTimer = window.setTimeout(() => {
        el.classList.remove("show");
      }, 2200);
    }

    function showShellBarcodeToast(message) {
      const el = $("shellBarcodeToast");
      if (!el || !message) return;
      el.textContent = String(message || "").trim();
      el.classList.add("show");
      window.clearTimeout(shellBarcodeToastTimer);
      shellBarcodeToastTimer = window.setTimeout(() => {
        el.classList.remove("show");
      }, 1800);
    }

    function findRegisterLookupCandidateIndexByKey(key) {
      if (!key) return -1;
      return registerLookupCandidates.findIndex((row, idx) => registerLookupCandidateKey(row, idx) === key);
    }

    function cloneRegisterLookupCandidate(candidate) {
      if (!candidate || typeof candidate !== "object") return null;
      try {
        return JSON.parse(JSON.stringify(candidate));
      } catch (_err) {
        return { ...candidate };
      }
    }

    function renderAdminBarcodePlacementSummary(state = null) {
      const root = $("adminBarcodePlacementSummary");
      if (!root) return;
      const candidateKey = selectedCandidate ? registerLookupCandidateKey(selectedCandidate) : "";
      const picked = candidateKey ? adminBarcodePlacementSelectionByCandidateKey.get(candidateKey) : null;
      if (!state || state.loading) {
        root.innerHTML = `
          <div class="admin-barcode-placement-item rank-1">
            <div class="admin-barcode-placement-rank">${escapeHtml(t("media.register.api_lookup.placement.rank_first"))}</div>
            <strong>${escapeHtml(state?.loading ? t("media.register.api_lookup.placement.loading_title") : t("media.register.api_lookup.placement.empty_title"))}</strong>
            <div class="mini">${escapeHtml(state?.loading ? t("media.register.api_lookup.placement.loading_body") : t("media.register.api_lookup.placement.empty_body"))}</div>
          </div>
        `;
        return;
      }
      if (!Array.isArray(state.recommendations) || !state.recommendations.length) {
        root.innerHTML = `
          <div class="admin-barcode-placement-item">
            <div class="admin-barcode-placement-rank">${escapeHtml(t("media.register.api_lookup.placement.waiting_title"))}</div>
            <strong>${escapeHtml(String(state.fallback_message || t("media.register.api_lookup.placement.empty_title")))}</strong>
            <div class="mini">${escapeHtml(t("media.register.api_lookup.placement.waiting_body"))}</div>
          </div>
        `;
        return;
      }
      const pickedSlot = picked ? getStorageSlotById(Number(picked.storage_slot_id || 0)) : null;
      const pickedSlotLabel = pickedSlot ? (storageSlotDisplayLabel(pickedSlot) || String(pickedSlot.slot_code || "").trim()) : "";
      const isManualSelection = Boolean(picked && Number(picked.rank || 0) > 1);
      const pickedSummary = pickedSlotLabel ? `
        <div class="admin-barcode-placement-picked">
          <span class="admin-barcode-placement-picked-label">${escapeHtml(t("media.register.api_lookup.placement.picked_label"))}</span>
          <span class="admin-barcode-placement-picked-chip">${escapeHtml(pickedSlotLabel)}</span>
          <span class="mini admin-barcode-placement-picked-copy">${escapeHtml(t("media.register.api_lookup.placement.picked_copy"))}</span>
        </div>
      ` : "";
      const manualSelectionCopy = isManualSelection
        ? `<div class="mini admin-barcode-placement-manual-copy">${escapeHtml(t("media.register.api_lookup.placement.manual_copy"))}</div>`
        : "";
      const manualSelectionNote = isManualSelection
        ? `<div class="mini admin-barcode-placement-manual-note">${escapeHtml(t("media.register.api_lookup.placement.manual_note"))}</div>`
        : "";
      root.innerHTML = `${pickedSummary}${manualSelectionCopy}${manualSelectionNote}${state.recommendations.map((item) => {
        const rank = Number(item.rank || 0);
        const slotName = String(item.slot_display_name || item.slot_code || "").trim() || t("media.register.api_lookup.placement.slot_fallback");
        const freeMm = Number(item.free_thickness_mm || 0);
        const occupancy = Number(item.occupancy_percent || 0);
        const slotId = Number(item.storage_slot_id || 0);
        const isActive = picked
          ? Number(picked.storage_slot_id || 0) === slotId
          : rank === 1;
        const autoBadge = rank === 1 ? `<span class="admin-barcode-placement-auto-badge">${escapeHtml(t("media.register.api_lookup.placement.badge.auto"))}</span>` : "";
        const activeBadge = isActive ? `<span class="admin-barcode-placement-active-badge">${escapeHtml(t("media.register.api_lookup.placement.badge.active"))}</span>` : "";
        const badgeGroup = autoBadge || activeBadge
          ? `<div class="admin-barcode-placement-badges">${autoBadge}${activeBadge}</div>`
          : "";
        const anchorDisplay = String(item.anchor_display || "").trim();
        const anchorPosition = String(item.anchor_position || "").trim();
        let anchorLine = "";
        if (anchorDisplay) {
          const posKey = anchorPosition === "BEFORE"
            ? "media.register.api_lookup.placement.anchor_before"
            : "media.register.api_lookup.placement.anchor_after";
          anchorLine = `<div class="mini admin-barcode-placement-anchor">${escapeHtml(anchorDisplay)} <span style="opacity:0.75;font-weight:400">${escapeHtml(t(posKey))}</span></div>`;
        }
        return `
          <div
            class="admin-barcode-placement-item${rank === 1 ? " rank-1" : ""}${isActive ? " active" : ""}"
            data-admin-barcode-placement-slot-id="${Number(item.storage_slot_id || 0)}"
            data-admin-barcode-placement-rank="${rank}"
          >
            <div class="admin-barcode-placement-rank">${escapeHtml(rank === 1 ? t("media.register.api_lookup.placement.rank_first") : t("media.register.api_lookup.placement.rank", { rank }))}</div>
            <strong>${escapeHtml(slotName)}</strong>
            ${badgeGroup}
            <div class="mini admin-barcode-placement-detail">${escapeHtml(t("media.register.api_lookup.placement.detail", { free: formatCount(freeMm), occupancy: formatCount(occupancy) }))}</div>
            ${anchorLine}
          </div>
        `;
      }).join("")}`;
    }

    function buildAdminBarcodeRecommendationPayload(candidate) {
      if (!candidate || typeof candidate !== "object") return null;
      const category = inferMusicCategoryFromMetadata(candidate);
      const sizeGroup = inferSizeGroupFromMetadata(category, candidate);
      const mappedDomain = pickMappedDomain(candidate.domain_code);
      return {
        category,
        size_group: sizeGroup,
        format_name: category,
        artist_or_brand: String(candidate.artist_or_brand || "").trim() || null,
        title: String(candidate.title || "").trim() || null,
        domain_code: mappedDomain || null,
        release_year: normalizePositiveIntOrNull(candidate.release_year),
        barcode: String(candidate.barcode || "").trim() || null,
        source: String(candidate.source || "").trim().toUpperCase() || null,
      };
    }

    function clearAdminBarcodeConfirmation(opts = {}) {
      adminBarcodeConfirmToken = "";
      adminBarcodeConfirmCandidateKey = "";
      syncAdminBarcodeInputReadyState("idle");
      if (opts.keepInput) return;
      const input = $("barcodeInput");
      if (input) input.value = "";
    }

    function resetAdminBarcodeIntakeWorkspace(opts = {}) {
      selectedCandidate = null;
      registerLookupLocationState = {};
      adminBarcodePlacementToken += 1;
      if (!opts.preserveStatus) {
        setStatus("barcodeStatus", "ok", "");
      }
      renderRegisterLookupProviderStatusBadges([]);
      renderBarcodeResults([]);
    }

    function armAdminBarcodeConfirmation(barcodeToken, candidate = null) {
      adminBarcodeConfirmToken = String(barcodeToken || "").trim();
      adminBarcodeConfirmCandidateKey = candidate ? registerLookupCandidateKey(candidate) : "";
      syncAdminBarcodeInputReadyState("confirm");
      const input = $("barcodeInput");
      if (!input) return;
      input.focus();
      if (typeof input.select === "function") input.select();
    }

    function shouldConfirmAdminBarcodeIntake(barcodeToken) {
      const normalized = String(barcodeToken || "").trim();
      if (!normalized || !adminBarcodeConfirmToken) return false;
      if (normalized !== adminBarcodeConfirmToken) return false;
      return findRegisterLookupCandidateIndexByKey(adminBarcodeConfirmCandidateKey) >= 0;
    }

    function setAdminBarcodeIntakeHint(mode = "confirm") {
      const el = $("adminBarcodeIntakeConfirm");
      if (!el) return;
      el.classList.toggle("ready", mode === "saved");
      if (mode === "saved") {
        syncAdminBarcodeInputReadyState("ready");
        el.textContent = t("media.register.api_lookup.confirm.saved");
        return;
      }
      syncAdminBarcodeInputReadyState(adminBarcodeConfirmToken ? "confirm" : "idle");
      el.textContent = t("media.register.api_lookup.confirm.ready");
    }

    function confirmAdminBarcodeDuplicateSave(candidate) {
      if (!candidate?.is_owned) return true;
      const artist = String(candidate.artist_or_brand || "").trim() || t("common.unknown");
      const title = String(candidate.title || "").trim() || t("common.no_title");
      const ownedCount = Math.max(1, Number(candidate.owned_count || 0));
      const slotId = resolveAdminBarcodeRecommendedSlotId(candidate);
      const slot = slotId ? getStorageSlotById(slotId) : null;
      const slotText = slot
        ? t("media.register.api_lookup.duplicate.slot", { slot: storageSlotDisplayLabel(slot) })
        : "";
      const confirmText = t("media.register.api_lookup.duplicate.confirm", {
        artist,
        title,
        slot: slotText,
        count: formatCount(ownedCount),
      });
      return window.confirm(confirmText);
    }

    function syncAdminBarcodePlacementSelection(candidate, storageSlotId, rank = 0) {
      const slotId = Number(storageSlotId || 0);
      if (!candidate || slotId <= 0) return;
      const candidateKey = registerLookupCandidateKey(candidate);
      if (!candidateKey) return;
      adminBarcodePlacementSelectionByCandidateKey.set(candidateKey, {
        storage_slot_id: slotId,
        rank: Number(rank || 0),
      });
      const selectedIndex = findRegisterLookupCandidateIndexByKey(candidateKey);
      const slot = getStorageSlotById(slotId);
      if (slot && selectedIndex >= 0) {
        registerLookupLocationState[String(selectedIndex)] = {
          cabinet_name: String(slot.cabinet_name || "").trim(),
          column_code: String(slot.column_code || "").trim(),
          cell_code: String(slot.cell_code || "").trim(),
        };
      }
      $("slotId").value = String(slotId);
      renderBarcodeResults(registerLookupCandidates, { resetLocationState: false });
      const cached = adminBarcodePlacementCache.get(candidateKey) || null;
      renderAdminBarcodePlacementSummary(cached);
    }

    function resolveAdminBarcodeRecommendedSlotId(candidate) {
      if (!candidate) return null;
      const candidateKey = registerLookupCandidateKey(candidate);
      const picked = adminBarcodePlacementSelectionByCandidateKey.get(candidateKey);
      if (picked) {
        const pickedSlotId = Number(picked.storage_slot_id || 0);
        if (pickedSlotId > 0) return pickedSlotId;
      }
      const cached = adminBarcodePlacementCache.get(candidateKey);
      if (!cached || !Array.isArray(cached.recommendations) || !cached.recommendations.length) return null;
      const slotId = Number(cached.recommendations[0]?.storage_slot_id || 0);
      return slotId > 0 ? slotId : null;
    }

    async function fetchAdminBarcodePlacementSummary(candidate = null) {
      if (!candidate) return null;
      const candidateKey = registerLookupCandidateKey(candidate);
      const cached = adminBarcodePlacementCache.get(candidateKey);
      if (cached) return cached;
      if (adminBarcodePlacementPending.has(candidateKey)) {
        return adminBarcodePlacementPending.get(candidateKey);
      }
      const payload = buildAdminBarcodeRecommendationPayload(candidate);
      if (!payload) return null;
      const request = (async () => {
        const res = await fetchWithRetry("/ingest/barcode/recommend-location", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }, {
          retries: 2,
          retryDelayMs: 250,
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("media.register.api_lookup.status.recommendation_failed")));
        adminBarcodePlacementCache.set(candidateKey, data);
        return data;
      })();
      adminBarcodePlacementPending.set(candidateKey, request);
      try {
        return await request;
      } finally {
        adminBarcodePlacementPending.delete(candidateKey);
      }
    }

    async function loadAdminBarcodePlacementSummary(candidate = null) {
      if (!candidate) {
        renderAdminBarcodePlacementSummary(null);
        return;
      }
      const candidateKey = registerLookupCandidateKey(candidate);
      const cached = adminBarcodePlacementCache.get(candidateKey);
      if (cached) {
        renderAdminBarcodePlacementSummary(cached);
        return;
      }
      const token = ++adminBarcodePlacementToken;
      renderAdminBarcodePlacementSummary({ loading: true });
      try {
        const data = await fetchAdminBarcodePlacementSummary(candidate);
        if (token !== adminBarcodePlacementToken) return;
        renderAdminBarcodePlacementSummary(data);
      } catch (err) {
        if (token !== adminBarcodePlacementToken) return;
        renderAdminBarcodePlacementSummary({
          available: false,
          recommendations: [],
          fallback_message: errorMessageText(err, t("media.register.api_lookup.status.recommendation_failed")),
        });
      }
    }

    function syncAdminBarcodeIntakePanels() {
      void loadAdminBarcodePlacementSummary(selectedCandidate);
    }

    async function submitAdminBarcodeIntake() {
      const barcode = $("barcodeInput").value.trim();
      setAdminBarcodeIntakeHint("confirm");
      if (!barcode) {
        setStatus("barcodeStatus", "err", t("media.register.api_lookup.status.enter_barcode"));
        return;
      }
      const barcodeToken = normalizeBarcodeLookupToken(barcode);
      if (!barcodeToken) {
        setStatus("barcodeStatus", "err", t("media.register.api_lookup.status.invalid_barcode"));
        return;
      }
      if (shouldConfirmAdminBarcodeIntake(barcodeToken)) {
        const selectedIndex = findRegisterLookupCandidateIndexByKey(adminBarcodeConfirmCandidateKey);
        if (selectedIndex < 0) {
          clearAdminBarcodeConfirmation({ keepInput: true });
          setStatus("barcodeStatus", "err", t("media.register.api_lookup.status.candidate_missing"));
          return;
        }
        const candidate = registerLookupCandidates[selectedIndex] || null;
        if (candidate && !resolveAdminBarcodeRecommendedSlotId(candidate)) {
          try {
            const data = await fetchAdminBarcodePlacementSummary(candidate);
            renderAdminBarcodePlacementSummary(data);
          } catch (err) {
            setStatus("barcodeStatus", "err", errorMessageText(err, t("media.register.api_lookup.status.recommendation_required")));
            return;
          }
        }
        setStatus("barcodeStatus", "ok", t("media.register.api_lookup.status.confirm_detected"));
        queueRegisterLookupCandidate(selectedIndex);
        return;
      }
      await barcodeSearch();
    }

    function joinLineList(values) {
      const rows = splitLineList(values);
      return rows.length ? rows.join("\n") : "";
    }

    function extractUrlCandidates(value) {
      const text = String(value || "").trim();
      if (!text) return [];
      return text
        .split(/\s+/g)
        .map((v) => String(v || "").trim())
        .filter((v) => /^https?:\/\//i.test(v) || v.startsWith("/"));
    }

    function setHomeLinkedGoodsImageEntries(values) {
      homeLinkedGoodsImageEntries = normalizeUrlList(values);
      $("homeLinkedGoodsImageUrls").value = joinLineList(homeLinkedGoodsImageEntries);
      renderHomeLinkedGoodsImageList();
    }

    function addHomeLinkedGoodsImageEntries(values) {
      const merged = [...homeLinkedGoodsImageEntries, ...normalizeUrlList(values)];
      setHomeLinkedGoodsImageEntries(merged);
    }

    function clearHomeLinkedGoodsImages() {
      homeLinkedGoodsImageEntries = [];
      $("homeLinkedGoodsImageUrls").value = "";
      $("homeLinkedGoodsImagePaste").value = "";
      $("homeLinkedGoodsImageFiles").value = "";
      renderHomeLinkedGoodsImageList();
    }

    async function uploadUiImageFiles(fileList) {
      const files = Array.from(fileList || []).filter((f) => f);
      if (!files.length) return [];

      const uploadedUrls = [];
      for (const file of files) {
        const type = String(file.type || "").toLowerCase();
        if (type && !type.startsWith("image/")) {
          continue;
        }
        const form = new FormData();
        form.append("file", file, file.name || "image");
        const res = await fetch("/ui/upload-image", {
          method: "POST",
          body: form
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("common.request_failed"));
        const url = String(data.url || "").trim();
        if (url) uploadedUrls.push(url);
      }
      return uploadedUrls;
    }

    // ── 로컬 이미지 관리 ──────────────────────────────────────────
    // ─────────────────────────────────────────────────────────────

    function setStatus(id, kind, text) {
      const el = $(id);
      if (!el) return;
      el.className = "status";
      if (!text) {
        el.textContent = "";
        return;
      }
      el.classList.add(kind === "err" ? "err" : "ok");
      el.textContent = text;
    }

    function isMusicCategory() {
      return MUSIC_CATEGORIES.has($("category").value);
    }

    function syncMusicVisibility() {
      const isMusic = isMusicCategory();
      setDisplayIfPresent("musicBox", isMusic ? "block" : "none");
      setDisplayIfPresent("goodsBox", isMusic ? "none" : "block");
      if (!isMusic && !$("goodsItemName").value.trim() && $("itemNameOverride").value.trim()) {
        $("goodsItemName").value = $("itemNameOverride").value.trim();
      }
      if (isMusic && !$("itemNameOverride").value.trim() && $("goodsItemName").value.trim()) {
        $("itemNameOverride").value = $("goodsItemName").value.trim();
      }
      syncGoodsSpecVisibility($("category").value, {
        poster: "posterSpecWrap",
        tshirt: "tshirtSizeWrap",
        cup: "cupMaterialWrap",
        hat: "hatSizeWrap",
      });
    }

    function syncHomeLinkedGoodsSpecVisibility() {
      syncGoodsSpecVisibility($("homeLinkedGoodsCategory").value, {
        poster: "homeLinkedPosterSpecWrap",
        tshirt: "homeLinkedTshirtSizeWrap",
        cup: "homeLinkedCupMaterialWrap",
        hat: "homeLinkedHatSizeWrap",
      });
    }

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

    // Nav contract:
    // - operator: 운영 홈, 장식장
    // - admin: 운영 홈, 장식장, 관리
    // - non-admin shells stay read-only and must not expose request-write actions
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

    async function safeJson(res) {
      if (res.status === 401) {
        window.location.replace("/login");
        return { detail: "authentication required" };
      }
      const text = await res.text();
      if (!text) return {};
      try { return JSON.parse(text); } catch (_) { return { detail: text }; }
    }

    function buildClientRequestId() {
      const seed = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
      return seed.slice(0, 12);
    }

    async function fetchWithRetry(input, init = {}, options = {}) {
      const clientRequestId = String(options.requestId || buildClientRequestId()).trim();
      const retries = Math.max(0, Number(options.retries ?? 1) || 0);
      const retryDelayMs = Math.max(50, Number(options.retryDelayMs ?? 250) || 250);
      const onRetry = typeof options.onRetry === "function" ? options.onRetry : null;
      const headers = new Headers(init?.headers || {});
      if (clientRequestId && !headers.has("X-Client-Request-ID")) {
        headers.set("X-Client-Request-ID", clientRequestId);
      }
      const nextInit = { ...init, headers };
      for (let attempt = 0; ; attempt += 1) {
        try {
          return await fetch(input, nextInit);
        } catch (err) {
          if (!isRetryableFetchError(err) || attempt >= retries) {
            const errorMessage = detailText(err?.message ?? err) || t("common.request_failed");
            throw new Error(`${errorMessage} [ref: ${clientRequestId}]`);
          }
          if (onRetry) onRetry(attempt + 1, retries + 1, err);
          await new Promise((resolve) => window.setTimeout(resolve, retryDelayMs * (attempt + 1)));
        }
      }
    }

    const GLOBAL_BARCODE_SCANNER_INPUT_IDS = new Set(["barcodeInput", "operatorLookupQuery", "homeBarcode"]);
    const GLOBAL_BARCODE_SCANNER_LENGTH = 13;
    const GLOBAL_BARCODE_SCANNER_MAX_GAP_MS = 80;
    let globalBarcodeScannerBuffer = "";
    let globalBarcodeScannerLastKeyAt = 0;
    let globalBarcodeScannerEditableTarget = null;
    let globalBarcodeScannerEditableInitialValue = "";

    function resetGlobalBarcodeScannerBuffer() {
      globalBarcodeScannerBuffer = "";
      globalBarcodeScannerLastKeyAt = 0;
      globalBarcodeScannerEditableTarget = null;
      globalBarcodeScannerEditableInitialValue = "";
    }

    function shouldHandleGlobalBarcodeScan() {
      const mode = currentShellMode();
      return mode === "ops" || (mode === "admin" && isAdminSession());
    }

    function isGlobalBarcodeScannerNativeInput(target) {
      const id = String(target?.id || "").trim();
      return GLOBAL_BARCODE_SCANNER_INPUT_IDS.has(id);
    }

    function isGlobalBarcodeScannerEditableTarget(target) {
      if (!target) return false;
      if (target.isContentEditable) return true;
      const tag = String(target.tagName || "").trim().toUpperCase();
      if (tag === "TEXTAREA") return true;
      if (tag !== "INPUT") return false;
      const type = String(target.getAttribute("type") || "text").trim().toLowerCase();
      return !["checkbox", "radio", "button", "submit", "reset", "file", "image", "range", "color"].includes(type);
    }

    function restoreGlobalBarcodeScannerEditableValue() {
      const target = globalBarcodeScannerEditableTarget;
      if (!target || typeof target.value !== "string") return;
      target.value = globalBarcodeScannerEditableInitialValue;
      if (typeof target.setSelectionRange === "function") {
        const pos = globalBarcodeScannerEditableInitialValue.length;
        try {
          target.setSelectionRange(pos, pos);
        } catch (_err) {}
      }
    }

    async function routeGlobalBarcodeScanForOps(barcode) {
      const normalizedBarcode = String(barcode || "").trim();
      if (!normalizedBarcode) return false;
      $("operatorLookupQuery").value = normalizedBarcode;
      setStatus("operatorLookupStatus", "ok", t("operator.lookup.status.barcode_loading"));
      await loadOperatorLookupResults();
      showShellBarcodeToast(t("operator.lookup.toast.routed"));
      return true;
    }

    async function lookupAdminOwnedBarcodeMatches(barcode) {
      const normalizedBarcode = String(barcode || "").trim();
      if (!normalizedBarcode) return { items: [], total: 0 };
      const params = new URLSearchParams({
        limit: "30",
        offset: "0",
        include_total: "true",
        media_only: "true",
      });
      params.set("barcode", normalizedBarcode);
      const res = await fetchWithRetry(`/album-masters?${params.toString()}`, {}, {
        retries: 2,
        retryDelayMs: 250,
      });
      const data = await safeJson(res);
      if (!res.ok) throw new Error(data.detail || t("media.register.api_lookup.status.owned_lookup_failed"));
      const totalFromHeader = Number(res.headers.get("X-Total-Count"));
      const items = Array.isArray(data) ? data : [];
      const total = Number.isFinite(totalFromHeader) && totalFromHeader >= 0 ? totalFromHeader : items.length;
      return { items, total };
    }

    function prepareAdminOwnedBarcodeSearch(barcode) {
      const normalizedBarcode = String(barcode || "").trim();
      $("homeArtist").value = "";
      $("homeItemName").value = "";
      $("homeCatalogNo").value = "";
      $("homeReleaseYear").value = "";
      $("homeSigDirect").checked = false;
      $("homeSigPurchase").checked = false;
      $("homeSortMode").value = "CREATED_DESC";
      $("homeBarcode").value = normalizedBarcode;
      $("homeMasterId").value = "";
      $("homeItemId").value = "";
      $("homePackagingList").querySelectorAll('input[type="checkbox"]').forEach(cb => { cb.checked = false; });
      $("homePackageContentsList").querySelectorAll('input[type="checkbox"]').forEach(cb => { cb.checked = false; });
      $("homeLimitEd").checked = false;
      $("homeNewProduct").checked = false;
      $("homePromo").checked = false;
      $("homeSearchAdvancedDetails").open = false;
    }

    async function routeGlobalBarcodeScanForAdmin(barcode) {
      const normalizedBarcode = String(barcode || "").trim();
      if (!normalizedBarcode) return false;
      try {
        const lookup = await lookupAdminOwnedBarcodeMatches(normalizedBarcode);
        if (lookup.total > 0) {
          openAdminConsole("manage");
          prepareAdminOwnedBarcodeSearch(normalizedBarcode);
          await homeSearchOwnedItems({ resetPage: true });
          setStatus("homeSearchStatus", "ok", t("media.register.api_lookup.candidate.flag.owned", { count: formatCount(lookup.total) }));
          showShellBarcodeToast(t("media.register.api_lookup.toast.owned_routed", { count: formatCount(lookup.total) }));
          return true;
        }
      } catch (err) {
        setStatus("barcodeStatus", "err", errorMessageText(err, t("media.register.api_lookup.status.owned_lookup_failed")));
        return false;
      }
      openAdminConsole("register");
      $("barcodeInput").value = normalizedBarcode;
      pulseAdminBarcodeInput();
      await submitAdminBarcodeIntake();
      showShellBarcodeToast(t("media.register.api_lookup.toast.register_routed"));
      return true;
    }

    async function routeGlobalBarcodeScan(barcode) {
      if (currentShellMode() === "ops") {
        return routeGlobalBarcodeScanForOps(barcode);
      }
      if (currentShellMode() === "admin" && isAdminSession()) {
        return routeGlobalBarcodeScanForAdmin(barcode);
      }
      return false;
    }

    function handleGlobalBarcodeScannerKeydown(e) {
      if (e.defaultPrevented || e.isComposing || e.ctrlKey || e.metaKey || e.altKey) return;
      if (!shouldHandleGlobalBarcodeScan()) {
        resetGlobalBarcodeScannerBuffer();
        return;
      }
      if (isGlobalBarcodeScannerNativeInput(e.target)) {
        if (e.key === "Enter") resetGlobalBarcodeScannerBuffer();
        return;
      }
      const targetIsEditable = isGlobalBarcodeScannerEditableTarget(e.target);
      const key = String(e.key || "");
      const isDigit = /^[0-9]$/.test(key);
      if (!isDigit && key !== "Enter") {
        if (key.length === 1) resetGlobalBarcodeScannerBuffer();
        return;
      }
      if (isDigit) {
        const now = Date.now();
        if (!globalBarcodeScannerLastKeyAt || now - globalBarcodeScannerLastKeyAt > GLOBAL_BARCODE_SCANNER_MAX_GAP_MS) {
          globalBarcodeScannerBuffer = "";
          if (targetIsEditable) {
            globalBarcodeScannerEditableTarget = e.target;
            globalBarcodeScannerEditableInitialValue = typeof e.target.value === "string" ? e.target.value : "";
          }
        }
        if (targetIsEditable && globalBarcodeScannerEditableTarget !== e.target) {
          globalBarcodeScannerEditableTarget = e.target;
          globalBarcodeScannerEditableInitialValue = typeof e.target.value === "string" ? e.target.value : "";
        }
        globalBarcodeScannerLastKeyAt = now;
        globalBarcodeScannerBuffer += key;
        if (globalBarcodeScannerBuffer.length > GLOBAL_BARCODE_SCANNER_LENGTH) {
          globalBarcodeScannerBuffer = globalBarcodeScannerBuffer.slice(-GLOBAL_BARCODE_SCANNER_LENGTH);
        }
        if (!targetIsEditable) {
          e.preventDefault();
        }
        return;
      }
      const barcode = String(globalBarcodeScannerBuffer || "").trim();
      if (!new RegExp(`^\\d{${GLOBAL_BARCODE_SCANNER_LENGTH}}$`).test(barcode)) {
        resetGlobalBarcodeScannerBuffer();
        return;
      }
      if (targetIsEditable) {
        restoreGlobalBarcodeScannerEditableValue();
      }
      resetGlobalBarcodeScannerBuffer();
      e.preventDefault();
      e.stopPropagation();
      routeGlobalBarcodeScan(barcode).catch((err) => {
        const statusId = currentShellMode() === "ops" ? "operatorLookupStatus" : "barcodeStatus";
        setStatus(statusId, "err", errorMessageText(err, t("media.register.api_lookup.status.scan_process_failed")));
      });
    }

    function renderAuthSession() {
      const sessionInfo = $("appSessionInfo");
      const sessionUser = $("appSessionUser");
      const roleTag = $("appSessionRoleTag");
      const logoutBtn = $("appLogoutBtn");
      const prefsResetBtn = $("appPrefsResetBtn");
      const enabled = Boolean(appAuthSession?.enabled);
      const authenticated = Boolean(appAuthSession?.authenticated);
      const username = String(appAuthSession?.username || "").trim();
      const role = String(appAuthSession?.role || "ADMIN").trim().toUpperCase();
      const roleLabel = role === "OPERATOR" ? t("auth.role.operator") : t("auth.role.admin");
      document.body.dataset.authenticated = authenticated ? "true" : "false";
      document.body.dataset.authRole = authenticated ? (role || "ADMIN") : "";
      if (sessionInfo) {
        if (enabled && authenticated && username) {
          if (sessionUser) sessionUser.textContent = username;
          setDisplayMode(sessionInfo, "inline-flex");
        } else {
          setDisplayMode(sessionInfo, "none");
          if (sessionUser) sessionUser.textContent = "";
        }
      }
      if (roleTag) {
        if (enabled && authenticated && username && role === "ADMIN") {
          roleTag.textContent = "";
          roleTag.setAttribute("title", roleLabel);
          roleTag.setAttribute("aria-label", roleLabel);
          setDisplayMode(roleTag, "inline-flex");
        } else {
          setDisplayMode(roleTag, "none");
          roleTag.textContent = "";
          roleTag.removeAttribute("title");
          roleTag.removeAttribute("aria-label");
        }
      }
      if (logoutBtn) {
        logoutBtn.textContent = "";
        logoutBtn.setAttribute("title", t("utility.logout"));
        logoutBtn.setAttribute("aria-label", t("utility.logout"));
        setDisplayMode(logoutBtn, enabled ? "inline-flex" : "none");
      }
      if (prefsResetBtn) {
        setDisplayMode(prefsResetBtn, enabled && authenticated ? "inline-flex" : "none");
      }
    }

    function clearDashboardSearchAutofill() {
      const barcodeInput = $("homeDashSearchBarcode");
      if (!barcodeInput) return;
      const username = String(appAuthSession?.username || "").trim();
      const currentValue = String(barcodeInput.value || "").trim();
      if (!currentValue) return;
      if (username && currentValue === username) {
        barcodeInput.value = "";
      }
    }

    function applyAuthSessionUi() {
      appShellMode = normalizeShellMode(appShellMode || shellModeFromPath(), appAuthSession);
      applyShellNavigation(appAuthSession);
    }

    function loadAdminBootstrapData() {
      if (!isAdminSession()) return;
      loadOpsCameras({ silent: true });
      loadReviewQueue();
      loadAlbumMasterGroups();
      loadMetadataSyncStatus();
      loadOpsSystemStatus();
      loadErrorBadge();
    }

    async function loadAuthSession(initialShellMode) {
      try {
        const res = await fetch("/auth/session");
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("auth.session.error"));
        appAuthSession = data;
        appAuthSessionResolved = true;
        renderAuthSession();
        applyAuthSessionUi();
        clearDashboardSearchAutofill();
        renderOpsExceptionPresetOptions();
        applyDefaultOpsExceptionPreset();
        applyRouteSelectedShellMode(initialShellMode);
        renderOpsLibraryContextDefault();
        loadOperatorHomeRecentSections();
        loadOperatorHomeFeed({ kind: operatorFeedKind, page: operatorFeedPage });
        loadAdminBootstrapData();
      } catch (_) {
        appAuthSession = null;
        appAuthSessionResolved = true;
        renderAuthSession();
        applyAuthSessionUi();
        clearDashboardSearchAutofill();
        renderOpsExceptionPresetOptions();
        applyRouteSelectedShellMode(initialShellMode);
        renderOpsLibraryContextDefault();
        loadOperatorHomeRecentSections();
        loadOperatorHomeFeed({ kind: operatorFeedKind, page: operatorFeedPage });
      }
    }

    async function logoutAppSession() {
      try {
        const res = await fetch("/auth/logout", { method: "POST" });
        await safeJson(res);
      } finally {
        window.location.replace("/login");
      }
    }

    function localizeServerDetailText(value) {
      const text = String(value || "").trim();
      if (!text) return "";
      if (text === "아이디 또는 비밀번호가 올바르지 않습니다.") return t("server.error.auth.invalid_credentials");
      if (text === "구매 항목에 상품 상세 URL이 없습니다.") return t("server.error.purchase.detail_url_missing");
      if (text === "현재는 Amazon/eBay 상품 상세 페이지만 보강할 수 있습니다.") return t("server.error.purchase.detail_page_unsupported");
      if (text === "구매 수입 큐 항목에서 후보 조회용 상품명/아티스트 정보를 찾지 못했습니다.") return t("server.error.purchase.lookup_query_missing");
      if (text === "이미 존재하는 계정입니다.") return t("server.error.account.exists");
      if (text === "계정을 찾을 수 없습니다.") return t("server.error.account.not_found");
      if (text === "관리 계정을 찾을 수 없습니다.") return t("server.error.account.managed_not_found");
      if (text === "계정 저장에 실패했습니다.") return t("server.error.account.save_failed");
      if (text === "계정 수정에 실패했습니다.") return t("server.error.account.update_failed");
      if (text === "계정 삭제에 실패했습니다.") return t("server.error.account.delete_failed");
      if (text === "유효한 ONVIF 장치 URL이 아닙니다.") return t("server.error.camera.invalid_url");
      if (text === "복구 파일의 SQLite 무결성 검사에 실패했습니다.") return t("server.error.restore.sqlite_integrity_failed");
      if (text === "복구 파일이 라이브러리 DB 형식이 아닙니다.") return t("server.error.restore.not_library_db");
      if (text === "복구 파일이 유효한 SQLite DB가 아닙니다.") return t("server.error.restore.invalid_sqlite");
      if (text === "메타 동기화 실행 중에는 DB 복구를 시작할 수 없습니다.") return t("server.error.restore.metadata_sync_running");
      if (text === "복구 파일이 유효한 ZIP 백업이 아닙니다.") return t("server.error.restore.invalid_zip");
      if (text === "복구 ZIP 파일이 손상되었습니다.") return t("server.error.restore.zip_corrupt");
      if (text === "복구 ZIP 파일 경로가 올바르지 않습니다.") return t("server.error.restore.zip_path_invalid");
      if (text === "복구 파일에 library.db가 없습니다.") return t("server.error.restore.zip_missing_db");
      if (text.startsWith("구매 내역 파일 디코딩 실패:")) {
        return t("server.error.purchase.decode_failed", { message: text.slice("구매 내역 파일 디코딩 실패:".length).trim() });
      }
      if (text.startsWith("ONVIF 응답 오류:")) {
        return t("server.error.camera.onvif_response", { status: text.slice("ONVIF 응답 오류:".length).trim() });
      }
      if (text.startsWith("ONVIF 연결 테스트 실패:")) {
        return t("server.error.camera.onvif_test_failed", { message: text.slice("ONVIF 연결 테스트 실패:".length).trim() });
      }
      if (text.startsWith("DB 복구 실패:")) {
        return t("server.error.restore.db_failed_detail", { message: text.slice("DB 복구 실패:".length).trim() });
      }
      if (text.startsWith("전체 백업 복구 실패:")) {
        return t("server.error.restore.bundle_failed_detail", { message: text.slice("전체 백업 복구 실패:".length).trim() });
      }
      return text;
    }

    function detailText(value) {
      if (value == null) return "";
      if (typeof value === "string") return localizeServerDetailText(value);
      if (Array.isArray(value)) {
        return value.map((row) => detailText(row)).filter((row) => row).join(" / ");
      }
      if (typeof value === "object") {
        const loc = Array.isArray(value.loc)
          ? value.loc.map((row) => String(row || "").trim()).filter((row) => row).join(".")
          : "";
        const msg = typeof value.msg === "string" ? localizeServerDetailText(value.msg) : "";
        if (loc || msg) return [loc, msg].filter((row) => row).join(": ");
        const detail = typeof value.detail === "string" ? localizeServerDetailText(value.detail) : "";
        if (detail) return detail;
        try {
          return JSON.stringify(value);
        } catch (_) {
          return String(value);
        }
      }
      return String(value || "").trim();
    }

    function responseDetailText(data, fallback) {
      return detailText(data?.detail) || fallback;
    }

    function errorMessageText(err, fallback = t("common.request_failed")) {
      return detailText(err?.message ?? err) || fallback;
    }

    function retryingStatusText(label, attempt, total) {
      return t("common.request_retrying", {
        label: String(label || "").trim() || t("common.request_failed"),
        attempt,
        total,
      });
    }

    function discogsRepairButtonHtml(scope, ownedItemId) {
      const id = Number(ownedItemId || 0);
      if (id <= 0) return "";
      if (scope === "home") {
        return `<button class="btn ghost tiny home-master-member-preview-repair-btn" type="button" data-home-repair-discogs-master="${id}">${escapeHtml(t("media.manage.search.repair_discogs_master"))}</button>`;
      }
      return `<button class="btn ghost tiny operator-recent-repair-btn" type="button" data-operator-repair-discogs-master="${id}">${escapeHtml(t("operator.feed.action.repair_discogs_master"))}</button>`;
    }

    function discogsRepairSlotHtml(scope, { ownedItemId, sourceCode, masterSourceCode, sourceExternalId }) {
      if (!isDiscogsRepairCandidate({ ownedItemId, sourceCode, masterSourceCode, sourceExternalId })) return "";
      const id = Number(ownedItemId || 0);
      const slotClassName = scope === "home" ? "home-master-member-preview-repair-slot" : "operator-recent-actions";
      const scopeAttr = scope === "home" ? `data-home-discogs-repair-slot="${id}"` : `data-operator-discogs-repair-slot="${id}"`;
      return `<div class="${slotClassName}" ${scopeAttr} data-discogs-repair-slot-scope="${escapeHtml(scope)}" data-owned-item-id="${id}" data-source-code="${escapeHtml(normalizeSourceCode(sourceCode))}" data-master-source-code="${escapeHtml(normalizeSourceCode(masterSourceCode))}" data-source-external-id="${escapeHtml(String(sourceExternalId || "").trim())}"></div>`;
    }

    async function loadDiscogsRepairEligibilityStatus(ownedItemId, options = {}) {
      const id = Number(ownedItemId || 0);
      if (!isDiscogsRepairCandidate({
        ownedItemId: id,
        sourceCode: options?.sourceCode,
        masterSourceCode: options?.masterSourceCode,
        sourceExternalId: options?.sourceExternalId,
      })) {
        return { eligible: false, reason: "not_candidate" };
      }
      const cached = discogsRepairEligibilityCache.get(id);
      if (cached?.status) return cached.status;
      if (cached?.promise) return cached.promise;
      const promise = (async () => {
        try {
          const res = await fetchWithRetry(`/owned-items/${id}/discogs-repair-status`, {}, {
            retries: 1,
            retryDelayMs: 200,
          });
          const data = await safeJson(res);
          const status = {
            eligible: Boolean(res.ok && data?.eligible === true),
            reason: String(data?.reason || "").trim() || (res.ok ? "discogs_master_not_found" : "unavailable"),
          };
          discogsRepairEligibilityCache.set(id, { status });
          return status;
        } catch (_err) {
          const status = { eligible: false, reason: "unavailable" };
          discogsRepairEligibilityCache.set(id, { status });
          return status;
        }
      })();
      discogsRepairEligibilityCache.set(id, { promise });
      return promise;
    }

    async function hydrateDiscogsRepairButtons(root = document) {
      const scopeRoot = root && typeof root.querySelectorAll === "function" ? root : document;
      const slots = Array.from(scopeRoot.querySelectorAll("[data-discogs-repair-slot-scope]"));
      if (!slots.length) return;
      await Promise.all(slots.map(async (slot) => {
        if (!slot || slot.dataset.repairHydrated === "1") return;
        slot.dataset.repairHydrated = "1";
        const ownedItemId = Number(slot.getAttribute("data-owned-item-id") || 0);
        const sourceCode = slot.getAttribute("data-source-code") || "";
        const masterSourceCode = slot.getAttribute("data-master-source-code") || "";
        const sourceExternalId = slot.getAttribute("data-source-external-id") || "";
        const scope = String(slot.getAttribute("data-discogs-repair-slot-scope") || "").trim() || "operator";
        const status = await loadDiscogsRepairEligibilityStatus(ownedItemId, {
          sourceCode,
          masterSourceCode,
          sourceExternalId,
        });
        if (!slot.isConnected) return;
        if (!status?.eligible) {
          slot.remove();
          return;
        }
        slot.innerHTML = discogsRepairButtonHtml(scope, ownedItemId);
      }));
    }

    function queueDiscogsRepairEligibilityHydration(root = document) {
      window.requestAnimationFrame(() => {
        hydrateDiscogsRepairButtons(root).catch(() => {});
      });
    }

    function discogsReleaseUrl(externalId) {
      const id = String(externalId || "").trim();
      if (!id) return "";
      return `https://www.discogs.com/release/${encodeURIComponent(id)}`;
    }

    function discogsReleaseLinkHtml(sourceCode, externalId, label = "Discogs") {
      if (normalizeSourceCode(sourceCode) !== "DISCOGS") return "";
      const href = discogsReleaseUrl(externalId);
      if (!href) return "";
      return `<a href="${href}" target="_blank" rel="noreferrer noopener">${escapeHtml(label)}</a>`;
    }

    function discogsMasterLinkHtml(masterSourceId, label = "Discogs 마스터") {
      const id = String(masterSourceId || "").trim();
      if (!id) return "";
      return `<a href="https://www.discogs.com/master/${encodeURIComponent(id)}" target="_blank" rel="noreferrer noopener">${escapeHtml(label)}</a>`;
    }

    function maniadbAlbumLinkHtml(albumId, label = "ManiaDB 앨범") {
      // 마스터(앨범) 수준 링크 — 쿼리 파라미터 없음
      const id = String(albumId || "").trim();
      if (!id) return "";
      return `<a href="http://www.maniadb.com/album/${encodeURIComponent(id)}" target="_blank" rel="noreferrer noopener">${escapeHtml(label)}</a>`;
    }

    // 소스별 개별 상품(릴리즈) 링크 — DISCOGS·MANIADB·ALADIN 통합
    function itemSourceLinkHtml(sourceCode, externalId, label) {
      const source = normalizeSourceCode(sourceCode);
      const id = String(externalId || "").trim();
      if (!id) return "";
      if (source === "DISCOGS") {
        return discogsReleaseLinkHtml(sourceCode, externalId, label || "Discogs");
      }
      if (source === "MANIADB") {
        // external_id 형식: "{album_id}" 또는 "{album_id}:{variant_seq}"
        // URL: maniadb.com/album/{album_id}?o=l&s={variant_seq}
        const colonIdx = id.indexOf(":");
        const albumId = colonIdx >= 0 ? id.slice(0, colonIdx).trim() : id;
        const variantSeq = colonIdx >= 0 ? id.slice(colonIdx + 1).trim() : "";
        if (!albumId) return "";
        const href = variantSeq
          ? `http://www.maniadb.com/album/${encodeURIComponent(albumId)}?o=l&s=${encodeURIComponent(variantSeq)}`
          : `http://www.maniadb.com/album/${encodeURIComponent(albumId)}`;
        return `<a href="${href}" target="_blank" rel="noreferrer noopener">${escapeHtml(label || "ManiaDB")}</a>`;
      }
      if (source === "ALADIN") {
        return `<a href="https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=${encodeURIComponent(id)}" target="_blank" rel="noreferrer noopener">${escapeHtml(label || "Aladin")}</a>`;
      }
      return "";
    }

    function buildDiscogsStandardMetaHtml(row, opts = {}) {
      const sourceCode = normalizeSourceCode(row?.source || "");
      if (!sourceCode) return "";
      const includeOwnedCount = opts.includeOwnedCount === true;
      const ownedCountClassName = String(opts.ownedCountClassName || "").trim();
      const releaseDate = String(row?.released_date || row?.release_year || "").trim() || "-";
      const releaseCountry = String(row?.pressing_country || row?.country || "").trim() || "-";
      const labelName = String(row?.label_name || "").trim() || "-";
      const catalogNo = String(row?.catalog_no || "").trim() || "-";
      const barcode = String(row?.barcode || "").trim() || "-";
      const formatLabel = mediaDisplayLabel(row?.format_name || row?.category || row?.media_type || "-");
      const trackCount = Array.isArray(row?.track_list)
        ? row.track_list.length
        : Math.max(0, Number(row?.track_count || row?.tracks || 0));
      const parts = [
        t("common.meta.release_date", { value: escapeHtml(releaseDate) }),
        t("common.meta.release_country", { value: escapeHtml(releaseCountry) }),
        t("common.meta.label", { value: escapeHtml(labelName) }),
        t("common.meta.catalog_no", { value: escapeHtml(catalogNo) }),
        t("common.meta.barcode", { value: escapeHtml(barcode) }),
        t("common.meta.format", { value: escapeHtml(formatLabel) }),
        t("common.meta.track_count", { value: escapeHtml(String(trackCount)) }),
      ];
      if (includeOwnedCount && Number(row?.owned_count || 0) > 0) {
        const ownedText = escapeHtml(t("common.meta.already_owned", { count: formatCount(Number(row.owned_count || 0)) }));
        parts.push(ownedCountClassName
          ? `<span class="${escapeHtml(ownedCountClassName)}">${ownedText}</span>`
          : `<span>${ownedText}</span>`);
      }
      return parts.map((text) => text.startsWith("<span") ? text : `<span>${text}</span>`).join("");
    }

    function collectGalleryItems(row) {
      const out = [];
      const seen = new Set();
      const push = (url, thumb, label, type = "IMAGE") => {
        const src = normalizeRenderableCoverUrl(url);
        if (!src || seen.has(src)) return;
        seen.add(src);
        const normalizedThumb = normalizeRenderableCoverUrl(thumb) || src;
        out.push({
          url: src,
          thumb: normalizedThumb,
          label: String(label || "").trim() || t("common.image"),
          type: String(type || "IMAGE").trim().toUpperCase(),
        });
      };

      const coverUrl = normalizeRenderableCoverUrl(row?.cover_image_url);
      if (coverUrl) push(coverUrl, coverUrl, t("image_gallery.label.cover"), "COVER");

      const imageItems = Array.isArray(row?.image_items) ? row.image_items : [];
      for (const item of imageItems) {
        if (!item || typeof item !== "object") continue;
        const url = normalizeRenderableCoverUrl(item.uri || item.url || item.resource_url);
        const thumb = normalizeRenderableCoverUrl(item.uri150 || item.thumb || item.thumbnail_url || url);
        const type = String(item.type || item.kind || "IMAGE").trim().toUpperCase();
        const label = type === "PRIMARY"
          ? t("image_gallery.label.primary")
          : (type === "SECONDARY" ? t("image_gallery.label.secondary") : type);
        push(url, thumb, label, type);
      }
      return out;
    }

    function imageGalleryButtonHtml(key, label = "") {
      const galleryKey = String(key || "").trim();
      if (!galleryKey) return "";
      return `<button class="btn ghost image-gallery-open-btn" type="button" data-open-image-gallery="${escapeHtml(galleryKey)}">${escapeHtml(label || t("common.image"))}</button>`;
    }

    function renderImageGalleryModal() {
      const items = Array.isArray(imageGalleryCurrentItems) ? imageGalleryCurrentItems : [];
      const current = items[imageGalleryCurrentIndex] || null;
      $("imageGalleryPreviewImg").src = current?.url || "";
      setDisplayMode($("imageGalleryPreviewImg"), current?.url ? "block" : "none");
      $("imageGalleryPreviewImg").alt = current?.label || t("image_gallery.preview.alt");
      $("imageGallerySourceText").textContent = imageGalleryRegistry.get(imageGalleryCurrentKey)?.subtitle || t("image_gallery.subtitle.default");
      $("imageGalleryCountText").textContent = t("common.count.images", { count: items.length });
      $("imageGalleryOpenOriginal").href = current?.url || "#";
      $("imageGalleryOpenOriginal").style.pointerEvents = current?.url ? "auto" : "none";
      $("imageGalleryOpenOriginal").style.opacity = current?.url ? "1" : "0.45";
      $("imageGalleryPreviewMeta").innerHTML = current
        ? [
            `<span class="tag">${escapeHtml(current.label || t("common.image"))}</span>`,
            `<span>${escapeHtml(current.type || t("common.image"))}</span>`,
            `<span>${escapeHtml(current.url)}</span>`,
          ].join("")
        : `<span>${escapeHtml(t("image_gallery.meta.empty"))}</span>`;
      $("imageGalleryList").innerHTML = items.map((item, idx) => `
        <button class="image-gallery-thumb ${idx === imageGalleryCurrentIndex ? "active" : ""}" type="button" data-image-gallery-index="${idx}">
          <img src="${escapeHtml(item.thumb || item.url)}" alt="${escapeHtml(item.label || t("common.image"))}" />
          <div>
            <strong class="image-gallery-thumb-label">${escapeHtml(item.label || t("common.image"))}</strong>
            <div class="mini">${escapeHtml(item.type || t("common.image"))}</div>
          </div>
        </button>
      `).join("");
    }

    function openImageGallery(key) {
      const galleryKey = String(key || "").trim();
      const entry = imageGalleryRegistry.get(galleryKey);
      if (!entry || !Array.isArray(entry.items) || !entry.items.length) return;
      imageGalleryCurrentKey = galleryKey;
      imageGalleryCurrentItems = entry.items.slice();
      imageGalleryCurrentIndex = 0;
      $("imageGalleryTitle").textContent = entry.title || t("image_gallery.title.default");
      $("imageGalleryModal").classList.add("open");
      $("imageGalleryModal").setAttribute("aria-hidden", "false");
      renderImageGalleryModal();
    }

    function closeImageGallery() {
      imageGalleryCurrentKey = "";
      imageGalleryCurrentItems = [];
      imageGalleryCurrentIndex = 0;
      $("imageGalleryModal").classList.remove("open");
      $("imageGalleryModal").setAttribute("aria-hidden", "true");
    }

    function currentLocaleTag() {
      if (appLocale === "en") return "en-US";
      if (appLocale === "ja") return "ja-JP";
      return "ko-KR";
    }

    function countWithUnit(v) {
      return t("common.count.items", { count: formatCount(v) });
    }

    function clearOperatorRequestForm() {
      $("operatorRequestTrack").value = "";
      $("operatorRequestOwnedItemId").value = "";
      $("operatorRequestMatchedTrack").value = "";
      $("operatorRequestMatchedTrackNo").value = "";
      $("operatorRequestCustomerNote").value = "";
      $("operatorRequestItemText").value = "";
    }

    function fillOperatorRequestForm(row, trackTitle = "", trackNo = "") {
      $("operatorRequestOwnedItemId").value = Number(row?.owned_item_id || row?.id || 0) || "";
      $("operatorRequestTrack").value = String(trackTitle || row?.requested_track || "").trim();
      $("operatorRequestMatchedTrack").value = String(trackTitle || row?.matched_track_title || "").trim();
      $("operatorRequestMatchedTrackNo").value = trackNo ? String(trackNo) : (row?.matched_track_no ? String(row.matched_track_no) : "");
      const itemTitle = String(row?.item_title || row?.item_name_override || "-").trim() || "-";
      const artist = String(row?.artist_or_brand || "").trim();
      $("operatorRequestItemText").value = `${itemTitle}${artist ? ` / ${artist}` : ""}`;
    }

    function buildOperatorCabinetTripletLabel(cabinetName, columnCode, cellCode) {
      const safeCabinetName = String(cabinetName || "").trim();
      const safeColumnCode = String(columnCode || "").trim();
      const safeCellCode = String(cellCode || "").trim();
      if (!(safeCabinetName && safeColumnCode && safeCellCode)) return "";
      return `${safeCabinetName} / ${dashboardColumnCodeLabel(safeColumnCode)} / ${dashboardCellCodeLabel(safeCellCode)}`;
    }

    function localizeOperatorSlotDisplayName(displayName) {
      const text = String(displayName || "").trim();
      if (!text || isOperatorUnslottedLabel(text)) return "";
      const parts = text.split("/").map((part) => String(part || "").trim()).filter(Boolean);
      if (parts.length === 3 && /열$/.test(parts[1]) && /칸$/.test(parts[2])) {
        const localized = buildOperatorCabinetTripletLabel(
          parts[0],
          parts[1].replace(/열$/, "").trim(),
          parts[2].replace(/칸$/, "").trim()
        );
        if (localized) return localized;
      }
      return text;
    }

    function buildOperatorSlotDisplayLabel(displayName, slotCode, cabinetName, columnCode, cellCode) {
      const localizedTriplet = buildOperatorCabinetTripletLabel(cabinetName, columnCode, cellCode);
      if (localizedTriplet) return localizedTriplet;
      const localizedDisplayName = localizeOperatorSlotDisplayName(displayName);
      if (localizedDisplayName) return localizedDisplayName;
      const safeSlotCode = String(slotCode || "").trim();
      if (safeSlotCode) return safeSlotCode;
      return t("operator.feed.state.unslotted");
    }

    function buildOperatorPreviousLocationLabel(row) {
      const previousDisplayName = String(row?.previous_slot_display_name || "").trim();
      const previousSlotCode = String(row?.previous_slot_code || "").trim();
      if (!previousDisplayName && !previousSlotCode) return "-";
      if (isOperatorUnslottedLabel(previousDisplayName || previousSlotCode)) return t("operator.feed.state.unslotted");
      return buildOperatorSlotDisplayLabel(previousDisplayName, previousSlotCode, "", "", "") || "-";
    }

    function hasOperatorCurrentLocation(row) {
      const currentSlotCode = String(row?.current_slot_code || "").trim();
      const currentDisplayName = String(row?.current_slot_display_name || "").trim();
      const currentCabinetName = String(row?.current_cabinet_name || "").trim();
      const currentColumnCode = String(row?.current_column_code || "").trim();
      const currentCellCode = String(row?.current_cell_code || "").trim();
      return Boolean(
        currentSlotCode
        || (currentDisplayName && !isOperatorUnslottedLabel(currentDisplayName))
        || (currentCabinetName && currentColumnCode && currentCellCode)
      );
    }

    function buildOperatorLocationLabel(row) {
      const currentDisplayName = String(row?.current_slot_display_name || "").trim();
      const currentCabinetName = String(row?.current_cabinet_name || "").trim();
      const currentColumnCode = String(row?.current_column_code || "").trim();
      const currentCellCode = String(row?.current_cell_code || "").trim();
      const currentSlotCode = String(row?.current_slot_code || "").trim();
      return buildOperatorSlotDisplayLabel(
        currentDisplayName,
        currentSlotCode,
        currentCabinetName,
        currentColumnCode,
        currentCellCode
      );
    }

    function buildOperatorDisplayTitleParts(row) {
      let title = String(row?.item_title || row?.item_name_override || "-").trim() || "-";
      const artist = String(row?.artist_or_brand || "").trim();
      if (!artist) return { title, artist: "" };
      const artistPrefix = `${artist} - `.toLowerCase();
      if (title.toLowerCase().startsWith(artistPrefix)) {
        title = title.slice(artistPrefix.length).trim() || title;
      }
      if (title.toLowerCase().endsWith(artist.toLowerCase())) {
        title = title.slice(0, title.length - artist.length).replace(/[\s/|·-]+$/, "").trim() || title;
      }
      return { title, artist };
    }

    function exactTitleArtistMatch(row, normalizedQuery) {
      const comparableQuery = normalizeOpsLookupComparable(normalizedQuery);
      if (!comparableQuery) return false;
      const title = String(row?.item_title || row?.item_name_override || "").trim();
      const artist = String(row?.artist_or_brand || "").trim();
      return [
        title,
        artist,
        [title, artist].filter(Boolean).join(" "),
        [artist, title].filter(Boolean).join(" "),
      ].some((candidate) => normalizeOpsLookupComparable(candidate) === comparableQuery);
    }

    function emptyOperatorLookupSummary(normalizedQuery = "", status = "idle") {
      return {
        normalizedQuery,
        topCandidate: null,
        locationSummary: null,
        status,
        matchReason: "",
      };
    }

    function summarizeOperatorResults(results, normalizedQuery) {
      const list = Array.isArray(results) ? results : [];
      const normalizedDigits = normalizeDigits(normalizedQuery);
      const exactBarcode = normalizedDigits
        ? list.find((row) => normalizeDigits(row?.barcode) === normalizedDigits)
        : null;
      const exactLabel = list.find((row) => normalizeOpsLookupComparable(row?.label_id) === normalizeOpsLookupComparable(normalizedQuery));
      const exactTitleArtist = list.find((row) => exactTitleArtistMatch(row, normalizedQuery));
      const assigned = list.find((row) => hasOperatorCurrentLocation(row));
      const topCandidate = exactBarcode || exactLabel || exactTitleArtist || assigned || list[0] || null;
      const matchReason = exactBarcode
        ? "barcode"
        : exactLabel
          ? "label"
          : exactTitleArtist
            ? "titleArtist"
            : assigned
              ? "assigned"
              : topCandidate
                ? "first"
                : "";
      return {
        normalizedQuery,
        topCandidate,
        locationSummary: topCandidate ? buildOperatorLocationLabel(topCandidate) : null,
        status: topCandidate ? "match" : "empty",
        matchReason,
      };
    }

    function buildOperatorLookupSummary(results, normalizedQuery, status = "") {
      const normalized = normalizeOpsLookupQuery(normalizedQuery);
      if (!normalized) return emptyOperatorLookupSummary();
      if (status === "error") return emptyOperatorLookupSummary(normalized, "error");
      if (!Array.isArray(results) || !results.length) return emptyOperatorLookupSummary(normalized, "empty");
      return summarizeOperatorResults(results, normalized);
    }

    function setOperatorLookupResults(results, normalizedQuery, status = "") {
      operatorLookupResults = Array.isArray(results) ? results : [];
      operatorLookupSummary = buildOperatorLookupSummary(operatorLookupResults, normalizedQuery, status);
      homeSelectedContextItem = null;
      homePreviewContextItem = null;
      renderOperatorLookupResults();
      renderOpsLibraryContextDefault();
    }

    async function loadOperatorOfficeClimate() {
      const res = await fetch("/operator/office-climate");
      const data = await safeJson(res);
      if (!res.ok) throw new Error(responseDetailText(data, t("operator.weather.status.office_load_failed")));
      if (!data || !data.available) return null;
      return data;
    }

    function renderAlbumReviewSection(item) {
      const text = String(item?.review_text || "").trim();
      if (!text) return "";
      const source = String(item?.review_source || "").trim();
      const reviewUrl = String(item?.review_url || "").trim();
      const TRUNCATE_LEN = 200;
      const needsTruncate = text.length > TRUNCATE_LEN;
      const previewText = needsTruncate ? text.slice(0, TRUNCATE_LEN) + "…" : text;
      const cardId = "albumReviewCard_" + String(item?.owned_item_id || item?.id || 0);
      const textId = "albumReviewText_" + String(item?.owned_item_id || item?.id || 0);
      const btnId = "albumReviewToggleBtn_" + String(item?.owned_item_id || item?.id || 0);
      const expandLabel = escapeHtml(t("media.search.context.review_expand") || "펼치기 ▼");
      const collapseLabel = escapeHtml(t("media.search.context.review_collapse") || "접기 ▲");

      return `
        <section id="${escapeHtml(cardId)}" class="operator-mini-card ops-album-review-card">
          <div class="ops-artist-context-head">
            <strong>${escapeHtml(t("media.search.context.review_label") || "앨범 리뷰")}</strong>
          </div>
          <div class="ops-artist-context-summary-wrap">
            <p class="ops-artist-context-summary" id="${escapeHtml(textId)}">${escapeHtml(previewText)}</p>
            ${needsTruncate ? `
              <button
                type="button"
                class="ops-artist-context-toggle"
                id="${escapeHtml(btnId)}"
                data-review-full="${escapeHtml(text)}"
                data-review-preview="${escapeHtml(previewText)}"
                data-show-label="${expandLabel}"
                data-hide-label="${collapseLabel}"
                data-expanded="false"
                aria-expanded="false"
              >${expandLabel}</button>
            ` : ""}
          </div>
          ${source ? `<div class="ops-artist-context-meta"><span class="ops-artist-context-pill"><strong>${escapeHtml(t("media.search.context.review_source_label") || "출처")}</strong>${reviewUrl ? `<a href="${escapeHtml(reviewUrl)}" target="_blank" rel="noopener">${escapeHtml(source)}</a>` : escapeHtml(source)}</span></div>` : ""}
        </section>
      `;
    }

    function currentHomeMasterId() {
      return Number(homeMasterInfo?.album_master_id || homeSelectedMasterId || 0) || null;
    }

    async function refreshCurrentMasterReview(masterId) {
      const res = await fetchWithRetry(`/album-masters/${masterId}`);
      const data = await res.json();
      renderHomeMasterReviewSection(data);
    }

    function normalizedOpsArtistContextCacheKey(value) {
      if (typeof value === "string") {
        return [String(value || "").trim().replace(/\s+/g, " ").toLowerCase(), appLocale].filter(Boolean).join("::");
      }
      const artistName = String(value?.artist_or_brand || value?.artist_name || "").trim().replace(/\s+/g, " ").toLowerCase();
      const category = String(value?.format_name || value?.category || "").trim().replace(/\s+/g, " ").toLowerCase();
      return [artistName, category, appLocale].filter(Boolean).join("::");
    }

    function normalizeOpsArtistContextPayload(payload, item = null) {
      const artistName = String(payload?.artist_name || item?.artist_or_brand || "").trim();
      const imageUrl = String(payload?.image_url || "").trim();
      return {
        available: Boolean(payload?.available),
        artist_name: artistName,
        summary: payload?.summary == null ? null : String(payload.summary),
        summary_original: payload?.summary_original == null ? null : String(payload.summary_original),
        image_url: /^https?:\/\//i.test(imageUrl) ? imageUrl : null,
        country: payload?.country == null ? null : String(payload.country).trim(),
        active_years: payload?.active_years == null ? null : String(payload.active_years).trim(),
        genres: Array.isArray(payload?.genres)
          ? payload.genres.map((value) => String(value || "").trim()).filter(Boolean)
          : [],
        links: Array.isArray(payload?.links)
          ? payload.links
            .map((link) => ({
              label: String(link?.label || "").trim(),
              url: String(link?.url || "").trim(),
            }))
            .filter((link) => link.label && /^https?:\/\//i.test(link.url))
          : [],
      };
    }

    async function loadOpsArtistContext(item, options = {}) {
      const cardId = String(options.cardId || "opsArtistContextCard");
      const getActiveItem = typeof options.getActiveItem === "function"
        ? options.getActiveItem
        : (() => homeSelectedContextItem || homePreviewContextItem || null);
      const cacheKey = normalizedOpsArtistContextCacheKey(item);
      const activeItem = getActiveItem();
      if (!cacheKey) {
        const emptyRoot = $(cardId);
        if (emptyRoot && activeItem === item) emptyRoot.outerHTML = renderOpsArtistContextUnavailable(item, null, { cardId });
        return;
      }
      if (opsArtistContextCache.has(cacheKey)) {
        const cachedPayload = opsArtistContextCache.get(cacheKey);
        const cachedRoot = $(cardId);
        if (cachedRoot && normalizedOpsArtistContextCacheKey(activeItem) === cacheKey) {
          cachedRoot.outerHTML = cachedPayload?.available
            ? renderOpsArtistContextReady(cachedPayload, { cardId })
            : renderOpsArtistContextUnavailable(item, cachedPayload, { cardId });
        }
        return;
      }
      const requestSeq = ++opsArtistContextRequestSeq;
      opsArtistContextLoadingKey = cacheKey;
      try {
        const res = await fetch("/ops/artist-context", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            artist_name: String(item?.artist_or_brand || "").trim(),
            category: String(item?.format_name || item?.category || "").trim() || null,
            locale: appLocale,
          }),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error("artist_context_unavailable");
        const payload = normalizeOpsArtistContextPayload(data, item);
        if (payload.available) opsArtistContextCache.set(cacheKey, payload);
        const nextActiveItem = getActiveItem();
        if (requestSeq !== opsArtistContextRequestSeq) return;
        if (normalizedOpsArtistContextCacheKey(nextActiveItem) !== cacheKey) return;
        const nextRoot = $(cardId);
        if (nextRoot) {
          nextRoot.outerHTML = payload.available
            ? renderOpsArtistContextReady(payload, { cardId })
            : renderOpsArtistContextUnavailable(item, payload, { cardId });
        }
      } catch (_) {
        const payload = normalizeOpsArtistContextPayload({ available: false }, item);
        const nextActiveItem = getActiveItem();
        if (requestSeq !== opsArtistContextRequestSeq) return;
        if (normalizedOpsArtistContextCacheKey(nextActiveItem) !== cacheKey) return;
        const nextRoot = $(cardId);
        if (nextRoot) nextRoot.outerHTML = renderOpsArtistContextUnavailable(item, payload, { cardId });
      } finally {
        if (opsArtistContextLoadingKey === cacheKey) {
          opsArtistContextLoadingKey = "";
        }
      }
    }

    function getOpsPlacementHintOwnedItemId(item) {
      return Number(item?.owned_item_id || item?.id || 0);
    }

    function getOpsPlacementHintRows(payload) {
      if (!payload || typeof payload !== "object") return [];
      if (Array.isArray(payload.recommendations)) return payload.recommendations.filter((row) => row && typeof row === "object");
      if (Array.isArray(payload.rows)) return payload.rows.filter((row) => row && typeof row === "object");
      if (Array.isArray(payload.items)) return payload.items.filter((row) => row && typeof row === "object");
      if (Array.isArray(payload.placements)) return payload.placements.filter((row) => row && typeof row === "object");
      if (Array.isArray(payload.hints)) return payload.hints.filter((row) => row && typeof row === "object");
      return [];
    }

    function isOpsPlacementHintUnslottedItem(item) {
      const slotCode = String(item?.current_slot_code || "").trim().toUpperCase();
      return !slotCode || slotCode === "UNASSIGNED";
    }

    function findOpsLibraryContextCabinet(item) {
      if (!item || !homeDashboardBySlot.length) return null;
      const slotCode = String(item?.current_slot_code || "").trim();
      const cabinetName = String(item?.current_cabinet_name || "").trim();
      if (cabinetName) {
        const rows = homeDashboardBySlot.filter((row) => String(row?.cabinet_name || "").trim() === cabinetName);
        if (rows.length) {
          const floorCodes = Array.from(new Set(rows.map((row) => String(row?.column_code || "").trim()).filter(Boolean)));
          return {
            title: cabinetName,
            rows,
            floorCodes,
            floorCount: floorCodes.length,
            slotCount: rows.length,
          };
        }
      }
      if (!slotCode) return null;
      const row = homeDashboardBySlot.find((entry) => String(entry?.slot_code || "").trim() === slotCode);
      if (!row) return null;
      const fallbackCabinetName = String(row?.cabinet_name || "").trim();
      if (!fallbackCabinetName) return null;
      const rows = homeDashboardBySlot.filter((entry) => String(entry?.cabinet_name || "").trim() === fallbackCabinetName);
      const floorCodes = Array.from(new Set(rows.map((entry) => String(entry?.column_code || "").trim()).filter(Boolean)));
      return {
        title: fallbackCabinetName,
        rows,
        floorCodes,
        floorCount: floorCodes.length,
        slotCount: rows.length,
      };
    }

    function findOpsLibraryContextCabinetGroup(item) {
      return findOpsLibraryContextCabinet(item);
    }

    function getOpsLibraryContextSlotPreviewRows(slotCode) {
      const normalizedSlotCode = String(slotCode || "").trim();
      if (!normalizedSlotCode || normalizedSlotCode === "UNASSIGNED") return null;
      if (homeDashboardSlotItemsSlotCode === normalizedSlotCode && !homeDashboardSlotItemsLoading) {
        return Array.isArray(homeDashboardSlotItems) ? homeDashboardSlotItems.slice(0, 6) : [];
      }
      if (opsLibraryContextSlotPreviewCache.has(normalizedSlotCode)) {
        return Array.isArray(opsLibraryContextSlotPreviewCache.get(normalizedSlotCode))
          ? opsLibraryContextSlotPreviewCache.get(normalizedSlotCode)
          : [];
      }
      return null;
    }

    async function loadOpsLibraryContextSlotPreview(item, options = {}) {
      const rootId = String(options.rootId || "opsLibraryContextSlotPreview");
      const getActiveItem = typeof options.getActiveItem === "function"
        ? options.getActiveItem
        : (() => homeSelectedContextItem || homePreviewContextItem || null);
      const slotCode = String(item?.current_slot_code || "").trim();
      const previewRoot = $(rootId);
      if (!previewRoot || !slotCode || slotCode === "UNASSIGNED") return;
      const existingRows = getOpsLibraryContextSlotPreviewRows(slotCode);
      if (existingRows !== null) {
        previewRoot.innerHTML = renderOpsLibraryContextSlotPreviewContent(item, existingRows);
        return;
      }
      const slotRow = getDashboardSlotRow(slotCode);
      const slotId = resolveDashboardStorageSlotId(slotRow);
      if (!slotId) {
        previewRoot.innerHTML = renderOpsLibraryContextSlotPreviewContent(item, [], { errorText: t("operator.context.preview.error.no_slot") });
        return;
      }
      const requestSeq = ++opsLibraryContextSlotPreviewRequestSeq;
      opsLibraryContextSlotPreviewLoadingSlotCode = slotCode;
      previewRoot.innerHTML = renderOpsLibraryContextSlotPreviewContent(item, null, { loading: true });
      try {
        const res = await fetch(`/storage-slots/${slotId}/owned-items?limit=6`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("operator.context.preview.error.load_failed")));
        const rows = Array.isArray(data) ? data : [];
        opsLibraryContextSlotPreviewCache.set(slotCode, rows);
        const activeItem = getActiveItem();
        if (requestSeq !== opsLibraryContextSlotPreviewRequestSeq) return;
        if (String(activeItem?.current_slot_code || "").trim() !== slotCode) return;
        const nextRoot = $(rootId);
        if (nextRoot) nextRoot.innerHTML = renderOpsLibraryContextSlotPreviewContent(item, rows);
      } catch (err) {
        const activeItem = getActiveItem();
        if (requestSeq !== opsLibraryContextSlotPreviewRequestSeq) return;
        if (String(activeItem?.current_slot_code || "").trim() !== slotCode) return;
        const nextRoot = $(rootId);
        if (nextRoot) {
          nextRoot.innerHTML = renderOpsLibraryContextSlotPreviewContent(item, [], {
            errorText: errorMessageText(err, t("operator.context.preview.error.load_failed")),
          });
        }
      } finally {
        if (opsLibraryContextSlotPreviewLoadingSlotCode === slotCode) {
          opsLibraryContextSlotPreviewLoadingSlotCode = "";
        }
      }
    }

    async function loadOpsPlacementHints(item, options = {}) {
      const cardId = String(options.cardId || "opsLibraryPlacementHintCard");
      const getActiveItem = typeof options.getActiveItem === "function"
        ? options.getActiveItem
        : (() => homeSelectedContextItem || homePreviewContextItem || null);
      const ownedItemId = getOpsPlacementHintOwnedItemId(item);
      const placementRoot = $(cardId);
      if (!placementRoot) return;
      if (ownedItemId <= 0) {
        placementRoot.innerHTML = renderOpsPlacementHintIdle(null, { cardId });
        return;
      }
      const cached = opsPlacementHintCache.get(ownedItemId) || null;
      if (cached) {
        placementRoot.innerHTML = cached.available === false
          ? renderOpsPlacementHintUnavailable(item, cached.message || cached.detail || "", { cardId })
          : renderOpsPlacementHintReady(item, cached, { cardId });
        return;
      }
      if (opsPlacementHintLoadingOwnedItemId === ownedItemId) {
        placementRoot.innerHTML = renderOpsPlacementHintLoading(item, { cardId });
        return;
      }
      const requestSeq = ++opsPlacementHintRequestSeq;
      opsPlacementHintLoadingOwnedItemId = ownedItemId;
      placementRoot.innerHTML = renderOpsPlacementHintLoading(item, { cardId });
      try {
        const res = await fetch("/ops/placement-hints", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ owned_item_id: ownedItemId }),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("operator.placement.state.unavailable")));
        const payload = data && typeof data === "object" ? data : {};
        opsPlacementHintCache.set(ownedItemId, payload);
        const activeItem = getActiveItem();
        if (requestSeq !== opsPlacementHintRequestSeq) return;
        if (getOpsPlacementHintOwnedItemId(activeItem) !== ownedItemId) return;
        const nextRoot = $(cardId);
        if (nextRoot) {
          nextRoot.innerHTML = payload.available === false
            ? renderOpsPlacementHintUnavailable(item, payload.message || payload.detail || "", { cardId })
            : renderOpsPlacementHintReady(item, payload, { cardId });
        }
      } catch (err) {
        const activeItem = getActiveItem();
        if (requestSeq !== opsPlacementHintRequestSeq) return;
        if (getOpsPlacementHintOwnedItemId(activeItem) !== ownedItemId) return;
        const nextRoot = $(cardId);
        if (nextRoot) {
          nextRoot.innerHTML = renderOpsPlacementHintUnavailable(item, errorMessageText(err, t("operator.placement.state.unavailable")), { cardId });
        }
      } finally {
        if (opsPlacementHintLoadingOwnedItemId === ownedItemId) {
          opsPlacementHintLoadingOwnedItemId = 0;
        }
      }
    }

    function clearOpsLibraryContextPreview() {
      if (!homePreviewContextItem) return;
      homePreviewContextItem = null;
      renderOpsLibraryContextDefault();
    }

    function setOpsLibraryContextSelectionFromTarget(target, options = {}) {
      const card = target?.closest?.("[data-operator-context-source][data-operator-context-index]");
      if (!card) return false;
      const source = String(card.getAttribute("data-operator-context-source") || "").trim();
      const index = Number(card.getAttribute("data-operator-context-index") || -1);
      const list = source === "feed" ? operatorFeedItems : operatorLookupResults;
      if (!Array.isArray(list) || !Number.isInteger(index) || index < 0 || index >= list.length) return false;
      const nextItem = list[index] || null;
      if (!nextItem) return false;
      if (options.pin) {
        homeSelectedContextItem = nextItem;
        homePreviewContextItem = null;
      } else {
        if (homeSelectedContextItem) return false;
        homePreviewContextItem = nextItem;
      }
      renderOpsLibraryContextDefault();
      return true;
    }

    async function loadOperatorWeather(force = false) {
      if (!appAuthSession?.authenticated) {
        renderOperatorWeatherEmpty();
        renderOpsLibraryContextDefault();
        setStatus("operatorWeatherStatus", "", "");
        return;
      }
      if (operatorWeatherState.loading) return;
      if (!force && operatorWeatherState.loadedAt && Date.now() - operatorWeatherState.loadedAt < 15 * 60 * 1000) {
        return;
      }
      operatorWeatherState.loading = true;
      setStatus("operatorWeatherStatus", "ok", t("operator.weather.status.loading"));
      renderOpsLibraryContextDefault();
      try {
        const officeClimate = await loadOperatorOfficeClimate();
        if (!officeClimate?.available) {
          throw new Error(t("operator.weather.status.load_failed"));
        }
        if (String(officeClimate.source || "").trim() === "seoul_weather") {
          renderOperatorSeoulWeather(officeClimate);
          setStatus("operatorWeatherStatus", "ok", t("operator.weather.status.seoul"));
        } else {
          renderOperatorOfficeClimate(officeClimate);
          setStatus("operatorWeatherStatus", "ok", t("operator.weather.status.office"));
        }
        renderOpsLibraryContextDefault();
        operatorWeatherState.loadedAt = Date.now();
      } catch (err) {
        renderOperatorWeatherEmpty();
        renderOpsLibraryContextDefault();
        setStatus("operatorWeatherStatus", "err", errorMessageText(err, t("operator.weather.status.load_failed")));
      } finally {
        operatorWeatherState.loading = false;
      }
    }

    function buildOperatorFeedPagerTokens(currentPage, totalPages) {
      if (totalPages <= 1) return [];
      const pages = new Set([1, totalPages]);
      const start = Math.max(1, currentPage - 2);
      const end = Math.min(totalPages, currentPage + 2);
      for (let page = start; page <= end; page += 1) {
        pages.add(page);
      }
      if (currentPage <= 3) {
        for (let page = 1; page <= Math.min(totalPages, 5); page += 1) {
          pages.add(page);
        }
      }
      if (currentPage >= totalPages - 2) {
        for (let page = Math.max(1, totalPages - 4); page <= totalPages; page += 1) {
          pages.add(page);
        }
      }
      const ordered = Array.from(pages).sort((a, b) => a - b);
      const tokens = [];
      ordered.forEach((page, index) => {
        if (index > 0 && page - ordered[index - 1] > 1) tokens.push("gap");
        tokens.push(page);
      });
      return tokens;
    }

    async function loadOperatorHomeRecentSections() {
      if (!appAuthSession?.authenticated) {
        recentMovedItems = [];
        recentRegisteredItems = [];
        renderOpsHomeHeroStats({ locationCount: 0, recentMoveCount: 0, recentRegistrationCount: 0, moveWindowDays: 1 });
        renderOperatorHomeRecentSections();
        return;
      }
      try {
        const res = await fetch("/operator/home/recent");
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("operator.lookup.status.feed_failed")));
        recentMovedItems = Array.isArray(data.recent_moved_items) ? data.recent_moved_items : [];
        recentRegisteredItems = Array.isArray(data.recent_registered_items) ? data.recent_registered_items : [];
        opsHomeHeroStats.recentMoveCount = Math.max(0, Number(data.recent_moved_total_count ?? recentMovedItems.length ?? 0));
        opsHomeHeroStats.recentRegistrationCount = Math.max(0, Number(data.recent_registered_total_count ?? recentRegisteredItems.length ?? 0));
      } catch (_) {
        recentMovedItems = [];
        recentRegisteredItems = [];
        opsHomeHeroStats.recentMoveCount = 0;
        opsHomeHeroStats.recentRegistrationCount = 0;
      }
      renderOpsHomeHeroStats({
        recentMoveCount: opsHomeHeroStats.recentMoveCount,
        recentRegistrationCount: opsHomeHeroStats.recentRegistrationCount,
        moveWindowDays: 1,
      });
      renderOperatorHomeRecentSections();
    }

    async function loadOperatorHomeFeed(options = {}) {
      const kind = String(options.kind || operatorFeedKind || "registered").trim() === "moved" ? "moved" : "registered";
      const page = Math.max(1, Number(options.page || operatorFeedPage || 1));
      const pinnedOwnedItemId = Number(homeSelectedContextItem?.owned_item_id || homeSelectedContextItem?.id || 0);
      operatorLookupMode = "FEED";
      operatorFeedKind = kind;
      operatorFeedPage = page;
      operatorLookupResults = [];
      homePreviewContextItem = null;
      operatorLookupSummary = emptyOperatorLookupSummary();
      updateOperatorFeedControls();
      if (!appAuthSession?.authenticated) {
        operatorFeedItems = [];
        operatorFeedTotalCount = 0;
        homeSelectedContextItem = null;
        renderOperatorLookupResults();
        renderOpsLibraryContextDefault();
        return;
      }
      try {
        const params = new URLSearchParams({
          kind,
          page: String(page),
          limit: String(operatorFeedPageSize),
        });
        const res = await fetch(`/operator/home/feed?${params.toString()}`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("operator.lookup.status.feed_failed")));
        operatorFeedItems = Array.isArray(data.items) ? data.items : [];
        operatorFeedTotalCount = Math.max(0, Number(data.total_count ?? operatorFeedItems.length ?? 0));
        operatorFeedPage = Math.max(1, Number(data.page || page));
        if (pinnedOwnedItemId > 0) {
          homeSelectedContextItem =
            operatorFeedItems.find((row) => Number(row?.owned_item_id || row?.id || 0) === pinnedOwnedItemId)
            || homeSelectedContextItem;
        }
        updateOperatorFeedControls();
        renderOperatorLookupResults();
        renderOpsLibraryContextDefault();
      } catch (err) {
        operatorFeedItems = [];
        operatorFeedTotalCount = 0;
        updateOperatorFeedControls();
        renderOperatorLookupResults();
        renderOpsLibraryContextDefault();
        setStatus("operatorLookupStatus", "err", errorMessageText(err, t("operator.lookup.status.feed_failed")));
      }
    }

    async function loadOperatorLookupResults() {
      const normalizedQuery = normalizeOpsLookupQuery($("operatorLookupQuery").value);
      const signatureMode = String($("operatorLookupSignatureMode").value || "ANY").trim().toUpperCase() || "ANY";
      const sortMode = String($("operatorLookupSortMode").value || "CREATED_DESC").trim().toUpperCase() || "CREATED_DESC";
      const requestSeq = ++operatorLookupRequestSeq;
      const loadingStatusText = t("operator.lookup.status.loading");
      $("operatorLookupQuery").value = normalizedQuery;
      if (!normalizedQuery) {
        await loadOperatorHomeFeed({ kind: operatorFeedKindFromSortMode(sortMode), page: 1 });
        setStatus("operatorLookupStatus", "", "");
        return;
      }
      operatorLookupMode = "SEARCH";
      updateOperatorFeedControls();
      setStatus("operatorLookupStatus", "", loadingStatusText);
      try {
        const params = new URLSearchParams({ q: normalizedQuery, limit: "30" });
        if (signatureMode !== "ANY") params.set("signature_mode", signatureMode);
        if (sortMode !== "CREATED_DESC") params.set("sort_mode", sortMode);
        const res = await fetchWithRetry(`/operator/catalog-search?${params.toString()}`, {}, {
          retries: 2,
          retryDelayMs: 250,
          onRetry: (attempt, total) => {
            if (requestSeq !== operatorLookupRequestSeq) return;
            setStatus("operatorLookupStatus", "", retryingStatusText(loadingStatusText, attempt, total));
          },
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("operator.lookup.status.search_failed")));
        if (requestSeq !== operatorLookupRequestSeq) return;
        setOperatorLookupResults(Array.isArray(data.items) ? data.items : [], normalizedQuery);
        setStatus("operatorLookupStatus", "ok", t("operator.lookup.status.complete", { count: formatCount(operatorLookupResults.length) }));
      } catch (err) {
        if (requestSeq !== operatorLookupRequestSeq) return;
        setOperatorLookupResults([], normalizedQuery, "error");
        setStatus("operatorLookupStatus", "err", errorMessageText(err, t("operator.lookup.status.search_failed")));
      }
    }

    function firstOperatorFormatLine(formatItems, fallbackFormatName = "") {
      const firstRow = cleanDictList(formatItems)[0] || null;
      if (firstRow) return formatOpsCollectorFormatItem(firstRow);
      return String(fallbackFormatName || "").trim() || "-";
    }

    async function openOperatorCabinetLocationFromButton(button) {
      if (!button) return;
      const activeItem = homeSelectedContextItem || homePreviewContextItem || null;
      const slotCode = String(button.getAttribute("data-operator-slot-code") || activeItem?.current_slot_code || "").trim();
      const cabinetName = String(button.getAttribute("data-cabinet-name") || activeItem?.current_cabinet_name || "").trim();
      const columnCode = String(button.getAttribute("data-column-code") || activeItem?.current_column_code || "").trim();
      const cellCode = String(button.getAttribute("data-cell-code") || activeItem?.current_cell_code || "").trim();
      if (!slotCode && !(cabinetName && columnCode && cellCode)) return;
      await openCabinetLocationAction(0, slotCode, cabinetName, columnCode, cellCode);
    }

    async function handleOperatorLookupAction(e) {
      const clearBtn = e.target.closest("[data-operator-context-clear]");
      if (clearBtn) {
        homeSelectedContextItem = null;
        homePreviewContextItem = null;
        renderOpsLibraryContextDefault();
        return;
      }
      const repairDiscogsMasterBtn = e.target.closest("[data-operator-repair-discogs-master]");
      if (repairDiscogsMasterBtn) {
        e.preventDefault();
        e.stopPropagation();
        const ownedItemId = Number(repairDiscogsMasterBtn.getAttribute("data-operator-repair-discogs-master") || 0);
        if (ownedItemId > 0) {
          const progressStatusText = t("operator.lookup.status.repair_discogs_master.progress");
          try {
            setStatus("operatorLookupStatus", "ok", progressStatusText);
            const res = await fetchWithRetry(`/owned-items/${ownedItemId}/repair-discogs-master-link`, { method: "POST" }, {
              retries: 2,
              retryDelayMs: 250,
              onRetry: (attempt, total) => setStatus("operatorLookupStatus", "ok", retryingStatusText(progressStatusText, attempt, total)),
            });
            const data = await safeJson(res);
            if (!res.ok) throw new Error(data.detail || t("operator.lookup.status.repair_discogs_master.failed"));
            discogsRepairEligibilityCache.delete(ownedItemId);
            await loadOperatorHomeRecentSections();
            if (operatorLookupMode === "FEED") await loadOperatorHomeFeed({ kind: operatorFeedKind, page: operatorFeedPage });
            else await loadOperatorLookupResults();
            const notices = Array.isArray(data?.notices) ? data.notices.map((value) => String(value || "").trim()).filter((value) => value) : [];
            setStatus("operatorLookupStatus", "ok", notices[0] || t("operator.lookup.status.repair_discogs_master.done"));
          } catch (err) {
            setStatus("operatorLookupStatus", "err", err.message || t("operator.lookup.status.repair_discogs_master.failed"));
          }
        }
        return;
      }
      // 도메인 수정 버튼
      const domainFixBtn = e.target.closest("[data-operator-domain-fix]");
      if (domainFixBtn) {
        e.preventDefault();
        e.stopPropagation();
        const masterId = Number(domainFixBtn.getAttribute("data-operator-domain-fix") || 0);
        if (masterId <= 0) {
          setStatus("operatorLookupStatus", "err", t("operator.lookup.domain.no_master"));
          return;
        }
        // 이미 폼이 열려 있으면 닫기
        const existingForm = domainFixBtn.parentElement.querySelector(".operator-domain-fix-form");
        if (existingForm) { existingForm.remove(); return; }
        // 다른 열린 폼 닫기
        document.querySelectorAll(".operator-domain-fix-form").forEach((f) => f.remove());
        const currentDc = String(domainFixBtn.getAttribute("data-current-domain") || "").trim();
        const currentSortArtist = String(domainFixBtn.getAttribute("data-current-sort-artist") || "").trim();
        const DOMAIN_OPTIONS = ["KOREA","JAPAN","GREATER_CHINA","WESTERN","OTHER_ASIA","WORLD","UNKNOWN"];
        const optionsHtml = DOMAIN_OPTIONS.map((dc) =>
          `<option value="${dc}"${dc === currentDc ? " selected" : ""}>${escapeHtml(dashboardDomainLabel(dc))}</option>`
        ).join("");
        const form = document.createElement("div");
        form.className = "operator-domain-fix-form";
        form.innerHTML = `
          <select class="domain-fix-select">${optionsHtml}</select>
          <input type="text" class="domain-fix-sort" placeholder="${escapeHtml(t("operator.lookup.domain.fix_sort_artist_placeholder"))}" value="${escapeHtml(currentSortArtist)}" />
          <button class="btn ghost tiny domain-fix-save-btn" type="button">${escapeHtml(t("operator.lookup.domain.fix_save"))}</button>
          <button class="btn ghost tiny domain-fix-cancel-btn" type="button">${escapeHtml(t("operator.lookup.domain.fix_cancel"))}</button>
        `;
        domainFixBtn.parentElement.appendChild(form);
        form.querySelector(".domain-fix-cancel-btn").addEventListener("click", () => form.remove());
        form.querySelector(".domain-fix-save-btn").addEventListener("click", async () => {
          const newDc = String(form.querySelector(".domain-fix-select").value || "").trim().toUpperCase() || null;
          const newSort = String(form.querySelector(".domain-fix-sort").value || "").trim() || null;
          try {
            setStatus("operatorLookupStatus", "ok", t("operator.lookup.domain.status.saving"));
            const corrRes = await fetch(`/album-masters/${masterId}/correction`, {
              method: "PATCH",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ domain_code: newDc }),
            });
            const corrData = await safeJson(corrRes);
            if (!corrRes.ok) throw new Error(corrData.detail || t("operator.lookup.domain.status.failed"));
            if (newSort) {
              const sortRes = await fetch(`/album-masters/${masterId}/sort-artist-name`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ sort_artist_name: newSort }),
              });
              const sortData = await safeJson(sortRes);
              if (!sortRes.ok) throw new Error(sortData.detail || t("operator.lookup.domain.status.failed"));
            }
            form.remove();
            await loadOperatorLookupResults();
            setStatus("operatorLookupStatus", "ok", t("operator.lookup.domain.status.done"));
          } catch (err) {
            setStatus("operatorLookupStatus", "err", err.message || t("operator.lookup.domain.status.failed"));
          }
        });
        return;
      }
      setOpsLibraryContextSelectionFromTarget(e.target, { pin: true });
      const cabinetBtn = e.target.closest("[data-operator-open-cabinet]");
      if (cabinetBtn) {
        await openOperatorCabinetLocationFromButton(cabinetBtn);
        return;
      }
      const contextCabinetBtn = e.target.closest("[data-operator-context-open-cabinet]");
      if (contextCabinetBtn) {
        if (contextCabinetBtn.classList.contains("ops-library-mini-map-cell")) {
          contextCabinetBtn.classList.remove("is-opening");
          contextCabinetBtn.offsetWidth;
          contextCabinetBtn.classList.add("is-opening");
        }
        await openOperatorCabinetLocationFromButton(contextCabinetBtn);
        return;
      }
      const manageBtn = e.target.closest("[data-operator-open-manage]");
      if (manageBtn) {
        const ownedItemId = Number(manageBtn.getAttribute("data-operator-open-manage") || 0);
        if (ownedItemId > 0) {
          const targetItem = homeSelectedContextItem || null;
          const masterId = Number(targetItem?.linked_album_master_id || targetItem?.album_master_id || 0);
          openAdminConsole("media", { remember: false, mediaMode: "manage" });
          await openMediaSearchDetailManage(masterId, ownedItemId);
        }
      }
    }

    async function loadOperatorRequestList() {
      const status = $("operatorRequestFilterStatus").value.trim();
      try {
        const params = new URLSearchParams({ limit: "60" });
        if (status) params.set("status", status);
        const res = await fetch(`/operator/customer-requests?${params.toString()}`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("operator.request.error.list_failed")));
        operatorRequestItems = Array.isArray(data.items) ? data.items : [];
        renderOperatorRequestList();
      } catch (err) {
        operatorRequestItems = [];
        renderOperatorRequestList();
        setStatus("operatorRequestStatus", "err", errorMessageText(err, t("operator.request.error.list_failed")));
      }
    }

    async function createOperatorRequest() {
      if (isShellReadOnly()) {
        setStatus("operatorRequestStatus", "err", t("operator.feed.state.read_only"));
        return;
      }
      const requestedTrack = $("operatorRequestTrack").value.trim();
      const ownedItemId = Number($("operatorRequestOwnedItemId").value || 0);
      const matchedTrackTitle = $("operatorRequestMatchedTrack").value.trim();
      const matchedTrackNoRaw = Number($("operatorRequestMatchedTrackNo").value || 0);
      const customerNote = $("operatorRequestCustomerNote").value.trim();
      if (!requestedTrack) {
        setStatus("operatorRequestStatus", "err", t("operator.request.field.required"));
        return;
      }
      setStatus("operatorRequestStatus", "", t("operator.request.status.creating"));
      try {
        const res = await fetch("/operator/customer-requests", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            requested_track: requestedTrack,
            owned_item_id: ownedItemId > 0 ? ownedItemId : null,
            matched_track_title: matchedTrackTitle || null,
            matched_track_no: matchedTrackNoRaw > 0 ? matchedTrackNoRaw : null,
            customer_note: customerNote || null,
          }),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("operator.request.error.create_failed")));
        clearOperatorRequestForm();
        setStatus("operatorRequestStatus", "ok", t("operator.request.status.created"));
        await loadOperatorRequestList();
      } catch (err) {
        setStatus("operatorRequestStatus", "err", errorMessageText(err, t("operator.request.error.create_failed")));
      }
    }

    async function updateOperatorRequestStatus(requestId, status) {
      if (isShellReadOnly()) {
        setStatus("operatorRequestStatus", "err", t("operator.feed.state.read_only"));
        return;
      }
      const requestIdNum = Number(requestId || 0);
      if (!requestIdNum || !status) return;
      try {
        const res = await fetch(`/operator/customer-requests/${requestIdNum}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status }),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("operator.request.error.update_failed")));
        setStatus("operatorRequestStatus", "ok", t("operator.request.status.updated", { status: operatorStatusLabel(status) }));
        await loadOperatorRequestList();
      } catch (err) {
        setStatus("operatorRequestStatus", "err", errorMessageText(err, t("operator.request.error.update_failed")));
      }
    }

    function currentPurchaseImportRawContent() {
      if (String(purchaseImportFileContentBase64 || "").trim()) return "";
      return String($("purchaseImportRawContent")?.value || "").trim();
    }

    function arrayBufferToBase64(buffer) {
      const bytes = new Uint8Array(buffer);
      if (!bytes.length) return "";
      const chunks = [];
      const chunkSize = 0x8000;
      for (let i = 0; i < bytes.length; i += chunkSize) {
        chunks.push(String.fromCharCode(...bytes.subarray(i, i + chunkSize)));
      }
      return window.btoa(chunks.join(""));
    }

    function setPurchaseImportFileInfo(message, statusClass = "muted") {
      const node = $("purchaseImportFileInfo");
      if (!node) return;
      node.className = `mini ${statusClass}`.trim();
      node.textContent = message || t("media.register.purchase.status.file_none");
    }

    async function handlePurchaseImportFileChange(event) {
      const input = event?.target;
      const file = input?.files?.[0];
      if (!file) {
        purchaseImportFileContent = "";
        purchaseImportFileContentBase64 = "";
        purchaseImportFileName = "";
        setPurchaseImportFileInfo(t("media.register.purchase.status.file_none"));
        return;
      }
      setPurchaseImportFileInfo(t("media.register.purchase.status.file_reading", { name: file.name }));
      try {
        purchaseImportFileContent = "";
        purchaseImportFileContentBase64 = arrayBufferToBase64(await file.arrayBuffer());
        purchaseImportFileName = file.name;
        if ($("purchaseImportSourceRef") && !$("purchaseImportSourceRef").value.trim()) {
          $("purchaseImportSourceRef").value = file.name;
        }
        $("purchaseImportSourceType").value = "FILE_UPLOAD";
        setPurchaseImportFileInfo(t("media.register.purchase.status.file_ready", { name: file.name }));
        setStatus("purchaseImportStatus", "ok", t("media.register.purchase.status.file_ready", { name: file.name }));
      } catch (err) {
        purchaseImportFileContent = "";
        purchaseImportFileContentBase64 = "";
        purchaseImportFileName = "";
        setPurchaseImportFileInfo(t("media.register.purchase.status.file_read_failed", { name: file.name }), "err");
        setStatus("purchaseImportStatus", "err", errorMessageText(err, t("media.register.purchase.status.file_read_failed", { name: file.name })));
      }
    }

    function buildPurchaseImportCandidateHtml(queueId, state, candidate, candidateIdx) {
      const artistText = String(candidate?.artist_or_brand || "").trim() || t("common.unknown");
      const itemText = String(candidate?.title || "").trim() || t("common.no_title");
      const title = `${artistText} - ${itemText}`;
      const galleryKey = registerImageGallery(`purchaseImport:${queueId}:${normalizeSourceCode(candidate?.source)}:${candidate?.external_id || candidateIdx}`, candidate, {
        title,
        subtitle: `${normalizeSourceCode(candidate?.source) || "-"}#${candidate?.external_id || "-"}`,
      });
      const galleryCount = galleryKey ? Number(imageGalleryRegistry.get(galleryKey)?.items?.length || 0) : 0;
      const coverUrl = normalizeRenderableCoverUrl(candidate?.cover_image_url);
      const cover = coverUrl
        ? `<img src="${escapeHtml(coverUrl)}" alt="${escapeHtml(candidate.title || "")}" />`
        : escapeHtml(mediaDisplayLabel(candidate?.format_name || "-"));
      const discogsLink = discogsReleaseLinkHtml(candidate?.source, candidate?.external_id, "Discogs");
      const discogsMetaHtml = buildDiscogsStandardMetaHtml(candidate, { includeOwnedCount: true, ownedCountClassName: "source-workbench-owned-pill" });
      return `
        <div class="source-workbench-candidate">
          <div class="source-workbench-cover">${cover}</div>
          <div class="source-workbench-candidate-main">
            <div class="source-workbench-candidate-title">${escapeHtml(artistText)} - ${escapeHtml(itemText)}</div>
            <div class="source-workbench-candidate-meta">
              <span class="tag">${escapeHtml(candidate?.source || "-")}</span>
              ${discogsMetaHtml || `
                <span>${escapeHtml(t("common.meta.release_date", { value: candidate?.released_date || candidate?.release_year || "-" }))}</span>
                <span>${escapeHtml(t("common.meta.label", { value: candidate?.label_name || "-" }))} / ${escapeHtml(t("common.meta.catalog_no", { value: candidate?.catalog_no || "-" }))}</span>
                <span>${escapeHtml(t("common.meta.barcode", { value: candidate?.barcode || "-" }))}</span>
                <span>${escapeHtml(t("common.meta.format", { value: candidate?.format_name || "-" }))}</span>
                <span>${escapeHtml(t("common.meta.track_count", { value: formatCount(Array.isArray(candidate?.track_list) ? candidate.track_list.length : 0) }))}</span>
                ${Number(candidate?.owned_count || 0) > 0 ? `<span>${escapeHtml(t("common.meta.already_owned", { count: formatCount(Number(candidate.owned_count || 0)) }))}</span>` : ""}
              `}
            </div>
            <div class="mini">
              external_id: ${escapeHtml(candidate?.external_id || "-")}
              ${discogsLink ? ` | ${discogsLink}` : ""}
              ${galleryKey ? ` | ${imageGalleryButtonHtml(galleryKey, t("common.count.images", { count: galleryCount }))}` : ""}
            </div>
          </div>
          <div class="source-workbench-candidate-actions">
            <button class="btn tiny" type="button" data-purchase-import-create-direct="${queueId}:${candidateIdx}">${escapeHtml(t("media.register.purchase.queue.action.create_from_candidate"))}</button>
          </div>
        </div>
      `;
    }

    async function previewPurchaseImport() {
      const rawContent = currentPurchaseImportRawContent();
      if (!rawContent && !purchaseImportFileContentBase64) {
        setStatus("purchaseImportStatus", "err", t("media.register.purchase.status.preview_requires_input"));
        return;
      }
      setStatus("purchaseImportStatus", "", t("media.register.purchase.status.preview_loading"));
      try {
        const payload = {
          ...purchaseImportPayloadBase(),
          raw_content: rawContent || null,
          raw_content_base64: purchaseImportFileContentBase64 || null,
          source_filename: purchaseImportFileName || null,
        };
        const res = await fetch("/purchase-imports/preview", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("media.register.purchase.status.preview_failed")));
        renderPurchaseImportPreview(Array.isArray(data.items) ? data.items : []);
        setStatus("purchaseImportStatus", "ok", t("media.register.purchase.status.preview_complete", {
          count: formatCount(Number(data.total_count || 0)),
          vendor: purchaseImportVendorLabel(data.vendor_code),
        }));
      } catch (err) {
        renderPurchaseImportPreview([]);
        setStatus("purchaseImportStatus", "err", errorMessageText(err, t("media.register.purchase.status.preview_failed")));
      }
    }

    async function savePurchaseImportQueue() {
      if (!purchaseImportPreviewItems.length) {
        setStatus("purchaseImportStatus", "err", t("media.register.purchase.status.save_requires_preview"));
        return;
      }
      setStatus("purchaseImportStatus", "", t("media.register.purchase.status.queue_save_loading"));
      try {
        const payload = {
          ...purchaseImportPayloadBase(),
          items: purchaseImportPreviewItems,
        };
        const res = await fetch("/purchase-imports", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("media.register.purchase.status.queue_save_failed")));
        setStatus("purchaseImportStatus", "ok", t("media.register.purchase.status.queue_save_complete", {
          count: formatCount(Number(data.created_count || 0)),
        }));
        await loadPurchaseImportQueue({ silent: true });
      } catch (err) {
        setStatus("purchaseImportStatus", "err", errorMessageText(err, t("media.register.purchase.status.queue_save_failed")));
      }
    }

    async function loadPurchaseImportQueue(opts = {}) {
      const silent = opts.silent === true;
      const queueStatus = String($("purchaseImportQueueStatusFilter")?.value || "PENDING").trim().toUpperCase();
      const vendorCode = String($("purchaseImportQueueVendorFilter")?.value || "").trim().toUpperCase();
      const limit = Math.max(1, Math.min(1000, Number($("purchaseImportQueueLimit")?.value || 200)));
      if (!silent) setStatus("purchaseImportQueueStatus", "", t("media.register.purchase.status.queue_loading"));
      try {
        const params = new URLSearchParams();
        if (queueStatus) params.set("queue_status", queueStatus);
        if (vendorCode) params.set("vendor_code", vendorCode);
        params.set("limit", String(limit));
        const res = await fetch(`/purchase-imports?${params.toString()}`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("media.register.purchase.status.queue_load_failed")));
        const rows = Array.isArray(data.items) ? data.items : [];
        renderPurchaseImportQueue(rows);
        setStatus(
          "purchaseImportQueueStatus",
          "ok",
          t("media.register.purchase.status.queue_loaded", {
            shown: formatCount(rows.length),
            total: formatCount(Number(data.total_count || 0)),
          })
        );
      } catch (err) {
        renderPurchaseImportQueue([]);
        setStatus("purchaseImportQueueStatus", "err", errorMessageText(err, t("media.register.purchase.status.queue_load_failed")));
      }
    }

    async function enrichPurchaseImportFromItemPage(queueId) {
      const id = Number(queueId || 0);
      if (!id) return;
      setStatus("purchaseImportQueueStatus", "", t("media.register.purchase.queue.status.enrich_loading", { id }));
      try {
        const res = await fetch(`/purchase-imports/${id}/enrich-item-page`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("media.register.purchase.queue.status.enrich_failed")));
        setStatus("purchaseImportQueueStatus", "ok", t("media.register.purchase.queue.status.enrich_complete", {
          id,
          suffix: data.artist_name ? ` / ${data.artist_name}` : "",
        }));
        await loadPurchaseImportQueue({ silent: true });
      } catch (err) {
        setStatus("purchaseImportQueueStatus", "err", errorMessageText(err, t("media.register.purchase.queue.status.enrich_failed")));
      }
    }

    async function createOwnedItemFromPurchaseQueue(queueId) {
      const id = Number(queueId || 0);
      if (!id) return;
      setStatus("purchaseImportQueueStatus", "", t("media.register.purchase.queue.status.create_loading", { id }));
      try {
        const res = await fetch(`/purchase-imports/${id}/create-owned-item`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("media.register.purchase.queue.status.create_failed")));
        const noticeText = Array.isArray(data.notices) && data.notices.length
          ? ` / ${data.notices.join(" / ")}`
          : "";
        setStatus("purchaseImportQueueStatus", "ok", t("media.register.purchase.queue.status.create_complete", {
          id: data.owned_item_id,
          label: data.label_id,
          suffix: noticeText,
        }));
        await loadPurchaseImportQueue({ silent: true });
        await Promise.allSettled([
          loadOwnedItems(),
          loadHomeDashboard(),
          homeSearchOwnedItems({ resetPage: true, suppressEmptyCta: true }),
        ]);
      } catch (err) {
        setStatus("purchaseImportQueueStatus", "err", errorMessageText(err, t("media.register.purchase.queue.status.create_failed")));
      }
    }

    async function loadPurchaseImportCandidates(queueId, opts = {}) {
      const id = Number(queueId || 0);
      if (!id) return;
      const lookupOpts = {
        ...getPurchaseImportCandidateLookupOptions(),
        ...(opts || {}),
      };
      let state = purchaseImportQueueStateFor(id);
      if (state.loading) return;
      state.expanded = Boolean(lookupOpts.expand ?? true);
      state.loading = true;
      state.error = "";
      renderPurchaseImportQueue(purchaseImportQueueItems);
      if (!lookupOpts.silentStatus) {
        setStatus("purchaseImportQueueStatus", "", t("media.register.purchase.queue.status.lookup_loading", { id }));
      }
      try {
        const params = new URLSearchParams();
        const source = String(lookupOpts.source ?? state.source ?? "AUTO").trim().toUpperCase() || "AUTO";
        params.set("source", source);
        params.set("limit", String(Math.max(1, Math.min(20, Number(lookupOpts.limit || 5)))));
        const artistName = String(lookupOpts.artistName ?? state.artistName ?? "").trim();
        const itemName = String(lookupOpts.itemName ?? state.itemName ?? "").trim();
        const queryOverride = String(lookupOpts.query ?? state.queryOverride ?? "").trim();
        if (artistName) params.set("artist_name", artistName);
        if (itemName) params.set("item_name", itemName);
        if (queryOverride) params.set("query", queryOverride);
        const res = await fetch(`/purchase-imports/${id}/candidates?${params.toString()}`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("media.register.purchase.queue.status.lookup_failed")));
        state = purchaseImportQueueStateFor(id);
        if (data.queue_item && typeof data.queue_item === "object") {
          const rowIndex = purchaseImportQueueItems.findIndex((row) => Number(row?.id || 0) === id);
          if (rowIndex >= 0) {
            purchaseImportQueueItems[rowIndex] = data.queue_item;
          }
        }
        state.source = source;
        state.artistName = artistName;
        state.itemName = itemName;
        state.queryOverride = queryOverride;
        state.query = String(data.query || "").trim();
        state.candidates = Array.isArray(data.candidates) ? data.candidates.map((candidate) => cloneRegisterLookupCandidate(candidate)).filter((candidate) => candidate) : [];
        state.selectedIdx = state.candidates.length ? 0 : -1;
        state.error = "";
        if (!lookupOpts.silentStatus) {
          setStatus("purchaseImportQueueStatus", "ok", t("media.register.purchase.queue.status.lookup_complete", {
            id,
            count: formatCount(state.candidates.length),
          }));
        }
        return { ok: true, count: state.candidates.length };
      } catch (err) {
        state = purchaseImportQueueStateFor(id);
        state.candidates = [];
        state.selectedIdx = -1;
        state.error = errorMessageText(err, t("media.register.purchase.queue.status.lookup_failed"));
        if (!lookupOpts.silentStatus) {
          setStatus("purchaseImportQueueStatus", "err", state.error);
        }
        return { ok: false, count: 0, error: state.error };
      } finally {
        state = purchaseImportQueueStateFor(id);
        state.loading = false;
        renderPurchaseImportQueue(purchaseImportQueueItems);
      }
    }

    async function loadAllPurchaseImportCandidates() {
      const rows = purchaseImportQueueItems.filter((row) => String(row?.queue_status || "").trim().toUpperCase() === "PENDING");
      if (!rows.length) {
        setStatus("purchaseImportQueueStatus", "err", t("media.register.purchase.queue.status.lookup_none_pending"));
        return;
      }
      const lookupOpts = getPurchaseImportCandidateLookupOptions();
      let successCount = 0;
      let emptyCount = 0;
      let failCount = 0;
      setStatus("purchaseImportQueueStatus", "", t("media.register.purchase.queue.status.lookup_fetch_all_loading", {
        count: formatCount(rows.length),
      }));
      for (const row of rows) {
        const result = await loadPurchaseImportCandidates(row.id, {
          ...lookupOpts,
          expand: false,
          silentStatus: true,
        });
        if (result?.ok && Number(result.count || 0) > 0) {
          successCount += 1;
        } else if (result?.ok) {
          emptyCount += 1;
        } else {
          failCount += 1;
        }
      }
      setStatus(
        "purchaseImportQueueStatus",
        failCount ? "err" : "ok",
        t("media.register.purchase.queue.status.lookup_fetch_all_complete", {
          success: formatCount(successCount),
          empty: formatCount(emptyCount),
          failed: formatCount(failCount),
        })
      );
      renderPurchaseImportQueue(purchaseImportQueueItems);
    }

    function selectPurchaseImportCandidate(queueId, candidateIdx) {
      const id = Number(queueId || 0);
      const idx = Number(candidateIdx);
      if (!id || !Number.isInteger(idx)) return;
      const state = purchaseImportQueueStateFor(id);
      if (!Array.isArray(state.candidates) || !state.candidates[idx]) return;
      state.expanded = true;
      state.selectedIdx = idx;
      renderPurchaseImportQueue(purchaseImportQueueItems);
      setStatus("purchaseImportQueueStatus", "ok", t("media.register.purchase.queue.status.select_complete", {
        id,
        source: `${state.candidates[idx].source}#${state.candidates[idx].external_id || "-"}`,
      }));
    }

    async function createOwnedItemFromPurchaseQueueCandidate(queueId, candidateIdx = null) {
      const id = Number(queueId || 0);
      if (!id) return;
      const state = purchaseImportQueueStateFor(id);
      const idx = (candidateIdx !== null && Number.isFinite(Number(candidateIdx))) ? Number(candidateIdx) : state.selectedIdx;
      const candidate = Array.isArray(state.candidates) ? state.candidates[idx] : null;
      if (!candidate) {
        setStatus("purchaseImportQueueStatus", "err", t("media.register.purchase.queue.status.create_candidate_requires_selection"));
        return;
      }
      setStatus("purchaseImportQueueStatus", "", t("media.register.purchase.queue.status.create_candidate_loading", { id }));
      try {
        const requestBody = { candidate };
        console.log("[createOwnedItemFromPurchaseQueueCandidate] Sending POST request:", {
          queueId: id,
          candidateData: requestBody,
          timestamp: new Date().toISOString(),
        });
        const res = await fetch(`/purchase-imports/${id}/create-owned-item-from-candidate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(requestBody),
        });
        const data = await safeJson(res);
        console.log("[createOwnedItemFromPurchaseQueueCandidate] Response received:", {
          status: res.status,
          ok: res.ok,
          data,
          timestamp: new Date().toISOString(),
        });
        if (!res.ok) throw new Error(responseDetailText(data, t("media.register.purchase.queue.status.create_candidate_failed")));
        const noticeText = Array.isArray(data.notices) && data.notices.length
          ? ` / ${data.notices.join(" / ")}`
          : "";
        console.log("[createOwnedItemFromPurchaseQueueCandidate] Success:", {
          ownedItemId: data.owned_item_id,
          labelId: data.label_id,
          linkedAlbumMasterId: data.linked_album_master_id,
          notices: data.notices,
        });
        setStatus("purchaseImportQueueStatus", "ok", t("media.register.purchase.queue.status.create_candidate_complete", {
          id: data.owned_item_id,
          label: data.label_id,
          suffix: noticeText,
        }));
        await loadPurchaseImportQueue({ silent: true });
        await Promise.allSettled([
          loadOwnedItems(),
          loadHomeDashboard(),
          homeSearchOwnedItems({ resetPage: true, suppressEmptyCta: true }),
        ]);
      } catch (err) {
        console.error("[createOwnedItemFromPurchaseQueueCandidate] Error occurred:", {
          error: err?.message || String(err),
          stack: err?.stack,
          timestamp: new Date().toISOString(),
        });
        setStatus("purchaseImportQueueStatus", "err", errorMessageText(err, t("media.register.purchase.queue.status.create_candidate_failed")));
      }
    }

    async function ignorePurchaseImportRow(queueId) {
      const id = Number(queueId || 0);
      if (!id) return;
      setStatus("purchaseImportQueueStatus", "", t("media.register.purchase.queue.status.ignore_loading", { id }));
      try {
        const res = await fetch(`/purchase-imports/${id}/ignore`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("media.register.purchase.queue.status.ignore_failed")));
        setStatus("purchaseImportQueueStatus", "ok", t("media.register.purchase.queue.status.ignore_complete", { id }));
        await loadPurchaseImportQueue({ silent: true });
      } catch (err) {
        setStatus("purchaseImportQueueStatus", "err", errorMessageText(err, t("media.register.purchase.queue.status.ignore_failed")));
      }
    }

    function currentOpsExceptionPresetPayload() {
      const opsExPkgChecked = [];
      $("opsExPackagingList")?.querySelectorAll("input:checked").forEach(cb => opsExPkgChecked.push(cb.value));
      const opsExContentsChecked = [];
      $("opsExPackageContentsList")?.querySelectorAll("input:checked").forEach(cb => opsExContentsChecked.push(cb.value));
      return {
        type: String($("opsExceptionType")?.value || "UNSLOTTED").trim().toUpperCase(),
        limit: Math.max(10, Math.min(200, Number($("opsExceptionLimit")?.value || 50))),
        domain:      String($("opsExceptionDomain")?.value || "").trim(),
        artist:      String($("opsExArtist")?.value      || "").trim(),
        title:       String($("opsExTitle")?.value        || "").trim(),
        barcode:     String($("opsExBarcode")?.value      || "").trim(),
        catalogNo:   String($("opsExCatalogNo")?.value    || "").trim(),
        releaseYear: String($("opsExReleaseYear")?.value  || "").trim(),
        packaging:       opsExPkgChecked,
        packageContents: opsExContentsChecked,
        sigDirect:   Boolean($("opsExSigDirect")?.checked),
        sigPurchase: Boolean($("opsExSigPurchase")?.checked),
        isNew:       Boolean($("opsExNewProduct")?.checked),
        isPromo:     Boolean($("opsExPromo")?.checked),
        isLimited:   Boolean($("opsExLimitEd")?.checked),
      };
    }

    function loadOpsExceptionPresets() {
      try {
        const raw = window.localStorage.getItem(OPS_EXCEPTION_PRESET_KEY);
        const parsed = JSON.parse(raw || "[]");
        return Array.isArray(parsed) ? parsed.filter((row) => row && typeof row === "object") : [];
      } catch (_err) {
        return [];
      }
    }

    function saveOpsExceptionPresets(list) {
      const rows = Array.isArray(list) ? list : [];
      window.localStorage.setItem(OPS_EXCEPTION_PRESET_KEY, JSON.stringify(rows));
    }

    function loadDefaultOpsExceptionPresetName() {
      const role = String(appAuthSession?.role || "ADMIN").trim().toUpperCase();
      const scopedKey = `${OPS_EXCEPTION_PRESET_DEFAULT_KEY}.${role}`;
      try {
        return String(window.localStorage.getItem(scopedKey) || "").trim();
      } catch (_err) {
        return "";
      }
    }

    function saveDefaultOpsExceptionPresetName(name) {
      const role = String(appAuthSession?.role || "ADMIN").trim().toUpperCase();
      const scopedKey = `${OPS_EXCEPTION_PRESET_DEFAULT_KEY}.${role}`;
      try {
        if (!name) window.localStorage.removeItem(scopedKey);
        else window.localStorage.setItem(scopedKey, String(name).trim());
      } catch (_err) {
        // ignore localStorage write errors
      }
    }

    function loadRoleScopedMap(storageKey) {
      try {
        const raw = window.localStorage.getItem(storageKey);
        const parsed = JSON.parse(raw || "{}");
        return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
      } catch (_err) {
        return {};
      }
    }

    function saveRoleScopedMap(storageKey, nextValue) {
      try {
        window.localStorage.setItem(storageKey, JSON.stringify(nextValue || {}));
      } catch (_err) {
        // ignore localStorage write errors
      }
    }

    function currentSessionRoleCode() {
      return String(appAuthSession?.role || "ADMIN").trim().toUpperCase();
    }

    function loadRoleScopedValue(storageKey) {
      const role = currentSessionRoleCode();
      const map = loadRoleScopedMap(storageKey);
      return String(map?.[role] || "").trim();
    }

    function saveRoleScopedValue(storageKey, value) {
      const role = currentSessionRoleCode();
      const map = loadRoleScopedMap(storageKey);
      if (!value) delete map[role];
      else map[role] = String(value).trim();
      saveRoleScopedMap(storageKey, map);
    }

    function clearCurrentRoleDefaultPreferences() {
      saveRoleScopedValue(APP_MAIN_TAB_MEMORY_KEY, "");
      saveRoleScopedValue(APP_SUBTAB_MEMORY_KEY, "");
      saveDefaultOpsExceptionPresetName("");
    }

    function renderOpsExceptionPresetOptions() {
      const select = $("opsExceptionPresetSelect");
      const chips = $("opsExceptionPresetChips");
      if (!select) return;
      const rows = loadOpsExceptionPresets();
      const currentValue = String(select.value || "");
      const defaultName = loadDefaultOpsExceptionPresetName().toLowerCase();
      select.innerHTML = [
        `<option value="">${escapeHtml(t("common.none"))}</option>`,
        ...rows.map((row, idx) => {
          const name = String(row.name || t("ops.exception.field.preset.fallback_name", { index: idx + 1 }));
          const type = opsExceptionTypeLabel(row.type || "UNSLOTTED");
          const limit = Math.max(10, Math.min(200, Number(row.limit || 50)));
          const isDefault = name.trim().toLowerCase() === defaultName;
          return `<option value="${idx}">${escapeHtml(isDefault
            ? t("ops.exception.field.preset.option.default", { name, type, limit: countWithUnit(limit) })
            : t("ops.exception.field.preset.option.normal", { name, type, limit: countWithUnit(limit) }))}</option>`;
        })
      ].join("");
      if (currentValue && rows[Number(currentValue)]) {
        select.value = currentValue;
      }
      if (chips) {
        chips.innerHTML = rows.length
          ? rows.slice(0, 8).map((row, idx) => {
              const name = String(row.name || t("ops.exception.field.preset.fallback_name", { index: idx + 1 }));
              const type = opsExceptionTypeLabel(row.type || "UNSLOTTED");
              const limit = Math.max(10, Math.min(200, Number(row.limit || 50)));
              const isDefault = name.trim().toLowerCase() === defaultName;
              return `<button class="dashboard-workbench-source ${isDefault ? "active" : ""}" type="button" data-ops-exception-preset-chip="${idx}" title="${escapeHtml(`${name} / ${type} / ${countWithUnit(limit)}`)}">${escapeHtml(isDefault ? t("ops.exception.field.preset.chip.default", { name, limit }) : t("ops.exception.field.preset.chip.normal", { name, limit }))}</button>`;
            }).join("")
          : `<div class="mini muted">${escapeHtml(t("ops.exception.state.empty_presets"))}</div>`;
      }
    }

    function applyDefaultOpsExceptionPreset() {
      const defaultName = loadDefaultOpsExceptionPresetName().toLowerCase();
      if (!defaultName) return false;
      const rows = loadOpsExceptionPresets();
      const idx = rows.findIndex((row) => String(row?.name || "").trim().toLowerCase() === defaultName);
      if (idx < 0) return false;
      $("opsExceptionPresetSelect").value = String(idx);
      return applyOpsExceptionPresetByIndex(String(idx));
    }

    function applyOpsExceptionPresetByIndex(indexValue) {
      const idx = Number(indexValue);
      if (!Number.isInteger(idx) || idx < 0) return false;
      const rows = loadOpsExceptionPresets();
      const preset = rows[idx];
      if (!preset) return false;
      $("opsExceptionType").value = String(preset.type || "UNSLOTTED").trim().toUpperCase();
      $("opsExceptionLimit").value = String(Math.max(10, Math.min(200, Number(preset.limit || 50))));
      if ($("opsExceptionPresetName")) {
        $("opsExceptionPresetName").value = String(preset.name || "").trim();
      }
      if ($("opsExceptionDomain"))    $("opsExceptionDomain").value    = String(preset.domain    || "").trim();
      if ($("opsExArtist"))      $("opsExArtist").value      = String(preset.artist      || "").trim();
      if ($("opsExTitle"))       $("opsExTitle").value        = String(preset.title       || "").trim();
      if ($("opsExBarcode"))     $("opsExBarcode").value      = String(preset.barcode     || "").trim();
      if ($("opsExCatalogNo"))   $("opsExCatalogNo").value    = String(preset.catalogNo   || "").trim();
      if ($("opsExReleaseYear")) $("opsExReleaseYear").value  = String(preset.releaseYear || "").trim();
      // 상세 검색 조건 복원
      const pkgValues = new Set(Array.isArray(preset.packaging) ? preset.packaging : []);
      $("opsExPackagingList")?.querySelectorAll("input").forEach(cb => { cb.checked = pkgValues.has(cb.value); });
      const contentsValues = new Set(Array.isArray(preset.packageContents) ? preset.packageContents : []);
      $("opsExPackageContentsList")?.querySelectorAll("input").forEach(cb => { cb.checked = contentsValues.has(cb.value); });
      if ($("opsExSigDirect"))  $("opsExSigDirect").checked  = Boolean(preset.sigDirect);
      if ($("opsExSigPurchase")) $("opsExSigPurchase").checked = Boolean(preset.sigPurchase);
      if ($("opsExNewProduct")) $("opsExNewProduct").checked = Boolean(preset.isNew);
      if ($("opsExPromo"))      $("opsExPromo").checked      = Boolean(preset.isPromo);
      if ($("opsExLimitEd"))    $("opsExLimitEd").checked    = Boolean(preset.isLimited);
      syncOpsExceptionSelectionControls();
      return true;
    }

    function syncMasterExceptionBanner() {
      const el = $("masterExceptionBanner");
      const legacyCard = $("registerMasterLegacyCard");
      const count = masterOwnedPrefilledIds.size;
      const showLegacyCard = count > 0 || (Array.isArray(masterOwnedItems) && masterOwnedItems.length > 0);
      if (legacyCard) {
        legacyCard.hidden = !showLegacyCard;
        setDisplayMode(legacyCard, showLegacyCard ? "block" : "none");
      }
      if (!el) return;
      if (!count) {
        setDisplayMode(el, "none");
        el.textContent = "";
        return;
      }
      setDisplayMode(el, "block");
      el.textContent = t("ops.exception.banner.prefilled", { count: countWithUnit(count) });
    }

    function opsExceptionTypeLabel(value) {
      const code = String(value || "").trim().toUpperCase();
      if (code === "UNSLOTTED") return t("common.exception.unslotted");
      if (code === "SOURCE_MISSING") return t("common.exception.source_missing");
      if (code === "MASTER_MISSING") return t("common.exception.master_missing");
      if (code === "COVER_MISSING") return t("common.exception.cover_missing");
      if (code === "PREFERRED_SIZE_MISMATCH") return t("common.exception.preferred_size_mismatch");
      if (code === "TRACK_MISSING") return t("common.exception.track_missing");
      if (code === "SPOTIFY_UNMATCHED") return t("common.exception.spotify_unmatched");
      if (code === "REVIEW_MISSING") return t("common.exception.review_missing");
      if (code === "MEDIA_MISSING") return t("common.exception.media_missing");
      if (code === "SIZE_MISMATCH") return t("common.exception.size_mismatch");
      if (code === "GENRE_MISSING") return t("common.exception.genre_missing");
      if (code === "CATALOG_MISSING") return t("common.exception.catalog_missing");
      if (code === "RELEASE_TYPE_MISSING") return "앨범 타입 없음";
      return code || "-";
    }

    function opsExceptionTypeHint(value) {
      const code = String(value || "").trim().toUpperCase();
      if (code === "UNSLOTTED") return t("common.exception_hint.unslotted");
      if (code === "SOURCE_MISSING") return t("common.exception_hint.source_missing");
      if (code === "MASTER_MISSING") return t("common.exception_hint.master_missing");
      if (code === "COVER_MISSING") return t("common.exception_hint.cover_missing");
      if (code === "PREFERRED_SIZE_MISMATCH") return t("common.exception_hint.preferred_size_mismatch");
      if (code === "TRACK_MISSING") return t("common.exception_hint.track_missing");
      if (code === "SPOTIFY_UNMATCHED") return t("common.exception_hint.spotify_unmatched");
      if (code === "REVIEW_MISSING") return t("common.exception_hint.review_missing");
      if (code === "MEDIA_MISSING") return t("common.exception_hint.media_missing");
      if (code === "SIZE_MISMATCH") return t("common.exception_hint.size_mismatch");
      if (code === "GENRE_MISSING") return t("common.exception_hint.genre_missing");
      if (code === "CATALOG_MISSING") return t("common.exception_hint.catalog_missing");
      if (code === "LOCAL_MISSING") return "로컬 음원 미연결";
      if (code === "RELEASE_TYPE_MISSING") return "앨범 마스터 타입 미등록";
      return "";
    }

    function buildMasterExceptionUrl(type, limit, offset = 0) {
      let url;
      const artist = String($("opsExArtist")?.value || "").trim();
      const title  = String($("opsExTitle")?.value  || "").trim();
      const domain = String($("opsExceptionDomain")?.value || "").trim();
      const releaseYear = String($("opsExReleaseYear")?.value || "").trim();
      if (type === "CATALOG_MISSING") {
        url = `/owned-items?music_only=true&status=IN_COLLECTION&include_total=true&limit=${limit}&offset=${offset}&catalog_missing=true`;
        if (artist)      url += `&artist_or_brand=${encodeURIComponent(artist)}`;
        if (title)       url += `&q=${encodeURIComponent(title)}`;
        if (domain)      url += `&domain_code=${encodeURIComponent(domain)}`;
        if (releaseYear) url += `&release_year=${encodeURIComponent(releaseYear)}`;
      } else {
        url = `/album-masters?include_total=true&limit=${limit}&offset=${offset}`;
        if (type === "GENRE_MISSING")           url += "&genre_missing=true&media_only=true";
        else if (type === "SPOTIFY_UNMATCHED")  url += "&spotify_state=MISSING";
        else if (type === "REVIEW_MISSING")     url += "&review_missing=true&media_only=true";
        else if (type === "LOCAL_MISSING")      url += "&local_missing=true&media_only=true";
        else if (type === "RELEASE_TYPE_MISSING") url += "&release_type_missing=true&media_only=true";
        if (artist)      url += `&artist_or_brand=${encodeURIComponent(artist)}`;
        if (title)       url += `&q=${encodeURIComponent(title)}`;
        if (domain)      url += `&domain_code=${encodeURIComponent(domain)}`;
        if (releaseYear) url += `&release_year=${encodeURIComponent(releaseYear)}`;
      }
      return url;
    }

    function buildMasterExceptionCountUrl(type) {
      let url;
      const domain = String($("opsExceptionDomain")?.value || "").trim();
      if (type === "CATALOG_MISSING") {
        url = `/owned-items?music_only=true&status=IN_COLLECTION&include_total=true&limit=1&catalog_missing=true`;
        if (domain) url += `&domain_code=${encodeURIComponent(domain)}`;
      } else {
        url = `/album-masters?include_total=true&limit=1`;
        if (type === "GENRE_MISSING")           url += "&genre_missing=true&media_only=true";
        else if (type === "SPOTIFY_UNMATCHED")  url += "&spotify_state=MISSING";
        else if (type === "REVIEW_MISSING")     url += "&review_missing=true&media_only=true";
        else if (type === "LOCAL_MISSING")      url += "&local_missing=true&media_only=true";
        else if (type === "RELEASE_TYPE_MISSING") url += "&release_type_missing=true&media_only=true";
        if (domain) url += `&domain_code=${encodeURIComponent(domain)}`;
      }
      return url;
    }

    function buildOpsExceptionParams(type, opts = {}) {
      const params = new URLSearchParams({
        music_only: "true",
        status: "IN_COLLECTION",
        sort: "RECENT",
        limit: String(Math.max(1, Math.min(200, Number(opts.limit || 50)))),
        offset: String(Math.max(0, Number(opts.offset || 0))),
      });
      if (opts.includeTotal) params.set("include_total", "true");
      const code = String(type || "UNSLOTTED").trim().toUpperCase();
      if (code === "UNSLOTTED") params.set("slot_state", "UNSLOTTED");
      if (code === "SOURCE_MISSING") params.set("source_state", "MISSING");
      if (code === "MASTER_MISSING") params.set("master_state", "MISSING");
      if (code === "COVER_MISSING") params.set("cover_state", "MISSING");
      if (code === "PREFERRED_SIZE_MISMATCH") params.set("preferred_storage_state", "MISMATCH");
      if (code === "TRACK_MISSING") params.set("track_state", "MISSING");
      if (code === "MEDIA_MISSING") params.set("media_format_state", "MISSING");
      if (code === "SIZE_MISMATCH") params.set("size_group_state", "MISMATCH");

      // 검색 필터
      const artist = String($("opsExArtist")?.value || "").trim();
      const title  = String($("opsExTitle")?.value  || "").trim();
      const barcode = String($("opsExBarcode")?.value || "").trim();
      const catalogNo = String($("opsExCatalogNo")?.value || "").trim();
      const releaseYear = String($("opsExReleaseYear")?.value || "").trim();
      const domain = String($("opsExceptionDomain")?.value || "").trim();
      if (artist)      params.set("artist_or_brand", artist);
      if (title)       params.set("item_name", title);
      if (barcode)     params.set("barcode", barcode);
      if (catalogNo)   params.set("catalog_no", catalogNo);
      if (releaseYear) params.set("release_year", releaseYear);
      if (domain)      params.set("domain_code", domain);

      // 상세 검색 조건 (OwnedItem 예외 타입에만 적용)
      const opsExPkgVals = [];
      $("opsExPackagingList")?.querySelectorAll("input:checked").forEach(cb => opsExPkgVals.push(cb.value));
      const opsExContentsVals = [];
      $("opsExPackageContentsList")?.querySelectorAll("input:checked").forEach(cb => opsExContentsVals.push(cb.value));
      opsExPkgVals.forEach(v => params.append("packaging", v));
      opsExContentsVals.forEach(v => params.append("package_contents", v));
      if ($("opsExSigDirect")?.checked) params.append("signature_types", "IN_PERSON");
      if ($("opsExSigPurchase")?.checked) params.append("signature_types", "PURCHASE_INCLUDED");
      if ($("opsExNewProduct")?.checked) params.set("is_new", "true");
      if ($("opsExPromo")?.checked) params.set("is_promo", "true");
      if ($("opsExLimitEd")?.checked) params.set("is_limited", "true");
      return params;
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


    let _dashCharts = {};

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

    function hexToRgb(hex) {
      var m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
      return m ? parseInt(m[1],16)+','+parseInt(m[2],16)+','+parseInt(m[3],16) : '128,128,128';
    }

    /* 대시보드 카드 공용 — 도메인 코드 → 표시명 */
    var _DOMAIN_LABEL = {
      KOREA:'가요', JAPAN:'J-POP', WESTERN:'팝/웨스턴',
      GREATER_CHINA:'C-Pop', OTHER_ASIA:'아시아', WORLD:'월드',
      UNASSIGNED:'미분류', UNKNOWN:'미분류',
    };
    function _dLabel(code) { return _DOMAIN_LABEL[String(code||'').toUpperCase()] || code || ''; }


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

async function loadDashboardClimate() {
      const outdoorTemp  = document.getElementById("homeDashOutdoorTemp");
      const outdoorHumid = document.getElementById("homeDashOutdoorHumid");
      const indoorTemp   = document.getElementById("homeDashIndoorTemp");
      const indoorHumid  = document.getElementById("homeDashIndoorHumid");
      const indoorBadge  = document.getElementById("homeDashIndoorBadge");
      const humGauge     = document.getElementById("homeDashHumGauge");
      if (!outdoorTemp && !indoorTemp) return;
      function humClass(h) {
        if (h == null) return "";
        if (h > 70 || h < 35) return "hum-alert";
        if (h >= 60 || h < 43) return "hum-warn";
        return "hum-ideal";
      }
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

    function renderMetadataSyncSummary(data) {
      if (!data) {
        $("metaSyncSummary").textContent = "-";
        return;
      }
      const autoText = data.auto_enabled
        ? t("ops.meta_sync.summary.auto_on", { minutes: Number(data.interval_minutes || 0) })
        : t("ops.meta_sync.summary.auto_off");
      const runningText = data.running ? t("ops.meta_sync.summary.state.running") : t("ops.meta_sync.summary.state.idle");
      const last = data.last_result || null;
      const lastText = last
        ? t("ops.meta_sync.summary.last_result", {
            processed: last.processed_count,
            updated: last.updated_count,
            skipped: last.skipped_count,
            failed: last.failed_count,
            completed: last.completed_at,
          })
        : t("ops.meta_sync.summary.last_result_none");
      const lastError = String(data.last_error || "").trim();
      const errorText = lastError ? ` | ${t("ops.meta_sync.summary.last_error", { error: lastError })}` : "";
      $("metaSyncSummary").textContent =
        t("ops.meta_sync.summary.full", {
          auto: autoText,
          limit: Number(data.batch_limit || 0),
          state: runningText,
          last: lastText,
          error: errorText,
        });
    }

    async function loadMetadataSyncStatus() {
      try {
        setStatus("metaSyncStatusBox", "ok", t("ops.meta_sync.status.load_loading"));
        const res = await fetch("/metadata-sync/status");
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("ops.meta_sync.status.load_failed"));
        renderMetadataSyncSummary(data);
        if (!$("metaSyncLimit").value.trim()) {
          $("metaSyncLimit").value = String(Number(data.batch_limit || 300));
        }
        setStatus(
          "metaSyncStatusBox",
          "ok",
          t("ops.meta_sync.status.load_complete", {
            state: data.running ? t("ops.meta_sync.state.running") : t("ops.meta_sync.state.idle"),
          })
        );
      } catch (err) {
        setStatus("metaSyncStatusBox", "err", errorMessageText(err, t("ops.meta_sync.status.load_failed")));
      }
    }

    async function loadOpsSystemStatus() {
      const summaryEl = $("opsSystemStatusSummary");
      const lineEl = $("opsSystemStatusLine");
      const linksEl = $("opsSystemStatusLinks");
      const pathsEl = $("opsSystemStatusPaths");
      const recentLogEl = $("opsSystemStatusRecentLog");
      const qaLineEl = $("opsQaStatusLine");
      const qaPathsEl = $("opsQaStatusPaths");
      const qaRemainingEl = $("opsQaRemainingList");
      if (!summaryEl || !lineEl || !linksEl || !pathsEl || !recentLogEl || !qaLineEl || !qaPathsEl || !qaRemainingEl) return;
      summaryEl.textContent = t("ops.system.summary.loading");
      lineEl.textContent = t("ops.system.line.load");
      linksEl.innerHTML = "";
      pathsEl.textContent = "";
      recentLogEl.textContent = "";
      qaLineEl.textContent = t("ops.system.line.qa");
      qaPathsEl.textContent = "";
      qaRemainingEl.textContent = "";
      try {
        const res = await fetch("/system/status");
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("ops.status.load_failed")));
        const syncRunning = Boolean(data?.metadata_sync_running);
        const syncLastError = String(data?.metadata_sync_last_error || "").trim();
        const recentLaunchdLines = Array.isArray(data?.recent_launchd_lines)
          ? data.recent_launchd_lines.map((line) => String(line || "").trim()).filter(Boolean)
          : [];
        const qaSummary = data?.qa_summary || {};
        const qaRemaining = Array.isArray(qaSummary?.remaining_items) ? qaSummary.remaining_items : [];
        const summaryText = syncLastError
          ? t("ops.system.summary.warning_sync_error")
          : (syncRunning ? t("ops.system.summary.healthy_running") : t("ops.system.summary.healthy_idle"));
        summaryEl.textContent = summaryText;
        lineEl.textContent = t("ops.system.status_line", {
          health: String(data?.health || "-"),
          state: syncRunning ? t("ops.meta_sync.state.running") : t("ops.meta_sync.state.idle"),
          error: syncLastError ? t("ops.system.status_line_error_suffix", { error: syncLastError }) : "",
        });
        linksEl.innerHTML = t("ops.system.links", {
          login_link: `<a href="${escapeHtml(String(data?.external_login_url || "https://__PROD_DOMAIN__/login"))}" target="_blank" rel="noreferrer">__PROD_DOMAIN__/login</a>`,
          health_link: `<a href="${escapeHtml(String(data?.external_health_url || "https://__PROD_DOMAIN__/health"))}" target="_blank" rel="noreferrer">__PROD_DOMAIN__/health</a>`,
        });
        pathsEl.textContent = t("ops.system.paths", {
          path: String(data?.launchd_err_log || "/Volumes/Data/Works/07.__PROJECT_SLUG__/logs/launchd/library.err.log"),
        });
        recentLogEl.textContent = recentLaunchdLines.length
          ? t("ops.system.logs.recent", { lines: recentLaunchdLines.join(" | ") })
          : t("ops.system.logs.recent_none");
        qaLineEl.textContent = t("ops.system.qa.summary", {
          pass_count: formatCount(Number(qaSummary?.pass_count || 0)),
          total_count: formatCount(Number(qaSummary?.total_count || 0)),
          fail_count: formatCount(Number(qaSummary?.fail_count || 0)),
          blocked_count: formatCount(Number(qaSummary?.blocked_count || 0)),
          not_started_count: formatCount(Number(qaSummary?.not_started_count || 0)),
        });
        qaPathsEl.innerHTML = t("ops.system.qa.paths", {
          master_link: `<a href="${escapeHtml(String(qaSummary?.qa_master_sheet || "/Volumes/Data/Works/07.__PROJECT_SLUG__/docs/qa/qa_master_sheet.csv"))}" target="_blank" rel="noreferrer">qa_master_sheet.csv</a>`,
          manual_link: `<a href="${escapeHtml(String(qaSummary?.qa_manual_sheet || "/Volumes/Data/Works/07.__PROJECT_SLUG__/docs/qa/qa_manual_remaining.csv"))}" target="_blank" rel="noreferrer">qa_manual_remaining.csv</a>`,
          updated: qaSummary?.updated_at
            ? t("ops.system.qa.updated_suffix", { updated_at: escapeHtml(String(qaSummary.updated_at)) })
            : "",
        });
        qaRemainingEl.textContent = qaRemaining.length
          ? t("ops.system.qa.remaining_examples", {
              items: qaRemaining.map((row) => `[${String(row.priority || "-")}] ${String(row.suite_id || "-")} ${String(row.title || "-")}`).join(" | "),
            })
          : t("ops.system.qa.remaining_none");
      } catch (err) {
        summaryEl.textContent = t("ops.system.summary.failure");
        lineEl.textContent = errorMessageText(err, t("ops.status.load_failed"));
        linksEl.innerHTML = t("ops.system.links", {
          login_link: `<a href="https://__PROD_DOMAIN__/login" target="_blank" rel="noreferrer">__PROD_DOMAIN__/login</a>`,
          health_link: `<a href="https://__PROD_DOMAIN__/health" target="_blank" rel="noreferrer">__PROD_DOMAIN__/health</a>`,
        });
        pathsEl.textContent = t("ops.system.paths", {
          path: "/Volumes/Data/Works/07.__PROJECT_SLUG__/logs/launchd/library.err.log | /Volumes/Data/Works/07.__PROJECT_SLUG__/logs/launchd/library.out.log",
        });
        recentLogEl.textContent = t("ops.system.logs.recent_load_failed");
        qaLineEl.textContent = t("ops.system.qa.load_failed");
        qaPathsEl.textContent = t("ops.system.qa.paths", {
          master_link: "/Volumes/Data/Works/07.__PROJECT_SLUG__/docs/qa/qa_master_sheet.csv",
          manual_link: "/Volumes/Data/Works/07.__PROJECT_SLUG__/docs/qa/qa_manual_remaining.csv",
          updated: "",
        });
        qaRemainingEl.textContent = t("ops.system.qa.load_failed");
      }
    }

    function downloadFilenameFromResponse(res, fallback = "download.bin") {
      const disposition = String(res?.headers?.get("content-disposition") || "").trim();
      if (!disposition) return fallback;
      const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
      if (utf8Match && utf8Match[1]) {
        try {
          return decodeURIComponent(utf8Match[1]);
        } catch (_) {
          return utf8Match[1];
        }
      }
      const plainMatch = disposition.match(/filename=\"?([^\";]+)\"?/i);
      if (plainMatch && plainMatch[1]) return plainMatch[1];
      return fallback;
    }

    async function triggerBrowserDownload(url, fallbackFilename = "download.bin") {
      const res = await fetch(url, {
        method: "GET",
        credentials: "same-origin",
      });
      if (!res.ok) {
        const data = await safeJson(res);
        throw new Error(data.detail || t("common.download_failed_status", { status: res.status }));
      }
      const blob = await res.blob();
      const filename = downloadFilenameFromResponse(res, fallbackFilename);
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = filename;
      a.rel = "noreferrer";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
      return filename;
    }

    async function runMetadataSyncNow() {
      const limit = Math.max(1, Math.min(5000, Number($("metaSyncLimit").value || 300)));
      const inter_item_delay_sec = Math.max(0, Math.min(60, Number($("metaSyncDelay").value ?? 1.5)));
      const payload = {
        source: $("metaSyncSource").value,
        only_missing: $("metaSyncOnlyMissing").checked,
        supplement_discogs: $("metaSyncSupplementDiscogs").checked,
        limit,
        inter_item_delay_sec,
        include_item_results: true,
      };

      try {
        setStatus("metaSyncStatusBox", "ok", t("ops.meta_sync.status.run_loading"));
        const logEl = $("metaSyncItemLog");
        if (logEl) { logEl.hidden = true; logEl.innerHTML = ""; }

        // POST to start — server returns 202 immediately (avoids Cloudflare 524 timeout)
        const res = await fetch("/metadata-sync/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("ops.meta_sync.status.run_failed"));

        // Poll /metadata-sync/status until running=false; render items incrementally
        let renderedCount = 0;
        let dot = 0;
        while (true) {
          await new Promise(r => setTimeout(r, 2000));
          try {
            const sRes = await fetch("/metadata-sync/status");
            const sData = await safeJson(sRes);
            if (!sRes.ok) break;
            if (sData.running) {
              dot = (dot + 1) % 4;
              const liveItems = sData.in_progress_items || [];
              const total = liveItems.length;
              setStatus("metaSyncStatusBox", "ok",
                t("ops.meta_sync.status.run_loading") + " " + ".".repeat(dot + 1) +
                (total > 0 ? `  (${total})` : "")
              );
              // Append only newly processed items
              if (liveItems.length > renderedCount) {
                appendMetaSyncItemLogRows(liveItems.slice(renderedCount));
                renderedCount = liveItems.length;
              }
              continue;
            }
            // Completed — render any remaining items from final result
            const result = sData.last_result || {};
            const finalItems = result.item_results || [];
            if (finalItems.length > renderedCount) {
              appendMetaSyncItemLogRows(finalItems.slice(renderedCount));
            }
            setStatus(
              "metaSyncStatusBox",
              "ok",
              t("ops.meta_sync.status.run_complete", {
                processed: result.processed_count ?? 0,
                updated: result.updated_count ?? 0,
                skipped: result.skipped_count ?? 0,
                failed: result.failed_count ?? 0,
              })
            );
            updateMetaSyncItemLogFooter(finalItems);
            await loadMetadataSyncStatus();
            break;
          } catch (_) {
            break;
          }
        }
      } catch (err) {
        setStatus("metaSyncStatusBox", "err", errorMessageText(err, t("ops.meta_sync.status.run_failed")));
      }
    }

    function _buildSyncLogRow(item) {
      const STATUS_CLASS = { UPDATED: "updated", SKIPPED: "skipped", FAILED: "failed" };
      const row = document.createElement("div");
      row.className = "sync-log-row";
      const status = String(item.status || "").toUpperCase();
      const cls = STATUS_CLASS[status] || "skipped";

      let productHtml = "";
      const name = String(item.display_name || "").trim();
      const artist = String(item.artist_or_brand || "").trim();
      const catalog = String(item.catalog_no || "").trim();
      if (name) {
        productHtml = `<span class="sync-log-product-name">${name}</span>`;
        if (artist && artist !== name) productHtml += `<br><span style="color:var(--muted);font-size:0.65rem">${artist}</span>`;
        if (catalog) productHtml += `<span style="color:var(--muted);font-size:0.65rem"> · ${catalog}</span>`;
      } else if (artist || catalog) {
        productHtml = `<span class="sync-log-product-name">${artist || "-"}</span>`;
        if (catalog) productHtml += `<br><span style="color:var(--muted);font-size:0.65rem">${catalog}</span>`;
      } else {
        productHtml = `<span style="color:var(--muted)">-</span>`;
      }

      let detailHtml = "";
      if (status === "UPDATED" && Array.isArray(item.updated_fields) && item.updated_fields.length > 0) {
        const tags = item.updated_fields.map(f => `<span class="field-tag">${f}</span>`).join("");
        detailHtml = `<div class="fields">${tags}</div>`;
      } else if (item.reason) {
        detailHtml = `<span style="color:var(--muted)">${item.reason}</span>`;
      } else {
        detailHtml = `<span style="color:var(--muted)">${item.source_external_id || "-"}</span>`;
      }

      row.innerHTML = `
        <span><span class="sync-log-badge ${cls}">${status}</span></span>
        <span class="sync-log-id">#${item.owned_item_id}</span>
        <span class="sync-log-source">${item.source_code}</span>
        <span class="sync-log-detail">${productHtml}</span>
        <span class="sync-log-detail">${detailHtml}</span>
      `;
      return row;
    }

    function _getOrCreateSyncLogBody() {
      const el = $("metaSyncItemLog");
      if (!el) return null;
      el.hidden = false;
      if (!el.querySelector(".sync-item-log-header")) {
        const header = document.createElement("div");
        header.className = "sync-item-log-header";
        header.innerHTML = `<span>상태</span><span>ID</span><span>소스</span><span>상품</span><span>내용</span>`;
        el.appendChild(header);
        const body = document.createElement("div");
        body.className = "sync-item-log-body";
        el.appendChild(body);
        const foot = document.createElement("div");
        foot.className = "sync-log-count";
        el.appendChild(foot);
      }
      return el.querySelector(".sync-item-log-body");
    }

    function appendMetaSyncItemLogRows(newItems) {
      if (!newItems || newItems.length === 0) return;
      const body = _getOrCreateSyncLogBody();
      if (!body) return;
      newItems.forEach(item => body.appendChild(_buildSyncLogRow(item)));
      // Scroll to bottom to show newest items
      const el = $("metaSyncItemLog");
      if (el) el.scrollTop = el.scrollHeight;
    }

    function updateMetaSyncItemLogFooter(allItems) {
      const el = $("metaSyncItemLog");
      if (!el) return;
      const foot = el.querySelector(".sync-log-count");
      if (!foot) return;
      const updated = (allItems || []).filter(i => i.status === "UPDATED").length;
      const skipped = (allItems || []).filter(i => i.status === "SKIPPED").length;
      const failed  = (allItems || []).filter(i => i.status === "FAILED").length;
      foot.textContent = `총 ${(allItems || []).length}건 — 반영 ${updated} / 스킵 ${skipped} / 실패 ${failed}`;
    }

    function renderMetaSyncItemLog(items) {
      const el = $("metaSyncItemLog");
      if (!el) return;
      el.innerHTML = "";
      if (!items || items.length === 0) { el.hidden = true; return; }
      appendMetaSyncItemLogRows(items);
      updateMetaSyncItemLogFooter(items);
    }

    // -----------------------------------------------------------------------
    // 알라딘 → Discogs 마스터 매칭 백필
    // -----------------------------------------------------------------------
    let _aladinDiscogsBackfillPoller = null;

    function renderAladinDiscogsBackfillStatus(data) {
      const summaryEl = $("aladinDiscogsBackfillSummary");
      const listEl = $("aladinDiscogsBackfillMatchedList");
      if (!summaryEl) return;

      const running = Boolean(data?.running);
      const lastErr = String(data?.last_error || "").trim();
      const r = data?.last_result;

      if (!r && !lastErr) {
        summaryEl.textContent = running ? "⏳ 실행 중..." : "실행 이력 없음";
        if (listEl) listEl.style.display = "none";
        return;
      }

      if (lastErr && !r) {
        summaryEl.textContent = `오류: ${lastErr}`;
        if (listEl) listEl.style.display = "none";
        return;
      }

      const dryTag = r.dry_run ? " [DRY-RUN]" : "";
      const finishedAt = r.finished_at ? ` | 완료: ${r.finished_at}` : (running ? " | 실행 중..." : "");
      summaryEl.textContent =
        `${dryTag} 스캔 ${r.scanned}건 | 매칭 신규 ${r.master_created}건 | 이미연결 ${r.already_discogs}건 | detail업데이트 ${r.detail_updated}건 | crossref없음 ${r.no_crossref}건 | 오류 ${r.error}건${finishedAt}`;

      const matched = Array.isArray(r.matched_items) ? r.matched_items : [];
      if (!listEl) return;
      if (matched.length === 0) {
        listEl.style.display = "none";
        return;
      }
      listEl.style.display = "";
      listEl.innerHTML = `<div class="result-head u-mt-8"><strong>매칭된 항목 (${matched.length}건)</strong></div>` +
        `<table style="width:100%;font-size:0.82em;border-collapse:collapse;margin-top:6px">` +
        `<thead><tr style="border-bottom:1px solid var(--border)">` +
        `<th style="text-align:left;padding:3px 6px">ID</th>` +
        `<th style="text-align:left;padding:3px 6px">아티스트 / 타이틀</th>` +
        `<th style="text-align:left;padding:3px 6px">포맷</th>` +
        `<th style="text-align:left;padding:3px 6px">바코드</th>` +
        `<th style="text-align:left;padding:3px 6px">레이블</th>` +
        `<th style="text-align:left;padding:3px 6px">액션</th>` +
        `</tr></thead><tbody>` +
        matched.map(m => {
          const discogsUrl = m.discogs_release_id
            ? `<a href="https://www.discogs.com/release/${escapeHtml(String(m.discogs_release_id))}" target="_blank" rel="noreferrer">${escapeHtml(String(m.discogs_release_id))}</a>`
            : "-";
          const actionLabel = m.action === "created" ? "마스터 생성" : m.action === "dry_run" ? "DRY-RUN" : "detail만 업데이트";
          return `<tr style="border-bottom:1px solid var(--border-light)">` +
            `<td style="padding:3px 6px">${m.owned_item_id} / ${discogsUrl}</td>` +
            `<td style="padding:3px 6px">${escapeHtml(String(m.artist || ""))} — ${escapeHtml(String(m.title || ""))}</td>` +
            `<td style="padding:3px 6px">${escapeHtml(String(m.format || "-"))}</td>` +
            `<td style="padding:3px 6px">${escapeHtml(String(m.barcode || "-"))}</td>` +
            `<td style="padding:3px 6px">${escapeHtml(String(m.label || "-"))}</td>` +
            `<td style="padding:3px 6px">${actionLabel}</td>` +
            `</tr>`;
        }).join("") +
        `</tbody></table>`;
    }

    async function loadAladinDiscogsBackfillStatus() {
      try {
        setStatus("aladinDiscogsBackfillStatusBox", "ok", "상태 확인 중...");
        const res = await fetch("/aladin-discogs-backfill/status");
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || "상태 조회 실패");
        renderAladinDiscogsBackfillStatus(data);

        if (data.running) {
          setStatus("aladinDiscogsBackfillStatusBox", "ok", "⏳ 실행 중... (자동 폴링 중)");
          _startAladinDiscogsBackfillPoller();
        } else {
          setStatus("aladinDiscogsBackfillStatusBox", data.last_error ? "err" : "ok",
            data.last_error ? `오류: ${data.last_error}` : "상태 확인 완료");
          _stopAladinDiscogsBackfillPoller();
        }
      } catch (err) {
        setStatus("aladinDiscogsBackfillStatusBox", "err", errorMessageText(err, "상태 조회 실패"));
      }
    }

    function _startAladinDiscogsBackfillPoller() {
      if (_aladinDiscogsBackfillPoller) return;
      _aladinDiscogsBackfillPoller = setInterval(async () => {
        try {
          const res = await fetch("/aladin-discogs-backfill/status");
          const data = await safeJson(res);
          renderAladinDiscogsBackfillStatus(data);
          if (!data.running) {
            _stopAladinDiscogsBackfillPoller();
            const runBtn = $("aladinDiscogsBackfillRunBtn");
            if (runBtn) runBtn.disabled = false;
            setStatus("aladinDiscogsBackfillStatusBox", data.last_error ? "err" : "ok",
              data.last_error ? `오류: ${data.last_error}` : "✅ 완료");
          }
        } catch (_) {}
      }, 5000);
    }

    function _stopAladinDiscogsBackfillPoller() {
      if (_aladinDiscogsBackfillPoller) {
        clearInterval(_aladinDiscogsBackfillPoller);
        _aladinDiscogsBackfillPoller = null;
      }
    }

    let _spotifyBatchPoller = null;

    async function loadSpotifyBatchStatus() {
      try {
        const res = await fetchWithRetry("/album-masters/spotify/batch/status");
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || "상태 조회 실패");
        const running = data.running;
        const result = data.last_result;
        const err = data.last_error;
        if (running) {
          setStatus("spotifyBatchStatusBox", "ok", "⏳ 실행 중...");
          $("spotifyBatchSummary").textContent = "-";
          return;
        }
        if (err) {
          setStatus("spotifyBatchStatusBox", "err", `오류: ${err}`);
        } else if (result) {
          setStatus("spotifyBatchStatusBox", "ok", `✅ 완료 — 매칭 ${result.matched}건, 미매칭 ${result.skipped}건, 오류 ${result.errors}건`);
        } else {
          setStatus("spotifyBatchStatusBox", "", "대기 중");
        }
      } catch (err) {
        setStatus("spotifyBatchStatusBox", "err", errorMessageText(err, "상태 조회 실패"));
      }
    }

    function _startSpotifyBatchPoller() {
      _stopSpotifyBatchPoller();
      _spotifyBatchPoller = setInterval(async () => {
        try {
          const res = await fetchWithRetry("/album-masters/spotify/batch/status");
          const data = await safeJson(res);
          if (!res.ok) return;
          if (!data.running) {
            _stopSpotifyBatchPoller();
            const runBtn = $("spotifyBatchRunBtn");
            if (runBtn) runBtn.disabled = false;
            if (data.last_error) {
              setStatus("spotifyBatchStatusBox", "err", `오류: ${data.last_error}`);
            } else if (data.last_result) {
              const r = data.last_result;
              setStatus("spotifyBatchStatusBox", "ok", `✅ 완료 — 매칭 ${r.matched}건, 미매칭 ${r.skipped}건, 오류 ${r.errors}건`);
            }
          }
        } catch (_) {}
      }, 5000);
    }

    function _stopSpotifyBatchPoller() {
      if (_spotifyBatchPoller) {
        clearInterval(_spotifyBatchPoller);
        _spotifyBatchPoller = null;
      }
    }

    async function runSpotifyBatch() {
      const limit = Math.max(1, Math.min(500, Number($("spotifyBatchLimit").value || 50)));
      const requireTracks = $("spotifyBatchRequireTracks").checked;
      const runBtn = $("spotifyBatchRunBtn");
      try {
        setStatus("spotifyBatchStatusBox", "ok", "⏳ 배치 시작 요청 중...");
        if (runBtn) runBtn.disabled = true;
        const url = `/album-masters/spotify/batch/run?limit=${limit}&require_tracks=${requireTracks}`;
        const res = await fetchWithRetry(url, { method: "POST" });
        const data = await safeJson(res);
        if (!res.ok) {
          if (runBtn) runBtn.disabled = false;
          throw new Error(data.detail || "실행 요청 실패");
        }
        setStatus("spotifyBatchStatusBox", "ok", `⏳ 실행 중... ${limit}건 처리, 자동으로 결과를 불러옵니다.`);
        _startSpotifyBatchPoller();
      } catch (err) {
        if (runBtn) runBtn.disabled = false;
        setStatus("spotifyBatchStatusBox", "err", errorMessageText(err, "실행 요청 실패"));
      }
    }

    async function runAladinDiscogsBackfill() {
      const dryRun = $("aladinDiscogsBackfillDryRun").checked;
      const sleepSec = parseFloat($("aladinDiscogsBackfillSleep").value || "2.0");
      const runBtn = $("aladinDiscogsBackfillRunBtn");

      try {
        setStatus("aladinDiscogsBackfillStatusBox", "ok", "⏳ 매칭 시작 요청 중...");
        if (runBtn) runBtn.disabled = true;
        const url = `/aladin-discogs-backfill/run?dry_run=${dryRun}&sleep_sec=${sleepSec}`;
        const res = await fetch(url, { method: "POST" });
        const data = await safeJson(res);
        if (!res.ok) {
          if (runBtn) runBtn.disabled = false;
          throw new Error(data.detail || "실행 요청 실패");
        }
        setStatus("aladinDiscogsBackfillStatusBox", "ok",
          `⏳ 실행 중${dryRun ? " (DRY-RUN)" : ""}... 완료까지 수분 소요. 자동으로 결과를 불러옵니다.`);
        _startAladinDiscogsBackfillPoller();
      } catch (err) {
        if (runBtn) runBtn.disabled = false;
        setStatus("aladinDiscogsBackfillStatusBox", "err", errorMessageText(err, "실행 요청 실패"));
      }
    }

    function resolveOwnedAlbumName(row) {
      const name = String(row.item_name_override || "").trim();
      if (name) return name;
      const label = String(row.label_name || "").trim();
      const cat = String(row.catalog_no || "").trim();
      if (label || cat) return `${label || "Unknown Label"}${cat ? ` / ${cat}` : ""}`;
      return `${row.category || "ITEM"} #${row.id}`;
    }

    function normalizeRenderableCoverUrl(value) {
      const raw = String(value || "").trim();
      if (!raw) return "";
      return raw.replace(/^http:\/\/i\.maniadb\.com\//i, "https://i.maniadb.com/");
    }

    function resolveAlternateManiadbCoverUrl(value) {
      const normalized = normalizeRenderableCoverUrl(value);
      if (!normalized) return "";
      const currentMatch = normalized.match(/^(https:\/\/i\.maniadb\.com\/images\/album\/\d+\/\d+)_(\d+)_([fb])\.jpg$/i);
      if (currentMatch) {
        return `${currentMatch[1]}_${currentMatch[3]}_${currentMatch[2]}.jpg`;
      }
      const legacyMatch = normalized.match(/^(https:\/\/i\.maniadb\.com\/images\/album\/\d+\/\d+)_([fb])_(\d+)\.jpg$/i);
      if (legacyMatch) {
        return `${legacyMatch[1]}_${legacyMatch[3]}_${legacyMatch[2]}.jpg`;
      }
      return "";
    }

    function applyBrokenCoverFallback(img) {
      if (!(img instanceof HTMLImageElement)) return;
      const currentSrc = normalizeRenderableCoverUrl(img.currentSrc || img.src || img.getAttribute("src"));
      if (!currentSrc) return;
      const alternateSrc = resolveAlternateManiadbCoverUrl(currentSrc);
      if (alternateSrc && alternateSrc !== currentSrc && img.dataset.coverFallbackTried !== "1") {
        img.dataset.coverFallbackTried = "1";
        img.src = alternateSrc;
        return;
      }
      if (img.id === "imageGalleryPreviewImg") {
        img.removeAttribute("src");
        setDisplayMode(img, "none");
        $("imageGalleryOpenOriginal").href = "#";
        $("imageGalleryOpenOriginal").style.pointerEvents = "none";
        $("imageGalleryOpenOriginal").style.opacity = "0.45";
        $("imageGalleryPreviewMeta").innerHTML = `<span>${escapeHtml(t("common.no_cover"))}</span>`;
        return;
      }
      const coverHost = img.closest(".album-result-cover, .home-master-member-preview-cover, .table-cover-thumb, .dashboard-move-cover, .operator-cover, .image-gallery-thumb");
      if (!coverHost || coverHost.dataset.coverFallbackResolved === "1") return;
      coverHost.dataset.coverFallbackResolved = "1";
      coverHost.textContent = t("common.no_cover");
    }

    function resolveOwnedItemCoverUrl(row) {
      const primary = normalizeRenderableCoverUrl(row?.cover_image_url || row?.goods_primary_image_url);
      if (primary) return primary;
      return "";
    }

    function cleanLinkedGoodsMemoryNote(value) {
      const lines = String(value || "")
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => line && !/^\[LINKED_GOODS\]\s*/i.test(line));
      return lines.join(" / ");
    }

    function isMusicOwnedRow(row) {
      return MUSIC_CATEGORIES.has(String(row?.category || "").trim().toUpperCase());
    }

    function resolveAlbumMasterName(row) {
      const title = String(row?.title || "").trim();
      if (title) return title;
      const source = String(row?.source_code || "MASTER").trim();
      return `${source} master #${row?.id ?? "-"}`;
    }

    function normalizeLookupToken(value) {
      return String(value || "").replace(/[^0-9A-Za-z]/g, "").trim().toLowerCase();
    }

    function buildSourceWorkbenchDiffFieldRows(payload = {}) {
      const item = payload?.item || {};
      const candidate = payload?.candidate || {};
      return sourceWorkbenchDiffFieldDefs().map((definition) => {
        const currentValue = sourceWorkbenchDiffResolveValue({ ...definition, itemKeys: definition.itemKeys }, item);
        const candidateValue = sourceWorkbenchDiffResolveValue({ ...definition, itemKeys: definition.candidateKeys }, candidate);
        const status = sourceWorkbenchDiffStatusCode(definition, currentValue, candidateValue);
        const disabled = status === "SAME" || status === "EMPTY_BOTH";
        return {
          key: definition.key,
          label: definition.label,
          labelKey: definition.labelKey || "",
          presentation: definition.presentation,
          currentValue,
          candidateValue,
          currentDisplay: definition.key === "track_list" ? sourceWorkbenchDiffNormalizeList(currentValue) : sourceWorkbenchDiffNormalizeScalar(currentValue),
          candidateDisplay: definition.key === "track_list" ? sourceWorkbenchDiffNormalizeList(candidateValue) : sourceWorkbenchDiffNormalizeScalar(candidateValue),
          status,
          statusLabel: sourceWorkbenchDiffStatusLabel(status),
          statusLabelKey: sourceWorkbenchDiffStatusLabelKey(status),
          selected: status === "EMPTY_FILL",
          disabled,
          visible: true,
        };
      });
    }

    function buildSourceWorkbenchDiffReviewState(payload = {}) {
      const selectedRows = Array.isArray(payload?.selectedRows) ? payload.selectedRows : [];
      const items = selectedRows.map((entry) => {
        const item = entry?.item || {};
        const candidateList = Array.isArray(entry?.candidates) ? entry.candidates : [];
        const candidate = candidateList[Number(entry?.selectedIdx || 0)] || {};
        const fieldRows = buildSourceWorkbenchDiffFieldRows({ item, candidate });
        return {
          ownedItemId: Number(item?.id || 0),
          labelId: String(item?.label_id || "").trim() || "-",
          currentTitle: sourceWorkbenchDiffNormalizeScalar(item?.item_title || item?.item_name_override) || "-",
          candidateSource: sourceWorkbenchDiffNormalizeScalar(candidate?.source) || "-",
          candidateTitle: sourceWorkbenchDiffNormalizeScalar(candidate?.title || candidate?.item_title || candidate?.item_name_override) || "-",
          candidateExternalId: sourceWorkbenchDiffNormalizeScalar(candidate?.external_id) || "",
          candidate,
          fieldRows,
        };
      }).filter((entry) => entry.ownedItemId > 0);
      const actionableFieldCount = items.reduce((total, item) => total + item.fieldRows.filter((row) => !row.disabled).length, 0);
      const candidateSources = [...new Set(items.map((item) => item.candidateSource).filter((value) => value && value !== "-"))];
      const reviewState = {
        items,
        summary: {
          itemCount: items.length,
          actionableFieldCount,
          selectedFieldCount: 0,
          candidateSources,
        },
      };
      reviewState.summary.selectedFieldCount = sourceWorkbenchDiffReviewFieldCount(reviewState);
      return reviewState;
    }

    function buildSourceWorkbenchLegacyApplyItems(payload = {}) {
      const selectedRows = Array.isArray(payload?.selectedRows) ? payload.selectedRows : [];
      return selectedRows
        .map((entry) => {
          const ownedItemId = Number(entry?.item?.id || 0);
          const candidateList = Array.isArray(entry?.candidates) ? entry.candidates : [];
          const candidate = candidateList[Number(entry?.selectedIdx ?? -1)] || null;
          if (ownedItemId <= 0 || !candidate) return null;
          return {
            owned_item_id: ownedItemId,
            candidate,
          };
        })
        .filter(Boolean);
    }

    function buildSourceWorkbenchDiffApplyItems(payload = {}) {
      const reviewItems = Array.isArray(payload?.reviewState?.items) ? payload.reviewState.items : [];
      return reviewItems
        .map((item) => {
          const ownedItemId = Number(item?.ownedItemId || 0);
          const candidate = item?.candidate && typeof item.candidate === "object" ? item.candidate : null;
          const selectedFields = Array.isArray(item?.fieldRows)
            ? item.fieldRows
              .filter((row) => row?.selected && !row?.disabled)
              .map((row) => String(row?.key || "").trim())
              .filter(Boolean)
            : [];
          if (ownedItemId <= 0 || !candidate || !selectedFields.length) return null;
          return {
            owned_item_id: ownedItemId,
            candidate,
            selected_fields: selectedFields,
          };
        })
        .filter(Boolean);
    }

    function buildSourceWorkbenchEditionComparatorRows(payload = {}) {
      const current = payload?.current || payload?.item || {};
      const candidate = payload?.candidate || {};
      return sourceWorkbenchEditionComparatorFieldDefs().map((definition) => {
        const currentValue = sourceWorkbenchEditionComparatorResolveValue({ ...definition, itemKeys: definition.itemKeys }, current);
        const candidateValue = sourceWorkbenchEditionComparatorResolveValue({ ...definition, itemKeys: definition.candidateKeys }, candidate);
        const currentAnalysis = sourceWorkbenchEditionComparatorAnalyzeValue(definition, currentValue);
        const candidateAnalysis = sourceWorkbenchEditionComparatorAnalyzeValue(definition, candidateValue);
        const state = sourceWorkbenchEditionComparatorState(currentAnalysis, candidateAnalysis);
        return {
          key: definition.key,
          label: definition.label,
          group: definition.group,
          cardRole: definition.cardRole || definition.group,
          strong: Boolean(definition.strong),
          state,
          currentPreview: currentAnalysis.preview,
          candidatePreview: candidateAnalysis.preview,
          deltaSummary: definition.key === "track_list"
            ? sourceWorkbenchEditionComparatorTrackDeltaSummary(currentAnalysis, candidateAnalysis, state)
            : "",
        };
      });
    }

    function buildSourceWorkbenchEditionComparatorExplanationPhrases(payload = {}) {
      const rows = buildSourceWorkbenchEditionComparatorRows(payload);
      const rowMap = new Map(rows.map((row) => [row.key, row]));
      const phrases = [];
      const artistRow = rowMap.get("artist_name");
      const titleRow = rowMap.get("item_title");
      if (artistRow?.state === "SAME" && titleRow?.state === "SAME") phrases.push("Name matches");
      const catalogPhrase = sourceWorkbenchEditionComparatorPresencePhrase("Catalog no", rowMap.get("catalog_no"));
      if (catalogPhrase) phrases.push(catalogPhrase);
      const barcodePhrase = sourceWorkbenchEditionComparatorPresencePhrase("Barcode", rowMap.get("barcode"));
      if (barcodePhrase) phrases.push(barcodePhrase);
      const countryPhrase = sourceWorkbenchEditionComparatorPresencePhrase("Pressing country", rowMap.get("pressing_country"));
      if (countryPhrase) phrases.push(countryPhrase);
      const trackRow = rowMap.get("track_list");
      if (trackRow?.state === "DIFFERENT") {
        phrases.push(trackRow.deltaSummary ? `Track count differs (${trackRow.deltaSummary})` : "Track listing differs");
      } else if (trackRow?.state === "CANDIDATE_ONLY") {
        phrases.push("Track data only on candidate");
      } else if (trackRow?.state === "CURRENT_ONLY") {
        phrases.push("Track data only on current");
      }
      const runoutRow = rowMap.get("runout_matrix");
      if (runoutRow?.state === "DIFFERENT") {
        phrases.push("Runout differs");
      } else if (runoutRow?.state === "CANDIDATE_ONLY") {
        phrases.push("Runout only on candidate");
      } else if (runoutRow?.state === "CURRENT_ONLY") {
        phrases.push("Runout only on current");
      }
      return phrases;
    }

    function buildSourceWorkbenchEditionComparatorSummary(payload = {}) {
      const rows = buildSourceWorkbenchEditionComparatorRows(payload);
      const rowStateForSummary = (value) => {
        const normalized = String(value || "").trim().toUpperCase();
        return normalized === "DIFFERENT" || normalized === "CANDIDATE_ONLY" || normalized === "CURRENT_ONLY";
      };
      const strongDiffRows = rows.filter((row) => row?.strong && rowStateForSummary(row.state));
      const strongMatchRows = rows.filter((row) => row?.strong && row.state === "SAME");
      const advisoryDiffRows = rows.filter((row) => !row?.strong && rowStateForSummary(row.state));
      const advisoryMatchRows = rows.filter((row) => !row?.strong && row.state === "SAME");
      const summaryParts = [
        ...strongDiffRows.map((row) => sourceWorkbenchEditionComparatorSummaryPhrase(row)).filter((phrase) => phrase),
        ...advisoryDiffRows.map((row) => sourceWorkbenchEditionComparatorSummaryPhrase(row)).filter((phrase) => phrase),
        ...strongMatchRows.map((row) => sourceWorkbenchEditionComparatorSummaryPhrase(row)).filter((phrase) => phrase),
        ...advisoryMatchRows.map((row) => sourceWorkbenchEditionComparatorSummaryPhrase(row)).filter((phrase) => phrase),
      ].slice(0, 3);
      if (!summaryParts.length) return "No comparable edition evidence.";
      const formattedParts = summaryParts.slice(0, 3).map((phrase, index) => {
        if (index === 0) return phrase;
        return phrase ? `${phrase.charAt(0).toLowerCase()}${phrase.slice(1)}` : "";
      }).filter((phrase) => phrase);
      return `${formattedParts.join("; ")}.`;
    }

    function buildSourceWorkbenchSearchRequest(entry, opts = {}) {
      const row = entry?.item || entry || {};
      const source = $("sourceWorkbenchSource").value;
      const limit = Math.max(1, Math.min(10, Number($("sourceWorkbenchCandidateLimit").value || 5)));
      const forceTextSearch = Boolean(opts.forceTextSearch);
      const barcode = String(row?.barcode || "").trim();
      const artist = String(entry?.searchArtistName ?? row?.artist_or_brand ?? row?.linked_artist_name ?? "").trim();
      const title = String(entry?.searchItemName ?? sourceWorkbenchCandidateTitle(row)).trim();
      const catalogNo = String(row?.catalog_no || "").trim();
      if (barcode && !forceTextSearch) {
        return {
          endpoint: "/ingest/barcode",
          payload: {
            barcode,
            category: row.category || null,
            source,
            limit,
          },
          summary: t("media.source.request.summary.barcode", { barcode }),
        };
      }
      if (!artist && !title && !catalogNo) {
        throw new Error(t("media.source.request.error.missing_query"));
      }
      const summaryBits = [artist, title, catalogNo].filter(Boolean);
      return {
        endpoint: "/ingest/search",
        payload: {
          category: row.category || null,
          source,
          artist_or_brand: artist || null,
          title: title || null,
          catalog_no: catalogNo || null,
          limit,
        },
        summary: forceTextSearch
          ? t("media.source.request.summary.override", { summary: summaryBits.join(" / ") })
          : summaryBits.join(" / "),
      };
    }

    function autoSelectSourceWorkbenchCandidate(row, candidates) {
      const list = Array.isArray(candidates) ? candidates : [];
      if (!list.length) return -1;
      const barcode = normalizeLookupToken(row?.barcode);
      if (barcode) {
        const exactIndex = list.findIndex((candidate) => normalizeLookupToken(candidate?.barcode) === barcode);
        if (exactIndex >= 0) return exactIndex;
      }
      return list.length === 1 ? 0 : -1;
    }

    function sourceQueueStatusLabel(status) {
      const code = String(status || "").trim().toUpperCase();
      if (code === "SUCCESS") return t("media.source.queue.status.success");
      if (code === "FAILED") return t("media.source.queue.status.failed");
      if (code === "PENDING") return t("media.source.queue.status.pending");
      return code || "-";
    }

    function sourceQueueModeLabel(mode) {
      const code = String(mode || "").trim().toUpperCase();
      if (code === "AUTO_READY") return t("media.source.queue.mode.auto_ready");
      if (code === "ROW_UPDATE") return t("media.source.queue.mode.row_update");
      if (code === "MANUAL_BATCH") return t("media.source.queue.mode.manual_batch");
      return code || "-";
    }

    function saveSourceWorkbenchQueue() {
      try {
        window.localStorage.setItem(
          SOURCE_WORKBENCH_QUEUE_KEY,
          JSON.stringify(Array.isArray(sourceWorkbenchQueue) ? sourceWorkbenchQueue.slice(0, 200) : [])
        );
      } catch (_err) {}
    }

    function pushSourceWorkbenchQueueEntries(entries) {
      const list = Array.isArray(entries) ? entries.filter(Boolean) : [];
      if (!list.length) return;
      sourceWorkbenchQueue = [...list, ...sourceWorkbenchQueue].slice(0, 200);
      saveSourceWorkbenchQueue();
      renderSourceWorkbenchQueue();
    }

    function seedSourceWorkbenchFromOwnedItem(row) {
      if (!row || typeof row !== "object") return;
      $("homeArtist").value = String(row.artist_or_brand || row.linked_artist_name || "").trim();
      $("homeItemName").value = String(row.item_name_override || "").trim();
      $("homeCatalogNo").value = String(row.catalog_no || "").trim();
      $("homeBarcode").value = String(row.barcode || "").trim();
      $("homeReleaseYear").value = row.release_year ? String(row.release_year) : "";
      $("sourceWorkbenchSourceState").value = "MISSING";
    }

    function loadMasterOwnedRowsFromItems(rows, statusText) {
      const items = Array.isArray(rows) ? rows.filter(Boolean) : [];
      masterOwnedPrefilledIds = new Set(items.map((row) => Number(row?.id || 0)).filter((id) => id > 0));
      $("masterOwnedQ").value = String(items[0]?.item_name_override || items[0]?.artist_or_brand || "").trim();
      $("masterOwnedBody").innerHTML = items.map(masterOwnedRowHtml).join("") ||
        `<tr><td colspan='6' class='muted'>${escapeHtml(t("media.source.queue.empty"))}</td></tr>`;
      syncMasterExceptionBanner();
      switchMainTab("register");
      switchSubTab("register", "master");
      setStatus("masterOwnedStatus", "ok", statusText || t("media.source.status.master_prep_ready", {
        count: countWithUnit(items.length),
      }));
      setStatus("bindMasterStatus", "ok", t("media.register.master.bind.status.instructions"));
    }

    function refreshOpsExceptionInBackground() {
      loadOpsExceptionCounts({ silent: true }).catch(() => {});
      const opsActive = $("tabOps")?.classList.contains("active");
      const exceptionActive = $("opsExceptionPanel")?.classList.contains("active");
      if (opsActive && exceptionActive) {
        loadOpsExceptionItems({ silent: true }).catch(() => {});
      }
    }

    function refreshHomeDashboardInBackground() {
      loadHomeDashboard({ silent: true }).catch(() => {});
    }

    function refreshHomeSearchInBackground() {
      homeSearchOwnedItems({ allowPageAdjust: false, suppressEmptyCta: true }).catch(() => {});
    }

    function renderOpsExceptionSummary() {
      const root = $("opsExceptionSummary");
      if (!root) return;
      const activeType = String($("opsExceptionType")?.value || "UNSLOTTED").trim().toUpperCase();
      const types = ["UNSLOTTED", "SOURCE_MISSING", "MASTER_MISSING", "COVER_MISSING", "PREFERRED_SIZE_MISMATCH", "MEDIA_MISSING", "SIZE_MISMATCH", "TRACK_MISSING", "SPOTIFY_UNMATCHED", "REVIEW_MISSING", "GENRE_MISSING", "CATALOG_MISSING", "LOCAL_MISSING", "RELEASE_TYPE_MISSING"];
      root.innerHTML = types.map((type) => `
        <button
          class="ops-exception-box ${activeType === type ? "active" : ""}"
          type="button"
          data-ops-exception-summary="${type}"
        >
          <strong>${countWithUnit(opsExceptionCounts[type] || 0)}</strong>
          <span>${escapeHtml(opsExceptionTypeLabel(type))}</span>
          <span>${escapeHtml(opsExceptionTypeHint(type))}</span>
        </button>
      `).join("");
    }

    function getSelectedOpsExceptionRows() {
      return (Array.isArray(opsExceptionItems) ? opsExceptionItems : [])
        .filter((row) => opsExceptionSelectedIds.has(Number(row?.id || 0)));
    }

    function renderOpsExBulkEditRow(type, selectedCount) {
      const row = $("opsExBulkEditRow");
      if (!row) return;
      if (type === "MEDIA_MISSING") {
        row.innerHTML = `
          <label style="font-size:0.78rem;white-space:nowrap;">미디어 타입</label>
          <select id="opsExBulkMediaType" style="font-size:0.78rem;">
            <option value="">선택</option>
            <option value="Vinyl">Vinyl (LP)</option>
            <option value="CD">CD</option>
            <option value="Cassette">Cassette</option>
            <option value='7"'>7"</option>
            <option value='10"'>10"</option>
            <option value="DVD">DVD</option>
            <option value="Blu-ray">Blu-ray</option>
            <option value="8-Track Cartridge">8-Track</option>
            <option value="SACD">SACD</option>
            <option value="CDr">CDr</option>
            <option value="Reel-To-Reel">Reel-To-Reel</option>
          </select>
          <button id="opsExBulkApplyBtn" class="btn ghost tiny" type="button" disabled>
            선택 ${selectedCount}건 일괄 적용
          </button>
        `;
        $("opsExBulkMediaType")?.addEventListener("change", () => {
          if ($("opsExBulkApplyBtn")) $("opsExBulkApplyBtn").disabled = !$("opsExBulkMediaType").value;
        });
      } else if (type === "RELEASE_TYPE_MISSING") {
        row.innerHTML = `
          <label style="font-size:0.78rem;white-space:nowrap;">앨범 타입</label>
          <select id="opsExBulkReleaseType" style="font-size:0.78rem;">
            <option value="">선택</option>
            <option value="ALBUM">ALBUM</option>
            <option value="EP">EP</option>
            <option value="SINGLE">SINGLE</option>
          </select>
          <button id="opsExBulkApplyBtn" class="btn ghost tiny" type="button" disabled>
            선택 ${selectedCount}건 일괄 적용
          </button>
        `;
        $("opsExBulkReleaseType")?.addEventListener("change", () => {
          if ($("opsExBulkApplyBtn")) $("opsExBulkApplyBtn").disabled = !$("opsExBulkReleaseType").value;
        });
      } else if (type === "SIZE_MISMATCH") {
        const sizeGroupOptions = `
            <option value="">선택 안 함</option>
            <option value="LP">LP</option>
            <option value="STD">STD (CD)</option>
            <option value="LP7">LP 7"</option>
            <option value="LP10">LP 10"</option>
            <option value="CASSETTE">Cassette</option>
            <option value="8TRACK">8-Track</option>
            <option value="REEL_TO_REEL">Reel-to-Reel</option>
            <option value="BOOK">Book</option>
            <option value="OVERSIZE">Oversize</option>`;
        row.innerHTML = `
          <label style="font-size:0.78rem;white-space:nowrap;">규격 그룹</label>
          <select id="opsExBulkSizeGroup" style="font-size:0.78rem;">${sizeGroupOptions}</select>
          <label style="font-size:0.78rem;white-space:nowrap;">보관 규격</label>
          <select id="opsExBulkPrefSizeGroup" style="font-size:0.78rem;">${sizeGroupOptions}</select>
          <button id="opsExBulkApplyBtn" class="btn ghost tiny" type="button" disabled>
            선택 ${selectedCount}건 일괄 적용
          </button>
        `;
        const updateBulkSizeApplyBtn = () => {
          const hasVal = !!$("opsExBulkSizeGroup")?.value || !!$("opsExBulkPrefSizeGroup")?.value;
          if ($("opsExBulkApplyBtn")) $("opsExBulkApplyBtn").disabled = !hasVal;
        };
        $("opsExBulkSizeGroup")?.addEventListener("change", updateBulkSizeApplyBtn);
        $("opsExBulkPrefSizeGroup")?.addEventListener("change", updateBulkSizeApplyBtn);
      }
      $("opsExBulkApplyBtn")?.addEventListener("click", () => applyOpsExBulk(type));
    }

    async function applyOpsExBulk(type) {
      const btn = $("opsExBulkApplyBtn");
      const statusEl = $("opsExBulkEditStatus");
      const selectedIds = Array.from(opsExceptionSelectedIds);
      if (!selectedIds.length) return;

      if (btn) btn.disabled = true;
      if (statusEl) statusEl.textContent = `적용 중... (0/${selectedIds.length})`;

      try {
        let res;
        if (type === "MEDIA_MISSING") {
          const mediaType = $("opsExBulkMediaType")?.value;
          if (!mediaType) return;
          res = await fetchWithRetry("/owned-items/bulk-update-music-detail", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ owned_item_ids: selectedIds, media_type: mediaType }),
          });
        } else if (type === "SIZE_MISMATCH") {
          const sizeGroup = $("opsExBulkSizeGroup")?.value;
          const prefSizeGroup = $("opsExBulkPrefSizeGroup")?.value;
          if (!sizeGroup && !prefSizeGroup) return;
          const bulkBody = { owned_item_ids: selectedIds };
          if (sizeGroup) bulkBody.size_group = sizeGroup;
          if (prefSizeGroup) bulkBody.preferred_storage_size_group = prefSizeGroup;
          res = await fetchWithRetry("/owned-items/bulk-update", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(bulkBody),
          });
        } else if (type === "RELEASE_TYPE_MISSING") {
          const releaseType = $("opsExBulkReleaseType")?.value;
          if (!releaseType) return;
          let ok = 0, fail = 0;
          for (const masterId of selectedIds) {
            if (statusEl) statusEl.textContent = `적용 중... (${ok + fail + 1}/${selectedIds.length}) 성공: ${ok} 실패: ${fail}`;
            try {
              const r = await fetchWithRetry(`/album-masters/${masterId}/correction`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ release_type: releaseType }),
              });
              if (r.ok) { ok++; opsExceptionSelectedIds.delete(Number(masterId)); }
              else fail++;
            } catch (_) { fail++; }
          }
          if (statusEl) statusEl.textContent = `완료 — 성공: ${ok}건 / 실패: ${fail}건`;
          if (btn) btn.disabled = false;
          setTimeout(() => loadOpsExceptionItems({ silent: true }), 1000);
          return;
        } else {
          return;
        }

        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || "적용 실패");
        const okCount = Number(data.updated_count || 0);
        const failCount = selectedIds.length - okCount;
        if (statusEl) statusEl.textContent = `완료 — 성공: ${okCount}건 / 실패: ${failCount}건`;
        (data.updated_item_ids || []).forEach(id => opsExceptionSelectedIds.delete(Number(id)));
        setTimeout(() => loadOpsExceptionItems({ silent: true }), 1500);
      } catch (err) {
        if (statusEl) statusEl.textContent = `오류: ${escapeHtml(String(err.message || err))}`;
      } finally {
        if (btn) btn.disabled = false;
      }
    }

    function syncOpsExceptionSelectionControls() {
      const activeType = String($("opsExceptionType")?.value || "UNSLOTTED").trim().toUpperCase();
      const selectedRows = getSelectedOpsExceptionRows();
      const selectedCount = selectedRows.length;
      const summary = $("opsExceptionSelectionSummary");
      if (summary) {
        summary.textContent = t("ops.exception.selection.summary", {
          type: opsExceptionTypeLabel(activeType),
          total: countWithUnit(opsExceptionTotalCount),
          selected: countWithUnit(selectedCount),
        });
      }
      const allowSource = selectedCount > 0 && (activeType === "SOURCE_MISSING" || activeType === "TRACK_MISSING" || activeType === "COVER_MISSING");
      const allowAlign = selectedCount > 0 && activeType === "PREFERRED_SIZE_MISMATCH";
      const allowMaster = selectedCount > 0 && activeType === "MASTER_MISSING";
      const allowReview = selectedCount > 0 && activeType === "REVIEW_MISSING";
      if ($("opsExceptionBulkSourceBtn")) $("opsExceptionBulkSourceBtn").disabled = !allowSource;
      if ($("opsExceptionBulkAlignBtn")) $("opsExceptionBulkAlignBtn").disabled = !allowAlign;
      if ($("opsExceptionBulkMasterBtn")) $("opsExceptionBulkMasterBtn").disabled = !allowMaster;
      const reviewBtn = $("opsExceptionBulkReviewBtn");
      if (reviewBtn) { reviewBtn.style.display = activeType === "REVIEW_MISSING" ? "" : "none"; reviewBtn.disabled = !allowReview; }
      const isMasterType = (activeType === "SPOTIFY_UNMATCHED" || activeType === "GENRE_MISSING"
                            || activeType === "CATALOG_MISSING" || activeType === "REVIEW_MISSING"
                            || activeType === "LOCAL_MISSING" || activeType === "RELEASE_TYPE_MISSING");
      if ($("opsExceptionSelectAllBtn")) $("opsExceptionSelectAllBtn").disabled = !(Array.isArray(opsExceptionItems) && opsExceptionItems.length);
      if ($("opsExceptionClearBtn")) $("opsExceptionClearBtn").disabled = selectedCount <= 0;
      const BULK_EDIT_TYPES = new Set(["MEDIA_MISSING", "SIZE_MISMATCH", "RELEASE_TYPE_MISSING"]);
      const showBulkEdit = BULK_EDIT_TYPES.has(activeType) && selectedCount > 0;
      const bulkEditRow = $("opsExBulkEditRow");
      if (bulkEditRow) {
        bulkEditRow.style.display = showBulkEdit ? "flex" : "none";
        if (showBulkEdit) renderOpsExBulkEditRow(activeType, selectedCount);
      }
      if (!showBulkEdit && $("opsExBulkEditStatus")) $("opsExBulkEditStatus").textContent = "";
    }

    function _opsExCtxEditFormHtml(type, data) {
      if (type === "MEDIA_MISSING") {
        const cur = data.music_detail?.media_type || "";
        const opts = [
          "Vinyl","CD","Cassette",'7"','10"',"DVD","Blu-ray",
          "8-Track Cartridge","SACD","CDr","Reel-To-Reel",
        ].map(v => `<option value="${escapeHtml(v)}"${cur===v?" selected":""}>${escapeHtml(v)}</option>`).join("");
        return `
          <div style="display:flex;flex-direction:column;gap:6px;">
            <label style="font-size:0.72rem;color:var(--muted);">미디어 타입</label>
            <div style="display:flex;gap:6px;align-items:center;">
              <select id="opsExCtxMediaType" style="flex:1;font-size:0.78rem;">
                <option value="">선택</option>${opts}
              </select>
              <button id="opsExCtxSaveBtn" class="btn ghost tiny save" type="button">저장</button>
            </div>
            <div id="opsExCtxEditStatus" class="status mini"></div>
          </div>`;
      }
      if (type === "SIZE_MISMATCH") {
        const cur = data.size_group || "";
        const curPref = data.preferred_storage_size_group || "";
        const sizeOpts = [
          ["LP","LP"],["STD","STD (CD)"],["LP7",'LP 7"'],["LP10",'LP 10"'],
          ["CASSETTE","Cassette"],["8TRACK","8-Track"],["REEL_TO_REEL","Reel-to-Reel"],
          ["BOOK","Book"],["OVERSIZE","Oversize"],
        ].map(([v,l]) => `<option value="${v}"${cur===v?" selected":""}>${escapeHtml(l)}</option>`).join("");
        const prefOpts = [
          ["LP","LP"],["STD","STD (CD)"],["LP7",'LP 7"'],["LP10",'LP 10"'],
          ["CASSETTE","Cassette"],["8TRACK","8-Track"],["REEL_TO_REEL","Reel-to-Reel"],
          ["BOOK","Book"],["OVERSIZE","Oversize"],
        ].map(([v,l]) => `<option value="${v}"${curPref===v?" selected":""}>${escapeHtml(l)}</option>`).join("");
        return `
          <div style="display:flex;flex-direction:column;gap:6px;">
            <label style="font-size:0.72rem;color:var(--muted);">규격 그룹</label>
            <select id="opsExCtxSizeGroup" style="font-size:0.78rem;">
              <option value="">선택 안 함</option>${sizeOpts}
            </select>
            <label style="font-size:0.72rem;color:var(--muted);">보관 규격</label>
            <select id="opsExCtxPrefSizeGroup" style="font-size:0.78rem;">
              <option value="">선택 안 함</option>${prefOpts}
            </select>
            <div style="display:flex;gap:6px;align-items:center;">
              <button id="opsExCtxSaveBtn" class="btn ghost tiny save" type="button">저장</button>
            </div>
            <div id="opsExCtxEditStatus" class="status mini"></div>
          </div>`;
      }
      if (type === "CATALOG_MISSING") {
        const catalogNo = escapeHtml(data.music_detail?.catalog_no || "");
        const labelName = escapeHtml(data.music_detail?.label_name || "");
        return `
          <div style="display:flex;flex-direction:column;gap:6px;">
            <label style="font-size:0.72rem;color:var(--muted);">카탈로그 번호</label>
            <input id="opsExCtxCatalogNo" type="text" value="${catalogNo}" style="font-size:0.78rem;" />
            <label style="font-size:0.72rem;color:var(--muted);">레이블</label>
            <input id="opsExCtxLabelName" type="text" value="${labelName}" style="font-size:0.78rem;" />
            <div style="display:flex;gap:6px;">
              <button id="opsExCtxSaveBtn" class="btn ghost tiny save" type="button">저장</button>
            </div>
            <div id="opsExCtxEditStatus" class="status mini"></div>
          </div>`;
      }
      return "";
    }

    function _bindOpsExCtxEditForm(type, ownedItemId, data) {
      const saveBtn = $("opsExCtxSaveBtn");
      const statusEl = $("opsExCtxEditStatus");
      if (!saveBtn) return;

      saveBtn.addEventListener("click", async () => {
        saveBtn.disabled = true;
        if (statusEl) statusEl.textContent = "저장 중...";
        try {
          // PATCH는 OwnedItemCreate 전체 스키마를 필요로 하므로 기존 data와 병합
          const base = {
            category: data.category,
            size_group: data.size_group,
            preferred_storage_size_group: data.preferred_storage_size_group,
            status: data.status,
            is_second_hand: data.is_second_hand,
            quantity: data.quantity || 1,
            signature_type: data.signature_type,
            source_code: data.source_code,
            source_external_id: data.source_external_id,
            linked_album_master_id: data.linked_album_master_id,
            linked_artist_name: data.linked_artist_name,
            item_name_override: data.item_name_override,
            storage_slot_id: data.storage_slot_id,
            notes: data.notes,
            music_detail: data.music_detail || null,
          };
          let patch;
          if (type === "MEDIA_MISSING") {
            const v = $("opsExCtxMediaType")?.value;
            if (!v) throw new Error("미디어 타입을 선택하세요");
            patch = { music_detail: { ...(base.music_detail || {}), media_type: v } };
          } else if (type === "SIZE_MISMATCH") {
            const sg = $("opsExCtxSizeGroup")?.value;
            const psg = $("opsExCtxPrefSizeGroup")?.value;
            if (!sg && !psg) throw new Error("규격 그룹 또는 보관 규격을 선택하세요");
            patch = {};
            if (sg) patch.size_group = sg;
            if (psg) patch.preferred_storage_size_group = psg;
          } else if (type === "CATALOG_MISSING") {
            const catalogNo = String($("opsExCtxCatalogNo")?.value || "").trim();
            const labelName = String($("opsExCtxLabelName")?.value || "").trim();
            if (!catalogNo && !labelName) throw new Error("카탈로그 번호 또는 레이블을 입력하세요");
            patch = { music_detail: { ...(base.music_detail || {}), catalog_no: catalogNo || null, label_name: labelName || null } };
          } else {
            return;
          }
          const body = { ...base, ...patch };
          const res = await fetchWithRetry(`/owned-items/${ownedItemId}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          });
          const resp = await safeJson(res);
          if (!res.ok) throw new Error(resp.detail || "저장 실패");
          if (statusEl) statusEl.textContent = "저장됨";
          opsExceptionItems = opsExceptionItems.filter(r => Number(r.id) !== Number(ownedItemId));
          opsExceptionSelectedIds.delete(Number(ownedItemId));
          opsExceptionTotalCount = Math.max(0, opsExceptionTotalCount - 1);
          if (opsExceptionCounts && opsExceptionCounts[type] !== undefined) {
            opsExceptionCounts[type] = Math.max(0, opsExceptionCounts[type] - 1);
          }
          renderOpsExceptionSummary();
          renderOpsExceptionList();
          renderOpsExceptionContextPanel(null, "");
        } catch (err) {
          if (statusEl) statusEl.textContent = `오류: ${escapeHtml(String(err.message || err))}`;
        } finally {
          saveBtn.disabled = false;
        }
      });
    }

    async function renderOpsExceptionContextPanel(row, type) {
      const card = $("opsExContextCard");
      const body = $("opsExContextBody");
      const empty = $("opsExContextEmpty");
      if (!card || !body) return;
      if (!row) {
        card.style.display = "none";
        if (empty) empty.style.display = "";
        return;
      }
      card.style.display = "";
      if (empty) empty.style.display = "none";

      const isMasterType = (type === "SPOTIFY_UNMATCHED" || type === "REVIEW_MISSING" || type === "LOCAL_MISSING" || type === "RELEASE_TYPE_MISSING");

      if (isMasterType) {
        const masterId = Number(row.id || 0);
        const title = String(row.title || "-").trim();
        const artist = String(row.artist_or_brand || "-").trim();
        const year = row.release_year ? ` (${row.release_year})` : "";
        const cover = normalizeRenderableCoverUrl(row.cover_image_url);
        const coverHtml = cover
          ? `<img src="${escapeHtml(cover)}" style="width:64px;height:64px;object-fit:cover;border-radius:8px;border:1px solid var(--line);" />`
          : `<div style="width:64px;height:64px;border-radius:8px;border:1px solid var(--line);background:var(--paper);display:flex;align-items:center;justify-content:center;font-size:0.7rem;color:var(--muted);">${escapeHtml(artist.substring(0,2).toUpperCase()||"?")}</div>`;
        body.innerHTML = `
          <div style="display:flex;gap:10px;align-items:flex-start;margin-bottom:8px;">
            ${coverHtml}
            <div style="min-width:0;">
              <div style="font-weight:700;font-size:0.85rem;line-height:1.2;">${escapeHtml(artist)}</div>
              <div style="font-size:0.8rem;margin-top:2px;">${escapeHtml(title)}${escapeHtml(year)}</div>
              <div class="mini muted" style="margin-top:4px;">master #${masterId}</div>
            </div>
          </div>
          <div id="opsExCtxMasterItems" class="mini muted">보유 상품 조회 중...</div>
          <div id="opsExCtxMasterActions" style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;">
            <button class="btn ghost tiny" type="button"
              onclick="openMediaSearchDetailManage(${masterId},0)">관리 화면으로</button>
            <button class="btn ghost tiny search" type="button"
              data-ops-exception-review-auto="${masterId}">소스 자동수집</button>
          </div>
        `;
        try {
          const res = await fetchWithRetry(`/album-masters/${masterId}/members`);
          const data = await safeJson(res);
          const items = Array.isArray(data) ? data : [];
          const el = $("opsExCtxMasterItems");
          if (!el) return;
          if (!items.length) { el.textContent = "보유 상품 없음"; return; }
          const firstId = Number(items[0]?.id || 0);
          // 관리 화면으로 버튼에 첫 상품 ID 반영
          const actionsEl = $("opsExCtxMasterActions");
          if (actionsEl && firstId > 0) {
            const manageBtn = actionsEl.querySelector("button");
            if (manageBtn) manageBtn.setAttribute("onclick", `openMediaSearchDetailManage(${masterId},${firstId})`);
          }
          el.innerHTML = `<strong style="font-size:0.75rem;">보유 상품 ${items.length}건</strong><div style="margin-top:4px;display:flex;flex-direction:column;gap:2px;">${
            items.slice(0,5).map(it => {
              const name = resolveOwnedAlbumName(it);
              const loc = it.slot_code || t("common.unslotted");
              return `<div style="font-size:0.72rem;">${escapeHtml(name)} — ${escapeHtml(loc)}</div>`;
            }).join("")
          }${items.length > 5 ? `<div class="mini muted">외 ${items.length-5}건</div>` : ""}</div>`;
        } catch (_) {}
      } else {
        const ownedItemId = Number(row.id || 0);
        body.innerHTML = `<div class="mini muted">상품 #${ownedItemId} 상세 조회 중...</div>`;
        try {
          const res = await fetchWithRetry(`/owned-items/${ownedItemId}`);
          const data = await safeJson(res);
          if (!res.ok) throw new Error(data.detail || "조회 실패");
          const name = resolveOwnedAlbumName(data);
          const loc = data.slot_code || t("common.unslotted");
          const artist = data.music_detail?.artist_or_brand || data.linked_artist_name || "-";
          const label = data.music_detail?.label_name || "-";
          const catno = data.music_detail?.catalog_no || "-";
          const cover = normalizeRenderableCoverUrl(data.music_detail?.cover_image_url);
          const coverHtml = cover
            ? `<img src="${escapeHtml(cover)}" style="width:64px;height:64px;object-fit:cover;border-radius:8px;border:1px solid var(--line);" />`
            : "";
          body.innerHTML = `
            <div style="display:flex;gap:10px;align-items:flex-start;margin-bottom:8px;">
              ${coverHtml}
              <div style="min-width:0;">
                <div style="font-weight:700;font-size:0.85rem;">${escapeHtml(artist)}</div>
                <div style="font-size:0.8rem;margin-top:2px;">${escapeHtml(name)}</div>
                <div class="mini muted" style="margin-top:4px;">${escapeHtml(label)} / ${escapeHtml(catno)}</div>
                <div class="mini muted">위치: ${escapeHtml(loc)}</div>
              </div>
            </div>
            <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;">
              <button class="btn ghost tiny" type="button"
                onclick="openMediaSearchDetailManage(0,${ownedItemId})">관리 화면으로</button>
            </div>
          `;
          const editFormHtml = _opsExCtxEditFormHtml(type, data);
          if (editFormHtml) {
            body.innerHTML += `<div id="opsExCtxEditSection" style="margin-top:12px;border-top:1px solid var(--line);padding-top:10px;">${editFormHtml}</div>`;
            _bindOpsExCtxEditForm(type, ownedItemId, data);
          }
        } catch (err) {
          body.innerHTML = `<div class="mini muted" style="color:var(--err);">오류: ${escapeHtml(String(err.message||err))}</div>`;
        }
      }
    }

    function renderOpsExceptionList() {
      const root = $("opsExceptionList");
      if (!root) return;
      $("opsExceptionCount").textContent = countWithUnit(opsExceptionTotalCount);
      if (opsExceptionLoading) {
        root.innerHTML = `<div class='mini muted'>${escapeHtml(t("ops.exception.status.list_loading"))}</div>`;
        syncOpsExceptionSelectionControls();
        return;
      }
      if (!Array.isArray(opsExceptionItems) || !opsExceptionItems.length) {
        root.innerHTML = `<div class='mini muted'>${escapeHtml(t("ops.exception.status.list_empty"))}</div>`;
        syncOpsExceptionSelectionControls();
        return;
      }
      const activeType = String($("opsExceptionType")?.value || "UNSLOTTED").trim().toUpperCase();

      // --- Album Master rows (SPOTIFY_UNMATCHED / REVIEW_MISSING) ---
      // --- Owned Item rows with inline edit (GENRE_MISSING / CATALOG_MISSING) ---
      if (activeType === "SPOTIFY_UNMATCHED" || activeType === "GENRE_MISSING" || activeType === "CATALOG_MISSING" || activeType === "REVIEW_MISSING" || activeType === "LOCAL_MISSING" || activeType === "RELEASE_TYPE_MISSING") {
        root.innerHTML = opsExceptionItems.map((item, idx) => {
          const id = Number(item.id || 0);
          const rawTitle = String(item.title || item.master_title || item.item_name_override || "-").trim();
          const artist = String(item.artist_or_brand || item.master_artist_or_brand || "-").trim();
          const releaseYear = item.release_year || item.master_release_year || "";
          const displayTitle = artist !== "-" ? `${artist} - ${rawTitle}` : rawTitle;
          const displayTitleWithYear = releaseYear ? `${displayTitle} (${releaseYear})` : displayTitle;
          const coverUrl = normalizeRenderableCoverUrl(item.cover_image_url || item.thumbnail_url);
          const coverHtml = coverUrl
            ? `<img src="${escapeHtml(coverUrl)}" alt="${escapeHtml(rawTitle)}" />`
            : `<span class="ops-exception-cover-placeholder">${escapeHtml(artist.substring(0, 2).toUpperCase() || "?")}</span>`;

          if (activeType === "CATALOG_MISSING") {
            const labelName = item.label_name || "";
            const catalogNo = item.catalog_no || "";
            return `
              <div class="ops-exception-row" data-ops-ex-row-idx="${idx}">
                <div class="ops-exception-cover">${coverHtml}</div>
                <div class="ops-exception-main" style="flex:1;min-width:0;">
                  <div class="ops-exception-title">${escapeHtml(displayTitleWithYear)}</div>
                  <div class="ops-exception-meta">상품 #${id}</div>
                  <div class="ops-exception-edit-row">
                    <input type="text" class="ops-exception-inline-input" style="flex:1;min-width:100px;" placeholder="레이블" data-oi-id="${id}" data-field="label_name" value="${escapeHtml(labelName)}" />
                    <input type="text" class="ops-exception-inline-input" style="flex:1;min-width:120px;" placeholder="카탈로그 넘버" data-oi-id="${id}" data-field="catalog_no" value="${escapeHtml(catalogNo)}" />
                    <button class="btn ghost tiny save" data-ops-catalog-save="${id}" style="flex-shrink:0;">저장</button>
                    <span class="ops-catalog-save-status mini muted" data-save-status="${id}"></span>
                  </div>
                </div>
              </div>`;
          }

          if (activeType === "GENRE_MISSING") {
            const masterId = id;
            const genresJoined  = (Array.isArray(item.genres)  ? item.genres  : []).join(", ");
            const stylesJoined  = (Array.isArray(item.styles)  ? item.styles  : []).join(", ");
            return `
              <div class="ops-exception-row" data-ops-ex-row-idx="${idx}">
                <div class="ops-exception-cover">${coverHtml}</div>
                <div class="ops-exception-main" style="flex:1;min-width:0;">
                  <div class="ops-exception-title">${escapeHtml(displayTitleWithYear)}</div>
                  <div class="ops-exception-meta">master #${masterId}</div>
                  <div class="ops-exception-edit-row">
                    <input type="text" class="ops-exception-inline-input" style="flex:2;min-width:160px;"
                      placeholder="장르 (쉼표 구분, 예: Rock, Pop)"
                      data-master-id="${masterId}" data-field="genres"
                      value="${escapeHtml(genresJoined)}" />
                    <input type="text" class="ops-exception-inline-input" style="flex:2;min-width:160px;"
                      placeholder="스타일 (쉼표 구분, 예: Indie Rock, Shoegaze)"
                      data-master-id="${masterId}" data-field="styles"
                      value="${escapeHtml(stylesJoined)}" />
                    <button class="btn ghost tiny save" data-ops-genre-save="${masterId}" style="flex-shrink:0;">저장</button>
                    <span class="mini muted" data-save-status="${masterId}"></span>
                  </div>
                </div>
              </div>`;
          }

          if (activeType === "LOCAL_MISSING") {
            const masterId = id;
            const inputId = `opsLocalPath_${masterId}`;
            const dropId  = `opsLocalDrop_${masterId}`;
            return `
              <div class="ops-exception-row" data-ops-ex-row-idx="${idx}">
                <div class="ops-exception-cover">${coverHtml}</div>
                <div class="ops-exception-main" style="flex:1;min-width:0;">
                  <div class="ops-exception-title">${escapeHtml(displayTitleWithYear)}</div>
                  <div class="ops-exception-meta">master #${masterId}</div>
                  <div class="ops-exception-edit-row" style="flex-direction:column;align-items:stretch;">
                    <div style="display:flex;gap:4px;align-items:center;">
                      <input type="text" id="${escapeHtml(inputId)}"
                        class="ops-exception-inline-input" style="flex:1;"
                        placeholder="아티스트 또는 앨범명으로 검색…" autocomplete="off"
                        data-ops-local-master="${masterId}" />
                      <button class="btn ghost tiny save" data-ops-local-save="${masterId}" style="flex-shrink:0;">저장</button>
                      <span class="mini muted" data-save-status="${masterId}"></span>
                    </div>
                    <div id="${escapeHtml(dropId)}" style="display:none;border:1px solid var(--line);border-radius:6px;background:var(--paper);max-height:160px;overflow-y:auto;font-size:0.72rem;"></div>
                  </div>
                </div>
              </div>`;
          }

          if (activeType === "RELEASE_TYPE_MISSING") {
            const masterId = id;
            const checked = opsExceptionSelectedIds.has(masterId);
            return `
              <div class="ops-exception-row ops-exception-row--with-check ${checked ? "is-selected" : ""}" data-ops-ex-row-idx="${idx}">
                <label class="ops-exception-check"><input type="checkbox" data-ops-exception-release-type-check="${masterId}" ${checked ? "checked" : ""} /></label>
                <div class="ops-exception-cover">${coverHtml}</div>
                <div class="ops-exception-main" style="flex:1;min-width:0;">
                  <div class="ops-exception-title">${escapeHtml(displayTitleWithYear)}</div>
                  <div class="ops-exception-meta">master #${masterId}</div>
                  <div class="ops-exception-edit-row">
                    <select class="ops-exception-inline-input" data-master-id="${masterId}" data-field="release_type" style="flex:1;min-width:120px;">
                      <option value="">-- 선택 --</option>
                      <option value="ALBUM">ALBUM</option>
                      <option value="EP">EP</option>
                      <option value="SINGLE">SINGLE</option>
                    </select>
                    <button class="btn ghost tiny save" data-ops-release-type-save="${masterId}" style="flex-shrink:0;">저장</button>
                    <span class="mini muted" data-save-status="${masterId}"></span>
                  </div>
                </div>
              </div>`;
          }

          // SPOTIFY_UNMATCHED / REVIEW_MISSING — existing master logic
          const masterId2 = id;
          const metaBits = [`master #${masterId2}`, opsExceptionTypeHint(activeType)].filter(Boolean);
          const checked = opsExceptionSelectedIds.has(masterId2);
          const checkboxHtml = activeType === "REVIEW_MISSING"
            ? `<label class="ops-exception-check"><input type="checkbox" data-ops-exception-master-check="${masterId2}" ${checked ? "checked" : ""} /></label>`
            : "";
          const actionBtn = activeType === "REVIEW_MISSING"
            ? `<button class="btn ghost" type="button" data-ops-exception-review-auto="${masterId2}">${escapeHtml(t("media.manage.master.review.action.auto") || "Wikipedia 자동수집")}</button>`
            : `<button class="btn ghost" type="button" data-ops-exception-spotify-match="${masterId2}" data-spotify-match-title="${escapeHtml(rawTitle)}" data-spotify-match-artist="${escapeHtml(artist)}">${escapeHtml(t("ops.exception.action.spotify_match"))}</button>`;
          return `
            <div class="ops-exception-row${activeType === "REVIEW_MISSING" ? " ops-exception-row--with-check" : ""} ${checked ? "is-selected" : ""}" data-ops-ex-row-idx="${idx}">
              ${checkboxHtml}
              <div class="ops-exception-cover">${coverHtml}</div>
              <div class="ops-exception-main">
                <div class="ops-exception-title">${escapeHtml(displayTitleWithYear)}</div>
                <div class="ops-exception-meta">${escapeHtml(metaBits.join(" | "))}</div>
              </div>
              <div class="ops-exception-actions">${actionBtn}</div>
            </div>`;
        }).join("");

        // 페이징 컨트롤
        const pageSize = 50;
        const hasPrev = opsExceptionOffset > 0;
        const hasNext = (opsExceptionOffset + pageSize) < opsExceptionTotalCount;
        if (hasPrev || hasNext) {
          const pageInfo = `${opsExceptionOffset + 1}–${Math.min(opsExceptionOffset + opsExceptionItems.length, opsExceptionTotalCount)} / ${opsExceptionTotalCount}`;
          root.innerHTML += `
            <div style="display:flex;align-items:center;gap:8px;padding:8px 0;margin-top:4px;border-top:1px solid var(--line);">
              <button class="btn ghost tiny" id="opsExPrevBtn" ${hasPrev ? "" : "disabled"}>◀ 이전</button>
              <span class="mini muted" style="flex:1;text-align:center;">${escapeHtml(pageInfo)}</span>
              <button class="btn ghost tiny" id="opsExNextBtn" ${hasNext ? "" : "disabled"}>다음 ▶</button>
            </div>`;
          root.querySelector("#opsExPrevBtn")?.addEventListener("click", () => {
            opsExceptionOffset = Math.max(0, opsExceptionOffset - pageSize);
            loadOpsExceptionItems({ resetOffset: false });
          });
          root.querySelector("#opsExNextBtn")?.addEventListener("click", () => {
            opsExceptionOffset += pageSize;
            loadOpsExceptionItems({ resetOffset: false });
          });
        }

        // wire row click → context panel (SPOTIFY_UNMATCHED / REVIEW_MISSING)
        root.querySelectorAll(".ops-exception-row[data-ops-ex-row-idx]").forEach((rowEl) => {
          rowEl.style.cursor = "pointer";
          rowEl.addEventListener("click", (e) => {
            if (e.target.closest("input,button,a,label")) return;
            const idx = Number(rowEl.dataset.opsExRowIdx || -1);
            const it = Array.isArray(opsExceptionItems) ? opsExceptionItems[idx] : null;
            root.querySelectorAll(".ops-exception-row").forEach(r => r.classList.remove("is-ctx-selected"));
            rowEl.classList.add("is-ctx-selected");
            void renderOpsExceptionContextPanel(it, activeType);
          });
        });

        // wire REVIEW_MISSING checkboxes
        root.querySelectorAll("[data-ops-exception-master-check]").forEach((cb) => {
          cb.addEventListener("change", () => {
            const mid = Number(cb.getAttribute("data-ops-exception-master-check") || 0);
            if (cb.checked) opsExceptionSelectedIds.add(mid); else opsExceptionSelectedIds.delete(mid);
            renderOpsExceptionList();
          });
        });

        // wire CATALOG_MISSING save buttons
        root.querySelectorAll("[data-ops-catalog-save]").forEach((btn) => {
          btn.addEventListener("click", async (e) => {
            e.stopPropagation();
            const oiId = btn.dataset.opsCatalogSave;
            const rowEl = btn.closest(".ops-exception-row");
            const labelInput = rowEl.querySelector("[data-field='label_name']");
            const catalogInput = rowEl.querySelector("[data-field='catalog_no']");
            const statusEl = rowEl.querySelector(`[data-save-status='${oiId}']`);
            btn.disabled = true;
            if (statusEl) statusEl.textContent = "저장 중...";
            try {
              const res = await fetchWithRetry(`/owned-items/${oiId}/catalog`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ catalog_no: catalogInput?.value || null, label_name: labelInput?.value || null }),
              });
              if (!res.ok) throw new Error((await safeJson(res)).detail || "저장 실패");
              if (statusEl) statusEl.textContent = "저장됨";
              setTimeout(() => rowEl.remove(), 600);
            } catch (err) {
              if (statusEl) statusEl.textContent = `오류: ${escapeHtml(String(err.message || err))}`;
              btn.disabled = false;
            }
          });
        });

        // wire GENRE_MISSING save buttons
        root.querySelectorAll("[data-ops-genre-save]").forEach((btn) => {
          btn.addEventListener("click", async (e) => {
            e.stopPropagation();
            const masterId = btn.dataset.opsGenreSave;
            const rowEl = btn.closest(".ops-exception-row");
            const genreInput  = rowEl.querySelector("[data-field='genres']");
            const styleInput  = rowEl.querySelector("[data-field='styles']");
            const statusEl    = rowEl.querySelector(`[data-save-status='${masterId}']`);
            const genres = (genreInput?.value || "").split(",").map(s => s.trim()).filter(Boolean);
            const styles = (styleInput?.value  || "").split(",").map(s => s.trim()).filter(Boolean);
            if (!genres.length) { if (statusEl) statusEl.textContent = "장르를 입력하세요"; return; }
            btn.disabled = true;
            if (statusEl) statusEl.textContent = "저장 중...";
            try {
              const res = await fetchWithRetry(`/album-masters/${masterId}/correction`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ genres, styles }),
              });
              if (!res.ok) throw new Error((await safeJson(res)).detail || "저장 실패");
              if (statusEl) statusEl.textContent = "저장됨";
              setTimeout(() => rowEl.remove(), 600);
            } catch (err) {
              if (statusEl) statusEl.textContent = `오류: ${escapeHtml(String(err.message || err))}`;
              btn.disabled = false;
            }
          });
        });

        // wire RELEASE_TYPE_MISSING inline save
        root.querySelectorAll("[data-ops-release-type-save]").forEach((btn) => {
          btn.addEventListener("click", async (e) => {
            e.stopPropagation();
            const masterId = btn.dataset.opsReleaseTypeSave;
            const rowEl = btn.closest(".ops-exception-row");
            const sel = rowEl.querySelector("[data-field='release_type']");
            const statusEl = rowEl.querySelector(`[data-save-status='${masterId}']`);
            const releaseType = sel?.value || "";
            if (!releaseType) { if (statusEl) statusEl.textContent = "타입을 선택하세요"; return; }
            btn.disabled = true;
            if (statusEl) statusEl.textContent = "저장 중...";
            try {
              const res = await fetchWithRetry(`/album-masters/${masterId}/correction`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ release_type: releaseType }),
              });
              if (!res.ok) throw new Error((await safeJson(res)).detail || "저장 실패");
              if (statusEl) statusEl.textContent = "저장됨";
              setTimeout(() => rowEl.remove(), 600);
            } catch (err) {
              if (statusEl) statusEl.textContent = `오류: ${escapeHtml(String(err.message || err))}`;
              btn.disabled = false;
            }
          });
        });

        // wire RELEASE_TYPE_MISSING checkboxes
        root.querySelectorAll("[data-ops-exception-release-type-check]").forEach((cb) => {
          cb.addEventListener("change", () => {
            const mid = Number(cb.getAttribute("data-ops-exception-release-type-check") || 0);
            if (cb.checked) opsExceptionSelectedIds.add(mid); else opsExceptionSelectedIds.delete(mid);
            renderOpsExceptionList();
          });
        });

        // wire LOCAL_MISSING search + save
        root.querySelectorAll("[data-ops-local-master]").forEach((input) => {
          const masterId = input.dataset.opsLocalMaster;
          const dropEl = document.getElementById(`opsLocalDrop_${masterId}`);
          let _timer = null;
          let _composing = false;
          input.addEventListener("compositionstart", () => { _composing = true; });
          input.addEventListener("compositionend", () => {
            _composing = false;
            input.dispatchEvent(new Event("input"));
          });
          input.addEventListener("input", () => {
            if (_composing) return;
            clearTimeout(_timer);
            const q = input.value.trim();
            if (q.length < 2) { if (dropEl) dropEl.style.display = "none"; return; }
            _timer = setTimeout(async () => {
              try {
                const res = await fetchWithRetry(`/local-music/search-dirs?q=${encodeURIComponent(q)}&limit=15`);
                if (!res.ok) return;
                const data = await safeJson(res);
                const dirs = data.dirs || [];
                if (!dropEl) return;
                if (!dirs.length) { dropEl.style.display = "none"; return; }
                dropEl.innerHTML = dirs.map(d => `
                  <div class="local-dir-result-row" data-dir-path="${escapeHtml(d.dir_path)}" style="padding:5px 10px;cursor:pointer;border-bottom:1px solid var(--line);">
                    <div style="font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(d.dir_name)}</div>
                    <div style="color:var(--muted);font-size:0.65rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(d.dir_path.replace(/^\/Volumes\/Music\//, "…/"))}</div>
                  </div>`).join("");
                dropEl.style.display = "block";
                dropEl.querySelectorAll(".local-dir-result-row").forEach(row => {
                  row.addEventListener("mousedown", (e) => {
                    e.preventDefault();
                    input.value = row.dataset.dirPath;
                    dropEl.style.display = "none";
                  });
                });
              } catch (_) {}
            }, 250);
          });
          input.addEventListener("blur", () => setTimeout(() => { if (dropEl) dropEl.style.display = "none"; }, 150));
          input.addEventListener("keydown", (e) => { if (e.key === "Escape" && dropEl) dropEl.style.display = "none"; });
        });

        root.querySelectorAll("[data-ops-local-save]").forEach((btn) => {
          btn.addEventListener("click", async (e) => {
            e.stopPropagation();
            const masterId = btn.dataset.opsLocalSave;
            const rowEl = btn.closest(".ops-exception-row");
            const input = rowEl.querySelector(`[data-ops-local-master="${masterId}"]`);
            const statusEl = rowEl.querySelector(`[data-save-status="${masterId}"]`);
            const path = (input?.value || "").trim();
            if (!path) { if (statusEl) statusEl.textContent = "경로를 선택하세요"; return; }
            btn.disabled = true;
            if (statusEl) statusEl.textContent = "저장 중...";
            try {
              const res = await fetchWithRetry(`/album-masters/${masterId}/local-link`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ dir_path: path }),
              });
              if (!res.ok) throw new Error((await safeJson(res)).detail || "저장 실패");
              if (statusEl) statusEl.textContent = "저장됨";
              _localLinkedIds.add(Number(masterId));
              setTimeout(() => rowEl.remove(), 600);
            } catch (err) {
              if (statusEl) statusEl.textContent = `오류: ${escapeHtml(String(err.message || err))}`;
              btn.disabled = false;
            }
          });
        });

        syncOpsExceptionSelectionControls();
        return;
      }

      // --- Standard OwnedItem rows ---
      root.innerHTML = opsExceptionItems.map((row, idx) => {
        const ownedItemId = Number(row.id || 0);
        const checked = opsExceptionSelectedIds.has(ownedItemId);
        const title = resolveOwnedAlbumName(row);
        const coverUrl = normalizeRenderableCoverUrl(row.cover_image_url);
        const coverHtml = coverUrl
          ? `<img src="${escapeHtml(coverUrl)}" alt="${escapeHtml(title)}" />`
          : escapeHtml(mediaDisplayLabel(row.format_name || row.category || "-"));
        const barcodeText = String(row.barcode || "").trim();
        const locationText = row.slot_code || t("common.unslotted");
        const releaseText = String(row.released_date || row.release_year || "-").trim() || "-";
        const sourceText = row.source_code
          ? `${dashboardSourceLabel(row.source_code)}#${row.source_external_id || "-"}`
          : t("common.source.manual");
        const labelCatText = `${row.label_name || "-"} / ${row.catalog_no || "-"}${barcodeText ? ` (${barcodeText})` : ""}`;
        const sizeMismatchText = activeType === "PREFERRED_SIZE_MISMATCH"
          ? (function() {
              const fmtRaw = String(row.format_items_json || "").toUpperCase();
              const media = String(row.media_type || "").trim();
              const sg = String(row.size_group || "LP").trim().toUpperCase();
              const CD_LIKE = ["CD","CDr","SACD","Digital","DVD","Blu-ray","CD-ROM"];
              const VINYL_LIKE = ["Vinyl","LP",'7"','10"',"All Media"];
              const isLpStyle = fmtRaw.includes("LP-STYLE PACKAGING") || fmtRaw.includes("LP STYLE PACKAGING");
              const isBoxSet = fmtRaw.includes("BOX SET");
              const slotSg = String(row.slot_allowed_size_group || "").trim().toUpperCase() || "-";
              const slotLabel = slotSg !== "-" ? dashboardSizeGroupLabel(slotSg) : "-";
              if (isLpStyle) {
                return `슬롯 ${slotLabel} → LP-Style Packaging (LP 또는 OVERSIZE 허용)`;
              }
              if (isBoxSet) {
                // Box Set: 기본 규격 또는 OVERSIZE 모두 허용
                const base = CD_LIKE.includes(media) ? "STD" : media === "Cassette" ? "CASSETTE" : sg || "LP";
                const baseLabel = dashboardSizeGroupLabel(base);
                return `슬롯 ${slotLabel} → Box Set (${baseLabel} 또는 OVERSIZE 허용)`;
              }
              let required = null, reason = "";
              if (media === "Reel-To-Reel") { required = "REEL_TO_REEL"; }
              else if (media === "8-Track Cartridge") { required = "8TRACK"; }
              else if (media === "Cassette") { required = "CASSETTE"; }
              else if (CD_LIKE.includes(media)) {
                if (fmtRaw.includes("DIGIBOOK")) { required = "OVERSIZE"; reason = "Digibook"; }
                else if (fmtRaw.includes("DVD SIZE")) { required = "OVERSIZE"; reason = "DVD Size"; }
                else { required = "STD"; }
              } else if (VINYL_LIKE.includes(media)) { required = sg || "LP"; }
              const reqLabel = required ? dashboardSizeGroupLabel(required) : "-";
              const reasonSuffix = reason ? ` (${reason})` : "";
              return `슬롯 ${slotLabel} → 필요 ${reqLabel}${reasonSuffix}`;
            })()
          : "";
        const trackMissingText = activeType === "TRACK_MISSING"
          ? t("common.meta.track_count", { value: formatCount((Array.isArray(row.track_list) ? row.track_list.length : 0) || (Array.isArray(row.track_items) ? row.track_items.length : 0)) })
          : "";
        const metaBits = [
          row.label_id || `owned_item_id ${ownedItemId}`,
          row.artist_or_brand || row.linked_artist_name || "-",
          sourceText,
        ].filter(Boolean);
        const subBits = [
          t("common.meta.release_date", { value: releaseText }),
          t("common.meta.label_catalog", { value: labelCatText }),
          t("common.meta.location", { value: locationText }),
          sizeMismatchText,
          trackMissingText,
          opsExceptionTypeHint(activeType),
        ].filter(Boolean);
        return `
          <div class="ops-exception-row" data-ops-ex-row-idx="${idx}">
            <div class="ops-exception-cover">${coverHtml}</div>
            <div class="ops-exception-main">
              <div class="ops-exception-title">${escapeHtml(title)}</div>
              <div class="ops-exception-meta">${escapeHtml(metaBits.join(" | "))}</div>
              <div class="ops-exception-submeta">${escapeHtml(subBits.join(" | "))}</div>
            </div>
            <div class="ops-exception-actions">
              <label class="inline-check inline-check--compact">
                <input type="checkbox" data-ops-exception-select="${ownedItemId}" ${checked ? "checked" : ""} />
                <span>${escapeHtml(t("media.source.action.select"))}</span>
              </label>
              ${activeType === "SOURCE_MISSING" || activeType === "TRACK_MISSING" || activeType === "COVER_MISSING" ? `<button class="btn ghost" type="button" data-ops-exception-source="${ownedItemId}">${escapeHtml(t("ops.exception.action.source"))}</button>` : ""}
              ${activeType === "MASTER_MISSING" ? `<button class="btn ghost" type="button" data-ops-exception-master="${ownedItemId}">${escapeHtml(t("ops.exception.action.master"))}</button>` : ""}
              ${activeType === "PREFERRED_SIZE_MISMATCH" ? `<button class="btn ghost" type="button" data-ops-exception-align-size="${ownedItemId}">${escapeHtml(t("ops.exception.action.align_size"))}</button>` : ""}
              <button class="btn ghost" type="button" data-ops-exception-open="${ownedItemId}">${escapeHtml(t("ops.exception.action.edit"))}</button>
            </div>
          </div>
        `;
      }).join("");
      // wire row click → context panel
      root.querySelectorAll(".ops-exception-row[data-ops-ex-row-idx]").forEach((rowEl) => {
        rowEl.style.cursor = "pointer";
        rowEl.addEventListener("click", (e) => {
          if (e.target.closest("input,button,a,label")) return;
          const idx = Number(rowEl.dataset.opsExRowIdx || -1);
          const item = Array.isArray(opsExceptionItems) ? opsExceptionItems[idx] : null;
          root.querySelectorAll(".ops-exception-row").forEach(r => r.classList.remove("is-ctx-selected"));
          rowEl.classList.add("is-ctx-selected");
          void renderOpsExceptionContextPanel(item, activeType);
        });
      });
      syncOpsExceptionSelectionControls();
    }

    async function fetchOpsExceptionCount(type) {
      if (type === "SPOTIFY_UNMATCHED" || type === "GENRE_MISSING" || type === "CATALOG_MISSING" || type === "REVIEW_MISSING" || type === "LOCAL_MISSING" || type === "RELEASE_TYPE_MISSING") {
        const res = await fetchWithRetry(buildMasterExceptionCountUrl(type));
        if (!res.ok) throw new Error(t("ops.exception.status.count_failed", { type: opsExceptionTypeLabel(type) }));
        const headerTotal = Number(res.headers.get("X-Total-Count") || 0);
        return Number.isFinite(headerTotal) ? headerTotal : 0;
      }
      const params = buildOpsExceptionParams(type, { includeTotal: true, limit: 1 });
      const res = await fetchWithRetry(`/owned-items?${params.toString()}`);
      const data = await safeJson(res);
      if (!res.ok) throw new Error(data.detail || t("ops.exception.status.count_failed", { type: opsExceptionTypeLabel(type) }));
      const headerTotal = Number(res.headers.get("X-Total-Count") || 0);
      return Number.isFinite(headerTotal) ? headerTotal : 0;
    }

    async function loadOpsExceptionCounts(opts = {}) {
      const silent = Boolean(opts?.silent);
      const types = ["UNSLOTTED", "SOURCE_MISSING", "MASTER_MISSING", "COVER_MISSING", "PREFERRED_SIZE_MISMATCH", "MEDIA_MISSING", "SIZE_MISMATCH", "TRACK_MISSING", "SPOTIFY_UNMATCHED", "REVIEW_MISSING", "GENRE_MISSING", "CATALOG_MISSING", "LOCAL_MISSING", "RELEASE_TYPE_MISSING"];
      try {
        if (!silent) setStatus("opsExceptionStatus", "ok", t("ops.exception.status.count_loading"));
        const results = await Promise.all(types.map(async (type) => ({
          type,
          count: await fetchOpsExceptionCount(type),
        })));
        opsExceptionCounts = results.reduce((acc, entry) => {
          acc[entry.type] = Number(entry.count || 0);
          return acc;
        }, { UNSLOTTED: 0, SOURCE_MISSING: 0, MASTER_MISSING: 0, COVER_MISSING: 0, PREFERRED_SIZE_MISMATCH: 0, MEDIA_MISSING: 0, SIZE_MISMATCH: 0, TRACK_MISSING: 0, SPOTIFY_UNMATCHED: 0, REVIEW_MISSING: 0, GENRE_MISSING: 0, CATALOG_MISSING: 0, LOCAL_MISSING: 0, RELEASE_TYPE_MISSING: 0 });
        renderOpsExceptionSummary();
        if (!silent) setStatus("opsExceptionStatus", "ok", t("ops.exception.status.count_loaded"));
      } catch (err) {
        renderOpsExceptionSummary();
        if (!silent) setStatus("opsExceptionStatus", "err", err.message);
      }
    }

    async function loadOpsExceptionItems(opts = {}) {
      const silent = Boolean(opts?.silent);
      const resetOffset = Boolean(opts?.resetOffset !== false && !opts?.silent);
      const type = String($("opsExceptionType")?.value || "UNSLOTTED").trim().toUpperCase();
      const limit = 50;
      if (resetOffset) opsExceptionOffset = 0;
      try {
        opsExceptionLoading = true;
        renderOpsExceptionSummary();
        renderOpsExceptionList();
        if (!silent) setStatus("opsExceptionStatus", "ok", t("ops.exception.status.list_loading_type", { type: opsExceptionTypeLabel(type) }));
        let res, data;
        if (type === "SPOTIFY_UNMATCHED" || type === "GENRE_MISSING" || type === "CATALOG_MISSING" || type === "REVIEW_MISSING" || type === "LOCAL_MISSING" || type === "RELEASE_TYPE_MISSING") {
          res = await fetchWithRetry(buildMasterExceptionUrl(type, limit, opsExceptionOffset));
          data = await safeJson(res);
        } else {
          const params = buildOpsExceptionParams(type, { includeTotal: true, limit });
          res = await fetchWithRetry(`/owned-items?${params.toString()}`);
          data = await safeJson(res);
        }
        if (!res.ok) throw new Error(data.detail || t("ops.exception.status.list_failed", { type: opsExceptionTypeLabel(type) }));
        opsExceptionItems = Array.isArray(data) ? data : [];
        opsExceptionSelectedIds = new Set(
          opsExceptionItems
            .map((row) => Number(row?.id || 0))
            .filter((id) => id > 0 && opsExceptionSelectedIds.has(id))
        );
        const headerTotal = Number(res.headers.get("X-Total-Count") || opsExceptionItems.length || 0);
        opsExceptionTotalCount = Number.isFinite(headerTotal) ? headerTotal : opsExceptionItems.length;
        // 카운트 카드를 실제 로드된 총수로 동기화
        if (opsExceptionCounts[type] !== undefined) opsExceptionCounts[type] = opsExceptionTotalCount;
        renderOpsExceptionSummary();
        renderOpsExceptionList();
        if (!silent) setStatus("opsExceptionStatus", "ok", t("ops.exception.status.list_loaded", { type: opsExceptionTypeLabel(type), count: countWithUnit(opsExceptionTotalCount) }));
      } catch (err) {
        opsExceptionItems = [];
        opsExceptionTotalCount = 0;
        renderOpsExceptionSummary();
        renderOpsExceptionList();
        if (!silent) setStatus("opsExceptionStatus", "err", err.message);
      } finally {
        opsExceptionLoading = false;
        renderOpsExceptionList();
      }
    }

    async function loadOpsAuthAccounts() {
      try {
        setStatus("opsAuthStatus", "ok", t("ops.account.status.loading"));
        const res = await fetch("/ops-auth-accounts");
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("ops.account.status.load_failed"));
        opsAuthItems = Array.isArray(data.items) ? data.items : [];
        if (opsAuthSelectedUsername && !opsAuthItems.some((row) => String(row.username || "").trim() === opsAuthSelectedUsername)) {
          resetOpsAuthForm();
        }
        renderOpsAuthTable();
        setStatus("opsAuthStatus", "ok", t("ops.account.status.loaded", { count: countWithUnit(opsAuthItems.length) }));
      } catch (err) {
        opsAuthItems = [];
        renderOpsAuthTable();
        setStatus("opsAuthStatus", "err", errorMessageText(err, t("ops.account.status.load_failed")));
      }
    }

    async function saveOpsAuthAccount() {
      const username = $("opsAuthUsername").value.trim();
      const password = $("opsAuthPassword").value;
      const role = $("opsAuthRole").value;
      const isActive = $("opsAuthIsActive").checked;
      const displayName = $("opsAuthDisplayName").value.trim() || null;
      const description = $("opsAuthDescription").value.trim() || null;
      if (!username) {
        setStatus("opsAuthStatus", "err", t("ops.account.status.username_required"));
        return;
      }
      const selectedRow = (Array.isArray(opsAuthItems) ? opsAuthItems : []).find((row) => String(row.username || "").trim() === username) || null;
      const isExisting = Boolean(selectedRow);
      const isManagedExisting = Boolean(selectedRow && selectedRow.source === "MANAGED");
      if (selectedRow && selectedRow.editable === false) {
        setStatus("opsAuthStatus", "err", t("ops.account.status.built_in_locked"));
        return;
      }
      if (!isExisting && !password.trim()) {
        setStatus("opsAuthStatus", "err", t("ops.account.status.password_required_new"));
        return;
      }
      try {
        setStatus("opsAuthStatus", "ok", isExisting ? t("ops.account.status.saving_update") : t("ops.account.status.saving_create"));
        const method = isExisting ? "PATCH" : "POST";
        const url = isExisting ? `/ops-auth-accounts/${encodeURIComponent(username)}` : "/ops-auth-accounts";
        const payload = isExisting
          ? {
              role,
              is_active: isActive,
              display_name: displayName,
              description: description,
              ...(password.trim() ? { password } : {}),
            }
          : {
              username,
              password,
              role,
              display_name: displayName,
              description: description,
            };
        const res = await fetch(url, {
          method,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("ops.account.status.save_failed"));
        if (isManagedExisting && selectedRow && selectedRow.is_active !== isActive) {
          data.is_active = isActive;
        }
        opsAuthSelectedUsername = String(data.username || username).trim();
        $("opsAuthPassword").value = "";
        await loadOpsAuthAccounts();
        setStatus("opsAuthStatus", "ok", isExisting ? t("ops.account.status.saved_update") : t("ops.account.status.saved_create"));
      } catch (err) {
        setStatus("opsAuthStatus", "err", errorMessageText(err, t("ops.account.status.save_failed")));
      }
    }

    async function deleteOpsAuthAccount() {
      const username = $("opsAuthUsername").value.trim();
      if (!username) {
        setStatus("opsAuthStatus", "err", t("ops.account.status.delete_required"));
        return;
      }
      const selectedRow = (Array.isArray(opsAuthItems) ? opsAuthItems : []).find((row) => String(row.username || "").trim() === username) || null;
      if (!selectedRow || selectedRow.source !== "MANAGED") {
        setStatus("opsAuthStatus", "err", t("ops.account.status.delete_managed_only"));
        return;
      }
      if (!confirm(t("ops.account.status.delete_confirm", { username }))) {
        setStatus("opsAuthStatus", "ok", t("ops.account.status.delete_cancelled"));
        return;
      }
      try {
        setStatus("opsAuthStatus", "ok", t("ops.account.status.deleting"));
        const res = await fetch(`/ops-auth-accounts/${encodeURIComponent(username)}`, { method: "DELETE" });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("ops.account.status.delete_failed"));
        resetOpsAuthForm();
        await loadOpsAuthAccounts();
        setStatus("opsAuthStatus", "ok", t("ops.account.status.deleted"));
      } catch (err) {
        setStatus("opsAuthStatus", "err", errorMessageText(err, t("ops.account.status.delete_failed")));
      }
    }

    // ── Permission management ──────────────────────────────────────────────

    async function loadPermissionData() {
      try {
        setStatus("permRoleStatus", "ok", "로딩 중...");
        const res = await fetch("/admin/permissions");
        if (!res.ok) throw new Error("권한 데이터 로드 실패");
        _permData = await safeJson(res);
        renderRoleMatrix();
        populatePermAccountSelect();
        setStatus("permRoleStatus", "ok", "");
      } catch (err) {
        setStatus("permRoleStatus", "err", errorMessageText(err, "권한 데이터 로드 실패"));
      }
    }

    async function saveRolePermissions() {
      if (!_permData) return;
      const roles = ["OPERATOR", "CAFE_STAFF"];
      setStatus("permRoleStatus", "ok", "저장 중...");
      try {
        for (const role of roles) {
          const keys = [...document.querySelectorAll(`#permRoleMatrix input[data-perm-role="${role}"]:checked`)]
            .map(el => el.dataset.permKey);
          const res = await fetch(`/admin/permissions/role/${role}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ permission_keys: keys }),
          });
          if (!res.ok) { const d = await safeJson(res); throw new Error(d.detail || "저장 실패"); }
        }
        await loadPermissionData();
        setStatus("permRoleStatus", "ok", "저장 완료");
      } catch (err) {
        setStatus("permRoleStatus", "err", errorMessageText(err, "역할 권한 저장 실패"));
      }
    }

    async function loadAccountPermissions(usernameOverride) {
      const username = usernameOverride || $("permAccountSelect").value;
      if (!username) { setStatus("permAccountStatus", "err", "계정을 선택하세요"); return; }
      setStatus("permAccountStatus", "ok", "로딩 중...");
      try {
        const [effRes, ovrRes] = await Promise.all([
          fetch(`/admin/permissions/account/${encodeURIComponent(username)}/effective`),
          fetch(`/admin/permissions/account/${encodeURIComponent(username)}`),
        ]);
        if (!effRes.ok || !ovrRes.ok) throw new Error("계정 권한 로드 실패");
        const eff = await safeJson(effRes);
        const ovr = await safeJson(ovrRes);
        _permAccountEffective = { username, effective: eff.effective || {}, role: eff.role, overrides: ovr.overrides || [] };
        renderAccountMatrix();
        setStatus("permAccountStatus", "ok", `${username} 권한 로드 완료`);
      } catch (err) {
        setStatus("permAccountStatus", "err", errorMessageText(err, "계정 권한 로드 실패"));
      }
    }

    async function grantPermOverride(username, key) {
      setStatus("permAccountStatus", "ok", "저장 중...");
      try {
        const res = await fetch(`/admin/permissions/account/${encodeURIComponent(username)}/grant/${encodeURIComponent(key)}`, { method: "PUT" });
        if (!res.ok) { const d = await safeJson(res); throw new Error(d.detail || "저장 실패"); }
        await loadAccountPermissions(username);
      } catch (err) {
        setStatus("permAccountStatus", "err", errorMessageText(err, "권한 부여 실패"));
      }
    }

    async function deletePermOverride(username, key) {
      setStatus("permAccountStatus", "ok", "처리 중...");
      try {
        const res = await fetch(`/admin/permissions/account/${encodeURIComponent(username)}/${encodeURIComponent(key)}`, { method: "DELETE" });
        if (!res.ok) { const d = await safeJson(res); throw new Error(d.detail || "삭제 실패"); }
        await loadAccountPermissions(username);
      } catch (err) {
        setStatus("permAccountStatus", "err", errorMessageText(err, "오버라이드 제거 실패"));
      }
    }

    async function clearAllPermOverrides() {
      const username = $("permAccountSelect").value || opsAuthSelectedUsername;
      if (!username) return;
      setStatus("permAccountStatus", "ok", "처리 중...");
      try {
        const res = await fetch(`/admin/permissions/account/${encodeURIComponent(username)}`, { method: "DELETE" });
        const d = await safeJson(res);
        if (!res.ok) throw new Error(d.detail || "초기화 실패");
        await loadAccountPermissions();
        setStatus("permAccountStatus", "ok", `${username} 오버라이드 전체 초기화 완료 (${d.deleted_count || 0}건)`);
      } catch (err) {
        setStatus("permAccountStatus", "err", errorMessageText(err, "초기화 실패"));
      }
    }

    $("permSaveRoleBtn").addEventListener("click", saveRolePermissions);
    $("permLoadAccountBtn").addEventListener("click", loadAccountPermissions);
    $("permClearAccountBtn").addEventListener("click", clearAllPermOverrides);
    // ── End permission management ──────────────────────────────────────────

    async function openSourceWorkbenchFromException(ownedItemId) {
      const targetId = Number(ownedItemId || 0);
      const row = (Array.isArray(opsExceptionItems) ? opsExceptionItems : [])
        .find((item) => Number(item?.id || 0) === targetId);
      if (!row) {
        setStatus("opsExceptionStatus", "err", t("ops.exception.status.item_missing"));
        return;
      }
      loadSourceWorkbenchRowsFromItems([row], t("ops.exception.status.source_loaded", { name: resolveOwnedAlbumName(row) }));
    }

    function bulkSendExceptionsToMasterWorkbench() {
      const rows = getSelectedOpsExceptionRows();
      if (!rows.length) {
        setStatus("opsExceptionStatus", "err", t("ops.exception.status.bulk_master_required"));
        return;
      }
      const sentCount = rows.length;
      loadMasterOwnedRowsFromItems(rows, t("ops.exception.status.bulk_master_loaded", { count: countWithUnit(sentCount) }));
      setStatus("opsExceptionStatus", "ok", `${countWithUnit(sentCount)}이 마스터 정리 대상으로 이동됐습니다`);
    }

    async function alignPreferredStorageFromException(ownedItemId) {
      const targetId = Number(ownedItemId || 0);
      const row = (Array.isArray(opsExceptionItems) ? opsExceptionItems : [])
        .find((item) => Number(item?.id || 0) === targetId);
      if (!row) {
        setStatus("opsExceptionStatus", "err", t("ops.exception.status.item_missing"));
        return;
      }
      const nextPreferred = String(row?.size_group || "").trim().toUpperCase();
      if (!nextPreferred) {
        setStatus("opsExceptionStatus", "err", t("ops.exception.status.align_missing_size"));
        return;
      }
      try {
        setStatus("opsExceptionStatus", "ok", t("ops.exception.status.align_saving"));
        const res = await fetch("/owned-items/bulk-update", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            owned_item_ids: [targetId],
            preferred_storage_size_group: nextPreferred,
          }),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("ops.exception.status.align_update_failed"));
        setStatus("opsExceptionStatus", "ok", t("ops.exception.status.align_saved", { size: dashboardSizeGroupLabel(nextPreferred) }));
        refreshOpsExceptionInBackground();
        refreshHomeSearchInBackground();
        refreshHomeDashboardInBackground();
        if (Number(homeSelectedItemId || 0) === targetId) {
          refreshHomeManageContext(targetId, {
            keepMasterContext: Boolean(homeSelectedMasterId),
            masterId: homeSelectedMasterId,
            reloadMaster: Boolean(homeSelectedMasterId),
          }).catch(() => {});
        }
      } catch (err) {
        setStatus("opsExceptionStatus", "err", err.message);
      }
    }

    async function bulkAlignPreferredStorageFromExceptions() {
      const rows = getSelectedOpsExceptionRows();
      if (!rows.length) {
        setStatus("opsExceptionStatus", "err", t("ops.exception.status.bulk_align_required"));
        return;
      }
      const payloadRows = rows.filter((row) => String(row?.size_group || "").trim());
      if (!payloadRows.length) {
        setStatus("opsExceptionStatus", "err", t("ops.exception.status.bulk_align_no_size"));
        return;
      }
      try {
        setStatus("opsExceptionStatus", "ok", t("ops.exception.status.bulk_align_saving", { count: countWithUnit(payloadRows.length) }));
        let updated = 0;
        for (const row of payloadRows) {
          const res = await fetch("/owned-items/bulk-update", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              owned_item_ids: [Number(row.id)],
              preferred_storage_size_group: String(row.size_group || "").trim().toUpperCase(),
            }),
          });
          const data = await safeJson(res);
          if (!res.ok) throw new Error(data.detail || t("ops.exception.status.align_update_failed"));
          updated += Number(data.updated_count || 0);
        }
        opsExceptionSelectedIds = new Set();
        const okCount = updated;
        setStatus("opsExceptionStatus", "ok", `실물 기준 맞춤 완료 — ${countWithUnit(okCount)} 변경됨`);
        refreshOpsExceptionInBackground();
        refreshHomeSearchInBackground();
        refreshHomeDashboardInBackground();
      } catch (err) {
        setStatus("opsExceptionStatus", "err", err.message);
      }
    }

    function bulkSendExceptionsToSourceWorkbench() {
      const rows = getSelectedOpsExceptionRows();
      if (!rows.length) {
        setStatus("opsExceptionStatus", "err", t("ops.exception.status.bulk_source_required"));
        return;
      }
      const sentCount = rows.length;
      loadSourceWorkbenchRowsFromItems(rows, t("ops.exception.status.bulk_source_loaded", { count: countWithUnit(sentCount) }));
      setStatus("opsExceptionStatus", "ok", `${countWithUnit(sentCount)}이 소스 보강 대상으로 이동됐습니다`);
    }

    async function loadSourceWorkbenchTargets() {
      const limit = Math.max(1, Math.min(100, Number($("sourceWorkbenchLimit").value || 30)));
      try {
        sourceWorkbenchLoading = true;
        setStatus("sourceWorkbenchStatus", "ok", t("media.source.status.targets_loading"));
        const params = new URLSearchParams();
        params.set("music_only", "true");
        params.set("status", "IN_COLLECTION");
        params.set("source_state", $("sourceWorkbenchSourceState").value);
        params.set("sort", "RECENT");
        params.set("limit", String(limit));
        params.set("offset", "0");
        params.set("include_total", "true");
        if ($("homeArtist").value.trim()) params.set("artist_or_brand", $("homeArtist").value.trim());
        if ($("homeItemName").value.trim()) params.set("item_name", $("homeItemName").value.trim());
        if ($("homeCatalogNo").value.trim()) params.set("catalog_no", $("homeCatalogNo").value.trim());
        if ($("homeBarcode").value.trim()) params.set("barcode", $("homeBarcode").value.trim());
        if ($("homeReleaseYear").value.trim()) params.set("release_year", $("homeReleaseYear").value.trim());

        const res = await fetch(`/owned-items?${params.toString()}`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.source.status.targets_failed"));
        const total = Number(res.headers.get("X-Total-Count") || (Array.isArray(data) ? data.length : 0));
        sourceWorkbenchRows = (Array.isArray(data) ? data : []).map((row) => ({
          item: row,
          candidates: [],
          selectedIdx: -1,
          selectionMode: null,
          querySummary: "",
          searchArtistName: String(row?.artist_or_brand || row?.linked_artist_name || "").trim(),
          searchItemName: String(sourceWorkbenchCandidateTitle(row) || "").trim(),
          loading: false,
          error: "",
        }));
        renderSourceWorkbenchList();
        setStatus("sourceWorkbenchStatus", "ok", t("media.source.status.targets_loaded", {
          shown: formatCount(sourceWorkbenchRows.length),
          total: formatCount(total),
        }));
      } catch (err) {
        sourceWorkbenchRows = [];
        renderSourceWorkbenchList();
        setStatus("sourceWorkbenchStatus", "err", errorMessageText(err, t("media.source.status.targets_failed")));
      } finally {
        sourceWorkbenchLoading = false;
      }
    }

    async function loadSourceWorkbenchCandidatesForRow(rowIndex, opts = {}) {
      const entry = sourceWorkbenchRows[rowIndex];
      if (!entry) return;
      const silent = Boolean(opts.silent);
      const force = Boolean(opts.force);
      if (entry.loading) return;
      if (!force && Array.isArray(entry.candidates) && entry.candidates.length) return;

      try {
        entry.loading = true;
        entry.error = "";
        renderSourceWorkbenchList();
        if (!silent) setStatus("sourceWorkbenchStatus", "ok", t("media.source.status.candidates_loading", {
          name: resolveOwnedAlbumName(entry.item),
        }));
        const request = buildSourceWorkbenchSearchRequest(entry, opts);
        entry.querySummary = request.summary;
        const res = await fetch(request.endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(request.payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.source.status.candidates_failed"));
        const candidates = Array.isArray(data.candidates) ? data.candidates : [];
        entry.candidates = candidates;
        entry.selectedIdx = autoSelectSourceWorkbenchCandidate(entry.item, candidates);
        entry.selectionMode = entry.selectedIdx >= 0 ? "AUTO" : null;
        renderSourceWorkbenchList();
        if (!silent) {
          setStatus("sourceWorkbenchStatus", "ok", t("media.source.status.candidates_complete", {
            name: resolveOwnedAlbumName(entry.item),
            count: formatCount(candidates.length),
            auto: entry.selectedIdx >= 0 ? t("media.source.status.candidates_auto_selected") : "",
          }));
        }
      } catch (err) {
        entry.candidates = [];
        entry.selectedIdx = -1;
        entry.selectionMode = null;
        entry.error = err.message;
        renderSourceWorkbenchList();
        if (!silent) setStatus("sourceWorkbenchStatus", "err", errorMessageText(err, t("media.source.status.candidates_failed")));
      } finally {
        entry.loading = false;
        renderSourceWorkbenchList();
      }
    }

    async function fetchAllSourceWorkbenchCandidates() {
      const rows = Array.isArray(sourceWorkbenchRows) ? sourceWorkbenchRows : [];
      if (!rows.length) {
        setStatus("sourceWorkbenchStatus", "err", t("media.source.status.no_targets"));
        return;
      }

      for (let i = 0; i < rows.length; i += 1) {
        setStatus("sourceWorkbenchStatus", "ok", t("media.source.status.fetch_all_loading", {
          progress: `${i + 1}/${rows.length}`,
        }));
        await loadSourceWorkbenchCandidatesForRow(i, { silent: true, force: true });
      }
      const selectedCount = sourceWorkbenchRows.filter((row) => row.selectedIdx >= 0).length;
      setStatus("sourceWorkbenchStatus", "ok", t("media.source.status.fetch_all_complete", {
        total: formatCount(rows.length),
        selected: formatCount(selectedCount),
      }));
    }

    function openSourceWorkbenchDiffReview(selectedRows) {
      const rows = Array.isArray(selectedRows) ? selectedRows.filter((entry) => entry?.selectedIdx >= 0 && entry?.candidates?.[entry.selectedIdx]) : [];
      if (!rows.length) {
        setStatus("sourceWorkbenchStatus", "err", t("media.source.status.apply_none_selected"));
        return;
      }
      sourceWorkbenchDiffReviewState = buildSourceWorkbenchDiffReviewState({ selectedRows: rows });
      const modal = $("sourceWorkbenchDiffReview");
      if (modal) {
        modal.hidden = false;
        modal.classList.add("open");
        modal.setAttribute("aria-hidden", "false");
      }
      renderSourceWorkbenchDiffReview();
      setStatus("sourceWorkbenchStatus", "ok", t("media.source.status.diff_review_open", {
        count: countWithUnit(rows.length),
        fields: formatCount(sourceWorkbenchDiffReviewState?.summary?.selectedFieldCount || 0),
      }));
    }

    function closeSourceWorkbenchDiffReview() {
      sourceWorkbenchDiffReviewState = null;
      const modal = $("sourceWorkbenchDiffReview");
      if (!modal) return;
      modal.classList.remove("open");
      modal.hidden = true;
      modal.setAttribute("aria-hidden", "true");
    }

    function openSourceWorkbenchDiffReviewForSelections() {
      const selectedRows = sourceWorkbenchRows
        .filter((entry) => entry.selectedIdx >= 0 && Array.isArray(entry.candidates) && entry.candidates[entry.selectedIdx]);
      openSourceWorkbenchDiffReview(selectedRows);
    }

    async function submitSourceWorkbenchDiffReviewSelection() {
      if (!sourceWorkbenchDiffReviewState) return;
      const selectedFieldCount = sourceWorkbenchDiffReviewFieldCount(sourceWorkbenchDiffReviewState);
      const selectedItems = buildSourceWorkbenchDiffApplyItems({ reviewState: sourceWorkbenchDiffReviewState });
      if (!selectedItems.length) {
        setStatus("sourceWorkbenchStatus", "err", t("media.source.status.diff_review_none_selected"));
        return;
      }
      const applied = await applySourceWorkbenchItems(sourceWorkbenchDiffReviewState.items, "MANUAL_BATCH", {
        items: selectedItems,
        selectedFieldCount,
      });
      if (applied) closeSourceWorkbenchDiffReview();
    }

    async function applySourceWorkbenchItems(selectedRows, mode, opts = {}) {
      const selectedItems = Array.isArray(opts?.items)
        ? opts.items.filter((entry) => Number(entry?.owned_item_id || 0) > 0 && entry?.candidate)
        : buildSourceWorkbenchLegacyApplyItems({ selectedRows });

      if (!selectedItems.length) {
        setStatus("sourceWorkbenchStatus", "err", mode === "AUTO_READY"
          ? t("media.source.status.apply_none_auto")
          : t("media.source.status.apply_none_selected"));
        return false;
      }

      try {
        const actionLabel = sourceWorkbenchActionLabel(mode);
        const selectedFieldCount = Number(opts?.selectedFieldCount || 0);
        const appliedSources = [...new Set(selectedItems
          .map((entry) => sourceWorkbenchDiffNormalizeScalar(entry?.candidate?.source))
          .filter(Boolean))];
        const appliedSourceText = appliedSources.length ? appliedSources.join(", ") : "-";
        setStatus("sourceWorkbenchStatus", "ok", t("media.source.status.apply_loading", {
          action: actionLabel,
          count: formatCount(selectedItems.length),
        }));
        const res = await fetch("/owned-items/source-replace-bulk", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ items: selectedItems }),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.source.queue.detail.updated_failed"));
        const failed = Array.isArray(data.results)
          ? data.results.filter((row) => !row.updated)
          : [];
        const failedText = failed.length
          ? t("media.source.status.apply_failed_suffix", { count: countWithUnit(failed.length) })
          : "";
        pushSourceWorkbenchQueueEntries((Array.isArray(data.results) ? data.results : []).map((row) => ({
          created_at: new Date().toISOString(),
          mode,
          status: row.updated ? "SUCCESS" : "FAILED",
          owned_item_id: row.owned_item_id,
          label_id: row.label_id || null,
          item_name: selectedRows.find((entry) => Number(entry?.item?.id || entry?.ownedItemId || 0) === Number(row.owned_item_id))?.item?.item_name_override
            || selectedRows.find((entry) => Number(entry?.item?.id || entry?.ownedItemId || 0) === Number(row.owned_item_id))?.currentTitle
            || `owned_item_id ${row.owned_item_id}`,
          detail: row.updated
            ? `${row.source_code || "-"}#${row.source_external_id || "-"}`
            : (row.error || t("media.source.queue.detail.updated_failed")),
        })));
        const completionStatusKey = selectedFieldCount > 0
          ? "media.source.status.apply_complete_reviewed"
          : "media.source.status.apply_complete";
        setStatus("sourceWorkbenchStatus", "ok", t(completionStatusKey, {
          action: actionLabel,
          updated: formatCount(data.updated_count || 0),
          fields: formatCount(selectedFieldCount),
          source: appliedSourceText,
          failed: failedText,
        }));
        applySourceWorkbenchResults(Array.isArray(data.results) ? data.results : []);
        refreshOpsExceptionInBackground();
        const refreshOwnedItemId = (Array.isArray(data.results) ? data.results : [])
          .find((row) => row.updated && Number(row.owned_item_id || 0) === Number(homeSelectedItemId || 0))
          ?.owned_item_id;
        if (refreshOwnedItemId && $("tabManage")?.classList.contains("active")) {
          refreshHomeManageContext(Number(refreshOwnedItemId), {
            keepMasterContext: Boolean(homeSelectedMasterId),
            reloadMaster: Boolean(homeSelectedMasterId),
          }).catch(() => {});
        }
        if (mode === "MANUAL_BATCH" && failed.length) {
          sourceWorkbenchDiffReviewState = updateSourceWorkbenchDiffReviewStateAfterApply({
            reviewState: sourceWorkbenchDiffReviewState,
            results: Array.isArray(data.results) ? data.results : [],
          });
          renderSourceWorkbenchDiffReview();
          return false;
        }
        return true;
      } catch (err) {
        setStatus("sourceWorkbenchStatus", "err", err.message);
        return false;
      }
    }

    async function applySingleSourceWorkbenchRow(rowIndex) {
      const entry = sourceWorkbenchRows[rowIndex];
      if (!entry) return;
      const candidate = Array.isArray(entry.candidates) ? entry.candidates[entry.selectedIdx] : null;
      if (!candidate) {
        setStatus("sourceWorkbenchStatus", "err", t("media.source.status.row_needs_candidate"));
        return;
      }
      await applySourceWorkbenchItems([entry], "ROW_UPDATE");
    }

    async function applySourceWorkbenchSelections() {
      const selectedRows = sourceWorkbenchRows
        .filter((entry) => entry.selectedIdx >= 0 && Array.isArray(entry.candidates) && entry.candidates[entry.selectedIdx]);
      await applySourceWorkbenchItems(selectedRows, "MANUAL_BATCH");
    }

    async function runAutoReadySourceWorkbench() {
      if (!sourceWorkbenchRows.length) {
        setStatus("sourceWorkbenchStatus", "err", t("media.source.status.no_targets"));
        return;
      }

      const pendingEntries = [];
      for (let i = 0; i < sourceWorkbenchRows.length; i += 1) {
        setStatus("sourceWorkbenchStatus", "ok", t("media.source.status.auto_detect_loading", {
          progress: `${i + 1}/${sourceWorkbenchRows.length}`,
        }));
        await loadSourceWorkbenchCandidatesForRow(i, { silent: true, force: !sourceWorkbenchRows[i]?.candidates?.length });
      }

      const autoRows = sourceWorkbenchRows.filter((entry) => entry.selectionMode === "AUTO" && entry.selectedIdx >= 0);
      for (const entry of sourceWorkbenchRows) {
        if (entry.selectionMode === "AUTO" && entry.selectedIdx >= 0) continue;
        let detail = entry.error || "";
        if (!detail) {
          if (!entry.candidates.length) detail = t("media.source.queue.detail.none");
          else detail = t("media.source.queue.detail.manual_required", { count: countWithUnit(entry.candidates.length) });
        }
        pendingEntries.push({
          created_at: new Date().toISOString(),
          mode: "AUTO_READY",
          status: "PENDING",
          owned_item_id: Number(entry.item.id || 0),
          label_id: entry.item.label_id || null,
          item_name: entry.item.item_name_override || `owned_item_id ${entry.item.id}`,
          detail,
        });
      }
      pushSourceWorkbenchQueueEntries(pendingEntries);
      if (!autoRows.length) {
        setStatus("sourceWorkbenchStatus", "ok", t("media.source.status.auto_pending_complete", {
          count: formatCount(pendingEntries.length),
        }));
        return;
      }
      await applySourceWorkbenchItems(autoRows, "AUTO_READY");
    }

    async function loadHomeDashboard(opts = {}) {
      const silent = Boolean(opts?.silent);
      let phase = "dashboard";
      try {
        if (!silent) setStatus("homeDashboardStatus", "ok", t("dashboard.status.loading"));
        phase = "collection";
        const res = await fetch("/dashboard/collection");
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("dashboard.status.load_failed"));

        phase = "summary";
        /* hero KPI bar */
        const _musicTotal = Number(data.music_items ?? 0);
        const _goodsTotal = Number(data.goods_items ?? 0);
        setTextIfPresent("homeDashTotal", formatCount(_musicTotal + _goodsTotal));
        {
          const lp = Number(data.by_category?.find?.(c => c.category === "LP")?.count ?? 0) || 0;
          const cd = Number(data.by_category?.find?.(c => c.category === "CD")?.count ?? 0) || 0;
          setTextIfPresent("homeDashMusic", formatCount(_musicTotal));
          setTextIfPresent("homeDashMusicDetail", "LP " + formatCount(lp) + "  CD " + formatCount(cd));
        }
        setTextIfPresent("homeDashGoods", formatCount(_goodsTotal));

                /* hero bar: slot rate */
        {
          const _inCol2 = Number(data.in_collection_items ?? 0);
          const _slotted2 = Number(data.slotted_in_collection_items ?? 0);
          const slotPct = _inCol2 > 0 ? Math.round(_slotted2 / _inCol2 * 100) : 0;
          setTextIfPresent("homeDashHeroSlotRate", slotPct + "%");
          setTextIfPresent("homeDashHeroSlotRateLabel", formatCount(_slotted2) + " / " + formatCount(_inCol2));
        }
        /* hero bar: meta rate */
        {
          const _srcUnlinked2 = Number(data.source_unlinked_items ?? 0);
          const metaPct = _musicTotal > 0 ? Math.round((1 - _srcUnlinked2 / _musicTotal) * 100) : 0;
          setTextIfPresent("homeDashHeroMetaRate", metaPct + "%");
          setTextIfPresent("homeDashHeroMetaRateLabel", formatCount(_musicTotal - _srcUnlinked2) + " / " + formatCount(_musicTotal));
        }
        setTextIfPresent("homeDashRecent30", formatCount(data.registered_last_30_days));
        setTextIfPresent("homeDashDirectSigned", formatCount(data.direct_signed_items ?? 0));
        setTextIfPresent("homeDashPurchaseSigned", formatCount(data.purchase_signed_items ?? 0));
        setTextIfPresent("homeDashLimited", formatCount(data.limited_items ?? 0));
        const _fmtQ = (n, tot) => { const v = Number(n ?? 0); if (!v) return "0"; if (!tot) return formatCount(v); const pct = Math.round((v / tot) * 100); return `${formatCount(v)} (${pct}%)`; };
        setTextIfPresent("homeDashGenreMissing", _fmtQ(data.genre_missing_items, _musicTotal));
        setTextIfPresent("homeDashFormatMissing", _fmtQ(data.media_missing_items, _musicTotal));
        setTextIfPresent("homeDashCatalogMissing", _fmtQ(data.catalog_missing_items, _musicTotal));
        setTextIfPresent("homeDashLoaned", formatCount(data.loaned_items ?? 0));
        setTextIfPresent("homeDashSold", formatCount(data.sold_items ?? 0));
        setTextIfPresent("homeDashLost", formatCount(data.lost_items ?? 0));
        setTextIfPresent("homeDashInCollection", formatCount(data.in_collection_items ?? 0));
        setTextIfPresent("homeDashNewItems", formatCount(data.new_items ?? 0));
        setTextIfPresent("homeDashPromoItems", formatCount(data.promo_items ?? 0));
        setTextIfPresent("homeDashOtherItems", formatCount(data.other_condition_items ?? 0));
        {
          const pcEl = document.getElementById("homeDashPressingCountry");
          if (pcEl) {
            const countries = (data.by_pressing_country || []).slice(0, 5);
            if (countries.length === 0) {
              pcEl.textContent = "—";
            } else {
              pcEl.innerHTML = countries.map(c =>
                `<span><em>${c.value}</em> ${formatCount(c.count)}</span>`
              ).join("");
            }
          }
        }
        setTextIfPresent("homeDashBoxSet", formatCount(data.box_set_items ?? 0));
                /* hero bar: slot rate */
        {
          const _inCol2 = Number(data.in_collection_items ?? 0);
          const _slotted2 = Number(data.slotted_in_collection_items ?? 0);
          const slotPct = _inCol2 > 0 ? Math.round(_slotted2 / _inCol2 * 100) : 0;
          setTextIfPresent("homeDashHeroSlotRate", slotPct + "%");
          setTextIfPresent("homeDashHeroSlotRateLabel", formatCount(_slotted2) + " / " + formatCount(_inCol2));
        }
        /* hero bar: meta rate */
        {
          const _srcUnlinked2 = Number(data.source_unlinked_items ?? 0);
          const metaPct = _musicTotal > 0 ? Math.round((1 - _srcUnlinked2 / _musicTotal) * 100) : 0;
          setTextIfPresent("homeDashHeroMetaRate", metaPct + "%");
          setTextIfPresent("homeDashHeroMetaRateLabel", formatCount(_musicTotal - _srcUnlinked2) + " / " + formatCount(_musicTotal));
        }
        setTextIfPresent("homeDashRecent30", formatCount(data.registered_last_30_days));
        setTextIfPresent("homeDashReg7d", formatCount(data.registered_last_7_days ?? 0));
        /* 1/4 cards */
        const _inCol = Number(data.in_collection_items ?? 0);
        const _music = Number(data.music_items ?? 0);
        const _slotted = Number(data.slotted_in_collection_items ?? 0);
        const _srcUnlinked = Number(data.source_unlinked_items ?? 0);

        /* slot rate */
        const slotPct = _inCol > 0 ? Math.round(_slotted / _inCol * 100) : 0;
        setTextIfPresent("homeDashSlotRate", slotPct + "%");
        setTextIfPresent("homeDashSlotRateLabel", _slotted.toLocaleString() + " / " + _inCol.toLocaleString());

        /* meta rate */
        const metaPct = _music > 0 ? Math.round((1 - _srcUnlinked / _music) * 100) : 0;
        setTextIfPresent("homeDashMetaRate", metaPct + "%");
        setTextIfPresent("homeDashMetaRateLabel", (_music - _srcUnlinked).toLocaleString() + " / " + _music.toLocaleString());

        /* signed */
        setTextIfPresent("homeDashSignedCount", formatCount(data.signed_items));
        const directSigned = Number(data.direct_signed_items ?? 0);
        setTextIfPresent("homeDashSignedLabel", "직접 " + directSigned.toLocaleString() + "장");

        /* spotify (master-based) */
        const _spotifyMasters = Number(data.spotify_master_count ?? 0);
        const _totalMasters = Number(data.total_master_count ?? 0);
        if (_totalMasters > 0) {
          const spotifyPct = Math.round(_spotifyMasters / _totalMasters * 100);
          setTextIfPresent("homeDashSpotifyRate", spotifyPct + "%");
          setTextIfPresent("homeDashSpotifyLabel", _spotifyMasters.toLocaleString() + " / " + _totalMasters.toLocaleString());
        } else {
          setTextIfPresent("homeDashSpotifyRate", "—");
          setTextIfPresent("homeDashSpotifyLabel", "데이터 없음");
        }
        setTextIfPresent("homeDashRegToday", formatCount(data.registered_today ?? 0));
        const placementRate = Number(data.in_collection_items || 0) > 0
          ? Math.round((Number(data.slotted_in_collection_items || 0) / Number(data.in_collection_items || 0)) * 100)
          : 0;
        setTextIfPresent("homeDashPlacementRate", `${placementRate}%`);
        setTextIfPresent("homeDashSlottedCount", formatCount(data.slotted_in_collection_items ?? 0));
        setTextIfPresent("homeDashUnslotted", formatCount(data.unslotted_in_collection_items));
        setTextIfPresent("homeDashRecentMove1d", formatCount(data.recent_move_total));
        setTextIfPresent("homeDashSourceUnlinked", _fmtQ(data.source_unlinked_items, _musicTotal));
        setTextIfPresent("homeDashMasterUnlinked", _fmtQ(data.master_unlinked_items, _musicTotal));
        setTextIfPresent("homeDashCoverMissing", _fmtQ(data.cover_missing_items, _musicTotal));
        renderOpsHomeHeroStats({
          locationCount: data.slotted_in_collection_items,
          recentMoveCount: data.recent_move_total,
          recentRegistrationCount: data.registered_last_30_days,
          moveWindowDays: data.movement_window_days,
        });

        phase = "chips";
        renderDashboardChipGroup("homeDashByCategory", data.by_category, (value) => mediaDisplayLabel(value));
        renderDashboardChipGroup("homeDashByStatus", data.by_status, dashboardStatusLabel);
        renderDashboardChipGroup("homeDashByDomain", data.by_domain, dashboardDomainLabel);
        {
          const _unassigned = (data.by_domain || []).find(r => r.value === "UNASSIGNED");
          const _wEl = document.getElementById("homeDashDomainWarn");
          if (_wEl) {
            if (_unassigned && _unassigned.count > 0) {
              _wEl.textContent = `⚠ 미분류 ${formatCount(_unassigned.count)}건`;
              setDisplayMode(_wEl, "");
            } else { _wEl.textContent = ""; setDisplayMode(_wEl, "none"); }
          }
        }
        renderDashboardChipGroup("homeDashByReleaseType", data.by_release_type, dashboardReleaseTypeLabel);
        renderDashboardChipGroup("homeDashBySizeGroup", data.by_size_group, dashboardSizeGroupLabel);
        phase = "sources";
        // ── Dashboard renderers v2 ──
        renderDashboardSnapshot(data);
        renderDashboardHeatmap(data);
        renderDashboardFinance(data);
        renderDashboardGenreDomain(data);
        renderDashboardFormatPressing(data);
        renderDashboardArtistTimeline(data);
        renderDashboardMetaSource(data);
        renderDashboardCollector(data);
        renderDashboardAlerts(data);
        renderDashboardRegImport(data);
        renderDashboardMoveHeatmap(data);
        renderDashboardRecentReg(data);
        renderDashboardPurchaseFlow(data);
        loadDashboardClimate();
        phase = "slots";
        if (!String(homeDashboardSelectedCabinetKey || "").trim()) {
          restoreDashboardCabinetSelectionMemory();
        }
        renderDashboardSlotCards(data.by_slot, data.in_collection_items);
        {
          // 장식장 그룹별 점유율 집계
          const _cabOccEl = document.getElementById("homeDashCabinetOccupancy");
          if (_cabOccEl) {
            const _grpMap = {};
            (data.by_slot || []).forEach(s => {
              const cn = s.cabinet_name || "";
              if (s.is_overflow_zone || cn === "미배치" || !cn) return;
              const gn = s.cabinet_group_name || cn;  // 그룹명 없으면 장식장명
              const go = s.cabinet_group_order ?? 999;
              if (!_grpMap[gn]) _grpMap[gn] = { label: gn, order: go, cap: 0, used: 0 };
              _grpMap[gn].cap  += (s.capacity_mm       || 0);
              _grpMap[gn].used += (s.used_thickness_mm || 0);
            });
            const _cabRows = Object.values(_grpMap)
              .sort((a, b) => a.order - b.order || a.label.localeCompare(b.label))
              .map(v => {
                const pct = v.cap > 0 ? Math.round(v.used / v.cap * 100) : 0;
                const barW = Math.min(pct, 100);
                const warn = pct > 100 ? ' style="color:#ef4444;font-weight:700"' : "";
                return `<div class="dashboard-chip-row"><span>${escapeHtml(v.label)}</span><span${warn}>${pct}%<span style="display:inline-block;width:${barW * 0.4}px;max-width:40px;height:2px;background:var(--brand,#3b82f6);opacity:0.45;margin-left:4px;vertical-align:middle;border-radius:1px;"></span></span></div>`;
              });
            _cabOccEl.innerHTML = _cabRows.join("");
          }
        }
        applyDashboardWorkbenchPreferences();
        phase = "unassigned";
        await loadDashboardUnassignedItems({ silent: true });
        if (currentShellMode() === "cabinets" && pendingOpsCabinetSelection) {
          phase = "cabinet-route";
          await applyPendingOpsCabinetSelection({ silent: true });
        } else if (homeDashboardSelectedCabinetKey && homeDashboardSelectedSlotCode) {
          phase = "selected-slot";
          const groups = buildDashboardCabinetGroups(homeDashboardBySlot);
          const group = groups.find((item) => item.key === homeDashboardSelectedCabinetKey) || null;
          const slotRow = group
            ? group.rows.find((row) => String(row.slot_code || "").trim() === String(homeDashboardSelectedSlotCode || "").trim()) || null
            : null;
          if (slotRow) {
            await loadDashboardSlotItems(slotRow, { silent: true });
          }
        }
        phase = "recent-moves";
        renderDashboardRecentMoves(data.recent_moves, data.movement_window_days, data.recent_move_total);
        phase = "drilldown";
        initDashboardDrilldown();
        phase = "workbench";
        renderDashboardWorkbench();
        if (!silent) setStatus("homeDashboardStatus", "ok", "");
        loadDashboardRecentActivity().catch(() => {});
        loadDashboardClimate().catch(() => {});
        loadAlbumOfDay();
        if (typeof initDashboardWidgetDragDrop === "function") { initDashboardWidgetDragDrop(); }
        updateDashCharts(data);
        updateDashMetaBars(data, data.music_items);
      } catch (err) {
        console.error("loadHomeDashboard failed", { phase, error: err });
        const message = errorMessageText(err, t("dashboard.status.load_failed"));
        setStatus("homeDashboardStatus", "err", phase && phase !== "dashboard" ? `${phase}: ${message}` : message);
      }
    }

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

    function renderProductLinkedGoodsSection() {
      const list = $("homeProductLinkedGoodsList");
      const section = $("homeProductLinkedGoodsSection");
      if (!list || !section) return;
      const ownedItemId = Number(homeSelectedItemId || 0);
      if (ownedItemId <= 0) {
        list.innerHTML = `<div class='muted'>${escapeHtml(t("media.manage.collectibles.state.empty"))}</div>`;
        return;
      }
      if (homeProductLinkedGoodsLoading) {
        list.innerHTML = `<div class='muted'>${escapeHtml(t("media.manage.collectibles.state.loading"))}</div>`;
        return;
      }
      if (!homeProductLinkedGoods.length) {
        list.innerHTML = `<div class='muted'>${escapeHtml(t("media.manage.collectibles.state.empty"))}</div>`;
        return;
      }
      list.innerHTML = homeProductLinkedGoods
        .map((row) => homeProductCollectibleItemHtml(row))
        .join("");
    }

    function homeProductCollectibleItemHtml(row) {
      const goodsItemId = Number(row?.id || 0);
      const goodsName = String(row?.goods_name || "").trim() || "-";
      const imageUrl = String(
        row?.primary_image_url ||
        (Array.isArray(row?.image_urls) ? row.image_urls[0] : "") ||
        ""
      ).trim();
      const slotText = String(row?.slot_display_name || "").trim() || t("common.unspecified");
      return `
        <div class="goods-result-item home-master-collectible-item">
          <div class="album-result-cover">
            ${imageUrl
              ? `<img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(goodsName)}" />`
              : `<span>${escapeHtml(goodsCategoryLabel(row?.category))}</span>`}
          </div>
          <div class="album-result-main">
            <strong>${escapeHtml(goodsName)}</strong>
            <div class="goods-result-meta">
              <span class="tag">${escapeHtml(goodsCategoryLabel(row?.category))}</span>
              <span>${escapeHtml(goodsStatusLabel(row?.status))}</span>
              <span>${escapeHtml(slotText)}</span>
            </div>
            <div class="row u-mt-4 u-flex-between-center-wrap">
              <div class="mini">collectible_id: ${goodsItemId}</div>
              <button
                class="btn ghost tiny home-master-collectible-manage-btn"
                type="button"
                data-home-related-goods-id="${goodsItemId}"
              >${escapeHtml(t("media.manage.collectibles.action.manage"))}</button>
            </div>
          </div>
        </div>
      `;
    }

    async function loadProductLinkedGoods(ownedItemId, requestSeq = 0) {
      const targetId = Number(ownedItemId || 0);
      if (targetId <= 0) {
        homeProductLinkedGoods = [];
        homeProductLinkedGoodsLoading = false;
        renderProductLinkedGoodsSection();
        return;
      }
      try {
        homeProductLinkedGoodsLoading = true;
        renderProductLinkedGoodsSection();
        const res = await fetch(`/goods-items?owned_item_id=${targetId}&limit=200&offset=0`);
        const data = await safeJson(res);
        if (requestSeq && !isActiveHomeEditRequest(requestSeq)) return;
        if (!res.ok) throw new Error(data.detail || t("media.manage.collectibles.status.load_failed"));
        homeProductLinkedGoods = Array.isArray(data.items) ? data.items : [];
      } catch (err) {
        if (requestSeq && !isActiveHomeEditRequest(requestSeq)) return;
        homeProductLinkedGoods = [];
        setStatus("homeProductLinkedGoodsStatus", "err",
          err.message || t("media.manage.collectibles.status.load_failed"));
      } finally {
        if (requestSeq && !isActiveHomeEditRequest(requestSeq)) return;
        homeProductLinkedGoodsLoading = false;
        renderProductLinkedGoodsSection();
      }
    }

    function openGoodsRegisterFromProductContext() {
      const ownedItemId = Number(homeSelectedItemId || 0);
      openAdminConsole("collectibles");
      switchGoodsMode("register");
      resetGoodsRegisterForm({ preserveStatus: true });
      if (ownedItemId > 0 && $("goodsRegisterLinkedOwnedItemId")) {
        $("goodsRegisterLinkedOwnedItemId").value = String(ownedItemId);
      }
      setStatus(
        "goodsRegisterStatusLine",
        "ok",
        ownedItemId > 0
          ? t("collectibles.register.status.start_linked", { id: ownedItemId })
          : t("collectibles.register.status.start_independent")
      );
    }

    function homeMasterAddVariantItemHtml(row) {
      const ownedCount = Number(row.owned_count || 0);
      const primaryOwnedItemId = Number(row.primary_owned_item_id || 0);
      const isOwned = ownedCount > 0 && primaryOwnedItemId > 0;
      const ownedText = isOwned
        ? t("media.manage.master.variant.state.owned", { count: countWithUnit(ownedCount) })
        : t("media.manage.master.variant.state.missing");
      const sourceCode = normalizeSourceCode(row.source || homeMasterInfo?.source || "");
      const discogsLink = discogsReleaseLinkHtml(sourceCode, row.external_id, t("media.manage.master.fetch.candidate.link.discogs"));
      const galleryKey = registerImageGallery(`homeMasterVariant:${sourceCode}:${row.external_id || row.id || "-"}`, row, {
        title: `${row.artist_or_brand || "Unknown"} - ${row.title || "(no title)"}`,
        subtitle: `${sourceCode || "-"}#${row.external_id || "-"}`,
      });
      const galleryCount = galleryKey ? Number(imageGalleryRegistry.get(galleryKey)?.items?.length || 0) : 0;
      const discogsMetaHtml = buildDiscogsStandardMetaHtml(row, { includeOwnedCount: true });
      const actionBtn = isOwned
        ? `<button class="btn ghost homeMasterVariantEditBtn btn-compact-pad-sm" data-owned-id="${primaryOwnedItemId}" type="button">${escapeHtml(t("media.manage.master.variant.action.edit"))}</button>`
        : `<button class="btn homeMasterVariantRegisterBtn btn-compact-pad-sm" data-external-id="${escapeHtml(row.external_id || "")}" type="button">${escapeHtml(t("media.manage.master.variant.action.register"))}</button>`;
      const coverUrl = normalizeRenderableCoverUrl(row.cover_image_url);
      const cover = coverUrl
        ? `<a href="${escapeHtml(coverUrl)}" target="_blank" rel="noreferrer" title="${escapeHtml(t("media.manage.master.variant.cover_original"))}"><div class="table-cover-thumb"><img src="${escapeHtml(coverUrl)}" alt="${escapeHtml(row.title || "cover")}" /></div></a>`
        : `<div class="table-cover-thumb">-</div>`;
      return `
        <div class="result-item album-result home-master-variant-result">
          <div class="album-result-cover">${cover}</div>
          <div class="album-result-main">
            <strong>${escapeHtml(row.title || "-")}</strong>
            <div class="home-master-subline">
              <span class="tag">${escapeHtml(sourceCode || "-")}</span>
              ${discogsMetaHtml || `
                <span>${escapeHtml(mediaDisplayLabel(row.format_name || "-"))}</span>
                <span>${escapeHtml(String(row.release_year ?? "-"))}</span>
                <span>${escapeHtml(row.label_name || "-")}</span>
              `}
            </div>
            <div class="mini">${discogsLink || "-"}${galleryKey ? ` | ${imageGalleryButtonHtml(galleryKey, t("common.count.images", { count: formatCount(galleryCount) }))}` : ""}</div>
            <div class="home-master-variant-actions">
              <span class="mini home-master-variant-owned">${escapeHtml(ownedText)}</span>
              ${actionBtn}
            </div>
          </div>
        </div>
      `;
    }

    function homeMasterAddVariantRowHtml(row) {
      return homeMasterAddVariantItemHtml(row);
    }

    function resetHomeMasterAddPager(opts = {}) {
      const clearInputs = Boolean(opts.clearInputs);
      homeMasterAddPage = 1;
      homeMasterAddHasNext = false;
      homeMasterAddTotalCount = null;
      homeMasterAddTruncated = false;
      if (clearInputs) {
        $("homeMasterAddCatalogNo").value = "";
        $("homeMasterAddBarcode").value = "";
      }
      renderHomeMasterAddPager();
    }

    function resetForm() {
      $("category").value = "LP";
      $("sizeGroup").value = "LP";
      $("quantity").value = "1";
      $("domainCode").value = "";
      $("releaseType").value = "";
      $("linkedAlbumMasterId").value = "";
      $("linkedArtistName").value = "";
      $("isSecondHand").checked = false;
      $("status").value = "IN_COLLECTION";
      $("displayRank").value = "";
      $("slotId").value = "";
      $("signatureType").value = "NONE";
      $("purchaseSource").value = "";
      $("purchasePrice").value = "";
      $("currencyCode").value = "KRW";
      $("conditionGrade").value = "";
      $("memoryNote").value = "";
      $("promoNfs").checked = false;
      $("formatName").value = "LP";
      setConditionSelectValue("coverCondition", "");
      setConditionSelectValue("discCondition", "");
      $("labelName").value = "";
      $("catalogNo").value = "";
      $("runoutMatrix").value = "";
      $("releasedDate").value = "";
      $("discCount").value = "";
      $("speedRpm").value = "";
      $("mediaType").value = "";
      $("genres").value = "";
      $("styles").value = "";
      $("pressingCountry").value = "";
      $("hasObi").checked = false;
      $("coverImageUrl").value = "";
      $("trackList").value = "";
      $("goodsItemName").value = "";
      $("goodsImageUrls").value = "";
      $("posterStorageSpec").value = "";
      $("tshirtSize").value = "";
      $("cupMaterial").value = "";
      $("hatSize").value = "";
      $("itemNameOverride").value = "";
      $("barcodeInput").value = "";
      $("metaSourceFilter").value = "AUTO";
      $("queryArtist").value = "";
      $("queryTitle").value = "";
      $("queryCatalog").value = "";
      $("querySourceRef").value = "";
      selectedCandidate = null;
      syncMusicVisibility();
      setStatus("createStatus", "ok", "");
      setStatus("barcodeStatus", "ok", "");
      renderBarcodeResults([]);
    }

    function applyCandidateToForm(c, opts = {}) {
      const scroll = opts.scroll !== false;
      selectedCandidate = c;
      const category = inferMusicCategoryFromMetadata(c);
      $("category").value = category;
      $("formatName").value = category;
      $("sizeGroup").value = inferSizeGroupFromMetadata(category, c);
      // ManiaDB는 항상 가요(KOREA) — domain_code가 없더라도 강제 적용
      const sourceUpper = String(c.source || "").trim().toUpperCase();
      const isManiadb = sourceUpper === "MANIADB";
      const effectiveDomainCode = isManiadb ? "KOREA" : c.domain_code;
      const mappedDomain = pickMappedDomain(effectiveDomainCode);
      const mappedReleaseType = pickMappedReleaseType(c.release_type);
      if (mappedDomain) {
        const artistText = String(c.artist_or_brand || "").trim();
        const artistHasHangul = /[가-힣ㄱ-ㆎ]/.test(artistText);
        const artistHasKana  = /[぀-ヿ一-鿿]/.test(artistText);
        // 후보 도메인이 KOREA인데 아티스트명이 라틴이면 WESTERN으로 자동보정
        // (ManiaDB 소스는 제외 — 영문 표기 한국 아티스트 다수)
        if (!isManiadb && mappedDomain === "KOREA" && artistText && !artistHasHangul && !artistHasKana) {
          $("domainCode").value = "WESTERN";
          setStatus("createStatus", "ok", `도메인을 팝(WESTERN)으로 자동보정했습니다 — 아티스트명 "${artistText}" 이(가) 영문입니다. 틀리면 직접 수정하세요.`);
        } else if (!isManiadb && mappedDomain === "JAPAN" && artistText && !artistHasKana && !artistHasHangul) {
          $("domainCode").value = "WESTERN";
          setStatus("createStatus", "ok", `도메인을 팝(WESTERN)으로 자동보정했습니다 — 아티스트명 "${artistText}" 이(가) 영문입니다. 틀리면 직접 수정하세요.`);
        } else {
          $("domainCode").value = mappedDomain;
        }
      }
      if (mappedReleaseType) $("releaseType").value = mappedReleaseType;
      if (c.title) {
        $("itemNameOverride").value = c.title;
      }
      if (c.label_name) $("labelName").value = c.label_name;
      if (c.catalog_no) $("catalogNo").value = c.catalog_no;
      if (c.released_date) $("releasedDate").value = c.released_date;
      if (Number.isFinite(Number(c.disc_count)) && Number(c.disc_count) > 0) $("discCount").value = String(Number(c.disc_count));
      if (Number.isFinite(Number(c.speed_rpm)) && Number(c.speed_rpm) > 0) $("speedRpm").value = String(Number(c.speed_rpm));
      if (c.runout_matrix) $("runoutMatrix").value = joinRunoutList(c.runout_matrix);
      if (c.media_type) $("mediaType").value = c.media_type;
      if (c.pressing_country) $("pressingCountry").value = c.pressing_country;
      $("genres").value = joinCommaList(c.genres);
      $("styles").value = joinCommaList(c.styles);
      if (c.cover_image_url) $("coverImageUrl").value = c.cover_image_url;
      if (Array.isArray(c.track_list) && c.track_list.length) {
        $("trackList").value = c.track_list.join("\n");
      }
      const sourceMemo = `[AUTO] ${c.source}#${c.external_id} confidence=${c.confidence}`;
      const oldLines = $("memoryNote").value
        .split("\n")
        .map((v) => v.trim())
        .filter((v) => v);
      if (!oldLines.includes(sourceMemo)) oldLines.push(sourceMemo);
      $("memoryNote").value = oldLines.join("\n");
      syncMusicVisibility();
      if (scroll) {
        window.scrollTo({ top: document.body.scrollHeight * 0.2, behavior: "smooth" });
      }
    }

    function listRegisterLookupCabinets() {
      return [...new Set(
        storageSlotCache
          .map((slot) => String(slot?.cabinet_name || "").trim())
          .filter((v) => v && v.toUpperCase() !== "OVERFLOW")
      )].sort((a, b) => a.localeCompare(b, "ko"));
    }

    function listRegisterLookupFloors(cabinetName) {
      if (!cabinetName) return [];
      return [...new Set(
        storageSlotCache
          .filter((slot) => String(slot?.cabinet_name || "").trim() === cabinetName)
          .map((slot) => String(slot?.column_code || "").trim())
          .filter((v) => v)
      )].sort(compareCodeValue);
    }

    function listRegisterLookupCells(cabinetName, columnCode) {
      if (!cabinetName || !columnCode) return [];
      return [...new Set(
        storageSlotCache
          .filter((slot) =>
            String(slot?.cabinet_name || "").trim() === cabinetName &&
            String(slot?.column_code || "").trim() === columnCode
          )
          .map((slot) => String(slot?.cell_code || "").trim())
          .filter((v) => v)
      )].sort(compareCodeValue);
    }

    function fillRegisterLookupSelect(select, items, selectedValue, emptyLabel) {
      select.innerHTML = "";
      const emptyOpt = document.createElement("option");
      emptyOpt.value = "";
      emptyOpt.textContent = emptyLabel;
      select.appendChild(emptyOpt);
      for (const item of items) {
        const opt = document.createElement("option");
        opt.value = item;
        opt.textContent = item;
        if (String(item) === String(selectedValue || "")) opt.selected = true;
        select.appendChild(opt);
      }
    }

    function resolveRegisterLookupStorageSlotId(index) {
      const state = registerLookupLocationStateFor(index);
      const hasAny = Boolean(state.cabinet_name || state.column_code || state.cell_code);
      if (!hasAny) return null;
      if (!(state.cabinet_name && state.column_code && state.cell_code)) {
        throw new Error(t("media.register.api_lookup.status.slot_selection_required"));
      }
      const slot = storageSlotCache.find((row) =>
        String(row?.cabinet_name || "").trim() === state.cabinet_name &&
        String(row?.column_code || "").trim() === state.column_code &&
        String(row?.cell_code || "").trim() === state.cell_code
      );
      if (!slot) {
        throw new Error(t("media.register.api_lookup.status.slot_not_found"));
      }
      return Number(slot.id || 0) || null;
    }

    function buildLookupOwnedPayload(candidate, storageSlotId) {
      const sourceCodeRaw = String(candidate?.source || "").trim().toUpperCase();
      const sourceCode = SOURCE_MANAGED_CODES.has(sourceCodeRaw) ? sourceCodeRaw : null;
      const sourceExternalId = sourceCode ? (String(candidate?.external_id || "").trim() || null) : null;
      const category = inferMusicCategoryFromMetadata(candidate);
      const sizeGroup = inferSizeGroupFromMetadata(category, candidate);
      const mappedDomain = pickMappedDomain(candidate?.domain_code);
      const mappedReleaseType = pickMappedReleaseType(candidate?.release_type);
      const artist = String(candidate?.artist_or_brand || "").trim();
      const title = String(candidate?.title || "").trim();
      const itemName = [artist, title].filter((v) => v).join(" - ") || title || category;
      const collector = buildCollectorPayload(sourceCode, candidate || {});
      const trackList = Array.isArray(candidate?.track_list)
        ? candidate.track_list.map((v) => String(v || "").trim()).filter((v) => v)
        : [];

      return {
        category,
        size_group: sizeGroup,
        preferred_storage_size_group: sizeGroup,
        auto_location_recommendation: false,
        quantity: 1,
        is_second_hand: false,
        status: "IN_COLLECTION",
        signature_type: "NONE",
        source_code: sourceCode,
        source_external_id: sourceExternalId,
        domain_code: mappedDomain || null,
        release_type: mappedReleaseType || null,
        linked_album_master_id: null,
        linked_artist_name: null,
        purchase_source: null,
        condition_grade: null,
        memory_note: sourceCode && sourceExternalId ? `[AUTO] ${sourceCode}#${sourceExternalId}` : null,
        item_name_override: itemName,
        display_rank: null,
        storage_slot_id: storageSlotId,
        music_detail: {
          format_name: category,
          is_promotional_not_for_sale: false,
          artist_or_brand: artist || null,
          released_date: String(candidate?.released_date || "").trim() || null,
          barcode: String(candidate?.barcode || "").trim() || null,
          label_name: String(candidate?.label_name || "").trim() || null,
          catalog_no: String(candidate?.catalog_no || "").trim() || null,
          media_type: String(candidate?.media_type || "").trim() || null,
          genres: splitCommaList(candidate?.genres || []),
          styles: splitCommaList(candidate?.styles || []),
          cover_image_url: String(candidate?.cover_image_url || "").trim() || null,
          track_list: trackList,
          cover_condition: null,
          disc_condition: null,
          disc_count: normalizePositiveIntOrNull(candidate?.disc_count),
          speed_rpm: Number.isFinite(Number(candidate?.speed_rpm)) ? Number(candidate.speed_rpm) : null,
          has_obi: null,
          runout_matrix: collector.runout_matrix,
          pressing_country: collector.pressing_country,
          source_notes: collector.source_notes,
          credits: collector.credits,
          identifier_items: collector.identifier_items,
          image_items: collector.image_items,
          company_items: collector.company_items,
          series: collector.series,
          format_items: collector.format_items,
          track_items: collector.track_items,
          label_items: collector.label_items
        }
      };
    }

    async function registerCandidateFromLookup(entryOrIndex) {
      const entry = Number.isInteger(entryOrIndex)
          ? (() => {
              const candidate = registerLookupCandidates[entryOrIndex];
              if (!candidate) return null;
              return {
                key: registerLookupCandidateKey(candidate, entryOrIndex),
                candidate: cloneRegisterLookupCandidate(candidate),
                storage_slot_id: resolveAdminBarcodeRecommendedSlotId(candidate),
              };
            })()
        : entryOrIndex;
      if (!entry?.candidate) {
        setStatus("barcodeStatus", "err", t("media.register.api_lookup.status.candidate_not_found"));
        return;
      }

      const sourceLabel = `${entry.candidate.source}#${entry.candidate.external_id || "-"}`;
      setStatus(
        "barcodeStatus",
        "ok",
        t("media.register.api_lookup.status.saving", {
          source: sourceLabel,
          suffix: registerLookupSaveQueue.length ? ` / ${formatCount(registerLookupSaveQueue.length)}` : "",
        })
      );
      const payload = buildLookupOwnedPayload(entry.candidate, entry.storage_slot_id ?? null);
      const res = await fetchWithRetry("/owned-items", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      }, {
        retries: 2,
        retryDelayMs: 250,
        onRetry: (attempt, total) => setStatus(
          "barcodeStatus",
          "ok",
          retryingStatusText(
            t("media.register.api_lookup.status.saving", {
              source: sourceLabel,
              suffix: registerLookupSaveQueue.length ? ` / ${formatCount(registerLookupSaveQueue.length)}` : "",
            }),
            attempt,
            total
          )
        ),
      });
      const data = await safeJson(res);
      if (!res.ok) throw new Error(responseDetailText(data, t("media.register.api_lookup.status.save_failed")));
      const notices = Array.isArray(data.notices) ? data.notices.slice() : [];
      const mergeNotices = await maybeMergeDuplicateMastersForCreatedItem(
        Number(data.linked_album_master_id || 0),
        "barcodeStatus"
      );
      for (const msg of mergeNotices) notices.push(msg);

      const visibleIndex = findRegisterLookupCandidateIndexByKey(entry.key);
      if (visibleIndex >= 0 && registerLookupCandidates[visibleIndex]) {
        registerLookupCandidates[visibleIndex].is_owned = true;
        registerLookupCandidates[visibleIndex].owned_count = Number(registerLookupCandidates[visibleIndex].owned_count || 0) + 1;
      }
      renderBarcodeResults(registerLookupCandidates, { resetLocationState: false });

      const savedSlot = entry.storage_slot_id ? getStorageSlotById(entry.storage_slot_id) : null;
      const savedLocationText = savedSlot ? storageSlotDisplayLabel(savedSlot) : t("common.unslotted");
      const labelText = data.label_id ? ` · ${t("common.meta.label_id", { value: data.label_id })}` : "";
      const noticeText = notices.length ? t("media.register.api_lookup.status.notice_suffix", { count: formatCount(notices.length) }) : "";
      const savedMessage = t("media.register.api_lookup.status.saved_message", {
        location: savedLocationText,
        label: labelText,
        suffix: noticeText,
      });
      clearAdminBarcodeConfirmation();
      const barcodeInput = $("barcodeInput");
      if (barcodeInput) barcodeInput.focus();
      setAdminBarcodeIntakeHint("saved");
      showAdminBarcodeToast(savedMessage);
      showAdminBarcodeToast(savedMessage, savedLocationText);
      setStatus("barcodeStatus", "ok", savedMessage);

      const refreshResults = await Promise.allSettled([
        loadOwnedItems(),
        loadHomeDashboard(),
        homeSearchOwnedItems({ resetPage: true }),
      ]);
      const refreshErrors = refreshResults
        .filter((row) => row.status === "rejected")
        .map((row) => errorMessageText(row.reason, t("media.register.api_lookup.status.refresh_failed")))
        .filter((row) => row);
      if (refreshErrors.length) {
        setStatus(
          "barcodeStatus",
          "ok",
          t("media.register.api_lookup.status.refresh_partial_failed", {
            saved: savedMessage,
            errors: refreshErrors.join(" / "),
          })
        );
      }
      if (registerLookupSaveQueue.length) {
        setStatus(
          "barcodeStatus",
          "ok",
          t("media.register.api_lookup.status.queue_continues", {
            saved: savedMessage,
            count: formatCount(registerLookupSaveQueue.length),
          })
        );
      }
    }

    function queueRegisterLookupCandidate(index) {
      const candidate = registerLookupCandidates[index];
      if (!candidate) {
        setStatus("barcodeStatus", "err", t("media.register.api_lookup.status.candidate_not_found"));
        return;
      }
      // Flush any pending edits from DOM inputs directly (belt-and-suspenders over the input event)
      const barcodeResultsEl = $("barcodeResults");
      if (barcodeResultsEl) {
        const artistInputEl = barcodeResultsEl.querySelector(`[data-register-lookup-artist="${index}"]`);
        if (artistInputEl) {
          const editedArtist = String(artistInputEl.value || "").trim();
          if (editedArtist) candidate.artist_or_brand = editedArtist;
        }
        const domainSelEl = barcodeResultsEl.querySelector(`[data-register-lookup-domain="${index}"]`);
        if (domainSelEl) {
          const editedDomain = String(domainSelEl.value || "").trim().toUpperCase() || null;
          candidate.domain_code = editedDomain;
        }
      }
      const key = registerLookupCandidateKey(candidate, index);
      if (registerLookupSavingKey === key || registerLookupQueuedKeys.has(key)) {
        setStatus("barcodeStatus", "ok", t("media.register.api_lookup.status.already_queued"));
        return;
      }
      if (!confirmAdminBarcodeDuplicateSave(candidate)) {
        setStatus("barcodeStatus", "ok", t("media.register.api_lookup.status.duplicate_cancelled"));
        return;
      }
      const entry = {
        key,
        candidate: cloneRegisterLookupCandidate(candidate),
        storage_slot_id: resolveAdminBarcodeRecommendedSlotId(candidate),
      };
      registerLookupSaveQueue.push(entry);
      registerLookupQueuedKeys.add(key);
      renderBarcodeResults(registerLookupCandidates, { resetLocationState: false });
      if (registerLookupSaveInFlight) {
        setStatus("barcodeStatus", "ok", t("media.register.api_lookup.status.queued", { count: formatCount(registerLookupSaveQueue.length) }));
        return;
      }
      void processRegisterLookupQueue();
    }

    async function processRegisterLookupQueue() {
      if (registerLookupSaveInFlight) return;
      const next = registerLookupSaveQueue.shift();
      if (!next) {
        registerLookupSavingKey = "";
        resetAdminBarcodeIntakeWorkspace({ preserveStatus: true });
        return;
      }
      registerLookupSaveInFlight = true;
      registerLookupQueuedKeys.delete(next.key);
      registerLookupSavingKey = next.key;
      renderBarcodeResults(registerLookupCandidates, { resetLocationState: false });
      try {
        await registerCandidateFromLookup(next);
      } catch (err) {
        setStatus("barcodeStatus", "err", errorMessageText(err, t("media.register.api_lookup.status.save_failed")));
      } finally {
        registerLookupSaveInFlight = false;
        registerLookupSavingKey = "";
        renderBarcodeResults(registerLookupCandidates, { resetLocationState: false });
        if (registerLookupSaveQueue.length) {
          void processRegisterLookupQueue();
        }
      }
    }

    function compareRegisterLookupCandidateDisplay(a, b) {
      const sourceA = normalizeSourceCode(a?.source);
      const sourceB = normalizeSourceCode(b?.source);
      if (sourceA !== "MANIADB" || sourceB !== "MANIADB") return 0;
      const yearDiff = registerLookupCandidateSortYear(a) - registerLookupCandidateSortYear(b);
      if (yearDiff !== 0) return yearDiff;
      const formatDiff = registerLookupCandidateFormatRank(a) - registerLookupCandidateFormatRank(b);
      if (formatDiff !== 0) return formatDiff;
      const aCatalog = String(a?.catalog_no || "").trim();
      const bCatalog = String(b?.catalog_no || "").trim();
      const catalogDiff = compareCodeValue(aCatalog || "ZZZ", bCatalog || "ZZZ");
      if (catalogDiff !== 0) return catalogDiff;
      return 0;
    }

    function renderBarcodeResults(items, opts = {}) {
      const resetLocationState = opts.resetLocationState !== false;
      registerLookupCandidates = Array.isArray(items)
        ? items
            .map((candidate, order) => ({
              candidate,
              order,
              isOwned: Number(candidate.owned_count || 0) > 0 || Boolean(candidate.is_owned),
            }))
            .sort((a, b) => Number(b.isOwned) - Number(a.isOwned) || compareRegisterLookupCandidateDisplay(a.candidate, b.candidate) || a.order - b.order)
            .map(({ candidate }) => candidate)
        : [];
      adminBarcodePlacementToken += 1;
      if (resetLocationState) registerLookupLocationState = {};
      const root = $("barcodeResults");
      root.innerHTML = "";
      $("barcodeCount").textContent = countWithUnit(registerLookupCandidates.length);
      const selectedKey = selectedRegisterLookupCandidateKey();
      if (selectedKey && findRegisterLookupCandidateIndexByKey(selectedKey) < 0) {
        selectedCandidate = null;
      }
      syncAdminBarcodeIntakePanels();

      if (!registerLookupCandidates.length) {
        root.innerHTML = `<div class='muted'>${escapeHtml(t("media.register.api_lookup.results.empty"))}</div>`;
        return;
      }

      for (const [index, c] of registerLookupCandidates.entries()) {
        const box = document.createElement("div");
        const candidateKey = registerLookupCandidateKey(c, index);
        const isSelected = Boolean(selectedKey) && selectedKey === candidateKey;
        const isOwnedCandidate = Number(c.owned_count || 0) > 0 || Boolean(c.is_owned);
        box.className = `result-item album-result${isSelected ? " pick" : ""}`;
        box.classList.toggle("is-owned", Number(c.owned_count || 0) > 0 || Boolean(c.is_owned));
        box.tabIndex = 0;
        box.style.cursor = "pointer";
        box.setAttribute("data-register-lookup-index", String(index));
        box.setAttribute("aria-selected", isSelected ? "true" : "false");
        const queueKey = registerLookupCandidateKey(c, index);
        const isSaving = registerLookupSavingKey === queueKey;
        const isQueued = registerLookupQueuedKeys.has(queueKey);
        const title = `${c.artist_or_brand || "Unknown"} - ${c.title || "(no title)"}`;
        const releasedDate = String(c.released_date || c.release_year || "").trim() || "-";
        const genreText = joinCommaList(c.genres || []) || "-";
        const formatLabel = mediaDisplayLabel(c.format_name || "LP");
        const discogsLink = discogsReleaseLinkHtml(c.source, c.external_id, "Discogs");
        const galleryKey = registerImageGallery(`registerLookup:${normalizeSourceCode(c.source)}:${c.external_id || index}`, c, {
          title,
          subtitle: `${normalizeSourceCode(c.source) || "-"}#${c.external_id || "-"}`,
        });
        const galleryCount = galleryKey ? Number(imageGalleryRegistry.get(galleryKey)?.items?.length || 0) : 0;
        const ownedBadge = Number(c.owned_count || 0) > 0 || c.is_owned
          ? `<span class="album-result-status-badge owned admin-barcode-candidate-flag">${escapeHtml(t("common.meta.already_owned", { count: countWithUnit(Number(c.owned_count || 0)) }))}</span>`
          : "";
        const discogsMetaHtml = buildDiscogsStandardMetaHtml(c, { includeOwnedCount: true });
        const coverUrl = normalizeRenderableCoverUrl(c.cover_image_url);
        const cover = coverUrl
          ? `<img src="${escapeHtml(coverUrl)}" alt="${escapeHtml(title)}" />`
          : escapeHtml(t("common.no_cover"));
        const registerButtonHtml = `<button class="btn ghost admin-barcode-result-save-btn" type="button" data-register-lookup-save="${index}" ${isSaving || isQueued ? "disabled" : ""}>${escapeHtml(isSaving ? t("media.register.api_lookup.action.save_loading") : (isQueued ? t("media.register.api_lookup.action.save_queued") : t("media.register.api_lookup.action.save_owned")))}</button>`;
        const currentDomainCode = String(c.domain_code || "").trim().toUpperCase();
        const domainOptions = ["", "KOREA", "JAPAN", "GREATER_CHINA", "WESTERN", "OTHER_ASIA", "WORLD", "UNKNOWN"]
          .map((dc) => `<option value="${dc}"${dc === currentDomainCode ? " selected" : ""}>${dc ? escapeHtml(dashboardDomainLabel(dc)) : escapeHtml(t("common.unspecified"))}</option>`)
          .join("");
        const domainSelectHtml = `<select class="ingest-domain-select operator-domain-badge${currentDomainCode ? ` domain-${escapeHtml(currentDomainCode)}` : ""}" data-register-lookup-domain="${index}" title="${escapeHtml(t("media.register.api_lookup.field.domain.label"))}">${domainOptions}</select>`;
        const artistName = String(c.artist_or_brand || "").trim();
        const artistEditHtml = `<div class="ingest-artist-edit-row"><span class="ingest-artist-edit-label">${escapeHtml(t("media.register.api_lookup.field.artist.label"))}</span><input class="ingest-artist-name-input" type="text" data-register-lookup-artist="${index}" value="${escapeHtml(artistName)}" placeholder="${escapeHtml(t("media.register.api_lookup.field.artist.placeholder"))}" autocomplete="off"></div>`;
        box.innerHTML = `
          <div class="album-result-cover">${cover}</div>
          <div class="album-result-main">
            <strong>${escapeHtml(title)}</strong>
            ${artistEditHtml}
            <div class="result-meta">
              <span class="tag home-master-source-chip">${escapeHtml(c.source || "-")}</span>
              ${domainSelectHtml}
              ${ownedBadge}
              ${discogsMetaHtml || `
                <span>${escapeHtml(t("common.meta.format", { value: formatLabel }))}</span>
                <span>${escapeHtml(t("common.meta.release_date", { value: releasedDate }))}</span>
                <span>${escapeHtml(t("common.meta.genre"))} ${escapeHtml(genreText)}</span>
                ${Number(c.owned_count || 0) > 0 ? `<span>${escapeHtml(t("common.meta.already_owned", { count: countWithUnit(Number(c.owned_count || 0)) }))}</span>` : ""}
              `}
              ${discogsLink ? `<span>${discogsLink}</span>` : ""}
              <span class="admin-barcode-result-actions">
                ${galleryKey ? imageGalleryButtonHtml(galleryKey, t("media.source.candidate.action.images", { count: galleryCount })) : ""}
                ${registerButtonHtml}
              </span>
            </div>
            <div class="row u-mt-4 u-flex-between-center-wrap">
              <div class="mini">${escapeHtml(t("common.meta.external_id", { value: c.external_id || "-" }))}${isOwnedCandidate ? ` / ${escapeHtml(t("common.meta.already_owned", { count: countWithUnit(Number(c.owned_count || 0)) }))}` : ""}</div>
              <div class="mini">${escapeHtml(t("common.meta.candidate_confidence", { value: Number(c.confidence || 0).toFixed(3) }))}</div>
            </div>
          </div>
        `;
        root.appendChild(box);
      }
    }

    function resetOpsSlotForm() {
      $("opsSlotId").value = "";
      $("opsSlotCabinetName").value = "";
      $("opsSlotColumnCode").value = "";
      $("opsSlotCellCode").value = "";
      $("opsSlotSizeGroup").value = "STD";
      setStatus("opsSlotStatus", "ok", "");
    }

    function recommendedCabinetSlotCapacityMm(sizeGroup) {
      const defaults = {
        STD: 142,
        BOOK: 320,
        LP: 360,
        LP10: 300,
        LP7: 200,
        OVERSIZE: 520,
        CASSETTE: 142,
        "8TRACK": 142,
        "REEL_TO_REEL": 320,
        GOODS: 220,
      };
      return Number(defaults[String(sizeGroup || "").trim().toUpperCase()] || 0);
    }

    function renderOpsCabinetSlotCapacityHint() {
      const hint = $("opsCabinetSlotCapacityHint");
      if (!hint) return;
      const recommended = recommendedCabinetSlotCapacityMm($("opsCabinetSizeGroup").value);
      const currentValue = Number($("opsCabinetSlotCapacityMm").value || 0);
      if (currentValue > 0 && currentValue !== recommended) {
        hint.textContent = t("ops.cabinet.slot_capacity.hint.custom", { recommended: formatCount(recommended) });
        return;
      }
      hint.textContent = t("ops.cabinet.slot_capacity.hint.default", { recommended: formatCount(recommended) });
    }

    function maybeAutofillOpsCabinetSlotCapacity(force = false) {
      const currentValue = String($("opsCabinetSlotCapacityMm").value || "").trim();
      if (!force && currentValue) {
        renderOpsCabinetSlotCapacityHint();
        return;
      }
      const suggested = recommendedCabinetSlotCapacityMm($("opsCabinetSizeGroup").value);
      $("opsCabinetSlotCapacityMm").value = suggested > 0 ? String(suggested) : "";
      renderOpsCabinetSlotCapacityHint();
    }

    function resetOpsCabinetForm() {
      $("opsCabinetSelectedName").value = "";
      $("opsCabinetName").value = "";
      $("opsCabinetGroupName").value = "";
      $("opsCabinetGroupOrder").value = "";
      $("opsCabinetDomainCode").value = "";
      $("opsCabinetSizeGroup").value = "STD";
      $("opsCabinetSortPolicy").value = "ARTIST_RELEASE_TITLE";
      $("opsCabinetFloorCount").value = "6";
      $("opsCabinetCellCount").value = "6";
      $("opsCabinetSlotCapacityMm").value = "";
      maybeAutofillOpsCabinetSlotCapacity(true);
      $("opsCabinetFloorStart").value = "1";
      $("opsCabinetCellStart").value = "1";
      setOpsCabinetFormMode(null);
      setStatus("opsCabinetStatus", "ok", "");
    }

    function fillOpsSlotForm(slot) {
      if (!slot) {
        resetOpsSlotForm();
        return;
      }
      $("opsSlotId").value = String(slot.id || "");
      $("opsSlotCabinetName").value = String(slot.cabinet_name || "");
      $("opsSlotColumnCode").value = String(slot.column_code || "");
      $("opsSlotCellCode").value = String(slot.cell_code || "");
      $("opsSlotSizeGroup").value = String(slot.allowed_size_group || "STD");
    }

    function renderOpsSlotTable(rows) {
      const body = $("opsSlotTableBody");
      if (!body) return;
      const list = Array.isArray(rows) ? rows : [];
      body.innerHTML = list.length ? list.map((slot) => `
        <tr data-slot-id="${slot.id}">
          <td>${slot.id}</td>
          <td>${escapeHtml(slot.cabinet_name || "-")}</td>
          <td>${escapeHtml(slot.column_code || "-")}</td>
          <td>${escapeHtml(slot.cell_code || "-")}</td>
          <td>${escapeHtml(storageSlotDisplayLabel(slot))}</td>
          <td>${escapeHtml(dashboardSizeGroupLabel(slot.allowed_size_group))}</td>
          <td>${escapeHtml(slot.slot_code || "-")}</td>
        </tr>
      `).join("") : `<tr><td colspan='7' class='muted'>${escapeHtml(t("ops.slot.list.state.empty"))}</td></tr>`;
    }

    function renderOpsCabinetTable(rows) {
      const body = $("opsCabinetTableBody");
      if (!body) return;
      const list = summarizeStorageCabinets(rows);
      body.innerHTML = list.length ? list.map((cabinet) => `
        <tr data-cabinet-name="${encodeURIComponent(cabinet.cabinet_name)}">
          <td>${escapeHtml(cabinet.cabinet_name)}</td>
          <td>${escapeHtml(cabinet.cabinet_group_name ? `${cabinet.cabinet_group_name} · ${formatCount(cabinet.cabinet_group_order || 0)}` : "-")}</td>
          <td>${escapeHtml(dashboardDomainLabel(cabinet.cabinet_domain_code || "UNASSIGNED"))}</td>
          <td>${escapeHtml(cabinet.size_group || "-")}</td>
          <td>${cabinet.max_thickness_mm ? `${formatCount(cabinet.max_thickness_mm)}mm` : t("common.default")}</td>
          <td>${escapeHtml(cabinetSortPolicyLabel(cabinet.cabinet_sort_policy))}</td>
          <td>${formatCount(cabinet.floor_count)}</td>
          <td>${formatCount(cabinet.cell_count)}</td>
          <td>${formatCount(cabinet.slot_count)}</td>
        </tr>
      `).join("") : `<tr><td colspan='9' class='muted'>${escapeHtml(t("ops.cabinet.list.state.empty"))}</td></tr>`;
    }

    function getOpsCabinetSummary(cabinetName) {
      const target = String(cabinetName || "").trim();
      if (!target) return null;
      return summarizeStorageCabinets(storageSlotCache)
        .find((item) => String(item.cabinet_name || "").trim() === target) || null;
    }

    function setOpsCabinetFormMode(summary = null) {
      const isEditMode = Boolean(summary && summary.cabinet_name);
      $("opsCabinetSelectedName").value = isEditMode ? String(summary.cabinet_name || "") : "";
      $("opsCabinetName").disabled = isEditMode;
      $("opsCabinetSizeGroup").disabled = isEditMode;
      $("opsCabinetFloorStart").disabled = isEditMode;
      $("opsCabinetCellStart").disabled = isEditMode;
      $("opsCabinetSaveBtn").textContent = isEditMode ? t("ops.cabinet.action.update") : t("ops.cabinet.action.save");
      const hint = $("opsCabinetModeHint");
      if (!hint) return;
      if (!isEditMode) {
        hint.textContent = t("ops.cabinet.mode_hint.create");
        return;
      }
      hint.textContent = summary.can_safe_edit
        ? t("ops.cabinet.mode_hint.safe_edit")
        : t("ops.cabinet.mode_hint.unsafe_edit");
    }

    function fillOpsCabinetForm(summary) {
      if (!summary) {
        resetOpsCabinetForm();
        return;
      }
      $("opsCabinetName").value = String(summary.cabinet_name || "");
      $("opsCabinetGroupName").value = String(summary.cabinet_group_name || "");
      $("opsCabinetGroupOrder").value = String(summary.cabinet_group_order || "");
      $("opsCabinetDomainCode").value = String(summary.cabinet_domain_code || "");
      $("opsCabinetSizeGroup").value = String(summary.size_group_code || "STD");
      $("opsCabinetSortPolicy").value = String(summary.cabinet_sort_policy || "ARTIST_RELEASE_TITLE");
      $("opsCabinetFloorCount").value = String(summary.floor_count || 1);
      $("opsCabinetCellCount").value = String(summary.cell_count || 1);
      $("opsCabinetSlotCapacityMm").value = String(summary.max_thickness_mm || "");
      renderOpsCabinetSlotCapacityHint();
      $("opsCabinetFloorStart").value = String(summary.floor_start || 1);
      $("opsCabinetCellStart").value = String(summary.cell_start || 1);
      $("opsSlotCabinetName").value = String(summary.cabinet_name || "");
      setOpsCabinetFormMode(summary);
    }

    function resetOpsCameraForm() {
      opsCameraSelectedId = null;
      $("opsCameraCabinetName").value = "";
      $("opsCameraName").value = "";
      $("opsCameraDescription").value = "";
      $("opsCameraOnvifUrl").value = "";
      $("opsCameraSnapshotUrl").value = "";
      $("opsCameraStreamUrl").value = "";
      $("opsCameraUsername").value = "";
      $("opsCameraPassword").value = "";
      $("opsCameraActive").checked = true;
      const advanced = $("opsCameraAdvancedSettings");
      if (advanced) advanced.open = false;
      const summary = $("opsCameraSelectionSummary");
      if (summary) {
        summary.classList.remove("active");
        summary.innerHTML = t("ops.camera.selection.new");
      }
      setStatus("opsCameraStatus", "", "");
    }

    function fillOpsCameraForm(item) {
      if (!item || typeof item !== "object") return;
      opsCameraSelectedId = Number(item.id || 0) || null;
      $("opsCameraCabinetName").value = String(item.cabinet_name || item.camera_name || "");
      $("opsCameraName").value = String(item.camera_name || "");
      $("opsCameraDescription").value = String(item.description || "");
      $("opsCameraOnvifUrl").value = String(item.onvif_device_url || "");
      $("opsCameraSnapshotUrl").value = String(item.snapshot_url || "");
      $("opsCameraStreamUrl").value = String(item.stream_url || "");
      $("opsCameraUsername").value = "";
      $("opsCameraPassword").value = "";
      $("opsCameraActive").checked = Boolean(item.is_active);
      const advanced = $("opsCameraAdvancedSettings");
      if (advanced) {
        advanced.open = Boolean(item.onvif_device_url || item.snapshot_url || item.stream_url || item.has_credentials);
      }
      const summary = $("opsCameraSelectionSummary");
      if (summary) {
        const detailBits = [
          String(item.description || "").trim() || t("shared_camera.state.no_description"),
          Boolean(item.stream_url)
            ? t("ops.camera.table.preview.stream_priority")
            : Boolean(item.snapshot_url)
              ? t("ops.camera.table.preview.snapshot")
              : t("ops.camera.table.preview.none"),
          Boolean(item.is_active) ? t("ops.camera.table.state.active") : t("ops.camera.table.state.inactive"),
        ];
        summary.classList.add("active");
        summary.innerHTML = `<strong>${escapeHtml(String(item.camera_name || "-"))}</strong><span>${escapeHtml(detailBits.join(" · "))}</span>`;
      }
      sharedCameraSelectedId = opsCameraSelectedId;
      renderSharedCameraPage();
      setStatus("opsCameraStatus", "ok", t("ops.camera.status.selected", { camera: String(item.camera_name || "-") }));
    }

    function renderOpsCameraTable(rows) {
      const body = $("opsCameraTableBody");
      if (!body) return;
      const list = Array.isArray(rows) ? rows : [];
      body.innerHTML = list.length ? list.map((item) => `
        <tr data-camera-id="${item.id}"${Number(item.id || 0) === Number(opsCameraSelectedId || 0) ? ' class="pick"' : ""}>
          <td>${escapeHtml(item.description || "-")}</td>
          <td>${escapeHtml(item.camera_name || "-")}</td>
          <td>${item.stream_url ? t("ops.camera.table.preview.stream_priority") : item.snapshot_url ? t("ops.camera.table.preview.snapshot") : t("ops.camera.table.preview.none")}</td>
          <td>${item.is_active ? t("ops.camera.table.state.active") : t("ops.camera.table.state.inactive")}</td>
        </tr>
      `).join("") : `<tr><td colspan='4' class='muted'>${escapeHtml(t("ops.camera.list.state.empty"))}</td></tr>`;
    }

    function renderOpsCameraDiscoverTable(rows) {
      const body = $("opsCameraDiscoverTableBody");
      if (!body) return;
      const list = Array.isArray(rows) ? rows : [];
      body.innerHTML = list.length ? list.map((item, index) => `
        <tr data-discover-index="${index}">
          <td>${escapeHtml(item.camera_name || "-")}</td>
          <td>${escapeHtml(item.host || "-")}</td>
          <td><button class="btn ghost tiny" type="button" data-ops-camera-discover-use="${index}" title="${escapeHtml(item.onvif_device_url || "-")}">${escapeHtml(t("ops.camera.discover.action.fill_form"))}</button></td>
        </tr>
      `).join("") : `<tr><td colspan='3' class='muted'>${escapeHtml(t("ops.camera.discover.state.empty"))}</td></tr>`;
    }

    function applyDiscoveredCamera(item) {
      if (!item || typeof item !== "object") return;
      $("opsCameraName").value = String(item.camera_name || item.host || "");
      $("opsCameraOnvifUrl").value = String(item.onvif_device_url || "");
      const advanced = $("opsCameraAdvancedSettings");
      if (advanced) advanced.open = true;
      const scopeLines = Array.isArray(item.scopes) ? item.scopes.filter((v) => String(v || "").trim()) : [];
      if (!$("opsCameraDescription").value.trim() && scopeLines.length) {
        $("opsCameraDescription").value = scopeLines[0];
      }
      setStatus("opsCameraStatus", "ok", t("ops.camera.status.discover_applied", {
        camera: String(item.camera_name || item.host || "camera"),
        url: String(item.onvif_device_url || "-"),
      }));
    }

    function ensureSharedCameraSelection(rows) {
      const list = Array.isArray(rows) ? rows : [];
      if (!list.length) {
        sharedCameraSelectedId = null;
        return null;
      }
      const current = list.find((item) => Number(item.id || 0) === Number(sharedCameraSelectedId || 0)) || null;
      if (current) return current;
      const firstActive = list.find((item) => Boolean(item?.is_active)) || list[0];
      sharedCameraSelectedId = Number(firstActive?.id || 0) || null;
      return firstActive || null;
    }

    function renderSharedCameraList(rows) {
      const listEl = $("sharedCameraList");
      const countEl = $("sharedCameraCount");
      if (!listEl || !countEl) return;
      const list = Array.isArray(rows) ? rows : [];
      countEl.textContent = countWithUnit(list.length);
      if (!list.length) {
        listEl.innerHTML = `<div class='dashboard-camera-placeholder'>${escapeHtml(t("shared_camera.list.empty"))}</div>`;
        return;
      }
      listEl.innerHTML = list.map((item) => {
        const cameraId = Number(item?.id || 0);
        const active = cameraId > 0 && cameraId === Number(sharedCameraSelectedId || 0);
        const description = String(item?.description || "").trim() || t("shared_camera.state.no_description");
        const stateText = Boolean(item?.is_active) ? t("shared_camera.state.active") : t("shared_camera.state.inactive");
        return `
          <button class="shared-camera-list-item${active ? " active" : ""}" type="button" data-shared-camera-id="${cameraId}">
            <strong>${escapeHtml(item?.camera_name || "-")}</strong>
            <div class="mini">${escapeHtml(description)}</div>
            <div class="mini">${escapeHtml(stateText)}</div>
          </button>
        `;
      }).join("");
    }

    function renderSharedCameraPreview(rows) {
      const titleEl = $("sharedCameraTitle");
      const metaEl = $("sharedCameraMeta");
      const bodyEl = $("sharedCameraPreviewBody");
      if (!titleEl || !metaEl || !bodyEl) return;
      const selected = ensureSharedCameraSelection(rows);
      if (!selected) {
        titleEl.textContent = t("shared_camera.empty.title");
        metaEl.textContent = t("shared_camera.empty.meta");
        bodyEl.innerHTML = `<div class='dashboard-camera-placeholder'>${escapeHtml(t("shared_camera.list.empty"))}</div>`;
        return;
      }
      const title = String(selected.camera_name || "").trim() || t("shared_camera.preview.title");
      const description = String(selected.description || "").trim() || t("shared_camera.state.no_description");
      const streamUrl = String(selected.stream_url || "").trim();
      const snapshotEnabled = Boolean(selected.snapshot_url);
      const metaBits = [
        description,
        Boolean(selected.is_active) ? t("shared_camera.state.active") : t("shared_camera.state.inactive"),
        /^https?:\/\//i.test(streamUrl) ? t("shared_camera.state.stream_preview") : snapshotEnabled ? t("shared_camera.state.snapshot_preview") : streamUrl ? t("shared_camera.state.external_stream_only") : t("shared_camera.state.no_preview"),
      ];
      titleEl.textContent = title;
      metaEl.textContent = metaBits.filter((value) => String(value || "").trim()).join(" · ");
      if (!selected.is_active) {
        bodyEl.innerHTML = `<div class='dashboard-camera-placeholder'>${escapeHtml(t("shared_camera.preview.inactive_body"))}</div>`;
        return;
      }
      if (/^https?:\/\//i.test(streamUrl)) {
        bodyEl.innerHTML = `<iframe class="shared-camera-stream-frame" src="${escapeHtml(streamUrl)}" title="${escapeHtml(title)}" loading="lazy"></iframe>`;
        return;
      }
      if (snapshotEnabled) {
        bodyEl.innerHTML = `<img class="dashboard-camera-image" src="/cabinet-cameras/${encodeURIComponent(String(selected.id))}/snapshot?ts=${Date.now()}" alt="${escapeHtml(title)}" />`;
        return;
      }
      if (/^rtsps?:\/\//i.test(streamUrl)) {
        bodyEl.innerHTML = `<div class='dashboard-camera-placeholder'>${escapeHtml(t("shared_camera.preview.rtsp_only_body"))}</div>`;
        return;
      }
      bodyEl.innerHTML = `<div class='dashboard-camera-placeholder'>${escapeHtml(t("shared_camera.preview.load_failed_body"))}</div>`;
    }

    function renderSharedCameraPage() {
      renderSharedCameraList(opsCameraItems);
      renderSharedCameraPreview(opsCameraItems);
    }

    async function discoverOpsCameras() {
      try {
        setStatus("opsCameraStatus", "ok", t("ops.camera.status.discover_loading"));
        const res = await fetch("/cabinet-cameras/discover?timeout_ms=2500");
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("ops.camera.status.discover_failed")));
        opsCameraDiscoverItems = Array.isArray(data) ? data : [];
        renderOpsCameraDiscoverTable(opsCameraDiscoverItems);
        setStatus("opsCameraStatus", "ok", t("ops.camera.status.discover_loaded", { count: countWithUnit(opsCameraDiscoverItems.length) }));
      } catch (err) {
        opsCameraDiscoverItems = [];
        renderOpsCameraDiscoverTable([]);
        setStatus("opsCameraStatus", "err", errorMessageText(err, t("ops.camera.status.discover_failed")));
      }
    }

    async function testOpsCameraConnection() {
      const onvifDeviceUrl = $("opsCameraOnvifUrl").value.trim();
      if (!onvifDeviceUrl) {
        setStatus("opsCameraStatus", "err", t("ops.camera.status.onvif_url_required"));
        return;
      }
      const payload = {
        camera_id: opsCameraSelectedId ? Number(opsCameraSelectedId) : null,
        onvif_device_url: onvifDeviceUrl,
        username: $("opsCameraUsername").value.trim() || null,
        password: $("opsCameraPassword").value || null,
      };
      try {
        const advanced = $("opsCameraAdvancedSettings");
        if (advanced) advanced.open = true;
        setStatus("opsCameraStatus", "ok", t("ops.camera.status.test_loading"));
        const res = await fetch("/cabinet-cameras/test-onvif", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("ops.camera.status.test_failed")));
        if (data.snapshot_url && !$("opsCameraSnapshotUrl").value.trim()) {
          $("opsCameraSnapshotUrl").value = String(data.snapshot_url || "");
        }
        if (data.stream_url && !$("opsCameraStreamUrl").value.trim()) {
          $("opsCameraStreamUrl").value = String(data.stream_url || "");
        }
        if (!$("opsCameraName").value.trim()) {
          const inferredName = [data.manufacturer, data.model].filter((v) => String(v || "").trim()).join(" ");
          if (inferredName) $("opsCameraName").value = inferredName;
        }
        const noteParts = [
          String(data.manufacturer || "").trim(),
          String(data.model || "").trim(),
          String(data.serial_number || "").trim() ? `S/N ${String(data.serial_number || "").trim()}` : "",
        ].filter((v) => v);
        if (noteParts.length && !$("opsCameraDescription").value.trim()) {
          $("opsCameraDescription").value = noteParts.join(" | ");
        }
        const statusParts = [];
        if (data.snapshot_url) statusParts.push(t("ops.camera.status.test_fill_snapshot"));
        if (data.stream_url) statusParts.push(t("ops.camera.status.test_fill_stream"));
        if (!statusParts.length) {
          statusParts.push((data.media_service_url || data.device_service_url) ? t("ops.camera.status.test_connection_verified") : t("ops.camera.status.test_device_info_verified"));
        }
        setStatus("opsCameraStatus", "ok", t("ops.camera.status.test_success", { details: statusParts.join(" / ") }));
      } catch (err) {
        setStatus("opsCameraStatus", "err", errorMessageText(err, t("ops.camera.status.test_failed")));
      }
    }

    async function loadOpsCameras({ silent = false } = {}) {
      try {
        const res = await fetch("/cabinet-cameras");
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || "camera list load failed");
        opsCameraItems = Array.isArray(data) ? data : [];
        renderOpsCameraTable(opsCameraItems);
        renderSharedCameraPage();
        if (!silent) {
          setStatus("opsCameraStatus", "ok", t("ops.camera.status.list_loaded", { count: countWithUnit(opsCameraItems.length) }));
          setStatus("sharedCameraStatus", "ok", t("ops.camera.status.list_loaded_shared", { count: countWithUnit(opsCameraItems.length) }));
        }
      } catch (err) {
        opsCameraItems = [];
        renderOpsCameraTable([]);
        renderSharedCameraPage();
        if (!silent) {
          setStatus("opsCameraStatus", "err", errorMessageText(err, t("ops.camera.status.list_failed")));
          setStatus("sharedCameraStatus", "err", errorMessageText(err, t("ops.camera.status.list_failed")));
        }
      }
    }

    async function saveOpsCamera() {
      const cameraName = $("opsCameraName").value.trim();
      const description = $("opsCameraDescription").value.trim();
      if (!cameraName) {
        setStatus("opsCameraStatus", "err", t("ops.camera.status.name_required"));
        return;
      }
      $("opsCameraCabinetName").value = $("opsCameraCabinetName").value.trim() || cameraName;
      const payload = {
        camera_id: opsCameraSelectedId ? Number(opsCameraSelectedId) : null,
        cabinet_name: $("opsCameraCabinetName").value.trim() || null,
        camera_name: cameraName,
        description: description || null,
        onvif_device_url: $("opsCameraOnvifUrl").value.trim() || null,
        snapshot_url: $("opsCameraSnapshotUrl").value.trim() || null,
        stream_url: $("opsCameraStreamUrl").value.trim() || null,
        username: $("opsCameraUsername").value.trim() || null,
        password: $("opsCameraPassword").value || null,
        notes: null,
        is_active: $("opsCameraActive").checked,
      };
      try {
        setStatus("opsCameraStatus", "ok", t("ops.camera.status.saving"));
        const res = await fetch("/cabinet-cameras", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("ops.camera.status.save_failed")));
        await loadOpsCameras({ silent: true });
        fillOpsCameraForm(data);
        setStatus("opsCameraStatus", "ok", t("ops.camera.status.saved", { camera: String(data.camera_name || "-") }));
      } catch (err) {
        setStatus("opsCameraStatus", "err", errorMessageText(err, t("ops.camera.status.save_failed")));
      }
    }

    async function deleteOpsCamera() {
      const cameraId = opsCameraSelectedId ? Number(opsCameraSelectedId) : 0;
      if (cameraId <= 0) {
        setStatus("opsCameraStatus", "err", t("ops.camera.status.delete_select_first"));
        return;
      }
      const item = opsCameraItems.find((row) => Number(row.id) === cameraId) || null;
      const ok = window.confirm(t("ops.camera.confirm_delete", {
        camera: String(item?.camera_name || "-"),
        description: String(item?.description || "-"),
      }));
      if (!ok) return;
      try {
        setStatus("opsCameraStatus", "ok", t("ops.camera.status.deleting"));
        const res = await fetch(`/cabinet-cameras/${encodeURIComponent(String(cameraId))}`, { method: "DELETE" });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("ops.camera.status.delete_failed")));
        resetOpsCameraForm();
        await loadOpsCameras({ silent: true });
        setStatus("opsCameraStatus", "ok", t("ops.camera.status.deleted"));
      } catch (err) {
        setStatus("opsCameraStatus", "err", errorMessageText(err, t("ops.camera.status.delete_failed")));
      }
    }

    async function loadStorageSlots() {
      try {
        const res = await fetch("/storage-slots");
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("ops.slot.status.list_failed")));

        storageSlotCache = Array.isArray(data) ? data : [];
        renderOpsCabinetTable(storageSlotCache);
        renderOpsSlotTable(storageSlotCache);

        const slotSel = $("slotId");
        const quickSlotSel = $("quickSlotId");
        const editSlotSel = $("editSlotId");
        const goodsSearchSlotSel = $("goodsSearchStorageSlotId");
        const goodsManageSlotSel = $("goodsManageSlotId");
        const goodsRegisterSlotSel = $("goodsRegisterSlotId");
        slotSel.innerHTML = `<option value="">${escapeHtml(t("common.unspecified"))}</option>`;
        quickSlotSel.innerHTML = `<option value="">${escapeHtml(t("common.unspecified"))}</option>`;
        editSlotSel.innerHTML = `<option value="">${escapeHtml(t("common.unspecified"))}</option>`;
        if (goodsSearchSlotSel) goodsSearchSlotSel.innerHTML = `<option value="">${escapeHtml(t("common.all"))}</option>`;
        if (goodsManageSlotSel) goodsManageSlotSel.innerHTML = `<option value="">${escapeHtml(t("common.unspecified"))}</option>`;
        if (goodsRegisterSlotSel) goodsRegisterSlotSel.innerHTML = `<option value="">${escapeHtml(t("common.unspecified"))}</option>`;
        for (const slot of storageSlotCache) {
          const opt = document.createElement("option");
          opt.value = String(slot.id);
          opt.textContent = `${slot.id} | ${storageSlotDisplayLabel(slot)} | ${dashboardSizeGroupLabel(slot.allowed_size_group)}`;
          slotSel.appendChild(opt);
          quickSlotSel.appendChild(opt.cloneNode(true));
          editSlotSel.appendChild(opt.cloneNode(true));
          if (goodsSearchSlotSel) goodsSearchSlotSel.appendChild(opt.cloneNode(true));
          if (goodsManageSlotSel) goodsManageSlotSel.appendChild(opt.cloneNode(true));
          if (goodsRegisterSlotSel) goodsRegisterSlotSel.appendChild(opt.cloneNode(true));
        }
      } catch (err) {
        setStatus("opsCabinetStatus", "err", errorMessageText(err, t("ops.slot.status.list_failed")));
        setStatus("opsSlotStatus", "err", errorMessageText(err, t("ops.slot.status.list_failed")));
        setStatus("quickCreateStatus", "err", errorMessageText(err, t("ops.slot.status.list_failed")));
        setStatus("createStatus", "err", errorMessageText(err, t("ops.slot.status.list_failed")));
        setStatus("homeEditStatus", "err", errorMessageText(err, t("ops.slot.status.list_failed")));
        setStatus("goodsManageStatusLine", "err", errorMessageText(err, t("ops.slot.status.list_failed")));
        setStatus("goodsRegisterStatusLine", "err", errorMessageText(err, t("ops.slot.status.list_failed")));
      }
    }

    function switchGoodsMode(mode) {
      const nextMode = ["search", "manage", "register"].includes(String(mode || "").trim())
        ? String(mode || "").trim()
        : "search";
      goodsMode = nextMode;
      syncGoodsModeUi();
    }

    async function openGoodsItemForManage(goodsItemId, options = {}) {
      const targetId = Number(goodsItemId || 0);
      if (targetId <= 0) return;
      try {
        setStatus("goodsManageStatusLine", "ok", t("collectibles.manage.status.loading", { id: targetId }));
        const res = await fetch(`/goods-items/${targetId}`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("collectibles.manage.status.load_failed"));
        applyGoodsManageItem(data);
        if (options.switchMode !== false) {
          switchGoodsMode("manage");
        }
      } catch (err) {
        setStatus("goodsManageStatusLine", "err", errorMessageText(err, t("collectibles.manage.status.load_failed")));
      }
    }

    async function loadGoodsSearchResults(options = {}) {
      try {
        goodsSearchLoading = true;
        renderGoodsSearchResults();
        if (!options.silent) {
          setStatus("goodsSearchStatus", "ok", t("collectibles.status.search.loading"));
        }
        const params = new URLSearchParams();
        const queryText = $("goodsSearchQuery").value.trim();
        const category = $("goodsSearchCategory").value;
        const albumMasterId = Number($("goodsSearchAlbumMasterId").value || 0);
        const status = $("goodsSearchStatusFilter").value || "";
        const domainCode = $("goodsSearchDomainCode").value || "";
        const storageSlotId = Number($("goodsSearchStorageSlotId").value || 0);
        const linkedState = $("goodsSearchLinkedState").value || "ANY";
        const collectibleRelationState = $("goodsSearchCollectibleRelationState").value || "ANY";
        const collectibleRelationType = $("goodsSearchCollectibleRelationType").value || "";
        if (queryText) params.set("q", queryText);
        if (category) params.set("category", category);
        if (status) params.set("status", status);
        if (domainCode) params.set("domain_code", domainCode);
        if (albumMasterId > 0) params.set("album_master_id", String(albumMasterId));
        if (storageSlotId > 0) params.set("storage_slot_id", String(storageSlotId));
        if (linkedState) params.set("linked_state", linkedState);
        if (collectibleRelationState) params.set("collectible_relation_state", collectibleRelationState);
        if (collectibleRelationType) params.set("collectible_relation_type", collectibleRelationType);
        params.set("limit", "80");
        params.set("offset", "0");
        const res = await fetch(`/goods-items?${params.toString()}`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("collectibles.status.search.failed"));
        goodsSearchResults = Array.isArray(data.items) ? data.items : [];
        goodsSearchTotalCount = Number(data.total_count || goodsSearchResults.length || 0);
        renderGoodsSearchResults();
        if (!options.silent) {
          setStatus("goodsSearchStatus", "ok", t("collectibles.status.search.complete", { count: formatCount(goodsSearchTotalCount) }));
        }
      } catch (err) {
        goodsSearchResults = [];
        goodsSearchTotalCount = 0;
        renderGoodsSearchResults();
        setStatus("goodsSearchStatus", "err", errorMessageText(err, t("collectibles.status.search.failed")));
      } finally {
        goodsSearchLoading = false;
        renderGoodsSearchResults();
      }
    }

    async function searchGoodsAlbumMasterTargets() {
      const query = $("goodsManageAlbumMasterQuery").value.trim();
      if (!query) {
        setHtmlIfPresent("goodsManageAlbumMasterResults", `<div class='mini muted'>${escapeHtml(t("collectibles.mapping.query_empty"))}</div>`);
        return;
      }
      try {
        setStatus("goodsManageMappingStatus", "ok", t("collectibles.mapping.status.lookup_progress"));
        const res = await fetch(`/goods-targets?kind=album_master&q=${encodeURIComponent(query)}&limit=12`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("collectibles.mapping.status.lookup_failed")));
        renderGoodsAlbumMasterTargetResults(Array.isArray(data.items) ? data.items : []);
        setStatus("goodsManageMappingStatus", "ok", t("collectibles.mapping.status.lookup_complete"));
      } catch (err) {
        renderGoodsAlbumMasterTargetResults([]);
        setStatus("goodsManageMappingStatus", "err", errorMessageText(err, t("collectibles.mapping.status.lookup_failed")));
      }
    }

    async function searchGoodsCollectibleTargets() {
      const goodsItemId = Number(goodsSelectedItemId || $("goodsManageId").value || 0);
      const query = $("goodsManageCollectibleQuery").value.trim();
      if (goodsItemId <= 0) {
        setStatus("goodsManageRelationStatus", "err", t("collectibles.mapping.status.select_first"));
        return;
      }
      if (!query) {
        setHtmlIfPresent("goodsManageCollectibleResults", `<div class='mini muted'>${escapeHtml(t("collectibles.mapping.query_empty"))}</div>`);
        return;
      }
      try {
        setStatus("goodsManageRelationStatus", "ok", t("collectibles.mapping.status.lookup_progress"));
        const params = new URLSearchParams({
          kind: "collectible",
          q: query,
          goods_item_id: String(goodsItemId),
          limit: "12",
        });
        const res = await fetch(`/goods-targets?${params.toString()}`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("collectibles.mapping.status.lookup_failed")));
        renderGoodsCollectibleTargetResults(Array.isArray(data.items) ? data.items : []);
        setStatus("goodsManageRelationStatus", "ok", t("collectibles.mapping.status.lookup_complete"));
      } catch (err) {
        renderGoodsCollectibleTargetResults([]);
        setStatus("goodsManageRelationStatus", "err", errorMessageText(err, t("collectibles.mapping.status.lookup_failed")));
      }
    }

    function addUniqueGoodsMappingValue(type, rawValue, extra = {}) {
      const value = String(rawValue || "").trim();
      if (!value) return;
      if (type === "artist") {
        if (!goodsManageArtistMappings.includes(value)) goodsManageArtistMappings.push(value);
      } else if (type === "label") {
        if (!goodsManageLabelMappings.includes(value)) goodsManageLabelMappings.push(value);
      } else if (type === "album_master") {
        const albumMasterId = Number(extra.album_master_id || rawValue || 0);
        if (albumMasterId <= 0) return;
        if (!goodsManageAlbumMasterMappings.some((row) => Number(row.album_master_id || 0) === albumMasterId)) {
          goodsManageAlbumMasterMappings.push({
            album_master_id: albumMasterId,
            title: String(extra.title || value || `album_master_id=${albumMasterId}`).trim(),
            artist_or_brand: String(extra.artist_or_brand || "").trim() || null,
          });
        }
      }
      renderGoodsManageMappings();
    }

    async function saveGoodsManageItem() {
      const goodsItemId = Number(goodsSelectedItemId || $("goodsManageId").value || 0);
      if (goodsItemId <= 0) {
        setStatus("goodsManageStatusLine", "err", t("collectibles.manage.status.select_first"));
        return;
      }
      try {
        const payload = {
          category: $("goodsManageCategory").value,
          goods_name: $("goodsManageName").value.trim(),
          quantity: Math.max(1, Number($("goodsManageQuantity").value || 1)),
          description: $("goodsManageDescription").value.trim() || null,
          size_group: $("goodsManageSizeGroup").value,
          storage_slot_id: $("goodsManageSlotId").value ? Number($("goodsManageSlotId").value) : null,
          status: $("goodsManageStatus").value,
          domain_code: $("goodsManageDomainCode").value || null,
          memory_note: $("goodsManageMemoryNote").value.trim() || null,
          image_urls: splitLineList($("goodsManageImageUrls").value),
        };
        setStatus("goodsManageStatusLine", "ok", t("collectibles.manage.status.save_progress"));
        const res = await fetch(`/goods-items/${goodsItemId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("collectibles.manage.status.save_failed"));
        goodsSearchResults = goodsSearchResults.map((row) => Number(row.id || 0) === goodsItemId ? data : row);
        applyGoodsManageItem(data);
        renderGoodsSearchResults();
        setStatus("goodsManageStatusLine", "ok", t("collectibles.manage.status.save_complete", { id: goodsItemId }));
      } catch (err) {
        setStatus("goodsManageStatusLine", "err", errorMessageText(err, t("collectibles.manage.status.save_failed")));
      }
    }

    async function deleteGoodsManageItem() {
      const goodsItemId = Number(goodsSelectedItemId || $("goodsManageId").value || 0);
      if (goodsItemId <= 0) {
        setStatus("goodsManageStatusLine", "err", t("collectibles.manage.status.delete_select_first"));
        return;
      }
      const goodsName = String($("goodsManageName").value || goodsSelectedItem?.goods_name || "-").trim() || "-";
      const ok = window.confirm(t("collectibles.manage.status.delete_confirm", { name: goodsName }));
      if (!ok) return;
      try {
        setStatus("goodsManageStatusLine", "ok", t("collectibles.manage.status.delete_progress"));
        const res = await fetch(`/goods-items/${goodsItemId}`, { method: "DELETE" });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("collectibles.manage.status.delete_failed"));
        goodsSearchResults = goodsSearchResults.filter((row) => Number(row.id || 0) !== goodsItemId);
        goodsSearchTotalCount = Math.max(0, goodsSearchTotalCount - 1);
        resetGoodsManageSelection();
        switchGoodsMode("search");
        renderGoodsSearchResults();
        setStatus("goodsSearchStatus", "ok", t("collectibles.manage.status.delete_complete", { name: goodsName }));
      } catch (err) {
        setStatus("goodsManageStatusLine", "err", errorMessageText(err, t("collectibles.manage.status.delete_failed")));
      }
    }

    async function saveGoodsManageMappings() {
      const goodsItemId = Number(goodsSelectedItemId || $("goodsManageId").value || 0);
      if (goodsItemId <= 0) {
        setStatus("goodsManageMappingStatus", "err", t("collectibles.mapping.status.select_first"));
        return;
      }
      try {
        const payload = {
          album_master_ids: goodsManageAlbumMasterMappings.map((row) => Number(row.album_master_id || 0)).filter((value) => value > 0),
          artist_names: goodsManageArtistMappings.filter((row) => String(row || "").trim()),
          label_names: goodsManageLabelMappings.filter((row) => String(row || "").trim()),
        };
        setStatus("goodsManageMappingStatus", "ok", t("collectibles.mapping.status.save_progress"));
        const res = await fetch(`/goods-items/${goodsItemId}/mappings`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("collectibles.mapping.status.save_failed")));
        goodsSearchResults = goodsSearchResults.map((row) => Number(row.id || 0) === goodsItemId ? data : row);
        applyGoodsManageItem(data);
        renderGoodsSearchResults();
        setStatus("goodsManageMappingStatus", "ok", t("collectibles.mapping.status.save_complete", { id: goodsItemId }));
      } catch (err) {
        setStatus("goodsManageMappingStatus", "err", errorMessageText(err, t("collectibles.mapping.status.save_failed")));
      }
    }

    async function saveGoodsManageRelations() {
      const goodsItemId = Number(goodsSelectedItemId || $("goodsManageId").value || 0);
      if (goodsItemId <= 0) {
        setStatus("goodsManageRelationStatus", "err", t("collectibles.mapping.status.select_first"));
        return;
      }
      try {
        const payload = {
          relations: goodsManageCollectibleRelations.map((row, index) => ({
            relation_type: String(row.relation_type || "").trim().toUpperCase(),
            linked_goods_item_id: Number(row.linked_goods_item_id || 0),
            note: String(row.note || "").trim() || null,
            display_order: Number(row.display_order ?? index) || index,
          })).filter((row) => row.linked_goods_item_id > 0 && row.relation_type),
        };
        setStatus("goodsManageRelationStatus", "ok", t("collectibles.mapping.status.save_progress"));
        const res = await fetch(`/goods-items/${goodsItemId}/relations`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("collectibles.mapping.status.save_failed")));
        goodsSearchResults = goodsSearchResults.map((row) => Number(row.id || 0) === goodsItemId ? data : row);
        applyGoodsManageItem(data);
        renderGoodsSearchResults();
        setStatus("goodsManageRelationStatus", "ok", t("collectibles.mapping.status.save_complete", { id: goodsItemId }));
      } catch (err) {
        setStatus("goodsManageRelationStatus", "err", errorMessageText(err, t("collectibles.mapping.status.save_failed")));
      }
    }

    async function createGoodsRegisterItem() {
      try {
        const payload = {
          category: $("goodsRegisterCategory").value,
          goods_name: $("goodsRegisterName").value.trim(),
          quantity: Math.max(1, Number($("goodsRegisterQuantity").value || 1)),
          description: $("goodsRegisterDescription").value.trim() || null,
          size_group: $("goodsRegisterSizeGroup").value,
          storage_slot_id: $("goodsRegisterSlotId").value ? Number($("goodsRegisterSlotId").value) : null,
          status: $("goodsRegisterStatus").value,
          domain_code: $("goodsRegisterDomainCode").value || null,
          memory_note: $("goodsRegisterMemoryNote").value.trim() || null,
          image_urls: splitLineList($("goodsRegisterImageUrls").value),
          album_master_ids: $("goodsRegisterAlbumMasterId").value ? [Number($("goodsRegisterAlbumMasterId").value)] : [],
          linked_owned_item_id: $("goodsRegisterLinkedOwnedItemId")?.value?.trim()
            ? Number($("goodsRegisterLinkedOwnedItemId").value)
            : null,
          artist_names: splitCommaList($("goodsRegisterArtistNames").value),
          label_names: splitCommaList($("goodsRegisterLabelNames").value),
        };
        setStatus("goodsRegisterStatusLine", "ok", t("collectibles.register.status.save_progress"));
        const res = await fetch("/goods-items", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("collectibles.register.status.save_failed"));
        resetGoodsRegisterForm({ preserveStatus: true });
        setStatus("goodsRegisterStatusLine", "ok", t("collectibles.register.status.save_complete", { id: data.id }));
        goodsSearchResults = [data, ...goodsSearchResults.filter((row) => Number(row.id || 0) !== Number(data.id || 0))];
        goodsSearchTotalCount += 1;
        renderGoodsSearchResults();
        switchGoodsMode("manage");
        applyGoodsManageItem(data);
      } catch (err) {
        setStatus("goodsRegisterStatusLine", "err", errorMessageText(err, t("collectibles.register.status.save_failed")));
      }
    }

    function openGoodsRegisterFromManageContext() {
      const { masterId, artist } = resolveHomeLinkedGoodsMasterContext();
      openAdminConsole("collectibles");
      switchGoodsMode("register");
      resetGoodsRegisterForm({ preserveStatus: true });
      if (masterId > 0) {
        $("goodsRegisterAlbumMasterId").value = String(masterId);
      }
      if (artist) {
        $("goodsRegisterArtistNames").value = artist;
      }
      setStatus(
        "goodsRegisterStatusLine",
        "ok",
        masterId > 0
          ? t("collectibles.register.status.start_linked", { id: masterId })
          : t("collectibles.register.status.start_independent")
      );
    }

    async function saveOpsStorageCabinet() {
      const cabinetName = $("opsCabinetName").value.trim();
      const selectedCabinetName = $("opsCabinetSelectedName").value.trim();
      const currentSummary = selectedCabinetName ? getOpsCabinetSummary(selectedCabinetName) : null;
      if (!cabinetName) {
        setStatus("opsCabinetStatus", "err", t("ops.cabinet.status.name_required"));
        return;
      }

      const payload = {
        cabinet_name: cabinetName,
        cabinet_domain_code: $("opsCabinetDomainCode").value || null,
        cabinet_group_name: $("opsCabinetGroupName").value.trim() || null,
        cabinet_group_order: Number($("opsCabinetGroupOrder").value || 0) || null,
        floor_count: Number($("opsCabinetFloorCount").value || 0),
        cell_count: Number($("opsCabinetCellCount").value || 0),
        floor_start: Number($("opsCabinetFloorStart").value || 0),
        cell_start: Number($("opsCabinetCellStart").value || 0),
        allowed_size_group: $("opsCabinetSizeGroup").value,
        cabinet_sort_policy: $("opsCabinetSortPolicy").value,
        max_thickness_mm: Number($("opsCabinetSlotCapacityMm").value || 0),
      };
      if (payload.floor_count <= 0 || payload.cell_count <= 0) {
        setStatus("opsCabinetStatus", "err", t("ops.cabinet.status.count_invalid"));
        return;
      }
      if (payload.floor_start <= 0 || payload.cell_start <= 0) {
        setStatus("opsCabinetStatus", "err", t("ops.cabinet.status.start_invalid"));
        return;
      }
      if (payload.max_thickness_mm < 0) {
        setStatus("opsCabinetStatus", "err", t("ops.cabinet.status.slot_capacity_invalid"));
        return;
      }
      if (currentSummary && !currentSummary.can_safe_edit) {
        setStatus("opsCabinetStatus", "err", t("ops.cabinet.status.unsafe_structure"));
        return;
      }
      if (currentSummary && cabinetName !== selectedCabinetName) {
        setStatus("opsCabinetStatus", "err", t("ops.cabinet.status.safe_edit_name_locked"));
        return;
      }
      if (currentSummary) {
        if (payload.floor_start !== currentSummary.floor_start || payload.cell_start !== currentSummary.cell_start) {
          setStatus("opsCabinetStatus", "err", t("ops.cabinet.status.safe_edit_start_locked"));
          return;
        }
        if (payload.floor_count < currentSummary.floor_count || payload.cell_count < currentSummary.cell_count) {
          setStatus("opsCabinetStatus", "err", t("ops.cabinet.status.safe_edit_count_locked"));
          return;
        }
        if (payload.allowed_size_group !== currentSummary.size_group_code) {
          setStatus("opsCabinetStatus", "err", t("ops.cabinet.status.safe_edit_size_locked"));
          return;
        }
      }

      try {
        setStatus("opsCabinetStatus", "ok", currentSummary ? t("ops.cabinet.status.saving_update") : t("ops.cabinet.status.saving_create"));
        const res = await fetch("/storage-cabinets/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || (currentSummary ? t("ops.cabinet.status.save_failed_update") : t("ops.cabinet.status.save_failed_create")));
        setStatus(
          "opsCabinetStatus",
          "ok",
          currentSummary
            ? t("ops.cabinet.status.save_done_update", {
                cabinet: String(data.cabinet_name || "-"),
                created: formatCount(data.created_count),
                updated: formatCount(data.updated_count),
                total: formatCount(data.total_slot_count),
              })
            : t("ops.cabinet.status.save_done_create", {
                cabinet: String(data.cabinet_name || "-"),
                created: formatCount(data.created_count),
                updated: formatCount(data.updated_count),
                total: formatCount(data.total_slot_count),
              })
        );
        $("opsSlotCabinetName").value = String(data.cabinet_name || "");
        $("opsSlotSizeGroup").value = $("opsCabinetSizeGroup").value;
        await loadStorageSlots();
        if (currentSummary) {
          const refreshedSummary = getOpsCabinetSummary(cabinetName);
          fillOpsCabinetForm(refreshedSummary || currentSummary);
        }
        await loadHomeDashboard();
      } catch (err) {
        setStatus("opsCabinetStatus", "err", err.message);
      }
    }

    async function deleteOpsStorageCabinet() {
      const cabinetName = $("opsCabinetName").value.trim();
      if (!cabinetName) {
        setStatus("opsCabinetStatus", "err", t("ops.cabinet.status.delete_select_first"));
        return;
      }
      const summary = summarizeStorageCabinets(storageSlotCache)
        .find((row) => String(row.cabinet_name || "") === cabinetName);
      const slotCount = Number(summary?.slot_count || 0);
      const ok = window.confirm(t("ops.cabinet.confirm_delete", { cabinet: cabinetName, slot_count: slotCount }));
      if (!ok) {
        setStatus("opsCabinetStatus", "ok", t("ops.cabinet.status.delete_cancelled"));
        return;
      }

      try {
        setStatus("opsCabinetStatus", "ok", t("ops.cabinet.status.deleting"));
        const params = new URLSearchParams({ cabinet_name: cabinetName });
        const res = await fetch(`/storage-cabinets?${params.toString()}`, { method: "DELETE" });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("ops.cabinet.status.delete_failed"));
        setStatus(
          "opsCabinetStatus",
          "ok",
          t("ops.cabinet.status.delete_done", {
            cabinet: data.cabinet_name,
            slot_count: formatCount(data.deleted_slot_count),
            item_count: formatCount(data.unassigned_item_count),
          })
        );
        resetOpsCabinetForm();
        resetOpsSlotForm();
        await loadStorageSlots();
        await loadHomeDashboard();
      } catch (err) {
        setStatus("opsCabinetStatus", "err", err.message);
      }
    }

    async function saveOpsStorageSlot() {
      const cabinetName = $("opsSlotCabinetName").value.trim();
      if (!cabinetName) {
        setStatus("opsSlotStatus", "err", t("ops.slot.status.cabinet_required"));
        return;
      }
      const currentSlotId = $("opsSlotId").value ? Number($("opsSlotId").value) : null;
      const currentSlot = currentSlotId
        ? storageSlotCache.find((item) => Number(item.id) === currentSlotId)
        : null;
      const cabinetSummary = summarizeStorageCabinets(storageSlotCache)
        .find((item) => String(item.cabinet_name || "").trim() === cabinetName);
      const payload = {
        slot_id: currentSlotId,
        cabinet_name: cabinetName,
        column_code: $("opsSlotColumnCode").value.trim() || null,
        cell_code: $("opsSlotCellCode").value.trim() || null,
        allowed_size_group: $("opsSlotSizeGroup").value,
        cabinet_sort_policy: String(
          currentSlot?.cabinet_sort_policy ||
          cabinetSummary?.cabinet_sort_policy ||
          $("opsCabinetSortPolicy")?.value ||
          "ARTIST_RELEASE_TITLE"
        ),
        is_overflow_zone: false,
      };
      try {
        setStatus("opsSlotStatus", "ok", t("ops.slot.status.saving"));
        const res = await fetch("/storage-slots", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("ops.slot.status.save_failed")));
        setStatus("opsSlotStatus", "ok", t("ops.slot.status.saved", {
          slot: storageSlotDisplayLabel(data),
          slot_code: data.slot_code,
        }));
        await loadStorageSlots();
        await loadHomeDashboard();
        fillOpsSlotForm(data);
      } catch (err) {
        setStatus("opsSlotStatus", "err", errorMessageText(err, t("ops.slot.status.save_failed")));
      }
    }

    async function barcodeSearch() {
      const barcode = $("barcodeInput").value.trim();
      const selectedSource = String($("metaSourceFilter").value || "AUTO").trim().toUpperCase() || "AUTO";
      const requestSources = buildRegisterLookupSourceCandidates(selectedSource);
      const loadingStatusText = t("media.register.api_lookup.status.lookup_loading");
      if (!barcode) {
        renderRegisterLookupProviderStatusBadges([]);
        setStatus("barcodeStatus", "err", t("media.register.api_lookup.status.enter_barcode"));
        return;
      }
      const barcodeToken = normalizeBarcodeLookupToken(barcode);
      if (!barcodeToken) {
        renderRegisterLookupProviderStatusBadges([]);
        setStatus("barcodeStatus", "err", t("media.register.api_lookup.status.invalid_barcode"));
        return;
      }
      if (adminBarcodeConfirmToken && barcodeToken !== adminBarcodeConfirmToken) {
        clearAdminBarcodeConfirmation({ keepInput: true });
      }
      const now = Date.now();
      if (barcodeSearchInFlight) {
        barcodeSearchPendingToken = barcodeToken;
        barcodeSearchPendingValue = barcode;
        setStatus("barcodeStatus", "ok", t("media.register.api_lookup.status.lookup_inflight"));
        return;
      }
      if (barcodeSearchLastToken === barcodeToken && now - barcodeSearchLastTriggeredAt < BARCODE_SCAN_COOLDOWN_MS) {
        setStatus("barcodeStatus", "ok", t("media.register.api_lookup.status.lookup_duplicate_skipped"));
        return;
      }
      barcodeSearchInFlight = true;
      barcodeSearchLastToken = barcodeToken;
      barcodeSearchLastTriggeredAt = now;
      renderRegisterLookupProviderStatusBadges([]);
      setStatus("barcodeStatus", "ok", loadingStatusText);

      const payload = {
        barcode,
        category: $("category").value,
        limit: Math.max(1, Math.min(20, Number($("barcodeLimit").value || 5))
      )};

      try {
        let candidates = [];
        let usedSource = requestSources[0];
        let lastError = null;
        const providerStatusEntries = [];
        let fallbackMode = false;
        for (const source of requestSources) {
          const res = await fetchWithRetry("/ingest/barcode", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              ...payload,
              source,
            })
          }, {
            retries: 2,
            retryDelayMs: 250,
            onRetry: (attempt, total) => setStatus("barcodeStatus", "ok", retryingStatusText(loadingStatusText, attempt, total)),
          });
          const data = await safeJson(res);
          if (!res.ok) {
            if (res.status === 502 && selectedSource !== "AUTO") {
              providerStatusEntries.push({ kind: "unavailable", source });
              fallbackMode = true;
              lastError = new Error(responseDetailText(data, t("media.register.api_lookup.status.lookup_failed")));
              continue;
            }
            throw new Error(responseDetailText(data, t("media.register.api_lookup.status.lookup_failed")));
          }
          const nextCandidates = Array.isArray(data.candidates) ? data.candidates : [];
          usedSource = source;
          if (selectedSource !== "AUTO" && !fallbackMode && source === selectedSource) {
            candidates = nextCandidates;
            break;
          }
          if (nextCandidates.length) {
            candidates = nextCandidates;
            break;
          }
        }
        if (fallbackMode && candidates.length && usedSource !== selectedSource) {
          providerStatusEntries.push({ kind: "fallback_results", source: usedSource });
        }
        renderRegisterLookupProviderStatusBadges(providerStatusEntries);
        if (!candidates.length && lastError && providerStatusEntries.some((entry) => entry.kind === "unavailable")) throw lastError;

        renderBarcodeResults(candidates || []);
        if (Array.isArray(candidates) && candidates.length) {
          selectRegisterLookupCandidate(0, { focus: true, preventScroll: true, scroll: false });
          armAdminBarcodeConfirmation(barcodeToken, candidates[0]);
        } else {
          selectedCandidate = null;
          clearAdminBarcodeConfirmation({ keepInput: true });
        }
        setStatus(
          "barcodeStatus",
          "ok",
          Array.isArray(candidates) && candidates.length
            ? t("media.register.api_lookup.status.candidates_ready", { count: countWithUnit((candidates || []).length) })
            : t("media.register.api_lookup.status.no_candidates_register_direct")
        );
      } catch (err) {
        selectedCandidate = null;
        clearAdminBarcodeConfirmation({ keepInput: true });
        renderBarcodeResults([]);
        setStatus("barcodeStatus", "err", errorMessageText(err, t("media.register.api_lookup.status.lookup_failed")));
      } finally {
        barcodeSearchInFlight = false;
        const pendingToken = String(barcodeSearchPendingToken || "").trim();
        const pendingValue = String(barcodeSearchPendingValue || "").trim();
        barcodeSearchPendingToken = "";
        barcodeSearchPendingValue = "";
        if (pendingToken && pendingToken !== barcodeToken) {
          const input = $("barcodeInput");
          if (input) input.value = pendingValue;
          await barcodeSearch();
        }
      }
    }

    async function detectRegisterLookupCategoryMismatch(payload, source) {
      if (String(source || "").trim().toUpperCase() !== "MANIADB") return { categories: [], candidates: [] };
      const currentCategory = String(payload?.category || "").trim().toUpperCase();
      if (!MUSIC_CATEGORIES.has(currentCategory)) return { categories: [], candidates: [] };
      const res = await fetchWithRetry("/ingest/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...payload,
          category: null,
          source: "MANIADB",
        })
      }, {
        retries: 1,
        retryDelayMs: 200,
      });
      const data = await safeJson(res);
      if (!res.ok) return { categories: [], candidates: [] };
      const candidates = Array.isArray(data.candidates) ? data.candidates : [];
      const mismatchCandidates = candidates.filter((candidate) => {
        const inferredCategory = String(inferMusicCategoryFromMetadata(candidate) || "").trim().toUpperCase();
        return inferredCategory && inferredCategory !== currentCategory;
      });
      return {
        categories: Array.from(new Set(
          mismatchCandidates
            .map((candidate) => inferMusicCategoryFromMetadata(candidate))
            .filter((category) => MUSIC_CATEGORIES.has(String(category || "").trim().toUpperCase()))
            .map((category) => String(category || "").trim().toUpperCase())
        )),
        candidates: mismatchCandidates,
      };
    }

    async function querySearch() {
      const selectedSource = String($("metaSourceFilter").value || "AUTO").trim().toUpperCase() || "AUTO";
      const requestSources = buildRegisterLookupSourceCandidates(selectedSource);
      const payload = {
        category: $("category").value,
        query: $("querySourceRef").value.trim() || null,
        artist_or_brand: $("queryArtist").value.trim() || null,
        title: $("queryTitle").value.trim() || null,
        catalog_no: $("queryCatalog").value.trim() || null,
        limit: Math.max(1, Math.min(20, Number($("barcodeLimit").value || 5)))
      };
      const requestedCategory = payload.category;

      const hasAny = payload.query || payload.artist_or_brand || payload.title || payload.catalog_no;
      if (!hasAny) {
        renderRegisterLookupProviderStatusBadges([]);
        setStatus("barcodeStatus", "err", t("media.register.api_lookup.status.query_requires_term"));
        return;
      }
      clearAdminBarcodeConfirmation({ keepInput: true });

      $("barcodeCount").textContent = t("media.register.api_lookup.results.loading");
      $("barcodeResults").innerHTML = `<div class='muted'>${escapeHtml(t("media.register.api_lookup.results.loading"))}</div>`;
      const loadingStatusText = t("media.register.api_lookup.status.query_loading", { source: requestSources[0] });
      renderRegisterLookupProviderStatusBadges([]);
      setStatus("barcodeStatus", "ok", loadingStatusText);
      try {
        let items = [];
        let usedSource = requestSources[0];
        let lastError = null;
        const providerStatusEntries = [];
        let fallbackMode = false;
        for (const source of requestSources) {
          const res = await fetchWithRetry("/ingest/search", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              ...payload,
              source,
            })
          }, {
            retries: 2,
            retryDelayMs: 250,
            onRetry: (attempt, total) => setStatus("barcodeStatus", "ok", retryingStatusText(loadingStatusText, attempt, total)),
          });
          const data = await safeJson(res);
          if (!res.ok) {
            if (res.status === 502 && selectedSource !== "AUTO") {
              providerStatusEntries.push({ kind: "unavailable", source });
              fallbackMode = true;
              lastError = new Error(responseDetailText(data, t("media.register.api_lookup.status.lookup_failed")));
              continue;
            }
            throw new Error(responseDetailText(data, t("media.register.api_lookup.status.lookup_failed")));
          }
          const nextItems = Array.isArray(data.candidates) ? data.candidates : [];
          usedSource = source;
          if (selectedSource !== "AUTO" && !fallbackMode && source === selectedSource) {
            items = nextItems;
            break;
          }
          if (nextItems.length) {
            items = nextItems;
            break;
          }
        }
        if (fallbackMode && items.length && usedSource !== selectedSource) {
          providerStatusEntries.push({ kind: "fallback_results", source: usedSource });
        }
        renderRegisterLookupProviderStatusBadges(providerStatusEntries);
        if (!items.length && lastError && providerStatusEntries.some((entry) => entry.kind === "unavailable")) throw lastError;
        if (!items.length && selectedSource === "MANIADB") {
          const mismatchInfo = await detectRegisterLookupCategoryMismatch(payload, selectedSource);
          if (mismatchInfo.categories.length === 1 && mismatchInfo.candidates.length) {
            $("category").value = mismatchInfo.categories[0];
            payload.category = mismatchInfo.categories[0];
            items = mismatchInfo.candidates;
            renderBarcodeResults(items || []);
            setStatus("barcodeStatus", "ok", t("media.register.api_lookup.status.category_mismatch_autofix", {
              category: requestedCategory || "-",
              detected: mismatchInfo.categories.join(", "),
            }));
            return;
          }
          if (mismatchInfo.categories.length) {
            renderBarcodeResults([]);
            setStatus("barcodeStatus", "err", t("media.register.api_lookup.status.category_mismatch_hint", {
              category: payload.category || "-",
              detected: mismatchInfo.categories.join(", "),
            }));
            return;
          }
        }
        renderBarcodeResults(items || []);
        if (Array.isArray(items) && items.length) {
          selectRegisterLookupCandidate(0, { focus: true, preventScroll: true, scroll: false });
        } else {
          selectedCandidate = null;
        }
        const adjustedSourceText = usedSource !== selectedSource ? t("media.register.api_lookup.status.adjusted_source", { source: usedSource }) : "";
        setStatus("barcodeStatus", "ok", t("media.register.api_lookup.status.query_done", {
          count: countWithUnit((items || []).length),
          adjusted_source: adjustedSourceText,
        }));
      } catch (err) {
        renderBarcodeResults([]);
        setStatus("barcodeStatus", "err", errorMessageText(err, t("media.register.api_lookup.status.lookup_failed")));
      }
    }

    async function submitAdminRegisterLookupSearch() {
      const barcode = $("barcodeInput").value.trim();
      const hasQueryInput = [
        $("queryArtist").value.trim(),
        $("queryTitle").value.trim(),
        $("queryCatalog").value.trim(),
        $("querySourceRef").value.trim(),
      ].some(Boolean);
      if (barcode) {
        await barcodeSearch();
        return;
      }
      if (hasQueryInput) {
        await querySearch();
        return;
      }
      renderRegisterLookupProviderStatusBadges([]);
      setStatus("barcodeStatus", "err", t("media.register.api_lookup.status.lookup_requires_input"));
    }

    function buildOwnedPayload() {
      const category = $("category").value;
      const isSecondHand = $("isSecondHand").checked;
      const status = $("status").value;
      const displayRankRaw = $("displayRank").value.trim();
      const purchasePrice = normalizePurchasePriceOrNull($("purchasePrice").value);
      const mappedDomain = pickMappedDomain(selectedCandidate?.domain_code);
      const mappedReleaseType = pickMappedReleaseType(selectedCandidate?.release_type);
      const isMusic = isMusicCategory();
      const itemNameInput = isMusic
        ? $("itemNameOverride").value.trim()
        : $("goodsItemName").value.trim();

      const payload = {
        category,
        size_group: $("sizeGroup").value,
        preferred_storage_size_group: $("sizeGroup").value,
        auto_location_recommendation: !selectedCandidate,
        quantity: Number($("quantity").value || 1),
        is_second_hand: isSecondHand,
        status,
        signature_type: $("signatureType").value,
        source_code: selectedCandidate?.source || null,
        source_external_id: selectedCandidate?.external_id || null,
        domain_code: $("domainCode").value || mappedDomain || null,
        release_type: $("releaseType").value || mappedReleaseType || null,
        linked_album_master_id: $("linkedAlbumMasterId").value.trim()
          ? Number($("linkedAlbumMasterId").value)
          : null,
        linked_artist_name: $("linkedArtistName").value.trim() || null,
        purchase_price: purchasePrice,
        currency_code: purchasePrice !== null ? normalizeCurrencyCodeOrNull($("currencyCode").value, "KRW") : null,
        purchase_source: $("purchaseSource").value.trim() || null,
        condition_grade: $("conditionGrade").value.trim() || null,
        memory_note: $("memoryNote").value.trim() || null,
        item_name_override: itemNameInput || null,
        display_rank: displayRankRaw ? Number(displayRankRaw) : null,
        storage_slot_id: $("slotId").value ? Number($("slotId").value) : null
      };

      if (isMusic) {
        const candidateCollector = buildCollectorPayload(selectedCandidate?.source || null, selectedCandidate || {});
        const runoutInput = splitRunoutList($("runoutMatrix").value);
        const pressingInput = $("pressingCountry").value.trim();
        const cover = normalizeConditionGradeValue($("coverCondition").value);
        const disc = normalizeConditionGradeValue($("discCondition").value);
        const trackList = $("trackList").value
          .split("\n")
          .map((v) => v.trim())
          .filter((v) => v);

        payload.music_detail = {
          format_name: $("formatName").value,
          is_promotional_not_for_sale: $("promoNfs").checked,
          artist_or_brand: selectedCandidate?.artist_or_brand || null,
          released_date: $("releasedDate").value.trim() || selectedCandidate?.released_date || null,
          barcode: selectedCandidate?.barcode || null,
          label_name: $("labelName").value.trim() || null,
          catalog_no: $("catalogNo").value.trim() || null,
          media_type: $("mediaType").value.trim() || selectedCandidate?.media_type || null,
          genres: splitCommaList($("genres").value || selectedCandidate?.genres || []),
          styles: splitCommaList($("styles").value || selectedCandidate?.styles || []),
          cover_image_url: $("coverImageUrl").value.trim() || null,
          track_list: trackList,
          cover_condition: cover || null,
          disc_condition: disc || null,
          disc_count: $("discCount").value.trim() ? normalizePositiveIntOrNull($("discCount").value) : normalizePositiveIntOrNull(selectedCandidate?.disc_count),
          speed_rpm: $("speedRpm").value.trim() ? Number($("speedRpm").value) : (Number.isFinite(Number(selectedCandidate?.speed_rpm)) ? Number(selectedCandidate.speed_rpm) : null),
          has_obi: $("hasObi").checked ? true : null,
          runout_matrix: runoutInput.length ? runoutInput : candidateCollector.runout_matrix,
          pressing_country: pressingInput || candidateCollector.pressing_country || null,
          source_notes: candidateCollector.source_notes,
          credits: candidateCollector.credits,
          identifier_items: candidateCollector.identifier_items,
          image_items: candidateCollector.image_items,
          company_items: candidateCollector.company_items,
          series: candidateCollector.series,
          format_items: candidateCollector.format_items,
          track_items: candidateCollector.track_items,
          label_items: candidateCollector.label_items
        };
      } else {
        const goodsImageUrls = splitLineList($("goodsImageUrls").value);
        payload.goods_detail = {
          image_urls: goodsImageUrls,
          primary_image_url: goodsImageUrls.length ? goodsImageUrls[0] : null,
          poster_storage_spec: $("posterStorageSpec").value.trim() || null,
          tshirt_size: $("tshirtSize").value.trim() || null,
          cup_material: $("cupMaterial").value.trim() || null,
          hat_size: $("hatSize").value.trim() || null
        };
      }

      if (selectedCandidate && selectedCandidate.external_id && !payload.memory_note) {
        payload.memory_note = `[AUTO] ${selectedCandidate.source}#${selectedCandidate.external_id}`;
      }

      return payload;
    }

    async function createOwnedItem() {
      try {
        const payload = buildOwnedPayload();
        const createdTitle = String(payload.item_name_override || $("goodsItemName").value || "").trim() || t("common.new_item");
        if (!confirmSlotMismatchById(payload.storage_slot_id, [{
          label_id: t("common.new"),
          item_name_override: createdTitle,
          size_group: payload.size_group,
          preferred_storage_size_group: payload.preferred_storage_size_group,
        }], t("media.register.direct.action.save"))) {
          setStatus("createStatus", "ok", t("media.register.direct.status.cancelled"));
          return;
        }
        // ── 도메인 불일치 검증 ──────────────────────────────────────────────
        if (isMusicCategory()) {
          const _domainVal   = String(payload.domain_code || "").trim().toUpperCase();
          const _artistCheck = String(
            payload.music_detail?.artist_or_brand ||
            payload.linked_artist_name ||
            payload.item_name_override || ""
          ).trim();
          const _hasHangul = /[가-힣ㄱ-ㆎ]/.test(_artistCheck);
          const _hasKana   = /[぀-ヿ一-鿿]/.test(_artistCheck);
          // ManiaDB 후보는 항상 가요 — 영문 표기 한국 아티스트가 많으므로 도메인 검증 면제
          const _candidateSource = String(selectedCandidate?.source || "").trim().toUpperCase();
          const _isManiadb = _candidateSource === "MANIADB";
          if (!_isManiadb && _artistCheck && !_hasHangul && !_hasKana) {
            if (_domainVal === "KOREA") {
              setStatus("createStatus", "err",
                `⚠ 도메인 불일치: 아티스트 "${_artistCheck}"는 영문인데 도메인이 '가요'입니다. ` +
                `팝(WESTERN)으로 바꾸거나, 맞다면 다시 저장 버튼을 누르세요.`
              );
              $("domainCode").focus();
              return;
            }
            if (_domainVal === "JAPAN") {
              setStatus("createStatus", "err",
                `⚠ 도메인 불일치: 아티스트 "${_artistCheck}"는 영문인데 도메인이 '제이팝'입니다. ` +
                `팝(WESTERN)으로 바꾸거나, 맞다면 다시 저장 버튼을 누르세요.`
              );
              $("domainCode").focus();
              return;
            }
          }
          if (_artistCheck && _hasHangul && _domainVal === "WESTERN") {
            setStatus("createStatus", "err",
              `⚠ 도메인 불일치: 아티스트 "${_artistCheck}"는 한글인데 도메인이 '팝'입니다. ` +
              `가요(KOREA)로 바꾸거나, 맞다면 다시 저장 버튼을 누르세요.`
            );
            $("domainCode").focus();
            return;
          }
        }
        // ────────────────────────────────────────────────────────────────────
        setStatus("createStatus", "ok", t("media.register.direct.status.saving"));

        const res = await fetch("/owned-items", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.register.direct.status.failed"));

        const notices = Array.isArray(data.notices) ? data.notices : [];
        const mergeNotices = await maybeMergeDuplicateMastersForCreatedItem(
          Number(data.linked_album_master_id || 0),
          "createStatus"
        );
        for (const msg of mergeNotices) {
          notices.push(msg);
        }
        setStatus("createStatus", "ok", t("media.register.direct.status.done", {
          owned_id: data.owned_item_id,
          label_id: data.label_id,
          details: notices.length ? `\n${notices.map((v) => `- ${v}`).join("\n")}` : "",
        }));
        $("orderMoveItemId").value = String(data.owned_item_id);
        await loadOwnedItems();
        await loadHomeDashboard();
      } catch (err) {
        setStatus("createStatus", "err", err.message);
      }
    }

    function trackMapRowHtml(row) {
      const assets = Array.isArray(row.assets) ? row.assets : [];
      const fileList = assets.length
        ? assets.map((a) => `${a.file_path}${a.duration_sec ? ` (${a.duration_sec}s)` : ""}`).join("\n")
        : "-";
      return `
        <tr>
          <td>${row.track_no}</td>
          <td>${escapeHtml(row.track_entry || "-")}</td>
          <td>${assets.length}</td>
          <td class="u-pre-wrap">${escapeHtml(fileList)}</td>
        </tr>
      `;
    }

    function renderTrackMapBody(bodyId, mappings) {
      $(bodyId).innerHTML = (mappings || []).map(trackMapRowHtml).join("") ||
        `<tr><td colspan='4' class='muted'>${escapeHtml(t("media.manage.track_map.track.table.empty"))}</td></tr>`;
    }

    function renderHomeTrackMapBody(mappings) {
      const rows = Array.isArray(mappings) ? mappings : [];
      homeAudioDirectoryMappings = rows;
      const info = $("homeTrackMapMappedInfo");
      if (!info) return;
      if (!rows.length) {
        info.textContent = t("media.manage.track_map.directory.state.none");
        return;
      }
      const top = rows[0] || {};
      const topPath = String(top.directory_path || "-").trim() || "-";
      info.textContent = t("media.manage.track_map.directory.meta.summary", {
        path: topPath,
        shown: formatCount(rows.length),
        total: formatCount(rows.length),
        recursive: "",
        truncated: "",
      });
    }

    function homeTrackFileRowHtml(row) {
      const relPath = String(row?.relative_path || row?.file_path || "-");
      const fullPath = String(row?.file_path || relPath);
      const sizeText = row?.file_size_bytes == null
        ? "-"
        : Number(row.file_size_bytes).toLocaleString();
      return `
        <tr>
          <td title="${escapeHtml(fullPath)}">${escapeHtml(relPath)}</td>
          <td>${escapeHtml(String(sizeText))}</td>
        </tr>
      `;
    }

    function renderHomeTrackFileList(files, meta = null) {
      const rows = Array.isArray(files) ? files : [];
      homeAudioDirectoryFiles = rows;
      $("homeTrackFileListBody").innerHTML = rows.map(homeTrackFileRowHtml).join("") ||
        `<tr><td colspan='2' class='muted'>${escapeHtml(t("media.manage.track_map.directory.table.empty_files"))}</td></tr>`;

      const metaEl = $("homeTrackFileListMeta");
      if (!meta) {
        metaEl.textContent = "";
        return;
      }
      const dir = String(meta.directory_path || "").trim() || "-";
      const total = Number(meta.file_count || rows.length || 0);
      const shown = Number(meta.returned_count || rows.length || 0);
      const recursiveText = meta.recursive ? t("media.manage.track_map.directory.meta.recursive") : "";
      const truncatedText = meta.truncated ? t("media.manage.track_map.directory.meta.truncated") : "";
      metaEl.textContent = t("media.manage.track_map.directory.meta.summary", {
        path: dir,
        shown: formatCount(shown),
        total: formatCount(total),
        recursive: recursiveText,
        truncated: truncatedText,
      });
    }

    async function loadHomeAudioDirectoryFiles() {
      const ownedItemId = Number($("editOwnedId").value || 0);
      const directoryPath = $("homeTrackMapDir").value.trim();
      if (!ownedItemId) {
        renderHomeTrackFileList([], null);
        return;
      }
      if (!MUSIC_CATEGORIES.has($("editCategory").value)) {
        renderHomeTrackFileList([], null);
        return;
      }
      if (!directoryPath) {
        renderHomeTrackFileList([], null);
        return;
      }

      try {
        setStatus("homeTrackMapStatus", "ok", t("media.manage.track_map.directory.status.files_loading"));
        const query = new URLSearchParams({
          directory_path: directoryPath,
          recursive: "true",
          limit: "300",
        });
        const res = await fetch(`/owned-items/${ownedItemId}/audio-directory-files?${query.toString()}`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.track_map.directory.status.files_failed"));

        renderHomeTrackFileList(data.files || [], data);
        if (!$("homeTrackMapDir").value.trim() && data.directory_path) {
          $("homeTrackMapDir").value = String(data.directory_path);
        }
        setStatus("homeTrackMapStatus", "ok", t("media.manage.track_map.directory.status.files_loaded", {
          shown: formatCount(Number(data.returned_count || 0)),
          total: formatCount(Number(data.file_count || 0)),
        }));
      } catch (err) {
        renderHomeTrackFileList([], null);
        setStatus("homeTrackMapStatus", "err", err.message);
      }
    }

    async function loadHomeTrackMappings() {
      const ownedItemId = Number($("editOwnedId").value || 0);
      if (!ownedItemId) {
        setStatus("homeTrackMapStatus", "err", t("media.manage.track_map.directory.status.item_required"));
        renderHomeTrackMapBody([]);
        renderHomeTrackFileList([], null);
        return;
      }
      if (!MUSIC_CATEGORIES.has($("editCategory").value)) {
        setStatus("homeTrackMapStatus", "ok", t("media.manage.track_map.directory.status.media_only"));
        renderHomeTrackMapBody([]);
        renderHomeTrackFileList([], null);
        return;
      }

      try {
        setStatus("homeTrackMapStatus", "ok", t("media.manage.track_map.directory.status.mappings_loading"));
        const res = await fetch(`/owned-items/${ownedItemId}/audio-directory-mappings`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.track_map.directory.status.mappings_failed"));

        const mappings = Array.isArray(data.mappings) ? data.mappings : [];
        renderHomeTrackMapBody(mappings);
        if (!$("homeTrackMapDir").value.trim() && mappings.length) {
          $("homeTrackMapDir").value = String(mappings[0].directory_path || "");
        }
        setStatus("homeTrackMapStatus", "ok", t("media.manage.track_map.directory.status.mappings_loaded", {
          count: countWithUnit(mappings.length),
        }));
        if ($("homeTrackMapDir").value.trim()) {
          await loadHomeAudioDirectoryFiles();
        } else {
          renderHomeTrackFileList([], null);
        }
      } catch (err) {
        renderHomeTrackMapBody([]);
        renderHomeTrackFileList([], null);
        setStatus("homeTrackMapStatus", "err", err.message);
      }
    }

    async function pickHomeTrackMapDirectory() {
      const currentPath = $("homeTrackMapDir").value.trim();
      try {
        setStatus("homeTrackMapStatus", "ok", t("media.manage.track_map.directory.status.pick_opening"));
        const res = await fetch("/ui/pick-directory", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            initial_path: currentPath || null,
            title: t("media.manage.track_map.directory.pick_title")
          }),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.track_map.directory.status.pick_failed"));

        const pickedPath = String(data.directory_path || "").trim();
        if (data.cancelled || !pickedPath) {
          setStatus("homeTrackMapStatus", "ok", t("media.manage.track_map.directory.status.pick_cancelled"));
          return;
        }
        $("homeTrackMapDir").value = pickedPath;
        setStatus("homeTrackMapStatus", "ok", t("media.manage.track_map.directory.status.pick_selected", { path: pickedPath }));
        await bulkMapHomeTrackMappings();
      } catch (err) {
        setStatus("homeTrackMapStatus", "err", err.message);
      }
    }

    async function bulkMapHomeTrackMappings() {
      const ownedItemId = Number($("editOwnedId").value || 0);
      const directoryPath = $("homeTrackMapDir").value.trim();

      if (!ownedItemId) {
        setStatus("homeTrackMapStatus", "err", t("media.manage.track_map.directory.status.item_required"));
        return;
      }
      if (!directoryPath) {
        setStatus("homeTrackMapStatus", "err", t("media.manage.track_map.directory.status.path_required"));
        return;
      }
      if (homeTrackMapSaveInFlight) {
        return;
      }

      const payload = {
        directory_path: directoryPath,
        replace_existing: $("homeTrackMapReplace").checked,
      };

      try {
        homeTrackMapSaveInFlight = true;
        setStatus("homeTrackMapStatus", "ok", t("media.manage.track_map.directory.status.saving"));
        const res = await fetch(`/owned-items/${ownedItemId}/audio-directory-mappings`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.track_map.directory.status.save_failed"));

        const replaced = Number(data.replaced_existing_links || 0);
        setStatus(
          "homeTrackMapStatus",
          "ok",
          t("media.manage.track_map.directory.status.saved", {
            path: String(data.directory_path || directoryPath),
            replaced: countWithUnit(replaced),
          })
        );
        await loadHomeTrackMappings();
        if (homeSelectedMasterId) {
          await loadHomeMasterMembers(homeSelectedMasterId, { autoOpenFirst: false });
        } else {
          resetHomeMasterLookupUi({ clearInputs: true });
        }
        await loadHomeItemForEdit(ownedItemId, { keepMasterContext: Boolean(homeSelectedMasterId) });
        await homeSearchOwnedItems();
        await loadHomeDashboard();
      } catch (err) {
        setStatus("homeTrackMapStatus", "err", err.message);
      } finally {
        homeTrackMapSaveInFlight = false;
      }
    }

    async function loadTrackMappings() {
      const ownedItemId = Number($("trackOwnedItemId").value || 0);
      if (!ownedItemId) {
        setStatus("trackMapStatus", "err", t("media.manage.track_map.track.status.owned_item_required"));
        return;
      }

      try {
        setStatus("trackMapStatus", "ok", t("media.manage.track_map.track.status.loading"));
        const res = await fetch(`/owned-items/${ownedItemId}/track-mappings`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.track_map.track.status.failed"));

        renderTrackMapBody("trackMapBody", data.mappings || []);
        setStatus("trackMapStatus", "ok", t("media.manage.track_map.track.status.loaded", {
          count: countWithUnit(Number(data.track_count || 0)),
        }));
      } catch (err) {
        renderTrackMapBody("trackMapBody", []);
        setStatus("trackMapStatus", "err", err.message);
      }
    }

    async function saveTrackMapping() {
      const ownedItemId = Number($("trackOwnedItemId").value || 0);
      const trackNo = Number($("trackMapNo").value || 0);
      const filePath = $("trackMapPath").value.trim();
      const durationRaw = $("trackMapDuration").value.trim();
      const note = $("trackMapNote").value.trim();

      if (!ownedItemId) {
        setStatus("trackMapStatus", "err", t("media.manage.track_map.track.status.owned_item_required"));
        return;
      }
      if (!trackNo) {
        setStatus("trackMapStatus", "err", t("media.manage.track_map.track.status.track_no_required"));
        return;
      }
      if (!filePath) {
        setStatus("trackMapStatus", "err", t("media.manage.track_map.track.status.file_path_required"));
        return;
      }

      const payload = {
        track_no: trackNo,
        file_path: filePath,
        duration_sec: durationRaw ? Number(durationRaw) : null,
        note: note || null
      };

      try {
        setStatus("trackMapStatus", "ok", t("media.manage.track_map.track.status.saving"));
        const res = await fetch(`/owned-items/${ownedItemId}/track-mappings`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.track_map.track.status.failed"));

        setStatus(
          "trackMapStatus",
          "ok",
          t("media.manage.track_map.track.status.saved", {
            track_no: data.track_no,
            link_id: data.link_id,
          })
        );
        await loadTrackMappings();
      } catch (err) {
        setStatus("trackMapStatus", "err", err.message);
      }
    }

    async function syncDiscogsOwned(ownedItemId) {
      if (!ownedItemId) return;
      try {
        setStatus("ownedStatusBox", "ok", t("media.manage.owned.status.discogs_syncing", { owned_item_id: ownedItemId }));
        const res = await fetch(`/discogs/owned-sync/${ownedItemId}`, { method: "POST" });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.owned.status.discogs_sync_failed"));
        setStatus(
          "ownedStatusBox",
          "ok",
          t("media.manage.owned.status.discogs_synced", {
            username: String(data.username || "-"),
            release_id: String(data.source_external_id || "-"),
          })
        );
      } catch (err) {
        setStatus("ownedStatusBox", "err", err.message);
      }
    }

    function renderOpsProviderSettings(snapshot) {
      opsProviderSettingsSnapshot = snapshot ? { ...snapshot } : null;
      const data = opsProviderSettingsSnapshot || {};
      $("opsProviderDiscogsToken").value = "";
      $("opsProviderAladinTtbKey").value = "";
      $("opsProviderDeeplAuthKey").value = "";
      $("opsProviderDiscogsToken").setAttribute(
        "placeholder",
        t(data.discogs_token_configured ? "ops.providers.field.secret.placeholder_configured" : "ops.providers.field.secret.placeholder_missing")
      );
      $("opsProviderAladinTtbKey").setAttribute(
        "placeholder",
        t(data.aladin_ttb_key_configured ? "ops.providers.field.secret.placeholder_configured" : "ops.providers.field.secret.placeholder_missing")
      );
      $("opsProviderDeeplAuthKey").setAttribute(
        "placeholder",
        t(data.deepl_auth_key_configured ? "ops.providers.field.secret.placeholder_configured" : "ops.providers.field.secret.placeholder_missing")
      );
      setTextIfPresent(
        "opsProviderDiscogsTokenState",
        t(data.discogs_token_configured ? "ops.providers.field.secret.configured" : "ops.providers.field.secret.missing")
      );
      setTextIfPresent(
        "opsProviderAladinTtbKeyState",
        t(data.aladin_ttb_key_configured ? "ops.providers.field.secret.configured" : "ops.providers.field.secret.missing")
      );
      setTextIfPresent(
        "opsProviderDeeplAuthKeyState",
        t(data.deepl_auth_key_configured ? "ops.providers.field.secret.configured" : "ops.providers.field.secret.missing")
      );
      const _discogs_ua = String(data.discogs_user_agent || "");
      const _emailMatch = _discogs_ua.match(/contact:\s*([^\s)]+)/);
      $("opsProviderDiscogsContactEmail").value = _emailMatch ? _emailMatch[1] : "";
      const _uaPreview = $("opsProviderDiscogsUaPreview");
      if (_uaPreview) _uaPreview.textContent = _discogs_ua ? `User-Agent: ${_discogs_ua}` : "";
      $("opsProviderAladinBaseUrl").value = String(data.aladin_base_url || "");
      $("opsProviderManiadbBaseUrl").value = String(data.maniadb_base_url || "");
      $("opsProviderDeeplBaseUrl").value = String(data.deepl_base_url || "");
    }

    async function loadOpsProviderSettings() {
      try {
        setStatus("opsProviderStatus", "ok", t("ops.providers.status.loading"));
        const res = await fetch("/ops/provider-settings");
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("ops.providers.status.load_failed"));
        renderOpsProviderSettings(data);
        setStatus("opsProviderStatus", "ok", t("ops.providers.status.loaded"));
      } catch (err) {
        setStatus("opsProviderStatus", "err", errorMessageText(err, t("ops.providers.status.load_failed")));
      }
    }

    async function saveOpsProviderSettings() {
      return saveOpsProviderSettingsFields([
        "discogs_token",
        "aladin_ttb_key",
        "deepl_auth_key",
        "discogs_user_agent",
        "aladin_base_url",
        "maniadb_base_url",
        "deepl_base_url",
      ]);
    }

    async function saveOpsProviderSettingsFields(fields, statusKey = "ops.providers.status.saved") {
      const allowedFields = new Set(Array.isArray(fields) ? fields : []);
      const sourcePayload = {
        discogs_token: $("opsProviderDiscogsToken").value.trim() || null,
        aladin_ttb_key: $("opsProviderAladinTtbKey").value.trim() || null,
        deepl_auth_key: $("opsProviderDeeplAuthKey").value.trim() || null,
        discogs_user_agent: (() => {
          const _email = $("opsProviderDiscogsContactEmail")?.value.trim();
          return _email ? `__PROJECT_SLUG__-library/0.1 (contact: ${_email})` : null;
        })(),
        aladin_base_url: $("opsProviderAladinBaseUrl").value.trim() || null,
        maniadb_base_url: $("opsProviderManiadbBaseUrl").value.trim() || null,
        deepl_base_url: $("opsProviderDeeplBaseUrl").value.trim() || null,
      };
      const payload = Object.fromEntries(
        Object.entries(sourcePayload).filter(([key]) => allowedFields.has(key))
      );
      try {
        setStatus("opsProviderStatus", "ok", t("ops.providers.status.saving"));
        const res = await fetch("/ops/provider-settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("ops.providers.status.save_failed"));
        renderOpsProviderSettings(data);
        setStatus("opsProviderStatus", "ok", t(statusKey));
      } catch (err) {
        setStatus("opsProviderStatus", "err", errorMessageText(err, t("ops.providers.status.save_failed")));
      }
    }

    async function testOpsProviderDeeplConnection() {
      try {
        setStatus("opsProviderStatus", "ok", t("ops.providers.status.testing_deepl"));
        const res = await fetch("/ops/provider-settings/deepl-test", {
          method: "POST",
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("ops.providers.status.deepl_test_failed"));
        if (!data || !data.ok) {
          throw new Error(String(data?.detail || t("ops.providers.status.deepl_test_failed")).trim());
        }
        const translatedText = String(data.translated_text || "").trim();
        setStatus(
          "opsProviderStatus",
          "ok",
          translatedText
            ? `${t("ops.providers.status.deepl_test_ok")}: ${translatedText}`
            : t("ops.providers.status.deepl_test_ok")
        );
      } catch (err) {
        setStatus("opsProviderStatus", "err", errorMessageText(err, t("ops.providers.status.deepl_test_failed")));
      }
    }

    async function loadOpsBackupSettings() {
      try {
        const res = await fetch("/ops/export/backup-settings");
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("ops.restore.status.load_failed"));
        $("opsAutoBackupEnabled").checked = Boolean(data.enabled);
        $("opsAutoBackupIntervalDays").value = String(autoBackupIntervalDaysFromMinutes(data.interval_minutes || 0));
        $("opsAutoBackupDir").value = String(data.backup_dir || "");
        $("opsAutoBackupScope").value = String(data.backup_scope || "DB").toUpperCase() === "FULL" ? "FULL" : "DB";
        $("opsAutoBackupIncludeEnvFile").checked = Boolean(data.include_env_file);
        renderOpsBackupScheduleDetails(data);
        const summaryBits = [
          data.enabled ? t("ops.restore.summary.auto_on", { days: formatCount(autoBackupIntervalDaysFromMinutes(data.interval_minutes || 0)) }) : t("ops.restore.summary.auto_off"),
          String(data.backup_scope || "DB").toUpperCase() === "FULL" ? t("ops.restore.summary.scope_full") : t("ops.restore.summary.scope_db"),
          data.include_env_file ? t("ops.restore.summary.include_env") : t("ops.restore.summary.exclude_env"),
          String(data.daily_schedule || "").trim() ? t("ops.restore.summary.daily_schedule", { value: String(data.daily_schedule || "").trim() }) : "",
          String(data.weekly_schedule || "").trim() ? t("ops.restore.summary.weekly_schedule", { value: String(data.weekly_schedule || "").trim() }) : "",
          String(data.backup_dir || "").trim() ? t("ops.restore.summary.path", { path: String(data.backup_dir || "").trim() }) : "",
          String(data.last_backup_at || "").trim() ? t("ops.restore.summary.last_at", { value: String(data.last_backup_at || "").trim() }) : "",
          String(data.last_backup_path || "").trim() ? t("ops.restore.summary.last_path", { value: String(data.last_backup_path || "").trim() }) : "",
        ].filter(Boolean);
        $("opsAutoBackupSummary").textContent = summaryBits.join(" · ") || t("ops.restore.summary.empty");
        setStatus("opsAutoBackupStatus", data.last_error ? "err" : "ok", data.last_error || t("ops.restore.status.load_complete"));
      } catch (err) {
        setStatus("opsAutoBackupStatus", "err", errorMessageText(err, t("ops.restore.status.load_failed")));
      }
    }

    async function saveOpsBackupSettings() {
      const payload = {
        enabled: $("opsAutoBackupEnabled").checked,
        interval_minutes: autoBackupIntervalMinutesFromDays($("opsAutoBackupIntervalDays").value),
        backup_dir: $("opsAutoBackupDir").value.trim(),
        backup_scope: $("opsAutoBackupScope").value === "FULL" ? "FULL" : "DB",
        include_env_file: $("opsAutoBackupIncludeEnvFile").checked,
      };
      if (!payload.backup_dir) {
        setStatus("opsAutoBackupStatus", "err", t("ops.restore.status.dir_required"));
        return;
      }
      try {
        setStatus("opsAutoBackupStatus", "ok", t("ops.restore.status.save_loading"));
        const res = await fetch("/ops/export/backup-settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("ops.restore.status.save_failed"));
        $("opsAutoBackupEnabled").checked = Boolean(data.enabled);
        $("opsAutoBackupIntervalDays").value = String(autoBackupIntervalDaysFromMinutes(data.interval_minutes || 0));
        $("opsAutoBackupDir").value = String(data.backup_dir || "");
        $("opsAutoBackupScope").value = String(data.backup_scope || "DB").toUpperCase() === "FULL" ? "FULL" : "DB";
        $("opsAutoBackupIncludeEnvFile").checked = Boolean(data.include_env_file);
        renderOpsBackupScheduleDetails(data);
        $("opsAutoBackupSummary").textContent = [
          data.enabled ? t("ops.restore.summary.auto_on", { days: formatCount(autoBackupIntervalDaysFromMinutes(data.interval_minutes || 0)) }) : t("ops.restore.summary.auto_off"),
          String(data.backup_scope || "DB").toUpperCase() === "FULL" ? t("ops.restore.summary.scope_full") : t("ops.restore.summary.scope_db"),
          data.include_env_file ? t("ops.restore.summary.include_env") : t("ops.restore.summary.exclude_env"),
          String(data.daily_schedule || "").trim() ? t("ops.restore.summary.daily_schedule", { value: String(data.daily_schedule || "").trim() }) : "",
          String(data.weekly_schedule || "").trim() ? t("ops.restore.summary.weekly_schedule", { value: String(data.weekly_schedule || "").trim() }) : "",
          t("ops.restore.summary.path", { path: String(data.backup_dir || "").trim() }),
        ].filter(Boolean).join(" · ");
        setStatus("opsAutoBackupStatus", "ok", t("ops.restore.status.save_complete"));
      } catch (err) {
        setStatus("opsAutoBackupStatus", "err", errorMessageText(err, t("ops.restore.status.save_failed")));
      }
    }

    async function downloadOpsFullBackup() {
      try {
        setStatus("opsExportStatus", "ok", t("ops.export.status.full_prepare"));
        const includeEnvFile = $("opsExportFullIncludeEnvFile").checked ? "true" : "false";
        const filename = await triggerBrowserDownload(
          `/ops/export/full-backup?include_env_file=${encodeURIComponent(includeEnvFile)}`,
          "__PROJECT_SLUG__-library-full-backup.zip"
        );
        setStatus("opsExportStatus", "ok", t("ops.export.status.full_started", { filename }));
      } catch (err) {
        setStatus("opsExportStatus", "err", errorMessageText(err, t("ops.export.status.full_failed")));
      }
    }

    async function restoreOpsDatabase() {
      const fileInput = $("opsRestoreDbFile");
      const file = fileInput?.files?.[0] || null;
      if (!file) {
        setStatus("opsAutoBackupStatus", "err", t("ops.restore.status.db_file_required"));
        return;
      }
      const ok = window.confirm(t("ops.restore.confirm.db"));
      if (!ok) {
        setStatus("opsAutoBackupStatus", "ok", t("ops.restore.status.db_cancelled"));
        return;
      }
      try {
        const formData = new FormData();
        formData.append("file", file);
        setStatus("opsAutoBackupStatus", "ok", t("ops.restore.status.db_uploading"));
        const res = await fetch("/ops/export/db-restore", {
          method: "POST",
          body: formData,
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("ops.restore.status.db_failed"));
        setStatus(
          "opsAutoBackupStatus",
          "ok",
          t("ops.restore.status.db_complete", {
            filename: String(data.restored_filename || file.name || "-"),
            backup: String(data.backup_path || "-")
          })
        );
        window.setTimeout(() => window.location.reload(), 600);
      } catch (err) {
        setStatus("opsAutoBackupStatus", "err", errorMessageText(err, t("ops.restore.status.db_failed")));
      }
    }

    async function restoreOpsBundle() {
      const fileInput = $("opsRestoreBundleFile");
      const file = fileInput?.files?.[0] || null;
      if (!file) {
        setStatus("opsAutoBackupStatus", "err", t("ops.restore.status.bundle_file_required"));
        return;
      }
      const ok = window.confirm(t("ops.restore.confirm.bundle"));
      if (!ok) {
        setStatus("opsAutoBackupStatus", "ok", t("ops.restore.status.bundle_cancelled"));
        return;
      }
      try {
        const formData = new FormData();
        formData.append("file", file);
        setStatus("opsAutoBackupStatus", "ok", t("ops.restore.status.bundle_uploading"));
        const res = await fetch("/ops/export/full-restore", {
          method: "POST",
          body: formData,
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("ops.restore.status.bundle_failed"));
        setStatus(
          "opsAutoBackupStatus",
          "ok",
          t("ops.restore.status.bundle_complete", {
            filename: String(data.restored_filename || file.name || "-"),
            backup: String(data.backup_path || "-")
          })
        );
        window.setTimeout(() => window.location.reload(), 600);
      } catch (err) {
        setStatus("opsAutoBackupStatus", "err", errorMessageText(err, t("ops.restore.status.bundle_failed")));
      }
    }

    async function downloadOpsDbBackup() {
      try {
        setStatus("opsExportStatus", "ok", t("ops.export.status.db_prepare"));
        const filename = await triggerBrowserDownload("/ops/export/db-backup", "__PROJECT_SLUG__-library-backup.db");
        setStatus("opsExportStatus", "ok", t("ops.export.status.db_started", { filename }));
      } catch (err) {
        setStatus("opsExportStatus", "err", errorMessageText(err, t("ops.export.status.db_failed")));
      }
    }

    async function downloadOpsOwnedCsv() {
      try {
        setStatus("opsExportStatus", "ok", t("ops.export.status.owned_csv_prepare"));
        const filename = await triggerBrowserDownload("/ops/export/owned-items.csv", "owned-items-export.csv");
        setStatus("opsExportStatus", "ok", t("ops.export.status.owned_csv_started", { filename }));
      } catch (err) {
        setStatus("opsExportStatus", "err", errorMessageText(err, t("ops.export.status.owned_csv_failed")));
      }
    }

    async function downloadOpsMasterCsv() {
      try {
        setStatus("opsExportStatus", "ok", t("ops.export.status.master_csv_prepare"));
        const filename = await triggerBrowserDownload("/ops/export/album-masters.csv", "album-masters-export.csv");
        setStatus("opsExportStatus", "ok", t("ops.export.status.master_csv_started", { filename }));
      } catch (err) {
        setStatus("opsExportStatus", "err", errorMessageText(err, t("ops.export.status.master_csv_failed")));
      }
    }

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
    function addRegImagePreview(url) {
      var p = document.getElementById("goodsRegisterImagePreview");
      if (!p) return;
      var item = document.createElement("span");
      item.style.cssText = "position:relative;display:inline-block;";
      var img = document.createElement("img"); img.src = url; img.style.cssText = "width:60px;height:60px;object-fit:cover;border-radius:4px;";
      var rm = document.createElement("button"); rm.textContent = "✕"; rm.style.cssText = "position:absolute;top:-4px;right:-4px;width:16px;height:16px;border-radius:50%;background:var(--danger);color:#fff;border:none;cursor:pointer;font-size:9px;line-height:16px;";
      rm.onclick = function() { _regImageUrls = _regImageUrls.filter(function(u) { return u !== url; }); item.remove(); $("goodsRegisterImageUrls").value = _regImageUrls.join("\n"); };
      item.appendChild(img); item.appendChild(rm);
      p.appendChild(item);
    }
    async function onGoodsRegisterImagePaste(e) {
      const clipboard = e.clipboardData;
      if (!clipboard) return;
      const imageFiles = [];
      for (const item of Array.from(clipboard.items || [])) {
        if (item.kind !== "file") continue;
        const file = item.getAsFile();
        if (file) imageFiles.push(file);
      }
      if (imageFiles.length) {
        e.preventDefault();
        try {
          const uploaded = await uploadUiImageFiles(imageFiles);
          uploaded.forEach(url => { if (url) { _regImageUrls.push(url); addRegImagePreview(url); } });
          $("goodsRegisterImageUrls").value = _regImageUrls.join("\n");
        } catch (err) { console.error("Image paste upload failed", err); }
        if ($("goodsRegisterImagePaste")) $("goodsRegisterImagePaste").value = "";
        return;
      }
      const pastedText = String(clipboard.getData("text/plain") || "").trim();
      if (!pastedText) return;
      const urls = extractUrlCandidates(pastedText);
      if (!urls.length) return;
      e.preventDefault();
      urls.forEach(url => { _regImageUrls.push(url); addRegImagePreview(url); });
      $("goodsRegisterImageUrls").value = _regImageUrls.join("\n");
      if ($("goodsRegisterImagePaste")) $("goodsRegisterImagePaste").value = "";
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

    async function loadErrorBadge() {
      try {
        const res = await fetchWithRetry("/admin/error-log/unread-count");
        if (!res.ok) return;
        const { count } = await res.json();
        const badge = $("errorUnreadBadge");
        if (count > 0) { badge.textContent = count; badge.style.display = ""; }
        else { badge.style.display = "none"; }
      } catch (_) {}
    }

    let _errAutoRefreshTimer = null;
    async function loadErrorLog(reset) {
      if (reset) _actErrOffset = 0;
      const isRead = $("actErrIsRead").value;
      let url = `/admin/error-log?limit=${_actErrLimit}&offset=${_actErrOffset}`;
      if (isRead !== "") url += `&is_read=${isRead}`;
      const res = await fetchWithRetry(url);
      if (!res.ok) { $("actErrCount").textContent = "조회 실패"; return; }
      const data = await res.json();
      $("actErrCount").textContent = `${data.total_count}건`;
      const tbody = $("actErrTbody");
      if (!data.items.length) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-muted)">결과 없음</td></tr>';
      } else {
        tbody.innerHTML = data.items.map(r => {
          const ts = (r.created_at || "").slice(0, 16).replace("T", " ");
          const levelBadge = r.level === "ERROR"
            ? `<span style="background:#fee2e2;color:#b91c1c;padding:1px 5px;border-radius:3px;font-size:0.7rem;font-weight:700">ERR</span>`
            : r.level === "WARNING"
            ? `<span style="background:#fef9c3;color:#92400e;padding:1px 5px;border-radius:3px;font-size:0.7rem;font-weight:700">WARN</span>`
            : `<span style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(r.level||"")}</span>`;
          const isReadBadge = r.is_read
            ? `<span style="color:var(--text-muted);font-size:0.72rem">확인</span>`
            : `<button data-ack-id="${r.id}" style="font-size:0.7rem;padding:1px 6px;border-radius:3px;cursor:pointer;border:1px solid #dc2626;background:#fee2e2;color:#b91c1c">확인처리</button>`;
          const tbDetail = r.traceback
            ? `<details style="margin-top:4px;font-size:0.72rem"><summary style="cursor:pointer;color:var(--accent)">스택 트레이스</summary><pre style="white-space:pre-wrap;margin:4px 0;font-size:0.7rem;color:var(--text-sub)">${escapeHtml(r.traceback)}</pre></details>`
            : "";
          return `<tr>
            <td style="white-space:nowrap;font-size:0.75rem;vertical-align:top">${ts}</td>
            <td style="vertical-align:top">${levelBadge}</td>
            <td style="font-size:0.74rem;vertical-align:top">${escapeHtml(r.request_path || "—")}</td>
            <td style="vertical-align:top"><div style="font-size:0.75rem;font-weight:600">${escapeHtml(r.message || "")}</div>${tbDetail}</td>
            <td style="font-size:0.72rem;color:var(--text-muted);vertical-align:top">${escapeHtml(r.source || "—")}</td>
            <td style="vertical-align:top">${isReadBadge}</td>
          </tr>`;
        }).join("");
      }
      $("actErrPrevBtn").disabled = _actErrOffset === 0;
      $("actErrNextBtn").disabled = data.items.length < _actErrLimit;
    }

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
    async function loadPerfLog() {
      const kind = $("actPerfKind").value;
      const days = $("actPerfDays").value;
      const slowOnly = $("actPerfSlowOnly").checked;
      let url = `/admin/perf-log?days=${days}&is_slow_only=${slowOnly}`;
      if (kind) url += `&kind=${kind}`;
      const res = await fetchWithRetry(url);
      if (!res.ok) { $("actPerfCount").textContent = "조회 실패"; return; }
      const data = await res.json();
      $("actPerfCount").textContent = `${data.total_count}건`;
      const tbody = $("actPerfTbody");
      const kindLabels = { API: "API", BATCH: "배치", QUERY: "DB" };
      if (!data.items.length) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-muted)">결과 없음</td></tr>';
      } else {
        tbody.innerHTML = data.items.map((r, i) => {
          const kindBadge = `<span style="font-size:0.72rem;background:var(--bg-dim,#f5f5f5);padding:1px 6px;border-radius:3px">${kindLabels[r.kind] || r.kind}</span>`;
          const slowBadge = r.slow_count > 0
            ? `<span style="background:#fee2e2;color:#b91c1c;padding:1px 5px;border-radius:3px;font-size:0.7rem;font-weight:700">${r.slow_count}건</span>`
            : `<span style="color:var(--text-muted);font-size:0.72rem">—</span>`;
          const fmtMs = (ms) => ms >= 1000 ? `${(ms/1000).toFixed(1)}s` : `${ms}ms`;
          const barW = Math.min(100, Math.round((r.avg_ms / 2000) * 100));
          const barColor = r.avg_ms >= 500 ? "#dc2626" : r.avg_ms >= 200 ? "#f59e0b" : "#22c55e";
          const bar = `<div style="width:60px;height:8px;background:var(--bg-dim,#eee);border-radius:4px;overflow:hidden;display:inline-block;vertical-align:middle"><div style="width:${barW}%;height:100%;background:${barColor}"></div></div>`;
          return `<tr data-perf-name="${escapeHtml(r.name)}" data-perf-kind="${escapeHtml(r.kind||"")}" style="cursor:pointer">
            <td>${kindBadge}</td>
            <td style="font-size:0.75rem;max-width:280px;word-break:break-all">${escapeHtml(r.name)}</td>
            <td style="font-size:0.75rem">${fmtMs(r.avg_ms)}</td>
            <td style="font-size:0.75rem;font-weight:${r.max_ms >= 300 ? '700' : '400'};color:${r.max_ms >= 300 ? '#dc2626' : 'inherit'}">${fmtMs(r.max_ms)}</td>
            <td style="font-size:0.75rem">${r.count}</td>
            <td>${slowBadge}</td>
            <td>${bar}</td>
          </tr>`;
        }).join("");
      }
    }

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

    async function loadActivityAudit(reset) {
      if (reset) _actAuditOffset = 0;
      const type = $("actAuditEntityType").value;
      const eid = ($("actAuditEntityId").value || "").trim();
      const action = $("logAuditAction")?.value || "";
      const changedBy = ($("logAuditChangedBy")?.value || "").trim();
      const dateFrom = $("logAuditDateFrom")?.value || "";
      const dateTo = $("logAuditDateTo")?.value || "";
      let url = `/admin/activity-log?limit=${_actAuditLimit}&offset=${_actAuditOffset}`;
      if (type) url += `&entity_type=${encodeURIComponent(type)}`;
      if (eid) url += `&entity_id=${encodeURIComponent(eid)}`;
      if (action) url += `&action=${encodeURIComponent(action)}`;
      if (changedBy) url += `&changed_by=${encodeURIComponent(changedBy)}`;
      if (dateFrom) url += `&date_from=${encodeURIComponent(dateFrom)}`;
      if (dateTo) url += `&date_to=${encodeURIComponent(dateTo + "T23:59:59")}`;
      const res = await fetchWithRetry(url);
      if (!res.ok) { $("actAuditCount").textContent = "조회 실패"; return; }
      const data = await res.json();
      $("actAuditCount").textContent = `${data.total_count}건`;
      const tbody = $("actAuditTbody");
      if (!data.items.length) { tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-muted)">결과 없음</td></tr>'; }
      else tbody.innerHTML = data.items.map(_renderGlobalAuditRow).join("");
      $("actAuditPrevBtn").disabled = _actAuditOffset === 0;
      $("actAuditNextBtn").disabled = data.total_count < _actAuditLimit;
    }
    $("actAuditLoadBtn").addEventListener("click", () => loadActivityAudit(true));
    $("actAuditPrevBtn").addEventListener("click", () => { _actAuditOffset = Math.max(0, _actAuditOffset - _actAuditLimit); loadActivityAudit(false); });
    $("actAuditNextBtn").addEventListener("click", () => { _actAuditOffset += _actAuditLimit; loadActivityAudit(false); });

    async function loadActivityLocation(reset) {
      if (reset) _actLocOffset = 0;
      const kind = $("actLocKind").value;
      const dateFrom = $("logLocDateFrom")?.value || "";
      const dateTo = $("logLocDateTo")?.value || "";
      let url = `/admin/activity-log/location-events?limit=${_actLocLimit}&offset=${_actLocOffset}`;
      if (kind) url += `&movement_kind=${encodeURIComponent(kind)}`;
      if (dateFrom) url += `&date_from=${encodeURIComponent(dateFrom)}`;
      if (dateTo) url += `&date_to=${encodeURIComponent(dateTo + "T23:59:59")}`;
      const res = await fetchWithRetry(url);
      if (!res.ok) { $("actLocCount").textContent = "조회 실패"; return; }
      const data = await res.json();
      $("actLocCount").textContent = `${data.total_count}건`;
      const tbody = $("actLocTbody");
      const _locKindLabels = { INITIAL_ASSIGN: "최초 배치", ASSIGN: "배치", MOVE: "이동", UNASSIGN: "회수", CABINET_DELETE: "장식장 삭제" };
      if (!data.items.length) { tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-muted)">결과 없음</td></tr>'; }
      else tbody.innerHTML = data.items.map(r => {
        const kindLabel = _locKindLabels[r.movement_kind] || r.movement_kind || "";
        const from_ = escapeHtml(r.from_slot_display_name || r.from_slot_code || "—");
        const to_ = escapeHtml(r.to_slot_display_name || r.to_slot_code || "—");
        return `<tr>
          <td style="white-space:nowrap;font-size:0.75rem">${(r.created_at||"").slice(0,16).replace("T"," ")}</td>
          <td style="font-size:0.75rem">${r.owned_item_id||""}</td>
          <td><span style="background:#e0e7ff;color:#3730a3;padding:1px 6px;border-radius:4px;font-size:0.7rem;font-weight:700">${kindLabel}</span></td>
          <td style="font-size:0.75rem;color:#dc2626">${from_}</td>
          <td style="font-size:0.75rem;color:#059669;font-weight:600">${to_}</td>
          <td style="font-size:0.75rem;color:var(--text-muted)">${escapeHtml(r.note||"")}</td>
        </tr>`;
      }).join("");
      $("actLocPrevBtn").disabled = _actLocOffset === 0;
      $("actLocNextBtn").disabled = data.total_count < _actLocLimit;
    }
    $("actLocLoadBtn").addEventListener("click", () => loadActivityLocation(true));
    $("actLocPrevBtn").addEventListener("click", () => { _actLocOffset = Math.max(0, _actLocOffset - _actLocLimit); loadActivityLocation(false); });
    $("actLocNextBtn").addEventListener("click", () => { _actLocOffset += _actLocLimit; loadActivityLocation(false); });
    async function loadServerLog() {
      const stream = $("actLogStream").value;
      const tail = parseInt($("actLogTail").value) || 200;
      const searchTerm = ($("logSrvSearch")?.value || "").trim();
      const res = await fetchWithRetry(`/admin/server-logs?stream=${stream}&tail=${tail}`);
      const box = $("actLogBox");
      if (!res.ok) { box.textContent = "로그 조회 실패 (권한 또는 경로 미설정)"; return; }
      const data = await res.json();
      if (searchTerm) {
        const escaped = searchTerm.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        const re = new RegExp(`(${escaped})`, "gi");
        box.innerHTML = escapeHtml(data.lines.join("\n")).replace(
          new RegExp(`(${escapeHtml(searchTerm).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi"),
          `<mark style="background:#fef08a;color:#000;border-radius:2px">$1</mark>`
        );
      } else {
        box.textContent = data.lines.join("\n");
      }
      box.scrollTop = box.scrollHeight;
    }
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
    function _syncCategoryFromMedia() {
      var mt = String($("editMediaType")?.value || "").trim();
      var cat = "LP", sg = "LP";
      if (["CD","CDr","SACD","Digital","DVD","Blu-ray","CD-ROM"].includes(mt)) { cat = "CD"; sg = "STD"; }
      else if (mt === "Cassette") { cat = "CASSETTE"; sg = "CASSETTE"; }
      else if (mt === "8-Track Cartridge") { cat = "8TRACK"; sg = "8TRACK"; }
      else if (mt === "Reel-To-Reel") { cat = "REEL_TO_REEL"; sg = "REEL_TO_REEL"; }
      else if (mt === '7"') { cat = "LP"; sg = "LP7"; }
      else if (mt === '10"') { cat = "LP"; sg = "LP10"; }
      if ($("editCategory")) $("editCategory").value = cat;
      if ($("editSizeGroup")) $("editSizeGroup").value = sg;
      if ($("editPreferredStorageSizeGroup")) $("editPreferredStorageSizeGroup").value = sg;
    }
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
    function openSpotifyEditMode() {
      const spId = String(homeMasterInfo?.spotify_album_id || "").trim();
      const input = $("homeMasterSpotifyMatchId");
      if (input) input.value = spId;
      const displayRow = $("homeMasterMetaSpotifyRow");
      const editRow = $("homeMasterMetaSpotifyEditRow");
      if (displayRow) displayRow.style.display = "none";
      if (editRow) editRow.style.display = "flex";
      setStatus("homeMasterSpotifyMatchStatus", "ok", "");
      input?.focus();
    }
    function closeSpotifyEditMode() {
      const displayRow = $("homeMasterMetaSpotifyRow");
      const editRow = $("homeMasterMetaSpotifyEditRow");
      if (editRow) editRow.style.display = "none";
      if (displayRow) displayRow.style.display = "flex";
      setStatus("homeMasterSpotifyMatchStatus", "ok", "");
    }
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
    async function saveLocalPath() {
      const masterIdVal = Number(homeMasterInfo?.album_master_id || 0);
      if (!masterIdVal) return;
      const path = ($("homeMasterLocalPath")?.value || "").trim();
      const statusEl = $("homeMasterLocalStatus");
      const saveBtn = $("homeMasterLocalSaveBtn");
      if (!path) { if (statusEl) statusEl.textContent = "경로를 입력하세요"; return; }
      if (saveBtn) saveBtn.disabled = true;
      if (statusEl) statusEl.textContent = "저장 중...";
      try {
        const res = await fetchWithRetry(`/album-masters/${masterIdVal}/local-link`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ dir_path: path }),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || "저장 실패");
        if (statusEl) statusEl.textContent = "저장됨";
        _localLinkedIds.add(masterIdVal);
        const short = path.replace(/^\/Volumes\/Music\//, "…/");
        const localText = $("homeMasterLocalText");
        if (localText) { localText.textContent = `♪ Local: ${short}`; localText.style.cursor = "pointer"; }
        $("homeMasterLocalRow").style.display = "flex";
        $("homeMasterLocalEditRow").style.display = "none";
        _lp._slotId = "homeMasterLocalPlayer";
        _lp.load(masterIdVal).catch(() => {});
        setTimeout(() => { if (statusEl) statusEl.textContent = ""; }, 2000);
      } catch (err) {
        if (statusEl) statusEl.textContent = `오류: ${escapeHtml(String(err.message || err))}`;
      } finally {
        if (saveBtn) saveBtn.disabled = false;
      }
    }
    $("homeMasterLocalSaveBtn")?.addEventListener("click", saveLocalPath);
    $("homeMasterLocalPath")?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); saveLocalPath(); }
      if (e.key === "Escape") { _hideLocalDirResults(); }
    });

    // ── 디렉토리 검색 자동완성 ──────────────────────────────────────────────
    let _localDirSearchTimer = null;

    function _hideLocalDirResults() {
      const el = $("homeMasterLocalDirResults");
      if (el) el.style.display = "none";
    }

    function _showLocalDirResults(dirs) {
      const el = $("homeMasterLocalDirResults");
      if (!el) return;
      if (!dirs.length) { el.style.display = "none"; return; }
      el.innerHTML = dirs.map(d => `
        <div class="local-dir-result-row" data-dir-path="${escapeHtml(d.dir_path)}" style="padding:5px 10px;cursor:pointer;border-bottom:1px solid var(--line);">
          <div style="font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(d.dir_name)}</div>
          <div style="color:var(--muted);font-size:0.65rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(d.dir_path.replace(/^\/Volumes\/Music\//, "…/"))}</div>
        </div>`).join("");
      el.style.display = "block";
      el.querySelectorAll(".local-dir-result-row").forEach(row => {
        row.addEventListener("mousedown", (e) => {
          e.preventDefault(); // blur 방지
          const path = row.dataset.dirPath;
          const pathInput = $("homeMasterLocalPath");
          if (pathInput) pathInput.value = path;
          _hideLocalDirResults();
        });
      });
    }

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
    async function handleMediaSearchContextAction(e) {
      const manageBtn = e.target.closest("[data-media-search-context-open-manage]");
      if (manageBtn) {
        const ownedItemId = Number(manageBtn.getAttribute("data-media-search-context-open-manage") || 0);
        if (!ownedItemId) return;
        const targetItem = findMediaSearchContextItemByOwnedItem(ownedItemId) || mediaSearchSelectedContextItem || null;
        const masterId = Number(targetItem?.linked_album_master_id || targetItem?.album_master_id || 0);
        await openMediaSearchDetailManage(masterId, ownedItemId);
        return;
      }
      const clearBtn = e.target.closest("[data-media-search-context-clear]");
      if (clearBtn) {
        mediaSearchSelectedContextItem = null;
        renderHomeSearchResults(homeSearchResults);
        return;
      }
      const contextCabinetBtn = e.target.closest("[data-operator-context-open-cabinet]");
      if (contextCabinetBtn) {
        if (contextCabinetBtn.classList.contains("ops-library-mini-map-cell")) {
          contextCabinetBtn.classList.remove("is-opening");
          contextCabinetBtn.offsetWidth;
          contextCabinetBtn.classList.add("is-opening");
        }
        await openOperatorCabinetLocationFromButton(contextCabinetBtn);
      }
    }

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
    const _inlineHistoryCache = new Map();

    // 한글 필드명 매핑
    const _AUDIT_FIELD_LABELS = {
      status: "상태", category: "카테고리", release_type: "발매 형태",
      linked_album_master_id: "연결 마스터 ID", linked_artist_name: "연결 아티스트명",
      source_code: "소스", source_external_id: "소스 ID",
      storage_slot_id: "보관 위치 ID", condition_grade: "컨디션",
      signature_type: "사인 유형", is_second_hand: "중고 여부",
      memory_note: "메모", notes: "내부 메모",
      purchase_price: "구매가", purchase_source: "구매처",
      acquisition_date: "취득일", size_group: "사이즈 그룹", signed_by: "사인한 사람",
      sort_artist_name: "정렬 아티스트명",
      release_year: "발매연도", domain_code: "도메인",
      override_note: "교정 메모", override_title: "교정 앨범명",
      override_artist_or_brand: "교정 아티스트명",
      genres: "장르", styles: "스타일",
      spotify_album_id: "Spotify 앨범 ID", spotify_album_uri: "Spotify URI",
      album_master_id: "마스터 ID",
      // album_master 필드
      artist_or_brand: "아티스트명", title: "앨범명", catalog_no: "카탈로그 번호",
      barcode: "바코드", release_month: "발매월", label: "레이블",
      country: "국가", format_text: "포맷", description: "설명",
      // 이미지/구매수입 스냅샷 필드
      filename: "파일명", content_type: "파일 형식",
      purchase_import_id: "구매수입 ID", source_email: "구매 이메일",
      // 외부참조
      source: "소스", source_master_id: "소스 마스터 ID",
      before_album_master_id: "이전 마스터 ID", after_album_master_id: "신규 마스터 ID",
    };

    const _AUDIT_VALUE_LABELS = {
      status: { IN_COLLECTION: "소장 중", SOLD: "판매됨", LENT: "대여 중", MISSING: "분실", DISPOSED: "처분" },
      category: { MUSIC: "음반", GOODS: "굿즈" },
      release_type: { LP: "LP", CD: "CD", TAPE: "카세트", DVD: "DVD", BLURAY: "블루레이", DIGITAL: "디지털", OTHER: "기타" },
      domain_code: { KOREA: "가요", JAPAN: "제이팝", GREATER_CHINA: "씨팝", WESTERN: "팝/웨스턴", OTHER_ASIA: "아시아 기타", WORLD: "월드 기타", UNKNOWN: "미분류" },
      signature_type: { NONE: "없음", SIGNED: "사인", DEDICATED: "헌정 사인", PRINTED: "인쇄 사인" },
      is_second_hand: { true: "중고", false: "새 상품", "1": "중고", "0": "새 상품" },
    };

    const _AUDIT_ACTION_LABELS = {
      CREATE: "등록", UPDATE: "수정", DELETE: "삭제",
      MERGE: "마스터 병합", MEMBER_LINK: "마스터 연결", MEMBER_UNLINK: "마스터 연결 해제",
      SPOTIFY_MATCH: "Spotify 매칭", SPOTIFY_CLEAR: "Spotify 매칭 해제",
      BULK_UPDATE: "일괄 수정", IMAGE_UPLOAD: "이미지 업로드", IMAGE_DELETE: "이미지 삭제",
      EXTERNAL_REF_UPDATE: "외부ID 변경", PURCHASE_IMPORT: "구매수입 등록",
    };

    const _AUDIT_ACTION_COLORS = {
      CREATE: { bg: "#d1fae5", color: "#065f46" },
      UPDATE: { bg: "#dbeafe", color: "#1d4ed8" },
      BULK_UPDATE: { bg: "#e0e7ff", color: "#3730a3" },
      DELETE: { bg: "#fee2e2", color: "#b91c1c" },
      MERGE: { bg: "#fef3c7", color: "#92400e" },
      MEMBER_LINK: { bg: "#d1fae5", color: "#065f46" },
      MEMBER_UNLINK: { bg: "#fee2e2", color: "#b91c1c" },
      SPOTIFY_MATCH: { bg: "#dcfce7", color: "#14532d" },
      SPOTIFY_CLEAR: { bg: "#fce7f3", color: "#831843" },
      EXTERNAL_REF_UPDATE: { bg: "#ede9fe", color: "#7c3aed" },
      PURCHASE_IMPORT: { bg: "#cffafe", color: "#0891b2" },
    };

    async function _loadInlineHistory(details) {
      const type = details.dataset.historyType;
      const id = Number(details.dataset.historyId || 0);
      if (!id || !type) { details.querySelector(".inline-entity-history-body").innerHTML = '<p style="color:var(--text-muted);font-size:0.78rem">ID 미설정</p>'; return; }
      const cacheKey = `${type}:${id}`;
      const body = details.querySelector(".inline-entity-history-body");
      if (_inlineHistoryCache.has(cacheKey)) { body.innerHTML = _inlineHistoryCache.get(cacheKey); return; }
      body.innerHTML = '<p style="color:var(--text-muted);font-size:0.78rem">불러오는 중...</p>';

      let html = "";
      try {
        if (type === "owned_item") {
          const [auditRes, locRes] = await Promise.all([
            fetchWithRetry(`/admin/activity-log?entity_type=owned_item&entity_id=${id}&limit=30`),
            fetchWithRetry(`/owned-items/${id}/location-events?limit=30`),
          ]);
          const auditData = auditRes.ok ? await auditRes.json() : { items: [] };
          const locData = locRes.ok ? await locRes.json() : { items: [] };
          const auditHtml = (auditData.items || []).map(_renderAuditItem).join("") || '<p style="color:var(--text-muted);font-size:0.76rem;margin:4px 0">변경 이력 없음</p>';
          const locHtml = (locData.items || []).length
            ? `<div style="border:1px solid var(--border-light,#e5e7eb);border-radius:8px;overflow:hidden">${(locData.items || []).map(_renderLocationItem).join("")}</div>`
            : '<p style="color:var(--text-muted);font-size:0.76rem;margin:4px 0">이동 이력 없음</p>';
          html = `<div style="font-weight:700;font-size:0.77rem;color:var(--text-sub);margin:6px 0 4px">메타 변경 이력 (${auditData.items?.length||0}건)</div>${auditHtml}
                  <div style="font-weight:700;font-size:0.77rem;color:var(--text-sub);margin:12px 0 4px">장식장 이동 이력 (${locData.items?.length||0}건)</div>${locHtml}`;
        } else if (type === "album_master") {
          const res = await fetchWithRetry(`/admin/activity-log/album-master/${id}?limit=30`);
          const data = res.ok ? await res.json() : { items: [] };
          html = (data.items || []).map(_renderAuditItem).join("") || '<p style="color:var(--text-muted);font-size:0.76rem;margin:4px 0">변경 이력 없음</p>';
        }
      } catch (err) {
        html = `<p style="color:var(--err,#dc3545);font-size:0.76rem">${escapeHtml(err.message)}</p>`;
      }
      body.innerHTML = html;
      _inlineHistoryCache.set(cacheKey, html);
    }

    document.addEventListener("toggle", (e) => {
      const details = e.target.closest(".inline-entity-history");
      if (!details || !details.open) return;
      const body = details.querySelector(".inline-entity-history-body");
      if (body && !body.innerHTML.trim()) _loadInlineHistory(details);
      else if (body && body.innerHTML.trim() && !_inlineHistoryCache.has(`${details.dataset.historyType}:${details.dataset.historyId}`)) _loadInlineHistory(details);
    }, true);

    // ── Spotify Match Modal ─────────────────────────────────────────────────
    let _spotifyMatchMasterId = 0;

    function openSpotifyMatchModal(masterId, title, artist) {
      _spotifyMatchMasterId = Number(masterId) || 0;
      const subtitle = $("spotifyMatchModalSubtitle");
      if (subtitle) subtitle.textContent = `${artist || ""} — ${title || ""}`;
      $("spotifyMatchDirectInput").value = "";
      $("spotifyMatchSearchInput").value = `${artist || ""} ${title || ""}`.trim();
      $("spotifyMatchStatus").className = "status";
      $("spotifyMatchStatus").textContent = "";
      $("spotifyMatchResults").innerHTML = "";
      $("spotifyMatchModal").classList.add("open");
      $("spotifyMatchModal").setAttribute("aria-hidden", "false");
      $("spotifyMatchSearchInput").focus();
    }

    function closeSpotifyMatchModal() {
      $("spotifyMatchModal").classList.remove("open");
      $("spotifyMatchModal").setAttribute("aria-hidden", "true");
      _spotifyMatchMasterId = 0;
    }

    async function doSpotifyMatchSearch() {
      const q = String($("spotifyMatchSearchInput")?.value || "").trim();
      if (!q) return;
      const statusEl = $("spotifyMatchStatus");
      const resultsEl = $("spotifyMatchResults");
      statusEl.className = "status ok";
      statusEl.textContent = t("ops.spotify_match.search.searching");
      resultsEl.innerHTML = "";
      try {
        const res = await fetch(`/spotify/search?q=${encodeURIComponent(q)}&limit=10`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
        // Response: {query, total_count, items: [{spotify_album_id, name, artist, release_date, image_url}]}
        const albums = Array.isArray(data?.items) ? data.items
          : Array.isArray(data?.albums) ? data.albums
          : Array.isArray(data) ? data : [];
        if (!albums.length) {
          statusEl.className = "status";
          statusEl.textContent = t("ops.spotify_match.search.empty");
          return;
        }
        statusEl.className = "status ok";
        statusEl.textContent = "";
        resultsEl.innerHTML = albums.map((a) => {
          const aId = escapeHtml(String(a.spotify_album_id || a.id || "").trim());
          const aName = escapeHtml(String(a.name || a.album_name || "-").trim());
          const aArtist = escapeHtml(String(
            a.artist || (Array.isArray(a.artists) ? a.artists.map(ar => ar.name || ar).join(", ") : "")
          ).trim() || "-");
          const aYear = escapeHtml(String(a.release_date || a.year || "").substring(0, 4) || "");
          const coverUrl = String(a.image_url || a.cover_image_url || a.thumbnail_url ||
            (Array.isArray(a.images) && a.images.length ? (a.images[a.images.length - 1]?.url || "") : "")
          ).trim();
          const coverHtml = coverUrl
            ? `<img class="spotify-match-result-cover" src="${escapeHtml(coverUrl)}" alt="${aName}" loading="lazy" />`
            : `<div class="spotify-match-result-cover-placeholder">${aArtist.substring(0, 2).toUpperCase() || "♪"}</div>`;
          return `
            <div class="spotify-match-result-row">
              ${coverHtml}
              <div class="spotify-match-result-info">
                <div class="spotify-match-result-title">${aName}</div>
                <div class="spotify-match-result-meta">${aArtist}${aYear ? " · " + aYear : ""}</div>
              </div>
              <button class="btn ghost" type="button" data-spotify-match-pick="${aId}" title="${aName}">${escapeHtml(t("ops.spotify_match.result.select"))}</button>
            </div>
          `;
        }).join("");
      } catch (err) {
        statusEl.className = "status err";
        statusEl.textContent = t("ops.spotify_match.search.failed", { error: err.message });
      }
    }

    async function saveSpotifyMatch(albumId) {
      if (!_spotifyMatchMasterId || !albumId) return;
      const statusEl = $("spotifyMatchStatus");
      statusEl.className = "status ok";
      statusEl.textContent = t("ops.spotify_match.save.saving");
      try {
        const res = await fetch(`/album-masters/${_spotifyMatchMasterId}/spotify/match`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ spotify_album_id: albumId }),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
        statusEl.className = "status ok";
        statusEl.textContent = t("ops.spotify_match.save.ok");
        setTimeout(() => {
          closeSpotifyMatchModal();
          loadOpsExceptionCounts({ silent: true }).catch(() => {});
          loadOpsExceptionItems({ silent: true }).catch(() => {});
        }, 900);
      } catch (err) {
        statusEl.className = "status err";
        statusEl.textContent = t("ops.spotify_match.save.failed", { error: err.message });
      }
    }

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
