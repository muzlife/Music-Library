from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import subprocess
import zipfile
from pathlib import Path


ROOT = Path("/Volumes/Works/07.hahahoho")
DAILY_DB_SCRIPT = ROOT / "deploy" / "scripts" / "backup_daily_db.sh"
WEEKLY_FULL_SCRIPT = ROOT / "deploy" / "scripts" / "backup_weekly_full.sh"
GCS_UPLOAD_SCRIPT = ROOT / "deploy" / "scripts" / "upload_backup_to_gcs.sh"
DRIVE_MIRROR_SCRIPT = ROOT / "deploy" / "scripts" / "mirror_backup_to_drive.sh"
QA_SYNC_SCRIPT = ROOT / "deploy" / "scripts" / "sync_prod_backup_to_qa.sh"
BACKUP_STATUS_SCRIPT = ROOT / "deploy" / "scripts" / "backup_status.sh"
CHECK_LIBRARY_STATUS_SCRIPT = ROOT / "scripts" / "check_library_status.sh"


def _load_backup_ops_module():
    spec = importlib.util.spec_from_file_location("backup_ops_module", ROOT / "deploy" / "scripts" / "backup_ops.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _make_sample_library_db(path: Path, *, title: str = "alpha") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("create table owned_item (id integer primary key, title text)")
        conn.execute("insert into owned_item (title) values (?)", (title,))
        conn.commit()
    finally:
        conn.close()


def _make_app_root(root: Path, *, db_title: str = "alpha") -> Path:
    app_root = root / "app"
    (app_root / "runtime" / "data").mkdir(parents=True, exist_ok=True)
    (app_root / "runtime" / "backups").mkdir(parents=True, exist_ok=True)
    (app_root / "runtime" / "logs").mkdir(parents=True, exist_ok=True)
    (app_root / "app" / "static" / "uploads").mkdir(parents=True, exist_ok=True)
    db_path = app_root / "runtime" / "data" / "library.db"
    _make_sample_library_db(db_path, title=db_title)
    (app_root / ".env.local").write_text(
        "\n".join(
            [
                "APP_HOST=127.0.0.1",
                "APP_PORT=8000",
                f"LIBRARY_DB_PATH={db_path}",
                "LIBRARY_AUTH_COOKIE_SECURE=0",
            ]
        )
        + "\n",
        "utf-8",
    )
    return app_root


def _load_json(stdout: str) -> dict[str, object]:
    return json.loads(stdout.strip())


def test_daily_db_backup_skips_when_snapshot_is_unchanged(tmp_path: Path):
    app_root = _make_app_root(tmp_path, db_title="daily")

    first = subprocess.run(
        [str(DAILY_DB_SCRIPT), str(app_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    first_payload = _load_json(first.stdout)
    assert first_payload["status"] == "created"

    second = subprocess.run(
        [str(DAILY_DB_SCRIPT), str(app_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    second_payload = _load_json(second.stdout)

    backup_dir = app_root / "runtime" / "backups" / "daily-db"
    assert second_payload["status"] == "skipped"
    assert len(list(backup_dir.glob("*.db"))) == 1
    assert len(list(backup_dir.glob("*.json"))) >= 1


def test_compute_db_fingerprint_falls_back_to_file_copy_when_sqlite_snapshot_fails(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "library.db"
    _make_sample_library_db(db_path, title="fallback")
    backup_ops = _load_backup_ops_module()

    def _boom(*_args, **_kwargs):
        raise sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr(backup_ops, "_write_db_snapshot", _boom)
    fingerprint, snapshot_path = backup_ops._compute_db_fingerprint(db_path)

    try:
        assert snapshot_path != db_path
        assert fingerprint == backup_ops._sha256_file(db_path)
        assert fingerprint == backup_ops._sha256_file(snapshot_path)
    finally:
        snapshot_path.unlink(missing_ok=True)
        snapshot_path.parent.rmdir()


def test_weekly_full_backup_keeps_uploads_and_skips_when_unchanged(tmp_path: Path):
    app_root = _make_app_root(tmp_path, db_title="weekly")
    upload_path = app_root / "app" / "static" / "uploads" / "cover.jpg"
    upload_path.write_text("cover", "utf-8")

    first = subprocess.run(
        [str(WEEKLY_FULL_SCRIPT), str(app_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    first_payload = _load_json(first.stdout)
    bundle_path = Path(str(first_payload["backup_path"]))

    with zipfile.ZipFile(bundle_path) as archive:
        names = set(archive.namelist())

    second = subprocess.run(
        [str(WEEKLY_FULL_SCRIPT), str(app_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    second_payload = _load_json(second.stdout)

    backup_dir = app_root / "runtime" / "backups" / "weekly-full"
    assert first_payload["status"] == "created"
    assert "library.db" in names
    assert "uploads/cover.jpg" in names
    assert "manifest.json" in names
    assert second_payload["status"] == "skipped"
    assert len(list(backup_dir.glob("*.zip"))) == 1


def test_upload_backup_to_gcs_uploads_created_only(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gsutil_log = tmp_path / "gsutil.log"
    (bin_dir / "gsutil").write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf '%s\\n' \"$*\" >> \"$GSUTIL_LOG\"",
            ]
        )
        + "\n",
        "utf-8",
    )
    os.chmod(bin_dir / "gsutil", 0o755)
    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}", GSUTIL_LOG=str(gsutil_log))

    skipped_manifest = tmp_path / "skipped.json"
    skipped_manifest.write_text(
        json.dumps({"status": "skipped", "kind": "db", "backup_path": str(tmp_path / "missing.db")}),
        "utf-8",
    )
    skipped = subprocess.run(
        [str(GCS_UPLOAD_SCRIPT), str(skipped_manifest), "gs://test-backups/prod"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert _load_json(skipped.stdout)["status"] == "skipped"
    assert not gsutil_log.exists()

    artifact_path = tmp_path / "bundle.zip"
    artifact_path.write_text("bundle", "utf-8")
    created_manifest = tmp_path / "created.json"
    created_manifest.write_text(
        json.dumps(
            {
                "status": "created",
                "kind": "full",
                "backup_path": str(artifact_path),
                "fingerprint": "abc123",
            }
        ),
        "utf-8",
    )
    created = subprocess.run(
        [str(GCS_UPLOAD_SCRIPT), str(created_manifest), "gs://test-backups/prod"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    created_payload = _load_json(created.stdout)
    log_lines = gsutil_log.read_text("utf-8").strip().splitlines()

    assert created_payload["status"] == "uploaded"
    assert len(log_lines) == 3
    assert str(artifact_path) in log_lines[0]
    assert str(created_manifest) in log_lines[-1]


def test_drive_mirror_copies_created_backup_into_drive_scope_directory(tmp_path: Path):
    artifact_path = tmp_path / "bundle.zip"
    artifact_path.write_text("bundle", "utf-8")
    created_manifest = tmp_path / "created.json"
    created_manifest.write_text(
        json.dumps(
            {
                "status": "created",
                "scope": "weekly-full",
                "kind": "full",
                "backup_path": str(artifact_path),
                "fingerprint": "abc123",
            }
        ),
        "utf-8",
    )
    drive_root = tmp_path / "Google Drive" / "Backups"

    result = subprocess.run(
        [str(DRIVE_MIRROR_SCRIPT), str(created_manifest), str(drive_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = _load_json(result.stdout)

    assert payload["status"] == "mirrored"
    assert (drive_root / "weekly-full" / artifact_path.name).read_text("utf-8") == "bundle"
    assert (drive_root / "weekly-full" / created_manifest.name).is_file()


def test_daily_db_backup_auto_mirrors_to_google_drive_when_configured(tmp_path: Path):
    app_root = _make_app_root(tmp_path, db_title="daily")
    drive_root = tmp_path / "Google Drive" / "Backups"
    with (app_root / ".env.local").open("a", encoding="utf-8") as handle:
        handle.write(f"GOOGLE_DRIVE_BACKUP_DIR={drive_root}\n")

    result = subprocess.run(
        [str(DAILY_DB_SCRIPT), str(app_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = _load_json(result.stdout)

    mirrored_db = drive_root / "daily-db" / Path(str(payload["backup_path"])).name
    mirrored_manifest = drive_root / "daily-db" / Path(str(payload["manifest_path"])).name
    assert payload["status"] == "created"
    assert payload["drive_status"] == "mirrored"
    assert mirrored_db.is_file()
    assert mirrored_manifest.is_file()


def test_weekly_qa_sync_restores_latest_full_bundle_once(tmp_path: Path):
    prod_root = _make_app_root(tmp_path / "prod", db_title="prod-source")
    qa_root = _make_app_root(tmp_path / "qa", db_title="old-qa")
    (prod_root / "app" / "static" / "uploads" / "poster.png").write_text("poster", "utf-8")

    full = subprocess.run(
        [str(WEEKLY_FULL_SCRIPT), str(prod_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    full_payload = _load_json(full.stdout)
    prod_full_dir = Path(str(full_payload["backup_path"])).parent

    env = dict(os.environ, QA_SYNC_SKIP_RESTART="1", QA_SYNC_SKIP_VERIFY="1")
    first = subprocess.run(
        [str(QA_SYNC_SCRIPT), str(prod_full_dir), str(qa_root)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    first_payload = _load_json(first.stdout)

    conn = sqlite3.connect(qa_root / "runtime" / "data" / "library.db")
    try:
        qa_title = conn.execute("select title from owned_item order by id limit 1").fetchone()[0]
    finally:
        conn.close()

    second = subprocess.run(
        [str(QA_SYNC_SCRIPT), str(prod_full_dir), str(qa_root)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    second_payload = _load_json(second.stdout)

    assert first_payload["status"] == "applied"
    assert qa_title == "prod-source"
    assert (qa_root / "app" / "static" / "uploads" / "poster.png").read_text("utf-8") == "poster"
    assert second_payload["status"] == "skipped"


def test_weekly_qa_sync_uses_mirrored_bundle_when_manifest_points_to_prod_path(tmp_path: Path):
    prod_root = _make_app_root(tmp_path / "prod", db_title="prod-source")
    qa_root = _make_app_root(tmp_path / "qa", db_title="old-qa")
    (prod_root / "app" / "static" / "uploads" / "poster.png").write_text("poster", "utf-8")

    full = subprocess.run(
        [str(WEEKLY_FULL_SCRIPT), str(prod_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    full_payload = _load_json(full.stdout)
    prod_full_dir = Path(str(full_payload["backup_path"])).parent

    mirror_dir = tmp_path / "mirror"
    mirror_dir.mkdir(parents=True, exist_ok=True)
    bundle_name = Path(str(full_payload["backup_path"])).name
    manifest_name = Path(str(full_payload["manifest_path"])).name
    original_bundle = prod_full_dir / bundle_name
    original_manifest = prod_full_dir / manifest_name
    (mirror_dir / bundle_name).write_bytes(original_bundle.read_bytes())
    (mirror_dir / manifest_name).write_text(original_manifest.read_text("utf-8"), "utf-8")

    result = subprocess.run(
        [str(QA_SYNC_SCRIPT), str(mirror_dir), str(qa_root)],
        check=True,
        capture_output=True,
        text=True,
        env=dict(os.environ, QA_SYNC_SKIP_RESTART="1", QA_SYNC_SKIP_VERIFY="1"),
    )
    payload = _load_json(result.stdout)

    conn = sqlite3.connect(qa_root / "runtime" / "data" / "library.db")
    try:
        qa_title = conn.execute("select title from owned_item order by id limit 1").fetchone()[0]
    finally:
        conn.close()

    assert payload["status"] == "applied"
    assert qa_title == "prod-source"
    assert (qa_root / "app" / "static" / "uploads" / "poster.png").read_text("utf-8") == "poster"


def test_weekly_qa_sync_rolls_back_when_preflight_fails(tmp_path: Path):
    prod_root = _make_app_root(tmp_path / "prod", db_title="prod-source")
    qa_root = _make_app_root(tmp_path / "qa", db_title="old-qa")
    (prod_root / "app" / "static" / "uploads" / "poster.png").write_text("poster", "utf-8")
    (qa_root / "app" / "static" / "uploads" / "existing.txt").write_text("keep-me", "utf-8")
    preflight_script = qa_root / "scripts" / "run_deploy_preflight.sh"
    preflight_script.parent.mkdir(parents=True, exist_ok=True)
    preflight_script.write_text("#!/usr/bin/env bash\nexit 1\n", "utf-8")
    os.chmod(preflight_script, 0o755)

    full = subprocess.run(
        [str(WEEKLY_FULL_SCRIPT), str(prod_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    full_payload = _load_json(full.stdout)
    prod_full_dir = Path(str(full_payload["backup_path"])).parent

    result = subprocess.run(
        [str(QA_SYNC_SCRIPT), str(prod_full_dir), str(qa_root)],
        check=False,
        capture_output=True,
        text=True,
        env=dict(os.environ, QA_SYNC_SKIP_RESTART="1"),
    )

    conn = sqlite3.connect(qa_root / "runtime" / "data" / "library.db")
    try:
        qa_title = conn.execute("select title from owned_item order by id limit 1").fetchone()[0]
    finally:
        conn.close()

    assert result.returncode != 0
    assert qa_title == "old-qa"
    assert (qa_root / "app" / "static" / "uploads" / "existing.txt").read_text("utf-8") == "keep-me"
    assert not (qa_root / "app" / "static" / "uploads" / "poster.png").exists()


def test_backup_status_reports_latest_daily_full_and_qa_sync(tmp_path: Path):
    prod_root = _make_app_root(tmp_path / "prod", db_title="prod-status")
    qa_root = _make_app_root(tmp_path / "qa", db_title="qa-status")
    (prod_root / "app" / "static" / "uploads" / "cover.jpg").write_text("cover", "utf-8")

    subprocess.run(
        [str(DAILY_DB_SCRIPT), str(prod_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [str(WEEKLY_FULL_SCRIPT), str(prod_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    env = dict(os.environ, QA_SYNC_SKIP_RESTART="1", QA_SYNC_SKIP_VERIFY="1")
    subprocess.run(
        [str(QA_SYNC_SCRIPT), str(prod_root / "runtime" / "backups" / "weekly-full"), str(qa_root)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    result = subprocess.run(
        [str(BACKUP_STATUS_SCRIPT), str(prod_root), str(qa_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = _load_json(result.stdout)

    assert payload["daily_db"]["status"] in {"created", "skipped"}
    assert payload["weekly_full"]["status"] in {"created", "skipped"}
    assert payload["qa_sync"]["status"] in {"applied", "skipped"}
    assert payload["paths"]["prod_app_root"] == str(prod_root)
    assert payload["paths"]["qa_app_root"] == str(qa_root)


def test_check_library_status_short_reports_normal_summary_and_scope_states(tmp_path: Path):
    prod_root = _make_app_root(tmp_path / "prod", db_title="prod-status")
    qa_root = _make_app_root(tmp_path / "qa", db_title="qa-status")

    subprocess.run(
        [str(DAILY_DB_SCRIPT), str(prod_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [str(WEEKLY_FULL_SCRIPT), str(prod_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [str(QA_SYNC_SCRIPT), str(prod_root / "runtime" / "backups" / "weekly-full"), str(qa_root)],
        check=True,
        capture_output=True,
        text=True,
        env=dict(os.environ, QA_SYNC_SKIP_RESTART="1", QA_SYNC_SKIP_VERIFY="1"),
    )

    result = subprocess.run(
        [str(CHECK_LIBRARY_STATUS_SCRIPT), "--short", str(prod_root), str(qa_root)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "정상:" in result.stdout
    assert "daily-db=" in result.stdout
    assert "weekly-full=" in result.stdout
    assert "qa-sync=" in result.stdout


def test_check_library_status_warns_in_korean_when_backup_state_is_missing(tmp_path: Path):
    prod_root = _make_app_root(tmp_path / "prod", db_title="prod-status")
    qa_root = _make_app_root(tmp_path / "qa", db_title="qa-status")

    result = subprocess.run(
        [str(CHECK_LIBRARY_STATUS_SCRIPT), "--short", str(prod_root), str(qa_root)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "주의:" in result.stdout
    assert "AFP/외장 마운트 지연" in result.stdout
    assert "launchd 로그" in result.stdout
