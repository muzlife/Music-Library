from __future__ import annotations

from contextlib import contextmanager
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
    slot = next(item for item in db.list_storage_slots() if item.get("cabinet_name"))
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
