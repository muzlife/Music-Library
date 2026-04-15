from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = REPO_ROOT / "app" / "static" / "index.html"


def read_index_html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def test_master_merge_workbench_ui_elements_exist():
    html = read_index_html()

    assert 'data-i18n="media.register.master.merge.title"' in html
    assert 'id="masterMergeQuery"' in html
    assert 'id="masterMergeSearchBtn"' in html
    assert 'id="masterMergeClearBtn"' in html
    assert 'id="masterMergeQueueClearBtn"' in html
    assert 'id="masterMergeRunBtn"' in html
    assert 'id="masterMergeStatus"' in html
    assert 'id="masterMergeSummary"' in html
    assert 'id="masterMergeBody"' in html
    assert 'id="masterMergeQueueBody"' in html
    assert 'data-i18n="media.register.master.merge.search_results.title"' in html
    assert 'data-i18n="media.register.master.merge.queue.title"' in html
    assert 'id="masterGroupPanel" hidden style="display:none;"' in html


def test_master_merge_workbench_state_and_functions_exist():
    html = read_index_html()

    assert "let masterMergeSearchResults = [];" in html
    assert "let masterMergeQueueItems = [];" in html
    assert "let masterMergeBaseId = 0;" in html
    assert "function isQueuedMasterMergeId(albumMasterId) {" in html
    assert "function renderMasterMergeRows(items) {" in html
    assert "function renderMasterMergeQueueRows() {" in html
    assert "function appendMasterMergeQueueItems(items, opts = {}) {" in html
    assert "function syncMasterMergeSelectionUi() {" in html
    assert "function selectedMasterMergeIds() {" in html
    assert "function clearInternalAlbumMasterMergeSearch() {" in html
    assert "function clearInternalAlbumMasterMergeQueue() {" in html
    assert "async function searchInternalAlbumMastersForMerge() {" in html
    assert "async function runInternalAlbumMasterMerge() {" in html
    assert 'fetch(`/album-masters?${params.toString()}`)' in html
    assert 'fetch(`/album-masters/${sourceId}/merge`,' in html
    assert "for (const sourceId of mergeIds) {" in html
    assert "if (sourceId === baseId) continue;" in html
    assert "await loadAlbumMasterGroups();" in html


def test_master_merge_workbench_event_bindings_exist():
    html = read_index_html()

    assert '$("masterMergeSearchBtn").addEventListener("click", searchInternalAlbumMastersForMerge);' in html
    assert '$("masterMergeClearBtn").addEventListener("click", clearInternalAlbumMasterMergeSearch);' in html
    assert '$("masterMergeQueueClearBtn").addEventListener("click", clearInternalAlbumMasterMergeQueue);' in html
    assert '$("masterMergeRunBtn").addEventListener("click", runInternalAlbumMasterMerge);' in html
    assert '$("masterMergeQuery").addEventListener("keydown", (e) => {' in html
    assert '$("masterMergeBody").addEventListener("click", (e) => {' in html
    assert 'const addBtn = e.target.closest("[data-master-merge-add-id]");' in html
    assert '$("masterMergeQueueBody").addEventListener("click", (e) => {' in html
    assert 'const removeBtn = e.target.closest("[data-master-merge-remove-id]");' in html
    assert '$("masterMergeQueueBody").addEventListener("change", (e) => {' in html
    assert 'const baseRadio = e.target.closest("[data-master-merge-base-id]");' in html


def test_bind_album_master_uses_merge_queue_representative_before_prompt_fallback():
    html = read_index_html()

    assert "let masterOwnedItems = [];" in html
    assert "function selectedMasterOwnedRows() {" in html
    assert "function promptMasterBindTargetSelection(selectedRows) {" in html
    assert "window.prompt(" in html
    bind_block = html.split("    async function bindAlbumMaster() {", 1)[1].split("    function normalizeMasterMergeId(value) {", 1)[0]
    assert "const selectedRows = selectedMasterOwnedRows();" in bind_block
    assert "const queuedMergeIds = selectedMasterMergeIds();" in bind_block
    assert "if (queuedMergeIds.length) {" in bind_block
    assert 'mergeTarget = { mode: "EXISTING", target_album_master_id: queuedBaseId };' in bind_block
    assert "mergeTarget = promptMasterBindTargetSelection(selectedRows);" in bind_block
    assert "if (!mergeTarget) {" in bind_block
    assert "const boundAlbumMasterId = Number(data.album_master_id || 0);" in bind_block
    assert "const existingMasterIds = Array.from(new Set(" in bind_block
    assert "const queuedMasterIds = selectedMasterMergeIds();" in bind_block
    assert "const targetAlbumMasterId = mergeTarget.mode === \"EXISTING\"" in bind_block
    assert "const mergeSourceIds = new Set(existingMasterIds);" in bind_block
    assert "for (const queuedMasterId of queuedMasterIds) mergeSourceIds.add(queuedMasterId);" in bind_block
    assert "if (boundAlbumMasterId > 0 && boundAlbumMasterId !== targetAlbumMasterId) mergeSourceIds.add(boundAlbumMasterId);" in bind_block
    assert 'const mergeRes = await fetch(`/album-masters/${sourceId}/merge`,' in bind_block
