#!/usr/bin/env python3
"""Weekly prod → QA DB sync (runs on the QA machine, Mac mini M4).

Pulls a consistent snapshot of the prod DB from macmini2018, verifies it,
then swaps it into the external-disk QA DB while QA is briefly stopped.

Design constraints (see CLAUDE.md):
  * The QA DB lives on the external disk (/Volumes/Data/...).
  * launchd-spawned `bash`/`scp` cannot write to the external disk (TCC),
    but this script is run by python3.12 which HAS Full Disk Access, so the
    final copy onto the external disk is done by Python itself.
  * scp only ever writes to /tmp (internal disk) to avoid the TCC block.

Run manually:
    /opt/homebrew/Caskroom/miniforge/base/bin/python3.12 \
        /Volumes/Data/Works/07.hahahoho/scripts/sync_prod_db_to_qa.py
Or via the weekly launchd job com.muzlife.qa-db-sync.
"""
from __future__ import annotations

import datetime as _dt
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import time

# ── config ───────────────────────────────────────────────────────────
PROD_HOST = "macmini2018.local"
PROD_DB = "/Users/matia/apps/hahahoho-prod/runtime/data/library.db"
PROD_TMP = "/tmp/qa_sync_prod_snapshot.db"          # snapshot on prod

QA_ROOT = "/Volumes/Data/Works/07.hahahoho"
QA_DB = f"{QA_ROOT}/data/library.db"                 # external — Python writes this
QA_DB_BACKUP_DIR = f"{QA_ROOT}/runtime/db_backups"
STAGING = "/tmp/qa_sync_staging.db"                  # internal disk

QA_LAUNCHD_LABEL = "com.muzlife.library-qa"
QA_PLIST = os.path.expanduser(f"~/Library/LaunchAgents/{QA_LAUNCHD_LABEL}.plist")
QA_HEALTH_URL = "http://localhost:8100/"

MIN_OWNED_ITEMS = 1000   # sanity floor — abort if snapshot looks empty/broken

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("qa_db_sync")


def _run(cmd: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    log.info("$ %s", " ".join(cmd))
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _gui_domain() -> str:
    return f"gui/{os.getuid()}"


def _verify_db(path: str) -> int:
    """Integrity check + return owned_item count. Raises on failure."""
    conn = sqlite3.connect(path)
    try:
        ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if ok != "ok":
            raise RuntimeError(f"integrity_check failed: {ok}")
        n = conn.execute("SELECT COUNT(*) FROM owned_item").fetchone()[0]
        return int(n)
    finally:
        conn.close()


def main() -> int:
    log.info("=== prod → QA DB sync 시작 ===")

    # 1. prod에서 일관된 스냅샷 생성 (.backup — WAL 안전)
    r = _run([
        "ssh", PROD_HOST,
        f"rm -f {PROD_TMP}; sqlite3 {PROD_DB} \".backup '{PROD_TMP}'\" && echo OK",
    ], timeout=600)
    if r.returncode != 0 or "OK" not in r.stdout:
        log.error("prod 스냅샷 실패: %s%s", r.stdout, r.stderr)
        return 1

    # 2. 스냅샷을 내장 /tmp 로만 전송 (외장 쓰기 회피)
    if os.path.exists(STAGING):
        os.remove(STAGING)
    r = _run(["scp", "-q", f"{PROD_HOST}:{PROD_TMP}", STAGING], timeout=600)
    if r.returncode != 0 or not os.path.exists(STAGING):
        log.error("scp 실패: %s%s", r.stdout, r.stderr)
        return 1
    _run(["ssh", PROD_HOST, f"rm -f {PROD_TMP}"])  # prod 임시파일 정리

    # 3. 스테이징 무결성 검증
    try:
        n_new = _verify_db(STAGING)
    except Exception as exc:
        log.error("스테이징 검증 실패: %s", exc)
        return 1
    if n_new < MIN_OWNED_ITEMS:
        log.error("스냅샷 owned_item=%d < 최소 %d — 중단", n_new, MIN_OWNED_ITEMS)
        return 1
    log.info("스테이징 검증 OK: owned_item=%d", n_new)

    # 4. QA 정지 (DB 락 해제)
    _run(["launchctl", "bootout", f"{_gui_domain()}/{QA_LAUNCHD_LABEL}"])
    time.sleep(3)

    # 5. 현재 QA DB 백업 회전 후 교체 (Python이 외장에 직접 씀 — FDA)
    try:
        os.makedirs(QA_DB_BACKUP_DIR, exist_ok=True)
        if os.path.exists(QA_DB):
            stamp = _dt.datetime.now().strftime("%Y%m%d")
            rotated = f"{QA_DB_BACKUP_DIR}/library.qa-presync.{stamp}.db"
            shutil.copy2(QA_DB, rotated)
            log.info("기존 QA DB 백업: %s", rotated)
        # WAL/SHM 잔재 제거 후 교체
        for suffix in ("-wal", "-shm"):
            p = QA_DB + suffix
            if os.path.exists(p):
                os.remove(p)
        shutil.copy2(STAGING, QA_DB)
        log.info("QA DB 교체 완료: %s", QA_DB)
    except Exception as exc:
        log.error("DB 교체 실패: %s — QA 재기동 시도", exc)
        _run(["launchctl", "bootstrap", _gui_domain(), QA_PLIST])
        return 1

    # 6. QA 재기동
    _run(["launchctl", "bootstrap", _gui_domain(), QA_PLIST])
    time.sleep(8)

    # 7. 헬스체크
    ok = False
    for _ in range(6):
        h = _run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", QA_HEALTH_URL], timeout=15)
        if h.stdout.strip() in ("200", "401"):  # 401 = 인증 동작 = 정상 기동
            ok = True
            break
        time.sleep(3)
    if not ok:
        log.error("QA 헬스체크 실패 (HTTP %s)", h.stdout.strip())
        return 1

    # 8. 정리
    try:
        os.remove(STAGING)
    except OSError:
        pass

    log.info("=== 동기화 완료: QA DB ← prod (owned_item=%d) ===", n_new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
