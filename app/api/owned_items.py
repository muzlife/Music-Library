"""Owned-items routes.

Fifth slice of the main.py → APIRouter split. Owns the entire
/owned-items/* CRUD and workflow surface — 22 endpoints covering listing,
detail, create / patch / delete, relations, copies, location
recommendations, source replace, bulk update, slot moves, digital links,
track mappings, and the related-versions / shelf-window helpers used by
the operator screens.

The supporting helpers (`_normalize_music_detail_payload`,
`_apply_post_create_links`, `_build_label_id`, etc.) stay in app.main
because they're shared with non-route code paths. We import them at the
top of this module — that works because main.py only registers this
router at the END of its module body, so by the time this file is
imported the helper symbols are bound on the partially-loaded main module.

The same `_main()` lazy-accessor pattern from earlier slices is also
provided for any helper we missed; that way a forgotten import doesn't
hard-fail at module load.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel

from .. import db
from ..schemas import (
    DigitalLinkCreate,
    DigitalLinkCreateResponse,
    OrderMoveRequest,
    OrderMoveResponse,
    OwnedAlbumShelfWindowResponse,
    OwnedItemAutoMasterResponse,
    OwnedItemBulkUpdateMusicDetailRequest,
    OwnedItemBulkUpdateMusicDetailResponse,
    OwnedItemBulkUpdateRequest,
    OwnedItemBulkUpdateResponse,
    OwnedItemCreate,
    OwnedItemCreateResponse,
    OwnedItemDeleteResponse,
    OwnedItemDetailResponse,
    OwnedItemDuplicateRequest,
    OwnedItemDuplicateResponse,
    OwnedItemListItem,
    OwnedItemLocationRecommendationCandidateSlot,
    OwnedItemLocationRecommendationItem,
    OwnedItemLocationRecommendationRequest,
    OwnedItemSourceReplaceBulkRequest,
    OwnedItemSourceReplaceBulkResponse,
    OwnedItemSourceReplaceResult,
    RelatedAlbumVersionsResponse,
    SlotUpdateRequest,
    SlotUpdateResponse,
    SourceLinkState,
    TrackMappedAssetItem,
    TrackMappingCreateRequest,
    TrackMappingCreateResponse,
    TrackMappingItem,
    TrackMappingListResponse,
)
from ..security import _require_admin_request, _require_operator_request, _read_auth_username


def _audit(request: Request, entity_type: str, entity_id: int, action: str, changed_fields: list[str] | None = None, snapshot: dict | None = None) -> None:
    """Fire-and-forget audit log entry."""
    try:
        username = _read_auth_username(request)
        db.log_audit_event(entity_type=entity_type, entity_id=entity_id, action=action, changed_by=username, changed_fields=changed_fields, snapshot=snapshot)
    except Exception:
        pass


router = APIRouter(tags=["owned-items"])


# Helper symbols pulled from app.main. These are bound at THIS file's
# import time, which (per the late-bound include_router pattern in main.py)
# happens after every helper has been defined. Keeping the list explicit
# means an accidental rename in main.py becomes an ImportError instead of
# a silent runtime NameError inside a route handler.
from app.main import (  # noqa: E402
    MUSIC_CATEGORIES,
    OwnedItemRelationSaveRequest,
    RELEASE_TYPES,
    SIZE_GROUP_CODES,
    _apply_discogs_korean_artist_name_to_owned_item,
    _apply_new_item_location_recommendation,
    _apply_post_create_links,
    _build_duplicate_payload_from_existing_item,
    _build_label_id,
    _build_manual_master_seed_from_owned_row,
    _build_owned_item_payload_for_source_replace,
    _clean_text,
    _default_size_group_for_category,
    _discogs_catalog_no,
    _fetch_owned_item_relation_brief,
    _fetch_owned_item_relation_group_items,
    _infer_album_master_domain_code,
    _link_source_master_for_created_item,
    _normalize_domain_code,
    _normalize_goods_detail_payload,
    _normalize_music_detail_payload,
    _normalize_size_group_code,
    _owned_item_relation_label,
    _preferred_storage_size_group,
    _resolve_owned_item_relation_scope,
    _save_owned_item_update,
    _source_master_variant_external_ids,
    _source_supports_master_auto_link,
    _to_owned_item_list_item,
    _validate_collection_rank,
    _validate_second_hand_music,
    _validate_signature,
    _validate_slot,
    resolve_release_master_reference,
)


def _main():
    """Lazy escape hatch for any helper not enumerated in the import block.
    Same pattern as the purchase-imports / album-masters slices."""
    from app import main as main_module

    return main_module


@router.get("/owned-items", response_model=list[OwnedItemListItem])
def get_owned_items(
    response: Response,
    category: str | None = Query(default=None, pattern="^(LP|CD|CASSETTE|8TRACK|DIGITAL|REEL_TO_REEL|T_SHIRT|POSTER|LIGHT_STICK|HAT|BAG|CUP|OTHER)$"),
    domain_code: str | None = Query(default=None, pattern="^(KOREA|JAPAN|GREATER_CHINA|WESTERN|OTHER_ASIA|WORLD_OTHER|UNKNOWN)$"),
    release_type: str | None = Query(default=None, pattern="^(ALBUM|EP|SINGLE)$"),
    status: str | None = Query(default=None, pattern="^(IN_COLLECTION|LOANED|SOLD|LOST|ARCHIVED)$"),
    q: str | None = Query(default=None),
    artist_or_brand: str | None = Query(default=None),
    item_name: str | None = Query(default=None),
    catalog_no: str | None = Query(default=None),
    barcode: str | None = Query(default=None),
    release_year: int | None = Query(default=None, ge=1900, le=2100),
    source_state: SourceLinkState = Query(default="ANY"),
    master_state: str = Query(default="ANY", pattern="^(ANY|MISSING|LINKED)$"),
    cover_state: str = Query(default="ANY", pattern="^(ANY|MISSING|HAS)$"),
    slot_state: str = Query(default="ANY", pattern="^(ANY|SLOTTED|UNSLOTTED)$"),
    preferred_storage_state: str = Query(default="ANY", pattern="^(ANY|MISMATCH|MATCH)$"),
    track_state: str = Query(default="ANY", pattern="^(ANY|MISSING|HAS)$"),
    media_format_state: str = Query(default="ANY", pattern="^(ANY|MISSING|HAS)$"),
    size_group_state: str = Query(default="ANY", pattern="^(ANY|MISMATCH|MATCH)$"),
    music_only: bool = Query(default=False),
    sort: str = Query(default="DISPLAY", pattern="^(DISPLAY|RECENT)$"),
    include_total: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    catalog_missing: bool = Query(default=False),
    genre_missing: bool = Query(default=False),
) -> list[OwnedItemListItem]:
    rows = db.list_owned_items(
        category=category,
        domain_code=domain_code,
        release_type=release_type,
        status=status,
        q=q,
        artist_or_brand=artist_or_brand,
        item_name=item_name,
        catalog_no=catalog_no,
        barcode=barcode,
        release_year=release_year,
        source_state=source_state,
        master_state=master_state,
        cover_state=cover_state,
        slot_state=slot_state,
        preferred_storage_state=preferred_storage_state,
        track_state=track_state,
        music_only=music_only,
        sort=sort,
        limit=limit,
        offset=offset,
        media_format_state=media_format_state,
        size_group_state=size_group_state,
        catalog_missing=catalog_missing,
        genre_missing=genre_missing,
    )
    if include_total:
        total = db.count_owned_items(
            category=category,
            domain_code=domain_code,
            release_type=release_type,
            status=status,
            q=q,
            artist_or_brand=artist_or_brand,
            item_name=item_name,
            catalog_no=catalog_no,
            barcode=barcode,
            release_year=release_year,
            source_state=source_state,
            master_state=master_state,
            cover_state=cover_state,
            slot_state=slot_state,
            preferred_storage_state=preferred_storage_state,
            track_state=track_state,
            music_only=music_only,
            media_format_state=media_format_state,
            size_group_state=size_group_state,
            catalog_missing=catalog_missing,
            genre_missing=genre_missing,
        )
        response.headers["X-Total-Count"] = str(total)
    return [_to_owned_item_list_item(row) for row in rows]


@router.post("/owned-items/location-recommendations", response_model=list[OwnedItemLocationRecommendationItem])
def get_owned_item_location_recommendations(
    payload: OwnedItemLocationRecommendationRequest,
) -> list[OwnedItemLocationRecommendationItem]:
    owned_item_ids = sorted({int(v) for v in (payload.owned_item_ids or []) if int(v) > 0})
    result: list[OwnedItemLocationRecommendationItem] = []
    for owned_item_id in owned_item_ids[:500]:
        row = db.get_owned_item_detail(owned_item_id)
        if not row:
            continue
        preferred_size_group = _preferred_storage_size_group(
            str(row.get("preferred_storage_size_group") or ""),
            str(row.get("size_group") or ""),
        )
        artist_or_brand = (
            _clean_text(row.get("linked_artist_name"))
            or _clean_text(row.get("artist_or_brand"))
            or _clean_text(row.get("master_artist_or_brand"))
        )
        item_title = _clean_text(row.get("item_name_override")) or _clean_text(row.get("master_title"))
        raw_year = row.get("master_release_year") if row.get("master_release_year") is not None else row.get("release_year")
        try:
            release_year = int(raw_year) if raw_year is not None else None
        except (TypeError, ValueError):
            release_year = None
        suggestion = db.recommend_owned_item_location(
            size_group=preferred_size_group,
            artist_or_brand=artist_or_brand,
            release_year=release_year,
            released_date=_clean_text(row.get("released_date")),
            domain_code=_normalize_domain_code(row.get("master_domain_code") or row.get("domain_code")),
            item_title=item_title,
            exclude_owned_item_id=owned_item_id,
            incoming_thickness_mm=int(row["thickness_mm"]) if row.get("thickness_mm") not in (None, "") else None,
            incoming_format_name=_clean_text(row.get("format_name")),
            incoming_package_hint=_clean_text(row.get("notes")),
        )
        slot_id = int(suggestion.get("recommended_storage_slot_id") or 0)
        slot = db.get_storage_slot(slot_id) if slot_id > 0 else None
        result.append(
            OwnedItemLocationRecommendationItem(
                owned_item_id=owned_item_id,
                recommended_storage_slot_id=slot_id or None,
                slot_code=str((slot or {}).get("slot_code") or suggestion.get("slot_code") or "").strip() or None,
                display_name=str((slot or {}).get("display_name") or "").strip() or None,
                cabinet_name=str((slot or {}).get("cabinet_name") or "").strip() or None,
                column_code=str((slot or {}).get("column_code") or "").strip() or None,
                cell_code=str((slot or {}).get("cell_code") or "").strip() or None,
                candidate_slots=[
                    OwnedItemLocationRecommendationCandidateSlot(
                        storage_slot_id=int(candidate.get("storage_slot_id") or 0) or None,
                        slot_code=str(candidate.get("slot_code") or "").strip() or None,
                        display_name=str(candidate.get("display_name") or "").strip() or None,
                        cabinet_name=str(candidate.get("cabinet_name") or "").strip() or None,
                        column_code=str(candidate.get("column_code") or "").strip() or None,
                        cell_code=str(candidate.get("cell_code") or "").strip() or None,
                    )
                    for candidate in (suggestion.get("candidate_slots") or [])
                    if isinstance(candidate, dict)
                ],
                anchor_owned_item_id=int(suggestion.get("anchor_owned_item_id") or 0) or None,
                anchor_position=str(suggestion.get("anchor_position") or "").strip().upper() or None,
                used_fallback_slot=bool(suggestion.get("used_fallback_slot")),
                reason=str(suggestion.get("reason") or "").strip() or None,
            )
        )
    return result


@router.get("/owned-items/{owned_item_id}/shelf-window", response_model=OwnedAlbumShelfWindowResponse)
def get_owned_item_shelf_window(
    owned_item_id: int,
    window: int = Query(default=6, ge=1, le=20),
) -> OwnedAlbumShelfWindowResponse:
    data = db.get_music_shelf_window(owned_item_id=owned_item_id, window=window)
    if data is None:
        raise HTTPException(status_code=404, detail="owned music item not found")

    items = [_to_owned_item_list_item(row) for row in data.get("items", [])]
    return OwnedAlbumShelfWindowResponse(
        center_owned_item_id=int(data["center_owned_item_id"]),
        previous_owned_item_id=data.get("previous_owned_item_id"),
        next_owned_item_id=data.get("next_owned_item_id"),
        items=items,
    )


@router.get("/owned-items/{owned_item_id}/related-versions", response_model=RelatedAlbumVersionsResponse)
def get_owned_item_related_versions(owned_item_id: int) -> RelatedAlbumVersionsResponse:
    base_row = db.get_owned_item_list_row(owned_item_id)
    if base_row is None or str(base_row.get("category") or "") not in MUSIC_CATEGORIES:
        raise HTTPException(status_code=404, detail="owned music item not found")

    def _to_items(rows: list[dict[str, object]]) -> list[OwnedItemListItem]:
        out: list[OwnedItemListItem] = []
        seen: set[int] = set()
        for row in rows:
            oid = int(row.get("id") or 0)
            if oid <= 0 or oid in seen:
                continue
            seen.add(oid)
            out.append(_to_owned_item_list_item(row))
        return out

    bound = db.get_album_master_binding_for_owned_item(owned_item_id)
    if bound:
        rows = db.list_owned_items_by_album_master(int(bound["album_master_id"]))
        if not rows:
            rows = [base_row]
        preferred_source = str(bound.get("source_code") or "").strip().upper() or None
        preferred_master_external_id = str(bound.get("source_master_id") or "").strip() or None
        if preferred_source not in {"DISCOGS", "MANIADB"} or not preferred_master_external_id:
            external_refs = db.list_album_master_external_refs(int(bound["album_master_id"]))
            supported_ref = next(
                (
                    row
                    for row in external_refs
                    if str(row.get("source_code") or "").strip().upper() in {"DISCOGS", "MANIADB"}
                    and str(row.get("source_master_id") or "").strip()
                ),
                None,
            )
            if supported_ref:
                preferred_source = str(supported_ref.get("source_code") or "").strip().upper() or preferred_source
                preferred_master_external_id = str(supported_ref.get("source_master_id") or "").strip() or preferred_master_external_id
            else:
                supported_row = next(
                    (
                        row
                        for row in rows
                        if str(row.get("source_code") or "").strip().upper() in {"DISCOGS", "MANIADB"}
                        and str(row.get("source_external_id") or "").strip()
                    ),
                    None,
                )
                if supported_row:
                    preferred_source = str(supported_row.get("source_code") or "").strip().upper() or preferred_source
                    preferred_master_external_id = (
                        str(supported_row.get("source_external_id") or "").strip() or preferred_master_external_id
                    )
        import json as _json
        def _parse_str_list(v: object) -> list[str]:
            if not v:
                return []
            try:
                parsed = _json.loads(str(v))
                return [str(x) for x in parsed] if isinstance(parsed, list) else []
            except Exception:
                return []

        return RelatedAlbumVersionsResponse(
            owned_item_id=owned_item_id,
            relation_type="ALBUM_MASTER_BIND",
            source=preferred_source,
            master_external_id=preferred_master_external_id,
            album_master_id=int(bound["album_master_id"]),
            title=str(bound.get("title") or "").strip() or None,
            artist_or_brand=str(bound.get("artist_or_brand") or "").strip() or None,
            sort_artist_name=str(bound.get("sort_artist_name") or "").strip() or None,
            release_year=int(bound["release_year"]) if bound.get("release_year") not in (None, "") else None,
            domain_code=str(bound.get("domain_code") or "").strip() or None,
            source_release_year=int(bound["source_release_year"]) if bound.get("source_release_year") not in (None, "") else None,
            source_domain_code=str(bound.get("source_domain_code") or "").strip() or None,
            override_release_year=int(bound["override_release_year"]) if bound.get("override_release_year") not in (None, "") else None,
            override_domain_code=str(bound.get("override_domain_code") or "").strip() or None,
            override_note=str(bound.get("override_note") or "").strip() or None,
            override_title=str(bound.get("override_title") or "").strip() or None,
            override_artist_or_brand=str(bound.get("override_artist_or_brand") or "").strip() or None,
            has_manual_correction=bool(
                bound.get("override_release_year") not in (None, "")
                or str(bound.get("override_domain_code") or "").strip()
                or str(bound.get("override_note") or "").strip()
            ),
            spotify_album_id=str(bound.get("spotify_album_id") or "").strip() or None,
            review_text=str(bound.get("review_text") or "").strip() or None,
            review_source=str(bound.get("review_source") or "").strip() or None,
            review_url=str(bound.get("review_url") or "").strip() or None,
            genres=_parse_str_list(bound.get("genres_json")),
            styles=_parse_str_list(bound.get("styles_json")),
            items=_to_items(rows),
        )

    source_code = str(base_row.get("source_code") or "").strip().upper()
    source_external_id = str(base_row.get("source_external_id") or "").strip()
    if _source_supports_master_auto_link(source_code) and source_external_id:
        master_ref = resolve_release_master_reference(source=source_code, external_id=source_external_id)
        if master_ref:
            master_source = str(master_ref.get("source") or source_code).strip().upper()
            master_external_id = str(master_ref.get("master_external_id") or "").strip()
            external_ids = _source_master_variant_external_ids(
                source_code=master_source,
                master_external_id=master_external_id,
                release_external_id=source_external_id,
            )

            rows = db.list_owned_items_by_source_external_ids(
                source_code=source_code,
                source_external_ids=sorted(external_ids),
            )
            if rows:
                return RelatedAlbumVersionsResponse(
                    owned_item_id=owned_item_id,
                    relation_type="SOURCE_MASTER",
                    source=master_source,
                    master_external_id=master_external_id or None,
                    title=str(master_ref.get("title") or "").strip() or None,
                    artist_or_brand=str(master_ref.get("artist_or_brand") or "").strip() or None,
                    items=_to_items(rows),
                )

    return RelatedAlbumVersionsResponse(
        owned_item_id=owned_item_id,
        relation_type="NONE",
        items=_to_items([base_row]),
    )


@router.get("/owned-items/{owned_item_id}/relations")
def get_owned_item_relations(owned_item_id: int, request: Request) -> dict[str, Any]:
    _require_operator_request(request)
    owned_row = db.get_owned_item(owned_item_id)
    if owned_row is None:
        raise HTTPException(status_code=404, detail="owned_item not found")
    scope_kind, scope_key, uses_shared = _resolve_owned_item_relation_scope(owned_row)
    bound_master = db.get_album_master_binding_for_owned_item(owned_item_id)

    with db.get_conn() as conn:
        relation_rows = conn.execute(
            """
            SELECT
              id,
              relation_type,
              target_kind,
              target_ref,
              note,
              display_order
            FROM owned_item_relation
            WHERE source_scope_kind = ?
              AND source_scope_key = ?
            ORDER BY display_order ASC, id ASC
            """,
            (scope_kind, scope_key),
        ).fetchall()

        relation_dicts = [dict(row) for row in relation_rows]

        album_master_ids: set[int] = set()
        product_group_ids: set[int] = set()
        owned_item_target_ids: set[int] = set()
        for row in relation_dicts:
            target_kind = str(row.get("target_kind") or "").strip().upper()
            target_ref = str(row.get("target_ref") or "").strip()
            try:
                target_id = int(target_ref)
            except (TypeError, ValueError):
                target_id = 0
            if target_id <= 0:
                continue
            if target_kind == "ALBUM_MASTER":
                album_master_ids.add(target_id)
            elif target_kind == "PRODUCT_GROUP":
                product_group_ids.add(target_id)
            elif target_kind == "OWNED_ITEM":
                owned_item_target_ids.add(target_id)

        album_master_map: dict[int, dict[str, Any]] = {}
        if album_master_ids:
            placeholders = ",".join("?" for _ in album_master_ids)
            rows = conn.execute(
                f"""
                SELECT id, title, artist_or_brand
                FROM album_master
                WHERE id IN ({placeholders})
                """,
                list(album_master_ids),
            ).fetchall()
            album_master_map = {int(row["id"]): dict(row) for row in rows}

        product_group_map: dict[int, dict[str, Any]] = {}
        if product_group_ids:
            placeholders = ",".join("?" for _ in product_group_ids)
            rows = conn.execute(
                f"""
                SELECT id, group_type, group_name
                FROM product_group
                WHERE id IN ({placeholders})
                """,
                list(product_group_ids),
            ).fetchall()
            product_group_map = {int(row["id"]): dict(row) for row in rows}

        owned_item_map: dict[int, dict[str, Any]] = {}
        for target_id in owned_item_target_ids:
            brief = _fetch_owned_item_relation_brief(conn, target_id)
            if brief is not None:
                owned_item_map[target_id] = brief

        master_links: list[dict[str, Any]] = []
        series_memberships: list[dict[str, Any]] = []
        box_memberships: list[dict[str, Any]] = []
        related_releases: list[dict[str, Any]] = []

        def _register_relation(entry: dict[str, Any], relation_type: str) -> None:
            if relation_type == "MASTER_CHILD":
                master_links.append(entry)
            elif relation_type == "SERIES_MEMBER":
                series_memberships.append(entry)
            elif relation_type == "BOX_MEMBER_OF":
                box_memberships.append(entry)
            elif relation_type == "RELATED_RELEASE":
                related_releases.append(entry)

        for row in relation_dicts:
            relation_type = str(row.get("relation_type") or "").strip().upper()
            target_kind = str(row.get("target_kind") or "").strip().upper()
            target_ref = str(row.get("target_ref") or "").strip()
            entry: dict[str, Any] = {
                "relation_type": relation_type,
                "target_kind": target_kind,
                "target_ref": target_ref,
                "note": str(row.get("note") or "").strip() or None,
                "display_order": int(row.get("display_order") or 0),
            }

            target_id = 0
            try:
                target_id = int(target_ref)
            except (TypeError, ValueError):
                target_id = 0

            if target_kind == "ALBUM_MASTER" and target_id > 0:
                entry["album_master_id"] = target_id
                master_row = album_master_map.get(target_id)
                if master_row:
                    entry["target_label"] = str(master_row.get("title") or "").strip() or None
                    entry["artist_or_brand"] = str(master_row.get("artist_or_brand") or "").strip() or None
            elif target_kind == "PRODUCT_GROUP" and target_id > 0:
                entry["product_group_id"] = target_id
                group_row = product_group_map.get(target_id)
                if group_row:
                    entry["product_group_type"] = str(group_row.get("group_type") or "").strip().upper() or None
                    entry["target_label"] = str(group_row.get("group_name") or "").strip() or None
            elif target_kind == "OWNED_ITEM" and target_id > 0:
                entry["target_owned_item_id"] = target_id
                item_row = owned_item_map.get(target_id)
                if item_row:
                    entry["target_category"] = str(item_row.get("category") or "").strip().upper() or None
                    entry["target_copy_group_key"] = str(item_row.get("copy_group_key") or "").strip() or None
                    entry["artist_or_brand"] = str(item_row.get("artist_or_brand") or "").strip() or None
                    entry["target_label"] = _owned_item_relation_label(item_row)
            elif target_kind == "COPY_GROUP" and target_ref:
                entry["target_copy_group_key"] = target_ref

            _register_relation(entry, relation_type)

        if bound_master:
            master_id = int(bound_master.get("album_master_id") or 0)
            if master_id > 0 and not any(
                str(row.get("target_kind") or "").strip().upper() == "ALBUM_MASTER"
                and str(row.get("target_ref") or "").strip() == str(master_id)
                for row in master_links
            ):
                master_links.insert(
                    0,
                    {
                        "relation_type": "MASTER_CHILD",
                        "target_kind": "ALBUM_MASTER",
                        "target_ref": str(master_id),
                        "target_label": str(bound_master.get("title") or "").strip() or None,
                        "album_master_id": master_id,
                        "artist_or_brand": str(bound_master.get("artist_or_brand") or "").strip() or None,
                        "display_order": 0,
                    },
                )

        target_conditions = ["(target_kind = 'OWNED_ITEM' AND target_ref = ?)"]
        target_params: list[Any] = [str(owned_item_id)]
        copy_group_key = str(owned_row.get("copy_group_key") or "").strip()
        if copy_group_key:
            target_conditions.append("(target_kind = 'COPY_GROUP' AND target_ref = ?)")
            target_params.append(copy_group_key)

        box_components: list[dict[str, Any]] = []
        seen_component_ids: set[int] = set()
        if target_conditions:
            box_rows = conn.execute(
                f"""
                SELECT source_scope_kind, source_scope_key, note
                FROM owned_item_relation
                WHERE relation_type = 'BOX_MEMBER_OF'
                  AND ({' OR '.join(target_conditions)})
                ORDER BY display_order ASC, id ASC
                """,
                target_params,
            ).fetchall()
            for row in box_rows:
                scope_kind = str(row.get("source_scope_kind") or "").strip().upper()
                scope_key = str(row.get("source_scope_key") or "").strip()
                note = str(row.get("note") or "").strip() or None
                source_rows: list[dict[str, Any]] = []
                if scope_kind == "OWNED_ITEM":
                    try:
                        source_id = int(scope_key)
                    except (TypeError, ValueError):
                        source_id = 0
                    if source_id > 0:
                        brief = _fetch_owned_item_relation_brief(conn, source_id)
                        if brief:
                            source_rows = [brief]
                        else:
                            source_rows = [{"id": source_id, "category": None, "copy_group_key": None}]
                elif scope_kind == "COPY_GROUP" and scope_key:
                    source_rows = _fetch_owned_item_relation_group_items(conn, scope_key)
                for source_row in source_rows:
                    source_id = int(source_row.get("id") or 0)
                    if source_id <= 0 or source_id in seen_component_ids:
                        continue
                    seen_component_ids.add(source_id)
                    box_components.append(
                        {
                            "source_owned_item_id": source_id,
                            "source_item_name": _owned_item_relation_label(source_row)
                            if source_row.get("id")
                            else f"owned_item_id={source_id}",
                            "source_copy_group_key": str(source_row.get("copy_group_key") or "").strip() or None,
                            "source_category": str(source_row.get("category") or "").strip().upper() or None,
                            "note": note,
                        }
                    )

    return {
        "uses_shared_relation_scope": uses_shared,
        "scope_key": scope_key if uses_shared else None,
        "master_links": master_links,
        "series_memberships": series_memberships,
        "box_memberships": box_memberships,
        "related_releases": related_releases,
        "box_components": box_components,
    }


@router.put("/owned-items/{owned_item_id}/relations")
def save_owned_item_relations(
    owned_item_id: int,
    payload: OwnedItemRelationSaveRequest,
    request: Request,
) -> dict[str, Any]:
    _require_operator_request(request)
    owned_row = db.get_owned_item(owned_item_id)
    if owned_row is None:
        raise HTTPException(status_code=404, detail="owned_item not found")
    scope_kind, scope_key, _ = _resolve_owned_item_relation_scope(owned_row)

    normalized: list[tuple[str, str, str, str | None, int]] = []
    seen: set[tuple[str, str, str]] = set()
    for index, rel in enumerate(payload.relations):
        relation_type = str(rel.relation_type or "").strip().upper()
        target_kind = str(rel.target_kind or "").strip().upper()
        target_ref = str(rel.target_ref or "").strip()
        if not relation_type or not target_kind or not target_ref:
            continue
        key = (relation_type, target_kind, target_ref)
        if key in seen:
            continue
        seen.add(key)
        display_order = int(rel.display_order if rel.display_order is not None else index)
        note = str(rel.note or "").strip() or None
        normalized.append((relation_type, target_kind, target_ref, note, display_order))

    now = db.utc_now_iso()
    with db.get_conn() as conn:
        conn.execute(
            "DELETE FROM owned_item_relation WHERE source_scope_kind = ? AND source_scope_key = ?",
            (scope_kind, scope_key),
        )
        for relation_type, target_kind, target_ref, note, display_order in normalized:
            conn.execute(
                """
                INSERT INTO owned_item_relation (
                  source_scope_kind,
                  source_scope_key,
                  relation_type,
                  target_kind,
                  target_ref,
                  display_order,
                  note,
                  created_at,
                  updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scope_kind,
                    scope_key,
                    relation_type,
                    target_kind,
                    target_ref,
                    display_order,
                    note,
                    now,
                    now,
                ),
            )

    return get_owned_item_relations(owned_item_id, request)


@router.get("/owned-item-relation-targets")
def search_owned_item_relation_targets(
    request: Request,
    kind: Literal["owned_item"] = Query(default="owned_item"),
    q: str = Query(default=""),
    owned_item_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=12, ge=1, le=50),
) -> dict[str, Any]:
    _require_operator_request(request)
    query_text = str(q or "").strip().lower()
    if not query_text:
        return {"items": []}
    like = f"%{query_text}%"
    params: list[Any] = [like, like, like]
    exclude_sql = ""
    if owned_item_id:
        exclude_sql = "AND oi.id <> ?"
        params.append(int(owned_item_id))
    params.append(limit)
    with db.get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT
              oi.id,
              oi.category,
              oi.copy_group_key,
              oi.item_name_override,
              mid.artist_or_brand,
              am.title AS master_title
            FROM owned_item oi
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
            WHERE oi.category IN ('LP', 'CD', 'CASSETTE', '8TRACK', 'DIGITAL', 'REEL_TO_REEL')
              AND (
                LOWER(COALESCE(oi.item_name_override, '')) LIKE ?
                OR LOWER(COALESCE(mid.artist_or_brand, '')) LIKE ?
                OR LOWER(COALESCE(am.title, '')) LIKE ?
              )
              {exclude_sql}
            ORDER BY oi.updated_at DESC, oi.id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()

    items = []
    for row in rows:
        data = dict(row)
        label = _owned_item_relation_label(data)
        copy_group_key = str(data.get("copy_group_key") or "").strip() or None
        if copy_group_key:
            scope_kind = "COPY_GROUP"
            scope_key = copy_group_key
        else:
            scope_kind = "OWNED_ITEM"
            scope_key = str(int(data.get("id") or 0))
        items.append(
            {
                "owned_item_id": int(data.get("id") or 0),
                "label": label,
                "category": str(data.get("category") or "").strip().upper() or None,
                "copy_group_key": copy_group_key,
                "scope_kind": scope_kind,
                "scope_key": scope_key,
            }
        )

    return {"items": items}


@router.get("/owned-items/{owned_item_id}/copies", response_model=list[OwnedItemListItem])
def get_owned_item_copies(owned_item_id: int) -> list[OwnedItemListItem]:
    base_row = db.get_owned_item_list_row(owned_item_id)
    if base_row is None:
        raise HTTPException(status_code=404, detail="owned_item not found")

    copy_group_key = str(base_row.get("copy_group_key") or "").strip()
    if not copy_group_key:
        return [_to_owned_item_list_item(base_row)]

    rows = db.list_owned_items_by_copy_group(copy_group_key)
    if not rows:
        rows = [base_row]
    return [_to_owned_item_list_item(row) for row in rows]


@router.post("/owned-items/{owned_item_id}/duplicate", response_model=OwnedItemDuplicateResponse)
def duplicate_owned_item(
    owned_item_id: int,
    payload: OwnedItemDuplicateRequest,
) -> OwnedItemDuplicateResponse:
    base_row = db.get_owned_item(owned_item_id)
    if base_row is None:
        raise HTTPException(status_code=404, detail="owned_item not found")

    detail_row = db.get_owned_item_detail(owned_item_id)
    bound = db.get_album_master_binding_for_owned_item(owned_item_id)
    linked_master_id = int(bound["album_master_id"]) if bound else int(base_row.get("linked_album_master_id") or 0)
    if linked_master_id <= 0 or not db.album_master_exists(linked_master_id):
        linked_master_id = None

    copy_group_key = str(base_row.get("copy_group_key") or "").strip()
    notices: list[str] = []
    if not copy_group_key:
        copy_group_key = f"COPY-{uuid4().hex[:12].upper()}"
        db.set_owned_item_copy_group(owned_item_id=owned_item_id, copy_group_key=copy_group_key)
        notices.append(f"원본 상품 copy_group 지정: {copy_group_key}")

    create_payload = _build_duplicate_payload_from_existing_item(
        base_row=base_row,
        detail_row=detail_row,
        copy_group_key=copy_group_key,
        linked_master_id=linked_master_id,
    )
    create_model = OwnedItemCreate(**create_payload)
    normalized = create_model.model_dump()
    _normalize_music_detail_payload(normalized)
    _normalize_goods_detail_payload(normalized)

    created_ids: list[int] = []
    seen_notices: set[str] = set()
    resolved_master_id = int(normalized.get("linked_album_master_id") or 0)
    duplicate_count = max(1, int(payload.count or 1))

    for _ in range(duplicate_count):
        owned_new_id = db.insert_owned_item(dict(normalized))
        _audit(request, "owned_item", owned_new_id, "CREATE", snapshot=dict(normalized))
        created_ids.append(owned_new_id)
        resolved_master_id, link_notices = _apply_post_create_links(
            payload=create_model,
            owned_item_id=owned_new_id,
            preferred_master_id=resolved_master_id,
        )
        for msg in link_notices:
            text = str(msg or "").strip()
            if text and text not in seen_notices:
                seen_notices.add(text)
                notices.append(text)

    shown_ids = ", ".join(str(v) for v in created_ids[:8])
    tail = f" 외 {len(created_ids) - 8}건" if len(created_ids) > 8 else ""
    notices.insert(0, f"복제본 {duplicate_count}건 생성 완료 (owned_item_id: {shown_ids}{tail})")
    return OwnedItemDuplicateResponse(
        source_owned_item_id=owned_item_id,
        copy_group_key=copy_group_key,
        created_ids=created_ids,
        notices=notices,
    )


def _schedule_image_download(owned_item_id: int, payload: OwnedItemCreate) -> None:
    """Schedule background image download for a newly created item."""
    import threading
    from pathlib import Path
    from app.services.image_store import download_images
    from ..db import get_conn
    source = (payload.source_code or "").strip().upper()
    if not source or source == "MANUAL":
        return
    static_dir = Path(__file__).resolve().parent.parent / "static"
    source_ext_id = str(payload.source_external_id or "").strip() or None
    music = payload.music_detail  # image data lives under music_detail, not at payload top level

    def _run():
        try:
            items: list[dict] = []

            # 1. music_detail.image_items — Discogs 상세 로드 시 채워짐
            if music and music.image_items:
                items = [
                    {"type": it.get("type") or "추가", "uri": it.get("uri") or ""}
                    for it in music.image_items if it.get("uri")
                ]

            # 2. music_detail.cover_image_url — Discogs thumbnail, Aladin 커버
            cover = str((music.cover_image_url if music else None) or "").strip()
            if cover and not any(it.get("uri") == cover for it in items):
                items.insert(0, {"type": "앞면", "uri": cover})

            # 3. ManiaDB: 검색 결과에는 이미지 없음 → snapshot에서 가져오기
            #    snapshot에도 뒷면이 없으면 URL 패턴(_b.jpg)으로 뒷면 추가 시도
            if source == "MANIADB" and source_ext_id and not items:
                try:
                    from app import main as _main_mod
                    snap = _main_mod.get_source_release_snapshot(source="MANIADB", external_id=source_ext_id)
                    snap_images = list((snap or {}).get("image_items") or [])
                    snap_cover = str((snap or {}).get("cover_image_url") or "").strip()
                    if snap_images:
                        items = [{"type": it.get("type") or "추가", "uri": it.get("uri") or ""} for it in snap_images if it.get("uri")]
                    elif snap_cover:
                        items = [{"type": "앞면", "uri": snap_cover}]
                    # 뒷면이 없으면 _f.jpg → _b.jpg 패턴으로 뒷면 URL 추가 시도
                    has_back = any("뒷면" in (it.get("type") or "") for it in items)
                    if not has_back and items:
                        from app.services.providers import _maniadb_variant_cover_url, _extract_maniadb_album_id
                        import re as _re
                        album_id = _extract_maniadb_album_id(source_ext_id)
                        seq_match = _re.search(r":(\d+)$", source_ext_id)
                        variant_seq = seq_match.group(1) if seq_match else "1"
                        back_url = _maniadb_variant_cover_url(album_id or "", variant_seq, "b") if album_id else None
                        if back_url:
                            items.append({"type": "뒷면", "uri": back_url})
                except Exception:
                    pass

            # 4. Aladin: 상품 상세 페이지에서 추가 이미지 스크레이핑
            if source == "ALADIN" and source_ext_id:
                try:
                    from app.services.providers import _fetch_aladin_images_from_web
                    extra = _fetch_aladin_images_from_web(source_ext_id, source_ext_id)
                    items.extend(extra)
                except Exception:
                    pass

            if items:
                download_images(
                    owned_item_id=owned_item_id,
                    image_items=items,
                    source=source,
                    static_dir=static_dir,
                    source_external_id=source_ext_id,
                )
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()


@router.post("/refresh-images")
def refresh_images(request: Request, owned_item_id: int | None = None, limit: int = 100) -> dict[str, Any]:
    """Refresh downloaded images for items. ADMIN only."""
    _require_admin_request(request)
    from pathlib import Path
    from app.services.image_store import download_images
    from ..db import get_conn
    import sqlite3
    static_dir = Path(__file__).resolve().parent.parent / "static"
    refreshed = skipped = 0
    if owned_item_id:
        row = db.get_owned_item_detail(owned_item_id)
        if not row: raise HTTPException(status_code=404, detail="not found")
        items = [row]
    else:
        with get_conn() as conn:
            conn.row_factory = sqlite3.Row
            items = conn.execute(
                "SELECT oi.id, oi.source_code, oi.source_external_id, mid.cover_image_url "
                "FROM owned_item oi JOIN music_item_detail mid ON mid.owned_item_id = oi.id "
                "WHERE mid.cover_image_url IS NOT NULL AND mid.cover_image_url != '' "
                "ORDER BY oi.id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    for row in items:
        oid = int(row["id"]); src = str(row.get("source_code") or "").strip().upper()
        url = str(row.get("cover_image_url") or "").strip()
        ext_id = str(row.get("source_external_id") or "").strip() or None
        if not url.startswith("http"): skipped += 1; continue
        img_items = [{"type":"앞면","uri":url}]
        if src == "ALADIN" and ext_id:
            try:
                from app.services.providers import _fetch_aladin_images_from_web
                extra = _fetch_aladin_images_from_web(ext_id, ext_id)
                img_items.extend(extra)
            except Exception: pass
        try:
            r = download_images(owned_item_id=oid, image_items=img_items, source=src, static_dir=static_dir, source_external_id=ext_id)
            if r:
                import json as _json
                with get_conn() as conn2:
                    conn2.execute(
                        "UPDATE music_item_detail SET local_image_items_json=? WHERE owned_item_id=?",
                        (_json.dumps(r, ensure_ascii=False), oid)
                    )
                refreshed += 1
            else:
                skipped += 1
        except Exception: skipped += 1
    return {"refreshed": refreshed, "skipped": skipped}


# ── Aladin 이미지 백필 워커 ────────────────────────────────────────────────
import threading as _threading

_ALADIN_BACKFILL_LOCK = _threading.Lock()
_ALADIN_BACKFILL_STATE: dict = {
    "running": False,
    "total": 0,
    "done": 0,
    "skipped": 0,
    "errors": 0,
    "last_error": None,
    "finished_at": None,
}


def _aladin_backfill_worker(dry_run: bool, sleep_sec: float) -> None:
    """백그라운드 Aladin 이미지 백필 워커."""
    import json as _json
    import time as _time
    from pathlib import Path
    from app.services.image_store import download_images
    from app.services.providers import _fetch_aladin_images_from_web, search_aladin_by_barcode
    from ..db import get_conn
    import sqlite3 as _sqlite3

    static_dir = Path(__file__).resolve().parent.parent / "static"

    with get_conn() as conn:
        conn.row_factory = _sqlite3.Row
        # Case 1: ALADIN 소스 + 이미지 없는 항목
        aladin_rows = conn.execute("""
            SELECT oi.id, oi.source_external_id, mid.cover_image_url
            FROM owned_item oi
            JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            WHERE oi.source_code = 'ALADIN'
              AND oi.source_external_id IS NOT NULL
              AND oi.source_external_id != ''
              AND (mid.local_image_items_json IS NULL OR mid.local_image_items_json = '[]')
            ORDER BY oi.id DESC
        """).fetchall()
        # Case 2: 880 바코드 + 2020 이후 + 비알라딘 + 이미지 없는 항목
        cross_rows = conn.execute("""
            SELECT oi.id, mid.barcode, mid.cover_image_url
            FROM owned_item oi
            JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            WHERE (oi.source_code IS NULL OR oi.source_code != 'ALADIN')
              AND mid.barcode LIKE '880%'
              AND mid.release_year >= 2020
              AND (mid.local_image_items_json IS NULL OR mid.local_image_items_json = '[]')
            ORDER BY oi.id DESC
        """).fetchall()

    all_items = [("aladin", dict(r)) for r in aladin_rows] + [("cross", dict(r)) for r in cross_rows]
    _ALADIN_BACKFILL_STATE.update({"total": len(all_items), "done": 0, "skipped": 0, "errors": 0, "last_error": None})

    import logging as _logging
    logger = _logging.getLogger(__name__)

    for kind, row in all_items:
        if not _ALADIN_BACKFILL_STATE.get("running"):
            break  # 외부에서 중단 요청 (/stop 호출 시)

        oid = int(row["id"])
        try:
            img_items: list[dict] = []

            if kind == "aladin":
                ext_id = str(row.get("source_external_id") or "").strip()
                cover = str(row.get("cover_image_url") or "").strip()
                if cover:
                    img_items.append({"type": "앞면", "uri": cover})
                if ext_id:
                    try:
                        extra = _fetch_aladin_images_from_web(ext_id, ext_id)
                        img_items.extend(extra)
                    except Exception as exc:
                        logger.warning("aladin backfill fetch error oid=%d: %s", oid, exc)
                source = "ALADIN"
                ext_id_for_dl = ext_id

            else:  # cross
                barcode = str(row.get("barcode") or "").strip()
                if not barcode:
                    _ALADIN_BACKFILL_STATE["skipped"] += 1
                    continue
                try:
                    candidates = search_aladin_by_barcode(barcode, limit=1)
                except Exception:
                    candidates = []
                if not candidates:
                    _ALADIN_BACKFILL_STATE["skipped"] += 1
                    _time.sleep(sleep_sec)
                    continue
                best = candidates[0]
                aladin_id = str(best.get("external_id") or "").strip()
                cover = str(best.get("cover_image_url") or "").strip()
                if cover:
                    img_items.append({"type": "앞면", "uri": cover})
                if aladin_id:
                    try:
                        extra = _fetch_aladin_images_from_web(aladin_id, aladin_id)
                        img_items.extend(extra)
                    except Exception as exc:
                        logger.warning("aladin cross-fetch error oid=%d: %s", oid, exc)
                source = "ALADIN"
                ext_id_for_dl = aladin_id

            if not img_items:
                _ALADIN_BACKFILL_STATE["skipped"] += 1
                _time.sleep(sleep_sec * 0.5)
                continue

            if not dry_run:
                downloaded = download_images(
                    owned_item_id=oid,
                    image_items=img_items,
                    source=source,
                    static_dir=static_dir,
                    source_external_id=ext_id_for_dl or None,
                )
                if downloaded:
                    with get_conn() as wconn:
                        wconn.execute(
                            "UPDATE music_item_detail SET local_image_items_json=? WHERE owned_item_id=?",
                            (_json.dumps(downloaded, ensure_ascii=False), oid),
                        )
                    _ALADIN_BACKFILL_STATE["done"] += 1
                else:
                    _ALADIN_BACKFILL_STATE["skipped"] += 1
            else:
                _ALADIN_BACKFILL_STATE["done"] += 1

        except Exception as exc:
            _ALADIN_BACKFILL_STATE["errors"] += 1
            _ALADIN_BACKFILL_STATE["last_error"] = f"oid={oid}: {exc}"
            logger.warning("aladin backfill error oid=%d: %s", oid, exc)

        _time.sleep(sleep_sec)

    from datetime import datetime, timezone
    _ALADIN_BACKFILL_STATE["running"] = False
    _ALADIN_BACKFILL_STATE["finished_at"] = datetime.now(timezone.utc).isoformat()


@router.get("/aladin-image-backfill/status")
def get_aladin_image_backfill_status(request: Request) -> dict:
    _require_admin_request(request)
    return dict(_ALADIN_BACKFILL_STATE)


@router.post("/aladin-image-backfill/run")
def run_aladin_image_backfill(
    request: Request,
    dry_run: bool = False,
    sleep_sec: float = 1.5,
) -> dict:
    _require_admin_request(request)
    if _ALADIN_BACKFILL_STATE.get("running"):
        raise HTTPException(status_code=409, detail="aladin image backfill already running")
    _ALADIN_BACKFILL_STATE["running"] = True
    t = _threading.Thread(
        target=_aladin_backfill_worker,
        kwargs={"dry_run": dry_run, "sleep_sec": sleep_sec},
        name="aladin-image-backfill",
        daemon=True,
    )
    t.start()
    return {"status": "started", "dry_run": dry_run, "sleep_sec": sleep_sec}


@router.post("/aladin-image-backfill/stop")
def stop_aladin_image_backfill(request: Request) -> dict:
    _require_admin_request(request)
    _ALADIN_BACKFILL_STATE["running"] = False
    return {"status": "stop_requested"}


def _load_local_image_items(owned_item_id: int) -> list[dict]:
    """music_item_detail.local_image_items_json 읽기."""
    import json as _json
    from ..db import get_conn
    import sqlite3
    with get_conn() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT local_image_items_json FROM music_item_detail WHERE owned_item_id=?",
            (owned_item_id,),
        ).fetchone()
    if not row or not row["local_image_items_json"]:
        return []
    try:
        items = _json.loads(row["local_image_items_json"])
        return items if isinstance(items, list) else []
    except Exception:
        return []


def _save_local_image_items(owned_item_id: int, items: list[dict]) -> None:
    """music_item_detail.local_image_items_json 저장 (upsert)."""
    import json as _json
    from ..db import get_conn, utc_now_iso
    now = utc_now_iso()
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO music_item_detail (owned_item_id, local_image_items_json, created_at, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(owned_item_id) DO UPDATE SET local_image_items_json=excluded.local_image_items_json""",
            (owned_item_id, _json.dumps(items, ensure_ascii=False), now, now),
        )


@router.post("/owned-items/{owned_item_id}/images/upload")
async def upload_owned_item_image(
    owned_item_id: int,
    request: Request,
    image_type: str = Query(default="추가"),
) -> dict:
    """관리자가 직접 이미지 파일을 업로드합니다 (multipart/form-data)."""
    from fastapi import UploadFile
    from pathlib import Path
    from app.services.image_store import _filename, _image_dir
    import hashlib
    _require_admin_request(request)
    row = db.get_owned_item(owned_item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="owned_item not found")

    form = await request.form()
    file = form.get("file")
    if file is None or not hasattr(file, "read"):
        raise HTTPException(status_code=400, detail="file field required")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty file")
    if len(raw) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="file too large (max 20MB)")

    static_dir = Path(__file__).resolve().parent.parent / "static"
    img_dir = _image_dir(static_dir, owned_item_id)
    url_hash = hashlib.md5(raw).hexdigest()[:12]
    content_type = str(getattr(file, "content_type", "") or "")
    ext = ".jpg"
    if "png" in content_type or (getattr(file, "filename", "") or "").lower().endswith(".png"):
        ext = ".png"
    elif "webp" in content_type or (getattr(file, "filename", "") or "").lower().endswith(".webp"):
        ext = ".webp"
    elif "gif" in content_type:
        ext = ".gif"

    existing = _load_local_image_items(owned_item_id)
    idx = len(existing)
    fname = f"{idx:03d}_{url_hash}_upload{ext}"
    local_file = img_dir / fname
    local_file.write_bytes(raw)
    local_path = f"/ui-static/images/owned/{owned_item_id}/{fname}"

    item = {
        "type": str(image_type or "추가").strip() or "추가",
        "local_path": local_path,
        "source_url": None,
        "source": "MANUAL",
    }
    existing.append(item)
    _save_local_image_items(owned_item_id, existing)
    _audit(request, "owned_item", owned_item_id, "IMAGE_UPLOAD")
    return {"local_path": local_path, "index": idx, "items": existing}


@router.post("/owned-items/{owned_item_id}/images/add-url")
def add_owned_item_image_url(
    owned_item_id: int,
    request: Request,
    url: str = Query(...),
    image_type: str = Query(default="추가"),
) -> dict:
    """URL을 입력하면 서버가 다운로드해 저장합니다."""
    from pathlib import Path
    from app.services.image_store import download_images
    _require_admin_request(request)
    row = db.get_owned_item(owned_item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="owned_item not found")
    if not url.startswith("http"):
        raise HTTPException(status_code=400, detail="url must start with http")

    static_dir = Path(__file__).resolve().parent.parent / "static"
    source = str(row.get("source_code") or "MANUAL").strip().upper() or "MANUAL"
    ext_id = str(row.get("source_external_id") or "").strip() or None
    image_type_clean = str(image_type or "추가").strip() or "추가"

    existing = _load_local_image_items(owned_item_id)
    downloaded = download_images(
        owned_item_id=owned_item_id,
        image_items=[{"type": image_type_clean, "uri": url}],
        source=source,
        static_dir=static_dir,
        source_external_id=ext_id,
    )
    if not downloaded:
        raise HTTPException(status_code=400, detail="image download failed — check the URL")

    new_item = downloaded[0]
    # 중복 local_path 방지
    if not any(it.get("local_path") == new_item.get("local_path") for it in existing):
        existing.append(new_item)
        _save_local_image_items(owned_item_id, existing)
    _audit(request, "owned_item", owned_item_id, "IMAGE_URL_ADD")
    return {"local_path": new_item.get("local_path"), "index": len(existing) - 1, "items": existing}


@router.delete("/owned-items/{owned_item_id}/images/{index}")
def delete_owned_item_image(
    owned_item_id: int,
    index: int,
    request: Request,
) -> dict:
    """로컬 이미지를 목록에서 제거합니다 (파일은 보존)."""
    _require_admin_request(request)
    row = db.get_owned_item(owned_item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="owned_item not found")

    existing = _load_local_image_items(owned_item_id)
    if index < 0 or index >= len(existing):
        raise HTTPException(status_code=404, detail=f"image index {index} not found")

    removed = existing.pop(index)
    _save_local_image_items(owned_item_id, existing)
    _audit(request, "owned_item", owned_item_id, "IMAGE_DELETE")
    return {"removed": removed, "items": existing}


@router.post("/owned-items", response_model=OwnedItemCreateResponse)
def create_owned_item(payload: OwnedItemCreate, request: Request) -> OwnedItemCreateResponse:
    _validate_signature(payload)
    _validate_collection_rank(payload)
    _validate_slot(payload.size_group, payload.storage_slot_id)
    _validate_second_hand_music(payload)
    if (payload.source_code and not payload.source_external_id) or (payload.source_external_id and not payload.source_code):
        raise HTTPException(status_code=400, detail="source_code and source_external_id must be provided together")
    linked_master_id = int(payload.linked_album_master_id or 0)
    if linked_master_id > 0 and not db.album_master_exists(linked_master_id):
        raise HTTPException(status_code=400, detail=f"linked_album_master_id not found: {linked_master_id}")

    normalized_payload = payload.model_dump()
    normalized_payload["size_group"] = _normalize_size_group_code(
        normalized_payload.get("size_group"),
        _default_size_group_for_category(normalized_payload.get("category") or payload.category),
    )
    normalized_payload["preferred_storage_size_group"] = _preferred_storage_size_group(
        normalized_payload.get("preferred_storage_size_group"),
        normalized_payload.get("size_group"),
    )
    _normalize_music_detail_payload(normalized_payload)
    _normalize_goods_detail_payload(normalized_payload)
    requested_quantity = max(1, int(normalized_payload.get("quantity") or 1))
    create_count = requested_quantity if requested_quantity > 1 else 1

    copy_group_key = str(normalized_payload.get("copy_group_key") or "").strip() or None
    if create_count > 1 and not copy_group_key:
        copy_group_key = f"COPY-{uuid4().hex[:12].upper()}"

    created_ids: list[int] = []
    notices: list[str] = []
    seen_notices: set[str] = set()
    resolved_master_id = linked_master_id

    for _ in range(create_count):
        one_payload = dict(normalized_payload)
        one_payload["quantity"] = 1
        if copy_group_key:
            one_payload["copy_group_key"] = copy_group_key

        owned_item_id = db.insert_owned_item(one_payload)
        _audit(request, "owned_item", owned_item_id, "CREATE", snapshot=one_payload)
        created_ids.append(owned_item_id)
        resolved_master_id, item_notices = _apply_post_create_links(
            payload=payload,
            owned_item_id=owned_item_id,
            preferred_master_id=resolved_master_id,
        )
        localized_artist_name = _apply_discogs_korean_artist_name_to_owned_item(owned_item_id)
        location_notices = _apply_new_item_location_recommendation(payload=payload, owned_item_id=owned_item_id)
        for msg in item_notices:
            text = str(msg or "").strip()
            if text and text not in seen_notices:
                seen_notices.add(text)
                notices.append(text)
        if localized_artist_name:
            text = f"Discogs 국내 아티스트명을 한글로 정규화했습니다: {localized_artist_name}"
            if text not in seen_notices:
                seen_notices.add(text)
                notices.append(text)
        for msg in location_notices:
            text = str(msg or "").strip()
            if text and text not in seen_notices:
                seen_notices.add(text)
                notices.append(text)

    if create_count > 1:
        shown_ids = ", ".join(str(v) for v in created_ids[:8])
        tail = f" 외 {len(created_ids) - 8}건" if len(created_ids) > 8 else ""
        notices.insert(0, f"동일 상품 복제본 {create_count}건을 개별 인스턴스로 생성했습니다. (owned_item_id: {shown_ids}{tail})")

    first_id = int(created_ids[0])

    # Background image download for newly created items
    _schedule_image_download(first_id, payload)

    return OwnedItemCreateResponse(
        owned_item_id=first_id,
        label_id=_build_label_id(payload.category, first_id),
        linked_album_master_id=resolved_master_id if resolved_master_id > 0 else None,
        notices=notices,
    )


@router.post("/owned-items/{owned_item_id}/auto-master", response_model=OwnedItemAutoMasterResponse)
def create_owned_item_auto_master(owned_item_id: int) -> OwnedItemAutoMasterResponse:
    row = db.get_owned_item_detail(owned_item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="owned_item not found")

    existing_bind = db.get_album_master_binding_for_owned_item(owned_item_id)
    if existing_bind is not None:
        album_master_id = int(existing_bind["album_master_id"])
        source_code = str(existing_bind.get("source_code") or "MANUAL").strip().upper()
        if source_code not in {"DISCOGS", "MANIADB", "MUSICBRAINZ", "MANUAL"}:
            source_code = "MANUAL"
        source_master_id = str(existing_bind.get("source_master_id") or "").strip()
        title = str(existing_bind.get("title") or "").strip() or f"Master {album_master_id}"
        linked_count = len(db.list_owned_items_by_album_master(album_master_id))
        db.set_owned_item_linked_album_master(owned_item_id=owned_item_id, album_master_id=album_master_id)
        return OwnedItemAutoMasterResponse(
            owned_item_id=owned_item_id,
            album_master_id=album_master_id,
            source_code=source_code,
            source_master_id=source_master_id,
            title=title,
            linked_count=linked_count,
            notices=["이미 연결된 마스터를 사용했습니다."],
        )

    notices: list[str] = []
    source_code = str(row.get("source_code") or "").strip().upper()
    source_external_id = str(row.get("source_external_id") or "").strip()

    # ALADIN 등록 시: 바코드로 Discogs 마스터 조회 → 있으면 DISCOGS 마스터로 연결
    if source_code == "ALADIN" and source_external_id:
        main_module = _main()
        snap = main_module.get_source_release_snapshot(source="ALADIN", external_id=source_external_id)
        discogs_crossref: dict[str, Any] | None = (snap or {}).get("discogs_crossref")
        if discogs_crossref:
            d_ext = str(discogs_crossref.get("external_id") or "").strip()
            d_master_id = str(discogs_crossref.get("master_id") or "").strip()
            d_src_id = d_master_id or d_ext
            d_title = str(discogs_crossref.get("title") or "").strip() or str(row.get("item_name_override") or "").strip()
            d_artist = str(discogs_crossref.get("artist_or_brand") or "").strip() or str(row.get("linked_artist_name") or "").strip() or None
            d_year = discogs_crossref.get("master_release_year") or discogs_crossref.get("release_year")
            album_master_id = db.upsert_album_master(
                source_code="DISCOGS",
                source_master_id=d_src_id,
                title=d_title,
                artist_or_brand=d_artist,
                domain_code=_infer_album_master_domain_code(
                    source_code="DISCOGS",
                    title=d_title,
                    artist_or_brand=d_artist,
                    raw=discogs_crossref.get("raw"),
                ),
                release_year=d_year,
                raw=discogs_crossref.get("raw"),
            )
            db.bind_album_master_members(
                album_master_id=album_master_id,
                owned_item_ids=[owned_item_id],
                replace_existing=False,
            )
            db.set_owned_item_linked_album_master(owned_item_id=owned_item_id, album_master_id=album_master_id)
            notice_msg = f"Discogs 마스터 등록 (바코드 매칭): album_master_id={album_master_id}, discogs_id={d_src_id}"
            notices.append(notice_msg)
            linked_count = len(db.list_owned_items_by_album_master(album_master_id))
            return OwnedItemAutoMasterResponse(
                owned_item_id=owned_item_id,
                album_master_id=album_master_id,
                source_code="DISCOGS",
                source_master_id=d_src_id,
                title=d_title,
                linked_count=linked_count,
                notices=notices,
            )

    if _source_supports_master_auto_link(source_code) and source_external_id:
        notices.extend(
            _link_source_master_for_created_item(
                source_code=source_code,
                source_external_id=source_external_id,
                owned_item_id=owned_item_id,
            )
        )
        discogs_bind = db.get_album_master_binding_for_owned_item(owned_item_id)
        if discogs_bind is not None:
            album_master_id = int(discogs_bind["album_master_id"])
            source_master_id = str(discogs_bind.get("source_master_id") or "").strip()
            title = str(discogs_bind.get("title") or "").strip() or f"{source_code} Master {source_master_id}"
            linked_count = len(db.list_owned_items_by_album_master(album_master_id))
            db.set_owned_item_linked_album_master(owned_item_id=owned_item_id, album_master_id=album_master_id)
            return OwnedItemAutoMasterResponse(
                owned_item_id=owned_item_id,
                album_master_id=album_master_id,
                source_code=source_code,
                source_master_id=source_master_id,
                title=title,
                linked_count=linked_count,
                notices=notices,
            )

    master_title, master_artist, master_year, raw = _build_manual_master_seed_from_owned_row(
        owned_item_id=owned_item_id,
        row=row,
    )
    source_master_id = f"OWNED-{owned_item_id}"
    album_master_id = db.upsert_album_master(
        source_code="MANUAL",
        source_master_id=source_master_id,
        title=master_title,
        artist_or_brand=master_artist,
        domain_code=_infer_album_master_domain_code(
            explicit_domain_code=row.get("domain_code"),
            source_code="MANUAL",
            title=master_title,
            artist_or_brand=master_artist,
            raw=raw,
        ),
        release_year=master_year,
        raw=raw,
    )
    linked_count = db.bind_album_master_members(
        album_master_id=album_master_id,
        owned_item_ids=[owned_item_id],
        replace_existing=False,
    )
    db.set_owned_item_linked_album_master(owned_item_id=owned_item_id, album_master_id=album_master_id)
    notices.append("간편 등록 메타를 기준으로 신규 마스터를 생성했습니다.")
    return OwnedItemAutoMasterResponse(
        owned_item_id=owned_item_id,
        album_master_id=album_master_id,
        source_code="MANUAL",
        source_master_id=source_master_id,
        title=master_title,
        linked_count=linked_count,
        notices=notices,
    )


@router.get("/owned-items/{owned_item_id}", response_model=OwnedItemDetailResponse)
def get_owned_item_detail(owned_item_id: int) -> OwnedItemDetailResponse:
    row = db.get_owned_item_detail(owned_item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="owned_item not found")

    category_code = str(row.get("category") or "")
    music_detail = None
    goods_detail = None
    if category_code in MUSIC_CATEGORIES:
        music_detail = {
            "format_name": row.get("format_name") or category_code,
            "is_promotional_not_for_sale": bool(row.get("is_promotional_not_for_sale")),
            "artist_or_brand": row.get("artist_or_brand"),
            "release_year": row.get("release_year"),
            "released_date": row.get("released_date"),
            "barcode": row.get("barcode"),
            "label_name": row.get("label_name"),
            "catalog_no": _discogs_catalog_no(row.get("catalog_no")),
            "cover_image_url": row.get("cover_image_url"),
            "track_list": row.get("track_list") or [],
            "media_type": row.get("media_type"),
            "genres": row.get("genres") or [],
            "styles": row.get("styles") or [],
            "disc_count": row.get("disc_count"),
            "speed_rpm": row.get("speed_rpm"),
            "disc_type": row.get("disc_type"),
            "package_contents": row.get("package_contents"),
            "is_limited_edition": bool(int(row["is_limited_edition"])) if row.get("is_limited_edition") is not None else None,
            "edition_number": row.get("edition_number"),
            "has_obi": row.get("has_obi"),
            "runout_matrix": row.get("runout_matrix"),
            "pressing_country": row.get("pressing_country"),
            "source_notes": row.get("source_notes"),
            "credits": row.get("credits") or [],
            "identifier_items": row.get("identifier_items") or [],
            "image_items": row.get("image_items") or [],
            "company_items": row.get("company_items") or [],
            "series": row.get("series") or [],
            "format_items": row.get("format_items") or [],
            "track_items": row.get("track_items") or [],
            "label_items": row.get("label_items") or [],
            "local_image_items": row.get("local_image_items") or [],
            "cover_condition": row.get("cover_condition"),
            "disc_condition": row.get("disc_condition"),
        }
    else:
        goods_image_urls = row.get("goods_image_urls") or []
        goods_primary_image_url = row.get("goods_primary_image_url")
        poster_storage_spec = row.get("poster_storage_spec")
        tshirt_size = row.get("tshirt_size")
        cup_material = row.get("cup_material")
        hat_size = row.get("hat_size")
        if goods_image_urls or goods_primary_image_url or poster_storage_spec or tshirt_size or cup_material or hat_size:
            goods_detail = {
                "image_urls": goods_image_urls,
                "primary_image_url": goods_primary_image_url,
                "poster_storage_spec": poster_storage_spec,
                "tshirt_size": tshirt_size,
                "cup_material": cup_material,
                "hat_size": hat_size,
            }

    local_image_items = row.get("local_image_items") or []

    return OwnedItemDetailResponse(
        id=int(row["id"]),
        label_id=_build_label_id(category_code, int(row["id"])),
        master_item_id=row.get("master_item_id"),
        category=category_code,
        item_name_override=row.get("item_name_override"),
        quantity=int(row.get("quantity") or 1),
        is_second_hand=bool(row.get("is_second_hand")),
        size_group=str(row.get("size_group") or "STD"),
        preferred_storage_size_group=str(row.get("preferred_storage_size_group") or row.get("size_group") or "STD"),
        status=str(row.get("status") or "IN_COLLECTION"),
        condition_grade=row.get("condition_grade"),
        signature_type=str(row.get("signature_type") or "NONE"),
        source_code=row.get("source_code"),
        source_external_id=row.get("source_external_id"),
        linked_album_master_id=row.get("linked_album_master_id"),
        linked_artist_name=row.get("linked_artist_name"),
        copy_group_key=row.get("copy_group_key"),
        domain_code=row.get("domain_code"),
        release_type=row.get("release_type"),
        purchase_price=row.get("purchase_price"),
        currency_code=row.get("currency_code"),
        purchase_source=row.get("purchase_source"),
        memory_note=row.get("memory_note"),
        display_rank=row.get("display_rank"),
        order_key=row.get("order_key"),
        storage_slot_id=row.get("storage_slot_id"),
        slot_code=row.get("slot_code"),
        thickness_mm=row.get("thickness_mm"),
        notes=row.get("notes"),
        created_at=str(row.get("created_at") or ""),
        updated_at=row.get("updated_at"),
        music_detail=music_detail,
        goods_detail=goods_detail,
        has_audio=bool(row.get("has_audio")),
        audio_asset_count=int(row.get("audio_asset_count") or 0),
        subtype_option_ids=row.get("subtype_option_ids") or [],
        subtype_labels=row.get("subtype_labels") or [],
        soundtrack_option_ids=row.get("soundtrack_option_ids") or [],
        soundtrack_labels=row.get("soundtrack_labels") or [],
        local_image_items=local_image_items,
    )


class _CatalogPatchBody(BaseModel):
    catalog_no: str | None = None
    label_name: str | None = None


@router.patch("/owned-items/{owned_item_id}/catalog")
def update_owned_item_catalog(
    owned_item_id: int,
    body: _CatalogPatchBody,
    request: Request,
) -> dict:
    """빠른 카탈로그 넘버·레이블 저장 (인라인 편집용). OPERATOR+"""
    _require_operator_request(request)
    catalog_no = str(body.catalog_no or "").strip() or None
    label_name = str(body.label_name or "").strip() or None
    from app.db.connection import get_conn, utc_now_iso
    from fastapi import HTTPException
    with get_conn() as conn:
        if not conn.execute("SELECT id FROM owned_item WHERE id=?", (owned_item_id,)).fetchone():
            raise HTTPException(status_code=404, detail="owned_item not found")
        conn.execute(
            "UPDATE music_item_detail SET catalog_no=?, label_name=?, updated_at=? WHERE owned_item_id=?",
            (catalog_no, label_name, utc_now_iso(), owned_item_id),
        )
        conn.execute("UPDATE owned_item SET updated_at=? WHERE id=?", (utc_now_iso(), owned_item_id))
        conn.commit()
    return {"ok": True, "owned_item_id": owned_item_id, "catalog_no": catalog_no, "label_name": label_name}


@router.patch("/owned-items/{owned_item_id}", response_model=OwnedItemCreateResponse)
def update_owned_item(owned_item_id: int, payload: OwnedItemCreate) -> OwnedItemCreateResponse:
    existing = db.get_owned_item(owned_item_id)
    return _save_owned_item_update(owned_item_id=owned_item_id, payload=payload, existing=existing)


@router.post("/owned-items/source-replace-bulk", response_model=OwnedItemSourceReplaceBulkResponse)
def bulk_replace_owned_item_sources(payload: OwnedItemSourceReplaceBulkRequest) -> OwnedItemSourceReplaceBulkResponse:
    results: list[OwnedItemSourceReplaceResult] = []
    updated_count = 0

    for item in payload.items:
        owned_item_id = int(item.owned_item_id)
        try:
            replace_payload = _build_owned_item_payload_for_source_replace(
                owned_item_id=owned_item_id,
                candidate=item.candidate.model_dump(),
            )
            saved = _save_owned_item_update(owned_item_id=owned_item_id, payload=replace_payload)
            updated_count += 1
            results.append(
                OwnedItemSourceReplaceResult(
                    owned_item_id=owned_item_id,
                    label_id=saved.label_id,
                    updated=True,
                    source_code=replace_payload.source_code,
                    source_external_id=replace_payload.source_external_id,
                    linked_album_master_id=saved.linked_album_master_id,
                    notices=saved.notices,
                )
            )
        except HTTPException as exc:
            message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            results.append(
                OwnedItemSourceReplaceResult(
                    owned_item_id=owned_item_id,
                    updated=False,
                    error=message,
                )
            )
        except Exception as exc:
            results.append(
                OwnedItemSourceReplaceResult(
                    owned_item_id=owned_item_id,
                    updated=False,
                    error=str(exc),
                )
            )

    failed_count = len([row for row in results if not row.updated])
    return OwnedItemSourceReplaceBulkResponse(
        requested_count=len(payload.items),
        updated_count=updated_count,
        failed_count=failed_count,
        results=results,
    )


@router.post("/owned-items/bulk-update", response_model=OwnedItemBulkUpdateResponse)
def bulk_update_owned_items(payload: OwnedItemBulkUpdateRequest) -> OwnedItemBulkUpdateResponse:
    owned_item_ids = [int(v) for v in payload.owned_item_ids if int(v) > 0]

    status = str(payload.status or "").strip() or None
    domain_code = _normalize_domain_code(payload.domain_code)
    release_type = str(payload.release_type or "").strip().upper() or None
    if release_type and release_type not in RELEASE_TYPES:
        raise HTTPException(status_code=400, detail="invalid release_type")
    is_second_hand = bool(payload.is_second_hand) if payload.is_second_hand is not None else None
    purchase_source = payload.purchase_source.strip() if isinstance(payload.purchase_source, str) else None
    append_memory_note = payload.append_memory_note.strip() if isinstance(payload.append_memory_note, str) else None
    preferred_storage_size_group = str(payload.preferred_storage_size_group or "").strip().upper() or None
    if preferred_storage_size_group and preferred_storage_size_group not in SIZE_GROUP_CODES:
        raise HTTPException(status_code=400, detail="invalid preferred_storage_size_group")
    size_group = str(payload.size_group or "").strip().upper() or None
    if size_group and size_group not in SIZE_GROUP_CODES:
        raise HTTPException(status_code=400, detail="invalid size_group")
    if (
        status is None
        and domain_code is None
        and release_type is None
        and is_second_hand is None
        and purchase_source is None
        and append_memory_note is None
        and preferred_storage_size_group is None
        and size_group is None
    ):
        raise HTTPException(status_code=400, detail="at least one field is required")

    if not owned_item_ids:
        return OwnedItemBulkUpdateResponse(requested_count=0, updated_count=0)

    _audit(request, "owned_item", 0, "UPDATE", changed_fields=list(payload.updates.keys()) if hasattr(payload, "updates") else None)
    updated_item_ids = db.bulk_update_owned_items(
        owned_item_ids,
        status=status,
        release_type=release_type,
        is_second_hand=is_second_hand,
        purchase_source=purchase_source,
        append_memory_note=append_memory_note,
        preferred_storage_size_group=preferred_storage_size_group,
        size_group=size_group,
    )
    return OwnedItemBulkUpdateResponse(
        requested_count=len({int(v) for v in owned_item_ids}),
        updated_count=len(updated_item_ids),
        updated_item_ids=updated_item_ids,
    )


@router.post(
    "/owned-items/bulk-update-music-detail",
    response_model=OwnedItemBulkUpdateMusicDetailResponse,
)
def bulk_update_music_detail(
    payload: OwnedItemBulkUpdateMusicDetailRequest,
    request: Request,
) -> OwnedItemBulkUpdateMusicDetailResponse:
    """Update music_item_detail.media_type for multiple owned items. ADMIN only."""
    _require_admin_request(request)
    updated_item_ids = db.bulk_update_music_detail(
        payload.owned_item_ids,
        media_type=payload.media_type,
    )
    return OwnedItemBulkUpdateMusicDetailResponse(
        requested_count=len(payload.owned_item_ids),
        updated_count=len(updated_item_ids),
        updated_item_ids=updated_item_ids,
    )


@router.delete("/owned-items/{owned_item_id}", response_model=OwnedItemDeleteResponse)
def delete_owned_item(owned_item_id: int) -> OwnedItemDeleteResponse:
    deleted = db.delete_owned_item(owned_item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="owned_item not found")
    return OwnedItemDeleteResponse(owned_item_id=owned_item_id, deleted=True)


@router.patch("/owned-items/{owned_item_id}/slot", response_model=SlotUpdateResponse)
def update_owned_item_slot(owned_item_id: int, payload: SlotUpdateRequest) -> SlotUpdateResponse:
    existing = db.get_owned_item(owned_item_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="owned_item not found")

    _validate_slot(existing["size_group"], payload.storage_slot_id)
    previous_slot_id = existing.get("storage_slot_id")
    db.update_owned_item_slot(owned_item_id, payload.storage_slot_id)
    if previous_slot_id != payload.storage_slot_id and payload.storage_slot_id is not None:
        db.inherit_owned_item_domain_from_slot_if_missing(owned_item_id, int(payload.storage_slot_id))
    if str(existing.get("status") or "").strip().upper() == "IN_COLLECTION" and previous_slot_id != payload.storage_slot_id:
        if payload.storage_slot_id is not None:
            db.realign_owned_item_order_after_slot_move(owned_item_id, int(payload.storage_slot_id))
        else:
            db.resequence_in_collection_order()

    return SlotUpdateResponse(owned_item_id=owned_item_id, storage_slot_id=payload.storage_slot_id)


@router.post("/owned-items/{owned_item_id}/restore-previous-slot")
def restore_owned_item_previous_slot(owned_item_id: int) -> dict[str, Any]:
    existing = db.get_owned_item(owned_item_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="owned_item not found")

    result = db.restore_owned_item_previous_slot(owned_item_id)
    if result is None:
        raise HTTPException(status_code=404, detail="owned_item not found")
    if not bool(result.get("restored")):
        raise HTTPException(status_code=400, detail=str(result.get("reason") or "restore failed"))
    if str(existing.get("status") or "").strip().upper() == "IN_COLLECTION":
        restored_slot_id = result.get("storage_slot_id")
        if restored_slot_id is not None:
            db.realign_owned_item_order_after_slot_move(owned_item_id, int(restored_slot_id))
        else:
            db.resequence_in_collection_order()
    return result


@router.patch("/owned-items/{owned_item_id}/order", response_model=OrderMoveResponse)
def move_owned_item_order(owned_item_id: int, payload: OrderMoveRequest) -> OrderMoveResponse:
    try:
        order_key = db.move_owned_item_order(
            owned_item_id=owned_item_id,
            target_owned_item_id=payload.target_owned_item_id,
            position=payload.position,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return OrderMoveResponse(
        owned_item_id=owned_item_id,
        target_owned_item_id=payload.target_owned_item_id,
        position=payload.position,
        order_key=order_key,
    )


@router.post("/owned-items/{owned_item_id}/digital-links", response_model=DigitalLinkCreateResponse)
def create_digital_link(
    owned_item_id: int,
    payload: DigitalLinkCreate,
) -> DigitalLinkCreateResponse:
    existing = db.get_owned_item(owned_item_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="owned_item not found")

    ids = db.insert_digital_link(owned_item_id, payload.model_dump())

    return DigitalLinkCreateResponse(
        owned_item_id=owned_item_id,
        digital_asset_id=ids["digital_asset_id"],
        link_id=ids["link_id"],
    )


@router.get("/owned-items/{owned_item_id}/track-mappings", response_model=TrackMappingListResponse)
def get_track_mappings(owned_item_id: int) -> TrackMappingListResponse:
    existing = db.get_owned_item(owned_item_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="owned_item not found")

    track_list = db.get_owned_item_track_list(owned_item_id)
    links = db.list_owned_item_track_links(owned_item_id)

    grouped: dict[int, list[TrackMappedAssetItem]] = {}
    for row in links:
        track_no = int(row.get("track_no") or 0)
        if track_no <= 0:
            continue
        grouped.setdefault(track_no, []).append(
            TrackMappedAssetItem(
                link_id=int(row["link_id"]),
                digital_asset_id=int(row["digital_asset_id"]),
                file_path=str(row["file_path"]),
                duration_sec=row.get("duration_sec"),
                note=row.get("note"),
                created_at=str(row["created_at"]),
            )
        )

    mappings: list[TrackMappingItem] = []
    for idx, entry in enumerate(track_list, start=1):
        mappings.append(
            TrackMappingItem(
                track_no=idx,
                track_entry=entry,
                assets=grouped.get(idx, []),
            )
        )

    return TrackMappingListResponse(
        owned_item_id=owned_item_id,
        track_count=len(track_list),
        mappings=mappings,
    )


@router.post("/owned-items/{owned_item_id}/track-mappings", response_model=TrackMappingCreateResponse)
def create_track_mapping(
    owned_item_id: int,
    payload: TrackMappingCreateRequest,
) -> TrackMappingCreateResponse:
    existing = db.get_owned_item(owned_item_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="owned_item not found")

    track_list = db.get_owned_item_track_list(owned_item_id)
    if not track_list:
        raise HTTPException(status_code=400, detail="track_list not found for this owned_item")
    if payload.track_no > len(track_list):
        raise HTTPException(status_code=400, detail=f"track_no out of range (max={len(track_list)})")

    track_entry = track_list[payload.track_no - 1]
    note = payload.note.strip() if payload.note else track_entry
    link_payload: dict[str, object] = {
        "asset_type": "AUDIO",
        "file_path": payload.file_path,
        "link_type": "TRACK",
        "file_hash": payload.file_hash,
        "file_size_bytes": payload.file_size_bytes,
        "duration_sec": payload.duration_sec,
        "metadata_json": payload.metadata_json,
        "track_no": payload.track_no,
        "note": note,
    }

    ids = db.insert_digital_link(owned_item_id, link_payload)
    return TrackMappingCreateResponse(
        owned_item_id=owned_item_id,
        track_no=payload.track_no,
        digital_asset_id=ids["digital_asset_id"],
        link_id=ids["link_id"],
    )


