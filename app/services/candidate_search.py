from __future__ import annotations
import re
from typing import Any
from .providers import (
    get_source_release_snapshot,
    get_album_master_variants,
    resolve_release_master_reference,
    search_discogs_artist_name_variations,
    search_music_metadata,
)
from .discogs_mapper import _discogs_catalog_no


def _clean_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _normalize_lookup_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    return re.sub(r"\s+", " ", text)


def _normalize_compact_lookup_text(value: Any) -> str:
    return re.sub(r"[\s\-\._/]+", "", _normalize_lookup_text(value))


def _lookup_match_level(query_value: Any, candidate_value: Any) -> int:
    query_text = _normalize_lookup_text(query_value)
    candidate_text = _normalize_lookup_text(candidate_value)
    if not query_text or not candidate_text:
        return 0
    if candidate_text == query_text:
        return 3
    if query_text in candidate_text:
        return 2
    query_tokens = set(query_text.split())
    candidate_tokens = set(candidate_text.split())
    if bool(query_tokens) and query_tokens.issubset(candidate_tokens):
        return 1
    return 0


def _lookup_compact_match_level(query_value: Any, candidate_value: Any) -> int:
    query_text = _normalize_compact_lookup_text(query_value)
    candidate_text = _normalize_compact_lookup_text(candidate_value)
    if not query_text or not candidate_text:
        return 0
    if candidate_text == query_text:
        return 3
    if query_text in candidate_text:
        return 2
    return 0


def _candidate_artist_match_level(candidate: dict[str, Any], artist_or_brand: str | None) -> int:
    levels = [_lookup_match_level(artist_or_brand, candidate.get("artist_or_brand"))]
    raw = candidate.get("raw")
    if isinstance(raw, dict):
        for term in raw.get("artist_search_terms") or raw.get("search_terms") or []:
            levels.append(_lookup_match_level(artist_or_brand, term))
    return max(levels)


def _candidate_title_match_level(candidate: dict[str, Any], title: str | None) -> int:
    return max(
        _lookup_match_level(title, candidate.get("title")),
        _lookup_compact_match_level(title, candidate.get("title")),
    )


def _candidate_matches_artist_filter(candidate: dict[str, Any], artist_or_brand: str | None) -> bool:
    return _candidate_artist_match_level(candidate, artist_or_brand) > 0


def _candidate_matches_title_filter(candidate: dict[str, Any], title: str | None) -> bool:
    return _candidate_title_match_level(candidate, title) > 0


def _is_maniadb_artist_candidate(candidate: dict[str, Any]) -> bool:
    external_id = str(candidate.get("external_id") or "").strip().lower()
    if external_id.startswith("artist:"):
        return True
    raw = candidate.get("raw")
    if isinstance(raw, dict) and str(raw.get("kind") or "").strip().lower() == "artist":
        return True
    return False


def _filter_maniadb_candidates(
    candidates: list[dict[str, Any]],
    *,
    artist_or_brand: str | None = None,
    title: str | None = None,
) -> list[dict[str, Any]]:
    narrowed = [
        candidate
        for candidate in candidates
        if str(candidate.get("source") or "").strip().upper() == "MANIADB"
    ]
    release_candidates = [candidate for candidate in narrowed if not _is_maniadb_artist_candidate(candidate)]
    if release_candidates:
        narrowed = release_candidates
    if artist_or_brand:
        matched_artist = [candidate for candidate in narrowed if _candidate_matches_artist_filter(candidate, artist_or_brand)]
        if matched_artist:
            narrowed = matched_artist
    if title:
        matched_title = [candidate for candidate in narrowed if _candidate_matches_title_filter(candidate, title)]
        if matched_title:
            narrowed = matched_title
    if artist_or_brand or title:
        narrowed = sorted(
            narrowed,
            key=lambda candidate: (
                _candidate_artist_match_level(candidate, artist_or_brand),
                _candidate_title_match_level(candidate, title),
                float(candidate.get("confidence") or 0.0),
            ),
            reverse=True,
        )
    return narrowed


_DIRECT_MB_RELEASE_PATTERN = re.compile(
    r"(?i)(?:^release:|musicbrainz\.org/release/)?([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$"
)


def _parse_direct_source_reference(query: str | None, *, source: str = "AUTO") -> dict[str, str] | None:
    text = str(query or "").strip()
    if not text:
        return None
    source_u = str(source or "AUTO").strip().upper() or "AUTO"

    def allows(code: str) -> bool:
        return source_u in {"AUTO", code}

    if allows("DISCOGS"):
        release_match = re.search(r"(?i)(?:^release:|discogs\.com/release/)(\d+)", text)
        if release_match:
            return {"source": "DISCOGS", "kind": "release", "external_id": str(release_match.group(1))}
        master_match = re.search(r"(?i)(?:^master:|discogs\.com/master(?:s)?/)(\d+)", text)
        if master_match:
            return {"source": "DISCOGS", "kind": "master", "external_id": str(master_match.group(1))}

    if allows("MANIADB"):
        album_match = re.search(r"(?i)(?:^album:|maniadb\.com/album/)(\d+(?::\d+)?)", text)
        if album_match:
            return {"source": "MANIADB", "kind": "album", "external_id": str(album_match.group(1))}

    if allows("ALADIN"):
        aladin_match = re.search(
            r"(?i)(?:aladin\.co\.kr/(?:shop/w[Pp]roduct\.aspx|ttb/api/ItemLookUp\.aspx).*?[?&]ItemId=|^aladin[:/])(\d+)",
            text,
        )
        if aladin_match:
            return {"source": "ALADIN", "kind": "release", "external_id": str(aladin_match.group(1))}

    return None


def _metadata_candidate_from_snapshot(source: str, external_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    raw = snapshot.get("raw") if isinstance(snapshot.get("raw"), dict) else {}
    title = (
        _clean_text(raw.get("title"))
        or _clean_text(snapshot.get("title"))
        or f"{str(source or '').strip().upper()} Release #{external_id}"
    )
    country = _clean_text(raw.get("country")) or _clean_text(snapshot.get("pressing_country"))
    return {
        "source": str(source or "").strip().upper(),
        "external_id": str(external_id or "").strip(),
        "title": title,
        "artist_or_brand": _clean_text(snapshot.get("artist_or_brand")),
        "release_year": snapshot.get("release_year"),
        "released_date": _clean_text(snapshot.get("released_date")),
        "country": country,
        "format_name": _clean_text(snapshot.get("format_name")),
        "barcode": _clean_text(snapshot.get("barcode")),
        "catalog_no": _discogs_catalog_no(snapshot.get("catalog_no")),
        "label_name": _clean_text(snapshot.get("label_name")),
        "cover_image_url": _clean_text(snapshot.get("cover_image_url")),
        "track_list": list(snapshot.get("track_list") or []),
        "media_type": _clean_text(snapshot.get("media_type")),
        "release_type": _clean_text(snapshot.get("release_type")),
        "domain_code": _clean_text(snapshot.get("domain_code")),
        "genres": list(snapshot.get("genres") or []),
        "styles": list(snapshot.get("styles") or []),
        "disc_count": snapshot.get("disc_count"),
        "speed_rpm": snapshot.get("speed_rpm"),
        "has_obi": snapshot.get("has_obi"),
        "runout_matrix": list(snapshot.get("runout_matrix") or []),
        "pressing_country": _clean_text(snapshot.get("pressing_country")),
        "source_notes": _clean_text(snapshot.get("source_notes")),
        "credits": list(snapshot.get("credits") or []),
        "identifier_items": list(snapshot.get("identifier_items") or []),
        "image_items": list(snapshot.get("image_items") or []),
        "company_items": list(snapshot.get("company_items") or []),
        "series": list(snapshot.get("series") or []),
        "format_items": list(snapshot.get("format_items") or []),
        "track_items": list(snapshot.get("track_items") or []),
        "label_items": list(snapshot.get("label_items") or []),
        "confidence": 1.0,
        "raw": raw,
    }


def _dedupe_metadata_candidates(candidates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    dedup: dict[tuple[str, str], dict[str, Any]] = {}
    for row in candidates:
        candidate = dict(row)
        source = str(candidate.get("source") or "").strip().upper()
        external_id = str(candidate.get("external_id") or "").strip()
        if not source or not external_id:
            continue
        current = dedup.get((source, external_id))
        if current is None or float(candidate.get("confidence") or 0.0) > float(current.get("confidence") or 0.0):
            dedup[(source, external_id)] = candidate
    merged = sorted(dedup.values(), key=lambda item: float(item.get("confidence") or 0.0), reverse=True)
    return merged[: max(1, int(limit or 1))]


def _build_direct_metadata_candidates(query: str | None, *, source: str = "AUTO", limit: int = 5) -> list[dict[str, Any]] | None:
    parsed = _parse_direct_source_reference(query, source=source)
    if not parsed:
        return None
    source_code = parsed["source"]
    kind = parsed["kind"]
    external_id = parsed["external_id"]
    if kind == "release":
        snapshot = get_source_release_snapshot(source=source_code, external_id=external_id)
        if not snapshot:
            return []
        return [_metadata_candidate_from_snapshot(source_code, external_id, snapshot)]
    if source_code == "DISCOGS" and kind == "master":
        variants = get_album_master_variants(source="DISCOGS", master_external_id=external_id, limit=limit, include_details=True)
        return _dedupe_metadata_candidates(variants, limit)
    if source_code == "MANIADB" and kind == "album":
        variants = get_album_master_variants(source="MANIADB", master_external_id=external_id, limit=limit, include_details=False)
        return _dedupe_metadata_candidates(variants, limit)
    return []


def _clean_track_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()]


def _clean_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        values = value
    elif isinstance(value, str):
        values = [part.strip() for part in re.split(r"[,\n|]", value)]
    else:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for v in values:
        text = str(v or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _clean_dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for row in value:
        if isinstance(row, dict):
            out.append(row)
    return out


def _clean_runout_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    text = _clean_text(value)
    if not text:
        return []
    return [part.strip() for part in re.split(r"[|\n]", text) if part.strip()]


def _normalize_has_obi_input(value: Any) -> bool | None:
    if isinstance(value, bool):
        return True if value else None
    if value in {0, 1}:
        return True if int(value) == 1 else None
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y"}:
            return True
        if lowered in {"0", "false", "no", "n"}:
            return None
    return None


def _clean_goods_image_urls(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    text = _clean_text(value)
    if not text:
        return []
    return [part.strip() for part in re.split(r"[\n|]", text) if part.strip()]


def _normalize_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value) if value is not None and str(value).strip() else None
    except (TypeError, ValueError):
        parsed = None
    if parsed is not None and parsed <= 0:
        parsed = None
    return parsed


def _candidate_collector_base(candidate: dict[str, Any]) -> dict[str, Any]:
    row = candidate if isinstance(candidate, dict) else {}
    source_code = str(row.get("source") or "").strip().upper()
    return {
        "source_notes": _clean_text(row.get("source_notes")),
        "credits": _clean_string_list(row.get("credits")),
        "identifier_items": _clean_dict_list(row.get("identifier_items")),
        "image_items": _clean_dict_list(row.get("image_items")),
        "company_items": _clean_dict_list(row.get("company_items")),
        "series": _clean_string_list(row.get("series")),
        "format_items": _clean_dict_list(row.get("format_items")),
        "track_items": _clean_dict_list(row.get("track_items")),
        "label_items": _clean_dict_list(row.get("label_items")),
        "runout_matrix": _clean_runout_list(row.get("runout_matrix")),
        "pressing_country": source_code == "DISCOGS" and _clean_text(row.get("pressing_country")) or None,
    }


def _is_blank_text(value: Any) -> bool:
    return _clean_text(value) is None
