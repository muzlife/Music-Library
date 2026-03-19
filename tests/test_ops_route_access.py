import app.main as main_module


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


def test_operator_cannot_open_admin_route(operator_client):
    res = operator_client.get("/admin", follow_redirects=False, headers={"accept": "text/html"})
    assert res.status_code == 303
    assert res.headers["location"] == "/ops"


def test_admin_root_redirects_to_ops(admin_client):
    res = admin_client.get("/", follow_redirects=False, headers={"accept": "text/html"})
    assert res.status_code == 303
    assert res.headers["location"] == "/ops"


def test_authenticated_ops_serves_index_html(operator_client):
    res = operator_client.get("/ops", headers={"accept": "text/html"})
    _assert_index_shell_response(res)


def test_authenticated_ops_cabinets_serves_index_html(operator_client):
    res = operator_client.get("/ops/cabinets", headers={"accept": "text/html"})
    _assert_index_shell_response(res)


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
                "label_name": "서울음반",
                "catalog_no": "JLS-120123",
                "barcode": "8800000000000",
                "cover_image_url": "https://example.com/cover.jpg",
                "signature_type": "NONE",
                "status": "IN_COLLECTION",
                "current_slot_code": "CAB-A-02-05",
                "current_slot_display_name": "A장 2층 5칸",
                "current_cabinet_name": "A장",
                "current_column_code": "02",
                "current_cell_code": "05",
                "previous_slot_code": "CAB-A-01-04",
                "previous_slot_display_name": "A장 1층 4칸",
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
