#!/usr/bin/env python3
"""
알라딘 입수 음반 일괄 보정 스크립트
- release_year 누락 건 → Aladin ItemLookUp으로 pubDate 재확보
- cover_image_url coversum → cover (고해상도) 로 교체
- released_date 컬럼도 함께 저장

실행 방법 (상용 서버에서):
    python3 scripts/fix_aladin_year_cover.py
"""
from __future__ import annotations

import os
import sys
import time
import sqlite3
import json
from pathlib import Path

# ── 경로 설정 ────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent

def _load_env() -> None:
    env_file = ROOT / ".env.local"
    if not env_file.is_file():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)

_load_env()

TTB_KEY   = os.environ.get("ALADIN_TTB_KEY", "")
DB_PATH   = os.environ.get("LIBRARY_DB_PATH") or str(ROOT / "data" / "library.db")
LOOKUP_URL = "https://www.aladin.co.kr/ttb/api/ItemLookUp.aspx"
SLEEP_SEC  = 0.4   # 알라딘 API rate-limit 배려

if not TTB_KEY:
    print("❌ ALADIN_TTB_KEY 없음. .env.local 확인", file=sys.stderr)
    sys.exit(1)

print(f"DB   : {DB_PATH}")
print(f"KEY  : {TTB_KEY[:8]}****")
print()

# ── httpx / urllib 선택 ──────────────────────────────────────────
try:
    import httpx
    def _get(url: str, params: dict) -> dict:
        with httpx.Client(timeout=10) as c:
            r = c.get(url, params=params)
            r.raise_for_status()
            return r.json()
except ImportError:
    from urllib.request import urlopen
    from urllib.parse import urlencode
    def _get(url: str, params: dict) -> dict:
        full = url + "?" + urlencode(params)
        with urlopen(full, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))


def _cover_hires(url: str | None) -> str | None:
    """coversum → cover に置換 (高解像度)"""
    if not url:
        return url
    return url.replace("/coversum/", "/cover/")


def _safe_year(v) -> int | None:
    try:
        y = int(str(v).split("-")[0])
        return y if 1900 <= y <= 2100 else None
    except Exception:
        return None


def _lookup(item_id: str) -> tuple[int | None, str | None, str | None]:
    """(release_year, released_date, cover_hires) 반환. 실패 시 모두 None."""
    try:
        data = _get(LOOKUP_URL, {
            "ttbkey": TTB_KEY,
            "itemId": item_id,
            "ItemIdType": "ItemId",
            "output": "js",
            "Version": "20131101",
        })
        items = data.get("item") or []
        if not items:
            return None, None, None
        it = items[0]
        pub = str(it.get("pubDate") or "").strip()
        year = _safe_year(pub) if pub else None
        released = pub if pub else None
        cover = _cover_hires(str(it.get("cover") or "").strip() or None)
        return year, released, cover
    except Exception as e:
        print(f"  ⚠️  lookup 실패: {e}")
        return None, None, None


# ── DB ───────────────────────────────────────────────────────────
db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row

rows = db.execute("""
    SELECT oi.id as owned_item_id, oi.source_external_id,
           mid.release_year, mid.cover_image_url, mid.released_date
    FROM owned_item oi
    JOIN music_item_detail mid ON mid.owned_item_id = oi.id
    WHERE oi.source_code = 'ALADIN'
      AND (mid.release_year IS NULL OR mid.release_year = 0
           OR mid.cover_image_url LIKE '%coversum%')
    ORDER BY oi.id
""").fetchall()

print(f"대상 건수: {len(rows)}")
print()

ok = skip = err = 0

for row in rows:
    oid      = row["owned_item_id"]
    ext_id   = str(row["source_external_id"] or "").strip()
    cur_year = row["release_year"]
    cur_cover= row["cover_image_url"]

    if not ext_id:
        print(f"  [{oid}] source_external_id 없음 — SKIP")
        skip += 1
        continue

    year, released, cover = _lookup(ext_id)
    time.sleep(SLEEP_SEC)

    new_year  = year   if (year  and not cur_year) else cur_year
    new_cover = cover  if cover else _cover_hires(cur_cover)

    if new_year == cur_year and new_cover == cur_cover:
        print(f"  [{oid}] itemId={ext_id} 변경없음 — SKIP")
        skip += 1
        continue

    try:
        db.execute("""
            UPDATE music_item_detail
            SET release_year    = COALESCE(?, release_year),
                released_date   = COALESCE(?, released_date),
                cover_image_url = COALESCE(?, cover_image_url),
                updated_at      = datetime('now')
            WHERE owned_item_id = ?
        """, (new_year, released, new_cover, oid))
        db.commit()
        print(f"  [{oid}] itemId={ext_id}  year={cur_year}→{new_year}  cover_hires={'Y' if new_cover != cur_cover else '-'}")
        ok += 1
    except Exception as e:
        print(f"  [{oid}] DB 업데이트 실패: {e}")
        err += 1

db.close()
print()
print(f"완료 — 업데이트: {ok}건 / 스킵: {skip}건 / 에러: {err}건")
