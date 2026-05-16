#!/usr/bin/env python3
"""
DB migration: add override_title and override_artist_or_brand columns to album_master.
Run this directly on the Mac: python3 run_db_migration.py
"""
import sqlite3
from pathlib import Path

root = Path(__file__).resolve().parent
db_path = root / "data" / "library.db"

print(f"DB path: {db_path}")
conn = sqlite3.connect(str(db_path))
cols = [r[1] for r in conn.execute("PRAGMA table_info(album_master)")]

if "override_title" not in cols:
    conn.execute("ALTER TABLE album_master ADD COLUMN override_title TEXT")
    conn.commit()
    print("OK: added override_title")
else:
    print("SKIP: override_title already exists")

if "override_artist_or_brand" not in cols:
    conn.execute("ALTER TABLE album_master ADD COLUMN override_artist_or_brand TEXT")
    conn.commit()
    print("OK: added override_artist_or_brand")
else:
    print("SKIP: override_artist_or_brand already exists")

conn.close()
print("Migration complete.")
