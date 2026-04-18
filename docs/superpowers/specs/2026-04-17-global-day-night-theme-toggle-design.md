# Global Day/Night Theme Toggle Design

## Goal

전체 관리 콘솔과 운영 홈, 장식장/커버플로우까지 하나의 수동 주간/야간 테마 토글로 전환한다. 토글 상태는 브라우저에 저장하고, 저장값이 없으면 기존 기본값인 야간모드로 시작한다.

## Scope

- 포함:
  - 운영 홈/관리/미디어/컬렉터블/등록/작업대
  - 장식장/슬롯 점유/커버플로우/상세 관리
  - 헤더 유틸 영역
- 제외:
  - 시스템 테마 연동
  - 시간대 자동 전환
  - 서버 저장

## Approach

`body[data-theme="night"|"day"]`를 전역 상태로 두고, 기존 `--admin-console-*` 계열 토큰을 테마별로 재정의한다. 현재 야간 테마를 기준으로 유지하고, 주간 테마는 동일한 대비 구조를 가진 저채도 밝은 팔레트로 추가한다.

## UI

- 언어 선택기 옆에 주간/야간 스위치 추가
- 스위치는 compact utility 패턴을 재사용
- 기본 표시는 아이콘 + 짧은 상태 텍스트
- 토글 상태 저장 키: `hahahoho.ui.theme`

## State Model

초기화 순서:
1. `localStorage["hahahoho.ui.theme"]`
2. 없으면 `"night"`

적용:
- `document.body.dataset.theme = "night" | "day"`

## Styling Strategy

- 우선 토큰:
  - `--admin-console-panel-bg`
  - `--admin-console-panel-bg-2`
  - `--admin-console-panel-border`
  - `--admin-console-text`
  - `--admin-console-text-muted`
  - `--admin-console-text-meta`
  - `--admin-console-accent`
  - 링크/상태/경고 색
- 토큰 미사용 하드코딩 패널은 1차 범위에서 day/night override 추가

## Verification

- 토글 마크업 존재
- `localStorage` 저장/복원 동작 존재
- `body[data-theme]` 적용 함수 존재
- 주요 shell이 토큰 기반 색을 사용
- QA에서 야간/주간 전환 후 운영 홈, 장식장, 상세 관리, 컬렉터블, 예외 큐를 확인
