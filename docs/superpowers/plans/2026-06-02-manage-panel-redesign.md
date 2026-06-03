# 미디어>관리 패널 단일 컬럼 재설계 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 미디어>관리 패널의 2단 레이아웃을 6개 `<details>` 섹션 스택으로 전환하고, 인라인 설명 텍스트를 제거/풍선 도움말로 이동한다.

**Architecture:** `app/static/index.html` 단일 파일 수정. CSS 2단 클래스 제거 → 구조 래퍼 전환(details→div) → 6개 섹션 `<details>` 구성 → 텍스트 정리. 백엔드 변경 없음. 기존 element ID는 최대한 유지해 JS 핸들러 변경을 최소화한다.

**Tech Stack:** HTML, CSS (변수 기반 테마), vanilla JS (기존 이벤트 핸들러 유지)

---

## 현재 구조 요약

```
homeEditorCard (section)
  homeEditorSelectedLabel
  homeCabinetSection               ← 위치 정보 (현재 최상단, 항상 표시)
  homeAcquisitionSourceInfo/Link
  homeEditUnifiedDetails (details) ← 2단 래퍼, masterId>0 일 때 표시
    home-editor-layout-wrapper (div)
      homeEditorLeftPane (div, 280px sticky)
        homeSection1MasterInfo     ← 마스터 카드
        homeMasterSpotifyMatchSection
        homeMasterEditDetails (details) ← 마스터 교정 필드
          homeMasterSortArtistRow
          homeMasterReviewSection
          homeMasterSummarySection
          homeLinkedGoodsPanelDetails
          homeSection3MasterDelete
      homeEditorRightPane (div, flex:1)
        "상품 수정" h2
        homeEditMusicProductSplit  ← 상품 필드 전체
        homeEditorActionBlock      ← 저장/삭제 버튼
        homeSection2ProductInfo
          homeSection21OwnedItem   ← 보유 상품 목록
          homeSection22ProductAdd  ← 상품 추가
          homeProductLinkedGoodsSection ← 수집품 연계
```

## 목표 구조

```
homeEditorCard (section)
  homeEditorSelectedLabel
  homeAcquisitionSourceInfo/Link

  ④ manageSection4Location (details, 기본 열림, 항상 표시)
     homeCabinetSection 내용

  homeEditUnifiedDetails (div, masterId>0 일 때 표시)  ← details→div 전환

    ① manageSection1Product (details open)             ← 상품 수정
       homeEditMusicProductSplit + homeEditorActionBlock

    ② manageSection2SpotifyReview (details open)       ← Spotify·리뷰
       compact 마스터 카드 + homeMasterSpotifyMatchSection + homeMasterReviewSection

    ③ homeMasterEditDetails (details, 기본 닫힘)        ← 마스터 메타 수정
       교정 필드 + sort artist + 삭제

    ⑤ manageSection5OwnedItems (details, 기본 닫힘)    ← 보유 상품
       homeMasterSummarySection + homeMasterRelatedList + homeProductRelationSection

    ⑥ manageSection6AddLink (details, 기본 닫힘)       ← 추가·연계
       homeSection22ProductAdd + homeLinkedGoodsPanelDetails + homeProductLinkedGoodsSection
```

---

## 파일 구조

| 파일 | 변경 내용 |
|------|-----------|
| `app/static/index.html` | CSS 제거/추가, HTML 구조 재편, 텍스트 정리 |

---

## Task 0: CSS — 2단 레이아웃 제거 및 섹션 스타일 추가

**Files:**
- Modify: `app/static/index.html` (lines ~11620-11656 CSS 영역, ~2083-2093 CSS 영역)

### 배경
2단 레이아웃을 구성하는 `.home-editor-layout-wrapper`, `.home-editor-left-pane`, `.home-editor-right-pane` CSS를 제거하고, 새 섹션 `<details>` 스타일을 추가한다.

- [ ] **Step 1: 2단 레이아웃 CSS 블록 제거**

찾아서 전체 제거:
```css
    /* 2열 배치 레이아웃 */
    .home-editor-layout-wrapper {
      display: flex;
      gap: 16px;
      align-items: flex-start;
      margin-top: 10px;
    }
    .home-editor-left-pane {
      width: 280px;
      flex-shrink: 0;
      position: sticky;
      top: 8px;
      overflow-y: auto;
      max-height: calc(100vh - 120px);
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .home-editor-right-pane {
      flex: 1;
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    @media (max-width: 768px) {
      .home-editor-layout-wrapper {
        flex-direction: column;
        align-items: stretch;
      }
      .home-editor-left-pane {
        width: 100%;
        position: static;
        max-height: none;
      }
    }
```

- [ ] **Step 2: 기존 .home-unified-edit-details 섹션 CSS 수정**

찾기:
```css
    .home-unified-edit-details {
```

이 CSS 블록(`#tabManage .home-unified-edit-details` 포함)은 유지하되, `homeEditUnifiedDetails`가 `<div>`로 바뀌므로 summary 관련 부분은 나중에 정리한다. 지금은 그대로 둔다.

- [ ] **Step 3: manage-section-details 스타일 추가**

`.home-unified-edit-details` CSS 블록 직전에 추가:
```css
    /* 관리 패널 섹션 스택 */
    .manage-sections-wrapper {
      display: flex;
      flex-direction: column;
      gap: 0;
      margin-top: 8px;
    }
    .manage-section-details {
      border-top: 1px solid var(--line);
    }
    .manage-section-details:last-child {
      border-bottom: 1px solid var(--line);
    }
    .manage-section-summary {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 4px;
      cursor: pointer;
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--muted);
      user-select: none;
      list-style: none;
    }
    .manage-section-summary::-webkit-details-marker { display: none; }
    .manage-section-summary::marker { display: none; }
    .manage-section-summary::before {
      content: "▶";
      font-size: 9px;
      margin-right: 6px;
      color: var(--muted);
      transition: transform 0.15s;
    }
    .manage-section-details[open] > .manage-section-summary::before {
      content: "▼";
    }
    .manage-section-details > .manage-section-body {
      padding: 8px 0 16px 0;
    }
```

- [ ] **Step 4: #homeSection 관련 CSS에서 제거된 ID 정리**

찾기 (약 2083~2093줄):
```css
    #homeSection2ProductInfo,
    #homeSection3MasterDelete {
```

`#homeSection3MasterDelete`는 이 규칙에서 제거한다 (섹션 ③ 내부로 이동):
```css
    #homeSection2ProductInfo {
```

그 아래 블록 (약 2089줄):
```css
    #homeSection21OwnedItem,
    #homeSection22ProductAdd,
    #homeSection22FromMaster,
    #homeSection22FromSource,
    #homeProductLinkedGoodsSection {
```
→ 이 줄들은 그대로 둔다 (IDs 유지).

- [ ] **Step 5: 구문 확인**

```bash
grep -c "home-editor-layout-wrapper" app/static/index.html
```
Expected: `0` (CSS 제거 후 남은 참조 없어야 함)

```bash
grep -c "manage-section-details" app/static/index.html
```
Expected: `1` (방금 추가한 CSS만)

- [ ] **Step 6: Commit**

```bash
git add app/static/index.html
git commit -m "style(manage): remove 2-column CSS, add manage-section-details styles"
```

---

## Task 1: 구조 래퍼 전환 — details→div, 2단 div 제거

**Files:**
- Modify: `app/static/index.html` (~17963-18862 HTML 영역)

### 배경
`homeEditUnifiedDetails`를 `<details>`에서 `<div>`로 전환하고, 내부 2단 래퍼(`home-editor-layout-wrapper`)와 좌우 pane div를 제거한다. **이 작업 후 내용이 세로로 나열되지만 아직 섹션 분리는 되지 않은 상태** — 이후 Task에서 분리한다.

- [ ] **Step 1: homeEditUnifiedDetails details 태그를 div로 전환**

찾기:
```html
        <!-- 통합 수정 패널 (기본 접힘) -->
        <details id="homeEditUnifiedDetails" class="home-unified-edit-details u-hidden-initial u-mt-4">
            <summary class="home-unified-edit-summary">수정 / 편집</summary>
            <div class="home-unified-edit-body">
```

교체:
```html
        <!-- 관리 섹션 스택 -->
        <div id="homeEditUnifiedDetails" class="manage-sections-wrapper u-hidden-initial u-mt-4">
```

- [ ] **Step 2: home-editor-layout-wrapper div 제거**

찾기:
```html
              <div class="home-editor-layout-wrapper">
                <!-- ==================== LEFT PANEL ==================== -->
                <div id="homeEditorLeftPane" class="home-editor-left-pane">
```

교체 (div 태그만 제거, 내용은 유지):
```html
```
(즉, 두 줄 전체 삭제 — 내용물만 남김)

- [ ] **Step 3: homeEditorLeftPane 닫는 태그와 RIGHT PANEL 시작 제거**

찾기:
```html
        </div><!-- /homeEditorLeftPane -->

        <!-- ==================== RIGHT PANEL ==================== -->
        <div id="homeEditorRightPane" class="home-editor-right-pane">
          <!-- ══ 장식장 / 위치 정보 (최상단) ══ -->
          <!-- ══ 상품 수정 ══ -->
```

교체 (모두 제거):
```html
```

- [ ] **Step 4: homeEditorRightPane 닫는 태그와 래퍼 닫는 태그들 제거**

찾기:
```html
              </div><!-- /homeEditorRightPane -->
            </div><!-- /home-editor-layout-wrapper -->
          </div><!-- /home-unified-edit-body -->
        </details>
```

교체:
```html
        </div><!-- /homeEditUnifiedDetails -->
```

- [ ] **Step 5: 검증**

```bash
# 제거된 클래스 참조 없어야 함
grep -c "homeEditorLeftPane\|homeEditorRightPane\|home-editor-layout-wrapper\|home-unified-edit-body" app/static/index.html
```
Expected: `0`

```bash
# homeEditUnifiedDetails는 div로 1개 남아야 함
grep -c "homeEditUnifiedDetails" app/static/index.html
```
Expected: `3` (HTML div 1 + JS 참조 2)

- [ ] **Step 6: Commit**

```bash
git add app/static/index.html
git commit -m "refactor(manage): convert homeEditUnifiedDetails from details to div, remove 2-col wrappers"
```

---

## Task 2: 섹션 ④ 위치 — homeCabinetSection을 details로 감싸기

**Files:**
- Modify: `app/static/index.html` (~17934-17960 HTML 영역)

### 배경
`homeCabinetSection`은 현재 `homeEditUnifiedDetails` 위에 위치하며 항목 선택 시 항상 표시된다. 이를 `<details>` 섹션으로 감싸되, `homeEditorCard` 안에서 `homeEditUnifiedDetails` 앞에 유지한다 (항목 선택 시 항상 표시 동작 유지).

- [ ] **Step 1: homeCabinetSection을 details로 감싸기**

찾기:
```html
          <div id="homeCabinetSection">
            <div class="section-divider u-mt-0">
              <h2><span data-i18n="media.manage.location.title">장식장 / 위치 정보</span><span class="section-help-dot" tabindex="0" data-help-key="help.media.manage.location">?</span></h2>
            </div>
```

교체:
```html
        <details id="manageSection4Location" class="manage-section-details" open>
          <summary class="manage-section-summary" data-i18n="media.manage.section.location">위치</summary>
          <div class="manage-section-body">
          <div id="homeCabinetSection">
```

찾기 (homeCabinetSection 닫는 태그):
```html
          </div>

        <div id="homeAcquisitionSourceInfo"
```

교체:
```html
          </div>
          </div><!-- /manage-section-body -->
        </details><!-- /manageSection4Location -->

        <div id="homeAcquisitionSourceInfo"
```

- [ ] **Step 2: i18n 키 추가**

KO 사전에서 `"media.manage.location.title"` 근처에 추가:
```
"media.manage.section.location": "위치",
"media.manage.section.product": "상품 수정",
"media.manage.section.spotify_review": "Spotify · 리뷰",
"media.manage.section.master_meta": "마스터 메타 수정",
"media.manage.section.owned_items": "보유 상품",
"media.manage.section.add_link": "추가 · 연계",
```

EN 사전에서 같은 키 추가:
```
"media.manage.section.location": "Location",
"media.manage.section.product": "Product edit",
"media.manage.section.spotify_review": "Spotify · Review",
"media.manage.section.master_meta": "Master metadata",
"media.manage.section.owned_items": "Owned items",
"media.manage.section.add_link": "Add · Link",
```

JA 사전에서 같은 키 추가:
```
"media.manage.section.location": "位置",
"media.manage.section.product": "商品編集",
"media.manage.section.spotify_review": "Spotify · レビュー",
"media.manage.section.master_meta": "マスターメタ修正",
"media.manage.section.owned_items": "保有商品",
"media.manage.section.add_link": "追加・連携",
```

- [ ] **Step 3: 검증**

```bash
grep -c "manageSection4Location" app/static/index.html
```
Expected: `1`

- [ ] **Step 4: Commit**

```bash
git add app/static/index.html
git commit -m "feat(manage): wrap location section in collapsible details (section IV)"
```

---

## Task 3: 섹션 ① 상품 수정 — 상품 편집 영역 details로 감싸기

**Files:**
- Modify: `app/static/index.html` (~18225-18616 HTML 영역)

### 배경
현재 "상품 수정" h2 헤딩부터 `homeSection2ProductInfo` 직전까지(`homeEditorActionBlock` 포함)를 섹션 ① `<details>`로 감싼다.

- [ ] **Step 1: 상품 수정 h2 위에 details 시작 태그 삽입**

찾기:
```html
          <!-- ══ 상품 수정 ══ -->
          <div class="section-divider u-mt-8">
            <h2>상품 수정</h2>
          </div>
```

교체:
```html
        <details id="manageSection1Product" class="manage-section-details" open>
          <summary class="manage-section-summary" data-i18n="media.manage.section.product">상품 수정</summary>
          <div class="manage-section-body">
```

- [ ] **Step 2: homeEditorActionBlock 뒤에 details 닫기 태그 삽입**

찾기:
```html
        <!-- ══ 섹션 2: 상품 정보 ══ -->
        <div id="homeSection2ProductInfo">
```

교체:
```html
          </div><!-- /manage-section-body -->
        </details><!-- /manageSection1Product -->

        <!-- ══ 섹션 2: 상품 정보 ══ -->
        <div id="homeSection2ProductInfo">
```

- [ ] **Step 3: 검증**

```bash
grep -c "manageSection1Product" app/static/index.html
```
Expected: `2` (opening + closing)

```bash
python3 -c "
from html.parser import HTMLParser
class Checker(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.errors = []
    def handle_starttag(self, tag, attrs):
        if tag not in ('br','hr','img','input','meta','link','area','base','col','embed','param','source','track','wbr'):
            self.depth += 1
    def handle_endtag(self, tag):
        self.depth -= 1
c = Checker()
c.feed(open('app/static/index.html').read())
print('depth at end:', c.depth)
"
```
Expected: depth가 0에 가까움 (HTML 구조 검증)

- [ ] **Step 4: Commit**

```bash
git add app/static/index.html
git commit -m "feat(manage): wrap product edit in collapsible details section (section I)"
```

---

## Task 4: 섹션 ② Spotify·리뷰 — 좌측 패널에서 새 섹션으로 이동

**Files:**
- Modify: `app/static/index.html` (좌측 패널 내 homeMasterSpotifyMatchSection, homeMasterReviewSection)

### 배경
현재 좌측 패널(`homeEditorLeftPane`)에 있던 Spotify 연결과 리뷰 섹션을 꺼내 `homeEditUnifiedDetails` 안, 섹션 ① 바로 아래에 새 `<details>` 섹션으로 배치한다.

Task 1에서 좌측 패널 div는 제거됐으므로, 이 내용들은 현재 `homeEditUnifiedDetails` 안에 섹션 ①과 뒤섞인 상태다. 이 Task에서 정리한다.

**주의:** `homeMasterMetaCard`(마스터 커버·제목·아티스트 카드)는 compact 마스터 컨텍스트로 섹션 ② 상단에 유지한다.

- [ ] **Step 1: 섹션 ② 시작 — homeMasterMetaCard 위에 details 삽입**

찾기:
```html
                  <!-- 마스터 메타 카드: 커버아트 + 앨범명 + 아티스트 + 연도 + 링크 -->
                    <div id="homeMasterMetaCard" class="u-hidden-initial">
```

교체:
```html
        <details id="manageSection2SpotifyReview" class="manage-section-details" open>
          <summary class="manage-section-summary" data-i18n="media.manage.section.spotify_review">Spotify · 리뷰</summary>
          <div class="manage-section-body">
                  <!-- 마스터 메타 카드: 커버아트 + 앨범명 + 아티스트 + 연도 + 링크 -->
                    <div id="homeMasterMetaCard" class="u-hidden-initial">
```

- [ ] **Step 2: 섹션 ② 끝 — homeMasterReviewSection 닫는 div 뒤에 details 닫기**

현재 `homeMasterReviewSection` 다음에 `homeMasterEditDetails`(`<details>`)가 온다. 그 직전에 섹션 ② 닫기 태그를 삽입한다.

찾기 (homeMasterEditDetails 시작 직전):
```html
        <details id="homeMasterEditDetails" class="home-unified-edit-details u-hidden-initial u-mt-2">
```

교체:
```html
          </div><!-- /manage-section-body -->
        </details><!-- /manageSection2SpotifyReview -->

        <details id="homeMasterEditDetails" class="home-unified-edit-details u-hidden-initial u-mt-2">
```

- [ ] **Step 3: 검증**

```bash
grep -n "manageSection2SpotifyReview\|homeMasterMetaCard\|homeMasterSpotifyMatchSection\|homeMasterReviewSection\|homeMasterEditDetails" app/static/index.html | head -20
```

`manageSection2SpotifyReview`의 `<details>` 안에 `homeMasterMetaCard`, `homeMasterSpotifyMatchSection`, `homeMasterReviewSection`이 포함되고, `homeMasterEditDetails`는 그 다음에 위치해야 한다.

- [ ] **Step 4: Commit**

```bash
git add app/static/index.html
git commit -m "feat(manage): create Spotify·review section (section II) from left pane content"
```

---

## Task 5: 섹션 ③ 마스터 메타 수정 — homeMasterEditDetails 재단장

**Files:**
- Modify: `app/static/index.html` (~18004-18100 HTML 영역)

### 배경
기존 `homeMasterEditDetails` (`<details>`)는 이미 접힌 형태지만 클래스와 summary 스타일이 구식이다. 이를 `manage-section-details` 스타일로 업데이트하고, 내부에서 `homeMasterSummarySection`, `homeLinkedGoodsPanelDetails`, `homeSection3MasterDelete`를 꺼내 별도 섹션으로 분리한다 (이 요소들은 보유 상품·연계 섹션으로 이동).

- [ ] **Step 1: homeMasterEditDetails 클래스·summary 수정**

찾기:
```html
        <details id="homeMasterEditDetails" class="home-unified-edit-details u-hidden-initial u-mt-2">
            <summary class="home-unified-edit-summary" data-i18n="media.manage.master.correction.title">앨범(마스터) 메타 수정</summary>
```

교체:
```html
        <details id="homeMasterEditDetails" class="manage-section-details u-hidden-initial">
            <summary class="manage-section-summary" data-i18n="media.manage.section.master_meta">마스터 메타 수정</summary>
          <div class="manage-section-body">
```

- [ ] **Step 2: homeSection3MasterDelete 이동 — homeMasterEditDetails 안으로**

현재 `homeSection3MasterDelete`는 좌측 패널 하단(`homeEditorLeftPane` 끝)에 있다. Task 1에서 좌측 패널 div가 제거됐으므로, 이 요소는 현재 `homeEditUnifiedDetails` 안에 독립적으로 위치한다. 이를 `homeMasterEditDetails` 닫는 `</details>` 직전으로 이동한다.

찾기 (homeMasterEditDetails 닫는 `</details>` — 현재 `homeMasterSummarySection` 직전):
```html
        </details><!-- end homeMasterEditDetails -->
```
혹은 패턴 확인:
```bash
grep -n "homeMasterSummarySection\|/homeMasterEditDetails\|homeSection3MasterDelete" app/static/index.html | head -20
```

`homeMasterEditDetails` 닫는 태그 바로 앞에 `homeSection3MasterDelete` 전체 블록이 오도록 이동. 마스터 삭제 블록 위치 확인 후 CUT → PASTE.

**구체적 순서:**
1. `<div id="homeSection3MasterDelete"...>` ~ `</div>` 전체를 찾아 삭제
2. `homeMasterEditDetails` 내부 마지막(닫기 직전)에 붙여넣기

삽입 위치 (homeMasterEditDetails 닫기 직전):
```html
              <!-- 마스터 삭제 -->
              <div id="homeSection3MasterDelete" style="margin-top: 12px;">
                <div class="home-master-danger-zone" style="border: 1px solid var(--border); border-radius: 8px; padding: 10px; background: rgba(220,53,69,0.05);">
                  <div class="section-divider u-mt-0">
                    <h2 style="color: var(--err);"><span data-i18n="media.manage.master.delete.title">앨범(마스터) 삭제</span><span class="section-help-dot" tabindex="0" data-help-key="media.manage.master.delete.note_help">?</span></h2>
                  </div>
                  <div id="homeMasterDeleteActions" class="row home-manage-actions-right" style="margin-top: 8px;">
                    <label class="inline-check u-maxw-250">
                      <input id="homeMasterDeleteCascade" type="checkbox" />
                      <span data-i18n="media.manage.master.delete.cascade">연결 상품도 함께 삭제</span>
                    </label>
                    <button id="homeMasterDeleteBtn" class="btn ghost danger tiny" type="button" disabled data-i18n="media.manage.master.delete.action">앨범(마스터) 삭제</button>
                  </div>
                </div>
              </div>
          </div><!-- /manage-section-body -->
        </details><!-- /homeMasterEditDetails -->
```

- [ ] **Step 3: 마스터 삭제 인라인 경고문 → help-dot**

`homeSection3MasterDelete` 안에 있는 경고 `.mini` 텍스트를 찾아 제거하고, h2의 `section-help-dot`에 `data-help-key="media.manage.master.delete.note_help"` 를 추가한다.

찾기 (마스터 삭제 note div):
```html
                  <div class="mini" data-i18n="media.manage.master.delete.note">상품 편집을 먼저 마친 뒤, 정말 필요할 때만 사용하세요. 연결 상품까지 함께 삭제할 수 있습니다.</div>
```

제거 (이 줄 전체 삭제).

KO 사전에 help-key 추가:
```
"media.manage.master.delete.note_help": "상품 편집을 먼저 마친 뒤, 정말 필요할 때만 사용하세요. 연결 상품까지 함께 삭제할 수 있습니다.",
```

- [ ] **Step 4: 검증**

```bash
grep -n "manageSection3\|homeMasterEditDetails\|homeSection3MasterDelete" app/static/index.html | head -15
```

`homeMasterEditDetails` 안에 `homeSection3MasterDelete`가 포함됐는지 확인.

- [ ] **Step 5: Commit**

```bash
git add app/static/index.html
git commit -m "feat(manage): restyle master meta section (III), move delete block inside"
```

---

## Task 6: 섹션 ⑤ 보유 상품 — homeMasterSummarySection + homeSection21 통합

**Files:**
- Modify: `app/static/index.html` (~18101-18704 HTML 영역)

### 배경
현재 `homeMasterSummarySection`, `homeMasterActionMount`, `homeMasterInlineEditorParking` (좌측 패널 출신)과 `homeSection21OwnedItem` (우측 패널 출신)을 하나의 섹션 ⑤로 묶는다.

- [ ] **Step 1: manageSection5OwnedItems details 삽입**

찾기 (homeMasterSummarySection 바로 앞, homeMasterEditDetails 닫기 다음):
```html
          <!-- ══ 마스터 / 보유 상품 및 마스터 연계 수집품 (이동됨) ══ -->
          <div id="homeMasterSummarySection" class="u-hidden-initial">
```

교체:
```html
        <details id="manageSection5OwnedItems" class="manage-section-details">
          <summary class="manage-section-summary" data-i18n="media.manage.section.owned_items">보유 상품</summary>
          <div class="manage-section-body">
          <!-- ══ 마스터 / 보유 상품 ══ -->
          <div id="homeMasterSummarySection" class="u-hidden-initial">
```

- [ ] **Step 2: homeSection21OwnedItem 닫는 태그 뒤에 섹션 ⑤ 닫기 삽입**

찾기:
```html
          </div>

          <!-- 2-2: 상품 추가 (마스터에서 / 다른소스에서) -->
          <div id="homeSection22ProductAdd">
```

교체:
```html
          </div>
          </div><!-- /manage-section-body -->
        </details><!-- /manageSection5OwnedItems -->

        <details id="manageSection6AddLink" class="manage-section-details">
          <summary class="manage-section-summary" data-i18n="media.manage.section.add_link">추가 · 연계</summary>
          <div class="manage-section-body">
          <!-- 상품 추가 / 연계 -->
          <div id="homeSection22ProductAdd">
```

- [ ] **Step 3: homeSection2ProductInfo 래퍼 닫는 태그 뒤 섹션 ⑥ 닫기 삽입**

`homeSection2ProductInfo` div의 닫기 태그와 `homeEditorRightPane` 닫기 사이에 섹션 ⑥ 닫기를 삽입한다.

찾기 (`homeProductLinkedGoodsSection` 뒤):
```html
        </div><!-- /homeEditUnifiedDetails -->
```

이 태그 앞에 삽입:
```html
          </div><!-- /manage-section-body -->
        </details><!-- /manageSection6AddLink -->
```

- [ ] **Step 4: homeSection21 헤딩에서 섹션 번호 제거**

찾기:
```html
              <h2><span data-i18n="media.manage.section2_1.title">2-1. 보유 상품</span></h2>
```

교체:
```html
              <h2><span data-i18n="media.manage.section2_1.title">보유 상품 목록</span></h2>
```

KO 사전에서 `"media.manage.section2_1.title"` 값을 `"보유 상품 목록"`으로 업데이트.

찾기:
```html
              <h2><span data-i18n="media.manage.section2_2.title">2-2. 상품 추가</span></h2>
```

교체:
```html
              <h2><span data-i18n="media.manage.section2_2.title">상품 추가</span></h2>
```

찾기:
```html
              <h2><span data-i18n="media.manage.section2_3.title">2-3. 상품 연계 수집품</span></h2>
```

교체:
```html
              <h2><span data-i18n="media.manage.section2_3.title">연계 수집품</span></h2>
```

- [ ] **Step 5: 검증**

```bash
grep -c "manageSection5OwnedItems\|manageSection6AddLink" app/static/index.html
```
Expected: 각각 `2` (열기+닫기)

- [ ] **Step 6: Commit**

```bash
git add app/static/index.html
git commit -m "feat(manage): create owned-items (V) and add-link (VI) sections, remove section numbers"
```

---

## Task 7: 텍스트 정리 — 중복 설명 제거 및 help-dot 이동

**Files:**
- Modify: `app/static/index.html`

### 배경
인라인 설명 중 중복이거나 help-dot으로 대체 가능한 것들을 정리한다.

- [ ] **Step 1: Sort artist 중복 note 제거**

찾기:
```html
                <div class="dashboard-selected-sort-artist-note mini" data-i18n="media.manage.master.sort_artist.note">같은 마스터의 모든 미디어 정렬에 공통 적용됩니다.</div>
```

이 줄 전체 삭제. (help-dot에 동일 내용이 이미 있음)

- [ ] **Step 2: 소스 메타 요약 힌트 → help-dot**

찾기:
```html
                          <span id="homeEditMusicSourceSummaryHint" class="mini" data-i18n="media.manage.source_meta.hint">외부 소스 메타는 후보 교체로 갱신</span>
```

교체:
```html
                          <span class="help-dot" tabindex="0" data-help-key="media.manage.source_meta.hint_help">?</span>
```

KO 사전 추가:
```
"media.manage.source_meta.hint_help": "외부 소스 메타는 후보 교체로 갱신합니다. 소스 보강 탭에서 다른 소스로 교체하세요.",
```

- [ ] **Step 3: 마스터 연계 추가 설명 단락 → help-dot 이미 있음 확인**

확인:
```bash
grep -n "data-help=\"필요할 때만\|마스터 연계 추가.*section-help-dot" app/static/index.html | head -5
```

`section-help-dot`이 이미 있으면 추가 작업 없음. 없으면:
h3 태그의 `section-help-dot` span에 `data-help` 내용이 있는지 확인 후 필요 시 추가.

- [ ] **Step 4: 다른 소스에서 추가 설명 단락 → help-dot**

찾기:
```html
                <div class="mini" data-i18n="media.manage.section2_2.from_source.help">현재 마스터에 없는 상품을 다른 소스에서 찾아 연계 상품으로 추가합니다. 기존 상품의 소스 교체는 '소스 보강' 탭에서 처리합니다.</div>
```

이 줄 전체 삭제. h3 태그에 `section-help-dot` 추가:

찾기:
```html
                  <h3 data-i18n="media.manage.section2_2.from_source.title">다른소스에서 추가</h3>
```

교체:
```html
                  <h3 data-i18n="media.manage.section2_2.from_source.title">다른소스에서 추가<span class="section-help-dot" tabindex="0" data-help-key="media.manage.section2_2.from_source.help">?</span></h3>
```

KO 사전 추가:
```
"media.manage.section2_2.from_source.help": "현재 마스터에 없는 상품을 다른 소스에서 찾아 연계 상품으로 추가합니다. 기존 상품의 소스 교체는 '소스 보강' 탭에서 처리합니다.",
```

- [ ] **Step 5: 수집품 패널 설명 단락 2개 → help-dot**

찾기 (수집품 안내 단락 1):
```html
                <div class="mini muted span-2 u-mt-0" data-i18n="media.manage.collectibles.panel_intro">수집품 등록과 검색은 상단 `수집품` 탭에서 독립적으로 관리하고, 여기서는 현재 마스터 기준 연결만 시작합니다.</div>
```

이 줄 전체 삭제.

찾기 (수집품 안내 단락 2):
```html
                <div class="mini span-2 u-mt-6" data-i18n="media.manage.collectibles.panel_note">콜라보, 레이블 행사 수집품, 단독 수집품은 `수집품` 탭에서 별도로 등록한 뒤 필요할 때만 현재 마스터와 연결하면 됩니다.</div>
```

이 줄 전체 삭제.

이미 `homeLinkedGoodsCreateBtn` 옆에 `help-dot`이 있는지 확인:
```bash
grep -n "homeLinkedGoodsCreateBtn" app/static/index.html
```

help-dot 없으면 버튼 옆에 추가:
```html
<span class="help-dot" tabindex="0" data-help-key="media.manage.collectibles.register_method.help">?</span>
```

- [ ] **Step 6: 상품 관계 subtitle → help-dot 확인**

```bash
grep -n "마스터, 시리즈, 박스세트, 연관 발매를 함께 관리" app/static/index.html
```

있으면 해당 `.mini` div 제거하고 `homeProductRelationSection`의 summary에 help-dot 추가.

- [ ] **Step 7: 검증**

```bash
# 제거된 항목들이 없는지 확인
grep -c "dashboard-selected-sort-artist-note\|homeEditMusicSourceSummaryHint\|panel_intro\|panel_note" app/static/index.html
```
Expected: `0` (모두 제거됨)

- [ ] **Step 8: Commit**

```bash
git add app/static/index.html
git commit -m "style(manage): remove redundant inline descriptions, move to help-dots"
```

---

## Task 8: JS 업데이트 — syncHomeMasterCorrectionEditor 정리

**Files:**
- Modify: `app/static/index.html` (JS 영역 ~46233 근처)

### 배경
`syncHomeMasterCorrectionEditor()`는 현재 `homeEditUnifiedDetails`와 `homeMasterEditDetails`의 `u-hidden-initial` 클래스를 토글한다. `homeEditUnifiedDetails`가 `<div>`로 바뀌었고 `homeMasterEditDetails`가 `manage-section-details`를 가졌으므로 동작을 검증한다. 추가로 `renderAdminManageSurface` 관련 scroll 동작 확인.

- [ ] **Step 1: syncHomeMasterCorrectionEditor 동작 확인**

현재 코드:
```javascript
const unifiedDetails = $("homeEditUnifiedDetails");
const masterEditDetails = $("homeMasterEditDetails");
// ...
if (unifiedDetails) unifiedDetails.classList.add("u-hidden-initial");
if (masterEditDetails) masterEditDetails.classList.add("u-hidden-initial");
// ...
if (unifiedDetails) unifiedDetails.classList.remove("u-hidden-initial");
if (masterEditDetails) masterEditDetails.classList.remove("u-hidden-initial");
```

`homeEditUnifiedDetails`는 이제 `<div>`지만 ID 동일 → JS 그대로 작동.
`homeMasterEditDetails`는 `<details>`에서 `manage-section-details` 클래스 추가됨 → `u-hidden-initial` 토글 그대로 작동.

**변경 불필요.** (확인만)

- [ ] **Step 2: homeSection21OwnedItem scrollIntoView 동작 확인**

찾기:
```bash
grep -n "homeSection21OwnedItem.*scrollIntoView" app/static/index.html
```

해당 줄 확인 후 섹션 ⑤ 안에 `homeSection21OwnedItem`이 여전히 존재하므로 동작 유지. **변경 불필요.**

- [ ] **Step 3: homeLinkedGoodsPanelDetails 관련 JS 확인**

```bash
grep -n "homeLinkedGoodsPanelDetails" app/static/index.html | head -10
```

`<details id="homeLinkedGoodsPanelDetails">`가 섹션 ⑥ 안에 위치하면서 JS가 `classList.add("u-hidden-initial")` / `remove`를 하는지 확인. 동작에 영향 없으면 **변경 불필요.**

- [ ] **Step 4: QA 배포**

```bash
python3 -m py_compile app/api/album_masters.py && echo OK
cp app/static/index.html /Users/__DEV_USER__/apps/__PROJECT_SLUG__-qa/app/static/index.html
```

- [ ] **Step 5: QA 서버 재시작**

```bash
launchctl stop com.muzlife.library-qa && sleep 3 && launchctl start com.muzlife.library-qa
sleep 4 && ps -eo pid,etime,command | grep 'uvicorn.*8100' | grep -v grep
```

- [ ] **Step 6: 브라우저 검증**

`http://localhost:8100` 에서:
1. 미디어 > 검색에서 상품 선택 → 관리 탭으로 이동
2. 위치 섹션(④)이 열린 상태로 보임
3. 상품 수정(①), Spotify·리뷰(②)가 열린 상태
4. 마스터 메타(③), 보유 상품(⑤), 추가·연계(⑥)가 닫힌 상태
5. 상품 수정 필드가 전체 너비 사용
6. 저장 버튼 동작 확인
7. Wikipedia 자동수집 버튼 접근 가능 확인

- [ ] **Step 7: Commit**

```bash
git add app/static/index.html
git commit -m "chore(manage): QA deploy and verify manage panel single-column redesign"
```

---

## 자기 검토 (Self-Review)

### Spec 커버리지

| 스펙 요구사항 | 커버 Task |
|---|---|
| 2단 → 1단 전환 | Task 0, 1 |
| 위치 섹션 (기본 열림) | Task 2 |
| 상품 수정 섹션 (기본 열림) | Task 3 |
| Spotify · 리뷰 섹션 (기본 열림) | Task 4 |
| 마스터 메타 섹션 (기본 닫힘) | Task 5 |
| 보유 상품 섹션 (기본 닫힘) | Task 6 |
| 추가·연계 섹션 (기본 닫힘) | Task 6 |
| Sort artist 중복 note 제거 | Task 7 |
| 섹션 번호 제거 | Task 6 |
| 소스 메타 힌트 → help-dot | Task 7 |
| 마스터 삭제 경고 → help-dot | Task 5 |
| 수집품 설명 단락 → help-dot | Task 7 |
| JS 호환성 유지 | Task 8 |
| i18n (KO/EN/JA) | Task 2 |

모든 스펙 요구사항 커버됨.
