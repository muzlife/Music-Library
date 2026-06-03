# Dashboard Card Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `app/static/index.html` CSS 토큰 개선 + 6개 render 함수 재작성으로 대시보드 카드를 현대적으로 쇄신한다.

**Architecture:** 단일 파일(`index.html`) 내 `<style>` 블록과 인라인 JS만 수정한다. CSS 먼저 확보 후 render 함수를 교체하는 순서로 진행해 중간 커밋마다 렌더링이 깨지지 않도록 한다.

**Tech Stack:** vanilla CSS, vanilla JS (no build step), `rsync` QA 동기화

---

## 파일 구조

수정 파일 1개:
- `app/static/index.html`
  - CSS 블록 (line ~12700–12780): 기존 토큰 수정 + 신규 클래스 추가
  - JS 블록 (line ~41036–41177): 6개 render 함수 교체

---

## Task 1: CSS 공통 토큰 수정

**Files:**
- Modify: `app/static/index.html:12701-12703` (dash-compare 바)
- Modify: `app/static/index.html:12710` (dash-artist-timeline)
- Modify: `app/static/index.html:12719` (dash-completeness-bar)
- Modify: `app/static/index.html:12729` (dash-reg-month-bar)

- [ ] **Step 1: `.dash-compare-bar` 높이 3px → 8px, 너비 고정 제거**

`app/static/index.html` line 12702를 다음으로 교체:
```css
.dash-compare-bar { flex: 1; height: 8px; border-radius: 4px; background: rgba(128,128,128,0.10); overflow: hidden; flex-shrink: 0; }
```

- [ ] **Step 2: `.dash-compare-row .count` 수치 강조**

`app/static/index.html` line 12701을 다음으로 교체:
```css
.dash-compare-row .count { font-family: var(--font-mono); font-size: 0.75rem; font-weight: 700; width: 36px; text-align: right; }
```

- [ ] **Step 3: `.dash-artist-timeline` 높이 8px → 10px**

`app/static/index.html` line 12710을 다음으로 교체:
```css
.dash-artist-timeline { flex: 1; height: 10px; border-radius: 5px; background: rgba(128,128,128,0.1); position: relative; }
```

- [ ] **Step 4: `.dash-completeness-bar` 고정 너비 제거 → flex**

`app/static/index.html` line 12719를 다음으로 교체:
```css
.dash-completeness-bar { flex: 1; height: 6px; border-radius: 3px; background: rgba(128,128,128,0.10); overflow: hidden; display: inline-block; vertical-align: middle; margin: 0 4px; }
```

- [ ] **Step 5: `.dash-reg-month-bar` 높이 6px → 10px**

`app/static/index.html` line 12729를 다음으로 교체:
```css
.dash-reg-month-bar { flex: 1; height: 10px; border-radius: 5px; background: rgba(128,128,128,0.1); overflow: hidden; }
```

- [ ] **Step 6: 구문 검증**

```bash
python3 -c "
import re, subprocess, tempfile, os
html = open('app/static/index.html', encoding='utf-8').read()
start = html.find('<script>') + len('<script>')
end = html.rfind('</script>')
js = html[start:end]
with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as tf:
    tf.write(js); tmp=tf.name
r = subprocess.run(['node', '--check', tmp], capture_output=True, text=True)
print('OK' if not r.stderr else r.stderr[:200])
os.unlink(tmp)
"
```
Expected: `OK`

- [ ] **Step 7: 커밋**

```bash
git add app/static/index.html
git commit -m "style: thicken dashboard bars — compare 8px, reg 10px, artist 10px"
```

---

## Task 2: 신규 CSS 클래스 추가

**Files:**
- Modify: `app/static/index.html` — line 12747 바로 뒤에 삽입 (`.dash-alert-item.alert-info` 다음)

- [ ] **Step 1: `.dash-tile-grid` / `.dash-tile` / `.dash-tile__num` / `.dash-tile__lbl` 추가**

line 12748 (`.dash-alert-item.alert-info { ... }` 줄) 바로 다음에 삽입:
```css
    /* ── tile grid (콜렉터·알림 공용) ── */
    .dash-tile-grid {
      display: grid; grid-template-columns: repeat(3, 1fr);
      gap: 1px; background: rgba(128,128,128,0.12);
      border-radius: 10px; overflow: hidden;
    }
    .dash-tile {
      background: var(--dash-card-bg);
      padding: 12px 10px 10px 12px;
      display: flex; flex-direction: column; gap: 3px;
      cursor: pointer; transition: background 0.12s;
    }
    .dash-tile:hover { background: var(--dash-card-bg-hover); }
    .dash-tile__num {
      font-family: var(--font-mono);
      font-size: 1.8rem; font-weight: 800;
      letter-spacing: -0.06em; line-height: 1;
    }
    .dash-tile__lbl {
      font-size: 0.62rem; font-weight: 600;
      text-transform: uppercase; letter-spacing: 0.05em;
      color: var(--theme-dashboard-text-muted);
    }
```

- [ ] **Step 2: 재정 인사이트용 CSS 추가** (`.dash-tile__lbl` 블록 바로 다음)

```css
    /* ── 재정 인사이트 ── */
    .dash-fin-hero { margin-bottom: 6px; }
    .dash-fin-hero__num {
      font-family: var(--font-mono);
      font-size: 1.8rem; font-weight: 800;
      letter-spacing: -0.05em; line-height: 1; color: #4ade80;
    }
    .dash-fin-hero__sub { font-size: 0.65rem; color: var(--theme-dashboard-text-muted); margin-top: 2px; }
    .dash-fin-stats { display: flex; gap: 8px; margin-bottom: 8px; }
    .dash-fin-stat {
      flex: 1; padding: 8px 10px; border-radius: 8px;
      background: var(--theme-dashboard-panel-soft);
      border: 1px solid var(--theme-dashboard-border);
    }
    .dash-fin-stat__lbl { font-size: 0.58rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--theme-dashboard-text-muted); margin-bottom: 3px; }
    .dash-fin-stat__val { font-family: var(--font-mono); font-size: 0.95rem; font-weight: 700; }
    .dash-fin-bar-row { display: flex; align-items: center; gap: 8px; padding: 3px 0; }
    .dash-fin-bar-row__lbl { width: 72px; font-size: 0.68rem; opacity: 0.65; flex-shrink: 0; }
    .dash-fin-bar-row__track { flex: 1; height: 8px; border-radius: 4px; background: rgba(128,128,128,0.10); overflow: hidden; }
    .dash-fin-bar-row__fill { height: 100%; border-radius: 4px; transition: width 0.5s; }
    .dash-fin-bar-row__val { font-family: var(--font-mono); font-size: 0.65rem; width: 90px; text-align: right; opacity: 0.75; flex-shrink: 0; }
```

- [ ] **Step 3: 등록 페이스 + 메타 완성도용 CSS 추가**

```css
    /* ── 등록 페이스 ── */
    .dash-reg-month-fill {
      height: 100%; border-radius: 5px;
      background: linear-gradient(90deg, #0f766e, #14b8a6);
      transition: width 0.5s;
    }
    .dash-import-panel {
      display: flex; align-items: center; gap: 12px;
      padding: 8px 12px; border-radius: 8px;
      background: rgba(249,115,22,0.08);
      border: 1px solid rgba(249,115,22,0.18);
    }
    .dash-import-panel__num {
      font-family: var(--font-mono); font-size: 2rem;
      font-weight: 800; letter-spacing: -0.05em; line-height: 1;
      color: #f97316;
    }
    .dash-import-panel__lbl { font-size: 0.65rem; color: #fdba74; line-height: 1.5; }
    .dash-import-panel__badge {
      font-size: 0.62rem; padding: 2px 8px; border-radius: 20px;
      background: rgba(249,115,22,0.22); color: #fb923c;
      font-weight: 600; margin-top: 3px; display: inline-block;
    }
    /* ── 메타 완성도 ── */
    .dash-meta-src-group { display: flex; flex-direction: column; gap: 8px; }
    .dash-meta-src-row { display: flex; align-items: flex-start; gap: 8px; }
    .dash-meta-src-name { width: 68px; font-size: 0.68rem; font-weight: 600; flex-shrink: 0; padding-top: 1px; }
    .dash-meta-bars { flex: 1; display: flex; flex-direction: column; gap: 4px; }
    .dash-meta-bar-line { display: flex; align-items: center; gap: 6px; }
    .dash-meta-bar-tag { font-size: 0.55rem; text-transform: uppercase; letter-spacing: 0.04em; width: 42px; text-align: right; flex-shrink: 0; opacity: 0.4; }
    .dash-meta-bar-track { flex: 1; height: 6px; border-radius: 3px; background: rgba(128,128,128,0.10); overflow: hidden; }
    .dash-meta-bar-fill { height: 100%; border-radius: 3px; transition: width 0.5s; }
    .dash-meta-bar-pct { font-family: var(--font-mono); font-size: 0.62rem; width: 30px; text-align: right; flex-shrink: 0; opacity: 0.65; }
    .dash-meta-bar-fill.high { background: #4caf50; }
    .dash-meta-bar-fill.mid  { background: #f97316; }
    .dash-meta-bar-fill.low  { background: #ef4444; }
```

- [ ] **Step 4: 반응형 미디어 쿼리에 `.dash-tile-grid` 추가**

line 12768 (`@media (max-width:…)` 블록 안의 `.dash-alert-grid, .dash-collector-grid` 규칙들)에서:

기존:
```css
      .dash-alert-grid, .dash-collector-grid { grid-template-columns: repeat(2, 1fr); }
```
→ 다음으로 교체:
```css
      .dash-alert-grid, .dash-collector-grid, .dash-tile-grid { grid-template-columns: repeat(2, 1fr); }
```

line 12776:
```css
      .dash-alert-grid, .dash-collector-grid { grid-template-columns: 1fr; }
```
→ 다음으로 교체:
```css
      .dash-alert-grid, .dash-collector-grid, .dash-tile-grid { grid-template-columns: 1fr; }
```

- [ ] **Step 5: 구문 검증**

```bash
python3 -c "
import re, subprocess, tempfile, os
html = open('app/static/index.html', encoding='utf-8').read()
start = html.find('<script>') + len('<script>')
end = html.rfind('</script>')
js = html[start:end]
with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as tf:
    tf.write(js); tmp=tf.name
r = subprocess.run(['node', '--check', tmp], capture_output=True, text=True)
print('OK' if not r.stderr else r.stderr[:200])
os.unlink(tmp)
"
```
Expected: `OK`

- [ ] **Step 6: 커밋**

```bash
git add app/static/index.html
git commit -m "style: add dash-tile-grid, dash-fin-*, dash-meta-*, dash-import-panel CSS"
```

---

## Task 3: renderDashboardCollector 재작성

**Files:**
- Modify: `app/static/index.html:41131-41143`

현재 코드 (lines 41131–41142):
```javascript
    function renderDashboardCollector(d) {
      var b=document.getElementById('homeDashCollectorBody'); if(!b)return;
      var fc=formatCount;
      b.innerHTML='<div class="dash-collector-grid">'+
        '<div class="dash-collector-item" data-dash-drilldown="sig_direct" style="cursor:pointer;"><span class="dash-collector-icon">✍️</span><span class="dash-collector-value">'+fc(d.signed_items||0)+'</span><span class="dash-collector-label">싸인본</span></div>'+
        '<div class="dash-collector-item" data-dash-drilldown="limited_edition" style="cursor:pointer;"><span class="dash-collector-icon">💎</span><span class="dash-collector-value">'+fc(d.limited_items||0)+'</span><span class="dash-collector-label">한정반</span></div>'+
        '<div class="dash-collector-item"><span class="dash-collector-icon">📀</span><span class="dash-collector-value">'+fc(d.multi_disc_items||0)+'</span><span class="dash-collector-label">멀티디스크</span></div>'+
        '<div class="dash-collector-item"><span class="dash-collector-icon">🎗️</span><span class="dash-collector-value">'+fc(d.obi_items||0)+'</span><span class="dash-collector-label">OBI</span></div>'+
        '<div class="dash-collector-item" data-dash-drilldown="promo_items" style="cursor:pointer;"><span class="dash-collector-icon">📢</span><span class="dash-collector-value">'+fc(d.promo_items||0)+'</span><span class="dash-collector-label">홍보반</span></div>'+
        '<div class="dash-collector-item" data-dash-drilldown="other_items" style="cursor:pointer;"><span class="dash-collector-icon">📦</span><span class="dash-collector-value">'+fc(d.box_set_items||0)+'</span><span class="dash-collector-label">박스세트</span></div>'+
      '</div>';
    }
```

- [ ] **Step 1: 함수 교체**

위 코드 전체를 다음으로 교체:
```javascript
    function renderDashboardCollector(d) {
      var b = document.getElementById('homeDashCollectorBody'); if (!b) return;
      var fc = formatCount;
      var items = [
        { num: d.signed_items||0,     lbl:'싸인본',    color:'#fbbf24', drill:'sig_direct'    },
        { num: d.limited_items||0,    lbl:'한정반',    color:'#a78bfa', drill:'limited_edition'},
        { num: d.multi_disc_items||0, lbl:'멀티디스크', color:'#22d3ee', drill:null             },
        { num: d.obi_items||0,        lbl:'OBI',       color:'#f9a8d4', drill:null             },
        { num: d.promo_items||0,      lbl:'홍보반',    color:'#fb923c', drill:'promo_items'    },
        { num: d.box_set_items||0,    lbl:'박스세트',   color:'#6b7280', drill:'other_items'    },
      ];
      b.innerHTML = '<div class="dash-tile-grid">' +
        items.map(function(it) {
          var drill = it.drill ? ' data-dash-drilldown="'+it.drill+'"' : '';
          return '<div class="dash-tile"'+drill+'>' +
            '<div class="dash-tile__num" style="color:'+it.color+';">'+fc(it.num)+'</div>' +
            '<div class="dash-tile__lbl">'+it.lbl+'</div>' +
            '</div>';
        }).join('') +
        '</div>';
    }
```

- [ ] **Step 2: 구문 검증**

```bash
python3 -c "
import re, subprocess, tempfile, os
html = open('app/static/index.html', encoding='utf-8').read()
start = html.find('<script>') + len('<script>')
end = html.rfind('</script>')
js = html[start:end]
with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as tf:
    tf.write(js); tmp=tf.name
r = subprocess.run(['node', '--check', tmp], capture_output=True, text=True)
print('OK' if not r.stderr else r.stderr[:200])
os.unlink(tmp)
"
```
Expected: `OK`

- [ ] **Step 3: 커밋**

```bash
git add app/static/index.html
git commit -m "feat: renderDashboardCollector — tile grid, no emoji, color numbers"
```

---

## Task 4: renderDashboardAlerts 재작성

**Files:**
- Modify: `app/static/index.html:41144-41161`

현재 코드 (lines 41144–41161):
```javascript
    function renderDashboardAlerts(d) {
      var b=document.getElementById('homeDashAlertsBody'); if(!b)return;
      var fc=formatCount;
      var unassigned=0;
      for(var i=0;i<(d.by_domain||[]).length;i++){if(d.by_domain[i].value==='UNASSIGNED')unassigned=d.by_domain[i].count;}
      var alerts=[
        {l:'소스 미연결',c:d.source_unlinked_items||0,cls:(d.source_unlinked_items>0?'alert-critical':'alert-info')},
        {l:'마스터 미연결',c:d.master_unlinked_items||0,cls:(d.master_unlinked_items>0?'alert-critical':'alert-info')},
        {l:'커버 없음',c:d.cover_missing_items||0,cls:(d.cover_missing_items>0?'alert-warning':'alert-info')},
        {l:'장르 없음',c:d.genre_missing_items||0,cls:(d.genre_missing_items>0?'alert-warning':'alert-info')},
        {l:'미배치',c:d.unslotted_in_collection_items||0,cls:(d.unslotted_in_collection_items>0?'alert-warning':'alert-info')},
        {l:'도메인 미지정',c:unassigned,cls:'alert-info'},
      ];
      var h='<div class="dash-alert-grid">';
      for(var j=0;j<alerts.length;j++){var dk=(alerts[j].l==='소스 미연결'?'source_unlinked':alerts[j].l==='마스터 미연결'?'master_unlinked':alerts[j].l==='커버 없음'?'cover_missing':alerts[j].l==='장르 없음'?'genre_missing':alerts[j].l==='미배치'?'unslotted':'genre_missing');h+='<div class="dash-alert-item '+alerts[j].cls+'" data-dash-drilldown="'+dk+'" style="cursor:pointer;"><span>'+alerts[j].l+'</span><span class="alert-count">'+fc(alerts[j].c)+'</span></div>';}
      h+='</div>';
      b.innerHTML=h;
    }
```

- [ ] **Step 1: 함수 교체**

위 코드 전체를 다음으로 교체:
```javascript
    function renderDashboardAlerts(d) {
      var b = document.getElementById('homeDashAlertsBody'); if (!b) return;
      var fc = formatCount;
      var unassigned = 0;
      for (var i = 0; i < (d.by_domain||[]).length; i++) {
        if (d.by_domain[i].value === 'UNASSIGNED') unassigned = d.by_domain[i].count;
      }
      function alertColor(count, severity) {
        if (count === 0) return '#4ade80';
        if (severity === 'critical') return '#f87171';
        if (severity === 'warning')  return '#fb923c';
        return '#60a5fa';
      }
      var items = [
        { lbl:'소스 미연결',  c: d.source_unlinked_items||0,          sev:'critical', drill:'source_unlinked'  },
        { lbl:'마스터 미연결', c: d.master_unlinked_items||0,         sev:'critical', drill:'master_unlinked'  },
        { lbl:'커버 없음',    c: d.cover_missing_items||0,            sev:'warning',  drill:'cover_missing'    },
        { lbl:'장르 없음',    c: d.genre_missing_items||0,            sev:'warning',  drill:'genre_missing'    },
        { lbl:'미배치',       c: d.unslotted_in_collection_items||0,  sev:'warning',  drill:'unslotted'        },
        { lbl:'도메인 미지정', c: unassigned,                          sev:'info',     drill:'genre_missing'    },
      ];
      b.innerHTML = '<div class="dash-tile-grid">' +
        items.map(function(it) {
          return '<div class="dash-tile" data-dash-drilldown="'+it.drill+'">' +
            '<div class="dash-tile__num" style="color:'+alertColor(it.c, it.sev)+';">'+fc(it.c)+'</div>' +
            '<div class="dash-tile__lbl">'+it.lbl+'</div>' +
            '</div>';
        }).join('') +
        '</div>';
    }
```

- [ ] **Step 2: 구문 검증**

```bash
python3 -c "
import re, subprocess, tempfile, os
html = open('app/static/index.html', encoding='utf-8').read()
start = html.find('<script>') + len('<script>')
end = html.rfind('</script>')
js = html[start:end]
with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as tf:
    tf.write(js); tmp=tf.name
r = subprocess.run(['node', '--check', tmp], capture_output=True, text=True)
print('OK' if not r.stderr else r.stderr[:200])
os.unlink(tmp)
"
```
Expected: `OK`

- [ ] **Step 3: 커밋**

```bash
git add app/static/index.html
git commit -m "feat: renderDashboardAlerts — tile grid, color numbers by severity"
```

---

## Task 5: renderDashboardFinance 재작성

**Files:**
- Modify: `app/static/index.html:41036-41053`

- [ ] **Step 1: 함수 교체**

lines 41036–41053 전체를 다음으로 교체:
```javascript
    function renderDashboardFinance(d) {
      var b = document.getElementById('homeDashFinanceBody'); if (!b) return;
      var bc = d.by_currency_spend || [], bd = d.by_domain_spend || [];
      var rt = {KRW:1, USD:1380, GBP:1750, JPY:9}, tKRW = 0, pi = 0;
      for (var i = 0; i < bc.length; i++) {
        tKRW += (bc[i].total_spend||0) * (rt[bc[i].currency_code]||1);
        pi += bc[i].items || 0;
      }
      var ap = pi > 0 ? Math.round(tKRW / pi) : 0;
      var ms = 1;
      for (var j = 0; j < bd.length; j++) { if ((bd[j].total_spend||0) > ms) ms = bd[j].total_spend; }
      var cl = {KOREA:'#4ade80', WESTERN:'#60a5fa', JAPAN:'#fb923c', GREATER_CHINA:'#f97316', WORLD_OTHER:'#a78bfa', UNASSIGNED:'#6b7280'};
      var fc = formatCount;
      // 주요 통화 (KRW 비중)
      var krwEntry = bc.find(function(x){return x.currency_code==='KRW';});
      var krwPct = tKRW > 0 && krwEntry ? Math.round((krwEntry.total_spend||0)/tKRW*100) : 0;
      var h = '<div class="dash-fin-hero">' +
        '<div class="dash-fin-hero__num">₩'+fc(tKRW)+'</div>' +
        '<div class="dash-fin-hero__sub">총 구매액 (≈원화) &middot; '+fc(pi)+'/'+fc(d.total_items)+'건 가격 정보</div>' +
        '</div>' +
        '<div class="dash-fin-stats">' +
        '<div class="dash-fin-stat"><div class="dash-fin-stat__lbl">평균 단가</div><div class="dash-fin-stat__val">₩'+fc(ap)+'</div></div>' +
        '<div class="dash-fin-stat"><div class="dash-fin-stat__lbl">주요 통화</div><div class="dash-fin-stat__val" style="font-size:0.82rem;">KRW '+krwPct+'%</div></div>' +
        '</div>' +
        '<hr class="dash-kpi-divider">';
      for (var q = 0; q < bd.length; q++) {
        var dd = bd[q];
        var pct = ms > 0 ? Math.round((dd.total_spend||0) / ms * 100) : 0;
        h += '<div class="dash-fin-bar-row">' +
          '<span class="dash-fin-bar-row__lbl">'+escapeHtml(dd.domain||'')+'</span>' +
          '<div class="dash-fin-bar-row__track"><div class="dash-fin-bar-row__fill" style="width:'+pct+'%;background:'+(cl[dd.domain]||'#888')+'"></div></div>' +
          '<span class="dash-fin-bar-row__val">₩'+fc(dd.total_spend)+' (avg ₩'+fc(dd.avg_price)+')</span>' +
          '</div>';
      }
      b.innerHTML = h;
    }
```

- [ ] **Step 2: 구문 검증**

```bash
python3 -c "
import re, subprocess, tempfile, os
html = open('app/static/index.html', encoding='utf-8').read()
start = html.find('<script>') + len('<script>')
end = html.rfind('</script>')
js = html[start:end]
with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as tf:
    tf.write(js); tmp=tf.name
r = subprocess.run(['node', '--check', tmp], capture_output=True, text=True)
print('OK' if not r.stderr else r.stderr[:200])
os.unlink(tmp)
"
```
Expected: `OK`

- [ ] **Step 3: 커밋**

```bash
git add app/static/index.html
git commit -m "feat: renderDashboardFinance — hero total, stat row, 8px domain bars"
```

---

## Task 6: renderDashboardGenreDomain 재작성

**Files:**
- Modify: `app/static/index.html:41055-41068`

- [ ] **Step 1: 함수 교체**

lines 41055–41068 전체를 다음으로 교체:
```javascript
    function renderDashboardGenreDomain(d) {
      var b = document.getElementById('homeDashGenreDomainBody'); if (!b) return;
      var r = d.by_genre_domain || [], kg = [], wg = [];
      for (var i = 0; i < r.length; i++) {
        if (r[i].domain === 'KOREA'   && kg.length < 6) kg.push(r[i]);
        if (r[i].domain === 'WESTERN' && wg.length < 6) wg.push(r[i]);
      }
      var mk = Math.max(1, kg.reduce(function(m,x){return Math.max(m,x.count||0);}, 0));
      var mw = Math.max(1, wg.reduce(function(m,x){return Math.max(m,x.count||0);}, 0));
      var fc = formatCount;
      function col(items, max, color, domain) {
        return '<div>' +
          '<div style="font-size:0.72rem;font-weight:800;letter-spacing:0.03em;text-transform:uppercase;'+
               'color:'+color+';margin-bottom:8px;padding-bottom:5px;border-bottom:2px solid '+color+';">'+domain+'</div>' +
          items.map(function(it) {
            var pct = Math.round((it.count||0) / max * 100);
            return '<div class="dash-compare-row">' +
              '<span class="name" title="'+escapeHtml(it.genre||'')+'">'+escapeHtml(it.genre||'')+'</span>' +
              '<div class="dash-compare-bar"><div class="dash-compare-bar-fill" style="width:'+pct+'%;background:'+color+';"></div></div>' +
              '<span class="count" style="color:'+color+';">'+fc(it.count)+'</span>' +
              '</div>';
          }).join('') +
          '</div>';
      }
      b.innerHTML = '<div class="dash-compare-grid">' +
        col(kg, mk, '#4ade80', 'KOREA') +
        col(wg, mw, '#60a5fa', 'WESTERN') +
        '</div>';
    }
```

- [ ] **Step 2: 구문 검증**

```bash
python3 -c "
import re, subprocess, tempfile, os
html = open('app/static/index.html', encoding='utf-8').read()
start = html.find('<script>') + len('<script>')
end = html.rfind('</script>')
js = html[start:end]
with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as tf:
    tf.write(js); tmp=tf.name
r = subprocess.run(['node', '--check', tmp], capture_output=True, text=True)
print('OK' if not r.stderr else r.stderr[:200])
os.unlink(tmp)
"
```
Expected: `OK`

- [ ] **Step 3: 커밋**

```bash
git add app/static/index.html
git commit -m "feat: renderDashboardGenreDomain — 8px bars, color counts, bold headers"
```

---

## Task 7: renderDashboardRegImport 재작성

**Files:**
- Modify: `app/static/index.html:41163-41175`

- [ ] **Step 1: 함수 교체**

lines 41163–41175 전체를 다음으로 교체:
```javascript
    function renderDashboardRegImport(d) {
      var b = document.getElementById('homeDashRegImportBody'); if (!b) return;
      var months = (d.by_registration_month || []).slice(-10);
      var maxReg = Math.max(1, months.reduce(function(m,x){return Math.max(m,x.count||0);}, 0));
      var fc = formatCount;
      var h = '<div class="dash-reg-pace">';
      for (var j = 0; j < months.length; j++) {
        var m = months[j], pct = Math.round((m.count||0) / maxReg * 100);
        h += '<div class="dash-reg-month">' +
          '<span class="dash-reg-month-label">'+m.month+'</span>' +
          '<div class="dash-reg-month-bar"><div class="dash-reg-month-fill" style="width:'+pct+'%"></div></div>' +
          '<span class="dash-reg-month-count" style="font-weight:700;opacity:'+(pct===100?'1':'0.6')+';">'+fc(m.count)+'</span>' +
          '</div>';
      }
      h += '</div>';
      var qSize = d.import_queue_size || 0;
      h += '<div class="dash-import-panel">' +
        '<div class="dash-import-panel__num">'+fc(qSize)+'</div>' +
        '<div><div class="dash-import-panel__lbl">구매 수입 대기</div>' +
        '<span class="dash-import-panel__badge">'+(qSize > 0 ? '처리 필요' : '완료')+'</span>' +
        '</div></div>';
      b.innerHTML = h;
    }
```

- [ ] **Step 2: 구문 검증**

```bash
python3 -c "
import re, subprocess, tempfile, os
html = open('app/static/index.html', encoding='utf-8').read()
start = html.find('<script>') + len('<script>')
end = html.rfind('</script>')
js = html[start:end]
with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as tf:
    tf.write(js); tmp=tf.name
r = subprocess.run(['node', '--check', tmp], capture_output=True, text=True)
print('OK' if not r.stderr else r.stderr[:200])
os.unlink(tmp)
"
```
Expected: `OK`

- [ ] **Step 3: 커밋**

```bash
git add app/static/index.html
git commit -m "feat: renderDashboardRegImport — 10px gradient bars, import panel hero"
```

---

## Task 8: renderDashboardMetaSource 재작성

**Files:**
- Modify: `app/static/index.html:41109-41129`

- [ ] **Step 1: 함수 교체**

lines 41109–41129 전체를 다음으로 교체:
```javascript
    function renderDashboardMetaSource(d) {
      var b = document.getElementById('homeDashMetaSourceBody'); if (!b) return;
      var rows = d.by_source_completeness || [];
      if (!rows.length) { b.innerHTML = '<div class="mini muted">데이터 없음</div>'; return; }
      var fc = formatCount;
      function pctClass(p) { return p >= 95 ? 'high' : p >= 70 ? 'mid' : 'low'; }
      function barLine(tag, pct) {
        return '<div class="dash-meta-bar-line">' +
          '<span class="dash-meta-bar-tag">'+tag+'</span>' +
          '<div class="dash-meta-bar-track"><div class="dash-meta-bar-fill '+pctClass(pct)+'" style="width:'+pct+'%"></div></div>' +
          '<span class="dash-meta-bar-pct">'+pct+'%</span>' +
          '</div>';
      }
      var h = '<div class="dash-meta-src-group">';
      for (var i = 0; i < rows.length; i++) {
        var r = rows[i];
        var mp  = r.total > 0 ? Math.round(r.master_linked  / r.total * 100) : 0;
        var cp  = r.total > 0 ? Math.round(r.cover_present  / r.total * 100) : 0;
        var gp  = r.total > 0 ? Math.round(r.genre_present  / r.total * 100) : 0;
        if (i > 0) h += '<div style="height:1px;background:rgba(128,128,128,0.1);margin:4px 0;"></div>';
        h += '<div class="dash-meta-src-row">' +
          '<span class="dash-meta-src-name">'+escapeHtml(r.source||'')+'</span>' +
          '<div class="dash-meta-bars">' +
            barLine('마스터', mp) + barLine('커버', cp) + barLine('장르', gp) +
          '</div>' +
          '</div>';
      }
      h += '</div>';
      b.innerHTML = h;
    }
```

- [ ] **Step 2: 구문 검증**

```bash
python3 -c "
import re, subprocess, tempfile, os
html = open('app/static/index.html', encoding='utf-8').read()
start = html.find('<script>') + len('<script>')
end = html.rfind('</script>')
js = html[start:end]
with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as tf:
    tf.write(js); tmp=tf.name
r = subprocess.run(['node', '--check', tmp], capture_output=True, text=True)
print('OK' if not r.stderr else r.stderr[:200])
os.unlink(tmp)
"
```
Expected: `OK`

- [ ] **Step 3: 커밋**

```bash
git add app/static/index.html
git commit -m "feat: renderDashboardMetaSource — remove table, flex progress bars per source"
```

---

## Task 9: QA 동기화 및 최종 검증

**Files:**
- Run: `rsync` → `~/apps/__PROJECT_SLUG__-qa/app/static/index.html`

- [ ] **Step 1: QA 동기화**

```bash
rsync -a --checksum app/static/index.html ~/apps/__PROJECT_SLUG__-qa/app/static/index.html && echo "synced"
```
Expected: `synced`

- [ ] **Step 2: 검증 스크립트 — 바 높이, table, 이모지**

```bash
python3 -c "
import re
html = open('app/static/index.html', encoding='utf-8').read()

# 바 높이 검사 (CSS 토큰)
for pattern, label in [
    (r'\.dash-compare-bar\s*\{[^}]*height:\s*(\d+)px', 'dash-compare-bar'),
    (r'\.dash-reg-month-bar\s*\{[^}]*height:\s*(\d+)px', 'dash-reg-month-bar'),
]:
    m = re.search(pattern, html)
    h = int(m.group(1)) if m else 0
    status = 'OK' if h >= 8 else 'FAIL ('+str(h)+'px)'
    print(label+':', status)

# table 태그 검사 (render 함수 내)
render_fns = ['renderDashboardCollector', 'renderDashboardAlerts',
              'renderDashboardFinance', 'renderDashboardGenreDomain',
              'renderDashboardRegImport', 'renderDashboardMetaSource']
for fn in render_fns:
    m = re.search(r'function '+fn+r'\(.*?\n.*?(?=\n    function )', html, re.DOTALL)
    if m:
        has_table = '<table' in m.group(0)
        print(fn+' table:', 'FAIL' if has_table else 'OK')
    else:
        print(fn+': not found')

# 이모지 검사 (render 함수 내)
emoji_pat = re.compile(r'[\U0001F300-\U0001FAFF]')
for fn in ['renderDashboardCollector']:
    m = re.search(r'function '+fn+r'\(.*?\n.*?(?=\n    function )', html, re.DOTALL)
    if m:
        emojis = emoji_pat.findall(m.group(0))
        print(fn+' emoji:', 'FAIL '+str(emojis) if emojis else 'OK')
"
```
Expected: 모든 항목 `OK`

- [ ] **Step 3: 브라우저 확인**

`https://__QA_DOMAIN__/admin` 접속 후 확인:
- [ ] 콜렉터 가치: 이모지 없음, 숫자 컬러 표시, 균일 배경
- [ ] 예외 알림: 숫자 색상으로 심각도 구분, 균일 배경
- [ ] 재정 인사이트: 총액 히어로 블록, 8px 도메인 바
- [ ] 장르 × 도메인: 8px 바, 수치에 도메인 색상
- [ ] 등록 페이스: 10px 그라데이션 바, 수입대기 패널
- [ ] 메타 완성도: 테이블 없음, 소스별 progress bar

- [ ] **Step 4: 최종 커밋**

```bash
git add app/static/index.html
git commit -m "chore: sync QA after dashboard card polish"
```
