# 단일 QA 마스터 시트 재정비 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `docs/qa/qa_master_sheet.csv`를 현재 제품/배포 흐름 기준의 단일 QA 기준 문서로 재작성하고, 관련 런북/체크리스트/README 참조를 그 시트 중심으로 정리한다.

**Architecture:** 기존 QA 시트의 row-level 사례는 최대한 유지하되, 새 스키마로 재배치한다. `qa_master_sheet.csv`는 배포 게이트와 기능 도메인 QA를 함께 담는 실행판으로 재구성하고, `qa_manual_remaining.csv`는 별도 진실 소스에서 제거한다. 주변 문서들은 절차 문서로 축소하고 QA 기준은 모두 마스터 시트를 참조하게 맞춘다.

**Tech Stack:** CSV 문서, Markdown 문서, shell inspection, Python CSV validation, ripgrep

---

### Task 1: QA 아티팩트 현황과 새 스키마 고정

**Files:**
- Modify: `docs/qa/qa_master_sheet.csv`
- Modify: `docs/qa/qa_manual_remaining.csv`
- Reference: `docs/superpowers/specs/2026-04-18-qa-master-sheet-refresh-design.md`

- [ ] **Step 1: 기존 QA 시트 헤더와 행 수를 확인한다**

Run:
```bash
python - <<'PY'
import csv
from pathlib import Path
path = Path('docs/qa/qa_master_sheet.csv')
with path.open() as f:
    reader = csv.reader(f)
    rows = list(reader)
print(rows[0])
print(len(rows) - 1)
PY
```

Expected: 기존 헤더와 총 케이스 수가 출력된다.

- [ ] **Step 2: 새 스키마 헤더를 설계 스펙과 일치시킨다**

Target header:
```csv
case_id,section,surface,role,environment,phase,release_ref,priority,gate,coverage_mode,scenario,preconditions_or_test_data,expected_result,definition_ref,evidence_ref,workflow_state,result,verified_at,executor,approver,notes_or_risk
```

- [ ] **Step 3: `qa_manual_remaining.csv`의 역할을 종료한다**

Action:
- 헤더만 남아 있는 별도 잔여 시트는 유지 가치가 없으므로 제거하거나
- 최소한 “deprecated, use qa_master_sheet.csv” 역할로 축소한다

- [ ] **Step 4: 변경 전후 CSV 구조를 검증한다**

Run:
```bash
python - <<'PY'
import csv
from pathlib import Path
path = Path('docs/qa/qa_master_sheet.csv')
with path.open() as f:
    reader = csv.DictReader(f)
    print(reader.fieldnames)
PY
```

Expected: 새 스키마 컬럼명이 순서대로 출력된다.

### Task 2: 기존 QA 케이스를 새 구조로 매핑

**Files:**
- Modify: `docs/qa/qa_master_sheet.csv`
- Reference: `docs/management_tool_manual.md`
- Reference: `docs/go_live_checklist.md`
- Reference: `docs/macos_qa_prod_runbook.md`

- [ ] **Step 1: 기존 `suite_id/area/role/priority/test_type/title...`를 새 컬럼으로 대응표를 만든다**

Mapping rules:
- `suite_id -> case_id`
- `area -> section` 또는 `surface` 보조 입력
- `title -> scenario`
- `precondition -> preconditions_or_test_data`
- `expected_result -> expected_result`
- `notes -> notes_or_risk`의 초기값

- [ ] **Step 2: 각 행에 `gate`를 부여한다**

Rules:
- 인증, health, backup/restore, 핵심 등록/이동/권한은 `Blocker` 또는 `Release`
- 시각 polish, 비교적 낮은 UX 항목은 `Non-blocking`

- [ ] **Step 2.1: 각 행에 `phase`를 부여한다**

Rules:
- QA 승격 전에 판단해야 하는 항목은 `Pre-release`
- 운영 반영 직후 smoke/초기 안정화/rollback 확인은 `Post-release`

- [ ] **Step 3: 각 행에 `coverage_mode`를 부여한다**

Rules:
- pytest/스크립트로 충분히 판정 가능하면 `Auto`
- 자동 + 브라우저가 필요하면 `Hybrid`
- 브라우저나 실장비만 의미 있으면 `Manual-only`

- [ ] **Step 4: `definition_ref`를 채운다**

Examples:
- `pytest:tests/test_ops_route_access.py::test_name`
- `pytest:tests/test_ops_shell_bootstrap.py::test_name`
- `runbook:docs/macos_qa_prod_runbook.md#9-qa-검증-절차`
- `manual:docs/management_tool_manual.md`

- [ ] **Step 5: 과거 pass 메모를 새 구조에 맞게 정리한다**

Rules:
- 과거 성공 메모는 `notes_or_risk`로 요약 이전
- `result`는 이번 릴리스 기준이므로 기본값을 `Not Run`으로 재설정
- `release_ref`, `verified_at`, `evidence_ref`는 빈 상태 또는 플레이스홀더로 둔다

### Task 3: 누락된 현재 기능 QA 항목 추가

**Files:**
- Modify: `docs/qa/qa_master_sheet.csv`
- Reference: `app/static/index.html`
- Reference: `tests/test_ops_shell_bootstrap.py`
- Reference: `tests/test_ops_route_access.py`
- Reference: `tests/test_artist_context_service.py`

- [ ] **Step 1: 현재 제품 기준 상위 섹션을 먼저 배치한다**

Required sections:
- `Release / Environment / Recovery`
- `Auth / Roles / Route Access`
- `Operator Home`
- `Dashboard / Placement / Recovery`
- `Search / Manage`
- `Source Enrichment / Master Cleanup`
- `Registration / Intake`
- `Ops / Integrations`
- `Cross-cutting Shell / UX`

- [ ] **Step 2: 최근 반영된 but 시트에 약한 항목을 추가한다**

Must-add examples:
- 아티스트 컨텍스트 fallback
- day/night theme and header utility
- 운영/연계 시스템 상태
- 검색/관리 day-mode selection surface
- 운영 홈 / 대시보드 shell smoke

- [ ] **Step 3: prod 전용 smoke와 초기 안정화 항목을 추가한다**

Examples:
- `REL-HEALTH-PROD`
- `REL-LOGIN-PROD`
- `REL-SMOKE-PROD`
- `REL-ROLLBACK-READY`

Rules:
- 이 항목들은 `environment=prod`
- 이 항목들은 `phase=Post-release`
- 배포 전 승격 계산에는 포함하지 않는다

- [ ] **Step 4: broad row를 분리한다**

Split rules:
- backup / restore / rollback은 각각 별도 행
- responsive / overflow / contrast / hit target도 분리
- negative / recovery / permission / data-integrity는 smoke와 분리

- [ ] **Step 5: ID 보존과 suffix 규칙을 적용한다**

Examples:
- `SYS-003A`
- `SYS-003B`
- `SEARCH-005A`

Expected: 기존 참조 가능성을 깨지 않으면서 세분화가 이뤄진다.

### Task 4: 주변 문서를 단일 QA 시트 중심으로 정리

**Files:**
- Modify: `README.md`
- Modify: `docs/go_live_checklist.md`
- Modify: `docs/macos_qa_prod_runbook.md`
- Modify or Delete: `docs/qa/qa_manual_remaining.csv`

- [ ] **Step 1: README의 QA 문서 안내를 정리한다**

Rules:
- QA 기준 문서는 `docs/qa/qa_master_sheet.csv` 하나라고 명시
- `qa_manual_remaining.csv` 참조는 제거 또는 deprecated 표기

- [ ] **Step 2: `go_live_checklist.md`에서 QA 항목 중복을 줄인다**

Rules:
- 릴리스 순서와 sign-off는 유지
- 세부 QA 기준은 `qa_master_sheet.csv`를 참조하게 바꾼다

- [ ] **Step 3: `macos_qa_prod_runbook.md`에서 QA 기준 중복을 줄인다**

Rules:
- 환경/배포/복원/launchd/cloudflare 절차는 유지
- QA 판정 기준은 마스터 시트 참조로 바꾼다
- 하드웨어 naming inconsistency가 있으면 함께 정리한다

- [ ] **Step 4: `qa_manual_remaining.csv` 처리 방침을 확정한다**

Choose one:
- 삭제
- deprecated 한 줄 설명만 남기기

Recommended: 삭제하거나 deprecated placeholder만 남긴다.

### Task 5: 검증 및 보정 루프 실행

**Files:**
- Verify: `docs/qa/qa_master_sheet.csv`
- Verify: `README.md`
- Verify: `docs/go_live_checklist.md`
- Verify: `docs/macos_qa_prod_runbook.md`

- [ ] **Step 1: CSV 파싱 검증**

Run:
```bash
python - <<'PY'
import csv
from pathlib import Path
for path in [
    Path('docs/qa/qa_master_sheet.csv'),
]:
    with path.open() as f:
        rows = list(csv.DictReader(f))
    print(path, len(rows))
PY
```

Expected: CSV가 파싱되고 행 수가 정상 출력된다.

- [ ] **Step 2: deprecated 참조 잔존 여부 확인**

Run:
```bash
rg -n "qa_manual_remaining|qa_master_sheet" README.md docs
```

Expected: `qa_master_sheet.csv`는 기준 문서로만 나오고, `qa_manual_remaining.csv`는 제거되었거나 deprecated로만 남는다.

- [ ] **Step 3: 새 필수 컬럼 누락 검사**

Run:
```bash
python - <<'PY'
import csv
from pathlib import Path
required = {
    'case_id','section','surface','role','environment','phase','release_ref','priority','gate',
    'coverage_mode','scenario','preconditions_or_test_data','expected_result',
    'definition_ref','evidence_ref','workflow_state','result','verified_at',
    'executor','approver','notes_or_risk'
}
with Path('docs/qa/qa_master_sheet.csv').open() as f:
    fields = set(csv.DictReader(f).fieldnames)
missing = sorted(required - fields)
print('missing=', missing)
raise SystemExit(1 if missing else 0)
PY
```

Expected: `missing=[]`

- [ ] **Step 4: 문서 정합성 최종 확인**

Checklist:
- QA 기준 문서 하나로 읽히는가
- release gate가 계산 가능하게 보이는가
- 최근 기능군이 누락되지 않았는가
- prod smoke 책임이 빠지지 않았는가

- [ ] **Step 5: Commit**

```bash
git add README.md docs/go_live_checklist.md docs/macos_qa_prod_runbook.md docs/qa/qa_master_sheet.csv docs/qa/qa_manual_remaining.csv docs/superpowers/specs/2026-04-18-qa-master-sheet-refresh-design.md docs/superpowers/plans/2026-04-18-qa-master-sheet-refresh-implementation.md
git commit -m "docs: refresh consolidated QA master sheet"
```
