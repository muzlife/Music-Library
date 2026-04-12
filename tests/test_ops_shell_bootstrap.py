import re
import subprocess
import tempfile
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "app" / "static"


def read_static_html(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


def extract_inline_scripts(html: str) -> list[str]:
    return re.findall(r"<script>(.*?)</script>", html, re.S)


def call_js_comparator_card_fragment(payload: dict | None = None) -> dict:
    html = read_static_html("index.html")
    script = html.split("function sourceWorkbenchEditionComparatorFieldDefs() {", 1)[1].split("function buildSourceWorkbenchSearchRequest(entry, opts = {}) {", 1)[0]
    payload = payload or {}
    payload_json = json.dumps(payload, ensure_ascii=False)
    harness = '''
function sourceWorkbenchEditionComparatorFieldDefs() {
__SCRIPT__

function escapeHtml(input) {
  return String(input == null ? "" : input)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/\x27/g, "&#39;");
}

const payload = __PAYLOAD__;
const current = payload.current || {};
const candidate = payload.candidate || {};
const rows = buildSourceWorkbenchEditionComparatorRows({ current, candidate });
const summary = buildSourceWorkbenchEditionComparatorSummary({ current, candidate });
const explanations = buildSourceWorkbenchEditionComparatorExplanationPhrases({ current, candidate });
const comparatorCard = sourceWorkbenchEditionComparatorCardHtml({ summary, rows, explanations });
const roles = rows.reduce((acc, row) => {
  if (!row?.key) return acc;
  acc.push({ key: row.key, cardRole: row.cardRole || "", group: row.group || "", label: row.label || "" });
  return acc;
}, []);
process.stdout.write(JSON.stringify({ summary, comparatorCard, roles }));
'''
    harness = harness.replace("__SCRIPT__", script).replace("__PAYLOAD__", payload_json)
    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as handle:
        handle.write(harness)
        path = Path(handle.name)
    try:
        result = subprocess.run(["node", str(path)], capture_output=True, text=True, check=False, cwd=str(REPO_ROOT))
    finally:
        path.unlink(missing_ok=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout, "empty node output"
    return json.loads(result.stdout)


def extract_js_function(script: str, function_name: str) -> str:
    marker = f"    function {function_name}("
    start = script.index(marker)
    tail = script[start + 4 :]
    match = re.search(r"\n    function [A-Za-z0-9_]+\s*\(", tail)
    if not match:
        return script[start:]
    return script[start : start + 4 + match.start()]


def render_media_search_result_card_html(row: dict) -> str:
    html = read_static_html("index.html")
    script = next((s for s in extract_inline_scripts(html) if "function homeResultItemHtml(row) {" in s), "")
    assert script, "homeResultItemHtml function block not found"
    blocks = [
        extract_js_function(script, "homeMasterMemberPreviewHtml"),
        extract_js_function(script, "getHomeMasterVisiblePreviewItems"),
        extract_js_function(script, "homeMasterMemberPreviewToggleHtml"),
        extract_js_function(script, "homeResultItemHtml"),
    ]
    harness = f"""
const t = (key, params) => key + (params ? JSON.stringify(params) : "");
const escapeHtml = (input) => String(input == null ? "" : input);
const normalizeSourceCode = (value) => String(value || "").trim().toUpperCase();
const resolveAlbumMasterName = (row) => String(row?.title || "");
const homeMasterHeadingLabel = (row) => String(row?.heading || "");
const buildOperatorDisplayTitleParts = (item) => ({{
  title: String(item?.title || item?.name || item?.item_name || ""),
  artist: String(item?.artist || ""),
}});
const formatOperatorCardDateTime = () => "";
const operatorRunoutSampleText = () => "-";
const homeMasterMemberPreviewMetaLine = () => "";
const homeMasterMemberPreviewLocationHtml = () => "";
const getMediaSearchContextSelectedOwnedItemId = () => 0;
const getMediaSearchExpandedPreviewOwnedItemId = () => "";
const mediaSearchMemberPreviewCoverSrc = () => "";
const discogsRepairSlotHtml = () => "";
const homeOwnedItemRelationTypeLabel = () => "";
const homeOwnedItemRelationTargetLabel = () => "";
const formatCount = (value) => String(value);
const homeMasterLocationButtonsHtml = () => "";
const homeExpandedMasterPreviewIds = new Set();
const homeSelectedMasterId = 0;

{chr(10).join(blocks)}

const row = {json.dumps(row, ensure_ascii=False)};
process.stdout.write(homeResultItemHtml(row) || "");
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as handle:
        handle.write(harness)
        path = Path(handle.name)
    try:
        result = subprocess.run(["node", str(path)], capture_output=True, text=True, check=False, cwd=str(REPO_ROOT))
    finally:
        path.unlink(missing_ok=True)
    assert result.returncode == 0, result.stderr
    return result.stdout


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


def test_index_admin_bootstrap_loads_only_after_session_resolution():
    html = read_static_html("index.html")
    assert "function loadAdminBootstrapData()" in html
    helper_start = "    function loadAdminBootstrapData() {"
    session_start = "    async function loadAuthSession(initialShellMode) {"
    assert helper_start in html
    assert session_start in html
    helper_block = html.split(helper_start, 1)[1].split(session_start, 1)[0]
    assert 'if (!isAdminSession()) return;' in helper_block
    assert 'loadOpsCameras({ silent: true });' in helper_block
    assert "loadReviewQueue();" in helper_block
    assert "loadAlbumMasterGroups();" in helper_block
    assert "loadMetadataSyncStatus();" in helper_block
    assert "loadOpsSystemStatus();" in helper_block
    session_block = html.split(session_start, 1)[1].split("    async function logoutAppSession()", 1)[0]
    assert "loadAdminBootstrapData();" in session_block


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
    assert 'setDisplayIfPresent("appHero", authenticated && isAdmin && mode === "admin" ? "block" : "none");' in html
    assert 'setDisplayIfPresent("opsHomeHero", authenticated && mode !== "admin" ? "grid" : "none");' in html
    assert 'setDisplayIfPresent("shellAdminBtn", authenticated && isAdmin && mode !== "admin" ? "inline-flex" : "none");' in html
    assert 'setDisplayIfPresent("adminTabs", authenticated && isAdmin && mode === "admin" ? "flex" : "none");' in html
    assert "appAuthSessionResolved = true;" in html


def test_index_uses_shell_utility_mounts_for_ops_and_admin_headers():
    html = read_static_html("index.html")
    assert '<header id="appHero" class="hero admin-shell-hero">' in html
    assert 'id="adminUtilityMount"' in html
    assert 'id="adminUtilityMainMount"' in html
    assert 'id="opsUtilityMount"' in html
    assert 'id="opsUtilityMainMount"' in html
    assert 'id="shellUtilityBar"' in html
    assert 'id="appSessionInfo"' in html
    assert 'id="appLogoutBtn"' in html
    assert 'id="shellAdminBtn"' in html


def test_index_defines_ops_home_header_markup_and_copy():
    html = read_static_html("index.html")
    assert 'id="opsHomeHero"' in html
    assert "라이브러리 운영 홈" in html
    assert "현장 조회, 위치 확인, 최근 흐름을 한 화면에서 정리합니다." in html


def test_ops_home_hybrid_layout_has_context_panel_shell():
    html = read_static_html("index.html")
    assert 'id="opsHomeLayout"' in html
    assert 'id="opsLibraryContextPanel"' in html
    assert 'id="opsLibraryContextClimate"' in html
    assert 'id="opsLibraryContextBody"' in html


def test_ops_home_context_panel_contains_default_and_focus_copy_hooks():
    html = read_static_html("index.html")
    assert 'id="opsLibraryContextPanel"' in html
    panel_block = html.split('id="opsLibraryContextPanel"', 1)[1]
    panel_block = panel_block.split("</aside>", 1)[0]
    assert 'id="opsLibraryContextClimate"' in panel_block
    assert 'id="opsLibraryContextBody"' in panel_block
    assert "라이브러리 컨텍스트" in panel_block
    assert "검색 결과를 선택하면 현재 위치와 직전 위치를 여기서 바로 확인합니다." in panel_block
    assert 'setTextIfPresent("operatorWeatherKicker", t("operator.weather.office.kicker"))' in html


def test_ops_home_context_panel_supports_selected_item_location_state():
    html = read_static_html("index.html")
    assert "renderOpsLibraryContextSelection" in html
    assert 'id="opsLibraryContextCurrentLocation"' in html
    assert 'id="opsLibraryContextPreviousLocation"' in html


def test_ops_home_context_panel_reuses_open_cabinet_action():
    html = read_static_html("index.html")
    assert 'data-operator-context-open-cabinet' in html
    assert 'e.target.closest("[data-operator-context-open-cabinet]")' in html
    assert "openOperatorCabinetLocationFromButton" in html


def test_ops_home_context_panel_updates_only_on_click_selection():
    html = read_static_html("index.html")
    assert "let homePreviewContextItem = null;" in html
    assert "const activeItem = homeSelectedContextItem || homePreviewContextItem || null;" in html
    assert 'setOpsLibraryContextSelectionFromTarget(e.target, { pin: true });' in html
    assert '$("operatorLookupResults").addEventListener("mouseover"' not in html
    assert '$("operatorLookupResults").addEventListener("focusin"' not in html
    assert '$("operatorLookupResults").addEventListener("mouseleave"' not in html
    assert '$("operatorLookupResults").addEventListener("focusout"' not in html


def test_ops_home_feed_reload_preserves_pinned_context_selection():
    html = read_static_html("index.html")
    block = html.split("async function loadOperatorHomeFeed(options = {}) {", 1)[1].split("function operatorSummaryReasonLabel(reason) {", 1)[0]
    pre_auth_block = block.split('if (!appAuthSession?.authenticated) {', 1)[0]
    assert "homePreviewContextItem = null;" in block
    assert "homeSelectedContextItem = null;" not in pre_auth_block
    assert "const pinnedOwnedItemId = Number(homeSelectedContextItem?.owned_item_id || homeSelectedContextItem?.id || 0);" in block
    assert "operatorFeedItems.find((row) => Number(row?.owned_item_id || row?.id || 0) === pinnedOwnedItemId)" in block


def test_operator_location_builder_prefers_localized_triplet_labels():
    html = read_static_html("index.html")
    block = html.split("function buildOperatorLocationLabel(row) {", 1)[1].split("function exactTitleArtistMatch(row, normalizedQuery) {", 1)[0]
    assert "buildOperatorSlotDisplayLabel(" in block
    assert "currentCabinetName," in block
    assert "currentColumnCode," in block
    assert "currentCellCode" in block


def test_operator_feed_and_lookup_render_current_location_with_helper():
    html = read_static_html("index.html")
    recent_block = html.split("function renderOperatorHomeRecentItems(items, options = {}) {", 1)[1].split("function renderOperatorFeedItems(items, options = {}) {", 1)[0]
    feed_block = html.split("function renderOperatorFeedItems(items, options = {}) {", 1)[1].split("function renderOperatorHomeRecentSections() {", 1)[0]
    lookup_block = html.split("function renderOperatorLookupResults() {", 1)[1].split("async function openOperatorCabinetLocationFromButton(button) {", 1)[0]
    assert 'const currentLocation = buildOperatorLocationLabel(row);' in recent_block
    assert 'const currentLocation = buildOperatorLocationLabel(row);' in feed_block
    assert 'const currentLocation = buildOperatorLocationLabel(row);' in lookup_block


def test_dashboard_and_operator_history_routes_localize_slot_display_names():
    html = read_static_html("index.html")
    request_block = html.split("el.innerHTML = operatorRequestItems.map((row) => {", 1)[1].split("function renderOperatorRequestList() {", 1)[0]
    dashboard_summary_block = html.split("function renderDashboardSelectedItemMeta() {", 1)[1].split("function setDashboardWorkbenchMode(mode) {", 1)[0]
    recent_move_block = html.split("function dashboardRecentMoveText(row) {", 1)[1].split("function dashboardRecentMoveInlineHtml(row, extraClass = \"\") {", 1)[0]
    route_block = html.split("function renderDashboardRecentMoves(rows, windowDays, totalMoves) {", 1)[1].split("function renderDashboardSourceRows(rows, totalItems) {", 1)[0]
    assert 'buildOperatorSlotDisplayLabel(row.current_slot_display_snapshot, row.current_slot_code_snapshot, "", "", "")' in request_block
    assert 'localizeOperatorSlotDisplayName(row?.previous_slot_display_name)' in dashboard_summary_block
    assert 'localizeOperatorSlotDisplayName(row?.previous_slot_display_name)' in recent_move_block
    assert 'from: buildOperatorSlotDisplayLabel(row.from_display_name, row.from_slot_code, "", "", "")' in route_block
    assert 'to: buildOperatorSlotDisplayLabel(row.to_display_name, row.to_slot_code, "", "", "")' in route_block


def test_storage_slot_display_label_prefers_localized_triplet_or_display_name():
    html = read_static_html("index.html")
    block = html.split("function storageSlotDisplayLabel(slot) {", 1)[1].split("function cabinetSortPolicyLabel(value) {", 1)[0]
    assert "const localizedTriplet = buildOperatorCabinetTripletLabel(slot.cabinet_name, slot.column_code, slot.cell_code);" in block
    assert "const displayName = localizeOperatorSlotDisplayName(slot.display_name);" in block


def test_ops_home_context_panel_supports_mini_cabinet_map_for_selected_item():
    html = read_static_html("index.html")
    assert "function findOpsLibraryContextCabinetGroup(item) {" in html
    assert "function renderOpsLibraryContextMiniCabinetMap(item, options = {}) {" in html
    assert 'const mapId = String(options.mapId || "opsLibraryContextMiniCabinetMap");' in html
    assert ".ops-library-mini-map {" in html
    assert ".ops-library-mini-map-cell.active {" in html
    assert "const miniMapHtml = renderOpsLibraryContextMiniCabinetMap(item);" in html


def test_ops_home_context_mini_cabinet_map_uses_i18n_helpers_for_head_meta():
    html = read_static_html("index.html")
    mini_map_block = html.split("function renderOpsLibraryContextMiniCabinetMap(item, options = {}) {", 1)[1].split("function getOpsLibraryContextSlotPreviewRows(slotCode) {", 1)[0]
    assert "dashboardConnectedCabinetsLabel(group.cabinetCount)" not in mini_map_block
    assert "dashboardFloorsLabel(cabinet.floorCount)" in mini_map_block
    assert "dashboardCellCountLabel(cabinet.slotCount)" in mini_map_block
    assert 'appLocale === "en" ? " cols"' not in mini_map_block
    assert 'appLocale === "en" ? " cells"' not in mini_map_block


def test_ops_home_context_panel_omits_placement_hint_card_from_right_panel():
    html = read_static_html("index.html")
    assert "const opsPlacementHintCache = new Map();" in html
    assert "let opsPlacementHintLoadingOwnedItemId = 0;" in html
    assert "let opsPlacementHintRequestSeq = 0;" in html
    assert "function renderOpsPlacementHintCard(item, options = {}) {" in html
    assert "function renderOpsPlacementHintIdle(item = null, options = {}) {" in html
    assert "function renderOpsPlacementHintLoading(item, options = {}) {" in html
    assert "function renderOpsPlacementHintReady(item, payload = {}, options = {}) {" in html
    assert "function renderOpsPlacementHintUnavailable(item, message = \"\", options = {}) {" in html
    assert "async function loadOpsPlacementHints(item, options = {}) {" in html
    default_block = html.split("function renderOpsLibraryContextDefault(climate) {", 1)[1].split("function renderOpsLibraryContextSelection(item) {", 1)[0]
    selection_block = html.split("function renderOpsLibraryContextSelection(item) {", 1)[1].split("function findOpsLibraryContextCabinetGroup(item) {", 1)[0]
    assert "renderOpsArtistContextIdle()" in default_block
    assert "renderOpsPlacementHintCard(null)" not in default_block
    assert "renderOpsArtistContextCard(item)" in selection_block
    assert "renderOpsPlacementHintCard(item)" not in selection_block
    assert "loadOpsPlacementHints(item)" not in selection_block


def test_ops_home_context_panel_groups_plugins_above_mini_map_and_preview():
    html = read_static_html("index.html")
    selection_block = html.split("function renderOpsLibraryContextSelection(item) {", 1)[1].split("function findOpsLibraryContextCabinetGroup(item) {", 1)[0]
    assert "const pluginSectionHtml = renderOpsPluginSection(`" in selection_block
    assert 't("operator.plugin.title")' in html
    plugin_index = selection_block.index("${pluginSectionHtml}")
    mini_map_index = selection_block.index("${miniMapHtml}")
    slot_preview_index = selection_block.index("${slotPreviewHtml}")
    assert plugin_index < mini_map_index < slot_preview_index
    plugin_block = selection_block.split("const pluginSectionHtml = renderOpsPluginSection(`", 1)[1].split("`);", 1)[0]
    assert "${renderOpsArtistContextCard(item)}" in plugin_block
    assert "${renderOpsCollectorInfoCard(item)}" not in plugin_block


def test_ops_home_context_panel_includes_artist_context_shell_and_loader():
    html = read_static_html("index.html")
    assert 'const cardId = String(options.cardId || "opsArtistContextCard");' in html
    assert "const opsArtistContextCache = new Map();" in html
    assert "let opsArtistContextLoadingKey = \"\";" in html
    assert "let opsArtistContextRequestSeq = 0;" in html
    assert "function renderOpsArtistContextCard(item, options = {}) {" in html
    assert "function renderOpsArtistContextIdle(options = {}) {" in html
    assert "function renderOpsArtistContextLoading(item, options = {}) {" in html
    assert "function renderOpsArtistContextReady(payload, options = {}) {" in html
    assert "function renderOpsArtistContextUnavailable(item, payload = null, options = {}) {" in html
    assert "async function loadOpsArtistContext(item, options = {}) {" in html
    default_block = html.split("function renderOpsLibraryContextDefault(climate) {", 1)[1].split("function getOpsPlacementHintOwnedItemId(item) {", 1)[0]
    selection_block = html.split("function renderOpsLibraryContextSelection(item) {", 1)[1].split("function findOpsLibraryContextCabinetGroup(item) {", 1)[0]
    assert "${renderOpsPluginSection(`" in default_block
    assert "${renderOpsArtistContextIdle()}" in default_block
    assert "${renderOpsArtistContextCard(item)}" in selection_block
    assert "loadOpsArtistContext(item).catch(() => {});" in selection_block


def test_ops_home_artist_context_caches_only_available_payloads():
    html = read_static_html("index.html")
    load_block = html.split("async function loadOpsArtistContext(item, options = {}) {", 1)[1].split("    function getMediaSearchContextSelectedOwnedItemId()", 1)[0]
    assert "if (payload.available) opsArtistContextCache.set(cacheKey, payload);" in load_block


def test_ops_home_artist_context_runtime_copy_uses_i18n_keys():
    html = read_static_html("index.html")
    assert '"operator.artist_context.title": "아티스트 컨텍스트"' in html
    assert '"operator.artist_context.idle": "항목을 선택하면 아티스트 배경을 여기에 표시합니다."' in html
    assert '"operator.artist_context.loading": "아티스트 정보를 불러오는 중입니다."' in html
    assert '"operator.artist_context.unavailable": "아티스트 컨텍스트를 아직 확인할 수 없습니다."' in html
    assert '"operator.artist_context.links": "외부 링크"' in html
    assert '"operator.artist_context.action.show_original": "원문 보기"' in html
    assert '"operator.artist_context.action.hide_original": "원문 숨기기"' in html
    assert '"operator.artist_context.field.country": "국가"' in html
    assert '"operator.artist_context.field.active_years": "활동"' in html
    assert '"operator.artist_context.field.genres": "장르"' in html
    assert '"operator.artist_context.title": "Artist Context"' in html
    assert '"operator.artist_context.unavailable": "Artist context is unavailable right now."' in html
    assert '"operator.artist_context.action.show_original": "Show Original"' in html
    assert '"operator.artist_context.action.hide_original": "Hide Original"' in html
    assert '"operator.artist_context.title": "アーティストコンテキスト"' in html
    assert '"operator.artist_context.action.show_original": "原文を見る"' in html
    assert '"operator.artist_context.action.hide_original": "原文を隠す"' in html


def test_ops_home_artist_context_ready_markup_supports_original_summary_toggle():
    html = read_static_html("index.html")
    idle_block = html.split("function renderOpsArtistContextIdle(options = {}) {", 1)[1].split("function renderOpsArtistContextLoading", 1)[0]
    loading_block = html.split("function renderOpsArtistContextLoading(item, options = {}) {", 1)[1].split("function renderOpsArtistContextLinks", 1)[0]
    ready_block = html.split("function renderOpsArtistContextReady(payload, options = {}) {", 1)[1].split("function renderOpsArtistContextUnavailable", 1)[0]
    assert "payload.image_url" not in idle_block
    assert "payload.image_url" not in loading_block
    assert "payload.image_url" in ready_block
    assert 'ops-artist-context-card${payload.image_url ? " has-image" : ""}' in ready_block
    assert "ops-artist-context-media" in ready_block
    assert "ops-artist-context-image" in ready_block
    assert "payload.summary_original" in ready_block
    assert "data-ops-artist-context-toggle" in ready_block
    assert "operator.artist_context.action.show_original" in ready_block
    assert "operator.artist_context.action.hide_original" in ready_block
    assert "ops-artist-context-original" in ready_block


def test_ops_home_artist_context_image_uses_square_top_aligned_crop():
    html = read_static_html("index.html")
    card_block = html.split(".ops-artist-context-card.has-image {", 1)[1].split(".ops-artist-context-head {", 1)[0]
    media_block = html.split(".ops-artist-context-media {", 1)[1].split(".ops-artist-context-image {", 1)[0]
    image_block = html.split(".ops-artist-context-image {", 1)[1].split(".ops-artist-context-summary {", 1)[0]
    assert "grid-template-columns: 104px minmax(0, 1fr);" in card_block
    assert "grid-template-areas:" in card_block
    assert '"head head"' in card_block
    assert '"media name"' in card_block
    assert "width: 104px;" in media_block
    assert "justify-self: start;" in media_block
    assert "align-self: start;" in media_block
    assert "aspect-ratio: 1 / 1;" in image_block
    assert "object-position: center top;" in image_block


def test_ops_home_artist_context_without_image_uses_linear_flow():
    html = read_static_html("index.html")
    head_block = html.split(".ops-artist-context-head {", 1)[1].split("}", 1)[0]
    name_block = html.split(".ops-artist-context-name {", 1)[1].split("}", 1)[0]
    summary_wrap_block = html.split(".ops-artist-context-summary-wrap {", 1)[1].split("}", 1)[0]
    meta_block = html.split(".ops-artist-context-meta {", 1)[1].split("}", 1)[0]
    links_block = html.split(".ops-artist-context-links {", 1)[1].split("}", 1)[0]
    assert "grid-area:" not in head_block
    assert "grid-area:" not in name_block
    assert "grid-area:" not in summary_wrap_block
    assert "grid-area:" not in meta_block
    assert "grid-area:" not in links_block
    assert ".ops-artist-context-card.has-image .ops-artist-context-head {" in html
    assert ".ops-artist-context-card.has-image .ops-artist-context-name {" in html
    assert ".ops-artist-context-card.has-image .ops-artist-context-media {" in html
    assert ".ops-artist-context-card.has-image .ops-artist-context-summary-wrap {" in html
    assert ".ops-artist-context-card.has-image .ops-artist-context-meta {" in html
    assert ".ops-artist-context-card.has-image .ops-artist-context-links {" in html


def test_ops_home_context_panel_excludes_collector_card_shell_and_loader():
    html = read_static_html("index.html")
    assert "const opsCollectorInfoCache = new Map();" not in html
    assert "let opsCollectorInfoLoadingOwnedItemId = 0;" not in html
    assert "let opsCollectorInfoRequestSeq = 0;" not in html
    assert "function renderOpsCollectorInfoCard(item, options = {}) {" not in html
    assert "async function loadOpsCollectorInfo(item) {" not in html
    default_block = html.split("function renderOpsLibraryContextDefault(climate) {", 1)[1].split("function renderOpsLibraryContextSelection(item) {", 1)[0]
    selection_block = html.split("function renderOpsLibraryContextSelection(item) {", 1)[1].split("function findOpsLibraryContextCabinetGroup(item) {", 1)[0]
    assert "renderOpsCollectorInfoCard(null)" not in default_block
    assert "renderOpsCollectorInfoCard(item)" not in selection_block
    assert 'id="opsLibraryCollectorInfoCard"' not in html
    assert "loadOpsCollectorInfo(item).catch(() => {});" not in selection_block


def test_ops_home_context_panel_removes_collector_card_markup():
    html = read_static_html("index.html")
    selection_block = html.split("function renderOpsLibraryContextSelection(item) {", 1)[1].split("function findOpsLibraryContextCabinetGroup(item) {", 1)[0]
    assert 'id="opsLibraryCollectorInfoCard"' not in html
    assert '${renderOpsCollectorInfoCard(item)}' not in selection_block


def test_ops_home_context_panel_removes_collector_info_loader_and_route():
    html = read_static_html("index.html")
    assert "const ownedItemId = getOpsCollectorInfoOwnedItemId(item);" not in html
    assert "async function loadOpsCollectorInfo(item) {" not in html
    assert 'fetch(`/ops/owned-items/${encodeURIComponent(ownedItemId)}/collector-info`)' not in html


def test_ops_home_context_panel_removes_collector_card_detail_fields():
    html = read_static_html("index.html")
    assert 't("operator.collector.field.country")' not in html
    assert 't("operator.collector.field.label")' not in html
    assert 't("operator.collector.field.catalog_no")' not in html
    assert 't("operator.collector.field.barcode")' not in html
    assert 't("operator.collector.field.format")' not in html
    assert 't("operator.collector.field.runout_sample")' not in html


def test_ops_home_context_panel_removes_collector_transport_cache_logic():
    html = read_static_html("index.html")
    assert "opsCollectorInfoCache.set(ownedItemId, payload);" not in html
    assert 'operator.collector.state.unavailable' not in html


def test_ops_home_context_panel_adds_placement_hint_i18n_copy():
    html = read_static_html("index.html")
    for key in [
        "operator.placement.title",
        "operator.placement.title.unslotted",
        "operator.placement.title.assigned",
        "operator.placement.state.idle",
        "operator.placement.state.idle.unslotted",
        "operator.placement.state.idle.assigned",
        "operator.placement.state.loading",
        "operator.placement.state.loading.unslotted",
        "operator.placement.state.loading.assigned",
        "operator.placement.state.unavailable",
        "operator.placement.state.unavailable.unslotted",
        "operator.placement.state.unavailable.assigned",
        "operator.placement.state.fallback",
        "operator.placement.state.fallback.unslotted",
        "operator.placement.state.fallback.assigned",
        "operator.placement.reason.artist",
        "operator.placement.reason.domain",
        "operator.placement.reason.nearby",
        "operator.placement.reason.label",
        "operator.placement.reason.fallback",
    ]:
        assert f'"{key}":' in html


def test_media_search_context_subtitle_removes_slot_recommendation_copy():
    html = read_static_html("index.html")
    assert '"media.search.context.subtitle": "상품 preview를 선택하면 현재 위치와 아티스트 컨텍스트를 여기서 확인하고 관리 화면으로 이어갈 수 있습니다."' in html
    assert '"media.search.context.subtitle": "Select a member-item preview to inspect its current location, artist context, and jump into manage."' in html
    assert '"media.search.context.subtitle": "商品 preview を選ぶと、現在位置とアーティストコンテキストを確認し、そのまま管理へ進めます。"' in html


def test_media_search_right_panel_selected_item_inspector_copy():
    html = read_static_html("index.html")
    default_block = html.split("    function renderMediaSearchContextDefault() {", 1)[1].split("    function setMediaSearchContextSelectionByOwnedItem(ownedItemId) {", 1)[0]
    selection_block = html.split("    function renderMediaSearchContextSelection(item) {", 1)[1].split("    function findOpsLibraryContextCabinet(item) {", 1)[0]
    assert '"media.search.context.title": "선택한 상품"' in html
    assert '"media.search.context.title": "Selected item"' in html
    assert '"media.search.context.title": "選択した商品"' in html
    assert '"media.search.context.subtitle": "상품 preview를 선택하면 현재 위치와 아티스트 컨텍스트를 여기서 확인하고 관리 화면으로 이어갈 수 있습니다."' in html
    assert '"media.search.context.subtitle": "Select a member-item preview to inspect its current location, artist context, and jump into manage."' in html
    assert '"media.search.context.subtitle": "商品 preview を選ぶと、現在位置とアーティストコンテキストを確認し、そのまま管理へ進めます。"' in html
    assert 't("media.search.context.selection_label")' in selection_block
    assert '<h3>${escapeHtml(t("media.search.context.title"))}</h3>' in default_block


def test_ops_home_context_panel_emphasizes_current_slot_with_contrast_badge():
    html = read_static_html("index.html")
    active_block = html.split(".ops-library-mini-map-cell.active {", 1)[1].split("}", 1)[0]
    badge_block = html.split(".ops-library-mini-map-active-badge {", 1)[1].split("}", 1)[0]
    mini_map_block = html.split("function renderOpsLibraryContextMiniCabinetMap(item, options = {}) {", 1)[1].split("function getOpsLibraryContextSlotPreviewRows(slotCode) {", 1)[0]
    assert "background: linear-gradient(180deg, var(--selected-accent-deep), var(--selected-accent-strong));" in active_block
    assert "color: #f8fafc;" in active_block
    assert "box-shadow:" in active_block
    assert "font-size: 0.53rem;" in badge_block
    assert 't("operator.context.map.active_badge")' in mini_map_block


def test_storage_mapping_high_occupancy_percent_uses_contrast_pill_tokens():
    html = read_static_html("index.html")
    tone_block = html.split("function dashboardCabinetMapCellTone(slotRow) {", 1)[1].split("function dashboardCabinetMapSizeClass(slotRow) {", 1)[0]
    mini_map_block = html.split("function renderOpsLibraryContextMiniCabinetMap(item, options = {}) {", 1)[1].split("function getOpsLibraryContextSlotPreviewRows(slotCode) {", 1)[0]
    mini_count_block = html.split(".ops-library-mini-map-cellcount {", 1)[1].split("}", 1)[0]
    dash_count_block = html.split(".dashboard-cabinet-map-cellcount {", 1)[1].split("}", 1)[0]
    assert 'ratio >= 0.7' in tone_block
    assert "const countBg =" in tone_block
    assert '"rgba(15, 23, 42, 0.82)"' in tone_block
    assert "const countBorder =" in tone_block
    assert '"rgba(15, 23, 42, 0.9)"' in tone_block
    assert "const countFg =" in tone_block
    assert '"#f8fafc"' in tone_block
    assert '--tile-count-bg:${tone.countBg};--tile-count-border:${tone.countBorder};--tile-count-fg:${tone.countFg};' in mini_map_block
    assert "background: var(--tile-count-bg, transparent);" in mini_count_block
    assert "border: 1px solid var(--tile-count-border, transparent);" in mini_count_block
    assert "color: var(--tile-count-fg, currentColor);" in mini_count_block
    assert "background: var(--tile-count-bg, transparent);" in dash_count_block
    assert "color: var(--tile-count-fg, currentColor);" in dash_count_block


def test_ops_home_context_panel_compacts_right_panel_density():
    html = read_static_html("index.html")
    weather_block = html.split(".operator-weather-card {", 1)[1].split("}", 1)[0]
    assert "gap: 2px;" in weather_block
    assert "padding: 8px 8px 10px;" in weather_block
    mini_map_block = html.split(".ops-library-mini-map {", 1)[1].split("}", 1)[0]
    assert "gap: 6px;" in mini_map_block
    assert "padding: 8px;" in mini_map_block
    assert "#opsLibraryContextBody {" in html


def test_ops_home_context_panel_supports_mini_slot_preview_for_selected_item():
    html = read_static_html("index.html")
    assert "function renderOpsLibraryContextSlotPreview(item, options = {}) {" in html
    assert "function loadOpsLibraryContextSlotPreview(item, options = {}) {" in html
    assert 'const rootId = String(options.rootId || "opsLibraryContextSlotPreview");' in html


def test_ops_home_context_panel_compacts_mini_slot_preview_density():
    html = read_static_html("index.html")
    preview_block = html.split(".ops-library-slot-preview {", 1)[1].split("}", 1)[0]
    grid_block = html.split(".ops-library-slot-preview-grid {", 1)[1].split("}", 1)[0]
    label_block = html.split(".ops-library-slot-preview-label {", 1)[1].split("}", 1)[0]
    assert "gap: 4px;" in preview_block
    assert "padding: 5px;" in preview_block
    assert "grid-template-columns: repeat(6, minmax(0, 1fr));" in grid_block
    assert "font-size: 0.58rem;" in label_block


def test_ops_home_context_panel_allows_preview_cover_click_to_open_cabinet():
    html = read_static_html("index.html")
    block = html.split("function renderOpsLibraryContextSlotPreviewContent(item, rows, options = {}) {", 1)[1].split("function renderOpsLibraryContextSlotPreview(item, options = {}) {", 1)[0]
    assert 'class="ops-library-slot-preview-item ${isActiveItem ? "active" : ""}"' in block
    assert 'data-operator-context-open-cabinet="${ownedItemId}"' in block
    assert 'data-operator-slot-code="${escapeHtml(String(row?.slot_code || slotCode).trim())}"' in block
    assert 'data-cabinet-name="${escapeHtml(String(row?.cabinet_name || item?.current_cabinet_name || "").trim())}"' in block


def test_ops_home_context_panel_compacts_default_empty_state():
    html = read_static_html("index.html")
    empty_block = html.split(".ops-library-context-empty {", 1)[1].split("}", 1)[0]
    assert "gap: 6px;" in empty_block
    assert "padding: 2px 0;" in empty_block
    default_block = html.split("function renderOpsLibraryContextDefault(climate) {", 1)[1].split("function renderOpsLibraryContextSelection(item) {", 1)[0]
    assert 'class="ops-library-context-empty"' in default_block
    assert 't("operator.context.title")' in default_block
    assert 't("operator.context.subtitle")' in default_block


def test_ops_home_context_panel_distinguishes_map_and_slot_preview_hierarchy():
    html = read_static_html("index.html")
    mini_map_block = html.split(".ops-library-mini-map {", 1)[1].split("}", 1)[0]
    preview_block = html.split(".ops-library-slot-preview {", 1)[1].split("}", 1)[0]
    assert "border-color: #dce7e1;" in mini_map_block
    assert "background: linear-gradient(180deg, rgba(248,250,252,0.96), rgba(243,247,245,0.94));" in mini_map_block
    assert "border-color: #dce7e1;" in preview_block
    assert "background: linear-gradient(180deg, rgba(252,254,253,0.98), rgba(245,248,246,0.95));" in preview_block
    assert "box-shadow: 0 8px 18px rgba(15, 23, 42, 0.04);" in preview_block


def test_ops_home_context_panel_supports_pinned_selection_clear_button():
    html = read_static_html("index.html")
    selection_block = html.split("function renderOpsLibraryContextSelection(item) {", 1)[1].split("function findOpsLibraryContextCabinetGroup(item) {", 1)[0]
    assert 'const isPinnedSelection = item === homeSelectedContextItem;' in selection_block
    assert 'class="ops-library-context-head"' in selection_block
    assert 'data-operator-context-clear="1"' in selection_block
    action_block = html.split("async function handleOperatorLookupAction(e) {", 1)[1].split("async function loadOperatorRequestList() {", 1)[0]
    assert 'const clearBtn = e.target.closest("[data-operator-context-clear]");' in action_block
    assert "homeSelectedContextItem = null;" in action_block
    assert "homePreviewContextItem = null;" in action_block
    assert "renderOpsLibraryContextDefault();" in action_block


def test_ops_home_context_panel_adds_slot_preview_footer_open_action():
    html = read_static_html("index.html")
    preview_block = html.split("function renderOpsLibraryContextSlotPreviewContent(item, rows, options = {}) {", 1)[1].split("function renderOpsLibraryContextSlotPreview(item, options = {}) {", 1)[0]
    assert 'class="ops-library-slot-preview-actions"' in preview_block
    assert 't("operator.context.preview.action.open_current")' in preview_block
    assert 'data-operator-context-open-cabinet="${Number(item?.owned_item_id || item?.id || 0)}"' in preview_block
    assert 'data-operator-slot-code="${escapeHtml(slotCode)}"' in preview_block


def test_operator_context_and_shared_camera_runtime_copy_use_i18n():
    html = read_static_html("index.html")
    context_default_block = html.split("function renderOpsLibraryContextDefault(climate) {", 1)[1].split("function renderOpsLibraryContextSelection(item) {", 1)[0]
    context_selection_block = html.split("function renderOpsLibraryContextSelection(item) {", 1)[1].split("function findOpsLibraryContextCabinetGroup(item) {", 1)[0]
    mini_map_block = html.split("function renderOpsLibraryContextMiniCabinetMap(item, options = {}) {", 1)[1].split("function getOpsLibraryContextSlotPreviewRows(slotCode) {", 1)[0]
    slot_preview_block = html.split("function renderOpsLibraryContextSlotPreviewContent(item, rows, options = {}) {", 1)[1].split("function renderOpsLibraryContextSlotPreview(item, options = {}) {", 1)[0]
    shared_camera_list_block = html.split("function renderSharedCameraList(rows) {", 1)[1].split("function renderSharedCameraPreview(rows) {", 1)[0]
    shared_camera_preview_block = html.split("function renderSharedCameraPreview(rows) {", 1)[1].split("function renderSharedCameraPage() {", 1)[0]

    assert 't("operator.context.title")' in context_default_block
    assert 't("operator.context.subtitle")' in context_default_block
    assert 't("operator.context.state.no_history")' in context_selection_block
    assert 't("operator.context.field.current")' in context_selection_block
    assert 't("operator.context.field.previous")' in context_selection_block
    assert 't("operator.context.action.clear")' in context_selection_block
    assert 't("operator.context.action.open")' in context_selection_block
    assert 't("operator.context.action.open_cabinet_all")' not in context_selection_block
    assert 't("operator.context.state.unslotted_no_cabinet")' not in context_selection_block
    assert 't("operator.context.map.active_badge")' in mini_map_block

    assert 't("operator.context.preview.loading")' in slot_preview_block
    assert 't("operator.context.preview.empty")' in slot_preview_block
    assert 't("operator.context.preview.title")' in slot_preview_block
    assert 't("operator.context.preview.badge_selected")' in slot_preview_block
    assert 't("operator.context.preview.action.open_current")' in slot_preview_block

    assert 't("shared_camera.list.empty")' in shared_camera_list_block
    assert 't("shared_camera.state.no_description")' in shared_camera_list_block
    assert 't("shared_camera.state.active")' in shared_camera_list_block
    assert 't("shared_camera.state.inactive")' in shared_camera_list_block
    assert 't("shared_camera.empty.title")' in shared_camera_preview_block
    assert 't("shared_camera.empty.meta")' in shared_camera_preview_block
    assert 't("shared_camera.state.stream_preview")' in shared_camera_preview_block
    assert 't("shared_camera.state.snapshot_preview")' in shared_camera_preview_block
    assert 't("shared_camera.state.external_stream_only")' in shared_camera_preview_block
    assert 't("shared_camera.state.no_preview")' in shared_camera_preview_block
    assert 't("shared_camera.preview.inactive_body")' in shared_camera_preview_block
    assert 't("shared_camera.preview.rtsp_only_body")' in shared_camera_preview_block
    assert 't("shared_camera.preview.load_failed_body")' in shared_camera_preview_block
    assert '"operator.context.preview.title":' in html
    assert '"shared_camera.preview.rtsp_only_body":' in html


def test_admin_page_has_barcode_intake_hero_shell():
    html = read_static_html("index.html")
    assert 'id="adminBarcodeIntakeHero"' in html
    assert 'id="adminBarcodeCandidatePanel"' in html
    assert 'id="adminBarcodePlacementPanel"' in html
    hero_block = html.split('<section id="adminBarcodeIntakeHero"', 1)[1].split('<div id="registerOwnedDetailBlock"', 1)[0]
    assert 'id="queryArtist"' in hero_block
    assert 'id="queryTitle"' in hero_block
    assert 'id="queryCatalog"' in hero_block
    assert 'id="querySearchBtn"' in hero_block
    assert 'id="adminSearchManageSecondary"' not in html


def test_admin_barcode_intake_hero_contains_scanner_first_copy():
    html = read_static_html("index.html")
    assert "바코드를 스캔하세요" in html
    assert "같은 바코드를 다시 스캔하거나 Enter를 누르면 1순위 칸으로 저장합니다." in html
    assert "추천 위치" in html


def test_admin_barcode_intake_supports_double_scan_confirmation_flow():
    html = read_static_html("index.html")
    assert "let adminBarcodeConfirmToken = \"\";" in html
    assert "let adminBarcodeConfirmCandidateKey = \"\";" in html
    assert "function submitAdminBarcodeIntake()" in html
    assert "if (shouldConfirmAdminBarcodeIntake(barcodeToken)) {" in html
    assert '$("barcodeInput").addEventListener("keydown", (e) => {' in html
    assert "submitAdminBarcodeIntake();" in html


def test_admin_barcode_intake_uses_rank_one_recommendation_when_no_manual_slot_selected():
    html = read_static_html("index.html")
    assert "function resolveAdminBarcodeRecommendedSlotId(candidate) {" in html
    assert "resolveRegisterLookupStorageSlotId(index) ?? resolveAdminBarcodeRecommendedSlotId(candidate)" in html


def test_admin_barcode_intake_allows_manual_recommendation_rank_override():
    html = read_static_html("index.html")
    assert "const adminBarcodePlacementSelectionByCandidateKey = new Map();" in html
    assert 'data-admin-barcode-placement-slot-id="${Number(item.storage_slot_id || 0)}"' in html
    assert 'data-admin-barcode-placement-rank="${rank}"' in html
    assert 'e.target.closest("[data-admin-barcode-placement-slot-id]")' in html
    assert "adminBarcodePlacementSelectionByCandidateKey.set(candidateKey, {" in html


def test_admin_barcode_intake_syncs_recommendation_click_into_manual_slot_state():
    html = read_static_html("index.html")
    assert "function syncAdminBarcodePlacementSelection(candidate, storageSlotId, rank = 0) {" in html
    assert "registerLookupLocationState[String(selectedIndex)] = {" in html
    assert '$("slotId").value = String(slotId);' in html
    assert "renderBarcodeResults(registerLookupCandidates, { resetLocationState: false });" in html
    assert "syncAdminBarcodePlacementSelection(selectedCandidate," in html


def test_admin_barcode_intake_uses_scanner_friendly_duplicate_and_save_copy():
    html = read_static_html("index.html")
    assert 't("media.register.api_lookup.candidate.flag.owned", { count: formatCount(candidate.owned_count) })' in html
    assert "class=\"admin-barcode-candidate-flag owned\"" in html
    assert 'class="admin-barcode-candidate-flag fresh"' in html
    assert 'const noticeText = notices.length ? t("media.register.api_lookup.status.notice_suffix", { count: formatCount(notices.length) }) : "";' in html
    assert 'const savedMessage = t("media.register.api_lookup.status.saved_message", {' in html
    assert 'setStatus("barcodeStatus", "ok", t("media.register.api_lookup.status.confirm_detected"));' in html


def test_admin_barcode_intake_confirms_duplicate_owned_save_before_queueing():
    html = read_static_html("index.html")
    assert "function confirmAdminBarcodeDuplicateSave(candidate) {" in html
    assert 'if (!candidate?.is_owned) return true;' in html
    assert 'window.confirm(confirmText);' in html
    assert 'if (!confirmAdminBarcodeDuplicateSave(candidate)) {' in html
    assert 'setStatus("barcodeStatus", "ok", t("media.register.api_lookup.status.duplicate_cancelled"));' in html


def test_admin_barcode_intake_promotes_next_scan_ready_state_after_save():
    html = read_static_html("index.html")
    assert 'id="adminBarcodeIntakeConfirm"' in html
    assert ".admin-barcode-intake-confirm.ready {" in html
    assert "function setAdminBarcodeIntakeHint(mode = \"confirm\") {" in html
    assert 'setAdminBarcodeIntakeHint("saved");' in html
    assert 'el.textContent = t("media.register.api_lookup.confirm.saved");' in html


def test_admin_barcode_intake_resets_lookup_panels_when_queue_finishes():
    html = read_static_html("index.html")
    assert "function resetAdminBarcodeIntakeWorkspace(opts = {}) {" in html
    assert "selectedCandidate = null;" in html
    assert "registerLookupLocationState = {};" in html
    assert "renderBarcodeResults([]);" in html
    assert 'resetAdminBarcodeIntakeWorkspace({ preserveStatus: true });' in html


def test_admin_barcode_intake_adds_quick_candidate_picker_for_multiple_matches():
    html = read_static_html("index.html")
    assert 'id="adminBarcodeCandidatePicker"' in html
    assert ".admin-barcode-candidate-picker {" in html
    assert "function renderAdminBarcodeCandidatePicker() {" in html
    assert 'data-admin-barcode-candidate-index="${index}"' in html
    assert 'class="admin-barcode-candidate-chip${isSelected ? " active" : ""}"' in html
    assert '$("adminBarcodeCandidatePicker").addEventListener("click", (e) => {' in html


def test_admin_barcode_intake_supports_arrow_key_navigation_between_candidate_chips():
    html = read_static_html("index.html")
    assert "function moveRegisterLookupCandidate(delta) {" in html
    assert 'const chip = root.querySelector(`[data-admin-barcode-candidate-index="${candidateIndex}"]`);' in html
    assert '$("adminBarcodeCandidatePicker").addEventListener("keydown", (e) => {' in html
    assert '!["ArrowLeft", "ArrowRight"].includes(e.key)' in html
    assert 'moveRegisterLookupCandidate(e.key === "ArrowRight" ? 1 : -1);' in html


def test_admin_barcode_intake_strengthens_primary_recommendation_badge_copy():
    html = read_static_html("index.html")
    assert ".admin-barcode-placement-item.rank-1 .admin-barcode-placement-rank {" in html
    assert 't("media.register.api_lookup.placement.rank_first")' in html


def test_admin_barcode_intake_adds_abbreviated_labels_to_candidate_chips():
    html = read_static_html("index.html")
    assert "function buildAdminBarcodeCandidateChipLabel(candidate, index) {" in html
    assert 'const artist = String(candidate?.artist_or_brand || "").trim();' in html
    assert 'const title = String(candidate?.title || "").trim();' in html
    assert 'return `${index + 1} · ${label}`;' in html
    assert '${escapeHtml(buildAdminBarcodeCandidateChipLabel(row, index))}' in html


def test_admin_barcode_intake_shows_transient_success_toast_after_save():
    html = read_static_html("index.html")
    assert 'id="adminBarcodeToast"' in html
    assert ".admin-barcode-toast.show {" in html
    assert "let adminBarcodeToastTimer = 0;" in html
    assert "function showAdminBarcodeToast(message) {" in html
    assert "window.clearTimeout(adminBarcodeToastTimer);" in html
    assert 'window.setTimeout(() => {' in html
    assert 'showAdminBarcodeToast(savedMessage);' in html


def test_admin_barcode_intake_surfaces_current_slot_chip_in_recommendation_panel():
    html = read_static_html("index.html")
    assert ".admin-barcode-placement-picked {" in html
    assert 'const pickedSlot = picked ? getStorageSlotById(Number(picked.storage_slot_id || 0)) : null;' in html
    assert 'const pickedSlotLabel = pickedSlot ? (storageSlotDisplayLabel(pickedSlot) || String(pickedSlot.slot_code || "").trim()) : "";' in html
    assert 't("media.register.api_lookup.placement.picked_label")' in html
    assert '<span class="admin-barcode-placement-picked-chip">${escapeHtml(pickedSlotLabel)}</span>' in html


def test_admin_barcode_intake_highlights_barcode_input_ready_states():
    html = read_static_html("index.html")
    assert 'id="barcodeInput" class="admin-barcode-input"' in html
    assert ".admin-barcode-input.is-confirm-armed {" in html
    assert ".admin-barcode-input.is-ready {" in html
    assert 'function syncAdminBarcodeInputReadyState(mode = "idle") {' in html
    assert 'input.classList.toggle("is-confirm-armed", mode === "confirm");' in html
    assert 'input.classList.toggle("is-ready", mode === "ready");' in html
    assert 'syncAdminBarcodeInputReadyState("confirm");' in html
    assert 'syncAdminBarcodeInputReadyState("ready");' in html
    assert 'syncAdminBarcodeInputReadyState("idle");' in html


def test_admin_barcode_intake_adds_save_target_copy_to_current_slot_chip():
    html = read_static_html("index.html")
    assert ".admin-barcode-placement-picked-copy {" in html
    assert 't("media.register.api_lookup.placement.picked_copy")' in html


def test_admin_barcode_intake_renders_small_input_state_badge():
    html = read_static_html("index.html")
    assert 'id="adminBarcodeInputState" class="admin-barcode-input-state" data-i18n="media.register.api_lookup.field.barcode.idle">스캔 대기</div>' in html
    assert ".admin-barcode-input-state.confirm {" in html
    assert ".admin-barcode-input-state.ready {" in html
    assert 'const state = $("adminBarcodeInputState");' in html
    assert 't("media.register.api_lookup.field.barcode.ready")' in html
    assert 't("media.register.api_lookup.field.barcode.confirm")' in html
    assert 't("media.register.api_lookup.field.barcode.idle")' in html
    assert 'state.classList.toggle("confirm", mode === "confirm");' in html
    assert 'state.classList.toggle("ready", mode === "ready");' in html


def test_admin_barcode_intake_duplicate_confirm_includes_selected_slot():
    html = read_static_html("index.html")
    assert 'const slotId = resolveAdminBarcodeRecommendedSlotId(candidate);' in html
    assert 'const slot = slotId ? getStorageSlotById(slotId) : null;' in html
    assert 't("media.register.api_lookup.duplicate.slot", { slot: storageSlotDisplayLabel(slot) })' in html
    assert 'const confirmText = t("media.register.api_lookup.duplicate.confirm", {' in html


def test_admin_barcode_intake_pulses_input_on_scanner_enter():
    html = read_static_html("index.html")
    assert "@keyframes adminBarcodeInputPulse {" in html
    assert ".admin-barcode-input.scan-pulse {" in html
    assert "let adminBarcodeInputPulseTimer = 0;" in html
    assert "function pulseAdminBarcodeInput() {" in html
    assert "window.clearTimeout(adminBarcodeInputPulseTimer);" in html
    assert 'input.classList.add("scan-pulse");' in html
    assert 'input.classList.remove("scan-pulse");' in html
    assert 'pulseAdminBarcodeInput();' in html


def test_shell_global_barcode_scanner_router_exists():
    html = read_static_html("index.html")
    assert 'const GLOBAL_BARCODE_SCANNER_INPUT_IDS = new Set(["barcodeInput", "operatorLookupQuery", "homeBarcode"]);' in html
    assert "function handleGlobalBarcodeScannerKeydown(e) {" in html
    assert 'document.addEventListener("keydown", handleGlobalBarcodeScannerKeydown, true);' in html


def test_shell_global_barcode_scanner_allows_manual_numeric_typing_in_general_inputs():
    html = read_static_html("index.html")
    block = html.split("function handleGlobalBarcodeScannerKeydown(e) {", 1)[1].split("function renderAuthSession()", 1)[0]
    assert "function isGlobalBarcodeScannerEditableTarget(target) {" in html
    assert "const targetIsEditable = isGlobalBarcodeScannerEditableTarget(e.target);" in block
    assert "if (!targetIsEditable) {" in block
    assert "e.preventDefault();" in block


def test_shell_global_barcode_scanner_restores_editable_field_after_routed_scan():
    html = read_static_html("index.html")
    assert "let globalBarcodeScannerEditableTarget = null;" in html
    assert 'let globalBarcodeScannerEditableInitialValue = "";' in html
    assert "function restoreGlobalBarcodeScannerEditableValue() {" in html
    reset_block = html.split("function resetGlobalBarcodeScannerBuffer() {", 1)[1].split("}", 1)[0]
    restore_block = html.split("function restoreGlobalBarcodeScannerEditableValue() {", 1)[1].split("}", 1)[0]
    assert "globalBarcodeScannerEditableTarget = null;" in reset_block
    assert 'globalBarcodeScannerEditableInitialValue = "";' in reset_block
    assert "const target = globalBarcodeScannerEditableTarget;" in restore_block
    assert "target.value = globalBarcodeScannerEditableInitialValue;" in restore_block




def test_shell_global_barcode_scanner_shows_contextual_toast_after_routing():
    html = read_static_html("index.html")
    assert 'id="shellBarcodeToast"' in html
    assert '.shell-barcode-toast.show {' in html
    assert 'function showShellBarcodeToast(message) {' in html
    ops_block = html.split("async function routeGlobalBarcodeScanForOps(barcode) {", 1)[1].split("async function lookupAdminOwnedBarcodeMatches(barcode) {", 1)[0]
    admin_block = html.split("async function routeGlobalBarcodeScanForAdmin(barcode) {", 1)[1].split("async function routeGlobalBarcodeScan(barcode) {", 1)[0]
    assert 'showShellBarcodeToast(t("operator.lookup.toast.routed"));' in ops_block
    assert 'showShellBarcodeToast(t("media.register.api_lookup.toast.owned_routed", { count: formatCount(lookup.total) }));' in admin_block
    assert 'showShellBarcodeToast(t("media.register.api_lookup.toast.register_routed"));' in admin_block


def test_admin_barcode_intake_uses_shorter_empty_candidate_status_copy():
    html = read_static_html("index.html")
    block = html.split("async function barcodeSearch() {", 1)[1].split("async function querySearch() {", 1)[0]
    assert '? t("media.register.api_lookup.status.candidates_ready", { count: countWithUnit((candidates || []).length) })' in block
    assert ': t("media.register.api_lookup.status.no_candidates_register_direct")' in block


def test_admin_barcode_intake_defaults_meta_source_to_auto():
    html = read_static_html("index.html")
    markup = html.split('<select id="metaSourceFilter">', 1)[1].split("</select>", 1)[0]
    assert '<option selected>AUTO</option>' in markup
    assert '<option>MUSICBRAINZ</option>' in markup
    assert '$("metaSourceFilter").value = "AUTO";' in html


def test_admin_non_barcode_query_search_keeps_auto_and_tries_candidate_sources():
    html = read_static_html("index.html")
    block = html.split("async function querySearch() {", 1)[1].split("function buildOwnedPayload()", 1)[0]
    assert 'const selectedSource = String($("metaSourceFilter").value || "AUTO").trim().toUpperCase() || "AUTO";' in block
    assert "const requestSources = buildRegisterLookupSourceCandidates(selectedSource);" in block
    assert 'const loadingStatusText = t("media.register.api_lookup.status.query_loading", { source: requestSources[0] });' in block
    assert 'setStatus("barcodeStatus", "ok", loadingStatusText);' in block
    assert "for (const source of requestSources) {" in block
    assert "source," in block
    assert 'const adjustedSourceText = usedSource !== selectedSource ? t("media.register.api_lookup.status.adjusted_source", { source: usedSource }) : "";' in block
    assert 'setStatus("barcodeStatus", "ok", t("media.register.api_lookup.status.query_done", {' in block
    assert 'selectedSource === "AUTO" ? "MANIADB" : selectedSource' not in block


def test_admin_query_search_autoadjusts_single_maniadb_category_mismatch():
    html = read_static_html("index.html")
    helper_block = html.split("async function detectRegisterLookupCategoryMismatch(payload, source) {", 1)[1].split("    async function barcodeSearch() {", 1)[0]
    query_block = html.split("async function querySearch() {", 1)[1].split("    function selectedRegisterLookupCandidateSource()", 1)[0]
    assert 'if (String(source || "").trim().toUpperCase() !== "MANIADB") return { categories: [], candidates: [] };' in helper_block
    assert "category: null," in helper_block
    assert "return {" in helper_block
    assert "categories: Array.from(new Set(" in helper_block
    assert "candidates: mismatchCandidates," in helper_block
    assert 'if (!items.length && selectedSource === "MANIADB") {' in query_block
    assert 'const mismatchInfo = await detectRegisterLookupCategoryMismatch(payload, selectedSource);' in query_block
    assert 'if (mismatchInfo.categories.length === 1 && mismatchInfo.candidates.length) {' in query_block
    assert '$("category").value = mismatchInfo.categories[0];' in query_block
    assert "items = mismatchInfo.candidates;" in query_block
    assert 't("media.register.api_lookup.status.category_mismatch_autofix"' in query_block
    assert 'mismatchInfo.categories.join(", ")' in query_block


def test_home_meta_source_candidates_only_fallback_when_source_is_auto():
    html = read_static_html("index.html")
    helper_block = html.split("function buildHomeMetaSourceCandidates(source) {", 1)[1].split("async function searchHomeMetadataByBarcode() {", 1)[0]
    assert 'if (primary === "AUTO") return ["AUTO"];' in helper_block
    assert 'return [primary];' in helper_block
    assert 'return [primary, "AUTO"];' not in helper_block


def test_register_lookup_explicit_source_uses_fallback_candidates_and_provider_status_badges():
    html = read_static_html("index.html")
    assert 'id="barcodeProviderStatusBadges"' in html
    assert 'class="operator-status-badges admin-barcode-provider-status-badges"' in html
    helper_block = html.split("function buildRegisterLookupSourceCandidates(source) {", 1)[1].split("function renderRegisterLookupProviderStatusBadges(entries = []) {", 1)[0]
    assert 'if (primary === "AUTO") return ["AUTO"];' in helper_block
    assert 'const fallbacks = ["DISCOGS", "MANIADB", "ALADIN", "MUSICBRAINZ"].filter((sourceCode) => sourceCode !== primary);' in helper_block
    assert "return [primary, ...fallbacks];" in helper_block
    render_block = html.split("function renderRegisterLookupProviderStatusBadges(entries = []) {", 1)[1].split("async function searchHomeMetadataByBarcode() {", 1)[0]
    assert 't("media.register.api_lookup.provider_status.unavailable", { source: entry.source })' in render_block
    assert 't("media.register.api_lookup.provider_status.fallback_results", { source: entry.source })' in render_block


def test_admin_api_lookup_explicit_source_only_falls_back_after_provider_unavailable():
    html = read_static_html("index.html")
    barcode_block = html.split("async function barcodeSearch() {", 1)[1].split("async function querySearch() {", 1)[0]
    query_block = html.split("async function querySearch() {", 1)[1].split("function buildOwnedPayload()", 1)[0]
    assert 'const requestSources = buildRegisterLookupSourceCandidates(selectedSource);' in barcode_block
    assert 'const providerStatusEntries = [];' in barcode_block
    assert 'if (res.status === 502 && selectedSource !== "AUTO") {' in barcode_block
    assert 'providerStatusEntries.push({ kind: "unavailable", source });' in barcode_block
    assert 'renderRegisterLookupProviderStatusBadges(providerStatusEntries);' in barcode_block
    assert 'const requestSources = buildRegisterLookupSourceCandidates(selectedSource);' in query_block
    assert 'const providerStatusEntries = [];' in query_block
    assert 'if (res.status === 502 && selectedSource !== "AUTO") {' in query_block
    assert 'providerStatusEntries.push({ kind: "fallback_results", source: usedSource });' in query_block


def test_admin_api_lookup_copy_explains_integrated_condition_search_flow():
    html = read_static_html("index.html")
    assert "바코드가 없거나 후보 보정이 필요하면 아래 조건 조회를 함께 사용합니다." in html


def test_admin_register_collect_copy_renames_quick_register_to_direct_register():
    html = read_static_html("index.html")
    assert 'id="registerCollectTabBtn" class="subtab-btn active" type="button" data-i18n="media.register.subtab.direct">직접 등록</button>' in html
    assert '<summary data-i18n="manual.register_direct.summary">직접 등록 페이지 활용 매뉴얼</summary>' in html
    assert 'data-page-help-open="register-direct"' in html
    assert '<h2><span data-i18n="media.register.direct.title">직접 등록</span></h2>' in html
    assert '<button id="quickCreateBtn" class="btn" data-i18n="media.register.direct.action.save">직접 등록 저장</button>' in html


def test_admin_register_collect_copy_renames_barcode_intake_to_api_lookup_register():
    html = read_static_html("index.html")
    assert '<h2 data-i18n="media.register.api_lookup.title">API 조회 / 등록' in html
    assert '<button id="querySearchBtn" class="btn ghost" type="button" data-i18n="media.register.api_lookup.action.query_search">조건 조회</button>' in html


def test_admin_barcode_results_shrink_cover_to_widen_text_lane():
    html = read_static_html("index.html")
    list_block = html.split("#barcodeResults.result-list {", 1)[1].split("}", 1)[0]
    item_block = html.split("#barcodeResults .album-result {", 1)[1].split("}", 1)[0]
    cover_block = html.split("#barcodeResults .album-result-cover {", 1)[1].split("}", 1)[0]
    assert "max-height: 320px;" in list_block
    assert "padding-right: 0;" in list_block
    assert "grid-template-columns: 64px minmax(0, 1fr);" in item_block
    assert "gap: 8px;" in item_block
    assert "width: 64px;" in cover_block
    assert "height: 64px;" in cover_block
def test_shell_global_barcode_scanner_routes_ops_scans_to_operator_lookup():
    html = read_static_html("index.html")
    block = html.split("async function routeGlobalBarcodeScanForOps(barcode) {", 1)[1].split("async function lookupAdminOwnedBarcodeMatches(barcode) {", 1)[0]
    assert 'const normalizedBarcode = String(barcode || "").trim();' in block
    assert '$("operatorLookupQuery").value = normalizedBarcode;' in block
    assert 'setStatus("operatorLookupStatus", "ok", t("operator.lookup.status.barcode_loading"));' in block
    assert "await loadOperatorLookupResults();" in block


def test_shell_global_barcode_scanner_routes_admin_scans_to_existing_search_before_register():
    html = read_static_html("index.html")
    lookup_block = html.split("async function lookupAdminOwnedBarcodeMatches(barcode) {", 1)[1].split("function prepareAdminOwnedBarcodeSearch(barcode) {", 1)[0]
    route_block = html.split("async function routeGlobalBarcodeScanForAdmin(barcode) {", 1)[1].split("function renderAuthSession() {", 1)[0]
    assert "const params = new URLSearchParams({" in lookup_block
    assert 'params.set("barcode", normalizedBarcode);' in lookup_block
    assert 'const res = await fetchWithRetry(`/album-masters?${params.toString()}`' in lookup_block
    assert 'retries: 2,' in lookup_block
    assert 'const lookup = await lookupAdminOwnedBarcodeMatches(normalizedBarcode);' in route_block
    assert 'openAdminConsole("manage");' in route_block
    assert 'await homeSearchOwnedItems({ resetPage: true });' in route_block
    assert 'openAdminConsole("register");' in route_block
    assert '$("barcodeInput").value = normalizedBarcode;' in route_block
    assert "await submitAdminBarcodeIntake();" in route_block


def test_admin_barcode_intake_emphasizes_saved_slot_in_success_toast():
    html = read_static_html("index.html")
    assert ".admin-barcode-toast-slot {" in html
    assert "function showAdminBarcodeToast(message) {" in html
    assert 'const safeSlotLabel = escapeHtml(String(arguments[1] || "").trim());' in html
    assert 'el.innerHTML = safeSlotLabel' in html
    assert 'showAdminBarcodeToast(savedMessage, savedLocationText);' in html


def test_admin_barcode_intake_marks_active_recommendation_as_current_selection():
    html = read_static_html("index.html")
    assert ".admin-barcode-placement-item.active .admin-barcode-placement-active-badge {" in html
    assert 'const activeBadge = isActive ? `<span class="admin-barcode-placement-active-badge">${escapeHtml(t("media.register.api_lookup.placement.badge.active"))}</span>` : "";' in html
    assert '${activeBadge}' in html


def test_admin_barcode_intake_marks_rank_one_recommendation_as_auto_recommended():
    html = read_static_html("index.html")
    assert ".admin-barcode-placement-item.rank-1 .admin-barcode-placement-auto-badge {" in html
    assert 'const autoBadge = rank === 1 ? `<span class="admin-barcode-placement-auto-badge">${escapeHtml(t("media.register.api_lookup.placement.badge.auto"))}</span>` : "";' in html
    assert '${autoBadge}' in html


def test_admin_barcode_intake_shows_planned_slot_chip_in_candidate_summary():
    html = read_static_html("index.html")
    assert "const candidateKey = registerLookupCandidateKey(candidate);" in html
    assert "const selectedPlacement = candidateKey ? adminBarcodePlacementSelectionByCandidateKey.get(candidateKey) : null;" in html
    assert "const selectedSlot = selectedPlacement ? getStorageSlotById(Number(selectedPlacement.storage_slot_id || 0)) : null;" in html
    assert "const saveTargetChip = selectedSlotLabel" in html
    assert 't("media.register.api_lookup.candidate.save_target")' in html


def test_admin_barcode_intake_marks_manual_slot_selection_inside_recommendations():
    html = read_static_html("index.html")
    assert "const isManualSelection = Boolean(picked && Number(picked.rank || 0) > 1);" in html
    assert "const manualSelectionCopy = isManualSelection" in html
    assert 't("media.register.api_lookup.placement.manual_copy")' in html


def test_admin_barcode_intake_compacts_candidate_status_and_slot_into_single_summary_row():
    html = read_static_html("index.html")
    assert ".admin-barcode-candidate-summary-line {" in html
    assert "const summaryLine = ownershipFlag || saveTargetChip" in html
    assert '<div class="admin-barcode-candidate-summary-line">${ownershipFlag}${saveTargetChip}</div>' in html


def test_admin_non_barcode_lookup_fields_define_explicit_tab_order():
    html = read_static_html("index.html")
    assert '<input id="queryArtist" tabindex="1"' in html
    assert '<input id="queryTitle" tabindex="2"' in html
    assert '<input id="queryCatalog" tabindex="3"' in html


def test_admin_non_barcode_lookup_fields_submit_query_search_on_enter():
    html = read_static_html("index.html")
    assert '$("queryArtist").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); querySearch(); } });' in html
    assert '$("queryTitle").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); querySearch(); } });' in html
    assert '$("queryCatalog").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); querySearch(); } });' in html


def test_admin_barcode_intake_explains_when_manual_slot_differs_from_auto_recommendation():
    html = read_static_html("index.html")
    assert ".admin-barcode-placement-manual-note {" in html
    assert "const manualSelectionNote = isManualSelection" in html
    assert 't("media.register.api_lookup.placement.manual_note")' in html


def test_admin_barcode_intake_formats_candidate_meta_as_compact_key_value_line():
    html = read_static_html("index.html")
    assert ".admin-barcode-candidate-meta {" in html
    assert ".admin-barcode-candidate-meta-key {" in html
    assert '<div class="admin-barcode-candidate-meta">' in html
    assert '<span class="admin-barcode-candidate-meta-key">source</span>' in html
    assert '<span class="admin-barcode-candidate-meta-key">barcode</span>' in html
    assert '<span class="admin-barcode-candidate-meta-key">cat#</span>' in html


def test_admin_barcode_intake_strengthens_visual_contrast_between_auto_and_active_badges():
    html = read_static_html("index.html")
    auto_block = html.split(".admin-barcode-placement-item.rank-1 .admin-barcode-placement-auto-badge {", 1)[1].split("}", 1)[0]
    active_block = html.split(".admin-barcode-placement-item.active .admin-barcode-placement-active-badge {", 1)[1].split("}", 1)[0]
    assert "border: 1px solid rgba(15, 118, 110, 0.18);" in auto_block
    assert "background: rgba(15, 118, 110, 0.08);" in auto_block
    assert "background: #1e293b;" in active_block
    assert "box-shadow: 0 2px 8px rgba(15, 23, 42, 0.18);" in active_block


def test_admin_barcode_intake_compacts_recommendation_capacity_line():
    html = read_static_html("index.html")
    assert ".admin-barcode-placement-detail {" in html
    assert 't("media.register.api_lookup.placement.detail", { free: formatCount(freeMm), occupancy: formatCount(occupancy) })' in html


def test_admin_barcode_intake_equalizes_candidate_and_recommendation_card_vertical_rhythm():
    html = read_static_html("index.html")
    candidate_block = html.split(".admin-barcode-candidate-main {", 1)[1].split("}", 1)[0]
    placement_block = html.split(".admin-barcode-placement-item {", 1)[1].split("}", 1)[0]
    assert "min-height: 68px;" in candidate_block
    assert "align-content: start;" in candidate_block
    assert "min-height: 74px;" in placement_block
    assert "align-content: start;" in placement_block


def test_admin_barcode_intake_groups_auto_and_active_badges_on_single_line():
    html = read_static_html("index.html")
    assert ".admin-barcode-placement-badges {" in html
    assert 'const badgeGroup = autoBadge || activeBadge' in html
    assert '<div class="admin-barcode-placement-badges">${autoBadge}${activeBadge}</div>' in html


def test_admin_barcode_intake_compacts_top_input_bar_density():
    html = read_static_html("index.html")
    head_block = html.split(".admin-barcode-intake-head {", 1)[1].split("}", 1)[0]
    bar_block = html.split(".admin-barcode-intake-bar {", 1)[1].split("}", 1)[0]
    state_block = html.split(".admin-barcode-input-state {", 1)[1].split("}", 1)[0]
    button_block = html.split(".admin-barcode-intake-bar .btn {", 1)[1].split("}", 1)[0]
    assert "gap: 8px;" in head_block
    assert "gap: 4px;" in bar_block
    assert "align-items: center;" in bar_block
    assert "margin-top: 0;" in state_block
    assert "padding: 2px 5px;" in state_block
    assert "min-height: 34px;" in button_block
    assert "line-height: 1;" in button_block
    assert "white-space: nowrap;" in button_block


def test_admin_barcode_intake_compacts_selected_slot_copy_into_single_inline_row():
    html = read_static_html("index.html")
    picked_block = html.split("const pickedSummary = pickedSlotLabel ? `", 1)[1].split("` : "";", 1)[0]
    css_block = html.split(".admin-barcode-placement-picked {", 1)[1].split("}", 1)[0]
    copy_block = html.split(".admin-barcode-placement-picked-copy {", 1)[1].split("}", 1)[0]
    assert 't("media.register.api_lookup.placement.picked_copy")' in picked_block
    assert "gap: 4px;" in css_block
    assert "display: inline-flex;" in copy_block
    assert "align-items: center;" in copy_block


def test_admin_barcode_intake_rebalances_top_bar_columns_toward_barcode_input():
    html = read_static_html("index.html")
    bar_block = html.split(".admin-barcode-intake-bar {", 1)[1].split("}", 1)[0]
    button_block = html.split(".admin-barcode-intake-bar .btn {", 1)[1].split("}", 1)[0]
    input_block = html.split(".admin-barcode-input-shell > input {", 1)[1].split("}", 1)[0]
    assert "grid-template-columns: 96px 64px minmax(0, 1fr) 100px;" in bar_block
    assert "min-width: 96px;" in button_block
    assert "line-height: 1;" in input_block


def test_admin_barcode_intake_shortens_selected_slot_label_copy():
    html = read_static_html("index.html")
    picked_block = html.split("const pickedSummary = pickedSlotLabel ? `", 1)[1].split("` : "";", 1)[0]
    label_block = html.split(".admin-barcode-placement-picked-label {", 1)[1].split("}", 1)[0]
    assert 't("media.register.api_lookup.placement.picked_label")' in picked_block
    assert "font-size: 0.63rem;" in label_block


def test_admin_barcode_intake_moves_input_state_badge_inline_with_barcode_input():
    html = read_static_html("index.html")
    shell_block = html.split(".admin-barcode-input-shell {", 1)[1].split("}", 1)[0]
    shell_input_block = html.split(".admin-barcode-input-shell > input {", 1)[1].split("}", 1)[0]
    markup_block = html.split('<label for="barcodeInput" data-i18n="media.register.api_lookup.field.barcode.label">바코드</label>', 1)[1].split('<button id="barcodeSearchBtn"', 1)[0]
    state_block = html.split(".admin-barcode-input-state {", 1)[1].split("}", 1)[0]
    assert "display: grid;" in shell_block
    assert "grid-template-columns: minmax(0, 1fr) auto;" in shell_block
    assert "align-items: center;" in shell_block
    assert "font-size: 0.84rem;" in shell_input_block
    assert "min-height: 34px;" in shell_input_block
    assert '<div class="admin-barcode-input-shell">' in markup_block
    assert 'id="barcodeInput" class="admin-barcode-input"' in markup_block
    assert 'id="adminBarcodeInputState" class="admin-barcode-input-state" data-i18n="media.register.api_lookup.field.barcode.idle">스캔 대기</div>' in markup_block
    assert "margin-top: 0;" in state_block


def test_admin_barcode_intake_compacts_selected_slot_meta_row_even_further():
    html = read_static_html("index.html")
    picked_block = html.split("const pickedSummary = pickedSlotLabel ? `", 1)[1].split("` : "";", 1)[0]
    wrap_block = html.split(".admin-barcode-placement-picked {", 1)[1].split("}", 1)[0]
    chip_block = html.split(".admin-barcode-placement-picked-chip {", 1)[1].split("}", 1)[0]
    assert 't("media.register.api_lookup.placement.picked_label")' in picked_block
    assert "gap: 4px;" in wrap_block
    assert "padding: 2px 7px;" in chip_block


def test_admin_barcode_intake_tightens_inline_input_state_badge_density():
    html = read_static_html("index.html")
    shell_block = html.split(".admin-barcode-input-shell {", 1)[1].split("}", 1)[0]
    state_block = html.split(".admin-barcode-input-state {", 1)[1].split("}", 1)[0]
    assert "gap: 4px;" in shell_block
    assert "font-size: 0.62rem;" in state_block
    assert "padding: 2px 5px;" in state_block


def test_admin_barcode_intake_compacts_candidate_and_recommendation_header_typography():
    html = read_static_html("index.html")
    candidate_title_block = html.split(".admin-barcode-candidate-main strong {", 1)[1].split("}", 1)[0]
    placement_title_block = html.split(".admin-barcode-placement-item strong {", 1)[1].split("}", 1)[0]
    placement_rank_block = html.rsplit(".admin-barcode-placement-rank {", 1)[1].split("}", 1)[0]
    assert "font-size: 0.84rem;" in candidate_title_block
    assert "line-height: 1.25;" in candidate_title_block
    assert "font-size: 0.81rem;" in placement_title_block
    assert "line-height: 1.2;" in placement_title_block
    assert "font-size: 0.62rem;" in placement_rank_block


def test_admin_barcode_intake_unifies_saved_hint_copy_with_success_feedback():
    html = read_static_html("index.html")
    hint_block = html.split("function setAdminBarcodeIntakeHint(mode = \"confirm\") {", 1)[1].split("function confirmAdminBarcodeDuplicateSave(candidate) {", 1)[0]
    assert 'el.textContent = t("media.register.api_lookup.confirm.saved");' in hint_block
    assert 'el.textContent = t("media.register.api_lookup.confirm.ready");' in hint_block
    assert 'const savedMessage = t("media.register.api_lookup.status.saved_message", {' in html


def test_admin_barcode_intake_unifies_candidate_and_recommendation_card_tones():
    html = read_static_html("index.html")
    candidate_block = html.split(".admin-barcode-candidate-summary {", 1)[1].split("}", 1)[0]
    placement_block = html.split(".admin-barcode-placement-item {", 1)[1].split("}", 1)[0]
    assert "border: 1px solid #dbe7e7;" in candidate_block
    assert "border-radius: 8px;" in candidate_block
    assert "background: linear-gradient(180deg, #ffffff, #f8fbfb);" in candidate_block
    assert "border: 1px solid #dbe7e7;" in placement_block
    assert "background: linear-gradient(180deg, #ffffff, #f8fbfb);" in placement_block


def test_admin_barcode_intake_compacts_left_filter_label_and_select_typography():
    html = read_static_html("index.html")
    label_block = html.split(".admin-barcode-intake-bar > div > label {", 1)[1].split("}", 1)[0]
    select_block = html.split(".admin-barcode-intake-bar > div > select,\n    .admin-barcode-intake-bar > div > input[type=\"number\"] {", 1)[1].split("}", 1)[0]
    assert "font-size: 0.69rem;" in label_block
    assert "margin-bottom: 3px;" in label_block
    assert "font-size: 0.84rem;" in select_block
    assert "min-height: 34px;" in select_block


def test_admin_barcode_intake_tightens_candidate_and_recommendation_internal_spacing():
    html = read_static_html("index.html")
    candidate_block = html.split(".admin-barcode-candidate-summary {", 1)[1].split("}", 1)[0]
    candidate_main_block = html.split(".admin-barcode-candidate-main {", 1)[1].split("}", 1)[0]
    placement_block = html.split(".admin-barcode-placement-item {", 1)[1].split("}", 1)[0]
    assert "gap: 7px;" in candidate_block
    assert "gap: 3px;" in candidate_main_block
    assert "padding: 5px 7px;" in placement_block
    assert "gap: 1px;" in placement_block


def test_admin_barcode_intake_tightens_right_side_status_badge_and_query_button_rhythm():
    html = read_static_html("index.html")
    bar_block = html.split(".admin-barcode-intake-bar {", 1)[1].split("}", 1)[0]
    shell_block = html.split(".admin-barcode-input-shell {", 1)[1].split("}", 1)[0]
    button_block = html.split(".admin-barcode-intake-bar .btn {", 1)[1].split("}", 1)[0]
    assert "gap: 4px;" in bar_block
    assert "gap: 4px;" in shell_block
    assert "min-height: 34px;" in button_block
    assert "min-width: 96px;" in button_block


def test_admin_barcode_intake_adds_slot_label_inside_success_toast_chip():
    html = read_static_html("index.html")
    assert ".admin-barcode-toast-slot-label {" in html
    assert '`${safeMessage}<strong class="admin-barcode-toast-slot"><span class="admin-barcode-toast-slot-label">${escapeHtml(t("media.register.api_lookup.toast.slot_label"))}</span>${safeSlotLabel}</strong>`' in html


def test_ops_home_context_panel_allows_previous_location_open_action():
    html = read_static_html("index.html")
    selection_block = html.split("function renderOpsLibraryContextSelection(item) {", 1)[1].split("function findOpsLibraryContextCabinetGroup(item) {", 1)[0]
    assert 'const previousSlotCode = String(item?.previous_slot_code || "").trim();' in selection_block
    assert 'const canOpenPrevious = Boolean(previousSlotCode && previousSlotCode !== "UNASSIGNED");' in selection_block
    assert 'data-operator-context-open-cabinet="${ownedItemId}"' in selection_block
    assert 'data-operator-slot-code="${escapeHtml(previousSlotCode)}"' in selection_block
    assert '>${escapeHtml(t("operator.context.action.open"))}</button>' in selection_block


def test_ops_home_context_panel_adds_hover_title_to_mini_map_cells():
    html = read_static_html("index.html")
    mini_map_block = html.split("function renderOpsLibraryContextMiniCabinetMap(item, options = {}) {", 1)[1].split("function getOpsLibraryContextSlotPreviewRows(slotCode) {", 1)[0]
    assert 'const hoverTitle = dashboardSlotHoverHintText(row);' in mini_map_block
    assert 'title="${escapeHtml(hoverTitle)}"' in mini_map_block


def test_dashboard_cabinet_map_cells_use_first_item_hover_hint():
    html = read_static_html("index.html")
    helper_block = html.split("    function dashboardSlotHoverHintText(slotRow, group = null) {", 1)[1].split("    function renderDashboardSlotCards(rows, totalInCollection) {", 1)[0]
    render_block = html.split("    function renderDashboardSlotCards(rows, totalInCollection) {", 1)[1].split("    async function loadDashboardSlotItems(slotRow, opts = {}) {", 1)[0]
    assert 'const firstItemHint = dashboardSlotFirstItemHintText(slotRow);' in helper_block
    assert 'return [dashboardCabinetMapCellLabel(slotRow, group), firstItemHint].filter(Boolean).join(" · ");' in helper_block
    assert 'const hoverTitle = dashboardSlotHoverHintText(row, group);' in render_block
    assert 'title="${escapeHtml(hoverTitle)}"' in render_block


def test_ops_home_context_panel_allows_mini_map_cell_click_to_open_cabinet():
    html = read_static_html("index.html")
    mini_map_block = html.split("function renderOpsLibraryContextMiniCabinetMap(item, options = {}) {", 1)[1].split("function getOpsLibraryContextSlotPreviewRows(slotCode) {", 1)[0]
    assert 'data-operator-context-open-cabinet="${Number(item?.owned_item_id || item?.id || 0)}"' in mini_map_block
    assert 'data-operator-slot-code="${escapeHtml(String(row?.slot_code || "").trim())}"' in mini_map_block
    cell_block = html.split(".ops-library-mini-map-cell {", 1)[1].split("}", 1)[0]
    assert "cursor: pointer;" in cell_block


def test_ops_home_context_panel_compacts_missing_previous_location_copy():
    html = read_static_html("index.html")
    selection_block = html.split("function renderOpsLibraryContextSelection(item) {", 1)[1].split("function findOpsLibraryContextCabinetGroup(item) {", 1)[0]
    assert 'const previousLocation = canOpenPrevious ? buildOperatorPreviousLocationLabel(item) : t("operator.context.state.no_history");' in selection_block


def test_ops_home_context_panel_allows_current_location_open_action():
    html = read_static_html("index.html")
    selection_block = html.split("function renderOpsLibraryContextSelection(item) {", 1)[1].split("function findOpsLibraryContextCabinetGroup(item) {", 1)[0]
    assert 'const canOpenCurrent = Boolean(String(item?.current_slot_code || "").trim() || (currentCabinetName && currentColumnCode && currentCellCode));' in selection_block
    assert 'data-operator-slot-code="${escapeHtml(String(item?.current_slot_code || "").trim())}"' in selection_block
    assert '<strong>${escapeHtml(t("operator.context.field.current"))}</strong>' in selection_block
    assert '>${escapeHtml(t("operator.context.action.open"))}</button>' in selection_block


def test_ops_home_context_panel_strengthens_active_mini_map_cell_accent():
    html = read_static_html("index.html")
    active_block = html.split(".ops-library-mini-map-cell.active {", 1)[1].split("}", 1)[0]
    assert "0 0 0 4px var(--selected-ring)" in active_block
    assert "border-color: var(--selected-accent);" in active_block


def test_ops_home_context_panel_styles_location_open_actions_as_chips():
    html = read_static_html("index.html")
    line_block = html.split(".operator-mini-line {", 1)[1].split("}", 1)[0]
    chip_block = html.split(".operator-mini-linkchip {", 1)[1].split("}", 1)[0]
    selection_block = html.split("function renderOpsLibraryContextSelection(item) {", 1)[1].split("function findOpsLibraryContextCabinetGroup(item) {", 1)[0]
    assert "align-items: flex-start;" in line_block
    assert "display: inline-flex;" in chip_block
    assert "border-radius: 999px;" in chip_block
    assert 'class="operator-mini-linkchip"' in selection_block


def test_ops_home_context_panel_highlights_selected_item_in_slot_preview():
    html = read_static_html("index.html")
    preview_block = html.split("function renderOpsLibraryContextSlotPreviewContent(item, rows, options = {}) {", 1)[1].split("function renderOpsLibraryContextSlotPreview(item, options = {}) {", 1)[0]
    item_block = html.split(".ops-library-slot-preview-item.active {", 1)[1].split("}", 1)[0]
    thumb_block = html.split(".ops-library-slot-preview-item.active .ops-library-slot-preview-thumb {", 1)[1].split("}", 1)[0]
    assert "const isActiveItem = ownedItemId > 0 && ownedItemId === Number(item?.owned_item_id || item?.id || 0);" in preview_block
    assert 'class="ops-library-slot-preview-item ${isActiveItem ? "active" : ""}"' in preview_block
    assert "transform: translateY(-1px);" in item_block
    assert "border-color: var(--selected-accent);" in thumb_block


def test_selected_slot_highlight_uses_shared_high_contrast_palette():
    html = read_static_html("index.html")
    root_block = html.split(":root {", 1)[1].split("}", 1)[0]
    ops_item_block = html.split(".ops-library-slot-preview-item.active {", 1)[1].split("}", 1)[0]
    ops_mini_map_block = html.split(".ops-library-mini-map-cell.active {", 1)[1].split("}", 1)[0]
    ops_preview_block = html.split(".ops-library-slot-preview-item.active .ops-library-slot-preview-thumb {", 1)[1].split("}", 1)[0]
    cabinet_map_block = html.split(".dashboard-cabinet-map-cell.active {", 1)[1].split("}", 1)[0]
    cabinet_map_code_block = html.split(".dashboard-cabinet-map-cell.active :is(", 1)[1].split("}", 1)[0]
    floor_map_block = html.split(".dashboard-floor-cell.active {", 1)[1].split("}", 1)[0]
    floor_map_title_block = html.split(".dashboard-floor-cell.active :is(", 1)[1].split("}", 1)[0]
    assert "--selected-accent: #8b5cf6;" in root_block
    assert "--selected-accent-strong: #7c3aed;" in root_block
    assert "--selected-accent-deep: #4c1d95;" in root_block
    assert "--selected-surface: #f3e8ff;" in root_block
    assert "--selected-ring: rgba(139, 92, 246, 0.36);" in root_block
    assert "background: linear-gradient(180deg, rgba(255, 237, 213, 0.96), rgba(255, 247, 237, 0.48));" in ops_item_block
    assert "box-shadow: 0 10px 18px var(--selected-shadow-soft);" in ops_item_block
    assert "background: linear-gradient(180deg, var(--selected-accent-deep), var(--selected-accent-strong));" in ops_mini_map_block
    assert "border-color: var(--selected-accent);" in ops_mini_map_block
    assert "0 0 0 4px var(--selected-ring)" in ops_mini_map_block
    assert "border-color: var(--selected-accent);" in ops_preview_block
    assert "0 0 0 4px var(--selected-ring)" in ops_preview_block
    assert "border-color: var(--selected-accent-strong);" in cabinet_map_block
    assert "color: var(--selected-accent-deep);" in cabinet_map_block
    assert "0 0 0 4px var(--selected-ring)" in cabinet_map_block
    assert "color: inherit;" in cabinet_map_code_block
    assert "border-color: var(--selected-accent-strong);" in floor_map_block
    assert "color: var(--selected-accent-deep);" in floor_map_block
    assert "0 0 0 4px var(--selected-ring)" in floor_map_block
    assert "color: inherit;" in floor_map_title_block


def test_dashboard_and_manage_selected_items_use_stronger_contrast_highlight():
    html = read_static_html("index.html")
    result_pick_block = html.split(".result-item.pick {", 1)[1].split("}", 1)[0]
    shelf_selected_block = html.split(".shelf-item.selected {", 1)[1].split("}", 1)[0]
    covercard_pick_block = html.split(".dashboard-slot-covercard.pick {", 1)[1].split("}", 1)[0]
    covercard_cover_pick_block = html.split(".dashboard-slot-covercard.pick .dashboard-slot-covercard-cover {", 1)[1].split("}", 1)[0]
    shelfcard_pick_block = html.split(".dashboard-slot-shelfcard.pick {", 1)[1].split("}", 1)[0]
    listitem_pick_block = html.split(".dashboard-slot-listitem.pick {", 1)[1].split("}", 1)[0]
    assert "border-color: var(--selected-accent-strong);" in result_pick_block
    assert "box-shadow: 0 0 0 4px var(--selected-ring), 0 14px 26px var(--selected-shadow-soft);" in result_pick_block
    assert "background: linear-gradient(180deg, var(--selected-surface), var(--selected-surface-soft));" in result_pick_block
    assert "border-color: var(--selected-accent);" in shelf_selected_block
    assert "0 0 0 4px var(--selected-ring)" in shelf_selected_block
    assert "box-shadow: none;" in covercard_pick_block
    assert "border-color: #d7dde5;" in covercard_pick_block
    assert "background: linear-gradient(180deg, #ffffff, #f8fafc);" in covercard_pick_block
    assert "border-color: var(--selected-accent);" in covercard_cover_pick_block
    assert "box-shadow: 0 12px 22px rgba(15, 23, 42, 0.14);" in covercard_cover_pick_block
    assert "box-shadow: none;" in shelfcard_pick_block
    assert "border-color: transparent;" in shelfcard_pick_block
    assert "background: transparent;" in shelfcard_pick_block
    assert "0 0 0 4px var(--selected-ring)" not in covercard_pick_block
    assert "var(--selected-shadow-soft)" not in covercard_pick_block
    assert "border-color: var(--selected-accent);" in listitem_pick_block


def test_storage_mapping_uses_size_group_legend_and_slot_classes():
    html = read_static_html("index.html")
    assert 'data-i18n="dashboard.mapping.legend.lp"' not in html
    assert 'data-i18n="dashboard.mapping.legend.cd"' not in html
    assert 'data-i18n="dashboard.mapping.legend.size_lp"' in html
    assert 'data-i18n="dashboard.mapping.legend.size_book"' in html
    assert 'data-i18n="dashboard.mapping.legend.size_oversize"' in html
    assert 'data-i18n="dashboard.mapping.legend.size_cassette"' in html
    assert 'data-i18n="dashboard.mapping.legend.size_goods"' in html
    assert ".dashboard-cabinet-map-cell.size-lp::before {" in html
    assert ".dashboard-cabinet-map-cell.size-book::before {" in html
    assert ".dashboard-cabinet-map-cell.size-oversize::before {" in html
    assert ".dashboard-cabinet-map-cell.size-cassette::before {" in html
    assert ".dashboard-cabinet-map-cell.size-goods::before {" in html
    legend_block = html.split('<div class="dashboard-slot-map-legend">', 1)[1].split("</div>", 1)[0]
    assert legend_block.index('data-i18n="dashboard.mapping.legend.size_lp"') < legend_block.index('data-i18n="dashboard.mapping.legend.size_book"')
    assert legend_block.index('data-i18n="dashboard.mapping.legend.size_book"') < legend_block.index('data-i18n="dashboard.mapping.legend.size_oversize"')
    assert legend_block.index('data-i18n="dashboard.mapping.legend.size_oversize"') < legend_block.index('data-i18n="dashboard.mapping.legend.size_cassette"')
    assert legend_block.index('data-i18n="dashboard.mapping.legend.size_cassette"') < legend_block.index('data-i18n="dashboard.mapping.legend.size_goods"')
    assert legend_block.index('data-i18n="dashboard.mapping.legend.size_goods"') < legend_block.index('data-i18n="dashboard.mapping.legend.free"')
    render_block = html.split("function renderDashboardSlotCards(rows, totalInCollection) {", 1)[1].split("async function loadDashboardSlotItems", 1)[0]
    assert 'const sizeClass = dashboardCabinetMapSizeClass(row);' in render_block
    assert 'class="dashboard-cabinet-map-cell ${active ? "active" : ""} ${sizeClass}"' in render_block


def test_apply_locale_rerenders_dashboard_and_operator_context_runtime_panels():
    html = read_static_html("index.html")
    helper_block = html.split("function rerenderLocaleSensitiveViews() {", 1)[1].split("function applyLocale(locale = appLocale) {", 1)[0]
    block = html.split("function applyLocale(locale = appLocale) {", 1)[1].split("function mediaDisplayLabel(value) {", 1)[0]
    assert "rerenderLocaleSensitiveViews();" in block
    assert "rerender(() => renderOperatorLookupResults());" in helper_block
    assert "rerender(() => renderHomeSearchResults(homeSearchResults));" in helper_block
    assert "rerender(() => renderDashboardWorkbench());" in helper_block
    assert "rerender(() => renderOpsLibraryContextDefault());" in helper_block


def test_ops_home_context_panel_uses_card_style_for_location_rows():
    html = read_static_html("index.html")
    list_block = html.split(".operator-mini-list {", 1)[1].split("}", 1)[0]
    card_block = html.split(".operator-mini-card {", 1)[1].split("}", 1)[0]
    selection_block = html.split("function renderOpsLibraryContextSelection(item) {", 1)[1].split("function findOpsLibraryContextCabinetGroup(item) {", 1)[0]
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in list_block
    assert "border-radius: 14px;" in card_block
    assert "border: 1px solid #dce7e1;" in card_block
    assert 'id="opsLibraryContextCurrentLocation" class="operator-mini-line operator-mini-card"' in selection_block
    assert 'id="opsLibraryContextPreviousLocation" class="operator-mini-line operator-mini-card"' in selection_block


def test_ops_home_context_panel_adds_selected_badge_to_active_slot_preview_item():
    html = read_static_html("index.html")
    preview_block = html.split("function renderOpsLibraryContextSlotPreviewContent(item, rows, options = {}) {", 1)[1].split("function renderOpsLibraryContextSlotPreview(item, options = {}) {", 1)[0]
    badge_block = html.split(".ops-library-slot-preview-badge {", 1)[1].split("}", 1)[0]
    assert 'class="ops-library-slot-preview-badge">${escapeHtml(t("operator.context.preview.badge_selected"))}</span>' in preview_block
    assert "position: absolute;" in badge_block
    assert "top: 6px;" in badge_block


def test_ops_home_context_panel_compacts_selection_header_copy():
    html = read_static_html("index.html")
    head_block = html.split(".ops-library-context-head {", 1)[1].split("}", 1)[0]
    copy_block = html.split(".ops-library-context-head-copy {", 1)[1].split("}", 1)[0]
    subtitle_block = html.split(".ops-library-context-subtitle {", 1)[1].split("}", 1)[0]
    selection_block = html.split("function renderOpsLibraryContextSelection(item) {", 1)[1].split("function findOpsLibraryContextCabinetGroup(item) {", 1)[0]
    assert "align-items: flex-start;" in head_block
    assert "display: grid;" in copy_block
    assert "gap: 2px;" in copy_block
    assert "font-size: 0.68rem;" in subtitle_block
    assert 'class="ops-library-context-head-copy"' in selection_block
    assert 'class="ops-library-context-subtitle"' in selection_block


def test_ops_home_context_panel_animates_mini_map_cell_on_open_click():
    html = read_static_html("index.html")
    active_block = html.split(".ops-library-mini-map-cell.is-opening {", 1)[1].split("}", 1)[0]
    action_block = html.split("async function handleOperatorLookupAction(e) {", 1)[1].split("async function loadOperatorRequestList() {", 1)[0]
    assert "animation: ops-library-mini-map-pulse 480ms ease-out;" in active_block
    assert 'if (contextCabinetBtn.classList.contains("ops-library-mini-map-cell")) {' in action_block
    assert 'contextCabinetBtn.classList.remove("is-opening");' in action_block
    assert 'contextCabinetBtn.offsetWidth;' in action_block
    assert 'contextCabinetBtn.classList.add("is-opening");' in action_block


def test_ops_home_context_panel_compacts_default_empty_copy():
    html = read_static_html("index.html")
    default_block = html.split("function renderOpsLibraryContextDefault(climate) {", 1)[1].split("function renderOpsLibraryContextSelection(item) {", 1)[0]
    assert 't("operator.context.subtitle")' in default_block
    assert "검색 결과를 선택하면 현재 위치와 직전 위치를 여기서 바로 확인합니다." not in default_block


def test_ops_home_context_panel_uses_link_style_for_slot_preview_footer_action():
    html = read_static_html("index.html")
    link_block = html.split(".ops-library-slot-preview-link {", 1)[1].split("}", 1)[0]
    preview_block = html.split("function renderOpsLibraryContextSlotPreviewContent(item, rows, options = {}) {", 1)[1].split("function renderOpsLibraryContextSlotPreview(item, options = {}) {", 1)[0]
    assert "padding: 6px 10px;" in link_block
    assert "border-radius: 999px;" in link_block
    assert "text-decoration: none;" in link_block
    assert 'class="ops-library-slot-preview-link"' in preview_block


def test_ops_home_context_panel_compacts_weather_card_density():
    html = read_static_html("index.html")
    search_shell_block = html.split(".operator-search-shell {", 1)[1].split("}", 1)[0]
    sidebar_block = html.split(".ops-library-context-panel.operator-shell-sidebar {", 1)[1].split("}", 1)[0]
    card_block = html.split(".operator-weather-card {", 1)[1].split("}", 1)[0]
    head_block = html.split(".operator-weather-head {", 1)[1].split("}", 1)[0]
    icon_block = html.split(".operator-weather-icon {", 1)[1].split("}", 1)[0]
    summary_block = html.split(".operator-weather-summary {", 1)[1].split("}", 1)[0]
    metrics_block = html.split(".operator-weather-metrics {", 1)[1].split("}", 1)[0]
    metric_block = html.split(".operator-weather-metric {", 1)[1].split("}", 1)[0]
    foot_block = html.split(".operator-weather-foot {", 1)[1].split("}", 1)[0]
    assert "gap: 2px;" in card_block
    assert 'grid-template-areas:' in card_block
    assert '"head head"' in card_block
    assert '"summary metrics"' in card_block
    assert '"foot foot"' in card_block
    assert "padding: 10px 10px 12px;" in search_shell_block
    assert "position: sticky;" in sidebar_block
    assert "top: 88px;" in sidebar_block
    assert "padding: 8px 8px 10px;" in card_block
    assert "overflow: hidden;" in card_block
    assert "position: sticky;" not in card_block
    assert "top: 88px;" not in card_block
    assert "gap: 4px;" in head_block
    assert "width: 30px;" in icon_block
    assert "height: 30px;" in icon_block
    assert "gap: 0;" in summary_block
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in metrics_block
    assert "gap: 4px;" in metrics_block
    assert "padding: 4px 7px;" in metric_block
    assert "gap: 2px;" in metric_block
    assert "gap: 0;" in foot_block


def test_ops_home_lookup_lists_do_not_force_internal_scroll_region():
    html = read_static_html("index.html")
    list_block = html.split(".operator-result-list,", 1)[1].split(".operator-recent-sections {", 1)[0]
    assert "max-height:" not in list_block
    assert "overflow: auto;" not in list_block


def test_media_search_results_do_not_force_internal_scroll_region():
    html = read_static_html("index.html")
    surface_block = html.split("#adminSearchSurface,", 1)[1].split("#homeSearchResults.result-list {", 1)[0]
    assert "max-height: none !important;" in surface_block
    assert "overflow: visible !important;" in surface_block
    assert "height: auto !important;" in surface_block
    result_block = html.split("#homeSearchResults.result-list {", 1)[1].split("}", 1)[0]
    assert "max-height: none !important;" in result_block
    assert "overflow: visible !important;" in result_block
    assert "height: auto !important;" in result_block


def test_media_search_surface_adds_right_side_context_panel():
    html = read_static_html("index.html")
    layout_block = html.split(".media-search-layout {", 1)[1].split("}", 1)[0]
    search_card_block = html.split("#homeSearchCard {", 1)[1].split("}", 1)[0]
    panel_block = html.split(".media-search-context-panel {", 1)[1].split("}", 1)[0]
    panel_id_block = html.split("#adminSearchContextPanel {", 1)[1].split("}", 1)[0]
    body_id_block = html.split("#adminSearchContextBody {", 1)[1].split("}", 1)[0]
    assert 'class="admin-manage-surface active media-search-layout"' in html
    assert 'id="adminSearchContextPanel" class="media-search-context-panel"' in html
    assert 'id="adminSearchContextBody"' in html
    assert 'data-i18n="media.search.context.title"' in html
    assert "display: flex !important;" in layout_block
    assert "align-items: flex-start;" in layout_block
    assert "flex: 0 1 60%;" in search_card_block
    assert "flex: 0 1 40%;" in panel_block
    assert "align-self: start;" in panel_block
    assert "position: sticky !important;" in panel_block
    assert "top: 20px !important;" in panel_block
    assert "position: sticky !important;" in panel_id_block
    assert "top: 20px !important;" in panel_id_block
    assert "position: relative !important;" in body_id_block
    assert "bottom: auto !important;" in body_id_block
    assert 'id="adminSearchContextPanel" class="media-search-context-panel" style="position:sticky;top:20px;align-self:start;"' in html
    assert 'id="adminSearchContextBody" class="card" style="position:relative;top:auto;bottom:auto;"' in html


def test_index_defines_network_error_retry_helper_for_search_requests():
    html = read_static_html("index.html")
    assert "function isRetryableFetchError(err) {" in html
    assert "async function fetchWithRetry(input, init = {}, options = {}) {" in html
    helper_block = html.split("async function fetchWithRetry(input, init = {}, options = {}) {", 1)[1].split("function firstOperatorFormatLine(", 1)[0]
    assert "function buildClientRequestId() {" in html
    assert "const clientRequestId = String(options.requestId || buildClientRequestId()).trim();" in helper_block
    assert '"X-Client-Request-ID"' in helper_block
    assert "const retries = Math.max(0, Number(options.retries ?? 1) || 0);" in helper_block
    assert "const onRetry = typeof options.onRetry === \"function\" ? options.onRetry : null;" in helper_block
    assert "if (!isRetryableFetchError(err) || attempt >= retries) {" in helper_block
    assert 'const errorMessage = detailText(err?.message ?? err) || t("common.request_failed");' in helper_block
    assert 'throw new Error(`${errorMessage} [ref: ${clientRequestId}]`);' in helper_block
    assert "if (onRetry) onRetry(attempt + 1, retries + 1, err);" in helper_block
    assert "await new Promise((resolve) => window.setTimeout(resolve, retryDelayMs * (attempt + 1)));" in helper_block


def test_search_flows_use_fetch_retry_helper_for_network_failures():
    html = read_static_html("index.html")
    admin_search_block = html.split("async function homeSearchOwnedItems(opts = {}) {", 1)[1].split("function renderHomeLocationInfo(row) {", 1)[0]
    ops_lookup_block = html.split("async function loadOperatorLookupResults() {", 1)[1].split("function firstOperatorFormatLine(", 1)[0]
    barcode_block = html.split("async function barcodeSearch() {", 1)[1].split("async function querySearch() {", 1)[0]
    query_block = html.split("async function querySearch() {", 1)[1].split("    function selectedRegisterLookupCandidateSource()", 1)[0]
    master_search_block = html.split("async function searchAlbumMasters() {", 1)[1].split("    function masterVariantRowHtml(row) {", 1)[0]
    assert "const res = await fetchWithRetry(`/album-masters?${params.toString()}`" in admin_search_block
    assert "const res = await fetchWithRetry(`/operator/catalog-search?${params.toString()}`" in ops_lookup_block
    assert 'const res = await fetchWithRetry("/ingest/barcode",' in barcode_block
    assert 'const res = await fetchWithRetry("/ingest/search",' in query_block
    assert 'const res = await fetchWithRetry("/album-masters/search",' in master_search_block


def test_media_search_omits_acquisition_mode_filter_field():
    html = read_static_html("index.html")
    assert 'homeAcquisitionMode' not in html
    assert 'media.search.field.acquisition_mode.label' not in html


def test_media_search_includes_signature_mode_filter_field():
    html = read_static_html("index.html")
    assert '<label for="homeSignatureMode" data-i18n="media.search.field.signature_mode.label">싸인 경로</label>' in html
    assert '<select id="homeSignatureMode">' in html
    assert '<option value="ANY" data-i18n="media.search.field.signature_mode.option.any">전체</option>' in html
    assert '<option value="DIRECT" data-i18n="media.search.field.signature_mode.option.direct">직접</option>' in html
    assert '<option value="PURCHASE" data-i18n="media.search.field.signature_mode.option.purchase">구매</option>' in html
    assert '"media.search.field.signature_mode.label": "싸인 경로"' in html
    assert '"media.search.field.signature_mode.option.direct": "직접"' in html
    assert '"media.search.field.signature_mode.option.purchase": "구매"' in html


def test_media_search_includes_sort_mode_filter_field():
    html = read_static_html("index.html")
    assert '<label for="homeSortMode" data-i18n="media.search.field.sort_mode.label">정렬</label>' in html
    assert '<select id="homeSortMode">' in html
    assert '<option value="CREATED_DESC" data-i18n="media.search.field.sort_mode.option.created_desc">최신 등록</option>' in html
    assert '<option value="ARTIST_ASC" data-i18n="media.search.field.sort_mode.option.artist_asc">아티스트순</option>' in html
    assert '<option value="RELEASE_DESC" data-i18n="media.search.field.sort_mode.option.release_desc">발매일 최신순</option>' in html
    assert '<option value="SIGNED_FIRST" data-i18n="media.search.field.sort_mode.option.signed_first">싸인 우선</option>' in html
    assert '"media.search.field.sort_mode.label": "정렬"' in html


def test_media_search_uses_two_row_filter_layout_with_secondary_controls_on_bottom_row():
    html = read_static_html("index.html")
    top_block = html.split('<div class="home-search-grid-top">', 1)[1].split('<div class="home-search-grid-bottom">', 1)[0]
    bottom_block = html.split('<div class="home-search-grid-bottom">', 1)[1].split('<div id="homeSearchStatus" class="status"></div>', 1)[0]

    assert 'id="homeArtist"' in top_block
    assert 'id="homeItemName"' in top_block
    assert 'id="homeReleaseYear"' in top_block
    assert 'id="homeBarcode"' not in top_block
    assert 'id="homeCatalogNo"' not in top_block
    assert 'id="homeSignatureMode"' not in top_block
    assert 'id="homeSortMode"' not in top_block

    assert 'id="homeBarcode"' in bottom_block
    assert 'id="homeCatalogNo"' in bottom_block
    assert 'id="homeSignatureMode"' in bottom_block
    assert 'id="homeSortMode"' in bottom_block
    assert 'id="homeSearchBtn"' in bottom_block
    assert 'id="homeResetBtn"' in bottom_block
    assert 'id="homeNewBtn"' in bottom_block

    assert """    .home-search-grid-bottom {
      grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr) 104px 104px 40px 40px 40px;
      margin-top: 6px;
    }""" in html


def test_media_search_omits_acquisition_mode_param_and_reset():
    html = read_static_html("index.html")
    admin_search_block = html.split("async function homeSearchOwnedItems(opts = {}) {", 1)[1].split("function renderHomeLocationInfo(row) {", 1)[0]
    assert "homeAcquisitionMode" not in admin_search_block
    assert "acquisition_mode" not in admin_search_block
    assert '$("homeAcquisitionMode").value = "ANY";' not in html


def test_media_search_sends_signature_mode_only_when_selected_and_resets_to_any():
    html = read_static_html("index.html")
    admin_search_block = html.split("async function homeSearchOwnedItems(opts = {}) {", 1)[1].split("function renderHomeLocationInfo(row) {", 1)[0]
    assert 'const signatureMode = String($("homeSignatureMode").value || "ANY").trim().toUpperCase() || "ANY";' in admin_search_block
    assert 'if (signatureMode !== "ANY") params.set("signature_mode", signatureMode);' in admin_search_block
    assert '$("homeSignatureMode").value = "ANY";' in html


def test_media_search_sends_sort_mode_only_when_selected_and_resets_to_default():
    html = read_static_html("index.html")
    admin_search_block = html.split("async function homeSearchOwnedItems(opts = {}) {", 1)[1].split("function renderHomeLocationInfo(row) {", 1)[0]
    assert 'const sortMode = String($("homeSortMode").value || "CREATED_DESC").trim().toUpperCase() || "CREATED_DESC";' in admin_search_block
    assert 'if (sortMode !== "CREATED_DESC") params.set("sort_mode", sortMode);' in admin_search_block
    assert '$("homeSortMode").value = "CREATED_DESC";' in html


def test_operator_lookup_includes_signature_filter_field_only():
    html = read_static_html("index.html")
    assert '<label for="operatorLookupSignatureMode" data-i18n="operator.lookup.field.signature_mode.label">싸인 경로</label>' in html
    assert '<select id="operatorLookupSignatureMode">' in html
    assert '<option value="DIRECT" data-i18n="operator.lookup.field.signature_mode.option.direct">직접</option>' in html
    assert '<option value="PURCHASE" data-i18n="operator.lookup.field.signature_mode.option.purchase">구매</option>' in html
    assert 'operatorLookupAcquisitionMode' not in html
    assert '"operator.lookup.field.acquisition_mode.label": "확보 방식"' not in html
    assert '"operator.lookup.field.signature_mode.label": "싸인 경로"' in html


def test_operator_lookup_includes_sort_mode_filter_field():
    html = read_static_html("index.html")
    assert '<label for="operatorLookupSortMode" data-i18n="operator.lookup.field.sort_mode.label">정렬</label>' in html
    assert '<select id="operatorLookupSortMode">' in html
    assert '<option value="CREATED_DESC" data-i18n="operator.lookup.field.sort_mode.option.created_desc">최신 등록</option>' in html
    assert '<option value="MOVED_DESC" data-i18n="operator.lookup.field.sort_mode.option.moved_desc">최근 이동</option>' in html
    assert '<option value="LOCATION_ASC" data-i18n="operator.lookup.field.sort_mode.option.location_asc">장식장 위치순</option>' in html
    assert '<option value="UNSLOTTED_FIRST" data-i18n="operator.lookup.field.sort_mode.option.unslotted_first">미배치 우선</option>' in html
    assert '"operator.lookup.field.sort_mode.label": "정렬"' in html


def test_operator_lookup_sends_signature_mode_only_when_selected_and_resets_to_any():
    html = read_static_html("index.html")
    ops_lookup_block = html.split("async function loadOperatorLookupResults() {", 1)[1].split("function firstOperatorFormatLine(", 1)[0]
    assert 'const signatureMode = String($("operatorLookupSignatureMode").value || "ANY").trim().toUpperCase() || "ANY";' in ops_lookup_block
    assert 'if (signatureMode !== "ANY") params.set("signature_mode", signatureMode);' in ops_lookup_block
    assert 'operatorLookupAcquisitionMode' not in ops_lookup_block
    assert '$("operatorLookupAcquisitionMode").value = "ANY";' not in html
    assert '$("operatorLookupSignatureMode").value = "ANY";' in html


def test_operator_lookup_sends_sort_mode_only_when_selected_and_resets_to_default():
    html = read_static_html("index.html")
    ops_lookup_block = html.split("async function loadOperatorLookupResults() {", 1)[1].split("function firstOperatorFormatLine(", 1)[0]
    assert 'const sortMode = String($("operatorLookupSortMode").value || "CREATED_DESC").trim().toUpperCase() || "CREATED_DESC";' in ops_lookup_block
    assert 'if (sortMode !== "CREATED_DESC") params.set("sort_mode", sortMode);' in ops_lookup_block
    assert 'await loadOperatorHomeFeed({ kind: operatorFeedKindFromSortMode(sortMode), page: 1 });' in ops_lookup_block
    assert '$("operatorLookupSortMode").value = "CREATED_DESC";' in html


def test_media_search_mobile_flattens_outer_shell_and_softens_preview_selection():
    html = read_static_html("index.html")
    mobile_block = html.split("@media (max-width: 1080px) {", 1)[1].split("    @media (max-width: 760px)", 1)[0]
    assert """#homeSearchCard,
      #adminSearchContextBody {
        border: 0 !important;
        box-shadow: none !important;
        background: transparent !important;
        padding: 0 !important;
      }""" in html
    assert ".home-master-member-preview-item.is-context-selected {" in mobile_block
    assert "border: 0 !important;" in mobile_block
    assert "border-left: 3px solid rgba(15, 118, 110, 0.72);" in mobile_block
    assert "border-radius: 0 !important;" in mobile_block
    assert "box-shadow: none !important;" in mobile_block
    assert "#homeSearchResults .result-item {" in mobile_block
    assert "padding: 4px 5px;" in mobile_block
    assert "border-color: #e2e8f0;" in mobile_block
    assert ".pager {" in mobile_block
    assert "margin: 0 0 4px;" in mobile_block
    assert ".pager-left label {" in mobile_block
    assert "font-size: 0.68rem;" in mobile_block
    assert ".operator-feed-pagebtn {" in mobile_block
    assert "min-width: 28px;" in mobile_block


def test_media_search_phone_compacts_filter_inputs_and_preview_copy():
    html = read_static_html("index.html")
    phone_block = html.split("@media (max-width: 760px) {", 1)[1].split("\n\n  </style>", 1)[0]
    assert ".home-search-grid-top, .home-search-grid-bottom {" in phone_block
    assert "gap: 4px;" in phone_block
    assert ".home-search-grid-bottom {" in phone_block
    assert "margin-top: 4px;" in phone_block
    assert ".home-search-grid-top label," in phone_block
    assert ".home-search-grid-bottom label {" in phone_block
    assert "font-size: 0.68rem;" in phone_block
    assert ".home-search-grid-top input," in phone_block
    assert ".home-search-grid-bottom input {" in phone_block
    assert "min-height: 36px;" in phone_block
    assert "font-size: 0.82rem;" in phone_block
    assert ".home-master-member-preview-title {" in phone_block
    assert "font-size: 0.79rem;" in phone_block
    assert "line-height: 1.22;" in phone_block
    assert ".operator-main {" in phone_block
    assert "gap: 3px;" in phone_block
    assert ".operator-secondary-line {" in phone_block
    assert "gap: 4px 8px;" in phone_block
    assert ".operator-secondary-line-main {" in phone_block
    assert "gap: 4px;" in phone_block
    assert ".operator-meta-line {" in phone_block
    assert "gap: 4px 7px;" in phone_block
    assert "font-size: 0.76rem;" in phone_block
    assert ".home-master-subline {" in phone_block
    assert "font-size: 0.71rem;" in phone_block
    assert ".home-master-location-btn {" in phone_block
    assert "min-height: 22px;" in phone_block
    assert "font-size: 0.64rem;" in phone_block
    assert "padding: 2px 6px;" in phone_block
    assert ".operator-meta-subline {" in phone_block
    assert "font-size: 0.66rem;" in phone_block
    assert "line-height: 1.22;" in phone_block
    assert "color: #94a3b8;" in phone_block


def test_media_search_phone_compacts_heading_line_and_cover_width():
    html = read_static_html("index.html")
    phone_block = html.split("@media (max-width: 760px) {", 1)[1].split("\n\n  </style>", 1)[0]
    assert ".home-master-heading-line {" in phone_block
    assert "gap: 4px;" in phone_block
    assert "align-items: flex-start;" in phone_block
    assert ".home-master-heading {" in phone_block
    assert "font-size: 0.9rem;" in phone_block
    assert ".home-master-source-chip {" in phone_block
    assert "font-size: 0.62rem;" in phone_block
    assert ".home-master-member-preview-cover {" in phone_block
    assert "width: 40px;" in phone_block
    assert "height: 40px;" in phone_block
    assert ".operator-label-chip {" in phone_block
    assert "padding: 1px 6px;" in phone_block
    assert "font-size: 0.68rem;" in phone_block


def test_media_search_phone_compacts_right_context_card_density():
    html = read_static_html("index.html")
    phone_block = html.split("@media (max-width: 760px) {", 1)[1].split("\n\n  </style>", 1)[0]
    assert "#adminSearchContextBody {" in phone_block
    assert "gap: 6px;" in phone_block
    assert ".ops-plugin-section-cards {" in phone_block
    assert "gap: 6px;" in phone_block
    assert ".ops-artist-context-card {" in phone_block
    assert "border-radius: 14px;" in phone_block
    assert "padding: 8px;" in phone_block
    assert "gap: 5px;" in phone_block
    assert ".ops-artist-context-toggle {" in phone_block
    assert "min-height: 22px;" in phone_block
    assert "padding: 0 8px;" in phone_block
    assert "font-size: 0.64rem;" in phone_block
    assert ".ops-artist-context-media {" in phone_block
    assert "border-radius: 10px;" in phone_block
    assert ".ops-artist-context-name {" in phone_block
    assert "font-size: 0.84rem;" in phone_block
    assert ".ops-artist-context-summary {" in phone_block
    assert "font-size: 0.71rem;" in phone_block
    assert ".operator-mini-card {" in phone_block
    assert "padding: 6px 8px;" in phone_block
    assert "border-radius: 12px;" in phone_block
    assert ".operator-mini-list {" in phone_block
    assert "grid-template-columns: 1fr;" in phone_block
    assert ".operator-mini-line {" in phone_block
    assert "font-size: 0.74rem;" in phone_block
    assert "gap: 4px;" in phone_block
    assert ".operator-mini-linkchip {" in phone_block
    assert "min-height: 22px;" in phone_block
    assert "padding: 0 8px;" in phone_block
    assert "font-size: 0.66rem;" in phone_block
    assert ".ops-library-mini-map {" in phone_block
    assert "gap: 4px;" in phone_block
    assert "padding: 6px;" in phone_block
    assert "border-radius: 14px;" in phone_block
    assert ".ops-library-mini-map-head strong {" in phone_block
    assert "font-size: 0.76rem;" in phone_block
    assert ".ops-library-mini-map-head span {" in phone_block
    assert "font-size: 0.56rem;" in phone_block
    assert ".ops-library-mini-map-grid {" in phone_block
    assert "gap: 4px;" in phone_block
    assert ".ops-library-mini-map-floor {" in phone_block
    assert "grid-template-columns: 24px minmax(0, 1fr);" in phone_block
    assert "gap: 4px;" in phone_block
    assert ".ops-library-mini-map-floorcode {" in phone_block
    assert "font-size: 0.58rem;" in phone_block
    assert ".ops-library-mini-map-cells {" in phone_block
    assert "gap: 3px;" in phone_block
    assert ".ops-library-mini-map-cell {" in phone_block
    assert "min-height: 26px;" in phone_block
    assert "padding: 3px 2px;" in phone_block
    assert "border-radius: 8px;" in phone_block
    assert ".ops-library-mini-map-cellcount {" in phone_block
    assert "padding: 1px 4px;" in phone_block
    assert "font-size: 0.64rem;" in phone_block
    assert ".ops-library-mini-map-active-badge {" in phone_block
    assert "padding: 1px 5px;" in phone_block
    assert "font-size: 0.49rem;" in phone_block


def test_dashboard_phone_flattens_cabinet_detail_shell_and_compacts_coverflow_density():
    html = read_static_html("index.html")
    phone_block = html.split("@media (max-width: 760px) {", 1)[1].split("\n\n  </style>", 1)[0]
    assert ".dashboard-slot-map-shell {" in phone_block
    assert "gap: 6px;" in phone_block
    assert "padding: 8px;" in phone_block
    assert "border-radius: 16px;" in phone_block
    assert ".dashboard-slot-map-legend {" in phone_block
    assert "gap: 5px;" in phone_block
    assert ".dashboard-slot-legend-chip {" in phone_block
    assert "gap: 5px;" in phone_block
    assert "padding: 4px 8px;" in phone_block
    assert "font-size: 0.68rem;" in phone_block
    assert ".dashboard-cabinet-detail {" in phone_block
    assert "margin-top: 6px;" in phone_block
    assert "border-top: 0;" in phone_block
    assert "padding-top: 0;" in phone_block
    assert "gap: 6px;" in phone_block
    assert ".dashboard-cabinet-stage {" in phone_block
    assert "gap: 6px;" in phone_block
    assert "padding: 0;" in phone_block
    assert "border: 0;" in phone_block
    assert "border-radius: 0;" in phone_block
    assert "background: transparent;" in phone_block
    assert "box-shadow: none;" in phone_block
    assert ".dashboard-slot-rack-surface {" in phone_block
    assert "gap: 6px;" in phone_block
    assert "min-height: 220px;" in phone_block
    assert "padding: 10px 12px 12px;" in phone_block
    assert "border-radius: 16px;" in phone_block
    assert ".dashboard-slot-sidearrow {" in phone_block
    assert "min-width: 36px;" in phone_block
    assert "min-height: 36px;" in phone_block
    assert "border-radius: 14px;" in phone_block
    assert ".dashboard-slot-sidearrow--left {" in phone_block
    assert "left: 6px;" in phone_block
    assert ".dashboard-slot-sidearrow--right {" in phone_block
    assert "right: 6px;" in phone_block
    assert ".dashboard-slot-surface-tools {" in phone_block
    assert "gap: 6px;" in phone_block
    assert ".dashboard-slot-toolbar-row {" in phone_block
    assert "gap: 8px;" in phone_block
    assert ".dashboard-slot-viewbar {" in phone_block
    assert "gap: 3px;" in phone_block
    assert ".dashboard-slot-viewbtn {" in phone_block
    assert "padding: 2px 7px;" in phone_block
    assert "font-size: 0.64rem;" in phone_block
    assert ".dashboard-slot-pagebar .btn {" in phone_block
    assert "min-width: 34px;" in phone_block
    assert "padding: 3px 6px;" in phone_block
    assert ".dashboard-slot-pagesize {" in phone_block
    assert "min-width: 52px;" in phone_block
    assert "padding: 2px 5px;" in phone_block
    assert "font-size: 0.68rem;" in phone_block
    assert ".dashboard-slot-pageinfo {" in phone_block
    assert "min-width: 88px;" in phone_block
    assert "font-size: 0.7rem;" in phone_block
    assert ".dashboard-slot-actionbtn {" in phone_block
    assert "min-height: 34px;" in phone_block
    assert "padding: 0 8px;" in phone_block
    assert "font-size: 0.6rem;" in phone_block
    assert ".dashboard-workbench-actionbtn {" in phone_block
    assert "min-height: 34px;" in phone_block
    assert "padding: 0 8px;" in phone_block
    assert "font-size: 0.6rem;" in phone_block
    assert ".dashboard-selected-item-meta {" in phone_block
    assert "gap: 8px;" in phone_block
    assert "padding: 6px 8px;" in phone_block
    assert "border-radius: 12px;" in phone_block
    assert "#homeDashSlotItems.dashboard-slot-listview {" in phone_block
    assert "max-height: 400px;" in phone_block
    assert ".dashboard-slot-listitem {" in phone_block
    assert "grid-template-columns: 18px 20px 38px minmax(0, 1fr) auto;" in phone_block
    assert "gap: 5px;" in phone_block
    assert ".dashboard-slot-listitem-cover {" in phone_block
    assert "width: 38px;" in phone_block
    assert "height: 38px;" in phone_block
    assert "#homeDashSlotItems.dashboard-slot-shelfview {" in phone_block
    assert "min-height: 188px;" in phone_block
    assert "padding: 16px 16px 10px 24px;" in phone_block
    assert ".dashboard-slot-shelfcard {" in phone_block
    assert "flex-basis: clamp(96px, 26vw, 116px);" in phone_block
    assert "margin-left: -28px;" in phone_block
    assert "#homeDashSlotItems.dashboard-slot-shelfview--lp .dashboard-slot-shelfcard {" in phone_block
    assert "flex-basis: clamp(104px, 28vw, 122px);" in phone_block
    assert "margin-left: -32px;" in phone_block


def test_dashboard_coverflow_uses_overlay_sidearrows_without_surface_gutters():
    html = read_static_html("index.html")
    sidearrow_block = html.split(".dashboard-slot-sidearrow {", 1)[1].split("}", 1)[0]
    left_block = html.split(".dashboard-slot-sidearrow--left {", 1)[1].split("}", 1)[0]
    right_block = html.split(".dashboard-slot-sidearrow--right {", 1)[1].split("}", 1)[0]
    surface_block = html.split(".dashboard-slot-rack-surface {", 1)[1].split("}", 1)[0]
    assert "position: absolute;" in sidearrow_block
    assert "top: 50%;" in sidearrow_block
    assert "z-index: 3;" in sidearrow_block
    assert "left: 8px;" in left_block
    assert "right: 8px;" in right_block
    assert "padding: 12px 14px 14px;" in surface_block
    assert "background: rgba(255,255,255,0.82);" in sidearrow_block
    assert "color: #475569;" in sidearrow_block
    assert "border: 1px solid rgba(203, 213, 225, 0.92);" in sidearrow_block
    assert "box-shadow: 0 6px 14px rgba(15, 23, 42, 0.08);" in sidearrow_block
    sidearrow_interactive_block = html.split(".dashboard-slot-sidearrow:hover,\n    .dashboard-slot-sidearrow:focus-visible {", 1)[1].split("}", 1)[0]
    assert "background: rgba(255,255,255,0.96);" in sidearrow_interactive_block
    assert "color: #0f172a;" in sidearrow_interactive_block
    assert "border-color: #94a3b8;" in sidearrow_interactive_block
    assert "box-shadow: 0 10px 18px rgba(15, 23, 42, 0.12);" in sidearrow_interactive_block


def test_dashboard_storage_mapping_uses_overlay_nav_without_frame_side_gutters():
    html = read_static_html("index.html")
    frame_block = html.split(".dashboard-slot-grid-frame {", 1)[1].split("}", 1)[0]
    nav_block = html.split(".dashboard-slot-grid-nav {", 1)[1].split("}", 1)[0]
    panel_block = html.split(".dashboard-slot-grid-panel {", 1)[1].split("}", 1)[0]
    assert "position: relative;" in frame_block
    assert "grid-template-columns: minmax(0, 1fr);" in frame_block
    assert "gap: 0;" in frame_block
    assert "position: absolute;" in nav_block
    assert "top: 50%;" in nav_block
    assert "transform: translateY(-50%);" in nav_block
    assert "z-index: 3;" in nav_block
    assert "width: 42px;" in nav_block
    assert "background: rgba(255,255,255,0.82);" in nav_block
    assert "color: #475569;" in nav_block
    assert "border: 1px solid rgba(203, 213, 225, 0.92);" in nav_block
    assert "box-shadow: 0 6px 14px rgba(15, 23, 42, 0.08);" in nav_block
    assert "left: 8px;" in html.split(".dashboard-slot-grid-nav--left {", 1)[1].split("}", 1)[0]
    assert "right: 8px;" in html.split(".dashboard-slot-grid-nav--right {", 1)[1].split("}", 1)[0]
    assert "padding: 0 18px;" in panel_block
    grid_nav_interactive_block = html.split(".dashboard-slot-grid-nav:hover,\n    .dashboard-slot-grid-nav:focus-visible {", 1)[1].split("}", 1)[0]
    assert "background: rgba(255,255,255,0.96);" in grid_nav_interactive_block
    assert "color: #0f172a;" in grid_nav_interactive_block
    assert "border-color: #94a3b8;" in grid_nav_interactive_block
    assert "box-shadow: 0 10px 18px rgba(15, 23, 42, 0.12);" in grid_nav_interactive_block


def test_media_search_member_preview_defines_split_click_targets():
    html = read_static_html("index.html")
    preview_block = html.split("    function homeMasterMemberPreviewHtml(item, options = {}) {", 1)[1].split("    function getHomeMasterVisiblePreviewItems(row) {", 1)[0]
    location_block = html.split("    function homeMasterMemberPreviewLocationHtml(item) {", 1)[1].split("    function homeMasterMemberPreviewMetaLine(item) {", 1)[0]
    assert 'data-home-member-preview-owned-id="' in preview_block
    assert 'data-home-member-preview-select="' in preview_block
    assert 'data-home-open-dashboard-location="' in location_block or 'data-home-member-preview-open-location="' in location_block
    assert 'home-master-member-preview-code' in preview_block
    assert 'escapeHtml(labelId)' in preview_block
    assert 'data-home-preview-edit="' in preview_block
    assert 'data-home-open-detail-manage=' in preview_block
    assert 'data-home-open-owned-editor="' not in preview_block
    assert 'home-master-member-preview-code-btn' not in preview_block


def test_media_search_master_location_buttons_collapse_same_slot_and_label_distinct_items():
    html = read_static_html("index.html")
    helper_block = html.split("    function homeMasterLocationButtonsHtml(row) {", 1)[1].split("    function homeMasterMemberPreviewLocationHtml(item) {", 1)[0]
    result_block = html.split("    function homeResultItemHtml(row) {", 1)[1].split("    function renderHomeSearchResults(items) {", 1)[0]
    assert "const actions = Array.isArray(row?.member_location_actions)" in helper_block
    assert "const distinctLocationKeys = new Set(actions.map((item) => {" in helper_block
    assert "const hasMultipleLocations = distinctLocationKeys.size > 1;" in helper_block
    assert "const dedupedActions = [];" in helper_block
    assert "if (!hasMultipleLocations && seenLocationKeys.has(locationKey)) return;" in helper_block
    assert 'const itemCode = String(item.label_id || "").trim();' in helper_block
    assert 'const itemLabel = String(item.item_label || "").trim();' in helper_block
    assert "const itemDescriptor = itemCode || itemLabel;" in helper_block
    assert 'const buttonLabel = hasMultipleLocations && itemDescriptor' in helper_block
    assert '`${itemDescriptor} · ${label}`' in helper_block
    assert "const locationButtons = homeMasterLocationButtonsHtml(row);" in result_block
    assert 'row.member_location_actions.filter' not in result_block


def test_media_search_member_preview_keeps_inline_editor_out_of_full_manage_surfaces():
    html = read_static_html("index.html")
    preview_block = html.split("    function homeMasterMemberPreviewHtml(item, options = {}) {", 1)[1].split("    function getHomeMasterVisiblePreviewItems(row) {", 1)[0]
    assert 'home-master-member-preview-actions' in preview_block
    assert 'data-home-preview-edit="' in preview_block
    assert 'class="btn tiny" type="button" data-home-preview-edit="' in preview_block
    assert 'class="btn ghost tiny home-master-member-preview-detail-btn" type="button" data-home-open-detail-manage="' in preview_block
    assert 'home-master-member-preview-code' in preview_block
    # First-pass inline edit should not expose full editor surfaces in the row panel.
    assert 'id="homeEditProductBlock"' not in preview_block
    assert 'id="homeEditMusicBox"' not in preview_block
    assert 'id="homeEditGoodsBox"' not in preview_block
    assert 'id="homeMasterInlineEditorHost"' not in preview_block
    # Row-level quick edit should stay separate from the full manage surface.
    assert 'id="editStatus"' not in preview_block
    assert 'id="editSignatureType"' not in preview_block
    assert 'id="editMemoryNote"' not in preview_block
    assert 'home-master-member-preview-code-btn' not in preview_block


def test_media_search_member_preview_uses_compact_collector_meta_pairs():
    html = read_static_html("index.html")
    meta_block = html.split("    function homeMasterMemberPreviewMetaLine(item) {", 1)[1].split("    function mediaSearchMemberPreviewCoverSrc(item) {", 1)[0]
    preview_block = html.split("    function homeMasterMemberPreviewHtml(item, options = {}) {", 1)[1].split("    function getHomeMasterVisiblePreviewItems(row) {", 1)[0]
    assert 'operatorMetaPairHtml(t("operator.feed.meta.summary.release"), releaseDate)' in meta_block
    assert 'operatorMetaPairHtml(t("operator.feed.meta.summary.country"), releaseCountry)' in meta_block
    assert 'operatorMetaPairHtml(t("operator.feed.meta.summary.label"), labelCatalogText)' in meta_block
    assert 'operatorMetaPairHtml(t("operator.feed.meta.summary.format"), formatSummary)' in meta_block
    assert "parts.join('<span class=\"operator-meta-separator\">/</span>')" in meta_block
    assert '<div class="operator-meta-line">${collectorMetaHtml}</div>' in preview_block
    assert '<div class="operator-meta-line"><span>${escapeHtml(collectorMetaLine || "-")}</span></div>' not in preview_block


def test_media_search_member_preview_uses_subtle_runout_tone():
    html = read_static_html("index.html")
    preview_block = html.split("    function homeMasterMemberPreviewHtml(item, options = {}) {", 1)[1].split("    function getHomeMasterVisiblePreviewItems(row) {", 1)[0]
    css_block = html.split(".home-master-member-preview-detail-btn {", 1)[1].split(".media-search-inline-editor {", 1)[0]
    phone_block = html.split("@media (max-width: 760px) {", 1)[1].split("      .ops-plugin-section-cards {", 1)[0]
    assert 'class="operator-meta-subline home-master-member-preview-runout"' in preview_block
    assert ".home-master-member-preview-runout {" in css_block
    assert "font-size: 0.64rem;" in css_block
    assert "color: #94a3b8;" in css_block
    assert ".home-master-member-preview-runout {" in phone_block
    assert "font-size: 0.62rem;" in phone_block


def test_media_search_single_master_item_uses_member_row_actions():
    single_item_row_html = render_media_search_result_card_html({
        "id": 101,
        "title": "Single master",
        "heading": "Single master",
        "source_code": "DISCOGS",
        "member_count": 1,
        "matched_track_preview": [],
        "member_items_preview": [
            {"owned_item_id": 9001, "title": "A-side", "artist": "A", "label_id": "LP-000123"},
        ],
    })
    multi_item_row_html = render_media_search_result_card_html({
        "id": 102,
        "title": "Multi master",
        "heading": "Multi master",
        "source_code": "DISCOGS",
        "member_count": 2,
        "matched_track_preview": [],
        "member_items_preview": [
            {"owned_item_id": 9001, "title": "A-side", "artist": "A", "label_id": "LP-000123"},
            {"owned_item_id": 9002, "title": "B-side", "artist": "B", "label_id": "LP-000124"},
        ],
    })
    assert 'LP-000123' in single_item_row_html
    assert 'LP-000124' in multi_item_row_html
    assert 'home-master-member-preview-code' in single_item_row_html
    assert 'home-master-member-preview-code' in multi_item_row_html
    assert 'data-home-preview-edit="' in single_item_row_html
    assert 'data-home-open-detail-manage=' in single_item_row_html
    assert "LP-000123" in single_item_row_html
    assert 'data-home-open-owned-editor="' not in single_item_row_html
    assert 'data-home-open-manage="' not in single_item_row_html
    assert 'home-master-member-preview-code-btn' not in single_item_row_html
    assert 'data-home-preview-edit="' in multi_item_row_html
    assert 'data-home-open-detail-manage=' in multi_item_row_html
    assert "LP-000123" in multi_item_row_html
    assert "LP-000124" in multi_item_row_html
    assert 'data-home-open-manage="' not in multi_item_row_html
    assert 'home-master-member-preview-code-btn' not in multi_item_row_html
    assert 'data-home-member-preview-select="9001"' in single_item_row_html
    assert 'data-home-member-preview-select="9002"' in multi_item_row_html


def test_media_search_member_preview_shows_per_item_cover_for_multi_item_masters():
    html = read_static_html("index.html")
    preview_block = html.split("    function homeMasterMemberPreviewHtml(item, options = {}) {", 1)[1].split("    function getHomeMasterVisiblePreviewItems(row) {", 1)[0]
    result_block = html.split("    function homeResultItemHtml(row) {", 1)[1].split("    function homeVariantResultHtml(row) {", 1)[0]
    cover_css = html.split(".home-master-member-preview-cover {", 1)[1].split("}", 1)[0]
    assert "const showCover = Boolean(options?.showCover);" in preview_block
    assert "home-master-member-preview-cover" in preview_block
    assert 'allMemberItemsPreview.length > 1' in result_block
    assert '.map((item) => homeMasterMemberPreviewHtml(item, { showCover: showMemberPreviewCover, masterSourceCode: sourceCode }))' in result_block


def test_media_search_member_preview_uses_discogs_cover_preview_route_for_discogs_items():
    html = read_static_html("index.html")
    helper_block = html.split("    function mediaSearchMemberPreviewCoverSrc(item) {", 1)[1].split("    function homeMasterMemberPreviewHtml(item, options = {}) {", 1)[0]
    preview_block = html.split("    function homeMasterMemberPreviewHtml(item, options = {}) {", 1)[1].split("    function getHomeMasterVisiblePreviewItems(row) {", 1)[0]
    assert 'const sourceCode = normalizeSourceCode(item?.source_code);' in helper_block
    assert 'const sourceExternalId = String(item?.source_external_id || "").trim();' in helper_block
    assert "const coverUrl = mediaSearchMemberPreviewCoverSrc(item);" in preview_block


def test_media_search_master_cards_place_source_chip_before_heading_and_remove_member_count_and_empty_location_copy():
    html = read_static_html("index.html")
    result_block = html.split("    function homeResultItemHtml(row) {", 1)[1].split("    function renderHomeSearchResults(items) {", 1)[0]
    assert 'const sourceChip = `<span class="tag home-master-source-chip">${escapeHtml(sourceCode)}</span>`;' in result_block
    assert '<div class="home-master-heading-line">' in result_block
    assert '${sourceChip}' in result_block
    assert 't("media.manage.search.member_count"' not in result_block
    assert 't("media.manage.search.location_empty")' not in result_block
    assert '${locationButtons}' in result_block


def test_media_search_result_card_primary_manage_cta():
    html = read_static_html("index.html")
    result_block = html.split("    function homeResultItemHtml(row) {", 1)[1].split("    function renderHomeSearchResults(items) {", 1)[0]
    location_block = html.split("    function homeMasterLocationButtonsHtml(row) {", 1)[1].split("    function homeMasterMemberPreviewLocationHtml(item) {", 1)[0]
    preview_block = html.split("    function homeMasterMemberPreviewHtml(item, options = {}) {", 1)[1].split("    function getHomeMasterVisiblePreviewItems(row) {", 1)[0]
    click_block = html.split('    $("homeSearchResults").addEventListener("click", async (e) => {', 1)[1].split('    $("homeDashSlotGrid").addEventListener("click", async (e) => {', 1)[0]
    assert 'data-i18n="media.manage.search.action.open_manage"' not in result_block
    assert 'data-home-open-manage="${row.id}"' not in result_block
    assert 'home-master-manage-btn' not in result_block
    assert 'data-home-preview-edit=' in preview_block
    assert 't("common.action.edit_item")' in preview_block
    assert 'data-home-open-detail-manage=' in preview_block
    assert 't("media.manage.search.action.open_detail_manage")' in preview_block
    assert 'data-home-open-owned-editor=' not in preview_block
    assert 'home-master-member-preview-code-btn' not in preview_block
    assert 'data-home-toggle-member-preview' in result_block
    assert 'home-master-member-preview-more' in result_block
    assert 'home-master-member-preview-toggle' in result_block
    assert 'const locationButtons = homeMasterLocationButtonsHtml(row);' in result_block
    assert ('data-home-open-dashboard-location=' in location_block) or ('data-home-member-preview-open-location="' in location_block)
    assert 'const repairDiscogsMasterBtn = discogsRepairSlotHtml("home", {' in preview_block
    assert 'data-home-member-preview-select' in click_block

def test_media_search_member_rows_use_per_master_inline_editor_state_contract():
    html = read_static_html("index.html")
    assert 'const mediaSearchExpandedPreviewByMaster = new Map();' in html
    assert 'mediaSearchExpandedPreviewByMaster.set(String(masterId), nextOwnedItemId);' in html
    assert 'mediaSearchExpandedPreviewByMaster.get(String(masterId))' in html
    assert 'mediaSearchExpandedPreviewByMaster.delete(String(masterId))' in html
    assert 'mediaSearchExpandedPreviewByMaster.clear()' not in html


def test_media_search_master_cards_gate_discogs_repair_button_on_eligibility():
    html = read_static_html("index.html")
    preview_block = html.split("    function homeMasterMemberPreviewHtml(item, options = {}) {", 1)[1].split("    function getHomeMasterVisiblePreviewItems(row) {", 1)[0]
    result_block = html.split("    function homeResultItemHtml(row) {", 1)[1].split("    function renderHomeSearchResults(items) {", 1)[0]
    assert 'const repairDiscogsMasterBtn = discogsRepairSlotHtml("home", {' in preview_block
    assert 'const repairDiscogsMasterBtn = e.target.closest("[data-home-repair-discogs-master]");' in html
    assert 'homeMasterMemberPreviewHtml(item, { showCover: showMemberPreviewCover, masterSourceCode: sourceCode })' in result_block
    assert 'function discogsRepairSlotHtml(scope, { ownedItemId, sourceCode, masterSourceCode, sourceExternalId }) {' in html
    assert 'data-home-discogs-repair-slot="${id}"' in html
    assert '/discogs-repair-status' in html
    assert ".home-master-member-preview-repair-btn {" in html


def test_media_search_inline_editor_uses_quick_edit_copy_and_compact_header():
    html = read_static_html("index.html")
    editor_block = html.split("    function renderMediaSearchInlineEditor(masterId, item) {", 1)[1].split("    async function loadMediaSearchInlineEditorDetail(ownedItemId) {", 1)[0]
    css_block = html.split(".media-search-inline-editor {", 1)[1].split(".home-master-member-preview-more {", 1)[0]
    assert 't("media.manage.search.inline_editor.kicker")' in editor_block
    assert 'media-search-inline-editor-copy' in editor_block
    assert '.media-search-inline-editor-copy {' in css_block
    assert '.media-search-inline-editor-kicker {' in css_block
    assert '.home-master-member-preview-detail-btn {' in html


def test_media_search_inline_editor_exposes_extended_operational_fields():
    html = read_static_html("index.html")
    editor_block = html.split("    function renderMediaSearchInlineEditor(masterId, item) {", 1)[1].split("    async function loadMediaSearchInlineEditorDetail(ownedItemId) {", 1)[0]
    assert 'data-media-search-inline-domain-field="${ownedItemId}"' in editor_block
    assert 'data-media-search-inline-preferred-size-field="${ownedItemId}"' in editor_block
    assert 'data-media-search-inline-purchase-price-field="${ownedItemId}"' in editor_block
    assert 'data-media-search-inline-currency-field="${ownedItemId}"' in editor_block
    assert 'data-media-search-inline-cover-condition-field="${ownedItemId}"' in editor_block
    assert 'data-media-search-inline-disc-condition-field="${ownedItemId}"' in editor_block
    assert 'data-media-search-inline-has-obi-field="${ownedItemId}"' in editor_block
    assert 't("media.manage.product.field.domain_code.label")' in editor_block
    assert 't("common.meta.storage_size")' in editor_block
    assert 't("media.manage.product.field.purchase_price.label")' in editor_block
    assert 't("media.manage.product.field.currency_code.label")' in editor_block
    assert 't("media.manage.product.field.cover_condition.label")' in editor_block
    assert 't("media.manage.product.field.disc_condition.label")' in editor_block
    assert 't("media.manage.product.field.has_obi.label")' in editor_block


def test_media_search_inline_editor_save_reads_extended_operational_fields():
    html = read_static_html("index.html")
    payload_block = html.split("    function buildMediaSearchInlineEditorPayload(detail, overrides = {}) {", 1)[1].split("    function mediaSearchInlineEditorStatusOptionsHtml(selectedValue) {", 1)[0]
    save_block = html.split("    async function saveMediaSearchInlineEditor(masterId, ownedItemId) {", 1)[1].split("    function normalizeHomeSearchResultItem(row) {", 1)[0]
    assert "domain_code: overrides.domain_code !== undefined" in payload_block
    assert "preferred_storage_size_group: overrides.preferred_storage_size_group !== undefined" in payload_block
    assert "purchase_price: overrides.purchase_price !== undefined" in payload_block
    assert "currency_code: overrides.currency_code !== undefined" in payload_block
    assert "payload.music_detail.cover_condition = overrides.cover_condition !== undefined" in payload_block
    assert "payload.music_detail.disc_condition = overrides.disc_condition !== undefined" in payload_block
    assert "payload.music_detail.has_obi = overrides.has_obi !== undefined" in payload_block
    assert 'const domainField = document.querySelector(`[data-media-search-inline-domain-field="${cacheKey}"]`);' in save_block
    assert 'const preferredSizeField = document.querySelector(`[data-media-search-inline-preferred-size-field="${cacheKey}"]`);' in save_block
    assert 'const purchasePriceField = document.querySelector(`[data-media-search-inline-purchase-price-field="${cacheKey}"]`);' in save_block
    assert 'const currencyField = document.querySelector(`[data-media-search-inline-currency-field="${cacheKey}"]`);' in save_block
    assert 'const coverConditionField = document.querySelector(`[data-media-search-inline-cover-condition-field="${cacheKey}"]`);' in save_block
    assert 'const discConditionField = document.querySelector(`[data-media-search-inline-disc-condition-field="${cacheKey}"]`);' in save_block
    assert 'const hasObiField = document.querySelector(`[data-media-search-inline-has-obi-field="${cacheKey}"]`);' in save_block
    assert "domain_code: nextDomainCode," in save_block
    assert "preferred_storage_size_group: nextPreferredSizeGroup," in save_block
    assert "purchase_price: nextPurchasePrice," in save_block
    assert "currency_code: nextCurrencyCode," in save_block
    assert "cover_condition: nextCoverCondition," in save_block
    assert "disc_condition: nextDiscCondition," in save_block
    assert "has_obi: nextHasObi," in save_block


def test_media_search_click_handler_routes_code_location_and_preview_selection():
    html = read_static_html("index.html")
    click_block = html.split('    $("homeSearchResults").addEventListener("click", async (e) => {', 1)[1].split('    $("homeDashSlotGrid").addEventListener("click", async (e) => {', 1)[0]
    assert '[data-home-preview-edit]' in click_block
    assert '[data-home-open-detail-manage]' in click_block
    assert '[data-home-member-preview-select]' in click_block
    preview_edit_index = click_block.index('[data-home-preview-edit]')
    detail_manage_index = click_block.index('[data-home-open-detail-manage]')
    preview_select_index = click_block.index('[data-home-member-preview-select]')
    assert preview_edit_index < detail_manage_index < preview_select_index
    preview_edit_if = click_block.rfind("if (", 0, detail_manage_index)
    detail_manage_if = click_block.rfind("if (", preview_edit_if + 1, preview_select_index)
    assert preview_edit_if >= 0 and detail_manage_if >= 0
    edit_handler_block = click_block[preview_edit_if:detail_manage_if]
    detail_handler_block = click_block[detail_manage_if:preview_select_index]
    select_handler_block = click_block[preview_select_index:]
    assert 'setMediaSearchContextSelectionByOwnedItem(ownedItemId);' in select_handler_block
    assert 'setMediaSearchContextSelectionByOwnedItem(ownedItemId);' not in edit_handler_block
    assert 'setMediaSearchContextSelectionByOwnedItem(ownedItemId);' not in detail_handler_block
    assert 'getAttribute("data-home-preview-edit")' in edit_handler_block
    assert 'getAttribute("data-home-open-detail-manage")' not in edit_handler_block
    assert 'getAttribute("data-home-open-detail-manage")' in detail_handler_block
    assert 'getAttribute("data-home-preview-edit")' not in detail_handler_block
    assert 'return;' in edit_handler_block
    assert 'return;' in detail_handler_block
    assert 'e.stopPropagation()' in click_block


def test_media_search_context_click_handler_routes_manage_and_clear_actions():
    html = read_static_html("index.html")
    handler_block = html.split("    async function handleMediaSearchContextAction(e) {", 1)[1].split('    document.addEventListener("click", (e) => {', 1)[0]
    assert 'const clearBtn = e.target.closest("[data-media-search-context-clear]");' in handler_block
    assert 'mediaSearchSelectedContextItem = null;' in handler_block


def test_media_search_detail_manage_keeps_master_context_and_focuses_structural_section():
    html = read_static_html("index.html")
    open_block = html.split("    async function openMediaSearchDetailManage(masterId, ownedItemId) {", 1)[1].split("    function findOpsLibraryContextCabinet(item) {", 1)[0]
    helper_block = html.split("    function ensureHomeManageStructuralSectionVisible() {", 1)[1].split("    function resolveHomeLinkedCollectiblesMasterId() {", 1)[0]
    assert "await loadHomeItemForEdit(targetOwnedItemId, {" in open_block
    assert "keepMasterContext: targetMasterId > 0," in open_block
    assert "resetMasterLookupUi: false," in open_block
    assert "ensureHomeManageStructuralSectionVisible();" in open_block
    assert '$("homeMasterFetchDetails")?.setAttribute("open", "");' in helper_block
    assert '$("homeMasterLookupResultsDetails")?.removeAttribute("open");' in helper_block


def test_media_search_click_handler_does_not_open_master_from_card_background():
    html = read_static_html("index.html")
    click_block = html.split('    $("homeSearchResults").addEventListener("click", async (e) => {', 1)[1].split('    $("homeDashSlotGrid").addEventListener("click", async (e) => {', 1)[0]
    assert 'const row = e.target.closest(".result-item.album-result");' not in click_block
    assert '[data-home-open-manage]' not in click_block
    assert '[data-home-open-detail-manage]' in click_block


def test_media_search_click_handler_routes_discogs_master_repair_action():
    html = read_static_html("index.html")
    click_block = html.split('    $("homeSearchResults").addEventListener("click", async (e) => {', 1)[1].split('    $("homeDashSlotGrid").addEventListener("click", async (e) => {', 1)[0]
    assert 'const repairDiscogsMasterBtn = e.target.closest("[data-home-repair-discogs-master]");' in click_block
    assert 'const ownedItemId = Number(repairDiscogsMasterBtn.getAttribute("data-home-repair-discogs-master") || 0);' in click_block
    assert 'await fetchWithRetry(`/owned-items/${ownedItemId}/repair-discogs-master-link`, { method: "POST" }, {' in click_block
    assert 'await homeSearchOwnedItems({ allowPageAdjust: false });' in click_block


def test_ops_home_context_panel_keeps_mini_map_head_on_one_line():
    html = read_static_html("index.html")
    head_block = html.split(".ops-library-mini-map-head {", 1)[1].split("}", 1)[0]
    span_block = html.split(".ops-library-mini-map-head span {", 1)[1].split("}", 1)[0]
    assert "gap: 4px;" in head_block
    assert "flex-wrap: nowrap;" in head_block
    assert "font-size: 0.6rem;" in span_block
    assert "white-space: nowrap;" in span_block
    assert "letter-spacing: -0.01em;" in span_block


def test_ops_home_context_panel_unifies_secondary_card_tone():
    html = read_static_html("index.html")
    weather_block = html.split(".operator-weather-card {", 1)[1].split("}", 1)[0]
    map_block = html.split(".ops-library-mini-map {", 1)[1].split("}", 1)[0]
    preview_block = html.split(".ops-library-slot-preview {", 1)[1].split("}", 1)[0]
    assert "border-radius: 18px;" in weather_block
    assert "border-radius: 18px;" in map_block
    assert "border-radius: 18px;" in preview_block
    assert "border-color: #dce7e1;" in weather_block
    assert "border-color: #dce7e1;" in map_block
    assert "border-color: #dce7e1;" in preview_block


def test_ops_home_context_panel_fixes_slot_preview_label_height():
    html = read_static_html("index.html")
    label_block = html.split(".ops-library-slot-preview-label {", 1)[1].split("}", 1)[0]
    assert "display: block;" in label_block
    assert "height: 1.32em;" in label_block


def test_ops_home_context_panel_uses_link_style_for_open_cabinet_action():
    html = read_static_html("index.html")
    link_block = html.split(".operator-mini-linkchip {", 1)[1].split("}", 1)[0]
    selection_block = html.split("function renderOpsLibraryContextSelection(item) {", 1)[1].split("function findOpsLibraryContextCabinetGroup(item) {", 1)[0]
    assert "min-height: 24px;" in link_block
    assert "border-radius: 999px;" in link_block
    assert "font-weight: 700;" in link_block
    assert 'class="operator-mini-linkchip"' in selection_block


def test_ops_home_context_panel_compacts_mini_map_floor_label_width():
    html = read_static_html("index.html")
    floor_block = html.split(".ops-library-mini-map-floor {", 1)[1].split("}", 1)[0]
    floorcode_block = html.split(".ops-library-mini-map-floorcode {", 1)[1].split("}", 1)[0]
    assert "grid-template-columns: 30px minmax(0, 1fr);" in floor_block
    assert "font-size: 0.62rem;" in floorcode_block



def test_index_admin_hero_moves_docs_to_upper_right_and_removes_metric_chips():
    html = read_static_html("index.html")
    hero_start = '<header id="appHero" class="hero admin-shell-hero">'
    ops_start = '    <section id="opsHomeHero" class="ops-home-hero" style="display:none;">'
    assert hero_start in html
    assert ops_start in html
    block = html.split(hero_start, 1)[1].split(ops_start, 1)[0]
    assert 'class="admin-shell-metrics"' not in block
    assert 'LP Archive' not in block
    assert 'CD Library' not in block
    assert 'Storage Mapping' not in block
    assert 'class="admin-shell-hero-side"' in block
    hero_head = block.split('<div class="admin-shell-hero-head">', 1)[1].split('<div class="shell-header-row admin-shell-row">', 1)[0]
    assert '<details class="hero-docs admin-shell-docs">' not in hero_head
    assert '<summary data-i18n="shell.admin.docs_summary">문서 / ERD / 활용 매뉴얼</summary>' not in hero_head
    side_block = block.split('<div class="admin-shell-hero-side">', 1)[1].split('</div>\n        </div>\n        <div class="shell-header-row admin-shell-row">', 1)[0]
    assert 'id="adminUtilityMount"' in side_block
    assert 'class="admin-shell-hero-art"' in side_block
    assert side_block.index('id="adminUtilityMount"') < side_block.index('class="admin-shell-hero-art"')
    row_block = block.split('<div class="shell-header-row admin-shell-row">', 1)[1].split('</div>\n      </div>\n    </header>', 1)[0]
    assert 'id="adminUtilityMount"' not in row_block
    assert 'id="adminUtilityMainMount"' in row_block


def test_index_ops_home_hero_removes_quick_focus_chips():
    html = read_static_html("index.html")
    ops_start = '    <section id="opsHomeHero" class="ops-home-hero" style="display:none;">'
    utility_start = '    <div id="shellUtilityBar" class="shell-utility" style="display:none;">'
    assert ops_start in html
    assert utility_start in html
    block = html.split(ops_start, 1)[1].split(utility_start, 1)[0]
    assert 'class="ops-home-focus-chips"' not in block
    assert 'id="opsHomeSearchFocusValue"' not in block
    assert 'id="opsHomeLocationValue"' not in block
    assert 'id="opsHomeRecentMoveValue"' not in block
    assert 'id="opsHomeRecentRegistrationValue"' not in block


def test_index_operator_home_search_uses_curator_shell_markup():
    html = read_static_html("index.html")
    assert 'id="opsHomeLayout"' in html
    assert 'class="ops-home-layout operator-shell"' in html
    assert 'id="opsLibraryContextPanel"' in html
    assert 'id="opsLibraryContextClimate"' in html
    assert 'id="opsLibraryContextBody"' in html
    assert '<section class="card operator-home-card">' in html
    assert 'class="operator-search-shell"' in html
    assert 'class="operator-search-actions"' in html
    assert 'class="ops-home-main operator-shell-main"' in html
    assert 'class="ops-library-context-panel operator-shell-sidebar"' in html
    assert 'id="operatorLookupQuery"' in html
    assert 'id="operatorLookupBtn"' in html
    assert 'id="operatorFeedRegisteredBtn"' not in html
    assert 'id="operatorFeedMovedBtn"' not in html
    assert 'id="operatorFeedPager"' in html
    assert 'id="operatorWeatherStatus"' in html
    assert 'id="operatorWeatherTemperature"' in html
    assert 'id="operatorWeatherHumidity"' in html


def test_index_ops_home_reuses_default_main_and_context_column_ratio():
    html = read_static_html("index.html")
    assert ".operator-shell,\n    .ops-home-layout {\n      display: grid;\n      grid-template-columns: minmax(0, 3fr) minmax(280px, 2fr);" in html
    assert ".ops-home-layout {\n      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);\n    }" not in html


def test_index_home_search_uses_same_numeric_pager_pattern_as_operator_feed():
    html = read_static_html("index.html")
    assert 'id="homeSearchPager"' in html
    assert 'id="homeSearchPagerBottom"' in html
    assert 'id="operatorFeedPagerBottom"' in html
    assert 'id="homePagePrevBtn"' not in html
    assert 'id="homePageNextBtn"' not in html
    assert 'id="homePageInfo"' not in html
    assert 'id="homeSearchPagerBottom"' in html
    assert "const pagers = [$(\"homeSearchPager\"), $(\"homeSearchPagerBottom\")].filter(Boolean);" in html
    assert "const pagers = [$(\"operatorFeedPager\"), $(\"operatorFeedPagerBottom\")].filter(Boolean);" in html
    assert "const tokens = buildOperatorFeedPagerTokens(homeSearchPage, totalPages);" in html
    assert 'data-home-search-page="${homeSearchPage - 1}"' in html
    assert '$("homeSearchPager").addEventListener("click", (e) => {' in html
    assert '$("homeSearchPagerBottom").addEventListener("click", (e) => {' in html
    assert '$("operatorFeedPager").addEventListener("click", (e) => {' in html
    assert '$("operatorFeedPagerBottom").addEventListener("click", (e) => {' in html


def test_index_admin_dashboard_removes_secondary_grid_after_source_summary_moves_into_hero():
    html = read_static_html("index.html")
    main_grid = '<div class="dashboard-main-grid">'
    status = '<div id="homeDashboardStatus" class="status"></div>'
    assert main_grid in html
    assert '<div class="dashboard-secondary-grid">' not in html
    assert status in html
    assert html.index(main_grid) < html.index(status)


def test_index_operator_home_weather_panel_uses_office_climate_without_public_weather_fallback():
    html = read_static_html("index.html")
    assert "async function loadOperatorWeather(force = false)" in html
    assert 'fetch("/operator/office-climate")' in html
    assert "function renderOpsLibraryContextDefault(climate)" in html
    assert "function formatOpsCollectorFormatItem(row)" in html
    assert "return formatFormatItem(row);" in html
    assert 'setTextIfPresent("operatorWeatherKicker", t("operator.weather.office.kicker"))' in html
    assert 'setTextIfPresent("operatorWeatherSecondaryLabel", t("operator.weather.office.secondary"))' in html
    assert 'setTextIfPresent("operatorWeatherLocation", t("operator.weather.office.location"))' in html
    assert "navigator.geolocation" not in html
    assert "https://api.open-meteo.com/v1/forecast" not in html
    assert 'return kind === "moved" ? t("operator.feed.filter.moved") : t("operator.feed.filter.registered");' in html
    assert 'setTextIfPresent("operatorWeatherHumidity"' in html
    assert 'setTextIfPresent("operatorWeatherTemperature"' in html


def test_index_dashboard_slot_panel_adds_mapping_legend():
    html = read_static_html("index.html")
    assert 'class="dashboard-slot-map-shell"' in html
    assert 'class="dashboard-slot-map-legend"' in html
    assert "LP zone" in html
    assert "CD zone" in html
    assert "여유 슬롯" in html
    assert 'dashboard-slot-legend-chip size-lp' in html
    assert 'dashboard-slot-legend-chip size-book' in html
    assert 'dashboard-slot-legend-chip size-oversize' in html
    assert 'dashboard-slot-legend-chip size-cassette' in html
    assert 'dashboard-slot-legend-chip size-goods' in html


def test_index_ops_cabinet_form_supports_safe_edit_mode():
    html = read_static_html("index.html")
    assert 'id="opsCabinetSelectedName"' in html
    assert 'id="opsCabinetModeHint"' in html
    assert 'id="opsCabinetGroupName"' in html
    assert 'id="opsCabinetGroupOrder"' in html
    assert 'id="opsCabinetSlotCapacityMm"' in html
    assert "function setOpsCabinetFormMode(summary = null)" in html
    assert "function fillOpsCabinetForm(summary)" in html
    assert '$("opsCabinetSaveBtn").textContent = isEditMode ? t("ops.cabinet.action.update") : t("ops.cabinet.action.save");' in html
    assert '$("opsCabinetName").disabled = isEditMode;' in html
    assert '$("opsCabinetSizeGroup").disabled = isEditMode;' in html
    assert '$("opsCabinetFloorStart").disabled = isEditMode;' in html
    assert '$("opsCabinetCellStart").disabled = isEditMode;' in html


def test_index_ops_cabinet_row_click_prefills_full_form_and_enters_edit_mode():
    html = read_static_html("index.html")
    start = '$("opsCabinetTableBody").addEventListener("click", (e) => {'
    end = '    $("opsAuthTableBody").addEventListener("click", (e) => {'
    assert start in html
    assert end in html
    block = html.split(start, 1)[1].split(end, 1)[0]
    assert "const summary = getOpsCabinetSummary(cabinetName);" in block
    assert "fillOpsCabinetForm(summary);" in block
    assert 'setStatus("opsCabinetStatus", "ok", t("ops.cabinet.status.selected", { cabinet: cabinetName }));' in block


def test_index_ops_cabinet_save_blocks_unsafe_shrink_and_start_changes_in_edit_mode():
    html = read_static_html("index.html")
    start = "    async function saveOpsStorageCabinet() {"
    end = "    async function deleteOpsStorageCabinet() {"
    assert start in html
    assert end in html
    block = html.split(start, 1)[1].split(end, 1)[0]
    assert 'const selectedCabinetName = $("opsCabinetSelectedName").value.trim();' in block
    assert "const currentSummary = selectedCabinetName ? getOpsCabinetSummary(selectedCabinetName) : null;" in block
    assert "if (currentSummary && !currentSummary.can_safe_edit)" in block
    assert 'if (payload.floor_start !== currentSummary.floor_start || payload.cell_start !== currentSummary.cell_start)' in block
    assert 'if (payload.floor_count < currentSummary.floor_count || payload.cell_count < currentSummary.cell_count)' in block
    assert 'if (payload.allowed_size_group !== currentSummary.size_group_code)' in block
    assert 'max_thickness_mm: Number($("opsCabinetSlotCapacityMm").value || 0),' in block
    assert 'setStatus("opsCabinetStatus", "ok", currentSummary ? t("ops.cabinet.status.saving_update") : t("ops.cabinet.status.saving_create"));' in block




def test_index_ops_cabinet_form_exposes_recommended_slot_capacity_defaults_by_size_group():
    html = read_static_html("index.html")
    assert 'function recommendedCabinetSlotCapacityMm(sizeGroup)' in html
    assert 'STD: 142,' in html
    assert 'BOOK: 320,' in html
    assert 'LP: 360,' in html
    assert 'LP10: 300,' in html
    assert 'LP7: 200,' in html
    assert 'OVERSIZE: 520,' in html
    assert 'CASSETTE: 142,' in html
    assert '"8TRACK": 142,' in html
    assert '"REEL_TO_REEL": 320,' in html
    assert 'GOODS: 220,' in html


def test_index_size_group_selects_expose_10inch_7inch_cassette_and_tape_options():
    html = read_static_html("index.html")
    assert '<option value="LP10" data-i18n="common.size_group.lp10">10인치</option>' in html
    assert '<option value="LP7" data-i18n="common.size_group.lp7">7인치</option>' in html
    assert '<option value="CASSETTE" data-i18n="common.size_group.cassette">카세트</option>' in html
    assert '<option value="8TRACK" data-i18n="common.size_group.8track">8-track</option>' in html
    assert '<option value="REEL_TO_REEL" data-i18n="common.size_group.reel_to_reel">Reel-to-reel</option>' in html


def test_index_default_size_group_for_cassette_category_is_cassette():
    html = read_static_html("index.html")
    block = html.split("    function defaultSizeGroupForCategory(category) {", 1)[1].split("    function quickDefaultSizeGroup(category) {", 1)[0]
    assert 'if (c === "CASSETTE") return "CASSETTE";' in block
    assert 'if (c === "8TRACK") return "8TRACK";' in block
    assert 'if (c === "REEL_TO_REEL") return "REEL_TO_REEL";' in block


def test_index_dashboard_size_group_label_includes_tape_formats():
    html = read_static_html("index.html")
    block = html.split("    function dashboardSizeGroupLabel(value) {", 1)[1].split("    function dashboardSourceLabel(value) {", 1)[0]
    assert 'if (code === "8TRACK") return "8-track";' in block
    assert 'if (code === "REEL_TO_REEL") return "Reel-to-reel";' in block


def test_index_ops_cabinet_size_group_change_autofills_empty_slot_capacity_without_overwriting_manual_value():
    html = read_static_html("index.html")
    assert 'function maybeAutofillOpsCabinetSlotCapacity(force = false)' in html
    assert 'const currentValue = String($("opsCabinetSlotCapacityMm").value || "").trim();' in html
    assert 'if (!force && currentValue) {' in html
    assert 'renderOpsCabinetSlotCapacityHint();' in html
    assert '$("opsCabinetSlotCapacityMm").value = suggested > 0 ? String(suggested) : "";' in html
    assert '$("opsCabinetSizeGroup").addEventListener("change", () => maybeAutofillOpsCabinetSlotCapacity(false));' in html
    assert 'maybeAutofillOpsCabinetSlotCapacity(true);' in html


def test_index_ops_cabinet_form_renders_slot_capacity_hint_node():
    html = read_static_html("index.html")
    block = html.split('data-i18n="ops.cabinet.field.slot_capacity.label">칸 폭(mm)</label>', 1)[1].split('data-i18n="ops.cabinet.field.floor_start.label">열 시작</label>', 1)[0]
    assert 'id="opsCabinetSlotCapacityHint"' in block
    assert 'data-i18n="ops.cabinet.field.slot_capacity.hint"' in block
    assert '권장값 안내' in block


def test_index_ops_cabinet_form_explains_grouped_cabinet_filing_hint():
    html = read_static_html("index.html")
    block = html.split('data-i18n="ops.cabinet.field.group_name.label">그룹명(선택)</label>', 1)[1].split('<label for="opsCabinetSizeGroup">규격</label>', 1)[0]
    assert 'id="opsCabinetGroupHint"' in block
    assert 'data-i18n="ops.cabinet.group_hint"' in block
    assert "같은 그룹명과 순서를 주면 운영 화면에서 하나의 장식장처럼 이어집니다." in block
    assert "1열은 그룹 순서대로 칸이 이어지고" in block


def test_index_ops_cabinet_form_exposes_domain_field_and_save_payload():
    html = read_static_html("index.html")
    assert '<label for="opsCabinetDomainCode" data-i18n="ops.cabinet.field.domain.label">도메인</label>' in html
    save_block = html.split("    async function saveOpsStorageCabinet() {", 1)[1].split("    async function deleteOpsStorageCabinet() {", 1)[0]
    assert 'cabinet_domain_code: $("opsCabinetDomainCode").value || null,' in save_block
    fill_block = html.split("    function fillOpsCabinetForm(summary) {", 1)[1].split("    function resetOpsCameraForm() {", 1)[0]
    assert '$("opsCabinetDomainCode").value = String(summary.cabinet_domain_code || "");' in fill_block
    reset_block = html.split("    function resetOpsCabinetForm() {", 1)[1].split("    function fillOpsSlotForm(slot) {", 1)[0]
    assert '$("opsCabinetDomainCode").value = "";' in reset_block


def test_index_ops_cabinet_slot_capacity_hint_tracks_recommended_and_custom_states():
    html = read_static_html("index.html")
    assert 'function renderOpsCabinetSlotCapacityHint()' in html
    assert 'const recommended = recommendedCabinetSlotCapacityMm($("opsCabinetSizeGroup").value);' in html
    assert 'hint.textContent = `권장 ${formatCount(recommended)}mm · 사용자 지정`; ' not in html
    assert 'hint.textContent = t("ops.cabinet.slot_capacity.hint.custom", { recommended: formatCount(recommended) });' in html
    assert 'hint.textContent = t("ops.cabinet.slot_capacity.hint.default", { recommended: formatCount(recommended) });' in html
    assert '$("opsCabinetSlotCapacityMm").addEventListener("input", renderOpsCabinetSlotCapacityHint);' in html
def test_index_ops_cabinet_summary_tracks_domain_value_and_renders_domain_column():
    html = read_static_html("index.html")
    summary_block = html.split("    function summarizeStorageCabinets(rows) {", 1)[1].split("    function renderDashboardChipGroup(", 1)[0]
    assert "domain_codes: new Set()," in summary_block
    assert "cabinet_domain_code:" in summary_block
    table_block = html.split("    function renderOpsCabinetTable(rows) {", 1)[1].split("    function renderOpsCameraCabinetOptions() {", 1)[0]
    assert 'dashboardDomainLabel(cabinet.cabinet_domain_code || "UNASSIGNED")' in table_block


def test_index_ops_subtab_order_places_slots_before_camera():
    html = read_static_html("index.html")
    cabinet_idx = html.index('id="opsCabinetTabBtn"')
    slot_idx = html.index('id="opsSlotTabBtn"')
    camera_idx = html.index('id="opsCameraTabBtn"')
    assert cabinet_idx < slot_idx < camera_idx


def test_index_load_storage_slots_no_longer_calls_removed_camera_cabinet_renderer():
    html = read_static_html("index.html")
    block = html.split("    async function loadStorageSlots() {", 1)[1].split("    async function saveOpsStorageCabinet() {", 1)[0]
    assert "renderOpsCameraCabinetOptions();" not in block


def test_index_ops_cabinet_form_prefills_and_resets_common_slot_capacity_override():
    html = read_static_html("index.html")
    reset_block = html.split("    function resetOpsCabinetForm() {", 1)[1].split("    function fillOpsSlotForm(slot) {", 1)[0]
    fill_block = html.split("    function fillOpsCabinetForm(summary) {", 1)[1].split("    function resetOpsCameraForm() {", 1)[0]
    summary_block = html.split("    function summarizeStorageCabinets(rows) {", 1)[1].split("    function renderDashboardChipGroup(", 1)[0]
    assert '$("opsCabinetGroupName").value = "";' in reset_block
    assert '$("opsCabinetGroupOrder").value = "";' in reset_block
    assert '$("opsCabinetGroupName").value = String(summary.cabinet_group_name || "");' in fill_block
    assert '$("opsCabinetGroupOrder").value = String(summary.cabinet_group_order || "");' in fill_block
    assert '$("opsCabinetSlotCapacityMm").value = "";' in reset_block
    assert '$("opsCabinetSlotCapacityMm").value = String(summary.max_thickness_mm || "");' in fill_block
    assert "group_names: new Set()," in summary_block
    assert "group_orders: new Set()," in summary_block
    assert "cabinet_group_name:" in summary_block
    assert "cabinet_group_order:" in summary_block
    assert "max_thickness_values: new Set()," in summary_block
    assert "max_thickness_mm:" in summary_block


def test_index_ops_cabinet_save_payload_includes_group_metadata():
    html = read_static_html("index.html")
    block = html.split("    async function saveOpsStorageCabinet() {", 1)[1].split("    async function deleteOpsStorageCabinet() {", 1)[0]
    assert 'cabinet_group_name: $("opsCabinetGroupName").value.trim() || null,' in block
    assert 'cabinet_group_order: Number($("opsCabinetGroupOrder").value || 0) || null,' in block


def test_index_dashboard_cabinet_groups_use_group_name_as_visual_board_key():
    html = read_static_html("index.html")
    key_block = html.split("    function dashboardCabinetKey(row) {", 1)[1].split("    function buildDashboardCabinetGroups(rows) {", 1)[0]
    assert 'const cabinetGroupName = String(row?.cabinet_group_name || "").trim();' in key_block
    assert 'if (cabinetGroupName) return `GROUP:${cabinetGroupName}`;' in key_block


def test_index_dashboard_grouped_cabinets_render_as_single_board_with_linked_meta():
    html = read_static_html("index.html")
    group_block = html.split("    function buildDashboardCabinetGroups(rows) {", 1)[1].split("    function resolveDashboardStorageSlotId(slotRow) {", 1)[0]
    render_block = html.split("    function renderDashboardSlotCards(rows, totalInCollection) {", 1)[1].split("    async function loadDashboardSlotItems(slotRow, opts = {}) {", 1)[0]
    assert "cabinetNames: new Set()," in group_block
    assert "const cabinetNamesText = Array.from(group.cabinetNames).sort(compareCodeValue).join(" in group_block
    assert "cabinetCount: group.cabinetNames.size," in group_block
    assert "const groupedOrdering = Boolean(group.groupName && cabinetCount > 1);" in group_block
    assert 'class="dashboard-cabinet-head-sub"' in render_block
    assert 't("dashboard.cabinet.meta.connected_cabinets", { count: formatCount(group.cabinetCount) })' in render_block
    assert "dashboardCabinetMapCellLabel(row, group)" in render_block


def test_index_dashboard_grouped_cabinet_map_relabels_cells_in_merged_order():
    html = read_static_html("index.html")
    block = html.split("    function dashboardCabinetMapCellLabel(slotRow, group = null) {", 1)[1].split("    function updateDashboardSlotGridControls(groups, startIndex, pageSize) {", 1)[0]
    assert "const groupedOrdering = Boolean(group?.groupName && Number(group?.cabinetCount || 0) > 1);" in block
    assert "const floorRows = group.rows.filter((row) => String(row?.column_code || \"\").trim() === floorCode);" in block
    assert "const index = floorRows.findIndex((row) => String(row?.slot_code || \"\").trim() === slotCode);" in block
    assert 'return dashboardCellCodeLabel(String(index + 1).padStart(2, "0"));' in block


def test_index_home_search_result_supports_compact_master_heading_and_location_actions():
    html = read_static_html("index.html")
    assert "function homeMasterHeadingLabel(row)" in html
    assert "function homeMasterLocationButtonsHtml(row)" in html
    assert 'class="home-master-location-actions"' in html
    assert 'home-master-location-btn' in html
    assert "data-home-open-dashboard-location" in html

def test_index_ops_home_header_is_ops_only_and_admin_hero_stays_separate():
    html = read_static_html("index.html")
    nav_start = "function applyShellNavigation(session) {"
    nav_end = "    function openAdminConsole(tab = \"home\", options = {}) {"
    assert nav_start in html
    assert nav_end in html
    block = html.split(nav_start, 1)[1].split(nav_end, 1)[0]
    assert 'setDisplayIfPresent("appHero"' in block
    assert 'setDisplayIfPresent("opsHomeHero"' in block
    assert 'mode === "admin"' in block
    assert 'mode !== "admin"' in block
    assert "placeShellUtilityBar(mode);" in block


def test_index_admin_hero_embeds_admin_menu_inside_header_shell():
    html = read_static_html("index.html")
    hero_start = '<header id="appHero" class="hero admin-shell-hero">'
    ops_start = '    <section id="opsHomeHero" class="ops-home-hero" style="display:none;">'
    assert hero_start in html
    assert ops_start in html
    block = html.split(hero_start, 1)[1].split(ops_start, 1)[0]
    assert 'class="admin-shell-hero-main"' in block
    assert 'class="shell-header-row admin-shell-row"' in block
    assert 'class="admin-shell-hero-side"' in block
    assert 'id="adminTabs"' in block
    assert block.index('class="shell-header-row admin-shell-row"') < block.index('id="adminTabs"')
    side_block = block.split('<div class="admin-shell-hero-side">', 1)[1].split('</div>\n        </div>\n        <div class="shell-header-row admin-shell-row">', 1)[0]
    assert 'id="adminUtilityMount"' in side_block
    row_block = block.split('<div class="shell-header-row admin-shell-row">', 1)[1].split('</div>\n      </div>\n    </header>', 1)[0]
    assert 'id="adminUtilityMainMount"' in row_block


def test_index_admin_hero_compacts_copy_to_tab_spacing():
    html = read_static_html("index.html")
    hero_block = html.split(".admin-shell-hero {", 1)[1].split("}", 1)[0]
    main_block = html.split(".admin-shell-hero-main {", 1)[1].split("}", 1)[0]
    head_block = html.split(".admin-shell-hero-head {", 1)[1].split("}", 1)[0]
    copy_block = html.split(".admin-shell-copy {", 1)[1].split("}", 1)[0]
    side_block = html.split(".admin-shell-hero-side {", 1)[1].split("}", 1)[0]
    art_block = html.split("\n    .admin-shell-hero-art {\n", 1)[1].split("}", 1)[0]
    header_row_block = html.split(".shell-header-row {", 1)[1].split("}", 1)[0]
    tab_btn_block = html.split("\n    .tab-btn {\n", 1)[1].split("}", 1)[0]
    assert "padding: 8px 12px;" in hero_block
    assert "gap: 3px;" in main_block
    assert "align-items: start;" in head_block
    assert "gap: 6px;" in head_block
    assert "gap: 1px;" in copy_block
    assert "gap: 3px;" in side_block
    assert "min-height: 44px;" in art_block
    assert "margin-top: 0;" in header_row_block
    assert "gap: 4px;" in header_row_block
    assert "padding: 4px 9px;" in tab_btn_block


def test_index_ops_home_hero_matches_admin_shell_spacing_tokens():
    html = read_static_html("index.html")
    admin_hero_block = html.split(".admin-shell-hero {", 1)[1].split("}", 1)[0]
    ops_hero_block = html.split(".ops-home-hero {", 1)[1].split("}", 1)[0]
    admin_main_block = html.split(".admin-shell-hero-main {", 1)[1].split("}", 1)[0]
    ops_main_block = html.split(".ops-home-hero-main {", 1)[1].split("}", 1)[0]
    admin_copy_block = html.split(".admin-shell-copy {", 1)[1].split("}", 1)[0]
    ops_copy_block = html.split(".ops-home-hero-copy {", 1)[1].split("}", 1)[0]
    admin_side_block = html.split(".admin-shell-hero-side {", 1)[1].split("}", 1)[0]
    ops_side_block = html.split(".ops-home-hero-side {", 2)[2].split("}", 1)[0]
    admin_h1_block = html.split(".admin-shell-hero h1 {", 1)[1].split("}", 1)[0]
    ops_h1_block = html.split(".ops-home-hero-copy h1 {", 1)[1].split("}", 1)[0]
    admin_art_block = html.split(".admin-shell-hero-art {", 2)[2].split("}", 1)[0]
    ops_art_block = html.split(".ops-home-hero-art {", 1)[1].split("}", 1)[0]
    assert "padding: 8px 12px;" in admin_hero_block
    assert "padding: 8px 12px;" in ops_hero_block
    assert "border-radius: 22px;" in admin_hero_block
    assert "border-radius: 22px;" in ops_hero_block
    assert "gap: 3px;" in admin_main_block
    assert "gap: 3px;" in ops_main_block
    assert "gap: 1px;" in admin_copy_block
    assert "gap: 1px;" in ops_copy_block
    assert "gap: 3px;" in admin_side_block
    assert "gap: 3px;" in ops_side_block
    assert "font-size: 1.34rem;" in admin_h1_block
    assert "font-size: 1.34rem;" in ops_h1_block
    assert "min-height: 44px;" in admin_art_block
    assert "min-height: 44px;" in ops_art_block


def test_index_shell_density_sync_clears_compact_header_classes_to_keep_shell_headers_consistent():
    html = read_static_html("index.html")
    assert "function syncShellDensityClasses()" in html
    block = html.split("function syncShellDensityClasses() {", 1)[1].split("    function updateShellRoute(mode, options = {}) {", 1)[0]
    assert '$("appHero")?.classList.remove("admin-shell-hero--compact");' in block
    assert '$("opsHomeHero")?.classList.remove("ops-home-hero--compact");' in block
    apply_block = html.split("function applyShellNavigation(session) {", 1)[1].split("    function openAdminConsole(tab = \"home\", options = {}) {", 1)[0]
    assert "syncShellDensityClasses();" in apply_block
    switch_block = html.split("    function switchMainTab(tab, options = {}) {", 1)[1].split("    function switchSubTab(group, tab, options = {}) {", 1)[0]
    assert "syncShellDensityClasses();" in switch_block


def test_index_ops_home_hero_uses_top_aligned_side_and_matches_admin_compact_title_scale():
    html = read_static_html("index.html")
    ops_main_block = html.split(".ops-home-hero-main {", 1)[1].split("}", 1)[0]
    ops_compact_h1_block = html.split(".ops-home-hero--compact .ops-home-hero-copy h1 {", 1)[1].split("}", 1)[0]
    assert "align-items: start;" in ops_main_block
    assert "font-size: 1.2rem;" in ops_compact_h1_block


def test_index_ops_home_header_uses_admin_width_tokens():
    html = read_static_html("index.html")
    admin_head_block = html.split(".admin-shell-hero-head {", 1)[1].split("}", 1)[0]
    admin_copy_block = html.split(".admin-shell-copy {", 1)[1].split("}", 1)[0]
    admin_subtitle_block = html.split(".admin-shell-hero p {", 1)[1].split("}", 1)[0]
    ops_main_block = html.split(".ops-home-hero-main {", 1)[1].split("}", 1)[0]
    ops_copy_block = html.split(".ops-home-hero-copy {", 1)[1].split("}", 1)[0]
    ops_subtitle_block = html.split(".ops-home-hero-copy p {", 1)[1].split("}", 1)[0]
    admin_grid = [line.strip() for line in admin_head_block.splitlines() if "grid-template-columns:" in line][0]
    ops_grid = [line.strip() for line in ops_main_block.splitlines() if "grid-template-columns:" in line][0]
    assert admin_grid == ops_grid
    assert "max-width: 56ch;" in admin_copy_block
    assert "max-width: 56ch;" in ops_copy_block
    assert "max-width: 52ch;" in admin_subtitle_block
    assert "max-width: 52ch;" in ops_subtitle_block


def test_index_admin_docs_box_becomes_compact_trigger_panel():
    html = read_static_html("index.html")
    docs_block = html.split(".admin-shell-docs {", 1)[1].split("}", 1)[0]
    link_block = html.split(".admin-shell-docs .doc-link-chip {", 1)[1].split("}", 1)[0]
    assert "width: auto;" in docs_block
    assert "justify-content: flex-end;" in docs_block
    assert "gap: 6px;" in docs_block
    assert "padding: 3px 8px;" in link_block
    assert "min-height: 24px;" in link_block
    assert "min-width: 96px;" in link_block
    assert "line-height: 1.1;" in link_block
    assert "font-size: 0.72rem;" in link_block
    hero_block = html.split('<div class="shell-doc-links admin-shell-docs">', 1)[1].split("</div>", 1)[0]
    assert 'href="/tool-docs/erd-summary"' in hero_block
    assert 'href="/tool-docs/erd-detail"' in hero_block
    assert 'href="/tool-docs/manual"' in hero_block
    assert 'href="/tool-docs/go-live-checklist"' not in hero_block


def test_index_uses_shared_page_help_drawer_for_first_wave_screens():
    html = read_static_html("index.html")
    assert 'id="pageHelpOverlay"' in html
    assert 'id="pageHelpDrawer"' in html
    assert 'id="pageHelpTitle"' in html
    assert 'id="pageHelpBody"' in html
    assert 'data-page-help-open="ops-home"' in html
    assert 'data-page-help-open="dashboard"' in html
    assert 'data-page-help-open="media-search"' in html
    assert 'data-page-help-open="media-manage"' in html
    assert 'data-page-help-open="ops-system"' in html
    assert 'data-page-help-open="ops-cabinet"' in html
    assert 'data-page-help-source="ops-home"' in html
    assert 'data-page-help-source="dashboard"' in html
    assert 'data-page-help-source="media-search"' in html
    assert 'data-page-help-source="media-manage"' in html
    assert 'data-page-help-source="ops-system"' in html
    assert 'data-page-help-source="ops-cabinet"' in html
    assert "function openPageHelpDrawer(helpId, trigger = null) {" in html
    assert "function closePageHelpDrawer(options = {}) {" in html
    assert "function renderPageHelpDrawer(helpId) {" in html
    assert 'document.addEventListener("click", (e) => {' in html
    assert 'const helpTrigger = e.target.closest("[data-page-help-open]");' in html
    assert 'const closeBtn = e.target.closest("[data-page-help-close]");' in html
    assert 'if (pageHelpDrawerState.open) {' in html
    assert 'if (e.key === "Escape") {' in html


def test_index_extends_shared_page_help_drawer_to_second_wave_screens():
    html = read_static_html("index.html")
    assert 'data-page-help-open="collectibles"' in html
    assert 'data-page-help-open="source-workbench"' in html
    assert 'data-page-help-open="register-direct"' in html
    assert 'data-page-help-open="register-purchase"' in html
    assert 'data-page-help-open="register-batch"' in html
    assert 'data-page-help-open="register-master"' in html
    assert 'data-page-help-open="ops-camera"' in html
    assert 'data-page-help-open="ops-slot"' in html
    assert 'data-page-help-open="ops-exception"' in html
    assert 'data-page-help-open="ops-account"' in html
    assert 'data-page-help-open="ops-export"' in html
    assert 'data-page-help-open="ops-meta-sync"' in html
    assert 'data-page-help-source="collectibles"' in html
    assert 'data-page-help-source="source-workbench"' in html
    assert 'data-page-help-source="register-direct"' in html
    assert 'data-page-help-source="register-purchase"' in html
    assert 'data-page-help-source="register-batch"' in html
    assert 'data-page-help-source="register-master"' in html
    assert 'data-page-help-source="ops-camera"' in html
    assert 'data-page-help-source="ops-slot"' in html
    assert 'data-page-help-source="ops-exception"' in html
    assert 'data-page-help-source="ops-account"' in html
    assert 'data-page-help-source="ops-export"' in html
    assert 'data-page-help-source="ops-meta-sync"' in html
    assert html.count('manual-block manual-block--page-help') == 1
    assert 'data-i18n="media.register.purchase.field.manual.summary"' in html


def test_index_ops_home_compacts_hero_art_and_focus_chip_grid():
    html = read_static_html("index.html")
    hero_block = html.split(".ops-home-hero {", 1)[1].split("}", 1)[0]
    main_regular_block = html.split(".ops-home-hero-main {", 1)[1].split("}", 1)[0]
    compact_block = html.split(".ops-home-hero--compact .ops-home-hero-main {", 1)[1].split("}", 1)[0]
    art_block = html.split(".ops-home-hero--compact .ops-home-hero-art {", 1)[1].split("}", 1)[0]
    copy_block = html.split(".ops-home-hero--compact .ops-home-hero-copy {", 1)[1].split("}", 1)[0]
    subtitle_block = html.split(".ops-home-hero--compact .ops-home-hero-copy p {", 1)[1].split("}", 1)[0]
    assert "padding: 8px 12px;" in hero_block
    assert "gap: 3px;" in main_regular_block
    assert "grid-template-columns: minmax(0, 1fr) auto;" in compact_block
    assert "display: none;" in art_block
    assert "gap: 1px;" in copy_block
    assert "display: block;" in subtitle_block
    assert "white-space: nowrap;" in subtitle_block
    assert "text-overflow: ellipsis;" in subtitle_block


def test_index_ops_home_header_includes_guidance_copy_in_compact_mode():
    html = read_static_html("index.html")
    assert 'data-i18n="shell.ops.subtitle"' in html
    assert "현장 조회, 위치 확인, 최근 흐름을 한 화면에서 정리합니다." in html


def test_index_compact_hero_variants_reduce_padding_one_more_step():
    html = read_static_html("index.html")
    compact_admin_block = html.split(".admin-shell-hero--compact {", 1)[1].split("}", 1)[0]
    compact_admin_head_block = html.split(".admin-shell-hero--compact .admin-shell-hero-head {", 1)[1].split("}", 1)[0]
    compact_admin_h1_block = html.split(".admin-shell-hero--compact h1 {", 1)[1].split("}", 1)[0]
    compact_ops_block = html.split(".ops-home-hero--compact {", 1)[1].split("}", 1)[0]
    compact_ops_copy_block = html.split(".ops-home-hero--compact .ops-home-hero-copy {", 1)[1].split("}", 1)[0]
    compact_ops_h1_block = html.split(".ops-home-hero--compact .ops-home-hero-copy h1 {", 1)[1].split("}", 1)[0]
    assert "padding: 7px 12px;" in compact_admin_block
    assert "gap: 4px;" in compact_admin_block
    assert "gap: 6px;" in compact_admin_head_block
    assert "font-size: 1.2rem;" in compact_admin_h1_block
    assert "padding: 7px 12px;" in compact_ops_block
    assert "gap: 4px;" in compact_ops_block
    assert "gap: 1px;" in compact_ops_copy_block
    assert "font-size: 1.2rem;" in compact_ops_h1_block


def test_index_admin_dashboard_and_subtabs_use_closer_header_title_scales():
    html = read_static_html("index.html")
    regular_admin_h1_block = html.split(".admin-shell-hero h1 {", 1)[1].split("}", 1)[0]
    compact_admin_h1_block = html.split(".admin-shell-hero--compact h1 {", 1)[1].split("}", 1)[0]
    assert "font-size: 1.34rem;" in regular_admin_h1_block
    assert "font-size: 1.2rem;" in compact_admin_h1_block


def test_index_header_utility_stacks_docs_and_locale_above_session_actions():
    html = read_static_html("index.html")
    utility_mount_block = html.split(".utility-mount {", 1)[1].split("}", 1)[0]
    shell_utility_block = html.split(".shell-utility {", 1)[1].split("}", 1)[0]
    utility_main_block = html.split(".shell-utility-main {", 1)[1].split("}", 1)[0]
    utility_tools_block = html.split(".shell-utility-tools {", 1)[1].split("}", 1)[0]
    utility_chip_block = html.split(".shell-utility .chip {", 1)[1].split("}", 1)[0]
    utility_btn_block = html.split(".shell-utility .tab-btn {", 1)[1].split("}", 1)[0]
    locale_block = html.split(".shell-locale-picker {", 1)[1].split("}", 1)[0]
    docs_link_block = html.split(".admin-shell-docs .doc-link-chip {", 1)[1].split("}", 1)[0]
    locale_select_block = html.split(".shell-locale-picker select {", 1)[1].split("}", 1)[0]
    assert "align-self: stretch;" in utility_mount_block
    assert "min-height: 100%;" in utility_mount_block
    assert "display: grid;" in shell_utility_block
    assert "align-content: space-between;" in shell_utility_block
    assert "min-height: 68px;" in shell_utility_block
    assert "justify-items: end;" in shell_utility_block
    assert "gap: 3px;" in shell_utility_block
    assert "justify-content: flex-end;" in utility_main_block
    assert "justify-self: end;" in utility_main_block
    assert "margin-left: 0;" in utility_tools_block
    assert "display: inline-flex;" in utility_tools_block
    assert "justify-self: end;" in utility_tools_block
    assert "align-items: center;" in utility_tools_block
    assert "justify-content: flex-end;" in utility_tools_block
    assert "display: inline-flex;" in utility_chip_block
    assert "align-items: center;" in utility_chip_block
    assert "padding: 4px 9px;" in utility_chip_block
    assert "min-height: 26px;" in utility_chip_block
    assert "font-size: 0.84rem;" in utility_chip_block
    assert "font-weight: 700;" in utility_chip_block
    assert "padding: 4px 9px;" in utility_btn_block
    assert "min-height: 26px;" in utility_btn_block
    assert "font-size: 0.84rem;" in utility_btn_block
    utility_override_block = html.split("#shellUtilityBar .chip,\n    #shellUtilityBar .tab-btn {", 1)[1].split("}", 1)[0]
    assert "min-height: 26px;" in utility_override_block
    assert "padding: 4px 9px;" in utility_override_block
    assert "font-size: 0.84rem;" in utility_override_block
    assert "font-weight: 700;" in utility_override_block
    tools_block = html.split(".shell-utility-tools {", 1)[1].split("}", 1)[0]
    main_row_block = html.split(".shell-utility-main {", 1)[1].split("}", 1)[0]
    assert "padding-bottom: 4px;" in tools_block
    assert "padding-top: 4px;" in main_row_block
    assert "border-top: 1px solid rgba(203, 213, 225, 0.7);" in main_row_block
    assert "padding: 3px 8px;" in locale_block
    assert "font-size: 0.72rem;" in locale_block
    assert "font-weight: 700;" in locale_block
    assert "min-width: 96px;" in locale_block
    assert "padding: 3px 8px;" in docs_link_block
    assert "min-height: 24px;" in docs_link_block
    assert "min-width: 96px;" in docs_link_block
    assert "appearance: none;" in locale_select_block
    assert "-webkit-appearance: none;" in locale_select_block
    assert "min-width: 68px;" in locale_select_block
    utility_block = html.split('<div id="shellUtilityBar" class="shell-utility" style="display:none;">', 1)[1].split('</div>\n\n    <div id="tabHome"', 1)[0]
    assert utility_block.index('class="shell-utility-tools shell-utility-tools--meta"') < utility_block.index('class="shell-utility-main shell-utility-main--actions"')
    assert 'class="shell-doc-links admin-shell-docs"' in utility_block
    assert utility_block.index('class="shell-doc-links admin-shell-docs"') < utility_block.index('class="shell-locale-picker"')
    assert utility_block.index('id="appSessionInfo"') < utility_block.index('id="appLogoutBtn"')


def test_index_shell_utility_exposes_direct_doc_links_with_routes():
    html = read_static_html("index.html")
    utility_block = html.split('<div id="shellUtilityBar" class="shell-utility" style="display:none;">', 1)[1].split('</div>\n\n    <div id="tabHome"', 1)[0]
    assert 'class="shell-doc-links admin-shell-docs"' in utility_block
    assert 'href="/tool-docs/erd-summary"' in utility_block
    assert 'href="/tool-docs/erd-detail"' in utility_block
    assert 'href="/tool-docs/manual"' in utility_block
    assert 'href="/tool-docs/go-live-checklist"' not in utility_block


def test_index_header_utility_hierarchy_uses_meta_and_action_modifier_groups():
    html = read_static_html("index.html")
    tools_modifier_block = html.split(".shell-utility-tools--meta {", 1)[1].split("}", 1)[0]
    actions_modifier_block = html.split(".shell-utility-main--actions {", 1)[1].split("}", 1)[0]
    meta_control_block = html.split(".shell-utility-tools--meta .doc-link-chip,\n    .shell-utility-tools--meta .shell-locale-picker {", 1)[1].split("}", 1)[0]
    action_control_block = html.split(".shell-utility-main--actions .chip,\n    .shell-utility-main--actions .tab-btn {", 1)[1].split("}", 1)[0]
    utility_block = html.split('<div id="shellUtilityBar" class="shell-utility" style="display:none;">', 1)[1].split('</div>\n\n    <div id="tabHome"', 1)[0]
    assert "padding-bottom: 3px;" in tools_modifier_block
    assert "border-top: 1px solid rgba(148, 163, 184, 0.22);" in actions_modifier_block
    assert "padding-top: 5px;" in actions_modifier_block
    assert "box-shadow: none;" in meta_control_block
    assert "color: #64748b;" in meta_control_block
    assert "background: rgba(255,255,255,0.96);" in action_control_block
    assert "border-color: #c7d7d2;" in action_control_block
    assert 'class="shell-utility-tools shell-utility-tools--meta"' in utility_block
    assert 'class="shell-utility-main shell-utility-main--actions"' in utility_block


def test_header_login_chip_uses_high_contrast_readable_treatment():
    html = read_static_html("index.html")
    chip_block = html.split(".shell-utility-main--actions .chip {", 1)[1].split("}", 1)[0]
    assert "background: rgba(15, 23, 42, 0.72);" in chip_block
    assert "color: #ffffff;" in chip_block
    assert "border-color: rgba(226, 232, 240, 0.4);" in chip_block


def test_index_apply_shell_navigation_shows_shell_utility_bar_as_grid():
    html = read_static_html("index.html")
    apply_block = html.split('function applyShellNavigation(session) {', 1)[1].split('    function openAdminConsole(tab = "home", options = {}) {', 1)[0]
    assert 'setDisplayIfPresent("shellUtilityBar", authenticated ? "grid" : "none");' in apply_block
    assert 'setDisplayIfPresent("adminUtilityMainMount", authenticated && isAdmin && mode === "admin" ? "flex" : "none");' in apply_block
    assert 'setDisplayIfPresent("opsUtilityMainMount", authenticated && mode !== "admin" ? "flex" : "none");' in apply_block
    assert "syncShellUtilityRowSizing();" in apply_block


def test_index_sync_shell_utility_row_sizing_normalizes_right_side_controls():
    html = read_static_html("index.html")
    assert "function syncShellUtilityRowSizing() {" in html
    block = html.split("function syncShellUtilityRowSizing() {", 1)[1].split("    function resetReadOnlyShellState() {", 1)[0]
    assert 'const utilityRowSelectors = ["appSessionInfo", "shellAdminBtn", "tabCameraBtn", "appPrefsResetBtn", "appLogoutBtn", "shellOpsHomeBtn"];' in block
    assert 'el.style.minHeight = "26px";' in block
    assert 'el.style.padding = "4px 9px";' in block
    assert 'el.style.fontSize = "0.84rem";' in block
    assert 'el.style.fontWeight = "700";' in block
    assert 'el.style.lineHeight = "1.2";' in block


def test_index_shell_utility_no_longer_mounts_page_help_into_header():
    html = read_static_html("index.html")
    assert 'function placeShellPageHelp(mode = currentShellMode()) {' not in html
    assert 'id="shellPageHelpMount"' not in html
    apply_block = html.split('function applyShellNavigation(session) {', 1)[1].split('    function openAdminConsole(tab = "home", options = {}) {', 1)[0]
    assert 'placeShellPageHelp(mode);' not in apply_block


def test_index_admin_hero_includes_music_domain_visuals():
    html = read_static_html("index.html")
    hero_start = '<header id="appHero" class="hero admin-shell-hero">'
    ops_start = '    <section id="opsHomeHero" class="ops-home-hero" style="display:none;">'
    assert hero_start in html
    assert ops_start in html
    block = html.split(hero_start, 1)[1].split(ops_start, 1)[0]
    assert 'class="admin-shell-hero-art"' in block
    assert "admin-shell-media admin-shell-media--lp" in block
    assert "admin-shell-media admin-shell-media--cd" in block
    assert "admin-shell-media admin-shell-media--cassette" in block


def test_index_exposes_shared_language_selector_and_locale_options():
    html = read_static_html("index.html")
    assert 'id="shellLocaleSelect"' in html
    assert 'value="ko"' in html
    assert 'value="en"' in html
    assert 'value="ja"' in html


def test_index_contains_i18n_state_dictionary_and_translation_hooks():
    html = read_static_html("index.html")
    assert "const APP_LOCALE_STORAGE_KEY" in html
    assert "let appLocale = " in html
    assert "const I18N_MESSAGES = {" in html
    assert "function t(key, params = {}) {" in html
    assert "function applyLocale(locale = appLocale) {" in html
    assert 'data-i18n="' in html


def test_index_header_shell_uses_translation_attributes_for_core_labels():
    html = read_static_html("index.html")
    assert 'data-i18n="shell.admin.kicker"' in html
    assert 'data-i18n="shell.admin.title"' in html
    assert 'data-i18n="shell.admin.subtitle"' in html
    assert 'data-i18n="nav.dashboard"' in html
    assert 'data-i18n="nav.media"' in html
    assert 'data-i18n="nav.collectibles"' in html
    assert 'data-i18n="nav.ops"' in html
    assert 'data-i18n="utility.language"' in html


def test_index_selected_manuals_and_page_help_triggers_use_i18n_keys():
    html = read_static_html("index.html")
    assert 'data-i18n="manual.ops_home.summary"' in html
    assert 'data-i18n="manual.dashboard.summary"' in html
    assert 'data-i18n="manual.media_search.summary"' in html
    assert 'data-i18n="manual.media_manage.summary"' in html
    assert 'data-i18n="page_help.trigger"' in html
    assert 'data-help-key="help.dashboard.slot_occupancy"' in html
    assert 'data-help-key="help.dashboard.cover_flow"' in html
    assert 'data-help-key="help.dashboard.workbench"' in html
    assert 'data-help-key="help.shared_camera.preview"' in html
    assert 'data-help-key="help.media.search.owned_items"' in html
    assert 'data-help-key="help.media.manage.location"' in html


def test_index_help_and_close_action_groups_render_as_symbol_buttons():
    html = read_static_html("index.html")
    title_row_block = html.split(".page-help-title-row {", 1)[1].split("}", 1)[0]
    help_block = html.split(".page-help-trigger {", 1)[1].split("}", 1)[0]
    help_before_block = html.split(".page-help-trigger::before {", 1)[1].split("}", 1)[0]
    help_dot_block = html.split(".help-dot {", 1)[1].split("}", 1)[0]
    section_help_dot_block = html.rsplit(".section-help-dot {", 1)[1].split("}", 1)[0]
    icon_close_block = html.split(".icon-symbol-btn--close {", 1)[1].split("}", 1)[0]
    assert "align-items: flex-end;" in title_row_block
    assert "font-size: 0;" in help_block
    assert "align-self: flex-end;" in help_block
    assert "min-height: 16px;" in help_block
    assert "width: 16px;" in help_block
    assert 'content: "?";' in help_before_block
    assert "font-size: 0.56rem;" in help_before_block
    assert "width: 10px;" in help_dot_block
    assert "height: 10px;" in help_dot_block
    assert "font-size: 0.46rem;" in help_dot_block
    assert "top: -1px;" in help_dot_block
    assert "vertical-align: text-bottom;" in help_dot_block
    assert "width: 14px;" in section_help_dot_block
    assert "height: 14px;" in section_help_dot_block
    assert "border-radius: 999px;" in section_help_dot_block
    assert "font-size: 0.56rem;" in section_help_dot_block
    assert "top: -2px;" in section_help_dot_block
    assert "vertical-align: text-bottom;" in section_help_dot_block
    assert "--icon-mask: url(" in icon_close_block
    assert 'id="pageHelpCloseBtn" class="btn ghost tiny page-help-close icon-symbol-btn icon-symbol-btn--close"' in html
    assert 'id="imageGalleryCloseBtn" class="btn ghost icon-symbol-btn icon-symbol-btn--close"' in html


def test_ops_primary_create_and_save_rows_place_primary_action_last():
    html = read_static_html("index.html")
    action_row_block = html.split(".row.action-row-trailing-primary {", 1)[1].split("}", 1)[0]
    cabinet_row = html.split('<div class="row action-row-trailing-primary" style="margin-top:8px;">', 1)[1].split("</div>", 1)[0]
    assert "justify-content: flex-end;" in action_row_block
    assert cabinet_row.index('id="opsCabinetDeleteBtn"') < cabinet_row.index('id="opsCabinetSaveBtn"')
    assert cabinet_row.index('id="opsCabinetResetBtn"') < cabinet_row.index('id="opsCabinetSaveBtn"')
    assert 'id="opsCameraSaveBtn" class="btn" type="button" data-i18n="ops.camera.action.save"' in html
    assert 'id="opsSlotSaveBtn" class="btn" type="button" data-i18n="ops.slot.action.save"' in html
    assert 'id="opsAuthSaveBtn" class="btn" type="button" data-i18n="ops.account.action.save"' in html


def test_index_navigation_open_and_edit_action_groups_render_as_symbol_buttons():
    html = read_static_html("index.html")
    icon_edit_block = html.split(".icon-symbol-btn--edit {", 1)[1].split("}", 1)[0]
    icon_open_block = html.split(".icon-symbol-btn--open {", 1)[1].split("}", 1)[0]
    icon_prev_block = html.split(".icon-symbol-btn--previous {", 1)[1].split("}", 1)[0]
    icon_next_block = html.rsplit(".icon-symbol-btn--next {", 1)[1].split("}", 1)[0]
    assert "--icon-mask: url(" in icon_edit_block
    assert "--icon-mask: url(" in icon_open_block
    assert "--icon-mask: url(" in icon_prev_block
    assert "--icon-mask: url(" in icon_next_block
    assert 'id="homeDashWorkbenchEditBtn" class="btn ghost tiny dashboard-workbench-actionbtn icon-symbol-btn icon-symbol-btn--edit"' in html
    assert 'id="homeOpenDashboardSlotBtn" class="btn ghost tiny icon-symbol-btn icon-symbol-btn--open"' in html
    assert 'id="homeEditShelfPrevBtn" class="btn ghost shelf-nav-btn icon-symbol-btn icon-symbol-btn--previous"' in html
    assert 'id="homeEditShelfNextBtn" class="btn ghost shelf-nav-btn icon-symbol-btn icon-symbol-btn--next"' in html


def test_index_search_action_group_uses_shared_symbol_buttons():
    html = read_static_html("index.html")
    assert 'id="homeDashSearchRunBtn" class="btn ghost icon-btn" type="button" data-i18n-title="operator.lookup.action.run" data-i18n-aria-label="operator.lookup.action.run"' in html
    assert 'id="operatorLookupBtn" class="btn secondary icon-btn" type="button" data-i18n-title="operator.lookup.action.run" data-i18n-aria-label="operator.lookup.action.run"' in html
    assert 'id="goodsSearchRunBtn" class="btn secondary icon-btn" type="button" data-i18n-title="common.search" data-i18n-aria-label="common.search"' in html
    assert 'id="albumSearchBtn" class="btn secondary icon-btn" type="button" data-i18n-title="viewer.action.search" data-i18n-aria-label="viewer.action.search"' in html
    assert html.count('<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6"></circle><path d="M20 20l-4.2-4.2"></path></svg>') >= 5


def test_index_selection_action_group_uses_shared_symbol_buttons():
    html = read_static_html("index.html")
    icon_base_block = html.split(".icon-symbol-btn::before {", 1)[1].split("}", 1)[0]
    icon_select_all_block = html.split(".icon-symbol-btn--select-all {", 1)[1].split("}", 1)[0]
    icon_clear_selection_block = html.split(".icon-symbol-btn--clear-selection {", 1)[1].split("}", 1)[0]
    assert "width: var(--action-icon-size);" in icon_base_block
    assert "height: var(--action-icon-size);" in icon_base_block
    assert "mask-image: var(--icon-mask);" in icon_base_block
    assert "--icon-mask: url(" in icon_select_all_block
    assert "--icon-mask: url(" in icon_clear_selection_block
    assert 'id="homeDashSlotSelectAllBtn" class="btn ghost tiny dashboard-slot-actionbtn icon-symbol-btn icon-symbol-btn--select-all"' in html
    assert 'id="homeDashSlotClearBtn" class="btn ghost tiny dashboard-slot-actionbtn icon-symbol-btn icon-symbol-btn--clear-selection"' in html
    assert 'id="homeDashWorkbenchSelectAllBtn" class="btn ghost tiny dashboard-workbench-actionbtn icon-symbol-btn icon-symbol-btn--select-all"' in html
    assert 'id="homeDashWorkbenchClearBtn" class="btn ghost tiny dashboard-workbench-actionbtn icon-symbol-btn icon-symbol-btn--clear-selection"' in html
    assert 'id="masterVariantSelectAllBtn" class="btn ghost icon-symbol-btn icon-symbol-btn--select-all"' in html
    assert 'id="masterVariantClearBtn" class="btn ghost icon-symbol-btn icon-symbol-btn--clear-selection"' in html
    assert 'id="opsExceptionSelectAllBtn" class="btn ghost tiny icon-symbol-btn icon-symbol-btn--select-all"' in html
    assert 'id="opsExceptionClearBtn" class="btn ghost tiny icon-symbol-btn icon-symbol-btn--clear-selection"' in html


def test_index_reset_action_group_uses_shared_symbol_buttons():
    html = read_static_html("index.html")
    icon_reset_block = html.split(".icon-symbol-btn--reset {", 1)[1].split("}", 1)[0]
    assert "--icon-mask: url(" in icon_reset_block
    assert 'id="homeResetBtn" class="btn ghost icon-symbol-btn icon-symbol-btn--reset" type="button" data-i18n-title="media.search.action.reset_filters" data-i18n-aria-label="media.search.action.reset_filters"' in html
    assert 'id="goodsSearchResetBtn" class="btn ghost icon-symbol-btn icon-symbol-btn--reset" type="button" title="비우기" aria-label="비우기" data-i18n="common.clear" data-i18n-title="common.clear" data-i18n-aria-label="common.clear"' in html
    assert 'id="quickResetBtn" class="btn ghost icon-symbol-btn icon-symbol-btn--reset" type="button" title="직접 등록 폼 초기화" aria-label="직접 등록 폼 초기화" data-i18n="media.register.direct.action.reset" data-i18n-title="media.register.direct.action.reset" data-i18n-aria-label="media.register.direct.action.reset"' in html
    assert 'id="resetFormBtn" class="btn ghost icon-symbol-btn icon-symbol-btn--reset" type="button" title="폼 초기화" aria-label="폼 초기화" data-i18n="media.register.detail.action.reset" data-i18n-title="media.register.detail.action.reset" data-i18n-aria-label="media.register.detail.action.reset"' in html
    assert 'id="purchaseImportResetBtn" class="btn ghost icon-symbol-btn icon-symbol-btn--reset" type="button" title="입력 비우기" aria-label="입력 비우기" data-i18n="media.register.purchase.action.reset" data-i18n-title="media.register.purchase.action.reset" data-i18n-aria-label="media.register.purchase.action.reset"' in html
    assert 'id="masterVariantResetBtn" class="btn ghost icon-symbol-btn icon-symbol-btn--reset" type="button" title="초기화" aria-label="초기화" data-i18n="media.register.master.action.reset_filters" data-i18n-title="media.register.master.action.reset_filters" data-i18n-aria-label="media.register.master.action.reset_filters"' in html
    assert 'id="opsCabinetResetBtn" class="btn ghost icon-symbol-btn icon-symbol-btn--reset" type="button" title="입력 초기화" aria-label="입력 초기화" data-i18n="ops.cabinet.action.reset" data-i18n-title="ops.cabinet.action.reset" data-i18n-aria-label="ops.cabinet.action.reset"' in html
    assert 'id="opsCameraResetBtn" class="btn ghost icon-symbol-btn icon-symbol-btn--reset" type="button" title="입력 초기화" aria-label="입력 초기화" data-i18n="ops.camera.action.reset" data-i18n-title="ops.camera.action.reset" data-i18n-aria-label="ops.camera.action.reset"' in html
    assert 'id="opsSlotResetBtn" class="btn ghost icon-symbol-btn icon-symbol-btn--reset" type="button" title="입력 초기화" aria-label="입력 초기화" data-i18n="ops.slot.action.reset" data-i18n-title="ops.slot.action.reset" data-i18n-aria-label="ops.slot.action.reset"' in html
    assert 'id="opsAuthResetBtn" class="btn ghost icon-symbol-btn icon-symbol-btn--reset" type="button" title="입력 초기화" aria-label="입력 초기화" data-i18n="ops.account.action.reset" data-i18n-title="ops.account.action.reset" data-i18n-aria-label="ops.account.action.reset"' in html


def test_icon_buttons_share_uniform_height_and_symbol_box():
    html = read_static_html("index.html")
    root_block = html.split(":root {", 1)[1].split("}", 1)[0]
    btn_block = html.split("\n    .btn {", 1)[1].split("}", 1)[0]
    ghost_block = html.split(".btn.ghost {", 1)[1].split("}", 1)[0]
    disabled_block = html.split(".btn:disabled {", 1)[1].split("}", 1)[0]
    icon_symbol_block = html.split("\n    .icon-symbol-btn {", 1)[1].split("}", 1)[0]
    icon_symbol_base_block = html.split(".icon-symbol-btn::before {", 1)[1].split("}", 1)[0]
    icon_btn_block = html.split(".icon-btn {", 1)[1].split("}", 1)[0]
    icon_btn_svg_block = html.split(".icon-btn svg {", 1)[1].split("}", 1)[0]
    refresh_block = html.split(".dashboard-cabinet-refreshbtn {", 1)[1].split("}", 1)[0]
    refresh_icon_block = html.split(".dashboard-cabinet-refreshicon {", 1)[1].split("}", 1)[0]
    assert "--action-btn-size: 40px;" in root_block
    assert "--action-icon-size: 16px;" in root_block
    assert "min-height: 40px;" in btn_block
    assert "display: inline-flex;" in btn_block
    assert "align-items: center;" in btn_block
    assert "background: #fff;" in ghost_block
    assert "cursor: not-allowed;" in disabled_block
    assert "opacity:" in disabled_block
    assert "box-shadow: none;" in disabled_block
    assert "min-height: var(--action-btn-size);" in icon_symbol_block
    assert "width: var(--action-icon-size);" in icon_symbol_base_block
    assert "height: var(--action-icon-size);" in icon_symbol_base_block
    assert "height: var(--action-btn-size);" in icon_btn_block
    assert "width: var(--action-icon-size);" in icon_btn_svg_block
    assert "height: var(--action-icon-size);" in icon_btn_svg_block
    assert "width: var(--action-btn-size);" in refresh_block
    assert "min-height: var(--action-btn-size);" in refresh_block
    assert "width: var(--action-icon-size);" in refresh_icon_block
    assert "height: var(--action-icon-size);" in refresh_icon_block


def test_index_apply_locale_updates_data_help_key_tooltips():
    html = read_static_html("index.html")
    block = html.split("function applyLocale(locale = appLocale) {", 1)[1].split("\n    }\n\n    function mediaDisplayLabel", 1)[0]
    assert 'document.querySelectorAll("[data-help-key]")' in block
    assert 'el.setAttribute("data-help", t(key));' in block
    assert 'el.setAttribute("title", t(key));' in block


def test_index_admin_utility_bar_shows_hahahoho_only_for_admin_and_places_it_last():
    html = read_static_html("index.html")
    utility_start = '    <div id="shellUtilityBar" class="shell-utility" style="display:none;">'
    admin_tabs_start = '\n    <div id="tabHome" class="tab-panel active">'
    nav_start = "function applyShellNavigation(session) {"
    open_admin_start = '    function openAdminConsole(tab = "home", options = {}) {'
    assert utility_start in html
    assert admin_tabs_start in html
    assert nav_start in html
    assert open_admin_start in html
    utility_block = html.split(utility_start, 1)[1].split(admin_tabs_start, 1)[0]
    nav_block = html.split(nav_start, 1)[1].split(open_admin_start, 1)[0]
    ops_block = html.split('    <section id="opsHomeHero" class="ops-home-hero" style="display:none;">', 1)[1].split(utility_start, 1)[0]
    assert 'id="shellOpsHomeBtn"' in utility_block
    assert ">hahahoho</button>" in utility_block
    assert utility_block.index('id="appLogoutBtn"') < utility_block.index('id="shellOpsHomeBtn"')
    assert 'setDisplayIfPresent("shellOpsHomeBtn", authenticated && isAdmin && mode === "admin" ? "inline-flex" : "none");' in nav_block
    assert '$("shellOpsHomeBtn").addEventListener("click", () => switchShellMode("ops"));' in html
    assert "hahahoho" not in ops_block


def test_index_dashboard_slot_detail_actions_are_grouped_by_intent():
    html = read_static_html("index.html")
    detail_start = '<div class="dashboard-detail-head">'
    flow_start = '              <div class="dashboard-slot-rack-surface dashboard-slot-rack-surface--interactive">'
    floors_marker = '              <div id="homeDashCabinetFloors" class="dashboard-floor-list" style="display:none !important;" aria-hidden="true"></div>'
    list_start = 'id="homeDashSlotItems" class="home-location-slot-list"'
    assert detail_start in html
    assert flow_start in html
    assert floors_marker in html
    assert list_start in html
    detail_block = html.split(detail_start, 2)[2].split(flow_start, 1)[0]
    flow_block = html.split(flow_start, 1)[1].split(floors_marker, 1)[0]
    assert 'id="homeDashSlotViewGroup"' in detail_block
    assert "보기/탐색" in detail_block
    assert 'id="homeDashSlotSelectionGroup"' not in detail_block
    assert 'id="homeDashSlotPagePrevBtn"' not in detail_block
    assert 'id="homeDashSlotPageNextBtn"' not in detail_block
    assert 'id="homeDashCameraCard"' not in detail_block
    assert 'class="dashboard-bulk-edit-bar"' not in detail_block
    assert 'id="homeDashSlotSelectionGroup"' in flow_block
    assert "선택 관리" not in flow_block
    assert "실제 변경" not in flow_block
    assert 'id="homeDashSlotViewShelfBtn"' in detail_block
    assert 'id="homeDashSelectedItemEditBtn"' in flow_block
    assert flow_block.index('id="homeDashSelectedItemEditBtn"') < flow_block.index('id="homeDashSlotBulkBtn"')
    assert 'id="homeDashSlotEditBtn"' not in flow_block
    assert 'id="homeDashSlotSelectAllBtn"' in flow_block
    assert 'id="homeDashSlotClearBtn"' in flow_block
    assert 'id="homeDashSlotPagePrevBtn"' in flow_block
    assert 'id="homeDashSlotPageNextBtn"' in flow_block
    assert 'class="dashboard-slot-viewportbar"' in flow_block
    assert 'id="homeDashSlotRestoreBtn"' in flow_block
    assert 'id="homeDashSlotMoveFrontBtn"' not in flow_block
    assert 'id="homeDashSlotMoveBackBtn"' not in flow_block
    assert html.index('id="homeDashSlotSelectionGroup"') < html.index('id="homeDashSlotItems"')
    assert html.index('id="homeDashSlotPagePrevBtn"') < html.index('id="homeDashSlotItems"')


def test_index_dashboard_slot_detail_embeds_controls_inside_cover_flow_surface():
    html = read_static_html("index.html")
    detail_start = '            <div id="homeDashCabinetDetail" class="dashboard-cabinet-detail" style="display:none;">'
    floors_start = '              <div id="homeDashCabinetFloors" class="dashboard-floor-list" style="display:none !important;" aria-hidden="true"></div>'
    assert detail_start in html
    assert floors_start in html
    block = html.split(detail_start, 1)[1].split(floors_start, 1)[0]
    assert 'class="dashboard-cabinet-stage"' in block
    assert 'class="dashboard-slot-rack-surface dashboard-slot-rack-surface--interactive"' in block
    assert 'class="dashboard-slot-surface-tools"' in block
    assert 'id="homeDashSurfaceDock"' in block
    assert 'id="homeDashSurfaceCameraBtn"' not in block
    assert 'id="homeDashSlotBulkBtn"' in block
    assert 'id="homeDashSelectedItemEditBtn"' in block
    assert 'id="homeDashBulkCloseBtn"' in block
    assert 'id="homeDashCameraCard"' not in block
    assert 'class="dashboard-bulk-edit-bar"' in block
    assert 'class="dashboard-slot-rack-tray"' not in block
    assert 'class="dashboard-slot-rack-handlebar"' not in block
    assert 'id="homeDashSlotPagePrevBtn"' in block
    assert 'id="homeDashSlotPageNextBtn"' in block
    assert block.index('class="dashboard-slot-rack-surface dashboard-slot-rack-surface--interactive"') < block.index('id="homeDashSlotItems"')
    assert block.index('class="dashboard-slot-surface-tools"') < block.index('id="homeDashSlotItems"')
    assert block.index('id="homeDashSlotBulkBtn"') < block.index('id="homeDashSlotItems"')
    surface_block = html.split(".dashboard-slot-rack-surface--interactive {", 1)[1].split("}", 1)[0]
    assert "overflow: visible;" in surface_block
    bulk_popover_block = html.split(".dashboard-slot-bulk-popover {", 1)[1].split("}", 1)[0]
    assert "width: min(320px, calc(100vw - 156px));" in bulk_popover_block


def test_index_dashboard_desktop_compacts_cabinet_detail_and_coverflow_gap():
    html = read_static_html("index.html")
    cabinet_detail_block = html.split(".dashboard-cabinet-detail {", 1)[1].split("}", 1)[0]
    cabinet_stage_block = html.split(".dashboard-cabinet-stage {", 1)[1].split("}", 1)[0]
    rack_surface_block = html.split(".dashboard-slot-rack-surface {", 1)[1].split("}", 1)[0]
    surface_tools_block = html.split(".dashboard-slot-surface-tools {", 1)[1].split("}", 1)[0]
    selected_item_meta_block = html.split(".dashboard-selected-item-meta {", 1)[1].split("}", 1)[0]
    sort_artist_block = html.split(".dashboard-selected-sort-artist-row {", 1)[1].split("}", 1)[0]
    toolbar_row_block = html.split(".dashboard-slot-toolbar-row {", 1)[1].split("}", 1)[0]
    viewportbar_block = html.split(".dashboard-slot-viewportbar {", 1)[1].split("}", 1)[0]
    viewtools_block = html.split(".dashboard-slot-viewtools {", 1)[1].split("}", 1)[0]
    viewbar_block = html.split(".dashboard-slot-viewbar {", 1)[1].split("}", 1)[0]
    pagebar_block = html.split(".dashboard-slot-pagebar {", 1)[1].split("}", 1)[0]
    selection_toolbar_block = html.split(".dashboard-selection-toolbar {", 1)[1].split("}", 1)[0]

    assert "margin-top: 6px;" in cabinet_detail_block
    assert "padding-top: 6px;" in cabinet_detail_block
    assert "gap: 6px;" in cabinet_detail_block
    assert "gap: 6px;" in cabinet_stage_block
    assert "padding: 10px 12px 12px;" in cabinet_stage_block
    assert "border-radius: 20px;" in cabinet_stage_block
    assert "gap: 6px;" in rack_surface_block
    assert "padding: 12px 14px 14px;" in rack_surface_block
    assert "border-radius: 18px;" in rack_surface_block
    assert "gap: 6px;" in surface_tools_block
    assert "gap: 8px;" in selected_item_meta_block
    assert "padding: 6px 8px;" in selected_item_meta_block
    assert "border-radius: 12px;" in selected_item_meta_block
    assert "margin-top: 2px;" in sort_artist_block
    assert "column-gap: 10px;" in sort_artist_block
    assert "row-gap: 3px;" in sort_artist_block
    assert "gap: 6px;" in toolbar_row_block
    assert "gap: 6px;" in viewportbar_block
    assert "gap: 4px;" in viewtools_block
    assert "gap: 3px;" in viewbar_block
    assert "gap: 4px;" in pagebar_block
    assert "min-height: 34px;" in pagebar_block
    assert "padding: 0 8px;" in pagebar_block
    assert "margin-top: 2px;" in selection_toolbar_block
    assert "margin-bottom: 4px;" in selection_toolbar_block


def test_index_dashboard_slot_hover_overlay_keeps_slot_meta_hidden():
    html = read_static_html("index.html")
    overlay_block = html.split(".dashboard-selected-item-meta--overlay {", 1)[1].split("}", 1)[0]
    overlay_button_block = html.split(".dashboard-selected-item-meta--overlay .dashboard-slot-actionbtn {", 1)[1].split("}", 1)[0]
    runtime_block = html.split("    function renderDashboardSelectedItemMeta() {", 1)[1].split("    function syncDashboardSelectedSortArtistEditor() {", 1)[0]
    hover_helper_block = html.split("    function dashboardSlotHoverMetaOverlayEnabled() {", 1)[1].split("    function renderDashboardSelectedItemMeta() {", 1)[0]
    slot_events_block = html.split('    $("homeDashSlotItems").addEventListener("pointerdown", (e) => {', 1)[1].split('    $("homeDashWorkbenchList").addEventListener("pointerdown", (e) => {', 1)[0]

    assert "position: absolute;" in overlay_block
    assert "top: 12px;" in overlay_block
    assert "left: 14px;" in overlay_block
    assert "right: 14px;" in overlay_block
    assert "z-index: 4;" in overlay_block
    assert "pointer-events: none;" in overlay_block
    assert "display: none !important;" in overlay_button_block

    assert 'let homeDashboardHoveredItemId = null;' in html
    assert 'window.matchMedia("(hover: hover) and (pointer: fine)").matches' in hover_helper_block
    assert 'homeDashboardSlotViewMode === "THUMB" || homeDashboardSlotViewMode === "SHELF"' in hover_helper_block
    assert 'const selectionSourceKind = getDashboardSelectionSourceKind();' in runtime_block
    assert 'if (selectionSourceKind === "SLOT") {' in runtime_block
    assert 'el.style.display = "none";' in runtime_block
    assert 'if (textEl) textEl.textContent = "";' in runtime_block
    assert 'syncDashboardSelectedSortArtistEditor();' in runtime_block
    assert 'return;' in runtime_block
    assert 'el.classList.toggle("dashboard-selected-item-meta--overlay", useOverlay);' in runtime_block
    assert 'el.style.display = useOverlay ? "flex" : "flex";' not in runtime_block
    assert 'el.style.display = "flex";' in runtime_block

    assert '$("homeDashSlotItems").addEventListener("pointerover", (e) => {' in slot_events_block
    assert '$("homeDashSlotItems").addEventListener("pointerleave", () => {' in slot_events_block
    assert '$("homeDashSlotItems").addEventListener("focusin", (e) => {' in slot_events_block
    assert '$("homeDashSlotItems").addEventListener("focusout", (e) => {' in slot_events_block


def test_index_exposes_shared_camera_main_tab():
    html = read_static_html("index.html")
    assert 'id="tabCameraBtn"' in html
    assert 'id="tabCamera"' in html
    assert 'id="sharedCameraList"' in html
    assert 'id="sharedCameraPreview"' in html
    assert 'id="sharedCameraTitle"' in html
    assert 'id="sharedCameraMeta"' in html


def test_index_camera_admin_copy_describes_shared_cameras():
    html = read_static_html("index.html")
    assert "공용 카메라" in html
    assert "장식장마다 확인용 카메라" not in html
    assert 'for="opsCameraDescription"' in html


def test_index_camera_admin_form_uses_selection_summary_instead_of_internal_id():
    html = read_static_html("index.html")
    assert 'id="opsCameraSelectionSummary"' in html
    assert "새 카메라 설정 중" in html
    assert 'for="opsCameraId"' not in html
    assert 'id="opsCameraNotes"' not in html


def test_index_camera_admin_table_uses_compact_settings_columns():
    html = read_static_html("index.html")
    assert '<th data-i18n="ops.camera.table.header.preview">미리보기</th>' in html
    assert '<th data-i18n="ops.camera.table.header.active">활성</th>' in html
    assert "<th>스냅샷</th>" not in html
    assert "<th>스트림</th>" not in html
    assert "<th>인증</th>" not in html


def test_index_camera_admin_hides_connection_fields_inside_advanced_details():
    html = read_static_html("index.html")
    assert 'id="opsCameraAdvancedSettings"' in html
    assert ">연결 설정 / 자동 채움<" in html
    advanced_block = html.split('id="opsCameraAdvancedSettings"', 1)[1].split("</details>", 1)[0]
    assert 'for="opsCameraOnvifUrl"' in advanced_block
    assert 'for="opsCameraSnapshotUrl"' in advanced_block
    assert 'for="opsCameraStreamUrl"' in advanced_block
    assert 'id="opsCameraDiscoverBtn"' in advanced_block
    assert 'id="opsCameraTestBtn"' in advanced_block


def test_index_camera_discovery_table_keeps_only_name_ip_and_apply_columns():
    html = read_static_html("index.html")
    advanced_block = html.split('id="opsCameraAdvancedSettings"', 1)[1].split("</details>", 1)[0]
    assert '<th data-i18n="ops.camera.discover.table.header.name">이름</th>' in advanced_block
    assert '<th data-i18n="ops.camera.discover.table.header.ip">IP</th>' in advanced_block
    assert '<th data-i18n="ops.camera.discover.table.header.apply">적용</th>' in advanced_block
    assert "<th>ONVIF 장치 URL</th>" not in advanced_block


def test_index_camera_admin_moves_reload_action_to_list_header():
    html = read_static_html("index.html")
    section = html.split('<div id="opsCameraPanel" class="subtab-panel">', 1)[1].split("</section>", 1)[0]
    assert '<span data-i18n="ops.camera.title">공용 카메라 설정</span>' in section
    assert 'id="opsCameraReloadBtn"' in section
    assert "저장된 카메라" in section
    button_row = section.split('<div class="row" style="margin-top:8px;">', 1)[1].split("</div>", 1)[0]
    assert 'id="opsCameraReloadBtn"' not in button_row


def test_index_export_panel_includes_restore_upload_and_auto_backup_settings():
    html = read_static_html("index.html")
    section = html.split('<div id="opsExportPanel" class="subtab-panel">', 1)[1].split('<div id="opsMetaSyncPanel"', 1)[0]
    assert 'id="opsAutoBackupEnabled"' in section
    assert 'id="opsAutoBackupIntervalMinutes"' in section
    assert 'id="opsAutoBackupScope"' in section
    assert 'id="opsAutoBackupIncludeEnvFile"' in section
    assert 'id="opsAutoBackupDir"' in section
    assert 'id="opsAutoBackupSaveBtn"' in section
    assert 'id="opsExportFullBtn"' in section
    assert 'id="opsRestoreDbFile"' in section
    assert 'id="opsRestoreDbBtn"' in section
    assert 'id="opsRestoreBundleFile"' in section
    assert 'id="opsRestoreBundleBtn"' in section
    assert 'data-i18n="ops.restore.intro"' in section
    assert '<label class="inline-check" for="opsAutoBackupEnabled"' in section
    assert 'data-i18n="ops.restore.field.enabled.label"' in section
    assert '<label for="opsAutoBackupDir" data-i18n="ops.restore.field.dir.label">저장 경로</label>' in section
    assert '<label for="opsAutoBackupScope" data-i18n="ops.restore.field.scope.label">백업 범위</label>' in section
    assert '<option value="DB" data-i18n="ops.restore.scope.db">DB만</option>' in section
    assert '<option value="FULL" data-i18n="ops.restore.scope.full">전체(zip)</option>' in section
    assert 'data-i18n="ops.restore.field.include_env.label"' in section
    assert 'id="opsAutoBackupSummary" class="mini muted" style="margin-top:8px;" data-i18n="ops.restore.summary.loading"' in section
    assert '<h2 data-i18n="ops.restore.db.title">DB 복구 업로드</h2>' in section
    assert '<label for="opsRestoreDbFile" data-i18n="ops.restore.db.field.file.label">복구 파일(.db)</label>' in section
    assert 'id="opsRestoreDbBtn" class="btn secondary" type="button" data-i18n="ops.restore.db.action.run"' in section
    assert '<h2 data-i18n="ops.restore.bundle.title">전체 백업(zip) 복구</h2>' in section
    assert '<label for="opsRestoreBundleFile" data-i18n="ops.restore.bundle.field.file.label">복구 파일(.zip)</label>' in section
    assert 'id="opsRestoreBundleBtn" class="btn secondary" type="button" data-i18n="ops.restore.bundle.action.run"' in section
    assert 'data-i18n="ops.restore.outro"' in section


def test_operator_weather_shared_camera_and_restore_static_copy_use_i18n_keys():
    html = read_static_html("index.html")
    assert 'id="operatorWeatherKicker" class="operator-weather-kicker" data-i18n="operator.weather.empty.kicker"' in html
    assert 'id="operatorWeatherLocation" data-i18n="operator.weather.empty.location"' in html
    assert 'id="operatorWeatherDescription" data-i18n="operator.weather.empty.description"' in html
    assert '<span class="mini" data-i18n="operator.weather.metric.humidity">습도</span>' in html
    assert 'id="operatorWeatherSecondaryLabel" class="mini" data-i18n="operator.weather.empty.secondary"' in html
    assert 'id="operatorWeatherUpdated" data-i18n="operator.weather.empty.updated"' in html
    assert 'class="dashboard-camera-placeholder" data-i18n="shared_camera.empty.body"' in html

    assert '"operator.feed.filter.aria":' in html
    assert '"operator.weather.metric.humidity":' in html
    assert '"shared_camera.empty.body":' in html
    assert '"ops.restore.intro":' in html
    assert '"ops.restore.db.action.run":' in html
    assert '"ops.restore.bundle.action.run":' in html


def test_index_export_panel_wires_backup_settings_and_restore_actions():
    html = read_static_html("index.html")
    assert "async function loadOpsBackupSettings()" in html
    assert "async function saveOpsBackupSettings()" in html
    assert "async function restoreOpsDatabase()" in html
    assert "async function downloadOpsFullBackup()" in html
    assert "async function restoreOpsBundle()" in html
    assert '$("opsAutoBackupSaveBtn")?.addEventListener("click", saveOpsBackupSettings);' in html
    assert '$("opsRestoreDbBtn")?.addEventListener("click", restoreOpsDatabase);' in html
    assert '$("opsExportFullBtn")?.addEventListener("click", downloadOpsFullBackup);' in html
    assert '$("opsRestoreBundleBtn")?.addEventListener("click", restoreOpsBundle);' in html


def test_index_ops_provider_settings_panel_includes_metadata_provider_inputs():
    html = read_static_html("index.html")
    section = html.split('<div id="opsProviderPanel" class="subtab-panel">', 1)[1].split('<div id="opsExportPanel"', 1)[0]
    deepl_group = section.split('id="opsProviderDeeplAuthKey"', 1)[1].split("</section>", 1)[0]
    assert 'class="ops-provider-settings-stack"' in section
    assert 'class="ops-provider-group ops-provider-group--pair"' in section
    assert 'class="ops-provider-group ops-provider-group--single"' in section
    assert 'class="ops-provider-group-grid"' in section
    assert 'class="ops-provider-group-actions"' in section
    assert 'id="opsProviderTabBtn" class="subtab-btn" type="button" data-i18n="ops.subtab.providers"' in html
    assert 'data-i18n="ops.providers.title"' in section
    assert 'id="opsProviderDiscogsToken"' in section
    assert 'id="opsProviderDiscogsUserAgent"' in section
    assert 'id="opsProviderDiscogsSaveBtn"' in section
    assert 'id="opsProviderAladinTtbKey"' in section
    assert 'id="opsProviderAladinBaseUrl"' in section
    assert 'id="opsProviderAladinSaveBtn"' in section
    assert 'id="opsProviderManiadbBaseUrl"' in section
    assert 'id="opsProviderManiadbSaveBtn"' in section
    assert 'id="opsProviderMusicbrainzUserAgent"' in section
    assert 'id="opsProviderMusicbrainzSaveBtn"' in section
    assert 'id="opsProviderDeeplAuthKey"' in section
    assert 'id="opsProviderDeeplBaseUrl"' in section
    assert 'id="opsProviderDeeplSaveBtn"' in deepl_group
    assert 'id="opsProviderDeeplTestBtn"' in deepl_group
    assert 'id="opsProviderResetBtn"' in section
    assert 'id="opsProviderStatus"' in section


def test_index_ops_provider_settings_panel_wires_load_and_save_actions():
    html = read_static_html("index.html")
    assert "async function loadOpsProviderSettings()" in html
    assert "async function saveOpsProviderSettings()" in html
    assert "async function saveOpsProviderSettingsFields(fields, statusKey = \"ops.providers.status.saved\") {" in html
    assert "async function testOpsProviderDeeplConnection() {" in html
    assert '$("opsProviderTabBtn")?.addEventListener("click", async () => {' in html
    assert 'await loadOpsProviderSettings();' in html
    assert '$("opsProviderDeeplTestBtn")?.addEventListener("click", testOpsProviderDeeplConnection);' in html
    assert '$("opsProviderDiscogsSaveBtn")?.addEventListener("click", () => saveOpsProviderSettingsFields([' in html
    assert '$("opsProviderAladinSaveBtn")?.addEventListener("click", () => saveOpsProviderSettingsFields([' in html
    assert '$("opsProviderManiadbSaveBtn")?.addEventListener("click", () => saveOpsProviderSettingsFields([' in html
    assert '$("opsProviderMusicbrainzSaveBtn")?.addEventListener("click", () => saveOpsProviderSettingsFields([' in html
    assert '$("opsProviderDeeplSaveBtn")?.addEventListener("click", () => saveOpsProviderSettingsFields([' in html
    assert '$("opsProviderResetBtn")?.addEventListener("click", loadOpsProviderSettings);' in html


def test_admin_top_level_tabs_use_dashboard_media_collectibles_and_ops():
    html = read_static_html("index.html")
    assert 'id="tabHomeBtn"' in html
    assert 'id="tabMediaBtn"' in html
    assert 'id="tabCollectiblesBtn"' in html
    assert 'id="tabOpsBtn"' in html
    assert ">대시보드</button>" in html
    assert ">미디어</button>" in html
    assert ">컬렉터블</button>" in html
    assert ">운영/연계</button>" in html


def test_admin_parent_surfaces_include_media_collectibles_and_ops():
    html = read_static_html("index.html")
    assert 'id="tabMedia"' in html
    assert 'id="tabCollectibles"' in html
    assert 'id="tabOps"' in html


def test_media_surface_contains_search_manage_register_and_source_subtabs():
    html = read_static_html("index.html")
    assert 'id="mediaSearchModeBtn"' in html
    assert 'id="mediaManageModeBtn"' in html
    assert 'id="mediaRegisterModeBtn"' in html
    assert 'id="mediaSourceModeBtn"' in html
    assert 'id="tabSearch"' in html
    assert 'id="tabManage"' in html
    assert 'id="tabRegister"' in html
    assert 'id="tabSource"' in html


def test_collectibles_surface_contains_search_manage_and_register_subtabs():
    html = read_static_html("index.html")
    assert 'id="tabCollectibles"' in html
    assert 'id="goodsSearchModeBtn"' in html
    assert 'id="goodsManageModeBtn"' in html
    assert 'id="goodsRegisterModeBtn"' in html


def test_goods_surface_contains_search_manage_register_sections():
    html = read_static_html("index.html")
    assert 'id="goodsSearchSurface"' in html
    assert 'id="goodsManageSurface"' in html
    assert 'id="goodsRegisterSurface"' in html


def test_goods_search_surface_contains_status_domain_and_slot_filters():
    html = read_static_html("index.html")
    assert 'id="goodsSearchStatusFilter"' in html
    assert 'id="goodsSearchDomainCode"' in html
    assert 'id="goodsSearchStorageSlotId"' in html


def test_goods_manage_surface_contains_album_artist_label_mapping_sections():
    html = read_static_html("index.html")
    assert 'id="goodsAlbumMasterMapList"' in html
    assert 'id="goodsArtistMapList"' in html
    assert 'id="goodsLabelMapList"' in html


def test_goods_manage_surface_is_split_into_basic_product_collectible_and_notes_sections():
    html = read_static_html("index.html")
    assert 'id="goodsManageBasicSection"' in html
    assert 'id="goodsManageProductLinksSection"' in html
    assert 'id="goodsManageCollectibleLinksSection"' in html
    assert 'id="goodsManageNotesSection"' in html


def test_goods_manage_surface_uses_compact_core_and_extra_notes_layout():
    html = read_static_html("index.html")
    assert 'id="goodsManageCoreFields"' in html
    assert 'id="goodsManageCoreRowA"' in html
    assert 'id="goodsManageCoreRowB"' in html
    assert 'id="goodsManageNotesDetails"' in html
    assert 'class="ops-compact-form-grid goods-manage-compact-grid"' in html


def test_goods_manage_mapping_blocks_use_compact_stack_controls():
    html = read_static_html("index.html")
    assert 'id="goodsManageAlbumMasterControls" class="compact-stack"' in html
    assert 'id="goodsManageArtistControls" class="compact-stack"' in html
    assert 'id="goodsManageLabelControls" class="compact-stack"' in html
    assert 'id="goodsManageCollectibleLookupControls" class="compact-stack"' in html
    assert 'id="goodsManageCollectibleComposeControls" class="compact-stack"' in html


def test_goods_search_surface_contains_collectible_relation_filters():
    html = read_static_html("index.html")
    assert 'id="goodsSearchCollectibleRelationState"' in html
    assert 'id="goodsSearchCollectibleRelationType"' in html


def test_goods_manage_surface_contains_collectible_relation_lookup_and_save_controls():
    html = read_static_html("index.html")
    assert 'id="goodsManageCollectibleQuery"' in html
    assert 'id="goodsManageCollectibleResults"' in html
    assert 'id="goodsManageRelationType"' in html
    assert 'id="goodsManageRelationNote"' in html
    assert 'id="goodsCollectibleRelationMapList"' in html
    assert 'id="goodsManageSaveRelationsBtn"' in html


def test_goods_search_results_render_collectible_relation_summary_metadata():
    html = read_static_html("index.html")
    render_block = html.split("function renderGoodsSearchResults() {", 1)[1].split("function resetGoodsManageSelection()", 1)[0]
    assert 'row.collectible_relation_count' in render_block
    assert 'row.relation_badges' in render_block
    assert 'row.collectible_relation_preview' in render_block


def test_admin_parent_tabs_are_registered_in_shell_switching():
    html = read_static_html("index.html")
    assert '{ id: "media", btn: "tabMediaBtn", panel: "tabMedia" }' in html
    assert '{ id: "collectibles", btn: "tabCollectiblesBtn", panel: "tabCollectibles" }' in html
    assert '["home", "camera", "media", "collectibles", "ops"]' in html
    assert '$("tabMediaBtn").addEventListener("click", () => openAdminConsole("media"));' in html
    assert '$("tabCollectiblesBtn").addEventListener("click", () => openAdminConsole("collectibles"));' in html


def test_media_and_collectibles_surfaces_wire_mode_actions():
    html = read_static_html("index.html")
    assert '$("mediaSearchModeBtn").addEventListener("click", () => switchMediaMode("search"));' in html
    assert '$("mediaManageModeBtn").addEventListener("click", () => switchMediaMode("manage"));' in html
    assert '$("mediaRegisterModeBtn").addEventListener("click", () => switchMediaMode("register"));' in html
    assert '$("mediaSourceModeBtn").addEventListener("click", () => switchMediaMode("source"));' in html
    assert '$("tabCollectiblesBtn").addEventListener("click", () => openAdminConsole("collectibles"));' in html


def test_goods_surface_wires_search_manage_and_register_actions():
    html = read_static_html("index.html")
    assert '$("goodsSearchRunBtn").addEventListener("click", () => loadGoodsSearchResults());' in html
    assert '$("goodsManageSaveBtn").addEventListener("click", saveGoodsManageItem);' in html
    assert '$("goodsManageDeleteBtn").addEventListener("click", deleteGoodsManageItem);' in html
    assert '$("goodsManageSaveMappingsBtn").addEventListener("click", saveGoodsManageMappings);' in html
    assert '$("goodsManageSaveRelationsBtn").addEventListener("click", saveGoodsManageRelations);' in html
    assert '$("goodsRegisterSaveBtn").addEventListener("click", createGoodsRegisterItem);' in html


def test_home_linked_goods_button_redirects_to_goods_register_surface():
    html = read_static_html("index.html")
    assert 'function openGoodsRegisterFromManageContext()' in html
    assert '$("homeLinkedGoodsCreateBtn").addEventListener("click", openGoodsRegisterFromManageContext);' in html


def test_help_dots_are_removed_from_tab_order_for_linear_form_navigation():
    html = read_static_html("index.html")
    assert 'function removeHelpDotsFromTabOrder(scope = document)' in html
    assert 'badge.setAttribute("tabindex", "-1");' in html
    assert 'removeHelpDotsFromTabOrder(root);' in html


def test_admin_manage_surface_contains_empty_state_prompt():
    html = read_static_html("index.html")
    assert 'id="adminManageEmptyState"' in html
    assert "먼저 검색 결과를 선택하세요." in html
    assert "검색으로 이동" in html


def test_manage_view_separates_linked_goods_zone_from_album_editor_area():
    html = read_static_html("index.html")
    assert 'id="homeMasterGoodsSection"' in html
    assert 'id="homeLinkedGoodsPanel" class="home-goods-panel' in html
    assert 'id="homeMasterSummarySection" style="display:none;"' in html
    assert ".home-goods-panel {" in html
    assert 'data-i18n="media.manage.collectibles.kicker"' in html
    assert 'id="homeLinkedGoodsCreateBtn"' in html
    assert 'data-i18n="media.manage.collectibles.action.open_register"' in html
    assert 'id="homeLinkedGoodsLegacyFields"' in html
    assert 'style="display:none;" hidden' in html
    assert 'data-i18n="media.manage.collectibles.panel_intro"' in html
    assert html.index('id="homeEditorProductBlock"') < html.index('id="homeMasterGoodsSection"') < html.index('id="homeLinkedGoodsPanel"')
    assert html.index('id="homeLinkedGoodsPanel"') < html.index('id="homeManageMasterSection"')
    assert html.index('id="homeMasterGoodsSection"') < html.index('id="homeTrackMapBox"')


def test_manage_view_orders_sections_as_product_collectibles_master_then_cabinet():
    html = read_static_html("index.html")
    assert 'id="homeManageMasterSection"' in html
    assert 'id="homeCabinetSection"' in html
    assert html.index('id="homeCabinetSection"') < html.index('id="homeEditorStandaloneMount"')
    assert html.index('id="homeEditMusicBox"') < html.index('id="homeEditorProductBlock"') < html.index('id="homeMasterGoodsSection"')
    assert html.index('id="homeMasterGoodsSection"') < html.index('id="homeManageMasterSection"')
    mount_block = html.split("function mountHomeMasterInlineEditor() {", 1)[1].split("function parkHomeMasterInlineEditor()", 1)[0]
    assert '$("homeEditMusicBox"),' in mount_block
    assert '$("homeEditGoodsBox"),' in mount_block
    assert '$("homeMasterGoodsSection"),' in mount_block


def test_manage_view_shows_master_summary_after_master_lookup():
    html = read_static_html("index.html")
    related_block = html.split("function renderHomeRelatedVersions() {", 1)[1].split("async function saveHomeMasterSortArtistName()", 1)[0]
    assert 'setDisplayIfPresent("homeMasterSummarySection", "block");' in related_block
    assert html.index('id="homeLinkedGoodsPanel"') < html.index('id="homeManageMasterSection"')
    assert html.index('id="homeMasterAddBlock"') < html.index('id="homeEditorMetaFetchBlock"') < html.index('id="homeMasterDeleteBtn"')


def test_manage_view_keeps_inline_editor_out_of_hidden_master_summary():
    html = read_static_html("index.html")
    block = html.split("function findHomeInlineEditorMountElement(ownedItemId) {", 1)[1].split("function syncHomeMasterInlineEditor()", 1)[0]
    assert 'const relatedSection = relatedItem.closest("#homeMasterSummarySection");' in block
    assert 'if (!relatedSection || relatedSection.style.display !== "none") return relatedItem;' in block
    assert 'return $("homeEditorStandaloneMount");' in block


def test_manage_view_loads_linked_collectibles_alongside_master_members():
    html = read_static_html("index.html")
    block = html.split("async function loadHomeMasterMembers(albumMasterId, opts = {}) {", 1)[1].split("function homeMasterAddVariantRowHtml", 1)[0]
    assert 'fetch(`/goods-items?album_master_id=${masterId}&limit=200&offset=0`)' in block
    assert "const collectibles = Array.isArray(collectiblesData.items) ? collectiblesData.items : [];" in block
    assert "collectibles," in block
    assert '"media.manage.master.members.status.loaded":' in html
    assert 't("media.manage.master.members.status.loaded"' in block


def test_manage_view_renders_linked_collectibles_in_goods_section():
    html = read_static_html("index.html")
    render_block = html.split("function renderHomeRelatedVersions() {", 1)[1].split("async function saveHomeMasterSortArtistName()", 1)[0]
    assert "const collectibles = Array.isArray(homeMasterInfo.collectibles) ? homeMasterInfo.collectibles : [];" in render_block
    assert '"media.manage.related_versions.summary":' in html
    assert 't("media.manage.related_versions.summary"' in render_block
    assert "renderHomeLinkedCollectiblesSection();" in render_block


def test_manage_view_can_render_linked_collectibles_without_master_lookup():
    html = read_static_html("index.html")
    helper_block = html.split("function renderHomeLinkedCollectiblesSection() {", 1)[1].split("function resetHomeMasterLookupUi", 1)[0]
    assert 'id="homeMasterGoodsSection"' in html
    assert 'const collectibles = Array.isArray(homeMasterInfo?.collectibles)' in helper_block
    assert 'homeLinkedCollectibles' in helper_block
    assert 'homeMasterCollectibleItemHtml' in helper_block
    assert 't("media.manage.collectibles.state.loading")' in helper_block
    assert 't("media.manage.collectibles.state.empty")' in helper_block
    assert 'setDisplayIfPresent("homeMasterGoodsSection", "block");' in helper_block
    assert 'setDisplayIfPresent("homeLinkedGoodsPanel", "block");' in helper_block
    assert 'setDisplayIfPresent("homeLinkedGoodsPanel", collectibles.length ? "none" : "block");' in helper_block


def test_manage_view_contains_owned_item_product_relationship_section():
    html = read_static_html("index.html")
    assert 'id="homeProductRelationSection"' in html
    assert 'id="homeProductRelationScopeInfo"' in html
    assert 'id="homeProductRelationMasterList"' in html
    assert 'id="homeProductRelationSeriesList"' in html
    assert 'id="homeProductRelationReleaseList"' in html
    assert 'id="homeProductRelationComponentList"' in html
    assert 'id="homeProductRelationSeriesQuery"' in html
    assert 'id="homeProductRelationReleaseQuery"' in html
    assert 'id="homeProductRelationType"' in html
    assert 'id="homeProductRelationSearchBtn"' in html
    assert 'id="homeProductRelationSaveBtn"' in html
    assert 'id="homeProductRelationStatus"' in html
    assert '"media.manage.product_relation.title":' in html
    assert '"media.manage.product_relation.scope.shared":' in html
    assert '"media.manage.product_relation.scope.single":' in html
    assert '"media.manage.product_relation.block.master":' in html
    assert '"media.manage.product_relation.block.series":' in html
    assert '"media.manage.product_relation.block.release":' in html
    assert '"media.manage.product_relation.block.components":' in html
    assert html.index('id="homeEditorProductBlock"') < html.index('id="homeProductRelationSection"') < html.index('id="homeEditorActionBlock"')


def test_manage_view_product_editor_uses_compact_core_and_extra_layout():
    html = read_static_html("index.html")
    assert 'id="homeEditProductCoreFields"' in html
    assert 'id="homeEditProductCoreRowA"' in html
    assert 'id="homeEditProductCoreRowB"' in html
    assert 'id="homeEditProductExtraDetails"' in html
    assert 'class="ops-compact-form-grid home-manage-product-compact-grid"' in html


def test_manage_view_product_editor_keeps_auxiliary_blocks_under_extra_details():
    html = read_static_html("index.html")
    assert 'id="homeEditMusicOpsRow"' in html
    assert 'id="homeEditMusicInfoRow"' in html
    assert 'id="editMemoryNote"' in html
    assert 'id="editPurchaseSource"' in html
    assert 'id="editConditionGrade"' in html
    assert 'id="editPurchasePrice"' in html
    assert 'id="editCurrencyCode"' in html
    assert 'id="homeEditProductExtraDetails"' in html


def test_manage_view_product_relationship_runtime_uses_relation_routes_and_preview_fields():
    html = read_static_html("index.html")
    relation_block = html.split("function homeOwnedItemRelationTypeLabel(", 1)[1].split("async function saveHomeEditedItem()", 1)[0]
    preview_block = html.split("function homeMasterMemberPreviewHtml(item, options = {}) {", 1)[1].split("function getHomeMasterVisiblePreviewItems(row) {", 1)[0]

    assert 'function renderHomeProductRelationSection() {' in relation_block
    assert 'function resetHomeOwnedItemRelationUi() {' in relation_block
    assert 'fetch(`/owned-items/${ownedItemId}/relations`)' in relation_block
    assert 'fetch(`/owned-item-relation-targets?${params.toString()}`)' in relation_block
    assert 'fetch("/product-groups", {' in relation_block
    assert 'fetch(`/product-groups?${params.toString()}`)' in relation_block
    assert 't("media.manage.product_relation.scope.shared"' in relation_block
    assert 't("media.manage.product_relation.scope.single"' in relation_block
    assert 't("media.manage.product_relation.status.loading")' in relation_block
    assert 't("media.manage.product_relation.status.loaded"' in relation_block
    assert 't("media.manage.product_relation.status.lookup_loading")' in relation_block
    assert 't("media.manage.product_relation.status.save_progress")' in relation_block
    assert 't("media.manage.product_relation.status.save_done"' in relation_block
    assert 't("media.manage.product_relation.results.empty")' in relation_block
    assert 't("media.manage.product_relation.action.create_series")' in relation_block

    assert "product_relation_badges" in preview_block
    assert "product_relation_preview" in preview_block
    assert "box_component_count" in preview_block
    assert "uses_shared_relation_scope" in preview_block
    assert 'homeOwnedItemRelationTypeLabel' in preview_block


def test_manage_view_linked_collectibles_copy_uses_i18n_keys():
    html = read_static_html("index.html")
    helper_block = html.split("function renderHomeLinkedCollectiblesSection() {", 1)[1].split("function resetHomeMasterLookupUi", 1)[0]
    master_info_block = html.split("function syncHomeLinkedGoodsMasterInfo() {", 1)[1].split("function resolveHomeMasterContext(", 1)[0]

    assert 'data-i18n="media.manage.collectibles.kicker"' in html
    assert 'data-i18n="media.manage.collectibles.note"' in html
    assert 'data-i18n="media.manage.collectibles.title"' in html
    assert 'data-i18n="media.manage.collectibles.panel_intro"' in html
    assert 'data-i18n="media.manage.collectibles.panel_note"' in html
    assert 'data-i18n="media.manage.collectibles.field.current_master"' in html
    assert 'data-i18n="media.manage.collectibles.field.register_method"' in html
    assert 'data-i18n="media.manage.collectibles.register_method.body"' in html
    assert 'data-i18n="media.manage.collectibles.action.open_register"' in html
    assert 't("media.manage.collectibles.state.empty")' in helper_block
    assert 't("media.manage.collectibles.state.loading")' in helper_block
    assert 't("media.manage.collectibles.state.no_master_selected")' in master_info_block

    assert '"media.manage.collectibles.kicker":' in html
    assert '"media.manage.collectibles.state.empty":' in html
    assert '"media.manage.collectibles.state.loading":' in html
    assert '"media.manage.collectibles.state.no_master_selected":' in html


def test_manage_view_loads_linked_collectibles_when_product_detail_opens():
    html = read_static_html("index.html")
    detail_block = html.split("async function applyHomeEditorDetail(data, requestSeq = 0) {", 1)[1].split("async function loadHomeItemForEdit", 1)[0]
    assert 'void loadHomeLinkedCollectibles(Number(data.linked_album_master_id || 0), requestSeq);' in detail_block


def test_manage_view_goods_section_can_open_collectible_manage_view():
    html = read_static_html("index.html")
    click_block = html.split("const handleHomeRelatedListClick = (e) => {", 1)[1].split('    $("homeMasterRelatedList").addEventListener("click", handleHomeRelatedListClick);', 1)[0]
    assert 'const goodsManageBtn = e.target.closest(".home-master-collectible-manage-btn");' in click_block
    assert 'openAdminConsole("collectibles");' in click_block
    assert "openGoodsItemForManage(goodsItemId);" in click_block


def test_manage_view_linked_collectibles_render_explicit_manage_button():
    html = read_static_html("index.html")
    block = html.split("function homeMasterCollectibleItemHtml(row) {", 1)[1].split("function groupHomeRelatedVersionItems", 1)[0]
    assert 'class="btn ghost tiny home-master-collectible-manage-btn"' in block
    assert 't("media.manage.collectibles.action.manage")' in block
    assert "클릭해서 컬렉터블 관리 열기" not in block


def test_discogs_result_meta_helper_uses_standard_field_order():
    html = read_static_html("index.html")
    block = html.split("function buildDiscogsStandardMetaHtml(row, opts = {}) {", 1)[1].split("function collectGalleryItems", 1)[0]
    expected_order = [
        't("common.meta.release_date", { value: escapeHtml(releaseDate) })',
        't("common.meta.release_country", { value: escapeHtml(releaseCountry) })',
        't("common.meta.label", { value: escapeHtml(labelName) })',
        't("common.meta.catalog_no", { value: escapeHtml(catalogNo) })',
        't("common.meta.barcode", { value: escapeHtml(barcode) })',
        't("common.meta.format", { value: escapeHtml(formatLabel) })',
        't("common.meta.track_count", { value: escapeHtml(String(trackCount)) })',
    ]
    positions = [block.index(text) for text in expected_order]
    assert positions == sorted(positions)


def test_discogs_result_cards_reuse_standard_meta_helper():
    html = read_static_html("index.html")
    purchase_block = html.split("function buildPurchaseImportCandidateHtml(queueId, state, candidate, candidateIdx) {", 1)[1].split("function purchaseImportAmazonMetaHtml", 1)[0]
    home_meta_block = html.split("function homeMetaCandidateHtml(c, idx) {", 1)[1].split("async function addLinkedHomeMetaCandidate", 1)[0]
    barcode_block = html.split("function renderBarcodeResults(items, opts = {}) {", 1)[1].split("function syncRegisterLookupChoiceToForm", 1)[0]
    master_add_block = html.split("function homeMasterAddVariantItemHtml(row) {", 1)[1].split("function homeMasterAddVariantRowHtml", 1)[0]
    assert 'buildDiscogsStandardMetaHtml(candidate, { includeOwnedCount: true, ownedCountClassName: "source-workbench-owned-pill" })' in purchase_block
    assert "buildDiscogsStandardMetaHtml(c)" in home_meta_block
    assert "buildDiscogsStandardMetaHtml(c, { includeOwnedCount: true })" in barcode_block
    assert "buildDiscogsStandardMetaHtml(row, { includeOwnedCount: true })" in master_add_block


def test_purchase_import_discogs_candidates_highlight_existing_owned_count():
    html = read_static_html("index.html")
    purchase_block = html.split("function buildPurchaseImportCandidateHtml(queueId, state, candidate, candidateIdx) {", 1)[1].split("function purchaseImportAmazonMetaHtml", 1)[0]
    assert 'buildDiscogsStandardMetaHtml(candidate, { includeOwnedCount: true, ownedCountClassName: "source-workbench-owned-pill" })' in purchase_block
    css_block = html.split(".source-workbench-candidate-meta {", 1)[1].split(".source-workbench-candidate-actions {", 1)[0]
    assert ".source-workbench-owned-pill {" in html
    assert "background: #fee2e2;" in html
    assert "color: #b91c1c;" in html


def test_purchase_import_candidate_search_inputs_share_single_inline_row():
    html = read_static_html("index.html")
    block = html.split("function renderPurchaseImportQueueDetails(row, state) {", 1)[1].split("function renderPurchaseImportQueue", 1)[0]
    assert 'class="purchase-import-candidate-search-row"' in block
    assert 'class="purchase-import-candidate-search-field"' in block
    assert 'for="purchaseImportArtistOverride-${queueId}"' in block
    assert 'for="purchaseImportItemOverride-${queueId}"' in block


def test_purchase_import_candidate_search_fields_submit_lookup_on_enter():
    html = read_static_html("index.html")
    block = html.split('$("purchaseImportQueueBody").addEventListener("keydown", async (e) => {', 1)[1].split('    $("opsCabinetTabBtn").addEventListener("click", () => switchSubTab("ops", "cabinet"));', 1)[0]
    assert 'if (e.key !== "Enter") return;' in block
    assert 'const artistInput = e.target.closest("[data-purchase-import-artist]");' in block
    assert 'const itemInput = e.target.closest("[data-purchase-import-item]");' in block
    assert 'await loadPurchaseImportCandidates(queueId);' in block


def test_search_and_manage_manuals_are_split_by_surface():
    html = read_static_html("index.html")
    assert "검색 페이지 활용 매뉴얼" in html
    assert "관리 페이지 활용 매뉴얼" in html
    assert 'data-i18n="manual.media_search.item3"' in html
    assert 'data-i18n="manual.media_manage.note"' in html

def test_source_and_register_manuals_use_i18n_keys():
    html = read_static_html("index.html")
    assert 'data-i18n="manual.source.summary"' in html
    assert 'data-i18n="manual.source.item4"' in html
    assert 'data-i18n="manual.register_direct.summary"' in html
    assert 'data-i18n="manual.register_purchase.summary"' in html
    assert 'data-i18n="manual.register_batch.summary"' in html


def test_source_and_register_help_dots_use_help_keys():
    html = read_static_html("index.html")
    assert 'data-help-key="help.register.api_lookup"' in html


def test_media_source_and_register_core_labels_use_i18n_keys():
    html = read_static_html("index.html")
    assert 'data-page-help-open="source-workbench"' in html
    assert '<h2><span data-i18n="media.source.title">일괄 소스 보강</span></h2>' in html
    assert 'data-i18n="media.source.subtitle"' in html
    assert 'data-i18n="media.source.field.source.label"' in html
    assert 'data-i18n="media.source.action.load"' in html
    assert 'data-i18n="media.source.action.fetch_all"' in html
    assert 'data-i18n="media.source.action.auto_apply"' in html
    assert 'data-i18n="media.source.action.apply_selected"' in html
    assert 'data-i18n="media.register.subtab.direct"' in html
    assert 'data-i18n="media.register.subtab.purchase"' in html
    assert 'data-i18n="media.register.subtab.batch"' in html
    assert 'data-i18n="media.register.subtab.master"' in html
    assert 'data-page-help-open="register-direct"' in html
    assert '<h2><span data-i18n="media.register.direct.title">직접 등록</span></h2>' in html
    assert 'data-i18n="media.register.direct.subtitle"' in html
    assert 'data-i18n="media.register.direct.field.category.label"' in html
    assert 'data-i18n="media.register.direct.action.save"' in html
    assert 'data-i18n="media.register.direct.action.reset"' in html
    assert '<h2 data-i18n="media.register.api_lookup.title">API 조회 / 등록' in html
    assert 'data-i18n="media.register.api_lookup.subtitle"' in html
    assert 'data-i18n="media.register.api_lookup.action.barcode_search"' in html
    assert 'data-page-help-open="register-purchase"' in html
    assert '<h2><span data-i18n="media.register.purchase.title">구매 내역 가져오기</span></h2>' in html
    assert 'data-i18n="media.register.purchase.action.preview"' in html
    assert 'data-i18n="media.register.purchase.action.save_queue"' in html
    assert 'data-page-help-open="register-batch"' in html
    assert '<h2><span data-i18n="media.register.batch.title">CSV 대량 등록</span></h2>' in html
    assert 'data-i18n="media.register.batch.action.upload"' in html
    assert '"media.source.title":' in html
    assert '"media.register.direct.title":' in html
    assert '"media.register.purchase.title":' in html
    assert '"media.register.batch.title":' in html


def test_media_source_and_register_form_labels_and_placeholders_use_i18n_keys():
    html = read_static_html("index.html")
    assert '<label for="sourceWorkbenchSourceState" data-i18n="media.source.field.scope.label">대상</label>' in html
    assert '<label for="sourceWorkbenchLimit" data-i18n="media.source.field.limit.label">대상 수</label>' in html
    assert '<label for="sourceWorkbenchCandidateLimit" data-i18n="media.source.field.candidate_limit.label">후보 수</label>' in html
    assert '<strong data-i18n="media.source.section.targets">보강 대상</strong>' in html
    assert '<strong data-i18n="media.source.section.queue">최근 보강 결과</strong>' in html
    assert '<button id="sourceWorkbenchQueueClearBtn" class="btn ghost" type="button" data-i18n="media.source.action.clear_queue">큐 비우기</button>' in html
    assert '<label for="quickArtist" data-i18n="media.register.direct.field.artist.label">아티스트명(필수)</label>' in html
    assert 'id="quickArtist" data-i18n-placeholder="media.register.direct.field.artist.placeholder"' in html
    assert '<label for="quickItemName" data-i18n="media.register.direct.field.item_name.label">상품명(필수)</label>' in html
    assert 'id="quickItemName" data-i18n-placeholder="media.register.direct.field.item_name.placeholder"' in html
    assert '<label for="queryArtist" data-i18n="media.register.api_lookup.field.artist.label">아티스트명</label>' in html
    assert 'id="queryArtist" tabindex="1" data-i18n-placeholder="media.register.api_lookup.field.artist.placeholder"' in html
    assert '<button id="querySearchBtn" class="btn ghost" type="button" data-i18n="media.register.api_lookup.action.query_search">조건 조회</button>' in html
    assert '<label for="purchaseImportFile" data-i18n="media.register.purchase.field.file.label">주문 파일</label>' in html
    assert '<label data-i18n="media.register.purchase.field.auto_detect.label">자동 판별</label>' in html
    assert '<strong data-i18n="media.register.purchase.section.preview">미리보기</strong>' in html
    assert '<h2 data-i18n="media.register.purchase.queue.title">구매 수입 큐</h2>' in html
    assert '<button id="purchaseImportQueueLoadBtn" class="btn ghost" type="button" data-i18n="media.register.purchase.queue.action.load">큐 불러오기</button>' in html
    assert '<label for="csvFile" data-i18n="media.register.batch.field.file.label">CSV 파일</label>' in html
    assert '<label for="csvNotes" data-i18n="media.register.batch.field.notes.label">노트</label>' in html
    assert '"media.source.field.scope.label":' in html
    assert '"media.register.direct.field.artist.placeholder":' in html
    assert '"media.register.purchase.queue.title":' in html
    assert '"media.register.batch.field.notes.label":' in html


def test_purchase_import_ui_mentions_paste_or_upload_and_extended_vendor_targets():
    html = read_static_html("index.html")
    assert '<p class="sub" data-i18n="media.register.purchase.subtitle">주문 페이지 원문을 붙여넣거나 파일로 올려 라이브러리 수입 큐로 연결합니다.</p>' in html
    assert 'id="purchaseImportVendorCode"' in html
    assert '<option value="OTHER" data-i18n="media.register.purchase.field.vendor.auto">자동 판별</option>' in html
    assert '<option value="ALADIN">알라딘</option>' in html
    assert '<option value="YES24">YES24</option>' in html
    assert '<option value="SAILMUSIC">Sailmusic</option>' not in html
    assert 'Amazon / eBay / Sailmusic' not in html
    assert '"media.register.purchase.subtitle":' in html


def test_purchase_import_payload_base_and_reset_include_manual_vendor_override():
    html = read_static_html("index.html")

    assert 'vendor_code: String($("purchaseImportVendorCode")?.value || "OTHER").trim().toUpperCase() || "OTHER",' in html
    assert '$("purchaseImportVendorCode").value = "OTHER";' in html


def test_source_workbench_bulk_apply_opens_diff_review_surface_markup():
    html = read_static_html("index.html")
    assert 'id="sourceWorkbenchDiffReview"' in html
    assert 'id="sourceWorkbenchDiffReviewList"' in html
    assert 'id="sourceWorkbenchDiffReviewSummary"' in html
    assert 'id="sourceWorkbenchDiffReviewSelectAllBtn"' in html
    assert 'id="sourceWorkbenchDiffReviewSelectEmptyBtn"' in html
    assert 'id="sourceWorkbenchDiffReviewClearBtn"' in html
    assert 'id="sourceWorkbenchDiffReviewCancelBtn"' in html
    assert 'id="sourceWorkbenchDiffReviewApplyBtn"' in html
    assert 'data-i18n="media.source.diff.title"' in html
    assert 'data-i18n="media.source.diff.action.select_all"' in html
    assert 'data-i18n="media.source.diff.action.select_empty"' in html
    assert 'data-i18n="media.source.diff.action.clear"' in html
    assert 'data-i18n="media.source.diff.action.cancel"' in html
    assert 'data-i18n="media.source.diff.action.apply_selected"' in html
    assert 'data-i18n="media.source.diff.note.title"' in html
    assert 'data-i18n="media.source.diff.note.body"' in html
    assert 'data-i18n="media.source.diff.footer.note"' in html
    assert '"media.source.diff.status.empty_fill":' in html
    assert '"media.source.diff.status.conflict":' in html
    assert '"media.source.diff.status.same":' in html
    assert '"media.source.diff.summary":' in html
    assert '"media.source.diff.card.current_title":' in html
    assert '"media.source.diff.field.item_title":' in html


def test_source_workbench_bulk_apply_wiring_opens_review_surface_only():
    html = read_static_html("index.html")
    assert 'let sourceWorkbenchDiffReviewState = null;' in html
    assert "function openSourceWorkbenchDiffReview(selectedRows) {" in html
    assert 'setStatus("sourceWorkbenchStatus", "ok", t("media.source.status.diff_review_open",' in html
    assert '$("sourceWorkbenchApplyBtn").addEventListener("click", openSourceWorkbenchDiffReviewForSelections);' in html
    assert '$("sourceWorkbenchAutoApplyBtn").addEventListener("click", runAutoReadySourceWorkbench);' in html
    assert 'await applySourceWorkbenchItems(autoRows, "AUTO_READY");' in html
    assert 'await applySourceWorkbenchItems([entry], "ROW_UPDATE");' in html


def test_source_workbench_edition_comparator_candidate_cards_render_summary_identity_and_evidence():
    html = read_static_html("index.html")
    source_block = html.split("function renderSourceWorkbenchList() {", 1)[1].split("async function loadSourceWorkbenchTargets()", 1)[0]
    assert "const comparatorRows = buildSourceWorkbenchEditionComparatorRows({ current: row, candidate });" in source_block
    assert "sourceWorkbenchEditionComparatorCardHtml({ summary: comparatorSummary, rows: comparatorRows, explanations: comparatorExplanations })" in source_block
    card_helper_block = html.split("function sourceWorkbenchEditionComparatorCardHtml(", 1)[1].split("function sourceWorkbenchEditionComparatorStateLabel", 1)[0]
    assert "item?.cardRole === \"identity_chip\"" in card_helper_block
    assert "item?.cardRole === \"evidence_preview\"" in card_helper_block
    assert "data-source-workbench-edition-summary" in card_helper_block

    result = call_js_comparator_card_fragment({
        "current": {
            "artist_or_brand": "Artist",
            "item_title": "Title",
            "catalog_no": "CAT-001",
            "barcode": "1234567890",
            "pressing_country": "Japan",
            "runout_matrix": ["A1", "A2", "A3", "A4"],
            "track_list": ["Intro", "Track A", "Track B", "Track C"],
        },
        "candidate": {
            "artist_or_brand": "Artist",
            "item_title": "Title",
            "catalog_no": "CAT-002",
            "barcode": "0987654321",
            "pressing_country": "Korea",
            "runout_matrix": ["A1", "B2", "B3", "C4"],
            "track_list": ["Intro", "Track A", "Track C", "Track D", "Track E"],
        },
    })
    card = result["comparatorCard"]
    assert "source-workbench-edition-summary" in card
    assert "source-workbench-edition-identity" in card
    assert "source-workbench-edition-evidence" in card
    assert "source-workbench-edition-identity-chip" in card
    assert "source-workbench-edition-evidence-row" in card
    assert "→" in card


def test_source_workbench_edition_comparator_card_surfaces_name_title_match_reasoning():
    result = call_js_comparator_card_fragment({
        "current": {
            "artist_or_brand": "Artist",
            "item_name_override": "Artist - Title",
            "catalog_no": "CAT-001",
        },
        "candidate": {
            "artist_or_brand": "Artist",
            "title": "Title",
            "catalog_no": "CAT-002",
        },
    })
    card = re.sub(r"\s+", " ", result["comparatorCard"]).lower()
    assert "evidence:" in card
    assert "name matches" in card


def test_source_workbench_edition_comparator_candidate_cards_surface_runout_and_track_compact_previews():
    result = call_js_comparator_card_fragment({
        "current": {
            "artist_or_brand": "Artist",
            "item_title": "Title",
            "runout_matrix": ["M1", "M2", "M3", "M4", "M5"],
            "track_list": ["One", "Two", "Three", "Four"],
        },
        "candidate": {
            "artist_or_brand": "Artist",
            "item_title": "Title",
            "runout_matrix": ["M1", "M9", "M4", "M5", "M8"],
            "track_list": ["One", "Two", "Three", "Four", "Five"],
        },
    })
    roles = {row["key"]: row["cardRole"] for row in result["roles"]}
    assert roles.get("runout_matrix") == "evidence_preview"
    assert roles.get("track_list") == "evidence_preview"

    card = result["comparatorCard"]
    assert "(+" in card
    assert "source-workbench-edition-evidence-row-values" in card
    assert re.search(r"\(\+\d+ more\)", card) is not None


def test_source_workbench_edition_comparator_non_identity_changed_fields_are_visible():
    result = call_js_comparator_card_fragment({
        "current": {
            "artist_or_brand": "Artist",
            "item_title": "Title",
            "label_name": "Riverman",
            "format_name": "LP",
            "format_items": [{"name": "LP", "qty": "1"}],
            "identifier_items": [{"type": "cat", "value": "ABC"}],
            "series": ["Original"],
            "company_items": [{"name": "LabelCo", "role": "publisher"}],
        },
        "candidate": {
            "artist_or_brand": "Artist",
            "item_title": "Title",
            "label_name": "Riverman Reissue",
            "format_name": "LP",
            "format_items": [{"name": "EP", "qty": "1"}],
            "identifier_items": [{"type": "cat", "value": "DEF"}],
            "series": ["Original"],
            "company_items": [{"name": "LabelCo", "role": "publisher"}],
        },
    })
    card = result["comparatorCard"]
    compact_card = re.sub(r"\s+", " ", card)
    assert "Label" in compact_card
    assert "Format items" in compact_card
    assert "Identifiers" in compact_card
    assert "Format items" in compact_card
    assert "source-workbench-edition-evidence-row" in card
    assert "Riverman" in compact_card
    assert "Riverman Reissue" in compact_card
    assert re.search(r"cat: abc", compact_card.lower()) is not None


def test_source_workbench_edition_comparator_missing_evidence_is_explicit_when_uncomparable():
    result = call_js_comparator_card_fragment({
        "current": {
            "artist_or_brand": "Artist",
            "item_title": "Title",
            "catalog_no": "CAT-001",
            "barcode": "123",
            "pressing_country": "KR",
        },
        "candidate": {
            "artist_or_brand": "Artist",
            "item_title": "Title",
            "catalog_no": "CAT-001",
            "barcode": "123",
            "pressing_country": "KR",
        },
    })
    card = re.sub(r"\s+", " ", result["comparatorCard"])
    assert "Format items" in card
    assert "Identifiers" in card
    assert "Series" in card
    assert "Companies" in card
    assert "uncomparable" in card
    assert re.search(r"Format items.*-.*→.*-", card) is not None
    assert re.search(r"Identifiers.*-.*→.*-", card) is not None
    assert re.search(r"Series.*-.*→.*-", card) is not None
    assert re.search(r"Companies.*-.*→.*-", card) is not None


def test_source_workbench_edition_comparator_card_shows_current_and_candidate_values():
    result = call_js_comparator_card_fragment({
        "current": {
            "artist_or_brand": "Artist",
            "item_title": "Title",
            "catalog_no": "CAT-001",
            "barcode": "880000000001",
            "pressing_country": "KR",
            "track_list": ["A", "B"],
        },
        "candidate": {
            "artist_or_brand": "Artist",
            "item_title": "Title",
            "catalog_no": "CAT-002",
            "barcode": "880000000001",
            "pressing_country": "JP",
            "track_list": ["A", "B", "C"],
        },
    })
    card = result["comparatorCard"]
    assert "CAT-001" in card
    assert "CAT-002" in card
    assert "880000000001" in card
    assert "KR" in card
    assert "JP" in card
    assert "A" in card
    assert "C" in card
    assert "source-workbench-edition-identity-chip" in card


def test_source_workbench_edition_comparator_missing_current_values_stay_visible_as_empty():
    result = call_js_comparator_card_fragment({
        "current": {
            "artist_or_brand": "Artist",
            "item_title": "Title",
        },
        "candidate": {
            "artist_or_brand": "Artist",
            "item_title": "Title",
            "catalog_no": "CAT-009",
            "pressing_country": "KR",
            "runout_matrix": ["SIDE-A", "SIDE-B"],
            "track_list": ["A", "B", "C"],
        },
    })
    card = result["comparatorCard"]
    compact_card = re.sub(r"\s+", " ", card)
    assert re.search(r"Catalog no.*-\s*→\s*CAT-009", compact_card) is not None
    assert re.search(r"Pressing country.*-\s*→\s*KR", compact_card) is not None
    assert re.search(r"Runout.*SIDE-A \| SIDE-B", compact_card) is not None
    assert re.search(r">-<.*SIDE-A \| SIDE-B", compact_card) is not None


def test_source_workbench_edition_comparator_copy_stays_advisory_without_source_trust_language():
    html = read_static_html("index.html")
    comparator_block = html.split("function buildSourceWorkbenchEditionComparatorSummary(payload = {}) {", 1)[1].split("function sourceWorkbenchEditionComparatorStateLabel", 1)[0]
    forbidden = ["판본", "trust", "tier", "likely", "confidence", "source-trust", "신뢰"]
    assert "No comparable edition evidence." in comparator_block
    for term in forbidden:
      assert term.lower() not in comparator_block.lower()

    result = call_js_comparator_card_fragment({
        "current": {
            "artist_or_brand": "Artist",
            "item_title": "Title",
            "catalog_no": "CAT-001",
            "pressing_country": "Japan",
        },
        "candidate": {
            "artist_or_brand": "Artist",
            "item_title": "Title",
            "barcode": "999",
            "pressing_country": "Korea",
        },
    })
    rendered_copy = f"{result['summary']} {result['comparatorCard']}".lower()
    for term in forbidden:
      assert term.lower() not in rendered_copy


def test_source_workbench_diff_review_confirm_wiring_uses_selected_fields_and_blocks_zero_selected_posts():
    html = read_static_html("index.html")
    submit_block = html.split("function submitSourceWorkbenchDiffReviewSelection() {", 1)[1].split("async function applySourceWorkbenchItems(", 1)[0]
    assert 'const selectedItems = buildSourceWorkbenchDiffApplyItems({ reviewState: sourceWorkbenchDiffReviewState });' in submit_block
    assert 'setStatus("sourceWorkbenchStatus", "err", t("media.source.status.diff_review_none_selected"));' in submit_block
    assert 'await applySourceWorkbenchItems(sourceWorkbenchDiffReviewState.items, "MANUAL_BATCH", {' in submit_block
    assert 'items: selectedItems,' in submit_block
    assert 'selectedFieldCount,' in submit_block
    assert 'closeSourceWorkbenchDiffReview();' in submit_block
    assert '"media.source.status.diff_review_none_selected":' in html


def test_source_workbench_review_apply_keeps_failed_review_items_open_for_retry():
    html = read_static_html("index.html")
    apply_block = html.split("async function applySourceWorkbenchItems(selectedRows, mode, opts = {}) {", 1)[1].split("async function applySingleSourceWorkbenchRow(", 1)[0]
    assert 'function updateSourceWorkbenchDiffReviewStateAfterApply(payload = {}) {' in html
    assert 'if (mode === "MANUAL_BATCH" && failed.length) {' in apply_block
    assert 'sourceWorkbenchDiffReviewState = updateSourceWorkbenchDiffReviewStateAfterApply({' in apply_block
    assert 'renderSourceWorkbenchDiffReview();' in apply_block
    assert 'return false;' in apply_block


def test_media_source_and_purchase_status_copy_and_table_headers_use_i18n():
    html = read_static_html("index.html")
    assert '<th data-i18n="media.register.purchase.preview.header.cover">커버</th>' in html
    assert '<th data-i18n="media.register.purchase.preview.header.item_name">상품명</th>' in html
    assert '<th data-i18n="media.register.purchase.queue.header.status">상태</th>' in html
    assert '<button id="purchaseImportQueueFetchAllCandidatesBtn" class="btn ghost" type="button" data-i18n="media.register.purchase.queue.action.fetch_all_candidates">후보 일괄 조회</button>' in html
    assert 't("media.register.purchase.status.file_ready", { name: file.name })' in html
    assert 't("media.register.purchase.status.preview_loading")' in html
    assert 't("media.register.purchase.status.preview_complete",' in html
    assert 't("media.register.purchase.status.queue_save_loading")' in html
    assert 't("media.source.status.targets_loading")' in html
    assert 't("media.source.status.targets_loaded",' in html
    assert 't("media.source.status.candidates_loading",' in html
    assert 't("media.source.status.fetch_all_loading",' in html
    assert 't("media.source.status.apply_loading",' in html
    assert '"media.register.purchase.preview.header.cover":' in html
    assert '"media.register.purchase.status.preview_loading":' in html
    assert '"media.source.status.targets_loading":' in html


def test_media_source_and_purchase_row_level_actions_use_i18n():
    html = read_static_html("index.html")
    purchase_block = html.split("function renderPurchaseImportQueueDetails(row, state) {", 1)[1].split("function renderPurchaseImportQueue(items) {", 1)[0]
    source_block = html.split("function renderSourceWorkbenchList() {", 1)[1].split("async function loadSourceWorkbenchTargets()", 1)[0]
    assert 't("media.register.purchase.queue.details.title")' in purchase_block
    assert 't("media.register.purchase.queue.details.query_prefix"' in purchase_block
    assert 't("media.register.purchase.queue.action.lookup_candidates")' in purchase_block
    assert 't("media.register.purchase.queue.field.artist_override.label")' in purchase_block
    assert 't("media.register.purchase.queue.action.create_from_candidate")' in purchase_block
    assert 't("media.source.field.artist_override.label")' in source_block
    assert 't("media.source.field.item_override.label")' in source_block
    assert 't("media.source.action.lookup_candidates")' in source_block
    assert 't("media.source.action.reset_search")' in source_block
    assert 't("media.source.status.no_candidates_yet")' in source_block
    assert '"media.register.purchase.queue.details.title":' in html
    assert '"media.source.field.artist_override.label":' in html


def test_purchase_queue_remaining_runtime_status_copy_uses_i18n():
    html = read_static_html("index.html")
    runtime_block = html.split("async function enrichPurchaseImportFromItemPage(queueId) {", 1)[1].split("function dashboardMoveKindLabel", 1)[0]
    assert 't("media.register.purchase.queue.status.enrich_loading"' in runtime_block
    assert 't("media.register.purchase.queue.status.enrich_complete"' in runtime_block
    assert 't("media.register.purchase.queue.status.create_loading"' in runtime_block
    assert 't("media.register.purchase.queue.status.create_complete"' in runtime_block
    assert 't("media.register.purchase.queue.status.lookup_loading"' in runtime_block
    assert 't("media.register.purchase.queue.status.lookup_complete"' in runtime_block
    assert 't("media.register.purchase.queue.status.lookup_none_pending")' in runtime_block
    assert 't("media.register.purchase.queue.status.lookup_fetch_all_loading"' in runtime_block
    assert 't("media.register.purchase.queue.status.lookup_fetch_all_complete"' in runtime_block
    assert 't("media.register.purchase.queue.status.apply_artist_empty")' in runtime_block
    assert 't("media.register.purchase.queue.status.apply_artist_complete"' in runtime_block
    assert 't("media.register.purchase.queue.status.select_complete"' in runtime_block
    assert 't("media.register.purchase.queue.status.create_candidate_requires_selection")' in runtime_block
    assert 't("media.register.purchase.queue.status.create_candidate_loading"' in runtime_block
    assert 't("media.register.purchase.queue.status.create_candidate_complete"' in runtime_block
    assert 't("media.register.purchase.queue.status.ignore_loading"' in runtime_block
    assert 't("media.register.purchase.queue.status.ignore_complete"' in runtime_block
    assert '"media.register.purchase.queue.status.enrich_loading":' in html
    assert '"media.register.purchase.queue.status.create_candidate_complete":' in html


def test_operator_and_ops_runtime_status_copy_uses_i18n():
    html = read_static_html("index.html")
    operator_block = html.split("async function routeGlobalBarcodeScanForOps(barcode) {", 1)[1].split("function purchaseImportVendorLabel", 1)[0]
    meta_sync_block = html.split("function renderMetadataSyncSummary(data) {", 1)[1].split("function resolveOwnedAlbumName", 1)[0]
    ops_actions_block = html.split('$("appLogoutBtn").addEventListener("click", logoutAppSession);', 1)[1].split('$("homeMasterAddResults").addEventListener("click", async (e) => {', 1)[0]

    assert 't("operator.lookup.status.barcode_loading")' in operator_block
    assert 't("operator.lookup.status.loading")' in operator_block
    assert 't("operator.lookup.status.complete",' in operator_block
    assert 'errorMessageText(err, t("operator.lookup.status.search_failed"))' in operator_block
    assert 't("operator.weather.empty.kicker")' in operator_block
    assert 't("operator.weather.status.loading")' in operator_block
    assert 't("operator.weather.status.office")' in operator_block
    assert 'responseDetailText(data, t("operator.weather.status.office_load_failed"))' in operator_block
    assert 'errorMessageText(err, t("operator.weather.status.office_load_failed"))' in operator_block

    assert 't("ops.meta_sync.status.load_loading")' in meta_sync_block
    assert 't("ops.meta_sync.status.load_complete",' in meta_sync_block
    assert 't("ops.meta_sync.status.run_loading")' in meta_sync_block
    assert 't("ops.meta_sync.status.run_complete",' in meta_sync_block

    assert 't("ops.exception.status.reset_defaults")' in ops_actions_block
    assert 't("ops.exception.status.preset_name_required")' in ops_actions_block
    assert 't("ops.exception.status.preset_saved",' in ops_actions_block
    assert 't("ops.exception.status.preset_select_required")' in ops_actions_block
    assert 't("ops.exception.status.preset_applied",' in ops_actions_block
    assert 't("ops.exception.status.preset_default_required")' in ops_actions_block
    assert 't("ops.exception.status.preset_default_saved",' in ops_actions_block
    assert 't("ops.exception.status.preset_delete_required")' in ops_actions_block
    assert 't("ops.exception.status.preset_deleted",' in ops_actions_block
    assert 't("ops.account.status.default_readonly",' in html

    assert '"operator.lookup.status.barcode_loading":' in html
    assert '"operator.weather.status.load_failed":' in html
    assert '"ops.meta_sync.status.run_complete":' in html
    assert '"ops.exception.status.preset_deleted":' in html
    assert '"ops.account.status.default_readonly":' in html


def test_operator_focus_and_weather_runtime_copy_use_i18n():
    html = read_static_html("index.html")
    operator_block = html.split("function hasOperatorCurrentLocation(row) {", 1)[1].split("function renderOpsLibraryContextSlotPreviewContent(item, rows, options = {}) {", 1)[0]

    assert 'return buildOperatorSlotDisplayLabel(' in operator_block
    assert 'return t("operator.feed.state.unslotted");' in html
    assert 't("operator.focus.count.location",' in operator_block
    assert '"operator.focus.count.recent_move_hour"' in operator_block
    assert '"operator.focus.count.recent_move_day"' in operator_block
    assert 't("operator.focus.count.recent_registration",' in operator_block
    assert 'responseDetailText(data, t("operator.weather.status.office_load_failed"))' in operator_block
    assert 't("operator.weather.office.updated",' in html
    assert 't("operator.weather.office.updated_now")' in html
    assert 'responseDetailText(data, t("operator.lookup.status.feed_failed"))' in html
    assert 'setStatus("operatorRequestStatus", "err", t("operator.feed.state.read_only"))' in html

    assert '"operator.focus.count.location":' in html
    assert '"operator.focus.count.recent_move_hour":' in html
    assert '"operator.focus.count.recent_move_day":' in html
    assert '"operator.focus.count.recent_registration":' in html
    assert '"operator.weather.status.office_load_failed":' in html
    assert '"operator.weather.office.updated":' in html
    assert '"operator.weather.office.updated_now":' in html


def test_collectibles_and_ops_manuals_use_i18n_keys():
    html = read_static_html("index.html")
    assert 'data-i18n="manual.collectibles.summary"' in html
    assert 'data-i18n="manual.collectibles.item4"' in html
    assert 'data-i18n="manual.ops.summary"' in html
    assert 'data-i18n="manual.ops.cabinet.summary"' in html
    assert 'data-i18n="manual.ops.camera.summary"' in html
    assert 'data-i18n="manual.ops.slot.summary"' in html
    assert 'data-i18n="manual.ops.exception.summary"' in html
    assert 'data-i18n="manual.ops.account.summary"' in html
    assert 'data-i18n="manual.ops.export.summary"' in html
    assert 'data-i18n="manual.ops.meta_sync.summary"' in html


def test_collectibles_and_ops_help_dots_use_help_keys():
    html = read_static_html("index.html")
    assert 'data-page-help-open="collectibles"' in html
    assert 'data-page-help-open="ops-system"' in html
    assert 'data-page-help-open="ops-cabinet"' in html
    assert 'data-page-help-open="ops-camera"' in html
    assert 'data-page-help-open="ops-slot"' in html
    assert 'data-page-help-open="ops-exception"' in html
    assert 'data-page-help-open="ops-account"' in html
    assert 'data-page-help-open="ops-export"' in html
    assert 'data-help-key="help.ops.restore"' in html



def test_collectibles_and_ops_primary_controls_use_i18n_keys():
    html = read_static_html("index.html")
    assert 'id="goodsSearchModeBtn" class="subtab-btn active" type="button" data-i18n="collectibles.mode.search"' in html
    assert 'id="goodsManageModeBtn" class="subtab-btn" type="button" data-i18n="collectibles.mode.manage"' in html
    assert 'id="goodsRegisterModeBtn" class="subtab-btn" type="button" data-i18n="collectibles.mode.register"' in html
    assert 'id="goodsSearchRunBtn" class="btn secondary icon-btn" type="button" data-i18n-title="common.search" data-i18n-aria-label="common.search"' in html
    assert 'id="goodsSearchResetBtn" class="btn ghost icon-symbol-btn icon-symbol-btn--reset" type="button" title="비우기" aria-label="비우기" data-i18n="common.clear" data-i18n-title="common.clear" data-i18n-aria-label="common.clear"' in html
    assert 'data-i18n="collectibles.search.results_heading"' in html
    assert 'id="goodsManageEmptyState" class="card admin-manage-empty-state active"' in html
    assert 'data-i18n="collectibles.manage.empty_title"' in html
    assert 'data-i18n="collectibles.manage.empty_body"' in html
    assert 'id="opsCabinetTabBtn" class="subtab-btn active" type="button" data-i18n="ops.subtab.cabinet"' in html
    assert 'id="opsSlotTabBtn" class="subtab-btn" type="button" data-i18n="ops.subtab.slot"' in html
    assert 'id="opsCameraTabBtn" class="subtab-btn" type="button" data-i18n="ops.subtab.camera"' in html
    assert 'id="opsExceptionTabBtn" class="subtab-btn" type="button" data-i18n="ops.subtab.exception"' in html
    assert 'id="opsAccountTabBtn" class="subtab-btn" type="button" data-i18n="ops.subtab.account"' in html
    assert 'id="opsProviderTabBtn" class="subtab-btn" type="button" data-i18n="ops.subtab.providers"' in html
    assert 'id="opsExportTabBtn" class="subtab-btn" type="button" data-i18n="ops.subtab.export"' in html
    assert 'id="opsMetaSyncTabBtn" class="subtab-btn" type="button" data-i18n="ops.subtab.meta_sync"' in html


def test_collectibles_search_actions_align_to_right_edge():
    html = read_static_html("index.html")
    actions_block = html.split(".goods-search-actions {", 1)[1].split("}", 1)[0]
    actions_button_block = html.split(".goods-search-actions > .btn,", 1)[1].split("}", 1)[0]
    assert "display: flex;" in actions_block
    assert "justify-content: flex-end;" in actions_block
    assert "margin-top: 10px;" in actions_block
    assert "flex: 1;" in actions_button_block
    assert "min-width: 110px;" in actions_button_block
    assert '<div class="ops-compact-form-actions goods-search-actions">' in html


def test_collectibles_dynamic_status_messages_use_i18n_keys():
    html = read_static_html("index.html")
    assert 't("collectibles.search.loading")' in html
    assert 't("collectibles.search.empty")' in html
    assert 't("collectibles.status.search.loading")' in html
    assert 't("collectibles.status.search.complete", { count: formatCount(goodsSearchTotalCount) })' in html
    assert 't("collectibles.manage.status.loading", { id: targetId })' in html
    assert 't("collectibles.manage.status.save_progress")' in html
    assert 't("collectibles.manage.status.delete_confirm", { name: goodsName })' in html
    assert 't("collectibles.mapping.status.save_complete", { id: goodsItemId })' in html
    assert 't("collectibles.register.status.save_progress")' in html
    assert 't("collectibles.register.status.start_linked", { id: masterId })' in html
    assert '"collectibles.search.loading":' in html
    assert '"collectibles.manage.status.loading":' in html
    assert '"collectibles.mapping.status.save_complete":' in html
    assert '"collectibles.register.status.start_independent":' in html


def test_collectibles_search_uses_compact_two_row_density_layout():
    html = read_static_html("index.html")
    assert '<div class="ops-compact-form-grid goods-search-compact-grid">' in html
    assert '<div class="ops-compact-form-row goods-search-compact-row--primary" data-density-role="collectibles-search-primary">' in html
    assert '<div class="ops-compact-form-row goods-search-compact-row--secondary" data-density-role="collectibles-search-secondary">' in html
    assert html.count('data-density-role="collectibles-search-primary"') == 1
    assert html.count('data-density-role="collectibles-search-secondary"') == 1


def test_collectibles_register_uses_compact_core_and_extra_layout():
    html = read_static_html("index.html")
    assert '<div id="goodsRegisterCoreFields" class="ops-compact-form-grid goods-register-compact-grid"' in html
    assert '<div id="goodsRegisterCoreRowA" class="ops-compact-form-row goods-register-compact-row--primary">' in html
    assert '<div id="goodsRegisterCoreRowB" class="ops-compact-form-row goods-register-compact-row--secondary">' in html
    assert '<details id="goodsRegisterExtraFields" class="ops-compact-extra-fields goods-extra-fields">' in html
    assert '<div class="ops-compact-extra-fields-body goods-form-grid">' in html


def test_direct_register_uses_compact_core_and_extra_layout():
    html = read_static_html("index.html")
    assert '<div id="quickRegisterCoreRowA" class="ops-compact-form-row quick-register-compact-row--primary">' in html
    assert '<div id="quickRegisterCoreRowB" class="ops-compact-form-row quick-register-compact-row--secondary"' in html
    assert '<details id="quickRegisterExtraFields" class="ops-compact-extra-fields"' in html
    assert '<div class="ops-compact-extra-fields-body">' in html
    assert '<div class="quick-register-extra-grid">' in html


def test_ops_compact_density_common_classes_exist():
    html = read_static_html("index.html")
    assert ".ops-compact-form-grid {" in html
    assert ".ops-compact-form-actions {" in html
    assert ".ops-compact-extra-fields {" in html


def test_collectibles_form_labels_and_placeholders_use_i18n_keys():
    html = read_static_html("index.html")
    assert '<label for="goodsSearchQuery" data-i18n="collectibles.search.field.query.label">검색어</label>' in html
    assert 'id="goodsSearchQuery" data-i18n-placeholder="collectibles.search.field.query.placeholder"' in html
    assert '<label for="goodsSearchArtist" data-i18n="collectibles.search.field.artist.label">연계 아티스트</label>' in html
    assert 'id="goodsSearchArtist" data-i18n-placeholder="collectibles.search.field.artist.placeholder"' in html
    assert '<label for="goodsManageName" data-i18n="collectibles.manage.field.name.label">컬렉터블명</label>' in html
    assert 'id="goodsManageName" data-i18n-placeholder="collectibles.manage.field.name.placeholder"' in html
    assert '<label for="goodsManageDescription" data-i18n="collectibles.manage.field.description.label">설명</label>' in html
    assert 'id="goodsManageDescription" data-i18n-placeholder="collectibles.manage.field.description.placeholder"' in html
    assert '<label for="goodsRegisterName" data-i18n="collectibles.register.field.name.label">컬렉터블명</label>' in html
    assert 'id="goodsRegisterName" data-i18n-placeholder="collectibles.register.field.name.placeholder"' in html
    assert '<label for="goodsRegisterArtistNames" data-i18n="collectibles.register.field.artist_names.label">연계 아티스트명(쉼표 구분)</label>' in html
    assert 'id="goodsRegisterArtistNames" data-i18n-placeholder="collectibles.register.field.artist_names.placeholder"' in html
    assert '"collectibles.search.field.query.label":' in html
    assert '"collectibles.manage.field.description.placeholder":' in html
    assert '"collectibles.register.field.artist_names.placeholder":' in html


def test_ops_core_form_labels_and_buttons_use_i18n_keys():
    html = read_static_html("index.html")
    assert 'data-page-help-open="ops-cabinet"' in html
    assert '<h2><span data-i18n="ops.cabinet.title">장식장 등록</span></h2>' in html
    assert '<label for="opsCabinetName" data-i18n="ops.cabinet.field.name.label">장식장명</label>' in html
    assert 'id="opsCabinetName" data-i18n-placeholder="ops.cabinet.field.name.placeholder"' in html
    assert 'id="opsCabinetSaveBtn" class="btn" type="button" data-i18n="ops.cabinet.action.save"' in html
    assert 'id="opsCabinetResetBtn" class="btn ghost icon-symbol-btn icon-symbol-btn--reset" type="button" title="입력 초기화" aria-label="입력 초기화" data-i18n="ops.cabinet.action.reset" data-i18n-title="ops.cabinet.action.reset" data-i18n-aria-label="ops.cabinet.action.reset"' in html

    assert 'data-page-help-open="ops-camera"' in html
    assert '<h2><span data-i18n="ops.camera.title">공용 카메라 설정</span></h2>' in html
    assert '<label for="opsCameraName" data-i18n="ops.camera.field.name.label">카메라명</label>' in html
    assert 'id="opsCameraName" data-i18n-placeholder="ops.camera.field.name.placeholder"' in html
    assert 'id="opsCameraSaveBtn" class="btn" type="button" data-i18n="ops.camera.action.save"' in html

    assert 'data-page-help-open="ops-slot"' in html
    assert '<h2><span data-i18n="ops.slot.title">개별 슬롯 관리</span></h2>' in html
    assert '<label for="opsSlotCabinetName" data-i18n="ops.slot.field.cabinet_name.label">장식장명</label>' in html
    assert 'id="opsSlotCabinetName" data-i18n-placeholder="ops.slot.field.cabinet_name.placeholder"' in html
    assert 'id="opsSlotSaveBtn" class="btn" type="button" data-i18n="ops.slot.action.save"' in html

    assert '"ops.cabinet.field.name.label":' in html
    assert '"ops.camera.field.name.placeholder":' in html
    assert '"ops.slot.action.save":' in html


def test_ops_backup_and_restore_runtime_status_copy_uses_i18n():
    html = read_static_html("index.html")
    block = html.split("async function loadOpsBackupSettings() {", 1)[1].split('$("tabHomeBtn").addEventListener("click", () => openAdminConsole("home"));', 1)[0]

    assert 't("ops.restore.status.load_failed")' in block
    assert 't("ops.restore.summary.auto_on",' in block
    assert 't("ops.restore.summary.auto_off")' in block
    assert 't("ops.restore.summary.scope_full")' in block
    assert 't("ops.restore.summary.scope_db")' in block
    assert 't("ops.restore.summary.include_env")' in block
    assert 't("ops.restore.summary.exclude_env")' in block
    assert 't("ops.restore.summary.path",' in block
    assert 't("ops.restore.summary.last_at",' in block
    assert 't("ops.restore.summary.last_path",' in block
    assert 't("ops.restore.summary.empty")' in block
    assert 't("ops.restore.status.load_complete")' in block
    assert 't("ops.restore.status.dir_required")' in block
    assert 't("ops.restore.status.save_loading")' in block
    assert 't("ops.restore.status.save_complete")' in block
    assert 't("ops.export.status.full_prepare")' in block
    assert 't("ops.export.status.full_started",' in block
    assert 't("ops.export.status.full_failed")' in block
    assert 't("ops.restore.status.db_file_required")' in block
    assert 't("ops.restore.status.db_cancelled")' in block
    assert 't("ops.restore.status.db_uploading")' in block
    assert 't("ops.restore.status.db_complete",' in block
    assert 't("ops.restore.status.db_failed")' in block
    assert 't("ops.restore.status.bundle_file_required")' in block
    assert 't("ops.restore.status.bundle_cancelled")' in block
    assert 't("ops.restore.status.bundle_uploading")' in block
    assert 't("ops.restore.status.bundle_complete",' in block
    assert 't("ops.restore.status.bundle_failed")' in block
    assert 't("ops.export.status.db_prepare")' in block
    assert 't("ops.export.status.db_started",' in block
    assert 't("ops.export.status.db_failed")' in block
    assert 't("ops.export.status.owned_csv_prepare")' in block
    assert 't("ops.export.status.owned_csv_started",' in block
    assert 't("ops.export.status.owned_csv_failed")' in block
    assert 't("ops.export.status.master_csv_prepare")' in block
    assert 't("ops.export.status.master_csv_started",' in block
    assert 't("ops.export.status.master_csv_failed")' in block

    assert '"ops.restore.status.load_failed":' in html
    assert '"ops.restore.summary.auto_on":' in html
    assert '"ops.export.status.full_prepare":' in html
    assert '"ops.restore.status.bundle_complete":' in html
    assert '"ops.export.status.master_csv_failed":' in html


def test_operator_dashboard_and_ops_system_static_copy_use_i18n_keys():
    html = read_static_html("index.html")
    assert 'data-page-help-open="dashboard"' in html
    assert '<h2><span data-i18n="dashboard.overview.title">라이브러리 현황판</span></h2>' in html
    assert '<h3><span data-i18n="dashboard.slot_occupancy.title">장식장 / 슬롯 점유</span><span class="section-help-dot"' in html
    assert '<h4 id="homeDashSlotItemsTitle"><span data-i18n="dashboard.cover_flow.title">커버 플로우</span><span class="section-help-dot"' in html
    assert '<h3><span data-i18n="dashboard.workbench.title">이동 작업대</span><span class="section-help-dot"' in html
    assert 'data-page-help-open="ops-home"' in html
    assert '<strong data-i18n="operator.lookup.panel_title">운영 홈 조회</strong>' in html
    assert '<h2><span data-i18n="shared_camera.preview.title">공용 카메라</span><span class="section-help-dot"' in html
    assert 'data-page-help-open="ops-system"' in html
    assert '<h2><span data-i18n="ops.system.title">시스템 상태</span></h2>' in html
    assert 'data-i18n="ops.system.action.reload"' in html
    assert 'id="opsSystemStatusSummary" class="dashboard-selection-summary" data-i18n="ops.system.summary.idle"' in html
    assert 'id="opsSystemStatusLine" class="compact-line" style="margin-top:6px;" data-i18n="ops.system.line.load"' in html
    assert 'id="opsQaStatusLine" class="compact-line" style="margin-top:6px;" data-i18n="ops.system.line.qa"' in html
    assert '"dashboard.overview.title":' in html
    assert '"operator.lookup.panel_title":' in html
    assert '"ops.system.summary.idle":' in html


def test_operator_dashboard_and_home_primary_controls_use_i18n_keys():
    html = read_static_html("index.html")
    assert 'data-i18n="dashboard.overview.subtitle"' in html
    assert 'id="homeOpenManageBtn" class="btn ghost icon-btn" type="button" data-i18n-title="dashboard.action.search" data-i18n-aria-label="dashboard.action.search"' in html
    assert 'id="homeOpenRegisterBtn" class="btn icon-btn" type="button" data-i18n-title="dashboard.action.new_item" data-i18n-aria-label="dashboard.action.new_item"' in html
    assert 'data-i18n="dashboard.card.library"' in html
    assert 'data-i18n="dashboard.card.media_collectibles"' in html
    assert 'data-i18n="dashboard.card.placement"' in html
    assert 'data-i18n="dashboard.card.collector"' in html
    assert 'data-i18n="dashboard.card.source"' in html
    assert 'data-i18n="dashboard.slot_window.hint"' in html
    assert 'data-i18n="dashboard.mapping.title"' in html
    assert 'data-i18n="dashboard.mapping.subtitle"' in html
    assert 'data-i18n="dashboard.mapping.legend.lp"' not in html
    assert 'data-i18n="dashboard.mapping.legend.cd"' not in html
    assert 'data-i18n="dashboard.mapping.legend.free"' in html
    assert 'data-i18n="dashboard.mapping.legend.size_lp"' in html
    assert 'data-i18n="dashboard.mapping.legend.size_book"' in html
    assert 'data-i18n="dashboard.mapping.legend.size_oversize"' in html
    assert 'data-i18n="dashboard.mapping.legend.size_cassette"' in html
    assert 'data-i18n="dashboard.mapping.legend.size_goods"' in html
    assert 'data-i18n="dashboard.cabinet.action.close"' in html
    assert 'data-i18n="dashboard.cover_flow.meta_idle"' in html
    assert 'data-i18n="dashboard.view_group.title"' in html
    assert 'data-i18n="dashboard.view.shelf"' in html
    assert 'data-i18n="dashboard.view.thumb"' in html
    assert 'data-i18n="dashboard.view.list"' in html
    assert 'data-i18n="dashboard.workbench.meta"' in html
    assert 'data-i18n="dashboard.workbench.mode.unslotted"' in html
    assert 'data-i18n="dashboard.workbench.mode.search_results"' in html
    assert 'data-i18n="dashboard.workbench.field.category.label"' in html
    assert 'data-i18n-placeholder="dashboard.workbench.field.artist.placeholder"' in html
    assert 'data-i18n="operator.lookup.summary_fields"' in html
    assert 'data-i18n="operator.lookup.field.query.label"' in html
    assert 'data-i18n-placeholder="operator.lookup.field.query.placeholder"' in html
    assert 'data-i18n-title="operator.lookup.action.run"' in html
    assert 'data-i18n-aria-label="operator.lookup.action.run"' in html
    assert 'data-i18n="operator.lookup.action.reset"' in html
    assert 'data-i18n="operator.feed.heading.recent_registered"' in html
    assert 'id="operatorLookupSortMode"' in html
    assert 'data-i18n="operator.context.title"' in html


def test_dashboard_stats_and_slot_mapping_defaults_use_i18n_keys():
    html = read_static_html("index.html")
    assert 'data-i18n="dashboard.stat.in_collection"' in html
    assert 'data-i18n="dashboard.stat.recent_30"' in html
    assert 'data-i18n="dashboard.stat.media"' in html
    assert 'data-i18n="dashboard.stat.slotted"' in html
    assert 'data-i18n="dashboard.stat.unslotted"' in html
    assert 'data-i18n="dashboard.stat.signed"' in html
    assert 'data-i18n="dashboard.stat.second_hand"' in html
    assert 'data-i18n-aria-label="dashboard.mapping.nav.prev"' in html
    assert 'data-i18n-aria-label="dashboard.mapping.nav.next"' in html
    assert 'data-i18n="dashboard.cabinet.detail"' in html
    assert 'data-i18n="dashboard.selection.summary.zero"' in html
    assert '"dashboard.stat.in_collection":' in html
    assert '"dashboard.mapping.nav.prev":' in html
    assert '"dashboard.selection.summary.zero":' in html


def test_collectibles_static_form_labels_and_options_use_i18n_keys():
    html = read_static_html("index.html")
    assert '<div class="goods-mode-tabs" role="tablist" aria-label="컬렉터블 화면 모드" data-i18n-aria-label="collectibles.mode.aria">' in html
    assert '<label for="goodsSearchCategory" data-i18n="collectibles.search.field.category.label">카테고리</label>' in html
    assert '<label for="goodsSearchStatusFilter" data-i18n="collectibles.search.field.status.label">상태</label>' in html
    assert '<label for="goodsSearchLabel" data-i18n="collectibles.search.field.label.label">연계 레이블</label>' in html
    assert '<label for="goodsSearchAlbumMasterId" data-i18n="collectibles.search.field.album_master_id.label">연계 마스터 ID</label>' in html
    assert '<label for="goodsSearchLinkedState" data-i18n="collectibles.search.field.linked_state.label">연계 상태</label>' in html
    assert '<label for="goodsSearchStorageSlotId" data-i18n="collectibles.search.field.slot_id.label">보관 슬롯</label>' in html
    assert '<label for="goodsManageCategory" data-i18n="collectibles.manage.field.category.label">카테고리</label>' in html
    assert '<label for="goodsManageQuantity" data-i18n="collectibles.manage.field.quantity.label">수량</label>' in html
    assert '<label for="goodsManageStatus" data-i18n="collectibles.manage.field.status.label">상태</label>' in html
    assert '<label for="goodsManageMemoryNote" data-i18n="collectibles.manage.field.memory_note.label">메모</label>' in html
    assert '<strong data-i18n="collectibles.manage.map.album_master.title">마스터 매핑</strong>' in html
    assert '<strong data-i18n="collectibles.manage.map.artist.title">아티스트 매핑</strong>' in html
    assert '<strong data-i18n="collectibles.manage.map.label.title">레이블 매핑</strong>' in html
    assert '<button id="goodsManageSaveMappingsBtn" class="btn ghost" type="button" data-i18n="collectibles.manage.action.save_mappings">매핑 저장</button>' in html
    assert '<div class="mini" data-i18n="collectibles.register.intro">컬렉터블을 먼저 독립 레코드로 등록하고, 필요하면 생성 시점에 기본 매핑을 함께 넣습니다.</div>' in html
    assert '<label for="goodsRegisterCategory" data-i18n="collectibles.register.field.category.label">카테고리</label>' in html
    assert '<label for="goodsRegisterQuantity" data-i18n="collectibles.register.field.quantity.label">수량</label>' in html
    assert '<label for="goodsRegisterStatus" data-i18n="collectibles.register.field.status.label">상태</label>' in html
    assert '<label for="goodsRegisterDescription" data-i18n="collectibles.register.field.description.label">설명</label>' in html
    assert '<label for="goodsRegisterLabelNames" data-i18n="collectibles.register.field.label_names.label">연계 레이블명(쉼표 구분)</label>' in html
    assert '"collectibles.search.field.category.label":' in html
    assert '"collectibles.manage.map.album_master.title":' in html
    assert '"collectibles.register.field.label_names.label":' in html


def test_collectibles_register_core_row_keeps_mapping_fields_in_optional_details():
    html = read_static_html("index.html")
    register_row_b = html.split('id="goodsRegisterCoreRowB"', 1)[1].split('id="goodsRegisterSaveBtn"', 1)[0]
    extra_details = html.split('id="goodsRegisterExtraFields"', 1)[1].split('id="goodsRegisterStatusLine"', 1)[0]

    assert 'goodsRegisterAlbumMasterId' in register_row_b
    assert 'goodsRegisterArtistNames' in register_row_b
    assert 'goodsRegisterLabelNames' in register_row_b
    assert 'goodsRegisterAlbumMasterId' not in extra_details
    assert 'goodsRegisterArtistNames' not in extra_details
    assert 'goodsRegisterLabelNames' not in extra_details


def test_media_register_static_form_labels_use_i18n_keys():
    html = read_static_html("index.html")
    assert '<label for="quickQuantity" data-i18n="media.register.direct.field.quantity.label">수량</label>' in html
    assert '<label for="quickSlotId" data-i18n="media.register.direct.field.slot_id.label">보관 슬롯(선택)</label>' in html
    assert '<label for="quickLabelName" data-i18n="media.register.direct.field.label_name.label">레이블(선택)</label>' in html
    assert 'id="quickLabelName" data-i18n-placeholder="media.register.direct.field.label_name.placeholder"' in html
    assert '<label for="quickReleasedDate" data-i18n="media.register.direct.field.released_date.label">발매일(선택)</label>' in html
    assert '<label for="quickDomainCode" data-i18n="media.register.direct.field.domain.label">도메인(선택)</label>' in html
    assert '<label for="metaSourceFilter" data-i18n="media.register.api_lookup.field.source.label">검색 소스</label>' in html
    assert '<label for="barcodeLimit" data-i18n="media.register.api_lookup.field.limit.label">개수</label>' in html
    assert '<label for="barcodeInput" data-i18n="media.register.api_lookup.field.barcode.label">바코드</label>' in html
    assert 'id="adminBarcodeInputState" class="admin-barcode-input-state" data-i18n="media.register.api_lookup.field.barcode.idle">스캔 대기</div>' in html
    assert '<label for="queryTitle" data-i18n="media.register.api_lookup.field.title.label">상품명</label>' in html
    assert '<label for="queryCatalog" data-i18n="media.register.api_lookup.field.catalog.label">카탈로그번호</label>' in html
    assert '<strong data-i18n="media.register.api_lookup.candidate.title">후보 확인</strong>' in html
    assert '<strong data-i18n="media.register.api_lookup.placement.title">추천 위치</strong>' in html
    assert '<strong data-i18n="media.register.api_lookup.results.title">조회 결과</strong>' in html
    assert '<label for="purchaseImportEmailFrom" data-i18n="media.register.purchase.field.email_from.label">발신자(선택)</label>' in html
    assert '<label for="purchaseImportRawContent" data-i18n="media.register.purchase.field.raw_content.label">원문 붙여넣기</label>' in html
    assert 'id="purchaseImportResetBtn" class="btn ghost icon-symbol-btn icon-symbol-btn--reset" type="button" title="입력 비우기" aria-label="입력 비우기" data-i18n="media.register.purchase.action.reset" data-i18n-title="media.register.purchase.action.reset" data-i18n-aria-label="media.register.purchase.action.reset"' in html
    assert '<p class="sub" data-i18n="media.register.batch.subtitle">파일 업로드 후 자동 매칭/검수 큐 적재까지 한 번에 실행됩니다.</p>' in html
    assert '<label for="csvDefaultCategory" data-i18n="media.register.batch.field.default_category.label">기본 카테고리(옵션)</label>' in html
    assert '<label for="csvCreatedBy" data-i18n="media.register.batch.field.created_by.label">등록자</label>' in html
    assert '<h2 data-i18n="media.register.review.title">검수 큐' in html
    assert '"media.register.direct.field.quantity.label":' in html
    assert '"media.register.api_lookup.field.source.label":' in html
    assert '"media.register.review.title":' in html


def test_media_master_cleanup_static_copy_uses_i18n_keys():
    html = read_static_html("index.html")
    assert '<summary data-i18n="manual.register_master.summary">마스터 정리 페이지 활용 매뉴얼</summary>' in html
    assert 'data-page-help-open="register-master"' in html
    assert '<h2><span data-i18n="media.register.master.title">앨범 마스터 묶기</span></h2>' in html
    assert '<label for="masterSource" data-i18n="media.register.master.field.source.label">마스터 소스</label>' in html
    assert '<label for="masterQuery" data-i18n="media.register.master.field.query.label">마스터 검색어</label>' in html
    assert '<button id="masterSearchBtn" class="btn secondary" data-i18n="media.register.master.action.search">마스터 검색</button>' in html
    assert '<strong data-i18n="media.register.master.section.candidates">마스터 후보</strong>' in html
    assert '<button id="masterVariantsBtn" class="btn ghost" type="button" data-i18n="media.register.master.action.load_variants">선택 마스터 버전 불러오기</button>' in html
    assert '<label for="masterVariantCatalogNo" data-i18n="media.register.master.field.variant_catalog.label">카탈로그 번호 검색</label>' in html
    assert '<button id="masterVariantSelectAllBtn" class="btn ghost icon-symbol-btn icon-symbol-btn--select-all" type="button" title="전체 선택" aria-label="전체 선택" data-i18n="media.register.master.action.select_all"' in html
    assert '<button id="masterImportVariantsBtn" class="btn" type="button" data-i18n="media.register.master.action.import_selected">선택 버전 신규 등록</button>' in html
    assert '"manual.register_master.summary":' in html
    assert '"media.register.master.title":' in html
    assert '"media.register.master.action.import_selected":' in html
    assert 'data-i18n="operator.context.subtitle"' in html
    assert 'data-i18n="shared_camera.preview.subtitle"' in html


def test_operator_focus_docs_and_meta_sync_static_copy_use_i18n_keys():
    html = read_static_html("index.html")
    assert 'data-i18n="shell.admin.doc_link.erd_summary"' in html
    assert 'data-i18n="shell.admin.doc_link.erd_detail"' in html
    assert 'data-i18n="shell.admin.doc_link.manual"' in html
    assert 'data-tool-doc-key="erd-summary"' in html
    assert 'data-tool-doc-key="erd-detail"' in html
    assert 'data-tool-doc-key="manual"' in html
    assert 'data-i18n="shell.admin.doc_link.checklist"' not in html
    assert '"manual.utility.summary":' in html
    assert 'data-i18n="utility.language"' in html
    assert 'data-page-help-open="ops-meta-sync"' in html
    assert '<h2><span data-i18n="ops.meta_sync.title">누락 메타 정기 동기화</span></h2>' in html
    assert '<label for="metaSyncSource" data-i18n="ops.meta_sync.field.source.label">대상 소스</label>' in html
    assert '<label for="metaSyncLimit" data-i18n="ops.meta_sync.field.limit.label">처리 개수(limit)</label>' in html
    assert 'data-i18n="ops.meta_sync.field.only_missing.label"' in html
    assert 'id="metaSyncStatusBtn" class="btn ghost" type="button" data-i18n="ops.meta_sync.action.reload"' in html
    assert 'id="metaSyncRunBtn" class="btn secondary" type="button" data-i18n="ops.meta_sync.action.run"' in html
    assert '"shell.admin.docs_body":' in html
    assert '"operator.focus.search.label":' in html
    assert '"ops.meta_sync.action.run":' in html
    assert 'data-i18n="shared_camera.list.title"' in html
    assert 'data-i18n="shared_camera.empty.title"' in html
    assert 'data-i18n="shared_camera.empty.meta"' in html
    assert '"dashboard.action.search":' in html
    assert '"operator.lookup.action.run":' in html
    assert '"shared_camera.empty.meta":' in html
    assert "function buildLocalizedToolDocHref(docKey) {" in html
    assert "function syncLocalizedToolDocLinks() {" in html
    apply_locale_block = html.split("function applyLocale(locale = appLocale) {", 1)[1].split("function mediaDisplayLabel", 1)[0]
    assert "syncLocalizedToolDocLinks();" in apply_locale_block


def test_dashboard_overview_actions_use_media_icon_button_pattern():
    html = read_static_html("index.html")
    assert 'id="homeOpenManageBtn" class="btn ghost icon-btn" type="button" data-i18n-title="dashboard.action.search" data-i18n-aria-label="dashboard.action.search"' in html
    assert 'id="homeOpenRegisterBtn" class="btn icon-btn" type="button" data-i18n-title="dashboard.action.new_item" data-i18n-aria-label="dashboard.action.new_item"' in html
    dashboard_topbar = html.split('<div class="dashboard-actions">', 1)[1].split("</div>", 1)[0]
    assert '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6"></circle><path d="M20 20l-4.2-4.2"></path></svg>' in dashboard_topbar
    assert '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14"></path><path d="M5 12h14"></path></svg>' in dashboard_topbar


def test_dashboard_selection_and_bulk_edit_controls_use_i18n_keys():
    html = read_static_html("index.html")
    flow_block = html.split('id="homeDashSlotSelectionGroup"', 1)[1].split('id="homeDashBulkEditPanel"', 1)[0]
    assert 'data-i18n-title="dashboard.selection.action.select_all"' in html
    assert 'data-i18n-title="dashboard.selection.action.clear"' in html
    assert 'data-i18n-title="dashboard.selection.action.restore"' in html
    assert 'data-i18n-title="dashboard.selection.action.bulk"' in html
    assert 'id="homeDashSlotSelectAllBtn"' in html
    assert 'id="homeDashSlotClearBtn"' in html
    assert 'class="dashboard-selection-action-clusters"' in flow_block
    assert 'class="dashboard-selection-actions dashboard-selection-actions--slot-icons dashboard-selection-actions--selection"' in flow_block
    assert 'class="dashboard-selection-actions dashboard-selection-actions--secondary"' in flow_block
    assert 'class="dashboard-selection-actions dashboard-selection-actions--primary"' in flow_block
    assert flow_block.index('id="homeDashSelectedItemEditBtn"') < flow_block.index('id="homeDashSlotBulkBtn"')
    assert 'data-i18n="dashboard.selection.action.select_all"' in flow_block
    assert 'data-i18n="dashboard.selection.action.clear"' in flow_block
    assert 'dashboard.selection.action.select_all_short' not in flow_block
    assert 'dashboard.selection.action.clear_short' not in flow_block
    assert 'data-i18n="dashboard.selection.action.restore_short"' in html
    assert 'data-i18n="dashboard.selection.action.bulk_short"' in html
    assert 'data-i18n="dashboard.bulk.title"' in html
    assert 'data-i18n="dashboard.bulk.action.close"' in html
    assert 'data-i18n="dashboard.bulk.field.status.label"' in html
    assert 'data-i18n="dashboard.bulk.field.status.keep"' in html
    assert 'data-i18n="dashboard.bulk.field.status.in_collection"' in html
    assert 'data-i18n="dashboard.bulk.field.domain.label"' in html
    assert 'data-i18n="dashboard.bulk.field.domain.keep"' in html
    assert 'data-i18n="dashboard.bulk.field.release_type.label"' in html
    assert 'data-i18n="dashboard.bulk.field.release_type.keep"' in html
    assert 'data-i18n="dashboard.bulk.field.second_hand.label"' in html
    assert 'data-i18n="dashboard.bulk.field.second_hand.keep"' in html
    assert 'data-i18n="dashboard.bulk.field.purchase_source.label"' in html
    assert 'data-i18n-placeholder="dashboard.bulk.field.purchase_source.placeholder"' in html
    assert 'data-i18n="dashboard.bulk.field.preferred_size.label"' in html
    assert 'data-i18n="dashboard.bulk.field.preferred_size.keep"' in html
    assert 'data-i18n="dashboard.bulk.field.memory_note.label"' in html
    assert 'data-i18n-placeholder="dashboard.bulk.field.memory_note.placeholder"' in html
    assert 'data-i18n="dashboard.bulk.action.apply"' in html
    assert 'data-i18n="dashboard.bulk.action.reset"' in html
    assert 'data-i18n="dashboard.bulk.note"' in html
    assert '"dashboard.bulk.action.apply":' in html
    assert '"dashboard.bulk.note":' in html


def test_dashboard_workbench_and_operator_runtime_copy_use_i18n_keys():
    html = read_static_html("index.html")
    assert 'id="homeDashSelectedItemEditBtn" class="btn ghost tiny dashboard-slot-actionbtn icon-symbol-btn icon-symbol-btn--edit" type="button" title="선택 상품 편집" aria-label="선택 상품 편집" data-i18n-title="dashboard.selection.action.edit_selected"' in html
    assert 'data-i18n="dashboard.selection.action.edit_short"' in html
    assert 'id="homeDashSelectedSortArtistRow"' in html
    assert 'id="homeDashSelectedSortArtistName"' in html
    assert 'id="homeDashSelectedSortArtistSaveBtn"' in html
    assert 'id="homeDashSelectedSortArtistStatus"' in html
    assert 'id="homeDashSelectedSortArtistDisplay"' in html
    assert 'data-i18n="dashboard.selection.sort_artist.label"' in html
    assert 'data-i18n="media.manage.master.sort_artist.action.save"' in html
    assert 'data-i18n="dashboard.selection.sort_artist.note"' in html
    assert '"dashboard.selection.sort_artist.label":' in html
    assert '"dashboard.selection.sort_artist.note":' in html
    assert '"dashboard.selection.sort_artist.display_artist":' in html
    assert 'id="homeDashSearchTitle" data-i18n-placeholder="dashboard.workbench.field.title.placeholder"' in html
    assert 'id="homeDashSearchCatalogNo"' in html
    assert 'data-i18n-placeholder="dashboard.workbench.field.catalog.placeholder"' in html
    assert 'id="homeDashSearchBarcode"' in html
    assert 'data-i18n-placeholder="dashboard.workbench.field.barcode.placeholder"' in html
    workbench_block = html.split('id="homeDashWorkbenchSummary"', 1)[1].split('id="homeDashWorkbenchPagePrevBtn"', 1)[0]
    assert 'class="dashboard-selection-action-clusters"' in workbench_block
    assert 'class="dashboard-selection-actions dashboard-selection-actions--selection"' in workbench_block
    assert 'class="dashboard-selection-actions dashboard-selection-actions--secondary"' in workbench_block
    assert 'class="dashboard-selection-actions dashboard-selection-actions--primary"' in workbench_block
    assert 'id="homeDashWorkbenchEditBtn" class="btn ghost tiny dashboard-workbench-actionbtn icon-symbol-btn icon-symbol-btn--edit" type="button" title="선택 상품 편집" aria-label="선택 상품 편집" data-i18n="dashboard.workbench.action.edit_selected"' in html
    assert 'id="homeDashWorkbenchRecommendBtn" class="btn ghost tiny dashboard-workbench-actionbtn" type="button" data-i18n="dashboard.workbench.action.recommend_slot"' in html
    assert 'id="homeDashWorkbenchSelectAllBtn" class="btn ghost tiny dashboard-workbench-actionbtn icon-symbol-btn icon-symbol-btn--select-all" type="button" title="전체 선택" aria-label="전체 선택" data-i18n="dashboard.selection.action.select_all"' in html
    assert 'id="homeDashWorkbenchClearBtn" class="btn ghost tiny dashboard-workbench-actionbtn icon-symbol-btn icon-symbol-btn--clear-selection" type="button" title="선택 해제" aria-label="선택 해제" data-i18n="dashboard.selection.action.clear"' in html
    assert '"dashboard.workbench.action.edit_selected":' in html
    assert '"dashboard.workbench.field.title.placeholder":' in html
    assert '"dashboard.workbench.field.catalog.placeholder":' in html
    assert '"dashboard.workbench.field.barcode.placeholder":' in html


def test_dashboard_selected_sort_artist_row_uses_aligned_grid_layout():
    html = read_static_html("index.html")
    assert 'id="homeDashSelectedSortArtistRow" class="dashboard-selected-sort-artist-row"' in html
    assert 'class="dashboard-selected-sort-artist-label mini"' in html
    assert 'class="dashboard-selected-sort-artist-input"' in html
    assert 'class="btn ghost tiny dashboard-slot-actionbtn dashboard-selected-sort-artist-save"' in html
    assert 'id="homeDashSelectedSortArtistDisplay" class="dashboard-selected-sort-artist-display mini muted"' in html
    assert 'class="dashboard-selected-sort-artist-note mini muted"' in html
    assert ".dashboard-selected-sort-artist-row {" in html
    assert "grid-template-columns: minmax(240px, 1.4fr) auto minmax(220px, 0.9fr) minmax(260px, 1fr);" in html
    assert 'grid-template-areas:' in html
    assert '"label . . ."' in html
    assert '"input button display note";' in html
    assert ".dashboard-selected-sort-artist-row--master {" in html
    assert '"input button note";' in html
    assert "@media (max-width: 1280px) {" in html
    assert '"label label label"' in html
    assert '"input button display"' in html
    assert 'id="homeMasterSortArtistRow" class="dashboard-selected-sort-artist-row dashboard-selected-sort-artist-row--master" style="display:none;"' in html

    operator_block = html.split("    function updateOperatorFeedControls() {", 1)[1].split("    async function openOperatorCabinetLocationFromButton(button) {", 1)[0]
    assert 't("operator.feed.heading.search_results")' in operator_block
    assert 't("operator.feed.meta.current")' in operator_block
    assert 't("operator.feed.meta.registered")' in operator_block
    assert 't("operator.feed.state.unslotted")' in operator_block
    helper_block = html.split("    function renderOperatorHelperSummary() {", 1)[1].split("    async function loadOperatorLookupResults() {", 1)[0]
    assert 't("operator.helper.kicker")' in helper_block
    assert 't("operator.helper.title")' in helper_block
    assert 't("operator.helper.field.query")' in helper_block
    assert 't("operator.helper.field.top_candidate")' in helper_block
    assert 't("operator.helper.field.current_location")' in helper_block
    assert 't("operator.helper.state.no_candidate")' in helper_block
    assert 't("operator.helper.action.open_cabinet")' in helper_block
    assert 't("operator.helper.state.no_current_location")' in helper_block
    assert 't("operator.helper.state.keep_results")' in helper_block

    workbench_block = html.split("    function renderDashboardUnassignedItems() {", 1)[1].split("    async function loadDashboardUnassignedItems(opts = {}) {", 1)[0]
    assert 't("dashboard.workbench.status.loading_unslotted")' in workbench_block
    assert 't("dashboard.workbench.meta.unslotted_ready")' in workbench_block
    assert 't("dashboard.workbench.status.empty_unslotted")' in workbench_block
    assert 't("dashboard.workbench.meta.search_ready")' in workbench_block
    assert 't("dashboard.workbench.status.loading_search")' in workbench_block
    assert 't("dashboard.workbench.status.empty_search")' in workbench_block


def test_dashboard_workbench_includes_media_filter_field():
    html = read_static_html("index.html")
    assert '<label for="homeDashMediaFilter" data-i18n="dashboard.workbench.field.category.label">미디어</label>' in html
    assert '<select id="homeDashMediaFilter">' in html
    assert '<option value="ANY" data-i18n="common.all">전체</option>' in html
    assert '<option value="LP">LP</option>' in html
    assert '<option value="CD">CD</option>' in html
    assert '<option value="CASSETTE" data-i18n="common.size_group.cassette">카세트</option>' in html
    assert '<option value="8TRACK" data-i18n="common.size_group.8track">8-track</option>' in html
    assert '<option value="DIGITAL">Digital</option>' in html
    assert '<option value="REEL_TO_REEL" data-i18n="common.size_group.reel_to_reel">Reel-to-reel</option>' in html
    assert '"dashboard.workbench.field.category.label": "미디어"' in html
    assert '<label for="homeDashSignatureMode" data-i18n="dashboard.workbench.field.signature_mode.label">싸인 경로</label>' in html
    assert '<select id="homeDashSignatureMode">' in html
    assert '<option value="ANY" data-i18n="dashboard.workbench.field.signature_mode.option.any">전체</option>' in html
    assert '<option value="DIRECT" data-i18n="dashboard.workbench.field.signature_mode.option.direct">직접</option>' in html
    assert '<option value="PURCHASE" data-i18n="dashboard.workbench.field.signature_mode.option.purchase">구매</option>' in html
    assert '"dashboard.workbench.field.signature_mode.label": "싸인 경로"' in html
    assert '<label for="homeDashWorkbenchSortMode" data-i18n="dashboard.workbench.field.sort_mode.label">정렬</label>' in html
    assert '<select id="homeDashWorkbenchSortMode">' in html
    assert '<option value="CREATED_DESC" data-i18n="dashboard.workbench.field.sort_mode.option.created_desc">등록순</option>' in html
    assert '<option value="NAME_ASC" selected data-i18n="dashboard.workbench.field.sort_mode.option.name_asc">이름순</option>' in html
    assert '"dashboard.workbench.field.sort_mode.label": "정렬"' in html


def test_dashboard_workbench_includes_sort_warning_filter_controls():
    html = read_static_html("index.html")
    assert 'id="homeDashSortWarningOnly"' in html
    assert 'data-i18n="dashboard.workbench.field.sort_warning_only.label"' in html
    assert 'id="homeDashWorkbenchDomainFilter"' in html
    assert "homeDashWorkbenchDomainFilter" in html
    domain_filter_block = html.split('id="homeDashWorkbenchDomainFilter"', 1)[1]
    assert "<select" in domain_filter_block
    assert "</select>" in domain_filter_block
    assert 'value="ANY"' in domain_filter_block
    assert 'value="KOREA"' in domain_filter_block
    assert 'data-i18n="dashboard.workbench.field.domain_filter.option.any"' in domain_filter_block
    assert 'value="JAPAN"' in domain_filter_block
    assert 'data-i18n="dashboard.workbench.field.domain_filter.option.korea"' in domain_filter_block
    assert 'data-i18n="dashboard.workbench.field.domain_filter.option.japan"' in domain_filter_block
    assert 'value="GREATER_CHINA"' in domain_filter_block
    assert 'data-i18n="dashboard.workbench.field.domain_filter.option.greater_china"' in domain_filter_block
    assert 'value="OTHER_ASIA"' in domain_filter_block
    assert 'data-i18n="dashboard.workbench.field.domain_filter.option.other_asia"' in domain_filter_block
    assert '"dashboard.workbench.field.domain_filter.label":' in html
    assert "dashboard.workbench.field.domain_filter.option" in html


def test_dashboard_workbench_warning_helpers_render_compact_reason_only():
    html = read_static_html("index.html")
    assert "정렬 주의" in html
    assert "도메인-이름 불일치" in html or "domain_name_mismatch" in html or "domain mismatch" in html
    assert "dashboard.workbench.warning" in html
    assert "dashboard.workbench.warning.badge" in html
    assert "dashboard.workbench.warning.reason" in html
    assert '"dashboard.workbench.warning.detail.domain_name_mismatch":' in html
    assert "dashboard.slot.warning" in html
    assert '"dashboard.slot.warning.badge.size_mismatch":' in html
    assert '"dashboard.slot.warning.badge.domain_mismatch":' in html
    assert '"dashboard.slot.warning.badge.domain_name_mismatch":' in html
    assert '"dashboard.slot.warning.detail.size_mismatch":' in html
    assert '"dashboard.slot.warning.detail.domain_mismatch":' in html
    assert '"dashboard.slot.warning.detail.domain_name_mismatch":' in html
    workbench_block = html.split("function dashboardWorkbenchWarningInfo(row) {", 1)[1].split("function dashboardSlotWarningInfo(row, slotRow) {", 1)[0]
    assert "details:" not in workbench_block


def test_dashboard_workbench_warning_html_renders_badges_only():
    html = read_static_html("index.html")
    warning_block = html.split("function dashboardWorkbenchWarningHtml(row) {", 1)[1].split("function dashboardSlotWarningHtml(row, slotRow) {", 1)[0]
    assert "warning.details.map" not in warning_block


def test_dashboard_workbench_warning_helper_excludes_various_artist_exceptions():
    html = read_static_html("index.html")
    helper_block = html.split("function dashboardWorkbenchNeedsSortWarning(row) {", 1)[1].split("function dashboardWorkbenchWarningInfo(row) {", 1)[0]
    assert 'const normalizedArtist = dashboardWorkbenchArtistSortText(row).toUpperCase();' in helper_block
    assert 'if (normalizedArtist === "VARIOUS" || normalizedArtist === "VARIOUS ARTISTS") return false;' in helper_block


def test_dashboard_workbench_warning_helper_clears_when_saved_sort_artist_matches_domain():
    html = read_static_html("index.html")
    match_block = html.split("function dashboardWorkbenchSortArtistMatchesDomain(row) {", 1)[1].split("function dashboardWorkbenchNeedsSortWarning(row) {", 1)[0]
    assert 'const explicitSortArtist = String(row?.master_sort_artist_name || "").trim();' in match_block
    assert 'if (!explicitSortArtist) return false;' in match_block
    assert 'if (domainCode === "KOREA") return /[\\uac00-\\ud7af]/.test(explicitSortArtist);' in match_block
    assert 'if (domainCode === "JAPAN") return /[\\u3040-\\u30ff\\u4e00-\\u9fff]/.test(explicitSortArtist);' in match_block
    assert 'if (["GREATER_CHINA", "OTHER_ASIA"].includes(domainCode)) return /[\\u3400-\\u4dbf\\u4e00-\\u9fff]/.test(explicitSortArtist);' in match_block
    helper_block = html.split("function dashboardWorkbenchNeedsSortWarning(row) {", 1)[1].split("function dashboardWorkbenchWarningInfo(row) {", 1)[0]
    assert 'if (dashboardWorkbenchSortArtistMatchesDomain(row)) return false;' in helper_block


def test_dashboard_move_status_includes_sort_warning_notice_for_warned_rows():
    html = read_static_html("index.html")
    assert '"dashboard.move.progress_sort_warning":' in html
    assert "moveDashboardOwnedItemsToSlot(" in html
    move_block = html.split("moveDashboardOwnedItemsToSlot(", 1)[1].split("function selectDashboardSingleWorkbenchItemById(", 1)[0]
    assert re.search(r"\?\s*t\(\s*['\"]dashboard\.move\.progress_sort_warning['\"]", move_block)


def test_dashboard_move_done_includes_sort_warning_followup():
    html = read_static_html("index.html")
    assert '"dashboard.move.done_sort_warning_followup":' in html
    move_block = html.split("moveDashboardOwnedItemsToSlot(", 1)[1].split("function selectDashboardSingleWorkbenchItemById(", 1)[0]
    assert "const movedWarningRows = eligible.filter((row) => {" in move_block
    assert "movedIds.has(ownedItemId)" in move_block
    assert "dashboardWorkbenchNeedsSortWarning(row)" in move_block
    assert 'movedWarningRows.length ? t("dashboard.move.done_sort_warning_followup"' in move_block


def test_dashboard_workbench_warning_rendering_is_shared_without_actions():
    html = read_static_html("index.html")
    list_block = html.split("function dashboardWorkbenchListItemHtml(row, source, index = 0) {", 1)[1].split("function dashboardWorkbenchShelfItemHtml", 1)[0]
    shelf_block = html.split("function dashboardWorkbenchShelfItemHtml(row, source, index = 0) {", 1)[1].split("function getDashboardWorkbenchRecommendation", 1)[0]
    assert 'const warningHtml = dashboardWorkbenchWarningHtml(row);' in list_block
    assert 'const warningHtml = dashboardWorkbenchWarningHtml(row);' in shelf_block


def test_dashboard_slot_warning_helpers_detect_size_domain_and_name_mismatch():
    html = read_static_html("index.html")
    helper_block = html.split("function dashboardSlotWarningInfo(row, slotRow) {", 1)[1].split("function dashboardSlotWarningHtml(row, slotRow) {", 1)[0]
    assert 'const warnings = [];' in helper_block
    assert 'const slotSizeGroup = String(slotRow?.allowed_size_group || "").trim().toUpperCase();' in helper_block
    assert 'const itemSizeGroup = String(ownedPreferredStorageSizeGroup(row) || row?.size_group || "").trim().toUpperCase();' in helper_block
    assert 'const slotDomainCode = String(slotRow?.cabinet_domain_code || "").trim().toUpperCase();' in helper_block
    assert 'const itemDomainCode = String(row?.domain_code || "").trim().toUpperCase();' in helper_block
    assert 'dashboardWorkbenchNeedsSortWarning(row)' in helper_block
    assert 'kind: "SIZE_MISMATCH"' in helper_block
    assert 'kind: "DOMAIN_MISMATCH"' in helper_block
    assert 'kind: "DOMAIN_NAME_MISMATCH"' in helper_block


def test_dashboard_slot_renderers_use_slot_specific_warning_logic():
    html = read_static_html("index.html")
    slot_item_block = html.split("function dashboardSlotItemHtml(row, index) {", 1)[1].split("function dashboardSlotListItemHtml", 1)[0]
    slot_list_block = html.split("function dashboardSlotListItemHtml(row, index) {", 1)[1].split("function dashboardSlotShelfItemHtml", 1)[0]
    slot_shelf_block = html.split("function dashboardSlotShelfItemHtml(row, index) {", 1)[1].split("function dashboardWorkbenchListItemHtml", 1)[0]
    assert 'const slotRow = getDashboardSlotRow(String(row?.slot_code || homeDashboardSelectedSlotCode || "").trim()) || null;' in slot_item_block
    assert 'const warningHtml = dashboardSlotWarningHtml(row, slotRow);' in slot_item_block
    assert 'const slotRow = getDashboardSlotRow(String(row?.slot_code || homeDashboardSelectedSlotCode || "").trim()) || null;' in slot_list_block
    assert 'const warningHtml = dashboardSlotWarningHtml(row, slotRow);' in slot_list_block
    assert 'const slotRow = getDashboardSlotRow(String(row?.slot_code || homeDashboardSelectedSlotCode || "").trim()) || null;' in slot_shelf_block
    assert 'const warningHtml = dashboardSlotWarningHtml(row, slotRow);' in slot_shelf_block


def test_dashboard_workbench_loaders_apply_media_filter_when_selected():
    html = read_static_html("index.html")
    unassigned_block = html.split("async function loadDashboardUnassignedItems(opts = {}) {", 1)[1].split("    async function loadDashboardSearchItems(opts = {}) {", 1)[0]
    search_block = html.split("async function loadDashboardSearchItems(opts = {}) {", 1)[1].split("    function getDashboardSelectedWorkbenchRows()", 1)[0]
    expected = 'const category = String($("homeDashMediaFilter")?.value || "ANY").trim().toUpperCase() || "ANY";'
    assert expected in unassigned_block
    assert 'if (category !== "ANY") params.set("category", category);' in unassigned_block
    assert 'const signatureMode = dashboardWorkbenchSignatureModeValue();' in unassigned_block
    assert 'if (signatureMode !== "ANY") params.set("signature_mode", signatureMode);' in unassigned_block
    assert 'params.set("include_relation_summary", "false");' in unassigned_block
    assert expected in search_block
    assert 'if (category !== "ANY") params.set("category", category);' in search_block
    assert 'const signatureMode = dashboardWorkbenchSignatureModeValue();' in search_block
    assert 'if (signatureMode !== "ANY") params.set("signature_mode", signatureMode);' in search_block
    assert 'params.set("include_relation_summary", "false");' in search_block
    assert unassigned_block.count("renderDashboardUnassignedItems();") == 2
    assert 'homeDashboardUnassignedLoaded = true;' in unassigned_block
    assert 'homeDashboardUnassignedLoaded = false;' in unassigned_block
    assert search_block.count("renderDashboardWorkbench();") == 2


def test_dashboard_workbench_unassigned_mode_lazy_loads_only_when_needed():
    html = read_static_html("index.html")
    assert 'let homeDashboardUnassignedLoaded = false;' in html
    mode_block = html.split("    function setDashboardWorkbenchMode(mode) {", 1)[1].split("    function syncDashboardSelectionControls()", 1)[0]
    assert 'if (next === "UNASSIGNED" && !homeDashboardUnassignedLoaded && !homeDashboardUnassignedLoading) {' in mode_block
    assert 'loadDashboardUnassignedItems({ silent: true }).catch(() => {});' in mode_block


def test_dashboard_slot_loader_rerenders_detail_and_workbench_only_at_start_and_finish():
    html = read_static_html("index.html")
    load_block = html.split("    async function loadDashboardSlotItems(slotRow, opts = {}) {", 1)[1].split("    function toggleDashboardCabinet(groupKey) {", 1)[0]
    assert load_block.count("renderDashboardCabinetDetail();") == 4
    assert load_block.count("renderDashboardWorkbench();") == 2
    assert 'include_relation_summary: "false"' in load_block


def test_dashboard_workbench_media_filter_change_reload_current_mode():
    html = read_static_html("index.html")
    change_start = '$("homeDashMediaFilter").addEventListener("change", () => {'
    next_start = '    $("homeOpenDashboardSlotBtn").addEventListener("click", openDashboardForCurrentLocation);'
    assert change_start in html
    assert next_start in html
    block = html.split(change_start, 1)[1].split(next_start, 1)[0]
    assert 'if (homeDashboardWorkbenchMode === "SEARCH") {' in block
    assert 'loadDashboardSearchItems({ silent: true });' in block
    assert 'loadDashboardUnassignedItems({ silent: true });' in block
    signature_change_start = '$("homeDashSignatureMode").addEventListener("change", () => {'
    assert signature_change_start in html
    signature_block = html.split(signature_change_start, 1)[1].split(next_start, 1)[0]
    assert 'if (homeDashboardWorkbenchMode === "SEARCH") {' in signature_block
    assert 'loadDashboardSearchItems({ silent: true });' in signature_block
    assert 'loadDashboardUnassignedItems({ silent: true });' in signature_block


def test_dashboard_workbench_search_row_tunes_warning_and_compact_filters():
    html = read_static_html("index.html")
    next_start = '    $("homeOpenDashboardSlotBtn").addEventListener("click", openDashboardForCurrentLocation);'
    assert ".dashboard-workbench-search {" in html
    assert "108px" in html
    assert "minmax(118px, 0.76fr)" in html
    assert ".dashboard-workbench-filter--signature" in html
    assert ".dashboard-workbench-filter--sort" in html
    assert 'class="dashboard-workbench-filter dashboard-workbench-filter--signature"' in html
    assert 'class="dashboard-workbench-filter dashboard-workbench-filter--sort"' in html
    assert 'id="homeDashSearchCatalogNo" class="dashboard-workbench-search-input--catalog"' in html
    assert 'id="homeDashSearchBarcode" class="dashboard-workbench-search-input--barcode"' in html
    sort_change_start = '$("homeDashWorkbenchSortMode").addEventListener("change", () => {'
    assert sort_change_start in html
    sort_block = html.split(sort_change_start, 1)[1].split(next_start, 1)[0]
    assert "resetDashboardWorkbenchPage();" in sort_block
    assert "renderDashboardWorkbench();" in sort_block


def test_dashboard_workbench_places_sort_warning_toggle_in_selection_row():
    html = read_static_html("index.html")
    workbench_toolbar = html.split('<div class="dashboard-workbench-search">', 1)[1].split("</div>\n            </div>\n            <div class=\"dashboard-slot-rack-surface", 1)[0]
    assert 'homeDashSortWarningOnly' not in workbench_toolbar
    workbench_summary = html.split('<div id="homeDashWorkbenchSummary"', 1)[1].split('<div class="dashboard-selection-actions dashboard-selection-actions--secondary">', 1)[0]
    assert 'class="dashboard-selection-inline-filter"' in workbench_summary
    assert 'id="homeDashSortWarningOnly"' in workbench_summary
    assert 'class="dashboard-workbench-checkbox" for="homeDashSortWarningOnly"' in workbench_summary


def test_dashboard_workbench_sort_helper_supports_created_and_name_modes():
    html = read_static_html("index.html")
    assert 'function dashboardWorkbenchSortModeValue() {' in html
    helper_block = html.split("function dashboardWorkbenchSortModeValue() {", 1)[1].split("    function renderDashboardUnassignedItems() {", 1)[0]
    assert 'String($("homeDashWorkbenchSortMode")?.value || "NAME_ASC").trim().toUpperCase() || "NAME_ASC"' in helper_block
    assert 'if (sortMode === "NAME_ASC") {' in helper_block
    assert 'const artistA = String(a?.master_sort_artist_name || a?.artist_or_brand || a?.linked_artist_name || a?.master_artist_or_brand || "").trim().replace(/\\s+/g, " ").toLocaleLowerCase();' in helper_block
    assert 'const releaseA = dashboardPreferredReleaseSortValue(a);' in helper_block
    assert 'const releaseCompare = releaseA.localeCompare(releaseB);' in helper_block
    assert 'if (releaseCompare !== 0) return releaseCompare;' in helper_block
    assert 'const titleA = String(a?.master_title || a?.item_title || a?.item_name_override || "").trim().replace(/\\s+/g, " ").toLocaleLowerCase();' in helper_block
    assert 'const createdA = String(a?.created_at || "").trim();' in helper_block
    assert 'const createdCompare = createdB.localeCompare(createdA);' in helper_block
    assert 'if (createdCompare !== 0) return createdCompare;' in helper_block


def test_dashboard_slot_includes_sort_mode_field():
    html = read_static_html("index.html")
    assert '<label for="homeDashSlotSortMode" data-i18n="dashboard.cover_flow.field.sort_mode.label">정렬</label>' in html
    assert '<select id="homeDashSlotSortMode">' in html
    assert '<option value="CREATED_DESC" data-i18n="dashboard.cover_flow.field.sort_mode.option.created_desc">등록순</option>' in html
    assert '<option value="NAME_ASC" selected data-i18n="dashboard.cover_flow.field.sort_mode.option.name_asc">이름순</option>' in html
    assert '"dashboard.cover_flow.field.sort_mode.label": "정렬"' in html


def test_dashboard_slot_includes_media_filter_field():
    html = read_static_html("index.html")
    assert '<label for="homeDashSlotMediaFilter" data-i18n="dashboard.cover_flow.field.category.label">미디어</label>' in html
    assert '<select id="homeDashSlotMediaFilter">' in html
    assert '<option value="ANY" data-i18n="dashboard.cover_flow.field.category.option.any">전체</option>' in html
    assert '<option value="LP" data-i18n="common.size_group.lp">LP</option>' in html
    assert '<option value="CD" data-i18n="common.size_group.cd">CD</option>' in html
    assert '<option value="CASSETTE" data-i18n="common.size_group.cassette">Cassette</option>' in html
    assert '<option value="8TRACK">8-track</option>' in html
    assert '<option value="DIGITAL">Digital</option>' in html
    assert '<option value="REEL_TO_REEL" data-i18n="common.size_group.reel_to_reel">Reel-to-reel</option>' in html
    assert '"dashboard.cover_flow.field.category.label": "미디어"' in html


def test_dashboard_slot_media_filter_helper_supports_selected_category():
    html = read_static_html("index.html")
    assert 'function dashboardSlotMediaFilterValue() {' in html
    helper_block = html.split("function dashboardSlotMediaFilterValue() {", 1)[1].split("    function dashboardSlotSortModeValue() {", 1)[0]
    assert 'String($("homeDashSlotMediaFilter")?.value || "ANY").trim().toUpperCase() || "ANY"' in helper_block
    assert 'const category = dashboardSlotMediaFilterValue();' in helper_block
    assert 'if (category === "ANY") return list;' in helper_block
    assert 'return list.filter((row) => String(row?.category || "").trim().toUpperCase() === category);' in helper_block


def test_dashboard_slot_sort_helper_supports_created_and_name_modes():
    html = read_static_html("index.html")
    assert 'function dashboardSlotSortModeValue() {' in html
    helper_block = html.split("function dashboardSlotSortModeValue() {", 1)[1].split("    function dashboardWorkbenchPageSlice(items, slotRow) {", 1)[0]
    assert 'String($("homeDashSlotSortMode")?.value || "NAME_ASC").trim().toUpperCase() || "NAME_ASC"' in helper_block
    assert 'if (sortMode === "NAME_ASC") {' in helper_block
    assert 'const artistA = String(a?.master_sort_artist_name || a?.artist_or_brand || a?.linked_artist_name || a?.master_artist_or_brand || "").trim().replace(/\\s+/g, " ").toLocaleLowerCase();' in helper_block
    assert 'const releaseA = dashboardPreferredReleaseSortValue(a);' in helper_block
    assert 'const releaseCompare = releaseA.localeCompare(releaseB);' in helper_block
    assert 'if (releaseCompare !== 0) return releaseCompare;' in helper_block
    assert 'const titleA = String(a?.master_title || a?.item_title || a?.item_name_override || "").trim().replace(/\\s+/g, " ").toLocaleLowerCase();' in helper_block
    assert 'const createdA = String(a?.created_at || "").trim();' in helper_block
    assert 'const createdCompare = createdB.localeCompare(createdA);' in helper_block
    assert 'if (createdCompare !== 0) return createdCompare;' in helper_block


def test_dashboard_workbench_name_sort_prefers_canonical_artist_and_master_title():
    html = read_static_html("index.html")
    assert 'function sortDashboardWorkbenchItems(items) {' in html
    helper_block = html.split("function sortDashboardWorkbenchItems(items) {", 1)[1].split("    function loadDashboardWorkbenchPreferences() {", 1)[0]
    assert 'if (sortMode === "NAME_ASC") {' in helper_block
    assert 'const artistA = String(a?.master_sort_artist_name || a?.artist_or_brand || a?.linked_artist_name || a?.master_artist_or_brand || "").trim().replace(/\\s+/g, " ").toLocaleLowerCase();' in helper_block
    assert 'const titleA = String(a?.master_title || a?.item_title || a?.item_name_override || "").trim().replace(/\\s+/g, " ").toLocaleLowerCase();' in helper_block


def test_dashboard_name_sort_uses_release_priority_and_year_only_first():
    html = read_static_html("index.html")
    assert 'function normalizeDashboardReleaseSortValue(value) {' in html
    helper_block = html.split("function normalizeDashboardReleaseSortValue(value) {", 1)[1].split("    function dashboardSlotSortModeValue() {", 1)[0]
    assert "if (/^\\d{4}-\\d{2}$/.test(text)) return `${text}-00`;" in helper_block
    assert "if (/^\\d{4}$/.test(text)) return `${text}-00-00`;" in helper_block
    assert 'function dashboardPreferredReleaseSortValue(row) {' in helper_block
    assert 'const candidates = [masterRelease, itemRelease].filter(Boolean).sort();' in helper_block


def test_dashboard_slot_items_apply_sort_helper_for_live_and_snapshot_rows():
    html = read_static_html("index.html")
    block = html.split("function renderDashboardSlotItems(slotRow, cabinetGroup = null) {", 1)[1].split("    function renderDashboardCabinetDetail() {", 1)[0]
    assert 'const visibleSnapshotItems = sortDashboardSlotItems(filterDashboardSlotItemsByMedia(snapshotItems));' in block
    assert 'const items = sortDashboardSlotItems(filterDashboardSlotItemsByMedia(Array.isArray(homeDashboardSlotItems) ? homeDashboardSlotItems : []));' in block


def test_dashboard_workbench_rows_apply_media_filter_then_sort():
    html = read_static_html("index.html")
    block = html.split("function getDashboardWorkbenchRows() {", 1)[1].split("    function getDashboardWorkbenchSelectedIds()", 1)[0]
    assert 'return sortDashboardWorkbenchItems(filterDashboardWorkbenchItemsByMedia(homeDashboardSearchItems));' in block
    assert 'return sortDashboardWorkbenchItems(filterDashboardWorkbenchItemsByMedia(homeDashboardUnassignedItems));' in block


def test_dashboard_workbench_persists_filter_preferences_by_role():
    html = read_static_html("index.html")
    assert 'const DASHBOARD_WORKBENCH_PREFS_KEY = "hahahoho.dashboardWorkbenchPrefsByRole.v1";' in html
    assert "function loadDashboardWorkbenchPreferences() {" in html
    assert "function saveDashboardWorkbenchPreferences() {" in html
    assert "function applyDashboardWorkbenchPreferences() {" in html
    helper_block = html.split("function loadDashboardWorkbenchPreferences() {", 1)[1].split("    function renderDashboardUnassignedItems() {", 1)[0]
    assert 'const map = loadRoleScopedMap(DASHBOARD_WORKBENCH_PREFS_KEY);' in helper_block
    assert 'saveRoleScopedMap(DASHBOARD_WORKBENCH_PREFS_KEY, map);' in helper_block
    assert 'category: dashboardWorkbenchMediaFilterValue(),' in helper_block
    assert 'signature_mode: dashboardWorkbenchSignatureModeValue(),' in helper_block
    assert 'sort_mode: dashboardWorkbenchSortModeValue(),' in helper_block
    assert 'slot_sort_mode: dashboardSlotSortModeValue(),' in helper_block
    assert 'artist: String($("homeDashSearchArtist")?.value || "").trim(),' in helper_block
    assert 'title: String($("homeDashSearchTitle")?.value || "").trim(),' in helper_block
    assert 'catalog_no: String($("homeDashSearchCatalogNo")?.value || "").trim(),' in helper_block
    assert 'barcode: String($("homeDashSearchBarcode")?.value || "").trim(),' in helper_block


def test_dashboard_workbench_restores_preferences_on_dashboard_load_and_saves_on_change():
    html = read_static_html("index.html")
    load_block = html.split("async function loadHomeDashboard(opts = {}) {", 1)[1].split("    function resetHomeSearchForm()", 1)[0]
    assert "applyDashboardWorkbenchPreferences();" in load_block
    assert "if (shouldRefreshDashboardUnassignedWorkbench()) {" in load_block
    assert "await loadDashboardUnassignedItems({ silent: true });" in load_block
    next_start = '    $("homeOpenDashboardSlotBtn").addEventListener("click", openDashboardForCurrentLocation);'
    media_block = html.split('$("homeDashMediaFilter").addEventListener("change", () => {', 1)[1].split(next_start, 1)[0]
    signature_block = html.split('$("homeDashSignatureMode").addEventListener("change", () => {', 1)[1].split(next_start, 1)[0]
    sort_block = html.split('$("homeDashWorkbenchSortMode").addEventListener("change", () => {', 1)[1].split(next_start, 1)[0]
    slot_sort_block = html.split('$("homeDashSlotSortMode").addEventListener("change", () => {', 1)[1].split(next_start, 1)[0]
    assert "saveDashboardWorkbenchPreferences();" in media_block
    assert "saveDashboardWorkbenchPreferences();" in signature_block
    assert "saveDashboardWorkbenchPreferences();" in sort_block
    assert "saveDashboardWorkbenchPreferences();" in slot_sort_block
    assert '$("homeDashSearchArtist").addEventListener("input", saveDashboardWorkbenchPreferences);' in html
    assert '$("homeDashSearchTitle").addEventListener("input", saveDashboardWorkbenchPreferences);' in html
    assert '$("homeDashSearchCatalogNo").addEventListener("input", saveDashboardWorkbenchPreferences);' in html
    assert '$("homeDashSearchBarcode").addEventListener("input", saveDashboardWorkbenchPreferences);' in html
    assert '$("homeDashWorkbenchSortMode").value = ["CREATED_DESC", "NAME_ASC"].includes(sortMode) ? sortMode : "NAME_ASC";' in html
    assert '$("homeDashSlotSortMode").value = ["CREATED_DESC", "NAME_ASC"].includes(slotSortMode) ? slotSortMode : "NAME_ASC";' in html
    assert '$("homeDashSearchArtist").value = String(prefs?.artist || "");' in html
    assert '$("homeDashSearchTitle").value = String(prefs?.title || "");' in html
    assert '$("homeDashSearchCatalogNo").value = String(prefs?.catalog_no || "");' in html
    assert '$("homeDashSearchBarcode").value = String(prefs?.barcode || "");' in html


def test_background_refresh_helpers_only_reload_visible_dashboard_and_search_surfaces():
    html = read_static_html("index.html")
    helper_block = html.split("    function refreshOpsExceptionInBackground() {", 1)[1].split("    function shouldKeepHomeMasterContextForOwnedItem(", 1)[0]
    assert 'function isHomeDashboardSurfaceActive() {' in helper_block
    assert 'return Boolean($("tabHome")?.classList.contains("active") || currentShellMode() === "cabinets");' in helper_block
    assert 'function isHomeSearchSurfaceActive() {' in helper_block
    assert 'return Boolean($("tabSearch")?.classList.contains("active"));' in helper_block
    assert 'if (!isHomeDashboardSurfaceActive()) return;' in helper_block
    assert 'if (!isHomeSearchSurfaceActive()) return;' in helper_block
    assert 'loadHomeDashboard({ silent: true }).catch(() => {});' in helper_block
    assert 'homeSearchOwnedItems({ allowPageAdjust: false }).catch(() => {});' in helper_block
    assert 'function shouldRefreshDashboardUnassignedWorkbench() {' in helper_block
    assert 'return homeDashboardWorkbenchMode === "UNASSIGNED" || !homeDashboardUnassignedLoaded;' in helper_block


def test_dashboard_slot_sort_change_rerenders_selected_slot_items():
    html = read_static_html("index.html")
    next_start = '    $("homeOpenDashboardSlotBtn").addEventListener("click", openDashboardForCurrentLocation);'
    change_start = '$("homeDashSlotSortMode").addEventListener("change", () => {'
    assert change_start in html
    block = html.split(change_start, 1)[1].split(next_start, 1)[0]
    assert "resetDashboardSlotPage();" in block
    assert "renderDashboardSlotItems(getDashboardSlotRow(homeDashboardSelectedSlotCode));" in block


def test_dashboard_slot_media_filter_change_rerenders_selected_slot_items():
    html = read_static_html("index.html")
    next_start = '    $("homeOpenDashboardSlotBtn").addEventListener("click", openDashboardForCurrentLocation);'
    change_start = '$("homeDashSlotMediaFilter").addEventListener("change", () => {'
    assert change_start in html
    block = html.split(change_start, 1)[1].split(next_start, 1)[0]
    assert "resetDashboardSlotPage();" in block
    assert "renderDashboardSlotItems(getDashboardSlotRow(homeDashboardSelectedSlotCode));" in block


def test_index_dashboard_selection_toolbar_uses_tiered_visual_weights_for_selection_secondary_and_primary_actions():
    html = read_static_html("index.html")
    secondary_block = html.split(".dashboard-selection-actions--secondary .dashboard-slot-actionbtn,\n    .dashboard-selection-actions--secondary .dashboard-workbench-actionbtn {", 1)[1].split("}", 1)[0]
    primary_block = html.split(".dashboard-selection-actions--primary .dashboard-slot-actionbtn,\n    .dashboard-selection-actions--primary .dashboard-workbench-actionbtn {", 1)[1].split("}", 1)[0]
    primary_hover_block = html.split(".dashboard-selection-actions--primary .dashboard-slot-actionbtn:hover,\n    .dashboard-selection-actions--primary .dashboard-workbench-actionbtn:hover {", 1)[1].split("}", 1)[0]
    assert "color: #526275;" in secondary_block
    assert "border-color: #d7e5df;" in secondary_block
    assert "background: rgba(248,250,252,0.82);" in secondary_block
    assert "color: #0f766e;" in primary_block
    assert "border-color: #8fd6cb;" in primary_block
    assert "background: rgba(236, 253, 245, 0.96);" in primary_block
    assert "box-shadow: 0 8px 16px rgba(15, 118, 110, 0.08);" in primary_block
    assert "background: #ccfbf1;" in primary_hover_block


def test_ops_exception_account_and_export_labels_use_i18n_keys():
    html = read_static_html("index.html")
    assert 'data-page-help-open="ops-exception"' in html
    assert '<h2><span data-i18n="ops.exception.title">예외 큐</span></h2>' in html
    assert '<label for="opsExceptionType" data-i18n="ops.exception.field.type.label">예외 종류</label>' in html
    assert 'id="opsExceptionLoadBtn" class="btn" type="button" data-i18n="ops.exception.action.load"' in html

    assert 'data-page-help-open="ops-account"' in html
    assert '<h2><span data-i18n="ops.account.title">관리자 / 현장 운영자 계정</span></h2>' in html
    assert '<label for="opsAuthUsername" data-i18n="ops.account.field.username.label">아이디</label>' in html
    assert 'id="opsAuthUsername" data-i18n-placeholder="ops.account.field.username.placeholder"' in html
    assert 'id="opsAuthSaveBtn" class="btn" type="button" data-i18n="ops.account.action.save"' in html

    assert 'data-page-help-open="ops-export"' in html
    assert '<h2><span data-i18n="ops.export.title">백업 / 내보내기</span></h2>' in html
    assert 'data-i18n="ops.export.intro"' in html
    assert 'id="opsExportDbBtn" class="btn" type="button" data-i18n="ops.export.action.db_backup"' in html
    assert 'id="opsExportFullBtn" class="btn secondary" type="button" data-i18n="ops.export.action.full_backup"' in html
    assert 'id="opsExportOwnedBtn" class="btn ghost" type="button" data-i18n="ops.export.action.owned_csv"' in html
    assert 'id="opsExportMasterBtn" class="btn ghost" type="button" data-i18n="ops.export.action.master_csv"' in html
    assert 'data-i18n="ops.export.field.include_env.label"' in html
    assert 'data-i18n="ops.export.outro"' in html
    assert '<h2><span data-i18n="ops.restore.title">자동 백업 / DB 복구</span><span class="section-help-dot"' in html
    assert '<label for="opsAutoBackupIntervalMinutes" data-i18n="ops.restore.field.interval.label">주기(분)</label>' in html
    assert 'id="opsAutoBackupDir" data-i18n-placeholder="ops.restore.field.dir.placeholder"' in html
    assert 'id="opsAutoBackupSaveBtn" class="btn ghost" type="button" data-i18n="ops.restore.action.save_auto_backup"' in html

    assert '"ops.exception.field.type.label":' in html
    assert '"ops.account.field.username.placeholder":' in html
    assert '"ops.export.intro":' in html
    assert '"ops.export.action.full_backup":' in html
    assert '"ops.export.outro":' in html
    assert '"ops.export.action.db_backup":' in html
    assert '"ops.restore.field.interval.label":' in html


def test_ops_camera_slot_exception_and_account_static_controls_use_i18n_keys():
    html = read_static_html("index.html")
    assert 'data-i18n="ops.camera.advanced.title"' in html
    assert 'data-i18n="ops.camera.field.snapshot_url.label"' in html
    assert 'data-i18n="ops.camera.action.delete"' in html
    assert 'data-i18n="ops.camera.action.reset"' in html
    assert 'data-i18n="ops.camera.list.title"' in html
    assert 'data-i18n="ops.camera.table.header.description"' in html

    assert 'data-i18n="ops.slot.intro"' in html
    assert 'data-i18n="ops.slot.field.id.label"' in html
    assert 'data-i18n="ops.slot.field.column.label"' in html
    assert 'data-i18n="ops.slot.field.cell.label"' in html
    assert 'data-i18n="ops.slot.field.size_group.label"' in html
    assert 'data-i18n="ops.slot.action.reset"' in html
    assert 'data-i18n="ops.slot.action.reload"' in html

    assert 'data-i18n="ops.exception.intro"' in html
    assert 'data-i18n="ops.exception.field.limit.label"' in html


def test_ops_secondary_static_controls_and_options_use_i18n_keys():
    html = read_static_html("index.html")
    assert 'data-i18n="ops.cabinet.intro"' in html
    assert 'data-i18n="ops.cabinet.field.group_name.label"' in html
    assert 'data-i18n-placeholder="ops.cabinet.field.group_name.placeholder"' in html
    assert 'data-i18n="ops.cabinet.field.group_order.label"' in html
    assert 'data-i18n-placeholder="ops.cabinet.field.group_order.placeholder"' in html
    assert 'data-i18n="ops.cabinet.field.domain.label"' in html
    assert 'data-i18n="ops.cabinet.field.domain.empty"' in html
    assert 'data-i18n="ops.cabinet.group_hint"' in html
    assert 'data-i18n="ops.cabinet.action.delete"' in html
    assert 'data-i18n="ops.cabinet.mode_hint"' in html
    assert 'data-i18n="ops.cabinet.table.header.cabinet"' in html
    assert 'data-i18n="ops.cabinet.table.header.group"' in html
    assert 'data-i18n="ops.cabinet.table.header.domain"' in html

    assert 'data-i18n="ops.camera.selection.new"' in html
    assert 'data-i18n="ops.camera.field.username.label"' in html
    assert 'data-i18n-placeholder="ops.camera.field.username.placeholder"' in html
    assert 'data-i18n="ops.camera.field.password.label"' in html
    assert 'data-i18n-placeholder="ops.camera.field.password.placeholder"' in html
    assert 'data-i18n="ops.camera.discover.note"' in html
    assert 'data-i18n="ops.camera.discover.table.header.name"' in html
    assert 'data-i18n="ops.camera.discover.table.header.ip"' in html
    assert 'data-i18n="ops.camera.discover.table.header.apply"' in html

    assert 'data-i18n="ops.slot.table.header.cabinet"' in html
    assert 'data-i18n="ops.slot.table.header.column"' in html
    assert 'data-i18n="ops.slot.table.header.cell"' in html
    assert 'data-i18n="ops.slot.table.header.display_name"' in html
    assert 'data-i18n="ops.slot.table.header.size_group"' in html

    assert 'data-i18n="ops.exception.field.preset.empty"' in html
    assert 'data-i18n-placeholder="ops.exception.field.preset_name.placeholder"' in html
    assert 'data-i18n="ops.exception.action.set_default"' in html
    assert 'data-i18n="ops.exception.action.delete_filter"' in html
    assert 'data-i18n="ops.exception.selection.summary.zero"' in html
    assert 'data-i18n="ops.exception.selection.action.bulk_source"' in html
    assert 'data-i18n="ops.exception.selection.action.bulk_align"' in html
    assert 'data-i18n="ops.exception.selection.action.bulk_master"' in html
    assert 'data-i18n="ops.exception.selection.action.select_all"' in html
    assert 'data-i18n="ops.exception.selection.action.clear"' in html
    assert 'data-i18n="ops.exception.section.targets"' in html

    assert 'data-i18n-placeholder="ops.account.field.password.placeholder"' in html
    assert 'data-i18n="ops.account.table.header.username"' in html
    assert 'data-i18n="ops.account.table.header.role"' in html
    assert 'data-i18n="ops.account.table.header.source"' in html
    assert 'data-i18n="ops.account.table.header.status"' in html

    assert '"ops.cabinet.intro":' in html
    assert '"ops.camera.selection.new":' in html
    assert '"ops.slot.table.header.cabinet":' in html
    assert '"ops.exception.selection.action.bulk_source":' in html
    assert '"ops.account.table.header.username":' in html
    assert 'data-i18n="ops.exception.field.preset.label"' in html
    assert 'data-i18n="ops.exception.action.reload_count"' in html
    assert 'data-i18n="ops.exception.action.save_filter"' in html
    assert 'data-i18n="ops.exception.action.apply_loaded_filter"' in html

    assert 'data-i18n="ops.account.intro"' in html
    assert 'data-i18n="ops.account.field.password.label"' in html
    assert 'data-i18n="ops.account.field.role.label"' in html
    assert 'data-i18n="ops.account.field.active.label"' in html
    assert 'data-i18n="ops.account.action.delete"' in html
    assert 'data-i18n="ops.account.action.reset"' in html
    assert 'data-i18n="ops.account.action.reload"' in html


def test_ops_remaining_select_options_and_headers_use_i18n_keys():
    html = read_static_html("index.html")

    assert 'data-i18n="ops.cabinet.field.size_group.label"' in html
    assert 'data-i18n="common.size_group.std"' in html
    assert 'data-i18n="common.size_group.book"' in html
    assert 'data-i18n="common.size_group.lp7"' in html
    assert 'data-i18n="common.size_group.goods"' in html
    assert 'data-i18n="ops.cabinet.field.sort_policy.label"' in html
    assert 'data-i18n="common.sort_policy.artist_release_title"' in html
    assert 'data-i18n="common.sort_policy.label_id"' in html
    assert 'data-i18n="ops.cabinet.field.floor_count.label"' in html
    assert 'data-i18n="ops.cabinet.field.cell_count.label"' in html
    assert 'data-i18n="ops.cabinet.field.slot_capacity.label"' in html
    assert 'data-i18n-placeholder="ops.cabinet.field.slot_capacity.placeholder"' in html
    assert 'data-i18n="ops.cabinet.field.slot_capacity.hint"' in html
    assert 'data-i18n="ops.cabinet.field.floor_start.label"' in html
    assert 'data-i18n="ops.cabinet.field.cell_start.label"' in html
    assert 'data-i18n="ops.cabinet.table.header.size_group"' in html
    assert 'data-i18n="ops.cabinet.table.header.slot_capacity"' in html
    assert 'data-i18n="ops.cabinet.table.header.sort_policy"' in html
    assert 'data-i18n="ops.cabinet.table.header.floor_count"' in html
    assert 'data-i18n="ops.cabinet.table.header.cell_count"' in html
    assert 'data-i18n="ops.cabinet.table.header.slot_count"' in html
    assert 'data-i18n="common.domain.korea"' in html
    assert 'data-i18n="common.domain.unknown"' in html

    assert 'data-i18n="ops.slot.table.header.id"' in html
    assert 'data-i18n="ops.slot.table.header.code"' in html

    assert 'data-i18n="ops.exception.field.type.unslotted"' in html
    assert 'data-i18n="ops.exception.field.type.source_missing"' in html
    assert 'data-i18n="ops.exception.field.type.preferred_size_mismatch"' in html

    assert 'data-i18n="ops.account.field.role.operator"' in html
    assert 'data-i18n="ops.account.field.role.admin"' in html
    assert 'data-i18n="ops.account.table.header.edit"' in html
    assert 'data-i18n="ops.account.table.header.updated_at"' in html

    assert '"common.size_group.std":' in html
    assert '"common.sort_policy.artist_release_title":' in html
    assert '"common.domain.korea":' in html
    assert '"ops.cabinet.field.slot_capacity.hint":' in html
    assert '"ops.exception.field.type.unslotted":' in html
    assert '"ops.account.table.header.updated_at":' in html


def test_media_and_collectibles_common_domain_size_and_unspecified_options_use_i18n_keys():
    html = read_static_html("index.html")

    assert 'id="editSlotId"><option value="" data-i18n="common.unspecified">' in html
    assert 'id="editPreferredStorageSizeGroup"' in html
    assert 'id="editDomainCode"' in html
    assert 'id="goodsManageSlotId"><option value="" data-i18n="common.unspecified">' in html
    assert 'id="goodsManageDomainCode"' in html
    assert 'id="goodsRegisterSlotId"><option value="" data-i18n="common.unspecified">' in html
    assert 'id="goodsRegisterDomainCode"' in html
    assert 'id="quickSlotId"><option value="" data-i18n="common.unspecified">' in html
    assert 'id="quickDomainCode"' in html
    assert 'id="slotId"><option value="" data-i18n="common.unspecified">' in html
    assert 'id="domainCode"' in html

    assert html.count('data-i18n="common.domain.korea"') >= 5
    assert html.count('data-i18n="common.domain.unknown"') >= 5
    assert html.count('data-i18n="common.size_group.std"') >= 5
    assert html.count('data-i18n="common.size_group.goods"') >= 4
    assert '"common.unspecified":' in html

    assert '"ops.camera.advanced.title":' in html
    assert '"ops.slot.field.column.label":' in html
    assert '"ops.exception.action.save_filter":' in html
    assert '"ops.account.action.reload":' in html


def test_common_runtime_label_helpers_use_i18n_keys():
    html = read_static_html("index.html")
    signature_block = html.split("function signatureTypeDisplayLabel(value) {", 1)[1].split("function signatureIconLabel(value) {", 1)[0]
    movement_block = html.split("function dashboardMoveKindLabel(value) {", 1)[1].split("function dashboardMoveKindClass(value) {", 1)[0]
    movement_display_block = html.split("function dashboardMoveDisplayKind(row) {", 1)[1].split("function dashboardDomainLabel(value) {", 1)[0]
    domain_block = html.split("function dashboardDomainLabel(value) {", 1)[1].split("function formatDashboardFloorSummaryLines(summaryText) {", 1)[0]
    release_block = html.split("function dashboardReleaseTypeLabel(value) {", 1)[1].split("function dashboardSizeGroupLabel(value) {", 1)[0]
    size_block = html.split("function dashboardSizeGroupLabel(value) {", 1)[1].split("function dashboardSourceLabel(value) {", 1)[0]
    source_block = html.split("function dashboardSourceLabel(value) {", 1)[1].split("function dashboardStatusLabel(value) {", 1)[0]
    status_block = html.split("function dashboardStatusLabel(value) {", 1)[1].split("function opsExceptionTypeLabel(value) {", 1)[0]
    exception_block = html.split("function opsExceptionTypeLabel(value) {", 1)[1].split("function opsExceptionTypeHint(value) {", 1)[0]
    exception_hint_block = html.split("function opsExceptionTypeHint(value) {", 1)[1].split("function buildOpsExceptionParams(type, opts = {}) {", 1)[0]
    assert 't("common.signature.none")' in signature_block
    assert 't("common.movement.restore")' in movement_display_block
    assert 't("common.movement.initial_assign")' in movement_block
    assert 't("common.domain.korea")' in domain_block
    assert 't("common.release_type.album")' in release_block
    assert 't("common.size_group.lp7")' in size_block
    assert 't("common.source.manual")' in source_block
    assert 't("common.status.in_collection")' in status_block
    assert 't("common.exception.unslotted")' in exception_block
    assert 't("common.exception_hint.unslotted")' in exception_hint_block


def test_lower_admin_runtime_status_copy_uses_i18n_keys():
    html = read_static_html("index.html")
    assert 'setStatus("barcodeStatus", "err", t("media.register.api_lookup.status.query_requires_term"));' in html
    assert 'const loadingStatusText = t("media.register.api_lookup.status.query_loading", { source: requestSources[0] });' in html
    assert 'setStatus("barcodeStatus", "ok", loadingStatusText);' in html
    assert 'setStatus("barcodeStatus", "ok", t("media.register.api_lookup.status.query_done", {' in html
    assert 'setStatus("createStatus", "ok", t("media.register.direct.status.saving"));' in html
    assert 'setStatus("csvStatus", "ok", t("media.register.csv.status.uploading"));' in html
    assert 'setStatus("queueStatusBox", "ok", t("media.register.queue.status.loading"));' in html
    assert 'setStatus("ownedStatusBox", "ok", t("media.manage.owned.status.loading"));' in html
    assert 'setStatus("homeTrackMapStatus", "ok", t("media.manage.track_map.directory.status.files_loading"));' in html
    assert 'setStatus("trackMapStatus", "ok", t("media.manage.track_map.track.status.loading"));' in html
    assert 'setStatus("opsCameraStatus", "ok", t("ops.camera.status.selected", { camera: String(item.camera_name || "-") }));' in html
    assert 'setStatus("opsCabinetStatus", "ok", currentSummary ? t("ops.cabinet.status.saving_update") : t("ops.cabinet.status.saving_create"));' in html
    assert 'setStatus("opsSlotStatus", "ok", t("ops.slot.status.saving"));' in html


def test_media_register_api_lookup_runtime_copy_use_i18n():
    html = read_static_html("index.html")
    assert 'setStatus("barcodeStatus", "ok", t("media.register.api_lookup.status.lookup_inflight"));' in html
    assert 'setStatus("barcodeStatus", "ok", t("media.register.api_lookup.status.lookup_duplicate_skipped"));' in html
    assert 'const loadingStatusText = t("media.register.api_lookup.status.lookup_loading");' in html
    assert 'setStatus("barcodeStatus", "ok", loadingStatusText);' in html
    assert 'throw new Error(responseDetailText(data, t("media.register.api_lookup.status.lookup_failed")));' in html
    assert '? t("media.register.api_lookup.status.candidates_ready", { count: countWithUnit((candidates || []).length) })' in html
    assert ': t("media.register.api_lookup.status.no_candidates_register_direct")' in html
    assert '$("barcodeCount").textContent = t("media.register.api_lookup.results.loading");' in html
    assert 'root.innerHTML = `<div class=\'muted\'>${escapeHtml(t("media.register.api_lookup.results.empty"))}</div>`;' in html
    assert '$("barcodeResults").innerHTML = `<div class=\'muted\'>${escapeHtml(t("media.register.api_lookup.results.loading"))}</div>`;' in html
    assert 'setStatus("barcodeStatus", "err", errorMessageText(err, t("media.register.api_lookup.status.lookup_failed")));' in html
    assert 'setStatus("barcodeStatus", "err", errorMessageText(err, t("media.register.api_lookup.status.save_failed")));' in html
    assert 'registerBtn.textContent = isSaving ? t("media.register.api_lookup.action.save_loading") : (isQueued ? t("media.register.api_lookup.action.save_queued") : t("media.register.api_lookup.action.save_owned"));' in html


def test_api_lookup_results_render_explicit_owned_badge_for_registered_candidates():
    html = read_static_html("index.html")
    barcode_block = html.split("function renderBarcodeResults(items, opts = {}) {", 1)[1].split("function resetOpsSlotForm() {", 1)[0]
    assert "box.classList.toggle(\"is-owned\", Number(c.owned_count || 0) > 0 || Boolean(c.is_owned));" in barcode_block
    assert 'const ownedBadge = Number(c.owned_count || 0) > 0 || c.is_owned' in barcode_block
    assert 'album-result-status-badge owned admin-barcode-candidate-flag' in barcode_block
    assert 't("common.meta.already_owned", { count: countWithUnit(Number(c.owned_count || 0)) })' in barcode_block


def test_api_lookup_results_sort_registered_candidates_to_top_while_preserving_input_order_within_groups():
    html = read_static_html("index.html")
    barcode_block = html.split("function renderBarcodeResults(items, opts = {}) {", 1)[1].split("function resetOpsSlotForm() {", 1)[0]
    assert 'registerLookupCandidates = Array.isArray(items)' in barcode_block
    assert '.map((candidate, order) => ({' in barcode_block
    assert 'isOwned: Number(candidate.owned_count || 0) > 0 || Boolean(candidate.is_owned),' in barcode_block
    assert '.sort((a, b) => Number(b.isOwned) - Number(a.isOwned) || compareRegisterLookupCandidateDisplay(a.candidate, b.candidate) || a.order - b.order)' in barcode_block
    assert '.map(({ candidate }) => candidate)' in barcode_block


def test_api_lookup_results_sort_maniadb_variants_by_year_format_and_catalog_within_owned_groups():
    html = read_static_html("index.html")
    assert "function compareRegisterLookupCandidateDisplay(a, b) {" in html
    helper_block = html.split("function compareRegisterLookupCandidateDisplay(a, b) {", 1)[1].split("function renderBarcodeResults(items, opts = {}) {", 1)[0]
    barcode_block = html.split("function renderBarcodeResults(items, opts = {}) {", 1)[1].split("function resetOpsSlotForm() {", 1)[0]
    assert 'if (sourceA !== "MANIADB" || sourceB !== "MANIADB") return 0;' in helper_block
    assert 'const yearDiff = registerLookupCandidateSortYear(a) - registerLookupCandidateSortYear(b);' in helper_block
    assert 'const formatDiff = registerLookupCandidateFormatRank(a) - registerLookupCandidateFormatRank(b);' in helper_block
    assert 'const catalogDiff = compareCodeValue(aCatalog || "ZZZ", bCatalog || "ZZZ");' in helper_block
    assert '.sort((a, b) => Number(b.isOwned) - Number(a.isOwned) || compareRegisterLookupCandidateDisplay(a.candidate, b.candidate) || a.order - b.order)' in barcode_block


def test_cover_url_normalizer_repairs_legacy_maniadb_variant_paths_for_rendering():
    html = read_static_html("index.html")
    assert "function normalizeRenderableCoverUrl(value) {" in html
    helper_block = html.split("function normalizeRenderableCoverUrl(value) {", 1)[1].split("function cleanLinkedGoodsMemoryNote(value) {", 1)[0]
    assert 'replace(/^http:\\/\\/i\\.maniadb\\.com\\//i, "https://i.maniadb.com/")' in helper_block
    assert "function resolveAlternateManiadbCoverUrl(value) {" in helper_block
    assert 'normalized.match(/^(https:\\/\\/i\\.maniadb\\.com\\/images\\/album\\/\\d+\\/\\d+)_(\\d+)_([fb])\\.jpg$/i);' in helper_block
    assert 'normalized.match(/^(https:\\/\\/i\\.maniadb\\.com\\/images\\/album\\/\\d+\\/\\d+)_([fb])_(\\d+)\\.jpg$/i);' in helper_block
    assert "function applyBrokenCoverFallback(img) {" in helper_block
    assert 'img.id === "imageGalleryPreviewImg"' in helper_block
    assert 'img.closest(".album-result-cover, .home-master-member-preview-cover, .table-cover-thumb, .dashboard-move-cover, .operator-cover, .image-gallery-thumb")' in helper_block
    assert 'const primary = normalizeRenderableCoverUrl(row?.cover_image_url || row?.goods_primary_image_url);' in html
    assert 'const coverUrl = normalizeRenderableCoverUrl(c.cover_image_url);' in html
    assert 'const src = normalizeRenderableCoverUrl(url);' in html
    assert 'document.addEventListener("error", (e) => {' in html
    assert 'applyBrokenCoverFallback(e.target);' in html


def test_api_lookup_flow_retries_recommendation_and_save_requests_instead_of_plain_fetch():
    html = read_static_html("index.html")
    assert 'const res = await fetchWithRetry("/ingest/barcode/recommend-location"' in html
    assert 'const res = await fetchWithRetry("/owned-items"' in html
    assert 't("media.register.api_lookup.status.recommendation_failed")' in html
    assert 't("media.register.api_lookup.status.save_failed")' in html


def test_register_lookup_and_ops_slot_camera_remaining_runtime_copy_use_i18n():
    html = read_static_html("index.html")
    assert '"common.cabinet":' in html
    assert '"common.default":' in html
    assert '"common.meta.external_id":' in html
    assert '"common.meta.candidate_confidence":' in html
    assert '"media.register.api_lookup.status.slot_selection_required":' in html
    assert '"media.register.api_lookup.status.slot_not_found":' in html
    assert '"ops.slot.status.save_failed":' in html
    assert '"ops.slot.status.list_failed":' in html
    assert '"ops.camera.confirm_delete":' in html
    assert 'throw new Error(t("media.register.api_lookup.status.slot_selection_required"));' in html
    assert 'throw new Error(t("media.register.api_lookup.status.slot_not_found"));' in html
    assert '$("barcodeCount").textContent = countWithUnit(registerLookupCandidates.length);' in html
    assert 't("common.meta.external_id", { value: c.external_id || "-" })' in html
    assert 't("common.meta.candidate_confidence", { value: Number(c.confidence || 0).toFixed(3) })' in html
    assert 'fillRegisterLookupSelect(cabinetSelect, listRegisterLookupCabinets(), state.cabinet_name, t("common.cabinet"));' in html
    assert 'fillRegisterLookupSelect(floorSelect, listRegisterLookupFloors(state.cabinet_name), state.column_code, t("common.column"));' in html
    assert 'fillRegisterLookupSelect(cellSelect, listRegisterLookupCells(state.cabinet_name, state.column_code), state.cell_code, t("common.cell"));' in html
    assert ': t("common.default")}</td>' in html
    assert 'if (!res.ok) throw new Error(responseDetailText(data, t("ops.camera.status.discover_failed")));' in html
    assert 'if (!res.ok) throw new Error(responseDetailText(data, t("ops.camera.status.test_failed")));' in html
    assert 'if (!res.ok) throw new Error(responseDetailText(data, t("ops.camera.status.save_failed")));' in html
    assert 'const ok = window.confirm(t("ops.camera.confirm_delete", {' in html
    assert 'setStatus("opsCabinetStatus", "err", errorMessageText(err, t("ops.slot.status.list_failed")));' in html
    assert 'setStatus("opsSlotStatus", "err", errorMessageText(err, t("ops.slot.status.list_failed")));' in html
    assert 'if (!res.ok) throw new Error(responseDetailText(data, t("ops.slot.status.save_failed")));' in html


def test_collectibles_and_direct_register_lower_runtime_copy_use_i18n():
    html = read_static_html("index.html")
    assert '"common.new":' in html
    assert '"common.new_item":' in html
    assert '"common.flag.second_hand":' in html
    assert '"common.flag.signature_prefix":' in html
    assert '"common.action.link":' in html
    assert '"common.action.sync":' in html
    assert '"common.action.before":' in html
    assert '"common.action.after":' in html
    assert '"media.register.api_lookup.status.adjusted_source":' in html
    assert '"media.manage.owned.status.move_failed":' in html
    assert 'data?.slot_display_name ? String(data.slot_display_name).trim() : t("common.unspecified"),' in html
    assert 'const adjustedSourceText = usedSource !== selectedSource ? t("media.register.api_lookup.status.adjusted_source", { source: usedSource }) : "";' in html
    assert 'const createdTitle = String(payload.item_name_override || $("goodsItemName").value || "").trim() || t("common.new_item");' in html
    assert 'label_id: t("common.new"),' in html
    assert '}], t("media.register.direct.action.save"))) {' in html
    assert 'setStatus("createStatus", "ok", t("media.register.direct.status.cancelled"));' in html
    assert 'if (!res.ok) throw new Error(data.detail || t("media.register.direct.status.failed"));' in html
    assert 'setStatus("createStatus", "ok", t("media.register.direct.status.done", {' in html
    assert 'if (row.is_second_hand) flags.push(t("common.flag.second_hand"));' in html
    assert 'flags.push(t("common.flag.signature_prefix", { value: row.signature_type }));' in html
    assert '>${escapeHtml(t("common.action.link"))}</a>' in html
    assert '>${escapeHtml(t("common.action.sync"))}</button>' in html
    assert '>${escapeHtml(t("common.action.before"))}</button>' in html
    assert '>${escapeHtml(t("common.action.after"))}</button>' in html
    assert 'if (!res.ok) throw new Error(data.detail || t("media.manage.owned.status.move_failed"));' in html


def test_dashboard_system_queue_and_sort_runtime_copy_use_i18n():
    html = read_static_html("index.html")
    assert 'if (!res.ok) throw new Error(responseDetailText(data, t("dashboard.slot.status.load_failed")));' in html
    assert 'if (!res.ok) throw new Error(responseDetailText(data, t("ops.status.load_failed")));' in html
    assert 'setStatus("homeMasterSortArtistStatus", "err", t("media.manage.master.sort_artist.status.master_required"));' in html
    assert 'setStatus("homeMasterSortArtistStatus", "ok", t("media.manage.master.sort_artist.status.saving"));' in html
    assert 'if (!res.ok) throw new Error(responseDetailText(data, t("media.manage.master.sort_artist.status.save_failed")));' in html
    assert 'if (!res.ok) throw new Error(responseDetailText(data, t("media.register.csv.status.failed")));' in html
    assert 'if (!res.ok) throw new Error(responseDetailText(data, t("media.register.queue.status.load_failed")));' in html
    assert '$("queueTableBody").innerHTML = (data || []).map(queueRowHtml).join("") ||' in html
    assert '`<tr><td colspan=\'6\' class=\'muted\'>${escapeHtml(t("common.data_empty"))}</td></tr>`' in html
    assert 'if (!res.ok) throw new Error(responseDetailText(data, t("media.manage.owned.status.load_failed")));' in html
    assert '`<tr><td colspan=\'18\' class=\'muted\'>${escapeHtml(t("common.data_empty"))}</td></tr>`' in html


def test_home_master_manual_correction_controls_and_save_flow_exist():
    html = read_static_html("index.html")

    assert 'id="homeMasterCorrectionRow"' in html
    assert 'id="homeMasterCorrectionReleaseYear"' in html
    assert 'id="homeMasterCorrectionDomainCode"' in html
    assert 'id="homeMasterCorrectionNote"' in html
    assert 'id="homeMasterCorrectionSaveBtn"' in html
    assert 'id="homeMasterCorrectionStatus"' in html
    assert '"media.manage.master.correction.action.save":' in html
    assert '"media.manage.master.correction.status.saving":' in html
    assert '"media.manage.master.correction.status.saved":' in html
    assert '"media.manage.master.correction.status.cleared":' in html
    assert '"media.manage.master.correction.status.save_failed":' in html
    assert '"media.manage.master.correction.field.release_year.label":' in html
    assert '"media.manage.master.correction.field.domain_code.label":' in html
    assert '"media.manage.master.correction.field.note.label":' in html
    assert '"media.manage.master.correction.source_hint":' in html
    assert 'row.style.display = "grid";' in html

    save_block = html.split("    async function saveHomeMasterCorrection() {", 1)[1].split("    async function saveHomeMasterSortArtistName()", 1)[0]
    assert 'const res = await fetch(`/album-masters/${masterId}/correction`,' in save_block
    assert 'release_year: releaseYearValue,' in save_block
    assert 'domain_code: domainCodeValue,' in save_block
    assert 'override_note: overrideNoteValue,' in save_block
    assert 'homeMasterInfo.release_year = data.release_year || null;' in save_block
    assert 'homeMasterInfo.domain_code = data.domain_code || null;' in save_block
    assert 'homeMasterInfo.source_release_year = data.source_release_year || null;' in save_block
    assert 'homeMasterInfo.source_domain_code = data.source_domain_code || null;' in save_block
    assert 'homeMasterInfo.override_release_year = data.override_release_year || null;' in save_block
    assert 'homeMasterInfo.override_domain_code = data.override_domain_code || null;' in save_block
    assert 'homeMasterInfo.override_note = data.override_note || null;' in save_block


def test_lower_admin_empty_states_and_mode_hints_use_i18n_keys():
    html = read_static_html("index.html")
    assert 'summary.innerHTML = t("ops.camera.selection.new");' in html
    assert 't("ops.slot.list.state.empty")' in html
    assert 't("ops.cabinet.list.state.empty")' in html
    assert 't("ops.cabinet.slot_capacity.hint.custom"' in html
    assert 't("ops.cabinet.slot_capacity.hint.default"' in html
    assert '$(\"opsCabinetSaveBtn\").textContent = isEditMode ? t(\"ops.cabinet.action.update\") : t(\"ops.cabinet.action.save\");' in html
    assert 'hint.textContent = t("ops.cabinet.mode_hint.create");' in html
    assert 't("ops.cabinet.mode_hint.safe_edit")' in html
    assert 't("ops.cabinet.mode_hint.unsafe_edit")' in html
    assert 'info.textContent = t("media.manage.track_map.directory.state.none");' in html
    assert 't("media.manage.track_map.directory.table.empty_files")' in html
    assert 't("media.manage.track_map.directory.meta.recursive")' in html
    assert 't("media.manage.track_map.directory.meta.truncated")' in html
    assert 't("media.manage.track_map.directory.meta.summary"' in html
    assert 'title: t("media.manage.track_map.directory.pick_title")' in html


def test_remaining_runtime_copy_for_direct_register_exception_presets_and_manage_shelf_uses_i18n():
    html = read_static_html("index.html")
    assert '"dashboard.cabinet.unnamed":' in html
    assert '"dashboard.workbench.unslotted_assets":' in html
    assert '"dashboard.slot_mismatch.confirm":' in html
    assert '"ops.exception.field.preset.option.default":' in html
    assert '"ops.exception.banner.prefilled":' in html
    assert '"media.register.direct.master_link.confirm":' in html
    assert '"media.register.direct.status.done":' in html
    assert '"media.manage.location.summary.placeholder":' in html
    assert '"media.manage.shelf.status.loading":' in html
    assert '"media.manage.related_versions.state.click_to_open":' in html

    exception_block = html.split("function renderOpsExceptionPresetOptions() {", 1)[1].split("function applyDefaultOpsExceptionPreset() {", 1)[0]
    banner_block = html.split("function syncMasterExceptionBanner() {", 1)[1].split("function dashboardReleaseTypeLabel(value) {", 1)[0]
    slot_mismatch_block = html.split("function confirmSlotMismatchMove(targetSlot, items, actionLabel = t(\"common.action.move\")) {", 1)[1].split("function confirmSlotMismatchById(storageSlotId, items, actionLabel = t(\"common.action.save\")) {", 1)[0]
    direct_block = html.split("async function createQuickOwnedItem() {", 1)[1].split("function renderAdminManageSurface() {", 1)[0]
    clear_block = html.split("function clearHomeEditor() {", 1)[1].split("function applyHomeItemData(item, opts = {}) {", 1)[0]
    shelf_block = html.split("function renderHomeEditShelfTrack() {", 1)[1].split("async function loadHomeEditShelfWindow(ownedItemId, fallbackRow, requestSeq = 0) {", 1)[0]
    related_block = html.split("function homeRelatedVersionItemHtml(row, opts = {}) {", 1)[1].split("function renderHomeRelatedVersions() {", 1)[0]

    assert 't("ops.exception.field.preset.option.default"' in exception_block
    assert 't("ops.exception.banner.prefilled"' in banner_block
    assert 't("dashboard.slot_mismatch.confirm"' in slot_mismatch_block
    assert 't("media.register.direct.master_link.confirm")' in direct_block
    assert 'media.register.direct.status.done' in direct_block
    assert 't("media.manage.location.summary.placeholder")' in clear_block
    assert 't("media.manage.shelf.state.empty_layout")' in shelf_block
    assert 't("media.manage.related_versions.state.click_to_open")' in related_block


def test_operator_recent_and_search_result_cards_use_i18n_runtime_copy():
    html = read_static_html("index.html")
    helper_block = html.split("function buildOperatorDisplayTitleParts(row) {", 1)[1].split("function exactTitleArtistMatch(row, normalizedQuery) {", 1)[0]
    recent_block = html.split("function renderOperatorHomeRecentItems(items, options = {}) {", 1)[1].split("function renderOperatorFeedItems(items, options = {}) {", 1)[0]
    feed_block = html.split("function renderOperatorFeedItems(items, options = {}) {", 1)[1].split("function renderOperatorHomeRecentSections() {", 1)[0]
    search_block = html.split("function renderOperatorLookupResults() {", 1)[1].split("async function openOperatorCabinetLocationFromButton(button) {", 1)[0]
    summary_block = html.split("function renderOperatorHelperSummary() {", 1)[1].split("async function loadOperatorLookupResults() {", 1)[0]
    assert 'const artistPrefix = `${artist} - `.toLowerCase();' in helper_block
    assert "if (title.toLowerCase().endsWith(artist.toLowerCase())) {" in helper_block
    assert "const whenLabel = kind === \"moved\" ? t(\"operator.feed.meta.moved\") : t(\"operator.feed.meta.registered\");" in recent_block
    assert "const titleParts = buildOperatorDisplayTitleParts(row);" in recent_block
    assert "const whenText = formatOperatorCardDateTime(row.created_at);" in recent_block
    assert 'const currentLocation = buildOperatorLocationLabel(row);' in recent_block
    assert 'const releaseCountry = String(row.pressing_country || row.country || "").trim() || "-";' in recent_block
    assert 'const formatSummary = firstOperatorFormatLine(row.format_items);' in recent_block
    assert 'const runoutSample = operatorRunoutSampleText(row.runout_sample || row.runout_matrix || []);' in recent_block
    assert "const labelCatalogText = labelName && catalogSummary" in recent_block
    assert "const whenLabel = kind === \"moved\" ? t(\"operator.feed.meta.moved\") : t(\"operator.feed.meta.registered\");" in feed_block
    assert "const titleParts = buildOperatorDisplayTitleParts(row);" in feed_block
    assert "const whenText = formatOperatorCardDateTime(row.created_at);" in feed_block
    assert 'const releaseCountry = String(row.pressing_country || row.country || "").trim() || "-";' in feed_block
    assert 'const formatSummary = firstOperatorFormatLine(row.format_items);' in feed_block
    assert 'const runoutSample = operatorRunoutSampleText(row.runout_sample || row.runout_matrix || []);' in feed_block
    assert "const whenLabel = t(\"operator.feed.meta.registered\");" in search_block
    assert "const titleParts = buildOperatorDisplayTitleParts(row);" in search_block
    assert "const whenText = formatOperatorCardDateTime(row.created_at);" in search_block
    assert 'const currentLocation = buildOperatorLocationLabel(row);' in search_block
    assert 't("operator.helper.state.no_candidate")' in summary_block
    assert 't("operator.feed.state.unslotted")' in summary_block


def test_operator_search_result_cards_render_collector_style_meta_line():
    html = read_static_html("index.html")
    search_block = html.split("function renderOperatorLookupResults() {", 1)[1].split("async function openOperatorCabinetLocationFromButton(button) {", 1)[0]
    assert "const releaseCountry = String(row.pressing_country || row.country || \"\").trim() || \"-\";" in search_block
    assert "const formatSummary = firstOperatorFormatLine(row.format_items);" in search_block
    assert "const runoutSample = operatorRunoutSampleText(row.runout_sample || row.runout_matrix || []);" in search_block
    assert "const labelCatalogText = labelName && catalogSummary" in search_block
    assert '<span class="operator-label-chip">${escapeHtml(String(row.label_id || "").trim() || "-")}</span>' in search_block
    assert "const collectorMetaHtml = operatorCollectorMetaHtml(row);" in search_block
    assert '<div class="operator-meta-line">${collectorMetaHtml}</div>' in search_block
    assert 'runoutSample !== "-"' in search_block
    assert 'class="operator-meta-subline"' in search_block


def test_operator_recent_cards_render_collector_style_meta_line():
    html = read_static_html("index.html")
    recent_block = html.split("function renderOperatorHomeRecentItems(items, options = {}) {", 1)[1].split("function renderOperatorFeedItems(items, options = {}) {", 1)[0]
    assert "const releaseCountry = String(row.pressing_country || row.country || \"\").trim() || \"-\";" in recent_block
    assert "const formatSummary = firstOperatorFormatLine(row.format_items);" in recent_block
    assert "const runoutSample = operatorRunoutSampleText(row.runout_sample || row.runout_matrix || []);" in recent_block
    assert "const labelCatalogText = labelName && catalogSummary" in recent_block
    assert '<span class="operator-label-chip">${escapeHtml(String(row.label_id || "").trim() || "-")}</span>' in recent_block
    assert "const collectorMetaHtml = operatorCollectorMetaHtml(row);" in recent_block
    assert '${collectorMetaHtml}' in recent_block
    assert 'runoutSample !== "-"' in recent_block
    assert 'class="operator-meta-subline"' in recent_block


def test_operator_cards_render_compact_collector_meta_pairs():
    html = read_static_html("index.html")
    helper_block = html.split("    function operatorMetaPairHtml(label, value, options = {}) {", 1)[1].split("    function renderOperatorHomeRecentItems(items, options = {}) {", 1)[0]
    assert 'function operatorCollectorMetaHtml(row) {' in html
    assert 'operator.feed.meta.summary.release' in helper_block
    assert 'operator.feed.meta.summary.country' in helper_block
    assert 'operator.feed.meta.summary.label' in helper_block
    assert 'operator.feed.meta.summary.format' in helper_block
    assert ".operator-meta-pair {" in html
    assert ".operator-meta-key {" in html
    assert ".operator-meta-value {" in html


def test_manage_source_meta_summary_uses_compact_label_value_rows():
    html = read_static_html("index.html")
    summary_block = html.split("    function renderHomeSourceManagedMetaSummary() {", 1)[1].split("    function syncHomeSourceManagedMetaUi() {", 1)[0]
    assert '"media.manage.source_meta.label.source":' in html
    assert '"media.manage.source_meta.label.item":' in html
    assert '"media.manage.source_meta.label.format":' in html
    assert '"media.manage.source_meta.label.release":' in html
    assert '"media.manage.source_meta.label.country":' in html
    assert '"media.manage.source_meta.label.label":' in html
    assert '"media.manage.source_meta.label.barcode":' in html
    assert 'operatorMetaPairHtml(t("media.manage.source_meta.label.source"), `${sourceLabel}#${sourceExternalId}`)' in summary_block
    assert 'operatorMetaPairHtml(t("media.manage.source_meta.label.memo"), memoText, { subtle: true })' in summary_block
    assert '$("homeEditMusicSourceSummaryMain").innerHTML = mainSummaryHtml' in summary_block
    assert '$("homeEditMusicSourceSummarySub").innerHTML = subSummaryHtml' in summary_block
    assert '$("homeEditMusicSourceSummaryExtra").style.display = "none";' in summary_block
    assert '$("homeEditMusicSourceSummaryOps").style.display = "none";' in summary_block


def test_operator_cards_place_registered_or_moved_time_on_second_line():
    html = read_static_html("index.html")
    recent_block = html.split("function renderOperatorHomeRecentItems(items, options = {}) {", 1)[1].split("function renderOperatorFeedItems(items, options = {}) {", 1)[0]
    feed_block = html.split("function renderOperatorFeedItems(items, options = {}) {", 1)[1].split("function renderOperatorHomeRecentSections() {", 1)[0]
    search_block = html.split("function renderOperatorLookupResults() {", 1)[1].split("async function openOperatorCabinetLocationFromButton(button) {", 1)[0]
    assert 'operator-title-side-meta' in recent_block
    assert 'operator-title-side-meta' in feed_block
    assert 'operator-title-side-meta' in search_block
    assert 'operator-secondary-line' in recent_block
    assert 'operator-secondary-line' in feed_block
    assert 'operator-secondary-line' in search_block
    assert 'operator-title-side-stack' not in recent_block
    assert 'operator-title-side-stack' not in feed_block
    assert 'operator-title-side-stack' not in search_block
    assert 'operator-title-side-location-btn' in recent_block
    assert 'operator-title-side-location-btn' in feed_block
    assert 'operator-title-side-location-btn' in search_block
    assert 'operator-secondary-line-main' in recent_block
    assert 'operator-secondary-line-main' in feed_block
    assert 'operator-secondary-line-main' in search_block


def test_operator_recent_cards_gate_discogs_repair_button_on_eligibility():
    html = read_static_html("index.html")
    recent_block = html.split("function renderOperatorHomeRecentItems(items, options = {}) {", 1)[1].split("function renderOperatorFeedItems(items, options = {}) {", 1)[0]
    assert 'const repairDiscogsMasterSlot = discogsRepairSlotHtml("operator", {' in recent_block
    assert 'const canRepairDiscogsMaster = ownedItemId > 0 && normalizeSourceCode(row?.source_code) === "DISCOGS" && normalizeSourceCode(row?.linked_master_source_code) === "MANUAL";' not in recent_block
    assert 'data-operator-discogs-repair-slot="${id}"' in html
    assert '/discogs-repair-status' in html


def test_operator_lookup_click_handler_routes_discogs_master_repair_action():
    html = read_static_html("index.html")
    click_block = html.split("    async function handleOperatorLookupAction(e) {", 1)[1].split("    async function loadOperatorRequestList() {", 1)[0]
    assert 'const repairDiscogsMasterBtn = e.target.closest("[data-operator-repair-discogs-master]");' in click_block
    assert 'await fetchWithRetry(`/owned-items/${ownedItemId}/repair-discogs-master-link`, { method: "POST" }, {' in click_block
    assert 'await loadOperatorHomeRecentSections();' in click_block


def test_operator_cards_omit_previous_line_when_no_previous_history():
    html = read_static_html("index.html")
    recent_block = html.split("function renderOperatorHomeRecentItems(items, options = {}) {", 1)[1].split("function renderOperatorFeedItems(items, options = {}) {", 1)[0]
    feed_block = html.split("function renderOperatorFeedItems(items, options = {}) {", 1)[1].split("function renderOperatorHomeRecentSections() {", 1)[0]
    search_block = html.split("function renderOperatorLookupResults() {", 1)[1].split("async function openOperatorCabinetLocationFromButton(button) {", 1)[0]
    assert 'operator.feed.meta.previous' not in recent_block
    assert 'operator.feed.meta.previous' not in feed_block
    assert 'operator.feed.meta.previous' not in search_block


def test_operator_cards_use_current_location_button_under_title_side_time():
    html = read_static_html("index.html")
    recent_block = html.split("function renderOperatorHomeRecentItems(items, options = {}) {", 1)[1].split("function renderOperatorFeedItems(items, options = {}) {", 1)[0]
    feed_block = html.split("function renderOperatorFeedItems(items, options = {}) {", 1)[1].split("function renderOperatorHomeRecentSections() {", 1)[0]
    search_block = html.split("function renderOperatorLookupResults() {", 1)[1].split("async function openOperatorCabinetLocationFromButton(button) {", 1)[0]
    assert 'const currentLocationButton = hasCurrentTriplet' in recent_block
    assert 'const currentLocationButton = hasCurrentTriplet' in feed_block
    assert 'const currentLocationButton = hasCurrentTriplet' in search_block
    assert 'data-operator-open-cabinet' in recent_block
    assert 'data-operator-open-cabinet' in feed_block
    assert 'data-operator-open-cabinet' in search_block
    assert 'operator-secondary-line' in html
    assert 'operator-title-side-location-btn' in html


def test_operator_cards_render_label_id_as_outlined_chip():
    html = read_static_html("index.html")
    recent_block = html.split("function renderOperatorHomeRecentItems(items, options = {}) {", 1)[1].split("function renderOperatorFeedItems(items, options = {}) {", 1)[0]
    feed_block = html.split("function renderOperatorFeedItems(items, options = {}) {", 1)[1].split("function renderOperatorHomeRecentSections() {", 1)[0]
    search_block = html.split("function renderOperatorLookupResults() {", 1)[1].split("async function openOperatorCabinetLocationFromButton(button) {", 1)[0]
    assert 'operator-label-chip' in html
    assert '<div class="operator-secondary-line">' in recent_block
    assert '<div class="operator-secondary-line">' in feed_block
    assert '<div class="operator-secondary-line">' in search_block
    assert '<span class="operator-label-chip">${escapeHtml(String(row.label_id || "").trim() || "-")}</span>' in recent_block
    assert '<span class="operator-label-chip">${escapeHtml(String(row.label_id || "").trim() || "-")}</span>' in feed_block
    assert '<span class="operator-label-chip">${escapeHtml(String(row.label_id || "").trim() || "-")}</span>' in search_block
    assert 'operator-recent-meta' in recent_block
    assert 'operator-meta-line' in feed_block
    assert 'operator-meta-line' in search_block


def test_operator_cards_place_label_chip_before_time_on_second_line():
    html = read_static_html("index.html")
    recent_block = html.split("function renderOperatorHomeRecentItems(items, options = {}) {", 1)[1].split("function renderOperatorFeedItems(items, options = {}) {", 1)[0]
    feed_block = html.split("function renderOperatorFeedItems(items, options = {}) {", 1)[1].split("function renderOperatorHomeRecentSections() {", 1)[0]
    search_block = html.split("function renderOperatorLookupResults() {", 1)[1].split("async function openOperatorCabinetLocationFromButton(button) {", 1)[0]
    chip_expr = '<span class="operator-label-chip">${escapeHtml(String(row.label_id || "").trim() || "-")}</span>'
    time_expr = 'operator-title-side-meta'
    assert chip_expr in recent_block
    assert chip_expr in feed_block
    assert chip_expr in search_block
    assert recent_block.index(chip_expr) < recent_block.index(time_expr)
    assert feed_block.index(chip_expr) < feed_block.index(time_expr)
    assert search_block.index(chip_expr) < search_block.index(time_expr)


def test_operator_title_side_meta_uses_small_runout_sized_text():
    html = read_static_html("index.html")
    css_block = html.split(".operator-title-side-meta {", 1)[1].split("}", 1)[0]
    assert "font-size: 0.72rem;" in css_block


def test_media_search_and_manage_core_labels_use_i18n_keys():
    html = read_static_html("index.html")
    assert '<strong data-i18n="media.title">미디어</strong>' in html
    assert '<div class="mini" data-i18n="media.subtitle">검색, 관리, 등록/수집, 소스 보강을 한 흐름으로 묶습니다.</div>' in html
    assert 'id="mediaSearchModeBtn" class="subtab-btn active" type="button" data-i18n="media.mode.search"' in html
    assert 'id="mediaManageModeBtn" class="subtab-btn" type="button" data-i18n="media.mode.manage"' in html
    assert 'id="mediaRegisterModeBtn" class="subtab-btn" type="button" data-i18n="media.mode.register"' in html
    assert 'id="mediaSourceModeBtn" class="subtab-btn" type="button" data-i18n="media.mode.source"' in html

    assert 'data-page-help-open="media-search"' in html
    assert '<h2><span data-i18n="media.search.title">검색 / 리스트</span></h2>' in html
    assert '<div class="mini" data-i18n="media.search.subtitle">리스트는 마스터 기준입니다. 결과를 선택하면 보유 상품과 상세 수정 화면으로 이동합니다.</div>' in html
    assert '<h2><span data-i18n="media.search.section.owned_items">보유 상품 검색</span><span class="section-help-dot"' in html
    assert '<label for="homeArtist" data-i18n="media.search.field.artist.label">아티스트명</label>' in html
    assert 'id="homeArtist" data-i18n-placeholder="media.search.field.artist.placeholder"' in html
    assert '<label for="homeItemName" data-i18n="media.search.field.item_name.label">상품명</label>' in html
    assert 'id="homeItemName" data-i18n-placeholder="media.search.field.item_name.placeholder"' in html
    assert '<label for="homeReleaseYear" data-i18n="media.search.field.release_year.label">발매년</label>' in html
    assert 'id="homeReleaseYear" type="number" min="1900" max="2100" data-i18n-placeholder="media.search.field.release_year.placeholder"' in html
    assert 'data-page-help-open="media-manage"' in html
    assert '<label for="homeBarcode" data-i18n="media.search.field.barcode.label">바코드</label>' in html
    assert 'id="homeBarcode" data-i18n-placeholder="media.search.field.barcode.placeholder"' in html
    assert '<label for="homeCatalogNo" data-i18n="media.search.field.catalog_no.label">카탈로그</label>' in html
    assert 'id="homeCatalogNo" data-i18n-placeholder="media.search.field.catalog_no.placeholder"' in html
    assert 'id="homeSearchBtn" class="btn secondary icon-btn" type="button" data-i18n-title="common.search" data-i18n-aria-label="common.search"' in html
    assert 'id="homeResetBtn" class="btn ghost icon-symbol-btn icon-symbol-btn--reset" type="button" data-i18n-title="media.search.action.reset_filters" data-i18n-aria-label="media.search.action.reset_filters"' in html
    assert 'id="homeNewBtn" class="btn icon-btn" type="button" data-i18n-title="media.search.action.new_item" data-i18n-aria-label="media.search.action.new_item"' in html
    assert '<strong data-i18n="media.search.empty.title">검색 결과가 없습니다.</strong>' in html
    assert '<div class="mini" data-i18n="media.search.empty.body">신규 등록 또는 마스터 묶기(운영/연계) 후 다시 검색하세요.</div>' in html
    assert 'id="homeNoResultCreateBtn" class="btn" type="button" data-i18n="media.search.empty.action"' in html

    assert '<strong data-i18n="media.manage.empty.title">먼저 검색 결과를 선택하세요.</strong>' in html
    assert '<div class="mini" style="margin-top:6px;" data-i18n="media.manage.empty.body">검색 결과를 고르면 이 화면에서 편집과 위치 확인을 바로 이어서 진행할 수 있습니다.</div>' in html
    assert 'id="adminManageEmptyStateSearchBtn" class="btn ghost tiny" type="button" data-i18n="media.manage.empty.action"' in html
    assert '<div id="homeEditorSelectedLabel" class="mini" data-i18n="media.manage.selected_label">선택된 상품</div>' in html
    assert '<h2><span data-i18n="media.manage.location.title">장식장 / 위치 정보</span><span class="section-help-dot"' in html
    assert '<div id="homeEditShelfCenterText" class="mini" data-i18n="media.manage.location.center">선택된 상품 기준 장식장 배열</div>' in html
    assert 'id="homeRestorePreviousSlotBtn" class="btn ghost tiny" type="button" data-i18n="media.manage.location.action.restore_previous"' in html
    assert 'id="homeOpenDashboardSlotBtn" class="btn ghost tiny icon-symbol-btn icon-symbol-btn--open" type="button" title="대시보드에서 위치 정리" aria-label="대시보드에서 위치 정리" data-i18n="media.manage.location.action.open_dashboard"' in html
    assert '<strong data-i18n="media.manage.source_meta.title">소스 메타 요약</strong>' in html
    assert '<span id="homeEditMusicSourceSummaryHint" class="mini" data-i18n="media.manage.source_meta.hint">외부 소스 메타는 후보 교체로 갱신</span>' in html
    assert 'id="homeEditShelfPrevBtn" class="btn ghost shelf-nav-btn icon-symbol-btn icon-symbol-btn--previous" type="button" title="◀ 이전" aria-label="◀ 이전" data-i18n="media.manage.location.action.prev"' in html
    assert 'id="homeEditShelfNextBtn" class="btn ghost shelf-nav-btn icon-symbol-btn icon-symbol-btn--next" type="button" title="다음 ▶" aria-label="다음 ▶" data-i18n="media.manage.location.action.next"' in html
    assert '<label for="editArtistName" data-i18n="media.manage.field.artist_name.label">아티스트명</label>' in html
    assert 'id="editArtistName" data-i18n-placeholder="media.manage.field.artist_name.placeholder"' in html
    assert '<label for="editCatalogNo" data-i18n="media.manage.field.catalog_no.label">카탈로그 번호</label>' in html
    assert '<label for="editTrackList" data-i18n="media.manage.field.track_list.label">곡 리스트 (한 줄에 1곡)</label>' in html
    assert '<div class="home-product-edit-kicker" data-i18n="media.manage.product.kicker">바로 수정 가능</div>' in html
    assert '<h2 data-i18n="media.manage.product.title">상품 정보</h2>' in html
    assert '<label for="editItemName" data-i18n="media.manage.product.field.item_name.label">상품명</label>' in html
    assert 'id="editItemName" data-i18n-placeholder="media.manage.product.field.item_name.placeholder"' in html
    assert '<label for="editPurchaseSource" data-i18n="media.manage.product.field.purchase_source.label">구매처</label>' in html
    assert '<label for="editCoverCondition" data-i18n="media.manage.product.field.cover_condition.label">커버 컨디션</label>' in html
    assert '<label for="homeEditCoverImagePaste" data-i18n="media.manage.product.field.cover_upload.label">커버 직접 등록 / 붙여넣기 / URL</label>' in html
    assert '<label for="editGoodsImageUrls" data-i18n="media.manage.goods.field.image_urls.label">사진 URL (줄바꿈, 복수)</label>' in html
    assert 'id="homeEditSaveBtn" class="btn" data-i18n="media.manage.product.action.save"' in html
    assert 'id="homeEditDeleteBtn" class="btn ghost" type="button" data-i18n="media.manage.product.action.delete"' in html
    assert '<h2 data-i18n="media.manage.master.lookup.title">마스터 후보 조회 / 연결</h2>' in html
    assert 'id="homeMasterAddLoadBtn" class="btn ghost home-master-load-btn" type="button" data-i18n="media.manage.master.lookup.action.load"' in html
    assert '<summary class="home-master-results-summary home-manage-secondary-summary" data-i18n="media.manage.master.lookup.results.toggle">조회 후보 보기 / 접기</summary>' in html
    assert '<summary class="home-manage-secondary-summary" style="cursor:pointer;font-weight:700;" data-i18n="media.manage.master.fetch.title">다른 소스 상품 추가 (선택)</summary>' in html
    assert '<label for="homeMetaBarcode" data-i18n="media.manage.master.fetch.barcode.field.label">바코드</label>' in html
    assert 'id="homeMetaQueryBtn" class="btn ghost" type="button" data-i18n="media.manage.master.fetch.query.action.lookup"' in html
    assert '<h2 data-i18n="media.manage.master.delete.title">앨범(마스터) 삭제</h2>' in html
    assert 'id="homeMasterDeleteBtn" class="btn ghost" type="button" disabled data-i18n="media.manage.master.delete.action"' in html

    assert '"media.search.field.artist.label":' in html
    assert '"media.search.empty.body":' in html
    assert '"media.manage.location.title":' in html
    assert '"media.manage.product.title":' in html
    assert '"media.manage.field.artist_name.label":' in html
    assert '"media.manage.product.field.item_name.label":' in html
    assert '"media.manage.goods.field.image_urls.label":' in html
    assert '"media.manage.master.lookup.title":' in html
    assert '"media.manage.master.fetch.title":' in html
    assert '"media.manage.master.delete.title":' in html


def test_admin_search_and_manage_surfaces_are_split():
    html = read_static_html("index.html")
    assert 'id="tabMedia"' in html
    assert 'id="tabSearch"' in html
    assert 'id="tabManage"' in html
    assert 'id="homeSearchCard"' in html
    assert 'id="homeEditorCard"' in html


def test_search_result_open_switches_media_mode_to_manage():
    html = read_static_html("index.html")
    assert 'switchMediaMode("manage")' in html
    assert 'openAdminConsole("media")' in html


def test_search_result_open_defers_master_lookup_until_explicit_query():
    html = read_static_html("index.html")
    block = html.split("async function openHomeMasterForEdit(albumMasterId) {", 1)[1].split("async function homeSearchOwnedItems", 1)[0]
    assert 'resetHomeMasterLookupUi({ clearInputs: true });' in block
    assert "await loadHomeMasterMembers(masterId, { autoOpenFirst: true });" not in block
    assert "await loadHomeMasterAddVariants();" not in block
    assert "await loadHomeItemForEdit(firstOwnedItemId, { keepMasterContext: true, resetMasterLookupUi: true });" in block


def test_index_dashboard_workbench_action_buttons_use_compact_class():
    html = read_static_html("index.html")
    assert ".dashboard-workbench-actionbtn" in html


def test_index_dashboard_bulk_popover_supports_close_button_and_outside_click():
    html = read_static_html("index.html")
    assert '$("homeDashBulkCloseBtn").addEventListener("click", () => toggleDashboardSurfacePanel("BULK"));' in html
    click_block = html.split('    document.addEventListener("click", (e) => {', 1)[1].split('    document.addEventListener("keydown", (e) => {', 1)[0]
    assert 'const bulkPopover = $("homeDashBulkEditPanel");' in click_block
    assert 'const bulkToggleBtn = $("homeDashSlotBulkBtn");' in click_block
    assert 'if (homeDashSurfacePanel === "BULK") {' in click_block
    assert 'const insideBulkPopover = bulkPopover?.contains(e.target);' in click_block
    assert 'const clickedBulkToggle = bulkToggleBtn?.contains(e.target);' in click_block
    assert 'homeDashSurfacePanel = "";' in click_block
    assert 'renderDashboardSurfaceDock();' in click_block
    assert 'id="homeDashWorkbenchEditBtn" class="btn ghost tiny dashboard-workbench-actionbtn icon-symbol-btn icon-symbol-btn--edit"' in html
    assert 'id="homeDashWorkbenchRecommendBtn" class="btn ghost tiny dashboard-workbench-actionbtn"' in html
    assert 'id="homeDashWorkbenchSelectAllBtn" class="btn ghost tiny dashboard-workbench-actionbtn icon-symbol-btn icon-symbol-btn--select-all"' in html
    assert 'id="homeDashWorkbenchClearBtn" class="btn ghost tiny dashboard-workbench-actionbtn icon-symbol-btn icon-symbol-btn--clear-selection"' in html


def test_index_dashboard_workbench_embeds_controls_inside_cover_flow_surface():
    html = read_static_html("index.html")
    workbench_start = '          <section class="dashboard-panel dashboard-workbench-panel">'
    status = '        <div id="homeDashboardStatus" class="status"></div>'
    assert workbench_start in html
    assert status in html
    block = html.split(workbench_start, 1)[1].split(status, 1)[0]
    assert 'class="dashboard-slot-rack-surface dashboard-slot-rack-surface--interactive"' in block
    assert 'id="homeDashWorkbenchPageInfo"' in block
    assert 'id="homeDashWorkbenchPagePrevBtn"' in block
    assert 'id="homeDashWorkbenchPageNextBtn"' in block
    assert 'id="homeDashWorkbenchList" class="dashboard-workbench-list"' in block
    assert block.index('id="homeDashWorkbenchPagePrevBtn"') < block.index('id="homeDashWorkbenchList"')
    assert block.index('id="homeDashWorkbenchPageNextBtn"') > block.index('id="homeDashWorkbenchList"')


def test_index_dashboard_slot_cards_expose_per_cabinet_refresh_action():
    html = read_static_html("index.html")
    render_block = html.split("    function renderDashboardSlotCards(rows, totalInCollection) {", 1)[1].split("    async function loadDashboardSlotItems(slotRow, opts = {}) {", 1)[0]
    click_block = html.split('    $("homeDashSlotGrid").addEventListener("click", async (e) => {', 1)[1].split('    $("homeDashSlotGrid").addEventListener("dragover", (e) => {', 1)[0]
    panel_head_block = html.split('<section class="dashboard-panel dashboard-slot-panel">', 1)[1].split('<div class="dashboard-slot-map-shell">', 1)[0]
    assert 'id="homeDashSlotWindow"' in panel_head_block
    assert 'id="homeDashSlotRefreshBtn"' not in panel_head_block
    assert 'data-dashboard-cabinet-refresh="${encodeURIComponent(group.key)}"' in render_block
    assert 'dashboard-cabinet-refreshbtn' in render_block
    assert 'class="dashboard-cabinet-refreshicon" aria-hidden="true">↻</span>' in render_block
    assert 'const refreshBtn = e.target.closest("[data-dashboard-cabinet-refresh]");' in click_block
    assert 'await refreshDashboardCabinetGroup(cabinetKey);' in click_block


def test_index_dashboard_drag_box_selection_adds_surface_overlays_and_selectable_ids():
    html = read_static_html("index.html")
    assert 'id="homeDashSlotSelectionBox"' in html
    assert 'id="homeDashWorkbenchSelectionBox"' in html
    slot_item_block = html.split("function dashboardSlotItemHtml(row, index) {", 1)[1].split("function dashboardSlotListItemHtml", 1)[0]
    list_item_block = html.split("function dashboardSlotListItemHtml(row, index) {", 1)[1].split("function dashboardSlotShelfItemHtml", 1)[0]
    shelf_item_block = html.split("function dashboardSlotShelfItemHtml(row, index) {", 1)[1].split("function dashboardWorkbenchListItemHtml", 1)[0]
    workbench_item_block = html.split("function dashboardWorkbenchListItemHtml(row, source, index = 0) {", 1)[1].split("function dashboardWorkbenchShelfItemHtml", 1)[0]
    assert 'data-dashboard-selectable-id="${ownedItemId}"' in slot_item_block
    assert 'data-dashboard-selectable-id="${ownedItemId}"' in list_item_block
    assert 'data-dashboard-selectable-id="${ownedItemId}"' in shelf_item_block
    assert 'data-dashboard-selectable-id="${ownedItemId}"' in workbench_item_block


def test_index_dashboard_drag_box_selection_only_starts_from_empty_background_and_supports_directional_deselect():
    html = read_static_html("index.html")
    assert "let dashboardPointerSelectionState = null;" in html
    assert "function startDashboardPointerSelection(e, scope) {" in html
    assert "function updateDashboardPointerSelection(clientX, clientY) {" in html
    assert "function finishDashboardPointerSelection() {" in html
    slot_block = html.split('$("homeDashSlotItems").addEventListener("pointerdown", (e) => {', 1)[1].split('$("homeDashSlotItems").addEventListener("click", (e) => {', 1)[0]
    workbench_block = html.split('$("homeDashWorkbenchList").addEventListener("pointerdown", (e) => {', 1)[1].split('$("homeDashWorkbenchList").addEventListener("click", (e) => {', 1)[0]
    assert 'if (e.target.closest("[data-dashboard-selectable-id]")) return;' in slot_block
    assert 'if (e.target.closest("[data-dashboard-selectable-id]")) return;' in workbench_block
    assert 'startDashboardPointerSelection(e, "SLOT");' in slot_block
    assert 'startDashboardPointerSelection(e, "WORKBENCH");' in workbench_block
    start_block = html.split("function startDashboardPointerSelection(e, scope) {", 1)[1].split("function updateDashboardPointerSelection(clientX, clientY) {", 1)[0]
    finish_block = html.split("function finishDashboardPointerSelection() {", 1)[1].split("function resetDashboardSlotPage()", 1)[0]
    assert 'const isDeselectMode = state.currentRect.left < state.startX;' in finish_block
    assert 'altKey: Boolean(e.altKey),' not in start_block


def test_index_dashboard_drag_box_selection_exposes_live_preview_count_labels():
    html = read_static_html("index.html")
    assert 'id="homeDashSlotSelectionBoxLabel"' in html
    assert 'id="homeDashWorkbenchSelectionBoxLabel"' in html
    assert '"dashboard.selection.preview.add":' in html
    assert '"dashboard.selection.preview.remove":' in html
    update_block = html.split("function updateDashboardPointerSelection(clientX, clientY) {", 1)[1].split("function finishDashboardPointerSelection() {", 1)[0]
    assert 'const label = state.scope === "WORKBENCH"' in update_block
    assert 'const isDeselectMode = nextRect.left < state.startX;' in update_block
    assert 'label.textContent = isDeselectMode' in update_block
    assert 't("dashboard.selection.preview.add"' in update_block
    assert 't("dashboard.selection.preview.remove"' in update_block


def test_index_dashboard_drag_box_selection_updates_summary_and_supports_escape_cancel():
    html = read_static_html("index.html")
    assert '"dashboard.selection.summary.preview_add":' in html
    assert '"dashboard.selection.summary.preview_remove":' in html
    summary_block = html.split("function renderDashboardSelectionSummary() {", 1)[1].split("function resetDashboardBulkEditForm()", 1)[0]
    assert 'const previewSummary = dashboardPointerSelectionState?.didMove && dashboardPointerSelectionPreviewIds.length' in summary_block
    assert 't("dashboard.selection.summary.preview_add"' in summary_block
    assert 't("dashboard.selection.summary.preview_remove"' in summary_block
    assert "dashboardPointerSelectionState.currentRect.left < dashboardPointerSelectionState.startX" in summary_block
    assert "function cancelDashboardPointerSelection() {" in html
    assert 'if (dashboardPointerSelectionState?.didMove && e.key === "Escape") {' in html
    keydown_block = html.split('if (dashboardPointerSelectionState?.didMove && e.key === "Escape") {', 1)[1].split('document.addEventListener("keydown", (e) => {', 1)[0]
    assert 'cancelDashboardPointerSelection();' in keydown_block


def test_index_dashboard_drag_box_selection_reports_completion_in_dashboard_status():
    html = read_static_html("index.html")
    assert '"dashboard.selection.status.preview_added":' in html
    assert '"dashboard.selection.status.preview_removed":' in html
    finish_block = html.split("function finishDashboardPointerSelection() {", 1)[1].split("function cancelDashboardPointerSelection() {", 1)[0]
    assert 'setStatus(' in finish_block
    assert '"homeDashboardStatus"' in finish_block
    assert 't("dashboard.selection.status.preview_added"' in finish_block
    assert 't("dashboard.selection.status.preview_removed"' in finish_block
    assert 'const isDeselectMode = state.currentRect.left < state.startX;' in finish_block


def test_shell_utility_bar_removes_go_live_checklist_link():
    html = read_static_html("index.html")
    utility_block = html.split('<div class="shell-doc-links admin-shell-docs">', 1)[1].split("</div>", 1)[0]
    assert '/tool-docs/erd-summary' in utility_block
    assert '/tool-docs/erd-detail' in utility_block
    assert '/tool-docs/manual' in utility_block
    assert '/tool-docs/go-live-checklist' not in utility_block
    assert 'shell.admin.doc_link.checklist' not in utility_block


def test_index_dashboard_shift_click_selection_adds_slot_range_from_anchor():
    html = read_static_html("index.html")
    assert "let homeDashboardSlotSelectionAnchorId = 0;" in html
    assert "function selectDashboardSlotRangeToId(ownedItemId) {" in html
    slot_block = html.split('$("homeDashSlotItems").addEventListener("click", (e) => {', 1)[1].split('$("homeDashWorkbenchList").addEventListener("pointerdown", (e) => {', 1)[0]
    assert "if (e.shiftKey) {" in slot_block
    assert "selectDashboardSlotRangeToId(ownedItemId);" in slot_block


def test_index_dashboard_shift_click_selection_adds_workbench_range_from_anchor():
    html = read_static_html("index.html")
    assert "let homeDashboardUnassignedSelectionAnchorId = 0;" in html
    assert "let homeDashboardSearchSelectionAnchorId = 0;" in html
    assert "function selectDashboardWorkbenchRangeToId(ownedItemId, source) {" in html
    workbench_block = html.split('$("homeDashWorkbenchList").addEventListener("click", (e) => {', 1)[1].split('$("homeDashWorkbenchList").addEventListener("dragstart", (e) => {', 1)[0]
    assert "if (e.shiftKey) {" in workbench_block
    assert "selectDashboardWorkbenchRangeToId(ownedItemId, source);" in workbench_block


def test_index_dashboard_drag_contract_supports_selected_group_move_to_slots():
    html = read_static_html("index.html")
    assert "let dashboardDraggedSelectionIds = [];" in html
    assert 'text/x-dashboard-selection-ids' in html
    assert "function getDashboardDraggedSelectionIds(event) {" in html
    assert "function getDashboardDraggedRows(event) {" in html
    assert "const selectedRows = getDashboardDraggedRows(e);" in html
    assert "if (selectedRows.length > 1) {" in html
    assert "await moveDashboardOwnedItemsToSlot(selectedRows, targetSlotCode);" in html


def test_index_dashboard_workbench_dragstart_populates_group_drag_payload():
    html = read_static_html("index.html")
    start = '$("homeDashWorkbenchList").addEventListener("dragstart", (e) => {'
    end = '    $("homeDashWorkbenchList").addEventListener("dragend", () => {'
    assert start in html
    assert end in html
    block = html.split(start, 1)[1].split(end, 1)[0]
    assert "const selectedIds = Array.from(getDashboardWorkbenchSelectedIds())" in block
    assert "dashboardDraggedSelectionIds = selectedIds;" in block
    assert 'e.dataTransfer.setData("text/x-dashboard-selection-ids", JSON.stringify(selectedIds));' in block
    assert 'e.dataTransfer.setData("text/x-dashboard-drag-source", "WORKBENCH");' in block


def test_index_dashboard_removes_secondary_grid_and_moves_source_summary_into_hero():
    html = read_static_html("index.html")
    main_start = '        <div class="dashboard-main-grid">'
    slot_start = '          <section class="dashboard-panel dashboard-slot-panel">'
    workbench_start = '          <section class="dashboard-panel dashboard-workbench-panel">'
    status = '<div id="homeDashboardStatus" class="status"></div>'
    source_summary = 'id="homeDashSourceSummary"'
    assert main_start in html
    assert slot_start in html
    assert workbench_start in html
    assert status in html
    assert source_summary in html
    assert 'id="homeDashSourceCount"' not in html
    assert 'id="homeDashExternalSourceItems"' not in html
    assert 'id="homeDashRecentMoves"' not in html
    assert 'id="homeDashMoveWindow"' not in html
    assert html.index(main_start) < html.index(slot_start)
    assert html.index(slot_start) < html.index(workbench_start) < html.index(status)
    hero_block = html.split(".dashboard-hero-grid {", 1)[1].split("}", 1)[0]
    collector_block = html.split(".dashboard-hero-card.accent-collector {", 1)[1].split("}", 1)[0]
    linked_block = html.split(".dashboard-hero-card.accent-linked {", 1)[1].split("}", 1)[0]
    source_block = html.split("function renderDashboardSourceRows(rows, totalItems) {", 1)[1].split("function renderMetadataSyncSummary", 1)[0]
    assert "grid-template-columns: repeat(5, minmax(0, 1fr));" in hero_block
    assert "grid-column: span 2;" not in collector_block
    assert "grid-column: span 2;" not in linked_block
    assert 'const externalRows = list.filter((row) => {' in source_block
    assert 'if (!sourceValue || sourceValue === "MANUAL") return false;' in source_block
    assert "const topRows = externalRows.slice(0, 3);" in source_block


def test_index_dashboard_slot_detail_uses_compact_icon_actions_and_selected_item_edit_anchor():
    html = read_static_html("index.html")
    flow_start = '              <div class="dashboard-slot-rack-surface dashboard-slot-rack-surface--interactive">'
    flow_end = '              <div id="homeDashCabinetFloors" class="dashboard-floor-list" style="display:none !important;" aria-hidden="true"></div>'
    assert flow_start in html
    assert flow_end in html
    flow_block = html.split(flow_start, 1)[1].split(flow_end, 1)[0]
    assert 'dashboard-slot-actionbtn' in flow_block
    assert 'data-slot-action="select-all"' in flow_block
    assert 'data-slot-action="clear"' in flow_block
    assert 'data-slot-action="restore"' in flow_block
    assert 'data-slot-action="bulk"' in flow_block
    assert 'data-slot-action="front"' not in flow_block
    assert 'data-slot-action="back"' not in flow_block
    toolbar_block = html.split(".dashboard-selection-toolbar--slot-inline {", 1)[1].split("}", 1)[0]
    assert "gap: 7px;" in toolbar_block
    actions_block = html.split(".dashboard-selection-actions--slot-icons {", 1)[1].split("}", 1)[0]
    assert "gap: 4px;" in actions_block
    slot_panel_block = html.split(".dashboard-slot-panel {", 1)[1].split("}", 1)[0]
    assert "overflow: visible;" in slot_panel_block
    workbench_button_block = html.rsplit("\n    .dashboard-workbench-actionbtn {", 1)[1].split("}", 1)[0]
    button_block = html.rsplit("\n    .dashboard-slot-actionbtn {", 1)[1].split("}", 1)[0]
    assert "min-height: 40px;" in workbench_button_block
    assert "padding: 0 10px;" in workbench_button_block
    assert "font-size: 0.64rem;" in workbench_button_block
    assert "line-height: 1.05;" in workbench_button_block
    assert "border-radius: 6px;" in workbench_button_block
    assert "min-height: 40px;" in button_block
    assert "padding: 0 10px;" in button_block
    assert "font-size: 0.64rem;" in button_block
    assert "line-height: 1.05;" in button_block
    assert "border-radius: 6px;" in button_block


def test_index_manage_shelf_clicks_use_context_aware_edit_open_helper():
    html = read_static_html("index.html")
    assert "function shouldKeepHomeMasterContextForOwnedItem(ownedItemId) {" in html
    assert "function openHomeOwnedItemFromManageContext(ownedItemId, opts = {}) {" in html
    shelf_block = html.split("function renderHomeEditShelfTrack() {", 1)[1].split("async function loadHomeEditShelfWindow", 1)[0]
    assert "openHomeOwnedItemFromManageContext(Number(row.id));" in shelf_block
    assert '$("homeLocationSlotList").addEventListener("click", (e) => {' not in html


def test_index_manage_editor_hydrates_secondary_panels_after_showing_form():
    html = read_static_html("index.html")
    assert "async function hydrateHomeEditorSecondaryPanels(locationSeed, requestSeq = 0) {" in html
    assert "function scheduleHomeEditorSecondaryHydration(locationSeed, requestSeq = 0) {" in html
    assert "function scheduleHomeCollectorSummaryRefresh(requestSeq = 0) {" in html
    block = html.split("async function applyHomeEditorDetail(data, requestSeq = 0) {", 1)[1].split("async function loadHomeItemForEdit", 1)[0]
    assert "showHomeEditView();" in block
    assert "renderHomeLocationSlotList();\n      syncHomeMasterInlineEditor();" in block
    assert "scheduleHomeEditorSecondaryHydration(locationSeed, requestSeq);" in block
    assert block.index("showHomeEditView();") < block.index("scheduleHomeEditorSecondaryHydration(locationSeed, requestSeq);")
    assert "await loadHomeCollectorSummary();" not in block
    assert "await loadHomeEditShelfWindow(homeSelectedItemId, locationSeed);" not in block
    assert "await loadHomeRelatedVersions(homeSelectedItemId);" not in block
    hydrate_block = html.split("async function hydrateHomeEditorSecondaryPanels(locationSeed, requestSeq = 0) {", 1)[1].split("function scheduleHomeCollectorSummaryRefresh", 1)[0]
    assert "loadHomeLocationSlotItems(" not in hydrate_block


def test_index_manage_rerenders_park_inline_editor_before_replacing_related_lists():
    html = read_static_html("index.html")
    assert "function parkHomeMasterInlineEditor() {" in html
    related_block = html.split("function renderHomeRelatedVersions() {", 1)[1].split("async function saveHomeMasterSortArtistName()", 1)[0]
    assert "parkHomeMasterInlineEditor();" in related_block
    location_block = html.split("function renderHomeLocationSlotList() {", 1)[1].split("async function loadHomeLocationSlotItems", 1)[0]
    assert 'root.innerHTML = "";' in location_block


def test_index_manage_keeps_location_panel_focused_on_selected_item_only():
    html = read_static_html("index.html")
    assert '<div id="homeLocationSlotList" class="home-location-slot-list" style="display:none;"></div>' in html
    location_info_block = html.split("function renderHomeLocationInfo(row) {", 1)[1].split("async function restoreHomePreviousLocation()", 1)[0]
    assert "같은 칸" not in location_info_block


def test_index_manage_secondary_panel_loaders_accept_request_sequence_guards():
    html = read_static_html("index.html")
    assert "async function loadHomeCollectorSummary(requestSeq = 0) {" in html
    assert "async function loadHomeEditShelfWindow(ownedItemId, fallbackRow, requestSeq = 0) {" in html
    assert "async function loadHomeRelatedVersions(ownedItemId, requestSeq = 0) {" in html
    collector_block = html.split("async function loadHomeCollectorSummary(requestSeq = 0) {", 1)[1].split("function pickMappedDomain", 1)[0]
    shelf_block = html.split("async function loadHomeEditShelfWindow(ownedItemId, fallbackRow, requestSeq = 0) {", 1)[1].split("async function moveHomeEditShelf", 1)[0]
    related_block = html.split("async function loadHomeRelatedVersions(ownedItemId, requestSeq = 0) {", 1)[1].split("async function applyHomeEditorDetail", 1)[0]
    assert "if (requestSeq && !isActiveHomeEditRequest(requestSeq)) return;" in collector_block
    assert "if (requestSeq && !isActiveHomeEditRequest(requestSeq)) return;" in shelf_block
    assert "if (requestSeq && !isActiveHomeEditRequest(requestSeq)) return;" in related_block


def test_index_purchase_import_reads_uploaded_files_as_bytes_and_posts_base64_payload():
    html = read_static_html("index.html")
    upload_block = html.split("async function handlePurchaseImportFileChange(event) {", 1)[1].split("function resetPurchaseImportForm()", 1)[0]
    preview_block = html.split("async function previewPurchaseImport() {", 1)[1].split("async function savePurchaseImportQueue()", 1)[0]
    assert "await file.arrayBuffer()" in upload_block
    assert "await file.text()" not in upload_block
    assert "purchaseImportFileContentBase64" in html
    assert "raw_content_base64: purchaseImportFileContentBase64 || null" in preview_block
    assert "source_filename: purchaseImportFileName || null" in preview_block


def test_index_purchase_import_lists_keep_ebay_listing_title_while_candidate_lookup_uses_parsed_fields():
    html = read_static_html("index.html")
    assert "function purchaseImportDisplayTitle(row) {" in html
    title_block = html.split("function purchaseImportDisplayTitle(row) {", 1)[1].split("function purchaseImportItemNameHtml(row) {", 1)[0]
    assert 'if (vendorCode === "EBAY" && listingTitle) return listingTitle;' in title_block
    queue_state_block = html.split("function renderPurchaseImportQueue(items) {", 1)[1].split("async function previewPurchaseImport()", 1)[0]
    assert "function purchaseImportParsedArtistName(row) {" in html
    assert "function purchaseImportParsedItemName(row) {" in html
    assert 'artistName: String(prevState.artistName || purchaseImportParsedArtistName(row) || "").trim(),' in queue_state_block
    assert 'itemName: String(prevState.itemName || purchaseImportParsedItemName(row) || "").trim(),' in queue_state_block


def test_index_purchase_import_queue_shows_single_product_title_column_without_artist_split():
    html = read_static_html("index.html")
    queue_table_block = html.split('<strong data-i18n="media.register.purchase.queue.section.list">큐 목록</strong>', 1)[1].split("</table>", 1)[0]
    assert "<th>아티스트명</th>" not in queue_table_block
    assert '<th data-i18n="media.register.purchase.queue.header.item_name">상품명</th>' in queue_table_block
    queue_render_block = html.split("function renderPurchaseImportQueue(items) {", 1)[1].split("async function previewPurchaseImport()", 1)[0]
    assert '<td>${escapeHtml(String(row.artist_name || "").trim() || "-")}</td>' not in queue_render_block
    assert 'body.innerHTML = `<tr><td colspan="9" class="muted">${escapeHtml(t("media.register.purchase.queue.status.empty"))}</td></tr>`;' in queue_render_block


def test_index_purchase_import_queue_item_cell_shows_artist_with_title():
    html = read_static_html("index.html")
    block = html.split("function purchaseImportItemNameHtml(row) {", 1)[1].split("function purchaseImportRowDetailSummaryHtml(row) {", 1)[0]
    assert "const artist = purchaseImportParsedArtistName(row);" in block
    assert 'const parsedItemName = purchaseImportParsedItemName(row);' in block
    assert 'if (!artist || !parsedItemName || title !== parsedItemName) return titleHtml;' in block
    assert 'return `<div class="mini muted">${escapeHtml(artist)}</div><div>${titleHtml}</div>`;' in block


def test_index_manage_editor_schedules_secondary_hydration_after_next_frame_and_skips_smooth_scroll():
    html = read_static_html("index.html")
    show_block = html.split("function showHomeEditView() {", 1)[1].split("function isActiveHomeEditRequest", 1)[0]
    schedule_block = html.split("function scheduleHomeEditorSecondaryHydration(locationSeed, requestSeq = 0) {", 1)[1].split("async function applyHomeEditorDetail", 1)[0]
    assert 'scrollIntoView({ behavior: "auto", block: "start" });' in show_block
    assert 'behavior: "smooth"' not in show_block
    assert "requestAnimationFrame(() => {" in schedule_block
    assert "void hydrateHomeEditorSecondaryPanels(locationSeed, requestSeq);" in schedule_block


def test_index_manage_editor_parallelizes_shelf_and_defers_collector_summary_to_idle():
    html = read_static_html("index.html")
    hydrate_block = html.split("async function hydrateHomeEditorSecondaryPanels(locationSeed, requestSeq = 0) {", 1)[1].split("function scheduleHomeEditorSecondaryHydration", 1)[0]
    collector_block = html.split("function scheduleHomeCollectorSummaryRefresh(requestSeq = 0) {", 1)[1].split("function scheduleHomeEditorSecondaryHydration", 1)[0]
    assert "const panelLoads = [" in hydrate_block
    assert "Promise.all(panelLoads)" in hydrate_block
    assert "loadHomeEditShelfWindow(homeSelectedItemId, locationSeed, requestSeq)" in hydrate_block
    assert "loadHomeLocationSlotItems(" not in hydrate_block
    assert "loadHomeRelatedVersions(homeSelectedItemId, requestSeq)" not in hydrate_block
    assert "if (homeSelectedMasterId) renderHomeRelatedVersions();" in hydrate_block
    assert "scheduleHomeCollectorSummaryRefresh(requestSeq);" in hydrate_block
    assert "window.requestIdleCallback" in collector_block
    assert "window.setTimeout(run, 0);" in collector_block
    assert "void loadHomeCollectorSummary(requestSeq);" in collector_block


def test_index_manage_music_editor_expands_music_fields_for_selected_product():
    html = read_static_html("index.html")
    block = html.split("function syncHomeEditorMusicVisibility() {", 1)[1].split("function goToRegisterFromHome()", 1)[0]
    assert '$("homeEditMusicBox").style.display = isMusic ? "block" : "none";' in block
    assert '$("homeEditGoodsBox").style.display = isMusic ? "none" : "block";' in block


def test_index_manage_master_lookup_waits_for_explicit_query_button():
    html = read_static_html("index.html")
    assert "function resetHomeMasterLookupUi(opts = {}) {" in html
    assert "async function loadHomeManageMasterLookup(opts = {}) {" in html
    assert "function syncHomeMasterLookupPromptState() {" in html
    hydrate_block = html.split("async function hydrateHomeEditorSecondaryPanels(locationSeed, requestSeq = 0) {", 1)[1].split("function scheduleHomeCollectorSummaryRefresh", 1)[0]
    load_block = html.split("async function loadHomeItemForEdit(ownedItemId, opts = {}) {", 1)[1].split("function buildHomeEditPayload()", 1)[0]
    render_block = html.split("function renderHomeRelatedVersions() {", 1)[1].split("async function saveHomeMasterSortArtistName()", 1)[0]
    button_block = html.split('$("homeMasterAddLoadBtn").addEventListener("click",', 1)[1].split('$("homeMasterAddResetBtn")', 1)[0]
    assert "loadHomeRelatedVersions(homeSelectedItemId, requestSeq)" not in hydrate_block
    assert 'resetHomeMasterLookupUi({ clearInputs: true });' in load_block
    assert 'setTextIfPresent("homeMasterMeta", homeMasterMetaPlaceholderText());' in render_block
    assert '"media.manage.master.placeholder.pending_versions":' in html
    assert 'classList.toggle("home-master-lookup-pending", isPending)' in html
    assert 'setDisplayIfPresent("homeMasterSummarySection", "block");' in render_block
    assert "loadHomeManageMasterLookup({ resetPage: true })" in button_block


def test_index_manage_item_loader_can_reset_master_lookup_without_dropping_selected_master():
    html = read_static_html("index.html")
    block = html.split("async function loadHomeItemForEdit(ownedItemId, opts = {}) {", 1)[1].split("function buildHomeEditPayload()", 1)[0]
    assert "const resetMasterLookupUi = Boolean(opts.resetMasterLookupUi);" in block
    assert "if (!keepMasterContext) {" in block
    assert "if (!keepMasterContext || resetMasterLookupUi) {" in block


def test_index_manage_product_edit_and_master_lookup_use_distinct_visual_sections():
    html = read_static_html("index.html")
    assert "#homeEditorProductBlock {" in html
    assert "#homeManageMasterSection {" in html
    assert "#homeCabinetSection {" in html
    assert "#homeMasterAddBlock {" in html
    assert ".home-product-edit-kicker {" in html
    assert ".home-master-lookup-kicker {" in html
    assert ".home-master-load-btn {" in html
    assert ".home-master-lookup-note {" in html
    assert '<div class="home-product-edit-kicker" data-i18n="media.manage.product.kicker">바로 수정 가능</div>' in html
    assert '<div class="home-master-lookup-kicker" data-i18n="media.manage.master.lookup.kicker">후보 조회</div>' in html
    assert 'id="homeMasterSummarySection" style="display:none;"' in html
    assert 'class="btn ghost home-master-load-btn"' in html
    assert 'data-i18n="media.manage.master.lookup.note"' in html


def test_index_manage_structural_landing_uses_master_operations_copy():
    html = read_static_html("index.html")
    manage_block = html.split('<div id="homeManageMasterSection">', 1)[1].split('<div class="home-master-danger-zone">', 1)[0]
    assert 'data-i18n="media.manage.master.structure.kicker"' in manage_block
    assert 'data-i18n="media.manage.master.structure.note"' in manage_block
    assert 'data-i18n="media.manage.master.lookup.kicker"' in manage_block
    assert 'data-i18n="media.manage.master.lookup.title"' in manage_block
    assert 'data-i18n="media.manage.master.lookup.results.toggle"' in manage_block
    assert 'data-i18n="media.manage.master.fetch.title"' in manage_block


def test_index_manage_right_aligns_mutating_action_rows():
    html = read_static_html("index.html")
    assert ".home-manage-actions-right {" in html
    assert 'id="homeMasterAddActionRow" class="row home-manage-actions-right"' in html
    assert 'id="homeEditorActionRow" class="row home-manage-actions-right"' in html
    assert 'id="homeMasterDeleteActions" class="row home-manage-actions-right"' in html


def test_index_manage_master_lookup_uses_search_style_paginated_results_and_collapse():
    html = read_static_html("index.html")
    assert 'id="homeMasterLookupResultsDetails"' in html
    assert 'id="homeMasterAddResultsHead" class="result-head"' in html
    assert 'id="homeMasterAddResultsPager" class="pager"' in html
    assert 'id="homeMasterAddResults" class="result-list"' in html
    assert "function homeMasterAddVariantItemHtml(row) {" in html
    render_block = html.split('function renderHomeMasterAddVariants(items, emptyText = t("media.manage.master.placeholder.empty_versions")) {', 1)[1].split("async function loadHomeManageMasterLookup", 1)[0]
    assert 'const root = $("homeMasterAddResults");' in render_block
    assert 'rows.map(homeMasterAddVariantItemHtml).join("")' in render_block


def test_index_manage_places_master_delete_controls_below_product_editor():
    html = read_static_html("index.html")
    assert 'id="homeMasterDeleteBtn"' in html
    assert 'id="homeMasterDeleteCascade"' in html
    assert html.index('id="homeEditGoodsBox"') < html.index('id="homeMasterDeleteBtn"')
    assert html.index('id="homeMasterDeleteBtn"') < html.index('id="homeTrackMapBox"')


def test_index_manage_inline_editor_can_mount_into_related_location_or_standalone_targets():
    html = read_static_html("index.html")
    assert 'id="homeEditorStandaloneMount"' in html
    assert "function findHomeInlineEditorMountElement(ownedItemId) {" in html
    block = html.split("function findHomeInlineEditorMountElement(ownedItemId) {", 1)[1].split("function hasHomeMasterLookupSelection()", 1)[0]
    assert 'document.querySelector(`.home-related-item[data-owned-id="${targetId}"]`)' in block
    assert 'document.querySelector(`.home-location-slot-item[data-slot-owned-id="${targetId}"]`)' in block
    assert 'return $("homeEditorStandaloneMount");' in block


def test_index_manage_location_list_resyncs_inline_editor_after_slot_rows_render():
    html = read_static_html("index.html")
    block = html.split("async function loadHomeLocationSlotItems(storageSlotId, opts = {}) {", 1)[1].split("async function moveHomeLocationCurrentItem", 1)[0]
    assert "syncHomeMasterInlineEditor();" in block


def test_index_operator_feed_renderer_tracks_row_index_for_context_selection():
    html = read_static_html("index.html")
    block = html.split("function renderOperatorFeedItems(items, options = {}) {", 1)[1].split("function renderOperatorLookupResults()", 1)[0]
    assert "return list.map((row, index) => {" in block
    assert 'data-operator-context-index="${index}"' in block


def test_index_barcode_results_show_release_country_for_discogs_disambiguation():
    html = read_static_html("index.html")
    block = html.split("function renderBarcodeResults(items, opts = {}) {", 1)[1].split('$("barcodeResults").addEventListener("click", (e) => {', 1)[0]
    helper_block = html.split("function buildDiscogsStandardMetaHtml(row, opts = {}) {", 1)[1].split("function collectGalleryItems", 1)[0]
    assert 'const discogsMetaHtml = buildDiscogsStandardMetaHtml(c, { includeOwnedCount: true });' in block
    assert "const releaseCountry = String(row?.pressing_country || row?.country || \"\").trim() || \"-\";" in helper_block
    assert 't("common.meta.release_country", { value: escapeHtml(releaseCountry) })' in helper_block


def test_index_dashboard_row_click_uses_single_selection_helper_while_toggle_buttons_remain_multi_select():
    html = read_static_html("index.html")
    assert "function selectDashboardSingleSlotItemById(ownedItemId) {" in html
    assert "function selectDashboardSingleWorkbenchItemById(ownedItemId, source) {" in html
    slot_click_block = html.split('$("homeDashSlotItems").addEventListener("click", (e) => {', 1)[1].split('$("homeDashWorkbenchList").addEventListener("click", (e) => {', 1)[0]
    workbench_click_block = html.split('$("homeDashWorkbenchList").addEventListener("click", (e) => {', 1)[1].split('$("homeDashWorkbenchList").addEventListener("dragstart", (e) => {', 1)[0]
    assert "toggleDashboardSlotSelectionById(ownedItemId);" in slot_click_block
    assert "selectDashboardSingleSlotItemById(ownedItemId);" in slot_click_block
    assert "toggleDashboardWorkbenchSelectionById(ownedItemId, source);" in workbench_click_block
    assert "selectDashboardSingleWorkbenchItemById(ownedItemId, source);" in workbench_click_block


def test_index_dashboard_cover_flow_uses_generic_titles_and_force_hides_floor_grid():
    html = read_static_html("index.html")
    assert 'id="homeDashSlotItemsTitle"><span data-i18n="dashboard.cover_flow.title">커버 플로우</span>' in html
    assert '.dashboard-cabinet-detail #homeDashCabinetFloors {' in html
    assert 'display: none !important;' in html.split('.dashboard-cabinet-detail #homeDashCabinetFloors {', 1)[1].split('}', 1)[0]
    assert 'titleEl.textContent = t("dashboard.selection.title");' in html
    assert 'titleEl.textContent = t("dashboard.cover_flow.title");' in html


def test_index_dashboard_slot_detail_hides_bottom_slot_meta_when_slot_is_selected():
    html = read_static_html("index.html")
    start = "    function renderDashboardSlotItems(slotRow, cabinetGroup = null) {"
    end = "    function renderDashboardCabinetDetail() {"
    assert start in html
    assert end in html
    block = html.split(start, 1)[1].split(end, 1)[0]
    assert 'const setSlotMeta = (statusText = "", includeOccupancy = true) => {' in block
    assert 'metaEl.style.display = "";' in block


def test_index_dashboard_slot_move_controls_use_slot_selection_and_reposition_visible_page():
    html = read_static_html("index.html")
    sync_start = "    function syncDashboardSelectionControls() {"
    sync_end = "    function renderDashboardSelectionSummary() {"
    move_start = "    async function moveDashboardSlotSelectionToEdge(direction) {"
    move_end = "    function renderDashboardSlotItems(slotRow, cabinetGroup = null) {"
    assert sync_start in html
    assert sync_end in html
    assert move_start in html
    assert move_end in html
    sync_block = html.split(sync_start, 1)[1].split(sync_end, 1)[0]
    move_block = html.split(move_start, 1)[1].split(move_end, 1)[0]
    assert 'const restoreEnabled = slotSelectedCount === 1;' in sync_block
    assert 'homeDashboardSlotPage = mode === "FRONT" ? 0 : Number.MAX_SAFE_INTEGER;' in move_block
    assert 'homeDashboardSlotShelfScrollLeft = mode === "FRONT" ? 0 : Number.MAX_SAFE_INTEGER;' in move_block


def test_index_dashboard_cover_flow_accepts_dragged_workbench_items_into_current_slot():
    html = read_static_html("index.html")
    start = '$("homeDashSlotItems").addEventListener("drop", async (e) => {'
    end = '    $("opsSlotTableBody").addEventListener("click", (e) => {'
    assert start in html
    assert end in html
    block = html.split(start, 1)[1].split(end, 1)[0]
    assert "const selectedRows = getDashboardDraggedRows(e);" in block
    assert 'const currentSlotCode = String(homeDashboardSelectedSlotCode || "").trim();' in block
    assert "await moveDashboardOwnedItemsToSlot(selectedRows, currentSlotCode);" in block
    assert "await moveDashboardOwnedItemToSlot(draggedOwnedItemId, currentSlotCode);" in block


def test_index_dashboard_artist_sorted_slots_block_manual_reorder_interactions():
    html = read_static_html("index.html")

    helper_start = "    function dashboardSlotAllowsManualOrder(slotRow) {"
    helper_end = "    function getDashboardDraggedOwnedItemId(event) {"
    assert helper_start in html
    assert helper_end in html
    helper_block = html.split(helper_start, 1)[1].split(helper_end, 1)[0]
    assert 'String(slotRow?.cabinet_sort_policy || "ARTIST_RELEASE_TITLE").trim().toUpperCase() === "LABEL_ID"' in helper_block

    move_start = "    async function moveDashboardOwnedItemRelative(ownedItemId, targetOwnedItemId, position) {"
    move_end = "    async function moveDashboardSlotSelectionToEdge(direction) {"
    assert move_start in html
    assert move_end in html
    move_block = html.split(move_start, 1)[1].split(move_end, 1)[0]
    assert 'if (!dashboardSlotAllowsManualOrder(currentSlotRow)) {' in move_block
    assert 't("dashboard.order.locked_artist_slot")' in move_block


def test_index_dashboard_slot_drop_avoids_same_slot_reorder_for_artist_sorted_cabinets():
    html = read_static_html("index.html")

    drag_start = '$("homeDashSlotItems").addEventListener("dragover", (e) => {'
    drag_end = '$("homeDashSlotItems").addEventListener("dragleave", (e) => {'
    assert drag_start in html
    assert drag_end in html
    drag_block = html.split(drag_start, 1)[1].split(drag_end, 1)[0]
    assert "const currentSlotRow = getDashboardSlotRow(currentSlotCode);" in drag_block
    assert "dashboardSlotAllowsManualOrder(currentSlotRow) === false" in drag_block

    drop_start = '$("homeDashSlotItems").addEventListener("drop", async (e) => {'
    drop_end = '    $("opsSlotTableBody").addEventListener("click", (e) => {'
    assert drop_start in html
    assert drop_end in html
    drop_block = html.split(drop_start, 1)[1].split(drop_end, 1)[0]
    assert "const currentSlotRow = getDashboardSlotRow(currentSlotCode);" in drop_block
    assert 'setStatus("homeDashboardStatus", "err", t("dashboard.order.locked_artist_slot"));' in drop_block
    assert "resetDashboardDragState();" in drop_block


def test_index_dashboard_drag_highlight_strengthens_slot_targets_and_cover_flow_surface():
    html = read_static_html("index.html")
    assert ".dashboard-cabinet-map-cell.drop-ready" in html
    assert ".dashboard-floor-cell.drop-ready" in html
    assert "#homeDashSlotItems.drop-ready" in html
    clear_start = "    function clearDashboardDragHints() {"
    clear_end = "    function resetDashboardDragState() {"
    assert clear_start in html
    assert clear_end in html
    clear_block = html.split(clear_start, 1)[1].split(clear_end, 1)[0]
    assert 'document.querySelectorAll(".dashboard-floor-cell.drag-over, .dashboard-floor-cell.drop-ready")' in clear_block
    assert 'document.querySelectorAll(".dashboard-cabinet-map-cell.drag-over, .dashboard-cabinet-map-cell.drop-ready")' in clear_block
    assert '$("homeDashSlotItems")?.classList.remove("drop-ready");' in clear_block
    drag_start = '$("homeDashSlotItems").addEventListener("dragover", (e) => {'
    drag_end = '$("homeDashSlotItems").addEventListener("dragleave", (e) => {'
    assert drag_start in html
    assert drag_end in html
    drag_block = html.split(drag_start, 1)[1].split(drag_end, 1)[0]
    assert '$("homeDashSlotItems")?.classList.add("drop-ready");' in drag_block


def test_index_dashboard_uses_unified_neutral_teal_palette_tokens():
    html = read_static_html("index.html")
    assert "--dashboard-surface:" in html
    assert "--dashboard-surface-soft:" in html
    assert "--dashboard-accent:" in html
    assert "--dashboard-accent-soft:" in html
    assert "background: var(--dashboard-surface);" in html
    assert "border: 1px solid var(--dashboard-border);" in html


def test_index_storage_mapping_meta_chips_are_compact():
    html = read_static_html("index.html")
    start = ".dashboard-cabinet-summary-meta span,"
    end = ".dashboard-cabinet-preview {"
    assert start in html
    assert end in html
    block = html.split(start, 1)[1].split(end, 1)[0]
    assert "padding: 2px 6px;" in block
    assert "font-size: 0.58rem;" in block


def test_index_dashboard_cabinet_selection_uses_cover_flow_area_for_cabinet_overview():
    html = read_static_html("index.html")
    assert ".dashboard-cabinet-overview-grid" in html
    assert ".dashboard-cabinet-overview-card" in html
    assert '"dashboard.cabinet.overview_title":' in html
    start = "    function renderDashboardSlotItems(slotRow, cabinetGroup = null) {"
    end = "    function renderDashboardCabinetDetail() {"
    assert start in html
    assert end in html
    block = html.split(start, 1)[1].split(end, 1)[0]
    assert "if (!slotRow && cabinetGroup && !cabinetGroup.isUnassigned && !cabinetGroup.isOverflow)" in block
    assert 'titleEl.textContent = t("dashboard.cabinet.overview_title", { title: cabinetGroup.title });' in block
    assert "root.classList.add(\"dashboard-cabinet-overview-grid\");" in block
    assert "dashboard-cabinet-overview-card" in block


def test_index_dashboard_runtime_sections_use_i18n_keys():
    html = read_static_html("index.html")
    assert '"dashboard.cabinet.meta.free_slots":' in html
    assert '"common.mixed":' in html
    assert '"dashboard.selection.title":' in html
    assert '"dashboard.selection.slot_title":' in html
    assert '"dashboard.selection.meta.pick_other_slot":' in html
    assert '"dashboard.selection.state.no_slot":' in html
    assert '"dashboard.slot.status.unslotted_block":' in html
    assert '"dashboard.slot.status.missing_slot_id":' in html
    assert '"dashboard.slot.status.loading":' in html
    assert '"dashboard.slot.status.load_complete":' in html
    assert '"dashboard.recent.window":' in html
    assert '"dashboard.recent.in_out_window":' in html
    assert '"dashboard.recent.empty":' in html
    assert '"dashboard.recent.title_fallback":' in html
    assert '"ops.system.summary.loading":' in html
    assert '"ops.system.summary.warning_sync_error":' in html
    assert '"ops.system.summary.healthy_running":' in html
    assert '"ops.system.summary.healthy_idle":' in html
    assert '"ops.system.summary.failure":' in html
    assert '"ops.system.logs.recent_none":' in html
    assert '"ops.system.logs.recent_load_failed":' in html
    assert '"ops.system.qa.summary":' in html
    assert '"ops.system.qa.remaining_none":' in html
    assert '"ops.system.qa.load_failed":' in html

    slot_block = html.split("    function renderDashboardSlotItems(slotRow, cabinetGroup = null) {", 1)[1].split("    function renderDashboardCabinetDetail() {", 1)[0]
    assert 't("dashboard.selection.title")' in slot_block
    assert 't("dashboard.selection.slot_title")' in slot_block
    assert 't("dashboard.selection.meta.pick_other_slot")' in slot_block
    assert 't("dashboard.selection.state.no_slot")' in slot_block

    load_block = html.split("    async function loadDashboardSlotItems(slotRow, opts = {}) {", 1)[1].split("    function toggleDashboardCabinet(groupKey) {", 1)[0]
    assert 't("dashboard.slot.status.unslotted_block")' in load_block
    assert 't("dashboard.slot.status.missing_slot_id")' in load_block
    assert 't("dashboard.slot.status.loading"' in load_block
    assert 't("dashboard.slot.status.load_complete"' in load_block

    cards_block = html.split("    function renderDashboardSlotCards(rows, totalInCollection) {", 1)[1].split("    async function loadDashboardSlotItems(slotRow, opts = {}) {", 1)[0]
    assert 'dashboard.cabinet.meta.free_slots' in slot_block
    assert 't("common.mixed")' in slot_block

    recent_block = html.split("    function renderDashboardRecentMoves(rows, windowDays, totalMoves) {", 1)[1].split("    function renderDashboardSourceRows(rows, totalItems) {", 1)[0]
    assert 't("dashboard.recent.window"' in recent_block
    assert 't("dashboard.recent.in_out_window"' in recent_block
    assert 't("dashboard.recent.empty")' in recent_block
    assert 't("common.item_name_missing")' in recent_block

    system_block = html.split("    async function loadOpsSystemStatus() {", 1)[1].split("    function downloadFilenameFromResponse", 1)[0]
    assert 't("ops.system.summary.loading")' in system_block
    assert 't("ops.system.summary.warning_sync_error")' in system_block
    assert 't("ops.system.summary.healthy_running")' in system_block


def test_dashboard_move_and_manage_runtime_copy_use_i18n_keys():
    html = read_static_html("index.html")
    assert '"dashboard.workbench.status.unslotted_load_failed":' in html
    assert '"dashboard.selection.status.select_one_item_to_edit":' in html
    assert '"dashboard.move.done_bulk":' in html
    assert '"dashboard.move.item_done":' in html
    assert '"dashboard.order.done":' in html
    assert '"dashboard.order.edge_done":' in html
    assert '"media.manage.master.placeholder.pending_meta":' in html
    assert '"media.manage.location.status.current_unslotted":' in html
    assert '"ops.meta_sync.summary.auto_on":' in html
    assert '"ops.cabinet.status.delete_done":' in html

    dashboard_block = html.split("    async function loadDashboardUnassignedItems(opts = {}) {", 1)[1].split("    function renderDashboardSlotItems(slotRow, cabinetGroup = null) {", 1)[0]
    assert 't("dashboard.workbench.status.unslotted_load_failed")' in dashboard_block
    assert 't("dashboard.selection.status.select_one_item_to_edit")' in dashboard_block
    assert 't("dashboard.move.done_bulk"' in dashboard_block
    assert 't("dashboard.move.item_done"' in dashboard_block
    assert 't("dashboard.order.done"' in dashboard_block
    assert 't("dashboard.order.edge_done"' in dashboard_block

    manage_block = html.split("    function homeMasterMetaPlaceholderText() {", 1)[1].split("    function clearDashboardSlotAttention() {", 1)[0]
    assert 't("media.manage.master.placeholder.pending_meta")' in manage_block
    location_block = html.split("    async function openDashboardForCurrentLocation() {", 1)[1].split("    function triggerInlineDirectUpload", 1)[0]
    assert 't("media.manage.location.status.current_unslotted")' in location_block

    meta_sync_block = html.split("    function renderMetadataSyncSummary(data) {", 1)[1].split("    async function loadMetadataSyncStatus()", 1)[0]
    assert 't("ops.meta_sync.summary.auto_on"' in meta_sync_block

    delete_block = html.split("    async function deleteOpsStorageCabinet() {", 1)[1].split('    $("opsStorageCabinetForm").addEventListener', 1)[0]
    assert 't("ops.cabinet.status.delete_done"' in delete_block
    system_block = html.split("    async function loadOpsSystemStatus() {", 1)[1].split("    function downloadFilenameFromResponse", 1)[0]
    assert 't("ops.system.summary.healthy_idle")' in system_block
    assert 't("ops.system.summary.failure")' in system_block
    assert 't("ops.system.logs.recent_none")' in system_block
    assert 't("ops.system.logs.recent_load_failed")' in system_block
    assert 't("ops.system.qa.summary"' in system_block
    assert 't("ops.system.qa.remaining_none")' in system_block
    assert 't("ops.system.qa.load_failed")' in system_block


def test_master_search_and_home_meta_runtime_copy_use_i18n_keys():
    html = read_static_html("index.html")
    assert '"media.register.master.action.select_candidate":' in html
    assert '"media.register.master.state.selected":' in html
    assert '"media.register.master.state.variants_prompt":' in html
    assert '"media.register.master.state.candidates_empty":' in html
    assert '"media.register.master.status.query_required":' in html
    assert '"media.register.master.status.searching":' in html
    assert '"media.register.master.status.search_complete":' in html
    assert '"media.register.master.variant.link.discogs":' in html
    assert '"media.register.master.variant.cover_original":' in html
    assert '"media.register.master.variant.owned_count":' in html
    assert '"media.register.master.variant.status.loading":' in html
    assert '"media.register.master.variant.status.loaded":' in html
    assert '"media.register.master.variant.status.empty":' in html
    assert '"media.register.master.owned_items.status.loading":' in html
    assert '"media.register.master.owned_items.state.empty":' in html
    assert '"media.manage.master.fetch.results.empty":' in html
    assert '"media.manage.master.fetch.results.loading":' in html
    assert '"media.manage.master.fetch.results.applied":' in html
    assert '"media.manage.master.fetch.action.add_linked":' in html
    assert '"media.manage.master.fetch.status.master_required":' in html
    assert '"media.manage.master.fetch.status.master_or_item_required":' in html
    assert '"media.manage.master.fetch.status.candidate_required":' in html
    assert '"media.manage.master.fetch.status.adding_linked":' in html
    assert '"media.manage.master.fetch.status.added_linked":' in html
    assert '"media.manage.master.fetch.status.barcode_required":' in html
    assert '"media.manage.master.fetch.status.barcode_loading":' in html
    assert '"media.manage.master.fetch.status.query_required":' in html
    assert '"media.manage.master.fetch.status.query_loading":' in html
    assert '"media.manage.master.fetch.status.results_complete":' in html

    master_block = html.split("    function renderMasterCandidates(items) {", 1)[1].split("    function albumMasterGroupRowHtml(row) {", 1)[0]
    assert 't("media.register.master.state.candidates_empty")' in master_block
    assert 't("media.register.master.action.select_candidate")' in master_block
    assert 't("media.register.master.state.selected"' in master_block
    assert 't("media.register.master.state.variants_prompt")' in master_block
    assert 't("media.register.master.status.query_required")' in master_block
    assert 't("media.register.master.status.searching")' in master_block
    assert 't("media.register.master.status.search_complete"' in master_block
    assert 't("media.register.master.variant.link.discogs")' in master_block
    assert 't("media.register.master.variant.cover_original")' in master_block
    assert 't("media.register.master.variant.owned_count"' in master_block
    assert 't("media.register.master.variant.status.loading")' in master_block
    assert 't("media.register.master.variant.status.loaded"' in master_block
    assert 't("media.register.master.variant.status.empty")' in master_block
    assert 't("media.register.master.owned_items.status.loading")' in master_block
    assert 't("media.register.master.owned_items.state.empty")' in master_block

    home_meta_block = html.split("    function clearHomeMetaCandidates() {", 1)[1].split("    function homeMasterHeadingLabel(row) {", 1)[0]
    assert 't("media.manage.master.fetch.results.empty")' in home_meta_block
    assert 't("media.manage.master.fetch.results.loading")' in home_meta_block
    assert 't("media.manage.master.fetch.results.applied"' in home_meta_block
    assert 't("media.manage.master.fetch.action.add_linked")' in home_meta_block
    assert 't("media.manage.master.fetch.status.master_required")' in home_meta_block
    assert 't("media.manage.master.fetch.status.master_or_item_required")' in home_meta_block
    assert 't("media.manage.master.fetch.status.candidate_required")' in home_meta_block
    assert 't("media.manage.master.fetch.status.adding_linked"' in home_meta_block
    assert 't("media.manage.master.fetch.status.added_linked"' in home_meta_block
    assert 't("media.manage.master.fetch.status.barcode_required")' in home_meta_block
    assert 't("media.manage.master.fetch.status.barcode_loading"' in home_meta_block
    assert 't("media.manage.master.fetch.status.query_required")' in home_meta_block
    assert 't("media.manage.master.fetch.status.query_loading"' in home_meta_block
    assert 't("media.manage.master.fetch.status.results_complete"' in home_meta_block


def test_home_manage_runtime_copy_uses_i18n_keys():
    html = read_static_html("index.html")
    assert '"media.manage.search.matched_tracks":' in html
    assert '"media.manage.search.results_empty":' in html
    assert '"media.manage.master.members.status.master_required":' in html
    assert '"media.manage.master.members.status.loading":' in html
    assert '"media.manage.master.members.status.loaded":' in html
    assert '"media.manage.master.members.state.no_owned_items":' in html
    assert '"media.manage.master.variant.state.owned":' in html
    assert '"media.manage.master.variant.state.missing":' in html
    assert '"media.manage.master.variant.action.edit":' in html
    assert '"media.manage.master.variant.action.register":' in html
    assert '"media.manage.master.variant.cover_original":' in html
    assert '"media.manage.master.variant.status.master_required":' in html
    assert '"media.manage.master.variant.status.no_source_link":' in html
    assert '"media.manage.master.variant.status.unsupported_source":' in html
    assert '"media.manage.master.variant.status.selection_required":' in html
    assert '"media.manage.master.variant.status.registering":' in html
    assert '"media.manage.master.variant.status.register_done":' in html
    assert '"media.manage.master.edit.source_summary":' in html
    assert '"media.manage.master.edit.status.loading_first_item":' in html
    assert '"media.manage.master.edit.status.no_linked_items":' in html
    assert '"media.manage.master.sort_artist.status.saved":' in html
    assert '"media.manage.master.sort_artist.status.cleared":' in html
    assert '"media.manage.master.item.duplicate.required_master":' in html
    assert '"media.manage.master.item.duplicate.required_item":' in html
    assert '"media.manage.master.item.duplicate.progress":' in html
    assert '"media.manage.master.item.duplicate.failed":' in html
    assert '"media.manage.master.item.duplicate.done":' in html
    assert '"media.manage.master.item.delete.required":' in html
    assert '"media.manage.master.item.delete.confirm":' in html
    assert '"media.manage.master.item.delete.already_gone":' in html
    assert '"media.manage.master.item.delete.done":' in html
    assert '"media.manage.master.delete.required":' in html
    assert '"media.manage.master.delete.confirm.cascade":' in html
    assert '"media.manage.master.delete.confirm.keep_items":' in html
    assert '"media.manage.master.delete.cancelled":' in html
    assert '"media.manage.master.delete.progress":' in html
    assert '"media.manage.master.delete.done.cascade":' in html
    assert '"media.manage.master.delete.done.keep_items":' in html
    assert '"media.manage.collectibles.status.master_required":' in html
    assert '"media.manage.collectibles.status.item_name_required":' in html
    assert '"media.manage.collectibles.status.registering":' in html
    assert '"media.manage.collectibles.status.registered":' in html
    assert '"media.manage.edit.status.loading":' in html
    assert '"media.manage.edit.status.selected":' in html
    assert '"media.manage.edit.status.save_required":' in html
    assert '"media.manage.edit.status.save_cancelled":' in html
    assert '"media.manage.edit.status.saving":' in html
    assert '"media.manage.edit.status.saved":' in html
    assert '"media.manage.edit.status.delete_required":' in html
    assert '"media.manage.edit.status.delete_cancelled":' in html
    assert '"media.manage.edit.status.deleting":' in html
    assert '"media.manage.edit.status.deleted":' in html
    assert '"media.manage.related_versions.status.loading":' in html
    assert '"media.manage.related_versions.status.loaded":' in html
    assert '"media.manage.related_versions.group.same":' in html
    assert '"media.manage.related_versions.group.individual":' in html
    assert '"media.manage.related_versions.relation.album_master_bind":' in html
    assert '"media.manage.related_versions.relation.source_master":' in html
    assert '"media.manage.related_versions.relation.none":' in html
    assert '"media.manage.related_versions.summary":' in html
    assert '"media.manage.related_versions.summary.sort_artist":' in html
    assert '"media.manage.related_versions.state.empty_versions":' in html
    assert '"media.manage.related_versions.state.empty_music_versions":' in html
    assert '"media.manage.shelf.related.status.loading":' in html
    assert '"media.manage.shelf.related.status.loaded":' in html
    assert '"media.manage.shelf.status.move_required":' in html
    assert '"media.manage.shelf.status.move_missing_target":' in html

    manage_block = html.split("    function homeResultItemHtml(row) {", 1)[1].split("    async function searchOwnedAlbums()", 1)[0]
    assert 't("media.manage.search.matched_tracks"' in manage_block
    assert 't("media.manage.search.results_empty")' in manage_block
    assert "member_items_preview" in manage_block
    assert "homeExpandedMasterPreviewIds" in html
    assert 'data-home-toggle-member-preview' in html
    assert "homeMasterMemberPreviewHtml" in html
    assert "home-master-member-preview-list" in html
    assert "operator-label-chip" in html
    assert "operator-meta-subline" in html
    assert 't("common.count.more"' in manage_block
    assert 't("media.manage.master.members.status.master_required")' in manage_block
    assert 't("media.manage.master.members.status.loading")' in manage_block
    assert 't("media.manage.master.members.status.loaded"' in manage_block
    assert 't("media.manage.master.members.state.no_owned_items")' in manage_block
    assert 't("media.manage.master.variant.state.owned"' in manage_block
    assert 't("media.manage.master.variant.state.missing")' in manage_block
    assert 't("media.manage.master.variant.action.edit")' in manage_block
    assert 't("media.manage.master.variant.action.register")' in manage_block
    assert 't("media.manage.master.variant.cover_original")' in manage_block
    assert 't("media.manage.master.variant.status.master_required")' in manage_block
    assert 't("media.manage.master.variant.status.no_source_link")' in manage_block
    assert 't("media.manage.master.variant.status.unsupported_source")' in manage_block
    assert 't("media.manage.master.variant.status.selection_required")' in manage_block
    assert 't("media.manage.master.variant.status.registering"' in manage_block
    assert 't("media.manage.master.variant.status.register_done"' in manage_block
    assert 't("media.manage.master.edit.source_summary"' in manage_block
    assert 't("media.manage.master.edit.status.loading_first_item")' in manage_block
    assert 't("media.manage.master.edit.status.no_linked_items")' in manage_block
    assert 't("media.manage.master.sort_artist.status.saved"' in manage_block
    assert 't("media.manage.master.sort_artist.status.cleared")' in manage_block
    assert 't("media.manage.master.item.duplicate.required_master")' in manage_block
    assert 't("media.manage.master.item.duplicate.required_item")' in manage_block
    assert 't("media.manage.master.item.duplicate.progress"' in manage_block
    assert 't("media.manage.master.item.duplicate.failed")' in manage_block
    assert 't("media.manage.master.item.duplicate.done"' in manage_block
    assert 't("media.manage.master.item.delete.required")' in manage_block
    assert 't("media.manage.master.item.delete.confirm"' in manage_block
    assert 't("media.manage.master.item.delete.already_gone"' in manage_block
    assert 't("media.manage.master.item.delete.done"' in manage_block
    assert 't("media.manage.master.delete.required")' in manage_block
    assert 't("media.manage.master.delete.confirm.cascade"' in manage_block
    assert 't("media.manage.master.delete.confirm.keep_items"' in manage_block
    assert 't("media.manage.master.delete.cancelled")' in manage_block
    assert 't("media.manage.master.delete.progress"' in manage_block
    assert 't("media.manage.master.delete.done.cascade"' in manage_block
    assert 't("media.manage.master.delete.done.keep_items"' in manage_block
    assert 't("media.manage.collectibles.status.master_required")' in manage_block
    assert 't("media.manage.collectibles.status.item_name_required")' in manage_block
    assert 't("media.manage.collectibles.status.registering")' in manage_block
    assert 't("media.manage.collectibles.status.registered"' in manage_block
    assert 't("media.manage.edit.status.loading")' in manage_block
    assert 't("media.manage.edit.status.selected"' in manage_block
    assert 't("media.manage.edit.status.save_required")' in manage_block
    assert 't("media.manage.edit.status.save_cancelled")' in manage_block
    assert 't("media.manage.edit.status.saving")' in manage_block
    assert 't("media.manage.edit.status.saved"' in manage_block
    assert 'console.warn("saveHomeEditedItem post-save master refresh failed", err);' in manage_block
    assert 't("media.manage.edit.status.delete_required")' in manage_block
    assert 't("media.manage.edit.status.delete_cancelled")' in manage_block
    assert 't("media.manage.edit.status.deleting")' in manage_block
    assert 't("media.manage.edit.status.deleted"' in manage_block
    assert 't("media.manage.related_versions.status.loading")' in manage_block
    assert 't("media.manage.related_versions.status.loaded"' in manage_block
    assert 't("media.manage.related_versions.group.same"' in manage_block
    assert 't("media.manage.related_versions.group.individual"' in manage_block
    assert 't("media.manage.related_versions.relation.album_master_bind")' in manage_block
    assert 't("media.manage.related_versions.relation.source_master")' in manage_block
    assert 't("media.manage.related_versions.relation.none")' in manage_block
    assert 't("media.manage.related_versions.summary"' in manage_block
    assert 't("media.manage.related_versions.summary.sort_artist"' in manage_block
    assert 't("media.manage.related_versions.state.empty_versions")' in manage_block
    assert 't("media.manage.related_versions.state.empty_music_versions")' in manage_block
    assert 't("media.manage.shelf.related.status.loading")' in manage_block
    assert 't("media.manage.shelf.related.status.loaded"' in manage_block
    assert 't("media.manage.shelf.status.move_required")' in manage_block
    assert 't("media.manage.shelf.status.move_missing_target")' in manage_block
    save_block = manage_block.split("async function saveHomeEditedItem() {", 1)[1].split("async function deleteHomeSelectedItem()", 1)[0]
    assert 'refreshHomeManageContext(ownedItemId, {' not in save_block
    assert 'if (homeSelectedMasterId) {' in save_block
    assert 'loadHomeMasterMembers(homeSelectedMasterId, { autoOpenFirst: false }).catch((err) => {' in save_block


def test_media_master_binding_and_source_helper_runtime_copy_uses_i18n():
    html = read_static_html("index.html")
    assert '"media.register.master.bind.status.instructions":' in html
    assert '"media.register.master.bind.status.no_master":' in html
    assert '"media.register.master.bind.status.no_owned_items":' in html
    assert '"media.register.master.bind.status.saving":' in html
    assert '"media.register.master.bind.status.failed":' in html
    assert '"media.register.master.bind.status.done":' in html
    assert '"media.register.master.group.status.loading":' in html
    assert '"media.register.master.group.status.failed":' in html
    assert '"media.register.master.group.state.empty":' in html
    assert '"media.source.status.queue_cleared":' in html
    assert '"media.source.status.search_reset":' in html

    block = html.split("    function syncMasterExceptionBanner() {", 1)[1].split('    $("masterSearchBtn").onclick = searchAlbumMasters;', 1)[0]
    assert 't("media.register.master.bind.status.instructions")' in block
    assert 't("media.register.master.bind.status.no_master")' in block
    assert 't("media.register.master.bind.status.no_owned_items")' in block
    assert 't("media.register.master.bind.status.saving")' in block
    assert 't("media.register.master.bind.status.failed")' in block
    assert 't("media.register.master.bind.status.done"' in block
    assert 't("media.register.master.group.status.loading")' in block
    assert 't("media.register.master.group.status.failed")' in block
    assert 't("media.register.master.group.state.empty")' in block
    assert 't("media.source.status.queue_cleared")' in block
    assert 't("media.source.status.search_reset")' in block


def test_index_storage_mapping_uses_per_slot_heatmap_tiles_inside_each_cabinet_board():
    html = read_static_html("index.html")
    start = "    function renderDashboardSlotCards(rows, totalInCollection) {"
    end = "    async function loadDashboardSlotItems(slotRow, opts = {}) {"
    assert start in html
    assert end in html
    block = html.split(start, 1)[1].split(end, 1)[0]
    assert 'class="dashboard-cabinet-map"' in block
    assert 'class="dashboard-cabinet-map-floor"' in block
    assert 'class="dashboard-cabinet-map-floorcode"' in block
    assert 'class="dashboard-cabinet-map-cells"' in block
    assert 'style="--cell-count:${Math.max(1, floorRows.length)};"' in block
    assert 'class="dashboard-cabinet-map-cell' in block
    assert 'data-dashboard-map-slot-code="' in block
    assert "dashboardCabinetMapCellTone" in block
    assert "dashboardCabinetOccupancyLabel(row)" in block


def test_index_storage_mapping_fill_palette_tracks_size_group_colors():
    html = read_static_html("index.html")
    block = html.split("    function dashboardCabinetMapCellTone(slotRow) {", 1)[1].split("    function dashboardCabinetMapSizeClass(slotRow) {", 1)[0]
    assert "const palette = {" in block
    assert "LP:" in block
    assert "STD:" in block
    assert "OVERSIZE:" in block
    assert "CASSETTE:" in block
    assert "GOODS:" in block
    assert "const steps = palette[sizeGroup] || palette.STD;" in block


def test_index_storage_mapping_slot_tiles_render_occupancy_ratio_or_percent():
    html = read_static_html("index.html")
    start = "    function dashboardCabinetOccupancyRatio(slotRow) {"
    end = "    function dashboardCabinetMapCellTone(slotRow) {"
    assert start in html
    assert end in html
    block = html.split(start, 1)[1].split(end, 1)[0]
    ratio_first = block.index("const occupancyRatio = Number(slotRow?.occupancy_ratio);");
    percent_first = block.index("const occupancyPercent = Number(slotRow?.occupancy_percent);");
    assert "Math.min(1, occupancyRatio)" not in block
    assert "Math.min(1, occupancyPercent / 100)" not in block
    assert ratio_first < percent_first
    assert "occupancy_percent" in block
    assert "occupancy_ratio" in block
    assert "occupancyPercent" in block
    assert "occupancyRatio" in block

    render_start = "    function renderDashboardSlotCards(rows, totalInCollection) {"
    render_end = "    async function loadDashboardSlotItems(slotRow, opts = {}) {"
    assert render_start in html
    assert render_end in html
    render_block = html.split(render_start, 1)[1].split(render_end, 1)[0]
    assert "const occupancy = dashboardCabinetOccupancyLabel(row);" in render_block
    assert "const occupancyTone = dashboardCabinetMapCellTone(row);" in render_block
    assert "const sizeGroupText = dashboardSizeGroupLabel(row?.allowed_size_group || \"-\");" in render_block
    assert "const occupancyText = occupancy.usedText" in render_block
    assert '--tile-count-bg:${occupancyTone.countBg};--tile-count-border:${occupancyTone.countBorder};--tile-count-fg:${occupancyTone.countFg};' in render_block
    assert 'dashboard-cabinet-map-cellcount">${escapeHtml(occupancy.percentText)}' in render_block
    assert 'dashboard-cabinet-map-cellmeta">${escapeHtml(cellMetaText)}' in render_block

    label_start = "    function dashboardCabinetOccupancyLabel(slotRow) {"
    label_end = "    function dashboardCabinetMapCellTone(slotRow) {"
    assert label_start in html
    assert label_end in html
    label_block = html.split(label_start, 1)[1].split(label_end, 1)[0]
    assert "Math.floor(ratio * 100)" in label_block
    assert "occupancyPercent" not in label_block
    assert "Math.round(ratio * 100)" not in label_block
    assert "Math.min(100" not in label_block
    assert "const capacity = Number(slotRow?.capacity_mm);" in label_block
    assert "const usedThickness = Number(slotRow?.used_thickness_mm);" in label_block


def test_index_storage_mapping_slot_tiles_allow_over_100_occupancy_labels():
    html = read_static_html("index.html")
    ratio_start = "    function dashboardCabinetOccupancyRatio(slotRow) {"
    ratio_end = "    function dashboardCabinetOccupancyLabel(slotRow) {"
    label_start = "    function dashboardCabinetOccupancyLabel(slotRow) {"
    label_end = "    function dashboardCabinetMapCellTone(slotRow) {"
    assert ratio_start in html
    assert ratio_end in html
    assert label_start in html
    assert label_end in html
    ratio_block = html.split(ratio_start, 1)[1].split(ratio_end, 1)[0]
    assert "return Math.max(0, occupancyRatio);" in ratio_block
    assert "return Math.max(0, occupancyPercent / 100);" in ratio_block
    label_block = html.split(label_start, 1)[1].split(label_end, 1)[0]
    assert "const percentText = `${Math.max(0, Math.floor(ratio * 100)).toFixed(0)}%`;" in label_block


def test_index_storage_mapping_keeps_size_fill_hover_and_selection_as_separate_visual_channels():
    html = read_static_html("index.html")
    cell_block = html.split(".dashboard-cabinet-map-cell {", 1)[1].split("}", 1)[0]
    hover_block = html.split(".dashboard-cabinet-map-cell:hover,\n    .dashboard-cabinet-map-cell.drag-over,\n    .dashboard-cabinet-map-cell.drop-ready {", 1)[1].split("}", 1)[0]
    active_block = html.split(".dashboard-cabinet-map-cell.active {", 1)[1].split("}", 1)[0]
    assert "background: color-mix(in srgb, var(--tile-bg, #f8fafc) 90%, white 10%);" in cell_block
    assert "transform: translateY(-1px);" in hover_block
    assert "background: color-mix(in srgb, var(--tile-bg, #f8fafc) 94%, white 6%);" in hover_block
    assert "border-color: color-mix(in srgb, var(--tile-border, #cbd5e1) 78%, #0ea5e9 22%);" in hover_block
    assert "background: color-mix(in srgb, var(--tile-bg, #f8fafc) 92%, white 8%);" in active_block
    assert "border-color: var(--selected-accent-strong);" in active_block
    assert "0 0 0 4px var(--selected-ring)" in active_block


def test_dashboard_move_updates_slot_occupancy_locally_using_box_set_thickness_rules():
    html = read_static_html("index.html")
    assert "function dashboardResolveOwnedItemThicknessMm(row, slotRow) {" in html
    helper_block = html.split("function dashboardResolveOwnedItemThicknessMm(row, slotRow) {", 1)[1].split("function dashboardApplySlotOccupancyDelta(slotRow, deltaMm) {", 1)[0]
    assert 'const slotIsBoxSet = slotSizeGroup === "OVERSIZE";' in helper_block
    assert "const explicitThickness = Number(row?.thickness_mm || 0);" in helper_block
    assert "normalizedDiscCount > 0 ? Math.max(1, Math.ceil(baseThickness * normalizedDiscCount * 1.2)) : 12" in helper_block

    update_block = html.split("function updateDashboardSlotCountsAfterMove(items, targetRow) {", 1)[1].split("function updateDashboardOwnedItemLocation(ownedItemId, targetRow) {", 1)[0]
    assert "dashboardApplySlotOccupancyDelta(sourceRow, -dashboardResolveOwnedItemThicknessMm(row, sourceRow));" in update_block
    assert "dashboardApplySlotOccupancyDelta(targetRow, dashboardResolveOwnedItemThicknessMm(row, targetRow));" in update_block


def test_index_storage_mapping_limits_visible_cabinets_to_two_with_prev_next_controls():
    html = read_static_html("index.html")
    assert 'id="homeDashSlotGridPrevBtn"' in html
    assert 'id="homeDashSlotGridNextBtn"' in html
    assert 'id="homeDashSlotGridInfo"' in html
    grid_block = html.split(".dashboard-slot-grid {", 1)[1].split("}", 1)[0]
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in grid_block
    assert ".dashboard-slot-grid.is-single {" not in html
    start = "    function renderDashboardSlotCards(rows, totalInCollection) {"
    end = "    async function loadDashboardSlotItems(slotRow, opts = {}) {"
    assert start in html
    assert end in html
    block = html.split(start, 1)[1].split(end, 1)[0]
    assert "const pageSize = 2;" in block
    assert "const pageCount = Math.max(1, Math.ceil(groups.length / pageSize));" in block
    assert "const visibleGroups = groups.slice(startIndex, startIndex + pageSize);" in block
    assert "updateDashboardSlotGridControls(groups, startIndex, pageSize);" in block
    assert "if (selectedGroupIndex >= 0 && homeDashboardSlotGridFollowSelection) {" in block
    prev_handler = html.split('    $("homeDashSlotGridPrevBtn").addEventListener("click", () => {', 1)[1].split('    $("homeDashSlotGridNextBtn").addEventListener("click", () => {', 1)[0]
    next_handler = html.split('    $("homeDashSlotGridNextBtn").addEventListener("click", () => {', 1)[1].split('    $("homeDashCabinetFloors").addEventListener("click", async (e) => {', 1)[0]
    for handler in (prev_handler, next_handler):
        assert "homeDashboardSlotGridFollowSelection = false;" in handler
        assert "homeDashboardSelectedCabinetKey = null;" not in handler
        assert "homeDashboardSelectedSlotCode = null;" not in handler

    open_block = html.split("    async function openDashboardForResolvedSlot(slotRow, opts = {}) {", 1)[1].split("    function findDashboardSlotByTriplet", 1)[0]
    assert "homeDashboardSlotGridFollowSelection = true;" in open_block


def test_index_dashboard_cabinet_detail_hides_floor_grid_below_cover_flow():
    html = read_static_html("index.html")
    start = "    function renderDashboardCabinetDetail() {"
    end = "    function summarizeStorageCabinets(rows) {"
    assert start in html
    assert end in html
    block = html.split(start, 1)[1].split(end, 1)[0]
    assert 'floorsRoot.style.display = "none";' in block


def test_index_storage_mapping_grid_clamps_min_width_to_avoid_panel_overflow():
    html = read_static_html("index.html")
    for selector in (
        ".dashboard-slot-map-shell {",
        ".dashboard-slot-grid-frame {",
        ".dashboard-slot-grid-panel {",
        ".dashboard-slot-grid {",
        ".dashboard-cabinet-board {",
        ".dashboard-cabinet-map {",
        ".dashboard-cabinet-map-floor {",
        ".dashboard-cabinet-map-cells {",
    ):
        assert selector in html
        block = html.split(selector, 1)[1].split("}", 1)[0]
        assert "min-width: 0;" in block
    map_block = html.split(".dashboard-cabinet-map {", 1)[1].split("}", 1)[0]
    assert "max-width: 100%;" in map_block
    assert "overflow-x: auto;" in map_block
    panel_block = html.split(".dashboard-slot-grid-panel {", 1)[1].split("}", 1)[0]
    assert "overflow-x: hidden;" in panel_block
    board_block = html.split(".dashboard-cabinet-board {", 1)[1].split("}", 1)[0]
    assert "max-width: 100%;" in board_block
    assert "overflow: hidden;" in board_block
    panel_shell_block = html.split(".dashboard-panel {", 1)[1].split("}", 1)[0]
    assert "min-width: 0;" in panel_shell_block
    assert "max-width: 100%;" in panel_shell_block
    assert "overflow: hidden;" in panel_shell_block
    floor_block = html.split(".dashboard-cabinet-map-floor {", 1)[1].split("}", 1)[0]
    assert "grid-template-columns: 42px minmax(0, 1fr);" in floor_block
    cells_block = html.split(".dashboard-cabinet-map-cells {", 1)[1].split("}", 1)[0]
    assert "grid-template-columns: repeat(var(--cell-count, 1), minmax(0, 1fr));" in cells_block
    assert "justify-content: start;" in cells_block
    assert "gap: 5px;" in cells_block
    assert "width: 100%;" in cells_block
    assert "max-width: 100%;" in cells_block
    assert "overflow-x: hidden;" in cells_block
    cell_block = html.split(".dashboard-cabinet-map-cell {", 1)[1].split("}", 1)[0]
    assert "min-height: 46px;" in cell_block
    assert "padding: 5px 4px;" in cell_block
    code_block = html.split(".dashboard-cabinet-map-cellcode {", 1)[1].split("}", 1)[0]
    assert "font-size: 0.6rem;" in code_block
    count_block = html.split(".dashboard-cabinet-map-cellcount {", 1)[1].split("}", 1)[0]
    assert "display: inline-flex;" in count_block
    assert "width: fit-content;" in count_block
    assert "padding: 2px 5px;" in count_block
    assert "border: 1px solid var(--tile-count-border, transparent);" in count_block
    assert "background: var(--tile-count-bg, transparent);" in count_block
    assert "color: var(--tile-count-fg, currentColor);" in count_block
    assert "font-size: 0.82rem;" in count_block
    meta_block = html.split(".dashboard-cabinet-map-cellmeta {", 1)[1].split("}", 1)[0]
    assert "font-size: 0.52rem;" in meta_block
    assert "color: inherit;" in meta_block
    assert "white-space: nowrap;" in meta_block
    assert "overflow: hidden;" in meta_block
    assert "text-overflow: ellipsis;" in meta_block


def test_index_storage_mapping_slot_tiles_drill_into_cabinet_detail_before_header_toggle():
    html = read_static_html("index.html")
    start = '    $("homeDashSlotGrid").addEventListener("click", async (e) => {'
    end = '    $("homeDashCabinetFloors").addEventListener("click", async (e) => {'
    assert start in html
    assert end in html
    block = html.split(start, 1)[1].split(end, 1)[0]
    assert 'const slotTile = e.target.closest("[data-dashboard-map-slot-code]");' in block
    assert 'const slotCode = String(slotTile.getAttribute("data-dashboard-map-slot-code") || "").trim();' in block
    assert "const groups = buildDashboardCabinetGroups(homeDashboardBySlot);" in block
    assert ".flatMap((group) => group.rows)" in block
    assert "openDashboardForResolvedSlot(slotRow);" in block
    assert block.index('const slotTile = e.target.closest("[data-dashboard-map-slot-code]");') < block.index('const btn = e.target.closest("[data-dashboard-cabinet-key]");')


def test_index_storage_slot_detail_shows_compact_occupancy_text():
    html = read_static_html("index.html")
    start = "    function renderDashboardSlotItems(slotRow, cabinetGroup = null) {"
    end = "    function renderDashboardCabinetDetail() {"
    assert start in html
    assert end in html
    block = html.split(start, 1)[1].split(end, 1)[0]
    assert "const occupancy = slotRow ? dashboardCabinetOccupancyLabel(slotRow) : null;" in block
    assert "const isUnassignedSlot = String(slotRow?.slot_code || \"\").trim() === \"UNASSIGNED\";" in block
    assert "const occupancyText = occupancy" in block
    assert "const setSlotMeta = (statusText = \"\", includeOccupancy = true) => {" in block
    assert 't("dashboard.cover_flow.meta.occupancy", {' in block
    assert 'setSlotMeta(t("dashboard.cover_flow.state.unslotted_block"), false);' in block
    assert 'setSlotMeta(t("dashboard.cover_flow.state.loading"));' in block
    assert 'setSlotMeta(t("dashboard.cover_flow.state.click_to_load"));' in block
    assert 'setSlotMeta(t("dashboard.cover_flow.state.empty"));' in block
    assert "setSlotMeta(rangeText);" in block


def test_index_storage_mapping_slot_tiles_share_selected_item_move_flow_with_floor_buttons():
    html = read_static_html("index.html")
    start = '    $("homeDashSlotGrid").addEventListener("click", async (e) => {'
    end = '    $("homeDashCabinetFloors").addEventListener("click", async (e) => {'
    assert start in html
    assert end in html
    block = html.split(start, 1)[1].split(end, 1)[0]
    assert 'const selectedWorkbenchItems = getDashboardSelectedWorkbenchRows();' in block
    assert 'const selectionSourceKind = getDashboardSelectionSourceKind();' in block
    assert 'await moveDashboardOwnedItemsToSlot(selectedWorkbenchItems, slotCode, { trigger: "click" });' in block
    assert 'await moveDashboardOwnedItemToSlot(sourceOwnedItemId, slotCode);' in block
    assert 'await openDashboardForResolvedSlot(slotRow);' in block


def test_index_storage_mapping_slot_tiles_require_explicit_move_mode_for_click_move():
    html = read_static_html("index.html")
    start = '    $("homeDashSlotGrid").addEventListener("click", async (e) => {'
    end = '    $("homeDashCabinetFloors").addEventListener("click", async (e) => {'
    assert start in html
    assert end in html
    block = html.split(start, 1)[1].split(end, 1)[0]
    assert "const clickMoveActive = isDashboardClickMoveModeActive();" in block
    assert "if (selectedWorkbenchItems.length && !clickMoveActive) {" in block
    assert "await openDashboardForResolvedSlot(slotRow);" in block
    assert 'await moveDashboardOwnedItemsToSlot(selectedWorkbenchItems, slotCode, { trigger: "click" });' in block


def test_index_storage_floor_buttons_require_explicit_move_mode_for_click_move():
    html = read_static_html("index.html")
    start = '    $("homeDashCabinetFloors").addEventListener("click", async (e) => {'
    end = '    $("homeDashCabinetFloors").addEventListener("dragover", (e) => {'
    assert start in html
    assert end in html
    block = html.split(start, 1)[1].split(end, 1)[0]
    assert "const clickMoveActive = isDashboardClickMoveModeActive();" in block
    assert "if (selectedWorkbenchItems.length && !clickMoveActive) {" in block
    assert "await selectDashboardSlot(slotCode);" in block
    assert 'await moveDashboardOwnedItemsToSlot(selectedWorkbenchItems, slotCode, { trigger: "click" });' in block


def test_index_dashboard_selection_toolbars_include_move_mode_controls():
    html = read_static_html("index.html")
    assert 'id="homeDashSlotMoveModeBtn"' in html
    assert 'id="homeDashSlotMoveCancelBtn"' in html
    assert 'id="homeDashWorkbenchMoveModeBtn"' in html
    assert 'id="homeDashWorkbenchMoveCancelBtn"' in html
    assert 'data-i18n="dashboard.selection.action.start_move"' in html
    assert 'data-i18n="dashboard.selection.action.cancel_move"' in html


def test_index_dashboard_selection_runtime_copy_explains_click_move_guard():
    html = read_static_html("index.html")
    assert '"dashboard.selection.summary.move_guard":' in html
    assert '"dashboard.selection.summary.move_active":' in html
    assert '"dashboard.selection.status.move_mode_started":' in html
    assert '"dashboard.selection.status.move_mode_cancelled":' in html
    assert '? "dashboard.selection.summary.move_active"' in html
    assert ': "dashboard.selection.summary.move_guard"' in html
    assert 't("dashboard.workbench.meta.unslotted_ready")' in html
    assert 't("dashboard.workbench.meta.search_ready")' in html


def test_index_slot_reorder_applies_local_order_before_background_reload():
    html = read_static_html("index.html")
    assert "function applyDashboardSlotLocalOrder(orderedIds) {" in html

    relative_start = "    async function moveDashboardOwnedItemRelative(ownedItemId, targetOwnedItemId, position) {"
    relative_end = "    async function moveDashboardSlotSelectionToEdge(direction) {"
    assert relative_start in html
    assert relative_end in html
    relative_block = html.split(relative_start, 1)[1].split(relative_end, 1)[0]
    assert "applyDashboardSlotLocalOrder(nextOrderedIds);" in relative_block

    edge_start = "    async function moveDashboardSlotSelectionToEdge(direction) {"
    edge_end = "    function renderDashboardSlotItems(slotRow, cabinetGroup = null) {"
    assert edge_start in html
    assert edge_end in html
    edge_block = html.split(edge_start, 1)[1].split(edge_end, 1)[0]
    assert "applyDashboardSlotLocalOrder(nextOrderedIds);" in edge_block


def test_index_slot_clear_button_can_clear_item_selection_or_current_slot_context():
    html = read_static_html("index.html")
    sync_start = "    function syncDashboardSelectionControls() {"
    sync_end = "    function renderDashboardSelectionSummary() {"
    assert sync_start in html
    assert sync_end in html
    sync_block = html.split(sync_start, 1)[1].split(sync_end, 1)[0]
    assert 'const slotClearEnabled = slotSelectedCount > 0 || Boolean(String(homeDashboardSelectedSlotCode || "").trim());' in sync_block
    assert '$("homeDashSlotClearBtn").disabled = !slotClearEnabled;' in sync_block

    click_start = '    $("homeDashSlotClearBtn").addEventListener("click", () => {'
    click_end = '    $("homeDashSlotPagePrevBtn").addEventListener("click", () => {'
    assert click_start in html
    assert click_end in html
    click_block = html.split(click_start, 1)[1].split(click_end, 1)[0]
    assert "if (homeDashboardSlotSelectedIds.size > 0) {" in click_block
    assert "homeDashboardSelectedSlotCode = null;" in click_block
    assert "homeDashboardSlotItems = [];" in click_block
    assert "homeDashboardSlotItemsSlotCode = null;" in click_block
    assert "renderDashboardCabinetDetail();" in click_block


def test_index_selected_item_edit_buttons_look_disabled_when_multi_select_blocks_editing():
    html = read_static_html("index.html")
    disabled_block = html.split(".dashboard-slot-actionbtn:disabled,", 1)[1].split("}", 1)[0]
    assert "opacity:" in disabled_block
    assert "cursor: not-allowed;" in disabled_block
    assert "color:" in disabled_block
    assert "border-color:" in disabled_block
    assert "background:" in disabled_block

    sync_start = "    function syncDashboardSelectionControls() {"
    sync_end = "    function renderDashboardSelectionSummary() {"
    sync_block = html.split(sync_start, 1)[1].split(sync_end, 1)[0]
    assert '$("homeDashSelectedItemEditBtn").disabled = slotSelectedCount !== 1;' in sync_block
    assert '$("homeDashWorkbenchEditBtn").disabled = workbenchSelectedCount !== 1;' in sync_block


def test_dashboard_selected_item_meta_exposes_master_sort_artist_quick_edit_logic():
    html = read_static_html("index.html")
    assert '"dashboard.selection.summary.sort_artist":' in html
    assert 'id="homeDashWorkbenchSortArtistRow"' in html
    assert 'id="homeDashWorkbenchSortArtistName"' in html
    assert 'id="homeDashWorkbenchSortArtistSaveBtn"' in html
    assert 'id="homeDashWorkbenchSortArtistDisplay"' in html
    assert 'id="homeDashWorkbenchSortArtistStatus"' in html
    meta_block = html.split("function renderDashboardSelectedItemMeta() {", 1)[1].split("    function syncDashboardSelectedSortArtistEditor() {", 1)[0]
    assert 'const selectionSourceKind = getDashboardSelectionSourceKind();' in meta_block
    assert 'if (selectionSourceKind === "SLOT") {' in meta_block
    assert 'const sortArtist = String(row?.master_sort_artist_name || "").trim();' in meta_block
    assert 'sortArtist ? t("dashboard.selection.summary.sort_artist", { value: sortArtist }) : null,' in meta_block
    sync_start = "    function syncDashboardSelectedSortArtistEditor() {"
    sync_end = "    function setDashboardWorkbenchMode(mode) {"
    assert sync_start in html
    block = html.split(sync_start, 1)[1].split(sync_end, 1)[0]
    assert 'const sourceKind = getDashboardSelectionSourceKind();' in block
    assert 'const slotEditor = {' in block
    assert 'const workbenchEditor = {' in block
    assert 'const editors = [slotEditor, workbenchEditor];' in block
    assert 'const isVisible = editor.sourceKinds.includes(sourceKind);' in block
    assert 'const selectedRow = getDashboardSingleSelectedRow();' in block
    assert 'const masterId = Number(selectedRow?.linked_album_master_id || selectedRow?.album_master_id || 0);' in block
    assert 'setStatus(editor.statusId, "ok", "");' in block
    assert 'editor.row.style.display = "none";' in block
    assert 'editor.input.value = String(selectedRow?.master_sort_artist_name || "").trim();' in block
    assert 'const displayArtist = String(selectedRow?.artist_or_brand || selectedRow?.linked_artist_name || selectedRow?.master_artist_or_brand || "-").trim() || "-";' in block
    assert 'editor.displayEl.textContent = t("dashboard.selection.sort_artist.display_artist", { value: displayArtist });' in block
    assert 'editor.saveBtn.disabled = false;' in block


def test_dashboard_selected_item_meta_sort_artist_save_reuses_master_patch_and_rerenders_lists():
    html = read_static_html("index.html")
    helper_start = "    function updateDashboardMasterSortArtistNameLocally(masterId, sortArtistName) {"
    helper_end = "    async function saveDashboardSelectedSortArtistName() {"
    assert helper_start in html
    helper_block = html.split(helper_start, 1)[1].split(helper_end, 1)[0]
    assert "homeDashboardSlotItems," in helper_block
    assert "homeDashboardSlotSelectionSnapshot," in helper_block
    assert "homeDashboardUnassignedItems," in helper_block
    assert "homeDashboardSearchItems," in helper_block
    assert "Number(row?.linked_album_master_id || row?.album_master_id || 0) !== normalizedMasterId" in helper_block
    assert "row.master_sort_artist_name = normalizedSortArtistName;" in helper_block

    save_end = "    async function duplicateHomeRelatedItem(ownedItemId, count = 1) {"
    save_block = html.split(helper_end, 1)[1].split(save_end, 1)[0]
    assert "function getActiveDashboardSelectedSortArtistEditor() {" in html
    assert "function getDashboardSingleSelectedRowBySourceKind(sourceKind) {" in html
    assert 'const selectionSourceKind = getDashboardSelectionSourceKind();' in save_block
    assert 'const selectedRow = getDashboardSingleSelectedRowBySourceKind(selectionSourceKind);' in save_block
    assert 'const activeEditor = getActiveDashboardSelectedSortArtistEditor();' in save_block
    assert 'const masterId = Number(selectedRow?.linked_album_master_id || selectedRow?.album_master_id || 0);' in save_block
    assert 'const sortArtistName = activeEditor?.input?.value.trim() || "";' in save_block
    assert 'const res = await fetch(`/album-masters/${masterId}/sort-artist-name`,' in save_block
    assert 'updateDashboardMasterSortArtistNameLocally(masterId, data.sort_artist_name || null);' in save_block
    assert 'renderDashboardSelectionSummary();' in save_block
    assert 'renderDashboardSlotItems(getDashboardSlotRow(homeDashboardSelectedSlotCode));' in save_block
    assert 'renderDashboardWorkbench();' in save_block
    assert 'setStatus(activeEditor.statusId,' in save_block


def test_dashboard_workbench_sort_artist_save_keeps_workbench_rerender_without_pinned_order():
    html = read_static_html("index.html")
    rows_block = html.split("function getDashboardWorkbenchRows() {", 1)[1].split("function getDashboardWorkbenchSelectedIds()", 1)[0]
    assert "sortDashboardWorkbenchItems(filterDashboardWorkbenchItemsByMedia(homeDashboardSearchItems))" in rows_block
    assert "sortDashboardWorkbenchItems(filterDashboardWorkbenchItemsByMedia(homeDashboardUnassignedItems))" in rows_block
    assert "applyDashboardWorkbenchPinnedOrder" not in rows_block
    assert "homeDashboardWorkbenchPinnedOrderIds" not in html


def test_dashboard_workbench_sort_artist_save_skips_auto_scroll_once():
    html = read_static_html("index.html")
    assert "let homeDashboardWorkbenchSuppressSelectionScrollOnce = false;" in html
    save_block = html.split("    async function saveDashboardSelectedSortArtistName() {", 1)[1].split("    async function duplicateHomeRelatedItem(ownedItemId, count = 1) {", 1)[0]
    assert 'homeDashboardWorkbenchSuppressSelectionScrollOnce = selectionSourceKind === "UNASSIGNED" || selectionSourceKind === "SEARCH";' in save_block
    render_unassigned_block = html.split("    function renderDashboardUnassignedItems() {", 1)[1].split("    function renderDashboardWorkbench() {", 1)[0]
    assert 'const skipSelectionScroll = homeDashboardWorkbenchSuppressSelectionScrollOnce;' in render_unassigned_block
    assert 'homeDashboardWorkbenchSuppressSelectionScrollOnce = false;' in render_unassigned_block
    assert 'if (!skipSelectionScroll) {' in render_unassigned_block
    render_search_block = html.split("    function renderDashboardWorkbench() {", 1)[1].split("    async function loadDashboardUnassignedItems(opts = {}) {", 1)[0]
    assert 'const skipSelectionScroll = homeDashboardWorkbenchSuppressSelectionScrollOnce;' in render_search_block
    assert 'homeDashboardWorkbenchSuppressSelectionScrollOnce = false;' in render_search_block
    assert 'if (!skipSelectionScroll) {' in render_search_block


def test_index_ops_home_header_moves_page_help_to_operator_panel_header():
    html = read_static_html("index.html")
    hero_start = 'id="opsHomeHero" class="ops-home-hero" style="display:none;"'
    tab_home_start = '\n    <div id="tabHome" class="tab-panel active">'
    assert hero_start in html
    assert tab_home_start in html
    block = html.split(hero_start, 1)[1].split(tab_home_start, 1)[0]
    assert 'data-page-help-source="ops-home"' in block
    assert 'id="shellTabs"' in block
    assert 'id="opsUtilityMount"' in block
    assert 'class="ops-home-hero-side"' in block
    assert 'class="shell-header-row ops-home-shell-row"' in block
    assert block.index('class="ops-home-hero-side"') < block.index('class="shell-header-row ops-home-shell-row"')
    assert block.index('id="opsUtilityMount"') < block.index('class="shell-header-row ops-home-shell-row"')
    operator_panel_block = html.split('<section class="card operator-home-card">', 1)[1].split('<div id="operatorLookupStatus" class="status"></div>', 1)[0]
    assert 'data-page-help-open="ops-home"' in operator_panel_block
    assert 'operator-home-head-actions' in operator_panel_block


def test_index_ops_home_places_utility_mount_in_top_right_hero_side():
    html = read_static_html("index.html")
    hero_start = '    <section id="opsHomeHero" class="ops-home-hero" style="display:none;">'
    utility_start = '    <div id="shellUtilityBar" class="shell-utility" style="display:none;">'
    assert hero_start in html
    assert utility_start in html
    block = html.split(hero_start, 1)[1].split(utility_start, 1)[0]
    side_block = block.split('<div class="ops-home-hero-side">', 1)[1].split('</div>\n      </div>\n      <details class="manual-block page-help-source" data-page-help-source="ops-home" hidden>', 1)[0]
    assert 'id="opsUtilityMount"' in side_block
    assert 'class="ops-home-hero-art"' in side_block
    assert side_block.index('id="opsUtilityMount"') < side_block.index('class="ops-home-hero-art"')
    row_block = block.split('<div class="shell-header-row ops-home-shell-row">', 1)[1].split('</div>\n    </section>', 1)[0]
    assert 'id="opsUtilityMainMount"' in row_block


def test_index_ops_home_header_precedes_dashboard_and_operator_tab_panels():
    html = read_static_html("index.html")
    assert 'id="opsHomeHero"' in html
    assert '<div id="tabHome" class="tab-panel active">' in html
    assert '<div id="tabSimple" class="tab-panel">' in html
    assert html.index('id="opsHomeHero"') < html.index('<div id="tabHome" class="tab-panel active">')
    assert html.index('id="opsHomeHero"') < html.index('<div id="tabSimple" class="tab-panel">')


def test_index_dashboard_slot_focus_centers_cover_flow_in_viewport():
    html = read_static_html("index.html")
    assert 'function focusDashboardTargetSlot(slotCode, opts = {}) {' in html
    function_block = html.split('function focusDashboardTargetSlot(slotCode, opts = {}) {', 1)[1].split('\n    }\n\n', 1)[0]
    assert 'const slotItemsRoot = $("homeDashSlotItems");' in function_block
    assert 'const targetRoot = slotItemsRoot || detailRoot;' in function_block
    assert 'const targetRect = targetRoot.getBoundingClientRect();' in function_block
    assert 'window.scrollTo({ top: Math.max(targetTop - viewportOffset, 0), behavior: smooth ? "smooth" : "auto" });' in function_block
    assert 'floorsRoot.scrollIntoView' not in function_block
    assert 'focusDashboardTargetSlot(slotRow.slot_code, { block: "center" });' in html


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
    assert 'data-operator-context-open-cabinet="${ownedItemId}"' in html
    assert 'data-operator-slot-code="${escapeHtml(String(topCandidate?.current_slot_code || "").trim())}"' in html
    assert 'data-operator-slot-code="${escapeHtml(String(row.current_slot_code || "").trim())}"' in html
    assert 'await openCabinetLocationAction(0, slotCode, cabinetName, columnCode, cellCode);' in html
    assert "async function openOperatorCabinetLocationFromButton(button) {" in html
    handler_start = "async function handleOperatorLookupAction(e) {"
    handler_end = "    async function loadOperatorLookupResults() {"
    assert handler_start in html
    assert handler_end in html
    block = html.split(handler_start, 1)[1].split(handler_end, 1)[0]
    cabinet_action = 'const cabinetBtn = e.target.closest("[data-operator-open-cabinet]");'
    context_cabinet_action = 'const contextCabinetBtn = e.target.closest("[data-operator-context-open-cabinet]");'
    helper_call = "await openOperatorCabinetLocationFromButton(cabinetBtn);"
    readonly_guard = 'if (isShellReadOnly()) return;'
    assert cabinet_action in block
    assert context_cabinet_action in block
    assert helper_call in block
    assert readonly_guard in block
    assert block.index(cabinet_action) < block.index(readonly_guard)
    assert "await openOperatorCabinetLocationFromButton(contextCabinetBtn);" in block
    assert '$("operatorHelperSummary").addEventListener("click", handleOperatorLookupAction);' in html


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


def test_index_operator_open_cabinet_prefers_exact_slot_selection_in_ops_shell():
    html = read_static_html("index.html")
    func_start = "async function openCabinetLocationAction(slotId, slotCode, cabinetName, columnCode, cellCode) {"
    func_end = "    async function openDashboardForCurrentLocation() {"
    assert func_start in html
    assert func_end in html
    block = html.split(func_start, 1)[1].split(func_end, 1)[0]
    assert 'const directSelection = findCabinetSelectionFromSlot(slotId, slotCode);' in block
    assert 'let selection = directSelection || normalizeCabinetRouteSelection(cabinetName, columnCode, cellCode);' in block
    assert 'const directRow = hasSlotRef ? (' in block
    assert 'await openDashboardForResolvedSlot(directRow, {' in block
    assert 'selection = selection || findCabinetSelectionFromSlot(slotId, slotCode);' not in block


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


def test_index_operator_lookup_discards_stale_responses_after_reset_or_new_search():
    html = read_static_html("index.html")
    assert "let operatorLookupRequestSeq = 0;" in html
    load_start = "    async function loadOperatorLookupResults() {"
    render_start = "    function renderOperatorLookupResults() {"
    assert load_start in html
    assert render_start in html
    block = html.split(load_start, 1)[1].split(render_start, 1)[0]
    assert "const requestSeq = ++operatorLookupRequestSeq;" in block
    assert block.count("if (requestSeq !== operatorLookupRequestSeq) return;") >= 2


def test_index_operator_lookup_reset_invalidates_inflight_request_before_clearing():
    html = read_static_html("index.html")
    reset_start = '$("operatorLookupResetBtn").addEventListener("click", async () => {'
    keydown_start = '    $("operatorLookupQuery").addEventListener("keydown", (e) => {'
    assert reset_start in html
    assert keydown_start in html
    block = html.split(reset_start, 1)[1].split(keydown_start, 1)[0]
    assert "operatorLookupRequestSeq += 1;" in block
    assert '$("operatorLookupQuery").value = "";' in block
    assert 'loadOperatorHomeFeed({ kind: operatorFeedKindFromSortMode("CREATED_DESC"), page: 1 });' in block
    assert 'setStatus("operatorLookupStatus", "", "");' in block


def test_index_operator_feed_kind_follows_sort_mode_without_legacy_toggle_buttons():
    html = read_static_html("index.html")
    helper_start = "    function operatorFeedKindFromSortMode(sortMode) {"
    helper_end = "    function operatorFeedKindBaseLabel(kind) {"
    assert helper_start in html
    assert helper_end in html
    helper_block = html.split(helper_start, 1)[1].split(helper_end, 1)[0]
    assert 'return normalizedSortMode === "MOVED_DESC" ? "moved" : "registered";' in helper_block
    assert '$("operatorFeedRegisteredBtn").addEventListener("click"' not in html
    assert '$("operatorFeedMovedBtn").addEventListener("click"' not in html


def test_index_operator_helper_summary_prioritizes_exact_matches_before_assigned_or_first():
    html = read_static_html("index.html")
    summarize_start = "    function summarizeOperatorResults(results, normalizedQuery) {"
    build_start = "    function buildOperatorLookupSummary(results, normalizedQuery, status = \"\") {"
    assert summarize_start in html
    assert build_start in html
    block = html.split(summarize_start, 1)[1].split(build_start, 1)[0]
    assert "const exactBarcode = normalizedDigits" in block
    assert "const exactLabel = list.find(" in block
    assert "const exactTitleArtist = list.find((row) => exactTitleArtistMatch(row, normalizedQuery));" in block
    assert "const assigned = list.find((row) => hasOperatorCurrentLocation(row));" in block
    assert "const topCandidate = exactBarcode || exactLabel || exactTitleArtist || assigned || list[0] || null;" in block
    assert 'if (reason === "barcode") return t("operator.helper.reason.barcode");' in html
    assert 'if (reason === "label") return t("operator.helper.reason.label");' in html
    assert 'if (reason === "titleArtist") return t("operator.helper.reason.title_artist");' in html
    assert 'if (reason === "assigned") return t("operator.helper.reason.assigned");' in html


def test_index_operator_helper_hides_cabinet_cta_for_unassigned_items():
    html = read_static_html("index.html")
    render_start = "    function renderOperatorHelperSummary() {"
    load_start = "    async function loadOperatorLookupResults() {"
    assert render_start in html
    assert load_start in html
    block = html.split(render_start, 1)[1].split(load_start, 1)[0]
    assert 'const canOpenCabinet = Boolean(topCandidate && currentCabinetName && currentColumnCode && currentCellCode);' in block
    assert 'data-operator-open-cabinet="${ownedItemId}"' in block
    assert 't("operator.helper.state.no_current_location")' in block
    assert 't("operator.helper.state.keep_results")' in block


def test_index_dashboard_keeps_source_summary_in_hero_and_removes_bottom_panels():
    html = read_static_html("index.html")
    assert "<h3>미디어 / 상태</h3>" not in html
    assert "<h3>도메인 / 타입 / 규격</h3>" not in html
    assert 'id="homeDashByCategory"' not in html
    assert 'id="homeDashByStatus"' not in html
    assert 'id="homeDashByDomain"' not in html
    assert 'id="homeDashByReleaseType"' not in html
    assert 'id="homeDashBySizeGroup"' not in html
    assert "<h3>확보 소스</h3>" not in html
    assert "<h3>최근 이동</h3>" not in html
    assert 'id="homeDashBySource"' not in html
    assert 'id="homeDashRecentMoves"' not in html
    assert 'id="homeDashMoveWindow"' not in html
    assert 'id="homeDashSourceSummary"' in html


def test_index_dashboard_recent_move_uses_inline_hint_instead_of_move_icon():
    html = read_static_html("index.html")
    assert "function dashboardRecentMoveInlineHtml(row, extraClass = \"\")" in html
    assert 'dashboard-slot-flag-icon--recent-move' not in html
    assert '">이동</span>' not in html
    assert 'dashboardRecentMoveInlineHtml(row, "dashboard-slot-covercard-recentmove")' in html
    assert 'dashboardRecentMoveInlineHtml(row, "dashboard-slot-listitem-recentmove")' in html
    assert 'dashboardRecentMoveInlineHtml(row, "dashboard-slot-shelfrecentmove")' in html


def test_index_operator_home_removes_request_sections_and_bootstrap_calls():
    html = read_static_html("index.html")
    assert "<strong>요청곡 등록" not in html
    assert "<strong>최근 요청곡</strong>" not in html
    assert 'id="operatorRequestComposerCard"' not in html
    assert 'id="operatorRequestHistoryCard"' not in html
    assert '$("operatorRequestCreateBtn").addEventListener("click", createOperatorRequest);' not in html
    assert '$("operatorRequestRefreshBtn").addEventListener("click", loadOperatorRequestList);' not in html
    assert '$("operatorRequestList").addEventListener("click", async (e) => {' not in html
    bootstrap_start = "    renderOpsExceptionSummary();"
    bootstrap_end = "    renderPurchaseImportPreview([]);"
    assert bootstrap_start in html
    assert bootstrap_end in html
    bootstrap_block = html.split(bootstrap_start, 1)[1].split(bootstrap_end, 1)[0]
    assert "clearOperatorRequestForm();" not in bootstrap_block
    assert "renderOperatorRequestList();" not in bootstrap_block
    assert "loadOperatorRequestList();" not in bootstrap_block


def test_index_bootstrap_no_longer_calls_admin_fetches_before_auth_load():
    html = read_static_html("index.html")
    bootstrap_start = "    const initialShellMode = shellModeFromPath();"
    bootstrap_end = '    window.addEventListener("popstate", () => {'
    assert bootstrap_start in html
    assert bootstrap_end in html
    bootstrap_block = html.split(bootstrap_start, 1)[1].split(bootstrap_end, 1)[0]
    assert "appShellMode = initialShellMode;" in bootstrap_block
    assert "loadStorageSlots();" in bootstrap_block
    assert "loadAuthSession(initialShellMode);" in bootstrap_block
    assert "loadHomeDashboard();" in bootstrap_block
    assert 'loadOpsCameras({ silent: true });' not in bootstrap_block
    assert "loadReviewQueue();" not in bootstrap_block
    assert "loadAlbumMasterGroups();" not in bootstrap_block
    assert "loadMetadataSyncStatus();" not in bootstrap_block
    assert "loadOpsSystemStatus();" not in bootstrap_block


def test_index_slot_management_removes_overflow_controls():
    html = read_static_html("index.html")
    assert 'id="opsSlotOverflow"' not in html
    assert "오버플로우 슬롯" not in html
    assert '[OVERFLOW]' not in html


def test_dashboard_shelf_and_collectibles_runtime_copy_use_i18n():
    html = read_static_html("index.html")
    assert 'setStatus("homeDashboardStatus", "ok", t("dashboard.status.loading"));' in html
    assert 'const message = errorMessageText(err, t("dashboard.status.load_failed"));' in html
    assert '$("homeSearchCount").textContent = t("common.count.zero_items");' in html
    assert 'if (!res.ok) throw new Error(data.detail || t("media.manage.shelf.status.load_failed"));' in html
    assert 'setStatus("shelfStatus", "ok", t("media.manage.shelf.status.load_done", { count: countWithUnit(shelfItems.length) }));' in html
    assert 'setStatus("albumSearchStatus", "ok", t("media.manage.search.status.loading"));' in html
    assert 'if (!res.ok) throw new Error(data.detail || t("media.manage.search.status.load_failed"));' in html
    assert 'setStatus("albumSearchStatus", "ok", t("media.manage.search.status.loaded", { count: countWithUnit(albumSearchResults.length) }));' in html
    assert 'if (code === "POSTER") return t("collectibles.category.poster");' in html
    assert 'if (code === "ACTIVE") return t("collectibles.item_status.active");' in html
    assert 'container.innerHTML = `<div class=\'mini muted\'>${escapeHtml(t("collectibles.mapping.state.empty"))}</div>`;' in html
    assert 'container.innerHTML = `<div class=\'mini muted\'>${escapeHtml(t("collectibles.mapping.results.empty"))}</div>`;' in html
    assert '>${escapeHtml(t("collectibles.mapping.action.connect"))}</button>' in html
    assert 'count.textContent = countWithUnit(goodsSearchTotalCount);' in html
    assert 'const slotText = String(row.slot_display_name || "").trim() || t("common.unspecified");' in html
    assert 'const domainText = row.domain_code ? dashboardDomainLabel(row.domain_code) : t("common.unspecified");' in html
    assert '<span>${escapeHtml(t("collectibles.search.meta.quantity", { quantity: String(row.quantity || 1) }))}</span>' in html
    assert '<span>${escapeHtml(t("collectibles.search.meta.links", { count: formatCount(linkedCount) }))}</span>' in html


def test_media_manage_runtime_copy_use_i18n():
    html = read_static_html("index.html")
    assert 'setStatus("homeSearchStatus", "err", t("media.manage.search.status.master_not_found"));' in html
    assert 'if (!res.ok) throw new Error(data.detail || t("media.manage.search.status.load_failed"));' in html
    assert 't("media.manage.location.meta.position", { slot: slotLabel })' in html
    assert 't("media.manage.location.meta.slot_id", { value: row.storage_slot_id ?? "-" })' in html
    assert 't("media.manage.location.meta.order_key", { value: row.order_key || "-" })' in html
    assert 't("media.manage.location.meta.display_rank", { value: row.display_rank ?? "-" })' in html
    assert '? `<span class="tag">${escapeHtml(t("media.manage.location.item.current"))}</span>`' in html
    assert '<button class="btn ghost tiny home-location-open-btn" type="button" data-owned-id="${row.id}">${escapeHtml(t("common.action.open"))}</button>' in html
    assert '<button class="btn ghost tiny home-location-before-btn" type="button" data-target-id="${row.id}">${escapeHtml(t("media.manage.location.action.before"))}</button>' in html
    assert '<button class="btn ghost tiny home-location-after-btn" type="button" data-target-id="${row.id}">${escapeHtml(t("media.manage.location.action.after"))}</button>' in html
    assert 't("media.manage.search.meta.track_count", { count: formatCount(tracks) })' in html
    assert '$("shelfCenterText").textContent = t("media.manage.shelf.center.selected", {' in html
    assert 'setStatus("shelfStatus", "err", t("media.manage.shelf.status.no_adjacent_album"));' in html
    assert 'if (!res.ok) throw new Error(data.detail || t("media.manage.shelf.status.move_failed"));' in html


def test_location_chip_buttons_keep_compact_pill_size():
    html = read_static_html("index.html")
    location_btn_block = html.split(".home-master-location-btn {", 1)[1].split("}", 1)[0]
    location_tiny_override = html.split(".btn.tiny.home-master-location-btn {", 1)[1].split("}", 1)[0]
    assert "min-height: 26px;" in location_btn_block
    assert "padding: 4px 8px;" in location_btn_block
    assert "border-radius: 999px;" in location_btn_block
    assert "min-height: 26px;" in location_tiny_override
    assert "padding: 4px 8px;" in location_tiny_override


def test_restore_exception_and_lower_runtime_copy_use_i18n():
    html = read_static_html("index.html")
    assert '"media.register.master.group.status.loaded":' in html
    assert '"media.manage.track_map.track.table.empty":' in html
    assert '"media.manage.track_map.directory.status.pick_failed":' in html
    assert '"ops.restore.confirm.db":' in html
    assert '"ops.restore.confirm.bundle":' in html
    assert '"ops.exception.field.preset.saved_name":' in html
    assert '"ops.exception.status.master_loaded":' in html
    assert '"media.source.confirm.clear_queue":' in html

    assert 'setStatus("masterGroupStatus", "ok", t("media.register.master.group.status.loaded", { count: countWithUnit(data.length) }));' in html
    assert 't("media.manage.track_map.track.table.empty")' in html
    assert 'throw new Error(data.detail || t("media.manage.track_map.directory.status.pick_failed"))' in html
    assert 'window.confirm(t("ops.restore.confirm.db"))' in html
    assert 'window.confirm(t("ops.restore.confirm.bundle"))' in html
    assert 't("ops.exception.status.preset_applied", { name: String(preset?.name || t("ops.exception.field.preset.saved_name")) })' in html
    assert 'const name = String(rows[idx]?.name || t("ops.exception.field.preset.saved_name"));' in html
    assert 'setStatus("opsExceptionStatus", "ok", t("ops.exception.status.preset_applied", { name: String(preset?.name || t("ops.exception.field.preset.saved_name")) }));' in html
    assert 'loadMasterOwnedRowsFromItems([row], t("ops.exception.status.master_loaded", { name: resolveOwnedAlbumName(row) }));' in html
    assert 'window.confirm(t("media.source.confirm.clear_queue"))' in html
    assert 'applyHomeEditCoverImageUrl(urls[0], t("media.manage.cover.status.url_applied"));' in html
    assert 'setStatus("homeLinkedGoodsStatus", "ok", t("media.manage.collectibles.image.status.urls_applied", { count: urls.length }));' in html


def test_remaining_runtime_copy_uses_i18n_for_dashboard_manage_and_download_flows():
    html = read_static_html("index.html")
    assert '"dashboard.cover_flow.meta.current_range":' in html
    assert '"dashboard.cover_flow.meta.occupancy":' in html
    assert '"media.source.status.master_prep_ready":' in html
    assert '"media.manage.location.status.restore_failed":' in html
    assert '"common.download_failed_status":' in html
    assert '"server.error.auth.invalid_credentials":' in html
    assert '"server.error.purchase.decode_failed":' in html
    assert '"server.error.account.save_failed":' in html
    assert '"server.error.account.update_failed":' in html
    assert '"server.error.account.delete_failed":' in html
    assert '"server.error.camera.invalid_url":' in html
    assert '"server.error.camera.onvif_response":' in html
    assert '"server.error.restore.sqlite_integrity_failed":' in html
    assert '"server.error.restore.not_library_db":' in html
    assert '"server.error.restore.invalid_sqlite":' in html
    assert '"server.error.restore.metadata_sync_running":' in html
    assert '"server.error.restore.invalid_zip":' in html
    assert '"server.error.restore.zip_corrupt":' in html
    assert '"server.error.restore.zip_path_invalid":' in html
    assert '"server.error.restore.zip_missing_db":' in html
    assert '"server.error.restore.db_failed_detail":' in html

    assert 't("common.sort_policy.label_id")' in html
    assert 't("common.sort_policy.artist_release_title")' in html
    assert 't("dashboard.cover_flow.meta.current_range", {' in html
    assert 't("dashboard.cover_flow.meta.all_count", { count: countWithUnit(total) })' in html
    assert 't("dashboard.cover_flow.meta.occupancy", {' in html
    assert 'confirmSlotMismatchMove(targetRow, eligible, t("common.action.move"))' in html
    assert 'confirmSlotMismatchMove(targetRow, [sourceItem], t("common.action.move"))' in html
    assert 'throw new Error(data.detail || t("common.download_failed_status", { status: res.status }))' in html
    assert 'setStatus("masterOwnedStatus", "ok", statusText || t("media.source.status.master_prep_ready", {' in html
    assert 'coverMeta.textContent = labelName === "-" && catalogNo === "-" && !barcode' in html
    assert '? t("media.manage.product.state.no_catalog_meta")' in html
    assert 'imageGalleryButtonHtml(galleryKey, t("common.count.images", { count: formatCount(galleryCount) }))' in html
    assert 'label: String(label || "").trim() || t("common.image"),' in html
    assert 'error: String(result.error || t("media.source.queue.detail.updated_failed")),' in html
    assert '<strong>${countWithUnit(opsExceptionCounts[type] || 0)}</strong>' in html
    assert 'if (text === "아이디 또는 비밀번호가 올바르지 않습니다.") return t("server.error.auth.invalid_credentials");' in html
    assert 'if (text === "계정 저장에 실패했습니다.") return t("server.error.account.save_failed");' in html
    assert 'if (text === "계정 수정에 실패했습니다.") return t("server.error.account.update_failed");' in html
    assert 'if (text === "계정 삭제에 실패했습니다.") return t("server.error.account.delete_failed");' in html
    assert 'if (text === "유효한 ONVIF 장치 URL이 아닙니다.") return t("server.error.camera.invalid_url");' in html
    assert 'if (text === "복구 파일의 SQLite 무결성 검사에 실패했습니다.") return t("server.error.restore.sqlite_integrity_failed");' in html
    assert 'if (text === "복구 파일이 라이브러리 DB 형식이 아닙니다.") return t("server.error.restore.not_library_db");' in html
    assert 'if (text === "복구 파일이 유효한 SQLite DB가 아닙니다.") return t("server.error.restore.invalid_sqlite");' in html
    assert 'if (text === "메타 동기화 실행 중에는 DB 복구를 시작할 수 없습니다.") return t("server.error.restore.metadata_sync_running");' in html
    assert 'if (text === "복구 파일이 유효한 ZIP 백업이 아닙니다.") return t("server.error.restore.invalid_zip");' in html
    assert 'if (text === "복구 ZIP 파일이 손상되었습니다.") return t("server.error.restore.zip_corrupt");' in html
    assert 'if (text === "복구 ZIP 파일 경로가 올바르지 않습니다.") return t("server.error.restore.zip_path_invalid");' in html
    assert 'if (text === "복구 파일에 library.db가 없습니다.") return t("server.error.restore.zip_missing_db");' in html
    assert 'if (text.startsWith("구매 내역 파일 디코딩 실패:")) {' in html
    assert 'return t("server.error.purchase.decode_failed", { message:' in html
    assert 'if (text.startsWith("ONVIF 응답 오류:")) {' in html
    assert 'return t("server.error.camera.onvif_response", { status:' in html
    assert 'if (text.startsWith("DB 복구 실패:")) {' in html
    assert 'return t("server.error.restore.db_failed_detail", { message:' in html
    assert 'if (!res.ok) throw new Error(data.detail || t("media.manage.master.add.failed"));' in html
    assert 'if (!res.ok) throw new Error(data.detail || t("media.manage.location.status.restore_failed"));' in html
    assert 'if (!res.ok) throw new Error(data.detail || t("ops.restore.status.save_failed"));' in html


def test_index_inline_script_parses_without_syntax_error():
    html = read_static_html("index.html")
    scripts = extract_inline_scripts(html)
    assert len(scripts) == 1
    script_path = Path("/tmp/hahahoho_index_inline.js")
    script_path.write_text(scripts[0], encoding="utf-8")
    result = subprocess.run(
        ["node", "--check", str(script_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
