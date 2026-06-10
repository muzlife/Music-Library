    let operatorLookupResults = [];
    let operatorLookupRequestSeq = 0;
    let operatorLookupMode = "FEED";
    let homeSelectedContextItem = null;
    let homePreviewContextItem = null;
    const opsLibraryContextSlotPreviewCache = new Map();
    let opsLibraryContextSlotPreviewLoadingSlotCode = "";
    let opsLibraryContextSlotPreviewRequestSeq = 0;
    const opsArtistContextCache = new Map();
    let opsArtistContextLoadingKey = "";
    let opsArtistContextRequestSeq = 0;
    const opsPlacementHintCache = new Map();
    let opsPlacementHintLoadingOwnedItemId = 0;
    let opsPlacementHintRequestSeq = 0;
    let operatorFeedKind = "registered";
    let operatorFeedPage = 1;
    let operatorFeedTotalCount = 0;
    const operatorFeedPageSize = 30;
    let operatorFeedItems = [];
    let operatorWeatherState = {
      loading: false,
      loadedAt: 0,
      source: "fallback",
      latitude: 37.5665,
      longitude: 126.9780,
    };
    let operatorLookupSummary = {
      normalizedQuery: "",
      topCandidate: null,
      locationSummary: null,
      status: "idle",
      matchReason: "",
    };
    let opsHomeHeroStats = {
      locationCount: 0,
      recentMoveCount: 0,
      recentRegistrationCount: 0,
      moveWindowDays: 1,
    };
    let recentMovedItems = [];
    let recentRegisteredItems = [];
    let operatorRequestItems = [];

    function operatorStatusClass(value) {
      const code = String(value || "").trim().toUpperCase();
      if (code === "PLAYING") return "playing";
      if (code === "RETURNED") return "returned";
      if (code === "CANCELLED") return "cancelled";
      return "requested";
    }

    function operatorStatusLabel(value) {
      const code = String(value || "").trim().toUpperCase();
      if (code === "PLAYING") return t("operator.request.status.playing");
      if (code === "RETURNED") return t("operator.request.status.returned");
      if (code === "CANCELLED") return t("operator.request.status.cancelled");
      return t("operator.request.status.requested");
    }

    function operatorCanUseManage() {
      return isAdminSession() && !isShellReadOnly();
    }

    function renderOpsHomeHeroStats(stats = {}) {
      opsHomeHeroStats = {
        locationCount: Math.max(0, Number(stats.locationCount ?? opsHomeHeroStats.locationCount ?? 0)),
        recentMoveCount: Math.max(0, Number(stats.recentMoveCount ?? opsHomeHeroStats.recentMoveCount ?? 0)),
        recentRegistrationCount: Math.max(0, Number(stats.recentRegistrationCount ?? opsHomeHeroStats.recentRegistrationCount ?? 0)),
        moveWindowDays: Math.max(1, Number(stats.moveWindowDays ?? opsHomeHeroStats.moveWindowDays ?? 1)),
      };
      setTextIfPresent("opsHomeLocationValue", t("operator.focus.count.location", {
        count: formatCount(opsHomeHeroStats.locationCount),
      }));
      setTextIfPresent(
        "opsHomeRecentMoveValue",
        t(
          opsHomeHeroStats.moveWindowDays === 1
            ? "operator.focus.count.recent_move_hour"
            : "operator.focus.count.recent_move_day",
          {
            days: String(opsHomeHeroStats.moveWindowDays),
            count: formatCount(opsHomeHeroStats.recentMoveCount),
          }
        )
      );
      setTextIfPresent("opsHomeRecentRegistrationValue", t("operator.focus.count.recent_registration", {
        count: formatCount(opsHomeHeroStats.recentRegistrationCount),
      }));
    }

    function operatorFeedKindBaseLabel(kind) {
      return kind === "moved" ? t("operator.feed.filter.moved") : t("operator.feed.filter.registered");
    }

    function operatorFeedKindFromSortMode(sortMode) {
      const normalizedSortMode = String(sortMode || "CREATED_DESC").trim().toUpperCase() || "CREATED_DESC";
      return normalizedSortMode === "MOVED_DESC" ? "moved" : "registered";
    }

    function operatorFeedKindLabel(kind) {
      return String(kind || "").trim() === "moved"
        ? t("operator.feed.heading.recent_moved")
        : t("operator.feed.heading.recent_registered");
    }

    function operatorWeatherDescription(code, isDay) {
      const weatherCode = Number(code);
      if (weatherCode === 0) return isDay ? t("operator.weather.desc.clear_day") : t("operator.weather.desc.clear_night");
      if ([1, 2].includes(weatherCode)) return isDay ? t("operator.weather.desc.mostly_clear_day") : t("operator.weather.desc.mostly_clear_night");
      if (weatherCode === 3) return t("operator.weather.desc.cloudy");
      if ([45, 48].includes(weatherCode)) return t("operator.weather.desc.fog");
      if ([51, 53, 55, 56, 57].includes(weatherCode)) return t("operator.weather.desc.drizzle");
      if ([61, 63, 65, 66, 67, 80, 81, 82].includes(weatherCode)) return t("operator.weather.desc.rain");
      if ([71, 73, 75, 77, 85, 86].includes(weatherCode)) return t("operator.weather.desc.snow");
      if ([95, 96, 99].includes(weatherCode)) return t("operator.weather.desc.thunder");
      return t("operator.weather.desc.check");
    }

    function operatorWeatherIcon(code, isDay) {
      const weatherCode = Number(code);
      if (weatherCode === 0) return isDay ? "☀" : "☾";
      if ([1, 2].includes(weatherCode)) return isDay ? "⛅" : "☁";
      if (weatherCode === 3) return "☁";
      if ([45, 48].includes(weatherCode)) return "〰";
      if ([51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82].includes(weatherCode)) return "☂";
      if ([71, 73, 75, 77, 85, 86].includes(weatherCode)) return "❄";
      if ([95, 96, 99].includes(weatherCode)) return "⚡";
      return "☁";
    }

    function renderOperatorWeatherEmpty() {
      setTextIfPresent("operatorWeatherKicker", t("operator.weather.empty.kicker"));
      setTextIfPresent("operatorWeatherSecondaryLabel", t("operator.weather.empty.secondary"));
      setTextIfPresent("operatorWeatherTemperature", "--°");
      setTextIfPresent("operatorWeatherHumidity", "--%");
      setTextIfPresent("operatorWeatherRange", "-- / --");
      setTextIfPresent("operatorWeatherLocation", t("operator.weather.empty.location"));
      setTextIfPresent("operatorWeatherDescription", t("operator.weather.empty.description"));
      setTextIfPresent("operatorWeatherUpdated", t("operator.weather.empty.updated"));
      setTextIfPresent("operatorWeatherIcon", "☁");
    }

    function renderOperatorOfficeClimate(data = {}) {
      const temperature = Number(data.temperature_c);
      const humidity = Number(data.humidity_percent);
      const comfortLabel = String(data.comfort_label || "").trim() || "--";
      setTextIfPresent("operatorWeatherKicker", t("operator.weather.office.kicker"));
      setTextIfPresent("operatorWeatherIcon", "HA");
      setTextIfPresent("operatorWeatherTemperature", Number.isFinite(temperature) ? `${Math.round(temperature)}°` : "--°");
      setTextIfPresent("operatorWeatherLocation", t("operator.weather.office.location"));
      setTextIfPresent(
        "operatorWeatherDescription",
        comfortLabel && comfortLabel !== "--"
          ? t("operator.weather.office.description_ready", { label: comfortLabel })
          : t("operator.weather.office.description_loading")
      );
      setTextIfPresent("operatorWeatherHumidity", Number.isFinite(humidity) ? `${Math.round(humidity)}%` : "--%");
      setTextIfPresent("operatorWeatherSecondaryLabel", t("operator.weather.office.secondary"));
      setTextIfPresent("operatorWeatherRange", comfortLabel);
      setTextIfPresent(
        "operatorWeatherUpdated",
        data.updated_at
          ? t("operator.weather.office.updated", { time: formatDateTimeCompact(data.updated_at) })
          : t("operator.weather.office.updated_now")
      );
    }

    function renderOperatorSeoulWeather(data = {}) {
      const temperature = Number(data.temperature_c);
      const humidity = Number(data.humidity_percent);
      const weatherCode = Number(data.weather_code);
      const isDay = Boolean(data.is_day);
      const high = Number(data.temperature_high_c);
      const low = Number(data.temperature_low_c);
      setTextIfPresent("operatorWeatherKicker", t("operator.weather.empty.kicker"));
      setTextIfPresent("operatorWeatherIcon", operatorWeatherIcon(weatherCode, isDay));
      setTextIfPresent("operatorWeatherTemperature", Number.isFinite(temperature) ? `${Math.round(temperature)}°` : "--°");
      setTextIfPresent("operatorWeatherLocation", t("operator.weather.location.seoul"));
      setTextIfPresent("operatorWeatherDescription", operatorWeatherDescription(weatherCode, isDay));
      setTextIfPresent("operatorWeatherHumidity", Number.isFinite(humidity) ? `${Math.round(humidity)}%` : "--%");
      setTextIfPresent("operatorWeatherSecondaryLabel", t("operator.weather.empty.secondary"));
      setTextIfPresent(
        "operatorWeatherRange",
        Number.isFinite(high) && Number.isFinite(low)
          ? `${Math.round(high)}° / ${Math.round(low)}°`
          : "-- / --"
      );
      setTextIfPresent(
        "operatorWeatherUpdated",
        data.updated_at
          ? t("operator.weather.updated.at", { time: formatDateTimeCompact(data.updated_at) })
          : t("operator.weather.empty.updated")
      );
    }

    function renderHomeMasterReviewSection(master) {
      const section = $("homeMasterReviewSection");
      if (!section) return;
      if (!master) { section.style.display = "none"; return; }
      section.style.display = "";

      const reviewText = String(master.review_text || "").trim();
      const reviewSource = String(master.review_source || "").trim();
      const reviewUrl = String(master.review_url || "").trim();

      const preview = $("homeMasterReviewPreview");
      const sourceTag = $("homeMasterReviewSourceTag");
      const deleteBtn = $("homeMasterReviewDeleteBtn");
      const toggleBtn = $("homeMasterReviewToggleBtn");
      const MANAGE_PREVIEW_LEN = 200;

      if (reviewText) {
        const needsTruncate = reviewText.length > MANAGE_PREVIEW_LEN;
        preview.textContent = needsTruncate ? reviewText.slice(0, MANAGE_PREVIEW_LEN) + "…" : reviewText;
        preview.dataset.fullText = reviewText;
        preview.dataset.expanded = "false";
        preview.style.display = "";
        if (reviewSource) {
          sourceTag.innerHTML = `출처: ${reviewUrl ? `<a href="${escapeHtml(reviewUrl)}" target="_blank" rel="noopener">${escapeHtml(reviewSource)}</a>` : escapeHtml(reviewSource)}`;
        } else {
          sourceTag.textContent = "";
        }
        deleteBtn.style.display = "";
        if (toggleBtn) {
          toggleBtn.style.display = needsTruncate ? "" : "none";
          toggleBtn.textContent = "더보기 ▼";
          toggleBtn.dataset.expanded = "false";
        }
      } else {
        preview.style.display = "none";
        sourceTag.textContent = "";
        deleteBtn.style.display = "none";
        if (toggleBtn) toggleBtn.style.display = "none";
      }

      $("homeMasterReviewUrlForm").style.display = "none";
      $("homeMasterReviewManualForm").style.display = "none";
      $("homeMasterReviewStatus").textContent = "";
      $("homeMasterReviewUrlInput").value = "";
      $("homeMasterReviewManualText").value = "";
      $("homeMasterReviewManualSource").value = "";
    }

    function renderOpsPluginSection(cardsHtml) {
      return `
        <section class="operator-mini-card ops-plugin-section">
          <div class="ops-plugin-section-head">
            <strong>${escapeHtml(t("operator.plugin.title"))}</strong>
          </div>
          <div class="ops-plugin-section-cards">
            ${cardsHtml}
          </div>
        </section>
      `;
    }

    function renderOpsArtistContextIdle(options = {}) {
      const cardId = String(options.cardId || "opsArtistContextCard");
      return `
        <section id="${escapeHtml(cardId)}" class="operator-mini-card ops-artist-context-card" aria-live="polite">
          <div class="ops-artist-context-head">
            <strong>${escapeHtml(t("operator.artist_context.title"))}</strong>
          </div>
          <div class="mini muted">${escapeHtml(t("operator.artist_context.idle"))}</div>
        </section>
      `;
    }

    function renderOpsArtistContextLoading(item, options = {}) {
      const cardId = String(options.cardId || "opsArtistContextCard");
      const artistName = String(item?.artist_or_brand || "").trim();
      return `
        <section id="${escapeHtml(cardId)}" class="operator-mini-card ops-artist-context-card" aria-live="polite">
          <div class="ops-artist-context-head">
            <strong>${escapeHtml(t("operator.artist_context.title"))}</strong>
          </div>
          ${artistName ? `<h4 class="ops-artist-context-name">${escapeHtml(artistName)}</h4>` : ""}
          <div class="mini muted">${escapeHtml(t("operator.artist_context.loading"))}</div>
        </section>
      `;
    }

    function renderOpsArtistContextLinks(payload) {
      if (!Array.isArray(payload?.links) || !payload.links.length) return "";
      return `
        <div class="ops-artist-context-links">
          <span class="ops-artist-context-links-label">${escapeHtml(t("operator.artist_context.links"))}</span>
          ${payload.links.map((link) => `
            <a class="ops-artist-context-link" href="${escapeHtml(link.url)}" target="_blank" rel="noreferrer noopener">${escapeHtml(link.label)}</a>
          `).join("")}
        </div>
      `;
    }

    function renderOpsArtistContextReady(payload, options = {}) {
      const cardId = String(options.cardId || "opsArtistContextCard");
      const hasOriginalSummary = Boolean(
        payload.summary
        && payload.summary_original
        && String(payload.summary_original).trim()
        && String(payload.summary_original).trim() !== String(payload.summary).trim()
      );
      const metaBits = [
        payload.country
          ? `<span class="ops-artist-context-pill"><strong>${escapeHtml(t("operator.artist_context.field.country"))}</strong>${escapeHtml(payload.country)}</span>`
          : "",
        payload.active_years
          ? `<span class="ops-artist-context-pill"><strong>${escapeHtml(t("operator.artist_context.field.active_years"))}</strong>${escapeHtml(payload.active_years)}</span>`
          : "",
        payload.genres.length
          ? `<span class="ops-artist-context-pill"><strong>${escapeHtml(t("operator.artist_context.field.genres"))}</strong>${escapeHtml(payload.genres.join(", "))}</span>`
          : "",
      ].filter(Boolean).join("");
      const showOriginalLabel = escapeHtml(t("operator.artist_context.action.show_original"));
      const hideOriginalLabel = escapeHtml(t("operator.artist_context.action.hide_original"));
      const imageHtml = payload.image_url
        ? `<div class="ops-artist-context-media"><img class="ops-artist-context-image" src="${escapeHtml(payload.image_url)}" alt="${escapeHtml(payload.artist_name || t("operator.artist_context.title"))}" loading="lazy" /></div>`
        : "";
      return `
        <section id="${escapeHtml(cardId)}" class="operator-mini-card ops-artist-context-card${payload.image_url ? " has-image" : ""}" aria-live="polite">
          <div class="ops-artist-context-head">
            <strong>${escapeHtml(t("operator.artist_context.title"))}</strong>
          </div>
          ${imageHtml}
          <h4 class="ops-artist-context-name">${escapeHtml(payload.artist_name || "-")}</h4>
          ${payload.summary ? `
            <div class="ops-artist-context-summary-wrap">
              <p class="ops-artist-context-summary">${escapeHtml(payload.summary)}</p>
              ${hasOriginalSummary ? `
                <button
                  type="button"
                  class="ops-artist-context-toggle"
                  data-ops-artist-context-toggle
                  data-show-label="${showOriginalLabel}"
                  data-hide-label="${hideOriginalLabel}"
                  aria-expanded="false"
                >${showOriginalLabel}</button>
              ` : ""}
              ${hasOriginalSummary ? `
                <div class="ops-artist-context-original" data-ops-artist-context-original hidden>
                  <p class="ops-artist-context-summary ops-artist-context-summary--original">${escapeHtml(payload.summary_original)}</p>
                </div>
              ` : ""}
            </div>
          ` : ""}
          ${metaBits ? `<div class="ops-artist-context-meta">${metaBits}</div>` : ""}
          ${renderOpsArtistContextLinks(payload)}
        </section>
      `;
    }

    function renderOpsArtistContextUnavailable(item, payload = null, options = {}) {
      const cardId = String(options.cardId || "opsArtistContextCard");
      const artistName = String(payload?.artist_name || item?.artist_or_brand || "").trim();
      return `
        <section id="${escapeHtml(cardId)}" class="operator-mini-card ops-artist-context-card" aria-live="polite">
          <div class="ops-artist-context-head">
            <strong>${escapeHtml(t("operator.artist_context.title"))}</strong>
          </div>
          ${artistName ? `<h4 class="ops-artist-context-name">${escapeHtml(artistName)}</h4>` : ""}
          <div class="mini muted">${escapeHtml(t("operator.artist_context.unavailable"))}</div>
          ${renderOpsArtistContextLinks(payload)}
        </section>
      `;
    }

    function renderOpsArtistContextCard(item, options = {}) {
      if (!item) return renderOpsArtistContextIdle(options);
      const cacheKey = normalizedOpsArtistContextCacheKey(item);
      if (!cacheKey) return renderOpsArtistContextUnavailable(item, null, options);
      if (opsArtistContextCache.has(cacheKey)) {
        const payload = opsArtistContextCache.get(cacheKey);
        return payload?.available
          ? renderOpsArtistContextReady(payload, options)
          : renderOpsArtistContextUnavailable(item, payload, options);
      }
      if (opsArtistContextLoadingKey === cacheKey) return renderOpsArtistContextLoading(item, options);
      return renderOpsArtistContextLoading(item, options);
    }

    function operatorPlacementReasonLabel(reason) {
      const key = String(reason || "").trim().toLowerCase();
      if (!key) return t("operator.placement.reason.fallback");
      if (key.includes("artist")) return t("operator.placement.reason.artist");
      if (key.includes("domain")) return t("operator.placement.reason.domain");
      if (key.includes("near") || key.includes("adjacent") || key.includes("neighbor")) return t("operator.placement.reason.nearby");
      if (key.includes("label")) return t("operator.placement.reason.label");
      return t("operator.placement.reason.fallback");
    }

    function renderOpsPlacementHintRow(item, row) {
      const slotCode = String(row?.slot_code || "").trim();
      const cabinetName = String(row?.cabinet_name || row?.current_cabinet_name || "").trim();
      const columnCode = String(row?.column_code || row?.current_column_code || "").trim();
      const cellCode = String(row?.cell_code || row?.current_cell_code || "").trim();
      const displayName = buildOperatorSlotDisplayLabel(
        String(row?.display_name || row?.slot_display_name || "").trim(),
        slotCode,
        cabinetName,
        columnCode,
        cellCode
      ) || t("operator.placement.state.fallback");
      const reasonLabel = operatorPlacementReasonLabel(row?.reason || row?.reason_code || row?.match_reason || row?.reason_type || "");
      const reasonDetail = String(row?.reason_detail || row?.detail || "").trim();
      const ownedItemId = Number(row?.owned_item_id || item?.owned_item_id || item?.id || 0);
      const canOpen = Boolean(slotCode || (cabinetName && columnCode && cellCode));
      return `
        <div class="ops-placement-hint-row">
          <div class="ops-placement-hint-row-copy">
            <strong>${escapeHtml(displayName)}</strong>
            <span>${escapeHtml([reasonLabel, reasonDetail].filter(Boolean).join(" · ") || t("operator.placement.state.fallback"))}</span>
          </div>
          ${canOpen
            ? `<div class="ops-placement-hint-row-actions"><button class="btn ghost tiny" type="button" data-operator-open-cabinet="${ownedItemId}" data-operator-slot-code="${escapeHtml(slotCode)}" data-cabinet-name="${escapeHtml(cabinetName)}" data-column-code="${escapeHtml(columnCode)}" data-cell-code="${escapeHtml(cellCode)}">${escapeHtml(t("operator.feed.action.open_cabinet"))}</button></div>`
            : ""}
        </div>
      `;
    }

    function renderOpsPlacementHintIdle(item = null, options = {}) {
      const cardId = String(options.cardId || "opsLibraryPlacementHintCard");
      return `
        <section id="${escapeHtml(cardId)}" class="ops-placement-hint-card is-idle">
          <div class="operator-helper-head">
            <div>
              <strong>${escapeHtml(t(isOpsPlacementHintUnslottedItem(item) ? "operator.placement.title.unslotted" : "operator.placement.title.assigned"))}</strong>
            </div>
          </div>
          <div class="mini muted">${escapeHtml(t(isOpsPlacementHintUnslottedItem(item) ? "operator.placement.state.idle.unslotted" : "operator.placement.state.idle.assigned"))}</div>
        </section>
      `;
    }

    function renderOpsPlacementHintLoading(item, options = {}) {
      const cardId = String(options.cardId || "opsLibraryPlacementHintCard");
      return `
        <section id="${escapeHtml(cardId)}" class="ops-placement-hint-card is-loading" aria-live="polite">
          <div class="operator-helper-head">
            <div>
              <strong>${escapeHtml(t(isOpsPlacementHintUnslottedItem(item) ? "operator.placement.title.unslotted" : "operator.placement.title.assigned"))}</strong>
            </div>
          </div>
          <div class="mini muted">${escapeHtml(t(isOpsPlacementHintUnslottedItem(item) ? "operator.placement.state.loading.unslotted" : "operator.placement.state.loading.assigned"))}</div>
        </section>
      `;
    }

    function renderOpsPlacementHintUnavailable(item, message = "", options = {}) {
      const cardId = String(options.cardId || "opsLibraryPlacementHintCard");
      const detail = String(message || "").trim() || t(isOpsPlacementHintUnslottedItem(item) ? "operator.placement.state.unavailable.unslotted" : "operator.placement.state.unavailable.assigned");
      return `
        <section id="${escapeHtml(cardId)}" class="ops-placement-hint-card is-unavailable" aria-live="polite">
          <div class="operator-helper-head">
            <div>
              <strong>${escapeHtml(t(isOpsPlacementHintUnslottedItem(item) ? "operator.placement.title.unslotted" : "operator.placement.title.assigned"))}</strong>
            </div>
          </div>
          <div class="mini muted">${escapeHtml(detail)}</div>
        </section>
      `;
    }

    function renderOpsPlacementHintReady(item, payload = {}, options = {}) {
      const cardId = String(options.cardId || "opsLibraryPlacementHintCard");
      const rows = getOpsPlacementHintRows(payload);
      const fallbackText = String(payload.fallback || payload.message || "").trim() || t(isOpsPlacementHintUnslottedItem(item) ? "operator.placement.state.fallback.unslotted" : "operator.placement.state.fallback.assigned");
      return `
        <section id="${escapeHtml(cardId)}" class="ops-placement-hint-card" aria-live="polite">
          <div class="operator-helper-head">
            <div>
              <strong>${escapeHtml(t(isOpsPlacementHintUnslottedItem(item) ? "operator.placement.title.unslotted" : "operator.placement.title.assigned"))}</strong>
            </div>
            ${rows.length ? `<span class="operator-helper-pill">${escapeHtml(formatCount(rows.length))}</span>` : ""}
          </div>
          ${rows.length
            ? `<div class="ops-placement-hint-list">${rows.slice(0, 4).map((row) => renderOpsPlacementHintRow(item, row)).join("")}</div>`
            : `<div class="mini muted">${escapeHtml(fallbackText)}</div>`
          }
        </section>
      `;
    }

    function renderOpsPlacementHintCard(item, options = {}) {
      const state = String(options.state || "").trim();
      const cardId = String(options.cardId || "opsLibraryPlacementHintCard");
      const renderOptions = { cardId };
      if (state === "idle") return renderOpsPlacementHintIdle(item, renderOptions);
      if (state === "loading") return renderOpsPlacementHintLoading(item, renderOptions);
      if (state === "unavailable") return renderOpsPlacementHintUnavailable(item, options.message || "", renderOptions);
      if (state === "ready") return renderOpsPlacementHintReady(item, options.payload || {}, renderOptions);
      const ownedItemId = getOpsPlacementHintOwnedItemId(item);
      if (ownedItemId <= 0) return renderOpsPlacementHintIdle(item, renderOptions);
      const cached = opsPlacementHintCache.get(ownedItemId) || null;
      if (cached) {
        return cached.available === false
          ? renderOpsPlacementHintUnavailable(item, cached.message || cached.detail || "", renderOptions)
          : renderOpsPlacementHintReady(item, cached, renderOptions);
      }
      return renderOpsPlacementHintLoading(item, renderOptions);
    }

    function renderOpsLibraryContextDefault(climate) {
      const activeItem = homeSelectedContextItem || homePreviewContextItem || null;
      if (activeItem) {
        renderOpsLibraryContextSelection(activeItem);
        return;
      }
      $("opsLibraryContextBody").innerHTML = `
        <div class="ops-library-context-empty">
          <h3>${escapeHtml(t("operator.context.title"))}</h3>
          <div class="mini muted">${escapeHtml(t("operator.context.subtitle"))}</div>
        </div>
        ${renderOpsPluginSection(`
          ${renderOpsArtistContextIdle()}
        `)}
      `;
    }

    function renderOpsLibraryContextSelection(item) {
      const title = String(item?.item_title || item?.item_name_override || "-").trim() || "-";
      const artist = String(item?.artist_or_brand || "").trim();
      const isPinnedSelection = item === homeSelectedContextItem;
      const currentLocation = buildOperatorLocationLabel(item);
      const currentSlotCode = String(item?.current_slot_code || "").trim();
      const previousSlotCode = String(item?.previous_slot_code || "").trim();
      const currentCabinetName = String(item?.current_cabinet_name || "").trim();
      const currentColumnCode = String(item?.current_column_code || "").trim();
      const currentCellCode = String(item?.current_cell_code || "").trim();
      const ownedItemId = Number(item?.owned_item_id || item?.id || 0);
      const canOpenCurrent = Boolean(String(item?.current_slot_code || "").trim() || (currentCabinetName && currentColumnCode && currentCellCode));
      const canOpenPrevious = Boolean(previousSlotCode && previousSlotCode !== "UNASSIGNED");
      const previousLocation = canOpenPrevious ? buildOperatorPreviousLocationLabel(item) : t("operator.context.state.no_history");
      const miniMapHtml = renderOpsLibraryContextMiniCabinetMap(item);
      const slotPreviewHtml = renderOpsLibraryContextSlotPreview(item);
      const spotifyAlbumId = String(item?.spotify_album_id || "").trim() || null;
      const hasLocalLink = Boolean(item?.has_local_link);
      const masterIdForOps = Number(item?.linked_album_master_id || 0);
      const pluginSectionHtml = renderOpsPluginSection(`
        ${renderOpsArtistContextCard(item)}
        <div id="opsLibraryContextReviewSection">${renderAlbumReviewSection(item)}</div>
      `);
      $("opsLibraryContextBody").innerHTML = `
        <div class="ops-library-context-head">
          <div class="ops-library-context-head-copy">
            <h3>${escapeHtml(title)}</h3>
            ${artist ? `<div class="ops-library-context-subtitle">${escapeHtml(artist)}</div>` : ""}
          </div>
          ${isPinnedSelection ? `<button class="btn ghost tiny" type="button" data-operator-context-clear="1">${escapeHtml(t("operator.context.action.clear"))}</button>` : ""}
        </div>
        ${hasLocalLink ? `<div id="opsLibraryContextPlayerSlot"></div>` : (spotifyAlbumId ? `<div class="ops-ctx-spotify-wrap">${_spotifyEmbedHtml(spotifyAlbumId, 352)}</div>` : "")}
        <div class="operator-mini-list">
          <div id="opsLibraryContextCurrentLocation" class="operator-mini-line operator-mini-card">
            <strong>${escapeHtml(t("operator.context.field.current"))}</strong>
            <span>${escapeHtml(currentLocation)}</span>
            ${canOpenCurrent
              ? `<button class="operator-mini-linkchip" type="button"
                  data-operator-context-open-cabinet="${ownedItemId}"
                  data-operator-slot-code="${escapeHtml(String(item?.current_slot_code || "").trim())}"
                >${escapeHtml(t("operator.context.action.open"))}</button>`
              : ""}
          </div>
          <div id="opsLibraryContextPreviousLocation" class="operator-mini-line operator-mini-card">
            <strong>${escapeHtml(t("operator.context.field.previous"))}</strong>
            <span>${escapeHtml(previousLocation)}</span>
            ${canOpenPrevious
              ? `<button class="operator-mini-linkchip" type="button"
                  data-operator-context-open-cabinet="${ownedItemId}"
                  data-operator-slot-code="${escapeHtml(previousSlotCode)}"
                >${escapeHtml(t("operator.context.action.open"))}</button>`
              : ""}
          </div>
        </div>
        ${pluginSectionHtml}
        ${miniMapHtml}
        ${slotPreviewHtml}
      `;
      if (hasLocalLink && masterIdForOps > 0) {
        _lp.audio.pause(); _lp.audio.src = ""; _lp.idx = -1;
        _lp._slotId = 'opsLibraryContextPlayerSlot';
        _lp.load(masterIdForOps).catch(() => {});
      } else {
        if (_lp._slotId === 'opsLibraryContextPlayerSlot') { _lp.audio.pause(); _lp.idx = -1; }
      }
      const opsCtxBody = $("opsLibraryContextBody");
      if (opsCtxBody) {
        opsCtxBody.querySelectorAll(".ops-album-review-card .ops-artist-context-toggle").forEach(function(btn) {
          btn.addEventListener("click", function() {
            const expanded = btn.dataset.expanded === "true";
            const textEl = document.getElementById(btn.id.replace("albumReviewToggleBtn_", "albumReviewText_"));
            if (!textEl) return;
            if (expanded) {
              textEl.textContent = btn.dataset.reviewPreview;
              btn.textContent = btn.dataset.showLabel || "펼치기 ▼";
              btn.dataset.expanded = "false";
              btn.setAttribute("aria-expanded", "false");
            } else {
              textEl.textContent = btn.dataset.reviewFull;
              btn.textContent = btn.dataset.hideLabel || "접기 ▲";
              btn.dataset.expanded = "true";
              btn.setAttribute("aria-expanded", "true");
            }
          });
        });
      }
      if (!item.review_text && masterIdForOps > 0) {
        fetchWithRetry(`/album-masters/${masterIdForOps}`).then((res) => res.json()).then((masterData) => {
          if (masterData?.review_text) {
            const reviewEl = document.getElementById("opsLibraryContextReviewSection");
            if (reviewEl) {
              reviewEl.innerHTML = renderAlbumReviewSection({ ...item, review_text: masterData.review_text, review_source: masterData.review_source, review_url: masterData.review_url });
              reviewEl.querySelectorAll(".ops-album-review-card .ops-artist-context-toggle").forEach(function(btn) {
                btn.addEventListener("click", function() {
                  const expanded = btn.dataset.expanded === "true";
                  const textEl = document.getElementById(btn.id.replace("albumReviewToggleBtn_", "albumReviewText_"));
                  if (!textEl) return;
                  if (expanded) {
                    textEl.textContent = btn.dataset.reviewPreview;
                    btn.textContent = btn.dataset.showLabel || "펼치기 ▼";
                    btn.dataset.expanded = "false";
                    btn.setAttribute("aria-expanded", "false");
                  } else {
                    textEl.textContent = btn.dataset.reviewFull;
                    btn.textContent = btn.dataset.hideLabel || "접기 ▲";
                    btn.dataset.expanded = "true";
                    btn.setAttribute("aria-expanded", "true");
                  }
                });
              });
            }
          }
        }).catch(() => {});
      }
      loadOpsArtistContext(item).catch(() => {});
      loadOpsLibraryContextSlotPreview(item).catch(() => {});
    }

    function renderOpsLibraryContextMiniCabinetMap(item, options = {}) {
      const mapId = String(options.mapId || "opsLibraryContextMiniCabinetMap");
      const slotCode = String(item?.current_slot_code || "").trim();
      const cabinet = findOpsLibraryContextCabinet(item);
      if (!slotCode || !cabinet) return "";
      const summaryBits = [
        dashboardFloorsLabel(cabinet.floorCount),
        dashboardCellCountLabel(cabinet.slotCount),
      ].filter(Boolean);
      return `
        <section id="${escapeHtml(mapId)}" class="ops-library-mini-map">
          <div class="ops-library-mini-map-head">
            <strong>${escapeHtml(cabinet.title)}</strong>
            <span>${escapeHtml(summaryBits.join(" · "))}</span>
          </div>
          <div class="ops-library-mini-map-grid has-active">
            ${cabinet.floorCodes.map((floorCode) => {
              const floorRows = cabinet.rows.filter((row) => String(row?.column_code || "").trim() === floorCode);
              return `
                <div class="ops-library-mini-map-floor">
                  <div class="ops-library-mini-map-floorcode">${escapeHtml(dashboardColumnCodeLabel(floorCode))}</div>
                  <div class="ops-library-mini-map-cells cell-count-${Math.max(1, floorRows.length)}">
                    ${floorRows.map((row) => {
                      const toneClass = dashboardCabinetMapCellTone(row);
                      const active = String(row?.slot_code || "").trim() === slotCode;
                      const occupancy = dashboardCabinetOccupancyLabel(row);
                      const hoverTitle = dashboardSlotHoverHintText(row);
                      const _opsCellFillPct = Math.min(200, Math.round(dashboardCabinetOccupancyRatio(row) * 100));
                      return `
                        <div
                          class="ops-library-mini-map-cell ${toneClass} ${active ? "active" : ""}"
                          aria-label="${escapeHtml(`${dashboardCabinetMapCellLabel(row)} ${occupancy.percentText}`)}"
                          title="${escapeHtml(hoverTitle)}"
                          data-operator-context-open-cabinet="${Number(item?.owned_item_id || item?.id || 0)}"
                          data-operator-slot-code="${escapeHtml(String(row?.slot_code || "").trim())}"
                          style="--cell-fill:${_opsCellFillPct}%"
                        >
                          <span class="ops-library-mini-map-cellcode">${escapeHtml(dashboardCabinetMapCellLabel(row))}</span>
                          <strong class="ops-library-mini-map-cellcount">${escapeHtml(occupancy.percentText)}</strong>
                          ${active ? `<span class="ops-library-mini-map-active-badge">${escapeHtml(t("operator.context.map.active_badge"))}</span>` : ""}
                        </div>
                      `;
                    }).join("")}
                  </div>
                </div>
              `;
            }).join("")}
          </div>
        </section>
      `;
    }

    function renderOpsLibraryContextSlotPreviewContent(item, rows, options = {}) {
      const slotCode = String(item?.current_slot_code || "").trim();
      const currentLocation = buildOperatorLocationLabel(item);
      const errorText = String(options.errorText || "").trim();
      if (errorText) return `<div class="mini muted">${escapeHtml(errorText)}</div>`;
      if (options.loading) return `<div class="mini muted">${escapeHtml(t("operator.context.preview.loading"))}</div>`;
      if (!Array.isArray(rows) || !rows.length) return `<div class="mini muted">${escapeHtml(t("operator.context.preview.empty"))}</div>`;
      return `
        <div class="ops-library-slot-preview-head">
          <strong>${escapeHtml(t("operator.context.preview.title"))}</strong>
          <span>${escapeHtml(currentLocation || slotCode)}</span>
        </div>
        <div class="ops-library-slot-preview-grid">
          ${rows.slice(0, 6).map((row) => {
            const title = getDashboardSelectableTitle(row);
            const coverUrl = resolveOwnedItemCoverUrl(row);
            const fallbackLabel = mediaIconLabel(row?.format_name || row?.category || "-");
            const ownedItemId = Number(row?.id || 0);
            const isActiveItem = ownedItemId > 0 && ownedItemId === Number(item?.owned_item_id || item?.id || 0);
            const sizeClass = dashboardShelfSizeClass(row);
            return `
              <button class="ops-library-slot-preview-item ${isActiveItem ? "active" : ""}" type="button"
                title="${escapeHtml(title)}"
                data-operator-context-open-cabinet="${ownedItemId}"
                data-operator-slot-code="${escapeHtml(String(row?.slot_code || slotCode).trim())}"
                data-cabinet-name="${escapeHtml(String(row?.cabinet_name || item?.current_cabinet_name || "").trim())}"
                data-column-code="${escapeHtml(String(row?.column_code || item?.current_column_code || "").trim())}"
                data-cell-code="${escapeHtml(String(row?.cell_code || item?.current_cell_code || "").trim())}"
              >
                <div class="ops-library-slot-preview-thumb">
                  <span class="ops-library-slot-preview-format ${sizeClass}">${escapeHtml(fallbackLabel)}</span>
                  ${isActiveItem ? `<span class="ops-library-slot-preview-badge">${escapeHtml(t("operator.context.preview.badge_selected"))}</span>` : ""}
                  ${coverUrl
                    ? `<img src="${escapeHtml(coverUrl)}" alt="${escapeHtml(title)}" />`
                    : `<span>${escapeHtml(fallbackLabel)}</span>`}
                </div>
                <div class="ops-library-slot-preview-label">${escapeHtml(title)}</div>
              </button>
            `;
          }).join("")}
        </div>
        <div class="ops-library-slot-preview-actions">
          <button class="ops-library-slot-preview-link" type="button"
            data-operator-context-open-cabinet="${Number(item?.owned_item_id || item?.id || 0)}"
            data-operator-slot-code="${escapeHtml(slotCode)}"
            data-cabinet-name="${escapeHtml(String(item?.current_cabinet_name || "").trim())}"
            data-column-code="${escapeHtml(String(item?.current_column_code || "").trim())}"
            data-cell-code="${escapeHtml(String(item?.current_cell_code || "").trim())}"
          >${escapeHtml(t("operator.context.preview.action.open_current"))}</button>
        </div>
      `;
    }

    function renderOpsLibraryContextSlotPreview(item, options = {}) {
      const rootId = String(options.rootId || "opsLibraryContextSlotPreview");
      const slotCode = String(item?.current_slot_code || "").trim();
      if (!slotCode || slotCode === "UNASSIGNED") return "";
      const rows = getOpsLibraryContextSlotPreviewRows(slotCode);
      const isLoading = opsLibraryContextSlotPreviewLoadingSlotCode === slotCode && rows === null;
      return `
        <section id="${escapeHtml(rootId)}" class="ops-library-slot-preview">
          ${renderOpsLibraryContextSlotPreviewContent(item, rows, { loading: isLoading })}
        </section>
      `;
    }

    function updateOperatorFeedControls() {
      const heading = $("operatorLookupHeading");
      const count = $("operatorLookupCount");
      const controls = $("operatorFeedControls");
      const pagers = [$("operatorFeedPager"), $("operatorFeedPagerBottom")].filter(Boolean);
      const isFeedMode = operatorLookupMode === "FEED";
      if (heading) heading.textContent = isFeedMode ? operatorFeedKindLabel(operatorFeedKind) : t("operator.feed.heading.search_results");
      if (count) {
        const value = isFeedMode ? operatorFeedTotalCount : operatorLookupResults.length;
        count.textContent = countWithUnit(value);
      }
      setDisplayMode(controls, isFeedMode ? "inline-flex" : "none");
      if (!pagers.length) return;
      if (!isFeedMode) {
        pagers.forEach((pager) => { pager.innerHTML = ""; });
        return;
      }
      const totalPages = Math.max(1, Math.ceil(operatorFeedTotalCount / operatorFeedPageSize));
      if (totalPages <= 1) {
        pagers.forEach((pager) => { pager.innerHTML = ""; });
        return;
      }
      const tokens = buildOperatorFeedPagerTokens(operatorFeedPage, totalPages);
      const markup = [
        `<button class="operator-feed-pagebtn" type="button" data-operator-feed-page="${operatorFeedPage - 1}" ${operatorFeedPage <= 1 ? "disabled" : ""}>&lt;</button>`,
        ...tokens.map((token) => token === "gap"
          ? `<span class="operator-feed-pagegap">…</span>`
          : `<button class="operator-feed-pagebtn ${token === operatorFeedPage ? "active" : ""}" type="button" data-operator-feed-page="${token}">${token}</button>`),
        `<button class="operator-feed-pagebtn" type="button" data-operator-feed-page="${operatorFeedPage + 1}" ${operatorFeedPage >= totalPages ? "disabled" : ""}>&gt;</button>`,
      ].join("");
      pagers.forEach((pager) => { pager.innerHTML = markup; });
    }

    function operatorMetaPairHtml(label, value, options = {}) {
      const text = String(value || "").trim();
      if (!text || text === "-") return "";
      const subtleClass = options.subtle ? " is-subtle" : "";
      return `<span class="operator-meta-pair${subtleClass}"><span class="operator-meta-key">${escapeHtml(label)}</span><span class="operator-meta-value">${escapeHtml(text)}</span></span>`;
    }

    function operatorCollectorMetaHtml(row) {
      const releaseDate = String(row?.released_date || "").trim();
      const releaseCountry = String(row?.pressing_country || row?.country || "").trim() || "-";
      const labelName = String(row?.label_name || "").trim();
      const catalogNo = String(row?.catalog_no || "").trim();
      const barcode = String(row?.barcode || "").trim();
      const catalogSummary = [catalogNo, barcode].filter((v) => v).join(" / ");
      const labelCatalogText = labelName && catalogSummary
        ? `${labelName} (${catalogSummary})`
        : (labelName || catalogSummary || "-");
      const formatSummary = firstOperatorFormatLine(row?.format_items || [], row?.format_name || "");
      const parts = [
        operatorMetaPairHtml(t("operator.feed.meta.summary.release"), releaseDate),
        operatorMetaPairHtml(t("operator.feed.meta.summary.country"), releaseCountry),
        operatorMetaPairHtml(t("operator.feed.meta.summary.label"), labelCatalogText),
        operatorMetaPairHtml(t("operator.feed.meta.summary.format"), formatSummary),
      ].filter((value) => value);
      return parts.length ? parts.join('<span class="operator-meta-separator">/</span>') : `<span class="operator-meta-value">-</span>`;
    }

    function renderOperatorHomeRecentItems(items, options = {}) {
      const list = Array.isArray(items) ? items : [];
      const kind = String(options.kind || "").trim();
      return list.map((row, index) => {
        const ownedItemId = Number(row.owned_item_id || row.id || 0);
        const titleParts = buildOperatorDisplayTitleParts(row);
        const title = titleParts.title;
        const artist = titleParts.artist;
        const whenLabel = kind === "moved" ? t("operator.feed.meta.moved") : t("operator.feed.meta.registered");
        const whenText = formatOperatorCardDateTime(row.created_at);
        const currentLocation = buildOperatorLocationLabel(row);
        const releaseDate = String(row.released_date || "").trim();
        const releaseCountry = String(row.pressing_country || row.country || "").trim() || "-";
        const labelName = String(row.label_name || "").trim();
        const catalogNo = String(row.catalog_no || "").trim();
        const barcode = String(row.barcode || "").trim();
        const catalogSummary = [catalogNo, barcode].filter((v) => v).join(" / ");
        const labelCatalogText = labelName && catalogSummary
          ? `${labelName} (${catalogSummary})`
          : (labelName || catalogSummary || "-");
        const formatSummary = firstOperatorFormatLine(row.format_items);
        const runoutSample = operatorRunoutSampleText(row.runout_sample || row.runout_matrix || []);
        const collectorMetaLine = [
          releaseDate || null,
          releaseCountry,
          labelCatalogText,
          formatSummary,
        ].filter((v) => v && v !== "-").join(" / ");
        const collectorMetaHtml = operatorCollectorMetaHtml(row);
        const currentCabinetName = String(row.current_cabinet_name || "").trim();
        const currentColumnCode = String(row.current_column_code || "").trim();
        const currentCellCode = String(row.current_cell_code || "").trim();
        const hasCurrentTriplet = Boolean(currentCabinetName && currentColumnCode && currentCellCode);
        const repairDiscogsMasterSlot = discogsRepairSlotHtml("operator", {
          ownedItemId,
          sourceCode: row?.source_code,
          masterSourceCode: row?.linked_master_source_code,
          sourceExternalId: row?.source_external_id,
        });
        const currentLocationButton = hasCurrentTriplet
          ? `<button class="btn ghost tiny home-master-location-btn operator-title-side-location-btn" type="button" data-operator-open-cabinet="${ownedItemId}" data-cabinet-name="${escapeHtml(currentCabinetName)}" data-column-code="${escapeHtml(currentColumnCode)}" data-cell-code="${escapeHtml(currentCellCode)}">${escapeHtml(t("operator.feed.meta.current"))} ${escapeHtml(currentLocation)}</button>`
          : `<span class="operator-title-side-fallback">${escapeHtml(t("operator.feed.meta.current"))} ${escapeHtml(currentLocation)}</span>`;
        return `
          <div class="operator-recent-item">
            <div class="operator-recent-copy">
              <div class="operator-title-line">
                <strong>${escapeHtml(title)}${artist ? `<span>${escapeHtml(artist)}</span>` : ""}</strong>
              </div>
              <div class="operator-secondary-line">
                <div class="operator-secondary-line-main">
                  <span class="operator-label-chip">${escapeHtml(String(row.label_id || "").trim() || "-")}</span>
                  ${whenText ? `<span class="operator-title-side-meta"><strong>${escapeHtml(whenLabel)}</strong> ${escapeHtml(whenText)}</span>` : ""}
                </div>
                ${currentLocationButton}
              </div>
              <div class="operator-recent-meta">
                ${collectorMetaHtml}
              </div>
              ${runoutSample !== "-" ? `<div class="operator-meta-subline">${escapeHtml(runoutSample)}</div>` : ""}
              ${repairDiscogsMasterSlot}
            </div>
          </div>
        `;
      }).join("");
    }

    function renderOperatorFeedItems(items, options = {}) {
      const list = Array.isArray(items) ? items : [];
      const kind = String(options.kind || "").trim() === "moved" ? "moved" : "registered";
      return list.map((row, index) => {
        const ownedItemId = Number(row.owned_item_id || row.id || 0);
        const titleParts = buildOperatorDisplayTitleParts(row);
        const title = titleParts.title;
        const artist = titleParts.artist;
        const whenLabel = kind === "moved" ? t("operator.feed.meta.moved") : t("operator.feed.meta.registered");
        const whenText = formatOperatorCardDateTime(row.created_at);
        const currentLocation = buildOperatorLocationLabel(row);
        const releaseDate = String(row.released_date || "").trim();
        const releaseCountry = String(row.pressing_country || row.country || "").trim() || "-";
        const labelName = String(row.label_name || "").trim();
        const catalogNo = String(row.catalog_no || "").trim();
        const barcode = String(row.barcode || "").trim();
        const catalogSummary = [catalogNo, barcode].filter((v) => v).join(" / ");
        const labelCatalogText = labelName && catalogSummary
          ? `${labelName} (${catalogSummary})`
          : (labelName || catalogSummary || "-");
        const formatSummary = firstOperatorFormatLine(row.format_items);
        const runoutSample = operatorRunoutSampleText(row.runout_sample || row.runout_matrix || []);
        const collectorMetaLine = [
          releaseDate || null,
          releaseCountry,
          labelCatalogText,
          formatSummary,
        ].filter((v) => v && v !== "-").join(" / ");
        const collectorMetaHtml = operatorCollectorMetaHtml(row);
        const currentCabinetName = String(row.current_cabinet_name || "").trim();
        const currentColumnCode = String(row.current_column_code || "").trim();
        const currentCellCode = String(row.current_cell_code || "").trim();
        const hasCurrentTriplet = Boolean(currentCabinetName && currentColumnCode && currentCellCode);
        const currentLocationButton = hasCurrentTriplet
          ? `<button class="btn ghost tiny home-master-location-btn operator-title-side-location-btn" type="button" data-operator-open-cabinet="${ownedItemId}" data-operator-slot-code="${escapeHtml(String(row.current_slot_code || "").trim())}" data-cabinet-name="${escapeHtml(currentCabinetName)}" data-column-code="${escapeHtml(currentColumnCode)}" data-cell-code="${escapeHtml(currentCellCode)}">${escapeHtml(t("operator.feed.meta.current"))} ${escapeHtml(currentLocation)}</button>`
          : `<span class="operator-title-side-fallback">${escapeHtml(t("operator.feed.meta.current"))} ${escapeHtml(currentLocation)}</span>`;
        const repairDiscogsMasterSlot = discogsRepairSlotHtml("operator", {
          ownedItemId,
          sourceCode: row?.source_code,
          masterSourceCode: row?.linked_master_source_code,
          sourceExternalId: row?.source_external_id,
        });
        const coverUrl = normalizeRenderableCoverUrl(row.cover_image_url);
        const coverHtml = coverUrl
          ? `<img src="${escapeHtml(coverUrl)}" alt="${escapeHtml(title)}" />`
          : escapeHtml(String(row.format_name || row.category || "-").trim() || "-");
        const feedMasterId = Number(row.linked_album_master_id || 0);
        const feedHasLocalLink = Boolean(row.has_local_link);
        const feedSpotifyAlbumId = String(row.spotify_album_id || "").trim() || null;
        const feedMediaBadges = [
          feedHasLocalLink && feedMasterId > 0 ? `<button class="local-player-badge" data-master-id="${feedMasterId}" title="로컬 재생">♪</button>` : "",
          feedSpotifyAlbumId ? `<button class="spotify-badge" data-sp-album="${escapeHtml(feedSpotifyAlbumId)}" title="Spotify">▶</button>` : "",
        ].filter(Boolean).join("");
        return `
          <div class="ops-card" data-operator-context-source="feed" data-operator-context-index="${index}">
            <figure class="ops-card-cover">${coverHtml}</figure>
            <div class="ops-card-body">
              <p class="ops-card-title">${escapeHtml(title)}</p>
              ${artist ? `<p class="ops-card-artist">${escapeHtml(artist)}</p>` : ""}
              <div class="ops-card-chips">
                <span class="ops-card-id">${escapeHtml(String(row.label_id || "").trim() || "-")}</span>
                ${feedMediaBadges}
              </div>
              <div class="ops-card-meta">${collectorMetaHtml}</div>
              ${runoutSample !== "-" ? `<div class="ops-card-runout">${escapeHtml(runoutSample)}</div>` : ""}
              ${repairDiscogsMasterSlot}
            </div>
            <div class="ops-card-side">
              ${currentLocationButton}
              ${whenText ? `<span class="ops-card-when">${escapeHtml(whenText)}</span>` : ""}
            </div>
          </div>
        `;
      }).join("");
    }

    function renderOperatorHomeRecentSections() {
      const el = $("operatorRecentSections");
      if (!el) return;
      el.innerHTML = "";
      setDisplayMode(el, "none");
    }

    function operatorSummaryReasonLabel(reason) {
      if (reason === "barcode") return t("operator.helper.reason.barcode");
      if (reason === "label") return t("operator.helper.reason.label");
      if (reason === "titleArtist") return t("operator.helper.reason.title_artist");
      if (reason === "assigned") return t("operator.helper.reason.assigned");
      if (reason === "first") return t("operator.helper.reason.first");
      return "";
    }

    function renderOperatorHelperSummary() {
      const el = $("operatorHelperSummary");
      if (!el) return;
      if (operatorLookupMode !== "SEARCH") {
        el.innerHTML = "";
        setDisplayMode(el, "none");
        return;
      }
      setDisplayMode(el, "block");
      const summary = operatorLookupSummary || emptyOperatorLookupSummary();
      if (summary.status === "idle") {
        el.innerHTML = "";
        setDisplayMode(el, "none");
        return;
      }
      if (summary.status === "error") {
        el.innerHTML = `
          <div class="operator-helper-card is-error">
            <div class="operator-helper-head">
              <div>
                <div class="operator-helper-kicker">${escapeHtml(t("operator.helper.kicker"))}</div>
                <strong>${escapeHtml(t("operator.helper.error_title"))}</strong>
              </div>
            </div>
            <div class="operator-helper-grid">
              <div class="operator-helper-cell">
                <span>${escapeHtml(t("operator.helper.field.query"))}</span>
                <strong>${escapeHtml(summary.normalizedQuery || "-")}</strong>
              </div>
              <div class="operator-helper-cell">
                <span>${escapeHtml(t("operator.helper.field.top_candidate"))}</span>
                <strong>${escapeHtml(t("operator.helper.state.load_failed"))}</strong>
              </div>
              <div class="operator-helper-cell">
                <span>${escapeHtml(t("operator.helper.field.current_location"))}</span>
                <strong>-</strong>
              </div>
            </div>
          </div>
        `;
        return;
      }
      const topCandidate = summary.topCandidate || null;
      const title = String(topCandidate?.item_title || topCandidate?.item_name_override || "").trim() || t("operator.helper.state.no_candidate");
      const artist = String(topCandidate?.artist_or_brand || "").trim();
      const topCandidateLabel = topCandidate ? `${title}${artist ? ` / ${artist}` : ""}` : t("operator.helper.state.no_candidate");
      const locationLabel = topCandidate ? (summary.locationSummary || t("operator.feed.state.unslotted")) : "-";
      const currentCabinetName = String(topCandidate?.current_cabinet_name || "").trim();
      const currentColumnCode = String(topCandidate?.current_column_code || "").trim();
      const currentCellCode = String(topCandidate?.current_cell_code || "").trim();
      const canOpenCabinet = Boolean(topCandidate && currentCabinetName && currentColumnCode && currentCellCode);
      const reasonLabel = operatorSummaryReasonLabel(summary.matchReason);
      const ownedItemId = Number(topCandidate?.owned_item_id || topCandidate?.id || 0);
      el.innerHTML = `
        <div class="operator-helper-card ${summary.status === "empty" ? "is-empty" : ""}">
          <div class="operator-helper-head">
            <div>
              <div class="operator-helper-kicker">${escapeHtml(t("operator.helper.kicker"))}</div>
              <strong>${escapeHtml(t("operator.helper.title"))}</strong>
            </div>
            ${reasonLabel ? `<span class="operator-helper-pill">${escapeHtml(reasonLabel)}</span>` : ""}
          </div>
          <div class="operator-helper-grid">
            <div class="operator-helper-cell">
              <span>${escapeHtml(t("operator.helper.field.query"))}</span>
              <strong>${escapeHtml(summary.normalizedQuery || "-")}</strong>
            </div>
            <div class="operator-helper-cell">
              <span>${escapeHtml(t("operator.helper.field.top_candidate"))}</span>
              <strong>${escapeHtml(topCandidateLabel)}</strong>
            </div>
            <div class="operator-helper-cell">
              <span>${escapeHtml(t("operator.helper.field.current_location"))}</span>
              <strong>${escapeHtml(locationLabel)}</strong>
            </div>
          </div>
          ${canOpenCabinet
            ? `<div class="operator-helper-actions"><button class="btn secondary tiny" type="button" data-operator-open-cabinet="${ownedItemId}" data-operator-slot-code="${escapeHtml(String(topCandidate?.current_slot_code || "").trim())}" data-cabinet-name="${escapeHtml(currentCabinetName)}" data-column-code="${escapeHtml(currentColumnCode)}" data-cell-code="${escapeHtml(currentCellCode)}">${escapeHtml(t("operator.helper.action.open_cabinet"))}</button></div>`
            : topCandidate
              ? `<div class="mini muted">${escapeHtml(t("operator.helper.state.no_current_location"))}</div>`
              : `<div class="mini muted">${escapeHtml(t("operator.helper.state.keep_results"))}</div>`
          }
        </div>
      `;
    }

    function operatorRunoutSampleText(value) {
      const runoutValues = splitRunoutList(value).filter((v) => String(v || "").trim());
      if (!runoutValues.length) return "-";
      return runoutValues.slice(0, 2).join(" | ");
    }

    function renderOperatorLookupResults() {
      const el = $("operatorLookupResults");
      if (!el) return;
      renderOperatorHelperSummary();
      updateOperatorFeedControls();
      if (operatorLookupMode === "FEED") {
        if (!operatorFeedItems.length) {
          el.innerHTML = `<div class="mini muted">${escapeHtml(operatorFeedKind === "moved" ? t("operator.feed.state.no_recent_moved") : t("operator.feed.state.no_recent_registered"))}</div>`;
          return;
        }
        el.innerHTML = renderOperatorFeedItems(operatorFeedItems, { kind: operatorFeedKind });
        queueDiscogsRepairEligibilityHydration(el);
        return;
      }
      if (!operatorLookupResults.length) {
        el.innerHTML = `<div class="mini muted">${escapeHtml(t("operator.feed.state.no_search_results"))}</div>`;
        return;
      }
      el.innerHTML = operatorLookupResults.map((row, index) => {
        const ownedItemId = Number(row.owned_item_id || row.id || 0);
        const titleParts = buildOperatorDisplayTitleParts(row);
        const title = titleParts.title;
        const artist = titleParts.artist;
        const whenLabel = t("operator.feed.meta.registered");
        const whenText = formatOperatorCardDateTime(row.created_at);
        const releaseDate = String(row.released_date || "").trim();
        const releaseCountry = String(row.pressing_country || row.country || "").trim() || "-";
        const labelName = String(row.label_name || "").trim();
        const catalogNo = String(row.catalog_no || "").trim();
        const barcode = String(row.barcode || "").trim();
        const catalogSummary = [catalogNo, barcode].filter((v) => v).join(" / ");
        const labelCatalogText = labelName && catalogSummary
          ? `${labelName} (${catalogSummary})`
          : (labelName || catalogSummary || "-");
        const formatSummary = firstOperatorFormatLine(row.format_items);
        const runoutSample = operatorRunoutSampleText(row.runout_sample || row.runout_matrix || []);
        const collectorMetaLine = [
          releaseDate || null,
          releaseCountry,
          labelCatalogText,
          formatSummary,
        ].filter((v) => v && v !== "-").join(" / ");
        const collectorMetaHtml = operatorCollectorMetaHtml(row);
        const currentLocation = buildOperatorLocationLabel(row);
        const trackHits = Array.isArray(row.track_matches) ? row.track_matches : [];
        const currentCabinetName = String(row.current_cabinet_name || "").trim();
        const currentColumnCode = String(row.current_column_code || "").trim();
        const currentCellCode = String(row.current_cell_code || "").trim();
        const hasCurrentTriplet = Boolean(currentCabinetName && currentColumnCode && currentCellCode);
        const currentLocationButton = hasCurrentTriplet
          ? `<button class="btn ghost tiny home-master-location-btn operator-title-side-location-btn" type="button" data-operator-open-cabinet="${ownedItemId}" data-operator-slot-code="${escapeHtml(String(row.current_slot_code || "").trim())}" data-cabinet-name="${escapeHtml(currentCabinetName)}" data-column-code="${escapeHtml(currentColumnCode)}" data-cell-code="${escapeHtml(currentCellCode)}">${escapeHtml(t("operator.feed.meta.current"))} ${escapeHtml(currentLocation)}</button>`
          : `<span class="operator-title-side-fallback">${escapeHtml(t("operator.feed.meta.current"))} ${escapeHtml(currentLocation)}</span>`;
        const coverUrl = normalizeRenderableCoverUrl(row.cover_image_url);
        const coverHtml = coverUrl
          ? `<img src="${escapeHtml(coverUrl)}" alt="${escapeHtml(title)}" />`
          : escapeHtml(String(row.format_name || row.category || "-").trim() || "-");
        const rightButtons = [];
        if (operatorCanUseManage()) {
          rightButtons.push(`<button class="btn ghost tiny" type="button" data-operator-open-manage="${ownedItemId}">${escapeHtml(t("media.manage.search.action.open_detail_manage"))}</button>`);
        }
        const actionsHtml = rightButtons.length ? rightButtons.join("") : "";
        // 도메인 배지
        const effectiveDc = String(row.effective_domain_code || "").trim().toUpperCase();
        const isOverridden = Boolean(row.override_domain_code);
        const albumMasterId = Number(row.album_master_id || 0);
        const domainBadgeHtml = effectiveDc
          ? `<span class="operator-domain-badge domain-${escapeHtml(effectiveDc)}${isOverridden ? " is-overridden" : ""}">${escapeHtml(dashboardDomainLabel(effectiveDc))}</span>`
          : "";
        const domainFixBtnHtml = albumMasterId > 0
          ? `<button class="operator-domain-fix-btn" type="button" data-operator-domain-fix="${albumMasterId}" data-current-sort-artist="${escapeHtml(String(row.sort_artist_name || "").trim())}" data-current-domain="${escapeHtml(effectiveDc)}">${escapeHtml(t("operator.lookup.domain.fix_btn"))}</button>`
          : "";
        const searchMasterId = Number(row.linked_album_master_id || 0);
        const searchHasLocalLink = Boolean(row.has_local_link);
        const searchSpotifyAlbumId = String(row.spotify_album_id || "").trim() || null;
        const searchMediaBadges = [
          searchHasLocalLink && searchMasterId > 0 ? `<button class="local-player-badge" data-master-id="${searchMasterId}" title="로컬 재생">♪</button>` : "",
          searchSpotifyAlbumId ? `<button class="spotify-badge" data-sp-album="${escapeHtml(searchSpotifyAlbumId)}" title="Spotify">▶</button>` : "",
        ].filter(Boolean).join("");
        return `
          <div class="ops-card" data-operator-context-source="search" data-operator-context-index="${index}">
            <figure class="ops-card-cover">${coverHtml}</figure>
            <div class="ops-card-body">
              <p class="ops-card-title">${escapeHtml(title)}</p>
              ${artist ? `<p class="ops-card-artist">${escapeHtml(artist)}</p>` : ""}
              <div class="ops-card-chips">
                <span class="ops-card-id">${escapeHtml(String(row.label_id || "").trim() || "-")}</span>
                ${domainBadgeHtml}
                ${domainFixBtnHtml}
                ${searchMediaBadges}
              </div>
              <div class="ops-card-meta">${collectorMetaHtml}</div>
              ${runoutSample !== "-" ? `<div class="ops-card-runout">${escapeHtml(runoutSample)}</div>` : ""}
              ${trackHits.length ? `<div class="ops-card-tracks">${trackHits.slice(0, 5).map((track) => `<div class="ops-card-track"><strong>${escapeHtml(t("operator.feed.track.label"))}</strong>${escapeHtml(track)}</div>`).join("")}</div>` : ""}
            </div>
            <div class="ops-card-side">
              ${currentLocationButton}
              ${whenText ? `<span class="ops-card-when">${escapeHtml(whenText)}</span>` : ""}
              ${actionsHtml ? `<div class="ops-card-actions">${actionsHtml}</div>` : ""}
            </div>
          </div>
        `;
      }).join("");
    }

    function renderOperatorRequestList() {
      const el = $("operatorRequestList");
      if (!el) return;
      $("operatorRequestCount").textContent = countWithUnit(operatorRequestItems.length);
      if (!operatorRequestItems.length) {
        el.innerHTML = `<div class="mini muted">${escapeHtml(t("operator.request.empty"))}</div>`;
        return;
      }
      el.innerHTML = operatorRequestItems.map((row) => {
        const requestId = Number(row.id || 0);
        const title = String(row.item_title || t("operator.request.title.unlinked")).trim() || t("operator.request.title.unlinked");
        const artist = String(row.artist_or_brand || "").trim();
        const snapshotLocation = buildOperatorSlotDisplayLabel(row.current_slot_display_snapshot, row.current_slot_code_snapshot, "", "", "");
        const previousLocation = buildOperatorSlotDisplayLabel(row.previous_slot_display_snapshot, row.previous_slot_code_snapshot, "", "", "");
        const currentLive = buildOperatorSlotDisplayLabel(row.current_live_slot_display_name || row.current_slot_display_snapshot, row.current_slot_code_snapshot, "", "", "");
        const readOnlyShell = isShellReadOnly();
        const coverUrl = normalizeRenderableCoverUrl(row.cover_image_url);
        const coverHtml = coverUrl
          ? `<img src="${escapeHtml(coverUrl)}" alt="${escapeHtml(title)}" />`
          : escapeHtml(String(row.category || "-").trim() || "-");
        return `
          <div class="operator-request-item">
            <div class="operator-cover">${coverHtml}</div>
            <div class="operator-main">
              <div class="operator-request-title">
                <strong>${escapeHtml(String(row.requested_track || "-").trim() || "-")}${row.matched_track_title ? `<span>${escapeHtml(String(row.matched_track_title).trim())}</span>` : ""}</strong>
              </div>
              <div class="operator-mini-list">
                <div class="operator-mini-line"><strong>${escapeHtml(t("operator.request.meta.item"))}</strong><span>${escapeHtml(title)}${artist ? ` / ${escapeHtml(artist)}` : ""}</span></div>
                <div class="operator-mini-line"><strong>${escapeHtml(t("operator.request.meta.origin"))}</strong><span>${escapeHtml(snapshotLocation)}</span><strong>${escapeHtml(t("operator.request.meta.previous"))}</strong><span>${escapeHtml(previousLocation)}</span></div>
                <div class="operator-mini-line"><strong>${escapeHtml(t("operator.request.meta.current"))}</strong><span>${escapeHtml(currentLive)}</span><strong>${escapeHtml(t("operator.request.meta.created"))}</strong><span>${escapeHtml(formatDateTimeCompact(row.created_at))}</span></div>
                ${row.customer_note ? `<div class="operator-mini-line"><strong>${escapeHtml(t("operator.request.meta.note"))}</strong><span>${escapeHtml(String(row.customer_note || "").trim())}</span></div>` : ""}
              </div>
            </div>
            <div class="operator-actions">
              <div class="operator-status-badges">
                <span class="operator-status-pill ${escapeHtml(operatorStatusClass(row.status))}">${escapeHtml(operatorStatusLabel(row.status))}</span>
              </div>
              ${readOnlyShell ? "" : `
              <button class="btn ghost tiny" type="button" data-operator-request-status="${requestId}" data-status="PLAYING">${escapeHtml(t("operator.request.action.playing"))}</button>
              <button class="btn ghost tiny" type="button" data-operator-request-status="${requestId}" data-status="RETURNED">${escapeHtml(t("operator.request.action.returned"))}</button>
              <button class="btn ghost tiny" type="button" data-operator-request-status="${requestId}" data-status="CANCELLED">${escapeHtml(t("operator.request.action.cancelled"))}</button>
              `}
            </div>
          </div>
        `;
      }).join("");
    }
