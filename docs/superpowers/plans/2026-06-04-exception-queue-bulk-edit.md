# Exception Queue Bulk Edit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 예외 큐에 상세 검색 조건, 타입별 툴바 벌크 편집(MEDIA_MISSING·SIZE_MISMATCH), 컨텍스트 패널 개별 인라인 편집(MEDIA_MISSING·SIZE_MISMATCH·GENRE_MISSING·CATALOG_MISSING)을 추가한다.

**Architecture:** 백엔드 2건(신규 엔드포인트 1개 + 기존 스키마 확장 1개) → 프론트엔드 3단계(상세 검색 필터 → 툴바 벌크 → 컨텍스트 패널 편집). 각 태스크는 독립 커밋으로 배포 가능하다.

**Tech Stack:** FastAPI, SQLite (app/db), Pydantic v2, Vanilla JS (index.html 단일 파일)

---

## File Map

| 파일 | 변경 내용 |
|------|-----------|
| `app/schemas.py` | `OwnedItemBulkUpdateRequest.size_group` 추가, 신규 `OwnedItemBulkUpdateMusicDetailRequest/Response` |
| `app/db/owned_item_write.py` | `bulk_update_owned_items` size_group 지원, 신규 `bulk_update_music_detail` 함수 |
| `app/api/owned_items.py` | 기존 bulk-update 라우터에 size_group 흐름 추가, 신규 `POST /owned-items/bulk-update-music-detail` |
| `app/static/index.html` | 상세 검색 조건 UI + buildOpsExceptionParams 확장, 툴바 벌크 컨트롤, 컨텍스트 패널 편집 폼 |
| `tests/test_ops_route_access.py` | 신규 엔드포인트 smoke 테스트 |

---

## Task 1: 스키마 + DB — `size_group` bulk 지원

**Files:**
- Modify: `app/schemas.py` (line 298 근처 `OwnedItemBulkUpdateRequest`)
- Modify: `app/db/owned_item_write.py` (line 339 근처 `bulk_update_owned_items`)
- Test: `tests/test_ops_route_access.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_ops_route_access.py`에 추가:

```python
def test_bulk_update_supports_size_group(client_with_db):
    """bulk-update endpoint accepts size_group field."""
    # client_with_db는 기존 fixture 사용 (conftest.py 확인)
    r = client_with_db.post("/owned-items/bulk-update", json={
        "owned_item_ids": [],
        "size_group": "LP",
    })
    # 빈 ids여서 updated_count=0, 하지만 400이 아닌 200이어야 함
    assert r.status_code == 200
    assert r.json()["updated_count"] == 0
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd /Volumes/Data/Works/07.hahahoho
python -m pytest tests/test_ops_route_access.py::test_bulk_update_supports_size_group -v
```

Expected: FAIL (422 Unprocessable Entity — size_group not in schema)

- [ ] **Step 3: `OwnedItemBulkUpdateRequest`에 size_group 추가**

`app/schemas.py` line 298 근처:

```python
class OwnedItemBulkUpdateRequest(BaseModel):
    owned_item_ids: list[int] = Field(default_factory=list)
    status: ItemStatus | None = None
    release_type: ReleaseType | None = None
    is_second_hand: bool | None = None
    purchase_source: str | None = None
    append_memory_note: str | None = None
    preferred_storage_size_group: SizeGroup | None = None
    size_group: SizeGroup | None = None  # 추가
```

- [ ] **Step 4: `bulk_update_owned_items` DB 함수에 size_group 추가**

`app/db/owned_item_write.py` `bulk_update_owned_items` 함수:

함수 시그니처에 추가:
```python
def bulk_update_owned_items(
    owned_item_ids: list[int],
    *,
    status: str | None = None,
    release_type: str | None = None,
    is_second_hand: bool | None = None,
    purchase_source: str | None = None,
    append_memory_note: str | None = None,
    preferred_storage_size_group: str | None = None,
    size_group: str | None = None,  # 추가
) -> list[int]:
```

SELECT 쿼리에 `size_group` 컬럼 추가:
```sql
SELECT id, status, release_type, is_second_hand, purchase_source, memory_note,
       preferred_storage_size_group, size_group
FROM owned_item WHERE id IN ({placeholders})
```

변경 감지 및 업데이트 로직에 size_group 추가:
```python
next_size_group = size_group if size_group is not None else row.get("size_group")
```

no-op 조건에 추가:
```python
and next_size_group == row.get("size_group")
```

updates 튜플에 next_size_group 추가 (7번째 위치, updated_at 앞):
```python
updates.append((
    next_status,
    next_release_type,
    next_is_second_hand,
    next_purchase_source,
    next_memory_note,
    next_preferred_size_group,
    next_size_group,   # 추가
    now,
    owned_item_id,
))
```

executemany SQL에 `size_group = ?,` 추가:
```sql
UPDATE owned_item SET
  status = ?,
  release_type = ?,
  is_second_hand = ?,
  purchase_source = ?,
  memory_note = ?,
  preferred_storage_size_group = ?,
  size_group = ?,
  updated_at = ?
WHERE id = ?
```

- [ ] **Step 5: API 라우터에서 size_group 전달**

`app/api/owned_items.py` line 1734 근처 `bulk_update_owned_items` 호출:

```python
updated_item_ids = db.bulk_update_owned_items(
    payload.owned_item_ids,
    status=payload.status,
    release_type=payload.release_type,
    is_second_hand=payload.is_second_hand,
    purchase_source=payload.purchase_source,
    append_memory_note=payload.append_memory_note,
    preferred_storage_size_group=payload.preferred_storage_size_group,
    size_group=payload.size_group,  # 추가
)
```

- [ ] **Step 6: 테스트 통과 확인**

```bash
python -m pytest tests/test_ops_route_access.py::test_bulk_update_supports_size_group -v
```

Expected: PASS

- [ ] **Step 7: 구문 검사**

```bash
python3 -m py_compile app/schemas.py app/db/owned_item_write.py app/api/owned_items.py && echo OK
```

Expected: `OK`

- [ ] **Step 8: 커밋**

```bash
git add app/schemas.py app/db/owned_item_write.py app/api/owned_items.py tests/test_ops_route_access.py
git commit -m "feat(exception-queue): bulk-update supports size_group field"
```

---

## Task 2: 신규 엔드포인트 — `POST /owned-items/bulk-update-music-detail`

**Files:**
- Modify: `app/schemas.py` (신규 스키마 클래스 추가)
- Modify: `app/db/owned_item_write.py` (신규 `bulk_update_music_detail` 함수)
- Modify: `app/api/owned_items.py` (신규 라우터)
- Test: `tests/test_ops_route_access.py`

미디어 타입만 업데이트한다. size_group은 건드리지 않는다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_ops_route_access.py`에 추가:

```python
def test_bulk_update_music_detail_media_type(client_with_db):
    """POST /owned-items/bulk-update-music-detail updates media_type only."""
    r = client_with_db.post("/owned-items/bulk-update-music-detail", json={
        "owned_item_ids": [],
        "media_type": "Vinyl",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["requested_count"] == 0
    assert data["updated_count"] == 0
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python -m pytest tests/test_ops_route_access.py::test_bulk_update_music_detail_media_type -v
```

Expected: FAIL (404 — endpoint not found)

- [ ] **Step 3: 스키마 추가**

`app/schemas.py`에 `OwnedItemBulkUpdateRequest` 아래 추가:

```python
class OwnedItemBulkUpdateMusicDetailRequest(BaseModel):
    owned_item_ids: list[int] = Field(default_factory=list)
    media_type: str | None = None


class OwnedItemBulkUpdateMusicDetailResponse(BaseModel):
    requested_count: int
    updated_count: int
    updated_item_ids: list[int] = Field(default_factory=list)
```

- [ ] **Step 4: DB 함수 추가**

`app/db/owned_item_write.py`에 `bulk_update_owned_items` 다음에 추가:

```python
def bulk_update_music_detail(
    owned_item_ids: list[int],
    *,
    media_type: str | None = None,
) -> list[int]:
    """Update music_item_detail fields (currently: media_type) for multiple items.

    size_group on owned_item is intentionally NOT touched — mismatches are
    handled separately via the SIZE_MISMATCH exception queue.
    """
    ids = sorted({int(v) for v in owned_item_ids if int(v) > 0})
    if not ids or media_type is None:
        return []

    now = utc_now_iso()
    updated_ids: list[int] = []

    with get_write_conn() as conn:
        placeholders = ",".join("?" for _ in ids)
        existing = {
            int(row["owned_item_id"]): dict(row)
            for row in conn.execute(
                f"SELECT owned_item_id, media_type FROM music_item_detail WHERE owned_item_id IN ({placeholders})",
                ids,
            ).fetchall()
        }
        for oid in ids:
            row = existing.get(oid)
            if row is not None:
                if row.get("media_type") == media_type:
                    continue  # no-op
                conn.execute(
                    "UPDATE music_item_detail SET media_type = ?, updated_at = ? WHERE owned_item_id = ?",
                    (media_type, now, oid),
                )
            else:
                # music_item_detail row doesn't exist yet — create minimal row
                conn.execute(
                    """INSERT INTO music_item_detail (owned_item_id, media_type, created_at, updated_at)
                       VALUES (?, ?, ?, ?)""",
                    (oid, media_type, now, now),
                )
            updated_ids.append(oid)

    return updated_ids
```

- [ ] **Step 5: `__init__.py`에 새 함수 export 확인**

```bash
grep -n "bulk_update_owned_items\|bulk_update_music" app/db/__init__.py | head -5
```

`bulk_update_owned_items`가 export되어 있는 패턴 확인 후 `bulk_update_music_detail`도 동일하게 추가.

- [ ] **Step 6: API 라우터 추가**

`app/api/owned_items.py`에서 기존 `POST /owned-items/bulk-update` 라우터 바로 다음에 추가:

```python
@router.post(
    "/owned-items/bulk-update-music-detail",
    response_model=OwnedItemBulkUpdateMusicDetailResponse,
)
def bulk_update_music_detail(
    payload: OwnedItemBulkUpdateMusicDetailRequest,
    request: Request,
) -> OwnedItemBulkUpdateMusicDetailResponse:
    """Update music_item_detail.media_type for multiple owned items. ADMIN only."""
    from ..security import _require_admin_request
    _require_admin_request(request)
    updated_item_ids = db.bulk_update_music_detail(
        payload.owned_item_ids,
        media_type=payload.media_type,
    )
    return OwnedItemBulkUpdateMusicDetailResponse(
        requested_count=len(payload.owned_item_ids),
        updated_count=len(updated_item_ids),
        updated_item_ids=updated_item_ids,
    )
```

import 확인: `OwnedItemBulkUpdateMusicDetailRequest`, `OwnedItemBulkUpdateMusicDetailResponse`가 `app/schemas.py`에서 import되고 있어야 함 (기존 import 블록 확인 후 추가).

- [ ] **Step 7: 테스트 통과 확인**

```bash
python -m pytest tests/test_ops_route_access.py::test_bulk_update_music_detail_media_type -v
```

Expected: PASS

- [ ] **Step 8: 구문 검사**

```bash
python3 -m py_compile app/schemas.py app/db/owned_item_write.py app/api/owned_items.py && echo OK
```

Expected: `OK`

- [ ] **Step 9: 커밋**

```bash
git add app/schemas.py app/db/owned_item_write.py app/db/__init__.py app/api/owned_items.py tests/test_ops_route_access.py
git commit -m "feat(exception-queue): POST /owned-items/bulk-update-music-detail (media_type only)"
```

---

## Task 3: UI — 예외 큐 상세 검색 조건 (Advanced Filters)

**Files:**
- Modify: `app/static/index.html`

`opsExSearchGrid` 바로 아래에 `<details>` 접기/펼치기로 상세 검색 조건 추가. 패키징·패키지 구성은 미디어>검색과 동일한 데이터로 동적 초기화.

- [ ] **Step 1: HTML 추가**

`opsExSearchGrid` 닫는 `</div>` 바로 다음에 삽입:

```html
<details id="opsExAdvancedDetails" class="ops-compact-extra-fields u-mt-6">
  <summary>상세 검색 조건</summary>
  <div class="ops-compact-extra-fields-body home-search-advanced-grid">
    <div class="checkbox-group-container">
      <label class="checkbox-group-title">패키징</label>
      <div id="opsExPackagingList" class="checkbox-group-scroll"></div>
    </div>
    <div class="checkbox-group-container">
      <label class="checkbox-group-title">패키지 구성</label>
      <div id="opsExPackageContentsList" class="checkbox-group-scroll"></div>
    </div>
    <div class="checkbox-group-sub">
      <label>싸인 여부</label>
      <div style="display:flex;gap:12px;align-items:center;min-height:38px;">
        <label class="inline-check"><input id="opsExSigDirect" type="checkbox" /><span>직접</span></label>
        <label class="inline-check"><input id="opsExSigPurchase" type="checkbox" /><span>구매</span></label>
      </div>
    </div>
    <div class="checkbox-group-sub">
      <label>기타 조건</label>
      <div style="display:flex;gap:12px;align-items:center;min-height:38px;">
        <label class="inline-check"><input id="opsExNewProduct" type="checkbox" /><span>새상품</span></label>
        <label class="inline-check"><input id="opsExPromo" type="checkbox" /><span>홍보반</span></label>
        <label class="inline-check"><input id="opsExLimitEd" type="checkbox" /><span>한정반</span></label>
      </div>
    </div>
  </div>
</details>
```

- [ ] **Step 2: 패키징·패키지 구성 동적 초기화**

기존에 `homePackagingList`와 `homePackageContentsList`를 초기화하는 코드 블록(line ~46976) 바로 다음에 추가. `PACKAGING_OPTIONS_BY_MEDIA`와 allContents를 재사용:

```javascript
// ── 예외 큐 상세 검색 조건 초기화 ──
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
```

- [ ] **Step 3: `buildOpsExceptionParams` 확장**

기존 검색 필터 추가 블록(`if (artist)...`) 다음에 추가:

```javascript
// 상세 검색 조건 (OwnedItem 예외 타입에만 적용)
const opsExPkgVals = [];
$("opsExPackagingList")?.querySelectorAll("input:checked").forEach(cb => opsExPkgVals.push(cb.value));
const opsExContentsVals = [];
$("opsExPackageContentsList")?.querySelectorAll("input:checked").forEach(cb => opsExContentsVals.push(cb.value));
opsExPkgVals.forEach(v => params.append("packaging", v));
opsExContentsVals.forEach(v => params.append("package_contents", v));
if ($("opsExSigDirect")?.checked) params.append("signature_types", "IN_PERSON");
if ($("opsExSigPurchase")?.checked) params.append("signature_types", "PURCHASE_INCLUDED");
if ($("opsExNewProduct")?.checked) params.set("is_new", "true");
if ($("opsExPromo")?.checked) params.set("is_promo", "true");
if ($("opsExLimitEd")?.checked) params.set("is_limited", "true");
```

- [ ] **Step 4: 프리셋 저장/복원 확장**

`currentOpsExceptionPresetPayload()` 함수에 추가:

```javascript
// 상세 검색 조건 직렬화
const opsExPkgChecked = [];
$("opsExPackagingList")?.querySelectorAll("input:checked").forEach(cb => opsExPkgChecked.push(cb.value));
const opsExContentsChecked = [];
$("opsExPackageContentsList")?.querySelectorAll("input:checked").forEach(cb => opsExContentsChecked.push(cb.value));
// payload 객체에 추가:
packaging: opsExPkgChecked,
packageContents: opsExContentsChecked,
sigDirect: Boolean($("opsExSigDirect")?.checked),
sigPurchase: Boolean($("opsExSigPurchase")?.checked),
isNew: Boolean($("opsExNewProduct")?.checked),
isPromo: Boolean($("opsExPromo")?.checked),
isLimited: Boolean($("opsExLimitEd")?.checked),
```

`applyOpsExceptionPresetByIndex` 함수에 복원 코드 추가:

```javascript
// 상세 검색 조건 복원
const pkgValues = new Set(Array.isArray(preset.packaging) ? preset.packaging : []);
$("opsExPackagingList")?.querySelectorAll("input").forEach(cb => {
  cb.checked = pkgValues.has(cb.value);
});
const contentsValues = new Set(Array.isArray(preset.packageContents) ? preset.packageContents : []);
$("opsExPackageContentsList")?.querySelectorAll("input").forEach(cb => {
  cb.checked = contentsValues.has(cb.value);
});
if ($("opsExSigDirect")) $("opsExSigDirect").checked = Boolean(preset.sigDirect);
if ($("opsExSigPurchase")) $("opsExSigPurchase").checked = Boolean(preset.sigPurchase);
if ($("opsExNewProduct")) $("opsExNewProduct").checked = Boolean(preset.isNew);
if ($("opsExPromo")) $("opsExPromo").checked = Boolean(preset.isPromo);
if ($("opsExLimitEd")) $("opsExLimitEd").checked = Boolean(preset.isLimited);
```

- [ ] **Step 5: 리셋 버튼 확장**

`opsExSearchResetBtn` 클릭 핸들러에 상세 조건 초기화 추가:

```javascript
// 기존 텍스트 필드 초기화 다음에 추가:
$("opsExPackagingList")?.querySelectorAll("input").forEach(cb => cb.checked = false);
$("opsExPackageContentsList")?.querySelectorAll("input").forEach(cb => cb.checked = false);
["opsExSigDirect","opsExSigPurchase","opsExNewProduct","opsExPromo","opsExLimitEd"].forEach(id => {
  const el = $(id); if (el) el.checked = false;
});
```

- [ ] **Step 6: 커밋**

```bash
git add app/static/index.html
git commit -m "feat(exception-queue): advanced search filters (packaging, sig, new/promo/limited)"
```

---

## Task 4: UI — 툴바 벌크 컨트롤 (MEDIA_MISSING · SIZE_MISMATCH)

**Files:**
- Modify: `app/static/index.html`

선택 항목이 있고 타입이 MEDIA_MISSING 또는 SIZE_MISMATCH일 때, 기존 벌크 버튼 행 아래에 타입별 입력 행을 표시한다.

- [ ] **Step 1: HTML 추가**

기존 `<div class="dashboard-selection-toolbar ...">` 안의 `dashboard-selection-actions` div 닫는 태그 바로 다음에 추가:

```html
<div id="opsExBulkEditRow" style="display:none;margin-top:8px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
</div>
<div id="opsExBulkEditStatus" class="status mini" style="margin-top:4px;"></div>
```

- [ ] **Step 2: `renderOpsExBulkEditRow` 함수 추가**

`syncOpsExceptionSelectionControls` 함수 바로 위에:

```javascript
function renderOpsExBulkEditRow(type, selectedCount) {
  const row = $("opsExBulkEditRow");
  if (!row) return;
  if (type === "MEDIA_MISSING") {
    row.innerHTML = `
      <label style="font-size:0.78rem;white-space:nowrap;">미디어 타입</label>
      <select id="opsExBulkMediaType" style="font-size:0.78rem;">
        <option value="">선택</option>
        <option value="Vinyl">Vinyl (LP)</option>
        <option value="CD">CD</option>
        <option value="Cassette">Cassette</option>
        <option value='7"'>7"</option>
        <option value='10"'>10"</option>
        <option value="DVD">DVD</option>
        <option value="Blu-ray">Blu-ray</option>
        <option value="8-Track Cartridge">8-Track</option>
        <option value="SACD">SACD</option>
        <option value="CDr">CDr</option>
        <option value="Reel-To-Reel">Reel-To-Reel</option>
      </select>
      <button id="opsExBulkApplyBtn" class="btn ghost tiny" type="button" disabled>
        선택 ${selectedCount}건 일괄 적용
      </button>
    `;
    $("opsExBulkMediaType")?.addEventListener("change", () => {
      if ($("opsExBulkApplyBtn")) $("opsExBulkApplyBtn").disabled = !$("opsExBulkMediaType").value;
    });
  } else if (type === "SIZE_MISMATCH") {
    row.innerHTML = `
      <label style="font-size:0.78rem;white-space:nowrap;">규격 그룹</label>
      <select id="opsExBulkSizeGroup" style="font-size:0.78rem;">
        <option value="">선택</option>
        <option value="LP">LP</option>
        <option value="STD">STD (CD)</option>
        <option value="LP7">LP 7"</option>
        <option value="LP10">LP 10"</option>
        <option value="CASSETTE">Cassette</option>
        <option value="8TRACK">8-Track</option>
        <option value="REEL_TO_REEL">Reel-to-Reel</option>
        <option value="BOOK">Book</option>
        <option value="OVERSIZE">Oversize</option>
      </select>
      <button id="opsExBulkApplyBtn" class="btn ghost tiny" type="button" disabled>
        선택 ${selectedCount}건 일괄 적용
      </button>
    `;
    $("opsExBulkSizeGroup")?.addEventListener("change", () => {
      if ($("opsExBulkApplyBtn")) $("opsExBulkApplyBtn").disabled = !$("opsExBulkSizeGroup").value;
    });
  }
  $("opsExBulkApplyBtn")?.addEventListener("click", () => applyOpsExBulk(type));
}
```

- [ ] **Step 3: `applyOpsExBulk` 함수 추가**

`renderOpsExBulkEditRow` 다음에:

```javascript
async function applyOpsExBulk(type) {
  const btn = $("opsExBulkApplyBtn");
  const statusEl = $("opsExBulkEditStatus");
  const selectedIds = Array.from(opsExceptionSelectedIds);
  if (!selectedIds.length) return;

  if (btn) btn.disabled = true;
  if (statusEl) statusEl.textContent = `적용 중... (0/${selectedIds.length})`;

  try {
    let res;
    if (type === "MEDIA_MISSING") {
      const mediaType = $("opsExBulkMediaType")?.value;
      if (!mediaType) return;
      res = await fetchWithRetry("/owned-items/bulk-update-music-detail", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ owned_item_ids: selectedIds, media_type: mediaType }),
      });
    } else if (type === "SIZE_MISMATCH") {
      const sizeGroup = $("opsExBulkSizeGroup")?.value;
      if (!sizeGroup) return;
      res = await fetchWithRetry("/owned-items/bulk-update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ owned_item_ids: selectedIds, size_group: sizeGroup }),
      });
    } else {
      return;
    }

    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.detail || "적용 실패");
    const okCount = Number(data.updated_count || 0);
    const failCount = selectedIds.length - okCount;
    if (statusEl) statusEl.textContent = `완료 — 성공: ${okCount}건 / 실패: ${failCount}건`;
    // 성공 항목 선택 해제
    (data.updated_item_ids || []).forEach(id => opsExceptionSelectedIds.delete(Number(id)));
    // 목록 갱신
    setTimeout(() => loadOpsExceptionItems({ silent: true }), 1500);
  } catch (err) {
    if (statusEl) statusEl.textContent = `오류: ${escapeHtml(String(err.message || err))}`;
  } finally {
    if (btn) btn.disabled = false;
  }
}
```

- [ ] **Step 4: `syncOpsExceptionSelectionControls`에 벌크 편집 행 표시 로직 추가**

기존 `reviewBtn` 표시 로직 다음에:

```javascript
const BULK_EDIT_TYPES = new Set(["MEDIA_MISSING", "SIZE_MISMATCH"]);
const showBulkEdit = BULK_EDIT_TYPES.has(activeType) && selectedCount > 0;
const bulkEditRow = $("opsExBulkEditRow");
if (bulkEditRow) {
  bulkEditRow.style.display = showBulkEdit ? "flex" : "none";
  if (showBulkEdit) renderOpsExBulkEditRow(activeType, selectedCount);
}
if (!showBulkEdit && $("opsExBulkEditStatus")) $("opsExBulkEditStatus").textContent = "";
```

- [ ] **Step 5: 커밋**

```bash
git add app/static/index.html
git commit -m "feat(exception-queue): toolbar bulk controls for MEDIA_MISSING and SIZE_MISMATCH"
```

---

## Task 5: UI — 컨텍스트 패널 개별 인라인 편집

**Files:**
- Modify: `app/static/index.html` (`renderOpsExceptionContextPanel` 함수)

행 클릭 시 컨텍스트 패널에 타입별 편집 폼을 추가. 저장 성공 시 해당 행을 목록에서 제거.

- [ ] **Step 1: `renderOpsExceptionContextPanel` OwnedItem 분기에 편집 폼 추가**

기존 OwnedItem 분기(else 브랜치)에서 `body.innerHTML` 설정 코드를 찾는다.
현재 "관리 화면으로" 버튼 다음에 타입별 편집 폼을 추가:

```javascript
// body.innerHTML 내부 버튼 div 다음에 추가:
const editFormHtml = _opsExCtxEditFormHtml(type, data);
if (editFormHtml) {
  body.innerHTML += `<div id="opsExCtxEditSection" style="margin-top:12px;border-top:1px solid var(--line);padding-top:10px;">${editFormHtml}</div>`;
  _bindOpsExCtxEditForm(type, ownedItemId, data);
}
```

- [ ] **Step 2: `_opsExCtxEditFormHtml` 함수 추가**

`renderOpsExceptionContextPanel` 바로 위에:

```javascript
function _opsExCtxEditFormHtml(type, data) {
  if (type === "MEDIA_MISSING") {
    const cur = data.music_detail?.media_type || "";
    const opts = [
      "Vinyl","CD","Cassette",'7"','10"',"DVD","Blu-ray",
      "8-Track Cartridge","SACD","CDr","Reel-To-Reel",
    ].map(v => `<option value="${escapeHtml(v)}"${cur===v?" selected":""}>${escapeHtml(v)}</option>`).join("");
    return `
      <div style="display:flex;flex-direction:column;gap:6px;">
        <label style="font-size:0.72rem;color:var(--muted);">미디어 타입</label>
        <div style="display:flex;gap:6px;align-items:center;">
          <select id="opsExCtxMediaType" style="flex:1;font-size:0.78rem;">
            <option value="">선택</option>${opts}
          </select>
          <button id="opsExCtxSaveBtn" class="btn ghost tiny" type="button">저장</button>
        </div>
        <div id="opsExCtxEditStatus" class="status mini"></div>
      </div>`;
  }
  if (type === "SIZE_MISMATCH") {
    const cur = data.size_group || "";
    const opts = [
      ["LP","LP"],["STD","STD (CD)"],["LP7",'LP 7"'],["LP10",'LP 10"'],
      ["CASSETTE","Cassette"],["8TRACK","8-Track"],["REEL_TO_REEL","Reel-to-Reel"],
      ["BOOK","Book"],["OVERSIZE","Oversize"],
    ].map(([v,l]) => `<option value="${v}"${cur===v?" selected":""}>${escapeHtml(l)}</option>`).join("");
    return `
      <div style="display:flex;flex-direction:column;gap:6px;">
        <label style="font-size:0.72rem;color:var(--muted);">규격 그룹</label>
        <div style="display:flex;gap:6px;align-items:center;">
          <select id="opsExCtxSizeGroup" style="flex:1;font-size:0.78rem;">
            <option value="">선택</option>${opts}
          </select>
          <button id="opsExCtxSaveBtn" class="btn ghost tiny" type="button">저장</button>
        </div>
        <div id="opsExCtxEditStatus" class="status mini"></div>
      </div>`;
  }
  if (type === "CATALOG_MISSING") {
    const catalogNo = escapeHtml(data.music_detail?.catalog_no || "");
    const labelName = escapeHtml(data.music_detail?.label_name || "");
    return `
      <div style="display:flex;flex-direction:column;gap:6px;">
        <label style="font-size:0.72rem;color:var(--muted);">카탈로그 번호</label>
        <input id="opsExCtxCatalogNo" type="text" value="${catalogNo}" style="font-size:0.78rem;" />
        <label style="font-size:0.72rem;color:var(--muted);">레이블</label>
        <input id="opsExCtxLabelName" type="text" value="${labelName}" style="font-size:0.78rem;" />
        <div style="display:flex;gap:6px;">
          <button id="opsExCtxSaveBtn" class="btn ghost tiny" type="button">저장</button>
        </div>
        <div id="opsExCtxEditStatus" class="status mini"></div>
      </div>`;
  }
  return "";
}
```

- [ ] **Step 3: `_bindOpsExCtxEditForm` 함수 추가**

`_opsExCtxEditFormHtml` 다음에:

```javascript
function _bindOpsExCtxEditForm(type, ownedItemId, data) {
  const saveBtn = $("opsExCtxSaveBtn");
  const statusEl = $("opsExCtxEditStatus");
  if (!saveBtn) return;

  saveBtn.addEventListener("click", async () => {
    saveBtn.disabled = true;
    if (statusEl) statusEl.textContent = "저장 중...";
    try {
      let body;
      if (type === "MEDIA_MISSING") {
        const v = $("opsExCtxMediaType")?.value;
        if (!v) throw new Error("미디어 타입을 선택하세요");
        body = { music_detail: { media_type: v } };
      } else if (type === "SIZE_MISMATCH") {
        const v = $("opsExCtxSizeGroup")?.value;
        if (!v) throw new Error("규격 그룹을 선택하세요");
        body = { size_group: v };
      } else if (type === "CATALOG_MISSING") {
        const catalogNo = String($("opsExCtxCatalogNo")?.value || "").trim();
        const labelName = String($("opsExCtxLabelName")?.value || "").trim();
        if (!catalogNo && !labelName) throw new Error("카탈로그 번호 또는 레이블을 입력하세요");
        body = { music_detail: { catalog_no: catalogNo || null, label_name: labelName || null } };
      } else {
        return;
      }
      const res = await fetchWithRetry(`/owned-items/${ownedItemId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const resp = await safeJson(res);
      if (!res.ok) throw new Error(resp.detail || "저장 실패");
      if (statusEl) statusEl.textContent = "저장됨";
      // 해당 행 목록에서 제거 (예외 해소)
      opsExceptionItems = opsExceptionItems.filter(r => Number(r.id) !== Number(ownedItemId));
      opsExceptionSelectedIds.delete(Number(ownedItemId));
      opsExceptionTotalCount = Math.max(0, opsExceptionTotalCount - 1);
      if (opsExceptionCounts[type] !== undefined) opsExceptionCounts[type] = Math.max(0, opsExceptionCounts[type] - 1);
      renderOpsExceptionSummary();
      renderOpsExceptionList();
      // 컨텍스트 패널 초기화
      renderOpsExceptionContextPanel(null, "");
    } catch (err) {
      if (statusEl) statusEl.textContent = `오류: ${escapeHtml(String(err.message || err))}`;
    } finally {
      saveBtn.disabled = false;
    }
  });
}
```

- [ ] **Step 4: GENRE_MISSING 컨텍스트 패널 편집 추가**

`renderOpsExceptionContextPanel`의 Master 분기(isMasterType 블록) body.innerHTML 생성 코드를 찾는다.
현재 "Wikipedia 자동수집" 버튼 다음에 genres 편집 폼 추가:

```javascript
// body.innerHTML 내 actions div 다음에 추가
if (type === "GENRE_MISSING") {
  const genresVal = escapeHtml((row.genres || []).join(", "));
  const stylesVal = escapeHtml((row.styles || []).join(", "));
  body.innerHTML += `
    <div style="margin-top:12px;border-top:1px solid var(--line);padding-top:10px;">
      <label style="font-size:0.72rem;color:var(--muted);">장르 (쉼표 구분)</label>
      <input id="opsExCtxGenres" type="text" value="${genresVal}" style="width:100%;font-size:0.78rem;margin-top:4px;" />
      <label style="font-size:0.72rem;color:var(--muted);margin-top:6px;display:block;">스타일 (쉼표 구분)</label>
      <input id="opsExCtxStyles" type="text" value="${stylesVal}" style="width:100%;font-size:0.78rem;margin-top:4px;" />
      <div style="display:flex;gap:6px;margin-top:8px;">
        <button id="opsExCtxGenreSaveBtn" class="btn ghost tiny" type="button">저장</button>
      </div>
      <div id="opsExCtxGenreStatus" class="status mini"></div>
    </div>`;
  // bind
  $("opsExCtxGenreSaveBtn")?.addEventListener("click", async () => {
    const btn = $("opsExCtxGenreSaveBtn");
    const statusEl = $("opsExCtxGenreStatus");
    if (btn) btn.disabled = true;
    if (statusEl) statusEl.textContent = "저장 중...";
    try {
      const genres = String($("opsExCtxGenres")?.value || "").split(",").map(s => s.trim()).filter(Boolean);
      const styles = String($("opsExCtxStyles")?.value || "").split(",").map(s => s.trim()).filter(Boolean);
      const res = await fetchWithRetry(`/album-masters/${masterId}/correction`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ genres, styles }),
      });
      const resp = await safeJson(res);
      if (!res.ok) throw new Error(resp.detail || "저장 실패");
      if (statusEl) statusEl.textContent = "저장됨";
      opsExceptionItems = opsExceptionItems.filter(r => Number(r.id) !== Number(masterId));
      opsExceptionSelectedIds.delete(Number(masterId));
      opsExceptionTotalCount = Math.max(0, opsExceptionTotalCount - 1);
      if (opsExceptionCounts["GENRE_MISSING"] !== undefined) opsExceptionCounts["GENRE_MISSING"] = Math.max(0, opsExceptionCounts["GENRE_MISSING"] - 1);
      renderOpsExceptionSummary();
      renderOpsExceptionList();
      renderOpsExceptionContextPanel(null, "");
    } catch (err) {
      if (statusEl) statusEl.textContent = `오류: ${escapeHtml(String(err.message || err))}`;
    } finally {
      if (btn) btn.disabled = false;
    }
  });
}
```

- [ ] **Step 5: 커밋**

```bash
git add app/static/index.html
git commit -m "feat(exception-queue): context panel inline edit for MEDIA/SIZE/GENRE/CATALOG"
```

---

## Task 6: 기존 벌크 액션 결과 피드백 개선

**Files:**
- Modify: `app/static/index.html`

기존 벌크 버튼(소스 보강, 마스터 정리, 실물 기준 맞춤)에 완료 결과 수를 표시한다.

- [ ] **Step 1: `bulkSendExceptionsToSourceWorkbench` 완료 메시지**

해당 함수 마지막에 카운트 표시:

```javascript
// 기존 함수 안에서 전송 후:
const statusEl = $("opsExceptionStatus");
if (statusEl) statusEl.textContent = `${sentCount}건이 소스 보강 대상으로 이동됐습니다`;
```

- [ ] **Step 2: `bulkAlignPreferredStorageFromExceptions` 완료 메시지**

API 응답 후:

```javascript
const statusEl = $("opsExceptionStatus");
if (statusEl) {
  const okCount = Number(data.updated_count || 0);
  statusEl.textContent = `실물 기준 맞춤 완료 — ${okCount}건 변경됨`;
}
```

- [ ] **Step 3: `bulkSendExceptionsToMasterWorkbench` 완료 메시지**

```javascript
const statusEl = $("opsExceptionStatus");
if (statusEl) statusEl.textContent = `${sentCount}건이 마스터 정리 대상으로 이동됐습니다`;
```

- [ ] **Step 4: 커밋**

```bash
git add app/static/index.html
git commit -m "feat(exception-queue): result feedback on existing bulk actions"
```

---

## Task 7: 배포 및 검증

- [ ] **Step 1: 구문 및 테스트**

```bash
cd /Volumes/Data/Works/07.hahahoho
python3 -m py_compile app/schemas.py app/api/owned_items.py app/db/owned_item_write.py && echo OK
python -m pytest tests/ --ignore=test_cloudflare.py --ignore=test_login.py -k "not shell_bootstrap" --tb=short -q 2>&1 | tail -10
```

Expected: `OK` + 기존 실패 수 유지 (새 실패 없음)

- [ ] **Step 2: 배포**

```bash
PROD_SSH_TARGET="__PROD_HOST__" PROD_APP_ROOT="/Users/__PROD_USER__/apps/__PROJECT_SLUG__-prod" \
  bash deploy/scripts/deploy_to_prod.sh 2>&1 | grep -E "^\[|Deploy complete|curl"
```

- [ ] **Step 3: 동작 검증 체크리스트**

- [ ] 예외 큐 → [상세 검색 조건] 펼치면 패키징/구성/싸인/새상품 필터 표시
- [ ] 상세 필터 체크 → 목록 자동 갱신
- [ ] 프리셋 저장 → 상세 조건 포함 저장
- [ ] MEDIA_MISSING 탭 → 항목 선택 → 툴바에 미디어 타입 select + 일괄 적용 버튼 표시
- [ ] 미디어 타입 선택 후 일괄 적용 → 성공/실패 건수 표시 + 목록 갱신
- [ ] SIZE_MISMATCH 탭 → 규격 그룹 select + 일괄 적용
- [ ] MEDIA_MISSING 행 클릭 → 우측 패널에 미디어 타입 select + 저장 폼
- [ ] 저장 성공 → 해당 행 목록에서 제거 + 카운트 감소
- [ ] GENRE_MISSING 행 클릭 → 장르/스타일 input + 저장
- [ ] CATALOG_MISSING 행 클릭 → 카탈로그번호/레이블 input + 저장

---

## 자가 검토

### Spec 커버리지
- ✅ 상세 검색 조건 (Task 3)
- ✅ MEDIA_MISSING 툴바 벌크 (Task 4)
- ✅ SIZE_MISMATCH 툴바 벌크 (Task 4)
- ✅ GENRE_MISSING 개별 편집 (Task 5)
- ✅ CATALOG_MISSING 개별 편집 (Task 5)
- ✅ MEDIA_MISSING 개별 편집 (Task 5)
- ✅ SIZE_MISMATCH 개별 편집 (Task 5)
- ✅ 기존 벌크 피드백 (Task 6)
- ✅ 신규 API bulk-update-music-detail (Task 2)
- ✅ size_group bulk-update 지원 (Task 1)

### 타입 일관성
- `opsExBulkApplyBtn` — Task 4 정의, `applyOpsExBulk`에서 참조 ✅
- `opsExCtxSaveBtn` — `_opsExCtxEditFormHtml`에서 생성, `_bindOpsExCtxEditForm`에서 바인딩 ✅
- `bulk_update_music_detail` — Task 2 DB 함수, Task 2 API에서 `db.bulk_update_music_detail` 호출 ✅
- `OwnedItemBulkUpdateMusicDetailRequest/Response` — Task 2 스키마 정의, Task 2 라우터에서 사용 ✅
