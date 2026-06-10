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
