import base64
from types import SimpleNamespace
import sqlite3
import httpx
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone, timedelta

import app.main as main_module
import app.config as config_module
from app import db
from app.services import providers as provider_module


def _assert_index_shell_response(response):
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<!doctype html>" in response.text.lower()
    assert "Hahahoho Library Management Console" in response.text


def test_unauthenticated_root_redirects_to_login(client):
    res = client.get("/", follow_redirects=False, headers={"accept": "text/html"})
    assert res.status_code == 303
    assert res.headers["location"] == "/login"


def test_unauthenticated_ops_redirects_to_login(client):
    res = client.get("/ops", follow_redirects=False, headers={"accept": "text/html"})
    assert res.status_code == 303
    assert res.headers["location"] == "/login"


def test_unauthenticated_ops_cabinets_redirects_to_login(client):
    res = client.get("/ops/cabinets", follow_redirects=False, headers={"accept": "text/html"})
    assert res.status_code == 303
    assert res.headers["location"] == "/login"


def test_login_route_serves_login_page_with_locale_and_theme_controls(client):
    res = client.get("/login", headers={"accept": "text/html"})

    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")
    assert "<!doctype html>" in res.text.lower()
    assert 'id="loginLocaleSelect"' in res.text
    assert 'id="loginThemeToggle"' in res.text


def test_operator_cannot_open_admin_route(operator_client):
    res = operator_client.get("/admin", follow_redirects=False, headers={"accept": "text/html"})
    assert res.status_code == 303
    assert res.headers["location"] == "/ops"


def test_operator_can_post_barcode_recommend_location(operator_client):
    res = operator_client.post(
        "/ingest/barcode/recommend-location",
        json={
            "category": "CD",
            "size_group": "STD",
            "format_name": "CD",
            "artist_or_brand": "산울림",
            "title": "1집",
        },
    )
    # Operator can access operational ingest routes
    assert res.status_code != 403


def test_admin_root_redirects_to_ops(admin_client):
    res = admin_client.get("/", follow_redirects=False, headers={"accept": "text/html"})
    assert res.status_code == 303
    assert res.headers["location"] == "/ops"


def test_system_status_uses_forwarded_qa_host_for_external_urls(admin_client):
    response = admin_client.get(
        "/system/status",
        headers={
            "host": "__QA_DOMAIN__",
            "x-forwarded-host": "__QA_DOMAIN__",
            "x-forwarded-proto": "https",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["external_login_url"] == "https://__QA_DOMAIN__/login"
    assert payload["external_health_url"] == "https://__QA_DOMAIN__/health"


def test_authenticated_ops_serves_index_html(operator_client):
    res = operator_client.get("/ops", headers={"accept": "text/html"})
    _assert_index_shell_response(res)


def test_authenticated_ops_cabinets_serves_index_html(operator_client):
    res = operator_client.get("/ops/cabinets", headers={"accept": "text/html"})
    _assert_index_shell_response(res)


def test_operator_can_read_shared_camera_list(operator_client):
    res = operator_client.get("/cabinet-cameras")

    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_operator_can_mutate_shared_cameras(operator_client):
    res = operator_client.post(
        "/cabinet-cameras",
        json={
            "camera_name": "LP존 전경 1",
            "cabinet_name": "legacy-camera-key",
            "notes": "LP존 전체",
            "is_active": True,
        },
    )
    # Operator can access operational camera routes
    assert res.status_code != 403


def test_ops_placement_hint_models_include_owned_item_id():
    try:
        from app.schemas import OpsPlacementHintRecommendation, OpsPlacementHintRequest, OpsPlacementHintResponse
    except ImportError:
        from app.main import OpsPlacementHintRecommendation, OpsPlacementHintRequest, OpsPlacementHintResponse

    request = OpsPlacementHintRequest(owned_item_id=42)
    recommendation = OpsPlacementHintRecommendation(
        rank=1,
        storage_slot_id=17,
        slot_code="LP-01",
        slot_display_name="LP 1",
        reason_code="SAME_ARTIST",
        reason_message="같은 아티스트의 인접 배치 힌트입니다.",
    )
    response = OpsPlacementHintResponse(
        available=False,
        recommendations=[recommendation],
        fallback_reason="NO_HINTS",
        fallback_message="추천 가능한 위치를 찾지 못했습니다.",
    )

    assert request.owned_item_id == 42
    assert response.fallback_message == "추천 가능한 위치를 찾지 못했습니다."


def test_operator_can_post_ops_placement_hints_with_ready_payload(operator_client, monkeypatch):
    payload = {
        "available": True,
        "recommendations": [
            {
                "rank": 1,
                "storage_slot_id": 17,
                "slot_code": "LP-01",
                "slot_display_name": "LP 1",
                "reason_code": "SAME_ARTIST",
                "reason_message": "같은 아티스트의 인접 배치 힌트입니다.",
            },
            {
                "rank": 2,
                "storage_slot_id": 18,
                "slot_code": "LP-02",
                "slot_display_name": "LP 2",
                "reason_code": "ANCHOR_PATTERN",
                "reason_message": "기존 배치 순서를 잇는 앵커 패턴입니다.",
            },
        ],
        "fallback_reason": None,
        "fallback_message": None,
    }
    seen = {}

    def fake_build_ops_placement_hint_payload(owned_item_id: int):
        seen["owned_item_id"] = owned_item_id
        return payload

    import app.api.ops_system as ops_system_module
    monkeypatch.setattr(ops_system_module, "_build_ops_placement_hint_payload", fake_build_ops_placement_hint_payload)

    res = operator_client.post("/ops/placement-hints", json={"owned_item_id": 123})

    assert res.status_code == 200
    assert seen["owned_item_id"] == 123
    assert res.json() == payload


def test_operator_can_post_artist_context_with_available_payload(operator_client, monkeypatch):
    from app.services import artist_context as artist_context_service

    seen = {}

    monkeypatch.setattr(
        artist_context_service,
        "build_artist_context",
        lambda artist_name, category=None, locale=None: seen.update(
            {"artist_name": artist_name, "category": category, "locale": locale}
        ) or {
            "available": True,
            "artist_name": artist_name,
            "summary": "서울의 대표 아티스트",
            "summary_original": "Representative artist from Seoul",
            "image_url": "https://upload.wikimedia.org/artist.jpg",
            "country": "대한민국",
            "active_years": "1990-현재",
            "genres": ["록", "팝"],
            "links": [{"label": "Wikipedia", "url": "https://wikipedia.org"}],
        },
    )

    response = operator_client.post("/ops/artist-context", json={"artist_name": "어떤날", "category": "CD", "locale": "ko"})

    assert response.status_code == 200
    assert seen == {"artist_name": "어떤날", "category": "CD", "locale": "ko"}
    payload = response.json()
    assert payload["available"] is True
    assert payload["artist_name"] == "어떤날"
    assert payload["summary"] == "서울의 대표 아티스트"
    assert payload["summary_original"] == "Representative artist from Seoul"
    assert payload["image_url"] == "https://upload.wikimedia.org/artist.jpg"


def test_operator_can_post_artist_context_with_unavailable_payload(operator_client, monkeypatch):
    from app.services import artist_context as artist_context_service

    monkeypatch.setattr(
        artist_context_service,
        "build_artist_context",
        lambda artist_name, category=None, locale=None: {
            "available": False,
            "artist_name": artist_name,
            "summary": None,
            "summary_original": None,
            "image_url": None,
            "country": None,
            "active_years": None,
            "genres": [],
            "links": [{"label": "Discogs", "url": "https://discogs.com"}],
        },
    )

    response = operator_client.post("/ops/artist-context", json={"artist_name": "어떤날", "category": "LP"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is False
    assert payload["links"] == [{"label": "Discogs", "url": "https://discogs.com"}]


def test_operator_can_post_ops_placement_hints_with_unavailable_payload(operator_client, monkeypatch):
    payload = {
        "available": False,
        "recommendations": [],
        "fallback_reason": "NO_HINTS",
        "fallback_message": "추천 가능한 위치를 찾지 못했습니다.",
    }
    seen = {}

    def fake_build_ops_placement_hint_payload(owned_item_id: int):
        seen["owned_item_id"] = owned_item_id
        return payload

    import app.api.ops_system as ops_system_module
    monkeypatch.setattr(ops_system_module, "_build_ops_placement_hint_payload", fake_build_ops_placement_hint_payload)

    res = operator_client.post("/ops/placement-hints", json={"owned_item_id": 123})

    assert res.status_code == 200
    assert seen["owned_item_id"] == 123
    assert res.json()["available"] is False
    assert res.json()["fallback_message"] == "추천 가능한 위치를 찾지 못했습니다."


def test_operator_can_get_ops_owned_item_collector_info_for_discogs_item(operator_client, monkeypatch):
    owned_item_row = {
        "id": 101,
        "source_code": "DISCOGS",
        "source_external_id": "9876543",
    }

    def fake_get_owned_item_detail(owned_item_id: int):
        if int(owned_item_id) == 101:
            return owned_item_row
        return None

    def fake_collector_info(release_id: str, compare_limit: int = 12):
        assert release_id == "9876543"
        return {
            "formats": [" LP ", " 7\" Vinyl ", " LP "],
            "format_items": [
                {
                    "name": "Vinyl",
                    "descriptions": ["LP", "Album", "Stereo"],
                    "qty": "2",
                    "text": None,
                    "display": "Vinyl (LP, Album, Stereo) / qty 2",
                }
            ],
            "label_items": [
                {
                    "name": "Example Label",
                    "catno": "EX-123",
                }
            ],
            "title": "Example Album",
            "artist_or_brand": "Example Artist",
            "country": "  Korea ",
            "pressing_country": "JPN",
            "catalog_no": None,
            "barcode": "1234567890123",
            "disc_count": 2,
            "speed_rpm": 33,
            "runout_matrix": ["A1 ", " B2", "C3"],
            "other_versions": [{"external_id": "1"}, {"external_id": "2"}],
        }

    import app.api.misc_catalog as misc_catalog_module
    monkeypatch.setattr(main_module.db, "get_owned_item_detail", fake_get_owned_item_detail)
    monkeypatch.setattr(misc_catalog_module, "get_discogs_release_collector_info", fake_collector_info)

    res = operator_client.get("/ops/owned-items/101/collector-info")

    assert res.status_code == 200
    payload = res.json()
    assert payload["available"] is True
    assert payload["owned_item_id"] == 101
    assert payload["source_code"] == "DISCOGS"
    assert payload["source_external_id"] == "9876543"
    assert payload["release_title"] == "Example Album"
    assert payload["artist_or_brand"] == "Example Artist"
    assert payload["country"] == "Korea"
    assert payload["pressing_country"] == "JPN"
    assert payload["catalog_no"] == "EX-123"
    assert payload["label_name"] == "Example Label"
    assert payload["barcode"] == "1234567890123"
    assert payload["formats"] == ["LP", "7\" Vinyl"]
    assert payload["format_items"] == [
        {
            "name": "Vinyl",
            "descriptions": ["LP", "Album", "Stereo"],
            "qty": "2",
            "text": None,
            "display": "Vinyl (LP, Album, Stereo) / qty 2",
        }
    ]
    assert payload["disc_count"] == 2
    assert payload["speed_rpm"] == 33
    assert payload["runout_sample"] == "A1 | B2"
    assert payload["other_versions_count"] == 2
    assert payload["external_links"] == ["https://www.discogs.com/release/9876543"]
    assert payload["fallback_reason"] is None
    assert payload["fallback_message"] is None


def test_operator_gets_unavailable_ops_owned_item_collector_info_for_non_discogs_item(operator_client, monkeypatch):
    owned_item_row = {
        "id": 202,
        "source_code": "MANIADB",
        "source_external_id": "abc-123",
    }

    def fake_get_owned_item_detail(owned_item_id: int):
        if int(owned_item_id) == 202:
            return owned_item_row
        return None

    monkeypatch.setattr(main_module.db, "get_owned_item_detail", fake_get_owned_item_detail)

    res = operator_client.get("/ops/owned-items/202/collector-info")

    assert res.status_code == 200
    payload = res.json()
    assert payload["available"] is False
    assert payload["owned_item_id"] == 202
    assert payload["source_code"] == "MANIADB"
    assert payload["source_external_id"] == "abc-123"
    assert payload["fallback_reason"] == "UNSUPPORTED_SOURCE"
    assert payload["fallback_message"] == "collector info is available only for Discogs-linked items."


def test_discogs_release_collector_info_uses_plain_int_default_compare_limit(monkeypatch):
    def fake_snapshot(source: str, external_id: str):
        assert source == "DISCOGS"
        assert external_id == "9876543"
        return {
            "raw": {
                "title": "Example Album",
                "artists": [{"name": "Example Artist"}],
                "country": "Korea",
                "master_id": "12345",
                "formats": [{"name": "Vinyl", "qty": "1", "descriptions": ["LP"]}],
                "tracklist": [],
            },
            "disc_count": 1,
            "speed_rpm": 33,
            "released_date": "1989-01-01",
            "pressing_country": "Korea",
            "catalog_no": "EX-123",
            "barcode": "1234567890123",
            "track_list": [],
        }

    monkeypatch.setattr(main_module, "get_source_release_snapshot", fake_snapshot)
    monkeypatch.setattr(main_module, "_discogs_compare_variants", lambda **kwargs: [])

    payload = main_module.get_discogs_release_collector_info("9876543")

    assert payload["title"] == "Example Album"
    assert payload["artist_or_brand"] == "Example Artist"
    assert payload["catalog_no"] == "EX-123"


def test_parse_maniadb_release_legend_preserves_full_released_date():
    parsed = provider_module._parse_maniadb_release_legend(
        '<font color="black"><strong><a href="/album/153773?o=l&amp;s=1"><img src="http://i.maniadb.com/images/music_lp.gif" border="0" alt="LP"/></a> :: 2003-12-20 :: 리버맨 <span style="padding-left:10px">2LP + 7인치 싱글 3장</span></strong></font>',
        album_id="153773",
        album_artist="김두수",
        album_title="自由魂 [box]",
        block_html=None,
    )

    assert parsed is not None
    assert parsed["release_year"] == 2003
    assert parsed["released_date"] == "2003-12-20"


def test_parse_maniadb_release_legend_extracts_estimated_year_prefix():
    parsed = provider_module._parse_maniadb_release_legend(
        '<font color="black"><strong><a href="/album/125780?o=l&amp;s=2"><img src="http://i.maniadb.com/images/music_cd.gif" border="0" alt="CD"/></a> :: 1999 (추정) :: 굿 인터내셔널 (GI-3013, 8808513000379)</strong></font>',
        album_id="125780",
        album_artist="이성원",
        album_title="뒷문 밖에는 갈잎의 노래 / 이성원이 노래하는 아이들을 위한 옛동요",
        block_html=None,
    )

    assert parsed is not None
    assert parsed["release_year"] == 1999
    assert parsed["released_date"] is None
    assert parsed["catalog_no"] == "GI-3013"
    assert parsed["barcode"] == "8808513000379"


def test_get_source_release_snapshot_for_maniadb_uses_variant_released_date(monkeypatch):
    monkeypatch.setattr(
        provider_module,
        "get_maniadb_master_variants",
        lambda master_external_id, limit=30: [
            {
                "external_id": "153773:1",
                "title": "自由魂 [box]",
                "artist_or_brand": "김두수",
                "release_year": 2003,
                "released_date": "2003-12-20",
                "label_name": "리버맨",
            }
        ],
    )

    snapshot = provider_module.get_source_release_snapshot("MANIADB", "album:153773")

    assert snapshot is not None
    assert snapshot["release_year"] == 2003
    assert snapshot["released_date"] == "2003-12-20"


def test_filter_maniadb_candidates_keeps_variant_external_ids():
    narrowed = main_module._filter_maniadb_candidates(
        [
            {
                "source": "MANIADB",
                "external_id": "125780:1",
                "artist_or_brand": "이성원",
                "title": "뒷문 밖에는 갈잎의 노래 / 이성원이 노래하는 아이들을 위한 옛동요",
                "confidence": 0.75,
            },
            {
                "source": "MANIADB",
                "external_id": "125780:4",
                "artist_or_brand": "이성원",
                "title": "뒷문 밖에는 갈잎의 노래 / 이성원이 노래하는 아이들을 위한 옛동요",
                "confidence": 0.75,
            },
        ],
        artist_or_brand="이성원",
        title="뒷문 밖에는 갈잎의 노래",
    )

    assert [row["external_id"] for row in narrowed] == ["125780:1", "125780:4"]


def test_operator_office_climate_returns_home_assistant_snapshot(operator_client, monkeypatch):
    monkeypatch.setattr(
        main_module,
        "_load_operator_office_climate",
        lambda: {
            "available": True,
            "source": "home_assistant",
            "location_label": "상주 사무실",
            "description": "온/습도계",
            "temperature_c": 22.4,
            "humidity_percent": 48.0,
            "comfort_label": "쾌적",
            "updated_at": "2026-03-21T08:30:00+09:00",
        },
    )

    res = operator_client.get("/operator/office-climate")

    assert res.status_code == 200
    payload = res.json()
    assert payload["available"] is True
    assert payload["location_label"] == "상주 사무실"
    assert payload["description"] == "온/습도계"
    assert payload["temperature_c"] == 22.4
    assert payload["humidity_percent"] == 48.0
    assert payload["comfort_label"] == "쾌적"


def test_operator_office_climate_returns_cached_snapshot_when_home_assistant_fails(operator_client, monkeypatch):
    monkeypatch.setattr(
        main_module,
        "_OFFICE_CLIMATE_CACHE",
        {
            "available": True,
            "source": "home_assistant",
            "location_label": "상주 사무실",
            "description": "온/습도계",
            "temperature_c": 21.8,
            "humidity_percent": 51.0,
            "comfort_label": "쾌적",
            "updated_at": "2026-04-03T14:10:00+09:00",
        },
    )
    monkeypatch.setattr(main_module, "_load_operator_office_climate", lambda: (_ for _ in ()).throw(RuntimeError("502 bad gateway")))

    res = operator_client.get("/operator/office-climate")

    assert res.status_code == 200
    payload = res.json()
    assert payload["available"] is True
    assert payload["temperature_c"] == 21.8
    assert payload["humidity_percent"] == 51.0
    assert payload["updated_at"] == "2026-04-03T14:10:00+09:00"


def test_operator_office_climate_falls_back_to_seoul_weather_when_office_unavailable(operator_client, monkeypatch):
    monkeypatch.setattr(main_module, "_OFFICE_CLIMATE_CACHE", None)
    monkeypatch.setattr(main_module, "_SEOUL_WEATHER_CACHE", None)
    monkeypatch.setattr(main_module, "_load_operator_office_climate", lambda: (_ for _ in ()).throw(RuntimeError("sensor offline")))
    monkeypatch.setattr(
        main_module,
        "_load_operator_seoul_weather",
        lambda: {
            "available": True,
            "source": "seoul_weather",
            "location_label": "서울",
            "description": "",
            "temperature_c": 18.6,
            "humidity_percent": 57.0,
            "comfort_label": None,
            "temperature_high_c": 22.3,
            "temperature_low_c": 12.1,
            "weather_code": 3,
            "is_day": True,
            "updated_at": "2026-04-17T09:00:00+09:00",
        },
    )

    res = operator_client.get("/operator/office-climate")

    assert res.status_code == 200
    payload = res.json()
    assert payload["available"] is True
    assert payload["source"] == "seoul_weather"
    assert payload["location_label"] == "서울"
    assert payload["temperature_c"] == 18.6
    assert payload["temperature_high_c"] == 22.3
    assert payload["temperature_low_c"] == 12.1
    assert payload["weather_code"] == 3
    assert payload["is_day"] is True


def test_operator_catalog_search_includes_current_cabinet_triplet(operator_client, monkeypatch):
    def fake_search_operator_catalog(query_text: str, limit: int = 30):
        assert query_text == "산울림"
        assert limit == 5
        return [
            {
                "id": 17,
                "category": "LP",
                "format_name": "LP",
                "item_title": "제11집",
                "artist_or_brand": "산울림",
                "released_date": "1985-01-01",
                "pressing_country": "Korea",
                "label_name": "서울음반",
                "catalog_no": "JLS-120123",
                "barcode": "8800000000000",
                "format_items": [
                    {
                        "name": "Vinyl",
                        "descriptions": ["LP", "Album", "Stereo"],
                        "qty": "2",
                        "text": None,
                    }
                ],
                "runout_matrix": ["A1", "B2", "C3"],
                "cover_image_url": "https://example.com/cover.jpg",
                "signature_type": "NONE",
                "status": "IN_COLLECTION",
                "current_slot_code": "CAB-A-02-05",
                "current_slot_display_name": "A장 2열 5칸",
                "current_cabinet_name": "A장",
                "current_column_code": "02",
                "current_cell_code": "05",
                "previous_slot_code": "CAB-A-01-04",
                "previous_slot_display_name": "A장 1열 4칸",
                "created_at": "2026-04-01T13:18:00+00:00",
                "track_matches": ["청춘"],
                "matched_track_count": 1,
                "track_items": [],
                "track_list": ["청춘"],
            }
        ]

    monkeypatch.setattr(main_module.db, "search_operator_catalog", fake_search_operator_catalog)

    res = operator_client.get("/operator/catalog-search", params={"q": "산울림", "limit": 5})

    assert res.status_code == 200
    payload = res.json()
    assert payload["total_count"] == 1
    assert payload["items"][0]["current_cabinet_name"] == "A장"
    assert payload["items"][0]["current_column_code"] == "02"
    assert payload["items"][0]["current_cell_code"] == "05"
    assert payload["items"][0]["pressing_country"] == "Korea"
    assert payload["items"][0]["format_items"][0]["name"] == "Vinyl"
    assert payload["items"][0]["runout_sample"] == "A1 | B2"
    assert payload["items"][0]["created_at"] == "2026-04-01T13:18:00+00:00"


def test_ingest_search_maniadb_filters_title_false_positives_when_artist_field_is_used(admin_client, monkeypatch):
    def fake_search_music_metadata(*, barcode=None, query=None, category=None, source="AUTO", limit=5, artist_or_brand=None, title=None):
        assert barcode is None
        assert query == "어떤날"
        assert source == "MANIADB"
        assert limit == 5
        assert artist_or_brand == "어떤날"
        assert title is None
        return [
            {
                "source": "MANIADB",
                "external_id": "album:wrong-title",
                "title": "어떤날",
                "artist_or_brand": "다른 아티스트",
                "domain_code": "KOREA",
                "confidence": 0.81,
                "raw": {"kind": "album"},
            },
            {
                "source": "MANIADB",
                "external_id": "album:artist-match",
                "title": "출발",
                "artist_or_brand": "어떤날",
                "domain_code": "KOREA",
                "confidence": 0.88,
                "raw": {"kind": "album"},
            },
        ]

    monkeypatch.setattr(main_module, "search_music_metadata", fake_search_music_metadata)

    res = admin_client.post(
        "/ingest/search",
        json={
            "source": "MANIADB",
            "category": "CD",
            "artist_or_brand": "어떤날",
            "limit": 5,
        },
    )

    assert res.status_code == 200
    payload = res.json()
    assert payload["query"] == "어떤날"
    assert [item["external_id"] for item in payload["candidates"]] == ["album:artist-match"]


def test_ingest_search_maniadb_prefers_artist_and_title_match_when_both_fields_are_used(admin_client, monkeypatch):
    def fake_search_music_metadata(*, barcode=None, query=None, category=None, source="AUTO", limit=5, artist_or_brand=None, title=None):
        assert barcode is None
        assert query == "어떤날 출발"
        assert source == "MANIADB"
        assert limit == 5
        assert artist_or_brand == "어떤날"
        assert title == "출발"
        return [
            {
                "source": "MANIADB",
                "external_id": "album:title-only",
                "title": "출발",
                "artist_or_brand": "다른 아티스트",
                "domain_code": "KOREA",
                "confidence": 0.81,
                "raw": {"kind": "album"},
            },
            {
                "source": "MANIADB",
                "external_id": "album:artist-only",
                "title": "하늘",
                "artist_or_brand": "어떤날",
                "domain_code": "KOREA",
                "confidence": 0.82,
                "raw": {"kind": "album"},
            },
            {
                "source": "MANIADB",
                "external_id": "album:artist-and-title",
                "title": "출발",
                "artist_or_brand": "어떤날",
                "domain_code": "KOREA",
                "confidence": 0.9,
                "raw": {"kind": "album"},
            },
        ]

    monkeypatch.setattr(main_module, "search_music_metadata", fake_search_music_metadata)

    res = admin_client.post(
        "/ingest/search",
        json={
            "source": "MANIADB",
            "category": "CD",
            "artist_or_brand": "어떤날",
            "title": "출발",
            "limit": 5,
        },
    )

    assert res.status_code == 200
    payload = res.json()
    assert payload["query"] == "어떤날 출발"
    assert [item["external_id"] for item in payload["candidates"]] == ["album:artist-and-title"]


def test_ingest_search_maniadb_ranks_exact_artist_and_title_match_first(admin_client, monkeypatch):
    def fake_search_music_metadata(*, barcode=None, query=None, category=None, source="AUTO", limit=5, artist_or_brand=None, title=None):
        assert barcode is None
        assert query == "어떤날 출발"
        assert source == "MANIADB"
        assert limit == 5
        assert artist_or_brand == "어떤날"
        assert title == "출발"
        return [
            {
                "source": "MANIADB",
                "external_id": "album:artist-and-title-partial",
                "title": "출발 라이브",
                "artist_or_brand": "어떤날",
                "domain_code": "KOREA",
                "confidence": 0.91,
                "raw": {"kind": "album"},
            },
            {
                "source": "MANIADB",
                "external_id": "album:artist-and-title-exact",
                "title": "출발",
                "artist_or_brand": "어떤날",
                "domain_code": "KOREA",
                "confidence": 0.84,
                "raw": {"kind": "album"},
            },
        ]

    monkeypatch.setattr(main_module, "search_music_metadata", fake_search_music_metadata)

    res = admin_client.post(
        "/ingest/search",
        json={
            "source": "MANIADB",
            "category": "CD",
            "artist_or_brand": "어떤날",
            "title": "출발",
            "limit": 5,
        },
    )

    assert res.status_code == 200
    payload = res.json()
    assert [item["external_id"] for item in payload["candidates"]] == [
        "album:artist-and-title-exact",
        "album:artist-and-title-partial",
    ]


def test_ingest_search_maniadb_excludes_artist_candidates(admin_client, monkeypatch):
    def fake_search_music_metadata(*, barcode=None, query=None, category=None, source="AUTO", limit=5, artist_or_brand=None, title=None):
        assert barcode is None
        assert query == "곽성삼 곽성삼"
        assert source == "MANIADB"
        assert limit == 5
        assert artist_or_brand == "곽성삼"
        assert title == "곽성삼"
        return [
            {
                "source": "MANIADB",
                "external_id": "artist:100577",
                "title": "곽성삼",
                "artist_or_brand": "곽성삼",
                "confidence": 0.95,
                "raw": {"kind": "artist"},
            },
            {
                "source": "MANIADB",
                "external_id": "album:133577",
                "title": "길",
                "artist_or_brand": "곽성삼",
                "confidence": 0.88,
                "raw": {"kind": "album"},
            },
        ]

    monkeypatch.setattr(main_module, "search_music_metadata", fake_search_music_metadata)

    res = admin_client.post(
        "/ingest/search",
        json={
            "source": "MANIADB",
            "category": "LP",
            "artist_or_brand": "곽성삼",
            "title": "곽성삼",
            "limit": 5,
        },
    )

    assert res.status_code == 200
    payload = res.json()
    assert [item["external_id"] for item in payload["candidates"]] == ["album:133577"]


def test_ingest_search_maniadb_keeps_variant_release_candidates_with_cover_images(admin_client, monkeypatch):
    def fake_search_music_metadata(*, barcode=None, query=None, category=None, source="AUTO", limit=20, artist_or_brand=None, title=None):
        assert barcode is None
        assert query == "이무하 고향"
        assert source == "MANIADB"
        assert limit == 20
        assert artist_or_brand == "이무하"
        assert title == "고향"
        return [
            {
                "source": "MANIADB",
                "external_id": "artist:55321",
                "title": "이무하",
                "artist_or_brand": "이무하",
                "confidence": 0.91,
                "raw": {"kind": "artist"},
            },
            {
                "source": "MANIADB",
                "external_id": "127440:4",
                "title": "고향",
                "artist_or_brand": "이무하",
                "confidence": 0.92,
                "cover_image_url": "https://i.maniadb.com/images/album/127/127440_4_f.jpeg",
                "raw": {"kind": "album", "album_id": "127440", "release_seq": "4"},
            },
            {
                "source": "MANIADB",
                "external_id": "127440:2",
                "title": "고향",
                "artist_or_brand": "이무하",
                "confidence": 0.92,
                "cover_image_url": "https://i.maniadb.com/images/album/127/127440_2_f.jpg",
                "raw": {"kind": "album", "album_id": "127440", "release_seq": "2"},
            },
        ]

    monkeypatch.setattr(main_module, "search_music_metadata", fake_search_music_metadata)

    res = admin_client.post(
        "/ingest/search",
        json={
            "source": "MANIADB",
            "category": "LP",
            "artist_or_brand": "이무하",
            "title": "고향",
            "limit": 20,
        },
    )

    assert res.status_code == 200
    payload = res.json()
    assert [item["external_id"] for item in payload["candidates"]] == ["127440:4", "127440:2"]
    assert [item["cover_image_url"] for item in payload["candidates"]] == [
        "https://i.maniadb.com/images/album/127/127440_4_f.jpeg",
        "https://i.maniadb.com/images/album/127/127440_2_f.jpg",
    ]


def test_ingest_search_maniadb_retries_with_split_title_when_compound_title_has_no_match(admin_client, monkeypatch):
    seen: list[tuple[str | None, str | None, str | None]] = []

    def fake_search_music_metadata(*, barcode=None, query=None, category=None, source="AUTO", limit=20, artist_or_brand=None, title=None):
        assert barcode is None
        assert source == "MANIADB"
        assert limit == 20
        seen.append((query, artist_or_brand, title))
        if title == "휘장을 열고 / 새 날":
            return []
        if title == "새 날":
            return [
                {
                    "source": "MANIADB",
                    "external_id": "215240:1",
                    "title": "휘장을 열고 / 새 날",
                    "artist_or_brand": "이무하",
                    "confidence": 0.89,
                    "cover_image_url": "https://i.maniadb.com/images/album/215/215240_1_f.jpg",
                    "raw": {"kind": "album", "album_id": "215240", "release_seq": "1"},
                }
            ]
        return []

    monkeypatch.setattr(main_module, "search_music_metadata", fake_search_music_metadata)

    res = admin_client.post(
        "/ingest/search",
        json={
            "source": "MANIADB",
            "category": "CD",
            "artist_or_brand": "이무하",
            "title": "휘장을 열고 / 새 날",
            "limit": 20,
        },
    )

    assert res.status_code == 200
    payload = res.json()
    assert [item["external_id"] for item in payload["candidates"]] == ["215240:1"]
    assert payload["candidates"][0]["cover_image_url"] == "https://i.maniadb.com/images/album/215/215240_1_f.jpg"


def test_filter_maniadb_candidates_matches_artist_filter_against_alias_search_terms():
    narrowed = main_module._filter_maniadb_candidates(
        [
            {
                "source": "MANIADB",
                "external_id": "album:129004",
                "title": "Open The Door",
                "artist_or_brand": "Noizegarden",
                "confidence": 0.91,
                "raw": {"kind": "album", "artist_search_terms": ["노이즈가든", "Noizegarden"]},
            }
        ],
        artist_or_brand="노이즈가든",
        title=None,
    )

    assert [item["external_id"] for item in narrowed] == ["album:129004"]


def test_maniadb_search_retries_album_lookup_with_artist_aliases(monkeypatch):
    album_ko_html = '''
    <div class="artist">
      <a href="/album/129004" alt="노이즈가든 - Open The Door (1999, Banana)">노이즈가든 - Open The Door (1999, Banana)</a>
    </div>
    '''
    artist_html = '''
    <div class="artist"><a href="/artist/114429" alt="노이즈가든">노이즈가든</a>
      / Noizegarden / 남성그룹 / 1990s
    </div>
    '''
    album_alias_html = '''
    <div class="artist">
      <a href="/album/127004" alt="Noizegarden - 골든디럭스 제1집 : 영일만 친구 / 내마음 갈곳을 잃어 (1979, Oasis)">Noizegarden - 골든디럭스 제1집 : 영일만 친구 / 내마음 갈곳을 잃어 (1979, Oasis)</a>
    </div>
    <div class="artist">
      <a href="/album/133577" alt="Noizegarden - 길 (1992, Oasis)">Noizegarden - 길 (1992, Oasis)</a>
    </div>
    '''

    calls: list[tuple[str, str]] = []

    class DummyResponse:
        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self):
            return None

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, params=None):
            path = str(url)
            sr = str((params or {}).get("sr") or "")
            calls.append((path, sr))
            if "/search/%EB%85%B8%EC%9D%B4%EC%A6%88%EA%B0%80%EB%93%A0/" in path and sr == "L":
                return DummyResponse(album_ko_html)
            if "/search/%EB%85%B8%EC%9D%B4%EC%A6%88%EA%B0%80%EB%93%A0/" in path and sr == "P":
                return DummyResponse(artist_html)
            if "/search/Noizegarden/" in path and sr == "L":
                return DummyResponse(album_alias_html)
            raise AssertionError(f"unexpected request: {path} params={params}")

    monkeypatch.setattr(provider_module.httpx, "Client", DummyClient)
    monkeypatch.setattr(
        provider_module,
        "get_settings",
        lambda: SimpleNamespace(maniadb_base_url="http://www.maniadb.com"),
    )
    monkeypatch.setattr(
        provider_module,
        "get_maniadb_master_variants",
        lambda master_external_id, limit=30: [
            {
                "source": "MANIADB",
                "external_id": str(master_external_id),
                "title": {
                    "129004": "Open The Door",
                    "127004": "골든디럭스 제1집 : 영일만 친구 / 내마음 갈곳을 잃어",
                    "133577": "길",
                }.get(str(master_external_id), ""),
                "artist_or_brand": {
                    "129004": "노이즈가든",
                    "127004": "Noizegarden",
                    "133577": "Noizegarden",
                }.get(str(master_external_id), ""),
                "raw": {"kind": "album", "album_id": str(master_external_id)},
            }
        ],
    )

    rows = provider_module.search_maniadb_by_query("노이즈가든", limit=5)

    assert [item["external_id"] for item in rows[:3]] == ["129004", "127004", "133577"]
    assert any(item["external_id"] == "artist:114429" for item in rows)
    assert any(path.endswith("/search/Noizegarden/") and sr == "L" for path, sr in calls)


def test_ingest_search_accepts_musicbrainz_source(admin_client, monkeypatch):
    def fake_search_music_metadata(*, barcode=None, query=None, category=None, source="AUTO", limit=5):
        assert barcode is None
        assert query == "David Bowie"
        assert source == "MUSICBRAINZ"
        assert limit == 5
        return [
            {
                "source": "MUSICBRAINZ",
                "external_id": "mb-release-1",
                "title": "Heroes",
                "artist_or_brand": "David Bowie",
                "domain_code": "WESTERN",
                "confidence": 0.88,
                "raw": {},
            }
        ]

    monkeypatch.setattr(main_module, "search_music_metadata", fake_search_music_metadata)

    res = admin_client.post(
        "/ingest/search",
        json={
            "source": "MUSICBRAINZ",
            "category": "CD",
            "artist_or_brand": "David Bowie",
            "limit": 5,
        },
    )

    assert res.status_code == 200
    payload = res.json()
    assert payload["query"] == "David Bowie"
    assert [item["source"] for item in payload["candidates"]] == ["MUSICBRAINZ"]


def test_ingest_search_discogs_retries_with_artist_variation_when_initial_query_is_empty(admin_client, monkeypatch):
    calls: list[tuple[str, str]] = []

    def fake_search_music_metadata(*, barcode=None, query=None, category=None, source="AUTO", limit=5):
        assert barcode is None
        calls.append((str(source), str(query)))
        if str(source).upper() == "DISCOGS" and query == "Yun Seok Cheol Trio 나의 여름은 아직 안 끝났어":
            return [
                {
                    "source": "DISCOGS",
                    "external_id": "36614953",
                    "title": "나의 여름은 아직 안 끝났어",
                    "artist_or_brand": "Yun Seok Cheol Trio*",
                    "domain_code": "KOREA",
                    "confidence": 0.99,
                    "raw": {},
                }
            ]
        return []

    monkeypatch.setattr(main_module, "search_music_metadata", fake_search_music_metadata)
    monkeypatch.setattr(
        main_module,
        "search_discogs_artist_name_variations",
        lambda artist_name, limit=6, suppress_errors=True: ["윤석철 트리오", "Yun Seok Cheol Trio"],
        raising=False,
    )
    monkeypatch.setattr(main_module, "_annotate_owned_flags", lambda candidates: candidates)

    res = admin_client.post(
        "/ingest/search",
        json={
            "source": "DISCOGS",
            "category": "LP",
            "artist_or_brand": "윤석철 트리오",
            "title": "나의 여름은 아직 안 끝났어",
            "limit": 5,
        },
    )

    assert res.status_code == 200
    payload = res.json()
    assert payload["candidates"][0]["external_id"] == "36614953"
    assert ("DISCOGS", "윤석철 트리오 나의 여름은 아직 안 끝났어") in calls
    assert ("DISCOGS", "Yun Seok Cheol Trio 나의 여름은 아직 안 끝났어") in calls


def test_ingest_search_discogs_supports_direct_release_reference(admin_client, monkeypatch):
    monkeypatch.setattr(
        main_module,
        "get_source_release_snapshot",
        lambda source, external_id: {
            "artist_or_brand": "Yun Seok Cheol Trio",
            "release_year": 2024,
            "released_date": "2024-06-12",
            "format_name": "LP",
            "catalog_no": "MBMC-2216",
            "label_name": "BEATBALL MUSIC",
            "barcode": "8809114692216",
            "cover_image_url": "https://img.example/36614953.jpg",
            "track_list": ["나의 여름은 아직 안 끝났어"],
            "media_type": "Vinyl",
            "release_type": "ALBUM",
            "domain_code": "KOREA",
            "genres": ["Jazz"],
            "styles": ["Contemporary Jazz"],
            "raw": {"title": "나의 여름은 아직 안 끝났어", "country": "South Korea"},
        }
        if source == "DISCOGS" and external_id == "36614953"
        else None,
    )
    monkeypatch.setattr(main_module, "search_music_metadata", lambda **kwargs: (_ for _ in ()).throw(AssertionError("unexpected metadata search")))
    monkeypatch.setattr(main_module, "_annotate_owned_flags", lambda candidates: candidates)

    res = admin_client.post(
        "/ingest/search",
        json={
            "source": "DISCOGS",
            "category": "LP",
            "query": "release:36614953",
            "limit": 5,
        },
    )

    assert res.status_code == 200
    payload = res.json()
    assert payload["query"] == "release:36614953"
    assert [item["external_id"] for item in payload["candidates"]] == ["36614953"]


def test_provider_search_music_metadata_supports_explicit_musicbrainz_source(monkeypatch):
    monkeypatch.setattr(
        provider_module,
        "search_musicbrainz_by_query",
        lambda query, limit=5: [
            {
                "source": "MUSICBRAINZ",
                "external_id": "mb-release-1",
                "title": "Heroes",
                "artist_or_brand": "David Bowie",
                "confidence": 0.88,
            }
        ],
    )

    result = provider_module.search_music_metadata(query="David Bowie", source="MUSICBRAINZ", limit=5)

    assert [item["source"] for item in result] == ["MUSICBRAINZ"]
    assert [item["external_id"] for item in result] == ["mb-release-1"]


def test_provider_search_music_metadata_retries_discogs_with_artist_variations(monkeypatch):
    calls: list[str] = []

    def fake_search_discogs_by_query(query, limit=5):
        calls.append(str(query))
        if query == "Yun Seok Cheol Trio 나의 여름은 아직 안끝났어":
            return [
                {
                    "source": "DISCOGS",
                    "external_id": "36614953",
                    "title": "나의 여름은 아직 안 끝났어",
                    "artist_or_brand": "Yun Seok Cheol Trio*",
                    "confidence": 0.99,
                    "raw": {},
                }
            ]
        return []

    monkeypatch.setattr(provider_module, "search_discogs_by_query", fake_search_discogs_by_query)
    monkeypatch.setattr(
        provider_module,
        "search_discogs_artist_name_variations",
        lambda artist_name, limit=6, suppress_errors=True: ["윤석철 트리오", "Yun Seok Cheol Trio"],
    )

    result = provider_module.search_music_metadata(
        query="윤석철 트리오 나의 여름은 아직 안끝났어",
        source="DISCOGS",
        limit=5,
        artist_or_brand="윤석철 트리오",
        title="나의 여름은 아직 안끝났어",
    )

    assert [item["external_id"] for item in result] == ["36614953"]
    assert calls == [
        "윤석철 트리오 나의 여름은 아직 안끝났어",
        "Yun Seok Cheol Trio 나의 여름은 아직 안끝났어",
    ]


def test_provider_search_music_metadata_expands_maniadb_album_results_to_variants(monkeypatch):
    monkeypatch.setattr(
        provider_module,
        "_maniadb_search",
        lambda query, limit=5: [
            provider_module.Candidate(
                source="MANIADB",
                external_id="album:125780",
                title="뒷문 밖에는 갈잎의 노래 / 이성원이 노래하는 아이들을 위한 옛동요",
                artist_or_brand="이성원",
                release_year=1996,
                country="KR",
                format_name="CD",
                barcode=None,
                catalog_no=None,
                label_name=None,
                cover_image_url=None,
                track_list=[],
                confidence=0.756,
                raw={"kind": "album", "album_id": "125780"},
            )
        ],
    )
    monkeypatch.setattr(
        provider_module,
        "get_maniadb_master_variants",
        lambda master_external_id, limit=30: [
            {
                "source": "MANIADB",
                "external_id": "125780:1",
                "title": "뒷문 밖에는 갈잎의 노래 / 이성원이 노래하는 아이들을 위한 옛동요",
                "artist_or_brand": "이성원",
                "release_year": 1996,
                "released_date": None,
                "country": "KR",
                "format_name": "CD",
                "label_name": "굿 인터내셔널",
                "catalog_no": "HD-2184",
                "barcode": "8808513000379",
                "cover_image_url": "https://i.maniadb.com/images/album/125/125780_2_f.jpg",
                "track_list": [],
                "image_items": [{"type": "앞면", "uri": "https://i.maniadb.com/images/album/125/125780_2_f.jpg"}],
                "confidence": 0.0,
                "raw": {"album_id": "125780", "release_seq": "1"},
            },
            {
                "source": "MANIADB",
                "external_id": "125780:2",
                "title": "뒷문 밖에는 갈잎의 노래 / 이성원이 노래하는 아이들을 위한 옛동요",
                "artist_or_brand": "이성원",
                "release_year": 1999,
                "released_date": None,
                "country": "KR",
                "format_name": "CD",
                "label_name": "굿 인터내셔널",
                "catalog_no": "GI-3013",
                "barcode": "8808513000379",
                "cover_image_url": "https://i.maniadb.com/images/album/125/125780_2_f.jpg",
                "track_list": [],
                "image_items": [{"type": "앞면", "uri": "https://i.maniadb.com/images/album/125/125780_2_f.jpg"}],
                "confidence": 0.0,
                "raw": {"album_id": "125780", "release_seq": "2"},
            },
            {
                "source": "MANIADB",
                "external_id": "125780:3",
                "title": "뒷문 밖에는 갈잎의 노래 / 이성원이 노래하는 아이들을 위한 옛동요",
                "artist_or_brand": "이성원",
                "release_year": None,
                "released_date": None,
                "country": "KR",
                "format_name": "CD",
                "label_name": "굿 인터내셔널",
                "catalog_no": "GOOD-3013",
                "barcode": "8808513000379",
                "cover_image_url": "https://i.maniadb.com/images/album/125/125780_3_f.jpg",
                "track_list": [],
                "image_items": [{"type": "앞면", "uri": "https://i.maniadb.com/images/album/125/125780_3_f.jpg"}],
                "confidence": 0.0,
                "raw": {"album_id": "125780", "release_seq": "3"},
            },
            {
                "source": "MANIADB",
                "external_id": "125780:4",
                "title": "뒷문 밖에는 갈잎의 노래 / 이성원이 노래하는 아이들을 위한 옛동요",
                "artist_or_brand": "이성원",
                "release_year": 2022,
                "released_date": "2022-05-20",
                "country": "KR",
                "format_name": "LP",
                "label_name": "굿 인터내셔널",
                "catalog_no": None,
                "barcode": "8808513882272",
                "cover_image_url": "https://i.maniadb.com/images/album/125/125780_4_f.jpg",
                "track_list": [],
                "image_items": [{"type": "앞면", "uri": "https://i.maniadb.com/images/album/125/125780_4_f.jpg"}],
                "confidence": 0.0,
                "raw": {"album_id": "125780", "release_seq": "4"},
            },
        ],
    )

    result = provider_module.search_music_metadata(
        query="이성원 뒷문 밖에는 갈잎의 노래",
        category="LP",
        source="MANIADB",
        limit=10,
    )

    assert [item["external_id"] for item in result] == ["125780:1", "125780:2", "125780:3", "125780:4"]
    assert result[0]["label_name"] == "굿 인터내셔널"
    assert result[0]["catalog_no"] == "HD-2184"
    assert result[1]["catalog_no"] == "GI-3013"
    assert result[2]["catalog_no"] == "GOOD-3013"
    assert result[3]["format_name"] == "LP"
    assert result[3]["barcode"] == "8808513882272"


def test_provider_search_album_master_candidates_retries_discogs_with_artist_variations(monkeypatch):
    calls: list[str] = []

    def fake_search_discogs_master_by_query(query, limit=10):
        calls.append(str(query))
        if query == "Yun Seok Cheol Trio 나의 여름은 아직 안끝났어":
            return [
                {
                    "source": "DISCOGS",
                    "master_external_id": "3123456",
                    "title": "나의 여름은 아직 안 끝났어",
                    "artist_or_brand": "Yun Seok Cheol Trio",
                    "confidence": 0.98,
                    "raw": {},
                }
            ]
        return []

    monkeypatch.setattr(provider_module, "search_discogs_master_by_query", fake_search_discogs_master_by_query)
    monkeypatch.setattr(
        provider_module,
        "search_discogs_artist_name_variations",
        lambda artist_name, limit=6, suppress_errors=True: ["윤석철 트리오", "Yun Seok Cheol Trio"],
    )
    monkeypatch.setattr(provider_module, "_get_album_master_candidate_preview", lambda source, master_external_id: None)

    result = provider_module.search_album_master_candidates(
        query="윤석철 트리오 나의 여름은 아직 안끝났어",
        source="DISCOGS",
        limit=10,
        artist_or_brand="윤석철 트리오",
        title="나의 여름은 아직 안끝났어",
    )

    assert [item["master_external_id"] for item in result] == ["3123456"]
    assert calls == [
        "윤석철 트리오 나의 여름은 아직 안끝났어",
        "Yun Seok Cheol Trio 나의 여름은 아직 안끝났어",
    ]


def test_admin_can_create_goods_item_without_mappings(admin_client):
    res = admin_client.post(
        "/goods-items",
        json={
            "category": "POSTER",
            "goods_name": "독립 포스터",
            "quantity": 1,
            "status": "ACTIVE",
        },
    )

    assert res.status_code == 200
    payload = res.json()
    assert payload["goods_name"] == "독립 포스터"
    assert payload["artist_mappings"] == []
    assert payload["album_master_mappings"] == []
    assert payload["label_mappings"] == []


def test_goods_items_search_returns_unlinked_goods(admin_client):
    created = admin_client.post(
        "/goods-items",
        json={
            "category": "HAT",
            "goods_name": "무연계 모자",
            "quantity": 1,
            "status": "ACTIVE",
        },
    )
    assert created.status_code == 200

    res = admin_client.get("/goods-items", params={"q": "모자", "linked_state": "UNLINKED"})

    assert res.status_code == 200
    payload = res.json()
    assert payload["items"][0]["goods_name"] == "무연계 모자"


def test_ebay_purchase_preview_parses_search_fields_and_condition_pair_from_listing_title():
    raw_html = """
    <div class="m-item-card">
      <h3 class="title-heading">Grand Funk - We're An American Band 1973 USA Orig. LP Gold Rec. G/VG+</h3>
      <div class="container-item-col__info-item-info-additionalPrice">US $19.99</div>
      <a href="/usr/example-seller">example-seller</a>
      <a href="/itm/1234567890">item</a>
      <img src="https://example.com/grandfunk.jpg" />
    </div>
    """

    items = main_module._purchase_preview_items_from_ebay_html(raw_html, purchase_date="2026-03-31")

    assert len(items) == 1
    item = items[0]
    assert item.artist_name == "Grand Funk"
    assert item.item_name == "We're An American Band 1973 USA"
    assert item.raw_payload["listing_title"] == "Grand Funk - We're An American Band 1973 USA Orig. LP Gold Rec. G/VG+"
    assert item.raw_payload["parsed_cover_condition"] == "G"
    assert item.raw_payload["parsed_disc_condition"] == "VG+"


def test_purchase_import_build_owned_item_uses_parsed_condition_pair_from_queue_row():
    payload = main_module._build_owned_item_from_purchase_queue_row(
        {
            "id": 9,
            "artist_name": "Grand Funk",
            "item_name": "We're An American Band 1973 USA",
            "media_format": "LP",
            "quantity": 1,
            "unit_price": 19.99,
            "currency_code": "USD",
            "purchase_date": "2026-03-31",
            "seller_name": "EBAY",
            "raw_payload": {
                "parsed_cover_condition": "G",
                "parsed_disc_condition": "VG+",
            },
        }
    )

    assert payload.music_detail is not None
    assert payload.music_detail.cover_condition == "G"
    assert payload.music_detail.disc_condition == "VG+"


def test_purchase_import_rows_for_save_defaults_blank_media_to_cd_for_aladin_and_yes24():
    items = [
        main_module.PurchaseImportPreviewItem(
            row_no=1,
            artist_name="여러 아티스트",
            item_name="유리화 Vol. 2 - O.S.T.",
            media_format=None,
            quantity=1,
            unit_price=2600,
            line_total=2600,
            currency_code="KRW",
            purchase_date="2008-10-16",
            raw_line="유리화 Vol. 2 - O.S.T.",
            raw_payload={},
        )
    ]

    aladin_rows = main_module._purchase_import_rows_for_save(items, vendor_code="ALADIN", email_from=None)
    yes24_rows = main_module._purchase_import_rows_for_save(items, vendor_code="YES24", email_from=None)

    assert aladin_rows[0]["media_format"] == "CD"
    assert yes24_rows[0]["media_format"] == "CD"


def test_purchase_import_build_owned_item_defaults_blank_aladin_media_to_cd():
    payload = main_module._build_owned_item_from_purchase_queue_row(
        {
            "id": 809,
            "vendor_code": "ALADIN",
            "artist_name": "여러 아티스트 (Various Artists)",
            "item_name": "유리화 Vol. 2 - O.S.T.",
            "media_format": None,
            "quantity": 1,
            "unit_price": 2600,
            "currency_code": "KRW",
            "purchase_date": "2008-10-16",
            "seller_name": "ALADIN",
            "raw_payload": {},
        }
    )

    assert payload.category == "CD"
    assert payload.size_group == "STD"
    assert payload.music_detail is not None
    assert payload.music_detail.format_name == "CD"


def test_purchase_import_preview_accepts_cp949_ebay_html_via_base64_upload_payload():
    raw_html = """
    <div class="m-item-card">
      <h3 class="title-heading">김윤아 - 유리가면 1997 Korea LP NM/VG+</h3>
      <div class="container-item-col__info-item-info-additionalPrice">US $19.99</div>
      <a href="/usr/example-seller">example-seller</a>
      <a href="/itm/1234567890">item</a>
      <img src="https://example.com/kimyuna.jpg" />
    </div>
    """.strip()
    payload = main_module.PurchaseImportPreviewRequest(
        raw_content=None,
        raw_content_base64=base64.b64encode(raw_html.encode("cp949")).decode("ascii"),
        source_filename="ebay-order.html",
        vendor_code="EBAY",
    )

    items = main_module._parse_purchase_import_preview(payload)

    assert len(items) == 1
    assert items[0].artist_name == "김윤아"
    assert items[0].item_name == "유리가면 1997 Korea"


def test_ebay_purchase_preview_parses_artist_quoted_title_pattern():
    raw_html = """
    <div class="m-item-card">
      <h3 class="title-heading">Emerson, Lake & Palmer "Brain Salad Surgery" 1973 USA Orig. LP VG+/VG+</h3>
      <div class="container-item-col__info-item-info-additionalPrice">US $24.99</div>
      <a href="/usr/example-seller">example-seller</a>
      <a href="/itm/1234567890">item</a>
      <img src="https://example.com/elp.jpg" />
    </div>
    """

    items = main_module._purchase_preview_items_from_ebay_html(raw_html, purchase_date="2026-03-31")

    assert len(items) == 1
    item = items[0]
    assert item.artist_name == "Emerson, Lake & Palmer"
    assert item.item_name == "Brain Salad Surgery 1973 USA"
    assert item.raw_payload["parsed_cover_condition"] == "VG+"
    assert item.raw_payload["parsed_disc_condition"] == "VG+"


def test_purchase_import_queue_item_prefers_clean_item_name_over_garbled_raw_line_for_ebay():
    item = main_module._purchase_queue_item_from_row(
        {
            "id": 228,
            "vendor_code": "EBAY",
            "source_type": "FILE_UPLOAD",
            "item_name": "Paul McCartney - McCartney 1970 USA Gatefold LP G/G",
            "artist_name": None,
            "raw_line": "���������(��������� ������): 5��� 18��� ��� - 5��� 21��� ��� ������ ������ 6��� 17������ ������ ������ ������. Paul McCartney - McCartney 1970 USA Gatefold LP G/G",
            "raw_payload": {},
            "queue_status": "PENDING",
            "quantity": 1,
            "unit_price": 3.80,
            "line_total": 3.80,
            "currency_code": "USD",
            "purchase_date": "2026-05-21",
            "seller_name": "123davie39",
            "item_url": None,
            "image_url": None,
            "source_ref": None,
            "email_from": None,
            "email_subject": None,
            "linked_owned_item_id": None,
            "created_at": "2026-03-31T00:00:00+00:00",
            "updated_at": "2026-03-31T00:00:00+00:00",
        }
    )

    assert item.artist_name == "Paul McCartney"
    assert item.item_name == "Paul McCartney - McCartney 1970 USA Gatefold LP G/G"
    assert item.raw_payload["parsed_search_artist_name"] == "Paul McCartney"
    assert item.raw_payload["parsed_search_item_name"] == "McCartney 1970 USA Gatefold"


def test_purchase_queue_candidate_query_prefers_parsed_search_fields_for_ebay():
    query = main_module._purchase_queue_candidate_query(
        {
            "vendor_code": "EBAY",
            "artist_name": "The Dregs",
            "item_name": 'The Dregs "Industry Standard" 1982 Rock LP, Nice VG++!, Original Arista Pressing',
            "raw_payload": {
                "parsed_search_artist_name": "The Dregs",
                "parsed_search_item_name": "Industry Standard 1982 Rock",
            },
        }
    )

    assert query == "The Dregs Industry Standard 1982 Rock"


def test_purchase_import_list_accepts_yes24_vendor_rows(admin_client, monkeypatch):
    monkeypatch.setattr(
        main_module.db,
        "list_purchase_import_rows",
        lambda **kwargs: [
            {
                "id": 816,
                "vendor_code": "YES24",
                "source_type": "FILE_UPLOAD",
                "source_ref": "debug-http",
                "email_from": None,
                "email_subject": None,
                "artist_name": "윤석철 트리오",
                "item_name": "나의 여름은 아직 안끝났어",
                "media_format": "LP",
                "quantity": 1,
                "unit_price": None,
                "line_total": None,
                "currency_code": None,
                "purchase_date": None,
                "seller_name": None,
                "item_url": None,
                "image_url": None,
                "raw_line": None,
                "queue_status": "PENDING",
                "linked_owned_item_id": None,
                "created_at": "2026-04-13T15:11:02.128993+00:00",
                "updated_at": "2026-04-13T15:11:02.128993+00:00",
                "raw_payload": {},
            }
        ],
    )
    monkeypatch.setattr(main_module.db, "count_purchase_import_rows", lambda **kwargs: 1)

    res = admin_client.get("/purchase-imports", params={"queue_status": "PENDING", "limit": 5})

    assert res.status_code == 200
    payload = res.json()
    assert payload["total_count"] == 1
    assert payload["items"][0]["vendor_code"] == "YES24"


def test_purchase_import_candidates_accept_yes24_queue_item_vendor(admin_client, monkeypatch):
    row = {
        "id": 816,
        "vendor_code": "YES24",
        "source_type": "FILE_UPLOAD",
        "source_ref": "debug-http",
        "email_from": None,
        "email_subject": None,
        "artist_name": "윤석철 트리오",
        "item_name": "나의 여름은 아직 안끝났어",
        "media_format": "LP",
        "quantity": 1,
        "unit_price": None,
        "line_total": None,
        "currency_code": None,
        "purchase_date": None,
        "seller_name": None,
        "item_url": None,
        "image_url": None,
        "raw_line": None,
        "queue_status": "PENDING",
        "linked_owned_item_id": None,
        "created_at": "2026-04-13T15:11:02.128993+00:00",
        "updated_at": "2026-04-13T15:11:02.128993+00:00",
        "raw_payload": {},
    }
    monkeypatch.setattr(main_module.db, "get_purchase_import_row", lambda queue_id: dict(row) if queue_id == 816 else None)
    monkeypatch.setattr(
        main_module,
        "search_music_metadata",
        lambda **kwargs: [
            {
                "source": "DISCOGS",
                "external_id": "36614953",
                "title": "나의 여름은 아직 안 끝났어",
                "artist_or_brand": "Yun Seok Cheol Trio*",
                "release_year": 2024,
                "confidence": 0.99,
                "raw": {},
            }
        ],
    )
    monkeypatch.setattr(main_module, "_annotate_owned_flags", lambda candidates: candidates)

    res = admin_client.get(
        "/purchase-imports/816/candidates",
        params={
            "source": "DISCOGS",
            "limit": 5,
            "artist_name": "윤석철 트리오",
            "item_name": "나의 여름은 아직 안끝났어",
        },
    )

    assert res.status_code == 200
    payload = res.json()
    assert payload["queue_item"]["vendor_code"] == "YES24"
    assert payload["candidates"][0]["external_id"] == "36614953"


def test_purchase_import_candidates_default_blank_aladin_media_to_cd(admin_client, monkeypatch):
    row = {
        "id": 809,
        "vendor_code": "ALADIN",
        "source_type": "FILE_UPLOAD",
        "source_ref": "aladdin.mhtml",
        "email_from": None,
        "email_subject": None,
        "artist_name": "여러 아티스트 (Various Artists)",
        "item_name": "유리화 Vol. 2 - O.S.T.",
        "media_format": None,
        "quantity": 1,
        "unit_price": 2600,
        "line_total": 2600,
        "currency_code": "KRW",
        "purchase_date": "2008-10-16",
        "seller_name": "ALADIN",
        "item_url": None,
        "image_url": None,
        "raw_line": None,
        "queue_status": "PENDING",
        "linked_owned_item_id": None,
        "created_at": "2026-04-13T15:11:02.128993+00:00",
        "updated_at": "2026-04-13T15:11:02.128993+00:00",
        "raw_payload": {},
    }
    captured: dict[str, object] = {}

    monkeypatch.setattr(main_module.db, "get_purchase_import_row", lambda queue_id: dict(row) if queue_id == 809 else None)

    def fake_search_music_metadata(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(main_module, "search_music_metadata", fake_search_music_metadata)
    monkeypatch.setattr(main_module, "_annotate_owned_flags", lambda candidates: candidates)

    res = admin_client.get(
        "/purchase-imports/809/candidates",
        params={"source": "MANIADB", "limit": 5},
    )

    assert res.status_code == 200
    assert captured["category"] == "CD"


def test_purchase_import_candidates_maniadb_exclude_artist_candidates(admin_client, monkeypatch):
    row = {
        "id": 816,
        "vendor_code": "YES24",
        "source_type": "FILE_UPLOAD",
        "source_ref": "yes24.mhtml",
        "email_from": None,
        "email_subject": None,
        "artist_name": "곽성삼",
        "item_name": "곽성삼",
        "media_format": "LP",
        "quantity": 1,
        "unit_price": None,
        "line_total": None,
        "currency_code": None,
        "purchase_date": None,
        "seller_name": None,
        "item_url": None,
        "image_url": None,
        "raw_line": None,
        "queue_status": "PENDING",
        "linked_owned_item_id": None,
        "created_at": "2026-04-13T15:11:02.128993+00:00",
        "updated_at": "2026-04-13T15:11:02.128993+00:00",
        "raw_payload": {},
    }
    monkeypatch.setattr(main_module.db, "get_purchase_import_row", lambda queue_id: dict(row) if queue_id == 816 else None)
    monkeypatch.setattr(
        main_module,
        "search_music_metadata",
        lambda **kwargs: [
            {
                "source": "MANIADB",
                "external_id": "artist:100577",
                "title": "곽성삼",
                "artist_or_brand": "곽성삼",
                "confidence": 0.95,
                "raw": {"kind": "artist"},
            },
            {
                "source": "MANIADB",
                "external_id": "album:133577",
                "title": "길",
                "artist_or_brand": "곽성삼",
                "confidence": 0.88,
                "raw": {"kind": "album"},
            },
        ],
    )
    monkeypatch.setattr(main_module, "_annotate_owned_flags", lambda candidates: candidates)

    res = admin_client.get(
        "/purchase-imports/816/candidates",
        params={
            "source": "MANIADB",
            "limit": 5,
            "artist_name": "곽성삼",
            "item_name": "곽성삼",
        },
    )

    assert res.status_code == 200
    payload = res.json()
    assert [item["external_id"] for item in payload["candidates"]] == ["album:133577"]


def test_purchase_import_ignore_rejects_non_pending_rows(admin_client, monkeypatch):
    row = {
        "id": 814,
        "queue_status": "CREATED",
        "linked_owned_item_id": 1244,
    }
    monkeypatch.setattr(main_module.db, "get_purchase_import_row", lambda queue_id: dict(row) if queue_id == 814 else None)

    def fail_update_purchase_import_row(*args, **kwargs):
        raise AssertionError("update should not run for non-pending rows")

    monkeypatch.setattr(main_module.db, "update_purchase_import_row", fail_update_purchase_import_row)

    res = admin_client.post("/purchase-imports/814/ignore")

    assert res.status_code == 400
    assert res.json() == {"detail": "purchase import row is not pending"}


def test_search_lookup_metadata_candidates_forwards_artist_and_title_to_provider(monkeypatch):
    captured: dict[str, object] = {}

    def fake_search_music_metadata(**kwargs):
        captured.update(kwargs)
        return [
            {
                "source": "MANIADB",
                "external_id": "album:1058176",
                "title": "나의 여름은 아직 안 끝났어",
                "artist_or_brand": "윤석철 트리오",
            }
        ]

    monkeypatch.setattr(main_module, "search_music_metadata", fake_search_music_metadata)

    rows = main_module._search_lookup_metadata_candidates(
        query="윤석철 트리오 나의 여름은 아직 안끝났어",
        category="CD",
        source="AUTO",
        limit=5,
        artist_or_brand="윤석철 트리오",
        title="나의 여름은 아직 안끝났어",
    )

    assert rows[0]["source"] == "MANIADB"
    assert captured["artist_or_brand"] == "윤석철 트리오"
    assert captured["title"] == "나의 여름은 아직 안끝났어"


def test_normalize_maniadb_image_url_upgrades_http_to_https():
    url = provider_module._normalize_maniadb_image_url("http://i.maniadb.com/images/album/105/1058176_1_f.jpg")

    assert url == "https://i.maniadb.com/images/album/105/1058176_1_f.jpg"


def test_normalize_maniadb_image_url_preserves_zero_padded_variant_path():
    url = provider_module._normalize_maniadb_image_url(
        "http://i.maniadb.com/images/album/153/153773_01_f.jpg",
        album_id="153773",
        variant_seq="1",
    )

    assert url == "https://i.maniadb.com/images/album/153/153773_01_f.jpg"


def test_parse_maniadb_release_legend_keeps_zero_padded_cover_path():
    parsed = provider_module._parse_maniadb_release_legend(
        '<font color="black"><strong><a href="/album/153773?o=l&amp;s=1"><img src="http://i.maniadb.com/images/music_lp.gif" border="0" alt="LP"/></a> :: 2003-12-20 :: 리버맨</strong></font>',
        album_id="153773",
        album_artist="김두수",
        album_title="自由魂 [box]",
        block_html="""
        <div class="album-track-list">
          <img src="http://i.maniadb.com/images/album/153/153773_01_f.jpg" />
          <img src="http://i.maniadb.com/images/album/153/153773_01_b.jpg" />
        </div>
        """,
    )

    assert parsed is not None
    assert parsed["cover_image_url"] == "https://i.maniadb.com/images/album/153/153773_01_f.jpg"
    assert parsed["image_items"][0]["uri"] == "https://i.maniadb.com/images/album/153/153773_01_f.jpg"
    assert parsed["image_items"][1]["uri"] == "https://i.maniadb.com/images/album/153/153773_01_b.jpg"


def test_parse_maniadb_release_legend_keeps_legacy_variant_cover_path_order():
    parsed = provider_module._parse_maniadb_release_legend(
        '<font color="black"><strong><a href="/album/153773?o=l&amp;s=1"><img src="http://i.maniadb.com/images/music_lp.gif" border="0" alt="LP"/></a> :: 2003-12-20 :: 리버맨</strong></font>',
        album_id="153773",
        album_artist="김두수",
        album_title="自由魂 [box]",
        block_html="""
        <div class="album-track-list">
          <img src="http://i.maniadb.com/images/album/153/153773_f_1.jpg" />
          <img src="http://i.maniadb.com/images/album/153/153773_b_1.jpg" />
        </div>
        """,
    )

    assert parsed is not None
    assert parsed["cover_image_url"] == "https://i.maniadb.com/images/album/153/153773_f_1.jpg"
    assert parsed["image_items"][0]["uri"] == "https://i.maniadb.com/images/album/153/153773_f_1.jpg"
    assert parsed["image_items"][1]["uri"] == "https://i.maniadb.com/images/album/153/153773_b_1.jpg"


def test_maniadb_variant_cover_url_uses_split_group_for_seven_digit_album_ids():
    url = provider_module._maniadb_variant_cover_url("1028570", "1", "f")

    assert url == "https://i.maniadb.com/images/album/1028/028570_1_f.jpg"


def test_maniadb_variant_image_matches_accepts_split_group_tail_path():
    matched = provider_module._maniadb_variant_image_matches(
        "https://i.maniadb.com/images/album/1028/028570_1_f.jpg",
        album_id="1028570",
        variant_seq="1",
    )

    assert matched is True


def test_parse_maniadb_release_legend_keeps_split_group_cover_path():
    parsed = provider_module._parse_maniadb_release_legend(
        '<font color="black"><strong><a href="/album/1028570?o=l&amp;s=1"><img src="http://i.maniadb.com/images/music_digital.gif" border="0" alt="DIGITAL"/></a> :: 2023-11-27 :: 금반지레코드, 포크라노스</strong></font>',
        album_id="1028570",
        album_artist="정밀아",
        album_title="리버사이드",
        block_html="""
        <div class="album-track-list">
          <img src="http://i.maniadb.com/images/album/1028/028570_1_f.jpg" />
        </div>
        """,
    )

    assert parsed is not None
    assert parsed["cover_image_url"] == "https://i.maniadb.com/images/album/1028/028570_1_f.jpg"
    assert parsed["image_items"][0]["uri"] == "https://i.maniadb.com/images/album/1028/028570_1_f.jpg"


def test_get_maniadb_master_variants_fallback_uses_album_page_cover_image(monkeypatch):
    album_html = """
    <html>
      <head>
        <meta name="keyword" content="디오니서스 1집 - Legend Of Darkness (1989), music" />
        <meta property="og:image" content="http://i.maniadb.com/images/album/100/100483_1_f.jpg" />
      </head>
      <body>
        <div class="album-artist"><a href="/artist/103438">디오니서스</a></div>
        <div class="album-title">디오니서스 1집 - Legend Of Darkness</div>
        <div id="COVERART_FRONT">
          <a href="http://i.maniadb.com/images/album/100/100483_1_f.jpg">
            <img src="http://i.maniadb.com/images/album_t/260/100/100483_1_f.jpg" />
          </a>
        </div>
      </body>
    </html>
    """

    class DummyResponse:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return None

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, params=None):
            assert url.endswith("/album/100483")
            assert params == {"o": "l", "s": 0}
            return DummyResponse(album_html)

    monkeypatch.setattr(provider_module.httpx, "Client", DummyClient)
    monkeypatch.setattr(
        provider_module,
        "get_settings",
        lambda: SimpleNamespace(maniadb_base_url="http://www.maniadb.com"),
    )

    rows = provider_module.get_maniadb_master_variants("100483", limit=1)

    assert len(rows) == 1
    assert rows[0]["external_id"] == "100483"
    assert rows[0]["title"] == "Legend Of Darkness"
    assert rows[0]["artist_or_brand"] == "디오니서스"
    assert rows[0]["cover_image_url"] == "https://i.maniadb.com/images/album/100/100483_1_f.jpg"


def test_parse_maniadb_release_legend_falls_back_to_album_page_cover_when_variant_images_missing():
    parsed = provider_module._parse_maniadb_release_legend(
        '<font color="black"><strong><a href="/album/133577?o=l&amp;s=2"><img src="http://i.maniadb.com/images/music_cd.gif" border="0" alt="CD"/></a> :: 1992-05-01 :: 오아시스레코드</strong></font>',
        album_id="133577",
        album_artist="곽성삼",
        album_title="길",
        block_html="""
        <div class="album-track-list">
          <img src="http://i.maniadb.com/images/player_d.gif" />
        </div>
        """,
        album_cover_image_url="https://i.maniadb.com/images/album/133/133577_f.jpg",
    )

    assert parsed is not None
    assert parsed["cover_image_url"] == "https://i.maniadb.com/images/album/133/133577_f.jpg"
    assert parsed["image_items"][0]["uri"] == "https://i.maniadb.com/images/album/133/133577_f.jpg"


def test_discogs_variation_fallback_skips_artist_only_false_positives_until_title_match(monkeypatch):
    monkeypatch.setattr(
        provider_module,
        "search_discogs_artist_name_variations",
        lambda artist_name, limit=6, suppress_errors=True: ["윤석철 트리오", "Yun Seok Cheol Trio"],
    )

    def fake_search_discogs_by_query(query, limit=10):
        normalized = str(query or "").strip()
        if normalized == "윤석철 트리오":
            return [
                {
                    "source": "DISCOGS",
                    "external_id": "24408149",
                    "title": "LIBRARIES",
                    "artist_or_brand": "윤석철 트리오",
                    "confidence": 0.75,
                }
            ]
        if normalized == "Yun Seok Cheol Trio":
            return [
                {
                    "source": "DISCOGS",
                    "external_id": "36614953",
                    "title": "나의 여름은 아직 안 끝났어",
                    "artist_or_brand": "Yun Seok Cheol Trio*",
                    "confidence": 0.75,
                }
            ]
        return []

    monkeypatch.setattr(provider_module, "search_discogs_by_query", fake_search_discogs_by_query)

    rows = provider_module._search_discogs_release_with_artist_variations(
        query="윤석철 트리오 나의 여름은 아직 안끝났어",
        artist_or_brand="윤석철 트리오",
        title="나의 여름은 아직 안끝났어",
        limit=10,
    )

    assert [row["external_id"] for row in rows] == ["36614953"]


def test_resolve_release_master_reference_uses_discogs_detail_master_external_id_fallback(monkeypatch):
    monkeypatch.setattr(provider_module, "_discogs_headers", lambda: {"Authorization": "Discogs token test"})
    monkeypatch.setattr(
        provider_module,
        "_fetch_discogs_release_detail",
        lambda external_id, headers=None, client=None: {
            "master_external_id": "3331849",
            "raw_detail": {
                "title": "The World EP.Fin:Will",
                "artists": [{"name": "Ateez (2)"}],
                "year": 2023,
            },
        },
    )

    row = provider_module.resolve_release_master_reference(source="DISCOGS", external_id="29121433")

    assert row == {
        "source": "DISCOGS",
        "master_external_id": "3331849",
        "title": "The World EP.Fin:Will",
        "artist_or_brand": "Ateez (2)",
        "release_year": 2023,
    }


def test_purchase_import_candidates_support_direct_discogs_release_reference(admin_client, monkeypatch):
    row = {
        "id": 816,
        "vendor_code": "YES24",
        "source_type": "FILE_UPLOAD",
        "source_ref": "debug-http",
        "email_from": None,
        "email_subject": None,
        "artist_name": "윤석철 트리오",
        "item_name": "나의 여름은 아직 안 끝났어",
        "media_format": "LP",
        "quantity": 1,
        "unit_price": None,
        "line_total": None,
        "currency_code": None,
        "purchase_date": None,
        "seller_name": None,
        "item_url": None,
        "image_url": None,
        "raw_line": None,
        "queue_status": "PENDING",
        "linked_owned_item_id": None,
        "created_at": "2026-04-13T15:11:02.128993+00:00",
        "updated_at": "2026-04-13T15:11:02.128993+00:00",
        "raw_payload": {},
    }
    monkeypatch.setattr(main_module.db, "get_purchase_import_row", lambda queue_id: dict(row) if queue_id == 816 else None)
    monkeypatch.setattr(
        main_module,
        "get_source_release_snapshot",
        lambda source, external_id: {
            "artist_or_brand": "Yun Seok Cheol Trio",
            "release_year": 2024,
            "released_date": "2024-06-12",
            "format_name": "LP",
            "catalog_no": "MBMC-2216",
            "label_name": "BEATBALL MUSIC",
            "barcode": "8809114692216",
            "cover_image_url": "https://img.example/36614953.jpg",
            "track_list": ["나의 여름은 아직 안 끝났어"],
            "media_type": "Vinyl",
            "release_type": "ALBUM",
            "domain_code": "KOREA",
            "genres": ["Jazz"],
            "styles": ["Contemporary Jazz"],
            "raw": {"title": "나의 여름은 아직 안 끝났어", "country": "South Korea"},
        }
        if source == "DISCOGS" and external_id == "36614953"
        else None,
    )
    monkeypatch.setattr(main_module, "search_music_metadata", lambda **kwargs: (_ for _ in ()).throw(AssertionError("unexpected metadata search")))
    monkeypatch.setattr(main_module, "_annotate_owned_flags", lambda candidates: candidates)

    res = admin_client.get(
        "/purchase-imports/816/candidates",
        params={
            "source": "DISCOGS",
            "limit": 5,
            "query": "https://www.discogs.com/release/36614953-Yun-Seok-Cheol-Trio",
        },
    )

    assert res.status_code == 200
    payload = res.json()
    assert payload["query"] == "https://www.discogs.com/release/36614953-Yun-Seok-Cheol-Trio"
    assert payload["candidates"][0]["external_id"] == "36614953"


def test_album_master_search_supports_direct_release_reference(admin_client, monkeypatch):
    monkeypatch.setattr(
        main_module,
        "resolve_release_master_reference",
        lambda source, external_id: {
            "source": "DISCOGS",
            "master_external_id": "3123456",
            "title": "나의 여름은 아직 안 끝났어",
            "artist_or_brand": "Yun Seok Cheol Trio",
            "release_year": 2024,
        }
        if source == "DISCOGS" and external_id == "36614953"
        else None,
    )
    monkeypatch.setattr(main_module, "search_album_master_candidates", lambda **kwargs: (_ for _ in ()).throw(AssertionError("unexpected master search")))

    res = admin_client.post(
        "/album-masters/search",
        json={
            "source": "DISCOGS",
            "query": "release:36614953",
            "limit": 10,
        },
    )

    assert res.status_code == 200
    payload = res.json()
    assert payload["candidates"][0]["source"] == "DISCOGS"
    assert payload["candidates"][0]["master_external_id"] == "3123456"


def test_album_master_search_supports_direct_maniadb_album_reference_with_cover(admin_client, monkeypatch):
    monkeypatch.setattr(
        main_module,
        "get_album_master_variants",
        lambda source, master_external_id, limit=30, include_details=False: [
            {
                "source": "MANIADB",
                "external_id": "129004:2",
                "title": "그쟈? / 입영전야",
                "artist_or_brand": "최백호",
                "release_year": 1977,
                "label_name": "SRB",
                "catalog_no": "SR-0086",
                "cover_image_url": "https://i.maniadb.com/images/album/129/129004_lpa_f.jpg",
            }
        ]
        if source == "MANIADB" and master_external_id == "129004"
        else [],
    )
    monkeypatch.setattr(main_module, "search_album_master_candidates", lambda **kwargs: (_ for _ in ()).throw(AssertionError("unexpected master search")))

    res = admin_client.post(
        "/album-masters/search",
        json={
            "source": "MANIADB",
            "query": "album:129004",
            "limit": 10,
        },
    )

    assert res.status_code == 200
    payload = res.json()
    assert payload["candidates"][0]["source"] == "MANIADB"
    assert payload["candidates"][0]["master_external_id"] == "129004"
    assert payload["candidates"][0]["cover_image_url"] == "https://i.maniadb.com/images/album/129/129004_lpa_f.jpg"


def test_album_master_search_forwards_artist_and_title_hints(admin_client, monkeypatch):
    captured: dict[str, object] = {}

    def fake_search_album_master_candidates(*, query, source="AUTO", limit=10, artist_or_brand=None, title=None):
        captured["query"] = query
        captured["source"] = source
        captured["limit"] = limit
        captured["artist_or_brand"] = artist_or_brand
        captured["title"] = title
        return []

    monkeypatch.setattr(main_module, "search_album_master_candidates", fake_search_album_master_candidates)

    res = admin_client.post(
        "/album-masters/search",
        json={
            "source": "DISCOGS",
            "query": "윤석철 트리오 나의 여름은 아직 안끝났어",
            "artist_or_brand": "윤석철 트리오",
            "title": "나의 여름은 아직 안끝났어",
            "limit": 10,
        },
    )

    assert res.status_code == 200
    assert captured == {
        "query": "윤석철 트리오 나의 여름은 아직 안끝났어",
        "source": "DISCOGS",
        "limit": 10,
        "artist_or_brand": "윤석철 트리오",
        "title": "나의 여름은 아직 안끝났어",
    }


def test_ingest_csv_forwards_artist_and_title_hints_to_discogs_lookup(admin_client, monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(main_module, "validate_row_for_ingest", lambda row, default_category=None: (True, "LP", None))

    def fake_search_music_metadata(
        *,
        barcode=None,
        query=None,
        category=None,
        source="AUTO",
        limit=5,
        artist_or_brand=None,
        title=None,
    ):
        captured["barcode"] = barcode
        captured["query"] = query
        captured["category"] = category
        captured["source"] = source
        captured["limit"] = limit
        captured["artist_or_brand"] = artist_or_brand
        captured["title"] = title
        return []

    monkeypatch.setattr(main_module, "search_music_metadata", fake_search_music_metadata)
    monkeypatch.setattr(
        main_module,
        "classify_candidate",
        lambda candidates: main_module.MatchResult(
            confidence=0.0,
            review_status="NEEDS_REVIEW",
            review_note=None,
            candidate=None,
        ),
    )

    res = admin_client.post(
        "/ingest/csv",
        files={
            "file": (
                "discogs-variation.csv",
                "artist_or_brand,title,category\n윤석철 트리오,나의 여름은 아직 안끝났어,LP\n",
                "text/csv",
            )
        },
    )

    assert res.status_code == 200
    assert captured == {
        "barcode": None,
        "query": "윤석철 트리오 나의 여름은 아직 안끝났어",
        "category": "LP",
        "source": "AUTO",
        "limit": 5,
        "artist_or_brand": "윤석철 트리오",
        "title": "나의 여름은 아직 안끝났어",
    }


def test_album_master_search_supports_direct_maniadb_album_reference(admin_client, monkeypatch):
    monkeypatch.setattr(
        main_module,
        "get_album_master_variants",
        lambda source, master_external_id, limit=30, include_details=False: [
            {
                "source": "MANIADB",
                "external_id": "1058176:1",
                "title": "나의 여름은 아직 안 끝났어",
                "artist_or_brand": "윤석철 트리오",
                "release_year": 2024,
                "label_name": "비트볼",
                "catalog_no": "MBMC-2216",
                "barcode": "8809114692216",
            }
        ]
        if source == "MANIADB" and master_external_id == "1058176"
        else [],
    )
    monkeypatch.setattr(main_module, "search_album_master_candidates", lambda **kwargs: (_ for _ in ()).throw(AssertionError("unexpected master search")))

    res = admin_client.post(
        "/album-masters/search",
        json={
            "source": "MANIADB",
            "query": "album:1058176",
            "limit": 10,
        },
    )

    assert res.status_code == 200
    payload = res.json()
    assert payload["candidates"][0]["source"] == "MANIADB"
    assert payload["candidates"][0]["master_external_id"] == "1058176"


def test_admin_can_replace_goods_item_mappings(admin_client):
    master_id = db.upsert_album_master(
        source_code="MANUAL",
        source_master_id="goods-route-master",
        title="굿즈 연결 앨범",
        artist_or_brand="굿즈 연결 아티스트",
        domain_code=None,
        release_year=2001,
        raw={},
    )
    created = admin_client.post(
        "/goods-items",
        json={
            "category": "T_SHIRT",
            "goods_name": "콜라보 티셔츠",
            "quantity": 1,
            "status": "ACTIVE",
        },
    )
    assert created.status_code == 200
    goods_id = int(created.json()["id"])

    res = admin_client.put(
        f"/goods-items/{goods_id}/mappings",
        json={
            "album_master_ids": [master_id],
            "artist_names": ["산울림", "아이유"],
            "label_names": ["서울음반"],
        },
    )

    assert res.status_code == 200
    payload = res.json()
    assert payload["album_master_mappings"][0]["album_master_id"] == master_id
    assert payload["artist_mappings"] == ["산울림", "아이유"]
    assert payload["label_mappings"] == ["서울음반"]


def test_admin_can_search_goods_album_master_targets(admin_client):
    master_id = db.upsert_album_master(
        source_code="MANUAL",
        source_master_id="goods-target-master",
        title="연계 대상 앨범",
        artist_or_brand="테스트 아티스트",
        domain_code=None,
        release_year=2003,
        raw={},
    )

    res = admin_client.get(
        "/goods-targets",
        params={"kind": "album_master", "q": "연계 대상", "limit": 5},
    )

    assert res.status_code == 200


def test_admin_can_search_goods_collectible_targets(admin_client):
    source = admin_client.post(
        "/goods-items",
        json={
            "category": "POSTER",
            "goods_name": "김윤아 포스터 A",
            "quantity": 1,
            "status": "ACTIVE",
        },
    )
    assert source.status_code == 200
    source_id = int(source.json()["id"])

    target = admin_client.post(
        "/goods-items",
        json={
            "category": "POSTER",
            "goods_name": "김윤아 포스터 B",
            "quantity": 1,
            "status": "ACTIVE",
        },
    )
    assert target.status_code == 200
    target_id = int(target.json()["id"])

    res = admin_client.get(
        "/goods-targets",
        params={
            "kind": "collectible",
            "q": "김윤아",
            "goods_item_id": source_id,
            "limit": 10,
        },
    )

    assert res.status_code == 200
    payload = res.json()
    assert [int(item["goods_item_id"]) for item in payload["items"]] == [target_id]
    assert payload["items"][0]["goods_name"] == "김윤아 포스터 B"


def test_admin_can_save_goods_collectible_relations(admin_client):
    source = admin_client.post(
        "/goods-items",
        json={
            "category": "POSTER",
            "goods_name": "세트 본품",
            "quantity": 1,
            "status": "ACTIVE",
        },
    )
    assert source.status_code == 200
    source_id = int(source.json()["id"])

    linked = admin_client.post(
        "/goods-items",
        json={
            "category": "OTHER",
            "goods_name": "프로모 전단",
            "quantity": 1,
            "status": "ACTIVE",
        },
    )
    assert linked.status_code == 200
    linked_id = int(linked.json()["id"])

    save = admin_client.put(
        f"/goods-items/{source_id}/relations",
        json={
            "relations": [
                {
                    "relation_type": "SET_MEMBER",
                    "linked_goods_item_id": linked_id,
                    "note": "초회 특전 포함",
                    "display_order": 0,
                }
            ]
        },
    )

    assert save.status_code == 200
    payload = save.json()
    assert payload["collectible_relation_count"] == 1
    assert payload["relation_badges"] == ["SET_MEMBER"]
    assert payload["collectible_relations"] == [
        {
            "relation_type": "SET_MEMBER",
            "direction": "OUTGOING",
            "linked_goods_item_id": linked_id,
            "linked_goods_name": "프로모 전단",
            "linked_category": "OTHER",
            "note": "초회 특전 포함",
            "display_order": 0,
        }
    ]

    detail = admin_client.get(f"/goods-items/{source_id}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["collectible_relation_count"] == 1
    assert detail_payload["collectible_relation_preview"][0]["linked_goods_name"] == "프로모 전단"


def test_admin_can_save_album_master_correction_and_related_versions_exposes_it(admin_client):
    master_id = db.upsert_album_master(
        source_code="MANUAL",
        source_master_id="correction-route-master",
        title="교정 테스트 앨범",
        artist_or_brand="교정 테스트 아티스트",
        domain_code="WESTERN",
        release_year=2001,
        raw={},
    )
    owned_item_id = db.insert_owned_item(
        {
            "category": "LP",
            "quantity": 1,
            "size_group": "LP",
            "preferred_storage_size_group": "LP",
            "status": "IN_COLLECTION",
            "item_name_override": "교정 테스트 앨범",
            "domain_code": "WESTERN",
            "music_detail": {
                "format_name": "LP",
                "artist_or_brand": "교정 테스트 아티스트",
                "release_year": 2001,
            },
        }
    )
    db.bind_album_master_members(album_master_id=master_id, owned_item_ids=[owned_item_id], replace_existing=False)
    db.set_owned_item_linked_album_master(owned_item_id=owned_item_id, album_master_id=master_id)

    res = admin_client.patch(
        f"/album-masters/{master_id}/correction",
        json={
            "release_year": 1978,
            "domain_code": "KOREA",
            "override_note": "정렬은 원발매 기준",
        },
    )

    assert res.status_code == 200
    payload = res.json()
    assert payload["album_master_id"] == master_id
    assert payload["release_year"] == 1978
    assert payload["domain_code"] == "KOREA"
    assert payload["source_release_year"] == 2001
    assert payload["source_domain_code"] == "WESTERN"
    assert payload["override_release_year"] == 1978
    assert payload["override_domain_code"] == "KOREA"
    assert payload["override_note"] == "정렬은 원발매 기준"
    assert payload["has_manual_correction"] is True

    related = admin_client.get(f"/owned-items/{owned_item_id}/related-versions")

    assert related.status_code == 200
    related_payload = related.json()
    assert related_payload["album_master_id"] == master_id
    assert related_payload["release_year"] == 1978
    assert related_payload["domain_code"] == "KOREA"
    assert related_payload["source_release_year"] == 2001
    assert related_payload["source_domain_code"] == "WESTERN"
    assert related_payload["override_release_year"] == 1978
    assert related_payload["override_domain_code"] == "KOREA"
    assert related_payload["override_note"] == "정렬은 원발매 기준"
    assert related_payload["has_manual_correction"] is True


def test_bind_album_master_updates_selected_owned_items_linked_master(admin_client):
    owned_item_ids = [
        db.insert_owned_item(
            {
                "category": "CD",
                "size_group": "STD",
                "quantity": 1,
                "status": "IN_COLLECTION",
                "signature_type": "NONE",
                "item_name_override": f"조동익 - 동경 테스트 {index}",
            }
        )
        for index in (1, 2)
    ]

    res = admin_client.post(
        "/album-masters/bind",
        json={
            "source": "DISCOGS",
            "master_external_id": "bind-test-master-1",
            "title": "동경",
            "artist_or_brand": "조동익",
            "release_year": 1994,
            "owned_item_ids": owned_item_ids,
            "replace_existing": True,
        },
    )

    assert res.status_code == 200
    payload = res.json()
    album_master_id = int(payload["album_master_id"])
    assert album_master_id > 0

    for owned_item_id in owned_item_ids:
        row = db.get_owned_item(owned_item_id)
        assert row is not None
        assert int(row["linked_album_master_id"] or 0) == album_master_id


def test_goods_items_search_supports_status_domain_and_slot_filters(admin_client):
    slot = db.upsert_storage_slot(
        cabinet_name="굿즈장",
        column_code="01",
        cell_code="01",
        allowed_size_group="GOODS",
    )
    archived = admin_client.post(
        "/goods-items",
        json={
            "category": "HAT",
            "goods_name": "보관 모자",
            "quantity": 1,
            "status": "ARCHIVED",
            "domain_code": "WESTERN",
            "storage_slot_id": int(slot["id"]),
        },
    )
    assert archived.status_code == 200
    active = admin_client.post(
        "/goods-items",
        json={
            "category": "HAT",
            "goods_name": "활성 모자",
            "quantity": 1,
            "status": "ACTIVE",
            "domain_code": "KOREA",
        },
    )
    assert active.status_code == 200

    res = admin_client.get(
        "/goods-items",
        params={
            "category": "HAT",
            "status": "ARCHIVED",
            "domain_code": "WESTERN",
            "storage_slot_id": int(slot["id"]),
        },
    )

    assert res.status_code == 200
    payload = res.json()
    assert payload["total_count"] == 1
    assert [item["goods_name"] for item in payload["items"]] == ["보관 모자"]


def test_admin_can_delete_goods_item(admin_client):
    created = admin_client.post(
        "/goods-items",
        json={
            "category": "POSTER",
            "goods_name": "삭제 포스터",
            "quantity": 1,
            "status": "ACTIVE",
        },
    )
    assert created.status_code == 200
    goods_id = int(created.json()["id"])

    res = admin_client.delete(f"/goods-items/{goods_id}")

    assert res.status_code == 200
    assert res.json() == {"deleted": True, "goods_item_id": goods_id}
    assert db.get_goods_item(goods_id) is None


def test_update_owned_item_slot_route_resequences_order_key_to_match_slot_sort(admin_client):
    slot = db.upsert_storage_slot(
        cabinet_name="재정렬 LP장",
        column_code="01",
        cell_code="01",
        allowed_size_group="LP",
        cabinet_sort_policy="ARTIST_RELEASE_TITLE",
    )

    bob_id = db.insert_owned_item(
        {
            "category": "LP",
            "quantity": 1,
            "size_group": "LP",
            "status": "IN_COLLECTION",
            "item_name_override": "Highway 61 Revisited",
            "storage_slot_id": int(slot["id"]),
            "music_detail": {
                "format_name": "LP",
                "artist_or_brand": "Bob Dylan",
                "label_name": "QA Label",
                "catalog_no": "BD-001",
                "barcode": "8800000091001",
                "track_list": ["Like a Rolling Stone"],
                "track_items": [{"display": "1. Like a Rolling Stone", "title": "Like a Rolling Stone"}],
            },
        }
    )
    beatles_id = db.insert_owned_item(
        {
            "category": "LP",
            "quantity": 1,
            "size_group": "LP",
            "status": "IN_COLLECTION",
            "item_name_override": "Abbey Road",
            "storage_slot_id": None,
            "music_detail": {
                "format_name": "LP",
                "artist_or_brand": "The Beatles",
                "label_name": "QA Label",
                "catalog_no": "TB-001",
                "barcode": "8800000091002",
                "track_list": ["Come Together"],
                "track_items": [{"display": "1. Come Together", "title": "Come Together"}],
            },
        }
    )

    res = admin_client.patch(f"/owned-items/{beatles_id}/slot", json={"storage_slot_id": int(slot["id"])})

    assert res.status_code == 200

    beatles_row = db.get_owned_item(beatles_id)
    bob_row = db.get_owned_item(bob_id)
    assert beatles_row is not None and bob_row is not None
    assert str(beatles_row["order_key"] or "") < str(bob_row["order_key"] or "")


def test_update_owned_item_slot_route_skips_full_resequence_for_unassigned_to_slot_move(admin_client, monkeypatch):
    slot = db.upsert_storage_slot(
        cabinet_name="속도 테스트 LP장",
        column_code="01",
        cell_code="01",
        allowed_size_group="LP",
        cabinet_sort_policy="ARTIST_RELEASE_TITLE",
    )

    bob_id = db.insert_owned_item(
        {
            "category": "LP",
            "quantity": 1,
            "size_group": "LP",
            "status": "IN_COLLECTION",
            "item_name_override": "Highway 61 Revisited",
            "storage_slot_id": int(slot["id"]),
            "music_detail": {
                "format_name": "LP",
                "artist_or_brand": "Bob Dylan",
                "label_name": "QA Label",
                "catalog_no": "BD-001",
                "barcode": "8800000091001",
                "track_list": ["Like a Rolling Stone"],
                "track_items": [{"display": "1. Like a Rolling Stone", "title": "Like a Rolling Stone"}],
            },
        }
    )
    beatles_id = db.insert_owned_item(
        {
            "category": "LP",
            "quantity": 1,
            "size_group": "LP",
            "status": "IN_COLLECTION",
            "item_name_override": "Abbey Road",
            "storage_slot_id": None,
            "music_detail": {
                "format_name": "LP",
                "artist_or_brand": "The Beatles",
                "label_name": "QA Label",
                "catalog_no": "TB-001",
                "barcode": "8800000091002",
                "track_list": ["Come Together"],
                "track_items": [{"display": "1. Come Together", "title": "Come Together"}],
            },
        }
    )

    def _unexpected_resequence():
        raise AssertionError("full resequence should not run for unassigned-to-slot moves")

    monkeypatch.setattr(main_module.db, "resequence_in_collection_order", _unexpected_resequence)

    res = admin_client.patch(f"/owned-items/{beatles_id}/slot", json={"storage_slot_id": int(slot["id"])})

    assert res.status_code == 200
    beatles_row = db.get_owned_item(beatles_id)
    bob_row = db.get_owned_item(bob_id)
    assert beatles_row is not None and bob_row is not None
    assert str(beatles_row["order_key"] or "") < str(bob_row["order_key"] or "")


def test_update_owned_item_slot_route_skips_full_resequence_for_slot_to_slot_move(admin_client, monkeypatch):
    source_slot = db.upsert_storage_slot(
        cabinet_name="속도 테스트 LP장",
        column_code="01",
        cell_code="01",
        allowed_size_group="LP",
        cabinet_sort_policy="ARTIST_RELEASE_TITLE",
    )
    target_slot = db.upsert_storage_slot(
        cabinet_name="속도 테스트 LP장",
        column_code="01",
        cell_code="02",
        allowed_size_group="LP",
        cabinet_sort_policy="ARTIST_RELEASE_TITLE",
    )

    moving_id = db.insert_owned_item(
        {
            "category": "LP",
            "quantity": 1,
            "size_group": "LP",
            "status": "IN_COLLECTION",
            "item_name_override": "Abbey Road",
            "storage_slot_id": int(source_slot["id"]),
            "music_detail": {
                "format_name": "LP",
                "artist_or_brand": "The Beatles",
                "label_name": "QA Label",
                "catalog_no": "TB-FAST-001",
                "barcode": "8800000091991",
                "track_list": ["Come Together"],
                "track_items": [{"display": "1. Come Together", "title": "Come Together"}],
            },
        }
    )
    anchor_id = db.insert_owned_item(
        {
            "category": "LP",
            "quantity": 1,
            "size_group": "LP",
            "status": "IN_COLLECTION",
            "item_name_override": "Highway 61 Revisited",
            "storage_slot_id": int(target_slot["id"]),
            "music_detail": {
                "format_name": "LP",
                "artist_or_brand": "Bob Dylan",
                "label_name": "QA Label",
                "catalog_no": "BD-FAST-001",
                "barcode": "8800000091992",
                "track_list": ["Like a Rolling Stone"],
                "track_items": [{"display": "1. Like a Rolling Stone", "title": "Like a Rolling Stone"}],
            },
        }
    )

    def _unexpected_resequence():
        raise AssertionError("full resequence should not run for slot-to-slot moves")

    monkeypatch.setattr(main_module.db, "resequence_in_collection_order", _unexpected_resequence)

    res = admin_client.patch(f"/owned-items/{moving_id}/slot", json={"storage_slot_id": int(target_slot["id"])})

    assert res.status_code == 200
    moved_row = db.get_owned_item(moving_id)
    anchor_row = db.get_owned_item(anchor_id)
    assert moved_row is not None and anchor_row is not None
    assert int(moved_row["storage_slot_id"] or 0) == int(target_slot["id"])
    assert str(moved_row["order_key"] or "") < str(anchor_row["order_key"] or "")


def test_update_owned_item_slot_route_inherits_target_cabinet_domain_when_item_domain_is_unspecified(admin_client):
    target_slot = db.upsert_storage_slot(
        cabinet_name="도메인 상속 LP장",
        column_code="01",
        cell_code="01",
        allowed_size_group="LP",
        cabinet_sort_policy="ARTIST_RELEASE_TITLE",
        cabinet_domain_code="WESTERN",
    )

    moving_id = db.insert_owned_item(
        {
            "category": "LP",
            "quantity": 1,
            "size_group": "LP",
            "status": "IN_COLLECTION",
            "domain_code": "UNKNOWN",
            "item_name_override": "Abbey Road",
            "storage_slot_id": None,
            "music_detail": {
                "format_name": "LP",
                "artist_or_brand": "The Beatles",
                "label_name": "QA Label",
                "catalog_no": "TB-DOMAIN-001",
                "barcode": "8800000091881",
                "track_list": ["Come Together"],
                "track_items": [{"display": "1. Come Together", "title": "Come Together"}],
            },
        }
    )

    res = admin_client.patch(f"/owned-items/{moving_id}/slot", json={"storage_slot_id": int(target_slot["id"])})

    assert res.status_code == 200
    moved_row = db.get_owned_item(moving_id)
    assert moved_row is not None
    assert int(moved_row["storage_slot_id"] or 0) == int(target_slot["id"])
    assert str(moved_row["domain_code"] or "") == "WESTERN"


def test_update_owned_item_slot_route_keeps_existing_domain_when_target_cabinet_has_different_domain(admin_client):
    target_slot = db.upsert_storage_slot(
        cabinet_name="도메인 유지 LP장",
        column_code="01",
        cell_code="01",
        allowed_size_group="LP",
        cabinet_sort_policy="ARTIST_RELEASE_TITLE",
        cabinet_domain_code="WESTERN",
    )

    moving_id = db.insert_owned_item(
        {
            "category": "LP",
            "quantity": 1,
            "size_group": "LP",
            "status": "IN_COLLECTION",
            "domain_code": "KOREA",
            "item_name_override": "이미 도메인 있는 상품",
            "storage_slot_id": None,
            "music_detail": {
                "format_name": "LP",
                "artist_or_brand": "테스트 아티스트",
                "label_name": "QA Label",
                "catalog_no": "TB-DOMAIN-002",
                "barcode": "8800000091882",
                "track_list": ["Track 1"],
                "track_items": [{"display": "1. Track 1", "title": "Track 1"}],
            },
        }
    )

    res = admin_client.patch(f"/owned-items/{moving_id}/slot", json={"storage_slot_id": int(target_slot["id"])})

    assert res.status_code == 200
    moved_row = db.get_owned_item(moving_id)
    assert moved_row is not None
    assert int(moved_row["storage_slot_id"] or 0) == int(target_slot["id"])
    assert str(moved_row["domain_code"] or "") == "KOREA"


def test_onvif_connection_tolerates_optional_unauthorized_calls(monkeypatch):
    def fake_onvif_soap_request(service_url, body_xml, *, username, password, timeout=8.0):
        if "GetCapabilities" in body_xml:
            return ET.fromstring(
                """
                <Envelope xmlns:tt="http://www.onvif.org/ver10/schema">
                  <Body>
                    <Capabilities>
                      <tt:Media>
                        <tt:XAddr>http://camera.local/onvif/media_service</tt:XAddr>
                      </tt:Media>
                    </Capabilities>
                  </Body>
                </Envelope>
                """
            )
        if "GetDeviceInformation" in body_xml:
            request = httpx.Request("POST", "http://camera.local/onvif/device_service")
            response = httpx.Response(400, request=request, text="Not Authorized")
            raise httpx.HTTPStatusError("400", request=request, response=response)
        if "GetProfiles" in body_xml:
            request = httpx.Request("POST", "http://camera.local/onvif/media_service")
            response = httpx.Response(400, request=request, text="Not Authorized")
            raise httpx.HTTPStatusError("400", request=request, response=response)
        raise AssertionError(f"unexpected body: {body_xml}")

    monkeypatch.setattr(main_module, "_onvif_soap_request", fake_onvif_soap_request)

    payload = main_module._test_onvif_camera_connection(
        "http://camera.local/onvif/device_service",
        username=None,
        password=None,
    )

    assert payload["device_service_url"] == "http://camera.local/onvif/device_service"
    assert payload["media_service_url"] == "http://camera.local/onvif/media_service"
    assert payload["manufacturer"] is None
    assert payload["snapshot_url"] is None
    assert payload["stream_url"] is None


def test_camera_onvif_route_uses_stored_credentials_for_selected_camera(admin_client, monkeypatch):
    monkeypatch.setattr(
        main_module.db,
        "get_cabinet_camera",
        lambda camera_id: {
            "id": int(camera_id),
            "username": "stored-admin",
            "password": "stored-pass",
        },
    )
    captured = {}

    def fake_test_onvif(url, *, username, password):
        captured["url"] = url
        captured["username"] = username
        captured["password"] = password
        return {
            "device_service_url": url,
            "media_service_url": "http://camera.local/onvif/media_service",
            "profile_token": "PROFILE_000",
            "snapshot_url": "http://camera.local/snapshot",
            "stream_url": "rtsp://camera.local/stream",
            "manufacturer": "Meari",
            "model": "Speed 4T",
            "firmware_version": None,
            "serial_number": None,
            "hardware_id": None,
        }

    monkeypatch.setattr(main_module, "_test_onvif_camera_connection", fake_test_onvif)

    res = admin_client.post(
        "/cabinet-cameras/test-onvif",
        json={
            "camera_id": 7,
            "onvif_device_url": "http://camera.local/onvif/device_service",
            "username": None,
            "password": None,
        },
    )

    assert res.status_code == 200
    assert captured["url"] == "http://camera.local/onvif/device_service"
    assert captured["username"] == "stored-admin"
    assert captured["password"] == "stored-pass"


def test_admin_can_read_and_save_auto_backup_settings(admin_client, monkeypatch, tmp_path):
    monkeypatch.setattr(
        main_module,
        "_read_backup_launchd_schedules",
        lambda: {
            "daily_schedule": "매일 00:00",
            "weekly_schedule": "일요일 01:00",
        },
        raising=False,
    )

    res = admin_client.get("/ops/export/backup-settings")

    assert res.status_code == 200
    payload = res.json()
    assert payload["enabled"] is False
    assert payload["interval_minutes"] == 0
    assert payload["backup_dir"].endswith("/backups")
    assert payload["backup_scope"] == "DB"
    assert payload["include_env_file"] is False
    assert payload["daily_schedule"] == "매일 00:00"
    assert payload["weekly_schedule"] == "일요일 01:00"

    save_res = admin_client.post(
        "/ops/export/backup-settings",
        json={
            "enabled": True,
            "interval_minutes": 180,
            "backup_dir": str(tmp_path / "auto-backups"),
            "backup_scope": "FULL",
            "include_env_file": True,
        },
    )

    assert save_res.status_code == 200
    saved = save_res.json()
    assert saved["enabled"] is True
    assert saved["interval_minutes"] == 180
    assert saved["backup_dir"] == str(tmp_path / "auto-backups")
    assert saved["backup_scope"] == "FULL"
    assert saved["include_env_file"] is True
    assert saved["daily_schedule"] == "매일 00:00"
    assert saved["weekly_schedule"] == "일요일 01:00"

    reread_res = admin_client.get("/ops/export/backup-settings")
    assert reread_res.status_code == 200
    reread = reread_res.json()
    assert reread["enabled"] is True
    assert reread["interval_minutes"] == 180
    assert reread["backup_dir"] == str(tmp_path / "auto-backups")
    assert reread["backup_scope"] == "FULL"
    assert reread["include_env_file"] is True
    assert reread["daily_schedule"] == "매일 00:00"
    assert reread["weekly_schedule"] == "일요일 01:00"


def test_admin_can_read_and_save_metadata_provider_settings(admin_client, monkeypatch, tmp_path):
    env_path = tmp_path / ".env.local"
    env_path.write_text(
        "\n".join(
            [
                "DISCOGS_TOKEN=existing-discogs-token",
                "ALADIN_TTB_KEY=existing-aladin-key",
                "DISCOGS_USER_AGENT=hahahoho-library/0.1 (contact: test@example.com)",
                "ALADIN_BASE_URL=https://api.example.com/aladin",
                "MANIADB_BASE_URL=https://api.example.com/maniadb",
                "MUSICBRAINZ_USER_AGENT=hahahoho-library/0.1 (musicbrainz-test)",
                "DEEPL_AUTH_KEY=existing-deepl-key",
                "DEEPL_BASE_URL=https://api-free.deepl.com/v2/translate",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config_module, "_default_env_path", lambda: env_path)
    for key in (
        "DISCOGS_TOKEN",
        "ALADIN_TTB_KEY",
        "DISCOGS_USER_AGENT",
        "ALADIN_BASE_URL",
        "MANIADB_BASE_URL",
        "MUSICBRAINZ_USER_AGENT",
        "DEEPL_AUTH_KEY",
        "DEEPL_BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    main_module.get_settings.cache_clear()

    res = admin_client.get("/ops/provider-settings")

    assert res.status_code == 200
    payload = res.json()
    assert payload["discogs_token_configured"] is True
    assert payload["aladin_ttb_key_configured"] is True
    assert payload["discogs_user_agent"] == "hahahoho-library/0.1 (contact: test@example.com)"
    assert payload["aladin_base_url"] == "https://api.example.com/aladin"
    assert payload["maniadb_base_url"] == "https://api.example.com/maniadb"
    assert payload["musicbrainz_user_agent"] == "hahahoho-library/0.1 (musicbrainz-test)"
    assert payload["deepl_auth_key_configured"] is True
    assert payload["deepl_base_url"] == "https://api-free.deepl.com/v2/translate"

    save_res = admin_client.post(
        "/ops/provider-settings",
        json={
            "discogs_token": "updated-discogs-token",
            "aladin_ttb_key": "updated-aladin-key",
            "discogs_user_agent": "hahahoho-library/0.2 (contact: ops@example.com)",
            "aladin_base_url": "https://api.example.com/aladin-v2",
            "maniadb_base_url": "https://api.example.com/maniadb-v2",
            "musicbrainz_user_agent": "hahahoho-library/0.2 (musicbrainz-ops)",
            "deepl_auth_key": "updated-deepl-key",
            "deepl_base_url": "https://api.deepl.com/v2/translate",
        },
    )

    assert save_res.status_code == 200
    saved = save_res.json()
    assert saved["discogs_token_configured"] is True
    assert saved["aladin_ttb_key_configured"] is True
    assert saved["discogs_user_agent"] == "hahahoho-library/0.2 (contact: ops@example.com)"
    assert saved["aladin_base_url"] == "https://api.example.com/aladin-v2"
    assert saved["maniadb_base_url"] == "https://api.example.com/maniadb-v2"
    assert saved["musicbrainz_user_agent"] == "hahahoho-library/0.2 (musicbrainz-ops)"
    assert saved["deepl_auth_key_configured"] is True
    assert saved["deepl_base_url"] == "https://api.deepl.com/v2/translate"

    reread_res = admin_client.get("/ops/provider-settings")
    assert reread_res.status_code == 200
    reread = reread_res.json()
    assert reread == saved
    env_text = env_path.read_text(encoding="utf-8")
    assert "DISCOGS_TOKEN=updated-discogs-token" in env_text
    assert "ALADIN_TTB_KEY=updated-aladin-key" in env_text
    assert 'DISCOGS_USER_AGENT="hahahoho-library/0.2 (contact: ops@example.com)"' in env_text
    assert "ALADIN_BASE_URL=https://api.example.com/aladin-v2" in env_text
    assert "MANIADB_BASE_URL=https://api.example.com/maniadb-v2" in env_text
    assert 'MUSICBRAINZ_USER_AGENT="hahahoho-library/0.2 (musicbrainz-ops)"' in env_text
    assert "DEEPL_AUTH_KEY=updated-deepl-key" in env_text
    assert "DEEPL_BASE_URL=https://api.deepl.com/v2/translate" in env_text


def test_admin_can_run_deepl_provider_connection_test(admin_client, monkeypatch):
    from app.services import artist_context as artist_context_service

    monkeypatch.setenv("DEEPL_AUTH_KEY", "test-deepl-key")
    monkeypatch.setenv("DEEPL_BASE_URL", "https://api-free.deepl.com/v2/translate")
    main_module.get_settings.cache_clear()

    monkeypatch.setattr(
        artist_context_service,
        "fetch_deepl_usage",
        lambda auth_key, base_url: {"character_count": 64, "character_limit": 500000},
    )

    response = admin_client.post("/ops/provider-settings/deepl-test")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["configured"] is True
    assert payload["translated_text"] == "사용량 64 / 500000"


def test_full_backup_route_returns_zip_bundle(admin_client, monkeypatch, tmp_path):
    bundle_path = tmp_path / "hahahoho-library-full-backup.zip"
    bundle_path.write_bytes(b"zip-bundle")
    captured = {}

    def fake_create_bundle(backup_dir: str, *, reason: str = "manual-full", include_env_file: bool = False) -> str:
        captured["backup_dir"] = backup_dir
        captured["reason"] = reason
        captured["include_env_file"] = include_env_file
        return str(bundle_path)

    monkeypatch.setattr(main_module, "_create_local_full_backup_bundle", fake_create_bundle)

    res = admin_client.get("/ops/export/full-backup?include_env_file=true")

    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/zip")
    assert captured["reason"] == "manual-full"
    assert captured["include_env_file"] is True


def test_full_restore_upload_route_accepts_zip_bundle_and_returns_restore_metadata(admin_client, monkeypatch, tmp_path):
    seen = {}

    def fake_restore(upload_path: str, original_filename: str) -> dict[str, object]:
        seen["upload_path"] = upload_path
        seen["original_filename"] = original_filename
        assert Path(upload_path).is_file()
        return {
            "restored": True,
            "restored_filename": original_filename,
            "restored_bytes": Path(upload_path).stat().st_size,
            "backup_path": str(tmp_path / "before-full-restore.zip"),
        }

    monkeypatch.setattr(main_module, "_restore_library_bundle_from_upload", fake_restore)

    res = admin_client.post(
        "/ops/export/full-restore",
        files={"file": ("restore.zip", b"zip-upload", "application/zip")},
    )

    assert res.status_code == 200
    payload = res.json()
    assert payload["restored"] is True
    assert payload["restored_filename"] == "restore.zip"
    assert payload["backup_path"] == str(tmp_path / "before-full-restore.zip")
    assert seen["original_filename"] == "restore.zip"


def test_restore_upload_route_accepts_db_file_and_returns_restore_metadata(admin_client, monkeypatch, tmp_path):
    seen = {}

    def fake_restore(upload_path: str, original_filename: str) -> dict[str, object]:
        seen["upload_path"] = upload_path
        seen["original_filename"] = original_filename
        assert Path(upload_path).is_file()
        return {
            "restored": True,
            "restored_filename": original_filename,
            "restored_bytes": Path(upload_path).stat().st_size,
            "backup_path": str(tmp_path / "before-restore.db"),
        }

    monkeypatch.setattr(main_module, "_restore_library_db_from_upload", fake_restore)

    res = admin_client.post(
        "/ops/export/db-restore",
        files={"file": ("restore.db", b"sqlite-upload", "application/octet-stream")},
    )

    assert res.status_code == 200
    payload = res.json()
    assert payload["restored"] is True
    assert payload["restored_filename"] == "restore.db"
    assert payload["backup_path"] == str(tmp_path / "before-restore.db")
    assert seen["original_filename"] == "restore.db"


def test_maybe_run_auto_backup_once_uses_saved_settings(monkeypatch, tmp_path):
    recorded = {}
    now = datetime(2026, 3, 30, 12, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(
        main_module.db,
        "get_auto_backup_settings",
        lambda: {
            "enabled": True,
            "interval_minutes": 120,
            "backup_dir": str(tmp_path),
            "backup_scope": "DB",
            "include_env_file": False,
            "last_backup_at": (now - timedelta(minutes=121)).isoformat(),
            "last_backup_path": None,
            "last_error": None,
        },
    )
    monkeypatch.setattr(
        main_module,
        "_create_local_db_backup",
        lambda backup_dir, *, reason="auto": str(Path(backup_dir) / f"{reason}-backup.db"),
    )

    def fake_record(*, last_backup_at, last_backup_path, last_error):
        recorded["last_backup_at"] = last_backup_at
        recorded["last_backup_path"] = last_backup_path
        recorded["last_error"] = last_error

    monkeypatch.setattr(main_module.db, "record_auto_backup_result", fake_record)

    result = main_module._maybe_run_auto_backup_once(now=now)

    assert result == str(tmp_path / "auto-backup.db")
    assert recorded["last_backup_path"] == str(tmp_path / "auto-backup.db")
    assert recorded["last_error"] is None


def test_maybe_run_auto_backup_once_uses_full_bundle_when_scope_is_full(monkeypatch, tmp_path):
    recorded = {}
    now = datetime(2026, 3, 30, 12, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(
        main_module.db,
        "get_auto_backup_settings",
        lambda: {
            "enabled": True,
            "interval_minutes": 60,
            "backup_dir": str(tmp_path),
            "backup_scope": "FULL",
            "include_env_file": True,
            "last_backup_at": (now - timedelta(minutes=61)).isoformat(),
            "last_backup_path": None,
            "last_error": None,
        },
    )
    monkeypatch.setattr(
        main_module,
        "_create_local_full_backup_bundle",
        lambda backup_dir, *, reason="auto", include_env_file=False: str(tmp_path / f"{reason}.zip"),
    )

    def fake_record(*, last_backup_at, last_backup_path, last_error):
        recorded["last_backup_at"] = last_backup_at
        recorded["last_backup_path"] = last_backup_path
        recorded["last_error"] = last_error

    monkeypatch.setattr(main_module.db, "record_auto_backup_result", fake_record)

    result = main_module._maybe_run_auto_backup_once(now=now)

    assert result == str(tmp_path / "auto.zip")
    assert recorded["last_backup_path"] == str(tmp_path / "auto.zip")
    assert recorded["last_error"] is None


def test_update_owned_item_route_resequences_order_key_after_sorting_metadata_changes(admin_client):
    slot = db.upsert_storage_slot(
        cabinet_name="편집 재정렬 LP장",
        column_code="01",
        cell_code="01",
        allowed_size_group="LP",
        cabinet_sort_policy="ARTIST_RELEASE_TITLE",
    )

    bob_id = db.insert_owned_item(
        {
            "category": "LP",
            "quantity": 1,
            "size_group": "LP",
            "status": "IN_COLLECTION",
            "item_name_override": "Highway 61 Revisited",
            "storage_slot_id": int(slot["id"]),
            "music_detail": {
                "format_name": "LP",
                "artist_or_brand": "Bob Dylan",
                "label_name": "QA Label",
                "catalog_no": "BD-101",
                "barcode": "8800000091101",
                "track_list": ["Like a Rolling Stone"],
                "track_items": [{"display": "1. Like a Rolling Stone", "title": "Like a Rolling Stone"}],
            },
        }
    )
    zed_id = db.insert_owned_item(
        {
            "category": "LP",
            "quantity": 1,
            "size_group": "LP",
            "status": "IN_COLLECTION",
            "item_name_override": "Zed Album",
            "storage_slot_id": int(slot["id"]),
            "music_detail": {
                "format_name": "LP",
                "artist_or_brand": "Zed Artist",
                "label_name": "QA Label",
                "catalog_no": "ZA-101",
                "barcode": "8800000091102",
                "track_list": ["Track 1"],
                "track_items": [{"display": "1. Track 1", "title": "Track 1"}],
            },
        }
    )

    res = admin_client.patch(
        f"/owned-items/{zed_id}",
        json={
            "category": "LP",
            "size_group": "LP",
            "quantity": 1,
            "status": "IN_COLLECTION",
            "signature_type": "NONE",
            "item_name_override": "The Beatles - Abbey Road",
            "storage_slot_id": int(slot["id"]),
            "music_detail": {
                "format_name": "LP",
                "artist_or_brand": "The Beatles",
                "label_name": "QA Label",
                "catalog_no": "TB-101",
                "barcode": "8800000091102",
                "track_list": ["Come Together"],
                "track_items": [{"display": "1. Come Together", "title": "Come Together"}],
            },
        },
    )

    assert res.status_code == 200

    beatles_row = db.get_owned_item(zed_id)
    bob_row = db.get_owned_item(bob_id)
    assert beatles_row is not None and bob_row is not None
    assert str(beatles_row["order_key"] or "") < str(bob_row["order_key"] or "")


def test_slot_order_move_route_returns_display_rank(admin_client, monkeypatch):
    monkeypatch.setattr(
        main_module.db,
        "get_storage_slot",
        lambda storage_slot_id: {"id": storage_slot_id, "slot_code": "QA-01-01"},
    )

    def fake_slot_move(*, storage_slot_id: int, owned_item_id: int, target_owned_item_id: int, position: str):
        assert storage_slot_id == 17
        assert owned_item_id == 101
        assert target_owned_item_id == 202
        assert position == "BEFORE"
        return 10

    monkeypatch.setattr(main_module.db, "move_owned_item_slot_display_rank", fake_slot_move)

    res = admin_client.patch(
        "/storage-slots/17/owned-items/101/order",
        json={"target_owned_item_id": 202, "position": "BEFORE"},
    )

    assert res.status_code == 200
    payload = res.json()
    assert payload["storage_slot_id"] == 17
    assert payload["owned_item_id"] == 101
    assert payload["target_owned_item_id"] == 202
    assert payload["position"] == "BEFORE"
    assert payload["display_rank"] == 10


def test_album_master_search_returns_clickable_location_actions(admin_client, monkeypatch):
    monkeypatch.setattr(
        main_module.db,
        "list_album_masters",
        lambda **kwargs: [
            {
                "id": 91,
                "source_code": "DISCOGS",
                "source_master_id": "master-91",
                "title": "The Album",
                "artist_or_brand": "The Artist",
                "sort_artist_name": "The Artist",
                "domain_code": "WESTERN",
                "release_year": 2004,
                "member_count": 2,
                "cover_image_url": "https://example.com/cover.jpg",
                "audio_asset_count": 0,
                "member_preview_text": "Sub Pop / SP-01",
                "member_location_preview_text": "CD장 1 / 01열 / 03칸 || CD장 2 / 02열 / 04칸",
                "first_member_storage_slot_id": 17,
                "first_member_slot_code": "CD-1-01-03",
                "first_member_cabinet_name": "CD장 1",
                "first_member_column_code": "01",
                "first_member_cell_code": "03",
                "updated_at": "2026-03-20T12:00:00+00:00",
            }
        ],
    )
    monkeypatch.setattr(main_module.db, "count_album_masters", lambda **kwargs: 1)
    monkeypatch.setattr(main_module.db, "list_album_master_track_matches", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        main_module.db,
        "list_owned_items_by_album_master",
        lambda album_master_id: [
            {
                "id": 501,
                "item_name_override": "The Artist - The Album",
                "current_slot_display_name": "CD장 1 / 01열 / 03칸",
                "storage_slot_id": 17,
                "slot_code": "CD-1-01-03",
                "current_cabinet_name": "CD장 1",
                "current_column_code": "01",
                "current_cell_code": "03",
                "cabinet_name": "CD장 1",
                "column_code": "01",
                "cell_code": "03",
            },
            {
                "id": 502,
                "item_name_override": "The Artist - The Album (Deluxe)",
                "current_slot_display_name": "CD장 2 / 02열 / 04칸",
                "storage_slot_id": 24,
                "slot_code": "CD-2-02-04",
                "current_cabinet_name": "CD장 2",
                "current_column_code": "02",
                "current_cell_code": "04",
                "cabinet_name": "CD장 2",
                "column_code": "02",
                "cell_code": "04",
            },
        ],
    )

    res = admin_client.get("/album-masters", params={"q": "The Album"})

    assert res.status_code == 200
    payload = res.json()
    assert len(payload) == 1
    row = payload[0]
    assert row["member_count"] == 2
    assert len(row["member_location_actions"]) == 2
    assert row["member_location_actions"][0]["owned_item_id"] == 501
    assert row["member_location_actions"][0]["storage_slot_id"] == 17
    assert row["member_location_actions"][0]["cabinet_name"] == "CD장 1"
    assert row["member_location_actions"][1]["cell_code"] == "04"


def test_album_master_search_returns_structured_member_items_preview(admin_client, monkeypatch):
    monkeypatch.setattr(
        main_module.db,
        "list_album_masters",
        lambda **kwargs: [
            {
                "id": 92,
                "source_code": "DISCOGS",
                "source_master_id": "master-92",
                "title": "Preview Album",
                "artist_or_brand": "Preview Artist",
                "sort_artist_name": "Preview Artist",
                "domain_code": "WESTERN",
                "release_year": 2018,
                "member_count": 4,
                "cover_image_url": "https://example.com/cover.jpg",
                "audio_asset_count": 0,
                "member_preview_text": "Rhino Records / R1 544846",
                "member_location_preview_text": "LP장 6 / 03열 / 01칸",
                "first_member_storage_slot_id": 31,
                "first_member_slot_code": "LP-6-03-01",
                "first_member_cabinet_name": "LP장 6",
                "first_member_column_code": "03",
                "first_member_cell_code": "01",
                "updated_at": "2026-04-04T09:10:00+00:00",
            }
        ],
    )
    monkeypatch.setattr(main_module.db, "count_album_masters", lambda **kwargs: 1)
    monkeypatch.setattr(main_module.db, "list_album_master_track_matches", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        main_module.db,
        "list_owned_items_by_album_master",
        lambda album_master_id: [
            {
                "id": 701,
                "owned_item_id": 701,
                "category": "LP",
                "source_code": "DISCOGS",
                "source_external_id": "701-release",
                "item_title": "Preview Artist - Preview Album",
                "item_name_override": "Preview Artist - Preview Album",
                "artist_or_brand": "Preview Artist",
                "cover_image_url": "https://example.com/items/701.jpg",
                "released_date": "2018-11-02",
                "pressing_country": "Worldwide",
                "label_name": "Rhino Records",
                "catalog_no": "R1 544846",
                "barcode": "603497856244",
                "format_name": "LP",
                "format_items": [{"qty": "1", "descriptions": ["LP", "Album"]}],
                "runout_sample": "R1-544846 A",
                "created_at": "2026-04-03T05:18:00+00:00",
                "storage_slot_id": 31,
                "slot_code": "LP-6-03-01",
                "current_slot_code": "LP-6-03-01",
                "current_slot_display_name": "LP장 6 / 03열 / 01칸",
                "current_cabinet_name": "LP장 6",
                "current_column_code": "03",
                "current_cell_code": "01",
                "cabinet_name": "LP장 6",
                "column_code": "03",
                "cell_code": "01",
                "label_id": "LP-000701",
            },
            {
                "id": 702,
                "owned_item_id": 702,
                "category": "LP",
                "source_code": "DISCOGS",
                "source_external_id": "702-release",
                "item_title": "Preview Artist - Preview Album (Deluxe)",
                "item_name_override": "Preview Artist - Preview Album (Deluxe)",
                "artist_or_brand": "Preview Artist",
                "cover_image_url": "https://example.com/items/702.jpg",
                "released_date": "2019-01-10",
                "pressing_country": "US",
                "label_name": "Rhino Records",
                "catalog_no": "R1 544846X",
                "barcode": "603497856245",
                "format_name": "LP",
                "format_items": [{"qty": "2", "descriptions": ["LP", "Deluxe Edition"]}],
                "runout_sample": "R1-544846 B",
                "created_at": "2026-04-04T01:12:00+00:00",
                "storage_slot_id": None,
                "slot_code": None,
                "current_slot_code": None,
                "current_slot_display_name": "미배치",
                "current_cabinet_name": None,
                "current_column_code": None,
                "current_cell_code": None,
                "cabinet_name": None,
                "column_code": None,
                "cell_code": None,
                "label_id": "LP-000702",
            },
        ],
    )

    res = admin_client.get("/album-masters", params={"q": "Preview Album"})

    assert res.status_code == 200
    payload = res.json()
    assert len(payload) == 1
    row = payload[0]
    assert len(row["member_items_preview"]) == 2
    assert row["member_items_preview"][0]["owned_item_id"] == 701
    assert row["member_items_preview"][0]["label_id"] == "LP-000701"
    assert row["member_items_preview"][0]["cover_image_url"] == "https://example.com/items/701.jpg"
    assert row["member_items_preview"][0]["source_code"] == "DISCOGS"
    assert row["member_items_preview"][0]["source_external_id"] == "701-release"
    assert row["member_items_preview"][0]["current_slot_display_name"] == "LP장 6 / 03열 / 01칸"
    assert row["member_items_preview"][0]["runout_sample"] == "R1-544846 A"
    assert row["member_items_preview"][1]["label_id"] == "LP-000702"
    assert row["member_items_preview"][1]["cover_image_url"] == "https://example.com/items/702.jpg"
    assert row["member_items_preview"][1]["source_code"] == "DISCOGS"
    assert row["member_items_preview"][1]["source_external_id"] == "702-release"
    assert row["member_items_preview"][1]["current_slot_display_name"] == "미배치"


def test_album_master_search_preview_backfills_missing_released_date_from_source_snapshot(admin_client, monkeypatch):
    monkeypatch.setattr(
        main_module.db,
        "list_album_masters",
        lambda **kwargs: [
            {
                "id": 93,
                "source_code": "MANIADB",
                "source_master_id": "153773",
                "title": "自由魂 [box]",
                "artist_or_brand": "김두수",
                "sort_artist_name": "김두수",
                "domain_code": "KOREA",
                "release_year": 2003,
                "member_count": 1,
                "cover_image_url": "https://example.com/cover.jpg",
                "audio_asset_count": 0,
                "member_preview_text": "",
                "member_location_preview_text": "",
                "updated_at": "2026-04-05T01:00:00+00:00",
            }
        ],
    )
    monkeypatch.setattr(main_module.db, "count_album_masters", lambda **kwargs: 1)
    monkeypatch.setattr(main_module.db, "list_album_master_track_matches", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        main_module.db,
        "list_owned_items_by_album_master",
        lambda album_master_id: [
            {
                "id": 567,
                "owned_item_id": 567,
                "category": "LP",
                "source_code": "MANIADB",
                "source_external_id": "album:153773",
                "item_title": "김두수 - 자유혼",
                "artist_or_brand": "김두수",
                "cover_image_url": "https://example.com/items/567.jpg",
                "released_date": None,
                "pressing_country": "KR",
                "label_name": "리버맨",
                "catalog_no": None,
                "barcode": None,
                "format_name": "LP",
                "format_items": [],
                "runout_sample": None,
                "created_at": "2026-04-04T14:54:37+00:00",
                "storage_slot_id": None,
                "slot_code": None,
                "current_slot_code": None,
                "current_slot_display_name": "미배치",
                "current_cabinet_name": None,
                "current_column_code": None,
                "current_cell_code": None,
                "cabinet_name": None,
                "column_code": None,
                "cell_code": None,
                "label_id": "LP-000567",
            }
        ],
    )
    monkeypatch.setattr(
        main_module,
        "get_source_release_snapshot",
        lambda source, external_id: {"released_date": "2003-12-20"} if source == "MANIADB" and external_id == "album:153773" else None,
    )

    res = admin_client.get("/album-masters", params={"q": "자유혼"})

    assert res.status_code == 200
    payload = res.json()
    assert payload[0]["member_items_preview"][0]["released_date"] == "2003-12-20"


def test_owned_items_list_backfills_missing_released_date_from_source_snapshot(admin_client, monkeypatch):
    monkeypatch.setattr(
        main_module.db,
        "list_owned_items",
        lambda **kwargs: [
            {
                "id": 567,
                "category": "LP",
                "size_group": "LP",
                "preferred_storage_size_group": "LP",
                "quantity": 1,
                "is_second_hand": 0,
                "signature_type": "NONE",
                "source_code": "MANIADB",
                "source_external_id": "album:153773",
                "released_date": None,
                "release_year": 2003,
                "created_at": "2026-04-04T14:54:37+00:00",
                "updated_at": "2026-04-04T14:54:37+00:00",
                "status": "IN_COLLECTION",
            }
        ],
    )
    monkeypatch.setattr(main_module.db, "count_owned_items", lambda **kwargs: 1)
    monkeypatch.setattr(
        main_module,
        "get_source_release_snapshot",
        lambda source, external_id: {"released_date": "2003-12-20"} if source == "MANIADB" and external_id == "album:153773" else None,
    )

    res = admin_client.get("/owned-items", params={"category": "LP"})

    assert res.status_code == 200
    payload = res.json()
    assert payload[0]["released_date"] == "2003-12-20"


def test_owned_items_list_includes_master_sort_artist_name(admin_client, monkeypatch):
    monkeypatch.setattr(
        main_module.db,
        "list_owned_items",
        lambda **kwargs: [
            {
                "id": 642,
                "category": "CD",
                "size_group": "STD",
                "preferred_storage_size_group": "STD",
                "quantity": 1,
                "is_second_hand": 0,
                "signature_type": "NONE",
                "source_code": "DISCOGS",
                "source_external_id": "123",
                "created_at": "2026-04-15T14:44:25+00:00",
                "updated_at": "2026-04-15T14:44:25+00:00",
                "status": "IN_COLLECTION",
                "linked_album_master_id": 589,
                "domain_code": "KOREA",
                "artist_or_brand": "Shinhwa",
                "master_artist_or_brand": "Shinhwa",
                "master_sort_artist_name": "신화",
            }
        ],
    )
    monkeypatch.setattr(main_module.db, "count_owned_items", lambda **kwargs: 1)

    res = admin_client.get("/owned-items", params={"category": "CD"})

    assert res.status_code == 200
    payload = res.json()
    assert payload[0]["master_sort_artist_name"] == "신화"


def test_storage_slot_owned_items_include_master_sort_artist_name(admin_client, monkeypatch):
    monkeypatch.setattr(
        main_module.db,
        "get_storage_slot",
        lambda storage_slot_id: {"id": storage_slot_id, "slot_code": "CD-138"},
    )
    monkeypatch.setattr(
        main_module.db,
        "list_owned_items_for_storage_slot",
        lambda **kwargs: [
            {
                "id": 618,
                "category": "CD",
                "size_group": "STD",
                "preferred_storage_size_group": "STD",
                "quantity": 1,
                "is_second_hand": 0,
                "signature_type": "NONE",
                "source_code": "DISCOGS",
                "source_external_id": "456",
                "created_at": "2026-04-15T14:44:32+00:00",
                "updated_at": "2026-04-15T14:44:32+00:00",
                "status": "IN_COLLECTION",
                "storage_slot_id": 138,
                "linked_album_master_id": 569,
                "domain_code": "KOREA",
                "artist_or_brand": "Sinawe",
                "master_artist_or_brand": "Sinawe",
                "master_sort_artist_name": "시나위",
            }
        ],
    )

    res = admin_client.get("/storage-slots/138/owned-items")

    assert res.status_code == 200
    payload = res.json()
    assert payload[0]["master_sort_artist_name"] == "시나위"


def test_owned_items_route_populates_master_sort_artist_name_from_db(admin_client):
    owned_item_id = db.insert_owned_item(
        {
            "category": "CD",
            "quantity": 1,
            "size_group": "STD",
            "status": "IN_COLLECTION",
            "domain_code": "KOREA",
            "item_name_override": "Brand New QA",
            "storage_slot_id": None,
            "music_detail": {
                "format_name": "CD",
                "artist_or_brand": "Shinhwa",
                "label_name": "QA Label",
                "catalog_no": "SH-007",
                "barcode": "8800000091642",
                "track_list": ["Hero"],
                "track_items": [{"display": "1. Hero", "title": "Hero"}],
            },
        }
    )
    album_master_id = db.upsert_album_master(
        source_code="DISCOGS",
        source_master_id="qa-shinhwa-589",
        title="Brand New QA",
        artist_or_brand="Shinhwa",
        domain_code="KOREA",
        release_year=2004,
        raw={},
    )
    db.update_album_master_sort_artist_name(album_master_id, "신화")
    db.set_owned_item_linked_album_master(owned_item_id, album_master_id)

    res = admin_client.get(
        "/owned-items",
        params={
            "category": "CD",
            "status": "IN_COLLECTION",
            "slot_state": "UNSLOTTED",
            "item_name": "Brand New QA",
        },
    )

    assert res.status_code == 200
    payload = res.json()
    target = next(item for item in payload if item["id"] == owned_item_id)
    assert target["master_sort_artist_name"] == "신화"


def test_create_owned_item_localizes_discogs_domestic_artist_name(admin_client, monkeypatch):
    monkeypatch.setattr(
        main_module,
        "get_source_release_snapshot",
        lambda source, external_id: {
            "artist_or_brand": "Cho Yong-pil",
            "domain_code": "KOREA",
            "raw": {"artists": [{"id": 101, "name": "Cho Yong-pil"}]},
        }
        if source == "DISCOGS" and external_id == "release-101"
        else None,
    )
    monkeypatch.setattr(
        main_module,
        "resolve_discogs_preferred_korean_artist_name",
        lambda artist_name, external_id=None, raw=None, domain_code=None: "조용필"
        if artist_name == "Cho Yong-pil"
        else None,
    )
    monkeypatch.setattr(
        main_module,
        "_apply_post_create_links",
        lambda payload, owned_item_id, preferred_master_id=0: (preferred_master_id, []),
    )

    response = admin_client.post(
        "/owned-items",
        json={
            "category": "CD",
            "quantity": 1,
            "size_group": "STD",
            "status": "IN_COLLECTION",
            "source_code": "DISCOGS",
            "source_external_id": "release-101",
            "linked_artist_name": "Cho Yong-pil",
            "item_name_override": "Cho Yong-pil - Hello",
            "music_detail": {
                "format_name": "CD",
                "artist_or_brand": "Cho Yong-pil",
                "label_name": "굿 인터내셔널",
                "catalog_no": "HD-2184",
                "barcode": "8808513000379",
                "track_list": ["Hello"],
                "track_items": [{"display": "1. Hello", "title": "Hello"}],
            },
        },
    )

    assert response.status_code == 200
    owned_item_id = int(response.json()["owned_item_id"])
    detail = db.get_owned_item_detail(owned_item_id)
    assert detail["linked_artist_name"] == "조용필"
    assert detail["artist_or_brand"] == "조용필"
    assert detail["item_name_override"] == "조용필 - Hello"


def test_backfill_discogs_korean_artist_names_updates_existing_registered_items(monkeypatch, tmp_path):
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("LIBRARY_DB_PATH", str(db_path))
    main_module.db.get_settings.cache_clear()
    main_module.db.init_db()

    owned_item_id = main_module.db.insert_owned_item(
        {
            "category": "CD",
            "quantity": 1,
            "size_group": "STD",
            "status": "IN_COLLECTION",
            "source_code": "DISCOGS",
            "source_external_id": "release-101",
            "linked_artist_name": "Cho Yong-pil",
            "item_name_override": "Cho Yong-pil - Hello",
            "music_detail": {
                "format_name": "CD",
                "artist_or_brand": "Cho Yong-pil",
                "label_name": "굿 인터내셔널",
                "catalog_no": "HD-2184",
                "barcode": "8808513000379",
                "track_list": ["Hello"],
                "track_items": [{"display": "1. Hello", "title": "Hello"}],
            },
        }
    )
    album_master_id = main_module.db.upsert_album_master(
        source_code="DISCOGS",
        source_master_id="master-101",
        title="Hello",
        artist_or_brand="Cho Yong-pil",
        domain_code="KOREA",
        release_year=1996,
        raw={},
    )
    main_module.db.bind_album_master_members(
        album_master_id=album_master_id,
        owned_item_ids=[owned_item_id],
        replace_existing=False,
    )
    main_module.db.set_owned_item_linked_album_master(owned_item_id, album_master_id)

    monkeypatch.setattr(
        main_module,
        "get_source_release_snapshot",
        lambda source, external_id: {
            "artist_or_brand": "Cho Yong-pil",
            "domain_code": "KOREA",
            "raw": {"artists": [{"id": 101, "name": "Cho Yong-pil"}]},
        }
        if source == "DISCOGS" and external_id == "release-101"
        else None,
    )
    monkeypatch.setattr(
        main_module,
        "resolve_discogs_preferred_korean_artist_name",
        lambda artist_name, external_id=None, raw=None, domain_code=None: "조용필"
        if artist_name == "Cho Yong-pil"
        else None,
    )

    result = main_module.backfill_discogs_korean_artist_names(limit=20)

    assert result["scanned_items"] == 1
    assert result["updated_items"] == 1
    detail = main_module.db.get_owned_item_detail(owned_item_id)
    binding = main_module.db.get_album_master_binding_for_owned_item(owned_item_id)
    assert detail["linked_artist_name"] == "조용필"
    assert detail["artist_or_brand"] == "조용필"
    assert detail["item_name_override"] == "조용필 - Hello"
    assert binding["artist_or_brand"] == "조용필"
    assert binding["sort_artist_name"] == "조용필"
    with main_module.db.get_conn() as conn:
        external_ref = conn.execute(
            """
            SELECT artist_or_brand_hint
            FROM album_master_external_ref
            WHERE album_master_id = ?
              AND source_code = 'DISCOGS'
            LIMIT 1
            """,
            (album_master_id,),
        ).fetchone()
    assert dict(external_ref or {})["artist_or_brand_hint"] == "조용필"


def test_admin_can_fetch_discogs_cover_preview(admin_client, monkeypatch, tmp_path):
    cover_path = tmp_path / "discogs-preview.jpg"
    expected = b"fake-discogs-cover-preview"
    cover_path.write_bytes(expected)

    def fake_ensure_discogs_cover_preview(release_id: str):
        assert release_id == "1017068"
        return cover_path, "image/jpeg"

    monkeypatch.setattr(
        main_module,
        "_ensure_discogs_cover_preview",
        fake_ensure_discogs_cover_preview,
    )

    res = admin_client.get("/discogs/release/1017068/cover-preview")

    assert res.status_code == 200
    assert res.headers["content-type"].startswith("image/jpeg")
    assert res.content == expected


def test_startup_db_ready_skips_full_init_for_existing_db(monkeypatch, tmp_path):
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("LIBRARY_DB_PATH", str(db_path))
    main_module.db.get_settings.cache_clear()
    main_module.db.init_db()

    called = {"init": 0}

    def fake_init_db():
        called["init"] += 1

    monkeypatch.setattr(
        main_module.db,
        "get_settings",
        lambda: SimpleNamespace(db_path=str(db_path)),
    )
    monkeypatch.setattr(main_module.db, "init_db", fake_init_db)

    main_module.db.ensure_startup_db_ready()

    assert called["init"] == 0


def test_collection_dashboard_includes_connection_quality_counts(monkeypatch, tmp_path):
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("LIBRARY_DB_PATH", str(db_path))
    main_module.db.get_settings.cache_clear()
    main_module.db.init_db()

    def insert_music_item(name: str, artist: str) -> int:
        return main_module.db.insert_owned_item(
            {
                "category": "CD",
                "quantity": 1,
                "size_group": "STD",
                "status": "IN_COLLECTION",
                "item_name_override": name,
                "music_detail": {
                    "format_name": "CD",
                    "artist_or_brand": artist,
                    "label_name": "테스트 레이블",
                    "catalog_no": f"CAT-{name}",
                    "barcode": f"8800000{name[-1:]}",
                    "track_list": [f"{name} 트랙"],
                    "track_items": [{"number": "1", "title": f"{name} 트랙"}],
                },
            }
        )

    linked_ok_id = insert_music_item("연결완료", "테스트 아티스트")
    source_missing_id = insert_music_item("소스누락", "테스트 아티스트")
    master_missing_id = insert_music_item("마스터누락", "테스트 아티스트")
    cover_missing_id = insert_music_item("커버누락", "테스트 아티스트")

    album_master_id = main_module.db.upsert_album_master(
        "DISCOGS",
        "master-1",
        "테스트 마스터",
        "테스트 아티스트",
        "KOREA",
        1999,
        {"id": "master-1"},
    )

    main_module.db.set_owned_item_linked_album_master(linked_ok_id, album_master_id)
    main_module.db.set_owned_item_linked_album_master(source_missing_id, album_master_id)
    main_module.db.set_owned_item_linked_album_master(cover_missing_id, album_master_id)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE owned_item SET source_code = ?, source_external_id = ? WHERE id IN (?, ?, ?)",
            ("DISCOGS", "release-1", linked_ok_id, master_missing_id, cover_missing_id),
        )
        conn.execute(
            "UPDATE owned_item SET source_code = ?, source_external_id = ? WHERE id = ?",
            ("DISCOGS", "release-2", master_missing_id),
        )
        conn.execute(
            "UPDATE music_item_detail SET cover_image_url = ? WHERE owned_item_id IN (?, ?, ?)",
            ("https://covers.example.com/ok.jpg", linked_ok_id, source_missing_id, master_missing_id),
        )
        conn.execute(
            "UPDATE music_item_detail SET cover_image_url = ? WHERE owned_item_id = ?",
            ("", cover_missing_id),
        )

    payload = main_module.db.get_collection_dashboard()

    assert payload["source_unlinked_items"] == 1
    assert payload["master_unlinked_items"] == 1
    assert payload["cover_missing_items"] == 1


def test_startup_db_ready_runs_full_init_for_missing_db(monkeypatch, tmp_path):
    db_path = tmp_path / "missing.db"
    called = {"init": 0}

    def fake_init_db():
        called["init"] += 1

    monkeypatch.setattr(
        main_module.db,
        "get_settings",
        lambda: SimpleNamespace(db_path=str(db_path)),
    )
    monkeypatch.setattr(main_module.db, "init_db", fake_init_db)

    main_module.db.ensure_startup_db_ready()

    assert called["init"] == 1


def test_startup_db_ready_recreates_collectibles_tables_for_existing_db(monkeypatch, tmp_path):
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("LIBRARY_DB_PATH", str(db_path))
    main_module.db.get_settings.cache_clear()
    main_module.db.init_db()

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("DROP TABLE IF EXISTS goods_item_album_master_map")
    conn.execute("DROP TABLE IF EXISTS goods_item_artist_map")
    conn.execute("DROP TABLE IF EXISTS goods_item_label_map")
    conn.execute("DROP TABLE IF EXISTS goods_item")
    # Simulating a pre-versioning install also requires rewinding user_version,
    # otherwise ensure_startup_db_ready takes the fast path and skips the
    # legacy idempotent migration that recreates these tables.
    conn.execute("PRAGMA user_version = 0")
    conn.commit()
    conn.close()

    main_module.db.ensure_startup_db_ready()

    conn = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name IN (
                    'goods_item',
                    'goods_item_detail',
                    'goods_item_album_master_map',
                    'goods_item_artist_map',
                    'goods_item_label_map'
                  )
                """
            ).fetchall()
        }
    finally:
        conn.close()
        main_module.db.get_settings.cache_clear()

    assert tables == {
        "goods_item",
        "goods_item_detail",
        "goods_item_album_master_map",
        "goods_item_artist_map",
        "goods_item_label_map",
    }


def test_startup_db_ready_migrates_purchase_import_queue_vendor_check_for_yes24(monkeypatch, tmp_path):
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("LIBRARY_DB_PATH", str(db_path))
    main_module.db.get_settings.cache_clear()
    main_module.db.init_db()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("DROP TABLE IF EXISTS purchase_import_queue")
        conn.execute(
            """
            CREATE TABLE purchase_import_queue (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              vendor_code TEXT NOT NULL CHECK (vendor_code IN ('SAILMUSIC', 'AMAZON', 'EBAY', 'OTHER')),
              source_type TEXT NOT NULL CHECK (source_type IN ('EMAIL_HTML', 'EMAIL_TEXT', 'FILE_UPLOAD', 'MANUAL')),
              source_ref TEXT,
              email_from TEXT,
              email_subject TEXT,
              artist_name TEXT,
              item_name TEXT NOT NULL,
              media_format TEXT,
              quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
              unit_price REAL,
              line_total REAL,
              currency_code TEXT,
              purchase_date TEXT,
              seller_name TEXT,
              item_url TEXT,
              image_url TEXT,
              raw_line TEXT,
              raw_payload_json TEXT NOT NULL DEFAULT '{}',
              queue_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (queue_status IN ('PENDING', 'CREATED', 'IGNORED')),
              linked_owned_item_id INTEGER,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (linked_owned_item_id) REFERENCES owned_item(id) ON DELETE SET NULL
            )
            """
        )
        # Pre-versioning install simulation: rewind user_version so the
        # next ensure_startup_db_ready takes the slow path and migrates
        # the vendor_code CHECK constraint.
        conn.execute("PRAGMA user_version = 0")
        conn.commit()
    finally:
        conn.close()

    main_module.db.ensure_startup_db_ready()

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'purchase_import_queue'"
        ).fetchone()
        assert row is not None
        table_sql = str(row[0] or "").upper()
        assert "'ALADIN'" in table_sql
        assert "'YES24'" in table_sql
    finally:
        conn.close()

    created_ids = main_module.db.insert_purchase_import_rows(
        "YES24",
        "FILE_UPLOAD",
        [
            {
                "artist_name": "윤석철 트리오",
                "item_name": "나의 여름은 아직 안끝났어",
                "media_format": "LP",
                "quantity": 1,
                "raw_payload": {},
            }
        ],
        source_ref="migration-test",
    )

    assert len(created_ids) == 1


def test_tool_docs_supports_purchase_import_guide(monkeypatch, tmp_path):
    from app.api.ops_system import tool_docs

    guide_path = tmp_path / "purchase_mail_import.md"
    guide_path.write_text("# purchase import guide\n", encoding="utf-8")
    monkeypatch.setattr(main_module, "PROJECT_PURCHASE_IMPORT_GUIDE_PATH", guide_path)

    response = tool_docs("purchase-import")

    assert str(response.path) == str(guide_path)
    assert response.media_type == "text/markdown; charset=utf-8"


def test_operator_can_post_owned_items_sync_metadata(operator_client, monkeypatch):
    seen = {}
    def fake_sync_one_item(owned_item_id: int):
        seen["owned_item_id"] = owned_item_id
        return {
            "owned_item_id": owned_item_id,
            "source_code": "DISCOGS",
            "source_external_id": "12345",
            "status": "UPDATED",
            "updated_fields": ["barcode"],
        }
    monkeypatch.setattr(main_module, "_sync_one_item", fake_sync_one_item)

    res = operator_client.post("/owned-items/42/sync-metadata")
    assert res.status_code == 200
    assert seen["owned_item_id"] == 42
    assert res.json()["status"] == "UPDATED"


