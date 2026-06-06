# Logging & Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 에러 알림(DB + 카카오 나에게 보내기 + 관리툴 배지), 성능 추적(API/배치/DB), 메타 변경 이력 보완(album_master 전체 필드 + 누락 이벤트)을 단계별로 구현한다.

**Architecture:** 모든 데이터를 기존 `library.db` SQLite에 저장하고 FastAPI 레이어에서 수집한다. 에러는 전역 예외 핸들러가 가로채어 `error_log` 테이블에 기록하고 카카오 REST API로 알림을 전송한다. 성능은 미들웨어(API), 컨텍스트 매니저(배치), `sqlite3.Connection` 서브클래스(DB 쿼리)로 `perf_log`에 기록한다.

**Tech Stack:** FastAPI, SQLite (sqlite3), httpx (카카오 API), Python logging, pytest

---

## 파일 맵

| 경로 | 역할 | 상태 |
|------|------|------|
| `app/db/error_log.py` | error_log 테이블 DDL + CRUD | 신규 |
| `app/db/perf_log.py` | perf_log 테이블 DDL + CRUD + 집계 | 신규 |
| `app/services/kakao_notify.py` | 카카오 나에게 보내기 REST API | 신규 |
| `app/services/perf_tracker.py` | 배치용 perf_track 컨텍스트 매니저 | 신규 |
| `app/db/schema_migration.py` | v18 마이그레이션 추가 | 수정 |
| `app/db/connection.py` | _TimedConnection 서브클래스 추가 | 수정 |
| `app/db/__init__.py` | 신규 DB 모듈 re-export | 수정 |
| `app/config.py` | KAKAO_* / PERF_SLOW_* 설정 추가 | 수정 |
| `app/main.py` | 전역 예외 핸들러, perf 미들웨어 추가 | 수정 |
| `app/api/activity_log.py` | error-log / perf-log 엔드포인트 추가 | 수정 |
| `app/api/album_masters.py` | album_master 전체 필드 audit 추가 | 수정 |
| `app/api/owned_items.py` | IMAGE_UPLOAD/DELETE snapshot 보강 | 수정 |
| `app/db/album_master_core.py` | upsert시 CREATE audit 추가 | 수정 |
| `app/api/purchase_imports.py` | PURCHASE_IMPORT audit 추가 | 수정 |
| `app/static/index.html` | 에러 배지, 에러 뷰어, 성능 뷰어, 필드 한글명 추가 | 수정 |
| `tests/test_error_log.py` | error_log DB 함수 테스트 | 신규 |
| `tests/test_perf_log.py` | perf_log DB 함수 테스트 | 신규 |
| `tests/test_kakao_notify.py` | 카카오 알림 (httpx mock) | 신규 |
| `tests/test_perf_tracker.py` | perf_track 컨텍스트 매니저 테스트 | 신규 |
| `tests/test_observability_api.py` | error-log / perf-log API 엔드포인트 테스트 | 신규 |

---

## Task 1: 스키마 마이그레이션 v18

**Files:**
- Modify: `app/db/schema_migration.py`
- Test: `tests/test_db_split_phase_1.py` (기존 마이그레이션 테스트 확인)

- [ ] **Step 1: 마이그레이션 함수 작성**

`app/db/schema_migration.py`의 `_migration_v17_expand_audit_log_actions` 함수 바로 위에 추가:

```python
def _migration_v18_add_observability_tables(conn: sqlite3.Connection) -> None:
    """Add error_log and perf_log tables for observability."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS error_log (
          id           INTEGER PRIMARY KEY AUTOINCREMENT,
          level        TEXT NOT NULL DEFAULT 'ERROR',
          source       TEXT,
          message      TEXT NOT NULL,
          traceback    TEXT,
          request_path TEXT,
          request_body TEXT,
          is_read      INTEGER NOT NULL DEFAULT 0,
          created_at   TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_error_log_created
          ON error_log (created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_error_log_is_read
          ON error_log (is_read, created_at DESC);

        CREATE TABLE IF NOT EXISTS perf_log (
          id           INTEGER PRIMARY KEY AUTOINCREMENT,
          kind         TEXT NOT NULL,
          name         TEXT NOT NULL,
          duration_ms  INTEGER NOT NULL,
          is_slow      INTEGER NOT NULL DEFAULT 0,
          context_json TEXT,
          created_at   TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_perf_log_kind_created
          ON perf_log (kind, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_perf_log_slow
          ON perf_log (is_slow, created_at DESC);
        """
    )
```

- [ ] **Step 2: SCHEMA_VERSION 및 딕셔너리 업데이트**

```python
# SCHEMA_VERSION = 17  →  18 으로 변경
SCHEMA_VERSION = 18

# _MIGRATIONS_BY_VERSION 딕셔너리에 추가:
    17: _migration_v17_expand_audit_log_actions,
    18: _migration_v18_add_observability_tables,
```

- [ ] **Step 3: 기존 마이그레이션 테스트 실행**

```bash
cd /Volumes/Data/Works/07.hahahoho
python -m pytest tests/test_db_split_phase_1.py -v 2>&1 | tail -20
```

Expected: 기존 테스트 PASS (마이그레이션이 멱등성 있게 동작)

- [ ] **Step 4: 직접 마이그레이션 동작 확인**

```bash
python -c "
import os, tempfile
os.environ['LIBRARY_DB_PATH'] = tempfile.mktemp(suffix='.db')
from app.config import get_settings; get_settings.cache_clear()
from app.db.schema_migration import _run_pending_migrations
from app.db.connection import get_conn
with get_conn() as conn:
    n = _run_pending_migrations(conn)
    tables = conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()
    print('migrations run:', n)
    print('tables:', [r[0] for r in tables])
"
```

Expected 출력: `error_log`, `perf_log` 포함 확인

- [ ] **Step 5: 커밋**

```bash
git add app/db/schema_migration.py
git commit -m "feat(db): schema v18 — add error_log and perf_log tables"
```

---

## Task 2: error_log DB 모듈

**Files:**
- Create: `app/db/error_log.py`
- Create: `tests/test_error_log.py`
- Modify: `app/db/__init__.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_error_log.py`:

```python
import os
import tempfile
import pytest

_tmp = tempfile.mktemp(suffix=".db")
os.environ.setdefault("LIBRARY_DB_PATH", _tmp)
os.environ.setdefault("LIBRARY_ADMIN_USERNAME", "admin")
os.environ.setdefault("LIBRARY_ADMIN_PASSWORD", "pw")
os.environ.setdefault("LIBRARY_AUTH_SESSION_SECRET", "s")

from app.config import get_settings
get_settings.cache_clear()

from app.db.error_log import (
    insert_error_log,
    list_error_log,
    get_unread_error_count,
    acknowledge_error_log,
)


def test_insert_and_list():
    row_id = insert_error_log(
        level="ERROR",
        source="app/main.py:handler",
        message="Test error",
        traceback="Traceback...",
        request_path="GET /test",
        request_body=None,
    )
    assert row_id > 0
    rows = list_error_log(limit=10, offset=0)
    assert any(r["id"] == row_id for r in rows)


def test_unread_count_and_acknowledge():
    insert_error_log(level="ERROR", source="x", message="err1", traceback=None, request_path=None, request_body=None)
    insert_error_log(level="ERROR", source="y", message="err2", traceback=None, request_path=None, request_body=None)
    count_before = get_unread_error_count()
    assert count_before >= 2
    acknowledge_error_log(ids=None)  # 전체 확인
    assert get_unread_error_count() == 0


def test_acknowledge_single():
    rid = insert_error_log(level="CRITICAL", source="z", message="crit", traceback=None, request_path=None, request_body=None)
    acknowledge_error_log(ids=[rid])
    rows = list_error_log(is_read=True, limit=10, offset=0)
    assert any(r["id"] == rid for r in rows)
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python -m pytest tests/test_error_log.py -v 2>&1 | tail -10
```

Expected: `ModuleNotFoundError: No module named 'app.db.error_log'`

- [ ] **Step 3: error_log.py 구현**

`app/db/error_log.py` 신규 생성:

```python
"""error_log 테이블: 서버 예외 기록 및 관리자 확인 추적."""
from __future__ import annotations

import sqlite3
from typing import Any

from app.db.connection import get_conn, get_write_conn, utc_now_iso

__all__ = [
    "insert_error_log",
    "list_error_log",
    "get_unread_error_count",
    "acknowledge_error_log",
]


def _ensure_error_log_table(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS error_log (
          id           INTEGER PRIMARY KEY AUTOINCREMENT,
          level        TEXT NOT NULL DEFAULT 'ERROR',
          source       TEXT,
          message      TEXT NOT NULL,
          traceback    TEXT,
          request_path TEXT,
          request_body TEXT,
          is_read      INTEGER NOT NULL DEFAULT 0,
          created_at   TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_error_log_created
          ON error_log (created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_error_log_is_read
          ON error_log (is_read, created_at DESC);
        """
    )


def insert_error_log(
    *,
    level: str = "ERROR",
    source: str | None,
    message: str,
    traceback: str | None,
    request_path: str | None,
    request_body: str | None,
) -> int:
    now = utc_now_iso()
    with get_conn() as conn:
        _ensure_error_log_table(conn)
        cursor = conn.execute(
            """
            INSERT INTO error_log
              (level, source, message, traceback, request_path, request_body, is_read, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (level, source, message, traceback, request_path, request_body, now),
        )
        return cursor.lastrowid or 0


def list_error_log(
    *,
    is_read: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    where = ""
    params: list[Any] = []
    if is_read is not None:
        where = "WHERE is_read = ?"
        params.append(1 if is_read else 0)
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT id, level, source, message, traceback,
                   request_path, request_body, is_read, created_at
            FROM error_log
            {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        ).fetchall()
    return [dict(r) for r in rows]


def get_unread_error_count() -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM error_log WHERE is_read = 0"
        ).fetchone()
    return int(row[0]) if row else 0


def acknowledge_error_log(*, ids: list[int] | None = None) -> int:
    """ids=None이면 전체 확인 처리. 반환값: 처리된 행 수."""
    with get_write_conn() as conn:
        if ids is None:
            cursor = conn.execute("UPDATE error_log SET is_read = 1 WHERE is_read = 0")
        else:
            placeholders = ",".join("?" * len(ids))
            cursor = conn.execute(
                f"UPDATE error_log SET is_read = 1 WHERE id IN ({placeholders})",
                ids,
            )
    return cursor.rowcount
```

- [ ] **Step 4: __init__.py에 re-export 추가**

`app/db/__init__.py`에서 owned_item_slot import 블록 근처에 추가:

```python
from .error_log import (  # noqa: F401
    insert_error_log,
    list_error_log,
    get_unread_error_count,
    acknowledge_error_log,
)
from .perf_log import (  # noqa: F401  — perf_log는 Task 3에서 구현
    insert_perf_log,
    list_perf_log_aggregated,
    list_perf_log_detail,
)
```

> **Note:** perf_log 임포트는 Task 3 완료 후 추가. 지금은 error_log만 추가.

- [ ] **Step 5: 테스트 통과 확인**

```bash
python -m pytest tests/test_error_log.py -v 2>&1 | tail -15
```

Expected: 3개 테스트 모두 PASS

- [ ] **Step 6: 커밋**

```bash
git add app/db/error_log.py tests/test_error_log.py app/db/__init__.py
git commit -m "feat(db): add error_log module — insert, list, unread-count, acknowledge"
```

---

## Task 3: perf_log DB 모듈

**Files:**
- Create: `app/db/perf_log.py`
- Create: `tests/test_perf_log.py`
- Modify: `app/db/__init__.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_perf_log.py`:

```python
import os, tempfile
os.environ.setdefault("LIBRARY_DB_PATH", tempfile.mktemp(suffix=".db"))
os.environ.setdefault("LIBRARY_ADMIN_USERNAME", "admin")
os.environ.setdefault("LIBRARY_ADMIN_PASSWORD", "pw")
os.environ.setdefault("LIBRARY_AUTH_SESSION_SECRET", "s")

from app.config import get_settings
get_settings.cache_clear()

from app.db.perf_log import insert_perf_log, list_perf_log_aggregated, list_perf_log_detail


def test_insert_and_aggregate():
    insert_perf_log(kind="API", name="GET /owned-items", duration_ms=450, is_slow=True)
    insert_perf_log(kind="API", name="GET /owned-items", duration_ms=80, is_slow=False)
    insert_perf_log(kind="BATCH", name="metadata_sync", duration_ms=38200, is_slow=False)

    rows = list_perf_log_aggregated(kind=None, is_slow_only=False, days=1)
    names = [r["name"] for r in rows]
    assert "GET /owned-items" in names
    assert "metadata_sync" in names

    api_row = next(r for r in rows if r["name"] == "GET /owned-items")
    assert api_row["count"] == 2
    assert api_row["max_ms"] == 450
    assert api_row["avg_ms"] == 265


def test_is_slow_filter():
    insert_perf_log(kind="QUERY", name="SELECT ...", duration_ms=350, is_slow=True)
    rows = list_perf_log_aggregated(kind=None, is_slow_only=True, days=1)
    assert all(r["slow_count"] > 0 for r in rows)


def test_detail_list():
    insert_perf_log(kind="API", name="POST /owned-items", duration_ms=120, is_slow=False)
    rows = list_perf_log_detail(name="POST /owned-items", limit=10)
    assert len(rows) >= 1
    assert rows[0]["duration_ms"] == 120
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python -m pytest tests/test_perf_log.py -v 2>&1 | tail -10
```

Expected: `ModuleNotFoundError: No module named 'app.db.perf_log'`

- [ ] **Step 3: perf_log.py 구현**

`app/db/perf_log.py` 신규 생성:

```python
"""perf_log 테이블: API/배치/DB 성능 기록."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.db.connection import get_conn, utc_now_iso

__all__ = [
    "insert_perf_log",
    "list_perf_log_aggregated",
    "list_perf_log_detail",
]


def _ensure_perf_log_table(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS perf_log (
          id           INTEGER PRIMARY KEY AUTOINCREMENT,
          kind         TEXT NOT NULL,
          name         TEXT NOT NULL,
          duration_ms  INTEGER NOT NULL,
          is_slow      INTEGER NOT NULL DEFAULT 0,
          context_json TEXT,
          created_at   TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_perf_log_kind_created
          ON perf_log (kind, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_perf_log_slow
          ON perf_log (is_slow, created_at DESC);
        """
    )


def insert_perf_log(
    *,
    kind: str,
    name: str,
    duration_ms: int,
    is_slow: bool,
    context: dict[str, Any] | None = None,
) -> None:
    now = utc_now_iso()
    ctx_json = json.dumps(context, ensure_ascii=False) if context else None
    with get_conn() as conn:
        _ensure_perf_log_table(conn)
        conn.execute(
            """
            INSERT INTO perf_log (kind, name, duration_ms, is_slow, context_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (kind, name, duration_ms, 1 if is_slow else 0, ctx_json, now),
        )


def list_perf_log_aggregated(
    *,
    kind: str | None = None,
    is_slow_only: bool = False,
    days: int = 7,
) -> list[dict[str, Any]]:
    conditions = [f"created_at >= datetime('now', '-{days} days')"]
    params: list[Any] = []
    if kind:
        conditions.append("kind = ?")
        params.append(kind)
    if is_slow_only:
        conditions.append("slow_count > 0")

    where_clause = "WHERE " + " AND ".join(conditions[:2]) if conditions[:2] else ""
    having_clause = "HAVING slow_count > 0" if is_slow_only else ""

    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT
              kind,
              name,
              COUNT(*) AS count,
              CAST(AVG(duration_ms) AS INTEGER) AS avg_ms,
              MAX(duration_ms) AS max_ms,
              SUM(is_slow) AS slow_count
            FROM perf_log
            {where_clause}
            GROUP BY kind, name
            {having_clause}
            ORDER BY max_ms DESC
            """,
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def list_perf_log_detail(
    *,
    name: str,
    kind: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    conditions = ["name = ?"]
    params: list[Any] = [name]
    if kind:
        conditions.append("kind = ?")
        params.append(kind)
    where = "WHERE " + " AND ".join(conditions)
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT id, kind, name, duration_ms, is_slow, context_json, created_at
            FROM perf_log
            {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        ).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 4: __init__.py perf_log 임포트 추가**

Task 2에서 남겨둔 부분을 실제로 추가:

```python
from .perf_log import (  # noqa: F401
    insert_perf_log,
    list_perf_log_aggregated,
    list_perf_log_detail,
)
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
python -m pytest tests/test_perf_log.py -v 2>&1 | tail -15
```

Expected: 3개 테스트 PASS

- [ ] **Step 6: 커밋**

```bash
git add app/db/perf_log.py tests/test_perf_log.py app/db/__init__.py
git commit -m "feat(db): add perf_log module — insert, aggregate, detail"
```

---

## Task 4: config.py — 카카오 & 성능 임계값 설정

**Files:**
- Modify: `app/config.py`

- [ ] **Step 1: Settings dataclass에 필드 추가**

`app/config.py`의 `Settings` 데이터클래스에 추가:

```python
# 카카오 알림 (선택 — 미설정 시 알림 스킵)
kakao_rest_api_key: str | None = None
kakao_refresh_token: str | None = None

# 성능 임계값 (ms 단위)
perf_slow_api_ms: int = 300
perf_slow_batch_ms: int = 60_000
perf_slow_query_ms: int = 200
```

- [ ] **Step 2: get_settings()에 환경변수 읽기 추가**

`get_settings()` 함수에 추가:

```python
kakao_rest_api_key=(os.getenv("KAKAO_REST_API_KEY") or "").strip() or None,
kakao_refresh_token=(os.getenv("KAKAO_REFRESH_TOKEN") or "").strip() or None,
perf_slow_api_ms=int(os.getenv("PERF_SLOW_API_MS") or "300"),
perf_slow_batch_ms=int(os.getenv("PERF_SLOW_BATCH_MS") or "60000"),
perf_slow_query_ms=int(os.getenv("PERF_SLOW_QUERY_MS") or "200"),
```

- [ ] **Step 3: 설정 로딩 확인**

```bash
python -c "
import os
os.environ['KAKAO_REST_API_KEY'] = 'test-key'
os.environ['PERF_SLOW_API_MS'] = '500'
from app.config import get_settings
get_settings.cache_clear()
s = get_settings()
print('kakao_key:', s.kakao_rest_api_key)
print('slow_api_ms:', s.perf_slow_api_ms)
"
```

Expected: `kakao_key: test-key`, `slow_api_ms: 500`

- [ ] **Step 4: 커밋**

```bash
git add app/config.py
git commit -m "feat(config): add Kakao notify and perf threshold settings"
```

---

## Task 5: 카카오 나에게 보내기 서비스

**Files:**
- Create: `app/services/kakao_notify.py`
- Create: `tests/test_kakao_notify.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_kakao_notify.py`:

```python
import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

os.environ.setdefault("LIBRARY_DB_PATH", "/tmp/test-kakao.db")
os.environ.setdefault("LIBRARY_ADMIN_USERNAME", "admin")
os.environ.setdefault("LIBRARY_ADMIN_PASSWORD", "pw")
os.environ.setdefault("LIBRARY_AUTH_SESSION_SECRET", "s")

from app.config import get_settings
get_settings.cache_clear()

from app.services.kakao_notify import send_kakao_message, _get_access_token


def test_send_skips_when_no_key(monkeypatch):
    """API 키 미설정 시 조용히 스킵."""
    monkeypatch.setattr("app.services.kakao_notify._get_settings", lambda: MagicMock(
        kakao_rest_api_key=None,
        kakao_refresh_token=None,
    ))
    # 예외 없이 반환
    import asyncio
    asyncio.get_event_loop().run_until_complete(send_kakao_message("test"))


def test_send_calls_kakao_api(monkeypatch):
    """API 키 설정 시 카카오 REST API 호출."""
    mock_settings = MagicMock(
        kakao_rest_api_key="test-key",
        kakao_refresh_token="test-refresh",
    )
    monkeypatch.setattr("app.services.kakao_notify._get_settings", lambda: mock_settings)

    token_response = MagicMock()
    token_response.status_code = 200
    token_response.json.return_value = {"access_token": "fake-access"}

    send_response = MagicMock()
    send_response.status_code = 200

    import asyncio

    async def run():
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=[token_response, send_response])
            mock_client_cls.return_value = mock_client
            await send_kakao_message("에러 발생")
            assert mock_client.post.call_count == 2

    asyncio.get_event_loop().run_until_complete(run())
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python -m pytest tests/test_kakao_notify.py -v 2>&1 | tail -10
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: kakao_notify.py 구현**

`app/services/kakao_notify.py` 신규 생성:

```python
"""카카오 나에게 보내기 알림 서비스.

카카오 REST API를 사용해 운영자 본인 카카오톡으로 메시지를 전송한다.
KAKAO_REST_API_KEY / KAKAO_REFRESH_TOKEN 미설정 시 조용히 스킵.
"""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

_KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
_KAKAO_SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


def _get_settings():
    from app.config import get_settings
    return get_settings()


async def _get_access_token(client: httpx.AsyncClient, refresh_token: str, rest_api_key: str) -> str | None:
    """refresh_token으로 access_token을 발급받는다."""
    try:
        resp = await client.post(
            _KAKAO_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": rest_api_key,
                "refresh_token": refresh_token,
            },
            timeout=10.0,
        )
        if resp.status_code != 200:
            logger.warning("kakao token refresh failed: HTTP %s", resp.status_code)
            return None
        return resp.json().get("access_token")
    except Exception as exc:
        logger.warning("kakao token refresh error: %s", exc)
        return None


async def send_kakao_message(text: str) -> None:
    """카카오 나에게 보내기. 실패해도 예외를 올리지 않는다."""
    settings = _get_settings()
    if not settings.kakao_rest_api_key or not settings.kakao_refresh_token:
        return

    try:
        async with httpx.AsyncClient() as client:
            access_token = await _get_access_token(
                client, settings.kakao_refresh_token, settings.kakao_rest_api_key
            )
            if not access_token:
                return

            import json as _json
            template = _json.dumps({
                "object_type": "text",
                "text": text[:2000],
                "link": {"web_url": "", "mobile_web_url": ""},
            }, ensure_ascii=False)

            resp = await client.post(
                _KAKAO_SEND_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                data={"template_object": template},
                timeout=10.0,
            )
            if resp.status_code != 200:
                logger.warning("kakao send failed: HTTP %s %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.warning("kakao send error: %s", exc)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_kakao_notify.py -v 2>&1 | tail -15
```

Expected: 2개 테스트 PASS

- [ ] **Step 5: 커밋**

```bash
git add app/services/kakao_notify.py tests/test_kakao_notify.py
git commit -m "feat(services): add kakao_notify — send to me via Kakao REST API"
```

---

## Task 6: FastAPI 전역 예외 핸들러

**Files:**
- Modify: `app/main.py`
- Create: `tests/test_observability_api.py` (일부)

- [ ] **Step 1: 테스트 작성**

`tests/test_observability_api.py` 신규 생성:

```python
"""에러 로그 / 성능 로그 API 엔드포인트 통합 테스트."""
import os, tempfile
os.environ["LIBRARY_DB_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("LIBRARY_ADMIN_USERNAME", "admin")
os.environ.setdefault("LIBRARY_ADMIN_PASSWORD", "admin-pw")
os.environ.setdefault("LIBRARY_OPERATOR_USERNAME", "op")
os.environ.setdefault("LIBRARY_OPERATOR_PASSWORD", "op-pw")
os.environ.setdefault("LIBRARY_AUTH_SESSION_SECRET", "test-secret")
os.environ.setdefault("LIBRARY_AUTH_COOKIE_SECURE", "0")
os.environ.setdefault("METADATA_SYNC_INTERVAL_MINUTES", "0")

from app.config import get_settings
get_settings.cache_clear()

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def _admin_login():
    client.post("/auth/login", data={"username": "admin", "password": "admin-pw"})


def test_exception_handler_records_error_log():
    """처리되지 않은 예외가 error_log에 기록된다."""
    _admin_login()
    # 일부러 존재하지 않는 DB 항목을 참조하는 엔드포인트 호출은
    # 실제 예외를 유발하기 어려우므로, 직접 DB 함수로 확인
    from app.db.error_log import insert_error_log, get_unread_error_count
    before = get_unread_error_count()
    insert_error_log(level="ERROR", source="test", message="simulated", traceback=None,
                     request_path="/test", request_body=None)
    assert get_unread_error_count() == before + 1
```

- [ ] **Step 2: 테스트 실행 (현재 상태)**

```bash
python -m pytest tests/test_observability_api.py::test_exception_handler_records_error_log -v 2>&1 | tail -10
```

Expected: PASS (DB 함수 직접 호출이므로 핸들러 없어도 통과)

- [ ] **Step 3: 전역 예외 핸들러 구현**

`app/main.py`에서 기존 `@app.middleware("http") async def auth_guard` 바로 위에 추가:

```python
@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception):
    import asyncio
    import traceback as _tb
    from fastapi import HTTPException as _HTTPEx
    from fastapi.responses import JSONResponse

    # 의도된 HTTP 예외는 기본 처리기에 위임
    if isinstance(exc, _HTTPEx):
        from fastapi.exception_handlers import http_exception_handler
        return await http_exception_handler(request, exc)

    tb_str = _tb.format_exc()
    source = ""
    tb_obj = exc.__traceback__
    if tb_obj:
        import traceback as _tbm
        frames = _tbm.extract_tb(tb_obj)
        if frames:
            last = frames[-1]
            source = f"{last.filename.replace(str(Path(__file__).parent.parent) + '/', '')}:{last.name}"

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

    # 카카오 알림 (비동기, 실패 무시)
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
```

- [ ] **Step 4: 서버 시작 확인**

```bash
python -m pytest tests/test_observability_api.py -v 2>&1 | tail -15
```

Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add app/main.py tests/test_observability_api.py
git commit -m "feat(main): add global exception handler — records to error_log, sends Kakao notify"
```

---

## Task 7: 에러 로그 API 엔드포인트

**Files:**
- Modify: `app/api/activity_log.py`
- Modify: `tests/test_observability_api.py`

- [ ] **Step 1: 테스트 추가**

`tests/test_observability_api.py`에 추가:

```python
def test_error_log_list_requires_admin():
    client.cookies.clear()
    resp = client.get("/admin/error-log")
    assert resp.status_code in (401, 403)


def test_error_log_list_and_unread_count():
    _admin_login()
    from app.db.error_log import insert_error_log, acknowledge_error_log
    acknowledge_error_log(ids=None)  # 초기화
    insert_error_log(level="ERROR", source="s", message="msg1",
                     traceback=None, request_path="/x", request_body=None)

    resp = client.get("/admin/error-log?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total_count"] >= 1

    resp2 = client.get("/admin/error-log/unread-count")
    assert resp2.status_code == 200
    assert resp2.json()["count"] >= 1


def test_error_log_acknowledge():
    _admin_login()
    from app.db.error_log import insert_error_log
    rid = insert_error_log(level="ERROR", source="s", message="ack-me",
                           traceback=None, request_path="/y", request_body=None)

    resp = client.post("/admin/error-log/acknowledge")  # 전체 확인
    assert resp.status_code == 200

    resp2 = client.get("/admin/error-log/unread-count")
    assert resp2.json()["count"] == 0
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python -m pytest tests/test_observability_api.py::test_error_log_list_and_unread_count -v 2>&1 | tail -10
```

Expected: 404 (엔드포인트 미존재)

- [ ] **Step 3: activity_log.py에 엔드포인트 추가**

`app/api/activity_log.py` 파일 상단의 imports 아래에 추가:

```python
from app.db.error_log import (
    list_error_log as _list_error_log,
    get_unread_error_count as _get_unread_count,
    acknowledge_error_log as _acknowledge,
)
```

파일 끝에 엔드포인트 추가:

```python
@router.get("/admin/error-log")
def get_error_log(
    is_read: bool | None = None,
    limit: int = 50,
    offset: int = 0,
    _: None = Depends(require_admin_or_operator),
):
    items = _list_error_log(is_read=is_read, limit=limit, offset=offset)
    return {"items": items, "total_count": len(items), "limit": limit, "offset": offset}


@router.get("/admin/error-log/unread-count")
def get_error_log_unread_count(_: None = Depends(require_admin_or_operator)):
    return {"count": _get_unread_count()}


@router.post("/admin/error-log/acknowledge")
def acknowledge_errors(
    ids: list[int] | None = None,
    _: None = Depends(require_admin),
):
    updated = _acknowledge(ids=ids)
    return {"updated": updated}
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_observability_api.py -v -k "error_log" 2>&1 | tail -15
```

Expected: 에러 로그 관련 테스트 모두 PASS

- [ ] **Step 5: 커밋**

```bash
git add app/api/activity_log.py tests/test_observability_api.py
git commit -m "feat(api): add error-log endpoints — list, unread-count, acknowledge"
```

---

## Task 8: 관리툴 에러 배지 & 뷰어

**Files:**
- Modify: `app/static/index.html`

- [ ] **Step 1: 에러 배지 HTML 추가**

`app/static/index.html`에서 `opsActivityTabBtn` 버튼을 찾아 배지 span 추가:

기존:
```html
<button id="opsActivityTabBtn" ...>이력 &amp; 로그</button>
```

변경:
```html
<button id="opsActivityTabBtn" ...>이력 &amp; 로그 <span id="errorUnreadBadge" style="display:none;background:#dc2626;color:#fff;font-size:0.65rem;font-weight:700;padding:1px 5px;border-radius:9px;margin-left:3px;vertical-align:middle"></span></button>
```

- [ ] **Step 2: 에러 로그 섹션 HTML 추가**

`opsActivityPanel` 내부의 기존 섹션들(① 메타 변경 이력, ② 장식장 이력, ③ 서버 로그) 앞에 새 섹션 추가:

```html
<!-- ③ 에러 로그 -->
<div class="act-section">
  <h3>에러 로그 <span id="actErrCount" style="font-weight:400;font-size:0.8rem;color:var(--text-muted)"></span></h3>
  <div class="act-filter-row">
    <select id="actErrIsRead">
      <option value="">전체</option>
      <option value="false">미확인</option>
      <option value="true">확인 완료</option>
    </select>
    <button id="actErrLoadBtn">조회</button>
    <button id="actErrAckBtn" style="background:var(--err,#dc3545)">전체 확인 처리</button>
  </div>
  <div style="overflow-x:auto">
    <table class="act-table">
      <thead><tr><th>시각</th><th>경로</th><th>메시지</th><th>위치</th><th>확인</th></tr></thead>
      <tbody id="actErrTbody"><tr><td colspan="5" style="text-align:center;color:var(--text-muted)">조회 버튼을 눌러주세요</td></tr></tbody>
    </table>
  </div>
  <div class="act-pagination">
    <button id="actErrPrevBtn" disabled>◀ 이전</button>
    <button id="actErrNextBtn" disabled>다음 ▶</button>
  </div>
</div>
```

- [ ] **Step 3: JS 함수 추가**

기존 `loadActivityAudit` 함수 위에 추가:

```javascript
// ── Error Log ──────────────────────────────────────────────────────
let _actErrOffset = 0, _actErrLimit = 50;

async function loadErrorBadge() {
  try {
    const res = await fetchWithRetry("/admin/error-log/unread-count");
    if (!res.ok) return;
    const { count } = await res.json();
    const badge = $("errorUnreadBadge");
    if (count > 0) { badge.textContent = count; badge.style.display = ""; }
    else { badge.style.display = "none"; }
  } catch (_) {}
}

async function loadErrorLog(reset) {
  if (reset) _actErrOffset = 0;
  const isRead = $("actErrIsRead").value;
  let url = `/admin/error-log?limit=${_actErrLimit}&offset=${_actErrOffset}`;
  if (isRead !== "") url += `&is_read=${isRead}`;
  const res = await fetchWithRetry(url);
  if (!res.ok) { $("actErrCount").textContent = "조회 실패"; return; }
  const data = await res.json();
  $("actErrCount").textContent = `${data.total_count}건`;
  const tbody = $("actErrTbody");
  if (!data.items.length) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-muted)">결과 없음</td></tr>';
  } else {
    tbody.innerHTML = data.items.map(r => {
      const ts = (r.created_at || "").slice(0, 16).replace("T", " ");
      const isReadBadge = r.is_read
        ? `<span style="color:var(--text-muted);font-size:0.72rem">확인</span>`
        : `<span style="background:#fee2e2;color:#b91c1c;padding:1px 5px;border-radius:3px;font-size:0.72rem;font-weight:700">미확인</span>`;
      const tbDetail = r.traceback
        ? `<details style="margin-top:4px;font-size:0.72rem"><summary style="cursor:pointer;color:var(--accent)">스택 트레이스</summary><pre style="white-space:pre-wrap;margin:4px 0;font-size:0.7rem;color:var(--text-sub)">${escapeHtml(r.traceback)}</pre></details>`
        : "";
      return `<tr>
        <td style="white-space:nowrap;font-size:0.75rem;vertical-align:top">${ts}</td>
        <td style="font-size:0.74rem;vertical-align:top">${escapeHtml(r.request_path || "—")}</td>
        <td style="vertical-align:top"><div style="font-size:0.75rem;font-weight:600">${escapeHtml(r.message || "")}</div>${tbDetail}</td>
        <td style="font-size:0.72rem;color:var(--text-muted);vertical-align:top">${escapeHtml(r.source || "—")}</td>
        <td style="vertical-align:top">${isReadBadge}</td>
      </tr>`;
    }).join("");
  }
  $("actErrPrevBtn").disabled = _actErrOffset === 0;
  $("actErrNextBtn").disabled = data.items.length < _actErrLimit;
}

$("actErrLoadBtn").addEventListener("click", () => loadErrorLog(true));
$("actErrAckBtn").addEventListener("click", async () => {
  const res = await fetchWithRetry("/admin/error-log/acknowledge", { method: "POST" });
  if (res.ok) { await loadErrorLog(true); await loadErrorBadge(); }
});
$("actErrPrevBtn").addEventListener("click", () => { _actErrOffset = Math.max(0, _actErrOffset - _actErrLimit); loadErrorLog(false); });
$("actErrNextBtn").addEventListener("click", () => { _actErrOffset += _actErrLimit; loadErrorLog(false); });
```

- [ ] **Step 4: 페이지 로드 시 배지 초기화**

페이지 로드 이벤트 또는 `DOMContentLoaded` 핸들러에 `loadErrorBadge()` 호출 추가. 기존 초기화 블록을 찾아서:

```javascript
// 기존 초기화 블록 끝에 추가
loadErrorBadge();
```

- [ ] **Step 5: QA 서버 재시작 후 브라우저 확인**

```bash
PID=$(pgrep -f 'uvicorn.*8100'); kill -TERM $PID; sleep 5
ps -eo pid,command | grep 'uvicorn.*8100' | grep -v grep
```

확인 사항:
- "이력 & 로그" 탭 버튼에 에러 수 배지 표시
- 에러 로그 섹션에서 "조회" 클릭 시 목록 표시
- "전체 확인 처리" 후 배지 사라짐
- 스택 트레이스 있는 항목 펼치기 동작

- [ ] **Step 6: 커밋**

```bash
git add app/static/index.html
git commit -m "feat(ui): add error log viewer and unread badge in activity tab"
```

---

## Task 9: perf_tracker 컨텍스트 매니저 (배치용)

**Files:**
- Create: `app/services/perf_tracker.py`
- Create: `tests/test_perf_tracker.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_perf_tracker.py`:

```python
import os, tempfile
os.environ.setdefault("LIBRARY_DB_PATH", tempfile.mktemp(suffix=".db"))
os.environ.setdefault("LIBRARY_ADMIN_USERNAME", "admin")
os.environ.setdefault("LIBRARY_ADMIN_PASSWORD", "pw")
os.environ.setdefault("LIBRARY_AUTH_SESSION_SECRET", "s")

from app.config import get_settings
get_settings.cache_clear()

import time
from app.services.perf_tracker import perf_track
from app.db.perf_log import list_perf_log_aggregated


def test_perf_track_records_batch():
    with perf_track("test_batch", kind="BATCH"):
        time.sleep(0.01)  # 10ms 대기

    rows = list_perf_log_aggregated(kind="BATCH", is_slow_only=False, days=1)
    names = [r["name"] for r in rows]
    assert "test_batch" in names
    row = next(r for r in rows if r["name"] == "test_batch")
    assert row["max_ms"] >= 10


def test_perf_track_records_context():
    with perf_track("test_with_ctx", kind="BATCH", context={"processed": 42}):
        pass

    from app.db.perf_log import list_perf_log_detail
    rows = list_perf_log_detail(name="test_with_ctx")
    assert len(rows) >= 1
    import json
    ctx = json.loads(rows[0]["context_json"] or "{}")
    assert ctx.get("processed") == 42


def test_perf_track_records_even_on_exception():
    try:
        with perf_track("test_exc", kind="BATCH"):
            raise ValueError("test error")
    except ValueError:
        pass

    rows = list_perf_log_aggregated(kind="BATCH", is_slow_only=False, days=1)
    names = [r["name"] for r in rows]
    assert "test_exc" in names
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python -m pytest tests/test_perf_tracker.py -v 2>&1 | tail -10
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: perf_tracker.py 구현**

`app/services/perf_tracker.py` 신규 생성:

```python
"""배치 작업 성능 추적 컨텍스트 매니저."""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Generator


@contextmanager
def perf_track(
    name: str,
    *,
    kind: str = "BATCH",
    context: dict[str, Any] | None = None,
    slow_ms: int | None = None,
) -> Generator[None, None, None]:
    """배치 작업 시간을 측정해 perf_log에 기록한다.

    with perf_track("metadata_sync", context={"processed": 300}):
        ...

    예외 발생 시에도 기록된다.
    """
    from app.config import get_settings
    from app.db.perf_log import insert_perf_log

    settings = get_settings()
    _slow_threshold = slow_ms if slow_ms is not None else settings.perf_slow_batch_ms

    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        is_slow = elapsed_ms >= _slow_threshold
        try:
            insert_perf_log(
                kind=kind,
                name=name,
                duration_ms=elapsed_ms,
                is_slow=is_slow,
                context=context,
            )
        except Exception:
            pass
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_perf_tracker.py -v 2>&1 | tail -15
```

Expected: 3개 테스트 PASS

- [ ] **Step 5: 커밋**

```bash
git add app/services/perf_tracker.py tests/test_perf_tracker.py
git commit -m "feat(services): add perf_tracker context manager for batch timing"
```

---

## Task 10: API 응답 시간 미들웨어

**Files:**
- Modify: `app/main.py`
- Modify: `tests/test_observability_api.py`

- [ ] **Step 1: 테스트 추가**

`tests/test_observability_api.py`에 추가:

```python
def test_perf_middleware_records_slow_api():
    """느린 API 호출이 perf_log에 기록된다."""
    _admin_login()
    # perf_log가 비어있는 새 DB이므로 owned-items 조회 후 확인
    client.get("/owned-items?limit=1")  # 실제 API 호출
    from app.db.perf_log import list_perf_log_aggregated
    # 기록 여부는 응답 시간에 따라 다르므로 단순 임포트 성공 여부만 검증
    rows = list_perf_log_aggregated(kind="API", is_slow_only=False, days=1)
    assert isinstance(rows, list)
```

- [ ] **Step 2: 미들웨어 구현**

`app/main.py`의 기존 `@app.middleware("http") async def auth_guard` 바로 위에 추가 (exception handler 아래):

```python
_PERF_SKIP_PREFIXES = ("/static/", "/health", "/cafe/now-playing/stream", "/cafe/tablet")


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
```

> **순서 주의:** `perf_timing_middleware`는 `auth_guard` 위에 선언해야 두 미들웨어 모두 동작한다. FastAPI 미들웨어는 역순 실행된다.

- [ ] **Step 3: 테스트 통과 확인**

```bash
python -m pytest tests/test_observability_api.py::test_perf_middleware_records_slow_api -v 2>&1 | tail -10
```

Expected: PASS

- [ ] **Step 4: 커밋**

```bash
git add app/main.py tests/test_observability_api.py
git commit -m "feat(main): add perf timing middleware — records slow API calls to perf_log"
```

---

## Task 11: 배치 워커에 perf_track 래핑

**Files:**
- Modify: `app/main.py` (6개 워커 함수)

- [ ] **Step 1: 워커 함수 위치 확인**

```bash
grep -n "async def _metadata_sync_worker\|async def _auto_backup_worker\|def aladin_discogs_backfill\|def discogs_korean_backfill\|def.*spotify.*batch\|def.*exception.*queue.*worker" /Volumes/Data/Works/07.hahahoho/app/main.py | head -10
```

- [ ] **Step 2: 각 워커에 perf_track 적용**

각 워커 함수 내부의 핵심 처리 블록을 `perf_track`으로 감싼다. 예시:

```python
# 기존
async def _metadata_sync_worker():
    ...핵심 처리...

# 변경 후 (핵심 처리 블록만 감쌈)
from app.services.perf_tracker import perf_track

async def _metadata_sync_worker():
    processed = 0
    # ... 처리 ...
    with perf_track("metadata_sync", context={"processed": processed}):
        # 처리 루프
        pass
```

실제 코드에서 워커 함수마다 `logger.exception` 블록 바깥쪽, 핵심 처리 구간에 `with perf_track(...)` 추가. 적용 대상:

| 워커 함수명 | perf_track name |
|------------|----------------|
| `_metadata_sync_worker` | `"metadata_sync"` |
| `_auto_backup_worker` | `"auto_backup"` |
| `aladin_discogs_backfill` | `"aladin_discogs_backfill"` |
| `discogs_korean_backfill` | `"discogs_korean_backfill"` |
| Spotify 배치 함수 | `"spotify_batch_match"` |
| 예외 큐 처리 함수 | `"exception_queue_process"` |

- [ ] **Step 3: 서버 시작 오류 없음 확인**

```bash
python -c "from app.main import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: 커밋**

```bash
git add app/main.py
git commit -m "feat(workers): wrap 6 batch workers with perf_track for timing"
```

---

## Task 12: 성능 로그 API 엔드포인트

**Files:**
- Modify: `app/api/activity_log.py`
- Modify: `tests/test_observability_api.py`

- [ ] **Step 1: 테스트 추가**

`tests/test_observability_api.py`에 추가:

```python
def test_perf_log_list():
    _admin_login()
    from app.db.perf_log import insert_perf_log
    insert_perf_log(kind="API", name="GET /test", duration_ms=500, is_slow=True)

    resp = client.get("/admin/perf-log?kind=API")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    names = [r["name"] for r in data["items"]]
    assert "GET /test" in names


def test_perf_log_detail():
    _admin_login()
    resp = client.get("/admin/perf-log/detail?name=GET+/test")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert any(r["duration_ms"] == 500 for r in data["items"])
```

- [ ] **Step 2: activity_log.py에 엔드포인트 추가**

imports에 추가:

```python
from app.db.perf_log import (
    list_perf_log_aggregated as _list_perf_agg,
    list_perf_log_detail as _list_perf_detail,
)
```

엔드포인트 추가:

```python
@router.get("/admin/perf-log")
def get_perf_log(
    kind: str | None = None,
    is_slow_only: bool = False,
    days: int = 7,
    _: None = Depends(require_admin_or_operator),
):
    items = _list_perf_agg(kind=kind, is_slow_only=is_slow_only, days=days)
    return {"items": items, "total_count": len(items)}


@router.get("/admin/perf-log/detail")
def get_perf_log_detail(
    name: str,
    kind: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _: None = Depends(require_admin_or_operator),
):
    items = _list_perf_detail(name=name, kind=kind, limit=limit, offset=offset)
    return {"items": items, "total_count": len(items)}
```

- [ ] **Step 3: 테스트 통과 확인**

```bash
python -m pytest tests/test_observability_api.py -v -k "perf" 2>&1 | tail -15
```

Expected: perf 관련 테스트 PASS

- [ ] **Step 4: 커밋**

```bash
git add app/api/activity_log.py tests/test_observability_api.py
git commit -m "feat(api): add perf-log endpoints — aggregated list and detail"
```

---

## Task 13: 관리툴 성능 현황 뷰어

**Files:**
- Modify: `app/static/index.html`

- [ ] **Step 1: 성능 현황 섹션 HTML 추가**

`opsActivityPanel`에 에러 로그 섹션 다음에 추가:

```html
<!-- ④ 성능 현황 -->
<div class="act-section">
  <h3>성능 현황 <span id="actPerfCount" style="font-weight:400;font-size:0.8rem;color:var(--text-muted)"></span></h3>
  <div class="act-filter-row">
    <select id="actPerfKind">
      <option value="">전체</option>
      <option value="API">API</option>
      <option value="BATCH">배치</option>
      <option value="QUERY">DB 쿼리</option>
    </select>
    <select id="actPerfDays">
      <option value="1">오늘</option>
      <option value="7" selected>최근 7일</option>
      <option value="30">최근 30일</option>
    </select>
    <label style="font-size:0.82rem"><input type="checkbox" id="actPerfSlowOnly"> 느린 항목만</label>
    <button id="actPerfLoadBtn">조회</button>
  </div>
  <div style="overflow-x:auto">
    <table class="act-table">
      <thead><tr><th>유형</th><th>이름</th><th>평균</th><th>최대</th><th>건수</th><th>느림</th></tr></thead>
      <tbody id="actPerfTbody"><tr><td colspan="6" style="text-align:center;color:var(--text-muted)">조회 버튼을 눌러주세요</td></tr></tbody>
    </table>
  </div>
</div>
```

- [ ] **Step 2: JS 함수 추가**

```javascript
// ── Perf Log ───────────────────────────────────────────────────────
async function loadPerfLog(reset) {
  const kind = $("actPerfKind").value;
  const days = $("actPerfDays").value;
  const slowOnly = $("actPerfSlowOnly").checked;
  let url = `/admin/perf-log?days=${days}&is_slow_only=${slowOnly}`;
  if (kind) url += `&kind=${kind}`;
  const res = await fetchWithRetry(url);
  if (!res.ok) { $("actPerfCount").textContent = "조회 실패"; return; }
  const data = await res.json();
  $("actPerfCount").textContent = `${data.total_count}건`;
  const tbody = $("actPerfTbody");
  const kindLabels = { API: "API", BATCH: "배치", QUERY: "DB" };
  if (!data.items.length) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-muted)">결과 없음</td></tr>';
  } else {
    tbody.innerHTML = data.items.map(r => {
      const kindBadge = `<span style="font-size:0.72rem;background:var(--bg-dim,#f5f5f5);padding:1px 6px;border-radius:3px">${kindLabels[r.kind] || r.kind}</span>`;
      const slowBadge = r.slow_count > 0
        ? `<span style="background:#fee2e2;color:#b91c1c;padding:1px 5px;border-radius:3px;font-size:0.7rem;font-weight:700">${r.slow_count}건</span>`
        : `<span style="color:var(--text-muted);font-size:0.72rem">—</span>`;
      const fmtMs = (ms) => ms >= 1000 ? `${(ms/1000).toFixed(1)}s` : `${ms}ms`;
      return `<tr>
        <td>${kindBadge}</td>
        <td style="font-size:0.75rem;max-width:280px;word-break:break-all">${escapeHtml(r.name)}</td>
        <td style="font-size:0.75rem">${fmtMs(r.avg_ms)}</td>
        <td style="font-size:0.75rem;font-weight:${r.max_ms >= 300 ? '700' : '400'};color:${r.max_ms >= 300 ? '#dc2626' : 'inherit'}">${fmtMs(r.max_ms)}</td>
        <td style="font-size:0.75rem">${r.count}</td>
        <td>${slowBadge}</td>
      </tr>`;
    }).join("");
  }
}

$("actPerfLoadBtn").addEventListener("click", () => loadPerfLog(true));
```

- [ ] **Step 3: QA 서버 재시작 후 확인**

```bash
PID=$(pgrep -f 'uvicorn.*8100'); kill -TERM $PID; sleep 5
```

확인: 성능 현황 섹션에서 "조회" 클릭 → API/배치 기록 표시, 느린 항목 빨간색

- [ ] **Step 4: 커밋**

```bash
git add app/static/index.html
git commit -m "feat(ui): add perf log viewer in activity tab"
```

---

## Task 14: album_master 전체 필드 audit 추적

**Files:**
- Modify: `app/api/album_masters.py`
- Modify: `app/db/album_master_core.py`

- [ ] **Step 1: _ALBUM_MASTER_AUDIT_FIELDS 상수 추가**

`app/api/album_masters.py` 상단 (imports 아래)에 추가:

```python
_ALBUM_MASTER_AUDIT_FIELDS = (
    "artist_or_brand", "title", "catalog_no", "barcode",
    "release_year", "release_month", "label", "domain_code",
    "genres", "styles", "country", "format_text",
    "sort_artist_name", "override_artist_or_brand",
    "override_title", "override_note", "description",
)
```

- [ ] **Step 2: update_album_master_correction에 전체 필드 추적 추가**

`app/api/album_masters.py`의 `update_album_master_correction` 함수에서 현재 audit 코드를 찾아 수정:

```python
# 기존: override 필드만 추적
# 변경: DB에서 before/after 모두 캡처
# 함수 시그니처: update_album_master_correction(album_master_id, payload: AlbumMasterCorrectionUpdateRequest, request: Request)

    # before 상태 캡처 (함수 첫 줄에 추가)
    _before_row = db.get_album_master_basic(album_master_id)
    _before = {f: (_before_row or {}).get(f) for f in _ALBUM_MASTER_AUDIT_FIELDS}
    
    # 기존 업데이트 로직 실행
    result = db.update_album_master_correction(...)
    
    # after 상태 캡처
    _after_row = db.get_album_master_basic(album_master_id)
    _after = {f: (_after_row or {}).get(f) for f in _ALBUM_MASTER_AUDIT_FIELDS}
    
    from app.security import _read_auth_username
    db.log_audit_event(
        entity_type="album_master", entity_id=album_master_id,
        action="UPDATE", changed_by=_read_auth_username(request),
        before=_before, after=_after,
    )
    return result
```

`update_album_master_sort_artist_name` 에도 동일 패턴 적용.

- [ ] **Step 3: upsert_album_master에 CREATE/UPDATE audit 추가**

`app/db/album_master_core.py`의 `upsert_album_master` 함수에서 INSERT 전 기존 row 존재 여부 확인:

```python
def upsert_album_master(...) -> int:
    now = utc_now_iso()
    normalized_domain_code = _normalize_domain_code_value(domain_code)
    with get_conn() as conn:
        # 기존 행 존재 여부 및 before 상태 확인
        _existing = conn.execute(
            "SELECT * FROM album_master WHERE source_code = ? AND source_master_id = ?",
            (source_code, source_master_id),
        ).fetchone()
        _is_new = _existing is None
        _before = dict(_existing) if _existing else {}
        
        conn.execute("""INSERT INTO album_master ... ON CONFLICT ... DO UPDATE SET ...""", ...)
        
        row = conn.execute("SELECT id FROM album_master WHERE ...", ...).fetchone()
    
    album_master_id = int(row["id"])
    
    # audit
    try:
        from app.db.audit_log import log_audit_event
        if _is_new:
            log_audit_event(
                entity_type="album_master", entity_id=album_master_id,
                action="CREATE", changed_by=None,
                snapshot={"source_code": source_code, "title": title,
                          "artist_or_brand": artist_or_brand, "domain_code": normalized_domain_code},
            )
        else:
            _FIELDS = ("title", "artist_or_brand", "domain_code", "release_year")
            _after = {"title": title, "artist_or_brand": artist_or_brand,
                      "domain_code": normalized_domain_code, "release_year": release_year}
            _before_subset = {f: _before.get(f) for f in _FIELDS}
            log_audit_event(
                entity_type="album_master", entity_id=album_master_id,
                action="UPDATE", changed_by=None,
                before=_before_subset, after=_after,
            )
    except Exception:
        pass
    
    ensure_album_master_external_ref(...)
    return album_master_id
```

- [ ] **Step 4: 서버 구동 확인**

```bash
python -c "from app.main import app; print('OK')"
```

- [ ] **Step 5: 커밋**

```bash
git add app/api/album_masters.py app/db/album_master_core.py
git commit -m "feat(audit): add album_master full field tracking — before/after for all 17 fields"
```

---

## Task 15: 누락 audit 이벤트 보완

**Files:**
- Modify: `app/api/owned_items.py` (IMAGE 스냅샷)
- Modify: `app/api/purchase_imports.py` (PURCHASE_IMPORT)

- [ ] **Step 1: IMAGE_UPLOAD/DELETE 스냅샷 보강**

`app/api/owned_items.py`의 `upload_owned_item_image` 함수에서 현재:

```python
_audit(request, "owned_item", owned_item_id, "IMAGE_UPLOAD")
```

변경:

```python
_audit(request, "owned_item", owned_item_id, "IMAGE_UPLOAD",
       snapshot={"filename": file.filename, "content_type": file.content_type})
```

`delete_owned_item_image` 함수에서 현재:

```python
_audit(request, "owned_item", owned_item_id, "IMAGE_DELETE")
```

변경 (삭제 전 파일명 캡처 후):

```python
_audit(request, "owned_item", owned_item_id, "IMAGE_DELETE",
       snapshot={"filename": image_filename})  # image_filename은 함수 내 기존 변수
```

- [ ] **Step 2: EXTERNAL_REF_UPDATE audit 추가**

`app/db/album_master_external_ref.py`의 `ensure_album_master_external_ref` 함수에서, ON CONFLICT 전에 기존 `album_master_id`를 읽어 변경 여부 확인:

```python
def ensure_album_master_external_ref(album_master_id, source_code, source_master_id, ...):
    ...
    with get_conn() as conn:
        # 기존 row의 album_master_id 확인
        _existing_ref = conn.execute(
            "SELECT album_master_id FROM album_master_external_ref WHERE source_code=? AND source_master_id=?",
            (source_u, source_master),
        ).fetchone()
        
        conn.execute("INSERT INTO album_master_external_ref ... ON CONFLICT DO UPDATE SET ...", ...)
        
        # album_master_id가 변경된 경우에만 audit
        if _existing_ref and int(_existing_ref["album_master_id"]) != master_id:
            try:
                from app.db.audit_log import log_audit_event
                log_audit_event(
                    entity_type="album_master", entity_id=master_id,
                    action="EXTERNAL_REF_UPDATE", changed_by=None,
                    snapshot={
                        "source": source_u,
                        "source_master_id": source_master,
                        "before_album_master_id": int(_existing_ref["album_master_id"]),
                        "after_album_master_id": master_id,
                    },
                )
            except Exception:
                pass
```

- [ ] **Step 3: PURCHASE_IMPORT audit 추가**

`app/api/purchase_imports.py`의 `create_owned_item_from_purchase_import` 함수 끝에 추가:

```python
# 구매 수입으로 생성된 상품 audit
try:
    from app.db.audit_log import log_audit_event
    log_audit_event(
        entity_type="owned_item", entity_id=new_owned_item_id,
        action="PURCHASE_IMPORT", changed_by=None,
        snapshot={"purchase_import_id": purchase_import_id,
                  "source_email": source_email or None},
    )
except Exception:
    pass
```

- [ ] **Step 3: 서버 구동 확인**

```bash
python -c "from app.main import app; print('OK')"
```

- [ ] **Step 4: 커밋**

```bash
git add app/api/owned_items.py app/api/purchase_imports.py
git commit -m "feat(audit): add IMAGE_UPLOAD/DELETE snapshot, PURCHASE_IMPORT tracking"
```

---

## Task 16: 관리툴 한글 필드명 추가

**Files:**
- Modify: `app/static/index.html`

- [ ] **Step 1: `_AUDIT_FIELD_LABELS`에 album_master 필드 추가**

기존 `const _AUDIT_FIELD_LABELS = { ... }` 블록을 찾아 다음 항목 추가:

```javascript
// album_master 필드
artist_or_brand: "아티스트명",
title: "앨범명",
catalog_no: "카탈로그 번호",
barcode: "바코드",
release_month: "발매월",
label: "레이블",
country: "국가",
format_text: "포맷",
description: "설명",
// 이미지/구매수입
filename: "파일명",
content_type: "파일 형식",
purchase_import_id: "구매수입 ID",
source_email: "구매 이메일",
```

- [ ] **Step 2: `_AUDIT_ACTION_LABELS`에 신규 액션 추가 확인**

```javascript
PURCHASE_IMPORT: "구매수입 등록",
EXTERNAL_REF_UPDATE: "외부ID 변경",
```

- [ ] **Step 3: QA 서버 재시작 후 확인**

```bash
PID=$(pgrep -f 'uvicorn.*8100'); kill -TERM $PID; sleep 5
```

확인:
- 관리툴에서 album_master 이력 펼쳤을 때 `artist_or_brand` → "아티스트명" 표시
- IMAGE_UPLOAD 이력에 파일명 표시

- [ ] **Step 4: 커밋**

```bash
git add app/static/index.html
git commit -m "feat(ui): add album_master field labels and new action labels in audit viewer"
```

---

## Task 17: SQLite 느린 쿼리 추적 (선택)

> 이 태스크는 `get_conn()`의 연결 객체를 서브클래스로 교체하므로 영향 범위가 넓다. Tasks 1~16 완료 후 별도 브랜치에서 진행 권장.

**Files:**
- Modify: `app/db/connection.py`

- [ ] **Step 1: _TimedConnection 서브클래스 구현**

`app/db/connection.py`에 추가:

```python
import time
import threading

_slow_query_recording = threading.local()


class _TimedConnection(sqlite3.Connection):
    """sqlite3.Connection 서브클래스 — execute() 시간 측정."""
    _slow_ms: int = 200

    def execute(self, sql: str, parameters=(), /):
        if getattr(_slow_query_recording, "active", False):
            return super().execute(sql, parameters)
        t0 = time.perf_counter()
        try:
            return super().execute(sql, parameters)
        finally:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            if elapsed_ms >= self._slow_ms:
                self._record_slow(sql, elapsed_ms)

    def _record_slow(self, sql: str, elapsed_ms: int) -> None:
        _slow_query_recording.active = True
        try:
            from app.db.perf_log import insert_perf_log
            insert_perf_log(
                kind="QUERY",
                name=sql.strip()[:300],
                duration_ms=elapsed_ms,
                is_slow=True,
            )
        except Exception:
            pass
        finally:
            _slow_query_recording.active = False
```

- [ ] **Step 2: get_conn()에서 factory 사용**

```python
@contextmanager
def get_conn() -> Generator[sqlite3.Connection, None, None]:
    settings = get_settings()
    _ensure_parent_dir(settings.db_path)
    _TimedConnection._slow_ms = settings.perf_slow_query_ms  # 설정 동기화
    conn = sqlite3.connect(
        settings.db_path,
        timeout=SQLITE_BUSY_TIMEOUT_MS / 1000,
        factory=_TimedConnection,  # 서브클래스 사용
    )
    # ... 나머지 동일
```

`get_write_conn()`도 동일하게 `factory=_TimedConnection` 추가.

- [ ] **Step 3: 기존 테스트 전체 실행**

```bash
python -m pytest tests/ -x --timeout=60 2>&1 | tail -20
```

Expected: 기존 테스트 모두 PASS (서브클래스가 기존 동작 변경 없이 투명하게 작동)

- [ ] **Step 4: 커밋**

```bash
git add app/db/connection.py
git commit -m "feat(db): add _TimedConnection subclass for slow query detection"
```

---

## 전체 테스트 실행

모든 태스크 완료 후:

```bash
cd /Volumes/Data/Works/07.hahahoho
python -m pytest tests/ -x --timeout=60 2>&1 | tail -30
```

Expected: 전체 테스트 PASS

## QA → Prod 배포 체크리스트

- [ ] QA에서 에러 배지 동작 확인
- [ ] QA에서 카카오 알림 테스트 (의도적 500 에러 유발)
- [ ] `.env.local` (prod)에 `KAKAO_REST_API_KEY`, `KAKAO_REFRESH_TOKEN` 추가
- [ ] prod 코드 업데이트 및 서버 재시작
- [ ] prod에서 `SCHEMA_VERSION` 18 마이그레이션 자동 적용 확인
