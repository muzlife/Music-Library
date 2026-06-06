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
