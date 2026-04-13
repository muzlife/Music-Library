from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "app" / "static"


def read_static_html(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


def test_admin_density_overrides_define_compact_tokens():
    html = read_static_html("index.html")
    admin_root_block = html.split('body[data-shell-mode="admin"] {', 1)[1].split("}", 1)[0]
    admin_input_block = html.split(
        'body[data-shell-mode="admin"] input,\n    body[data-shell-mode="admin"] select,\n    body[data-shell-mode="admin"] textarea {',
        1,
    )[1].split("}", 1)[0]
    admin_btn_block = html.split('body[data-shell-mode="admin"] .btn {', 1)[1].split("}", 1)[0]
    admin_non_btn_compact_selectors = [
        "body[data-shell-mode=\"admin\"] .tab-btn",
        "body[data-shell-mode=\"admin\"] .dashboard-slot-viewbtn",
        "body[data-shell-mode=\"admin\"] .page-help-trigger",
    ]
    admin_compact_gap_selectors = [
        "body[data-shell-mode=\"admin\"] .ops-compact-form-grid",
        "body[data-shell-mode=\"admin\"] .ops-compact-form-row",
        "body[data-shell-mode=\"admin\"] .compact-stack",
        "body[data-shell-mode=\"admin\"] .compact-stack-grid",
        "body[data-shell-mode=\"admin\"] .compact-stack-actions",
    ]
    admin_grid_selectors = [
        "body[data-shell-mode=\"admin\"] .grid",
        "body[data-shell-mode=\"admin\"] .grid-3",
        "body[data-shell-mode=\"admin\"] .grid-6",
        "body[data-shell-mode=\"admin\"] .home-edit-grid-6",
        "body[data-shell-mode=\"admin\"] .home-search-grid-top",
        "body[data-shell-mode=\"admin\"] .home-search-grid-bottom",
    ]
    assert 'body[data-shell-mode="admin"] input,' in html
    assert 'body[data-shell-mode="admin"] label' in html
    assert 'body[data-shell-mode="admin"] .btn' in html
    assert 'body[data-shell-mode="admin"] .section-divider' in html
    assert "--compact-control-height: 32px;" in admin_root_block
    assert "--compact-control-pad: 6px 10px;" in admin_root_block
    assert "--compact-label-size: 0.72rem;" in admin_root_block
    assert "--compact-font-size: 0.82rem;" in admin_root_block
    assert "--compact-gap: 6px;" in admin_root_block
    assert "--compact-line-height: 1.25;" in admin_root_block
    assert "min-height: var(--compact-control-height);" in admin_input_block
    assert "padding: var(--compact-control-pad);" in admin_input_block
    assert "font-size: var(--compact-font-size);" in admin_input_block
    assert "line-height: var(--compact-line-height);" in admin_input_block
    assert "min-height: var(--compact-control-height);" in admin_btn_block
    assert "padding: var(--compact-control-pad);" in admin_btn_block
    assert "font-size: var(--compact-font-size);" in admin_btn_block
    assert "line-height: var(--compact-line-height);" in admin_btn_block
    for selector in admin_non_btn_compact_selectors:
        non_btn_block = html.split(f'{selector} {{', 1)[1].split("}", 1)[0]
        assert "min-height: var(--compact-control-height);" in non_btn_block
        assert "padding: var(--compact-control-pad);" in non_btn_block
        assert "font-size: var(--compact-font-size);" in non_btn_block
        assert "line-height: var(--compact-line-height);" in non_btn_block
    for selector in admin_grid_selectors:
        selector_token = f"{selector},"
        if selector_token not in html:
            selector_token = f"{selector} {{"
        assert selector_token in html
        selector_block = html.split(selector_token, 1)[1].split("}", 1)[0]
        assert "gap: var(--compact-gap);" in selector_block
    for selector in admin_compact_gap_selectors:
        selector_token = f"{selector},"
        if selector_token not in html:
            selector_token = f"{selector} {{"
        assert selector_token in html
        selector_block = html.split(selector_token, 1)[1].split("}", 1)[0]
        assert "gap: var(--compact-gap);" in selector_block


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
    linked_goods = html.split('id="homeLinkedGoodsPanel"', 1)[1].split('id="homeManageMasterSection"', 1)[0]
    assert "body[data-shell-mode=\"admin\"] .compact-stack-actions" in html
    compact_action_input_block = html.split(
        'body[data-shell-mode="admin"] .compact-stack-actions input:not([type="checkbox"]):not([type="radio"]):not([type="file"]):not([type="hidden"]),',
        1,
    )[1].split("}", 1)[0]
    compact_action_button_block = html.split(
        'body[data-shell-mode="admin"] .compact-stack-actions button,',
        1,
    )[1].split("}", 1)[0]
    compact_equal_block = html.split(
        "body[data-shell-mode=\"admin\"] .compact-stack-actions--equal",
        1,
    )[1].split("}", 1)[0]
    assert "--compact-control-height" in html
    assert "body[data-shell-mode=\"admin\"] .compact-stack-actions input:not([type=\"checkbox\"]):not([type=\"radio\"]):not([type=\"file\"]):not([type=\"hidden\"])" in html
    assert "body[data-shell-mode=\"admin\"] .compact-stack-actions select" in html
    assert "body[data-shell-mode=\"admin\"] .compact-stack-actions button" in html
    assert "body[data-shell-mode=\"admin\"] .compact-stack-actions .btn" in html
    assert "body[data-shell-mode=\"admin\"] .compact-stack-actions .btn.tiny" in html
    assert "body[data-shell-mode=\"admin\"] .compact-stack-actions .compact-line" in html
    assert "min-height: var(--compact-control-height);" in compact_action_input_block
    assert "min-height: var(--compact-control-height);" in compact_action_button_block
    assert 'class="compact-stack-actions compact-stack-actions--equal"' in linked_goods
    assert "body[data-shell-mode=\"admin\"] .compact-stack-actions--equal" in html
    assert "body[data-shell-mode=\"admin\"] .compact-stack-actions--equal > *" in html
    assert "body[data-shell-mode=\"admin\"] .compact-stack-actions--equal button" in html
    assert "body[data-shell-mode=\"admin\"] .compact-stack-actions--equal .btn" in html
    equal_block = compact_equal_block
    equal_child_block = html.split("body[data-shell-mode=\"admin\"] .compact-stack-actions--equal > *", 1)[1].split("}", 1)[0]
    equal_button_block = html.split("body[data-shell-mode=\"admin\"] .compact-stack-actions--equal button", 1)[1].split("}", 1)[0]
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in equal_block
    assert "gap: var(--compact-gap);" in equal_block
    assert "min-width: 0;" in equal_child_block
    assert "width: 100%;" in equal_button_block
    block_760 = html.split("@media (max-width: 760px)", 1)[1].split("@media", 1)[0]
    assert "body[data-shell-mode=\"admin\"] .compact-stack-actions--equal { grid-template-columns: 1fr; }" in block_760
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


def test_collectibles_search_action_width_rules():
    html = read_static_html("index.html")
    assert "grid-template-columns: repeat(6, minmax(110px, 1fr)) minmax(200px, 1.35fr);" in html
    action_block = html.split(".goods-search-actions > .btn", 1)[1].split("}", 1)[0]
    assert "flex: 1;" in action_block
    assert "min-width: 110px;" in action_block


def test_admin_left_sidebar_nav_structure():
    html = read_static_html("index.html")
    assert 'id="adminSideNav"' in html
    assert 'data-admin-nav="home"' in html
    assert 'data-admin-nav="media"' in html
    assert 'data-admin-nav="collectibles"' in html
    assert 'data-admin-nav="ops"' in html
    assert 'data-admin-subnav="media:search"' in html
    assert 'data-admin-subnav="media:manage"' in html
    assert 'data-admin-subnav="media:register"' in html
    assert 'data-admin-subnav="media:source"' in html
    assert 'data-admin-subnav="collectibles:search"' in html
    assert 'data-admin-subnav="collectibles:manage"' in html
    assert 'data-admin-subnav="collectibles:register"' in html
    assert 'data-admin-subnav="ops:system"' in html


def test_admin_body_menus_hidden_in_admin_mode():
    html = read_static_html("index.html")
    assert 'body[data-shell-mode="admin"] .goods-mode-tabs' in html
    assert 'body[data-shell-mode="admin"] .subtabs' in html
    assert "display: none" in html


def test_ops_system_docs_block_present():
    html = read_static_html("index.html")
    block = html.split('id="tabOps"', 1)[1].split('id="opsSystemStatusSummary"', 1)[0]
    assert 'id="opsDocsBlock"' in block
    assert 'data-i18n="shell.admin.docs_summary"' in block
    assert 'data-tool-doc-key="erd-summary"' in block
    assert 'data-tool-doc-key="erd-detail"' in block
    assert 'data-tool-doc-key="manual"' in block
