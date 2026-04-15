from __future__ import annotations

from collections import defaultdict
from typing import Any


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split()).casefold()


def _normalize_sort_artist_name(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _normalize_year(value: Any) -> int | None:
    try:
        return int(value) if value is not None and str(value).strip() else None
    except (TypeError, ValueError):
        return None


def _source_key(row: dict[str, Any]) -> tuple[str, str] | None:
    source_code = str(row.get("source_code") or "").strip().upper()
    source_master_id = str(row.get("source_master_id") or "").strip()
    if not source_code or not source_master_id:
        return None
    return source_code, source_master_id


def _title_artist_year_key(row: dict[str, Any]) -> tuple[str, str, int | None]:
    return (
        _normalize_text(row.get("title")),
        _normalize_text(row.get("artist_or_brand")),
        _normalize_year(row.get("release_year")),
    )


def _build_plan_row(
    current_row: dict[str, Any],
    backup_row: dict[str, Any],
    *,
    strategy: str,
) -> dict[str, Any]:
    return {
        "album_master_id": int(current_row["id"]),
        "source_code": str(current_row.get("source_code") or "").strip(),
        "source_master_id": str(current_row.get("source_master_id") or "").strip(),
        "title": current_row.get("title"),
        "artist_or_brand": current_row.get("artist_or_brand"),
        "release_year": _normalize_year(current_row.get("release_year")),
        "current_sort_artist_name": _normalize_sort_artist_name(current_row.get("sort_artist_name")),
        "backup_sort_artist_name": _normalize_sort_artist_name(backup_row.get("sort_artist_name")),
        "strategy": strategy,
        "backup_album_master_id": int(backup_row["id"]),
    }


def build_sort_artist_restore_plan(
    *,
    current_rows: list[dict[str, Any]],
    backup_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    backup_rows_with_sort = [
        row for row in backup_rows if _normalize_sort_artist_name(row.get("sort_artist_name")) is not None
    ]

    backup_by_source_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    backup_by_title_artist_year: dict[tuple[str, str, int | None], list[dict[str, Any]]] = defaultdict(list)
    for backup_row in backup_rows_with_sort:
        source_key = _source_key(backup_row)
        if source_key is not None:
            backup_by_source_key[source_key].append(backup_row)
        backup_by_title_artist_year[_title_artist_year_key(backup_row)].append(backup_row)

    plan: list[dict[str, Any]] = []
    for current_row in current_rows:
        if _normalize_sort_artist_name(current_row.get("sort_artist_name")) is not None:
            continue

        source_key = _source_key(current_row)
        if source_key is not None:
            source_matches = backup_by_source_key.get(source_key) or []
            if len(source_matches) == 1:
                plan.append(
                    _build_plan_row(
                        current_row,
                        source_matches[0],
                        strategy="source_key_exact",
                    )
                )
                continue

        fallback_matches = backup_by_title_artist_year.get(_title_artist_year_key(current_row)) or []
        if len(fallback_matches) != 1:
            continue
        plan.append(
            _build_plan_row(
                current_row,
                fallback_matches[0],
                strategy="title_artist_year_exact",
            )
        )

    return plan
