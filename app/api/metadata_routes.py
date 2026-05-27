"""Metadata sync routes — ninth slice of main.py -> APIRouter split.
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import Any
from fastapi import APIRouter, HTTPException, Path as FastAPIPath, Query, Request
from .. import db
from .. import security
from ..schemas import (
    AudioDirectoryMappingCreateRequest,
    AudioDirectoryMappingCreateResponse,
    AudioDirectoryMappingItem,
    AudioDirectoryMappingListResponse,
    AudioDirectoryFileItem,
    AudioDirectoryFileListResponse,
    MetadataSyncRunRequest,
    MetadataSyncStatusResponse,
    MetadataSyncItemResult,
    TrackMappingBulkFromDirRequest,
    TrackMappingBulkFromDirResponse,
    TrackMappingBulkMappedItem,
    TrackMappingManualAssignRequest,
    TrackMappingManualAssignResponse,
)

router = APIRouter()

def _main():
    from app import main as main_module
    return main_module

def _require_admin(request: Request) -> None:
    security._require_operator_request(request)



@router.get("/metadata-sync/status", response_model=MetadataSyncStatusResponse)
def get_metadata_sync_status() -> MetadataSyncStatusResponse:
    running = METADATA_SYNC_LOCK.locked()
    return MetadataSyncStatusResponse(
        auto_enabled=int(settings.metadata_sync_interval_minutes) > 0,
        interval_minutes=int(settings.metadata_sync_interval_minutes),
        batch_limit=int(settings.metadata_sync_batch_limit),
        running=running,
        in_progress_items=list(METADATA_SYNC_IN_PROGRESS_ITEMS) if running else [],
        last_result=METADATA_SYNC_LAST_RESULT,
        last_error=METADATA_SYNC_LAST_ERROR,
    )


@router.post("/metadata-sync/run", status_code=202)
def run_metadata_sync(payload: MetadataSyncRunRequest) -> dict[str, Any]:
    """Start a metadata sync run in the background and return immediately (202).

    Cloudflare (and most proxies) enforce a ~100 s origin timeout, so we must
    not hold the HTTP connection open for the full sync duration.  Callers
    should poll ``GET /metadata-sync/status`` until ``running`` becomes
    ``false``, then read ``last_result`` for the outcome.
    """
    if METADATA_SYNC_LOCK.locked():
        raise HTTPException(status_code=409, detail="metadata sync already running")
    t = threading.Thread(
        target=_run_metadata_sync,
        kwargs={"payload": payload, "fail_when_running": True},
        daemon=True,
        name="metadata-sync-manual",
    )
    t.start()
    return {"started": True}


@router.post("/owned-items/{owned_item_id}/sync-metadata")
def sync_single_item_metadata(owned_item_id: int = FastAPIPath(ge=1)) -> MetadataSyncItemResult:
    """단건 상품 메타 동기화 – 즉시(동기) 실행 후 결과 반환."""
    return _main()._sync_one_item(owned_item_id)

# ═══════════════════════════════════════════════════════════════════
# Phase N-4: Audio directory + track mappings
# ═══════════════════════════════════════════════════════════════════

MUSIC_CATEGORIES = {"LP", "CD", "CASSETTE", "8TRACK", "DIGITAL", "REEL_TO_REEL"}

DEFAULT_AUDIO_EXTENSIONS = {
    "flac",
    "mp3",
    "m4a",
    "wav",
    "aac",
    "ogg",
    "opus",
    "aiff",
    "ape",
    "alac",
    "wma",
}


def _normalize_audio_extensions(values: list[str] | None) -> set[str]:
    out: set[str] = set()
    for raw in values or []:
        text = str(raw or "").strip().lower()
        if not text:
            continue
        if text.startswith("."):
            text = text[1:]
        if text:
            out.add(text)
    return out or set(DEFAULT_AUDIO_EXTENSIONS)


def _collect_audio_files(directory: Path, recursive: bool, extensions: set[str]) -> list[Path]:
    iterator = directory.rglob("*") if recursive else directory.iterdir()
    files: list[Path] = []
    for path in iterator:
        if not path.is_file():
            continue
        ext = path.suffix.lower().lstrip(".")
        if ext in extensions:
            files.append(path)
    files.sort(key=lambda p: (p.name.lower(), str(p).lower()))
    return files


def _extract_track_no_from_filename(path: Path) -> int | None:
    name = path.stem.strip()
    m = re.match(r"^\s*(\d{1,2})(?:\D|$)", name)
    if m:
        try:
            return int(m.group(1))
        except (TypeError, ValueError):
            return None

    m = re.search(r"\btrack[\s._-]*(\d{1,2})\b", name, flags=re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except (TypeError, ValueError):
            return None
    return None


def _assign_audio_files_to_tracks(track_list: list[str], files: list[Path]) -> list[Path | None]:
    track_count = len(track_list)
    assigned: list[Path | None] = [None] * track_count
    remaining: list[Path] = []

    for path in files:
        track_no = _extract_track_no_from_filename(path)
        if track_no is None or track_no <= 0 or track_no > track_count:
            remaining.append(path)
            continue
        idx = track_no - 1
        if assigned[idx] is None:
            assigned[idx] = path
        else:
            remaining.append(path)

    rem_idx = 0
    for idx in range(track_count):
        if assigned[idx] is not None:
            continue
        if rem_idx >= len(remaining):
            break
        assigned[idx] = remaining[rem_idx]
        rem_idx += 1
    return assigned


@router.get(
    "/owned-items/{owned_item_id}/audio-directory-mappings",
    response_model=AudioDirectoryMappingListResponse,
)
def get_audio_directory_mappings(owned_item_id: int) -> AudioDirectoryMappingListResponse:
    existing = db.get_owned_item(owned_item_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="owned_item not found")

    rows = db.list_owned_item_audio_directory_links(owned_item_id)
    mappings: list[AudioDirectoryMappingItem] = []
    for row in rows:
        metadata_json = row.get("metadata_json")
        metadata = metadata_json if isinstance(metadata_json, dict) else {}
        directory_path = str(metadata.get("directory_path") or row.get("file_path") or "").strip()
        if not directory_path:
            continue
        mappings.append(
            AudioDirectoryMappingItem(
                link_id=int(row["link_id"]),
                digital_asset_id=int(row["digital_asset_id"]),
                directory_path=directory_path,
                note=row.get("note"),
                created_at=str(row["created_at"]),
                metadata_json=metadata,
            )
        )

    return AudioDirectoryMappingListResponse(
        owned_item_id=owned_item_id,
        mapping_count=len(mappings),
        mappings=mappings,
    )


@router.post(
    "/owned-items/{owned_item_id}/audio-directory-mappings",
    response_model=AudioDirectoryMappingCreateResponse,
)
def create_audio_directory_mapping(
    owned_item_id: int,
    payload: AudioDirectoryMappingCreateRequest,
) -> AudioDirectoryMappingCreateResponse:
    existing = db.get_owned_item(owned_item_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="owned_item not found")
    if str(existing.get("category") or "").upper() not in MUSIC_CATEGORIES:
        raise HTTPException(status_code=400, detail="audio directory mapping is allowed only for music categories")

    directory_raw = payload.directory_path.strip()
    if not directory_raw:
        raise HTTPException(status_code=400, detail="directory_path is required")

    directory = Path(directory_raw).expanduser()
    if not directory.exists():
        raise HTTPException(status_code=400, detail=f"directory not found: {directory}")
    if not directory.is_dir():
        raise HTTPException(status_code=400, detail=f"not a directory: {directory}")

    replaced_existing_links = 0
    if payload.replace_existing:
        replaced_existing_links = db.delete_owned_item_audio_directory_links(owned_item_id)

    note_text = str(payload.note or "").strip() or None
    ids = db.insert_digital_link(
        owned_item_id,
        {
            "asset_type": "AUDIO",
            "file_path": str(directory),
            "link_type": "FULL_ALBUM",
            "track_no": None,
            "note": note_text,
            "metadata_json": {
                "source": "DIR_ONLY",
                "directory_path": str(directory),
            },
        },
    )

    return AudioDirectoryMappingCreateResponse(
        owned_item_id=owned_item_id,
        directory_path=str(directory),
        digital_asset_id=ids["digital_asset_id"],
        link_id=ids["link_id"],
        replaced_existing_links=replaced_existing_links,
    )


@router.get(
    "/owned-items/{owned_item_id}/audio-directory-files",
    response_model=AudioDirectoryFileListResponse,
)
def get_audio_directory_files(
    owned_item_id: int,
    directory_path: str | None = Query(default=None),
    recursive: bool = Query(default=True),
    limit: int = Query(default=300, ge=1, le=2000),
) -> AudioDirectoryFileListResponse:
    existing = db.get_owned_item(owned_item_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="owned_item not found")
    if str(existing.get("category") or "").upper() not in MUSIC_CATEGORIES:
        raise HTTPException(status_code=400, detail="audio directory listing is allowed only for music categories")

    selected_dir = str(directory_path or "").strip()
    if not selected_dir:
        mappings = db.list_owned_item_audio_directory_links(owned_item_id)
        if mappings:
            top = mappings[0]
            top_meta = top.get("metadata_json") if isinstance(top.get("metadata_json"), dict) else {}
            selected_dir = str(top_meta.get("directory_path") or top.get("file_path") or "").strip()

    if not selected_dir:
        raise HTTPException(status_code=400, detail="directory_path is required or mapped directory must exist")

    directory = Path(selected_dir).expanduser()
    if not directory.exists():
        raise HTTPException(status_code=400, detail=f"directory not found: {directory}")
    if not directory.is_dir():
        raise HTTPException(status_code=400, detail=f"not a directory: {directory}")

    files = _collect_audio_files(
        directory=directory,
        recursive=recursive,
        extensions=_normalize_audio_extensions(None),
    )
    total_count = len(files)
    truncated = total_count > limit
    shown_files = files[:limit]

    items: list[AudioDirectoryFileItem] = []
    for path in shown_files:
        try:
            relative = str(path.relative_to(directory))
        except ValueError:
            relative = path.name
        try:
            size_bytes = int(path.stat().st_size)
        except OSError:
            size_bytes = None
        items.append(
            AudioDirectoryFileItem(
                file_path=str(path),
                relative_path=relative,
                file_size_bytes=size_bytes,
            )
        )

    return AudioDirectoryFileListResponse(
        owned_item_id=owned_item_id,
        directory_path=str(directory),
        recursive=recursive,
        file_count=total_count,
        returned_count=len(items),
        truncated=truncated,
        files=items,
    )


@router.post(
    "/owned-items/{owned_item_id}/track-mappings/bulk-from-dir",
    response_model=TrackMappingBulkFromDirResponse,
)
def bulk_create_track_mappings_from_dir(
    owned_item_id: int,
    payload: TrackMappingBulkFromDirRequest,
) -> TrackMappingBulkFromDirResponse:
    existing = db.get_owned_item(owned_item_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="owned_item not found")

    track_list = db.get_owned_item_track_list(owned_item_id)
    if not track_list:
        raise HTTPException(status_code=400, detail="track_list not found for this owned_item")

    directory_raw = payload.directory_path.strip()
    if not directory_raw:
        raise HTTPException(status_code=400, detail="directory_path is required")
    directory = Path(directory_raw).expanduser()
    if not directory.exists():
        raise HTTPException(status_code=400, detail=f"directory not found: {directory}")
    if not directory.is_dir():
        raise HTTPException(status_code=400, detail=f"not a directory: {directory}")

    extensions = _normalize_audio_extensions(payload.extensions)
    files = _collect_audio_files(directory=directory, recursive=payload.recursive, extensions=extensions)
    if not files:
        raise HTTPException(status_code=400, detail="no audio files found in directory")

    replaced_existing_links = 0
    if payload.replace_existing:
        replaced_existing_links = db.delete_owned_item_track_links(owned_item_id)

    assignments = _assign_audio_files_to_tracks(track_list=track_list, files=files)

    mappings: list[TrackMappingBulkMappedItem] = []
    mapped_count = 0
    for idx, track_entry in enumerate(track_list, start=1):
        assigned = assignments[idx - 1]
        file_path = str(assigned) if assigned is not None else None

        if file_path:
            link_payload: dict[str, object] = {
                "asset_type": "AUDIO",
                "file_path": file_path,
                "link_type": "TRACK",
                "track_no": idx,
                "note": track_entry,
                "metadata_json": {
                    "source": "BULK_DIR",
                    "directory_path": str(directory),
                    "recursive": bool(payload.recursive),
                },
            }
            db.insert_digital_link(owned_item_id, link_payload)
            mapped_count += 1

        mappings.append(
            TrackMappingBulkMappedItem(
                track_no=idx,
                track_entry=track_entry,
                file_path=file_path,
            )
        )

    return TrackMappingBulkFromDirResponse(
        owned_item_id=owned_item_id,
        track_count=len(track_list),
        candidate_file_count=len(files),
        candidate_files=[str(path) for path in files],
        mapped_count=mapped_count,
        unmapped_track_count=max(0, len(track_list) - mapped_count),
        replaced_existing_links=replaced_existing_links,
        mappings=mappings,
    )


@router.post(
    "/owned-items/{owned_item_id}/track-mappings/manual-assign",
    response_model=TrackMappingManualAssignResponse,
)
def manual_assign_track_mappings(
    owned_item_id: int,
    payload: TrackMappingManualAssignRequest,
) -> TrackMappingManualAssignResponse:
    existing = db.get_owned_item(owned_item_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="owned_item not found")

    track_list = db.get_owned_item_track_list(owned_item_id)
    if not track_list:
        raise HTTPException(status_code=400, detail="track_list not found for this owned_item")

    track_count = len(track_list)
    assignment_by_track: dict[int, str | None] = {}
    duplicate_check: set[str] = set()
    for row in payload.assignments:
        track_no = int(row.track_no)
        if track_no < 1 or track_no > track_count:
            raise HTTPException(status_code=400, detail=f"track_no out of range: {track_no} (max={track_count})")
        if track_no in assignment_by_track:
            raise HTTPException(status_code=400, detail=f"duplicate track_no in assignments: {track_no}")

        file_path = str(row.file_path or "").strip() or None
        if file_path and not payload.allow_duplicate_files:
            if file_path in duplicate_check:
                raise HTTPException(status_code=400, detail=f"duplicate file_path in assignments: {file_path}")
            duplicate_check.add(file_path)
        assignment_by_track[track_no] = file_path

    replaced_existing_links = 0
    if payload.replace_existing:
        replaced_existing_links = db.delete_owned_item_track_links(owned_item_id)

    mappings: list[TrackMappingBulkMappedItem] = []
    mapped_count = 0
    for idx, track_entry in enumerate(track_list, start=1):
        file_path = assignment_by_track.get(idx)
        if file_path:
            db.insert_digital_link(
                owned_item_id,
                {
                    "asset_type": "AUDIO",
                    "file_path": file_path,
                    "link_type": "TRACK",
                    "track_no": idx,
                    "note": track_entry,
                    "metadata_json": {
                        "source": "MANUAL_ASSIGN",
                        "replace_existing": bool(payload.replace_existing),
                    },
                },
            )
            mapped_count += 1

        mappings.append(
            TrackMappingBulkMappedItem(
                track_no=idx,
                track_entry=track_entry,
                file_path=file_path,
            )
        )

    return TrackMappingManualAssignResponse(
        owned_item_id=owned_item_id,
        track_count=len(track_list),
        mapped_count=mapped_count,
        unmapped_track_count=max(0, len(track_list) - mapped_count),
        replaced_existing_links=replaced_existing_links,
        mappings=mappings,
    )
