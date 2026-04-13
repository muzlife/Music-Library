from __future__ import annotations

import os
import subprocess
import tarfile
from pathlib import Path


ROOT = Path("/Volumes/Works/07.hahahoho")
BOOTSTRAP_SCRIPT = ROOT / "deploy" / "scripts" / "bootstrap_macos_runtime.sh"
LAUNCHD_SCRIPT = ROOT / "deploy" / "scripts" / "install_launchd_service.sh"
CLOUDFLARE_SCRIPT = ROOT / "deploy" / "scripts" / "render_cloudflare_tunnel_config.sh"
RESTORE_SCRIPT = ROOT / "deploy" / "scripts" / "restore_backup_to_qa.sh"


def test_bootstrap_script_creates_runtime_dirs_and_env(tmp_path: Path):
    app_root = tmp_path / "hahahoho-qa"
    result = subprocess.run(
        [str(BOOTSTRAP_SCRIPT), "qa", str(app_root)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert (app_root / "runtime" / "data").exists()
    assert (app_root / "runtime" / "uploads").exists()
    assert (app_root / "runtime" / "logs").exists()
    assert (app_root / "runtime" / "backups").exists()
    assert (app_root / "runtime" / "imports").exists()
    assert (app_root / ".env.local").exists()
    assert "Prepared runtime directories for qa" in result.stdout


def test_launchd_install_script_renders_plist_into_home(tmp_path: Path):
    app_root = tmp_path / "hahahoho-prod"
    app_root.mkdir()
    home_dir = tmp_path / "home"
    env = dict(os.environ, HOME=str(home_dir))

    subprocess.run(
        [str(LAUNCHD_SCRIPT), "prod", str(app_root)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    plist_path = home_dir / "Library" / "LaunchAgents" / "com.muzlife.library-prod.plist"
    text = plist_path.read_text("utf-8")

    assert plist_path.exists()
    assert str(app_root) in text
    assert "com.muzlife.library-prod" in text


def test_cloudflare_render_script_writes_hostname_and_tunnel(tmp_path: Path):
    output_path = tmp_path / "library-qa.yml"

    subprocess.run(
        [str(CLOUDFLARE_SCRIPT), "qa", "tunnel-123", str(output_path), "tester"],
        check=True,
        capture_output=True,
        text=True,
    )

    text = output_path.read_text("utf-8")
    assert "qa.library.muzlife.com" in text
    assert "tunnel-123" in text
    assert "/Users/tester/.cloudflared/tunnel-123.json" in text


def test_restore_backup_script_copies_db_and_extracts_uploads(tmp_path: Path):
    qa_root = tmp_path / "hahahoho-qa"
    db_backup = tmp_path / "library.db"
    db_backup.write_text("db-bytes", "utf-8")

    uploads_source = tmp_path / "uploads-src"
    uploads_dir = uploads_source / "uploads"
    uploads_dir.mkdir(parents=True)
    (uploads_dir / "cover.jpg").write_text("cover", "utf-8")
    uploads_tgz = tmp_path / "uploads.tgz"
    with tarfile.open(uploads_tgz, "w:gz") as archive:
        archive.add(uploads_dir, arcname="uploads")

    subprocess.run(
        [str(RESTORE_SCRIPT), str(qa_root), str(db_backup), str(uploads_tgz)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert (qa_root / "runtime" / "data" / "library.db").read_text("utf-8") == "db-bytes"
    assert (qa_root / "runtime" / "uploads" / "cover.jpg").read_text("utf-8") == "cover"
