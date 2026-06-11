"""Ingest routes — eighth slice of main.py -> APIRouter split.
"""
from __future__ import annotations
import csv
import io
import re
from typing import Annotated, Any
from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from .. import db
from .. import security
from ..schemas import (
    BarcodeIngestRequest,
    BarcodeIngestResponse,
    BarcodePlacementRecommendationItem,
    BarcodePlacementRecommendationRequest,
    BarcodePlacementRecommendationResponse,
    CsvIngestResponse,
    QueryIngestRequest,
    QueryIngestResponse,
    ReviewQueueItem,
)

router = APIRouter()

def _main():
    from app import main as main_module
    return main_module

def _require_admin(request: Request) -> None:
    security._require_operator_request(request)


def _csv_first_text(row: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        text = str(value or "").strip()
        if text:
            return text
    return None


def _normalize_discogs_release_id(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if re.fullmatch(r"\d+", text):
        return text
    url_match = re.search(r"/release/(\d+)", text, flags=re.IGNORECASE)
    if url_match:
        return str(url_match.group(1))
    return None


def _merge_review_note(*parts: str | None) -> str | None:
    merged = [str(part).strip() for part in parts if str(part or "").strip()]
    return " / ".join(merged) if merged else None


def _normalize_csv_ingest_row(
    row: dict[str, Any],
    default_category: str | None,
    slot_by_code: dict[str, dict[str, Any]],
    slot_by_triplet: dict[tuple[str, str, str], dict[str, Any]],
) -> tuple[dict[str, Any], str | None, str | None]:
    normalized: dict[str, Any] = {}
    for raw_key, raw_value in row.items():
        key = str(raw_key or "").strip()
        if not key:
            continue
        normalized[key] = str(raw_value or "").strip()

    if not normalized.get("category") and default_category:
        normalized["category"] = str(default_category).strip().upper()
    elif normalized.get("category"):
        normalized["category"] = str(normalized["category"]).strip().upper()

    discogs_release_id_input = _csv_first_text(
        normalized,
        "discogs_release_id",
        "discogs_id",
        "discogs_release",
        "디스코그스ID",
        "디스코그스 아이디",
        "디스코그스아이디",
    )
    discogs_release_id = _normalize_discogs_release_id(discogs_release_id_input)
    if discogs_release_id_input and not discogs_release_id:
        return normalized, "invalid discogs_release_id", None
    if discogs_release_id:
        normalized["discogs_release_id"] = discogs_release_id
        normalized["source_code"] = "DISCOGS"
        normalized["source_external_id"] = discogs_release_id

    cabinet_name = _csv_first_text(normalized, "cabinet_name", "storage_cabinet", "cabinet", "장식장명")
    column_code = _csv_first_text(normalized, "column_code", "floor", "층", "열")
    cell_code = _csv_first_text(normalized, "cell_code", "cell", "칸")
    slot_code = _csv_first_text(normalized, "slot_code", "보관슬롯", "보관 슬롯")
    if cabinet_name:
        normalized["cabinet_name"] = cabinet_name
    if column_code:
        normalized["column_code"] = column_code
    if cell_code:
        normalized["cell_code"] = cell_code
    if slot_code:
        normalized["slot_code"] = slot_code

    location_error: str | None = None
    location_review_note: str | None = None
    resolved_slot: dict[str, Any] | None = None

    has_triplet_input = any(v is not None for v in (cabinet_name, column_code, cell_code))
    if has_triplet_input:
        if not (cabinet_name and column_code and cell_code):
            location_error = "storage location requires cabinet_name/column_code/cell_code together"
        else:
            resolved_triplet = slot_by_triplet.get((cabinet_name.casefold(), column_code.casefold(), cell_code.casefold()))
            resolved_code = slot_by_code.get(slot_code.casefold()) if slot_code else None
            if slot_code and resolved_triplet and resolved_code and int(resolved_triplet["id"]) != int(resolved_code["id"]):
                location_error = "slot_code does not match cabinet_name/column_code/cell_code"
            elif slot_code and ((resolved_triplet is None) != (resolved_code is None)):
                location_error = "slot_code does not match cabinet_name/column_code/cell_code"
            resolved_slot = resolved_triplet or resolved_code
            if not location_error and resolved_slot is None:
                location_review_note = "storage slot not found for cabinet_name/column_code/cell_code"
    elif slot_code:
        resolved_slot = slot_by_code.get(slot_code.casefold())
        if resolved_slot is None:
            location_review_note = "storage slot not found for slot_code"

    if resolved_slot is not None:
        normalized["storage_slot_id"] = int(resolved_slot["id"])
        normalized["slot_code"] = str(resolved_slot.get("slot_code") or "")
        if resolved_slot.get("cabinet_name") is not None:
            normalized["cabinet_name"] = str(resolved_slot.get("cabinet_name") or "")
        if resolved_slot.get("column_code") is not None:
            normalized["column_code"] = str(resolved_slot.get("column_code") or "")
        if resolved_slot.get("cell_code") is not None:
            normalized["cell_code"] = str(resolved_slot.get("cell_code") or "")

    return normalized, location_error, location_review_note



@router.post("/ingest/barcode", response_model=BarcodeIngestResponse)
def ingest_barcode(payload: BarcodeIngestRequest) -> BarcodeIngestResponse:
    candidates = _main().search_music_metadata(
        barcode=payload.barcode,
        category=payload.category,
        source=payload.source,
        limit=payload.limit,
    )
    candidates = _main()._annotate_owned_flags(candidates)
    return BarcodeIngestResponse(query=payload.barcode, candidates=candidates)


@router.post("/ingest/barcode/recommend-location", response_model=BarcodePlacementRecommendationResponse)
def recommend_barcode_location(
    payload: BarcodePlacementRecommendationRequest,
    request: Request,
) -> BarcodePlacementRecommendationResponse:
    _require_admin(request)
    recommendations = db.recommend_barcode_candidate_locations(
        category=payload.category,
        size_group=payload.size_group,
        domain_code=payload.domain_code,
        format_name=payload.format_name,
        artist_or_brand=payload.artist_or_brand,
        title=payload.title,
        release_year=payload.release_year,
        thickness_mm=payload.thickness_mm,
        package_hint=payload.package_hint,
    )
    return BarcodePlacementRecommendationResponse(
        available=bool(recommendations),
        recommendations=[BarcodePlacementRecommendationItem(**row) for row in recommendations],
        fallback_message=None if recommendations else "추천 가능한 위치가 없습니다.",
    )


@router.post("/ingest/search", response_model=QueryIngestResponse)
def ingest_search(payload: QueryIngestRequest) -> QueryIngestResponse:
    query = _main()._compose_non_barcode_query(payload)
    if not query:
        raise HTTPException(
            status_code=400,
            detail="Provide query or at least one of artist_or_brand/title/catalog_no/runout/label_name/release_year/country",
        )

    candidates = _main()._search_lookup_metadata_candidates(
        query=query,
        category=payload.category,
        source=payload.source,
        limit=payload.limit,
        artist_or_brand=payload.artist_or_brand,
        title=payload.title,
    )
    candidates = _main()._annotate_owned_flags(candidates)
    return QueryIngestResponse(query=query, candidates=candidates)


@router.post("/ingest/csv", response_model=CsvIngestResponse)
async def ingest_csv(
    file: UploadFile = File(...),
    default_category: Annotated[str | None, Form()] = None,
    created_by: Annotated[str | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
) -> CsvIngestResponse:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="only .csv upload is supported")

    batch_id = db.insert_batch("CSV_IMPORT", created_by, notes)

    raw = await file.read()
    text = _main()._decode_upload_bytes(raw)
    reader = csv.DictReader(io.StringIO(text))
    slot_by_code, slot_by_triplet = _main()._csv_slot_lookup_maps()
    discogs_candidate_cache: dict[str, dict[str, Any] | None] = {}

    total = 0
    matched = 0
    review = 0
    failed = 0
    # We accumulate review_queue inserts and flush them via executemany at
    # the very end (`db.bulk_finalize_csv_ingest`). Pre-2026-04 each row
    # opened its own write transaction; on a 1k-row import that paid for
    # 1k separate fsync barriers. The single batch keeps everything atomic
    # — if the loop raises, the whole CSV is rolled back together.
    pending_rows: list[dict[str, Any]] = []

    for row_no, row in enumerate(reader, start=2):
        total += 1
        normalized_row, location_error, location_review_note = _normalize_csv_ingest_row(
            row,
            default_category=default_category,
            slot_by_code=slot_by_code,
            slot_by_triplet=slot_by_triplet,
        )
        discogs_release_id = str(normalized_row.get("discogs_release_id") or "").strip()
        discogs_candidate: dict[str, Any] | None = None
        if discogs_release_id:
            if discogs_release_id not in discogs_candidate_cache:
                discogs_candidate_cache[discogs_release_id] = _main()._build_csv_discogs_candidate(discogs_release_id)
            discogs_candidate = discogs_candidate_cache.get(discogs_release_id)
            if discogs_candidate:
                candidate_category = str(discogs_candidate.get("format_name") or "").strip().upper()
                if candidate_category:
                    normalized_row["category"] = candidate_category
                for field in ("artist_or_brand", "title", "catalog_no", "label_name", "barcode"):
                    incoming = str(discogs_candidate.get(field) or "").strip()
                    if incoming:
                        normalized_row[field] = incoming

        valid, category, validation_error = _main().validate_row_for_ingest(normalized_row, default_category=default_category)

        if not valid or location_error:
            failed += 1
            pending_rows.append(
                {
                    "batch_id": batch_id,
                    "row_no": row_no,
                    "category": category,
                    "payload": normalized_row,
                    "candidate": None,
                    "confidence": 0.0,
                    "review_status": "NEEDS_REVIEW",
                    "review_note": _merge_review_note(validation_error, location_error),
                }
            )
            continue

        if discogs_release_id:
            if discogs_candidate:
                result = MatchResult(
                    confidence=1.0,
                    review_status="AUTO_APPROVED",
                    review_note=None,
                    candidate=discogs_candidate,
                )
            else:
                result = MatchResult(
                    confidence=0.0,
                    review_status="NEEDS_REVIEW",
                    review_note="discogs release snapshot not found",
                    candidate=None,
                )
        else:
            barcode = (normalized_row.get("barcode") or "").strip()
            query = _main().compose_query(normalized_row)

            if barcode:
                candidates = _main().search_music_metadata(barcode=barcode, category=category, limit=5)
            elif query:
                candidates = _main().search_music_metadata(
                    query=query,
                    category=category,
                    limit=5,
                    artist_or_brand=normalized_row.get("artist_or_brand"),
                    title=normalized_row.get("title"),
                )
            else:
                candidates = []

            result = _main().classify_candidate(candidates)
        if location_review_note:
            result.review_status = "NEEDS_REVIEW"
            result.review_note = _merge_review_note(result.review_note, location_review_note)

        if result.review_status == "AUTO_APPROVED":
            matched += 1
        else:
            review += 1

        pending_rows.append(
            {
                "batch_id": batch_id,
                "row_no": row_no,
                "category": category,
                "payload": normalized_row,
                "candidate": result.candidate,
                "confidence": result.confidence,
                "review_status": result.review_status,
                "review_note": result.review_note,
            }
        )

    db.bulk_finalize_csv_ingest(
        batch_id=batch_id,
        totals={"total": total, "matched": matched, "review": review, "failed": failed},
        review_queue_rows=pending_rows,
    )

    return CsvIngestResponse(
        batch_id=batch_id,
        total_count=total,
        matched_count=matched,
        review_count=review,
        failed_count=failed,
    )


@router.get("/review-queue", response_model=list[ReviewQueueItem])
def get_review_queue(
    review_status: str = Query(default="NEEDS_REVIEW", pattern="^(AUTO_APPROVED|NEEDS_REVIEW|APPROVED|REJECTED)$"),
    category: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[ReviewQueueItem]:
    rows = db.list_review_queue(review_status=review_status, category=category, limit=limit, offset=offset)
    return [ReviewQueueItem(**row) for row in rows]