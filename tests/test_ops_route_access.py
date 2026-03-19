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
