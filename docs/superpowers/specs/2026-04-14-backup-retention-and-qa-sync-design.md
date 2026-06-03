# 백업 보존 정책 및 QA 동기화 설계

작성일: 2026-04-14

## 배경

현재 코드베이스에는 앱 내부 자동 백업 설정이 이미 존재합니다.

- `DB` 또는 `FULL` 스코프 백업 생성 가능
- 백업 디렉터리, 주기(분 단위), `.env.local` 포함 여부 저장 가능
- 운영/QA 분리 배포 런북에는 `운영 백업 -> QA 복제` 절차가 문서화되어 있음

하지만 실제 운영 관점에서는 아래 빈틈이 남아 있습니다.

1. 앱 내부 자동 백업은 단일 주기만 다룰 수 있어 `일일 DB 백업`과 `주간 QA 반영용 full bundle`을 동시에 관리하기 어렵다.
2. 변경이 없는 날에도 동일한 백업을 계속 쌓아 저장 공간을 낭비한다.
3. QA 반영은 절차 문서만 있고, 주 1회 운영 기준 복제 정책이 명시적으로 고정돼 있지 않다.
4. 백업 성공 여부보다 중요한 `복구 가능성`과 `QA 반영 후 검증` 기준이 자동 운영 규칙으로 고정돼 있지 않다.

## 목표

이번 설계의 목표는 아래 네 가지입니다.

1. 운영 서버는 하루 1회 복구 지점을 남긴다.
2. 백업 결과가 직전과 동일하면 새 파일을 만들지 않고 스킵한다.
3. QA 서버는 주 1회 운영 최신 상태를 반영해 가상 운영 검증 환경을 유지한다.
4. 구현은 macOS 운영 구조에 맞게 단순하고 복구 가능해야 한다.

## 비목표

이번 범위에서 하지 않는 일은 아래와 같습니다.

1. 블록 단위 증분 백업 시스템 도입
2. 객체 스토리지, 원격 백업 서버, S3 같은 외부 저장소 도입
3. QA 데이터를 부분 병합하는 양방향 동기화
4. 앱 UI 안에 복잡한 캘린더형 스케줄러 추가

## 요구 조건

### 운영 백업

- 주기: 하루 1회
- 기본 원칙: 변경 없으면 스킵
- 최소 보장 대상: `library.db`
- 권장 보장 대상: `library.db + uploads`

### QA 반영

- 주기: 주 1회
- 소스: 운영 최신 백업
- 동작: QA 데이터를 덮어쓰는 복원
- 복원 후 QA 앱 재시작 및 검증 수행

## 접근안 비교

### 안 1. 앱 내부 자동 백업 기능 확장

- 기존 `app_setting` 기반 자동 백업 스레드를 확장해 다중 스케줄, 변경 감지, QA 반영까지 수행
- 장점: UI에서 설정을 관리할 수 있음
- 단점: 앱 프로세스에 과도하게 의존하고, 운영/QA처럼 서로 다른 주기를 다루기엔 구조가 무거워짐

### 안 2. 앱 내부 자동 백업은 유지하고, 운영 스케줄은 `launchd` 스크립트로 분리 `추천`

- 앱 내부 자동 백업은 수동/예비 경로로 남겨둠
- 실제 운영 스케줄은 `launchd + 쉘/파이썬 헬퍼 스크립트`로 관리
- 운영 일일 백업, 운영 주간 full bundle, QA 주간 복원을 각자 분리 실행
- 장점: macOS 서버 운영 구조와 맞고, 서비스 재기동과 독립적으로 동작하며, 다중 주기를 가장 단순하게 처리 가능
- 단점: 설정 UI가 아니라 배포 자산과 런북을 통해 관리해야 함

### 안 3. 외부 백업 서비스/스토리지 중심 운영

- 운영에서 생성한 백업을 외부 저장소로 밀고, QA도 외부 저장소에서 받아 복원
- 장점: 장기적으로 확장성 좋음
- 단점: 현재 범위에 비해 과하고, 운영 복잡도가 크게 증가

## 결정

`안 2`를 채택합니다.

핵심 이유는 다음과 같습니다.

1. 이미 운영/QA 배포가 macOS `launchd` 기준으로 정리되어 있다.
2. 백업은 앱 내부 스레드보다 OS 수준 스케줄러가 더 예측 가능하다.
3. `일일 DB`, `주간 FULL`, `주간 QA 복원`처럼 주기가 다른 작업을 단순하게 나눌 수 있다.
4. 운영 앱이 재시작되거나 일시적으로 내려가도 백업 정책 자체는 독립적으로 유지된다.

## 최종 정책

### 백업 계층

최종 구조는 `로컬 주백업 + GCS 이중 백업` 2계층으로 둡니다.

1. `1차 백업`
   - 운영 맥미니 로컬 디스크
   - 복구와 QA 반영의 기준점

2. `2차 백업`
   - Google Cloud Storage
   - 운영 장비 장애, 로컬 디스크 손상, 실수 삭제에 대비한 오프사이트 백업

즉, QA는 기본적으로 로컬 운영 백업을 기준으로 동작하고, GCS는 재해복구용 2차 보관소입니다.

### 1. 운영 일일 DB 백업

- 대상: `runtime/data/library.db`
- 주기: 매일 1회
- 권장 시각: 새벽 03:00
- 파일명 예시: `__PROJECT_SLUG__-library-daily-db-YYYYMMDD-HHMMSS.db`
- 변경 감지: 직전 성공 백업과 SHA-256 비교
- 동일하면:
  - 새 백업 파일 삭제
  - `last_result = skipped`
  - `reason = unchanged`

### 2. 운영 주간 FULL 백업

- 대상:
  - `runtime/data/library.db`
  - `app/static/uploads/`
- 주기: 주 1회
- 권장 시각: 일요일 새벽 04:00
- 파일명 예시: `__PROJECT_SLUG__-library-weekly-full-YYYYMMDD-HHMMSS.zip`
- 변경 감지:
  - DB snapshot hash
  - uploads fingerprint
  - 위 두 값을 묶은 manifest hash
- 동일하면 스킵

### 2-1. 운영 오프사이트 백업(GCS)

- 대상:
  - 일일 DB 백업 산출물
  - 주간 FULL 백업 산출물
  - 각 백업의 메타 JSON
- 시점:
  - 로컬 백업 생성 직후
- 원칙:
  - 로컬 백업이 `created`일 때만 업로드
  - 로컬 백업이 `skipped`면 GCS 업로드도 스킵
- 역할:
  - 재해복구용 2차 보관소
  - QA 주간 반영의 기본 소스는 아님

### 3. QA 주간 운영 반영

- 주기: 주 1회
- 권장 시각: 월요일 새벽 05:00
- 소스: 운영 최신 `weekly full` 백업
- 대상: QA 서버 `library.db + uploads`
- 동작:
  1. 운영 최신 full bundle 조회
  2. 직전 QA 적용 manifest hash와 비교
  3. 동일하면 스킵
  4. 다르면 QA에 복원
  5. QA 앱 재시작
  6. smoke/preflight 검증

## 변경 감지 규칙

### DB 비교

- SQLite 원본 파일을 직접 해시하지 않음
- 항상 SQLite `backup()`으로 만든 임시 snapshot 파일을 해시
- 이유:
  - WAL 상태 차이를 줄일 수 있음
  - 복구 가능한 실질 snapshot 기준으로 비교 가능

### uploads 비교

- 업로드 전체 파일 내용을 매일 전부 해시하는 건 비용이 큼
- 주간 full에만 fingerprint 계산 적용
- fingerprint 기준:
  - 상대 경로
  - 파일 크기
  - mtime
- 필요 시 이후 단계에서 일부 파일 해시로 강화 가능

## 보관 정책

### 운영 DB 일일 백업

- 보관: 최근 30개
- 추가 규칙:
  - 가장 최근 성공본은 무조건 유지
  - `skipped`는 새 파일 없음

### 운영 FULL 주간 백업

- 보관: 최근 12개
- 이유:
  - 약 3개월 복구 지점 유지
  - 업로드 포함 bundle 크기를 고려한 보수적 기준

### QA 적용 기록

- QA 자체 백업을 장기 보관하지는 않음
- 다만 `직전 복원본` 1세트는 롤백용으로 유지 권장

### GCS 오프사이트 보관

- 일일 DB 백업: 최근 30일
- 주간 FULL 백업: 최근 12주
- 보호 방식:
  - timestamp 기반 불변 파일명
  - GCS `soft delete`와 lifecycle 정책 적용 권장

## 실행 구조

### 운영 서버(__PROD_MACHINE__)

- `launchd` 작업 2개
  - `com.muzlife.backup-daily-db`
  - `com.muzlife.backup-weekly-full`
- 산출물 위치
  - `/Users/__PROD_USER__/apps/__PROJECT_SLUG__-prod/runtime/backups/db/`
  - `/Users/__PROD_USER__/apps/__PROJECT_SLUG__-prod/runtime/backups/full/`
- 메타 기록 위치
  - `/Users/__PROD_USER__/apps/__PROJECT_SLUG__-prod/runtime/backups/metadata/`
- GCS 업로드
  - 각 백업 스크립트 후속 단계에서 수행
  - 또는 운영 안정화 후 별도 작업으로 분리 가능

### QA 서버(M4)

- `launchd` 작업 1개
  - `com.muzlife.qa-sync-weekly`
- 입력 위치
  - `/Users/__DEV_USER__/apps/__PROJECT_SLUG__-qa/runtime/imports/`
- 적용 메타 기록
  - `/Users/__DEV_USER__/apps/__PROJECT_SLUG__-qa/runtime/imports/metadata/`

### GCS 버킷 구조

추천 예시:

- `gs://__GCS_BUCKET__/prod/db/`
- `gs://__GCS_BUCKET__/prod/full/`
- `gs://__GCS_BUCKET__/prod/metadata/`
- `gs://__GCS_BUCKET__/qa/applied-manifests/`

원칙:

1. 운영 산출물과 QA 적용 기록은 prefix를 분리
2. 파일명은 로컬과 동일한 timestamp 기반 유지
3. 메타 JSON도 함께 업로드

## 산출 메타데이터

백업/복원 스크립트는 파일 외에도 메타 JSON을 남깁니다.

예시 필드:

- `kind`
- `created_at`
- `scope`
- `status` (`created`, `skipped`, `restored`, `failed`)
- `reason`
- `db_sha256`
- `uploads_fingerprint`
- `manifest_sha256`
- `source_backup_path`
- `target_backup_path`
- `remote_object_path`
- `remote_upload_status`

이 메타는 사람이 로그를 읽지 않고도
- 왜 스킵되었는지
- 무엇을 기준으로 비교했는지
- QA가 어떤 운영 백업본을 반영했는지
를 바로 확인할 수 있게 해줍니다.

## QA 복원 규칙

QA는 운영 복제 검증 환경이므로 아래 원칙을 둡니다.

1. QA 로컬 수정사항은 보호 대상이 아니다.
2. 주간 복원 시 QA 데이터는 덮어쓴다.
3. 복원 직후 자동 검증이 실패하면:
   - QA 적용 실패로 기록
   - 직전 QA 롤백본 복원
   - 운영에는 영향 없음
4. QA 복원 기본 소스는 운영 로컬 latest full이다.
5. GCS는 운영 장애 시 대체 소스로 사용한다.

## 검증 규칙

### 운영 백업 검증

- 생성 직후 SQLite `quick_check`
- 백업 파일 존재 여부 및 크기 확인
- manifest 기록

### QA 동기화 검증

복원 후 아래를 자동 실행합니다.

1. `/health`
2. 로그인
3. 라이브러리 현황판
4. 보유 상품 검색
5. 구매 수입 미리보기

## 장애 대응

### 운영 백업 실패

- 실패 로그 기록
- 기존 최근 성공본 유지
- 다음 스케줄에서 재시도

### QA 복원 실패

- QA만 롤백
- 운영에는 영향 없음
- 최근 성공 QA 적용본으로 되돌림

### 운영 장비 장애

- 로컬 백업이 손상되거나 디스크 접근이 불가능하면
  - GCS의 최신 `DB` 또는 `FULL` 백업을 내려받아 복구
- 즉 GCS는 일상 검증 경로가 아니라 재해복구 경로다

### GCS 업로드 실패

- 로컬 백업이 성공했으면 전체 백업은 성공으로 본다
- 단, 메타에는 `remote_upload_status=failed` 기록
- 다음 백업 시 다시 업로드 시도 가능

## 구현 원칙

1. 기존 `_create_local_db_backup`, `_create_local_full_backup_bundle`를 최대한 재사용
2. 백업 정책의 핵심 스케줄은 앱 내부가 아니라 `launchd`가 담당
3. 스킵 여부는 “파일 존재 여부”가 아니라 `hash/fingerprint`로 판단
4. 운영/QA 경로는 절대 공유하지 않음
5. GCS 업로드 실패가 로컬 백업 성공을 뒤집지는 않음

## GCS 운영 기준

### 권장 구성

- 버킷: 백업 전용 1개
- 스토리지 클래스: 시작은 `Standard`
- 위치:
  - 단순성과 지연시간 우선이면 `Seoul`
  - 재해 분산 우선이면 `ASIA`

### 버킷 보호

- `soft delete` 활성화 권장
- lifecycle로 일일/주간 보관 기간 자동 정리

### 인증

- macOS 서버에는 업로드 전용 service account 사용
- 권한은 최소한으로 제한
  - `storage.objects.create`
  - `storage.objects.get`
  - `storage.objects.list`
  - 필요 시 `storage.objects.delete`

## 성공 기준

다음이 만족되면 설계 성공입니다.

1. 운영 DB 백업이 하루 1회 자동 수행된다.
2. 변경이 없으면 새 백업 파일이 쌓이지 않는다.
3. 주간 full bundle이 생성된다.
4. QA가 주 1회 운영 최신 full bundle을 반영한다.
5. QA 반영 후 검증과 실패 시 롤백 기준이 자동화된다.
6. 생성된 백업이 GCS에도 이중 보관된다.
