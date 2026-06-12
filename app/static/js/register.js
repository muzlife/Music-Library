    let goodsMode = "search";
    let goodsSearchResults = [];
    let goodsSearchTotalCount = 0;
    let goodsSelectedItemId = null;
    let goodsSelectedItem = null;
    let goodsSearchLoading = false;
    let goodsManageAlbumMasterMappings = [];
    let goodsManageArtistMappings = [];
    let goodsManageLabelMappings = [];
    let goodsManageCollectibleRelations = [];

    function registerLookupCandidateKey(candidate, index = -1) {
      const source = String(candidate?.source || "").trim().toUpperCase();
      const externalId = String(candidate?.external_id || "").trim();
      if (source && externalId) return `${source}#${externalId}`;
      const title = String(candidate?.title || "").trim();
      return `${source || "UNKNOWN"}#${externalId || title || index}`;
    }

    function registerLookupPendingCount() {
      return registerLookupSaveQueue.length + (registerLookupSaveInFlight ? 1 : 0);
    }

    function syncGoodsSpecVisibility(category, ids) {
      const cat = String(category || "").toUpperCase();
      const poster = $(ids.poster);
      const tshirt = $(ids.tshirt);
      const cup = $(ids.cup);
      const hat = $(ids.hat);
      if (poster) setDisplayMode(poster, cat === "POSTER" ? "block" : "none");
      if (tshirt) setDisplayMode(tshirt, cat === "T_SHIRT" ? "block" : "none");
      if (cup) setDisplayMode(cup, cat === "CUP" ? "block" : "none");
      if (hat) setDisplayMode(hat, cat === "HAT" ? "block" : "none");
    }

    function registerImageGallery(key, row, opts = {}) {
      const galleryKey = String(key || "").trim();
      if (!galleryKey) return "";
      const items = collectGalleryItems(row);
      if (!items.length) {
        imageGalleryRegistry.delete(galleryKey);
        return "";
      }
      imageGalleryRegistry.set(galleryKey, {
        key: galleryKey,
        title: String(opts.title || row?.title || row?.item_name_override || t("image_gallery.title.default")).trim() || t("image_gallery.title.default"),
        subtitle: String(opts.subtitle || "").trim() || t("image_gallery.subtitle.default"),
        items,
      });
      return galleryKey;
    }

    function purchaseImportVendorLabel(value) {
      const code = String(value || "").trim().toUpperCase();
      if (code === "SAILMUSIC") return "Sailmusic";
      if (code === "AMAZON") return "Amazon";
      if (code === "EBAY") return "eBay";
      return code || t("media.register.purchase.vendor.other");
    }

    function purchaseImportStatusLabel(value) {
      const code = String(value || "").trim().toUpperCase();
      if (code === "CREATED") return t("media.register.purchase.queue.status.created");
      if (code === "IGNORED") return t("media.register.purchase.queue.status.ignored");
      return t("media.register.purchase.queue.status.pending");
    }

    function purchaseImportMoneyText(value, currency = "KRW") {
      if (value === null || value === undefined) return "-";
      if (typeof value === "string" && !value.trim()) return "-";
      const amount = Number(value);
      if (!Number.isFinite(amount)) return "-";
      const code = String(currency || "").trim().toUpperCase();
      if (code === "KRW") {
        const rounded = Math.round(amount);
        return `${rounded.toLocaleString(currentLocaleTag())} KRW`;
      }
      if (code === "USD" || code === "GBP") {
        return `${amount.toLocaleString(currentLocaleTag(), { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${code}`.trim();
      }
      const rounded = Math.round(amount);
      return `${rounded.toLocaleString(currentLocaleTag())} ${code || ""}`.trim();
    }

    function purchaseImportItemUrl(row) {
      const payload = row && typeof row.raw_payload === "object" && row.raw_payload ? row.raw_payload : {};
      return String(row?.item_url || payload.item_url || "").trim();
    }

    function purchaseImportImageUrl(row) {
      const payload = row && typeof row.raw_payload === "object" && row.raw_payload ? row.raw_payload : {};
      return String(row?.image_url || payload.image_url || "").trim();
    }

    function purchaseImportDisplayTitle(row) {
      const payload = row && typeof row.raw_payload === "object" && row.raw_payload ? row.raw_payload : {};
      const vendorCode = String(row?.vendor_code || payload.vendor_code || "").trim().toUpperCase();
      const listingTitle = String(payload.listing_title || "").trim();
      if (vendorCode === "EBAY" && listingTitle) return listingTitle;
      return String(row?.item_name || "").trim() || "-";
    }

    function purchaseImportParsedArtistName(row) {
      const payload = row && typeof row.raw_payload === "object" && row.raw_payload ? row.raw_payload : {};
      return String(payload.parsed_search_artist_name || row?.artist_name || "").trim();
    }

    function purchaseImportParsedItemName(row) {
      const payload = row && typeof row.raw_payload === "object" && row.raw_payload ? row.raw_payload : {};
      return String(payload.parsed_search_item_name || row?.item_name || "").trim();
    }

    function purchaseImportCoverThumbHtml(row) {
      const imageUrl = purchaseImportImageUrl(row);
      const itemUrl = purchaseImportItemUrl(row);
      const title = purchaseImportDisplayTitle(row) || "purchase";
      const thumb = imageUrl
        ? `<div class="table-cover-thumb"><img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(title)}" /></div>`
        : `<div class="table-cover-thumb">-</div>`;
      if (!itemUrl) return thumb;
      return `<a href="${escapeHtml(itemUrl)}" target="_blank" rel="noreferrer" title="${escapeHtml(t("media.register.purchase.action.open_item"))}">${thumb}</a>`;
    }

    function purchaseImportItemNameHtml(row) {
      const artist = purchaseImportParsedArtistName(row);
      const parsedItemName = purchaseImportParsedItemName(row);
      const title = purchaseImportDisplayTitle(row);
      const itemUrl = purchaseImportItemUrl(row);
      const titleHtml = (!itemUrl || title === "-")
        ? escapeHtml(title)
        : `<a href="${escapeHtml(itemUrl)}" target="_blank" rel="noreferrer">${escapeHtml(title)}</a>`;
      if (!artist || !parsedItemName || title !== parsedItemName) return titleHtml;
      return `<div class="mini muted">${escapeHtml(artist)}</div><div>${titleHtml}</div>`;
    }

    function purchaseImportRowDetailSummaryHtml(row) {
      const payload = row && typeof row.raw_payload === "object" && row.raw_payload ? row.raw_payload : {};
      const bits = [];
      const artist = String(payload.detail_page_artist_name || "").trim();
      const label = String(payload.detail_page_label_name || payload.parsed_label_name || "").trim();
      const released = String(payload.detail_page_released_date || "").trim();
      if (artist) bits.push(escapeHtml(t("media.register.purchase.detail.artist", { value: artist })));
      if (released) bits.push(escapeHtml(t("media.register.purchase.detail.released", { value: released })));
      if (label) bits.push(escapeHtml(t("media.register.purchase.detail.label", { value: label })));
      if (!bits.length) return "";
      return `<div class="mini muted u-mt-4">${bits.join(" | ")}</div>`;
    }

    function purchaseImportPayloadBase() {
      const rawContent = currentPurchaseImportRawContent();
      const sourceType = purchaseImportFileContentBase64 ? "FILE_UPLOAD" : (
        rawContent && rawContent.includes("<") && rawContent.includes(">") ? "EMAIL_HTML" : "EMAIL_TEXT"
      );
      return {
        vendor_code: String($("purchaseImportVendorCode")?.value || "OTHER").trim().toUpperCase() || "OTHER",
        source_type: sourceType,
        source_ref: String($("purchaseImportSourceRef")?.value || "").trim() || null,
        email_from: String($("purchaseImportEmailFrom")?.value || "").trim() || null,
        email_subject: String($("purchaseImportEmailSubject")?.value || "").trim() || null,
      };
    }

    function resetPurchaseImportForm() {
      $("purchaseImportSourceType").value = "FILE_UPLOAD";
      $("purchaseImportVendorCode").value = "OTHER";
      $("purchaseImportEmailFrom").value = "";
      $("purchaseImportEmailSubject").value = "";
      $("purchaseImportSourceRef").value = "";
      $("purchaseImportRawContent").value = "";
      if ($("purchaseImportFile")) $("purchaseImportFile").value = "";
      purchaseImportFileContent = "";
      purchaseImportFileContentBase64 = "";
      purchaseImportFileName = "";
      setPurchaseImportFileInfo(t("media.register.purchase.status.file_none"));
      purchaseImportPreviewItems = [];
      renderPurchaseImportPreview([]);
      setStatus("purchaseImportStatus", "", "");
    }

    function renderPurchaseImportPreview(items) {
      purchaseImportPreviewItems = Array.isArray(items) ? items.slice() : [];
      const body = $("purchaseImportPreviewBody");
      const count = $("purchaseImportPreviewCount");
      if (count) count.textContent = countWithUnit(purchaseImportPreviewItems.length);
      if (!body) return;
      if (!purchaseImportPreviewItems.length) {
        body.innerHTML = `<tr><td colspan="8" class="muted">${escapeHtml(t("media.register.purchase.status.preview_empty"))}</td></tr>`;
        return;
      }
      body.innerHTML = purchaseImportPreviewItems.map((row, index) => `
        <tr>
          <td>${formatCount(index + 1)}</td>
          <td>${purchaseImportCoverThumbHtml(row)}</td>
          <td>${escapeHtml(String(row.artist_name || "").trim() || "-")}</td>
          <td>${purchaseImportItemNameHtml(row)}</td>
          <td>${escapeHtml(String(row.media_format || "").trim() || "-")}</td>
          <td>${formatCount(Number(row.quantity || 1))}</td>
          <td>${escapeHtml(purchaseImportMoneyText(row.unit_price, row.currency_code || "KRW"))}</td>
          <td>${escapeHtml(purchaseImportMoneyText(row.line_total, row.currency_code || "KRW"))}</td>
        </tr>
      `).join("");
    }

    function purchaseImportQueueStateFor(queueId) {
      const key = String(Number(queueId || 0) || "");
      if (!key) {
        return {
          expanded: false,
          loading: false,
          source: String($("purchaseImportCandidateSource")?.value || "AUTO").trim().toUpperCase() || "AUTO",
          query: "",
          artistName: "",
          itemName: "",
          queryOverride: "",
          candidates: [],
          selectedIdx: -1,
          error: "",
        };
      }
      if (!purchaseImportQueueCandidateState[key]) {
        purchaseImportQueueCandidateState[key] = {
          expanded: false,
          loading: false,
          source: String($("purchaseImportCandidateSource")?.value || "AUTO").trim().toUpperCase() || "AUTO",
          query: "",
          artistName: "",
          itemName: "",
          queryOverride: "",
          candidates: [],
          selectedIdx: -1,
          error: "",
        };
      }
      return purchaseImportQueueCandidateState[key];
    }

    function getPurchaseImportCandidateLookupOptions() {
      return {
        source: String($("purchaseImportCandidateSource")?.value || "AUTO").trim().toUpperCase() || "AUTO",
        limit: Math.max(1, Math.min(20, Number($("purchaseImportCandidateLimit")?.value || 5))),
      };
    }

    function purchaseImportAmazonMetaHtml(row) {
      const payload = row && typeof row.raw_payload === "object" && row.raw_payload ? row.raw_payload : {};
      const asin = String(payload.asin || "").trim();
      const marketplace = String(payload.marketplace || "").trim();
      const itemUrl = purchaseImportItemUrl(row);
      const detailArtist = String(payload.detail_page_artist_name || "").trim();
      const detailLabel = String(payload.detail_page_label_name || "").trim();
      const detailReleased = String(payload.detail_page_released_date || "").trim();
      if (!asin && !itemUrl && !detailArtist && !detailLabel && !detailReleased) return "";
      const bits = [];
      if (asin) bits.push(`ASIN ${escapeHtml(asin)}`);
      if (marketplace) bits.push(`Amazon ${escapeHtml(marketplace)}`);
      if (itemUrl) {
        bits.push(`<a href="${escapeHtml(itemUrl)}" target="_blank" rel="noreferrer">${escapeHtml(t("media.register.purchase.meta.amazon_detail"))}</a>`);
      }
      if (detailArtist) bits.push(escapeHtml(t("media.register.purchase.detail.artist", { value: detailArtist })));
      if (detailLabel) bits.push(escapeHtml(t("media.register.purchase.detail.label", { value: detailLabel })));
      if (detailReleased) bits.push(escapeHtml(t("media.register.purchase.detail.released", { value: detailReleased })));
      return `<div class="mini mini-mb-8">${bits.join(" | ")}</div>`;
    }

    function renderPurchaseImportQueueDetails(row, state) {
      const queueId = Number(row?.id || 0);
      const queryText = String(state?.query || "").trim();
      const selectedCandidate = Number(state?.selectedIdx) >= 0 && Array.isArray(state?.candidates)
        ? state.candidates[state.selectedIdx]
        : null;
      const canApplyArtist = Boolean(selectedCandidate?.artist_or_brand);
      let bodyHtml = `<div class='mini muted'>${escapeHtml(t("media.register.purchase.queue.details.empty"))}</div>`;
      if (state?.loading) {
        bodyHtml = `<div class='mini'>${escapeHtml(t("media.register.purchase.queue.details.loading"))}</div>`;
      } else if (state?.error) {
        bodyHtml = `<div class="mini console-inline-error">${escapeHtml(state.error)}</div>`;
      } else if (Array.isArray(state?.candidates) && state.candidates.length) {
        bodyHtml = `<div class="source-workbench-candidates">${state.candidates.map((candidate, idx) => buildPurchaseImportCandidateHtml(queueId, state, candidate, idx)).join("")}</div>`;
      }
      return `
        <tr class="purchase-import-candidate-row">
          <td colspan="9">
            <div class="purchase-import-candidate-box">
              <div class="purchase-import-candidate-head">
                <div>
                  <strong>${escapeHtml(t("media.register.purchase.queue.details.title"))}</strong>
                  <div class="mini">${escapeHtml(queryText ? t("media.register.purchase.queue.details.query_prefix", { query: queryText }) : t("media.register.purchase.queue.details.query_empty"))}</div>
                </div>
                <div class="row row-gap-6">
                  <button class="btn ghost tiny" type="button" data-purchase-import-enrich="${queueId}">${escapeHtml(t("media.register.purchase.queue.action.enrich"))}</button>
                  <button class="btn ghost tiny" type="button" data-purchase-import-apply-artist="${queueId}" ${canApplyArtist ? "" : "disabled"}>${escapeHtml(t("media.register.purchase.queue.action.apply_candidate_artist"))}</button>
                </div>
              </div>
              ${purchaseImportAmazonMetaHtml(row)}
              <div class="purchase-import-candidate-search-row">
                <div class="purchase-import-candidate-search-field">
                  <label class="mini" for="purchaseImportArtistOverride-${queueId}">${escapeHtml(t("media.register.purchase.queue.field.artist_override.label"))}</label>
                  <input id="purchaseImportArtistOverride-${queueId}" type="text" value="${escapeHtml(String(state?.artistName || row?.artist_name || '').trim())}" data-purchase-import-artist="${queueId}" />
                </div>
                <div class="purchase-import-candidate-search-field">
                  <label class="mini" for="purchaseImportItemOverride-${queueId}">${escapeHtml(t("media.register.purchase.queue.field.item_override.label"))}</label>
                  <input id="purchaseImportItemOverride-${queueId}" type="text" value="${escapeHtml(String(state?.itemName || row?.item_name || '').trim())}" data-purchase-import-item="${queueId}" />
                </div>
                <div class="purchase-import-candidate-search-field">
                  <label class="mini" for="purchaseImportQueryOverride-${queueId}">${escapeHtml(t("media.register.purchase.queue.field.query_override.label"))}</label>
                  <input id="purchaseImportQueryOverride-${queueId}" type="text" value="${escapeHtml(String(state?.queryOverride || '').trim())}" data-purchase-import-query="${queueId}" />
                </div>
                <div class="purchase-import-candidate-search-field">
                  <label class="mini">${escapeHtml(t("media.register.purchase.queue.field.candidate_source.label"))}</label>
                  <div class="row row-gap-4">
                    <button class="btn ghost tiny" type="button" data-purchase-import-candidates-source="${queueId}:DISCOGS">Discogs</button>
                    <button class="btn ghost tiny" type="button" data-purchase-import-candidates-source="${queueId}:MANIADB">매니아디비</button>
                    <button class="btn ghost tiny" type="button" data-purchase-import-candidates-source="${queueId}:ALADIN">알라딘</button>
                  </div>
                </div>
              </div>
              ${bodyHtml}
            </div>
          </td>
        </tr>
      `;
    }

    function renderPurchaseImportQueue(items) {
      purchaseImportQueueItems = Array.isArray(items) ? items.slice() : [];
      const nextCandidateState = {};
      for (const row of purchaseImportQueueItems) {
        const key = String(Number(row?.id || 0) || "");
        if (!key) continue;
        const prevState = purchaseImportQueueCandidateState[key] || {};
        const prevCandidates = Array.isArray(prevState.candidates) ? prevState.candidates : [];
        const prevSelectedIdx = Number.isInteger(prevState.selectedIdx) ? prevState.selectedIdx : -1;
        nextCandidateState[key] = {
          ...prevState,
          expanded: Boolean(prevState.expanded),
          loading: false,
          source: String(prevState.source || $("purchaseImportCandidateSource")?.value || "AUTO").trim().toUpperCase() || "AUTO",
          query: String(prevState.query || "").trim(),
          artistName: String(prevState.artistName || purchaseImportParsedArtistName(row) || "").trim(),
          itemName: String(prevState.itemName || purchaseImportParsedItemName(row) || "").trim(),
          queryOverride: String(prevState.queryOverride || "").trim(),
          candidates: prevCandidates,
          selectedIdx: prevCandidates[prevSelectedIdx] ? prevSelectedIdx : (prevCandidates.length ? 0 : -1),
          error: String(prevState.error || ""),
        };
      }
      purchaseImportQueueCandidateState = nextCandidateState;
      const body = $("purchaseImportQueueBody");
      const count = $("purchaseImportQueueCount");
      if (count) count.textContent = countWithUnit(purchaseImportQueueItems.length);
      if (!body) return;
      if (!purchaseImportQueueItems.length) {
        body.innerHTML = `<tr><td colspan="9" class="muted">${escapeHtml(t("media.register.purchase.queue.status.empty"))}</td></tr>`;
        return;
      }
      body.innerHTML = purchaseImportQueueItems.map((row) => {
        const queueId = Number(row.id || 0);
        const canCreate = String(row.queue_status || "").trim().toUpperCase() === "PENDING";
        const candidateState = purchaseImportQueueStateFor(queueId);
        const candidateSummary = candidateState.loading
          ? `<div class='mini muted'>${escapeHtml(t("media.register.purchase.queue.status.candidates_loading"))}</div>`
          : (Array.isArray(candidateState.candidates) && candidateState.candidates.length)
            ? `<div class="mini mini-mt-4">${escapeHtml(t("media.register.purchase.queue.status.candidates_summary", {
                count: formatCount(candidateState.candidates.length),
                source: String(candidateState.candidates[candidateState.selectedIdx]?.source || candidateState.candidates[0]?.source || "-"),
              }))}</div>`
            : (candidateState.error
              ? `<div class="mini console-inline-error mt-4">${escapeHtml(candidateState.error)}</div>`
              : "");
        const detailsHtml = candidateState.expanded ? renderPurchaseImportQueueDetails(row, candidateState) : "";
        return `
          <tr>
            <td>${formatCount(queueId)}</td>
            <td>${escapeHtml(purchaseImportVendorLabel(row.vendor_code))}</td>
            <td>${purchaseImportCoverThumbHtml(row)}</td>
            <td>${purchaseImportItemNameHtml(row)}${purchaseImportRowDetailSummaryHtml(row)}</td>
            <td>${escapeHtml(String(row.media_format || "").trim() || "-")}</td>
            <td>${formatCount(Number(row.quantity || 1))}</td>
            <td>${escapeHtml(purchaseImportMoneyText(row.line_total ?? row.unit_price, row.currency_code || "KRW"))}</td>
            <td>${escapeHtml(purchaseImportStatusLabel(row.queue_status))}</td>
            <td>
              <div class="row row-gap-4-end">
                <button class="btn ghost tiny" type="button" data-purchase-import-enrich="${queueId}">${escapeHtml(t("media.register.purchase.queue.action.enrich"))}</button>
                <button class="btn ghost tiny" type="button" data-purchase-import-candidates="${queueId}" ${canCreate ? "" : "disabled"}>${escapeHtml(t("media.register.purchase.queue.action.lookup_candidates"))}</button>
                <button class="btn ghost tiny" type="button" data-purchase-import-create="${queueId}" ${canCreate ? "" : "disabled"}>${escapeHtml(t("media.register.purchase.queue.action.create_owned"))}</button>
                <button class="btn ghost tiny" type="button" data-purchase-import-ignore="${queueId}" ${canCreate ? "" : "disabled"}>${escapeHtml(t("media.register.purchase.queue.action.ignore"))}</button>
              </div>
              ${candidateSummary}
            </td>
          </tr>
          ${detailsHtml}
        `;
      }).join("");
    }

    function updatePurchaseImportCandidateSearchText(queueId, field, value) {
      const id = Number(queueId || 0);
      if (!id) return;
      const state = purchaseImportQueueStateFor(id);
      if (field === "source") state.source = String(value || "AUTO").trim().toUpperCase() || "AUTO";
      if (field === "artist") state.artistName = String(value || "").trim();
      if (field === "item") state.itemName = String(value || "").trim();
      if (field === "query") state.queryOverride = String(value || "").trim();
    }

    function applyPurchaseImportCandidateArtist(queueId) {
      const id = Number(queueId || 0);
      if (!id) return;
      const state = purchaseImportQueueStateFor(id);
      const candidate = Array.isArray(state.candidates) ? state.candidates[state.selectedIdx] : null;
      const artist = String(candidate?.artist_or_brand || "").trim();
      if (!artist) {
        setStatus("purchaseImportQueueStatus", "err", t("media.register.purchase.queue.status.apply_artist_empty"));
        return;
      }
      state.artistName = artist;
      state.expanded = true;
      renderPurchaseImportQueue(purchaseImportQueueItems);
      setStatus("purchaseImportQueueStatus", "ok", t("media.register.purchase.queue.status.apply_artist_complete", {
        id,
        artist,
      }));
    }

    function renderRegisterLookupProviderStatusBadges(entries = []) {
      const el = $("barcodeProviderStatusBadges");
      if (!el) return;
      const rows = Array.isArray(entries)
        ? entries
            .filter((entry) => entry && entry.kind && entry.source)
            .map((entry) => ({
              kind: String(entry.kind),
              source: String(entry.source).trim().toUpperCase(),
            }))
        : [];
      if (!rows.length) {
        setDisplayMode(el, "none");
        el.innerHTML = "";
        return;
      }
      setDisplayMode(el, "flex");
      el.innerHTML = rows.map((entry) => `
        <span class="operator-status-pill ${entry.kind === "unavailable" ? "cancelled" : "requested"}">
          ${escapeHtml(
            entry.kind === "unavailable"
              ? t("media.register.api_lookup.provider_status.unavailable", { source: entry.source })
              : t("media.register.api_lookup.provider_status.fallback_results", { source: entry.source })
          )}
        </span>
      `).join("");
    }

    function registerLookupLocationStateFor(index) {
      const current = registerLookupLocationState[String(index)] || {};
      return {
        cabinet_name: String(current.cabinet_name || "").trim(),
        column_code: String(current.column_code || "").trim(),
        cell_code: String(current.cell_code || "").trim(),
      };
    }

    function registerLookupCandidateSortYear(candidate) {
      const releasedDate = String(candidate?.released_date || "").trim();
      const releaseYear = Number(candidate?.release_year || 0) || 0;
      if (/^\d{4}-\d{2}-\d{2}$/.test(releasedDate)) {
        return Number(releasedDate.slice(0, 4)) || 9999;
      }
      return releaseYear > 0 ? releaseYear : 9999;
    }

    function registerLookupCandidateFormatRank(candidate) {
      const category = String(inferMusicCategoryFromMetadata(candidate) || "").trim().toUpperCase();
      const ranking = {
        CD: 1,
        LP: 2,
        CASSETTE: 3,
        "8TRACK": 4,
        DIGITAL: 5,
        "REEL_TO_REEL": 6,
      };
      return Number(ranking[category] || 99);
    }

    function goodsCategoryLabel(value) {
      const code = String(value || "").trim().toUpperCase();
      if (code === "POSTER") return t("collectibles.category.poster");
      if (code === "T_SHIRT") return t("collectibles.category.t_shirt");
      if (code === "LIGHT_STICK") return t("collectibles.category.light_stick");
      if (code === "HAT") return t("collectibles.category.hat");
      if (code === "BAG") return t("collectibles.category.bag");
      if (code === "CUP") return t("collectibles.category.cup");
      if (code === "OTHER") return t("collectibles.category.other");
      return code || "-";
    }

    function goodsStatusLabel(value) {
      const code = String(value || "").trim().toUpperCase();
      if (code === "ACTIVE") return t("collectibles.item_status.active");
      if (code === "ARCHIVED") return t("collectibles.item_status.archived");
      return code || "-";
    }

    function resetGoodsRegisterForm(options = {}) {
      $("goodsRegisterCategory").value = "POSTER";
      $("goodsRegisterQuantity").value = "1";
      $("goodsRegisterSizeGroup").value = "GOODS";
      $("goodsRegisterName").value = "";
      $("goodsRegisterStatus").value = "ACTIVE";
      $("goodsRegisterSlotId").value = "";
      $("goodsRegisterDomainCode").value = "";
      $("goodsRegisterDescription").value = "";
      $("goodsRegisterMemoryNote").value = "";
      $("goodsRegisterImageUrls").value = "";
      $("goodsRegisterAlbumMasterId").value = "";
      $("goodsRegisterLinkedOwnedItemId").value = "";
      $("goodsRegisterArtistNames").value = "";
      $("goodsRegisterLabelNames").value = "";
      if (!options.preserveStatus) {
        setStatus("goodsRegisterStatusLine", "", "");
      }
    }

    function syncGoodsModeUi() {
      const items = [
        { id: "search", btn: "goodsSearchModeBtn", panel: "goodsSearchSurface" },
        { id: "manage", btn: "goodsManageModeBtn", panel: "goodsManageSurface" },
        { id: "register", btn: "goodsRegisterModeBtn", panel: "goodsRegisterSurface" },
      ];
      for (const item of items) {
        const active = item.id === goodsMode;
        $(item.btn)?.classList.toggle("active", active);
        $(item.panel)?.classList.toggle("active", active);
      }
      const hasSelection = Boolean(goodsSelectedItem && Number(goodsSelectedItemId || 0) > 0);
      setDisplayIfPresent("goodsManageEmptyState", hasSelection ? "none" : "block");
      setDisplayIfPresent("goodsManageContent", hasSelection ? "block" : "none");
    }

    function goodsMappingAlbumMasterLabel(row) {
      if (!row || typeof row !== "object") return "-";
      const title = String(row.title || "").trim() || `album_master_id=${Number(row.album_master_id || 0)}`;
      const artist = String(row.artist_or_brand || "").trim();
      return artist ? `${title} / ${artist}` : title;
    }

    function renderGoodsChipList(containerId, items, mapType) {
      const container = $(containerId);
      if (!container) return;
      const rows = Array.isArray(items) ? items : [];
      if (!rows.length) {
        container.innerHTML = `<div class='mini muted'>${escapeHtml(t("collectibles.mapping.state.empty"))}</div>`;
        return;
      }
      container.innerHTML = rows.map((row, index) => {
        const label = mapType === "album_master"
          ? goodsMappingAlbumMasterLabel(row)
          : String(row || "").trim();
        return `
          <span class="goods-chip">
            <span>${escapeHtml(label)}</span>
            <button type="button" data-goods-remove-map="${escapeHtml(mapType)}" data-goods-map-index="${index}">${escapeHtml(t("common.action.delete"))}</button>
          </span>
        `;
      }).join("");
    }

    function renderGoodsManageMappings() {
      renderGoodsChipList("goodsAlbumMasterMapList", goodsManageAlbumMasterMappings, "album_master");
      renderGoodsCollectibleRelationList();
    }

    function goodsRelationTypeLabel(code) {
      const normalized = String(code || "").trim().toUpperCase();
      if (normalized === "SERIES") return t("collectibles.relation_type.series");
      if (normalized === "VARIANT") return t("collectibles.relation_type.variant");
      if (normalized === "SET_MEMBER") return t("collectibles.relation_type.set_member");
      if (normalized === "RELATED") return t("collectibles.relation_type.related");
      if (normalized === "PROMO_FOR") return t("collectibles.relation_type.promo_for");
      return normalized || "-";
    }

    function renderGoodsCollectibleRelationList() {
      const container = $("goodsCollectibleRelationMapList");
      if (!container) return;
      const rows = Array.isArray(goodsManageCollectibleRelations) ? goodsManageCollectibleRelations : [];
      if (!rows.length) {
        container.innerHTML = `<div class='mini muted'>${escapeHtml(t("collectibles.mapping.state.empty"))}</div>`;
        return;
      }
      container.innerHTML = rows.map((row, index) => {
        const linkedName = String(row.linked_goods_name || "").trim() || `goods_item_id=${Number(row.linked_goods_item_id || 0)}`;
        const linkedCategory = String(row.linked_category || "").trim();
        const note = String(row.note || "").trim();
        const label = [
          goodsRelationTypeLabel(row.relation_type),
          linkedName,
          linkedCategory ? `(${goodsCategoryLabel(linkedCategory)})` : "",
          note ? `- ${note}` : "",
        ].filter((value) => value).join(" ");
        return `
          <span class="goods-chip">
            <span>${escapeHtml(label)}</span>
            <button type="button" data-goods-remove-map="collectible" data-goods-map-index="${index}">${escapeHtml(t("common.action.delete"))}</button>
          </span>
        `;
      }).join("");
    }

    function renderGoodsAlbumMasterTargetResults(items) {
      const container = $("goodsManageAlbumMasterResults");
      if (!container) return;
      const rows = Array.isArray(items) ? items : [];
      if (!rows.length) {
        container.innerHTML = `<div class='mini muted'>${escapeHtml(t("collectibles.mapping.results.empty"))}</div>`;
        return;
      }
      container.innerHTML = rows.map((row) => `
        <div class="goods-target-row">
          <div class="u-minw-0">
            <strong>${escapeHtml(String(row.label || row.value || "").trim() || "-")}</strong>
          </div>
          <button
            class="btn ghost tiny"
            type="button"
            data-goods-add-album-master="${Number(row.value || 0)}"
            data-goods-add-album-master-title="${escapeHtml(String(row.title || row.label || "").trim())}"
            data-goods-add-album-master-artist="${escapeHtml(String(row.artist_or_brand || "").trim())}"
          >${escapeHtml(t("collectibles.mapping.action.connect"))}</button>
        </div>
      `).join("");
    }

    function renderGoodsCollectibleTargetResults(items) {
      const container = $("goodsManageCollectibleResults");
      if (!container) return;
      const rows = Array.isArray(items) ? items : [];
      if (!rows.length) {
        container.innerHTML = `<div class='mini muted'>${escapeHtml(t("collectibles.mapping.results.empty"))}</div>`;
        return;
      }
      container.innerHTML = rows.map((row) => `
        <div class="goods-target-row">
          <div class="u-minw-0">
            <strong>${escapeHtml(String(row.goods_name || row.label || "").trim() || "-")}</strong>
            <div class="mini muted">${escapeHtml(goodsCategoryLabel(String(row.category || "").trim().toUpperCase()))}</div>
          </div>
          <button
            class="btn ghost tiny"
            type="button"
            data-goods-add-collectible="${Number(row.goods_item_id || row.value || 0)}"
            data-goods-add-collectible-name="${escapeHtml(String(row.goods_name || row.label || "").trim())}"
            data-goods-add-collectible-category="${escapeHtml(String(row.category || "").trim())}"
          >${escapeHtml(t("collectibles.mapping.action.connect"))}</button>
        </div>
      `).join("");
    }

    function renderGoodsSearchResults() {
      const container = $("goodsSearchResults");
      const count = $("goodsSearchCount");
      if (count) {
        count.textContent = countWithUnit(goodsSearchTotalCount);
      }
      if (!container) return;
      if (goodsSearchLoading) {
        container.innerHTML = `<div class='mini muted'>${escapeHtml(t("collectibles.search.loading"))}</div>`;
        return;
      }
      if (!goodsSearchResults.length) {
        container.innerHTML = `<div class='mini muted'>${escapeHtml(t("collectibles.search.empty"))}</div>`;
        return;
      }
      container.innerHTML = goodsSearchResults.map((row) => {
        const imageUrl = String(row.primary_image_url || (Array.isArray(row.image_urls) ? row.image_urls[0] : "") || "").trim();
        const slotText = String(row.slot_display_name || "").trim() || t("common.unspecified");
        const domainText = row.domain_code ? dashboardDomainLabel(row.domain_code) : t("common.unspecified");
        const linkedCount = Number(row.product_link_count || 0)
          || (
            Number((row.album_master_mappings || []).length)
            + Number((row.artist_mappings || []).length)
            + Number((row.label_mappings || []).length)
          );
        const collectibleRelationCount = Number(row.collectible_relation_count || 0);
        const relationBadges = Array.isArray(row.relation_badges)
          ? row.relation_badges.map((badge) => goodsRelationTypeLabel(badge)).filter((badge) => badge)
          : [];
        const relationPreview = Array.isArray(row.collectible_relation_preview)
          ? row.collectible_relation_preview.slice(0, 2).map((relation) => {
              const relationLabel = goodsRelationTypeLabel(relation?.relation_type);
              const relationName = String(relation?.linked_goods_name || "").trim();
              return [relationLabel, relationName].filter((value) => value).join(": ");
            }).filter((text) => text)
          : [];
        return `
          <button type="button" class="goods-result-item" data-goods-open="${Number(row.id || 0)}">
            <div class="album-result-cover">
              ${imageUrl
                ? `<img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(String(row.goods_name || "-").trim())}" />`
                : `<span>${escapeHtml(goodsCategoryLabel(row.category))}</span>`}
            </div>
            <div class="album-result-main">
              <strong>${escapeHtml(String(row.goods_name || "-").trim())}</strong>
              <div class="goods-result-meta">
                <span class="tag">${escapeHtml(goodsCategoryLabel(row.category))}</span>
                <span>${escapeHtml(t("collectibles.search.meta.quantity", { quantity: String(row.quantity || 1) }))}</span>
                <span>${escapeHtml(goodsStatusLabel(row.status))}</span>
                <span>${escapeHtml(slotText)}</span>
                <span>${escapeHtml(dashboardSizeGroupLabel(row.size_group))}</span>
                <span>${escapeHtml(domainText)}</span>
                <span>${escapeHtml(t("collectibles.search.meta.links", { count: formatCount(linkedCount) }))}</span>
                <span>${escapeHtml(t("collectibles.search.meta.collectible_relations", { count: formatCount(row.collectible_relation_count || collectibleRelationCount) }))}</span>
              </div>
              ${relationBadges.length
                ? `<div class="goods-result-meta">${relationBadges.map((badge) => `<span class="tag">${escapeHtml(badge)}</span>`).join("")}</div>`
                : ""}
              ${relationPreview.length
                ? `<div class="mini muted">${escapeHtml(relationPreview.join(" / "))}</div>`
                : ""}
            </div>
          </button>
        `;
      }).join("");
    }

    function resetGoodsManageSelection() {
      goodsSelectedItemId = null;
      goodsSelectedItem = null;
      goodsManageAlbumMasterMappings = [];
      goodsManageArtistMappings = [];
      goodsManageLabelMappings = [];
      goodsManageCollectibleRelations = [];
      setValueIfPresent("goodsManageId", "");
      setValueIfPresent("goodsManageName", "");
      setValueIfPresent("goodsManageQuantity", "1");
      setValueIfPresent("goodsManageDescription", "");
      setValueIfPresent("goodsManageMemoryNote", "");
      setValueIfPresent("goodsManageImageUrls", "");
      setValueIfPresent("goodsManageAlbumMasterQuery", "");
      setValueIfPresent("goodsManageCollectibleQuery", "");
      setValueIfPresent("goodsManageRelationNote", "");
      if ($("goodsManageCategory")) $("goodsManageCategory").value = "POSTER";
      if ($("goodsManageStatus")) $("goodsManageStatus").value = "ACTIVE";
      if ($("goodsManageSizeGroup")) $("goodsManageSizeGroup").value = "GOODS";
      if ($("goodsManageSlotId")) $("goodsManageSlotId").value = "";
      if ($("goodsManageDomainCode")) $("goodsManageDomainCode").value = "";
      if ($("goodsManageRelationType")) $("goodsManageRelationType").value = "SERIES";
      setTextIfPresent("goodsManageHeading", t("collectibles.manage.default_heading"));
      setTextIfPresent("goodsManageMeta", "-");
      setHtmlIfPresent("goodsManageAlbumMasterResults", "");
      setHtmlIfPresent("goodsManageCollectibleResults", "");
      renderGoodsManageMappings();
      syncGoodsModeUi();
    }

    function applyGoodsManageItem(data) {
      goodsSelectedItemId = Number(data?.id || 0) || null;
      goodsSelectedItem = data && typeof data === "object" ? data : null;
      goodsManageAlbumMasterMappings = Array.isArray(data?.album_master_mappings)
        ? data.album_master_mappings.map((row) => ({
            album_master_id: Number(row.album_master_id || 0),
            title: String(row.title || "").trim(),
            artist_or_brand: String(row.artist_or_brand || "").trim() || null,
          })).filter((row) => row.album_master_id > 0)
        : [];
      goodsManageArtistMappings = Array.isArray(data?.artist_mappings)
        ? data.artist_mappings.map((row) => String(row || "").trim()).filter((row) => row)
        : [];
      goodsManageLabelMappings = Array.isArray(data?.label_mappings)
        ? data.label_mappings.map((row) => String(row || "").trim()).filter((row) => row)
        : [];
      goodsManageCollectibleRelations = Array.isArray(data?.collectible_relations)
        ? data.collectible_relations.map((row, index) => ({
            relation_type: String(row?.relation_type || "").trim().toUpperCase(),
            direction: String(row?.direction || "PEER").trim().toUpperCase(),
            linked_goods_item_id: Number(row?.linked_goods_item_id || 0),
            linked_goods_name: String(row?.linked_goods_name || "").trim(),
            linked_category: String(row?.linked_category || "").trim().toUpperCase() || null,
            note: String(row?.note || "").trim() || null,
            display_order: Number(row?.display_order ?? index) || index,
          })).filter((row) => row.linked_goods_item_id > 0)
        : [];
      $("goodsManageId").value = goodsSelectedItemId ? String(goodsSelectedItemId) : "";
      $("goodsManageCategory").value = String(data?.category || "POSTER").trim().toUpperCase();
      $("goodsManageQuantity").value = String(Math.max(1, Number(data?.quantity || 1)));
      $("goodsManageName").value = String(data?.goods_name || "").trim();
      $("goodsManageStatus").value = String(data?.status || "ACTIVE").trim().toUpperCase();
      $("goodsManageSizeGroup").value = String(data?.size_group || "GOODS").trim().toUpperCase();
      $("goodsManageSlotId").value = data?.storage_slot_id ? String(data.storage_slot_id) : "";
      $("goodsManageDomainCode").value = String(data?.domain_code || "").trim().toUpperCase();
      $("goodsManageDescription").value = String(data?.description || "").trim();
      $("goodsManageMemoryNote").value = String(data?.memory_note || "").trim();
      $("goodsManageImageUrls").value = joinLineList(Array.isArray(data?.image_urls) ? data.image_urls : []);
      $("goodsManageHeading").textContent = String(data?.goods_name || t("collectibles.manage.default_heading")).trim() || t("collectibles.manage.default_heading");
      $("goodsManageMeta").textContent = [
        goodsCategoryLabel(data?.category),
        data?.slot_display_name ? String(data.slot_display_name).trim() : t("common.unspecified"),
        goodsStatusLabel(data?.status),
      ].filter((row) => row && row !== "-").join(" · ") || "-";
      $("goodsManageAlbumMasterQuery").value = "";
      $("goodsManageCollectibleQuery").value = "";
      $("goodsManageRelationNote").value = "";
      $("goodsManageRelationType").value = "SERIES";
      $("goodsManageAlbumMasterResults").innerHTML = "";
      $("goodsManageCollectibleResults").innerHTML = "";
      setStatus("goodsManageStatusLine", "", "");
      setStatus("goodsManageMappingStatus", "", "");
      setStatus("goodsManageRelationStatus", "", "");
      renderGoodsManageMappings();
      syncGoodsModeUi();
    }

    function normalizeRegisteredMasterMergeId(value) {
      const id = Number(value || 0);
      return Number.isInteger(id) && id > 0 ? id : 0;
    }

    function registeredMasterMergeTargetIds() {
      return (registeredMasterMergeTargetItems || [])
        .map((row) => normalizeRegisteredMasterMergeId(row?.id))
        .filter((value) => value > 0);
    }

    function isRegisteredMasterMergeTargetId(albumMasterId) {
      const normalizedId = normalizeRegisteredMasterMergeId(albumMasterId);
      return normalizedId > 0 && registeredMasterMergeTargetIds().includes(normalizedId);
    }

    function registeredMasterMergeRepresentativeId() {
      return normalizeRegisteredMasterMergeId(registeredMasterMergeRepresentativeItem?.id);
    }

    function isRegisteredMasterMergeRepresentativeId(albumMasterId) {
      const normalizedId = normalizeRegisteredMasterMergeId(albumMasterId);
      return normalizedId > 0 && registeredMasterMergeRepresentativeId() === normalizedId;
    }

    function registeredMasterMergeRowSnapshot(row) {
      const rowId = normalizeRegisteredMasterMergeId(row?.id);
      if (!rowId) return null;
      return {
        id: rowId,
        source_code: String(row?.source_code || "-"),
        source_master_id: String(row?.source_master_id || "-"),
        title: String(row?.title || "-"),
        artist_or_brand: String(row?.artist_or_brand || "-"),
        release_year: row?.release_year ?? null,
        member_count: Number(row?.member_count || 0),
        cover_image_url: String(row?.cover_image_url || "").trim() || null,
      };
    }

    function registeredMasterMergeHeadingLabel(row) {
      const title = resolveAlbumMasterName(row);
      const artist = String(row?.artist_or_brand || "").trim();
      return artist ? `${artist} - ${title}` : title;
    }

    function registeredMasterMergeCardHtml(row, options = {}) {
      const title = registeredMasterMergeHeadingLabel(row);
      const rowId = normalizeRegisteredMasterMergeId(row?.id);
      const coverUrl = normalizeRenderableCoverUrl(row?.cover_image_url);
      const cover = coverUrl
        ? `<img src="${escapeHtml(coverUrl)}" alt="${escapeHtml(title)}" />`
        : escapeHtml(t("media.manage.related_versions.state.no_cover"));
      const actionsHtml = String(options.actionsHtml || "").trim();
      const contextBadge = String(options.contextBadge || "").trim();
      const order = Number(options.order || 0);
      const orderBadge = order > 0
        ? `<span class="registered-master-merge-order-badge">#${order}</span>`
        : "";
      const contextBadgeHtml = contextBadge
        ? `<span class="registered-master-merge-context-badge">${escapeHtml(contextBadge)}</span>`
        : "";
      return `
        <div class="result-item album-result registered-master-merge-card" data-registered-master-merge-row-id="${rowId}">
          <div class="album-result-cover">${cover}</div>
          <div class="album-result-main">
            <div class="registered-master-merge-head">
              <div>
                <strong class="registered-master-merge-title">${escapeHtml(title)}</strong>
                <div class="registered-master-merge-meta">
                  <span class="tag">${escapeHtml(String(row?.source_code || "-"))}</span>
                  <span class="tag alt">master ${escapeHtml(String(row?.source_master_id || "-"))}</span>
                  <span>album_master_id: ${rowId || "-"}</span>
                  <span>year: ${row?.release_year ?? "-"}</span>
                  <span>${escapeHtml(t("common.table.member_count"))}: ${escapeHtml(countWithUnit(Number(row?.member_count || 0)))}</span>
                </div>
              </div>
              <div class="registered-master-merge-actions">${orderBadge}${contextBadgeHtml}${actionsHtml}</div>
            </div>
          </div>
        </div>
      `;
    }

    function registeredMasterMergeRowHtml(row) {
      const rowId = normalizeRegisteredMasterMergeId(row?.id);
      const representativeId = registeredMasterMergeRepresentativeId();
      const isTarget = isRegisteredMasterMergeTargetId(rowId);
      const isRepresentative = isRegisteredMasterMergeRepresentativeId(rowId);
      const representativeLocked = representativeId > 0 && representativeId !== rowId;
      const addDisabled = isTarget || isRepresentative;
      const representativeDisabled = representativeLocked || isRepresentative;
      const addLabel = isTarget
        ? t("media.register.master.workflow.search.action.target_added")
        : t("media.register.master.workflow.search.action.target");
      const representativeLabel = isRepresentative
        ? t("media.register.master.workflow.search.action.representative_selected")
        : t("media.register.master.workflow.search.action.representative");
      const actionsHtml = `
        <button class="btn ghost tiny" type="button" data-registered-master-merge-add-id="${rowId}" ${addDisabled ? "disabled" : ""}>${escapeHtml(addLabel)}</button>
        <button class="btn ghost tiny" type="button" data-registered-master-merge-representative-id="${rowId}" ${representativeDisabled ? "disabled" : ""}>${escapeHtml(representativeLabel)}</button>
      `;
      return registeredMasterMergeCardHtml(row, { actionsHtml });
    }

    function renderRegisteredMasterMergeRows(items) {
      registeredMasterMergeSearchResults = Array.isArray(items) ? items : [];
      const count = $("registeredMasterMergeCount");
      if (count) {
        count.textContent = countWithUnit(registeredMasterMergeSearchResults.length);
      }
      const body = $("registeredMasterMergeBody");
      if (!body) return;
      if (!registeredMasterMergeSearchResults.length) {
        const emptyKey = registeredMasterMergeHasSearched
          ? "media.register.master.workflow.search.state.empty"
          : "media.register.master.workflow.search.state.prompt";
        body.innerHTML = `<div class='muted'>${escapeHtml(t(emptyKey))}</div>`;
        return;
      }
      body.innerHTML = registeredMasterMergeSearchResults.map(registeredMasterMergeRowHtml).join("");
    }

    function renderRegisteredMasterMergeRepresentative() {
      const summary = $("registeredMasterMergeRepresentativeSummary");
      const body = $("registeredMasterMergeRepresentativeBody");
      const representative = registeredMasterMergeRepresentativeItem;
      const representativeId = registeredMasterMergeRepresentativeId();
      if (summary) {
        summary.textContent = representativeId
          ? t("media.register.master.workflow.representative.summary.selected", {
              album_master_id: representativeId,
            })
          : t("media.register.master.workflow.representative.summary.none");
      }
      if (!body) return;
      if (!representativeId || !representative) {
        body.innerHTML = `<div class='muted'>${escapeHtml(t("media.register.master.workflow.representative.state.empty"))}</div>`;
        return;
      }
      const actionsHtml = `<button class="btn ghost tiny" type="button" data-registered-master-merge-clear-representative="1">${escapeHtml(t("media.register.master.workflow.representative.action.clear"))}</button>`;
      body.innerHTML = registeredMasterMergeCardHtml(representative, {
        actionsHtml,
        contextBadge: t("media.register.master.workflow.search.action.representative_selected"),
      });
    }

    function renderRegisteredMasterMergeTargets() {
      const summary = $("registeredMasterMergeTargetSummary");
      const body = $("registeredMasterMergeTargetBody");
      const targetIds = registeredMasterMergeTargetIds();
      if (summary) {
        summary.textContent = targetIds.length
          ? t("media.register.master.workflow.targets.summary.selected", {
              count: countWithUnit(targetIds.length),
            })
          : t("media.register.master.workflow.targets.summary.none");
      }
      if (!body) return;
      if (!registeredMasterMergeTargetItems.length) {
        body.innerHTML = `<div class='muted'>${escapeHtml(t("media.register.master.workflow.targets.state.empty"))}</div>`;
        return;
      }
      body.innerHTML = registeredMasterMergeTargetItems.map((row, index) => {
        const rowId = normalizeRegisteredMasterMergeId(row?.id);
        const actionsHtml = `<button class="btn ghost tiny" type="button" data-registered-master-merge-remove-id="${rowId}">${escapeHtml(t("media.register.master.workflow.targets.table.remove"))}</button>`;
        return registeredMasterMergeCardHtml(row, {
          actionsHtml,
          order: index + 1,
          contextBadge: t("media.register.master.workflow.search.action.target_added"),
        });
      }).join("");
    }

    function renderRegisteredMasterMergeHistory() {
      const summary = $("registeredMasterMergeHistorySummary");
      const body = $("registeredMasterMergeHistoryBody");
      const items = Array.isArray(registeredMasterMergeHistoryItems) ? registeredMasterMergeHistoryItems : [];
      if (summary) {
        summary.textContent = items.length
          ? t("media.register.master.workflow.history.summary.loaded", {
              count: countWithUnit(items.length),
            })
          : t("media.register.master.workflow.history.summary.none");
      }
      if (!body) return;
      if (!items.length) {
        body.innerHTML = `<div class='muted'>${escapeHtml(t("media.register.master.workflow.history.state.empty"))}</div>`;
        return;
      }
      body.innerHTML = items.map((entry, index) => {
        const entryId = Number(entry?.id || 0);
        const isLatest = index === 0 && !String(entry?.rolled_back_at || "").trim();
        const rollbackAvailable = Boolean(entry?.rollback_available);
        const rollbackBlockedReason = String(entry?.rollback_blocked_reason || "").trim();
        const rollbackMeta = String(entry?.rolled_back_at || "").trim()
          ? t("media.register.master.workflow.history.meta.rolled_back", {
              rolled_back_at: formatDateTimeCompact(entry.rolled_back_at),
              user: String(entry?.rolled_back_by || "").trim() || "-",
            })
          : rollbackAvailable
            ? t("media.register.master.workflow.history.meta.rollback_ready")
            : (rollbackBlockedReason || t("media.register.master.workflow.history.meta.rollback_unavailable"));
        const actionsHtml = isLatest
          ? `<button class="btn ghost tiny" type="button" data-registered-master-merge-rollback-id="${entry.id}" ${rollbackAvailable ? "" : "disabled"}>${escapeHtml(t("media.register.master.workflow.history.action.rollback"))}</button>`
          : "";
        return `
          <div class="result-item registered-master-merge-history-item" data-registered-master-merge-history-id="${entryId}">
            <div class="registered-master-merge-history-head">
              <strong>${escapeHtml(`${String(entry?.source_title || "-")} → ${String(entry?.target_title || "-")}`)}</strong>
              <div class="registered-master-merge-actions">${actionsHtml}</div>
            </div>
            <div class="registered-master-merge-history-meta">
              <span>${escapeHtml(t("media.register.master.workflow.history.meta.by", {
                user: String(entry?.merged_by || "").trim() || "-",
                created_at: formatDateTimeCompact(entry?.created_at || ""),
              }))}</span>
              <span>${escapeHtml(t("media.register.master.workflow.history.meta.members", {
                moved_count: countWithUnit(Number(entry?.moved_member_count || 0)),
                target_count: countWithUnit(Number(entry?.target_member_count || 0)),
              }))}</span>
              <span>${escapeHtml(t("media.register.master.workflow.history.meta.target", {
                source_album_master_id: Number(entry?.source_album_master_id || 0),
                target_album_master_id: Number(entry?.target_album_master_id || 0),
              }))}</span>
              <span>${escapeHtml(rollbackMeta)}</span>
            </div>
          </div>
        `;
      }).join("");
    }

    function syncRegisteredMasterMergeUi() {
      renderRegisteredMasterMergeRepresentative();
      renderRegisteredMasterMergeTargets();
      renderRegisteredMasterMergeHistory();
      renderRegisteredMasterMergeRows(registeredMasterMergeSearchResults);
      const runBtn = $("registeredMasterMergeRunBtn");
      if (runBtn) {
        runBtn.disabled = !registeredMasterMergeRepresentativeId() || !registeredMasterMergeTargetIds().length;
      }
    }

    function addRegisteredMasterMergeTarget(row) {
      const snapshot = registeredMasterMergeRowSnapshot(row);
      const rowId = normalizeRegisteredMasterMergeId(snapshot?.id);
      if (!rowId || isRegisteredMasterMergeRepresentativeId(rowId) || isRegisteredMasterMergeTargetId(rowId)) {
        return;
      }
      registeredMasterMergeTargetItems.push(snapshot);
      syncRegisteredMasterMergeUi();
    }

    function setRegisteredMasterMergeRepresentative(row) {
      const snapshot = registeredMasterMergeRowSnapshot(row);
      const rowId = normalizeRegisteredMasterMergeId(snapshot?.id);
      if (!rowId || !snapshot) return;
      registeredMasterMergeRepresentativeItem = {
        id: rowId,
        source_code: snapshot.source_code,
        source_master_id: snapshot.source_master_id,
        title: snapshot.title,
        artist_or_brand: snapshot.artist_or_brand,
        release_year: snapshot.release_year,
        member_count: snapshot.member_count,
        cover_image_url: snapshot.cover_image_url,
      };
      registeredMasterMergeTargetItems = registeredMasterMergeTargetItems.filter(
        (item) => normalizeRegisteredMasterMergeId(item?.id) !== rowId
      );
      syncRegisteredMasterMergeUi();
    }

    function removeRegisteredMasterMergeTarget(albumMasterId) {
      const rowId = normalizeRegisteredMasterMergeId(albumMasterId);
      if (!rowId) return;
      registeredMasterMergeTargetItems = registeredMasterMergeTargetItems.filter(
        (item) => normalizeRegisteredMasterMergeId(item?.id) !== rowId
      );
      syncRegisteredMasterMergeUi();
    }

    function clearRegisteredMasterMergeRepresentative() {
      registeredMasterMergeRepresentativeItem = null;
      syncRegisteredMasterMergeUi();
    }

    function clearRegisteredMasterMergeSearch() {
      registeredMasterMergeHasSearched = false;
      registeredMasterMergeSearchResults = [];
      if ($("registeredMasterMergeQuery")) $("registeredMasterMergeQuery").value = "";
      setStatus("registeredMasterMergeStatus", "ok", "");
      syncRegisteredMasterMergeUi();
    }
    function applyGoodsRegisterImageUrl() {
      const url = String($("goodsRegisterImageUrlInput")?.value || "").trim();
      if (!url) return;
      _regImageUrls.push(url);
      addRegImagePreview(url);
      $("goodsRegisterImageUrls").value = _regImageUrls.join("\n");
      if ($("goodsRegisterImageUrlInput")) $("goodsRegisterImageUrlInput").value = "";
    }


    async function searchRegisteredAlbumMastersForMerge() {
      const query = $("registeredMasterMergeQuery").value.trim();
      const params = new URLSearchParams({ limit: "80", media_only: "true" });
      if (query) params.set("q", query);
      registeredMasterMergeHasSearched = true;

      try {
        setStatus("registeredMasterMergeStatus", "ok", t("media.register.master.workflow.status.loading"));
        const res = await fetch(`/album-masters?${params.toString()}`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.register.master.workflow.status.failed"));
        registeredMasterMergeSearchResults = Array.isArray(data) ? data : [];
        syncRegisteredMasterMergeUi();
        setStatus("registeredMasterMergeStatus", "ok", t("media.register.master.workflow.status.loaded", {
          count: countWithUnit(registeredMasterMergeSearchResults.length),
        }));
      } catch (err) {
        registeredMasterMergeSearchResults = [];
        syncRegisteredMasterMergeUi();
        setStatus("registeredMasterMergeStatus", "err", err.message);
      }
    }

    async function loadRegisteredMasterMergeHistory() {
      try {
        const res = await fetch("/album-masters/merge-history?limit=10");
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.register.master.workflow.history.status.failed"));
        registeredMasterMergeHistoryItems = Array.isArray(data) ? data : [];
        syncRegisteredMasterMergeUi();
      } catch (err) {
        registeredMasterMergeHistoryItems = [];
        syncRegisteredMasterMergeUi();
        setStatus("registeredMasterMergeStatus", "err", err.message);
      }
    }

    async function runRegisteredAlbumMasterMerge() {
      const targetIds = registeredMasterMergeTargetIds();
      const representativeId = registeredMasterMergeRepresentativeId();
      if (!representativeId) {
        setStatus("registeredMasterMergeStatus", "err", t("media.register.master.workflow.status.no_representative"));
        return;
      }
      if (!targetIds.length) {
        setStatus("registeredMasterMergeStatus", "err", t("media.register.master.workflow.status.no_targets"));
        return;
      }
      const previewRows = registeredMasterMergeTargetItems
        .slice(0, 5)
        .map((row, index) => `${index + 1}. ${registeredMasterMergeHeadingLabel(row)} (album_master_id=${normalizeRegisteredMasterMergeId(row?.id)})`);
      const remainingCount = Math.max(0, targetIds.length - previewRows.length);
      const confirmText = t("media.register.master.workflow.confirm.run", {
        representative_id: representativeId,
        count: countWithUnit(targetIds.length),
        preview: previewRows.join("\n") || "-",
        more: remainingCount > 0
          ? `\n+ ${countWithUnit(remainingCount)}`
          : "",
      });
      if (!window.confirm(confirmText)) {
        setStatus("registeredMasterMergeStatus", "ok", t("media.register.master.workflow.status.cancelled"));
        return;
      }

      let mergedCount = 0;
      let movedCount = 0;
      const failures = [];
      const failedIdSet = new Set();
      try {
        setStatus("registeredMasterMergeStatus", "ok", t("media.register.master.workflow.status.merging", {
          representative_id: representativeId,
          count: countWithUnit(targetIds.length),
        }));
        for (const sourceId of targetIds) {
          if (sourceId === representativeId) continue;
          try {
            const res = await fetch(`/album-masters/${sourceId}/merge`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ target_album_master_id: representativeId }),
            });
            const data = await safeJson(res);
            if (!res.ok) throw new Error(data.detail || t("media.register.direct.duplicate.merge_failed"));
            mergedCount += Number(data?.merged === false ? 0 : 1);
            movedCount += Number(data?.moved_member_count || 0);
          } catch (err) {
            failedIdSet.add(sourceId);
            failures.push(`- ${sourceId}: ${err.message}`);
          }
        }
        registeredMasterMergeTargetItems = registeredMasterMergeTargetItems.filter((item) => {
          const rowId = normalizeRegisteredMasterMergeId(item?.id);
          return rowId > 0 && failedIdSet.has(rowId);
        });
        if (registeredMasterMergeHasSearched) {
          await searchRegisteredAlbumMastersForMerge();
        } else {
          syncRegisteredMasterMergeUi();
        }
        await loadRegisteredMasterMergeHistory();
        if (failures.length) {
          setStatus("registeredMasterMergeStatus", "err", t("media.register.master.workflow.status.partial", {
            merged_count: formatCount(mergedCount),
            failed_count: formatCount(failures.length),
            representative_id: representativeId,
            details: `\n${failures.join("\n")}`,
          }));
          return;
        }
        setStatus("registeredMasterMergeStatus", "ok", t("media.register.master.workflow.status.done", {
          merged_count: formatCount(mergedCount),
          moved_count: formatCount(movedCount),
          representative_id: representativeId,
        }));
      } catch (err) {
        setStatus("registeredMasterMergeStatus", "err", err.message);
      }
    }

    async function rollbackLatestRegisteredAlbumMasterMerge() {
      const latestEntry = Array.isArray(registeredMasterMergeHistoryItems) ? registeredMasterMergeHistoryItems[0] : null;
      if (!latestEntry || !Number(latestEntry?.id || 0)) return;
      const confirmText = t("media.register.master.workflow.history.confirm.rollback", {
        source_album_master_id: Number(latestEntry?.source_album_master_id || 0),
        target_album_master_id: Number(latestEntry?.target_album_master_id || 0),
      });
      if (!window.confirm(confirmText)) return;
      try {
        setStatus("registeredMasterMergeStatus", "ok", t("media.register.master.workflow.history.status.rollbacking"));
        const res = await fetch("/album-masters/merge-history/latest/rollback", {
          method: "POST",
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.register.master.workflow.history.status.rollback_failed"));
        registeredMasterMergeRepresentativeItem = null;
        registeredMasterMergeTargetItems = [];
        if (registeredMasterMergeHasSearched) {
          await searchRegisteredAlbumMastersForMerge();
        } else {
          syncRegisteredMasterMergeUi();
        }
        await loadRegisteredMasterMergeHistory();
        setStatus("registeredMasterMergeStatus", "ok", t("media.register.master.workflow.history.status.rolled_back", {
          source_album_master_id: Number(data?.source_album_master_id || 0),
          target_album_master_id: Number(data?.target_album_master_id || 0),
          restored_member_count: countWithUnit(Number(data?.restored_member_count || 0)),
        }));
      } catch (err) {
        setStatus("registeredMasterMergeStatus", "err", err.message);
      }
    }


    async function uploadCsv() {
      const fileInput = $("csvFile");
      if (!fileInput.files || !fileInput.files[0]) {
        setStatus("csvStatus", "err", t("media.register.csv.status.file_required"));
        return;
      }

      const form = new FormData();
      form.append("file", fileInput.files[0]);

      const dc = $("csvDefaultCategory").value;
      const by = $("csvCreatedBy").value.trim();
      const notes = $("csvNotes").value.trim();
      if (dc) form.append("default_category", dc);
      if (by) form.append("created_by", by);
      if (notes) form.append("notes", notes);

      try {
        setStatus("csvStatus", "ok", t("media.register.csv.status.uploading"));
        const res = await fetch("/ingest/csv", { method: "POST", body: form });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("media.register.csv.status.failed")));

        setDisplayIfPresent("csvKpi", "grid");
        $("kpiTotal").textContent = data.total_count;
        $("kpiMatched").textContent = data.matched_count;
        $("kpiReview").textContent = data.review_count;
        $("kpiFailed").textContent = data.failed_count;

        setStatus("csvStatus", "ok", t("media.register.csv.status.done", { batch_id: data.batch_id }));
      } catch (err) {
        setStatus("csvStatus", "err", err.message);
      }
    }

    function queueRowHtml(row) {
      const candidate = row.candidate || {};
      const title = candidate.title || "-";
      const source = candidate.source ? ` (${candidate.source})` : "";
      return `
        <tr>
          <td>${row.id}</td>
          <td>${row.row_no ?? "-"}</td>
          <td>${row.category ?? "-"}</td>
          <td>${Number(row.confidence_score || 0).toFixed(3)}</td>
          <td>${title}${source}</td>
          <td>${row.review_note ?? ""}</td>
        </tr>
      `;
    }

    async function loadReviewQueue() {
      const status = $("queueStatus").value;
      const category = $("queueCategory").value.trim();
      const limit = Math.max(1, Math.min(200, Number($("queueLimit").value || 20)));

      const params = new URLSearchParams({ review_status: status, limit: String(limit) });
      if (category) params.set("category", category);

      try {
        setStatus("queueStatusBox", "ok", t("media.register.queue.status.loading"));
        const res = await fetch(`/review-queue?${params.toString()}`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("media.register.queue.status.load_failed")));

        $("queueTableBody").innerHTML = (data || []).map(queueRowHtml).join("") ||
          `<tr><td colspan='6' class='muted'>${escapeHtml(t("common.data_empty"))}</td></tr>`;
        setStatus("queueStatusBox", "ok", t("media.register.queue.status.loaded", { count: countWithUnit(data.length) }));
      } catch (err) {
        setStatus("queueStatusBox", "err", err.message);
      }
    }

    function ownedRowHtml(row) {
      const flags = [];
      if (row.is_second_hand) flags.push(t("common.flag.second_hand"));
      if (row.signature_type && row.signature_type !== "NONE") flags.push(t("common.flag.signature_prefix", { value: row.signature_type }));
      if (row.is_promotional_not_for_sale) flags.push("NFS");

      const cond = row.format_name ? `${row.cover_condition ?? "-"} / ${row.disc_condition ?? "-"}` : "-";
      const name = row.item_name_override || "-";
      const labelCat = `${row.label_name || "-"} / ${row.catalog_no || "-"}`;
      const trackCount = Array.isArray(row.track_list) ? row.track_list.length : 0;
      const coverUrl = normalizeRenderableCoverUrl(row.cover_image_url);
      const coverCell = coverUrl
        ? `<a href="${escapeHtml(coverUrl)}" target="_blank" rel="noreferrer">${escapeHtml(t("common.action.link"))}</a>`
        : "-";
      const sourceText = row.source_code && row.source_external_id
        ? `${row.source_code}#${row.source_external_id}`
        : "-";
      const discogsSyncBtn = row.source_code === "DISCOGS"
        ? `<button class="btn ghost sync-discogs-btn btn-compact-pad-xs" data-owned-id="${row.id}">${escapeHtml(t("common.action.sync"))}</button>`
        : "-";
      const orderMoveButtons = `
        <button class="btn ghost order-before-btn btn-compact-pad-xs" data-target-id="${row.id}">${escapeHtml(t("common.action.before"))}</button>
        <button class="btn ghost order-after-btn btn-compact-pad-xs" data-target-id="${row.id}">${escapeHtml(t("common.action.after"))}</button>
      `;

      return `
        <tr>
          <td>${row.id}</td>
          <td>${escapeHtml(row.label_id || "-")}</td>
          <td>${escapeHtml(row.category)}</td>
          <td>${escapeHtml(name)}</td>
          <td>${row.quantity}</td>
          <td>${escapeHtml(row.status)}</td>
          <td>${escapeHtml(sourceText)}</td>
          <td>${row.display_rank ?? "-"}</td>
          <td>${escapeHtml(row.order_key ?? "-")}</td>
          <td>${escapeHtml(row.slot_code ?? "-")}</td>
          <td>${escapeHtml(flags.join(", ") || "-")}</td>
          <td>${escapeHtml(labelCat)}</td>
          <td>${coverCell}</td>
          <td>${escapeHtml(cond)}</td>
          <td>${trackCount}</td>
          <td>${escapeHtml(row.purchase_source ?? "-")}</td>
          <td>${orderMoveButtons}</td>
          <td>${discogsSyncBtn}</td>
        </tr>
      `;
    }

    async function loadOwnedItems() {
      const category = $("ownedCategory").value;
      const status = $("ownedStatus").value;
      const q = $("ownedQuery").value.trim();
      const limit = Math.max(1, Math.min(200, Number($("ownedLimit").value || 30)));

      const params = new URLSearchParams({ limit: String(limit) });
      if (category) params.set("category", category);
      if (status) params.set("status", status);
      if (q) params.set("q", q);

      try {
        setStatus("ownedStatusBox", "ok", t("media.manage.owned.status.loading"));
        const res = await fetch(`/owned-items?${params.toString()}`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("media.manage.owned.status.load_failed")));

        $("ownedTableBody").innerHTML = (data || []).map(ownedRowHtml).join("") ||
          `<tr><td colspan='18' class='muted'>${escapeHtml(t("common.data_empty"))}</td></tr>`;
        setStatus("ownedStatusBox", "ok", t("media.manage.owned.status.loaded", { count: countWithUnit(data.length) }));
      } catch (err) {
        setStatus("ownedStatusBox", "err", err.message);
      }
    }

    async function moveOwnedItemOrder(ownedItemId, targetOwnedItemId, position) {
      if (!ownedItemId || !targetOwnedItemId) {
        setStatus("ownedStatusBox", "err", t("media.manage.owned.status.move_required"));
        return;
      }
      if (ownedItemId === targetOwnedItemId) {
        setStatus("ownedStatusBox", "err", t("media.manage.owned.status.move_same_item"));
        return;
      }

      try {
        setStatus(
          "ownedStatusBox",
          "ok",
          t("media.manage.owned.status.moving", {
            source: ownedItemId,
            target: targetOwnedItemId,
            position,
          })
        );
        const res = await fetch(`/owned-items/${ownedItemId}/order`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target_owned_item_id: targetOwnedItemId,
            position
          })
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.owned.status.move_failed"));
        setStatus(
          "ownedStatusBox",
          "ok",
          t("media.manage.owned.status.moved", {
            owned_item_id: data.owned_item_id,
            order_key: data.order_key,
          })
        );
        await loadOwnedItems();
      } catch (err) {
        setStatus("ownedStatusBox", "err", err.message);
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
      const isVinyl = ["LP", "LP7", "LP10"].includes(sizeGroup);
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
        is_second_hand: true,
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
          disc_type: String(candidate?.disc_type || "").trim() || (isVinyl ? "Standard" : null),
          speed_rpm: Number.isFinite(Number(candidate?.speed_rpm)) ? Number(candidate.speed_rpm) : (isVinyl ? 33 : null),
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


    const GLOBAL_BARCODE_SCANNER_INPUT_IDS = new Set(["barcodeInput", "operatorLookupQuery", "homeBarcode"]);
    const GLOBAL_BARCODE_SCANNER_LENGTH = 13;
    const GLOBAL_BARCODE_SCANNER_MAX_GAP_MS = 80;
    let globalBarcodeScannerBuffer = "";
    let globalBarcodeScannerLastKeyAt = 0;
    let globalBarcodeScannerEditableTarget = null;
    let globalBarcodeScannerEditableInitialValue = "";


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


    const PACKAGING_OPTIONS_BY_MEDIA = {
      VINYL: ["Single Jacket", "Gatefold", "Triple-fold", "Gimmick Sleeve", "Die-Cut Sleeve", "Pop-up Sleeve", "Box Set"],
      CD: ["Jewel Case", "Double Jewel", "Slim Jewel", "Digipak", "Paper Sleeve", "Slipcase", "Digibook", "Eco-pack", "DVD Size Digipak", "Keep Case", "Gimmick Case", "LP-Style Packaging", "Box Set"],
      CASSETTE: ["Standard Case", "Slipcase", "LP-Style Packaging", "Box Set"],
      EIGHT_TRACK: ["Standard"],
      REEL: ["Standard Box"],
    };
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
