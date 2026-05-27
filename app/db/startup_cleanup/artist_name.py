"""아티스트명 교정 startup cleanup 도메인.

ensure_startup_db_ready / init_db 가 호출하는 아티스트명/정렬명 관련
멱등(idempotent) 교정 함수들을 소유한다.

책임 범위
  _cleanup_pop_korean_sort_names          — 팝 앨범의 잘못된 한글 sort_artist_name 제거
  _restore_latin_artist_names_from_ext_ref — ext_ref hint로 한글→영문 아티스트명 복원
  _cleanup_pop_hangul_artist_names         — 비가요 앨범의 한글 아티스트명을 영문으로 복원
                                             (raw_json 원본 또는 hint 우선순위)

변경격리: domain_code 값 교정은 domain_code.py 에서 담당한다.
테스트 단위: test_startup_cleanup_artist_name.py 에서 독립 검증.

Cross-package dependencies (app.db 패키지 surface 경유)
  _column_exists, _table_exists, utc_now_iso
"""

from __future__ import annotations

import re
import sqlite3

from app.db._schema_helpers import _column_exists, _table_exists
from app.db.connection import utc_now_iso

_HANGUL_RE = re.compile(r"[가-힣ㄱ-ㆎ]")


def _cleanup_pop_korean_sort_names(conn: sqlite3.Connection) -> None:
    """팝(가요 외) 앨범에 잘못 적용된 한글 정렬명을 제거한다.

    `infer_domain_code` 버그로 인해 팝 국내발매(라이선스)반의 domain_code 가
    'KOREA'로 잘못 지정된 경우, 아티스트 현지화 로직이 외국 아티스트에게도
    한글 sort_artist_name을 부여할 수 있다.
    이 함수는 domain_code가 'KOREA'가 아닌데 sort_artist_name에 한글이 있는
    레코드를 찾아 sort_artist_name을 NULL로 리셋한다.
    """
    if not _column_exists(conn, "album_master", "sort_artist_name"):
        return
    if not _column_exists(conn, "album_master", "domain_code"):
        return

    rows = conn.execute(
        """
        SELECT id, sort_artist_name
        FROM album_master
        WHERE domain_code IS NOT NULL
          AND TRIM(domain_code) NOT IN ('', 'KOREA', 'WORLD_OTHER')
          AND sort_artist_name IS NOT NULL
          AND TRIM(sort_artist_name) <> ''
        """
    ).fetchall()

    now = utc_now_iso()
    fixed = 0
    for row in rows:
        if _HANGUL_RE.search(str(row["sort_artist_name"] or "")):
            conn.execute(
                "UPDATE album_master SET sort_artist_name = NULL, updated_at = ? WHERE id = ?",
                (now, row["id"]),
            )
            fixed += 1

    if fixed:
        conn.commit()


def _restore_latin_artist_names_from_ext_ref(conn: sqlite3.Connection) -> None:
    """album_master.artist_or_brand가 한글로 덮어써진 경우,
    album_master_external_ref의 영문 hint로 복원한다.

    backfill_discogs_korean_artist_names 실행 시 domain_code='KOREA'인
    팝 아티스트에게도 한글 이름이 기록될 수 있다.
    ext_ref.artist_or_brand_hint가 영문(라틴)이고
    album_master.artist_or_brand가 한글인 경우만 대상으로 한다.

    연결된 owned_item.linked_artist_name이 한글인 경우도 NULL로 리셋한다.
    """
    if not _column_exists(conn, "album_master", "artist_or_brand"):
        return
    if not _table_exists(conn, "album_master_external_ref"):
        return

    rows = conn.execute("""
        SELECT am.id, am.artist_or_brand, am.domain_code,
               ref.artist_or_brand_hint AS hint
        FROM album_master am
        JOIN album_master_external_ref ref ON ref.album_master_id = am.id
        WHERE am.artist_or_brand IS NOT NULL
          AND TRIM(am.artist_or_brand) <> ''
          AND COALESCE(TRIM(am.domain_code), '') NOT IN ('KOREA', '')
        GROUP BY am.id
        HAVING MIN(ref.id)
    """).fetchall()

    now = utc_now_iso()
    fixed = 0
    for row in rows:
        am_artist = str(row["artist_or_brand"] or "").strip()
        hint = str(row["hint"] or "").strip()
        # album_master.artist_or_brand가 한글이고 ext_ref hint가 영문인 경우
        if not _HANGUL_RE.search(am_artist):
            continue
        if not hint or _HANGUL_RE.search(hint):
            continue

        # 영문 hint로 복원
        conn.execute(
            "UPDATE album_master SET artist_or_brand = ?, updated_at = ? WHERE id = ?",
            (hint, now, row["id"]),
        )

        # owned_item.linked_artist_name이 한글이면 NULL 처리
        ois = conn.execute("""
            SELECT id, linked_artist_name FROM owned_item
            WHERE linked_album_master_id = ?
              AND linked_artist_name IS NOT NULL
        """, (row["id"],)).fetchall()
        for oi in ois:
            if _HANGUL_RE.search(str(oi["linked_artist_name"] or "")):
                conn.execute(
                    "UPDATE owned_item SET linked_artist_name = NULL, updated_at = ? WHERE id = ?",
                    (now, oi["id"]),
                )

        fixed += 1

    if fixed:
        conn.commit()


def _cleanup_pop_hangul_artist_names(conn: sqlite3.Connection) -> None:
    """비가요 도메인 앨범에 한글 아티스트명이 잘못 기록된 경우 영문으로 복원한다.

    backfill_discogs_korean_artist_names가 도메인 오분류된 팝 앨범에도
    한글 이름을 기록했을 수 있다. _restore_latin_artist_names_from_ext_ref 는
    artist_or_brand_hint 가 영문인 경우만 처리하지만, 이 함수는 hint 가 이미
    한글로 덮어써진 경우에도 raw_json 원본값으로 복원한다.

    복원 소스 우선순위:
      1. album_master_external_ref.raw_json 의 artist_or_brand
         (resolve_release_master_reference 가 Discogs API 에서 가져온 원본 영문명)
      2. album_master_external_ref.artist_or_brand_hint 가 아직 영문인 경우

    수정 대상 필드:
      - album_master.artist_or_brand
      - album_master_external_ref.artist_or_brand_hint  (복원)
      - owned_item.linked_artist_name
      - owned_item.item_name_override  (아티스트 prefix 교체)
      - music_item_detail.artist_or_brand
    """
    if not _table_exists(conn, "album_master"):
        return
    if not _table_exists(conn, "album_master_external_ref"):
        return

    # 비가요 도메인인데 artist_or_brand 에 한글이 있는 album_master 조회.
    # 동시에 연결된 DISCOGS ext_ref 의 hint 와 raw_json 원본명을 가져온다.
    rows = conn.execute("""
        SELECT
            am.id,
            am.artist_or_brand,
            am.domain_code,
            (
                SELECT ref.artist_or_brand_hint
                FROM album_master_external_ref ref
                WHERE ref.album_master_id = am.id
                  AND ref.source_code = 'DISCOGS'
                ORDER BY ref.id
                LIMIT 1
            ) AS hint,
            (
                SELECT json_extract(ref.raw_json, '$.artist_or_brand')
                FROM album_master_external_ref ref
                WHERE ref.album_master_id = am.id
                  AND ref.source_code = 'DISCOGS'
                ORDER BY ref.id
                LIMIT 1
            ) AS raw_artist
        FROM album_master am
        WHERE am.artist_or_brand IS NOT NULL
          AND TRIM(am.artist_or_brand) <> ''
          AND COALESCE(TRIM(am.domain_code), '') NOT IN ('KOREA', 'WORLD_OTHER', '')
    """).fetchall()

    now = utc_now_iso()
    fixed = 0
    for row in rows:
        am_artist = str(row["artist_or_brand"] or "").strip()
        if not _HANGUL_RE.search(am_artist):
            continue  # 한글 없으면 건너뜀

        # 1순위: raw_json 원본 영문명
        latin_name: str | None = None
        raw_artist = str(row["raw_artist"] or "").strip()
        if raw_artist and not _HANGUL_RE.search(raw_artist):
            latin_name = raw_artist

        # 2순위: hint 가 아직 영문이면 사용
        if not latin_name:
            hint = str(row["hint"] or "").strip()
            if hint and not _HANGUL_RE.search(hint):
                latin_name = hint

        # album_master.artist_or_brand 복원 (or NULL)
        conn.execute(
            "UPDATE album_master SET artist_or_brand = ?, updated_at = ? WHERE id = ?",
            (latin_name, now, row["id"]),
        )

        # ext_ref.artist_or_brand_hint 복원
        if latin_name:
            conn.execute(
                """UPDATE album_master_external_ref
                   SET artist_or_brand_hint = ?, updated_at = ?
                   WHERE album_master_id = ? AND source_code = 'DISCOGS'""",
                (latin_name, now, row["id"]),
            )

        # 연결된 owned_item 처리
        oi_rows = conn.execute("""
            SELECT id, linked_artist_name, item_name_override
            FROM owned_item
            WHERE linked_album_master_id = ?
        """, (row["id"],)).fetchall()

        for oi in oi_rows:
            oi_artist = str(oi["linked_artist_name"] or "").strip()
            item_name = str(oi["item_name_override"] or "").strip()

            new_oi_artist: str | None = oi_artist or None
            new_item_name: str | None = item_name or None

            # linked_artist_name: 한글이면 영문으로 교체 (또는 NULL)
            if _HANGUL_RE.search(oi_artist):
                new_oi_artist = latin_name  # None 이면 NULL 처리

            # item_name_override: 한글 아티스트 prefix 교체
            if item_name:
                if item_name == am_artist:
                    # 타이틀 전체가 아티스트명인 경우
                    new_item_name = latin_name
                elif item_name.startswith(f"{am_artist} - "):
                    rest = item_name[len(f"{am_artist} - "):]
                    new_item_name = f"{latin_name} - {rest}" if latin_name else rest
                # 한글이 여전히 포함된 경우 (다른 형태): 그냥 NULL 처리보다 유지
                # (아티스트 prefix 가 정확히 매칭되지 않으면 건드리지 않음)

            oi_changed = (new_oi_artist != (oi_artist or None)) or (new_item_name != (item_name or None))
            if oi_changed:
                conn.execute(
                    "UPDATE owned_item SET linked_artist_name = ?, item_name_override = ?, updated_at = ? WHERE id = ?",
                    (new_oi_artist, new_item_name, now, oi["id"]),
                )

        # music_item_detail.artist_or_brand 처리
        if (
            _table_exists(conn, "music_item_detail")
            and _column_exists(conn, "music_item_detail", "artist_or_brand")
            and _column_exists(conn, "music_item_detail", "updated_at")
        ):
            mid_rows = conn.execute("""
                SELECT mid.owned_item_id, mid.artist_or_brand
                FROM music_item_detail mid
                JOIN owned_item oi ON oi.id = mid.owned_item_id
                WHERE oi.linked_album_master_id = ?
                  AND mid.artist_or_brand IS NOT NULL
                  AND TRIM(mid.artist_or_brand) <> ''
            """, (row["id"],)).fetchall()

            for mid in mid_rows:
                mid_artist = str(mid["artist_or_brand"] or "").strip()
                if _HANGUL_RE.search(mid_artist):
                    conn.execute(
                        "UPDATE music_item_detail SET artist_or_brand = ?, updated_at = ? WHERE owned_item_id = ?",
                        (latin_name, now, mid["owned_item_id"]),
                    )

        fixed += 1

    if fixed:
        conn.commit()
