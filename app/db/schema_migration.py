"""스키마 마이그레이션 도메인 (schema_migration).

db/__init__.py 에서 분리된 슬라이스. SQLite DB 버전 관리 및
레거시 idempotent 마이그레이션 패스를 소유한다.

공개 surface (app.db re-export)
  SCHEMA_VERSION               — 현재 DB 스키마 버전 번호
  _read_user_version(conn)     — PRAGMA user_version 읽기
  _apply_migrations(conn)      — ensure_startup_db_ready / init_db 진입점

내부 함수
  _set_user_version, _run_pending_migrations, _apply_migrations_legacy
  _migration_v1~v3, _migrate_album_master_*, _ensure_album_master_*
  _backfill_album_master_*, _music_item_detail_*, _migrate_owned_item_*

변경격리: startup cleanup은 startup_cleanup/ 패키지에서 담당한다.
테스트 단위: test_schema_migration.py 에서 독립 검증.

Cross-package dependencies
  app.db surface (always available at import time):
    _column_exists, _table_exists, utc_now_iso
    _domain_code_check_sql, _size_group_check_sql,
    _cabinet_sort_policy_check_sql, _normalize_domain_code_sql
    _ensure_app_setting_table, _ensure_recent_feed_indexes

  app.db surface (available after sub-module re-exports — this module is
  imported at the BOTTOM of db/__init__.py, after purchase_import/
  storage_slot/order_keys/goods_item are already re-exported):
    _ensure_purchase_import_queue_table
    _migrate_purchase_import_queue_allow_file_upload
    _migrate_storage_slot_allow_goods, _derive_storage_slot_parts
    _backfill_order_keys
    _goods_category_check_sql, _goods_status_check_sql, _goods_relation_type_check_sql
"""

from __future__ import annotations

import sqlite3
from typing import Callable

from app.db._schema_helpers import _column_exists, _table_exists
from app.db.connection import utc_now_iso
from app.db import (  # noqa: E402 — package surface (always bound)
    _cabinet_sort_policy_check_sql,
    _domain_code_check_sql,
    _ensure_app_setting_table,
    _ensure_recent_feed_indexes,
    _normalize_domain_code_sql,
    _size_group_check_sql,
)
from app.db import (  # noqa: E402 — sub-module surface (bound after re-exports)
    _backfill_order_keys,
    _derive_storage_slot_parts,
    _ensure_purchase_import_queue_table,
    _goods_category_check_sql,
    _goods_relation_type_check_sql,
    _goods_status_check_sql,
    _migrate_purchase_import_queue_allow_file_upload,
    _migrate_storage_slot_allow_goods,
)

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


SCHEMA_VERSION = 14
"""Bump every time a NEW migration entry is added to `_MIGRATIONS_BY_VERSION`.

The legacy idempotent pass (`_apply_migrations`) is collapsed into version 1.
Future schema changes should be added as new functions, registered in the
dictionary below, and assigned the next integer.

Version log:
  1 — legacy idempotent pass (pre-versioning installs converge here).
  2 — `external_response_cache` table for persisted Discogs/MusicBrainz/
      Aladin/CoverArtArchive replies. See providers.cached_fetch_json.
  3 — `goods_item.linked_owned_item_id` nullable FK → owned_item.
      Links a collectible (goods_item) to a specific owned product (owned_item)
      for the 상품 연계 수집품 (2-3) feature.
  4 — `music_item_detail.disc_type` TEXT column. Was added to
      _apply_migrations_legacy after DBs already passed v1, so it was never
      applied to existing installs. Fixes INSERT 500 error on owned-item create.
  5 — `album_master.override_title` and `album_master.override_artist_or_brand`
      TEXT columns. Supports the unified correction editor that lets operators
      override title and artist/brand alongside release_year / domain_code.
  6 — `music_item_detail.package_contents` TEXT, `is_limited_edition` INTEGER,
      `edition_number` TEXT columns. Supports 패키지 구성 checkboxes,
      한정판 checkbox and 넘버링 field in the owned-item edit form.
  7 — `music_item_detail.format_name` CHECK 제약 제거 (테이블 재생성).
      Pydantic 스키마를 str | None 으로 완화했으나 SQLite 레벨 CHECK 가
      남아 있어 Vinyl 등 자유 형식 값 저장 시 500 에러 발생.
  8 — `customer_track_request` weather columns (weather_temp_c, weather_description,
      weather_code, season) and playback columns (playback_deck, played_at, returned_at).
  9 — spotify album fields (spotify_album_id, spotify_album_uri, spotify_matched_at, spotify_image_url) in album_master.
  10 — table_device and track_reaction tables for cafe operations.
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


def _migration_v3_add_goods_item_owned_link(conn: sqlite3.Connection) -> None:
    """Add linked_owned_item_id to goods_item.

    Enables the 상품 연계 수집품 (2-3) feature: a collectible registered in the
    수집품 tab can be associated with a specific owned product (owned_item).
    The FK is SET NULL on delete so removing the owned item doesn't cascade
    to the collectible itself.
    """
    if _table_exists(conn, "goods_item"):
        if not _column_exists(conn, "goods_item", "linked_owned_item_id"):
            conn.execute(
                "ALTER TABLE goods_item ADD COLUMN linked_owned_item_id INTEGER "
                "REFERENCES owned_item(id) ON DELETE SET NULL"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_goods_item_linked_owned "
                "ON goods_item (linked_owned_item_id) WHERE linked_owned_item_id IS NOT NULL"
            )


def _migration_v5_add_album_master_override_title_artist(conn: sqlite3.Connection) -> None:
    """`album_master.override_title` and `album_master.override_artist_or_brand` TEXT columns.

    Supports the unified correction editor (운영자 수동 보정 통합 패널) that lets
    operators override the displayed title and artist/brand alongside the existing
    override_release_year / override_domain_code / override_note fields.
    When set, the effective `title` and `artist_or_brand` columns are also updated
    via COALESCE so the main catalog reflects the correction immediately.
    """
    if _table_exists(conn, "album_master"):
        if not _column_exists(conn, "album_master", "override_title"):
            conn.execute("ALTER TABLE album_master ADD COLUMN override_title TEXT")
        if not _column_exists(conn, "album_master", "override_artist_or_brand"):
            conn.execute("ALTER TABLE album_master ADD COLUMN override_artist_or_brand TEXT")


def _migration_v4_add_disc_type(conn: sqlite3.Connection) -> None:
    """`music_item_detail.disc_type` TEXT column.

    This was added inside `_apply_migrations_legacy` (the v1 idempotent pass)
    after production DBs had already been bumped to user_version >= 1, so the
    ALTER was silently skipped on every boot. Any attempt to INSERT or UPDATE
    a music_item_detail row raised:
        sqlite3.OperationalError: table music_item_detail has no column named disc_type
    causing a 500 on 직접등록 and 구매 내역 owned-item creation.
    """
    if _table_exists(conn, "music_item_detail") and not _column_exists(
        conn, "music_item_detail", "disc_type"
    ):
        conn.execute("ALTER TABLE music_item_detail ADD COLUMN disc_type TEXT")


def _migration_v7_drop_format_name_check(conn: sqlite3.Connection) -> None:
    """`music_item_detail.format_name` CHECK 제약 제거 (테이블 재생성).

    SQLite는 ALTER TABLE DROP CONSTRAINT 를 지원하지 않으므로
    동일 스키마에서 CHECK 만 제거한 새 테이블로 데이터를 이전한다.
    v4(disc_type), v6(package_contents, is_limited_edition, edition_number)
    컬럼도 포함해 재생성한다.
    """
    if not _table_exists(conn, "music_item_detail"):
        return
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='music_item_detail'"
    ).fetchone()
    if row is None:
        return
    # CHECK 제약이 이미 없으면 스킵
    if "CHECK" not in str(row[0] or "").upper():
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
              owned_item_id       INTEGER PRIMARY KEY,
              format_name         TEXT,
              is_promotional_not_for_sale INTEGER NOT NULL DEFAULT 0,
              artist_or_brand     TEXT,
              release_year        INTEGER,
              released_date       TEXT,
              barcode             TEXT,
              label_name          TEXT,
              catalog_no          TEXT,
              cover_image_url     TEXT,
              track_list_json     TEXT,
              media_type          TEXT,
              genres_json         TEXT,
              styles_json         TEXT,
              media_condition     TEXT,
              sleeve_condition    TEXT,
              disc_count          INTEGER,
              speed_rpm           INTEGER,
              has_obi             INTEGER,
              runout_matrix       TEXT,
              runout_matrix_json  TEXT,
              pressing_country    TEXT,
              source_notes        TEXT,
              credits_json        TEXT,
              identifier_items_json TEXT,
              image_items_json    TEXT,
              company_items_json  TEXT,
              series_json         TEXT,
              format_items_json   TEXT,
              track_items_json    TEXT,
              label_items_json    TEXT,
              created_at          TEXT NOT NULL,
              updated_at          TEXT NOT NULL,
              disc_type           TEXT,
              package_contents    TEXT,
              is_limited_edition  INTEGER,
              edition_number      TEXT,
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
              label_items_json, created_at, updated_at,
              disc_type, package_contents, is_limited_edition, edition_number
            )
            SELECT
              owned_item_id, format_name, is_promotional_not_for_sale,
              artist_or_brand, release_year, released_date, barcode,
              label_name, catalog_no, cover_image_url, track_list_json,
              media_type, genres_json, styles_json,
              media_condition, sleeve_condition, disc_count, speed_rpm,
              has_obi, runout_matrix, runout_matrix_json, pressing_country,
              source_notes, credits_json, identifier_items_json, image_items_json,
              company_items_json, series_json, format_items_json, track_items_json,
              label_items_json, created_at, updated_at,
              disc_type, package_contents, is_limited_edition, edition_number
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


def _migration_v6_add_package_contents_limited_edition(conn: sqlite3.Connection) -> None:
    """`music_item_detail` columns for 패키지 구성, 한정판, 넘버링.

    package_contents   — comma-joined list of included items (부클릿, 포토카드, …)
    is_limited_edition — 0/1 flag for 한정판 여부
    edition_number     — free-text numbering e.g. "5/1000"
    """
    if not _table_exists(conn, "music_item_detail"):
        return
    if not _column_exists(conn, "music_item_detail", "package_contents"):
        conn.execute("ALTER TABLE music_item_detail ADD COLUMN package_contents TEXT")
    if not _column_exists(conn, "music_item_detail", "is_limited_edition"):
        conn.execute("ALTER TABLE music_item_detail ADD COLUMN is_limited_edition INTEGER")
    if not _column_exists(conn, "music_item_detail", "edition_number"):
        conn.execute("ALTER TABLE music_item_detail ADD COLUMN edition_number TEXT")


def _migration_v8_add_customer_track_weather_and_decks(conn: sqlite3.Connection) -> None:
    """`customer_track_request` weather columns (weather_temp_c, weather_description,
    weather_code, season) and playback columns (playback_deck, played_at, returned_at).
    """
    if not _table_exists(conn, "customer_track_request"):
        return
    if not _column_exists(conn, "customer_track_request", "weather_temp_c"):
        conn.execute("ALTER TABLE customer_track_request ADD COLUMN weather_temp_c REAL")
    if not _column_exists(conn, "customer_track_request", "weather_description"):
        conn.execute("ALTER TABLE customer_track_request ADD COLUMN weather_description TEXT")
    if not _column_exists(conn, "customer_track_request", "weather_code"):
        conn.execute("ALTER TABLE customer_track_request ADD COLUMN weather_code INTEGER")
    if not _column_exists(conn, "customer_track_request", "season"):
        conn.execute("ALTER TABLE customer_track_request ADD COLUMN season TEXT")
    if not _column_exists(conn, "customer_track_request", "playback_deck"):
        conn.execute("ALTER TABLE customer_track_request ADD COLUMN playback_deck TEXT")
    if not _column_exists(conn, "customer_track_request", "played_at"):
        conn.execute("ALTER TABLE customer_track_request ADD COLUMN played_at TEXT")
    if not _column_exists(conn, "customer_track_request", "returned_at"):
        conn.execute("ALTER TABLE customer_track_request ADD COLUMN returned_at TEXT")


def _migration_v9_add_spotify_album_fields(conn: sqlite3.Connection) -> None:
    """Add spotify_album_id, spotify_album_uri, spotify_matched_at, and spotify_image_url to album_master."""
    if not _table_exists(conn, "album_master"):
        return
    if not _column_exists(conn, "album_master", "spotify_album_id"):
        conn.execute("ALTER TABLE album_master ADD COLUMN spotify_album_id TEXT")
    if not _column_exists(conn, "album_master", "spotify_album_uri"):
        conn.execute("ALTER TABLE album_master ADD COLUMN spotify_album_uri TEXT")
    if not _column_exists(conn, "album_master", "spotify_matched_at"):
        conn.execute("ALTER TABLE album_master ADD COLUMN spotify_matched_at TEXT")
    if not _column_exists(conn, "album_master", "spotify_image_url"):
        conn.execute("ALTER TABLE album_master ADD COLUMN spotify_image_url TEXT")


def _migration_v10_add_cafe_tablet_and_reaction_tables(conn: sqlite3.Connection) -> None:
    """Create table_device and track_reaction tables for cafe operations."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS table_device (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          table_number TEXT NOT NULL UNIQUE,
          device_label TEXT,
          device_id TEXT UNIQUE,
          is_active INTEGER NOT NULL DEFAULT 1,
          notes TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS track_reaction (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          track_request_id INTEGER NOT NULL,
          table_number TEXT NOT NULL,
          reaction_type TEXT NOT NULL,
          free_text TEXT,
          created_at TEXT NOT NULL,
          FOREIGN KEY (track_request_id) REFERENCES customer_track_request(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_track_reaction_request ON track_reaction (track_request_id)"
    )


def _migration_v11_add_local_image_items_json(conn: sqlite3.Connection) -> None:
    """Add local_image_items_json column to music_item_detail if it does not exist."""
    if _table_exists(conn, "music_item_detail") and not _column_exists(
        conn, "music_item_detail", "local_image_items_json"
    ):
        conn.execute("ALTER TABLE music_item_detail ADD COLUMN local_image_items_json TEXT")


def _migration_v12_add_album_master_review_fields(conn: sqlite3.Connection) -> None:
    """Add review_text, review_source, review_url to album_master if they do not exist."""
    if not _table_exists(conn, "album_master"):
        return
    if not _column_exists(conn, "album_master", "review_text"):
        conn.execute("ALTER TABLE album_master ADD COLUMN review_text TEXT")
    if not _column_exists(conn, "album_master", "review_source"):
        conn.execute("ALTER TABLE album_master ADD COLUMN review_source TEXT")
    if not _column_exists(conn, "album_master", "review_url"):
        conn.execute("ALTER TABLE album_master ADD COLUMN review_url TEXT")


def _migration_v14_add_label_domain_registry(conn: sqlite3.Connection) -> None:
    """Create label_domain_registry table and seed from confirmed masters."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS label_domain_registry (
          label_name_key TEXT PRIMARY KEY,
          label_name     TEXT NOT NULL,
          domain_code    TEXT NOT NULL,
          confirmed_count INTEGER NOT NULL DEFAULT 1,
          created_at     TEXT NOT NULL,
          updated_at     TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_label_domain_registry_domain
        ON label_domain_registry (domain_code)
    """)
    # Seed from masters that already have a confirmed override_domain_code
    conn.execute("""
        INSERT OR IGNORE INTO label_domain_registry
          (label_name_key, label_name, domain_code, confirmed_count, created_at, updated_at)
        SELECT
          LOWER(TRIM(mid.label_name)),
          mid.label_name,
          am.override_domain_code,
          COUNT(*),
          datetime('now'),
          datetime('now')
        FROM album_master am
        JOIN owned_item oi ON oi.linked_album_master_id = am.id
        JOIN music_item_detail mid ON mid.owned_item_id = oi.id
        WHERE am.override_domain_code IS NOT NULL
          AND mid.label_name IS NOT NULL
          AND TRIM(mid.label_name) != ''
        GROUP BY LOWER(TRIM(mid.label_name)), am.override_domain_code
    """)


def _migration_v13_add_album_master_genres_styles(conn: sqlite3.Connection) -> None:
    """Add genres_json and styles_json columns to album_master, then backfill from
    the best (lowest order_key) music_item_detail record linked to each master."""
    if not _table_exists(conn, "album_master"):
        return
    if not _column_exists(conn, "album_master", "genres_json"):
        conn.execute("ALTER TABLE album_master ADD COLUMN genres_json TEXT")
    if not _column_exists(conn, "album_master", "styles_json"):
        conn.execute("ALTER TABLE album_master ADD COLUMN styles_json TEXT")
    # Backfill from best music_item_detail per master
    conn.execute("""
        UPDATE album_master
        SET
          genres_json = (
            SELECT mid.genres_json
            FROM album_master_member amm
            JOIN owned_item oi ON oi.id = amm.owned_item_id
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            WHERE amm.album_master_id = album_master.id
              AND mid.genres_json IS NOT NULL
              AND mid.genres_json <> '[]'
              AND TRIM(mid.genres_json) <> ''
            ORDER BY
              CASE WHEN oi.order_key IS NULL OR TRIM(oi.order_key) = '' THEN 1 ELSE 0 END,
              oi.order_key ASC, oi.id ASC
            LIMIT 1
          ),
          styles_json = (
            SELECT mid.styles_json
            FROM album_master_member amm
            JOIN owned_item oi ON oi.id = amm.owned_item_id
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            WHERE amm.album_master_id = album_master.id
              AND mid.styles_json IS NOT NULL
              AND mid.styles_json <> '[]'
              AND TRIM(mid.styles_json) <> ''
            ORDER BY
              CASE WHEN oi.order_key IS NULL OR TRIM(oi.order_key) = '' THEN 1 ELSE 0 END,
              oi.order_key ASC, oi.id ASC
            LIMIT 1
          )
        WHERE genres_json IS NULL OR styles_json IS NULL
    """)


_MIGRATIONS_BY_VERSION: dict[int, "Callable[[sqlite3.Connection], None]"] = {
    1: _migration_v1_legacy_idempotent_pass,
    2: _migration_v2_add_external_response_cache,
    3: _migration_v3_add_goods_item_owned_link,
    4: _migration_v4_add_disc_type,
    5: _migration_v5_add_album_master_override_title_artist,
    6: _migration_v6_add_package_contents_limited_edition,
    7: _migration_v7_drop_format_name_check,
    8: _migration_v8_add_customer_track_weather_and_decks,
    9: _migration_v9_add_spotify_album_fields,
    10: _migration_v10_add_cafe_tablet_and_reaction_tables,
    11: _migration_v11_add_local_image_items_json,
    12: _migration_v12_add_album_master_review_fields,
    13: _migration_v13_add_album_master_genres_styles,
    14: _migration_v14_add_label_domain_registry,
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
        if not _column_exists(conn, "album_master", "spotify_album_id"):
            conn.execute("ALTER TABLE album_master ADD COLUMN spotify_album_id TEXT")
        if not _column_exists(conn, "album_master", "spotify_album_uri"):
            conn.execute("ALTER TABLE album_master ADD COLUMN spotify_album_uri TEXT")
        if not _column_exists(conn, "album_master", "spotify_matched_at"):
            conn.execute("ALTER TABLE album_master ADD COLUMN spotify_matched_at TEXT")
        if not _column_exists(conn, "album_master", "spotify_image_url"):
            conn.execute("ALTER TABLE album_master ADD COLUMN spotify_image_url TEXT")
        
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
           OR UPPER(TRIM(cabinet_sort_policy)) NOT IN ('ARTIST_RELEASE_TITLE', 'LABEL_ID', 'TITLE_RELEASE')
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
    if not _column_exists(conn, "music_item_detail", "disc_type"):
        conn.execute("ALTER TABLE music_item_detail ADD COLUMN disc_type TEXT")
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
