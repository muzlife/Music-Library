from __future__ import annotations

import json as _json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from .. import db
from ..config import get_settings
from ..schemas import MetadataSyncItemResult, MetadataSyncRunRequest, MetadataSyncRunResponse
from ..services.candidate_search import (
    _clean_text,
    _clean_string_list,
    _clean_track_list,
    _normalize_has_obi_input,
)
from ..services.providers import get_source_release_snapshot

logger = logging.getLogger(__name__)

MUSIC_CATEGORIES = {"LP", "CD", "CASSETTE", "8TRACK", "DIGITAL", "REEL_TO_REEL"}

# ---------------------------------------------------------------------------
# Metadata sync mutable state (module-level so metadata_routes can read them)
# ---------------------------------------------------------------------------
METADATA_SYNC_LOCK = threading.Lock()
METADATA_SYNC_STOP_EVENT = threading.Event()
METADATA_SYNC_THREAD: threading.Thread | None = None
METADATA_SYNC_LAST_RESULT: MetadataSyncRunResponse | None = None
METADATA_SYNC_LAST_ERROR: str | None = None
METADATA_SYNC_IN_PROGRESS_ITEMS: list[Any] = []

# ---------------------------------------------------------------------------
# Image-download queue (populated by _run_metadata_sync, drained by thread)
# ---------------------------------------------------------------------------
_SYNC_IMAGE_QUEUE: list[tuple[int, str, str, dict[str, Any]]] = []
_SYNC_IMAGE_THREAD: threading.Thread | None = None
_SYNC_IMAGE_COUNT = 0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_db_conn():
    from app.db import get_conn
    return get_conn()


def _get_master_member_track_fallback(master_id: int, exclude_owned_item_id: int | None = None) -> list[str]:
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


def _download_images_for_item(
    owned_item_id: int,
    source_code: str,
    source_external_id: str,
    snapshot: dict[str, Any],
) -> None:
    from app.services.image_store import download_images
    static_dir = Path(__file__).resolve().parent.parent / "static"
    items = []
    cover = str(snapshot.get("cover_image_url") or "").strip()
    extra = snapshot.get("image_items") or []
    if cover:
        items.append({"type": "앞면", "uri": cover})
    if isinstance(extra, list):
        items.extend([{"type": it.get("type", "추가"), "uri": it.get("uri", "")} for it in extra if it.get("uri")])
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
            with _get_db_conn() as conn:
                conn.execute(
                    "UPDATE music_item_detail SET local_image_items_json=? WHERE owned_item_id=?",
                    (_json.dumps(result, ensure_ascii=False), owned_item_id),
                )


def _has_local_images(owned_item_id: int) -> bool:
    try:
        with _get_db_conn() as conn:
            row = conn.execute(
                "SELECT local_image_items_json FROM music_item_detail WHERE owned_item_id=?",
                (owned_item_id,),
            ).fetchone()
            if row and row[0] and row[0] not in ("[]", "null", ""):
                return True
    except Exception:
        pass
    return False


def _trigger_sync_image_download(
    owned_item_id: int,
    source_code: str,
    source_external_id: str,
    snapshot: dict[str, Any],
) -> None:
    def _run():
        try:
            _download_images_for_item(owned_item_id, source_code, source_external_id, snapshot)
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()


def _start_sync_image_download_thread() -> None:
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


def _item_meta_fields(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "display_name": _clean_text(row.get("display_name")),
        "artist_or_brand": _clean_text(row.get("artist_or_brand")),
        "catalog_no": _clean_text(row.get("catalog_no")),
    }


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
    METADATA_SYNC_IN_PROGRESS_ITEMS = []
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
        non_updated_ids: list[int] = []

        def _item_meta(row: dict[str, Any]) -> dict[str, Any]:
            return {
                "display_name": _clean_text(row.get("display_name")),
                "artist_or_brand": _clean_text(row.get("artist_or_brand")),
                "catalog_no": _clean_text(row.get("catalog_no")),
            }

        def _record(item: MetadataSyncItemResult) -> None:
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
                if _validate_barcode_checksum(barcode_digits):
                    discogs_supplement = _try_discogs_for_barcode(barcode_digits)
                    if discogs_supplement:
                        orig_text = f"{row.get('artist_or_brand') or ''} {row.get('master_title') or row.get('display_name') or ''}".strip()
                        disc_text = f"{discogs_supplement.get('artist_or_brand') or ''} {discogs_supplement.get('title') or ''}".strip()
                        sim = _token_similarity(orig_text, disc_text) if orig_text and disc_text else 0.0
                        orig_fmt = str(row.get("format_name") or "").upper()
                        disc_fmt = str(discogs_supplement.get("format_name") or "").upper()
                        fmt_ok = (not orig_fmt or not disc_fmt or orig_fmt == disc_fmt)
                        if sim < 0.85 or not fmt_ok:
                            discogs_supplement = None
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


def _sync_one_item(owned_item_id: int) -> MetadataSyncItemResult:
    candidates = db.list_metadata_sync_candidates(
        source_code=None,
        only_missing=False,
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

    discogs_supplement = None
    if source_code != "DISCOGS":
        from app.services.providers import (
            _try_discogs_for_barcode, _try_discogs_for_catalog_no,
            _token_similarity, _validate_barcode_checksum,
        )
        barcode = str(row.get("barcode") or "").strip()
        barcode_digits = barcode.replace(" ", "").replace("-", "")
        if _validate_barcode_checksum(barcode_digits):
            discogs_supplement = _try_discogs_for_barcode(barcode_digits)
            if discogs_supplement:
                orig_text = f"{row.get('artist_or_brand') or ''} {row.get('master_title') or row.get('display_name') or ''}".strip()
                disc_text = f"{discogs_supplement.get('artist_or_brand') or ''} {discogs_supplement.get('title') or ''}".strip()
                sim = _token_similarity(orig_text, disc_text) if orig_text and disc_text else 0.0
                orig_fmt = str(row.get("format_name") or "").upper()
                disc_fmt = str(discogs_supplement.get("format_name") or "").upper()
                fmt_ok = (not orig_fmt or not disc_fmt or orig_fmt == disc_fmt)
                if sim < 0.85 or not fmt_ok:
                    discogs_supplement = None
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
