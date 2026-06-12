"""
tests/test_search_filter_regression.py — 0.1 회귀 테스트

H1 버그: size_group_state=MATCH + track_state=HAS 조합 시 elif 체인으로
track 필터가 무시됨. 수정 후 두 필터가 AND로 적용되는지 검증.

검증 픽스처:
  A: size_group=STD, media_type=CD, track_list_json=[tracks] → MATCH+HAS
  B: size_group=STD, media_type=CD, track_list_json=NULL      → MATCH+MISSING
  C: size_group=LP,  media_type=CD, track_list_json=[tracks]  → MISMATCH+HAS
  D: size_group=STD, media_type=CD, track_list_json=[]        → MATCH+empty(MISSING)
"""

import json
import pytest

import app.db as db
from app.db.owned_item_query import list_owned_items, count_owned_items

_TAG = "REGTEST_H1_"  # unique prefix for isolation


def _list(**kw):
    defaults = dict(
        category="CD",
        domain_code=None, release_type=None, status=None,
        q=None, artist_or_brand=None, barcode=None,
        release_year=None,
        source_state="ANY", master_state="ANY", cover_state="ANY",
        slot_state="ANY", preferred_storage_state="ANY",
        music_only=False, sort="RECENT", limit=200, offset=0,
        media_format_state="ANY", size_group_state="ANY",
        catalog_missing=False, genre_missing=False,
    )
    defaults.update(kw)
    # item_name is the free-text search for item_name_override
    return list_owned_items(
        category=defaults["category"],
        domain_code=defaults["domain_code"],
        release_type=defaults["release_type"],
        status=defaults["status"],
        q=None,
        artist_or_brand=None,
        item_name=defaults.get("item_name"),
        catalog_no=None,
        barcode=defaults["barcode"],
        release_year=defaults["release_year"],
        source_state=defaults["source_state"],
        master_state=defaults["master_state"],
        cover_state=defaults["cover_state"],
        slot_state=defaults["slot_state"],
        preferred_storage_state=defaults["preferred_storage_state"],
        track_state=defaults.get("track_state", "ANY"),
        music_only=defaults["music_only"],
        sort=defaults["sort"],
        limit=defaults["limit"],
        offset=defaults["offset"],
        media_format_state=defaults["media_format_state"],
        size_group_state=defaults["size_group_state"],
        catalog_missing=defaults["catalog_missing"],
        genre_missing=defaults["genre_missing"],
    )


def _count(**kw):
    defaults = dict(
        category="CD",
        domain_code=None, release_type=None, status=None,
        q=None, artist_or_brand=None, barcode=None,
        release_year=None,
        source_state="ANY", master_state="ANY", cover_state="ANY",
        slot_state="ANY", preferred_storage_state="ANY",
        music_only=False,
        media_format_state="ANY", size_group_state="ANY",
        catalog_missing=False, genre_missing=False,
    )
    defaults.update(kw)
    return count_owned_items(
        category=defaults["category"],
        domain_code=defaults["domain_code"],
        release_type=defaults["release_type"],
        status=defaults["status"],
        q=None,
        artist_or_brand=None,
        item_name=defaults.get("item_name"),
        catalog_no=None,
        barcode=defaults["barcode"],
        release_year=defaults["release_year"],
        source_state=defaults["source_state"],
        master_state=defaults["master_state"],
        cover_state=defaults["cover_state"],
        slot_state=defaults["slot_state"],
        preferred_storage_state=defaults["preferred_storage_state"],
        track_state=defaults.get("track_state", "ANY"),
        music_only=defaults["music_only"],
        media_format_state=defaults["media_format_state"],
        size_group_state=defaults["size_group_state"],
        catalog_missing=defaults["catalog_missing"],
        genre_missing=defaults["genre_missing"],
    )


@pytest.fixture(scope="module")
def fixture_ids():
    """픽스처 4건 생성, 테스트 완료 후 정리."""
    from app.db.catalog_search import delete_catalog_search_in_conn, upsert_catalog_search_in_conn
    db.ensure_startup_db_ready()
    now = db.utc_now_iso()
    ids: dict[str, int] = {}

    specs = [
        # (label, size_group, track_list_json)
        ("A", "STD", json.dumps(["Track1", "Track2"])),  # MATCH+HAS
        ("B", "STD", None),                               # MATCH+MISSING (NULL)
        ("C", "LP",  json.dumps(["Track3"])),             # MISMATCH+HAS
        ("D", "STD", "[]"),                               # MATCH+empty=MISSING
    ]

    for label, size_group, track_json in specs:
        name = f"{_TAG}{label}"
        with db.get_write_conn() as conn:
            cur = conn.execute(
                """INSERT INTO owned_item
                     (category, status, quantity, item_name_override,
                      size_group, is_second_hand, signature_type, created_at, updated_at)
                   VALUES ('CD', 'IN_COLLECTION', 1, ?, ?, 0, 'NONE', ?, ?)""",
                (name, size_group, now, now),
            )
            oid = int(cur.lastrowid)
            conn.execute(
                """INSERT INTO music_item_detail
                     (owned_item_id, media_type, track_list_json, created_at, updated_at)
                   VALUES (?, 'CD', ?, ?, ?)""",
                (oid, track_json, now, now),
            )
            upsert_catalog_search_in_conn(conn, oid)
        ids[label] = oid

    yield ids

    for oid in ids.values():
        with db.get_write_conn() as conn:
            delete_catalog_search_in_conn(conn, oid)
            conn.execute("DELETE FROM music_item_detail WHERE owned_item_id = ?", (oid,))
            conn.execute("DELETE FROM owned_item WHERE id = ?", (oid,))


def _ids_from(rows):
    return {r["id"] for r in rows}


# ── 1. track_state=HAS 단독 → A, C ────────────────────────────────

def test_track_has_only_list(fixture_ids):
    rows = _list(item_name=_TAG, track_state="HAS")
    result = _ids_from(rows)
    assert fixture_ids["A"] in result
    assert fixture_ids["C"] in result
    assert fixture_ids["B"] not in result
    assert fixture_ids["D"] not in result


def test_track_has_only_count_matches_list(fixture_ids):
    rows = _list(item_name=_TAG, track_state="HAS")
    cnt = _count(item_name=_TAG, track_state="HAS")
    assert cnt == len(rows)


# ── 2. size_group_state=MATCH 단독 → A, B, D ──────────────────────

def test_size_match_only_list(fixture_ids):
    rows = _list(item_name=_TAG, size_group_state="MATCH")
    result = _ids_from(rows)
    assert fixture_ids["A"] in result
    assert fixture_ids["B"] in result
    assert fixture_ids["D"] in result
    assert fixture_ids["C"] not in result


def test_size_match_only_count_matches_list(fixture_ids):
    rows = _list(item_name=_TAG, size_group_state="MATCH")
    cnt = _count(item_name=_TAG, size_group_state="MATCH")
    assert cnt == len(rows)


# ── 3. MATCH+HAS 동시 → A만 (버그 핵심 검증) ─────────────────────

def test_match_and_has_list(fixture_ids):
    rows = _list(item_name=_TAG, size_group_state="MATCH", track_state="HAS")
    result = _ids_from(rows)
    assert result == {fixture_ids["A"]}, (
        f"MATCH+HAS should return only A, got ids={result}"
    )


def test_match_and_has_count_matches_list(fixture_ids):
    rows = _list(item_name=_TAG, size_group_state="MATCH", track_state="HAS")
    cnt = _count(item_name=_TAG, size_group_state="MATCH", track_state="HAS")
    assert cnt == len(rows) == 1


# ── 4. MATCH+MISSING 동시 → B, D ─────────────────────────────────

def test_match_and_missing_list(fixture_ids):
    rows = _list(item_name=_TAG, size_group_state="MATCH", track_state="MISSING")
    result = _ids_from(rows)
    assert fixture_ids["B"] in result
    assert fixture_ids["D"] in result
    assert fixture_ids["A"] not in result
    assert fixture_ids["C"] not in result


def test_match_and_missing_count_matches_list(fixture_ids):
    rows = _list(item_name=_TAG, size_group_state="MATCH", track_state="MISSING")
    cnt = _count(item_name=_TAG, size_group_state="MATCH", track_state="MISSING")
    assert cnt == len(rows) == 2


# ── 5. MISMATCH+HAS → C만 ────────────────────────────────────────

def test_mismatch_and_has_list(fixture_ids):
    rows = _list(item_name=_TAG, size_group_state="MISMATCH", track_state="HAS")
    result = _ids_from(rows)
    assert result == {fixture_ids["C"]}


def test_mismatch_and_has_count_matches_list(fixture_ids):
    rows = _list(item_name=_TAG, size_group_state="MISMATCH", track_state="HAS")
    cnt = _count(item_name=_TAG, size_group_state="MISMATCH", track_state="HAS")
    assert cnt == len(rows) == 1
