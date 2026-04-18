# 상용화 체크리스트

이 문서는 `QA 검증 완료 -> 운영 반영 -> 초기 안정화`까지의 실행 체크리스트입니다.  
세부 서버 작업은 [macos_qa_prod_runbook.md](/Volumes/Works/07.hahahoho/docs/macos_qa_prod_runbook.md)를 함께 봅니다.

## 1. 배포 전 기준선

- [ ] 운영과 QA가 다른 DB 경로를 사용한다.
- [ ] 운영과 QA가 다른 세션 시크릿을 사용한다.
- [ ] 운영과 QA가 다른 구매 수입 webhook token을 사용한다.
- [ ] 운영 `daily-db`와 `weekly-full` 백업이 최근 성공 상태다.
- [ ] QA에 최신 운영 데이터 복제가 끝났다.
- [ ] QA에서 검증한 커밋 SHA가 명확하다.
- [ ] 롤백 기준 커밋과 직전 DB 백업 경로를 기록했다.

기록 항목
- 배포 대상 커밋: `5409b8cdc26939826c4abd4075f616b81560f7ae` (`main`, local commit + deploy_to_prod.sh)
- 직전 운영 커밋: `c671ff4990f8b676166fbbc09f53608266c4e2f3` (배포 직전 운영 기준 코드)
- 직전 운영 DB 백업: `/Users/matia/apps/hahahoho-prod/runtime/backups/daily-db/hahahoho-library-daily-db-20260418-063130.db`
- 배포 담당: `Codex`
- 승인자: `jingunpark`

## 2. QA 사전 검증

- [ ] QA 마스터 시트의 `environment=qa`, `phase=Pre-release`, `gate in {Blocker, Release}` 행을 이번 릴리스 기준으로 실행했다.
- [ ] `REL-001` 자동 검증 통과
  `pytest -q tests/test_ops_route_access.py tests/test_artist_context_service.py`
- [ ] `REL-002` 자동 검증 통과
  `pytest -q tests/test_ops_shell_bootstrap.py`
- [ ] `REL-003` QA 로컬/외부 health가 `200 ok`를 반환한다.
- [ ] `REL-004` 배포 대상 커밋, 롤백 백업, 승인 정보가 `qa_master_sheet.csv`에 기록됐다.
- [ ] QA 마스터 시트의 해당 행들에 `release_ref`, `evidence_ref`, `result`, `verified_at`, `executor`, `approver`가 반영됐다.

참고 문서
- QA 마스터 시트: [qa_master_sheet.csv](/Volumes/Works/07.hahahoho/docs/qa/qa_master_sheet.csv)

## 3. 운영 반영 직전

- [ ] 사용자에게 점검 시간 공지
- [ ] 운영 서버 로컬 `/health`가 현재 정상
- [ ] 운영 서버 직전 백업 생성
- [ ] 배포 스크립트 또는 GitHub Actions 입력값 재확인
- [ ] 설치가 필요한 의존성 변경 여부 확인
- [ ] 업로드/로그/백업 런타임 경로가 정상 마운트 상태인지 확인

## 4. 운영 배포 실행

- [ ] 코드 반영
- [ ] 필요 시 `pip install -r requirements.txt`
- [ ] `launchctl kickstart` 또는 배포 스크립트로 앱 재기동
- [ ] 로컬 `/health` 확인
- [ ] 외부 `https://library.muzlife.com/health` 확인
- [ ] 로그인 화면 노출 확인

## 5. 운영 스모크 체크

- [ ] QA 마스터 시트의 `environment=prod`, `phase=Post-release` 행을 실행했다.
- [ ] `REL-005` 운영 local/external health가 `200 ok`를 반환한다.
- [ ] `REL-006` 로그인과 대표 핵심 동선 smoke가 통과한다.
- [ ] 운영 스모크 결과와 잔여 리스크를 `qa_master_sheet.csv`와 배포 완료 기록에 남겼다.

## 6. 배포 후 1차 안정화

- [ ] launchd 에러 로그 확인
- [ ] 최근 1시간 5xx 여부 확인
- [ ] 구매 수입 webhook 동작 여부 확인
- [ ] 자동 백업 설정이 의도대로 유지됐는지 확인
- [ ] QA와 운영이 같은 커밋인지 다시 확인

## 7. 롤백 기준

아래 중 하나면 롤백을 검토합니다.

- 로그인 자체가 불가능하다.
- `/health`가 안정적으로 `200`을 내지 못한다.
- 검색/대시보드/구매 수입 중 두 개 이상 핵심 동선이 깨진다.
- 배포 직후 데이터 손상 또는 위치 정보 누락이 확인된다.

## 8. 롤백 절차

- [ ] 운영 앱 중지 또는 점검 유지
- [ ] 이전 커밋으로 코드 복귀
- [ ] 필요 시 직전 DB 백업 복원
- [ ] 앱 재시작
- [ ] `/health` 재확인
- [ ] 로그인/검색/대시보드 최소 스모크 재확인

## 9. 배포 완료 기록

- 배포 완료 시각:
- 최종 운영 커밋:
- 배포 방식:
- 설치 추가 작업:
- 스모크 체크 결과:
- 남은 이슈:
