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
import json

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel

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

    # ALADIN 등록 시 스냅샷 캐시 (루프에서 재사용)
    _aladin_snap_cache: dict[str, dict[str, Any] | None] = {}

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

        # ALADIN: 바코드로 Discogs 마스터 조회 시도
        discogs_crossref: dict[str, Any] | None = None
        if source == "ALADIN" and selected_external_ids:
            _pre_snap = main_module.get_source_release_snapshot(
                source="ALADIN", external_id=selected_external_ids[0]
            )
            _aladin_snap_cache[selected_external_ids[0]] = _pre_snap
            discogs_crossref = (_pre_snap or {}).get("discogs_crossref")

        if discogs_crossref:
            d_ext = str(discogs_crossref.get("external_id") or "").strip()
            d_master_id = str(discogs_crossref.get("master_id") or "").strip()
            d_src_id = d_master_id or d_ext
            d_title = str(discogs_crossref.get("title") or "").strip() or master_title
            d_artist = str(discogs_crossref.get("artist_or_brand") or "").strip() or master_artist or None
            d_year = discogs_crossref.get("master_release_year") or discogs_crossref.get("release_year") or master_year
            target_master_id = db.upsert_album_master(
                source_code="DISCOGS",
                source_master_id=d_src_id,
                title=d_title,
                artist_or_brand=d_artist,
                domain_code=main_module._infer_album_master_domain_code(
                    source_code="DISCOGS",
                    title=d_title,
                    artist_or_brand=d_artist,
                    raw=discogs_crossref.get("raw"),
                ),
                release_year=d_year,
                raw=discogs_crossref.get("raw"),
            )
            notices.append(
                f"Discogs 마스터 등록 (바코드 매칭): album_master_id={target_master_id}"
                f", discogs_id={d_src_id}"
            )
        else:
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
        # ALADIN: 이미 pre-fetch한 스냅샷 재사용
        if source == "ALADIN" and ext in _aladin_snap_cache:
            snapshot = _aladin_snap_cache[ext]
        else:
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
    sort_mode: str | None = Query(default=None),
    owned_item_id: int | None = Query(default=None),
    signature_types: list[str] | None = Query(default=None),
    packaging: list[str] | None = Query(default=None),
    package_contents: list[str] | None = Query(default=None),
    is_limited: bool | None = Query(default=None),
    is_new: bool | None = Query(default=None),
    is_promo: bool | None = Query(default=None),
    album_master_id: int | None = Query(default=None, ge=1),
    genre_missing: bool = Query(default=False),
    format_missing: bool = Query(default=False),
    catalog_missing: bool = Query(default=False),
    review_missing: bool = Query(default=False),
    local_missing: bool = Query(default=False),
    spotify_state: str = Query(default="ANY", pattern="^(ANY|MISSING|MATCHED)$"),
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
        sort_mode=sort_mode,
        owned_item_id=owned_item_id,
        signature_types=signature_types,
        packaging=packaging,
        package_contents=package_contents,
        is_limited=is_limited,
        is_new=is_new,
        is_promo=is_promo,
        album_master_id=album_master_id,
        genre_missing=genre_missing,
        format_missing=format_missing,
        catalog_missing=catalog_missing,
        review_missing=review_missing,
        local_missing=local_missing,
        spotify_state=spotify_state,
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
            owned_item_id=owned_item_id,
            signature_types=signature_types,
            packaging=packaging,
            package_contents=package_contents,
            is_limited=is_limited,
            is_new=is_new,
            is_promo=is_promo,
        genre_missing=genre_missing,
        format_missing=format_missing,
        catalog_missing=catalog_missing,
        review_missing=review_missing,
        local_missing=local_missing,
        spotify_state=spotify_state,
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
        genres_raw = row2.pop("genres_json", None)
        row2["genres"] = json.loads(genres_raw) if isinstance(genres_raw, str) and genres_raw.strip() else []
        styles_raw = row2.pop("styles_json", None)
        row2["styles"] = json.loads(styles_raw) if isinstance(styles_raw, str) and styles_raw.strip() else []
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
        override_title=payload.override_title,
        override_artist_or_brand=payload.override_artist_or_brand,
        genres=payload.genres,
        styles=payload.styles,
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
        override_title=str(updated.get("override_title") or "").strip() or None,
        override_artist_or_brand=str(updated.get("override_artist_or_brand") or "").strip() or None,
        has_manual_correction=bool(updated.get("has_manual_correction")),
        genres=updated.get("genres") or [],
        styles=updated.get("styles") or [],
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


@router.get("/album-masters/{album_master_id}")
def get_album_master(album_master_id: int) -> dict:
    """Return basic info for a single album master (title, artist, year, cover)."""
    row = db.get_album_master_basic(album_master_id)
    if row is None:
        raise HTTPException(status_code=404, detail="album_master not found")
    return row


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





# ── Spotify integration ────────────────────────────────────────────

@router.post("/album-masters/spotify/match")
def spotify_batch_match(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    """Batch match album_masters to Spotify. ADMIN or webhook token."""
    import secrets as _secrets
    from ..config import get_settings as _get_settings
    _cfg = _get_settings()
    _token = str(_cfg.spotify_batch_webhook_token or "").strip()
    _provided = str(request.headers.get("x-spotify-batch-token") or "").strip()
    _token_ok = bool(_token) and _secrets.compare_digest(_provided, _token)
    if not _token_ok:
        from ..security import _require_admin_request
        _require_admin_request(request)
    from ..services.spotify import SpotifyService
    from ..db.album_master_spotify import batch_match_spotify

    sp = SpotifyService()
    if not sp.configured:
        raise HTTPException(status_code=503, detail="Spotify not configured")
    from spotipy.exceptions import SpotifyException
    try:
        result = batch_match_spotify(sp, limit=limit)
    except SpotifyException as exc:
        if exc.http_status == 429:
            raise HTTPException(status_code=429, detail="Spotify API rate-limit exceeded")
        raise HTTPException(status_code=502, detail=f"Spotify API error: {exc.msg}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to run batch match: {exc}")
    return {
        'ok': True,
        'limit': limit,
        'matched': result['matched'],
        'skipped': result['skipped'],
        'errors': result['errors'],
    }


@router.post("/album-masters/{album_master_id}/spotify/play")
def spotify_play_master(
    album_master_id: int,
    request: Request,
) -> dict[str, Any]:
    """Play a Spotify album by album_master_id. OPERATOR+."""
    from ..security import _require_operator_request
    _require_operator_request(request)
    from ..services.spotify import SpotifyService

    sp = SpotifyService()
    if not sp.configured:
        raise HTTPException(status_code=503, detail="Spotify not configured")

    row = db.get_album_master(album_master_id)
    if not row:
        raise HTTPException(status_code=404, detail="Album master not found")

    uri = (row.get("spotify_album_uri") or "").strip()
    if not uri:
        raise HTTPException(status_code=404, detail="No Spotify match for this album")

    ok = sp.play_sync(uri)
    return {"ok": ok, "album_master_id": album_master_id, "spotify_uri": uri}


# ── Spotify manual management ──────────────────────────────────────

# ── Review collection ──────────────────────────────────────────────

@router.post("/album-masters/review/batch-preview")
def batch_review_preview(
    request: Request,
    limit: int = Query(default=5, ge=1, le=20),
) -> dict[str, Any]:
    """Preview DeepL translation for N masters without review (no DB write). ADMIN only."""
    from ..security import _require_admin_request
    _require_admin_request(request)
    from ..services.providers import fetch_wikipedia_album_review
    from ..services.review_pipeline import translate_to_korean_with_deepl
    from ..db.album_master_review import get_masters_without_review
    from ..db.connection import get_conn

    with get_conn() as conn:
        masters = get_masters_without_review(conn, limit=limit)

    results = []
    for master in masters:
        mid = master["id"]
        artist = str(master.get("artist_or_brand") or "").strip()
        title = str(master.get("title") or "").strip()
        year = int(master["release_year"]) if master.get("release_year") else None
        domain = str(master.get("domain_code") or "").strip().upper()
        entry: dict[str, Any] = {
            "master_id": mid,
            "artist": artist,
            "title": title,
            "raw_text": None,
            "translated_text": None,
            "review_url": None,
            "error": None,
        }
        if not artist or not title:
            entry["error"] = "missing artist or title"
            results.append(entry)
            continue
        wiki_lang = "ko" if domain in ("KOREA", "JAPAN", "GREATER_CHINA") else "en"
        raw = fetch_wikipedia_album_review(artist, title, year=year, lang=wiki_lang)
        if not raw:
            entry["error"] = "no Wikipedia page found"
            results.append(entry)
            continue
        entry["raw_text"] = raw["review_text"]
        entry["review_url"] = raw.get("review_url")
        try:
            entry["translated_text"] = translate_to_korean_with_deepl(raw["review_text"])
        except Exception as e:
            entry["error"] = str(e)
        results.append(entry)

    return {"ok": True, "limit": limit, "results": results}


@router.post("/album-masters/review/batch")
def batch_collect_reviews(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    """Batch collect reviews: ManiaDB intro first, Wikipedia fallback. ADMIN only."""
    from ..security import _require_admin_request
    _require_admin_request(request)
    from ..services.providers import fetch_wikipedia_album_review, fetch_maniadb_album_review
    from ..services.review_pipeline import translate_to_korean_with_deepl
    from ..db.album_master_review import get_masters_without_review, save_review, count_masters_without_review
    from ..db.connection import get_conn

    with get_conn() as conn:
        masters = get_masters_without_review(conn, limit=limit)
        # ManiaDB ID 맵 일괄 조회
        if masters:
            ids = [str(m["id"]) for m in masters]
            placeholders = ",".join("?" * len(ids))
            mania_rows = conn.execute(
                f"SELECT album_master_id, source_master_id FROM album_master_external_ref "
                f"WHERE album_master_id IN ({placeholders}) AND source_code = 'MANIADB'",
                ids,
            ).fetchall()
            maniadb_map = {r[0]: str(r[1] or "").strip() for r in mania_rows}
        else:
            maniadb_map = {}

    succeeded = 0
    failed = 0
    for master in masters:
        mid = master["id"]
        artist = str(master.get("artist_or_brand") or "").strip()
        title = str(master.get("title") or "").strip()
        year = int(master["release_year"]) if master.get("release_year") else None
        domain = str(master.get("domain_code") or "").strip().upper()
        if not artist or not title:
            failed += 1
            continue

        # ManiaDB 소개 텍스트 우선 시도
        maniadb_id = maniadb_map.get(mid, "")
        if maniadb_id:
            raw_m = fetch_maniadb_album_review(maniadb_id)
            if raw_m:
                with get_conn() as conn:
                    save_review(conn, mid, raw_m["review_text"], "MANIADB", raw_m.get("review_url"))
                succeeded += 1
                continue

        # Wikipedia 폴백
        wiki_lang = "ko" if domain in ("KOREA", "JAPAN", "GREATER_CHINA") else "en"
        raw = fetch_wikipedia_album_review(artist, title, year=year, lang=wiki_lang)
        if not raw:
            failed += 1
            continue
        try:
            translated = translate_to_korean_with_deepl(raw["review_text"])
            source = "WIKIPEDIA_KO"
        except Exception:
            translated = raw["review_text"] or ""
            source = "WIKIPEDIA_RAW"
        with get_conn() as conn:
            save_review(conn, mid, translated, source, raw.get("review_url"))
        succeeded += 1

    with get_conn() as conn:
        remaining_after = count_masters_without_review(conn)

    return {
        "ok": True,
        "processed": len(masters),
        "succeeded": succeeded,
        "failed": failed,
        "remaining": remaining_after,
    }


@router.post("/album-masters/{album_master_id}/review/auto")
def collect_review_auto(album_master_id: int, request: Request) -> dict[str, Any]:
    """Fetch review for one master: ManiaDB intro first, Wikipedia fallback. ADMIN only."""
    from ..security import _require_admin_request
    _require_admin_request(request)
    from ..services.providers import fetch_wikipedia_album_review, fetch_maniadb_album_review
    from ..services.review_pipeline import translate_to_korean_with_deepl
    from ..db.album_master_review import save_review
    from ..db.connection import get_conn

    with get_conn() as conn:
        row = conn.execute(
            "SELECT artist_or_brand, title, release_year, "
            "COALESCE(override_domain_code, domain_code) AS domain "
            "FROM album_master WHERE id = ?", (album_master_id,)
        ).fetchone()
        maniadb_row = conn.execute(
            "SELECT source_master_id FROM album_master_external_ref "
            "WHERE album_master_id = ? AND source_code = 'MANIADB' LIMIT 1",
            (album_master_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Album master not found")
    artist = str(row[0] or "").strip()
    title = str(row[1] or "").strip()
    year = int(row[2]) if row[2] else None
    domain = str(row[3] or "").strip().upper()
    if not artist or not title:
        raise HTTPException(status_code=400, detail="Artist and title required")

    # ManiaDB 소개 텍스트 우선 시도
    if maniadb_row:
        maniadb_id = str(maniadb_row[0] or "").strip()
        if maniadb_id:
            raw_m = fetch_maniadb_album_review(maniadb_id)
            if raw_m:
                with get_conn() as conn:
                    save_review(conn, album_master_id, raw_m["review_text"], "MANIADB", raw_m.get("review_url"))
                return {
                    "ok": True,
                    "album_master_id": album_master_id,
                    "source": "MANIADB",
                    "review_text": raw_m["review_text"],
                    "review_url": raw_m.get("review_url"),
                }

    # Wikipedia 폴백
    wiki_lang = "ko" if domain in ("KOREA", "JAPAN", "GREATER_CHINA") else "en"
    raw = fetch_wikipedia_album_review(artist, title, year=year, lang=wiki_lang)
    if not raw:
        raise HTTPException(status_code=404, detail="No review found (ManiaDB: no intro, Wikipedia: not found)")

    try:
        review_text = translate_to_korean_with_deepl(raw["review_text"])
        source = "WIKIPEDIA_KO"
    except Exception:
        review_text = raw["review_text"] or ""
        source = "WIKIPEDIA_RAW"

    with get_conn() as conn:
        save_review(conn, album_master_id, review_text, source, raw.get("review_url"))

    return {
        "ok": True,
        "album_master_id": album_master_id,
        "source": source,
        "review_text": review_text,
        "review_url": raw.get("review_url"),
    }


class _ReviewUrlBody(BaseModel):
    url: str


@router.post("/album-masters/{album_master_id}/review/url")
def collect_review_from_url(
    album_master_id: int, body: _ReviewUrlBody, request: Request
) -> dict[str, Any]:
    """Fetch review from a URL, summarize to Korean. ADMIN only."""
    from ..security import _require_admin_request
    _require_admin_request(request)
    from ..services.providers import fetch_review_from_url, fetch_pitchfork_review
    from ..services.review_pipeline import translate_to_korean_with_deepl
    from ..db.album_master_review import save_review
    from ..db.connection import get_conn
    import urllib.parse

    url = body.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="url required")

    with get_conn() as conn:
        exists = conn.execute(
            "SELECT 1 FROM album_master WHERE id = ?", (album_master_id,)
        ).fetchone()
    if not exists:
        raise HTTPException(status_code=404, detail="Album master not found")

    parsed_host = urllib.parse.urlparse(url).netloc.lower().lstrip("www.")
    is_pitchfork = "pitchfork.com" in parsed_host

    if is_pitchfork:
        raw_text = fetch_pitchfork_review(url)
        source_base = "PITCHFORK"
    else:
        raw_text = fetch_review_from_url(url)
        domain = urllib.parse.urlparse(url).netloc or "URL"
        source_base = domain.upper().replace("WWW.", "").replace(".", "_")[:30]

    if not raw_text:
        raise HTTPException(status_code=422, detail="Could not extract text from URL")

    try:
        review_text = translate_to_korean_with_deepl(raw_text)
        source = source_base + "_KO"
    except Exception:
        review_text = raw_text
        source = source_base + "_RAW"

    with get_conn() as conn:
        save_review(conn, album_master_id, review_text, source, url)

    return {"ok": True, "album_master_id": album_master_id, "source": source, "review_text": review_text}


class _ReviewManualBody(BaseModel):
    text: str
    source: str = "MANUAL"


def _is_korean(text: str) -> bool:
    """Return True if the text contains a meaningful portion of Korean characters."""
    import unicodedata
    hangul = sum(1 for ch in text if "가" <= ch <= "힣" or "ᄀ" <= ch <= "ᇿ" or "㄰" <= ch <= "㆏")
    non_space = sum(1 for ch in text if not ch.isspace())
    return non_space > 0 and hangul / non_space >= 0.1


@router.post("/album-masters/{album_master_id}/review/manual")
def save_review_manual(
    album_master_id: int, body: _ReviewManualBody, request: Request
) -> dict[str, Any]:
    """Save a manually written review. Translates to Korean via DeepL if input is not Korean. ADMIN only."""
    from ..security import _require_admin_request
    _require_admin_request(request)
    from ..db.album_master_review import save_review
    from ..db.connection import get_conn

    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")

    with get_conn() as conn:
        exists = conn.execute(
            "SELECT 1 FROM album_master WHERE id = ?", (album_master_id,)
        ).fetchone()
    if not exists:
        raise HTTPException(status_code=404, detail="Album master not found")

    source = (body.source or "MANUAL").strip()[:50]
    translated = False

    if not _is_korean(text):
        try:
            from ..services.review_pipeline import translate_to_korean_with_deepl
            text = translate_to_korean_with_deepl(text)
            source = f"{source}_KO"
            translated = True
        except Exception:
            pass  # DeepL 미설정이거나 실패 시 원문 그대로 저장

    with get_conn() as conn:
        save_review(conn, album_master_id, text, source, None)

    return {"ok": True, "album_master_id": album_master_id, "source": source, "translated": translated}


@router.delete("/album-masters/{album_master_id}/review")
def delete_review(album_master_id: int, request: Request) -> dict[str, Any]:
    """Clear review for an album master. ADMIN only."""
    from ..security import _require_admin_request
    _require_admin_request(request)
    from ..db.album_master_review import clear_review
    from ..db.connection import get_conn

    with get_conn() as conn:
        exists = conn.execute(
            "SELECT 1 FROM album_master WHERE id = ?", (album_master_id,)
        ).fetchone()
    if not exists:
        raise HTTPException(status_code=404, detail="Album master not found")

    with get_conn() as conn:
        clear_review(conn, album_master_id)

    return {"ok": True, "album_master_id": album_master_id}


@router.delete("/album-masters/{album_master_id}/spotify/match")
def spotify_clear_match(
    album_master_id: int,
    request: Request,
) -> dict[str, Any]:
    """Clear Spotify match for an album master. ADMIN only."""
    from ..security import _require_admin_request
    _require_admin_request(request)
    from app.db.connection import get_conn, utc_now_iso

    with get_conn() as conn:
        conn.execute(
            """UPDATE album_master
               SET spotify_album_id = NULL, spotify_album_uri = NULL,
                   spotify_matched_at = NULL, updated_at = ?
               WHERE id = ?""",
            (utc_now_iso(), album_master_id),
        )
        conn.commit()
    return {"ok": True, "album_master_id": album_master_id}


@router.put("/album-masters/{album_master_id}/spotify/match")
async def spotify_set_match(
    album_master_id: int,
    request: Request,
) -> dict[str, Any]:
    """Manually set Spotify album ID for a master. ADMIN only."""
    from ..security import _require_admin_request
    _require_admin_request(request)
    import json as _json

    body = _json.loads(await request.body())
    spotify_album_id = str(body.get("spotify_album_id") or "").strip()
    spotify_album_uri = str(body.get("spotify_album_uri") or f"spotify:album:{spotify_album_id}").strip()

    if not spotify_album_id:
        raise HTTPException(status_code=400, detail="spotify_album_id required")

    from app.db.connection import get_conn, utc_now_iso
    with get_conn() as conn:
        conn.execute(
            """UPDATE album_master
               SET spotify_album_id = ?, spotify_album_uri = ?, spotify_matched_at = ?, updated_at = ?
               WHERE id = ?""",
            (spotify_album_id, spotify_album_uri, utc_now_iso(), utc_now_iso(), album_master_id),
        )
        conn.commit()
    return {"ok": True, "album_master_id": album_master_id, "spotify_album_id": spotify_album_id}


@router.get("/spotify/search")
def spotify_search_albums(
    request: Request,
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=10, ge=1, le=30),
) -> dict[str, Any]:
    """Search Spotify for albums. OPERATOR+."""
    from ..security import _require_operator_request
    _require_operator_request(request)
    from ..services.spotify import SpotifyService

    sp = SpotifyService()
    if not sp.configured:
        raise HTTPException(status_code=503, detail="Spotify not configured")

    albums = sp.search_albums_sync(q, limit=limit)
    return {"query": q, "total_count": len(albums), "items": albums}


# ── Spotify tracks ──────────────────────────────────────────────────

_ALBUM_TRACKS_CACHE: dict[str, dict[str, Any]] = {}

@router.get("/spotify/albums/{spotify_album_id}/tracks")
def spotify_album_tracks(
    spotify_album_id: str,
    request: Request,
) -> dict[str, Any]:
    """Get tracks for a Spotify album. OPERATOR+."""
    from ..security import _require_operator_request
    _require_operator_request(request)
    from ..services.spotify import SpotifyService
    from spotipy.exceptions import SpotifyException

    if spotify_album_id in _ALBUM_TRACKS_CACHE:
        return _ALBUM_TRACKS_CACHE[spotify_album_id]

    sp = SpotifyService()
    if not sp.configured:
        raise HTTPException(status_code=503, detail="Spotify not configured")

    try:
        items = sp.album_tracks_sync(spotify_album_id)
        tracks = [
            {
                "track_id": t.get("id"),
                "name": t.get("name"),
                "track_number": t.get("track_number", 0),
                "duration_ms": t.get("duration_ms", 0),
                "uri": t.get("uri"),
                "artists": [a.get("name", "") for a in t.get("artists", [])],
            }
            for t in items
        ]
        
        album_cover = None
        album = None
        try:
            sp_client = sp._ensure_client_cc()
            if sp_client:
                album = sp_client.album(spotify_album_id)
                images = album.get("images") or []
                album_cover = images[1]["url"] if len(images) > 1 else (images[0]["url"] if images else None)
        except Exception:
            pass
            
        res = {
            "spotify_album_id": spotify_album_id,
            "total_tracks": len(tracks),
            "tracks": tracks,
            "image_url": album_cover,
            "name": album.get("name", "") if album else "",
            "artist": ", ".join(a.get("name", "") for a in album.get("artists", [])) if album else ""
        }
        _ALBUM_TRACKS_CACHE[spotify_album_id] = res
        return res
    except SpotifyException as exc:
        if exc.http_status == 429:
            raise HTTPException(status_code=429, detail="Spotify API rate-limit exceeded")
        raise HTTPException(status_code=502, detail=f"Spotify API error: {exc.msg}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch tracklist: {exc}")


# ── Generic Spotify play ────────────────────────────────────────────

@router.post("/spotify/play")
async def spotify_play_uri(request: Request) -> dict[str, Any]:
    """Play a Spotify URI (track or album). OPERATOR+."""
    from ..security import _require_operator_request
    _require_operator_request(request)
    import json as _json
    from ..services.spotify import SpotifyService

    body = _json.loads(await request.body())
    uri = str(body.get("uri") or "").strip()
    if not uri:
        raise HTTPException(status_code=400, detail="uri required")

    sp = SpotifyService()
    if not sp.configured:
        raise HTTPException(status_code=503, detail="Spotify not configured")

    ok = sp.play_sync(uri)
    return {"ok": ok, "uri": uri}
