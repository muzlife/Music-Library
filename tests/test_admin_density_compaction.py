from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "app" / "static"


def read_static_html(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


def test_admin_density_overrides_define_compact_tokens():
    html = read_static_html("index.html")
    assert 'body[data-shell-mode="admin"] input,' in html
    assert 'body[data-shell-mode="admin"] label' in html
    assert 'body[data-shell-mode="admin"] .btn' in html
    assert 'body[data-shell-mode="admin"] .section-divider' in html


def test_direct_register_uses_two_grid_rows_for_all_fields():
    html = read_static_html("index.html")
    block = html.split('data-i18n="media.register.direct.title"', 1)[1].split('id="quickSizeGroup"', 1)[0]
    assert 'id="quickRegisterCoreRowA"' in block
    assert 'id="quickRegisterCoreRowB"' in block
    assert "quick-register-compact-row--primary" in block
    assert "quick-register-compact-row--secondary" in block
    assert block.count("quick-register-compact-row--") == 2
    assert 'id="quickItemName"' in block


def test_manage_edit_grids_use_grid12_mapping():
    html = read_static_html("index.html")
    block_1080 = html.split("@media (max-width: 1080px)", 1)[1].split("@media", 1)[0]
    assert ".grid-12--from-6 > * { grid-column: span 2; }" in html
    assert ".grid-12--from-6 .span-2 { grid-column: span 4; }" in html
    assert ".grid-12--from-6 .span-3 { grid-column: span 6; }" in html
    assert ".grid-12--from-6 .span-4 { grid-column: span 8; }" in html
    assert ".grid-12--from-6 .span-5 { grid-column: span 10; }" in html
    assert ".grid-12--from-6 { grid-template-columns: repeat(4, minmax(0, 1fr)); }" in block_1080
    assert ".grid-12--from-6 > * { grid-column: span 1; }" in block_1080
    assert ".grid-12--from-6 .span-2 { grid-column: span 2; }" in block_1080
    assert ".grid-12--from-6 .span-3 { grid-column: span 3; }" in block_1080
    assert ".grid-12--from-6 .span-4 { grid-column: span 4; }" in block_1080
    assert ".grid-12--from-6 .span-5 { grid-column: span 4; }" in block_1080
    assert 'id="homeEditMusicMetaFieldsA" class="grid-12 grid-12--from-6"' in html
    assert 'id="homeEditMusicMetaFieldsB" class="grid-12 grid-12--from-6"' in html
    assert 'id="homeEditMusicMetaFieldsC" class="grid-12 grid-12--from-6"' in html
    assert 'id="homeEditMusicInfoRow" data-grid="home-product-grid" class="grid-12 grid-12--from-6 home-product-grid"' in html
    assert html.count('data-grid="home-product-grid"') == 2
    assert "home-edit-grid-6 home-product-grid" not in html


def test_collector_relation_compact_stack_helpers():
    html = read_static_html("index.html")
    block_1080 = html.split("@media (max-width: 1080px)", 1)[1].split("@media", 1)[0]
    assert ".compact-stack" in html
    assert ".compact-stack-actions" in html
    assert ".compact-stack-grid" in html
    assert ".compact-stack { grid-template-columns: 1fr; }" in block_1080


def test_compact_stack_actions_control_height_rules():
    html = read_static_html("index.html")
    assert "body[data-shell-mode=\"admin\"] .compact-stack-actions" in html
    assert "--compact-control-height" in html
    assert "body[data-shell-mode=\"admin\"] .compact-stack-actions input:not([type=\"checkbox\"])" in html
    assert "body[data-shell-mode=\"admin\"] .compact-stack-actions select" in html
    assert "body[data-shell-mode=\"admin\"] .compact-stack-actions button" in html
    assert "body[data-shell-mode=\"admin\"] .compact-stack-actions .btn" in html
    assert "body[data-shell-mode=\"admin\"] .compact-stack-actions .compact-line" in html
    assert ".compact-stack-actions textarea" not in html
    assert ".compact-stack-actions input[type=\"checkbox\"]" not in html
    assert ".compact-stack-actions input[type=\"radio\"]" not in html
    assert ".compact-stack-actions input[type=\"file\"]" not in html
    assert ".compact-stack-actions input[type=\"hidden\"]" not in html


def test_collector_relation_blocks_use_compact_stack():
    html = read_static_html("index.html")
    goods_section = html.split('id="homeMasterGoodsSection"', 1)[1].split('id="homeLinkedGoodsPanel"', 1)[0]
    linked_section = html.split('id="homeLinkedGoodsPanel"', 1)[1].split('id="homeManageMasterSection"', 1)[0]
    assert "compact-stack" in goods_section
    assert "compact-stack-actions" in goods_section
    assert "compact-stack" in linked_section
    assert "compact-stack-actions" in linked_section


def test_product_relation_blocks_use_compact_stack():
    html = read_static_html("index.html")
    section = html.split("homeProductRelationSection", 1)[1].split("homeEditorActionBlock", 1)[0]
    assert section.count("goods-map-section compact-stack") >= 4
    assert section.count('goods-map-section compact-stack" style="grid-template-columns: 1fr;"') == 2
    assert 'id="homeProductRelationMasterList"' in section
    assert 'id="homeProductRelationSeriesList"' in section
    assert 'id="homeProductRelationReleaseList"' in section
    assert 'id="homeProductRelationComponentList"' in section
    assert 'id="homeProductRelationSaveBtn"' in section
    assert 'id="homeProductRelationStatus"' in section
    assert "compact-stack-grid" in section
    assert "compact-stack-actions" in section
    status_block = section.split('<div class="compact-stack" style="margin-top:6px;">', 1)[1].lstrip()
    assert status_block.startswith('<div id="homeProductRelationStatus" class="status span-2"></div>')
    assert 'class="compact-stack-actions span-2"' in section


def test_search_list_edit_button_has_arrow_indicator():
    html = read_static_html("index.html")
    block = html.split("function homeMasterMemberPreviewHtml(item", 1)[1].split("function getHomeMasterVisiblePreviewItems", 1)[0]
    assert 'data-home-preview-edit' in block
    assert 'class="edit-arrow"' in block
    assert 'aria-expanded' in block


def test_search_list_label_id_chip_is_non_button():
    html = read_static_html("index.html")
    block = html.split("function homeMasterMemberPreviewHtml(item", 1)[1].split("function getHomeMasterVisiblePreviewItems", 1)[0]
    assert '<span class="home-master-member-preview-code">' in block
    assert "home-master-member-preview-code-btn" not in block
    assert '<button class="home-master-member-preview-code"' not in block
