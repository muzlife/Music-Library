"""도메인 코드 교정 startup cleanup 도메인.

ensure_startup_db_ready / init_db 가 호출하는 domain_code 관련
멱등(idempotent) 교정 함수들을 소유한다.

책임 범위
  _sync_album_master_domain_from_owned_items  — owned_item 다수결로 album_master 동기화
  _fix_maniadb_domain_corrections             — ManiaDB 소스 앨범의 KOREA 복원
  _fix_hangul_artist_domain_corrections       — 한글 item_name_override 신호로 KOREA 교정
  _fix_known_domain_corrections               — 수동 확인된 특정 레코드 일괄 교정

변경격리: 아티스트명 관련 교정은 artist_name.py 에서 담당한다.
테스트 단위: test_startup_cleanup_domain_code.py 에서 독립 검증.

Cross-package dependencies (app.db 패키지 surface 경유)
  _column_exists, _table_exists, utc_now_iso
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3

from app.db._schema_helpers import _column_exists, _table_exists
from app.db.connection import utc_now_iso

_HANGUL_RE = re.compile(r"[가-힣ㄱ-ㆎ]")
_KANA_RE = re.compile(r"[぀-ヿㇰ-ㇿ]")
_log = logging.getLogger(__name__)


def _sync_album_master_domain_from_owned_items(conn: sqlite3.Connection) -> None:
    """Deprecated: domain is now managed at album_master level directly."""
    return  # no-op


def _fix_maniadb_domain_corrections(conn: sqlite3.Connection) -> None:
    """ManiaDB 소스 앨범의 domain_code를 KOREA로 교정한다. (멱등 실행 안전)

    ManiaDB는 한국 음악 전용 데이터베이스이므로, ManiaDB 소스를 가진 모든
    album_master의 domain_code는 KOREA여야 한다.

    _sync_album_master_domain_from_owned_items 함수가 라틴 아티스트명을 가진
    ManiaDB 앨범(예: Double K, EP)을 WESTERN으로 잘못 분류하는 버그를 복원한다.

    override_domain_code가 명시된 레코드는 건드리지 않는다.
    """
    if not _column_exists(conn, "album_master", "domain_code"):
        return
    if not _column_exists(conn, "album_master", "source_code"):
        return

    now = utc_now_iso()

    # album_master: MANIADB 소스인데 KOREA가 아닌 것 → KOREA로 복원
    conn.execute(
        """
        UPDATE album_master
        SET domain_code = 'KOREA',
            source_domain_code = 'KOREA',
            updated_at = ?
        WHERE source_code = 'MANIADB'
          AND COALESCE(TRIM(domain_code), '') != 'KOREA'
          AND (override_domain_code IS NULL OR TRIM(override_domain_code) = '')
        """,
        (now,),
    )

    # owned_item: MANIADB 앨범에 연결됐는데 domain이 KOREA가 아닌 것 → 동기화
    if _column_exists(conn, "owned_item", "domain_code") and _column_exists(
        conn, "owned_item", "linked_album_master_id"
    ):
        conn.execute(
            """
            UPDATE owned_item
            SET domain_code = 'KOREA',
                updated_at = ?
            WHERE linked_album_master_id IN (
                SELECT id FROM album_master WHERE source_code = 'MANIADB'
            )
              AND COALESCE(TRIM(domain_code), '') != 'KOREA'
            """,
            (now,),
        )

    conn.commit()


def _fix_hangul_artist_domain_corrections(conn: sqlite3.Connection) -> None:
    """한글이 포함된 item_name_override를 가진 owned_item에 연결된 album_master의
    domain_code를 KOREA로 교정한다. (멱등 실행 안전)

    Discogs/MANUAL 소스로 등록된 album_master는 아티스트명이 로마자(예: "Seo Taiji",
    "Park Hyo Shin", "Hyukoh")로 기록되어 WESTERN으로 오분류되는 경우가 있다.

    owned_item.item_name_override("강산에 - Kiss", "서태지 - ..." 등)에 한글이
    포함된 경우를 한국 아티스트의 신호로 사용한다.
    override_domain_code가 명시된 레코드는 건드리지 않는다.
    """
    if not _table_exists(conn, "album_master"):
        return
    if not _table_exists(conn, "owned_item"):
        return
    if not _column_exists(conn, "album_master", "domain_code"):
        return
    if not _column_exists(conn, "album_master", "override_domain_code"):
        return
    if not _column_exists(conn, "album_master", "source_domain_code"):
        return
    if not _column_exists(conn, "owned_item", "linked_album_master_id"):
        return
    if not _column_exists(conn, "owned_item", "item_name_override"):
        return

    try:
        # non-KOREA, override 없는 album_master + linked owned_item의 item_name_override 조회
        rows = conn.execute(
            """
            SELECT am.id, oi.item_name_override AS oi_name
            FROM album_master am
            JOIN owned_item oi ON oi.linked_album_master_id = am.id
            WHERE COALESCE(TRIM(am.domain_code), '') != 'KOREA'
              AND (am.override_domain_code IS NULL OR TRIM(am.override_domain_code) = '')
              AND oi.item_name_override IS NOT NULL
              AND TRIM(oi.item_name_override) != ''
            """
        ).fetchall()

        # 한글 포함 item_name_override를 가진 album_master id 수집
        hangul_am_ids: set[int] = set()
        for row in rows:
            if _HANGUL_RE.search(str(row["oi_name"] or "")):
                hangul_am_ids.add(row["id"])

        if not hangul_am_ids:
            return

        now = utc_now_iso()
        for am_id in hangul_am_ids:
            conn.execute(
                """
                UPDATE album_master
                SET domain_code = 'KOREA',
                    source_domain_code = CASE
                        WHEN source_domain_code IS NULL OR TRIM(source_domain_code) = ''
                        THEN 'KOREA'
                        ELSE source_domain_code
                    END,
                    updated_at = ?
                WHERE id = ?
                  AND COALESCE(TRIM(domain_code), '') != 'KOREA'
                  AND (override_domain_code IS NULL OR TRIM(override_domain_code) = '')
                """,
                (now, am_id),
            )

        conn.commit()

    except Exception as exc:  # noqa: BLE001
        _log.warning(
            "_fix_hangul_artist_domain_corrections skipped due to error: %s", exc
        )


def _fix_known_domain_corrections(conn: sqlite3.Connection) -> None:
    """수동 확인된 도메인/아티스트명 오류를 일괄 교정한다. (멱등 실행 안전)

    케이스별 근거:
      am.id=949  이하이    — WORLD_OTHER 오분류 → KOREA
                            (국내 K-pop 가수, 해외활동 없음)
      am.id=1036 나윤선    — GREATER_CHINA → WORLD_OTHER,
                            artist_or_brand → 'Youn Sun Nah' (Discogs 국제명),
                            sort_artist_name='나윤선' 유지 (국내 정렬 기준)
      am.id=1053 나윤선    — GREATER_CHINA → WORLD_OTHER (홍콩반이지만 한국 아티스트),
                            artist_or_brand → 'Youn Sun Nah',
                            sort_artist_name='나윤선' 유지
      oi.id=578  김창완   — owned_item.domain_code GREATER_CHINA → KOREA
      oi.id=815  변진섭   — owned_item.domain_code GREATER_CHINA → KOREA
      oi.id=835  김완선   — owned_item.domain_code GREATER_CHINA → KOREA
    """
    if not _table_exists(conn, "album_master"):
        return

    now = utc_now_iso()

    # ── am.id=949 이하이: WORLD_OTHER → KOREA ──────────────────────────────
    conn.execute(
        """UPDATE album_master
              SET domain_code = 'KOREA',
                  source_domain_code = CASE
                      WHEN source_domain_code = 'WORLD_OTHER' THEN 'KOREA'
                      ELSE source_domain_code
                  END,
                  updated_at = ?
            WHERE id = 949
              AND domain_code = 'WORLD_OTHER'""",
        (now,),
    )

    # ── am.id=1036 나윤선: artist → Youn Sun Nah, sort 유지 ───────────────
    conn.execute(
        """UPDATE album_master
              SET artist_or_brand = 'Youn Sun Nah',
                  sort_artist_name = COALESCE(
                      NULLIF(TRIM(sort_artist_name), ''),
                      '나윤선'
                  ),
                  updated_at = ?
            WHERE id = 1036
              AND artist_or_brand = '나윤선'""",
        (now,),
    )
    # sort가 이미 NULL 된 경우도 복원
    conn.execute(
        """UPDATE album_master
              SET sort_artist_name = '나윤선', updated_at = ?
            WHERE id = 1036
              AND artist_or_brand = 'Youn Sun Nah'
              AND (sort_artist_name IS NULL OR TRIM(sort_artist_name) = '')""",
        (now,),
    )

    # ── am.id=1053 나윤선: GREATER_CHINA → WORLD_OTHER, artist 교정 ───────
    conn.execute(
        """UPDATE album_master
              SET artist_or_brand = 'Youn Sun Nah',
                  sort_artist_name = COALESCE(
                      NULLIF(TRIM(sort_artist_name), ''),
                      '나윤선'
                  ),
                  domain_code = 'WORLD_OTHER',
                  source_domain_code = CASE
                      WHEN source_domain_code = 'GREATER_CHINA' THEN 'WORLD_OTHER'
                      ELSE source_domain_code
                  END,
                  updated_at = ?
            WHERE id = 1053
              AND domain_code = 'GREATER_CHINA'""",
        (now,),
    )
    # sort가 이미 NULL 된 경우도 복원
    conn.execute(
        """UPDATE album_master
              SET sort_artist_name = '나윤선', updated_at = ?
            WHERE id = 1053
              AND artist_or_brand = 'Youn Sun Nah'
              AND (sort_artist_name IS NULL OR TRIM(sort_artist_name) = '')""",
        (now,),
    )

    # ── ext_ref hint 업데이트 (나윤선 양쪽) ───────────────────────────────
    conn.execute(
        """UPDATE album_master_external_ref
              SET artist_or_brand_hint = 'Youn Sun Nah', updated_at = ?
            WHERE album_master_id IN (1036, 1053)
              AND source_code = 'DISCOGS'
              AND artist_or_brand_hint = '나윤선'""",
        (now,),
    )

    # ── owned_item: 나윤선 linked_artist_name 교정 ────────────────────────
    conn.execute(
        """UPDATE owned_item
              SET linked_artist_name = 'Youn Sun Nah', updated_at = ?
            WHERE linked_album_master_id IN (1036, 1053)
              AND linked_artist_name = '나윤선'""",
        (now,),
    )

    # ── oi.id=578,815,835 한국 아티스트 GREATER_CHINA → KOREA ─────────────
    if _table_exists(conn, "owned_item"):
        conn.execute(
            """UPDATE owned_item
                  SET domain_code = 'KOREA', updated_at = ?
                WHERE id IN (578, 815, 835)
                  AND domain_code = 'GREATER_CHINA'""",
            (now,),
        )

    conn.commit()
