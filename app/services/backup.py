from __future__ import annotations

import asyncio
import json
import plistlib
import shutil
import sqlite3
import tempfile
import threading
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .. import db
from ..config import get_settings

__all__ = [
    "AUTO_BACKUP_LOCK",
    "AUTO_BACKUP_STOP_EVENT",
    "AUTO_BACKUP_THREAD",
    "_normalize_backup_dir_path",
    "_write_db_snapshot_to_path",
    "_create_local_db_backup",
    "_create_local_full_backup_bundle",
    "_read_launchd_calendar_interval",
    "_format_launchd_schedule_label",
    "_read_backup_launchd_schedules",
    "_validate_library_db_file",
    "_restore_library_db_from_upload",
    "_restore_library_bundle_from_upload",
    "_maybe_run_auto_backup_once",
    "_auto_backup_worker",
    "_start_auto_backup_worker",
]

_SERVICES_DIR = Path(__file__).resolve().parent
_APP_DIR = _SERVICES_DIR.parent
_PROJECT_ROOT = _APP_DIR.parent
_IMAGE_UPLOAD_DIR = _APP_DIR / "static" / "uploads"

AUTO_BACKUP_LOCK = threading.Lock()
AUTO_BACKUP_STOP_EVENT = threading.Event()
AUTO_BACKUP_THREAD: threading.Thread | None = None


def _normalize_backup_dir_path(raw_value: Any) -> str:
    text = str(raw_value or "").strip()
    if not text:
        return str(Path(get_settings().db_path).resolve().parent / "backups")
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = _PROJECT_ROOT / path
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
    env_path = _PROJECT_ROOT / ".env.local"
    manifest = {
        "kind": "__PROJECT_SLUG__-library-full-backup",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "db_filename": "library.db",
        "includes_uploads": _IMAGE_UPLOAD_DIR.exists(),
        "includes_env_file": bool(include_env_file and env_path.is_file()),
    }
    try:
        _write_db_snapshot_to_path(temp_db_path)
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.write(temp_db_path, arcname="library.db")
            if _IMAGE_UPLOAD_DIR.exists():
                for file_path in sorted(p for p in _IMAGE_UPLOAD_DIR.rglob("*") if p.is_file()):
                    bundle.write(file_path, arcname=str(Path("uploads") / file_path.relative_to(_IMAGE_UPLOAD_DIR)))
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
            _PROJECT_ROOT / "deploy" / "templates" / "launchd" / "com.muzlife.backup-daily-db.plist",
        ),
        "weekly_schedule": _read_first_label(
            launch_agents_dir / "com.muzlife.backup-weekly-full.plist",
            _PROJECT_ROOT / "deploy" / "templates" / "launchd" / "com.muzlife.backup-weekly-full.plist",
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
    from app.main import METADATA_SYNC_LOCK
    if METADATA_SYNC_LOCK.locked():
        raise ValueError("메타 동기화 실행 중에는 DB 복구를 시작할 수 없습니다.")
    source_path = Path(upload_path)
    _validate_library_db_file(source_path)
    backup_settings = db.get_auto_backup_settings()
    backup_dir = _normalize_backup_dir_path(backup_settings.get("backup_dir"))
    backup_path = _create_local_db_backup(backup_dir, reason="before-restore")
    settings = get_settings()
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    staged_path = db_path.with_name(f".{db_path.name}.restore-{uuid4().hex}.tmp")
    shutil.copyfile(source_path, staged_path)
    for suffix in ("-wal", "-shm"):
        candidate = Path(f"{settings.db_path}{suffix}")
        if candidate.exists():
            candidate.unlink(missing_ok=True)
    staged_path.replace(db_path)
    db.invalidate_read_conn_cache()
    db.ensure_startup_db_ready()
    return {
        "restored": True,
        "restored_filename": str(original_filename or source_path.name or "restore.db"),
        "restored_bytes": int(source_path.stat().st_size),
        "backup_path": backup_path,
    }


def _restore_library_bundle_from_upload(upload_path: str, original_filename: str) -> dict[str, Any]:
    from app.main import METADATA_SYNC_LOCK
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

            settings = get_settings()
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
                if _IMAGE_UPLOAD_DIR.exists():
                    shutil.rmtree(_IMAGE_UPLOAD_DIR)
                if uploads_extract_root.exists():
                    _IMAGE_UPLOAD_DIR.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(uploads_extract_root), str(_IMAGE_UPLOAD_DIR))

            if has_env:
                env_target = _PROJECT_ROOT / ".env.local"
                with bundle.open(".env.local", "r") as source_env, open(env_target, "wb") as target_env:
                    shutil.copyfileobj(source_env, target_env)

            db.invalidate_read_conn_cache()
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
    last_backup_at = None
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
        import logging
        logging.getLogger(__name__).exception("auto backup worker failed")
        db.record_auto_backup_result(
            last_backup_at=last_backup_at_text or None,
            last_backup_path=str(backup_settings.get("last_backup_path") or "").strip() or None,
            last_error=f"{now_dt.astimezone(timezone.utc).isoformat()} | {exc}",
        )
        return None
    finally:
        AUTO_BACKUP_LOCK.release()


def _auto_backup_worker() -> None:
    from app.services.perf_tracker import perf_track
    while not AUTO_BACKUP_STOP_EVENT.wait(60):
        with perf_track("auto_backup"):
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
