from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..config import get_settings


MUSIC_CATEGORIES = {"LP", "CD", "CASSETTE"}


@dataclass
class MatchResult:
    confidence: float
    review_status: str
    review_note: str | None
    candidate: dict[str, Any] | None


def compose_query(row: dict[str, Any]) -> str:
    artist = (row.get("artist_or_brand") or "").strip()
    title = (row.get("title") or "").strip()
    catalog_no = (row.get("catalog_no") or "").strip()
    label_name = (row.get("label_name") or "").strip()

    parts = [p for p in [artist, title, catalog_no, label_name] if p]
    return " ".join(parts)


def validate_row_for_ingest(row: dict[str, Any], default_category: str | None = None) -> tuple[bool, str | None, str | None]:
    category = (row.get("category") or default_category or "").strip().upper()
    has_discogs_release_id = bool((row.get("discogs_release_id") or row.get("source_external_id") or "").strip())
    if not category:
        if not has_discogs_release_id:
            return False, None, "category is required"

    if category in MUSIC_CATEGORIES:
        has_barcode = bool((row.get("barcode") or "").strip())
        has_catalog = bool((row.get("catalog_no") or "").strip())
        has_runout = bool((row.get("runout") or row.get("runout_matrix") or "").strip())
        if not (has_barcode or has_catalog or has_runout or has_discogs_release_id):
            return False, category, "music item requires one of barcode/catalog_no/runout"

    return True, category, None


def classify_candidate(candidates: list[dict[str, Any]]) -> MatchResult:
    settings = get_settings()
    if not candidates:
        return MatchResult(
            confidence=0.0,
            review_status="NEEDS_REVIEW",
            review_note="no metadata candidate",
            candidate=None,
        )

    top = candidates[0]
    confidence = float(top.get("confidence", 0.0))
    if confidence >= settings.confidence_auto_approve:
        return MatchResult(
            confidence=confidence,
            review_status="AUTO_APPROVED",
            review_note=None,
            candidate=top,
        )

    if confidence >= settings.confidence_review:
        return MatchResult(
            confidence=confidence,
            review_status="NEEDS_REVIEW",
            review_note="medium confidence",
            candidate=top,
        )

    return MatchResult(
        confidence=confidence,
        review_status="NEEDS_REVIEW",
        review_note="low confidence",
        candidate=top,
    )
