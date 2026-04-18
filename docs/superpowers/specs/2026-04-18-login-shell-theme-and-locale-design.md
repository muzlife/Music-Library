# Login Shell Theme And Locale Design

## Goal

로그인 화면을 운영/관리 화면과 같은 시각 계열로 맞추고, 로그인 전에도 `언어 선택`과 `주/야간 모드`를 조절할 수 있게 만든다.  
로그인 화면에서 바꾼 설정은 로그인 후 메인 콘솔에서도 그대로 유지돼야 한다.

## Current State

- 로그인 화면은 [app/static/login.html](/Volumes/Works/07.hahahoho/app/static/login.html) 의 독립 정적 파일이다.
- 현재 로그인 화면은 고정 밝은 테마만 제공한다.
- 운영/관리 화면은 [app/static/index.html](/Volumes/Works/07.hahahoho/app/static/index.html) 에서 `localStorage` 기반으로 `locale/theme`를 유지한다.
- 로그인 화면은 이 저장 상태를 읽거나 쓸 수 없다.
- 결과적으로 로그인 화면과 본 콘솔의 헤더, 컬러 시스템, 상태 유지 방식이 분리돼 있다.

## Chosen Approach

로그인 화면 상단에 `로그인 전용 shell utility row`를 추가한다.

포함 요소:
- 언어 선택기
- 주/야간 모드 토글

제외 요소:
- 홈 버튼
- 관리 버튼
- 운영 버튼
- 문서 링크
- 세션/로그아웃 액션

핵심 원칙은 `시각은 shell utility 계열로 맞추되, 기능은 로그인 화면에 필요한 최소 범위만 둔다`이다.

## Alternatives Considered

### 1. 색상만 맞추고 utility control은 두지 않는 방식

장점:
- 구현이 가장 단순하다.

단점:
- 사용자가 로그인 전 언어/테마를 조정할 수 없다.
- 로그인 후에만 shell utility를 보게 되어 경험이 끊긴다.

### 2. 메인 shell utility 전체를 거의 그대로 이식하는 방식

장점:
- 구조적 일관성이 가장 높다.

단점:
- 로그인 화면에 불필요한 버튼과 내비 문맥이 들어온다.
- 로그인 전 화면이 과하게 무거워진다.

### 3. 로그인 전용 utility row를 별도로 구성하는 방식

장점:
- 필요한 기능만 남겨 로그인 화면의 단순함을 유지한다.
- 언어/테마 상태를 본 콘솔과 자연스럽게 공유할 수 있다.

단점:
- shell utility의 일부를 로그인 화면에 맞게 재구성해야 한다.

이 설계는 `3번`을 채택한다.

## Scope

### Included

- 로그인 화면 상단 utility row 추가
- 로그인 화면의 day/night token 추가
- 언어 선택 UI 추가
- 주/야간 토글 UI 추가
- 기존 콘솔과 동일한 `localStorage` 키 사용
- 로그인 후 설정 유지
- 로그인 화면 텍스트의 locale 반영

### Excluded

- 시스템 테마 자동 연동
- 서버 저장
- 로그인 화면에서의 역할별 랜딩 변경
- 추가 헤더 액션
- 인증 API 변경

## UI Structure

로그인 화면은 세 덩어리로 구성한다.

1. `login-shell-utility`
- 좌측: 언어 선택기
- 우측: 주/야간 토글

2. `login-shell-card`
- 제목
- 설명문
- 아이디/비밀번호 입력
- 로그인 버튼
- 상태 메시지

3. `login-shell-note`
- 필요 시 관리자/현장 운영자 진입 차이를 짧게 설명하는 보조 문구

메인 콘솔과 달리 별도 탭/내비게이션 행은 두지 않는다.

## State Model

로그인 화면은 메인 콘솔과 같은 **저장 키 문자열**을 사용한다.

- locale storage key literal: `hahahoho.appLocale.v1`
- theme storage key literal: `hahahoho.uiTheme.v1`

구현 경계는 `login.html` 한 파일이므로, 이번 범위에서는 별도 공통 스크립트를 추출하지 않는다.  
대신 로그인 화면 안에 위 두 literal key를 직접 적고, 메인 콘솔과 동일한 값만 사용한다.

초기화 순서:
1. 저장된 locale/theme 읽기
2. 값이 유효하지 않으면 기본값 적용
   - locale: `ko`
   - theme: `night`

지원 locale 집합은 메인 shell과 동일하게 아래 셋으로 고정한다.

- `ko`
- `en`
- `ja`

적용 방식:
- `document.documentElement.lang` 갱신
- `document.body.dataset.theme = "day" | "night"`
- locale 변경 시 로그인 화면의 텍스트, 버튼 라벨, 상태 문구를 다시 렌더

로그인 성공 후 `/ops` 또는 후속 라우트로 이동하면, 본 콘솔이 같은 저장값을 읽어 그대로 이어진다.

## Styling Strategy

로그인 화면은 별도 팔레트를 만들지 않고 shell/admin 계열과 같은 명도 구조를 따른다.

### Night

- 배경: shell night tone 기반 radial/linear surface
- 카드: `theme-shell-surface` / `theme-admin-panel-bg` 계열
- 텍스트: `theme-shell-text`, `theme-shell-text-muted`
- 강조: `theme-shell-accent`

### Day

- 배경: 현재 shell day tone 기반 밝은 금속성 회색
- 카드: `theme-shell-surface`, `theme-shell-surface-2`
- 텍스트: `theme-shell-text`, `theme-shell-text-muted`
- 강조: `theme-shell-accent`

### Control Style

- 언어 선택기: 현재 shell locale picker와 같은 아이콘/compact pill 계열
- 테마 토글: 현재 shell theme toggle과 동일한 sun/pill/moon 구조
- 로그인 버튼: 운영/관리의 primary button 계열과 같은 accent 체계
- 입력창: console input과 같은 border/focus ring 체계

## Behavior

### Locale

- 로그인 화면에서 locale를 바꾸면:
  - 제목
  - 설명문
  - `아이디`
  - `비밀번호`
  - `로그인`
  - `로그인 중...`
  - `로그인 실패`
  를 즉시 다시 렌더한다.

로그인 화면의 i18n은 메인 콘솔의 대형 `I18N_MESSAGES` 블록을 복사하지 않는다.  
`login.html` 안에는 로그인 화면에서 실제로 쓰는 최소 문구만 가진 **login-scoped message table**만 둔다.

### Theme

- 로그인 화면에서 theme를 바꾸면 즉시 `body[data-theme]`가 변경된다.
- page reload 후에도 같은 테마가 유지된다.

### Auth Flow

- `/auth/login` 요청/응답 구조는 그대로 유지한다.
- 성공 시 리다이렉트 동작은 그대로 둔다.
- 실패 시 상태 메시지만 locale/theme에 맞는 스타일로 보여준다.

실패 메시지 정책:

- 서버가 내려주는 한국어 detail을 그대로 번역하지 않는다.
- 대신 `401` 응답이면서 detail이 아래 정확한 문자열과 일치할 때만, 클라이언트에서 locale별 표준 문구로 치환한다.
  - `아이디 또는 비밀번호가 올바르지 않습니다.`
  - 예: `아이디 또는 비밀번호가 올바르지 않습니다.`
- 그 외 예상 밖 오류는 서버 detail을 우선 노출한다.

이렇게 하면 인증 API는 그대로 두면서도, 대표적인 로그인 실패 문구는 locale에 맞춰 보여줄 수 있다.

## Implementation Boundaries

수정 범위는 가능한 한 좁게 유지한다.

### Primary File

- [app/static/login.html](/Volumes/Works/07.hahahoho/app/static/login.html)

### Optional Test Files

- 로그인 페이지 응답/마크업 테스트가 이미 있으면 그 파일에 추가
- 없으면 최소 범위의 로그인 정적 페이지 테스트를 새로 추가

### Do Not Change

- 인증 쿠키 로직
- `/auth/login`, `/auth/logout`, `/auth/session` 서버 동작
- 메인 콘솔 shell utility 구현

## Verification

### Automated

- `/login` 응답이 utility control 마크업을 포함한다.
- 로그인 페이지에 locale picker와 theme toggle이 존재한다.
- 로그인 페이지 스크립트가 기존 shell과 같은 storage key를 사용한다.
- 로그인 기본 폼 동작은 그대로 유지된다.

### Manual

- `day`와 `night`에서 로그인 화면이 모두 깨지지 않는다.
- 로그인 화면에서 locale/theme를 바꾸고 새로고침해도 유지된다.
- 로그인 후 메인 콘솔에서 같은 locale/theme가 유지된다.
- 실패 메시지가 day/night 모두에서 충분히 읽힌다.

## Risks

### 1. Storage key duplication drift

`index.html`과 `login.html`에 동일한 key literal을 별도로 적으면 나중에 어긋날 수 있다.  
이번 변경에서는 scope를 넓히지 않기 위해 literal 복제를 허용하되, 값은 위에서 명시한 두 문자열로 고정한다.

### 2. Login page overgrowth

shell utility를 과하게 가져오면 로그인 화면이 복잡해질 수 있다.  
이번 범위는 언어/테마만 허용하고 나머지 액션은 배제한다.

### 3. Visual mismatch due to copied partial styles

토글/locale picker를 일부만 복사하면 shell과 미묘하게 다른 UI가 될 수 있다.  
따라서 아이콘 구조와 상태 표시는 최대한 같은 패턴을 유지하되, 레이아웃만 로그인 전용으로 단순화한다.
