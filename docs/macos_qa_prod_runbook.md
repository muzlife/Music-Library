# macOS QA/운영 독립 배포 런북

## 개요

이 문서는 `Mac mini M4`를 `QA`, `Mac mini M1`을 `운영`으로 완전히 분리해서 `qa.library.muzlife.com` / `library.muzlife.com` 기준으로 운영하는 절차를 정리합니다.

- QA: `https://qa.library.muzlife.com/`
- 운영: `https://library.muzlife.com/`
- 외부 진입: `Cloudflare DNS + Cloudflare Tunnel`
- 서비스 관리: macOS `launchd`
- 앱 실행: 저장소의 [`scripts/run_api.sh`](/Volumes/Works/07.hahahoho/scripts/run_api.sh)

이 런북은 `Synology`를 웹 진입점, 프록시, 인증서, 스토리지 의존성에서 제외하는 것을 전제로 합니다.

## 1. 서버 역할 고정

### 운영 서버: `Mac mini M1`

- 서비스명: `library-prod`
- 코드 루트 예시: `/Users/<user>/apps/hahahoho-prod`
- 런타임 루트 예시: `/Users/<user>/apps/hahahoho-prod/runtime`
- 로컬 앱 포트: `127.0.0.1:8000`
- 외부 도메인: `library.muzlife.com`

### QA 서버: `Mac mini M4`

- 서비스명: `library-qa`
- 코드 루트 예시: `/Users/<user>/apps/hahahoho-qa`
- 런타임 루트 예시: `/Users/<user>/apps/hahahoho-qa/runtime`
- 로컬 앱 포트: `127.0.0.1:8100`
- 외부 도메인: `qa.library.muzlife.com`

## 2. 디렉터리 준비

운영/QA 모두 같은 구조를 쓰되 경로는 완전히 분리합니다.

```text
apps/
  hahahoho-prod/
    .venv/
    .env.local
    runtime/
      data/
      uploads/
      logs/
      backups/
      imports/
  hahahoho-qa/
    .venv/
    .env.local
    runtime/
      data/
      uploads/
      logs/
      backups/
      imports/
```

권장 명령 예시:

```bash
mkdir -p /Users/<user>/apps/hahahoho-prod/runtime/{data,uploads,logs,backups,imports}
mkdir -p /Users/<user>/apps/hahahoho-qa/runtime/{data,uploads,logs,backups,imports}
```

반복 작업을 줄이려면 아래 보조 스크립트를 바로 써도 됩니다.

```bash
./deploy/scripts/bootstrap_macos_runtime.sh prod /Users/<user>/apps/hahahoho-prod
./deploy/scripts/bootstrap_macos_runtime.sh qa /Users/<user>/apps/hahahoho-qa
```

## 3. Python / 가상환경 준비

각 서버에서 저장소를 별도 체크아웃한 뒤 가상환경을 만듭니다.

```bash
cd /Users/<user>/apps/hahahoho-prod
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

QA도 같은 방식으로 진행합니다.

## 4. 환경변수 작성

템플릿 파일:

- [운영 env 예시](/Volumes/Works/07.hahahoho/deploy/templates/env/.env.production.example)
- [QA env 예시](/Volumes/Works/07.hahahoho/deploy/templates/env/.env.qa.example)

핵심 규칙:

1. QA와 운영은 `LIBRARY_DB_PATH`를 절대 공유하지 않습니다.
2. QA와 운영은 `LIBRARY_AUTH_SESSION_SECRET`을 다르게 둡니다.
3. QA와 운영은 `LIBRARY_PURCHASE_IMPORT_TOKEN`을 다르게 둡니다.
4. 두 환경 모두 `LIBRARY_AUTH_COOKIE_SECURE=1`을 사용합니다.
5. `APP_PORT`는 운영 `8000`, QA `8100`으로 분리합니다.

## 5. launchd 등록

템플릿 파일:

- [운영 launchd 템플릿](/Volumes/Works/07.hahahoho/deploy/templates/launchd/com.muzlife.library-prod.plist)
- [QA launchd 템플릿](/Volumes/Works/07.hahahoho/deploy/templates/launchd/com.muzlife.library-qa.plist)

절차:

1. 템플릿의 `__APP_ROOT__`를 실제 앱 루트로 치환합니다.
2. 운영은 `~/Library/LaunchAgents/com.muzlife.library-prod.plist`에 복사합니다.
3. QA는 `~/Library/LaunchAgents/com.muzlife.library-qa.plist`에 복사합니다.
4. 문법 점검:

```bash
plutil -lint ~/Library/LaunchAgents/com.muzlife.library-prod.plist
plutil -lint ~/Library/LaunchAgents/com.muzlife.library-qa.plist
```

5. 서비스 등록:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.muzlife.library-prod.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.muzlife.library-qa.plist
```

보조 스크립트로 plist를 렌더링/설치하려면:

```bash
./deploy/scripts/install_launchd_service.sh prod /Users/<user>/apps/hahahoho-prod
./deploy/scripts/install_launchd_service.sh qa /Users/<user>/apps/hahahoho-qa
```

재기동/반영:

```bash
launchctl kickstart -k gui/$(id -u)/com.muzlife.library-prod
launchctl kickstart -k gui/$(id -u)/com.muzlife.library-qa
```

## 6. Cloudflare DNS / Tunnel 연결

템플릿 파일:

- [운영 tunnel 설정 예시](/Volumes/Works/07.hahahoho/deploy/templates/cloudflare/library-prod-config.yml)
- [QA tunnel 설정 예시](/Volumes/Works/07.hahahoho/deploy/templates/cloudflare/library-qa-config.yml)

권장 매핑:

- `library.muzlife.com -> http://127.0.0.1:8000`
- `qa.library.muzlife.com -> http://127.0.0.1:8100`

Cloudflare 절차 예시:

```bash
cloudflared tunnel login
cloudflared tunnel create library-prod
cloudflared tunnel create library-qa
cloudflared tunnel route dns <PROD_TUNNEL_ID> library.muzlife.com
cloudflared tunnel route dns <QA_TUNNEL_ID> qa.library.muzlife.com
```

설정 파일을 배치한 뒤 서비스 설치:

```bash
cloudflared service install
```

템플릿을 실제 설정 파일로 렌더링하려면:

```bash
./deploy/scripts/render_cloudflare_tunnel_config.sh prod <PROD_TUNNEL_ID> ~/.cloudflared/library-prod.yml
./deploy/scripts/render_cloudflare_tunnel_config.sh qa <QA_TUNNEL_ID> ~/.cloudflared/library-qa.yml
```

운영/QA 각각 해당 맥에서 자신의 tunnel 설정 파일을 사용하도록 맞춥니다.

## 7. 서비스 상태 점검

운영 M1:

```bash
curl -I http://127.0.0.1:8000/health
```

QA M4:

```bash
curl -I http://127.0.0.1:8100/health
```

저장소 기준 상태 점검:

```bash
./scripts/check_library_status.sh --short
```

## 8. 운영 백업 -> QA 복제

목표는 `QA`가 항상 최근 운영 상태에 가까운 데이터로 검증되게 하는 것입니다.

### 운영 M1에서 백업 생성

최소 대상:

- `runtime/data/library.db`

권장 대상:

- `runtime/data/library.db`
- `runtime/uploads/`

예시:

```bash
ts=$(date +"%Y%m%d-%H%M%S")
cp /Users/<user>/apps/hahahoho-prod/runtime/data/library.db \
  /Users/<user>/apps/hahahoho-prod/runtime/backups/library-${ts}.db
tar -czf /Users/<user>/apps/hahahoho-prod/runtime/backups/uploads-${ts}.tgz \
  -C /Users/<user>/apps/hahahoho-prod/runtime uploads
```

### QA M4로 복사

예시:

```bash
rsync -av /Users/<user>/apps/hahahoho-prod/runtime/backups/library-<ts>.db <qa-user>@<qa-host>:/Users/<user>/apps/hahahoho-qa/runtime/imports/
rsync -av /Users/<user>/apps/hahahoho-prod/runtime/backups/uploads-<ts>.tgz <qa-user>@<qa-host>:/Users/<user>/apps/hahahoho-qa/runtime/imports/
```

### QA M4에서 복원

```bash
cp /Users/<user>/apps/hahahoho-qa/runtime/imports/library-<ts>.db \
  /Users/<user>/apps/hahahoho-qa/runtime/data/library.db
tar -xzf /Users/<user>/apps/hahahoho-qa/runtime/imports/uploads-<ts>.tgz \
  -C /Users/<user>/apps/hahahoho-qa/runtime
launchctl kickstart -k gui/$(id -u)/com.muzlife.library-qa
```

보조 스크립트를 쓰면:

```bash
./deploy/scripts/restore_backup_to_qa.sh /Users/<user>/apps/hahahoho-qa /tmp/library-<ts>.db /tmp/uploads-<ts>.tgz
```

주의:

- QA의 기존 데이터는 덮어써도 되는 전제로 운영합니다.
- QA에서 임시 테스트로 만든 데이터는 다음 복제 시 사라질 수 있습니다.

## 9. QA 검증 절차

운영 데이터를 복원한 뒤 QA에서 먼저 검증합니다.

사전 점검:

```bash
./scripts/run_deploy_preflight.sh
```

전체 QA:

```bash
./scripts/run_qa_full.sh
```

수동 검증 체크:

1. 로그인
2. 검색/관리
3. 직접 등록
4. 이동 작업대
5. 구매 내역 가져오기
6. 수입 큐
7. 소스 보강
8. 백업/복원 화면

규칙:

- QA에서 통과한 **같은 커밋**만 운영으로 올립니다.
- 운영에서 먼저 수정하고 QA에 나중에 맞추는 흐름은 금지합니다.

## 10. 운영 배포 절차

운영은 짧은 점검 시간을 허용하는 전제로 갑니다.

1. 사용자에게 짧은 점검 공지
2. 운영 M1에서 배포 직전 백업 생성
3. QA에서 통과한 같은 커밋 체크아웃
4. 필요 시 의존성 설치
5. 운영 앱 재기동
6. 헬스체크
7. 핵심 동선 수동 확인
8. 점검 종료

권장 점검 항목:

- `https://library.muzlife.com/` 접속
- 로그인
- 관리 메인 진입
- 검색
- 등록
- 구매 수입
- 이동 작업대

## 11. 롤백 절차

운영 배포 전에는 반드시 아래 두 기준점을 남깁니다.

1. 직전 코드 커밋
2. 직전 DB 백업

롤백 순서:

1. 운영 앱 중지 또는 점검 유지
2. 이전 커밋으로 코드 복귀
3. 필요 시 직전 DB 백업 복원
4. 앱 재시작
5. `/health` 확인
6. 로그인/핵심 동선 확인

## 12. 첫 구축 체크리스트

1. M1 운영 디렉터리 생성
2. M4 QA 디렉터리 생성
3. 양쪽 `.venv` 설치
4. 양쪽 `.env.local` 작성
5. 양쪽 `launchd` 등록
6. 양쪽 `cloudflared` 연결
7. 운영 로컬 헬스체크 확인
8. QA 로컬 헬스체크 확인
9. 운영 DB -> QA 복제 1회 리허설
10. QA preflight/QA full 리허설
11. 운영 무반영 상태에서 배포 리허설

## 13. 관련 자산

- [배포 설계 스펙](/Volumes/Works/07.hahahoho/docs/superpowers/specs/2026-04-13-macos-qa-production-independent-deployment-design.md)
- [배포 구현 계획](/Volumes/Works/07.hahahoho/docs/superpowers/plans/2026-04-13-macos-qa-production-independent-deployment-implementation.md)
- [운영 env 템플릿](/Volumes/Works/07.hahahoho/deploy/templates/env/.env.production.example)
- [QA env 템플릿](/Volumes/Works/07.hahahoho/deploy/templates/env/.env.qa.example)
- [운영 launchd 템플릿](/Volumes/Works/07.hahahoho/deploy/templates/launchd/com.muzlife.library-prod.plist)
- [QA launchd 템플릿](/Volumes/Works/07.hahahoho/deploy/templates/launchd/com.muzlife.library-qa.plist)
- [운영 Cloudflare Tunnel 템플릿](/Volumes/Works/07.hahahoho/deploy/templates/cloudflare/library-prod-config.yml)
- [QA Cloudflare Tunnel 템플릿](/Volumes/Works/07.hahahoho/deploy/templates/cloudflare/library-qa-config.yml)
- [런타임 준비 스크립트](/Volumes/Works/07.hahahoho/deploy/scripts/bootstrap_macos_runtime.sh)
- [launchd 설치 스크립트](/Volumes/Works/07.hahahoho/deploy/scripts/install_launchd_service.sh)
- [Cloudflare 설정 렌더 스크립트](/Volumes/Works/07.hahahoho/deploy/scripts/render_cloudflare_tunnel_config.sh)
- [QA 복원 스크립트](/Volumes/Works/07.hahahoho/deploy/scripts/restore_backup_to_qa.sh)
