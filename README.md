# Music Library Management Console

음반/굿즈 라이브러리 운영을 위한 내부 관리 콘솔입니다.  
한 저장소 안에서 `등록`, `메타 보강`, `마스터 정리`, `장식장 배치`, `예외 처리`, `백업/복구`까지 이어지는 운영 흐름을 다룹니다.

## 현재 기준 문서

- 운영 매뉴얼: [docs/management_tool_manual.md](docs/management_tool_manual.md)
- 운영자용 ERD 요약: [docs/library_erd_operator.md](docs/library_erd_operator.md)
- 개발자용 ERD 상세: [docs/library_erd.md](docs/library_erd.md)
- 구매 내역 수입 가이드: [docs/purchase_mail_import.md](docs/purchase_mail_import.md)
- 상용화 체크리스트: [docs/go_live_checklist.md](docs/go_live_checklist.md)
- macOS QA/운영 런북: [docs/macos_qa_prod_runbook.md](docs/macos_qa_prod_runbook.md)
- 자격증명 회전 런북: [docs/secret_rotation_runbook.md](docs/secret_rotation_runbook.md)
- CSV 샘플: [docs/csv_import_sample.csv](docs/csv_import_sample.csv)

## 화면별 역할

- `대시보드`
  실제 장식장/칸 배치 운영, 이동, 복구
- `운영 홈`
  현장 조회, 요청곡 응대, 현재/직전 위치 확인
- `검색/관리`
  보유 상품 상세 수정, 마스터 연결 상태 확인
- `소스 보강`
  Discogs, ManiaDB, Aladin 기반 메타 보강
- `등록/수집`
  간편 등록, 구매 내역 수입, CSV 대량 입력, 마스터 정리
- `운영/연계`
  구조 관리, 예외 큐, 계정, 백업/복원, 메타 동기화

## 문서 구조

- `docs/`
  현재 운영 기준 문서와 앱이 직접 링크하는 산출물
- `docs/qa/`
  단일 QA 기준 시트와 배포/검증 증적
- `docs/superpowers/specs/`
  설계 기록
- `docs/superpowers/plans/`
  구현 계획 기록

`docs/superpowers/*`는 개발 이력 보관용입니다. 운영자가 바로 참고해야 하는 최종 문서는 `docs/`와 `docs/qa/`를 기준으로 봅니다.
