# 구현 상태 검토 리포트

작성일: 2026-04-29  
대상: `app/` (FastAPI 백엔드 + 단일 페이지 프런트), `db.py`, `services/`, 운영 스크립트

## 0. 한눈에

| 영역 | 라인 수 | 상태 평가 |
| :-- | --: | :-- |
| `app/main.py` | 11,414 | 단일 모듈 비대화 — 라우터 분할 필요 |
| `app/db.py` | 10,867 | SQLite 스키마/마이그레이션이 한 파일에 누적됨 |
| `app/services/providers.py` | 3,442 | 외부 API 어댑터, 재시도/레이트리밋 부재 |
| `app/static/index.html` | 53,455 (CSS 16,915 / JS 32,464) | 모놀리스 SPA — 분할 시급 |
| 라우트 수 | 132개 | 도메인별 라우터 분리 권장 |
| 테스트 | 13개 파일 / 약 20k라인 | shell bootstrap 단일 파일에 12k 집중 |

전체 흐름은 운영자가 매뉴얼에서 약속한 대로 동작하도록 잘 짜여 있고, 인증/권한, 스키마 마이그레이션, 백업 자동화, QA 스모크까지 운영 관점이 들어가 있습니다. 다만 **단일 파일 비대화, 외부 API 견고성, 프런트 모놀리스, 시크릿 관리 위생, 일부 SQLite 트랜잭션 패턴**에서 우선순위 높은 정리 거리가 있습니다.

---

## 1. 오류 / 위험 (먼저 봐야 하는 항목)

### 1.1 [Critical] `.env.local`에 평문 운영 자격증명·실 토큰이 들어가 있음
- 파일이 작업 폴더에 그대로 존재합니다. `.gitignore`로 git 추적은 막혀 있지만, 디스크 자체는 평문이고 `Volumes/Works/...`는 외장/공유 마운트 가능성이 큽니다.
- 포함된 값: `DISCOGS_TOKEN`, `ALADIN_TTB_KEY`, `LIBRARY_AUTH_PASSWORD`, `LIBRARY_OPERATOR_PASSWORD`, `LIBRARY_OPERATOR_ACCOUNTS=…:평문비번`, `LIBRARY_AUTH_SESSION_SECRET`, `LIBRARY_PURCHASE_IMPORT_TOKEN`.
- 즉시 처리 권장
  1. 운영 토큰/비번을 모두 회전(rotation).
  2. macOS Keychain 또는 launchd `EnvironmentVariables` plist 사용으로 옮기고, 디스크 평문 파일은 운영기 권한 `chmod 600` + 소유자 제한.
  3. `LIBRARY_OPERATOR_ACCOUNTS`는 평문 비번을 ENV에 두는 구조 자체를 폐기하고, `auth_account` 테이블 + `pbkdf2_sha256` 해시(이미 `_hash_auth_password` 함수 존재)로 일원화.

### 1.2 [High] 평문/해시 인증이 ENV·DB에 혼재
- `_match_auth_account` (main.py 441~)이 ENV 평문과 DB 해시를 동시에 처리합니다. ENV 평문이 우선순위로 접근하면 DB 해시 정책의 보호 가치가 약화됩니다.
- 권장: ENV는 “부트스트랩 어드민 시드” 용도로만 1회 사용 → 부팅 시 해시로 DB에 입력 → ENV 변수는 바로 비워 둔다. 코드는 “DB 우선, 미존재시에만 ENV로 폴백”으로 정리.

### 1.3 [High] 외부 API 호출에 재시도/백오프/레이트리밋 처리 부재
- `services/providers.py` 전반: `httpx.Client(timeout=15.0)` 단발 호출, 429/5xx에 대한 재시도/백오프 없음. Discogs/MusicBrainz는 명시적 분당 요청 한도가 있어 메타동기화 워커가 한도에 닿으면 한꺼번에 실패합니다.
- 권장
  - 공용 `_fetch_json(url, ...)` 유틸에 `httpx.HTTPTransport(retries=...)` + 지수 백오프 + 429 헤더 `Retry-After` 존중.
  - `metadata_sync_batch_limit=300` 기본값과 함께 “초당 1건” 정도의 토큰 버킷.
  - 각 provider별 `User-Agent` 점검(현재 `your-email@example.com` placeholder가 살아있음 → Discogs/MusicBrainz 약관상 결격).

### 1.4 [High] DB 쓰기에 `BEGIN IMMEDIATE`가 없음 → SQLite WAL 동시쓰기 충돌 위험
- `get_conn`은 `journal_mode=WAL`만 켜고 트랜잭션 시작은 sqlite3 기본(implicit, deferred)에 의존합니다. 백업 워커, 메타동기화 워커, 사용자 요청이 동시에 INSERT/UPDATE를 치면 `database is locked`/`SQLITE_BUSY`가 잠깐 발생할 수 있습니다 (`SQLITE_BUSY_TIMEOUT_MS=30_000`로 완화는 됨).
- 권장: 쓰기가 큰 트랜잭션은 `conn.execute("BEGIN IMMEDIATE")` 후 마지막에 `commit()`. 백업/마이그레이션처럼 긴 트랜잭션은 별도 컨텍스트에서.

### 1.5 [High] 단일 파일 비대화 (`main.py` 11,414라인 / `db.py` 10,867라인)
- 132개 라우트가 한 모듈에 살고 있고, 보안/세션/구매수입/메타동기화/백업/CSV/Goods 등 도메인이 섞여 있어 변경 시 회귀가 큽니다.
- 권장 분할안 (예시)
  - `app/api/auth.py`, `app/api/owned_items.py`, `app/api/album_masters.py`, `app/api/purchase_import.py`, `app/api/ops.py`, `app/api/metadata_sync.py`
  - `app/db/schema.py` (테이블/인덱스), `app/db/migrations/000x_*.py`, `app/db/owned_items.py`, `app/db/album_master.py` …
  - 각 라우터를 `APIRouter`로 만들고 `main.py`는 `include_router`만.

### 1.6 [Medium] 마이그레이션이 “컬럼 존재 여부 분기 + ALTER” 누적식
- `_apply_migrations`가 60+개의 `if not _column_exists(...): ALTER TABLE …`로 구성됩니다. 시작 시간이 누적적으로 길어지고, 순서·롤백을 추적하기 어렵습니다.
- 권장: `PRAGMA user_version`을 도입해 “버전 N → N+1” 함수 리스트를 한 줄로 적용. 새 마이그레이션을 추가하면 자동으로 버전이 올라가고 이미 적용된 머신에서는 스킵.

### 1.7 [Medium] 프런트가 단일 53k라인 HTML
- `<style>` 16k줄 + `<script>` 32k줄 + 200곳 넘는 `innerHTML = …` 패턴.
- `escapeHtml`이 1회 정의돼 855곳에서 호출되고 있는 것은 좋은 시도지만, 기본 사용을 `innerHTML` 대신 `textContent` / DOM 빌더 / 가벼운 `tagged template`로 옮기면 회귀 안전성이 훨씬 올라갑니다.
- 1차 권장
  - `static/index.html`을 `index.html` + `app.css` + `app.js` 분리.
  - 이후 도메인 단위로 `dashboard.js`, `ops_home.js`, `register.js`, `master_workbench.js`로 쪼개기 (모듈 ESM, `<script type="module">`).
  - 빌드 도구(esbuild/Vite) 도입은 부담스러우면 ESM 직접 import만으로도 충분.

### 1.8 [Medium] 1,810개 함수/람다 + 1,779회 `t("…")` 호출 = i18n 키가 코드에 흩어져 있음
- 키 충돌, 미사용 키, 누락 키 추적이 사실상 수동.
- 권장: `messages.ko.json`, `messages.en.json` 분리 + 빌드 시 “선언만 되고 사용 안 된 키” 검사 스크립트.

### 1.9 [Medium] `_purchase_html_from_raw_content` 등에서 `BeautifulSoup(...)`만 사용
- `_purchase_extract_amazon_detail_enrichment`/`_purchase_extract_ebay_detail_enrichment`는 외부 페이지를 직접 fetch + 파싱. Amazon/eBay는 봇 감지/HTML 구조 변경 빈도가 높아 “조용한 실패”로 빈 결과를 줄 수 있습니다.
- 권장
  - 응답 status, 길이, 핵심 셀렉터 hit 여부를 메타로 남겨서 “파싱 실패가 잦은 vendor”를 가시화.
  - 사용자 정의 가능한 `Cookie/User-Agent` 풀로 분기.

### 1.10 [Low] 주요 쿼리 컬럼에 인덱스 누락 가능성
- 자주 보이는 `WHERE storage_slot_id IN (...)`, `WHERE status = 'IN_COLLECTION'` 패턴인데, `owned_item.storage_slot_id`, `owned_item.status` 단독 인덱스가 보이지 않습니다. (`idx_owned_item_category_created_id` 등 복합은 있음)
- 데이터가 충분히 쌓인 환경에서 EXPLAIN으로 실측 후, 필요시 `CREATE INDEX idx_owned_item_status_slot ON owned_item(status, storage_slot_id)` 정도 추가 검토.

### 1.11 [Low] `try: … except Exception:` 폭넓게 38회 (main.py 기준)
- 주로 외부 입력/파일 처리 방어인 것은 이해되나, 일부는 “예외를 삼킨 뒤 None 반환”이라 디버깅 시 흔적이 사라집니다.
- 권장: `logger.exception(...)`로 흔적이라도 남기고 운영 화면(`/system/status`)에서 최근 N건 보일 수 있게 카운터/링버퍼.

### 1.12 [Low] 하드코딩된 `/Volumes/Works/07.hahahoho/...` 경로
- `main.py` 327~335에 9개의 절대경로 상수. 운영기·QA기 양쪽에서 그대로 쓰면 충돌합니다.
- 권장: `Path(__file__).resolve().parents[1]` 기준으로 상대경로화 + 운영기에서는 `LIBRARY_PROJECT_ROOT` ENV로 override.

### 1.13 [Low] `webhook/gmail`이 `auth_guard`의 allowed_paths에 직접 박혀 있음
- 토큰 비교는 `secrets.compare_digest`로 잘 하고 있습니다. 추가로 `Content-Type` allow-list, body 사이즈 상한, 중복 webhook 식별자(`source_ref` 기반 dedupe) 정도가 빠져 있습니다.

---

## 2. 최적화 거리

### 2.1 메타데이터 동기화 워커
- 현재 `threading.Thread` + `Event`. async/await로 옮기면 외부 API I/O 동시성을 안전하게 올릴 수 있고, 같은 이벤트 루프에서 `httpx.AsyncClient` 한 개로 connection pool을 공유 가능.
- 또는 단순화: `asyncio.create_task` 대신 별도 OS 프로세스(launchd) + cron-style. 이미 launchd 인프라가 있으니 워커를 앱 외부로 빼는 것이 깨지기 쉬운 “shutdown 시 thread 정리”에서 자유로워집니다.

### 2.2 Discogs/MusicBrainz/ManiaDB 응답 캐시
- 같은 release/master에 대해 같은 응답을 다시 가져오는 경우가 많음(`master_cache`/`detail_cache` dict가 일부 함수에 있긴 함).
- 권장: 결과 JSON을 `data/external_cache/<source>/<id>.json` 로 디스크 캐시 + `If-Modified-Since` 또는 `etag` 비교. SQLite의 `metadata_source_snapshot` 테이블이 이미 있다면 그쪽에 통일.

### 2.3 SQLite `PRAGMA`
- `journal_mode=WAL`, `synchronous=NORMAL`, `foreign_keys=ON` 적용 양호.
- 추가 검토
  - `PRAGMA temp_store=MEMORY`
  - `PRAGMA mmap_size=268435456` (256MB) — 읽기 많은 검색 화면에서 체감.
  - `PRAGMA cache_size=-65536` (64MB)
  - 대량 INSERT 경로(CSV ingest, bulk update)는 한 트랜잭션 안에 묶고 `executemany`.

### 2.4 프런트 “초기 로드” 최적화
- 53k 라인 HTML을 매 페이지에서 다시 파싱합니다.
- 단순한 1차 개선: `<style>`/`<script>`를 `app.css`/`app.js`로 분리만 해도 브라우저 캐시가 듣고 매번 16k+32k 다시 받지 않게 됩니다 (`HTML_NO_CACHE_HEADERS`로 HTML 자체는 매번 새로, JS/CSS는 fingerprint URL로 장기 캐시).
- 그 다음 단계로 화면 단위 lazy load.

### 2.5 라우트별 응답 모델 정합성
- `schemas.py`만 1,770라인 — Pydantic 모델은 잘 짜여 있는 편. 다만 `purchase_import` 부근 응답 모델 일부가 `Any`로 남아 있는지 확인 권장(메일 본문 파싱 결과). 운영에서 필드 추가될 때 `extra="forbid"`보다 `extra="ignore"` 쪽이 호환성이 좋음.

### 2.6 `goods_item` 검색 쿼리
- `idx_goods_item_artist_map_lookup`, `idx_goods_item_label_map_lookup`이 있는데, 검색은 정규화된 LOWER/CASEFOLD 텍스트와 부분일치(`LIKE %x%`)일 가능성이 큽니다. 부분일치는 인덱스를 못 탑니다.
- 권장: 자주 쓰는 검색어 prefix 인덱스(`LIKE 'x%'`만 인덱스 탐 — `COLLATE NOCASE`)이거나, 데이터 규모가 더 커지면 SQLite FTS5 가상 테이블 도입.

### 2.7 백업
- `deploy/scripts/backup_*.sh`가 잘 갖춰진 편. 다만 “백업 결과를 DB의 `app_setting`에 기록” 흐름과 “외부 mirror(Drive/GCS)” 흐름이 두 갈래로 분리돼 있어, 한쪽 실패가 다른 쪽 상태에 반영되지 않을 수 있음 → `backup_ops.py`에서 결과 코드를 통일해 `auto_backup_last_error`까지 합쳐 기록.

---

## 3. 개선 지점 의견 (우선순위 제안)

> 한 번에 다 하지 말고 “보안 → 견고성 → 구조”순으로 진행하는 것을 권장합니다.

**1주차 (보안/위생)**
- `.env.local` 평문 자격증명 회전 + Keychain/launchd plist 이전.
- 모든 운영자 계정을 `auth_account` 테이블로 이관, ENV는 부트스트랩 1회 시드.
- `_purchase_import_webhook_allowed`에 사이즈/Content-Type/dedupe 추가.

**2~3주차 (런타임 견고성)**
- `services/providers.py`에 공용 retry/backoff/rate-limit + Discogs/MusicBrainz `User-Agent` 정정.
- 외부 응답 디스크 캐시(또는 `metadata_source_snapshot` 활용).
- 큰 쓰기 경로에 `BEGIN IMMEDIATE` 도입, executemany로 CSV ingest 최적화.

**4~6주차 (구조 정리)**
- `main.py`를 `app/api/*`로 도메인별 분리(`APIRouter`), 동시에 절대경로 상수를 `paths.py`로 모으고 root 기반 상대경로화.
- `db.py`를 `app/db/{schema, migrations, owned_items, album_master, purchase_import, …}`으로 분리 + `PRAGMA user_version` 기반 마이그레이션 매니저.
- 마이그레이션 정리 끝나면 `tests/test_ops_route_access.py` (4,340라인) / `tests/test_ops_shell_bootstrap.py` (12,409라인)도 도메인 단위 분할.

**6주차+ (프런트)**
- `index.html`에서 CSS/JS 분리 → ESM 모듈 단위 분할(대시보드/운영홈/검색관리/등록수집/운영연계).
- `innerHTML`/문자열 결합을 줄이고 가벼운 `html\`...\`` tagged template + `escapeHtml` 디폴트 패턴으로 통일.
- i18n 키를 외부 JSON으로 분리하고 미사용 키 검사 추가.

---

## 4. 잘 되어 있는 점 (유지 권장)

- **운영 매뉴얼/ERD/QA 시트가 한 묶음으로 관리**되고 있고, README가 각 문서로 직접 링크합니다. 이게 코드 리뷰만으론 못 찾는 운영 정보를 빠르게 잡아줍니다.
- **인증 쿠키**가 `hmac-sha256` 서명 + 만료 검증 + `pbkdf2_sha256` 해시 지원으로 기본기가 잡혀 있고, `secrets.compare_digest` 사용도 일관됩니다.
- **마이그레이션이 idempotent** 하게 짜여 있어 재시작에 안전합니다 (`IF NOT EXISTS`, `_column_exists`).
- **백업 launchd 자동화 + 운영/QA 분리**가 deploy 스크립트 수준에서 되어 있고, `qa_master_sheet.csv`로 회귀 증적이 한 곳에 모입니다.
- **프런트 `escapeHtml` 사용 빈도가 높음** — XSS 표면이 작은 편(완전하진 않지만, 라이브러리 없는 vanilla 환경 치고 잘 통제됨).

---

## 5. 빠른 액션 체크리스트 (복붙용)

```
[ ] DISCOGS_TOKEN, ALADIN_TTB_KEY 회전
[ ] LIBRARY_AUTH_PASSWORD, LIBRARY_OPERATOR_PASSWORD, LIBRARY_OPERATOR_ACCOUNTS 모두 회전
[ ] LIBRARY_AUTH_SESSION_SECRET 회전 + .env.local 권한 chmod 600
[ ] 모든 운영자 계정을 DB(auth_account)로 이관 + ENV는 시드 전용
[ ] services/providers.py: 429/5xx retry+backoff, Retry-After 존중, User-Agent placeholder 제거
[ ] sqlite write 경로에 BEGIN IMMEDIATE 도입(특히 album_master merge, purchase_import insert)
[ ] PRAGMA user_version 기반 마이그레이션 매니저로 _apply_migrations 정리
[ ] main.py 라우트를 app/api/*로 분리(우선 auth, owned_items, album_masters, purchase_import)
[ ] static/index.html → index.html + app.css + app.js 분리, JS는 ESM 모듈로 도메인별 분할
[ ] /Volumes/Works/07.hahahoho 하드코딩 경로를 LIBRARY_PROJECT_ROOT로 추상화
[ ] webhook/gmail에 size limit + Content-Type + source_ref 기반 dedupe
```
