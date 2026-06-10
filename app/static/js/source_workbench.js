    let sourceWorkbenchRows = [];
    let sourceWorkbenchLoading = false;
    let sourceWorkbenchQueue = [];
    let sourceWorkbenchDiffReviewState = null;
    function _spotifyEmbedHtml(albumId, height) {
      var src = 'https://open.spotify.com/embed/album/' + encodeURIComponent(albumId) + '?utm_source=generator';
      return '<iframe src="' + src + '" width="100%" height="' + (height||352) + '" frameborder="0" ' +
        'allowfullscreen="" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe>';
    }
    const _lp = {
      audio: new Audio(),
      tracks: [],
      idx: -1,
      masterId: null,
      _slotId: "homeMasterLocalPlayer",

      _fmt(sec) {
        if (!sec || isNaN(sec)) return "--:--";
        const m = Math.floor(sec / 60), s = Math.floor(sec % 60);
        return `${m}:${String(s).padStart(2, "0")}`;
      },

      _render(data) {
        const slot = document.getElementById(this._slotId || "homeMasterLocalPlayer");
        if (!slot) return;
        this.tracks = data.tracks || [];
        const cover = data.cover_url
          ? `<img src="${escapeHtml(data.cover_url)}" onerror="this.style.display='none'" />`
          : `<span>🎵</span>`;
        const albumTitle = String(data.title || "").trim();
        const albumYear = data.release_year ? ` (${data.release_year})` : "";
        const albumArtist = String(data.artist_or_brand || "").trim();
        slot.innerHTML = `
          <div class="local-player">
            <div class="local-player-top">
              <div class="local-player-cover">${cover}</div>
              <div class="local-player-info">
                <div class="local-player-album-title">${escapeHtml(albumTitle || "—")}${albumYear ? `<span class="local-player-album-year">${escapeHtml(albumYear)}</span>` : ""}</div>
                <div class="local-player-album-artist">${escapeHtml(albumArtist)}</div>
                <div class="local-player-controls">
                  <button class="local-player-btn" id="lpPrevBtn" title="이전">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M6 6h2v12H6zm3.5 6 8.5 6V6z"/></svg>
                  </button>
                  <button class="local-player-btn play-btn" id="lpPlayBtn" title="재생">
                    <svg id="lpPlayIcon" width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                  </button>
                  <button class="local-player-btn" id="lpNextBtn" title="다음">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M6 18l8.5-6L6 6v12zm2.5-6 8.5 6V6z"/></svg>
                  </button>
                </div>
              </div>
            </div>
            <div class="local-player-progress">
              <input class="local-player-seek" type="range" id="lpSeek" min="0" max="100" value="0" step="0.1" />
              <div class="local-player-time">
                <span id="lpCurrent">0:00</span>
                <span id="lpDuration">--:--</span>
              </div>
            </div>
            <div class="local-player-tracklist" id="lpTrackList"></div>
            <div class="local-player-footer">
              <button class="btn ghost tiny danger" id="lpUnlinkBtn">연결 해제</button>
              <span class="mini muted" style="margin-left:auto;">${escapeHtml(data.match_confidence === "AUTO" ? "자동매칭" : "수동연결")}</span>
            </div>
          </div>`;
        this._renderTrackList();
        this._wire();
        slot.hidden = false;
      },

      _renderTrackList() {
        const el = document.getElementById("lpTrackList");
        if (!el) return;
        el.innerHTML = this.tracks.map((t, i) => `
          <div class="local-player-track${i === this.idx ? " is-active" : ""}" data-lp-track="${i}">
            <span class="local-player-track-num">${t.track_number || i + 1}</span>
            <span class="local-player-track-title">${escapeHtml(t.title || "—")}</span>
            <span class="local-player-track-dur">${this._fmt(t.duration_seconds)}</span>
          </div>`).join("");
        el.querySelectorAll("[data-lp-track]").forEach(el => {
          el.addEventListener("click", () => this._playIdx(Number(el.dataset.lpTrack)));
        });
      },

      _wire() {
        const a = this.audio;
        document.getElementById("lpPlayBtn")?.addEventListener("click", () => {
          if (this.idx < 0 && this.tracks.length) this._playIdx(0);
          else a.paused ? a.play() : a.pause();
        });
        document.getElementById("lpPrevBtn")?.addEventListener("click", () => {
          if (a.currentTime > 3) { a.currentTime = 0; return; }
          this._playIdx(Math.max(0, this.idx - 1));
        });
        document.getElementById("lpNextBtn")?.addEventListener("click", () => {
          this._playIdx(Math.min(this.tracks.length - 1, this.idx + 1));
        });
        const seek = document.getElementById("lpSeek");
        let seeking = false;
        seek?.addEventListener("mousedown", () => { seeking = true; });
        seek?.addEventListener("mouseup", () => {
          seeking = false;
          if (a.duration) a.currentTime = (seek.value / 100) * a.duration;
        });
        a.addEventListener("timeupdate", () => {
          if (seeking || !a.duration) return;
          if (seek) seek.value = (a.currentTime / a.duration) * 100;
          const cur = document.getElementById("lpCurrent");
          if (cur) cur.textContent = this._fmt(a.currentTime);
        });
        a.addEventListener("durationchange", () => {
          const dur = document.getElementById("lpDuration");
          if (dur) dur.textContent = this._fmt(a.duration);
        });
        a.addEventListener("ended", () => {
          if (this.idx < this.tracks.length - 1) this._playIdx(this.idx + 1);
          else this._setPlayIcon(false);
        });
        a.addEventListener("play",  () => this._setPlayIcon(true));
        a.addEventListener("pause", () => this._setPlayIcon(false));
        document.getElementById("lpUnlinkBtn")?.addEventListener("click", async () => {
          const unlinkedId = this.masterId;
          await fetchWithRetry(`/album-masters/${this.masterId}/local-link`, { method: "DELETE" });
          a.pause(); a.src = "";
          const slot = document.getElementById("homeMasterLocalPlayer");
          if (slot) { slot.hidden = true; slot.innerHTML = ""; }
          if (unlinkedId) _localLinkedIds.delete(Number(unlinkedId));
          this.masterId = null; this.tracks = []; this.idx = -1;
        });
      },

      _setPlayIcon(playing) {
        const icon = document.getElementById("lpPlayIcon");
        if (!icon) return;
        icon.innerHTML = playing
          ? `<path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>`
          : `<path d="M8 5v14l11-7z"/>`;
      },

      _playIdx(i) {
        if (i < 0 || i >= this.tracks.length) return;
        this.idx = i;
        const t = this.tracks[i];
        this.audio.src = t.stream_url;
        this.audio.play().catch(() => {});
        this._renderTrackList();
      },

      async load(masterId) {
        this.masterId = masterId;
        const res = await fetchWithRetry(`/album-masters/${masterId}/local-player`);
        if (!res.ok) return;
        const data = await safeJson(res);
        if (!data.linked) return;
        _localLinkedIds.add(Number(masterId));
        this._render(data);
      },

      hide() {
        this.audio.pause();
        this.audio.src = "";
        this.idx = -1;
        const slot = document.getElementById(this._slotId || "homeMasterLocalPlayer");
        if (slot) { slot.hidden = true; slot.innerHTML = ""; }
      },
    };

    function spotifyTogglePanel(masterId, albumId) {
      var inManage = document.getElementById('tabManage')?.classList.contains('active');
      var inSearch = document.getElementById('tabSearch')?.classList.contains('active');

      if (inManage) {
        var slot = document.getElementById('homeMasterSpotifyEmbed');
        if (!slot) return;
        if (!slot.hidden && slot.dataset.albumId === albumId) {
          slot.hidden = true; slot.innerHTML = ''; return;
        }
        slot.innerHTML = _spotifyEmbedHtml(albumId, 352);
        slot.dataset.albumId = albumId;
        slot.hidden = false;
        return;
      }

      if (inSearch) {
        var searchEmbed = document.getElementById('searchSpotifyEmbed');
        var searchPanel = document.getElementById('searchSpotifyPanel');
        if (!searchEmbed || !searchPanel) return;
        if (!searchPanel.hidden && searchEmbed.dataset.albumId === albumId) {
          searchPanel.hidden = true; searchEmbed.innerHTML = ''; searchEmbed.dataset.albumId = ''; return;
        }
        searchEmbed.innerHTML = _spotifyEmbedHtml(albumId, 352);
        searchEmbed.dataset.albumId = albumId;
        searchPanel.hidden = false;
        return;
      }
    }
    function spotifyPlayAlbum(id) { fetch('/spotify/play',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({uri:'spotify:album:'+id})}).catch(function(){}); }
    function spotifyPlayTrack(uri) { if(uri) fetch('/spotify/play',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({uri:uri})}).catch(function(){}); }
    document.addEventListener('click',function(e){
      var b = e.target.closest('.spotify-badge,.local-player-badge');
      if (!b) return;
      e.stopPropagation();
      // 운영 홈 피드/검색 결과 뱃지 클릭 → 사이드바 컨텍스트 선택 및 플레이어 로드
      var card = b.closest('[data-operator-context-source][data-operator-context-index]');
      if (card) {
        setOpsLibraryContextSelectionFromTarget(card, { pin: true });
        return;
      }
      // 관리탭에서 Spotify 뱃지 클릭 → Spotify 플레이어로 전환
      if (b.classList.contains('spotify-badge')) {
        var inManage = document.getElementById('tabManage')?.classList.contains('active');
        if (inManage) {
          var spId = b.dataset.spAlbum;
          if (spId) {
            _lp.hide();
            var spSlot = document.getElementById('homeMasterSpotifyEmbed');
            if (spSlot) { spSlot.innerHTML = _spotifyEmbedHtml(spId, 352); spSlot.dataset.albumId = spId; spSlot.hidden = false; }
          }
        }
      }
    });

    function sourceWorkbenchCandidateTitle(row) {
      const artist = String(row?.artist_or_brand || row?.linked_artist_name || "").trim();
      const itemName = String(row?.item_name_override || "").trim();
      if (!artist || !itemName) return itemName;
      const separatorMatch = itemName.match(/^(.+?)\s*([-–—])\s+(.+)$/);
      if (separatorMatch && String(separatorMatch[1] || "").trim().toLowerCase() === artist.toLowerCase()) {
        return String(separatorMatch[3] || "").trim() || itemName;
      }
      return itemName;
    }

    function sourceWorkbenchDiffFieldDefs() {
      return [
        { key: "artist_name", label: "아티스트명", labelKey: "media.source.diff.field.artist_name", presentation: "default", itemKeys: ["artist_or_brand", "linked_artist_name"], candidateKeys: ["artist_or_brand", "linked_artist_name"] },
        { key: "item_title", label: "상품명", labelKey: "media.source.diff.field.item_title", presentation: "default", itemKeys: ["item_title", "item_name_override"], candidateKeys: ["title", "item_title", "item_name_override"] },
        { key: "released_date", label: "발매일", labelKey: "media.source.diff.field.released_date", presentation: "meta_emphasis", itemKeys: ["released_date"], candidateKeys: ["released_date", "release_date"] },
        { key: "label_name", label: "레이블", labelKey: "media.source.diff.field.label_name", presentation: "default", itemKeys: ["label_name"], candidateKeys: ["label_name", "label"] },
        { key: "catalog_no", label: "카탈로그", labelKey: "media.source.diff.field.catalog_no", presentation: "meta_emphasis", itemKeys: ["catalog_no"], candidateKeys: ["catalog_no"] },
        { key: "barcode", label: "바코드", labelKey: "media.source.diff.field.barcode", presentation: "meta_emphasis", itemKeys: ["barcode"], candidateKeys: ["barcode"] },
        { key: "format_name", label: "포맷", labelKey: "media.source.diff.field.format_name", presentation: "default", itemKeys: ["format_name", "category"], candidateKeys: ["format_name"] },
        { key: "pressing_country", label: "압반 국가", labelKey: "media.source.diff.field.pressing_country", presentation: "default", itemKeys: ["pressing_country"], candidateKeys: ["pressing_country"] },
        { key: "cover_image_url", label: "커버 이미지", labelKey: "media.source.diff.field.cover_image_url", presentation: "cover_thumb", itemKeys: ["cover_image_url"], candidateKeys: ["cover_image_url"] },
        { key: "track_list", label: "트랙리스트", labelKey: "media.source.diff.field.track_list", presentation: "track_fold", itemKeys: ["track_list"], candidateKeys: ["track_list"] },
      ];
    }

    function sourceWorkbenchDiffNormalizedItemTitle(record = {}) {
      const directTitle = sourceWorkbenchDiffNormalizeScalar(record?.item_title || record?.title);
      if (directTitle) return directTitle;
      const artist = sourceWorkbenchDiffNormalizeScalar(record?.artist_or_brand || record?.linked_artist_name);
      const itemName = sourceWorkbenchDiffNormalizeScalar(record?.item_name_override);
      if (!artist || !itemName) return itemName;
      const separatorMatch = itemName.match(/^(.+?)\s*([-–—])\s+(.+)$/);
      if (separatorMatch && sourceWorkbenchDiffNormalizeScalar(separatorMatch[1]).toLowerCase() === artist.toLowerCase()) {
        return sourceWorkbenchDiffNormalizeScalar(separatorMatch[3]) || itemName;
      }
      return itemName;
    }

    function sourceWorkbenchDiffNormalizeScalar(value) {
      return String(value == null ? "" : value).trim().replace(/\s+/g, " ");
    }

    function sourceWorkbenchDiffNormalizeList(value) {
      if (Array.isArray(value)) {
        return value.map((entry) => sourceWorkbenchDiffNormalizeScalar(entry)).filter((entry) => entry);
      }
      const text = String(value == null ? "" : value);
      if (!text.trim()) return [];
      return text.split(/\r?\n+/).map((entry) => sourceWorkbenchDiffNormalizeScalar(entry)).filter((entry) => entry);
    }

    function sourceWorkbenchDiffResolveValue(definition, record = {}) {
      const keys = Array.isArray(definition?.itemKeys) || Array.isArray(definition?.candidateKeys)
        ? (Array.isArray(definition.itemKeys) ? definition.itemKeys : definition.candidateKeys)
        : [];
      if (definition?.key === "track_list") {
        for (const key of keys) {
          const normalizedList = sourceWorkbenchDiffNormalizeList(record?.[key]);
          if (normalizedList.length) return normalizedList;
        }
        return [];
      }
      if (definition?.key === "item_title") {
        const normalizedTitle = sourceWorkbenchDiffNormalizedItemTitle(record);
        if (normalizedTitle) return normalizedTitle;
      }
      for (const key of keys) {
        const normalizedValue = sourceWorkbenchDiffNormalizeScalar(record?.[key]);
        if (normalizedValue) return normalizedValue;
      }
      return "";
    }

    function sourceWorkbenchDiffComparableValue(definition, value) {
      if (definition?.key === "track_list") {
        return sourceWorkbenchDiffNormalizeList(value).join("\n");
      }
      return sourceWorkbenchDiffNormalizeScalar(value);
    }

    function sourceWorkbenchDiffEmpty(definition, value) {
      if (definition?.key === "track_list") return sourceWorkbenchDiffNormalizeList(value).length === 0;
      return !sourceWorkbenchDiffNormalizeScalar(value);
    }

    function sourceWorkbenchDiffStatusCode(definition, currentValue, candidateValue) {
      const currentEmpty = sourceWorkbenchDiffEmpty(definition, currentValue);
      const candidateEmpty = sourceWorkbenchDiffEmpty(definition, candidateValue);
      if (currentEmpty && candidateEmpty) return "EMPTY_BOTH";
      if (sourceWorkbenchDiffComparableValue(definition, currentValue) === sourceWorkbenchDiffComparableValue(definition, candidateValue)) return "SAME";
      if (currentEmpty && !candidateEmpty) return "EMPTY_FILL";
      return "CONFLICT";
    }

    function sourceWorkbenchDiffStatusLabel(status) {
      if (status === "EMPTY_FILL") return "빈 값 채움";
      if (status === "CONFLICT") return "변경 충돌";
      if (status === "SAME") return "동일";
      if (status === "EMPTY_BOTH") return "동일";
      return status || "-";
    }

    function sourceWorkbenchDiffStatusLabelKey(status) {
      if (status === "EMPTY_FILL") return "media.source.diff.status.empty_fill";
      if (status === "CONFLICT") return "media.source.diff.status.conflict";
      if (status === "SAME") return "media.source.diff.status.same";
      if (status === "EMPTY_BOTH") return "media.source.diff.status.empty_both";
      return "";
    }

    function updateSourceWorkbenchDiffReviewStateAfterApply(payload = {}) {
      const reviewState = payload?.reviewState || {};
      const reviewItems = Array.isArray(reviewState?.items) ? reviewState.items : [];
      const results = Array.isArray(payload?.results) ? payload.results : [];
      const failedIds = new Set(
        results
          .filter((row) => !row?.updated)
          .map((row) => Number(row?.owned_item_id || 0))
          .filter((id) => id > 0)
      );
      const items = reviewItems.filter((item) => failedIds.has(Number(item?.ownedItemId || 0)));
      const actionableFieldCount = items.reduce((total, item) => total + (Array.isArray(item?.fieldRows) ? item.fieldRows.filter((row) => !row?.disabled).length : 0), 0);
      const candidateSources = [...new Set(items.map((item) => String(item?.candidateSource || "").trim()).filter((value) => value && value !== "-"))];
      const nextState = {
        items,
        summary: {
          itemCount: items.length,
          actionableFieldCount,
          selectedFieldCount: 0,
          candidateSources,
        },
      };
      nextState.summary.selectedFieldCount = sourceWorkbenchDiffReviewFieldCount(nextState);
      return nextState;
    }

    function sourceWorkbenchDiffReviewFieldCount(reviewState) {
      const items = Array.isArray(reviewState?.items) ? reviewState.items : [];
      return items.reduce((total, item) => total + (Array.isArray(item?.fieldRows) ? item.fieldRows.filter((row) => row?.selected).length : 0), 0);
    }

    function sourceWorkbenchEditionComparatorFieldDefs() {
      return [
        {
          key: "catalog_no",
          label: "Catalog no",
          group: "identity",
          strong: true,
          type: "scalar",
          cardRole: "identity_chip",
          itemKeys: ["catalog_no"],
          candidateKeys: ["catalog_no"],
        },
        {
          key: "barcode",
          label: "Barcode",
          group: "identity",
          strong: true,
          type: "scalar",
          cardRole: "identity_chip",
          itemKeys: ["barcode"],
          candidateKeys: ["barcode"],
        },
        {
          key: "pressing_country",
          label: "Pressing country",
          group: "identity",
          strong: true,
          type: "scalar",
          cardRole: "identity_chip",
          itemKeys: ["pressing_country"],
          candidateKeys: ["pressing_country"],
        },
        { key: "label_name", label: "Label", group: "identity", strong: false, type: "scalar", itemKeys: ["label_name", "label"], candidateKeys: ["label_name", "label"] },
        { key: "format_name", label: "Format", group: "identity", strong: false, type: "scalar", itemKeys: ["format_name", "category"], candidateKeys: ["format_name"] },
        { key: "artist_name", label: "Artist", group: "identity", strong: false, type: "scalar", itemKeys: ["artist_or_brand", "linked_artist_name"], candidateKeys: ["artist_or_brand", "linked_artist_name"] },
        { key: "item_title", label: "Title", group: "identity", strong: false, type: "scalar", itemKeys: ["item_title", "item_name_override"], candidateKeys: ["title", "item_title", "item_name_override"] },
        { key: "format_items", label: "Format items", group: "evidence", strong: false, type: "object_list", cardRole: "evidence", itemKeys: ["format_items"], candidateKeys: ["format_items"] },
        { key: "identifier_items", label: "Identifiers", group: "evidence", strong: false, type: "object_list", itemKeys: ["identifier_items"], candidateKeys: ["identifier_items"] },
        {
          key: "runout_matrix",
          label: "Runout",
          group: "evidence",
          strong: false,
          type: "string_list",
          cardRole: "evidence_preview",
          itemKeys: ["runout_matrix"],
          candidateKeys: ["runout_matrix"],
        },
        { key: "series", label: "Series", group: "evidence", strong: false, type: "string_list", itemKeys: ["series"], candidateKeys: ["series"] },
        { key: "company_items", label: "Companies", group: "evidence", strong: false, type: "object_list", itemKeys: ["company_items"], candidateKeys: ["company_items"] },
        {
          key: "track_list",
          label: "Tracks",
          group: "content",
          strong: false,
          type: "track_list",
          cardRole: "evidence_preview",
          itemKeys: ["track_list", "track_items"],
          candidateKeys: ["track_list", "track_items"],
        },
      ];
    }

    function sourceWorkbenchEditionComparatorNormalizeScalar(value) {
      return String(value == null ? "" : value).trim().replace(/\s+/g, " ");
    }

    function sourceWorkbenchEditionComparatorNormalizeStringList(value) {
      if (Array.isArray(value)) {
        return value
          .map((entry) => sourceWorkbenchEditionComparatorNormalizeScalar(entry))
          .filter((entry) => entry);
      }
      const text = sourceWorkbenchEditionComparatorNormalizeScalar(value);
      if (!text) return [];
      return text
        .split(/\r?\n+/)
        .map((entry) => sourceWorkbenchEditionComparatorNormalizeScalar(entry))
        .filter((entry) => entry);
    }

    function sourceWorkbenchEditionComparatorNormalizeObjectList(value) {
      return Array.isArray(value)
        ? value.filter((entry) => entry && typeof entry === "object" && !Array.isArray(entry))
        : [];
    }

    function sourceWorkbenchEditionComparatorNormalizedItemTitle(record = {}) {
      const directTitle = sourceWorkbenchEditionComparatorNormalizeScalar(record?.item_title || record?.title);
      if (directTitle) return directTitle;
      const artist = sourceWorkbenchEditionComparatorNormalizeScalar(record?.artist_or_brand || record?.linked_artist_name);
      const itemName = sourceWorkbenchEditionComparatorNormalizeScalar(record?.item_name_override);
      if (!artist || !itemName) return itemName;
      const separatorMatch = itemName.match(/^(.+?)\s*([-–—])\s+(.+)$/);
      if (separatorMatch && sourceWorkbenchEditionComparatorNormalizeScalar(separatorMatch[1]).toLowerCase() === artist.toLowerCase()) {
        return sourceWorkbenchEditionComparatorNormalizeScalar(separatorMatch[3]) || itemName;
      }
      return itemName;
    }

    function sourceWorkbenchEditionComparatorResolveValue(definition, record = {}) {
      const keys = Array.isArray(definition?.itemKeys) || Array.isArray(definition?.candidateKeys)
        ? (Array.isArray(definition.itemKeys) ? definition.itemKeys : definition.candidateKeys)
        : [];
      if (definition?.key === "item_title") {
        const normalizedTitle = sourceWorkbenchEditionComparatorNormalizedItemTitle(record);
        if (normalizedTitle) return normalizedTitle;
      }
      if (definition?.type === "track_list") {
        for (const key of keys) {
          if (key === "track_items") {
            const objectList = sourceWorkbenchEditionComparatorNormalizeObjectList(record?.[key]);
            if (objectList.length) return objectList;
            continue;
          }
          const normalizedList = sourceWorkbenchEditionComparatorNormalizeStringList(record?.[key]);
          if (normalizedList.length) return normalizedList;
        }
        return [];
      }
      if (definition?.type === "string_list") {
        for (const key of keys) {
          const normalizedList = sourceWorkbenchEditionComparatorNormalizeStringList(record?.[key]);
          if (normalizedList.length) return normalizedList;
        }
        return [];
      }
      if (definition?.type === "object_list") {
        for (const key of keys) {
          const objectList = sourceWorkbenchEditionComparatorNormalizeObjectList(record?.[key]);
          if (objectList.length) return objectList;
        }
        return [];
      }
      for (const key of keys) {
        const normalizedValue = sourceWorkbenchEditionComparatorNormalizeScalar(record?.[key]);
        if (normalizedValue) return normalizedValue;
      }
      return "";
    }

    function sourceWorkbenchEditionComparatorFormatIdentifierItem(row) {
      if (!row || typeof row !== "object" || Array.isArray(row)) return "";
      const type = sourceWorkbenchEditionComparatorNormalizeScalar(row.type || row.kind || row.name);
      const value = sourceWorkbenchEditionComparatorNormalizeScalar(row.value || row.description || row.text);
      if (type && value) return `${type}: ${value}`;
      return type || value || "";
    }

    function sourceWorkbenchEditionComparatorFormatFormatItem(row) {
      if (!row || typeof row !== "object" || Array.isArray(row)) return "";
      const name = sourceWorkbenchEditionComparatorNormalizeScalar(row.name || row.format_name || row.format);
      const qtyRaw = sourceWorkbenchEditionComparatorNormalizeScalar(row.qty ?? row.quantity ?? "");
      const qtyText = qtyRaw && qtyRaw !== "1" ? ` x${qtyRaw}` : "";
      const descriptions = Array.isArray(row.descriptions)
        ? row.descriptions
          .map((entry) => sourceWorkbenchEditionComparatorNormalizeScalar(entry))
          .filter((entry) => entry)
        : [];
      const text = sourceWorkbenchEditionComparatorNormalizeScalar(row.text || row.description);
      const parts = [];
      if (name) parts.push(`${name}${qtyText}`);
      if (descriptions.length) parts.push(descriptions.join(", "));
      if (text) parts.push(text);
      if (!parts.length && qtyRaw) return `qty ${qtyRaw}`;
      return parts.join(" / ");
    }

    function sourceWorkbenchEditionComparatorFormatCompanyItem(row) {
      if (!row || typeof row !== "object" || Array.isArray(row)) return "";
      const name = sourceWorkbenchEditionComparatorNormalizeScalar(row.name || row.company || row.label);
      const role = sourceWorkbenchEditionComparatorNormalizeScalar(row.role || row.type);
      if (name && role) return `${name} (${role})`;
      return name || role || "";
    }

    function sourceWorkbenchEditionComparatorFormatTrackItem(row, index = 0) {
      if (!row || typeof row !== "object" || Array.isArray(row)) return "";
      const display = sourceWorkbenchEditionComparatorNormalizeScalar(row.display);
      if (display) return display;
      const position = sourceWorkbenchEditionComparatorNormalizeScalar(row.position || index + 1);
      const title = sourceWorkbenchEditionComparatorNormalizeScalar(row.title || row.name);
      const duration = sourceWorkbenchEditionComparatorNormalizeScalar(row.duration);
      const parts = [position, title, duration].filter((entry) => entry);
      return parts.join(" ").trim();
    }

    function sourceWorkbenchEditionComparatorObjectText(definition, row, index = 0) {
      if (definition?.key === "identifier_items") return sourceWorkbenchEditionComparatorFormatIdentifierItem(row);
      if (definition?.key === "format_items") return sourceWorkbenchEditionComparatorFormatFormatItem(row);
      if (definition?.key === "company_items") return sourceWorkbenchEditionComparatorFormatCompanyItem(row);
      if (definition?.key === "track_list") return sourceWorkbenchEditionComparatorFormatTrackItem(row, index);
      return Object.values(row || {})
        .map((entry) => sourceWorkbenchEditionComparatorNormalizeScalar(entry))
        .filter((entry) => entry)
        .join(" | ");
    }

    function sourceWorkbenchEditionComparatorPreviewList(values, maxItems = 2) {
      const list = Array.isArray(values) ? values.filter((entry) => entry) : [];
      if (!list.length) return "-";
      if (list.length <= maxItems) return list.join(" | ");
      return `${list.slice(0, maxItems).join(" | ")} (+${list.length - maxItems} more)`;
    }

    function sourceWorkbenchEditionComparatorAnalyzeValue(definition, value) {
      if (definition?.type === "scalar") {
        const text = sourceWorkbenchEditionComparatorNormalizeScalar(value);
        return {
          empty: !text,
          comparable: Boolean(text),
          token: text.toLowerCase(),
          preview: text || "-",
          count: text ? 1 : 0,
        };
      }

      if (definition?.type === "track_list") {
        const list = Array.isArray(value)
          ? value.every((entry) => typeof entry === "string")
            ? sourceWorkbenchEditionComparatorNormalizeStringList(value)
            : sourceWorkbenchEditionComparatorNormalizeObjectList(value)
              .map((entry, index) => sourceWorkbenchEditionComparatorObjectText(definition, entry, index))
              .filter((entry) => entry)
          : [];
        return {
          empty: list.length === 0,
          comparable: list.length > 0,
          token: list.map((entry) => entry.toLowerCase()).join("\n"),
          preview: list.length ? `${list.length} tracks` : "-",
          count: list.length,
        };
      }

      if (definition?.type === "string_list") {
        const list = sourceWorkbenchEditionComparatorNormalizeStringList(value);
        return {
          empty: list.length === 0,
          comparable: list.length > 0,
          token: list.map((entry) => entry.toLowerCase()).join("\n"),
          preview: definition?.key === "runout_matrix"
            ? sourceWorkbenchEditionComparatorPreviewList(list, 2)
            : sourceWorkbenchEditionComparatorPreviewList(list, 2),
          count: list.length,
        };
      }

      const objects = sourceWorkbenchEditionComparatorNormalizeObjectList(value);
      const lines = objects
        .map((entry, index) => sourceWorkbenchEditionComparatorObjectText(definition, entry, index))
        .filter((entry) => entry);
      return {
        empty: objects.length === 0,
        comparable: lines.length > 0,
        token: lines.map((entry) => entry.toLowerCase()).join("\n"),
        preview: lines.length ? sourceWorkbenchEditionComparatorPreviewList(lines, 2) : "-",
        count: lines.length,
      };
    }

    function sourceWorkbenchEditionComparatorState(currentAnalysis, candidateAnalysis) {
      if (currentAnalysis.empty && candidateAnalysis.empty) return "UNCOMPARABLE";
      if (currentAnalysis.empty) return candidateAnalysis.comparable ? "CANDIDATE_ONLY" : "UNCOMPARABLE";
      if (candidateAnalysis.empty) return currentAnalysis.comparable ? "CURRENT_ONLY" : "UNCOMPARABLE";
      if (!currentAnalysis.comparable || !candidateAnalysis.comparable) return "UNCOMPARABLE";
      return currentAnalysis.token === candidateAnalysis.token ? "SAME" : "DIFFERENT";
    }

    function sourceWorkbenchEditionComparatorTrackDeltaSummary(currentAnalysis, candidateAnalysis, state) {
      if (state !== "DIFFERENT") return "";
      const delta = Number(candidateAnalysis?.count || 0) - Number(currentAnalysis?.count || 0);
      if (delta > 0) return `+${delta} candidate`;
      if (delta < 0) return `+${Math.abs(delta)} current`;
      return "";
    }

    function sourceWorkbenchEditionComparatorPresencePhrase(baseLabel, row) {
      if (!row) return "";
      if (row.state === "SAME") return `${baseLabel} matches`;
      if (row.state === "DIFFERENT") return `${baseLabel} differs`;
      if (row.state === "CANDIDATE_ONLY") return `${baseLabel} only on candidate`;
      if (row.state === "CURRENT_ONLY") return `${baseLabel} only on current`;
      return "";
    }

    function sourceWorkbenchEditionComparatorSummaryPhrase(row) {
      if (!row || row.state === "UNCOMPARABLE") return "";
      if (row.state === "SAME") {
        if (row.key === "track_list") return "Track list matches";
        if (row.key === "catalog_no") return "Catalog no matches";
        if (row.key === "barcode") return "Barcode matches";
        if (row.key === "pressing_country") return "Pressing country matches";
        if (row.key === "runout_matrix") return "Runout matches";
        return `${row.label || "Field"} matches`;
      }
      if (row.key === "catalog_no") {
        if (row.state === "DIFFERENT") return "Catalog no differs";
        if (row.state === "CANDIDATE_ONLY") return "Catalog no only on candidate";
        if (row.state === "CURRENT_ONLY") return "Catalog no only on current";
      }
      if (row.key === "barcode") {
        if (row.state === "DIFFERENT") return "Barcode differs";
        if (row.state === "CANDIDATE_ONLY") return "Barcode only on candidate";
        if (row.state === "CURRENT_ONLY") return "Barcode only on current";
      }
      if (row.key === "pressing_country") {
        if (row.state === "DIFFERENT") return "Pressing country differs";
        if (row.state === "CANDIDATE_ONLY") return "Pressing country only on candidate";
        if (row.state === "CURRENT_ONLY") return "Pressing country only on current";
      }
      if (row.key === "track_list") {
        if (row.state === "DIFFERENT") return row.deltaSummary ? `Track count differs (${row.deltaSummary})` : "Track listing differs";
        if (row.state === "CANDIDATE_ONLY") return "Track data only on candidate";
        if (row.state === "CURRENT_ONLY") return "Track data only on current";
      }
      if (row.key === "runout_matrix") {
        if (row.state === "DIFFERENT") return "Runout differs";
        if (row.state === "CANDIDATE_ONLY") return "Runout only on candidate";
        if (row.state === "CURRENT_ONLY") return "Runout only on current";
      }
      return "";
    }

    function sourceWorkbenchEditionComparatorCardHtml(payload = {}) {
      const summary = String(payload?.summary || "");
      const rows = Array.isArray(payload?.rows) ? payload.rows : [];
      const explanationRows = Array.isArray(payload?.explanations) ? payload.explanations : [];
      const comparatorIdentityChips = rows
        .filter((item) => item?.cardRole === "identity_chip")
        .map((item) => sourceWorkbenchEditionComparatorIdentityChipHtml(item))
        .filter(Boolean)
        .join("");
      const comparatorEvidenceRows = rows
        .filter((item) => item?.cardRole === "evidence_preview")
        .map((item) => sourceWorkbenchEditionComparatorEvidenceRowHtml(item))
        .filter(Boolean)
        .join("");
      const comparatorSecondaryRows = rows
        .filter((item) => !["identity_chip", "evidence_preview"].includes(String(item?.cardRole || "")))
        .filter((item) => ["DIFFERENT", "CANDIDATE_ONLY", "CURRENT_ONLY", "UNCOMPARABLE"].includes(String(item?.state || "").toUpperCase()))
        .map((item) => sourceWorkbenchEditionComparatorEvidenceRowHtml(item))
        .filter(Boolean)
        .join("");
      const comparatorEvidenceRowsCombined = [comparatorEvidenceRows, comparatorSecondaryRows].filter(Boolean).join("");
      return `
        <div class="source-workbench-edition-summary" data-source-workbench-edition-summary="${escapeHtml(summary)}">
          ${escapeHtml(summary)}
        </div>
        ${explanationRows.length
          ? `<div class="source-workbench-edition-explanation mini">Evidence: ${explanationRows.map((entry) => escapeHtml(String(entry || ""))).join("; ")}</div>`
          : ""
        }
        <div class="source-workbench-edition-identity">
          ${comparatorIdentityChips}
        </div>
        <details class="source-workbench-edition-evidence">
          <summary>Edition evidence</summary>
          <div class="source-workbench-edition-evidence-list">
            ${comparatorEvidenceRowsCombined || "<div class='mini'>No comparable evidence.</div>"}
          </div>
        </details>
      `;
    }

    function sourceWorkbenchEditionComparatorStateLabel(state) {
      const normalized = String(state || "").trim().toUpperCase();
      if (normalized === "SAME") return "same";
      if (normalized === "DIFFERENT") return "different";
      if (normalized === "CANDIDATE_ONLY") return "candidate only";
      if (normalized === "CURRENT_ONLY") return "current only";
      if (normalized === "UNCOMPARABLE") return "uncomparable";
      return "-";
    }

    function sourceWorkbenchEditionComparatorStateClass(state) {
      const normalized = String(state || "").trim().toUpperCase();
      if (normalized === "SAME") return "same";
      if (normalized === "DIFFERENT") return "different";
      if (normalized === "CANDIDATE_ONLY" || normalized === "CURRENT_ONLY") return "partial";
      return "uncomparable";
    }

    function sourceWorkbenchEditionComparatorIdentityChipHtml(row) {
      if (!row) return "";
      const stateClass = sourceWorkbenchEditionComparatorStateClass(row.state);
      const stateLabel = sourceWorkbenchEditionComparatorStateLabel(row.state);
      return `
                <span class="source-workbench-edition-identity-chip source-workbench-edition-identity-chip--${escapeHtml(stateClass)}">
                  <strong>${escapeHtml(row.label)}:</strong> ${escapeHtml(row.currentPreview || "-")} → ${escapeHtml(row.candidatePreview || "-")}
                  <em>${escapeHtml(stateLabel)}</em>
                </span>
      `.trim();
    }

    function sourceWorkbenchEditionComparatorEvidenceRowHtml(row) {
      if (!row) return "";
      const stateClass = sourceWorkbenchEditionComparatorStateClass(row.state);
      return `
        <div class="source-workbench-edition-evidence-row source-workbench-edition-evidence-row--${escapeHtml(stateClass)}">
          <div class="source-workbench-edition-evidence-row-head">
            <strong>${escapeHtml(row.label)}</strong>
            <span>${escapeHtml(sourceWorkbenchEditionComparatorStateLabel(row.state))}</span>
          </div>
          <div class="source-workbench-edition-evidence-row-values">
            <span>${escapeHtml(String(row.currentPreview || "-"))}</span>
            <span>→</span>
            <span>${escapeHtml(String(row.candidatePreview || "-"))}</span>
          </div>
        </div>
      `.trim();
    }

    function sourceWorkbenchActionLabel(mode) {
      const code = String(mode || "").trim().toUpperCase();
      if (code === "AUTO_READY") return t("media.source.action.auto_apply");
      if (code === "ROW_UPDATE") return t("media.source.action.row_update");
      return t("media.source.action.apply_selected");
    }

    function loadSourceWorkbenchQueue() {
      try {
        const raw = window.localStorage.getItem(SOURCE_WORKBENCH_QUEUE_KEY);
        if (!raw) {
          sourceWorkbenchQueue = [];
          return;
        }
        const parsed = JSON.parse(raw);
        sourceWorkbenchQueue = Array.isArray(parsed) ? parsed : [];
      } catch (_err) {
        sourceWorkbenchQueue = [];
      }
    }

    function renderSourceWorkbenchQueue() {
      const root = $("sourceWorkbenchQueue");
      if (!root) return;
      const list = Array.isArray(sourceWorkbenchQueue) ? sourceWorkbenchQueue : [];
      if (!list.length) {
        root.innerHTML = `<div class='mini muted'>${escapeHtml(t("media.source.status.queue_empty"))}</div>`;
        return;
      }
      root.innerHTML = list.map((entry, idx) => `
        <div class="source-queue-row">
          <span class="source-queue-badge ${String(entry.status || '').toLowerCase()}">${escapeHtml(sourceQueueStatusLabel(entry.status))}</span>
          <div class="source-queue-main">
            <div class="source-queue-title">${escapeHtml(entry.item_name || "-")}</div>
            <div class="source-queue-meta">${escapeHtml([entry.label_id, sourceQueueModeLabel(entry.mode), formatDateTimeCompact(entry.created_at), entry.detail].filter(Boolean).join(" | "))}</div>
          </div>
          <div class="source-queue-actions">
            ${entry.owned_item_id ? `<button class="btn ghost" type="button" data-source-queue-open="${Number(entry.owned_item_id)}">${escapeHtml(t("media.source.queue.action.open"))}</button>` : ""}
            <button class="btn ghost" type="button" data-source-queue-remove="${idx}">${escapeHtml(t("media.source.queue.action.delete"))}</button>
          </div>
        </div>
      `).join("");
    }

    function loadSourceWorkbenchRowsFromItems(rows, statusText) {
      const items = Array.isArray(rows) ? rows.filter(Boolean) : [];
      sourceWorkbenchRows = items.map((row) => ({
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
      if (items[0]) seedSourceWorkbenchFromOwnedItem(items[0]);
      switchMainTab("source");
      setStatus("sourceWorkbenchStatus", "ok", statusText || t("media.source.status.targets_ready", {
        count: formatCount(items.length),
      }));
    }

    function syncSourceWorkbenchSearchInputs(rowIndex) {
      const entry = sourceWorkbenchRows[rowIndex];
      if (!entry) return;
      const artistInput = document.querySelector(`[data-workbench-artist-input="${rowIndex}"]`);
      const titleInput = document.querySelector(`[data-workbench-title-input="${rowIndex}"]`);
      if (artistInput) entry.searchArtistName = String(artistInput.value || "");
      if (titleInput) entry.searchItemName = String(titleInput.value || "");
    }

    function applySourceWorkbenchResults(results) {
      const list = Array.isArray(results) ? results : [];
      if (!list.length) return;
      const filterState = String($("sourceWorkbenchSourceState")?.value || "MISSING").trim().toUpperCase();
      const resultMap = new Map(list.map((row) => [Number(row?.owned_item_id || 0), row]));
      const nextRows = [];
      for (const entry of Array.isArray(sourceWorkbenchRows) ? sourceWorkbenchRows : []) {
        const ownedItemId = Number(entry?.item?.id || 0);
        const result = resultMap.get(ownedItemId);
        if (!result) {
          nextRows.push(entry);
          continue;
        }
        if (!result.updated) {
          nextRows.push({
            ...entry,
            error: String(result.error || t("media.source.queue.detail.updated_failed")),
          });
          continue;
        }
        const nextEntry = {
          ...entry,
          item: {
            ...entry.item,
            source_code: result.source_code || entry.item.source_code || null,
            source_external_id: result.source_external_id || entry.item.source_external_id || null,
          },
          candidates: [],
          selectedIdx: -1,
          selectionMode: null,
          querySummary: "",
          loading: false,
          error: "",
        };
        if (filterState !== "MISSING") nextRows.push(nextEntry);
      }
      sourceWorkbenchRows = nextRows;
      renderSourceWorkbenchList();
    }

    function renderSourceWorkbenchList() {
      const root = $("sourceWorkbenchList");
      if (!root) return;
      const rows = Array.isArray(sourceWorkbenchRows) ? sourceWorkbenchRows : [];
      $("sourceWorkbenchCount").textContent = countWithUnit(rows.length);
      if (!rows.length) {
        root.innerHTML = `<div class='muted'>${escapeHtml(t("media.source.status.targets_empty"))}</div>`;
        return;
      }

      root.innerHTML = rows.map((entry, idx) => {
        const row = entry.item || {};
        const currentSourceText = row.source_code && row.source_external_id
          ? `${row.source_code}#${row.source_external_id}`
          : t("media.source.current_source.unlinked");
        const currentCoverUrl = normalizeRenderableCoverUrl(row.cover_image_url);
        const currentCover = currentCoverUrl
          ? `<img src="${escapeHtml(currentCoverUrl)}" alt="${escapeHtml(resolveOwnedAlbumName(row))}" />`
          : escapeHtml(mediaDisplayLabel(row.category || ""));
        const currentMeta = [
          row.label_id,
          mediaDisplayLabel(row.category || ""),
          row.artist_or_brand || row.linked_artist_name || "-",
          row.catalog_no ? t("common.meta.catalog_no", { value: row.catalog_no }) : null,
          row.barcode ? t("common.meta.barcode", { value: row.barcode }) : null,
          t("media.source.current_source.label", { source: currentSourceText }),
        ].filter(Boolean);
        const selectedCandidate = entry.selectedIdx >= 0 ? entry.candidates[entry.selectedIdx] : null;
        const searchArtistValue = String(entry.searchArtistName || "").trim();
        const searchItemValue = String(entry.searchItemName || "").trim();
        const selectedText = selectedCandidate
          ? `${entry.selectionMode === "AUTO" ? t("media.source.selection.auto_ready") : t("media.source.selection.selected")}: ${selectedCandidate.source}#${selectedCandidate.external_id}`
          : t("media.source.selection.none");
        const candidateHtml = entry.candidates.map((candidate, candidateIdx) => {
          const selected = candidateIdx === entry.selectedIdx;
          const comparatorRows = buildSourceWorkbenchEditionComparatorRows({ current: row, candidate });
          const comparatorSummary = buildSourceWorkbenchEditionComparatorSummary({ current: row, candidate });
          const comparatorExplanations = buildSourceWorkbenchEditionComparatorExplanationPhrases({ current: row, candidate });
          const galleryKey = registerImageGallery(`workbench:${normalizeSourceCode(candidate.source)}:${candidate.external_id || `${idx}-${candidateIdx}`}`, candidate, {
            title: `${String(candidate.artist_or_brand || "").trim() || t("common.unknown")} - ${String(candidate.title || "").trim() || t("common.no_title")}`,
            subtitle: `${normalizeSourceCode(candidate.source) || "-"}#${candidate.external_id || "-"}`,
          });
          const galleryCount = galleryKey ? Number(imageGalleryRegistry.get(galleryKey)?.items?.length || 0) : 0;
          const coverUrl = normalizeRenderableCoverUrl(candidate.cover_image_url);
          const cover = coverUrl
            ? `<img src="${escapeHtml(coverUrl)}" alt="${escapeHtml(candidate.title || "")}" />`
            : escapeHtml(mediaDisplayLabel(candidate.format_name || row.category || ""));
          const discogsLink = discogsReleaseLinkHtml(candidate.source, candidate.external_id, "Discogs");
          return `
            <div class="source-workbench-candidate ${selected ? "selected" : ""}">
              <div class="source-workbench-cover">${cover}</div>
              <div class="source-workbench-candidate-main">
                <div class="source-workbench-candidate-title">${escapeHtml(String(candidate.artist_or_brand || "").trim() || t("common.unknown"))} - ${escapeHtml(String(candidate.title || "").trim() || t("common.no_title"))}</div>
                <div class="source-workbench-candidate-meta">
                  <span class="tag">${escapeHtml(candidate.source || "-")}</span>
                  <span>${escapeHtml(t("common.meta.release_date", { value: candidate.released_date || candidate.release_year || "-" }))}</span>
                  <span>${escapeHtml(t("common.meta.catalog_no", { value: candidate.catalog_no || "-" }))}</span>
                  <span>${escapeHtml(t("common.meta.barcode", { value: candidate.barcode || "-" }))}</span>
                  <span>${escapeHtml(t("common.meta.format", { value: candidate.format_name || "-" }))}</span>
                  <span>${escapeHtml(t("common.meta.track_count", { value: formatCount(Array.isArray(candidate.track_list) ? candidate.track_list.length : 0) }))}</span>
                </div>
                <div class="mini">${escapeHtml(t("media.source.candidate.meta.external_id", { value: candidate.external_id || "-" }))}${discogsLink ? ` | ${discogsLink}` : ""}${galleryKey ? ` | ${imageGalleryButtonHtml(galleryKey, t("media.source.candidate.action.images", { count: formatCount(galleryCount) }))}` : ""}</div>
                ${sourceWorkbenchEditionComparatorCardHtml({ summary: comparatorSummary, rows: comparatorRows, explanations: comparatorExplanations })}
              </div>
              <div class="source-workbench-candidate-actions">
                <button class="btn ghost" type="button" data-workbench-select="${idx}:${candidateIdx}">${selected ? escapeHtml(t("media.source.action.selected")) : escapeHtml(t("media.source.action.select"))}</button>
              </div>
            </div>
          `;
        }).join("");

        const rowClass = [
          "source-workbench-row",
          entry.loading ? "loading" : "",
          selectedCandidate ? "selected" : "",
        ].filter(Boolean).join(" ");

        return `
          <div class="${rowClass}">
            <div class="source-workbench-head">
              <div class="source-workbench-cover">${currentCover}</div>
              <div class="source-workbench-head-main">
                <div class="source-workbench-title">${escapeHtml(resolveOwnedAlbumName(row))}</div>
                <div class="source-workbench-meta">${currentMeta.map((text) => `<span>${escapeHtml(text)}</span>`).join("")}</div>
                <div class="source-workbench-query">${escapeHtml(t("media.source.query.summary", { query: entry.querySummary || "-", selected: selectedText }))}</div>
                <div class="source-workbench-search-adjust">
                  <label>
                    ${escapeHtml(t("media.source.field.artist_override.label"))}
                    <input type="text" value="${escapeHtml(searchArtistValue)}" placeholder="${escapeHtml(t("media.source.field.artist_override.placeholder"))}" data-workbench-artist-input="${idx}" />
                  </label>
                  <label>
                    ${escapeHtml(t("media.source.field.item_override.label"))}
                    <input type="text" value="${escapeHtml(searchItemValue)}" placeholder="${escapeHtml(t("media.source.field.item_override.placeholder"))}" data-workbench-title-input="${idx}" />
                  </label>
                  <div class="source-workbench-search-actions">
                    <button class="btn ghost" type="button" data-workbench-refind="${idx}">${entry.loading ? escapeHtml(t("media.source.status.candidates_loading_short")) : escapeHtml(t("media.source.action.lookup_candidates"))}</button>
                    <button class="btn ghost" type="button" data-workbench-reset="${idx}">${escapeHtml(t("media.source.action.reset_search"))}</button>
                  </div>
                </div>
                ${entry.error ? `<div class="mini console-inline-error">${escapeHtml(entry.error)}</div>` : ""}
              </div>
              <div class="source-workbench-row-actions">
                <button class="btn ghost" type="button" data-workbench-find="${idx}">${entry.loading ? escapeHtml(t("media.source.status.candidates_loading_short")) : escapeHtml(t("media.source.action.lookup_candidates"))}</button>
                <button class="btn ghost" type="button" data-workbench-apply="${idx}">${escapeHtml(t("media.source.action.row_update"))}</button>
              </div>
            </div>
            ${candidateHtml || `<div class='mini muted'>${escapeHtml(t("media.source.status.no_candidates_yet"))}</div>`}
          </div>
        `;
      }).join("");
    }

    function sourceWorkbenchDiffStatusClass(status) {
      const code = String(status || "").trim().toLowerCase();
      return code ? ` ${code.replace(/_/g, "-")}` : "";
    }

    function sourceWorkbenchDiffSummaryText(reviewState) {
      const summary = reviewState?.summary || {};
      const itemCount = Number(summary.itemCount || 0);
      const selectedFieldCount = Number(summary.selectedFieldCount || 0);
      const actionableFieldCount = Number(summary.actionableFieldCount || 0);
      const sources = Array.isArray(summary.candidateSources) && summary.candidateSources.length
        ? summary.candidateSources.join(", ")
        : "-";
      return t("media.source.diff.summary", {
        items: countWithUnit(itemCount),
        selected: formatCount(selectedFieldCount),
        actionable: formatCount(actionableFieldCount),
        sources,
      });
    }

    function renderSourceWorkbenchDiffValue(row, side) {
      const displayValue = side === "candidate" ? row?.candidateDisplay : row?.currentDisplay;
      const safeText = Array.isArray(displayValue)
        ? displayValue.join("\n")
        : String(displayValue || "").trim();
      if (row?.presentation === "cover_thumb") {
        const currentUrl = String((side === "candidate" ? row?.candidateValue : row?.currentValue) || "").trim();
        const thumbHtml = currentUrl
          ? `<img src="${escapeHtml(currentUrl)}" alt="${escapeHtml(t(side === "candidate" ? "media.source.diff.cover.alt.candidate" : "media.source.diff.cover.alt.current"))}" />`
          : escapeHtml(t("common.unspecified"));
        return `
          <div class="source-workbench-diff-cover-box">
            <div class="source-workbench-diff-cover-thumb">${thumbHtml}</div>
            <div class="mini">${escapeHtml(currentUrl || t("common.unspecified"))}</div>
          </div>
        `;
      }
      if (row?.presentation === "track_fold") {
        const lines = Array.isArray(displayValue) ? displayValue : [];
        const countText = lines.length ? t("media.source.diff.track.count", { count: formatCount(lines.length) }) : t("common.unspecified");
        return `
          <details class="source-workbench-diff-track-preview">
            <summary>${escapeHtml(countText)}</summary>
            ${lines.length ? `<ol>${lines.map((line) => `<li>${escapeHtml(line)}</li>`).join("")}</ol>` : `<div class="mini">${escapeHtml(t("common.unspecified"))}</div>`}
          </details>
        `;
      }
      const emphasis = row?.presentation === "meta_emphasis" && safeText
        ? `<span class="source-workbench-diff-inline-strong">${escapeHtml(safeText)}</span>`
        : "";
      return `
        <div class="source-workbench-diff-value-card">
          ${emphasis}
          <div>${escapeHtml(safeText || t("common.unspecified"))}</div>
        </div>
      `;
    }

    function renderSourceWorkbenchDiffReview() {
      const modal = $("sourceWorkbenchDiffReview");
      const list = $("sourceWorkbenchDiffReviewList");
      const summaryEl = $("sourceWorkbenchDiffReviewSummary");
      if (!modal || !list || !summaryEl) return;
      const reviewState = sourceWorkbenchDiffReviewState;
      if (!reviewState || !Array.isArray(reviewState.items) || !reviewState.items.length) {
        summaryEl.textContent = t("common.count.zero_items");
        list.innerHTML = `<div class="mini muted">${escapeHtml(t("media.source.status.apply_none_selected"))}</div>`;
        return;
      }
      reviewState.summary.selectedFieldCount = sourceWorkbenchDiffReviewFieldCount(reviewState);
      summaryEl.textContent = sourceWorkbenchDiffSummaryText(reviewState);
      list.innerHTML = reviewState.items.map((item, itemIndex) => `
        <section class="source-workbench-diff-card">
          <div class="source-workbench-diff-card-head">
            <div>
              <span class="source-workbench-diff-card-head-label">${escapeHtml(t("media.source.diff.card.label_id"))}</span>
              <div class="source-workbench-diff-card-head-value">${escapeHtml(item.labelId)}</div>
            </div>
            <div>
              <span class="source-workbench-diff-card-head-label">${escapeHtml(t("media.source.diff.card.current_title"))}</span>
              <div class="source-workbench-diff-card-head-value">${escapeHtml(item.currentTitle)}</div>
            </div>
            <div>
              <span class="source-workbench-diff-card-head-label">${escapeHtml(t("media.source.diff.card.candidate_source"))}</span>
              <div class="source-workbench-diff-card-head-value">${escapeHtml(item.candidateExternalId ? `${item.candidateSource}#${item.candidateExternalId}` : item.candidateSource)}</div>
            </div>
            <div>
              <span class="source-workbench-diff-card-head-label">${escapeHtml(t("media.source.diff.card.candidate_title"))}</span>
              <div class="source-workbench-diff-card-head-value">${escapeHtml(item.candidateTitle)}</div>
            </div>
          </div>
          <div class="source-workbench-diff-card-body">
            ${item.fieldRows.map((row) => `
              <label class="source-workbench-diff-row ${row.selected ? "is-selected" : ""} ${row.disabled ? "is-disabled" : ""} ${row.presentation === "meta_emphasis" ? "source-workbench-diff-row--emphasis" : ""}">
                <div class="source-workbench-diff-check">
                  <input type="checkbox" data-source-workbench-diff-toggle="${itemIndex}:${row.key}" ${row.selected ? "checked" : ""} ${row.disabled ? "disabled" : ""} />
                </div>
                <div class="source-workbench-diff-label">
                  <strong>${escapeHtml(t(row.labelKey || row.label))}</strong>
                  <span>${escapeHtml(row.key)}</span>
                </div>
                <div class="source-workbench-diff-value">
                  ${renderSourceWorkbenchDiffValue(row, "current")}
                </div>
                <div class="source-workbench-diff-value">
                  ${renderSourceWorkbenchDiffValue(row, "candidate")}
                </div>
                <span class="source-workbench-diff-status-badge${sourceWorkbenchDiffStatusClass(row.status)}">${escapeHtml(t(row.statusLabelKey || row.statusLabel))}</span>
              </label>
            `).join("")}
          </div>
        </section>
      `).join("");
    }

    function updateSourceWorkbenchDiffSelections(mode) {
      if (!sourceWorkbenchDiffReviewState || !Array.isArray(sourceWorkbenchDiffReviewState.items)) return;
      for (const item of sourceWorkbenchDiffReviewState.items) {
        if (!Array.isArray(item?.fieldRows)) continue;
        for (const row of item.fieldRows) {
          if (row.disabled) {
            row.selected = false;
            continue;
          }
          if (mode === "ALL") row.selected = true;
          else if (mode === "EMPTY_ONLY") row.selected = row.status === "EMPTY_FILL";
          else row.selected = false;
        }
      }
      renderSourceWorkbenchDiffReview();
    }

    function updateSourceWorkbenchDiffFieldSelection(itemIndex, fieldKey, selected) {
      const item = sourceWorkbenchDiffReviewState?.items?.[itemIndex];
      if (!item || !Array.isArray(item.fieldRows)) return;
      const row = item.fieldRows.find((entry) => entry?.key === fieldKey);
      if (!row || row.disabled) return;
      row.selected = Boolean(selected);
      renderSourceWorkbenchDiffReview();
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
