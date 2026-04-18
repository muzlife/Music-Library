from __future__ import annotations

import importlib
from types import SimpleNamespace


artist_context = importlib.import_module("app.services.artist_context")


def test_normalize_artist_name_is_whitespace_and_case_normalized() -> None:
    assert artist_context.normalize_artist_name("  The   Beatles  ") == "the beatles"


def test_build_artist_context_returns_available_on_exact_normalized_match(monkeypatch) -> None:
    def fake_wikipedia_summary(artist_name: str):
        return {
            "artist_name": "The  Beatles",
            "summary": "Legendary rock band",
            "country": "UK",
            "active_years": "1960-1970",
            "genres": ["rock"],
            "url": "https://en.wikipedia.org/wiki/The_Beatles",
        }

    monkeypatch.setattr(artist_context, "fetch_wikipedia_summary", fake_wikipedia_summary)
    monkeypatch.setattr(artist_context, "search_musicbrainz_artist", lambda artist_name: None)

    result = artist_context.build_artist_context("  the   beatles  ", category="cd")

    assert result["available"] is True
    assert result["artist_name"] == "the   beatles"
    assert result["summary"] == "Legendary rock band"
    assert any(link["label"] == "Wikipedia" and link["url"] == "https://en.wikipedia.org/wiki/The_Beatles" for link in result["links"])


def test_build_artist_context_non_music_category_skips_lookup(monkeypatch) -> None:
    monkeypatch.setattr(artist_context, "fetch_wikipedia_summary", lambda _: (_ for _ in ()).throw(AssertionError("Wikipedia lookup should be skipped")))
    monkeypatch.setattr(artist_context, "search_musicbrainz_artist", lambda _: (_ for _ in ()).throw(AssertionError("MusicBrainz lookup should be skipped")))

    result = artist_context.build_artist_context("Nirvana", category="BOOK")

    assert result["available"] is False
    assert result["artist_name"] == "Nirvana"
    assert result["links"] == []


def test_build_artist_context_translates_summary_with_deepl_for_non_english_locale(monkeypatch) -> None:
    def fake_wikipedia_summary(artist_name: str):
        return {
            "artist_name": "The Beatles",
            "summary": "Legendary rock band",
            "image_url": "https://upload.wikimedia.org/beatles.jpg",
            "country": "UK",
            "active_years": "1960-1970",
            "genres": ["rock"],
            "url": "https://en.wikipedia.org/wiki/The_Beatles",
        }

    monkeypatch.setattr(artist_context, "fetch_wikipedia_summary", fake_wikipedia_summary)
    monkeypatch.setattr(artist_context, "search_musicbrainz_artist", lambda artist_name: None)
    monkeypatch.setattr(
        artist_context,
        "translate_text_with_deepl",
        lambda text, locale: "전설적인 록 밴드" if text == "Legendary rock band" and locale == "ko" else text,
    )

    result = artist_context.build_artist_context("The Beatles", category="CD", locale="ko")

    assert result["available"] is True
    assert result["summary"] == "전설적인 록 밴드"
    assert result["summary_original"] == "Legendary rock band"
    assert result["image_url"] == "https://upload.wikimedia.org/beatles.jpg"


def test_build_artist_context_retries_wikipedia_with_music_qualifier_for_ambiguous_artist(monkeypatch) -> None:
    def fake_wikipedia_summary(artist_name: str):
        if artist_name == "Prince":
            return {
                "artist_name": "Prince",
                "description": "male ruler",
                "summary": "A prince is the ruler of a principality.",
                "url": "https://en.wikipedia.org/wiki/Prince",
            }
        if artist_name == "Prince (musician)":
            return {
                "artist_name": "Prince (musician)",
                "description": "American singer-songwriter",
                "summary": "Prince was an American singer-songwriter and musician.",
                "url": "https://en.wikipedia.org/wiki/Prince_(musician)",
            }
        raise AssertionError(f"unexpected wikipedia lookup: {artist_name}")

    monkeypatch.setattr(artist_context, "fetch_wikipedia_summary", fake_wikipedia_summary)
    monkeypatch.setattr(artist_context, "search_wikipedia_titles", lambda query, limit=5: ["Prince (musician)"] if query == "Prince musician" else [])
    monkeypatch.setattr(artist_context, "search_musicbrainz_artist", lambda artist_name: None)

    result = artist_context.build_artist_context("Prince", category="LP")

    assert result["available"] is True
    assert result["summary"] == "Prince was an American singer-songwriter and musician."
    assert any(link["label"] == "Wikipedia" and link["url"] == "https://en.wikipedia.org/wiki/Prince_(musician)" for link in result["links"])


def test_build_artist_context_rejects_non_music_wikipedia_match_when_no_music_candidate_found(monkeypatch) -> None:
    monkeypatch.setattr(
        artist_context,
        "fetch_wikipedia_summary",
        lambda artist_name: {
            "artist_name": "Prince",
            "description": "male ruler",
            "summary": "A prince is the ruler of a principality.",
            "url": "https://en.wikipedia.org/wiki/Prince",
        },
    )
    monkeypatch.setattr(artist_context, "search_wikipedia_titles", lambda query, limit=5: [])
    monkeypatch.setattr(artist_context, "search_musicbrainz_artist", lambda artist_name: None)

    result = artist_context.build_artist_context("Prince", category="LP")

    assert result["available"] is False
    assert result["summary"] is None
    assert any(link["label"] == "Wikipedia" for link in result["links"])


def test_build_artist_context_strips_discogs_suffixes_before_lookup(monkeypatch) -> None:
    looked_up: list[str] = []

    def fake_wikipedia_music_summary(artist_name: str):
        looked_up.append(artist_name)
        return {
            "artist_name": "Jacqueline du Pré",
            "description": "British cellist",
            "summary": "Jacqueline du Pré was a British cellist.",
            "url": "https://en.wikipedia.org/wiki/Jacqueline_du_Pr%C3%A9",
        }

    monkeypatch.setattr(artist_context, "fetch_wikipedia_music_summary", fake_wikipedia_music_summary)
    monkeypatch.setattr(artist_context, "search_musicbrainz_artist", lambda artist_name: None)

    result = artist_context.build_artist_context("Jacqueline du Pré*", category="LP")

    assert looked_up == ["Jacqueline du Pré"]
    assert result["available"] is True
    assert result["artist_name"] == "Jacqueline du Pré"
    assert any(link["label"] == "Wikipedia" and "Jacqueline_du_Pr%C3%A9" in link["url"] for link in result["links"])


def test_build_artist_context_strips_discogs_numeric_suffix_before_lookup(monkeypatch) -> None:
    looked_up: list[str] = []

    def fake_wikipedia_music_summary(artist_name: str):
        looked_up.append(artist_name)
        return {
            "artist_name": "Prince (musician)",
            "description": "American singer-songwriter",
            "summary": "Prince was an American singer-songwriter and musician.",
            "url": "https://en.wikipedia.org/wiki/Prince_(musician)",
        }

    monkeypatch.setattr(artist_context, "fetch_wikipedia_music_summary", fake_wikipedia_music_summary)
    monkeypatch.setattr(artist_context, "search_musicbrainz_artist", lambda artist_name: None)

    result = artist_context.build_artist_context("Prince (2)", category="LP")

    assert looked_up == ["Prince"]
    assert result["available"] is True
    assert result["artist_name"] == "Prince"


def test_build_artist_context_accepts_classical_performer_wikipedia_summary(monkeypatch) -> None:
    def fake_wikipedia_summary(artist_name: str):
        assert artist_name == "Jacqueline du Pré"
        return {
            "artist_name": "Jacqueline du Pré",
            "description": "British cellist",
            "summary": "Jacqueline du Pré was a British cellist.",
            "url": "https://en.wikipedia.org/wiki/Jacqueline_du_Pr%C3%A9",
        }

    monkeypatch.setattr(artist_context, "fetch_wikipedia_summary", fake_wikipedia_summary)
    monkeypatch.setattr(artist_context, "search_musicbrainz_artist", lambda artist_name: None)

    result = artist_context.build_artist_context("Jacqueline du Pré*", category="LP")

    assert result["available"] is True
    assert result["artist_name"] == "Jacqueline du Pré"
    assert result["summary"] == "Jacqueline du Pré was a British cellist."


def test_build_artist_context_cleans_discogs_suffix_on_unavailable_payload(monkeypatch) -> None:
    monkeypatch.setattr(artist_context, "fetch_wikipedia_music_summary", lambda artist_name: None)
    monkeypatch.setattr(artist_context, "search_musicbrainz_artist", lambda artist_name: None)

    result = artist_context.build_artist_context("Prince (2)", category="LP")

    assert result["available"] is False
    assert result["artist_name"] == "Prince"


def test_build_artist_context_accepts_korean_artist_when_wikipedia_uses_romanized_title(monkeypatch) -> None:
    monkeypatch.setattr(artist_context, "fetch_wikipedia_music_summary", lambda artist_name: None)
    monkeypatch.setattr(
        artist_context,
        "fetch_wikipedia_summary",
        lambda artist_name: {
            "artist_name": "Cho Yong-pil",
            "description": "South Korean singer (born 1950)",
            "summary": "Cho Yong-pil is a South Korean singer-songwriter.",
            "url": "https://en.wikipedia.org/wiki/Cho_Yong-pil",
            "type": "standard",
        },
    )
    monkeypatch.setattr(
        artist_context,
        "search_musicbrainz_artist",
        lambda artist_name: {
            "artist_name": "조용필",
            "sort_name": "Cho, Yong-pil",
            "country": "KR",
            "active_years": "1950",
            "resource_url": "https://musicbrainz.org/artist/f1fa5a60-33f7-42fb-8c59-de7a0765e6d0",
            "aliases": [
                {"name": "Cho Yong Pil"},
                {"name": "CHO Yong Pil"},
            ],
        },
    )
    monkeypatch.setattr(artist_context, "translate_text_with_deepl", lambda text, locale: text)

    result = artist_context.build_artist_context("조용필", category="CD", locale="ko")

    assert result["available"] is True
    assert result["artist_name"] == "조용필"
    assert result["country"] == "KR"
    assert any(link["label"] == "Wikipedia" and "Cho_Yong-pil" in link["url"] for link in result["links"])
    assert any(link["label"] == "MusicBrainz" and "f1fa5a60-33f7-42fb-8c59-de7a0765e6d0" in link["url"] for link in result["links"])


def test_build_artist_context_accepts_romanized_query_when_musicbrainz_primary_name_is_korean(monkeypatch) -> None:
    monkeypatch.setattr(artist_context, "fetch_wikipedia_music_summary", lambda artist_name: None)
    monkeypatch.setattr(
        artist_context,
        "fetch_wikipedia_summary",
        lambda artist_name: {
            "artist_name": "Cho Yong-pil",
            "description": "South Korean singer (born 1950)",
            "summary": "Cho Yong-pil is a South Korean singer-songwriter.",
            "url": "https://en.wikipedia.org/wiki/Cho_Yong-pil",
            "type": "standard",
        },
    )
    monkeypatch.setattr(
        artist_context,
        "search_musicbrainz_artist",
        lambda artist_name: {
            "artist_name": "조용필",
            "sort_name": "Cho, Yong-pil",
            "country": "KR",
            "active_years": "1950",
            "resource_url": "https://musicbrainz.org/artist/f1fa5a60-33f7-42fb-8c59-de7a0765e6d0",
            "aliases": [
                {"name": "Cho Yong Pil"},
                {"name": "CHO Yong Pil"},
            ],
        },
    )
    monkeypatch.setattr(artist_context, "translate_text_with_deepl", lambda text, locale: text)

    result = artist_context.build_artist_context("Cho Yong-pil", category="CD", locale="ko")

    assert result["available"] is True
    assert result["artist_name"] == "Cho Yong-pil"
    assert result["country"] == "KR"


def test_resolve_musicbrainz_preferred_korean_name_prefers_primary_hangul_name(monkeypatch) -> None:
    monkeypatch.setattr(
        artist_context,
        "search_musicbrainz_artist",
        lambda artist_name: {
            "artist_name": "백예린",
            "sort_name": "Baek, Yerin",
            "country": "KR",
            "aliases": [{"name": "Yerin Baek"}],
        },
    )

    assert artist_context.resolve_musicbrainz_preferred_korean_name("Yerin Baek") == "백예린"


def test_resolve_musicbrainz_preferred_korean_name_uses_hangul_alias_for_korean_artist(monkeypatch) -> None:
    monkeypatch.setattr(
        artist_context,
        "search_musicbrainz_artist",
        lambda artist_name: {
            "artist_name": "Yun Seok Cheol Trio",
            "sort_name": "Yun Seok Cheol Trio",
            "country": "KR",
            "aliases": [{"name": "윤석철 트리오"}],
        },
    )

    assert artist_context.resolve_musicbrainz_preferred_korean_name("Yun Seok Cheol Trio") == "윤석철 트리오"


def test_resolve_musicbrainz_preferred_korean_name_skips_non_korean_artist(monkeypatch) -> None:
    monkeypatch.setattr(
        artist_context,
        "search_musicbrainz_artist",
        lambda artist_name: {
            "artist_name": "The Beatles",
            "sort_name": "Beatles, The",
            "country": "GB",
            "aliases": [{"name": "비틀즈"}],
        },
    )

    assert artist_context.resolve_musicbrainz_preferred_korean_name("The Beatles") is None


def test_build_artist_context_falls_back_to_korean_wikipedia_for_korean_artist(monkeypatch) -> None:
    monkeypatch.setattr(artist_context, "fetch_wikipedia_music_summary", lambda artist_name: None)
    monkeypatch.setattr(artist_context, "fetch_wikipedia_summary", lambda artist_name: None)
    monkeypatch.setattr(
        artist_context,
        "_fetch_wikipedia_summary_for_language",
        lambda artist_name, language="en": {
            "artist_name": "어떤날",
            "description": "대한민국의 포크 밴드",
            "summary": "어떤날은 대한민국의 포크 밴드이다.",
            "url": "https://ko.wikipedia.org/wiki/%EC%96%B4%EB%96%A4%EB%82%A0",
            "type": "standard",
        }
        if language == "ko"
        else None,
    )
    monkeypatch.setattr(
        artist_context,
        "search_musicbrainz_artist",
        lambda artist_name: {
            "artist_name": "어떤날",
            "sort_name": "Eoddeonnal",
            "country": "KR",
            "active_years": "1984",
            "resource_url": "https://musicbrainz.org/artist/example",
            "aliases": None,
        },
    )
    monkeypatch.setattr(artist_context, "translate_text_with_deepl", lambda text, locale: text)

    result = artist_context.build_artist_context("어떤날", category="CD", locale="ko")

    assert result["available"] is True
    assert result["artist_name"] == "어떤날"
    assert result["summary"] == "어떤날은 대한민국의 포크 밴드이다."
    assert result["country"] == "KR"


def test_translate_text_with_deepl_uses_header_authentication_and_json_payload(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class DummyResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"translations": [{"text": "연결 확인"}]}

    def fake_post(url: str, *, headers=None, json=None, timeout=None, **kwargs):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        captured["extra_kwargs"] = kwargs
        return DummyResponse()

    monkeypatch.setattr(
        artist_context,
        "get_settings",
        lambda: SimpleNamespace(
            deepl_auth_key="test-key:fx",
            deepl_base_url="https://api-free.deepl.com/v2/translate",
        ),
    )
    monkeypatch.setattr(artist_context.httpx, "post", fake_post)

    translated = artist_context.translate_text_with_deepl("Connection check", "ko")

    assert translated == "연결 확인"
    assert captured["url"] == "https://api-free.deepl.com/v2/translate"
    assert captured["headers"] == {
        "Authorization": "DeepL-Auth-Key test-key:fx",
        "User-Agent": "hahahoho-library/0.1 (ops translation)",
    }
    assert captured["json"] == {
        "text": ["Connection check"],
        "target_lang": "KO",
    }
    assert captured["extra_kwargs"] == {}
