
    function renderHomeLinkedGoodsImageList() {
      const root = $("homeLinkedGoodsImageList");
      if (!root) return;
      if (!homeLinkedGoodsImageEntries.length) {
        root.innerHTML = `<span class="mini">${escapeHtml(t("common.none"))}</span>`;
        return;
      }
      root.innerHTML = homeLinkedGoodsImageEntries
        .map((url, idx) => `
          <span class="image-chip-item">
            <a href="${escapeHtml(url)}" target="_blank" rel="noreferrer" title="${escapeHtml(url)}">${escapeHtml(t("common.image_index", { index: idx + 1 }))}</a>
            <button type="button" data-idx="${idx}" class="home-linked-image-remove">x</button>
          </span>
        `)
        .join("");
    }

    async function uploadHomeLinkedGoodsImageFiles(fileList) {
      const uploadedUrls = await uploadUiImageFiles(fileList);
      if (uploadedUrls.length) {
        addHomeLinkedGoodsImageEntries(uploadedUrls);
      }
      return uploadedUrls.length;
    }
    let _editLocalImages = [];

    function renderEditLocalImages() {
      const grid = $("editLocalImagesGrid");
      const section = $("editLocalImagesSection");
      if (!grid) return;
      section.style.display = "";
      if (!_editLocalImages.length) {
        grid.innerHTML = `<span style="font-size:0.8rem;opacity:0.5;">등록된 이미지 없음</span>`;
        return;
      }
      grid.innerHTML = _editLocalImages.map((item, i) => {
        const src = item.local_path || item.uri || "";
        const label = escapeHtml(item.type || "추가");
        return `<div style="position:relative;display:inline-block;text-align:center;cursor:pointer;" onclick="openLocalImageGallery(${i})">
          <img src="${escapeHtml(src)}" alt="${label}" style="width:80px;height:80px;object-fit:cover;border-radius:4px;border:1px solid var(--theme-dashboard-border);" onerror="this.style.opacity=0.3" />
          <div style="font-size:0.65rem;margin-top:2px;opacity:0.7;">${label}</div>
          <button type="button" onclick="event.stopPropagation();deleteEditLocalImage(${i})" style="position:absolute;top:2px;right:2px;background:rgba(0,0,0,0.55);color:#fff;border:none;border-radius:50%;width:18px;height:18px;font-size:10px;cursor:pointer;line-height:18px;padding:0;">✕</button>
        </div>`;
      }).join("");
    }

    function openLocalImageGallery(startIndex) {
      const images = _editLocalImages || [];
      if (!images.length) return;
      let idx = Math.max(0, Math.min(startIndex, images.length - 1));
      const modal = document.getElementById("imageGalleryModal");
      const previewImg = document.getElementById("imageGalleryPreviewImg");
      const meta = document.getElementById("imageGalleryPreviewMeta");
      if (!modal || !previewImg) return;
      modal.style.display = "flex";
      modal.classList.add("_local-mode");
      modal.setAttribute("aria-hidden", "false");
      // Add prev/next buttons if not already there
      if (!document.getElementById("_localGalleryPrev")) {
        const prevBtn = document.createElement("button");
        prevBtn.id = "_localGalleryPrev";
        prevBtn.textContent = "‹";
        prevBtn.style.cssText = "position:absolute;left:16px;top:50%;transform:translateY(-50%);font-size:3rem;color:#fff;background:rgba(0,0,0,0.4);border:none;border-radius:50%;width:48px;height:48px;cursor:pointer;z-index:10;line-height:48px;text-align:center;";
        const nextBtn = document.createElement("button");
        nextBtn.id = "_localGalleryNext";
        nextBtn.textContent = "›";
        nextBtn.style.cssText = "position:absolute;right:16px;top:50%;transform:translateY(-50%);font-size:3rem;color:#fff;background:rgba(0,0,0,0.4);border:none;border-radius:50%;width:48px;height:48px;cursor:pointer;z-index:10;line-height:48px;text-align:center;";
        modal.appendChild(prevBtn);
        modal.appendChild(nextBtn);
        prevBtn.onclick = function(e) { e.stopPropagation(); if (idx > 0) { idx--; show(); } };
        nextBtn.onclick = function(e) { e.stopPropagation(); if (idx < images.length - 1) { idx++; show(); } };
      }
      function show() {
        const img = images[idx];
        const src = img.local_path || img.uri || "";
        previewImg.src = src;
        previewImg.alt = img.type || "이미지";
        if (meta) meta.textContent = (img.type || "이미지") + ` (${idx + 1}/${images.length})`;
        const p = document.getElementById("_localGalleryPrev");
        const n = document.getElementById("_localGalleryNext");
        if (p) p.style.opacity = idx > 0 ? "1" : "0.3";
        if (n) n.style.opacity = idx < images.length - 1 ? "1" : "0.3";
      }
      show();
      modal.onclick = function(e) { if (e.target === modal) { closeGallery(); } };
      const closeBtn = document.getElementById("imageGalleryCloseBtn");
      if (closeBtn) closeBtn.onclick = closeGallery;
      function closeGallery() {
        modal.classList.remove("_local-mode");
        modal.style.display = "none";
        modal.setAttribute("aria-hidden", "true");
        modal.onclick = null;
        if (closeBtn) closeBtn.onclick = null;
        document.removeEventListener("keydown", modal._keyHandler);
        // Remove prev/next buttons
        const p = document.getElementById("_localGalleryPrev");
        const n = document.getElementById("_localGalleryNext");
        if (p) p.remove();
        if (n) n.remove();
      }
      // Keyboard nav
      const handler = function(e) {
        if (e.key === "Escape") { modal.style.display = "none"; modal.setAttribute("aria-hidden", "true"); document.removeEventListener("keydown", handler); return; }
        if (e.key === "ArrowLeft" && idx > 0) { idx--; show(); }
        if (e.key === "ArrowRight" && idx < images.length - 1) { idx++; show(); }
      };
      document.removeEventListener("keydown", modal._keyHandler);
      document.addEventListener("keydown", handler);
      modal._keyHandler = handler;
    }

    function loadEditLocalImages(localImages) {
      _editLocalImages = Array.isArray(localImages) ? localImages.slice() : [];
      renderEditLocalImages();
    }

    async function handleEditImageFileUpload(input) {
      const ownedItemId = Number($("editOwnedId")?.value || 0);
      if (!ownedItemId || !input.files?.length) return;
      const file = input.files[0];
      const imageType = $("editImageTypeSelect")?.value || "추가";
      setStatus("editImageStatus", "ok", "업로드 중...");
      try {
        const form = new FormData();
        form.append("file", file);
        const res = await fetchWithRetry(`/owned-items/${ownedItemId}/images/upload?image_type=${encodeURIComponent(imageType)}`, { method: "POST", body: form });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, "업로드 실패"));
        _editLocalImages = Array.isArray(data.items) ? data.items : _editLocalImages;
        renderEditLocalImages();
        setStatus("editImageStatus", "ok", "업로드 완료");
      } catch (err) {
        setStatus("editImageStatus", "err", errorMessageText(err, "업로드 실패"));
      }
      input.value = "";
    }

    async function handleEditImageUrlAdd() {
      const ownedItemId = Number($("editOwnedId")?.value || 0);
      const url = String($("editImageUrlInput")?.value || "").trim();
      const imageType = $("editImageTypeSelect")?.value || "추가";
      if (!ownedItemId || !url) return;
      setStatus("editImageStatus", "ok", "다운로드 중...");
      try {
        const res = await fetchWithRetry(`/owned-items/${ownedItemId}/images/add-url?url=${encodeURIComponent(url)}&image_type=${encodeURIComponent(imageType)}`, { method: "POST" });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, "다운로드 실패"));
        _editLocalImages = Array.isArray(data.items) ? data.items : _editLocalImages;
        renderEditLocalImages();
        setStatus("editImageStatus", "ok", "다운로드 완료");
        if ($("editImageUrlInput")) $("editImageUrlInput").value = "";
      } catch (err) {
        setStatus("editImageStatus", "err", errorMessageText(err, "다운로드 실패"));
      }
    }

    async function onEditImagePaste(e) {
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
        const ownedItemId = Number($("editOwnedId")?.value || 0);
        if (!ownedItemId) return;
        const imageType = $("editImageTypeSelect")?.value || "추가";
        setStatus("editImageStatus", "ok", "업로드 중...");
        try {
          for (const file of imageFiles) {
            const form = new FormData();
            form.append("file", file);
            const res = await fetchWithRetry(`/owned-items/${ownedItemId}/images/upload?image_type=${encodeURIComponent(imageType)}`, { method: "POST", body: form });
            const data = await safeJson(res);
            if (!res.ok) throw new Error(responseDetailText(data, "업로드 실패"));
            _editLocalImages = Array.isArray(data.items) ? data.items : _editLocalImages;
            renderEditLocalImages();
          }
          setStatus("editImageStatus", "ok", "업로드 완료");
        } catch (err) {
          setStatus("editImageStatus", "err", errorMessageText(err, "업로드 실패"));
        }
        if ($("editImagePasteInput")) $("editImagePasteInput").value = "";
        return;
      }
      const pastedText = String(clipboard.getData("text/plain") || "").trim();
      if (!pastedText) return;
      const urls = extractUrlCandidates(pastedText);
      if (!urls.length) return;
      e.preventDefault();
      if ($("editImageUrlInput")) $("editImageUrlInput").value = urls[0];
      if ($("editImagePasteInput")) $("editImagePasteInput").value = "";
      await handleEditImageUrlAdd();
    }

    async function deleteEditLocalImage(index) {
      const ownedItemId = Number($("editOwnedId")?.value || 0);
      if (!ownedItemId) return;
      if (!window.confirm("이 이미지를 목록에서 제거할까요?")) return;
      try {
        const res = await fetchWithRetry(`/owned-items/${ownedItemId}/images/${index}`, { method: "DELETE" });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, "삭제 실패"));
        _editLocalImages = Array.isArray(data.items) ? data.items : _editLocalImages;
        renderEditLocalImages();
        setStatus("editImageStatus", "ok", "삭제됨");
      } catch (err) {
        setStatus("editImageStatus", "err", errorMessageText(err, "삭제 실패"));
      }
    }

    function renderHomeEditCoverImagePreview() {
      const root = $("homeEditCoverImagePreview");
      const link = $("homeEditCoverSourceLink");
      if (!root) return;
      const url = String($("editCoverImageUrl")?.value || "").trim();
      if (!url) {
        root.innerHTML = `<span class="mini">${escapeHtml(t("common.none"))}</span>`;
        if (link) {
          link.innerHTML = "";
          setDisplayMode(link, "none");
        }
        return;
      }
      root.innerHTML = `
        <a class="home-edit-cover-preview-link" href="${escapeHtml(url)}" target="_blank" rel="noreferrer" title="${escapeHtml(t("image_gallery.action.open_original"))}">
          <div class="table-cover-thumb"><img src="${escapeHtml(url)}" alt="${escapeHtml(t("image_gallery.preview.alt"))}" /></div>
        </a>
      `;
      if (link) {
        link.innerHTML = `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer" title="${escapeHtml(url)}">${escapeHtml(t("image_gallery.action.open_original"))}</a>`;
        setDisplayMode(link, "block");
      }
    }

    function applyHomeEditCoverImageUrl(url, message) {
      const nextUrl = String(url || "").trim();
      $("editCoverImageUrl").value = nextUrl;
      if (!homeLoadedMusicDetail || typeof homeLoadedMusicDetail !== "object") {
        homeLoadedMusicDetail = {};
      }
      homeLoadedMusicDetail.cover_image_url = nextUrl || null;
      renderHomeEditCoverImagePreview();
      syncHomeSourceManagedMetaUi();
      if (message) {
        setStatus("homeEditStatus", "ok", message);
      }
    }

    function handleHomeEditCoverImageUrlApply() {
      const url = String($("homeEditCoverImageUrlInput")?.value || "").trim();
      if (!url) return;
      applyHomeEditCoverImageUrl(url, t("media.manage.cover.status.url_applied"));
      if ($("homeEditCoverImageUrlInput")) $("homeEditCoverImageUrlInput").value = "";
    }

    async function onHomeEditCoverImageFileChange(e) {
      const files = e?.target?.files;
      if (!files || !files.length) return;
      try {
        setStatus("homeEditStatus", "ok", t("media.manage.cover.status.uploading"));
        const uploadedUrls = await uploadUiImageFiles(files);
        const url = String(uploadedUrls[0] || "").trim();
        if (!url) throw new Error(t("media.manage.cover.error.missing_url"));
        applyHomeEditCoverImageUrl(url, t("media.manage.cover.status.uploaded"));
      } catch (err) {
        setStatus("homeEditStatus", "err", err.message);
      } finally {
        e.target.value = "";
      }
    }

    async function onHomeEditCoverImagePaste(e) {
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
          setStatus("homeEditStatus", "ok", t("media.manage.cover.status.paste_uploading"));
          const uploadedUrls = await uploadUiImageFiles(imageFiles);
          const url = String(uploadedUrls[0] || "").trim();
          if (!url) throw new Error(t("media.manage.cover.error.missing_url"));
          applyHomeEditCoverImageUrl(url, t("media.manage.cover.status.paste_uploaded"));
        } catch (err) {
          setStatus("homeEditStatus", "err", err.message);
        } finally {
          $("homeEditCoverImagePaste").value = "";
        }
        return;
      }

      const pastedText = String(clipboard.getData("text/plain") || "").trim();
      if (!pastedText) return;
      const urls = extractUrlCandidates(pastedText);
      if (!urls.length) return;
      e.preventDefault();
      applyHomeEditCoverImageUrl(urls[0], t("media.manage.cover.status.url_applied"));
      $("homeEditCoverImagePaste").value = "";
    }

    async function onHomeLinkedGoodsImageFileChange(e) {
      const files = e?.target?.files;
      if (!files || !files.length) return;
      try {
        setStatus("homeLinkedGoodsStatus", "ok", t("media.manage.collectibles.image.status.uploading"));
        const count = await uploadHomeLinkedGoodsImageFiles(files);
        setStatus("homeLinkedGoodsStatus", "ok", t("media.manage.collectibles.image.status.uploaded", { count: count || 0 }));
      } catch (err) {
        setStatus("homeLinkedGoodsStatus", "err", err.message);
      } finally {
        e.target.value = "";
      }
    }

    async function onHomeLinkedGoodsImagePaste(e) {
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
          setStatus("homeLinkedGoodsStatus", "ok", t("media.manage.collectibles.image.status.paste_uploading"));
          const count = await uploadHomeLinkedGoodsImageFiles(imageFiles);
          setStatus("homeLinkedGoodsStatus", "ok", t("media.manage.collectibles.image.status.paste_uploaded", { count: count || 0 }));
        } catch (err) {
          setStatus("homeLinkedGoodsStatus", "err", err.message);
        } finally {
          $("homeLinkedGoodsImagePaste").value = "";
        }
        return;
      }

      const pastedText = String(clipboard.getData("text/plain") || "").trim();
      if (!pastedText) return;
      const urls = extractUrlCandidates(pastedText);
      if (!urls.length) return;
      e.preventDefault();
      addHomeLinkedGoodsImageEntries(urls);
      $("homeLinkedGoodsImagePaste").value = "";
      setStatus("homeLinkedGoodsStatus", "ok", t("media.manage.collectibles.image.status.urls_applied", { count: urls.length }));
    }

    function cleanDictList(value) {
      if (!Array.isArray(value)) return [];
      return value.filter((row) => row && typeof row === "object" && !Array.isArray(row));
    }

    function buildCollectorPayload(sourceCodeRaw, data) {
      const sourceCode = String(sourceCodeRaw || "").trim().toUpperCase();
      const row = data && typeof data === "object" ? data : {};
      return {
        source_notes: String(row.source_notes || "").trim() || null,
        credits: splitCommaList(row.credits || []),
        identifier_items: cleanDictList(row.identifier_items),
        image_items: cleanDictList(row.image_items),
        company_items: cleanDictList(row.company_items),
        series: splitCommaList(row.series || []),
        format_items: cleanDictList(row.format_items),
        track_items: cleanDictList(row.track_items),
        label_items: cleanDictList(row.label_items),
        runout_matrix: splitRunoutList(row.runout_matrix),
        pressing_country: sourceCode === "DISCOGS" ? (String(row.pressing_country || "").trim() || null) : null,
      };
    }

    function parseTracksFromText(text) {
      const lines = String(text || "").split("\n");
      const items = [];
      let autoIdx = 0;
      let currentSide = null;  // 'A', 'B', ... when [Side X] tag seen
      let sideTrackIdx = 0;
      let currentDisc = null;  // 1, 2, ... when [Disc N] tag seen
      let discTrackIdx = 0;
      for (const rawLine of lines) {
        // Strip leading bullet markers: *, •, -, ·
        let line = rawLine.trim().replace(/^[*•\-·]\s+/, "");
        if (!line) continue;
        autoIdx++;
        let rest = line;
        let duration = "";
        // Extract duration at end: 3:45 / 1:03:45
        const durMatch = rest.match(/\s+(\d{1,2}:\d{2}(?::\d{2})?)$/);
        if (durMatch) {
          duration = durMatch[1];
          rest = rest.slice(0, -durMatch[0].length).trim();
        }
        // Detect and strip [Side X] / (Side X) tags → switch to side notation
        const sideTagMatch = rest.match(/[\[(](?:Side\s*([A-Za-z])|([A-Za-z])\s*Side)[\])]/i);
        if (sideTagMatch) {
          currentSide = (sideTagMatch[1] || sideTagMatch[2]).toUpperCase();
          sideTrackIdx = 0;
          currentDisc = null;
          rest = rest.replace(sideTagMatch[0], "").trim();
        }
        // Detect and strip [Disc N] / (Disc N) tags → switch to disc notation
        const discTagMatch = rest.match(/[\[(]Disc\s*(\d+)[\])]/i);
        if (discTagMatch) {
          currentDisc = Number(discTagMatch[1]);
          discTrackIdx = 0;
          currentSide = null;
          rest = rest.replace(discTagMatch[0], "").trim();
        }
        // If line was only a marker tag, skip (no track item)
        if (!rest) { autoIdx--; continue; }
        // Extract position at start (priority order):
        //   disc-track:  1-1.  1-1  2-3.
        //   vinyl/alpha: A1  B2  A1.
        //   numbered:    1.  12  3
        let position = String(autoIdx);
        const posMatch = rest.match(/^(\d+-\d+\.?|[A-Za-z]-\d+\.?|[A-Ga-g]?\d+[a-z]?\.?)\s+/i);
        if (posMatch) {
          // Consume the position token from the title text
          rest = rest.slice(posMatch[0].length).trim();
        }
        if (currentSide !== null) {
          // Side mode: override position with A-1, B-2, ...
          sideTrackIdx++;
          position = `${currentSide}-${sideTrackIdx}`;
        } else if (currentDisc !== null) {
          // Disc mode: override position with 1-1, 2-3, ...
          discTrackIdx++;
          position = `${currentDisc}-${discTrackIdx}`;
        } else if (posMatch) {
          position = posMatch[1].replace(/\.$/, "");
        }
        if (!rest) continue;
        items.push({ position, title: rest, duration });
      }
      return items;
    }

    function renderHomeTrackInfoPanel() {
      const panel = $("homeEditTrackPanel");
      const summary = $("homeEditTrackInfoSummary");
      const list = $("homeEditTrackInfoList");
      if (!panel || !summary || !list) return;

      const isMusic = MUSIC_CATEGORIES.has($("editCategory").value);
      if (!isMusic) {
        summary.textContent = t("media.manage.tracks.empty");
        list.innerHTML = `<div class="muted">${escapeHtml(t("media.manage.tracks.empty"))}</div>`;
        return;
      }

      const rows = parseTracksFromText($("editTrackList").value);
      summary.textContent = rows.length
        ? t("media.manage.tracks.count", { count: rows.length })
        : t("media.manage.tracks.empty");
      if (!rows.length) {
        list.innerHTML = `<div class="muted">${escapeHtml(t("media.manage.tracks.empty"))}</div>`;
        return;
      }
      // Detect disc-track (e.g. "1-1") or side-track (e.g. "A-1") grouping
      const hasDiscTrack = rows.some((row) => /^\d+-\d+$/.test(String(row.position || "")));
      const hasSideTrack = rows.some((row) => /^[A-Z]-\d+$/.test(String(row.position || "")));
      const trackRow = (row) => `<div class="home-edit-track-row">
        <div class="home-edit-track-pos">${escapeHtml(row.position)}</div>
        <div class="home-edit-track-title">${escapeHtml(row.title)}</div>
        <div class="home-edit-track-duration">${escapeHtml(row.duration)}</div>
      </div>`;
      if (hasSideTrack) {
        let currentGroup = null;
        list.innerHTML = rows.map((row) => {
          const sideMatch = String(row.position || "").match(/^([A-Z])-(\d+)$/);
          const group = sideMatch ? sideMatch[1] : null;
          let header = "";
          if (group && group !== currentGroup) {
            currentGroup = group;
            header = `<div class="home-edit-track-disc-header">${escapeHtml(t("media.manage.tracks.side_label", { side: group }))}</div>`;
          }
          return header + trackRow(row);
        }).join("");
      } else if (hasDiscTrack) {
        let currentDisc = null;
        list.innerHTML = rows.map((row) => {
          const discMatch = String(row.position || "").match(/^(\d+)-(\d+)$/);
          const disc = discMatch ? discMatch[1] : null;
          let header = "";
          if (disc && disc !== currentDisc) {
            currentDisc = disc;
            header = `<div class="home-edit-track-disc-header">${escapeHtml(t("media.manage.tracks.disc_label", { disc }))}</div>`;
          }
          return header + trackRow(row);
        }).join("");
      } else {
        list.innerHTML = rows.map(trackRow).join("");
      }
    }

    function applyCandidateCollectorToHomeDetail(candidate) {
      const sourceCode = String(candidate?.source || homeSelectedSourceCode || "").trim().toUpperCase();
      const collector = buildCollectorPayload(sourceCode, candidate || {});
      if (!homeLoadedMusicDetail || typeof homeLoadedMusicDetail !== "object") {
        homeLoadedMusicDetail = {};
      }
      homeLoadedMusicDetail.source_notes = collector.source_notes;
      homeLoadedMusicDetail.credits = collector.credits;
      homeLoadedMusicDetail.identifier_items = collector.identifier_items;
      homeLoadedMusicDetail.image_items = collector.image_items;
      homeLoadedMusicDetail.company_items = collector.company_items;
      homeLoadedMusicDetail.series = collector.series;
      homeLoadedMusicDetail.format_items = collector.format_items;
      homeLoadedMusicDetail.track_items = collector.track_items;
      homeLoadedMusicDetail.label_items = collector.label_items;
      homeLoadedMusicDetail.runout_matrix = collector.runout_matrix;
      homeLoadedMusicDetail.pressing_country = collector.pressing_country;
      homeLoadedMusicDetail.has_obi = null;
      renderHomeCollectorSummary(homeLoadedMusicDetail);
    }

    function summarizeFormatItems(items, maxItems = 2) {
      const lines = cleanDictList(items).map((row) => formatFormatItem(row)).filter((v) => v);
      if (!lines.length) return "-";
      if (lines.length <= maxItems) return lines.join(" | ");
      return `${lines.slice(0, maxItems).join(" | ")} ${t("common.count.more", { count: lines.length - maxItems })}`;
    }

    function renderHomeCollectorSummary(musicDetail, discogsInfo = null) {
      const detail = musicDetail && typeof musicDetail === "object" && !Array.isArray(musicDetail)
        ? musicDetail
        : {};
      const info = discogsInfo && typeof discogsInfo === "object" && !Array.isArray(discogsInfo)
        ? discogsInfo
        : null;

      let credits = [];
      if (info) {
        const creditItems = Array.isArray(info.credit_items) ? info.credit_items : [];
        if (creditItems.length) {
          credits = creditItems
            .map((row) => {
              const name = String(row?.name || "").trim();
              const role = String(row?.role || "").trim();
              const tracks = String(row?.tracks || "").trim();
              if (name && role) return `${name}/${role}${tracks ? ` [${tracks}]` : ""}`;
              if (name) return name;
              if (role) return role;
              return "";
            })
            .filter((v) => v);
        }
        if (!credits.length) {
          credits = splitCommaList(info.credits || [])
            .map(normalizeCreditDisplay)
            .filter((v) => v);
        }
      }
      if (!credits.length) {
        credits = splitCommaList(detail.credits || [])
          .map(normalizeCreditDisplay)
          .filter((v) => v);
      }
      $("homeCollectorCreditsInfo").textContent = `credits: ${credits.length ? credits.join(" | ") : "-"}`;

      const runout = info
        ? splitRunoutList(info.runout_matrix || [])
        : splitRunoutList(detail.runout_matrix || []);
      const identifierSource = info
        ? cleanDictList(info.identifier_items)
        : cleanDictList(detail.identifier_items);
      const identifierBits = identifierSource
        .map((row) => formatIdentifierItem(row))
        .filter((v) => v);
      const notes = info
        ? (String(info.notes || "").trim() || String(info.source_notes || "").trim())
        : String(detail.source_notes || "").trim();
      const matrixBits = [];
      if (runout.length) matrixBits.push(`Matrix/Runout: ${runout.join(" | ")}`);
      if (identifierBits.length) matrixBits.push(`Identifiers: ${identifierBits.join(" | ")}`);
      if (notes) matrixBits.push(`Notes: ${notes}`);
      $("homeCollectorMatrixInfo").textContent =
        `matrix/identifiers: ${matrixBits.length ? matrixBits.join(" | ") : "-"}`;
    }

    async function loadHomeCollectorSummary(requestSeq = 0) {
      if (requestSeq && !isActiveHomeEditRequest(requestSeq)) return;
      const baseDetail = homeLoadedMusicDetail && typeof homeLoadedMusicDetail === "object"
        ? homeLoadedMusicDetail
        : null;
      const sourceCode = String(homeSelectedSourceCode || "").trim().toUpperCase();
      const releaseId = String(homeSelectedSourceExternalId || "").trim();
      if (sourceCode !== "DISCOGS" || !releaseId) {
        if (requestSeq && !isActiveHomeEditRequest(requestSeq)) return;
        renderHomeCollectorSummary(baseDetail);
        return;
      }
      try {
        const res = await fetch(`/discogs/release/${encodeURIComponent(releaseId)}/collector-info?compare_limit=1`);
        const data = await safeJson(res);
        if (requestSeq && !isActiveHomeEditRequest(requestSeq)) return;
        if (!res.ok) throw new Error(data.detail || "collector info fetch failed");
        renderHomeCollectorSummary(baseDetail, data);
      } catch (_err) {
        if (requestSeq && !isActiveHomeEditRequest(requestSeq)) return;
        renderHomeCollectorSummary(baseDetail);
      }
    }

    function pickMappedDomain(value) {
      const code = String(value || "").trim().toUpperCase();
      return DOMAIN_CODES.has(code) ? code : null;
    }

    function pickMappedReleaseType(value) {
      const code = String(value || "").trim().toUpperCase();
      return RELEASE_TYPES.has(code) ? code : null;
    }

    function getMediaSearchContextSelectedOwnedItemId() {
      return Number(mediaSearchSelectedContextItem?.owned_item_id || mediaSearchSelectedContextItem?.id || 0);
    }

    function findMediaSearchContextItemByOwnedItem(ownedItemId) {
      const targetOwnedItemId = Number(ownedItemId || 0);
      if (targetOwnedItemId <= 0) return null;
      for (const row of Array.isArray(homeSearchResults) ? homeSearchResults : []) {
        const items = Array.isArray(row?.member_items_preview) ? row.member_items_preview : [];
        const match = items.find((item) => Number(item?.owned_item_id || item?.id || 0) === targetOwnedItemId);
        if (match) return {
          ...match,
          review_text: match.review_text ?? row.review_text ?? null,
          review_source: match.review_source ?? row.review_source ?? null,
        };
      }
      return null;
    }

    function renderMediaSearchContextDefault() {
      const activeItem = mediaSearchSelectedContextItem || null;
      if (activeItem) {
        renderMediaSearchContextSelection(activeItem);
        return;
      }
      const root = $("adminSearchContextBody");
      if (!root) return;
      root.innerHTML = `
        <div class="ops-library-context-empty">
          <h3>${escapeHtml(t("media.search.context.title"))}</h3>
          <div class="mini muted">${escapeHtml(t("media.search.context.subtitle"))}</div>
        </div>
        ${renderOpsPluginSection(`
          ${renderOpsArtistContextIdle({ cardId: "mediaSearchArtistContextCard" })}
        `)}
      `;
    }

    function setMediaSearchContextSelectionByOwnedItem(ownedItemId) {
      const nextItem = findMediaSearchContextItemByOwnedItem(ownedItemId);
      if (!nextItem) return false;
      mediaSearchSelectedContextItem = nextItem;
      renderHomeSearchResults(homeSearchResults);
      renderMediaSearchContextDefault();
      return true;
    }

    function renderMediaSearchContextSelection(item) {
      const root = $("adminSearchContextBody");
      if (!root) return;
      const title = String(item?.item_title || item?.item_name_override || "-").trim() || "-";
      const artist = String(item?.artist_or_brand || "").trim();
      const currentLocation = buildOperatorLocationLabel(item);
      const currentCabinetName = String(item?.current_cabinet_name || "").trim();
      const currentColumnCode = String(item?.current_column_code || "").trim();
      const currentCellCode = String(item?.current_cell_code || "").trim();
      const currentSlotCode = String(item?.current_slot_code || "").trim();
      const ownedItemId = Number(item?.owned_item_id || item?.id || 0);
      const canOpenCurrent = Boolean(currentSlotCode || (currentCabinetName && currentColumnCode && currentCellCode));

      // 플레이어: innerHTML 렌더 전에 미리 조회
      const oid = Number(item?.owned_item_id || item?.id || 0);
      let spotifyAlbumId = null;
      let masterIdForReview = 0;
      let hasLocalLink = false;
      for (const row of Array.isArray(homeSearchResults) ? homeSearchResults : []) {
        const members = Array.isArray(row?.member_items_preview) ? row.member_items_preview : [];
        if (members.some(m => Number(m?.owned_item_id || m?.id || 0) === oid)) {
          spotifyAlbumId = row?.spotify_album_id || null;
          masterIdForReview = Number(row?.id || 0);
          hasLocalLink = _localLinkedIds.has(masterIdForReview);
          // Merge fresh review_text if not in cached item
          if (!item.review_text && row.review_text) item = { ...item, review_text: row.review_text, review_source: row.review_source };
          break;
        }
      }

      root.innerHTML = `
        <div class="ops-library-context-head">
          <div class="ops-library-context-head-copy">
            <div class="ops-library-context-eyebrow">${escapeHtml(t("media.search.context.selection_label"))}</div>
            <div class="ops-ctx-title-line">
              <span class="ops-ctx-title">${(function(){
                const sep = " - ";
                let titleOnly = title;
                if (artist && title.startsWith(artist + sep)) titleOnly = title.slice(artist.length + sep.length);
                return escapeHtml(artist ? artist + sep + titleOnly : titleOnly);
              })()}</span>
              ${item?.master_release_year ? `<span class="ops-ctx-year">(${escapeHtml(String(item.master_release_year))})</span>` : ""}
            </div>
          </div>
          <div class="ops-library-context-head-actions">
            ${ownedItemId > 0 ? `<button class="btn tiny" type="button" data-media-search-context-open-manage="${ownedItemId}">${escapeHtml(t("media.manage.search.action.open_detail_manage"))}</button>` : ""}
            <button class="btn ghost tiny" type="button" data-media-search-context-clear="1">${escapeHtml(t("operator.context.action.clear"))}</button>
          </div>
        </div>
        ${hasLocalLink ? `<div id="searchContextLocalPlayerSlot"></div>` : (spotifyAlbumId ? `<div class="ops-ctx-spotify-wrap">${_spotifyEmbedHtml(spotifyAlbumId, 352)}</div>` : "")}
        ${renderOpsPluginSection(`
          ${renderOpsArtistContextCard(item, { cardId: "mediaSearchArtistContextCard" })}
          <div id="mediaSearchReviewSection">${renderAlbumReviewSection(item)}</div>
        `)}
        <details class="ops-ctx-location-details${canOpenCurrent ? "" : " ops-ctx-location-details--no-slot"}">
          <summary class="ops-ctx-location-summary">
            <span class="ops-ctx-location-label">${escapeHtml(t("operator.context.field.current"))}</span>
            <span class="ops-ctx-location-value">${escapeHtml(currentLocation)}</span>
          </summary>
          <div class="ops-ctx-location-body">
            ${canOpenCurrent ? `
            <div class="u-mt-6">
              <button class="operator-mini-linkchip" type="button"
                data-operator-context-open-cabinet="${ownedItemId}"
                data-operator-slot-code="${escapeHtml(currentSlotCode)}"
                data-cabinet-name="${escapeHtml(currentCabinetName)}"
                data-column-code="${escapeHtml(currentColumnCode)}"
                data-cell-code="${escapeHtml(currentCellCode)}"
              >${escapeHtml(t("operator.context.action.open"))}</button>
            </div>` : ""}
            ${renderOpsLibraryContextMiniCabinetMap(item, { mapId: "mediaSearchContextMiniCabinetMap" })}
            ${renderOpsLibraryContextSlotPreview(item, { rootId: "mediaSearchContextSlotPreview" })}
          </div>
        </details>
      `;

      // 별도 Spotify/로컬 패널 숨김
      const searchPanel = document.getElementById('searchSpotifyPanel');
      if (searchPanel) searchPanel.hidden = true;
      // 로컬 링크 있으면 인라인 슬롯에 로드
      if (hasLocalLink && masterIdForReview > 0) {
        _lp.audio.pause(); _lp.audio.src = ""; _lp.idx = -1;
        _lp._slotId = 'searchContextLocalPlayerSlot';
        _lp.load(masterIdForReview).catch(() => {});
      } else {
        if (_lp._slotId === 'searchContextLocalPlayerSlot') { _lp.audio.pause(); _lp.idx = -1; }
      }

      // 캐시에 review_text가 없으면 마스터 API로 최신 데이터 가져와서 갱신
      if (!item.review_text && masterIdForReview > 0) {
        fetchWithRetry(`/album-masters/${masterIdForReview}`).then((res) => res.json()).then((masterData) => {
          if (masterData?.review_text) {
            const reviewEl = document.getElementById("mediaSearchReviewSection");
            if (reviewEl) {
              reviewEl.innerHTML = renderAlbumReviewSection({ ...item, review_text: masterData.review_text, review_source: masterData.review_source, review_url: masterData.review_url });
              reviewEl.querySelectorAll(".ops-artist-context-toggle").forEach(function(btn) {
                btn.addEventListener("click", function() {
                  const expanded = this.getAttribute("aria-expanded") === "true";
                  const textId = this.id.replace("albumReviewToggleBtn_", "albumReviewText_");
                  const textEl = document.getElementById(textId);
                  if (!textEl) return;
                  if (expanded) {
                    textEl.textContent = this.getAttribute("data-review-preview") || "";
                    this.textContent = this.getAttribute("data-show-label") || "펼치기 ▼";
                    this.setAttribute("aria-expanded", "false");
                    this.setAttribute("data-expanded", "false");
                  } else {
                    textEl.textContent = this.getAttribute("data-review-full") || "";
                    this.textContent = this.getAttribute("data-hide-label") || "접기 ▲";
                    this.setAttribute("aria-expanded", "true");
                    this.setAttribute("data-expanded", "true");
                  }
                });
              });
            }
          }
        }).catch(() => {});
      }

      // 앨범 리뷰 펼치기/접기
      root.querySelectorAll(".ops-album-review-card .ops-artist-context-toggle").forEach(function(btn) {
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

      loadOpsArtistContext(item, {
        cardId: "mediaSearchArtistContextCard",
        getActiveItem: () => mediaSearchSelectedContextItem,
      }).catch(() => {});
      loadOpsLibraryContextSlotPreview(item, {
        rootId: "mediaSearchContextSlotPreview",
        getActiveItem: () => mediaSearchSelectedContextItem,
      }).catch(() => {});
    }

    function mediaSearchInlineEditorOwnedKey(ownedItemId) {
      const numericOwnedItemId = Number(ownedItemId || 0);
      return numericOwnedItemId > 0 ? String(numericOwnedItemId) : "";
    }

    function getMediaSearchExpandedPreviewOwnedItemId(masterId) {
      return String(mediaSearchExpandedPreviewByMaster.get(String(masterId)) || "").trim();
    }

    function setMediaSearchInlineEditorStatus(ownedItemId, kind = "", message = "") {
      const key = mediaSearchInlineEditorOwnedKey(ownedItemId);
      if (!key) return;
      const text = String(message || "").trim();
      if (!text) {
        mediaSearchInlineEditorStatusByOwnedItem.delete(key);
        return;
      }
      mediaSearchInlineEditorStatusByOwnedItem.set(key, {
        kind: String(kind || "ok").trim() || "ok",
        message: text,
      });
    }

    function getMediaSearchInlineEditorStatus(ownedItemId) {
      const key = mediaSearchInlineEditorOwnedKey(ownedItemId);
      if (!key) return null;
      return mediaSearchInlineEditorStatusByOwnedItem.get(key) || null;
    }

    function buildMediaSearchInlineEditorPayload(detail, overrides = {}) {
      if (!detail || typeof detail !== "object") return null;
      const category = String(detail.category || "").trim().toUpperCase() || "LP";
      const payload = {
        category,
        size_group: detail.size_group || defaultSizeGroupForCategory(category),
        preferred_storage_size_group: overrides.preferred_storage_size_group !== undefined
          ? (String(overrides.preferred_storage_size_group || "").trim().toUpperCase() || detail.size_group || defaultSizeGroupForCategory(category))
          : (detail.preferred_storage_size_group || detail.size_group || defaultSizeGroupForCategory(category)),
        quantity: Math.max(1, Number(detail.quantity || 1) || 1),
        is_second_hand: Boolean(detail.is_second_hand),
        status: String(overrides.status || detail.status || "IN_COLLECTION").trim().toUpperCase() || "IN_COLLECTION",
        signature_type: String(overrides.signature_type || detail.signature_type || "NONE").trim().toUpperCase() || "NONE",
        source_code: detail.source_code || null,
        source_external_id: detail.source_external_id || null,
        domain_code: overrides.domain_code !== undefined
          ? (String(overrides.domain_code || "").trim().toUpperCase() || null)
          : (detail.domain_code || null),
        release_type: detail.release_type || null,
        master_item_id: detail.master_item_id || null,
        linked_album_master_id: detail.linked_album_master_id || null,
        linked_artist_name: detail.linked_artist_name || null,
        copy_group_key: detail.copy_group_key || null,
        item_name_override: detail.item_name_override || null,
        condition_grade: detail.condition_grade || null,
        purchase_price: overrides.purchase_price !== undefined
          ? (overrides.purchase_price ?? null)
          : (detail.purchase_price ?? null),
        currency_code: overrides.currency_code !== undefined
          ? (String(overrides.currency_code || "").trim().toUpperCase() || null)
          : (detail.currency_code || null),
        purchase_source: detail.purchase_source || null,
        memory_note: overrides.memory_note !== undefined
          ? (String(overrides.memory_note || "").trim() || null)
          : (detail.memory_note || null),
        display_rank: detail.display_rank ?? null,
        storage_slot_id: detail.storage_slot_id || null,
        thickness_mm: detail.thickness_mm ?? null,
        notes: detail.notes || null,
        subtype_option_ids: Array.isArray(detail.subtype_option_ids) ? detail.subtype_option_ids.map((value) => Number(value || 0)).filter((value) => value > 0) : [],
        soundtrack_option_ids: Array.isArray(detail.soundtrack_option_ids) ? detail.soundtrack_option_ids.map((value) => Number(value || 0)).filter((value) => value > 0) : [],
      };
      if (detail.music_detail && typeof detail.music_detail === "object") {
        payload.music_detail = JSON.parse(JSON.stringify(detail.music_detail));
        payload.music_detail.cover_condition = overrides.cover_condition !== undefined
          ? (String(overrides.cover_condition || "").trim().toUpperCase() || null)
          : (payload.music_detail.cover_condition || null);
        payload.music_detail.disc_condition = overrides.disc_condition !== undefined
          ? (String(overrides.disc_condition || "").trim().toUpperCase() || null)
          : (payload.music_detail.disc_condition || null);
        payload.music_detail.has_obi = overrides.has_obi !== undefined
          ? overrides.has_obi
          : (payload.music_detail.has_obi ?? null);
      }
      if (detail.goods_detail && typeof detail.goods_detail === "object") {
        payload.goods_detail = JSON.parse(JSON.stringify(detail.goods_detail));
      }
      return payload;
    }

    function mediaSearchInlineEditorStatusOptionsHtml(selectedValue) {
      const selected = String(selectedValue || "IN_COLLECTION").trim().toUpperCase() || "IN_COLLECTION";
      return ["IN_COLLECTION", "LOANED", "SOLD", "LOST", "ARCHIVED"]
        .map((value) => `<option value="${value}" ${value === selected ? "selected" : ""}>${escapeHtml(dashboardStatusLabel(value))}</option>`)
        .join("");
    }

    function mediaSearchInlineEditorSignatureOptionsHtml(selectedValue) {
      const selected = String(selectedValue || "NONE").trim().toUpperCase() || "NONE";
      return ["NONE", "IN_PERSON", "PURCHASE_INCLUDED", "UNKNOWN"]
        .map((value) => `<option value="${value}" ${value === selected ? "selected" : ""}>${escapeHtml(signatureTypeDisplayLabel(value))}</option>`)
        .join("");
    }

    function mediaSearchInlineEditorDomainOptionsHtml(selectedValue) {
      const selected = String(selectedValue || "").trim().toUpperCase();
      return ["", "KOREA", "JAPAN", "GREATER_CHINA", "WESTERN", "OTHER_ASIA", "WORLD", "UNKNOWN"]
        .map((value) => {
          const label = value ? dashboardDomainLabel(value) : t("common.unspecified");
          return `<option value="${value}" ${value === selected ? "selected" : ""}>${escapeHtml(label)}</option>`;
        })
        .join("");
    }

    function mediaSearchInlineEditorPreferredSizeOptionsHtml(selectedValue) {
      const selected = String(selectedValue || "").trim().toUpperCase();
      return ["STD", "BOOK", "LP", "LP10", "LP7", "OVERSIZE", "CASSETTE", "8TRACK", "REEL_TO_REEL", "GOODS"]
        .map((value) => `<option value="${value}" ${value === selected ? "selected" : ""}>${escapeHtml(dashboardSizeGroupLabel(value))}</option>`)
        .join("");
    }

    function mediaSearchInlineEditorCurrencyOptionsHtml(selectedValue) {
      const selected = String(selectedValue || "KRW").trim().toUpperCase() || "KRW";
      return ["KRW", "USD", "GBP", "JPY", "EUR"]
        .map((value) => `<option value="${value}" ${value === selected ? "selected" : ""}>${escapeHtml(value)}</option>`)
        .join("");
    }

    function mediaSearchInlineEditorConditionOptionsHtml(selectedValue) {
      const selected = String(selectedValue || "").trim().toUpperCase();
      return [
        ["", "-"],
        ["M", "M (Mint)"],
        ["NM", "NM / M- (Near Mint)"],
        ["VG+", "VG+ / E (Excellent)"],
        ["VG", "VG"],
        ["G+", "G+ / VG-"],
        ["G", "G"],
        ["F", "F (Fair)"],
        ["P", "P (Poor)"],
      ].map(([value, label]) => `<option value="${value}" ${value === selected ? "selected" : ""}>${escapeHtml(label)}</option>`).join("");
    }

    function renderMediaSearchInlineEditor(masterId, item) {
      const ownedItemId = Number(item?.owned_item_id || item?.id || 0);
      if (ownedItemId <= 0) return "";
      if (getMediaSearchExpandedPreviewOwnedItemId(masterId) !== mediaSearchInlineEditorOwnedKey(ownedItemId)) return "";
      const cacheKey = mediaSearchInlineEditorOwnedKey(ownedItemId);
      const detail = mediaSearchInlineEditorDetailCache.get(cacheKey) || null;
      const statusEntry = getMediaSearchInlineEditorStatus(ownedItemId);
      const statusHtml = statusEntry?.message
        ? `<div class="media-search-inline-editor-status ${statusEntry.kind === "err" ? "is-error" : ""}">${escapeHtml(statusEntry.message)}</div>`
        : "";
      if (!detail) {
        return `
          <div class="media-search-inline-editor" data-media-search-inline-editor="${ownedItemId}">
            <div class="media-search-inline-editor-head">
              <div class="media-search-inline-editor-copy">
                <span class="media-search-inline-editor-kicker">${escapeHtml(t("media.manage.search.inline_editor.kicker"))}</span>
                <strong>${escapeHtml(t("common.action.edit_item"))}</strong>
              </div>
              <span class="home-master-member-preview-code">${escapeHtml(String(item?.label_id || "-").trim() || "-")}</span>
            </div>
            ${statusHtml || `<div class="media-search-inline-editor-status">${escapeHtml(t("media.manage.edit.status.loading"))}</div>`}
            <div class="media-search-inline-editor-actions">
              <button class="btn ghost tiny" type="button" data-media-search-inline-cancel="${masterId}">${escapeHtml(t("common.action.cancel"))}</button>
            </div>
          </div>
        `;
      }
      const isSaving = mediaSearchInlineEditorSavingOwnedIds.has(cacheKey);
      return `
        <div class="media-search-inline-editor" data-media-search-inline-editor="${ownedItemId}">
          <div class="media-search-inline-editor-head">
            <div class="media-search-inline-editor-copy">
              <span class="media-search-inline-editor-kicker">${escapeHtml(t("media.manage.search.inline_editor.kicker"))}</span>
              <strong>${escapeHtml(t("common.action.edit_item"))}</strong>
            </div>
            <span class="home-master-member-preview-code">${escapeHtml(String(detail.label_id || item?.label_id || "-").trim() || "-")}</span>
          </div>
          <div class="media-search-inline-editor-grid">
            <label class="media-search-inline-editor-field">
              <span>${escapeHtml(t("media.manage.product.field.status.label"))}</span>
              <select data-media-search-inline-status-field="${ownedItemId}" ${isSaving ? "disabled" : ""}>
                ${mediaSearchInlineEditorStatusOptionsHtml(detail.status)}
              </select>
            </label>
            <label class="media-search-inline-editor-field">
              <span>${escapeHtml(t("media.manage.product.field.signature_type.label"))}</span>
              <select data-media-search-inline-signature-field="${ownedItemId}" ${isSaving ? "disabled" : ""}>
                ${mediaSearchInlineEditorSignatureOptionsHtml(detail.signature_type)}
              </select>
            </label>
            <label class="media-search-inline-editor-field">
              <span>${escapeHtml(t("media.manage.product.field.domain_code.label"))}</span>
              <select data-media-search-inline-domain-field="${ownedItemId}" ${isSaving ? "disabled" : ""}>
                ${mediaSearchInlineEditorDomainOptionsHtml(detail.domain_code)}
              </select>
            </label>
            <label class="media-search-inline-editor-field">
              <span>${escapeHtml(t("common.meta.storage_size"))}</span>
              <select data-media-search-inline-preferred-size-field="${ownedItemId}" ${isSaving ? "disabled" : ""}>
                ${mediaSearchInlineEditorPreferredSizeOptionsHtml(detail.preferred_storage_size_group || detail.size_group)}
              </select>
            </label>
            <label class="media-search-inline-editor-field">
              <span>${escapeHtml(t("media.manage.product.field.purchase_price.label"))}</span>
              <input type="number" min="0" step="0.01" data-media-search-inline-purchase-price-field="${ownedItemId}" value="${escapeHtml(detail.purchase_price ?? "")}" ${isSaving ? "disabled" : ""} />
            </label>
            <label class="media-search-inline-editor-field">
              <span>${escapeHtml(t("media.manage.product.field.currency_code.label"))}</span>
              <select data-media-search-inline-currency-field="${ownedItemId}" ${isSaving ? "disabled" : ""}>
                ${mediaSearchInlineEditorCurrencyOptionsHtml(detail.currency_code)}
              </select>
            </label>
            <label class="media-search-inline-editor-field">
              <span>${escapeHtml(t("media.manage.product.field.cover_condition.label"))}</span>
              <select data-media-search-inline-cover-condition-field="${ownedItemId}" ${isSaving ? "disabled" : ""}>
                ${mediaSearchInlineEditorConditionOptionsHtml(detail.music_detail?.cover_condition || detail.cover_condition)}
              </select>
            </label>
            <label class="media-search-inline-editor-field">
              <span>${escapeHtml(t("media.manage.product.field.disc_condition.label"))}</span>
              <select data-media-search-inline-disc-condition-field="${ownedItemId}" ${isSaving ? "disabled" : ""}>
                ${mediaSearchInlineEditorConditionOptionsHtml(detail.music_detail?.disc_condition || detail.disc_condition)}
              </select>
            </label>
            <label class="media-search-inline-editor-field">
              <span>${escapeHtml(t("media.manage.product.field.has_obi.label"))}</span>
              <input type="checkbox" data-media-search-inline-has-obi-field="${ownedItemId}" ${detail.music_detail?.has_obi ? "checked" : ""} ${isSaving ? "disabled" : ""} />
            </label>
            <label class="media-search-inline-editor-field u-grid-col-span-all">
              <span>${escapeHtml(t("media.manage.product.field.memory_note.label"))}</span>
              <textarea data-media-search-inline-memory-note-field="${ownedItemId}" ${isSaving ? "disabled" : ""}>${escapeHtml(detail.memory_note || "")}</textarea>
            </label>
          </div>
          ${statusHtml}
          <div class="media-search-inline-editor-actions">
            <button class="btn tiny" type="button" data-media-search-inline-save="${ownedItemId}" data-media-search-inline-save-master-id="${masterId}" ${isSaving ? "disabled" : ""}>${escapeHtml(t("common.action.save"))}</button>
            <button class="btn ghost tiny" type="button" data-media-search-inline-cancel="${masterId}" ${isSaving ? "disabled" : ""}>${escapeHtml(t("common.action.cancel"))}</button>
          </div>
          <details class="inline-entity-history" data-history-type="owned_item" data-history-id="${ownedItemId}" style="margin-top:10px;font-size:0.8rem">
            <summary style="cursor:pointer;color:var(--accent);font-weight:600;padding:4px 0">변경 이력 / 장식장 이력</summary>
            <div class="inline-entity-history-body" style="padding:8px 0"></div>
          </details>
        </div>
      `;
    }

    async function loadMediaSearchInlineEditorDetail(ownedItemId) {
      const cacheKey = mediaSearchInlineEditorOwnedKey(ownedItemId);
      if (!cacheKey || mediaSearchInlineEditorDetailCache.has(cacheKey) || mediaSearchInlineEditorLoadingOwnedIds.has(cacheKey)) return;
      mediaSearchInlineEditorLoadingOwnedIds.add(cacheKey);
      setMediaSearchInlineEditorStatus(ownedItemId, "ok", t("media.manage.edit.status.loading"));
      renderHomeSearchResults(homeSearchResults);
      try {
        const res = await fetchWithRetry(`/owned-items/${encodeURIComponent(cacheKey)}`, {}, {
          retries: 2,
          retryDelayMs: 250,
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.edit.status.load_failed"));
        mediaSearchInlineEditorDetailCache.set(cacheKey, data);
        setMediaSearchInlineEditorStatus(ownedItemId);
      } catch (err) {
        setMediaSearchInlineEditorStatus(ownedItemId, "err", err.message || t("media.manage.edit.status.load_failed"));
      } finally {
        mediaSearchInlineEditorLoadingOwnedIds.delete(cacheKey);
        renderHomeSearchResults(homeSearchResults);
      }
    }

    async function executeMetadataSyncAction(ownedItemId, metaSyncBtn, onComplete) {
      if (ownedItemId <= 0) return;
      metaSyncBtn.disabled = true;
      const origLabel = metaSyncBtn.textContent;
      metaSyncBtn.textContent = t("media.manage.search.action.sync_meta.running");
      try {
        const res = await fetch(`/owned-items/${encodeURIComponent(ownedItemId)}/sync-metadata`, { method: "POST" });
        const data = await safeJson(res);
        if (!res.ok) {
          const errMsg = data?.detail || data?.reason || t("media.manage.search.action.sync_meta.fail");
          showShellBarcodeToast(`✗ ${t("media.manage.search.action.sync_meta.fail")}: ${errMsg}`);
        } else {
          const status = String(data?.status || "").toUpperCase();
          if (status === "UPDATED") {
            const fields = Array.isArray(data?.updated_fields) && data.updated_fields.length
              ? data.updated_fields.join(", ")
              : "";
            showShellBarcodeToast(fields
              ? `✓ ${t("media.manage.search.action.sync_meta.success")}: ${fields}`
              : `✓ ${t("media.manage.search.action.sync_meta.success")}`);
            if (typeof onComplete === "function") {
              await onComplete();
            }
          } else if (status === "SKIPPED") {
            showShellBarcodeToast(`— ${t("media.manage.search.action.sync_meta.skipped")}`);
          } else {
            const reason = String(data?.reason || "").trim();
            showShellBarcodeToast(reason
              ? `✗ ${t("media.manage.search.action.sync_meta.fail")}: ${reason}`
              : `✗ ${t("media.manage.search.action.sync_meta.fail")}`);
          }
        }
      } catch (err) {
        showShellBarcodeToast(`✗ ${t("media.manage.search.action.sync_meta.fail")}: ${err?.message || ""}`);
      } finally {
        metaSyncBtn.disabled = false;
        metaSyncBtn.textContent = origLabel;
      }
    }

    async function refreshHomeSearchResultCard(masterId) {
      const activeOwnedItemId = getMediaSearchContextSelectedOwnedItemId();
      await homeSearchOwnedItems({ allowPageAdjust: false });
      if (activeOwnedItemId > 0) {
        setMediaSearchContextSelectionByOwnedItem(activeOwnedItemId);
      }
      if (Number(masterId || 0) <= 0) return;
    }

    async function openMediaSearchInlineEditor(masterId, ownedItemId) {
      const targetMasterId = Number(masterId || 0);
      const targetOwnedItemId = Number(ownedItemId || 0);
      if (targetMasterId <= 0 || targetOwnedItemId <= 0) return;
      const currentOwnedItemId = getMediaSearchExpandedPreviewOwnedItemId(targetMasterId);
      const nextOwnedItemId = currentOwnedItemId === String(targetOwnedItemId) ? "" : String(targetOwnedItemId);
      if (nextOwnedItemId) {
        mediaSearchExpandedPreviewByMaster.set(String(masterId), nextOwnedItemId);
      } else {
        mediaSearchExpandedPreviewByMaster.delete(String(masterId));
      }
      renderHomeSearchResults(homeSearchResults);
      if (nextOwnedItemId) {
        await loadMediaSearchInlineEditorDetail(Number(nextOwnedItemId));
      }
    }

    function cancelMediaSearchInlineEditor(masterId) {
      if (Number(masterId || 0) <= 0) return;
      mediaSearchExpandedPreviewByMaster.delete(String(masterId));
      renderHomeSearchResults(homeSearchResults);
    }

    async function saveMediaSearchInlineEditor(masterId, ownedItemId) {
      const cacheKey = mediaSearchInlineEditorOwnedKey(ownedItemId);
      if (!cacheKey) return;
      const detail = mediaSearchInlineEditorDetailCache.get(cacheKey) || null;
      if (!detail) {
        await loadMediaSearchInlineEditorDetail(ownedItemId);
        return;
      }
      const statusField = document.querySelector(`[data-media-search-inline-status-field="${cacheKey}"]`);
      const signatureField = document.querySelector(`[data-media-search-inline-signature-field="${cacheKey}"]`);
      const domainField = document.querySelector(`[data-media-search-inline-domain-field="${cacheKey}"]`);
      const preferredSizeField = document.querySelector(`[data-media-search-inline-preferred-size-field="${cacheKey}"]`);
      const purchasePriceField = document.querySelector(`[data-media-search-inline-purchase-price-field="${cacheKey}"]`);
      const currencyField = document.querySelector(`[data-media-search-inline-currency-field="${cacheKey}"]`);
      const coverConditionField = document.querySelector(`[data-media-search-inline-cover-condition-field="${cacheKey}"]`);
      const discConditionField = document.querySelector(`[data-media-search-inline-disc-condition-field="${cacheKey}"]`);
      const hasObiField = document.querySelector(`[data-media-search-inline-has-obi-field="${cacheKey}"]`);
      const memoryNoteField = document.querySelector(`[data-media-search-inline-memory-note-field="${cacheKey}"]`);
      const nextStatus = String(statusField?.value || detail.status || "IN_COLLECTION").trim().toUpperCase() || "IN_COLLECTION";
      const nextSignatureType = String(signatureField?.value || detail.signature_type || "NONE").trim().toUpperCase() || "NONE";
      const nextDomainCode = String(domainField?.value || "").trim().toUpperCase() || null;
      const nextPreferredSizeGroup = String(preferredSizeField?.value || detail.preferred_storage_size_group || detail.size_group || "").trim().toUpperCase() || null;
      const purchasePriceText = String(purchasePriceField?.value || "").trim();
      const nextPurchasePrice = purchasePriceText ? Number(purchasePriceText) : null;
      const nextCurrencyCode = String(currencyField?.value || detail.currency_code || "KRW").trim().toUpperCase() || null;
      const nextCoverCondition = String(coverConditionField?.value || "").trim().toUpperCase() || null;
      const nextDiscCondition = String(discConditionField?.value || "").trim().toUpperCase() || null;
      const nextHasObi = hasObiField ? Boolean(hasObiField.checked) : null;
      const nextMemoryNote = String(memoryNoteField?.value || "").trim();
      mediaSearchInlineEditorDetailCache.set(cacheKey, {
        ...detail,
        status: nextStatus,
        signature_type: nextSignatureType,
        domain_code: nextDomainCode,
        preferred_storage_size_group: nextPreferredSizeGroup,
        purchase_price: nextPurchasePrice,
        currency_code: nextCurrencyCode,
        memory_note: nextMemoryNote || null,
        music_detail: {
          ...(detail.music_detail && typeof detail.music_detail === "object" ? detail.music_detail : {}),
          cover_condition: nextCoverCondition,
          disc_condition: nextDiscCondition,
          has_obi: nextHasObi,
        },
      });
      mediaSearchInlineEditorSavingOwnedIds.add(cacheKey);
      setMediaSearchInlineEditorStatus(ownedItemId, "ok", t("media.manage.edit.status.saving"));
      renderHomeSearchResults(homeSearchResults);
      try {
        const payload = buildMediaSearchInlineEditorPayload(detail, {
          status: nextStatus,
          signature_type: nextSignatureType,
          domain_code: nextDomainCode,
          preferred_storage_size_group: nextPreferredSizeGroup,
          purchase_price: nextPurchasePrice,
          currency_code: nextCurrencyCode,
          cover_condition: nextCoverCondition,
          disc_condition: nextDiscCondition,
          has_obi: nextHasObi,
          memory_note: nextMemoryNote,
        });
        const res = await fetchWithRetry(`/owned-items/${encodeURIComponent(cacheKey)}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }, {
          retries: 2,
          retryDelayMs: 250,
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.edit.status.save_failed"));
        mediaSearchInlineEditorDetailCache.delete(cacheKey);
        setMediaSearchInlineEditorStatus(ownedItemId, "ok", t("media.manage.edit.status.saved", { label_id: data.label_id || detail.label_id || cacheKey }));
        await refreshHomeSearchResultCard(masterId);
        await loadMediaSearchInlineEditorDetail(ownedItemId);
      } catch (err) {
        setMediaSearchInlineEditorStatus(ownedItemId, "err", err.message || t("media.manage.edit.status.save_failed"));
      } finally {
        mediaSearchInlineEditorSavingOwnedIds.delete(cacheKey);
        renderHomeSearchResults(homeSearchResults);
      }
    }

    function ensureHomeManageStructuralSectionVisible() {
      $("homeMasterFetchDetails")?.setAttribute("open", "");
      $("homeMasterLookupResultsDetails")?.removeAttribute("open");
    }

    async function openMediaSearchDetailManage(masterId, ownedItemId) {
      openAdminConsole("media", { remember: false, mediaMode: "manage" });
      const targetMasterId = Number(masterId || 0);
      const targetOwnedItemId = Number(ownedItemId || 0);
      let resolvedMasterId = targetMasterId;
      if (resolvedMasterId <= 0 && targetOwnedItemId > 0) {
        resolvedMasterId = resolveHomeManageMasterIdForOwnedItem(targetOwnedItemId);
      }
      if (resolvedMasterId <= 0 && targetOwnedItemId > 0) {
        try {
          const res = await fetch(`/owned-items/${encodeURIComponent(targetOwnedItemId)}`);
          const data = await safeJson(res);
          if (res.ok) {
            resolvedMasterId = Number(data?.linked_album_master_id || data?.album_master_id || 0);
          }
        } catch (_) {}
      }
      if (resolvedMasterId > 0) {
        homeSelectedMasterId = resolvedMasterId;
        syncHomeMasterDeleteUi();
        await loadHomeMasterMembers(resolvedMasterId, { autoOpenFirst: false });
      }
      if (targetOwnedItemId > 0) {
        await loadHomeItemForEdit(targetOwnedItemId, {
          keepMasterContext: resolvedMasterId > 0,
          resetMasterLookupUi: false,
        });
      }
      ensureHomeManageStructuralSectionVisible();
    }

    function shouldKeepHomeMasterContextForOwnedItem(ownedItemId) {
      const targetOwnedItemId = Number(ownedItemId || 0);
      const masterId = Number(homeSelectedMasterId || 0);
      if (targetOwnedItemId <= 0 || masterId <= 0) return false;
      if (targetOwnedItemId === Number(homeSelectedItemId || 0)) return true;
      const items = Array.isArray(homeMasterInfo?.items) ? homeMasterInfo.items : [];
      return items.some((row) => Number(row?.id || 0) === targetOwnedItemId);
    }

    function resolveHomeManageMasterIdForOwnedItem(ownedItemId, opts = {}) {
      const explicitMasterId = Number(opts.masterId || 0);
      if (explicitMasterId > 0) return explicitMasterId;
      const targetOwnedItemId = Number(ownedItemId || 0);
      if (targetOwnedItemId <= 0) return 0;
      if (targetOwnedItemId === Number(homeSelectedItemId || 0) && Number(homeSelectedMasterId || 0) > 0) {
        return Number(homeSelectedMasterId || 0);
      }
      const rowLists = [
        Array.isArray(homeMasterInfo?.items) ? homeMasterInfo.items : [],
        Array.isArray(homeEditShelfItems) ? homeEditShelfItems : [],
        Array.isArray(opsExceptionItems) ? opsExceptionItems : [],
        Array.isArray(sourceWorkbenchQueue) ? sourceWorkbenchQueue : [],
      ];
      for (const rows of rowLists) {
        const row = rows.find((item) => Number(item?.id || item?.owned_item_id || 0) === targetOwnedItemId);
        const masterId = Number(row?.linked_album_master_id || row?.album_master_id || 0);
        if (masterId > 0) return masterId;
      }
      // Do not fall back to the old master — caller (openMediaSearchDetailManage)
      // will fetch the item's own linked_album_master_id from the API when 0 is returned.
      return 0;
    }

    async function openHomeOwnedItemFromManageContext(ownedItemId, opts = {}) {
      const targetOwnedItemId = Number(ownedItemId || 0);
      if (targetOwnedItemId <= 0) return;
      const keepMasterContext = opts.keepMasterContext == null
        ? shouldKeepHomeMasterContextForOwnedItem(targetOwnedItemId)
        : Boolean(opts.keepMasterContext);
      const masterId = resolveHomeManageMasterIdForOwnedItem(targetOwnedItemId, {
        masterId: keepMasterContext ? Number(opts.masterId || homeSelectedMasterId || 0) : Number(opts.masterId || 0),
      });
      homeInlineEditorCollapsed = false;
      await openMediaSearchDetailManage(masterId, targetOwnedItemId);
      requestAnimationFrame(() => {
        $("homeMasterRelatedList")?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }

    async function refreshHomeManageContext(ownedItemId, opts = {}) {
      const targetOwnedItemId = Number(ownedItemId || 0);
      if (targetOwnedItemId <= 0) return;
      // URL hash 갱신 — 직접 링크 공유/복원용
      if (!opts._fromHash) {
        const newHash = `#item/${targetOwnedItemId}`;
        if (window.location.hash !== newHash) {
          history.pushState(null, "", newHash);
        }
      }
      const keepMasterContext = Boolean(opts.keepMasterContext ?? homeSelectedMasterId);
      const masterId = Number(opts.masterId ?? homeSelectedMasterId ?? 0);
      if (keepMasterContext && masterId > 0 && opts.reloadMaster !== false) {
        await loadHomeMasterMembers(masterId, { autoOpenFirst: false });
      }
      await loadHomeItemForEdit(targetOwnedItemId, { keepMasterContext });
    }

    function isManagedSourceCode(value) {
      return SOURCE_MANAGED_CODES.has(String(value || "").trim().toUpperCase());
    }

    function isHomeSourceManagedItem() {
      const category = $("editCategory").value;
      return MUSIC_CATEGORIES.has(category) && isManagedSourceCode(homeSelectedSourceCode);
    }

    function renderHomeSourceManagedMetaSummary() {
      const box = $("homeEditMusicSourceSummary");
      const tracksWrap = $("homeEditMusicSourceTracksWrap");
      if (!box) return;
      if (!isHomeSourceManagedItem()) {
        setHiddenState(box, true);
        setHiddenState(tracksWrap, true);
        return;
      }

      const sourceCode = String(homeSelectedSourceCode || "").trim().toUpperCase();
      const sourceLabel = sourceCode === "DISCOGS"
        ? "Discogs"
        : (sourceCode === "MANIADB" ? "ManiaDB" : (sourceCode === "ALADIN" ? "Aladin" : sourceCode));
      const sourceExternalId = String(homeSelectedSourceExternalId || "").trim() || "-";
      const itemName = $("editItemName").value.trim() || "-";
      const formatText = mediaDisplayLabel($("editFormatName").value || $("editCategory").value);
      const releasedDate = $("editReleasedDate").value.trim() || "-";
      const labelName = $("editLabelName").value.trim() || "-";
      const catalogNo = $("editCatalogNo").value.trim() || "-";
      const pressingCountry = $("editPressingCountry").value.trim() || "-";
      const barcode = $("editBarcode").value.trim() || "-";
      const trackList = splitLineList($("editTrackList").value);
      const trackText = trackList.length ? trackList.join("\n") : "-";
      const signatureText = signatureTypeDisplayLabel($("editSignatureType").value);
      const memoRaw = $("editMemoryNote").value.trim();
      const memoText = memoRaw ? (memoRaw.length > 120 ? `${memoRaw.slice(0, 120)}...` : memoRaw) : "-";
      const labelSummary = [labelName, catalogNo].filter((value) => value && value !== "-").join(" / ") || "-";
      const mainSummaryHtml = [
        operatorMetaPairHtml(t("media.manage.source_meta.label.source"), `${sourceLabel}#${sourceExternalId}`),
        operatorMetaPairHtml(t("media.manage.source_meta.label.item"), itemName),
        operatorMetaPairHtml(t("media.manage.source_meta.label.format"), formatText),
        operatorMetaPairHtml(t("media.manage.source_meta.label.release"), releasedDate),
        operatorMetaPairHtml(t("media.manage.source_meta.label.country"), pressingCountry),
      ].filter((value) => value).join('<span class="operator-meta-separator">/</span>');
      const subSummaryHtml = [
        operatorMetaPairHtml(t("media.manage.source_meta.label.label"), labelSummary),
        operatorMetaPairHtml(t("media.manage.source_meta.label.barcode"), barcode),
        operatorMetaPairHtml(t("media.manage.source_meta.label.signature"), signatureText, { subtle: true }),
        operatorMetaPairHtml(t("media.manage.source_meta.label.memo"), memoText, { subtle: true }),
      ].filter((value) => value).join('<span class="operator-meta-separator">/</span>');

      $("homeEditMusicSourceSummaryMain").innerHTML = mainSummaryHtml || `<span class="operator-meta-value">-</span>`;
      $("homeEditMusicSourceSummarySub").innerHTML = subSummaryHtml || `<span class="operator-meta-value">-</span>`;
      setDisplayIfPresent("homeEditMusicSourceSummaryExtra", "none");
      setDisplayIfPresent("homeEditMusicSourceSummaryOps", "none");
      $("homeEditMusicSourceTracksSummary").textContent = t("media.manage.source_meta.track_count", {
        count: formatCount(trackList.length),
      });
      $("homeEditMusicSourceTracks").textContent = trackText;
      setHiddenState(tracksWrap, !trackList.length);
      setHiddenState(box, false);
      renderHomeEditCoverImagePreview();
    }

    function syncHomeSourceManagedMetaUi() {
      const isMusic = MUSIC_CATEGORIES.has($("editCategory").value);
      const isSourceManaged = isMusic && isHomeSourceManagedItem();
      setHiddenIfPresent("homeEditMusicMetaFieldsA", isSourceManaged);
      setHiddenIfPresent("homeEditMusicMetaFieldsB", isSourceManaged);
      setHiddenIfPresent("homeEditMusicMetaFieldsC", isSourceManaged);
      if (!isMusic) {
        setDisplayIfPresent("homeEditMusicSourceSummary", "none");
        setDisplayIfPresent("homeEditMusicSourceTracksWrap", "none");
        return;
      }
      renderHomeSourceManagedMetaSummary();
    }

    function syncHomeEditorMusicVisibility() {
      const category = $("editCategory").value;
      const isMusic = MUSIC_CATEGORIES.has(category);
      setHiddenIfPresent("homeEditLinkedArtistWrap", !isMusic);
      setDisplayIfPresent("homeEditMusicOpsRow", isMusic ? "grid" : "none");
      setDisplayIfPresent("homeEditMusicInfoRow", isMusic ? "grid" : "none");
      setDisplayIfPresent("homeEditMusicBox", isMusic ? "block" : "none");
      setDisplayIfPresent("homeEditGoodsBox", isMusic ? "none" : "block");
      setDisplayIfPresent("homeTrackMapBox", "none");
      syncGoodsSpecVisibility(category, {
        poster: "editPosterSpecWrap",
        tshirt: "editTshirtSizeWrap",
        cup: "editCupMaterialWrap",
        hat: "editHatSizeWrap",
      });
      if (isMusic) {
        // format_name stores packaging labels (e.g., "Box Set, Gatefold").
        // Only set a default when the field is empty — never overwrite real packaging values.
        if (!$("editFormatName").value) {
          $("editFormatName").value = category;
        }
      }
      setDisplayMode($("homeEditTrackPanel"), isMusic ? "grid" : "none");
      syncHomeSourceManagedMetaUi();
      renderHomeTrackInfoPanel();
    }

    function goToRegisterFromHome() {
      switchMainTab("register");
      const artist = $("homeArtist").value.trim();
      const itemName = $("homeItemName").value.trim();
      const catalogNo = $("homeCatalogNo").value.trim();
      const barcode = $("homeBarcode").value.trim();

      if (artist) $("queryArtist").value = artist;
      if (itemName) $("queryTitle").value = itemName;
      if (catalogNo) $("queryCatalog").value = catalogNo;
      if (barcode) $("barcodeInput").value = barcode;
      if (artist && !$("quickArtist").value.trim()) $("quickArtist").value = artist;
      if (itemName && !$("quickItemName").value.trim()) {
        $("quickItemName").value = artist ? `${artist} - ${itemName}` : itemName;
      }

      window.scrollTo({ top: 0, behavior: "smooth" });
    }

    function defaultSizeGroupForCategory(category) {
      const c = String(category || "").toUpperCase();
      if (c === "LP") return "LP";
      if (c === "CASSETTE") return "CASSETTE";
      if (c === "8TRACK") return "8TRACK";
      if (c === "REEL_TO_REEL") return "REEL_TO_REEL";
      if (["T_SHIRT", "POSTER", "LIGHT_STICK", "HAT", "BAG", "CUP", "OTHER"].includes(c)) return "GOODS";
      return "STD";
    }

    function metadataCandidateSizeHintTexts(candidate) {
      const hints = [];
      const pushHint = (value) => {
        const text = String(value || "").trim();
        if (text) hints.push(text);
      };
      pushHint(candidate?.format_name);
      pushHint(candidate?.media_type);
      pushHint(candidate?.source_notes);
      const formatItems = Array.isArray(candidate?.format_items) ? candidate.format_items : [];
      formatItems.forEach((item) => {
        if (!item || typeof item !== "object") return;
        pushHint(item.name);
        pushHint(item.text);
        pushHint(item.display);
        if (Array.isArray(item.descriptions)) item.descriptions.forEach(pushHint);
      });
      return hints;
    }

    function inferSizeGroupFromMetadata(category, candidate = null) {
      const base = defaultSizeGroupForCategory(category);
      const hints = metadataCandidateSizeHintTexts(candidate)
        .map((value) => String(value || "").trim().toUpperCase())
        .filter(Boolean);
      if (String(category || "").trim().toUpperCase() === "CASSETTE") return "CASSETTE";
      if (String(category || "").trim().toUpperCase() === "8TRACK") return "8TRACK";
      if (String(category || "").trim().toUpperCase() === "REEL_TO_REEL") return "REEL_TO_REEL";
      if (hints.some((value) => value.includes("CASSETTE") || value.includes("카세트") || value === "MC" || value.includes(" TAPE"))) return "CASSETTE";
      if (hints.some((value) => value.includes("8-TRACK") || value.includes("8 TRACK") || value.includes("8TRACK"))) return "8TRACK";
      if (hints.some((value) => value.includes("REEL-TO-REEL") || value.includes("REEL TO REEL") || value.includes("OPEN REEL"))) return "REEL_TO_REEL";
      if (hints.some((value) => value.includes('10"') || value.includes("10INCH") || value.includes("10-INCH") || value.includes("10인치"))) return "LP10";
      if (hints.some((value) => value.includes('7"') || value.includes("7INCH") || value.includes("7-INCH") || value.includes("7인치"))) return "LP7";
      return base;
    }

    function inferMusicCategoryFromMetadata(candidate = null) {
      const direct = String(candidate?.format_name || "").trim().toUpperCase();
      if (MUSIC_CATEGORIES.has(direct)) return direct;
      const hints = metadataCandidateSizeHintTexts(candidate)
        .map((value) => String(value || "").trim().toUpperCase())
        .filter(Boolean);
      if (hints.some((value) => value.includes("CASSETTE") || value.includes("카세트") || value === "MC" || value.includes(" TAPE"))) return "CASSETTE";
      if (hints.some((value) => value.includes("CD"))) return "CD";
      if (hints.some((value) => value.includes("8-TRACK") || value.includes("8TRACK"))) return "8TRACK";
      if (hints.some((value) => value.includes("REEL"))) return "REEL_TO_REEL";
      if (hints.some((value) => value.includes("DIGITAL") || value.includes("DOWNLOAD") || value.includes("FILE"))) return "DIGITAL";
      return "LP";
    }

    function quickDefaultSizeGroup(category) {
      return defaultSizeGroupForCategory(category);
    }

    function syncQuickSizeGroup() {
      $("quickSizeGroup").value = quickDefaultSizeGroup($("quickCategory").value);
    }

    function resetQuickForm() {
      $("quickCategory").value = "LP";
      $("quickSizeGroup").value = "LP";
      $("quickQuantity").value = "1";
      $("quickItemName").value = "";
      $("quickArtist").value = "";
      $("quickLabelName").value = "";
      $("quickReleasedDate").value = "";
      $("quickSlotId").value = "";
      $("quickCoverImageUrl").value = "";
      $("quickMemoryNote").value = "";
      $("quickDomainCode").value = "";
      $("quickPurchasePrice").value = "";
      $("quickCurrencyCode").value = "KRW";
      $("quickIsSecondHand").checked = true;
      $("quickOpenEditAfterCreate").checked = false;
      setStatus("quickCreateStatus", "ok", "");
    }

    function buildQuickOwnedPayload(opts = {}) {
      const category = $("quickCategory").value;
      const artistName = $("quickArtist").value.trim();
      const itemName = $("quickItemName").value.trim();
      if (!artistName) {
        throw new Error(t("media.register.direct.error.artist_required"));
      }
      if (!itemName) {
        throw new Error(t("media.register.direct.error.item_required"));
      }
      const linkedAlbumMasterId = Number(opts.linkedAlbumMasterId || 0);
      const purchasePrice = normalizePurchasePriceOrNull($("quickPurchasePrice").value);
      const sizeGroup = String($("quickSizeGroup").value || defaultSizeGroupForCategory(category)).trim().toUpperCase();

      const payload = {
        category,
        size_group: sizeGroup,
        preferred_storage_size_group: sizeGroup,
        quantity: Math.max(1, Number($("quickQuantity").value || 1)),
        is_second_hand: $("quickIsSecondHand").checked,
        status: "IN_COLLECTION",
        signature_type: "NONE",
        source_code: null,
        source_external_id: null,
        domain_code: $("quickDomainCode").value || null,
        release_type: null,
        linked_album_master_id: linkedAlbumMasterId > 0 ? linkedAlbumMasterId : null,
        linked_artist_name: null,
        purchase_source: null,
        purchase_price: purchasePrice,
        currency_code: purchasePrice !== null ? normalizeCurrencyCodeOrNull($("quickCurrencyCode").value, "KRW") : null,
        memory_note: $("quickMemoryNote").value.trim() || null,
        item_name_override: itemName,
        storage_slot_id: $("quickSlotId").value ? Number($("quickSlotId").value) : null
      };

      if (MUSIC_CATEGORIES.has(category)) {
        payload.music_detail = {
          format_name: category,
          is_promotional_not_for_sale: false,
          artist_or_brand: artistName,
          released_date: $("quickReleasedDate").value.trim() || null,
          label_name: $("quickLabelName").value.trim() || null,
          cover_image_url: $("quickCoverImageUrl").value.trim() || null,
          track_list: []
        };
      }
      return payload;
    }

    async function createQuickAutoMaster(ownedItemId) {
      const res = await fetch(`/owned-items/${ownedItemId}/auto-master`, { method: "POST" });
      const data = await safeJson(res);
      if (!res.ok) throw new Error(data.detail || t("media.register.direct.status.auto_master_create_failed"));
      return data;
    }

    function duplicateMasterLine(row) {
      const source = String(row?.source_code || "-").trim();
      const sourceMasterId = String(row?.source_master_id || "-").trim();
      const title = String(row?.title || "-").trim();
      const artist = String(row?.artist_or_brand || "-").trim();
      const year = row?.release_year ?? "-";
      const memberCount = Number(row?.member_count || 0);
      const mid = Number(row?.album_master_id || 0);
      return `${mid} | ${source}#${sourceMasterId} | ${artist} - ${title} | year:${year} | members:${memberCount}`;
    }

    async function maybeMergeDuplicateMastersForCreatedItem(linkedAlbumMasterId, statusBoxId) {
      const albumMasterId = Number(linkedAlbumMasterId || 0);
      if (!albumMasterId) return [];
      const notices = [];
      try {
        const dupRes = await fetch(`/album-masters/${albumMasterId}/duplicates?limit=10`);
        const dupData = await safeJson(dupRes);
        if (!dupRes.ok) throw new Error(dupData.detail || t("media.register.direct.duplicate.lookup_failed"));

        const duplicates = Array.isArray(dupData.duplicates) ? dupData.duplicates : [];
        if (!duplicates.length) return notices;

        const suggestedTargetId = Number(
          dupData.suggested_target_album_master_id || duplicates[0]?.album_master_id || 0
        );
        const previewText = duplicates.slice(0, 6).map((row) => duplicateMasterLine(row)).join("\n");
        const confirmText = t("media.register.direct.duplicate.confirm", {
          count: countWithUnit(duplicates.length),
          preview: previewText,
          target_id: suggestedTargetId || "-",
        });
        const shouldMerge = window.confirm(confirmText);
        if (!shouldMerge) {
          notices.push(t("media.register.direct.duplicate.deferred", {
            count: countWithUnit(duplicates.length),
          }));
          return notices;
        }
        if (!suggestedTargetId) {
          notices.push(t("media.register.direct.duplicate.no_target"));
          return notices;
        }

        setStatus(statusBoxId, "ok", t("media.register.direct.duplicate.merging", {
          source_id: albumMasterId,
          target_id: suggestedTargetId,
        }));
        const mergeRes = await fetch(`/album-masters/${albumMasterId}/merge`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ target_album_master_id: suggestedTargetId }),
        });
        const mergeData = await safeJson(mergeRes);
        if (!mergeRes.ok) throw new Error(mergeData.detail || t("media.register.direct.duplicate.merge_failed"));
        notices.push(t("media.register.direct.duplicate.merge_complete", {
          source_id: albumMasterId,
          target_id: mergeData.target_album_master_id,
          moved_count: countWithUnit(Number(mergeData.moved_member_count || 0)),
        }));
      } catch (err) {
        notices.push(`${t("media.register.direct.duplicate.merge_failed")}: ${err.message}`);
      }
      return notices;
    }

    async function createQuickOwnedItem() {
      try {
        const category = $("quickCategory").value;
        const isMusic = MUSIC_CATEGORIES.has(category);
        let linkedAlbumMasterId = null;
        let autoCreateMaster = false;

        if (isMusic) {
          const chooseExisting = window.confirm(t("media.register.direct.master_link.confirm"));
          if (chooseExisting) {
            const raw = window.prompt(t("media.register.direct.master_link.prompt"));
            if (raw === null) {
              setStatus("quickCreateStatus", "ok", t("media.register.direct.status.cancelled"));
              return;
            }
            const parsed = Number(String(raw).trim());
            if (!Number.isInteger(parsed) || parsed <= 0) {
              setStatus("quickCreateStatus", "err", t("media.register.direct.status.invalid_master_id"));
              return;
            }
            linkedAlbumMasterId = parsed;
          } else {
            autoCreateMaster = true;
          }
        }

        const payload = buildQuickOwnedPayload({ linkedAlbumMasterId });
        if (!confirmSlotMismatchById(payload.storage_slot_id, [payload], t("media.register.direct.action.save"))) {
          setStatus("quickCreateStatus", "ok", t("media.register.direct.status.cancelled"));
          return;
        }
        setStatus("quickCreateStatus", "ok", t("media.register.direct.status.saving"));
        const res = await fetch("/owned-items", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.register.direct.status.failed"));

        const notices = Array.isArray(data.notices) ? data.notices : [];
        const extraMessages = [];
        let resolvedMasterId = Number(data.linked_album_master_id || 0);
        if (autoCreateMaster && isMusic) {
          try {
            const master = await createQuickAutoMaster(Number(data.owned_item_id));
            resolvedMasterId = Number(master.album_master_id || resolvedMasterId || 0);
            extraMessages.push(
              t("media.register.direct.status.auto_master_created", {
                id: master.album_master_id,
                source: master.source_code,
                source_id: master.source_master_id,
              })
            );
            const masterNotices = Array.isArray(master.notices) ? master.notices : [];
            for (const msg of masterNotices) {
              extraMessages.push(msg);
            }
          } catch (err) {
            extraMessages.push(t("media.register.direct.status.auto_master_failed", { message: err.message }));
          }
        }
        const mergeNotices = await maybeMergeDuplicateMastersForCreatedItem(resolvedMasterId, "quickCreateStatus");
        for (const msg of mergeNotices) {
          extraMessages.push(msg);
        }
        setStatus(
          "quickCreateStatus",
          "ok",
          t("media.register.direct.status.done", {
            owned_id: data.owned_item_id,
            label_id: data.label_id,
            details: (notices.length || extraMessages.length) ? `\n${[...notices, ...extraMessages].map((v) => `- ${v}`).join("\n")}` : "",
          })
        );
        await loadHomeDashboard();
        await homeSearchOwnedItems({ resetPage: true, suppressEmptyCta: true });

        if ($("quickOpenEditAfterCreate").checked) {
          openAdminConsole("media", { remember: false, mediaMode: "manage" });
          const createdOwnedItemId = Number(data.owned_item_id || 0);
          const masterId = resolveHomeManageMasterIdForOwnedItem(createdOwnedItemId, {
            masterId: Number(resolvedMasterId || data.linked_album_master_id || data.album_master_id || 0),
          });
          await openMediaSearchDetailManage(masterId, createdOwnedItemId);
        } else {
          $("quickItemName").value = "";
          $("quickMemoryNote").value = "";
        }
      } catch (err) {
        setStatus("quickCreateStatus", "err", err.message);
      }
    }

    function showHomeSearchView() {
      setDisplayIfPresent("homeSearchCard", "block");
      renderAdminManageSurface();
      if (currentShellMode() === "admin") {
        openAdminConsole("media", { remember: false, mediaMode: "search" });
      }
    }

    function mountHomeMasterInlineEditor() {
      const host = $("homeMasterInlineEditorHost");
      if (!host) return;
      const blocks = [
        $("homeEditMusicProductSplit"),
        $("homeEditGoodsBox"),
        $("homeEditorActionBlock"),
        $("homeProductRelationSection"),
        $("homeProductLinkedGoodsSection"),
      ].filter((node) => node);
      for (const block of blocks) {
        if (block.parentElement !== host) {
          host.appendChild(block);
        }
      }
    }

    function parkHomeMasterInlineEditor() {
      const host = $("homeMasterInlineEditorHost");
      const parking = $("homeMasterInlineEditorParking");
      if (!host || !parking) return;
      if (host.parentElement !== parking) {
        parking.appendChild(host);
      }
      setDisplayMode(host, "none");
    }

    function mountHomeMasterActionBlocks() {
      // DOM is statically structured since v3 restructuring; no-op.
      const mount = $("homeMasterActionMount");
      const addBlock = $("homeMasterAddBlock");
      const metaBlock = $("homeEditorMetaFetchBlock");
      if (!mount || !addBlock || !metaBlock) return;
      if (addBlock.parentElement !== mount) {
        mount.appendChild(addBlock);
      }
      if (metaBlock.parentElement !== mount) {
        mount.appendChild(metaBlock);
      }
    }

    function findHomeRelatedItemElement(ownedItemId) {
      const targetId = Number(ownedItemId || 0);
      if (targetId <= 0) return null;
      return document.querySelector(`.home-related-item[data-owned-id="${targetId}"]`);
    }

    function findHomeInlineEditorMountElement(ownedItemId) {
      const targetId = Number(ownedItemId || 0);
      if (targetId <= 0) return $("homeEditorStandaloneMount");
      const relatedItem = document.querySelector(`.home-related-item[data-owned-id="${targetId}"]`);
      if (relatedItem) {
        const relatedSection = relatedItem.closest("#homeMasterSummarySection");
        if (!relatedSection || !isElementDisplayNone(relatedSection)) return relatedItem;
      }
      const locationItem = document.querySelector(`.home-location-slot-item[data-slot-owned-id="${targetId}"]`);
      if (locationItem) return locationItem;
      return $("homeEditorStandaloneMount");
    }

    function syncHomeMasterInlineEditor() {
      const host = $("homeMasterInlineEditorHost");
      const parking = $("homeMasterInlineEditorParking");
      const standaloneSection = $("manageSection1Product");
      if (!host || !parking) return;
      const ownedItemId = Number(homeSelectedItemId || 0);
      if (ownedItemId <= 0 || homeInlineEditorCollapsed) {
        if (host.parentElement !== parking) {
          parking.appendChild(host);
        }
        setDisplayMode(host, "none");
        if (standaloneSection) standaloneSection.hidden = true;
        return;
      }
      const mountTarget = findHomeInlineEditorMountElement(ownedItemId);
      if (!mountTarget) {
        if (host.parentElement !== parking) {
          parking.appendChild(host);
        }
        setDisplayMode(host, "none");
        if (standaloneSection) standaloneSection.hidden = true;
        return;
      }
      const standaloneMount = $("homeEditorStandaloneMount");
      if (standaloneSection) standaloneSection.hidden = (mountTarget !== standaloneMount);
      if (host.parentElement !== mountTarget) {
        mountTarget.appendChild(host);
      }
      setDisplayMode(host, "grid");
    }

    function hasHomeMasterLookupSelection() {
      const ownedItemId = Number(homeSelectedItemId || $("editOwnedId")?.value || 0);
      const masterId = Number(homeSelectedMasterId || $("editLinkedAlbumMasterId")?.value || 0);
      return ownedItemId > 0 || masterId > 0;
    }

    function homeMasterMetaPlaceholderText() {
      return hasHomeMasterLookupSelection()
        ? t("media.manage.master.placeholder.pending_meta")
        : t("media.manage.master.placeholder.empty_meta");
    }

    function homeMasterRelatedPlaceholderHtml() {
      return hasHomeMasterLookupSelection()
        ? `<div class='muted'>${escapeHtml(t("media.manage.master.placeholder.pending_related"))}</div>`
        : `<div class='muted'>${escapeHtml(t("media.manage.master.placeholder.empty_related"))}</div>`;
    }

    function homeMasterVariantPlaceholderText() {
      return hasHomeMasterLookupSelection()
        ? t("media.manage.master.placeholder.pending_versions")
        : t("media.manage.master.placeholder.empty_versions");
    }

    function syncHomeMasterLookupPromptState() {
      const isPending = !homeMasterInfo && hasHomeMasterLookupSelection();
      $("homeMasterRelatedList")?.classList.toggle("home-master-lookup-pending", isPending);
      $("homeMasterAddBlock")?.classList.toggle("home-master-lookup-pending", isPending);
    }

    function setHomeMasterLookupResultsVisible(visible, opts = {}) {
      const details = $("homeMasterLookupResultsDetails");
      if (!details) return;
      setDisplayMode(details, visible ? "block" : "none");
      if (visible) details.open = opts.open !== false;
    }

    function resolveHomeLinkedCollectiblesMasterId() {
      return Number(
        homeMasterInfo?.album_master_id ||
        $("editLinkedAlbumMasterId")?.value ||
        homeSelectedMasterId ||
        0
      );
    }

    function renderHomeLinkedCollectiblesSection() {
      const masterId = resolveHomeLinkedCollectiblesMasterId();
      const collectibles = Array.isArray(homeMasterInfo?.collectibles)
        ? homeMasterInfo.collectibles
        : homeLinkedCollectibles;
      // 마스터 연계 수집품 섹션 (2-3에 위치)
      if (masterId <= 0) {
        setHtmlIfPresent("homeMasterGoodsList", "");
        const detailsEl = $("homeLinkedGoodsPanelDetails");
        if (detailsEl) {
          detailsEl.hidden = true;
          detailsEl.classList.add("u-hidden-initial");
        }
        return;
      }
      // 마스터 있으면 details 표시 (기본 접힘 상태 유지)
      const detailsEl = $("homeLinkedGoodsPanelDetails");
      if (detailsEl) {
        detailsEl.hidden = false;
        detailsEl.classList.remove("u-hidden-initial");
      }
      if (!Array.isArray(homeMasterInfo?.collectibles) && homeLinkedCollectiblesLoading) {
        setHtmlIfPresent("homeMasterGoodsList", `<div class='muted'>${escapeHtml(t("media.manage.collectibles.state.loading"))}</div>`);
        return;
      }
      setHtmlIfPresent(
        "homeMasterGoodsList",
        collectibles.length
          ? collectibles.map((row) => homeMasterCollectibleItemHtml(row)).join("")
          : `<div class='muted mini u-mt-4'>마스터와 연계된 수집품이 없습니다.</div>`
      );
    }

    function resetHomeMasterLookupUi(opts = {}) {
      const clearInputs = Boolean(opts.clearInputs);
      homeMasterInfo = null;
      renderHomeRelatedVersions();
      resetHomeMasterAddPager({ clearInputs });
      renderHomeMasterAddVariants([], homeMasterVariantPlaceholderText());
      setHomeMasterLookupResultsVisible(false, { open: false });
      setStatus("homeMasterStatus", "ok", "");
      setStatus("homeMasterAddStatus", "ok", "");
    }

    function syncHomeMasterSortArtistEditor() {
      const input = $("homeMasterSortArtistName");
      const saveBtn = $("homeMasterSortArtistSaveBtn");
      if (!input || !saveBtn) return;
      const masterId = Number(homeMasterInfo?.album_master_id || homeSelectedMasterId || 0);
      if (masterId <= 0) {
        input.value = "";
        saveBtn.disabled = true;
        setStatus("homeMasterSortArtistStatus", "ok", "");
        return;
      }
      input.value = String(homeMasterInfo?.sort_artist_name || "").trim();
      saveBtn.disabled = false;
    }

    function syncHomeMasterCorrectionEditor() {
      const unifiedDetails = $("homeEditUnifiedDetails");
      const masterEditDetails = $("homeMasterEditDetails");
      const releaseYearInput = $("homeMasterCorrectionReleaseYear");
      const domainCodeInput = $("homeMasterCorrectionDomainCode");
      const noteInput = $("homeMasterCorrectionNote");
      const titleInput = $("homeMasterCorrectionTitle");
      const artistInput = $("homeMasterCorrectionArtist");
      const saveBtn = $("homeMasterCorrectionSaveBtn");
      const sourceHint = $("homeMasterCorrectionSourceHint");
      if (!releaseYearInput || !domainCodeInput || !noteInput || !saveBtn || !sourceHint) return;
      const masterId = Number(homeMasterInfo?.album_master_id || homeSelectedMasterId || 0);
      if (masterId <= 0) {
        if (unifiedDetails) unifiedDetails.classList.add("u-hidden-initial");
        if (masterEditDetails) masterEditDetails.classList.add("u-hidden-initial");
        releaseYearInput.value = "";
        domainCodeInput.value = "";
        noteInput.value = "";
        if (titleInput) titleInput.value = "";
        if (artistInput) artistInput.value = "";
        const genresInput = $("homeMasterCorrectionGenres");
        const stylesInput = $("homeMasterCorrectionStyles");
        if (genresInput) genresInput.value = "";
        if (stylesInput) stylesInput.value = "";
        const releaseTypeInput = $("homeMasterCorrectionReleaseType");
        if (releaseTypeInput) releaseTypeInput.value = "";
        saveBtn.disabled = true;
        sourceHint.textContent = t("media.manage.master.correction.source_hint_pending");
        setStatus("homeMasterCorrectionStatus", "ok", "");
        const spMatchId = $("homeMasterSpotifyMatchId");
        if (spMatchId) spMatchId.value = "";
        setStatus("homeMasterSpotifyMatchStatus", "ok", "");
        renderHomeMasterReviewSection(null);
        return;
      }
      if (unifiedDetails) unifiedDetails.classList.remove("u-hidden-initial");
      if (masterEditDetails) masterEditDetails.classList.remove("u-hidden-initial");
      releaseYearInput.value = String(
        homeMasterInfo?.override_release_year
        ?? homeMasterInfo?.release_year
        ?? ""
      ).trim();
      domainCodeInput.value = String(
        homeMasterInfo?.override_domain_code
        || homeMasterInfo?.domain_code
        || ""
      ).trim().toUpperCase();
      noteInput.value = String(homeMasterInfo?.override_note || "").trim();
      if (titleInput) titleInput.value = String(homeMasterInfo?.override_title || homeMasterInfo?.title || "").trim();
      if (artistInput) artistInput.value = String(homeMasterInfo?.override_artist_or_brand || homeMasterInfo?.artist_or_brand || "").trim();
      const genresInput = $("homeMasterCorrectionGenres");
      const stylesInput = $("homeMasterCorrectionStyles");
      if (genresInput) genresInput.value = joinCommaList(homeMasterInfo?.genres || []);
      if (stylesInput) stylesInput.value = joinCommaList(homeMasterInfo?.styles || []);
      const releaseTypeInput = $("homeMasterCorrectionReleaseType");
      if (releaseTypeInput) releaseTypeInput.value = String(homeMasterInfo?.release_type || "").trim().toUpperCase();
      const spMatchId = $("homeMasterSpotifyMatchId");
      if (spMatchId) spMatchId.value = String(homeMasterInfo?.spotify_album_id || "").trim();
      setStatus("homeMasterSpotifyMatchStatus", "ok", "");
      const sourceReleaseYear = homeMasterInfo?.source_release_year ?? homeMasterInfo?.release_year ?? null;
      const sourceDomainCode = String(
        homeMasterInfo?.source_domain_code
        || homeMasterInfo?.domain_code
        || ""
      ).trim().toUpperCase();
      sourceHint.textContent = t("media.manage.master.correction.source_hint", {
        release_year: sourceReleaseYear || "-",
        domain: sourceDomainCode ? dashboardDomainLabel(sourceDomainCode) : t("common.unspecified"),
      });
      saveBtn.disabled = false;
      renderHomeMasterReviewSection(homeMasterInfo);
    }

    function syncHomeRelatedSelectedMetaPreview() {
      const ownedItemId = Number($("editOwnedId").value || homeSelectedItemId || 0);
      const labelName = $("editLabelName").value.trim() || "-";
      const catalogNo = $("editCatalogNo").value.trim() || "-";
      const barcode = $("editBarcode").value.trim();
      const coverMeta = $("homeEditCoverCatalogMeta");
      if (coverMeta) {
        coverMeta.textContent = labelName === "-" && catalogNo === "-" && !barcode
          ? t("media.manage.product.state.no_catalog_meta")
          : `${labelName !== "-" ? `${labelName} / ` : ""}${catalogNo}${barcode ? ` (${barcode})` : ""}`;
      }
      if (ownedItemId <= 0) return;
      const labelCatText = `label/cat#: ${labelName} / ${catalogNo}${barcode ? ` (${barcode})` : ""}`;
      const target = document.querySelector(`.home-related-item[data-owned-id="${ownedItemId}"] [data-role="label-cat"]`);
      if (target) target.textContent = labelCatText;
      const items = Array.isArray(homeMasterInfo?.items) ? homeMasterInfo.items : [];
      const row = items.find((item) => Number(item?.id) === ownedItemId);
      if (row) {
        row.label_name = $("editLabelName").value.trim() || null;
        row.catalog_no = $("editCatalogNo").value.trim() || null;
        row.barcode = $("editBarcode").value.trim() || null;
      }
    }

    function showHomeEditView() {
      setDisplayIfPresent("homeSearchCard", "block");
      mountHomeMasterActionBlocks();
      mountHomeMasterInlineEditor();
      syncHomeMasterInlineEditor();
      renderAdminManageSurface();
      if (currentShellMode() === "admin") {
        openAdminConsole("media", { remember: false, mediaMode: "manage" });
      }
      $("homeEditorCard").scrollIntoView({ behavior: "auto", block: "start" });
    }

    function isActiveHomeEditRequest(requestSeq) {
      return Number(requestSeq || 0) > 0 && Number(requestSeq) === Number(homeEditRequestSeq || 0);
    }

    function renderHomePagination() {
      const pagers = [$("homeSearchPager"), $("homeSearchPagerBottom")].filter(Boolean);
      if (!pagers.length) return;

      if (homeSearchTotalCount <= 0) {
        pagers.forEach((pager) => { pager.innerHTML = ""; });
        return;
      }

      const totalPages = Math.max(1, Math.ceil(homeSearchTotalCount / homeSearchPageSize));
      if (totalPages <= 1) {
        pagers.forEach((pager) => { pager.innerHTML = ""; });
        return;
      }
      const tokens = buildOperatorFeedPagerTokens(homeSearchPage, totalPages);
      const markup = [
        `<button class="operator-feed-pagebtn" type="button" data-home-search-page="${homeSearchPage - 1}" ${homeSearchPage <= 1 ? "disabled" : ""}>&lt;</button>`,
        ...tokens.map((token) => token === "gap"
          ? `<span class="operator-feed-pagegap">…</span>`
          : `<button class="operator-feed-pagebtn ${token === homeSearchPage ? "active" : ""}" type="button" data-home-search-page="${token}">${token}</button>`),
        `<button class="operator-feed-pagebtn" type="button" data-home-search-page="${homeSearchPage + 1}" ${homeSearchPage >= totalPages ? "disabled" : ""}>&gt;</button>`,
      ].join("");
      pagers.forEach((pager) => { pager.innerHTML = markup; });
    }

    function initSearchOptionsCheckboxes() {
      const packagingContainer = $("homePackagingList");
      if (packagingContainer) {
        const allPackaging = new Set();
        for (const mediaType in PACKAGING_OPTIONS_BY_MEDIA) {
          var _mt = mediaType;
          if (_mt === "CDr" || _mt === "SACD") _mt = "CD";
          if (_mt === "All Media") _mt = "VINYL";
          (PACKAGING_OPTIONS_BY_MEDIA[_mt] || []).forEach(opt => allPackaging.add(opt));
        }
        let html = "";
        Array.from(allPackaging).sort().forEach(opt => {
          html += `<label data-packaging-tip="${escapeHtml(opt)}"><input type="checkbox" value="${escapeHtml(opt)}" /><span>${escapeHtml(opt)}</span></label>`;
        });
        packagingContainer.innerHTML = html;
        if (typeof applyFieldHelpTooltips === "function") applyFieldHelpTooltips(packagingContainer);
        packagingContainer.querySelectorAll('input[type="checkbox"]').forEach(cb => {
          cb.addEventListener("change", () => homeSearchOwnedItems({ resetPage: true }));
        });
      }

      const contentsContainer = $("homePackageContentsList");
      if (contentsContainer) {
        const allContents = [
          "Inner Sleeve",
          "Insert",
          "Leaflet",
          "Booklet",
          "Photo Book",
          "Mini Poster / Tabloid",
          "Postcard",
          "Sticker",
          "Bookmark",
          "Lenticular / Hologram Card",
          "Photo Card",
          "Film Cut",
          "Warranty Card",
          "Entry Form"
        ];
        let html = "";
        const _SEARCH_PKG_KEY = {
          "Inner Sleeve": "inner_sleeve", "Insert": "insert", "Leaflet": "leaflet",
          "Booklet": "booklet", "Photo Book": "photo_book", "Mini Poster / Tabloid": "mini_poster",
          "Postcard": "postcard", "Sticker": "sticker", "Bookmark": "bookmark",
          "Lenticular / Hologram Card": "lenticular", "Photo Card": "photo_card",
          "Film Cut": "film_cut", "Warranty Card": "warranty_card", "Entry Form": "entry_form",
        };
        allContents.forEach(opt => {
          const _k = _SEARCH_PKG_KEY[opt];
          const _a = _k ? ` data-i18n-title="media.manage.pkg_contents.tip.${_k}"` : "";
          html += `<label${_a}><input type="checkbox" value="${escapeHtml(opt)}" /><span>${escapeHtml(opt)}</span></label>`;
        });
        contentsContainer.innerHTML = html;
        if (typeof applyFieldHelpTooltips === "function") applyFieldHelpTooltips(contentsContainer);
        contentsContainer.querySelectorAll('input[type="checkbox"]').forEach(cb => {
          cb.addEventListener("change", () => homeSearchOwnedItems({ resetPage: true }));
        });
      }
    }

    function resetHomeSearchForm() {
      $("homeArtist").value = "";
      $("homeItemName").value = "";
      $("homeCatalogNo").value = "";
      $("homeBarcode").value = "";
      $("homeReleaseYear").value = "";
      $("homeSigDirect").checked = false;
      $("homeSigPurchase").checked = false;
      $("homeSortMode").value = "CREATED_DESC";
      $("homePageSize").value = "30";
      $("homeMasterId").value = "";
      $("homeItemId").value = "";
      $("homePackagingList").querySelectorAll('input[type="checkbox"]').forEach(cb => { cb.checked = false; });
      $("homePackageContentsList").querySelectorAll('input[type="checkbox"]').forEach(cb => { cb.checked = false; });
      $("homeLimitEd").checked = false;
      $("homeNewProduct").checked = false;
      $("homePromo").checked = false;
      $("homeSearchAdvancedDetails").open = false;
      homeSearchPageSize = 30;
      homeSearchPage = 1;
      homeSelectedMasterId = null;
      homeSearchTotalCount = 0;
      homeSearchResults = [];
      syncHomeMasterDeleteUi();
      setStatus("homeSearchStatus", "ok", "");
      setDisplayIfPresent("homeNoResultCta", "none");
      $("homeSearchResults").innerHTML = "";
      $("homeSearchCount").textContent = t("common.count.zero_items");
      renderHomePagination();
    }

    function clearHomeEditor() {
      homeSelectedMasterId = null;
      homeSelectedItemId = null;
      // URL hash 클리어
      if (window.location.hash.startsWith("#item/")) history.pushState(null, "", location.pathname);
      homeInlineEditorCollapsed = false;
      homeSelectedSourceCode = null;
      homeSelectedSourceExternalId = null;
      homeEditShelfItems = [];
      homeEditShelfSelectedId = null;
      homeEditShelfPrevId = null;
      homeEditShelfNextId = null;
      homeLocationSlotItems = [];
      homeLocationSlotId = null;
      homeLocationSlotLoading = false;
      homeMasterInfo = null;
      homeLinkedCollectibles = [];
      homeLinkedCollectiblesLoading = false;
      homeProductLinkedGoods = [];
      homeProductLinkedGoodsLoading = false;
      homeOwnedItemRelationView = null;
      homeOwnedItemRelationMasterEntries = [];
      homeOwnedItemEditableRelations = [];
      if ($("homeProductRelationSection")) $("homeProductRelationSection").open = false;
      homeLoadedMusicDetail = null;
      clearHomeMetaCandidates();
      syncHomeLinkedSourceText();
      syncHomeMasterDeleteUi();
      setTextIfPresent("homeEditorSelectedLabel", t("media.manage.selected_label"));
      setHtmlIfPresent("homeAcquisitionSourceInfo", "");
      setDisplayIfPresent("homeAcquisitionSourceInfo", "none");
      setHtmlIfPresent("homeAcquisitionSourceLink", "");
      setDisplayIfPresent("homeAcquisitionSourceLink", "none");
      renderHomeCollectorSummary(null);
      setHtmlIfPresent("homeEditMusicSourceSummaryMain", `<span class='operator-meta-value'>-</span>`);
      setHtmlIfPresent("homeEditMusicSourceSummarySub", `<span class='operator-meta-value'>-</span>`);
      setHtmlIfPresent("homeEditMusicSourceSummaryExtra", "-");
      setHtmlIfPresent("homeEditMusicSourceSummaryOps", "-");
      setDisplayIfPresent("homeEditMusicSourceSummaryExtra", "none");
      setDisplayIfPresent("homeEditMusicSourceSummaryOps", "none");
      setTextIfPresent("homeEditMusicSourceTracksSummary", t("media.manage.source_meta.tracks_summary"));
      setTextIfPresent("homeEditMusicSourceTracks", "-");
      setHtmlIfPresent("homeEditCoverImagePreview", `<span class='mini'>${escapeHtml(t("media.manage.product.state.no_cover"))}</span>`);
      setTextIfPresent("homeEditCoverCatalogMeta", t("media.manage.product.state.no_catalog_meta"));
      if ($("homeEditCoverSourceLink")) {
        setHtmlIfPresent("homeEditCoverSourceLink", "");
        setDisplayIfPresent("homeEditCoverSourceLink", "none");
      }
      if ($("homeEditCoverImagePaste")) $("homeEditCoverImagePaste").value = "";
      if ($("homeEditCoverImageFile")) $("homeEditCoverImageFile").value = "";
      setTextIfPresent("homeEditTrackInfoSummary", t("media.manage.product.field.track_info.empty"));
      setHtmlIfPresent("homeEditTrackInfoList", `<div class='muted'>${escapeHtml(t("media.manage.product.field.track_info.empty"))}</div>`);
      setDisplayIfPresent("homeEditTrackPanel", "none");
      // homeEditTrackPanel display is controlled by syncHomeEditorMusicVisibility
      setDisplayIfPresent("homeEditMusicSourceSummary", "none");
      setDisplayIfPresent("homeEditMusicSourceTracksWrap", "none");
      syncHomeMasterInlineEditor();
      $("editReleaseType").value = "";
      $("editMediaType").value = "";
      _syncVinylOnlyFields();
      $("editReleasedDate").value = "";
      $("editDiscCount").value = "";
      $("editSpeedRpm").value = "";
      if ($("editDiscType")) $("editDiscType").value = "";
      _loadPackageContents("");
      if ($("editIsLimitedEdition")) $("editIsLimitedEdition").checked = false;
      if ($("editEditionNumber")) $("editEditionNumber").value = "";
      setHiddenIfPresent("editEditionNumberWrap", true);
      $("editRunoutMatrix").value = "";
      $("editPressingCountry").value = "";
      $("editHasObi").checked = false;
      $("editGoodsImageUrls").value = "";
      $("editPosterStorageSpec").value = "";
      $("editTshirtSize").value = "";
      $("editCupMaterial").value = "";
      $("editHatSize").value = "";
      if ($("editLinkedAlbumMasterId")) $("editLinkedAlbumMasterId").value = "";
      $("editLinkedArtistName").value = "";
      $("editPurchasePrice").value = "";
      $("editCurrencyCode").value = "KRW";
      setHtmlIfPresent("homeEditShelfTrack", `<div class='shelf-empty'>${escapeHtml(t("media.manage.shelf.state.no_selected_item"))}</div>`);
      setTextIfPresent("homeEditShelfCenterText", t("media.manage.location.center"));
      setTextIfPresent("homeLocationInfo", t("media.manage.location.summary.placeholder"));
      setHtmlIfPresent("homeLocationSlotList", `<div class='muted'>${escapeHtml(t("media.manage.location.state.no_slot_info"))}</div>`);
      setStatus("homeLocationSlotStatus", "ok", "");
      setTextIfPresent("homeMasterMeta", t("media.manage.master.placeholder.empty_meta"));
      setHtmlIfPresent("homeMasterRelatedList", `<div class='muted'>${escapeHtml(t("media.manage.master.placeholder.empty_related"))}</div>`);
      setHtmlIfPresent("homeMasterGoodsList", `<div class='muted'>${escapeHtml(t("media.manage.collectibles.state.empty"))}</div>`);
      setDisplayIfPresent("homeMasterSummarySection", "block");
      setDisplayIfPresent("homeMasterGoodsSection", "none");
      syncHomeMasterSortArtistEditor();
      $("homeLinkedGoodsCategory").value = "POSTER";
      $("homeLinkedGoodsName").value = "";
      $("homeLinkedGoodsSizeGroup").value = "GOODS";
      $("homeLinkedGoodsQuantity").value = "1";
      $("homeLinkedGoodsPurchaseSource").value = "";
      clearHomeLinkedGoodsImages();
      $("homeLinkedPosterStorageSpec").value = "";
      $("homeLinkedTshirtSize").value = "";
      $("homeLinkedCupMaterial").value = "";
      $("homeLinkedHatSize").value = "";
      syncHomeLinkedGoodsSpecVisibility();
      syncHomeLinkedGoodsMasterInfo();
      setStatus("homeLinkedGoodsStatus", "ok", "");
      homeMasterAddVariants = [];
      resetHomeMasterAddPager({ clearInputs: true });
      renderHomeMasterAddVariants([], t("media.manage.master.add.prompt_select"));
      setHomeMasterLookupResultsVisible(false, { open: false });
      setStatus("homeMasterAddStatus", "ok", "");
      $("homeTrackMapDir").value = "";
      $("homeTrackMapReplace").checked = true;
      homeAudioDirectoryMappings = [];
      homeAudioDirectoryFiles = [];
      renderHomeTrackMapBody([]);
      renderHomeTrackFileList([], null);
      setStatus("homeTrackMapStatus", "ok", "");
      setStatus("homeEditShelfStatus", "ok", "");
      setStatus("homeMasterStatus", "ok", "");
      setStatus("homeEditStatus", "ok", "");
      resetHomeOwnedItemRelationUi();
      renderHomeSearchResults(homeSearchResults);
      showHomeSearchView();
    }

    function syncHomeMasterDeleteUi() {
      const hasMaster = Number(homeSelectedMasterId || 0) > 0;
      $("homeMasterDeleteBtn").disabled = !hasMaster;
      if (!hasMaster) {
        const confirmPanel = $("homeMasterDeleteConfirm");
        if (confirmPanel) confirmPanel.style.display = "none";
        $("homeMasterDeleteCascade").checked = true;
      }
      const histDetails = $("homeMasterHistoryDetails");
      if (histDetails) {
        const newId = String(homeSelectedMasterId || "");
        if (histDetails.dataset.historyId !== newId) {
          histDetails.dataset.historyId = newId;
          histDetails.open = false;
          const body = histDetails.querySelector(".inline-entity-history-body");
          if (body) body.innerHTML = "";
          _inlineHistoryCache.delete(`album_master:${newId}`);
        }
      }
    }

    function resolveHomeLinkedGoodsMasterContext() {
      const fieldMasterId = Number($("editLinkedAlbumMasterId")?.value || 0);
      const infoMasterId = Number(homeMasterInfo?.album_master_id || 0);
      const masterId = Number(homeSelectedMasterId || fieldMasterId || infoMasterId || 0);
      const masterRow = homeSearchResults.find((row) => Number(row.id) === masterId) || null;
      const title = masterRow
        ? resolveAlbumMasterName(masterRow)
        : String(homeMasterInfo?.title || "").trim();
      const artist = masterRow
        ? String(masterRow.artist_or_brand || "").trim()
        : String(homeMasterInfo?.artist_or_brand || $("editArtistName")?.value || "").trim();
      return { masterId, title, artist };
    }

    function syncHomeLinkedGoodsMasterInfo() {
      const el = $("homeLinkedGoodsMasterInfo");
      if (!el) return;
      const { masterId, title, artist } = resolveHomeLinkedGoodsMasterContext();
      if (masterId > 0) {
        const bits = [
          title || `album_master_id=${masterId}`,
          `album_master_id=${masterId}`,
          artist ? `${t("media.search.field.artist.label")} ${artist}` : null
        ].filter(Boolean);
        el.textContent = bits.join(" | ");
        return;
      }
      el.textContent = t("media.manage.collectibles.state.no_master_selected");
    }

    function resolveHomeMasterContext(masterIdArg = null) {
      const supportedVariantSources = ["DISCOGS", "MANIADB"];
      const preferredMasterId = Number(masterIdArg || 0);
      const fieldMasterId = Number($("editLinkedAlbumMasterId")?.value || 0);
      const infoMasterId = Number(homeMasterInfo?.album_master_id || 0);
      const masterId = Number(preferredMasterId || homeSelectedMasterId || infoMasterId || fieldMasterId || 0);
      const masterRow = null;
      const contextCandidates = [];
      const currentItemSource = String(homeSelectedSourceCode || "").trim().toUpperCase();
      const currentItemExternalId = String(homeSelectedSourceExternalId || "").trim();
      if (currentItemSource || currentItemExternalId) {
        contextCandidates.push({
          source: currentItemSource,
          masterExternalId: currentItemExternalId,
        });
      }
      const infoSource = String(homeMasterInfo?.source || "").trim().toUpperCase();
      const infoExternalId = String(homeMasterInfo?.master_external_id || "").trim();
      if (infoSource || infoExternalId) {
        contextCandidates.push({
          source: infoSource,
          masterExternalId: infoExternalId,
        });
      }
      const memberItems = Array.isArray(homeMasterInfo?.items) ? homeMasterInfo.items : [];
      const currentOwnedItemId = Number(homeSelectedItemId || $("editOwnedId")?.value || 0);
      const prioritizedItems = [
        ...memberItems.filter((row) => Number(row?.id || 0) === currentOwnedItemId),
        ...memberItems.filter((row) => Number(row?.id || 0) !== currentOwnedItemId),
      ];
      for (const row of prioritizedItems) {
        contextCandidates.push({
          source: String(row?.source_code || "").trim().toUpperCase(),
          masterExternalId: String(row?.source_external_id || "").trim(),
        });
      }
      const supportedCandidate = contextCandidates.find(
        (candidate) => supportedVariantSources.includes(candidate.source) && candidate.masterExternalId
      );
      const source = String(supportedCandidate?.source || "").trim().toUpperCase();
      const masterExternalId = String(supportedCandidate?.masterExternalId || "").trim();
      const title = String(homeMasterInfo?.title || $("editItemName")?.value || "").trim();
      const artist = String(homeMasterInfo?.artist_or_brand || $("editArtistName")?.value || $("editLinkedArtistName")?.value || "").trim();
      return { masterId, masterRow, source, masterExternalId, title, artist };
    }

    function syncHomeLinkedSourceText() {
      const text = homeSelectedSourceCode && homeSelectedSourceExternalId
        ? `${homeSelectedSourceCode}#${homeSelectedSourceExternalId}`
        : "-";
      $("homeMetaLinkedSource").textContent = text;
    }

    function detectAcquisitionSource(data) {
      const sourceCode = String(data?.source_code || "").trim().toUpperCase();
      const sourceExternalId = String(data?.source_external_id || "").trim();
      const createdAt = String(data?.created_at || "").trim();
      const memoryNote = String(data?.memory_note || "");

      if (sourceCode) {
        const sourceLabel = sourceCode === "DISCOGS"
          ? "Discogs"
          : (sourceCode === "MANIADB" ? "ManiaDB" : (sourceCode === "ALADIN" ? "Aladin" : sourceCode));
        return t("media.manage.source_link.external", {
          source: sourceLabel,
          source_id: sourceExternalId || "-",
          created_at: createdAt ? ` / ${createdAt}` : "",
        });
      }

      const markerMatch = memoryNote.match(/\[(AUTO|META)\]\s*([A-Z_]+)#([^\s]+)/i);
      if (markerMatch) {
        const guessedSource = String(markerMatch[2] || "").toUpperCase();
        const guessedId = String(markerMatch[3] || "");
        return t("media.manage.source_link.manual_meta", {
          source: guessedSource,
          external_id: guessedId,
          created_at: createdAt ? ` / ${createdAt}` : "",
        });
      }

      return t("media.manage.source_link.manual", {
        created_at: createdAt ? ` / ${createdAt}` : "",
      });
    }

    function sourceReleaseLinkText(sourceCode, sourceExternalId) {
      const source = normalizeSourceCode(sourceCode);
      const externalId = String(sourceExternalId || "").trim();
      if (!externalId) return "";
      const labelMap = {
        DISCOGS: t("media.manage.source_link.discogs_product"),
        MANIADB: "ManiaDB 상품 열기",
        ALADIN: "Aladin 상품 열기",
      };
      const link = itemSourceLinkHtml(source, externalId, labelMap[source] || source);
      return link ? t("media.manage.source_link.product_path", { link }) : "";
    }

    function clearHomeMetaCandidates() {
      homeMetaCandidates = [];
      $("homeMetaCount").textContent = countWithUnit(0);
      $("homeMetaResults").innerHTML = "";
      setStatus("homeMetaStatus", "ok", "");
    }

    function homeMetaFallbackQuery() {
      const parts = [
        valueOf("editArtistName").trim(),
        String(homeMasterInfo?.artist_or_brand || "").trim(),
        valueOf("editItemName").trim(),
        String(homeMasterInfo?.title || "").trim(),
        valueOf("editCatalogNo").trim(),
        valueOf("homeMasterAddCatalogNo").trim(),
        valueOf("editReleasedDate").trim()
      ].filter((v) => v);
      return parts.join(" ").trim();
    }

    function buildHomeMetaQueryAlternatives(rawQuery) {
      const base = String(rawQuery || "").trim();
      const variants = [];
      const pushVariant = (value) => {
        const text = String(value || "").trim();
        if (!text || variants.includes(text)) return;
        variants.push(text);
      };
      pushVariant(base);
      if (/[가-힣]/.test(base) && /\s/.test(base)) {
        pushVariant(base.replace(/\s+/g, ""));
      }
      return variants;
    }

    function homeMetaCandidateHtml(c, idx) {
      const title = `${c.artist_or_brand || "Unknown"} - ${c.title || "(no title)"}`;
      const discogsLink = discogsReleaseLinkHtml(c.source, c.external_id, t("media.manage.master.fetch.candidate.link.discogs"));
      const galleryKey = registerImageGallery(`homeMeta:${normalizeSourceCode(c.source)}:${c.external_id || idx}`, c, {
        title,
        subtitle: `${normalizeSourceCode(c.source) || "-"}#${c.external_id || "-"}`,
      });
      const galleryCount = galleryKey ? Number(imageGalleryRegistry.get(galleryKey)?.items?.length || 0) : 0;
      const coverUrl = normalizeRenderableCoverUrl(c.cover_image_url);
      const cover = coverUrl
        ? `<img src="${escapeHtml(coverUrl)}" alt="${escapeHtml(title)}" />`
        : escapeHtml(t("media.manage.master.fetch.candidate.no_cover"));
      const discogsMetaHtml = buildDiscogsStandardMetaHtml(c);
      return `
        <div class="result-item album-result">
          <div class="album-result-cover">${cover}</div>
          <div class="album-result-main">
            <strong>${escapeHtml(title)}</strong>
            <div class="result-meta">
              <span class="tag">${escapeHtml(c.source || "-")}</span>
              ${discogsMetaHtml || `
                <span>${escapeHtml(t("common.meta.release_date", { value: c.released_date || c.release_year || "-" }))}</span>
                <span>media/type: ${escapeHtml(c.media_type || "-")} / ${escapeHtml(c.release_type || "-")}</span>
                <span>${escapeHtml(t("common.meta.pressing", { value: String(c.pressing_country || c.country || "").trim() || "-" }))}</span>
                <span>${escapeHtml(t("common.meta.format_items", { value: summarizeFormatItems(c.format_items, 2) }))}</span>
                <span>${escapeHtml(t("common.meta.genre_styles", { value: joinCommaList(c.genres) || "-" }))}</span>
                <span>${escapeHtml(t("common.meta.label_catalog", { value: c.catalog_no || "-" }))}</span>
                <span>${escapeHtml(t("common.meta.barcode", { value: c.barcode || "-" }))}</span>
                <span>${escapeHtml(t("common.meta.track_count", { value: formatCount(Array.isArray(c.track_list) ? c.track_list.length : 0) }))}</span>
              `}
            </div>
            <div class="mini">external_id: ${escapeHtml(c.external_id || "-")} ${discogsLink ? `| ${discogsLink}` : ""} ${galleryKey ? `| ${imageGalleryButtonHtml(galleryKey, t("common.count.images", { count: formatCount(galleryCount) }))}` : ""}</div>
            <div class="row u-mt-2">
              <button class="btn ghost home-meta-add-linked-btn" data-idx="${idx}" type="button">${escapeHtml(t("media.manage.master.fetch.action.add_linked"))}</button>
            </div>
          </div>
        </div>
      `;
    }

    function renderHomeMetaCandidates(items) {
      homeMetaCandidates = items;
      $("homeMetaCount").textContent = countWithUnit(items.length);
      $("homeMetaResults").innerHTML = items.map(homeMetaCandidateHtml).join("") || `<div class='muted'>${escapeHtml(t("media.manage.master.fetch.results.empty"))}</div>`;
    }

    function applyHomeMetadataCandidate(c) {
      if (!c) return;
      if (MUSIC_CATEGORIES.has($("editCategory").value)) {
        const mappedDomain = pickMappedDomain(c.domain_code);
        const mappedReleaseType = pickMappedReleaseType(c.release_type);
        if (mappedReleaseType) $("editReleaseType").value = mappedReleaseType;
        if (c.artist_or_brand) $("editArtistName").value = c.artist_or_brand;
        if (c.released_date) $("editReleasedDate").value = c.released_date;
        if (c.barcode) $("editBarcode").value = c.barcode;
        if (c.label_name) $("editLabelName").value = c.label_name;
        if (c.catalog_no) $("editCatalogNo").value = c.catalog_no;
        if (Number.isFinite(Number(c.disc_count)) && Number(c.disc_count) > 0) $("editDiscCount").value = String(Number(c.disc_count));
        if (Number.isFinite(Number(c.speed_rpm)) && Number(c.speed_rpm) > 0) $("editSpeedRpm").value = String(Number(c.speed_rpm));
        if (c.runout_matrix) $("editRunoutMatrix").value = joinRunoutList(c.runout_matrix);
        if (c.pressing_country) $("editPressingCountry").value = c.pressing_country;
        if (c.media_type) { $("editMediaType").value = c.media_type; _syncVinylOnlyFields(); }
        if (c.cover_image_url) $("editCoverImageUrl").value = c.cover_image_url;
        if (Array.isArray(c.track_list) && c.track_list.length) {
          $("editTrackList").value = c.track_list.join("\n");
        }
        applyCandidateCollectorToHomeDetail(c);
      }

      if (c.title) {
        $("editItemName").value = c.title;
      }

      if (c.source && c.external_id) {
        homeSelectedSourceCode = String(c.source).toUpperCase();
        homeSelectedSourceExternalId = String(c.external_id);
        syncHomeLinkedSourceText();
        loadHomeCollectorSummary();
      }

      const marker = `[META] ${c.source}#${c.external_id}`;
      const prev = $("editMemoryNote").value.trim();
      if (!prev.includes(marker)) {
        $("editMemoryNote").value = prev ? `${prev}\n${marker}` : marker;
      }
      syncHomeRelatedSelectedMetaPreview();
      syncHomeSourceManagedMetaUi();
      renderHomeTrackInfoPanel();
      setStatus("homeMetaStatus", "ok", t("media.manage.master.fetch.results.applied", {
        source: c.source || "-",
        external_id: c.external_id || "-",
      }));
    }

    function buildLinkedOwnedPayloadFromMetaCandidate(c, albumMasterId) {
      const sourceCodeRaw = String(c?.source || "").trim().toUpperCase();
      const sourceCode = ["DISCOGS", "MANIADB", "ALADIN"].includes(sourceCodeRaw)
        ? sourceCodeRaw
        : null;
      const sourceExternalId = String(c?.external_id || "").trim() || null;
      const currentCategory = valueOf("editCategory").trim().toUpperCase() || valueOf("editFormatName").trim().toUpperCase();
      const inferredCategory = inferMusicCategoryFromMetadata(c);
      const category = inferredCategory || (MUSIC_CATEGORIES.has(currentCategory) ? currentCategory : "LP");
      const sizeGroup = inferSizeGroupFromMetadata(category, c);
      const mappedDomain = pickMappedDomain(c?.domain_code);
      const mappedReleaseType = pickMappedReleaseType(c?.release_type);
      const artist = String(c?.artist_or_brand || "").trim();
      const title = String(c?.title || "").trim();
      const itemName = title || [artist, title].filter((v) => v).join(" - ") || `${category} linked`;
      const sourceCodeUpper = String(c?.source || "").trim().toUpperCase();
      const collector = buildCollectorPayload(sourceCodeUpper, c || {});
      const trackList = Array.isArray(c?.track_list)
        ? c.track_list.map((v) => String(v || "").trim()).filter((v) => v)
        : [];
      const memoryMarker = sourceCode && sourceExternalId ? `[META_LINK] ${sourceCode}#${sourceExternalId}` : null;

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
        source_external_id: sourceCode ? sourceExternalId : null,
        release_type: valueOf("editReleaseType").trim() || mappedReleaseType || null,
        linked_album_master_id: Number(albumMasterId),
        linked_artist_name: null,
        purchase_source: null,
        condition_grade: null,
        memory_note: memoryMarker,
        item_name_override: itemName,
        display_rank: null,
        storage_slot_id: null,
        subtype_option_ids: [],
        soundtrack_option_ids: [],
        music_detail: {
          format_name: category,
          is_promotional_not_for_sale: false,
          artist_or_brand: artist || null,
          released_date: c?.released_date || null,
          barcode: c?.barcode || null,
          label_name: c?.label_name || null,
          catalog_no: c?.catalog_no || null,
          media_type: c?.media_type || null,
          genres: splitCommaList(c?.genres || []),
          styles: splitCommaList(c?.styles || []),
          cover_image_url: c?.cover_image_url || null,
          track_list: trackList,
          cover_condition: null,
          disc_condition: null,
          disc_count: normalizePositiveIntOrNull(c?.disc_count),
          speed_rpm: Number.isFinite(Number(c?.speed_rpm)) ? Number(c.speed_rpm) : null,
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

    async function addLinkedItemFromHomeMetaCandidate(c) {
      const fieldMasterId = Number($("editLinkedAlbumMasterId")?.value || 0);
      const infoMasterId = Number(homeMasterInfo?.album_master_id || 0);
      const masterId = Number(homeSelectedMasterId || fieldMasterId || infoMasterId || 0);
      if (!masterId) {
        setStatus("homeMetaStatus", "err", t("media.manage.master.fetch.status.master_required"));
        return;
      }
      if (!c) {
        setStatus("homeMetaStatus", "err", t("media.manage.master.fetch.status.candidate_required"));
        return;
      }
      try {
        const payload = buildLinkedOwnedPayloadFromMetaCandidate(c, masterId);
        setStatus("homeMetaStatus", "ok", t("media.manage.master.fetch.status.adding_linked", {
          source: c.source || "-",
          external_id: c.external_id || "-",
        }));
        const res = await fetch("/owned-items", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.master.fetch.status.add_linked_failed"));
        setStatus("homeMetaStatus", "ok", t("media.manage.master.fetch.status.added_linked", {
          owned_item_id: data.owned_item_id,
          label_id: data.label_id,
        }));
        await homeSearchOwnedItems();
        await loadHomeMasterMembers(masterId, { autoOpenFirst: false });
        await loadHomeMasterAddVariants();
      } catch (err) {
        setStatus("homeMetaStatus", "err", err.message);
      }
    }

    function buildHomeMetaSourceCandidates(source) {
      const primary = String(source || "AUTO").trim().toUpperCase() || "AUTO";
      if (primary === "AUTO") return ["AUTO"];
      return [primary];
    }

    function buildRegisterLookupSourceCandidates(source) {
      const primary = String(source || "AUTO").trim().toUpperCase() || "AUTO";
      if (primary === "AUTO") return ["AUTO"];
      const fallbacks = ["DISCOGS", "MANIADB", "ALADIN", "MUSICBRAINZ"].filter((sourceCode) => sourceCode !== primary);
      return [primary, ...fallbacks];
    }

    async function searchHomeMetadataByBarcode() {
      const ownedItemId = Number(valueOf("editOwnedId") || 0);
      const masterId = Number(homeSelectedMasterId || homeMasterInfo?.album_master_id || 0);
      if (!ownedItemId && !masterId) {
        setStatus("homeMetaStatus", "err", t("media.manage.master.fetch.status.master_or_item_required"));
        return;
      }
      const barcode = valueOf("homeMetaBarcode").trim() || valueOf("editBarcode").trim();
      if (!barcode) {
        setStatus("homeMetaStatus", "err", t("media.manage.master.fetch.status.barcode_required"));
        return;
      }

      try {
        const selectedSource = valueOf("homeMetaSource").trim().toUpperCase() || "AUTO";
        const requestSources = buildHomeMetaSourceCandidates(selectedSource);
        setStatus("homeMetaStatus", "ok", t("media.manage.master.fetch.status.barcode_loading", { source: requestSources[0] }));
        const category = valueOf("editCategory").trim() || "LP";
        const fallbackQuery = homeMetaFallbackQuery();
        const fallbackQueries = buildHomeMetaQueryAlternatives(fallbackQuery);
        const artistOrBrand = valueOf("editArtistName").trim() || String(homeMasterInfo?.artist_or_brand || "").trim() || null;
        const title = valueOf("editItemName").trim() || String(homeMasterInfo?.title || "").trim() || null;
        const catalogNo = valueOf("editCatalogNo").trim() || valueOf("homeMasterAddCatalogNo").trim() || null;
        let items = [];
        let usedSource = requestSources[0];
        let usedQuery = "";
        let usedFallbackQuery = false;
        let lastError = null;
        for (const source of requestSources) {
          const res = await fetchWithRetry("/ingest/barcode", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              barcode,
              category,
              source,
              limit: 8
            })
          }, { retries: 2, retryDelayMs: 250 });
          const data = await safeJson(res);
          if (!res.ok) {
            lastError = new Error(data.detail || t("media.manage.master.fetch.status.barcode_failed"));
            continue;
          }
          items = Array.isArray(data.candidates) ? data.candidates : [];
          usedSource = source;
          if (items.length) break;
        }
        if (!items.length && fallbackQueries.length) {
          for (const source of requestSources) {
            for (const candidateQuery of fallbackQueries) {
              const res = await fetchWithRetry("/ingest/search", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  category,
                  source,
                  query: candidateQuery,
                  artist_or_brand: artistOrBrand,
                  title,
                  catalog_no: catalogNo,
                  limit: 8
                })
              }, { retries: 2, retryDelayMs: 250 });
              const data = await safeJson(res);
              if (!res.ok) {
                lastError = new Error(data.detail || t("media.manage.master.fetch.status.barcode_failed"));
                continue;
              }
              items = Array.isArray(data.candidates) ? data.candidates : [];
              usedSource = source;
              usedQuery = String(data.query || candidateQuery || "").trim() || candidateQuery;
              usedFallbackQuery = items.length > 0;
              if (items.length) break;
            }
            if (items.length) break;
          }
        }
        if (!items.length && lastError) throw lastError;
        renderHomeMetaCandidates(items);
        const adjustedText = usedSource !== selectedSource ? t("media.manage.master.fetch.status.adjusted_source", { source: usedSource }) : "";
        const fallbackText = usedFallbackQuery ? t("media.manage.master.fetch.status.adjusted_query", { query: usedQuery }) : "";
        setStatus("homeMetaStatus", "ok", t("media.manage.master.fetch.status.results_complete", {
          count: countWithUnit(items.length),
          adjusted_source: adjustedText,
          adjusted_query: fallbackText,
        }));
      } catch (err) {
        renderHomeMetaCandidates([]);
        setStatus("homeMetaStatus", "err", err.message);
      }
    }

    async function searchHomeMetadataByQuery() {
      const ownedItemId = Number(valueOf("editOwnedId") || 0);
      const masterId = Number(homeSelectedMasterId || homeMasterInfo?.album_master_id || 0);
      if (!ownedItemId && !masterId) {
        setStatus("homeMetaStatus", "err", t("media.manage.master.fetch.status.master_or_item_required"));
        return;
      }
      const query = valueOf("homeMetaQuery").trim() || homeMetaFallbackQuery();
      if (!query) {
        setStatus("homeMetaStatus", "err", t("media.manage.master.fetch.status.query_required"));
        return;
      }

      try {
        const selectedSource = valueOf("homeMetaSource").trim().toUpperCase() || "AUTO";
        const requestSources = buildHomeMetaSourceCandidates(selectedSource);
        const category = valueOf("editCategory").trim() || "LP";
        const artistOrBrand = valueOf("editArtistName").trim() || String(homeMasterInfo?.artist_or_brand || "").trim() || null;
        const title = valueOf("editItemName").trim() || String(homeMasterInfo?.title || "").trim() || null;
        const catalogNo = valueOf("editCatalogNo").trim() || valueOf("homeMasterAddCatalogNo").trim() || null;
        const queryAlternatives = buildHomeMetaQueryAlternatives(query);
        $("homeMetaCount").textContent = t("media.manage.master.fetch.results.loading");
        $("homeMetaResults").innerHTML = `<div class='muted'>${escapeHtml(t("media.manage.master.fetch.results.loading"))}</div>`;
        setStatus("homeMetaStatus", "ok", t("media.manage.master.fetch.status.query_loading", { source: requestSources[0] }));
        let items = [];
        let usedQuery = query;
        let usedSource = requestSources[0];
        let lastError = null;
        for (const source of requestSources) {
          for (const candidateQuery of queryAlternatives) {
            const res = await fetchWithRetry("/ingest/search", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                category,
                source,
                query: candidateQuery,
                artist_or_brand: artistOrBrand,
                title,
                catalog_no: catalogNo,
                limit: 8
              })
            }, { retries: 2, retryDelayMs: 250 });
            const data = await safeJson(res);
            if (!res.ok) {
              lastError = new Error(data.detail || t("media.manage.master.fetch.status.query_failed"));
              continue;
            }
            items = Array.isArray(data.candidates) ? data.candidates : [];
            usedQuery = String(data.query || candidateQuery || "").trim() || candidateQuery;
            usedSource = source;
            if (items.length) break;
          }
          if (items.length) break;
        }
        if (!items.length && lastError) throw lastError;
        renderHomeMetaCandidates(items);
        const adjustedText = usedQuery !== query ? t("media.manage.master.fetch.status.adjusted_query", { query: usedQuery }) : "";
        const adjustedSourceText = usedSource !== selectedSource ? t("media.manage.master.fetch.status.adjusted_source", { source: usedSource }) : "";
        setStatus("homeMetaStatus", "ok", t("media.manage.master.fetch.status.results_complete", {
          count: countWithUnit(items.length),
          adjusted_source: adjustedSourceText,
          adjusted_query: adjustedText,
        }));
      } catch (err) {
        renderHomeMetaCandidates([]);
        setStatus("homeMetaStatus", "err", err.message);
      }
    }

    function homeMasterHeadingLabel(row) {
      const title = resolveAlbumMasterName(row);
      const artist = String(row?.artist_or_brand || "").trim();
      const year = Number(row?.release_year || 0);
      const yearText = year > 0 ? ` (${year})` : "";
      return artist ? `${artist} - ${title}${yearText}` : `${title}${yearText}`;
    }

    function homeMasterLocationButtonsHtml(row) {
      const actions = Array.isArray(row?.member_location_actions)
        ? row.member_location_actions.filter((item) => item && (item.storage_slot_id || item.slot_code || item.cabinet_name))
        : [];
      if (!actions.length) return "";
      const distinctLocationKeys = new Set(actions.map((item) => {
        const slotId = Number(item.storage_slot_id || 0);
        const slotCode = String(item.slot_code || "").trim();
        const cabinetName = String(item.cabinet_name || "").trim();
        const columnCode = String(item.column_code || "").trim();
        const cellCode = String(item.cell_code || "").trim();
        const label = String(item.location_display_name || "").trim() || slotCode || t("common.unslotted");
        return JSON.stringify([slotId, slotCode, cabinetName, columnCode, cellCode, label]);
      }));
      const hasMultipleLocations = distinctLocationKeys.size > 1;
      const dedupedActions = [];
      const seenLocationKeys = new Set();
      actions.forEach((item) => {
        const slotId = Number(item.storage_slot_id || 0);
        const slotCode = String(item.slot_code || "").trim();
        const cabinetName = String(item.cabinet_name || "").trim();
        const columnCode = String(item.column_code || "").trim();
        const cellCode = String(item.cell_code || "").trim();
        const label = String(item.location_display_name || "").trim() || slotCode || t("common.unslotted");
        const locationKey = JSON.stringify([slotId, slotCode, cabinetName, columnCode, cellCode, label]);
        if (!hasMultipleLocations && seenLocationKeys.has(locationKey)) return;
        seenLocationKeys.add(locationKey);
        dedupedActions.push(item);
      });
      return `
        <div class="home-master-location-actions">
          ${dedupedActions.map((item) => {
            const slotId = Number(item.storage_slot_id || 0);
            const slotCode = String(item.slot_code || "").trim();
            const cabinetName = String(item.cabinet_name || "").trim();
            const columnCode = String(item.column_code || "").trim();
            const cellCode = String(item.cell_code || "").trim();
            const label = String(item.location_display_name || "").trim() || slotCode || t("common.unslotted");
            const itemCode = String(item.label_id || "").trim();
            const itemLabel = String(item.item_label || "").trim();
            const itemDescriptor = itemCode || itemLabel;
            const buttonLabel = hasMultipleLocations && itemDescriptor
              ? `${itemDescriptor} · ${label}`
              : label;
            const titleText = itemDescriptor
              ? `${itemDescriptor} · ${label}`
              : label;
            return `<button class="btn ghost tiny home-master-location-btn" type="button" title="${escapeHtml(titleText)}" data-home-open-dashboard-location="${slotId}" data-home-open-dashboard-slot-code="${escapeHtml(slotCode)}" data-home-open-cabinet-name="${escapeHtml(cabinetName)}" data-home-open-column-code="${escapeHtml(columnCode)}" data-home-open-cell-code="${escapeHtml(cellCode)}">${escapeHtml(buttonLabel)}</button>`;
          }).join("")}
        </div>
      `;
    }

    function homeMasterMemberPreviewLocationHtml(item) {
      const ownedItemId = Number(item?.owned_item_id || item?.id || 0);
      const storageSlotId = Number(item?.storage_slot_id || 0);
      const slotCode = String(item?.current_slot_code || item?.slot_code || "").trim();
      const cabinetName = String(item?.current_cabinet_name || item?.cabinet_name || "").trim();
      const columnCode = String(item?.current_column_code || item?.column_code || "").trim();
      const cellCode = String(item?.current_cell_code || item?.cell_code || "").trim();
      const hasTriplet = Boolean(cabinetName && columnCode && cellCode);
      const currentLocation = buildOperatorLocationLabel(item);
      if (hasTriplet) {
        return `<button class="btn ghost tiny home-master-location-btn" type="button" data-home-open-dashboard-location="${storageSlotId || ""}" data-home-open-dashboard-slot-code="${escapeHtml(slotCode)}" data-home-open-cabinet-name="${escapeHtml(cabinetName)}" data-home-open-column-code="${escapeHtml(columnCode)}" data-home-open-cell-code="${escapeHtml(cellCode)}" title="${escapeHtml(String(item?.item_title || "").trim() || currentLocation)}">${escapeHtml(t("operator.feed.meta.current"))} ${escapeHtml(currentLocation)}</button>`;
      }
      return `<span class="operator-title-side-fallback">${escapeHtml(t("operator.feed.meta.current"))} ${escapeHtml(currentLocation)}</span>`;
    }

    function homeMasterMemberPreviewMetaLine(item) {
      const releaseDate = String(item?.released_date || "").trim()
        || (item?.master_release_year ? String(item.master_release_year) : "");
      const releaseCountry = String(item?.pressing_country || item?.country || "").trim() || "-";
      const labelName = String(item?.label_name || "").trim();
      const catalogNo = String(item?.catalog_no || "").trim();
      const barcode = String(item?.barcode || "").trim();
      const catalogSummary = [catalogNo, barcode].filter((v) => v).join(" / ");
      const labelCatalogText = labelName && catalogSummary
        ? `${labelName} (${catalogSummary})`
        : (labelName || catalogSummary || "-");
      const formatSummary = firstOperatorFormatLine(item?.format_items || [], item?.format_name || "");
      const parts = [
        operatorMetaPairHtml(t("operator.feed.meta.summary.release"), releaseDate),
        operatorMetaPairHtml(t("operator.feed.meta.summary.country"), releaseCountry),
        operatorMetaPairHtml(t("operator.feed.meta.summary.label"), labelCatalogText),
        operatorMetaPairHtml(t("operator.feed.meta.summary.format"), formatSummary),
      ].filter((value) => value);
      return parts.length ? parts.join('<span class="operator-meta-separator">/</span>') : `<span class="operator-meta-value">-</span>`;
    }

    function mediaSearchMemberPreviewCoverSrc(item) {
      const sourceCode = normalizeSourceCode(item?.source_code);
      const sourceExternalId = String(item?.source_external_id || "").trim();
      if (sourceCode === "DISCOGS" && sourceExternalId) {
        return `/discogs/release/${encodeURIComponent(sourceExternalId)}/cover-preview`;
      }
      return String(item?.cover_image_url || "").trim();
    }

    function homeMasterMemberPreviewHtml(item, options = {}) {
      const titleParts = buildOperatorDisplayTitleParts(item);
      const title = titleParts.title;
      const artist = titleParts.artist;
      const rawFormatName = String(item?.format_name || "").trim();
      const packagingLabel = rawFormatName && !MUSIC_CATEGORIES.has(rawFormatName.toUpperCase()) ? rawFormatName : "";
      const whenText = formatOperatorCardDateTime(item?.created_at);
      const runoutSample = operatorRunoutSampleText(item?.runout_sample || item?.runout_matrix || []);
      const productRelationBadges = Array.isArray(item?.product_relation_badges)
        ? item.product_relation_badges
          .map((badge) => homeOwnedItemRelationTypeLabel(badge))
          .filter((badge) => badge)
        : [];
      const productRelationPreview = Array.isArray(item?.product_relation_preview)
        ? item.product_relation_preview
          .slice(0, 2)
          .map((relation) => {
            const relationLabel = homeOwnedItemRelationTypeLabel(relation?.relation_type);
            const targetLabel = homeOwnedItemRelationTargetLabel(relation);
            return [relationLabel, targetLabel].filter((value) => value && value !== "-").join(": ");
          })
          .filter((text) => text)
        : [];
      const boxComponentCount = Math.max(0, Number(item?.box_component_count || 0));
      const usesSharedRelationScope = Boolean(item?.uses_shared_relation_scope);
      const collectorMetaHtml = homeMasterMemberPreviewMetaLine(item);
      const masterId = Number(options?.masterId || item?.linked_album_master_id || 0);
      const ownedItemId = Number(item?.owned_item_id || item?.id || 0);
      const isInlineExpanded = ownedItemId > 0 && getMediaSearchExpandedPreviewOwnedItemId(masterId) === String(ownedItemId);
      const sourceCode = normalizeSourceCode(item?.source_code);
      const isContextSelected = ownedItemId > 0 && ownedItemId === getMediaSearchContextSelectedOwnedItemId();
      const labelId = String(item?.label_id || "").trim() || "-";
      const showCover = Boolean(options?.showCover);
      const coverUrl = mediaSearchMemberPreviewCoverSrc(item);
      const repairDiscogsMasterBtn = discogsRepairSlotHtml("home", {
        ownedItemId,
        sourceCode,
        masterSourceCode: options?.masterSourceCode,
        sourceExternalId: item?.source_external_id,
      });
      const inlineEditorHtml = typeof renderMediaSearchInlineEditor === "function"
        ? renderMediaSearchInlineEditor(masterId, item)
        : "";
      const signatureBadge = signatureCoverBadgeHtml(item?.signature_type, "media-search-cover-signature-badge");
      const coverHtml = showCover
        ? `<div class="home-master-member-preview-cover">${coverUrl
            ? `${signatureBadge}<img src="${escapeHtml(coverUrl)}" alt="${escapeHtml(title)}" />`
            : `${signatureBadge}${escapeHtml(t("media.manage.related_versions.state.no_cover"))}`}
          </div>`
        : "";
      return `
        <div class="home-master-member-preview-item ${showCover ? "with-cover" : ""} ${isContextSelected ? "is-context-selected" : ""}" data-home-member-preview-select="${ownedItemId}" data-home-member-preview-owned-id="${ownedItemId}">
          ${coverHtml}
          <div class="home-master-member-preview-body">
            <div class="home-master-member-preview-title-row">
              <div class="home-master-member-preview-title">${escapeHtml(title)}${packagingLabel ? `<span class="item-packaging-tag">(${escapeHtml(packagingLabel)})</span>` : ""}${artist ? `<span>${escapeHtml(artist)}</span>` : ""}</div>
              <div class="home-master-member-preview-actions">
                ${repairDiscogsMasterBtn}
                <span class="home-master-member-preview-code">${escapeHtml(labelId)}</span>
                <button class="btn tiny" type="button" data-home-preview-edit="${ownedItemId}" data-home-preview-edit-master-id="${masterId}" aria-expanded="${isInlineExpanded ? "true" : "false"}">${escapeHtml(t("common.action.edit_item"))} <span class="edit-arrow">${isInlineExpanded ? "▲" : "▼"}</span></button>
                <button class="btn ghost tiny home-master-member-preview-detail-btn" type="button" data-home-open-detail-manage="${ownedItemId}" data-home-open-detail-master-id="${masterId}">${escapeHtml(t("media.manage.search.action.open_detail_manage"))}</button>
                ${item.barcode ? `<button class="btn ghost tiny home-meta-sync-btn" type="button" data-home-meta-sync="${ownedItemId}" title="${escapeHtml(t("media.manage.search.action.sync_meta"))}">${escapeHtml(t("media.manage.search.action.sync_meta"))}</button>` : ""}
              </div>
            </div>
            <div class="operator-secondary-line">
              <div class="operator-secondary-line-main">
                ${whenText && whenText !== "-" ? `<span class="operator-title-side-meta"><strong>${escapeHtml(t("operator.feed.meta.registered"))}</strong> ${escapeHtml(whenText)}</span>` : ""}
              </div>
              ${homeMasterMemberPreviewLocationHtml(item)}
            </div>
            <div class="operator-meta-line">${collectorMetaHtml}</div>
            ${productRelationBadges.length || boxComponentCount > 0 || usesSharedRelationScope ? `
              <div class="home-master-subline">
                ${productRelationBadges.map((badge) => `<span class="tag">${escapeHtml(badge)}</span>`).join("")}
                ${boxComponentCount > 0 ? `<span class="tag">${escapeHtml(t("media.manage.product_relation.preview.box_components", { count: formatCount(boxComponentCount) }))}</span>` : ""}
                ${usesSharedRelationScope ? `<span class="tag">${escapeHtml(t("media.manage.product_relation.preview.shared_scope"))}</span>` : ""}
              </div>
            ` : ""}
            ${productRelationPreview.length ? `<div class="operator-meta-subline">${escapeHtml(productRelationPreview.join(" / "))}</div>` : ""}
            ${runoutSample !== "-" ? `<div class="operator-meta-subline home-master-member-preview-runout">${escapeHtml(runoutSample)}</div>` : ""}
          </div>
          ${inlineEditorHtml}
        </div>
      `;
    }

    function getHomeMasterVisiblePreviewItems(row) {
      const items = Array.isArray(row?.member_items_preview) ? row.member_items_preview.filter((item) => item && Number(item.owned_item_id || item.id || 0) > 0) : [];
      const expanded = homeExpandedMasterPreviewIds.has(Number(row?.id || 0));
      return expanded ? items : items.slice(0, 3);
    }

    function homeMasterMemberPreviewToggleHtml(row, totalItems, visibleCount) {
      const masterId = Number(row?.id || 0);
      if (masterId <= 0 || totalItems <= 3) return "";
      const expanded = homeExpandedMasterPreviewIds.has(masterId);
      const hiddenCount = Math.max(0, totalItems - visibleCount);
      const label = expanded
        ? t("media.manage.search.preview.collapse")
        : t("media.manage.search.preview.more", { count: formatCount(hiddenCount) });
      return `<button class="btn ghost tiny home-master-member-preview-toggle" type="button" data-home-toggle-member-preview="${masterId}" aria-expanded="${expanded ? "true" : "false"}">${escapeHtml(label)}</button>`;
    }

    function homeResultItemHtml(row) {
      const title = resolveAlbumMasterName(row);
      const heading = homeMasterHeadingLabel(row);
      const coverUrl = normalizeRenderableCoverUrl(row.cover_image_url);
      const allMemberItemsPreview = Array.isArray(row.member_items_preview)
        ? row.member_items_preview
          .filter((item) => item && Number(item.owned_item_id || item.id || 0) > 0)
          .map((item) => ({ ...item, linked_album_master_id: Number(row.id || 0) || null }))
        : [];
      const signatureType = String(row?.signature_type || "").trim().toUpperCase() || "";
      const previewSignatureType = allMemberItemsPreview.find((item) => {
        const code = String(item?.signature_type || "").trim().toUpperCase();
        return code === "IN_PERSON" || code === "PURCHASE_INCLUDED";
      })?.signature_type || "";
      const signatureBadge = signatureCoverBadgeHtml(signatureType || previewSignatureType, "media-search-cover-signature-badge");
      const cover = coverUrl
        ? `${signatureBadge}<img src="${escapeHtml(coverUrl)}" alt="${escapeHtml(title)}" />`
        : `${signatureBadge}${escapeHtml(t("media.manage.related_versions.state.no_cover"))}`;
      const memberItemsPreview = getHomeMasterVisiblePreviewItems({
        ...row,
        member_items_preview: allMemberItemsPreview,
      });
      const showMemberPreviewCover = allMemberItemsPreview.length > 1;
      const trackPreview = Array.isArray(row.matched_track_preview) ? row.matched_track_preview.filter((v) => String(v || "").trim()) : [];
      const sourceCode = normalizeSourceCode(row.source_code) || "-";
      const memberSourceCodes = Array.from(new Set(
        allMemberItemsPreview
          .map((item) => normalizeSourceCode(item?.source_code))
          .filter((value) => value)
      ));
      const previewOverflow = Math.max(0, Number(row.member_count || 0) - allMemberItemsPreview.length);
      const locationButtons = homeMasterLocationButtonsHtml(row);
      const previewExpanded = homeExpandedMasterPreviewIds.has(Number(row.id || 0));
      const previewHiddenCount = Math.max(0, allMemberItemsPreview.length - memberItemsPreview.length);
      const previewToggle = allMemberItemsPreview.length <= 3
        ? ""
        : `<button class="btn ghost tiny home-master-member-preview-toggle" type="button" data-home-toggle-member-preview="${row.id}" aria-expanded="${previewExpanded ? "true" : "false"}">${escapeHtml(previewExpanded ? t("media.manage.search.preview.collapse") : t("media.manage.search.preview.more", { count: formatCount(previewHiddenCount) }))}</button>`;
            const genres = Array.isArray(row.genres) && row.genres.length > 0 ? row.genres : [];
      const styles = Array.isArray(row.styles) && row.styles.length > 0 ? row.styles : [];
      const genreDisplay = [...genres, ...styles.filter(s => !genres.includes(s))];
      const genreLine = genreDisplay.length > 0
        ? `<div class="home-master-genre-line">장르/스타일: ${escapeHtml(genreDisplay.join(', '))}</div>`
        : "";
      const sourceChip = `<span class="tag home-master-source-chip">${escapeHtml(sourceCode)}</span>`;
      const itemSourceChip = memberSourceCodes.length === 1 && memberSourceCodes[0] !== sourceCode
        ? `<span class="tag home-master-item-source-chip">${escapeHtml(t("media.manage.search.item_source_chip", { source: memberSourceCodes[0] }))}</span>`
        : "";
      return `
        <div class="result-item album-result ${Number(row.id) === Number(homeSelectedMasterId) ? "pick" : ""}" data-master-id="${row.id}">
          <div class="album-result-cover">${cover}</div>
          <div class="album-result-main">
            <div class="home-master-heading-line">${sourceChip}${itemSourceChip}<strong class="home-master-heading">${escapeHtml(heading)}</strong>${row.spotify_album_id ? `<span class="spotify-badge" data-sp-master="${escapeHtml(String(row.id))}" data-sp-album="${escapeHtml(row.spotify_album_id)}">Spotify</span>` : ""}${_localLinkedIds.has(Number(row.id)) ? `<span class="local-player-badge" data-lp-badge="${escapeHtml(String(row.id))}" title="로컬 음원 연결됨">♪ Local</span>` : ""}${row.review_text ? `<span class="tag" style="font-size:0.65rem;opacity:0.8;">리뷰</span>` : ""}</div>${genreLine}
            ${trackPreview.length ? `<div class="mini">${escapeHtml(t("media.manage.search.matched_tracks", { tracks: trackPreview.join(" | ") }))}</div>` : ""}
            ${memberItemsPreview.length ? `<div class="home-master-member-preview-list">
              ${memberItemsPreview.map((item) => homeMasterMemberPreviewHtml(item, { showCover: showMemberPreviewCover, masterSourceCode: sourceCode })).join("")}
              ${previewToggle}
              ${previewOverflow > 0 ? `<div class="home-master-member-preview-more">${escapeHtml(t("common.count.more", { count: formatCount(previewOverflow) }))}</div>` : ""}
            </div>` : ""}
            ${locationButtons}
          </div>
        </div>
      `;
    }

    function renderHomeSearchResults(items) {
      $("homeSearchCount").textContent = countWithUnit(homeSearchTotalCount);
      if (getMediaSearchContextSelectedOwnedItemId() > 0 && !findMediaSearchContextItemByOwnedItem(getMediaSearchContextSelectedOwnedItemId())) {
        mediaSearchSelectedContextItem = null;
      }
      const root = $("homeSearchResults");
      root.innerHTML = items.map(homeResultItemHtml).join("") || `<div class='muted'>${escapeHtml(t("media.manage.search.results_empty"))}</div>`;
      renderHomePagination();
      renderMediaSearchContextDefault();
      queueDiscogsRepairEligibilityHydration(root);
    }

    async function loadHomeMasterMembers(albumMasterId, opts = {}) {
      const autoOpenFirst = Boolean(opts.autoOpenFirst);
      const context = resolveHomeMasterContext(albumMasterId);
      const masterId = Number(context.masterId || 0);
      if (!masterId) {
        homeMasterInfo = null;
        renderHomeRelatedVersions();
        setStatus("homeMasterStatus", "err", t("media.manage.master.members.status.master_required"));
        return;
      }

      try {
        setStatus("homeMasterStatus", "ok", t("media.manage.master.members.status.loading"));
        _lp._slotId = "homeMasterLocalPlayer";
        _lp.hide();
        const _spSlotClear = document.getElementById("homeMasterSpotifyEmbed");
        if (_spSlotClear) { _spSlotClear.hidden = true; _spSlotClear.innerHTML = ""; delete _spSlotClear.dataset.albumId; }
        const [res, collectiblesRes, masterRes] = await Promise.all([
          fetch(`/album-masters/${masterId}/members`),
          fetch(`/goods-items?album_master_id=${masterId}&limit=200&offset=0`),
          fetch(`/album-masters/${masterId}`),
        ]);
        const data = await safeJson(res);
        const collectiblesData = await safeJson(collectiblesRes);
        const masterData = masterRes.ok ? await safeJson(masterRes) : null;
        if (!res.ok) throw new Error(data.detail || t("media.manage.master.members.status.load_failed"));
        if (!collectiblesRes.ok) throw new Error(collectiblesData.detail || t("media.manage.collectibles.status.load_failed"));

        const items = Array.isArray(data) ? data : [];
        const collectibles = Array.isArray(collectiblesData.items) ? collectiblesData.items : [];
        // Derive master title/artist from the direct master API response (most reliable),
        // then fall back to item-level master_title (from album_master JOIN).
        // Never reuse the OLD homeMasterInfo fields — they belong to the previous master.
        const masterTitleResolved = String(masterData?.title || items[0]?.master_title || "").trim() || null;
        const masterArtistResolved = String(masterData?.artist_or_brand || items[0]?.master_artist_or_brand || "").trim() || null;
        const masterReleaseYearResolved = masterData?.release_year ?? items[0]?.master_release_year ?? null;
        const masterCoverResolved = masterData?.cover_image_url ?? items[0]?.cover_image_url ?? null;
        homeMasterInfo = {
          relation_type: "ALBUM_MASTER_BIND",
          source: context.source || masterData?.source_code || null,
          master_external_id: context.masterExternalId || masterData?.source_master_id || null,
          album_master_id: masterId,
          title: masterTitleResolved,
          artist_or_brand: masterArtistResolved,
          release_year: masterReleaseYearResolved,
          cover_image_url: masterCoverResolved,
          master_source_code: masterData?.source_code || null,
          master_source_id: masterData?.source_master_id || null,
          master_release_id: masterData?.source_release_id || null,
          items,
          collectibles,
          spotify_album_id: masterData?.spotify_album_id || null,
          spotify_album_uri: masterData?.spotify_album_uri || null,
          spotify_image_url: masterData?.spotify_image_url || null,
          review_text: masterData?.review_text || null,
          review_source: masterData?.review_source || null,
          review_url: masterData?.review_url || null,
          genres: masterData?.genres || [],
          styles: masterData?.styles || [],
          domain_code: masterData?.domain_code || null,
          source_release_year: masterData?.source_release_year ?? null,
          source_domain_code: masterData?.source_domain_code || null,
          override_release_year: masterData?.override_release_year ?? null,
          override_domain_code: masterData?.override_domain_code || null,
          override_note: masterData?.override_note || null,
          override_title: masterData?.override_title || null,
          override_artist_or_brand: masterData?.override_artist_or_brand || null,
          sort_artist_name: masterData?.sort_artist_name || null,
          release_type: masterData?.release_type || null,
        };
        renderHomeRelatedVersions();
        setStatus("homeMasterStatus", "ok", "");

        // 플레이어: 로컬 우선, Spotify 폴백
        (function() {
          const _spId = homeMasterInfo?.spotify_album_id || null;
          _lp.load(masterId).then(() => {
            const localSlot = document.getElementById("homeMasterLocalPlayer");
            if ((!localSlot || localSlot.hidden) && _spId) {
              const spSlot = document.getElementById("homeMasterSpotifyEmbed");
              if (spSlot) { spSlot.innerHTML = _spotifyEmbedHtml(_spId, 352); spSlot.dataset.albumId = _spId; spSlot.hidden = false; }
            }
          }).catch(() => {
            if (_spId) {
              const spSlot = document.getElementById("homeMasterSpotifyEmbed");
              if (spSlot) { spSlot.innerHTML = _spotifyEmbedHtml(_spId, 352); spSlot.dataset.albumId = _spId; spSlot.hidden = false; }
            }
          });
        })();

        if (autoOpenFirst) {
          const firstOwnedItemId = Number(items[0]?.id || 0);
          if (firstOwnedItemId > 0) {
            await loadHomeItemForEdit(firstOwnedItemId, { keepMasterContext: true });
          } else {
            setStatus("homeEditStatus", "ok", t("media.manage.master.members.state.no_owned_items"));
          }
        }
      } catch (err) {
        homeMasterInfo = null;
        renderHomeRelatedVersions();
        setStatus("homeMasterStatus", "err", err.message);
      }
    }

    async function loadHomeLinkedCollectibles(albumMasterId, requestSeq = 0) {
      if (requestSeq && !isActiveHomeEditRequest(requestSeq)) return;
      const masterId = Number(albumMasterId || 0);
      if (masterId <= 0) {
        homeLinkedCollectibles = [];
        homeLinkedCollectiblesLoading = false;
        renderHomeLinkedCollectiblesSection();
        return;
      }
      try {
        homeLinkedCollectiblesLoading = true;
        renderHomeLinkedCollectiblesSection();
        const res = await fetch(`/goods-items?album_master_id=${masterId}&limit=200&offset=0`);
        const data = await safeJson(res);
        if (requestSeq && !isActiveHomeEditRequest(requestSeq)) return;
        if (!res.ok) throw new Error(data.detail || t("media.manage.collectibles.status.load_failed"));
        homeLinkedCollectibles = Array.isArray(data.items) ? data.items : [];
      } catch (err) {
        if (requestSeq && !isActiveHomeEditRequest(requestSeq)) return;
        homeLinkedCollectibles = [];
        setHtmlIfPresent("homeMasterGoodsList", `<div class='muted'>${escapeHtml(err.message || t("media.manage.collectibles.status.load_failed"))}</div>`);
      } finally {
        if (requestSeq && !isActiveHomeEditRequest(requestSeq)) return;
        homeLinkedCollectiblesLoading = false;
        renderHomeLinkedCollectiblesSection();
      }
    }

    function renderHomeMasterAddVariants(items, emptyText = t("media.manage.master.placeholder.empty_versions")) {
      const rows = Array.isArray(items) ? items : [];
      homeMasterAddVariants = rows;
      const root = $("homeMasterAddResults");
      if (!root) return;
      root.innerHTML = rows.length
        ? rows.map(homeMasterAddVariantItemHtml).join("")
        : `<div class="result-item"><div class="muted">${escapeHtml(emptyText)}</div></div>`;
      setTextIfPresent("homeMasterAddCount", countWithUnit(homeMasterAddTotalCount ?? rows.length));
    }

    async function loadHomeManageMasterLookup(opts = {}) {
      const context = resolveHomeMasterContext();
      const masterId = Number(context.masterId || 0);
      if (masterId > 0) {
        homeSelectedMasterId = masterId;
        syncHomeMasterDeleteUi();
        await loadHomeMasterMembers(masterId, { autoOpenFirst: false });
      } else {
        homeSelectedMasterId = null;
        syncHomeMasterDeleteUi();
        homeMasterInfo = null;
        renderHomeRelatedVersions();
      }
      await loadHomeMasterAddVariants(opts);
    }

    function renderHomeMasterAddPager() {
      const prevBtn = $("homeMasterAddPrevBtn");
      const nextBtn = $("homeMasterAddNextBtn");
      const pageInfo = $("homeMasterAddPageInfo");
      const countInfo = $("homeMasterAddCount");
      if (!prevBtn || !nextBtn || !pageInfo) return;
      prevBtn.disabled = homeMasterAddPage <= 1;
      nextBtn.disabled = !homeMasterAddHasNext;

      let totalText = "";
      if (Number.isFinite(homeMasterAddTotalCount) && Number(homeMasterAddTotalCount) >= 0) {
        totalText = ` / ${t("media.manage.master.add.total_suffix", { count: formatCount(Number(homeMasterAddTotalCount)) })}`;
      } else if (homeMasterAddTruncated) {
        totalText = ` / ${t("media.manage.master.add.total_truncated")}`;
      }
      pageInfo.textContent = `page ${homeMasterAddPage}${totalText}`;
      if (countInfo) {
        countInfo.textContent = countWithUnit(homeMasterAddTotalCount ?? homeMasterAddVariants.length);
      }
    }

    async function loadHomeMasterAddVariants(opts = {}) {
      const resetPage = Boolean(opts.resetPage);
      if (resetPage) homeMasterAddPage = 1;
      homeMasterAddPageSize = Math.max(1, Math.min(100, Number(homeMasterAddPageSize || 50)));
      const context = resolveHomeMasterContext();
      const masterId = Number(context.masterId || 0);
      if (!masterId) {
        setHomeMasterLookupResultsVisible(true);
        renderHomeMasterAddVariants([], t("media.manage.master.add.no_master"));
        setStatus("homeMasterAddStatus", "err", t("media.manage.master.add.no_master"));
        homeMasterAddHasNext = false;
        homeMasterAddTotalCount = null;
        homeMasterAddTruncated = false;
        renderHomeMasterAddPager();
        return;
      }
      if (!context.source || !context.masterExternalId) {
        setHomeMasterLookupResultsVisible(true);
        const guideMessage = t("media.manage.master.add.no_source_link");
        renderHomeMasterAddVariants([], guideMessage);
        setStatus("homeMasterAddStatus", "err", guideMessage);
        homeMasterAddHasNext = false;
        homeMasterAddTotalCount = null;
        homeMasterAddTruncated = false;
        renderHomeMasterAddPager();
        return;
      }
      const source = String(context.source || "").toUpperCase();
      const masterExternalId = String(context.masterExternalId || "").trim();
      if (!["DISCOGS", "MANIADB"].includes(source) || !masterExternalId) {
        setHomeMasterLookupResultsVisible(true);
        renderHomeMasterAddVariants([], t("media.manage.master.add.unsupported_source"));
        setStatus("homeMasterAddStatus", "ok", t("media.manage.master.add.unsupported_source_short"));
        homeMasterAddHasNext = false;
        homeMasterAddTotalCount = null;
        homeMasterAddTruncated = false;
        renderHomeMasterAddPager();
        return;
      }
      setHomeMasterLookupResultsVisible(true);
      const params = new URLSearchParams({
        source,
        master_external_id: masterExternalId,
        album_master_id: String(masterId),
        page: String(homeMasterAddPage),
        page_size: String(homeMasterAddPageSize)
      });
      try {
        setStatus("homeMasterAddStatus", "ok", t("media.manage.master.add.loading"));
        const res = await fetch(`/album-masters/variants?${params.toString()}`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.master.add.failed"));
        const ownedByExternal = new Map();
        const memberItems = Array.isArray(homeMasterInfo?.items) ? homeMasterInfo.items : [];
        for (const member of memberItems) {
          const ext = String(member.source_external_id || "").trim();
          const ownedId = Number(member.id || 0);
          if (!ext || ownedId <= 0) continue;
          if (!ownedByExternal.has(ext)) ownedByExternal.set(ext, []);
          ownedByExternal.get(ext).push(ownedId);
        }

        const items = (Array.isArray(data.items) ? data.items : []).map((row) => {
          const ext = String(row.external_id || "").trim();
          const ownedIds = ownedByExternal.get(ext) || [];
          return {
            ...row,
            owned_count: ownedIds.length,
            primary_owned_item_id: ownedIds.length ? Number(ownedIds[0]) : null
          };
        });
        const pageValue = Number(data.page);
        homeMasterAddPage = Number.isFinite(pageValue) && pageValue > 0 ? Math.floor(pageValue) : homeMasterAddPage;
        homeMasterAddHasNext = Boolean(data.has_next);
        const totalValue = Number(data.total_count);
        homeMasterAddTotalCount = Number.isFinite(totalValue) && totalValue >= 0 ? Math.floor(totalValue) : null;
        homeMasterAddTruncated = Boolean(data.truncated);
        renderHomeMasterAddVariants(items);
        renderHomeMasterAddPager();
        let totalText = "";
        if (homeMasterAddTotalCount !== null) {
          totalText = ` / ${t("media.manage.master.add.total_suffix", { count: formatCount(homeMasterAddTotalCount) })}`;
        } else if (homeMasterAddTruncated) {
          totalText = ` / ${t("media.manage.master.add.total_truncated")}`;
        }
        setStatus("homeMasterAddStatus", "ok", t("media.manage.master.add.loaded", {
          count: formatCount(items.length),
          page_info: t("media.manage.master.add.page_info", { page: homeMasterAddPage, total: totalText }),
        }));
      } catch (err) {
        renderHomeMasterAddVariants([], t("media.manage.master.placeholder.empty_versions"));
        homeMasterAddHasNext = false;
        homeMasterAddTotalCount = null;
        homeMasterAddTruncated = false;
        renderHomeMasterAddPager();
        setStatus("homeMasterAddStatus", "err", err.message);
      }
    }

    async function registerHomeMasterVariant(externalId) {
      const context = resolveHomeMasterContext();
      const masterId = Number(context.masterId || 0);
      if (!masterId) {
        setStatus("homeMasterAddStatus", "err", t("media.manage.master.variant.status.master_required"));
        return;
      }
      if (!context.source || !context.masterExternalId) {
        setStatus("homeMasterAddStatus", "err", t("media.manage.master.variant.status.no_source_link"));
        return;
      }
      const source = String(context.source || "").toUpperCase();
      const masterExternalId = String(context.masterExternalId || "").trim();
      if (!["DISCOGS", "MANIADB"].includes(source) || !masterExternalId) {
        setStatus("homeMasterAddStatus", "err", t("media.manage.master.variant.status.unsupported_source"));
        return;
      }
      const targetExternalId = String(externalId || "").trim();
      if (!targetExternalId) {
        setStatus("homeMasterAddStatus", "err", t("media.manage.master.variant.status.selection_required"));
        return;
      }

      try {
        setStatus("homeMasterAddStatus", "ok", t("media.manage.master.variant.status.registering", { external_id: targetExternalId }));
        const res = await fetch("/album-masters/import-variants", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            source,
            master_external_id: masterExternalId,
            linked_album_master_id: masterId,
            selected_variant_external_ids: [targetExternalId],
            skip_if_owned: true
          })
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.master.variant.status.register_failed"));
        const notices = Array.isArray(data.notices) ? data.notices : [];
        const createdItems = Array.isArray(data.created_items) ? data.created_items : [];
        const skippedItems = Array.isArray(data.skipped_items) ? data.skipped_items : [];
        const noticesText = notices.length
          ? t("media.manage.master.variant.status.notices", {
              items: notices.map((v) => t("media.manage.master.variant.status.notice_item", { notice: v })).join("\n"),
            })
          : "";
        await loadHomeMasterMembers(masterId, { autoOpenFirst: false });
        await loadHomeMasterAddVariants();

        const createdOwnedItemId = Number(createdItems[0]?.owned_item_id || 0);
        const resultStatusType = createdItems.length > 0 ? "ok" : (skippedItems.length > 0 ? "ok" : "ok");
        const resultStatusText = t("media.manage.master.variant.status.register_done", {
          created_count: formatCount(Number(data.created_count || 0)),
          skipped_count: formatCount(Number(data.skipped_count || 0)),
          notices: noticesText,
        });

        if (createdItems.length) {
          const masterListRow = homeSearchResults.find((row) => Number(row.id) === masterId);
          if (masterListRow) {
            const prevCount = Number(masterListRow.member_count || 0);
            masterListRow.member_count = Math.max(prevCount, prevCount + createdItems.length);
          }
          renderHomeSearchResults(homeSearchResults);
        }
        if (createdOwnedItemId > 0) {
          setStatus("homeMasterAddStatus", "ok", resultStatusText);
          await openMediaSearchDetailManage(masterId, createdOwnedItemId);
          return;
        }

        const skippedReason = String(skippedItems[0]?.reason || "").toLowerCase();
        if (skippedReason === "already_owned") {
          const fallbackOwned = (homeMasterInfo?.items || []).find(
            (row) => String(row.source_external_id || "").trim() === targetExternalId
          );
          const fallbackOwnedId = Number(fallbackOwned?.id || 0);
          if (fallbackOwnedId > 0) {
            setStatus("homeMasterAddStatus", "ok", resultStatusText);
            await openMediaSearchDetailManage(masterId, fallbackOwnedId);
            return;
          }
          // Already owned but couldn't find the item - show the result
          setStatus("homeMasterAddStatus", "ok", resultStatusText);
          return;
        }

        // Show error for non-already_owned skips, otherwise show success
        setStatus(
          "homeMasterAddStatus",
          skippedReason ? "err" : "ok",
          skippedReason
            ? t("media.manage.master.variant.status.skipped_reason", { reason: skippedReason })
            : resultStatusText
        );
      } catch (err) {
        setStatus("homeMasterAddStatus", "err", err.message);
      }
    }

    async function createHomeLinkedGoods() {
      const { masterId } = resolveHomeLinkedGoodsMasterContext();
      const category = $("homeLinkedGoodsCategory").value;
      const itemName = $("homeLinkedGoodsName").value.trim();
      const quantity = Math.max(1, Number($("homeLinkedGoodsQuantity").value || 1));
      $("homeLinkedGoodsQuantity").value = String(quantity);

      if (masterId <= 0) {
        setStatus("homeLinkedGoodsStatus", "err", t("media.manage.collectibles.status.master_required"));
        return;
      }
      if (!itemName) {
        setStatus("homeLinkedGoodsStatus", "err", t("media.manage.collectibles.status.item_name_required"));
        return;
      }
      const goodsImageUrls = homeLinkedGoodsImageEntries.length
        ? [...homeLinkedGoodsImageEntries]
        : splitLineList($("homeLinkedGoodsImageUrls").value);

      const payload = {
        category,
        size_group: $("homeLinkedGoodsSizeGroup").value,
        quantity,
        is_second_hand: false,
        status: "IN_COLLECTION",
        signature_type: "NONE",
        source_code: null,
        source_external_id: null,
        domain_code: null,
        release_type: null,
        linked_album_master_id: masterId,
        linked_artist_name: null,
        purchase_source: $("homeLinkedGoodsPurchaseSource").value.trim() || null,
        condition_grade: null,
        memory_note: `[LINKED_GOODS] album_master_id=${masterId}`,
        item_name_override: itemName,
        display_rank: null,
        storage_slot_id: null,
        subtype_option_ids: [],
        soundtrack_option_ids: [],
        goods_detail: {
          image_urls: goodsImageUrls,
          primary_image_url: goodsImageUrls.length ? goodsImageUrls[0] : null,
          poster_storage_spec: $("homeLinkedPosterStorageSpec").value.trim() || null,
          tshirt_size: $("homeLinkedTshirtSize").value.trim() || null,
          cup_material: $("homeLinkedCupMaterial").value.trim() || null,
          hat_size: $("homeLinkedHatSize").value.trim() || null
        }
      };

      try {
        setStatus("homeLinkedGoodsStatus", "ok", t("media.manage.collectibles.status.registering"));
        const res = await fetch("/owned-items", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.collectibles.status.register_failed"));
        setStatus("homeLinkedGoodsStatus", "ok", t("media.manage.collectibles.status.registered", { label_id: data.label_id }));
        await homeSearchOwnedItems();
        if (masterId > 0) {
          await loadHomeMasterMembers(masterId, { autoOpenFirst: false });
          await loadHomeMasterAddVariants();
        }
        await openMediaSearchDetailManage(masterId, Number(data.owned_item_id || 0));
      } catch (err) {
        setStatus("homeLinkedGoodsStatus", "err", err.message);
      }
    }

    async function openHomeMasterForEdit(albumMasterId) {
      const masterId = Number(albumMasterId || 0);
      if (!masterId) return;
      openAdminConsole("media", { remember: false, mediaMode: "manage" });

      const masterRow = homeSearchResults.find((row) => Number(row.id) === masterId);
      if (!masterRow) {
        setStatus("homeSearchStatus", "err", t("media.manage.search.status.master_not_found"));
        return;
      }

      homeSelectedMasterId = masterId;
      syncHomeMasterDeleteUi();
      homeSelectedItemId = null;
      homeSelectedSourceCode = null;
      homeSelectedSourceExternalId = null;
      homeEditShelfItems = [];
      homeEditShelfSelectedId = null;
      homeEditShelfPrevId = null;
      homeEditShelfNextId = null;
      clearHomeMetaCandidates();
      syncHomeLinkedSourceText();
      renderHomeSearchResults(homeSearchResults);
      renderHomeEditShelfTrack();
      syncHomeEditShelfNavButtons();
      renderHomeLocationInfo(null);
      renderHomeCollectorSummary(null);
      $("homeLinkedGoodsName").value = "";
      $("homeLinkedGoodsQuantity").value = "1";
      $("homeLinkedGoodsPurchaseSource").value = "";
      clearHomeLinkedGoodsImages();
      $("homeLinkedPosterStorageSpec").value = "";
      $("homeLinkedTshirtSize").value = "";
      $("homeLinkedCupMaterial").value = "";
      $("homeLinkedHatSize").value = "";
      syncHomeLinkedGoodsSpecVisibility();
      syncHomeLinkedGoodsMasterInfo();
      resetHomeMasterLookupUi({ clearInputs: true });
      setStatus("homeLinkedGoodsStatus", "ok", "");
      showHomeEditView();
      $("homeEditorSelectedLabel").textContent =
        t("media.manage.selected_album_label", {
          name: resolveAlbumMasterName(masterRow),
          id: masterRow.id,
        });
      setHtmlIfPresent("homeAcquisitionSourceInfo", "");
      setDisplayIfPresent("homeAcquisitionSourceInfo", "none");
      $("homeAcquisitionSourceInfo").textContent =
        t("media.manage.master.edit.source_summary", {
          source: masterRow.source_code || "-",
          source_master_id: masterRow.source_master_id || "-",
        });
      try {
        setStatus("homeEditStatus", "ok", t("media.manage.master.edit.status.loading_first_item"));
        const res = await fetch(`/album-masters/${masterId}/members`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.master.members.status.load_failed"));
        const firstOwnedItemId = Number((Array.isArray(data) ? data : [])[0]?.id || 0);
        if (firstOwnedItemId > 0) {
          await openMediaSearchDetailManage(masterId, firstOwnedItemId);
          return;
        }
        setStatus("homeEditStatus", "ok", t("media.manage.master.edit.status.no_linked_items"));
      } catch (err) {
        setStatus("homeEditStatus", "err", err.message);
      }
    }

    async function homeSearchOwnedItems(opts = {}) {
      const resetPage = Boolean(opts.resetPage);
      const allowPageAdjust = opts.allowPageAdjust !== false;
      const loadingStatusText = t("media.search.status.loading");
      if (resetPage) homeSearchPage = 1;
      homeSearchPageSize = Math.max(1, Math.min(500, Number($("homePageSize").value || homeSearchPageSize || 30)));

      const params = new URLSearchParams({
        limit: String(homeSearchPageSize),
        offset: String((homeSearchPage - 1) * homeSearchPageSize),
        include_total: "true",
        media_only: "true"
      });
      const artist = $("homeArtist").value.trim();
      const itemName = $("homeItemName").value.trim();
      const catalogNo = $("homeCatalogNo").value.trim();
      const barcode = $("homeBarcode").value.trim();
      const releaseYear = $("homeReleaseYear").value.trim();
      const sortMode = String($("homeSortMode").value || "CREATED_DESC").trim().toUpperCase() || "CREATED_DESC";
      const masterId = $("homeMasterId").value.trim();
      const ownedItemId = $("homeItemId").value.trim();
      const isLimited = $("homeLimitEd").checked;
      const isNew = $("homeNewProduct").checked;
      const isPromo = $("homePromo").checked;

      // Collect checked packaging values from the dynamic checkbox list
      const packagingVals = [];
      $("homePackagingList").querySelectorAll('input[type="checkbox"]:checked').forEach(cb => packagingVals.push(cb.value));
      // Collect checked package_contents values from the dynamic checkbox list
      const packageContentsVals = [];
      $("homePackageContentsList").querySelectorAll('input[type="checkbox"]:checked').forEach(cb => packageContentsVals.push(cb.value));

      const domainCode = String($("homeSearchDomain")?.value || "").trim().toUpperCase();
      if (domainCode) params.set("domain_code", domainCode);
      if (artist) params.set("artist_or_brand", artist);
      if (itemName) params.set("item_name", itemName);
      if (catalogNo) params.set("catalog_no", catalogNo);
      if (barcode) params.set("barcode", barcode);
      if (releaseYear) params.set("release_year", releaseYear);
      if (sortMode !== "CREATED_DESC") params.set("sort_mode", sortMode);
      if (masterId) params.set("album_master_id", masterId);
      if (ownedItemId) params.set("owned_item_id", ownedItemId);
      packagingVals.forEach(v => params.append("packaging", v));
      packageContentsVals.forEach(v => params.append("package_contents", v));
      if (isLimited) params.set("is_limited", "true");
      if (isNew) params.set("is_new", "true");
      if (isPromo) params.set("is_promo", "true");
      const ownershipStatus = $("homeOwnershipStatus")?.value || "";
      if (ownershipStatus) params.set("ownership_status", ownershipStatus);
      

      if ($("homeSigDirect").checked) params.append("signature_types", "IN_PERSON");
      if ($("homeSigPurchase").checked) params.append("signature_types", "PURCHASE_INCLUDED");

      try {
        setStatus("homeSearchStatus", "ok", loadingStatusText);
        const res = await fetchWithRetry(`/album-masters?${params.toString()}`, {}, {
          retries: 2,
          retryDelayMs: 250,
          onRetry: (attempt, total) => setStatus("homeSearchStatus", "ok", retryingStatusText(loadingStatusText, attempt, total)),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.search.status.load_failed"));

        const totalFromHeader = Number(res.headers.get("X-Total-Count"));
        homeSearchTotalCount = Number.isFinite(totalFromHeader) && totalFromHeader >= 0
          ? totalFromHeader
          : (Array.isArray(data) ? data.length : 0);
        homeSearchResults = Array.isArray(data) ? data : [];
        if (!homeSearchResults.some((row) => Number(row.id) === Number(homeSelectedMasterId))) {
          homeSelectedMasterId = null;
          syncHomeMasterDeleteUi();
        }
        const totalPages = Math.max(1, Math.ceil(homeSearchTotalCount / homeSearchPageSize));
        if (allowPageAdjust && homeSearchTotalCount > 0 && homeSearchPage > totalPages) {
          homeSearchPage = totalPages;
          await homeSearchOwnedItems({ allowPageAdjust: false });
          return;
        }

        renderHomeSearchResults(homeSearchResults);
        setDisplayIfPresent("homeNoResultCta", (homeSearchTotalCount || opts.suppressEmptyCta) ? "none" : "block");
        setStatus("homeSearchStatus", "ok", "");
        if (!homeSearchTotalCount) {
          clearHomeEditor();
        }
      } catch (err) {
        homeSelectedMasterId = null;
        syncHomeMasterDeleteUi();
        homeSearchResults = [];
        homeSearchTotalCount = 0;
        renderHomeSearchResults(homeSearchResults);
        setDisplayIfPresent("homeNoResultCta", "none");
        setStatus("homeSearchStatus", "err", err.message);
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

    function clearDashboardSlotAttention() {
      $("homeDashCabinetFloors")
        ?.querySelectorAll(".dashboard-floor-cell.attention")
        .forEach((node) => node.classList.remove("attention"));
      if (homeDashboardSlotAttentionTimer) {
        clearTimeout(homeDashboardSlotAttentionTimer);
        homeDashboardSlotAttentionTimer = null;
      }
    }

    function focusDashboardTargetSlot(slotCode, opts = {}) {
      const targetSlotCode = String(slotCode || "").trim();
      if (!targetSlotCode) return;
      const floorsRoot = $("homeDashCabinetFloors");
      const detailRoot = $("homeDashCabinetDetail");
      const slotItemsRoot = $("homeDashSlotItems");
      const smooth = opts.smooth !== false;
      const block = String(opts.block || "start");
      const targetRoot = slotItemsRoot || detailRoot;
      const focusTarget = () => {
        if (!targetRoot || typeof targetRoot.focus !== "function") return;
        if (!targetRoot.hasAttribute("tabindex")) targetRoot.setAttribute("tabindex", "-1");
        try {
          targetRoot.focus({ preventScroll: true });
        } catch {
          try { targetRoot.focus(); } catch {}
        }
      };
      const scrollTarget = () => {
        if (!targetRoot) return;
        if (block === "center") {
          const targetRect = targetRoot.getBoundingClientRect();
          const targetTop = window.scrollY + targetRect.top;
          const viewportOffset = Math.max((window.innerHeight - targetRect.height) / 2, 32);
          window.scrollTo({ top: Math.max(targetTop - viewportOffset, 0), behavior: smooth ? "smooth" : "auto" });
          return;
        }
        targetRoot.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block });
      };
      if (!floorsRoot) {
        scrollTarget();
        focusTarget();
        return;
      }
      const cell = Array.from(floorsRoot.querySelectorAll("[data-dashboard-slot-code]"))
        .find((node) => String(node.getAttribute("data-dashboard-slot-code") || "").trim() === targetSlotCode) || null;
      if (!cell) {
        scrollTarget();
        focusTarget();
        return;
      }
      clearDashboardSlotAttention();
      scrollTarget();
      focusTarget();
      cell.classList.add("attention");
      homeDashboardSlotAttentionTimer = window.setTimeout(() => {
        cell.classList.remove("attention");
        homeDashboardSlotAttentionTimer = null;
      }, 2200);
    }

    async function openDashboardForResolvedSlot(slotRow, opts = {}) {
      if (!slotRow) return;
      homeDashboardSlotGridFollowSelection = true;
      homeDashboardSelectedCabinetKey = dashboardCabinetKey(slotRow);
      homeDashboardSelectedSlotCode = String(slotRow.slot_code || "").trim();
      syncDashboardCabinetSelectionMemory();
      homeDashboardSlotItems = [];
      homeDashboardSlotItemsSlotCode = null;
      resetDashboardSlotPage();
      resetDashboardSlotSelection();
      renderDashboardSlotCards(homeDashboardBySlot, homeDashboardInCollectionItems);
      await loadDashboardSlotItems(slotRow, { silent: true });
      focusDashboardTargetSlot(slotRow.slot_code, { block: "end" });
      const slotLabel = storageSlotDisplayLabel(slotRow);
      const selectedWorkbenchRows = getDashboardSelectedWorkbenchRows();
      const cabinetMode = currentShellMode() === "cabinets";
      if (cabinetMode) {
        updateShellRoute("cabinets", {
          replaceHistory: true,
          cabinetSelection: normalizeCabinetRouteSelection(
            slotRow.cabinet_name,
            slotRow.column_code,
            slotRow.cell_code,
          ),
        });
      }
      const guideMessage = cabinetMode
        ? (opts.message || t("media.manage.location.status.opened_read_only", { slot: slotLabel }))
        : (
            selectedWorkbenchRows.length
              ? t("media.manage.location.status.opened_move_ready", { slot: slotLabel, count: formatCount(selectedWorkbenchRows.length) })
              : (opts.message || t("media.manage.location.status.opened_check_first", { slot: slotLabel }))
          );
      setStatus("homeDashboardStatus", "ok", guideMessage);
    }

    function findDashboardSlotByTriplet(cabinetName, columnCode, cellCode) {
      const selection = normalizeCabinetRouteSelection(cabinetName, columnCode, cellCode);
      if (!selection) return null;
      return homeDashboardBySlot.find((row) =>
        String(row?.cabinet_name || "").trim() === selection.cabinet_name
        && String(row?.column_code || "").trim() === selection.column_code
        && String(row?.cell_code || "").trim() === selection.cell_code
      ) || null;
    }

    async function applyPendingOpsCabinetSelection(opts = {}) {
      if (currentShellMode() !== "cabinets") return false;
      const selection = resolveCabinetRouteSelection(opts.selection) || pendingOpsCabinetSelection;
      if (!selection) return false;
      const slotRow = findDashboardSlotByTriplet(
        selection.cabinet_name,
        selection.column_code,
        selection.cell_code,
      );
      if (!slotRow) {
        pendingOpsCabinetSelection = null;
        homeDashboardSelectedCabinetKey = null;
        homeDashboardSelectedSlotCode = null;
        homeDashboardSlotItems = [];
        homeDashboardSlotItemsSlotCode = null;
        homeDashboardSlotItemsLoading = false;
        resetDashboardSlotPage();
        resetDashboardSlotSelection();
        renderDashboardCabinetDetail();
        if (!opts.silent) {
          setStatus("homeDashboardStatus", "err", t("media.manage.location.status.selection_not_found"));
        }
        return false;
      }
      pendingOpsCabinetSelection = null;
      await openDashboardForResolvedSlot(slotRow, {
        message: t("media.manage.location.status.opened_read_only", { slot: storageSlotDisplayLabel(slotRow) }),
      });
      return true;
    }

    async function openOpsCabinetView(cabinetName, columnCode, cellCode, options = {}) {
      const selection = normalizeCabinetRouteSelection(cabinetName, columnCode, cellCode);
      pendingOpsCabinetSelection = selection;
      switchShellMode("cabinets", {
        remember: false,
        pushHistory: options.pushHistory !== false,
        replaceHistory: options.replaceHistory === true,
        cabinetSelection: selection,
      });
      if (!homeDashboardBySlot.length) {
        await loadHomeDashboard({ silent: true });
      }
      if (!selection) {
        $("homeDashboardCard")?.scrollIntoView({ behavior: "smooth", block: "start" });
        return;
      }
      await applyPendingOpsCabinetSelection({ selection, silent: options.silent === true });
    }

    function findCabinetSelectionFromSlot(slotId, slotCode) {
      const directRow = getStorageSlotById(slotId)
        || getDashboardSlotRow(slotCode)
        || homeDashboardBySlot.find((item) => Number(item?.id || 0) === Number(slotId || 0))
        || null;
      if (!directRow) return null;
      return normalizeCabinetRouteSelection(
        directRow.cabinet_name,
        directRow.column_code,
        directRow.cell_code,
      );
    }

    async function openCabinetLocationAction(slotId, slotCode, cabinetName, columnCode, cellCode) {
      if (isAdminSession() && currentShellMode() === "admin") {
        await openDashboardForSlotLocation(slotId, slotCode);
        return;
      }
      const hasSlotRef = Number(slotId || 0) > 0 || Boolean(String(slotCode || "").trim());
      if (hasSlotRef && !homeDashboardBySlot.length) {
        await loadHomeDashboard({ silent: true });
      }
      const directRow = hasSlotRef ? (
        (Number(slotId || 0) > 0 ? homeDashboardBySlot.find((item) => Number(item?.id || 0) === Number(slotId || 0)) : null)
        || (String(slotCode || "").trim() ? homeDashboardBySlot.find((item) => String(item?.slot_code || "").trim() === String(slotCode || "").trim()) : null)
        || null
      ) : null;
      const directSelection = findCabinetSelectionFromSlot(slotId, slotCode);
      let selection = directSelection || normalizeCabinetRouteSelection(cabinetName, columnCode, cellCode);
      if (directRow) {
        switchShellMode("cabinets", { remember: false, pushHistory: true, replaceHistory: false });
        await openDashboardForResolvedSlot(directRow, {
          message: t("media.manage.location.status.opened_read_only", { slot: storageSlotDisplayLabel(directRow) }),
        });
        return;
      }
      await openOpsCabinetView(selection?.cabinet_name, selection?.column_code, selection?.cell_code);
      if (!selection && (Number(slotId || 0) > 0 || String(slotCode || "").trim())) {
        setStatus("homeDashboardStatus", "err", t("media.manage.location.status.slot_detail_missing"));
      }
    }

    async function openDashboardForCurrentLocation() {
      switchMainTab("home");
      if (!homeDashboardBySlot.length) {
        await loadHomeDashboard({ silent: true });
      }
      const slotId = Number($("editSlotId")?.value || 0);
      if (slotId <= 0) {
        setStatus("homeDashboardStatus", "ok", t("media.manage.location.status.current_unslotted"));
        $("homeDashboardCard")?.scrollIntoView({ behavior: "smooth", block: "start" });
        return;
      }
      const slotRow = homeDashboardBySlot.find((item) => Number(item?.id || 0) === slotId) || null;
      if (!slotRow) {
        setStatus("homeDashboardStatus", "err", t("media.manage.location.status.current_slot_missing"));
        return;
      }
      await openDashboardForResolvedSlot(slotRow, {
        message: t("media.manage.location.status.current_opened")
      });
    }

    async function openDashboardForSlotLocation(slotId, slotCode) {
      switchMainTab("cabinet");
      if (!homeDashboardBySlot.length) {
        await loadHomeDashboard({ silent: true });
      }
      const nextSlotId = Number(slotId || 0);
      const nextSlotCode = String(slotCode || "").trim();
      const slotRow = (
        (nextSlotId > 0 ? homeDashboardBySlot.find((item) => Number(item?.id || 0) === nextSlotId) : null)
        || (nextSlotCode ? homeDashboardBySlot.find((item) => String(item?.slot_code || "").trim() === nextSlotCode) : null)
        || null
      );
      if (!slotRow) {
        setStatus("homeDashboardStatus", "err", t("media.manage.location.status.dashboard_slot_missing"));
        return;
      }
      await openDashboardForResolvedSlot(slotRow);
    }

    async function loadDashboardWorkbenchRecommendations() {
      const rows = getDashboardWorkbenchRows();
      if (!rows.length) {
        setStatus("homeDashboardStatus", "err", t("dashboard.workbench.status.no_recommend_items"));
        return;
      }
      const selectedIds = Array.from(getDashboardWorkbenchSelectedIds()).map((v) => Number(v || 0)).filter((v) => v > 0);
      const ownedItemIds = (selectedIds.length ? selectedIds : rows.map((row) => Number(row?.id || 0)))
        .filter((v) => v > 0);
      if (!ownedItemIds.length) {
        setStatus("homeDashboardStatus", "err", t("dashboard.workbench.status.no_recommend_items"));
        return;
      }
      try {
        setStatus("homeDashboardStatus", "ok", t("dashboard.workbench.status.recommend_loading", { count: countWithUnit(ownedItemIds.length) }));
        const res = await fetch("/owned-items/location-recommendations", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ owned_item_ids: ownedItemIds }),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("dashboard.workbench.status.recommend_failed"));
        const map = {};
        for (const item of Array.isArray(data) ? data : []) {
          const ownedItemId = Number(item?.owned_item_id || 0);
          if (ownedItemId > 0) map[ownedItemId] = item;
        }
        homeDashboardWorkbenchRecommendations = {
          ...homeDashboardWorkbenchRecommendations,
          ...map,
        };
        renderDashboardWorkbench();
        setStatus("homeDashboardStatus", "ok", t("dashboard.workbench.status.recommend_done", { count: countWithUnit(Object.keys(map).length) }));
      } catch (err) {
        setStatus("homeDashboardStatus", "err", err.message);
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

    function syncHomeEditShelfNavButtons() {
      $("homeEditShelfPrevBtn").disabled = !homeEditShelfPrevId;
      $("homeEditShelfNextBtn").disabled = !homeEditShelfNextId;
    }

    function renderHomeEditShelfTrack() {
      const root = $("homeEditShelfTrack");
      if (!root) return;
      root.innerHTML = "";

      if (!homeEditShelfItems.length) {
        root.innerHTML = `<div class='shelf-empty'>${escapeHtml(t("media.manage.shelf.state.empty_layout"))}</div>`;
        setTextIfPresent("homeEditShelfCenterText", t("media.manage.location.center"));
        return;
      }

      const selectedIdx = homeEditShelfItems.findIndex((row) => Number(row.id) === Number(homeEditShelfSelectedId));
      for (let i = 0; i < homeEditShelfItems.length; i += 1) {
        const row = homeEditShelfItems[i];
        const distance = selectedIdx >= 0 ? i - selectedIdx : 0;
        const tilt = Math.max(-8, Math.min(8, distance * 1.7));
        const raise = Math.min(16, Math.abs(distance) * 2);
        const title = resolveOwnedAlbumName(row);
        const signatureBadge = signatureCoverBadgeHtml(row?.signature_type, "media-search-cover-signature-badge");

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
        if (Number(row.id) === Number(homeEditShelfSelectedId)) {
          card.classList.add("selected");
          card.style.zIndex = "70";
        }
        card.innerHTML = `
          ${signatureBadge}
          <span class="fmt">${escapeHtml(mediaDisplayLabel(row.format_name || row.category || "-"))}</span>
          <p class="cap">${escapeHtml(title)}</p>
        `;
        card.addEventListener("click", () => {
          openHomeOwnedItemFromManageContext(Number(row.id));
        });
        root.appendChild(card);
      }

      const centerItem = homeEditShelfItems.find((row) => Number(row.id) === Number(homeEditShelfSelectedId)) || homeEditShelfItems[0];
      setTextIfPresent(
        "homeEditShelfCenterText",
        t("media.manage.shelf.center.selected", {
          title: resolveOwnedAlbumName(centerItem),
          id: centerItem.id,
          order_key: centerItem.order_key || "-",
        })
      );
    }

    async function loadHomeEditShelfWindow(ownedItemId, fallbackRow, requestSeq = 0) {
      if (requestSeq && !isActiveHomeEditRequest(requestSeq)) return;
      const category = String(fallbackRow?.category || $("editCategory").value || "").toUpperCase();
      if (!ownedItemId || !MUSIC_CATEGORIES.has(category)) {
        homeEditShelfItems = [];
        homeEditShelfSelectedId = Number(ownedItemId || 0) || null;
        homeEditShelfPrevId = null;
        homeEditShelfNextId = null;
        renderHomeEditShelfTrack();
        syncHomeEditShelfNavButtons();
        setStatus("homeEditShelfStatus", "ok", t("media.manage.shelf.status.media_only"));
        renderHomeLocationInfo(fallbackRow || null);
        return;
      }

      try {
        setStatus("homeEditShelfStatus", "ok", t("media.manage.shelf.status.loading"));
        const res = await fetch(`/owned-items/${ownedItemId}/shelf-window?window=6`);
        const data = await safeJson(res);
        if (requestSeq && !isActiveHomeEditRequest(requestSeq)) return;
        if (!res.ok) throw new Error(data.detail || t("media.manage.shelf.status.load_failed"));

        homeEditShelfItems = Array.isArray(data.items) ? data.items : [];
        homeEditShelfSelectedId = Number(data.center_owned_item_id || ownedItemId);
        homeEditShelfPrevId = data.previous_owned_item_id ? Number(data.previous_owned_item_id) : null;
        homeEditShelfNextId = data.next_owned_item_id ? Number(data.next_owned_item_id) : null;
        renderHomeEditShelfTrack();
        syncHomeEditShelfNavButtons();
        const selected = homeEditShelfItems.find((row) => Number(row.id) === Number(homeEditShelfSelectedId));
        renderHomeLocationInfo(selected || fallbackRow || null);
        setStatus("homeEditShelfStatus", "ok", t("media.manage.shelf.status.load_done", { count: countWithUnit(homeEditShelfItems.length) }));
      } catch (err) {
        homeEditShelfItems = [];
        homeEditShelfSelectedId = Number(ownedItemId || 0) || null;
        homeEditShelfPrevId = null;
        homeEditShelfNextId = null;
        renderHomeEditShelfTrack();
        syncHomeEditShelfNavButtons();
        renderHomeLocationInfo(fallbackRow || null);
        setStatus("homeEditShelfStatus", "err", err.message);
      }
    }

    async function moveHomeEditShelf(direction) {
      if (direction < 0 && homeEditShelfPrevId) {
        await openHomeOwnedItemFromManageContext(homeEditShelfPrevId);
        return;
      }
      if (direction > 0 && homeEditShelfNextId) {
        await openHomeOwnedItemFromManageContext(homeEditShelfNextId);
        return;
      }
      setStatus("homeEditShelfStatus", "err", t("media.manage.shelf.status.no_adjacent_album"));
    }

    function homeRelatedVersionItemHtml(row, opts = {}) {
      const showDupControl = opts.showDupControl !== false;
      const categoryCode = String(row?.category || "").trim().toUpperCase();
      const isMusic = MUSIC_CATEGORIES.has(categoryCode);
      const title = resolveOwnedAlbumName(row);
      const coverUrl = resolveOwnedItemCoverUrl(row);
      const cover = coverUrl
        ? `<img src="${escapeHtml(coverUrl)}" alt="${escapeHtml(title)}" />`
        : escapeHtml(t("media.manage.related_versions.state.no_cover"));
      const releasedDate = String(row.released_date || row.release_year || "").trim() || "-";
      const barcodeText = String(row.barcode || "").trim();
      const labelCatText = `${row.label_name || "-"} / ${row.catalog_no || "-"}${barcodeText ? ` (${barcodeText})` : ""}`;
      const discogsLink = itemSourceLinkHtml(row.source_code, row.source_external_id);
      const purchaseSource = String(row.purchase_source || "").trim();
      const memoText = cleanLinkedGoodsMemoryNote(row.memory_note);
      const goodsMeta = [
        `${t("common.meta.category")}: ${mediaDisplayLabel(row.category || "-")}`,
        `${t("common.meta.storage_size")}: ${dashboardSizeGroupLabel(row.preferred_storage_size_group || row.size_group || "-")}`,
        purchaseSource ? `${t("common.meta.purchase_source")}: ${purchaseSource}` : "",
        row.status && row.status !== "IN_COLLECTION" ? `status: ${row.status}` : "",
      ].filter((v) => v);
      const dupControlHtml = showDupControl
        ? `
              <div class="home-related-dup-controls">
                ${row.barcode ? `<button class="btn ghost tiny home-meta-sync-btn" type="button" data-home-meta-sync="${row.id}" title="${escapeHtml(t("media.manage.search.action.sync_meta"))}">${escapeHtml(t("media.manage.search.action.sync_meta"))}</button>` : ""}
                <input
                  class="home-related-dup-count"
                  type="number"
                  min="1"
                  max="100"
                  value="1"
                  data-owned-id="${row.id}"
                  title="${escapeHtml(t("common.quantity.create_count"))}"
                />
                <button
                  class="btn ghost tiny home-related-dup-btn"
                  type="button"
                  data-owned-id="${row.id}"
                >${escapeHtml(t("common.action.add"))}</button>
                <button
                  class="btn ghost tiny home-related-del-btn"
                  type="button"
                  data-owned-id="${row.id}"
                >${escapeHtml(t("common.action.delete"))}</button>
              </div>
          `
        : `
              <div class="home-related-dup-controls">
                ${row.barcode ? `<button class="btn ghost tiny home-meta-sync-btn" type="button" data-home-meta-sync="${row.id}" title="${escapeHtml(t("media.manage.search.action.sync_meta"))}">${escapeHtml(t("media.manage.search.action.sync_meta"))}</button>` : ""}
                <div class="mini">${escapeHtml(t("common.item.same"))}</div>
              </div>
          `;
      return `
        <div
          class="result-item album-result home-related-item ${Number(row.id) === Number(homeSelectedItemId) ? "pick" : ""}"
          data-owned-id="${row.id}"
        >
          <div class="album-result-cover">${cover}</div>
          <div class="album-result-main">
            <strong>${escapeHtml(title)}</strong>
            <div class="result-meta">
              <span class="tag">${escapeHtml(mediaDisplayLabel(row.format_name || row.category || "-"))}</span>
              ${isMusic ? `
                <span>${escapeHtml(t("common.meta.release_date", { value: releasedDate }))}</span>
                <span>status: ${escapeHtml(row.status || "-")}</span>
                <span>order: ${escapeHtml(row.order_key || "-")}</span>
                <span data-role="label-cat">label/cat#: ${escapeHtml(labelCatText)}</span>
                ${discogsLink ? `<span>${discogsLink}</span>` : ""}
              ` : goodsMeta.map((text) => `<span>${escapeHtml(text)}</span>`).join("")}
            </div>
            <div class="row u-mt-4 u-flex-between-center-wrap">
              <div class="mini">
                owned_item_id: ${row.id} (${escapeHtml(t("media.manage.related_versions.state.click_to_open"))}) / 견출지: ${escapeHtml(String(row.label_id || "-"))}
                ${!isMusic && memoText ? ` / ${escapeHtml(t("media.manage.goods.meta.memo"))}: ${escapeHtml(memoText)}` : ""}
              </div>
              ${dupControlHtml}
            </div>
          </div>
        </div>
      `;
    }

    function homeMasterCollectibleItemHtml(row) {
      const goodsItemId = Number(row?.id || 0);
      const goodsName = String(row?.goods_name || "").trim() || "-";
      const imageUrl = String(
        row?.primary_image_url
        || (Array.isArray(row?.image_urls) ? row.image_urls[0] : "")
        || ""
      ).trim();
      const slotText = String(row?.slot_display_name || "").trim() || t("common.unspecified");
      const domainText = row?.domain_code ? dashboardDomainLabel(row.domain_code) : t("common.unspecified");
      const mappingText = Array.isArray(row?.artist_mappings) && row.artist_mappings.length
        ? row.artist_mappings.join(", ")
        : (
            Array.isArray(row?.label_mappings) && row.label_mappings.length
              ? row.label_mappings.join(", ")
              : "-"
          );
      return `
        <div
          class="goods-result-item home-master-collectible-item"
        >
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
              <span>${escapeHtml(dashboardSizeGroupLabel(row?.size_group || "GOODS"))}</span>
              <span>${escapeHtml(domainText)}</span>
            </div>
            <div class="row u-mt-4 u-flex-between-center-wrap">
              <div class="mini">
                collectible_id: ${goodsItemId} / ${escapeHtml(t("media.manage.collectibles.meta.mapping"))}: ${escapeHtml(mappingText)}
              </div>
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

    function groupHomeRelatedVersionItems(items) {
      const groups = [];
      const byKey = new Map();
      for (const row of items) {
        const copyGroupKey = String(row?.copy_group_key || "").trim();
        const groupKey = copyGroupKey ? `COPY:${copyGroupKey}` : `ITEM:${Number(row?.id || 0)}`;
        if (!byKey.has(groupKey)) {
          const group = {
            key: groupKey,
            copy_group_key: copyGroupKey || null,
            items: [],
          };
          byKey.set(groupKey, group);
          groups.push(group);
        }
        byKey.get(groupKey).items.push(row);
      }
      return groups;
    }

    function homeRelatedGroupHtml(group) {
      const rows = Array.isArray(group?.items) ? group.items : [];
      const count = rows.length;
      const copyGroupKey = String(group?.copy_group_key || "").trim();
      const isSameItemGroup = Boolean(copyGroupKey);
      const title = isSameItemGroup
        ? t("media.manage.related_versions.group.same", { count: formatCount(count), group: copyGroupKey })
        : t("media.manage.related_versions.group.individual", { count: formatCount(count) });
      return `
        <div class="home-copy-group ${isSameItemGroup ? "same" : ""}">
          <div class="home-copy-group-head">${escapeHtml(title)}</div>
          <div class="home-copy-group-items">
            ${rows.map((row, idx) => homeRelatedVersionItemHtml(
              row,
              { showDupControl: !isSameItemGroup || idx === 0 }
            )).join("")}
          </div>
        </div>
      `;
    }

    function renderHomeMasterMetaCard() {
      const card = $("homeMasterMetaCard");
      if (!card) return;
      if (!homeMasterInfo) {
        card.classList.add("u-hidden-initial");
        return;
      }
      // items[0]의 master_* 필드를 fallback으로 활용
      const firstItem = Array.isArray(homeMasterInfo?.items) ? homeMasterInfo.items[0] : null;
      const title  = homeMasterInfo.title  || firstItem?.master_title  || "-";
      const artist = homeMasterInfo.artist_or_brand || firstItem?.master_artist_or_brand || firstItem?.artist_or_brand || "-";
      const year   = homeMasterInfo.release_year
        || homeMasterInfo.source_release_year
        || firstItem?.master_release_year
        || firstItem?.release_year
        || null;
      // 커버: 현재 로드된 상품 우선 → 마스터 항목 중 첫 커버
      const rawCover =
        (typeof homeLoadedMusicDetail !== "undefined" && homeLoadedMusicDetail?.cover_image_url) ||
        (firstItem?.cover_image_url || "") ||
        "";
      const coverUrl = (typeof normalizeRenderableCoverUrl === "function")
        ? normalizeRenderableCoverUrl(rawCover)
        : rawCover;
      // 마스터 수준 링크: Discogs master / ManiaDB 앨범 (album_master.source_master_id 기반)
      const msc = String(homeMasterInfo.master_source_code || "").trim().toUpperCase();
      const msid = String(homeMasterInfo.master_source_id || "").trim();
      const masterLinkParts = [];
      if (msc === "DISCOGS" && msid) {
        masterLinkParts.push(discogsMasterLinkHtml(msid, "Discogs 마스터"));
      } else if (msc === "MANIADB" && msid) {
        masterLinkParts.push(maniadbAlbumLinkHtml(msid, "ManiaDB 마스터"));
      }
      // Count badges: 음반N 수집품N
      const metaItems = Array.isArray(homeMasterInfo?.items) ? homeMasterInfo.items : [];
      const metaMusic = metaItems.filter((r) => isMusicOwnedRow(r));
      const metaCollectibles = Array.isArray(homeMasterInfo?.collectibles) ? homeMasterInfo.collectibles : [];
      setTextIfPresent("homeMasterMetaTitleText", title);
      setHtmlIfPresent("homeMasterMetaTitleBadge", "");
      setHtmlIfPresent("homeMasterCountBadges", "");
      setTextIfPresent("homeMasterMetaArtist", artist);
      setTextIfPresent("homeMasterMetaYear", year ? `(${year})` : "");

      const masterIdVal = Number(homeMasterInfo?.album_master_id || 0);
      const idRowEl = $("homeMasterMetaIdRow");
      if (idRowEl) {
        if (masterIdVal > 0) { idRowEl.textContent = `album_master_id: ${masterIdVal}`; idRowEl.style.display = "block"; }
        else { idRowEl.style.display = "none"; }
      }

      const spEditRow = $("homeMasterMetaSpotifyEditRow");
      {
        const spId = String(homeMasterInfo?.spotify_album_id || "").trim();
        const spText = $("homeMasterMetaSpotifyText");
        if (spText) {
          if (spId) {
            spText.innerHTML = `Spotify: ${escapeHtml(spId)} <span class="spotify-badge" data-sp-master="${masterIdVal}" data-sp-album="${escapeHtml(spId)}" style="cursor:pointer;vertical-align:middle;">▶</span>`;
          } else {
            spText.textContent = "Spotify Album Code: -";
          }
        }
        if (!spEditRow || spEditRow.style.display === "none") {
          const spRow = $("homeMasterMetaSpotifyRow");
          if (spRow) spRow.style.display = "flex";
        }
      }

      // 로컬 경로 행
      (function() {
        const localRow = $("homeMasterLocalRow");
        const localEditRow = $("homeMasterLocalEditRow");
        const localStatus = $("homeMasterLocalStatus");
        if (!localRow) return;
        if (localEditRow && localEditRow.style.display !== "none") return; // 편집 중이면 갱신 안 함
        fetchWithRetry(`/album-masters/${masterIdVal}/local-player`).then(async res => {
          if (!res.ok) { localRow.style.display = "none"; return; }
          const data = await safeJson(res);
          const localText = $("homeMasterLocalText");
          if (data.linked) {
            const short = data.dir_path.replace(/^\/Volumes\/Music\//, "…/");
            if (localText) { localText.textContent = `♪ Local: ${short}`; localText.style.cursor = "pointer"; }
            localRow.style.display = "flex";
          } else {
            if (localText) { localText.textContent = "♪ Local: 미연결"; localText.style.cursor = ""; }
            localRow.style.display = "flex";
          }
          if (localStatus) localStatus.textContent = "";
        }).catch(() => { localRow.style.display = "none"; });
      })();

      (function() {
        const firstItem = metaMusic[0] || metaItems[0] || null;
        const genres = Array.isArray(firstItem?.genres) ? firstItem.genres : [];
        const styles = Array.isArray(firstItem?.styles) ? firstItem.styles : [];
        const combined = [...genres, ...styles.filter(s => !genres.includes(s))];
        const el = $("homeMasterMetaGenreRow");
        if (!el) return;
        if (combined.length) { el.textContent = `장르/스타일: ${combined.join(", ")}`; el.style.display = "block"; }
        else { el.style.display = "none"; }
      })();

      const linkRowEl = $("homeMasterMetaLinkRow");
      if (linkRowEl) {
        linkRowEl.textContent = `연계 구성: 음반 ${metaMusic.length}, 수집품 ${metaCollectibles.length}`;
        linkRowEl.style.display = "block";
      }

      (function() {
        const srcItem = (homeSelectedItemId
          ? metaMusic.find((r) => Number(r.id || 0) === Number(homeSelectedItemId || 0))
          : null) || metaMusic[0] || null;
        const el = $("homeAcquisitionSourceInfo");
        const linkEl = $("homeAcquisitionSourceLink");
        if (!el) return;
        if (!srcItem) {
          el.innerHTML = ""; el.style.display = "none";
          if (linkEl) { linkEl.textContent = ""; linkEl.style.display = "none"; }
          return;
        }
        const sc = String(srcItem.source_code || "").trim().toUpperCase();
        const sid = String(srcItem.source_external_id || "").trim();
        const createdAt = String(srcItem.created_at || "").trim();
        const srcLabel = sc === "DISCOGS" ? "Discogs" : sc === "MANIADB" ? "ManiaDB" : sc === "ALADIN" ? "Aladin" : sc || null;
        if (srcLabel || sid) {
          let idHtml = escapeHtml(sid);
          if (sc === "DISCOGS" && sid) idHtml = `<a href="https://www.discogs.com/release/${encodeURIComponent(sid)}" target="_blank" rel="noreferrer noopener">${escapeHtml(sid)}</a>`;
          else if (sc === "MANIADB" && sid) idHtml = `<a href="https://www.maniadb.com/album/${encodeURIComponent(sid.split(":")[0])}" target="_blank" rel="noreferrer noopener">${escapeHtml(sid)}</a>`;
          el.innerHTML = `소스: ${[srcLabel, idHtml].filter(Boolean).join(" / ")}`;
          el.style.display = "block";
        } else { el.innerHTML = ""; el.style.display = "none"; }
        if (linkEl) {
          if (createdAt) { linkEl.textContent = `생성: ${createdAt}`; linkEl.style.display = "block"; }
          else { linkEl.textContent = ""; linkEl.style.display = "none"; }
        }
      })();

      card.classList.remove("u-hidden-initial");
    }

    function renderHomeRelatedVersions() {
      parkHomeMasterInlineEditor();
      if (!homeMasterInfo) {
        setHtmlIfPresent("homeMasterRelatedList", homeMasterRelatedPlaceholderHtml());
        setHtmlIfPresent("homeMasterCountBadges", "");
        setDisplayIfPresent("homeMasterSummarySection", "none");
        renderHomeMasterMetaCard();
        renderHomeLinkedCollectiblesSection();
        syncHomeMasterLookupPromptState();
        syncHomeMasterInlineEditor();
        syncHomeMasterCorrectionEditor();
        syncHomeLinkedGoodsMasterInfo();
        return;
      }

      const items = Array.isArray(homeMasterInfo.items) ? homeMasterInfo.items : [];
      const musicItems = items.filter((row) => isMusicOwnedRow(row));
      const collectibles = Array.isArray(homeMasterInfo.collectibles) ? homeMasterInfo.collectibles : [];

      setDisplayIfPresent("homeMasterSummarySection", "block");
      renderHomeMasterMetaCard();
      renderHomeLinkedCollectiblesSection();
      syncHomeMasterCorrectionEditor();
      syncHomeMasterSortArtistEditor();
      if (!items.length && !collectibles.length) {
        setHtmlIfPresent("homeMasterRelatedList", `<div class='muted'>${escapeHtml(t("media.manage.related_versions.state.empty_versions"))}</div>`);
        renderHomeLinkedCollectiblesSection();
        syncHomeMasterInlineEditor();
        syncHomeMasterCorrectionEditor();
        syncHomeMasterSortArtistEditor();
        syncHomeLinkedGoodsMasterInfo();
        return;
      }
      const musicGroups = groupHomeRelatedVersionItems(musicItems);
      setHtmlIfPresent("homeMasterRelatedList", musicGroups.length
        ? musicGroups.map(homeRelatedGroupHtml).join("")
        : `<div class='muted'>${escapeHtml(t("media.manage.related_versions.state.empty_music_versions"))}</div>`);
      renderHomeLinkedCollectiblesSection();
      syncHomeMasterLookupPromptState();
      mountHomeMasterInlineEditor();
      syncHomeMasterInlineEditor();
      syncHomeMasterCorrectionEditor();
      syncHomeMasterSortArtistEditor();
      syncHomeLinkedGoodsMasterInfo();
    }

    async function saveHomeMasterCorrection() {
      const masterId = Number(
        homeMasterInfo?.album_master_id ||
        homeSelectedMasterId ||
        $("editLinkedAlbumMasterId")?.value ||
        0
      );
      if (masterId <= 0) {
        setStatus("homeMasterCorrectionStatus", "err", t("media.manage.master.correction.status.master_required"));
        return;
      }
      const releaseYearText = $("homeMasterCorrectionReleaseYear")?.value.trim() || "";
      const releaseYearNumber = releaseYearText ? Number(releaseYearText) : null;
      if (releaseYearText && (!Number.isInteger(releaseYearNumber) || releaseYearNumber < 1900 || releaseYearNumber > 2100)) {
        setStatus("homeMasterCorrectionStatus", "err", t("media.manage.master.correction.status.invalid_release_year"));
        return;
      }
      const releaseYearValue = releaseYearText ? releaseYearNumber : null;
      const domainCodeValue = String($("homeMasterCorrectionDomainCode")?.value || "").trim().toUpperCase() || null;
      const overrideNoteValue = $("homeMasterCorrectionNote")?.value.trim() || null;
      const overrideTitleValue = $("homeMasterCorrectionTitle")?.value.trim() || null;
      const overrideArtistValue = $("homeMasterCorrectionArtist")?.value.trim() || null;
      const genresValue = splitCommaList($("homeMasterCorrectionGenres")?.value || "");
      const stylesValue = splitCommaList($("homeMasterCorrectionStyles")?.value || "");
      const releaseTypeValue = String($("homeMasterCorrectionReleaseType")?.value || "").trim().toUpperCase() || null;
      try {
        setStatus("homeMasterCorrectionStatus", "ok", t("media.manage.master.correction.status.saving"));
        const res = await fetch(`/album-masters/${masterId}/correction`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            release_year: releaseYearValue,
            domain_code: domainCodeValue,
            override_note: overrideNoteValue,
            override_title: overrideTitleValue,
            override_artist_or_brand: overrideArtistValue,
            genres: genresValue,
            styles: stylesValue,
            release_type: releaseTypeValue,
          }),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("media.manage.master.correction.status.save_failed")));
        if (homeMasterInfo && Number(homeMasterInfo.album_master_id || 0) === masterId) {
          homeMasterInfo.release_year = data.release_year || null;
          homeMasterInfo.domain_code = data.domain_code || null;
          homeMasterInfo.source_release_year = data.source_release_year || null;
          homeMasterInfo.source_domain_code = data.source_domain_code || null;
          homeMasterInfo.override_release_year = data.override_release_year || null;
          homeMasterInfo.override_domain_code = data.override_domain_code || null;
          homeMasterInfo.override_note = data.override_note || null;
          homeMasterInfo.override_title = data.override_title || null;
          homeMasterInfo.override_artist_or_brand = data.override_artist_or_brand || null;
          homeMasterInfo.release_type = data.release_type || null;
          if (data.override_title) homeMasterInfo.title = data.override_title;
          if (data.override_artist_or_brand) homeMasterInfo.artist_or_brand = data.override_artist_or_brand;
          homeMasterInfo.has_manual_correction = Boolean(data.has_manual_correction);
        }
        const masterRow = Array.isArray(homeSearchResults)
          ? homeSearchResults.find((row) => Number(row?.id || 0) === masterId)
          : null;
        if (masterRow) {
          masterRow.release_year = data.release_year || null;
          masterRow.domain_code = data.domain_code || null;
        }
        renderHomeRelatedVersions();
        if (Number(homeSelectedItemId || 0) > 0) {
          await refreshHomeManageContext(Number(homeSelectedItemId), {
            keepMasterContext: Boolean(homeSelectedMasterId),
            masterId,
            reloadMaster: true,
          });
        }
        loadHomeDashboard({ silent: true }).catch(() => {});
        setStatus(
          "homeMasterCorrectionStatus",
          "ok",
          data.has_manual_correction
            ? t("media.manage.master.correction.status.saved")
            : t("media.manage.master.correction.status.cleared")
        );
      } catch (err) {
        setStatus("homeMasterCorrectionStatus", "err", err.message);
      }
    }

    async function linkHomeMasterSpotify() {
      const masterId = Number(homeMasterInfo?.album_master_id || homeSelectedMasterId || 0);
      if (masterId <= 0) {
        setStatus("homeMasterSpotifyMatchStatus", "err", t("media.manage.master.correction.status.master_required"));
        return;
      }
      const spotifyId = $("homeMasterSpotifyMatchId")?.value.trim() || "";
      if (!spotifyId) {
        setStatus("homeMasterSpotifyMatchStatus", "err", "Spotify Album ID를 입력해주세요.");
        return;
      }
      try {
        setStatus("homeMasterSpotifyMatchStatus", "ok", "연결 중...");
        const res = await fetch(`/album-masters/${masterId}/spotify/match`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ spotify_album_id: spotifyId }),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
        setStatus("homeMasterSpotifyMatchStatus", "ok", "연결되었습니다.");
        if (homeMasterInfo && Number(homeMasterInfo.album_master_id || 0) === masterId) {
          homeMasterInfo.spotify_album_id = spotifyId;
          homeMasterInfo.spotify_album_uri = `spotify:album:${spotifyId}`;
        }
        renderHomeMasterMetaCard();
      } catch (err) {
        setStatus("homeMasterSpotifyMatchStatus", "err", "연결 실패: " + err.message);
      }
    }

    async function unlinkHomeMasterSpotify() {
      const masterId = Number(homeMasterInfo?.album_master_id || homeSelectedMasterId || 0);
      if (masterId <= 0) {
        setStatus("homeMasterSpotifyMatchStatus", "err", t("media.manage.master.correction.status.master_required"));
        return;
      }
      if (!confirm("Spotify 연결을 해제할까요?")) return;
      try {
        setStatus("homeMasterSpotifyMatchStatus", "ok", "해제 중...");
        const res = await fetch(`/album-masters/${masterId}/spotify/match`, {
          method: "DELETE",
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
        setStatus("homeMasterSpotifyMatchStatus", "ok", "해제되었습니다.");
        const input = $("homeMasterSpotifyMatchId");
        if (input) input.value = "";
        if (homeMasterInfo && Number(homeMasterInfo.album_master_id || 0) === masterId) {
          homeMasterInfo.spotify_album_id = null;
          homeMasterInfo.spotify_album_uri = null;
        }
        renderHomeMasterMetaCard();
      } catch (err) {
        setStatus("homeMasterSpotifyMatchStatus", "err", "해제 실패: " + err.message);
      }
    }

    async function saveHomeMasterSortArtistName() {
      const masterId = Number(
        homeMasterInfo?.album_master_id ||
        homeSelectedMasterId ||
        $("editLinkedAlbumMasterId")?.value ||
        0
      );
      if (masterId <= 0) {
        setStatus("homeMasterSortArtistStatus", "err", t("media.manage.master.sort_artist.status.master_required"));
        return;
      }
      const sortArtistName = $("homeMasterSortArtistName")?.value.trim() || "";
      try {
        setStatus("homeMasterSortArtistStatus", "ok", t("media.manage.master.sort_artist.status.saving"));
        const res = await fetch(`/album-masters/${masterId}/sort-artist-name`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sort_artist_name: sortArtistName || null }),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("media.manage.master.sort_artist.status.save_failed")));
        if (homeMasterInfo && Number(homeMasterInfo.album_master_id || 0) === masterId) {
          homeMasterInfo.sort_artist_name = data.sort_artist_name || null;
        }
        const masterRow = Array.isArray(homeSearchResults)
          ? homeSearchResults.find((row) => Number(row?.id || 0) === masterId)
          : null;
        if (masterRow) {
          masterRow.sort_artist_name = data.sort_artist_name || null;
        }
        renderHomeRelatedVersions();
        if (Number(homeSelectedItemId || 0) > 0) {
          await refreshHomeManageContext(Number(homeSelectedItemId), {
            keepMasterContext: Boolean(homeSelectedMasterId),
            masterId,
            reloadMaster: true,
          });
        }
        loadHomeDashboard({ silent: true }).catch(() => {});
        setStatus(
          "homeMasterSortArtistStatus",
          "ok",
          data.sort_artist_name
            ? t("media.manage.master.sort_artist.status.saved", { name: data.sort_artist_name })
            : t("media.manage.master.sort_artist.status.cleared")
        );
      } catch (err) {
        setStatus("homeMasterSortArtistStatus", "err", err.message);
      }
    }

    async function saveDashboardSelectedSortArtistName() {
      const selectionSourceKind = getDashboardSelectionSourceKind();
      const selectedRow = getDashboardSingleSelectedRowBySourceKind(selectionSourceKind);
      const activeEditor = getActiveDashboardSelectedSortArtistEditor();
      if (!activeEditor) {
        setStatus("homeDashSelectedSortArtistStatus", "err", t("media.manage.master.sort_artist.status.master_required"));
        return;
      }
      const masterId = Number(selectedRow?.linked_album_master_id || selectedRow?.album_master_id || 0);
      if (masterId <= 0) {
        setStatus(activeEditor.statusId, "err", t("media.manage.master.sort_artist.status.master_required"));
        return;
      }
      const sortArtistName = activeEditor?.input?.value.trim() || "";
      try {
        setStatus(activeEditor.statusId, "ok", t("media.manage.master.sort_artist.status.saving"));
        const res = await fetch(`/album-masters/${masterId}/sort-artist-name`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sort_artist_name: sortArtistName || null }),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("media.manage.master.sort_artist.status.save_failed")));
        updateDashboardMasterSortArtistNameLocally(masterId, data.sort_artist_name || null);
        updateDashboardSlotSelectionSnapshot();
        homeDashboardWorkbenchSuppressSelectionScrollOnce = selectionSourceKind === "UNASSIGNED" || selectionSourceKind === "SEARCH";
        renderDashboardSelectionSummary();
        renderDashboardSlotItems(getDashboardSlotRow(homeDashboardSelectedSlotCode));
        renderDashboardWorkbench();
        setStatus(
          activeEditor.statusId,
          "ok",
          data.sort_artist_name
            ? t("media.manage.master.sort_artist.status.saved", { name: data.sort_artist_name })
            : t("media.manage.master.sort_artist.status.cleared")
        );
      } catch (err) {
        setStatus(activeEditor.statusId, "err", err.message);
      }
    }

    async function duplicateHomeRelatedItem(ownedItemId, count = 1) {
      const targetOwnedItemId = Number(ownedItemId || 0);
      const masterId = Number(homeSelectedMasterId || 0);
      const duplicateCount = Math.max(1, Math.min(100, Number(count || 1)));
      if (!masterId) {
        setStatus("homeMasterStatus", "err", t("media.manage.master.item.duplicate.required_master"));
        return;
      }
      if (!targetOwnedItemId) {
        setStatus("homeMasterStatus", "err", t("media.manage.master.item.duplicate.required_item"));
        return;
      }
      try {
        setStatus("homeMasterStatus", "ok", t("media.manage.master.item.duplicate.progress", {
          owned_item_id: targetOwnedItemId,
          count: duplicateCount,
        }));
        const res = await fetch(`/owned-items/${targetOwnedItemId}/duplicate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ count: duplicateCount })
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.master.item.duplicate.failed"));
        const createdIds = Array.isArray(data.created_ids) ? data.created_ids : [];
        const nextOwnedItemId = Number(createdIds[0] || 0);
        if (createdIds.length) {
          const masterListRow = homeSearchResults.find((row) => Number(row.id) === masterId);
          if (masterListRow) {
            const prevCount = Number(masterListRow.member_count || 0);
            masterListRow.member_count = Math.max(prevCount, prevCount + createdIds.length);
          }
          renderHomeSearchResults(homeSearchResults);
        }
        await loadHomeMasterMembers(masterId, { autoOpenFirst: false });
        await loadHomeMasterAddVariants();
        setStatus(
          "homeMasterStatus",
          "ok",
          t("media.manage.master.item.duplicate.done", {
            count: countWithUnit(createdIds.length || 0),
            first_id: nextOwnedItemId > 0
              ? t("media.manage.master.item.duplicate.first_id", { owned_item_id: nextOwnedItemId })
              : "",
          })
        );
        if (nextOwnedItemId > 0) {
          await openMediaSearchDetailManage(masterId, nextOwnedItemId);
        }
      } catch (err) {
        setStatus("homeMasterStatus", "err", err.message);
      }
    }

    async function deleteHomeRelatedItem(ownedItemId) {
      const targetOwnedItemId = Number(ownedItemId || 0);
      if (!targetOwnedItemId) {
        setStatus("homeMasterStatus", "err", t("media.manage.master.item.delete.required"));
        return;
      }

      const relatedItems = Array.isArray(homeMasterInfo?.items) ? homeMasterInfo.items : [];
      const row = relatedItems.find((v) => Number(v.id) === targetOwnedItemId) || null;
      const itemName = row ? resolveOwnedAlbumName(row) : `owned_item_id=${targetOwnedItemId}`;
      const labelId = String(row?.label_id || "-");
      const ok = window.confirm(
        t("media.manage.master.item.delete.confirm", {
          item_name: itemName,
          label_id: labelId,
          owned_item_id: targetOwnedItemId,
        })
      );
      if (!ok) {
        setStatus("homeMasterStatus", "ok", t("media.manage.edit.status.delete_cancelled"));
        return;
      }

      try {
        setStatus("homeMasterStatus", "ok", t("media.manage.product.delete.progress", { owned_item_id: targetOwnedItemId }));
        const res = await fetch(`/owned-items/${targetOwnedItemId}`, { method: "DELETE" });
        const data = await safeJson(res);
        const masterId = Number(homeSelectedMasterId || homeMasterInfo?.album_master_id || 0);
        if (!res.ok) {
          if (res.status === 404) {
            if (masterId > 0) {
              await openHomeMasterForEdit(masterId);
            } else {
              resetHomeMasterLookupUi({ clearInputs: true });
            }
            setStatus("homeMasterStatus", "ok", t("media.manage.master.item.delete.already_gone", { owned_item_id: targetOwnedItemId }));
            return;
          }
          throw new Error(data.detail || t("media.manage.edit.status.delete_failed"));
        }

        if (masterId > 0) {
          await openHomeMasterForEdit(masterId);
        } else if (Number(homeSelectedItemId) === targetOwnedItemId) {
          clearHomeEditor();
        }

        await homeSearchOwnedItems();
        await loadHomeDashboard();
        const deletedId = Number(data.owned_item_id || targetOwnedItemId);
        setStatus("homeMasterStatus", "ok", t("media.manage.master.item.delete.done", { owned_item_id: deletedId }));
        setStatus("homeEditStatus", "ok", t("media.manage.master.item.delete.done", { owned_item_id: deletedId }));
      } catch (err) {
        setStatus("homeMasterStatus", "err", err.message);
      }
    }

    async function loadHomeRelatedVersions(ownedItemId, requestSeq = 0) {
      if (requestSeq && !isActiveHomeEditRequest(requestSeq)) return;
      if (!ownedItemId) {
        homeMasterInfo = null;
        renderHomeRelatedVersions();
        setStatus("homeMasterStatus", "ok", "");
        return;
      }

      try {
        setStatus("homeMasterStatus", "ok", t("media.manage.related_versions.status.loading"));
        const res = await fetch(`/owned-items/${ownedItemId}/related-versions`);
        const data = await safeJson(res);
        if (requestSeq && !isActiveHomeEditRequest(requestSeq)) return;
        if (!res.ok) throw new Error(data.detail || t("media.manage.related_versions.status.load_failed"));
        homeMasterInfo = data;
        renderHomeRelatedVersions();
        const relatedCount = Array.isArray(data.items) ? data.items.length : 0;
        setStatus("homeMasterStatus", "ok", t("media.manage.related_versions.status.loaded", { count: countWithUnit(relatedCount) }));
      } catch (err) {
        homeMasterInfo = null;
        renderHomeRelatedVersions();
        setStatus("homeMasterStatus", "err", err.message);
      }
    }

    async function hydrateHomeEditorSecondaryPanels(locationSeed, requestSeq = 0) {
      if (requestSeq && !isActiveHomeEditRequest(requestSeq)) return;
      const panelLoads = [
        loadHomeEditShelfWindow(homeSelectedItemId, locationSeed, requestSeq),
        loadHomeOwnedItemRelations(homeSelectedItemId, requestSeq),
      ];
      if (homeSelectedMasterId) renderHomeRelatedVersions();
      await Promise.all(panelLoads);
      if (requestSeq && !isActiveHomeEditRequest(requestSeq)) return;
      scheduleHomeCollectorSummaryRefresh(requestSeq);
    }

    function scheduleHomeCollectorSummaryRefresh(requestSeq = 0) {
      const run = () => {
        if (requestSeq && !isActiveHomeEditRequest(requestSeq)) return;
        void loadHomeCollectorSummary(requestSeq);
      };
      if (typeof window.requestIdleCallback === "function") {
        window.requestIdleCallback(run, { timeout: 400 });
        return;
      }
      window.setTimeout(run, 0);
    }

    function scheduleHomeEditorSecondaryHydration(locationSeed, requestSeq = 0) {
      requestAnimationFrame(() => {
        if (requestSeq && !isActiveHomeEditRequest(requestSeq)) return;
        void hydrateHomeEditorSecondaryPanels(locationSeed, requestSeq);
      });
    }

    async function applyHomeEditorDetail(data, requestSeq = 0) {
      if (requestSeq && !isActiveHomeEditRequest(requestSeq)) return;
      homeSelectedItemId = Number(data.id);
      homeInlineEditorCollapsed = false;
      homeSelectedSourceCode = data.source_code || null;
      homeSelectedSourceExternalId = data.source_external_id || null;
      homeOwnedItemRelationView = null;
      homeOwnedItemRelationMasterEntries = [];
      homeOwnedItemEditableRelations = [];
      if ($("homeProductRelationSeriesQuery")) $("homeProductRelationSeriesQuery").value = "";
      if ($("homeProductRelationReleaseQuery")) $("homeProductRelationReleaseQuery").value = "";
      if ($("homeProductRelationNote")) $("homeProductRelationNote").value = "";
      if ($("homeProductRelationType")) $("homeProductRelationType").value = "BOX_MEMBER_OF";
      setHtmlIfPresent("homeProductRelationSeriesResults", "");
      setHtmlIfPresent("homeProductRelationReleaseResults", "");
      setStatus("homeProductRelationStatus", "", "");
      homeLoadedMusicDetail = data.music_detail && typeof data.music_detail === "object"
        ? JSON.parse(JSON.stringify(data.music_detail))
        : null;

      if ($("editOwnedId")) $("editOwnedId").value = String(data.id || "");
      if ($("editLabelId")) $("editLabelId").value = String(data.label_id || "");
      $("editCategory").value = data.category || "LP";
      $("editItemName").value = data.item_name_override || "";
      $("editSizeGroup").value = data.size_group || defaultSizeGroupForCategory(data.category);
      $("editPreferredStorageSizeGroup").value = data.preferred_storage_size_group || data.size_group || defaultSizeGroupForCategory(data.category);
      $("editReleaseType").value = data.release_type || "";
      $("editLinkedAlbumMasterId").value = data.linked_album_master_id ? String(data.linked_album_master_id) : "";
      $("editLinkedArtistName").value = data.linked_artist_name || "";
      $("editStatus").value = data.status || "IN_COLLECTION";
      $("editSignatureType").value = data.signature_type || "NONE";
      $("editSlotId").value = data.storage_slot_id ? String(data.storage_slot_id) : "";
      $("editPurchasePrice").value = data.purchase_price ?? "";
      $("editCurrencyCode").value = data.currency_code || "KRW";
      $("editPurchaseSource").value = data.purchase_source || "";
      $("editConditionGrade").value = data.condition_grade || "";
      $("editDisplayRank").value = data.display_rank ?? "";
      $("editMemoryNote").value = data.memory_note || "";
      $("editIsSecondHand").checked = !Boolean(data.is_second_hand);  // 새상품 여부: checked = 새상품 = NOT second_hand
      $("editPromoNfs").checked = Boolean(data.music_detail?.is_promotional_not_for_sale);

      $("editFormatName").value = data.music_detail?.format_name || "";
      $("editArtistName").value = data.music_detail?.artist_or_brand || "";
      $("editReleasedDate").value = data.music_detail?.released_date || "";
      $("editBarcode").value = data.music_detail?.barcode || "";
      $("editLabelName").value = data.music_detail?.label_name || "";
      $("editCatalogNo").value = data.music_detail?.catalog_no || "";
      $("editDiscCount").value = data.music_detail?.disc_count ?? "";
      $("editSpeedRpm").value = data.music_detail?.speed_rpm ?? "";
      if ($("editDiscType")) $("editDiscType").value = data.music_detail?.disc_type ?? "";
      _loadPackageContents(data.music_detail?.package_contents || "");
      $("editIsLimitedEdition").checked = Boolean(data.music_detail?.is_limited_edition);
      $("editEditionNumber").value = data.music_detail?.edition_number || "";
      setHiddenIfPresent("editEditionNumberWrap", !$("editIsLimitedEdition").checked);
      $("editHasObi").checked = Boolean(data.music_detail?.has_obi);
      $("editRunoutMatrix").value = joinRunoutList(data.music_detail?.runout_matrix || []);
      $("editPressingCountry").value = data.music_detail?.pressing_country || "";
      $("editMediaType").value = data.music_detail?.media_type || "";
      _syncVinylOnlyFields();
      setConditionSelectValue("editCoverCondition", data.music_detail?.cover_condition || "");
      setConditionSelectValue("editDiscCondition", data.music_detail?.disc_condition || "");
      $("editCoverImageUrl").value = data.music_detail?.cover_image_url || "";
      loadEditLocalImages(data.local_image_items || []);
      {
        const tl = Array.isArray(data.music_detail?.track_list) ? data.music_detail.track_list : [];
        const ti = Array.isArray(data.music_detail?.track_items) ? data.music_detail.track_items : [];
        const tiToText = (items) => items.map((row) => {
          const pos = String(row.position || "").trim();
          const title = String(row.title || "").trim();
          const dur = String(row.duration || "").trim();
          return [pos, title, dur].filter(Boolean).join(" ");
        }).join("\n");
        // Prefer track_items when they have meaningful positions (disc-track / vinyl alpha)
        const hasRichPos = ti.some((row) => /\d+-\d+|[A-Za-z]-\d+|[A-Ga-g]\d/i.test(String(row.position || "")));
        if (ti.length && hasRichPos) {
          $("editTrackList").value = tiToText(ti);
        } else if (tl.length) {
          $("editTrackList").value = tl.join("\n");
        } else if (ti.length) {
          $("editTrackList").value = tiToText(ti);
        } else {
          $("editTrackList").value = "";
        }
      }
      const goodsImages = Array.isArray(data.goods_detail?.image_urls) ? data.goods_detail.image_urls : [];
      const goodsPrimary = String(data.goods_detail?.primary_image_url || "").trim();
      $("editGoodsImageUrls").value = joinLineList(goodsImages.length ? goodsImages : (goodsPrimary ? [goodsPrimary] : []));
      $("editPosterStorageSpec").value = data.goods_detail?.poster_storage_spec || "";
      $("editTshirtSize").value = data.goods_detail?.tshirt_size || "";
      $("editCupMaterial").value = data.goods_detail?.cup_material || "";
      $("editHatSize").value = data.goods_detail?.hat_size || "";
      $("homeMetaSource").value = "AUTO";
      $("homeMetaBarcode").value = data.music_detail?.barcode || "";
      $("homeMetaQuery").value = [data.music_detail?.artist_or_brand, data.item_name_override, data.music_detail?.catalog_no]
        .filter((v) => String(v || "").trim())
        .join(" ")
        .trim();
      clearHomeMetaCandidates();
      syncHomeLinkedSourceText();
      $("homeEditorSelectedLabel").textContent = t("media.manage.selected_item_label", {
        name: resolveOwnedAlbumName(data),
        id: data.id,
      });
      syncHomeEditorMusicVisibility();
      syncHomeLinkedGoodsMasterInfo();
      syncHomeMasterInlineEditor();
      syncHomeRelatedSelectedMetaPreview();
      renderHomeCollectorSummary(homeLoadedMusicDetail);
      renderHomeProductRelationSection();
      renderHomeSearchResults(homeSearchResults);
      renderHomeMasterMetaCard();
      showHomeEditView();
      setStatus("homeEditStatus", "ok", t("media.manage.edit.status.selected", { id: data.id }));
      const locationSeed = {
        id: data.id,
        label_id: data.label_id,
        category: data.category,
        format_name: data.music_detail?.format_name || data.category,
        status: data.status,
        slot_code: data.slot_code,
        storage_slot_id: data.storage_slot_id,
        order_key: data.order_key,
        display_rank: data.display_rank,
        size_group: data.size_group,
        domain_code: data.domain_code,
        release_type: data.release_type,
        linked_album_master_id: data.linked_album_master_id,
        linked_artist_name: data.linked_artist_name,
        copy_group_key: data.copy_group_key,
        source_code: data.source_code,
        source_external_id: data.source_external_id,
        track_list: Array.isArray(data.music_detail?.track_list) ? data.music_detail.track_list : [],
        has_audio: Boolean(data.has_audio),
        audio_asset_count: Number(data.audio_asset_count || 0)
      };
      renderHomeLocationInfo(locationSeed);
      homeLocationSlotId = data.storage_slot_id ? Number(data.storage_slot_id) : null;
      homeLocationSlotItems = [];
      homeLocationSlotLoading = false;
      renderHomeLocationSlotList();
      syncHomeMasterInlineEditor();
      setStatus("homeLocationSlotStatus", "ok", "");
      if (!homeSelectedMasterId) {
        resetHomeMasterLookupUi({ clearInputs: true });
      }
      void loadHomeLinkedCollectibles(Number(data.linked_album_master_id || 0), requestSeq);
      void loadProductLinkedGoods(Number(data.id || 0), requestSeq);
      homeAudioDirectoryMappings = [];
      homeAudioDirectoryFiles = [];
      renderHomeTrackMapBody([]);
      renderHomeTrackFileList([], null);
      setStatus("homeTrackMapStatus", "ok", "");
      scheduleHomeEditorSecondaryHydration(locationSeed, requestSeq);
    }

    async function loadHomeItemForEdit(ownedItemId, opts = {}) {
      if (!ownedItemId) return;
      const requestSeq = Number(homeEditRequestSeq || 0) + 1;
      homeEditRequestSeq = requestSeq;
      switchMediaMode("manage");
      const keepMasterContext = Boolean(opts.keepMasterContext);
      const resetMasterLookupUi = Boolean(opts.resetMasterLookupUi);
      if (!keepMasterContext) {
        homeSelectedMasterId = null;
        syncHomeMasterDeleteUi();
      }
      const _spotifySlot = document.getElementById('homeMasterSpotifyEmbed');
      if (_spotifySlot) { _spotifySlot.hidden = true; _spotifySlot.innerHTML = ''; delete _spotifySlot.dataset.albumId; }
      homeSelectedItemId = Number(ownedItemId);
      if ($("homeProductRelationSection")) $("homeProductRelationSection").open = false;
      homeLinkedCollectibles = [];
      homeLinkedCollectiblesLoading = false;
      if ($("editOwnedId")) $("editOwnedId").value = String(ownedItemId);
      if (!keepMasterContext || resetMasterLookupUi) {
        resetHomeMasterLookupUi({ clearInputs: true });
      }
      showHomeEditView();
      try {
        setStatus("homeEditStatus", "ok", t("media.manage.edit.status.loading"));
        const res = await fetch(`/owned-items/${ownedItemId}`);
        const data = await safeJson(res);
        if (!isActiveHomeEditRequest(requestSeq)) return;
        if (!res.ok) throw new Error(data.detail || t("media.manage.edit.status.load_failed"));
        await applyHomeEditorDetail(data, requestSeq);
      } catch (err) {
        if (!isActiveHomeEditRequest(requestSeq)) return;
        setStatus("homeEditStatus", "err", err.message);
      }
    }

    function buildHomeEditPayload() {
      const category = $("editCategory").value;
      const purchasePrice = normalizePurchasePriceOrNull($("editPurchasePrice").value);
      const payload = {
        category,
        size_group: $("editSizeGroup").value,
        preferred_storage_size_group: $("editPreferredStorageSizeGroup").value || $("editSizeGroup").value,
        quantity: 1,
        is_second_hand: !$("editIsSecondHand").checked,  // 새상품 여부: checked = 새상품 → NOT second_hand
        status: $("editStatus").value,
        signature_type: $("editSignatureType").value,
        source_code: homeSelectedSourceCode,
        source_external_id: homeSelectedSourceExternalId,
        release_type: $("editReleaseType").value || null,
        linked_album_master_id: $("editLinkedAlbumMasterId").value.trim()
          ? Number($("editLinkedAlbumMasterId").value)
          : null,
        linked_artist_name: MUSIC_CATEGORIES.has(category)
          ? ($("editLinkedArtistName").value.trim() || null)
          : null,
        purchase_price: purchasePrice,
        currency_code: purchasePrice !== null ? normalizeCurrencyCodeOrNull($("editCurrencyCode").value, "KRW") : null,
        purchase_source: $("editPurchaseSource").value.trim() || null,
        condition_grade: $("editConditionGrade").value.trim() || null,
        memory_note: $("editMemoryNote").value.trim() || null,
        item_name_override: $("editItemName").value.trim() || null,
        display_rank: $("editDisplayRank").value.trim() ? Number($("editDisplayRank").value) : null,
        storage_slot_id: $("editSlotId").value ? Number($("editSlotId").value) : null
      };

      if (MUSIC_CATEGORIES.has(category)) {
        const collectorBase = buildCollectorPayload(homeSelectedSourceCode, homeLoadedMusicDetail || {});
        const editRunout = splitRunoutList($("editRunoutMatrix").value);
        const editPressingInput = $("editPressingCountry").value.trim();
        const editedTrackItems = parseTracksFromText($("editTrackList").value);
        const trackList = editedTrackItems.map((item) => item.title);
        payload.music_detail = {
          format_name: $("editFormatName").value,
          is_promotional_not_for_sale: $("editPromoNfs").checked,
          artist_or_brand: $("editArtistName").value.trim() || null,
          released_date: $("editReleasedDate").value.trim() || null,
          barcode: $("editBarcode").value.trim() || null,
          label_name: $("editLabelName").value.trim() || null,
          catalog_no: $("editCatalogNo").value.trim() || null,
          disc_count: normalizePositiveIntOrNull($("editDiscCount").value),
          speed_rpm: $("editSpeedRpm").value.trim() ? Number($("editSpeedRpm").value) : null,
          disc_type: $("editDiscType")?.value.trim() || null,
          package_contents: _collectPackageContents() || null,
          is_limited_edition: $("editIsLimitedEdition").checked ? true : null,
          edition_number: $("editEditionNumber").value.trim() || null,
          has_obi: $("editHasObi").checked ? true : null,
          runout_matrix: editRunout.length ? editRunout : collectorBase.runout_matrix,
          pressing_country: editPressingInput || collectorBase.pressing_country || null,
          media_type: $("editMediaType").value.trim() || null,
          cover_image_url: $("editCoverImageUrl").value.trim() || null,
          track_list: trackList,
          cover_condition: normalizeConditionGradeValue($("editCoverCondition").value) || null,
          disc_condition: normalizeConditionGradeValue($("editDiscCondition").value) || null,
          source_notes: collectorBase.source_notes,
          credits: collectorBase.credits,
          identifier_items: collectorBase.identifier_items,
          image_items: collectorBase.image_items,
          company_items: collectorBase.company_items,
          series: collectorBase.series,
          format_items: collectorBase.format_items,
          track_items: editedTrackItems.length ? editedTrackItems : collectorBase.track_items || [],
          label_items: collectorBase.label_items
        };
      } else {
        const goodsImageUrls = splitLineList($("editGoodsImageUrls").value);
        payload.goods_detail = {
          image_urls: goodsImageUrls,
          primary_image_url: goodsImageUrls.length ? goodsImageUrls[0] : null,
          poster_storage_spec: $("editPosterStorageSpec").value.trim() || null,
          tshirt_size: $("editTshirtSize").value.trim() || null,
          cup_material: $("editCupMaterial").value.trim() || null,
          hat_size: $("editHatSize").value.trim() || null
        };
      }
      return payload;
    }

    function homeOwnedItemRelationTypeLabel(code) {
      const normalized = String(code || "").trim().toUpperCase();
      if (normalized === "MASTER_CHILD") return t("media.manage.product_relation.type.master_child");
      if (normalized === "SERIES_MEMBER") return t("media.manage.product_relation.type.series_member");
      if (normalized === "BOX_MEMBER_OF") return t("media.manage.product_relation.type.box_member_of");
      if (normalized === "RELATED_RELEASE") return t("media.manage.product_relation.type.related_release");
      return normalized || "-";
    }

    function cloneHomeOwnedItemRelationEntry(row, index = 0) {
      return {
        relation_type: String(row?.relation_type || "").trim().toUpperCase(),
        target_kind: String(row?.target_kind || "").trim().toUpperCase(),
        target_ref: String(row?.target_ref || "").trim(),
        target_label: String(row?.target_label || "").trim() || null,
        album_master_id: Number(row?.album_master_id || 0) || null,
        product_group_id: Number(row?.product_group_id || 0) || null,
        product_group_type: String(row?.product_group_type || "").trim().toUpperCase() || null,
        target_owned_item_id: Number(row?.target_owned_item_id || 0) || null,
        target_copy_group_key: String(row?.target_copy_group_key || "").trim() || null,
        target_category: String(row?.target_category || "").trim().toUpperCase() || null,
        artist_or_brand: String(row?.artist_or_brand || "").trim() || null,
        note: String(row?.note || "").trim() || null,
        display_order: Number(row?.display_order ?? index) || index,
      };
    }

    function homeOwnedItemRelationTargetLabel(row) {
      const explicit = String(row?.target_label || "").trim();
      if (explicit) return explicit;
      const albumMasterId = Number(row?.album_master_id || 0);
      if (albumMasterId > 0) return `album_master_id=${albumMasterId}`;
      const productGroupId = Number(row?.product_group_id || 0);
      if (productGroupId > 0) return `product_group_id=${productGroupId}`;
      const targetOwnedItemId = Number(row?.target_owned_item_id || 0);
      if (targetOwnedItemId > 0) return `owned_item_id=${targetOwnedItemId}`;
      const targetCopyGroupKey = String(row?.target_copy_group_key || "").trim();
      if (targetCopyGroupKey) return `copy_group=${targetCopyGroupKey}`;
      return String(row?.target_ref || "").trim() || "-";
    }

    function deriveHomeOwnedItemMasterRelations() {
      const rows = Array.isArray(homeOwnedItemRelationMasterEntries)
        ? homeOwnedItemRelationMasterEntries.map((row, index) => cloneHomeOwnedItemRelationEntry(row, index))
        : [];
      const seen = new Set(rows.map((row) => `${row.target_kind}:${row.target_ref}`));
      const masterContext = resolveHomeLinkedGoodsMasterContext();
      if (Number(masterContext.masterId || 0) > 0) {
        const targetRef = String(masterContext.masterId);
        const key = `ALBUM_MASTER:${targetRef}`;
        if (!seen.has(key)) {
          rows.unshift(
            cloneHomeOwnedItemRelationEntry(
              {
                relation_type: "MASTER_CHILD",
                target_kind: "ALBUM_MASTER",
                target_ref: targetRef,
                target_label: masterContext.title || `album_master_id=${targetRef}`,
                album_master_id: Number(masterContext.masterId || 0),
                artist_or_brand: masterContext.artist || null,
              },
              0,
            ),
          );
        }
      }
      return rows;
    }

    function renderHomeOwnedItemRelationChipList(containerId, rows, options = {}) {
      const container = $(containerId);
      if (!container) return;
      const items = Array.isArray(rows) ? rows : [];
      if (!items.length) {
        container.innerHTML = `<div class='mini muted'>${escapeHtml(t("media.manage.product_relation.state.none"))}</div>`;
        return;
      }
      const removable = options.removable !== false;
      const removeRole = String(options.removeRole || "editable");
      container.innerHTML = items.map((row, index) => {
        const draftIndex = Number.isInteger(Number(row?._draft_index)) ? Number(row._draft_index) : index;
        const label = [
          homeOwnedItemRelationTypeLabel(row?.relation_type),
          homeOwnedItemRelationTargetLabel(row),
          row?.note ? `- ${String(row.note).trim()}` : "",
        ].filter((value) => value).join(" ");
        return `
          <span class="goods-chip">
            <span>${escapeHtml(label)}</span>
            ${removable
              ? `<button type="button" data-home-remove-product-relation="${escapeHtml(removeRole)}" data-home-product-relation-index="${draftIndex}">${escapeHtml(t("common.action.delete"))}</button>`
              : ""}
          </span>
        `;
      }).join("");
    }

    function renderHomeOwnedItemRelationComponentList() {
      const container = $("homeProductRelationComponentList");
      if (!container) return;
      const rows = Array.isArray(homeOwnedItemRelationView?.box_components) ? homeOwnedItemRelationView.box_components : [];
      if (!rows.length) {
        container.innerHTML = `<div class='mini muted'>${escapeHtml(t("media.manage.product_relation.state.no_components"))}</div>`;
        return;
      }
      container.innerHTML = rows.map((row) => {
        const sourceOwnedItemId = Number(row?.source_owned_item_id || 0);
        const sourceName = String(row?.source_item_name || "").trim() || (sourceOwnedItemId > 0 ? `owned_item_id=${sourceOwnedItemId}` : "-");
        const meta = [
          row?.source_copy_group_key ? `group: ${String(row.source_copy_group_key).trim()}` : "",
          row?.source_category ? mediaDisplayLabel(row.source_category) : "",
          row?.note ? String(row.note).trim() : "",
        ].filter((value) => value).join(" / ");
        return `
          <div class="goods-target-row">
            <div class="u-minw-0">
              <strong>${escapeHtml(sourceName)}</strong>
              ${meta ? `<div class="mini muted">${escapeHtml(meta)}</div>` : ""}
            </div>
          </div>
        `;
      }).join("");
    }

    function renderHomeProductRelationSeriesResults(items) {
      const container = $("homeProductRelationSeriesResults");
      if (!container) return;
      const rows = Array.isArray(items) ? items : [];
      if (!rows.length) {
        container.innerHTML = `<div class='mini muted'>${escapeHtml(t("media.manage.product_relation.results.empty"))}</div>`;
        return;
      }
      container.innerHTML = rows.map((row) => `
        <div class="goods-target-row">
          <div class="u-minw-0">
            <strong>${escapeHtml(String(row.group_name || row.label || "").trim() || "-")}</strong>
            <div class="mini muted">${escapeHtml(String(row.group_type || "").trim() || "SERIES")}</div>
          </div>
          <button
            class="btn ghost tiny"
            type="button"
            data-home-add-product-series="${Number(row.id || row.product_group_id || row.value || 0)}"
            data-home-add-product-series-name="${escapeHtml(String(row.group_name || row.label || "").trim())}"
            data-home-add-product-series-type="${escapeHtml(String(row.group_type || "SERIES").trim())}"
          >${escapeHtml(t("common.action.add"))}</button>
        </div>
      `).join("");
    }

    function renderHomeProductRelationReleaseResults(items) {
      const container = $("homeProductRelationReleaseResults");
      if (!container) return;
      const rows = Array.isArray(items) ? items : [];
      if (!rows.length) {
        container.innerHTML = `<div class='mini muted'>${escapeHtml(t("media.manage.product_relation.results.empty"))}</div>`;
        return;
      }
      container.innerHTML = rows.map((row) => `
        <div class="goods-target-row">
          <div class="u-minw-0">
            <strong>${escapeHtml(String(row.label || "").trim() || "-")}</strong>
            <div class="mini muted">${escapeHtml([
              row?.copy_group_key ? `group: ${String(row.copy_group_key).trim()}` : "",
              row?.category ? mediaDisplayLabel(row.category) : "",
            ].filter((value) => value).join(" / ") || "-")}</div>
          </div>
          <button
            class="btn ghost tiny"
            type="button"
            data-home-add-product-release="${Number(row.owned_item_id || row.value || 0)}"
            data-home-add-product-release-name="${escapeHtml(String(row.label || "").trim())}"
            data-home-add-product-release-category="${escapeHtml(String(row.category || "").trim())}"
            data-home-add-product-release-scope-kind="${escapeHtml(String(row.scope_kind || "").trim())}"
            data-home-add-product-release-scope-key="${escapeHtml(String(row.scope_key || "").trim())}"
            data-home-add-product-release-copy-group="${escapeHtml(String(row.copy_group_key || "").trim())}"
          >${escapeHtml(t("common.action.add"))}</button>
        </div>
      `).join("");
    }

    function renderHomeProductRelationSection() {
      const categoryCode = String($("editCategory")?.value || "").trim().toUpperCase();
      const isMusic = MUSIC_CATEGORIES.has(categoryCode);
      const hasSelection = Number(homeSelectedItemId || $("editOwnedId")?.value || 0) > 0;
      const createSeriesLabel = t("media.manage.product_relation.action.create_series");
      if ($("homeProductRelationCreateGroupBtn")) $("homeProductRelationCreateGroupBtn").setAttribute("title", createSeriesLabel);
      setDisplayIfPresent("homeProductRelationSection", isMusic && hasSelection ? "grid" : "none");
      if (!isMusic || !hasSelection) return;

      const masterRows = deriveHomeOwnedItemMasterRelations();
      const editableRows = Array.isArray(homeOwnedItemEditableRelations)
        ? homeOwnedItemEditableRelations.map((row, index) => ({ ...row, _draft_index: index }))
        : [];
      renderHomeOwnedItemRelationChipList("homeProductRelationMasterList", masterRows, { removable: false });
      renderHomeOwnedItemRelationChipList(
        "homeProductRelationSeriesList",
        editableRows.filter((row) => String(row?.relation_type || "").trim().toUpperCase() === "SERIES_MEMBER"),
      );
      renderHomeOwnedItemRelationChipList(
        "homeProductRelationReleaseList",
        editableRows.filter((row) => {
          const relationType = String(row?.relation_type || "").trim().toUpperCase();
          return relationType === "BOX_MEMBER_OF" || relationType === "RELATED_RELEASE";
        }),
      );
      renderHomeOwnedItemRelationComponentList();

      if (homeOwnedItemRelationView?.uses_shared_relation_scope && String(homeOwnedItemRelationView.scope_key || "").trim()) {
        setTextIfPresent(
          "homeProductRelationScopeInfo",
          t("media.manage.product_relation.scope.shared", { group: String(homeOwnedItemRelationView.scope_key || "").trim() }),
        );
        return;
      }
      if (Number(homeSelectedItemId || $("editOwnedId")?.value || 0) > 0) {
        setTextIfPresent("homeProductRelationScopeInfo", t("media.manage.product_relation.scope.single"));
        return;
      }
      setTextIfPresent("homeProductRelationScopeInfo", t("media.manage.product_relation.scope.empty"));
    }

    function resetHomeOwnedItemRelationUi() {
      homeOwnedItemRelationView = null;
      homeOwnedItemRelationMasterEntries = [];
      homeOwnedItemEditableRelations = [];
      if ($("homeProductRelationSeriesQuery")) $("homeProductRelationSeriesQuery").value = "";
      if ($("homeProductRelationReleaseQuery")) $("homeProductRelationReleaseQuery").value = "";
      if ($("homeProductRelationNote")) $("homeProductRelationNote").value = "";
      if ($("homeProductRelationType")) $("homeProductRelationType").value = "BOX_MEMBER_OF";
      setHtmlIfPresent("homeProductRelationSeriesResults", "");
      setHtmlIfPresent("homeProductRelationReleaseResults", "");
      setStatus("homeProductRelationStatus", "", "");
      renderHomeProductRelationSection();
    }

    function applyHomeOwnedItemRelationView(view) {
      homeOwnedItemRelationView = view && typeof view === "object" ? view : null;
      homeOwnedItemRelationMasterEntries = Array.isArray(homeOwnedItemRelationView?.master_links)
        ? homeOwnedItemRelationView.master_links.map((row, index) => cloneHomeOwnedItemRelationEntry(row, index))
        : [];
      homeOwnedItemEditableRelations = [
        ...(Array.isArray(homeOwnedItemRelationView?.series_memberships) ? homeOwnedItemRelationView.series_memberships : []),
        ...(Array.isArray(homeOwnedItemRelationView?.box_memberships) ? homeOwnedItemRelationView.box_memberships : []),
        ...(Array.isArray(homeOwnedItemRelationView?.related_releases) ? homeOwnedItemRelationView.related_releases : []),
      ].map((row, index) => cloneHomeOwnedItemRelationEntry(row, index));
      renderHomeProductRelationSection();
    }

    async function loadHomeOwnedItemRelations(ownedItemId, requestSeq = 0) {
      if (requestSeq && !isActiveHomeEditRequest(requestSeq)) return;
      ownedItemId = Number(ownedItemId || 0);
      const categoryCode = String($("editCategory")?.value || "").trim().toUpperCase();
      if (ownedItemId <= 0 || !MUSIC_CATEGORIES.has(categoryCode)) {
        resetHomeOwnedItemRelationUi();
        return;
      }

      try {
        setStatus("homeProductRelationStatus", "ok", t("media.manage.product_relation.status.loading"));
        const res = await fetch(`/owned-items/${ownedItemId}/relations`);
        const data = await safeJson(res);
        if (requestSeq && !isActiveHomeEditRequest(requestSeq)) return;
        if (!res.ok) throw new Error(data.detail || t("media.manage.product_relation.status.load_failed"));
        applyHomeOwnedItemRelationView(data);
        const relationCount = homeOwnedItemRelationMasterEntries.length + homeOwnedItemEditableRelations.length;
        setStatus("homeProductRelationStatus", "ok", t("media.manage.product_relation.status.loaded", { count: countWithUnit(relationCount) }));
      } catch (err) {
        homeOwnedItemRelationView = null;
        homeOwnedItemRelationMasterEntries = [];
        homeOwnedItemEditableRelations = [];
        renderHomeProductRelationSection();
        setStatus("homeProductRelationStatus", "err", err.message);
      }
    }

    function addHomeOwnedItemRelationDraft(row) {
      const relationType = String(row?.relation_type || "").trim().toUpperCase();
      const targetKind = String(row?.target_kind || "").trim().toUpperCase();
      const targetRef = String(row?.target_ref || "").trim();
      if (!relationType || !targetKind || !targetRef) return;
      const exists = homeOwnedItemEditableRelations.some((item) =>
        String(item?.relation_type || "").trim().toUpperCase() === relationType
        && String(item?.target_kind || "").trim().toUpperCase() === targetKind
        && String(item?.target_ref || "").trim() === targetRef
      );
      if (exists) return;
      homeOwnedItemEditableRelations.push(
        cloneHomeOwnedItemRelationEntry(
          {
            ...row,
            relation_type: relationType,
            target_kind: targetKind,
            target_ref: targetRef,
            display_order: homeOwnedItemEditableRelations.length,
          },
          homeOwnedItemEditableRelations.length,
        ),
      );
      renderHomeProductRelationSection();
    }

    async function searchHomeProductRelationSeriesTargets() {
      const ownedItemId = Number(homeSelectedItemId || $("editOwnedId")?.value || 0);
      if (ownedItemId <= 0) {
        setStatus("homeProductRelationStatus", "err", t("media.manage.product_relation.status.select_first"));
        return;
      }
      const query = String($("homeProductRelationSeriesQuery")?.value || "").trim();
      if (!query) {
        setHtmlIfPresent("homeProductRelationSeriesResults", `<div class='mini muted'>${escapeHtml(t("media.manage.product_relation.results.query_empty"))}</div>`);
        return;
      }
      try {
        setStatus("homeProductRelationStatus", "ok", t("media.manage.product_relation.status.lookup_loading"));
        const params = new URLSearchParams({ q: query, limit: "12" });
        const res = await fetch(`/product-groups?${params.toString()}`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.product_relation.status.lookup_failed"));
        renderHomeProductRelationSeriesResults(Array.isArray(data) ? data : []);
        setStatus("homeProductRelationStatus", "ok", t("media.manage.product_relation.status.lookup_done"));
      } catch (err) {
        renderHomeProductRelationSeriesResults([]);
        setStatus("homeProductRelationStatus", "err", err.message);
      }
    }

    async function createHomeProductRelationSeriesGroup() {
      const ownedItemId = Number(homeSelectedItemId || $("editOwnedId")?.value || 0);
      if (ownedItemId <= 0) {
        setStatus("homeProductRelationStatus", "err", t("media.manage.product_relation.status.select_first"));
        return;
      }
      const groupName = String($("homeProductRelationSeriesQuery")?.value || "").trim();
      if (!groupName) {
        setStatus("homeProductRelationStatus", "err", t("media.manage.product_relation.status.create_series_required"));
        return;
      }
      try {
        setStatus("homeProductRelationStatus", "ok", t("media.manage.product_relation.status.create_series_progress"));
        const res = await fetch("/product-groups", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            group_type: "SERIES",
            group_name: groupName,
          }),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.product_relation.status.create_series_failed"));
        addHomeOwnedItemRelationDraft({
          relation_type: "SERIES_MEMBER",
          target_kind: "PRODUCT_GROUP",
          target_ref: String(data.id || data.product_group_id || ""),
          target_label: String(data.group_name || "").trim() || groupName,
          product_group_id: Number(data.id || data.product_group_id || 0) || null,
          product_group_type: String(data.group_type || "SERIES").trim().toUpperCase(),
        });
        setHtmlIfPresent("homeProductRelationSeriesResults", "");
        setStatus("homeProductRelationStatus", "ok", t("media.manage.product_relation.status.create_series_done", { name: groupName }));
      } catch (err) {
        setStatus("homeProductRelationStatus", "err", err.message);
      }
    }

    async function searchHomeProductRelationReleaseTargets() {
      const ownedItemId = Number(homeSelectedItemId || $("editOwnedId")?.value || 0);
      if (ownedItemId <= 0) {
        setStatus("homeProductRelationStatus", "err", t("media.manage.product_relation.status.select_first"));
        return;
      }
      const query = String($("homeProductRelationReleaseQuery")?.value || "").trim();
      if (!query) {
        setHtmlIfPresent("homeProductRelationReleaseResults", `<div class='mini muted'>${escapeHtml(t("media.manage.product_relation.results.query_empty"))}</div>`);
        return;
      }
      try {
        setStatus("homeProductRelationStatus", "ok", t("media.manage.product_relation.status.lookup_loading"));
        const params = new URLSearchParams({
          kind: "owned_item",
          q: query,
          owned_item_id: String(ownedItemId),
          limit: "12",
        });
        const res = await fetch(`/owned-item-relation-targets?${params.toString()}`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.product_relation.status.lookup_failed"));
        renderHomeProductRelationReleaseResults(Array.isArray(data.items) ? data.items : []);
        setStatus("homeProductRelationStatus", "ok", t("media.manage.product_relation.status.lookup_done"));
      } catch (err) {
        renderHomeProductRelationReleaseResults([]);
        setStatus("homeProductRelationStatus", "err", err.message);
      }
    }

    async function saveHomeOwnedItemRelations() {
      const ownedItemId = Number(homeSelectedItemId || $("editOwnedId")?.value || 0);
      if (ownedItemId <= 0) {
        setStatus("homeProductRelationStatus", "err", t("media.manage.product_relation.status.select_first"));
        return;
      }
      try {
        const payload = {
          relations: [
            ...homeOwnedItemRelationMasterEntries.map((row, index) => ({
              relation_type: String(row?.relation_type || "").trim().toUpperCase(),
              target_kind: String(row?.target_kind || "").trim().toUpperCase(),
              target_ref: String(row?.target_ref || "").trim(),
              note: String(row?.note || "").trim() || null,
              display_order: Number(row?.display_order ?? index) || index,
            })),
            ...homeOwnedItemEditableRelations.map((row, index) => ({
              relation_type: String(row?.relation_type || "").trim().toUpperCase(),
              target_kind: String(row?.target_kind || "").trim().toUpperCase(),
              target_ref: String(row?.target_ref || "").trim(),
              note: String(row?.note || "").trim() || null,
              display_order: Number(row?.display_order ?? index) || index,
            })),
          ].filter((row) => row.relation_type && row.target_kind && row.target_ref),
        };
        setStatus("homeProductRelationStatus", "ok", t("media.manage.product_relation.status.save_progress"));
        const res = await fetch(`/owned-items/${ownedItemId}/relations`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.product_relation.status.save_failed"));
        applyHomeOwnedItemRelationView(data);
        setStatus("homeProductRelationStatus", "ok", t("media.manage.product_relation.status.save_done", { count: countWithUnit(payload.relations.length) }));
        refreshHomeSearchInBackground();
        if (Number(homeSelectedMasterId || 0) > 0) {
          await loadHomeMasterMembers(Number(homeSelectedMasterId || 0));
        }
      } catch (err) {
        setStatus("homeProductRelationStatus", "err", err.message);
      }
    }

    async function saveHomeEditedItem() {
      const ownedItemId = Number($("editOwnedId").value || 0);
      if (!ownedItemId) {
        setStatus("homeEditStatus", "err", t("media.manage.edit.status.save_required"));
        return;
      }
      try {
        const payload = buildHomeEditPayload();
        const currentLabelId = String($("editLabelId").value || ownedItemId).trim();
        const currentTitle = String($("editItemName").value || "").trim() || currentLabelId;
        if (!confirmSlotMismatchById(payload.storage_slot_id, [{
          label_id: currentLabelId,
          item_name_override: currentTitle,
          size_group: payload.size_group,
          preferred_storage_size_group: payload.preferred_storage_size_group,
        }], t("media.manage.product.action.save"))) {
          setStatus("homeEditStatus", "ok", t("media.manage.edit.status.save_cancelled"));
          return;
        }
        setStatus("homeEditStatus", "ok", t("media.manage.edit.status.saving"));
        const res = await fetch(`/owned-items/${ownedItemId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.edit.status.save_failed"));
        setStatus("homeEditStatus", "ok", t("media.manage.edit.status.saved", { label_id: data.label_id }));
        homeSelectedMasterId = $("editLinkedAlbumMasterId").value.trim()
          ? Number($("editLinkedAlbumMasterId").value)
          : null;
        await refreshHomeManageContext(ownedItemId, {
          keepMasterContext: Boolean(homeSelectedMasterId),
          masterId: homeSelectedMasterId,
          reloadMaster: Boolean(homeSelectedMasterId),
        });
        refreshHomeDashboardInBackground();
        refreshHomeSearchInBackground();
        refreshOpsExceptionInBackground();
      } catch (err) {
        setStatus("homeEditStatus", "err", err.message);
      }
    }

    async function deleteHomeSelectedItem() {
      const ownedItemId = Number($("editOwnedId").value || 0);
      if (!ownedItemId) {
        setStatus("homeEditStatus", "err", t("media.manage.edit.status.delete_required"));
        return;
      }
      const labelId = String($("editLabelId").value || "-");
      const itemName = String($("editItemName").value || "").trim() || `owned_item_id=${ownedItemId}`;
      const ok = window.confirm(
        t("media.manage.product.delete.confirm", {
          item_name: itemName,
          label_id: labelId,
          owned_item_id: ownedItemId,
        })
      );
      if (!ok) {
        setStatus("homeEditStatus", "ok", t("media.manage.edit.status.delete_cancelled"));
        return;
      }
      try {
        setStatus("homeEditStatus", "ok", t("media.manage.edit.status.deleting"));
        const res = await fetch(`/owned-items/${ownedItemId}`, { method: "DELETE" });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.edit.status.delete_failed"));
        setStatus("homeEditStatus", "ok", t("media.manage.edit.status.deleted", { owned_item_id: data.owned_item_id }));
        clearHomeEditor();
        await homeSearchOwnedItems();
        await loadHomeDashboard();
      } catch (err) {
        setStatus("homeEditStatus", "err", err.message);
      }
    }

    async function deleteHomeSelectedMaster(masterIdArg = null) {
      const masterId = Number(masterIdArg || homeSelectedMasterId || 0);
      if (!masterId) {
        setStatus("homeSearchStatus", "err", t("media.manage.master.delete.required"));
        return;
      }
      const cascadeItems = Boolean($("homeMasterDeleteCascade").checked);
      const confirmPanel = $("homeMasterDeleteConfirm");
      if (confirmPanel) confirmPanel.style.display = "none";
      try {
        const modeText = cascadeItems ? t("media.manage.master.delete.cascade") : t("media.manage.master.delete.action");
        setStatus("homeSearchStatus", "ok", t("media.manage.master.delete.progress", { mode: modeText }));
        const res = await fetch(
          `/album-masters/${masterId}?cascade_items=${cascadeItems ? "true" : "false"}`,
          { method: "DELETE" }
        );
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.manage.master.delete.failed"));

        const removedLinks = Number(data.removed_member_links || 0);
        const deletedItems = Number(data.deleted_owned_item_count || 0);
        const message = cascadeItems
          ? t("media.manage.master.delete.done.cascade", {
              master_id: masterId,
              removed_links: removedLinks,
              deleted_items: deletedItems,
            })
          : t("media.manage.master.delete.done.keep_items", {
              master_id: masterId,
              removed_links: removedLinks,
            });
        setStatus("homeSearchStatus", "ok", message);
        setStatus("homeEditStatus", "ok", message);

        if (Number(homeSelectedMasterId) === masterId) {
          clearHomeEditor();
        }
        await homeSearchOwnedItems();
        await loadHomeDashboard();
      } catch (err) {
        setStatus("homeSearchStatus", "err", err.message);
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
