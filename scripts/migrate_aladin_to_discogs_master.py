"""One-time migration: ALADIN owned_items with non-Discogs masters → Discogs masters.

For each ALADIN item that has a barcode and is currently linked to a MANUAL/MANIADB
master, search Discogs by barcode. If found, upsert the Discogs album_master and
re-link the item. Items with no Discogs match are left unchanged.

Usage:
    cd ~/apps/hahahoho-prod
    .venv/bin/python3 scripts/migrate_aladin_to_discogs_master.py [--dry-run]
"""
from __future__ import annotations

import sys
import os
import time
import logging
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_conn
from app.db.album_master_core import upsert_album_master
from app.db.album_master_read import set_owned_item_linked_album_master
from app.db.album_master_member import bind_album_master_members
from app.services.providers import _try_discogs_for_barcode

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("migrate_aladin_discogs")

SLEEP_BETWEEN = 2.0  # seconds between Discogs API calls


def _infer_domain(crossref: dict) -> str | None:
    try:
        from app.main import _infer_album_master_domain_code
        return _infer_album_master_domain_code(
            source_code="DISCOGS",
            title=crossref.get("title"),
            artist_or_brand=crossref.get("artist_or_brand"),
            raw=crossref.get("raw"),
        )
    except Exception:
        return crossref.get("domain_code")


def main(dry_run: bool = False) -> None:
    logger.info("=== ALADIN → Discogs master migration %s===", "[DRY RUN] " if dry_run else "")

    with get_conn() as conn:
        rows = conn.execute("""
            SELECT oi.id          AS owned_item_id,
                   oi.source_external_id,
                   oi.item_name_override,
                   am.id          AS current_master_id,
                   am.source_code AS current_master_src,
                   am.title       AS current_master_title,
                   mid.barcode
            FROM owned_item oi
            JOIN album_master am ON am.id = oi.linked_album_master_id
            JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            WHERE oi.source_code = 'ALADIN'
              AND am.source_code != 'DISCOGS'
              AND mid.barcode IS NOT NULL
              AND TRIM(mid.barcode) != ''
            ORDER BY oi.id
        """).fetchall()

    total = len(rows)
    logger.info("대상: %d건", total)

    matched = skipped = errors = 0

    for i, row in enumerate(rows, 1):
        oi_id = row[0]
        barcode = str(row[6] or "").strip().replace("-", "").replace(" ", "")
        label = f"[{i}/{total}] oi={oi_id} ({row[2] or row[5]})"

        if not barcode:
            logger.info("%s — 바코드 없음, 건너뜀", label)
            skipped += 1
            continue

        try:
            crossref = _try_discogs_for_barcode(barcode)
        except Exception as e:
            logger.warning("%s — Discogs API 오류: %s", label, e)
            errors += 1
            time.sleep(SLEEP_BETWEEN)
            continue

        if not crossref:
            logger.info("%s — Discogs 매칭 없음 (barcode=%s)", label, barcode)
            skipped += 1
            time.sleep(SLEEP_BETWEEN)
            continue

        d_master_id = str(crossref.get("master_id") or "").strip()
        d_ext_id = str(crossref.get("external_id") or "").strip()
        d_src_id = d_master_id or d_ext_id
        d_title = str(crossref.get("title") or "").strip() or str(row[2] or row[5] or "").strip()
        d_artist = str(crossref.get("artist_or_brand") or "").strip() or None
        d_year = crossref.get("master_release_year") or crossref.get("release_year")
        d_domain = _infer_domain(crossref)
        d_raw = crossref.get("raw") or {}

        logger.info("%s — 매칭: discogs=%s '%s' (%s)", label, d_src_id, d_title, d_year)

        if not dry_run:
            try:
                new_master_id = upsert_album_master(
                    source_code="DISCOGS",
                    source_master_id=d_src_id,
                    title=d_title,
                    artist_or_brand=d_artist,
                    domain_code=d_domain,
                    release_year=d_year,
                    raw=d_raw,
                )
                bind_album_master_members(
                    album_master_id=new_master_id,
                    owned_item_ids=[oi_id],
                    replace_existing=False,
                )
                set_owned_item_linked_album_master(
                    owned_item_id=oi_id,
                    album_master_id=new_master_id,
                )
                logger.info("  → album_master #%d으로 재연결 완료", new_master_id)
                matched += 1
            except Exception as e:
                logger.error("%s — 마스터 등록/연결 실패: %s", label, e)
                errors += 1
        else:
            matched += 1

        time.sleep(SLEEP_BETWEEN)

    logger.info(
        "=== 완료: 매칭 %d건 / 미매칭 %d건 / 오류 %d건 (전체 %d건) ===",
        matched, skipped, errors, total,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="API 검색만, DB 변경 없음")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
