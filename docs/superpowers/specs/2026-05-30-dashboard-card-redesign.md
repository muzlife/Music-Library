# Dashboard Card Redesign

**Date**: 2026-05-30  
**Status**: designed

## Overview

대시보드 위젯 카드를 데이터 성격에 따라 1/1, 3/4, 1/2, 1/4 사이즈로 재정비하고, 심플 카드(1/4, 1/2) 변형을 추가하며, 인터랙티브 요소(hover 툴팁, 클릭 필터 이동, 스파크라인 애니메이션)를 도입한다.

## Grid System

| `data-size` | grid-column span | 비율 | 사용 |
|-------------|-----------------|------|------|
| `1/4` | span 1 | 25% | 단일 KPI, 스파크라인, 알림 뱃지 |
| `1/2` | span 2 | 50% | KPI+차트, 요약 리스트, 트렌드 |
| `3/4` | span 3 | 75% | 히트맵, 대형 차트 |
| `1/1` | span 4 | 100% | 컬렉션 스냅샷 |

```css
.dashboard-widget-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}
.dashboard-widget-grid .dashboard-widget-card[data-size="1/4"] { grid-column: span 1; }
.dashboard-widget-grid .dashboard-widget-card[data-size="1/2"] { grid-column: span 2; }
.dashboard-widget-grid .dashboard-widget-card[data-size="3/4"] { grid-column: span 3; }
.dashboard-widget-grid .dashboard-widget-card[data-size="1/1"] { grid-column: span 4; }

@media (max-width: 1080px) { grid-template-columns: repeat(2, 1fr); }
@media (max-width: 760px)  { grid-template-columns: 1fr; }
```

## Card Anatomy

```
┌─ dash-card ─────────────────────────────┐
│ dash-card__head:  ● accent dot  LABEL   │
│ dash-card__body:  (size-dependent)      │
│ dash-card__foot:  "지난주 +12%" (opt)   │
└─────────────────────────────────────────┘
```

## Card Variants by Role

### 1/4 Cards (3 variants)

| `data-role` | Content | Example |
|-------------|---------|---------|
| `metric` | big number + label + optional delta | 총 음반 31,247 |
| `spark` | small KPI + inline sparkline | 보강률 78.4% + ▂▃▅▆▇ |
| `alerts` | alert badge list (max 3) | ⚠ 3건 대기, ⚠ 12건 누락 |

### 1/2 Cards (4 variants)

| `data-role` | Content | Interaction |
|-------------|---------|-------------|
| `bar-list` | horizontal bars + labels | hover→tooltip, click→filter |
| `timeline` | decade bars + artist top-list | hover→highlight |
| `trend-spark` | sparkline + monthly summary | hover→data point tooltip |
| `alert-summary` | alert categories + counts | click→navigate to exception queue |

### 3/4 Card

| `data-role` | Content |
|-------------|---------|
| `heatmap` | domain × decade heatmap with row/col headers, filter controls |

### 1/1 Card

| `data-role` | Content |
|-------------|---------|
| `snapshot` | 4 KPI chips + progress bars + source/format filters |

## Data → Card Mapping

| Card ID | Label | Size | Role | Accent |
|---------|-------|------|------|--------|
| card-snapshot | 컬렉션 스냅샷 | 1/1 | snapshot | main |
| card-heatmap | 도메인 × 연대 | 3/4 | heatmap | heatmap |
| card-finance | 재정 인사이트 | 1/2 | bar-list | source |
| card-genre-domain | 장르 × 도메인 | 1/2 | bar-list | genre |
| card-format-pressing | 포맷·프레싱 | 1/2 | bar-list | format |
| card-artist-timeline | 아티스트 연대기 | 1/2 | timeline | artist |
| card-meta-source | 메타 완성도 | 1/2 | bar-list | quality |
| card-collector | 콜렉터 가치 | 1/2 | metric-grid | product |
| card-alerts | 예외 알림 | 1/4 | alert-badge | — |
| card-reg-import | 등록 페이스 | 1/2 | trend-spark | placement |
| card-move-heatmap | 이동 히트맵 | 1/2 | heatmap-mini | heatmap |
| card-recent-reg | 최근 등록 | 1/2 | top-list | product |
| card-purchase-flow | 구매 흐름 | 1/2 | trend-spark | source |
| card-climate | 실내 환경 | 1/4 | metric-only | — |
| card-album-of-day | 오늘의 음반 | 1/4 | spark | — |
| card-quick-search | 빠른 검색 | 1/4 | metric | — |

## Interactions

- **hover**: card lift (translateY -2px) + shadow increase
- **bar-list hover**: bar highlight + tooltip showing exact value
- **bar-list click**: navigate to search with that filter applied
- **sparkline**: animated draw-in on page load (stroke-dasharray)
- **sparkline hover**: data point tooltip
- **alert click**: navigate to exception queue tab
- **snapshot filter**: dropdown filters affect all visible metric cards

## Accessibility

- All text/background pairs ≥ WCAG AA 4.5:1
- Focus-visible ring on all interactive cards
- aria-label on sparklines and charts
- Keyboard-navigable card grid (Tab between cards)

## Migration Notes

- Replace `data-widget-size="wide/medium/large"` with `data-size="1/1","1/2","3/4"`
- Add `data-role` attribute to all cards
- Remove unused `.dash-kpi-card`, `.dash-chart-card`, `.dash-activity-card` classes; consolidate to `.dash-card`
- Keep existing `data-widget-id`, `data-widget-label` for JS compatibility
