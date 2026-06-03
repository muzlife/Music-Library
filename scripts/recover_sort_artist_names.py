#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

import httpx


def _resolve_root() -> Path:
    raw = os.getenv("LIBRARY_PROJECT_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


ROOT = _resolve_root()
ENV_PATH = ROOT / ".env.local"
DEFAULT_BASE_URL = "https://__PROD_DOMAIN__"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.sort_artist_recovery import build_sort_artist_restore_plan


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preview or restore album_master.sort_artist_name values from backup.")
    parser.add_argument(
        "--backup-db",
        default=str(ROOT / "data" / "backups" / "library-20260329-103422.db"),
        help="SQLite backup database path used as the recovery source.",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Target API base URL.")
    parser.add_argument("--username", default="", help="Admin username. Defaults to .env.local.")
    parser.add_argument("--password", default="", help="Admin password. Defaults to .env.local.")
    parser.add_argument("--page-size", type=int, default=500, help="Album master page size for API fetch.")
    parser.add_argument(
        "--preview-limit",
        type=int,
        default=20,
        help="Number of planned updates to print in preview output.",
    )
    parser.add_argument("--apply", action="store_true", help="Apply planned updates through the API.")
    return parser.parse_args()


def resolve_credentials(args: argparse.Namespace) -> tuple[str, str]:
    env_values = load_env_file(ENV_PATH)
    username = (
        str(args.username or "").strip()
        or str(env_values.get("LIBRARY_ADMIN_USERNAME") or "").strip()
        or str(env_values.get("LIBRARY_AUTH_USERNAME") or "").strip()
    )
    password = (
        str(args.password or "").strip()
        or str(env_values.get("LIBRARY_ADMIN_PASSWORD") or "").strip()
        or str(env_values.get("LIBRARY_AUTH_PASSWORD") or "").strip()
    )
    if not username or not password:
        raise SystemExit("admin credentials are required via --username/--password or .env.local")
    return username, password


def fetch_backup_rows(backup_db_path: Path) -> list[dict[str, Any]]:
    if not backup_db_path.is_file():
        raise SystemExit(f"backup db not found: {backup_db_path}")
    with sqlite3.connect(str(backup_db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, source_code, source_master_id, title, artist_or_brand, release_year, sort_artist_name
            FROM album_master
            """
        ).fetchall()
    return [dict(row) for row in rows]


def login(client: httpx.Client, *, base_url: str, username: str, password: str) -> None:
    response = client.post(
        f"{base_url.rstrip('/')}/auth/login",
        data={"username": username, "password": password},
    )
    response.raise_for_status()
    session_response = client.get(f"{base_url.rstrip('/')}/auth/session")
    session_response.raise_for_status()
    payload = session_response.json()
    if not payload.get("authenticated"):
        raise SystemExit("login failed: unauthenticated session")


def fetch_current_rows(client: httpx.Client, *, base_url: str, page_size: int) -> list[dict[str, Any]]:
    offset = 0
    rows: list[dict[str, Any]] = []
    while True:
        response = client.get(
            f"{base_url.rstrip('/')}/album-masters",
            params={"limit": page_size, "offset": offset},
        )
        response.raise_for_status()
        page = response.json()
        if not isinstance(page, list) or not page:
            break
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def apply_plan(client: httpx.Client, *, base_url: str, plan: list[dict[str, Any]]) -> int:
    applied = 0
    for row in plan:
        response = client.patch(
            f"{base_url.rstrip('/')}/album-masters/{int(row['album_master_id'])}/sort-artist-name",
            json={"sort_artist_name": row["backup_sort_artist_name"]},
        )
        response.raise_for_status()
        applied += 1
    return applied


def preview(plan: list[dict[str, Any]], *, preview_limit: int) -> None:
    print(
        json.dumps(
            {
                "planned_updates": len(plan),
                "preview": plan[: max(0, int(preview_limit))],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> int:
    args = parse_args()
    username, password = resolve_credentials(args)
    backup_db_path = Path(str(args.backup_db or "")).expanduser().resolve()
    backup_rows = fetch_backup_rows(backup_db_path)

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        login(client, base_url=args.base_url, username=username, password=password)
        current_rows = fetch_current_rows(client, base_url=args.base_url, page_size=max(1, int(args.page_size)))
        plan = build_sort_artist_restore_plan(current_rows=current_rows, backup_rows=backup_rows)
        preview(plan, preview_limit=args.preview_limit)
        if args.apply:
            applied = apply_plan(client, base_url=args.base_url, plan=plan)
            print(json.dumps({"applied_updates": applied}, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
