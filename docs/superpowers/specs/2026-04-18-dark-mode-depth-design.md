# Dark Mode Depth Design

## Goal

다크 모드에서 `배경 → 주요 패널 → 패널 내부 서브패널`의 깊이 차를 더 분명하게 만들어, 긴 화면에서도 영역 구분이 빠르게 읽히도록 한다.

## Problem

- 현재 night 테마는 전체 톤이 안정적이지만, 대형 콘솔 화면에서는 카드와 카드 내부 툴바/서브패널의 명도 차가 작다.
- 그 결과 정보 계층은 존재하지만, 시각적으로는 납작하게 보여 집중 대상이 늦게 잡힌다.
- 이번 작업의 핵심은 텍스트 색을 바꾸는 것이 아니라, 패널 계층의 깊이를 더 명확하게 만드는 것이다.

## Constraints

- 기존 레이아웃과 상호작용은 유지한다.
- 오렌지/시안 등의 강조색 체계는 유지한다.
- day 테마는 변경하지 않는다.
- 토큰 기반 구조를 우선 활용하고, 토큰만으로 부족한 경우에만 국소 오버라이드를 추가한다.

## Approaches

### 1. Depth A

- night 토큰의 surface/panel/border만 조정한다.
- 쉘, admin panel, dashboard panel, soft panel 간의 톤 차를 한 단계 벌린다.
- 기존 화면 인상을 거의 유지하면서 깊이만 보강한다.

장점:
- 가장 안전하다.
- 기존 색채 체계가 흐트러지지 않는다.
- 광범위한 회귀 위험이 낮다.

단점:
- 효과가 너무 약하면 일부 화면에서는 체감이 제한될 수 있다.

### 2. Depth B

- Depth A보다 더 크게 명도 차를 벌리고, 카드 그림자와 경계선을 강화한다.
- 콘솔형 밀도를 더 강하게 만든다.

장점:
- 카드와 서브패널 분리가 매우 분명하다.

단점:
- 전체 인상이 무거워지고 피로도가 올라갈 수 있다.
- 기존 운영 화면과의 연속성이 약해질 수 있다.

## Recommendation

`Depth A`를 적용한다.

이유:
- 사용자는 가독성 향상을 원하지만, 기존 운영 화면의 분위기를 크게 바꾸길 원하지는 않았다.
- 현재 구조는 이미 토큰화가 되어 있어, 토큰 조정만으로도 상당수 화면에서 계층 분리가 같이 개선된다.
- 이번 작업은 “다크 모드를 더 다듬기”가 목적이므로, 강한 재해석보다 안전한 깊이 보강이 맞다.

## Implementation Scope

수정 대상 토큰:

- `body[data-theme="night"]`
  - `--theme-shell-surface`
  - `--theme-shell-surface-2`
  - `--theme-shell-border`
  - `--theme-admin-panel-bg`
  - `--theme-admin-panel-bg-2`
  - `--theme-admin-panel-border`
  - `--theme-dashboard-panel`
  - `--theme-dashboard-panel-soft`
  - `--theme-dashboard-border`

국소 조정 후보:

- shell utility/header
- admin console result/panel surfaces
- dashboard console statusbar/panel/soft surfaces

비수정 범위:

- layout/grid
- accent semantics
- locale/theme toggle behavior
- day theme token set

## Verification

- 관련 정적 테스트는 night/day theme token expectations를 함께 점검한다.
- 구현 후에는 shell utility, admin panel, dashboard surface 관련 테스트를 다시 실행한다.
- 결과 확인 기준:
  - 같은 화면에서 카드와 서브패널이 더 빠르게 분리되어 보일 것
  - 텍스트 대비는 유지되고, 포인트 색은 과도하게 튀지 않을 것
