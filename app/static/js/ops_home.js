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


    function renderAlbumSearchResults(items) {
      const root = $("albumSearchResults");
      root.innerHTML = "";
      $("albumSearchCount").textContent = countWithUnit(items.length);

      if (!items.length) {
        root.innerHTML = `<div class='muted'>${escapeHtml(t("media.manage.search.results_empty"))}</div>`;
        return;
      }

      for (const row of items) {
        const box = document.createElement("div");
        box.className = "result-item album-result";
        box.setAttribute("data-owned-id", String(row.id));
        if (Number(row.id) === Number(shelfSelectedId)) {
          box.classList.add("pick");
        }
        const title = resolveOwnedAlbumName(row);
        const tracks = Array.isArray(row.track_list) ? row.track_list.length : 0;
        const coverUrl = resolveOwnedItemCoverUrl(row);
        const coverHtml = coverUrl
          ? `<img src="${escapeHtml(coverUrl)}" alt="${escapeHtml(title)}" />`
          : escapeHtml(t("common.no_cover"));
        const metaBits = [
          `format: ${mediaDisplayLabel(row.format_name || row.category || "-")}`,
          `order_key: ${row.order_key || "-"}`,
          `slot: ${row.slot_code || "-"}`,
          `label/cat#: ${row.label_name || "-"}/${row.catalog_no || "-"}`,
          t("media.manage.search.meta.track_count", { count: formatCount(tracks) })
        ];
        box.innerHTML = `
          <div class="album-result-cover">${coverHtml}</div>
          <div class="album-result-main">
            <strong>${escapeHtml(title)}</strong>
            <div class="result-meta">
              <span class="tag">${escapeHtml(mediaDisplayLabel(row.category || "-"))}</span>
              <span>${escapeHtml(metaBits.join(" | "))}</span>
            </div>
            <div class="mini">owned_item_id: ${row.id} / label_id: ${escapeHtml(row.label_id || "-")}</div>
          </div>
        `;
        root.appendChild(box);
      }
    }

    function renderShelfTrack() {
      const root = $("shelfTrack");
      root.innerHTML = "";

      if (!shelfItems.length) {
        root.innerHTML = `<div class='shelf-empty'>${escapeHtml(t("media.manage.shelf.state.empty_albums"))}</div>`;
        $("shelfCenterText").textContent = t("media.manage.shelf.state.select_prompt");
        return;
      }

      const selectedIdx = shelfItems.findIndex((row) => Number(row.id) === Number(shelfSelectedId));
      for (let i = 0; i < shelfItems.length; i += 1) {
        const row = shelfItems[i];
        const distance = selectedIdx >= 0 ? i - selectedIdx : 0;
        const tilt = Math.max(-8, Math.min(8, distance * 1.7));
        const raise = Math.min(16, Math.abs(distance) * 2);
        const title = resolveOwnedAlbumName(row);

        const card = document.createElement("button");
        card.type = "button";
        card.className = "shelf-item";
        card.style.setProperty("--tilt", `${tilt}deg`);
        card.style.setProperty("--raise", `${raise}px`);
        card.style.zIndex = String(10 + i);
        if (row.cover_image_url) {
          const safeCoverUrl = String(row.cover_image_url)
            .replaceAll("\\", "\\\\")
            .replaceAll("'", "%27")
            .replaceAll("\"", "%22");
          card.style.backgroundImage =
            `linear-gradient(165deg, rgba(0,0,0,0.08), rgba(0,0,0,0.62)), url('${safeCoverUrl}')`;
        }
        if (Number(row.id) === Number(shelfSelectedId)) {
          card.classList.add("selected");
          card.style.zIndex = "70";
        }
        card.innerHTML = `
          <span class="fmt">${escapeHtml(mediaDisplayLabel(row.format_name || row.category || "-"))}</span>
          <p class="cap">${escapeHtml(title)}</p>
        `;
        card.addEventListener("click", () => {
          openShelfWindow(Number(row.id));
        });
        root.appendChild(card);
      }

      const centerItem = shelfItems.find((row) => Number(row.id) === Number(shelfSelectedId)) || shelfItems[0];
      $("shelfCenterText").textContent = t("media.manage.shelf.center.selected", {
        title: resolveOwnedAlbumName(centerItem),
        id: centerItem.id,
        order_key: centerItem.order_key || "-",
      });
    }

    function renderShelfDetail() {
      const root = $("shelfDetail");
      const row = shelfItems.find((v) => Number(v.id) === Number(shelfSelectedId));
      if (!row) {
        root.innerHTML = `
          <div class="shelf-cover">${escapeHtml(t("media.manage.shelf.detail.state.none"))}</div>
          <div class="shelf-meta muted">${escapeHtml(t("media.manage.shelf.detail.state.prompt"))}</div>
        `;
        return;
      }

      const title = resolveOwnedAlbumName(row);
      const coverUrl = resolveOwnedItemCoverUrl(row);
      const cover = coverUrl
        ? `<img src="${escapeHtml(coverUrl)}" alt="${escapeHtml(title)}" />`
        : escapeHtml(t("common.no_cover"));
      const tracks = Array.isArray(row.track_list) ? row.track_list.length : 0;
      const cond = row.format_name ? `${row.cover_condition ?? "-"} / ${row.disc_condition ?? "-"}` : "-";
      const source = row.source_code && row.source_external_id
        ? `${row.source_code}#${row.source_external_id}`
        : "-";
      const discogsLink = discogsReleaseLinkHtml(row.source_code, row.source_external_id, t("media.manage.master.fetch.candidate.link.discogs"));

      root.innerHTML = `
        <div class="shelf-cover">${cover}</div>
        <div class="shelf-meta">
          <strong>${escapeHtml(title)}</strong>
          <div>owned_item_id: ${row.id} / label_id: ${escapeHtml(row.label_id || "-")}</div>
          <div>${escapeHtml(t("media.manage.shelf.detail.meta.format_status", {
            format: mediaDisplayLabel(row.format_name || row.category || "-"),
            status: row.status || "-",
          }))}</div>
          <div>${escapeHtml(t("media.manage.shelf.detail.meta.order", {
            order_key: row.order_key || "-",
            display_rank: row.display_rank ?? "-",
          }))}</div>
          <div>${escapeHtml(t("media.manage.shelf.detail.meta.slot", {
            slot: row.slot_code || "-",
            source,
          }))}</div>
          ${discogsLink ? `<div>${discogsLink}</div>` : ""}
          <div>${escapeHtml(t("media.manage.shelf.detail.meta.label_catalog", {
            label: row.label_name || "-",
            catalog: row.catalog_no || "-",
          }))}</div>
          <div>${escapeHtml(t("media.manage.shelf.detail.meta.condition_tracks", {
            condition: cond,
            track_count: formatCount(tracks),
          }))}</div>
          <div>${escapeHtml(t("media.manage.shelf.detail.meta.purchase_source", { purchase_source: row.purchase_source || "-" }))}</div>
          <div class="u-pre-wrap">${escapeHtml(t("media.manage.shelf.detail.meta.memo", { memo: row.memory_note || "-" }))}</div>
        </div>
      `;
    }

    function relatedVersionItemHtml(row) {
      const title = resolveOwnedAlbumName(row);
      const coverUrl = resolveOwnedItemCoverUrl(row);
      const cover = coverUrl
        ? `<img src="${escapeHtml(coverUrl)}" alt="${escapeHtml(title)}" />`
        : escapeHtml(t("common.no_cover"));
      const discogsLink = discogsReleaseLinkHtml(row.source_code, row.source_external_id, "Discogs");
      return `
        <div class="result-item album-result ${Number(row.id) === Number(shelfSelectedId) ? "pick" : ""}" data-owned-id="${row.id}">
          <div class="album-result-cover">${cover}</div>
          <div class="album-result-main">
            <strong>${escapeHtml(title)}</strong>
            <div class="result-meta">
              <span class="tag">${escapeHtml(mediaDisplayLabel(row.format_name || row.category || "-"))}</span>
              <span>status: ${escapeHtml(row.status || "-")}</span>
              <span>order: ${escapeHtml(row.order_key || "-")}</span>
              <span>label/cat#: ${escapeHtml(row.label_name || "-")} / ${escapeHtml(row.catalog_no || "-")}</span>
              ${discogsLink ? `<span>${discogsLink}</span>` : ""}
            </div>
            <div class="mini">owned_item_id: ${row.id}</div>
          </div>
        </div>
      `;
    }

    function renderShelfRelatedVersions() {
      const root = $("shelfRelatedList");
      if (!shelfRelatedInfo) {
        root.innerHTML = `<div class='muted'>${escapeHtml(t("media.manage.related_versions.empty"))}</div>`;
        return;
      }

      const items = Array.isArray(shelfRelatedInfo.items) ? shelfRelatedInfo.items : [];
      const title = shelfRelatedInfo.title ? escapeHtml(shelfRelatedInfo.title) : "-";
      const artist = shelfRelatedInfo.artist_or_brand ? escapeHtml(shelfRelatedInfo.artist_or_brand) : "-";
      const source = shelfRelatedInfo.source ? `${shelfRelatedInfo.source}#${shelfRelatedInfo.master_external_id || "-"}` : "-";
      const relationText = {
        ALBUM_MASTER_BIND: t("media.manage.related_versions.relation.album_master_bind"),
        SOURCE_MASTER: t("media.manage.related_versions.relation.source_master"),
        NONE: t("media.manage.related_versions.relation.none")
      }[shelfRelatedInfo.relation_type || "NONE"] || t("media.manage.related_versions.relation.none");

      const head = `
        <div class="mini">
          ${escapeHtml(t("media.manage.related_versions.summary", {
            relation: relationText,
            source,
            title,
            artist,
            sort_artist: "",
            music_count: countWithUnit(items.length),
            collectible_count: countWithUnit(0),
          }))}
        </div>
      `;
      const body = items.length
        ? items.map(relatedVersionItemHtml).join("")
        : `<div class='muted'>${escapeHtml(t("media.manage.related_versions.state.empty_versions"))}</div>`;
      root.innerHTML = `${head}${body}`;
    }

    function syncShelfNavButtons() {
      $("shelfPrevBtn").disabled = !shelfPrevId;
      $("shelfNextBtn").disabled = !shelfNextId;
      $("shelfMoveLeftBtn").disabled = !shelfPrevId || !shelfSelectedId;
      $("shelfMoveRightBtn").disabled = !shelfNextId || !shelfSelectedId;
    }

    async function loadShelfRelatedVersions(ownedItemId) {
      if (!ownedItemId) {
        shelfRelatedInfo = null;
        renderShelfRelatedVersions();
        setStatus("shelfRelatedStatus", "ok", "");
        return;
      }

      try {
        setStatus("shelfRelatedStatus", "ok", t("media.manage.shelf.related.status.loading"));
        const res = await fetch(`/owned-items/${ownedItemId}/related-versions`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.shelf.related.status.load_failed"));
        shelfRelatedInfo = data;
        renderShelfRelatedVersions();
        const relatedCount = Array.isArray(data.items) ? data.items.length : 0;
        setStatus("shelfRelatedStatus", "ok", t("media.manage.shelf.related.status.loaded", { count: countWithUnit(relatedCount) }));
      } catch (err) {
        shelfRelatedInfo = null;
        renderShelfRelatedVersions();
        setStatus("shelfRelatedStatus", "err", err.message);
      }
    }

    async function openShelfWindow(ownedItemId) {
      if (!ownedItemId) return;
      try {
        setStatus("shelfStatus", "ok", t("media.manage.shelf.status.loading_item", { owned_item_id: ownedItemId }));
        const res = await fetch(`/owned-items/${ownedItemId}/shelf-window?window=6`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.shelf.status.load_failed"));

        shelfItems = data.items || [];
        shelfSelectedId = Number(data.center_owned_item_id || ownedItemId);
        shelfPrevId = data.previous_owned_item_id ? Number(data.previous_owned_item_id) : null;
        shelfNextId = data.next_owned_item_id ? Number(data.next_owned_item_id) : null;

        renderAlbumSearchResults(albumSearchResults);
        renderShelfTrack();
        renderShelfDetail();
        syncShelfNavButtons();
        await loadShelfRelatedVersions(shelfSelectedId);
        setStatus("shelfStatus", "ok", t("media.manage.shelf.status.load_done", { count: countWithUnit(shelfItems.length) }));
      } catch (err) {
        shelfItems = [];
        shelfSelectedId = null;
        shelfPrevId = null;
        shelfNextId = null;
        shelfRelatedInfo = null;
        renderShelfTrack();
        renderShelfDetail();
        renderShelfRelatedVersions();
        syncShelfNavButtons();
        setStatus("shelfRelatedStatus", "ok", "");
        setStatus("shelfStatus", "err", err.message);
      }
    }

    async function moveShelf(direction) {
      if (direction < 0 && shelfPrevId) {
        await openShelfWindow(shelfPrevId);
        return;
      }
      if (direction > 0 && shelfNextId) {
        await openShelfWindow(shelfNextId);
        return;
      }
      setStatus("shelfStatus", "err", t("media.manage.shelf.status.no_adjacent_album"));
    }

    async function moveShelfPosition(direction) {
      if (!shelfSelectedId) {
        setStatus("shelfStatus", "err", t("media.manage.shelf.status.move_required"));
        return;
      }
      const targetOwnedItemId = direction < 0 ? shelfPrevId : shelfNextId;
      if (!targetOwnedItemId) {
        setStatus("shelfStatus", "err", t("media.manage.shelf.status.move_missing_target"));
        return;
      }

      const position = direction < 0 ? "BEFORE" : "AFTER";
      try {
        setStatus(
          "shelfStatus",
          "ok",
          t("media.manage.shelf.status.moving", {
            source: shelfSelectedId,
            target: targetOwnedItemId,
            position,
          })
        );
        const res = await fetch(`/owned-items/${shelfSelectedId}/order`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target_owned_item_id: targetOwnedItemId,
            position
          })
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.shelf.status.move_failed"));
        setStatus(
          "shelfStatus",
          "ok",
          t("media.manage.shelf.status.moved", {
            owned_item_id: data.owned_item_id,
            order_key: data.order_key,
          })
        );
        await openShelfWindow(shelfSelectedId);
        await loadOwnedItems();
      } catch (err) {
        setStatus("shelfStatus", "err", err.message);
      }
    }

    async function searchOwnedAlbums() {
      const q = $("albumSearchQuery").value.trim();
      const limit = Math.max(1, Math.min(500, Number($("albumSearchLimit").value || 120)));
      const params = new URLSearchParams({
        status: "IN_COLLECTION",
        limit: String(limit)
      });
      if (q) params.set("q", q);

      try {
        setStatus("albumSearchStatus", "ok", t("media.manage.search.status.loading"));
        const res = await fetch(`/owned-items?${params.toString()}`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.search.status.load_failed"));

        albumSearchResults = (data || []).filter((row) => MUSIC_CATEGORIES.has(row.category));
        renderAlbumSearchResults(albumSearchResults);
        setStatus("albumSearchStatus", "ok", t("media.manage.search.status.loaded", { count: countWithUnit(albumSearchResults.length) }));

        if (albumSearchResults.length) {
          await openShelfWindow(Number(albumSearchResults[0].id));
        } else {
          shelfItems = [];
          shelfSelectedId = null;
          shelfPrevId = null;
          shelfNextId = null;
          shelfRelatedInfo = null;
          renderShelfTrack();
          renderShelfDetail();
          renderShelfRelatedVersions();
          syncShelfNavButtons();
          setStatus("shelfRelatedStatus", "ok", "");
        }
      } catch (err) {
        albumSearchResults = [];
        renderAlbumSearchResults(albumSearchResults);
        shelfRelatedInfo = null;
        renderShelfRelatedVersions();
        setStatus("shelfRelatedStatus", "ok", "");
        setStatus("albumSearchStatus", "err", err.message);
      }
    }


    function renderHomeLocationInfo(row) {
      const openBtn = $("homeOpenDashboardSlotBtn");
      const restoreBtn = $("homeRestorePreviousSlotBtn");
      if (!row) {
        $("homeLocationInfo").textContent = t("media.manage.location.empty");
        if (openBtn) openBtn.disabled = !homeSelectedItemId;
        if (openBtn) {
          const openLabel = t("media.manage.location.action.open_dashboard");
          openBtn.textContent = openLabel;
          openBtn.title = openLabel;
          openBtn.setAttribute("aria-label", openLabel);
        }
        if (restoreBtn) restoreBtn.disabled = true;
        return;
      }

      const slotId = Number(row.storage_slot_id || 0);
      const slotRow = slotId > 0
        ? (
          homeDashboardBySlot.find((item) => Number(item?.id || 0) === slotId)
          || storageSlotCache.find((item) => Number(item.id) === slotId)
          || null
        )
        : null;
      const slotLabel = slotRow
        ? storageSlotDisplayLabel(slotRow)
        : (row.slot_code || t("common.unslotted"));
      const bits = [
        t("media.manage.location.meta.position", { slot: slotLabel }),
        slotId > 0 ? t("media.manage.location.meta.slot_id", { value: row.storage_slot_id ?? "-" }) : null,
        t("media.manage.location.meta.order_key", { value: row.order_key || "-" }),
        t("media.manage.location.meta.display_rank", { value: row.display_rank ?? "-" }),
        slotId > 0 ? t("media.manage.location.summary.current") : t("media.manage.location.summary.unslotted")
      ].filter(Boolean);
      $("homeLocationInfo").textContent = bits.join(" | ");
      if (openBtn) {
        openBtn.disabled = !homeSelectedItemId;
        const openLabel = slotId > 0
          ? t("media.manage.location.action.open_dashboard_current")
          : t("media.manage.location.action.open_dashboard");
        openBtn.textContent = openLabel;
        openBtn.title = openLabel;
        openBtn.setAttribute("aria-label", openLabel);
      }
      if (restoreBtn) {
        const hasPrevious = Boolean(String(row.previous_slot_code || row.previous_slot_display_name || "").trim());
        restoreBtn.disabled = !homeSelectedItemId || !hasPrevious;
      }
    }

    async function restoreHomePreviousLocation() {
      const ownedItemId = Number(homeSelectedItemId || 0);
      if (ownedItemId <= 0) {
        setStatus("homeLocationSlotStatus", "err", t("media.manage.location.status.select_item_first"));
        return;
      }
      try {
        setStatus("homeLocationSlotStatus", "ok", t("media.manage.location.status.restoring"));
        const res = await fetch(`/owned-items/${ownedItemId}/restore-previous-slot`, { method: "POST" });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.location.status.restore_failed"));
        setStatus("homeLocationSlotStatus", "ok", t("media.manage.location.status.restore_done"));
        await refreshHomeManageContext(ownedItemId, {
          keepMasterContext: Boolean(homeSelectedMasterId),
          masterId: homeSelectedMasterId,
          reloadMaster: Boolean(homeSelectedMasterId),
        });
        loadHomeDashboard({ silent: true }).catch(() => {});
      } catch (err) {
        setStatus("homeLocationSlotStatus", "err", err.message);
      }
    }

    function homeLocationSlotItemHtml(row, index) {
      const title = resolveOwnedAlbumName(row);
      const coverUrl = normalizeRenderableCoverUrl(row.cover_image_url);
      const signatureBadge = signatureCoverBadgeHtml(row?.signature_type, "media-search-cover-signature-badge");
      const cover = coverUrl
        ? `${signatureBadge}<img src="${escapeHtml(coverUrl)}" alt="${escapeHtml(title)}" />`
        : `${signatureBadge}${escapeHtml(t("common.no_cover"))}`;
      const barcodeText = String(row.barcode || "").trim();
      const labelCatText = `${row.label_name || "-"} / ${row.catalog_no || "-"}${barcodeText ? ` (${barcodeText})` : ""}`;
      const isCurrent = Number(row.id) === Number(homeSelectedItemId || 0);
      const actions = isCurrent
        ? `<span class="tag">${escapeHtml(t("media.manage.location.item.current"))}</span>`
        : `
            <div class="home-location-slot-actions">
              <button class="btn ghost tiny home-location-open-btn" type="button" data-owned-id="${row.id}">${escapeHtml(t("common.action.open"))}</button>
              <button class="btn ghost tiny home-location-before-btn" type="button" data-target-id="${row.id}">${escapeHtml(t("media.manage.location.action.before"))}</button>
              <button class="btn ghost tiny home-location-after-btn" type="button" data-target-id="${row.id}">${escapeHtml(t("media.manage.location.action.after"))}</button>
            </div>
          `;
      return `
        <div
          class="result-item album-result home-location-slot-item ${isCurrent ? "pick" : ""}"
          data-slot-owned-id="${row.id}"
        >
          <div class="album-result-cover">${cover}</div>
          <div class="album-result-main">
            <div class="home-location-slot-head">
              <strong>${escapeHtml(`${index + 1}. ${title}`)}</strong>
              ${actions}
            </div>
            <div class="result-meta">
              <span class="tag">${escapeHtml(mediaDisplayLabel(row.format_name || row.category || "-"))}</span>
              <span>status: ${escapeHtml(row.status || "-")}</span>
              <span>order: ${escapeHtml(row.order_key || "-")}</span>
              <span>display: ${escapeHtml(row.display_rank ?? "-")}</span>
              <span>label/cat#: ${escapeHtml(labelCatText)}</span>
            </div>
            <div class="mini">owned_item_id: ${row.id} | label_id: ${escapeHtml(row.label_id || "-")}</div>
          </div>
        </div>
      `;
    }

    function renderHomeLocationSlotList() {
      const root = $("homeLocationSlotList");
      if (!root) return;
      root.innerHTML = "";
    }

    async function loadHomeLocationSlotItems(storageSlotId, opts = {}) {
      const slotId = Number(storageSlotId || 0);
      const seed = opts.seed || null;
      const silent = Boolean(opts.silent);
      homeLocationSlotId = slotId > 0 ? slotId : null;
      if (slotId <= 0) {
        homeLocationSlotItems = [];
        homeLocationSlotLoading = false;
        renderHomeLocationInfo(seed);
        renderHomeLocationSlotList();
        setStatus("homeLocationSlotStatus", "ok", "");
        return;
      }

      try {
        homeLocationSlotLoading = true;
        renderHomeLocationInfo(seed);
        renderHomeLocationSlotList();
        if (!silent) setStatus("homeLocationSlotStatus", "ok", t("media.manage.location.status.slot_items_loading"));
        const res = await fetch(`/storage-slots/${slotId}/owned-items?limit=300`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.location.status.slot_items_failed"));
        if (Number(homeLocationSlotId || 0) !== slotId) return;
        homeLocationSlotItems = Array.isArray(data) ? data : [];
        renderHomeLocationInfo(seed || homeLocationSlotItems.find((row) => Number(row.id) === Number(homeSelectedItemId || 0)) || null);
        renderHomeLocationSlotList();
        syncHomeMasterInlineEditor();
        if (!silent) setStatus("homeLocationSlotStatus", "ok", t("media.manage.location.status.slot_items_done", { count: countWithUnit(homeLocationSlotItems.length) }));
      } catch (err) {
        homeLocationSlotItems = [];
        renderHomeLocationInfo(seed);
        renderHomeLocationSlotList();
        syncHomeMasterInlineEditor();
        setStatus("homeLocationSlotStatus", "err", err.message);
      } finally {
        homeLocationSlotLoading = false;
        renderHomeLocationInfo(seed || homeLocationSlotItems.find((row) => Number(row.id) === Number(homeSelectedItemId || 0)) || null);
        renderHomeLocationSlotList();
        syncHomeMasterInlineEditor();
      }
    }

    async function moveHomeLocationCurrentItem(targetOwnedItemId, position) {
      const ownedItemId = Number(homeSelectedItemId || $("editOwnedId").value || 0);
      const targetId = Number(targetOwnedItemId || 0);
      if (!ownedItemId || !targetId) {
        setStatus("homeLocationSlotStatus", "err", t("dashboard.order.need_item_and_target"));
        return;
      }
      if (ownedItemId === targetId) {
        setStatus("homeLocationSlotStatus", "err", t("media.manage.location.reorder.same_item"));
        return;
      }
      try {
        setStatus("homeLocationSlotStatus", "ok", t("dashboard.order.progress", { source: ownedItemId, target: targetId, position }));
        const res = await fetch(`/owned-items/${ownedItemId}/order`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target_owned_item_id: targetId,
            position,
          })
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("dashboard.order.failed"));
        setStatus("homeLocationSlotStatus", "ok", t("media.manage.location.reorder.done", { order_key: data.order_key }));
        await refreshHomeManageContext(ownedItemId, {
          keepMasterContext: Boolean(homeSelectedMasterId),
          masterId: homeSelectedMasterId,
          reloadMaster: Boolean(homeSelectedMasterId),
        });
        refreshHomeDashboardInBackground();
        refreshHomeSearchInBackground();
      } catch (err) {
        setStatus("homeLocationSlotStatus", "err", err.message);
      }
    }
