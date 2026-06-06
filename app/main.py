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
    get_discogs_snapshot_from_master_id,
    get_album_master_variants,
    get_album_master_variants_page,
    resolve_discogs_preferred_korean_artist_name,
    resolve_release_master_reference,
    search_album_master_candidates,
    search_discogs_artist_name_variations,
    search_music_metadata,
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
MUSIC_CATEGORIES = {"LP", "CD", "CASSETTE", "8TRACK", "DIGITAL", "REEL_TO_REEL"}
DOMAIN_CODES = {"KOREA", "JAPAN", "GREATER_CHINA", "WESTERN", "OTHER_ASIA", "WORLD_OTHER", "UNKNOWN"}
LEGACY_DOMAIN_CODE_MAP = {"KOREAN": "KOREA", "JPOP": "JAPAN", "OTHER": "WORLD_OTHER"}
RELEASE_TYPES = {"ALBUM", "EP", "SINGLE"}
SIZE_GROUP_CODES = {"STD", "BOOK", "LP", "LP10", "LP7", "OVERSIZE", "CASSETTE", "8TRACK", "REEL_TO_REEL", "GOODS"}
LABEL_PREFIX_BY_CATEGORY = {
    "LP": "LP",
    "CD": "CD",
    "CASSETTE": "CT",
    "8TRACK": "8T",
    "DIGITAL": "DG",
    "REEL_TO_REEL": "RT",
    "T_SHIRT": "TS",
    "POSTER": "PO",
    "LIGHT_STICK": "LS",
    "HAT": "HT",
    "BAG": "BG",
    "CUP": "CP",
    "OTHER": "OT",
}
STATIC_DIR = Path(__file__).resolve().parent / "static"
IMAGE_UPLOAD_DIR = STATIC_DIR / "uploads"
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
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "image/tiff": ".tif",
    "image/heic": ".heic",
    "image/heif": ".heif",
}
MAX_IMAGE_UPLOAD_BYTES = 20 * 1024 * 1024
METADATA_SYNC_LOCK = threading.Lock()
METADATA_SYNC_STOP_EVENT = threading.Event()
METADATA_SYNC_THREAD: threading.Thread | None = None
METADATA_SYNC_LAST_RESULT: MetadataSyncRunResponse | None = None
METADATA_SYNC_LAST_ERROR: str | None = None
METADATA_SYNC_IN_PROGRESS_ITEMS: list[Any] = []  # live feed; reset at sync start
ALADIN_DISCOGS_BACKFILL_LOCK = threading.Lock()
ALADIN_DISCOGS_BACKFILL_THREAD: threading.Thread | None = None
ALADIN_DISCOGS_BACKFILL_LAST_RESULT: dict[str, Any] | None = None
ALADIN_DISCOGS_BACKFILL_LAST_ERROR: str | None = None
AUTO_BACKUP_LOCK = threading.Lock()
AUTO_BACKUP_STOP_EVENT = threading.Event()
AUTO_BACKUP_THREAD: threading.Thread | None = None
LAUNCHD_LOG_DIR = Path.home() / "Library" / "Logs" / "__PROJECT_SLUG__-library"
LAUNCHD_ERR_LOG_PATH = LAUNCHD_LOG_DIR / "library.err.log"


def _resolve_project_root() -> Path:
    """Resolve the workspace project root.

    Resolution order:
      1. Explicit `LIBRARY_PROJECT_ROOT` env var (preferred for QA/Prod).
      2. The directory two levels above this file (works for in-repo runs).

    The repo used to embed `/Volumes/Data/Works/07.__PROJECT_SLUG__` as a literal in nine
    places. That made the same code break on a teammate's laptop, on a
    runtime that mounted the repo elsewhere, or inside CI. Anchoring on a
    single env var keeps QA/Prod overridable while keeping the local dev
    flow zero-config.
    """
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
DISCOGS_COVER_PREVIEW_CACHE_DIR = PROJECT_ROOT / "data" / "discogs_cover_preview_cache"
HTML_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}
# QA 환경: APP_ENV=qa 로 설정 → 엄격한 no-store + Clear-Site-Data
# 상용 환경: ?v=hash URL 버전닝으로 캐시 버스팅 → max-age 허용, Clear-Site-Data 제거
def _is_qa_env() -> bool:
    return os.getenv("APP_ENV", "production").lower() in {"qa", "dev", "staging"}

HTML_PROD_CACHE_HEADERS = {
    "Cache-Control": "no-cache",  # ETag 기반 조건부 요청 허용 (304 응답)
}
PURCHASE_ITEM_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

settings = get_settings()
_OFFICE_CLIMATE_CACHE: dict[str, Any] | None = None
_SEOUL_WEATHER_CACHE: dict[str, Any] | None = None

_ROON_CONNECTED: bool = True
_ROON_CORE_NAME: str = "Cafe Roon Core"
_ROON_ACTIVE_ZONE: str = "Main Hall (McIntosh + JBL)"
_ROON_VOLUME: int = 65
_ROON_NOW_PLAYING_REQUEST_ID: int | None = None

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


def _serialize_env_value(value: str) -> str:
    if not value:
        return '""'
    if re.search(r'[\s#"\'=]', value):
        return json.dumps(value)
    return value


def _write_env_updates(path: Path, updates: dict[str, str]) -> None:
    existing_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    pending = dict(updates)
    rendered_lines: list[str] = []
    for raw_line in existing_lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in raw_line:
            rendered_lines.append(raw_line)
            continue
        key, _value = raw_line.split("=", 1)
        env_key = key.strip()
        if env_key in pending:
            rendered_lines.append(f"{env_key}={_serialize_env_value(pending.pop(env_key))}")
        else:
            rendered_lines.append(raw_line)
    for env_key, env_value in pending.items():
        rendered_lines.append(f"{env_key}={_serialize_env_value(env_value)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rendered_lines).rstrip() + "\n", encoding="utf-8")


def _metadata_provider_settings_payload() -> dict[str, Any]:
    settings = get_settings()
    return {
        "discogs_token_configured": bool(settings.discogs_token),
        "aladin_ttb_key_configured": bool(settings.aladin_ttb_key),
        "deepl_auth_key_configured": bool(settings.deepl_auth_key),
        "discogs_user_agent": str(settings.discogs_user_agent or ""),
        "musicbrainz_user_agent": str(settings.musicbrainz_user_agent or ""),
        "aladin_base_url": str(settings.aladin_base_url or ""),
        "maniadb_base_url": str(settings.maniadb_base_url or ""),
        "deepl_base_url": str(settings.deepl_base_url or ""),
    }


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
    if path in allowed_paths:
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
        return RedirectResponse(url="/login", status_code=303)
    return JSONResponse(status_code=401, content={"detail": "authentication required"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tail_text_lines(path: Path, limit: int = 2) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    lines = [str(line).strip() for line in text.splitlines() if str(line).strip()]
    if limit <= 0:
        return lines
    return lines[-limit:]


def _read_qa_summary() -> dict[str, Any]:
    if not PROJECT_QA_MASTER_SHEET_PATH.exists():
        return {
            "total_count": 0,
            "pass_count": 0,
            "fail_count": 0,
            "blocked_count": 0,
            "not_started_count": 0,
            "remaining_items": [],
            "qa_master_sheet": str(PROJECT_QA_MASTER_SHEET_PATH),
            "qa_manual_sheet": str(PROJECT_QA_MANUAL_SHEET_PATH),
            "updated_at": None,
        }

    with PROJECT_QA_MASTER_SHEET_PATH.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    pass_count = len([row for row in rows if str(row.get("status") or "").strip() == "Pass"])
    fail_count = len([row for row in rows if str(row.get("status") or "").strip() == "Fail"])
    blocked_count = len([row for row in rows if str(row.get("status") or "").strip() == "Blocked"])
    not_started_rows = [row for row in rows if str(row.get("status") or "").strip() == "Not Started"]
    remaining_items = [
        {
            "suite_id": str(row.get("suite_id") or "").strip(),
            "area": str(row.get("area") or "").strip(),
            "priority": str(row.get("priority") or "").strip(),
            "title": str(row.get("title") or "").strip(),
            "role": str(row.get("role") or "").strip(),
        }
        for row in not_started_rows[:6]
    ]
    updated_at = datetime.fromtimestamp(PROJECT_QA_MASTER_SHEET_PATH.stat().st_mtime, timezone.utc).isoformat()
    return {
        "total_count": len(rows),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "blocked_count": blocked_count,
        "not_started_count": len(not_started_rows),
        "remaining_items": remaining_items,
        "qa_master_sheet": str(PROJECT_QA_MASTER_SHEET_PATH),
        "qa_manual_sheet": str(PROJECT_QA_MANUAL_SHEET_PATH),
        "updated_at": updated_at,
    }


def _cleanup_temp_file(path: str) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        return


def _pick_directory_via_osascript(title: str, initial_path: str | None = None) -> str | None:
    safe_title = str(title or "폴더 선택").replace('"', '\\"')
    script_lines: list[str] = []

    init = Path(initial_path).expanduser() if initial_path else None
    if init and init.exists() and init.is_dir():
        safe_init = str(init).replace('"', '\\"')
        script_lines.extend(
            [
                f'set _defaultLocation to POSIX file "{safe_init}"',
                f'set _pickedFolder to choose folder with prompt "{safe_title}" default location _defaultLocation',
                "POSIX path of _pickedFolder",
            ]
        )
    else:
        script_lines.extend(
            [
                f'set _pickedFolder to choose folder with prompt "{safe_title}"',
                "POSIX path of _pickedFolder",
            ]
        )

    cmd = ["osascript"]
    for line in script_lines:
        cmd.extend(["-e", line])
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)

    if proc.returncode == 0:
        picked = str(proc.stdout or "").strip()
        return picked or None

    err_text = f"{proc.stderr or ''}\n{proc.stdout or ''}".lower()
    if "user canceled" in err_text or "-128" in err_text:
        return None
    raise RuntimeError(f"directory picker failed: {(proc.stderr or proc.stdout or 'unknown error').strip()}")


def _pick_directory_via_tk(title: str, initial_path: str | None = None) -> str | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        raise RuntimeError("directory picker backend not available") from exc

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory(
            parent=root,
            title=title or "폴더 선택",
            initialdir=str(Path(initial_path).expanduser()) if initial_path else None,
            mustexist=True,
        )
    finally:
        root.destroy()
    selected = str(selected or "").strip()
    return selected or None


def _pick_directory_interactive(title: str, initial_path: str | None = None) -> str | None:
    system_name = platform.system().lower()
    if system_name == "darwin":
        return _pick_directory_via_osascript(title=title, initial_path=initial_path)
    return _pick_directory_via_tk(title=title, initial_path=initial_path)


def _resolve_image_upload_extension(file_name: str | None, content_type: str | None) -> str | None:
    ext = Path(str(file_name or "")).suffix.lower().strip()
    if ext in ALLOWED_IMAGE_EXTENSIONS:
        return ext
    normalized_content_type = str(content_type or "").strip().lower()
    return ALLOWED_IMAGE_CONTENT_TYPES.get(normalized_content_type)


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
    # ManiaDB는 항상 가요(KOREA). Discogs는 preview에서 가져오되 없으면 None.
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
            results = [candidate for candidate in results if _candidate_matches_title_filter(candidate, title_text)]
        if results:
            collected.extend(results)
            break

    if not collected and title_text:
        for variation_name in variation_names:
            variation_text = _clean_text(variation_name)
            if not variation_text:
                continue
            results = run_query(variation_text)
            matched = [candidate for candidate in results if _candidate_matches_title_filter(candidate, title_text)]
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


def _parse_price_number(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = re.sub(r"[^0-9.,-]", "", text)
    normalized = normalized.replace(",", "")
    if normalized in {"", "-", ".", "-."}:
        return None
    try:
        return float(normalized)
    except ValueError:
        return None


def _parse_positive_int(value: Any, default: int = 1) -> int:
    text = str(value or "").strip()
    if not text:
        return default
    digits = re.sub(r"[^0-9]", "", text)
    if not digits:
        return default
    try:
        parsed = int(digits)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _normalize_purchase_date(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    compact = text.replace(".", "-").replace("/", "-")
    if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", compact):
        y, m, d = compact.split("-")
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    for fmt in ("%B %d, %Y", "%d %B %Y", "%b %d, %Y", "%d %b %Y"):
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return parsed.strftime("%Y-%m-%d")
    return text


def _purchase_message_from_raw_content(raw_content: str):
    raw = str(raw_content or "").strip()
    if not raw:
        return None
    try:
        return EmailParser(policy=email_policy.default).parsestr(raw)
    except Exception:
        return None


def _purchase_message_from_raw_bytes(raw_content: bytes):
    raw = bytes(raw_content or b"").strip()
    if not raw:
        return None
    try:
        return EmailBytesParser(policy=email_policy.default).parsebytes(raw)
    except Exception:
        return None


def _resolve_purchase_import_vendor_code(
    vendor_code: Any = None,
    *,
    raw_content: str | None = None,
    items: list[Any] | None = None,
) -> str:
    explicit = str(vendor_code or "").strip().upper()
    if explicit and explicit != "OTHER":
        return explicit
    for item in items or []:
        payload = getattr(item, "raw_payload", None)
        if not isinstance(payload, dict):
            payload = item.get("raw_payload") if isinstance(item, dict) else None
        candidate = str((payload or {}).get("vendor_code") or "").strip().upper()
        if candidate and candidate != "OTHER":
            return candidate
    text = str(raw_content or "")
    upper = text.upper()
    has_ebay_marker = any(
        marker in upper
        for marker in (
            "EBAY.COM/MYE/MYEBAY/PURCHASE",
            "MY EBAY",
            "M-ITEM-CARD",
            "MODULE_PROVIDER",
        )
    )
    has_amazon_marker = "AMAZON." in upper and any(
        marker in upper
        for marker in (
            "ORDER-CARD",
            "ORDER PLACED",
            "YOUR ORDERS",
        )
    )
    if "__VENDOR_EMAIL__" in upper or "세일뮤직" in text:
        return "SAILMUSIC"
    if has_ebay_marker:
        return "EBAY"
    if has_amazon_marker:
        return "AMAZON"
    if "AMAZON." in upper:
        return "AMAZON"
    if "EBAY.COM" in upper:
        return "EBAY"
    return "OTHER"


def _extract_purchase_date_from_raw_content(raw_content: str, purchase_date: Any = None) -> str | None:
    normalized = _normalize_purchase_date(purchase_date)
    if normalized:
        return normalized
    candidates = [str(raw_content or "").strip()]
    html_content = _purchase_html_from_raw_content(str(raw_content or ""))
    if html_content:
        candidates.append(html_content)
    for candidate in candidates:
        parsed = _extract_purchase_date_from_text(candidate)
        if parsed:
            return parsed
        match = re.search(r"\b(20\d{2})[./-]\s*(\d{1,2})[./-]\s*(\d{1,2})\b", candidate)
        if match:
            return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    msg = _purchase_message_from_raw_content(str(raw_content or ""))
    if msg:
        header_date = str(msg.get("Date") or "").strip()
        if header_date:
            try:
                parsed = parsedate_to_datetime(header_date)
            except Exception:
                parsed = None
            if parsed is not None:
                return parsed.strftime("%Y-%m-%d")
    return None


def _resolve_purchase_import_purchase_date(purchase_date: Any = None, *, raw_content: str | None = None, items: list[Any] | None = None) -> str | None:
    normalized = _normalize_purchase_date(purchase_date)
    if normalized:
        return normalized
    for item in items or []:
        item_purchase_date = getattr(item, "purchase_date", None)
        if item_purchase_date is None and isinstance(item, dict):
            item_purchase_date = item.get("purchase_date")
        normalized_item = _normalize_purchase_date(item_purchase_date)
        if normalized_item:
            return normalized_item
    return _extract_purchase_date_from_raw_content(str(raw_content or ""))


def _split_artist_item_text(value: Any) -> tuple[str | None, str | None]:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" /")
    if not text:
        return None, None
    for separator in (" / ", "／", "/"):
        if separator in text:
            left, right = text.split(separator, 1)
            artist_name = _clean_text(left)
            item_name = _clean_text(right)
            if artist_name and item_name:
                return artist_name, item_name
    return None, text


_PURCHASE_CONDITION_TOKEN_PATTERN = r"(?:M-|M|NM-|NM|EX|VG\+|VG|G\+|G|F|P)"


def _normalize_purchase_condition_token(value: Any) -> str | None:
    token = _purchase_compact_text(value).upper().replace(" ", "")
    if token == "E":
        token = "EX"
    if token in {"M-", "M", "NM-", "NM", "EX", "VG+", "VG", "G+", "G", "F", "P"}:
        return token
    return None


def _extract_purchase_condition_pair(value: Any) -> tuple[str | None, str | None, str]:
    text = _purchase_compact_text(value)
    if not text:
        return None, None, ""
    match = re.search(
        rf"(?:^|\s)(?P<cover>{_PURCHASE_CONDITION_TOKEN_PATTERN})\s*/\s*(?P<disc>{_PURCHASE_CONDITION_TOKEN_PATTERN})\s*$",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None, None, text
    cover = _normalize_purchase_condition_token(match.group("cover"))
    disc = _normalize_purchase_condition_token(match.group("disc"))
    if not cover or not disc:
        return None, None, text
    stripped = text[: match.start()].strip(" -/|,")
    return cover, disc, stripped


def _strip_ebay_listing_search_suffix(value: Any) -> str:
    text = _purchase_compact_text(value)
    if not text:
        return ""
    text = re.sub(
        r"\s+(?:ORIG(?:INAL)?\.?|1ST|FIRST|PRESS(?:ING)?|PROMO|REISSUE|VINYL|RECORDS?|REC\.?|LP|LPS|ALBUM|EP|SINGLE|12\"|10\"|7\"|45RPM|33RPM|RPM|MONO|STEREO|GOLD\s+REC\.?|COLOR\s+VINYL|COLOUR\s+VINYL)\b.*$",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return text.strip(" -/|,")


def _parse_ebay_purchase_title(value: Any) -> tuple[str | None, str | None, str | None, str | None]:
    text = _purchase_compact_text(value)
    if not text:
        return None, None, None, None
    cover_condition, disc_condition, stripped_text = _extract_purchase_condition_pair(text)
    working_text = stripped_text or text
    artist_name: str | None = None
    item_name = working_text
    match = re.match(r"(?P<artist>.+?)\s[-–—]\s(?P<title>.+)$", working_text)
    if match:
        artist_name = _clean_text(match.group("artist"))
        item_name = _clean_text(match.group("title")) or working_text
    else:
        quoted_match = re.match(r'(?P<artist>.+?)\s*["“](?P<title>[^"”]+)["”](?P<suffix>.*)$', working_text)
        if quoted_match:
            artist_name = _clean_text(quoted_match.group("artist"))
            suffix = _clean_text(quoted_match.group("suffix"))
            title_core = _clean_text(quoted_match.group("title"))
            item_name = _clean_text(" ".join(part for part in (title_core, suffix) if part)) or working_text
    item_name = _strip_ebay_listing_search_suffix(item_name) or _clean_text(item_name)
    return artist_name, item_name, cover_condition, disc_condition


def _purchase_ebay_parse_source_text(row: dict[str, Any], raw_payload: dict[str, Any] | None = None) -> str:
    payload = raw_payload if isinstance(raw_payload, dict) else dict(row.get("raw_payload") or {})
    listing_title = _clean_text(payload.get("listing_title"))
    item_name = _clean_text(row.get("item_name"))
    raw_line = _clean_text(row.get("raw_line"))
    return listing_title or item_name or raw_line


def _purchase_queue_display_item_name(row: dict[str, Any], raw_payload: dict[str, Any] | None = None) -> str:
    payload = raw_payload if isinstance(raw_payload, dict) else dict(row.get("raw_payload") or {})
    vendor_code = str(row.get("vendor_code") or payload.get("vendor_code") or "").strip().upper()
    listing_title = _clean_text(payload.get("listing_title"))
    item_name = _clean_text(row.get("item_name"))
    if vendor_code == "EBAY":
        return listing_title or item_name
    return item_name


def _normalize_purchase_media_format(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip().upper()
    if not text:
        return None
    if (
        "VINYL" in text
        or re.search(r"(?<![A-Z0-9])(?:LP|LPS|LP'S)(?![A-Z0-9])", text)
        or re.search(r"(?<![A-Z0-9])(?:12|10|7)\s*\"", text)
    ):
        return "LP"
    if "COMPACT DISC" in text or re.search(r"(?<![A-Z0-9])CDS?(?![A-Z0-9])", text):
        return "CD"
    if "CASSETTE" in text or re.search(r"(?<![A-Z0-9])(?:MC|TAPE|TAPES)(?![A-Z0-9])", text):
        return "CASSETTE"
    if "8-TRACK" in text or "8 TRACK" in text or "8TRACK" in text:
        return "8TRACK"
    if "DIGITAL" in text or "DOWNLOAD" in text or "FILE" in text:
        return "DIGITAL"
    if "REEL" in text:
        return "REEL_TO_REEL"
    return None


def _purchase_import_media_format_or_default(vendor_code: Any, value: Any) -> str | None:
    normalized = _normalize_purchase_media_format(value)
    if normalized:
        return normalized
    cleaned = _clean_text(value)
    if cleaned:
        return cleaned
    vendor = str(vendor_code or "").strip().upper()
    if vendor in {"ALADIN", "YES24"}:
        return "CD"
    return None


class _PurchaseMailTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None
        self._ignore_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = str(tag or "").lower()
        if name in {"script", "style"}:
            self._ignore_depth += 1
            return
        if self._ignore_depth:
            return
        if name == "tr":
            self._current_row = []
            return
        if name in {"td", "th"}:
            self._current_cell = []
            return
        if name == "br" and self._current_cell is not None:
            self._current_cell.append("\n")

    def handle_endtag(self, tag: str) -> None:
        name = str(tag or "").lower()
        if name in {"script", "style"} and self._ignore_depth:
            self._ignore_depth -= 1
            return
        if self._ignore_depth:
            return
        if name in {"td", "th"} and self._current_cell is not None and self._current_row is not None:
            cell_text = re.sub(r"\s+", " ", "".join(self._current_cell)).strip()
            self._current_row.append(cell_text)
            self._current_cell = None
            return
        if name == "tr" and self._current_row is not None:
            if any(_clean_text(cell) for cell in self._current_row):
                self.rows.append(self._current_row)
            self._current_row = None

    def handle_data(self, data: str) -> None:
        if self._ignore_depth or self._current_cell is None:
            return
        self._current_cell.append(str(data or ""))


def _purchase_rows_from_html(raw_content: str) -> list[list[str]]:
    parser = _PurchaseMailTableParser()
    parser.feed(raw_content)
    parser.close()
    return parser.rows


def _purchase_rows_from_text(raw_content: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in str(raw_content or "").splitlines():
        text = re.sub(r"\s+", " ", line).strip()
        if not text:
            continue
        cells = [part.strip() for part in re.split(r"\t+| {2,}", text) if part.strip()]
        if cells:
            rows.append(cells)
    return rows


def _extract_html_from_mhtml(raw_content: str) -> str | None:
    raw = str(raw_content or "").strip()
    if not raw:
        return None
    msg = _purchase_message_from_raw_content(raw)
    if msg is None:
        return None
    html_parts: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() != "text/html":
                continue
            try:
                content = part.get_content()
            except Exception:
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                content = payload.decode(charset, errors="replace") if isinstance(payload, bytes) else ""
            text = str(content or "").strip()
            if text:
                html_parts.append(text)
    elif msg.get_content_type() == "text/html":
        try:
            content = msg.get_content()
        except Exception:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            content = payload.decode(charset, errors="replace") if isinstance(payload, bytes) else ""
        text = str(content or "").strip()
        if text:
            html_parts.append(text)
    return html_parts[0] if html_parts else None


def _extract_html_from_mhtml_bytes(raw_content: bytes) -> str | None:
    raw = bytes(raw_content or b"").strip()
    if not raw:
        return None
    msg = _purchase_message_from_raw_bytes(raw)
    if msg is None:
        return None
    html_parts: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() != "text/html":
                continue
            try:
                content = part.get_content()
            except Exception:
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                content = payload.decode(charset, errors="replace") if isinstance(payload, bytes) else ""
            text = str(content or "").strip()
            if text:
                html_parts.append(text)
    elif msg.get_content_type() == "text/html":
        try:
            content = msg.get_content()
        except Exception:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            content = payload.decode(charset, errors="replace") if isinstance(payload, bytes) else ""
        text = str(content or "").strip()
        if text:
            html_parts.append(text)
    return html_parts[0] if html_parts else None


def _purchase_html_from_raw_content(raw_content: str) -> str | None:
    extracted = _extract_html_from_mhtml(raw_content)
    if extracted:
        return extracted
    text = str(raw_content or "").strip()
    if "<" in text and ">" in text:
        return text
    return None


def _decode_purchase_import_upload_bytes(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp949", "euc-kr", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise HTTPException(status_code=400, detail="구매 내역 파일 디코딩 실패: UTF-8/CP949/EUC-KR/LATIN-1 확인 필요")


def _purchase_html_from_upload_bytes(raw_content: bytes, *, fallback_text: str | None = None) -> str | None:
    extracted = _extract_html_from_mhtml_bytes(raw_content)
    if extracted:
        return extracted
    text = str(fallback_text or "").strip() or _decode_purchase_import_upload_bytes(raw_content)
    if "<" in text and ">" in text:
        return text
    return None


def _resolve_purchase_import_raw_input(
    payload: PurchaseImportPreviewRequest | PurchaseImportWebhookRequest,
) -> tuple[str, str | None]:
    raw_content = str(getattr(payload, "raw_content", "") or "").strip()
    raw_content_base64 = str(getattr(payload, "raw_content_base64", "") or "").strip()
    if not raw_content_base64:
        return raw_content, _purchase_html_from_raw_content(raw_content)
    try:
        raw_bytes = base64.b64decode(raw_content_base64, validate=True)
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"구매 내역 파일 디코딩 실패: {err}") from err
    decoded_text = _decode_purchase_import_upload_bytes(raw_bytes)
    html_content = _purchase_html_from_upload_bytes(raw_bytes, fallback_text=decoded_text)
    return (html_content or decoded_text), html_content


def _purchase_compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _purchase_dense_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def _purchase_normalize_item_url(value: Any, *, base_url: str | None = None) -> str | None:
    url = _clean_text(value)
    if not url:
        return None
    if base_url and url.startswith("/"):
        url = f"{base_url.rstrip('/')}{url}"
    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        normalized = parsed._replace(params="", query="", fragment="")
        return normalized.geturl()
    return url.split("#", 1)[0].split("?", 1)[0].strip() or None


def _purchase_currency_code(value: Any, default: str = "KRW") -> str:
    text = str(value or "").strip()
    upper = text.upper()
    if upper in {"KRW", "USD", "GBP", "EUR", "JPY"}:
        return upper
    if "US $" in upper or ("$" in text and "CA$" not in upper and "A$" not in upper):
        return "USD"
    if "GBP" in upper or "£" in text:
        return "GBP"
    if "EUR" in upper or "€" in text:
        return "EUR"
    if "JPY" in upper or "¥" in text or "￥" in text:
        return "JPY"
    return default


def _purchase_host_from_url(value: Any) -> str:
    url = _clean_text(value)
    if not url:
        return ""
    try:
        return str(urlparse(url).hostname or "").strip().lower()
    except Exception:
        return ""


def _purchase_marketplace_currency(vendor_code: str, marketplace: Any) -> str:
    vendor = str(vendor_code or "").strip().upper()
    market = str(marketplace or "").strip().upper()
    if vendor == "AMAZON":
        if market == "UK":
            return "GBP"
        if market == "JP":
            return "JPY"
        return "USD"
    if vendor == "EBAY":
        return "USD"
    return "KRW"


def _purchase_amazon_marketplace_from_raw_content(raw_content: str) -> str | None:
    text = str(raw_content or "")
    if "amazon.co.jp" in text:
        return "JP"
    if "amazon.co.uk" in text:
        return "UK"
    if "amazon.com" in text:
        return "US"
    return None


def _extract_purchase_price_from_text(value: Any, default_currency: str) -> tuple[float | None, str]:
    text = _purchase_compact_text(value)
    if not text:
        return None, default_currency
    text_variants = [text]
    dense_text = _purchase_dense_text(text)
    if dense_text and dense_text != text:
        text_variants.append(dense_text)
    patterns = (
        r"(US\s*\$\s*[0-9,\s]+(?:\.[0-9]{2})?)",
        r"(\$\s*[0-9,\s]+(?:\.[0-9]{2})?)",
        r"(£\s*[0-9,\s]+(?:\.[0-9]{2})?)",
        r"(¥\s*[0-9,\s]+(?:\.[0-9]{2})?)",
        r"(￥\s*[0-9,\s]+(?:\.[0-9]{2})?)",
        r"([0-9,\s]+(?:\.[0-9]{2})?\s*(?:USD|GBP|EUR|JPY))",
    )
    for candidate_text in text_variants:
        for pattern in patterns:
            match = re.search(pattern, candidate_text, re.IGNORECASE)
            if not match:
                continue
            price_text = str(match.group(1) or "").strip()
            amount = _parse_price_number(price_text)
            if amount is None:
                continue
            return amount, _purchase_currency_code(price_text, default_currency)
    return None, default_currency


def _extract_purchase_date_from_text(value: Any) -> str | None:
    text = _purchase_compact_text(value)
    patterns = (
        r"Order placed\s+([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})",
        r"Order placed\s+(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})",
        r"Placed on\s+([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})",
        r"Placed on\s+(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        normalized = _normalize_purchase_date(match.group(1))
        if normalized:
            return normalized
    return None


def _extract_purchase_total_from_text(value: Any, default_currency: str = "KRW") -> tuple[float | None, str]:
    text = _purchase_compact_text(value)
    text_variants = [text]
    dense_text = _purchase_dense_text(text)
    if dense_text and dense_text != text:
        text_variants.append(dense_text)
    patterns = (
        r"Total\s+((?:US\s*\$|\$|GBP\s*|EUR\s*|JPY\s*|¥|￥)[0-9,.\s]+)",
        r"Total\s+([0-9,.\s]+\s*(?:USD|GBP|EUR|JPY))",
        r"Total((?:US\$|\$|GBP|EUR|JPY|¥|￥)[0-9,.\s]+)",
        r"Total[^0-9]{0,6}([0-9][0-9,.\s]{0,20})",
    )
    for candidate_text in text_variants:
        for pattern in patterns:
            match = re.search(pattern, candidate_text, re.IGNORECASE)
            if not match:
                continue
            price_text = str(match.group(1) or "").strip()
            amount = _parse_price_number(price_text)
            if amount is None:
                continue
            return amount, _purchase_currency_code(price_text, default_currency)
    return None, default_currency


def _build_purchase_preview_item_direct(
    *,
    row_no: int,
    artist_name: str | None,
    item_name: str,
    media_format: str | None,
    quantity: int = 1,
    unit_price: float | None = None,
    line_total: float | None = None,
    currency_code: str = "KRW",
    purchase_date: str | None = None,
    raw_line: str | None = None,
    raw_payload: dict[str, Any] | None = None,
) -> PurchaseImportPreviewItem | None:
    item_title = _clean_text(item_name)
    if not item_title:
        return None
    normalized_media = _normalize_purchase_media_format(media_format)
    if normalized_media is None:
        return None
    return PurchaseImportPreviewItem(
        row_no=row_no,
        artist_name=_clean_text(artist_name),
        item_name=item_title,
        media_format=normalized_media,
        quantity=max(1, int(quantity or 1)),
        unit_price=unit_price,
        line_total=line_total,
        currency_code=_purchase_currency_code(currency_code),
        purchase_date=_normalize_purchase_date(purchase_date),
        raw_line=_clean_text(raw_line),
        raw_payload=dict(raw_payload or {}),
    )


def _purchase_amazon_asin_from_url(value: Any) -> str | None:
    url = _clean_text(value)
    if not url:
        return None
    patterns = (
        r"/dp/([A-Z0-9]{10})(?:[/?]|$)",
        r"/gp/product/([A-Z0-9]{10})(?:[/?]|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return str(match.group(1) or "").strip().upper() or None
    return None


def _purchase_amazon_marketplace_from_url(value: Any) -> str | None:
    url = _clean_text(value)
    if not url:
        return None
    try:
        hostname = str(urlparse(url).hostname or "").strip().lower()
    except Exception:
        return None
    if not hostname:
        return None
    if hostname.endswith("amazon.co.jp"):
        return "JP"
    if hostname.endswith("amazon.co.uk"):
        return "UK"
    if hostname.endswith("amazon.com"):
        return "US"
    if hostname.endswith("amazon.de"):
        return "DE"
    if hostname.endswith("amazon.fr"):
        return "FR"
    return hostname


def _purchase_fetch_item_page_html(item_url: str) -> str | None:
    url = _purchase_normalize_item_url(item_url)
    if not url:
        return None
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True, headers=PURCHASE_ITEM_FETCH_HEADERS) as client:
            response = client.get(url)
            response.raise_for_status()
    except httpx.HTTPError:
        return None
    text = str(response.text or "").strip()
    return text or None


def _purchase_extract_amazon_artist_name(soup: BeautifulSoup) -> str | None:
    byline = _purchase_compact_text(soup.select_one("#bylineInfo").get_text(" ", strip=True) if soup.select_one("#bylineInfo") else "")
    if byline:
        text = re.sub(r"\s+", " ", byline).strip()
        text = re.sub(r"\s*Visit the .*? Store\s*", " ", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\s*Brand:\s*", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\s*Format:.*$", "", text, flags=re.IGNORECASE).strip(" -|/")
        if text:
            return text
    detail_text = _purchase_compact_text(soup.select_one("#detailBullets_feature_div").get_text(" ", strip=True) if soup.select_one("#detailBullets_feature_div") else "")
    if detail_text:
        match = re.search(r"Artist\s*[:\u200f\u200e]*\s*(.+?)(?:Label\s*:|ASIN\s*:|Number of discs|$)", detail_text, re.IGNORECASE)
        if match:
            artist_name = _clean_text(match.group(1))
            if artist_name:
                return artist_name
    return None


def _purchase_normalize_amazon_detail_key(value: str) -> str:
    text = _purchase_compact_text(value).replace("\u200f", " ").replace("\u200e", " ")
    text = re.sub(r"\s+", " ", text).strip().rstrip(":").strip()
    return text.lower()


def _purchase_extract_amazon_detail_map(soup: BeautifulSoup) -> dict[str, str]:
    out: dict[str, str] = {}

    def _put(label: str | None, value: str | None) -> None:
        key = _purchase_normalize_amazon_detail_key(label or "")
        text = _clean_text(value)
        if not key or not text or key in out:
            return
        out[key] = text

    detail_root = soup.select_one("#detailBullets_feature_div") or soup.select_one("#detailBulletsWrapper_feature_div")
    if detail_root:
        for li in detail_root.select("li"):
            label_node = li.select_one(".a-text-bold")
            label_text = _purchase_compact_text(label_node.get_text(" ", strip=True) if label_node else "")
            full_text = _purchase_compact_text(li.get_text(" ", strip=True))
            if label_text and full_text.startswith(label_text):
                _put(label_text, full_text[len(label_text):])
            elif ":" in full_text:
                left, right = full_text.split(":", 1)
                _put(left, right)

    for selector in ("#productDetails_detailBullets_sections1", "#productDetails_techSpec_section_1"):
        table = soup.select_one(selector)
        if not table:
            continue
        for tr in table.select("tr"):
            label_text = _purchase_compact_text(tr.select_one("th").get_text(" ", strip=True) if tr.select_one("th") else "")
            value_text = _purchase_compact_text(tr.select_one("td").get_text(" ", strip=True) if tr.select_one("td") else "")
            _put(label_text, value_text)

    return out


def _purchase_extract_amazon_detail_enrichment(item_url: str) -> dict[str, Any] | None:
    html = _purchase_fetch_item_page_html(item_url)
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    title = _purchase_compact_text(soup.select_one("#productTitle").get_text(" ", strip=True) if soup.select_one("#productTitle") else "")
    artist_name = _purchase_extract_amazon_artist_name(soup)
    image_node = soup.select_one("#landingImage")
    image_url = _clean_text(image_node.get("data-old-hires") if image_node else None) or _clean_text(image_node.get("src") if image_node else None)
    track_text = _purchase_compact_text(soup.select_one("#musicTracks_feature_div").get_text(" ", strip=True) if soup.select_one("#musicTracks_feature_div") else "")
    detail_map = _purchase_extract_amazon_detail_map(soup)

    def _detail_value(*keys: str) -> str | None:
        for key in keys:
            text = _clean_text(detail_map.get(_purchase_normalize_amazon_detail_key(key)))
            if text:
                return text
        return None

    label_name = _detail_value("Label", "Manufacturer")
    released_date = _detail_value("Original Release Date", "Date First Available")
    track_samples: list[str] = []
    if track_text:
        sample_matches = re.findall(r"\d+\s+([^0-9].*?)(?=\s+\d+\s+|$)", track_text)
        for raw in sample_matches[:10]:
            cleaned = _clean_text(raw)
            if cleaned:
                track_samples.append(cleaned)
    return {
        "item_name": title or None,
        "artist_name": artist_name,
        "image_url": image_url,
        "label_name": label_name,
        "released_date": released_date,
        "track_samples": track_samples,
    }


def _purchase_extract_ebay_detail_enrichment(item_url: str) -> dict[str, Any] | None:
    html = _purchase_fetch_item_page_html(item_url)
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    title = _clean_text(soup.select_one("meta[property='og:title']").get("content") if soup.select_one("meta[property='og:title']") else None)
    image_url = _clean_text(soup.select_one("meta[property='og:image']").get("content") if soup.select_one("meta[property='og:image']") else None)
    seller_name = _purchase_compact_text(soup.select_one("[data-testid='ux-seller-section']").get_text(" ", strip=True) if soup.select_one("[data-testid='ux-seller-section']") else "")
    return {
        "item_name": title or None,
        "image_url": image_url,
        "seller_name": seller_name or None,
    }


def _purchase_enrich_row_from_item_page(row: dict[str, Any]) -> dict[str, Any]:
    raw_payload = dict(row.get("raw_payload") or {})
    item_url = _purchase_normalize_item_url(row.get("item_url") or raw_payload.get("item_url"))
    if not item_url:
        raise HTTPException(status_code=400, detail="구매 항목에 상품 상세 URL이 없습니다.")
    host = _purchase_host_from_url(item_url)
    enrichment: dict[str, Any] | None = None
    if "amazon." in host:
        enrichment = _purchase_extract_amazon_detail_enrichment(item_url)
    elif "ebay." in host:
        enrichment = _purchase_extract_ebay_detail_enrichment(item_url)
    if enrichment is None:
        raise HTTPException(status_code=400, detail="현재는 Amazon/eBay 상품 상세 페이지만 보강할 수 있습니다.")

    raw_payload["item_url"] = item_url
    if enrichment.get("image_url"):
        raw_payload["image_url"] = enrichment["image_url"]
    if "amazon." in host:
        raw_payload["detail_page_title"] = enrichment.get("item_name")
        raw_payload["detail_page_artist_name"] = enrichment.get("artist_name")
        raw_payload["detail_page_label_name"] = enrichment.get("label_name")
        raw_payload["detail_page_released_date"] = enrichment.get("released_date")
        raw_payload["detail_page_track_samples"] = list(enrichment.get("track_samples") or [])
    updated = db.update_purchase_import_row(
        int(row["id"]),
        artist_name=_clean_text(enrichment.get("artist_name")) or _clean_text(row.get("artist_name")),
        seller_name=_clean_text(enrichment.get("seller_name")) or _clean_text(row.get("seller_name")),
        item_url=item_url,
        image_url=_clean_text(enrichment.get("image_url")) or _clean_text(row.get("image_url")),
        raw_payload=raw_payload,
    )
    if updated is None:
        raise HTTPException(status_code=500, detail="purchase import row update failed")
    return updated


def _purchase_preview_items_from_amazon_html(raw_content: str, *, purchase_date: str | None) -> list[PurchaseImportPreviewItem]:
    detail_items = _purchase_preview_items_from_amazon_order_details_html(
        raw_content,
        purchase_date=purchase_date,
    )
    if detail_items:
        return detail_items
    soup = BeautifulSoup(raw_content, "html.parser")
    cards = soup.select(".order-card")
    preview_items: list[PurchaseImportPreviewItem] = []
    next_row_no = 1
    page_marketplace = _purchase_amazon_marketplace_from_raw_content(raw_content)
    for card in cards:
        card_text = _purchase_compact_text(card.get_text(" ", strip=True))
        order_date = _extract_purchase_date_from_text(card_text) or _normalize_purchase_date(purchase_date)
        order_default_currency = _purchase_marketplace_currency("AMAZON", page_marketplace)
        order_total, currency_code = _extract_purchase_total_from_text(card_text, order_default_currency)
        image_candidates = []
        for img in card.select("img[src]"):
            image_candidates.append(
                {
                    "title": _purchase_compact_text(img.get("alt")),
                    "image_url": _clean_text(img.get("src")),
                }
            )
        item_rows: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, str]] = set()
        for link in card.select("a[href]"):
            href = _clean_text(link.get("href"))
            if not href or ("/dp/" not in href and "/gp/product/" not in href):
                continue
            title = _purchase_compact_text(link.get_text(" ", strip=True))
            if not title:
                continue
            key = (title.lower(), href)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            image_url = None
            for image in image_candidates:
                image_title = str(image.get("title") or "")
                if image_title and (image_title in title or title in image_title):
                    image_url = image.get("image_url")
                    break
            item_marketplace = _purchase_amazon_marketplace_from_url(href) or page_marketplace
            item_default_currency = _purchase_marketplace_currency("AMAZON", item_marketplace)
            item_price = None
            item_currency = item_default_currency
            probe = link
            probe_depth = 0
            while probe is not None and probe is not card and probe_depth < 6:
                probe_text = _purchase_compact_text(probe.get_text(" ", strip=True))
                if probe_text:
                    parsed_price, parsed_currency = _extract_purchase_price_from_text(probe_text, item_default_currency)
                    if parsed_price is not None and not (order_total is not None and len(item_rows) > 1 and abs(parsed_price - order_total) < 0.0001):
                        item_price = parsed_price
                        item_currency = parsed_currency
                        break
                probe = getattr(probe, "parent", None)
                probe_depth += 1
            item_rows.append(
                {
                    "title": title,
                    "item_url": href,
                    "image_url": image_url,
                    "marketplace": item_marketplace,
                    "unit_price": item_price,
                    "currency_code": item_currency,
                }
            )
        for item_row in item_rows:
            item_url = item_row.get("item_url")
            item_marketplace = item_row.get("marketplace") or page_marketplace
            item_default_currency = _purchase_marketplace_currency("AMAZON", item_marketplace)
            item_price = item_row.get("unit_price")
            item_currency = str(item_row.get("currency_code") or item_default_currency).strip().upper() or item_default_currency
            item = _build_purchase_preview_item_direct(
                row_no=next_row_no,
                artist_name=None,
                item_name=item_row["title"],
                media_format=item_row["title"],
                quantity=1,
                unit_price=item_price if item_price is not None else (order_total if len(item_rows) == 1 else None),
                line_total=item_price if item_price is not None else (order_total if len(item_rows) == 1 else None),
                currency_code=item_currency if item_price is not None else currency_code,
                purchase_date=order_date,
                raw_line=card_text,
                raw_payload={
                    "vendor_code": "AMAZON",
                    "item_url": item_url,
                    "image_url": item_row.get("image_url"),
                    "asin": _purchase_amazon_asin_from_url(item_url),
                    "marketplace": item_marketplace,
                },
            )
            if item is None:
                continue
            preview_items.append(item)
            next_row_no += 1
    return preview_items


def _purchase_preview_items_from_amazon_order_details_html(raw_content: str, *, purchase_date: str | None) -> list[PurchaseImportPreviewItem]:
    soup = BeautifulSoup(raw_content, "html.parser")
    root = soup.select_one("#orderDetails") or soup.select_one("[id*='orderDetails']")
    if root is None:
        return []
    page_marketplace = _purchase_amazon_marketplace_from_raw_content(raw_content)
    order_text = _purchase_compact_text(root.get_text(" ", strip=True))
    order_date = _extract_purchase_date_from_text(order_text) or _normalize_purchase_date(purchase_date)
    order_default_currency = _purchase_marketplace_currency("AMAZON", page_marketplace)
    summary_node = root.select_one("#od-subtotals")
    order_total, currency_code = _extract_purchase_total_from_text(
        _purchase_compact_text(summary_node.get_text(" ", strip=True) if summary_node else order_text),
        order_default_currency,
    )
    blocks: list[Any] = []
    for block in root.select("div.a-fixed-left-grid"):
        title_links = [
            link for link in block.select("a[href]")
            if (
                "/dp/" in str(link.get("href") or "")
                or "/gp/product/" in str(link.get("href") or "")
            )
            and "ppx_hzod_" in str(link.get("href") or "")
        ]
        if title_links:
            blocks.append(block)
    preview_items: list[PurchaseImportPreviewItem] = []
    seen_keys: set[tuple[str, str]] = set()
    next_row_no = 1
    for block in blocks:
        block_text = _purchase_compact_text(block.get_text(" ", strip=True))
        if not block_text:
            continue
        title_link = None
        for link in block.select("a[href]"):
            href = _clean_text(link.get("href"))
            title = _purchase_compact_text(link.get_text(" ", strip=True))
            if not href or ("/dp/" not in href and "/gp/product/" not in href):
                continue
            if not title:
                continue
            title_link = link
            break
        if title_link is None:
            continue
        item_title = _purchase_compact_text(title_link.get_text(" ", strip=True))
        item_url = _purchase_normalize_item_url(title_link.get("href"))
        dedupe_key = (item_title.lower(), item_url or "")
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        item_marketplace = _purchase_amazon_marketplace_from_url(item_url) or page_marketplace
        item_default_currency = _purchase_marketplace_currency("AMAZON", item_marketplace)
        item_price, item_currency = _extract_purchase_price_from_text(block_text, item_default_currency)
        media_hint = _normalize_purchase_media_format(block_text) or _normalize_purchase_media_format(item_title)
        if media_hint is None:
            parent_row = block.find_parent("div", class_=lambda value: isinstance(value, str) and "a-row" in value and "a-spacing-top-base" in value)
            if parent_row is not None:
                sibling_has_music = False
                for sibling in parent_row.select("div.a-fixed-left-grid"):
                    if sibling is block:
                        continue
                    sibling_text = _purchase_compact_text(sibling.get_text(" ", strip=True))
                    if _normalize_purchase_media_format(sibling_text):
                        sibling_has_music = True
                        break
                if sibling_has_music and item_price is not None:
                    media_hint = "LP"
        if media_hint is None:
            continue
        image_node = block.select_one("img[src]")
        seller_text = None
        seller_match = re.search(r"Sold by:\s*([^$]+?)(?:Buy it again|View your item|Condition:|$)", block_text, re.IGNORECASE)
        if seller_match:
            seller_text = _clean_text(seller_match.group(1))
        item = _build_purchase_preview_item_direct(
            row_no=next_row_no,
            artist_name=None,
            item_name=item_title,
            media_format=media_hint,
            quantity=1,
            unit_price=item_price if item_price is not None else (order_total if len(blocks) == 1 else None),
            line_total=item_price if item_price is not None else (order_total if len(blocks) == 1 else None),
            currency_code=item_currency if item_price is not None else currency_code,
            purchase_date=order_date,
            raw_line=block_text,
            raw_payload={
                "vendor_code": "AMAZON",
                "item_url": item_url,
                "image_url": _clean_text(image_node.get("src") if image_node else None),
                "asin": _purchase_amazon_asin_from_url(item_url),
                "marketplace": item_marketplace,
                "seller_name": seller_text,
                "media_format_inferred": 1 if media_hint == "LP" and _normalize_purchase_media_format(block_text) is None and _normalize_purchase_media_format(item_title) is None else 0,
            },
        )
        if item is None:
            continue
        preview_items.append(item)
        next_row_no += 1
    return preview_items


def _purchase_preview_items_from_ebay_html(raw_content: str, *, purchase_date: str | None) -> list[PurchaseImportPreviewItem]:
    soup = BeautifulSoup(raw_content, "html.parser")
    cards = soup.select(".m-item-card")
    preview_items: list[PurchaseImportPreviewItem] = []
    next_row_no = 1
    for card in cards:
        title_node = card.select_one("h3.title-heading") or card.select_one("h3")
        title = _purchase_compact_text(title_node.get_text(" ", strip=True) if title_node else "")
        if not title:
            continue
        media_format = _normalize_purchase_media_format(title)
        if media_format is None:
            continue
        artist_name, item_name, cover_condition, disc_condition = _parse_ebay_purchase_title(title)
        price_node = card.select_one(".container-item-col__info-item-info-additionalPrice")
        price_text = _purchase_compact_text(price_node.get_text(" ", strip=True) if price_node else "")
        seller_link = card.select_one("a[href*='/usr/']")
        seller_name = _purchase_compact_text(seller_link.get_text(" ", strip=True) if seller_link else "")
        item_link = card.select_one("a[href*='/itm/']")
        item_url = _purchase_normalize_item_url(item_link.get("href") if item_link else None, base_url="https://www.ebay.com")
        image_node = card.select_one("img[src]")
        item = _build_purchase_preview_item_direct(
            row_no=next_row_no,
            artist_name=artist_name,
            item_name=item_name or title,
            media_format=media_format,
            quantity=1,
            unit_price=_parse_price_number(price_text),
            line_total=_parse_price_number(price_text),
            currency_code=_purchase_marketplace_currency("EBAY", None),
            purchase_date=_normalize_purchase_date(purchase_date),
            raw_line=_purchase_compact_text(card.get_text(" ", strip=True)),
            raw_payload={
                "vendor_code": "EBAY",
                "listing_title": title,
                "seller_name": seller_name or "EBAY",
                "item_url": item_url,
                "image_url": _clean_text(image_node.get("src") if image_node else None),
                "parsed_search_artist_name": artist_name,
                "parsed_search_item_name": item_name or title,
                "parsed_cover_condition": cover_condition,
                "parsed_disc_condition": disc_condition,
            },
        )
        if item is None:
            continue
        preview_items.append(item)
        next_row_no += 1
    return preview_items


def _purchase_import_empty_reason(vendor_code: str, raw_content: str) -> str | None:
    vendor = str(vendor_code or "").strip().upper()
    text = str(raw_content or "")
    if vendor == "AMAZON":
        has_order_list = ".order-card" in text or 'class=\"order-card' in text or "order-card" in text
        has_order_details = "#orderDetails" in text or 'id=\"orderDetails' in text or "/order-details?orderID=" in text or "Order Details" in text
        if not has_order_list and not has_order_details:
            return "Amazon 주문 카드(order-card) 또는 주문 상세(orderDetails)를 찾지 못했습니다. 주문목록/주문상세 페이지 MHTML인지 확인하세요."
        return "Amazon 주문 페이지에서 음악 상품 행을 찾지 못했습니다. 다른 주문 페이지 형식이거나 비음악 상품만 포함됐을 수 있습니다."
    if vendor == "EBAY":
        if ".m-item-card" not in text and 'class=\"m-item-card' not in text and "m-item-card" not in text:
            return "eBay 구매 카드(m-item-card)를 찾지 못했습니다. 구매내역 목록 페이지 MHTML인지 확인하세요."
        return "eBay 구매 페이지에서 음악 상품 행을 찾지 못했습니다. 현재 파서는 음악 미디어로 보이는 항목만 추출합니다."
    return None


def _build_purchase_preview_item(
    *,
    row_no: int,
    cells: list[str],
    purchase_date: str | None,
    vendor_code: str,
) -> PurchaseImportPreviewItem | None:
    if not cells:
        return None
    first_text = _clean_text(cells[0])
    if not first_text or "합계" in first_text:
        return None
    if any(str(cell or "").strip() in {"합계", "총계"} for cell in cells):
        return None

    media_idx: int | None = None
    media_format: str | None = None
    for idx, cell in enumerate(cells):
        normalized = _normalize_purchase_media_format(cell)
        if normalized:
            media_idx = idx
            media_format = normalized
            break
    if media_idx is None:
        normalized = _normalize_purchase_media_format(first_text)
        if normalized:
            media_idx = 1 if len(cells) > 1 else 0
            media_format = normalized
    if media_format is None:
        return None

    artist_name, item_name = _split_artist_item_text(first_text)
    if not item_name:
        return None
    quantity = _parse_positive_int(cells[media_idx + 1] if len(cells) > media_idx + 1 else None, 1)
    unit_price = _parse_price_number(cells[media_idx + 2] if len(cells) > media_idx + 2 else None)
    line_total = _parse_price_number(cells[media_idx + 3] if len(cells) > media_idx + 3 else None)
    if line_total is None and unit_price is not None:
        line_total = float(unit_price) * quantity
    raw_line = " | ".join(str(cell or "").strip() for cell in cells if str(cell or "").strip())
    return PurchaseImportPreviewItem(
        row_no=row_no,
        artist_name=artist_name,
        item_name=item_name,
        media_format=media_format,
        quantity=quantity,
        unit_price=unit_price,
        line_total=line_total,
        currency_code="KRW",
        purchase_date=_normalize_purchase_date(purchase_date),
        raw_line=raw_line,
        raw_payload={
            "vendor_code": vendor_code,
            "cells": cells,
        },
    )


def _parse_purchase_import_preview(payload: PurchaseImportPreviewRequest | PurchaseImportWebhookRequest) -> list[PurchaseImportPreviewItem]:
    raw_content, html_content = _resolve_purchase_import_raw_input(payload)
    if not raw_content:
        return []
    vendor_code = _resolve_purchase_import_vendor_code(getattr(payload, "vendor_code", "OTHER"), raw_content=raw_content)
    resolved_purchase_date = _resolve_purchase_import_purchase_date(
        getattr(payload, "purchase_date", None),
        raw_content=raw_content,
    )
    if html_content:
        if vendor_code == "AMAZON":
            preview_items = _purchase_preview_items_from_amazon_html(
                html_content,
                purchase_date=resolved_purchase_date,
            )
            if preview_items:
                return preview_items
        if vendor_code == "EBAY":
            preview_items = _purchase_preview_items_from_ebay_html(
                html_content,
                purchase_date=resolved_purchase_date,
            )
            if preview_items:
                return preview_items
    rows = _purchase_rows_from_html(html_content or raw_content) if html_content else _purchase_rows_from_text(raw_content)
    preview_items: list[PurchaseImportPreviewItem] = []
    next_row_no = 1
    for cells in rows:
        item = _build_purchase_preview_item(
            row_no=next_row_no,
            cells=cells,
            purchase_date=resolved_purchase_date,
            vendor_code=vendor_code,
        )
        if item is None:
            continue
        preview_items.append(item)
        next_row_no += 1
    return preview_items


def _purchase_queue_item_from_row(row: dict[str, Any]) -> PurchaseImportQueueItem:
    raw_payload = dict(row.get("raw_payload") or {})
    parsed_artist_name = _clean_text(raw_payload.get("parsed_search_artist_name"))
    parsed_item_name = _clean_text(raw_payload.get("parsed_search_item_name"))
    if str(row.get("vendor_code") or "").strip().upper() == "EBAY" and (not parsed_artist_name or not parsed_item_name):
        ebay_artist_name, ebay_item_name, ebay_cover_condition, ebay_disc_condition = _parse_ebay_purchase_title(
            _purchase_ebay_parse_source_text(row, raw_payload)
        )
        parsed_artist_name = parsed_artist_name or ebay_artist_name
        parsed_item_name = parsed_item_name or ebay_item_name
        if parsed_artist_name and not raw_payload.get("parsed_search_artist_name"):
            raw_payload["parsed_search_artist_name"] = parsed_artist_name
        if parsed_item_name and not raw_payload.get("parsed_search_item_name"):
            raw_payload["parsed_search_item_name"] = parsed_item_name
        if ebay_cover_condition and not raw_payload.get("parsed_cover_condition"):
            raw_payload["parsed_cover_condition"] = ebay_cover_condition
        if ebay_disc_condition and not raw_payload.get("parsed_disc_condition"):
            raw_payload["parsed_disc_condition"] = ebay_disc_condition
    return PurchaseImportQueueItem(
        id=int(row["id"]),
        vendor_code=str(row.get("vendor_code") or "OTHER"),  # type: ignore[arg-type]
        source_type=str(row.get("source_type") or "MANUAL"),  # type: ignore[arg-type]
        source_ref=_clean_text(row.get("source_ref")),
        email_from=_clean_text(row.get("email_from")),
        email_subject=_clean_text(row.get("email_subject")),
        artist_name=parsed_artist_name or _clean_text(row.get("artist_name")),
        item_name=_purchase_queue_display_item_name(row, raw_payload) or str(row.get("item_name") or "").strip(),
        media_format=_clean_text(row.get("media_format")),
        quantity=max(1, int(row.get("quantity") or 1)),
        unit_price=float(row["unit_price"]) if row.get("unit_price") is not None else None,
        line_total=float(row["line_total"]) if row.get("line_total") is not None else None,
        currency_code=_clean_text(row.get("currency_code")),
        purchase_date=_normalize_purchase_date(row.get("purchase_date")),
        seller_name=_clean_text(row.get("seller_name")),
        item_url=_clean_text(row.get("item_url")),
        image_url=_clean_text(row.get("image_url")),
        raw_line=_clean_text(row.get("raw_line")),
        raw_payload=raw_payload,
        queue_status=str(row.get("queue_status") or "PENDING"),  # type: ignore[arg-type]
        linked_owned_item_id=int(row["linked_owned_item_id"]) if row.get("linked_owned_item_id") is not None else None,
        created_at=str(row.get("created_at") or ""),
        updated_at=str(row.get("updated_at") or ""),
    )


def _purchase_import_webhook_allowed(request: Request) -> bool:
    expected = str(settings.purchase_import_webhook_token or "").strip()
    provided = str(request.headers.get("x-purchase-import-token") or "").strip()
    return bool(expected) and secrets.compare_digest(provided, expected)


# 1 MB ceiling for the JSON body. Gmail forwards rarely exceed a few hundred
# kilobytes; cap higher than that and we are paying the parse cost for what
# is almost certainly an attack or a misrouted request.
PURCHASE_IMPORT_WEBHOOK_MAX_BODY_BYTES = int(
    os.getenv("LIBRARY_PURCHASE_IMPORT_WEBHOOK_MAX_BODY_BYTES", str(1 * 1024 * 1024))
)
_PURCHASE_IMPORT_WEBHOOK_ALLOWED_CONTENT_TYPES = ("application/json",)


def _purchase_import_webhook_validate_request(request: Request) -> None:
    """Hard checks on the incoming HTTP request before we let Pydantic parse it.

    Used as a FastAPI `Depends`. Dependencies run before the route's body
    parameter is parsed, so a wrong Content-Type or oversized body produces
    415/413 instead of falling through to Pydantic's 422 with a confusing
    "Input should be a valid dict" / "Field required" message.

    * Content-Type must be a JSON variant. Browsers / non-JSON callers get
      a 415.
    * Content-Length, when present, must fit our cap. We can't enforce a
      true streaming cap from inside FastAPI without a custom middleware,
      but the header check covers well-behaved clients (Gmail forwarders,
      Zapier).
    """
    content_type = str(request.headers.get("content-type") or "").lower().strip()
    base_type = content_type.split(";", 1)[0].strip()
    if base_type and base_type not in _PURCHASE_IMPORT_WEBHOOK_ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"unsupported content-type: {base_type or 'unknown'}",
        )

    raw_length = str(request.headers.get("content-length") or "").strip()
    if raw_length:
        try:
            declared = int(raw_length)
        except (TypeError, ValueError):
            declared = -1
        if declared > PURCHASE_IMPORT_WEBHOOK_MAX_BODY_BYTES:
            raise HTTPException(
                status_code=413,
                detail=(
                    "request body exceeds purchase import webhook limit of "
                    f"{PURCHASE_IMPORT_WEBHOOK_MAX_BODY_BYTES} bytes"
                ),
            )


def _require_purchase_import_webhook_envelope(request: Request) -> None:
    """Composite Depends: token + envelope checks together.

    Combines the token gate with the Content-Type / Content-Length check so
    a single `dependencies=[...]` on the route covers everything that has
    to happen before Pydantic parses the body.
    """
    if not _purchase_import_webhook_allowed(request):
        raise HTTPException(status_code=403, detail="purchase import webhook token mismatch")
    _purchase_import_webhook_validate_request(request)


def _clean_track_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()]


def _get_master_member_track_fallback(master_id: int, exclude_owned_item_id: int | None = None) -> list[str]:
    """마스터 멤버 중 수록곡이 있는 첫 번째 상품의 track_list를 반환한다."""
    import json as _json
    exclude_clause = ""
    params: list[Any] = [master_id]
    if exclude_owned_item_id:
        exclude_clause = "AND amm.owned_item_id <> ?"
        params.append(exclude_owned_item_id)
    with db.get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT mid.track_list_json
            FROM album_master_member amm
            JOIN music_item_detail mid ON mid.owned_item_id = amm.owned_item_id
            WHERE amm.album_master_id = ?
              {exclude_clause}
              AND mid.track_list_json IS NOT NULL
              AND TRIM(mid.track_list_json) NOT IN ('', '[]')
            ORDER BY amm.id ASC
            LIMIT 1
            """,
            params,
        ).fetchall()
    for row in rows:
        try:
            parsed = _json.loads(str(row["track_list_json"]))
        except Exception:
            continue
        if isinstance(parsed, list):
            clean = [str(v).strip() for v in parsed if str(v).strip()]
            if clean:
                return clean
    return []


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


def _build_music_detail_for_sync(
    candidate: dict[str, Any],
    snapshot: dict[str, Any],
    only_missing: bool,
) -> tuple[dict[str, Any], list[str]]:
    def merge_text(field: str, current: Any, incoming: Any) -> str | None:
        current_text = _clean_text(current)
        incoming_text = _clean_text(incoming)
        if incoming_text is None:
            return current_text
        if only_missing and current_text is not None:
            return current_text
        if current_text != incoming_text:
            updated_fields.append(field)
        return incoming_text

    def merge_int(field: str, current: Any, incoming: Any) -> int | None:
        current_val = int(current) if isinstance(current, int) else None
        incoming_val: int | None = None
        if isinstance(incoming, int):
            incoming_val = int(incoming)
        elif isinstance(incoming, str):
            try:
                incoming_val = int(incoming.strip())
            except (TypeError, ValueError):
                incoming_val = None
        if incoming_val is None:
            return current_val
        if only_missing and current_val is not None:
            return current_val
        if current_val != incoming_val:
            updated_fields.append(field)
        return incoming_val

    def merge_bool(field: str, current: Any, incoming: Any) -> bool | None:
        current_val = _normalize_has_obi_input(current)
        incoming_val = _normalize_has_obi_input(incoming)
        if incoming_val is None:
            return current_val
        if only_missing and current_val is not None:
            return current_val
        if current_val != incoming_val:
            updated_fields.append(field)
        return incoming_val

    def merge_list(field: str, current: Any, incoming: Any) -> list[str]:
        current_list = _clean_string_list(current)
        incoming_list = _clean_string_list(incoming)
        if not incoming_list:
            return current_list
        if only_missing and current_list:
            return current_list
        if current_list != incoming_list:
            updated_fields.append(field)
        return incoming_list

    def merge_dict_list(field: str, current: Any, incoming: Any) -> list[dict[str, Any]]:
        current_list = current if isinstance(current, list) else []
        current_list = [row for row in current_list if isinstance(row, dict)]
        incoming_list = incoming if isinstance(incoming, list) else []
        incoming_list = [row for row in incoming_list if isinstance(row, dict)]
        if not incoming_list:
            return current_list
        if only_missing and current_list:
            return current_list
        if current_list != incoming_list:
            updated_fields.append(field)
        return incoming_list

    def merge_runout_list(field: str, current: Any, incoming: Any) -> list[str]:
        def normalize(values: Any) -> list[str]:
            if isinstance(values, list):
                return [str(v).strip() for v in values if str(v).strip()]
            text = _clean_text(values)
            if not text:
                return []
            return [p.strip() for p in text.split("|") if p.strip()]

        current_list = normalize(current)
        incoming_list = normalize(incoming)
        if not incoming_list:
            return current_list
        if only_missing and current_list:
            return current_list
        if current_list != incoming_list:
            updated_fields.append(field)
        return incoming_list

    updated_fields: list[str] = []
    category = str(candidate.get("category") or "CD").upper()
    format_name = str(candidate.get("format_name") or category).upper()
    if format_name not in MUSIC_CATEGORIES:
        format_name = category if category in MUSIC_CATEGORIES else "CD"

    existing_tracks = _clean_track_list(candidate.get("track_list"))
    snapshot_tracks = _clean_track_list(snapshot.get("track_list"))
    track_list = existing_tracks
    if snapshot_tracks and ((only_missing and not existing_tracks) or ((not only_missing) and existing_tracks != snapshot_tracks)):
        track_list = snapshot_tracks
        updated_fields.append("track_list")

    music_detail = {
        "format_name": format_name,
        "is_promotional_not_for_sale": bool(candidate.get("is_promotional_not_for_sale")),
        "artist_or_brand": merge_text("artist_or_brand", candidate.get("artist_or_brand"), snapshot.get("artist_or_brand")),
        "release_year": merge_int("release_year", candidate.get("release_year"), snapshot.get("release_year")),
        "released_date": merge_text("released_date", candidate.get("released_date"), snapshot.get("released_date")),
        "barcode": merge_text("barcode", candidate.get("barcode"), snapshot.get("barcode")),
        "label_name": merge_text("label_name", candidate.get("label_name"), snapshot.get("label_name")),
        "catalog_no": merge_text("catalog_no", candidate.get("catalog_no"), snapshot.get("catalog_no")),
        "cover_image_url": merge_text("cover_image_url", candidate.get("cover_image_url"), snapshot.get("cover_image_url")),
        "media_type": merge_text("media_type", candidate.get("media_type"), snapshot.get("media_type")),
        "genres": merge_list("genres", candidate.get("genres"), snapshot.get("genres")),
        "styles": merge_list("styles", candidate.get("styles"), snapshot.get("styles")),
        "disc_count": merge_int("disc_count", candidate.get("disc_count"), snapshot.get("disc_count")),
        "speed_rpm": merge_int("speed_rpm", candidate.get("speed_rpm"), snapshot.get("speed_rpm")),
        "has_obi": merge_bool("has_obi", candidate.get("has_obi"), snapshot.get("has_obi")),
        "runout_matrix": merge_runout_list("runout_matrix", candidate.get("runout_matrix"), snapshot.get("runout_matrix")),
        "pressing_country": merge_text("pressing_country", candidate.get("pressing_country"), snapshot.get("pressing_country")),
        "source_notes": merge_text("source_notes", candidate.get("source_notes"), snapshot.get("source_notes")),
        "credits": merge_list("credits", candidate.get("credits"), snapshot.get("credits")),
        "identifier_items": merge_dict_list("identifier_items", candidate.get("identifier_items"), snapshot.get("identifier_items")),
        "image_items": merge_dict_list("image_items", candidate.get("image_items"), snapshot.get("image_items")),
        "company_items": merge_dict_list("company_items", candidate.get("company_items"), snapshot.get("company_items")),
        "series": merge_list("series", candidate.get("series"), snapshot.get("series")),
        "format_items": merge_dict_list("format_items", candidate.get("format_items"), snapshot.get("format_items")),
        "track_items": merge_dict_list("track_items", candidate.get("track_items"), snapshot.get("track_items")),
        "label_items": merge_dict_list("label_items", candidate.get("label_items"), snapshot.get("label_items")),
        "track_list": track_list,
        "cover_condition": _clean_text(candidate.get("cover_condition")),
        "disc_condition": _clean_text(candidate.get("disc_condition")),
    }
    return music_detail, sorted(set(updated_fields))

def _get_db_conn():
    from app.db import get_conn
    return get_conn()

_SYNC_IMAGE_QUEUE: list[tuple[int, str, str, dict[str, Any]]] = []
_SYNC_IMAGE_THREAD: threading.Thread | None = None
_SYNC_IMAGE_COUNT = 0

def _trigger_sync_image_download(
    owned_item_id: int,
    source_code: str,
    source_external_id: str,
    snapshot: dict[str, Any],
) -> None:
    """Immediately download images for a single item (individual sync)."""
    import threading as _th
    def _run():
        try:
            _download_images_for_item(owned_item_id, source_code, source_external_id, snapshot)
        except Exception:
            pass
    _th.Thread(target=_run, daemon=True).start()

def _download_images_for_item(
    owned_item_id: int,
    source_code: str,
    source_external_id: str,
    snapshot: dict[str, Any],
) -> None:
    """Download all available images for one item."""
    from app.services.image_store import download_images
    from pathlib import Path
    static_dir = Path(__file__).resolve().parent / "static"
    items = []
    # Collect from snapshot
    cover = str(snapshot.get("cover_image_url") or "").strip()
    extra = snapshot.get("image_items") or []
    if cover:
        items.append({"type": "앞면", "uri": cover})
    if isinstance(extra, list):
        items.extend([{"type": it.get("type", "추가"), "uri": it.get("uri", "")} for it in extra if it.get("uri")])
    # ALADIN additional
    if source_code == "ALADIN" and source_external_id:
        try:
            from app.services.providers import _fetch_aladin_images_from_web
            aladin_extra = _fetch_aladin_images_from_web(source_external_id, source_external_id)
            items.extend(aladin_extra)
        except Exception:
            pass
    if items:
        result = download_images(
            owned_item_id=owned_item_id,
            image_items=items,
            source=source_code,
            static_dir=static_dir,
            source_external_id=source_external_id,
        )
        if result:
            import json as _json
            with _get_db_conn() as conn:
                conn.execute(
                    "UPDATE music_item_detail SET local_image_items_json=? WHERE owned_item_id=?",
                    (_json.dumps(result, ensure_ascii=False), owned_item_id),
                )

def _has_local_images(owned_item_id: int) -> bool:
    """Check if the item already has local images."""
    try:
        with _get_db_conn() as conn:
            row = conn.execute(
                "SELECT local_image_items_json FROM music_item_detail WHERE owned_item_id=?",
                (owned_item_id,)
            ).fetchone()
            if row and row[0] and row[0] not in ("[]", "null", ""):
                return True
    except Exception:
        pass
    return False

def _start_sync_image_download_thread() -> None:
    """Start background thread to process the sync image queue."""
    global _SYNC_IMAGE_THREAD, _SYNC_IMAGE_QUEUE, _SYNC_IMAGE_COUNT
    queue = _SYNC_IMAGE_QUEUE[:]
    _SYNC_IMAGE_QUEUE = []
    _SYNC_IMAGE_COUNT = len(queue)

    def _run():
        global _SYNC_IMAGE_COUNT
        for owned_item_id, source_code, source_external_id, snapshot in queue:
            try:
                _download_images_for_item(owned_item_id, source_code, source_external_id, snapshot)
            except Exception:
                pass
            _SYNC_IMAGE_COUNT -= 1
    _SYNC_IMAGE_THREAD = threading.Thread(target=_run, daemon=True, name="sync-image-download")
    _SYNC_IMAGE_THREAD.start()



def _run_metadata_sync(
    payload: MetadataSyncRunRequest,
    fail_when_running: bool = True,
) -> MetadataSyncRunResponse | None:
    global METADATA_SYNC_LAST_RESULT, METADATA_SYNC_LAST_ERROR, METADATA_SYNC_IN_PROGRESS_ITEMS

    acquired = METADATA_SYNC_LOCK.acquire(blocking=False)
    if not acquired:
        if fail_when_running:
            raise HTTPException(status_code=409, detail="metadata sync already running")
        return None

    started_at = _now_iso()
    METADATA_SYNC_IN_PROGRESS_ITEMS = []  # reset live feed
    try:
        source_u = str(payload.source or "ALL").upper()
        source_filter = None if source_u == "ALL" else source_u
        candidates = db.list_metadata_sync_candidates(
            source_code=source_filter,
            only_missing=bool(payload.only_missing),
            limit=int(payload.limit),
            offset=0,
        )

        item_results: list[MetadataSyncItemResult] = []
        updated_count = 0
        skipped_count = 0
        failed_count = 0
        # Track IDs that were processed but NOT updated via upsert_music_detail.
        # We'll touch their owned_item.updated_at at the end so they don't
        # repeatedly appear at the top of the sync queue (ORDER BY updated_at ASC).
        non_updated_ids: list[int] = []

        def _item_meta(row: dict[str, Any]) -> dict[str, Any]:
            """로그 표시용 식별 메타 (display_name, artist_or_brand, catalog_no)."""
            return {
                "display_name": _clean_text(row.get("display_name")),
                "artist_or_brand": _clean_text(row.get("artist_or_brand")),
                "catalog_no": _clean_text(row.get("catalog_no")),
            }

        def _record(item: MetadataSyncItemResult) -> None:
            """항목 결과를 실시간 피드 및 최종 결과 목록에 기록한다."""
            METADATA_SYNC_IN_PROGRESS_ITEMS.append(item)
            if payload.include_item_results:
                item_results.append(item)

        for row in candidates:
            discogs_supplement = None
            owned_item_id = int(row.get("id") or 0)
            source_code = str(row.get("source_code") or "").strip().upper()
            source_external_id = str(row.get("source_external_id") or "").strip()
            if owned_item_id <= 0 or not source_code or not source_external_id:
                failed_count += 1
                _record(MetadataSyncItemResult(
                    owned_item_id=owned_item_id,
                    source_code=source_code or "-",
                    source_external_id=source_external_id or "-",
                    status="FAILED",
                    reason="invalid candidate data",
                    **_item_meta(row),
                ))
                if owned_item_id > 0:
                    non_updated_ids.append(owned_item_id)
                continue

            if source_code not in {"DISCOGS", "MANIADB", "ALADIN"}:
                skipped_count += 1
                _record(MetadataSyncItemResult(
                    owned_item_id=owned_item_id,
                    source_code=source_code,
                    source_external_id=source_external_id,
                    status="SKIPPED",
                    reason="source not supported for snapshot sync",
                    **_item_meta(row),
                ))
                non_updated_ids.append(owned_item_id)
                continue

            delay = float(payload.inter_item_delay_sec or 0.0)
            if delay > 0:
                time.sleep(delay)

            snapshot = get_source_release_snapshot(source=source_code, external_id=source_external_id)
            if not snapshot:
                failed_count += 1
                _record(MetadataSyncItemResult(
                    owned_item_id=owned_item_id,
                    source_code=source_code,
                    source_external_id=source_external_id,
                    status="FAILED",
                    reason="source snapshot not found",
                    **_item_meta(row),
                ))
                non_updated_ids.append(owned_item_id)
                continue

            # Discogs 부가정보 보강: MANIADB, ALADIN 등 타 소스 아이템의 경우
            # 바코드가 정확히 일치하는 Discogs 릴리즈를 검색하고,
            # 오기(Barcode Collision)를 방지하기 위해 제목/아티스트 유사도를 검증한 뒤,
            # 포맷(CD/LP)을 포함한 모든 상세 부가 정보를 Discogs 기준으로 덮어씌웁니다.
            if payload.supplement_discogs and source_code != "DISCOGS":
                from app.services.providers import (
                    _try_discogs_for_barcode, _try_discogs_for_catalog_no,
                    _token_similarity, _validate_barcode_checksum,
                )
                if delay > 0:
                    time.sleep(delay)
                discogs_supplement = None
                barcode = str(row.get("barcode") or "").strip()
                barcode_digits = barcode.replace(" ", "").replace("-", "")
                # 1차: 바코드 (EAN-13/UPC-A 체크섬, 880 포함)
                if _validate_barcode_checksum(barcode_digits):
                    discogs_supplement = _try_discogs_for_barcode(barcode_digits)
                    if discogs_supplement:
                        orig_text = f"{row.get('artist_or_brand') or ''} {row.get('master_title') or row.get('display_name') or ''}".strip()
                        disc_text = f"{discogs_supplement.get('artist_or_brand') or ''} {discogs_supplement.get('title') or ''}".strip()
                        sim = _token_similarity(orig_text, disc_text) if orig_text and disc_text else 0.0
                        # 유사도 + 미디어 타입 검증 (바코드 경로는 포맷 일치 필수)
                        orig_fmt = str(row.get("format_name") or "").upper()
                        disc_fmt = str(discogs_supplement.get("format_name") or "").upper()
                        fmt_ok = (not orig_fmt or not disc_fmt or orig_fmt == disc_fmt)
                        if sim < 0.85 or not fmt_ok:
                            discogs_supplement = None
                # 2차: 카탈로그넘버 fallback (바코드 없거나 검증 실패 시)
                if discogs_supplement is None:
                    catalog_no = str(row.get("catalog_no") or "").strip()
                    if catalog_no:
                        discogs_supplement = _try_discogs_for_catalog_no(
                            catalog_no=catalog_no,
                            artist=str(row.get("artist_or_brand") or ""),
                            title=str(row.get("master_title") or row.get("display_name") or ""),
                            format_name=str(row.get("format_name") or "") or None,
                            pressing_country=str(row.get("pressing_country") or "") or None,
                        )
                if discogs_supplement:
                    _DISCOGS_FIELDS = {
                        "disc_count", "speed_rpm", "has_obi",
                        "runout_matrix", "pressing_country", "source_notes",
                        "credits", "identifier_items", "image_items",
                        "company_items", "series", "format_items",
                        "track_items", "label_items", "genres", "styles",
                    }
                    for field in _DISCOGS_FIELDS:
                        val = discogs_supplement.get(field)
                        has_val = bool(val) if isinstance(val, (list, dict)) else val is not None
                        if has_val:
                            snapshot[field] = val
            music_detail, updated_fields = _build_music_detail_for_sync(
                candidate=row,
                snapshot=snapshot,
                only_missing=bool(payload.only_missing),
            )
            # 마스터 수록곡 폴백: 소스(ManiaDB 등)에 수록곡 없고, 마스터에 연결된
            # 다른 보유 상품의 수록곡이 있으면 그것을 사용한다.
            _fallback_master_id = int(row.get("linked_album_master_id") or 0)
            if not music_detail.get("track_list") and _fallback_master_id > 0:
                master_tracks = _get_master_member_track_fallback(
                    master_id=_fallback_master_id,
                    exclude_owned_item_id=owned_item_id,
                )
                if master_tracks:
                    music_detail["track_list"] = master_tracks
                    if "track_list" not in updated_fields:
                        updated_fields.append("track_list")
            if not updated_fields:
                skipped_count += 1
                # Queue image download even if no metadata to update (only if no images yet)
                if not _has_local_images(owned_item_id):
                    _SYNC_IMAGE_QUEUE.append((
                        owned_item_id, source_code, source_external_id, snapshot
                    ))
                _record(MetadataSyncItemResult(
                    owned_item_id=owned_item_id,
                    source_code=source_code,
                    source_external_id=source_external_id,
                    status="SKIPPED",
                    reason="no missing fields to update",
                    **_item_meta(row),
                ))
                non_updated_ids.append(owned_item_id)
                continue

            note_append = None
            if updated_fields:
                release_info = ""
                if source_code == "DISCOGS":
                    release_info = f"[Discogs: {source_external_id}] "
                elif discogs_supplement:
                    discogs_ext = discogs_supplement.get("external_id")
                    if discogs_ext:
                        release_info = f"[Discogs Barcode Match: {discogs_ext}] "
                
                note_append = f"[메타동기화] {release_info}업데이트: {', '.join(updated_fields)}"

            db.upsert_music_detail(owned_item_id=owned_item_id, music_detail=music_detail, note_append=note_append)
            linked_master_id = int(row.get("linked_album_master_id") or 0)
            if linked_master_id > 0:
                db.update_album_master_genres(
                    album_master_id=linked_master_id,
                    genres=music_detail.get("genres") or [],
                    styles=music_detail.get("styles") or [],
                )
            updated_count += 1
            # Queue for image download after sync completes (only if no images yet)
            if not _has_local_images(owned_item_id):
                _SYNC_IMAGE_QUEUE.append((
                    owned_item_id, source_code, source_external_id, snapshot
                ))
            _record(MetadataSyncItemResult(
                owned_item_id=owned_item_id,
                source_code=source_code,
                source_external_id=source_external_id,
                status="UPDATED",
                updated_fields=updated_fields,
                **_item_meta(row),
            ))

        # Touch updated_at for SKIPPED/FAILED items so they advance in the
        # sync queue and don't appear repeatedly on subsequent runs.
        if non_updated_ids:
            _touch_now = _now_iso()
            with db.get_conn() as _conn:
                _placeholders = ",".join("?" * len(non_updated_ids))
                _conn.execute(
                    f"UPDATE owned_item SET updated_at = ? WHERE id IN ({_placeholders})",
                    [_touch_now, *non_updated_ids],
                )

        result = MetadataSyncRunResponse(
            started_at=started_at,
            completed_at=_now_iso(),
            source=source_u,
            only_missing=bool(payload.only_missing),
            limit=int(payload.limit),
            processed_count=len(candidates),
            updated_count=updated_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            item_results=item_results if payload.include_item_results else [],
        )
        # Start background image download for queued items
        if _SYNC_IMAGE_QUEUE:
            _start_sync_image_download_thread()

        METADATA_SYNC_LAST_RESULT = result
        METADATA_SYNC_LAST_ERROR = None
        return result
    finally:
        METADATA_SYNC_LOCK.release()


def _metadata_sync_worker() -> None:
    global METADATA_SYNC_LAST_ERROR
    settings = get_settings()
    interval = max(0, int(settings.metadata_sync_interval_minutes))
    batch_limit = max(1, int(settings.metadata_sync_batch_limit))
    if interval <= 0:
        return

    while not METADATA_SYNC_STOP_EVENT.wait(interval * 60):
        try:
            _run_metadata_sync(
                MetadataSyncRunRequest(
                    source="ALL",
                    only_missing=True,
                    limit=batch_limit,
                    include_item_results=False,
                ),
                fail_when_running=False,
            )
        except Exception as exc:
            METADATA_SYNC_LAST_ERROR = f"{_now_iso()} | {exc}"
            logger.exception("metadata sync worker failed")
            continue


def _start_metadata_sync_worker() -> None:
    global METADATA_SYNC_THREAD
    settings = get_settings()
    if int(settings.metadata_sync_interval_minutes) <= 0:
        return
    if METADATA_SYNC_THREAD is not None and METADATA_SYNC_THREAD.is_alive():
        return
    METADATA_SYNC_STOP_EVENT.clear()
    METADATA_SYNC_THREAD = threading.Thread(
        target=_metadata_sync_worker,
        name="metadata-sync-worker",
        daemon=True,
    )
    METADATA_SYNC_THREAD.start()


def _normalize_backup_dir_path(raw_value: Any) -> str:
    text = str(raw_value or "").strip()
    if not text:
        return str(Path(settings.db_path).resolve().parent / "backups")
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    return str(path)


def _write_db_snapshot_to_path(target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with db.get_conn() as source_conn:
        dest_conn = sqlite3.connect(str(target_path))
        try:
            source_conn.backup(dest_conn)
        finally:
            dest_conn.close()


def _create_local_db_backup(backup_dir: str, *, reason: str = "manual") -> str:
    target_dir = Path(_normalize_backup_dir_path(backup_dir))
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    final_path = target_dir / f"__PROJECT_SLUG__-library-{reason}-{timestamp}.db"
    temp_path = target_dir / f".__PROJECT_SLUG__-library-{reason}-{timestamp}-{uuid4().hex}.tmp"
    _write_db_snapshot_to_path(temp_path)
    temp_path.replace(final_path)
    return str(final_path)


def _create_local_full_backup_bundle(
    backup_dir: str,
    *,
    reason: str = "manual-full",
    include_env_file: bool = False,
) -> str:
    target_dir = Path(_normalize_backup_dir_path(backup_dir))
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    final_path = target_dir / f"__PROJECT_SLUG__-library-{reason}-{timestamp}.zip"
    temp_path = target_dir / f".__PROJECT_SLUG__-library-{reason}-{timestamp}-{uuid4().hex}.tmp"
    temp_db_path = target_dir / f".__PROJECT_SLUG__-library-{reason}-{timestamp}-{uuid4().hex}.db"
    project_root = Path(__file__).resolve().parents[1]
    env_path = project_root / ".env.local"
    manifest = {
        "kind": "__PROJECT_SLUG__-library-full-backup",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "db_filename": "library.db",
        "includes_uploads": IMAGE_UPLOAD_DIR.exists(),
        "includes_env_file": bool(include_env_file and env_path.is_file()),
    }
    try:
        _write_db_snapshot_to_path(temp_db_path)
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.write(temp_db_path, arcname="library.db")
            if IMAGE_UPLOAD_DIR.exists():
                for file_path in sorted(p for p in IMAGE_UPLOAD_DIR.rglob("*") if p.is_file()):
                    bundle.write(file_path, arcname=str(Path("uploads") / file_path.relative_to(IMAGE_UPLOAD_DIR)))
            if include_env_file and env_path.is_file():
                bundle.write(env_path, arcname=".env.local")
            bundle.writestr(
                "manifest.json",
                json.dumps(manifest, ensure_ascii=False, separators=(",", ":")),
            )
        temp_path.replace(final_path)
    finally:
        temp_db_path.unlink(missing_ok=True)
        Path(temp_path).unlink(missing_ok=True)
    return str(final_path)


def _read_launchd_calendar_interval(plist_path: Path) -> dict[str, int] | None:
    if not plist_path.is_file():
        return None
    try:
        with plist_path.open("rb") as handle:
            payload = plistlib.load(handle)
    except Exception:
        return None
    interval = payload.get("StartCalendarInterval")
    if isinstance(interval, list):
        interval = interval[0] if interval else None
    if not isinstance(interval, dict):
        return None
    try:
        hour = int(interval.get("Hour"))
        minute = int(interval.get("Minute"))
    except (TypeError, ValueError):
        return None
    schedule: dict[str, int] = {"hour": hour, "minute": minute}
    weekday = interval.get("Weekday")
    if weekday is not None:
        try:
            schedule["weekday"] = int(weekday)
        except (TypeError, ValueError):
            pass
    return schedule


def _format_launchd_schedule_label(schedule: dict[str, int] | None) -> str | None:
    if not schedule:
        return None
    time_text = f"{int(schedule.get('hour', 0)):02d}:{int(schedule.get('minute', 0)):02d}"
    weekday = schedule.get("weekday")
    if weekday is None:
        return time_text
    weekday_names = {
        0: "일요일",
        1: "월요일",
        2: "화요일",
        3: "수요일",
        4: "목요일",
        5: "금요일",
        6: "토요일",
        7: "일요일",
    }
    return f"{weekday_names.get(int(weekday), '주간')} {time_text}"


def _read_backup_launchd_schedules() -> dict[str, str | None]:
    project_root = Path(__file__).resolve().parents[1]
    launch_agents_dir = Path.home() / "Library" / "LaunchAgents"

    def _read_first_label(*candidates: Path) -> str | None:
        for candidate in candidates:
            label = _format_launchd_schedule_label(_read_launchd_calendar_interval(candidate))
            if label:
                return label
        return None

    return {
        "daily_schedule": _read_first_label(
            launch_agents_dir / "com.muzlife.backup-daily-db.plist",
            project_root / "deploy" / "templates" / "launchd" / "com.muzlife.backup-daily-db.plist",
        ),
        "weekly_schedule": _read_first_label(
            launch_agents_dir / "com.muzlife.backup-weekly-full.plist",
            project_root / "deploy" / "templates" / "launchd" / "com.muzlife.backup-weekly-full.plist",
        ),
    }


def _validate_library_db_file(candidate_path: Path) -> None:
    conn = sqlite3.connect(f"file:{candidate_path}?mode=ro", uri=True, timeout=1)
    try:
        quick_check = conn.execute("PRAGMA quick_check").fetchone()
        if not quick_check or str(quick_check[0] or "").strip().lower() != "ok":
            raise ValueError("복구 파일의 SQLite 무결성 검사에 실패했습니다.")
        row = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'owned_item'
            """
        ).fetchone()
        if row is None:
            raise ValueError("복구 파일이 라이브러리 DB 형식이 아닙니다.")
    except sqlite3.DatabaseError as err:
        raise ValueError("복구 파일이 유효한 SQLite DB가 아닙니다.") from err
    finally:
        conn.close()


def _restore_library_db_from_upload(upload_path: str, original_filename: str) -> dict[str, Any]:
    if METADATA_SYNC_LOCK.locked():
        raise ValueError("메타 동기화 실행 중에는 DB 복구를 시작할 수 없습니다.")
    source_path = Path(upload_path)
    _validate_library_db_file(source_path)
    backup_settings = db.get_auto_backup_settings()
    backup_dir = _normalize_backup_dir_path(backup_settings.get("backup_dir"))
    backup_path = _create_local_db_backup(backup_dir, reason="before-restore")
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    staged_path = db_path.with_name(f".{db_path.name}.restore-{uuid4().hex}.tmp")
    shutil.copyfile(source_path, staged_path)
    for suffix in ("-wal", "-shm"):
        candidate = Path(f"{settings.db_path}{suffix}")
        if candidate.exists():
            candidate.unlink(missing_ok=True)
    staged_path.replace(db_path)
    db.ensure_startup_db_ready()
    return {
        "restored": True,
        "restored_filename": str(original_filename or source_path.name or "restore.db"),
        "restored_bytes": int(source_path.stat().st_size),
        "backup_path": backup_path,
    }


def _restore_library_bundle_from_upload(upload_path: str, original_filename: str) -> dict[str, Any]:
    if METADATA_SYNC_LOCK.locked():
        raise ValueError("메타 동기화 실행 중에는 DB 복구를 시작할 수 없습니다.")
    source_path = Path(upload_path)
    try:
        bundle = zipfile.ZipFile(source_path)
    except zipfile.BadZipFile as err:
        raise ValueError("복구 파일이 유효한 ZIP 백업이 아닙니다.") from err
    with bundle:
        broken_member = bundle.testzip()
        if broken_member:
            raise ValueError("복구 ZIP 파일이 손상되었습니다.")
        names = bundle.namelist()
        for name in names:
            parts = Path(name).parts
            if any(part == ".." for part in parts) or Path(name).is_absolute():
                raise ValueError("복구 ZIP 파일 경로가 올바르지 않습니다.")
        db_member = "library.db" if "library.db" in names else next((name for name in names if name.lower().endswith(".db")), None)
        if not db_member:
            raise ValueError("복구 파일에 library.db가 없습니다.")
        has_uploads = any(name.startswith("uploads/") and not name.endswith("/") for name in names)
        has_env = ".env.local" in names
        extract_root = Path(tempfile.mkdtemp(prefix="__PROJECT_SLUG__-restore-bundle-"))
        try:
            extracted_db_path = extract_root / "library.db"
            with bundle.open(db_member, "r") as source_db, open(extracted_db_path, "wb") as target_db:
                shutil.copyfileobj(source_db, target_db)
            _validate_library_db_file(extracted_db_path)

            backup_settings = db.get_auto_backup_settings()
            backup_dir = _normalize_backup_dir_path(backup_settings.get("backup_dir"))
            backup_path = _create_local_full_backup_bundle(backup_dir, reason="before-full-restore", include_env_file=True)

            db_path = Path(settings.db_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            staged_path = db_path.with_name(f".{db_path.name}.restore-{uuid4().hex}.tmp")
            shutil.copyfile(extracted_db_path, staged_path)
            for suffix in ("-wal", "-shm"):
                candidate = Path(f"{settings.db_path}{suffix}")
                if candidate.exists():
                    candidate.unlink(missing_ok=True)
            staged_path.replace(db_path)

            if has_uploads:
                uploads_extract_root = extract_root / "uploads"
                bundle.extractall(extract_root, members=[name for name in names if name.startswith("uploads/")])
                if IMAGE_UPLOAD_DIR.exists():
                    shutil.rmtree(IMAGE_UPLOAD_DIR)
                if uploads_extract_root.exists():
                    IMAGE_UPLOAD_DIR.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(uploads_extract_root), str(IMAGE_UPLOAD_DIR))

            if has_env:
                env_target = Path(__file__).resolve().parents[1] / ".env.local"
                with bundle.open(".env.local", "r") as source_env, open(env_target, "wb") as target_env:
                    shutil.copyfileobj(source_env, target_env)

            db.ensure_startup_db_ready()
            return {
                "restored": True,
                "restored_filename": str(original_filename or source_path.name or "restore.zip"),
                "restored_bytes": int(source_path.stat().st_size),
                "backup_path": backup_path,
            }
        finally:
            shutil.rmtree(extract_root, ignore_errors=True)


def _maybe_run_auto_backup_once(*, now: datetime | None = None) -> str | None:
    backup_settings = db.get_auto_backup_settings()
    if not bool(backup_settings.get("enabled")):
        return None
    interval_minutes = max(0, int(backup_settings.get("interval_minutes") or 0))
    if interval_minutes <= 0:
        return None
    now_dt = now or datetime.now(timezone.utc)
    last_backup_at_text = str(backup_settings.get("last_backup_at") or "").strip()
    if last_backup_at_text:
        try:
            last_backup_at = datetime.fromisoformat(last_backup_at_text)
        except ValueError:
            last_backup_at = None
        else:
            if last_backup_at.tzinfo is None:
                last_backup_at = last_backup_at.replace(tzinfo=timezone.utc)
        if last_backup_at is not None and now_dt < (last_backup_at + timedelta(minutes=interval_minutes)):
            return None
    if not AUTO_BACKUP_LOCK.acquire(blocking=False):
        return None
    try:
        backup_scope = str(backup_settings.get("backup_scope") or "DB").strip().upper()
        include_env_file = bool(backup_settings.get("include_env_file"))
        if backup_scope == "FULL":
            backup_path = _create_local_full_backup_bundle(
                str(backup_settings.get("backup_dir") or ""),
                reason="auto",
                include_env_file=include_env_file,
            )
        else:
            backup_path = _create_local_db_backup(str(backup_settings.get("backup_dir") or ""), reason="auto")
        db.record_auto_backup_result(
            last_backup_at=now_dt.astimezone(timezone.utc).isoformat(),
            last_backup_path=backup_path,
            last_error=None,
        )
        return backup_path
    except Exception as exc:
        db.record_auto_backup_result(
            last_backup_at=last_backup_at_text or None,
            last_backup_path=str(backup_settings.get("last_backup_path") or "").strip() or None,
            last_error=f"{now_dt.astimezone(timezone.utc).isoformat()} | {exc}",
        )
        logger.exception("auto backup worker failed")
        return None
    finally:
        AUTO_BACKUP_LOCK.release()


def _auto_backup_worker() -> None:
    while not AUTO_BACKUP_STOP_EVENT.wait(60):
        _maybe_run_auto_backup_once()


def _start_auto_backup_worker() -> None:
    global AUTO_BACKUP_THREAD
    if AUTO_BACKUP_THREAD is not None and AUTO_BACKUP_THREAD.is_alive():
        return
    AUTO_BACKUP_STOP_EVENT.clear()
    AUTO_BACKUP_THREAD = threading.Thread(
        target=_auto_backup_worker,
        name="auto-backup-worker",
        daemon=True,
    )
    AUTO_BACKUP_THREAD.start()


# Startup / shutdown hooks live in the `lifespan` context manager defined
# near the top of this module. The old @app.on_event("startup"/"shutdown")
# pattern is deprecated since FastAPI 0.93.
























@app.post("/ops/export/db-restore", response_model=DatabaseRestoreResponse)
async def restore_db_backup(request: Request, file: UploadFile = File(...)) -> DatabaseRestoreResponse:
    _require_admin_request(request)
    filename = str(file.filename or "").strip() or "restore.db"
    tmp = tempfile.NamedTemporaryFile(prefix="__PROJECT_SLUG__-restore-", suffix=".db", delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
        with open(tmp_path, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
        result = _restore_library_db_from_upload(tmp_path, filename)
        return DatabaseRestoreResponse(**result)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"DB 복구 실패: {err}") from err
    finally:
        await file.close()
        Path(tmp_path).unlink(missing_ok=True)


@app.post("/ops/export/full-restore", response_model=DatabaseRestoreResponse)
async def restore_full_backup(request: Request, file: UploadFile = File(...)) -> DatabaseRestoreResponse:
    _require_admin_request(request)
    filename = str(file.filename or "").strip() or "restore.zip"
    tmp = tempfile.NamedTemporaryFile(prefix="__PROJECT_SLUG__-full-restore-", suffix=".zip", delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
        with open(tmp_path, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
        result = _restore_library_bundle_from_upload(tmp_path, filename)
        return DatabaseRestoreResponse(**result)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"전체 백업 복구 실패: {err}") from err
    finally:
        await file.close()
        Path(tmp_path).unlink(missing_ok=True)








# Auth routes (/login, /auth/login, /auth/logout, /auth/session) live in
# app/api/auth.py. They are wired below via app.include_router.




def _cabinet_camera_item_from_row(row: dict[str, Any]) -> CabinetCameraItem:
    description = str(row.get("notes") or "").strip() or None
    return CabinetCameraItem(
        id=int(row["id"]),
        cabinet_name=str(row.get("cabinet_name") or "").strip() or None,
        camera_name=str(row.get("camera_name") or "").strip(),
        description=description,
        onvif_device_url=str(row.get("onvif_device_url") or "").strip() or None,
        snapshot_url=str(row.get("snapshot_url") or "").strip() or None,
        stream_url=str(row.get("stream_url") or "").strip() or None,
        notes=description,
        is_active=bool(row.get("is_active")),
        has_credentials=bool(str(row.get("username") or "").strip() or str(row.get("password") or "").strip()),
        created_at=str(row.get("created_at") or "").strip() or None,
        updated_at=str(row.get("updated_at") or "").strip() or None,
    )


def _goods_item_response_from_row(row: dict[str, Any]) -> GoodsItemResponse:
    return GoodsItemResponse(
        id=int(row["id"]),
        category=str(row.get("category") or "").strip().upper(),  # type: ignore[arg-type]
        goods_name=str(row.get("goods_name") or "").strip(),
        description=str(row.get("description") or "").strip() or None,
        quantity=int(row.get("quantity") or 0),
        size_group=str(row.get("size_group") or "GOODS").strip().upper(),  # type: ignore[arg-type]
        storage_slot_id=int(row["storage_slot_id"]) if row.get("storage_slot_id") not in (None, "") else None,
        status=str(row.get("status") or "ACTIVE").strip().upper(),  # type: ignore[arg-type]
        domain_code=str(row.get("domain_code") or "").strip().upper() or None,  # type: ignore[arg-type]
        memory_note=str(row.get("memory_note") or "").strip() or None,
        image_urls=[str(url or "").strip() for url in row.get("image_urls") or [] if str(url or "").strip()],
        primary_image_url=str(row.get("primary_image_url") or "").strip() or None,
        poster_storage_spec=str(row.get("poster_storage_spec") or "").strip() or None,
        tshirt_size=str(row.get("tshirt_size") or "").strip() or None,
        cup_material=str(row.get("cup_material") or "").strip() or None,
        hat_size=str(row.get("hat_size") or "").strip() or None,
        slot_code=str(row.get("slot_code") or "").strip() or None,
        slot_display_name=str(row.get("slot_display_name") or "").strip() or None,
        album_master_mappings=[
            GoodsItemAlbumMasterMapping(
                album_master_id=int(mapping["album_master_id"]),
                title=str(mapping.get("title") or "").strip(),
                artist_or_brand=str(mapping.get("artist_or_brand") or "").strip() or None,
            )
            for mapping in row.get("album_master_mappings") or []
        ],
        artist_mappings=[str(name or "").strip() for name in row.get("artist_mappings") or [] if str(name or "").strip()],
        label_mappings=[str(name or "").strip() for name in row.get("label_mappings") or [] if str(name or "").strip()],
        collectible_relations=[
            GoodsItemCollectibleRelation(
                relation_type=str(relation.get("relation_type") or "").strip().upper(),  # type: ignore[arg-type]
                direction="OUTGOING",
                linked_goods_item_id=int(relation["linked_goods_item_id"]),
                linked_goods_name=str(relation.get("linked_goods_name") or "").strip(),
                linked_category=str(relation.get("linked_category") or "").strip().upper() or None,  # type: ignore[arg-type]
                note=str(relation.get("note") or "").strip() or None,
                display_order=int(relation.get("display_order") or 0),
            )
            for relation in row.get("collectible_relations") or []
        ],
        collectible_relation_count=int(row.get("collectible_relation_count") or 0),
        relation_badges=[str(relation_type or "").strip().upper() for relation_type in row.get("relation_badges") or [] if str(relation_type or "").strip()],
        collectible_relation_preview=[
            GoodsItemCollectibleRelation(
                relation_type=str(relation.get("relation_type") or "").strip().upper(),  # type: ignore[arg-type]
                direction="OUTGOING",
                linked_goods_item_id=int(relation["linked_goods_item_id"]),
                linked_goods_name=str(relation.get("linked_goods_name") or "").strip(),
                linked_category=str(relation.get("linked_category") or "").strip().upper() or None,  # type: ignore[arg-type]
                note=str(relation.get("note") or "").strip() or None,
                display_order=int(relation.get("display_order") or 0),
            )
            for relation in row.get("collectible_relation_preview") or []
        ],
        created_at=str(row.get("created_at") or "").strip(),
        updated_at=str(row.get("updated_at") or "").strip(),
    )


def _camera_http_url_or_none(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = urlparse(raw)
    except Exception:
        return None
    if parsed.scheme.lower() not in {"http", "https"}:
        return None
    if not parsed.netloc:
        return None
    return raw


def _camera_rtsp_url_or_none(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = urlparse(raw)
    except Exception:
        return None
    if parsed.scheme.lower() not in {"rtsp", "rtsps"}:
        return None
    if not parsed.netloc:
        return None
    return raw


def _camera_stream_url_with_credentials(stream_url: str, *, username: str | None, password: str | None) -> str:
    parsed = urlparse(str(stream_url or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return str(stream_url or "").strip()
    if parsed.username or not username:
        return parsed.geturl()
    safe_username = quote(str(username), safe="")
    safe_password = quote(str(password or ""), safe="")
    auth_part = safe_username if safe_password == "" else f"{safe_username}:{safe_password}"
    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = auth_part + "@"
    if host:
        netloc += host
    if parsed.port:
        netloc += f":{parsed.port}"
    return parsed._replace(netloc=netloc).geturl()


def _camera_snapshot_bytes_from_stream(stream_url: str, *, username: str | None, password: str | None) -> bytes:
    ffmpeg_bin = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
    resolved_url = _camera_stream_url_with_credentials(stream_url, username=username, password=password)
    proc = subprocess.run(
        [
            ffmpeg_bin,
            "-v",
            "error",
            "-rtsp_transport",
            "tcp",
            "-i",
            resolved_url,
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "-",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=15,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout:
        stderr_text = proc.stderr.decode("utf-8", errors="ignore").strip()
        raise RuntimeError(stderr_text or "ffmpeg snapshot capture failed")
    return proc.stdout


def _xml_local_name(tag: str) -> str:
    raw = str(tag or "")
    return raw.split("}", 1)[-1] if "}" in raw else raw


def _onvif_wsse_security_header(username: str, password: str) -> str:
    nonce_bytes = secrets.token_bytes(16)
    created = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    digest = base64.b64encode(hashlib.sha1(nonce_bytes + created.encode("utf-8") + password.encode("utf-8")).digest()).decode("ascii")
    nonce_b64 = base64.b64encode(nonce_bytes).decode("ascii")
    return f"""
<wsse:Security soap:mustUnderstand="1"
 xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
 xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
  <wsse:UsernameToken>
    <wsse:Username>{username}</wsse:Username>
    <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest">{digest}</wsse:Password>
    <wsse:Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">{nonce_b64}</wsse:Nonce>
    <wsu:Created>{created}</wsu:Created>
  </wsse:UsernameToken>
</wsse:Security>
""".strip()


def _onvif_soap_request(
    service_url: str,
    body_xml: str,
    *,
    username: str | None,
    password: str | None,
    timeout: float = 8.0,
) -> ET.Element:
    service = _camera_http_url_or_none(service_url)
    if service is None:
        raise ValueError("유효한 ONVIF 장치 URL이 아닙니다.")
    header_parts = [f"<wsa:MessageID>uuid:{uuid4()}</wsa:MessageID>"]
    if username:
        header_parts.append(_onvif_wsse_security_header(username, password or ""))
    envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
 xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing">
  <soap:Header>
    {''.join(header_parts)}
  </soap:Header>
  <soap:Body>
    {body_xml}
  </soap:Body>
</soap:Envelope>
""".strip()
    auth = (username, password or "") if username else None
    with httpx.Client(timeout=timeout, follow_redirects=True, verify=False) as client:
        response = client.post(
            service,
            content=envelope.encode("utf-8"),
            headers={"Content-Type": "application/soap+xml; charset=utf-8"},
            auth=auth,
        )
    response.raise_for_status()
    return ET.fromstring(response.content)


def _find_first_descendant_text(element: ET.Element, local_name: str) -> str | None:
    target = str(local_name or "").strip()
    if not target:
        return None
    for node in element.iter():
        if _xml_local_name(node.tag) == target:
            value = str(node.text or "").strip()
            if value:
                return value
    return None


def _find_media_service_xaddr(root: ET.Element) -> str | None:
    for node in root.iter():
        if _xml_local_name(node.tag) in {"Media", "Media2"}:
            xaddr = _find_first_descendant_text(node, "XAddr")
            if _camera_http_url_or_none(xaddr):
                return xaddr
    for service in root.iter():
        if _xml_local_name(service.tag) != "Service":
            continue
        namespace_text = _find_first_descendant_text(service, "Namespace") or ""
        if "media/wsdl" not in namespace_text.lower():
            continue
        xaddr = _find_first_descendant_text(service, "XAddr")
        if _camera_http_url_or_none(xaddr):
            return xaddr
    return None


def _test_onvif_camera_connection(
    device_service_url: str,
    *,
    username: str | None,
    password: str | None,
) -> dict[str, Any]:
    device_root = _onvif_soap_request(
        device_service_url,
        '<tds:GetCapabilities xmlns:tds="http://www.onvif.org/ver10/device/wsdl"><tds:Category>All</tds:Category></tds:GetCapabilities>',
        username=username,
        password=password,
    )
    media_service_url = _find_media_service_xaddr(device_root)
    if not media_service_url:
        services_root = _onvif_soap_request(
            device_service_url,
            '<tds:GetServices xmlns:tds="http://www.onvif.org/ver10/device/wsdl"><tds:IncludeCapability>false</tds:IncludeCapability></tds:GetServices>',
            username=username,
            password=password,
        )
        media_service_url = _find_media_service_xaddr(services_root)

    manufacturer = None
    model = None
    firmware_version = None
    serial_number = None
    hardware_id = None
    try:
        info_root = _onvif_soap_request(
            device_service_url,
            '<tds:GetDeviceInformation xmlns:tds="http://www.onvif.org/ver10/device/wsdl" />',
            username=username,
            password=password,
        )
        manufacturer = _find_first_descendant_text(info_root, "Manufacturer")
        model = _find_first_descendant_text(info_root, "Model")
        firmware_version = _find_first_descendant_text(info_root, "FirmwareVersion")
        serial_number = _find_first_descendant_text(info_root, "SerialNumber")
        hardware_id = _find_first_descendant_text(info_root, "HardwareId")
    except httpx.HTTPStatusError:
        pass

    profile_token = None
    snapshot_url = None
    stream_url = None

    if media_service_url:
        try:
            profiles_root = _onvif_soap_request(
                media_service_url,
                '<trt:GetProfiles xmlns:trt="http://www.onvif.org/ver10/media/wsdl" />',
                username=username,
                password=password,
            )
            for node in profiles_root.iter():
                if _xml_local_name(node.tag) == "Profiles":
                    profile_token = str(node.attrib.get("token") or node.attrib.get("{http://www.onvif.org/ver10/media/wsdl}token") or "").strip() or None
                    if profile_token:
                        break
        except httpx.HTTPStatusError:
            profile_token = None
        if profile_token:
            try:
                snapshot_root = _onvif_soap_request(
                    media_service_url,
                    f'<trt:GetSnapshotUri xmlns:trt="http://www.onvif.org/ver10/media/wsdl"><trt:ProfileToken>{profile_token}</trt:ProfileToken></trt:GetSnapshotUri>',
                    username=username,
                    password=password,
                )
                snapshot_url = _find_first_descendant_text(snapshot_root, "Uri")
            except Exception:
                snapshot_url = None
            try:
                stream_root = _onvif_soap_request(
                    media_service_url,
                    (
                        '<trt:GetStreamUri xmlns:trt="http://www.onvif.org/ver10/media/wsdl" xmlns:tt="http://www.onvif.org/ver10/schema">'
                        '<trt:StreamSetup><tt:Stream>RTP-Unicast</tt:Stream><tt:Transport><tt:Protocol>RTSP</tt:Protocol></tt:Transport></trt:StreamSetup>'
                        f'<trt:ProfileToken>{profile_token}</trt:ProfileToken>'
                        '</trt:GetStreamUri>'
                    ),
                    username=username,
                    password=password,
                )
                stream_url = _find_first_descendant_text(stream_root, "Uri")
            except Exception:
                stream_url = None

    return {
        "device_service_url": _camera_http_url_or_none(device_service_url) or str(device_service_url).strip(),
        "media_service_url": _camera_http_url_or_none(media_service_url),
        "profile_token": profile_token,
        "snapshot_url": _camera_http_url_or_none(snapshot_url) or snapshot_url,
        "stream_url": str(stream_url or "").strip() or None,
        "manufacturer": manufacturer,
        "model": model,
        "firmware_version": firmware_version,
        "serial_number": serial_number,
        "hardware_id": hardware_id,
    }


def _discover_onvif_devices(timeout_seconds: float = 2.5) -> list[dict[str, Any]]:
    timeout = max(0.5, min(10.0, float(timeout_seconds or 2.5)))
    probe = f"""<?xml version="1.0" encoding="UTF-8"?>
<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"
            xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"
            xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"
            xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
  <e:Header>
    <w:MessageID>uuid:{uuid4()}</w:MessageID>
    <w:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>
    <w:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>
  </e:Header>
  <e:Body>
    <d:Probe>
      <d:Types>dn:NetworkVideoTransmitter</d:Types>
    </d:Probe>
  </e:Body>
</e:Envelope>
""".strip()
    namespaces = {
        "a": "http://schemas.xmlsoap.org/ws/2004/08/addressing",
        "d": "http://schemas.xmlsoap.org/ws/2005/04/discovery",
    }
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.settimeout(0.35)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except OSError:
        pass
    try:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    except OSError:
        pass
    try:
        try:
            sock.sendto(probe.encode("utf-8"), ("239.255.255.250", 3702))
        except OSError:
            return []
        deadline = time.time() + timeout
        found: dict[str, dict[str, Any]] = {}
        while time.time() < deadline:
            try:
                packet, addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                root = ET.fromstring(packet)
            except ET.ParseError:
                continue
            for match in root.findall(".//d:ProbeMatch", namespaces):
                endpoint_reference = str(match.findtext("./a:EndpointReference/a:Address", default="", namespaces=namespaces) or "").strip() or None
                raw_xaddrs = str(match.findtext("./d:XAddrs", default="", namespaces=namespaces) or "").strip()
                xaddr_candidates = [value.strip() for value in raw_xaddrs.split() if _camera_http_url_or_none(value.strip())]
                onvif_device_url = xaddr_candidates[0] if xaddr_candidates else None
                scopes = [value.strip() for value in str(match.findtext("./d:Scopes", default="", namespaces=namespaces) or "").split() if value.strip()]
                types = [value.strip() for value in str(match.findtext("./d:Types", default="", namespaces=namespaces) or "").split() if value.strip()]
                host = None
                if onvif_device_url:
                    try:
                        host = urlparse(onvif_device_url).hostname
                    except Exception:
                        host = None
                if not host:
                    host = str(addr[0] or "").strip() or None
                camera_name = None
                for scope in scopes:
                    if "/name/" in scope:
                        camera_name = unquote(scope.split("/name/", 1)[1]).replace("_", " ").strip() or None
                        break
                key = str(onvif_device_url or endpoint_reference or host or uuid4())
                found[key] = {
                    "endpoint_reference": endpoint_reference,
                    "camera_name": camera_name,
                    "host": host,
                    "onvif_device_url": onvif_device_url,
                    "scopes": scopes,
                    "types": types,
                }
    finally:
        sock.close()
    return sorted(
        found.values(),
        key=lambda row: (
            str(row.get("host") or ""),
            str(row.get("camera_name") or ""),
            str(row.get("onvif_device_url") or ""),
        ),
    )


def _purchase_import_rows_for_save(
    items: list[PurchaseImportPreviewItem],
    *,
    vendor_code: str,
    email_from: str | None,
) -> list[dict[str, Any]]:
    seller_name = _clean_text(email_from) or vendor_code
    rows: list[dict[str, Any]] = []
    for item in items:
        raw_payload = dict(item.raw_payload or {})
        raw_payload["row_no"] = max(1, int(item.row_no or 1))
        item_url = _purchase_normalize_item_url(raw_payload.get("item_url"))
        rows.append(
            {
                "artist_name": _clean_text(item.artist_name),
                "item_name": str(item.item_name or "").strip(),
                "media_format": _purchase_import_media_format_or_default(vendor_code, item.media_format),
                "quantity": max(1, int(item.quantity or 1)),
                "unit_price": float(item.unit_price) if item.unit_price is not None else None,
                "line_total": float(item.line_total) if item.line_total is not None else None,
                "currency_code": str(item.currency_code or "KRW").strip().upper() or "KRW",
                "purchase_date": _normalize_purchase_date(item.purchase_date),
                "seller_name": _clean_text(raw_payload.get("seller_name")) or seller_name,
                "item_url": item_url,
                "image_url": _clean_text(raw_payload.get("image_url")),
                "raw_line": _clean_text(item.raw_line),
                "raw_payload": raw_payload,
            }
        )
    return rows


def _purchase_queue_base_context(row: dict[str, Any]) -> tuple[str, str, str, str]:
    media_format = _purchase_import_media_format_or_default(row.get("vendor_code"), row.get("media_format")) or "CD"
    category = _infer_music_category_from_format(media_format)
    size_group = _default_size_group_for_category(category)
    seller_name = _clean_text(row.get("seller_name")) or _clean_text(row.get("vendor_code")) or "PURCHASE_IMPORT"
    return media_format, category, size_group, seller_name


def _purchase_queue_memory_note(row: dict[str, Any], candidate: dict[str, Any] | None = None) -> str:
    seller_name = _clean_text(row.get("seller_name")) or _clean_text(row.get("vendor_code")) or "PURCHASE_IMPORT"
    memory_bits = [f"구매 수입 큐 #{int(row['id'])}"]
    email_subject = _clean_text(row.get("email_subject"))
    source_ref = _clean_text(row.get("source_ref"))
    if email_subject:
        memory_bits.append(f"메일 제목: {email_subject}")
    if source_ref:
        memory_bits.append(f"메일 ID: {source_ref}")
    if isinstance(candidate, dict):
        source = str(candidate.get("source") or "").strip().upper()
        external_id = str(candidate.get("external_id") or "").strip()
        if source and external_id:
            memory_bits.append(f"메타 후보: {source}#{external_id}")
        candidate_source_notes = _clean_text(candidate.get("source_notes"))
        if candidate_source_notes:
            memory_bits.append(f"소스 메모: {candidate_source_notes}")
    memory_note = " | ".join(memory_bits)
    return memory_note


def _purchase_queue_candidate_query(
    row: dict[str, Any],
    *,
    artist_name: str | None = None,
    item_name: str | None = None,
    query: str | None = None,
) -> str:
    override_query = _clean_text(query)
    if override_query:
        return override_query
    raw_payload = dict(row.get("raw_payload") or {})
    fallback_artist_name = _clean_text(raw_payload.get("parsed_search_artist_name")) or _clean_text(row.get("artist_name"))
    fallback_item_name = _clean_text(raw_payload.get("parsed_search_item_name")) or _clean_text(row.get("item_name"))
    parts = [
        _clean_text(artist_name) if artist_name is not None else fallback_artist_name,
        _clean_text(item_name) if item_name is not None else fallback_item_name,
    ]
    return " ".join(part for part in parts if part).strip()


def _build_owned_item_from_purchase_queue_row(
    row: dict[str, Any],
    candidate: dict[str, Any] | None = None,
) -> OwnedItemCreate:
    media_format, fallback_category, fallback_size_group, seller_name = _purchase_queue_base_context(row)
    raw_payload = dict(row.get("raw_payload") or {})
    candidate_source = str((candidate or {}).get("source") or "").strip().upper()
    candidate_external_id = str((candidate or {}).get("external_id") or "").strip()
    candidate_format = str((candidate or {}).get("format_name") or "").strip().upper()
    category = fallback_category
    if category == "DIGITAL" and candidate_format in MUSIC_CATEGORIES:
        category = candidate_format
    size_group = _default_size_group_for_category(category)
    ebay_artist_name: str | None = None
    ebay_item_name: str | None = None
    if str(row.get("vendor_code") or "").strip().upper() == "EBAY":
        ebay_artist_name, ebay_item_name, _, _ = _parse_ebay_purchase_title(_purchase_ebay_parse_source_text(row, raw_payload))
    artist_name = _clean_text((candidate or {}).get("artist_or_brand")) or _clean_text(row.get("artist_name")) or ebay_artist_name
    item_name = _clean_text((candidate or {}).get("title")) or ebay_item_name or _clean_text(row.get("item_name")) or category
    cover_condition = _clean_text((candidate or {}).get("cover_condition")) or _clean_text(raw_payload.get("parsed_cover_condition"))
    disc_condition = _clean_text((candidate or {}).get("disc_condition")) or _clean_text(raw_payload.get("parsed_disc_condition"))
    mapped_domain = _normalize_domain_code((candidate or {}).get("domain_code"))
    release_type = str((candidate or {}).get("release_type") or "").strip().upper() or None
    if release_type not in RELEASE_TYPES:
        release_type = None
    collector = _candidate_collector_base(candidate or {})
    # Aladin 후보에 track_items가 없으면 ItemLookUp API로 수록곡 보강
    if candidate_source == "ALADIN" and candidate_external_id and not collector.get("track_items"):
        try:
            fetched_tracks = fetch_aladin_track_items(candidate_external_id)
            if fetched_tracks:
                collector["track_items"] = fetched_tracks
        except Exception:
            pass
    return OwnedItemCreate(
        category=category,  # type: ignore[arg-type]
        size_group=size_group,  # type: ignore[arg-type]
        preferred_storage_size_group=size_group,  # type: ignore[arg-type]
        auto_location_recommendation=False,
        quantity=max(1, int(row.get("quantity") or 1)),
        status="IN_COLLECTION",
        source_code=candidate_source or None,
        source_external_id=candidate_external_id or None,
        domain_code=mapped_domain,
        release_type=release_type,  # type: ignore[arg-type]
        item_name_override=item_name,
        acquisition_date=_normalize_purchase_date(row.get("purchase_date")),
        purchase_price=float(row["unit_price"]) if row.get("unit_price") is not None else None,
        currency_code=str(row.get("currency_code") or "KRW").strip().upper() or "KRW",
        purchase_source=seller_name,
        memory_note=_purchase_queue_memory_note(row, candidate),
        music_detail=(
            MusicDetailCreate(
                format_name=category,  # type: ignore[arg-type]
                artist_or_brand=artist_name,
                released_date=_clean_text((candidate or {}).get("released_date")),
                barcode=_clean_text((candidate or {}).get("barcode")),
                label_name=_clean_text((candidate or {}).get("label_name")),
                catalog_no=_discogs_catalog_no((candidate or {}).get("catalog_no")),
                media_type=_clean_text((candidate or {}).get("media_type")),
                cover_condition=cover_condition or None,
                disc_condition=disc_condition or None,
                sleeve_condition=cover_condition or None,
                media_condition=disc_condition or None,
                genres=_clean_string_list((candidate or {}).get("genres")),
                styles=_clean_string_list((candidate or {}).get("styles")),
                cover_image_url=_clean_text((candidate or {}).get("cover_image_url")),
                track_list=_clean_track_list((candidate or {}).get("track_list")),
                disc_count=_normalize_positive_int((candidate or {}).get("disc_count")),
                speed_rpm=_normalize_positive_int((candidate or {}).get("speed_rpm")),
                source_notes=collector.get("source_notes"),
                credits=collector.get("credits"),
                identifier_items=collector.get("identifier_items"),
                image_items=collector.get("image_items"),
                company_items=collector.get("company_items"),
                series=collector.get("series"),
                format_items=collector.get("format_items"),
                track_items=collector.get("track_items"),
                label_items=collector.get("label_items"),
                runout_matrix=collector.get("runout_matrix"),
                pressing_country=collector.get("pressing_country"),
            )
            if category in MUSIC_CATEGORIES
            else None
        ),
    )


def _purchase_import_duplicate_create_response(
    *,
    queue_id: int,
    row: dict[str, Any],
    existing_owned_item_id: int,
) -> PurchaseImportCreateResponse:
    existing_owned_item = db.get_owned_item(existing_owned_item_id)
    if existing_owned_item is None:
        raise HTTPException(status_code=404, detail="linked owned item not found")
    updated = db.update_purchase_import_row(
        queue_id,
        queue_status="CREATED",
        linked_owned_item_id=existing_owned_item_id,
    )
    if updated is None:
        raise HTTPException(status_code=500, detail="purchase import row update failed")
    category = str(existing_owned_item.get("category") or row.get("media_format") or "OTHER").strip().upper() or "OTHER"
    return PurchaseImportCreateResponse(
        queue_item=_purchase_queue_item_from_row(updated),
        owned_item_id=existing_owned_item_id,
        label_id=_build_label_id(category, existing_owned_item_id),
        linked_album_master_id=(
            int(existing_owned_item["linked_album_master_id"])
            if existing_owned_item.get("linked_album_master_id") is not None
            else None
        ),
        notices=["동일한 주문 상품이 이미 등록되어 기존 보유상품에 연결했습니다. 신규 등록은 생략했습니다."],
    )


# Purchase-imports routes (preview/save/webhook/list/candidates/enrich/
# create/ignore) live in app/api/purchase_imports.py, wired at the bottom
# of this module via include_router. The parsing/normalising helpers stay
# here because they're shared with non-route code paths.


# Admin auth-account routes (list/create/update/delete + legacy mirrors)
# live in app/api/admin_auth_accounts.py, wired below via include_router.








def _home_assistant_api_base_url() -> str:
    raw = str(settings.home_assistant_base_url or "").strip().rstrip("/")
    if raw.endswith("/api"):
        return raw
    return f"{raw}/api" if raw else ""


def _fetch_home_assistant_state(entity_id: str) -> dict[str, Any] | None:
    token = str(settings.home_assistant_token or "").strip()
    api_base = _home_assistant_api_base_url()
    entity = str(entity_id or "").strip()
    if not (token and api_base and entity):
        return None
    url = f"{api_base}/states/{quote(entity, safe='._-')}"
    response = httpx.get(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        timeout=5.0,
        follow_redirects=True,
    )
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else None


def _coerce_home_assistant_number(value: Any) -> float | None:
    raw = str(value or "").strip().lower()
    if raw in {"", "unknown", "unavailable", "none"}:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _office_climate_comfort_label(temperature_c: float | None, humidity_percent: float | None) -> str | None:
    if humidity_percent is not None:
        if humidity_percent < 40:
            return "건조"
        if humidity_percent > 65:
            return "습함"
    if temperature_c is not None:
        if temperature_c < 18:
            return "서늘"
        if temperature_c > 27:
            return "따뜻함"
    if temperature_c is None and humidity_percent is None:
        return None
    return "쾌적"


def _load_operator_office_climate() -> dict[str, Any]:
    temperature_state = _fetch_home_assistant_state(settings.office_climate_temperature_entity_id)
    humidity_state = _fetch_home_assistant_state(settings.office_climate_humidity_entity_id)
    temperature_c = _coerce_home_assistant_number(temperature_state.get("state") if temperature_state else None)
    humidity_percent = _coerce_home_assistant_number(humidity_state.get("state") if humidity_state else None)
    updated_candidates = [
        str(temperature_state.get("last_updated") or temperature_state.get("last_changed") or "").strip()
        if temperature_state else "",
        str(humidity_state.get("last_updated") or humidity_state.get("last_changed") or "").strip()
        if humidity_state else "",
    ]
    updated_at = max([item for item in updated_candidates if item], default=None)
    comfort_label = _office_climate_comfort_label(temperature_c, humidity_percent)
    available = temperature_c is not None or humidity_percent is not None
    return {
        "available": available,
        "source": "home_assistant",
        "location_label": "상주 사무실",
        "description": "온/습도계",
        "temperature_c": temperature_c,
        "humidity_percent": humidity_percent,
        "comfort_label": comfort_label,
        "updated_at": updated_at,
    }


def _load_operator_seoul_weather() -> dict[str, Any]:
    response = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": 37.5665,
            "longitude": 126.9780,
            "current": "temperature_2m,relative_humidity_2m,is_day,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min",
            "forecast_days": 1,
            "timezone": "Asia/Seoul",
        },
        timeout=10.0,
        follow_redirects=True,
    )
    response.raise_for_status()
    payload = response.json() if response.content else {}
    current = payload.get("current") if isinstance(payload, dict) and isinstance(payload.get("current"), dict) else {}
    daily = payload.get("daily") if isinstance(payload, dict) and isinstance(payload.get("daily"), dict) else {}
    temperature_c = current.get("temperature_2m")
    humidity_percent = current.get("relative_humidity_2m")
    weather_code = current.get("weather_code")
    is_day = current.get("is_day")
    daily_max = daily.get("temperature_2m_max") if isinstance(daily.get("temperature_2m_max"), list) else []
    daily_min = daily.get("temperature_2m_min") if isinstance(daily.get("temperature_2m_min"), list) else []
    temperature_high_c = daily_max[0] if daily_max else None
    temperature_low_c = daily_min[0] if daily_min else None
    updated_at = str(current.get("time") or "").strip() or None
    available = temperature_c is not None
    return {
        "available": available,
        "source": "seoul_weather",
        "location_label": "서울",
        "description": "",
        "temperature_c": float(temperature_c) if temperature_c is not None else None,
        "humidity_percent": float(humidity_percent) if humidity_percent is not None else None,
        "comfort_label": None,
        "temperature_high_c": float(temperature_high_c) if temperature_high_c is not None else None,
        "temperature_low_c": float(temperature_low_c) if temperature_low_c is not None else None,
        "weather_code": int(weather_code) if weather_code is not None else None,
        "is_day": bool(is_day) if is_day is not None else None,
        "updated_at": updated_at,
    }





def _wmo_weather_code_to_desc(code: int | None) -> str | None:
    if code is None:
        return None
    if code == 0:
        return "맑음"
    elif code in {1, 2, 3}:
        return "구름 조금/흐림"
    elif code in {45, 48}:
        return "안개"
    elif code in {51, 53, 55, 56, 57}:
        return "이슬비"
    elif code in {61, 63, 65, 66, 67, 80, 81, 82}:
        return "비"
    elif code in {71, 73, 75, 77, 85, 86}:
        return "눈"
    elif code in {95, 96, 99}:
        return "뇌우"
    return "기타"


def _map_to_customer_track_request_item(row: dict[str, Any]) -> CustomerTrackRequestItem:
    category_raw = str(row.get("category") or "").strip()
    return CustomerTrackRequestItem(
        id=int(row["id"]),
        requested_track=str(row.get("requested_track") or ""),
        matched_track_title=row.get("matched_track_title"),
        matched_track_no=row.get("matched_track_no"),
        owned_item_id=row.get("owned_item_id"),
        label_id=row.get("label_id"),
        category=category_raw if category_raw else None,
        item_title=row.get("item_title"),
        artist_or_brand=row.get("artist_or_brand"),
        cover_image_url=row.get("cover_image_url"),
        status=str(row.get("status") or "REQUESTED"),
        customer_note=row.get("customer_note"),
        response_note=row.get("response_note"),
        requested_by=row.get("requested_by"),
        handled_by=row.get("handled_by"),
        created_at=str(row.get("created_at") or ""),
        updated_at=str(row.get("updated_at") or ""),
        handled_at=row.get("handled_at"),
        current_slot_code_snapshot=row.get("current_slot_code_snapshot"),
        current_slot_display_snapshot=row.get("current_slot_display_snapshot"),
        previous_slot_code_snapshot=row.get("previous_slot_code_snapshot"),
        previous_slot_display_snapshot=row.get("previous_slot_display_snapshot"),
        current_live_slot_code=row.get("current_live_slot_code"),
        current_live_slot_display_name=row.get("current_live_slot_display_name"),
        weather_temp_c=row.get("weather_temp_c"),
        weather_description=row.get("weather_description"),
        weather_code=row.get("weather_code"),
        season=row.get("season"),
        playback_deck=row.get("playback_deck"),
        played_at=row.get("played_at"),
        returned_at=row.get("returned_at"),
    )






















def _item_meta_fields(row: dict[str, Any]) -> dict[str, Any]:
    """로그/응답 표시용 식별 메타 (display_name, artist_or_brand, catalog_no)."""
    return {
        "display_name": _clean_text(row.get("display_name")),
        "artist_or_brand": _clean_text(row.get("artist_or_brand")),
        "catalog_no": _clean_text(row.get("catalog_no")),
    }


def _sync_one_item(owned_item_id: int) -> MetadataSyncItemResult:
    """단건 메타 동기화 – 동기 실행, 결과를 즉시 반환.

    기존 _run_metadata_sync 루프의 로직을 재사용하되 배치 관련 상태는 건드리지 않음.
    """
    from app.services.providers import get_source_release_snapshot, _try_discogs_for_barcode, _token_similarity

    candidates = db.list_metadata_sync_candidates(
        source_code=None,
        only_missing=False,   # 단건이므로 only_missing 무관하게 전체 필드 비교
        limit=1,
        offset=0,
        owned_item_ids=[owned_item_id],
    )
    if not candidates:
        return MetadataSyncItemResult(
            owned_item_id=owned_item_id,
            source_code="-",
            source_external_id="-",
            status="FAILED",
            reason="item not found or not eligible for sync",
        )

    row = candidates[0]
    source_code = str(row.get("source_code") or "").strip().upper()
    source_external_id = str(row.get("source_external_id") or "").strip()

    if not source_code or not source_external_id:
        return MetadataSyncItemResult(
            owned_item_id=owned_item_id,
            source_code=source_code or "-",
            source_external_id=source_external_id or "-",
            status="FAILED",
            reason="missing source info",
            **_item_meta_fields(row),
        )

    if source_code not in {"DISCOGS", "MANIADB", "ALADIN"}:
        return MetadataSyncItemResult(
            owned_item_id=owned_item_id,
            source_code=source_code,
            source_external_id=source_external_id,
            status="FAILED",
            reason=f"source '{source_code}' not supported for snapshot sync",
            **_item_meta_fields(row),
        )

    snapshot = get_source_release_snapshot(source=source_code, external_id=source_external_id)
    if not snapshot:
        return MetadataSyncItemResult(
            owned_item_id=owned_item_id,
            source_code=source_code,
            source_external_id=source_external_id,
            status="FAILED",
            reason="source snapshot not found",
            **_item_meta_fields(row),
        )

    # Discogs 보강 – 1차: 바코드(EAN/UPC 체크섬), 2차: 카탈로그넘버 fallback
    discogs_supplement = None
    if source_code != "DISCOGS":
        from app.services.providers import (
            _try_discogs_for_barcode, _try_discogs_for_catalog_no,
            _token_similarity, _validate_barcode_checksum,
        )
        barcode = str(row.get("barcode") or "").strip()
        barcode_digits = barcode.replace(" ", "").replace("-", "")
        # 1차: 바코드 (EAN-13/UPC-A 체크섬, 880 포함)
        if _validate_barcode_checksum(barcode_digits):
            discogs_supplement = _try_discogs_for_barcode(barcode_digits)
            if discogs_supplement:
                orig_text = f"{row.get('artist_or_brand') or ''} {row.get('master_title') or row.get('display_name') or ''}".strip()
                disc_text = f"{discogs_supplement.get('artist_or_brand') or ''} {discogs_supplement.get('title') or ''}".strip()
                sim = _token_similarity(orig_text, disc_text) if orig_text and disc_text else 0.0
                # 유사도 + 미디어 타입 검증 (바코드 경로는 포맷 일치 필수)
                orig_fmt = str(row.get("format_name") or "").upper()
                disc_fmt = str(discogs_supplement.get("format_name") or "").upper()
                fmt_ok = (not orig_fmt or not disc_fmt or orig_fmt == disc_fmt)
                if sim < 0.85 or not fmt_ok:
                    discogs_supplement = None
        # 2차: 카탈로그넘버 fallback (바코드 없거나 검증 실패 시)
        if discogs_supplement is None:
            catalog_no = str(row.get("catalog_no") or "").strip()
            if catalog_no:
                discogs_supplement = _try_discogs_for_catalog_no(
                    catalog_no=catalog_no,
                    artist=str(row.get("artist_or_brand") or ""),
                    title=str(row.get("master_title") or row.get("display_name") or ""),
                    format_name=str(row.get("format_name") or "") or None,
                    pressing_country=str(row.get("pressing_country") or "") or None,
                )
        if discogs_supplement:
            _DISCOGS_FIELDS = {
                "disc_count", "speed_rpm", "has_obi",
                "runout_matrix", "pressing_country", "source_notes",
                "credits", "identifier_items", "image_items",
                "company_items", "series", "format_items",
                "track_items", "label_items", "genres", "styles",
            }
            for field in _DISCOGS_FIELDS:
                val = discogs_supplement.get(field)
                has_val = bool(val) if isinstance(val, (list, dict)) else val is not None
                if has_val:
                    snapshot[field] = val

    music_detail, updated_fields = _build_music_detail_for_sync(
        candidate=row,
        snapshot=snapshot,
        only_missing=False,
    )

    if not updated_fields:
        return MetadataSyncItemResult(
            owned_item_id=owned_item_id,
            source_code=source_code,
            source_external_id=source_external_id,
            status="SKIPPED",
            reason="no fields to update",
            **_item_meta_fields(row),
        )

    # 메모 기록
    release_info = ""
    if source_code == "DISCOGS":
        release_info = f"[Discogs: {source_external_id}] "
    elif discogs_supplement:
        discogs_ext = discogs_supplement.get("external_id")
        if discogs_ext:
            release_info = f"[Discogs Barcode Match: {discogs_ext}] "
    note_append = f"[메타동기화] {release_info}업데이트: {', '.join(updated_fields)}"

    db.upsert_music_detail(owned_item_id=owned_item_id, music_detail=music_detail, note_append=note_append)
    linked_master_id = int(row.get("linked_album_master_id") or 0)
    if linked_master_id > 0:
        db.update_album_master_genres(
            album_master_id=linked_master_id,
            genres=music_detail.get("genres") or [],
            styles=music_detail.get("styles") or [],
        )

    # Trigger background image download for this item
    _trigger_sync_image_download(
        owned_item_id=owned_item_id,
        source_code=source_code,
        source_external_id=source_external_id,
        snapshot=snapshot,
    )

    return MetadataSyncItemResult(
        owned_item_id=owned_item_id,
        source_code=source_code,
        source_external_id=source_external_id,
        status="UPDATED",
        updated_fields=updated_fields,
        **_item_meta_fields(row),
    )




# ---------------------------------------------------------------------------
# ALADIN → Discogs 마스터 매칭 백필
# ---------------------------------------------------------------------------

def _run_aladin_discogs_backfill(*, dry_run: bool = False, sleep_sec: float = 2.0) -> dict[str, Any]:
    """ALADIN owned_item 전체를 대상으로 Discogs 마스터 매칭 + 포맷 정보 업데이트."""
    global ALADIN_DISCOGS_BACKFILL_LAST_RESULT, ALADIN_DISCOGS_BACKFILL_LAST_ERROR

    acquired = ALADIN_DISCOGS_BACKFILL_LOCK.acquire(blocking=False)
    if not acquired:
        raise HTTPException(status_code=409, detail="aladin discogs backfill already running")

    started_at = _now_iso()
    stats: dict[str, Any] = {
        "started_at": started_at,
        "finished_at": None,
        "dry_run": dry_run,
        "scanned": 0,
        "no_crossref": 0,
        "master_created": 0,
        "master_linked": 0,
        "already_discogs": 0,
        "detail_updated": 0,
        "error": 0,
        "matched_items": [],
    }

    try:
        import time as _time

        with db.get_conn() as conn:
            rows = conn.execute(
                """
                SELECT oi.id, oi.source_external_id, oi.linked_album_master_id,
                       am.source_code AS master_source_code,
                       am.source_master_id AS master_source_id
                FROM owned_item oi
                LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
                WHERE oi.source_code = 'ALADIN'
                ORDER BY oi.id
                """
            ).fetchall()

        items = [dict(r) for r in rows]
        stats["scanned"] = 0  # will count per loop

        for row in items:
            owned_item_id = int(row["id"])
            source_ext = str(row["source_external_id"] or "").strip()
            current_master_id = row["linked_album_master_id"]
            current_master_source = str(row.get("master_source_code") or "").strip().upper()
            stats["scanned"] += 1

            try:
                snap = get_source_release_snapshot(source="ALADIN", external_id=source_ext)
                crossref: dict[str, Any] | None = (snap or {}).get("discogs_crossref")
                _time.sleep(sleep_sec)

                if not crossref:
                    stats["no_crossref"] += 1
                    continue

                d_ext = str(crossref.get("external_id") or "").strip()
                d_master_id = str(crossref.get("master_id") or "").strip()
                d_src_id = d_master_id or d_ext
                d_title = str(crossref.get("title") or "").strip() or f"ALADIN#{source_ext}"
                d_artist = str(crossref.get("artist_or_brand") or "").strip() or None
                d_year = crossref.get("master_release_year") or crossref.get("release_year")
                d_raw = crossref.get("raw") or {}
                d_domain = _infer_album_master_domain_code(
                    source_code="DISCOGS", title=d_title, artist_or_brand=d_artist, raw=d_raw
                )

                matched_entry: dict[str, Any] = {
                    "owned_item_id": owned_item_id,
                    "aladin_id": source_ext,
                    "discogs_release_id": d_ext,
                    "discogs_master_id": d_src_id,
                    "artist": d_artist,
                    "title": d_title,
                    "format": crossref.get("format_name"),
                    "barcode": crossref.get("barcode"),
                    "label": crossref.get("label_name"),
                    "album_master_id": None,
                    "action": None,
                }

                if current_master_source == "DISCOGS":
                    stats["already_discogs"] += 1
                    album_master_id = int(current_master_id)
                    matched_entry["album_master_id"] = album_master_id
                    matched_entry["action"] = "detail_only"
                else:
                    if not dry_run:
                        album_master_id = db.upsert_album_master(
                            source_code="DISCOGS",
                            source_master_id=d_src_id,
                            title=d_title,
                            artist_or_brand=d_artist,
                            domain_code=d_domain,
                            release_year=d_year,
                            raw=d_raw,
                        )
                        db.bind_album_master_members(
                            album_master_id=album_master_id,
                            owned_item_ids=[owned_item_id],
                            replace_existing=False,
                        )
                        db.set_owned_item_linked_album_master(
                            owned_item_id=owned_item_id, album_master_id=album_master_id
                        )
                    else:
                        album_master_id = -1
                    stats["master_created"] += 1
                    matched_entry["album_master_id"] = album_master_id
                    matched_entry["action"] = "dry_run" if dry_run else "created"

                music_detail_raw = {
                    "format_name": crossref.get("format_name"),
                    "artist_or_brand": d_artist,
                    "release_year": d_year,
                    "released_date": crossref.get("released_date"),
                    "barcode": crossref.get("barcode"),
                    "label_name": crossref.get("label_name"),
                    "catalog_no": crossref.get("catalog_no"),
                    "cover_image_url": crossref.get("cover_image_url"),
                    "track_list": crossref.get("track_list") or [],
                    "media_type": crossref.get("media_type") or crossref.get("format_name"),
                    "genres": crossref.get("genres") or [],
                    "styles": crossref.get("styles") or [],
                    "disc_count": crossref.get("disc_count"),
                    "speed_rpm": crossref.get("speed_rpm"),
                    "has_obi": crossref.get("has_obi"),
                    "runout_matrix": crossref.get("runout_matrix") or [],
                    "pressing_country": crossref.get("pressing_country"),
                    "source_notes": crossref.get("source_notes"),
                    "credits": crossref.get("credits") or [],
                    "identifier_items": crossref.get("identifier_items") or [],
                    "image_items": crossref.get("image_items") or [],
                    "company_items": crossref.get("company_items") or [],
                    "series": crossref.get("series") or [],
                    "format_items": crossref.get("format_items") or [],
                    "track_items": crossref.get("track_items") or [],
                    "label_items": crossref.get("label_items") or [],
                }
                music_detail_clean = {k: v for k, v in music_detail_raw.items() if v is not None}

                if not dry_run:
                    with _get_db_conn() as conn:
                        db._upsert_music_item_detail_in_conn(conn, owned_item_id, music_detail_clean)
                stats["detail_updated"] += 1
                stats["matched_items"].append(matched_entry)

            except Exception as exc:
                stats["error"] += 1
                logger.exception("aladin_discogs_backfill item %s error: %s", owned_item_id, exc)

        stats["finished_at"] = _now_iso()
        ALADIN_DISCOGS_BACKFILL_LAST_RESULT = stats
        ALADIN_DISCOGS_BACKFILL_LAST_ERROR = None
        return stats

    except HTTPException:
        raise
    except Exception as exc:
        ALADIN_DISCOGS_BACKFILL_LAST_ERROR = f"{_now_iso()} | {exc}"
        logger.exception("aladin_discogs_backfill failed: %s", exc)
        raise
    finally:
        ALADIN_DISCOGS_BACKFILL_LOCK.release()


def _aladin_discogs_backfill_thread_worker(dry_run: bool, sleep_sec: float) -> None:
    global ALADIN_DISCOGS_BACKFILL_LAST_ERROR
    try:
        _run_aladin_discogs_backfill(dry_run=dry_run, sleep_sec=sleep_sec)
    except HTTPException:
        pass
    except Exception as exc:
        ALADIN_DISCOGS_BACKFILL_LAST_ERROR = f"{_now_iso()} | {exc}"
        logger.exception("aladin_discogs_backfill thread error: %s", exc)







# ── Discogs 한국 아티스트 한글명 백필 ──
DISCOGS_KOREAN_BACKFILL_LOCK   = threading.Lock()
DISCOGS_KOREAN_BACKFILL_THREAD: threading.Thread | None = None
DISCOGS_KOREAN_BACKFILL_RESULT: dict[str, Any] | None   = None

def _discogs_korean_backfill_worker(limit: int | None) -> None:
    global DISCOGS_KOREAN_BACKFILL_RESULT
    try:
        with DISCOGS_KOREAN_BACKFILL_LOCK:
            result = backfill_discogs_korean_artist_names(limit=limit)
            DISCOGS_KOREAN_BACKFILL_RESULT = {"status": "done", **result}
    except Exception as exc:
        DISCOGS_KOREAN_BACKFILL_RESULT = {"status": "error", "detail": str(exc)}
        logger.exception("discogs_korean_backfill error: %s", exc)



















def _compose_non_barcode_query(payload: QueryIngestRequest) -> str:
    if payload.query and payload.query.strip():
        return payload.query.strip()

    parts: list[str] = []
    for value in [
        payload.artist_or_brand,
        payload.title,
        payload.catalog_no,
        payload.runout,
        payload.label_name,
    ]:
        if value and value.strip():
            parts.append(value.strip())

    if payload.release_year:
        parts.append(str(payload.release_year))
    if payload.country and payload.country.strip():
        parts.append(payload.country.strip().upper())

    return " ".join(parts).strip()




def _decode_upload_bytes(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise HTTPException(status_code=400, detail="CSV decode failed. Use UTF-8/CP949/EUC-KR.")


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
    direct = re.fullmatch(r"\d+", text)
    if direct:
        return text
    url_match = re.search(r"/release/(\d+)", text, flags=re.IGNORECASE)
    if url_match:
        return str(url_match.group(1))
    return None


def _csv_slot_lookup_maps() -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str, str], dict[str, Any]]]:
    slot_by_code: dict[str, dict[str, Any]] = {}
    slot_by_triplet: dict[tuple[str, str, str], dict[str, Any]] = {}
    for slot in db.list_storage_slots():
        slot_code = str(slot.get("slot_code") or "").strip()
        if slot_code:
            slot_by_code[slot_code.casefold()] = slot
        cabinet_name = str(slot.get("cabinet_name") or "").strip()
        column_code = str(slot.get("column_code") or "").strip()
        cell_code = str(slot.get("cell_code") or "").strip()
        if cabinet_name and column_code and cell_code:
            slot_by_triplet[(cabinet_name.casefold(), column_code.casefold(), cell_code.casefold())] = slot
    return slot_by_code, slot_by_triplet


def _build_csv_discogs_candidate(release_id: str) -> dict[str, Any] | None:
    release_id_s = str(release_id or "").strip()
    if not release_id_s:
        return None
    snapshot = get_source_release_snapshot(source="DISCOGS", external_id=release_id_s)
    if not snapshot:
        return None

    raw = snapshot.get("raw") if isinstance(snapshot.get("raw"), dict) else {}
    title = str(raw.get("title") or "").strip() or f"Discogs Release #{release_id_s}"
    country = str(raw.get("country") or "").strip() or None
    return {
        "source": "DISCOGS",
        "external_id": release_id_s,
        "title": title,
        "artist_or_brand": snapshot.get("artist_or_brand"),
        "release_year": snapshot.get("release_year"),
        "released_date": snapshot.get("released_date"),
        "country": country,
        "format_name": snapshot.get("format_name"),
        "barcode": snapshot.get("barcode"),
        "catalog_no": snapshot.get("catalog_no"),
        "label_name": snapshot.get("label_name"),
        "cover_image_url": snapshot.get("cover_image_url"),
        "track_list": snapshot.get("track_list") or [],
        "media_type": snapshot.get("media_type"),
        "release_type": snapshot.get("release_type"),
        "domain_code": snapshot.get("domain_code"),
        "genres": snapshot.get("genres") or [],
        "styles": snapshot.get("styles") or [],
        "disc_count": snapshot.get("disc_count"),
        "speed_rpm": snapshot.get("speed_rpm"),
        "has_obi": snapshot.get("has_obi"),
        "runout_matrix": snapshot.get("runout_matrix") or [],
        "pressing_country": snapshot.get("pressing_country"),
        "source_notes": snapshot.get("source_notes"),
        "credits": snapshot.get("credits") or [],
        "identifier_items": snapshot.get("identifier_items") or [],
        "image_items": snapshot.get("image_items") or [],
        "company_items": snapshot.get("company_items") or [],
        "series": snapshot.get("series") or [],
        "format_items": snapshot.get("format_items") or [],
        "track_items": snapshot.get("track_items") or [],
        "label_items": snapshot.get("label_items") or [],
        "confidence": 1.0,
        "raw": raw,
    }


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


def _merge_review_note(*parts: str | None) -> str | None:
    merged = [str(part).strip() for part in parts if str(part or "").strip()]
    return " / ".join(merged) if merged else None


















































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



def _build_duplicate_payload_from_existing_item(
    base_row: dict[str, Any],
    detail_row: dict[str, Any] | None,
    copy_group_key: str,
    linked_master_id: int | None,
) -> dict[str, Any]:
    source_code = str(base_row.get("source_code") or "").strip().upper() or None
    source_external_id = str(base_row.get("source_external_id") or "").strip() or None
    if bool(source_code) != bool(source_external_id):
        source_code = None
        source_external_id = None

    payload: dict[str, Any] = {
        "master_item_id": base_row.get("master_item_id"),
        "linked_album_master_id": linked_master_id,
        "linked_artist_name": base_row.get("linked_artist_name"),
        "copy_group_key": copy_group_key,
        "category": str(base_row.get("category") or "").strip().upper() or "CD",
        "domain_code": base_row.get("domain_code"),
        "release_type": base_row.get("release_type"),
        "item_name_override": base_row.get("item_name_override"),
        "quantity": 1,
        "is_second_hand": bool(base_row.get("is_second_hand")),
        "size_group": base_row.get("size_group") or "STD",
        "preferred_storage_size_group": base_row.get("preferred_storage_size_group") or base_row.get("size_group") or "STD",
        "status": base_row.get("status") or "IN_COLLECTION",
        "condition_grade": base_row.get("condition_grade"),
        "signature_type": base_row.get("signature_type") or "NONE",
        "source_code": source_code,
        "source_external_id": source_external_id,
        "signed_by": base_row.get("signed_by"),
        "signed_at": base_row.get("signed_at"),
        "acquisition_date": base_row.get("acquisition_date"),
        "purchase_price": base_row.get("purchase_price"),
        "currency_code": base_row.get("currency_code"),
        "purchase_source": base_row.get("purchase_source"),
        "memory_note": base_row.get("memory_note"),
        "display_rank": None,
        "order_key": None,
        "storage_slot_id": None,
        "thickness_mm": base_row.get("thickness_mm"),
        "notes": base_row.get("notes"),
        "subtype_option_ids": (detail_row or {}).get("subtype_option_ids") or [],
        "soundtrack_option_ids": (detail_row or {}).get("soundtrack_option_ids") or [],
    }

    category_code = str(payload.get("category") or "").strip().upper()
    if category_code in MUSIC_CATEGORIES:
        ref = detail_row or {}
        payload["music_detail"] = {
            "format_name": ref.get("format_name") or category_code,
            "is_promotional_not_for_sale": bool(ref.get("is_promotional_not_for_sale")),
            "artist_or_brand": ref.get("artist_or_brand"),
            "release_year": ref.get("release_year"),
            "barcode": ref.get("barcode"),
            "label_name": ref.get("label_name"),
            "catalog_no": _discogs_catalog_no(ref.get("catalog_no")),
            "cover_image_url": ref.get("cover_image_url"),
            "track_list": ref.get("track_list") or [],
            "media_type": ref.get("media_type"),
            "genres": ref.get("genres") or [],
            "styles": ref.get("styles") or [],
            "cover_condition": ref.get("cover_condition"),
            "disc_condition": ref.get("disc_condition"),
        }
    else:
        ref = detail_row or {}
        payload["goods_detail"] = {
            "image_urls": ref.get("goods_image_urls") or [],
            "primary_image_url": ref.get("goods_primary_image_url"),
            "poster_storage_spec": ref.get("poster_storage_spec"),
            "tshirt_size": ref.get("tshirt_size"),
            "cup_material": ref.get("cup_material"),
            "hat_size": ref.get("hat_size"),
        }

    return payload


def _annotate_owned_flags(candidates: list[dict[str, object]]) -> list[dict[str, object]]:
    by_source: dict[str, set[str]] = {}
    for c in candidates:
        source = str(c.get("source") or "").strip().upper()
        external_id = str(c.get("external_id") or "").strip()
        if not source or not external_id:
            continue
        by_source.setdefault(source, set()).add(external_id)

    counts_by_source: dict[str, dict[str, int]] = {}
    for source, external_ids in by_source.items():
        counts_by_source[source] = db.get_owned_counts_by_source(source, sorted(external_ids))

    out: list[dict[str, object]] = []
    for c in candidates:
        source = str(c.get("source") or "").strip().upper()
        external_id = str(c.get("external_id") or "").strip()
        cnt = counts_by_source.get(source, {}).get(external_id, 0)
        c2 = dict(c)
        c2["owned_count"] = cnt
        c2["is_owned"] = cnt > 0
        out.append(c2)
    return out


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


def _album_master_variant_item_from_owned_row(row: dict[str, Any], source_code: str) -> AlbumMasterVariantItem:
    return AlbumMasterVariantItem(
        source=str(source_code or "").strip().upper() or "DISCOGS",
        external_id=str(row.get("source_external_id") or "").strip(),
        title=str(row.get("item_name_override") or "").strip() or str(row.get("master_title") or "").strip() or f"{source_code} item",
        artist_or_brand=str(row.get("artist_or_brand") or row.get("linked_artist_name") or row.get("master_artist_or_brand") or "").strip() or None,
        release_year=int(row["release_year"]) if row.get("release_year") is not None else None,
        released_date=str(row.get("released_date") or "").strip() or None,
        country=str(row.get("pressing_country") or "").strip() or None,
        format_name=str(row.get("format_name") or "").strip() or None,
        media_type=str(row.get("media_type") or "").strip() or None,
        release_type=str(row.get("release_type") or "").strip().upper() or None,
        domain_code=str(row.get("domain_code") or "").strip().upper() or None,
        genres=list(row.get("genres") or []),
        styles=list(row.get("styles") or []),
        label_name=str(row.get("label_name") or "").strip() or None,
        catalog_no=str(row.get("catalog_no") or "").strip() or None,
        barcode=str(row.get("barcode") or "").strip() or None,
        cover_image_url=str(row.get("cover_image_url") or "").strip() or None,
        track_list=list(row.get("track_list") or []),
        disc_count=int(row["disc_count"]) if row.get("disc_count") is not None else None,
        speed_rpm=int(row["speed_rpm"]) if row.get("speed_rpm") is not None else None,
        has_obi=bool(row.get("has_obi")) if row.get("has_obi") is not None else None,
        runout_matrix=list(row.get("runout_matrix") or []),
        pressing_country=str(row.get("pressing_country") or "").strip() or None,
        source_notes=str(row.get("source_notes") or "").strip() or None,
        credits=list(row.get("credits") or []),
        identifier_items=list(row.get("identifier_items") or []),
        image_items=list(row.get("image_items") or []),
        company_items=list(row.get("company_items") or []),
        series=list(row.get("series") or []),
        format_items=list(row.get("format_items") or []),
        track_items=list(row.get("track_items") or []),
        label_items=list(row.get("label_items") or []),
        is_owned=True,
        owned_count=1,
        raw={},
    )


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


def _search_compact_text(value: Any) -> str:
    compact = re.sub(r"[^0-9a-zA-Z가-힣]+", "", str(value or "").strip().lower())
    return re.sub(r"제(?=\d+집$)", "", compact)


def _track_match_quality(track_values: list[str], query_text: str) -> tuple[int, str]:
    query_key = _search_compact_text(query_text)
    if not query_key:
        return (2, "")
    best_rank = 2
    best_value = ""
    for value in track_values:
        text = str(value or "").strip()
        if not text:
            continue
        compact = _search_compact_text(text)
        if not compact:
            continue
        rank = 2
        if compact == query_key or compact.endswith(query_key):
            rank = 0
        elif query_key in compact:
            rank = 1
        if rank < best_rank:
            best_rank = rank
            best_value = text
            if rank == 0:
                break
    return (best_rank, best_value)


def _album_master_search_sort_key(row: AlbumMasterListItem, query_text: str) -> tuple[Any, ...]:
    query_key = _search_compact_text(query_text)
    title_key = _search_compact_text(row.title)
    artist_key = _search_compact_text(row.artist_or_brand or "")
    combined_key = f"{artist_key}{title_key}"
    track_rank, best_track = _track_match_quality(list(row.matched_track_preview or []), query_text)

    title_rank = 2
    if query_key:
        if title_key == query_key or combined_key == query_key:
            title_rank = 0
        elif query_key in title_key or query_key in combined_key:
            title_rank = 1

    updated_epoch = 0.0
    updated_text = str(row.updated_at or "").strip()
    if updated_text:
        try:
            updated_epoch = datetime.fromisoformat(updated_text).timestamp()
        except ValueError:
            updated_epoch = 0.0
    return (
        track_rank,
        title_rank,
        0 if best_track else 1,
        -int(row.member_count or 0),
        -updated_epoch,
        -int(row.id or 0),
    )


def _album_master_member_context(album_master_id: int, preview_limit: int = 8) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    actions: list[dict[str, Any]] = []
    previews: list[dict[str, Any]] = []
    source_snapshot_cache: dict[tuple[str, str], dict[str, Any] | None] = {}
    for item in db.list_owned_items_by_album_master(album_master_id):
        owned_item_id = int(item.get("id") or item.get("owned_item_id") or 0)
        category = str(item.get("category") or "").strip()
        storage_slot_id = int(item.get("storage_slot_id") or 0) or None
        slot_code = str(item.get("slot_code") or item.get("current_slot_code") or "").strip() or None
        cabinet_name = str(item.get("cabinet_name") or item.get("current_cabinet_name") or "").strip() or None
        column_code = str(item.get("column_code") or item.get("current_column_code") or "").strip() or None
        cell_code = str(item.get("cell_code") or item.get("current_cell_code") or "").strip() or None
        location_display_name = str(item.get("current_slot_display_name") or "").strip()
        if not location_display_name:
            location_display_name = " / ".join(
                part
                for part in [
                    cabinet_name,
                    f"{column_code}열" if column_code else "",
                    f"{cell_code}칸" if cell_code else "",
                ]
                if part
            ) or slot_code or "미배치"
        item_label = str(item.get("item_name_override") or item.get("item_title") or item.get("title") or "").strip() or None
        if storage_slot_id or slot_code or cabinet_name:
            actions.append(
                {
                    "owned_item_id": owned_item_id,
                    "storage_slot_id": storage_slot_id,
                    "slot_code": slot_code,
                    "cabinet_name": cabinet_name,
                    "column_code": column_code,
                    "cell_code": cell_code,
                    "location_display_name": location_display_name,
                    "item_label": item_label,
                }
            )
        if owned_item_id <= 0 or len(previews) >= preview_limit:
            continue
        source_code = str(item.get("source_code") or "").strip().upper() or None
        source_external_id = str(item.get("source_external_id") or "").strip() or None
        released_date = str(item.get("released_date") or "").strip() or None
        if not released_date and source_code == "MANIADB" and source_external_id:
            snapshot_key = (source_code, source_external_id)
            if snapshot_key not in source_snapshot_cache:
                source_snapshot_cache[snapshot_key] = get_source_release_snapshot(source_code, source_external_id)
            snapshot = source_snapshot_cache.get(snapshot_key) or {}
            released_date = str(snapshot.get("released_date") or "").strip() or None
        previews.append(
            {
                "owned_item_id": owned_item_id,
                "storage_slot_id": storage_slot_id,
                "label_id": str(item.get("label_id") or db._build_label_id(category, owned_item_id)),
                "source_code": source_code,
                "source_external_id": source_external_id,
                "item_title": str(item.get("item_title") or item.get("item_name_override") or item.get("title") or "").strip() or None,
                "artist_or_brand": str(item.get("artist_or_brand") or "").strip() or None,
                "cover_image_url": str(item.get("cover_image_url") or "").strip() or None,
                "created_at": str(item.get("created_at") or "").strip() or None,
                "released_date": released_date,
                "master_release_year": int(item["master_release_year"]) if item.get("master_release_year") else None,
                "pressing_country": str(item.get("pressing_country") or "").strip() or None,
                "label_name": str(item.get("label_name") or "").strip() or None,
                "catalog_no": str(item.get("catalog_no") or "").strip() or None,
                "barcode": str(item.get("barcode") or "").strip() or None,
                "format_name": str(item.get("format_name") or "").strip() or None,
                "format_items": [dict(row) for row in item.get("format_items") or [] if isinstance(row, dict)],
                "runout_sample": str(item.get("runout_sample") or "").strip() or None,
                "current_slot_display_name": location_display_name,
                "current_slot_code": slot_code,
                "current_cabinet_name": cabinet_name,
                "current_column_code": column_code,
                "current_cell_code": cell_code,
            }
        )
    return actions, previews


def _discogs_cover_preview_cache_name(release_id: str) -> str:
    return re.sub(r"[^0-9A-Za-z._-]+", "_", str(release_id or "").strip()) or "discogs-release"


def _discogs_cover_preview_cached_file(release_id: str) -> tuple[Path, str] | None:
    cache_name = _discogs_cover_preview_cache_name(release_id)
    for path in sorted(DISCOGS_COVER_PREVIEW_CACHE_DIR.glob(f"{cache_name}.*")):
        if not path.is_file():
            continue
        media_type = next(
            (content_type for content_type, ext in ALLOWED_IMAGE_CONTENT_TYPES.items() if ext == path.suffix.lower()),
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
    request_headers = dict(PURCHASE_ITEM_FETCH_HEADERS)
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


def _album_master_source_priority(source_code: str) -> int:
    code = str(source_code or "").strip().upper()
    if code == "DISCOGS":
        return 0
    if code == "MANIADB":
        return 1
    return 2


def _pick_duplicate_merge_target_id(duplicates: list[dict[str, Any]]) -> int | None:
    if not duplicates:
        return None
    ranked = sorted(
        duplicates,
        key=lambda row: (
            _album_master_source_priority(str(row.get("source_code") or "")),
            -int(row.get("member_count") or 0),
            -int(row.get("album_master_id") or 0),
        ),
    )
    target_id = int(ranked[0].get("album_master_id") or 0)
    return target_id if target_id > 0 else None




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


def _discogs_format_values(raw: dict[str, Any]) -> list[str]:
    out = []
    for item in _discogs_format_items(raw):
        out.append(str(item.get("display") or ""))
    return [v for v in out if v]


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


def _discogs_identifiers(raw: dict[str, Any]) -> tuple[list[str], list[str], str | None, list[dict[str, Any]]]:
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


def _contains_hangul_artist_name(value: Any) -> bool:
    return bool(re.search(r"[\u3131-\u318e\uac00-\ud7a3]", str(value or "")))


def _discogs_artist_name_needs_localization(value: Any) -> bool:
    text = _clean_text(value)
    return bool(text) and not _contains_hangul_artist_name(text)


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


def _normalize_music_detail_payload(normalized_payload: dict[str, object]) -> None:
    music_detail = normalized_payload.get("music_detail")
    if not isinstance(music_detail, dict):
        return

    source_code = str(normalized_payload.get("source_code") or "").strip().upper()
    source_external_id = str(normalized_payload.get("source_external_id") or "").strip()
    domain_code_raw = normalized_payload.get("domain_code")
    release_type_raw = str(normalized_payload.get("release_type") or "").strip().upper()
    domain_code = _normalize_domain_code(domain_code_raw)
    release_type = release_type_raw if release_type_raw in RELEASE_TYPES else None
    source_snapshot: dict[str, object] | None = None
    if source_code and source_external_id:
        source_snapshot = get_source_release_snapshot(source_code, source_external_id)

    cover_condition = (music_detail.get("cover_condition") or music_detail.get("sleeve_condition") or "").strip()
    disc_condition = (music_detail.get("disc_condition") or music_detail.get("media_condition") or "").strip()
    artist_or_brand = (music_detail.get("artist_or_brand") or "").strip() or None
    release_year = music_detail.get("release_year")
    if release_year is not None:
        try:
            release_year = int(release_year)
        except (TypeError, ValueError):
            release_year = None
    released_date = (music_detail.get("released_date") or "").strip() or None
    barcode = (music_detail.get("barcode") or "").strip() or None
    label_name = (music_detail.get("label_name") or "").strip() or None
    catalog_no = _discogs_catalog_no(music_detail.get("catalog_no"))
    cover_image_url = (music_detail.get("cover_image_url") or "").strip() or None
    media_type = (music_detail.get("media_type") or "").strip() or None
    track_list_raw = music_detail.get("track_list") or []
    track_list = [
        str(v).strip()
        for v in track_list_raw
        if str(v).strip()
    ]
    genres = _clean_string_list(music_detail.get("genres"))
    styles = _clean_string_list(music_detail.get("styles"))
    disc_count_raw = music_detail.get("disc_count")
    try:
        disc_count = int(disc_count_raw) if disc_count_raw is not None and str(disc_count_raw).strip() else None
    except (TypeError, ValueError):
        disc_count = None
    if disc_count is not None and disc_count <= 0:
        disc_count = None
    speed_rpm_raw = music_detail.get("speed_rpm")
    try:
        speed_rpm = int(speed_rpm_raw) if speed_rpm_raw is not None and str(speed_rpm_raw).strip() else None
    except (TypeError, ValueError):
        speed_rpm = None
    if speed_rpm is not None and speed_rpm <= 0:
        speed_rpm = None
    has_obi = _normalize_has_obi_input(music_detail.get("has_obi"))
    runout_matrix = _clean_runout_list(music_detail.get("runout_matrix"))
    pressing_country = (music_detail.get("pressing_country") or "").strip() or None
    source_notes = _clean_text(music_detail.get("source_notes"))
    credits = _clean_string_list(music_detail.get("credits"))
    identifier_items = _clean_dict_list(music_detail.get("identifier_items"))
    image_items = _clean_dict_list(music_detail.get("image_items"))
    company_items = _clean_dict_list(music_detail.get("company_items"))
    series = _clean_string_list(music_detail.get("series"))
    format_items = _clean_dict_list(music_detail.get("format_items"))
    track_items = _clean_dict_list(music_detail.get("track_items"))
    label_items = _clean_dict_list(music_detail.get("label_items"))
    if source_snapshot:
        label_name = label_name or str(source_snapshot.get("label_name") or "").strip() or None
        catalog_no = catalog_no or _discogs_catalog_no(source_snapshot.get("catalog_no"))
        cover_image_url = cover_image_url or str(source_snapshot.get("cover_image_url") or "").strip() or None
        barcode = barcode or str(source_snapshot.get("barcode") or "").strip() or None
        media_type = media_type or str(source_snapshot.get("media_type") or "").strip() or None
        snapshot_released_date = str(source_snapshot.get("released_date") or "").strip() or None
        released_date = released_date or snapshot_released_date
        if not genres:
            genres = _clean_string_list(source_snapshot.get("genres"))
        if not styles:
            styles = _clean_string_list(source_snapshot.get("styles"))
        if disc_count is None:
            snap_disc_count = source_snapshot.get("disc_count")
            try:
                disc_count = int(snap_disc_count) if snap_disc_count is not None and str(snap_disc_count).strip() else None
            except (TypeError, ValueError):
                disc_count = None
            if disc_count is not None and disc_count <= 0:
                disc_count = None
        if speed_rpm is None:
            snap_speed = source_snapshot.get("speed_rpm")
            try:
                speed_rpm = int(snap_speed) if snap_speed is not None and str(snap_speed).strip() else None
            except (TypeError, ValueError):
                speed_rpm = None
            if speed_rpm is not None and speed_rpm <= 0:
                speed_rpm = None
        if not runout_matrix:
            runout_matrix = _clean_runout_list(source_snapshot.get("runout_matrix"))
        if source_code == "DISCOGS":
            pressing_country = pressing_country or str(source_snapshot.get("pressing_country") or "").strip() or None
        source_notes = source_notes or _clean_text(source_snapshot.get("source_notes"))
        if not credits:
            credits = _clean_string_list(source_snapshot.get("credits"))
        if not identifier_items:
            identifier_items = _clean_dict_list(source_snapshot.get("identifier_items"))
        if not image_items:
            image_items = _clean_dict_list(source_snapshot.get("image_items"))
        if not company_items:
            company_items = _clean_dict_list(source_snapshot.get("company_items"))
        if not series:
            series = _clean_string_list(source_snapshot.get("series"))
        if not format_items:
            format_items = _clean_dict_list(source_snapshot.get("format_items"))
        if not track_items:
            track_items = _clean_dict_list(source_snapshot.get("track_items"))
        if not label_items:
            label_items = _clean_dict_list(source_snapshot.get("label_items"))
        if domain_code is None:
            domain_code = _normalize_domain_code(source_snapshot.get("domain_code"))
        if release_type is None:
            snapshot_release_type = str(source_snapshot.get("release_type") or "").strip().upper()
            release_type = snapshot_release_type if snapshot_release_type in RELEASE_TYPES else None
        if not track_list:
            source_tracks = source_snapshot.get("track_list")
            if isinstance(source_tracks, list):
                track_list = [str(v).strip() for v in source_tracks if str(v).strip()]

    if release_year is None:
        date_like = str(released_date or "").strip()
        m = re.match(r"^(\d{4})", date_like)
        if m:
            try:
                parsed_year = int(m.group(1))
                if 1900 <= parsed_year <= 2100:
                    release_year = parsed_year
            except (TypeError, ValueError):
                release_year = None
        elif source_snapshot:
            snap_year_raw = source_snapshot.get("release_year")
            try:
                parsed_year = int(snap_year_raw) if snap_year_raw is not None else None
            except (TypeError, ValueError):
                parsed_year = None
            if parsed_year is not None and 1900 <= parsed_year <= 2100:
                release_year = parsed_year

    music_detail["sleeve_condition"] = cover_condition or None
    music_detail["media_condition"] = disc_condition or None
    music_detail["cover_condition"] = cover_condition or None
    music_detail["disc_condition"] = disc_condition or None
    music_detail["artist_or_brand"] = artist_or_brand
    music_detail["release_year"] = release_year
    music_detail["released_date"] = released_date
    music_detail["barcode"] = barcode
    music_detail["label_name"] = label_name
    music_detail["catalog_no"] = catalog_no
    music_detail["cover_image_url"] = cover_image_url
    music_detail["media_type"] = media_type
    music_detail["genres"] = genres
    music_detail["styles"] = styles
    music_detail["disc_count"] = disc_count
    music_detail["speed_rpm"] = speed_rpm
    music_detail["disc_type"] = (music_detail.get("disc_type") or "").strip() or None
    music_detail["package_contents"] = (music_detail.get("package_contents") or "").strip() or None
    music_detail["is_limited_edition"] = music_detail.get("is_limited_edition")
    music_detail["edition_number"] = (music_detail.get("edition_number") or "").strip() or None
    music_detail["has_obi"] = has_obi
    music_detail["runout_matrix"] = runout_matrix
    music_detail["pressing_country"] = pressing_country
    music_detail["source_notes"] = source_notes
    music_detail["credits"] = credits
    music_detail["identifier_items"] = identifier_items
    music_detail["image_items"] = image_items
    music_detail["company_items"] = company_items
    music_detail["series"] = series
    music_detail["format_items"] = format_items
    music_detail["track_items"] = track_items
    music_detail["label_items"] = label_items
    music_detail["track_list"] = track_list
    # 도메인 결정 우선순위:
    # 1. 사용자가 명시한 domain_code (payload)
    # 2. 소스 스냅샷의 domain_code (Discogs: master_country 기반, MANIADB: 항상 KOREA)
    # 3. genres/styles/country/artist 재추론 + master_domain_hint 폴백
    snapshot_domain = _normalize_domain_code((source_snapshot or {}).get("domain_code"))
    normalized_payload["domain_code"] = (
        domain_code
        or snapshot_domain
        or _infer_owned_item_domain_code(normalized_payload, music_detail, source_snapshot)
    )
    normalized_payload["release_type"] = release_type


def _normalize_goods_detail_payload(normalized_payload: dict[str, object]) -> None:
    category_code = str(normalized_payload.get("category") or "").strip().upper()
    if category_code in MUSIC_CATEGORIES:
        normalized_payload["goods_detail"] = None
        return

    goods_detail = normalized_payload.get("goods_detail")
    if not isinstance(goods_detail, dict):
        normalized_payload["goods_detail"] = None
        normalized_payload["music_detail"] = None
        return

    image_urls = _clean_goods_image_urls(goods_detail.get("image_urls"))
    primary_image_url = _clean_text(goods_detail.get("primary_image_url"))
    if primary_image_url is None and image_urls:
        primary_image_url = image_urls[0]

    normalized_payload["goods_detail"] = {
        "image_urls": image_urls,
        "primary_image_url": primary_image_url,
        "poster_storage_spec": _clean_text(goods_detail.get("poster_storage_spec")),
        "tshirt_size": _clean_text(goods_detail.get("tshirt_size")),
        "cup_material": _clean_text(goods_detail.get("cup_material")),
        "hat_size": _clean_text(goods_detail.get("hat_size")),
    }
    normalized_payload["music_detail"] = None


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


def _apply_post_create_links(
    payload: OwnedItemCreate,
    owned_item_id: int,
    preferred_master_id: int = 0,
) -> tuple[int, list[str]]:
    notices: list[str] = []
    linked_master_id = int(preferred_master_id or 0)
    source_code = str(payload.source_code or "").strip().upper()
    source_external_id = str(payload.source_external_id or "").strip()

    if linked_master_id > 0:
        linked_count = db.bind_album_master_members(
            album_master_id=linked_master_id,
            owned_item_ids=[owned_item_id],
            replace_existing=False,
        )
        db.set_owned_item_linked_album_master(owned_item_id=owned_item_id, album_master_id=linked_master_id)
        notices.append(f"선택한 마스터(album_master_id={linked_master_id})에 연결되었습니다. (멤버 수: {linked_count})")
        if source_code == "DISCOGS" and source_external_id:
            promoted_master_id, promoted_notices = _promote_album_master_to_discogs(
                album_master_id=linked_master_id,
                source_external_id=source_external_id,
            )
            if promoted_master_id > 0:
                linked_master_id = promoted_master_id
                db.bind_album_master_members(
                    album_master_id=linked_master_id,
                    owned_item_ids=[owned_item_id],
                    replace_existing=False,
                )
                db.set_owned_item_linked_album_master(owned_item_id=owned_item_id, album_master_id=linked_master_id)
            for msg in promoted_notices:
                text = str(msg or "").strip()
                if text:
                    notices.append(text)
        elif _source_supports_master_auto_link(source_code) and source_external_id:
            for msg in _attach_source_master_ref_to_album_master(
                album_master_id=linked_master_id,
                source_code=source_code,
                source_external_id=source_external_id,
            ):
                text = str(msg or "").strip()
                if text:
                    notices.append(text)
        return linked_master_id, notices

    if _source_supports_master_auto_link(source_code) and source_external_id:
        notices.extend(
            _link_source_master_for_created_item(
                source_code=source_code,
                source_external_id=source_external_id,
                owned_item_id=owned_item_id,
            )
        )

    ensured_master_id, ensured_notices = _ensure_owned_item_master_link(owned_item_id)
    if ensured_master_id > 0:
        linked_master_id = ensured_master_id
    for msg in ensured_notices:
        text = str(msg or "").strip()
        if text:
            notices.append(text)
    if source_code == "DISCOGS" and source_external_id:
        promoted_master_id, promoted_notices = _promote_owned_item_linked_master_from_discogs_source(owned_item_id)
        if promoted_master_id > 0:
            linked_master_id = promoted_master_id
        for msg in promoted_notices:
            text = str(msg or "").strip()
            if text:
                notices.append(text)
    return linked_master_id, notices


def _extract_location_recommendation_context(payload: OwnedItemCreate) -> tuple[str | None, int | None, str | None, str | None]:
    artist_or_brand = _clean_text(payload.linked_artist_name)
    release_year: int | None = None
    item_title = _clean_text(payload.item_name_override)
    released_date = None
    music_detail = payload.music_detail
    if music_detail is not None:
        artist_or_brand = _clean_text(music_detail.artist_or_brand) or artist_or_brand
        try:
            release_year = int(music_detail.release_year) if music_detail.release_year is not None else None
        except (TypeError, ValueError):
            release_year = None
        released_date = _clean_text(music_detail.released_date)
    return artist_or_brand, release_year, item_title, released_date


def _apply_new_item_location_recommendation(payload: OwnedItemCreate, owned_item_id: int) -> list[str]:
    oid = int(owned_item_id or 0)
    if oid <= 0:
        return []
    if not bool(payload.auto_location_recommendation):
        return []
    if str(payload.status or "IN_COLLECTION").strip().upper() != "IN_COLLECTION":
        return []
    if str(payload.category or "").strip().upper() not in MUSIC_CATEGORIES:
        return []

    notices: list[str] = []
    artist_or_brand, release_year, item_title, released_date = _extract_location_recommendation_context(payload)
    preferred_size_group = _preferred_storage_size_group(payload.preferred_storage_size_group, payload.size_group)
    suggestion = db.recommend_owned_item_location(
        size_group=preferred_size_group,
        artist_or_brand=artist_or_brand,
        release_year=release_year,
        released_date=released_date,
        domain_code=payload.domain_code,
        item_title=item_title,
        exclude_owned_item_id=oid,
        incoming_thickness_mm=payload.thickness_mm,
        incoming_format_name=_clean_text(payload.music_detail.format_name) if payload.music_detail else None,
        incoming_package_hint=_clean_text(payload.notes),
    )
    if not suggestion:
        return notices

    anchor_owned_item_id = int(suggestion.get("anchor_owned_item_id") or 0)
    anchor_position = str(suggestion.get("anchor_position") or "").strip().upper()
    recommended_slot_id = int(suggestion.get("recommended_storage_slot_id") or 0)
    slot_code = str(suggestion.get("slot_code") or "").strip() or "-"
    used_fallback_slot = bool(suggestion.get("used_fallback_slot"))
    reason = str(suggestion.get("reason") or "").strip()

    applied_slot_text = "-"
    if payload.storage_slot_id is None and recommended_slot_id > 0:
        try:
            _validate_slot(preferred_size_group, recommended_slot_id)
            db.update_owned_item_slot(owned_item_id=oid, storage_slot_id=recommended_slot_id)
            applied_slot_text = f"{slot_code}(id={recommended_slot_id})"
        except HTTPException:
            applied_slot_text = f"미적용(id={recommended_slot_id})"

    applied_order_text = "-"
    if anchor_owned_item_id > 0 and anchor_position in {"BEFORE", "AFTER"} and anchor_owned_item_id != oid:
        try:
            order_key = db.move_owned_item_order(
                owned_item_id=oid,
                target_owned_item_id=anchor_owned_item_id,
                position=anchor_position,
            )
            applied_order_text = f"{anchor_position} owned_item_id={anchor_owned_item_id} (order_key={order_key})"
        except (LookupError, ValueError):
            applied_order_text = f"미적용(target={anchor_owned_item_id})"

    if applied_slot_text != "-" or applied_order_text != "-":
        fallback_text = "대체 위치 적용" if used_fallback_slot else "기준 위치 적용"
        reason_text = f", reason={reason}" if reason else ""
        notices.append(
            f"위치 추천: slot={applied_slot_text} | order={applied_order_text} | {fallback_text}{reason_text}"
        )
    return notices


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


def _build_owned_item_payload_for_source_replace(owned_item_id: int, candidate: dict[str, Any]) -> OwnedItemCreate:
    base_row = db.get_owned_item(owned_item_id)
    detail_row = db.get_owned_item_detail(owned_item_id)
    if base_row is None or detail_row is None:
        raise HTTPException(status_code=404, detail="owned_item not found")

    existing_category = str(detail_row.get("category") or "").strip().upper()
    if existing_category not in MUSIC_CATEGORIES:
        raise HTTPException(status_code=400, detail="source replace is only supported for music items")

    source_code_raw = str(candidate.get("source") or "").strip().upper()
    source_external_id = str(candidate.get("external_id") or "").strip()
    if source_code_raw not in {"DISCOGS", "MANIADB", "ALADIN"} or not source_external_id:
        raise HTTPException(status_code=400, detail="candidate source/external_id is invalid")

    category = _infer_music_category_from_format(candidate.get("format_name") or detail_row.get("format_name") or existing_category)
    item_title = _clean_text(candidate.get("title"))
    artist_name = _merge_replace_text(candidate.get("artist_or_brand"), detail_row.get("artist_or_brand") or base_row.get("linked_artist_name"))
    # item_name_override는 순수 앨범명만 저장. 디스플레이명(아티스트 + 앨범)은 쿼리 레이어에서 조합.
    item_name_override = item_title or _clean_text(detail_row.get("item_name_override")) or _clean_text(base_row.get("item_name_override"))

    memory_note_parts = []
    existing_memory_note = _clean_text(base_row.get("memory_note"))
    if existing_memory_note:
        memory_note_parts.append(existing_memory_note)
    marker = f"[META-REPLACE] {source_code_raw}#{source_external_id}"
    if not existing_memory_note or marker not in existing_memory_note:
        memory_note_parts.append(marker)

    domain_code = (
        _normalize_domain_code(candidate.get("domain_code"))
        or _normalize_domain_code(detail_row.get("domain_code"))
        or _normalize_domain_code(base_row.get("domain_code"))
    )
    release_type_raw = str(candidate.get("release_type") or detail_row.get("release_type") or base_row.get("release_type") or "").strip().upper()
    release_type = release_type_raw if release_type_raw in RELEASE_TYPES else None

    music_detail = {
        "format_name": category,
        "is_promotional_not_for_sale": bool(detail_row.get("is_promotional_not_for_sale")),
        "artist_or_brand": artist_name,
        "release_year": _merge_replace_int(candidate.get("release_year"), detail_row.get("release_year")),
        "released_date": _merge_replace_text(candidate.get("released_date"), detail_row.get("released_date")),
        "barcode": _merge_replace_text(candidate.get("barcode"), detail_row.get("barcode")),
        "label_name": _merge_replace_text(candidate.get("label_name"), detail_row.get("label_name")),
        "catalog_no": _merge_replace_text(candidate.get("catalog_no"), detail_row.get("catalog_no")),
        "cover_image_url": _merge_replace_text(candidate.get("cover_image_url"), detail_row.get("cover_image_url")),
        "track_list": _clean_track_list(candidate.get("track_list")) or _clean_track_list(detail_row.get("track_list")),
        "media_type": _merge_replace_text(candidate.get("media_type"), detail_row.get("media_type")),
        "genres": _merge_replace_string_list(candidate.get("genres"), detail_row.get("genres")),
        "styles": _merge_replace_string_list(candidate.get("styles"), detail_row.get("styles")),
        "cover_condition": _clean_text(detail_row.get("cover_condition")),
        "disc_condition": _clean_text(detail_row.get("disc_condition")),
        "disc_count": _merge_replace_int(candidate.get("disc_count"), detail_row.get("disc_count")),
        "speed_rpm": _merge_replace_int(candidate.get("speed_rpm"), detail_row.get("speed_rpm")),
        "has_obi": _normalize_has_obi_input(candidate.get("has_obi")) if candidate.get("has_obi") is not None else detail_row.get("has_obi"),
        "runout_matrix": _merge_replace_runout(candidate.get("runout_matrix"), detail_row.get("runout_matrix")),
        "pressing_country": _merge_replace_text(candidate.get("pressing_country"), detail_row.get("pressing_country")),
        "source_notes": _merge_replace_text(candidate.get("source_notes"), detail_row.get("source_notes")),
        "credits": _merge_replace_string_list(candidate.get("credits"), detail_row.get("credits")),
        "identifier_items": _merge_replace_dict_list(candidate.get("identifier_items"), detail_row.get("identifier_items")),
        "image_items": _merge_replace_dict_list(candidate.get("image_items"), detail_row.get("image_items")),
        "company_items": _merge_replace_dict_list(candidate.get("company_items"), detail_row.get("company_items")),
        "series": _merge_replace_string_list(candidate.get("series"), detail_row.get("series")),
        "format_items": _merge_replace_dict_list(candidate.get("format_items"), detail_row.get("format_items")),
        "track_items": _merge_replace_dict_list(candidate.get("track_items"), detail_row.get("track_items")),
        "label_items": _merge_replace_dict_list(candidate.get("label_items"), detail_row.get("label_items")),
    }

    return OwnedItemCreate(
        category=category,
        size_group=str(base_row.get("size_group") or "STD"),
        preferred_storage_size_group=str(base_row.get("preferred_storage_size_group") or base_row.get("size_group") or "STD"),
        quantity=1,
        is_second_hand=bool(base_row.get("is_second_hand")),
        status=str(base_row.get("status") or "IN_COLLECTION"),
        signature_type=str(base_row.get("signature_type") or "NONE"),
        source_code=source_code_raw,
        source_external_id=source_external_id,
        domain_code=domain_code,
        release_type=release_type,
        master_item_id=base_row.get("master_item_id"),
        linked_album_master_id=base_row.get("linked_album_master_id"),
        linked_artist_name=artist_name,
        copy_group_key=base_row.get("copy_group_key"),
        item_name_override=item_name_override,
        condition_grade=base_row.get("condition_grade"),
        signed_by=base_row.get("signed_by"),
        signed_at=base_row.get("signed_at"),
        acquisition_date=base_row.get("acquisition_date"),
        purchase_price=base_row.get("purchase_price"),
        currency_code=base_row.get("currency_code"),
        purchase_source=base_row.get("purchase_source"),
        memory_note="\n".join(memory_note_parts) if memory_note_parts else None,
        display_rank=base_row.get("display_rank"),
        storage_slot_id=base_row.get("storage_slot_id"),
        thickness_mm=base_row.get("thickness_mm"),
        notes=base_row.get("notes"),
        subtype_option_ids=detail_row.get("subtype_option_ids") or [],
        soundtrack_option_ids=detail_row.get("soundtrack_option_ids") or [],
        music_detail=music_detail,
        goods_detail=None,
    )


def _save_owned_item_update(
    owned_item_id: int,
    payload: OwnedItemCreate,
    existing: dict[str, Any] | None = None,
) -> OwnedItemCreateResponse:
    save_started_at = time.perf_counter()
    existing_row = existing or db.get_owned_item(owned_item_id)
    existing_detail_row = db.get_owned_item_detail(owned_item_id)
    if existing_row is None:
        raise HTTPException(status_code=404, detail="owned_item not found")

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
        existing_row.get("size_group") or _default_size_group_for_category(normalized_payload.get("category") or payload.category),
    )
    normalized_payload["preferred_storage_size_group"] = _preferred_storage_size_group(
        normalized_payload.get("preferred_storage_size_group"),
        normalized_payload.get("size_group"),
    )
    if not str(normalized_payload.get("copy_group_key") or "").strip():
        normalized_payload["copy_group_key"] = existing_row.get("copy_group_key")
    notices: list[str] = []
    quantity = max(1, int(normalized_payload.get("quantity") or 1))
    if quantity > 1:
        normalized_payload["quantity"] = 1
        notices.append("복수 보유는 개별 인스턴스로 관리됩니다. 수량은 1로 저장했습니다.")
    _normalize_music_detail_payload(normalized_payload)
    _normalize_goods_detail_payload(normalized_payload)
    previous_source_code = str(existing_row.get("source_code") or "").strip().upper()
    previous_source_external_id = str(existing_row.get("source_external_id") or "").strip()
    normalize_done_at = time.perf_counter()
    ok = db.update_owned_item(owned_item_id=owned_item_id, payload=normalized_payload)
    if not ok:
        raise HTTPException(status_code=404, detail="owned_item not found")
    update_done_at = time.perf_counter()
    previous_status = str(existing_row.get("status") or "").strip().upper()
    next_status = str(normalized_payload.get("status") or "").strip().upper()
    try:
        previous_slot_id = int(existing_row.get("storage_slot_id")) if existing_row.get("storage_slot_id") is not None else None
    except (TypeError, ValueError):
        previous_slot_id = None
    try:
        next_slot_id = int(normalized_payload.get("storage_slot_id")) if normalized_payload.get("storage_slot_id") is not None else None
    except (TypeError, ValueError):
        next_slot_id = None
    try:
        previous_display_rank = int(existing_row.get("display_rank")) if existing_row.get("display_rank") is not None else None
    except (TypeError, ValueError):
        previous_display_rank = None
    try:
        next_display_rank = int(normalized_payload.get("display_rank")) if normalized_payload.get("display_rank") is not None else None
    except (TypeError, ValueError):
        next_display_rank = None
    should_resequence = False
    if previous_status != next_status:
        should_resequence = True
    elif previous_status == "IN_COLLECTION" and next_status == "IN_COLLECTION":
        if previous_slot_id != next_slot_id or previous_display_rank != next_display_rank:
            should_resequence = True
        elif previous_slot_id is not None and previous_slot_id == next_slot_id:
            updated_detail_row = db.get_owned_item_detail(owned_item_id)
            if db.owned_item_storage_sort_changed(existing_detail_row, updated_detail_row):
                should_resequence = True
    if should_resequence:
        db.resequence_in_collection_order()
    resequence_done_at = time.perf_counter()
    resolved_master_id, ensured_notices = _ensure_owned_item_master_link(owned_item_id)
    for msg in ensured_notices:
        text = str(msg or "").strip()
        if text and text not in notices:
            notices.append(text)
    ensure_done_at = time.perf_counter()
    next_source_code = str(normalized_payload.get("source_code") or "").strip().upper()
    next_source_external_id = str(normalized_payload.get("source_external_id") or "").strip()
    source_changed = (
        previous_source_code != next_source_code
        or previous_source_external_id != next_source_external_id
    )
    promote_done_at = ensure_done_at
    if source_changed:
        promoted_master_id, promoted_notices = _promote_owned_item_linked_master_from_discogs_source(owned_item_id)
        if promoted_master_id > 0:
            resolved_master_id = promoted_master_id
        for msg in promoted_notices:
            text = str(msg or "").strip()
            if text and text not in notices:
                notices.append(text)
        promote_done_at = time.perf_counter()
    localized_artist_name = _apply_discogs_korean_artist_name_to_owned_item(owned_item_id)
    if localized_artist_name:
        text = f"Discogs 국내 아티스트명을 한글로 정규화했습니다: {localized_artist_name}"
        if text not in notices:
            notices.append(text)

    save_total = time.perf_counter() - save_started_at
    if save_total >= OWNED_ITEM_SAVE_SLOW_SEC:
        logger.warning(
            "owned_item_save_slow owned_item_id=%s total=%.3fs normalize=%.3fs update=%.3fs resequence=%.3fs ensure=%.3fs promote=%.3fs",
            owned_item_id,
            save_total,
            normalize_done_at - save_started_at,
            update_done_at - normalize_done_at,
            resequence_done_at - update_done_at,
            ensure_done_at - resequence_done_at,
            promote_done_at - ensure_done_at,
        )

    return OwnedItemCreateResponse(
        owned_item_id=owned_item_id,
        label_id=_build_label_id(payload.category, owned_item_id),
        linked_album_master_id=resolved_master_id if resolved_master_id > 0 else None,
        notices=notices,
    )




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
from app.api.cafe import router as cafe_router, _now_playing_worker as _cafe_now_playing_worker
app.include_router(cafe_router)

# ── Backward-compatible re-exports for tests ──
from app.api.discogs_integration import get_discogs_release_collector_info, get_discogs_release_cover_preview
