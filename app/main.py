from __future__ import annotations

import asyncio
import csv
from email import policy as email_policy
from email.parser import Parser as EmailParser
from email.parser import BytesParser as EmailBytesParser
from email.utils import parsedate_to_datetime
import io
import inspect
import json
import logging
import os
import platform
import plistlib
import re
import shutil
import socket
from html import unescape as html_unescape
from html.parser import HTMLParser
import secrets
import sqlite3
import subprocess
import threading
import tempfile
import time
import base64
import hashlib
import hmac
import zipfile
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import quote, unquote, urlparse
from uuid import uuid4
from xml.etree import ElementTree as ET

import httpx
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Path as FastAPIPath, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from . import config as config_module
from . import db
from . import schemas as schemas_module
from .config import get_settings
from .schemas import (
    AlbumMasterImportVariantsRequest,
    AlbumMasterListItem,
    AlbumMasterVariantItem,
    ArtistContextRequest,
    ArtistContextResponse,
    BarcodeIngestRequest,
    BarcodeIngestResponse,
    BarcodePlacementRecommendationItem,
    BarcodePlacementRecommendationRequest,
    BarcodePlacementRecommendationResponse,
    CabinetCameraConnectionTestRequest,
    CabinetCameraConnectionTestResponse,
    CabinetCameraDiscoveryItem,
    CabinetCameraDeleteResponse,
    CabinetCameraItem,
    CabinetCameraUpsertRequest,
    ClassificationOptionCreate,
    ClassificationOptionItem,
    CollectionDashboardResponse,
    CustomerTrackRequestCreate,
    CustomerTrackRequestItem,
    CustomerTrackRequestListResponse,
    RoonStatusResponse,
    CustomerTrackRequestUpdate,
    CsvIngestResponse,
    DiscogsIdentityResponse,
    DiscogsOwnedSyncResponse,
    OpsCollectorInfoResponse,
    DirectoryPickerRequest,
    DirectoryPickerResponse,
    AudioDirectoryMappingCreateRequest,
    AudioDirectoryMappingCreateResponse,
    AudioDirectoryFileItem,
    AudioDirectoryFileListResponse,
    AudioDirectoryMappingItem,
    AudioDirectoryMappingListResponse,
    AutoBackupSettingsResponse,
    AutoBackupSettingsUpdateRequest,
    DatabaseRestoreResponse,
    GoodsCategory,
    GoodsItemAlbumMasterMapping,
    GoodsItemCollectibleRelation,
    GoodsItemCreateRequest,
    GoodsItemMappingUpdateRequest,
    GoodsItemRelationUpdateRequest,
    GoodsItemResponse,
    GoodsItemSearchResponse,
    GoodsItemUpdateRequest,
    GoodsCollectibleRelationState,
    GoodsLinkedState,
    GoodsStatus,
    DomainCode,
    OrderMoveRequest,
    SlotOrderMoveResponse,
    MetadataSyncItemResult,
    MetadataProviderConnectionTestResponse,
    MetadataProviderSettingsResponse,
    MetadataProviderSettingsUpdateRequest,
    MetadataSyncRunRequest,
    MetadataSyncRunResponse,
    MetadataSyncStatusResponse,
    MusicDetailCreate,
    OwnedItemCreate,
    OwnedItemCreateResponse,
    OwnedItemListItem,
    OperatorCatalogSearchItem,
    OperatorCatalogSearchResponse,
    OfficeClimateResponse,
    OpsHomeFeedResponse,
    OpsHomeRecentItem,
    OpsHomeRecentSectionsResponse,
    PurchaseImportPreviewItem,
    PurchaseImportPreviewRequest,
    PurchaseImportCreateResponse,
    PurchaseImportQueueItem,
    PurchaseImportWebhookRequest,
    QueryIngestRequest,
    QueryIngestResponse,
    ReviewQueueItem,
    StorageCabinetDeleteResponse,
    StorageCabinetRegisterRequest,
    StorageCabinetRegisterResponse,
    StorageSlotItem,
    StorageSlotUpsertRequest,
    TrackMappingBulkFromDirRequest,
    TrackMappingBulkFromDirResponse,
    TrackMappingBulkMappedItem,
    TrackMappingManualAssignRequest,
    TrackMappingManualAssignResponse,
    UiImageUploadResponse,
)
from .services import artist_context as artist_context_service
from .services.matcher import MatchResult, classify_candidate, compose_query, validate_row_for_ingest
from .services.providers import (
    discogs_add_release_to_collection,
    discogs_identity,
    fetch_aladin_track_items,
    has_default_user_agent_placeholder,
    infer_domain_code,
    get_source_release_snapshot,
    get_discogs_release_year_from_cache,
    get_discogs_snapshot_from_master_id,
    get_album_master_variants,
    get_album_master_variants_page,
    resolve_discogs_preferred_korean_artist_name,
    resolve_release_master_reference,
    search_album_master_candidates,
    search_discogs_artist_name_variations,
    search_music_metadata,
)
from .services.metadata_sync import (  # noqa: E402
    MUSIC_CATEGORIES,
    METADATA_SYNC_LOCK,
    METADATA_SYNC_STOP_EVENT,
    METADATA_SYNC_THREAD,
    METADATA_SYNC_LAST_RESULT,
    METADATA_SYNC_LAST_ERROR,
    METADATA_SYNC_IN_PROGRESS_ITEMS,
    _build_music_detail_for_sync,
    _get_master_member_track_fallback,
    _item_meta_fields,
    _run_metadata_sync,
    _metadata_sync_worker,
    _start_metadata_sync_worker,
    _sync_one_item,
    _trigger_sync_image_download,
    _download_images_for_item,
    _has_local_images,
    _start_sync_image_download_thread,
)
from .services.candidate_search import (  # noqa: E402
    _clean_text,
    _normalize_lookup_text,
    _normalize_compact_lookup_text,
    _lookup_match_level,
    _lookup_compact_match_level,
    _candidate_artist_match_level,
    _candidate_title_match_level,
    _candidate_matches_artist_filter,
    _candidate_matches_title_filter,
    _is_maniadb_artist_candidate,
    _filter_maniadb_candidates,
    _DIRECT_MB_RELEASE_PATTERN,
    _parse_direct_source_reference,
    _metadata_candidate_from_snapshot,
    _dedupe_metadata_candidates,
    _build_direct_metadata_candidates,
    _clean_track_list,
    _clean_string_list,
    _clean_dict_list,
    _clean_runout_list,
    _normalize_has_obi_input,
    _clean_goods_image_urls,
    _normalize_positive_int,
    _candidate_collector_base,
    _is_blank_text,
)
from .services.site import (  # noqa: E402
    _tail_text_lines, _read_qa_summary,
    _serialize_env_value, _write_env_updates,
)
from .services.discogs_mapper import (  # noqa: E402
    ALLOWED_IMAGE_CONTENT_TYPES,
    DISCOGS_COVER_PREVIEW_CACHE_DIR,
    _contains_hangul_artist_name,
    _discogs_artist_name_needs_localization,
    _discogs_artist_value,
    _discogs_catalog_no,
    _discogs_compare_variants,
    _discogs_company_items,
    _discogs_companies,
    _discogs_cover_preview_cache_name,
    _discogs_cover_preview_cached_file,
    _discogs_cover_preview_source_url,
    _discogs_credit_items,
    _discogs_credits,
    _discogs_format_items,
    _discogs_format_values,
    _discogs_identifiers,
    _discogs_image_items,
    _discogs_label_items,
    _discogs_labels,
    _discogs_primary_format,
    _discogs_release_year,
    _discogs_string_list,
    _discogs_text,
    _discogs_track_items,
    _ensure_discogs_cover_preview,
    _fetch_discogs_cover_preview_bytes,
)

class OwnedItemRelationSaveItem(BaseModel):
    relation_type: Literal["MASTER_CHILD", "SERIES_MEMBER", "BOX_MEMBER_OF", "RELATED_RELEASE"]
    target_kind: Literal["ALBUM_MASTER", "COPY_GROUP", "OWNED_ITEM", "PRODUCT_GROUP"]
    target_ref: str
    note: str | None = None
    display_order: int | None = 0


class OwnedItemRelationSaveRequest(BaseModel):
    relations: list[OwnedItemRelationSaveItem] = Field(default_factory=list)


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan handler.

    Replaces the deprecated `@app.on_event("startup"/"shutdown")` pattern.
    The body references names defined later in this module — that's fine
    because lifespan only fires after the entire module has loaded, by
    which time all the worker globals (`METADATA_SYNC_*`, `AUTO_BACKUP_*`,
    `_start_*_worker`) are bound.
    """
    db.ensure_startup_db_ready()
    _seed_system_accounts()
    if has_default_user_agent_placeholder():
        logger.warning(
            "DISCOGS_USER_AGENT/MUSICBRAINZ_USER_AGENT still contain the example "
            "'your-email@example.com' placeholder. Discogs and MusicBrainz both "
            "require a real contact in the User-Agent; update .env.local before "
            "running metadata sync against production traffic.",
        )
    _start_metadata_sync_worker()
    _start_auto_backup_worker()
    asyncio.create_task(_cafe_now_playing_worker())  # SSE now-playing worker
    try:
        yield
    finally:
        METADATA_SYNC_STOP_EVENT.set()
        AUTO_BACKUP_STOP_EVENT.set()


app = FastAPI(title="Hahahoho Library API", version="0.1.0", lifespan=lifespan)


OWNED_ITEM_SAVE_SLOW_SEC = float(os.getenv("OWNED_ITEM_SAVE_SLOW_SEC", "0.7"))
from .db import DOMAIN_CODES, LABEL_PREFIX_BY_CATEGORY, LEGACY_DOMAIN_CODE_MAP  # noqa: E402
RELEASE_TYPES = {"ALBUM", "EP", "SINGLE"}
SIZE_GROUP_CODES = {"STD", "BOOK", "LP", "LP10", "LP7", "OVERSIZE", "CASSETTE", "8TRACK", "REEL_TO_REEL", "GOODS"}
from .services.site import (  # noqa: E402
    STATIC_DIR,
    IMAGE_UPLOAD_DIR,
    HTML_NO_CACHE_HEADERS,
    HTML_PROD_CACHE_HEADERS,
    MAX_IMAGE_UPLOAD_BYTES,
    _is_qa_env,
)
LOGIN_PAGE_PATH = STATIC_DIR / "login.html"
from .security import (
    AUTH_COOKIE_MAX_AGE,
    AUTH_COOKIE_NAME,
    AUTH_ROLE_ADMIN,
    AUTH_ROLE_OPERATOR,
    AUTH_ROLE_VIEWER,
    _auth_accounts,
    _auth_cookie_signature,
    _auth_cookie_value,
    _auth_enabled,
    _db_auth_accounts,
    _env_seed_account_candidates,
    _extra_operator_accounts,
    _hash_auth_password,
    _is_admin_role,
    _is_authenticated,
    _is_html_request,
    _is_operator_role,
    _match_auth_account,
    _read_auth_role,
    _read_auth_session_data,
    _read_auth_username,
    _require_admin_request,
    _require_operator_request,
    _require_authenticated_request,
    _seed_system_accounts,
    _verify_auth_password,
)
ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
    ".heic",
    ".heif",
}
from .services.backfill import (  # noqa: E402
    ALADIN_DISCOGS_BACKFILL_LOCK, ALADIN_DISCOGS_BACKFILL_THREAD,
    ALADIN_DISCOGS_BACKFILL_LAST_RESULT, ALADIN_DISCOGS_BACKFILL_LAST_ERROR,
    SPOTIFY_BATCH_LOCK, SPOTIFY_BATCH_THREAD,
    SPOTIFY_BATCH_LAST_RESULT, SPOTIFY_BATCH_LAST_ERROR,
    DISCOGS_KOREAN_BACKFILL_LOCK, DISCOGS_KOREAN_BACKFILL_THREAD, DISCOGS_KOREAN_BACKFILL_RESULT,
    MANIADB_RELEASE_TYPE_BACKFILL_LOCK, MANIADB_RELEASE_TYPE_BACKFILL_RESULT,
    _run_aladin_discogs_backfill, _aladin_discogs_backfill_thread_worker,
    _spotify_batch_thread_worker, _discogs_korean_backfill_worker,
    _run_maniadb_release_type_backfill, _maniadb_release_type_backfill_worker,
)
from .services.backup import AUTO_BACKUP_LOCK, AUTO_BACKUP_STOP_EVENT, AUTO_BACKUP_THREAD  # noqa: E402
LAUNCHD_LOG_DIR = Path.home() / "Library" / "Logs" / "__PROJECT_SLUG__-library"
LAUNCHD_ERR_LOG_PATH = LAUNCHD_LOG_DIR / "library.err.log"


def _resolve_project_root() -> Path:
    raw = os.getenv("LIBRARY_PROJECT_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


PROJECT_ROOT = _resolve_project_root()
PROJECT_LAUNCHD_ERR_LOG_PATH = PROJECT_ROOT / "logs" / "launchd" / "library.err.log"
PROJECT_QA_MASTER_SHEET_PATH = PROJECT_ROOT / "docs" / "qa" / "qa_master_sheet.csv"
PROJECT_QA_MANUAL_SHEET_PATH = PROJECT_ROOT / "docs" / "qa" / "qa_manual_remaining.csv"
PROJECT_ERD_SUMMARY_PATH = PROJECT_ROOT / "docs" / "library_erd_operator.md"
PROJECT_ERD_DETAIL_PATH = PROJECT_ROOT / "docs" / "library_erd.md"
PROJECT_TOOL_MANUAL_PATH = PROJECT_ROOT / "docs" / "management_tool_manual.md"
PROJECT_GO_LIVE_CHECKLIST_PATH = PROJECT_ROOT / "docs" / "go_live_checklist.md"
PROJECT_PURCHASE_IMPORT_GUIDE_PATH = PROJECT_ROOT / "docs" / "purchase_mail_import.md"
PROJECT_CSV_IMPORT_SAMPLE_PATH = PROJECT_ROOT / "docs" / "csv_import_sample.csv"
PURCHASE_ITEM_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

settings = get_settings()

app.mount("/ui-static", StaticFiles(directory=STATIC_DIR), name="ui-static")


# Domain routers extracted from this file. New domains should land in
# app/api/<name>.py and be wired below — keep this list short and
# alphabetised so reviewers can spot duplicates.
from .api.admin_auth_accounts import router as admin_auth_accounts_router  # noqa: E402
from .api.auth import router as auth_router  # noqa: E402  (must follow `app` definition)

app.include_router(admin_auth_accounts_router)
app.include_router(auth_router)


_METADATA_PROVIDER_ENV_KEYS = (
    "DISCOGS_TOKEN",
    "ALADIN_TTB_KEY",
    "DEEPL_AUTH_KEY",
    "DISCOGS_USER_AGENT",
    "MUSICBRAINZ_USER_AGENT",
    "ALADIN_BASE_URL",
    "MANIADB_BASE_URL",
    "DEEPL_BASE_URL",
)


@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception):
    import asyncio
    import traceback as _tb
    from pathlib import Path as _Path
    from fastapi import HTTPException as _HTTPEx
    from fastapi.responses import JSONResponse
    from fastapi.exception_handlers import http_exception_handler

    if isinstance(exc, _HTTPEx):
        return await http_exception_handler(request, exc)

    tb_str = _tb.format_exc()
    source = ""
    tb_obj = exc.__traceback__
    if tb_obj:
        frames = _tb.extract_tb(tb_obj)
        if frames:
            last = frames[-1]
            source = f"{last.filename.replace(str(_Path(__file__).parent.parent) + '/', '')}:{last.name}"

    body_str: str | None = None
    try:
        body_bytes = await request.body()
        if body_bytes:
            body_str = body_bytes[:2048].decode("utf-8", errors="replace")
    except Exception:
        pass

    try:
        from app.db.error_log import insert_error_log
        insert_error_log(
            level="ERROR",
            source=source or None,
            message=str(exc)[:500],
            traceback=tb_str[:8000],
            request_path=f"{request.method} {request.url.path}",
            request_body=body_str,
        )
    except Exception:
        pass

    try:
        from app.services.kakao_notify import send_kakao_message
        msg = (
            f"[hahahoho 에러 알림]\n"
            f"🔴 ERROR\n"
            f"경로: {request.method} {request.url.path}\n"
            f"내용: {str(exc)[:200]}\n"
            f"위치: {source}"
        )
        asyncio.ensure_future(send_kakao_message(msg))
    except Exception:
        pass

    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


_PERF_SKIP_PREFIXES = ("/ui-static/", "/health", "/cafe/now-playing/stream", "/cafe/tablet")

_UI_STATIC_NO_CACHE_PREFIXES = ("/ui-static/css/", "/ui-static/js/")


@app.middleware("http")
async def ui_static_cache_control_middleware(request: Request, call_next):
    response = await call_next(request)
    if any(request.url.path.startswith(p) for p in _UI_STATIC_NO_CACHE_PREFIXES):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.middleware("http")
async def perf_timing_middleware(request: Request, call_next):
    path = request.url.path
    if any(path.startswith(p) for p in _PERF_SKIP_PREFIXES):
        return await call_next(request)

    import time as _time
    from app.config import get_settings as _gs
    from app.db.perf_log import insert_perf_log as _insert_perf

    start = _time.perf_counter()
    response = await call_next(request)
    elapsed_ms = int((_time.perf_counter() - start) * 1000)

    settings = _gs()
    is_slow = elapsed_ms >= settings.perf_slow_api_ms
    if is_slow or response.status_code >= 500:
        try:
            name = f"{request.method} {path}"
            _insert_perf(
                kind="API",
                name=name,
                duration_ms=elapsed_ms,
                is_slow=is_slow,
                context={"status_code": response.status_code},
            )
        except Exception:
            pass

    return response


@app.middleware("http")
async def auth_guard(request: Request, call_next):
    if not _auth_enabled():
        return await call_next(request)

    path = request.url.path.rstrip("/") or "/"
    allowed_paths = {
        "/health",
        "/catalog-stats",
        "/login",
        "/auth/login",
        "/auth/logout",
        "/auth/session",
        "/purchase-imports/webhook/gmail",
        "/cafe/search",
        "/cafe/request",
        "/cafe/queue",
        "/cafe/now-playing",
        "/cafe/now-playing/stream",
        "/cafe/tablet",
        "/cafe/lyrics",
        "/cafe/tags",
        "/cafe/local-cover",
        "/random-album",
        "/spotify/callback",
    }
    if path in allowed_paths or path.startswith("/ui-static/"):
        return await call_next(request)

    session = _read_auth_session_data(request)
    request.state.auth_session = session or {}
    if session is not None:
        role = str(session.get("role") or "").strip().upper()
        # VIEWER role: read-only (GET/HEAD/OPTIONS only)
        if role == AUTH_ROLE_VIEWER and request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
            return JSONResponse(status_code=403, content={"detail": "viewer write access denied"})
        return await call_next(request)

    if request.method == "GET" and _is_html_request(request):
        path_str = request.url.path
        if path_str and path_str != "/":
            import urllib.parse
            encoded_path = urllib.parse.quote(path_str)
            return RedirectResponse(url=f"/login?next={encoded_path}", status_code=303)
        return RedirectResponse(url="/login", status_code=303)
    return JSONResponse(status_code=401, content={"detail": "authentication required"})


def _build_album_master_candidate_from_release_reference(source: str, release_external_id: str) -> dict[str, Any] | None:
    master_ref = resolve_release_master_reference(source=source, external_id=release_external_id)
    if not isinstance(master_ref, dict):
        return None
    source_code = str(master_ref.get("source") or source).strip().upper()
    master_external_id = str(master_ref.get("master_external_id") or "").strip()
    if not source_code or not master_external_id:
        return None
    preview = None
    if source_code in {"DISCOGS", "MANIADB"}:
        variants = get_album_master_variants(source=source_code, master_external_id=master_external_id, limit=1, include_details=False)
        preview = variants[0] if variants else None
    return {
        "source": source_code,
        "master_external_id": master_external_id,
        "title": _clean_text(master_ref.get("title")) or _clean_text((preview or {}).get("title")) or f"{source_code} Master #{master_external_id}",
        "artist_or_brand": _clean_text(master_ref.get("artist_or_brand")) or _clean_text((preview or {}).get("artist_or_brand")),
        "release_year": master_ref.get("release_year") if master_ref.get("release_year") is not None else (preview or {}).get("release_year"),
        "label_name": _clean_text((preview or {}).get("label_name")),
        "catalog_no": _discogs_catalog_no((preview or {}).get("catalog_no")),
        "barcode": _clean_text((preview or {}).get("barcode")),
        "cover_image_url": _clean_text((preview or {}).get("cover_image_url")),
        "variant_count": None,
        "confidence": 1.0,
        "raw": {"direct_reference": release_external_id, "kind": "release"},
    }


def _build_album_master_candidate_from_master_reference(source: str, master_external_id: str) -> dict[str, Any] | None:
    source_code = str(source or "").strip().upper()
    preview = None
    variant_count = None
    if source_code in {"DISCOGS", "MANIADB"}:
        variants = get_album_master_variants(source=source_code, master_external_id=master_external_id, limit=30, include_details=False)
        if variants:
            preview = variants[0]
            variant_count = len(variants)
    if source_code not in {"DISCOGS", "MANIADB"}:
        return None
    domain_code: str | None
    if source_code == "MANIADB":
        domain_code = "KOREA"
    else:
        domain_code = _clean_text((preview or {}).get("domain_code")) or None
    return {
        "source": source_code,
        "master_external_id": str(master_external_id or "").strip(),
        "title": _clean_text((preview or {}).get("title")) or f"{source_code} Master #{master_external_id}",
        "artist_or_brand": _clean_text((preview or {}).get("artist_or_brand")),
        "domain_code": domain_code,
        "release_year": (preview or {}).get("release_year"),
        "label_name": _clean_text((preview or {}).get("label_name")),
        "catalog_no": _discogs_catalog_no((preview or {}).get("catalog_no")),
        "barcode": _clean_text((preview or {}).get("barcode")),
        "cover_image_url": _clean_text((preview or {}).get("cover_image_url")),
        "variant_count": variant_count,
        "confidence": 1.0,
        "raw": {"direct_reference": master_external_id, "kind": "master"},
    }


def _build_direct_album_master_candidates(query: str | None, *, source: str = "AUTO") -> list[dict[str, Any]] | None:
    parsed = _parse_direct_source_reference(query, source=source)
    if not parsed:
        return None
    source_code = parsed["source"]
    kind = parsed["kind"]
    external_id = parsed["external_id"]
    if kind == "release":
        candidate = _build_album_master_candidate_from_release_reference(source_code, external_id)
        return [candidate] if candidate else []
    if source_code == "DISCOGS" and kind == "master":
        candidate = _build_album_master_candidate_from_master_reference("DISCOGS", external_id)
        return [candidate] if candidate else []
    if source_code == "MANIADB" and kind == "album":
        candidate = _build_album_master_candidate_from_master_reference("MANIADB", external_id.split(":", 1)[0].strip())
        return [candidate] if candidate else []
    return []


def _search_discogs_with_artist_variations(
    *,
    artist_or_brand: str | None,
    title: str | None,
    category: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    artist_text = _clean_text(artist_or_brand)
    title_text = _clean_text(title)
    if not artist_text:
        return []
    variation_names = search_discogs_artist_name_variations(artist_text, limit=6, suppress_errors=True)
    if not variation_names:
        return []
    collected: list[dict[str, Any]] = []
    seen_queries: set[str] = set()

    def run_query(search_query: str) -> list[dict[str, Any]]:
        normalized_query = _normalize_lookup_text(search_query)
        if not normalized_query or normalized_query in seen_queries:
            return []
        seen_queries.add(normalized_query)
        return search_music_metadata(
            query=search_query,
            category=category,
            source="DISCOGS",
            limit=limit,
        )

    for variation_name in variation_names:
        variation_text = _clean_text(variation_name)
        if not variation_text:
            continue
        query_text = " ".join(part for part in [variation_text, title_text] if part).strip()
        results = run_query(query_text)
        if title_text:
            results = [c for c in results if _candidate_matches_title_filter(c, title_text)]
        if results:
            collected.extend(results)
            break

    if not collected and title_text:
        for variation_name in variation_names:
            variation_text = _clean_text(variation_name)
            if not variation_text:
                continue
            results = run_query(variation_text)
            matched = [c for c in results if _candidate_matches_title_filter(c, title_text)]
            if matched:
                collected.extend(matched)
                break

    return _dedupe_metadata_candidates(collected, limit)


def _search_lookup_metadata_candidates(
    *,
    query: str,
    category: str | None,
    source: str,
    limit: int,
    artist_or_brand: str | None = None,
    title: str | None = None,
) -> list[dict[str, Any]]:
    direct_candidates = _build_direct_metadata_candidates(query, source=source, limit=limit)
    if direct_candidates is not None:
        return direct_candidates

    hint_kwargs = {
        key: value
        for key, value in {
            "artist_or_brand": artist_or_brand,
            "title": title,
        }.items()
        if value is not None
    }
    try:
        signature = inspect.signature(search_music_metadata)
    except (TypeError, ValueError):
        signature = None

    def build_search_kwargs(next_query: str, next_title: str | None) -> dict[str, Any]:
        search_kwargs: dict[str, Any] = {
            "query": next_query,
            "category": category,
            "source": source,
            "limit": limit,
        }
        next_hint_kwargs = {
            key: value
            for key, value in {
                "artist_or_brand": artist_or_brand,
                "title": next_title,
            }.items()
            if value is not None
        }
        if not next_hint_kwargs:
            return search_kwargs
        if signature is None:
            search_kwargs.update(next_hint_kwargs)
            return search_kwargs
        if any(param.kind is inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()):
            search_kwargs.update(next_hint_kwargs)
            return search_kwargs
        search_kwargs.update(
            {
                key: value
                for key, value in next_hint_kwargs.items()
                if key in signature.parameters
            }
        )
        return search_kwargs

    candidates = search_music_metadata(**build_search_kwargs(query, title))

    source_u = str(source or "").strip().upper()
    if source_u == "MANIADB" and (artist_or_brand or title):
        candidates = _filter_maniadb_candidates(
            candidates,
            artist_or_brand=artist_or_brand,
            title=title,
        )
        if not candidates and title:
            seen_titles: set[str] = set()
            retry_titles = [
                part.strip()
                for part in re.split(r"\s*/\s*", str(title or "").strip())
                if part and part.strip()
            ]
            for retry_title in retry_titles:
                normalized_retry_title = _normalize_lookup_text(retry_title)
                if not normalized_retry_title or normalized_retry_title in seen_titles:
                    continue
                seen_titles.add(normalized_retry_title)
                retry_query = " ".join(part for part in [artist_or_brand, retry_title] if part and str(part).strip()).strip()
                if not retry_query:
                    retry_query = retry_title
                retry_candidates = search_music_metadata(**build_search_kwargs(retry_query, retry_title))
                retry_candidates = _filter_maniadb_candidates(
                    retry_candidates,
                    artist_or_brand=artist_or_brand,
                    title=retry_title,
                )
                if retry_candidates:
                    candidates = retry_candidates
                    break

    if candidates or source_u not in {"AUTO", "DISCOGS"}:
        return candidates

    if artist_or_brand or title:
        return _search_discogs_with_artist_variations(
            artist_or_brand=artist_or_brand,
            title=title,
            category=category,
            limit=limit,
        )

    return []


from .services import purchase_mail as _pm_service
from .services.purchase_mail import (
    _parse_price_number,
    _parse_positive_int,
    _normalize_purchase_date,
    _purchase_message_from_raw_content,
    _purchase_message_from_raw_bytes,
    _resolve_purchase_import_vendor_code,
    _extract_purchase_date_from_raw_content,
    _resolve_purchase_import_purchase_date,
    _split_artist_item_text,
    _PURCHASE_CONDITION_TOKEN_PATTERN,
    _normalize_purchase_condition_token,
    _extract_purchase_condition_pair,
    _strip_ebay_listing_search_suffix,
    _parse_ebay_purchase_title,
    _purchase_ebay_parse_source_text,
    _purchase_queue_display_item_name,
    _normalize_purchase_media_format,
    _purchase_import_media_format_or_default,
    _PurchaseMailTableParser,
    _purchase_rows_from_html,
    _purchase_rows_from_text,
    _extract_html_from_mhtml,
    _extract_html_from_mhtml_bytes,
    _purchase_html_from_raw_content,
    _decode_purchase_import_upload_bytes,
    _purchase_html_from_upload_bytes,
    _resolve_purchase_import_raw_input,
    _purchase_compact_text,
    _purchase_dense_text,
    _purchase_normalize_item_url,
    _purchase_currency_code,
    _purchase_host_from_url,
    _purchase_marketplace_currency,
    _purchase_amazon_marketplace_from_raw_content,
    _extract_purchase_price_from_text,
    _extract_purchase_date_from_text,
    _extract_purchase_total_from_text,
    _build_purchase_preview_item_direct,
    _purchase_amazon_asin_from_url,
    _purchase_amazon_marketplace_from_url,
    _purchase_fetch_item_page_html,
    _purchase_extract_amazon_artist_name,
    _purchase_normalize_amazon_detail_key,
    _purchase_extract_amazon_detail_map,
    _purchase_extract_amazon_detail_enrichment,
    _purchase_extract_ebay_detail_enrichment,
    _purchase_enrich_row_from_item_page,
    _purchase_preview_items_from_amazon_html,
    _purchase_preview_items_from_amazon_order_details_html,
    _purchase_preview_items_from_ebay_html,
    _purchase_import_empty_reason,
    _build_purchase_preview_item,
    _parse_purchase_import_preview,
    _purchase_queue_item_from_row,
    _purchase_import_webhook_allowed,
    PURCHASE_IMPORT_WEBHOOK_MAX_BODY_BYTES,
    _PURCHASE_IMPORT_WEBHOOK_ALLOWED_CONTENT_TYPES,
    _purchase_import_webhook_validate_request,
    _require_purchase_import_webhook_envelope,
)


from .services.backup import (  # noqa: E402 — re-export for backward compat
    _normalize_backup_dir_path,
    _write_db_snapshot_to_path,
    _create_local_db_backup,
    _create_local_full_backup_bundle,
    _read_launchd_calendar_interval,
    _format_launchd_schedule_label,
    _read_backup_launchd_schedules,
    _validate_library_db_file,
    _restore_library_db_from_upload,
    _restore_library_bundle_from_upload,
    _maybe_run_auto_backup_once,
    _auto_backup_worker,
    _start_auto_backup_worker,
)


from .services.camera import (  # noqa: E402 — re-export for backward compat
    _camera_http_url_or_none,
    _camera_rtsp_url_or_none,
    _camera_stream_url_with_credentials,
    _camera_snapshot_bytes_from_stream,
    _xml_local_name,
    _onvif_wsse_security_header,
    _onvif_soap_request,
    _find_first_descendant_text,
    _find_media_service_xaddr,
    _test_onvif_camera_connection,
    _discover_onvif_devices,
)


from .services.purchase_mail import (
    _purchase_import_rows_for_save,
    _purchase_queue_base_context,
    _purchase_queue_memory_note,
    _purchase_queue_candidate_query,
    _build_owned_item_from_purchase_queue_row,
    _purchase_import_duplicate_create_response,
)


from .services.home_env import (  # noqa: E402 — re-export for backward compat
    _home_assistant_api_base_url,
    _fetch_home_assistant_state,
    _coerce_home_assistant_number,
    _office_climate_comfort_label,
    _load_operator_office_climate,
    _load_operator_seoul_weather,
    _wmo_weather_code_to_desc,
)


def _build_label_id(category: str, owned_item_id: int) -> str:
    prefix = LABEL_PREFIX_BY_CATEGORY.get(category, "IT")
    return f"{prefix}-{owned_item_id:06d}"


def _resolve_owned_item_relation_scope(row: dict[str, Any]) -> tuple[str, str, bool]:
    copy_group_key = str(row.get("copy_group_key") or "").strip()
    if copy_group_key:
        return "COPY_GROUP", copy_group_key, True
    return "OWNED_ITEM", str(row.get("id") or ""), False


def _fetch_owned_item_relation_brief(conn: sqlite3.Connection, owned_item_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
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
        WHERE oi.id = ?
        """,
        (owned_item_id,),
    ).fetchone()
    return dict(row) if row else None


def _fetch_owned_item_relation_group_items(conn: sqlite3.Connection, copy_group_key: str) -> list[dict[str, Any]]:
    key = str(copy_group_key or "").strip()
    if not key:
        return []
    rows = conn.execute(
        """
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
        WHERE oi.copy_group_key = ?
        ORDER BY oi.id ASC
        """,
        (key,),
    ).fetchall()
    return [dict(row) for row in rows]


def _owned_item_relation_label(row: dict[str, Any]) -> str:
    title = str(row.get("item_name_override") or "").strip()
    if not title:
        title = str(row.get("master_title") or "").strip()
    if not title:
        title = _build_label_id(str(row.get("category") or ""), int(row.get("id") or 0))
    return title


def _to_owned_item_list_item(row: dict[str, object]) -> OwnedItemListItem:
    row2 = dict(row)
    category_code = str(row2.get("category") or "")
    owned_item_id = int(row2.get("id") or 0)
    row2["label_id"] = _build_label_id(category_code, owned_item_id)
    row2["preferred_storage_size_group"] = str(
        row2.get("preferred_storage_size_group") or row2.get("size_group") or "STD"
    )
    # Prioritize album_master domain over owned_item domain
    row2["domain_code"] = _normalize_domain_code(
        row2.get("master_domain_code") or row2.get("domain_code")
    )
    source_code = str(row2.get("source_code") or "").strip().upper()
    source_external_id = str(row2.get("source_external_id") or "").strip()
    released_date = str(row2.get("released_date") or "").strip()
    if not released_date and source_code == "MANIADB" and source_external_id:
        source_snapshot = get_source_release_snapshot(source_code, source_external_id)
        snapshot_released_date = str((source_snapshot or {}).get("released_date") or "").strip()
        if snapshot_released_date:
            row2["released_date"] = snapshot_released_date
    return OwnedItemListItem(**row2)


def _resolve_discogs_master_id_from_album_context(
    master_external_id: str,
    album_master_id: int | None = None,
) -> tuple[str, bool]:
    master_id = str(master_external_id or "").strip()
    target_album_master_id = int(album_master_id or 0)
    if not master_id or target_album_master_id <= 0:
        return master_id, False

    member_rows = db.list_owned_items_by_album_master(target_album_master_id)
    hint_release_id = ""
    for row in member_rows:
        source_code = str(row.get("source_code") or "").strip().upper()
        source_external_id = str(row.get("source_external_id") or "").strip()
        if source_code == "DISCOGS" and source_external_id:
            hint_release_id = source_external_id
            break
    if not hint_release_id:
        return master_id, False

    master_ref = resolve_release_master_reference(source="DISCOGS", external_id=hint_release_id)
    resolved_master_id = str(master_ref.get("master_external_id") or "").strip() if isinstance(master_ref, dict) else ""
    if resolved_master_id and resolved_master_id != master_id:
        return resolved_master_id, True
    return master_id, False


def _infer_music_category_from_format(format_name: str | None) -> str:
    text = str(format_name or "").strip().upper()
    if "REEL" in text:
        return "REEL_TO_REEL"
    if "8-TRACK" in text or "8 TRACK" in text or "8TRACK" in text:
        return "8TRACK"
    if "DIGITAL SINGLE" in text or "DIGITAL EP" in text or "DIGITAL ALBUM" in text:
        return "CD"
    if "DIGITAL" in text or "FILE" in text or "DOWNLOAD" in text:
        return "DIGITAL"
    if "CASSETTE" in text or text in {"TAPE", "MC"}:
        return "CASSETTE"
    if "CD" in text:
        return "CD"
    if "LP" in text or "VINYL" in text or "12" in text or "10" in text or "7" in text:
        return "LP"
    return "CD"


def _default_size_group_for_category(category: str) -> str:
    code = str(category).upper()
    if code == "LP":
        return "LP"
    if code == "CASSETTE":
        return "CASSETTE"
    if code == "8TRACK":
        return "8TRACK"
    if code == "REEL_TO_REEL":
        return "REEL_TO_REEL"
    if code in {"T_SHIRT", "POSTER", "LIGHT_STICK", "HAT", "BAG", "CUP", "OTHER"}:
        return "GOODS"
    return "STD"


def _normalize_size_group_code(value: Any, fallback: Any = "STD") -> str:
    text = str(value or "").strip().upper()
    if text in SIZE_GROUP_CODES:
        return text
    fallback_text = str(fallback or "").strip().upper()
    if fallback_text in SIZE_GROUP_CODES:
        return fallback_text
    return "STD"


def _preferred_storage_size_group(value: Any, fallback: Any) -> str:
    return _normalize_size_group_code(value, fallback)


def _resolve_master_seed_from_variants(
    payload: AlbumMasterImportVariantsRequest,
    variant_by_external: dict[str, dict[str, Any]],
    selected_external_ids: list[str],
) -> tuple[str, str | None, int | None, dict[str, Any]]:
    title = str(payload.title or "").strip()
    artist_or_brand = str(payload.artist_or_brand or "").strip() or None
    release_year = payload.release_year
    if title:
        raw = dict(payload.raw or {})
        return title, artist_or_brand, release_year, raw

    for ext in selected_external_ids:
        row = variant_by_external.get(ext)
        if not row:
            continue
        if not title:
            title = str(row.get("title") or "").strip()
        if not artist_or_brand:
            artist_or_brand = str(row.get("artist_or_brand") or "").strip() or None
        if release_year is None:
            raw_year = row.get("release_year")
            try:
                release_year = int(raw_year) if raw_year is not None else None
            except (TypeError, ValueError):
                release_year = None
        if title and (artist_or_brand is not None or release_year is not None):
            break

    if not title:
        title = f"{payload.source} Master {payload.master_external_id}"

    raw = dict(payload.raw or {})
    raw.setdefault("import_mode", "MASTER_VARIANT_BATCH")
    raw.setdefault("source", str(payload.source))
    raw.setdefault("master_external_id", str(payload.master_external_id))
    raw.setdefault("selected_variant_external_ids", list(selected_external_ids))
    return title, artist_or_brand, release_year, raw


def _merge_variant_with_release_snapshot(
    variant: dict[str, Any],
    snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(variant or {})
    if not isinstance(snapshot, dict):
        return merged

    for key, value in snapshot.items():
        if key == "raw":
            if isinstance(value, dict) and value:
                merged["raw_detail"] = value
            continue
        if value in (None, "", [], {}):
            continue
        merged[key] = value
    return merged


def _validate_signature(payload: OwnedItemCreate) -> None:
    if (payload.signed_by or payload.signed_at) and payload.signature_type == "NONE":
        raise HTTPException(status_code=400, detail="signature_type cannot be NONE when signed_by/signed_at is set")


def _validate_collection_rank(payload: OwnedItemCreate) -> None:
    # 장식장/슬롯 재배치에 대비해 display_rank는 선택값으로 처리.
    return


def _validate_slot(size_group: str, storage_slot_id: int | None) -> None:
    if storage_slot_id is None:
        return

    slot = db.get_storage_slot(storage_slot_id)
    if slot is None:
        raise HTTPException(status_code=404, detail="storage_slot not found")


def _validate_second_hand_music(_payload: OwnedItemCreate) -> None:
    # 중고 여부와 무관하게 컨디션 값은 선택 입력으로 허용.
    return


def _normalize_domain_code(value: Any) -> str | None:
    code = str(value or "").strip().upper()
    if not code:
        return None
    code = LEGACY_DOMAIN_CODE_MAP.get(code, code)
    return code if code in DOMAIN_CODES else None


def _master_domain_hint(linked_album_master_id: Any) -> str | None:
    try:
        master_id = int(linked_album_master_id or 0)
    except (TypeError, ValueError):
        master_id = 0
    if master_id <= 0:
        return None
    return _normalize_domain_code(db.get_album_master_domain_hint(master_id))


def _infer_owned_item_domain_code(
    normalized_payload: dict[str, object],
    music_detail: dict[str, Any] | None = None,
    source_snapshot: dict[str, object] | None = None,
) -> str | None:
    music = music_detail if isinstance(music_detail, dict) else {}
    snapshot = source_snapshot if isinstance(source_snapshot, dict) else {}
    genres = music.get("genres") or snapshot.get("genres") or []
    styles = music.get("styles") or snapshot.get("styles") or []
    # DISCOGS 소스는 pressing_country를 country 신호로 쓰지 않는다.
    # 제조국(pressing country)은 아티스트 국적과 무관하며, 이미
    # _fetch_discogs_release_detail에서 master_country 우선으로 처리된 후
    # source_snapshot["domain_code"]로 넘어오기 때문이다.
    _src = str(normalized_payload.get("source_code") or "").strip().upper()
    if _src == "DISCOGS":
        country = None  # genres/styles/artist_name 으로만 판단
    else:
        country = (
            music.get("pressing_country")
            or snapshot.get("pressing_country")
            or snapshot.get("country")
            or music.get("country")
        )
    artist_or_brand = (
        music.get("artist_or_brand")
        or snapshot.get("artist_or_brand")
        or normalized_payload.get("linked_artist_name")
    )
    title = normalized_payload.get("item_name_override") or snapshot.get("title")
    label_name = music.get("label_name") or snapshot.get("label_name")
    source_code = normalized_payload.get("source_code")
    inferred = infer_domain_code(
        genres=genres if isinstance(genres, list) else [],
        styles=styles if isinstance(styles, list) else [],
        country=country,
        artist_or_brand=artist_or_brand,
        title=title,
        label_name=label_name,
        source=str(source_code or "").strip().upper() or None,
    )
    return (
        _normalize_domain_code(inferred)
        or db.lookup_label_domain(label_name)
        or _master_domain_hint(normalized_payload.get("linked_album_master_id"))
    )


def _infer_album_master_domain_code(
    *,
    explicit_domain_code: Any = None,
    source_code: Any = None,
    title: Any = None,
    artist_or_brand: Any = None,
    raw: Any = None,
    linked_album_master_id: Any = None,
) -> str | None:
    explicit = _normalize_domain_code(explicit_domain_code)
    if explicit:
        return explicit

    raw_dict = raw if isinstance(raw, dict) else {}
    raw_domain = _normalize_domain_code(raw_dict.get("domain_code"))
    if raw_domain:
        return raw_domain

    label_name = raw_dict.get("label_name")
    if not label_name and isinstance(raw_dict.get("label_items"), list):
        first = raw_dict["label_items"][0] if raw_dict["label_items"] else None
        if isinstance(first, dict):
            label_name = first.get("name")

    inferred = infer_domain_code(
        genres=raw_dict.get("genres") if isinstance(raw_dict.get("genres"), list) else None,
        styles=raw_dict.get("styles") if isinstance(raw_dict.get("styles"), list) else None,
        country=raw_dict.get("country") or raw_dict.get("pressing_country"),
        artist_or_brand=artist_or_brand,
        title=title,
        label_name=label_name,
        source=str(source_code or "").strip().upper() or None,
    )
    return (
        _normalize_domain_code(inferred)
        or db.lookup_label_domain(label_name)
        or _master_domain_hint(linked_album_master_id)
    )
def _rewrite_artist_prefixed_item_name(
    item_name_override: Any,
    previous_artist_names: list[str | None],
    preferred_artist_name: str,
) -> str | None:
    current_text = _clean_text(item_name_override)
    preferred_text = _clean_text(preferred_artist_name)
    if not current_text or not preferred_text:
        return current_text

    seen: set[str] = set()
    for candidate in previous_artist_names:
        previous_text = _clean_text(candidate)
        if not previous_text or previous_text == preferred_text:
            continue
        key = previous_text.casefold()
        if key in seen:
            continue
        seen.add(key)
        if current_text == previous_text:
            return preferred_text
        prefix = f"{previous_text} - "
        if current_text.startswith(prefix):
            return f"{preferred_text} - {current_text[len(prefix):]}"
    return current_text


def _owned_item_discogs_artist_row(owned_item_id: int) -> dict[str, Any] | None:
    with db.get_conn() as conn:
        row = conn.execute(
            """
            SELECT
              oi.id,
              oi.source_code,
              oi.source_external_id,
              oi.linked_artist_name,
              oi.item_name_override,
              oi.linked_album_master_id,
              COALESCE(NULLIF(TRIM(oi.domain_code), ''), NULLIF(TRIM(am.domain_code), ''), '') AS domain_code,
              mid.artist_or_brand AS music_artist_or_brand,
              am.artist_or_brand AS master_artist_or_brand,
              am.sort_artist_name AS master_sort_artist_name
            FROM owned_item oi
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
            WHERE oi.id = ?
            LIMIT 1
            """,
            (int(owned_item_id),),
        ).fetchone()
    return dict(row) if row else None


def _resolve_owned_item_discogs_korean_artist_name(
    row: dict[str, Any],
    *,
    source_snapshot: dict[str, Any] | None = None,
) -> str | None:
    source_code = str(row.get("source_code") or "").strip().upper()
    source_external_id = str(row.get("source_external_id") or "").strip()
    if source_code != "DISCOGS" or not source_external_id:
        return None

    master_sort_artist_name = _clean_text(row.get("master_sort_artist_name"))
    if master_sort_artist_name and _contains_hangul_artist_name(master_sort_artist_name):
        return master_sort_artist_name

    artist_text = (
        _clean_text(row.get("music_artist_or_brand"))
        or _clean_text(row.get("linked_artist_name"))
        or _clean_text(row.get("master_artist_or_brand"))
    )
    if not artist_text or _contains_hangul_artist_name(artist_text):
        return artist_text or None

    snapshot = source_snapshot if isinstance(source_snapshot, dict) else get_source_release_snapshot("DISCOGS", source_external_id)
    snapshot_artist = _clean_text((snapshot or {}).get("artist_or_brand"))
    preferred_artist_name = resolve_discogs_preferred_korean_artist_name(
        snapshot_artist or artist_text,
        external_id=source_external_id,
        raw=(snapshot or {}).get("raw") if isinstance((snapshot or {}).get("raw"), dict) else None,
        domain_code=(snapshot or {}).get("domain_code") or row.get("domain_code"),
    )
    preferred_text = _clean_text(preferred_artist_name)
    if preferred_text and _contains_hangul_artist_name(preferred_text):
        return preferred_text
    return None


def _apply_discogs_korean_artist_name_to_row(
    row: dict[str, Any],
    preferred_artist_name: str,
) -> bool:
    owned_item_id = int(row.get("id") or 0)
    linked_album_master_id = int(row.get("linked_album_master_id") or 0)
    preferred_text = _clean_text(preferred_artist_name)
    if owned_item_id <= 0 or not preferred_text:
        return False

    linked_artist_name = _clean_text(row.get("linked_artist_name"))
    music_artist_name = _clean_text(row.get("music_artist_or_brand"))
    master_artist_name = _clean_text(row.get("master_artist_or_brand"))
    master_sort_artist_name = _clean_text(row.get("master_sort_artist_name"))
    item_name_override = _clean_text(row.get("item_name_override"))
    rewritten_item_name = _rewrite_artist_prefixed_item_name(
        item_name_override,
        [music_artist_name, linked_artist_name, master_artist_name],
        preferred_text,
    )

    changed = False
    with db.get_conn() as conn:
        now = db.utc_now_iso()
        if not linked_artist_name or _discogs_artist_name_needs_localization(linked_artist_name):
            conn.execute(
                """
                UPDATE owned_item
                SET linked_artist_name = ?, updated_at = ?
                WHERE id = ?
                """,
                (preferred_text, now, owned_item_id),
            )
            changed = True
        if rewritten_item_name and rewritten_item_name != item_name_override:
            conn.execute(
                """
                UPDATE owned_item
                SET item_name_override = ?, updated_at = ?
                WHERE id = ?
                """,
                (rewritten_item_name, now, owned_item_id),
            )
            changed = True
        if not music_artist_name or _discogs_artist_name_needs_localization(music_artist_name):
            conn.execute(
                """
                UPDATE music_item_detail
                SET artist_or_brand = ?, updated_at = ?
                WHERE owned_item_id = ?
                """,
                (preferred_text, now, owned_item_id),
            )
            changed = True
        if linked_album_master_id > 0:
            if not master_artist_name or _discogs_artist_name_needs_localization(master_artist_name):
                conn.execute(
                    """
                    UPDATE album_master
                    SET artist_or_brand = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (preferred_text, now, linked_album_master_id),
                )
                changed = True
            if not master_sort_artist_name or _discogs_artist_name_needs_localization(master_sort_artist_name):
                conn.execute(
                    """
                    UPDATE album_master
                    SET sort_artist_name = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (preferred_text, now, linked_album_master_id),
                )
                changed = True
            ext_ref_row = conn.execute(
                """
                SELECT artist_or_brand_hint
                FROM album_master_external_ref
                WHERE album_master_id = ?
                  AND source_code = 'DISCOGS'
                LIMIT 1
                """,
                (linked_album_master_id,),
            ).fetchone()
            ext_ref_artist_hint = _clean_text(ext_ref_row["artist_or_brand_hint"]) if ext_ref_row is not None else None
            if ext_ref_row is not None and (
                not ext_ref_artist_hint or _discogs_artist_name_needs_localization(ext_ref_artist_hint)
            ):
                cur = conn.execute(
                    """
                    UPDATE album_master_external_ref
                    SET artist_or_brand_hint = ?, updated_at = ?
                    WHERE album_master_id = ?
                      AND source_code = 'DISCOGS'
                    """,
                    (preferred_text, now, linked_album_master_id),
                )
                if int(cur.rowcount or 0) > 0:
                    changed = True
    return changed


def _apply_discogs_korean_artist_name_to_owned_item(owned_item_id: int) -> str | None:
    row = _owned_item_discogs_artist_row(owned_item_id)
    if not row:
        return None
    preferred_artist_name = _resolve_owned_item_discogs_korean_artist_name(row)
    if not preferred_artist_name:
        return None
    changed = _apply_discogs_korean_artist_name_to_row(row, preferred_artist_name)
    if changed and _contains_hangul_artist_name(preferred_artist_name):
        return preferred_artist_name
    return None


def backfill_discogs_korean_artist_names(limit: int | None = None) -> dict[str, int]:
    with db.get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
              oi.id,
              oi.source_code,
              oi.source_external_id,
              oi.linked_artist_name,
              oi.item_name_override,
              oi.linked_album_master_id,
              COALESCE(NULLIF(TRIM(oi.domain_code), ''), NULLIF(TRIM(am.domain_code), ''), '') AS domain_code,
              mid.artist_or_brand AS music_artist_or_brand,
              am.artist_or_brand AS master_artist_or_brand,
              am.sort_artist_name AS master_sort_artist_name
            FROM owned_item oi
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
            WHERE oi.source_code = 'DISCOGS'
              AND TRIM(COALESCE(oi.source_external_id, '')) <> ''
            ORDER BY oi.id ASC
            """
        ).fetchall()

    scanned_rows = [dict(row) for row in rows]
    if isinstance(limit, int) and limit > 0:
        scanned_rows = scanned_rows[:limit]

    preferred_name_cache: dict[str, str | None] = {}
    updated_items = 0
    for row in scanned_rows:
        if _normalize_domain_code(row.get("domain_code")) != "KOREA":
            continue
        if not any(
            _discogs_artist_name_needs_localization(row.get(field))
            for field in ("music_artist_or_brand", "linked_artist_name", "master_artist_or_brand", "master_sort_artist_name")
        ):
            continue

        cache_key = _normalize_lookup_text(
            row.get("music_artist_or_brand")
            or row.get("linked_artist_name")
            or row.get("master_artist_or_brand")
            or row.get("source_external_id")
        )
        if not cache_key:
            continue
        if cache_key not in preferred_name_cache:
            preferred_name_cache[cache_key] = _resolve_owned_item_discogs_korean_artist_name(row)
        preferred_artist_name = preferred_name_cache.get(cache_key)
        if not preferred_artist_name:
            continue
        if _apply_discogs_korean_artist_name_to_row(row, preferred_artist_name):
            updated_items += 1

    return {"scanned_items": len(scanned_rows), "updated_items": updated_items}


def _link_discogs_master_for_created_item(
    source_external_id: str,
    owned_item_id: int,
) -> list[str]:
    return _link_source_master_for_created_item("DISCOGS", source_external_id, owned_item_id)


def _source_master_notice_prefix(source_code: str) -> str:
    source_u = str(source_code or "").strip().upper()
    if source_u == "DISCOGS":
        return "Discogs"
    if source_u == "MANIADB":
        return "ManiaDB"
    return source_u or "Source"


def _source_supports_master_auto_link(source_code: str) -> bool:
    return str(source_code or "").strip().upper() in {"DISCOGS", "MANIADB"}


def _source_master_variant_external_ids(
    source_code: str,
    master_external_id: str,
    release_external_id: str,
) -> set[str]:
    source_u = str(source_code or "").strip().upper()
    external_ids: set[str] = {str(release_external_id or "").strip()}
    if source_u == "MANIADB" and master_external_id:
        external_ids.add(str(master_external_id).strip())
        external_ids.add(f"album:{str(master_external_id).strip()}")
    if source_u not in {"DISCOGS", "MANIADB"}:
        return {ext for ext in external_ids if ext}
    try:
        variants = get_album_master_variants(
            source=source_u,
            master_external_id=master_external_id,
            limit=2000 if source_u == "MANIADB" else 200,
        )
    except Exception:
        variants = []
    for variant in variants:
        ext = str(variant.get("external_id") or "").strip()
        if ext:
            external_ids.add(ext)
    return {ext for ext in external_ids if ext}


def _link_source_master_for_created_item(
    source_code: str,
    source_external_id: str,
    owned_item_id: int,
) -> list[str]:
    source_u = str(source_code or "").strip().upper()
    release_external_id = str(source_external_id or "").strip()
    if not _source_supports_master_auto_link(source_u) or not release_external_id or owned_item_id <= 0:
        return []
    source_label = _source_master_notice_prefix(source_u)

    same_release_rows = [
        row for row in db.list_owned_items_by_source_external_ids(source_u, [release_external_id])
        if int(row.get("id") or 0) != owned_item_id
    ]
    same_release_ids = sorted({int(row["id"]) for row in same_release_rows if int(row.get("id") or 0) > 0})

    try:
        master_ref = resolve_release_master_reference(source=source_u, external_id=release_external_id)
    except Exception:
        master_ref = None
    if not master_ref:
        if not same_release_ids:
            return []
        shown = ", ".join(str(v) for v in same_release_ids[:8])
        tail = f" 외 {len(same_release_ids) - 8}건" if len(same_release_ids) > 8 else ""
        return [
            f"{source_label} 연계: release_id={release_external_id}로 등록되었습니다.",
            f"동일 {source_label} 상품(release_id)으로 이미 등록된 상품이 있습니다 (owned_item_id: {shown}{tail}). 마스터 기준으로 관리하세요.",
        ]

    master_external_id = str(master_ref.get("master_external_id") or "").strip()
    if not master_external_id:
        if not same_release_ids:
            return []
        shown = ", ".join(str(v) for v in same_release_ids[:8])
        tail = f" 외 {len(same_release_ids) - 8}건" if len(same_release_ids) > 8 else ""
        return [
            f"{source_label} 연계: release_id={release_external_id}로 등록되었습니다.",
            f"동일 {source_label} 상품(release_id)으로 이미 등록된 상품이 있습니다 (owned_item_id: {shown}{tail}). 마스터 기준으로 관리하세요.",
        ]

    external_ids = _source_master_variant_external_ids(source_u, master_external_id, release_external_id)

    existing_rows = [
        row for row in db.list_owned_items_by_source_external_ids(source_u, sorted(external_ids))
        if int(row.get("id") or 0) != owned_item_id
    ]
    existing_ids = sorted({int(row["id"]) for row in existing_rows if int(row.get("id") or 0) > 0})

    master_title = str(master_ref.get("title") or "").strip() or f"Discogs Master {master_external_id}"
    master_artist = str(master_ref.get("artist_or_brand") or "").strip() or None
    master_year_raw = master_ref.get("release_year")
    master_year: int | None
    try:
        master_year = int(master_year_raw) if master_year_raw is not None else None
    except (TypeError, ValueError):
        master_year = None

    album_master_id = db.get_album_master_id_by_external_ref(source_u, master_external_id)
    if album_master_id:
        db.ensure_album_master_external_ref(
            album_master_id=album_master_id,
            source_code=source_u,
            source_master_id=master_external_id,
            title_hint=master_title,
            artist_or_brand_hint=master_artist,
            release_year=master_year,
            raw=master_ref if isinstance(master_ref, dict) else {},
        )
    else:
        album_master_id = db.upsert_album_master(
            source_code=source_u,
            source_master_id=master_external_id,
            title=master_title,
            artist_or_brand=master_artist,
            domain_code=_infer_album_master_domain_code(
                source_code=source_u,
                title=master_title,
                artist_or_brand=master_artist,
                raw=master_ref,
            ),
            release_year=master_year,
            raw=master_ref if isinstance(master_ref, dict) else {},
        )
    db.bind_album_master_members(
        album_master_id=album_master_id,
        owned_item_ids=[owned_item_id, *existing_ids],
        replace_existing=False,
    )
    for target_owned_id in [owned_item_id, *existing_ids]:
        if target_owned_id > 0:
            db.set_owned_item_linked_album_master(owned_item_id=target_owned_id, album_master_id=album_master_id)

    notices = [f"{source_label} 연계: release_id={release_external_id}, master_id={master_external_id}로 함께 관리됩니다."]
    if existing_ids:
        shown = ", ".join(str(v) for v in existing_ids[:8])
        tail = f" 외 {len(existing_ids) - 8}건" if len(existing_ids) > 8 else ""
        notices.append(
            f"동일 {source_label} 마스터로 이미 등록된 상품이 있습니다 (owned_item_id: {shown}{tail}). 마스터 기준으로 관리하세요."
        )
    return notices


def _attach_source_master_ref_to_album_master(
    album_master_id: int,
    source_code: str,
    source_external_id: str,
) -> list[str]:
    master_id = int(album_master_id or 0)
    source_u = str(source_code or "").strip().upper()
    release_external_id = str(source_external_id or "").strip()
    if master_id <= 0 or not _source_supports_master_auto_link(source_u) or not release_external_id:
        return []

    try:
        master_ref = resolve_release_master_reference(source=source_u, external_id=release_external_id)
    except Exception:
        master_ref = None
    if not master_ref:
        return []

    master_external_id = str(master_ref.get("master_external_id") or "").strip()
    if not master_external_id:
        return []

    existing_master_id = db.get_album_master_id_by_external_ref(source_u, master_external_id)
    if existing_master_id and existing_master_id != master_id:
        merged = db.merge_album_masters(source_album_master_id=existing_master_id, target_album_master_id=master_id)
        moved_member_count = int(merged.get("moved_member_count") or 0)
        db.ensure_album_master_external_ref(
            album_master_id=master_id,
            source_code=source_u,
            source_master_id=master_external_id,
            title_hint=str(master_ref.get("title") or "").strip() or None,
            artist_or_brand_hint=str(master_ref.get("artist_or_brand") or "").strip() or None,
            release_year=master_ref.get("release_year") if isinstance(master_ref.get("release_year"), int) else None,
            raw=master_ref if isinstance(master_ref, dict) else {},
        )
        return [
            f"{_source_master_notice_prefix(source_u)} 마스터 연계: 선택한 마스터에 외부 마스터 ID를 연결했습니다.",
            f"기존 {_source_master_notice_prefix(source_u)} 마스터를 병합했습니다. (이동 멤버 수: {moved_member_count})",
        ]

    db.ensure_album_master_external_ref(
        album_master_id=master_id,
        source_code=source_u,
        source_master_id=master_external_id,
        title_hint=str(master_ref.get("title") or "").strip() or None,
        artist_or_brand_hint=str(master_ref.get("artist_or_brand") or "").strip() or None,
        release_year=master_ref.get("release_year") if isinstance(master_ref.get("release_year"), int) else None,
        raw=master_ref if isinstance(master_ref, dict) else {},
    )
    return [f"{_source_master_notice_prefix(source_u)} 마스터 연계: 선택한 마스터에 외부 마스터 ID를 연결했습니다."]


def _promote_album_master_to_discogs(
    album_master_id: int,
    source_external_id: str,
) -> tuple[int, list[str]]:
    master_id = int(album_master_id or 0)
    release_external_id = str(source_external_id or "").strip()
    if master_id <= 0 or not release_external_id:
        return master_id, []

    try:
        master_ref = resolve_release_master_reference(source="DISCOGS", external_id=release_external_id)
    except Exception:
        master_ref = None
    if not isinstance(master_ref, dict):
        return master_id, []

    discogs_master_id = str(master_ref.get("master_external_id") or "").strip()
    if not discogs_master_id:
        return master_id, []

    title = str(master_ref.get("title") or "").strip() or f"Discogs Master {discogs_master_id}"
    artist_or_brand = str(master_ref.get("artist_or_brand") or "").strip() or None
    release_year_raw = master_ref.get("release_year")
    try:
        release_year = int(release_year_raw) if release_year_raw is not None else None
    except (TypeError, ValueError):
        release_year = None

    promoted_master_id = db.promote_album_master_source(
        album_master_id=master_id,
        source_code="DISCOGS",
        source_master_id=discogs_master_id,
        title=title,
        artist_or_brand=artist_or_brand,
        domain_code=_infer_album_master_domain_code(
            source_code="DISCOGS",
            title=title,
            artist_or_brand=artist_or_brand,
            raw=master_ref,
            linked_album_master_id=master_id,
        ),
        release_year=release_year,
        raw=master_ref,
    )
    if promoted_master_id <= 0:
        return master_id, []
    if promoted_master_id == master_id:
        return promoted_master_id, [f"마스터 소스 반영: album_master_id={promoted_master_id} / DISCOGS#{discogs_master_id}"]
    return promoted_master_id, [f"마스터 소스 반영: album_master_id={master_id} -> {promoted_master_id} / DISCOGS#{discogs_master_id}"]


def _promote_owned_item_linked_master_from_discogs_source(owned_item_id: int) -> tuple[int, list[str]]:
    oid = int(owned_item_id or 0)
    if oid <= 0:
        return 0, []

    row = db.get_owned_item(oid)
    if row is None:
        return 0, []

    source_code = str(row.get("source_code") or "").strip().upper()
    source_external_id = str(row.get("source_external_id") or "").strip()
    if source_code != "DISCOGS" or not source_external_id:
        return int(row.get("linked_album_master_id") or 0), []

    linked_master_id = int(row.get("linked_album_master_id") or 0)
    if linked_master_id <= 0:
        bound = db.get_album_master_binding_for_owned_item(oid)
        linked_master_id = int(bound.get("album_master_id") or 0) if bound else 0
    if linked_master_id <= 0:
        return 0, []

    promoted_master_id, notices = _promote_album_master_to_discogs(
        album_master_id=linked_master_id,
        source_external_id=source_external_id,
    )
    if promoted_master_id > 0:
        db.bind_album_master_members(
            album_master_id=promoted_master_id,
            owned_item_ids=[oid],
            replace_existing=False,
        )
        db.set_owned_item_linked_album_master(owned_item_id=oid, album_master_id=promoted_master_id)
    return promoted_master_id, notices


def _ensure_owned_item_master_link(owned_item_id: int) -> tuple[int, list[str]]:
    oid = int(owned_item_id or 0)
    if oid <= 0:
        raise HTTPException(status_code=400, detail="owned_item_id must be positive")

    row = db.get_owned_item(oid)
    if row is None:
        raise HTTPException(status_code=404, detail="owned_item not found")

    notices: list[str] = []
    linked_master_id = int(row.get("linked_album_master_id") or 0)
    if linked_master_id > 0:
        if not db.album_master_exists(linked_master_id):
            raise HTTPException(status_code=400, detail=f"linked_album_master_id not found: {linked_master_id}")
        db.bind_album_master_members(
            album_master_id=linked_master_id,
            owned_item_ids=[oid],
            replace_existing=False,
        )
        db.set_owned_item_linked_album_master(owned_item_id=oid, album_master_id=linked_master_id)
        return linked_master_id, notices

    bound = db.get_album_master_binding_for_owned_item(oid)
    if bound is not None:
        linked_master_id = int(bound.get("album_master_id") or 0)
        if linked_master_id > 0:
            db.set_owned_item_linked_album_master(owned_item_id=oid, album_master_id=linked_master_id)
            return linked_master_id, notices

    # `create_owned_item_auto_master` moved to app.api.owned_items in the
    # router split; importing it lazily inside the helper avoids a hard
    # cycle (this module imports the router file at the very bottom).
    from .api.owned_items import create_owned_item_auto_master

    auto = create_owned_item_auto_master(oid)
    linked_master_id = int(auto.album_master_id or 0)
    if linked_master_id <= 0:
        raise HTTPException(status_code=500, detail="failed to ensure linked album master")
    db.set_owned_item_linked_album_master(owned_item_id=oid, album_master_id=linked_master_id)
    notices.append(
        f"자동 마스터 연결: album_master_id={auto.album_master_id} ({auto.source_code}#{auto.source_master_id})"
    )
    notices.extend([str(v).strip() for v in auto.notices if str(v).strip()])
    return linked_master_id, notices


def _build_manual_master_seed_from_owned_row(owned_item_id: int, row: dict[str, Any]) -> tuple[str, str | None, int | None, dict[str, Any]]:
    category = str(row.get("category") or "CD").strip().upper()
    title = str(row.get("item_name_override") or "").strip()
    artist = str(row.get("artist_or_brand") or row.get("linked_artist_name") or "").strip() or None
    release_year: int | None
    try:
        release_year = int(row.get("release_year")) if row.get("release_year") is not None else None
    except (TypeError, ValueError):
        release_year = None

    if not title:
        label_name = str(row.get("label_name") or "").strip()
        catalog_no = _discogs_catalog_no(row.get("catalog_no")) or ""
        if artist and label_name:
            title = f"{artist} - {label_name}"
        elif artist and catalog_no:
            title = f"{artist} - {catalog_no}"
        elif artist:
            title = artist
        elif label_name and catalog_no:
            title = f"{label_name} / {catalog_no}"
        else:
            title = f"{category} #{owned_item_id}"

    raw = {
        "mode": "QUICK_AUTO",
        "owned_item_id": owned_item_id,
        "category": category,
        "item_name_override": row.get("item_name_override"),
        "artist_or_brand": row.get("artist_or_brand"),
        "release_year": row.get("release_year"),
        "label_name": row.get("label_name"),
        "catalog_no": row.get("catalog_no"),
        "barcode": row.get("barcode"),
        "source_code": row.get("source_code"),
        "source_external_id": row.get("source_external_id"),
    }
    return title, artist, release_year, raw


def _merge_replace_text(incoming: Any, current: Any) -> str | None:
    return _clean_text(incoming) or _clean_text(current)


def _merge_replace_int(incoming: Any, current: Any) -> int | None:
    for value in (incoming, current):
        if value is None:
            continue
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        return parsed
    return None


def _merge_replace_string_list(incoming: Any, current: Any) -> list[str]:
    incoming_list = _clean_string_list(incoming)
    if incoming_list:
        return incoming_list
    return _clean_string_list(current)


def _merge_replace_dict_list(incoming: Any, current: Any) -> list[dict[str, Any]]:
    incoming_list = _clean_dict_list(incoming)
    if incoming_list:
        return incoming_list
    return _clean_dict_list(current)


def _merge_replace_runout(incoming: Any, current: Any) -> list[str]:
    incoming_list = _clean_runout_list(incoming)
    if incoming_list:
        return incoming_list
    return _clean_runout_list(current)


# Late-bound router registrations. The slices below reach into helpers
# defined throughout this module, so we import their routers AFTER
# everything has been declared rather than at the top. The auth and
# admin routers higher up don't need the deferral, but registering them
# here too would also work — we keep the early ones to minimise the diff.
from .api.album_masters import router as album_masters_router  # noqa: E402
from .api.owned_items import router as owned_items_router  # noqa: E402
from .api.purchase_imports import router as purchase_imports_router  # noqa: E402

app.include_router(album_masters_router)
app.include_router(owned_items_router)
app.include_router(purchase_imports_router)
from app.api.ops_system import router as ops_system_router
app.include_router(ops_system_router)
from app.api.operator_home import router as operator_home_router
app.include_router(operator_home_router)
from app.api.ingest import router as ingest_router
app.include_router(ingest_router)
from app.api.metadata_routes import router as metadata_routes_router
app.include_router(metadata_routes_router)
from app.api.storage import router as storage_router
app.include_router(storage_router)
from app.api.misc_catalog import router as misc_catalog_router
app.include_router(misc_catalog_router)
from app.api.discogs_integration import router as discogs_router
app.include_router(discogs_router)
from app.api.local_player import router as local_player_router
app.include_router(local_player_router)
from app.api.static_pages import router as static_pages_router
app.include_router(static_pages_router)
from app.api.audit_log import router as audit_log_router
app.include_router(audit_log_router)
from app.api.cafe_admin import router as cafe_admin_router
app.include_router(cafe_admin_router)
from app.api.permissions import router as permissions_router
app.include_router(permissions_router)
from app.api.activity_log import router as activity_log_router
app.include_router(activity_log_router)
from app.api.cafe import router as cafe_router, _now_playing_worker as _cafe_now_playing_worker
app.include_router(cafe_router)

# ── Backward-compatible re-exports for tests ──
from app.api.discogs_integration import get_discogs_release_collector_info, get_discogs_release_cover_preview
