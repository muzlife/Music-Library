"""Purchase-import queue routes.

Third slice of the main.py → APIRouter split. Owns the surface that the
구매 내역 수입 (purchase import) workflow drives:

  * preview / save  — POST /purchase-imports/preview, POST /purchase-imports
  * webhook         — POST /purchase-imports/webhook/gmail
  * list / detail   — GET /purchase-imports, GET /purchase-imports/{queue_id}/candidates
  * row actions     — POST /purchase-imports/{queue_id}/{enrich,create,ignore,...}

The parsing/normalising helpers (`_purchase_*`, `_resolve_purchase_*`,
`_parse_purchase_import_preview`, etc.) still live in app.main because
they're shared with non-route code paths and total ~1.5k lines we don't
want to move in a single slice. We import them here at module load — that
forces main.py to defer registering this router until the END of its
module body, so all the helper names are bound by the time we touch them.

Cross-domain calls (`create_owned_item` on the owned-items route) are kept
as direct imports from app.main; the next slice will move owned_items into
its own module and we'll switch the import target then.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from .. import db
from ..schemas import (
    PurchaseImportCandidateCreateRequest,
    PurchaseImportCandidateSearchResponse,
    PurchaseImportCreateResponse,
    PurchaseImportListResponse,
    PurchaseImportPreviewRequest,
    PurchaseImportPreviewResponse,
    PurchaseImportQueueItem,
    PurchaseImportSaveRequest,
    PurchaseImportSaveResponse,
    PurchaseImportStatus,
    PurchaseImportVendor,
    PurchaseImportWebhookRequest,
)
from ..security import _require_admin_request


logger = logging.getLogger(__name__)
router = APIRouter(tags=["purchase-imports"])


def _main():
    """Lazy accessor for main-module helpers.

    Avoids a hard import-time cycle: `app.main` is what registers this
    router, and registering would re-trigger module load if we did
    `from app.main import _foo` at the top. Resolving on first call lets
    main.py finish loading before any helper is touched.
    """
    from app import main as main_module

    return main_module


@router.post("/purchase-imports/preview", response_model=PurchaseImportPreviewResponse)
def preview_purchase_import(
    payload: PurchaseImportPreviewRequest, request: Request
) -> PurchaseImportPreviewResponse:
    _require_admin_request(request)
    main_module = _main()
    raw_content, _html_content = main_module._resolve_purchase_import_raw_input(payload)
    resolved_vendor_code = main_module._resolve_purchase_import_vendor_code(
        payload.vendor_code, raw_content=raw_content
    )
    items = main_module._parse_purchase_import_preview(payload)
    if not items:
        reason = main_module._purchase_import_empty_reason(resolved_vendor_code, raw_content)
        if reason:
            raise HTTPException(status_code=400, detail=reason)
    return PurchaseImportPreviewResponse(
        vendor_code=resolved_vendor_code,
        total_count=len(items),
        items=items,
    )


@router.post("/purchase-imports", response_model=PurchaseImportSaveResponse)
def save_purchase_import(
    payload: PurchaseImportSaveRequest, request: Request
) -> PurchaseImportSaveResponse:
    _require_admin_request(request)
    main_module = _main()
    resolved_vendor_code = main_module._resolve_purchase_import_vendor_code(
        payload.vendor_code, items=payload.items
    )
    resolved_purchase_date = main_module._resolve_purchase_import_purchase_date(
        payload.purchase_date, items=payload.items
    )
    rows = main_module._purchase_import_rows_for_save(
        payload.items,
        vendor_code=resolved_vendor_code,
        email_from=payload.email_from,
    )
    created_ids = db.insert_purchase_import_rows(
        resolved_vendor_code,
        payload.source_type,
        rows,
        source_ref=main_module._clean_text(payload.source_ref),
        email_from=main_module._clean_text(payload.email_from),
        email_subject=main_module._clean_text(payload.email_subject),
        purchase_date=resolved_purchase_date,
    )
    return PurchaseImportSaveResponse(created_count=len(created_ids), created_ids=created_ids)


def _webhook_envelope_dependency(request: Request) -> None:
    """Wrapper so APIRouter's `dependencies=[Depends(...)]` machinery resolves
    the envelope guard against the live main module rather than an
    import-time symbol that doesn't exist yet."""
    _main()._require_purchase_import_webhook_envelope(request)


@router.post(
    "/purchase-imports/webhook/gmail",
    response_model=PurchaseImportSaveResponse,
    dependencies=[Depends(_webhook_envelope_dependency)],
)
def purchase_import_webhook_gmail(
    payload: PurchaseImportWebhookRequest,
) -> PurchaseImportSaveResponse:
    main_module = _main()
    cleaned_source_ref = main_module._clean_text(payload.source_ref)
    # Webhook-level dedupe: Gmail/Zapier-style retries deliver the same
    # message_id twice; short-circuit before HTML parsing & vendor inference.
    if cleaned_source_ref and db.has_purchase_import_for_source_ref(
        str(payload.vendor_code or ""), cleaned_source_ref
    ):
        logger.info(
            "purchase import webhook: duplicate source_ref %s for vendor %s; skipped",
            cleaned_source_ref,
            payload.vendor_code,
        )
        return PurchaseImportSaveResponse(created_count=0, created_ids=[])

    items = main_module._parse_purchase_import_preview(payload)
    resolved_vendor_code = main_module._resolve_purchase_import_vendor_code(
        payload.vendor_code, raw_content=payload.raw_content, items=items
    )
    resolved_purchase_date = main_module._resolve_purchase_import_purchase_date(
        payload.purchase_date, raw_content=payload.raw_content, items=items
    )
    # Re-check after vendor resolution since the inferred vendor may differ
    # from the payload-supplied one and our dedupe key is (vendor_code, source_ref).
    if (
        cleaned_source_ref
        and resolved_vendor_code != str(payload.vendor_code or "")
        and db.has_purchase_import_for_source_ref(resolved_vendor_code, cleaned_source_ref)
    ):
        logger.info(
            "purchase import webhook: duplicate source_ref %s for resolved vendor %s; skipped",
            cleaned_source_ref,
            resolved_vendor_code,
        )
        return PurchaseImportSaveResponse(created_count=0, created_ids=[])

    rows = main_module._purchase_import_rows_for_save(
        items, vendor_code=resolved_vendor_code, email_from=payload.email_from
    )
    created_ids = db.insert_purchase_import_rows(
        resolved_vendor_code,
        payload.source_type,
        rows,
        source_ref=cleaned_source_ref,
        email_from=main_module._clean_text(payload.email_from),
        email_subject=main_module._clean_text(payload.email_subject),
        purchase_date=resolved_purchase_date,
    )
    return PurchaseImportSaveResponse(created_count=len(created_ids), created_ids=created_ids)


@router.get("/purchase-imports", response_model=PurchaseImportListResponse)
def list_purchase_imports(
    request: Request,
    queue_status: PurchaseImportStatus | None = Query(default="PENDING"),
    vendor_code: PurchaseImportVendor | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=300),
) -> PurchaseImportListResponse:
    _require_admin_request(request)
    main_module = _main()
    rows = db.list_purchase_import_rows(
        queue_status=queue_status, vendor_code=vendor_code, limit=limit
    )
    total_count = db.count_purchase_import_rows(
        queue_status=queue_status, vendor_code=vendor_code
    )
    return PurchaseImportListResponse(
        total_count=total_count,
        items=[main_module._purchase_queue_item_from_row(row) for row in rows],
    )


@router.get(
    "/purchase-imports/{queue_id}/candidates",
    response_model=PurchaseImportCandidateSearchResponse,
)
def list_purchase_import_candidates(
    queue_id: int,
    request: Request,
    source: str = Query(default="AUTO"),
    limit: int = Query(default=5, ge=1, le=20),
    artist_name: str | None = Query(default=None),
    item_name: str | None = Query(default=None),
    query: str | None = Query(default=None),
) -> PurchaseImportCandidateSearchResponse:
    _require_admin_request(request)
    main_module = _main()
    row = db.get_purchase_import_row(queue_id)
    if row is None:
        raise HTTPException(status_code=404, detail="purchase import row not found")

    working_row = row
    vendor_code = str(row.get("vendor_code") or "").strip().upper()
    item_url = main_module._clean_text(row.get("item_url"))
    has_artist_name = bool(main_module._clean_text(row.get("artist_name")))
    has_image_url = bool(main_module._clean_text(row.get("image_url")))
    if vendor_code == "AMAZON" and item_url and (not has_artist_name or not has_image_url):
        try:
            working_row = main_module._purchase_enrich_row_from_item_page(row)
        except Exception:
            working_row = row

    search_query = main_module._purchase_queue_candidate_query(
        working_row, artist_name=artist_name, item_name=item_name, query=query
    )
    if not search_query:
        raise HTTPException(
            status_code=400,
            detail="구매 수입 큐 항목에서 후보 조회용 상품명/아티스트 정보를 찾지 못했습니다.",
        )

    _media_format, category, _size_group, _seller_name = main_module._purchase_queue_base_context(
        working_row
    )
    candidates = main_module._search_lookup_metadata_candidates(
        query=search_query,
        category=category,
        source=str(source or "AUTO").strip().upper() or "AUTO",
        limit=limit,
        artist_or_brand=main_module._clean_text(artist_name)
        if artist_name is not None
        else main_module._clean_text(working_row.get("artist_name")),
        title=main_module._clean_text(item_name)
        if item_name is not None
        else main_module._clean_text(working_row.get("item_name")),
    )
    candidates = main_module._annotate_owned_flags(candidates)
    return PurchaseImportCandidateSearchResponse(
        queue_item=main_module._purchase_queue_item_from_row(working_row),
        query=search_query,
        candidates=candidates,
    )


@router.post(
    "/purchase-imports/{queue_id}/enrich-item-page", response_model=PurchaseImportQueueItem
)
def enrich_purchase_import_from_item_page(
    queue_id: int, request: Request
) -> PurchaseImportQueueItem:
    _require_admin_request(request)
    main_module = _main()
    row = db.get_purchase_import_row(queue_id)
    if row is None:
        raise HTTPException(status_code=404, detail="purchase import row not found")
    updated = main_module._purchase_enrich_row_from_item_page(row)
    return main_module._purchase_queue_item_from_row(updated)


@router.post(
    "/purchase-imports/{queue_id}/create-owned-item",
    response_model=PurchaseImportCreateResponse,
)
def create_owned_item_from_purchase_import(
    queue_id: int, request: Request
) -> PurchaseImportCreateResponse:
    _require_admin_request(request)
    main_module = _main()
    row = db.get_purchase_import_row(queue_id)
    if row is None:
        raise HTTPException(status_code=404, detail="purchase import row not found")
    if str(row.get("queue_status") or "").strip().upper() != "PENDING":
        raise HTTPException(status_code=400, detail="purchase import row is not pending")
    duplicate_row = db.find_purchase_import_duplicate_row(
        row, exclude_queue_id=queue_id, require_linked_owned_item=True
    )
    if duplicate_row is not None:
        existing_owned_item_id = int(duplicate_row.get("linked_owned_item_id") or 0)
        if existing_owned_item_id > 0 and db.get_owned_item(existing_owned_item_id) is not None:
            return main_module._purchase_import_duplicate_create_response(
                queue_id=queue_id,
                row=row,
                existing_owned_item_id=existing_owned_item_id,
            )
    payload = main_module._build_owned_item_from_purchase_queue_row(row)
    created = main_module.create_owned_item(payload)
    updated = db.update_purchase_import_row(
        queue_id,
        queue_status="CREATED",
        linked_owned_item_id=int(created.owned_item_id),
    )
    if updated is None:
        raise HTTPException(status_code=500, detail="purchase import row update failed")
    return PurchaseImportCreateResponse(
        queue_item=main_module._purchase_queue_item_from_row(updated),
        owned_item_id=int(created.owned_item_id),
        label_id=str(created.label_id),
        linked_album_master_id=created.linked_album_master_id,
        notices=list(created.notices or []),
    )


@router.post(
    "/purchase-imports/{queue_id}/create-owned-item-from-candidate",
    response_model=PurchaseImportCreateResponse,
)
def create_owned_item_from_purchase_import_candidate(
    queue_id: int,
    payload: PurchaseImportCandidateCreateRequest,
    request: Request,
) -> PurchaseImportCreateResponse:
    _require_admin_request(request)
    main_module = _main()
    row = db.get_purchase_import_row(queue_id)
    if row is None:
        raise HTTPException(status_code=404, detail="purchase import row not found")
    if str(row.get("queue_status") or "").strip().upper() != "PENDING":
        raise HTTPException(status_code=400, detail="purchase import row is not pending")
    duplicate_row = db.find_purchase_import_duplicate_row(
        row, exclude_queue_id=queue_id, require_linked_owned_item=True
    )
    if duplicate_row is not None:
        existing_owned_item_id = int(duplicate_row.get("linked_owned_item_id") or 0)
        if existing_owned_item_id > 0 and db.get_owned_item(existing_owned_item_id) is not None:
            return main_module._purchase_import_duplicate_create_response(
                queue_id=queue_id,
                row=row,
                existing_owned_item_id=existing_owned_item_id,
            )

    candidate = payload.candidate.model_dump(mode="python")
    owned_payload = main_module._build_owned_item_from_purchase_queue_row(row, candidate)
    created = main_module.create_owned_item(owned_payload)
    updated = db.update_purchase_import_row(
        queue_id,
        queue_status="CREATED",
        linked_owned_item_id=int(created.owned_item_id),
    )
    if updated is None:
        raise HTTPException(status_code=500, detail="purchase import row update failed")
    return PurchaseImportCreateResponse(
        queue_item=main_module._purchase_queue_item_from_row(updated),
        owned_item_id=int(created.owned_item_id),
        label_id=str(created.label_id),
        linked_album_master_id=created.linked_album_master_id,
        notices=list(created.notices or []),
    )


@router.post("/purchase-imports/{queue_id}/ignore", response_model=PurchaseImportQueueItem)
def ignore_purchase_import(queue_id: int, request: Request) -> PurchaseImportQueueItem:
    _require_admin_request(request)
    main_module = _main()
    row = db.get_purchase_import_row(queue_id)
    if row is None:
        raise HTTPException(status_code=404, detail="purchase import row not found")
    queue_status = str(row.get("queue_status") or "").strip().upper()
    if queue_status != "PENDING":
        raise HTTPException(status_code=400, detail="purchase import row is not pending")
    updated = db.update_purchase_import_row(queue_id, queue_status="IGNORED")
    if updated is None:
        raise HTTPException(status_code=404, detail="purchase import row not found")
    return main_module._purchase_queue_item_from_row(updated)
