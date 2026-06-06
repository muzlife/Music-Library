# 로깅 & 옵저버빌리티 설계

**날짜:** 2026-06-06  
**범위:** FastAPI + SQLite 기반 음반 라이브러리 관리 콘솔 (QA: Mac mini M4, Prod: Mac mini 2018)  
**방향:** 외부 서비스 없이 자체 구현 (Self-hosted, SQLite 저장, 카카오 알림)

---

## 개요

세 가지 문제를 해결한다:

1. **에러 알림** — 서버 오류 발생 시 뒤늦게 알게 되는 문제
2. **성능 추적** — API/배치/DB가 느려질 때 원인을 찾기 어려운 문제
3. **메타 변경 이력 보완** — 일부 이벤트와 album_master 필드 추적이 누락된 문제

모든 데이터는 기존 `library.db` SQLite 파일에 저장하며, 관리툴(index.html) "이력 & 로그" 탭에서 조회한다.

---

## 섹션 1: 에러 로그 & 알림

### 1-1. `error_log` 테이블

```sql
CREATE TABLE error_log (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  level        TEXT NOT NULL,          -- 'ERROR' | 'CRITICAL'
  source       TEXT,                   -- 'app/api/owned_items.py:save'
  message      TEXT NOT NULL,          -- 에러 메시지 요약 (첫 줄)
  traceback    TEXT,                   -- 전체 스택 트레이스
  request_path TEXT,                   -- 'POST /owned-items/1234'
  request_body TEXT,                   -- 요청 본문 (민감정보 제외, 최대 2KB)
  is_read      INTEGER NOT NULL DEFAULT 0,  -- 0=미확인, 1=확인
  created_at   TEXT NOT NULL
);
CREATE INDEX idx_error_log_created ON error_log (created_at DESC);
CREATE INDEX idx_error_log_is_read ON error_log (is_read, created_at DESC);
```

### 1-2. FastAPI 전역 예외 핸들러

- 위치: `app/main.py`
- `@app.exception_handler(Exception)` 등록
- 처리 흐름:
  1. `error_log` 테이블에 INSERT
  2. 카카오 알림 전송 (비동기, 실패해도 서버 영향 없음)
  3. HTTP 500 응답 반환
- 제외 대상: `HTTPException` (의도된 4xx 응답), `/health` 엔드포인트

### 1-3. 카카오 알림 — 나에게 보내기

**방식:** 카카오 메시지 API (나에게 보내기) — 무료, 사업자 등록 불필요

**준비 절차:**
1. [Kakao Developers](https://developers.kakao.com) 앱 등록 (REST API 키 발급)
2. OAuth 인증 1회 실행 → `refresh_token` 획득 (유효기간 2개월, 자동 갱신)
3. `.env.local`에 저장:
   ```
   KAKAO_REST_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   KAKAO_REFRESH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

**알림 메시지 형식:**
```
[hahahoho 에러 알림]
🔴 ERROR — 2026-06-06 10:23:44
경로: POST /owned-items/1234
내용: 'NoneType' object has no attribute 'get'
위치: app/api/owned_items.py:_save_owned_item_update
```

**토큰 자동 갱신:**
- access_token 만료 시 refresh_token으로 자동 갱신
- 갱신된 refresh_token은 `.env.local`에 덮어씀
- 갱신 실패 시 알림 전송만 스킵, 에러 로그 기록은 정상 유지

**카카오 알림 구현 위치:** `app/services/kakao_notify.py` (신규)

### 1-4. 관리툴 에러 배지 & 뷰어

**배지:**
- 페이지 로드 시 `GET /admin/error-log/unread-count` 호출
- 미확인 에러 수를 "이력 & 로그" 탭 버튼 옆에 빨간 숫자로 표시
- 탭 클릭 시 에러 섹션으로 자동 스크롤

**뷰어 (이력 & 로그 탭 ③ 에러 로그 섹션):**
- 목록: 시각, 경로, 메시지 요약, 확인 여부
- 클릭 → 상세 패널 (traceback 전체 표시)
- "전체 확인 처리" 버튼 → `POST /admin/error-log/acknowledge` → 배지 초기화

**API 엔드포인트 (app/api/activity_log.py에 추가):**
```
GET  /admin/error-log              — 목록 (is_read 필터, 페이지네이션)
GET  /admin/error-log/unread-count — 미확인 수
POST /admin/error-log/acknowledge  — 전체 또는 개별 확인 처리
```

---

## 섹션 2: 성능 로그

### 2-1. `perf_log` 테이블

```sql
CREATE TABLE perf_log (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  kind         TEXT NOT NULL,       -- 'API' | 'BATCH' | 'QUERY'
  name         TEXT NOT NULL,       -- 'GET /owned-items' | 'metadata_sync' | 'SELECT ...'
  duration_ms  INTEGER NOT NULL,    -- 소요 시간 (밀리초)
  is_slow      INTEGER NOT NULL,    -- 1=느림 기준 초과
  context_json TEXT,               -- 부가정보 JSON
  created_at   TEXT NOT NULL
);
CREATE INDEX idx_perf_log_kind_created ON perf_log (kind, created_at DESC);
CREATE INDEX idx_perf_log_slow ON perf_log (is_slow, created_at DESC);
```

**느림 기준:**

| kind | 기준 | 이유 |
|------|------|------|
| API | 300ms | 목표 응답 시간 |
| BATCH | 60,000ms (1분) | 정상 배치 기준 |
| QUERY | 200ms | SQLite 기준 |

**context_json 예시:**
```json
// API
{"status_code": 200, "user": "admin", "query_count": 12}

// BATCH
{"processed": 300, "success": 298, "fail": 2}

// QUERY (없음 — 쿼리 텍스트가 name에 포함됨)
```

### 2-2. API 응답 시간 — FastAPI 미들웨어

- 위치: `app/main.py` (`@app.middleware("http")`)
- 모든 요청의 시작/종료 시각 기록
- 제외: 정적 파일 (`/static/`), 헬스체크 (`/health`), SSE 스트림 (`/stream`)
- `perf_log` INSERT는 300ms 초과 시에만 (정상 요청은 기록 안 함 → DB 부하 방지)
- 에러 발생 요청은 항상 기록 (느린지 여부와 무관)

### 2-3. 배치 작업 시간 — 컨텍스트 매니저

위치: `app/services/perf_tracker.py` (신규)

```python
# 사용 예시
with perf_track("metadata_sync", kind="BATCH", context={"processed": count}):
    ...배치 처리...
# 블록 종료 시 자동으로 duration 계산 → perf_log INSERT
```

**적용 대상 (기존 워커 6개):**
- `metadata_sync` 워커
- `auto_backup` 워커
- `aladin_discogs_backfill` 워커
- `discogs_korean_backfill` 워커
- Spotify 배치 매칭 워커
- 예외 큐 자동 처리 워커

### 2-4. 느린 DB 쿼리 — execute() 래핑

- `set_trace_callback()`은 실행 전에만 호출되어 시간 측정 불가
- 대신 `app/db/__init__.py`의 `get_conn()` 반환 객체에서 `execute()`를 래핑
- `time.perf_counter()`로 시작/종료 측정 → 200ms 초과 시 `perf_log` INSERT
- 저장 시 쿼리 텍스트 앞 300자만 저장 (길이 제한)
- perf_log INSERT 쿼리 자체는 측정에서 제외 (재귀 방지)

### 2-5. 관리툴 성능 현황 섹션

"이력 & 로그" 탭 ④ 성능 현황:

```
필터: [전체 ▼]  기간: [오늘 ▼]  [조회]          느린 항목만 보기 [✓]
───────────────────────────────────────────────────────────────────
이름                         평균    최대    건수    느림
GET /owned-items             45ms   380ms   1,204    3건  [펼치기]
metadata_sync (BATCH)       38.2s   91.4s      24    2건  [펼치기]
SELECT owned_item... (DB)   340ms  820ms        8    8건  [펼치기]
───────────────────────────────────────────────────────────────────
```

**API 엔드포인트:**
```
GET /admin/perf-log          — 집계 목록 (kind/is_slow/기간 필터)
GET /admin/perf-log/detail   — 개별 기록 목록 (name 기준)
```

---

## 섹션 3: 메타 변경 이력 보완

### 3-1. 추가할 audit_log 액션 코드

| 액션 코드 | 발생 시점 | 추적 필드 |
|-----------|-----------|-----------|
| `CREATE` (owned_item) | 상품 신규 등록 | category, release_type, linked_artist_name, source_code |
| `CREATE` (album_master) | 마스터 신규 생성 | artist_or_brand, title, domain_code, release_year |
| `EXTERNAL_REF_UPDATE` | Discogs/ManiaDB ID 변경 | source, before_id, after_id |
| `IMAGE_UPLOAD` | 이미지 업로드 | filename, file_size_kb |
| `IMAGE_DELETE` | 이미지 삭제 | filename |
| `PURCHASE_IMPORT` | 구매 수입으로 상품 생성 | purchase_import_id, created_item_count |

### 3-2. album_master 필드 전체 추적

현재 일부 엔드포인트에서만 추적되는 album_master를 **모든 필드 변경** 시 추적한다.

**추적 대상 필드 (`_ALBUM_MASTER_AUDIT_FIELDS`):**

```python
_ALBUM_MASTER_AUDIT_FIELDS = (
    "artist_or_brand",        # 아티스트명
    "title",                  # 앨범명
    "catalog_no",             # 카탈로그 번호
    "barcode",                # 바코드
    "release_year",           # 발매연도
    "release_month",          # 발매월
    "label",                  # 레이블
    "domain_code",            # 도메인
    "genres",                 # 장르
    "styles",                 # 스타일
    "country",                # 국가
    "format_text",            # 포맷
    "sort_artist_name",       # 정렬 아티스트명
    "override_artist_or_brand",  # 교정 아티스트명
    "override_title",         # 교정 앨범명
    "override_note",          # 교정 메모
    "description",            # 설명
)
```

**적용 방식:** `owned_item`과 동일한 before/after diff 패턴
```python
_before = {f: existing_row.get(f) for f in _ALBUM_MASTER_AUDIT_FIELDS}
# ... 업데이트 실행 ...
_after = {f: updated_row.get(f) for f in _ALBUM_MASTER_AUDIT_FIELDS}
log_audit_event(entity_type="album_master", entity_id=id,
                action="UPDATE", changed_by=user,
                before=_before, after=_after)
# diff가 없으면 자동으로 기록 안 함
```

### 3-3. 한글 필드명 매핑 추가 (관리툴)

기존 `_AUDIT_FIELD_LABELS`에 album_master 필드 추가:

```javascript
artist_or_brand: "아티스트명",
title: "앨범명",
catalog_no: "카탈로그 번호",
barcode: "바코드",
release_month: "발매월",
label: "레이블",
country: "국가",
format_text: "포맷",
description: "설명",
```

---

## 전체 관리툴 이력 & 로그 탭 구성 (완성 후)

```
이력 & 로그 탭
  ① 메타 변경 이력   — audit_log  (전 이벤트, 한글 before/after)  [기존 + 보완]
  ② 장식장 이력      — owned_item_location_event                    [기존]
  ③ 에러 로그        — error_log  (스택 트레이스, 확인 처리)        [신규]
  ④ 성능 현황        — perf_log   (API/배치/DB 집계)                [신규]
  ⑤ 서버 로그        — 파일 tail  (stdout/stderr)                   [기존]
```

---

## 스키마 마이그레이션

- `SCHEMA_VERSION` 18로 증가
- `_migration_v18_add_observability_tables()`:
  - `error_log` 테이블 + 인덱스 생성
  - `perf_log` 테이블 + 인덱스 생성
  - 기존 테이블 변경 없음

---

## 구현 순서 (권장)

단계별로 독립적으로 배포 가능하다.

| 단계 | 내용 | 효과 |
|------|------|------|
| 1 | 스키마 마이그레이션 (v18) | error_log, perf_log 테이블 생성 |
| 2 | 에러 핸들러 + error_log 기록 | 에러 즉시 저장 시작 |
| 3 | 관리툴 에러 배지 + 뷰어 | 에러 확인 가능 |
| 4 | 카카오 알림 연동 | 실시간 모바일 알림 |
| 5 | API 성능 미들웨어 | API 느린 항목 추적 시작 |
| 6 | 배치 perf_track 래핑 | 배치 시간 추적 |
| 7 | SQLite 트레이스 | 느린 쿼리 추적 |
| 8 | 관리툴 성능 현황 탭 | 성능 현황 조회 |
| 9 | audit_log 보완 (CREATE, 외부ID, 이미지, 구매수입) | 누락 이벤트 커버 |
| 10 | album_master 전체 필드 추적 | 필드별 before/after 완성 |

---

## 환경변수 추가 목록

```bash
# 카카오 알림 (선택 — 미설정 시 알림 스킵)
KAKAO_REST_API_KEY=
KAKAO_REFRESH_TOKEN=

# 느림 기준 커스터마이징 (선택 — 미설정 시 기본값 사용)
PERF_SLOW_API_MS=300
PERF_SLOW_BATCH_MS=60000
PERF_SLOW_QUERY_MS=200
```

---

## 제외 범위

- 외부 로그 집계 서비스 (Loki, Elasticsearch 등) — 불필요
- 메트릭 대시보드 (Grafana, Prometheus 등) — 과함
- 로그 파일 로테이션 — launchd + macOS logrotate로 별도 처리 가능
- 실시간 스트리밍 알림 (WebSocket) — 배지 방식으로 충분
