# Login Shell Theme And Locale Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 로그인 화면에 운영/관리 콘솔과 어울리는 언어 선택기와 주/야간 토글을 추가하고, 로그인 전 설정이 로그인 후에도 그대로 유지되게 만든다.

**Architecture:** 서버 인증 흐름은 건드리지 않고 [app/static/login.html](/Volumes/Data/Works/07.hahahoho/app/static/login.html) 안에 로그인 전용 shell utility와 최소 i18n/theme 초기화만 넣는다. 상태 저장은 메인 콘솔과 같은 `localStorage` key literal을 직접 사용하고, 테스트는 기존 정적 HTML 검사용 [tests/test_ops_shell_bootstrap.py](/Volumes/Data/Works/07.hahahoho/tests/test_ops_shell_bootstrap.py) 중심으로 고정한다.

**Tech Stack:** FastAPI static page delivery, vanilla HTML/CSS/JS, pytest

---

## File Map

- Modify: `/Volumes/Data/Works/07.hahahoho/app/static/login.html`
  - 로그인 전용 shell utility row
  - day/night theme token
  - login-scoped locale message table
  - theme/locale persistence and auth error mapping
- Modify: `/Volumes/Data/Works/07.hahahoho/tests/test_ops_shell_bootstrap.py`
  - 로그인 페이지 정적 HTML/스크립트 회귀 테스트 추가
- Modify: `/Volumes/Data/Works/07.hahahoho/tests/test_ops_route_access.py`
  - `/login` route smoke 추가

## Task 1: Lock The Login Page Contract With Failing Static Tests

**Files:**
- Modify: `/Volumes/Data/Works/07.hahahoho/tests/test_ops_shell_bootstrap.py`
- Verify against: `/Volumes/Data/Works/07.hahahoho/app/static/login.html`

- [ ] **Step 1: Add a small login inline-script harness helper**

In `/Volumes/Data/Works/07.hahahoho/tests/test_ops_shell_bootstrap.py`, add a Node harness helper that:
- reads `login.html`
- extracts the inline `<script>`
- stubs a tiny DOM (`document.body.dataset`, `document.documentElement.lang`, `getElementById`, `querySelector`)
- stubs `window.localStorage`
- allows dispatching login page functions/events

Model it after the existing Node harness patterns already used in this file.

- [ ] **Step 2: Write the failing test for login shell utility controls**

Add a new static HTML test asserting the login page contains the required controls and storage key literals.

```python
def test_login_page_exposes_shell_locale_and_theme_controls():
    html = read_static_html("login.html")
    assert 'class="login-shell-utility"' in html
    assert 'id="loginLocaleSelect"' in html
    assert 'id="loginThemeToggle"' in html
    assert '"hahahoho.appLocale.v1"' in html
    assert '"hahahoho.uiTheme.v1"' in html
```

- [ ] **Step 3: Run the new test to verify it fails**

Run:

```bash
pytest -q tests/test_ops_shell_bootstrap.py -k "login_page_exposes_shell_locale_and_theme_controls"
```

Expected:
- FAIL because the current `login.html` has no locale picker, no theme toggle, and no shared storage key literals.

- [ ] **Step 4: Write the failing behavior test for defaulting and locale/theme application**

Use the new Node harness to prove behavior, not just string existence.

```python
def test_login_page_defaults_invalid_saved_locale_and_theme():
    payload = run_login_page_harness(
        local_storage={
            "hahahoho.appLocale.v1": "bogus",
            "hahahoho.uiTheme.v1": "bogus",
        }
    )
    assert payload["lang"] == "ko"
    assert payload["theme"] == "night"
    assert payload["heading"] == "라이브러리 관리/운영 콘솔"
```

- [ ] **Step 5: Run the new behavior test to verify it fails**

Run:

```bash
pytest -q tests/test_ops_shell_bootstrap.py -k "login_page_defaults_invalid_saved_locale_and_theme"
```

Expected:
- FAIL because the current login page does not read or normalize saved locale/theme.

- [ ] **Step 6: Write the failing behavior test for exact auth-error mapping and pass-through**

Add a Node-based behavior test that proves both branches:
- exact `401` invalid-credential detail gets localized
- any other server detail passes through unchanged

```python
def test_login_page_maps_only_exact_auth_failure_literal():
    mapped = run_login_page_harness(
        locale="en",
        submit_response={"ok": False, "status": 401, "detail": "아이디 또는 비밀번호가 올바르지 않습니다."},
    )
    assert mapped["status_text"] == "Incorrect username or password."

    passthrough = run_login_page_harness(
        locale="en",
        submit_response={"ok": False, "status": 401, "detail": "임의 오류"},
    )
    assert passthrough["status_text"] == "임의 오류"
```

- [ ] **Step 7: Run the auth-error behavior test to verify it fails**

Run:

```bash
pytest -q tests/test_ops_shell_bootstrap.py -k "login_page_maps_only_exact_auth_failure_literal"
```

Expected:
- FAIL because the current `login.html` surfaces the raw server detail without locale-aware mapping.

- [ ] **Step 8: Write the failing behavior test for base login form contract**

Add a Node-based submit-flow test that proves:
- `fetch("/auth/login")` is still used
- success redirects to `/ops`
- failed submit re-enables the button

```python
def test_login_page_preserves_submit_flow_contract():
    success = run_login_page_harness(
        submit_response={"ok": True, "status": 200, "body": {"authenticated": True}},
    )
    assert success["fetch_url"] == "/auth/login"
    assert success["redirect_url"] == "/ops"

    failure = run_login_page_harness(
        submit_response={"ok": False, "status": 500, "detail": "임의 오류"},
    )
    assert failure["submit_disabled_after_error"] is False
```

- [ ] **Step 9: Run the submit-flow behavior test to verify it fails**

Run:

```bash
pytest -q tests/test_ops_shell_bootstrap.py -k "login_page_preserves_submit_flow_contract"
```

Expected:
- FAIL because the current login page has no test harness for proving this runtime behavior yet.

- [ ] **Step 10: Write the failing compatibility test for shared persistence keys**

Add a small static test that proves `login.html` and `index.html` use the same literal storage keys.

```python
def test_login_page_reuses_same_locale_and_theme_storage_keys_as_main_shell():
    login_html = read_static_html("login.html")
    index_html = read_static_html("index.html")
    assert '"hahahoho.appLocale.v1"' in login_html
    assert '"hahahoho.uiTheme.v1"' in login_html
    assert '"hahahoho.appLocale.v1"' in index_html
    assert '"hahahoho.uiTheme.v1"' in index_html
```

- [ ] **Step 11: Run the compatibility test to verify it fails**

Run:

```bash
pytest -q tests/test_ops_shell_bootstrap.py -k "login_page_reuses_same_locale_and_theme_storage_keys_as_main_shell"
```

Expected:
- FAIL because the current login page does not reference those key literals at all.

- [ ] **Step 12: Commit the red-state test additions**

```bash
git add /Volumes/Data/Works/07.hahahoho/tests/test_ops_shell_bootstrap.py
git commit -m "test: define login shell theme and locale contract"
```

## Task 2: Implement Minimal Login-Specific Theme And Locale Support

**Files:**
- Modify: `/Volumes/Data/Works/07.hahahoho/app/static/login.html`
- Test: `/Volumes/Data/Works/07.hahahoho/tests/test_ops_shell_bootstrap.py`

- [ ] **Step 1: Add the login shell utility row markup**

Insert a compact utility row above the login card with:
- `loginLocaleSelect`
- `loginThemeToggle`
- icon-only theme structure matching the main shell pattern (`sun + track + moon`)

Do **not** add home/admin/ops navigation buttons.

- [ ] **Step 2: Add minimal day/night token blocks**

Replace the current hard-coded login palette with login-specific CSS tokens that mirror the shell/admin palette shape:

```css
body[data-theme="night"] { ... }
body[data-theme="day"] { ... }
```

Keep the login page self-contained. Do not extract a shared CSS asset in this change.

- [ ] **Step 3: Add login-scoped locale/theme initialization**

Implement minimal client-side state with literal keys:

```js
const LOGIN_LOCALE_STORAGE_KEY = "hahahoho.appLocale.v1";
const LOGIN_THEME_STORAGE_KEY = "hahahoho.uiTheme.v1";
const LOGIN_SUPPORTED_LOCALES = new Set(["ko", "en", "ja"]);
```

Add:
- locale normalize/load/save/apply helpers
- theme normalize/load/save/apply helpers
- `document.body.dataset.theme` application
- `document.documentElement.lang` update
- login utility event wiring
- rerender of login-scoped copy after locale/theme apply

- [ ] **Step 4: Add a login-only message table**

Define only the strings actually used on the login page for `ko`, `en`, `ja`.

Required keys include:
- page title
- heading
- body copy
- username label
- password label
- submit label
- loading status
- invalid-credential error

Do **not** copy the full `I18N_MESSAGES` block from `index.html`.

- [ ] **Step 5: Map the exact auth failure literal**

Preserve the existing `/auth/login` API call, but map only this exact server detail to locale-aware client text:

```text
아이디 또는 비밀번호가 올바르지 않습니다.
```

Any other server detail should still render as-is.

- [ ] **Step 6: Keep the auth flow contract unchanged**

Preserve these exact runtime behaviors:
- `fetch("/auth/login", ...)`
- success still redirects with `window.location.replace("/ops")`
- submit button disabling/re-enabling remains intact

- [ ] **Step 7: Run the focused login tests and verify they pass**

Run:

```bash
pytest -q tests/test_ops_shell_bootstrap.py -k "login_page_redirect_target_is_ops or login_page_exposes_shell_locale_and_theme_controls or login_page_defaults_invalid_saved_locale_and_theme or login_page_maps_only_exact_auth_failure_literal or login_page_preserves_submit_flow_contract or login_page_reuses_same_locale_and_theme_storage_keys_as_main_shell"
```

Expected:
- PASS for all selected login-page static tests.

- [ ] **Step 8: Commit the login implementation**

```bash
git add /Volumes/Data/Works/07.hahahoho/app/static/login.html /Volumes/Data/Works/07.hahahoho/tests/test_ops_shell_bootstrap.py
git commit -m "feat: add login shell theme and locale controls"
```

## Task 3: Verify Route Delivery And Regression Safety

**Files:**
- Verify: `/Volumes/Data/Works/07.hahahoho/app/main.py`
- Verify: `/Volumes/Data/Works/07.hahahoho/app/static/login.html`
- Test: `/Volumes/Data/Works/07.hahahoho/tests/test_ops_route_access.py`
- Test: `/Volumes/Data/Works/07.hahahoho/tests/test_ops_shell_bootstrap.py`

- [ ] **Step 1: Add a route-level smoke test for `/login` delivery**

Add a minimal route test:

```python
def test_login_route_serves_login_page(client):
    res = client.get("/login", headers={"accept": "text/html"})
    assert res.status_code == 200
    assert "라이브러리 로그인" in res.text
    assert 'id="loginThemeToggle"' in res.text
    assert 'id="loginLocaleSelect"' in res.text
```

- [ ] **Step 2: Run the relevant Python regression slice**

Run:

```bash
pytest -q tests/test_ops_route_access.py tests/test_ops_shell_bootstrap.py -k "login"
```

Expected:
- PASS for login-related route/static checks
- No auth-flow regressions

- [ ] **Step 3: Run the final full verification for touched areas**

Run:

```bash
pytest -q tests/test_ops_route_access.py tests/test_ops_shell_bootstrap.py
```

Expected:
- PASS
- Any remaining warnings should only be the known FastAPI `on_event` deprecation warnings

- [ ] **Step 4: Do one browser-level persistence/manual proof**

In QA or local browser:
1. Open `/login`
2. Switch locale away from default
3. Switch theme away from default
4. Reload `/login`
5. Log in
6. Confirm the main console inherits the same locale/theme
7. Confirm both `day` and `night` layouts remain readable
8. Trigger one invalid-credential error and confirm the status text remains readable in both themes

Record the evidence in notes or QA sheet if this work is part of a release batch.

- [ ] **Step 5: Commit the verification-closeout changes**

If Task 3 introduced any additional test edits:

```bash
git add /Volumes/Data/Works/07.hahahoho/tests/test_ops_route_access.py /Volumes/Data/Works/07.hahahoho/tests/test_ops_shell_bootstrap.py
git commit -m "test: cover login route theme and locale delivery"
```

If Task 3 made no file changes, do not create an extra commit.
