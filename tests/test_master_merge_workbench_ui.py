from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = REPO_ROOT / "app" / "static" / "index.html"


def read_index_html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def test_registered_master_merge_ui_elements_exist():
    html = read_index_html()

    assert 'id="registerMasterLegacyCard" class="card" style="margin-top:14px;display:none;" hidden' in html
    assert 'id="registeredMasterMergeQuery"' in html
    assert 'id="registeredMasterMergeSearchBtn"' in html
    assert 'id="registeredMasterMergeClearBtn"' in html
    assert 'id="registeredMasterMergeStatus"' in html
    assert 'id="registeredMasterMergeBody"' in html
    assert 'id="registeredMasterMergeRepresentativeSummary"' in html
    assert 'id="registeredMasterMergeTargetSummary"' in html
    assert 'id="registeredMasterMergeTargetBody"' in html
    assert 'id="registeredMasterMergeRunBtn"' in html
    assert 'id="registeredMasterMergeHistorySummary"' in html
    assert 'id="registeredMasterMergeHistoryBody"' in html
    assert 'class="result-list registered-master-merge-list"' in html
    assert 'data-i18n="media.register.master.workflow.title"' in html
    assert 'data-i18n="media.register.master.workflow.search_results.title"' in html
    assert 'data-i18n="media.register.master.workflow.representative.title"' in html
    assert 'data-i18n="media.register.master.workflow.targets.title"' in html
    assert 'data-i18n="media.register.master.workflow.history.title"' in html
    assert 'media.register.master.workflow.confirm.run' in html
    assert 'media.register.master.workflow.status.cancelled' in html


def test_registered_master_merge_console_shell_roots_exist():
    html = read_index_html()

    assert 'id="registeredMasterMergeCard" class="card registered-master-merge-console"' in html
    assert 'class="registered-master-merge-console-shell"' in html


def test_registered_master_merge_console_regions_exist():
    html = read_index_html()

    assert 'class="registered-master-merge-commandbar"' in html
    assert 'class="registered-master-merge-console-grid"' in html
    assert 'class="registered-master-merge-results-panel"' in html
    assert 'class="registered-master-merge-workspace-panel"' in html
    assert 'class="registered-master-merge-log-panel"' in html


def test_registered_master_merge_state_and_functions_exist():
    html = read_index_html()

    assert "let registeredMasterMergeSearchResults = [];" in html
    assert "let registeredMasterMergeTargetItems = [];" in html
    assert "let registeredMasterMergeRepresentativeItem = null;" in html
    assert "let registeredMasterMergeHasSearched = false;" in html
    assert "let registeredMasterMergeHistoryItems = [];" in html
    assert "function normalizeRegisteredMasterMergeId(value) {" in html
    assert "function registeredMasterMergeTargetIds() {" in html
    assert "function isRegisteredMasterMergeTargetId(albumMasterId) {" in html
    assert "function registeredMasterMergeRepresentativeId() {" in html
    assert "function isRegisteredMasterMergeRepresentativeId(albumMasterId) {" in html
    assert "function registeredMasterMergeCardHtml(row, options = {}) {" in html
    assert "function registeredMasterMergeRowHtml(row) {" in html
    assert "function renderRegisteredMasterMergeRows(items) {" in html
    assert "function renderRegisteredMasterMergeRepresentative() {" in html
    assert "function renderRegisteredMasterMergeTargets() {" in html
    assert "function renderRegisteredMasterMergeHistory() {" in html
    assert "function syncRegisteredMasterMergeUi() {" in html
    assert "function addRegisteredMasterMergeTarget(row) {" in html
    assert "function setRegisteredMasterMergeRepresentative(row) {" in html
    assert "function removeRegisteredMasterMergeTarget(albumMasterId) {" in html
    assert "function clearRegisteredMasterMergeRepresentative() {" in html
    assert "function clearRegisteredMasterMergeSearch() {" in html
    assert "async function searchRegisteredAlbumMastersForMerge() {" in html
    assert "async function loadRegisteredMasterMergeHistory() {" in html
    assert "async function runRegisteredAlbumMasterMerge() {" in html
    assert "async function rollbackLatestRegisteredAlbumMasterMerge() {" in html
    assert 'fetch(`/album-masters?${params.toString()}`)' in html
    assert 'fetch(`/album-masters/${sourceId}/merge`,' in html
    assert 'fetch("/album-masters/merge-history?limit=10")' in html
    assert 'fetch("/album-masters/merge-history/latest/rollback",' in html


def test_registered_master_merge_row_actions_and_order_rules_exist():
    html = read_index_html()

    row_block = html.split("    function registeredMasterMergeRowHtml(row) {", 1)[1].split("    function renderRegisteredMasterMergeRows(items) {", 1)[0]
    assert "const rowId = normalizeRegisteredMasterMergeId(row?.id);" in row_block
    assert "const isTarget = isRegisteredMasterMergeTargetId(rowId);" in row_block
    assert "const isRepresentative = isRegisteredMasterMergeRepresentativeId(rowId);" in row_block
    assert "const representativeLocked = representativeId > 0 && representativeId !== rowId;" in row_block
    assert "const actionsHtml = `" in row_block
    assert 'data-registered-master-merge-add-id="${rowId}"' in row_block
    assert 'data-registered-master-merge-representative-id="${rowId}"' in row_block
    assert 't("media.register.master.workflow.search.action.representative_selected")' in row_block
    assert 't("media.register.master.workflow.search.action.target_added")' in row_block
    assert "return registeredMasterMergeCardHtml(row, { actionsHtml });" in row_block

    card_block = html.split("    function registeredMasterMergeCardHtml(row, options = {}) {", 1)[1].split("    function registeredMasterMergeRowHtml(row) {", 1)[0]
    assert "const coverUrl = normalizeRenderableCoverUrl(row?.cover_image_url);" in card_block
    assert 'class="result-item album-result registered-master-merge-card"' in card_block
    assert 'class="registered-master-merge-actions"' in card_block

    target_ids_block = html.split("    function registeredMasterMergeTargetIds() {", 1)[1].split("    function isRegisteredMasterMergeTargetId(albumMasterId) {", 1)[0]
    assert "return (registeredMasterMergeTargetItems || [])" in target_ids_block
    assert ".sort(" not in target_ids_block

    representative_block = html.split("    function setRegisteredMasterMergeRepresentative(row) {", 1)[1].split("    function removeRegisteredMasterMergeTarget(albumMasterId) {", 1)[0]
    assert "registeredMasterMergeRepresentativeItem = {" in representative_block
    assert "registeredMasterMergeTargetItems = registeredMasterMergeTargetItems.filter(" in representative_block

    render_representative_block = html.split("    function renderRegisteredMasterMergeRepresentative() {", 1)[1].split("    function renderRegisteredMasterMergeTargets() {", 1)[0]
    assert "registeredMasterMergeCardHtml(representative, {" in render_representative_block

    render_targets_block = html.split("    function renderRegisteredMasterMergeTargets() {", 1)[1].split("    function syncRegisteredMasterMergeUi() {", 1)[0]
    assert "registeredMasterMergeCardHtml(row, {" in render_targets_block

    history_block = html.split("    function renderRegisteredMasterMergeHistory() {", 1)[1].split("    function syncRegisteredMasterMergeUi() {", 1)[0]
    assert 'data-registered-master-merge-rollback-id="${entry.id}"' in history_block
    assert 't("media.register.master.workflow.history.action.rollback")' in history_block
    assert 't("media.register.master.workflow.history.meta.by",' in history_block

    run_block = html.split("    async function runRegisteredAlbumMasterMerge() {", 1)[1].split("    function albumMasterGroupRowHtml(row) {", 1)[0]
    assert "const targetIds = registeredMasterMergeTargetIds();" in run_block
    assert "const representativeId = registeredMasterMergeRepresentativeId();" in run_block
    assert "if (!representativeId) {" in run_block
    assert "if (!targetIds.length) {" in run_block
    assert 'const confirmText = t("media.register.master.workflow.confirm.run",' in run_block
    assert "if (!window.confirm(confirmText)) {" in run_block
    assert 'setStatus("registeredMasterMergeStatus", "ok", t("media.register.master.workflow.status.cancelled"));' in run_block
    assert "for (const sourceId of targetIds) {" in run_block
    assert "if (sourceId === representativeId) continue;" in run_block
    assert "await loadRegisteredMasterMergeHistory();" in run_block


def test_registered_master_merge_event_bindings_exist():
    html = read_index_html()

    assert '$("registeredMasterMergeSearchBtn").addEventListener("click", searchRegisteredAlbumMastersForMerge);' in html
    assert '$("registeredMasterMergeClearBtn").addEventListener("click", clearRegisteredMasterMergeSearch);' in html
    assert '$("registeredMasterMergeRunBtn").addEventListener("click", runRegisteredAlbumMasterMerge);' in html
    assert '$("registeredMasterMergeQuery").addEventListener("keydown", (e) => {' in html
    assert '$("registeredMasterMergeBody").addEventListener("click", (e) => {' in html
    assert 'const addBtn = e.target.closest("[data-registered-master-merge-add-id]");' in html
    assert 'const representativeBtn = e.target.closest("[data-registered-master-merge-representative-id]");' in html
    assert '$("registeredMasterMergeRepresentativeBody").addEventListener("click", (e) => {' in html
    assert '$("registeredMasterMergeTargetBody").addEventListener("click", (e) => {' in html
    assert '$("registeredMasterMergeHistoryBody").addEventListener("click", (e) => {' in html
    assert 'const removeBtn = e.target.closest("[data-registered-master-merge-remove-id]");' in html
    assert 'const rollbackBtn = e.target.closest("[data-registered-master-merge-rollback-id]");' in html
