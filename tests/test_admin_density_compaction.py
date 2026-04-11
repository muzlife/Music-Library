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
    assert block.count('class="grid-12"') == 2
    assert 'id="quickItemName"' in block and 'span-4' in block


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
    assert html.count('data-grid="home-product-grid"') == 5
    assert "home-edit-grid-6 home-product-grid" not in html


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
