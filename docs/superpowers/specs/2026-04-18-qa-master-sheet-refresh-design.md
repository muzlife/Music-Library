# 단일 QA 마스터 시트 재정비 설계

## 목표

`docs/qa/qa_master_sheet.csv`를 현재 제품/배포 흐름 기준의 단일 QA 기준 문서로 재정비한다.  
이 문서는 다음 세 역할을 동시에 수행해야 한다.

1. 배포 전 QA 게이트
2. 기능 도메인별 검증 추적
3. 자동/수동 증적 관리

별도 잔여 시트나 과거 pass 로그 중심 구조는 중단하고, 현재 릴리스 판단과 후속 보정에 모두 쓸 수 있는 형태로 다시 잡는다.

## 현재 문제

### 1. 시트가 현재 기준 QA 계획표가 아니라 과거 pass 로그에 가깝다

기존 `docs/qa/qa_master_sheet.csv`는 많은 항목이 `Pass` 상태와 실행 메모 위주로 적재되어 있다.  
이 구조는 “지금 무엇을 다시 확인해야 하는가”보다 “예전에 무엇이 통과했는가”를 보여준다.

### 2. QA 기준 문서가 사실상 분산돼 있다

다음 문서들이 QA 흐름을 각각 일부씩 담고 있다.

- `docs/qa/qa_master_sheet.csv`
- `docs/qa/qa_manual_remaining.csv`
- `docs/go_live_checklist.md`
- `docs/macos_qa_prod_runbook.md`

이 때문에 QA 기준, 운영 절차, 남은 수동 확인이 한눈에 모이지 않는다.

### 3. 최근 제품 범위가 시트에 충분히 반영되지 않았다

현재 제품은 기존 시트보다 넓은 범위를 가진다.

- 운영 홈
- 대시보드 / 위치 복구 / 이동 작업대
- 검색 / 관리 / 외부 소스 연계
- 등록 / 구매 수입 / CSV 일괄 등록
- 운영/연계 / 시스템 상태 / 예외 큐 / 연동 설정 / 백업
- 공통 shell / day-night / locale / help drawer
- 아티스트 컨텍스트 및 외부 메타 fallback

기존 시트는 일부 기능군은 상세하지만, 최근 UI/메타/운영 검증 포인트는 구조적으로 흡수하지 못하고 있다.

## 설계 원칙

### 1. 기준 문서는 하나만 둔다

QA의 기준 문서는 `docs/qa/qa_master_sheet.csv` 하나로 고정한다.

- QA 실행 상태
- 배포 게이트
- 수동 전용 항목
- 자동 검증 링크
- 증적 위치

이 다섯 가지는 모두 이 시트 안에 들어가야 한다.

### 2. 절차 문서와 체크 시트를 분리한다

다음 문서는 계속 유지한다.

- `docs/macos_qa_prod_runbook.md`
- `docs/go_live_checklist.md`

하지만 이 문서들은 “어떻게 실행하는가”를 설명하는 절차 문서로 한정한다.  
실제 QA 항목의 상태와 증적은 `qa_master_sheet.csv`가 가진다.

### 3. 과거 결과보다 현재 게이트 상태가 우선이다

시트는 “Pass 이력 누적표”가 아니라 “이번 검증 기준표”여야 한다.

따라서 각 행은 다음 질문에 답해야 한다.

- 이번 배포에서 꼭 막아야 하는가
- 자동으로 검증 가능한가
- 사람이 브라우저/실장비로 봐야 하는가
- 어떤 증적으로 통과를 판단하는가
- 누가 확인했는가

### 4. 현재 제품 구조를 기준으로 묶는다

상위 섹션은 문서 구조가 아니라 현재 제품 표면을 따라간다.  
운영자가 실제 화면/흐름을 따라 확인할 수 있어야 한다.

## 단일 QA 시트 구조

### 상단 게이트 섹션

가장 먼저 다음 섹션을 둔다.

- `Release / Environment / Recovery`

이 섹션은 배포 전 승격 판단용이다.

포함 항목 예:

- QA/운영 DB 분리
- QA 최신 반영 여부
- preflight / full QA 실행
- 로컬/외부 health
- 배포 대상 commit/ref 고정
- rollback 가능 backup 존재
- launchd / 외부 접속 확인

### 기능 도메인 섹션

그 아래는 현재 제품 기준으로 기능을 나눈다.

- `Auth / Roles / Route Access`
- `Operator Home`
- `Dashboard / Placement / Recovery`
- `Search / Manage`
- `Source Enrichment / Master Cleanup`
- `Registration / Intake`
- `Ops / Integrations`
- `Cross-cutting Shell / UX`

### 섹션 설계 이유

이 구조는 두 가지를 동시에 만족한다.

1. 상단 게이트만 보면 배포 가능 여부를 판단할 수 있다.
2. 하단 기능 섹션을 보면 어떤 영역에 잔여 리스크가 있는지 추적할 수 있다.

즉, 배포용 체크리스트와 기능 QA 인벤토리를 한 시트 안에 공존시킨다.

## 컬럼 정의

다음 컬럼을 최소 기준으로 사용한다.

- `case_id`
- `section`
- `surface`
- `role`
- `environment`
- `phase`
- `release_ref`
- `priority`
- `gate`
- `coverage_mode`
- `scenario`
- `preconditions_or_test_data`
- `expected_result`
- `definition_ref`
- `evidence_ref`
- `workflow_state`
- `result`
- `verified_at`
- `executor`
- `approver`
- `notes_or_risk`

### 컬럼 의미

#### `case_id`

영역별 고유 ID.  
기존 접두사는 최대한 살리되, 새 섹션에 맞게 재배치한다.

예:

- `REL-001`
- `AUTH-001`
- `OPS-UI-001`
- `SHELL-001`

#### `section`

상위 묶음. 필터링과 릴리스 판단을 위해 반드시 필요하다.

#### `surface`

사용자가 실제로 보는 화면/패널/흐름 이름.

예:

- `미디어 > 검색`
- `운영/연계 > 시스템 상태`
- `운영 홈 > 위치 검색`
- `공통 헤더`

#### `role`

테스트를 수행하는 역할.

예:

- `관리자`
- `현장 운영자`
- `공통`

#### `environment`

검증이 수행되는 환경.

예:

- `qa`
- `prod`
- `local`

prod 전용 smoke와 안정화 확인도 별도 문서로 빼지 않고 이 컬럼으로 식별한다.

#### `phase`

릴리스 단계.

허용값:

- `Pre-release`
- `Post-release`

의미:

- `Pre-release`: QA 승격 전에 확인해야 하는 항목
- `Post-release`: 운영 반영 직후 smoke/안정화 확인 항목

#### `release_ref`

이번 QA가 어떤 배포 후보를 검증하는지 식별하는 키.

예:

- git commit SHA
- release tag
- deploy candidate ID

이 컬럼은 `Pass`, `Fail`, `Waived`가 어떤 릴리스 후보의 결과인지 고정하는 역할을 한다.

#### `priority`

기능 중요도.

예:

- `P0`
- `P1`
- `P2`

#### `gate`

배포 차단 수준.

허용값:

- `Blocker`
- `Release`
- `Non-blocking`

의미:

- `Blocker`: 실패 시 운영 반영 금지
- `Release`: 이번 배포 판단에 포함
- `Non-blocking`: 후속 보정 항목

#### `coverage_mode`

검증 방식.

허용값:

- `Auto`
- `Hybrid`
- `Manual`
- `Manual-only`

의미:

- `Auto`: 자동 검증만으로 판단 가능
- `Hybrid`: 자동 + 브라우저/실장비 확인 필요
- `Manual`: 수동 중심이지만 반복 가능
- `Manual-only`: 자동화 불가 또는 비경제적

#### `scenario`

검증하려는 동작을 한 줄로 기술한다.

#### `preconditions_or_test_data`

사전 조건과 데이터 준비를 쓴다.  
지금처럼 긴 절차를 풀기보다 “무엇이 있어야 하는가”를 먼저 적는다.

#### `expected_result`

판정 기준을 기술한다.  
가능하면 상태, 응답, 화면 결과를 같이 적는다.

#### `definition_ref`

이 행을 어떻게 실행하는지 가리키는 정의 참조.

예:

- pytest 파일/테스트 이름
- 실행 스크립트
- runbook 섹션
- 관련 매뉴얼 링크

이 컬럼은 절차를 담는다.

#### `evidence_ref`

이번 재정비의 핵심 컬럼이다.  
이 컬럼은 “이번 릴리스 후보에서 실제로 무엇을 확인했는가”를 담는다.

예:

- health check 응답
- 스크린샷 파일명
- 브라우저 확인 메모
- 로그 파일 경로
- 백업 번들명
- 실제 실행 명령과 요약 결과

형식은 `type:value | type:value`의 다중 참조 형식으로 고정한다.

예:

- `pytest:tests/test_ops_route_access.py::test_artist_context | screenshot:qa-artist-context-20260418.png`
- `health:https://qa-library.muzlife.com/health=200 | log:runtime/logs/launchd.qa.stdout.log`

#### `workflow_state`

행의 준비/진행 상태를 나타낸다.

허용값:

- `Planned`
- `Ready`
- `In Progress`
- `Blocked`

#### `result`

현재 릴리스 후보에 대한 실제 결과를 나타낸다.

허용값:

- `Not Run`
- `Pass`
- `Fail`
- `Waived`

`workflow_state`와 `result`를 분리해서 릴리스 판단을 계산 가능하게 만든다.

#### `verified_at`

실제 검증 시각.

형식:

- `YYYY-MM-DD HH:MM KST`

이 컬럼이 있어야 stale pass와 현재 릴리스 결과를 구분할 수 있다.

#### `executor`

실행 주체.

예:

- `codex`
- `ops`
- `qa`
- `admin`

#### `approver`

릴리스 게이트 또는 waiver 승인 책임자.

`executor`와 분리해서 최종 판단 책임을 남긴다.

#### `notes_or_risk`

남은 리스크, 임시 우회, 실제 확인 메모를 남긴다.

## 릴리스 판정 규칙

### 계산 규칙

`gate`는 그대로 유지하되, 판정은 `phase`별로 계산한다.

### 배포 전 승격 규칙

운영 승격은 `phase=Pre-release` 행에 대해서만 계산한다.

1. 대상 `release_ref`가 명확히 채워져 있다.
2. `phase=Pre-release` 이고 `gate=Blocker` 인 행의 `result`가 모두 `Pass`다.
3. `phase=Pre-release` 이고 `gate=Release` 인 행의 `result`가 모두 `Pass` 또는 승인된 `Waived`다.
4. `phase=Pre-release` 이고 `workflow_state=Blocked` 인 `Blocker`/`Release` 행이 없다.

### 배포 후 안정화 규칙

운영 반영 직후에는 `phase=Post-release` 행을 별도로 확인한다.

- prod smoke
- 초기 안정화
- rollback readiness re-check

이 항목들은 운영 승격 전 조건이 아니라, 운영 반영 직후 확인 및 복구 판단 조건이다.

### `Waived` 규칙

- `Blocker`는 waive 불가
- `Release`와 `Non-blocking`만 waive 가능
- `Waived`를 쓰려면 반드시 `approver`와 `notes_or_risk`에 사유를 남긴다
- waiver는 현재 `release_ref`에만 유효하며 다음 릴리스로 자동 이월되지 않는다

### prod smoke 위치

prod 배포 직후 smoke와 초기 안정화 확인도 별도 문서에만 두지 않고 `qa_master_sheet.csv`에 포함한다.

- `section=Release / Environment / Recovery`
- `environment=prod`
- `phase=Post-release`
- `gate=Release`

즉, prod 확인은 절차는 `go_live_checklist.md`에 남기되, 결과는 마스터 시트에 기록한다.

## 행 분할 규칙

한 행은 “하나의 트리거와 하나의 판정 결과”만 가져야 한다.

다음은 반드시 분리한다.

- backup
- restore
- rollback
- responsive
- contrast
- overflow
- hit target
- negative / permission / recovery / data-integrity 케이스

즉, broad flow를 한 행으로 묶지 않는다.

## 기존 행 마이그레이션 규칙

기존 시트의 케이스는 단순 삭제하지 않는다.

원칙:

1. `Negative`, `Recovery`, `Permission`, `DataIntegrity` 항목은 유지한다.
2. 기존 `suite_id`는 가능한 한 `case_id`로 승계한다.
3. 너무 넓은 기존 행은 세분화하되, 원본 ID 뒤에 suffix를 붙인다.

예:

- `SYS-003`
- `SYS-003A`
- `SYS-003B`

4. 과거 실행 메모는 `notes_or_risk`로 요약 이전하고, 현재 릴리스 결과는 새 `result/verified_at/evidence_ref`로 다시 기록한다.

## 기존 문서와의 관계

### `docs/qa/qa_manual_remaining.csv`

별도 진실 소스로 유지하지 않는다.

처리 원칙:

- 내용이 비어 있으면 사실상 폐기 대상
- 수동 전용 항목은 `qa_master_sheet.csv`의 `coverage_mode=Manual-only`로 흡수

### `docs/go_live_checklist.md`

릴리스 순서 문서로 남긴다.  
체크 항목 본문은 줄이고, QA 기준은 마스터 시트를 참조하게 바꾼다.  
다만 prod smoke와 초기 안정화 절차는 계속 유지하되, 실제 결과 기록은 마스터 시트에 남긴다.

### `docs/macos_qa_prod_runbook.md`

환경/배포/롤백 절차 문서로 남긴다.  
QA 항목 목록을 반복하지 않고, “어떤 시트를 따라 확인하는가”만 연결한다.

### `README.md`

문서 인덱스 역할만 유지한다.  
QA 기준 문서는 `docs/qa/qa_master_sheet.csv` 하나라고 명시한다.

## 포함해야 할 현재 QA 범위

다음 범위는 새 시트에 반드시 반영한다.

### 1. Release / Environment / Recovery

- QA/운영 분리
- 최신 QA 반영 여부
- health
- backup / restore / rollback
- deploy preflight
- 운영 승격 조건
- prod smoke
- 배포 직후 초기 안정화

### 2. Auth / Roles / Route Access

- 관리자 로그인
- 현장 운영자 로그인
- 로그아웃
- operator write 제한
- direct route / role별 UI 노출

### 3. Operator Home

- 검색
- 현재/직전 위치
- 컨텍스트 패널
- CTA 동작

### 4. Dashboard / Placement / Recovery

- 장식장 열기
- 칸 선택
- 이동 시작/취소
- 이전 위치 복구
- 선택 상태
- 대시보드 요약

### 5. Search / Manage

- 상품/곡/바코드 검색
- 상품 수정
- 관련 상품/변형 미리보기
- day 모드 선택/확장 surface

### 6. Source Enrichment / Master Cleanup

- 미연결 후보 조회
- 자동/수동 교체
- master 정리
- 아티스트 컨텍스트
- Discogs / ManiaDB / MusicBrainz / Wikipedia fallback

### 7. Registration / Intake

- 직접 등록
- 외부 메타 기반 등록
- 구매 파일 미리보기
- 수입 큐 저장/후보 선택/생성
- CSV 업로드 및 검수 큐

### 8. Ops / Integrations

- 예외 큐
- 장식장 / 슬롯 / 카메라
- 계정
- 연동/API 설정
- 시스템 상태
- 백업/복원/내보내기

### 9. Cross-cutting Shell / UX

- day/night
- locale
- header utility
- help drawer
- responsive
- 텍스트 overflow / contrast / hit target

## 검증/보정 루프 설계

재정비 후 QA는 다음 루프로 운영한다.

1. 자동 검증 항목 실행
2. `coverage_mode=Hybrid`와 `Manual-only`를 우선순위대로 브라우저/실장비 확인
3. 실패/이상 항목은 `status=Fail` 또는 `Blocked`로 즉시 반영
4. 보정 후 동일 행에서 증적 갱신
5. 상단 `Blocker` / `Release`가 모두 해소될 때만 운영 승격

즉, QA 시트는 static checklist가 아니라 보정 루프를 수용하는 실행판이어야 한다.

추가 원칙:

- `Pass`와 `Waived`는 반드시 `release_ref`, `environment`, `verified_at`, `approver`와 함께 남는다
- `Hybrid`와 `Manual-only`는 stale evidence를 막기 위해 현재 릴리스 기준 증적을 매번 새로 남긴다

## 비목표

이번 재정비에서 하지 않는 일:

- 모든 수동 항목의 즉시 자동화
- 런북 전체를 QA 시트로 대체
- 과거 모든 실행 로그의 완전 보존
- 제품 기능 구조의 대규모 재분류

이번 범위는 `단일 QA 기준 문서`를 다시 세우는 것이다.

## 성공 기준

다음이 만족되면 성공이다.

1. QA 기준 문서를 열었을 때 이번 배포 가능 여부를 바로 알 수 있다.
2. 최근 제품 기능과 UI 검증 포인트가 빠지지 않는다.
3. 자동/수동/증적 구분이 각 행에서 명확하다.
4. `qa_manual_remaining.csv` 없이도 수동 잔여를 추적할 수 있다.
5. 런북/체크리스트와 역할이 충돌하지 않는다.
