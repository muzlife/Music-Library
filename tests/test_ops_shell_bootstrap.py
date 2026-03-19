from pathlib import Path


def test_login_page_redirect_target_is_ops():
    html = Path("/Volumes/Works/07.hahahoho/app/static/login.html").read_text(encoding="utf-8")
    assert 'window.location.replace("/ops")' in html


def test_admin_route_serves_index_for_admin(admin_client):
    res = admin_client.get("/admin")
    assert res.status_code == 200
    assert "라이브러리 관리/운영 콘솔" in res.text


def test_index_defines_route_aware_shell_mode_helpers():
    html = Path("/Volumes/Works/07.hahahoho/app/static/index.html").read_text(encoding="utf-8")
    assert "function currentAppPath()" in html
    assert "function shellModeFromPath()" in html
    assert 'if (path === "/admin") return "admin";' in html
    assert 'if (path === "/ops/cabinets") return "cabinets";' in html
    assert 'return "ops";' in html


def test_index_bootstrap_uses_route_selected_shell_mode_first():
    html = Path("/Volumes/Works/07.hahahoho/app/static/index.html").read_text(encoding="utf-8")
    assert "function applyRouteSelectedShellMode(mode)" in html
    assert 'switchMainTab("simple", { remember: false });' in html
    assert 'switchMainTab("ops", { remember: false });' in html
    assert 'switchSubTab("ops", "cabinet", { remember: false });' in html
    assert 'switchMainTab("home", { remember: false });' in html
    assert "applyRouteSelectedShellMode(shellModeFromPath());" in html
    assert "const preferredMainTab = loadRoleScopedValue(APP_MAIN_TAB_MEMORY_KEY);" not in html
    assert "const preferredSubTab = loadRoleScopedValue(APP_SUBTAB_MEMORY_KEY);" not in html
