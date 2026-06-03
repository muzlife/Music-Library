from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote, quote_plus, urlencode, urlparse

import httpx

from app.config import get_settings


MUSIC_CATEGORIES = {"LP", "CD", "CASSETTE", "8TRACK", "DIGITAL", "REEL_TO_REEL"}
DEEPL_TARGET_LANGUAGE_BY_LOCALE = {
    "ko": "KO",
    "ja": "JA",
}
MUSIC_CONTEXT_KEYWORDS = (
    "musician",
    "singer",
    "songwriter",
    "rapper",
    "cellist",
    "violinist",
    "pianist",
    "guitarist",
    "drummer",
    "bassist",
    "conductor",
    "orchestra",
    "composer",
    "classical",
    "mezzo-soprano",
    "soprano",
    "tenor",
    "baritone",
    "band",
    "rock band",
    "pop singer",
    "record producer",
    "dj",
    "vocalist",
    "가수",
    "음악가",
    "싱어송라이터",
    "래퍼",
    "밴드",
    "록 밴드",
    "포크 밴드",
    "작곡가",
    "피아니스트",
    "첼리스트",
    "바이올리니스트",
    "기타리스트",
    "드러머",
    "베이시스트",
)


def normalize_artist_name(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def strip_discogs_artist_suffixes(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"\*+\s*$", "", text).strip()
    text = re.sub(r"\s+\(\d+\)\s*$", "", text).strip()
    return text


def normalize_artist_lookup_name(value: str) -> str:
    text = re.sub(r"\s+", " ", strip_discogs_artist_suffixes(value))
    if not text:
        return ""
    return text


def _contains_hangul(value: str) -> bool:
    return bool(re.search(r"[\u3131-\u318e\uac00-\ud7a3]", str(value or "")))


def is_music_category(category: str | None) -> bool:
    if category is None:
        return True
    return str(category or "").strip().upper() in MUSIC_CATEGORIES


def _extract_name(raw: dict[str, Any] | None) -> str:
    if not raw:
        return ""
    for key in ("artist_name", "name", "title"):
        text = str(raw.get(key) or "").strip()
        if text:
            return text
    return ""


def _extract_genres(raw: dict[str, Any] | None) -> list[str]:
    if not raw:
        return []
    genres = raw.get("genres")
    if isinstance(genres, str):
        return [genre.strip() for genre in genres.split(",") if genre.strip()]
    if isinstance(genres, list):
        return [str(item).strip() for item in genres if str(item).strip()]
    return []


def _extract_image_url(raw: dict[str, Any] | None) -> str | None:
    if not raw:
        return None
    direct = str(raw.get("image_url") or "").strip()
    if direct:
        return direct
    for key in ("thumbnail", "originalimage"):
        candidate = raw.get(key)
        if not isinstance(candidate, dict):
            continue
        source = str(candidate.get("source") or "").strip()
        if source:
            return source
    return None


def _safe_wikipedia_article_url(candidate: dict[str, Any] | None) -> str | None:
    if not candidate:
        return None
    if str(candidate.get("type") or "").strip().lower() == "disambiguation":
        return None
    for key in ("url", "wiki_url", "article_url", "page_url"):
        raw = candidate.get(key)
        if not raw:
            continue
        parsed = urlparse(str(raw).strip())
        hostname = str(parsed.hostname or "").lower()
        if hostname.endswith("wikipedia.org") and parsed.path.startswith("/wiki/"):
            lower_path = parsed.path.lower()
            if "disambiguation" in lower_path:
                continue
            return str(raw).strip()
    return None


def _normalize_wikipedia_match_name(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+\([^()]+\)\s*$", "", text)
    return normalize_artist_name(text)


def _normalize_artist_match_key(value: str) -> str:
    text = _normalize_wikipedia_match_name(value)
    if not text:
        return ""
    text = re.sub(r"[^\w\s]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _artist_name_match_keys(value: str) -> set[str]:
    normalized = _normalize_wikipedia_match_name(value)
    if not normalized:
        return set()
    simplified = _normalize_artist_match_key(value)
    compact = simplified.replace(" ", "")
    return {item for item in (normalized, simplified, compact) if item}


def _artist_names_match(left: str, right: str) -> bool:
    left_keys = _artist_name_match_keys(left)
    right_keys = _artist_name_match_keys(right)
    return bool(left_keys and right_keys and left_keys.intersection(right_keys))


def _extract_musicbrainz_match_names(raw: dict[str, Any] | None) -> list[str]:
    if not raw:
        return []
    names: list[str] = []
    for key in ("artist_name", "name", "sort_name", "sort-name"):
        text = str(raw.get(key) or "").strip()
        if text:
            names.append(text)
    aliases = raw.get("aliases")
    if isinstance(aliases, list):
        for alias in aliases:
            if isinstance(alias, dict):
                for key in ("name", "sort_name", "sort-name"):
                    text = str(alias.get(key) or "").strip()
                    if text:
                        names.append(text)
            else:
                text = str(alias or "").strip()
                if text:
                    names.append(text)
    return names


def _extract_musicbrainz_korean_names(raw: dict[str, Any] | None) -> list[str]:
    if not raw:
        return []
    names: list[str] = []
    seen: set[str] = set()
    for candidate in _extract_musicbrainz_match_names(raw):
        text = str(candidate or "").strip()
        if not text or not _contains_hangul(text):
            continue
        key = normalize_artist_name(text)
        if not key or key in seen:
            continue
        seen.add(key)
        names.append(text)
    return names


def _wikipedia_search_url(artist_name: str) -> str:
    return f"https://en.wikipedia.org/w/index.php?{urlencode({'search': artist_name}, encoding='utf-8')}"


def _discogs_search_url(artist_name: str) -> str:
    return f"https://www.discogs.com/search/?{urlencode({'q': artist_name, 'type': 'artist'}, encoding='utf-8')}"


def _fetch_wikipedia_summary_for_language(artist_name: str, language: str = "en") -> dict[str, Any] | None:
    query = str(artist_name or "").strip()
    if not query:
        return None

    encoded_query = quote(query, safe="")
    normalized_language = str(language or "en").strip().lower() or "en"
    url = f"https://{normalized_language}.wikipedia.org/api/rest_v1/page/summary/{encoded_query}"
    response = httpx.get(
        url,
        headers={"User-Agent": get_settings().musicbrainz_user_agent},
        timeout=5.0,
    )
    response.raise_for_status()
    data = response.json()

    title = str(data.get("title") or "").strip()
    summary = data.get("extract")
    if not isinstance(summary, str):
        return None

    return {
        "artist_name": title or query,
        "description": str(data.get("description") or "").strip() or None,
        "summary": summary,
        "url": str((data.get("content_urls") or {}).get("desktop", {}).get("page", "")).strip(),
        "type": str(data.get("type") or "").strip() or None,
        "image_url": _extract_image_url(data),
        "country": data.get("country"),
        "active_years": data.get("active_years"),
        "genres": data.get("genres"),
    }


def fetch_wikipedia_summary(artist_name: str) -> dict[str, Any] | None:
    return _fetch_wikipedia_summary_for_language(artist_name, language="en")


def search_wikipedia_titles(query: str, limit: int = 5) -> list[str]:
    search_query = str(query or "").strip()
    if not search_query:
        return []

    response = httpx.get(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "list": "search",
            "srsearch": search_query,
            "format": "json",
            "srlimit": max(1, int(limit)),
        },
        headers={"User-Agent": get_settings().musicbrainz_user_agent},
        timeout=5.0,
    )
    response.raise_for_status()
    payload = response.json() or {}
    items = ((payload.get("query") or {}).get("search")) if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    results: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if title:
            results.append(title)
    return results


def _is_music_related_wikipedia_summary(raw: dict[str, Any] | None) -> bool:
    if not raw:
        return False
    text = " ".join(
        str(raw.get(key) or "").strip()
        for key in ("artist_name", "description", "summary")
        if str(raw.get(key) or "").strip()
    ).casefold()
    return any(keyword in text for keyword in MUSIC_CONTEXT_KEYWORDS)


def _wikipedia_summary_matches_artist(raw: dict[str, Any] | None, artist_name: str) -> bool:
    candidate_name = _extract_name(raw)
    return bool(candidate_name) and _artist_names_match(candidate_name, artist_name)


def fetch_wikipedia_music_summary(artist_name: str) -> dict[str, Any] | None:
    direct = fetch_wikipedia_summary(artist_name)
    if direct and _wikipedia_summary_matches_artist(direct, artist_name) and _is_music_related_wikipedia_summary(direct):
        return direct

    qualifiers = ("musician", "band", "singer", "rapper", "composer")
    for qualifier in qualifiers:
        for title in search_wikipedia_titles(f"{artist_name} {qualifier}"):
            if _normalize_wikipedia_match_name(title) != normalize_artist_name(artist_name):
                continue
            candidate = fetch_wikipedia_summary(title)
            if candidate and _wikipedia_summary_matches_artist(candidate, artist_name) and _is_music_related_wikipedia_summary(candidate):
                return candidate
    return None


def search_musicbrainz_artist(artist_name: str) -> dict[str, Any] | None:
    query = str(artist_name or "").strip()
    if not query:
        return None

    response = httpx.get(
        "https://musicbrainz.org/ws/2/artist/",
        params={"query": query, "fmt": "json", "limit": 1},
        headers={"User-Agent": get_settings().musicbrainz_user_agent},
        timeout=5.0,
    )
    response.raise_for_status()
    data = response.json() or {}
    artists = data.get("artists")
    if not isinstance(artists, list) or not artists:
        return None

    first = artists[0]
    if not isinstance(first, dict):
        return None

    life_span = first.get("life-span") if isinstance(first.get("life-span"), dict) else {}
    begin = str((life_span.get("begin") or "").split("-")[0]).strip()
    end = str((life_span.get("end") or "").split("-")[0]).strip()
    if begin and end:
        active_years = f"{begin}-{end}"
    elif begin:
        active_years = begin
    else:
        active_years = None

    return {
        "artist_name": str(first.get("name") or "").strip() or query,
        "sort_name": str(first.get("sort-name") or "").strip() or None,
        "summary": first.get("disambiguation"),
        "url": str(first.get("url") or "").strip(),
        "country": str(first.get("country") or "").strip() or None,
        "active_years": active_years,
        "genres": first.get("genres") if isinstance(first.get("genres"), list) else None,
        "resource_url": str((first.get("_links") or {}).get("self", {}).get("href") or "").strip(),
        "aliases": first.get("aliases") if isinstance(first.get("aliases"), list) else None,
    }


def resolve_musicbrainz_preferred_korean_name(artist_name: str) -> str | None:
    query = normalize_artist_lookup_name(artist_name)
    if not query:
        return None
    try:
        musicbrainz_data = search_musicbrainz_artist(query)
    except Exception:
        return None
    if not musicbrainz_data:
        return None

    country = str(musicbrainz_data.get("country") or "").strip().upper()
    if country != "KR":
        return None

    if not any(_artist_names_match(query, candidate_name) for candidate_name in _extract_musicbrainz_match_names(musicbrainz_data)):
        return None

    korean_names = _extract_musicbrainz_korean_names(musicbrainz_data)
    return korean_names[0] if korean_names else None


def discogs_artist_search_link(artist_name: str) -> dict[str, str]:
    return {"label": "Discogs", "url": _discogs_search_url(artist_name)}


def _normalize_translation_locale(locale: str | None) -> str | None:
    normalized = str(locale or "").strip().lower()
    if not normalized:
        return None
    normalized = normalized.split("-", 1)[0]
    return normalized or None


def _resolve_deepl_api_root(auth_key: str, base_url: str | None) -> str:
    raw_base_url = str(base_url or "").strip()
    if raw_base_url:
        parsed = urlparse(raw_base_url)
        hostname = str(parsed.hostname or "").strip().lower()
        if hostname in {"api-free.deepl.com", "api.deepl.com"}:
            scheme = str(parsed.scheme or "https").strip() or "https"
            return f"{scheme}://{hostname}"
    if str(auth_key or "").strip().endswith(":fx"):
        return "https://api-free.deepl.com"
    return "https://api.deepl.com"


def _resolve_deepl_api_url(auth_key: str, base_url: str | None, path: str) -> str:
    normalized_path = str(path or "").strip().lstrip("/")
    return f"{_resolve_deepl_api_root(auth_key, base_url)}/v2/{normalized_path}"


def fetch_deepl_usage(auth_key: str, base_url: str | None) -> dict[str, Any]:
    normalized_auth_key = str(auth_key or "").strip()
    usage_url = _resolve_deepl_api_url(normalized_auth_key, base_url, "usage")
    response = httpx.get(
        usage_url,
        headers={
            "Authorization": f"DeepL-Auth-Key {normalized_auth_key}",
            "User-Agent": "__PROJECT_SLUG__-library/0.1 (ops translation)",
        },
        timeout=5.0,
    )
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def translate_text_with_deepl(text: str, locale: str | None) -> str:
    content = str(text or "").strip()
    target_locale = _normalize_translation_locale(locale)
    if not content or not target_locale:
        return content
    target_lang = DEEPL_TARGET_LANGUAGE_BY_LOCALE.get(target_locale)
    if not target_lang:
        return content
    settings = get_settings()
    auth_key = str(settings.deepl_auth_key or "").strip()
    base_url = str(settings.deepl_base_url or "").strip()
    if not auth_key or not base_url:
        return content
    response = httpx.post(
        _resolve_deepl_api_url(auth_key, base_url, "translate"),
        headers={
            "Authorization": f"DeepL-Auth-Key {auth_key}",
            "User-Agent": "__PROJECT_SLUG__-library/0.1 (ops translation)",
        },
        json={
            "text": [content],
            "target_lang": target_lang,
        },
        timeout=5.0,
    )
    response.raise_for_status()
    payload = response.json() or {}
    translations = payload.get("translations")
    if not isinstance(translations, list) or not translations:
        return content
    translated = str((translations[0] or {}).get("text") or "").strip()
    return translated or content


def _build_unavailable_payload(artist_name: str, links: list[dict[str, str]]) -> dict[str, Any]:
    display_artist_name = str(artist_name).strip()
    cleaned_artist_name = strip_discogs_artist_suffixes(display_artist_name)
    return {
        "available": False,
        "artist_name": str(cleaned_artist_name or display_artist_name).strip(),
        "summary": None,
        "summary_original": None,
        "image_url": None,
        "country": None,
        "active_years": None,
        "genres": [],
        "links": links,
    }


def build_artist_context(artist_name: str, category: str | None = None, locale: str | None = None) -> dict[str, Any]:
    display_artist_name = str(artist_name or "").strip()
    display_artist_name_clean = strip_discogs_artist_suffixes(display_artist_name)
    lookup_artist_name = normalize_artist_lookup_name(artist_name)
    normalized_input = normalize_artist_name(lookup_artist_name)
    if not normalized_input:
        return _build_unavailable_payload("", [])

    if not is_music_category(category):
        return _build_unavailable_payload(artist_name, [])

    links: list[dict[str, str]] = [discogs_artist_search_link(artist_name)]

    try:
        wikipedia_data = fetch_wikipedia_music_summary(lookup_artist_name)
    except Exception:
        wikipedia_data = None

    try:
        musicbrainz_data = search_musicbrainz_artist(lookup_artist_name)
    except Exception:
        musicbrainz_data = None

    if not wikipedia_data:
        try:
            direct_wikipedia_data = fetch_wikipedia_summary(lookup_artist_name)
        except Exception:
            direct_wikipedia_data = None
        if direct_wikipedia_data and _is_music_related_wikipedia_summary(direct_wikipedia_data):
            wikipedia_data = direct_wikipedia_data
    if not wikipedia_data and (
        _normalize_translation_locale(locale) == "ko" or re.search(r"[\u3131-\u318E\uAC00-\uD7A3]", lookup_artist_name)
    ):
        try:
            localized_wikipedia_data = _fetch_wikipedia_summary_for_language(lookup_artist_name, language="ko")
        except Exception:
            localized_wikipedia_data = None
        if localized_wikipedia_data and _is_music_related_wikipedia_summary(localized_wikipedia_data):
            wikipedia_data = localized_wikipedia_data

    wiki_url = _safe_wikipedia_article_url(wikipedia_data) or _wikipedia_search_url(lookup_artist_name or artist_name)
    links.append({"label": "Wikipedia", "url": wiki_url})

    mb_url = str((musicbrainz_data or {}).get("resource_url") or "").strip()
    if musicbrainz_data:
        if not mb_url:
            mb_url = str((musicbrainz_data or {}).get("url") or "").strip()
            if not mb_url and (artist := _extract_name(musicbrainz_data)):
                mb_url = f"https://musicbrainz.org/ws/2/artist/?query={quote_plus(artist)}&fmt=json"
        if mb_url:
            links.append({"label": "MusicBrainz", "url": mb_url})

    wiki_name = _extract_name(wikipedia_data)
    mb_match_names = _extract_musicbrainz_match_names(musicbrainz_data)
    wiki_is_disambiguation = str((wikipedia_data or {}).get("type") or "").strip().lower() == "disambiguation"

    wiki_matches_query = bool(wiki_name) and _artist_names_match(wiki_name, lookup_artist_name)
    wiki_matches_musicbrainz = bool(wiki_name) and any(
        _artist_names_match(wiki_name, candidate_name) for candidate_name in mb_match_names
    )
    query_matches_musicbrainz = any(
        _artist_names_match(lookup_artist_name, candidate_name) for candidate_name in mb_match_names
    )
    if musicbrainz_data and wiki_name and not wiki_matches_musicbrainz:
        return _build_unavailable_payload(artist_name, links)

    if wiki_data := wikipedia_data:
        if (wiki_matches_query or (wiki_matches_musicbrainz and query_matches_musicbrainz)) and not wiki_is_disambiguation:
            summary_original = None
            summary_text = wiki_data.get("summary")
            country = str(wiki_data.get("country") or (musicbrainz_data or {}).get("country") or "").strip() or None
            active_years = str(wiki_data.get("active_years") or (musicbrainz_data or {}).get("active_years") or "").strip() or None
            genres = _extract_genres(wiki_data) or _extract_genres(musicbrainz_data)
            if isinstance(summary_text, str) and summary_text.strip():
                summary_original = summary_text
                try:
                    summary_text = translate_text_with_deepl(summary_text, locale)
                except Exception:
                    summary_text = wiki_data.get("summary")
                if str(summary_text or "").strip() == str(summary_original or "").strip():
                    summary_original = None
            return {
                "available": True,
                "artist_name": str(display_artist_name_clean if display_artist_name_clean != display_artist_name else display_artist_name).strip(),
                "summary": summary_text,
                "summary_original": summary_original,
                "image_url": _extract_image_url(wiki_data),
                "country": country,
                "active_years": active_years,
                "genres": genres,
                "links": links,
            }
        return _build_unavailable_payload(artist_name, links)

    if musicbrainz_data and query_matches_musicbrainz:
        return _build_unavailable_payload(artist_name, links)

    return _build_unavailable_payload(artist_name, links)
