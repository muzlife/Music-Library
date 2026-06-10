# index.html 분리 실행 계획 (착수용)

작성일: 2026-06-10
근거: `docs/repo_audit_2026-06-10.md` H5 / §7.4 (9개월간 331커밋 — 전체 1위, 2위의 4배)
목표: **빌드 도구 없이**, 동작 변경 0으로 62,176줄 단일 파일을 도메인별 정적 파일로 분리

---

## 0. 현재 구조 실측 (2026-06-10 기준)

| 구간 | 라인 | 내용 |
|---|---|---|
| 1–6 | 6 | `<head>` 시작 |
| **7–17,909** | 17,903 | `<style>` 메인 CSS |
| 17,910–22,884 | 4,975 | HTML 마크업 (22,497–22,521에 25줄 인라인 style 포함) |
| **22,885–62,174** | 39,290 | 단일 클래식 `<script>` |

스크립트 내부:

| 구간 | 라인 수 | 내용 |
|---|---|---|
| 22,886–23,071 | ~190 | fetch 래퍼(credentials:"include") + 공유 상수 |
| 23,072–31,315 | **8,243** | `const I18N_MESSAGES = {...}` — 순수 데이터 |
| 31,316–62,174 | ~30,860 | 앱 로직: 최상위 함수 1,156개, const/let 5,382개, addEventListener 519건 |

분리 난이도를 좌우하는 실측 사실:
- **인라인 `onclick`은 단 10건** (정적 HTML 3건 + JS 템플릿 문자열 7건). 나머지는 전부 addEventListener → 전역 유지가 필요한 함수는 7개뿐:
  `handleEditImageUrlAdd`, `handleHomeEditCoverImageUrlApply`, `applyGoodsRegisterImageUrl`, `openLocalImageGallery`, `deleteEditLocalImage`, `openDashboardOwnedItemDetailManage`, `openMediaSearchDetailManage`
- 서빙: `app/api/static_pages.py`가 매 요청 index.html **전체의 md5**를 계산해 `/?v=<hash>` 리다이렉트로 캐시 버스팅 (`static_pages.py:63,111`). 자산은 `/ui-static` StaticFiles 마운트(ETag/Last-Modified 자동).
- index.html **내용을 문자열로 검사하는 테스트 3개**: `tests/test_admin_density_compaction.py`, `test_master_merge_workbench_ui.py`, `test_ops_home_recent_sections.py` (`read_static_html` 헬퍼 경유).
- ⚠️ 프런트 `DOMAIN_CODES`(22,899행 부근)는 `WORLD` 포함/`WORLD_OTHER` 미포함 — 백엔드 두 정의와 다른 **세 번째 변종**. 분리 작업 중 건드리지 말고 감사 M1 과제에서 일괄 정리.

> ⚠️ **선행 조건**: 현재 작업 트리에 index.html 미커밋 변경(+244줄)이 있음. **분리 착수 전 반드시 커밋**해서 깨끗한 기준점을 만들 것. 병렬 수정 세션과 일정 조율 필수 — 분리 진행 중 index.html 직접 수정 금지.

---

## 1. 전략 요약

**클래식 `<script src>` 분할** (ESM 아님)을 선택한다. 이유:
- 클래식 스크립트는 최상위 선언이 전역 스코프를 공유 → 1,156개 함수의 상호 참조를 import/export 선언 없이 그대로 유지
- onclick 7개 함수도 자동으로 전역 유지 (ESM이면 `window.*` 수동 노출 필요)
- 실행 순서 = 태그 순서로 결정적, 빌드 도구 불필요
- ESM 전환은 분할 안정화 이후 선택 과제(Phase 4)로 미룸

파일 배치(목표):

```
app/static/
├── index.html          (~5,100줄: HTML + link/script 태그만)
├── css/
│   └── app.css         (17,903줄 → Phase 3에서 도메인 분할)
└── js/
    ├── core.js         fetch 래퍼 + 공유 상수 (~190줄)
    ├── i18n.ko.js      I18N_MESSAGES (~8,243줄)
    ├── util.js         escapeHtml/normalize*/format*/t() 등 공용 헬퍼
    ├── dashboard.js    dashboard* 87함수 + Dashboard renderers v2(49,530행~)
    ├── ops_home.js     home*/operator*/climate (운영 홈)
    ├── search_manage.js 검색/관리: 목록 렌더·상세 편집·로컬 이미지(33,183행~)
    ├── register.js     등록/수집: purchase*/csv/goods 등록
    ├── source_workbench.js source*/sync* + Spotify Match Modal(61,867행~) + Local Player(43,050행~)
    ├── master_workbench.js 마스터 정리/병합/변형
    ├── admin_system.js 권한(47,693행~)·에러/퍼프/활동 로그(59,101~59,236행)·백업
    └── boot.js         hash 라우팅(62,158행~)·DOMContentLoaded 초기화·탭 와이어링 (반드시 마지막)
```

---

## 2. Phase 0 — 안전망 (0.5일)

1. **커밋 기준점**: 병렬 작업분 커밋 + `git tag pre-frontend-split`.
2. **Playwright 스모크 작성** (`tests/e2e_smoke.py`, 로컬 전용 — `.venv`에 playwright 이미 설치됨):
   - 로그인 → 6개 주 탭(대시보드/운영 홈/검색·관리/소스 보강/등록·수집/운영·연계) 각각 클릭 → `page.on("console")`로 **콘솔 에러 0건** 검증 + 각 탭 핵심 셀렉터 1개 존재 확인.
   - 분리 작업의 회귀 검증은 이 스모크 + `docs/qa/qa_master_sheet.csv` 수동 시트로 한다.
3. **테스트 헬퍼 호환층**: `read_static_html`를 "index.html + css/*.css + js/*.js 연결 문자열"을 반환하도록 수정 → 기존 문자열 검사 테스트 3개가 분리 전후 동일하게 통과.
4. **구문 검사 게이트**: 각 js 파일에 `node --check` (없으면 `python3 -c "import re,sys..."` 대신 **브라우저 로드 스모크로 갈음**). CI/프리플라이트에 추가.

완료 기준: 스모크 그린, 태그 생성, 헬퍼 수정 커밋.

---

## 3. Phase 1 — 기계적 3분할 (1일, 동작 변경 0)

**한 커밋**으로 CSS/i18n/JS를 통째로 추출한다. 라인 번호가 아니라 **마커 문자열**로 자르는 스크립트 사용(병렬 수정으로 라인이 밀려도 안전):

```python
# scripts/split_index_html.py — 1회용. 실행 전 git 클린 상태 확인.
from pathlib import Path
p = Path("app/static/index.html")
src = p.read_text(encoding="utf-8")

# 1) 메인 CSS: 첫 <style> ~ 첫 </style>
css_start = src.index("<style>") + len("<style>")
css_end = src.index("</style>")
css = src[css_start:css_end]

# 2) 메인 스크립트: 마지막 <script> ~ 마지막 </script>
js_start = src.rindex("<script>") + len("<script>")
js_end = src.rindex("</script>")
js = src[js_start:js_end]

# 3) i18n 블록: 'const I18N_MESSAGES = {' ~ 매칭되는 '};' (들여쓰기 4칸 기준 '\n    };')
i_start = js.index("const I18N_MESSAGES")
i_end = js.index("\n    };", i_start) + len("\n    };")
core, i18n, app = js[:i_start], js[i_start:i_end], js[i_end:]

out = Path("app/static")
(out / "css").mkdir(exist_ok=True); (out / "js").mkdir(exist_ok=True)
(out / "css/app.css").write_text(css.strip() + "\n", encoding="utf-8")
(out / "js/core.js").write_text(core.strip() + "\n", encoding="utf-8")
(out / "js/i18n.ko.js").write_text(i18n.strip() + "\n", encoding="utf-8")
(out / "js/app.js").write_text(app.strip() + "\n", encoding="utf-8")

html = (src[:css_start - len("<style>")]
        + '<link rel="stylesheet" href="/ui-static/css/app.css" />'
        + src[css_end + len("</style>"):js_start - len("<script>")]
        + '<script src="/ui-static/js/core.js"></script>\n'
        + '  <script src="/ui-static/js/i18n.ko.js"></script>\n'
        + '  <script src="/ui-static/js/app.js"></script>'
        + src[js_end + len("</script>"):])
p.write_text(html, encoding="utf-8")
print("done:", {f.name: len(f.read_text().splitlines()) for f in [out/'css/app.css', out/'js/core.js', out/'js/i18n.ko.js', out/'js/app.js']})
```

주의 사항:
- 22,497–22,521의 25줄짜리 두 번째 `<style>`은 그대로 둔다(첫 `<style>`만 추출되는지 결과 diff로 확인).
- script 태그 위치를 원래 `<script>` 자리(body 끝)에 유지 — `defer`/`type=module` 붙이지 말 것. 실행 시점이 완전히 동일해야 한다.
- 검증: `core.js + i18n.ko.js + app.js` 연결 내용이 원본 스크립트 구간과 **바이트 동일**(공백 trim 차이만)인지 체크섬 비교.

**서빙/캐시 수정** (`app/api/static_pages.py`):
- `file_hash` 계산을 index.html 단독 md5 → **index.html + css/* + js/* 전체를 합친 md5**로 변경 (두 곳: `:63`, `:111`). 이렇게 해야 js만 바뀌어도 `/?v=` 리다이렉트가 갱신된다.
- `/ui-static`의 css/js에 `Cache-Control: no-cache` 부여(StaticFiles의 ETag 304 재검증과 조합 → 항상 최신 + 변경 없으면 바디 미전송). 가장 간단한 구현은 main.py의 perf 미들웨어처럼 응답 헤더를 덧씌우는 5줄짜리 미들웨어.

완료 기준: 스모크 그린 + 문자열 테스트 3개 그린 + index.html ≈ 5,100줄 + QA/상용 캐시 버스팅 동작 확인(파일 1바이트 수정 → `/?v=` 해시 변경).

---

## 4. Phase 2 — app.js 도메인 분할 (도메인당 0.5~1일 × 8~9회)

**규칙 (모든 이동 공통)**
1. 한 커밋 = 한 도메인 파일. 함수를 **수정 없이 그대로** 잘라 옮긴다 (리팩토링 금지 — 이동과 수정을 같은 커밋에 섞지 않는다).
2. index.html의 `<script src>` 목록에 새 파일을 **app.js보다 앞에** 추가. 로드 순서: `core → i18n.ko → util → (도메인들) → app.js(잔여) → boot`.
3. 이동 후 스모크 + 해당 도메인 QA 시트 항목 수동 1회.
4. 전역 onclick 함수 7개는 파일 상단 주석으로 "전역 필수(인라인 onclick 사용)" 표기.

**순서** (의존이 얕은 것 → 깊은 것):

| 차수 | 파일 | 추출 대상(현재 위치 단서) | 크기 추정 |
|---|---|---|---|
| 1 | `util.js` | escapeHtml, `t()`, normalize*/format*/is*/get* 공용 헬퍼 (전역 879회 호출되는 escapeHtml 포함) | ~2k줄 |
| 2 | `admin_system.js` | 권한 관리 47,693~47,921행, 에러/퍼프/활동 로그 59,082~59,236행, 백업/복원 UI | ~3k줄 |
| 3 | `dashboard.js` | `dashboard*` 87함수, Dashboard renderers v2 49,530행~, dash-activity 43,502행~ | ~4k줄 |
| 4 | `ops_home.js` | home*/operator*/climate-compare | ~3k줄 |
| 5 | `source_workbench.js` | source*/sync*, Spotify Match Modal 61,867~62,044행, Local Player 43,050행~ | ~4k줄 |
| 6 | `register.js` | purchase*(14함수)/csv/goods 등록, 이미지 URL 적용 핸들러 | ~4k줄 |
| 7 | `master_workbench.js` | 마스터 병합/변형/도메인 불일치 검증 56,476행~ | ~3k줄 |
| 8 | `search_manage.js` | 목록 렌더·상세 편집·로컬 이미지 관리 33,183~33,373행 | ~5k줄 |
| 9 | `boot.js` | hash 라우팅 62,158행~, 초기화/탭 와이어링 — **마지막에 분리, 로드도 마지막** | ~1k줄 |

**함정 (반드시 숙지)**
- **최상위 `const`/`let`의 TDZ**: 클래식 스크립트끼리도 전역 렉시컬 스코프를 공유하므로, 파일 A의 *최상위 코드*가 파일 B의 const를 즉시 참조하면 로드 순서에 따라 ReferenceError. 함수 *내부* 참조(호출 시점)는 안전 — 대부분이 이 경우다. 이동 후 페이지 1회 로드로 즉시 검출됨.
- **동명 선언 충돌**: 같은 이름의 `const`를 두 파일에 두면 SyntaxError가 아니라 두 번째 파일 전체가 죽는다. 이동은 "잘라내기"만 — 복사 금지.
- **i18n `t()` 의존**: 거의 모든 렌더 함수가 사용 → `util.js`(t 정의)와 `i18n.ko.js`(데이터)는 항상 도메인 파일들보다 앞.
- `.gitignore`의 `index.html.bak_*` 패턴이 있던 관행처럼 **bak 파일 만들지 말 것** — git이 안전망이다.

완료 기준(전체): `app.js` 잔여 < 3,000줄(공용 잔여물), 어떤 파일도 6,000줄 초과 금지, 스모크/QA 시트/문자열 테스트 그린.

---

## 5. Phase 3 — CSS 분할 + 후속 (선택, 각 0.5일)

- `app.css` → `base.css`(토큰·리셋·공용 컴포넌트) / `ops_home.css`(Ops Home 테마 6,155~6,490행 등) / `dashboard.css`(카드 13,410~13,761행 등) / `manage.css`. CSS는 순서 의존(캐스케이드)이 있으므로 **원본 순서를 유지한 채 구간 단위로만** 자른다.
- 미사용 CSS 감사: 분할 후 Chrome Coverage로 측정 → 별도 과제.
- i18n: `i18n.ko.js` → JSON + 로더로 전환하면 다국어 추가 대비(선택).

## Phase 4 — ESM 전환 (보류 권고)

분할 안정화 후에도 전역 충돌이 실제 문제가 될 때만. 그 시점 비용: 파일별 import/export 선언 + onclick 7개 함수 `window.*` 노출 + script 태그 `type="module"` 전환.

---

## 6. 일정·완료 정의

| 단계 | 공수 | 산출물 |
|---|---|---|
| Phase 0 | 0.5일 | 스모크 테스트, 태그, 헬퍼 호환층 |
| Phase 1 | 1일 | index.html ~5,100줄 + css 1 + js 3 |
| Phase 2 | 5~8일 (분할 커밋 9개) | js 11파일, 최대 파일 < 6k줄 |
| Phase 3 | 1~2일 (선택) | css 4파일 |

최종 완료 정의(감사 보고서 §4 테마1과 동일): index.html 단일 파일 < 5,000줄(HTML만), 스모크·QA 시트·기존 테스트 전부 그린, 캐시 버스팅 정상, 이후 프런트 변경 커밋이 도메인 파일 단위로 떨어지는 것.
