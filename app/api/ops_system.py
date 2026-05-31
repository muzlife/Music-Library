"""Ops system routes — sixth slice of the main.py → APIRouter split.
"""
from __future__ import annotations

import csv
import io
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse

from .. import config as config_module
from .. import db
from .. import security
from ..config import get_settings
from ..schemas import (
    AutoBackupSettingsResponse,
    AutoBackupSettingsUpdateRequest,
    DatabaseRestoreResponse,
    MetadataProviderConnectionTestResponse,
    MetadataProviderSettingsResponse,
    MetadataProviderSettingsUpdateRequest,
    OpsCollectorInfoResponse,
    OpsPlacementHintRecommendation,
    OpsPlacementHintRequest,
    OpsPlacementHintResponse,
)
from ..services import artist_context as artist_context_service

router = APIRouter()


def _main():
    from app import main as main_module
    return main_module


def _require_admin_request(request: Request) -> None:
    security._require_operator_request(request)


def _require_operator_request(request: Request) -> None:
    security._require_operator_request(request)


def _require_authenticated_request(request: Request) -> None:
    security._require_authenticated_request(request)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/catalog-stats", include_in_schema=False)
def catalog_stats() -> dict[str, int]:
    """Public endpoint — returns total owned-item count for the login page."""
    with db.get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM owned_item").fetchone()
    return {"total_items": int(row["cnt"] or 0) if row else 0}


def _external_base_url_for_request(request: Request) -> str:
    forwarded_host = str(request.headers.get("x-forwarded-host") or "").split(",", 1)[0].strip()
    host = forwarded_host or str(request.headers.get("host") or request.url.netloc or "").split(",", 1)[0].strip()
    forwarded_proto = str(request.headers.get("x-forwarded-proto") or "").split(",", 1)[0].strip().lower()
    scheme = forwarded_proto or str(request.url.scheme or "").strip().lower() or "https"
    if not host or host in {"127.0.0.1", "localhost", "testserver"}:
        return "https://library.muzlife.com"
    if scheme not in {"http", "https"}:
        scheme = "https"
    return f"{scheme}://{host}"


@router.get("/system/status")
def system_status(request: Request) -> dict[str, Any]:
    _require_operator_request(request)
    m = _main()
    sync_running = bool(m.METADATA_SYNC_LOCK.locked())
    sync_last_error = str(m.METADATA_SYNC_LAST_ERROR or "").strip()
    recent_launchd_lines = m._tail_text_lines(m.LAUNCHD_ERR_LOG_PATH, limit=2)
    qa_summary = m._read_qa_summary()
    external_base_url = _external_base_url_for_request(request)
    return {
        "health": "ok",
        "metadata_sync_running": sync_running,
        "metadata_sync_last_error": sync_last_error or None,
        "external_login_url": f"{external_base_url}/login",
        "external_health_url": f"{external_base_url}/health",
        "launchd_err_log": str(m.PROJECT_LAUNCHD_ERR_LOG_PATH),
        "recent_launchd_lines": recent_launchd_lines,
        "qa_summary": qa_summary,
    }


@router.get("/ops/export/db-backup")
def export_db_backup(request: Request, background_tasks: BackgroundTasks) -> FileResponse:
    _require_operator_request(request)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    tmp = tempfile.NamedTemporaryFile(prefix="hahahoho-library-", suffix=".db", delete=False)
    tmp_path = tmp.name
    tmp.close()
    with db.get_conn() as source_conn:
        dest_conn = sqlite3.connect(tmp_path)
        try:
            source_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    background_tasks.add_task(_cleanup_temp_file, tmp_path)
    return FileResponse(
        tmp_path,
        media_type="application/octet-stream",
        filename=f"hahahoho-library-backup-{timestamp}.db",
    )


@router.get("/ops/export/full-backup")
def export_full_backup(
    request: Request,
    background_tasks: BackgroundTasks,
    include_env_file: bool = Query(default=False),
) -> FileResponse:
    _require_operator_request(request)
    mf = _main()
    backup_settings = db.get_auto_backup_settings()
    bundle_path = mf._create_local_full_backup_bundle(
        str(backup_settings.get("backup_dir") or ""),
        reason="manual-full",
        include_env_file=include_env_file,
    )
    background_tasks.add_task(mf._cleanup_temp_file, bundle_path)
    return FileResponse(
        bundle_path,
        media_type="application/zip",
        filename=Path(bundle_path).name,
    )


@router.get("/ops/export/backup-settings", response_model=AutoBackupSettingsResponse)
def get_auto_backup_settings(request: Request) -> AutoBackupSettingsResponse:
    _require_operator_request(request)
    payload = db.get_auto_backup_settings()
    payload.update(_main()._read_backup_launchd_schedules())
    return AutoBackupSettingsResponse(**payload)


@router.post("/ops/export/backup-settings", response_model=AutoBackupSettingsResponse)
def save_auto_backup_settings(
    payload: AutoBackupSettingsUpdateRequest,
    request: Request,
) -> AutoBackupSettingsResponse:
    _require_operator_request(request)
    backup_dir = _main()._normalize_backup_dir_path(payload.backup_dir)
    Path(backup_dir).mkdir(parents=True, exist_ok=True)
    saved = db.save_auto_backup_settings(
        enabled=bool(payload.enabled),
        interval_minutes=int(payload.interval_minutes),
        backup_dir=backup_dir,
        backup_scope=str(payload.backup_scope or "DB"),
        include_env_file=bool(payload.include_env_file),
    )
    saved.update(_main()._read_backup_launchd_schedules())
    return AutoBackupSettingsResponse(**saved)


@router.get("/ops/provider-settings", response_model=MetadataProviderSettingsResponse)
def get_metadata_provider_settings(request: Request) -> MetadataProviderSettingsResponse:
    _require_operator_request(request)
    return MetadataProviderSettingsResponse(**_main()._metadata_provider_settings_payload())


@router.post("/ops/provider-settings", response_model=MetadataProviderSettingsResponse)
def save_metadata_provider_settings(
    payload: MetadataProviderSettingsUpdateRequest,
    request: Request,
) -> MetadataProviderSettingsResponse:
    _require_operator_request(request)
    updates: dict[str, str] = {}
    if payload.discogs_token is not None and payload.discogs_token.strip():
        updates["DISCOGS_TOKEN"] = payload.discogs_token.strip()
    if payload.aladin_ttb_key is not None and payload.aladin_ttb_key.strip():
        updates["ALADIN_TTB_KEY"] = payload.aladin_ttb_key.strip()
    if payload.deepl_auth_key is not None and payload.deepl_auth_key.strip():
        updates["DEEPL_AUTH_KEY"] = payload.deepl_auth_key.strip()
    if payload.discogs_user_agent is not None and payload.discogs_user_agent.strip():
        updates["DISCOGS_USER_AGENT"] = payload.discogs_user_agent.strip()
    if payload.musicbrainz_user_agent is not None and payload.musicbrainz_user_agent.strip():
        updates["MUSICBRAINZ_USER_AGENT"] = payload.musicbrainz_user_agent.strip()
    if payload.aladin_base_url is not None and payload.aladin_base_url.strip():
        updates["ALADIN_BASE_URL"] = payload.aladin_base_url.strip()
    if payload.maniadb_base_url is not None and payload.maniadb_base_url.strip():
        updates["MANIADB_BASE_URL"] = payload.maniadb_base_url.strip()
    if payload.deepl_base_url is not None and payload.deepl_base_url.strip():
        updates["DEEPL_BASE_URL"] = payload.deepl_base_url.strip()
    if updates:
        m = _main()
        env_path = config_module._default_env_path()
        m._write_env_updates(env_path, updates)
        for env_key in m._METADATA_PROVIDER_ENV_KEYS:
            if env_key in updates:
                os.environ[env_key] = updates[env_key]
        get_settings.cache_clear()
    return MetadataProviderSettingsResponse(**_main()._metadata_provider_settings_payload())


@router.post("/ops/provider-settings/deepl-test", response_model=MetadataProviderConnectionTestResponse)
def test_deepl_provider_settings(request: Request) -> MetadataProviderConnectionTestResponse:
    _require_operator_request(request)
    settings = get_settings()
    auth_key = str(settings.deepl_auth_key or "").strip()
    base_url = str(settings.deepl_base_url or "").strip()
    configured = bool(auth_key and base_url)
    if not configured:
        return MetadataProviderConnectionTestResponse(
            ok=False,
            configured=False,
            detail="DeepL 키 또는 Base URL이 설정되지 않았습니다.",
        )
    try:
        usage = artist_context_service.fetch_deepl_usage(auth_key, base_url)
        character_count = int(usage.get("character_count") or 0)
        character_limit = int(usage.get("character_limit") or 0)
        return MetadataProviderConnectionTestResponse(
            ok=True,
            configured=True,
            translated_text=f"사용량 {character_count} / {character_limit}" if character_limit else "사용량 확인",
        )
    except httpx.HTTPStatusError as err:
        status_code = err.response.status_code if err.response is not None else None
        if status_code == 403:
            detail = "DeepL 인증이 거부되었습니다. API 키 또는 Free/Pro 엔드포인트 조합을 확인하세요."
        else:
            detail = f"DeepL 호출 실패 ({status_code or 'unknown'})"
        return MetadataProviderConnectionTestResponse(
            ok=False,
            configured=True,
            detail=detail,
        )
    except Exception as err:
        return MetadataProviderConnectionTestResponse(
            ok=False,
            configured=True,
            detail=f"DeepL 연결 테스트 실패: {err}",
        )


def _csv_response(filename: str, header: list[str], rows: list[list[Any]]) -> Response:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(header)
    writer.writerows(rows)
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/ops/export/owned-items.csv")
def export_owned_items_csv(request: Request) -> Response:
    _require_operator_request(request)
    with db.get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
              oi.id,
              oi.category,
              oi.item_name_override,
              oi.status,
              oi.signature_type,
              oi.size_group,
              oi.preferred_storage_size_group,
              oi.linked_album_master_id,
              oi.purchase_source,
              oi.memory_note,
              ss.cabinet_name,
              ss.column_code,
              ss.cell_code,
              mid.artist_or_brand,
              mid.format_name,
              mid.released_date,
              mid.label_name,
              mid.catalog_no,
              mid.barcode
            FROM owned_item oi
            LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
            LEFT JOIN storage_slot ss ON ss.id = oi.storage_slot_id
            ORDER BY oi.id ASC
            """
        ).fetchall()
    csv_rows = [
        [
            row["id"], _build_label_id(str(row["category"] or ""), int(row["id"] or 0)), row["category"], row["item_name_override"], row["status"], row["signature_type"],
            row["size_group"], row["preferred_storage_size_group"], row["linked_album_master_id"], row["purchase_source"], row["memory_note"],
            row["cabinet_name"], row["column_code"], row["cell_code"], row["artist_or_brand"], row["format_name"], row["released_date"],
            row["label_name"], row["catalog_no"], row["barcode"],
        ]
        for row in rows
    ]
    return _csv_response(
        "owned-items-export.csv",
        [
            "owned_item_id", "label_id", "category", "item_name", "status", "signature_type",
            "size_group", "preferred_storage_size_group", "album_master_id", "purchase_source", "memory_note",
            "cabinet_name", "column_code", "cell_code", "artist", "format_name", "released_date",
            "label_name", "catalog_no", "barcode",
        ],
        csv_rows,
    )


@router.get("/ops/export/album-masters.csv")
def export_album_masters_csv(request: Request) -> Response:
    _require_operator_request(request)
    with db.get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
              am.id,
              am.source_code,
              am.source_master_id,
              am.title,
              am.artist_or_brand,
              am.release_year,
              COUNT(amm.id) AS member_count,
              am.updated_at
            FROM album_master am
            LEFT JOIN album_master_member amm ON amm.album_master_id = am.id
            GROUP BY am.id, am.source_code, am.source_master_id, am.title, am.artist_or_brand, am.release_year, am.updated_at
            ORDER BY am.id ASC
            """
        ).fetchall()
    csv_rows = [
        [row["id"], row["source_code"], row["source_master_id"], row["title"], row["artist_or_brand"], row["release_year"], row["member_count"], row["updated_at"]]
        for row in rows
    ]
    return _csv_response(
        "album-masters-export.csv",
        ["album_master_id", "source_code", "source_master_id", "title", "artist", "release_year", "member_count", "updated_at"],
        csv_rows,
    )


@router.get("/tool-docs/{doc_key}", include_in_schema=False)
def tool_docs(doc_key: str) -> FileResponse:
    m = _main()
    key = str(doc_key or "").strip().lower()
    path_map = {
        "erd-summary": m.PROJECT_ERD_SUMMARY_PATH,
        "erd-detail": m.PROJECT_ERD_DETAIL_PATH,
        "manual": m.PROJECT_TOOL_MANUAL_PATH,
        "go-live-checklist": m.PROJECT_GO_LIVE_CHECKLIST_PATH,
        "purchase-import": m.PROJECT_PURCHASE_IMPORT_GUIDE_PATH,
        "csv-import-sample": m.PROJECT_CSV_IMPORT_SAMPLE_PATH,
    }
    doc_path = path_map.get(key)
    if doc_path is None or not doc_path.exists():
        raise HTTPException(status_code=404, detail="document not found")
    media_type = "text/markdown; charset=utf-8"
    if doc_path.suffix.lower() == ".csv":
        media_type = "text/csv; charset=utf-8"
    return FileResponse(doc_path, media_type=media_type, filename=doc_path.name)


# ═══════════════════════════════════════════════════════════════════
# Phase N-2: Ops placement hints
# ═══════════════════════════════════════════════════════════════════

def _normalize_ops_placement_hint_reason_code(reason: Any, used_fallback_slot: bool) -> str:
    parts = [part.strip().upper() for part in str(reason or "").split("/") if part.strip()]
    if not parts:
        return "NO_HINTS"
    if any(part in {"INVALID_SIZE_GROUP", "NO_ANCHOR", "NO_SLOT"} for part in parts):
        return "NO_HINTS"
    if any(part.startswith("SAME_ARTIST") for part in parts):
        return "SAME_ARTIST"
    if any("DOMAIN" in part for part in parts):
        return "DOMAIN_MATCH"
    if any(part.startswith("ANCHOR") or part.startswith("SAME_GROUP") for part in parts):
        return "ANCHOR_PATTERN"
    if used_fallback_slot or any(part in {"ARTIST_SLOT", "LEAST_OCCUPIED_SLOT", "FALLBACK_COLLECTION_TAIL"} for part in parts):
        return "ROOMY_FALLBACK"
    return "ROOMY_FALLBACK" if any("FALLBACK" in part for part in parts) else "ANCHOR_PATTERN"


def _ops_placement_hint_reason_message(reason_code: str, slot_code: str | None, slot_display_name: str | None) -> str:
    messages = {
        "SAME_ARTIST": "같은 아티스트의 인접 배치 힌트입니다.",
        "DOMAIN_MATCH": "도메인이 맞는 위치를 우선했습니다.",
        "ANCHOR_PATTERN": "기존 배치 순서를 잇는 앵커 패턴입니다.",
        "ROOMY_FALLBACK": "여유 공간이 있는 대안 위치입니다.",
        "NO_HINTS": "추천 근거를 찾지 못했습니다.",
    }
    base_message = messages.get(str(reason_code or "").strip().upper(), "추천 근거를 계산했습니다.")
    location_label = str(slot_display_name or "").strip() or str(slot_code or "").strip()
    if location_label and reason_code != "NO_HINTS":
        return f"{base_message} ({location_label})"
    return base_message


def _build_ops_placement_hint_recommendation(
    *,
    rank: int,
    storage_slot_id: int,
    slot_code: str | None,
    slot_display_name: str | None,
    reason_code: str,
    reason_message: str,
) -> dict[str, Any]:
    clean_slot_code = str(slot_code or "").strip() or f"SLOT-{storage_slot_id}"
    clean_slot_display_name = str(slot_display_name or "").strip() or clean_slot_code
    return {
        "rank": rank,
        "storage_slot_id": storage_slot_id,
        "slot_code": clean_slot_code,
        "slot_display_name": clean_slot_display_name,
        "reason_code": reason_code,
        "reason_message": reason_message,
    }


def _build_ops_placement_hint_payload(owned_item_id: int) -> dict[str, Any]:
    item_id = int(owned_item_id or 0)
    detail_row = db.get_owned_item_detail(item_id) if item_id > 0 else None
    if not detail_row:
        return {
            "available": False,
            "recommendations": [],
            "fallback_reason": "NO_HINTS",
            "fallback_message": "추천 가능한 위치를 찾지 못했습니다.",
        }

    m = _main()
    preferred_size_group = m._preferred_storage_size_group(
        str(detail_row.get("preferred_storage_size_group") or ""),
        str(detail_row.get("size_group") or ""),
    )
    artist_or_brand = (
        m._clean_text(detail_row.get("linked_artist_name"))
        or m._clean_text(detail_row.get("artist_or_brand"))
        or m._clean_text(detail_row.get("master_artist_or_brand"))
    )
    _raw_item_name = m._clean_text(detail_row.get("item_name_override")) or m._clean_text(detail_row.get("master_title"))
    item_title = _raw_item_name
    raw_year = detail_row.get("master_release_year") if detail_row.get("master_release_year") is not None else detail_row.get("release_year")
    try:
        release_year = int(raw_year) if raw_year is not None else None
    except (TypeError, ValueError):
        release_year = None

    suggestion = db.recommend_owned_item_location(
        size_group=preferred_size_group,
        artist_or_brand=artist_or_brand,
        release_year=release_year,
        released_date=m._clean_text(detail_row.get("released_date")),
        domain_code=m._normalize_domain_code(detail_row.get("domain_code") or detail_row.get("master_domain_code")),
        item_title=item_title,
        exclude_owned_item_id=item_id,
        incoming_thickness_mm=int(detail_row["thickness_mm"]) if detail_row.get("thickness_mm") not in (None, "") else None,
        incoming_format_name=m._clean_text(detail_row.get("format_name")),
        incoming_package_hint=m._clean_text(detail_row.get("notes")),
    )
    if not suggestion:
        return {
            "available": False,
            "recommendations": [],
            "fallback_reason": "NO_HINTS",
            "fallback_message": "추천 가능한 위치를 찾지 못했습니다.",
        }

    used_fallback_slot = bool(suggestion.get("used_fallback_slot"))
    reason_code = _normalize_ops_placement_hint_reason_code(suggestion.get("reason"), used_fallback_slot)
    primary_reason_code = reason_code if reason_code != "NO_HINTS" else "ROOMY_FALLBACK"
    recommendations: list[dict[str, Any]] = []
    seen_slot_ids: set[int] = set()

    primary_slot_id = int(suggestion.get("recommended_storage_slot_id") or 0)
    if primary_slot_id > 0:
        primary_slot = db.get_storage_slot(primary_slot_id)
        primary_slot_code = str((primary_slot or {}).get("slot_code") or suggestion.get("slot_code") or "").strip()
        primary_slot_display_name = (
            str((primary_slot or {}).get("display_name") or "").strip()
            or primary_slot_code
            or f"SLOT-{primary_slot_id}"
        )
        recommendations.append(
            _build_ops_placement_hint_recommendation(
                rank=1,
                storage_slot_id=primary_slot_id,
                slot_code=primary_slot_code,
                slot_display_name=primary_slot_display_name,
                reason_code=primary_reason_code,
                reason_message=_ops_placement_hint_reason_message(
                    primary_reason_code,
                    primary_slot_code,
                    primary_slot_display_name,
                ),
            )
        )
        seen_slot_ids.add(primary_slot_id)

    candidate_reason_code = "ROOMY_FALLBACK" if primary_reason_code == "ROOMY_FALLBACK" else primary_reason_code
    for candidate in suggestion.get("candidate_slots") or []:
        if len(recommendations) >= 3 or not isinstance(candidate, dict):
            break
        storage_slot_id = int(candidate.get("storage_slot_id") or 0)
        if storage_slot_id <= 0 or storage_slot_id in seen_slot_ids:
            continue
        candidate_slot = db.get_storage_slot(storage_slot_id)
        slot_code = str(candidate.get("slot_code") or (candidate_slot or {}).get("slot_code") or "").strip()
        slot_display_name = (
            str(candidate.get("display_name") or (candidate_slot or {}).get("display_name") or "").strip()
            or slot_code
            or f"SLOT-{storage_slot_id}"
        )
        recommendations.append(
            _build_ops_placement_hint_recommendation(
                rank=len(recommendations) + 1,
                storage_slot_id=storage_slot_id,
                slot_code=slot_code,
                slot_display_name=slot_display_name,
                reason_code=candidate_reason_code,
                reason_message=_ops_placement_hint_reason_message(
                    candidate_reason_code,
                    slot_code,
                    slot_display_name,
                ),
            )
        )
        seen_slot_ids.add(storage_slot_id)

    if not recommendations:
        return {
            "available": False,
            "recommendations": [],
            "fallback_reason": reason_code,
            "fallback_message": _ops_placement_hint_reason_message(reason_code, None, None),
        }

    return {
        "available": True,
        "recommendations": recommendations,
        "fallback_reason": None,
        "fallback_message": None,
    }


@router.post("/ops/placement-hints", response_model=OpsPlacementHintResponse)
def post_ops_placement_hints(payload: OpsPlacementHintRequest, request: Request) -> OpsPlacementHintResponse:
    _require_authenticated_request(request)
    return OpsPlacementHintResponse(**_build_ops_placement_hint_payload(payload.owned_item_id))
