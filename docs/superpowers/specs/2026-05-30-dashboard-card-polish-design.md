# Dashboard Card Polish — Design Spec
**Date:** 2026-05-30  
**Scope:** `app/static/index.html` — CSS + 6개 render 함수  
**Approach:** B — CSS 기반 刷新 + 핵심 카드 재작성

---

## 1. 문제 정의

현재 대시보드 카드의 문제점:
- 모든 바가 3–6px로 시각적 무게 없음
- `<table>` + inline style 남용 → 오래된 웹 느낌
- 수치보다 구조가 먼저 눈에 들어옴 (계층 역전)
- 이모지 아이콘 → 아마추어 인상
- 폰트 크기 0.6–0.7rem → 읽기 어려움
- 컬러 사용 무분별 (인라인 hex 혼재)

---

## 2. 디자인 원칙

| 원칙 | 적용 |
|---|---|
| **숫자가 히어로** | 카드 상단: 히어로 수치 1개 (1.6–2rem mono). 구조·레이블은 보조 |
| **배경은 중립, 색상은 숫자에** | 배경 틴트 금지. 상태/도메인 색상은 수치 텍스트 컬러로만 표현 |
| **정렬 일관성** | 타일 내부 좌상단 정렬 통일 (숫자 → 레이블 순) |
| **바 최소 높이 8px** | 3–6px 바 전면 폐기. 8–10px으로 시각적 무게 확보 |
| **테이블 제거** | `<table>` → flex progress bar 그룹으로 교체 |

---

## 3. CSS 공통 토큰 변경

```css
/* 기존 → 신규 */
.dash-compare-bar      { height: 3px → 8px }
.dash-reg-month-bar    { height: 6px → 10px }
.dash-artist-timeline  { height: 8px → 10px }
.dash-completeness-bar { width: 60px (fixed) → flex: 1 (전폭) }
.dash-compare-row .count { font-size: 0.68rem → 0.75rem; opacity: 0.65 → 1.0; color: 도메인 색상 }
```

신규 추가 클래스:
- `.dash-tile-grid` — 1px 격자선 구분 타일 컨테이너 (2×3 또는 3×2)
- `.dash-tile` — 균일 배경 타일 (좌상단 정렬, hover 효과)
- `.dash-tile__num` — 1.8rem mono 히어로 숫자
- `.dash-tile__lbl` — 0.62rem muted 레이블
- `.dash-fin-hero` — 재정 인사이트 총액 히어로 블록
- `.dash-fin-bar-row` — 8px 도메인 바 행
- `.dash-meta-source-row` — 소스별 progress bar 그룹

---

## 4. 카드별 재작성 명세

### 4-A. 콜렉터 가치 (`renderDashboardCollector`)

**레이아웃:** 3×2 `.dash-tile-grid`

| 타일 | 수치 | 색상 |
|---|---|---|
| 싸인본 | `d.signed_items` | `#fbbf24` |
| 한정반 | `d.limited_items` | `#a78bfa` |
| 멀티디스크 | `d.multi_disc_items` | `#22d3ee` |
| OBI | `d.obi_items` | `#f9a8d4` |
| 홍보반 | `d.promo_items` | `#fb923c` |
| 박스세트 | `d.box_set_items` | `#6b7280` |

변경: 이모지 제거 → 숫자 색상으로만 구분. 배경 균일 다크.

---

### 4-B. 예외 알림 (`renderDashboardAlerts`)

**레이아웃:** 3×2 `.dash-tile-grid` (콜렉터와 동일 구조)

| 항목 | 조건 | 숫자 색상 |
|---|---|---|
| 소스 미연결 | > 0 | `#f87171` (critical) |
| 마스터 미연결 | > 0 | `#f87171` (critical) |
| 커버 없음 | > 0 | `#fb923c` (warning) |
| 장르 없음 | > 0 | `#fb923c` (warning) |
| 미배치 | > 0 | `#fb923c` (warning) |
| 도메인 미지정 | 항상 | `#60a5fa` (info) |
| 모든 항목 0 | = 0 | `#4ade80` (ok) |

변경: 배경 틴트 제거. 상태는 숫자 텍스트 색상만으로 표현.

---

### 4-C. 재정 인사이트 (`renderDashboardFinance`)

**레이아웃:**  
```
[히어로 총액 블록]           ← ₩XX,XXX,XXX (2rem, #4ade80)
[평균 단가 stat] [통화 stat]  ← 2칸 stat row
[구분선]
[도메인 바 목록]             ← 8px 바, 우측 ₩ 수치
```

변경: 4칸 균등 그리드 → 계층 구조. 총액이 시각적 앵커.

---

### 4-D. 장르 × 도메인 (`renderDashboardGenreDomain`)

**레이아웃:** 2열 그리드 (KOREA / WESTERN)

변경:
- 바 높이: 3px → 8px
- 수치 색상: 도메인 색상과 일치 (KOREA `#4ade80`, WESTERN `#60a5fa`)
- 컬럼 헤더: 2px 언더라인 액센트 + 컬러 텍스트

---

### 4-E. 등록 페이스 (`renderDashboardRegImport`)

**레이아웃:**  
```
[월별 스파크 바 목록]   ← 10px 그라데이션 바 (#0f766e → #14b8a6)
[수입대기 강조 블록]   ← 수치 2rem + 배지 (count > 0 시 orange 틴트 패널)
```

변경: 바 6px → 10px. 수입대기 count를 독립 패널로 분리.

---

### 4-F. 메타 완성도 (`renderDashboardMetaSource`)

**레이아웃:** 소스별 그룹, 각 그룹 내 3개 progress bar

```
[소스명]  마스터 ──────────── 99%
          커버   ────────── 98%
          장르   ──────     58%
[구분선]
[소스명]  ...
```

변경: `<table>` 완전 제거 → flex `.dash-meta-source-row`. 바 전폭 사용.

---

## 5. 변경하지 않는 것

- `renderDashboardHeatmap` — 히트맵 구조 유지
- `renderDashboardArtistTimeline` — CSS 토큰 변경으로 자동 개선
- `renderDashboardMoveHeatmap` — CSS 토큰 변경으로 자동 개선
- `renderDashboardRecentReg` — CSS 토큰 변경으로 자동 개선
- `renderDashboardPurchaseFlow` — CSS 토큰 변경으로 자동 개선
- 카드 외곽 shell (`.dash-card`, `.dash-card__head`) — 유지
- KPI 바 — 유지
- 백엔드 — 변경 없음

---

## 6. 구현 순서

1. CSS 공통 토큰 추가/수정 (`<style>` 블록 내 `dash-*` 규칙)
2. 신규 CSS 클래스 추가 (`.dash-tile-grid`, `.dash-tile`, `.dash-fin-*`, `.dash-meta-*`)
3. `renderDashboardCollector` 재작성
4. `renderDashboardAlerts` 재작성
5. `renderDashboardFinance` 재작성
6. `renderDashboardGenreDomain` 재작성
7. `renderDashboardRegImport` 재작성
8. `renderDashboardMetaSource` 재작성
9. QA 동기화 → 브라우저 검증

---

## 7. 검증 기준

- 모든 바 높이 ≥ 8px
- 카드 내 `<table>` 태그 0개 (6개 render 함수 대상)
- 타일 내 이모지 0개
- 숫자 font-size ≥ 1.6rem (히어로), ≥ 0.75rem (보조)
- 배경 틴트 색상 없음 (`.dash-tile` 배경 균일)
- QA 다크/라이트 테마 모두 정상 렌더링
