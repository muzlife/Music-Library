"""Discogs API response mapper — pure data-transformation helpers.

Extracted from app/main.py. Functions are stateless transforms over raw
Discogs API dicts; the cover-preview helpers are the only ones that touch
the filesystem or network.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse
from uuid import uuid4

import httpx
from fastapi import HTTPException

from .. import db
from ..services.providers import get_album_master_variants, get_source_release_snapshot


# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------

def _resolve_project_root() -> Path:
    raw = os.getenv("LIBRARY_PROJECT_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


ALLOWED_IMAGE_CONTENT_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "image/tiff": ".tif",
    "image/heic": ".heic",
    "image/heif": ".heif",
}

DISCOGS_COVER_PREVIEW_CACHE_DIR: Path = (
    _resolve_project_root() / "data" / "discogs_cover_preview_cache"
)

_PURCHASE_ITEM_FETCH_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ---------------------------------------------------------------------------
# Pure text / scalar helpers
# ---------------------------------------------------------------------------

def _discogs_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _discogs_catalog_no(value: Any) -> str | None:
    text = _discogs_text(value)
    if not text:
        return None
    text = re.sub(r"^(?:cat\s*#?\s*:?)\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^[\s;:,/|]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text or text in {"-", "--", "---"}:
        return None
    return text


def _discogs_string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _discogs_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _discogs_release_year(raw: dict[str, Any]) -> int | None:
    year_raw = raw.get("year")
    try:
        year = int(year_raw) if year_raw is not None else None
    except (TypeError, ValueError):
        return None
    if year is None or year <= 0:
        return None
    return year


# ---------------------------------------------------------------------------
# Format / image / track / identifier helpers
# ---------------------------------------------------------------------------

def _discogs_format_items(raw: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    formats = raw.get("formats")
    if not isinstance(formats, list):
        return out
    for row in formats:
        if not isinstance(row, dict):
            continue
        name = _discogs_text(row.get("name"))
        descriptions = row.get("descriptions")
        desc_parts = [str(v).strip() for v in descriptions] if isinstance(descriptions, list) else []
        desc_parts = [v for v in desc_parts if v]
        qty = _discogs_text(row.get("qty"))
        text = _discogs_text(row.get("text"))
        joined = f"{name} ({', '.join(desc_parts)})" if name and desc_parts else (name or ", ".join(desc_parts))
        if not joined:
            continue
        bits = [joined]
        if qty:
            bits.append(f"qty {qty}")
        if text:
            bits.append(text)
        out.append(
            {
                "name": name,
                "descriptions": desc_parts,
                "qty": qty,
                "text": text,
                "display": " / ".join(bits),
            }
        )
    return out


def _discogs_format_values(raw: dict[str, Any]) -> list[str]:
    out = []
    for item in _discogs_format_items(raw):
        out.append(str(item.get("display") or ""))
    return [v for v in out if v]


def _discogs_primary_format(raw: dict[str, Any]) -> str | None:
    formats = raw.get("formats")
    if not isinstance(formats, list) or not formats:
        return None
    first = formats[0]
    if not isinstance(first, dict):
        return None
    return _discogs_text(first.get("name"))


def _discogs_image_items(raw: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    images = raw.get("images")
    if not isinstance(images, list):
        return out
    for row in images:
        if not isinstance(row, dict):
            continue
        uri = _discogs_text(row.get("uri")) or _discogs_text(row.get("uri150"))
        if not uri or uri in seen:
            continue
        seen.add(uri)
        out.append(
            {
                "type": _discogs_text(row.get("type")) or "unknown",
                "uri": uri,
                "uri150": _discogs_text(row.get("uri150")),
                "resource_url": _discogs_text(row.get("resource_url")),
                "width": row.get("width"),
                "height": row.get("height"),
            }
        )
    return out


def _discogs_artist_value(raw: dict[str, Any]) -> str | None:
    artists = raw.get("artists")
    if not isinstance(artists, list) or not artists:
        return None
    first = artists[0]
    if not isinstance(first, dict):
        return None
    return _discogs_text(first.get("anv")) or _discogs_text(first.get("name"))


def _discogs_track_items(raw: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    rows = raw.get("tracklist")
    if not isinstance(rows, list):
        return out

    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        position = _discogs_text(row.get("position")) or str(idx + 1)
        title = _discogs_text(row.get("title"))
        duration = _discogs_text(row.get("duration"))
        track_type = _discogs_text(row.get("type_")) or "track"
        sub_tracks = row.get("sub_tracks")
        sub_track_titles: list[str] = []
        if isinstance(sub_tracks, list):
            for sub in sub_tracks:
                if not isinstance(sub, dict):
                    continue
                sub_title = _discogs_text(sub.get("title"))
                if sub_title:
                    sub_track_titles.append(sub_title)
        if not title and sub_track_titles:
            title = " / ".join(sub_track_titles)
        if not title:
            continue

        extraartists = row.get("extraartists")
        credit_bits: list[str] = []
        if isinstance(extraartists, list):
            for extra in extraartists:
                if not isinstance(extra, dict):
                    continue
                name = _discogs_text(extra.get("anv")) or _discogs_text(extra.get("name"))
                role = _discogs_text(extra.get("role"))
                if name and role:
                    credit_bits.append(f"{name} ({role})")
                elif name:
                    credit_bits.append(name)

        out.append(
            {
                "position": position,
                "title": title,
                "duration": duration,
                "type": track_type,
                "sub_tracks": sub_track_titles,
                "credits": credit_bits,
                "display": f"{position} {title}".strip(),
            }
        )
    return out


def _discogs_identifiers(
    raw: dict[str, Any],
) -> tuple[list[str], list[str], str | None, list[dict[str, Any]]]:
    runout_values: list[str] = []
    other_values: list[str] = []
    barcode: str | None = None
    identifier_items: list[dict[str, Any]] = []
    identifiers = raw.get("identifiers")
    if not isinstance(identifiers, list):
        return runout_values, other_values, barcode, identifier_items

    for row in identifiers:
        if not isinstance(row, dict):
            continue
        type_text = str(row.get("type") or "").strip()
        value_text = _discogs_text(row.get("value"))
        if not value_text:
            continue
        description = _discogs_text(row.get("description"))
        identifier_items.append(
            {
                "type": type_text or None,
                "value": value_text,
                "description": description,
            }
        )
        lower_type = type_text.lower()
        if lower_type == "barcode" and not barcode:
            barcode = re.sub(r"[^0-9Xx]", "", value_text) or value_text
        if "matrix" in lower_type or "runout" in lower_type:
            runout_values.append(value_text)
            continue
        other_values.append(f"{type_text}: {value_text}" if type_text else value_text)
    return runout_values, other_values, barcode, identifier_items


# ---------------------------------------------------------------------------
# Credit / company / label helpers
# ---------------------------------------------------------------------------

def _discogs_credit_items(raw: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    rows = raw.get("extraartists")
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = _discogs_text(row.get("anv")) or _discogs_text(row.get("name"))
        role = _discogs_text(row.get("role"))
        tracks = _discogs_text(row.get("tracks"))
        if not name and not role and not tracks:
            continue
        out.append(
            {
                "name": name,
                "role": role,
                "tracks": tracks,
                "join": _discogs_text(row.get("join")),
            }
        )
    return out


def _discogs_credits(raw: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for item in _discogs_credit_items(raw):
        name = _discogs_text(item.get("name"))
        role = _discogs_text(item.get("role"))
        tracks = _discogs_text(item.get("tracks"))
        core = f"{name} ({role})" if name and role else (name or role or "")
        if not core:
            continue
        out.append(f"{core} [{tracks}]" if tracks else core)
    return out


def _discogs_company_items(raw: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    rows = raw.get("companies")
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = _discogs_text(row.get("name"))
        entity = _discogs_text(row.get("entity_type_name"))
        catno = _discogs_catalog_no(row.get("catno"))
        if not (name or entity or catno):
            continue
        out.append(
            {
                "entity_type": entity,
                "name": name,
                "catno": catno,
            }
        )
    return out


def _discogs_companies(raw: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for item in _discogs_company_items(raw):
        bits = [v for v in [item.get("entity_type"), item.get("name"), item.get("catno")] if v]
        if bits:
            out.append(" | ".join(bits))
    return out


def _discogs_label_items(raw: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    rows = raw.get("labels")
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = _discogs_text(row.get("name"))
        catno = _discogs_catalog_no(row.get("catno"))
        if not (name or catno):
            continue
        out.append(
            {
                "name": name,
                "catno": catno,
            }
        )
    return out


def _discogs_labels(raw: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for item in _discogs_label_items(raw):
        name = _discogs_text(item.get("name"))
        catno = _discogs_catalog_no(item.get("catno"))
        if name and catno:
            out.append(f"{name} / {catno}")
        elif name:
            out.append(name)
    return out


# ---------------------------------------------------------------------------
# Variant comparison
# ---------------------------------------------------------------------------

def _discogs_compare_variants(
    release_id: str,
    master_id: str | None,
    selected: dict[str, Any],
    compare_limit: int,
) -> list[dict[str, Any]]:
    if not master_id:
        return []
    variants = get_album_master_variants(
        source="DISCOGS",
        master_external_id=master_id,
        limit=max(compare_limit * 3, 20),
        include_details=True,
    )
    if not variants:
        return []

    def normalize_compare(v: Any) -> str:
        text = _discogs_text(v)
        return text if text else "-"

    selected_track_count = int(selected.get("track_count") or 0)
    selected_runout_sample = normalize_compare(selected.get("runout_sample"))
    selected_release_id = str(release_id).strip()
    compare_rows: list[dict[str, Any]] = []
    for row in variants:
        external_id = str(row.get("external_id") or "").strip()
        if not external_id or external_id == selected_release_id:
            continue

        differences: list[str] = []
        fields: list[tuple[str, str]] = [
            ("format_name", "포맷"),
            ("label_name", "레이블"),
            ("catalog_no", "카탈로그"),
            ("barcode", "바코드"),
            ("country", "국가"),
            ("release_year", "발매년"),
        ]
        for key, label in fields:
            selected_val = normalize_compare(selected.get(key))
            other_val = normalize_compare(row.get(key))
            if selected_val != other_val:
                differences.append(f"{label}: {selected_val} -> {other_val}")

        other_track_count = len(row.get("track_list") or [])
        if selected_track_count != other_track_count:
            differences.append(f"트랙 수: {selected_track_count} -> {other_track_count}")

        raw_detail = row.get("raw_detail")
        if not isinstance(raw_detail, dict):
            raw_candidate = row.get("raw")
            if isinstance(raw_candidate, dict):
                nested = raw_candidate.get("release_detail")
                raw_detail = nested if isinstance(nested, dict) else None
        other_runout_values: list[str] = []
        if isinstance(raw_detail, dict):
            other_runout_values, _, _, _ = _discogs_identifiers(raw_detail)
        other_runout_sample = normalize_compare(" | ".join(other_runout_values[:2]) if other_runout_values else None)
        if selected_runout_sample != "-" or other_runout_sample != "-":
            if selected_runout_sample != other_runout_sample:
                differences.append(f"Matrix/Runout: {selected_runout_sample} -> {other_runout_sample}")

        if not differences:
            continue

        compare_rows.append(
            {
                "external_id": external_id,
                "title": _discogs_text(row.get("title")),
                "format_name": _discogs_text(row.get("format_name")),
                "label_name": _discogs_text(row.get("label_name")),
                "catalog_no": _discogs_catalog_no(row.get("catalog_no")),
                "barcode": _discogs_text(row.get("barcode")),
                "country": _discogs_text(row.get("country")),
                "release_year": row.get("release_year"),
                "cover_image_url": _discogs_text(row.get("cover_image_url")),
                "track_count": other_track_count,
                "runout_sample": None if other_runout_sample == "-" else other_runout_sample,
                "difference_summary": differences,
            }
        )

    compare_rows.sort(key=lambda x: len(x.get("difference_summary") or []), reverse=True)
    return compare_rows[:compare_limit]


# ---------------------------------------------------------------------------
# Artist name helpers
# ---------------------------------------------------------------------------

def _contains_hangul_artist_name(value: Any) -> bool:
    return bool(re.search(r"[ㄱ-ㆎ가-힣]", str(value or "")))


def _discogs_artist_name_needs_localization(value: Any) -> bool:
    text = str(value or "").strip() or None
    return bool(text) and not _contains_hangul_artist_name(text)


# ---------------------------------------------------------------------------
# Cover preview cache helpers
# ---------------------------------------------------------------------------

def _discogs_cover_preview_cache_name(release_id: str) -> str:
    return re.sub(r"[^0-9A-Za-z._-]+", "_", str(release_id or "").strip()) or "discogs-release"


def _discogs_cover_preview_cached_file(release_id: str) -> tuple[Path, str] | None:
    cache_name = _discogs_cover_preview_cache_name(release_id)
    for path in sorted(DISCOGS_COVER_PREVIEW_CACHE_DIR.glob(f"{cache_name}.*")):
        if not path.is_file():
            continue
        media_type = next(
            (ct for ct, ext in ALLOWED_IMAGE_CONTENT_TYPES.items() if ext == path.suffix.lower()),
            None,
        ) or "application/octet-stream"
        return path, media_type
    return None


def _discogs_cover_preview_source_url(release_id: str) -> str | None:
    external_id = str(release_id or "").strip()
    if not external_id:
        return None
    owned_items = db.list_owned_items_by_source_external_ids("DISCOGS", [external_id])
    for item in owned_items:
        cover_url = str(item.get("cover_image_url") or "").strip()
        if cover_url:
            return cover_url

    snapshot = get_source_release_snapshot(source="DISCOGS", external_id=external_id)
    if isinstance(snapshot, dict):
        cover_url = str(snapshot.get("cover_image_url") or "").strip()
        if cover_url:
            return cover_url
        raw_detail = snapshot.get("raw")
        if isinstance(raw_detail, dict):
            for image in _discogs_image_items(raw_detail):
                image_url = str(image.get("uri") or "").strip()
                if image_url:
                    return image_url
    return None


def _fetch_discogs_cover_preview_bytes(release_id: str, cover_url: str) -> tuple[bytes, str]:
    external_id = str(release_id or "").strip()
    target_url = str(cover_url or "").strip()
    if not external_id or not target_url:
        raise HTTPException(status_code=404, detail="discogs cover preview unavailable")

    release_url = f"https://www.discogs.com/release/{quote(external_id)}"
    request_headers = dict(_PURCHASE_ITEM_FETCH_HEADERS)
    request_headers.setdefault("Accept", "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8")

    try:
        with httpx.Client(headers=request_headers, follow_redirects=True, timeout=20.0) as client:
            try:
                client.get(release_url)
            except httpx.HTTPError:
                pass
            image_response = client.get(target_url, headers={"Referer": release_url})
            image_response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"discogs cover preview fetch failed: {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"discogs cover preview fetch failed: {exc}") from exc

    media_type = str(image_response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    if not media_type.startswith("image/"):
        raise HTTPException(status_code=502, detail="discogs cover preview returned non-image content")
    return image_response.content, media_type


def _ensure_discogs_cover_preview(release_id: str) -> tuple[Path, str]:
    external_id = str(release_id or "").strip()
    if not external_id:
        raise HTTPException(status_code=404, detail="discogs release not found")

    cached = _discogs_cover_preview_cached_file(external_id)
    if cached is not None:
        return cached

    cover_url = _discogs_cover_preview_source_url(external_id)
    if not cover_url:
        raise HTTPException(status_code=404, detail="discogs cover preview unavailable")

    image_bytes, media_type = _fetch_discogs_cover_preview_bytes(external_id, cover_url)
    cache_name = _discogs_cover_preview_cache_name(external_id)
    suffix = ALLOWED_IMAGE_CONTENT_TYPES.get(media_type)
    if not suffix:
        suffix = Path(urlparse(cover_url).path).suffix.lower() or ".img"
    DISCOGS_COVER_PREVIEW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for stale_path in DISCOGS_COVER_PREVIEW_CACHE_DIR.glob(f"{cache_name}.*"):
        if stale_path.is_file():
            stale_path.unlink()
    target_path = DISCOGS_COVER_PREVIEW_CACHE_DIR / f"{cache_name}{suffix}"
    tmp_path = target_path.with_suffix(f"{target_path.suffix}.tmp-{uuid4().hex}")
    tmp_path.write_bytes(image_bytes)
    tmp_path.replace(target_path)
    return target_path, media_type
