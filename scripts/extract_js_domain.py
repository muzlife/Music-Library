"""
General-purpose extractor: finds top-level function/const/let blocks in app.js by name
and cuts them into a domain file.

Usage:
    python3 scripts/extract_js_domain.py <domain_file> <func_name_1> <func_name_2> ...

The script:
1. Reads app/static/js/app.js
2. Locates each named declaration (function, const, let)
3. Finds the end of each block via brace-depth tracking
4. Writes extracted blocks to app/static/js/<domain_file>
5. Removes extracted blocks from app.js (replace with empty)
6. Reports line counts before/after

Example:
    python3 scripts/extract_js_domain.py util.js escapeHtml t interpolateI18nMessage
"""

import sys
import re
from pathlib import Path

APP_JS = Path("app/static/js/app.js")
STATIC_JS = Path("app/static/js")


def find_block_end(lines, start_idx):
    """Return the index of the last line of the top-level block starting at start_idx."""
    depth = 0
    for i, line in enumerate(lines[start_idx:], start=start_idx):
        opens = line.count("{")
        closes = line.count("}")
        depth += opens - closes
        # Single-line balanced block: function foo() { return 1; }
        if i == start_idx and opens > 0 and depth == 0:
            return i
        # Multi-line block: return when depth comes back to 0
        if i > start_idx and depth <= 0:
            return i
    return len(lines) - 1


def find_declaration(lines, name):
    """Find the start line of a top-level function/const/let declaration by name."""
    open_paren_or_brace = r"[({]"
    patterns = [
        re.compile(rf'^\s+function {re.escape(name)}\s*' + open_paren_or_brace),
        re.compile(rf'^\s+async function {re.escape(name)}\s*' + open_paren_or_brace),
        re.compile(rf'^\s+const {re.escape(name)}\s*='),
        re.compile(rf'^\s+let {re.escape(name)}\s*='),
        re.compile(rf'^\s+var {re.escape(name)}\s*='),
        re.compile(rf'^function {re.escape(name)}\s*' + open_paren_or_brace),
        re.compile(rf'^async function {re.escape(name)}\s*' + open_paren_or_brace),
        re.compile(rf'^const {re.escape(name)}\s*='),
        re.compile(rf'^let {re.escape(name)}\s*='),
        re.compile(rf'^var {re.escape(name)}\s*='),
    ]
    for i, line in enumerate(lines):
        for pat in patterns:
            if pat.match(line):
                return i
    return None


def extract_functions(domain_filename, func_names):
    src = APP_JS.read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)
    original_count = len(lines)

    extracted_blocks = []  # list of (start, end, lines)
    not_found = []

    for name in func_names:
        start = find_declaration(lines, name)
        if start is None:
            not_found.append(name)
            continue

        # Check if this is a simple single-line const/let (no braces needed)
        line = lines[start]
        if (line.rstrip().endswith(";") or
                (re.search(r'const|let', line) and "{" not in line)):
            end = start
        else:
            end = find_block_end(lines, start)

        # Include any blank line BEFORE the block as part of the block
        block_start = start
        if start > 0 and lines[start - 1].strip() == "":
            block_start = start - 1

        extracted_blocks.append((block_start, end, lines[block_start:end + 1]))
        print(f"  found: {name} → lines {block_start + 1}–{end + 1} ({end - block_start + 1} lines)")

    if not_found:
        print(f"  NOT FOUND: {not_found}")

    if not extracted_blocks:
        print("Nothing to extract.")
        return

    # Sort by line number so we can remove from bottom up (preserve indices)
    extracted_blocks.sort(key=lambda x: x[0])

    # Collect extracted content in original order
    domain_content_parts = []
    for _, _, block_lines in extracted_blocks:
        domain_content_parts.extend(block_lines)

    # Remove from app.js (process in reverse to preserve indices)
    for start, end, _ in reversed(extracted_blocks):
        del lines[start:end + 1]

    # Write domain file
    out_path = STATIC_JS / domain_filename
    existing = out_path.read_text(encoding="utf-8") if out_path.exists() else ""
    if existing:
        out_path.write_text(existing.rstrip() + "\n\n" + "".join(domain_content_parts), encoding="utf-8")
    else:
        out_path.write_text("".join(domain_content_parts), encoding="utf-8")

    # Write updated app.js
    APP_JS.write_text("".join(lines), encoding="utf-8")

    new_count = len(lines)
    extracted_total = sum(end - start + 1 for start, end, _ in extracted_blocks)
    print(f"\napp.js: {original_count} → {new_count} lines (removed {extracted_total})")
    print(f"{domain_filename}: {len(out_path.read_text().splitlines())} lines")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 scripts/extract_js_domain.py <domain_file> <func1> [func2 ...]")
        sys.exit(1)
    domain_file = sys.argv[1]
    names = sys.argv[2:]
    print(f"Extracting {len(names)} declarations → {domain_file}")
    extract_functions(domain_file, names)
