# Dashboard Card Redesign Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development. Steps use checkbox syntax.

**Goal:** Redesign dashboard widget cards with 4 sizes (1/1, 3/4, 1/2, 1/4), 7 card roles, interactive hover/click.

**Architecture:** Consolidate 3 card CSS classes into single .dash-card base. Size via data-size, content via data-role. CSS-only interactions + minimal JS for sparklines and navigation.

**Tech Stack:** Single HTML/CSS/JS file (app/static/index.html), CSS custom properties, vanilla JS.

---

## File Map
| File | Change |
|------|--------|
| app/static/index.html | All HTML, CSS, JS |

---

### Task 1: Rename data-widget-size to data-size
- [ ] Update CSS grid rules (lines ~12538-12560)
- [ ] Update HTML card attributes (wide→1/1, medium→1/2)
- [ ] Update JS references to widget-size
- [ ] Commit

### Task 2: Consolidate into .dash-card base
- [ ] Create .dash-card shared shell (bg, border, shadow, hover lift)
- [ ] Remove .dash-kpi-card, .dash-chart-card, .dash-activity-card CSS
- [ ] Update HTML class attributes
- [ ] Commit

### Task 3: Card head + accent dot
- [ ] Add .dash-card__head, .dash-card__dot CSS
- [ ] Add data-accent attribute to all cards
- [ ] Replace old accent-border-top with dot
- [ ] Commit

### Task 4: 1/4 card variants
- [ ] Add metric-only CSS (big number + label + delta)
- [ ] Add spark CSS (small KPI + inline sparkline SVG)
- [ ] Add alert-badge CSS (alert list + counts)
- [ ] Create card-album-of-day, card-quick-search HTML
- [ ] Commit

### Task 5: 1/2 card interactions
- [ ] Add bar-list hover + tooltip CSS
- [ ] Add timeline highlight CSS
- [ ] Add trend-spark hover CSS
- [ ] Commit

### Task 6: JS interaction layer
- [ ] Sparkline draw animation (stroke-dasharray)
- [ ] Bar-list click → filter navigation
- [ ] Alert click → exception queue navigation
- [ ] Commit

### Task 7: Responsive adaptation
- [ ] Update responsive breakpoints (1080px, 760px)
- [ ] Resize observer for label truncation
- [ ] Commit

### Task 8: Cleanup
- [ ] Remove old accent-border rules
- [ ] Verify no hard-coded colors
- [ ] CSS balance check
- [ ] Commit
