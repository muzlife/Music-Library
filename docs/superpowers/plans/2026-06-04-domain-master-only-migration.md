# Domain Master-Only Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `owned_item.domain_code`를 폐기하고 `album_master.domain_code`를 도메인의 단일 진실 공급원(Single Source of Truth)으로 전환한다.

**Architecture:** 현재 `am.domain_code`는 `oi.domain_code`로부터 상향 동기화된다(item → master). 마이그레이션 후에는 반대로 `am.domain_code`가 직접 관리되며, 쿼리 레이어는 `album_master_member` JOIN을 통해 `am.domain_code`를 읽는다. `owned_item.domain_code` 컬럼은 DROP하지 않고 무시(write 중단, read fallback 제거) 처리한다.

**Tech Stack:** SQLite, FastAPI, Pydantic, Vanilla JS (index.html)

---

## 현황 파악 (점검 결과)

| 영역 | 파일 | 내용 |
|------|------|------|
| DB 쿼리 | `app/db/owned_item_query.py:92,282` | `oi.domain_code = ?` 필터 2곳 |
| DB 쓰기 | `app/db/owned_item_write.py:109,251,407` | INSERT/UPDATE에 domain_code 포함, sync 호출 |
| DB 동기화 | `app/db/album_master_core.py:151` | `_sync_album_master_domain_code_in_conn` — oi에서 am으로 domain 집계 |
| DB 동기화 | `app/db/startup_cleanup/domain_code.py:34` | 시작 시 bulk sync |
| 대시보드 | `app/db/collection_dashboard.py:394,470,484,500,512,582,613` | `oi.domain_code` 7곳 |
| API | `app/api/owned_items.py:132,157,182` | `domain_code` 쿼리 파라미터 |
| 스키마 | `app/schemas.py` | `OwnedItemCreate.domain_code`, `OwnedItemListItem.domain_code` |
| UI | `app/static/index.html` | `editDomainCode` select + payload 포함 |
| 테스트 | `tests/test_db_split_phase_15.py:60` | `_sync_album_master_domain_code_in_conn` 존재 여부 테스트 |

**데이터 현황 (prod):**
- 마스터 없는 상품 중 domain_code 가진 것: **0건** → 안전
- 마스터-상품 domain_code 불일치: **215건** → 마이그레이션 후 master 기준 적용
- `am.domain_code` NULL: **1건** → 무시 가능

---

## File Map

| 파일 | 변경 내용 |
|------|-----------|
| `app/db/owned_item_query.py` | domain 필터를 am.domain_code JOIN으로 교체 |
| `app/db/owned_item_write.py` | domain_code write 제거, sync 호출 제거 |
| `app/db/album_master_core.py` | `_sync_album_master_domain_code_in_conn` — oi 의존 제거 |
| `app/db/startup_cleanup/domain_code.py` | bulk sync 함수 no-op으로 변경 |
| `app/db/collection_dashboard.py` | oi.domain_code → am.domain_code JOIN |
| `app/api/owned_items.py` | domain_code 쿼리 파라미터 — 쿼리 레이어로 위임 |
| `app/schemas.py` | OwnedItemCreate.domain_code deprecated |
| `app/static/index.html` | editDomainCode 제거, payload domain_code 제거 |
| `tests/test_db_split_phase_15.py` | sync 함수 존재 테스트 제거 |
| `tests/test_db_operator_catalog_search.py` | domain_code 테스트 — am 기준으로 업데이트 |

---

## Task 1: DB 쿼리 — `owned_item_query.py` domain 필터를 master JOIN으로 교체

**Files:**
- Modify: `app/db/owned_item_query.py:59,91-93,246,281-283`
- Test: `tests/test_db_operator_catalog_search.py`

`_build_owned_item_filter_sql`와 카운트용 동일 함수 내 domain_code 필터를 `oi.domain_code = ?` 에서 `am.domain_code` JOIN으로 변경한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_db_operator_catalog_search.py` 에 추가:

```python
def test_owned_item_domain_filter_uses_master_domain(tmp_path):
    """domain_code 필터가 am.domain_code 기준으로 동작해야 한다."""
    import sqlite3, os
    db_path = str(tmp_path / "library.db")
    os.environ["LIBRARY_DB_PATH"] = db_path
    from app.db.schema_migration import run_migrations
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    run_migrations(conn)

    # album_master: domain=WESTERN
    conn.execute("""INSERT INTO album_master (id, source_code, source_master_id, title,
        artist_or_brand, domain_code, release_year, raw_json, created_at, updated_at)
        VALUES (1,'DISCOGS','1','Test Album','Test Artist','WESTERN',2000,'{}',
        '2024-01-01T00:00:00Z','2024-01-01T00:00:00Z')""")
    # owned_item: domain=KOREA (intentionally wrong — master is authoritative)
    conn.execute("""INSERT INTO owned_item (id, label_id, category, size_group,
        preferred_storage_size_group, status, signature_type, domain_code, created_at, updated_at)
        VALUES (1,'TEST-001','LP','LP','LP','IN_COLLECTION','NONE','KOREA',
        '2024-01-01T00:00:00Z','2024-01-01T00:00:00Z')""")
    conn.execute("INSERT INTO album_master_member (album_master_id, owned_item_id) VALUES (1, 1)")
    conn.commit()
    conn.close()

    from app.db import list_owned_items
    # フィルタ WESTERN → should find item (master is WESTERN, even though oi.domain_code=KOREA)
    results_western = list_owned_items(
        domain_code="WESTERN", music_only=True, status=None,
        q=None, artist_or_brand=None, item_name=None, catalog_no=None,
        barcode=None, release_year=None, source_state="ANY", master_state="ANY",
        cover_state="ANY", slot_state="ANY", preferred_storage_state="ANY",
        track_state="ANY", media_format_state="ANY", size_group_state="ANY",
        release_type=None, category=None, sort="RECENT", limit=10, offset=0,
        include_total=False, signature_types=None,
    )
    assert len(results_western) == 1, f"WESTERN filter should return 1 item, got {len(results_western)}"

    # フィルタ KOREA → should NOT find item (master is WESTERN)
    results_korea = list_owned_items(
        domain_code="KOREA", music_only=True, status=None,
        q=None, artist_or_brand=None, item_name=None, catalog_no=None,
        barcode=None, release_year=None, source_state="ANY", master_state="ANY",
        cover_state="ANY", slot_state="ANY", preferred_storage_state="ANY",
        track_state="ANY", media_format_state="ANY", size_group_state="ANY",
        release_type=None, category=None, sort="RECENT", limit=10, offset=0,
        include_total=False, signature_types=None,
    )
    assert len(results_korea) == 0, f"KOREA filter should return 0 items, got {len(results_korea)}"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd /Volumes/Data/Works/07.hahahoho
python -m pytest tests/test_db_operator_catalog_search.py::test_owned_item_domain_filter_uses_master_domain -v
```

Expected: FAIL (현재 oi.domain_code 기준이라 반대 결과)

- [ ] **Step 3: `owned_item_query.py` domain 필터 교체**

`app/db/owned_item_query.py` 의 두 곳 (line 91-93, line 281-283) 모두 변경:

```python
# 기존:
if domain_code:
    query += " AND oi.domain_code = ?"
    params.append(domain_code)

# 변경 후:
if domain_code:
    query += """
      AND EXISTS (
        SELECT 1
        FROM album_master_member amm_d
        JOIN album_master am_d ON am_d.id = amm_d.album_master_id
        WHERE amm_d.owned_item_id = oi.id
          AND COALESCE(am_d.override_domain_code, am_d.domain_code) = ?
      )
    """
    params.append(domain_code)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_db_operator_catalog_search.py::test_owned_item_domain_filter_uses_master_domain -v
```

Expected: PASS

- [ ] **Step 5: 기존 관련 테스트 확인**

```bash
python -m pytest tests/test_db_operator_catalog_search.py -v --tb=short -q
```

Expected: 기존 테스트 통과 유지

- [ ] **Step 6: 커밋**

```bash
git add app/db/owned_item_query.py tests/test_db_operator_catalog_search.py
git commit -m "feat(domain): filter owned_items by album_master.domain_code via JOIN"
```

---

## Task 2: 대시보드 — `collection_dashboard.py` oi.domain_code → am.domain_code

**Files:**
- Modify: `app/db/collection_dashboard.py` (7곳)

대시보드 통계 쿼리에서 `oi.domain_code`를 `am.domain_code`(LEFT JOIN via album_master_member)로 교체한다. 마스터 없는 상품은 `'UNASSIGNED'`로 처리(기존 동일).

- [ ] **Step 1: 현재 쿼리 파악**

```bash
grep -n "oi\.domain_code" app/db/collection_dashboard.py
```

Expected: 7곳 표시

- [ ] **Step 2: JOIN 헬퍼 패턴 준비**

각 쿼리에 다음 패턴을 적용한다. 기존 `oi.domain_code`를 아래로 교체:

```sql
-- 기존:
COALESCE(NULLIF(oi.domain_code, ''), 'UNASSIGNED') AS domain

-- 변경 후 (쿼리에 LEFT JOIN album_master_member amm_d ON amm_d.owned_item_id = oi.id
--           LEFT JOIN album_master am_d ON am_d.id = amm_d.album_master_id 추가 필요):
COALESCE(NULLIF(COALESCE(am_d.override_domain_code, am_d.domain_code), ''), 
         NULLIF(oi.domain_code, ''), 'UNASSIGNED') AS domain
```

- [ ] **Step 3: 7곳 모두 교체**

각 SELECT 쿼리에서:
1. FROM 절 또는 기존 JOIN 뒤에 다음 추가:
   ```sql
   LEFT JOIN album_master_member amm_d ON amm_d.owned_item_id = oi.id
   LEFT JOIN album_master am_d ON am_d.id = amm_d.album_master_id
   ```
2. `oi.domain_code` 참조를 `COALESCE(am_d.override_domain_code, am_d.domain_code, oi.domain_code)` 로 교체

**Line 394** (단순 SELECT):
```sql
-- 기존: oi.domain_code,
-- 변경: COALESCE(am_d.override_domain_code, am_d.domain_code, oi.domain_code) AS domain_code,
```

**Line 470, 484, 500, 512, 582, 613** (COALESCE/GROUP BY 패턴):
```sql
-- 기존: COALESCE(NULLIF(oi.domain_code, ''), 'UNASSIGNED') AS domain
-- 변경: COALESCE(NULLIF(COALESCE(am_d.override_domain_code, am_d.domain_code, oi.domain_code), ''), 'UNASSIGNED') AS domain
```

- [ ] **Step 4: 구문 검사**

```bash
python3 -m py_compile app/db/collection_dashboard.py && echo OK
```

Expected: `OK`

- [ ] **Step 5: 커밋**

```bash
git add app/db/collection_dashboard.py
git commit -m "feat(domain): dashboard uses album_master.domain_code with oi fallback"
```

---

## Task 3: 쓰기 경로 — `owned_item_write.py` domain_code write 제거

**Files:**
- Modify: `app/db/owned_item_write.py`

CREATE/UPDATE 시 `owned_item.domain_code` 에 더 이상 쓰지 않는다. `_sync_album_master_domain_code_in_conn` 호출도 제거한다.

- [ ] **Step 1: INSERT 에서 domain_code 제거**

`app/db/owned_item_write.py` 의 INSERT SQL (line ~109):

```python
# 기존 (일부):
"""INSERT INTO owned_item (master_item_id, linked_album_master_id, linked_artist_name,
   copy_group_key, category, domain_code, release_type, ...) VALUES (?,?,?,?,?,?,?,...)"""

# 변경: domain_code 컬럼과 해당 ? 파라미터 제거
```

정확히 `domain_code`가 포함된 INSERT 컬럼 목록과 대응하는 params 값(`payload.get("domain_code")`) 줄을 제거.

- [ ] **Step 2: UPDATE 에서 domain_code = ? 제거**

line ~251:

```python
# 기존:
"""UPDATE owned_item SET ... domain_code = ?, ..."""

# 변경: domain_code = ? 줄 및 해당 파라미터 제거
```

- [ ] **Step 3: copy/bulk-update 경로에서 domain_code 제거**

line ~383, 407:
- `next_domain_code` 변수 계산 로직 제거
- `next_domain_code` 를 사용하는 조건문 및 파라미터 제거

- [ ] **Step 4: `_sync_album_master_domain_code_in_conn` 호출 제거**

line ~438-440:

```python
# 기존:
if domain_code is not None:
    if album_master_id:
        _sync_album_master_domain_code_in_conn(conn, album_master_id)

# 변경: 해당 블록 전체 제거
```

- [ ] **Step 5: 구문 검사**

```bash
python3 -m py_compile app/db/owned_item_write.py && echo OK
```

Expected: `OK`

- [ ] **Step 6: 커밋**

```bash
git add app/db/owned_item_write.py
git commit -m "feat(domain): stop writing oi.domain_code on create/update"
```

---

## Task 4: 동기화 함수 — `_sync_album_master_domain_code_in_conn` oi 의존 제거

**Files:**
- Modify: `app/db/album_master_core.py:151-193`
- Modify: `app/db/startup_cleanup/domain_code.py`

마스터 domain_code 동기화 함수가 더 이상 `oi.domain_code`를 읽지 않는다. 외부에서 `preferred_domain_code`를 직접 전달할 때만 업데이트한다. Startup bulk sync는 no-op으로 변경.

- [ ] **Step 1: `_sync_album_master_domain_code_in_conn` 수정**

```python
def _sync_album_master_domain_code_in_conn(
    conn: sqlite3.Connection,
    album_master_id: int,
    preferred_domain_code: str | None = None,
) -> str | None:
    master_id = int(album_master_id or 0)
    if master_id <= 0:
        return None
    master_row = conn.execute(
        "SELECT domain_code FROM album_master WHERE id = ? LIMIT 1",
        (master_id,),
    ).fetchone()
    if master_row is None:
        return None
    current_code = _normalize_domain_code_value(master_row["domain_code"])
    resolved_code = _normalize_domain_code_value(preferred_domain_code)
    # oi.domain_code 집계 제거: preferred가 없으면 현재 master domain 그대로 유지
    if not resolved_code:
        return current_code
    if resolved_code != current_code:
        conn.execute(
            "UPDATE album_master SET domain_code = ?, updated_at = ? WHERE id = ?",
            (resolved_code, utc_now_iso(), master_id),
        )
    return resolved_code
```

- [ ] **Step 2: startup bulk sync no-op으로 변경**

`app/db/startup_cleanup/domain_code.py`:

```python
def _sync_album_master_domain_from_owned_items(conn: sqlite3.Connection) -> None:
    """Deprecated: domain is now managed at album_master level directly."""
    return  # no-op
```

- [ ] **Step 3: 구문 검사**

```bash
python3 -m py_compile app/db/album_master_core.py app/db/startup_cleanup/domain_code.py && echo OK
```

Expected: `OK`

- [ ] **Step 4: 관련 테스트 수정**

`tests/test_db_split_phase_15.py:60-73` — `_sync_album_master_domain_code_in_conn` 존재 여부 테스트는 유지하되(함수 자체는 남아있음), oi에서 집계하는 동작 테스트가 있다면 삭제.

```bash
python -m pytest tests/test_db_split_phase_15.py -v --tb=short -q
```

Expected: 통과 (존재 여부 테스트만 남음)

- [ ] **Step 5: 커밋**

```bash
git add app/db/album_master_core.py app/db/startup_cleanup/domain_code.py tests/test_db_split_phase_15.py
git commit -m "feat(domain): sync func no longer reads oi.domain_code; startup bulk sync no-op"
```

---

## Task 5: API/스키마 — `OwnedItemCreate.domain_code` deprecated, 리스트 응답 갱신

**Files:**
- Modify: `app/schemas.py`
- Modify: `app/api/owned_items.py`

`OwnedItemCreate.domain_code`를 옵션 유지(하위 호환)하되 write에서 무시. `OwnedItemListItem.domain_code`는 master domain 우선으로 채운다.

- [ ] **Step 1: `OwnedItemListItem.domain_code` 소스 변경**

`app/api/owned_items.py` 의 `_to_owned_item_list_item` (line ~235):

```python
# 기존:
domain_code=_normalize_domain_code(row.get("domain_code") or row.get("master_domain_code")),

# 변경: master_domain_code 우선
domain_code=_normalize_domain_code(row.get("master_domain_code") or row.get("domain_code")),
```

`owned_item_query.py`의 SELECT에 `am.domain_code as master_domain_code`가 이미 있는지 확인:

```bash
grep -n "master_domain_code" app/db/owned_item_query.py | head -5
```

없으면 SELECT 절에 추가:
```sql
COALESCE(am.override_domain_code, am.domain_code) AS master_domain_code,
```
(owned_item_query의 JOIN에 album_master가 이미 있다면 해당 alias로 추가, 없으면 LEFT JOIN 추가)

- [ ] **Step 2: `OwnedItemCreate.domain_code` deprecated 주석 추가**

`app/schemas.py` 의 `OwnedItemCreate` (line 1045):

```python
# 기존:
domain_code: DomainCode | None = None

# 변경:
domain_code: DomainCode | None = None  # Deprecated: ignored on write; domain managed at album_master level
```

- [ ] **Step 3: 구문 검사**

```bash
python3 -m py_compile app/api/owned_items.py app/schemas.py && echo OK
```

Expected: `OK`

- [ ] **Step 4: 커밋**

```bash
git add app/api/owned_items.py app/schemas.py app/db/owned_item_query.py
git commit -m "feat(domain): OwnedItemListItem reads master domain; OwnedItemCreate.domain_code deprecated"
```

---

## Task 6: UI — `editDomainCode` 제거 및 페이로드 정리

**Files:**
- Modify: `app/static/index.html`

상품 편집 폼에서 도메인 선택 필드를 제거하고, 저장 페이로드에서 `domain_code` 를 제거한다. 읽기 표시(현재 도메인 표시 텍스트)는 마스터 도메인 기준으로 유지.

- [ ] **Step 1: `editDomainCode` HTML 제거**

line ~18349 의 도메인 select 래퍼 div 전체 삭제:

```html
<!-- 삭제 대상: -->
<div>
  <label for="editDomainCode" data-i18n="media.manage.product.field.domain_code.label">도메인</label>
  <select id="editDomainCode">
    <option value="" data-i18n="common.unspecified">미지정</option>
    <option value="KOREA" ...>가요</option>
    ...
  </select>
</div>
```

- [ ] **Step 2: 페이로드 `domain_code` 제거**

`buildHomeEditPayload()` 함수 (line ~50374):

```javascript
// 기존:
domain_code: $("editDomainCode").value || null,

// 변경: 해당 줄 삭제
```

`buildQuickCreatePayload()` 또는 기타 페이로드 빌더에서도 동일하게 제거 (line ~47506):

```javascript
// 기존:
domain_code: valueOf("editDomainCode").trim() || mappedDomain || null,

// 변경: 삭제
```

- [ ] **Step 3: `editDomainCode` 참조하는 JS 코드 정리**

다음 라인들 제거 또는 수정:
- `$("editDomainCode").value = "";` (line 47136) — 폼 초기화 시
- `$("editDomainCode").value = data.domain_code || "";` (line 50196) — 아이템 로드 시
- `if (mappedDomain) $("editDomainCode").value = mappedDomain;` (line 47429) — 소스 매핑 시

각각 해당 줄 삭제.

- [ ] **Step 4: 인라인 도메인 편집기 확인**

line ~35097 의 `mediaSearchInlineEditorDomainOptionsHtml(detail.domain_code)` 사용하는 인라인 편집기는 master correction 경로(마스터 메타 수정)이므로 유지. `detail.domain_code`는 이제 master domain에서 옴 → 별도 수정 불필요.

- [ ] **Step 5: 구문 확인**

```bash
python3 -m py_compile app/main.py && echo OK
```

Expected: `OK`

- [ ] **Step 6: 커밋**

```bash
git add app/static/index.html
git commit -m "feat(domain): remove editDomainCode field from item edit form"
```

---

## Task 7: 데이터 정합성 확인 및 prod 배포

**Files:**
- `deploy/scripts/deploy_to_prod.sh`

- [ ] **Step 1: 전체 테스트 실행**

```bash
cd /Volumes/Data/Works/07.hahahoho
python -m pytest --ignore=test_cloudflare.py --ignore=test_login.py --tb=short -q 2>&1 | tail -10
```

Expected: 기존 통과 테스트 유지 (domain 관련 실패 없음)

- [ ] **Step 2: prod DB 상태 확인**

```bash
ssh __PROD_HOST__ 'cd ~/apps/hahahoho-prod && .venv/bin/python3 -c "
import sqlite3
conn = sqlite3.connect(\"/Users/__PROD_USER__/apps/__PROJECT_SLUG__-prod/runtime/data/library.db\")
# am.domain_code 분포 확인
rows = conn.execute(\"SELECT domain_code, COUNT(*) FROM album_master GROUP BY domain_code ORDER BY COUNT(*) DESC\").fetchall()
for r in rows: print(r)
# am.domain_code NULL 마스터 확인
nulls = conn.execute(\"SELECT id, title FROM album_master WHERE domain_code IS NULL\").fetchall()
print(f\"domain NULL masters: {nulls}\")
conn.close()
"'
```

`domain_code IS NULL` 마스터가 있으면 직접 수정 후 진행.

- [ ] **Step 3: 상용 배포**

```bash
PROD_SSH_TARGET="__PROD_HOST__" PROD_APP_ROOT="/Users/__PROD_USER__/apps/__PROJECT_SLUG__-prod" \
  bash deploy/scripts/deploy_to_prod.sh 2>&1 | grep -E "^\[|Deploy complete|curl"
```

Expected: `Deploy complete: branch=...`

- [ ] **Step 4: 검증 체크리스트**

- [ ] 예외 큐 → MEDIA_MISSING → 도메인 "가요" 필터 → 7건 표시
- [ ] 예외 큐 → REVIEW_MISSING → 도메인 "팝/웨스턴" → 한국 앨범 없음
- [ ] 미디어>관리 → 상품 편집 폼에 도메인 필드 없음
- [ ] 대시보드 → 도메인별 통계 숫자 합리적 (LP/CD 도메인 분포)
- [ ] 상품 저장 후 도메인 변경 없음 (master 기준 유지)

---

## 자가 검토

### Spec 커버리지
- ✅ owned_item 도메인 필터 → master JOIN (Task 1)
- ✅ 대시보드 oi.domain_code 참조 제거 (Task 2)
- ✅ CREATE/UPDATE 쓰기 경로 domain_code 제거 (Task 3)
- ✅ sync 함수 oi 의존 제거 (Task 4)
- ✅ OwnedItemListItem domain 소스 변경 (Task 5)
- ✅ editDomainCode UI 제거 (Task 6)
- ✅ 배포 + 검증 (Task 7)

### 경계 조건
- **MASTER_MISSING 상품**: `oi.domain_code` 자체는 컬럼에 남아있으나 필터/표시에서 무시됨. 향후 마스터 생성 시 master domain으로 관리됨.
- **`_sync_album_master_domain_code_in_conn`**: 함수 자체는 유지(외부 코드에서 `preferred_domain_code` 직접 전달 용도), oi 집계 로직만 제거.
- **task 5의 SELECT**: `owned_item_query.py` JOIN 구조에 따라 `master_domain_code` alias 추가 방법이 달라질 수 있음 — 실행 시 확인 필요.
