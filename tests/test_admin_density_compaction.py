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
