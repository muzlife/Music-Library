# Exception Queue Bulk Edit & Advanced Search Design

**Goal:** 예외 큐에 타입별 맞춤 벌크 편집과 개별 인라인 편집 기능을 추가하고, 미디어>검색의 상세 검색 조건을 예외 큐에도 반영한다.

**Architecture:** 툴바(벌크) + 컨텍스트 패널(개별) 분리. 백엔드는 신규 엔드포인트 2개 + 기존 bulk-update 스키마 확장 1건.

---

## 1. 상세 검색 조건 (Advanced Filters)

### 위치
`opsExSearchGrid` 바로 아래, `<details id="opsExAdvancedDetails" class="ops-compact-extra-fields">` 접기/펼치기.

### 포함 필드 (예외 큐 전용 ID)

| 필드 | ID | API 파라미터 |
|------|-----|-------------|
| 패키징 체크박스 목록 | `opsExPackagingList` | `packaging` (multi) |
| 패키지 구성 체크박스 목록 | `opsExPackageContentsList` | `package_contents` (multi) |
| 싸인: 직접 | `opsExSigDirect` | `signature_types=IN_PERSON` |
| 싸인: 구매 | `opsExSigPurchase` | `signature_types=PURCHASE_INCLUDED` |
| 새상품 | `opsExNewProduct` | `is_new=true` |
| 홍보반 | `opsExPromo` | `is_promo=true` |
| 한정반 | `opsExLimitEd` | `is_limited=true` |

미디어>검색의 `homePackagingList`와 같은 데이터 소스로 동적 초기화. 별도 DOM이므로 독립적으로 동작.

### `buildOpsExceptionParams` 확장
OwnedItem 예외 타입에서만 읽음 (Master 타입은 `/album-masters` 엔드포인트라 파라미터 무관):
```javascript
packagingVals.forEach(v => params.append("packaging", v));
packageContentsVals.forEach(v => params.append("package_contents", v));
if ($("opsExSigDirect").checked) params.append("signature_types", "IN_PERSON");
if ($("opsExSigPurchase").checked) params.append("signature_types", "PURCHASE_INCLUDED");
if ($("opsExNewProduct").checked) params.set("is_new", "true");
if ($("opsExPromo").checked) params.set("is_promo", "true");
if ($("opsExLimitEd").checked) params.set("is_limited", "true");
```

### 프리셋 직렬화 확장
`currentOpsExceptionPresetPayload()`에 상세 조건 직렬화 추가:
- `packaging: [...]`, `packageContents: [...]`, `sigDirect`, `sigPurchase`, `isNew`, `isPromo`, `isLimited`

---

## 2. 툴바 벌크 컨트롤

### 위치
기존 벌크 버튼 행(`dashboard-selection-actions`) 바로 아래에 타입별 컨트롤 행 추가:
```html
<div id="opsExBulkEditRow" style="display:none;">
  <!-- 타입별로 내용 교체 -->
</div>
<div id="opsExBulkEditStatus" class="status mini"></div>
```

### MEDIA_MISSING 컨트롤
```html
<label>미디어 타입</label>
<select id="opsExBulkMediaType">
  <option value="">선택</option>
  <option value="Vinyl">Vinyl (LP)</option>
  <option value="CD">CD</option>
  <option value="Cassette">Cassette</option>
  <option value="7&quot;">7"</option>
  <option value="10&quot;">10"</option>
  <option value="DVD">DVD</option>
  <option value="Blu-ray">Blu-ray</option>
  ...
</select>
<button id="opsExBulkApplyBtn">선택 N건 일괄 적용</button>
```
→ `POST /owned-items/bulk-update-music-detail`

### SIZE_MISMATCH 컨트롤
```html
<label>규격 그룹</label>
<select id="opsExBulkSizeGroup">
  <option value="LP">LP</option>
  <option value="STD">STD (CD)</option>
  <option value="LP7">LP 7"</option>
  <option value="LP10">LP 10"</option>
  <option value="CASSETTE">Cassette</option>
  ...
</select>
<button id="opsExBulkApplyBtn">선택 N건 일괄 적용</button>
```
→ 기존 `POST /owned-items/bulk-update` (`size_group` 필드 추가)

### GENRE_MISSING 컨트롤
```html
<label>장르</label>
<input id="opsExBulkGenres" placeholder="예: Rock, Pop" />
<label>스타일</label>
<input id="opsExBulkStyles" placeholder="예: Indie Rock" />
<button id="opsExBulkApplyBtn">선택 N건 일괄 적용</button>
```
→ `POST /album-masters/bulk-update-genres`

### 동작 원칙
- 선택 0건: 버튼 비활성화
- 적용 중: 버튼 disabled + 진행 상태 표시 (`적용 중... N/M`)
- 완료: `완료 — 성공: N건 / 실패: F건` 표시 후 3초 뒤 목록 자동 갱신
- 성공 항목은 `opsExceptionSelectedIds`에서 제거

### `syncOpsExceptionSelectionControls` 확장
```javascript
const BULK_EDIT_TYPES = new Set(["MEDIA_MISSING", "SIZE_MISMATCH", "GENRE_MISSING"]);
const showBulkEdit = BULK_EDIT_TYPES.has(activeType) && selectedCount > 0;
const bulkEditRow = $("opsExBulkEditRow");
if (bulkEditRow) {
  bulkEditRow.style.display = showBulkEdit ? "" : "none";
  if (showBulkEdit) renderOpsExBulkEditRow(activeType, selectedCount);
}
```

`renderOpsExBulkEditRow(type, count)` 함수가 `opsExBulkEditRow` 내부 HTML을 교체하며, 적용 버튼은 항상 `id="opsExBulkApplyBtn"`을 재사용 (단일 버튼, 타입별 핸들러 분기).

---

## 3. 컨텍스트 패널 인라인 편집

### 확장 대상
`renderOpsExceptionContextPanel(row, type)` 함수에 타입별 편집 폼 섹션 추가.

### MEDIA_MISSING (OwnedItem)
```html
<div class="ops-ex-ctx-edit-section">
  <label>미디어 타입</label>
  <select id="opsExCtxMediaType">...</select>
  <button data-ops-ctx-save="media_type">저장</button>
  <div class="status"></div>
</div>
```
저장 시:
1. `PATCH /owned-items/{id}` with `music_detail: { media_type: value }`
2. 성공 → 자동으로 연동 `size_group` 추정 업데이트 (서버 사이드)
3. 해당 행 목록에서 제거

### SIZE_MISMATCH (OwnedItem)
```html
<div class="ops-ex-ctx-edit-section">
  <label>규격 그룹</label>
  <select id="opsExCtxSizeGroup">...</select>
  <button data-ops-ctx-save="size_group">저장</button>
  <div class="status"></div>
</div>
```
저장 시: `PATCH /owned-items/{id}` with `size_group: value`

### GENRE_MISSING (Master)
```html
<div class="ops-ex-ctx-edit-section">
  <label>장르 (쉼표 구분)</label>
  <input id="opsExCtxGenres" value="[기존값]" />
  <label>스타일 (쉼표 구분)</label>
  <input id="opsExCtxStyles" value="[기존값]" />
  <button data-ops-ctx-save="genres">저장</button>
  <div class="status"></div>
</div>
```
저장 시: `PATCH /album-masters/{masterId}/correction` with `genres`, `styles`

### CATALOG_MISSING (OwnedItem, 개별 편집만)
```html
<div class="ops-ex-ctx-edit-section">
  <label>카탈로그 번호</label>
  <input id="opsExCtxCatalogNo" value="[기존값]" />
  <label>레이블</label>
  <input id="opsExCtxLabelName" value="[기존값]" />
  <button data-ops-ctx-save="catalog">저장</button>
  <div class="status"></div>
</div>
```
저장 시: `PATCH /owned-items/{id}` with `music_detail: { catalog_no, label_name }`

### 저장 후 공통 동작
- 성공 → 패널 내 저장 완료 메시지 + 해당 행 목록에서 제거 + 카운트 -1
- 실패 → 패널 내 에러 메시지 (행 유지)

---

## 4. 백엔드 변경

### ① 신규 엔드포인트: `POST /owned-items/bulk-update-music-detail`

**파일:** `app/api/owned_items.py`, `app/schemas.py`, `app/db/owned_item_write.py`

```python
class OwnedItemBulkUpdateMusicDetailRequest(BaseModel):
    owned_item_ids: list[int] = Field(default_factory=list)
    media_type: str | None = None   # music_item_detail.media_type

class OwnedItemBulkUpdateMusicDetailResponse(BaseModel):
    requested_count: int
    updated_count: int
    updated_item_ids: list[int] = Field(default_factory=list)
```

동작:
- `music_item_detail`에 `media_type` UPDATE
- `media_type`에 따라 `owned_item.size_group` 자동 추정:
  ```python
  MEDIA_TYPE_TO_SIZE_GROUP = {
      "Vinyl": "LP", "LP": "LP",
      '10"': "LP10", '7"': "LP7",
      "CD": "STD", "CDr": "STD", "SACD": "STD", "Digital": "STD",
      "Cassette": "CASSETTE", "8-Track Cartridge": "8TRACK",
      "DVD": "STD", "Blu-ray": "STD", "CD-ROM": "STD",
  }
  ```
- `music_item_detail`이 없는 경우 생성 후 `media_type` 설정

### ② 기존 확장: `OwnedItemBulkUpdateRequest`에 `size_group` 추가

**파일:** `app/schemas.py`, `app/db/owned_item_write.py`

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

`bulk_update_owned_items` DB 함수도 `size_group` UPDATE 포함.

### ③ 신규 엔드포인트: `POST /album-masters/bulk-update-genres`

**파일:** `app/api/album_masters.py`, `app/schemas.py`

```python
class AlbumMasterBulkUpdateGenresRequest(BaseModel):
    album_master_ids: list[int] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    styles: list[str] = Field(default_factory=list)

class AlbumMasterBulkUpdateGenresResponse(BaseModel):
    requested_count: int
    updated_count: int
```

기존 `update_album_master_genres(album_master_id, genres, styles)` DB 함수 반복 호출.

---

## 5. 기존 카드 사용성 개선

### 공통 개선
- 벌크 작업 완료 후 결과를 `opsExBulkEditStatus` (또는 `opsExceptionStatus`)에 표시: `완료 — 성공: N건 / 실패: F건`
- 현재 벌크 버튼들(소스 보강, 실물 기준 맞춤 등)도 동일한 상태 피드백 추가

### PREFERRED_SIZE_MISMATCH
- 기존 "실물 기준 맞춤" 실행 후 몇 건이 변경됐는지 결과 수 표시

### SOURCE_MISSING / COVER_MISSING / TRACK_MISSING
- 소스 보강 전송 완료 후 `N건이 소스 보강 대상으로 이동됐습니다` 토스트 표시

### REVIEW_MISSING
- 기존 벌크 수집 버튼에 진행률 표시 (`수집 중... 3/10`) 이미 구현됨 → 유지

---

## 6. 파일 맵

| 파일 | 변경 내용 |
|------|-----------|
| `app/schemas.py` | `OwnedItemBulkUpdateRequest.size_group` 추가, 신규 스키마 2개 |
| `app/api/owned_items.py` | `POST /owned-items/bulk-update-music-detail` 신규 |
| `app/api/album_masters.py` | `POST /album-masters/bulk-update-genres` 신규 |
| `app/db/owned_item_write.py` | `bulk_update_owned_items` size_group 지원, 신규 `bulk_update_music_detail` |
| `app/db/album_master_core.py` | 신규 `bulk_update_album_master_genres` (반복 호출 래퍼) |
| `app/static/index.html` | 상세 검색 조건 UI, 툴바 벌크 컨트롤, 컨텍스트 패널 편집 폼 |
| `tests/` | 신규 엔드포인트 테스트 |
