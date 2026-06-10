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

    // ── 로컬 이미지 관리 ──────────────────────────────────────────
    // ─────────────────────────────────────────────────────────────

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
    var _DOMAIN_LABEL = {
      KOREA:'가요', JAPAN:'J-POP', WESTERN:'팝/웨스턴',
      GREATER_CHINA:'C-Pop', OTHER_ASIA:'아시아', WORLD:'월드',
      UNASSIGNED:'미분류', UNKNOWN:'미분류',
    };
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
