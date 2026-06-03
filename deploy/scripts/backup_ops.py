#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def _load_env_file(env_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_path.is_file():
        return values
    for raw_line in env_path.read_text("utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = value.strip()
    return values


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_db_snapshot(source_db: Path, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    source_conn = sqlite3.connect(f"file:{source_db}?mode=ro", uri=True, timeout=10)
    try:
        dest_conn = sqlite3.connect(str(target_path))
        try:
            source_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        source_conn.close()


def _compute_db_fingerprint(db_path: Path) -> tuple[str, Path]:
    temp_dir = Path(tempfile.mkdtemp(prefix="__PROJECT_SLUG__-db-fingerprint-"))
    snapshot_path = temp_dir / "library.db"
    try:
        _write_db_snapshot(db_path, snapshot_path)
    except (sqlite3.Error, OSError):
        shutil.copy2(db_path, snapshot_path)
    return _sha256_file(snapshot_path), snapshot_path


def _compute_tree_fingerprint(root: Path) -> str:
    if not root.exists():
        return "empty"
    hasher = hashlib.sha256()
    for file_path in sorted(path for path in root.rglob("*") if path.is_file()):
        rel = str(file_path.relative_to(root)).replace(os.sep, "/")
        hasher.update(rel.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(_sha256_file(file_path).encode("ascii"))
        hasher.update(b"\n")
    return hasher.hexdigest()


def _compute_optional_file_fingerprint(path: Path) -> str:
    if not path.is_file():
        return "absent"
    return _sha256_file(path)


def _resolve_app_paths(app_root: Path) -> dict[str, Path]:
    env_path = app_root / ".env.local"
    env_values = _load_env_file(env_path)
    for key, value in env_values.items():
        os.environ[key] = value
    db_path = Path(env_values.get("LIBRARY_DB_PATH") or (app_root / "runtime" / "data" / "library.db"))
    if not db_path.is_absolute():
        db_path = (app_root / db_path).resolve()
    return {
        "app_root": app_root,
        "env_path": env_path,
        "db_path": db_path,
        "uploads_dir": app_root / "app" / "static" / "uploads",
        "backup_root": app_root / "runtime" / "backups",
        "state_root": app_root / "runtime" / "backups" / ".state",
    }


def _load_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text("utf-8"))


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", "utf-8")


def _prune_old_artifacts(target_dir: Path, suffix: str, keep: int) -> None:
    keep_count = max(1, int(keep))
    artifacts = sorted((path for path in target_dir.glob(f"*{suffix}") if path.is_file()), key=lambda p: p.name)
    stale = artifacts[:-keep_count]
    for artifact in stale:
        artifact.unlink(missing_ok=True)
        sidecar = artifact.with_suffix(artifact.suffix + ".json")
        sidecar.unlink(missing_ok=True)


def _build_report(
    *,
    scope: str,
    status: str,
    fingerprint: str,
    backup_path: str | None,
    manifest_path: str | None,
    previous_fingerprint: str | None = None,
    uploaded: bool = False,
    skipped_reason: str | None = None,
    source_manifest_path: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "scope": scope,
        "kind": "db" if scope == "daily-db" else "full" if scope == "weekly-full" else scope,
        "status": status,
        "fingerprint": fingerprint,
        "backup_path": backup_path,
        "manifest_path": manifest_path,
        "previous_fingerprint": previous_fingerprint,
        "created_at": _utc_now_iso(),
    }
    if uploaded:
        payload["gcs_status"] = "uploaded"
    if skipped_reason:
        payload["skipped_reason"] = skipped_reason
    if source_manifest_path:
        payload["source_manifest_path"] = source_manifest_path
    return payload


def _create_daily_db_backup(app_root: Path, *, keep: int = 30) -> dict[str, object]:
    paths = _resolve_app_paths(app_root)
    db_path = paths["db_path"]
    backup_dir = paths["backup_root"] / "daily-db"
    state_path = paths["state_root"] / "daily-db-latest.json"
    if not db_path.is_file():
        raise FileNotFoundError(f"library db not found: {db_path}")
    fingerprint, snapshot_path = _compute_db_fingerprint(db_path)
    try:
        previous = _load_json(state_path)
        previous_fingerprint = str(previous.get("fingerprint") or "") or None
        previous_backup_path = Path(str(previous.get("backup_path") or "")) if str(previous.get("backup_path") or "").strip() else None
        if previous_fingerprint == fingerprint and previous_backup_path and previous_backup_path.is_file():
            report = _build_report(
                scope="daily-db",
                status="skipped",
                fingerprint=fingerprint,
                backup_path=str(previous_backup_path),
                manifest_path=str(previous.get("manifest_path") or "") or None,
                previous_fingerprint=previous_fingerprint,
                skipped_reason="unchanged",
            )
            _write_json(state_path, report)
            return report

        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        backup_path = backup_dir / f"__PROJECT_SLUG__-library-daily-db-{timestamp}.db"
        manifest_path = backup_path.with_suffix(".db.json")
        snapshot_path.replace(backup_path)
        report = _build_report(
            scope="daily-db",
            status="created",
            fingerprint=fingerprint,
            backup_path=str(backup_path),
            manifest_path=str(manifest_path),
            previous_fingerprint=previous_fingerprint,
        )
        _write_json(manifest_path, report)
        _write_json(state_path, report)
        _prune_old_artifacts(backup_dir, ".db", keep)
        return report
    finally:
        snapshot_path.unlink(missing_ok=True)
        snapshot_path.parent.rmdir()


def _create_weekly_full_backup(app_root: Path, *, keep: int = 12, include_env_file: bool = False) -> dict[str, object]:
    paths = _resolve_app_paths(app_root)
    db_path = paths["db_path"]
    backup_dir = paths["backup_root"] / "weekly-full"
    state_path = paths["state_root"] / "weekly-full-latest.json"
    if not db_path.is_file():
        raise FileNotFoundError(f"library db not found: {db_path}")
    db_fingerprint, snapshot_path = _compute_db_fingerprint(db_path)
    try:
        uploads_fingerprint = _compute_tree_fingerprint(paths["uploads_dir"])
        env_fingerprint = _compute_optional_file_fingerprint(paths["env_path"]) if include_env_file else "excluded"
        fingerprint = _sha256_bytes(f"{db_fingerprint}|{uploads_fingerprint}|{env_fingerprint}".encode("utf-8"))
        previous = _load_json(state_path)
        previous_fingerprint = str(previous.get("fingerprint") or "") or None
        previous_backup_path = Path(str(previous.get("backup_path") or "")) if str(previous.get("backup_path") or "").strip() else None
        if previous_fingerprint == fingerprint and previous_backup_path and previous_backup_path.is_file():
            report = _build_report(
                scope="weekly-full",
                status="skipped",
                fingerprint=fingerprint,
                backup_path=str(previous_backup_path),
                manifest_path=str(previous.get("manifest_path") or "") or None,
                previous_fingerprint=previous_fingerprint,
                skipped_reason="unchanged",
            )
            _write_json(state_path, report)
            return report

        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        backup_path = backup_dir / f"__PROJECT_SLUG__-library-weekly-full-{timestamp}.zip"
        manifest_path = backup_path.with_suffix(".zip.json")
        bundle_manifest = {
            "kind": "__PROJECT_SLUG__-library-full-backup",
            "created_at": _utc_now_iso(),
            "db_filename": "library.db",
            "includes_uploads": paths["uploads_dir"].exists(),
            "includes_env_file": bool(include_env_file and paths["env_path"].is_file()),
        }
        with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot_path, arcname="library.db")
            if paths["uploads_dir"].exists():
                for file_path in sorted(path for path in paths["uploads_dir"].rglob("*") if path.is_file()):
                    archive.write(file_path, arcname=str(Path("uploads") / file_path.relative_to(paths["uploads_dir"])))
            if include_env_file and paths["env_path"].is_file():
                archive.write(paths["env_path"], arcname=".env.local")
            archive.writestr("manifest.json", json.dumps(bundle_manifest, ensure_ascii=False, separators=(",", ":")))
        report = _build_report(
            scope="weekly-full",
            status="created",
            fingerprint=fingerprint,
            backup_path=str(backup_path),
            manifest_path=str(manifest_path),
            previous_fingerprint=previous_fingerprint,
        )
        _write_json(manifest_path, report)
        _write_json(state_path, report)
        _prune_old_artifacts(backup_dir, ".zip", keep)
        return report
    finally:
        snapshot_path.unlink(missing_ok=True)
        snapshot_path.parent.rmdir()


def _upload_backup_to_gcs(manifest_path: Path, bucket_prefix: str, *, emit: bool = True) -> dict[str, object]:
    payload = _load_json(manifest_path)
    status = str(payload.get("status") or "").strip().lower()
    if status != "created":
        report = {
            "status": "skipped",
            "reason": "backup-not-created",
            "manifest_path": str(manifest_path),
        }
        if emit:
            print(json.dumps(report, ensure_ascii=False))
        return report

    artifact_path = Path(str(payload.get("backup_path") or ""))
    if not artifact_path.is_file():
        raise FileNotFoundError(f"backup artifact not found: {artifact_path}")
    gsutil_bin = os.getenv("GSUTIL_BIN") or "gsutil"
    base_prefix = bucket_prefix.rstrip("/")
    kind = str(payload.get("kind") or "backup").strip().lower()
    artifact_uri = f"{base_prefix}/{kind}/{artifact_path.name}"
    manifest_uri = f"{base_prefix}/{kind}/manifests/{manifest_path.name}"

    subprocess.run([gsutil_bin, "cp", str(artifact_path), artifact_uri], check=True)
    subprocess.run([gsutil_bin, "cp", str(manifest_path), manifest_uri], check=True)

    payload["gcs_status"] = "uploaded"
    payload["gcs_uploaded_at"] = _utc_now_iso()
    payload["gcs_artifact_uri"] = artifact_uri
    payload["gcs_manifest_uri"] = manifest_uri
    _write_json(manifest_path, payload)
    subprocess.run([gsutil_bin, "cp", str(manifest_path), manifest_uri], check=True)

    report = {
        "status": "uploaded",
        "manifest_path": str(manifest_path),
        "artifact_uri": artifact_uri,
        "manifest_uri": manifest_uri,
    }
    if emit:
        print(json.dumps(report, ensure_ascii=False))
    return report


def _mirror_backup_to_drive(manifest_path: Path, drive_root: str, *, emit: bool = True) -> dict[str, object]:
    payload = _load_json(manifest_path)
    status = str(payload.get("status") or "").strip().lower()
    if status != "created":
        report = {
            "status": "skipped",
            "manifest_path": str(manifest_path),
            "skipped_reason": "not-created",
        }
        if emit:
            print(json.dumps(report, ensure_ascii=False))
        return report

    artifact_path = Path(str(payload.get("backup_path") or ""))
    if not artifact_path.is_file():
        raise FileNotFoundError(f"backup artifact not found: {artifact_path}")

    scope = str(payload.get("scope") or "misc").strip() or "misc"
    target_dir = Path(drive_root).expanduser() / scope
    target_dir.mkdir(parents=True, exist_ok=True)

    mirrored_artifact_path = target_dir / artifact_path.name
    mirrored_manifest_path = target_dir / manifest_path.name
    shutil.copy2(artifact_path, mirrored_artifact_path)
    shutil.copy2(manifest_path, mirrored_manifest_path)

    report = {
        "status": "mirrored",
        "manifest_path": str(manifest_path),
        "drive_artifact_path": str(mirrored_artifact_path),
        "drive_manifest_path": str(mirrored_manifest_path),
    }
    if emit:
        print(json.dumps(report, ensure_ascii=False))
    return report


def _extract_full_bundle(bundle_path: Path, qa_root: Path) -> None:
    qa_db_path = qa_root / "runtime" / "data" / "library.db"
    qa_uploads_dir = qa_root / "app" / "static" / "uploads"
    qa_db_path.parent.mkdir(parents=True, exist_ok=True)
    if qa_uploads_dir.exists():
        shutil.rmtree(qa_uploads_dir)
    qa_uploads_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="__PROJECT_SLUG__-qa-sync-") as temp_dir_text:
        temp_dir = Path(temp_dir_text)
        with zipfile.ZipFile(bundle_path) as archive:
            archive.extract("library.db", path=temp_dir)
            for member in archive.namelist():
                if member.startswith("uploads/") and not member.endswith("/"):
                    archive.extract(member, path=temp_dir)
        shutil.copy2(temp_dir / "library.db", qa_db_path)
        extracted_uploads = temp_dir / "uploads"
        if extracted_uploads.exists():
            for file_path in extracted_uploads.rglob("*"):
                if file_path.is_file():
                    target = qa_uploads_dir / file_path.relative_to(extracted_uploads)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file_path, target)


def _snapshot_qa_state(qa_root: Path, snapshot_root: Path) -> None:
    qa_db_path = qa_root / "runtime" / "data" / "library.db"
    qa_uploads_dir = qa_root / "app" / "static" / "uploads"
    if qa_db_path.is_file():
        snapshot_db_path = snapshot_root / "library.db"
        snapshot_db_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(qa_db_path, snapshot_db_path)
    if qa_uploads_dir.exists():
        shutil.copytree(qa_uploads_dir, snapshot_root / "uploads")


def _restore_qa_state(qa_root: Path, snapshot_root: Path) -> None:
    qa_db_path = qa_root / "runtime" / "data" / "library.db"
    qa_uploads_dir = qa_root / "app" / "static" / "uploads"
    snapshot_db_path = snapshot_root / "library.db"
    snapshot_uploads_dir = snapshot_root / "uploads"

    qa_db_path.parent.mkdir(parents=True, exist_ok=True)
    if snapshot_db_path.is_file():
        shutil.copy2(snapshot_db_path, qa_db_path)
    else:
        qa_db_path.unlink(missing_ok=True)

    if qa_uploads_dir.exists():
        shutil.rmtree(qa_uploads_dir)
    if snapshot_uploads_dir.exists():
        shutil.copytree(snapshot_uploads_dir, qa_uploads_dir)
    else:
        qa_uploads_dir.mkdir(parents=True, exist_ok=True)


def _sync_prod_backup_to_qa(prod_full_backup_dir: Path, qa_app_root: Path) -> dict[str, object]:
    manifests = sorted(
        path
        for path in prod_full_backup_dir.glob("*.json")
        if path.is_file() and path.name.endswith(".zip.json")
    )
    if not manifests:
        raise FileNotFoundError(f"no full backup manifest found in: {prod_full_backup_dir}")
    latest_manifest_path = manifests[-1]
    latest_manifest = _load_json(latest_manifest_path)
    if str(latest_manifest.get("status") or "").strip().lower() != "created":
        raise ValueError(f"latest full backup manifest is not created: {latest_manifest_path}")
    fingerprint = str(latest_manifest.get("fingerprint") or "").strip()
    bundle_path = Path(str(latest_manifest.get("backup_path") or ""))
    if not bundle_path.is_file():
        mirrored_bundle_path = prod_full_backup_dir / bundle_path.name
        if mirrored_bundle_path.is_file():
            bundle_path = mirrored_bundle_path
        else:
            raise FileNotFoundError(f"full backup bundle not found: {bundle_path}")

    state_path = qa_app_root / "runtime" / "backups" / ".state" / "qa-sync-latest.json"
    previous = _load_json(state_path)
    if str(previous.get("fingerprint") or "").strip() == fingerprint:
        report = {
            "status": "skipped",
            "fingerprint": fingerprint,
            "source_manifest_path": str(latest_manifest_path),
            "skipped_reason": "unchanged",
        }
        _write_json(state_path, report)
        return report

    with tempfile.TemporaryDirectory(prefix="__PROJECT_SLUG__-qa-rollback-") as snapshot_text:
        snapshot_root = Path(snapshot_text)
        _snapshot_qa_state(qa_app_root, snapshot_root)
        try:
            _extract_full_bundle(bundle_path, qa_app_root)
            report = {
                "status": "applied",
                "fingerprint": fingerprint,
                "source_manifest_path": str(latest_manifest_path),
                "applied_at": _utc_now_iso(),
            }

            if os.getenv("QA_SYNC_SKIP_RESTART") != "1":
                label = os.getenv("QA_SYNC_LAUNCHD_LABEL", "com.muzlife.library-qa")
                subprocess.run(["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{label}"], check=True)

            if os.getenv("QA_SYNC_SKIP_VERIFY") != "1":
                preflight_script = qa_app_root / "scripts" / "run_deploy_preflight.sh"
                if preflight_script.is_file():
                    subprocess.run([str(preflight_script)], check=True, cwd=str(qa_app_root))

            _write_json(state_path, report)
            return report
        except Exception as exc:
            _restore_qa_state(qa_app_root, snapshot_root)
            report = {
                "status": "rolled-back",
                "fingerprint": fingerprint,
                "source_manifest_path": str(latest_manifest_path),
                "rolled_back_at": _utc_now_iso(),
                "error": str(exc),
            }
            _write_json(state_path, report)
            raise


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    daily = sub.add_parser("daily-db")
    daily.add_argument("app_root")
    daily.add_argument("--keep", type=int, default=30)

    weekly = sub.add_parser("weekly-full")
    weekly.add_argument("app_root")
    weekly.add_argument("--keep", type=int, default=12)
    weekly.add_argument("--include-env", action="store_true")

    upload = sub.add_parser("upload-gcs")
    upload.add_argument("manifest_path")
    upload.add_argument("bucket_prefix")

    drive = sub.add_parser("mirror-drive")
    drive.add_argument("manifest_path")
    drive.add_argument("drive_root")

    sync = sub.add_parser("sync-qa")
    sync.add_argument("prod_full_backup_dir")
    sync.add_argument("qa_app_root")

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    if args.command == "daily-db":
        payload = _create_daily_db_backup(Path(args.app_root), keep=args.keep)
    elif args.command == "weekly-full":
        payload = _create_weekly_full_backup(Path(args.app_root), keep=args.keep, include_env_file=bool(args.include_env))
    elif args.command == "upload-gcs":
        payload = _upload_backup_to_gcs(Path(args.manifest_path), args.bucket_prefix)
        if payload.get("status") == "uploaded":
            return 0
        return 0
    elif args.command == "mirror-drive":
        payload = _mirror_backup_to_drive(Path(args.manifest_path), args.drive_root)
        if payload.get("status") == "mirrored":
            return 0
        return 0
    elif args.command == "sync-qa":
        payload = _sync_prod_backup_to_qa(Path(args.prod_full_backup_dir), Path(args.qa_app_root))
    else:
        raise ValueError(f"unsupported command: {args.command}")
    manifest_path = str(payload.get("manifest_path") or "").strip()
    drive_backup_dir = str(os.getenv("GOOGLE_DRIVE_BACKUP_DIR") or "").strip()
    if drive_backup_dir and manifest_path and str(payload.get("status") or "").strip().lower() == "created":
        drive_report = _mirror_backup_to_drive(Path(manifest_path), drive_backup_dir, emit=False)
        payload["drive_status"] = drive_report.get("status")
        payload["drive_artifact_path"] = drive_report.get("drive_artifact_path")
        payload["drive_manifest_path"] = drive_report.get("drive_manifest_path")
    gcs_prefix = str(os.getenv("GCS_BACKUP_PREFIX") or "").strip()
    if gcs_prefix and manifest_path and str(payload.get("status") or "").strip().lower() == "created":
        upload_report = _upload_backup_to_gcs(Path(manifest_path), gcs_prefix, emit=False)
        payload["gcs_status"] = upload_report.get("status")
        payload["gcs_artifact_uri"] = upload_report.get("artifact_uri")
        payload["gcs_manifest_uri"] = upload_report.get("manifest_uri")
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
