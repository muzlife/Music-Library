# 저장소 감사 및 개선 계획 (Repo Audit & Improvement Plan)

작성일: 2026-06-10
대상: `/Volumes/Data/Works/07.hahahoho` (외장 디스크 개발 원본 기준)
방법: 코드 정독 + 패턴 검색. **코드는 일절 수정하지 않음.** 모든 지적은 `파일:라인`으로 근거를 명시했고, 검증 불가한 항목은 그렇게 표기함.

> 참고: 2026-04-29 코드 리뷰(`docs/code_review_2026-04-29.md`)의 후속 점검을 겸한다. 당시 지적 중 라우터 분할, db.py 패키지화, 외부 API 재시도/백오프, `BEGIN IMMEDIATE` 도입은 **실제로 이행됐다.** 이번 감사는 "그 다음에 남은 것"에 집중한다.

---

## 1. Executive Summary

종합 등급: **C+** — 단일 운영자 내부 도구로서는 잘 작동하고 운영 문서·텔레메트리·백업 체계가 이례적으로 충실하지만, 검색 핵심 경로에 실제 동작 버그가 있고, 세션/시크릿 수명주기가 인증 암호화 수준을 따라가지 못하며, 두 개의 모놀리스(main.py 7,765줄, index.html 62,176줄)가 모든 변경의 회귀 위험을 키우고 있다. 테스트 77개 파일은 강점이나 CI/린트가 전혀 없어 품질이 "자발성"에만 의존한다.

**Top 3 리스크**
1. 검색 필터 버그 — 수록곡 보유("HAS") 필터가 특정 조합에서 조용히 무시됨 (`app/db/owned_item_query.py:234`, `:445`). 운영자가 틀린 결과를 보고 데이터 정리를 진행할 수 있음.
2. 세션·시크릿 수명주기 — 세션 시크릿의 하드코딩 기본값(`app/config.py:140`), 로그인 무제한 시도 허용(`app/api/auth.py:91`), 14일간 폐기 불가능한 역할 내장 쿠키(`app/security.py:230-256`). Cloudflare로 외부 노출된 상용 도메인 기준으로 실질 위협.
3. 강제 장치 부재 — CI·린터·포매터 설정이 저장소에 없음. 중복 상수가 이미 서로 다른 값으로 드리프트됨(`app/main.py:212-213` vs `app/db/__init__.py:18-25`).

**Top 3 기회**
1. 퀵윈 7건(아래 §5.4)은 합쳐서 반나절이면 끝나고 그중 2건은 실사용 버그 수정이다.
2. list/count 중복 400줄을 공용 필터 빌더로 합치면 버그 1번이 구조적으로 재발 불가능해진다.
3. pytest+ruff를 도는 최소 CI 하나만 세워도 이 프로젝트의 가장 큰 메타 리스크(아무것도 강제되지 않음)가 해소된다.

---

## 2. Repo Map

**목적**: 음반/굿즈 약 3만 점의 카탈로그·메타 보강·장식장 배치·카페 신청곡 운영을 담는 FastAPI 기반 운영 콘솔. 단일 운영자(+카페 스태프/태블릿) 내부 도구이며, Mac mini 2대(상용 8000/QA 8100) + Cloudflare 터널로 서비스. 성숙도: **운영 중인 내부 프로덕션** (go-live 체크리스트, QA 시트, 런북 보유).

**스택**: Python 3.12 · FastAPI 0.115.6 · Uvicorn · SQLite(WAL) · Pydantic 2 · httpx · pytest. 프런트는 빌드 도구 없는 정적 HTML(바닐라 JS).

**아키텍처 흐름**: `app/main.py`(앱 생성, 미들웨어, 백그라운드 워커, 거대 헬퍼층) → `app/api/*` 19개 도메인 라우터 → `app/db/*` 40여 개 모듈(읽기/쓰기/쿼리 분리, `__init__.py`가 재수출 허브) → SQLite `library.db`. 외부 연동은 `app/services/providers.py`(Discogs/ManiaDB/Aladin/MusicBrainz)와 `spotify.py`, `kakao_notify.py`, `deepseek_client.py`.

| 경로 | 설명 |
|---|---|
| `app/main.py` (7,765줄) | 앱 진입점 + 미들웨어 + 워커 + 구매메일 파싱/ONVIF 카메라/날씨/백업/Discogs 매핑 헬퍼 ~250개 |
| `app/api/` (19모듈, ~9,000줄) | 도메인 라우터. 다수가 `_main()` 지연 접근자로 main.py 헬퍼를 역참조 |
| `app/db/` (40+모듈, ~20,000줄) | DB 계층. `schema_migration.py`(1,723줄)가 `PRAGMA user_version` 기반 마이그레이션 관리 |
| `app/services/` | providers.py(5,191줄), artist_context, spotify(spotipy), image_store 등 |
| `app/static/index.html` (**62,176줄**) | 관리 콘솔 SPA 전체 — CSS 22,884줄 + 단일 `<script>`에 JS 약 39,000줄 |
| `tests/` (77파일) | conftest가 임시 DB로 격리. 단, 39개 파일은 모듈 분할 구조를 고정하는 "split phase" 테스트 |
| `docs/` | 운영 매뉴얼, ERD, 런북, QA 시트, 날짜별 설계/계획 기록 — 매우 충실 |
| `scripts/`, `deploy/`, `mcp-deepseek/` | QA/배포 스크립트, launchd plist, DeepSeek MCP 서버 |

**놀란 점**: ① 2026-04-29 리뷰 권고가 대부분 실제 이행됨(드문 일). ② 그런데 index.html은 같은 기간 53k → 62k줄로 오히려 9천 줄 성장. ③ 작업 폴더에 `.env.local.bak.20260527_1503`(시크릿 백업 사본), 루트 `library.db`, `data/*.db` + 백업 9개, `.worktrees/` 9개, venv 2개가 쌓여 있음 — 이번 감사 중 샌드박스가 "디스크 공간 부족"으로 부팅 실패했을 정도의 디스크 압박.

---

## 3. Audit Report

표기: [사실] = 코드로 확인된 사실 / [판단] = 정황 기반 판단.

### 3.1 Critical

**C1. 세션 시크릿 기본값 폴백** — [사실] `app/config.py:140`이 `LIBRARY_AUTH_SESSION_SECRET` 미설정 시 `"change-this-library-session-secret"`을 그대로 사용한다. 쿠키는 이 시크릿의 HMAC 서명만으로 신뢰되므로(`app/security.py:210-256`), 기본값으로 뜬 서버에서는 누구나 ADMIN 쿠키를 위조할 수 있다. [판단] `.env.local`이 존재하므로 현재 머신들은 설정돼 있을 가능성이 높지만, 새 머신 이전·복구 시 조용히 기본값으로 떨어지는 구조 자체가 지뢰다. 시크릿 미설정 시 **기동 거부(fail-fast)** 가 맞다.

**C2. 시크릿 평문 사본 방치 + 운영자 등급 유출 경로** — [사실] 작업 폴더에 `.env.local`과 그 백업 `.env.local.bak.20260527_1503`이 존재한다. 04-29 리뷰가 이미 "전체 회전 + Keychain 이전"을 Critical로 요구했는데(`docs/code_review_2026-04-29.md:23-29`) `.bak` 사본이 그 뒤(5/27)에 새로 생겼다. 또한 `/ops/export/full-backup?include_env_file=true`가 **OPERATOR 권한만으로** `.env` 포함 전체 백업 다운로드를 허용하고(`app/api/ops_system.py:121-135`), `/ops/provider-settings` POST 역시 OPERATOR가 API 키를 `.env.local`에 기록할 수 있다(`app/api/ops_system.py:176-207`). 시크릿 열람·변경은 ADMIN 전용이어야 한다.

### 3.2 High

**H1. 검색 필터 정합성 버그 (`elif` 체인 오접합)** — [사실] `app/db/owned_item_query.py:221-240`에서 `track_state == "HAS"` 조건이 `size_group_state`의 `if/elif` 체인에 `elif`로 붙어 있다. 즉 size_group 필터(MATCH/MISMATCH)를 함께 선택하면 "수록곡 있음" 필터가 **조용히 무시**된다. `count_owned_items`에도 동일 코드가 복붙돼 있다(`:432-451`). 반면 `track_state == "MISSING"`은 독립 `if`(`:192-201`)라서 정상 동작 — 비대칭이 버그임을 방증한다. 핵심 검색 화면의 결과/카운트가 모두 틀어진다.

**H2. 로그인 무제한 시도** — [사실] `/auth/login`(`app/api/auth.py:91-124`)에 레이트리밋·계정 잠금·지연이 전혀 없다. PBKDF2 200k 반복(`app/security.py:52`)은 시도당 CPU 비용이 커서 무차별 대입을 늦추는 동시에, 역으로 로그인 엔드포인트 자체가 CPU DoS 표적이 된다. 외부 노출 도메인 기준 High.

**H3. 14일짜리 폐기 불가 역할 쿠키** — [사실] 쿠키 페이로드의 `role`이 `_ALL_ROLES`에 속하기만 하면 DB 조회 없이 그대로 신뢰된다(`app/security.py:244-256`). 계정 비활성화·강등·비밀번호 변경을 해도 기존 쿠키는 만료(14일, `security.py:41`)까지 유효하다. 세션 무효화 수단이 없다.

**H4. main.py 갓 모듈 + 역방향 의존** — [사실] 라우트는 2개만 남았지만(`app/main.py:3559`, `:3584`) 구매메일 파싱(약 1,200~2,400행대), ONVIF 카메라 SOAP(3,700~4,060), 날씨/Home Assistant(4,281~4,427), Discogs 응답 매핑(5,873~6,284), 백업/복구, 워커 4종이 한 모듈에 산다. 게다가 api 모듈이 `_main()` 지연 접근자로 main의 비공개 헬퍼를 역참조한다(`app/api/ops_system.py:128, 147, 157, 200`). 라우터 분할은 끝났지만 **서비스 분할은 안 된 상태** — main.py가 사실상 공유 라이브러리 역할이라 어떤 변경이든 7,700줄 모듈을 통과한다.

**H5. index.html 62,176줄 단일 파일** — [사실] CSS 22,884줄 + 22,885행에서 시작하는 단일 `<script>` 블록에 JS 약 39,000줄. 04-29 리뷰가 "분할 시급"으로 지적(`code_review_2026-04-29.md:57-63`)했으나 이후 9천 줄 더 성장했다. diff 리뷰·부분 캐싱·동시 작업이 모두 불가능하고, 프런트 회귀가 테스트 사각지대(프런트 테스트 0)에 있다.

### 3.3 Medium

**M1. 도메인 코드 상수 드리프트(데이터 정합성)** — [사실] `app/main.py:212-213`은 `DOMAIN_CODES`에 `WORLD`가 없고 `LEGACY_DOMAIN_CODE_MAP`이 `"OTHER"→"WORLD_OTHER"`인 반면, `app/db/__init__.py:18-25`는 `WORLD`/`WORLD_OTHER` 둘 다 두고 `"OTHER"→"WORLD"`로 매핑한다. **같은 레거시 값이 경로에 따라 다른 정규값으로 변환**된다. `LABEL_PREFIX_BY_CATEGORY`도 양쪽에 중복(`main.py:216-230`, `db/__init__.py:26-40`).

**M2. list/count 400줄 복제** — [사실] `owned_item_query.py:57-263`과 `:266-455`가 WHERE 빌더를 통째로 복제한다. H1 버그가 양쪽에 동일하게 존재하는 것 자체가 복제 비용의 증거이며, 한쪽만 고치면 목록과 카운트가 어긋난다.

**M3. async 경로의 블로킹 호출** — [사실] `app/api/cafe.py`의 `async def cafe_request_track`이 동기 SQLite 쓰기를 이벤트 루프에서 직접 호출한다(`cafe.py:257-274`; busy_timeout 최대 30초 = `app/db/connection.py:20`). `_now_playing_worker`도 `_local.current_track()`(VLC 소켓)을 루프에서 직접 호출(`cafe.py:121`) — Spotify 호출만 executor로 빼고(`:126`) 로컬 체크는 안 뺐다. SSE/WebSocket을 같은 루프에서 서비스하므로 DB 락 한 번이 카페 태블릿 전체 실시간성을 멈출 수 있다.

**M4. 공개 `/cafe/search`의 Spotify 프록시** — [사실] auth_guard 허용 목록에 포함(`app/main.py:542`)되어 무인증으로 Spotify 검색을 호출하며(`cafe.py:193-213`) 레이트리밋이 없다. 외부 도메인에서 두드리면 Spotify 쿼터 소진 가능. [판단] 태블릿 UX상 공개가 필요하면 디바이스 헤더 검증 또는 IP 제한이 타협안.

**M5. 평문 비밀번호 하위호환** — [사실] `app/security.py:66-69`가 `pbkdf2_sha256$` 접두사가 없는 저장값을 평문 비교로 통과시킨다. [판단] 마이그레이션 완료 후 제거하거나, 로그인 성공 시 즉시 재해시하는 코드가 없어 영구 잔존 위험.

**M6. 스키마 DDL 이중 정의** — [사실] 동일 인덱스 DDL이 `schema_migration.py`와 `db/__init__.py:1399-1437`에 각각 존재하고, `schema_migration.py` 안에서도 중복(예: `idx_goods_item_collectible_relation_*`이 `:1542-1543`과 `:1671-1672` 두 번). 드리프트와 "어느 쪽이 진실인가" 혼란의 원천.

**M7. 중복 라우트 등록** — [사실] `GET /cafe/tags`가 동일 본문으로 두 번 정의됨(`app/api/cafe.py:175-179`, `:184-188`). 동작 무해하나 복붙 사고의 흔적.

**M8. 의존성 명세 불완전** — [사실] `app/services/spotify.py:41`이 `spotipy`를 임포트하지만 `requirements.txt`(8줄)에 없다. `.venv`에는 playwright·requests·websocket-client 등 미명세 패키지 다수. 새 머신 배포 시 Spotify 기능이 조용히 죽는다(지연 임포트라 기동은 됨). 락파일 없음.

**M9. 검색 성능: LIKE 풀스캔** — [사실] 주요 텍스트 필터가 전부 `LOWER(...) LIKE '%…%'`(`owned_item_query.py:113-146`)로 인덱스 불가. [판단] 3만 행이면 보통 수백 ms 이내지만 목표(검색 <500ms)는 `perf_log`로 실측 확인 필요 — 단정하지 않음. FTS5 도입은 측정 후 결정.

**M10. CI/린트/포맷 부재** — [사실] `.github/`, `pyproject.toml`, lint 설정이 저장소에 없다. 77개 테스트 파일이 있어도 실행을 강제하는 장치가 없다.

**M11. 복구와 동시 쓰기 경합** — [사실] DB 복구는 메타동기화 락만 확인하고(`app/main.py:3395`) 자동백업 워커·진행 중 요청과의 배타는 없다. 복구 직전 백업을 만들기는 함(`:3425`).

### 3.4 Low

- **L1.** `.env.example:6`은 `DB_PATH`를 안내하지만 코드는 `LIBRARY_DB_PATH`를 읽는다(`app/config.py:92`). 문서대로 설정하면 무시됨.
- **L2.** 로그인 페이지 로고 깨짐: `login.html:666`이 `/ui-static/images/...`를 참조하나 auth_guard 허용 목록(`app/main.py:534-553`)에 `/ui-static`이 없어 미인증 상태에서 401.
- **L3.** 성능 미들웨어 스킵 목록의 `"/static/"`(`app/main.py:493`)은 존재하지 않는 경로 — 실제 마운트는 `/ui-static`(`:367`).
- **L4.** 작업 폴더 위생: `.worktrees/` 9개, venv 2개, 루트 `library.db`, `data/` DB 사본·백업 9개, `.env.local.bak`. (이번 감사 중 디스크 부족 실증.)
- **L5.** "split phase" 테스트 39개 파일은 행위가 아니라 모듈 표면(재수출 구조)을 고정한다(예: `tests/test_db_split_phase_20.py:40-60`). 리팩토링 완료 후엔 구조 변경을 막는 족쇄가 됨.
- **L6.** providers의 일부 호출이 공용 재시도 헬퍼를 우회한다(`providers.py:1586`, `:1616` raw `httpx.get`; `:1499` urllib).
- **L7.** `except Exception` 174회 중 bare-pass 41회. 텔레메트리 자체 보호(`connection.py:50-51`, `main.py:474-488`)는 타당하나, 비즈니스 경로 일부(`api/owned_items.py` 4건 등)는 흔적 없이 삼킨다.

### 3.5 잘 하고 있는 것 (보존할 것)

- **쓰기 트랜잭션 규율**: `BEGIN IMMEDIATE` 전용 컨텍스트 + WAL + busy_timeout, 의도를 설명하는 독스트링까지 (`app/db/connection.py:98-142`).
- **버전 기반 마이그레이션**: `PRAGMA user_version` + 레거시 폴백 (`schema_migration.py:535-548`, `:1148-1165`).
- **외부 API 견고성**: Retry-After 존중·지수 백오프·env 튜닝 가능한 공용 재시도층 (`providers.py:35-186`).
- **복구 안전장치**: zip-slip 검증, 복구 전 자동 백업, 스테이징 후 원자적 교체 (`main.py:3406-3435`).
- **인증 암호 원시 요소**: PBKDF2 200k, HMAC 쿠키, `compare_digest` 일관 사용 (`security.py`).
- **자가 텔레메트리**: 느린 쿼리/API 자동 기록, 에러 로그 테이블 + Kakao 알림 (`connection.py:25-53`, `main.py:435-525`).
- **테스트 격리**: conftest가 임시 DB·테스트 계정·시크릿을 세팅 (`tests/conftest.py:9-27`).
- **문서 문화**: 날짜별 설계/계획 기록, 런북, QA 시트 — 그리고 **이전 리뷰 권고를 실제로 이행한 이력**.

---

## 4. Improvement Strategy

### 테마 1 — "남은 두 모놀리스" (H4, H5)
원칙: *코드는 그것을 바꾸는 사람 수만큼 쪼개면 충분하다.* 1인 운영이므로 프레임워크 도입 없이 **파일 분할만** 한다.
목표 상태: main.py는 앱 조립(미들웨어·라우터 와이어링·워커 기동)만 남기고 헬퍼는 `app/services/`·`app/api/`로 이동, `_main()` 역참조 제거. index.html은 `index.html + app.css + js/` 도메인별 ESM 모듈 6~10개로 분할(빌드 도구 없이 `<script type="module">`).

### 테마 2 — "단일 진실 원천 부재가 만든 실버그" (H1, M1, M2, M6)
원칙: *복제된 로직은 반드시 드리프트한다 — 이미 했다.*
목표 상태: 도메인 상수는 `app/db/__init__.py`(또는 신설 `app/constants.py`) 한 곳, main.py는 임포트만. list/count는 `(where_sql, params)`를 반환하는 공용 빌더 하나를 공유. 스키마 DDL은 schema_migration으로 일원화.

### 테마 3 — "세션·시크릿 수명주기" (C1, C2, H2, H3, M5)
원칙: *암호화가 강해도 수명주기가 약하면 무용지물.*
목표 상태: 시크릿 미설정 시 기동 거부, 로그인 백오프(실패 5회→지수 지연), 세션은 매 요청 DB의 `is_active`/역할과 대조(쿼리 1회, 30k 규모에서 무시 가능한 비용), `.env` 노출 경로는 ADMIN 전용, 토큰 전체 회전 + `.bak` 삭제.

### 테마 4 — "강제 장치" (M10, M8)
원칙: *문화는 좋다. 그러나 게이트가 문화를 지킨다.*
목표 상태: GitHub Actions(또는 사정상 로컬 pre-commit + launchd 주기 실행)에서 `ruff check` + `pytest`가 PR/푸시마다 돌고, 실패 시 배포 스크립트가 거부. requirements는 실제 임포트와 일치 + 버전 고정.

### 의도적으로 안 고치는 것
- **SQLite → 다른 DB**: 3만 행 + WAL + 단일 작성자 환경에서 교체 이득 없음.
- **워커의 async 전환 / 외부 프로세스화**: 현 스레드+Event 구조는 규모에 적절. (04-29 리뷰 2.1 제안은 보류 권고)
- **프런트 프레임워크/빌드 도입**: 파일 분할 대비 위험·비용 과대. 분할만으로 회귀 격리 목적 달성.
- **i18n 키 추출, FTS5**: 측정·필요 확인 전에는 미착수 (M9는 perf_log 실측이 선행).

### "완료"의 측정 가능한 정의
- Critical 0건, High 0건 (본 문서 기준 재감사).
- CI(또는 게이트 스크립트)가 lint+test 실패 시 빨간불 — 배포 스크립트가 이를 확인.
- `app/main.py` < 2,000줄, `_main()` 역참조 0건, `index.html` 단일 파일 < 5,000줄.
- list/count가 공용 빌더 사용 + "size_group×track_state 조합" 회귀 테스트 존재.
- 로그인 연속 실패 시 지연 동작 테스트 통과. 시크릿 미설정 기동 거부 테스트 통과.
- 검색 p95 < 500ms를 `perf_log` 실측으로 확인(미달 시 FTS5 과제 발권).

---

## 5. Task Plan

### Milestone 0 — 안전망 (리팩토링 전 필수)

| # | 과제 | 영향 범위 | 완료 기준 | 공수 | 위험 | 의존 |
|---|---|---|---|---|---|---|
| 0.1 ✅ | 검색 필터 조합 회귀 테스트 작성 (size_group×track_state, list=count 일치 검증) | `tests/` 신규 | 현 버그를 재현하는 실패 테스트 존재 | S | 없음 | — |
| 0.2 ✅ | ruff 도입 + `pyproject.toml` 베이스라인 (기존 위반은 ignore 베이스라인으로 동결) | 루트 설정 | `ruff check` 통과 | M | 낮음 | — |
| 0.3 ✅ | CI 게이트: GitHub Actions 또는 `scripts/preflight.sh`(pytest+ruff)를 배포 스크립트가 호출 | `.github/` 또는 `scripts/` | 실패 시 배포 중단 실증 | M | 낮음 | 0.2 |
| 0.4 | 작업 폴더 정리: `.worktrees/` 9개·`.env.local.bak`·루트 `library.db`·중복 venv 정리(백업 후) | 저장소 외곽 | 디스크 회수, `.bak` 소거 | S | 낮음(삭제 전 백업) | — |

### Milestone 1 — Critical/정확성 수정

| # | 과제 | 영향 범위 | 완료 기준 | 공수 | 위험 | 의존 |
|---|---|---|---|---|---|---|
| 1.1 ✅ | H1 `elif`→`if` 수정 (list/count 양쪽) | `owned_item_query.py:234,445` | 0.1 테스트 녹색 | S | 낮음 | 0.1 |
| 1.2 ✅ | 시크릿 fail-fast: 기본 세션 시크릿 제거, 미설정 시 기동 거부 | `config.py:140`, lifespan | 미설정 기동 시 명확한 에러 | S | 중(운영기 env 확인 선행) | — |
| 1.3 ✅ | 시크릿 전면 회전 + `.env` 접근 ADMIN 전용화 (`include_env_file`, provider-settings) | `ops_system.py:121-207`, 운영 절차 | OPERATOR로 `.env` 획득 불가 | M | 중 | 1.2 |
| 1.4 ✅ | 로그인 백오프/잠금 (메모리 카운터, 실패 5회→지수 지연) | `api/auth.py` | 연속 실패 지연 테스트 통과 | M | 낮음 | — |
| 1.5 ✅ | 세션-DB 대조: 매 요청 계정 활성/역할 확인, 로그아웃·비활성화 즉시 반영 | `security.py:230-256` | 비활성 계정 쿠키 즉시 거부 테스트 | M | 중(전 요청 경로) | 0.3 |
| 1.6 ✅ | M1 도메인 상수 단일화 + 레거시 매핑 확정, 기존 데이터 `WORLD`/`WORLD_OTHER` 실태 조사 후 정정 마이그레이션 | `main.py:212-230`, `db/__init__.py:18-40` | 상수 정의 1곳, 데이터 검증 쿼리 첨부 | M | 중(데이터 변환) | 0.1 |

### Milestone 2 — 고레버리지 구조 개선

| # | 과제 | 영향 범위 | 완료 기준 | 공수 | 위험 | 의존 |
|---|---|---|---|---|---|---|
| 2.1 ✅ | list/count 공용 WHERE 빌더 추출 | `owned_item_query.py` 전체 | 중복 0, 테스트 녹색 | M | 중 | 1.1 |
| 2.2 ✅ | main.py 헬퍼 이주 1차: ①날씨/HA→`services/home_env.py`✅ ②카메라→`services/camera.py`✅ ③백업→`services/backup.py`✅ ④구매메일→`services/purchase_mail.py`✅ | `main.py`, `api/*`의 `_main()` 제거 | main.py 5,493줄(목표 < 4,000줄 미달, Discogs 매핑 블록 미이주) | XL→분할 | 중 | 0.3 |
| 2.3 | index.html 1차 분할: CSS 외부화 + `<script>`를 도메인 ESM 6~10개로 | `app/static/` | 단일 파일 < 5,000줄, 화면 QA 시트 통과 | XL→분할 | 높음(프런트 테스트 부재) | 0.3, QA시트 |
| 2.4 ⛔ | 스키마 DDL 일원화(schema_migration로), `db/__init__.py` 잔존 DDL 제거 (SKIPPED — init_db() 경로 위험) | `db/__init__.py:1399+` | DDL 정의 1곳 | M | 중 | 0.3 |
| 2.5 ✅ | requirements 정비: spotipy 등 실제 임포트 전수 반영 + 핀 고정(+ `pip freeze` 락) | `requirements.txt` | 새 venv에서 전 기능 기동 | S | 낮음 | — |
| 2.6 ✅ | cafe async 정리: DB 호출 `run_in_executor`/동기 라우트화, `_local.current_track()` executor 이동, 중복 `/cafe/tags` 제거 | `api/cafe.py:121,175-188,257-274` | 이벤트 루프 블로킹 0 | M | 중 | 0.3 |

### Milestone 3 — 품질·마감

| # | 과제 | 영향 범위 | 완료 기준 | 공수 |
|---|---|---|---|---|
| 3.1 ✅ | `/cafe/search` 보호(디바이스 검증 또는 레이트리밋) | `cafe.py:193` | 무인증 남용 차단 | M |
| 3.2 ✅ | 평문 비번 하위호환 제거(로그인 성공 시 재해시 후 일몰) | `security.py:66-69` | 평문 행 0 확인 후 코드 삭제 | S |
| 3.3 ✅ | 로그인 로고 401 수정(`/ui-static/images/` 허용 또는 인라인) | `main.py:534-553` | 미인증 로그인 화면 정상 | S |
| 3.4 ✅ | `.env.example`의 `DB_PATH`→`LIBRARY_DB_PATH` 정정 | `.env.example:6` | 문서=코드 | S |
| 3.5 ✅ | perf 스킵 목록 `/static/`→`/ui-static/` 정정 | `main.py:493` | — | S |
| 3.6 ✅ | 검색 p95 실측(perf_log 집계) → 미달 시 FTS5 과제 발권 | 측정 | 수치 보고서 | S |
| 3.7 | split-phase 테스트 39개를 구조 리팩토링 완료 시점에 정리/통합 | `tests/` | 의미 있는 행위 테스트만 잔존 | M |
| 3.8 ✅ | bare `except Exception: pass` 중 비즈니스 경로 분류 후 `logger.warning` 부여 | 41건 분류 | 텔레메트리성 외 0건 | M |

### 5.4 퀵윈 (즉시, 전부 S — 합계 반나절)
1. **1.1** `elif`→`if` 버그 수정 (실사용 버그)
2. **M7** 중복 `/cafe/tags` 제거
3. **3.3** 로그인 로고 401
4. **2.5 일부** requirements에 `spotipy` 추가
5. **0.4 일부** `.env.local.bak` 파기(회전과 병행)
6. **3.4** `.env.example` 키 이름 정정
7. **3.5** perf 스킵 경로 정정

### 5.5 상위 3개 과제 구현 스케치

**① 1.1 + 2.1 — 필터 버그 수정과 공용 빌더**
접근: 먼저 0.1에서 `size_group_state="MATCH"` + `track_state="HAS"` 조합으로 list/count 양쪽이 트랙 필터를 적용하는지 검증하는 실패 테스트를 만든다. 수정은 `elif track_state_u == "HAS":` 를 독립 `if`로 승격(2곳). 이어서 `_build_owned_item_filters(...) -> tuple[str, list[Any]]`를 추출해 두 함수가 공유. 주의: 빌더 추출 시 ORDER BY/LIMIT는 list 전용으로 남길 것, `slot_size_ok_sql()` 같은 f-string 삽입부는 파라미터화 불가하므로 그대로 유지.

**② 1.2~1.5 — 세션 수명주기 묶음**
접근: (a) `get_settings`에서 시크릿 빈값이면 raise, conftest는 이미 시크릿 주입하므로 영향 없음(`tests/conftest.py:20`). (b) `_read_auth_session_data`에 `db.get_auth_account_by_username` 대조 추가 — 비활성/부재 시 None. 주의: 이 함수는 미들웨어에서 매 요청 호출되므로 60초 TTL의 소형 인메모리 캐시 허용. (c) 로그인 백오프는 `{username: (fail_count, until_ts)}` 모듈 딕셔너리로 충분(단일 프로세스). (d) 회전 절차는 `docs/secret_rotation_runbook.md`가 이미 있으니 그 절차를 따르고 `.bak`을 파기. 함정: 1.5 배포 직후 모든 기존 쿠키가 DB 대조를 통과해야 하므로 username 케이스 일치 확인.

**③ 2.2 — main.py 해체 1차**
접근: 이미 검증된 플레이북(라우터 분할 때 쓴 re-export + split-phase 테스트 방식)을 재사용하되, 이번엔 모듈 표면 고정 테스트 대신 **행위 테스트**(구매메일 파싱 픽스처, 백업 생성/복구 왕복)를 먼저 둔다. 이동 순서는 의존이 가장 얕은 것부터: ① 날씨/HA(4,281-4,427) ② 카메라/ONVIF(3,700-4,060) ③ 백업(3,203-3,520) ④ 구매메일(1,253-2,470). 각 단계마다 `api/*`의 `_main()` 참조를 직접 임포트로 치환. 함정: 워커 전역 상태(`METADATA_SYNC_*` 등, `main.py:285-301`)는 마지막에 옮길 것 — lifespan(`:179-204`)과의 바인딩 순서가 깨지기 쉽다.

---

## 6. Open Questions

1. **운영기 시크릿 실태**: 상용/QA 머신의 `LIBRARY_AUTH_SESSION_SECRET`이 실제 설정돼 있는가? (외장 디스크 사본만으로는 확인 불가) 1.2 착수 전 확인 필요.
2. **Cloudflare 앞단 보호**: 터널에 Cloudflare Access/WAF 룰이 걸려 있는가? 있다면 H2/M4의 실효 위험도가 한 단계 내려간다.
3. **`WORLD` vs `WORLD_OTHER`**: DB에 두 값이 모두 존재하는가? (감사 환경에서 DB 질의 불가) M1 정정 방향(통합 vs 구분 유지)은 데이터 실태와 운영 의도에 달려 있다.
4. **카페 태블릿 공개 범위**: `/cafe/search` 무인증 공개가 의도인가, 디바이스 등록 검증을 붙여도 UX가 깨지지 않는가?
5. **성능 목표의 실측치**: `perf_log`에 쌓인 검색 p95가 이미 500ms를 넘는가? (3.6) FTS5 투자 여부의 결정 변수.
6. **split-phase 테스트 39개의 처분**: 구조 고정 테스트를 언제 은퇴시킬지 — 2.2/2.4 완료 시점 일괄 정리에 동의하는가?
7. **CI 인프라**: 이 저장소가 GitHub 등 원격에 푸시되는가, 아니면 로컬 전용인가? 0.3의 형태(GitHub Actions vs 로컬 pre-flight)가 갈린다.

---

## 7. 부록 — 실측 분석 (2026-06-10, 폴더 정리 후 추가 수행)

작업 폴더 정리(약 660MB 회수: `.worktrees/` 9개, `.venv_api`, `.env.local.bak`, 루트 0바이트 `library.db`, 3~4월 수동 백업, 6/7 corrupted 사본) 후 셸이 복구되어 아래 실측을 수행했다. **이 부록 작성 시점에 다른 세션에서 퀵윈 수정이 병렬 진행 중**이어서(작업 트리 미커밋 변경 18파일), 본문 §3의 일부 지적은 이미 해소됐다 — 항목별로 표기한다.

### 7.1 [신규·High] 6/7 손상 복구 후 데이터가 `lost_and_found`에 방치됨

개발 DB(`data/library.db`)에서:
- `music_item_detail` 테이블이 **0행** (스키마 38컬럼은 존재). `goods_item_detail`, `track_tag`도 0행.
- 대신 `lost_and_found` 테이블(108MB)에 nfield=38 행 **4,801개** — 표본 확인 결과 명백한 음반 상세 데이터('Digipak', 아티스트명, 발매일, 레이블). 그 외 nfield=2(10,208행), nfield=3(5,938행), nfield=9(5,098행) 그룹도 존재.
- `error_log`에 2026-06-07 `no such table: music_item_detail` 연쇄 기록 → 6/7 손상 후 `.recover`로 복구하면서 데이터가 `lost_and_found`로 빠지고, 앱 마이그레이션이 빈 테이블을 재생성한 정황.

**의미**: 개발 DB는 6/7 이후 상세 메타(아티스트/바코드/커버/수록곡 연결) 없이 돌고 있고, 검색의 `mid.*` 필터는 전부 빈 값과 매칭 중. 복구 경로는 ① `lost_and_found`에서 컬럼 매핑 후 INSERT 복원(nfield=컬럼 수로 원천 테이블 식별 가능), ② QA/상용 머신의 독립 DB에서 역동기화. **조치 전까지 `lost_and_found` 테이블을 절대 삭제하지 말 것** (DB 용량 377MB의 약 1/3이지만 유일한 원본일 수 있음).

### 7.2 DB 실측 수치

- 규모: `owned_item` **4,846행**, `album_master` 4,350행 — *운영자 확인: 등록 진행 중이며 완료 시 3만+ 예정.* 즉 현 DB에서의 성능 실측은 최종 규모의 ~16% 부하에 불과 — §7.3의 느린 응답은 데이터 증가 시 더 악화된다고 봐야 한다.
- **M1(도메인 드리프트) 데이터로 확인**: `owned_item.domain_code`에 `WORLD` 10행, `album_master.domain_code`에 `WORLD_OTHER` 71행 — 두 레거시 매핑이 실제로 서로 다른 값을 만들어 놓음.
- M5(평문 비번): 현 DB에는 평문 행 **0건** (전부 pbkdf2_sha256). 상용 DB 확인 후 하위호환 코드 제거 가능.
- DB 용량 구성: `local_music_index` 128MB+인덱스 121MB, `lost_and_found` 108MB가 377MB의 대부분. 카탈로그 자체는 ~10MB.

### 7.3 성능 실측 (perf_log 4,741행 — *느린 요청만 기록되는 편향 표본*)

- `GET /owned-items`: 느린 호출 19건, 1.1~7.4초. `GET /album-masters` 최대 **222초**, `GET /operator/home/feed` 평균 86초/최대 222초 — 외부 API 또는 락 대기 정황, 원인 추적 필요(3.6 과제 상향 권고).
- 느린 쿼리 상위는 전부 `local_music_index` LIKE 스캔(0.6~1.0초) — FTS5 후보는 owned_item이 아니라 **local_music_index**다.

### 7.4 git 이력 핫스팟 (최근 9개월)

- `app/static/index.html` **331커밋** — 2위(79)의 4배. H5(프런트 분할)의 정량 근거. 5/27 57,859줄 → 6/10 62,176줄(+4,300/2주).
- `app/db/__init__.py` 72, `app/main.py` 59, `providers.py` 54커밋이 뒤따름 — 변경이 모놀리스에 집중.

### 7.5 pytest 베이스라인 (Linux 샌드박스, 병렬 수정 반영된 작업 트리 기준)

`8 failed, 639 passed, 13 skipped, 171 xfailed, 531 xpassed (38초)`
- 실패 8건 중 4건은 macOS 전용(`test_macos_deploy_assets`, plutil 부재), 1건은 의존성 누락(`test_local_music` — mutagen/tinytag 미설치)으로 환경 요인. `test_cafe_sse` 2건과 `test_ops_route_access` 1건은 병렬 수정 중인 코드라 재확인 필요.
- **xpassed 531건**: xfail 마크가 걸렸는데 통과하는 테스트가 절반 이상 — 마커 정비 필요(3.7 과제에 포함 권고).

### 7.6 본문 지적 중 이미 해소 확인 (미커밋 작업 트리 기준)

H1 elif 버그(list/count 모두 `if`로 수정), C1 시크릿 fail-fast(`_INSECURE_SESSION_SECRETS` 가드), H2 로그인 백오프(auth.py +42줄), M7 `/cafe/tags` 중복 제거, L2/L3 `/ui-static` 허용·perf 스킵 수정, M8 일부(requirements에 spotipy·ruff 추가). **잔여**: requirements에 `mutagen`, `tinytag` 여전히 누락(테스트 실패로 실증), `starlette` 직접 임포트 미고정.

---

### 검토 범위 메모
`app/main.py`·`app/db/owned_item_query.py`·`connection.py`·`security.py`·`config.py`·`api/auth.py`·`api/ops_system.py`·`api/cafe.py`·providers 헤더·schema_migration 인덱스부·conftest·split-phase 테스트 표본은 정독. `schemas.py`(2,118줄), `collection_dashboard.py`, `location_recommendation.py`, `artist_context.py`, index.html의 JS 본문, `mcp-deepseek/`, `scripts/` 대부분은 표본 검토에 그쳤다 — 해당 영역에 추가 이슈가 있을 수 있다. 샌드박스 셸 부팅 실패(디스크 부족)로 git 이력·DB 실측·테스트 실행은 수행하지 못했다.
