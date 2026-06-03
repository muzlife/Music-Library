# macOS QA/운영 독립 배포 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `__DEV_MACHINE__`를 `QA`, `__PROD_MACHINE__`을 `운영`으로 완전히 분리하고 `__QA_DOMAIN__` / `library.muzlife.com` 기준의 독립 배포 절차와 템플릿 자산을 저장소에 추가한다.

**Architecture:** 실행 자산은 코드와 분리된 문서/템플릿으로 먼저 고정한다. `launchd` 템플릿, `Cloudflare Tunnel` 템플릿, QA/운영 `.env` 예시, 운영 백업을 QA로 복제하는 런북을 저장소에 두고, 실제 장비 값은 플레이스홀더 치환으로 채운다.

**Tech Stack:** Markdown, XML plist, YAML, Bash 실행 절차, macOS `launchd`, Cloudflare Tunnel

---

### Task 1: 배포 런북 구조 고정

**Files:**
- Create: `docs/macos_qa_prod_runbook.md`
- Modify: `docs/superpowers/specs/2026-04-13-macos-qa-production-independent-deployment-design.md`

- [ ] **Step 1: 런북에 들어갈 절차 범위 고정**

포함할 절차:
- 서버 역할 구분
- 디렉터리 구조
- `.env.local` 분리
- `launchd` 등록
- Cloudflare Tunnel 연결
- 운영 백업 -> QA 복원
- QA 검증 -> 운영 배포
- 롤백

- [ ] **Step 2: 런북 초안 작성**

```md
## 1. 서버 역할
## 2. 디렉터리 준비
## 3. Python/venv 준비
## 4. 환경변수 작성
## 5. launchd 등록
## 6. Cloudflare Tunnel 연결
## 7. 운영 백업을 QA에 복제
## 8. QA 검증
## 9. 운영 배포
## 10. 롤백
```

- [ ] **Step 3: 템플릿 파일 경로와 연결**

런북에 아래 경로를 명시한다.
- `deploy/templates/env/.env.production.example`
- `deploy/templates/env/.env.qa.example`
- `deploy/templates/launchd/com.muzlife.library-prod.plist`
- `deploy/templates/launchd/com.muzlife.library-qa.plist`
- `deploy/templates/cloudflare/library-prod-config.yml`
- `deploy/templates/cloudflare/library-qa-config.yml`

- [ ] **Step 4: 검토**

확인:
- 시놀로지 의존이 남아 있지 않은지
- QA/운영이 같은 경로를 공유하지 않는지
- 도메인 `__QA_DOMAIN__` / `library.muzlife.com`이 모두 절차에 반영됐는지

- [ ] **Step 5: Commit**

```bash
git add docs/macos_qa_prod_runbook.md
git commit -m "docs: add macOS QA/prod runbook"
```

### Task 2: QA/운영 환경변수 템플릿 추가

**Files:**
- Create: `deploy/templates/env/.env.production.example`
- Create: `deploy/templates/env/.env.qa.example`
- Reference: `.env.example`

- [ ] **Step 1: 필수 키 목록 정리**

운영/QA 공통:
- `APP_HOST`
- `APP_PORT`
- `LIBRARY_DB_PATH`
- `LIBRARY_AUTH_COOKIE_SECURE`
- `LIBRARY_ADMIN_USERNAME`
- `LIBRARY_ADMIN_PASSWORD`
- `LIBRARY_OPERATOR_USERNAME`
- `LIBRARY_OPERATOR_PASSWORD`
- `LIBRARY_AUTH_SESSION_SECRET`
- `LIBRARY_PURCHASE_IMPORT_TOKEN`
- `DISCOGS_TOKEN`
- `ALADIN_TTB_KEY`

- [ ] **Step 2: 운영 예시 파일 작성**

```env
APP_HOST=127.0.0.1
APP_PORT=8000
LIBRARY_DB_PATH=/Users/__USER__/apps/hahahoho-prod/runtime/data/library.db
LIBRARY_AUTH_COOKIE_SECURE=1
```

- [ ] **Step 3: QA 예시 파일 작성**

```env
APP_HOST=127.0.0.1
APP_PORT=8100
LIBRARY_DB_PATH=/Users/__USER__/apps/hahahoho-qa/runtime/data/library.db
LIBRARY_AUTH_COOKIE_SECURE=1
```

- [ ] **Step 4: 검토**

확인:
- QA/운영 포트가 다르게 들어갔는지
- QA/운영 세션 시크릿과 webhook token은 분리해야 한다는 문구가 들어갔는지

- [ ] **Step 5: Commit**

```bash
git add deploy/templates/env/.env.production.example deploy/templates/env/.env.qa.example
git commit -m "docs: add QA and production env templates"
```

### Task 3: launchd 템플릿 추가

**Files:**
- Create: `deploy/templates/launchd/com.muzlife.library-prod.plist`
- Create: `deploy/templates/launchd/com.muzlife.library-qa.plist`
- Reference: `scripts/run_api.sh`

- [ ] **Step 1: 실행 방식 확인**

`run_api.sh`가 아래를 담당하는지 다시 확인한다.
- `.env.local` 로드
- `.venv/bin/uvicorn` 우선 사용
- `APP_HOST`, `APP_PORT` 반영

- [ ] **Step 2: 운영 plist 작성**

```xml
<key>WorkingDirectory</key>
<string>__APP_ROOT__</string>
<key>ProgramArguments</key>
<array>
  <string>/bin/zsh</string>
  <string>-lc</string>
  <string>./scripts/run_api.sh</string>
</array>
```

- [ ] **Step 3: QA plist 작성**

운영과 같은 구조로 작성하되 라벨과 로그 경로만 QA 기준으로 둔다.

- [ ] **Step 4: 문법 검증**

Run:
`plutil -lint deploy/templates/launchd/com.muzlife.library-prod.plist`

Expected:
`OK`

Run:
`plutil -lint deploy/templates/launchd/com.muzlife.library-qa.plist`

Expected:
`OK`

- [ ] **Step 5: Commit**

```bash
git add deploy/templates/launchd/com.muzlife.library-prod.plist deploy/templates/launchd/com.muzlife.library-qa.plist
git commit -m "docs: add launchd templates for QA and production"
```

### Task 4: Cloudflare Tunnel 템플릿 추가

**Files:**
- Create: `deploy/templates/cloudflare/library-prod-config.yml`
- Create: `deploy/templates/cloudflare/library-qa-config.yml`

- [ ] **Step 1: 운영 ingress 작성**

```yaml
tunnel: __CLOUDFLARE_TUNNEL_ID__
credentials-file: /Users/__USER__/.cloudflared/__CLOUDFLARE_TUNNEL_ID__.json
ingress:
  - hostname: library.muzlife.com
    service: http://127.0.0.1:8000
  - service: http_status:404
```

- [ ] **Step 2: QA ingress 작성**

```yaml
tunnel: __CLOUDFLARE_TUNNEL_ID__
credentials-file: /Users/__USER__/.cloudflared/__CLOUDFLARE_TUNNEL_ID__.json
ingress:
  - hostname: __QA_DOMAIN__
    service: http://127.0.0.1:8100
  - service: http_status:404
```

- [ ] **Step 3: 런북에 연결**

런북에 아래 명령 예시를 추가한다.
- `cloudflared service install`
- `cloudflared tunnel route dns`

- [ ] **Step 4: Commit**

```bash
git add deploy/templates/cloudflare/library-prod-config.yml deploy/templates/cloudflare/library-qa-config.yml docs/macos_qa_prod_runbook.md
git commit -m "docs: add cloudflare tunnel deployment templates"
```

### Task 5: 운영 백업 -> QA 복원 절차 문서화

**Files:**
- Modify: `docs/macos_qa_prod_runbook.md`
- Reference: `scripts/run_deploy_preflight.sh`
- Reference: `scripts/run_qa_full.sh`

- [ ] **Step 1: 운영 백업 절차 작성**

포함:
- 운영 앱 정지 여부 판단
- DB 백업 경로
- 업로드 백업 경로
- 백업 파일명 규칙

- [ ] **Step 2: QA 복원 절차 작성**

포함:
- 기존 QA 데이터 덮어쓰기 경고
- DB 복원
- 업로드 복원
- QA 앱 재기동

- [ ] **Step 3: QA 검증 절차 작성**

```bash
./scripts/run_deploy_preflight.sh
./scripts/run_qa_full.sh
```

수동 검증 체크:
- 로그인
- 검색/관리
- 이동 작업대
- 구매 내역 가져오기
- 수입 큐

- [ ] **Step 4: Commit**

```bash
git add docs/macos_qa_prod_runbook.md
git commit -m "docs: document prod-to-QA restore workflow"
```

### Task 6: 운영 배포 및 롤백 절차 마감

**Files:**
- Modify: `docs/macos_qa_prod_runbook.md`

- [ ] **Step 1: 운영 배포 절차 정리**

순서:
1. 배포 직전 운영 백업
2. QA에서 통과한 같은 커밋 확인
3. 운영 코드 반영
4. 서비스 재시작
5. 헬스체크
6. 핵심 수동 확인

- [ ] **Step 2: 롤백 절차 정리**

순서:
1. 운영 앱 중지
2. 이전 커밋 복귀
3. 필요 시 DB 복원
4. 앱 재시작
5. 핵심 확인

- [ ] **Step 3: 최종 검토**

확인:
- QA와 운영의 역할이 명확한지
- 점검 허용형 배포 모델이 문서에 반영됐는지
- 실제 작업자가 복붙 가능한 수준인지

- [ ] **Step 4: 최종 검증**

Run:
`plutil -lint deploy/templates/launchd/com.muzlife.library-prod.plist && plutil -lint deploy/templates/launchd/com.muzlife.library-qa.plist`

Expected:
두 파일 모두 `OK`

- [ ] **Step 5: Commit**

```bash
git add docs/macos_qa_prod_runbook.md deploy/templates
git commit -m "docs: add macOS QA/prod deployment assets"
```
