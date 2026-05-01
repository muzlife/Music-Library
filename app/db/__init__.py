from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Generator

from ..config import get_settings

ORDER_KEY_WIDTH = 12
ORDER_KEY_STEP = 1024
SQLITE_BUSY_TIMEOUT_MS = 30_000
DASHBOARD_MOVE_WINDOW_DAYS = 1
SIZE_GROUP_CODES = ("STD", "BOOK", "LP", "LP10", "LP7", "OVERSIZE", "CASSETTE", "8TRACK", "REEL_TO_REEL", "GOODS")
DOMAIN_CODES = ("KOREA", "JAPAN", "GREATER_CHINA", "WESTERN", "OTHER_ASIA", "WORLD_OTHER", "UNKNOWN")
CABINET_SORT_POLICIES = ("ARTIST_RELEASE_TITLE", "LABEL_ID")
GOODS_RELATION_TYPE_CODES = ("SERIES", "VARIANT", "SET_MEMBER", "RELATED", "PROMO_FOR")
LEGACY_DOMAIN_CODE_MAP = {
    "KOREAN": "KOREA",
    "JPOP": "JAPAN",
    "OTHER": "WORLD_OTHER",
}
LABEL_PREFIX_BY_CATEGORY = {
    "LP": "LP",
    "CD": "CD",
    "CASSETTE": "CT",
    "8TRACK": "8T",
    "DIGITAL": "DG",
    "REEL_TO_REEL": "RT",
    "T_SHIRT": "TS",
    "POSTER": "PO",
    "LIGHT_STICK": "LS",
    "HAT": "HT",
    "BAG": "BG",
    "CUP": "CP",
    "OTHER": "OT",
}
LABEL_CATEGORIES_BY_PREFIX: dict[str, tuple[str, ...]] = {}
for _category_code, _label_prefix in LABEL_PREFIX_BY_CATEGORY.items():
    LABEL_CATEGORIES_BY_PREFIX.setdefault(_label_prefix.upper(), [])
    LABEL_CATEGORIES_BY_PREFIX[_label_prefix.upper()].append(_category_code)
LABEL_CATEGORIES_BY_PREFIX = {
    prefix: tuple(categories)
    for prefix, categories in LABEL_CATEGORIES_BY_PREFIX.items()
}
DEFAULT_SLOT_CAPACITY_MM = {
    "STD": 142,
    "BOOK": 220,
    "LP": 360,
    "LP10": 300,
    "LP7": 200,
    "OVERSIZE": 320,
    "CASSETTE": 142,
    "8TRACK": 142,
    "REEL_TO_REEL": 320,
    "GOODS": 220,
}
DEFAULT_ITEM_THICKNESS_MM = {
    "CD": 10,
    "CD_SLIM": 5,
    "CD_BOX": 18,
    "LP": 4,
    "LP10": 4,
    "LP7": 3,
    "LP_GATEFOLD": 7,
    "LP_BOX": 12,
    "CASSETTE": 11,
    "8TRACK": 22,
    "REEL_TO_REEL": 25,
    "BOOK": 12,
    "GOODS": 12,
}
GOODS_CATEGORY_CODES = ("POSTER", "T_SHIRT", "LIGHT_STICK", "HAT", "BAG", "CUP", "OTHER")
GOODS_STATUS_CODES = ("ACTIVE", "ARCHIVED")
_UNSET = object()
# `AUTO_BACKUP_SETTING_KEYS` lives in app/db/auto_backup.py and is
# re-exported from this package's __init__ at the bottom of the file.


def _domain_code_check_sql() -> str:
    return "', '".join(DOMAIN_CODES)


def _size_group_check_sql() -> str:
    return "', '".join(SIZE_GROUP_CODES)


def _normalize_domain_code_sql(expr: str) -> str:
    return f"""
    CASE UPPER(TRIM(COALESCE({expr}, '')))
      WHEN 'KOREAN' THEN 'KOREA'
      WHEN 'JPOP' THEN 'JAPAN'
      WHEN 'OTHER' THEN 'WORLD_OTHER'
      WHEN 'KOREA' THEN 'KOREA'
      WHEN 'JAPAN' THEN 'JAPAN'
      WHEN 'GREATER_CHINA' THEN 'GREATER_CHINA'
      WHEN 'WESTERN' THEN 'WESTERN'
      WHEN 'OTHER_ASIA' THEN 'OTHER_ASIA'
      WHEN 'WORLD_OTHER' THEN 'WORLD_OTHER'
      WHEN 'UNKNOWN' THEN 'UNKNOWN'
      ELSE NULL
    END
    """


def _normalize_domain_code_value(value: Any) -> str | None:
    code = str(value or "").strip().upper()
    if not code:
        return None
    code = LEGACY_DOMAIN_CODE_MAP.get(code, code)
    return code if code in DOMAIN_CODES else None


def _cabinet_sort_policy_check_sql() -> str:
    return "', '".join(CABINET_SORT_POLICIES)


def _normalize_cabinet_sort_policy_value(value: Any) -> str:
    code = str(value or "").strip().upper()
    return code if code in CABINET_SORT_POLICIES else "ARTIST_RELEASE_TITLE"


def _natural_sort_key(value: Any) -> list[Any]:
    text = str(value or "").strip()
    if not text:
        return [""]
    parts = re.split(r"(\d+)", text)
    return [int(part) if part.isdigit() else part.lower() for part in parts]


def _contains_any_token(value: Any, tokens: tuple[str, ...]) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return False
    return any(token in text for token in tokens)


def _resolve_slot_capacity_mm(
    *,
    allowed_size_group: Any,
    cabinet_name: Any = None,
    slot_code: Any = None,
    format_name: Any = None,
    max_thickness_mm: Any = None,
) -> int:
    try:
        explicit_capacity = int(max_thickness_mm) if max_thickness_mm not in (None, "") else 0
    except (TypeError, ValueError):
        explicit_capacity = 0
    if explicit_capacity > 0:
        return explicit_capacity
    size_group = str(allowed_size_group or "").strip().upper()
    hint_values = (cabinet_name, slot_code, format_name)
    if size_group == "LP":
        if any(_contains_any_token(value, ("확장", "extended", "oversize", "box")) for value in hint_values):
            return 520
        return DEFAULT_SLOT_CAPACITY_MM["LP"]
    if size_group == "LP10":
        if any(_contains_any_token(value, ("확장", "extended", "oversize", "box")) for value in hint_values):
            return DEFAULT_SLOT_CAPACITY_MM["LP"]
        return DEFAULT_SLOT_CAPACITY_MM["LP10"]
    if size_group == "LP7":
        if any(_contains_any_token(value, ("확장", "extended", "oversize", "box")) for value in hint_values):
            return 240
        return DEFAULT_SLOT_CAPACITY_MM["LP7"]
    if size_group == "OVERSIZE":
        if any(_contains_any_token(value, ("lp", "엘피")) for value in hint_values):
            return 520
        return 320
    if size_group in ("BOOK", "GOODS", "CASSETTE", "8TRACK", "REEL_TO_REEL"):
        return DEFAULT_SLOT_CAPACITY_MM[size_group]
    if any(_contains_any_token(value, ("확장", "extended", "oversize", "box")) for value in hint_values):
        return 320
    return DEFAULT_SLOT_CAPACITY_MM.get(size_group, DEFAULT_SLOT_CAPACITY_MM["STD"])


def _resolve_owned_item_thickness_mm(
    *,
    thickness_mm: Any = None,
    size_group: Any = None,
    format_name: Any = None,
    package_hint: Any = None,
    disc_count: Any = None,
    format_items: Any = None,
    slot_size_group: Any = None,
) -> int:
    size_group_u = str(size_group or "").strip().upper()
    slot_size_group_u = str(slot_size_group or "").strip().upper()
    format_name_u = str(format_name or "").strip().upper()

    try:
        disc_count_value = int(disc_count) if disc_count not in (None, "") else None
    except (TypeError, ValueError):
        disc_count_value = None
    if disc_count_value is not None and disc_count_value <= 0:
        disc_count_value = None

    def _vinyl_box_thickness(base_thickness_mm: int) -> int:
        if disc_count_value is None:
            return DEFAULT_ITEM_THICKNESS_MM["LP_BOX"]
        return max(1, (int(base_thickness_mm) * disc_count_value * 120 + 99) // 100)

    def _coerce_format_items(raw: Any) -> list[dict[str, Any]]:
        if isinstance(raw, list):
            return [row for row in raw if isinstance(row, dict)]
        if raw in (None, ""):
            return []
        try:
            parsed = json.loads(str(raw))
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
        if not isinstance(parsed, list):
            return []
        return [row for row in parsed if isinstance(row, dict)]

    def _parse_positive_int(raw: Any, default: int = 0) -> int:
        text = str(raw or "").strip()
        if not text:
            return default
        try:
            value = int(text)
        except (TypeError, ValueError):
            return default
        return value if value > 0 else default

    if size_group_u == "BOOK":
        return DEFAULT_ITEM_THICKNESS_MM["BOOK"]
    if size_group_u == "GOODS":
        return DEFAULT_ITEM_THICKNESS_MM["GOODS"]
    if size_group_u == "CASSETTE" or _contains_any_token(format_name, ("cassette", "카세트", "tape", "mc")):
        return DEFAULT_ITEM_THICKNESS_MM["CASSETTE"]
    if size_group_u == "8TRACK" or _contains_any_token(format_name, ("8-track", "8 track", "8track")):
        return DEFAULT_ITEM_THICKNESS_MM["8TRACK"]
    if size_group_u == "REEL_TO_REEL" or _contains_any_token(format_name, ("reel-to-reel", "reel to reel", "open reel")):
        return DEFAULT_ITEM_THICKNESS_MM["REEL_TO_REEL"]

    hint_values = (format_name, package_hint)
    hint_is_slim = any(_contains_any_token(value, ("slim", "슬림")) for value in hint_values)
    hint_is_gatefold = any(_contains_any_token(value, ("gatefold", "게이트폴드")) for value in hint_values)
    hint_is_box = any(_contains_any_token(value, ("box", "박스", "확장", "digipak")) for value in hint_values)
    hint_is_10inch = any(_contains_any_token(value, ('10"', "10inch", "10-inch", "10인치")) for value in hint_values)
    hint_is_7inch = any(_contains_any_token(value, ('7"', "7inch", "7-inch", "7인치")) for value in hint_values)
    slot_is_box_set = slot_size_group_u == "OVERSIZE"
    lp_box_unit_thickness = DEFAULT_ITEM_THICKNESS_MM["LP_GATEFOLD"] if slot_is_box_set else DEFAULT_ITEM_THICKNESS_MM["LP"]
    format_item_rows = _coerce_format_items(format_items)
    lp_count = 0
    lp10_count = 0
    lp7_count = 0
    cd_count = 0
    for item in format_item_rows:
        qty = _parse_positive_int(item.get("qty"), default=1)
        values = [
            item.get("name"),
            item.get("text"),
            item.get("display"),
            *list(item.get("descriptions") or []),
        ]
        if any(_contains_any_token(value, ("cd", "compact disc", "compactdisc")) for value in values):
            cd_count += qty
            continue
        if any(_contains_any_token(value, ('7"', "7inch", "7-inch", "7인치")) for value in values):
            lp7_count += qty
            continue
        if any(_contains_any_token(value, ('10"', "10inch", "10-inch", "10인치")) for value in values):
            lp10_count += qty
            continue
        if any(_contains_any_token(value, ("lp", "vinyl", "엘피")) for value in values):
            lp_count += qty

    parsed_total_count = lp_count + lp10_count + lp7_count + cd_count
    missing_count = max(0, (disc_count_value or 0) - parsed_total_count)
    if missing_count > 0:
        if size_group_u == "LP7" or hint_is_7inch:
            lp7_count += missing_count
        elif size_group_u == "LP10" or hint_is_10inch:
            lp10_count += missing_count
        elif size_group_u in {"STD", "BOOK"} or format_name_u == "CD":
            cd_count += missing_count
        else:
            lp_count += missing_count

    box_set_slot_item = slot_is_box_set and (
        size_group_u in {"LP", "LP10", "LP7", "OVERSIZE"}
        or size_group_u in {"STD", "BOOK"}
        or format_name_u == "LP"
        or format_name_u == "CD"
        or hint_is_10inch
        or hint_is_7inch
        or bool(format_item_rows)
    )

    if thickness_mm not in (None, ""):
        try:
            value = int(thickness_mm)
        except (TypeError, ValueError):
            value = 0
        if value > 0 and not box_set_slot_item:
            return value

    if slot_is_box_set:
        base_thickness_mm = (
            (lp_count * lp_box_unit_thickness)
            + (lp10_count * DEFAULT_ITEM_THICKNESS_MM["LP10"])
            + (lp7_count * DEFAULT_ITEM_THICKNESS_MM["LP7"])
            + (((cd_count + 3) // 4) * DEFAULT_ITEM_THICKNESS_MM["CD"])
        )
        if base_thickness_mm <= 0 and disc_count_value is not None:
            if size_group_u == "LP7" or hint_is_7inch:
                base_thickness_mm = DEFAULT_ITEM_THICKNESS_MM["LP7"] * disc_count_value
            elif size_group_u == "LP10" or hint_is_10inch:
                base_thickness_mm = DEFAULT_ITEM_THICKNESS_MM["LP10"] * disc_count_value
            elif size_group_u in {"STD", "BOOK"} or format_name_u == "CD":
                base_thickness_mm = ((disc_count_value + 3) // 4) * DEFAULT_ITEM_THICKNESS_MM["CD"]
            else:
                base_thickness_mm = lp_box_unit_thickness * disc_count_value
        if base_thickness_mm > 0:
            return max(1, (base_thickness_mm * 120 + 99) // 100)

    if size_group_u == "LP7" or hint_is_7inch:
        if hint_is_box or slot_is_box_set:
            return _vinyl_box_thickness(DEFAULT_ITEM_THICKNESS_MM["LP7"])
        return DEFAULT_ITEM_THICKNESS_MM["LP7"]

    if size_group_u == "LP10" or hint_is_10inch:
        if hint_is_box or slot_is_box_set:
            return _vinyl_box_thickness(DEFAULT_ITEM_THICKNESS_MM["LP10"])
        if hint_is_gatefold:
            return DEFAULT_ITEM_THICKNESS_MM["LP_GATEFOLD"]
        return DEFAULT_ITEM_THICKNESS_MM["LP10"]

    if format_name_u == "LP" or size_group_u in {"LP", "OVERSIZE"}:
        if hint_is_box or size_group_u == "OVERSIZE" or slot_is_box_set:
            return _vinyl_box_thickness(lp_box_unit_thickness)
        if hint_is_gatefold:
            return DEFAULT_ITEM_THICKNESS_MM["LP_GATEFOLD"]
        return DEFAULT_ITEM_THICKNESS_MM["LP"]

    if hint_is_slim:
        return DEFAULT_ITEM_THICKNESS_MM["CD_SLIM"]
    if hint_is_box or size_group_u == "OVERSIZE":
        return DEFAULT_ITEM_THICKNESS_MM["CD_BOX"]
    return DEFAULT_ITEM_THICKNESS_MM["CD"]


def build_storage_slot_occupancy_summary(
    slot_row: dict[str, Any],
    item_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    capacity_mm = _resolve_slot_capacity_mm(
        allowed_size_group=slot_row.get("allowed_size_group"),
        cabinet_name=slot_row.get("cabinet_name"),
        slot_code=slot_row.get("slot_code"),
        format_name=slot_row.get("format_name"),
        max_thickness_mm=slot_row.get("max_thickness_mm"),
    )
    used_thickness_mm = sum(
        _resolve_owned_item_thickness_mm(
            thickness_mm=row.get("thickness_mm"),
            size_group=row.get("size_group"),
            format_name=row.get("format_name"),
            package_hint=row.get("package_hint") or row.get("notes") or row.get("item_name_override"),
            disc_count=row.get("disc_count"),
            format_items=row.get("format_items") or row.get("format_items_json"),
            slot_size_group=slot_row.get("allowed_size_group"),
        )
        for row in item_rows
    )
    free_thickness_mm = max(capacity_mm - used_thickness_mm, 0)
    occupancy_ratio = (used_thickness_mm / capacity_mm) if capacity_mm > 0 else 0.0
    return {
        "capacity_mm": capacity_mm,
        "used_thickness_mm": used_thickness_mm,
        "free_thickness_mm": free_thickness_mm,
        "occupancy_ratio": occupancy_ratio,
        "occupancy_percent": int(round(occupancy_ratio * 100)),
    }


def _slot_token(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.isdigit():
        return text.zfill(2)
    return re.sub(r"\s+", "-", text.upper())


def _compact_search_text(value: Any) -> str:
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "", str(value or "").strip().lower())


def _album_number_token_variants(value: str) -> list[str]:
    compact = _compact_search_text(value)
    if not compact:
        return []
    variants: list[str] = [compact]

    without_je = re.sub(r"제(?=\d+집$)", "", compact)
    if without_je and without_je not in variants:
        variants.append(without_je)

    match = re.search(r"(\d+집)$", compact)
    if match and "제" not in compact[max(0, match.start(1) - 1) : match.start(1)]:
        with_je = f"{compact[:match.start(1)]}제{match.group(1)}"
        if with_je not in variants:
            variants.append(with_je)

    return variants


def _search_token_groups(value: Any) -> list[list[str]]:
    raw = str(value or "").strip()
    if not raw:
        return []

    groups: list[list[str]] = []
    for token in re.split(r"\s+", raw):
        variants = _album_number_token_variants(token)
        if variants:
            groups.append(variants)

    return groups


def _compact_search_sql_expr(sql_expr: str, *, strip_album_prefix: bool = False) -> str:
    expr = f"LOWER(COALESCE(({sql_expr}), ''))"
    for needle in (" ", "-", "*", "/", "(", ")", "[", "]", "{", "}", ".", ",", ":", ";"):
        expr = f"REPLACE({expr}, '{needle}', '')"
    if strip_album_prefix:
        expr = f"REPLACE({expr}, '제', '')"
    return expr


def _build_compact_token_match_sql(sql_expr: str, token_groups: list[list[str]]) -> tuple[str, list[Any]]:
    if not token_groups:
        return "", []

    preserve_expr = _compact_search_sql_expr(sql_expr, strip_album_prefix=False)
    stripped_expr = _compact_search_sql_expr(sql_expr, strip_album_prefix=True)
    params: list[Any] = []
    group_clauses: list[str] = []

    for variants in token_groups:
        option_clauses: list[str] = []
        for variant in variants:
            if not variant:
                continue
            option_clauses.append(f"{preserve_expr} LIKE ?")
            params.append(f"%{variant}%")
            option_clauses.append(f"{stripped_expr} LIKE ?")
            params.append(f"%{variant}%")
        if option_clauses:
            group_clauses.append("(" + " OR ".join(option_clauses) + ")")

    if not group_clauses:
        return "", []
    return "(" + " AND ".join(group_clauses) + ")", params


def _matches_search_text(value: Any, query_text: str, token_groups: list[list[str]]) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    query_norm = str(query_text or "").strip().lower()
    lowered = text.lower()
    if query_norm and query_norm in lowered:
        return True
    compact = _compact_search_text(text)
    if not compact or not token_groups:
        return False
    for variants in token_groups:
        if not any(variant and variant in compact for variant in variants):
            return False
    return True


def _compose_storage_slot_code(
    cabinet_name: str,
    column_code: str | None,
    cell_code: str | None,
    allowed_size_group: str,
    is_overflow_zone: bool,
) -> str:
    cabinet = _slot_token(cabinet_name) or "SLOT"
    column = _slot_token(column_code)
    cell = _slot_token(cell_code)
    size_group_u = str(allowed_size_group or "").strip().upper() or "STD"
    if is_overflow_zone:
        return f"OVERFLOW-{size_group_u}"
    parts = [cabinet]
    if column:
        parts.append(column)
    if cell:
        parts.append(cell)
    return "-".join(parts)


def _storage_slot_display_name(row: dict[str, Any]) -> str:
    slot_code = str(row.get("slot_code") or "").strip()
    if slot_code == "UNASSIGNED":
        return "미배치"

    cabinet_name = str(row.get("cabinet_name") or "").strip()
    column_code = str(row.get("column_code") or "").strip()
    cell_code = str(row.get("cell_code") or "").strip()
    if cabinet_name:
        parts = [cabinet_name]
        if column_code:
            parts.append(f"{column_code}열")
        if cell_code:
            parts.append(f"{cell_code}칸")
        return " / ".join(parts)

    if slot_code.startswith("OVERFLOW-"):
        return f"Overflow / {slot_code.removeprefix('OVERFLOW-')}"
    return slot_code or "-"


def _cabinet_group_order_value(value: Any) -> int:
    try:
        parsed = int(str(value or "").strip())
    except (TypeError, ValueError):
        return 0
    return parsed if parsed > 0 else 0


def _storage_slot_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    slot_code = str(row.get("slot_code") or "").strip()
    if slot_code == "UNASSIGNED":
        return (2, ["unassigned"], [""], [""], [""], 0)
    if bool(row.get("is_overflow_zone")):
        return (1, _natural_sort_key(row.get("cabinet_name") or "Overflow"), _natural_sort_key(row.get("allowed_size_group")), [""], [""], int(row.get("id") or 0))
    cabinet_name = str(row.get("cabinet_name") or "").strip()
    cabinet_group_name = str(row.get("cabinet_group_name") or "").strip()
    group_name_key = _natural_sort_key(cabinet_group_name or cabinet_name)
    group_order_key = _cabinet_group_order_value(row.get("cabinet_group_order")) if cabinet_group_name else 0
    return (
        0,
        group_name_key,
        _natural_sort_key(row.get("column_code")),
        group_order_key,
        _natural_sort_key(cabinet_name),
        _natural_sort_key(row.get("cell_code")),
        _natural_sort_key(slot_code),
        int(row.get("id") or 0),
    )


def _contains_hangul(text: Any) -> bool:
    value = str(text or "").strip()
    return any("가" <= ch <= "힣" for ch in value)


def _normalize_artist_sort_text(text: Any) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    value = value.replace("*", " ").replace("·", " ").replace("ㆍ", " ")
    value = " ".join(value.split())
    article_match = re.match(r"^(the|a|an)\s+(.+)$", value, flags=re.IGNORECASE)
    if article_match:
        article = article_match.group(1)
        remainder = article_match.group(2).strip()
        if remainder:
            value = f"{remainder}, {article}"
    return value.casefold()


def _normalize_released_date_sort_text(text: Any) -> str:
    return str(text or "").strip()


def _normalize_master_release_sort_text(text: Any, fallback_year: Any = None) -> str:
    raw = str(text or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    if re.fullmatch(r"\d{4}-\d{2}", raw):
        return f"{raw}-99"
    if re.fullmatch(r"\d{4}", raw):
        return f"{raw}-99-99"
    try:
        year_value = int(fallback_year) if fallback_year is not None else None
    except (TypeError, ValueError):
        year_value = None
    if year_value is not None:
        return f"{year_value:04d}-99-99"
    return "9999-99-99"


def _normalize_recommendation_text(text: Any) -> str:
    return _compact_search_text(text)


def _is_title_first_group_artist(text: Any) -> bool:
    normalized = _normalize_recommendation_text(text)
    if not normalized:
        return False
    if "variousartist" in normalized:
        return True
    if normalized in {
        "va",
        "v.a",
        "ost",
        "o.s.t",
        "사운드트랙",
        "오리지널사운드트랙",
        "오에스티",
        "영화음악",
        "드라마음악",
    }:
        return True
    return "soundtrack" in normalized


def _title_first_group_artist_key(text: Any) -> bool:
    return _is_title_first_group_artist(text)


def _preferred_korean_artist_by_master_ids(master_ids: list[int]) -> dict[int, str]:
    normalized_ids = sorted({int(v) for v in master_ids if int(v or 0) > 0})
    if not normalized_ids:
        return {}
    placeholders = ",".join("?" for _ in normalized_ids)
    query = f"""
        SELECT album_master_id, priority, artist_name
        FROM (
          SELECT am.id AS album_master_id, 0 AS priority, am.sort_artist_name AS artist_name
          FROM album_master am
          WHERE am.id IN ({placeholders})
          UNION ALL
          SELECT am.id AS album_master_id, 5 AS priority, am.artist_or_brand AS artist_name
          FROM album_master am
          WHERE am.id IN ({placeholders})
          UNION ALL
          SELECT amm.album_master_id AS album_master_id, 1 AS priority, oi.linked_artist_name AS artist_name
          FROM album_master_member amm
          JOIN owned_item oi ON oi.id = amm.owned_item_id
          WHERE amm.album_master_id IN ({placeholders})
          UNION ALL
          SELECT amm.album_master_id AS album_master_id, 3 AS priority, mid.artist_or_brand AS artist_name
          FROM album_master_member amm
          JOIN music_item_detail mid ON mid.owned_item_id = amm.owned_item_id
          WHERE amm.album_master_id IN ({placeholders})
          UNION ALL
          SELECT aer.album_master_id AS album_master_id, 2 AS priority, aer.artist_or_brand_hint AS artist_name
          FROM album_master_external_ref aer
          WHERE aer.album_master_id IN ({placeholders})
        )
        ORDER BY album_master_id ASC, priority ASC
    """
    params = normalized_ids * 5
    resolved: dict[int, str] = {}
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    for row in rows:
        master_id = int(row["album_master_id"] or 0)
        if master_id <= 0 or master_id in resolved:
            continue
        artist_name = str(row["artist_name"] or "").strip()
        if not _contains_hangul(artist_name):
            continue
        normalized = _normalize_artist_sort_text(artist_name)
        if normalized:
            resolved[master_id] = normalized
    return resolved


def _preferred_owned_item_artist_sort_value(
    row: dict[str, Any],
    korean_artist_by_master_id: dict[int, str] | None = None,
) -> str:
    candidates = [
        row.get("master_sort_artist_name"),
        row.get("linked_artist_name"),
        row.get("artist_or_brand"),
        row.get("master_artist_or_brand"),
    ]
    is_korea = str(row.get("domain_code") or row.get("master_domain_code") or "").strip().upper() == "KOREA"
    if is_korea:
        master_id = int(row.get("linked_album_master_id") or 0)
        if master_id > 0:
            mapped = str((korean_artist_by_master_id or {}).get(master_id) or "").strip()
            if mapped:
                return mapped
        for candidate in candidates:
            if _contains_hangul(candidate):
                normalized = _normalize_artist_sort_text(candidate)
                if normalized:
                    return normalized
    for candidate in candidates:
        normalized = _normalize_artist_sort_text(candidate)
        if normalized:
            return normalized
    return ""


def _owned_item_storage_sort_key(
    row: dict[str, Any],
    korean_artist_by_master_id: dict[int, str] | None = None,
) -> tuple[Any, ...]:
    release_year = row.get("master_release_year")
    try:
        release_year_value = int(release_year) if release_year is not None else None
    except (TypeError, ValueError):
        release_year_value = None
    master_release_sort_value = _normalize_master_release_sort_text(
        row.get("master_release_date"),
        release_year_value,
    )
    released_date_value = _normalize_released_date_sort_text(row.get("released_date"))
    title_value = _normalize_artist_sort_text(row.get("master_title") or row.get("item_name_override"))
    order_key = str(row.get("order_key") or "").strip()
    display_rank = row.get("display_rank")
    try:
        display_rank_value = int(display_rank) if display_rank is not None else None
    except (TypeError, ValueError):
        display_rank_value = None
    if display_rank_value is not None:
        return (
            0,
            display_rank_value,
            int(row.get("id") or 0),
        )
    artist_value = _preferred_owned_item_artist_sort_value(row, korean_artist_by_master_id)
    title_first_group = _title_first_group_artist_key(artist_value)
    common_tail = (
        1 if not order_key else 0,
        order_key,
        int(row.get("id") or 0),
    )
    if title_first_group:
        return (
            1,
            artist_value,
            title_value,
            master_release_sort_value,
            1 if not released_date_value else 0,
            released_date_value or "9999-99-99",
            *common_tail,
        )
    return (
        1,
        artist_value,
        master_release_sort_value,
        1 if not released_date_value else 0,
        released_date_value or "9999-99-99",
        title_value,
        *common_tail,
    )


def owned_item_storage_sort_changed(
    previous_row: dict[str, Any] | None,
    next_row: dict[str, Any] | None,
) -> bool:
    if not isinstance(previous_row, dict) or not isinstance(next_row, dict):
        return False
    try:
        previous_slot_id = int(previous_row.get("storage_slot_id") or 0) or None
    except (TypeError, ValueError):
        previous_slot_id = None
    try:
        next_slot_id = int(next_row.get("storage_slot_id") or 0) or None
    except (TypeError, ValueError):
        next_slot_id = None
    if previous_slot_id is None or previous_slot_id != next_slot_id:
        return False
    slot = get_storage_slot(previous_slot_id) or {}
    if _normalize_cabinet_sort_policy_value(slot.get("cabinet_sort_policy")) == "LABEL_ID":
        return False
    master_ids: list[int] = []
    for row in (previous_row, next_row):
        try:
            master_id = int(row.get("linked_album_master_id") or 0)
        except (TypeError, ValueError):
            master_id = 0
        if master_id > 0:
            master_ids.append(master_id)
    korean_artist_by_master_id = _preferred_korean_artist_by_master_ids(master_ids)
    return _owned_item_storage_sort_key(previous_row, korean_artist_by_master_id) != _owned_item_storage_sort_key(
        next_row,
        korean_artist_by_master_id,
    )


def _extract_collection_dashboard_release_year(row: dict[str, Any]) -> int | None:
    for candidate in (
        row.get("master_release_year"),
        row.get("release_year"),
    ):
        try:
            value = int(candidate) if candidate is not None and str(candidate).strip() else None
        except (TypeError, ValueError):
            value = None
        if value is not None and value > 0:
            return value
    for text in (
        row.get("master_release_date"),
        row.get("released_date"),
    ):
        raw = str(text or "").strip()
        match = re.match(r"^(\d{4})", raw)
        if not match:
            continue
        try:
            value = int(match.group(1))
        except (TypeError, ValueError):
            value = None
        if value is not None and value > 0:
            return value
    return None


def _build_collection_dashboard_first_item_hints(
    slot_item_map: dict[int, list[dict[str, Any]]],
) -> dict[int, dict[str, Any]]:
    master_ids = [
        int(row.get("linked_album_master_id") or 0)
        for rows in slot_item_map.values()
        for row in rows
        if int(row.get("linked_album_master_id") or 0) > 0
    ]
    korean_artist_by_master_id = _preferred_korean_artist_by_master_ids(master_ids)
    hints: dict[int, dict[str, Any]] = {}
    for slot_id, rows in slot_item_map.items():
        if not rows:
            continue
        ordered_rows = sorted(
            rows,
            key=lambda row: _owned_item_storage_sort_key(row, korean_artist_by_master_id),
        )
        first_row = ordered_rows[0] if ordered_rows else None
        if not first_row:
            continue
        artist = (
            str(first_row.get("artist_or_brand") or "").strip()
            or str(first_row.get("linked_artist_name") or "").strip()
            or str(first_row.get("master_artist_or_brand") or "").strip()
            or None
        )
        title = (
            str(first_row.get("item_name_override") or "").strip()
            or str(first_row.get("master_title") or "").strip()
            or None
        )
        hints[int(slot_id)] = {
            "first_item_artist_or_brand": artist,
            "first_item_title": title,
            "first_item_release_year": _extract_collection_dashboard_release_year(first_row),
        }
    return hints


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# External-response cache surface (get/upsert/touch/purge) lives in
# app.db.cache now and is re-exported at the bottom of this module.


def _format_order_value(value: int) -> str:
    safe = value if value > 0 else ORDER_KEY_STEP
    return f"{safe:0{ORDER_KEY_WIDTH}d}"


def _parse_order_value(raw: Any) -> int | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        value = int(text)
    except ValueError:
        return None
    if value <= 0:
        return None
    return value


def _build_label_id(category: str | None, owned_item_id: int) -> str:
    prefix = LABEL_PREFIX_BY_CATEGORY.get(str(category or "").upper(), "IT")
    return f"{prefix}-{owned_item_id:06d}"


def _parse_label_id_query(raw_query: str | None) -> tuple[tuple[str, ...], int] | None:
    compact = re.sub(r"[^A-Za-z0-9]", "", str(raw_query or "").upper())
    if not compact:
        return None
    for prefix, category_codes in LABEL_CATEGORIES_BY_PREFIX.items():
        if not compact.startswith(prefix):
            continue
        raw_owned_item_id = compact[len(prefix):]
        if not raw_owned_item_id.isdigit():
            continue
        owned_item_id = int(raw_owned_item_id)
        if owned_item_id <= 0:
            continue
        return category_codes, owned_item_id
    return None


def _location_slot_snapshot_in_conn(conn: sqlite3.Connection, storage_slot_id: int | None) -> dict[str, Any]:
    if storage_slot_id is None:
        return {
            "storage_slot_id": None,
            "slot_code": "UNASSIGNED",
            "display_name": "미배치",
        }

    row = conn.execute(
        """
        SELECT id, slot_code, cabinet_name, column_code, cell_code, allowed_size_group, is_overflow_zone
        FROM storage_slot
        WHERE id = ?
        LIMIT 1
        """,
        (int(storage_slot_id),),
    ).fetchone()
    if row is None:
        slot_id = int(storage_slot_id)
        return {
            "storage_slot_id": slot_id,
            "slot_code": f"DELETED-{slot_id}",
            "display_name": f"삭제 슬롯 #{slot_id}",
        }

    data = dict(row)
    return {
        "storage_slot_id": int(data["id"]),
        "slot_code": str(data["slot_code"] or ""),
        "display_name": _storage_slot_display_name(data),
    }


def _derive_location_movement_kind(
    from_storage_slot_id: int | None,
    to_storage_slot_id: int | None,
    is_create: bool = False,
) -> str | None:
    if from_storage_slot_id == to_storage_slot_id:
        return None
    if from_storage_slot_id is None and to_storage_slot_id is not None:
        return "INITIAL_ASSIGN" if is_create else "ASSIGN"
    if from_storage_slot_id is not None and to_storage_slot_id is None:
        return "UNASSIGN"
    if from_storage_slot_id is not None and to_storage_slot_id is not None:
        return "MOVE"
    return None


def _log_owned_item_location_event_in_conn(
    conn: sqlite3.Connection,
    owned_item_id: int,
    from_storage_slot_id: int | None,
    to_storage_slot_id: int | None,
    movement_kind: str | None = None,
    note: str | None = None,
    now: str | None = None,
    is_create: bool = False,
) -> None:
    kind = movement_kind or _derive_location_movement_kind(
        from_storage_slot_id=from_storage_slot_id,
        to_storage_slot_id=to_storage_slot_id,
        is_create=is_create,
    )
    if kind is None:
        return

    from_snapshot = _location_slot_snapshot_in_conn(conn, from_storage_slot_id)
    to_snapshot = _location_slot_snapshot_in_conn(conn, to_storage_slot_id)
    timestamp = now or utc_now_iso()
    note_text = str(note).strip() if note is not None else ""
    conn.execute(
        """
        INSERT INTO owned_item_location_event (
          owned_item_id,
          from_storage_slot_id,
          from_slot_code,
          from_slot_display_name,
          to_storage_slot_id,
          to_slot_code,
          to_slot_display_name,
          movement_kind,
          note,
          created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            owned_item_id,
            from_snapshot["storage_slot_id"],
            from_snapshot["slot_code"],
            from_snapshot["display_name"],
            to_snapshot["storage_slot_id"],
            to_snapshot["slot_code"],
            to_snapshot["display_name"],
            kind,
            note_text or None,
            timestamp,
        ),
    )


def _ensure_parent_dir(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _ensure_app_setting_table(conn: sqlite3.Connection) -> None:
    conn.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS app_setting (
          setting_key TEXT PRIMARY KEY,
          setting_value TEXT,
          updated_at TEXT NOT NULL
        );
        """
    )


# `_default_auto_backup_dir`, `_upsert_app_setting`,
# `_auto_backup_settings_from_conn`, plus the public auto-backup
# read/write surface live in app/db/auto_backup.py and are re-exported
# from this package's __init__ at the bottom of the file.


@contextmanager
def get_conn() -> Generator[sqlite3.Connection, None, None]:
    settings = get_settings()
    _ensure_parent_dir(settings.db_path)
    conn = sqlite3.connect(
        settings.db_path,
        timeout=SQLITE_BUSY_TIMEOUT_MS / 1000,
    )
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA journal_mode = WAL").fetchone()
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_write_conn() -> Generator[sqlite3.Connection, None, None]:
    """Connection that begins an IMMEDIATE transaction up-front.

    Use this in place of `get_conn` for any function that performs multiple
    write statements (inserts/updates/deletes) that must be a single atomic
    unit, especially when concurrent writers (auto-backup thread, metadata
    sync worker, user requests) might race for the SQLite WAL write lock.

    With the default DEFERRED isolation, two writers that BEGIN at the same
    time will both succeed initially and only collide on the first write,
    which on busy systems leaves one of them with a partial work-set when
    SQLITE_BUSY fires past the timeout. IMMEDIATE acquires the write lock
    first, so contenders block at BEGIN — predictably and atomically.

    The connection is configured with `isolation_level=None` (autocommit
    mode) and we manage `BEGIN IMMEDIATE`/`COMMIT`/`ROLLBACK` ourselves.
    """
    settings = get_settings()
    _ensure_parent_dir(settings.db_path)
    conn = sqlite3.connect(
        settings.db_path,
        timeout=SQLITE_BUSY_TIMEOUT_MS / 1000,
        isolation_level=None,
    )
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA journal_mode = WAL").fetchone()
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("BEGIN IMMEDIATE")
    committed = False
    try:
        yield conn
        conn.execute("COMMIT")
        committed = True
    finally:
        if not committed:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            f"""
            CREATE TABLE IF NOT EXISTS metadata_source (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              source_code TEXT NOT NULL UNIQUE,
              source_name TEXT NOT NULL,
              source_scope TEXT NOT NULL CHECK (source_scope IN ('GLOBAL', 'KR', 'INTERNAL')),
              is_primary INTEGER NOT NULL DEFAULT 0,
              priority INTEGER NOT NULL DEFAULT 100,
              enabled INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ingestion_batch (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ingest_source TEXT NOT NULL,
              started_at TEXT NOT NULL,
              completed_at TEXT,
              total_count INTEGER NOT NULL DEFAULT 0,
              matched_count INTEGER NOT NULL DEFAULT 0,
              review_count INTEGER NOT NULL DEFAULT 0,
              failed_count INTEGER NOT NULL DEFAULT 0,
              created_by TEXT,
              notes TEXT
            );

            CREATE TABLE IF NOT EXISTS review_queue (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              batch_id INTEGER NOT NULL,
              row_no INTEGER,
              category TEXT,
              payload_json TEXT NOT NULL,
              candidate_json TEXT,
              confidence_score REAL NOT NULL,
              review_status TEXT NOT NULL CHECK (review_status IN ('AUTO_APPROVED', 'NEEDS_REVIEW', 'APPROVED', 'REJECTED')),
              review_note TEXT,
              created_at TEXT NOT NULL,
              reviewed_at TEXT,
              reviewed_by TEXT,
              FOREIGN KEY (batch_id) REFERENCES ingestion_batch(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS storage_slot (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              slot_code TEXT NOT NULL UNIQUE,
              allowed_size_group TEXT NOT NULL CHECK (allowed_size_group IN ('{_size_group_check_sql()}')),
              cabinet_sort_policy TEXT NOT NULL DEFAULT 'ARTIST_RELEASE_TITLE' CHECK (cabinet_sort_policy IN ('ARTIST_RELEASE_TITLE', 'LABEL_ID')),
              cabinet_domain_code TEXT CHECK (cabinet_domain_code IN ('KOREA', 'JAPAN', 'GREATER_CHINA', 'WESTERN', 'OTHER_ASIA', 'WORLD_OTHER', 'UNKNOWN')),
              max_thickness_mm INTEGER,
              cabinet_group_name TEXT,
              cabinet_group_order INTEGER,
              is_overflow_zone INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cabinet_camera (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              cabinet_name TEXT NOT NULL UNIQUE,
              camera_name TEXT NOT NULL,
              onvif_device_url TEXT,
              snapshot_url TEXT,
              stream_url TEXT,
              username TEXT,
              password TEXT,
              notes TEXT,
              is_active INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS classification_option (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              option_group TEXT NOT NULL CHECK (option_group IN ('SUBTYPE', 'SOUNDTRACK')),
              label TEXT NOT NULL,
              sort_order INTEGER NOT NULL DEFAULT 100,
              is_active INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE (option_group, label)
            );

            CREATE TABLE IF NOT EXISTS owned_item (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              master_item_id INTEGER,
              linked_album_master_id INTEGER,
              linked_artist_name TEXT,
              copy_group_key TEXT,
              category TEXT NOT NULL,
              domain_code TEXT CHECK (domain_code IN ('KOREA', 'JAPAN', 'GREATER_CHINA', 'WESTERN', 'OTHER_ASIA', 'WORLD_OTHER', 'UNKNOWN')),
              release_type TEXT CHECK (release_type IN ('ALBUM', 'EP', 'SINGLE')),
              item_name_override TEXT,
              quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
              is_second_hand INTEGER NOT NULL DEFAULT 0,
              size_group TEXT NOT NULL CHECK (size_group IN ('{_size_group_check_sql()}')),
              preferred_storage_size_group TEXT CHECK (preferred_storage_size_group IN ('{_size_group_check_sql()}')),
              status TEXT NOT NULL DEFAULT 'IN_COLLECTION' CHECK (status IN ('IN_COLLECTION', 'LOANED', 'SOLD', 'LOST', 'ARCHIVED')),
              condition_grade TEXT,
              signature_type TEXT NOT NULL DEFAULT 'NONE' CHECK (signature_type IN ('NONE', 'IN_PERSON', 'PURCHASE_INCLUDED', 'UNKNOWN')),
              source_code TEXT,
              source_external_id TEXT,
              signed_by TEXT,
              signed_at TEXT,
              acquisition_date TEXT,
              purchase_price REAL,
              currency_code TEXT,
              purchase_source TEXT,
              memory_note TEXT,
              display_rank INTEGER,
              order_key TEXT,
              storage_slot_id INTEGER,
              thickness_mm INTEGER,
              notes TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              CHECK (signature_type <> 'NONE' OR (signed_by IS NULL AND signed_at IS NULL)),
              FOREIGN KEY (linked_album_master_id) REFERENCES album_master(id) ON DELETE SET NULL,
              FOREIGN KEY (storage_slot_id) REFERENCES storage_slot(id)
            );

            CREATE TABLE IF NOT EXISTS owned_item_location_event (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              owned_item_id INTEGER NOT NULL,
              from_storage_slot_id INTEGER,
              from_slot_code TEXT,
              from_slot_display_name TEXT,
              to_storage_slot_id INTEGER,
              to_slot_code TEXT,
              to_slot_display_name TEXT,
              movement_kind TEXT NOT NULL CHECK (movement_kind IN ('INITIAL_ASSIGN', 'ASSIGN', 'MOVE', 'UNASSIGN', 'CABINET_DELETE')),
              note TEXT,
              created_at TEXT NOT NULL,
              FOREIGN KEY (owned_item_id) REFERENCES owned_item(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS music_item_detail (
              owned_item_id INTEGER PRIMARY KEY,
              format_name TEXT NOT NULL CHECK (format_name IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')),
              is_promotional_not_for_sale INTEGER NOT NULL DEFAULT 0,
              artist_or_brand TEXT,
              release_year INTEGER,
              released_date TEXT,
              barcode TEXT,
              label_name TEXT,
              catalog_no TEXT,
              cover_image_url TEXT,
              track_list_json TEXT,
              media_type TEXT,
              genres_json TEXT,
              styles_json TEXT,
              media_condition TEXT,
              sleeve_condition TEXT,
              disc_count INTEGER,
              speed_rpm INTEGER,
              has_obi INTEGER,
              runout_matrix TEXT,
              runout_matrix_json TEXT,
              pressing_country TEXT,
              source_notes TEXT,
              credits_json TEXT,
              identifier_items_json TEXT,
              image_items_json TEXT,
              company_items_json TEXT,
              series_json TEXT,
              format_items_json TEXT,
              track_items_json TEXT,
              label_items_json TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (owned_item_id) REFERENCES owned_item(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS goods_item_detail (
              owned_item_id INTEGER PRIMARY KEY,
              image_urls_json TEXT,
              primary_image_url TEXT,
              poster_storage_spec TEXT,
              tshirt_size TEXT,
              cup_material TEXT,
              hat_size TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (owned_item_id) REFERENCES owned_item(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS goods_item (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              category TEXT NOT NULL CHECK (category IN ('{_goods_category_check_sql()}')),
              goods_name TEXT NOT NULL,
              description TEXT,
              quantity INTEGER NOT NULL DEFAULT 1,
              size_group TEXT NOT NULL DEFAULT 'GOODS' CHECK (size_group IN ('{_size_group_check_sql()}')),
              storage_slot_id INTEGER,
              status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('{_goods_status_check_sql()}')),
              domain_code TEXT CHECK (domain_code IN ('{_domain_code_check_sql()}')),
              memory_note TEXT,
              image_urls_json TEXT NOT NULL DEFAULT '[]',
              primary_image_url TEXT,
              poster_storage_spec TEXT,
              tshirt_size TEXT,
              cup_material TEXT,
              hat_size TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (storage_slot_id) REFERENCES storage_slot(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS goods_item_album_master_map (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              goods_item_id INTEGER NOT NULL,
              album_master_id INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              UNIQUE (goods_item_id, album_master_id),
              FOREIGN KEY (goods_item_id) REFERENCES goods_item(id) ON DELETE CASCADE,
              FOREIGN KEY (album_master_id) REFERENCES album_master(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS goods_item_artist_map (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              goods_item_id INTEGER NOT NULL,
              artist_name TEXT NOT NULL,
              normalized_artist_name TEXT NOT NULL,
              created_at TEXT NOT NULL,
              UNIQUE (goods_item_id, normalized_artist_name),
              FOREIGN KEY (goods_item_id) REFERENCES goods_item(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS goods_item_label_map (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              goods_item_id INTEGER NOT NULL,
              label_name TEXT NOT NULL,
              normalized_label_name TEXT NOT NULL,
              created_at TEXT NOT NULL,
              UNIQUE (goods_item_id, normalized_label_name),
              FOREIGN KEY (goods_item_id) REFERENCES goods_item(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS goods_item_collectible_relation (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              goods_item_id INTEGER NOT NULL,
              relation_type TEXT NOT NULL CHECK (relation_type IN ('{_goods_relation_type_check_sql()}')),
              linked_goods_item_id INTEGER NOT NULL,
              note TEXT,
              display_order INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE (goods_item_id, relation_type, linked_goods_item_id),
              FOREIGN KEY (goods_item_id) REFERENCES goods_item(id) ON DELETE CASCADE,
              FOREIGN KEY (linked_goods_item_id) REFERENCES goods_item(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS owned_item_subtype (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              owned_item_id INTEGER NOT NULL,
              option_id INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              UNIQUE (owned_item_id, option_id),
              FOREIGN KEY (owned_item_id) REFERENCES owned_item(id) ON DELETE CASCADE,
              FOREIGN KEY (option_id) REFERENCES classification_option(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS owned_item_soundtrack (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              owned_item_id INTEGER NOT NULL,
              option_id INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              UNIQUE (owned_item_id, option_id),
              FOREIGN KEY (owned_item_id) REFERENCES owned_item(id) ON DELETE CASCADE,
              FOREIGN KEY (option_id) REFERENCES classification_option(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS digital_asset (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              asset_type TEXT NOT NULL CHECK (asset_type IN ('AUDIO', 'IMAGE', 'DOCUMENT', 'VIDEO')),
              file_path TEXT NOT NULL,
              file_hash TEXT,
              file_size_bytes INTEGER,
              duration_sec INTEGER,
              metadata_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS owned_item_digital_link (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              owned_item_id INTEGER NOT NULL,
              digital_asset_id INTEGER NOT NULL,
              link_type TEXT NOT NULL CHECK (link_type IN ('FULL_ALBUM', 'TRACK', 'SCAN', 'REFERENCE', 'PROOF')),
              track_no INTEGER,
              note TEXT,
              created_at TEXT NOT NULL,
              UNIQUE (owned_item_id, digital_asset_id, link_type, track_no),
              FOREIGN KEY (owned_item_id) REFERENCES owned_item(id) ON DELETE CASCADE,
              FOREIGN KEY (digital_asset_id) REFERENCES digital_asset(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS album_master (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              source_code TEXT NOT NULL CHECK (source_code IN ('DISCOGS', 'MANIADB', 'MUSICBRAINZ', 'MANUAL')),
              source_master_id TEXT NOT NULL,
              title TEXT NOT NULL,
              artist_or_brand TEXT,
              sort_artist_name TEXT,
              domain_code TEXT CHECK (domain_code IN ('KOREA', 'JAPAN', 'GREATER_CHINA', 'WESTERN', 'OTHER_ASIA', 'WORLD_OTHER', 'UNKNOWN')),
              release_year INTEGER,
              source_domain_code TEXT CHECK (source_domain_code IN ('KOREA', 'JAPAN', 'GREATER_CHINA', 'WESTERN', 'OTHER_ASIA', 'WORLD_OTHER', 'UNKNOWN')),
              source_release_year INTEGER,
              override_domain_code TEXT CHECK (override_domain_code IN ('KOREA', 'JAPAN', 'GREATER_CHINA', 'WESTERN', 'OTHER_ASIA', 'WORLD_OTHER', 'UNKNOWN')),
              override_release_year INTEGER,
              override_note TEXT,
              raw_json TEXT NOT NULL DEFAULT '{{}}',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE (source_code, source_master_id)
            );

            CREATE TABLE IF NOT EXISTS album_master_member (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              album_master_id INTEGER NOT NULL,
              owned_item_id INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              UNIQUE (album_master_id, owned_item_id),
              FOREIGN KEY (album_master_id) REFERENCES album_master(id) ON DELETE CASCADE,
              FOREIGN KEY (owned_item_id) REFERENCES owned_item(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS album_master_external_ref (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              album_master_id INTEGER NOT NULL,
              source_code TEXT NOT NULL CHECK (source_code IN ('DISCOGS', 'MANIADB', 'MUSICBRAINZ', 'MANUAL')),
              source_master_id TEXT NOT NULL,
              title_hint TEXT,
              artist_or_brand_hint TEXT,
              release_year INTEGER,
              raw_json TEXT NOT NULL DEFAULT '{{}}',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE (source_code, source_master_id),
              FOREIGN KEY (album_master_id) REFERENCES album_master(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS album_master_merge_history (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              source_album_master_id INTEGER NOT NULL,
              target_album_master_id INTEGER NOT NULL,
              source_master_snapshot_json TEXT NOT NULL DEFAULT '{{}}',
              target_master_snapshot_json TEXT NOT NULL DEFAULT '{{}}',
              source_member_links_json TEXT NOT NULL DEFAULT '[]',
              source_external_refs_json TEXT NOT NULL DEFAULT '[]',
              overlap_owned_item_ids_json TEXT NOT NULL DEFAULT '[]',
              moved_member_count INTEGER NOT NULL DEFAULT 0,
              target_member_count INTEGER NOT NULL DEFAULT 0,
              merged_by TEXT,
              created_at TEXT NOT NULL,
              target_updated_at_after_merge TEXT,
              rolled_back_at TEXT,
              rolled_back_by TEXT
            );

            CREATE TABLE IF NOT EXISTS customer_track_request (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              requested_track TEXT NOT NULL,
              owned_item_id INTEGER,
              matched_track_title TEXT,
              matched_track_no INTEGER,
              item_title_snapshot TEXT,
              artist_or_brand_snapshot TEXT,
              cover_image_url_snapshot TEXT,
              category_snapshot TEXT,
              current_slot_code_snapshot TEXT,
              current_slot_display_snapshot TEXT,
              previous_slot_code_snapshot TEXT,
              previous_slot_display_snapshot TEXT,
              customer_note TEXT,
              response_note TEXT,
              status TEXT NOT NULL DEFAULT 'REQUESTED' CHECK (status IN ('REQUESTED', 'PLAYING', 'RETURNED', 'CANCELLED')),
              requested_by TEXT,
              handled_by TEXT,
              handled_at TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (owned_item_id) REFERENCES owned_item(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS auth_account (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              role TEXT NOT NULL CHECK (role IN ('ADMIN', 'OPERATOR')),
              is_active INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS purchase_import_queue (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              vendor_code TEXT NOT NULL CHECK (vendor_code IN ('{_purchase_import_vendor_check_sql()}')),
              source_type TEXT NOT NULL CHECK (source_type IN ('EMAIL_HTML', 'EMAIL_TEXT', 'FILE_UPLOAD', 'MANUAL')),
              source_ref TEXT,
              email_from TEXT,
              email_subject TEXT,
              artist_name TEXT,
              item_name TEXT NOT NULL,
              media_format TEXT,
              quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
              unit_price REAL,
              line_total REAL,
              currency_code TEXT,
              purchase_date TEXT,
              seller_name TEXT,
              item_url TEXT,
              image_url TEXT,
              raw_line TEXT,
              raw_payload_json TEXT NOT NULL DEFAULT '{{}}',
              queue_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (queue_status IN ('PENDING', 'CREATED', 'IGNORED')),
              linked_owned_item_id INTEGER,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (linked_owned_item_id) REFERENCES owned_item(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_review_queue_status ON review_queue (review_status, confidence_score, created_at);
            CREATE INDEX IF NOT EXISTS idx_owned_item_category_rank ON owned_item (category, display_rank);
            CREATE INDEX IF NOT EXISTS idx_owned_item_signature ON owned_item (signature_type);
            CREATE INDEX IF NOT EXISTS idx_owned_item_second_hand ON owned_item (is_second_hand);
            CREATE INDEX IF NOT EXISTS idx_owned_item_location_event_owned ON owned_item_location_event (owned_item_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_owned_item_location_event_from_slot ON owned_item_location_event (from_slot_code, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_owned_item_location_event_to_slot ON owned_item_location_event (to_slot_code, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_classification_option_group ON classification_option (option_group, is_active, sort_order, label);
            CREATE INDEX IF NOT EXISTS idx_owned_item_subtype_owned ON owned_item_subtype (owned_item_id);
            CREATE INDEX IF NOT EXISTS idx_owned_item_soundtrack_owned ON owned_item_soundtrack (owned_item_id);
            CREATE INDEX IF NOT EXISTS idx_album_master_lookup ON album_master (source_code, source_master_id);
            CREATE INDEX IF NOT EXISTS idx_album_master_member_owned ON album_master_member (owned_item_id);
            CREATE INDEX IF NOT EXISTS idx_album_master_external_ref_master ON album_master_external_ref (album_master_id);
            CREATE INDEX IF NOT EXISTS idx_album_master_external_ref_lookup ON album_master_external_ref (source_code, source_master_id);
            CREATE INDEX IF NOT EXISTS idx_album_master_merge_history_created ON album_master_merge_history (created_at DESC, id DESC);
            CREATE INDEX IF NOT EXISTS idx_goods_item_category_name ON goods_item (category, goods_name);
            CREATE INDEX IF NOT EXISTS idx_goods_item_storage_slot ON goods_item (storage_slot_id, status);
            CREATE INDEX IF NOT EXISTS idx_goods_item_album_master_map_goods ON goods_item_album_master_map (goods_item_id, album_master_id);
            CREATE INDEX IF NOT EXISTS idx_goods_item_artist_map_lookup ON goods_item_artist_map (normalized_artist_name);
            CREATE INDEX IF NOT EXISTS idx_goods_item_label_map_lookup ON goods_item_label_map (normalized_label_name);
            CREATE INDEX IF NOT EXISTS idx_customer_track_request_status ON customer_track_request (status, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_customer_track_request_owned ON customer_track_request (owned_item_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_auth_account_role ON auth_account (role, is_active, username);
            CREATE INDEX IF NOT EXISTS idx_purchase_import_queue_status ON purchase_import_queue (queue_status, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_purchase_import_queue_vendor ON purchase_import_queue (vendor_code, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_purchase_import_queue_source_ref ON purchase_import_queue (vendor_code, source_ref) WHERE source_ref IS NOT NULL;
            CREATE INDEX IF NOT EXISTS idx_owned_item_category_created_id ON owned_item (category, created_at DESC, id DESC);
            CREATE INDEX IF NOT EXISTS idx_owned_item_location_event_move_created_owned ON owned_item_location_event (movement_kind, created_at DESC, owned_item_id, id DESC);

            CREATE TABLE IF NOT EXISTS external_response_cache (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              cache_key TEXT NOT NULL UNIQUE,
              source_code TEXT NOT NULL,
              body_json TEXT NOT NULL,
              status_code INTEGER NOT NULL DEFAULT 200,
              fetched_at TEXT NOT NULL,
              expires_at TEXT,
              etag TEXT,
              last_modified TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_external_response_cache_expires ON external_response_cache (expires_at) WHERE expires_at IS NOT NULL;
            CREATE INDEX IF NOT EXISTS idx_external_response_cache_source ON external_response_cache (source_code, fetched_at DESC);
            """
        )

        _apply_migrations(conn)
        _ensure_app_setting_table(conn)
        _ensure_recent_feed_indexes(conn)
        _seed_metadata_sources(conn)
        _cleanup_overflow_slots(conn)
        _seed_classification_options(conn)


def ensure_startup_db_ready() -> None:
    settings = get_settings()
    db_path = Path(settings.db_path)
    _ensure_parent_dir(settings.db_path)
    if not db_path.exists() or db_path.stat().st_size == 0:
        init_db()
        return

    conn = sqlite3.connect(settings.db_path, timeout=1)
    try:
        row = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'owned_item'
            """
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        init_db()
        return

    # Fast path: if user_version already matches SCHEMA_VERSION, skip the
    # legacy idempotent inspection entirely. This used to scan ~60 columns
    # via PRAGMA table_info on every boot; with the version short-circuit
    # in place we only re-pay that cost when the schema actually changes.
    conn = sqlite3.connect(settings.db_path, timeout=1)
    try:
        conn.row_factory = sqlite3.Row
        if _read_user_version(conn) >= SCHEMA_VERSION:
            # Seeders / cleanups remain idempotent and cheap; keep them
            # running so manual DB edits don't drift away silently.
            _seed_metadata_sources(conn)
            _cleanup_overflow_slots(conn)
            _seed_classification_options(conn)
            return

        _apply_migrations(conn)
        _ensure_app_setting_table(conn)
        _ensure_recent_feed_indexes(conn)
        _seed_metadata_sources(conn)
        _cleanup_overflow_slots(conn)
        _seed_classification_options(conn)
    finally:
        conn.close()


# `get_auto_backup_settings`, `save_auto_backup_settings`, and
# `record_auto_backup_result` live in app/db/auto_backup.py and are
# re-exported from this package's __init__ at the bottom of the file.


def _column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(str(row["name"]) == column_name for row in rows)


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (str(table_name or ""),),
    ).fetchone()
    return row is not None


# `_purchase_import_vendor_check_sql` lives in app.db.purchase_import and
# is re-exported at the bottom of this module.


def _ensure_recent_feed_indexes(conn: sqlite3.Connection) -> None:
    if _column_exists(conn, "owned_item", "category") and _column_exists(conn, "owned_item", "created_at"):
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_owned_item_category_created_id ON owned_item (category, created_at DESC, id DESC)"
        )
    if (
        _column_exists(conn, "owned_item_location_event", "movement_kind")
        and _column_exists(conn, "owned_item_location_event", "created_at")
        and _column_exists(conn, "owned_item_location_event", "owned_item_id")
    ):
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_owned_item_location_event_move_created_owned ON owned_item_location_event (movement_kind, created_at DESC, owned_item_id, id DESC)"
        )


# `_ensure_auth_account_table` lives in app.db.auth_account now and is
# re-exported at the bottom of this module so existing call sites keep
# working unchanged.


# `_ensure_purchase_import_queue_table` lives in app.db.purchase_import
# and is re-exported at the bottom of this module.


def _album_master_allows_manual(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'album_master'"
    ).fetchone()
    if not row:
        return False
    table_sql = str(row["sql"] or "").upper()
    return "SOURCE_CODE" in table_sql and "'MANUAL'" in table_sql and "'MUSICBRAINZ'" in table_sql


# Purchase-import queue migration helpers live in app.db.purchase_import
# and are re-exported at the bottom of this module.


def _migrate_album_master_allow_manual(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'album_master'"
    ).fetchone()
    if not row or _album_master_allows_manual(conn):
        return

    if conn.in_transaction:
        conn.commit()

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript(
            """
            BEGIN;
            DROP TABLE IF EXISTS album_master_new;
            CREATE TABLE album_master_new (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              source_code TEXT NOT NULL CHECK (source_code IN ('DISCOGS', 'MANIADB', 'MUSICBRAINZ', 'MANUAL')),
              source_master_id TEXT NOT NULL,
              title TEXT NOT NULL,
              artist_or_brand TEXT,
              sort_artist_name TEXT,
              domain_code TEXT CHECK (domain_code IN ('KOREA', 'JAPAN', 'GREATER_CHINA', 'WESTERN', 'OTHER_ASIA', 'WORLD_OTHER', 'UNKNOWN')),
              release_year INTEGER,
              raw_json TEXT NOT NULL DEFAULT '{{}}',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE (source_code, source_master_id)
            );
            INSERT INTO album_master_new
              (id, source_code, source_master_id, title, artist_or_brand, sort_artist_name, domain_code, release_year, raw_json, created_at, updated_at)
            SELECT
              id, source_code, source_master_id, title, artist_or_brand, NULL, NULL, release_year, raw_json, created_at, updated_at
            FROM album_master;
            DROP TABLE album_master;
            ALTER TABLE album_master_new RENAME TO album_master;
            CREATE INDEX IF NOT EXISTS idx_album_master_lookup ON album_master (source_code, source_master_id);
            COMMIT;
            """
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _ensure_album_master_external_ref_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS album_master_external_ref (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          album_master_id INTEGER NOT NULL,
          source_code TEXT NOT NULL CHECK (source_code IN ('DISCOGS', 'MANIADB', 'MUSICBRAINZ', 'MANUAL')),
          source_master_id TEXT NOT NULL,
          title_hint TEXT,
          artist_or_brand_hint TEXT,
          release_year INTEGER,
          raw_json TEXT NOT NULL DEFAULT '{{}}',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE (source_code, source_master_id),
          FOREIGN KEY (album_master_id) REFERENCES album_master(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_album_master_external_ref_master ON album_master_external_ref (album_master_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_album_master_external_ref_lookup ON album_master_external_ref (source_code, source_master_id)"
    )


def _ensure_album_master_merge_history_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS album_master_merge_history (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source_album_master_id INTEGER NOT NULL,
          target_album_master_id INTEGER NOT NULL,
          source_master_snapshot_json TEXT NOT NULL DEFAULT '{}',
          target_master_snapshot_json TEXT NOT NULL DEFAULT '{}',
          source_member_links_json TEXT NOT NULL DEFAULT '[]',
          source_external_refs_json TEXT NOT NULL DEFAULT '[]',
          overlap_owned_item_ids_json TEXT NOT NULL DEFAULT '[]',
          moved_member_count INTEGER NOT NULL DEFAULT 0,
          target_member_count INTEGER NOT NULL DEFAULT 0,
          merged_by TEXT,
          created_at TEXT NOT NULL,
          target_updated_at_after_merge TEXT,
          rolled_back_at TEXT,
          rolled_back_by TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_album_master_merge_history_created ON album_master_merge_history (created_at DESC, id DESC)"
    )


def _backfill_album_master_external_refs(conn: sqlite3.Connection) -> None:
    _ensure_album_master_external_ref_table(conn)
    # The backfill SELECTs from album_master; if that table doesn't exist
    # in the current DB (e.g. test fixture with a minimal schema), there's
    # nothing to backfill — skip so the SELECT doesn't raise.
    if not _table_exists(conn, "album_master"):
        return
    now = utc_now_iso()
    conn.execute(
        """
        INSERT OR IGNORE INTO album_master_external_ref
          (album_master_id, source_code, source_master_id, title_hint, artist_or_brand_hint, release_year, raw_json, created_at, updated_at)
        SELECT
          id,
          source_code,
          source_master_id,
          title,
          artist_or_brand,
          release_year,
          raw_json,
          ?,
          updated_at
        FROM album_master
        WHERE TRIM(COALESCE(source_code, '')) <> ''
          AND TRIM(COALESCE(source_master_id, '')) <> ''
        """,
        (now,),
    )


def _music_item_detail_allows_extended_formats(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'music_item_detail'"
    ).fetchone()
    if not row:
        return False
    table_sql = str(row["sql"] or "").upper()
    return "'8TRACK'" in table_sql and "'DIGITAL'" in table_sql and "'REEL_TO_REEL'" in table_sql


def _migrate_music_item_detail_allow_extended_formats(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'music_item_detail'"
    ).fetchone()
    if not row or _music_item_detail_allows_extended_formats(conn):
        return

    if conn.in_transaction:
        conn.commit()

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript(
            """
            BEGIN;
            DROP TABLE IF EXISTS music_item_detail_new;
            CREATE TABLE music_item_detail_new (
              owned_item_id INTEGER PRIMARY KEY,
              format_name TEXT NOT NULL CHECK (format_name IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')),
              is_promotional_not_for_sale INTEGER NOT NULL DEFAULT 0,
              artist_or_brand TEXT,
              release_year INTEGER,
              released_date TEXT,
              barcode TEXT,
              label_name TEXT,
              catalog_no TEXT,
              cover_image_url TEXT,
              track_list_json TEXT,
              media_type TEXT,
              genres_json TEXT,
              styles_json TEXT,
              media_condition TEXT,
              sleeve_condition TEXT,
              disc_count INTEGER,
              speed_rpm INTEGER,
              has_obi INTEGER,
              runout_matrix TEXT,
              runout_matrix_json TEXT,
              pressing_country TEXT,
              source_notes TEXT,
              credits_json TEXT,
              identifier_items_json TEXT,
              image_items_json TEXT,
              company_items_json TEXT,
              series_json TEXT,
              format_items_json TEXT,
              track_items_json TEXT,
              label_items_json TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (owned_item_id) REFERENCES owned_item(id) ON DELETE CASCADE
            );
            INSERT INTO music_item_detail_new (
              owned_item_id, format_name, is_promotional_not_for_sale,
              artist_or_brand, release_year, released_date, barcode,
              label_name, catalog_no, cover_image_url, track_list_json,
              media_type, genres_json, styles_json,
              media_condition, sleeve_condition, disc_count, speed_rpm,
              has_obi, runout_matrix, runout_matrix_json, pressing_country,
              source_notes, credits_json, identifier_items_json, image_items_json,
              company_items_json, series_json, format_items_json, track_items_json,
              label_items_json, created_at, updated_at
            )
            SELECT
              owned_item_id, format_name, is_promotional_not_for_sale,
              artist_or_brand, release_year, NULL, barcode,
              label_name, catalog_no, cover_image_url, track_list_json,
              media_type, genres_json, styles_json,
              media_condition, sleeve_condition, disc_count, speed_rpm,
              has_obi, runout_matrix, NULL, pressing_country,
              NULL, NULL, NULL, NULL,
              NULL, NULL, NULL, NULL,
              NULL, created_at, updated_at
            FROM music_item_detail;
            DROP TABLE music_item_detail;
            ALTER TABLE music_item_detail_new RENAME TO music_item_detail;
            COMMIT;
            """
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _owned_item_allows_goods(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'owned_item'"
    ).fetchone()
    if not row:
        return False
    table_sql = str(row["sql"] or "").upper()
    return "'GOODS'" in table_sql and "'LP10'" in table_sql and "'LP7'" in table_sql and "'CASSETTE'" in table_sql


def _owned_item_allows_extended_domains(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'owned_item'"
    ).fetchone()
    if not row:
        return False
    table_sql = str(row["sql"] or "").upper()
    return "'GREATER_CHINA'" in table_sql and "'WORLD_OTHER'" in table_sql and "'UNKNOWN'" in table_sql


def _migrate_owned_item_allow_goods(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'owned_item'"
    ).fetchone()
    if not row or _owned_item_allows_goods(conn):
        return
    # Defensive: the rewrite SELECTs from columns we expect a real
    # owned_item to have (master_item_id, etc.). Test fixtures and
    # partially-initialised DBs sometimes carry only the columns they care
    # about; running the rewrite there would fail with "no such column".
    # If the source schema doesn't have the canonical column set, skip —
    # init_db() handles the create-from-scratch path for those.
    if not _column_exists(conn, "owned_item", "master_item_id"):
        return

    if conn.in_transaction:
        conn.commit()

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript(
            f"""
            BEGIN;
            DROP TABLE IF EXISTS owned_item_new;
            CREATE TABLE owned_item_new (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              master_item_id INTEGER,
              linked_album_master_id INTEGER,
              linked_artist_name TEXT,
              copy_group_key TEXT,
              category TEXT NOT NULL,
              domain_code TEXT CHECK (domain_code IN ('KOREA', 'JAPAN', 'GREATER_CHINA', 'WESTERN', 'OTHER_ASIA', 'WORLD_OTHER', 'UNKNOWN')),
              release_type TEXT CHECK (release_type IN ('ALBUM', 'EP', 'SINGLE')),
              item_name_override TEXT,
              quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
              is_second_hand INTEGER NOT NULL DEFAULT 0,
              size_group TEXT NOT NULL CHECK (size_group IN ('{_size_group_check_sql()}')),
              preferred_storage_size_group TEXT CHECK (preferred_storage_size_group IN ('{_size_group_check_sql()}')),
              status TEXT NOT NULL DEFAULT 'IN_COLLECTION' CHECK (status IN ('IN_COLLECTION', 'LOANED', 'SOLD', 'LOST', 'ARCHIVED')),
              condition_grade TEXT,
              signature_type TEXT NOT NULL DEFAULT 'NONE' CHECK (signature_type IN ('NONE', 'IN_PERSON', 'PURCHASE_INCLUDED', 'UNKNOWN')),
              source_code TEXT,
              source_external_id TEXT,
              signed_by TEXT,
              signed_at TEXT,
              acquisition_date TEXT,
              purchase_price REAL,
              currency_code TEXT,
              purchase_source TEXT,
              memory_note TEXT,
              display_rank INTEGER,
              order_key TEXT,
              storage_slot_id INTEGER,
              thickness_mm INTEGER,
              notes TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              CHECK (signature_type <> 'NONE' OR (signed_by IS NULL AND signed_at IS NULL)),
              FOREIGN KEY (linked_album_master_id) REFERENCES album_master(id) ON DELETE SET NULL,
              FOREIGN KEY (storage_slot_id) REFERENCES storage_slot(id)
            );
            INSERT INTO owned_item_new (
              id, master_item_id, linked_album_master_id, linked_artist_name, copy_group_key,
              category, domain_code, release_type, item_name_override, quantity,
              is_second_hand, size_group, preferred_storage_size_group, status, condition_grade, signature_type,
              source_code, source_external_id, signed_by, signed_at, acquisition_date,
              purchase_price, currency_code, purchase_source, memory_note, display_rank,
              order_key, storage_slot_id, thickness_mm, notes, created_at, updated_at
            )
            SELECT
              id, master_item_id, linked_album_master_id, linked_artist_name, copy_group_key,
              category, {_normalize_domain_code_sql("domain_code")}, release_type, item_name_override, quantity,
              is_second_hand, size_group, COALESCE(preferred_storage_size_group, size_group), status, condition_grade, signature_type,
              source_code, source_external_id, signed_by, signed_at, acquisition_date,
              purchase_price, currency_code, purchase_source, memory_note, display_rank,
              order_key, storage_slot_id, thickness_mm, notes, created_at, updated_at
            FROM owned_item;
            DROP TABLE owned_item;
            ALTER TABLE owned_item_new RENAME TO owned_item;
            COMMIT;
            """
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrate_owned_item_allow_extended_domains(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'owned_item'"
    ).fetchone()
    if not row or _owned_item_allows_extended_domains(conn):
        return
    # See the matching guard in `_migrate_owned_item_allow_goods` —
    # skip the rewrite when the source table is too minimal to copy.
    if not _column_exists(conn, "owned_item", "master_item_id"):
        return

    if conn.in_transaction:
        conn.commit()

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript(
            f"""
            BEGIN;
            DROP TABLE IF EXISTS owned_item_new;
            CREATE TABLE owned_item_new (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              master_item_id INTEGER,
              linked_album_master_id INTEGER,
              linked_artist_name TEXT,
              copy_group_key TEXT,
              category TEXT NOT NULL,
              domain_code TEXT CHECK (domain_code IN ('{_domain_code_check_sql()}')),
              release_type TEXT CHECK (release_type IN ('ALBUM', 'EP', 'SINGLE')),
              item_name_override TEXT,
              quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
              is_second_hand INTEGER NOT NULL DEFAULT 0,
              size_group TEXT NOT NULL CHECK (size_group IN ('{_size_group_check_sql()}')),
              preferred_storage_size_group TEXT CHECK (preferred_storage_size_group IN ('{_size_group_check_sql()}')),
              status TEXT NOT NULL DEFAULT 'IN_COLLECTION' CHECK (status IN ('IN_COLLECTION', 'LOANED', 'SOLD', 'LOST', 'ARCHIVED')),
              condition_grade TEXT,
              signature_type TEXT NOT NULL DEFAULT 'NONE' CHECK (signature_type IN ('NONE', 'IN_PERSON', 'PURCHASE_INCLUDED', 'UNKNOWN')),
              source_code TEXT,
              source_external_id TEXT,
              signed_by TEXT,
              signed_at TEXT,
              acquisition_date TEXT,
              purchase_price REAL,
              currency_code TEXT,
              purchase_source TEXT,
              memory_note TEXT,
              display_rank INTEGER,
              order_key TEXT,
              storage_slot_id INTEGER,
              thickness_mm INTEGER,
              notes TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              CHECK (signature_type <> 'NONE' OR (signed_by IS NULL AND signed_at IS NULL)),
              FOREIGN KEY (linked_album_master_id) REFERENCES album_master(id) ON DELETE SET NULL,
              FOREIGN KEY (storage_slot_id) REFERENCES storage_slot(id)
            );
            INSERT INTO owned_item_new (
              id, master_item_id, linked_album_master_id, linked_artist_name, copy_group_key,
              category, domain_code, release_type, item_name_override, quantity,
              is_second_hand, size_group, preferred_storage_size_group, status, condition_grade, signature_type,
              source_code, source_external_id, signed_by, signed_at, acquisition_date,
              purchase_price, currency_code, purchase_source, memory_note, display_rank,
              order_key, storage_slot_id, thickness_mm, notes, created_at, updated_at
            )
            SELECT
              id, master_item_id, linked_album_master_id, linked_artist_name, copy_group_key,
              category, {_normalize_domain_code_sql("domain_code")}, release_type, item_name_override, quantity,
              is_second_hand, size_group, COALESCE(preferred_storage_size_group, size_group), status, condition_grade, signature_type,
              source_code, source_external_id, signed_by, signed_at, acquisition_date,
              purchase_price, currency_code, purchase_source, memory_note, display_rank,
              order_key, storage_slot_id, thickness_mm, notes, created_at, updated_at
            FROM owned_item;
            DROP TABLE owned_item;
            ALTER TABLE owned_item_new RENAME TO owned_item;
            COMMIT;
            """
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


SCHEMA_VERSION = 2
"""Bump every time a NEW migration entry is added to `_MIGRATIONS_BY_VERSION`.

The legacy idempotent pass (`_apply_migrations`) is collapsed into version 1.
Future schema changes should be added as new functions, registered in the
dictionary below, and assigned the next integer.

Version log:
  1 — legacy idempotent pass (pre-versioning installs converge here).
  2 — `external_response_cache` table for persisted Discogs/MusicBrainz/
      Aladin/CoverArtArchive replies. See providers.cached_fetch_json.
"""


def _read_user_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("PRAGMA user_version").fetchone()
    if row is None:
        return 0
    try:
        return int(row[0])
    except (TypeError, ValueError):
        return 0


def _set_user_version(conn: sqlite3.Connection, value: int) -> None:
    # PRAGMA user_version doesn't accept bound parameters, so we coerce
    # `value` to int explicitly to keep the SQL injection surface zero.
    conn.execute(f"PRAGMA user_version = {int(value)}")


def _migration_v1_legacy_idempotent_pass(conn: sqlite3.Connection) -> None:
    """Pre-2026-04 schema convergence collapsed into version 1.

    Every install that lands here either:
      * was just initialised by `init_db()` (schema is current — these calls
        are no-ops), or
      * is an existing install upgrading past the version-tracking line —
        the idempotent ALTER/PRAGMA-table_info checks bring it forward.

    Once this runs, `user_version` is bumped to 1 and the slow per-boot
    inspection is skipped on every subsequent restart.
    """
    _apply_migrations_legacy(conn)
    _ensure_app_setting_table(conn)
    _ensure_recent_feed_indexes(conn)


def _migration_v2_add_external_response_cache(conn: sqlite3.Connection) -> None:
    """Create the persisted external-response cache surface.

    Stores Discogs/MusicBrainz/Aladin/CoverArtArchive bodies keyed by a
    SHA-256-prefixed `cache_key`. The TTL is enforced at read time
    (`expires_at` is a UTC ISO-8601 string), and a partial index over
    `expires_at` keeps the periodic purge query cheap even when the table
    grows past tens of thousands of entries.

    See `providers.cached_fetch_json` for the read/write contract.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS external_response_cache (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          cache_key TEXT NOT NULL UNIQUE,
          source_code TEXT NOT NULL,
          body_json TEXT NOT NULL,
          status_code INTEGER NOT NULL DEFAULT 200,
          fetched_at TEXT NOT NULL,
          expires_at TEXT,
          etag TEXT,
          last_modified TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_external_response_cache_expires "
        "ON external_response_cache (expires_at) WHERE expires_at IS NOT NULL"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_external_response_cache_source "
        "ON external_response_cache (source_code, fetched_at DESC)"
    )


_MIGRATIONS_BY_VERSION: dict[int, "Callable[[sqlite3.Connection], None]"] = {
    1: _migration_v1_legacy_idempotent_pass,
    2: _migration_v2_add_external_response_cache,
}


def _run_pending_migrations(conn: sqlite3.Connection) -> int:
    """Apply every migration whose version is greater than the DB's current
    `user_version`, in numeric order. Returns the number of migrations
    actually executed (0 if the DB was already at SCHEMA_VERSION).

    Each migration runs in its own implicit transaction provided by the
    connection's autocommit semantics (caller decides whether the wrapping
    `get_conn`/`get_write_conn` already opened a transaction).
    """
    current = _read_user_version(conn)
    if current >= SCHEMA_VERSION:
        return 0
    applied = 0
    for version in sorted(_MIGRATIONS_BY_VERSION):
        if version <= current:
            continue
        if version > SCHEMA_VERSION:
            break
        _MIGRATIONS_BY_VERSION[version](conn)
        _set_user_version(conn, version)
        applied += 1
    return applied


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """Public entry point — defers to the version-aware runner.

    Existing call sites (`init_db`, `ensure_startup_db_ready`) keep using
    this name; the version short-circuit means second-and-later boots stop
    paying for the 60+ idempotent PRAGMA checks.
    """
    _run_pending_migrations(conn)


def _apply_migrations_legacy(conn: sqlite3.Connection) -> None:
    _migrate_album_master_allow_manual(conn)
    _ensure_album_master_external_ref_table(conn)
    _ensure_album_master_merge_history_table(conn)
    _ensure_purchase_import_queue_table(conn)
    _migrate_purchase_import_queue_allow_file_upload(conn)
    _migrate_storage_slot_allow_goods(conn)
    _migrate_owned_item_allow_goods(conn)
    _migrate_owned_item_allow_extended_domains(conn)

    # Wrap the ALTER TABLE block on a table-exists check. `_column_exists`
    # returns False for both missing-column AND missing-table; the latter
    # would fail the ALTER, which is a problem when test fixtures create a
    # minimal subset of the schema.
    if _table_exists(conn, "album_master"):
        if not _column_exists(conn, "album_master", "domain_code"):
            conn.execute(
                f"ALTER TABLE album_master ADD COLUMN domain_code TEXT CHECK (domain_code IN ('{_domain_code_check_sql()}'))"
            )
        if not _column_exists(conn, "album_master", "sort_artist_name"):
            conn.execute("ALTER TABLE album_master ADD COLUMN sort_artist_name TEXT")
        if not _column_exists(conn, "album_master", "source_domain_code"):
            conn.execute(
                f"ALTER TABLE album_master ADD COLUMN source_domain_code TEXT CHECK (source_domain_code IN ('{_domain_code_check_sql()}'))"
            )
        if not _column_exists(conn, "album_master", "source_release_year"):
            conn.execute("ALTER TABLE album_master ADD COLUMN source_release_year INTEGER")
        if not _column_exists(conn, "album_master", "override_domain_code"):
            conn.execute(
                f"ALTER TABLE album_master ADD COLUMN override_domain_code TEXT CHECK (override_domain_code IN ('{_domain_code_check_sql()}'))"
            )
        if not _column_exists(conn, "album_master", "override_release_year"):
            conn.execute("ALTER TABLE album_master ADD COLUMN override_release_year INTEGER")
        if not _column_exists(conn, "album_master", "override_note"):
            conn.execute("ALTER TABLE album_master ADD COLUMN override_note TEXT")
    if _column_exists(conn, "album_master", "sort_artist_name"):
        conn.execute(
            """
            UPDATE album_master
            SET sort_artist_name = NULL
            WHERE sort_artist_name IS NOT NULL
              AND TRIM(sort_artist_name) = ''
            """
        )
        conn.execute(
            """
            UPDATE album_master AS am
            SET sort_artist_name = (
              SELECT oi.linked_artist_name
              FROM album_master_member amm
              JOIN owned_item oi ON oi.id = amm.owned_item_id
              WHERE amm.album_master_id = am.id
                AND oi.linked_artist_name IS NOT NULL
                AND TRIM(oi.linked_artist_name) <> ''
              GROUP BY oi.linked_artist_name
              ORDER BY COUNT(*) DESC, oi.linked_artist_name ASC
              LIMIT 1
            )
            WHERE am.sort_artist_name IS NULL
               OR TRIM(am.sort_artist_name) = ''
            """
        )
    if _column_exists(conn, "album_master", "domain_code"):
        conn.execute(
            f"""
            UPDATE album_master
            SET domain_code = {_normalize_domain_code_sql("domain_code")}
            WHERE domain_code IS NOT NULL
              AND TRIM(domain_code) <> ''
            """
        )
        conn.execute(
            """
            UPDATE album_master AS am
            SET domain_code = (
              SELECT oi.domain_code
              FROM album_master_member amm
              JOIN owned_item oi ON oi.id = amm.owned_item_id
              WHERE amm.album_master_id = am.id
                AND oi.domain_code IS NOT NULL
                AND TRIM(oi.domain_code) <> ''
              GROUP BY oi.domain_code
              ORDER BY COUNT(*) DESC, oi.domain_code ASC
              LIMIT 1
            )
            WHERE am.domain_code IS NULL OR TRIM(am.domain_code) = ''
            """
        )
    if _column_exists(conn, "album_master", "source_domain_code"):
        conn.execute(
            f"""
            UPDATE album_master
            SET source_domain_code = {_normalize_domain_code_sql("source_domain_code")}
            WHERE source_domain_code IS NOT NULL
              AND TRIM(source_domain_code) <> ''
            """
        )
        conn.execute(
            """
            UPDATE album_master
            SET source_domain_code = domain_code
            WHERE source_domain_code IS NULL
               OR TRIM(source_domain_code) = ''
            """
        )
    if _column_exists(conn, "album_master", "source_release_year"):
        conn.execute(
            """
            UPDATE album_master
            SET source_release_year = release_year
            WHERE source_release_year IS NULL
            """
        )
    if _column_exists(conn, "album_master", "override_domain_code"):
        conn.execute(
            f"""
            UPDATE album_master
            SET override_domain_code = {_normalize_domain_code_sql("override_domain_code")}
            WHERE override_domain_code IS NOT NULL
              AND TRIM(override_domain_code) <> ''
            """
        )
        conn.execute(
            """
            UPDATE album_master
            SET override_domain_code = NULL
            WHERE override_domain_code IS NOT NULL
              AND TRIM(override_domain_code) = ''
            """
        )
    if _column_exists(conn, "album_master", "override_note"):
        conn.execute(
            """
            UPDATE album_master
            SET override_note = NULL
            WHERE override_note IS NOT NULL
              AND TRIM(override_note) = ''
            """
        )

    if not _column_exists(conn, "owned_item", "is_second_hand"):
        conn.execute(
            "ALTER TABLE owned_item ADD COLUMN is_second_hand INTEGER NOT NULL DEFAULT 0"
        )
    if not _column_exists(conn, "owned_item", "source_code"):
        conn.execute("ALTER TABLE owned_item ADD COLUMN source_code TEXT")
    if not _column_exists(conn, "owned_item", "source_external_id"):
        conn.execute("ALTER TABLE owned_item ADD COLUMN source_external_id TEXT")
    if not _column_exists(conn, "owned_item", "domain_code"):
        conn.execute(
            f"ALTER TABLE owned_item ADD COLUMN domain_code TEXT CHECK (domain_code IN ('{_domain_code_check_sql()}'))"
        )
    if _column_exists(conn, "owned_item", "domain_code"):
        conn.execute(
            f"""
            UPDATE owned_item
            SET domain_code = {_normalize_domain_code_sql("domain_code")}
            WHERE domain_code IS NOT NULL
              AND TRIM(domain_code) <> ''
            """
        )
    if not _column_exists(conn, "owned_item", "release_type"):
        conn.execute(
            "ALTER TABLE owned_item ADD COLUMN release_type TEXT CHECK (release_type IN ('ALBUM', 'EP', 'SINGLE'))"
        )
    if not _column_exists(conn, "owned_item", "linked_album_master_id"):
        conn.execute("ALTER TABLE owned_item ADD COLUMN linked_album_master_id INTEGER")
    if not _column_exists(conn, "owned_item", "linked_artist_name"):
        conn.execute("ALTER TABLE owned_item ADD COLUMN linked_artist_name TEXT")
    if not _column_exists(conn, "owned_item", "copy_group_key"):
        conn.execute("ALTER TABLE owned_item ADD COLUMN copy_group_key TEXT")
    if not _column_exists(conn, "owned_item", "order_key"):
        conn.execute("ALTER TABLE owned_item ADD COLUMN order_key TEXT")
    if not _column_exists(conn, "owned_item", "preferred_storage_size_group"):
        conn.execute(
            f"ALTER TABLE owned_item ADD COLUMN preferred_storage_size_group TEXT CHECK (preferred_storage_size_group IN ('{_size_group_check_sql()}'))"
        )
    if _column_exists(conn, "owned_item", "preferred_storage_size_group") and _column_exists(
        conn, "owned_item", "size_group"
    ):
        conn.execute(
            """
            UPDATE owned_item
            SET preferred_storage_size_group = size_group
            WHERE preferred_storage_size_group IS NULL OR TRIM(preferred_storage_size_group) = ''
            """
        )
    if _column_exists(conn, "owned_item", "source_code") and _column_exists(conn, "owned_item", "source_external_id"):
        conn.execute("CREATE INDEX IF NOT EXISTS idx_owned_item_source ON owned_item (source_code, source_external_id)")
    if _column_exists(conn, "owned_item", "order_key"):
        conn.execute("CREATE INDEX IF NOT EXISTS idx_owned_item_order_key ON owned_item (order_key)")
    if _column_exists(conn, "owned_item", "copy_group_key"):
        conn.execute("CREATE INDEX IF NOT EXISTS idx_owned_item_copy_group ON owned_item (copy_group_key)")
    if _column_exists(conn, "owned_item", "domain_code"):
        conn.execute("CREATE INDEX IF NOT EXISTS idx_owned_item_domain ON owned_item (domain_code)")
    if _column_exists(conn, "owned_item", "release_type"):
        conn.execute("CREATE INDEX IF NOT EXISTS idx_owned_item_release_type ON owned_item (release_type)")
    if _column_exists(conn, "owned_item", "linked_album_master_id"):
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_owned_item_linked_album_master ON owned_item (linked_album_master_id)"
        )
    _ensure_recent_feed_indexes(conn)
    if _column_exists(conn, "album_master", "domain_code"):
        conn.execute("CREATE INDEX IF NOT EXISTS idx_album_master_domain ON album_master (domain_code)")
    _backfill_album_master_external_refs(conn)

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS classification_option (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          option_group TEXT NOT NULL CHECK (option_group IN ('SUBTYPE', 'SOUNDTRACK')),
          label TEXT NOT NULL,
          sort_order INTEGER NOT NULL DEFAULT 100,
          is_active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE (option_group, label)
        );

        CREATE TABLE IF NOT EXISTS owned_item_subtype (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          owned_item_id INTEGER NOT NULL,
          option_id INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          UNIQUE (owned_item_id, option_id),
          FOREIGN KEY (owned_item_id) REFERENCES owned_item(id) ON DELETE CASCADE,
          FOREIGN KEY (option_id) REFERENCES classification_option(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS owned_item_soundtrack (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          owned_item_id INTEGER NOT NULL,
          option_id INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          UNIQUE (owned_item_id, option_id),
          FOREIGN KEY (owned_item_id) REFERENCES owned_item(id) ON DELETE CASCADE,
          FOREIGN KEY (option_id) REFERENCES classification_option(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_classification_option_group ON classification_option (option_group, is_active, sort_order, label);
        CREATE INDEX IF NOT EXISTS idx_owned_item_subtype_owned ON owned_item_subtype (owned_item_id);
        CREATE INDEX IF NOT EXISTS idx_owned_item_soundtrack_owned ON owned_item_soundtrack (owned_item_id);
        """
    )

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS cabinet_camera (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          cabinet_name TEXT NOT NULL UNIQUE,
          camera_name TEXT NOT NULL,
          onvif_device_url TEXT,
          snapshot_url TEXT,
          stream_url TEXT,
          username TEXT,
          password TEXT,
          notes TEXT,
          is_active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_cabinet_camera_active ON cabinet_camera (is_active, cabinet_name);
        """
    )
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS goods_item_detail (
          owned_item_id INTEGER PRIMARY KEY,
          image_urls_json TEXT,
          primary_image_url TEXT,
          poster_storage_spec TEXT,
          tshirt_size TEXT,
          cup_material TEXT,
          hat_size TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY (owned_item_id) REFERENCES owned_item(id) ON DELETE CASCADE
        );
        """
    )
    conn.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS goods_item (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          category TEXT NOT NULL CHECK (category IN ('{_goods_category_check_sql()}')),
          goods_name TEXT NOT NULL,
          description TEXT,
          quantity INTEGER NOT NULL DEFAULT 1,
          size_group TEXT NOT NULL DEFAULT 'GOODS' CHECK (size_group IN ('{_size_group_check_sql()}')),
          storage_slot_id INTEGER,
          status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('{_goods_status_check_sql()}')),
          domain_code TEXT CHECK (domain_code IN ('{_domain_code_check_sql()}')),
          memory_note TEXT,
          image_urls_json TEXT NOT NULL DEFAULT '[]',
          primary_image_url TEXT,
          poster_storage_spec TEXT,
          tshirt_size TEXT,
          cup_material TEXT,
          hat_size TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY (storage_slot_id) REFERENCES storage_slot(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS goods_item_album_master_map (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          goods_item_id INTEGER NOT NULL,
          album_master_id INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          UNIQUE (goods_item_id, album_master_id),
          FOREIGN KEY (goods_item_id) REFERENCES goods_item(id) ON DELETE CASCADE,
          FOREIGN KEY (album_master_id) REFERENCES album_master(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS goods_item_artist_map (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          goods_item_id INTEGER NOT NULL,
          artist_name TEXT NOT NULL,
          normalized_artist_name TEXT NOT NULL,
          created_at TEXT NOT NULL,
          UNIQUE (goods_item_id, normalized_artist_name),
          FOREIGN KEY (goods_item_id) REFERENCES goods_item(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS goods_item_label_map (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          goods_item_id INTEGER NOT NULL,
          label_name TEXT NOT NULL,
          normalized_label_name TEXT NOT NULL,
          created_at TEXT NOT NULL,
          UNIQUE (goods_item_id, normalized_label_name),
          FOREIGN KEY (goods_item_id) REFERENCES goods_item(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS goods_item_collectible_relation (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          goods_item_id INTEGER NOT NULL,
          relation_type TEXT NOT NULL CHECK (relation_type IN ('{_goods_relation_type_check_sql()}')),
          linked_goods_item_id INTEGER NOT NULL,
          note TEXT,
          display_order INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE (goods_item_id, relation_type, linked_goods_item_id),
          FOREIGN KEY (goods_item_id) REFERENCES goods_item(id) ON DELETE CASCADE,
          FOREIGN KEY (linked_goods_item_id) REFERENCES goods_item(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_goods_item_category_name ON goods_item (category, goods_name);
        CREATE INDEX IF NOT EXISTS idx_goods_item_storage_slot ON goods_item (storage_slot_id, status);
        CREATE INDEX IF NOT EXISTS idx_goods_item_album_master_map_goods ON goods_item_album_master_map (goods_item_id, album_master_id);
        CREATE INDEX IF NOT EXISTS idx_goods_item_artist_map_lookup ON goods_item_artist_map (normalized_artist_name);
        CREATE INDEX IF NOT EXISTS idx_goods_item_label_map_lookup ON goods_item_label_map (normalized_label_name);
        CREATE INDEX IF NOT EXISTS idx_goods_item_collectible_relation_goods ON goods_item_collectible_relation (goods_item_id, display_order, id);
        CREATE INDEX IF NOT EXISTS idx_goods_item_collectible_relation_linked ON goods_item_collectible_relation (linked_goods_item_id);
        """
    )
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS owned_item_location_event (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          owned_item_id INTEGER NOT NULL,
          from_storage_slot_id INTEGER,
          from_slot_code TEXT,
          from_slot_display_name TEXT,
          to_storage_slot_id INTEGER,
          to_slot_code TEXT,
          to_slot_display_name TEXT,
          movement_kind TEXT NOT NULL CHECK (movement_kind IN ('INITIAL_ASSIGN', 'ASSIGN', 'MOVE', 'UNASSIGN', 'CABINET_DELETE')),
          note TEXT,
          created_at TEXT NOT NULL,
          FOREIGN KEY (owned_item_id) REFERENCES owned_item(id) ON DELETE CASCADE
        );
        """
    )
    # The INDEX statements below reference columns that may not exist on
    # an older / minimal location-event table — `CREATE TABLE IF NOT
    # EXISTS` above is a no-op when the table already exists, so we have
    # to gate each index on the column it sorts by.
    if _column_exists(conn, "owned_item_location_event", "owned_item_id") and _column_exists(
        conn, "owned_item_location_event", "created_at"
    ):
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_owned_item_location_event_owned "
            "ON owned_item_location_event (owned_item_id, created_at DESC)"
        )
    if _column_exists(conn, "owned_item_location_event", "from_slot_code") and _column_exists(
        conn, "owned_item_location_event", "created_at"
    ):
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_owned_item_location_event_from_slot "
            "ON owned_item_location_event (from_slot_code, created_at DESC)"
        )
    if _column_exists(conn, "owned_item_location_event", "to_slot_code") and _column_exists(
        conn, "owned_item_location_event", "created_at"
    ):
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_owned_item_location_event_to_slot "
            "ON owned_item_location_event (to_slot_code, created_at DESC)"
        )
    if not _column_exists(conn, "storage_slot", "cabinet_name"):
        conn.execute("ALTER TABLE storage_slot ADD COLUMN cabinet_name TEXT")
    if not _column_exists(conn, "storage_slot", "column_code"):
        conn.execute("ALTER TABLE storage_slot ADD COLUMN column_code TEXT")
    if not _column_exists(conn, "storage_slot", "cell_code"):
        conn.execute("ALTER TABLE storage_slot ADD COLUMN cell_code TEXT")
    if not _column_exists(conn, "storage_slot", "cabinet_sort_policy"):
        conn.execute(
            f"ALTER TABLE storage_slot ADD COLUMN cabinet_sort_policy TEXT NOT NULL DEFAULT 'ARTIST_RELEASE_TITLE' CHECK (cabinet_sort_policy IN ('{_cabinet_sort_policy_check_sql()}'))"
        )
    if not _column_exists(conn, "storage_slot", "cabinet_domain_code"):
        conn.execute(
            f"ALTER TABLE storage_slot ADD COLUMN cabinet_domain_code TEXT CHECK (cabinet_domain_code IN ('{_domain_code_check_sql()}'))"
        )
    if not _column_exists(conn, "storage_slot", "max_thickness_mm"):
        conn.execute("ALTER TABLE storage_slot ADD COLUMN max_thickness_mm INTEGER")
    if not _column_exists(conn, "storage_slot", "cabinet_group_name"):
        conn.execute("ALTER TABLE storage_slot ADD COLUMN cabinet_group_name TEXT")
    if not _column_exists(conn, "storage_slot", "cabinet_group_order"):
        conn.execute("ALTER TABLE storage_slot ADD COLUMN cabinet_group_order INTEGER")
    conn.execute(
        """
        UPDATE storage_slot
        SET cabinet_sort_policy = 'ARTIST_RELEASE_TITLE'
        WHERE cabinet_sort_policy IS NULL
           OR TRIM(cabinet_sort_policy) = ''
           OR UPPER(TRIM(cabinet_sort_policy)) NOT IN ('ARTIST_RELEASE_TITLE', 'LABEL_ID')
        """
    )
    rows = conn.execute(
        """
        SELECT id, slot_code, allowed_size_group, is_overflow_zone, cabinet_name, column_code, cell_code
        FROM storage_slot
        """
    ).fetchall()
    for row in rows:
        if row["cabinet_name"] and (row["column_code"] is not None or row["cell_code"] is not None):
            continue
        cabinet_name, column_code, cell_code = _derive_storage_slot_parts(
            slot_code=str(row["slot_code"] or ""),
            allowed_size_group=str(row["allowed_size_group"] or ""),
            is_overflow_zone=bool(row["is_overflow_zone"]),
        )
        conn.execute(
            """
            UPDATE storage_slot
            SET cabinet_name = ?, column_code = ?, cell_code = ?, updated_at = ?
            WHERE id = ?
            """,
            (cabinet_name, column_code, cell_code, utc_now_iso(), int(row["id"])),
        )
    if not _column_exists(conn, "goods_item_detail", "image_urls_json"):
        conn.execute("ALTER TABLE goods_item_detail ADD COLUMN image_urls_json TEXT")
    if not _column_exists(conn, "goods_item_detail", "primary_image_url"):
        conn.execute("ALTER TABLE goods_item_detail ADD COLUMN primary_image_url TEXT")
    if not _column_exists(conn, "goods_item_detail", "poster_storage_spec"):
        conn.execute("ALTER TABLE goods_item_detail ADD COLUMN poster_storage_spec TEXT")
    if not _column_exists(conn, "goods_item_detail", "tshirt_size"):
        conn.execute("ALTER TABLE goods_item_detail ADD COLUMN tshirt_size TEXT")
    if not _column_exists(conn, "goods_item_detail", "cup_material"):
        conn.execute("ALTER TABLE goods_item_detail ADD COLUMN cup_material TEXT")
    if not _column_exists(conn, "goods_item_detail", "hat_size"):
        conn.execute("ALTER TABLE goods_item_detail ADD COLUMN hat_size TEXT")
    if not _column_exists(conn, "goods_item_detail", "created_at"):
        conn.execute("ALTER TABLE goods_item_detail ADD COLUMN created_at TEXT")
    if not _column_exists(conn, "goods_item_detail", "updated_at"):
        conn.execute("ALTER TABLE goods_item_detail ADD COLUMN updated_at TEXT")
    conn.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS goods_item_collectible_relation (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          goods_item_id INTEGER NOT NULL,
          relation_type TEXT NOT NULL CHECK (relation_type IN ('{_goods_relation_type_check_sql()}')),
          linked_goods_item_id INTEGER NOT NULL,
          note TEXT,
          display_order INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE (goods_item_id, relation_type, linked_goods_item_id),
          FOREIGN KEY (goods_item_id) REFERENCES goods_item(id) ON DELETE CASCADE,
          FOREIGN KEY (linked_goods_item_id) REFERENCES goods_item(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_goods_item_collectible_relation_goods ON goods_item_collectible_relation (goods_item_id, display_order, id);
        CREATE INDEX IF NOT EXISTS idx_goods_item_collectible_relation_linked ON goods_item_collectible_relation (linked_goods_item_id);
        """
    )

    if not _column_exists(conn, "music_item_detail", "label_name"):
        conn.execute("ALTER TABLE music_item_detail ADD COLUMN label_name TEXT")
    if not _column_exists(conn, "music_item_detail", "catalog_no"):
        conn.execute("ALTER TABLE music_item_detail ADD COLUMN catalog_no TEXT")
    if not _column_exists(conn, "music_item_detail", "cover_image_url"):
        conn.execute("ALTER TABLE music_item_detail ADD COLUMN cover_image_url TEXT")
    if not _column_exists(conn, "music_item_detail", "track_list_json"):
        conn.execute("ALTER TABLE music_item_detail ADD COLUMN track_list_json TEXT")
    if not _column_exists(conn, "music_item_detail", "media_type"):
        conn.execute("ALTER TABLE music_item_detail ADD COLUMN media_type TEXT")
    if not _column_exists(conn, "music_item_detail", "genres_json"):
        conn.execute("ALTER TABLE music_item_detail ADD COLUMN genres_json TEXT")
    if not _column_exists(conn, "music_item_detail", "styles_json"):
        conn.execute("ALTER TABLE music_item_detail ADD COLUMN styles_json TEXT")
    if not _column_exists(conn, "music_item_detail", "artist_or_brand"):
        conn.execute("ALTER TABLE music_item_detail ADD COLUMN artist_or_brand TEXT")
    if not _column_exists(conn, "music_item_detail", "release_year"):
        conn.execute("ALTER TABLE music_item_detail ADD COLUMN release_year INTEGER")
    if not _column_exists(conn, "music_item_detail", "released_date"):
        conn.execute("ALTER TABLE music_item_detail ADD COLUMN released_date TEXT")
    if not _column_exists(conn, "music_item_detail", "barcode"):
        conn.execute("ALTER TABLE music_item_detail ADD COLUMN barcode TEXT")
    if not _column_exists(conn, "music_item_detail", "runout_matrix_json"):
        conn.execute("ALTER TABLE music_item_detail ADD COLUMN runout_matrix_json TEXT")
    if not _column_exists(conn, "music_item_detail", "source_notes"):
        conn.execute("ALTER TABLE music_item_detail ADD COLUMN source_notes TEXT")
    if not _column_exists(conn, "music_item_detail", "credits_json"):
        conn.execute("ALTER TABLE music_item_detail ADD COLUMN credits_json TEXT")
    if not _column_exists(conn, "music_item_detail", "identifier_items_json"):
        conn.execute("ALTER TABLE music_item_detail ADD COLUMN identifier_items_json TEXT")
    if not _column_exists(conn, "music_item_detail", "image_items_json"):
        conn.execute("ALTER TABLE music_item_detail ADD COLUMN image_items_json TEXT")
    if not _column_exists(conn, "music_item_detail", "company_items_json"):
        conn.execute("ALTER TABLE music_item_detail ADD COLUMN company_items_json TEXT")
    if not _column_exists(conn, "music_item_detail", "series_json"):
        conn.execute("ALTER TABLE music_item_detail ADD COLUMN series_json TEXT")
    if not _column_exists(conn, "music_item_detail", "format_items_json"):
        conn.execute("ALTER TABLE music_item_detail ADD COLUMN format_items_json TEXT")
    if not _column_exists(conn, "music_item_detail", "track_items_json"):
        conn.execute("ALTER TABLE music_item_detail ADD COLUMN track_items_json TEXT")
    if not _column_exists(conn, "music_item_detail", "label_items_json"):
        conn.execute("ALTER TABLE music_item_detail ADD COLUMN label_items_json TEXT")

    _migrate_music_item_detail_allow_extended_formats(conn)

    _backfill_order_keys(conn)


def _next_order_key_in_conn(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        """
        SELECT order_key
        FROM owned_item
        WHERE order_key IS NOT NULL
          AND TRIM(order_key) <> ''
        ORDER BY order_key DESC
        LIMIT 1
        """
    ).fetchone()
    value = _parse_order_value(row["order_key"]) if row else None
    base = value if value is not None else 0
    return _format_order_value(base + ORDER_KEY_STEP)


def _backfill_order_keys(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT id
        FROM owned_item
        WHERE status = 'IN_COLLECTION'
          AND (order_key IS NULL OR TRIM(order_key) = '')
        ORDER BY
          CASE WHEN display_rank IS NULL THEN 1 ELSE 0 END,
          display_rank ASC,
          created_at ASC,
          id ASC
        """
    ).fetchall()
    if not rows:
        return

    next_key = _next_order_key_in_conn(conn)
    next_value = _parse_order_value(next_key)
    if next_value is None:
        next_value = ORDER_KEY_STEP

    now = utc_now_iso()
    for row in rows:
        conn.execute(
            """
            UPDATE owned_item
            SET order_key = ?, updated_at = ?
            WHERE id = ?
            """,
            (_format_order_value(next_value), now, int(row["id"])),
        )
        next_value += ORDER_KEY_STEP


def _compute_between_order_value(left: int | None, right: int | None) -> int | None:
    if left is None and right is None:
        return ORDER_KEY_STEP
    if left is None:
        if right is None:
            return ORDER_KEY_STEP
        candidate = right // 2
        if candidate <= 0 or candidate >= right:
            return None
        return candidate
    if right is None:
        return left + ORDER_KEY_STEP
    gap = right - left
    if gap <= 1:
        return None
    return left + (gap // 2)


def _rebalance_in_collection_order(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT id
        FROM owned_item
        WHERE status = 'IN_COLLECTION'
        ORDER BY
          CASE WHEN order_key IS NULL OR TRIM(order_key) = '' THEN 1 ELSE 0 END,
          order_key ASC,
          CASE WHEN display_rank IS NULL THEN 1 ELSE 0 END,
          display_rank ASC,
          created_at ASC,
          id ASC
        """
    ).fetchall()
    now = utc_now_iso()
    value = 0
    for row in rows:
        value += ORDER_KEY_STEP
        conn.execute(
            """
            UPDATE owned_item
            SET order_key = ?, updated_at = ?
            WHERE id = ?
            """,
            (_format_order_value(value), now, int(row["id"])),
        )


def resequence_in_collection_order() -> dict[str, int]:
    with get_conn() as conn:
        slot_rows = conn.execute(
            """
            SELECT DISTINCT ss.*
            FROM storage_slot ss
            JOIN owned_item oi ON oi.storage_slot_id = ss.id
            WHERE oi.status = 'IN_COLLECTION'
              AND oi.storage_slot_id IS NOT NULL
            """
        ).fetchall()
        slot_dicts = [dict(row) for row in slot_rows]
        slot_dicts.sort(key=_storage_slot_sort_key)

        ordered_ids: list[int] = []
        for slot in slot_dicts:
            rows = list_owned_items_for_storage_slot(int(slot["id"]))
            ordered_ids.extend(int(row["id"]) for row in rows if int(row.get("id") or 0) > 0)

        unassigned_rows = conn.execute(
            """
            SELECT id
            FROM owned_item
            WHERE status = 'IN_COLLECTION'
              AND storage_slot_id IS NULL
            ORDER BY
              CASE WHEN order_key IS NULL OR TRIM(order_key) = '' THEN 1 ELSE 0 END,
              order_key ASC,
              id ASC
            """
        ).fetchall()
        ordered_ids.extend(int(row["id"]) for row in unassigned_rows if int(row["id"] or 0) > 0)

        now = utc_now_iso()
        value = 0
        for owned_item_id in ordered_ids:
            value += ORDER_KEY_STEP
            conn.execute(
                """
                UPDATE owned_item
                SET order_key = ?, updated_at = ?
                WHERE id = ?
                """,
                (_format_order_value(value), now, owned_item_id),
            )

    return {
        "reordered_count": len(ordered_ids),
        "assigned_slot_count": len(slot_dicts),
        "unassigned_tail_count": len(unassigned_rows),
    }


def _seed_metadata_sources(conn: sqlite3.Connection) -> None:
    now = utc_now_iso()
    rows = [
        ("DISCOGS", "Discogs", "GLOBAL", 1, 10, 1, now, now),
        ("MANIADB", "ManiaDB", "KR", 0, 15, 1, now, now),
        ("ALADIN", "Aladin", "KR", 0, 18, 1, now, now),
        ("MUSICBRAINZ", "MusicBrainz", "GLOBAL", 0, 20, 1, now, now),
        ("INTERNAL_KR", "Internal KR Curation", "KR", 0, 90, 1, now, now),
    ]
    conn.executemany(
        """
        INSERT INTO metadata_source
          (source_code, source_name, source_scope, is_primary, priority, enabled, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_code) DO UPDATE SET
          source_name = excluded.source_name,
          source_scope = excluded.source_scope,
          is_primary = excluded.is_primary,
          priority = excluded.priority,
          enabled = excluded.enabled,
          updated_at = excluded.updated_at
        """,
        rows,
    )


# Purchase-import queue CRUD (insert/find_duplicate/list/has_for_source_ref/
# count/get/update) lives in app.db.purchase_import and is re-exported at
# the bottom of this module.


def insert_owned_item(payload: dict[str, Any]) -> int:
    now = utc_now_iso()
    status = str(payload.get("status") or "IN_COLLECTION")
    order_key = payload.get("order_key")
    initial_storage_slot_id = payload.get("storage_slot_id")
    with get_conn() as conn:
        if status == "IN_COLLECTION":
            if not str(order_key or "").strip():
                _backfill_order_keys(conn)
                order_key = _next_order_key_in_conn(conn)
            else:
                order_key = str(order_key).strip()
        else:
            order_key = None

        cur = conn.execute(
            """
            INSERT INTO owned_item (
              master_item_id, linked_album_master_id, linked_artist_name, copy_group_key, category, domain_code, release_type, item_name_override, quantity, is_second_hand, size_group, preferred_storage_size_group, status,
              condition_grade, signature_type, source_code, source_external_id, signed_by, signed_at, acquisition_date,
              purchase_price, currency_code, purchase_source, memory_note, display_rank, order_key,
              storage_slot_id, thickness_mm, notes, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("master_item_id"),
                payload.get("linked_album_master_id"),
                payload.get("linked_artist_name"),
                payload.get("copy_group_key"),
                payload["category"],
                payload.get("domain_code"),
                payload.get("release_type"),
                payload.get("item_name_override"),
                payload["quantity"],
                1 if payload.get("is_second_hand") else 0,
                payload["size_group"],
                payload.get("preferred_storage_size_group") or payload["size_group"],
                payload.get("status", "IN_COLLECTION"),
                payload.get("condition_grade"),
                payload.get("signature_type", "NONE"),
                payload.get("source_code"),
                payload.get("source_external_id"),
                payload.get("signed_by"),
                payload.get("signed_at"),
                payload.get("acquisition_date"),
                payload.get("purchase_price"),
                payload.get("currency_code"),
                payload.get("purchase_source"),
                payload.get("memory_note"),
                payload.get("display_rank"),
                order_key,
                payload.get("storage_slot_id"),
                payload.get("thickness_mm"),
                payload.get("notes"),
                now,
                now,
            ),
        )
        owned_item_id = int(cur.lastrowid)

        _sync_owned_item_classifications_in_conn(
            conn,
            owned_item_id=owned_item_id,
            subtype_option_ids=payload.get("subtype_option_ids") or [],
            soundtrack_option_ids=payload.get("soundtrack_option_ids") or [],
            now=now,
        )

        music_detail = payload.get("music_detail")
        if music_detail:
            _upsert_music_item_detail_in_conn(conn, owned_item_id=owned_item_id, music_detail=music_detail, now=now)
        goods_detail = payload.get("goods_detail")
        if goods_detail:
            _upsert_goods_item_detail_in_conn(conn, owned_item_id=owned_item_id, goods_detail=goods_detail, now=now)

        if initial_storage_slot_id is not None:
            _log_owned_item_location_event_in_conn(
                conn,
                owned_item_id=owned_item_id,
                from_storage_slot_id=None,
                to_storage_slot_id=int(initial_storage_slot_id),
                now=now,
                is_create=True,
            )

    return owned_item_id


def _upsert_music_item_detail_in_conn(
    conn: sqlite3.Connection,
    owned_item_id: int,
    music_detail: dict[str, Any],
    now: str | None = None,
) -> None:
    timestamp = now or utc_now_iso()
    disc_condition = music_detail.get("disc_condition") or music_detail.get("media_condition")
    cover_condition = music_detail.get("cover_condition") or music_detail.get("sleeve_condition")
    has_obi_raw = music_detail.get("has_obi")
    has_obi_db: int | None = None
    if isinstance(has_obi_raw, bool):
        has_obi_db = 1 if has_obi_raw else None
    elif has_obi_raw in {0, 1}:
        has_obi_db = 1 if int(has_obi_raw) == 1 else None
    elif isinstance(has_obi_raw, str):
        lowered = has_obi_raw.strip().lower()
        if lowered in {"1", "true", "yes", "y"}:
            has_obi_db = 1
    runout_matrix_values_raw = music_detail.get("runout_matrix")
    if isinstance(runout_matrix_values_raw, list):
        runout_matrix_values = [str(v).strip() for v in runout_matrix_values_raw if str(v).strip()]
    elif runout_matrix_values_raw is None:
        runout_matrix_values = []
    else:
        text = str(runout_matrix_values_raw).strip()
        runout_matrix_values = [p.strip() for p in text.split("|") if p.strip()] if text else []
    runout_matrix_legacy = " | ".join(runout_matrix_values) if runout_matrix_values else None
    conn.execute(
        """
        INSERT INTO music_item_detail (
          owned_item_id, format_name, is_promotional_not_for_sale,
          artist_or_brand, release_year, released_date, barcode,
          label_name, catalog_no, cover_image_url, track_list_json,
          media_type, genres_json, styles_json,
          media_condition, sleeve_condition, disc_count, speed_rpm,
          has_obi, runout_matrix, runout_matrix_json, pressing_country,
          source_notes, credits_json, identifier_items_json, image_items_json,
          company_items_json, series_json, format_items_json, track_items_json,
          label_items_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(owned_item_id) DO UPDATE SET
          format_name = excluded.format_name,
          is_promotional_not_for_sale = excluded.is_promotional_not_for_sale,
          artist_or_brand = excluded.artist_or_brand,
          release_year = excluded.release_year,
          released_date = excluded.released_date,
          barcode = excluded.barcode,
          label_name = excluded.label_name,
          catalog_no = excluded.catalog_no,
          cover_image_url = excluded.cover_image_url,
          track_list_json = excluded.track_list_json,
          media_type = excluded.media_type,
          genres_json = excluded.genres_json,
          styles_json = excluded.styles_json,
          media_condition = excluded.media_condition,
          sleeve_condition = excluded.sleeve_condition,
          disc_count = excluded.disc_count,
          speed_rpm = excluded.speed_rpm,
          has_obi = excluded.has_obi,
          runout_matrix = excluded.runout_matrix,
          runout_matrix_json = excluded.runout_matrix_json,
          pressing_country = excluded.pressing_country,
          source_notes = excluded.source_notes,
          credits_json = excluded.credits_json,
          identifier_items_json = excluded.identifier_items_json,
          image_items_json = excluded.image_items_json,
          company_items_json = excluded.company_items_json,
          series_json = excluded.series_json,
          format_items_json = excluded.format_items_json,
          track_items_json = excluded.track_items_json,
          label_items_json = excluded.label_items_json,
          updated_at = excluded.updated_at
        """,
        (
            owned_item_id,
            music_detail["format_name"],
            1 if music_detail.get("is_promotional_not_for_sale") else 0,
            music_detail.get("artist_or_brand"),
            music_detail.get("release_year"),
            music_detail.get("released_date"),
            music_detail.get("barcode"),
            music_detail.get("label_name"),
            music_detail.get("catalog_no"),
            music_detail.get("cover_image_url"),
            json.dumps(music_detail.get("track_list", []), ensure_ascii=True),
            music_detail.get("media_type"),
            json.dumps(music_detail.get("genres", []), ensure_ascii=True),
            json.dumps(music_detail.get("styles", []), ensure_ascii=True),
            disc_condition,
            cover_condition,
            music_detail.get("disc_count"),
            music_detail.get("speed_rpm"),
            has_obi_db,
            runout_matrix_legacy,
            json.dumps(runout_matrix_values, ensure_ascii=True),
            music_detail.get("pressing_country"),
            music_detail.get("source_notes"),
            json.dumps(music_detail.get("credits", []), ensure_ascii=True),
            json.dumps(music_detail.get("identifier_items", []), ensure_ascii=True),
            json.dumps(music_detail.get("image_items", []), ensure_ascii=True),
            json.dumps(music_detail.get("company_items", []), ensure_ascii=True),
            json.dumps(music_detail.get("series", []), ensure_ascii=True),
            json.dumps(music_detail.get("format_items", []), ensure_ascii=True),
            json.dumps(music_detail.get("track_items", []), ensure_ascii=True),
            json.dumps(music_detail.get("label_items", []), ensure_ascii=True),
            timestamp,
            timestamp,
        ),
    )


def _upsert_goods_item_detail_in_conn(
    conn: sqlite3.Connection,
    owned_item_id: int,
    goods_detail: dict[str, Any],
    now: str | None = None,
) -> None:
    timestamp = now or utc_now_iso()
    image_urls_raw = goods_detail.get("image_urls")
    if isinstance(image_urls_raw, list):
        image_urls = [str(v).strip() for v in image_urls_raw if str(v).strip()]
    elif image_urls_raw is None:
        image_urls = []
    else:
        text = str(image_urls_raw).strip()
        image_urls = [part.strip() for part in text.splitlines() if part.strip()] if text else []

    primary_image_url = str(goods_detail.get("primary_image_url") or "").strip() or None
    if primary_image_url is None and image_urls:
        primary_image_url = image_urls[0]

    poster_storage_spec = str(goods_detail.get("poster_storage_spec") or "").strip() or None
    tshirt_size = str(goods_detail.get("tshirt_size") or "").strip() or None
    cup_material = str(goods_detail.get("cup_material") or "").strip() or None
    hat_size = str(goods_detail.get("hat_size") or "").strip() or None

    conn.execute(
        """
        INSERT INTO goods_item_detail (
          owned_item_id,
          image_urls_json,
          primary_image_url,
          poster_storage_spec,
          tshirt_size,
          cup_material,
          hat_size,
          created_at,
          updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(owned_item_id) DO UPDATE SET
          image_urls_json = excluded.image_urls_json,
          primary_image_url = excluded.primary_image_url,
          poster_storage_spec = excluded.poster_storage_spec,
          tshirt_size = excluded.tshirt_size,
          cup_material = excluded.cup_material,
          hat_size = excluded.hat_size,
          updated_at = excluded.updated_at
        """,
        (
            owned_item_id,
            json.dumps(image_urls, ensure_ascii=True),
            primary_image_url,
            poster_storage_spec,
            tshirt_size,
            cup_material,
            hat_size,
            timestamp,
            timestamp,
        ),
    )


def _sync_owned_item_classifications_in_conn(
    conn: sqlite3.Connection,
    owned_item_id: int,
    subtype_option_ids: list[int],
    soundtrack_option_ids: list[int],
    now: str | None = None,
) -> None:
    timestamp = now or utc_now_iso()
    conn.execute("DELETE FROM owned_item_subtype WHERE owned_item_id = ?", (owned_item_id,))
    conn.execute("DELETE FROM owned_item_soundtrack WHERE owned_item_id = ?", (owned_item_id,))

    def _valid_option_ids(option_group: str, ids: list[int]) -> list[int]:
        unique_ids = sorted({int(v) for v in ids if int(v) > 0})
        if not unique_ids:
            return []
        placeholders = ",".join("?" for _ in unique_ids)
        rows = conn.execute(
            f"""
            SELECT id
            FROM classification_option
            WHERE option_group = ?
              AND id IN ({placeholders})
            """,
            [option_group, *unique_ids],
        ).fetchall()
        return [int(row["id"]) for row in rows]

    valid_subtypes = _valid_option_ids("SUBTYPE", subtype_option_ids)
    valid_soundtracks = _valid_option_ids("SOUNDTRACK", soundtrack_option_ids)

    if valid_subtypes:
        conn.executemany(
            """
            INSERT OR IGNORE INTO owned_item_subtype
              (owned_item_id, option_id, created_at)
            VALUES (?, ?, ?)
            """,
            [(owned_item_id, option_id, timestamp) for option_id in valid_subtypes],
        )
    if valid_soundtracks:
        conn.executemany(
            """
            INSERT OR IGNORE INTO owned_item_soundtrack
              (owned_item_id, option_id, created_at)
            VALUES (?, ?, ?)
            """,
            [(owned_item_id, option_id, timestamp) for option_id in valid_soundtracks],
        )


def update_owned_item(owned_item_id: int, payload: dict[str, Any]) -> bool:
    now = utc_now_iso()
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id, storage_slot_id FROM owned_item WHERE id = ?",
            (owned_item_id,),
        ).fetchone()
        if existing is None:
            return False
        previous_storage_slot_id = existing["storage_slot_id"]

        conn.execute(
            """
            UPDATE owned_item
            SET
              master_item_id = ?,
              linked_album_master_id = ?,
              linked_artist_name = ?,
              copy_group_key = ?,
              category = ?,
              domain_code = ?,
              release_type = ?,
              item_name_override = ?,
              quantity = ?,
              is_second_hand = ?,
              size_group = ?,
              preferred_storage_size_group = ?,
              status = ?,
              condition_grade = ?,
              signature_type = ?,
              source_code = ?,
              source_external_id = ?,
              signed_by = ?,
              signed_at = ?,
              acquisition_date = ?,
              purchase_price = ?,
              currency_code = ?,
              purchase_source = ?,
              memory_note = ?,
              display_rank = ?,
              storage_slot_id = ?,
              thickness_mm = ?,
              notes = ?,
              updated_at = ?
            WHERE id = ?
            """,
            (
                payload.get("master_item_id"),
                payload.get("linked_album_master_id"),
                payload.get("linked_artist_name"),
                payload.get("copy_group_key"),
                payload["category"],
                payload.get("domain_code"),
                payload.get("release_type"),
                payload.get("item_name_override"),
                payload["quantity"],
                1 if payload.get("is_second_hand") else 0,
                payload["size_group"],
                payload.get("preferred_storage_size_group") or payload["size_group"],
                payload.get("status", "IN_COLLECTION"),
                payload.get("condition_grade"),
                payload.get("signature_type", "NONE"),
                payload.get("source_code"),
                payload.get("source_external_id"),
                payload.get("signed_by"),
                payload.get("signed_at"),
                payload.get("acquisition_date"),
                payload.get("purchase_price"),
                payload.get("currency_code"),
                payload.get("purchase_source"),
                payload.get("memory_note"),
                payload.get("display_rank"),
                payload.get("storage_slot_id"),
                payload.get("thickness_mm"),
                payload.get("notes"),
                now,
                owned_item_id,
            ),
        )

        _sync_owned_item_classifications_in_conn(
            conn,
            owned_item_id=owned_item_id,
            subtype_option_ids=payload.get("subtype_option_ids") or [],
            soundtrack_option_ids=payload.get("soundtrack_option_ids") or [],
            now=now,
        )

        music_detail = payload.get("music_detail")
        if music_detail:
            _upsert_music_item_detail_in_conn(conn, owned_item_id=owned_item_id, music_detail=music_detail, now=now)
        else:
            conn.execute("DELETE FROM music_item_detail WHERE owned_item_id = ?", (owned_item_id,))
        goods_detail = payload.get("goods_detail")
        if goods_detail:
            _upsert_goods_item_detail_in_conn(conn, owned_item_id=owned_item_id, goods_detail=goods_detail, now=now)
        else:
            conn.execute("DELETE FROM goods_item_detail WHERE owned_item_id = ?", (owned_item_id,))

        next_storage_slot_id = payload.get("storage_slot_id")
        if previous_storage_slot_id != next_storage_slot_id:
            _log_owned_item_location_event_in_conn(
                conn,
                owned_item_id=owned_item_id,
                from_storage_slot_id=int(previous_storage_slot_id) if previous_storage_slot_id is not None else None,
                to_storage_slot_id=int(next_storage_slot_id) if next_storage_slot_id is not None else None,
                now=now,
            )

    return True


def bulk_update_owned_items(
    owned_item_ids: list[int],
    *,
    status: str | None = None,
    domain_code: str | None = None,
    release_type: str | None = None,
    is_second_hand: bool | None = None,
    purchase_source: str | None = None,
    append_memory_note: str | None = None,
    preferred_storage_size_group: str | None = None,
) -> list[int]:
    ids = sorted({int(v) for v in owned_item_ids if int(v) > 0})
    if not ids:
        return []

    now = utc_now_iso()
    note_text = str(append_memory_note or "").strip()
    # Bulk update touches every row in `ids` for status/domain/release_type
    # and may append memory notes. IMMEDIATE keeps the batch atomic from a
    # reader's perspective (the dashboard / export endpoints).
    with get_write_conn() as conn:
        placeholders = ",".join("?" for _ in ids)
        rows = conn.execute(
            f"""
            SELECT id, status, domain_code, release_type, is_second_hand, purchase_source, memory_note, preferred_storage_size_group, linked_album_master_id
            FROM owned_item
            WHERE id IN ({placeholders})
            """,
            ids,
        ).fetchall()
        existing_by_id = {int(row["id"]): dict(row) for row in rows}
        updates = []
        updated_ids = []
        master_ids_to_sync: set[int] = set()
        for owned_item_id in ids:
            row = existing_by_id.get(owned_item_id)
            if not row:
                continue
            next_status = status if status is not None else row.get("status")
            next_domain_code = domain_code if domain_code is not None else row.get("domain_code")
            next_release_type = release_type if release_type is not None else row.get("release_type")
            next_is_second_hand = int(bool(is_second_hand)) if is_second_hand is not None else int(bool(row.get("is_second_hand")))
            next_purchase_source = purchase_source if purchase_source is not None else row.get("purchase_source")
            next_preferred_size_group = (
                preferred_storage_size_group if preferred_storage_size_group is not None else row.get("preferred_storage_size_group")
            )
            next_memory_note = row.get("memory_note")
            if note_text:
                existing_note = str(next_memory_note or "").strip()
                next_memory_note = f"{existing_note}\n{note_text}".strip() if existing_note else note_text
            if (
                next_status == row.get("status")
                and next_domain_code == row.get("domain_code")
                and next_release_type == row.get("release_type")
                and next_is_second_hand == int(bool(row.get("is_second_hand")))
                and next_purchase_source == row.get("purchase_source")
                and next_preferred_size_group == row.get("preferred_storage_size_group")
                and next_memory_note == row.get("memory_note")
            ):
                continue
            updates.append(
                (
                    next_status,
                    next_domain_code,
                    next_release_type,
                    next_is_second_hand,
                    next_purchase_source,
                    next_memory_note,
                    next_preferred_size_group,
                    now,
                    owned_item_id,
                )
            )
            updated_ids.append(owned_item_id)
            linked_album_master_id = int(row.get("linked_album_master_id") or 0)
            if linked_album_master_id > 0:
                master_ids_to_sync.add(linked_album_master_id)
        if updates:
            conn.executemany(
                """
                UPDATE owned_item
                SET
                  status = ?,
                  domain_code = ?,
                  release_type = ?,
                  is_second_hand = ?,
                  purchase_source = ?,
                  memory_note = ?,
                  preferred_storage_size_group = ?,
                  updated_at = ?
                WHERE id = ?
                """,
                updates,
            )
            if domain_code is not None:
                for album_master_id in sorted(master_ids_to_sync):
                    _sync_album_master_domain_code_in_conn(conn, album_master_id)
    return updated_ids


def set_owned_item_copy_group(owned_item_id: int, copy_group_key: str | None) -> bool:
    now = utc_now_iso()
    key = str(copy_group_key or "").strip() or None
    with get_conn() as conn:
        cur = conn.execute(
            """
            UPDATE owned_item
            SET copy_group_key = ?, updated_at = ?
            WHERE id = ?
            """,
            (key, now, owned_item_id),
        )
        return int(cur.rowcount or 0) > 0


def delete_owned_item(owned_item_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM owned_item WHERE id = ?", (owned_item_id,))
        return int(cur.rowcount or 0) > 0


def get_owned_item(owned_item_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM owned_item WHERE id = ?",
            (owned_item_id,),
        ).fetchone()
        if row is None:
            return None
        return dict(row)


def get_owned_item_detail(owned_item_id: int) -> dict[str, Any] | None:
    query = _owned_item_select_query() + " WHERE oi.id = ? LIMIT 1"
    with get_conn() as conn:
        row = conn.execute(query, (owned_item_id,)).fetchone()
    if row is None:
        return None
    return _normalize_owned_item_row(dict(row))


def get_owned_item_location_snapshot(owned_item_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT
              oi.id,
              oi.storage_slot_id,
              ss.slot_code,
              ss.cabinet_name,
              ss.column_code,
              ss.cell_code,
              ss.allowed_size_group,
              ss.is_overflow_zone,
              (
                SELECT e.from_slot_code
                FROM owned_item_location_event e
                WHERE e.owned_item_id = oi.id
                  AND TRIM(COALESCE(e.from_slot_code, '')) <> ''
                ORDER BY e.created_at DESC, e.id DESC
                LIMIT 1
              ) AS previous_slot_code,
              (
                SELECT e.from_slot_display_name
                FROM owned_item_location_event e
                WHERE e.owned_item_id = oi.id
                  AND TRIM(COALESCE(e.from_slot_display_name, '')) <> ''
                ORDER BY e.created_at DESC, e.id DESC
                LIMIT 1
              ) AS previous_slot_display_name
            FROM owned_item oi
            LEFT JOIN storage_slot ss ON ss.id = oi.storage_slot_id
            WHERE oi.id = ?
            LIMIT 1
            """,
            (int(owned_item_id),),
        ).fetchone()
    if row is None:
        return None
    data = dict(row)
    current_display_name = "미배치"
    if data.get("storage_slot_id") is not None:
        current_display_name = _storage_slot_display_name(
            {
                "slot_code": data.get("slot_code"),
                "cabinet_name": data.get("cabinet_name"),
                "column_code": data.get("column_code"),
                "cell_code": data.get("cell_code"),
                "allowed_size_group": data.get("allowed_size_group"),
                "is_overflow_zone": data.get("is_overflow_zone"),
            }
        )
    return {
        "current_slot_code": data.get("slot_code"),
        "current_slot_display_name": current_display_name,
        "previous_slot_code": str(data.get("previous_slot_code") or "").strip() or None,
        "previous_slot_display_name": str(data.get("previous_slot_display_name") or "").strip() or None,
    }


def search_operator_catalog(query_text: str, limit: int = 30) -> list[dict[str, Any]]:
    clean_query = str(query_text or "").strip()
    if not clean_query:
        return []

    query_norm = clean_query.lower()
    query_like = f"%{query_norm}%"
    query_token_groups = _search_token_groups(clean_query)
    barcode_digits = re.sub(r"[^0-9]", "", clean_query)
    parsed_label_id = _parse_label_id_query(clean_query)
    requested_limit = max(1, int(limit))
    fetch_limit = max(10, min(200, requested_limit * 4))

    base_sql_template = """
      SELECT
        oi.id,
        oi.category,
        oi.item_name_override,
        oi.linked_album_master_id,
        oi.created_at,
        oi.status,
        oi.signature_type,
        mid.format_name,
        mid.artist_or_brand,
        mid.released_date,
        mid.pressing_country,
        mid.label_name,
        mid.catalog_no,
        mid.barcode,
        mid.runout_matrix_json,
        mid.format_items_json,
        mid.cover_image_url,
        mid.track_list_json,
        mid.track_items_json,
        COALESCE(oi.item_name_override, am.title) AS item_title,
        ss.slot_code,
        ss.cabinet_name,
        ss.column_code,
        ss.cell_code,
        ss.allowed_size_group,
        ss.is_overflow_zone,
        (
          SELECT e.from_slot_code
          FROM owned_item_location_event e
          WHERE e.owned_item_id = oi.id
            AND TRIM(COALESCE(e.from_slot_code, '')) <> ''
          ORDER BY e.created_at DESC, e.id DESC
          LIMIT 1
        ) AS previous_slot_code,
        (
          SELECT e.from_slot_display_name
          FROM owned_item_location_event e
          WHERE e.owned_item_id = oi.id
            AND TRIM(COALESCE(e.from_slot_display_name, '')) <> ''
          ORDER BY e.created_at DESC, e.id DESC
          LIMIT 1
        ) AS previous_slot_display_name
      FROM owned_item oi
      LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
      LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
      LEFT JOIN storage_slot ss ON ss.id = oi.storage_slot_id
      WHERE oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
        AND {where_sql}
      ORDER BY
        CASE WHEN oi.status = 'IN_COLLECTION' THEN 0 ELSE 1 END,
        oi.updated_at DESC,
        oi.id DESC
      LIMIT ?
    """

    def _build_items(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in rows:
            item = _normalize_owned_item_row(dict(row))
            track_matches: list[str] = []
            seen_tracks: set[str] = set()

            def _push_track(value: Any) -> None:
                text = str(value or "").strip()
                if not text or text.lower() in seen_tracks:
                    return
                if not _matches_search_text(text, clean_query, query_token_groups):
                    return
                seen_tracks.add(text.lower())
                track_matches.append(text)

            for track in item.get("track_list") or []:
                _push_track(track)
            for track_item in item.get("track_items") or []:
                if not isinstance(track_item, dict):
                    continue
                _push_track(track_item.get("display"))
                _push_track(track_item.get("title"))

            current_slot_display_name = "미배치"
            if item.get("slot_code"):
                current_slot_display_name = _storage_slot_display_name(
                    {
                        "slot_code": item.get("slot_code"),
                        "cabinet_name": item.get("cabinet_name"),
                        "column_code": item.get("column_code"),
                        "cell_code": item.get("cell_code"),
                        "allowed_size_group": item.get("allowed_size_group"),
                        "is_overflow_zone": item.get("is_overflow_zone"),
                    }
                )

            item["current_slot_code"] = item.get("slot_code")
            item["current_slot_display_name"] = current_slot_display_name
            item["current_cabinet_name"] = str(item.get("cabinet_name") or "").strip() or None
            item["current_column_code"] = str(item.get("column_code") or "").strip() or None
            item["current_cell_code"] = str(item.get("cell_code") or "").strip() or None
            item["previous_slot_code"] = str(item.get("previous_slot_code") or "").strip() or None
            item["previous_slot_display_name"] = str(item.get("previous_slot_display_name") or "").strip() or None
            item["track_matches"] = track_matches[:8]
            item["matched_track_count"] = len(track_matches)
            out.append(item)
        return out

    def _select_candidate_rows(
        conn: sqlite3.Connection,
        where_clauses: list[str],
        params: list[Any],
        *,
        query_limit: int,
        exclude_ids: list[int] | None = None,
    ) -> list[sqlite3.Row]:
        filters = ["(" + " OR ".join(where_clauses) + ")"]
        query_params = list(params)
        if exclude_ids:
            placeholders = ",".join("?" for _ in exclude_ids)
            filters.append(f"oi.id NOT IN ({placeholders})")
            query_params.extend(exclude_ids)
        sql = base_sql_template.format(where_sql=" AND ".join(filters))
        query_params.append(query_limit)
        return conn.execute(sql, query_params).fetchall()

    primary_where_clauses = [
        "LOWER(COALESCE(oi.item_name_override, '')) LIKE ?",
        "LOWER(COALESCE(am.title, '')) LIKE ?",
        "LOWER(COALESCE(mid.artist_or_brand, '')) LIKE ?",
        "LOWER(COALESCE(mid.label_name, '')) LIKE ?",
        "LOWER(COALESCE(mid.catalog_no, '')) LIKE ?",
    ]
    primary_params: list[Any] = [query_like, query_like, query_like, query_like, query_like]
    if parsed_label_id is not None:
        category_codes, owned_item_id = parsed_label_id
        category_placeholders = ",".join("?" for _ in category_codes)
        primary_where_clauses.insert(0, f"(oi.id = ? AND UPPER(COALESCE(oi.category, '')) IN ({category_placeholders}))")
        primary_params = [owned_item_id, *category_codes, *primary_params]
    if barcode_digits:
        primary_where_clauses.append("REPLACE(COALESCE(mid.barcode, ''), '-', '') LIKE ?")
        primary_params.append(f"%{barcode_digits}%")
    if query_token_groups:
        token_sql, token_params = _build_compact_token_match_sql(
            """
            COALESCE(oi.item_name_override, '') || ' ' ||
            COALESCE(am.title, '') || ' ' ||
            COALESCE(mid.artist_or_brand, '') || ' ' ||
            COALESCE(mid.label_name, '') || ' ' ||
            COALESCE(mid.catalog_no, '') || ' ' ||
            COALESCE(mid.barcode, '')
            """,
            query_token_groups,
        )
        if token_sql:
            primary_where_clauses.append(token_sql)
            primary_params.extend(token_params)

    fallback_where_clauses = [
        "LOWER(COALESCE(mid.track_list_json, '')) LIKE ?",
        "LOWER(COALESCE(mid.track_items_json, '')) LIKE ?",
        """
        EXISTS (
          SELECT 1
          FROM json_each(COALESCE(mid.track_list_json, '[]')) jt
          WHERE LOWER(COALESCE(jt.value, '')) LIKE ?
        )
        """,
        """
        EXISTS (
          SELECT 1
          FROM json_each(COALESCE(mid.track_items_json, '[]')) ji
          WHERE LOWER(COALESCE(json_extract(ji.value, '$.display'), '')) LIKE ?
             OR LOWER(COALESCE(json_extract(ji.value, '$.title'), '')) LIKE ?
        )
        """,
    ]
    fallback_params: list[Any] = [query_like, query_like, query_like, query_like, query_like]
    if query_token_groups:
        token_sql, token_params = _build_compact_token_match_sql(
            """
            COALESCE(mid.track_list_json, '') || ' ' ||
            COALESCE(mid.track_items_json, '')
            """,
            query_token_groups,
        )
        if token_sql:
            fallback_where_clauses.append(token_sql)
            fallback_params.extend(token_params)

    with get_conn() as conn:
        primary_rows = _select_candidate_rows(
            conn,
            primary_where_clauses,
            primary_params,
            query_limit=fetch_limit,
        )
        rows = list(primary_rows)
        if len(rows) < requested_limit:
            fallback_rows = _select_candidate_rows(
                conn,
                fallback_where_clauses,
                fallback_params,
                query_limit=max(10, min(200, (requested_limit - len(rows)) * 4)),
                exclude_ids=[int(row["id"]) for row in rows],
            )
            rows.extend(fallback_rows)

    out = _build_items(rows)
    out.sort(
        key=lambda row: (
            0
            if (
                parsed_label_id is not None
                and int(row.get("id") or 0) == parsed_label_id[1]
                and str(row.get("category") or "").upper() in parsed_label_id[0]
            )
            else 1,
            0 if (row.get("matched_track_count") or 0) > 0 else 1,
            0 if str(row.get("status") or "") == "IN_COLLECTION" else 1,
            str(row.get("item_title") or row.get("item_name_override") or "").lower(),
            int(row.get("id") or 0),
        )
    )
    return out[:requested_limit]


def _build_ops_home_recent_item(row: dict[str, Any]) -> dict[str, Any]:
    category = str(row.get("category") or "").strip()
    owned_item_id = int(row.get("owned_item_id") or row.get("id") or 0)
    current_slot_code = str(row.get("current_slot_code") or "").strip() or None
    current_cabinet_name = str(row.get("current_cabinet_name") or "").strip() or None
    current_column_code = str(row.get("current_column_code") or "").strip() or None
    current_cell_code = str(row.get("current_cell_code") or "").strip() or None
    current_slot_display_name = "미배치"
    if current_slot_code:
        current_slot_display_name = _storage_slot_display_name(
            {
                "slot_code": current_slot_code,
                "cabinet_name": current_cabinet_name,
                "column_code": current_column_code,
                "cell_code": current_cell_code,
                "allowed_size_group": row.get("allowed_size_group"),
                "is_overflow_zone": row.get("is_overflow_zone"),
            }
        )
    runout_values: list[str] = []
    raw_runout_json = row.get("runout_matrix_json")
    if raw_runout_json:
        try:
            parsed_runout = json.loads(str(raw_runout_json))
        except json.JSONDecodeError:
            parsed_runout = []
        if isinstance(parsed_runout, list):
            runout_values = [str(value).strip() for value in parsed_runout if str(value).strip()]
    if not runout_values:
        legacy_runout = str(row.get("runout_matrix") or "").strip()
        if legacy_runout:
            runout_values = [part.strip() for part in legacy_runout.split("|") if part.strip()]

    format_items: list[dict[str, Any]] = []
    raw_format_items = row.get("format_items_json")
    if raw_format_items:
        try:
            parsed_format_items = json.loads(str(raw_format_items))
        except json.JSONDecodeError:
            parsed_format_items = []
        if isinstance(parsed_format_items, list):
            format_items = [dict(value) for value in parsed_format_items if isinstance(value, dict)]
    return {
        "owned_item_id": owned_item_id,
        "label_id": _build_label_id(category, owned_item_id),
        "category": category,
        "format_name": str(row.get("format_name") or "").strip() or None,
        "format_items": format_items,
        "item_title": str(row.get("item_title") or "").strip() or None,
        "artist_or_brand": str(row.get("artist_or_brand") or "").strip() or None,
        "released_date": str(row.get("released_date") or "").strip() or None,
        "pressing_country": str(row.get("pressing_country") or "").strip() or None,
        "label_name": str(row.get("label_name") or "").strip() or None,
        "catalog_no": str(row.get("catalog_no") or "").strip() or None,
        "barcode": str(row.get("barcode") or "").strip() or None,
        "runout_sample": " | ".join(runout_values[:2]) if runout_values else None,
        "cover_image_url": str(row.get("cover_image_url") or "").strip() or None,
        "current_slot_code": current_slot_code,
        "current_slot_display_name": current_slot_display_name,
        "current_cabinet_name": current_cabinet_name,
        "current_column_code": current_column_code,
        "current_cell_code": current_cell_code,
        "previous_slot_code": str(row.get("previous_slot_code") or "").strip() or None,
        "previous_slot_display_name": str(row.get("previous_slot_display_name") or "").strip() or None,
        "created_at": str(row.get("created_at") or ""),
    }


def count_ops_home_recent_moved_items() -> int:
    move_threshold = (datetime.now(timezone.utc) - timedelta(days=DASHBOARD_MOVE_WINDOW_DAYS)).isoformat()
    with get_conn() as conn:
        row = conn.execute(
            """
            WITH ranked_events AS (
              SELECT
                e.owned_item_id,
                ROW_NUMBER() OVER (
                  PARTITION BY e.owned_item_id
                  ORDER BY e.created_at DESC, e.id DESC
                ) AS event_rank
              FROM owned_item_location_event e
              WHERE e.movement_kind = 'MOVE'
                AND TRIM(COALESCE(e.from_slot_code, '')) NOT IN ('', 'UNASSIGNED')
                AND e.created_at >= ?
            )
            SELECT COUNT(*) AS total_count
            FROM ranked_events re
            JOIN owned_item oi ON oi.id = re.owned_item_id
            WHERE re.event_rank = 1
              AND oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
              AND oi.storage_slot_id IS NOT NULL
            """,
            (move_threshold,),
        ).fetchone()
    return int(row["total_count"] or 0) if row else 0


def list_ops_home_recent_moved_items(limit: int = 6, offset: int = 0) -> list[dict[str, Any]]:
    move_threshold = (datetime.now(timezone.utc) - timedelta(days=DASHBOARD_MOVE_WINDOW_DAYS)).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            """
            WITH ranked_events AS (
              SELECT
                e.id AS event_id,
                e.owned_item_id,
                e.from_slot_code AS previous_slot_code,
                e.from_slot_display_name AS previous_slot_display_name,
                e.created_at,
                ROW_NUMBER() OVER (
                  PARTITION BY e.owned_item_id
                  ORDER BY e.created_at DESC, e.id DESC
                ) AS event_rank
              FROM owned_item_location_event e
              WHERE e.movement_kind = 'MOVE'
                AND TRIM(COALESCE(e.from_slot_code, '')) NOT IN ('', 'UNASSIGNED')
                AND e.created_at >= ?
            ),
            recent_events AS (
              SELECT *
              FROM ranked_events
              WHERE event_rank = 1
              ORDER BY created_at DESC, event_id DESC
              LIMIT ?
              OFFSET ?
            )
            SELECT
              re.event_id,
              oi.id AS owned_item_id,
              oi.category,
              mid.format_name,
              COALESCE(oi.item_name_override, am.title) AS item_title,
              COALESCE(mid.artist_or_brand, am.artist_or_brand, oi.linked_artist_name) AS artist_or_brand,
              mid.released_date,
              mid.pressing_country,
              mid.label_name,
              mid.catalog_no,
              mid.barcode,
              mid.runout_matrix_json,
              mid.format_items_json,
              COALESCE(mid.cover_image_url, gid.primary_image_url) AS cover_image_url,
              ss.slot_code AS current_slot_code,
              ss.cabinet_name AS current_cabinet_name,
              ss.column_code AS current_column_code,
              ss.cell_code AS current_cell_code,
              ss.allowed_size_group,
              ss.is_overflow_zone,
              re.previous_slot_code,
              re.previous_slot_display_name,
              re.created_at
            FROM recent_events re
            JOIN owned_item oi ON oi.id = re.owned_item_id
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            LEFT JOIN goods_item_detail gid ON gid.owned_item_id = oi.id
            LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
            LEFT JOIN storage_slot ss ON ss.id = oi.storage_slot_id
            WHERE oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
              AND oi.storage_slot_id IS NOT NULL
            ORDER BY re.created_at DESC, re.event_id DESC
            """,
            (move_threshold, int(limit), max(0, int(offset))),
        ).fetchall()
    return [_build_ops_home_recent_item(dict(row)) for row in rows]


def count_ops_home_recent_registered_items(days: int | None = None) -> int:
    where_sql = "WHERE oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')"
    params: list[Any] = []
    if days is not None and int(days) > 0:
        threshold = (datetime.now(timezone.utc) - timedelta(days=int(days))).isoformat()
        where_sql += " AND oi.created_at >= ?"
        params.append(threshold)
    with get_conn() as conn:
        row = conn.execute(
            f"""
            SELECT COUNT(*) AS total_count
            FROM owned_item oi
            {where_sql}
            """,
            tuple(params),
        ).fetchone()
    return int(row["total_count"] or 0) if row else 0


def list_ops_home_recent_registered_items(limit: int = 6, offset: int = 0) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            WITH recent_owned AS (
              SELECT
                oi.id,
                oi.category,
                oi.item_name_override,
                oi.linked_album_master_id,
                oi.linked_artist_name,
                oi.storage_slot_id,
                oi.created_at
              FROM owned_item oi
              WHERE oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
              ORDER BY oi.created_at DESC, oi.id DESC
              LIMIT ?
              OFFSET ?
            )
            SELECT
              oi.id AS owned_item_id,
              oi.category,
              mid.format_name,
              COALESCE(oi.item_name_override, am.title) AS item_title,
              COALESCE(mid.artist_or_brand, am.artist_or_brand, oi.linked_artist_name) AS artist_or_brand,
              mid.released_date,
              mid.pressing_country,
              mid.label_name,
              mid.catalog_no,
              mid.barcode,
              mid.runout_matrix_json,
              mid.format_items_json,
              COALESCE(mid.cover_image_url, gid.primary_image_url) AS cover_image_url,
              ss.slot_code AS current_slot_code,
              ss.cabinet_name AS current_cabinet_name,
              ss.column_code AS current_column_code,
              ss.cell_code AS current_cell_code,
              ss.allowed_size_group,
              ss.is_overflow_zone,
              oi.created_at
            FROM recent_owned oi
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            LEFT JOIN goods_item_detail gid ON gid.owned_item_id = oi.id
            LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
            LEFT JOIN storage_slot ss ON ss.id = oi.storage_slot_id
            ORDER BY oi.created_at DESC, oi.id DESC
            """,
            (int(limit), max(0, int(offset))),
        ).fetchall()
    return [_build_ops_home_recent_item(dict(row)) for row in rows]


def get_ops_home_recent_sections(limit: int = 6) -> dict[str, Any]:
    return {
        "recent_moved_items": list_ops_home_recent_moved_items(limit=limit),
        "recent_registered_items": list_ops_home_recent_registered_items(limit=limit),
        "recent_moved_total_count": count_ops_home_recent_moved_items(),
        "recent_registered_total_count": count_ops_home_recent_registered_items(days=30),
    }


def get_ops_home_feed(kind: str = "registered", page: int = 1, limit: int = 30) -> dict[str, Any]:
    normalized_kind = "moved" if str(kind or "").strip().lower() == "moved" else "registered"
    safe_page = max(1, int(page))
    safe_limit = max(1, int(limit))
    offset = (safe_page - 1) * safe_limit
    if normalized_kind == "moved":
        total_count = count_ops_home_recent_moved_items()
        items = list_ops_home_recent_moved_items(limit=safe_limit, offset=offset)
    else:
        total_count = count_ops_home_recent_registered_items()
        items = list_ops_home_recent_registered_items(limit=safe_limit, offset=offset)
    return {
        "kind": normalized_kind,
        "page": safe_page,
        "limit": safe_limit,
        "total_count": total_count,
        "items": items,
    }


# Customer track request CRUD lives in app.db.customer_track_request and
# is re-exported at the bottom of this module.


# Auth-account CRUD (`list_auth_accounts`, `get_auth_account_by_username`,
# `upsert_auth_account`, `delete_auth_account`) lives in app.db.auth_account
# now and is re-exported at the bottom of this module.


def _owned_item_select_query() -> str:
    return """
      SELECT
        oi.id,
        oi.master_item_id,
        oi.linked_album_master_id,
        oi.linked_artist_name,
        oi.copy_group_key,
        oi.category,
        oi.domain_code,
        oi.release_type,
        oi.item_name_override,
        oi.quantity,
        oi.size_group,
        COALESCE(oi.preferred_storage_size_group, oi.size_group) AS preferred_storage_size_group,
        oi.status,
        oi.condition_grade,
        oi.display_rank,
        oi.order_key,
        oi.storage_slot_id,
        ss.slot_code,
        oi.is_second_hand,
        oi.signature_type,
        oi.source_code,
        oi.source_external_id,
        oi.purchase_price,
        oi.currency_code,
        oi.purchase_source,
        oi.memory_note,
        oi.thickness_mm,
        oi.notes,
        oi.created_at,
        oi.updated_at,
        mid.format_name,
        mid.artist_or_brand,
        mid.release_year,
        mid.released_date,
        am.title AS master_title,
        am.artist_or_brand AS master_artist_or_brand,
        am.sort_artist_name AS master_sort_artist_name,
        am.release_year AS master_release_year,
        mid.barcode,
        mid.label_name,
        mid.catalog_no,
        COALESCE(mid.cover_image_url, gid.primary_image_url) AS cover_image_url,
        mid.track_list_json,
        mid.media_type,
        mid.genres_json,
        mid.styles_json,
        mid.disc_count,
        mid.speed_rpm,
        mid.has_obi,
        mid.runout_matrix,
        mid.runout_matrix_json,
        mid.pressing_country,
        mid.source_notes,
        mid.credits_json,
        mid.identifier_items_json,
        mid.image_items_json,
        mid.company_items_json,
        mid.series_json,
        mid.format_items_json,
        mid.track_items_json,
        mid.label_items_json,
        mid.sleeve_condition AS cover_condition,
        mid.media_condition AS disc_condition,
        mid.is_promotional_not_for_sale,
        gid.image_urls_json,
        gid.primary_image_url AS goods_primary_image_url,
        gid.poster_storage_spec,
        gid.tshirt_size,
        gid.cup_material,
        gid.hat_size,
        COALESCE((
          SELECT GROUP_CONCAT(co.id)
          FROM owned_item_subtype ois
          JOIN classification_option co ON co.id = ois.option_id
          WHERE ois.owned_item_id = oi.id
          ORDER BY co.sort_order ASC, co.id ASC
        ), '') AS subtype_option_ids_csv,
        COALESCE((
          SELECT GROUP_CONCAT(co.label, '|')
          FROM owned_item_subtype ois
          JOIN classification_option co ON co.id = ois.option_id
          WHERE ois.owned_item_id = oi.id
          ORDER BY co.sort_order ASC, co.id ASC
        ), '') AS subtype_labels_csv,
        COALESCE((
          SELECT GROUP_CONCAT(co.id)
          FROM owned_item_soundtrack ois
          JOIN classification_option co ON co.id = ois.option_id
          WHERE ois.owned_item_id = oi.id
          ORDER BY co.sort_order ASC, co.id ASC
        ), '') AS soundtrack_option_ids_csv,
        COALESCE((
          SELECT GROUP_CONCAT(co.label, '|')
          FROM owned_item_soundtrack ois
          JOIN classification_option co ON co.id = ois.option_id
          WHERE ois.owned_item_id = oi.id
          ORDER BY co.sort_order ASC, co.id ASC
        ), '') AS soundtrack_labels_csv,
        COALESCE((
          SELECT COUNT(*)
          FROM owned_item_digital_link l
          JOIN digital_asset da ON da.id = l.digital_asset_id
          WHERE l.owned_item_id = oi.id
            AND da.asset_type = 'AUDIO'
        ), 0) AS audio_asset_count
      FROM owned_item oi
      LEFT JOIN storage_slot ss ON ss.id = oi.storage_slot_id
      LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
      LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
      LEFT JOIN goods_item_detail gid ON gid.owned_item_id = oi.id
    """


def _normalize_owned_item_row(obj: dict[str, Any]) -> dict[str, Any]:
    track_list_raw = obj.pop("track_list_json", None)
    if track_list_raw:
        try:
            track_list = json.loads(track_list_raw)
            obj["track_list"] = track_list if isinstance(track_list, list) else []
        except json.JSONDecodeError:
            obj["track_list"] = []
    else:
        obj["track_list"] = []

    genres_raw = obj.pop("genres_json", None)
    if genres_raw:
        try:
            parsed_genres = json.loads(genres_raw)
            obj["genres"] = [str(v).strip() for v in parsed_genres if str(v).strip()] if isinstance(parsed_genres, list) else []
        except json.JSONDecodeError:
            obj["genres"] = []
    else:
        obj["genres"] = []

    styles_raw = obj.pop("styles_json", None)
    if styles_raw:
        try:
            parsed_styles = json.loads(styles_raw)
            obj["styles"] = [str(v).strip() for v in parsed_styles if str(v).strip()] if isinstance(parsed_styles, list) else []
        except json.JSONDecodeError:
            obj["styles"] = []
    else:
        obj["styles"] = []

    goods_images_raw = obj.pop("image_urls_json", None)
    goods_image_urls: list[str] = []
    if goods_images_raw:
        try:
            parsed_goods_images = json.loads(str(goods_images_raw))
            if isinstance(parsed_goods_images, list):
                goods_image_urls = [str(v).strip() for v in parsed_goods_images if str(v).strip()]
        except json.JSONDecodeError:
            goods_image_urls = []
    obj["goods_image_urls"] = goods_image_urls
    goods_primary_image_url = str(obj.pop("goods_primary_image_url", "") or "").strip() or None
    if goods_primary_image_url is None and goods_image_urls:
        goods_primary_image_url = goods_image_urls[0]
    obj["goods_primary_image_url"] = goods_primary_image_url
    obj["poster_storage_spec"] = str(obj.get("poster_storage_spec") or "").strip() or None
    obj["tshirt_size"] = str(obj.get("tshirt_size") or "").strip() or None
    obj["cup_material"] = str(obj.get("cup_material") or "").strip() or None
    obj["hat_size"] = str(obj.get("hat_size") or "").strip() or None

    obj["is_second_hand"] = bool(obj.get("is_second_hand"))
    if obj.get("recently_moved_to_current_slot") is not None:
        obj["recently_moved_to_current_slot"] = bool(obj.get("recently_moved_to_current_slot"))
    if obj.get("is_promotional_not_for_sale") is not None:
        obj["is_promotional_not_for_sale"] = bool(obj.get("is_promotional_not_for_sale"))
    if obj.get("has_obi") is not None:
        obj["has_obi"] = True if int(obj.get("has_obi")) == 1 else None

    runout_json_raw = obj.pop("runout_matrix_json", None)
    runout_values: list[str] = []
    if runout_json_raw:
        try:
            parsed_runout = json.loads(runout_json_raw)
            if isinstance(parsed_runout, list):
                runout_values = [str(v).strip() for v in parsed_runout if str(v).strip()]
        except json.JSONDecodeError:
            runout_values = []
    if not runout_values:
        legacy_runout = str(obj.get("runout_matrix") or "").strip()
        if legacy_runout:
            runout_values = [p.strip() for p in legacy_runout.split("|") if p.strip()]
    obj["runout_matrix"] = runout_values

    def _json_to_string_list(raw: Any) -> list[str]:
        if not raw:
            return []
        try:
            parsed = json.loads(str(raw))
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        return [str(v).strip() for v in parsed if str(v).strip()]

    def _json_to_dict_list(raw: Any) -> list[dict[str, Any]]:
        if not raw:
            return []
        try:
            parsed = json.loads(str(raw))
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        out: list[dict[str, Any]] = []
        for row in parsed:
            if isinstance(row, dict):
                out.append(row)
        return out

    obj["credits"] = _json_to_string_list(obj.pop("credits_json", None))
    obj["identifier_items"] = _json_to_dict_list(obj.pop("identifier_items_json", None))
    obj["image_items"] = _json_to_dict_list(obj.pop("image_items_json", None))
    obj["company_items"] = _json_to_dict_list(obj.pop("company_items_json", None))
    obj["series"] = _json_to_string_list(obj.pop("series_json", None))
    obj["format_items"] = _json_to_dict_list(obj.pop("format_items_json", None))
    obj["track_items"] = _json_to_dict_list(obj.pop("track_items_json", None))
    obj["label_items"] = _json_to_dict_list(obj.pop("label_items_json", None))

    def _csv_to_int_list(raw: Any) -> list[int]:
        text = str(raw or "").strip()
        if not text:
            return []
        out: list[int] = []
        for part in text.split(","):
            p = str(part).strip()
            if not p:
                continue
            try:
                value = int(p)
            except ValueError:
                continue
            if value > 0:
                out.append(value)
        return out

    def _csv_to_label_list(raw: Any) -> list[str]:
        text = str(raw or "").strip()
        if not text:
            return []
        return [p.strip() for p in text.split("|") if p.strip()]

    obj["subtype_option_ids"] = _csv_to_int_list(obj.pop("subtype_option_ids_csv", None))
    obj["subtype_labels"] = _csv_to_label_list(obj.pop("subtype_labels_csv", None))
    obj["soundtrack_option_ids"] = _csv_to_int_list(obj.pop("soundtrack_option_ids_csv", None))
    obj["soundtrack_labels"] = _csv_to_label_list(obj.pop("soundtrack_labels_csv", None))

    audio_count = int(obj.get("audio_asset_count") or 0)
    obj["audio_asset_count"] = audio_count
    obj["has_audio"] = audio_count > 0
    return obj


def list_owned_items(
    category: str | None,
    domain_code: str | None,
    release_type: str | None,
    status: str | None,
    q: str | None,
    artist_or_brand: str | None,
    item_name: str | None,
    catalog_no: str | None,
    barcode: str | None,
    release_year: int | None,
    source_state: str,
    master_state: str,
    cover_state: str,
    slot_state: str,
    preferred_storage_state: str,
    track_state: str,
    music_only: bool,
    sort: str,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    query = _owned_item_select_query() + " WHERE 1 = 1"
    params: list[Any] = []

    if category:
        query += " AND oi.category = ?"
        params.append(category)
    elif music_only:
        query += " AND oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')"

    if domain_code:
        query += " AND oi.domain_code = ?"
        params.append(domain_code)

    if release_type:
        query += " AND oi.release_type = ?"
        params.append(release_type)

    if status:
        query += " AND oi.status = ?"
        params.append(status)

    if q and q.strip():
        q_norm = f"%{q.strip().lower()}%"
        query += """
         AND (
           LOWER(COALESCE(oi.item_name_override, '')) LIKE ?
           OR LOWER(COALESCE(oi.purchase_source, '')) LIKE ?
           OR LOWER(COALESCE(oi.memory_note, '')) LIKE ?
         )
        """
        params.extend([q_norm, q_norm, q_norm])

    if artist_or_brand and artist_or_brand.strip():
        v = f"%{artist_or_brand.strip().lower()}%"
        query += """
         AND (
           LOWER(COALESCE(mid.artist_or_brand, '')) LIKE ?
           OR LOWER(COALESCE(oi.item_name_override, '')) LIKE ?
         )
        """
        params.extend([v, v])

    if item_name and item_name.strip():
        query += " AND LOWER(COALESCE(oi.item_name_override, '')) LIKE ?"
        params.append(f"%{item_name.strip().lower()}%")

    if catalog_no and catalog_no.strip():
        query += " AND LOWER(COALESCE(mid.catalog_no, '')) LIKE ?"
        params.append(f"%{catalog_no.strip().lower()}%")

    if barcode and barcode.strip():
        normalized = "".join(ch for ch in str(barcode).strip() if ch.isalnum()).lower()
        if normalized:
            query += " AND LOWER(REPLACE(REPLACE(COALESCE(mid.barcode, ''), '-', ''), ' ', '')) LIKE ?"
            params.append(f"%{normalized}%")

    if release_year is not None:
        query += " AND mid.release_year = ?"
        params.append(int(release_year))

    source_state_u = str(source_state or "ANY").strip().upper()
    if source_state_u == "MISSING":
        query += """
         AND (
           oi.source_code IS NULL OR TRIM(oi.source_code) = ''
           OR oi.source_external_id IS NULL OR TRIM(oi.source_external_id) = ''
         )
        """
    elif source_state_u == "LINKED":
        query += """
         AND (
           oi.source_code IS NOT NULL AND TRIM(oi.source_code) <> ''
           AND oi.source_external_id IS NOT NULL AND TRIM(oi.source_external_id) <> ''
         )
        """

    master_state_u = str(master_state or "ANY").strip().upper()
    if master_state_u == "MISSING":
        query += " AND oi.linked_album_master_id IS NULL"
    elif master_state_u == "LINKED":
        query += " AND oi.linked_album_master_id IS NOT NULL"

    cover_state_u = str(cover_state or "ANY").strip().upper()
    if cover_state_u == "MISSING":
        query += " AND (mid.cover_image_url IS NULL OR TRIM(mid.cover_image_url) = '')"
    elif cover_state_u == "HAS":
        query += " AND (mid.cover_image_url IS NOT NULL AND TRIM(mid.cover_image_url) <> '')"

    slot_state_u = str(slot_state or "ANY").strip().upper()
    if slot_state_u == "UNSLOTTED":
        query += " AND oi.storage_slot_id IS NULL"
    elif slot_state_u == "SLOTTED":
        query += " AND oi.storage_slot_id IS NOT NULL"

    preferred_storage_state_u = str(preferred_storage_state or "ANY").strip().upper()
    if preferred_storage_state_u == "MISMATCH":
        query += """
         AND (
           oi.preferred_storage_size_group IS NOT NULL
           AND TRIM(oi.preferred_storage_size_group) <> ''
           AND UPPER(TRIM(COALESCE(oi.preferred_storage_size_group, ''))) <> UPPER(TRIM(COALESCE(oi.size_group, '')))
         )
        """
    elif preferred_storage_state_u == "MATCH":
        query += """
         AND (
           oi.preferred_storage_size_group IS NOT NULL
           AND TRIM(oi.preferred_storage_size_group) <> ''
           AND UPPER(TRIM(COALESCE(oi.preferred_storage_size_group, ''))) = UPPER(TRIM(COALESCE(oi.size_group, '')))
         )
        """

    track_state_u = str(track_state or "ANY").strip().upper()
    if track_state_u == "MISSING":
        query += """
         AND (
           mid.track_items_json IS NULL OR TRIM(mid.track_items_json) = '' OR TRIM(mid.track_items_json) = '[]'
         )
         AND (
           mid.track_list_json IS NULL OR TRIM(mid.track_list_json) = '' OR TRIM(mid.track_list_json) = '[]'
         )
        """
    elif track_state_u == "HAS":
        query += """
         AND (
           (mid.track_items_json IS NOT NULL AND TRIM(mid.track_items_json) <> '' AND TRIM(mid.track_items_json) <> '[]')
           OR (mid.track_list_json IS NOT NULL AND TRIM(mid.track_list_json) <> '' AND TRIM(mid.track_list_json) <> '[]')
         )
        """

    if str(sort or "").upper() == "RECENT":
        query += """
          ORDER BY oi.created_at DESC, oi.id DESC
          LIMIT ? OFFSET ?
        """
    else:
        query += """
          ORDER BY
            CASE WHEN oi.order_key IS NULL OR TRIM(oi.order_key) = '' THEN 1 ELSE 0 END,
            oi.order_key ASC,
            CASE WHEN oi.display_rank IS NULL THEN 1 ELSE 0 END,
            oi.display_rank ASC,
            oi.created_at DESC,
            oi.id DESC
          LIMIT ? OFFSET ?
        """
    params.extend([limit, offset])

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()

    return [_normalize_owned_item_row(dict(row)) for row in rows]


def count_owned_items(
    category: str | None,
    domain_code: str | None,
    release_type: str | None,
    status: str | None,
    q: str | None,
    artist_or_brand: str | None,
    item_name: str | None,
    catalog_no: str | None,
    barcode: str | None,
    release_year: int | None,
    source_state: str,
    master_state: str,
    cover_state: str,
    slot_state: str,
    preferred_storage_state: str,
    track_state: str,
    music_only: bool,
) -> int:
    query = """
      SELECT COUNT(*) AS cnt
      FROM owned_item oi
      LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
      WHERE 1 = 1
    """
    params: list[Any] = []

    if category:
        query += " AND oi.category = ?"
        params.append(category)
    elif music_only:
        query += " AND oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')"

    if domain_code:
        query += " AND oi.domain_code = ?"
        params.append(domain_code)

    if release_type:
        query += " AND oi.release_type = ?"
        params.append(release_type)

    if status:
        query += " AND oi.status = ?"
        params.append(status)

    if q and q.strip():
        q_norm = f"%{q.strip().lower()}%"
        query += """
         AND (
           LOWER(COALESCE(oi.item_name_override, '')) LIKE ?
           OR LOWER(COALESCE(oi.purchase_source, '')) LIKE ?
           OR LOWER(COALESCE(oi.memory_note, '')) LIKE ?
         )
        """
        params.extend([q_norm, q_norm, q_norm])

    if artist_or_brand and artist_or_brand.strip():
        v = f"%{artist_or_brand.strip().lower()}%"
        query += """
         AND (
           LOWER(COALESCE(mid.artist_or_brand, '')) LIKE ?
           OR LOWER(COALESCE(oi.item_name_override, '')) LIKE ?
         )
        """
        params.extend([v, v])

    if item_name and item_name.strip():
        query += " AND LOWER(COALESCE(oi.item_name_override, '')) LIKE ?"
        params.append(f"%{item_name.strip().lower()}%")

    if catalog_no and catalog_no.strip():
        query += " AND LOWER(COALESCE(mid.catalog_no, '')) LIKE ?"
        params.append(f"%{catalog_no.strip().lower()}%")

    if barcode and barcode.strip():
        normalized = "".join(ch for ch in str(barcode).strip() if ch.isalnum()).lower()
        if normalized:
            query += " AND LOWER(REPLACE(REPLACE(COALESCE(mid.barcode, ''), '-', ''), ' ', '')) LIKE ?"
            params.append(f"%{normalized}%")

    if release_year is not None:
        query += " AND mid.release_year = ?"
        params.append(int(release_year))

    source_state_u = str(source_state or "ANY").strip().upper()
    if source_state_u == "MISSING":
        query += """
         AND (
           oi.source_code IS NULL OR TRIM(oi.source_code) = ''
           OR oi.source_external_id IS NULL OR TRIM(oi.source_external_id) = ''
         )
        """
    elif source_state_u == "LINKED":
        query += """
         AND (
           oi.source_code IS NOT NULL AND TRIM(oi.source_code) <> ''
           AND oi.source_external_id IS NOT NULL AND TRIM(oi.source_external_id) <> ''
         )
        """

    master_state_u = str(master_state or "ANY").strip().upper()
    if master_state_u == "MISSING":
        query += " AND oi.linked_album_master_id IS NULL"
    elif master_state_u == "LINKED":
        query += " AND oi.linked_album_master_id IS NOT NULL"

    cover_state_u = str(cover_state or "ANY").strip().upper()
    if cover_state_u == "MISSING":
        query += " AND (mid.cover_image_url IS NULL OR TRIM(mid.cover_image_url) = '')"
    elif cover_state_u == "HAS":
        query += " AND (mid.cover_image_url IS NOT NULL AND TRIM(mid.cover_image_url) <> '')"

    slot_state_u = str(slot_state or "ANY").strip().upper()
    if slot_state_u == "UNSLOTTED":
        query += " AND oi.storage_slot_id IS NULL"
    elif slot_state_u == "SLOTTED":
        query += " AND oi.storage_slot_id IS NOT NULL"

    preferred_storage_state_u = str(preferred_storage_state or "ANY").strip().upper()
    if preferred_storage_state_u == "MISMATCH":
        query += """
         AND (
           oi.preferred_storage_size_group IS NOT NULL
           AND TRIM(oi.preferred_storage_size_group) <> ''
           AND UPPER(TRIM(COALESCE(oi.preferred_storage_size_group, ''))) <> UPPER(TRIM(COALESCE(oi.size_group, '')))
         )
        """
    elif preferred_storage_state_u == "MATCH":
        query += """
         AND (
           oi.preferred_storage_size_group IS NOT NULL
           AND TRIM(oi.preferred_storage_size_group) <> ''
           AND UPPER(TRIM(COALESCE(oi.preferred_storage_size_group, ''))) = UPPER(TRIM(COALESCE(oi.size_group, '')))
         )
        """

    track_state_u = str(track_state or "ANY").strip().upper()
    if track_state_u == "MISSING":
        query += """
         AND (
           mid.track_items_json IS NULL OR TRIM(mid.track_items_json) = '' OR TRIM(mid.track_items_json) = '[]'
         )
         AND (
           mid.track_list_json IS NULL OR TRIM(mid.track_list_json) = '' OR TRIM(mid.track_list_json) = '[]'
         )
        """
    elif track_state_u == "HAS":
        query += """
         AND (
           (mid.track_items_json IS NOT NULL AND TRIM(mid.track_items_json) <> '' AND TRIM(mid.track_items_json) <> '[]')
           OR (mid.track_list_json IS NOT NULL AND TRIM(mid.track_list_json) <> '' AND TRIM(mid.track_list_json) <> '[]')
         )
        """

    with get_conn() as conn:
        row = conn.execute(query, params).fetchone()
    return int((row["cnt"] if row else 0) or 0)


def get_collection_dashboard() -> dict[str, Any]:
    move_threshold = (datetime.now(timezone.utc) - timedelta(days=DASHBOARD_MOVE_WINDOW_DAYS)).isoformat()
    with get_conn() as conn:
        summary = conn.execute(
            """
            SELECT
              COUNT(*) AS total_items,
              SUM(CASE WHEN oi.status = 'IN_COLLECTION' THEN 1 ELSE 0 END) AS in_collection_items,
              SUM(CASE WHEN oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL') THEN 1 ELSE 0 END) AS music_items,
              SUM(CASE WHEN oi.category NOT IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL') THEN 1 ELSE 0 END) AS goods_items,
              SUM(CASE WHEN oi.signature_type IS NOT NULL AND oi.signature_type <> 'NONE' THEN 1 ELSE 0 END) AS signed_items,
              SUM(CASE WHEN oi.is_second_hand = 1 THEN 1 ELSE 0 END) AS second_hand_items,
              SUM(CASE WHEN oi.created_at >= datetime('now', '-30 days') THEN 1 ELSE 0 END) AS registered_last_30_days,
              SUM(CASE WHEN oi.status = 'IN_COLLECTION' AND oi.storage_slot_id IS NOT NULL THEN 1 ELSE 0 END) AS slotted_in_collection_items,
              SUM(CASE WHEN oi.status = 'IN_COLLECTION' AND oi.storage_slot_id IS NULL THEN 1 ELSE 0 END) AS unslotted_in_collection_items,
              SUM(
                CASE
                  WHEN oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
                   AND (
                     oi.source_code IS NULL
                     OR TRIM(oi.source_code) = ''
                     OR UPPER(TRIM(oi.source_code)) = 'MANUAL'
                     OR oi.source_external_id IS NULL
                     OR TRIM(oi.source_external_id) = ''
                   )
                  THEN 1
                  ELSE 0
                END
              ) AS source_unlinked_items,
              SUM(
                CASE
                  WHEN oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
                   AND oi.linked_album_master_id IS NULL
                  THEN 1
                  ELSE 0
                END
              ) AS master_unlinked_items,
              SUM(
                CASE
                  WHEN oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
                   AND (mid.cover_image_url IS NULL OR TRIM(mid.cover_image_url) = '')
                  THEN 1
                  ELSE 0
                END
              ) AS cover_missing_items
            FROM owned_item oi
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            """
        ).fetchone()

        standalone_goods_row = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM goods_item
            """
        ).fetchone()

        audio_row = conn.execute(
            """
            SELECT COUNT(DISTINCT l.owned_item_id) AS cnt
            FROM owned_item_digital_link l
            JOIN digital_asset da ON da.id = l.digital_asset_id
            WHERE da.asset_type = 'AUDIO'
            """
        ).fetchone()

        by_category_rows = conn.execute(
            """
            SELECT category, COUNT(*) AS cnt
            FROM owned_item
            GROUP BY category
            ORDER BY cnt DESC, category ASC
            """
        ).fetchall()

        by_status_rows = conn.execute(
            """
            SELECT status, COUNT(*) AS cnt
            FROM owned_item
            GROUP BY status
            ORDER BY cnt DESC, status ASC
            """
        ).fetchall()

        by_domain_rows = conn.execute(
            """
            SELECT COALESCE(NULLIF(domain_code, ''), 'UNASSIGNED') AS value, COUNT(*) AS cnt
            FROM owned_item
            WHERE category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
            GROUP BY COALESCE(NULLIF(domain_code, ''), 'UNASSIGNED')
            ORDER BY cnt DESC, value ASC
            """
        ).fetchall()

        by_release_type_rows = conn.execute(
            """
            SELECT COALESCE(NULLIF(release_type, ''), 'UNASSIGNED') AS value, COUNT(*) AS cnt
            FROM owned_item
            WHERE category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
            GROUP BY COALESCE(NULLIF(release_type, ''), 'UNASSIGNED')
            ORDER BY cnt DESC, value ASC
            """
        ).fetchall()

        by_size_group_rows = conn.execute(
            """
            SELECT COALESCE(NULLIF(size_group, ''), 'UNASSIGNED') AS value, COUNT(*) AS cnt
            FROM owned_item
            GROUP BY COALESCE(NULLIF(size_group, ''), 'UNASSIGNED')
            ORDER BY cnt DESC, value ASC
            """
        ).fetchall()

        by_source_rows = conn.execute(
            """
            SELECT COALESCE(NULLIF(source_code, ''), 'MANUAL') AS value, COUNT(*) AS cnt
            FROM owned_item
            GROUP BY COALESCE(NULLIF(source_code, ''), 'MANUAL')
            ORDER BY cnt DESC, value ASC
            """
        ).fetchall()

        slot_rows = conn.execute(
            """
            SELECT id, slot_code, cabinet_name, cabinet_domain_code, cabinet_group_name, cabinet_group_order, column_code, cell_code, allowed_size_group, is_overflow_zone
            FROM storage_slot
            """
        ).fetchall()

        slot_count_rows = conn.execute(
            """
            SELECT storage_slot_id, COUNT(*) AS cnt
            FROM owned_item
            WHERE status = 'IN_COLLECTION'
              AND storage_slot_id IS NOT NULL
            GROUP BY storage_slot_id
            """
        ).fetchall()

        slot_item_rows = conn.execute(
            """
            SELECT
              oi.storage_slot_id,
              oi.id,
              oi.linked_album_master_id,
              oi.linked_artist_name,
              oi.domain_code,
              oi.order_key,
              oi.display_rank,
              oi.size_group,
              oi.thickness_mm,
              oi.notes,
              oi.item_name_override,
              mid.format_name,
              mid.artist_or_brand,
              mid.release_year,
              mid.released_date,
              mid.disc_count,
              mid.format_items_json,
              am.title AS master_title,
              am.artist_or_brand AS master_artist_or_brand,
              am.sort_artist_name AS master_sort_artist_name,
              am.domain_code AS master_domain_code,
              am.release_year AS master_release_year,
              TRIM(COALESCE(json_extract(am.raw_json, '$.release_date'), json_extract(am.raw_json, '$.master_release_date'), '')) AS master_release_date
            FROM owned_item oi
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
            WHERE oi.status = 'IN_COLLECTION'
              AND oi.storage_slot_id IS NOT NULL
            """
        ).fetchall()

        slot_in_rows = conn.execute(
            """
            SELECT COALESCE(NULLIF(to_slot_code, ''), 'UNASSIGNED') AS slot_code, COUNT(*) AS cnt
            FROM owned_item_location_event
            WHERE created_at >= ?
            GROUP BY COALESCE(NULLIF(to_slot_code, ''), 'UNASSIGNED')
            """,
            (move_threshold,),
        ).fetchall()

        slot_out_rows = conn.execute(
            """
            SELECT COALESCE(NULLIF(from_slot_code, ''), 'UNASSIGNED') AS slot_code, COUNT(*) AS cnt
            FROM owned_item_location_event
            WHERE created_at >= ?
            GROUP BY COALESCE(NULLIF(from_slot_code, ''), 'UNASSIGNED')
            """,
            (move_threshold,),
        ).fetchall()

        unassigned_row = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM owned_item
            WHERE status = 'IN_COLLECTION'
              AND storage_slot_id IS NULL
            """
        ).fetchone()

    slot_count_map = {int(row["storage_slot_id"]): int(row["cnt"] or 0) for row in slot_count_rows if row["storage_slot_id"] is not None}
    slot_item_map: dict[int, list[dict[str, Any]]] = {}
    for row in slot_item_rows:
        storage_slot_id = int(row["storage_slot_id"] or 0)
        if storage_slot_id <= 0:
            continue
        slot_item_map.setdefault(storage_slot_id, []).append(dict(row))
    slot_first_item_hint_map = _build_collection_dashboard_first_item_hints(slot_item_map)
    slot_in_map = {str(row["slot_code"] or "UNASSIGNED"): int(row["cnt"] or 0) for row in slot_in_rows}
    slot_out_map = {str(row["slot_code"] or "UNASSIGNED"): int(row["cnt"] or 0) for row in slot_out_rows}
    structured_slots = [dict(row) for row in slot_rows]
    recent_move_total = count_ops_home_recent_moved_items()
    recent_move_items = list_ops_home_recent_moved_items(limit=12)
    for item in structured_slots:
        item["display_name"] = _storage_slot_display_name(item)
        item["count"] = int(slot_count_map.get(int(item["id"]), 0))
        item["recent_in_count"] = int(slot_in_map.get(str(item["slot_code"] or ""), 0))
        item["recent_out_count"] = int(slot_out_map.get(str(item["slot_code"] or ""), 0))
        item.update(build_storage_slot_occupancy_summary(item, slot_item_map.get(int(item["id"]), [])))
        item.update(slot_first_item_hint_map.get(int(item["id"]), {}))
    structured_slots.sort(key=_storage_slot_sort_key)

    legacy_goods_items = int((summary["goods_items"] if summary else 0) or 0)
    standalone_goods_items = int((standalone_goods_row["cnt"] if standalone_goods_row else 0) or 0)

    return {
        "total_items": int((summary["total_items"] if summary else 0) or 0),
        "in_collection_items": int((summary["in_collection_items"] if summary else 0) or 0),
        "music_items": int((summary["music_items"] if summary else 0) or 0),
        "goods_items": legacy_goods_items + standalone_goods_items,
        "signed_items": int((summary["signed_items"] if summary else 0) or 0),
        "second_hand_items": int((summary["second_hand_items"] if summary else 0) or 0),
        "audio_mapped_items": int((audio_row["cnt"] if audio_row else 0) or 0),
        "registered_last_30_days": int((summary["registered_last_30_days"] if summary else 0) or 0),
        "slotted_in_collection_items": int((summary["slotted_in_collection_items"] if summary else 0) or 0),
        "unslotted_in_collection_items": int((summary["unslotted_in_collection_items"] if summary else 0) or 0),
        "source_unlinked_items": int((summary["source_unlinked_items"] if summary else 0) or 0),
        "master_unlinked_items": int((summary["master_unlinked_items"] if summary else 0) or 0),
        "cover_missing_items": int((summary["cover_missing_items"] if summary else 0) or 0),
        "by_category": [
            {"category": str(row["category"]), "count": int(row["cnt"] or 0)}
            for row in by_category_rows
        ],
        "by_status": [
            {"status": str(row["status"]), "count": int(row["cnt"] or 0)}
            for row in by_status_rows
        ],
        "by_domain": [
            {"value": str(row["value"]), "count": int(row["cnt"] or 0)}
            for row in by_domain_rows
        ],
        "by_release_type": [
            {"value": str(row["value"]), "count": int(row["cnt"] or 0)}
            for row in by_release_type_rows
        ],
        "by_size_group": [
            {"value": str(row["value"]), "count": int(row["cnt"] or 0)}
            for row in by_size_group_rows
        ],
        "by_source": [
            {"value": str(row["value"]), "count": int(row["cnt"] or 0)}
            for row in by_source_rows
        ],
        "movement_window_days": DASHBOARD_MOVE_WINDOW_DAYS,
        "recent_move_total": int(recent_move_total),
        "recent_moves": [
            {
                "id": int(row["owned_item_id"]),
                "owned_item_id": int(row["owned_item_id"]),
                "label_id": str(row.get("label_id") or _build_label_id(str(row["category"] or ""), int(row["owned_item_id"]))),
                "category": str(row["category"] or ""),
                "item_title": str(row["item_title"]) if row["item_title"] is not None else None,
                "artist_or_brand": str(row["artist_or_brand"]) if row["artist_or_brand"] is not None else None,
                "cover_image_url": str(row["cover_image_url"]) if row["cover_image_url"] is not None else None,
                "movement_kind": "MOVE",
                "from_slot_code": str(row["previous_slot_code"]) if row.get("previous_slot_code") is not None else None,
                "from_display_name": str(row["previous_slot_display_name"]) if row.get("previous_slot_display_name") is not None else None,
                "to_slot_code": str(row["current_slot_code"]) if row.get("current_slot_code") is not None else None,
                "to_display_name": str(row["current_slot_display_name"]) if row.get("current_slot_display_name") is not None else None,
                "note": None,
                "created_at": str(row["created_at"] or ""),
            }
            for row in recent_move_items
        ],
        "by_slot": [
            {
                "slot_code": str(row["slot_code"]),
                "cabinet_name": str(row["cabinet_name"]) if row.get("cabinet_name") is not None else None,
                "cabinet_domain_code": _normalize_domain_code_value(row.get("cabinet_domain_code")),
                "cabinet_group_name": str(row["cabinet_group_name"]) if row.get("cabinet_group_name") is not None else None,
                "cabinet_group_order": int(row["cabinet_group_order"]) if row.get("cabinet_group_order") not in (None, "") else None,
                "column_code": str(row["column_code"]) if row.get("column_code") is not None else None,
                "cell_code": str(row["cell_code"]) if row.get("cell_code") is not None else None,
                "display_name": str(row["display_name"]) if row.get("display_name") is not None else None,
                "allowed_size_group": str(row["allowed_size_group"]) if row.get("allowed_size_group") is not None else None,
                "is_overflow_zone": bool(row["is_overflow_zone"]),
                "count": int(row["count"] or 0),
                "recent_in_count": int(row.get("recent_in_count") or 0),
                "recent_out_count": int(row.get("recent_out_count") or 0),
                "capacity_mm": int(row.get("capacity_mm") or 0),
                "used_thickness_mm": int(row.get("used_thickness_mm") or 0),
                "free_thickness_mm": int(row.get("free_thickness_mm") or 0),
                "occupancy_ratio": float(row.get("occupancy_ratio") or 0.0),
                "occupancy_percent": int(row.get("occupancy_percent") or 0),
                "first_item_artist_or_brand": str(row["first_item_artist_or_brand"]) if row.get("first_item_artist_or_brand") is not None else None,
                "first_item_title": str(row["first_item_title"]) if row.get("first_item_title") is not None else None,
                "first_item_release_year": int(row["first_item_release_year"]) if row.get("first_item_release_year") not in (None, "") else None,
            }
            for row in structured_slots
        ]
        + [
            {
                "slot_code": "UNASSIGNED",
                "cabinet_name": "미배치",
                "cabinet_domain_code": None,
                "cabinet_group_name": None,
                "cabinet_group_order": None,
                "column_code": None,
                "cell_code": None,
                "display_name": "미배치",
                "allowed_size_group": None,
                "is_overflow_zone": False,
                "count": int((unassigned_row["cnt"] if unassigned_row else 0) or 0),
                "recent_in_count": int(slot_in_map.get("UNASSIGNED", 0)),
                "recent_out_count": int(slot_out_map.get("UNASSIGNED", 0)),
                "capacity_mm": 0,
                "used_thickness_mm": 0,
                "free_thickness_mm": 0,
                "occupancy_ratio": 0.0,
                "occupancy_percent": 0,
            }
        ],
    }


def get_music_shelf_window(owned_item_id: int, window: int) -> dict[str, Any] | None:
    half_window = max(1, int(window))
    with get_conn() as conn:
        _backfill_order_keys(conn)

        selected = conn.execute(
            """
            SELECT id, order_key
            FROM owned_item
            WHERE id = ?
              AND status = 'IN_COLLECTION'
              AND category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
            """,
            (owned_item_id,),
        ).fetchone()
        if selected is None:
            return None

        center_order_key = str(selected["order_key"] or "").strip()
        if not center_order_key:
            _rebalance_in_collection_order(conn)
            selected = conn.execute(
                """
                SELECT id, order_key
                FROM owned_item
                WHERE id = ?
                  AND status = 'IN_COLLECTION'
                  AND category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
                """,
                (owned_item_id,),
            ).fetchone()
            if selected is None:
                return None
            center_order_key = str(selected["order_key"] or "").strip()
            if not center_order_key:
                return None

        prev_row = conn.execute(
            """
            SELECT oi.id
            FROM owned_item oi
            WHERE oi.status = 'IN_COLLECTION'
              AND oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
              AND (
                oi.order_key < ?
                OR (oi.order_key = ? AND oi.id < ?)
              )
            ORDER BY oi.order_key DESC, oi.id DESC
            LIMIT 1
            """,
            (center_order_key, center_order_key, owned_item_id),
        ).fetchone()

        next_row = conn.execute(
            """
            SELECT oi.id
            FROM owned_item oi
            WHERE oi.status = 'IN_COLLECTION'
              AND oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
              AND (
                oi.order_key > ?
                OR (oi.order_key = ? AND oi.id > ?)
              )
            ORDER BY oi.order_key ASC, oi.id ASC
            LIMIT 1
            """,
            (center_order_key, center_order_key, owned_item_id),
        ).fetchone()

        select_query = _owned_item_select_query()

        before_rows = conn.execute(
            select_query
            + """
            WHERE oi.status = 'IN_COLLECTION'
              AND oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
              AND (
                oi.order_key < ?
                OR (oi.order_key = ? AND oi.id < ?)
              )
            ORDER BY oi.order_key DESC, oi.id DESC
            LIMIT ?
            """,
            (center_order_key, center_order_key, owned_item_id, half_window),
        ).fetchall()

        center_row = conn.execute(
            select_query
            + """
            WHERE oi.id = ?
            LIMIT 1
            """,
            (owned_item_id,),
        ).fetchone()
        if center_row is None:
            return None

        after_rows = conn.execute(
            select_query
            + """
            WHERE oi.status = 'IN_COLLECTION'
              AND oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
              AND (
                oi.order_key > ?
                OR (oi.order_key = ? AND oi.id > ?)
              )
            ORDER BY oi.order_key ASC, oi.id ASC
            LIMIT ?
            """,
            (center_order_key, center_order_key, owned_item_id, half_window),
        ).fetchall()

    before_items = [_normalize_owned_item_row(dict(row)) for row in before_rows]
    before_items.reverse()
    center_item = _normalize_owned_item_row(dict(center_row))
    after_items = [_normalize_owned_item_row(dict(row)) for row in after_rows]

    return {
        "center_owned_item_id": int(owned_item_id),
        "previous_owned_item_id": int(prev_row["id"]) if prev_row else None,
        "next_owned_item_id": int(next_row["id"]) if next_row else None,
        "items": [*before_items, center_item, *after_items],
    }


def get_owned_item_list_row(owned_item_id: int) -> dict[str, Any] | None:
    query = _owned_item_select_query() + " WHERE oi.id = ? LIMIT 1"
    with get_conn() as conn:
        row = conn.execute(query, (owned_item_id,)).fetchone()
    if row is None:
        return None
    return _normalize_owned_item_row(dict(row))


# `get_album_master_binding_for_owned_item` lives in app/db/album_master_read.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `get_album_master_domain_hint` lives in app/db/album_master_read.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `list_owned_items_by_album_master` lives in app/db/album_master_read.py and is
# re-exported from this package's __init__ at the bottom of the file.


def list_owned_items_by_copy_group(copy_group_key: str) -> list[dict[str, Any]]:
    key = str(copy_group_key or "").strip()
    if not key:
        return []

    query = (
        _owned_item_select_query()
        + """
        WHERE oi.copy_group_key = ?
        ORDER BY
          CASE WHEN oi.order_key IS NULL OR TRIM(oi.order_key) = '' THEN 1 ELSE 0 END,
          oi.order_key ASC,
          CASE WHEN oi.display_rank IS NULL THEN 1 ELSE 0 END,
          oi.display_rank ASC,
          oi.created_at DESC,
          oi.id DESC
        """
    )
    with get_conn() as conn:
        rows = conn.execute(query, (key,)).fetchall()
    return [_normalize_owned_item_row(dict(row)) for row in rows]


def list_owned_items_by_source_external_ids(source_code: str, source_external_ids: list[str]) -> list[dict[str, Any]]:
    cleaned = sorted({str(v).strip() for v in source_external_ids if str(v).strip()})
    if not source_code or not cleaned:
        return []

    placeholders = ",".join("?" for _ in cleaned)
    query = (
        _owned_item_select_query()
        + f"""
        WHERE oi.source_code = ?
          AND oi.source_external_id IN ({placeholders})
          AND oi.status IN ('IN_COLLECTION', 'LOANED', 'ARCHIVED')
        ORDER BY
          CASE WHEN oi.order_key IS NULL OR TRIM(oi.order_key) = '' THEN 1 ELSE 0 END,
          oi.order_key ASC,
          CASE WHEN oi.display_rank IS NULL THEN 1 ELSE 0 END,
          oi.display_rank ASC,
          oi.created_at DESC,
          oi.id DESC
        """
    )
    params: list[Any] = [source_code, *cleaned]
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_normalize_owned_item_row(dict(row)) for row in rows]


def get_owned_counts_by_source(source_code: str, source_external_ids: list[str]) -> dict[str, int]:
    cleaned = [str(v).strip() for v in source_external_ids if str(v).strip()]
    if not source_code or not cleaned:
        return {}

    placeholders = ",".join("?" for _ in cleaned)
    query = f"""
      SELECT source_external_id, COUNT(*) AS cnt
      FROM owned_item
      WHERE source_code = ?
        AND source_external_id IN ({placeholders})
        AND status IN ('IN_COLLECTION', 'LOANED', 'ARCHIVED')
      GROUP BY source_external_id
    """
    params: list[Any] = [source_code, *cleaned]

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return {str(r["source_external_id"]): int(r["cnt"]) for r in rows}


def get_owned_item_track_list(owned_item_id: int) -> list[str]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT track_list_json
            FROM music_item_detail
            WHERE owned_item_id = ?
            """,
            (owned_item_id,),
        ).fetchone()

    if row is None or row["track_list_json"] is None:
        return []

    raw = str(row["track_list_json"])
    if not raw.strip():
        return []
    try:
        values = json.loads(raw)
    except json.JSONDecodeError:
        return []

    if not isinstance(values, list):
        return []
    return [str(v).strip() for v in values if str(v).strip()]


def list_metadata_sync_candidates(
    source_code: str | None,
    only_missing: bool,
    limit: int,
    offset: int = 0,
) -> list[dict[str, Any]]:
    query = """
      SELECT
        oi.id,
        oi.category,
        oi.source_code,
        oi.source_external_id,
        mid.format_name,
        mid.artist_or_brand,
        mid.release_year,
        mid.released_date,
        mid.barcode,
        mid.label_name,
        mid.catalog_no,
        mid.cover_image_url,
        mid.track_list_json,
        mid.media_type,
        mid.genres_json,
        mid.styles_json,
        mid.disc_count,
        mid.speed_rpm,
        mid.has_obi,
        mid.runout_matrix,
        mid.runout_matrix_json,
        mid.pressing_country,
        mid.source_notes,
        mid.credits_json,
        mid.identifier_items_json,
        mid.image_items_json,
        mid.company_items_json,
        mid.series_json,
        mid.format_items_json,
        mid.track_items_json,
        mid.label_items_json,
        mid.is_promotional_not_for_sale,
        mid.sleeve_condition AS cover_condition,
        mid.media_condition AS disc_condition
      FROM owned_item oi
      LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
      WHERE oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
        AND oi.source_code IS NOT NULL
        AND TRIM(COALESCE(oi.source_external_id, '')) <> ''
    """
    params: list[Any] = []
    if source_code:
        query += " AND oi.source_code = ?"
        params.append(source_code)

    if only_missing:
        query += """
          AND (
            mid.owned_item_id IS NULL
            OR TRIM(COALESCE(mid.label_name, '')) = ''
            OR TRIM(COALESCE(mid.catalog_no, '')) = ''
            OR TRIM(COALESCE(mid.cover_image_url, '')) = ''
            OR TRIM(COALESCE(mid.barcode, '')) = ''
            OR TRIM(COALESCE(mid.media_type, '')) = ''
            OR mid.genres_json IS NULL
            OR TRIM(COALESCE(mid.genres_json, '')) = ''
            OR TRIM(COALESCE(mid.genres_json, '')) = '[]'
            OR mid.styles_json IS NULL
            OR TRIM(COALESCE(mid.styles_json, '')) = ''
            OR TRIM(COALESCE(mid.styles_json, '')) = '[]'
            OR mid.track_list_json IS NULL
            OR TRIM(COALESCE(mid.track_list_json, '')) = ''
            OR TRIM(COALESCE(mid.track_list_json, '')) = '[]'
          )
        """

    query += """
      ORDER BY oi.updated_at ASC, oi.id ASC
      LIMIT ? OFFSET ?
    """
    params.extend([max(1, int(limit)), max(0, int(offset))])

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()

    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        raw_tracks = item.pop("track_list_json", None)
        if raw_tracks:
            try:
                parsed = json.loads(raw_tracks)
                item["track_list"] = [str(v).strip() for v in parsed if str(v).strip()] if isinstance(parsed, list) else []
            except json.JSONDecodeError:
                item["track_list"] = []
        else:
            item["track_list"] = []

        raw_genres = item.pop("genres_json", None)
        if raw_genres:
            try:
                parsed_genres = json.loads(raw_genres)
                item["genres"] = [str(v).strip() for v in parsed_genres if str(v).strip()] if isinstance(parsed_genres, list) else []
            except json.JSONDecodeError:
                item["genres"] = []
        else:
            item["genres"] = []

        raw_styles = item.pop("styles_json", None)
        if raw_styles:
            try:
                parsed_styles = json.loads(raw_styles)
                item["styles"] = [str(v).strip() for v in parsed_styles if str(v).strip()] if isinstance(parsed_styles, list) else []
            except json.JSONDecodeError:
                item["styles"] = []
        else:
            item["styles"] = []

        runout_values: list[str] = []
        raw_runout_json = item.pop("runout_matrix_json", None)
        if raw_runout_json:
            try:
                parsed_runout = json.loads(raw_runout_json)
                runout_values = [str(v).strip() for v in parsed_runout if str(v).strip()] if isinstance(parsed_runout, list) else []
            except json.JSONDecodeError:
                runout_values = []
        if not runout_values:
            legacy_runout = str(item.get("runout_matrix") or "").strip()
            if legacy_runout:
                runout_values = [p.strip() for p in legacy_runout.split("|") if p.strip()]
        item["runout_matrix"] = runout_values

        def _parse_json_string_list(raw: Any) -> list[str]:
            if not raw:
                return []
            try:
                parsed = json.loads(str(raw))
            except json.JSONDecodeError:
                return []
            if not isinstance(parsed, list):
                return []
            return [str(v).strip() for v in parsed if str(v).strip()]

        def _parse_json_dict_list(raw: Any) -> list[dict[str, Any]]:
            if not raw:
                return []
            try:
                parsed = json.loads(str(raw))
            except json.JSONDecodeError:
                return []
            if not isinstance(parsed, list):
                return []
            return [row for row in parsed if isinstance(row, dict)]

        item["credits"] = _parse_json_string_list(item.pop("credits_json", None))
        item["identifier_items"] = _parse_json_dict_list(item.pop("identifier_items_json", None))
        item["image_items"] = _parse_json_dict_list(item.pop("image_items_json", None))
        item["company_items"] = _parse_json_dict_list(item.pop("company_items_json", None))
        item["series"] = _parse_json_string_list(item.pop("series_json", None))
        item["format_items"] = _parse_json_dict_list(item.pop("format_items_json", None))
        item["track_items"] = _parse_json_dict_list(item.pop("track_items_json", None))
        item["label_items"] = _parse_json_dict_list(item.pop("label_items_json", None))

        item["is_promotional_not_for_sale"] = bool(item.get("is_promotional_not_for_sale"))
        if item.get("has_obi") is not None:
            item["has_obi"] = True if int(item.get("has_obi")) == 1 else None
        out.append(item)
    return out


def upsert_music_detail(owned_item_id: int, music_detail: dict[str, Any]) -> None:
    now = utc_now_iso()
    with get_conn() as conn:
        _upsert_music_item_detail_in_conn(
            conn,
            owned_item_id=owned_item_id,
            music_detail=music_detail,
            now=now,
        )
        conn.execute(
            """
            UPDATE owned_item
            SET updated_at = ?
            WHERE id = ?
            """,
            (now, owned_item_id),
        )


def list_owned_item_track_links(owned_item_id: int) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
              l.id AS link_id,
              l.track_no,
              l.note,
              l.created_at,
              a.id AS digital_asset_id,
              a.file_path,
              a.duration_sec
            FROM owned_item_digital_link l
            JOIN digital_asset a ON a.id = l.digital_asset_id
            WHERE l.owned_item_id = ? AND l.link_type = 'TRACK'
            ORDER BY l.track_no ASC, l.id ASC
            """,
            (owned_item_id,),
        ).fetchall()

    return [dict(r) for r in rows]


def list_owned_item_audio_directory_links(owned_item_id: int) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
              l.id AS link_id,
              l.note,
              l.created_at,
              a.id AS digital_asset_id,
              a.file_path,
              a.metadata_json
            FROM owned_item_digital_link l
            JOIN digital_asset a ON a.id = l.digital_asset_id
            WHERE l.owned_item_id = ?
              AND l.link_type = 'FULL_ALBUM'
              AND a.asset_type = 'AUDIO'
            ORDER BY l.id DESC
            """,
            (owned_item_id,),
        ).fetchall()

    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        raw_meta = item.pop("metadata_json", None)
        if raw_meta:
            try:
                parsed = json.loads(str(raw_meta))
            except json.JSONDecodeError:
                parsed = {}
        else:
            parsed = {}
        item["metadata_json"] = parsed if isinstance(parsed, dict) else {}
        out.append(item)
    return out


def delete_owned_item_audio_directory_links(owned_item_id: int) -> int:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT l.digital_asset_id
            FROM owned_item_digital_link l
            JOIN digital_asset a ON a.id = l.digital_asset_id
            WHERE l.owned_item_id = ?
              AND l.link_type = 'FULL_ALBUM'
              AND a.asset_type = 'AUDIO'
            """,
            (owned_item_id,),
        ).fetchall()
        asset_ids = sorted({int(r["digital_asset_id"]) for r in rows if r["digital_asset_id"] is not None})

        cur = conn.execute(
            """
            DELETE FROM owned_item_digital_link
            WHERE id IN (
                SELECT l.id
                FROM owned_item_digital_link l
                JOIN digital_asset a ON a.id = l.digital_asset_id
                WHERE l.owned_item_id = ?
                  AND l.link_type = 'FULL_ALBUM'
                  AND a.asset_type = 'AUDIO'
            )
            """,
            (owned_item_id,),
        )
        deleted = int(cur.rowcount or 0)

        if asset_ids:
            placeholders = ",".join("?" for _ in asset_ids)
            conn.execute(
                f"""
                DELETE FROM digital_asset
                WHERE id IN ({placeholders})
                  AND id NOT IN (SELECT DISTINCT digital_asset_id FROM owned_item_digital_link)
                """,
                asset_ids,
            )

    return deleted


def delete_owned_item_track_links(owned_item_id: int) -> int:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT digital_asset_id
            FROM owned_item_digital_link
            WHERE owned_item_id = ? AND link_type = 'TRACK'
            """,
            (owned_item_id,),
        ).fetchall()
        asset_ids = sorted({int(r["digital_asset_id"]) for r in rows if r["digital_asset_id"] is not None})

        cur = conn.execute(
            """
            DELETE FROM owned_item_digital_link
            WHERE owned_item_id = ? AND link_type = 'TRACK'
            """,
            (owned_item_id,),
        )
        deleted = int(cur.rowcount or 0)

        if asset_ids:
            placeholders = ",".join("?" for _ in asset_ids)
            conn.execute(
                f"""
                DELETE FROM digital_asset
                WHERE id IN ({placeholders})
                  AND id NOT IN (SELECT DISTINCT digital_asset_id FROM owned_item_digital_link)
                """,
                asset_ids,
            )

    return deleted


# `upsert_album_master` lives in app/db/album_master_core.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `normalize_album_master_source_id` lives in app/db/album_master_core.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `promote_album_master_source` lives in app/db/album_master_core.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `_snapshot_album_master_record` lives in app/db/album_master_core.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `_snapshot_member_link_records` lives in app/db/album_master_core.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `_snapshot_external_ref_records` lives in app/db/album_master_core.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `merge_album_masters` lives in app/db/album_master_core.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `set_owned_item_linked_album_master` lives in app/db/album_master_read.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `_build_album_master_filter_sql` lives in app/db/album_master_read.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `list_album_masters` lives in app/db/album_master_read.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `count_album_masters` lives in app/db/album_master_read.py and is
# re-exported from this package's __init__ at the bottom of the file.


def update_owned_item_slot(owned_item_id: int, storage_slot_id: int | None, movement_note: str | None = None) -> None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT storage_slot_id, display_rank FROM owned_item WHERE id = ? LIMIT 1",
            (owned_item_id,),
        ).fetchone()
        previous_storage_slot_id = row["storage_slot_id"] if row is not None else None
        previous_display_rank = row["display_rank"] if row is not None else None
        now = utc_now_iso()
        next_display_rank = previous_display_rank if previous_storage_slot_id == storage_slot_id else None
        conn.execute(
            """
            UPDATE owned_item
            SET storage_slot_id = ?, display_rank = ?, updated_at = ?
            WHERE id = ?
            """,
            (storage_slot_id, next_display_rank, now, owned_item_id),
        )
        if row is not None and previous_storage_slot_id != storage_slot_id:
            _log_owned_item_location_event_in_conn(
                conn,
                owned_item_id=owned_item_id,
                from_storage_slot_id=int(previous_storage_slot_id) if previous_storage_slot_id is not None else None,
                to_storage_slot_id=int(storage_slot_id) if storage_slot_id is not None else None,
                note=movement_note,
                now=now,
            )


def inherit_owned_item_domain_from_slot_if_missing(owned_item_id: int, storage_slot_id: int | None) -> str | None:
    if storage_slot_id is None:
        return None
    with get_conn() as conn:
        owned_row = conn.execute(
            "SELECT domain_code FROM owned_item WHERE id = ? LIMIT 1",
            (int(owned_item_id),),
        ).fetchone()
        if owned_row is None:
            return None
        current_domain_code = _normalize_domain_code_value(owned_row["domain_code"])
        if current_domain_code not in (None, "UNKNOWN"):
            return current_domain_code
        slot_row = conn.execute(
            "SELECT cabinet_domain_code FROM storage_slot WHERE id = ? LIMIT 1",
            (int(storage_slot_id),),
        ).fetchone()
        inherited_domain_code = _normalize_domain_code_value(slot_row["cabinet_domain_code"]) if slot_row is not None else None
        if inherited_domain_code in (None, "UNKNOWN"):
            return current_domain_code
        conn.execute(
            "UPDATE owned_item SET domain_code = ?, updated_at = ? WHERE id = ?",
            (inherited_domain_code, utc_now_iso(), int(owned_item_id)),
        )
        return inherited_domain_code


def restore_owned_item_previous_slot(owned_item_id: int) -> dict[str, Any] | None:
    row = get_owned_item_location_snapshot(int(owned_item_id))
    if row is None:
        return None
    previous_slot_code = str(row.get("previous_slot_code") or "").strip()
    if not previous_slot_code:
        return {"owned_item_id": int(owned_item_id), "storage_slot_id": None, "restored": False, "reason": "이전 위치 이력이 없습니다."}
    next_slot_id: int | None = None
    if previous_slot_code != "UNASSIGNED":
        slot = get_storage_slot_by_code(previous_slot_code)
        if slot is None:
            return {"owned_item_id": int(owned_item_id), "restored": False, "reason": "이전 위치 칸을 찾지 못했습니다."}
        next_slot_id = int(slot["id"])
    update_owned_item_slot(int(owned_item_id), next_slot_id, movement_note="직전 위치 복구")
    return {"owned_item_id": int(owned_item_id), "storage_slot_id": next_slot_id, "restored": True}


def move_owned_item_order(owned_item_id: int, target_owned_item_id: int, position: str) -> str:
    if owned_item_id == target_owned_item_id:
        raise ValueError("owned_item_id and target_owned_item_id must be different")
    if position not in {"BEFORE", "AFTER"}:
        raise ValueError("position must be BEFORE or AFTER")

    with get_conn() as conn:
        src_row = conn.execute(
            "SELECT id, status FROM owned_item WHERE id = ?",
            (owned_item_id,),
        ).fetchone()
        if src_row is None:
            raise LookupError("owned_item not found")

        target_row = conn.execute(
            "SELECT id, status FROM owned_item WHERE id = ?",
            (target_owned_item_id,),
        ).fetchone()
        if target_row is None:
            raise LookupError("target owned_item not found")

        src_status = str(src_row["status"] or "")
        target_status = str(target_row["status"] or "")
        if src_status != "IN_COLLECTION" or target_status != "IN_COLLECTION":
            raise ValueError("order move is available only for IN_COLLECTION items")

        _backfill_order_keys(conn)

        for _ in range(2):
            rows = conn.execute(
                """
                SELECT id, order_key
                FROM owned_item
                WHERE status = 'IN_COLLECTION'
                  AND id <> ?
                ORDER BY order_key ASC, id ASC
                """,
                (owned_item_id,),
            ).fetchall()

            ordered = [
                {"id": int(r["id"]), "value": _parse_order_value(r["order_key"])}
                for r in rows
            ]
            if any(row["value"] is None for row in ordered):
                _rebalance_in_collection_order(conn)
                continue
            idx = next((i for i, row in enumerate(ordered) if row["id"] == target_owned_item_id), None)
            if idx is None:
                raise LookupError("target owned_item not found in IN_COLLECTION order")

            if position == "BEFORE":
                left = ordered[idx - 1]["value"] if idx > 0 else None
                right = ordered[idx]["value"]
            else:
                left = ordered[idx]["value"]
                right = ordered[idx + 1]["value"] if idx + 1 < len(ordered) else None

            if left is not None and right is not None and left >= right:
                _rebalance_in_collection_order(conn)
                continue

            next_value = _compute_between_order_value(left, right)
            if next_value is None:
                _rebalance_in_collection_order(conn)
                continue

            new_order_key = _format_order_value(next_value)
            conn.execute(
                """
                UPDATE owned_item
                SET order_key = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_order_key, utc_now_iso(), owned_item_id),
            )
            return new_order_key

    raise RuntimeError("order move failed after rebalance")


def realign_owned_item_order_after_slot_move(owned_item_id: int, target_slot_id: int) -> str:
    target_slot_id = int(target_slot_id)
    moved_row = get_owned_item(owned_item_id)
    if moved_row is None:
        raise LookupError("owned_item not found")
    if str(moved_row.get("status") or "").strip().upper() != "IN_COLLECTION":
        raise ValueError("slot move order realign is available only for IN_COLLECTION items")
    if int(moved_row.get("storage_slot_id") or 0) != target_slot_id:
        raise ValueError("owned_item is not assigned to the target slot")

    target_rows = list_owned_items_for_storage_slot(target_slot_id, limit=1000, offset=0)
    ordered_ids = [int(row["id"]) for row in target_rows if int(row.get("id") or 0) > 0]
    if owned_item_id not in ordered_ids:
        raise LookupError("owned_item not found in target slot order")

    anchor_owned_item_id: int | None = None
    anchor_position: str | None = None
    target_index = ordered_ids.index(owned_item_id)
    if target_index > 0:
        anchor_owned_item_id = ordered_ids[target_index - 1]
        anchor_position = "AFTER"
    elif target_index + 1 < len(ordered_ids):
        anchor_owned_item_id = ordered_ids[target_index + 1]
        anchor_position = "BEFORE"

    if anchor_owned_item_id is None:
        with get_conn() as conn:
            _backfill_order_keys(conn)
            slot_rows = conn.execute(
                """
                SELECT DISTINCT ss.*
                FROM storage_slot ss
                JOIN owned_item oi ON oi.storage_slot_id = ss.id
                WHERE oi.status = 'IN_COLLECTION'
                  AND oi.storage_slot_id IS NOT NULL
                """
            ).fetchall()
            slot_dicts = [dict(row) for row in slot_rows]
            slot_dicts.sort(key=_storage_slot_sort_key)
            slot_order = [int(row["id"]) for row in slot_dicts if row["id"] is not None]
            slot_index = next((idx for idx, slot_id in enumerate(slot_order) if slot_id == target_slot_id), None)

            if slot_index is not None:
                for previous_slot_id in reversed(slot_order[:slot_index]):
                    previous_rows = list_owned_items_for_storage_slot(previous_slot_id, limit=1000, offset=0)
                    previous_ids = [int(row["id"]) for row in previous_rows if int(row.get("id") or 0) > 0]
                    if previous_ids:
                        anchor_owned_item_id = previous_ids[-1]
                        anchor_position = "AFTER"
                        break

            if anchor_owned_item_id is None and slot_index is not None:
                for next_slot_id in slot_order[slot_index + 1 :]:
                    next_rows = list_owned_items_for_storage_slot(next_slot_id, limit=1000, offset=0)
                    next_ids = [int(row["id"]) for row in next_rows if int(row.get("id") or 0) > 0]
                    if next_ids:
                        anchor_owned_item_id = next_ids[0]
                        anchor_position = "BEFORE"
                        break

            if anchor_owned_item_id is None:
                unassigned_row = conn.execute(
                    """
                    SELECT order_key
                    FROM owned_item
                    WHERE status = 'IN_COLLECTION'
                      AND storage_slot_id IS NULL
                      AND id <> ?
                    ORDER BY
                      CASE WHEN order_key IS NULL OR TRIM(order_key) = '' THEN 1 ELSE 0 END,
                      order_key ASC,
                      id ASC
                    LIMIT 1
                    """,
                    (owned_item_id,),
                ).fetchone()
                right_value = _parse_order_value(unassigned_row["order_key"]) if unassigned_row else None
                next_value = _compute_between_order_value(None, right_value)
                if next_value is None and right_value is not None:
                    _rebalance_in_collection_order(conn)
                    refreshed_row = conn.execute(
                        """
                        SELECT order_key
                        FROM owned_item
                        WHERE status = 'IN_COLLECTION'
                          AND storage_slot_id IS NULL
                          AND id <> ?
                        ORDER BY
                          CASE WHEN order_key IS NULL OR TRIM(order_key) = '' THEN 1 ELSE 0 END,
                          order_key ASC,
                          id ASC
                        LIMIT 1
                        """,
                        (owned_item_id,),
                    ).fetchone()
                    refreshed_value = _parse_order_value(refreshed_row["order_key"]) if refreshed_row else None
                    next_value = _compute_between_order_value(None, refreshed_value)
                new_order_key = (
                    _format_order_value(next_value)
                    if next_value is not None
                    else _next_order_key_in_conn(conn)
                )
                conn.execute(
                    """
                    UPDATE owned_item
                    SET order_key = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (new_order_key, utc_now_iso(), owned_item_id),
                )
                return new_order_key

    if anchor_owned_item_id is None or anchor_position is None:
        raise RuntimeError("slot move order realign failed without anchor")
    return move_owned_item_order(
        owned_item_id=owned_item_id,
        target_owned_item_id=anchor_owned_item_id,
        position=anchor_position,
    )


def move_owned_item_slot_display_rank(
    storage_slot_id: int,
    owned_item_id: int,
    target_owned_item_id: int,
    position: str,
) -> int:
    if owned_item_id == target_owned_item_id:
        raise ValueError("owned_item_id and target_owned_item_id must be different")
    if position not in {"BEFORE", "AFTER"}:
        raise ValueError("position must be BEFORE or AFTER")

    with get_conn() as conn:
        source_row = conn.execute(
            "SELECT id, status, storage_slot_id FROM owned_item WHERE id = ? LIMIT 1",
            (owned_item_id,),
        ).fetchone()
        if source_row is None:
            raise LookupError("owned_item not found")
        target_row = conn.execute(
            "SELECT id, status, storage_slot_id FROM owned_item WHERE id = ? LIMIT 1",
            (target_owned_item_id,),
        ).fetchone()
        if target_row is None:
            raise LookupError("target owned_item not found")

    source_slot_id = int(source_row["storage_slot_id"] or 0) if source_row["storage_slot_id"] is not None else 0
    target_slot_id = int(target_row["storage_slot_id"] or 0) if target_row["storage_slot_id"] is not None else 0
    if source_slot_id <= 0 or target_slot_id <= 0:
        raise ValueError("slot order move is available only for assigned items")
    if source_slot_id != int(storage_slot_id) or target_slot_id != int(storage_slot_id):
        raise ValueError("slot order move is available only within the current slot")
    if str(source_row["status"] or "") != "IN_COLLECTION" or str(target_row["status"] or "") != "IN_COLLECTION":
        raise ValueError("slot order move is available only for IN_COLLECTION items")

    current_rows = list_owned_items_for_storage_slot(int(storage_slot_id), limit=1000, offset=0)
    ordered_ids = [int(row["id"]) for row in current_rows if int(row.get("id") or 0) > 0]
    if owned_item_id not in ordered_ids:
        raise LookupError("owned_item not found in current slot")
    if target_owned_item_id not in ordered_ids:
        raise LookupError("target owned_item not found in current slot")

    ordered_ids = [item_id for item_id in ordered_ids if item_id != owned_item_id]
    target_index = ordered_ids.index(target_owned_item_id)
    insert_index = target_index if position == "BEFORE" else target_index + 1
    ordered_ids.insert(insert_index, owned_item_id)

    now = utc_now_iso()
    display_rank = 0
    with get_conn() as conn:
        for index, item_id in enumerate(ordered_ids, start=1):
            rank_value = index * 10
            conn.execute(
                """
                UPDATE owned_item
                SET display_rank = ?, updated_at = ?
                WHERE id = ?
                """,
                (rank_value, now, item_id),
            )
            if item_id == owned_item_id:
                display_rank = rank_value

    if display_rank <= 0:
        raise RuntimeError("slot order move failed")
    return display_rank


# `insert_digital_link` lives in app/db/digital_link.py and is
# re-exported from this package's __init__ at the bottom of the file.


# --------------------------------------------------------------------------- #
# Domain submodule re-exports (db.py package split)
# --------------------------------------------------------------------------- #
# The auth-account surface lives in app.db.auth_account. Re-exporting it
# here keeps the public `db.list_auth_accounts(...)` API identical to the
# pre-split module so neither callers nor tests need touching.
from .auth_account import (  # noqa: E402
    _ensure_auth_account_table,
    delete_auth_account,
    get_auth_account_by_username,
    list_auth_accounts,
    upsert_auth_account,
)
from .cache import (  # noqa: E402
    get_cached_external_response,
    purge_expired_external_responses,
    touch_cached_external_response_expiry,
    upsert_cached_external_response,
)
from .purchase_import import (  # noqa: E402
    _ensure_purchase_import_queue_table,
    _find_purchase_import_duplicate_in_conn,
    _migrate_purchase_import_queue_allow_file_upload,
    _purchase_import_cmp_float,
    _purchase_import_cmp_text,
    _purchase_import_queue_allows_extended_vendors,
    _purchase_import_queue_allows_file_upload,
    _purchase_import_row_matches_duplicate,
    _purchase_import_vendor_check_sql,
    count_purchase_import_rows,
    find_purchase_import_duplicate_row,
    get_purchase_import_row,
    has_purchase_import_for_source_ref,
    insert_purchase_import_rows,
    list_purchase_import_rows,
    update_purchase_import_row,
)
from .customer_track_request import (  # noqa: E402
    count_customer_track_requests,
    create_customer_track_request,
    get_customer_track_request,
    list_customer_track_requests,
    update_customer_track_request,
)
from .storage_slot import (  # noqa: E402
    _cleanup_overflow_slots,
    _derive_storage_slot_parts,
    _migrate_storage_slot_allow_goods,
    _storage_slot_allows_goods,
    delete_storage_cabinet,
    get_storage_slot,
    get_storage_slot_by_code,
    list_owned_items_for_storage_slot,
    list_storage_slots,
    register_storage_cabinet_slots,
    upsert_storage_slot,
)
from .goods_item import (  # noqa: E402
    _build_goods_item_with_mappings,
    _build_goods_search_where,
    _goods_category_check_sql,
    _goods_item_select_query,
    _goods_relation_type_check_sql,
    _goods_status_check_sql,
    _list_goods_item_album_master_mappings_in_conn,
    _list_goods_item_artist_mappings_in_conn,
    _list_goods_item_collectible_relations_in_conn,
    _list_goods_item_label_mappings_in_conn,
    _normalize_goods_category_value,
    _normalize_goods_item_row,
    _normalize_goods_mapping_text,
    _normalize_goods_relation_type_value,
    _normalize_goods_status_value,
    _replace_goods_item_collectible_relations_in_conn,
    _replace_goods_item_mappings_in_conn,
    count_goods_items,
    create_goods_item,
    delete_goods_item,
    get_goods_item,
    list_goods_artist_name_candidates,
    list_goods_label_name_candidates,
    replace_goods_item_collectible_relations,
    replace_goods_item_mappings,
    search_goods_collectible_targets,
    search_goods_items,
    update_goods_item,
)
from .cabinet_camera import (  # noqa: E402
    delete_cabinet_camera,
    get_cabinet_camera,
    get_cabinet_camera_by_cabinet,
    list_cabinet_cameras,
    upsert_cabinet_camera,
)
from .classification_option import (  # noqa: E402
    _seed_classification_options,
    list_classification_options,
    upsert_classification_option,
)
from .ingestion_batch import (  # noqa: E402
    bulk_finalize_csv_ingest,
    bulk_insert_review_queue,
    finalize_batch,
    insert_batch,
    insert_review_queue,
    list_review_queue,
)
from .auto_backup import (  # noqa: E402
    AUTO_BACKUP_SETTING_KEYS,
    get_auto_backup_settings,
    record_auto_backup_result,
    save_auto_backup_settings,
)
from .album_master_merge_history import (  # noqa: E402
    list_album_master_merge_history,
    rollback_latest_album_master_merge,
)
from .album_master_external_ref import (  # noqa: E402
    ensure_album_master_external_ref,
    get_album_master_id_by_external_ref,
    list_album_master_external_refs,
)
from .album_master_correction import (  # noqa: E402
    get_album_master_correction_state,
    update_album_master_correction,
)
from .album_master_duplicates import (  # noqa: E402
    _album_master_source_priority,
    list_duplicate_album_masters,
)
# album_master_core MUST be re-exported BEFORE album_master_member,
# because album_master_member.bind_album_master_members imports
# `_sync_album_master_domain_code_in_conn` from the package surface
# at module-load time, and that helper now lives in album_master_core.
from .album_master_core import (  # noqa: E402
    _snapshot_album_master_record,
    _snapshot_external_ref_records,
    _snapshot_member_link_records,
    _sync_album_master_domain_code_in_conn,
    merge_album_masters,
    normalize_album_master_source_id,
    promote_album_master_source,
    upsert_album_master,
)
from .album_master_member import (  # noqa: E402
    album_master_exists,
    bind_album_master_members,
    delete_album_master,
    list_album_master_members,
    update_album_master_sort_artist_name,
)
from .album_master_tracks import (  # noqa: E402
    list_album_master_track_matches,
)
from .digital_link import (  # noqa: E402
    insert_digital_link,
)
from .location_recommendation import (  # noqa: E402
    recommend_barcode_candidate_locations,
    recommend_owned_item_location,
)
from .album_master_read import (  # noqa: E402
    count_album_masters,
    get_album_master_binding_for_owned_item,
    get_album_master_domain_hint,
    list_album_masters,
    list_owned_items_by_album_master,
    set_owned_item_linked_album_master,
)
