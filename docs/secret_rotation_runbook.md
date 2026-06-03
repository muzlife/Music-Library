# 자격증명 회전 런북

`.env.local`(QA) 와 운영기 `.env`(prod)에 들어가 있는 평문 시크릿을 안전하게 교체하는 절차입니다. 모든 회전은 **서비스 무중단 보장 X — 짧은 재시작 창이 필요**합니다.

> **2026-05-27 업데이트:** QA 서버는 이제 launchd plist의 `EnvironmentVariables`에서 시크릿을 직접 읽습니다.
> `.env.local`은 개발/fallback 용이며, launchd가 제공하는 환경변수가 우선합니다.
> 시크릿 회전 시 **plist와 `.env.local`을 모두 갱신**해야 합니다.
> 자세한 설정은 `runtime/plist/com.muzlife.library-qa.plist`와 `scripts/install_qa_plist.sh` 참조.

회전 대상은 7종입니다.

| ENV 변수 | 종류 | 회전 빈도 권장 | 영향 범위 |
| :-- | :-- | :-- | :-- |
| `DISCOGS_TOKEN` | 외부 API 토큰 | 분실/노출 시 즉시 | 메타 동기화, 검색/등록 |
| `ALADIN_TTB_KEY` | 외부 API 키 | 분실/노출 시 즉시 | 알라딘 메타 |
| `DEEPL_AUTH_KEY` | 외부 API 키 | 분실/노출 시 즉시 | 아티스트 컨텍스트 번역 |
| `LIBRARY_ADMIN_PASSWORD` / `LIBRARY_OPERATOR_PASSWORD` / `LIBRARY_OPERATOR_ACCOUNTS` | 운영자 비번 | 90일 또는 인사 변동 시 | 로그인 |
| `LIBRARY_AUTH_SESSION_SECRET` | 쿠키 서명 키 | 90일 또는 노출 시 | 모든 사용자 강제 재로그인 |
| `LIBRARY_PURCHASE_IMPORT_TOKEN` | 웹훅 공유 비밀 | 30~90일 | Gmail/Zapier 웹훅 |
| `HOME_ASSISTANT_TOKEN` | HA Long-Lived Token | 분실/노출 시 즉시 | 사무실 온습도 위젯 |

> **공통 원칙** — 모든 시크릿은 `secrets.token_urlsafe(32)`처럼 충분히 긴 무작위 값을 사용합니다. 이메일/이름 같은 추측 가능한 문자열은 금지.

---

## 0. 회전 전 공통 준비

```bash
# 1. 현재 .env.local을 안전 백업
cp /Volumes/Data/Works/07.__PROJECT_SLUG__/.env.local /Volumes/Data/Works/07.__PROJECT_SLUG__/.env.local.bak.$(date +%Y%m%d_%H%M)

# 2. 권한이 600인지 확인 (혹시 644면 즉시 600)
stat -f "%Sp %N" /Volumes/Data/Works/07.__PROJECT_SLUG__/.env.local
chmod 600 /Volumes/Data/Works/07.__PROJECT_SLUG__/.env.local

# 3. 운영기에서도 동일하게
ssh USER@PROD_HOST.local 'cp /Users/USER/apps/__PROJECT_SLUG__-prod/.env /Users/USER/apps/__PROJECT_SLUG__-prod/.env.bak.$(date +%Y%m%d_%H%M) && chmod 600 /Users/USER/apps/__PROJECT_SLUG__-prod/.env'
```

새 값을 만들 때 쓰는 도구.

```bash
# URL-safe 32바이트 무작위 (세션 시크릿/웹훅 토큰용)
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# 16자리 영숫자 (운영자 비번용. 반드시 사람이 외울 필요 없음)
python3 -c "import secrets, string; print(''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(20)))"
```

---

## 1. `DISCOGS_TOKEN`

1. https://www.discogs.com/settings/developers 로 로그인
2. **Generate new token** → 표시된 값 복사 (한 번만 보임)
3. 옛 토큰은 같은 페이지에서 **Revoke**
4. `.env.local` 의 `DISCOGS_TOKEN="..."` 갱신
5. 운영기/QA 양쪽 모두 적용 (rsync 가 아니라 직접 ssh 후 vi)
6. 재시작 (아래 §재시작 절차)
7. 확인:
   ```bash
   curl -s -H "x-purchase-import-token: ..." \
        http://127.0.0.1:8000/discogs/identity | jq .
   ```
   `consumer_name` 이 본인 디스코그스 계정으로 응답되면 OK

---

## 2. `ALADIN_TTB_KEY`

1. https://blog.aladin.co.kr/openapi/popup/6695306 → API 신청 페이지에서 Key 발급
2. 옛 키는 같은 페이지의 **API 키 재발급** 으로 무효화 (현재 알라딘은 직접 revoke API 가 없으므로 재발급 = 회전)
3. `.env.local` 갱신 → 재시작
4. 확인:
   ```bash
   # 등록/수집 화면에서 ALADIN 검색 한 번 시도. 캔디데이트가 0건이 아니면 OK.
   ```

---

## 3. `DEEPL_AUTH_KEY`

1. https://www.deepl.com/account/summary → **API Key** 항목에서 새 키 생성
2. 옛 키는 동일 페이지의 휴지통 아이콘으로 삭제
3. `.env.local` 갱신 → 재시작
4. 확인:
   ```bash
   # 운영/연계 → 메타 제공자 → "DeepL 연결 테스트" 버튼이 200 ok 응답
   curl -s -X POST http://127.0.0.1:8000/ops/provider-settings/deepl-test \
        -H "Cookie: __PROJECT_SLUG___session=..." | jq .
   ```

---

## 4. 운영자 비번 (`LIBRARY_*_PASSWORD` / `LIBRARY_OPERATOR_ACCOUNTS`)

> **이번 변경(2026-04) 이후 ENV 비번은 부트스트랩 1회용입니다.** 시드된 다음에는 ENV를 바꿔도 로그인에 영향이 없습니다. 실제 운영자 비번 변경은 화면(`8-4. 계정`) 또는 API로 합니다.

### 4-A. 처음 시드 후 ENV 정리 (한 번만)

```bash
# 시드가 끝났는지 확인 (DB에 row가 보여야 함)
ssh USER@PROD_HOST.local "sqlite3 /Users/USER/apps/__PROJECT_SLUG__-prod/runtime/data/library.db \
  'SELECT username, role FROM auth_account WHERE is_active = 1;'"
# admin/ADMIN, operator/OPERATOR, kinolifecom/OPERATOR ... 가 보이면 시드 완료
```

이후 ENV는 **빈 값**으로 정리합니다. (완전히 지워도 되지만, 향후 새 운영기 부트스트랩이 또 필요해질 수 있으니 빈 줄로 유지 권장.)

```dotenv
LIBRARY_ADMIN_USERNAME=
LIBRARY_ADMIN_PASSWORD=
LIBRARY_OPERATOR_USERNAME=
LIBRARY_OPERATOR_PASSWORD=
LIBRARY_OPERATOR_ACCOUNTS=
```

### 4-B. 평소 비번 회전 (90일 또는 인사 변동)

브라우저:
1. 관리자 로그인 → `운영/연계 → 8-4. 계정`
2. 대상 계정 **수정** → 새 비밀번호 입력 → 저장

또는 API:
```bash
curl -s -X PATCH "http://127.0.0.1:8000/admin/auth-accounts/<username>" \
     -H "Content-Type: application/json" \
     -H "Cookie: __PROJECT_SLUG___session=..." \
     -d '{"password": "<새-비번>"}'
```

확인:
```bash
curl -s -X POST http://127.0.0.1:8000/auth/login \
     -d "username=<username>&password=<새-비번>"
# 200 ok 면 성공
```

### 4-C. 직원 퇴사

1. `8-4. 계정` 화면에서 **사용 중지**(is_active=false) 또는 **삭제**.
2. DB에서 흔적까지 지우려면:
   ```bash
   curl -s -X DELETE "http://127.0.0.1:8000/admin/auth-accounts/<username>" \
        -H "Cookie: __PROJECT_SLUG___session=..."
   ```

---

## 5. `LIBRARY_AUTH_SESSION_SECRET`

이 값을 바꾸면 **모든 기존 로그인 쿠키가 무효화**됩니다. 사용자가 다시 로그인합니다. 운영시간 외에 진행 권장.

```bash
# 새 시크릿
NEW_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
echo "$NEW_SECRET"

# .env.local 갱신
# plist도 동일한 값으로 갱신
vim runtime/plist/com.muzlife.library-qa.plist
# install_qa_plist.sh로 반영
sed -i.bak "s|^LIBRARY_AUTH_SESSION_SECRET=.*|LIBRARY_AUTH_SESSION_SECRET=\"$NEW_SECRET\"|" \
    /Volumes/Data/Works/07.__PROJECT_SLUG__/.env.local

# 운영기에도 동일하게
ssh USER@PROD_HOST.local \
  "sed -i.bak 's|^LIBRARY_AUTH_SESSION_SECRET=.*|LIBRARY_AUTH_SESSION_SECRET=\"$NEW_SECRET\"|' /Users/USER/apps/__PROJECT_SLUG__-prod/.env"
```

재시작 후 모든 사용자가 `/login` 으로 리다이렉트되면 OK.

---

## 6. `LIBRARY_PURCHASE_IMPORT_TOKEN`

이 값을 바꾸면 **Gmail/Zapier 측 웹훅 설정도 동시 갱신** 해야 합니다. 안 그러면 그 시점부터 들어오는 웹훅이 모두 403.

1. 새 토큰 발급:
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
2. `.env.local` / 운영기 `.env` 양쪽 갱신
3. **외부 발신처 갱신을 먼저** 하면 그 사이 503 처럼 보일 수 있음. 순서 권장:
   1. 새 토큰을 발신처(Apps Script / Zapier)에 추가
   2. 코드측 `.env` 갱신 + 재시작
   3. Apps Script / Zapier 에서 옛 토큰 제거
4. 확인:
   ```bash
   # 정상 토큰
   curl -s -X POST http://127.0.0.1:8000/purchase-imports/webhook/gmail \
        -H "x-purchase-import-token: <새-토큰>" \
        -H "Content-Type: application/json" \
        -d '{"raw_content":"noop","vendor_code":"OTHER","source_type":"EMAIL_HTML","source_ref":"rotation-probe"}'
   # → 200 (created_count 0 이어도 OK; 토큰 통과 자체가 검증)

   # 옛 토큰 → 403 이 와야 회전 성공
   curl -s -o /dev/null -w "%{http_code}\n" \
        -X POST http://127.0.0.1:8000/purchase-imports/webhook/gmail \
        -H "x-purchase-import-token: <옛-토큰>" \
        -H "Content-Type: application/json" \
        -d '{"raw_content":"noop","vendor_code":"OTHER","source_type":"EMAIL_HTML"}'
   # → 403
   ```

---

## 7. `HOME_ASSISTANT_TOKEN`

1. HA UI → Profile → **Long-Lived Access Tokens** → Create Token
2. 옛 토큰은 같은 페이지에서 휴지통 아이콘으로 삭제
3. `.env.local` 갱신 → 재시작
4. 확인:
   ```bash
   # 운영 홈 → 사무실 온습도 위젯이 정상 표시되면 OK
   curl -s http://127.0.0.1:8000/operator/office-climate \
        -H "Cookie: __PROJECT_SLUG___session=..." | jq .
   ```

---

## 재시작 절차

### QA 로컬 (mac mini)
```bash
launchctl kickstart -k gui/$(id -u)/com.muzlife.library-qa
sleep 2
curl -s http://127.0.0.1:8100/health
# {"status":"ok"} 면 OK
```

### Production
```bash
ssh USER@PROD_HOST.local 'launchctl kickstart -k gui/$(id -u)/com.muzlife.library-prod && sleep 2 && curl -s http://127.0.0.1:8000/health'
# {"status":"ok"} 면 OK
```

### 외부 health
```bash
curl -s https://__QA_DOMAIN__/health
curl -s https://library.muzlife.com/health
```

---

## 회전 후 정리

회전이 모두 끝난 뒤 백업한 `.env.local.bak.*` 파일을 안전한 보관 위치(예: 1Password, macOS Keychain)로 옮기고 디스크에서 삭제합니다. 검토용으로 7일 이상 디스크에 두지 않는 것이 안전합니다.

```bash
# 1Password CLI 가 설치돼 있다면
op item create --category=secure-note --title="__PROJECT_SLUG__ .env.local backup $(date +%Y-%m-%d)" \
  --vault=Private notesPlain="$(cat /Volumes/Data/Works/07.__PROJECT_SLUG__/.env.local.bak.<날짜>)"

# 그 후 디스크 백업 삭제
shred -uvz /Volumes/Data/Works/07.__PROJECT_SLUG__/.env.local.bak.*  # GNU
# macOS 기본은 shred 없음 → rm -P 사용
rm -P /Volumes/Data/Works/07.__PROJECT_SLUG__/.env.local.bak.*
```

---

## 회전 빈도 트래커 (참고)

다음 회전 시점은 `docs/qa/qa_master_sheet.csv`의 마지막 회전 행을 보고 알 수 있습니다. 회전 후 한 줄 추가 권장:

```
SEC-XXX,Security / Rotation,운영/연계,관리자,prod,Operations,,P1,Non-blocking,Manual-only,
DISCOGS_TOKEN 회전,장비 정비 후 / steps=...,...,Verified,Pass,2026-04-29T12:00:00+09:00,
jingun.park,,...
```
