# 앨범 리뷰 표시 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 미디어>검색 우측 패널의 운영 플러그인 섹션 아래에 앨범 리뷰(최대 150자 미리보기 + 펼치기)를 표시한다.

**Architecture:** `operator_search.py` 쿼리에 `review_text`/`review_source` 컬럼을 추가하고, `schemas.py`와 `operator_home.py`에 필드를 전달한 뒤, `index.html`에서 `renderAlbumReviewSection()` 함수로 렌더링한다.

**Tech Stack:** Python 3.11+, FastAPI, SQLite, Vanilla JS (index.html 내 인라인)

---

## 파일 구조

| 파일 | 변경 내용 |
|------|-----------|
| `app/db/__init__.py` | `init_db()` 내 `album_master` CREATE TABLE에 review 컬럼 추가 (테스트 DB용) |
| `app/db/operator_search.py` | SELECT에 `am.review_text`, `am.review_source` 추가 |
| `app/schemas.py` | `OperatorCatalogSearchItem`에 review 필드 2개 추가 |
| `app/api/operator_home.py` | `OperatorCatalogSearchItem` 생성자에 review 필드 전달 |
| `app/static/index.html` | `renderAlbumReviewSection()` 신규 함수 + 호출 삽입 |
| `tests/test_db_operator_catalog_search.py` | review 컬럼 포함 여부 단위 테스트 추가 |

> **참고:** `review_text`, `review_source`, `review_url` 컬럼은 상용/QA DB에 이미 ALTER TABLE로 추가됨. `init_db()` 변경은 테스트용 fresh DB와 미래 신규 설치를 위한 것이다.

---

## Task 0: init_db() — album_master CREATE TABLE에 review 컬럼 추가

**Files:**
- Modify: `app/db/__init__.py:1277-1281`

배경: `init_db()`의 `album_master` CREATE TABLE (line 1260)에 `review_text`, `review_source`, `review_url`이 없다. 상용/QA DB는 ALTER TABLE로 이미 추가했지만, 테스트용 fresh DB는 `init_db()`로 생성되므로 컬럼이 없어 테스트가 실패한다.

- [ ] **Step 1: init_db()의 album_master 테이블 정의에 컬럼 추가**

`app/db/__init__.py`의 `album_master` CREATE TABLE에서 `spotify_image_url TEXT,` 줄 (line 1277) 바로 뒤에 추가:

```sql
              review_text TEXT,
              review_source TEXT,
              review_url TEXT,
```

결과적으로 해당 블록이 다음과 같아야 한다:

```sql
              spotify_album_id TEXT,
              spotify_album_uri TEXT,
              spotify_matched_at TEXT,
              spotify_image_url TEXT,
              review_text TEXT,
              review_source TEXT,
              review_url TEXT,
              raw_json TEXT NOT NULL DEFAULT '{{}}',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE (source_code, source_master_id)
            );
```

- [ ] **Step 2: 구문 검사**

```bash
cd /Volumes/Data/Works/07.hahahoho
python3 -m py_compile app/db/__init__.py && echo OK
```

Expected: `OK`

- [ ] **Step 3: fresh DB에서 컬럼 존재 확인**

```bash
python3 -c "
import os, tempfile
os.environ['LIBRARY_DB_PATH'] = tempfile.mktemp(suffix='.db')
from app.config import get_settings
get_settings.cache_clear()
from app import db
db.init_db()
with db.get_conn() as conn:
    cols = [r[1] for r in conn.execute('PRAGMA table_info(album_master)').fetchall()]
    assert 'review_text' in cols, f'review_text 없음: {cols}'
    assert 'review_source' in cols, f'review_source 없음: {cols}'
    assert 'review_url' in cols, f'review_url 없음: {cols}'
    print('OK:', [c for c in cols if c.startswith('review')])
"
```

Expected: `OK: ['review_text', 'review_source', 'review_url']`

- [ ] **Step 4: 기존 테스트 전체 통과 확인**

```bash
pytest tests/ -x -q 2>&1 | tail -10
```

Expected: 전체 `passed`, 실패 없음

- [ ] **Step 5: 커밋**

```bash
git add app/db/__init__.py
git commit -m "feat(schema): add review_text/review_source/review_url to album_master in init_db"
```

---

## Task 1: operator_search.py — 쿼리에 review 컬럼 추가

**Files:**
- Modify: `app/db/operator_search.py:86-89`
- Test: `tests/test_db_operator_catalog_search.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_db_operator_catalog_search.py` 파일 끝에 추가:

```python
def test_search_operator_catalog_includes_review_fields(isolated_operator_search_db):
    """검색 결과 각 항목에 review_text, review_source 키가 포함되어야 한다."""
    from app.db.operator_search import search_operator_catalog
    from app.db import get_conn

    # album_master에 review 데이터 삽입
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO album_master (id, title, artist_or_brand, review_text, review_source)
            VALUES (1, 'Test Album', 'Test Artist', '좋은 앨범입니다.', '음악취향Y')
        """)
        conn.execute("""
            INSERT INTO owned_item (id, category, item_name_override, linked_album_master_id, status, signature_type, domain_code)
            VALUES (1, 'LP', 'Test LP', 1, 'IN_COLLECTION', 'NONE', 'POP')
        """)

    results = search_operator_catalog("Test", limit=5)
    assert len(results) >= 1
    item = results[0]
    assert "review_text" in item
    assert "review_source" in item
    assert item["review_text"] == "좋은 앨범입니다."
    assert item["review_source"] == "음악취향Y"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd /Volumes/Data/Works/07.hahahoho
pytest tests/test_db_operator_catalog_search.py::test_search_operator_catalog_includes_review_fields -v 2>&1 | tail -10
```

Expected: `FAILED` — `KeyError: 'review_text'` 또는 `AssertionError`

- [ ] **Step 3: operator_search.py 쿼리 수정**

`app/db/operator_search.py`의 `base_sql_template` SELECT 블록에서 `am.sort_artist_name` 줄 바로 뒤에 두 컬럼 추가:

```python
        am.sort_artist_name       AS master_sort_artist_name,
        am.review_text,
        am.review_source,
```

즉, 현재 line 89 (`am.sort_artist_name AS master_sort_artist_name,`) 다음에 위 두 줄을 삽입한다.

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_db_operator_catalog_search.py::test_search_operator_catalog_includes_review_fields -v 2>&1 | tail -10
```

Expected: `PASSED`

- [ ] **Step 5: 전체 operator_search 테스트 통과 확인**

```bash
pytest tests/test_db_operator_catalog_search.py -v 2>&1 | tail -15
```

Expected: 모든 기존 테스트 포함 전체 `PASSED`

- [ ] **Step 6: 커밋**

```bash
git add app/db/operator_search.py tests/test_db_operator_catalog_search.py
git commit -m "feat(search): include review_text and review_source in operator catalog search query"
```

---

## Task 2: schemas.py + operator_home.py — review 필드 전달

**Files:**
- Modify: `app/schemas.py:350`
- Modify: `app/api/operator_home.py:104`

- [ ] **Step 1: schemas.py — OperatorCatalogSearchItem에 필드 추가**

`app/schemas.py` line 350 (`sort_artist_name: str | None = None`) 바로 뒤에 추가:

```python
    review_text: str | None = None
    review_source: str | None = None
```

결과적으로 해당 블록 끝이 다음과 같아야 한다:

```python
    sort_artist_name: str | None = None        # album_master.sort_artist_name (교정 UI 표시)
    review_text: str | None = None
    review_source: str | None = None
```

- [ ] **Step 2: operator_home.py — 생성자에 review 필드 전달**

`app/api/operator_home.py` line 104 (`sort_artist_name=_sort_artist,`) 바로 뒤에 추가:

```python
                review_text=str(row.get("review_text") or "").strip() or None,
                review_source=str(row.get("review_source") or "").strip() or None,
```

결과적으로 해당 `OperatorCatalogSearchItem(...)` 호출 끝이 다음과 같아야 한다:

```python
                sort_artist_name=_sort_artist,
                review_text=str(row.get("review_text") or "").strip() or None,
                review_source=str(row.get("review_source") or "").strip() or None,
            )
```

- [ ] **Step 3: 구문 검사**

```bash
python3 -m py_compile app/schemas.py app/api/operator_home.py && echo OK
```

Expected: `OK`

- [ ] **Step 4: 기존 테스트 전체 통과 확인**

```bash
pytest tests/ -x -q 2>&1 | tail -15
```

Expected: 전체 `passed`, 실패 없음

- [ ] **Step 5: 커밋**

```bash
git add app/schemas.py app/api/operator_home.py
git commit -m "feat(schema): add review_text and review_source to OperatorCatalogSearchItem"
```

---

## Task 3: index.html — renderAlbumReviewSection 구현

**Files:**
- Modify: `app/static/index.html`

배경:
- `renderOpsPluginSection` 함수는 line 33899에 정의되어 있다.
- `renderMediaSearchContextSelection` 함수는 line 34388에 정의되어 있다.
- 운영 플러그인 섹션 렌더링 라인은 line 34432: `` ${renderOpsPluginSection(`...`)} ``
- 리뷰 섹션은 그 바로 다음 줄에 삽입한다.
- 검색 결과 아이템은 `item.review_text`, `item.review_source` 필드를 가진다 (Task 2 이후).

- [ ] **Step 1: renderAlbumReviewSection 함수 추가**

`app/static/index.html`에서 `function renderOpsPluginSection` (line 33899) **바로 앞** 줄에 아래 함수를 삽입한다:

```javascript
    function renderAlbumReviewSection(item) {
      const text = String(item?.review_text || "").trim();
      if (!text) return "";
      const source = String(item?.review_source || "").trim();
      const TRUNCATE_LEN = 150;
      const needsTruncate = text.length > TRUNCATE_LEN;
      const previewText = needsTruncate ? text.slice(0, TRUNCATE_LEN) + "…" : text;
      const sectionId = "albumReviewSection_" + String(item?.owned_item_id || item?.id || 0);
      const textId = "albumReviewText_" + String(item?.owned_item_id || item?.id || 0);
      const btnId = "albumReviewToggleBtn_" + String(item?.owned_item_id || item?.id || 0);

      return `
        <div class="ops-ctx-review" id="${escapeHtml(sectionId)}">
          <div class="ops-ctx-review-label">${escapeHtml(t("media.search.context.review_label") || "앨범 리뷰")}</div>
          <div class="ops-ctx-review-text" id="${escapeHtml(textId)}">${escapeHtml(previewText)}</div>
          ${needsTruncate ? `<button class="btn ghost tiny ops-ctx-review-toggle" type="button" id="${escapeHtml(btnId)}"
            data-review-full="${escapeHtml(text)}"
            data-review-preview="${escapeHtml(previewText)}"
            data-expanded="false">펼치기 ▼</button>` : ""}
          ${source ? `<div class="ops-ctx-review-source">${escapeHtml(t("media.search.context.review_source_label") || "출처")}: ${escapeHtml(source)}</div>` : ""}
        </div>
      `;
    }
```

- [ ] **Step 2: renderMediaSearchContextSelection에 호출 삽입**

`app/static/index.html` line 34432 일대:

현재:
```javascript
        ${renderOpsPluginSection(`
          ${renderOpsArtistContextCard(item, { cardId: "mediaSearchArtistContextCard" })}
        `)}
        <details class="ops-ctx-location-details
```

변경 후:
```javascript
        ${renderOpsPluginSection(`
          ${renderOpsArtistContextCard(item, { cardId: "mediaSearchArtistContextCard" })}
        `)}
        ${renderAlbumReviewSection(item)}
        <details class="ops-ctx-location-details
```

- [ ] **Step 3: 펼치기/접기 이벤트 핸들러 추가**

`renderMediaSearchContextSelection` 함수 끝부분(innerHTML 설정 직후, `loadOpsArtistContext` 호출 전)에서 이벤트 위임 핸들러를 추가한다.

`app/static/index.html`에서 line 34457 일대의 `// 별도 Spotify 패널 숨김` 주석 블록 다음에 추가:

```javascript
      // 앨범 리뷰 펼치기/접기
      root.querySelectorAll(".ops-ctx-review-toggle").forEach(function(btn) {
        btn.addEventListener("click", function() {
          const expanded = btn.dataset.expanded === "true";
          const textEl = document.getElementById(btn.id.replace("albumReviewToggleBtn_", "albumReviewText_"));
          if (!textEl) return;
          if (expanded) {
            textEl.textContent = btn.dataset.reviewPreview;
            btn.textContent = "펼치기 ▼";
            btn.dataset.expanded = "false";
          } else {
            textEl.textContent = btn.dataset.reviewFull;
            btn.textContent = "접기 ▲";
            btn.dataset.expanded = "true";
          }
        });
      });
```

- [ ] **Step 4: 구문 검사 (HTML 파일 JS 부분)**

```bash
node --input-type=module < /dev/null 2>&1 || true
python3 -c "
import re, sys
with open('app/static/index.html', encoding='utf-8') as f:
    content = f.read()
assert 'renderAlbumReviewSection' in content, 'renderAlbumReviewSection 함수 없음'
assert 'ops-ctx-review-toggle' in content, 'toggle 버튼 없음'
assert 'ops-ctx-review-toggle' in content and 'albumReviewToggleBtn_' in content, '이벤트 핸들러 없음'
print('OK')
"
```

Expected: `OK`

- [ ] **Step 5: 커밋**

```bash
git add app/static/index.html
git commit -m "feat(ui): add album review section in media search context panel"
```

---

## Task 4: 수동 UI 검증

> 코드 변경 없음. QA 서버에서 직접 확인한다.

- [ ] **Step 1: QA 서버 재시작**

```bash
PID=$(pgrep -f 'uvicorn.*8100'); kill -TERM $PID; sleep 5
ps -eo pid,etime,command | grep 'uvicorn.*8100' | grep -v grep
```

Expected: 새 PID로 uvicorn 프로세스 표시

- [ ] **Step 2: 리뷰 없는 아이템 검색 및 클릭**

__QA_DOMAIN__ → 미디어>검색 → 리뷰 없는 아이템 클릭
Expected: 우측 패널에 "앨범 리뷰" 섹션이 표시되지 않음

- [ ] **Step 3: 리뷰 있는 아이템 확인**

review_text가 있는 album_master와 연결된 아이템 클릭
Expected: 운영 플러그인 섹션 바로 아래 "앨범 리뷰" 섹션 표시

- [ ] **Step 4: 150자 초과 리뷰 펼치기/접기 확인**

150자 초과 리뷰가 있는 아이템 클릭 → [펼치기 ▼] 클릭 → [접기 ▲] 클릭
Expected:
- 초기: 150자 미리보기 + [펼치기 ▼] 표시
- 펼치기 후: 전체 텍스트 + [접기 ▲] 표시
- 접기 후: 다시 미리보기로 복귀

- [ ] **Step 5: 다른 아이템 클릭 시 초기화 확인**

펼쳐진 상태에서 다른 아이템 클릭
Expected: 새 패널은 접힌 미리보기 상태로 렌더링

---

## 완료 기준

- [ ] `pytest tests/test_db_operator_catalog_search.py` 전체 통과
- [ ] `pytest tests/ -x -q` 전체 통과 (기존 회귀 없음)
- [ ] QA 서버에서 리뷰 없음/있음/펼치기/접기 4가지 시나리오 수동 확인
