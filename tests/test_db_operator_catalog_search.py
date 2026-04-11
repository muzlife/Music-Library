from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator

import pytest

from app import db
from app.config import get_settings


class RecordingConnection:
    def __init__(self, conn, statements: list[str]) -> None:
        self._conn = conn
        self._statements = statements

    def execute(self, sql, params=()):
        self._statements.append(" ".join(str(sql).split()))
        return self._conn.execute(sql, params)

    def __getattr__(self, name: str):
        return getattr(self._conn, name)


@pytest.fixture
def isolated_operator_search_db(tmp_path, monkeypatch) -> Iterator[None]:
    monkeypatch.setenv("LIBRARY_DB_PATH", str(tmp_path / "operator-search.db"))
    get_settings.cache_clear()
    db.init_db()
    yield
    get_settings.cache_clear()


@contextmanager
def record_search_sql(monkeypatch) -> Iterator[list[str]]:
    statements: list[str] = []
    original_get_conn = db.get_conn

    @contextmanager
    def wrapped_get_conn():
        with original_get_conn() as conn:
            yield RecordingConnection(conn, statements)

    monkeypatch.setattr(db, "get_conn", wrapped_get_conn)
    try:
        yield statements
    finally:
        monkeypatch.setattr(db, "get_conn", original_get_conn)


def insert_music_owned_item(
    *,
    item_name: str,
    artist: str,
    label: str,
    catalog_no: str,
    barcode: str,
    track_list: list[str],
    track_items: list[dict[str, str]],
    storage_slot_id: int | None = None,
) -> int:
    return db.insert_owned_item(
        {
            "category": "CD",
            "quantity": 1,
            "size_group": "STD",
            "status": "IN_COLLECTION",
            "item_name_override": item_name,
            "storage_slot_id": storage_slot_id,
            "music_detail": {
                "format_name": "CD",
                "artist_or_brand": artist,
                "label_name": label,
                "catalog_no": catalog_no,
                "barcode": barcode,
                "track_list": track_list,
                "track_items": track_items,
            },
        }
    )


def operator_search_sql(statements: list[str]) -> list[str]:
    return [sql for sql in statements if "FROM owned_item oi" in sql]


def test_search_operator_catalog_uses_primary_query_without_json_fallback_when_limit_is_satisfied(
    isolated_operator_search_db, monkeypatch
):
    slot = db.upsert_storage_slot(
        cabinet_name="검색 테스트 장",
        column_code="01",
        cell_code="01",
        allowed_size_group="STD",
        cabinet_sort_policy="ARTIST_RELEASE_TITLE",
    )
    owned_item_id = insert_music_owned_item(
        item_name="Field Guide",
        artist="Operator Team",
        label="Fast Label",
        catalog_no="FAST-001",
        barcode="8800000000001",
        track_list=["Slow Song"],
        track_items=[{"display": "1. Slow Song", "title": "Slow Song"}],
        storage_slot_id=int(slot["id"]),
    )

    with record_search_sql(monkeypatch) as statements:
        rows = db.search_operator_catalog("field", limit=1)

    assert len(rows) == 1
    assert int(rows[0]["id"]) == owned_item_id
    assert rows[0]["current_cabinet_name"] == slot["cabinet_name"]
    assert rows[0]["current_column_code"] == slot["column_code"]
    assert rows[0]["current_cell_code"] == slot["cell_code"]
    assert rows[0]["track_list"] == ["Slow Song"]
    assert rows[0]["track_items"][0]["title"] == "Slow Song"

    search_sql = operator_search_sql(statements)
    assert len(search_sql) == 1
    assert "json_each" not in search_sql[0]
    assert "LOWER(COALESCE(mid.track_list_json, '')) LIKE ?" not in search_sql[0]
    assert "LOWER(COALESCE(mid.track_items_json, '')) LIKE ?" not in search_sql[0]


def test_search_operator_catalog_uses_json_fallback_only_to_fill_remaining_results(
    isolated_operator_search_db, monkeypatch
):
    primary_id = insert_music_owned_item(
        item_name="밤의 도시",
        artist="청춘 밴드",
        label="Fast Label",
        catalog_no="FAST-101",
        barcode="8800000000101",
        track_list=["Intro"],
        track_items=[{"display": "1. Intro", "title": "Intro"}],
    )
    fallback_id = insert_music_owned_item(
        item_name="다른 앨범",
        artist="Fallback Artist",
        label="Slow Label",
        catalog_no="SLOW-202",
        barcode="8800000000202",
        track_list=["청춘"],
        track_items=[{"display": "1. 청춘", "title": "청춘"}],
    )

    with record_search_sql(monkeypatch) as statements:
        rows = db.search_operator_catalog("청춘", limit=2)

    assert len(rows) == 2
    assert {int(row["id"]) for row in rows} == {primary_id, fallback_id}
    assert int(rows[0]["id"]) == fallback_id
    assert rows[0]["track_matches"][0] == "청춘"
    assert rows[0]["matched_track_count"] >= 1
    assert rows[1]["track_matches"] == []

    search_sql = operator_search_sql(statements)
    assert len(search_sql) == 2
    assert "json_each" not in search_sql[0]
    assert "json_each" in search_sql[1]


def test_search_operator_catalog_keeps_individual_cabinet_display_even_when_grouped(
    isolated_operator_search_db,
):
    db.register_storage_cabinet_slots(
        cabinet_name="가요장 A",
        floor_count=1,
        cell_count=2,
        allowed_size_group="STD",
        cabinet_sort_policy="ARTIST_RELEASE_TITLE",
        cabinet_group_name="가요 메인열",
        cabinet_group_order=1,
    )
    db.register_storage_cabinet_slots(
        cabinet_name="가요장 B",
        floor_count=1,
        cell_count=2,
        allowed_size_group="STD",
        cabinet_sort_policy="ARTIST_RELEASE_TITLE",
        cabinet_group_name="가요 메인열",
        cabinet_group_order=2,
    )
    grouped_slot = next(
        row for row in db.list_storage_slots()
        if row["cabinet_name"] == "가요장 B" and row["column_code"] == "01" and row["cell_code"] == "01"
    )
    insert_music_owned_item(
        item_name="그룹 위치 확인",
        artist="산울림",
        label="Group Label",
        catalog_no="GROUP-001",
        barcode="8800000009999",
        track_list=["Track 1"],
        track_items=[{"display": "1. Track 1", "title": "Track 1"}],
        storage_slot_id=int(grouped_slot["id"]),
    )

    rows = db.search_operator_catalog("그룹 위치 확인", limit=5)

    assert len(rows) == 1
    assert rows[0]["current_cabinet_name"] == "가요장 B"
    assert rows[0]["current_slot_display_name"] == "가요장 B / 01열 / 01칸"


def test_recent_move_flag_only_applies_within_one_day(isolated_operator_search_db):
    slot = db.upsert_storage_slot(
        cabinet_name="이동 테스트 장",
        column_code="01",
        cell_code="01",
        allowed_size_group="STD",
        cabinet_sort_policy="ARTIST_RELEASE_TITLE",
    )
    owned_item_id = insert_music_owned_item(
        item_name="최근 이동 테스트",
        artist="테스트 밴드",
        label="Move Label",
        catalog_no="MOVE-001",
        barcode="8800000000303",
        track_list=["Move"],
        track_items=[{"display": "1. Move", "title": "Move"}],
        storage_slot_id=int(slot["id"]),
    )

    with db.get_conn() as conn:
        recent_at = (datetime.now(timezone.utc) - timedelta(hours=23)).isoformat()
        conn.execute(
            "UPDATE owned_item_location_event SET created_at = ? WHERE owned_item_id = ?",
            (recent_at, owned_item_id),
        )
    row = next(item for item in db.list_owned_items_for_storage_slot(int(slot["id"])) if int(item["id"]) == owned_item_id)
    assert bool(row["recently_moved_to_current_slot"]) is True

    with db.get_conn() as conn:
        stale_at = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        conn.execute(
            "UPDATE owned_item_location_event SET created_at = ? WHERE owned_item_id = ?",
            (stale_at, owned_item_id),
        )
    row = next(item for item in db.list_owned_items_for_storage_slot(int(slot["id"])) if int(item["id"]) == owned_item_id)
    assert bool(row["recently_moved_to_current_slot"]) is False


def test_slot_display_rank_move_overrides_default_artist_sort_and_resets_on_slot_change(isolated_operator_search_db):
    slot = db.upsert_storage_slot(
        cabinet_name="QA 장",
        column_code="01",
        cell_code="01",
        allowed_size_group="STD",
        cabinet_sort_policy="ARTIST_RELEASE_TITLE",
    )
    other_slot = db.upsert_storage_slot(
        cabinet_name="QA 장",
        column_code="01",
        cell_code="02",
        allowed_size_group="STD",
        cabinet_sort_policy="ARTIST_RELEASE_TITLE",
    )

    alpha_id = insert_music_owned_item(
        item_name="Alpha Album",
        artist="Alpha Artist",
        label="QA Label",
        catalog_no="QA-001",
        barcode="8800000000401",
        track_list=["A"],
        track_items=[{"display": "1. A", "title": "A"}],
        storage_slot_id=int(slot["id"]),
    )
    beta_id = insert_music_owned_item(
        item_name="Beta Album",
        artist="Beta Artist",
        label="QA Label",
        catalog_no="QA-002",
        barcode="8800000000402",
        track_list=["B"],
        track_items=[{"display": "1. B", "title": "B"}],
        storage_slot_id=int(slot["id"]),
    )
    gamma_id = insert_music_owned_item(
        item_name="Gamma Album",
        artist="Gamma Artist",
        label="QA Label",
        catalog_no="QA-003",
        barcode="8800000000403",
        track_list=["C"],
        track_items=[{"display": "1. C", "title": "C"}],
        storage_slot_id=int(slot["id"]),
    )

    rows = db.list_owned_items_for_storage_slot(int(slot["id"]))
    assert [int(row["id"]) for row in rows[:3]] == [alpha_id, beta_id, gamma_id]

    moved_rank = db.move_owned_item_slot_display_rank(
        int(slot["id"]),
        owned_item_id=gamma_id,
        target_owned_item_id=alpha_id,
        position="BEFORE",
    )
    assert moved_rank == 10

    rows = db.list_owned_items_for_storage_slot(int(slot["id"]))
    assert [int(row["id"]) for row in rows[:3]] == [gamma_id, alpha_id, beta_id]
    assert [row["display_rank"] for row in rows[:3]] == [10, 20, 30]

    db.update_owned_item_slot(gamma_id, int(other_slot["id"]))

    moved_row = db.get_owned_item(gamma_id)
    assert moved_row is not None
    assert moved_row["display_rank"] is None

    rows = db.list_owned_items_for_storage_slot(int(slot["id"]))
    assert [int(row["id"]) for row in rows[:2]] == [alpha_id, beta_id]


def test_slot_listing_supports_mixed_display_rank_and_default_sort_rows(isolated_operator_search_db):
    slot = db.upsert_storage_slot(
        cabinet_name="혼합 정렬 장",
        column_code="01",
        cell_code="01",
        allowed_size_group="LP",
        cabinet_sort_policy="ARTIST_RELEASE_TITLE",
    )

    ranked_id = insert_music_owned_item(
        item_name="Ranked Album",
        artist="Ranked Artist",
        label="QA Label",
        catalog_no="QA-RANK",
        barcode="8800000000411",
        track_list=["R"],
        track_items=[{"display": "1. R", "title": "R"}],
        storage_slot_id=int(slot["id"]),
    )
    natural_id = insert_music_owned_item(
        item_name="Natural Album",
        artist="Natural Artist",
        label="QA Label",
        catalog_no="QA-NAT",
        barcode="8800000000412",
        track_list=["N"],
        track_items=[{"display": "1. N", "title": "N"}],
        storage_slot_id=int(slot["id"]),
    )

    with db.get_conn() as conn:
        conn.execute(
            "UPDATE owned_item SET display_rank = ? WHERE id = ?",
            (10, ranked_id),
        )

    rows = db.list_owned_items_for_storage_slot(int(slot["id"]))

    assert [int(row["id"]) for row in rows[:2]] == [ranked_id, natural_id]


def test_slot_artist_sort_uses_item_released_date_before_title_when_master_year_matches(isolated_operator_search_db):
    slot = db.upsert_storage_slot(
        cabinet_name="LP장 4",
        column_code="01",
        cell_code="01",
        allowed_size_group="LP",
        cabinet_sort_policy="ARTIST_RELEASE_TITLE",
    )

    late_title_id = insert_music_owned_item(
        item_name="Alpha Album",
        artist="Angelo Branduardi",
        label="QA Label",
        catalog_no="AB-001",
        barcode="8800000001401",
        track_list=["A"],
        track_items=[{"display": "1. A", "title": "A"}],
        storage_slot_id=int(slot["id"]),
    )
    early_title_id = insert_music_owned_item(
        item_name="Bravo Album",
        artist="Angelo Branduardi",
        label="QA Label",
        catalog_no="AB-002",
        barcode="8800000001402",
        track_list=["B"],
        track_items=[{"display": "1. B", "title": "B"}],
        storage_slot_id=int(slot["id"]),
    )

    alpha_master_id = db.upsert_album_master(
        source_code="DISCOGS",
        source_master_id="alpha-master",
        title="Alpha Album",
        artist_or_brand="Angelo Branduardi",
        domain_code="WORLD",
        release_year=1994,
        raw={"source": "DISCOGS", "master_external_id": "alpha-master", "title": "Alpha Album", "artist_or_brand": "Angelo Branduardi", "release_year": 1994},
    )
    bravo_master_id = db.upsert_album_master(
        source_code="DISCOGS",
        source_master_id="bravo-master",
        title="Bravo Album",
        artist_or_brand="Angelo Branduardi",
        domain_code="WORLD",
        release_year=1994,
        raw={"source": "DISCOGS", "master_external_id": "bravo-master", "title": "Bravo Album", "artist_or_brand": "Angelo Branduardi", "release_year": 1994},
    )

    with db.get_conn() as conn:
        conn.execute("UPDATE owned_item SET linked_album_master_id = ? WHERE id = ?", (alpha_master_id, late_title_id))
        conn.execute("UPDATE owned_item SET linked_album_master_id = ? WHERE id = ?", (bravo_master_id, early_title_id))
        conn.execute("UPDATE music_item_detail SET released_date = ? WHERE owned_item_id = ?", ("1994-11-20", late_title_id))
        conn.execute("UPDATE music_item_detail SET released_date = ? WHERE owned_item_id = ?", ("1994-01-20", early_title_id))
    db.bind_album_master_members(alpha_master_id, [late_title_id])
    db.bind_album_master_members(bravo_master_id, [early_title_id])

    rows = db.list_owned_items_for_storage_slot(int(slot["id"]))

    assert [int(row["id"]) for row in rows[:2]] == [early_title_id, late_title_id]


def test_slot_artist_sort_prefers_master_release_date_before_item_release_date(isolated_operator_search_db):
    slot = db.upsert_storage_slot(
        cabinet_name="LP장 6",
        column_code="01",
        cell_code="01",
        allowed_size_group="LP",
        cabinet_sort_policy="ARTIST_RELEASE_TITLE",
    )

    later_item_date_id = insert_music_owned_item(
        item_name="A Hard Day's Night",
        artist="The Beatles",
        label="QA Label",
        catalog_no="TB-064A",
        barcode="8800000001601",
        track_list=["A Hard Day's Night"],
        track_items=[{"display": "1. A Hard Day's Night", "title": "A Hard Day's Night"}],
        storage_slot_id=int(slot["id"]),
    )
    earlier_item_date_id = insert_music_owned_item(
        item_name="Beatles For Sale",
        artist="The Beatles",
        label="QA Label",
        catalog_no="TB-064B",
        barcode="8800000001602",
        track_list=["No Reply"],
        track_items=[{"display": "1. No Reply", "title": "No Reply"}],
        storage_slot_id=int(slot["id"]),
    )

    hard_days_master_id = db.upsert_album_master(
        source_code="DISCOGS",
        source_master_id="beatles-master-a-hard-days-night",
        title="A Hard Day's Night",
        artist_or_brand="The Beatles",
        domain_code="WESTERN",
        release_year=1964,
        raw={
            "source": "DISCOGS",
            "master_external_id": "beatles-master-a-hard-days-night",
            "title": "A Hard Day's Night",
            "artist_or_brand": "The Beatles",
            "release_year": 1964,
            "release_date": "1964-07-10",
        },
    )
    beatles_for_sale_master_id = db.upsert_album_master(
        source_code="DISCOGS",
        source_master_id="beatles-master-beatles-for-sale",
        title="Beatles For Sale",
        artist_or_brand="The Beatles",
        domain_code="WESTERN",
        release_year=1964,
        raw={
            "source": "DISCOGS",
            "master_external_id": "beatles-master-beatles-for-sale",
            "title": "Beatles For Sale",
            "artist_or_brand": "The Beatles",
            "release_year": 1964,
            "release_date": "1964-12-04",
        },
    )

    with db.get_conn() as conn:
        conn.execute("UPDATE owned_item SET linked_album_master_id = ? WHERE id = ?", (hard_days_master_id, later_item_date_id))
        conn.execute("UPDATE owned_item SET linked_album_master_id = ? WHERE id = ?", (beatles_for_sale_master_id, earlier_item_date_id))
        conn.execute("UPDATE music_item_detail SET released_date = ? WHERE owned_item_id = ?", ("1993", later_item_date_id))
        conn.execute("UPDATE music_item_detail SET released_date = ? WHERE owned_item_id = ?", ("1990-11-10", earlier_item_date_id))
    db.bind_album_master_members(hard_days_master_id, [later_item_date_id])
    db.bind_album_master_members(beatles_for_sale_master_id, [earlier_item_date_id])

    rows = db.list_owned_items_for_storage_slot(int(slot["id"]))

    assert [int(row["id"]) for row in rows[:2]] == [later_item_date_id, earlier_item_date_id]


def test_slot_artist_sort_ignores_leading_english_articles(isolated_operator_search_db):
    slot = db.upsert_storage_slot(
        cabinet_name="LP장 5",
        column_code="01",
        cell_code="01",
        allowed_size_group="LP",
        cabinet_sort_policy="ARTIST_RELEASE_TITLE",
    )

    beatles_id = insert_music_owned_item(
        item_name="Abbey Road",
        artist="The Beatles",
        label="QA Label",
        catalog_no="TB-001",
        barcode="8800000001501",
        track_list=["Come Together"],
        track_items=[{"display": "1. Come Together", "title": "Come Together"}],
        storage_slot_id=int(slot["id"]),
    )
    bob_id = insert_music_owned_item(
        item_name="Highway 61 Revisited",
        artist="Bob Dylan",
        label="QA Label",
        catalog_no="BD-001",
        barcode="8800000001502",
        track_list=["Like a Rolling Stone"],
        track_items=[{"display": "1. Like a Rolling Stone", "title": "Like a Rolling Stone"}],
        storage_slot_id=int(slot["id"]),
    )

    rows = db.list_owned_items_for_storage_slot(int(slot["id"]))

    assert [int(row["id"]) for row in rows[:2]] == [beatles_id, bob_id]
