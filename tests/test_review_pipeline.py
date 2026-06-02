import pytest
from unittest.mock import patch, MagicMock


def test_wikipedia_picks_album_page_over_artist():
    """앨범 title이 포함된 페이지를 아티스트 페이지보다 우선 선택."""
    from app.services.providers import fetch_wikipedia_album_review

    search_results = [
        {"title": "Humming Urban Stereo"},
        {"title": "Shabbat Shalom (album)"},
        {"title": "Korean indie music"},
    ]
    extract_data = {
        "query": {
            "pages": {
                "123": {"extract": "Shabbat Shalom is a studio album by Humming Urban Stereo."}
            }
        }
    }

    import json, urllib.request
    call_count = [0]

    def fake_urlopen(req, timeout=10):
        call_count[0] += 1
        mock_resp = MagicMock()
        if call_count[0] == 1:
            mock_resp.read.return_value = json.dumps(
                {"query": {"search": search_results}}
            ).encode()
        else:
            mock_resp.read.return_value = json.dumps(extract_data).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    with patch.object(urllib.request, "urlopen", side_effect=fake_urlopen):
        result = fetch_wikipedia_album_review("Humming Urban Stereo", "Shabbat Shalom")

    assert result is not None
    assert " " not in result["review_url"]
    assert "Shabbat_Shalom" in result["review_url"]
    assert result["review_source"] == "WIKIPEDIA"


def test_wikipedia_returns_none_when_no_album_page():
    """앨범 title이 포함된 페이지가 없으면 None 반환."""
    from app.services.providers import fetch_wikipedia_album_review

    search_results = [
        {"title": "Humming Urban Stereo"},
        {"title": "Korean indie music"},
    ]

    import json, urllib.request

    def fake_urlopen(req, timeout=10):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"query": {"search": search_results}}
        ).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    with patch.object(urllib.request, "urlopen", side_effect=fake_urlopen):
        result = fetch_wikipedia_album_review("Humming Urban Stereo", "Shabbat Shalom")

    assert result is None


def test_fetch_review_from_url_extracts_article_text():
    """<article> 태그에서 본문 텍스트를 추출한다."""
    from app.services.providers import fetch_review_from_url

    html = b"""<html><body>
        <nav>nav stuff</nav>
        <article>
          <p>This album changed everything.</p>
          <p>A masterpiece of modern music.</p>
        </article>
    </body></html>"""

    import httpx
    mock_resp = MagicMock()
    mock_resp.content = html
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.get", return_value=mock_resp):
        text = fetch_review_from_url("https://example.com/review")

    assert text is not None
    assert "This album changed everything" in text


def test_fetch_review_from_url_returns_none_on_error():
    """fetch 실패 시 None 반환."""
    from app.services.providers import fetch_review_from_url
    import httpx

    with patch("httpx.get", side_effect=httpx.TimeoutException("timeout")):
        result = fetch_review_from_url("https://example.com/review")

    assert result is None
