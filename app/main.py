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
MUSIC_CATEGORIES = {"LP", "CD", "CASSETTE", "8TRACK", "DIGITAL", "REEL_TO_REEL"}
from .db import DOMAIN_CODES, LABEL_PREFIX_BY_CATEGORY, LEGACY_DOMAIN_CODE_MAP  # noqa: E402
RELEASE_TYPES = {"ALBUM", "EP", "SINGLE"}
SIZE_GROUP_CODES = {"STD", "BOOK", "LP", "LP10", "LP7", "OVERSIZE", "CASSETTE", "8TRACK", "REEL_TO_REEL", "GOODS"}
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
from .services.backup import AUTO_BACKUP_LOCK, AUTO_BACKUP_STOP_EVENT, AUTO_BACKUP_THREAD  # noqa: E402
SPOTIFY_BATCH_LOCK = threading.Lock()
SPOTIFY_BATCH_THREAD: threading.Thread | None = None
SPOTIFY_BATCH_LAST_RESULT: dict[str, Any] | None = None
SPOTIFY_BATCH_LAST_ERROR: str | None = None
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
    from app.services.perf_tracker import perf_track
    settings = get_settings()
    interval = max(0, int(settings.metadata_sync_interval_minutes))
    batch_limit = max(1, int(settings.metadata_sync_batch_limit))
    if interval <= 0:
        return

    while not METADATA_SYNC_STOP_EVENT.wait(interval * 60):
        try:
            with perf_track("metadata_sync", context={"batch_limit": batch_limit}):
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


# Purchase-imports routes (preview/save/webhook/list/candidates/enrich/
# create/ignore) live in app/api/purchase_imports.py, wired at the bottom
# of this module via include_router. The parsing/normalising helpers live in
# app/services/purchase_mail — see reexports above.


# Admin auth-account routes (list/create/update/delete + legacy mirrors)
# live in app/api/admin_auth_accounts.py, wired below via include_router.


from .services.home_env import (  # noqa: E402 — re-export for backward compat
    _home_assistant_api_base_url,
    _fetch_home_assistant_state,
    _coerce_home_assistant_number,
    _office_climate_comfort_label,
    _load_operator_office_climate,
    _load_operator_seoul_weather,
    _wmo_weather_code_to_desc,
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
    from app.services.perf_tracker import perf_track
    try:
        with perf_track("aladin_discogs_backfill", context={"dry_run": dry_run}):
            _run_aladin_discogs_backfill(dry_run=dry_run, sleep_sec=sleep_sec)
    except HTTPException:
        pass
    except Exception as exc:
        ALADIN_DISCOGS_BACKFILL_LAST_ERROR = f"{_now_iso()} | {exc}"
        logger.exception("aladin_discogs_backfill thread error: %s", exc)


def _spotify_batch_thread_worker(limit: int, require_tracks: bool) -> None:
    global SPOTIFY_BATCH_LAST_RESULT, SPOTIFY_BATCH_LAST_ERROR
    from app.services.spotify import SpotifyService
    from app.db.album_master_spotify import batch_match_spotify
    from app.services.perf_tracker import perf_track
    try:
        with SPOTIFY_BATCH_LOCK:
            sp = SpotifyService()
            with perf_track("spotify_batch_match", context={"limit": limit}):
                result = batch_match_spotify(sp, limit=limit, require_tracks=require_tracks)
            SPOTIFY_BATCH_LAST_RESULT = result
            SPOTIFY_BATCH_LAST_ERROR = None
    except Exception as exc:
        SPOTIFY_BATCH_LAST_ERROR = f"{_now_iso()} | {exc}"
        SPOTIFY_BATCH_LAST_RESULT = None
        logger.exception("spotify_batch thread error: %s", exc)





# ── Discogs 한국 아티스트 한글명 백필 ──
DISCOGS_KOREAN_BACKFILL_LOCK   = threading.Lock()
DISCOGS_KOREAN_BACKFILL_THREAD: threading.Thread | None = None
DISCOGS_KOREAN_BACKFILL_RESULT: dict[str, Any] | None   = None

def _discogs_korean_backfill_worker(limit: int | None) -> None:
    global DISCOGS_KOREAN_BACKFILL_RESULT
    from app.services.perf_tracker import perf_track
    try:
        with DISCOGS_KOREAN_BACKFILL_LOCK:
            with perf_track("discogs_korean_backfill", context={"limit": limit}):
                result = backfill_discogs_korean_artist_names(limit=limit)
            DISCOGS_KOREAN_BACKFILL_RESULT = {"status": "done", **result}
    except Exception as exc:
        DISCOGS_KOREAN_BACKFILL_RESULT = {"status": "error", "detail": str(exc)}
        logger.exception("discogs_korean_backfill error: %s", exc)


MANIADB_RELEASE_TYPE_BACKFILL_LOCK   = threading.Lock()
MANIADB_RELEASE_TYPE_BACKFILL_RESULT: dict[str, Any] | None = None


def _run_maniadb_release_type_backfill(limit: int = 200, sleep_sec: float = 0.3) -> dict[str, Any]:
    """ManiaDB album_master 중 release_type 미반영건을 재요청해 채운다."""
    import time as _time
    from app.services.providers import get_maniadb_master_variants

    with db.get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, source_master_id
            FROM album_master
            WHERE source_code = 'MANIADB'
              AND release_type IS NULL
            ORDER BY id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    candidates = [dict(r) for r in rows]

    updated = 0
    skipped = 0
    failed = 0
    now = _now_iso()

    for row in candidates:
        master_id = int(row["id"])
        raw_sid = str(row["source_master_id"] or "").strip()
        # source_master_id may be "145206:1" — strip variant suffix
        album_id = raw_sid.split(":")[0].strip()
        if not album_id:
            skipped += 1
            continue
        try:
            variants = get_maniadb_master_variants(album_id, limit=1)
            release_type = None
            if variants:
                release_type = str(variants[0].get("release_type") or "").strip().upper() or None
            if release_type not in ("ALBUM", "EP", "SINGLE"):
                release_type = None
            if release_type:
                with db.get_conn() as wconn:
                    wconn.execute(
                        "UPDATE album_master SET release_type = ?, updated_at = ? WHERE id = ?",
                        (release_type, now, master_id),
                    )
                updated += 1
            else:
                skipped += 1
        except Exception as exc:
            logger.warning("maniadb_release_type_backfill error id=%s: %s", master_id, exc)
            failed += 1
        if sleep_sec > 0:
            _time.sleep(sleep_sec)

    remaining = 0
    with db.get_conn() as conn:
        remaining = conn.execute(
            "SELECT COUNT(*) FROM album_master WHERE source_code='MANIADB' AND release_type IS NULL"
        ).fetchone()[0]

    return {
        "processed": len(candidates),
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
        "remaining": remaining,
    }


def _maniadb_release_type_backfill_worker(limit: int, sleep_sec: float) -> None:
    global MANIADB_RELEASE_TYPE_BACKFILL_RESULT
    try:
        with MANIADB_RELEASE_TYPE_BACKFILL_LOCK:
            result = _run_maniadb_release_type_backfill(limit=limit, sleep_sec=sleep_sec)
            MANIADB_RELEASE_TYPE_BACKFILL_RESULT = {"status": "done", **result}
    except Exception as exc:
        MANIADB_RELEASE_TYPE_BACKFILL_RESULT = {"status": "error", "detail": str(exc)}
        logger.exception("maniadb_release_type_backfill error: %s", exc)

















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
        if not released_date and source_code == "DISCOGS" and source_external_id:
            snapshot_key = (source_code, source_external_id)
            if snapshot_key not in source_snapshot_cache:
                year = get_discogs_release_year_from_cache(source_external_id)
                source_snapshot_cache[snapshot_key] = {"released_date": str(year)} if year else None
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


_OWNED_ITEM_AUDIT_FIELDS = (
    "status", "category", "release_type", "linked_album_master_id", "linked_artist_name",
    "source_code", "source_external_id", "storage_slot_id", "condition_grade", "signature_type",
    "is_second_hand", "memory_note", "notes", "purchase_price", "purchase_source",
    "acquisition_date", "size_group", "signed_by",
)


def _save_owned_item_update(
    owned_item_id: int,
    payload: OwnedItemCreate,
    existing: dict[str, Any] | None = None,
    request: Any = None,
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
    if request is not None:
        from app.security import _read_auth_username
        _before = {f: existing_row.get(f) for f in _OWNED_ITEM_AUDIT_FIELDS}
        _after = {f: normalized_payload.get(f) for f in _OWNED_ITEM_AUDIT_FIELDS}
        db.log_audit_event(
            entity_type="owned_item",
            entity_id=owned_item_id,
            action="UPDATE",
            changed_by=_read_auth_username(request),
            before=_before,
            after=_after,
        )
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
from app.api.permissions import router as permissions_router
app.include_router(permissions_router)
from app.api.activity_log import router as activity_log_router
app.include_router(activity_log_router)
from app.api.cafe import router as cafe_router, _now_playing_worker as _cafe_now_playing_worker
app.include_router(cafe_router)

# ── Backward-compatible re-exports for tests ──
from app.api.discogs_integration import get_discogs_release_collector_info, get_discogs_release_cover_preview
