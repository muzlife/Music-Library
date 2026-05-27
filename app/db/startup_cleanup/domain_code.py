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

from app.db import (  # noqa: E402 — package surface
    _column_exists,
    _table_exists,
    utc_now_iso,
)

_HANGUL_RE = re.compile(r"[가-힣ㄱ-ㆎ]")
_KANA_RE = re.compile(r"[぀-ヿㇰ-ㇿ]")
_log = logging.getLogger(__name__)


def _sync_album_master_domain_from_owned_items(conn: sqlite3.Connection) -> None:
    """album_master.domain_code가 'KOREA'이지만 아티스트명에 한글이 없는
    (라틴 알파벳) 팝 아티스트 앨범의 domain_code를 WESTERN으로 정정한다.

    두 가지 케이스를 처리한다:
    A) owned_item.domain_code = WESTERN (한글 표기명 등록으로 오분류)
       → owned_item 도메인으로 album_master 업데이트
    B) owned_item.domain_code = KOREA (국내 면세점 등 구매 경로 영향으로 오분류)
       → 라틴 아티스트이고 infer_domain_code가 KOREA가 아닌 경우
       → album_master + owned_item 모두 WESTERN으로 업데이트

    override_domain_code가 설정된 레코드는 수정하지 않는다.
    """
    if not _column_exists(conn, "album_master", "domain_code"):
        return
    if not _column_exists(conn, "album_master", "override_domain_code"):
        return
    if not _column_exists(conn, "owned_item", "domain_code"):
        return
    if not _column_exists(conn, "owned_item", "linked_album_master_id"):
        return

    # KOREA로 분류된 album_master 중 override 없는 것 대상
    # MANIADB는 한국 전용 DB이므로 제외 (Korean-only source)
    # WORLD_OTHER는 해외 활동 국내 아티스트이므로 제외
    candidates = conn.execute("""
        SELECT id, artist_or_brand, source_code, raw_json
        FROM album_master
        WHERE domain_code = 'KOREA'
          AND (override_domain_code IS NULL OR TRIM(override_domain_code) = '')
          AND COALESCE(TRIM(source_code), '') NOT IN ('MANIADB')
    """).fetchall()

    now = utc_now_iso()
    fixed = 0
    for row in candidates:
        am_id = row["id"]
        artist = str(row["artist_or_brand"] or "").strip()

        # 연결된 owned_item 도메인 목록
        oi_rows = conn.execute("""
            SELECT id, TRIM(domain_code) AS dc
            FROM owned_item
            WHERE linked_album_master_id = ?
              AND domain_code IS NOT NULL
              AND TRIM(domain_code) <> ''
        """, (am_id,)).fetchall()

        if not oi_rows:
            continue  # 연결된 owned_item 없음 → 건드리지 않음

        domains = {r["dc"] for r in oi_rows}

        # Case A: owned_item이 모두 비가요 → owned_item 다수결 도메인으로 album_master 수정
        if "KOREA" not in domains:
            counts = conn.execute("""
                SELECT TRIM(domain_code) AS dc, COUNT(*) AS cnt
                FROM owned_item
                WHERE linked_album_master_id = ?
                  AND domain_code IS NOT NULL AND TRIM(domain_code) <> ''
                GROUP BY TRIM(domain_code)
                ORDER BY cnt DESC, TRIM(domain_code) ASC
                LIMIT 1
            """, (am_id,)).fetchone()
            new_domain = counts["dc"] if counts else "WESTERN"
            conn.execute(
                "UPDATE album_master SET domain_code = ?, source_domain_code = ?, updated_at = ? WHERE id = ?",
                (new_domain, new_domain, now, am_id),
            )
            fixed += 1
            continue

        # Case B: owned_item 중 KOREA가 있지만, 아티스트가 라틴 문자인 경우
        # infer_domain_code로 재계산해서 KOREA가 아니면 WESTERN으로 수정
        if artist and not _HANGUL_RE.search(artist) and not _KANA_RE.search(artist):
            try:
                rj = json.loads(row["raw_json"] or "{}")
            except Exception:
                rj = {}
            from app.services.providers import infer_domain_code
            new_code = infer_domain_code(
                genres=rj.get("genres") or rj.get("genre") or [],
                styles=rj.get("styles") or rj.get("style") or [],
                country=rj.get("country"),
                artist_or_brand=artist,
                title=rj.get("title"),
                label_name=rj.get("label") or rj.get("label_name"),
                source=str(row["source_code"] or ""),
            )
            if new_code != "KOREA":
                conn.execute(
                    "UPDATE album_master SET domain_code = 'WESTERN', source_domain_code = 'WESTERN', updated_at = ? WHERE id = ?",
                    (now, am_id),
                )
                # 연결된 owned_item 중 KOREA인 것도 WESTERN으로 수정
                for oi in oi_rows:
                    if oi["dc"] == "KOREA":
                        conn.execute(
                            "UPDATE owned_item SET domain_code = 'WESTERN', updated_at = ? WHERE id = ?",
                            (now, oi["id"]),
                        )
                fixed += 1

    if fixed:
        conn.commit()


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
