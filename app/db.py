from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Generator

from .config import get_settings

ORDER_KEY_WIDTH = 12
ORDER_KEY_STEP = 1024
SQLITE_BUSY_TIMEOUT_MS = 30_000
DASHBOARD_MOVE_WINDOW_DAYS = 14
SIZE_GROUP_CODES = ("STD", "BOOK", "LP", "OVERSIZE", "GOODS")
DOMAIN_CODES = ("KOREA", "JAPAN", "GREATER_CHINA", "WESTERN", "OTHER_ASIA", "WORLD_OTHER", "UNKNOWN")
CABINET_SORT_POLICIES = ("ARTIST_RELEASE_TITLE", "LABEL_ID")
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
_UNSET = object()


def _domain_code_check_sql() -> str:
    return "', '".join(DOMAIN_CODES)


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


def _derive_storage_slot_parts(
    slot_code: str | None,
    allowed_size_group: str | None,
    is_overflow_zone: bool,
) -> tuple[str | None, str | None, str | None]:
    code = str(slot_code or "").strip()
    size_group = str(allowed_size_group or "").strip().upper() or None
    if is_overflow_zone:
        return ("Overflow", size_group or None, "보조")

    if not code:
        return (None, None, None)

    if "/" in code:
        parts = [part.strip() for part in code.split("/") if part.strip()]
        if len(parts) >= 3:
            return (parts[0], parts[1], "/".join(parts[2:]))
        if len(parts) == 2:
            return (parts[0], parts[1], None)

    if code.count("-") >= 2:
        parts = [part.strip() for part in code.split("-") if part.strip()]
        if len(parts) >= 3:
            return ("-".join(parts[:-2]), parts[-2], parts[-1])

    return (code, None, None)


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
            parts.append(f"{column_code}층")
        if cell_code:
            parts.append(f"{cell_code}칸")
        return " / ".join(parts)

    if slot_code.startswith("OVERFLOW-"):
        return f"Overflow / {slot_code.removeprefix('OVERFLOW-')}"
    return slot_code or "-"


def _storage_slot_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    slot_code = str(row.get("slot_code") or "").strip()
    if slot_code == "UNASSIGNED":
        return (2, ["unassigned"], [""], [""], [""], 0)
    if bool(row.get("is_overflow_zone")):
        return (1, _natural_sort_key(row.get("cabinet_name") or "Overflow"), _natural_sort_key(row.get("allowed_size_group")), [""], [""], int(row.get("id") or 0))
    return (
        0,
        _natural_sort_key(row.get("cabinet_name")),
        _natural_sort_key(row.get("column_code")),
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
    return value.casefold()


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
    title_value = _normalize_artist_sort_text(row.get("master_title") or row.get("item_name_override"))
    order_key = str(row.get("order_key") or "").strip()
    display_rank = row.get("display_rank")
    try:
        display_rank_value = int(display_rank) if display_rank is not None else None
    except (TypeError, ValueError):
        display_rank_value = None
    artist_value = _preferred_owned_item_artist_sort_value(row, korean_artist_by_master_id)
    title_first_group = _title_first_group_artist_key(artist_value)
    common_tail = (
        1 if not order_key else 0,
        order_key,
        1 if display_rank_value is None else 0,
        display_rank_value if display_rank_value is not None else 999999,
        int(row.get("id") or 0),
    )
    if title_first_group:
        return (
            artist_value,
            title_value,
            1 if release_year_value is None else 0,
            release_year_value if release_year_value is not None else 999999,
            *common_tail,
        )
    return (
        artist_value,
        1 if release_year_value is None else 0,
        release_year_value if release_year_value is not None else 999999,
        title_value,
        *common_tail,
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
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
              allowed_size_group TEXT NOT NULL CHECK (allowed_size_group IN ('STD', 'BOOK', 'LP', 'OVERSIZE', 'GOODS')),
              cabinet_sort_policy TEXT NOT NULL DEFAULT 'ARTIST_RELEASE_TITLE' CHECK (cabinet_sort_policy IN ('ARTIST_RELEASE_TITLE', 'LABEL_ID')),
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
              size_group TEXT NOT NULL CHECK (size_group IN ('STD', 'BOOK', 'LP', 'OVERSIZE', 'GOODS')),
              preferred_storage_size_group TEXT CHECK (preferred_storage_size_group IN ('STD', 'BOOK', 'LP', 'OVERSIZE', 'GOODS')),
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
              raw_json TEXT NOT NULL DEFAULT '{}',
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
              raw_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE (source_code, source_master_id),
              FOREIGN KEY (album_master_id) REFERENCES album_master(id) ON DELETE CASCADE
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
              vendor_code TEXT NOT NULL CHECK (vendor_code IN ('SAILMUSIC', 'AMAZON', 'EBAY', 'OTHER')),
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
              raw_payload_json TEXT NOT NULL DEFAULT '{}',
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
            CREATE INDEX IF NOT EXISTS idx_customer_track_request_status ON customer_track_request (status, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_customer_track_request_owned ON customer_track_request (owned_item_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_auth_account_role ON auth_account (role, is_active, username);
            CREATE INDEX IF NOT EXISTS idx_purchase_import_queue_status ON purchase_import_queue (queue_status, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_purchase_import_queue_vendor ON purchase_import_queue (vendor_code, created_at DESC);
            """
        )

        _apply_migrations(conn)
        _seed_metadata_sources(conn)
        _seed_storage_slots(conn)
        _seed_classification_options(conn)


def _column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(str(row["name"]) == column_name for row in rows)


def _ensure_auth_account_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_account (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT NOT NULL UNIQUE,
          password_hash TEXT NOT NULL,
          role TEXT NOT NULL CHECK (role IN ('ADMIN', 'OPERATOR')),
          is_active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_auth_account_role ON auth_account (role, is_active, username)"
    )


def _ensure_purchase_import_queue_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS purchase_import_queue (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          vendor_code TEXT NOT NULL CHECK (vendor_code IN ('SAILMUSIC', 'AMAZON', 'EBAY', 'OTHER')),
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
          raw_payload_json TEXT NOT NULL DEFAULT '{}',
          queue_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (queue_status IN ('PENDING', 'CREATED', 'IGNORED')),
          linked_owned_item_id INTEGER,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY (linked_owned_item_id) REFERENCES owned_item(id) ON DELETE SET NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_purchase_import_queue_status ON purchase_import_queue (queue_status, created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_purchase_import_queue_vendor ON purchase_import_queue (vendor_code, created_at DESC)"
    )


def _album_master_allows_manual(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'album_master'"
    ).fetchone()
    if not row:
        return False
    table_sql = str(row["sql"] or "").upper()
    return "SOURCE_CODE" in table_sql and "'MANUAL'" in table_sql and "'MUSICBRAINZ'" in table_sql


def _purchase_import_queue_allows_file_upload(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'purchase_import_queue'"
    ).fetchone()
    if not row:
        return False
    table_sql = str(row["sql"] or "").upper()
    return "SOURCE_TYPE" in table_sql and "'FILE_UPLOAD'" in table_sql


def _migrate_purchase_import_queue_allow_file_upload(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'purchase_import_queue'"
    ).fetchone()
    if not row or _purchase_import_queue_allows_file_upload(conn):
        return

    if conn.in_transaction:
        conn.commit()

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript(
            """
            BEGIN;
            DROP TABLE IF EXISTS purchase_import_queue_new;
            CREATE TABLE purchase_import_queue_new (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              vendor_code TEXT NOT NULL CHECK (vendor_code IN ('SAILMUSIC', 'AMAZON', 'EBAY', 'OTHER')),
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
              raw_payload_json TEXT NOT NULL DEFAULT '{}',
              queue_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (queue_status IN ('PENDING', 'CREATED', 'IGNORED')),
              linked_owned_item_id INTEGER,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (linked_owned_item_id) REFERENCES owned_item(id) ON DELETE SET NULL
            );
            INSERT INTO purchase_import_queue_new (
              id, vendor_code, source_type, source_ref, email_from, email_subject,
              artist_name, item_name, media_format, quantity, unit_price, line_total,
              currency_code, purchase_date, seller_name, item_url, image_url,
              raw_line, raw_payload_json, queue_status, linked_owned_item_id, created_at, updated_at
            )
            SELECT
              id, vendor_code, source_type, source_ref, email_from, email_subject,
              artist_name, item_name, media_format, quantity, unit_price, line_total,
              currency_code, purchase_date, seller_name, item_url, image_url,
              raw_line, raw_payload_json, queue_status, linked_owned_item_id, created_at, updated_at
            FROM purchase_import_queue;
            DROP TABLE purchase_import_queue;
            ALTER TABLE purchase_import_queue_new RENAME TO purchase_import_queue;
            CREATE INDEX IF NOT EXISTS idx_purchase_import_queue_status ON purchase_import_queue (queue_status, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_purchase_import_queue_vendor ON purchase_import_queue (vendor_code, created_at DESC);
            COMMIT;
            """
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


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
              raw_json TEXT NOT NULL DEFAULT '{}',
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
          raw_json TEXT NOT NULL DEFAULT '{}',
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


def _backfill_album_master_external_refs(conn: sqlite3.Connection) -> None:
    _ensure_album_master_external_ref_table(conn)
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


def _storage_slot_allows_goods(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'storage_slot'"
    ).fetchone()
    if not row:
        return False
    table_sql = str(row["sql"] or "").upper()
    return "'GOODS'" in table_sql


def _migrate_storage_slot_allow_goods(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'storage_slot'"
    ).fetchone()
    if not row or _storage_slot_allows_goods(conn):
        return

    if conn.in_transaction:
        conn.commit()

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript(
            """
            BEGIN;
            DROP TABLE IF EXISTS storage_slot_new;
            CREATE TABLE storage_slot_new (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              slot_code TEXT NOT NULL UNIQUE,
              allowed_size_group TEXT NOT NULL CHECK (allowed_size_group IN ('STD', 'BOOK', 'LP', 'OVERSIZE', 'GOODS')),
              cabinet_sort_policy TEXT NOT NULL DEFAULT 'ARTIST_RELEASE_TITLE' CHECK (cabinet_sort_policy IN ('ARTIST_RELEASE_TITLE', 'LABEL_ID')),
              is_overflow_zone INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              cabinet_name TEXT,
              column_code TEXT,
              cell_code TEXT
            );
            INSERT INTO storage_slot_new
              (id, slot_code, allowed_size_group, cabinet_sort_policy, is_overflow_zone, created_at, updated_at, cabinet_name, column_code, cell_code)
            SELECT
              id, slot_code, allowed_size_group, 'ARTIST_RELEASE_TITLE', is_overflow_zone, created_at, updated_at, cabinet_name, column_code, cell_code
            FROM storage_slot;
            DROP TABLE storage_slot;
            ALTER TABLE storage_slot_new RENAME TO storage_slot;
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
    return "'GOODS'" in table_sql


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
              size_group TEXT NOT NULL CHECK (size_group IN ('STD', 'BOOK', 'LP', 'OVERSIZE', 'GOODS')),
              preferred_storage_size_group TEXT CHECK (preferred_storage_size_group IN ('STD', 'BOOK', 'LP', 'OVERSIZE', 'GOODS')),
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
              size_group TEXT NOT NULL CHECK (size_group IN ('STD', 'BOOK', 'LP', 'OVERSIZE', 'GOODS')),
              preferred_storage_size_group TEXT CHECK (preferred_storage_size_group IN ('STD', 'BOOK', 'LP', 'OVERSIZE', 'GOODS')),
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


def _apply_migrations(conn: sqlite3.Connection) -> None:
    _migrate_album_master_allow_manual(conn)
    _ensure_album_master_external_ref_table(conn)
    _ensure_purchase_import_queue_table(conn)
    _migrate_purchase_import_queue_allow_file_upload(conn)
    _migrate_storage_slot_allow_goods(conn)
    _migrate_owned_item_allow_goods(conn)
    _migrate_owned_item_allow_extended_domains(conn)

    if not _column_exists(conn, "album_master", "domain_code"):
        conn.execute(
            f"ALTER TABLE album_master ADD COLUMN domain_code TEXT CHECK (domain_code IN ('{_domain_code_check_sql()}'))"
        )
    if not _column_exists(conn, "album_master", "sort_artist_name"):
        conn.execute("ALTER TABLE album_master ADD COLUMN sort_artist_name TEXT")
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
            "ALTER TABLE owned_item ADD COLUMN preferred_storage_size_group TEXT CHECK (preferred_storage_size_group IN ('STD', 'BOOK', 'LP', 'OVERSIZE', 'GOODS'))"
        )
    if _column_exists(conn, "owned_item", "preferred_storage_size_group"):
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
        CREATE INDEX IF NOT EXISTS idx_owned_item_location_event_owned ON owned_item_location_event (owned_item_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_owned_item_location_event_from_slot ON owned_item_location_event (from_slot_code, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_owned_item_location_event_to_slot ON owned_item_location_event (to_slot_code, created_at DESC);
        """
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


def _seed_storage_slots(conn: sqlite3.Connection) -> None:
    now = utc_now_iso()
    rows = [
        ("OVERFLOW-STD", "Overflow", "STD", "보조", "STD", 1, now, now),
        ("OVERFLOW-BOOK", "Overflow", "BOOK", "보조", "BOOK", 1, now, now),
        ("OVERFLOW-LP", "Overflow", "LP", "보조", "LP", 1, now, now),
        ("OVERFLOW-OVERSIZE", "Overflow", "OVERSIZE", "보조", "OVERSIZE", 1, now, now),
        ("OVERFLOW-GOODS", "Overflow", "GOODS", "보조", "GOODS", 1, now, now),
    ]
    conn.executemany(
        """
        INSERT INTO storage_slot
          (slot_code, cabinet_name, column_code, cell_code, allowed_size_group, is_overflow_zone, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(slot_code) DO UPDATE SET
          cabinet_name = excluded.cabinet_name,
          column_code = excluded.column_code,
          cell_code = excluded.cell_code,
          allowed_size_group = excluded.allowed_size_group,
          is_overflow_zone = excluded.is_overflow_zone,
          updated_at = excluded.updated_at
        """,
        rows,
    )


def _seed_classification_options(conn: sqlite3.Connection) -> None:
    now = utc_now_iso()
    rows = [
        ("SUBTYPE", "박스셋", 10, 1, now, now),
        ("SUBTYPE", "한정판", 20, 1, now, now),
        ("SUBTYPE", "컴필레이션", 30, 1, now, now),
        ("SUBTYPE", "언플러그드", 40, 1, now, now),
        ("SUBTYPE", "리메이크", 50, 1, now, now),
        ("SUBTYPE", "헌정", 60, 1, now, now),
        ("SUBTYPE", "옴니버스", 70, 1, now, now),
        ("SUBTYPE", "데모", 80, 1, now, now),
        ("SUBTYPE", "동요", 90, 1, now, now),
        ("SOUNDTRACK", "드라마", 10, 1, now, now),
        ("SOUNDTRACK", "영화", 20, 1, now, now),
        ("SOUNDTRACK", "애니메이션", 30, 1, now, now),
        ("SOUNDTRACK", "뮤지컬", 40, 1, now, now),
        ("SOUNDTRACK", "연극", 50, 1, now, now),
        ("SOUNDTRACK", "게임", 60, 1, now, now),
    ]
    conn.executemany(
        """
        INSERT INTO classification_option
          (option_group, label, sort_order, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(option_group, label) DO UPDATE SET
          sort_order = excluded.sort_order,
          is_active = 1,
          updated_at = excluded.updated_at
        """,
        rows,
    )


def insert_batch(ingest_source: str, created_by: str | None, notes: str | None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO ingestion_batch
              (ingest_source, started_at, created_by, notes)
            VALUES (?, ?, ?, ?)
            """,
            (ingest_source, utc_now_iso(), created_by, notes),
        )
        return int(cur.lastrowid)


def finalize_batch(batch_id: int, total: int, matched: int, review: int, failed: int) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE ingestion_batch
            SET total_count = ?,
                matched_count = ?,
                review_count = ?,
                failed_count = ?,
                completed_at = ?
            WHERE id = ?
            """,
            (total, matched, review, failed, utc_now_iso(), batch_id),
        )


def insert_review_queue(
    batch_id: int,
    row_no: int | None,
    category: str | None,
    payload: dict[str, Any],
    candidate: dict[str, Any] | None,
    confidence: float,
    review_status: str,
    review_note: str | None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO review_queue
              (batch_id, row_no, category, payload_json, candidate_json, confidence_score, review_status, review_note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                batch_id,
                row_no,
                category,
                json.dumps(payload, ensure_ascii=True),
                json.dumps(candidate, ensure_ascii=True) if candidate else None,
                confidence,
                review_status,
                review_note,
                utc_now_iso(),
            ),
        )


def list_review_queue(
    review_status: str,
    category: str | None,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    query = """
      SELECT id, batch_id, row_no, category, payload_json, candidate_json,
             confidence_score, review_status, review_note, created_at, reviewed_at, reviewed_by
      FROM review_queue
      WHERE review_status = ?
    """
    params: list[Any] = [review_status]

    if category:
        query += " AND category = ?"
        params.append(category)

    query += " ORDER BY confidence_score DESC, created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        obj = dict(row)
        obj["payload"] = json.loads(obj.pop("payload_json"))
        candidate_raw = obj.pop("candidate_json")
        obj["candidate"] = json.loads(candidate_raw) if candidate_raw else None
        results.append(obj)
    return results


def insert_purchase_import_rows(
    vendor_code: str,
    source_type: str,
    rows: list[dict[str, Any]],
    *,
    source_ref: str | None = None,
    email_from: str | None = None,
    email_subject: str | None = None,
    purchase_date: str | None = None,
) -> list[int]:
    now = utc_now_iso()
    created_ids: list[int] = []
    with get_conn() as conn:
        _ensure_purchase_import_queue_table(conn)
        for row in rows:
            duplicate = _find_purchase_import_duplicate_in_conn(
                conn,
                vendor_code=vendor_code,
                row=row,
                source_ref=source_ref,
                email_subject=email_subject,
            )
            if duplicate is not None:
                continue
            cur = conn.execute(
                """
                INSERT INTO purchase_import_queue (
                  vendor_code, source_type, source_ref, email_from, email_subject,
                  artist_name, item_name, media_format, quantity, unit_price, line_total,
                  currency_code, purchase_date, seller_name, item_url, image_url,
                  raw_line, raw_payload_json, queue_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
                """,
                (
                    vendor_code,
                    source_type,
                    source_ref,
                    email_from,
                    email_subject,
                    row.get("artist_name"),
                    row.get("item_name"),
                    row.get("media_format"),
                    max(1, int(row.get("quantity") or 1)),
                    row.get("unit_price"),
                    row.get("line_total"),
                    row.get("currency_code"),
                    row.get("purchase_date") or purchase_date,
                    row.get("seller_name"),
                    row.get("item_url"),
                    row.get("image_url"),
                    row.get("raw_line"),
                    json.dumps(row.get("raw_payload") or {}, ensure_ascii=True),
                    now,
                    now,
                ),
            )
            created_ids.append(int(cur.lastrowid))
    return created_ids


def _purchase_import_cmp_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _purchase_import_cmp_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _purchase_import_row_matches_duplicate(
    existing: dict[str, Any],
    incoming: dict[str, Any],
    *,
    source_ref: str | None = None,
    email_subject: str | None = None,
) -> bool:
    existing_item_name = _purchase_import_cmp_text(existing.get("item_name"))
    incoming_item_name = _purchase_import_cmp_text(incoming.get("item_name"))
    if not existing_item_name or existing_item_name != incoming_item_name:
        return False

    existing_media = _purchase_import_cmp_text(existing.get("media_format")).upper()
    incoming_media = _purchase_import_cmp_text(incoming.get("media_format")).upper()
    if existing_media != incoming_media:
        return False

    existing_quantity = int(existing.get("quantity") or 1)
    incoming_quantity = max(1, int(incoming.get("quantity") or 1))
    if existing_quantity != incoming_quantity:
        return False

    existing_source_ref = _purchase_import_cmp_text(existing.get("source_ref"))
    incoming_source_ref = _purchase_import_cmp_text(source_ref)
    existing_email_subject = _purchase_import_cmp_text(existing.get("email_subject"))
    incoming_email_subject = _purchase_import_cmp_text(email_subject)
    existing_item_url = _purchase_import_cmp_text(existing.get("item_url"))
    incoming_item_url = _purchase_import_cmp_text(incoming.get("item_url"))
    existing_purchase_date = _purchase_import_cmp_text(existing.get("purchase_date"))
    incoming_purchase_date = _purchase_import_cmp_text(incoming.get("purchase_date"))
    existing_raw_line = _purchase_import_cmp_text(existing.get("raw_line"))
    incoming_raw_line = _purchase_import_cmp_text(incoming.get("raw_line"))

    by_source_ref = bool(existing_source_ref and incoming_source_ref and existing_source_ref == incoming_source_ref and existing_raw_line and incoming_raw_line and existing_raw_line == incoming_raw_line)
    by_item_url = bool(existing_item_url and incoming_item_url and existing_item_url == incoming_item_url and existing_purchase_date and incoming_purchase_date and existing_purchase_date == incoming_purchase_date)
    by_email_subject = bool(existing_email_subject and incoming_email_subject and existing_email_subject == incoming_email_subject and existing_raw_line and incoming_raw_line and existing_raw_line == incoming_raw_line)
    by_raw_line = bool(existing_raw_line and incoming_raw_line and existing_raw_line == incoming_raw_line and existing_purchase_date and incoming_purchase_date and existing_purchase_date == incoming_purchase_date)
    if not (by_source_ref or by_item_url or by_email_subject or by_raw_line):
        return False

    existing_unit_price = _purchase_import_cmp_float(existing.get("unit_price"))
    incoming_unit_price = _purchase_import_cmp_float(incoming.get("unit_price"))
    if existing_unit_price is not None and incoming_unit_price is not None and existing_unit_price != incoming_unit_price:
        return False

    existing_line_total = _purchase_import_cmp_float(existing.get("line_total"))
    incoming_line_total = _purchase_import_cmp_float(incoming.get("line_total"))
    if existing_line_total is not None and incoming_line_total is not None and existing_line_total != incoming_line_total:
        return False

    return True


def _find_purchase_import_duplicate_in_conn(
    conn: sqlite3.Connection,
    vendor_code: str,
    row: dict[str, Any],
    *,
    source_ref: str | None = None,
    email_subject: str | None = None,
    exclude_queue_id: int | None = None,
    require_linked_owned_item: bool = False,
) -> dict[str, Any] | None:
    vendor = _purchase_import_cmp_text(vendor_code).upper()
    item_name = _purchase_import_cmp_text(row.get("item_name"))
    if not vendor or not item_name:
        return None
    params: list[Any] = [vendor, item_name]
    query = """
      SELECT id, vendor_code, source_ref, email_subject, artist_name, item_name, media_format,
             quantity, unit_price, line_total, currency_code, purchase_date, item_url, raw_line,
             queue_status, linked_owned_item_id
      FROM purchase_import_queue
      WHERE vendor_code = ?
        AND item_name = ?
    """
    if require_linked_owned_item:
        query += " AND linked_owned_item_id IS NOT NULL"
    if exclude_queue_id is not None:
        query += " AND id <> ?"
        params.append(int(exclude_queue_id))
    query += " ORDER BY id DESC"
    rows = conn.execute(query, params).fetchall()
    incoming = dict(row)
    incoming["source_ref"] = source_ref
    incoming["email_subject"] = email_subject
    for existing in rows:
        existing_row = dict(existing)
        if _purchase_import_row_matches_duplicate(existing_row, incoming, source_ref=source_ref, email_subject=email_subject):
            return existing_row
    return None


def find_purchase_import_duplicate_row(
    row: dict[str, Any],
    *,
    exclude_queue_id: int | None = None,
    require_linked_owned_item: bool = False,
) -> dict[str, Any] | None:
    vendor_code = _purchase_import_cmp_text(row.get("vendor_code")).upper()
    if not vendor_code:
        return None
    with get_conn() as conn:
        _ensure_purchase_import_queue_table(conn)
        return _find_purchase_import_duplicate_in_conn(
            conn,
            vendor_code=vendor_code,
            row=row,
            source_ref=row.get("source_ref"),
            email_subject=row.get("email_subject"),
            exclude_queue_id=exclude_queue_id,
            require_linked_owned_item=require_linked_owned_item,
        )


def list_purchase_import_rows(
    *,
    queue_status: str | None = "PENDING",
    vendor_code: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    query = """
      SELECT id, vendor_code, source_type, source_ref, email_from, email_subject,
             artist_name, item_name, media_format, quantity, unit_price, line_total,
             currency_code, purchase_date, seller_name, item_url, image_url,
             raw_line, raw_payload_json, queue_status, linked_owned_item_id,
             created_at, updated_at
      FROM purchase_import_queue
      WHERE 1=1
    """
    params: list[Any] = []
    if queue_status:
        query += " AND queue_status = ?"
        params.append(queue_status)
    if vendor_code:
        query += " AND vendor_code = ?"
        params.append(vendor_code)
    query += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        _ensure_purchase_import_queue_table(conn)
        rows = conn.execute(query, params).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        raw_payload = item.pop("raw_payload_json", None)
        item["raw_payload"] = json.loads(raw_payload) if raw_payload else {}
        items.append(item)
    return items


def count_purchase_import_rows(*, queue_status: str | None = "PENDING", vendor_code: str | None = None) -> int:
    query = "SELECT COUNT(*) AS cnt FROM purchase_import_queue WHERE 1=1"
    params: list[Any] = []
    if queue_status:
        query += " AND queue_status = ?"
        params.append(queue_status)
    if vendor_code:
        query += " AND vendor_code = ?"
        params.append(vendor_code)
    with get_conn() as conn:
        _ensure_purchase_import_queue_table(conn)
        row = conn.execute(query, params).fetchone()
    return int(row["cnt"] or 0) if row else 0


def get_purchase_import_row(queue_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        _ensure_purchase_import_queue_table(conn)
        row = conn.execute(
            """
            SELECT id, vendor_code, source_type, source_ref, email_from, email_subject,
                   artist_name, item_name, media_format, quantity, unit_price, line_total,
                   currency_code, purchase_date, seller_name, item_url, image_url,
                   raw_line, raw_payload_json, queue_status, linked_owned_item_id,
                   created_at, updated_at
            FROM purchase_import_queue
            WHERE id = ?
            LIMIT 1
            """,
            (int(queue_id),),
        ).fetchone()
    if row is None:
        return None
    item = dict(row)
    raw_payload = item.pop("raw_payload_json", None)
    item["raw_payload"] = json.loads(raw_payload) if raw_payload else {}
    return item


def update_purchase_import_row(
    queue_id: int,
    *,
    queue_status: str | None = None,
    linked_owned_item_id: int | None = None,
    artist_name: Any = _UNSET,
    item_name: Any = _UNSET,
    seller_name: Any = _UNSET,
    item_url: Any = _UNSET,
    image_url: Any = _UNSET,
    raw_payload: Any = _UNSET,
) -> dict[str, Any] | None:
    assignments: list[str] = []
    params: list[Any] = []
    if queue_status is not None:
        assignments.append("queue_status = ?")
        params.append(queue_status)
    if linked_owned_item_id is not None:
        assignments.append("linked_owned_item_id = ?")
        params.append(int(linked_owned_item_id))
    elif queue_status == "IGNORED":
        assignments.append("linked_owned_item_id = NULL")
    if artist_name is not _UNSET:
        assignments.append("artist_name = ?")
        params.append(artist_name)
    if item_name is not _UNSET:
        assignments.append("item_name = ?")
        params.append(item_name)
    if seller_name is not _UNSET:
        assignments.append("seller_name = ?")
        params.append(seller_name)
    if item_url is not _UNSET:
        assignments.append("item_url = ?")
        params.append(item_url)
    if image_url is not _UNSET:
        assignments.append("image_url = ?")
        params.append(image_url)
    if raw_payload is not _UNSET:
        assignments.append("raw_payload_json = ?")
        params.append(json.dumps(raw_payload or {}, ensure_ascii=True))
    if not assignments:
        return get_purchase_import_row(queue_id)
    assignments.append("updated_at = ?")
    params.append(utc_now_iso())
    params.append(int(queue_id))
    with get_conn() as conn:
        _ensure_purchase_import_queue_table(conn)
        conn.execute(
            f"UPDATE purchase_import_queue SET {', '.join(assignments)} WHERE id = ?",
            params,
        )
    return get_purchase_import_row(queue_id)


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
    with get_conn() as conn:
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
    requested_limit = max(1, int(limit))
    fetch_limit = max(10, min(200, requested_limit * 4))

    base_sql_template = """
      SELECT
        oi.id,
        oi.category,
        oi.item_name_override,
        oi.linked_album_master_id,
        oi.status,
        oi.signature_type,
        mid.format_name,
        mid.artist_or_brand,
        mid.released_date,
        mid.label_name,
        mid.catalog_no,
        mid.barcode,
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
            0 if (row.get("matched_track_count") or 0) > 0 else 1,
            0 if str(row.get("status") or "") == "IN_COLLECTION" else 1,
            str(row.get("item_title") or row.get("item_name_override") or "").lower(),
            int(row.get("id") or 0),
        )
    )
    return out[:requested_limit]


def create_customer_track_request(
    requested_track: str,
    requested_by: str | None = None,
    owned_item_id: int | None = None,
    matched_track_title: str | None = None,
    matched_track_no: int | None = None,
    customer_note: str | None = None,
) -> dict[str, Any]:
    now = utc_now_iso()
    owned_id = int(owned_item_id) if owned_item_id else None
    detail = get_owned_item_detail(owned_id) if owned_id else None
    location = get_owned_item_location_snapshot(owned_id) if owned_id else None

    item_title = None
    artist_or_brand = None
    cover_image_url = None
    category = None
    if detail is not None:
        category = str(detail.get("category") or "").strip() or None
        item_title = str(detail.get("item_name_override") or "").strip() or None
        artist_or_brand = str(detail.get("artist_or_brand") or "").strip() or None
        item_title = item_title or str(detail.get("catalog_no") or "").strip() or None
        cover_image_url = str(detail.get("cover_image_url") or detail.get("goods_primary_image_url") or "").strip() or None

    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO customer_track_request (
              requested_track,
              owned_item_id,
              matched_track_title,
              matched_track_no,
              item_title_snapshot,
              artist_or_brand_snapshot,
              cover_image_url_snapshot,
              category_snapshot,
              current_slot_code_snapshot,
              current_slot_display_snapshot,
              previous_slot_code_snapshot,
              previous_slot_display_snapshot,
              customer_note,
              status,
              requested_by,
              created_at,
              updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'REQUESTED', ?, ?, ?)
            """,
            (
                str(requested_track or "").strip(),
                owned_id,
                str(matched_track_title or "").strip() or None,
                int(matched_track_no) if matched_track_no else None,
                item_title,
                artist_or_brand,
                cover_image_url,
                category,
                location.get("current_slot_code") if location else None,
                location.get("current_slot_display_name") if location else None,
                location.get("previous_slot_code") if location else None,
                location.get("previous_slot_display_name") if location else None,
                str(customer_note or "").strip() or None,
                str(requested_by or "").strip() or None,
                now,
                now,
            ),
        )
        request_id = int(cur.lastrowid or 0)
    return get_customer_track_request(request_id) or {}


def get_customer_track_request(request_id: int) -> dict[str, Any] | None:
    rows = list_customer_track_requests(status=None, limit=1, request_id=int(request_id))
    return rows[0] if rows else None


def list_customer_track_requests(
    status: str | None = None,
    limit: int = 100,
    request_id: int | None = None,
) -> list[dict[str, Any]]:
    where_parts = ["1=1"]
    params: list[Any] = []
    if status and str(status).strip():
        where_parts.append("ctr.status = ?")
        params.append(str(status).strip().upper())
    if request_id is not None:
        where_parts.append("ctr.id = ?")
        params.append(int(request_id))
    where_sql = " AND ".join(where_parts)

    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT
              ctr.*,
              oi.category AS live_category,
              COALESCE(oi.item_name_override, am.title, ctr.item_title_snapshot) AS live_item_title,
              COALESCE(mid.artist_or_brand, am.artist_or_brand, ctr.artist_or_brand_snapshot) AS live_artist_or_brand,
              COALESCE(mid.cover_image_url, ctr.cover_image_url_snapshot) AS live_cover_image_url,
              ss.slot_code AS current_live_slot_code,
              ss.cabinet_name AS current_live_cabinet_name,
              ss.column_code AS current_live_column_code,
              ss.cell_code AS current_live_cell_code,
              ss.allowed_size_group AS current_live_allowed_size_group,
              ss.is_overflow_zone AS current_live_is_overflow_zone
            FROM customer_track_request ctr
            LEFT JOIN owned_item oi ON oi.id = ctr.owned_item_id
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
            LEFT JOIN storage_slot ss ON ss.id = oi.storage_slot_id
            WHERE {where_sql}
            ORDER BY ctr.created_at DESC, ctr.id DESC
            LIMIT ?
            """,
            [*params, max(1, int(limit))],
        ).fetchall()

    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        live_slot_display = None
        if item.get("current_live_slot_code"):
            live_slot_display = _storage_slot_display_name(
                {
                    "slot_code": item.get("current_live_slot_code"),
                    "cabinet_name": item.get("current_live_cabinet_name"),
                    "column_code": item.get("current_live_column_code"),
                    "cell_code": item.get("current_live_cell_code"),
                    "allowed_size_group": item.get("current_live_allowed_size_group"),
                    "is_overflow_zone": item.get("current_live_is_overflow_zone"),
                }
            )
        item["item_title"] = str(item.get("item_title_snapshot") or item.get("live_item_title") or "").strip() or None
        item["artist_or_brand"] = str(item.get("artist_or_brand_snapshot") or item.get("live_artist_or_brand") or "").strip() or None
        item["cover_image_url"] = str(item.get("cover_image_url_snapshot") or item.get("live_cover_image_url") or "").strip() or None
        category = str(item.get("live_category") or item.get("category_snapshot") or "").strip() or None
        item["category"] = category
        owned_item_id = int(item.get("owned_item_id") or 0)
        item["label_id"] = _build_label_id(category, owned_item_id) if category and owned_item_id > 0 else None
        item["current_live_slot_display_name"] = live_slot_display
        out.append(item)
    return out


def count_customer_track_requests(status: str | None = None) -> int:
    where_sql = ""
    params: list[Any] = []
    if status and str(status).strip():
        where_sql = " WHERE status = ?"
        params.append(str(status).strip().upper())
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT COUNT(*) AS cnt FROM customer_track_request{where_sql}",
            params,
        ).fetchone()
    return int(row["cnt"] or 0) if row else 0


def update_customer_track_request(
    request_id: int,
    status: str | None = None,
    response_note: str | None = None,
    handled_by: str | None = None,
) -> dict[str, Any] | None:
    request_row = get_customer_track_request(int(request_id))
    if request_row is None:
        return None
    next_status = str(status or request_row.get("status") or "REQUESTED").strip().upper()
    next_note = str(response_note or "").strip() or None
    now = utc_now_iso()
    handled_at = request_row.get("handled_at")
    if next_status in {"PLAYING", "RETURNED", "CANCELLED"}:
        handled_at = now
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE customer_track_request
            SET status = ?,
                response_note = ?,
                handled_by = ?,
                handled_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                next_status,
                next_note,
                str(handled_by or "").strip() or request_row.get("handled_by"),
                handled_at,
                now,
                int(request_id),
            ),
        )
    return get_customer_track_request(int(request_id))


def list_auth_accounts() -> list[dict[str, Any]]:
    with get_conn() as conn:
        _ensure_auth_account_table(conn)
        rows = conn.execute(
            """
            SELECT id, username, password_hash, role, is_active, created_at, updated_at
            FROM auth_account
            ORDER BY
              CASE WHEN role = 'ADMIN' THEN 0 ELSE 1 END,
              LOWER(username) ASC,
              id ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_auth_account_by_username(username: str) -> dict[str, Any] | None:
    key = str(username or "").strip()
    if not key:
        return None
    with get_conn() as conn:
        _ensure_auth_account_table(conn)
        row = conn.execute(
            """
            SELECT *
            FROM auth_account
            WHERE username = ?
            LIMIT 1
            """,
            (key,),
        ).fetchone()
    return dict(row) if row else None


def upsert_auth_account(username: str, password_hash: str, role: str, is_active: bool = True) -> dict[str, Any] | None:
    key = str(username or "").strip()
    hashed = str(password_hash or "").strip()
    role_code = str(role or "").strip().upper()
    if not key or not hashed or role_code not in {"ADMIN", "OPERATOR"}:
        return None
    now = utc_now_iso()
    with get_conn() as conn:
        _ensure_auth_account_table(conn)
        conn.execute(
            """
            INSERT INTO auth_account (username, password_hash, role, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
              password_hash = excluded.password_hash,
              role = excluded.role,
              is_active = excluded.is_active,
              updated_at = excluded.updated_at
            """,
            (key, hashed, role_code, 1 if is_active else 0, now, now),
        )
    return get_auth_account_by_username(key)


def delete_auth_account(username: str) -> bool:
    key = str(username or "").strip()
    if not key:
        return False
    with get_conn() as conn:
        _ensure_auth_account_table(conn)
        cur = conn.execute("DELETE FROM auth_account WHERE username = ?", (key,))
    return int(cur.rowcount or 0) > 0


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
              SUM(CASE WHEN status = 'IN_COLLECTION' THEN 1 ELSE 0 END) AS in_collection_items,
              SUM(CASE WHEN category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL') THEN 1 ELSE 0 END) AS music_items,
              SUM(CASE WHEN category NOT IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL') THEN 1 ELSE 0 END) AS goods_items,
              SUM(CASE WHEN signature_type IS NOT NULL AND signature_type <> 'NONE' THEN 1 ELSE 0 END) AS signed_items,
              SUM(CASE WHEN is_second_hand = 1 THEN 1 ELSE 0 END) AS second_hand_items,
              SUM(CASE WHEN created_at >= datetime('now', '-30 days') THEN 1 ELSE 0 END) AS registered_last_30_days,
              SUM(CASE WHEN status = 'IN_COLLECTION' AND storage_slot_id IS NOT NULL THEN 1 ELSE 0 END) AS slotted_in_collection_items,
              SUM(CASE WHEN status = 'IN_COLLECTION' AND storage_slot_id IS NULL THEN 1 ELSE 0 END) AS unslotted_in_collection_items
            FROM owned_item
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

        recent_move_total_row = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM owned_item_location_event
            WHERE created_at >= ?
            """,
            (move_threshold,),
        ).fetchone()

        recent_move_rows = conn.execute(
            """
            SELECT
              e.id,
              e.owned_item_id,
              oi.category,
              COALESCE(oi.item_name_override, am.title) AS item_title,
              COALESCE(mid.artist_or_brand, am.artist_or_brand, oi.linked_artist_name) AS artist_or_brand,
              COALESCE(mid.cover_image_url, gid.primary_image_url) AS cover_image_url,
              e.movement_kind,
              e.from_slot_code,
              e.from_slot_display_name,
              e.to_slot_code,
              e.to_slot_display_name,
              e.note,
              e.created_at
            FROM owned_item_location_event e
            JOIN owned_item oi ON oi.id = e.owned_item_id
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            LEFT JOIN goods_item_detail gid ON gid.owned_item_id = oi.id
            LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
            WHERE e.created_at >= ?
            ORDER BY e.created_at DESC, e.id DESC
            LIMIT 12
            """,
            (move_threshold,),
        ).fetchall()

        slot_rows = conn.execute(
            """
            SELECT id, slot_code, cabinet_name, column_code, cell_code, allowed_size_group, is_overflow_zone
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
    slot_in_map = {str(row["slot_code"] or "UNASSIGNED"): int(row["cnt"] or 0) for row in slot_in_rows}
    slot_out_map = {str(row["slot_code"] or "UNASSIGNED"): int(row["cnt"] or 0) for row in slot_out_rows}
    structured_slots = [dict(row) for row in slot_rows]
    for item in structured_slots:
        item["display_name"] = _storage_slot_display_name(item)
        item["count"] = int(slot_count_map.get(int(item["id"]), 0))
        item["recent_in_count"] = int(slot_in_map.get(str(item["slot_code"] or ""), 0))
        item["recent_out_count"] = int(slot_out_map.get(str(item["slot_code"] or ""), 0))
    structured_slots.sort(key=_storage_slot_sort_key)

    return {
        "total_items": int((summary["total_items"] if summary else 0) or 0),
        "in_collection_items": int((summary["in_collection_items"] if summary else 0) or 0),
        "music_items": int((summary["music_items"] if summary else 0) or 0),
        "goods_items": int((summary["goods_items"] if summary else 0) or 0),
        "signed_items": int((summary["signed_items"] if summary else 0) or 0),
        "second_hand_items": int((summary["second_hand_items"] if summary else 0) or 0),
        "audio_mapped_items": int((audio_row["cnt"] if audio_row else 0) or 0),
        "registered_last_30_days": int((summary["registered_last_30_days"] if summary else 0) or 0),
        "slotted_in_collection_items": int((summary["slotted_in_collection_items"] if summary else 0) or 0),
        "unslotted_in_collection_items": int((summary["unslotted_in_collection_items"] if summary else 0) or 0),
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
        "recent_move_total": int((recent_move_total_row["cnt"] if recent_move_total_row else 0) or 0),
        "recent_moves": [
            {
                "id": int(row["id"]),
                "owned_item_id": int(row["owned_item_id"]),
                "label_id": _build_label_id(str(row["category"] or ""), int(row["owned_item_id"])),
                "category": str(row["category"] or ""),
                "item_title": str(row["item_title"]) if row["item_title"] is not None else None,
                "artist_or_brand": str(row["artist_or_brand"]) if row["artist_or_brand"] is not None else None,
                "cover_image_url": str(row["cover_image_url"]) if row["cover_image_url"] is not None else None,
                "movement_kind": str(row["movement_kind"] or ""),
                "from_slot_code": str(row["from_slot_code"]) if row["from_slot_code"] is not None else None,
                "from_display_name": str(row["from_slot_display_name"]) if row["from_slot_display_name"] is not None else None,
                "to_slot_code": str(row["to_slot_code"]) if row["to_slot_code"] is not None else None,
                "to_display_name": str(row["to_slot_display_name"]) if row["to_slot_display_name"] is not None else None,
                "note": str(row["note"]) if row["note"] is not None else None,
                "created_at": str(row["created_at"] or ""),
            }
            for row in recent_move_rows
        ],
        "by_slot": [
            {
                "slot_code": str(row["slot_code"]),
                "cabinet_name": str(row["cabinet_name"]) if row.get("cabinet_name") is not None else None,
                "column_code": str(row["column_code"]) if row.get("column_code") is not None else None,
                "cell_code": str(row["cell_code"]) if row.get("cell_code") is not None else None,
                "display_name": str(row["display_name"]) if row.get("display_name") is not None else None,
                "allowed_size_group": str(row["allowed_size_group"]) if row.get("allowed_size_group") is not None else None,
                "is_overflow_zone": bool(row["is_overflow_zone"]),
                "count": int(row["count"] or 0),
                "recent_in_count": int(row.get("recent_in_count") or 0),
                "recent_out_count": int(row.get("recent_out_count") or 0),
            }
            for row in structured_slots
        ]
        + [
            {
                "slot_code": "UNASSIGNED",
                "cabinet_name": "미배치",
                "column_code": None,
                "cell_code": None,
                "display_name": "미배치",
                "allowed_size_group": None,
                "is_overflow_zone": False,
                "count": int((unassigned_row["cnt"] if unassigned_row else 0) or 0),
                "recent_in_count": int(slot_in_map.get("UNASSIGNED", 0)),
                "recent_out_count": int(slot_out_map.get("UNASSIGNED", 0)),
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


def get_album_master_binding_for_owned_item(owned_item_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT
              am.id AS album_master_id,
              am.source_code,
              am.source_master_id,
              am.title,
              am.artist_or_brand,
              am.sort_artist_name
            FROM album_master_member amm
            JOIN album_master am ON am.id = amm.album_master_id
            WHERE amm.owned_item_id = ?
            ORDER BY am.updated_at DESC, am.id DESC
            LIMIT 1
            """,
            (owned_item_id,),
        ).fetchone()
    return dict(row) if row else None


def get_album_master_domain_hint(album_master_id: int) -> str | None:
    with get_conn() as conn:
        if _column_exists(conn, "album_master", "domain_code"):
            master_row = conn.execute(
                """
                SELECT domain_code
                FROM album_master
                WHERE id = ?
                LIMIT 1
                """,
                (int(album_master_id),),
            ).fetchone()
            direct_code = _normalize_domain_code_value(master_row["domain_code"]) if master_row is not None else None
            if direct_code:
                return direct_code
        row = conn.execute(
            """
            SELECT oi.domain_code, COUNT(*) AS cnt
            FROM owned_item oi
            WHERE oi.linked_album_master_id = ?
              AND oi.domain_code IS NOT NULL
              AND TRIM(oi.domain_code) <> ''
            GROUP BY oi.domain_code
            ORDER BY cnt DESC, oi.domain_code ASC
            LIMIT 1
            """,
            (int(album_master_id),),
        ).fetchone()
    if row is None:
        return None
    return _normalize_domain_code_value(row["domain_code"])


def _sync_album_master_domain_code_in_conn(
    conn: sqlite3.Connection,
    album_master_id: int,
    preferred_domain_code: str | None = None,
) -> str | None:
    master_id = int(album_master_id or 0)
    if master_id <= 0:
        return None

    master_row = conn.execute(
        "SELECT domain_code FROM album_master WHERE id = ? LIMIT 1",
        (master_id,),
    ).fetchone()
    if master_row is None:
        return None

    current_code = _normalize_domain_code_value(master_row["domain_code"])
    resolved_code = _normalize_domain_code_value(preferred_domain_code)
    if not resolved_code and current_code:
        return current_code
    if not resolved_code:
        row = conn.execute(
            """
            SELECT oi.domain_code, COUNT(*) AS cnt
            FROM album_master_member amm
            JOIN owned_item oi ON oi.id = amm.owned_item_id
            WHERE amm.album_master_id = ?
              AND oi.domain_code IS NOT NULL
              AND TRIM(oi.domain_code) <> ''
            GROUP BY oi.domain_code
            ORDER BY COUNT(*) DESC, oi.domain_code ASC
            LIMIT 1
            """,
            (master_id,),
        ).fetchone()
        resolved_code = _normalize_domain_code_value(row["domain_code"]) if row is not None else None

    if resolved_code and resolved_code != current_code:
        conn.execute(
            "UPDATE album_master SET domain_code = ?, updated_at = ? WHERE id = ?",
            (resolved_code, utc_now_iso(), master_id),
        )
    return resolved_code or current_code


def list_owned_items_by_album_master(album_master_id: int) -> list[dict[str, Any]]:
    query = (
        _owned_item_select_query()
        + """
        JOIN album_master_member amm ON amm.owned_item_id = oi.id
        WHERE amm.album_master_id = ?
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
        rows = conn.execute(query, (album_master_id,)).fetchall()
    return [_normalize_owned_item_row(dict(row)) for row in rows]


def get_album_master_id_by_external_ref(source_code: str, source_master_id: str) -> int | None:
    source_u = str(source_code or "").strip().upper()
    source_master = str(source_master_id or "").strip()
    if not source_u or not source_master:
        return None
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT album_master_id
            FROM album_master_external_ref
            WHERE source_code = ? AND source_master_id = ?
            LIMIT 1
            """,
            (source_u, source_master),
        ).fetchone()
    if row is None:
        return None
    return int(row["album_master_id"] or 0) or None


def list_album_master_external_refs(
    album_master_id: int,
    source_code: str | None = None,
) -> list[dict[str, Any]]:
    master_id = int(album_master_id or 0)
    if master_id <= 0:
        return []
    query = """
        SELECT
          id,
          album_master_id,
          source_code,
          source_master_id,
          title_hint,
          artist_or_brand_hint,
          release_year,
          raw_json,
          created_at,
          updated_at
        FROM album_master_external_ref
        WHERE album_master_id = ?
    """
    params: list[Any] = [master_id]
    source_u = str(source_code or "").strip().upper()
    if source_u:
        query += " AND source_code = ?"
        params.append(source_u)
    query += " ORDER BY updated_at DESC, id DESC"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def ensure_album_master_external_ref(
    album_master_id: int,
    source_code: str,
    source_master_id: str,
    title_hint: str | None = None,
    artist_or_brand_hint: str | None = None,
    release_year: int | None = None,
    raw: dict[str, Any] | None = None,
) -> int:
    master_id = int(album_master_id or 0)
    source_u = str(source_code or "").strip().upper()
    source_master = str(source_master_id or "").strip()
    if master_id <= 0 or not source_u or not source_master:
        raise ValueError("album_master_id, source_code, source_master_id required")

    now = utc_now_iso()
    raw_json = json.dumps(raw or {}, ensure_ascii=True)
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO album_master_external_ref
              (album_master_id, source_code, source_master_id, title_hint, artist_or_brand_hint, release_year, raw_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_code, source_master_id) DO UPDATE SET
              album_master_id = excluded.album_master_id,
              title_hint = COALESCE(excluded.title_hint, album_master_external_ref.title_hint),
              artist_or_brand_hint = COALESCE(excluded.artist_or_brand_hint, album_master_external_ref.artist_or_brand_hint),
              release_year = COALESCE(excluded.release_year, album_master_external_ref.release_year),
              raw_json = CASE
                           WHEN TRIM(COALESCE(excluded.raw_json, '{}')) IN ('', '{}') THEN album_master_external_ref.raw_json
                           ELSE excluded.raw_json
                         END,
              updated_at = excluded.updated_at
            """,
            (
                master_id,
                source_u,
                source_master,
                str(title_hint or "").strip() or None,
                str(artist_or_brand_hint or "").strip() or None,
                release_year,
                raw_json,
                now,
                now,
            ),
        )
        row = conn.execute(
            """
            SELECT id
            FROM album_master_external_ref
            WHERE source_code = ? AND source_master_id = ?
            LIMIT 1
            """,
            (source_u, source_master),
        ).fetchone()
    if row is None:
        raise RuntimeError("album_master_external_ref upsert failed")
    return int(row["id"])


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


def upsert_album_master(
    source_code: str,
    source_master_id: str,
    title: str,
    artist_or_brand: str | None,
    domain_code: str | None,
    release_year: int | None,
    raw: dict[str, Any],
) -> int:
    now = utc_now_iso()
    normalized_domain_code = _normalize_domain_code_value(domain_code)
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO album_master
              (source_code, source_master_id, title, artist_or_brand, domain_code, release_year, raw_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_code, source_master_id) DO UPDATE SET
              title = excluded.title,
              artist_or_brand = excluded.artist_or_brand,
              domain_code = COALESCE(excluded.domain_code, album_master.domain_code),
              release_year = excluded.release_year,
              raw_json = excluded.raw_json,
              updated_at = excluded.updated_at
            """,
            (
                source_code,
                source_master_id,
                title,
                artist_or_brand,
                normalized_domain_code,
                release_year,
                json.dumps(raw, ensure_ascii=True),
                now,
                now,
            ),
        )
        row = conn.execute(
            """
            SELECT id
            FROM album_master
            WHERE source_code = ? AND source_master_id = ?
            """,
            (source_code, source_master_id),
        ).fetchone()

    if row is None:
        raise RuntimeError("album_master upsert failed")
    album_master_id = int(row["id"])
    ensure_album_master_external_ref(
        album_master_id=album_master_id,
        source_code=source_code,
        source_master_id=source_master_id,
        title_hint=title,
        artist_or_brand_hint=artist_or_brand,
        release_year=release_year,
        raw=raw,
    )
    return album_master_id


def normalize_album_master_source_id(
    album_master_id: int,
    source_code: str,
    source_master_id: str,
) -> int:
    master_id = int(album_master_id or 0)
    source_u = str(source_code or "").strip().upper()
    source_master = str(source_master_id or "").strip()
    if master_id <= 0 or not source_u or not source_master:
        return master_id

    now = utc_now_iso()
    with get_conn() as conn:
        current = conn.execute(
            """
            SELECT id, source_code, source_master_id, domain_code, sort_artist_name
            FROM album_master
            WHERE id = ?
            """,
            (master_id,),
        ).fetchone()
        if current is None:
            return 0

        current_source = str(current["source_code"] or "").strip().upper()
        current_source_master = str(current["source_master_id"] or "").strip()
        if current_source != source_u:
            return master_id
        if current_source_master == source_master:
            return master_id

        existing = conn.execute(
            """
            SELECT id
            FROM album_master
            WHERE source_code = ? AND source_master_id = ?
            LIMIT 1
            """,
            (source_u, source_master),
        ).fetchone()

        if existing is not None:
            target_master_id = int(existing["id"])
            if target_master_id == master_id:
                return master_id

            conn.execute(
                """
                INSERT OR IGNORE INTO album_master_member
                  (album_master_id, owned_item_id, created_at)
                SELECT ?, owned_item_id, ?
                FROM album_master_member
                WHERE album_master_id = ?
                """,
                (target_master_id, now, master_id),
            )
            conn.execute(
                """
                UPDATE owned_item
                SET linked_album_master_id = ?, updated_at = ?
                WHERE linked_album_master_id = ?
                """,
                (target_master_id, now, master_id),
            )
            _sync_album_master_domain_code_in_conn(
                conn,
                target_master_id,
                preferred_domain_code=_normalize_domain_code_value(current["domain_code"]),
            )
            current_sort_artist_name = str(current["sort_artist_name"] or "").strip() or None
            if current_sort_artist_name:
                conn.execute(
                    """
                    UPDATE album_master
                    SET sort_artist_name = CASE
                                             WHEN TRIM(COALESCE(sort_artist_name, '')) = '' THEN ?
                                             ELSE sort_artist_name
                                           END,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (current_sort_artist_name, now, target_master_id),
                )
            conn.execute("DELETE FROM album_master WHERE id = ?", (master_id,))
            conn.execute(
                "UPDATE album_master SET updated_at = ? WHERE id = ?",
                (now, target_master_id),
            )
            return target_master_id

        conn.execute(
            """
            UPDATE album_master
            SET source_master_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (source_master, now, master_id),
        )
    ensure_album_master_external_ref(
        album_master_id=master_id,
        source_code=source_u,
        source_master_id=source_master,
    )
    return master_id


def promote_album_master_source(
    album_master_id: int,
    source_code: str,
    source_master_id: str,
    title: str,
    artist_or_brand: str | None,
    domain_code: str | None,
    release_year: int | None,
    raw: dict[str, Any],
) -> int:
    master_id = int(album_master_id or 0)
    source_u = str(source_code or "").strip().upper()
    source_master = str(source_master_id or "").strip()
    if master_id <= 0 or not source_u or not source_master:
        return 0

    now = utc_now_iso()
    raw_json = json.dumps(raw or {}, ensure_ascii=True)
    title_text = str(title or "").strip() or f"{source_u} Master {source_master}"
    artist_text = str(artist_or_brand or "").strip() or None
    domain_text = _normalize_domain_code_value(domain_code)
    year_value = int(release_year) if isinstance(release_year, int) else None

    with get_conn() as conn:
        current = conn.execute(
            """
            SELECT id, sort_artist_name
            FROM album_master
            WHERE id = ?
            """,
            (master_id,),
        ).fetchone()
        if current is None:
            return 0

        existing = conn.execute(
            """
            SELECT id
            FROM album_master
            WHERE source_code = ? AND source_master_id = ?
            LIMIT 1
            """,
            (source_u, source_master),
        ).fetchone()

        if existing is not None:
            target_master_id = int(existing["id"])
            if target_master_id != master_id:
                current_sort_artist_name = str(current["sort_artist_name"] or "").strip() or None
                conn.execute(
                    """
                    INSERT OR IGNORE INTO album_master_member
                      (album_master_id, owned_item_id, created_at)
                    SELECT ?, owned_item_id, ?
                    FROM album_master_member
                    WHERE album_master_id = ?
                    """,
                    (target_master_id, now, master_id),
                )
                conn.execute(
                    """
                    UPDATE owned_item
                    SET linked_album_master_id = ?, updated_at = ?
                    WHERE linked_album_master_id = ?
                    """,
                    (target_master_id, now, master_id),
                )
                conn.execute(
                    """
                    UPDATE album_master
                    SET title = ?,
                        artist_or_brand = ?,
                        sort_artist_name = CASE
                                             WHEN TRIM(COALESCE(sort_artist_name, '')) = '' THEN ?
                                             ELSE sort_artist_name
                                           END,
                        domain_code = COALESCE(?, domain_code),
                        release_year = ?,
                        raw_json = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (title_text, artist_text, current_sort_artist_name, domain_text, year_value, raw_json, now, target_master_id),
                )
                conn.execute(
                    """
                    UPDATE album_master_external_ref
                    SET album_master_id = ?, updated_at = ?
                    WHERE album_master_id = ?
                    """,
                    (target_master_id, now, master_id),
                )
                conn.execute("DELETE FROM album_master WHERE id = ?", (master_id,))
                master_id = target_master_id
            else:
                master_id = target_master_id

        conn.execute(
            """
            UPDATE album_master
            SET source_code = ?,
                source_master_id = ?,
                title = ?,
                artist_or_brand = ?,
                domain_code = COALESCE(?, domain_code),
                release_year = ?,
                raw_json = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (source_u, source_master, title_text, artist_text, domain_text, year_value, raw_json, now, master_id),
        )
    ensure_album_master_external_ref(
        album_master_id=master_id,
        source_code=source_u,
        source_master_id=source_master,
        title_hint=title_text,
        artist_or_brand_hint=artist_text,
        release_year=year_value,
        raw=raw,
    )
    return master_id


def _album_master_source_priority(source_code: str) -> int:
    code = str(source_code or "").strip().upper()
    if code == "DISCOGS":
        return 0
    if code == "MANIADB":
        return 1
    if code == "MUSICBRAINZ":
        return 2
    return 3


def list_duplicate_album_masters(album_master_id: int, limit: int = 20) -> list[dict[str, Any]]:
    master_id = int(album_master_id or 0)
    if master_id <= 0:
        return []
    limit_n = max(1, min(100, int(limit or 20)))

    with get_conn() as conn:
        source_row = conn.execute(
            """
            SELECT id, title, artist_or_brand, release_year
            FROM album_master
            WHERE id = ?
            LIMIT 1
            """,
            (master_id,),
        ).fetchone()
        if source_row is None:
            return []

        norm_title = str(source_row["title"] or "").strip().lower()
        norm_artist = str(source_row["artist_or_brand"] or "").strip().lower()
        if not norm_title:
            return []
        base_year = source_row["release_year"]

        rows = conn.execute(
            """
            SELECT
              am.id AS album_master_id,
              am.source_code,
              am.source_master_id,
              am.title,
              am.artist_or_brand,
              am.release_year,
              am.updated_at,
              (
                SELECT COUNT(*)
                FROM album_master_member amm
                WHERE amm.album_master_id = am.id
              ) AS member_count
            FROM album_master am
            WHERE am.id <> ?
              AND LOWER(TRIM(COALESCE(am.title, ''))) = ?
              AND LOWER(TRIM(COALESCE(am.artist_or_brand, ''))) = ?
              AND (
                ? IS NULL
                OR am.release_year = ?
                OR am.release_year IS NULL
              )
            ORDER BY
              CASE am.source_code
                WHEN 'DISCOGS' THEN 0
                WHEN 'MANIADB' THEN 1
                ELSE 2
              END ASC,
              CASE
                WHEN ? IS NOT NULL AND am.release_year = ? THEN 0
                ELSE 1
              END ASC,
              member_count DESC,
              am.updated_at DESC,
              am.id DESC
            LIMIT ?
            """,
            (master_id, norm_title, norm_artist, base_year, base_year, base_year, base_year, limit_n),
        ).fetchall()

    return [dict(row) for row in rows]


def merge_album_masters(source_album_master_id: int, target_album_master_id: int) -> dict[str, int]:
    source_id = int(source_album_master_id or 0)
    target_id = int(target_album_master_id or 0)
    if source_id <= 0 or target_id <= 0:
        raise ValueError("source/target album_master_id must be positive")

    with get_conn() as conn:
        target_exists = conn.execute(
            """
            SELECT id
            FROM album_master
            WHERE id = ?
            LIMIT 1
            """,
            (target_id,),
        ).fetchone()
        if target_exists is None:
            raise LookupError("target album_master not found")

        if source_id == target_id:
            target_member_count_row = conn.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM album_master_member
                WHERE album_master_id = ?
                """,
                (target_id,),
            ).fetchone()
            return {
                "source_album_master_id": source_id,
                "target_album_master_id": target_id,
                "moved_member_count": 0,
                "target_member_count": int(target_member_count_row["cnt"] or 0) if target_member_count_row else 0,
            }

        source_row = conn.execute(
            """
            SELECT id, title, artist_or_brand, sort_artist_name, domain_code, release_year, raw_json
            FROM album_master
            WHERE id = ?
            LIMIT 1
            """,
            (source_id,),
        ).fetchone()
        if source_row is None:
            raise LookupError("source album_master not found")

        now = utc_now_iso()
        source_member_count_row = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM album_master_member
            WHERE album_master_id = ?
            """,
            (source_id,),
        ).fetchone()
        moved_member_count = int(source_member_count_row["cnt"] or 0) if source_member_count_row else 0

        conn.execute(
            """
            INSERT OR IGNORE INTO album_master_member
              (album_master_id, owned_item_id, created_at)
            SELECT ?, owned_item_id, ?
            FROM album_master_member
            WHERE album_master_id = ?
            """,
            (target_id, now, source_id),
        )
        conn.execute(
            """
            UPDATE owned_item
            SET linked_album_master_id = ?, updated_at = ?
            WHERE linked_album_master_id = ?
            """,
            (target_id, now, source_id),
        )
        conn.execute(
            """
            UPDATE album_master
            SET title = CASE
                          WHEN TRIM(COALESCE(title, '')) = '' THEN ?
                          ELSE title
                        END,
                artist_or_brand = CASE
                                    WHEN TRIM(COALESCE(artist_or_brand, '')) = '' THEN ?
                                    ELSE artist_or_brand
                                  END,
                sort_artist_name = CASE
                                     WHEN TRIM(COALESCE(sort_artist_name, '')) = '' THEN ?
                                     ELSE sort_artist_name
                                   END,
                domain_code = CASE
                                WHEN TRIM(COALESCE(domain_code, '')) = '' THEN ?
                                ELSE domain_code
                              END,
                release_year = COALESCE(release_year, ?),
                raw_json = CASE
                             WHEN TRIM(COALESCE(raw_json, '')) IN ('', '{}') THEN ?
                             ELSE raw_json
                           END,
                updated_at = ?
            WHERE id = ?
            """,
            (
                str(source_row["title"] or "").strip() or None,
                str(source_row["artist_or_brand"] or "").strip() or None,
                str(source_row["sort_artist_name"] or "").strip() or None,
                _normalize_domain_code_value(source_row["domain_code"]),
                source_row["release_year"],
                str(source_row["raw_json"] or "{}"),
                now,
                target_id,
            ),
        )
        _sync_album_master_domain_code_in_conn(conn, target_id)
        conn.execute(
            """
            UPDATE album_master_external_ref
            SET album_master_id = ?, updated_at = ?
            WHERE album_master_id = ?
            """,
            (target_id, now, source_id),
        )
        conn.execute("DELETE FROM album_master WHERE id = ?", (source_id,))

        target_member_count_row = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM album_master_member
            WHERE album_master_id = ?
            """,
            (target_id,),
        ).fetchone()

    return {
        "source_album_master_id": source_id,
        "target_album_master_id": target_id,
        "moved_member_count": moved_member_count,
        "target_member_count": int(target_member_count_row["cnt"] or 0) if target_member_count_row else 0,
    }


def bind_album_master_members(
    album_master_id: int,
    owned_item_ids: list[int],
    replace_existing: bool = True,
) -> int:
    unique_ids = sorted({int(v) for v in owned_item_ids if int(v) > 0})
    now = utc_now_iso()

    with get_conn() as conn:
        if replace_existing:
            conn.execute("DELETE FROM album_master_member WHERE album_master_id = ?", (album_master_id,))

        valid_ids: list[int] = []
        if unique_ids:
            placeholders = ",".join("?" for _ in unique_ids)
            rows = conn.execute(
                f"SELECT id FROM owned_item WHERE id IN ({placeholders})",
                unique_ids,
            ).fetchall()
            valid_id_set = {int(r["id"]) for r in rows}
            valid_ids = [v for v in unique_ids if v in valid_id_set]

        if valid_ids:
            conn.executemany(
                """
                INSERT OR IGNORE INTO album_master_member
                  (album_master_id, owned_item_id, created_at)
                VALUES (?, ?, ?)
                """,
                [(album_master_id, owned_item_id, now) for owned_item_id in valid_ids],
            )
        _sync_album_master_domain_code_in_conn(conn, album_master_id)

        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM album_master_member WHERE album_master_id = ?",
            (album_master_id,),
        ).fetchone()
    return int(row["cnt"]) if row else 0


def album_master_exists(album_master_id: int) -> bool:
    mid = int(album_master_id or 0)
    if mid <= 0:
        return False
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM album_master WHERE id = ?", (mid,)).fetchone()
        return row is not None


def update_album_master_sort_artist_name(album_master_id: int, sort_artist_name: str | None) -> dict[str, Any] | None:
    master_id = int(album_master_id or 0)
    if master_id <= 0:
        return None
    normalized_value = str(sort_artist_name or "").strip() or None
    now = utc_now_iso()
    with get_conn() as conn:
        cur = conn.execute(
            """
            UPDATE album_master
            SET sort_artist_name = ?, updated_at = ?
            WHERE id = ?
            """,
            (normalized_value, now, master_id),
        )
        if int(cur.rowcount or 0) <= 0:
            return None
        row = conn.execute(
            """
            SELECT id, sort_artist_name
            FROM album_master
            WHERE id = ?
            LIMIT 1
            """,
            (master_id,),
        ).fetchone()
    return dict(row) if row else None


def set_owned_item_linked_album_master(owned_item_id: int, album_master_id: int | None) -> bool:
    oid = int(owned_item_id or 0)
    if oid <= 0:
        return False
    mid = int(album_master_id) if album_master_id is not None else None
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE owned_item SET linked_album_master_id = ?, updated_at = ? WHERE id = ?",
            (mid, utc_now_iso(), oid),
        )
        return int(cur.rowcount or 0) > 0


def _build_album_master_filter_sql(
    source_code: str | None,
    q: str | None,
    artist_or_brand: str | None,
    item_name: str | None,
    catalog_no: str | None,
    barcode: str | None,
    release_year: int | None,
    category: str | None,
    media_only: bool,
    domain_code: str | None,
    release_type: str | None,
) -> tuple[str, list[Any]]:
    where_sql = ""
    params: list[Any] = []
    master_search_expr = "COALESCE(am.artist_or_brand, '') || ' ' || COALESCE(am.title, '')"
    member_search_expr = """
        COALESCE(mid.artist_or_brand, '') || ' ' ||
        COALESCE(oi.item_name_override, '') || ' ' ||
        COALESCE(mid.label_name, '') || ' ' ||
        COALESCE(mid.catalog_no, '') || ' ' ||
        COALESCE(mid.barcode, '') || ' ' ||
        COALESCE(mid.track_list_json, '') || ' ' ||
        COALESCE(mid.track_items_json, '')
    """

    if source_code:
        where_sql += " AND am.source_code = ?"
        params.append(source_code)

    if q and q.strip():
        q_norm = f"%{q.strip().lower()}%"
        q_token_groups = _search_token_groups(q)
        master_token_sql, master_token_params = _build_compact_token_match_sql(master_search_expr, q_token_groups)
        member_token_sql, member_token_params = _build_compact_token_match_sql(member_search_expr, q_token_groups)
        where_sql += """
          AND (
            LOWER(am.title) LIKE ?
            OR LOWER(COALESCE(am.artist_or_brand, '')) LIKE ?
            OR EXISTS (
              SELECT 1
              FROM album_master_member amm
              JOIN owned_item oi ON oi.id = amm.owned_item_id
              LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
              WHERE amm.album_master_id = am.id
                AND (
                  LOWER(COALESCE(oi.item_name_override, '')) LIKE ?
                  OR LOWER(COALESCE(mid.artist_or_brand, '')) LIKE ?
                  OR LOWER(COALESCE(mid.label_name, '')) LIKE ?
                  OR LOWER(COALESCE(mid.catalog_no, '')) LIKE ?
                  OR LOWER(COALESCE(mid.barcode, '')) LIKE ?
                  OR EXISTS (
                    SELECT 1
                    FROM json_each(COALESCE(mid.track_list_json, '[]')) jt
                    WHERE LOWER(COALESCE(jt.value, '')) LIKE ?
                  )
                  OR EXISTS (
                    SELECT 1
                    FROM json_each(COALESCE(mid.track_items_json, '[]')) ji
                    WHERE LOWER(COALESCE(json_extract(ji.value, '$.display'), '')) LIKE ?
                       OR LOWER(COALESCE(json_extract(ji.value, '$.title'), '')) LIKE ?
                  )
                )
            )
        """
        params.extend([q_norm, q_norm, q_norm, q_norm, q_norm, q_norm, q_norm, q_norm, q_norm, q_norm])
        if master_token_sql:
            where_sql += f"""
            OR {master_token_sql}
            """
            params.extend(master_token_params)
        if member_token_sql:
            where_sql += f"""
            OR EXISTS (
              SELECT 1
              FROM album_master_member amm
              JOIN owned_item oi ON oi.id = amm.owned_item_id
              LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
              WHERE amm.album_master_id = am.id
                AND {member_token_sql}
            )
            """
            params.extend(member_token_params)
        where_sql += """
          )
        """

    if artist_or_brand and artist_or_brand.strip():
        artist_norm = f"%{artist_or_brand.strip().lower()}%"
        where_sql += """
          AND (
            LOWER(COALESCE(am.artist_or_brand, '')) LIKE ?
            OR EXISTS (
              SELECT 1
              FROM album_master_member amm
              JOIN owned_item oi ON oi.id = amm.owned_item_id
              LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
              WHERE amm.album_master_id = am.id
                AND LOWER(COALESCE(mid.artist_or_brand, '')) LIKE ?
            )
          )
        """
        params.extend([artist_norm, artist_norm])

    if item_name and item_name.strip():
        item_norm = f"%{item_name.strip().lower()}%"
        item_token_groups = _search_token_groups(item_name)
        master_token_sql, master_token_params = _build_compact_token_match_sql(master_search_expr, item_token_groups)
        member_token_sql, member_token_params = _build_compact_token_match_sql(member_search_expr, item_token_groups)
        where_sql += """
          AND (
            LOWER(am.title) LIKE ?
            OR LOWER(COALESCE(am.artist_or_brand, '') || ' ' || COALESCE(am.title, '')) LIKE ?
            OR EXISTS (
              SELECT 1
              FROM album_master_member amm
              JOIN owned_item oi ON oi.id = amm.owned_item_id
              LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
              WHERE amm.album_master_id = am.id
                AND (
                  LOWER(COALESCE(oi.item_name_override, '')) LIKE ?
                  OR LOWER(COALESCE(mid.artist_or_brand, '')) LIKE ?
                  OR LOWER(COALESCE(mid.label_name, '')) LIKE ?
                  OR LOWER(COALESCE(mid.catalog_no, '')) LIKE ?
                  OR LOWER(COALESCE(mid.barcode, '')) LIKE ?
                  OR LOWER(COALESCE(mid.artist_or_brand, '') || ' ' || COALESCE(oi.item_name_override, '')) LIKE ?
                  OR EXISTS (
                    SELECT 1
                    FROM json_each(COALESCE(mid.track_list_json, '[]')) jt
                    WHERE LOWER(COALESCE(jt.value, '')) LIKE ?
                  )
                  OR EXISTS (
                    SELECT 1
                    FROM json_each(COALESCE(mid.track_items_json, '[]')) ji
                    WHERE LOWER(COALESCE(json_extract(ji.value, '$.display'), '')) LIKE ?
                       OR LOWER(COALESCE(json_extract(ji.value, '$.title'), '')) LIKE ?
                  )
        """
        params.extend([item_norm, item_norm, item_norm, item_norm, item_norm, item_norm, item_norm, item_norm, item_norm, item_norm, item_norm])
        if member_token_sql:
            where_sql += f"""
                  OR {member_token_sql}
            """
            params.extend(member_token_params)
        where_sql += """
                )
            )
        """
        if master_token_sql:
            where_sql += f"""
            OR {master_token_sql}
            """
            params.extend(master_token_params)
        where_sql += """
          )
        """

    if catalog_no and catalog_no.strip():
        catalog_norm = f"%{catalog_no.strip().lower()}%"
        where_sql += """
          AND EXISTS (
            SELECT 1
            FROM album_master_member amm
            JOIN music_item_detail mid ON mid.owned_item_id = amm.owned_item_id
            WHERE amm.album_master_id = am.id
              AND LOWER(COALESCE(mid.catalog_no, '')) LIKE ?
          )
        """
        params.append(catalog_norm)

    if barcode and barcode.strip():
        barcode_norm = f"%{barcode.strip().replace('-', '')}%"
        where_sql += """
          AND EXISTS (
            SELECT 1
            FROM album_master_member amm
            JOIN music_item_detail mid ON mid.owned_item_id = amm.owned_item_id
            WHERE amm.album_master_id = am.id
              AND REPLACE(COALESCE(mid.barcode, ''), '-', '') LIKE ?
          )
        """
        params.append(barcode_norm)

    if release_year is not None:
        where_sql += """
          AND (
            am.release_year = ?
            OR EXISTS (
              SELECT 1
              FROM album_master_member amm
              JOIN music_item_detail mid ON mid.owned_item_id = amm.owned_item_id
              WHERE amm.album_master_id = am.id
                AND mid.release_year = ?
            )
          )
        """
        params.extend([int(release_year), int(release_year)])

    if category:
        where_sql += """
          AND EXISTS (
            SELECT 1
            FROM album_master_member amm
            JOIN owned_item oi ON oi.id = amm.owned_item_id
            WHERE amm.album_master_id = am.id
              AND oi.category = ?
          )
        """
        params.append(category)

    if media_only:
        where_sql += """
          AND EXISTS (
            SELECT 1
            FROM album_master_member amm
            JOIN owned_item oi ON oi.id = amm.owned_item_id
            WHERE amm.album_master_id = am.id
              AND oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
          )
        """

    if domain_code:
        where_sql += """
          AND (
            am.domain_code = ?
            OR EXISTS (
              SELECT 1
              FROM album_master_member amm
              JOIN owned_item oi ON oi.id = amm.owned_item_id
              WHERE amm.album_master_id = am.id
                AND oi.domain_code = ?
            )
          )
        """
        params.extend([domain_code, domain_code])

    if release_type:
        where_sql += """
          AND EXISTS (
            SELECT 1
            FROM album_master_member amm
            JOIN owned_item oi ON oi.id = amm.owned_item_id
            WHERE amm.album_master_id = am.id
              AND oi.release_type = ?
          )
        """
        params.append(release_type)

    return where_sql, params


def list_album_masters(
    source_code: str | None,
    q: str | None,
    artist_or_brand: str | None,
    item_name: str | None,
    catalog_no: str | None,
    barcode: str | None,
    release_year: int | None,
    category: str | None,
    media_only: bool,
    domain_code: str | None,
    release_type: str | None,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    filter_sql, params = _build_album_master_filter_sql(
        source_code=source_code,
        q=q,
        artist_or_brand=artist_or_brand,
        item_name=item_name,
        catalog_no=catalog_no,
        barcode=barcode,
        release_year=release_year,
        category=category,
        media_only=media_only,
        domain_code=domain_code,
        release_type=release_type,
    )

    query = """
      SELECT
        am.id,
        am.source_code,
        am.source_master_id,
        am.title,
        am.artist_or_brand,
        am.sort_artist_name,
        am.domain_code,
        am.release_year,
        am.updated_at,
        COUNT(amm.id) AS member_count,
        (
          SELECT mid.cover_image_url
          FROM album_master_member amm_cov
          JOIN owned_item oi_cov ON oi_cov.id = amm_cov.owned_item_id
          LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi_cov.id
          WHERE amm_cov.album_master_id = am.id
            AND mid.cover_image_url IS NOT NULL
            AND TRIM(mid.cover_image_url) <> ''
          ORDER BY
            CASE WHEN oi_cov.order_key IS NULL OR TRIM(oi_cov.order_key) = '' THEN 1 ELSE 0 END,
            oi_cov.order_key ASC,
            oi_cov.id ASC
          LIMIT 1
        ) AS cover_image_url,
        (
          SELECT COUNT(*)
          FROM album_master_member amm_audio
          JOIN owned_item_digital_link oidl ON oidl.owned_item_id = amm_audio.owned_item_id
          JOIN digital_asset da ON da.id = oidl.digital_asset_id
          WHERE amm_audio.album_master_id = am.id
            AND da.asset_type = 'AUDIO'
        ) AS audio_asset_count,
        (
          SELECT GROUP_CONCAT(preview_text, ' || ')
          FROM (
            SELECT TRIM(
              CASE
                WHEN TRIM(COALESCE(mid.label_name, '')) <> '' THEN mid.label_name
                ELSE ''
              END ||
              CASE
                WHEN TRIM(COALESCE(mid.catalog_no, '')) <> '' THEN
                  CASE WHEN TRIM(COALESCE(mid.label_name, '')) <> '' THEN ' / ' ELSE '' END || mid.catalog_no
                ELSE ''
              END ||
              CASE
                WHEN TRIM(COALESCE(mid.barcode, '')) <> '' THEN
                  CASE
                    WHEN TRIM(COALESCE(mid.label_name, '')) <> '' OR TRIM(COALESCE(mid.catalog_no, '')) <> '' THEN ' / '
                    ELSE ''
                  END || mid.barcode
                ELSE ''
              END
            ) AS preview_text
            FROM album_master_member amm_prev
            JOIN owned_item oi_prev ON oi_prev.id = amm_prev.owned_item_id
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi_prev.id
            WHERE amm_prev.album_master_id = am.id
            ORDER BY
              CASE WHEN oi_prev.order_key IS NULL OR TRIM(oi_prev.order_key) = '' THEN 1 ELSE 0 END,
              oi_prev.order_key ASC,
              oi_prev.id ASC
            LIMIT 4
          ) preview_rows
          WHERE TRIM(COALESCE(preview_text, '')) <> ''
        ) AS member_preview_text,
        (
          SELECT GROUP_CONCAT(preview_text, ' || ')
          FROM (
            SELECT TRIM(
              CASE
                WHEN ss.id IS NULL THEN '미배치'
                WHEN TRIM(COALESCE(ss.cabinet_name, '')) <> '' THEN ss.cabinet_name
                WHEN TRIM(COALESCE(ss.slot_code, '')) <> '' THEN ss.slot_code
                ELSE '미배치'
              END ||
              CASE
                WHEN TRIM(COALESCE(ss.column_code, '')) <> '' THEN ' / ' || ss.column_code || '층'
                ELSE ''
              END ||
              CASE
                WHEN TRIM(COALESCE(ss.cell_code, '')) <> '' THEN ' / ' || ss.cell_code || '칸'
                ELSE ''
              END
            ) AS preview_text
            FROM album_master_member amm_loc
            JOIN owned_item oi_loc ON oi_loc.id = amm_loc.owned_item_id
            LEFT JOIN storage_slot ss ON ss.id = oi_loc.storage_slot_id
            WHERE amm_loc.album_master_id = am.id
            ORDER BY
              CASE WHEN oi_loc.order_key IS NULL OR TRIM(oi_loc.order_key) = '' THEN 1 ELSE 0 END,
              oi_loc.order_key ASC,
              oi_loc.id ASC
            LIMIT 4
          ) preview_rows
          WHERE TRIM(COALESCE(preview_text, '')) <> ''
        ) AS member_location_preview_text,
        (
          SELECT oi_loc.storage_slot_id
          FROM album_master_member amm_first
          JOIN owned_item oi_loc ON oi_loc.id = amm_first.owned_item_id
          WHERE amm_first.album_master_id = am.id
            AND oi_loc.storage_slot_id IS NOT NULL
          ORDER BY
            CASE WHEN oi_loc.order_key IS NULL OR TRIM(oi_loc.order_key) = '' THEN 1 ELSE 0 END,
            oi_loc.order_key ASC,
            oi_loc.id ASC
          LIMIT 1
        ) AS first_member_storage_slot_id,
        (
          SELECT ss.slot_code
          FROM album_master_member amm_first
          JOIN owned_item oi_loc ON oi_loc.id = amm_first.owned_item_id
          LEFT JOIN storage_slot ss ON ss.id = oi_loc.storage_slot_id
          WHERE amm_first.album_master_id = am.id
            AND oi_loc.storage_slot_id IS NOT NULL
          ORDER BY
            CASE WHEN oi_loc.order_key IS NULL OR TRIM(oi_loc.order_key) = '' THEN 1 ELSE 0 END,
            oi_loc.order_key ASC,
            oi_loc.id ASC
          LIMIT 1
        ) AS first_member_slot_code,
        (
          SELECT ss.cabinet_name
          FROM album_master_member amm_first
          JOIN owned_item oi_loc ON oi_loc.id = amm_first.owned_item_id
          LEFT JOIN storage_slot ss ON ss.id = oi_loc.storage_slot_id
          WHERE amm_first.album_master_id = am.id
            AND oi_loc.storage_slot_id IS NOT NULL
          ORDER BY
            CASE WHEN oi_loc.order_key IS NULL OR TRIM(oi_loc.order_key) = '' THEN 1 ELSE 0 END,
            oi_loc.order_key ASC,
            oi_loc.id ASC
          LIMIT 1
        ) AS first_member_cabinet_name,
        (
          SELECT ss.column_code
          FROM album_master_member amm_first
          JOIN owned_item oi_loc ON oi_loc.id = amm_first.owned_item_id
          LEFT JOIN storage_slot ss ON ss.id = oi_loc.storage_slot_id
          WHERE amm_first.album_master_id = am.id
            AND oi_loc.storage_slot_id IS NOT NULL
          ORDER BY
            CASE WHEN oi_loc.order_key IS NULL OR TRIM(oi_loc.order_key) = '' THEN 1 ELSE 0 END,
            oi_loc.order_key ASC,
            oi_loc.id ASC
          LIMIT 1
        ) AS first_member_column_code,
        (
          SELECT ss.cell_code
          FROM album_master_member amm_first
          JOIN owned_item oi_loc ON oi_loc.id = amm_first.owned_item_id
          LEFT JOIN storage_slot ss ON ss.id = oi_loc.storage_slot_id
          WHERE amm_first.album_master_id = am.id
            AND oi_loc.storage_slot_id IS NOT NULL
          ORDER BY
            CASE WHEN oi_loc.order_key IS NULL OR TRIM(oi_loc.order_key) = '' THEN 1 ELSE 0 END,
            oi_loc.order_key ASC,
            oi_loc.id ASC
          LIMIT 1
        ) AS first_member_cell_code
      FROM album_master am
      LEFT JOIN album_master_member amm ON amm.album_master_id = am.id
      WHERE 1 = 1
    """
    query += filter_sql
    query += """
      GROUP BY am.id
      ORDER BY am.updated_at DESC, am.id DESC
      LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def list_album_master_track_matches(album_master_id: int, query_text: str, limit: int = 3) -> list[str]:
    master_id = int(album_master_id or 0)
    clean_query = str(query_text or "").strip()
    if master_id <= 0 or not clean_query:
        return []

    token_groups = _search_token_groups(clean_query)
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
              mid.track_list_json,
              mid.track_items_json
            FROM album_master_member amm
            JOIN music_item_detail mid ON mid.owned_item_id = amm.owned_item_id
            WHERE amm.album_master_id = ?
            ORDER BY amm.id ASC
            """,
            (master_id,),
        ).fetchall()

    matches: list[str] = []
    seen: set[str] = set()

    def _push(value: Any) -> None:
        text = str(value or "").strip()
        key = text.lower()
        if not text or key in seen:
            return
        if not _matches_search_text(text, clean_query, token_groups):
            return
        seen.add(key)
        matches.append(text)

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

    for row in rows:
        track_list = _parse_json_string_list(row["track_list_json"])
        track_items = _parse_json_dict_list(row["track_items_json"])
        for track in track_list:
            _push(track)
        for item in track_items:
            if not isinstance(item, dict):
                continue
            _push(item.get("display"))
            _push(item.get("title"))
        if len(matches) >= max(1, int(limit)):
            break

    return matches[: max(1, int(limit))]


def count_album_masters(
    source_code: str | None,
    q: str | None,
    artist_or_brand: str | None,
    item_name: str | None,
    catalog_no: str | None,
    barcode: str | None,
    release_year: int | None,
    category: str | None,
    media_only: bool,
    domain_code: str | None,
    release_type: str | None,
) -> int:
    filter_sql, params = _build_album_master_filter_sql(
        source_code=source_code,
        q=q,
        artist_or_brand=artist_or_brand,
        item_name=item_name,
        catalog_no=catalog_no,
        barcode=barcode,
        release_year=release_year,
        category=category,
        media_only=media_only,
        domain_code=domain_code,
        release_type=release_type,
    )
    query = """
      SELECT COUNT(*) AS cnt
      FROM album_master am
      WHERE 1 = 1
    """
    query += filter_sql
    with get_conn() as conn:
        row = conn.execute(query, params).fetchone()
    return int(row["cnt"]) if row else 0


def list_album_master_members(album_master_id: int) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
              oi.id AS owned_item_id,
              oi.category,
              oi.item_name_override,
              oi.quantity,
              oi.status,
              mid.format_name
            FROM album_master_member amm
            JOIN owned_item oi ON oi.id = amm.owned_item_id
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            WHERE amm.album_master_id = ?
            ORDER BY oi.category ASC, oi.id ASC
            """,
            (album_master_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_album_master(album_master_id: int, cascade_items: bool = False) -> dict[str, int] | None:
    master_id = int(album_master_id or 0)
    if master_id <= 0:
        return None

    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM album_master WHERE id = ?",
            (master_id,),
        ).fetchone()
        if existing is None:
            return None

        member_rows = conn.execute(
            """
            SELECT DISTINCT owned_item_id
            FROM album_master_member
            WHERE album_master_id = ?
            """,
            (master_id,),
        ).fetchall()
        member_ids = [int(r["owned_item_id"]) for r in member_rows if r["owned_item_id"] is not None]
        removed_member_links = len(member_ids)

        deleted_owned_item_count = 0
        if cascade_items and member_ids:
            placeholders = ",".join("?" for _ in member_ids)
            cur_items = conn.execute(
                f"DELETE FROM owned_item WHERE id IN ({placeholders})",
                member_ids,
            )
            deleted_owned_item_count = int(cur_items.rowcount or 0)

        cur_master = conn.execute(
            "DELETE FROM album_master WHERE id = ?",
            (master_id,),
        )
        if int(cur_master.rowcount or 0) <= 0:
            return None

    return {
        "removed_member_links": removed_member_links,
        "deleted_owned_item_count": deleted_owned_item_count,
    }


def get_storage_slot(slot_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM storage_slot WHERE id = ?", (slot_id,)).fetchone()
    if row is None:
        return None
    item = dict(row)
    item["display_name"] = _storage_slot_display_name(item)
    return item


def get_storage_slot_by_code(slot_code: str) -> dict[str, Any] | None:
    code = str(slot_code or "").strip()
    if not code:
        return None
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM storage_slot WHERE slot_code = ? LIMIT 1", (code,)).fetchone()
    if row is None:
        return None
    item = dict(row)
    item["display_name"] = _storage_slot_display_name(item)
    return item


def list_storage_slots() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, slot_code, cabinet_name, column_code, cell_code, allowed_size_group, cabinet_sort_policy, is_overflow_zone
            FROM storage_slot
            """
        ).fetchall()
    items = [dict(row) for row in rows]
    for item in items:
        item["display_name"] = _storage_slot_display_name(item)
    items.sort(key=_storage_slot_sort_key)
    return items


def list_cabinet_cameras(cabinet_name: str | None = None) -> list[dict[str, Any]]:
    params: list[Any] = []
    query = """
        SELECT
          id,
          cabinet_name,
          camera_name,
          onvif_device_url,
          snapshot_url,
          stream_url,
          username,
          password,
          notes,
          is_active,
          created_at,
          updated_at
        FROM cabinet_camera
    """
    cabinet = str(cabinet_name or "").strip()
    if cabinet:
        query += " WHERE TRIM(COALESCE(cabinet_name, '')) = ?"
        params.append(cabinet)
    query += " ORDER BY is_active DESC, LOWER(cabinet_name) ASC, id ASC"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_cabinet_camera(camera_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT
              id,
              cabinet_name,
              camera_name,
              onvif_device_url,
              snapshot_url,
              stream_url,
              username,
              password,
              notes,
              is_active,
              created_at,
              updated_at
            FROM cabinet_camera
            WHERE id = ?
            LIMIT 1
            """,
            (int(camera_id),),
        ).fetchone()
    return dict(row) if row is not None else None


def get_cabinet_camera_by_cabinet(cabinet_name: str) -> dict[str, Any] | None:
    cabinet = str(cabinet_name or "").strip()
    if not cabinet:
        return None
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT
              id,
              cabinet_name,
              camera_name,
              onvif_device_url,
              snapshot_url,
              stream_url,
              username,
              password,
              notes,
              is_active,
              created_at,
              updated_at
            FROM cabinet_camera
            WHERE TRIM(COALESCE(cabinet_name, '')) = ?
            LIMIT 1
            """,
            (cabinet,),
        ).fetchone()
    return dict(row) if row is not None else None


def upsert_cabinet_camera(
    *,
    camera_id: int | None = None,
    cabinet_name: str,
    camera_name: str,
    onvif_device_url: str | None = None,
    snapshot_url: str | None = None,
    stream_url: str | None = None,
    username: str | None = None,
    password: str | None = None,
    notes: str | None = None,
    is_active: bool = True,
) -> dict[str, Any] | None:
    cabinet = str(cabinet_name or "").strip()
    name = str(camera_name or "").strip()
    if not cabinet:
        raise ValueError("cabinet_name required")
    if not name:
        raise ValueError("camera_name required")
    now = utc_now_iso()
    device_url = str(onvif_device_url or "").strip() or None
    snapshot = str(snapshot_url or "").strip() or None
    stream = str(stream_url or "").strip() or None
    user = str(username or "").strip() or None
    secret = str(password or "")
    secret_value = secret if secret.strip() else None
    memo = str(notes or "").strip() or None
    active_value = int(bool(is_active))

    with get_conn() as conn:
        existing = None
        if camera_id is not None:
            existing = conn.execute("SELECT * FROM cabinet_camera WHERE id = ?", (int(camera_id),)).fetchone()
            if existing is None:
                raise ValueError("cabinet_camera not found")
        else:
            existing = conn.execute(
                "SELECT * FROM cabinet_camera WHERE TRIM(COALESCE(cabinet_name, '')) = ?",
                (cabinet,),
            ).fetchone()
        if existing is not None:
            existing_id = int(existing["id"])
            duplicate = conn.execute(
                "SELECT id FROM cabinet_camera WHERE TRIM(COALESCE(cabinet_name, '')) = ? AND id <> ?",
                (cabinet, existing_id),
            ).fetchone()
            if duplicate is not None:
                raise ValueError("duplicate cabinet camera mapping")
            if secret_value is None:
                secret_value = str(existing["password"] or "").strip() or None
            conn.execute(
                """
                UPDATE cabinet_camera
                SET cabinet_name = ?, camera_name = ?, onvif_device_url = ?, snapshot_url = ?, stream_url = ?,
                    username = ?, password = ?, notes = ?, is_active = ?, updated_at = ?
                WHERE id = ?
                """,
                (cabinet, name, device_url, snapshot, stream, user, secret_value, memo, active_value, now, existing_id),
            )
            row = conn.execute("SELECT * FROM cabinet_camera WHERE id = ?", (existing_id,)).fetchone()
        else:
            cur = conn.execute(
                """
                INSERT INTO cabinet_camera
                  (cabinet_name, camera_name, onvif_device_url, snapshot_url, stream_url, username, password, notes, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (cabinet, name, device_url, snapshot, stream, user, secret_value, memo, active_value, now, now),
            )
            row = conn.execute("SELECT * FROM cabinet_camera WHERE id = ?", (int(cur.lastrowid),)).fetchone()
    return dict(row) if row is not None else None


def delete_cabinet_camera(camera_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM cabinet_camera WHERE id = ?", (int(camera_id),))
    return int(cur.rowcount or 0) > 0


def list_owned_items_for_storage_slot(
    storage_slot_id: int,
    limit: int = 300,
    offset: int = 0,
) -> list[dict[str, Any]]:
    recent_cutoff = (datetime.now(timezone.utc) - timedelta(days=DASHBOARD_MOVE_WINDOW_DAYS)).isoformat()
    slot = get_storage_slot(storage_slot_id) or {}
    cabinet_sort_policy = _normalize_cabinet_sort_policy_value(slot.get("cabinet_sort_policy"))
    if cabinet_sort_policy == "LABEL_ID":
        order_by_sql = """
          base.id ASC
        """
    else:
        order_by_sql = """
          LOWER(TRIM(COALESCE(am.sort_artist_name, base.artist_or_brand, am.artist_or_brand, base.linked_artist_name, ''))) ASC,
          CASE WHEN COALESCE(am.release_year, base.release_year) IS NULL THEN 1 ELSE 0 END,
          COALESCE(am.release_year, base.release_year) ASC,
          LOWER(TRIM(COALESCE(am.title, base.item_name_override, ''))) ASC,
          CASE WHEN base.order_key IS NULL OR TRIM(base.order_key) = '' THEN 1 ELSE 0 END,
          base.order_key ASC,
          CASE WHEN base.display_rank IS NULL THEN 1 ELSE 0 END,
          base.display_rank ASC,
          base.id ASC
        """
    query = f"""
        WITH base AS (
{_owned_item_select_query()}
        )
        SELECT
          base.*,
          am.title AS master_title,
          am.artist_or_brand AS master_artist_or_brand,
          am.sort_artist_name AS master_sort_artist_name,
          am.domain_code AS master_domain_code,
          am.release_year AS master_release_year,
          (
            SELECT e.from_slot_code
            FROM owned_item_location_event e
            WHERE e.owned_item_id = base.id
              AND TRIM(COALESCE(e.from_slot_code, '')) <> ''
            ORDER BY e.created_at DESC, e.id DESC
            LIMIT 1
          ) AS previous_slot_code,
          (
            SELECT e.from_slot_display_name
            FROM owned_item_location_event e
            WHERE e.owned_item_id = base.id
              AND TRIM(COALESCE(e.from_slot_display_name, '')) <> ''
            ORDER BY e.created_at DESC, e.id DESC
            LIMIT 1
          ) AS previous_slot_display_name,
          (
            SELECT e.created_at
            FROM owned_item_location_event e
            WHERE e.owned_item_id = base.id
            ORDER BY e.created_at DESC, e.id DESC
            LIMIT 1
          ) AS last_slot_event_at,
          COALESCE((
            SELECT CASE
              WHEN e.to_storage_slot_id = base.storage_slot_id
               AND e.movement_kind IN ('INITIAL_ASSIGN', 'ASSIGN', 'MOVE')
               AND e.created_at >= ?
              THEN 1 ELSE 0 END
            FROM owned_item_location_event e
            WHERE e.owned_item_id = base.id
            ORDER BY e.created_at DESC, e.id DESC
            LIMIT 1
          ), 0) AS recently_moved_to_current_slot
        FROM base
        LEFT JOIN album_master am ON am.id = base.linked_album_master_id
        WHERE base.status = 'IN_COLLECTION'
          AND base.storage_slot_id = ?
        ORDER BY
          {order_by_sql}
        LIMIT ? OFFSET ?
    """
    with get_conn() as conn:
        rows = conn.execute(query, (recent_cutoff, int(storage_slot_id), int(limit), int(offset))).fetchall()
    items = [_normalize_owned_item_row(dict(row)) for row in rows]
    if cabinet_sort_policy == "LABEL_ID":
        items.sort(
            key=lambda row: (
                _natural_sort_key(_build_label_id(row.get("category"), int(row.get("id") or 0))),
                int(row.get("id") or 0),
            )
        )
    else:
        korean_artist_by_master_id = _preferred_korean_artist_by_master_ids(
            [int(item.get("linked_album_master_id") or 0) for item in items]
        )
        items.sort(key=lambda row: _owned_item_storage_sort_key(row, korean_artist_by_master_id))
    return items


def upsert_storage_slot(
    cabinet_name: str,
    column_code: str | None,
    cell_code: str | None,
    allowed_size_group: str,
    cabinet_sort_policy: str | None = None,
    is_overflow_zone: bool = False,
    slot_id: int | None = None,
) -> dict[str, Any]:
    cabinet = str(cabinet_name or "").strip()
    if not cabinet:
        raise ValueError("cabinet_name required")
    column = str(column_code or "").strip() or None
    cell = str(cell_code or "").strip() or None
    size_group = str(allowed_size_group or "").strip().upper()
    if size_group not in SIZE_GROUP_CODES:
        raise ValueError("invalid allowed_size_group")
    sort_policy = _normalize_cabinet_sort_policy_value(cabinet_sort_policy)
    overflow = bool(is_overflow_zone)
    slot_code = _compose_storage_slot_code(cabinet, column, cell, size_group, overflow)
    now = utc_now_iso()

    with get_conn() as conn:
        if slot_id is not None:
            existing = conn.execute("SELECT id, cabinet_sort_policy FROM storage_slot WHERE id = ?", (slot_id,)).fetchone()
            if existing is None:
                raise ValueError("storage_slot not found")
            dup = conn.execute("SELECT id FROM storage_slot WHERE slot_code = ? AND id <> ?", (slot_code, slot_id)).fetchone()
            if dup is not None:
                raise ValueError("duplicate storage_slot code")
            if cabinet_sort_policy is None:
                sort_policy = _normalize_cabinet_sort_policy_value(existing["cabinet_sort_policy"])
            conn.execute(
                """
                UPDATE storage_slot
                SET slot_code = ?, cabinet_name = ?, column_code = ?, cell_code = ?,
                    allowed_size_group = ?, cabinet_sort_policy = ?, is_overflow_zone = ?, updated_at = ?
                WHERE id = ?
                """,
                (slot_code, cabinet, column, cell, size_group, sort_policy, int(overflow), now, slot_id),
            )
            row = conn.execute("SELECT * FROM storage_slot WHERE id = ?", (slot_id,)).fetchone()
        else:
            existing = conn.execute("SELECT id, cabinet_sort_policy FROM storage_slot WHERE slot_code = ?", (slot_code,)).fetchone()
            if existing is not None:
                if cabinet_sort_policy is None:
                    sort_policy = _normalize_cabinet_sort_policy_value(existing["cabinet_sort_policy"])
                conn.execute(
                    """
                    UPDATE storage_slot
                    SET cabinet_name = ?, column_code = ?, cell_code = ?,
                        allowed_size_group = ?, cabinet_sort_policy = ?, is_overflow_zone = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (cabinet, column, cell, size_group, sort_policy, int(overflow), now, int(existing["id"])),
                )
                row = conn.execute("SELECT * FROM storage_slot WHERE id = ?", (int(existing["id"]),)).fetchone()
            else:
                cur = conn.execute(
                    """
                    INSERT INTO storage_slot
                      (slot_code, cabinet_name, column_code, cell_code, allowed_size_group, cabinet_sort_policy, is_overflow_zone, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (slot_code, cabinet, column, cell, size_group, sort_policy, int(overflow), now, now),
                )
                row = conn.execute("SELECT * FROM storage_slot WHERE id = ?", (int(cur.lastrowid),)).fetchone()

    if row is None:
        raise ValueError("storage_slot save failed")
    item = dict(row)
    item["display_name"] = _storage_slot_display_name(item)
    return item


def register_storage_cabinet_slots(
    cabinet_name: str,
    floor_count: int,
    cell_count: int,
    allowed_size_group: str,
    cabinet_sort_policy: str | None = None,
    floor_start: int = 1,
    cell_start: int = 1,
) -> dict[str, Any]:
    cabinet = str(cabinet_name or "").strip()
    if not cabinet:
        raise ValueError("cabinet_name required")

    floors = int(floor_count or 0)
    cells = int(cell_count or 0)
    floor_begin = int(floor_start or 0)
    cell_begin = int(cell_start or 0)
    if floors <= 0 or cells <= 0:
        raise ValueError("floor_count and cell_count must be positive")
    if floor_begin <= 0 or cell_begin <= 0:
        raise ValueError("floor_start and cell_start must be positive")

    size_group = str(allowed_size_group or "").strip().upper()
    if size_group not in SIZE_GROUP_CODES:
        raise ValueError("invalid allowed_size_group")
    sort_policy = _normalize_cabinet_sort_policy_value(cabinet_sort_policy)

    max_floor = floor_begin + floors - 1
    max_cell = cell_begin + cells - 1
    floor_width = max(2, len(str(max_floor)))
    cell_width = max(2, len(str(max_cell)))

    created_count = 0
    updated_count = 0
    now = utc_now_iso()

    with get_conn() as conn:
        for floor_no in range(floor_begin, floor_begin + floors):
            floor_code = str(floor_no).zfill(floor_width)
            for cell_no in range(cell_begin, cell_begin + cells):
                cell_code = str(cell_no).zfill(cell_width)
                slot_code = _compose_storage_slot_code(cabinet, floor_code, cell_code, size_group, False)
                existing = conn.execute(
                    "SELECT id FROM storage_slot WHERE slot_code = ?",
                    (slot_code,),
                ).fetchone()
                if existing is not None:
                    conn.execute(
                        """
                        UPDATE storage_slot
                        SET cabinet_name = ?, column_code = ?, cell_code = ?,
                            allowed_size_group = ?, cabinet_sort_policy = ?, is_overflow_zone = 0, updated_at = ?
                        WHERE id = ?
                        """,
                        (cabinet, floor_code, cell_code, size_group, sort_policy, now, int(existing["id"])),
                    )
                    updated_count += 1
                else:
                    conn.execute(
                        """
                        INSERT INTO storage_slot
                          (slot_code, cabinet_name, column_code, cell_code, allowed_size_group, cabinet_sort_policy, is_overflow_zone, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
                        """,
                        (slot_code, cabinet, floor_code, cell_code, size_group, sort_policy, now, now),
                    )
                    created_count += 1

        total_slot_row = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM storage_slot
            WHERE is_overflow_zone = 0
              AND cabinet_name = ?
            """,
            (cabinet,),
        ).fetchone()

    return {
        "cabinet_name": cabinet,
        "floor_count": floors,
        "cell_count": cells,
        "cabinet_sort_policy": sort_policy,
        "created_count": created_count,
        "updated_count": updated_count,
        "total_slot_count": int(total_slot_row["cnt"] or 0) if total_slot_row is not None else 0,
    }


def delete_storage_cabinet(cabinet_name: str) -> dict[str, Any]:
    cabinet = str(cabinet_name or "").strip()
    if not cabinet:
        raise ValueError("cabinet_name required")
    if cabinet.lower() == "overflow":
        raise ValueError("overflow cabinet cannot be deleted")

    with get_conn() as conn:
        slot_rows = conn.execute(
            """
            SELECT id
            FROM storage_slot
            WHERE cabinet_name = ?
              AND is_overflow_zone = 0
            """,
            (cabinet,),
        ).fetchall()
        slot_ids = [int(row["id"]) for row in slot_rows if row["id"] is not None]
        if not slot_ids:
            raise ValueError("storage_cabinet not found")

        placeholders = ",".join("?" for _ in slot_ids)
        item_rows = conn.execute(
            f"""
            SELECT id, storage_slot_id
            FROM owned_item
            WHERE storage_slot_id IN ({placeholders})
            """,
            slot_ids,
        ).fetchall()
        unassigned_item_count = len(item_rows)
        now = utc_now_iso()

        conn.execute(
            f"""
            UPDATE owned_item
            SET storage_slot_id = NULL, updated_at = ?
            WHERE storage_slot_id IN ({placeholders})
            """,
            (now, *slot_ids),
        )
        for row in item_rows:
            _log_owned_item_location_event_in_conn(
                conn,
                owned_item_id=int(row["id"]),
                from_storage_slot_id=int(row["storage_slot_id"]) if row["storage_slot_id"] is not None else None,
                to_storage_slot_id=None,
                movement_kind="CABINET_DELETE",
                note=cabinet,
                now=now,
            )
        cur = conn.execute(
            f"DELETE FROM storage_slot WHERE id IN ({placeholders})",
            slot_ids,
        )

    return {
        "cabinet_name": cabinet,
        "deleted_slot_count": int(cur.rowcount or 0),
        "unassigned_item_count": unassigned_item_count,
    }


def recommend_owned_item_location(
    size_group: str,
    artist_or_brand: str | None,
    release_year: int | None,
    item_title: str | None = None,
    exclude_owned_item_id: int | None = None,
) -> dict[str, Any]:
    size = str(size_group or "").strip().upper()
    if size not in SIZE_GROUP_CODES:
        return {
            "anchor_owned_item_id": None,
            "anchor_position": None,
            "recommended_storage_slot_id": None,
            "slot_code": None,
            "candidate_slots": [],
            "reason": "INVALID_SIZE_GROUP",
            "used_fallback_slot": False,
        }

    artist_norm = _normalize_recommendation_text(artist_or_brand)
    title_norm = _normalize_recommendation_text(item_title)
    try:
        year_value = int(release_year) if release_year is not None else None
    except (TypeError, ValueError):
        year_value = None
    exclude_id = int(exclude_owned_item_id or 0)

    anchor_row: sqlite3.Row | None = None
    anchor_position: str | None = None
    anchor_reason = "NO_ANCHOR"
    preferred_slot_id = 0
    recommended_slot_id: int | None = None
    recommended_slot_code: str | None = None
    slot_reason = "NO_SLOT"
    candidate_slots: list[dict[str, Any]] = []

    def _recommendation_sort_key(row: sqlite3.Row | dict[str, Any]) -> tuple[Any, ...]:
        raw_year = row["release_year"] if isinstance(row, sqlite3.Row) else row.get("release_year")
        try:
            row_year = int(raw_year) if raw_year is not None else None
        except (TypeError, ValueError):
            row_year = None
        row_title_norm = _normalize_recommendation_text(
            row["item_title"] if isinstance(row, sqlite3.Row) else row.get("item_title")
        )
        if _title_first_group_artist_key(artist_norm):
            return (
                row_title_norm,
                1 if row_year is None else 0,
                row_year if row_year is not None else 999999,
            )
        return (
            1 if row_year is None else 0,
            row_year if row_year is not None else 999999,
            row_title_norm,
        )

    with get_conn() as conn:
        _backfill_order_keys(conn)
        exclude_sql = " AND oi.id <> ? " if exclude_id > 0 else " "
        exclude_params = [exclude_id] if exclude_id > 0 else []

        artist_rows: list[sqlite3.Row] = []
        if artist_norm:
            artist_rows = conn.execute(
                f"""
                SELECT
                  oi.id,
                  oi.order_key,
                  oi.storage_slot_id,
                  ss.slot_code,
                  ss.cabinet_name,
                  ss.column_code,
                  ss.cell_code,
                  COALESCE(am.release_year, mid.release_year) AS release_year,
                  COALESCE(oi.item_name_override, am.title, '') AS item_title
                FROM owned_item oi
                JOIN music_item_detail mid ON mid.owned_item_id = oi.id
                LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
                JOIN storage_slot ss ON ss.id = oi.storage_slot_id
                WHERE oi.status = 'IN_COLLECTION'
                  AND oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
                  AND ss.allowed_size_group = ?
                  AND ss.cabinet_sort_policy = 'ARTIST_RELEASE_TITLE'
                  AND {_compact_search_sql_expr("COALESCE(am.sort_artist_name, oi.linked_artist_name, mid.artist_or_brand, am.artist_or_brand, '')")} = ?
                  {exclude_sql}
                """,
                [size, artist_norm, *exclude_params],
            ).fetchall()
            artist_rows = sorted(
                artist_rows,
                key=lambda row: (
                    *_recommendation_sort_key(row),
                    str(row["order_key"] or "").strip(),
                    int(row["id"] or 0),
                ),
            )

        candidate_slot_map: dict[int, dict[str, Any]] = {}
        for row in artist_rows:
            slot_id = int(row["storage_slot_id"] or 0)
            if slot_id <= 0 or slot_id in candidate_slot_map:
                continue
            slot_code = str(row["slot_code"] or "").strip()
            cabinet_name = str(row["cabinet_name"] or "").strip()
            column_code = str(row["column_code"] or "").strip()
            cell_code = str(row["cell_code"] or "").strip()
            display_name = " / ".join(
                [
                    value
                    for value in (
                        cabinet_name,
                        f"{column_code}층" if column_code else "",
                        f"{cell_code}칸" if cell_code else "",
                    )
                    if value
                ]
            ) or slot_code
            candidate_slot_map[slot_id] = {
                "storage_slot_id": slot_id,
                "slot_code": slot_code or None,
                "cabinet_name": cabinet_name or None,
                "column_code": column_code or None,
                "cell_code": cell_code or None,
                "display_name": display_name or None,
            }
        candidate_slots = list(candidate_slot_map.values())

        if artist_rows:
            if _title_first_group_artist_key(artist_norm):
                newer_row: sqlite3.Row | None = None
                for row in artist_rows:
                    row_title_norm = _normalize_recommendation_text(row["item_title"])
                    if bool(title_norm) and row_title_norm > title_norm:
                        newer_row = row
                        break
                if newer_row is not None:
                    anchor_row = newer_row
                    anchor_position = "BEFORE"
                    anchor_reason = "SAME_GROUP_TITLE"
                else:
                    anchor_row = artist_rows[-1]
                    anchor_position = "AFTER"
                    anchor_reason = "SAME_GROUP_TAIL"
            elif year_value is not None:
                newer_row = None
                for row in artist_rows:
                    raw_year = row["release_year"]
                    try:
                        row_year = int(raw_year) if raw_year is not None else None
                    except (TypeError, ValueError):
                        row_year = None
                    row_title_norm = _normalize_recommendation_text(row["item_title"])
                    is_newer_year = row_year is not None and row_year > year_value
                    is_same_year_later_title = (
                        row_year is not None
                        and row_year == year_value
                        and bool(title_norm)
                        and row_title_norm > title_norm
                    )
                    if is_newer_year or is_same_year_later_title:
                        newer_row = row
                        break
                if newer_row is not None:
                    anchor_row = newer_row
                    anchor_position = "BEFORE"
                    anchor_reason = "SAME_ARTIST_YEAR_TITLE"
                else:
                    anchor_row = artist_rows[-1]
                    anchor_position = "AFTER"
                    anchor_reason = "SAME_ARTIST_TAIL"
            else:
                anchor_row = artist_rows[-1]
                anchor_position = "AFTER"
                anchor_reason = "SAME_ARTIST_TAIL"

        if anchor_row is None:
            fallback_row = conn.execute(
                f"""
                SELECT oi.id, oi.order_key, oi.storage_slot_id
                FROM owned_item oi
                JOIN storage_slot ss ON ss.id = oi.storage_slot_id
                WHERE oi.status = 'IN_COLLECTION'
                  AND oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
                  AND ss.allowed_size_group = ?
                  AND ss.cabinet_sort_policy = 'ARTIST_RELEASE_TITLE'
                  {exclude_sql}
                ORDER BY oi.order_key DESC, oi.id DESC
                LIMIT 1
                """,
                [size, *exclude_params],
            ).fetchone()
            if fallback_row is not None:
                anchor_row = fallback_row
                anchor_position = "AFTER"
                anchor_reason = "FALLBACK_COLLECTION_TAIL"

        if anchor_row is not None and anchor_row["storage_slot_id"] is not None:
            try:
                preferred_slot_id = int(anchor_row["storage_slot_id"])
            except (TypeError, ValueError):
                preferred_slot_id = 0

        if preferred_slot_id > 0:
            slot_row = conn.execute(
                """
                SELECT id, slot_code
                FROM storage_slot
                WHERE id = ?
                  AND allowed_size_group = ?
                LIMIT 1
                """,
                (preferred_slot_id, size),
            ).fetchone()
            if slot_row is not None:
                recommended_slot_id = int(slot_row["id"])
                recommended_slot_code = str(slot_row["slot_code"] or "")
                slot_reason = "ANCHOR_SLOT"

        if recommended_slot_id is None and artist_norm:
            slot_row = conn.execute(
                f"""
                SELECT
                  ss.id,
                  ss.slot_code,
                  ss.is_overflow_zone,
                  COUNT(*) AS cnt
                FROM owned_item oi
                JOIN music_item_detail mid ON mid.owned_item_id = oi.id
                LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
                JOIN storage_slot ss ON ss.id = oi.storage_slot_id
                WHERE oi.status = 'IN_COLLECTION'
                  AND oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
                  AND ss.cabinet_sort_policy = 'ARTIST_RELEASE_TITLE'
                  AND {_compact_search_sql_expr("COALESCE(am.sort_artist_name, oi.linked_artist_name, mid.artist_or_brand, am.artist_or_brand, '')")} = ?
                  AND ss.allowed_size_group = ?
                  {exclude_sql}
                GROUP BY ss.id, ss.slot_code, ss.is_overflow_zone
                ORDER BY cnt DESC, ss.is_overflow_zone ASC, ss.id ASC
                LIMIT 1
                """,
                [artist_norm, size, *exclude_params],
            ).fetchone()
            if slot_row is not None:
                recommended_slot_id = int(slot_row["id"])
                recommended_slot_code = str(slot_row["slot_code"] or "")
                slot_reason = "ARTIST_SLOT"

        if recommended_slot_id is None:
            slot_row = conn.execute(
                """
                SELECT
                  ss.id,
                  ss.slot_code,
                  ss.is_overflow_zone,
                  COUNT(oi.id) AS usage_count
                FROM storage_slot ss
                LEFT JOIN owned_item oi
                  ON oi.storage_slot_id = ss.id
                 AND oi.status = 'IN_COLLECTION'
                WHERE ss.allowed_size_group = ?
                  AND ss.cabinet_sort_policy = 'ARTIST_RELEASE_TITLE'
                GROUP BY ss.id, ss.slot_code, ss.is_overflow_zone
                ORDER BY ss.is_overflow_zone ASC, usage_count ASC, ss.id ASC
                LIMIT 1
                """,
                (size,),
            ).fetchone()
            if slot_row is not None:
                recommended_slot_id = int(slot_row["id"])
                recommended_slot_code = str(slot_row["slot_code"] or "")
                slot_reason = "LEAST_OCCUPIED_SLOT"

    used_fallback_slot = slot_reason in {"ARTIST_SLOT", "LEAST_OCCUPIED_SLOT"}
    if slot_reason == "ANCHOR_SLOT":
        used_fallback_slot = False
    if recommended_slot_id is None:
        used_fallback_slot = False

    return {
        "anchor_owned_item_id": int(anchor_row["id"]) if anchor_row is not None else None,
        "anchor_position": anchor_position,
        "recommended_storage_slot_id": recommended_slot_id,
        "slot_code": recommended_slot_code,
        "candidate_slots": candidate_slots,
        "reason": f"{anchor_reason}/{slot_reason}",
        "used_fallback_slot": used_fallback_slot,
    }


def list_classification_options(option_group: str, include_inactive: bool = False) -> list[dict[str, Any]]:
    query = """
      SELECT id, option_group, label, sort_order, is_active
      FROM classification_option
      WHERE option_group = ?
    """
    params: list[Any] = [option_group]
    if not include_inactive:
        query += " AND is_active = 1"
    query += " ORDER BY sort_order ASC, label ASC, id ASC"

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def upsert_classification_option(option_group: str, label: str, sort_order: int = 100) -> dict[str, Any]:
    now = utc_now_iso()
    clean_label = str(label or "").strip()
    if not clean_label:
        raise ValueError("label is required")

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO classification_option
              (option_group, label, sort_order, is_active, created_at, updated_at)
            VALUES (?, ?, ?, 1, ?, ?)
            ON CONFLICT(option_group, label) DO UPDATE SET
              sort_order = excluded.sort_order,
              is_active = 1,
              updated_at = excluded.updated_at
            """,
            (option_group, clean_label, int(sort_order), now, now),
        )
        row = conn.execute(
            """
            SELECT id, option_group, label, sort_order, is_active
            FROM classification_option
            WHERE option_group = ? AND label = ?
            LIMIT 1
            """,
            (option_group, clean_label),
        ).fetchone()
    if row is None:
        raise RuntimeError("classification option upsert failed")
    return dict(row)


def update_owned_item_slot(owned_item_id: int, storage_slot_id: int | None, movement_note: str | None = None) -> None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT storage_slot_id FROM owned_item WHERE id = ? LIMIT 1",
            (owned_item_id,),
        ).fetchone()
        previous_storage_slot_id = row["storage_slot_id"] if row is not None else None
        now = utc_now_iso()
        conn.execute(
            """
            UPDATE owned_item
            SET storage_slot_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (storage_slot_id, now, owned_item_id),
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


def insert_digital_link(owned_item_id: int, payload: dict[str, Any]) -> dict[str, int]:
    now = utc_now_iso()
    with get_conn() as conn:
        asset_cur = conn.execute(
            """
            INSERT INTO digital_asset
              (asset_type, file_path, file_hash, file_size_bytes, duration_sec, metadata_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["asset_type"],
                payload["file_path"],
                payload.get("file_hash"),
                payload.get("file_size_bytes"),
                payload.get("duration_sec"),
                json.dumps(payload.get("metadata_json", {}), ensure_ascii=True),
                now,
                now,
            ),
        )
        asset_id = int(asset_cur.lastrowid)

        link_cur = conn.execute(
            """
            INSERT INTO owned_item_digital_link
              (owned_item_id, digital_asset_id, link_type, track_no, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                owned_item_id,
                asset_id,
                payload["link_type"],
                payload.get("track_no"),
                payload.get("note"),
                now,
            ),
        )
        link_id = int(link_cur.lastrowid)

    return {"digital_asset_id": asset_id, "link_id": link_id}
