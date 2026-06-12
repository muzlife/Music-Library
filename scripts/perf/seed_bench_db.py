#!/usr/bin/env python3
"""Generate data/bench_library.db with 30k synthetic records for perf benchmarking.

Usage:
    python3 scripts/perf/seed_bench_db.py
    BENCH_DB_PATH=data/my_bench.db python3 scripts/perf/seed_bench_db.py
"""
from __future__ import annotations

import json
import os
import random
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_env_path = os.environ.get("BENCH_DB_PATH", "")
BENCH_DB: Path = (
    (Path(_env_path) if Path(_env_path).is_absolute() else REPO_ROOT / _env_path)
    if _env_path
    else REPO_ROOT / "data" / "bench_library.db"
)

assert "bench" in str(BENCH_DB), f"Safety check failed — refusing to write to: {BENCH_DB}"
assert "library.db" not in str(BENCH_DB) or "bench" in BENCH_DB.name, \
    f"Refusing: path looks like live DB: {BENCH_DB}"

random.seed(42)

# ── Schema init via app migration ──────────────────────────────────────────────
def _init_full_schema() -> None:
    """Delete bench DB and recreate with the full app schema via schema_migration."""
    if BENCH_DB.exists():
        BENCH_DB.unlink()
    BENCH_DB.parent.mkdir(parents=True, exist_ok=True)

    # Point the app at the bench DB and run its full migration
    os.environ["LIBRARY_DB_PATH"] = str(BENCH_DB)
    os.environ.setdefault("LIBRARY_AUTH_SESSION_SECRET", "bench-secret-not-for-production")

    sys.path.insert(0, str(REPO_ROOT))
    import app.db as _db  # noqa: PLC0415
    _db.ensure_startup_db_ready()
    print("  schema migration complete")

BATCH = 1000
N_OWNED = 30_000
N_ALBUM = 27_000
N_SLOTS = 128
N_EVENTS = 60_000
N_MUSIC = 250_000

KR_ARTISTS = ["아이유", "BTS", "빅뱅", "소녀시대", "레드벨벳", "블랙핑크", "EXO", "샤이니", "NCT", "에스파"]
EN_ARTISTS = ["The Beatles", "Pink Floyd", "Led Zeppelin", "David Bowie", "Radiohead", "Nirvana", "The Rolling Stones"]
KR_TITLES = ["미니2집", "정규3집", "스페셜앨범", "리패키지", "싱글", "OST", "EP"]
EN_TITLES = ["Greatest Hits", "Live Album", "Debut", "Remastered", "Deluxe Edition", "Singles Collection"]
KR_LABELS = ["SM Entertainment", "YG Entertainment", "JYP Entertainment", "HYBE", "카카오엔터"]
EN_LABELS = ["Columbia", "EMI", "Island Records", "Atlantic", "Geffen"]
GENRES = ["Pop", "Rock", "Jazz", "Classical", "Electronic", "R&B", "Hip Hop", "Country", "발라드", "댄스"]


def _wc(options, weights):
    return random.choices(options, weights=weights, k=1)[0]


def _date():
    y = random.randint(2010, 2024)
    m = random.randint(1, 12)
    d = random.randint(1, 28)
    return f"{y}-{m:02d}-{d:02d}T00:00:00"


def _artist(domain):
    return random.choice(KR_ARTISTS if domain == "KOREA" else EN_ARTISTS)


def _title(domain):
    return random.choice(KR_TITLES if domain == "KOREA" else EN_TITLES)


def _track_items():
    n = random.randint(5, 15)
    return json.dumps([
        {"position": str(j), "title": f"트랙 {j}" if random.random() < 0.5 else f"Track {j}",
         "duration": f"{random.randint(2,7)}:{random.randint(0,59):02d}"}
        for j in range(1, n + 1)
    ], ensure_ascii=False)



_NOW = "2024-01-01T00:00:00"

_CAT_OPT = ["CD", "LP", "CASSETTE", "T_SHIRT", "OTHER"]
_CAT_W = [0.40, 0.20, 0.10, 0.20, 0.10]
_DOM_OPT = ["KOREA", "WESTERN", "JAPAN"]
_DOM_W = [0.74, 0.25, 0.01]
_SZ_OPT = ["STD", "LP", "BOOK"]
_SZ_W = [0.70, 0.20, 0.10]
_SRC_OPT = ["DISCOGS", "MANIADB", None]
_SRC_W = [0.50, 0.30, 0.20]


def _batch_insert(conn, sql, rows):
    for i in range(0, len(rows), BATCH):
        conn.executemany(sql, rows[i:i + BATCH])
    conn.commit()


def seed(conn):
    # --- local_music_index (created on demand by app; create it here for bench) ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS local_music_index (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          file_path TEXT NOT NULL UNIQUE,
          title TEXT NOT NULL,
          artist TEXT NOT NULL,
          album TEXT,
          genre TEXT,
          year TEXT,
          track_number INTEGER,
          duration_seconds REAL,
          file_size INTEGER,
          has_cover INTEGER NOT NULL DEFAULT 0,
          indexed_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lmi_title ON local_music_index (title)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lmi_artist ON local_music_index (artist)")
    conn.commit()

    # --- storage_slot (actual schema: slot_code, allowed_size_group, cabinet_sort_policy,
    #     cabinet_domain_code, max_thickness_mm, cabinet_group_name, cabinet_group_order,
    #     is_overflow_zone, created_at, updated_at, cabinet_name, column_code, cell_code) ---
    slots = []
    for i in range(1, N_SLOTS + 1):
        code = f"A{i:03d}"
        dom = _wc(["KOREA", "WESTERN"], [0.6, 0.4])
        sz = "STD" if i % 3 != 0 else "LP"
        slots.append((code, sz, "ARTIST_RELEASE_TITLE", dom, 30, f"Cabinet {(i-1)//8 + 1}", (i-1) % 8, 0, _NOW, _NOW, f"Cabinet {(i-1)//8 + 1}", f"C{(i-1)//8 + 1}", f"R{(i-1) % 8 + 1}"))
    _batch_insert(conn,
        "INSERT INTO storage_slot(slot_code,allowed_size_group,cabinet_sort_policy,cabinet_domain_code,max_thickness_mm,cabinet_group_name,cabinet_group_order,is_overflow_zone,created_at,updated_at,cabinet_name,column_code,cell_code) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        slots)
    print(f"  storage_slot: {N_SLOTS} rows")

    # --- album_master ---
    masters = []
    for i in range(1, N_ALBUM + 1):
        dom = _wc(_DOM_OPT, _DOM_W)
        art = _artist(dom)
        masters.append(("DISCOGS", f"m{i}", _title(dom), art, art, dom, random.randint(1990, 2024), "{}", _NOW, _NOW))
    _batch_insert(conn,
        "INSERT INTO album_master(source_code,source_master_id,title,artist_or_brand,sort_artist_name,domain_code,release_year,raw_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        masters)
    print(f"  album_master: {N_ALBUM} rows")

    # --- owned_item ---
    owned = []
    for i in range(1, N_OWNED + 1):
        cat = _wc(_CAT_OPT, _CAT_W)
        dom = _wc(_DOM_OPT, _DOM_W)
        sz = _wc(_SZ_OPT, _SZ_W)
        src = _wc(_SRC_OPT, _SRC_W)
        ext_id = str(i) if src else None
        slot = random.randint(1, N_SLOTS) if random.random() < 0.7 else None
        art = _artist(dom)
        owned.append((
            i,                              # master_item_id
            random.randint(1, N_ALBUM),     # linked_album_master_id
            art,                            # linked_artist_name
            f"grp_{i}",                     # copy_group_key
            cat, dom,
            "ALBUM",                        # release_type
            None,                           # item_name_override
            1,                              # quantity
            0,                              # is_second_hand
            sz, sz,                         # size_group, preferred
            "IN_COLLECTION",
            "NEAR_MINT",                    # condition_grade
            "NONE",                         # signature_type
            src, ext_id,
            None, None,                     # signed_by, signed_at
            _date(),                        # acquisition_date
            round(random.uniform(5, 300), 2),
            "KRW",
            "Online",                       # purchase_source
            None,                           # memory_note
            i,                              # display_rank
            f"ok{i:06d}",                   # order_key
            slot,
            round(random.uniform(2, 15), 1),
            None,                           # notes
            _NOW, _NOW,
        ))
    _batch_insert(conn,
        "INSERT INTO owned_item(master_item_id,linked_album_master_id,linked_artist_name,copy_group_key,category,domain_code,release_type,item_name_override,quantity,is_second_hand,size_group,preferred_storage_size_group,status,condition_grade,signature_type,source_code,source_external_id,signed_by,signed_at,acquisition_date,purchase_price,currency_code,purchase_source,memory_note,display_rank,order_key,storage_slot_id,thickness_mm,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        owned)
    print(f"  owned_item: {N_OWNED} rows")

    # --- music_item_detail ---
    details = []
    for i in range(1, N_OWNED + 1):
        dom = _wc(_DOM_OPT, _DOM_W)
        art = _artist(dom)
        label = random.choice(KR_LABELS if dom == "KOREA" else EN_LABELS)
        details.append((
            i,                              # owned_item_id
            "Album",                        # format_name
            0,                              # is_promotional_not_for_sale
            art,
            random.randint(1990, 2024),     # release_year
            None,                           # released_date
            f"880{random.randint(10000000,99999999)}",  # barcode
            label,
            f"CAT{random.randint(1000,9999)}",          # catalog_no
            None,                           # cover_image_url
            None,                           # track_list_json
            "CD",                           # media_type
            json.dumps([random.choice(GENRES)]),  # genres_json
            json.dumps([]),                 # styles_json
            "Mint (M)",                     # media_condition
            "Mint (M)",                     # sleeve_condition
            1,                              # disc_count
            33,                             # speed_rpm
            0,                              # has_obi
            None, None,                     # runout_matrix, runout_matrix_json
            None,                           # pressing_country
            None,                           # source_notes
            None,                           # credits_json
            None,                           # identifier_items_json
            None,                           # image_items_json
            None,                           # company_items_json
            None,                           # series_json
            None,                           # format_items_json
            _track_items(),                 # track_items_json
            None,                           # label_items_json
            "", "",                         # created_at, updated_at
            None,                           # disc_type
            None,                           # package_contents
            0,                              # is_limited_edition
            None,                           # edition_number
            None,                           # local_image_items_json
        ))
    _batch_insert(conn,
        "INSERT INTO music_item_detail(owned_item_id,format_name,is_promotional_not_for_sale,artist_or_brand,release_year,released_date,barcode,label_name,catalog_no,cover_image_url,track_list_json,media_type,genres_json,styles_json,media_condition,sleeve_condition,disc_count,speed_rpm,has_obi,runout_matrix,runout_matrix_json,pressing_country,source_notes,credits_json,identifier_items_json,image_items_json,company_items_json,series_json,format_items_json,track_items_json,label_items_json,created_at,updated_at,disc_type,package_contents,is_limited_edition,edition_number,local_image_items_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        details)
    print(f"  music_item_detail: {N_OWNED} rows")

    # --- owned_item_location_event ---
    events = []
    for _ in range(N_EVENTS):
        oid = random.randint(1, N_OWNED)
        to_slot = random.randint(1, N_SLOTS)
        code = f"A{to_slot:03d}"
        events.append((oid, None, None, None, to_slot, code, f"Slot {code}", "ASSIGN", None, _NOW))
    _batch_insert(conn,
        "INSERT INTO owned_item_location_event(owned_item_id,from_storage_slot_id,from_slot_code,from_slot_display_name,to_storage_slot_id,to_slot_code,to_slot_display_name,movement_kind,note,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        events)
    print(f"  owned_item_location_event: {N_EVENTS} rows")

    # --- local_music_index ---
    all_artists = KR_ARTISTS + EN_ARTISTS
    music_rows = []
    for i in range(1, N_MUSIC + 1):
        art = random.choice(all_artists)
        album = f"Album_{random.randint(1,5000)}"
        music_rows.append((
            f"/music/{art}/{album}/{i:06d}.flac",
            f"Track {i}",
            art, album,
            random.choice(GENRES),
            str(random.randint(1990, 2024)),
            random.randint(1, 20),
            round(random.uniform(120, 600), 1),
            random.randint(1_000_000, 50_000_000),
            0,
            _NOW,
        ))
    _batch_insert(conn,
        "INSERT INTO local_music_index(file_path,title,artist,album,genre,year,track_number,duration_seconds,file_size,has_cover,indexed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        music_rows)
    print(f"  local_music_index: {N_MUSIC} rows")


def main():
    print(f"Initialising schema on {BENCH_DB} …")
    _init_full_schema()

    conn = sqlite3.connect(str(BENCH_DB))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA cache_size=-65536")

    print("Seeding benchmark DB...")
    seed(conn)

    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("ANALYZE")
    conn.close()

    mb = BENCH_DB.stat().st_size / (1024 * 1024)
    print(f"\nDone. {BENCH_DB} — {mb:.1f} MB")


if __name__ == "__main__":
    main()
