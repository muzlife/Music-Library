from __future__ import annotations

import json
import os
import subprocess
import tarfile
from pathlib import Path


ROOT = Path(os.getenv("LIBRARY_PROJECT_ROOT") or Path(__file__).resolve().parents[1])
BOOTSTRAP_SCRIPT = ROOT / "deploy" / "scripts" / "bootstrap_macos_runtime.sh"
LAUNCHD_SCRIPT = ROOT / "deploy" / "scripts" / "install_launchd_service.sh"
CLOUDFLARE_SCRIPT = ROOT / "deploy" / "scripts" / "render_cloudflare_tunnel_config.sh"
RESTORE_SCRIPT = ROOT / "deploy" / "scripts" / "restore_backup_to_qa.sh"
RUN_API_SCRIPT = ROOT / "scripts" / "run_api.sh"
DEPLOY_PROD_SCRIPT = ROOT / "deploy" / "scripts" / "deploy_to_prod.sh"
DEPLOY_PROD_WORKFLOW = ROOT / ".github" / "workflows" / "deploy-production.yml"
INSTALL_BACKUP_JOBS_SCRIPT = ROOT / "deploy" / "scripts" / "install_backup_launchd_jobs.sh"
BOOTSTRAP_BACKUP_JOBS_SCRIPT = ROOT / "deploy" / "scripts" / "bootstrap_backup_launchd_jobs.sh"
GCS_PREFLIGHT_SCRIPT = ROOT / "deploy" / "scripts" / "gcs_backup_preflight.sh"
DRIVE_PREFLIGHT_SCRIPT = ROOT / "deploy" / "scripts" / "drive_backup_preflight.sh"
BACKUP_DAILY_PLIST = ROOT / "deploy" / "templates" / "launchd" / "com.muzlife.backup-daily-db.plist"
BACKUP_WEEKLY_PLIST = ROOT / "deploy" / "templates" / "launchd" / "com.muzlife.backup-weekly-full.plist"
QA_SYNC_WEEKLY_PLIST = ROOT / "deploy" / "templates" / "launchd" / "com.muzlife.qa-sync-weekly.plist"
BACKUP_SCRIPT_PATHS = (
    ROOT / "deploy" / "scripts" / "backup_daily_db.sh",
    ROOT / "deploy" / "scripts" / "backup_weekly_full.sh",
    ROOT / "deploy" / "scripts" / "upload_backup_to_gcs.sh",
    ROOT / "deploy" / "scripts" / "sync_prod_backup_to_qa.sh",
    ROOT / "deploy" / "scripts" / "install_backup_launchd_jobs.sh",
    ROOT / "deploy" / "scripts" / "bootstrap_backup_launchd_jobs.sh",
    ROOT / "deploy" / "scripts" / "gcs_backup_preflight.sh",
    ROOT / "deploy" / "scripts" / "drive_backup_preflight.sh",
    ROOT / "deploy" / "scripts" / "mirror_backup_to_drive.sh",
)


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


def test_launchd_install_script_rejects_non_isolated_prod_root(tmp_path: Path):
    app_root = tmp_path / "hahahoho"
    app_root.mkdir()
    home_dir = tmp_path / "home"
    env = dict(os.environ, HOME=str(home_dir))

    result = subprocess.run(
        [str(LAUNCHD_SCRIPT), "prod", str(app_root)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode != 0
    assert "hahahoho-prod" in result.stderr
    assert not (home_dir / "Library" / "LaunchAgents" / "com.muzlife.library-prod.plist").exists()


def test_cloudflare_render_script_writes_hostname_and_tunnel(tmp_path: Path):
    output_path = tmp_path / "library-qa.yml"

    subprocess.run(
        [str(CLOUDFLARE_SCRIPT), "qa", "tunnel-123", str(output_path), "tester"],
        check=True,
        capture_output=True,
        text=True,
    )

    text = output_path.read_text("utf-8")
    assert "qa-library.muzlife.com" in text
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
    assert (qa_root / "app" / "static" / "uploads" / "cover.jpg").read_text("utf-8") == "cover"


def test_launchd_runtime_entrypoint_script_exists():
    assert RUN_API_SCRIPT.exists()
    assert os.access(RUN_API_SCRIPT, os.X_OK)


def test_run_api_script_loads_unquoted_env_values_with_spaces(tmp_path: Path):
    app_root = tmp_path / "hahahoho-prod"
    scripts_dir = app_root / "scripts"
    python_bin = app_root / ".venv" / "bin"
    capture_path = tmp_path / "captured-drive-path.txt"
    drive_dir = tmp_path / "Google Drive" / "library_backup"

    scripts_dir.mkdir(parents=True)
    python_bin.mkdir(parents=True)
    drive_dir.mkdir(parents=True)

    run_api_copy = scripts_dir / "run_api.sh"
    run_api_copy.write_text(RUN_API_SCRIPT.read_text("utf-8"), "utf-8")
    os.chmod(run_api_copy, 0o755)

    fake_python = python_bin / "python3"
    fake_python.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf '%s\\n' \"$GOOGLE_DRIVE_BACKUP_DIR\" > \"$RUN_API_CAPTURE\"",
            ]
        )
        + "\n",
        "utf-8",
    )
    os.chmod(fake_python, 0o755)

    (app_root / ".env.local").write_text(
        f"APP_PORT=8000\n"
        f"LIBRARY_DB_PATH={app_root / 'runtime' / 'data' / 'library.db'}\n"
        f"GOOGLE_DRIVE_BACKUP_DIR={drive_dir}\n",
        "utf-8",
    )

    subprocess.run(
        [str(run_api_copy)],
        check=True,
        capture_output=True,
        text=True,
        env=dict(os.environ, RUN_API_CAPTURE=str(capture_path)),
    )

    assert capture_path.read_text("utf-8").strip() == str(drive_dir)


def test_run_api_script_rejects_prod_root_without_matching_library_db_path(tmp_path: Path):
    app_root = tmp_path / "hahahoho-prod"
    scripts_dir = app_root / "scripts"
    python_bin = app_root / ".venv" / "bin"
    capture_path = tmp_path / "captured-run.txt"

    scripts_dir.mkdir(parents=True)
    python_bin.mkdir(parents=True)

    run_api_copy = scripts_dir / "run_api.sh"
    run_api_copy.write_text(RUN_API_SCRIPT.read_text("utf-8"), "utf-8")
    os.chmod(run_api_copy, 0o755)

    fake_python = python_bin / "python3"
    fake_python.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf 'started\\n' > \"$RUN_API_CAPTURE\"",
            ]
        )
        + "\n",
        "utf-8",
    )
    os.chmod(fake_python, 0o755)

    (app_root / ".env.local").write_text(
        "APP_PORT=8000\n",
        "utf-8",
    )

    result = subprocess.run(
        [str(run_api_copy)],
        check=False,
        capture_output=True,
        text=True,
        env=dict(os.environ, RUN_API_CAPTURE=str(capture_path)),
    )

    assert result.returncode != 0
    assert "LIBRARY_DB_PATH" in result.stderr
    assert not capture_path.exists()


def test_run_api_script_rejects_qa_root_with_prod_port_and_db_path(tmp_path: Path):
    app_root = tmp_path / "hahahoho-qa"
    scripts_dir = app_root / "scripts"
    python_bin = app_root / ".venv" / "bin"
    capture_path = tmp_path / "captured-run.txt"

    scripts_dir.mkdir(parents=True)
    python_bin.mkdir(parents=True)

    run_api_copy = scripts_dir / "run_api.sh"
    run_api_copy.write_text(RUN_API_SCRIPT.read_text("utf-8"), "utf-8")
    os.chmod(run_api_copy, 0o755)

    fake_python = python_bin / "python3"
    fake_python.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf 'started\\n' > \"$RUN_API_CAPTURE\"",
            ]
        )
        + "\n",
        "utf-8",
    )
    os.chmod(fake_python, 0o755)

    (app_root / ".env.local").write_text(
        "APP_PORT=8000\n"
        "LIBRARY_DB_PATH=/Users/tester/apps/hahahoho-prod/runtime/data/library.db\n",
        "utf-8",
    )

    result = subprocess.run(
        [str(run_api_copy)],
        check=False,
        capture_output=True,
        text=True,
        env=dict(os.environ, RUN_API_CAPTURE=str(capture_path)),
    )

    assert result.returncode != 0
    assert "APP_PORT" in result.stderr or "LIBRARY_DB_PATH" in result.stderr
    assert not capture_path.exists()


def test_run_api_script_validate_only_exits_before_python_start(tmp_path: Path):
    app_root = tmp_path / "hahahoho-prod"
    scripts_dir = app_root / "scripts"
    python_bin = app_root / ".venv" / "bin"
    capture_path = tmp_path / "captured-run.txt"

    scripts_dir.mkdir(parents=True)
    python_bin.mkdir(parents=True)
    (app_root / "runtime" / "data").mkdir(parents=True)

    run_api_copy = scripts_dir / "run_api.sh"
    run_api_copy.write_text(RUN_API_SCRIPT.read_text("utf-8"), "utf-8")
    os.chmod(run_api_copy, 0o755)

    fake_python = python_bin / "python3"
    fake_python.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf 'started\\n' > \"$RUN_API_CAPTURE\"",
            ]
        )
        + "\n",
        "utf-8",
    )
    os.chmod(fake_python, 0o755)

    (app_root / ".env.local").write_text(
        f"APP_PORT=8000\nLIBRARY_DB_PATH={app_root / 'runtime' / 'data' / 'library.db'}\n",
        "utf-8",
    )

    result = subprocess.run(
        [str(run_api_copy)],
        check=True,
        capture_output=True,
        text=True,
        env=dict(os.environ, RUN_API_CAPTURE=str(capture_path), RUN_API_VALIDATE_ONLY="1"),
    )

    assert result.stdout.strip() == "runtime validation ok"
    assert not capture_path.exists()


def test_prod_deploy_script_exists_and_is_executable():
    assert DEPLOY_PROD_SCRIPT.exists()
    assert os.access(DEPLOY_PROD_SCRIPT, os.X_OK)
    text = DEPLOY_PROD_SCRIPT.read_text("utf-8")
    assert "./deploy/scripts/backup_daily_db.sh" in text
    assert "RUN_API_VALIDATE_ONLY=1 ./scripts/run_api.sh" in text
    assert 'LAUNCHD_DOMAIN=\\"gui/\\$(id -u)\\"' in text
    assert 'launchctl print \\"\\${LAUNCHD_DOMAIN}/${PROD_LAUNCHD_LABEL}\\"' in text
    assert 'launchctl kickstart -k \\"\\${LAUNCHD_DOMAIN}/${PROD_LAUNCHD_LABEL}\\"' in text
    assert 'launchctl bootstrap \\"\\${LAUNCHD_DOMAIN}\\"' in text
    assert "curl --fail --silent --show-error" in text


def test_prod_deploy_workflow_declares_manual_self_hosted_production_deploy():
    text = DEPLOY_PROD_WORKFLOW.read_text("utf-8")
    assert "workflow_dispatch:" in text
    assert "environment: production" in text
    assert "self-hosted" in text
    assert "macOS" in text
    assert "muzlife-qa" in text
    assert "./deploy/scripts/deploy_to_prod.sh" in text
    assert "qa_verified" in text


def test_backup_shell_scripts_are_executable():
    for script_path in BACKUP_SCRIPT_PATHS:
        assert script_path.exists()
        assert os.access(script_path, os.X_OK)


def test_backup_launchd_install_script_renders_three_jobs(tmp_path: Path):
    prod_root = tmp_path / "hahahoho-prod"
    qa_root = tmp_path / "hahahoho-qa"
    prod_root.mkdir()
    qa_root.mkdir()
    home_dir = tmp_path / "home"
    env = dict(os.environ, HOME=str(home_dir))

    subprocess.run(
        [str(INSTALL_BACKUP_JOBS_SCRIPT), str(prod_root), str(qa_root)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    dest_dir = home_dir / "Library" / "LaunchAgents"
    daily_text = (dest_dir / "com.muzlife.backup-daily-db.plist").read_text("utf-8")
    weekly_text = (dest_dir / "com.muzlife.backup-weekly-full.plist").read_text("utf-8")
    qa_sync_text = (dest_dir / "com.muzlife.qa-sync-weekly.plist").read_text("utf-8")

    assert str(prod_root) in daily_text
    assert str(prod_root) in weekly_text
    assert str(prod_root / "runtime" / "backups" / "weekly-full") in qa_sync_text
    assert str(qa_root) in qa_sync_text
    assert "<key>Hour</key>\n    <integer>0</integer>" in daily_text
    assert "<key>Minute</key>\n    <integer>0</integer>" in daily_text
    assert "<key>Weekday</key>\n    <integer>0</integer>" in weekly_text
    assert "<key>Hour</key>\n    <integer>1</integer>" in weekly_text
    assert "<key>Minute</key>\n    <integer>0</integer>" in weekly_text


def test_backup_launchd_install_script_rejects_non_isolated_roots(tmp_path: Path):
    prod_root = tmp_path / "hahahoho"
    qa_root = tmp_path / "qa"
    prod_root.mkdir()
    qa_root.mkdir()
    home_dir = tmp_path / "home"
    env = dict(os.environ, HOME=str(home_dir))

    result = subprocess.run(
        [str(INSTALL_BACKUP_JOBS_SCRIPT), str(prod_root), str(qa_root)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode != 0
    assert "hahahoho-prod" in result.stderr or "hahahoho-qa" in result.stderr
    assert not (home_dir / "Library" / "LaunchAgents" / "com.muzlife.backup-daily-db.plist").exists()


def test_backup_launchd_install_script_can_render_qa_only(tmp_path: Path):
    home_dir = tmp_path / "home"
    prod_root = tmp_path / "hahahoho-prod"
    qa_root = tmp_path / "hahahoho-qa"
    prod_backup_dir = tmp_path / "mirror" / "weekly-full"
    prod_root.mkdir()
    qa_root.mkdir()
    prod_backup_dir.mkdir(parents=True)
    env = dict(os.environ, HOME=str(home_dir))

    subprocess.run(
        [
            str(INSTALL_BACKUP_JOBS_SCRIPT),
            "--mode",
            "qa",
            "--prod-backup-dir",
            str(prod_backup_dir),
            str(prod_root),
            str(qa_root),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    dest_dir = home_dir / "Library" / "LaunchAgents"
    assert not (dest_dir / "com.muzlife.backup-daily-db.plist").exists()
    assert not (dest_dir / "com.muzlife.backup-weekly-full.plist").exists()
    qa_sync_path = dest_dir / "com.muzlife.qa-sync-weekly.plist"
    assert qa_sync_path.exists()
    assert str(prod_backup_dir) in qa_sync_path.read_text("utf-8")


def test_backup_launchd_bootstrap_script_calls_bootstrap_and_kickstart(tmp_path: Path):
    home_dir = tmp_path / "home"
    dest_dir = home_dir / "Library" / "LaunchAgents"
    dest_dir.mkdir(parents=True)
    for filename in (
        "com.muzlife.backup-daily-db.plist",
        "com.muzlife.backup-weekly-full.plist",
        "com.muzlife.qa-sync-weekly.plist",
    ):
        (dest_dir / filename).write_text("<plist />", "utf-8")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    launchctl_log = tmp_path / "launchctl.log"
    (bin_dir / "launchctl").write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf '%s\\n' \"$*\" >> \"$LAUNCHCTL_LOG\"",
                "exit 0",
            ]
        )
        + "\n",
        "utf-8",
    )
    os.chmod(bin_dir / "launchctl", 0o755)
    env = dict(
        os.environ,
        HOME=str(home_dir),
        PATH=f"{bin_dir}:{os.environ['PATH']}",
        LAUNCHCTL_LOG=str(launchctl_log),
    )

    subprocess.run(
        [str(BOOTSTRAP_BACKUP_JOBS_SCRIPT)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    log_lines = launchctl_log.read_text("utf-8").strip().splitlines()
    assert any("bootstrap gui/" in line and "com.muzlife.backup-daily-db.plist" in line for line in log_lines)
    assert any("bootstrap gui/" in line and "com.muzlife.backup-weekly-full.plist" in line for line in log_lines)
    assert any("bootstrap gui/" in line and "com.muzlife.qa-sync-weekly.plist" in line for line in log_lines)
    assert any("kickstart -k gui/" in line and "com.muzlife.backup-daily-db" in line for line in log_lines)
    assert any("kickstart -k gui/" in line and "com.muzlife.qa-sync-weekly" in line for line in log_lines)


def test_backup_launchd_bootstrap_script_can_start_prod_only(tmp_path: Path):
    home_dir = tmp_path / "home"
    dest_dir = home_dir / "Library" / "LaunchAgents"
    dest_dir.mkdir(parents=True)
    for filename in (
        "com.muzlife.backup-daily-db.plist",
        "com.muzlife.backup-weekly-full.plist",
        "com.muzlife.qa-sync-weekly.plist",
    ):
        (dest_dir / filename).write_text("<plist />", "utf-8")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    launchctl_log = tmp_path / "launchctl.log"
    (bin_dir / "launchctl").write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf '%s\\n' \"$*\" >> \"$LAUNCHCTL_LOG\"",
                "exit 0",
            ]
        )
        + "\n",
        "utf-8",
    )
    os.chmod(bin_dir / "launchctl", 0o755)
    env = dict(
        os.environ,
        HOME=str(home_dir),
        PATH=f"{bin_dir}:{os.environ['PATH']}",
        LAUNCHCTL_LOG=str(launchctl_log),
    )

    subprocess.run(
        [str(BOOTSTRAP_BACKUP_JOBS_SCRIPT), "--mode", "prod"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    log_lines = launchctl_log.read_text("utf-8").strip().splitlines()
    assert any("com.muzlife.backup-daily-db.plist" in line for line in log_lines)
    assert any("com.muzlife.backup-weekly-full.plist" in line for line in log_lines)
    assert not any("com.muzlife.qa-sync-weekly.plist" in line for line in log_lines)


def test_gcs_backup_preflight_reports_env_and_gsutil_readiness(tmp_path: Path):
    app_root = tmp_path / "hahahoho-prod"
    app_root.mkdir()
    env_file = app_root / ".env.local"
    env_file.write_text(
        "GCS_BACKUP_PREFIX=gs://muzlife-library-backups/prod\nGSUTIL_BIN=gsutil\n",
        "utf-8",
    )

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "gsutil").write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "if [[ \"$1\" == \"ls\" ]]; then exit 0; fi",
                "exit 0",
            ]
        )
        + "\n",
        "utf-8",
    )
    os.chmod(bin_dir / "gsutil", 0o755)
    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}")

    result = subprocess.run(
        [str(GCS_PREFLIGHT_SCRIPT), str(app_root)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "ready"
    assert payload["gcs_backup_prefix"] == "gs://muzlife-library-backups/prod"
    assert payload["gsutil_bin"].endswith("gsutil")


def test_drive_backup_preflight_reports_ready_when_google_drive_dir_is_configured(tmp_path: Path):
    app_root = tmp_path / "hahahoho-prod"
    drive_dir = tmp_path / "Google Drive" / "LibraryBackups"
    app_root.mkdir()
    drive_dir.mkdir(parents=True)
    env_file = app_root / ".env.local"
    env_file.write_text(
        f"GOOGLE_DRIVE_BACKUP_DIR={drive_dir}\n",
        "utf-8",
    )

    result = subprocess.run(
        [str(DRIVE_PREFLIGHT_SCRIPT), str(app_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "ready"
    assert payload["google_drive_backup_dir"] == str(drive_dir)


def test_backup_launchd_templates_exist_and_pass_plutil():
    for plist_path in (BACKUP_DAILY_PLIST, BACKUP_WEEKLY_PLIST, QA_SYNC_WEEKLY_PLIST):
        assert plist_path.exists()
        subprocess.run(
            ["plutil", "-lint", str(plist_path)],
            check=True,
            capture_output=True,
            text=True,
        )
