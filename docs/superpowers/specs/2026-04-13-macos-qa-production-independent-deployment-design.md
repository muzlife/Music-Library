# macOS QA/운영 독립 배포 설계

## 목표

- `Mac mini M4`를 `QA` 전용 서버로 운영한다.
- `Mac mini M1`을 `운영` 전용 서버로 운영한다.
- `QA`는 운영 데이터를 복제해 실제 운영과 유사한 검증 환경으로 쓴다.
- 배포는 항상 `QA 검증 -> 운영 배포` 순서로 진행한다.
- `Synology`를 웹 진입점, 프록시, 인증서, 스토리지 의존성에서 제외한다.
- 운영 배포 시 짧은 점검 시간은 허용하되, 장애 없이 안정적으로 이어지도록 한다.

## 현재 요구

- `QA`: [https://qa.library.muzlife.com/](https://qa.library.muzlife.com/)
- `운영`: [https://library.muzlife.com/](https://library.muzlife.com/)
- 운영 데이터는 정기 또는 배포 직전 기준으로 `QA`에 복제한다.
- `QA`에서 자동/수동 검증을 충분히 거친 뒤 같은 커밋을 `운영`에 반영한다.
- `Synology` 없이 독립적으로 운영한다.

## 접근안 비교

### 1. 권장안: `Cloudflare DNS + Cloudflare Tunnel + 각 맥 전용 앱 런타임`

- 외부 진입점은 Cloudflare가 담당하고, 각 맥은 tunnel client를 통해 외부 도메인과 연결된다.
- `library.muzlife.com -> M1`
- `qa.library.muzlife.com -> M4`
- 각 맥은 내부에서만 앱 포트를 연다.

장점
- `443` 포트 분기, 인증서, 외부 공개를 서버별로 직접 처리하지 않아도 된다.
- `Synology`를 완전히 제외하기 쉽다.
- 공인 IP 1개 환경에서도 `QA/운영`을 호스트 기반으로 쉽게 분리할 수 있다.

단점
- Cloudflare 의존성이 생긴다.
- 로컬 완전 자가 네트워크보다 외부 서비스 하나가 더 들어간다.

### 2. 자가 엣지안: `라우터/소형 프록시 + 각 맥 전용 앱 런타임`

- 별도 엣지 장비가 `qa.library.muzlife.com` 과 `library.muzlife.com`을 받아 Host 기준으로 `M4`, `M1`에 분기한다.

장점
- 네트워크를 완전히 자가 통제할 수 있다.

단점
- 라우터/프록시 설정 난이도가 높다.
- 인증서, 프록시, 포트포워딩, 장애 추적 부담이 커진다.

### 3. 비권장안: `운영/QA를 한 장비 또는 같은 경로에서만 논리 분리`

- 포트나 DB만 나누고 나머지는 공유하는 방식이다.

문제
- 경로 오염, 세션 혼동, 업로드 혼입, 백업 범위 혼동이 생기기 쉽다.
- 지금 목표인 `운영 안정성`과 `QA 실운영 검증`에 맞지 않는다.

## 권장 구조

- `M4`: QA 전용
- `M1`: 운영 전용
- 외부 도메인 분기: `Cloudflare Tunnel`
- 앱 실행: macOS `launchd`
- 앱 포트:
  - QA: `127.0.0.1:8100`
  - 운영: `127.0.0.1:8000`
- 각 서버는 `코드`, `DB`, `업로드`, `로그`, `백업`, `환경변수`를 완전히 분리한다.

## 환경 분리 규칙

### 운영 M1

- 서비스명: `library-prod`
- 도메인: `library.muzlife.com`
- 앱 루트 예시: `/Users/<user>/apps/hahahoho-prod`
- 런타임 루트 예시: `/Users/<user>/apps/hahahoho-prod/runtime`

구성 예시
- DB: `/Users/<user>/apps/hahahoho-prod/runtime/data/library.db`
- 업로드: `/Users/<user>/apps/hahahoho-prod/runtime/uploads`
- 로그: `/Users/<user>/apps/hahahoho-prod/runtime/logs`
- 백업: `/Users/<user>/apps/hahahoho-prod/runtime/backups`
- import 임시 파일: `/Users/<user>/apps/hahahoho-prod/runtime/imports`

### QA M4

- 서비스명: `library-qa`
- 도메인: `qa.library.muzlife.com`
- 앱 루트 예시: `/Users/<user>/apps/hahahoho-qa`
- 런타임 루트 예시: `/Users/<user>/apps/hahahoho-qa/runtime`

구성 예시
- DB: `/Users/<user>/apps/hahahoho-qa/runtime/data/library.db`
- 업로드: `/Users/<user>/apps/hahahoho-qa/runtime/uploads`
- 로그: `/Users/<user>/apps/hahahoho-qa/runtime/logs`
- 백업: `/Users/<user>/apps/hahahoho-qa/runtime/backups`
- 운영 복제 import: `/Users/<user>/apps/hahahoho-qa/runtime/imports`

### 분리 원칙

1. QA와 운영은 같은 DB 파일을 절대 공유하지 않는다.
2. QA와 운영은 같은 업로드 경로를 절대 공유하지 않는다.
3. QA와 운영은 같은 `.env.local`을 절대 공유하지 않는다.
4. QA와 운영은 같은 세션 시크릿을 쓰지 않는다.
5. QA와 운영은 같은 webhook token을 쓰지 않는다.

## 도메인 / TLS / 네트워크

### DNS

- `library.muzlife.com`
- `qa.library.muzlife.com`

DNS는 `Synology`가 아니라 외부 DNS 서비스에서 직접 관리한다.

### 권장 연결

- `library.muzlife.com -> Cloudflare Tunnel -> M1:127.0.0.1:8000`
- `qa.library.muzlife.com -> Cloudflare Tunnel -> M4:127.0.0.1:8100`

### TLS

- 외부 HTTPS는 Cloudflare가 맡는다.
- 내부 앱은 로컬 포트로만 노출한다.
- 앱 쿠키는 HTTPS 기준으로만 동작하도록 `LIBRARY_AUTH_COOKIE_SECURE=1`을 사용한다.

## 앱 실행 방식

각 서버는 앱을 `launchd` 서비스로 등록한다.

권장 이유
- macOS 기본 서비스 관리자와 맞다.
- 부팅 후 자동 실행이 쉽다.
- 프로세스 비정상 종료 시 재기동이 쉽다.

권장 서비스 구성
- `~/Library/LaunchAgents/com.muzlife.library-prod.plist`
- `~/Library/LaunchAgents/com.muzlife.library-qa.plist`

서비스 역할
- 운영 plist: `uvicorn app.main:app --host 127.0.0.1 --port 8000`
- QA plist: `uvicorn app.main:app --host 127.0.0.1 --port 8100`

## 환경변수 구성

### 운영 `.env.local`

필수 예시
- `LIBRARY_DB_PATH`
- `LIBRARY_AUTH_COOKIE_SECURE=1`
- `LIBRARY_ADMIN_USERNAME`
- `LIBRARY_ADMIN_PASSWORD`
- `LIBRARY_OPERATOR_USERNAME`
- `LIBRARY_OPERATOR_PASSWORD`
- `LIBRARY_AUTH_SESSION_SECRET`
- `LIBRARY_PURCHASE_IMPORT_TOKEN`
- `DISCOGS_TOKEN`
- `ALADIN_TTB_KEY`

### QA `.env.local`

운영과 동일한 키 구조를 쓰되 값은 QA 전용으로 둔다.

추가 원칙
- QA 관리자 계정은 운영과 다르게 둘 수 있으면 다르게 둔다.
- QA 세션 secret은 운영과 다르게 둔다.
- QA webhook token은 운영과 다르게 둔다.
- QA 외부 연동은 필요 최소만 복제한다.

## 운영 데이터 복제 설계

### 목적

- QA가 샘플 데이터가 아니라 운영과 유사한 상태에서 검증되도록 한다.
- 최근 운영 데이터에서만 드러나는 파싱, 정렬, 관계, 이동 작업대, 큐 누적 문제를 QA에서 먼저 잡는다.

### 복제 단위

최소
- `library.db`

권장
- `library.db`
- 업로드/이미지 자산
- 필요 시 전체 백업 번들

### 권장 흐름

1. 운영 M1에서 백업 생성
2. 백업 파일을 QA M4로 복사
3. QA에서 복원
4. QA 앱 재기동
5. QA 자동/수동 검증

### 운영 규칙

- QA의 테스트 데이터는 다음 운영 복제 때 덮어써도 되는 구조로 본다.
- 배포 후보 검증 전에는 가능한 한 최신 운영 백업으로 QA를 갱신한다.

## 배포 절차

### 1. QA 준비

1. 배포 후보 커밋 확정
2. QA 서버 코드 업데이트
3. 운영 백업을 QA에 복원
4. QA 앱 재기동

### 2. QA 검증

자동 검증
- `./scripts/run_deploy_preflight.sh`
- `./scripts/run_qa_full.sh` 또는 필요한 QA 묶음

수동 검증
- 로그인
- 검색/관리
- 직접 등록
- 이동 작업대
- 구매 내역 가져오기
- 수입 큐
- 소스 보강
- 백업/복원 화면

### 3. 운영 배포

1. 운영 공지 또는 짧은 점검 진입
2. 운영 M1에서 배포 직전 백업 생성
3. QA에서 통과한 같은 커밋으로 운영 코드 업데이트
4. 운영 앱 재시작
5. `/health` 확인
6. 핵심 동선 확인
7. 점검 종료

## 롤백 절차

운영 배포 전에는 아래 두 기준점을 남긴다.

1. 직전 운영 코드 커밋
2. 직전 운영 DB 백업

이상 발생 시

1. 운영 앱 중지
2. 코드 이전 커밋으로 복귀
3. 필요 시 배포 직전 DB 백업 복원
4. 앱 재시작
5. `/health`, 로그인, 핵심 화면 재확인

## 절차형 구축 순서

### 단계 1. M1 운영 서버 구축

1. 운영 전용 디렉터리 생성
2. 운영 전용 `.venv` 생성
3. 운영 전용 `runtime/data`, `runtime/uploads`, `runtime/logs`, `runtime/backups` 생성
4. 운영 `.env.local` 작성
5. 운영 `launchd` 등록
6. 로컬 `http://127.0.0.1:8000/health` 확인

### 단계 2. M4 QA 서버 구축

1. QA 전용 디렉터리 생성
2. QA 전용 `.venv` 생성
3. QA 전용 `runtime/data`, `runtime/uploads`, `runtime/logs`, `runtime/backups` 생성
4. QA `.env.local` 작성
5. QA `launchd` 등록
6. 로컬 `http://127.0.0.1:8100/health` 확인

### 단계 3. DNS / 외부 연결

1. DNS를 Synology 바깥에서 관리하도록 이전
2. `library.muzlife.com`, `qa.library.muzlife.com` 생성
3. 각 서버에 Cloudflare Tunnel 연결
4. 외부 HTTPS 접속 확인

### 단계 4. 데이터 복제 리허설

1. 운영 백업 생성
2. QA로 복사
3. QA 복원
4. QA 재기동
5. QA 검증

### 단계 5. 첫 배포 리허설

1. QA에서 새 커밋 검증
2. 운영 점검 시작
3. 운영 백업
4. 운영 배포
5. 운영 헬스체크
6. 필요 시 롤백 리허설

## 성공 기준

- `qa.library.muzlife.com` 는 항상 `M4 QA`에 연결된다.
- `library.muzlife.com` 는 항상 `M1 운영`에 연결된다.
- 운영 데이터 복제가 QA에서 실제로 복원된다.
- QA 검증 후 같은 커밋만 운영에 반영된다.
- 운영 배포 직전 백업과 롤백 절차가 문서화되어 있다.
- `Synology` 없이도 DNS, HTTPS, 앱 실행, 백업, 배포가 유지된다.

## 후속 구현 항목

1. `launchd plist` 템플릿 작성
2. `Cloudflare Tunnel` 설정 절차 문서 작성
3. `M1 운영 / M4 QA` 폴더 구조와 `.env.local` 예시 문서화
4. 운영 백업 -> QA 복제 스크립트 작성
5. 배포 체크리스트를 `QA`와 `운영`으로 나눠 문서화
