
    function renderMasterCandidates(items) {
      const root = $("masterCandidates");
      root.innerHTML = "";
      $("masterCandidateCount").textContent = countWithUnit(items.length);

      if (!items.length) {
        root.innerHTML = `<div class='muted'>${escapeHtml(t("media.register.master.state.candidates_empty"))}</div>`;
        return;
      }

      for (const c of items) {
        const box = document.createElement("div");
        box.className = "result-item";
        const labelName = String(c.label_name || "").trim();
        const catalogNo = String(c.catalog_no || "").trim();
        const barcode = String(c.barcode || "").trim();
        const hasMeta = Boolean(labelName || catalogNo || barcode);
        const labelCatText = `${labelName || "-"} / ${catalogNo || "-"}${barcode ? ` (${barcode})` : ""}`;
        box.innerHTML = `
          <strong>${escapeHtml(c.artist_or_brand || "-")} - ${escapeHtml(c.title || "(no title)")}</strong>
          <div class="result-meta">
            <span class="tag">${escapeHtml(c.source)}</span>
            <span class="tag alt">master ${escapeHtml(c.master_external_id)}</span>
            <span>year: ${c.release_year ?? "-"}</span>
            <span>conf: ${Number(c.confidence || 0).toFixed(3)}</span>
            ${hasMeta ? `<span>label/cat#: ${escapeHtml(labelCatText)}</span>` : ""}
          </div>
        `;
        const btn = document.createElement("button");
        btn.className = "btn ghost";
        btn.textContent = t("media.register.master.action.select_candidate");
        btn.onclick = () => {
          selectedAlbumMaster = c;
          $("masterSelected").textContent = t("media.register.master.state.selected", {
            source: c.source || "-",
            artist: c.artist_or_brand || "-",
            title: c.title || "(no title)",
            master: c.master_external_id || "-",
          });
          if (!$("masterOwnedQ").value.trim()) {
            $("masterOwnedQ").value = c.title || "";
          }
          setStatus("bindMasterStatus", "ok", "");
          setStatus("masterImportStatus", "ok", "");
          masterVariantItems = [];
          resetMasterVariantPager({ clearInputs: true });
          $("masterVariantBody").innerHTML = `<tr><td colspan='11' class='muted'>${escapeHtml(t("media.register.master.state.variants_prompt"))}</td></tr>`;
        };
        box.appendChild(btn);
        root.appendChild(box);
      }
    }

    async function searchAlbumMasters() {
      const sourceRef = $("masterSourceRef").value.trim();
      const query = sourceRef || $("masterQuery").value.trim();
      const loadingStatusText = t("media.register.master.status.searching");
      if (!query) {
        setStatus("masterSearchStatus", "err", t("media.register.master.status.query_required"));
        return;
      }

      const payload = {
        source: $("masterSource").value,
        query,
        artist_or_brand: $("queryArtist") ? $("queryArtist").value.trim() || null : null,
        title: $("queryTitle") ? $("queryTitle").value.trim() || null : null,
        limit: Math.max(1, Math.min(50, Number($("masterLimit").value || 10)))
      };

      try {
        setStatus("masterSearchStatus", "ok", loadingStatusText);
        const res = await fetchWithRetry("/album-masters/search", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        }, {
          retries: 2,
          retryDelayMs: 250,
          onRetry: (attempt, total) => setStatus("masterSearchStatus", "ok", retryingStatusText(loadingStatusText, attempt, total)),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.register.master.status.search_failed"));

        const items = data.candidates || [];
        renderMasterCandidates(items);
        if (items.length) {
          selectedAlbumMaster = items[0];
          $("masterSelected").textContent = t("media.register.master.state.selected", {
            source: items[0].source || "-",
            artist: items[0].artist_or_brand || "-",
            title: items[0].title || "(no title)",
            master: items[0].master_external_id || "-",
          });
        } else {
          selectedAlbumMaster = null;
          $("masterSelected").textContent = t("media.register.master.state.none_selected");
        }
        masterVariantItems = [];
        resetMasterVariantPager({ clearInputs: true });
        $("masterVariantBody").innerHTML = `<tr><td colspan='11' class='muted'>${escapeHtml(t("media.register.master.state.variants_prompt"))}</td></tr>`;
        setStatus("masterImportStatus", "ok", "");
        setStatus("masterSearchStatus", "ok", t("media.register.master.status.search_complete", { count: countWithUnit(items.length) }));
      } catch (err) {
        renderMasterCandidates([]);
        selectedAlbumMaster = null;
        $("masterSelected").textContent = t("media.register.master.state.none_selected");
        masterVariantItems = [];
        resetMasterVariantPager({ clearInputs: true });
        $("masterVariantBody").innerHTML = `<tr><td colspan='11' class='muted'>${escapeHtml(t("media.register.master.state.variants_prompt"))}</td></tr>`;
        setStatus("masterImportStatus", "ok", "");
        setStatus("masterSearchStatus", "err", err.message);
      }
    }

    function masterVariantRowHtml(row) {
      const trackCount = Array.isArray(row.track_list) ? row.track_list.length : 0;
      const ownedCount = Number(row.owned_count || 0);
      const ownedText = ownedCount > 0 ? t("media.register.master.variant.owned_count", { count: formatCount(ownedCount) }) : "-";
      const checked = ownedCount > 0 ? "" : "checked";
      const sourceCode = normalizeSourceCode(row.source || selectedAlbumMaster?.source || "");
      const discogsLink = discogsReleaseLinkHtml(sourceCode, row.external_id, t("media.register.master.variant.link.discogs"));
      const galleryKey = registerImageGallery(`masterVariant:${sourceCode}:${row.external_id || "-"}`, row, {
        title: `${row.artist_or_brand || "Unknown"} - ${row.title || "(no title)"}`,
        subtitle: `${sourceCode || "-"}#${row.external_id || "-"}`,
      });
      const galleryCount = galleryKey ? Number(imageGalleryRegistry.get(galleryKey)?.items?.length || 0) : 0;
      const releasedDate = String(row.released_date || row.release_year || "").trim() || "-";
      const pressingCountry = String(row.pressing_country || row.country || "").trim() || "-";
      const formatItemsText = summarizeFormatItems(row.format_items, 2);
      const coverUrl = normalizeRenderableCoverUrl(row.cover_image_url);
      const cover = coverUrl
        ? `<a href="${escapeHtml(coverUrl)}" target="_blank" rel="noreferrer" title="${escapeHtml(t("media.register.master.variant.cover_original"))}"><div class="table-cover-thumb"><img src="${escapeHtml(coverUrl)}" alt="${escapeHtml(row.title || "cover")}" /></div></a>`
        : `<div class="table-cover-thumb">-</div>`;
      return `
        <tr>
          <td><input type="checkbox" class="masterVariantChk" value="${escapeHtml(row.external_id)}" ${checked} /></td>
          <td>
            <div>${escapeHtml(row.external_id)}</div>
            <div class="mini">${discogsLink || "-"}${galleryKey ? ` | ${imageGalleryButtonHtml(galleryKey, t("common.count.images", { count: formatCount(galleryCount) }))}` : ""}</div>
          </td>
          <td>
            <div>${escapeHtml(row.title || "-")}</div>
            <div class="mini">${escapeHtml(t("common.meta.release_date", { value: releasedDate }))} | ${escapeHtml(t("media.register.master.variant.meta.pressing", { value: pressingCountry }))}</div>
            <div class="mini">${escapeHtml(t("media.register.master.variant.meta.format_items", { value: formatItemsText }))}</div>
          </td>
          <td>${escapeHtml(mediaDisplayLabel(row.format_name || "-"))}</td>
          <td>${row.release_year ?? "-"}</td>
          <td>${escapeHtml(row.label_name || "-")}</td>
          <td>${escapeHtml(row.catalog_no || "-")}</td>
          <td>${escapeHtml(row.barcode || "-")}</td>
          <td>${cover}</td>
          <td>${escapeHtml(ownedText)}</td>
          <td>${trackCount}</td>
        </tr>
      `;
    }

    function selectedMasterVariantExternalIds() {
      return Array.from(document.querySelectorAll("#masterVariantBody .masterVariantChk:checked"))
        .map((el) => String(el.value || "").trim())
        .filter((v) => v);
    }

    function markMasterVariantSelection(mode) {
      const boxes = Array.from(document.querySelectorAll("#masterVariantBody .masterVariantChk"));
      if (!boxes.length) return;
      const ownedMap = new Map(
        (masterVariantItems || []).map((row) => [String(row.external_id || ""), Number(row.owned_count || 0)])
      );
      for (const box of boxes) {
        const ext = String(box.value || "");
        const ownedCount = Number(ownedMap.get(ext) || 0);
        if (mode === "ALL") box.checked = true;
        if (mode === "MISSING") box.checked = ownedCount <= 0;
        if (mode === "NONE") box.checked = false;
      }
    }

    function renderMasterVariantPager() {
      const prevBtn = $("masterVariantPrevBtn");
      const nextBtn = $("masterVariantNextBtn");
      const pageInfo = $("masterVariantPageInfo");
      if (!prevBtn || !nextBtn || !pageInfo) return;
      prevBtn.disabled = masterVariantPage <= 1;
      nextBtn.disabled = !masterVariantHasNext;

      let totalText = "";
      if (Number.isFinite(masterVariantTotalCount) && Number(masterVariantTotalCount) >= 0) {
        totalText = ` / ${t("media.register.master.variant.total_suffix", { count: formatCount(Number(masterVariantTotalCount)) })}`;
      } else if (masterVariantTruncated) {
        totalText = ` / ${t("media.register.master.variant.total_truncated")}`;
      }
      pageInfo.textContent = `page ${masterVariantPage}${totalText}`;
    }

    function resetMasterVariantPager(opts = {}) {
      const clearInputs = Boolean(opts.clearInputs);
      masterVariantPage = 1;
      masterVariantHasNext = false;
      masterVariantTotalCount = null;
      masterVariantTruncated = false;
      if (clearInputs) {
        $("masterVariantCatalogNo").value = "";
        $("masterVariantBarcode").value = "";
      }
      renderMasterVariantPager();
    }

    async function importMasterVariants() {
      if (!selectedAlbumMaster) {
        setStatus("masterImportStatus", "err", t("media.register.master.import.status.no_master"));
        return;
      }
      const source = String(selectedAlbumMaster.source || "").toUpperCase();
      if (!["DISCOGS", "MANIADB"].includes(source)) {
        setStatus("masterImportStatus", "err", t("media.register.master.import.status.unsupported_source"));
        return;
      }
      const selectedIds = selectedMasterVariantExternalIds();
      if (!selectedIds.length) {
        setStatus("masterImportStatus", "err", t("media.register.master.import.status.no_selection"));
        return;
      }
      try {
        setStatus("masterImportStatus", "ok", t("media.register.master.import.status.saving"));
        const res = await fetch("/album-masters/import-variants", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            source,
            master_external_id: selectedAlbumMaster.master_external_id,
            title: selectedAlbumMaster.title || null,
            artist_or_brand: selectedAlbumMaster.artist_or_brand || null,
            release_year: selectedAlbumMaster.release_year || null,
            raw: selectedAlbumMaster.raw || {},
            selected_variant_external_ids: selectedIds,
            skip_if_owned: true
          })
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.register.master.import.status.failed"));
        const notices = Array.isArray(data.notices) ? data.notices : [];
        setStatus(
          "masterImportStatus",
          "ok",
          t("media.register.master.import.status.done", {
            created: formatCount(Number(data.created_count || 0)),
            skipped: formatCount(Number(data.skipped_count || 0)),
            album_master_id: data.album_master_id,
            notices: notices.length ? `\n${notices.map((v) => `- ${v}`).join("\n")}` : "",
          })
        );
        await loadMasterVariants();
        await loadAlbumMasterGroups();
        await homeSearchOwnedItems({ resetPage: true });
      } catch (err) {
        setStatus("masterImportStatus", "err", err.message);
      }
    }

    async function loadMasterVariants(opts = {}) {
      const resetPage = Boolean(opts.resetPage);
      if (resetPage) masterVariantPage = 1;
      masterVariantPageSize = Math.max(1, Math.min(100, Number(masterVariantPageSize || 50)));
      if (!selectedAlbumMaster) {
        setStatus("masterVariantStatus", "err", t("media.register.master.variant.status.no_master"));
        masterVariantHasNext = false;
        masterVariantTotalCount = null;
        masterVariantTruncated = false;
        renderMasterVariantPager();
        return;
      }

      const catalogNo = $("masterVariantCatalogNo").value.trim();
      const barcode = $("masterVariantBarcode").value.trim();
      const params = new URLSearchParams({
        source: selectedAlbumMaster.source,
        master_external_id: selectedAlbumMaster.master_external_id,
        page: String(masterVariantPage),
        page_size: String(masterVariantPageSize)
      });
      if (catalogNo) params.set("catalog_no", catalogNo);
      if (barcode) params.set("barcode", barcode);

      try {
        setStatus("masterVariantStatus", "ok", t("media.register.master.variant.status.loading"));
        const res = await fetch(`/album-masters/variants?${params.toString()}`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.register.master.variant.status.failed"));

        const items = data.items || [];
        masterVariantItems = Array.isArray(items) ? items : [];
        const pageValue = Number(data.page);
        masterVariantPage = Number.isFinite(pageValue) && pageValue > 0 ? Math.floor(pageValue) : masterVariantPage;
        masterVariantHasNext = Boolean(data.has_next);
        const totalValue = Number(data.total_count);
        masterVariantTotalCount = Number.isFinite(totalValue) && totalValue >= 0 ? Math.floor(totalValue) : null;
        masterVariantTruncated = Boolean(data.truncated);
        $("masterVariantBody").innerHTML = items.map(masterVariantRowHtml).join("") ||
          `<tr><td colspan='11' class='muted'>${escapeHtml(t("media.register.master.variant.status.empty"))}</td></tr>`;
        renderMasterVariantPager();
        let totalText = "";
        if (masterVariantTotalCount !== null) {
          totalText = ` / ${t("media.register.master.variant.total_suffix", { count: formatCount(masterVariantTotalCount) })}`;
        } else if (masterVariantTruncated) {
          totalText = ` / ${t("media.register.master.variant.total_truncated")}`;
        }
        setStatus("masterVariantStatus", "ok", t("media.register.master.variant.status.loaded", {
          count: countWithUnit(items.length),
          page_info: t("media.register.master.variant.page_info", { page: masterVariantPage, total: totalText }),
        }));
        setStatus("masterImportStatus", "ok", "");
      } catch (err) {
        masterVariantItems = [];
        masterVariantHasNext = false;
        masterVariantTotalCount = null;
        masterVariantTruncated = false;
        $("masterVariantBody").innerHTML = `<tr><td colspan='11' class='muted'>${escapeHtml(t("media.register.master.variant.status.empty"))}</td></tr>`;
        renderMasterVariantPager();
        setStatus("masterVariantStatus", "err", err.message);
      }
    }

    function masterOwnedRowHtml(row) {
      const name = row.item_name_override || "-";
      const mt = (selectedAlbumMaster?.title || "").trim().toLowerCase();
      const nm = name.trim().toLowerCase();
      const checked = masterOwnedPrefilledIds.has(Number(row?.id || 0)) || (mt && nm && nm.includes(mt));
      return `
        <tr>
          <td><input type="checkbox" class="masterOwnedChk" value="${row.id}" ${checked ? "checked" : ""} /></td>
          <td>${row.id}</td>
          <td>${escapeHtml(mediaDisplayLabel(row.category))}</td>
          <td>${escapeHtml(name)}</td>
          <td>${escapeHtml(mediaDisplayLabel(row.format_name || "-"))}</td>
          <td>${escapeHtml(row.status)}</td>
        </tr>
      `;
    }

    async function loadMasterOwnedItems() {
      const q = $("masterOwnedQ").value.trim();
      const limit = Math.max(1, Math.min(200, Number($("masterOwnedLimit").value || 50)));

      const params = new URLSearchParams({
        status: "IN_COLLECTION",
        limit: String(limit)
      });
      if (q) params.set("q", q);

      try {
        setStatus("masterOwnedStatus", "ok", t("media.register.master.owned_items.status.loading"));
        const res = await fetch(`/owned-items?${params.toString()}`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.register.master.owned_items.status.failed"));

        masterOwnedItems = Array.isArray(data) ? data : [];
        $("masterOwnedBody").innerHTML = masterOwnedItems.map(masterOwnedRowHtml).join("") ||
          `<tr><td colspan='6' class='muted'>${escapeHtml(t("media.register.master.owned_items.state.empty"))}</td></tr>`;
        syncMasterExceptionBanner();
        setStatus("masterOwnedStatus", "ok", t("media.register.master.status.search_complete", { count: countWithUnit(masterOwnedItems.length) }));
      } catch (err) {
        masterOwnedItems = [];
        $("masterOwnedBody").innerHTML = `<tr><td colspan='6' class='muted'>${escapeHtml(t("media.register.master.owned_items.state.empty"))}</td></tr>`;
        syncMasterExceptionBanner();
        setStatus("masterOwnedStatus", "err", err.message);
      }
    }

    function selectedMasterOwnedIds() {
      return Array.from(document.querySelectorAll("#masterOwnedBody .masterOwnedChk:checked"))
        .map((el) => Number(el.value))
        .filter((v) => Number.isInteger(v) && v > 0);
    }

    function selectedMasterOwnedRows() {
      const selectedIdSet = new Set(selectedMasterOwnedIds());
      return (masterOwnedItems || []).filter((row) => selectedIdSet.has(Number(row?.id || 0)));
    }

    function promptMasterBindTargetSelection(selectedRows) {
      const rows = Array.isArray(selectedRows) ? selectedRows : [];
      const existingCounts = new Map();
      for (const row of rows) {
        const masterId = Number(row?.linked_album_master_id || 0);
        if (masterId <= 0) continue;
        existingCounts.set(masterId, Number(existingCounts.get(masterId) || 0) + 1);
      }
      if (!existingCounts.size) {
        return { mode: "SEARCHED" };
      }

      const existingOptions = Array.from(existingCounts.entries())
        .map(([albumMasterId, count]) => ({ album_master_id: Number(albumMasterId), count: Number(count) }))
        .sort((a, b) => b.count - a.count || a.album_master_id - b.album_master_id);

      const optionRows = existingOptions.map((row, index) => ({
        index: index + 1,
        mode: "EXISTING",
        album_master_id: row.album_master_id,
        label: t("media.register.master.bind.target.option.existing", {
          index: index + 1,
          album_master_id: row.album_master_id,
          count: countWithUnit(row.count),
        }),
      }));
      optionRows.push({
        index: optionRows.length + 1,
        mode: "SEARCHED",
        album_master_id: 0,
        label: t("media.register.master.bind.target.option.searched", { index: optionRows.length + 1 }),
      });

      const defaultValue = String(existingOptions[0]?.album_master_id || optionRows[0]?.index || "");
      const rawChoice = window.prompt(t("media.register.master.bind.target.prompt", {
        options: optionRows.map((row) => row.label).join("\n"),
        default_value: defaultValue,
      }), defaultValue);
      if (rawChoice == null) return null;

      const normalizedChoice = String(rawChoice || "").trim();
      if (!normalizedChoice) return null;
      const normalizedUpper = normalizedChoice.toUpperCase();
      const matchedExisting = existingOptions.find((row) => String(row.album_master_id) === normalizedChoice);
      if (matchedExisting) {
        return { mode: "EXISTING", target_album_master_id: matchedExisting.album_master_id };
      }
      const matchedOption = optionRows.find((row) => String(row.index) === normalizedChoice);
      if (matchedOption?.mode === "EXISTING") {
        return { mode: "EXISTING", target_album_master_id: Number(matchedOption.album_master_id || 0) };
      }
      if ((matchedOption && matchedOption.mode === "SEARCHED") || ["S", "SEARCH", "SEARCHED", "NEW"].includes(normalizedUpper)) {
        return { mode: "SEARCHED" };
      }
      throw new Error(t("media.register.master.bind.target.invalid"));
    }

    async function bindAlbumMaster() {
      if (!selectedAlbumMaster) {
        setStatus("bindMasterStatus", "err", t("media.register.master.bind.status.no_master"));
        return;
      }
      const ownedItemIds = selectedMasterOwnedIds();
      if (!ownedItemIds.length) {
        setStatus("bindMasterStatus", "err", t("media.register.master.bind.status.no_owned_items"));
        return;
      }
      const selectedRows = selectedMasterOwnedRows();
      const queuedMergeIds = selectedMasterMergeIds();
      let mergeTarget = null;
      if (queuedMergeIds.length) {
        const queuedBaseId = normalizeMasterMergeId(masterMergeBaseId);
        if (!queuedBaseId || !queuedMergeIds.includes(queuedBaseId)) {
          setStatus("bindMasterStatus", "err", t("media.register.master.merge.status.base_required"));
          return;
        }
        mergeTarget = { mode: "EXISTING", target_album_master_id: queuedBaseId };
      } else {
        mergeTarget = promptMasterBindTargetSelection(selectedRows);
      }
      if (!mergeTarget) {
        setStatus("bindMasterStatus", "err", t("media.register.master.bind.status.cancelled"));
        return;
      }

      const payload = {
        source: selectedAlbumMaster.source,
        master_external_id: selectedAlbumMaster.master_external_id,
        title: selectedAlbumMaster.title,
        artist_or_brand: selectedAlbumMaster.artist_or_brand || null,
        release_year: selectedAlbumMaster.release_year || null,
        raw: selectedAlbumMaster.raw || {},
        owned_item_ids: ownedItemIds,
        replace_existing: true
      };

      try {
        setStatus("bindMasterStatus", "ok", t("media.register.master.bind.status.saving"));
        const res = await fetch("/album-masters/bind", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.register.master.bind.status.failed"));
        const boundAlbumMasterId = Number(data.album_master_id || 0);
        const existingMasterIds = Array.from(new Set(
          selectedRows
            .map((row) => Number(row?.linked_album_master_id || 0))
            .filter((value) => Number.isInteger(value) && value > 0)
        ));
        const queuedMasterIds = selectedMasterMergeIds();
        const targetAlbumMasterId = mergeTarget.mode === "EXISTING"
          ? Number(mergeTarget.target_album_master_id || 0)
          : boundAlbumMasterId;
        const mergeSourceIds = new Set(existingMasterIds);
        for (const queuedMasterId of queuedMasterIds) mergeSourceIds.add(queuedMasterId);
        if (boundAlbumMasterId > 0 && boundAlbumMasterId !== targetAlbumMasterId) mergeSourceIds.add(boundAlbumMasterId);
        mergeSourceIds.delete(targetAlbumMasterId);

        let mergedCount = 0;
        const mergeFailures = [];
        for (const sourceId of Array.from(mergeSourceIds).sort((a, b) => a - b)) {
          try {
            const mergeRes = await fetch(`/album-masters/${sourceId}/merge`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ target_album_master_id: targetAlbumMasterId }),
            });
            const mergeData = await safeJson(mergeRes);
            if (!mergeRes.ok) throw new Error(mergeData.detail || t("media.register.direct.duplicate.merge_failed"));
            mergedCount += Number(mergeData?.merged === false ? 0 : 1);
          } catch (err) {
            mergeFailures.push(`\n- ${sourceId}: ${err.message}`);
          }
        }

        setStatus(
          "bindMasterStatus",
          "ok",
          t("media.register.master.bind.status.done", {
            album_master_id: targetAlbumMasterId || data.album_master_id,
            linked_count: data.linked_count,
          })
        );
        masterOwnedPrefilledIds = new Set();
        syncMasterExceptionBanner();
        await loadAlbumMasterGroups();
        if (mergeFailures.length) {
          setStatus(
            "bindMasterStatus",
            "err",
            `${t("media.register.master.bind.status.done", {
              album_master_id: targetAlbumMasterId || data.album_master_id,
              linked_count: data.linked_count,
            })}\n${t("media.register.master.bind.status.merge_partial", {
              target_album_master_id: targetAlbumMasterId || data.album_master_id,
              merged_count: formatCount(mergedCount),
              failed_count: formatCount(mergeFailures.length),
              details: mergeFailures.join(""),
            })}`
          );
          return;
        }
        if (mergedCount > 0 || (targetAlbumMasterId > 0 && targetAlbumMasterId !== boundAlbumMasterId)) {
          setStatus(
            "bindMasterStatus",
            "ok",
            `${t("media.register.master.bind.status.done", {
              album_master_id: targetAlbumMasterId || data.album_master_id,
              linked_count: data.linked_count,
            })}\n${t("media.register.master.bind.status.merge_done", {
              target_album_master_id: targetAlbumMasterId || data.album_master_id,
              merged_count: formatCount(mergedCount),
            })}`
          );
        }
      } catch (err) {
        setStatus("bindMasterStatus", "err", err.message);
      }
    }

    function normalizeMasterMergeId(value) {
      const id = Number(value || 0);
      return Number.isInteger(id) && id > 0 ? id : 0;
    }

    function selectedMasterMergeIds() {
      return (masterMergeQueueItems || [])
        .map((row) => normalizeMasterMergeId(row?.id))
        .filter((value) => value > 0)
        .sort((a, b) => a - b);
    }

    function isQueuedMasterMergeId(albumMasterId) {
      const normalizedId = normalizeMasterMergeId(albumMasterId);
      return normalizedId > 0 && masterMergeQueueItems.some((row) => normalizeMasterMergeId(row?.id) === normalizedId);
    }

    function syncMasterMergeSelectionUi() {
      const selectedIds = selectedMasterMergeIds();
      const summary = $("masterMergeSummary");
      const runBtn = $("masterMergeRunBtn");

      if (masterMergeBaseId && !selectedIds.includes(masterMergeBaseId)) {
        masterMergeBaseId = 0;
      }
      if (!masterMergeBaseId && selectedIds.length) {
        masterMergeBaseId = selectedIds[0];
      }

      const ready = selectedIds.length >= 2 && masterMergeBaseId > 0 && selectedIds.includes(masterMergeBaseId);
      if (runBtn) runBtn.disabled = !ready;
      if (!summary) return;
      summary.textContent = selectedIds.length
        ? t("media.register.master.merge.summary.selected", {
            count: countWithUnit(selectedIds.length),
            base_id: masterMergeBaseId || "-",
          })
        : t("media.register.master.merge.summary.none_selected");
    }

    function masterMergeRowHtml(row) {
      const rowId = normalizeMasterMergeId(row?.id);
      const queued = isQueuedMasterMergeId(rowId);
      return `
        <tr>
          <td><button class="btn ghost tiny" type="button" data-master-merge-add-id="${rowId}" ${queued ? "disabled" : ""}>${escapeHtml(t(queued ? "media.register.master.merge.action.added" : "media.register.master.merge.action.add"))}</button></td>
          <td>${rowId || "-"}</td>
          <td>${escapeHtml(String(row?.source_code || "-"))}</td>
          <td>${escapeHtml(String(row?.source_master_id || "-"))}</td>
          <td>${escapeHtml(String(row?.title || "-"))}</td>
          <td>${escapeHtml(String(row?.artist_or_brand || "-"))}</td>
          <td>${row?.release_year ?? "-"}</td>
          <td>${Number(row?.member_count || 0)}</td>
        </tr>
      `;
    }

    function renderMasterMergeRows(items) {
      masterMergeSearchResults = Array.isArray(items) ? items : [];
      const body = $("masterMergeBody");
      if (!body) return;
      if (!masterMergeSearchResults.length) {
        const emptyKey = masterMergeHasSearched
          ? "media.register.master.merge.state.empty"
          : "media.register.master.merge.state.prompt";
        body.innerHTML = `<tr><td colspan='8' class='muted'>${escapeHtml(t(emptyKey))}</td></tr>`;
        return;
      }
      body.innerHTML = masterMergeSearchResults.map(masterMergeRowHtml).join("");
    }

    function masterMergeQueueRowHtml(row) {
      const rowId = normalizeMasterMergeId(row?.id);
      const isBase = rowId > 0 && rowId === masterMergeBaseId;
      return `
        <tr>
          <td><input type="radio" name="masterMergeBaseId" data-master-merge-base-id="${rowId}" ${isBase ? "checked" : ""} /></td>
          <td><button class="btn ghost tiny" type="button" data-master-merge-remove-id="${rowId}">${escapeHtml(t("media.register.master.merge.table.remove"))}</button></td>
          <td>${rowId || "-"}</td>
          <td>${escapeHtml(String(row?.source_code || "-"))}</td>
          <td>${escapeHtml(String(row?.source_master_id || "-"))}</td>
          <td>${escapeHtml(String(row?.title || "-"))}</td>
          <td>${escapeHtml(String(row?.artist_or_brand || "-"))}</td>
          <td>${row?.release_year ?? "-"}</td>
          <td>${Number(row?.member_count || 0)}</td>
        </tr>
      `;
    }

    function renderMasterMergeQueueRows() {
      const body = $("masterMergeQueueBody");
      if (!body) return;
      if (!masterMergeQueueItems.length) {
        body.innerHTML = `<tr><td colspan='9' class='muted'>${escapeHtml(t("media.register.master.merge.queue.state.empty"))}</td></tr>`;
        syncMasterMergeSelectionUi();
        return;
      }
      body.innerHTML = masterMergeQueueItems.map(masterMergeQueueRowHtml).join("");
      syncMasterMergeSelectionUi();
    }

    function appendMasterMergeQueueItems(items, opts = {}) {
      const rows = Array.isArray(items) ? items : [];
      const preferBaseId = normalizeMasterMergeId(opts.preferBaseId);
      let changed = false;
      for (const row of rows) {
        const rowId = normalizeMasterMergeId(row?.id);
        if (rowId <= 0 || isQueuedMasterMergeId(rowId)) continue;
        masterMergeQueueItems.push({
          id: rowId,
          source_code: String(row?.source_code || "-"),
          source_master_id: String(row?.source_master_id || "-"),
          title: String(row?.title || "-"),
          artist_or_brand: String(row?.artist_or_brand || "-"),
          release_year: row?.release_year ?? null,
          member_count: Number(row?.member_count || 0),
        });
        changed = true;
      }
      if (!masterMergeBaseId && preferBaseId > 0 && isQueuedMasterMergeId(preferBaseId)) {
        masterMergeBaseId = preferBaseId;
      }
      if (!masterMergeBaseId && masterMergeQueueItems.length) {
        masterMergeBaseId = normalizeMasterMergeId(masterMergeQueueItems[0]?.id);
      }
      if (changed) {
        renderMasterMergeRows(masterMergeSearchResults);
      }
      renderMasterMergeQueueRows();
    }

    function clearInternalAlbumMasterMergeWorkbench() {
      masterMergeHasSearched = false;
      masterMergeSearchResults = [];
      masterMergeQueueItems = [];
      masterMergeBaseId = 0;
      if ($("masterMergeQuery")) $("masterMergeQuery").value = "";
      setStatus("masterMergeStatus", "ok", "");
      renderMasterMergeRows([]);
      renderMasterMergeQueueRows();
    }

    function clearInternalAlbumMasterMergeSearch() {
      masterMergeHasSearched = false;
      masterMergeSearchResults = [];
      if ($("masterMergeQuery")) $("masterMergeQuery").value = "";
      setStatus("masterMergeStatus", "ok", "");
      renderMasterMergeRows([]);
    }

    function clearInternalAlbumMasterMergeQueue() {
      masterMergeQueueItems = [];
      masterMergeBaseId = 0;
      renderMasterMergeRows(masterMergeSearchResults);
      renderMasterMergeQueueRows();
    }

    async function searchInternalAlbumMastersForMerge() {
      const query = $("masterMergeQuery").value.trim();
      const params = new URLSearchParams({ limit: "80", media_only: "true" });
      if (query) params.set("q", query);

      masterMergeHasSearched = true;

      try {
        setStatus("masterMergeStatus", "ok", t("media.register.master.merge.status.loading"));
        const res = await fetch(`/album-masters?${params.toString()}`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.register.master.merge.status.failed"));
        renderMasterMergeRows(Array.isArray(data) ? data : []);
        setStatus("masterMergeStatus", "ok", t("media.register.master.merge.status.loaded", {
          count: countWithUnit(Array.isArray(data) ? data.length : 0),
        }));
      } catch (err) {
        masterMergeSearchResults = [];
        renderMasterMergeRows([]);
        setStatus("masterMergeStatus", "err", err.message);
      }
    }

    async function runInternalAlbumMasterMerge() {
      const mergeIds = selectedMasterMergeIds();
      const baseId = normalizeMasterMergeId(masterMergeBaseId);
      if (mergeIds.length < 2) {
        setStatus("masterMergeStatus", "err", t("media.register.master.merge.status.no_selection"));
        return;
      }
      if (!baseId || !mergeIds.includes(baseId)) {
        setStatus("masterMergeStatus", "err", t("media.register.master.merge.status.base_required"));
        return;
      }

      let mergedCount = 0;
      let movedCount = 0;
      const failures = [];
      try {
        setStatus("masterMergeStatus", "ok", t("media.register.master.merge.status.merging", {
          base_id: baseId,
          count: countWithUnit(mergeIds.length - 1),
        }));
        for (const sourceId of mergeIds) {
          if (sourceId === baseId) continue;
          try {
            const res = await fetch(`/album-masters/${sourceId}/merge`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ target_album_master_id: baseId }),
            });
            const data = await safeJson(res);
            if (!res.ok) throw new Error(data.detail || t("media.register.direct.duplicate.merge_failed"));
            mergedCount += Number(data?.merged === false ? 0 : 1);
            movedCount += Number(data?.moved_member_count || 0);
          } catch (err) {
            failures.push(`- ${sourceId}: ${err.message}`);
          }
        }
        await loadAlbumMasterGroups();
        await searchInternalAlbumMastersForMerge();
        masterMergeQueueItems = masterMergeQueueItems.filter((row) => normalizeMasterMergeId(row?.id) === baseId);
        masterMergeBaseId = baseId;
        renderMasterMergeQueueRows();
        if (failures.length) {
          setStatus("masterMergeStatus", "err", t("media.register.master.merge.status.partial", {
            merged_count: formatCount(mergedCount),
            failed_count: formatCount(failures.length),
            base_id: baseId,
            details: `\n${failures.join("\n")}`,
          }));
          return;
        }
        setStatus("masterMergeStatus", "ok", t("media.register.master.merge.status.done", {
          merged_count: formatCount(mergedCount),
          moved_count: formatCount(movedCount),
          base_id: baseId,
        }));
      } catch (err) {
        setStatus("masterMergeStatus", "err", err.message);
      }
    }

    function albumMasterGroupRowHtml(row) {
      return `
        <tr>
          <td>${row.id}</td>
          <td>${escapeHtml(row.source_code)}</td>
          <td>${escapeHtml(row.source_master_id)}</td>
          <td>${escapeHtml(row.title)}</td>
          <td>${escapeHtml(row.artist_or_brand || "-")}</td>
          <td>${row.release_year ?? "-"}</td>
          <td>${row.member_count}</td>
        </tr>
      `;
    }

    async function loadAlbumMasterGroups() {
      const panel = $("masterGroupPanel");
      const body = $("masterGroupBody");
      if (!panel || panel.hidden || !body) return;
      const source = $("masterSource").value;
      const q = $("masterQuery").value.trim();
      const params = new URLSearchParams({ limit: "80" });
      if (source && source !== "AUTO") params.set("source", source);
      if (q) params.set("q", q);

      try {
        setStatus("masterGroupStatus", "ok", t("media.register.master.group.status.loading"));
        const res = await fetch(`/album-masters?${params.toString()}`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.register.master.group.status.failed"));

        body.innerHTML = (data || []).map(albumMasterGroupRowHtml).join("") ||
          `<tr><td colspan='7' class='muted'>${escapeHtml(t("media.register.master.group.state.empty"))}</td></tr>`;
        setStatus("masterGroupStatus", "ok", t("media.register.master.group.status.loaded", { count: countWithUnit(data.length) }));
      } catch (err) {
        body.innerHTML = `<tr><td colspan='7' class='muted'>${escapeHtml(t("media.register.master.group.state.empty"))}</td></tr>`;
        setStatus("masterGroupStatus", "err", err.message);
      }
    }
