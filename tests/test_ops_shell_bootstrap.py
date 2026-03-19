from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "app" / "static"


def read_static_html(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


def test_login_page_redirect_target_is_ops():
    html = read_static_html("login.html")
    assert 'window.location.replace("/ops")' in html


def test_admin_route_serves_index_for_admin(admin_client):
    res = admin_client.get("/admin")
    assert res.status_code == 200
    assert "라이브러리 관리/운영 콘솔" in res.text


def test_index_defines_route_aware_shell_mode_helpers():
    html = read_static_html("index.html")
    assert "function currentAppPath()" in html
    assert "function shellModeFromPath()" in html
    assert 'if (path === "/admin") return "admin";' in html
    assert 'if (path === "/ops/cabinets") return "cabinets";' in html
    assert 'return "ops";' in html


def test_index_bootstrap_uses_route_selected_shell_mode_first():
    html = read_static_html("index.html")
    assert "function applyRouteSelectedShellMode(mode)" in html
    assert 'switchMainTab(nextMode === "cabinets" ? "home" : "simple", { remember: false });' in html
    assert 'openAdminConsole(options.adminTab || "home", {' in html
    assert "pushHistory: options.pushHistory," in html
    assert "replaceHistory: options.replaceHistory," in html
    assert "const initialShellMode = shellModeFromPath();" in html
    assert "applyRouteSelectedShellMode(initialShellMode);" in html
    assert "const preferredMainTab = loadRoleScopedValue(APP_MAIN_TAB_MEMORY_KEY);" not in html
    assert "const preferredSubTab = loadRoleScopedValue(APP_SUBTAB_MEMORY_KEY);" not in html


def test_index_startup_does_not_force_home_before_route_mode():
    html = read_static_html("index.html")
    assert "const initialShellMode = shellModeFromPath();" in html
    assert "appShellMode = initialShellMode;" in html
    assert "applyRouteSelectedShellMode(initialShellMode);" in html
    assert "loadAuthSession(initialShellMode);" in html
    assert 'resetPurchaseImportForm();\n    switchMainTab("home", { remember: false });' not in html
    assert "loadAuthSession();" not in html


def test_index_failure_path_reapplies_route_mode():
    html = read_static_html("index.html")
    assert "async function loadAuthSession(initialShellMode)" in html
    assert html.count("applyRouteSelectedShellMode(initialShellMode);") >= 2


def test_index_pre_auth_route_mode_preserves_direct_admin_and_cabinets_entry():
    html = read_static_html("index.html")
    assert "let appAuthSessionResolved = false;" in html
    assert "if (!appAuthSessionResolved) {" in html
    assert 'if (requested === "admin") return "admin";' in html
    assert 'if (requested === "cabinets") return "cabinets";' in html


def test_index_shell_navigation_uses_history_and_popstate():
    html = read_static_html("index.html")
    assert 'window.history.pushState({}, "", nextPath);' in html
    assert 'window.addEventListener("popstate", () => {' in html
    assert "const routeShellMode = shellModeFromPath();" in html
    assert "applyRouteSelectedShellMode(routeShellMode);" in html


def test_index_auth_failure_fallback_hides_full_ui_until_session_loads():
    html = read_static_html("index.html")
    assert "const authenticated = Boolean(appAuthSession?.authenticated);" in html
    assert 'setDisplayIfPresent("shellTabs", authenticated ? "flex" : "none");' in html
    assert 'setDisplayIfPresent("shellAdminBtn", authenticated && isAdmin ? "inline-flex" : "none");' in html
    assert 'setDisplayIfPresent("adminTabs", authenticated && isAdmin && mode === "admin" ? "flex" : "none");' in html
    assert "appAuthSessionResolved = true;" in html


def test_index_defines_ops_cabinet_route_helper_and_query_contract():
    html = read_static_html("index.html")
    assert "function openOpsCabinetView(cabinetName, columnCode, cellCode, options = {})" in html
    assert "function cabinetRouteSelectionFromLocation()" in html
    assert 'params.get("cabinet_name")' in html
    assert 'params.get("column_code")' in html
    assert 'params.get("cell_code")' in html
    assert 'return `/ops/cabinets?${params.toString()}`;' in html
    assert 'switchShellMode("cabinets",' in html


def test_index_operator_results_expose_cabinet_open_action_in_readonly_shell():
    html = read_static_html("index.html")
    assert 'data-operator-open-cabinet="${ownedItemId}"' in html
    assert 'await openOpsCabinetView(cabinetName, columnCode, cellCode);' in html
    handler_start = "async function handleOperatorLookupAction(e) {"
    handler_end = '    $("operatorRequestList").addEventListener("click", async (e) => {'
    assert handler_start in html
    assert handler_end in html
    block = html.split(handler_start, 1)[1].split(handler_end, 1)[0]
    cabinet_action = 'const cabinetBtn = e.target.closest("[data-operator-open-cabinet]");'
    readonly_guard = 'if (isShellReadOnly()) return;'
    assert cabinet_action in block
    assert readonly_guard in block
    assert block.index(cabinet_action) < block.index(readonly_guard)


def test_index_workbench_location_action_runs_before_readonly_guard():
    html = read_static_html("index.html")
    event_start = '$("homeDashWorkbenchList").addEventListener("click", (e) => {'
    event_end = '    $("homeDashWorkbenchRecommendBtn").addEventListener("click", loadDashboardWorkbenchRecommendations);'
    assert event_start in html
    assert event_end in html
    block = html.split(event_start, 1)[1].split(event_end, 1)[0]
    locate_action = 'const locateBtn = e.target.closest("[data-dashboard-workbench-open-slot]");'
    readonly_guard = 'if (isShellReadOnly()) return;'
    assert locate_action in block
    assert 'openCabinetLocationAction(slotId, slotCode, "", "", "");' in block
    assert readonly_guard in block
    assert block.index(locate_action) < block.index(readonly_guard)


def test_index_cabinets_route_without_selection_clears_stale_dashboard_focus():
    html = read_static_html("index.html")
    assert 'if (nextMode === "cabinets" && !pendingOpsCabinetSelection) {' in html
    assert "homeDashboardSelectedCabinetKey = null;" in html
    assert "homeDashboardSelectedSlotCode = null;" in html
    assert "homeDashboardSlotItems = [];" in html
    assert "homeDashboardSlotItemsSlotCode = null;" in html


def test_index_invalid_cabinet_route_selection_resets_previous_slot_state():
    html = read_static_html("index.html")
    apply_pending_start = "async function applyPendingOpsCabinetSelection(opts = {}) {"
    open_ops_start = "    async function openOpsCabinetView(cabinetName, columnCode, cellCode, options = {}) {"
    assert apply_pending_start in html
    assert open_ops_start in html
    block = html.split(apply_pending_start, 1)[1].split(open_ops_start, 1)[0]
    assert "if (!slotRow) {" in block
    assert "homeDashboardSelectedCabinetKey = null;" in block
    assert "homeDashboardSelectedSlotCode = null;" in block
    assert "homeDashboardSlotItems = [];" in block
    assert "homeDashboardSlotItemsSlotCode = null;" in block


def test_index_readonly_shell_reset_rerenders_dashboard_detail_panel():
    html = read_static_html("index.html")
    reset_start = "function resetReadOnlyShellState() {"
    focus_start = "    function focusOpsHomeSearchInput() {"
    assert reset_start in html
    assert focus_start in html
    block = html.split(reset_start, 1)[1].split(focus_start, 1)[0]
    assert 'renderDashboardSlotItems(getDashboardSlotRow(homeDashboardSelectedSlotCode));' in block
    assert "renderDashboardCabinetDetail();" in block
    assert "renderDashboardWorkbench();" in block
