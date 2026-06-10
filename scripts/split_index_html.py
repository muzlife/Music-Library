"""One-shot script: splits app/static/index.html into css/app.css + js/core.js + js/i18n.ko.js + js/app.js.
Run from repo root with: python3 scripts/split_index_html.py
Requires a clean git state — verify before running."""
from pathlib import Path

p = Path("app/static/index.html")
src = p.read_text(encoding="utf-8")

# 1) Main CSS: first <style> … first </style>
css_start = src.index("<style>") + len("<style>")
css_end = src.index("</style>")
css = src[css_start:css_end]

# 2) Main script: last <script> … last </script>
js_start = src.rindex("<script>") + len("<script>")
js_end = src.rindex("</script>")
js = src[js_start:js_end]

# 3) i18n block inside script: 'const I18N_MESSAGES = {' … '\n    };'
i_start = js.index("const I18N_MESSAGES")
i_end = js.index("\n    };", i_start) + len("\n    };")
core, i18n, app_js = js[:i_start], js[i_start:i_end], js[i_end:]

out = Path("app/static")
(out / "css").mkdir(exist_ok=True)
(out / "js").mkdir(exist_ok=True)
(out / "css/app.css").write_text(css.strip() + "\n", encoding="utf-8")
(out / "js/core.js").write_text(core.strip() + "\n", encoding="utf-8")
(out / "js/i18n.ko.js").write_text(i18n.strip() + "\n", encoding="utf-8")
(out / "js/app.js").write_text(app_js.strip() + "\n", encoding="utf-8")

html = (
    src[: css_start - len("<style>")]
    + '<link rel="stylesheet" href="/ui-static/css/app.css" />'
    + src[css_end + len("</style>") : js_start - len("<script>")]
    + '<script src="/ui-static/js/core.js"></script>\n'
    + '  <script src="/ui-static/js/i18n.ko.js"></script>\n'
    + '  <script src="/ui-static/js/app.js"></script>'
    + src[js_end + len("</script>") :]
)
p.write_text(html, encoding="utf-8")

files = [out / "css/app.css", out / "js/core.js", out / "js/i18n.ko.js", out / "js/app.js"]
print("done:", {f.name: len(f.read_text().splitlines()) for f in files})
print("index.html:", len(p.read_text().splitlines()), "lines")

# Checksum: verify core+i18n+app_js == original js block (modulo strip)
combined = (core.strip() + "\n" + i18n.strip() + "\n" + app_js.strip()).replace("\r\n", "\n")
original = js.strip().replace("\r\n", "\n")
if combined == original:
    print("checksum: OK (concat matches original script block)")
else:
    import hashlib
    print("checksum MISMATCH — diff lengths:", len(combined), "vs", len(original))
    print("  combined md5:", hashlib.md5(combined.encode()).hexdigest())
    print("  original md5:", hashlib.md5(original.encode()).hexdigest())
