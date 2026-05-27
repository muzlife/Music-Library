# 백업 보존 정책 및 QA 동기화 구현 계획

작성일: 2026-04-14

## 목표

운영은 `일일 DB 백업 + 주간 FULL 백업`, QA는 `주간 운영 반영` 구조로 정리하고, 변경이 없으면 새 산출물을 만들지 않도록 구현합니다.

## 범위

### 포함

1. DB/FULL 백업용 공통 fingerprint 메타 로직
2. 변경 없으면 스킵하는 백업 헬퍼
3. 운영 백업 스크립트 2종
4. QA 주간 복원 스크립트
5. GCS 업로드 스크립트/헬퍼
6. `launchd` 템플릿 3종
7. 런북/운영 문서 갱신

### 제외

1. UI 기반 백업 스케줄러 개편
2. 블록 단위 증분 백업

## 구현 단계

### 1단계. 백업 비교 메타 유틸 추가

대상:

- `/Volumes/Data/Works/07.hahahoho/app/main.py`
- 필요 시 `/Volumes/Data/Works/07.hahahoho/app/db.py`

작업:

1. DB snapshot SHA-256 계산 헬퍼 추가
2. uploads fingerprint 계산 헬퍼 추가
3. 백업 메타 JSON 읽기/쓰기 헬퍼 추가
4. 직전 성공본과 비교해 `created/skipped`를 결정하는 공통 함수 추가

검증:

- 동일 DB 두 번 백업 시 두 번째는 `skipped`
- DB 변경 후 다시 백업 시 새 파일 생성

### 2단계. 운영 일일/주간 스크립트 작성

대상:

- `/Volumes/Data/Works/07.hahahoho/deploy/scripts/backup_daily_db.sh`
- `/Volumes/Data/Works/07.hahahoho/deploy/scripts/backup_weekly_full.sh`

작업:

1. 운영 앱 루트 입력
2. `.env.local` 로드
3. 백업 생성 또는 스킵
4. 보관 개수 정리
5. 메타 JSON 기록

검증:

- 임시 런타임 경로에서 스크립트 실행
- 동일 데이터 재실행 시 스킵 확인
- 보관 개수 초과 시 오래된 파일 정리 확인

### 3단계. QA 주간 복원 스크립트 작성

대상:

- `/Volumes/Data/Works/07.hahahoho/deploy/scripts/sync_prod_backup_to_qa.sh`

작업:

1. 운영 full backup 디렉터리에서 최신 bundle 선택
2. QA 직전 적용 manifest와 비교
3. 동일하면 스킵
4. 다르면 QA로 복원
5. QA 앱 재시작
6. smoke/preflight 실행
7. 실패 시 직전 QA 복원본으로 롤백

검증:

- 동일 bundle 재적용 시 스킵
- 새 bundle 적용 시 QA 데이터 갱신 확인

### 4단계. GCS 오프사이트 업로드 추가

대상:

- `/Volumes/Data/Works/07.hahahoho/deploy/scripts/upload_backup_to_gcs.sh`
- 필요 시 공통 헬퍼 스크립트

작업:

1. 로컬 백업 메타 JSON 읽기
2. `created` 상태일 때만 업로드
3. DB/FULL/metadata를 prefix에 맞춰 업로드
4. 업로드 성공/실패 상태를 메타에 기록

검증:

- `created` 백업은 업로드 수행
- `skipped` 백업은 업로드 스킵
- 업로드 실패 시 로컬 백업 성공 상태는 유지

### 5단계. launchd 자산 추가

대상:

- `/Volumes/Data/Works/07.hahahoho/deploy/templates/launchd/com.muzlife.backup-daily-db.plist`
- `/Volumes/Data/Works/07.hahahoho/deploy/templates/launchd/com.muzlife.backup-weekly-full.plist`
- `/Volumes/Data/Works/07.hahahoho/deploy/templates/launchd/com.muzlife.qa-sync-weekly.plist`

작업:

1. 운영 일일 DB 백업 스케줄 정의
2. 운영 주간 FULL 백업 스케줄 정의
3. QA 주간 동기화 스케줄 정의

검증:

- `plutil -lint`
- 경로 치환 스크립트로 실제 설치 가능 여부 확인

### 6단계. 문서/런북 갱신

대상:

- `/Volumes/Data/Works/07.hahahoho/docs/macos_qa_prod_runbook.md`
- 필요 시 운영 매뉴얼/체크리스트

작업:

1. 일일 DB, 주간 FULL, 주간 QA 반영 정책 반영
2. 스킵 로직과 메타 파일 위치 설명 추가
3. GCS 오프사이트 업로드 절차 추가
4. 롤백 절차 명시

## 테스트 전략

### 자동 테스트

1. 메타 비교 유틸 테스트
2. 스크립트 단위 테스트
3. `plutil`/셸 문법 검사
4. GCS 업로드 명령 구성 검증(모의 경로)

### 수동 검증

1. 운영 임시 경로에서 백업 두 번 실행
2. 두 번째 실행 스킵 확인
3. 생성된 백업의 GCS 업로드 조건 확인
4. QA 임시 경로에 복원
5. QA 재기동 후 `/health` 확인

## 완료 기준

1. 운영 DB 일일 백업 스크립트가 동작
2. 주간 FULL 백업 스크립트가 동작
3. 동일 데이터에서 스킵이 동작
4. 생성된 백업이 GCS에도 업로드된다
5. QA 주간 반영 스크립트가 동작
6. 관련 `launchd` 템플릿과 런북이 정리됨
