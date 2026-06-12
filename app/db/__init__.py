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
DOMAIN_CODES = ("KOREA", "JAPAN", "GREATER_CHINA", "WESTERN", "OTHER_ASIA", "WORLD", "WORLD_OTHER", "UNKNOWN")
CABINET_SORT_POLICIES = ("ARTIST_RELEASE_TITLE", "LABEL_ID", "TITLE_RELEASE")
GOODS_RELATION_TYPE_CODES = ("SERIES", "VARIANT", "SET_MEMBER", "RELATED", "PROMO_FOR")
LEGACY_DOMAIN_CODE_MAP = {
    "KOREAN": "KOREA",
    "JPOP": "JAPAN",
    "OTHER": "WORLD",
    "WORLD_OTHER": "WORLD",
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

# ── Connection management (extracted to app.db.connection) ──
from .connection import get_conn, get_write_conn, utc_now_iso, invalidate_read_conn_cache  # noqa: F401
from .connection import _ensure_parent_dir, _ensure_app_setting_table  # noqa: F401


def _domain_code_check_sql() -> str:
    return "', '".join(DOMAIN_CODES)


def _size_group_check_sql() -> str:
    return "', '".join(SIZE_GROUP_CODES)


# CD 계열 미디어 타입 (DVD, Blu-ray, CD-ROM 포함)
CD_LIKE_MEDIA_TYPES = ("CD", "CDr", "SACD", "Digital", "DVD", "Blu-ray", "CD-ROM")
CD_LIKE_MEDIA_SQL = ", ".join(f"'{m}'" for m in CD_LIKE_MEDIA_TYPES)

VINYL_LIKE_MEDIA_TYPES = ("Vinyl", "LP", '7"', '10"', "All Media")
VINYL_LIKE_MEDIA_SQL = ", ".join(f"'{m}'" for m in VINYL_LIKE_MEDIA_TYPES)


def slot_size_ok_sql() -> str:
    """
    슬롯 규격 판정 SQL (1=OK, 0=MISMATCH).
    mid.media_type + mid.format_items_json + oi.size_group vs ss.allowed_size_group 비교.

    규칙:
      - LP-Style Packaging (CD/Cassette 등): LP 슬롯 허용
      - Box Set: 기본 규격 또는 OVERSIZE 허용
      - CD 계열(CD/CDr/SACD/Digital/DVD/Blu-ray/CD-ROM):
          Digibook 또는 DVD Size 패키징 → OVERSIZE 필요
          그 외 → STD
      - Vinyl 계열(Vinyl/LP/7"/10"/All Media): oi.size_group 기준 (LP/LP7/LP10)
      - Cassette → CASSETTE
      - 8-Track Cartridge → 8TRACK
      - Reel-To-Reel → REEL_TO_REEL
      - 미지정/기타 → 판정 제외 (1 반환)
    """
    cd_sql = CD_LIKE_MEDIA_SQL
    vinyl_sql = VINYL_LIKE_MEDIA_SQL
    lp_style_pkg = """(
        UPPER(COALESCE(mid.format_items_json,'')) LIKE '%LP-STYLE PACKAGING%'
        OR UPPER(COALESCE(mid.format_items_json,'')) LIKE '%LP STYLE PACKAGING%'
        OR UPPER(COALESCE(mid.format_name,'')) LIKE '%LP-STYLE PACKAGING%'
        OR UPPER(COALESCE(mid.format_name,'')) LIKE '%LP STYLE PACKAGING%'
      )"""
    return f"""
    CASE
      WHEN mid.media_type IS NULL OR TRIM(mid.media_type) = '' THEN 1

      -- LP-Style Packaging: CD/Cassette 등이 LP 크기 슬리브로 포장 → LP 슬롯 허용
      WHEN {lp_style_pkg}
        THEN CASE WHEN UPPER(TRIM(COALESCE(ss.allowed_size_group,''))) IN ('LP','OVERSIZE')
             THEN 1 ELSE 0 END

      -- Box Set: 기본 규격 또는 OVERSIZE 모두 허용
      WHEN UPPER(COALESCE(mid.format_items_json,'')) LIKE '%"BOX SET"%'
        OR UPPER(COALESCE(mid.format_items_json,'')) LIKE '%BOX SET%'
        OR UPPER(COALESCE(mid.format_name,'')) LIKE '%BOX SET%'
        THEN CASE WHEN
          UPPER(TRIM(COALESCE(ss.allowed_size_group,''))) = 'OVERSIZE'
          OR (mid.media_type IN ({cd_sql})
              AND UPPER(TRIM(COALESCE(ss.allowed_size_group,''))) = 'STD')
          OR (mid.media_type = 'Cassette'
              AND UPPER(TRIM(COALESCE(ss.allowed_size_group,''))) = 'CASSETTE')
          OR (mid.media_type IN ({vinyl_sql})
              AND UPPER(TRIM(COALESCE(ss.allowed_size_group,'')))
                  = UPPER(COALESCE(NULLIF(TRIM(oi.size_group),''),'LP')))
          THEN 1 ELSE 0 END

      -- Reel-To-Reel
      WHEN mid.media_type = 'Reel-To-Reel'
        THEN CASE WHEN UPPER(TRIM(COALESCE(ss.allowed_size_group,''))) = 'REEL_TO_REEL'
             THEN 1 ELSE 0 END

      -- 8-Track Cartridge
      WHEN mid.media_type = '8-Track Cartridge'
        THEN CASE WHEN UPPER(TRIM(COALESCE(ss.allowed_size_group,''))) = '8TRACK'
             THEN 1 ELSE 0 END

      -- Cassette
      WHEN mid.media_type = 'Cassette'
        THEN CASE WHEN UPPER(TRIM(COALESCE(ss.allowed_size_group,''))) = 'CASSETTE'
             THEN 1 ELSE 0 END

      -- CD 계열 (DVD, Blu-ray, CD-ROM 포함)
      WHEN mid.media_type IN ({cd_sql})
        THEN CASE
          WHEN UPPER(COALESCE(mid.format_items_json,'')) LIKE '%DIGIBOOK%'
            OR UPPER(COALESCE(mid.format_items_json,'')) LIKE '%DVD SIZE%'
            THEN CASE WHEN UPPER(TRIM(COALESCE(ss.allowed_size_group,''))) = 'OVERSIZE'
                 THEN 1 ELSE 0 END
          ELSE
            CASE WHEN UPPER(TRIM(COALESCE(ss.allowed_size_group,''))) = 'STD'
                 THEN 1 ELSE 0 END
          END

      -- Vinyl 계열
      WHEN mid.media_type IN ({vinyl_sql})
        THEN CASE WHEN UPPER(TRIM(COALESCE(ss.allowed_size_group,'')))
                      = UPPER(COALESCE(NULLIF(TRIM(oi.size_group),''),'LP'))
             THEN 1 ELSE 0 END

      ELSE 1
    END
    """


def _normalize_domain_code_sql(expr: str) -> str:
    return f"""
    CASE UPPER(TRIM(COALESCE({expr}, '')))
      WHEN 'KOREAN' THEN 'KOREA'
      WHEN 'JPOP' THEN 'JAPAN'
      WHEN 'OTHER' THEN 'WORLD'
      WHEN 'KOREA' THEN 'KOREA'
      WHEN 'JAPAN' THEN 'JAPAN'
      WHEN 'GREATER_CHINA' THEN 'GREATER_CHINA'
      WHEN 'WESTERN' THEN 'WESTERN'
      WHEN 'OTHER_ASIA' THEN 'OTHER_ASIA'
      WHEN 'WORLD_OTHER' THEN 'WORLD'
      WHEN 'WORLD' THEN 'WORLD'
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


def _normalize_title_sort_text(text: Any) -> str:
    """앨범 타이틀 정렬용 — 관사(The/A/An) 제외 후 casefold."""
    return _normalize_artist_sort_text(text)


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
    domain = str(row.get("domain_code") or row.get("master_domain_code") or "").strip().upper()
    is_korea = domain == "KOREA"
    is_non_latin_domain = domain in ("KOREA", "JAPAN", "GREATER_CHINA", "OTHER_ASIA")
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
    # 비라틴 도메인(KOREA 제외)이나 Latin 도메인에서는 한글 후보를 먼저 건너뜀
    # — WESTERN 등 라틴 도메인 아이템에 한글 아티스트명이 잘못 등록된 경우 방어
    latin_result = None
    for candidate in candidates:
        normalized = _normalize_artist_sort_text(candidate)
        if not normalized:
            continue
        if not is_non_latin_domain and _contains_hangul(candidate):
            # 라틴 도메인인데 한글 후보 → 마지막 수단으로만 사용
            if latin_result is None:
                latin_result = normalized
            continue
        return normalized
    return latin_result or ""


def _owned_item_storage_sort_key(
    row: dict[str, Any],
    korean_artist_by_master_id: dict[int, str] | None = None,
    sort_policy: str = "ARTIST_RELEASE_TITLE",
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
    title_value = _normalize_title_sort_text(row.get("master_title") or row.get("item_name_override"))
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
    common_tail = (
        1 if not order_key else 0,
        order_key,
        int(row.get("id") or 0),
    )
    # TITLE_RELEASE: 상품명(관사 제외) → 발매일 → 아티스트 순
    if sort_policy == "TITLE_RELEASE":
        artist_value = _preferred_owned_item_artist_sort_value(row, korean_artist_by_master_id)
        return (
            1,
            title_value,
            master_release_sort_value,
            1 if not released_date_value else 0,
            released_date_value or "9999-99-99",
            artist_value,
            *common_tail,
        )
    artist_value = _preferred_owned_item_artist_sort_value(row, korean_artist_by_master_id)
    title_first_group = _title_first_group_artist_key(artist_value)
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
    slot_sort_policy = _normalize_cabinet_sort_policy_value(slot.get("cabinet_sort_policy"))
    if slot_sort_policy == "LABEL_ID":
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
    return _owned_item_storage_sort_key(previous_row, korean_artist_by_master_id, slot_sort_policy) != _owned_item_storage_sort_key(
        next_row,
        korean_artist_by_master_id,
        slot_sort_policy,
    )


# `_extract_collection_dashboard_release_year` lives in app/db/collection_dashboard.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `_build_collection_dashboard_first_item_hints` lives in app/db/collection_dashboard.py and is
# re-exported from this package's __init__ at the bottom of the file.


# ── Connection management (extracted to app.db.connection) ──
# Public symbols: get_conn, get_write_conn, utc_now_iso.
# Internal helpers: _ensure_parent_dir, _ensure_app_setting_table.
# _build_label_id / _parse_label_id_query stay in __init__.py (use __init__ constants).
# Re-exported so ``from app.db import get_conn`` keeps working.


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
              cabinet_sort_policy TEXT NOT NULL DEFAULT 'ARTIST_RELEASE_TITLE' CHECK (cabinet_sort_policy IN ('ARTIST_RELEASE_TITLE', 'LABEL_ID', 'TITLE_RELEASE')),
              cabinet_domain_code TEXT CHECK (cabinet_domain_code IN ('KOREA', 'JAPAN', 'GREATER_CHINA', 'WESTERN', 'OTHER_ASIA', 'WORLD', 'WORLD_OTHER', 'UNKNOWN')),
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
              domain_code TEXT CHECK (domain_code IN ('KOREA', 'JAPAN', 'GREATER_CHINA', 'WESTERN', 'OTHER_ASIA', 'WORLD', 'WORLD_OTHER', 'UNKNOWN')),
              release_type TEXT CHECK (release_type IN ('ALBUM', 'EP', 'SINGLE')),
              item_name_override TEXT,
              quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
              is_second_hand INTEGER NOT NULL DEFAULT 1,
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
              format_name TEXT,
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
              disc_type TEXT,
              package_contents TEXT,
              is_limited_edition INTEGER,
              edition_number TEXT,
              local_image_items_json TEXT,
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
              domain_code TEXT CHECK (domain_code IN ('KOREA', 'JAPAN', 'GREATER_CHINA', 'WESTERN', 'OTHER_ASIA', 'WORLD', 'WORLD_OTHER', 'UNKNOWN')),
              release_year INTEGER,
              source_domain_code TEXT CHECK (source_domain_code IN ('KOREA', 'JAPAN', 'GREATER_CHINA', 'WESTERN', 'OTHER_ASIA', 'WORLD', 'WORLD_OTHER', 'UNKNOWN')),
              source_release_year INTEGER,
              override_domain_code TEXT CHECK (override_domain_code IN ('KOREA', 'JAPAN', 'GREATER_CHINA', 'WESTERN', 'OTHER_ASIA', 'WORLD', 'WORLD_OTHER', 'UNKNOWN')),
              override_release_year INTEGER,
              override_note TEXT,
              spotify_album_id TEXT,
              spotify_album_uri TEXT,
              spotify_matched_at TEXT,
              spotify_image_url TEXT,
              review_text TEXT,
              review_source TEXT,
              review_url TEXT,
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
              weather_temp_c REAL,
              weather_description TEXT,
              weather_code INTEGER,
              season TEXT,
              playback_deck TEXT,
              played_at TEXT,
              returned_at TEXT,
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

            CREATE TABLE IF NOT EXISTS track_tag (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              tag_type TEXT NOT NULL,
              tag_value TEXT NOT NULL,
              owned_item_id INTEGER,
              spotify_track_id TEXT,
              created_by TEXT,
              created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_track_tag_type_value ON track_tag (tag_type, tag_value);
            CREATE INDEX IF NOT EXISTS idx_track_tag_owned ON track_tag (owned_item_id);
            CREATE INDEX IF NOT EXISTS idx_track_tag_spotify ON track_tag (spotify_track_id);

            CREATE TABLE IF NOT EXISTS table_device (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              table_number TEXT NOT NULL UNIQUE,
              device_label TEXT,
              device_id TEXT UNIQUE,
              is_active INTEGER NOT NULL DEFAULT 1,
              notes TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS track_reaction (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              track_request_id INTEGER NOT NULL,
              table_number TEXT NOT NULL,
              reaction_type TEXT NOT NULL,
              free_text TEXT,
              created_at TEXT NOT NULL
            );

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
        _cleanup_pop_korean_sort_names(conn)
        _seed_classification_options(conn)


# Startup cleanup 함수들은 도메인별 서브모듈로 분리됨:
#   startup_cleanup/domain_code.py  — domain_code 교정 (ManiaDB, 한글신호, 수동확인, 동기화)
#   startup_cleanup/artist_name.py  — 아티스트명 교정 (팝 한글정렬명, 라틴명 복원, 한글명 제거)
# _column_exists / _table_exists 가 정의된 이후(아래)에 import 된다.


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
            _cleanup_pop_korean_sort_names(conn)
            _sync_album_master_domain_from_owned_items(conn)
            _restore_latin_artist_names_from_ext_ref(conn)
            _fix_maniadb_domain_corrections(conn)
            _fix_known_domain_corrections(conn)
            _cleanup_pop_hangul_artist_names(conn)
            _seed_classification_options(conn)
            return

        _apply_migrations(conn)
        _ensure_app_setting_table(conn)
        _ensure_recent_feed_indexes(conn)
        _seed_metadata_sources(conn)
        _cleanup_overflow_slots(conn)
        _cleanup_pop_korean_sort_names(conn)
        _sync_album_master_domain_from_owned_items(conn)
        _restore_latin_artist_names_from_ext_ref(conn)
        _fix_maniadb_domain_corrections(conn)
        _fix_known_domain_corrections(conn)
        _cleanup_pop_hangul_artist_names(conn)
        _seed_classification_options(conn)
    finally:
        conn.close()


# `get_auto_backup_settings`, `save_auto_backup_settings`, and
# `record_auto_backup_result` live in app/db/auto_backup.py and are
# re-exported from this package's __init__ at the bottom of the file.


from ._schema_helpers import _column_exists, _table_exists

# Startup cleanup 도메인 분리 — _column_exists / _table_exists 는
# _schema_helpers 에서 제공하므로 import 시 순환참조가 발생하지 않는다.
from .startup_cleanup.domain_code import (  # noqa: E402
    _fix_hangul_artist_domain_corrections,
    _fix_known_domain_corrections,
    _fix_maniadb_domain_corrections,
    _sync_album_master_domain_from_owned_items,
)
from .startup_cleanup.artist_name import (  # noqa: E402
    _cleanup_pop_hangul_artist_names,
    _cleanup_pop_korean_sort_names,
    _restore_latin_artist_names_from_ext_ref,
)

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


# Schema migration functions live in app/db/schema_migration.py
# (SCHEMA_VERSION, _read_user_version, _apply_migrations re-exported below)


# `_next_order_key_in_conn` lives in app/db/order_keys.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `_backfill_order_keys` lives in app/db/order_keys.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `_compute_between_order_value` lives in app/db/order_keys.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `_rebalance_in_collection_order` lives in app/db/order_keys.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `resequence_in_collection_order` lives in app/db/order_keys.py and is
# re-exported from this package's __init__ at the bottom of the file.


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


# `insert_owned_item` lives in app/db/owned_item_write.py and is
# re-exported from this package's __init__ at the bottom of the file.


# owned_item 상세 upsert → app/db/owned_item_detail.py (re-exported below)


# `_sync_owned_item_classifications_in_conn` lives in app/db/owned_item_write.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `update_owned_item` lives in app/db/owned_item_write.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `bulk_update_owned_items` lives in app/db/owned_item_write.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `delete_owned_item` lives in app/db/owned_item_write.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `search_operator_catalog` lives in app/db/operator_search.py and is
# re-exported from this package's __init__ at the bottom of the file.


# owned_item SELECT 쿼리/정규화 → app/db/owned_item_select.py (re-exported below)


# `list_owned_items` lives in app/db/owned_item_query.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `count_owned_items` lives in app/db/owned_item_query.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `get_collection_dashboard` lives in app/db/collection_dashboard.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `get_music_shelf_window` lives in app/db/music_shelf_window.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `get_owned_counts_by_source` lives in app/db/music_shelf_window.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `get_owned_item_track_list` lives in app/db/owned_item_track.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `list_metadata_sync_candidates` lives in app/db/metadata_sync.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `upsert_music_detail` lives in app/db/metadata_sync.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `list_owned_item_track_links`,
# `list_owned_item_audio_directory_links`,
# `delete_owned_item_audio_directory_links`, and
# `delete_owned_item_track_links` live in
# app/db/owned_item_track_links.py and are re-exported from this
# package's __init__ at the bottom of the file.


# `update_owned_item_slot` lives in app/db/owned_item_slot.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `inherit_owned_item_domain_from_slot_if_missing` lives in app/db/owned_item_slot.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `restore_owned_item_previous_slot` lives in app/db/owned_item_slot.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `move_owned_item_order` lives in app/db/owned_item_order.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `realign_owned_item_order_after_slot_move` lives in app/db/owned_item_order.py and is
# re-exported from this package's __init__ at the bottom of the file.


# `move_owned_item_slot_display_rank` lives in app/db/owned_item_order.py and is
# re-exported from this package's __init__ at the bottom of the file.


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
# owned_item_track MUST be re-exported BEFORE customer_track_request
# AND owned_item_slot, because both modules import
# `get_owned_item_location_snapshot` from the package surface at
# module-load time.
from .owned_item_track import (  # noqa: E402
    get_owned_item_location_snapshot,
    get_owned_item_track_list,
)
# owned_item_select / owned_item_detail MUST be re-exported BEFORE owned_item_read
# (owned_item_read imports _normalize_owned_item_row at module load time).
from .owned_item_select import (  # noqa: E402
    _owned_item_select_query,
    _normalize_owned_item_row,
)
# owned_item_detail MUST be re-exported BEFORE owned_item_write / metadata_sync.
from .owned_item_detail import (  # noqa: E402
    _upsert_music_item_detail_in_conn,
    _upsert_goods_item_detail_in_conn,
)

# owned_item_read MUST be re-exported BEFORE customer_track_request
# (which imports `get_owned_item_detail` at module-load time) AND
# BEFORE owned_item_order (which imports `get_owned_item` at
# module-load time).
from .owned_item_read import (  # noqa: E402
    get_owned_item,
    get_owned_item_detail,
    get_sibling_tracklist,
)
from .customer_track_request import (  # noqa: E402
    count_customer_track_requests,
    create_customer_track_request,
    get_customer_track_request,
    list_customer_track_requests,
    update_customer_track_request,
)
from .track_tag import (  # noqa: E402
    _ensure_track_tag_table,
    delete_track_tag,
    find_tracks_by_tag,
    insert_track_tag,
    list_track_tags,
)
from .table_device import (  # noqa: E402
    _ensure_table_device_table,
    deactivate_table_device,
    get_table_by_device,
    list_table_devices,
    register_table_device,
)
from .cafe_playlist import (  # noqa: E402
    _ensure_playlist_tables,
    add_playlist_item,
    create_playlist,
    delete_playlist,
    get_next_playlist_item,
    get_playlist,
    get_playlist_items,
    list_playlists,
    remove_playlist_item,
)
from .local_music_index import (  # noqa: E402
    _ensure_index_table,
    rebuild_index,
    search_local_index,
    get_index_stats,
)
from .track_reaction import (  # noqa: E402
    _ensure_track_reaction_table,
    insert_track_reaction,
    list_reactions_by_request,
)
# owned_item_slot MUST be re-exported BEFORE storage_slot, because
# storage_slot.py imports `_log_owned_item_location_event_in_conn`
# from the package surface at module-load time, and that helper now
# lives in owned_item_slot.
from .label_domain_registry import (  # noqa: E402
    lookup_label_domain,
    upsert_label_domain,
)
from .album_master_local_link import (  # noqa: E402
    get_local_link,
    set_local_link,
    delete_local_link,
    list_tracks_for_link,
    find_cover_path,
    auto_match as auto_match_local,
)
from .owned_item_slot import (  # noqa: E402
    _derive_location_movement_kind,
    _location_slot_snapshot_in_conn,
    _log_owned_item_location_event_in_conn,
    inherit_owned_item_domain_from_slot_if_missing,
    list_owned_item_location_events,
    list_recent_location_events,
    restore_owned_item_previous_slot,
    update_owned_item_slot,
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
# order_keys MUST be re-exported BEFORE any consumer slice
# (location_recommendation, owned_item_order, music_shelf_window,
# owned_item_write). It depends on list_owned_items_for_storage_slot
# from storage_slot, so it loads right after storage_slot.
from .order_keys import (  # noqa: E402
    _backfill_order_keys,
    _compute_between_order_value,
    _format_order_value,
    _next_order_key_in_conn,
    _parse_order_value,
    _rebalance_in_collection_order,
    resequence_in_collection_order,
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

# schema_migration MUST be re-exported AFTER purchase_import, storage_slot,
# order_keys, and goods_item — _apply_migrations_legacy depends on their helpers.
from .schema_migration import (  # noqa: E402
    SCHEMA_VERSION,
    _apply_migrations,
    _read_user_version,
    _run_pending_migrations,
    _apply_migrations_legacy,
    _MIGRATIONS_BY_VERSION,
    _owned_item_allows_goods,
    _migrate_owned_item_allow_goods,
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
from .audit_log import (  # noqa: E402
    log_audit_event,
    list_audit_log,
)
from .album_master_external_ref import (  # noqa: E402
    ensure_album_master_external_ref,
    get_album_master_id_by_external_ref,
    list_album_master_external_refs,
)
from .album_master_correction import (  # noqa: E402
    bulk_update_album_master_domain,
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
    get_album_master_basic,
    merge_album_masters,
    normalize_album_master_source_id,
    promote_album_master_source,
    update_album_master_genres,
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
from .owned_item_track_links import (  # noqa: E402
    delete_owned_item_audio_directory_links,
    delete_owned_item_track_links,
    list_owned_item_audio_directory_links,
    list_owned_item_track_links,
)
from .owned_item_copy_group import (  # noqa: E402
    list_owned_items_by_copy_group,
    list_owned_items_by_source_external_ids,
    set_owned_item_copy_group,
)
from .owned_item_order import (  # noqa: E402
    move_owned_item_order,
    move_owned_item_slot_display_rank,
    realign_owned_item_order_after_slot_move,
)
# owned_item_query MUST be re-exported AFTER album_master_read and
# owned_item_copy_group — it pulls list_owned_items_by_* /
# get_album_master_* helpers from the package surface.
from .owned_item_query import (  # noqa: E402
    count_owned_items,
    get_owned_item_list_row,
    list_owned_items,
)
from .ops_home_recent import (  # noqa: E402
    _build_ops_home_recent_item,
    count_ops_home_recent_moved_items,
    count_ops_home_recent_registered_items,
    get_ops_home_feed,
    get_ops_home_recent_sections,
    list_ops_home_recent_moved_items,
    list_ops_home_recent_registered_items,
)
from .operator_search import (  # noqa: E402
    search_operator_catalog,
)
from .cafe_playlist import (  # noqa: E402
    rollback_customer_track_request,
    get_shelf_location_by_owned_item,
)
from .metadata_sync import (  # noqa: E402
    list_metadata_sync_candidates,
    upsert_music_detail,
)
# music_shelf_window MUST be re-exported AFTER owned_item_query —
# it pulls get_owned_item_list_row from the package surface.
from .music_shelf_window import (  # noqa: E402
    get_music_shelf_window,
    get_owned_counts_by_source,
)
# collection_dashboard MUST be re-exported AFTER ops_home_recent —
# it pulls count_ops_home_recent_moved_items / list_ops_home_recent_moved_items
# from the package surface.
from .collection_dashboard import (  # noqa: E402
    get_collection_dashboard,
    invalidate_dashboard_cache,
)
# owned_item_write MUST be the LAST re-export — it depends on
# helpers from album_master_core, owned_item_slot,
# owned_item_copy_group, and owned_item_track which are all loaded
# earlier in this list.
from .owned_item_write import (  # noqa: E402
    _sync_owned_item_classifications_in_conn,
    bulk_update_music_detail,
    bulk_update_owned_items,
    delete_owned_item,
    insert_owned_item,
    update_owned_item,
)


from .error_log import (  # noqa: E402
    insert_error_log,
    list_error_log,
    get_unread_error_count,
    acknowledge_error_log,
)
from .perf_log import (  # noqa: E402
    insert_perf_log,
    list_perf_log_aggregated,
    list_perf_log_detail,
)
from .account_permission import (  # noqa: E402
    ALL_PERMISSION_KEYS,
    _ensure_permission_tables,
    seed_default_permissions,
    list_permissions,
    list_role_permissions,
    set_role_permissions,
    list_account_permissions,
    set_account_permission,
    delete_account_permission,
    clear_account_permissions,
    check_permission,
    get_effective_permissions,
)
