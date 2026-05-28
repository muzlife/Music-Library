import pytest
import json
import time
from fastapi.testclient import TestClient
from app import db
from app.main import app

def test_search_filters_extra_functionality(operator_client: TestClient) -> None:
    db.ensure_startup_db_ready()

    # Create temporary records for testing filters
    owned_ids = []
    master_ids = []

    try:
        # Helper to create master + owned_item + detail
        def create_fixture(
            title: str,
            is_limited_edition: int = 0,
            is_second_hand: int = 1,
            is_promotional_not_for_sale: int = 0,
            signature_type: str = "NONE",
            format_name: str = "CD",
            package_contents: str = "None",
            release_year: int = 2020,
            created_at: str = None,
            updated_at: str = None
        ):
            c_time = created_at or db.utc_now_iso()
            u_time = updated_at or db.utc_now_iso()
            with db.get_write_conn() as conn:
                cur = conn.execute(
                    """
                    INSERT INTO album_master
                      (source_code, source_master_id, title, artist_or_brand,
                       sort_artist_name, domain_code, release_year, raw_json,
                       created_at, updated_at)
                    VALUES ('MANUAL', ?, ?, 'Test Filter Artist', NULL,
                            'UNKNOWN', ?, '{}', ?, ?)
                    """,
                    (f"test-filter-{title}", title, release_year, c_time, u_time),
                )
                mid = int(cur.lastrowid)
                master_ids.append(mid)

                cur = conn.execute(
                    """
                    INSERT INTO owned_item
                      (category, status, quantity, item_name_override,
                       size_group, is_second_hand, signature_type, created_at, updated_at)
                    VALUES ('CD', 'IN_COLLECTION', 1, ?, 'STD', ?, ?, ?, ?)
                    """,
                    (title, is_second_hand, signature_type, c_time, u_time),
                )
                oid = int(cur.lastrowid)
                owned_ids.append(oid)

                conn.execute(
                    """
                    INSERT INTO album_master_member
                      (album_master_id, owned_item_id, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (mid, oid, c_time),
                )

                conn.execute(
                    """
                    INSERT INTO music_item_detail
                      (owned_item_id, format_name, package_contents, is_limited_edition, is_promotional_not_for_sale, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        oid,
                        format_name,
                        package_contents,
                        is_limited_edition,
                        is_promotional_not_for_sale,
                        c_time,
                        u_time,
                    ),
                )
            return mid, oid

        # 1. Create limited edition
        mid_limited, oid_limited = create_fixture(
            "Limited Album",
            is_limited_edition=1,
            format_name="Gatefold Special Edition",
            package_contents="Booklet Poster Sticker",
            release_year=2022,
            created_at="2026-01-01T12:00:00Z",
            updated_at="2026-01-01T12:00:00Z"
        )
        # 2. Create new product
        mid_new, oid_new = create_fixture(
            "New Product Album",
            is_second_hand=0,
            format_name="Jewel Case",
            package_contents="Booklet",
            release_year=2021,
            created_at="2026-01-02T12:00:00Z",
            updated_at="2026-01-02T12:00:00Z"
        )
        # 3. Create promo copy
        mid_promo, oid_promo = create_fixture(
            "Promo Copy Album",
            is_promotional_not_for_sale=1,
            format_name="Digipak",
            package_contents="Sticker",
            release_year=2020,
            created_at="2026-01-03T12:00:00Z",
            updated_at="2026-01-03T12:00:00Z"
        )
        # 4. Create signature direct
        mid_sig_direct, oid_sig_direct = create_fixture(
            "Direct Signature Album",
            signature_type="IN_PERSON",
            format_name="Sleeve",
            package_contents="Lyric Sheet",
            release_year=2019,
            created_at="2026-01-04T12:00:00Z",
            updated_at="2026-01-04T12:00:00Z"
        )
        # 5. Create signature purchase
        mid_sig_purchase, oid_sig_purchase = create_fixture(
            "Purchase Signature Album",
            signature_type="PURCHASE_INCLUDED",
            format_name="Box Set",
            package_contents="Photobook Disc",
            release_year=2018,
            created_at="2026-01-05T12:00:00Z",
            updated_at="2026-01-05T12:00:00Z"
        )

        # Now query via API with filters and verify we get exactly what we want.
        
        # Test: is_limited = True
        res = operator_client.get("/album-masters", params={"is_limited": "true", "media_only": "true"})
        assert res.status_code == 200
        titles = [item["title"] for item in res.json()]
        assert "Limited Album" in titles
        assert "New Product Album" not in titles
        assert "Promo Copy Album" not in titles

        # Test: is_new = True
        res = operator_client.get("/album-masters", params={"is_new": "true", "media_only": "true"})
        assert res.status_code == 200
        titles = [item["title"] for item in res.json()]
        assert "New Product Album" in titles
        assert "Limited Album" not in titles

        # Test: is_promo = True
        res = operator_client.get("/album-masters", params={"is_promo": "true", "media_only": "true"})
        assert res.status_code == 200
        titles = [item["title"] for item in res.json()]
        assert "Promo Copy Album" in titles
        assert "Limited Album" not in titles

        # Test: signature_types = IN_PERSON
        res = operator_client.get("/album-masters", params={"signature_types": ["IN_PERSON"], "media_only": "true"})
        assert res.status_code == 200
        titles = [item["title"] for item in res.json()]
        assert "Direct Signature Album" in titles
        assert "Purchase Signature Album" not in titles

        # Test: signature_types = PURCHASE_INCLUDED
        res = operator_client.get("/album-masters", params={"signature_types": ["PURCHASE_INCLUDED"], "media_only": "true"})
        assert res.status_code == 200
        titles = [item["title"] for item in res.json()]
        assert "Purchase Signature Album" in titles
        assert "Direct Signature Album" not in titles

        # Test: multiple signature_types
        res = operator_client.get("/album-masters", params={"signature_types": ["IN_PERSON", "PURCHASE_INCLUDED"], "media_only": "true"})
        assert res.status_code == 200
        titles = [item["title"] for item in res.json()]
        assert "Direct Signature Album" in titles
        assert "Purchase Signature Album" in titles

        # Test: owned_item_id filter
        res = operator_client.get("/album-masters", params={"owned_item_id": oid_new, "media_only": "true"})
        assert res.status_code == 200
        titles = [item["title"] for item in res.json()]
        assert titles == ["New Product Album"]

        # Test: packaging filter
        res = operator_client.get("/album-masters", params={"packaging": "Special Edition", "media_only": "true"})
        assert res.status_code == 200
        titles = [item["title"] for item in res.json()]
        assert "Limited Album" in titles
        assert "New Product Album" not in titles

        # Test: package_contents filter
        res = operator_client.get("/album-masters", params={"package_contents": "Poster", "media_only": "true"})
        assert res.status_code == 200
        titles = [item["title"] for item in res.json()]
        assert "Limited Album" in titles
        assert "Promo Copy Album" not in titles

        # Test: sorting CREATED_DESC
        res = operator_client.get("/album-masters", params={"sort_mode": "CREATED_DESC", "media_only": "true"})
        assert res.status_code == 200
        titles = [item["title"] for item in res.json() if item["title"] in ["Limited Album", "New Product Album", "Promo Copy Album", "Direct Signature Album", "Purchase Signature Album"]]
        # Since we added them in order (Limited -> New -> Promo -> Direct -> Purchase), CREATED_DESC should return them reversed:
        assert titles == [
            "Purchase Signature Album",
            "Direct Signature Album",
            "Promo Copy Album",
            "New Product Album",
            "Limited Album"
        ]

        # Test: sorting RELEASE_DESC
        res = operator_client.get("/album-masters", params={"sort_mode": "RELEASE_DESC", "media_only": "true"})
        assert res.status_code == 200
        titles = [item["title"] for item in res.json() if item["title"] in ["Limited Album", "New Product Album", "Promo Copy Album", "Direct Signature Album", "Purchase Signature Album"]]
        # Years: Limited (2022) > New (2021) > Promo (2020) > Direct (2019) > Purchase (2018)
        assert titles == [
            "Limited Album",
            "New Product Album",
            "Promo Copy Album",
            "Direct Signature Album",
            "Purchase Signature Album"
        ]

        # Test: empty text fields with only checkbox (is_limited = true)
        res = operator_client.get("/album-masters", params={
            "artist_or_brand": "",
            "item_name": "",
            "catalog_no": "",
            "barcode": "",
            "is_limited": "true",
            "media_only": "true"
        })
        assert res.status_code == 200
        titles = [item["title"] for item in res.json()]
        assert "Limited Album" in titles
        assert "New Product Album" not in titles

    finally:
        # Cleanup
        with db.get_write_conn() as conn:
            for oid in owned_ids:
                conn.execute("DELETE FROM music_item_detail WHERE owned_item_id = ?", (oid,))
                conn.execute("DELETE FROM album_master_member WHERE owned_item_id = ?", (oid,))
                conn.execute("DELETE FROM owned_item WHERE id = ?", (oid,))
            for mid in master_ids:
                conn.execute("DELETE FROM album_master_member WHERE album_master_id = ?", (mid,))
                conn.execute("DELETE FROM album_master WHERE id = ?", (mid,))
