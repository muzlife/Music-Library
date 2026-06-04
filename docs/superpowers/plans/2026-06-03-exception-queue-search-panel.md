# Exception Queue Search Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 예외 큐에 세밀한 검색 필터 입력 영역과 우측 sticky 컨텍스트 패널을 추가하여, 예외 종류 기반 목록을 검색 필터로 더 정교하게 좁히고 선택 항목 상세를 즉시 확인할 수 있게 한다. 필터 조합은 기존 프리셋 저장 기능으로 재사용 가능하다.

**Architecture:**
- `opsExceptionPanel`을 `media-search-layout` (flex 60/40) 구조로 전환. 좌측: 기존 예외 카드(예외 종류 + 새 검색 필터 + 결과 목록 + 벌크 툴바). 우측: 새 `opsExceptionContextPanel` (sticky, 선택 항목 상세).
- 검색 필터(아티스트, 상품명, 바코드, 카탈로그, 발매년, 도메인)는 새 ID(`opsExArtist` 등)로 추가. `buildOpsExceptionParams` / master URL 빌더가 이 필드를 읽어 API 호출에 포함.
- 프리셋 직렬화 객체에 새 필드를 추가하고 `applyOpsExceptionPresetByIndex`에서 복원. 기존 프리셋(구 형식)은 새 필드를 빈값으로 복원하여 하위 호환.
- 행 클릭 핸들러: OwnedItem 예외는 `renderMediaSearchContextSelection` 재사용, Master 예외(REVIEW_MISSING 등)는 `/owned-items?album_master_id=` 조회 후 컨텍스트 렌더.

**Tech Stack:** Vanilla JS, HTML/CSS (index.html 단일 파일), FastAPI `/owned-items` + `/album-masters` 기존 엔드포인트

---

## File Map

| 파일 | 변경 내용 |
|------|-----------|
| `app/static/index.html` | CSS 추가, HTML 구조 변경, JS 함수 수정/추가 |

백엔드 변경 없음. 기존 `/owned-items`, `/album-masters` 엔드포인트가 이미 필요한 모든 필터 파라미터를 지원한다.

---

## Task 1: CSS — 레이아웃 및 컨텍스트 패널 스타일 추가

**Files:**
- Modify: `app/static/index.html` (CSS 블록, ~line 8987 근처 ops-exception 섹션)

- [ ] **Step 1: CSS 추가**

기존 `.ops-exception-row { ... }` 블록 바로 위에 다음을 삽입:

```css
/* Exception queue: two-panel search layout */
#opsExceptionPanel .ops-exception-search-layout {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}
#opsExceptionPanel .ops-exception-main-card {
  flex: 0 1 60%;
  min-width: 0;
}
#opsExceptionContextPanel {
  flex: 0 1 40%;
  min-width: 0;
  display: grid;
  gap: 8px;
  align-content: start;
  align-self: start;
  position: sticky;
  top: 20px;
}
/* Search filter grid — same pattern as home-search-grid-top */
.ops-ex-search-grid {
  display: grid;
  grid-template-columns: minmax(0,1fr) minmax(0,1fr) minmax(0,1fr) 80px;
  gap: 6px;
  margin-top: 8px;
}
.ops-ex-search-grid label {
  font-size: 0.72rem;
  color: var(--muted);
  display: block;
  margin-bottom: 2px;
}
/* Narrow breakpoint: stack to single column */
@media (max-width: 900px) {
  #opsExceptionPanel .ops-exception-search-layout { flex-direction: column; }
  #opsExceptionContextPanel { position: static; }
  .ops-ex-search-grid { grid-template-columns: repeat(2, minmax(0,1fr)); }
}
```

- [ ] **Step 2: 커밋**

```bash
git add app/static/index.html
git commit -m "style(exception-queue): add two-panel search layout CSS"
```

---

## Task 2: HTML — 레이아웃 구조 전환 + 검색 필터 + 컨텍스트 패널 추가

**Files:**
- Modify: `app/static/index.html` (~line 20868 `opsExceptionPanel`)

현재 구조:
```html
<div id="opsExceptionPanel" class="subtab-panel admin-console-main">
  <details>...</details>
  <div class="layout">
    <section class="card">
      ... (필터 바, 목록, 툴바 전체)
    </section>
  </div>
</div>
```

목표 구조:
```html
<div id="opsExceptionPanel" class="subtab-panel admin-console-main">
  <details>...</details>
  <div class="ops-exception-search-layout">
    <!-- 좌측: 기존 카드 -->
    <section class="card ops-exception-main-card">
      ... (기존 내용 유지 + 검색 필터 추가)
    </section>
    <!-- 우측: 새 컨텍스트 패널 -->
    <aside id="opsExceptionContextPanel">
      ... (선택 항목 상세)
    </aside>
  </div>
</div>
```

- [ ] **Step 1: 외부 div 교체**

`<div class="layout">` → `<div class="ops-exception-search-layout">` 로 변경.
`<section class="card">` → `<section class="card ops-exception-main-card">` 로 변경.

- [ ] **Step 2: 검색 필터 행 추가**

`<div class="ops-exception-inline-row">` (기존 예외종류/표시수/도메인/프리셋 행) 바로 **다음**에 삽입:

```html
<div class="ops-ex-search-grid" id="opsExSearchGrid">
  <div>
    <label for="opsExArtist">아티스트명</label>
    <input id="opsExArtist" type="text" placeholder="예: Pink Floyd" />
  </div>
  <div>
    <label for="opsExTitle">상품명</label>
    <input id="opsExTitle" type="text" placeholder="예: The Wall" />
  </div>
  <div>
    <label for="opsExBarcode">바코드</label>
    <input id="opsExBarcode" type="text" placeholder="예: 5099902987606" />
  </div>
  <div>
    <label for="opsExCatalogNo">카탈로그</label>
    <input id="opsExCatalogNo" type="text" placeholder="예: SMAS-3723" />
  </div>
  <div>
    <label for="opsExReleaseYear">발매년</label>
    <input id="opsExReleaseYear" type="number" min="1900" max="2100" placeholder="예: 1979" />
  </div>
</div>
```

- [ ] **Step 3: 우측 컨텍스트 패널 추가**

`</section>` (기존 카드 닫는 태그) 바로 **뒤**에 삽입:

```html
<aside id="opsExceptionContextPanel">
  <section class="card" id="opsExContextCard" style="display:none;">
    <div id="opsExContextBody"></div>
  </section>
  <div id="opsExContextEmpty" class="mini muted" style="padding:12px 0;">
    목록에서 항목을 클릭하면 상세 정보가 표시됩니다.
  </div>
</aside>
```

- [ ] **Step 4: 커밋**

```bash
git add app/static/index.html
git commit -m "feat(exception-queue): two-panel layout + search filter inputs + context panel shell"
```

---

## Task 3: JS — `buildOpsExceptionParams` 확장 (검색 필터 → OwnedItem API 파라미터)

**Files:**
- Modify: `app/static/index.html` (함수 `buildOpsExceptionParams`, ~line 37633)

OwnedItem 예외(UNSLOTTED, SOURCE_MISSING 등)는 `/owned-items` 를 사용한다. 이 함수가 새 검색 필터 입력값을 읽어 파라미터에 포함시킨다.

- [ ] **Step 1: 함수 수정**

```javascript
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

  // 검색 필터 추가
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
  return params;
}
```

- [ ] **Step 2: 커밋**

```bash
git add app/static/index.html
git commit -m "feat(exception-queue): add search filters to buildOpsExceptionParams"
```

---

## Task 4: JS — Master 예외 URL 빌더에 검색 필터 추가

**Files:**
- Modify: `app/static/index.html` (함수 `loadOpsExceptionItems`, ~line 44866)

Master 예외(SPOTIFY_UNMATCHED, GENRE_MISSING, CATALOG_MISSING, REVIEW_MISSING)는 `/album-masters` 를 사용한다. URL 조립 코드에 검색 필터를 추가한다.

- [ ] **Step 1: URL 빌더 함수 추출**

`loadOpsExceptionItems` 내부의 master URL 조립 로직을 `buildMasterExceptionUrl(type, limit)` 헬퍼로 분리:

```javascript
function buildMasterExceptionUrl(type, limit) {
  let url = `/album-masters?include_total=true&limit=${limit}`;
  if (type === "SPOTIFY_UNMATCHED") url += "&spotify_state=MISSING";
  else if (type === "GENRE_MISSING")    url += "&genre_missing=true&media_only=true";
  else if (type === "REVIEW_MISSING")   url += "&review_missing=true&media_only=true";
  else                                   url += "&catalog_missing=true&media_only=true";

  // 검색 필터
  const artist = String($("opsExArtist")?.value || "").trim();
  const title  = String($("opsExTitle")?.value  || "").trim();
  const domain = String($("opsExceptionDomain")?.value || "").trim();
  const releaseYear = String($("opsExReleaseYear")?.value || "").trim();
  if (artist)      url += `&artist_or_brand=${encodeURIComponent(artist)}`;
  if (title)       url += `&q=${encodeURIComponent(title)}`;
  if (domain && type !== "REVIEW_MISSING") url += `&domain_code=${encodeURIComponent(domain)}`;
  // REVIEW_MISSING의 domain 필터는 기존 로직이 이미 처리하므로 그대로 유지
  if (releaseYear) url += `&release_year=${encodeURIComponent(releaseYear)}`;
  return url;
}
```

`loadOpsExceptionItems`의 master URL 조립 부분을 `buildMasterExceptionUrl(type, limit)` 호출로 교체.

`fetchOpsExceptionCount`의 master URL도 동일하게 교체 (count 용 `limit=1` 버전):

```javascript
function buildMasterExceptionCountUrl(type) {
  let url = `/album-masters?include_total=true&limit=1`;
  if (type === "SPOTIFY_UNMATCHED") url += "&spotify_state=MISSING";
  else if (type === "GENRE_MISSING")    url += "&genre_missing=true&media_only=true";
  else if (type === "REVIEW_MISSING")   url += "&review_missing=true&media_only=true";
  else                                   url += "&catalog_missing=true&media_only=true";
  const domain = String($("opsExceptionDomain")?.value || "").trim();
  if (domain) url += `&domain_code=${encodeURIComponent(domain)}`;
  return url;
}
```

- [ ] **Step 2: 커밋**

```bash
git add app/static/index.html
git commit -m "feat(exception-queue): add search filters to master exception URL builder"
```

---

## Task 5: JS — 프리셋 저장/복원에 검색 필터 추가

**Files:**
- Modify: `app/static/index.html` (프리셋 저장 핸들러 ~line 56108, `applyOpsExceptionPresetByIndex` ~line 37522)

- [ ] **Step 1: 프리셋 저장 핸들러 수정**

`$("opsExceptionPresetSaveBtn").addEventListener(...)` 내부에서 preset 객체를 만드는 곳에 검색 필터 필드 추가:

```javascript
const preset = {
  name: String($("opsExceptionPresetName")?.value || "").trim(),
  type: String($("opsExceptionType")?.value || "UNSLOTTED").trim().toUpperCase(),
  limit: Number($("opsExceptionLimit")?.value || 50),
  domain: String($("opsExceptionDomain")?.value || "").trim(),
  // 새 검색 필터
  artist:      String($("opsExArtist")?.value      || "").trim(),
  title:       String($("opsExTitle")?.value        || "").trim(),
  barcode:     String($("opsExBarcode")?.value      || "").trim(),
  catalogNo:   String($("opsExCatalogNo")?.value    || "").trim(),
  releaseYear: String($("opsExReleaseYear")?.value  || "").trim(),
};
```

- [ ] **Step 2: `applyOpsExceptionPresetByIndex` 수정**

```javascript
function applyOpsExceptionPresetByIndex(indexValue) {
  const idx = Number(indexValue);
  if (!Number.isInteger(idx) || idx < 0) return false;
  const rows = loadOpsExceptionPresets();
  const preset = rows[idx];
  if (!preset) return false;
  $("opsExceptionType").value = String(preset.type || "UNSLOTTED").trim().toUpperCase();
  $("opsExceptionLimit").value = String(Math.max(10, Math.min(200, Number(preset.limit || 50))));
  if ($("opsExceptionPresetName")) $("opsExceptionPresetName").value = String(preset.name || "").trim();
  if ($("opsExceptionDomain"))    $("opsExceptionDomain").value    = String(preset.domain    || "").trim();
  // 새 검색 필터 복원 (구 프리셋은 빈 문자열로 복원 → 필터 없는 상태)
  if ($("opsExArtist"))      $("opsExArtist").value      = String(preset.artist      || "").trim();
  if ($("opsExTitle"))       $("opsExTitle").value        = String(preset.title       || "").trim();
  if ($("opsExBarcode"))     $("opsExBarcode").value      = String(preset.barcode     || "").trim();
  if ($("opsExCatalogNo"))   $("opsExCatalogNo").value    = String(preset.catalogNo   || "").trim();
  if ($("opsExReleaseYear")) $("opsExReleaseYear").value  = String(preset.releaseYear || "").trim();
  syncOpsExceptionSelectionControls();
  return true;
}
```

- [ ] **Step 3: 검색 필터 초기화 버튼 추가**

`opsExSearchGrid` 내에 리셋 버튼 추가:

```html
<div style="display:flex;align-items:flex-end;">
  <button id="opsExSearchResetBtn" class="btn ghost icon-symbol-btn icon-symbol-btn--reset" type="button" title="검색 필터 초기화" aria-label="검색 필터 초기화"></button>
</div>
```

이벤트 연결:

```javascript
$("opsExSearchResetBtn")?.addEventListener("click", () => {
  ["opsExArtist","opsExTitle","opsExBarcode","opsExCatalogNo","opsExReleaseYear"].forEach(id => {
    const el = $(id); if (el) el.value = "";
  });
});
```

Enter 키로 즉시 검색:

```javascript
["opsExArtist","opsExTitle","opsExBarcode","opsExCatalogNo","opsExReleaseYear"].forEach(id => {
  $(id)?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); loadOpsExceptionItems(); }
  });
});
```

- [ ] **Step 4: 커밋**

```bash
git add app/static/index.html
git commit -m "feat(exception-queue): persist/restore search filters in presets"
```

---

## Task 6: JS — 행 클릭 핸들러 + 컨텍스트 패널 렌더링

**Files:**
- Modify: `app/static/index.html` (이벤트 핸들러, 새 함수 추가)

- [ ] **Step 1: `renderOpsExceptionContextPanel` 함수 추가**

```javascript
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

  const isMasterType = (type === "SPOTIFY_UNMATCHED" || type === "GENRE_MISSING"
                        || type === "CATALOG_MISSING" || type === "REVIEW_MISSING");

  if (isMasterType) {
    // Master 예외: 마스터 카드 + 보유 상품 수 표시
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
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;">
        <button class="btn ghost tiny" type="button"
          onclick="openMediaSearchDetailManage(${masterId},0)">관리 화면으로</button>
        <button class="btn ghost tiny" type="button"
          data-ops-exception-review-auto="${masterId}">Wikipedia 자동수집</button>
      </div>
    `;
    // 보유 상품 목록 비동기 로드
    try {
      const res = await fetchWithRetry(`/owned-items?album_master_id=${masterId}&limit=10&include_total=true`);
      const data = await safeJson(res);
      const items = Array.isArray(data) ? data : [];
      const total = Number(res.headers.get("X-Total-Count") || items.length);
      const el = $("opsExCtxMasterItems");
      if (!el) return;
      if (!items.length) { el.textContent = "보유 상품 없음"; return; }
      el.innerHTML = `<strong style="font-size:0.75rem;">보유 상품 ${total}건</strong><div style="margin-top:4px;display:flex;flex-direction:column;gap:2px;">${
        items.slice(0,5).map(it => {
          const name = resolveOwnedAlbumName(it);
          const loc = it.slot_code || t("common.unslotted");
          return `<div style="font-size:0.72rem;">${escapeHtml(name)} — ${escapeHtml(loc)}</div>`;
        }).join("")
      }${total > 5 ? `<div class="mini muted">외 ${total-5}건</div>` : ""}</div>`;
    } catch (_) {}
  } else {
    // OwnedItem 예외: 기존 컨텍스트 렌더 재활용
    const ownedItemId = Number(row.id || 0);
    body.innerHTML = `<div class="mini muted">상품 #${ownedItemId} 상세 조회 중...</div>`;
    try {
      const res = await fetchWithRetry(`/owned-items/${ownedItemId}`);
      const data = await safeJson(res);
      if (!res.ok) throw new Error(data.detail || "조회 실패");
      // renderMediaSearchContextSelection은 별도 DOM을 조작하므로
      // 여기서는 핵심 정보를 직접 렌더한다
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
    } catch (err) {
      body.innerHTML = `<div class="mini muted" style="color:var(--err);">오류: ${escapeHtml(String(err.message||err))}</div>`;
    }
  }
}
```

- [ ] **Step 2: `renderOpsExceptionList` 에 행 클릭 이벤트 연결**

`renderOpsExceptionList` 함수 내부, 기존 `syncOpsExceptionSelectionControls()` 호출 직전에 삽입:

```javascript
// 행 클릭 → 컨텍스트 패널
root.querySelectorAll(".ops-exception-row").forEach((rowEl) => {
  rowEl.style.cursor = "pointer";
  rowEl.addEventListener("click", (e) => {
    // 체크박스, 버튼 클릭은 제외
    if (e.target.closest("input,button,a")) return;
    const activeType = String($("opsExceptionType")?.value || "UNSLOTTED").trim().toUpperCase();
    const idx = Number(rowEl.dataset.opsExRowIdx || -1);
    const item = Array.isArray(opsExceptionItems) ? opsExceptionItems[idx] : null;
    // 선택 하이라이트
    root.querySelectorAll(".ops-exception-row").forEach(r => r.classList.remove("is-ctx-selected"));
    rowEl.classList.add("is-ctx-selected");
    renderOpsExceptionContextPanel(item, activeType);
  });
});
```

`data-ops-ex-row-idx` 속성을 각 행에 추가:
- Master 행: `<div class="ops-exception-row..." data-ops-ex-row-idx="${escapeHtml(String(opsExceptionItems.indexOf(master)))}">`
- OwnedItem 행: `<div class="ops-exception-row..." data-ops-ex-row-idx="${escapeHtml(String(opsExceptionItems.indexOf(row)))}">` 

인덱스 계산은 `map((master, idx) => ...)` 콜백의 `idx`를 그대로 사용:
```javascript
// master 행 예시:
`<div class="ops-exception-row..." data-ops-ex-row-idx="${idx}">`
```

- [ ] **Step 3: `is-ctx-selected` CSS 추가**

```css
.ops-exception-row.is-ctx-selected {
  border-color: var(--accent, #4f8ef7);
  background: color-mix(in srgb, var(--paper) 85%, var(--accent, #4f8ef7) 15%);
}
```

- [ ] **Step 4: 커밋**

```bash
git add app/static/index.html
git commit -m "feat(exception-queue): row click → context panel with item detail"
```

---

## Task 7: JS — `opsExceptionDomain` 가시성 + 검색 필터 그리드 가시성 동기화

**Files:**
- Modify: `app/static/index.html` (함수 `syncOpsExceptionSelectionControls`)

현재 `opsExceptionDomainWrap`은 REVIEW_MISSING 일 때만 표시된다. 검색 필터 그리드(`opsExSearchGrid`)는 항상 표시하되, 도메인 필터는 master 타입에만 표시하도록 유지.

- [ ] **Step 1: `syncOpsExceptionSelectionControls` 수정**

기존:
```javascript
const domainWrap = $("opsExceptionDomainWrap");
if (domainWrap) domainWrap.style.display = activeType === "REVIEW_MISSING" ? "" : "none";
```

변경:
```javascript
const isMasterType = (activeType === "SPOTIFY_UNMATCHED" || activeType === "GENRE_MISSING"
                      || activeType === "CATALOG_MISSING" || activeType === "REVIEW_MISSING");
const domainWrap = $("opsExceptionDomainWrap");
if (domainWrap) domainWrap.style.display = isMasterType ? "" : "none";
```

- [ ] **Step 2: 컨텍스트 패널 초기화 (타입 변경 시)**

`opsExceptionType` change 이벤트 핸들러에 컨텍스트 패널 초기화 추가:

```javascript
$("opsExceptionType").addEventListener("change", () => {
  renderOpsExceptionContextPanel(null, "");
  syncOpsExceptionSelectionControls();
});
```

- [ ] **Step 3: 커밋**

```bash
git add app/static/index.html
git commit -m "feat(exception-queue): domain filter for all master types + ctx panel reset on type change"
```

---

## Task 8: 배포 및 검증

**Files:**
- `deploy/scripts/deploy_to_prod.sh` (실행)

- [ ] **Step 1: 로컬 구문 검사**

```bash
python3 -m py_compile app/main.py && echo OK
```

Expected: `OK`

- [ ] **Step 2: 상용 배포**

```bash
PROD_SSH_TARGET="__PROD_HOST__" PROD_APP_ROOT="/Users/__PROD_USER__/apps/__PROJECT_SLUG__-prod" \
  bash deploy/scripts/deploy_to_prod.sh 2>&1 | grep -E "^\[|Deploy complete|curl"
```

Expected: `Deploy complete: branch=main sha=...`

- [ ] **Step 3: 동작 확인 체크리스트**

- [ ] 예외 큐 진입 시 좌우 2열 레이아웃으로 표시됨
- [ ] 검색 필터 입력 후 불러오기 → 결과 필터링 적용됨
- [ ] Enter 키로 즉시 검색됨
- [ ] 행 클릭 시 우측 패널에 상세 표시됨
- [ ] Master 예외(REVIEW_MISSING) 행 클릭 → 마스터 카드 + 보유 상품 수 표시
- [ ] OwnedItem 예외(UNSLOTTED 등) 행 클릭 → 소유 상품 상세 표시
- [ ] "관리 화면으로" 버튼 → 미디어>관리로 이동
- [ ] 프리셋 저장 → 검색 필터 포함하여 저장됨
- [ ] 프리셋 불러오기 → 검색 필터 복원됨
- [ ] 도메인 필터: Master 예외 시 표시, OwnedItem 예외 시 숨김
- [ ] 검색 필터 초기화 버튼 동작

---

## 자가 검토

### Spec 커버리지
- ✅ 예외 큐 좌우 2열 레이아웃 (Task 1, 2)
- ✅ 검색 필터 입력 (아티스트, 상품명, 바코드, 카탈로그, 발매년) (Task 2, 3, 4)
- ✅ 필터 API 파라미터 연동 — OwnedItem, Master 모두 (Task 3, 4)
- ✅ 필터 프리셋 저장/복원 (Task 5)
- ✅ Enter 키 검색, 리셋 버튼 (Task 5)
- ✅ 우측 컨텍스트 패널 — Master/OwnedItem 양쪽 렌더링 (Task 6)
- ✅ 행 클릭 선택 하이라이트 (Task 6)
- ✅ 타입 변경 시 컨텍스트 패널 초기화 (Task 7)
- ✅ 도메인 필터 가시성 Master 전체로 확장 (Task 7)

### 타입 일관성
- `renderOpsExceptionContextPanel(row, type)` — Task 6에서 정의, Task 7에서 `(null, "")` 호출 ✅
- `buildMasterExceptionUrl(type, limit)` — Task 4 정의, `loadOpsExceptionItems`에서 사용 ✅
- `opsExArtist`, `opsExTitle`, `opsExBarcode`, `opsExCatalogNo`, `opsExReleaseYear` — Task 2 HTML, Task 3/4/5 JS 모두 동일 ID ✅
