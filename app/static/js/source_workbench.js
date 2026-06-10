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
