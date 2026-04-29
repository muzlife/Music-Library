"""Album-master routes.

Fourth slice of the main.py → APIRouter split. Owns the surface that drives
the 마스터 정리 (album master) workflow:

  * search / variants / bind / import-variants
  * list / sort-artist-name / correction / members / delete
  * duplicates / merge / merge-history / rollback

The route bodies pull from a long tail of helpers in app.main —
`_resolve_discogs_master_id_from_album_context`, `_infer_album_master_domain_code`,
`_resolve_master_seed_from_variants`, `_album_master_member_context`, etc.
We keep those in main.py for now (they're shared with non-route paths and
moving them out is a separate refactor) and reach into them via the lazy
`_main()` accessor — same trick as the purchase-imports slice.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response

from .. import db
from ..schemas import (
    AlbumMasterBindRequest,
    AlbumMasterBindResponse,
    AlbumMasterCorrectionUpdateRequest,
    AlbumMasterCorrectionUpdateResponse,
    AlbumMasterDeleteResponse,
    AlbumMasterDuplicateCheckResponse,
    AlbumMasterDuplicateItem,
    AlbumMasterImportVariantsRequest,
    AlbumMasterImportVariantsResponse,
    AlbumMasterImportCreatedItem,
    AlbumMasterImportSkippedItem,
    AlbumMasterListItem,
    AlbumMasterMergeHistoryItem,
    AlbumMasterMergeRequest,
    AlbumMasterMergeResponse,
    AlbumMasterMergeRollbackResponse,
    AlbumMasterSearchRequest,
    AlbumMasterSearchResponse,
    AlbumMasterSortArtistUpdateRequest,
    AlbumMasterSortArtistUpdateResponse,
    AlbumMasterVariantsResponse,
    OwnedItemCreate,
    OwnedItemListItem,
)
from ..security import _read_auth_username


router = APIRouter(tags=["album-masters"])


def _main():
    """Lazy accessor for main-module helpers (same pattern as Phase C)."""
    from app import main as main_module

    return main_module


@router.post("/album-masters/search", response_model=AlbumMasterSearchResponse)
def search_album_masters(payload: AlbumMasterSearchRequest) -> AlbumMasterSearchResponse:
    main_module = _main()
    direct_candidates = main_module._build_direct_album_master_candidates(
        payload.query, source=payload.source
    )
    if direct_candidates is not None:
        candidates = direct_candidates
    else:
        candidates = main_module.search_album_master_candidates(
            query=payload.query,
            source=payload.source,
            limit=payload.limit,
            artist_or_brand=payload.artist_or_brand,
            title=payload.title,
        )
    return AlbumMasterSearchResponse(query=payload.query, candidates=candidates)


@router.get("/album-masters/variants", response_model=AlbumMasterVariantsResponse)
def get_album_master_variants_api(
    source: str = Query(pattern="^(DISCOGS|MANIADB)$"),
    master_external_id: str = Query(min_length=1, max_length=128),
    album_master_id: int | None = Query(default=None, ge=1),
    limit: int | None = Query(default=None, ge=1, le=200),
    page: int = Query(default=1, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=100),
    catalog_no: str | None = Query(default=None, max_length=120),
    barcode: str | None = Query(default=None, max_length=120),
) -> AlbumMasterVariantsResponse:
    main_module = _main()
    source_u = str(source or "").strip().upper()
    effective_master_external_id = str(master_external_id or "").strip()
    page_size_n = int(page_size or min(int(limit or 30), 100))
    page_n = max(1, int(page))
    catalog_no_q = str(catalog_no or "").strip() or None
    barcode_q = str(barcode or "").strip() or None
    fallback_member_rows: list[dict[str, Any]] = []
    member_rows_for_source = (
        [
            row
            for row in db.list_owned_items_by_album_master(int(album_master_id or 0))
            if str(row.get("source_code") or "").strip().upper() == source_u
        ]
        if int(album_master_id or 0) > 0
        else []
    )
    source_master_refs = (
        db.list_album_master_external_refs(int(album_master_id or 0), source_code=source_u)
        if int(album_master_id or 0) > 0
        else []
    )
    if source_u == "DISCOGS":
        requested_master_external_id = effective_master_external_id
        effective_master_external_id, corrected = main_module._resolve_discogs_master_id_from_album_context(
            master_external_id=effective_master_external_id,
            album_master_id=album_master_id,
        )
        if corrected and int(album_master_id or 0) > 0:
            db.normalize_album_master_source_id(
                album_master_id=int(album_master_id or 0),
                source_code="DISCOGS",
                source_master_id=effective_master_external_id,
            )
        elif member_rows_for_source:
            if not source_master_refs or any(
                str(row.get("source_external_id") or "").strip() == requested_master_external_id
                for row in member_rows_for_source
            ):
                fallback_member_rows = member_rows_for_source
    elif member_rows_for_source:
        if not source_master_refs or any(
            str(row.get("source_external_id") or "").strip() == effective_master_external_id
            for row in member_rows_for_source
        ):
            fallback_member_rows = member_rows_for_source
    if fallback_member_rows:
        total_count = len(fallback_member_rows)
        start = max(0, (page_n - 1) * page_size_n)
        page_rows = fallback_member_rows[start : start + page_size_n]
        annotated = [
            main_module._album_master_variant_item_from_owned_row(row, source_u) for row in page_rows
        ]
        return AlbumMasterVariantsResponse(
            source=source_u,
            master_external_id=effective_master_external_id,
            items=annotated,
            page=page_n,
            page_size=page_size_n,
            total_count=total_count,
            has_next=(start + page_size_n) < total_count,
            filtered=False,
            filter_catalog_no=None,
            filter_barcode=None,
            truncated=False,
        )
    paged = main_module.get_album_master_variants_page(
        source=source_u,
        master_external_id=effective_master_external_id,
        page=page_n,
        page_size=page_size_n,
        catalog_no=catalog_no_q,
        barcode=barcode_q,
        include_details=bool(barcode_q),
    )
    items = [
        row
        for row in (paged.get("items") if isinstance(paged, dict) else [])
        if isinstance(row, dict)
    ]
    external_ids = sorted(
        {
            str(row.get("external_id") or "").strip()
            for row in items
            if str(row.get("external_id") or "").strip()
        }
    )
    owned_counts = db.get_owned_counts_by_source(source_u, external_ids) if external_ids else {}
    annotated: list[dict[str, Any]] = []
    for row in items:
        ext = str(row.get("external_id") or "").strip()
        cnt = int(owned_counts.get(ext, 0)) if ext else 0
        row2 = dict(row)
        row2["is_owned"] = cnt > 0
        row2["owned_count"] = cnt
        annotated.append(row2)
    return AlbumMasterVariantsResponse(
        source=source_u,
        master_external_id=effective_master_external_id,
        items=annotated,
        page=int(paged.get("page") or page_n),
        page_size=int(paged.get("page_size") or page_size_n),
        total_count=(
            int(paged.get("total_count"))
            if isinstance(paged.get("total_count"), int) and int(paged.get("total_count")) >= 0
            else None
        ),
        has_next=bool(paged.get("has_next")),
        filtered=bool(paged.get("filtered")),
        filter_catalog_no=str(paged.get("filter_catalog_no") or "").strip() or None,
        filter_barcode=str(paged.get("filter_barcode") or "").strip() or None,
        truncated=bool(paged.get("truncated")),
    )


@router.post("/album-masters/bind", response_model=AlbumMasterBindResponse)
def bind_album_master(payload: AlbumMasterBindRequest) -> AlbumMasterBindResponse:
    main_module = _main()
    master_domain_code = main_module._infer_album_master_domain_code(
        source_code=payload.source,
        title=payload.title,
        artist_or_brand=payload.artist_or_brand,
        raw=payload.raw,
    )
    album_master_id = db.upsert_album_master(
        source_code=payload.source,
        source_master_id=payload.master_external_id,
        title=payload.title,
        artist_or_brand=payload.artist_or_brand,
        domain_code=master_domain_code,
        release_year=payload.release_year,
        raw=payload.raw,
    )
    linked_count = db.bind_album_master_members(
        album_master_id=album_master_id,
        owned_item_ids=payload.owned_item_ids,
        replace_existing=payload.replace_existing,
    )
    for owned_item_id in payload.owned_item_ids:
        db.set_owned_item_linked_album_master(
            owned_item_id=owned_item_id, album_master_id=album_master_id
        )
    return AlbumMasterBindResponse(album_master_id=album_master_id, linked_count=linked_count)


@router.post(
    "/album-masters/import-variants", response_model=AlbumMasterImportVariantsResponse
)
def import_album_master_variants(
    payload: AlbumMasterImportVariantsRequest,
) -> AlbumMasterImportVariantsResponse:
    main_module = _main()
    source = str(payload.source or "").strip().upper()
    target_master_id = int(payload.linked_album_master_id or 0)
    effective_master_external_id = str(payload.master_external_id or "").strip()
    if source == "DISCOGS":
        effective_master_external_id, corrected = main_module._resolve_discogs_master_id_from_album_context(
            master_external_id=effective_master_external_id,
            album_master_id=payload.linked_album_master_id,
        )
        if corrected and target_master_id > 0:
            normalized_master_id = db.normalize_album_master_source_id(
                album_master_id=target_master_id,
                source_code="DISCOGS",
                source_master_id=effective_master_external_id,
            )
            if normalized_master_id > 0:
                target_master_id = normalized_master_id
    selected_external_ids = [
        str(v).strip()
        for v in payload.selected_variant_external_ids
        if str(v).strip()
    ]
    selected_external_ids = list(dict.fromkeys(selected_external_ids))
    variant_by_external: dict[str, dict[str, Any]] = {}

    if selected_external_ids:
        selected_set = set(selected_external_ids)
        page = 1
        page_size = 100
        scan_guard = 0
        while selected_set and scan_guard < 200:
            paged = main_module.get_album_master_variants_page(
                source=source,
                master_external_id=effective_master_external_id,
                page=page,
                page_size=page_size,
                include_details=False,
            )
            items = [
                row
                for row in (paged.get("items") if isinstance(paged, dict) else [])
                if isinstance(row, dict)
            ]
            if not items:
                break
            for row in items:
                ext = str(row.get("external_id") or "").strip()
                if not ext:
                    continue
                if ext in selected_set and ext not in variant_by_external:
                    variant_by_external[ext] = row
            if not bool(paged.get("has_next")):
                break
            page += 1
            scan_guard += 1
    else:
        variants = main_module.get_album_master_variants(
            source=source,
            master_external_id=effective_master_external_id,
            limit=200,
            include_details=(source == "DISCOGS"),
        )
        for row in variants:
            ext = str(row.get("external_id") or "").strip()
            if not ext:
                continue
            if ext not in variant_by_external:
                variant_by_external[ext] = row
        selected_external_ids = list(variant_by_external.keys())

    if not variant_by_external and not selected_external_ids:
        raise HTTPException(status_code=404, detail="master variants not found")
    if not selected_external_ids:
        raise HTTPException(status_code=400, detail="no variant external ids selected")

    notices: list[str] = []
    if effective_master_external_id and effective_master_external_id != str(
        payload.master_external_id or ""
    ).strip():
        notices.append(
            f"Discogs 마스터 ID 보정: {payload.master_external_id} -> {effective_master_external_id}"
        )
    if target_master_id > 0:
        if not db.album_master_exists(target_master_id):
            raise HTTPException(
                status_code=400,
                detail=f"linked_album_master_id not found: {target_master_id}",
            )
    else:
        master_title, master_artist, master_year, master_raw = (
            main_module._resolve_master_seed_from_variants(
                payload=payload,
                variant_by_external=variant_by_external,
                selected_external_ids=selected_external_ids,
            )
        )
        target_master_id = db.upsert_album_master(
            source_code=source,
            source_master_id=effective_master_external_id,
            title=master_title,
            artist_or_brand=master_artist,
            domain_code=main_module._infer_album_master_domain_code(
                explicit_domain_code=payload.domain_code,
                source_code=source,
                title=master_title,
                artist_or_brand=master_artist,
                raw=master_raw,
                linked_album_master_id=payload.linked_album_master_id,
            ),
            release_year=master_year,
            raw=master_raw,
        )
        notices.append(f"마스터 생성/갱신: album_master_id={target_master_id}")

    source_owned_counts = db.get_owned_counts_by_source(source, selected_external_ids)
    existing_rows = db.list_owned_items_by_source_external_ids(source, selected_external_ids)
    existing_ids_by_external: dict[str, list[int]] = {}
    for row in existing_rows:
        ext = str(row.get("source_external_id") or "").strip()
        owned_item_id = int(row.get("id") or 0)
        if not ext or owned_item_id <= 0:
            continue
        existing_ids_by_external.setdefault(ext, []).append(owned_item_id)

    created_items: list[AlbumMasterImportCreatedItem] = []
    skipped_items: list[AlbumMasterImportSkippedItem] = []
    existing_ids_for_bind: set[int] = set()

    for ext in selected_external_ids:
        variant_base = variant_by_external.get(ext)
        if variant_base is None:
            skipped_items.append(
                AlbumMasterImportSkippedItem(
                    external_id=ext,
                    reason="not_found_in_master_variants",
                    owned_count=0,
                )
            )
            continue
        snapshot = main_module.get_source_release_snapshot(source=source, external_id=ext)
        variant = main_module._merge_variant_with_release_snapshot(variant_base, snapshot)

        owned_count = int(source_owned_counts.get(ext, 0))
        if payload.skip_if_owned and owned_count > 0:
            for existing_id in existing_ids_by_external.get(ext, []):
                if existing_id > 0:
                    existing_ids_for_bind.add(existing_id)
            skipped_items.append(
                AlbumMasterImportSkippedItem(
                    external_id=ext,
                    reason="already_owned",
                    owned_count=owned_count,
                )
            )
            continue

        category = main_module._infer_music_category_from_format(
            str(variant.get("format_name") or "")
        )
        artist = str(variant.get("artist_or_brand") or "").strip() or None
        title = str(variant.get("title") or "").strip() or f"{source}#{ext}"
        name_bits = [artist, title]
        item_name_override = " - ".join([v for v in name_bits if v]) or title
        track_list_raw = variant.get("track_list")
        track_list = track_list_raw if isinstance(track_list_raw, list) else []
        mapped_domain = main_module._normalize_domain_code(variant.get("domain_code")) or ""
        mapped_release_type = str(variant.get("release_type") or "").strip().upper()
        if mapped_release_type not in main_module.RELEASE_TYPES:
            mapped_release_type = ""

        create_payload = {
            "category": category,
            "size_group": main_module._default_size_group_for_category(category),
            "preferred_storage_size_group": main_module._default_size_group_for_category(category),
            "quantity": int(payload.quantity or 1),
            "is_second_hand": bool(payload.is_second_hand),
            "status": "IN_COLLECTION",
            "signature_type": "NONE",
            "source_code": source,
            "source_external_id": ext,
            "domain_code": payload.domain_code or (mapped_domain or None),
            "release_type": payload.release_type or (mapped_release_type or None),
            "linked_album_master_id": target_master_id,
            "linked_artist_name": None,
            "item_name_override": item_name_override,
            "purchase_source": payload.purchase_source,
            "memory_note": payload.memory_note,
            "subtype_option_ids": list(payload.subtype_option_ids or []),
            "soundtrack_option_ids": list(payload.soundtrack_option_ids or []),
            "music_detail": {
                "format_name": category,
                "is_promotional_not_for_sale": False,
                "artist_or_brand": artist,
                "release_year": variant.get("release_year"),
                "released_date": variant.get("released_date"),
                "barcode": str(variant.get("barcode") or "").strip() or None,
                "label_name": str(variant.get("label_name") or "").strip() or None,
                "catalog_no": main_module._discogs_catalog_no(variant.get("catalog_no")),
                "cover_image_url": str(variant.get("cover_image_url") or "").strip() or None,
                "track_list": [str(v).strip() for v in track_list if str(v).strip()],
                "media_type": str(variant.get("media_type") or "").strip() or None,
                "genres": main_module._clean_string_list(variant.get("genres")),
                "styles": main_module._clean_string_list(variant.get("styles")),
                "disc_count": variant.get("disc_count"),
                "speed_rpm": variant.get("speed_rpm"),
                "has_obi": main_module._normalize_has_obi_input(variant.get("has_obi")),
                "runout_matrix": main_module._clean_runout_list(variant.get("runout_matrix")),
                "pressing_country": variant.get("pressing_country"),
                "source_notes": main_module._clean_text(variant.get("source_notes")),
                "credits": main_module._clean_string_list(variant.get("credits")),
                "identifier_items": main_module._clean_dict_list(variant.get("identifier_items")),
                "image_items": main_module._clean_dict_list(variant.get("image_items")),
                "company_items": main_module._clean_dict_list(variant.get("company_items")),
                "series": main_module._clean_string_list(variant.get("series")),
                "format_items": main_module._clean_dict_list(variant.get("format_items")),
                "track_items": main_module._clean_dict_list(variant.get("track_items")),
                "label_items": main_module._clean_dict_list(variant.get("label_items")),
            },
        }

        try:
            created = main_module.create_owned_item(OwnedItemCreate(**create_payload))
        except HTTPException as exc:
            skipped_items.append(
                AlbumMasterImportSkippedItem(
                    external_id=ext,
                    reason=str(exc.detail or f"create_failed_{exc.status_code}"),
                    owned_count=owned_count,
                )
            )
            continue
        except Exception as exc:
            skipped_items.append(
                AlbumMasterImportSkippedItem(
                    external_id=ext,
                    reason=f"create_failed: {exc}",
                    owned_count=owned_count,
                )
            )
            continue

        created_items.append(
            AlbumMasterImportCreatedItem(
                external_id=ext,
                owned_item_id=int(created.owned_item_id),
                label_id=str(created.label_id),
                category=category,
                format_name=str(variant.get("format_name") or "").strip() or category,
                title=item_name_override,
            )
        )

    if existing_ids_for_bind:
        db.bind_album_master_members(
            album_master_id=target_master_id,
            owned_item_ids=sorted(existing_ids_for_bind),
            replace_existing=False,
        )
        for existing_id in sorted(existing_ids_for_bind):
            db.set_owned_item_linked_album_master(
                owned_item_id=existing_id, album_master_id=target_master_id
            )
        notices.append(
            f"이미 보유 중인 상품 {len(existing_ids_for_bind)}건을 선택 마스터에 연결했습니다."
        )

    linked_count = len(db.list_owned_items_by_album_master(target_master_id))
    return AlbumMasterImportVariantsResponse(
        album_master_id=target_master_id,
        source=source,
        master_external_id=effective_master_external_id,
        created_count=len(created_items),
        skipped_count=len(skipped_items),
        linked_count=linked_count,
        created_items=created_items,
        skipped_items=skipped_items,
        notices=notices,
    )


@router.get("/album-masters", response_model=list[AlbumMasterListItem])
def list_album_masters(
    response: Response,
    source: str | None = Query(default=None, pattern="^(DISCOGS|MANIADB|MANUAL)$"),
    q: str | None = Query(default=None),
    artist_or_brand: str | None = Query(default=None),
    item_name: str | None = Query(default=None),
    catalog_no: str | None = Query(default=None),
    barcode: str | None = Query(default=None),
    release_year: int | None = Query(default=None, ge=1900, le=2100),
    category: str | None = Query(
        default=None,
        pattern="^(LP|CD|CASSETTE|8TRACK|DIGITAL|REEL_TO_REEL|T_SHIRT|POSTER|LIGHT_STICK|HAT|BAG|CUP|OTHER)$",
    ),
    media_only: bool = Query(default=False),
    domain_code: str | None = Query(
        default=None,
        pattern="^(KOREA|JAPAN|GREATER_CHINA|WESTERN|OTHER_ASIA|WORLD_OTHER|UNKNOWN)$",
    ),
    release_type: str | None = Query(default=None, pattern="^(ALBUM|EP|SINGLE)$"),
    include_total: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[AlbumMasterListItem]:
    main_module = _main()
    match_query = str(item_name or q or "").strip()
    fetch_limit = limit
    fetch_offset = offset
    if match_query:
        fetch_limit = min(500, max(limit, offset + (limit * 5)))
        fetch_offset = 0
    rows = db.list_album_masters(
        source_code=source,
        q=q,
        artist_or_brand=artist_or_brand,
        item_name=item_name,
        catalog_no=catalog_no,
        barcode=barcode,
        release_year=release_year,
        category=category,
        media_only=media_only,
        domain_code=domain_code,
        release_type=release_type,
        limit=fetch_limit,
        offset=fetch_offset,
    )
    if include_total:
        total = db.count_album_masters(
            source_code=source,
            q=q,
            artist_or_brand=artist_or_brand,
            item_name=item_name,
            catalog_no=catalog_no,
            barcode=barcode,
            release_year=release_year,
            category=category,
            media_only=media_only,
            domain_code=domain_code,
            release_type=release_type,
        )
        response.headers["X-Total-Count"] = str(total)
    result: list[AlbumMasterListItem] = []
    for row in rows:
        row2 = dict(row)
        audio_count = int(row2.get("audio_asset_count") or 0)
        row2["audio_asset_count"] = audio_count
        row2["has_audio"] = audio_count > 0
        preview_text = str(row2.pop("member_preview_text", "") or "").strip()
        preview_items: list[str] = []
        if preview_text:
            seen_preview: set[str] = set()
            for raw in preview_text.split(" || "):
                text = str(raw or "").strip()
                if not text or text in seen_preview:
                    continue
                seen_preview.add(text)
                preview_items.append(text)
        row2["member_preview"] = preview_items
        location_preview_text = str(
            row2.pop("member_location_preview_text", "") or ""
        ).strip()
        location_preview_items: list[str] = []
        if location_preview_text:
            seen_locations: set[str] = set()
            for raw in location_preview_text.split(" || "):
                text = str(raw or "").strip()
                if not text or text in seen_locations:
                    continue
                seen_locations.add(text)
                location_preview_items.append(text)
        row2["member_location_preview"] = location_preview_items
        member_location_actions, member_items_preview = main_module._album_master_member_context(
            int(row2.get("id") or 0)
        )
        row2["member_location_actions"] = member_location_actions
        row2["member_items_preview"] = member_items_preview
        row2["matched_track_preview"] = (
            db.list_album_master_track_matches(int(row2.get("id") or 0), match_query, limit=3)
            if match_query
            else []
        )
        result.append(AlbumMasterListItem(**row2))
    if match_query:
        result.sort(key=lambda row: main_module._album_master_search_sort_key(row, match_query))
        result = result[offset : offset + limit]
    return result


@router.patch(
    "/album-masters/{album_master_id}/sort-artist-name",
    response_model=AlbumMasterSortArtistUpdateResponse,
)
def update_album_master_sort_artist_name(
    album_master_id: int,
    payload: AlbumMasterSortArtistUpdateRequest,
) -> AlbumMasterSortArtistUpdateResponse:
    updated = db.update_album_master_sort_artist_name(
        album_master_id=album_master_id,
        sort_artist_name=payload.sort_artist_name,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="album_master not found")
    return AlbumMasterSortArtistUpdateResponse(
        album_master_id=int(updated["id"]),
        sort_artist_name=str(updated.get("sort_artist_name") or "").strip() or None,
    )


@router.patch(
    "/album-masters/{album_master_id}/correction",
    response_model=AlbumMasterCorrectionUpdateResponse,
)
def update_album_master_correction(
    album_master_id: int,
    payload: AlbumMasterCorrectionUpdateRequest,
) -> AlbumMasterCorrectionUpdateResponse:
    updated = db.update_album_master_correction(
        album_master_id=album_master_id,
        release_year=payload.release_year,
        domain_code=payload.domain_code,
        override_note=payload.override_note,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="album_master not found")
    return AlbumMasterCorrectionUpdateResponse(
        album_master_id=int(updated["id"]),
        release_year=int(updated["release_year"])
        if updated.get("release_year") not in (None, "")
        else None,
        domain_code=str(updated.get("domain_code") or "").strip() or None,
        source_release_year=(
            int(updated["source_release_year"])
            if updated.get("source_release_year") not in (None, "")
            else None
        ),
        source_domain_code=str(updated.get("source_domain_code") or "").strip() or None,
        override_release_year=(
            int(updated["override_release_year"])
            if updated.get("override_release_year") not in (None, "")
            else None
        ),
        override_domain_code=str(updated.get("override_domain_code") or "").strip() or None,
        override_note=str(updated.get("override_note") or "").strip() or None,
        has_manual_correction=bool(updated.get("has_manual_correction")),
    )


@router.get(
    "/album-masters/{album_master_id}/members", response_model=list[OwnedItemListItem]
)
def list_album_master_members(album_master_id: int) -> list[OwnedItemListItem]:
    main_module = _main()
    rows = db.list_owned_items_by_album_master(album_master_id=album_master_id)
    return [main_module._to_owned_item_list_item(row) for row in rows]


@router.delete(
    "/album-masters/{album_master_id}", response_model=AlbumMasterDeleteResponse
)
def delete_album_master(
    album_master_id: int,
    cascade_items: bool = Query(default=False),
) -> AlbumMasterDeleteResponse:
    result = db.delete_album_master(album_master_id=album_master_id, cascade_items=cascade_items)
    if result is None:
        raise HTTPException(status_code=404, detail="album_master not found")
    return AlbumMasterDeleteResponse(
        album_master_id=album_master_id,
        deleted=True,
        cascade_items=bool(cascade_items),
        removed_member_links=int(result.get("removed_member_links") or 0),
        deleted_owned_item_count=int(result.get("deleted_owned_item_count") or 0),
    )


@router.get(
    "/album-masters/{album_master_id}/duplicates",
    response_model=AlbumMasterDuplicateCheckResponse,
)
def get_album_master_duplicates(
    album_master_id: int,
    limit: int = Query(default=20, ge=1, le=100),
) -> AlbumMasterDuplicateCheckResponse:
    main_module = _main()
    if not db.album_master_exists(album_master_id):
        raise HTTPException(status_code=404, detail="album_master not found")
    rows = db.list_duplicate_album_masters(album_master_id=album_master_id, limit=limit)
    duplicates: list[AlbumMasterDuplicateItem] = []
    for row in rows:
        duplicate_master_id = int(row.get("album_master_id") or 0)
        if duplicate_master_id <= 0:
            continue
        source_code = str(row.get("source_code") or "").strip().upper()
        if source_code not in {"DISCOGS", "MANIADB", "MUSICBRAINZ", "MANUAL"}:
            source_code = "MANUAL"
        release_year: int | None = None
        raw_year = row.get("release_year")
        try:
            release_year = (
                int(raw_year) if raw_year is not None and str(raw_year).strip() else None
            )
        except (TypeError, ValueError):
            release_year = None
        duplicates.append(
            AlbumMasterDuplicateItem(
                album_master_id=duplicate_master_id,
                source_code=source_code,
                source_master_id=str(row.get("source_master_id") or "").strip(),
                title=str(row.get("title") or "").strip() or f"Master {duplicate_master_id}",
                artist_or_brand=str(row.get("artist_or_brand") or "").strip() or None,
                release_year=release_year,
                member_count=int(row.get("member_count") or 0),
                updated_at=str(row.get("updated_at") or "").strip() or None,
            )
        )
    suggested_target_album_master_id = main_module._pick_duplicate_merge_target_id(rows)
    return AlbumMasterDuplicateCheckResponse(
        album_master_id=album_master_id,
        duplicate_count=len(duplicates),
        suggested_target_album_master_id=suggested_target_album_master_id,
        duplicates=duplicates,
    )


@router.post(
    "/album-masters/{album_master_id}/merge", response_model=AlbumMasterMergeResponse
)
def merge_album_master(
    request: Request,
    album_master_id: int,
    payload: AlbumMasterMergeRequest,
) -> AlbumMasterMergeResponse:
    if not db.album_master_exists(album_master_id):
        raise HTTPException(status_code=404, detail="album_master not found")
    source_id = int(album_master_id)
    target_id = int(payload.target_album_master_id)
    if source_id == target_id:
        count_rows = db.list_owned_items_by_album_master(target_id)
        return AlbumMasterMergeResponse(
            source_album_master_id=source_id,
            target_album_master_id=target_id,
            moved_member_count=0,
            target_member_count=len(count_rows),
            merge_history_id=None,
            merged=False,
        )
    try:
        result = db.merge_album_masters(
            source_album_master_id=source_id,
            target_album_master_id=target_id,
            merged_by=_read_auth_username(request),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return AlbumMasterMergeResponse(
        source_album_master_id=int(result.get("source_album_master_id") or source_id),
        target_album_master_id=int(result.get("target_album_master_id") or target_id),
        moved_member_count=int(result.get("moved_member_count") or 0),
        target_member_count=int(result.get("target_member_count") or 0),
        merge_history_id=int(result["merge_history_id"])
        if result.get("merge_history_id") is not None
        else None,
        merged=True,
    )


@router.get(
    "/album-masters/merge-history", response_model=list[AlbumMasterMergeHistoryItem]
)
def get_album_master_merge_history(
    limit: int = Query(default=10, ge=1, le=50),
) -> list[AlbumMasterMergeHistoryItem]:
    rows = db.list_album_master_merge_history(limit=limit)
    return [AlbumMasterMergeHistoryItem(**row) for row in rows]


@router.post(
    "/album-masters/merge-history/latest/rollback",
    response_model=AlbumMasterMergeRollbackResponse,
)
def rollback_latest_album_master_merge(request: Request) -> AlbumMasterMergeRollbackResponse:
    try:
        result = db.rollback_latest_album_master_merge(
            rolled_back_by=_read_auth_username(request)
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return AlbumMasterMergeRollbackResponse(**result)
