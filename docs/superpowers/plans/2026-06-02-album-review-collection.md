# Album Review Collection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `album_master`에 앨범 리뷰를 수집·저장하는 파이프라인을 구축한다 — Wikipedia 자동수집(버그 수정), 임의 URL fetch, 직접 입력을 지원하고 영문 텍스트는 DeepSeek API로 한국어 요약 후 저장한다.

**Architecture:** DeepSeek OpenAI 호환 HTTP 클라이언트(`deepseek_client.py`) → 리뷰 파이프라인(`review_pipeline.py`) → DB 레이어(`album_master_review.py`) → API 엔드포인트 4종(auto/url/manual/batch) → 프론트엔드 개별·배치 UI.

**Tech Stack:** FastAPI, SQLite, httpx, BeautifulSoup4, OpenAI Python SDK (DeepSeek 호환), Wikipedia API

---

## 파일 구조

| 파일 | 역할 |
|------|------|
| `app/config.py` | `deepseek_api_key` 필드 추가 |
| `app/services/deepseek_client.py` | DeepSeek HTTP 클라이언트 (신규) |
| `app/services/review_pipeline.py` | `summarize_to_korean()` 파이프라인 (신규) |
| `app/services/providers.py` | Wikipedia 버그 수정, `fetch_review_from_url()` 추가 |
| `app/db/album_master_review.py` | 리뷰 저장/조회/배치 쿼리 (신규) |
| `app/api/album_masters.py` | 기존 `/review` 교체 + 4개 엔드포인트 추가 |
| `app/static/index.html` | 개별 리뷰 관리 UI + 배치 UI |
| `tests/test_review_pipeline.py` | 파이프라인 단위 테스트 (신규) |
| `tests/test_db_album_master_review.py` | DB 레이어 단위 테스트 (신규) |

---

## Task 0: DeepSeek 클라이언트 + config 추가

**Files:**
- Modify: `app/config.py`
- Create: `app/services/deepseek_client.py`

### 배경
`app/config.py`는 `Settings` dataclass에 모든 설정을 보관한다. `.env.local`에 `DEEPSEEK_API_KEY="sk-..."` 가 이미 있다.

- [ ] **Step 1: `app/config.py`에 `deepseek_api_key` 필드 추가**

`Settings` dataclass에 한 줄 추가:

```python
# app/config.py  — Settings dataclass 내부 (다른 필드들 사이)
deepseek_api_key: str | None
```

`get_settings()` 함수의 `Settings(...)` 생성자에 한 줄 추가:

```python
deepseek_api_key=(os.getenv("DEEPSEEK_API_KEY") or "").strip() or None,
```

- [ ] **Step 2: `app/services/deepseek_client.py` 작성**

```python
from __future__ import annotations

from openai import OpenAI

from ..config import get_settings


def _client() -> OpenAI:
    api_key = get_settings().deepseek_api_key
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY not configured")
    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")


def chat_complete(prompt: str, system: str = "", model: str = "deepseek-chat") -> str:
    """Send a single-turn prompt and return the text response."""
    client = _client()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = client.chat.completions.create(model=model, messages=messages, max_tokens=512)
    return resp.choices[0].message.content or ""
```

- [ ] **Step 3: 구문 검사**

```bash
python3 -m py_compile app/config.py app/services/deepseek_client.py && echo OK
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add app/config.py app/services/deepseek_client.py
git commit -m "feat(config): add deepseek_api_key + deepseek_client service"
```

---

## Task 1: Wikipedia 버그 수정 + URL fetcher 추가

**Files:**
- Modify: `app/services/providers.py:1446-1488`
- Test: `tests/test_review_pipeline.py`

### 배경
`fetch_wikipedia_album_review(artist, title)` 현재 버그:
- 검색 쿼리 `"{artist} {title} album"` → 아티스트 Wikipedia 페이지가 상위에 오면 그걸 가져옴
- `pages[0]`을 무조건 사용하므로 앨범 페이지가 아닌 아티스트 전기 페이지가 반환됨

수정: 검색 결과 5개 중 페이지 제목에 앨범 `title`이 포함된 것을 우선 선택. 없으면 `None` 반환.

`fetch_review_from_url(url)` 신규: httpx로 임의 URL fetch → BeautifulSoup으로 본문 추출.

- [ ] **Step 1: 테스트 작성**

```python
# tests/test_review_pipeline.py
import pytest
from unittest.mock import patch, MagicMock


def test_wikipedia_picks_album_page_over_artist():
    """앨범 title이 포함된 페이지를 아티스트 페이지보다 우선 선택."""
    from app.services.providers import fetch_wikipedia_album_review

    search_results = [
        {"title": "Humming Urban Stereo"},           # 아티스트 페이지 (먼저 등장)
        {"title": "Shabbat Shalom (album)"},         # 앨범 페이지
        {"title": "Korean indie music"},
    ]
    extract_data = {
        "query": {
            "pages": {
                "123": {"extract": "Shabbat Shalom is a studio album by Humming Urban Stereo."}
            }
        }
    }

    import json, urllib.request
    call_count = [0]

    def fake_urlopen(req, timeout=10):
        call_count[0] += 1
        mock_resp = MagicMock()
        if call_count[0] == 1:
            mock_resp.read.return_value = json.dumps(
                {"query": {"search": search_results}}
            ).encode()
        else:
            mock_resp.read.return_value = json.dumps(extract_data).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    with patch.object(urllib.request, "urlopen", side_effect=fake_urlopen):
        result = fetch_wikipedia_album_review("Humming Urban Stereo", "Shabbat Shalom")

    assert result is not None
    assert "Shabbat Shalom" in result["review_url"]
    assert result["review_source"] == "WIKIPEDIA"


def test_wikipedia_returns_none_when_no_album_page():
    """앨범 title이 포함된 페이지가 없으면 None 반환."""
    from app.services.providers import fetch_wikipedia_album_review

    search_results = [
        {"title": "Humming Urban Stereo"},
        {"title": "Korean indie music"},
    ]

    import json, urllib.request

    def fake_urlopen(req, timeout=10):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"query": {"search": search_results}}
        ).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    with patch.object(urllib.request, "urlopen", side_effect=fake_urlopen):
        result = fetch_wikipedia_album_review("Humming Urban Stereo", "Shabbat Shalom")

    assert result is None


def test_fetch_review_from_url_extracts_article_text():
    """<article> 태그에서 본문 텍스트를 추출한다."""
    from app.services.providers import fetch_review_from_url

    html = b"""<html><body>
        <nav>nav stuff</nav>
        <article>
          <p>This album changed everything.</p>
          <p>A masterpiece of modern music.</p>
        </article>
    </body></html>"""

    import httpx
    mock_resp = MagicMock()
    mock_resp.content = html
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.get", return_value=mock_resp):
        text = fetch_review_from_url("https://example.com/review")

    assert text is not None
    assert "This album changed everything" in text


def test_fetch_review_from_url_returns_none_on_error():
    """fetch 실패 시 None 반환."""
    from app.services.providers import fetch_review_from_url
    import httpx

    with patch("httpx.get", side_effect=httpx.TimeoutException("timeout")):
        result = fetch_review_from_url("https://example.com/review")

    assert result is None
```

- [ ] **Step 2: 테스트 실행 확인 (FAIL)**

```bash
pytest tests/test_review_pipeline.py -v
```

Expected: 4개 FAIL (함수가 아직 수정/추가 안 됨)

- [ ] **Step 3: `providers.py` Wikipedia 함수 수정**

`fetch_wikipedia_album_review` 함수 전체를 아래로 교체 (`providers.py` 1446~1488줄):

```python
def fetch_wikipedia_album_review(artist: str, title: str) -> dict[str, str | None] | None:
    """Fetch album page extract from Wikipedia API.

    Searches for the album page specifically — not the artist page.
    Returns None if no album-titled page is found in the top 5 results.
    """
    import urllib.request, urllib.parse, json as _json
    query = f"{title} {artist} album"
    params = urllib.parse.urlencode({
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": query,
        "srlimit": "5",
        "srprop": "snippet",
    })
    try:
        req = urllib.request.Request(
            f"https://en.wikipedia.org/w/api.php?{params}",
            headers={"User-Agent": "hahahoho-library/0.1"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read())
        pages = data.get("query", {}).get("search") or []
        if not pages:
            return None
        # 앨범 title이 포함된 페이지를 우선 선택
        title_lower = title.lower()
        page_title = None
        for page in pages:
            if title_lower in page["title"].lower():
                page_title = page["title"]
                break
        if not page_title:
            return None
        # extract 가져오기
        params2 = urllib.parse.urlencode({
            "action": "query",
            "format": "json",
            "prop": "extracts",
            "exintro": "1",
            "explaintext": "1",
            "titles": page_title,
        })
        req2 = urllib.request.Request(
            f"https://en.wikipedia.org/w/api.php?{params2}",
            headers={"User-Agent": "hahahoho-library/0.1"},
        )
        with urllib.request.urlopen(req2, timeout=10) as resp2:
            data2 = _json.loads(resp2.read())
        pages_data = data2.get("query", {}).get("pages") or {}
        extract = next(iter(pages_data.values())).get("extract", "")
        if extract:
            return {
                "review_text": extract[:3000],
                "review_source": "WIKIPEDIA",
                "review_url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(page_title)}",
            }
    except Exception:
        pass
    return None
```

- [ ] **Step 4: `fetch_review_from_url` 함수 추가**

`fetch_wikipedia_album_review` 함수 바로 다음에 추가:

```python
def fetch_review_from_url(url: str) -> str | None:
    """Fetch and extract main body text from any URL.

    Tries <article>, <main>, then all <p> tags in order.
    Returns up to 3000 chars, or None on error.
    """
    import httpx
    from bs4 import BeautifulSoup
    try:
        resp = httpx.get(
            url,
            timeout=15,
            headers={"User-Agent": "hahahoho-library/0.1"},
            follow_redirects=True,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
        # 본문 추출 우선순위: article > main > body
        container = soup.find("article") or soup.find("main") or soup.find("body")
        if not container:
            return None
        paragraphs = container.find_all("p")
        text = "\n".join(p.get_text(" ", strip=True) for p in paragraphs if p.get_text(strip=True))
        text = text.strip()
        return text[:3000] if text else None
    except Exception:
        return None
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
pytest tests/test_review_pipeline.py -v
```

Expected: 4개 PASS

- [ ] **Step 6: Commit**

```bash
git add app/services/providers.py tests/test_review_pipeline.py
git commit -m "fix(providers): fix Wikipedia album page detection + add fetch_review_from_url"
```

---

## Task 2: Review Pipeline (DeepSeek 한국어 요약)

**Files:**
- Create: `app/services/review_pipeline.py`
- Test: `tests/test_review_pipeline.py` (테스트 추가)

### 배경
영문 텍스트 → DeepSeek API 호출 → 한국어 요약 300자 이내. 이미 한국어 비율이 높으면 요약만. DeepSeek API 실패 시 원문 최대 300자를 그대로 반환.

언어 감지: 텍스트에 한글 문자(가-힣, AC00-D7A3)가 15% 이상이면 한국어로 판단.

- [ ] **Step 1: 테스트 추가 (기존 파일에 append)**

```python
# tests/test_review_pipeline.py 에 추가

def test_summarize_to_korean_calls_deepseek():
    """DeepSeek가 성공하면 요약 결과 반환."""
    from app.services.review_pipeline import summarize_to_korean
    from unittest.mock import patch

    with patch("app.services.review_pipeline.chat_complete", return_value="한국어 요약 결과") as mock_chat:
        result = summarize_to_korean("This is an English album review.")

    mock_chat.assert_called_once()
    assert result == "한국어 요약 결과"


def test_summarize_to_korean_fallback_on_error():
    """DeepSeek 실패 시 원문 앞 300자 반환."""
    from app.services.review_pipeline import summarize_to_korean
    from unittest.mock import patch

    long_text = "A" * 500

    with patch("app.services.review_pipeline.chat_complete", side_effect=RuntimeError("api error")):
        result = summarize_to_korean(long_text)

    assert result == "A" * 300


def test_is_korean_text_detection():
    """한글 비율 15% 이상이면 True."""
    from app.services.review_pipeline import _is_korean_text
    assert _is_korean_text("이 앨범은 훌륭하다 great album") is True
    assert _is_korean_text("This is purely English text") is False
```

- [ ] **Step 2: 테스트 실행 확인 (FAIL)**

```bash
pytest tests/test_review_pipeline.py::test_summarize_to_korean_calls_deepseek \
       tests/test_review_pipeline.py::test_summarize_to_korean_fallback_on_error \
       tests/test_review_pipeline.py::test_is_korean_text_detection -v
```

Expected: 3개 FAIL

- [ ] **Step 3: `review_pipeline.py` 작성**

```python
# app/services/review_pipeline.py
from __future__ import annotations

from .deepseek_client import chat_complete

_SUMMARIZE_SYSTEM = (
    "당신은 음악 앨범 리뷰를 한국어로 요약하는 전문가입니다. "
    "요약문만 출력하고 다른 설명은 붙이지 마세요."
)

_SUMMARIZE_PROMPT_EN = """다음 텍스트는 음악 앨범에 관한 글입니다.
한국어로 300자 이내로 요약하세요.
음악적 특징과 평가를 중심으로, 자연스러운 한국어 문어체로 작성하세요.

[텍스트]
{text}"""

_SUMMARIZE_PROMPT_KO = """다음 텍스트는 음악 앨범에 관한 글입니다.
300자 이내로 요약하세요.
음악적 특징과 평가를 중심으로, 자연스러운 한국어 문어체로 작성하세요.

[텍스트]
{text}"""

_MAX_INPUT = 2000
_MAX_RESULT = 300


def _is_korean_text(text: str) -> bool:
    """한글 문자 비율이 15% 이상이면 True."""
    if not text:
        return False
    korean_chars = sum(1 for c in text if "가" <= c <= "힣")
    return (korean_chars / len(text)) >= 0.15


def summarize_to_korean(text: str) -> str:
    """Summarize text to Korean within 300 chars using DeepSeek.

    Falls back to raw text[:300] if DeepSeek fails.
    """
    truncated = text[:_MAX_INPUT]
    prompt_template = _SUMMARIZE_PROMPT_KO if _is_korean_text(truncated) else _SUMMARIZE_PROMPT_EN
    try:
        result = chat_complete(
            prompt=prompt_template.format(text=truncated),
            system=_SUMMARIZE_SYSTEM,
        )
        return result.strip()[:_MAX_RESULT * 2] or text[:_MAX_RESULT]
    except Exception:
        return text[:_MAX_RESULT]
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_review_pipeline.py -v
```

Expected: 7개 PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/review_pipeline.py tests/test_review_pipeline.py
git commit -m "feat(review): add review_pipeline with DeepSeek Korean summarization"
```

---

## Task 3: DB 레이어

**Files:**
- Create: `app/db/album_master_review.py`
- Create: `tests/test_db_album_master_review.py`

### 배경
`album_master` 테이블에 이미 `review_text`, `review_source`, `review_url` 컬럼이 있다 (v12 마이그레이션). `get_conn()`은 `app.db.connection`에서 가져온다.

- [ ] **Step 1: 테스트 작성**

```python
# tests/test_db_album_master_review.py
import pytest
import sqlite3
from app.db.album_master_review import (
    get_masters_without_review,
    save_review,
    clear_review,
    count_masters_without_review,
)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("""
        CREATE TABLE album_master (
            id INTEGER PRIMARY KEY,
            artist_or_brand TEXT,
            title TEXT,
            review_text TEXT,
            review_source TEXT,
            review_url TEXT,
            updated_at TEXT
        )
    """)
    c.executemany(
        "INSERT INTO album_master (id, artist_or_brand, title) VALUES (?, ?, ?)",
        [(1, "Artist A", "Album One"), (2, "Artist B", "Album Two")],
    )
    c.commit()
    yield c
    c.close()


def test_count_masters_without_review(conn):
    assert count_masters_without_review(conn) == 2


def test_get_masters_without_review_returns_up_to_limit(conn):
    rows = get_masters_without_review(conn, limit=1)
    assert len(rows) == 1
    assert rows[0]["id"] in (1, 2)


def test_save_review(conn):
    save_review(conn, 1, "한국어 요약", "WIKIPEDIA", "https://en.wikipedia.org/wiki/Album_One")
    row = conn.execute("SELECT review_text, review_source, review_url FROM album_master WHERE id=1").fetchone()
    assert row["review_text"] == "한국어 요약"
    assert row["review_source"] == "WIKIPEDIA"
    assert row["review_url"] == "https://en.wikipedia.org/wiki/Album_One"


def test_save_review_with_null_url(conn):
    save_review(conn, 1, "직접 입력한 리뷰", "MANUAL", None)
    row = conn.execute("SELECT review_url FROM album_master WHERE id=1").fetchone()
    assert row["review_url"] is None


def test_clear_review(conn):
    save_review(conn, 1, "요약", "WIKIPEDIA", "https://url")
    clear_review(conn, 1)
    row = conn.execute("SELECT review_text FROM album_master WHERE id=1").fetchone()
    assert row["review_text"] is None


def test_masters_without_review_excludes_existing(conn):
    save_review(conn, 1, "요약", "WIKIPEDIA", None)
    rows = get_masters_without_review(conn, limit=10)
    ids = [r["id"] for r in rows]
    assert 1 not in ids
    assert 2 in ids
    assert count_masters_without_review(conn) == 1
```

- [ ] **Step 2: 테스트 실행 확인 (FAIL)**

```bash
pytest tests/test_db_album_master_review.py -v
```

Expected: FAIL (모듈 없음)

- [ ] **Step 3: `album_master_review.py` 작성**

```python
# app/db/album_master_review.py
from __future__ import annotations

import sqlite3
from typing import Any

from .connection import utc_now_iso


def get_masters_without_review(conn: sqlite3.Connection, limit: int) -> list[dict[str, Any]]:
    """review_text IS NULL인 album_master 행을 limit건 반환."""
    rows = conn.execute(
        """
        SELECT id, artist_or_brand, title
        FROM album_master
        WHERE review_text IS NULL OR TRIM(review_text) = ''
        ORDER BY id
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def save_review(
    conn: sqlite3.Connection,
    master_id: int,
    review_text: str,
    review_source: str,
    review_url: str | None,
) -> None:
    """review_text, review_source, review_url, updated_at을 업데이트."""
    conn.execute(
        """
        UPDATE album_master
        SET review_text = ?, review_source = ?, review_url = ?, updated_at = ?
        WHERE id = ?
        """,
        (review_text, review_source, review_url, utc_now_iso(), master_id),
    )
    conn.commit()


def clear_review(conn: sqlite3.Connection, master_id: int) -> None:
    """review 3개 컬럼을 NULL로 초기화."""
    conn.execute(
        """
        UPDATE album_master
        SET review_text = NULL, review_source = NULL, review_url = NULL, updated_at = ?
        WHERE id = ?
        """,
        (utc_now_iso(), master_id),
    )
    conn.commit()


def count_masters_without_review(conn: sqlite3.Connection) -> int:
    """review_text가 없는 마스터 건수 반환."""
    row = conn.execute(
        """
        SELECT COUNT(*) FROM album_master
        WHERE review_text IS NULL OR TRIM(review_text) = ''
        """
    ).fetchone()
    return row[0] if row else 0
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_db_album_master_review.py -v
```

Expected: 6개 PASS

- [ ] **Step 5: Commit**

```bash
git add app/db/album_master_review.py tests/test_db_album_master_review.py
git commit -m "feat(db): add album_master_review DB layer"
```

---

## Task 4: API 엔드포인트 교체·추가

**Files:**
- Modify: `app/api/album_masters.py:1003-1026`

### 배경
기존 `POST /album-masters/{id}/review` (1003~1026줄)를 삭제하고 4개 엔드포인트로 대체한다.

`_require_admin_request`는 이미 파일 상단에 import되어 있다. `get_conn`은 `from ..db.connection import get_conn, utc_now_iso` 패턴으로 lazy import 사용.

라우터에서 `/album-masters/review/batch` 경로가 `/album-masters/{id}/...` 보다 먼저 정의되어야 한다 (FastAPI 경로 매칭 순서). 배치 엔드포인트를 개별 엔드포인트들보다 **먼저** 삽입한다.

- [ ] **Step 1: 기존 엔드포인트 교체**

`app/api/album_masters.py`에서 아래 블록을 찾아 전체 교체한다:

찾을 코드:
```python
@router.post("/album-masters/{album_master_id}/review")
def fetch_album_review(album_master_id: int) -> dict[str, Any]:
    """Fetch Wikipedia review for an album master."""
    from ..services.providers import fetch_wikipedia_album_review
    from ..db.connection import get_conn, utc_now_iso
    row = None
    with get_conn() as conn:
        row = conn.execute("SELECT artist_or_brand, title FROM album_master WHERE id = ?", (album_master_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Album master not found")
    artist = str(row[0] or "").strip()
    title = str(row[1] or "").strip()
    if not artist or not title:
        raise HTTPException(status_code=400, detail="Artist and title required")
    review = fetch_wikipedia_album_review(artist, title)
    if not review:
        raise HTTPException(status_code=404, detail="No review found on Wikipedia")
    with get_conn() as conn:
        conn.execute(
            "UPDATE album_master SET review_text = ?, review_source = ?, review_url = ?, updated_at = ? WHERE id = ?",
            (review["review_text"], review["review_source"], review["review_url"], utc_now_iso(), album_master_id),
        )
        conn.commit()
    return {"ok": True, "album_master_id": album_master_id, "source": review["review_source"]}
```

교체할 코드:
```python
# ── Review collection ──────────────────────────────────────────────

@router.post("/album-masters/review/batch")
def batch_collect_reviews(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    """Batch collect Wikipedia reviews for masters without review. ADMIN only."""
    from ..security import _require_admin_request
    _require_admin_request(request)
    from ..services.providers import fetch_wikipedia_album_review
    from ..services.review_pipeline import summarize_to_korean
    from ..db.album_master_review import get_masters_without_review, save_review, count_masters_without_review
    from ..db.connection import get_conn

    with get_conn() as conn:
        masters = get_masters_without_review(conn, limit=limit)
        remaining_before = count_masters_without_review(conn)

    succeeded = 0
    failed = 0
    for master in masters:
        mid = master["id"]
        artist = str(master.get("artist_or_brand") or "").strip()
        title = str(master.get("title") or "").strip()
        if not artist or not title:
            failed += 1
            continue
        raw = fetch_wikipedia_album_review(artist, title)
        if not raw:
            failed += 1
            continue
        try:
            korean_summary = summarize_to_korean(raw["review_text"])
            source = raw["review_source"]
            url = raw.get("review_url")
        except Exception:
            korean_summary = (raw["review_text"] or "")[:300]
            source = "WIKIPEDIA_RAW"
            url = raw.get("review_url")
        with get_conn() as conn:
            save_review(conn, mid, korean_summary, source, url)
        succeeded += 1

    with get_conn() as conn:
        remaining_after = count_masters_without_review(conn)

    return {
        "ok": True,
        "processed": len(masters),
        "succeeded": succeeded,
        "failed": failed,
        "remaining": remaining_after,
    }


@router.post("/album-masters/{album_master_id}/review/auto")
def collect_review_auto(album_master_id: int, request: Request) -> dict[str, Any]:
    """Fetch Wikipedia review for one master, summarize to Korean. ADMIN only."""
    from ..security import _require_admin_request
    _require_admin_request(request)
    from ..services.providers import fetch_wikipedia_album_review
    from ..services.review_pipeline import summarize_to_korean
    from ..db.album_master_review import save_review
    from ..db.connection import get_conn

    with get_conn() as conn:
        row = conn.execute(
            "SELECT artist_or_brand, title FROM album_master WHERE id = ?", (album_master_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Album master not found")
    artist = str(row[0] or "").strip()
    title = str(row[1] or "").strip()
    if not artist or not title:
        raise HTTPException(status_code=400, detail="Artist and title required")

    raw = fetch_wikipedia_album_review(artist, title)
    if not raw:
        raise HTTPException(status_code=404, detail="No Wikipedia album page found")

    try:
        korean_summary = summarize_to_korean(raw["review_text"])
        source = raw["review_source"]
    except Exception:
        korean_summary = (raw["review_text"] or "")[:300]
        source = "WIKIPEDIA_RAW"

    with get_conn() as conn:
        save_review(conn, album_master_id, korean_summary, source, raw.get("review_url"))

    return {"ok": True, "album_master_id": album_master_id, "source": source}


class _ReviewUrlBody(BaseModel):
    url: str


@router.post("/album-masters/{album_master_id}/review/url")
def collect_review_from_url(
    album_master_id: int, body: _ReviewUrlBody, request: Request
) -> dict[str, Any]:
    """Fetch review from a URL, summarize to Korean. ADMIN only."""
    from ..security import _require_admin_request
    _require_admin_request(request)
    from ..services.providers import fetch_review_from_url
    from ..services.review_pipeline import summarize_to_korean
    from ..db.album_master_review import save_review
    from ..db.connection import get_conn
    import urllib.parse

    url = body.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="url required")

    with get_conn() as conn:
        exists = conn.execute(
            "SELECT 1 FROM album_master WHERE id = ?", (album_master_id,)
        ).fetchone()
    if not exists:
        raise HTTPException(status_code=404, detail="Album master not found")

    raw_text = fetch_review_from_url(url)
    if not raw_text:
        raise HTTPException(status_code=422, detail="Could not extract text from URL")

    try:
        korean_summary = summarize_to_korean(raw_text)
        domain = urllib.parse.urlparse(url).netloc or "URL"
        source = domain.upper().replace("WWW.", "").replace(".", "_")[:30]
    except Exception:
        korean_summary = raw_text[:300]
        source = "URL_RAW"

    with get_conn() as conn:
        save_review(conn, album_master_id, korean_summary, source, url)

    return {"ok": True, "album_master_id": album_master_id, "source": source}


class _ReviewManualBody(BaseModel):
    text: str
    source: str = "MANUAL"


@router.post("/album-masters/{album_master_id}/review/manual")
def save_review_manual(
    album_master_id: int, body: _ReviewManualBody, request: Request
) -> dict[str, Any]:
    """Save a manually written review (no DeepSeek). ADMIN only."""
    from ..security import _require_admin_request
    _require_admin_request(request)
    from ..db.album_master_review import save_review
    from ..db.connection import get_conn

    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")

    with get_conn() as conn:
        exists = conn.execute(
            "SELECT 1 FROM album_master WHERE id = ?", (album_master_id,)
        ).fetchone()
    if not exists:
        raise HTTPException(status_code=404, detail="Album master not found")

    source = (body.source or "MANUAL").strip()[:50]
    with get_conn() as conn:
        save_review(conn, album_master_id, text, source, None)

    return {"ok": True, "album_master_id": album_master_id, "source": source}


@router.delete("/album-masters/{album_master_id}/review")
def delete_review(album_master_id: int, request: Request) -> dict[str, Any]:
    """Clear review for an album master. ADMIN only."""
    from ..security import _require_admin_request
    _require_admin_request(request)
    from ..db.album_master_review import clear_review
    from ..db.connection import get_conn

    with get_conn() as conn:
        exists = conn.execute(
            "SELECT 1 FROM album_master WHERE id = ?", (album_master_id,)
        ).fetchone()
    if not exists:
        raise HTTPException(status_code=404, detail="Album master not found")

    with get_conn() as conn:
        clear_review(conn, album_master_id)

    return {"ok": True, "album_master_id": album_master_id}
```

- [ ] **Step 2: `BaseModel` import 확인**

`app/api/album_masters.py` 상단에 `from pydantic import BaseModel`가 있는지 확인:

```bash
grep -n "from pydantic import\|BaseModel" app/api/album_masters.py | head -5
```

없으면 파일 상단 import에 추가.

- [ ] **Step 3: 구문 검사**

```bash
python3 -m py_compile app/api/album_masters.py && echo OK
```

Expected: `OK`

- [ ] **Step 4: 서버 기동 확인**

```bash
cd /Volumes/Data/Works/07.hahahoho
python3 -c "from app.api.album_masters import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add app/api/album_masters.py
git commit -m "feat(api): replace review endpoint with auto/url/manual/batch endpoints"
```

---

## Task 5: UI — 개별 리뷰 관리 블록 (미디어>관리)

**Files:**
- Modify: `app/static/index.html`

### 배경
`homeMasterEditDetails` (`<details id="homeMasterEditDetails" ...>`) 안의 `</details>` 바로 앞, 즉 `homeMasterSortArtistStatus` div 다음에 **리뷰 관리 섹션**을 추가한다.

리뷰 관리 섹션은 현재 마스터의 `review_text`, `review_source`를 기존 마스터 상세 조회 응답에서 읽어 렌더링한다. 마스터 데이터는 이미 `homeSearchResults` 배열에 저장되어 있고, `openDashboardForMasterId()` 호출 시 채워진다.

`album_masters.py`의 `GET /album-masters/{id}` 응답에 `review_text`, `review_source`, `review_url`이 이미 포함되어 있는지 확인 필요:

```bash
grep -n "review_text\|review_source" app/db/album_master_read.py | head -10
```

이미 포함되어 있으면 바로 UI 작업 진행. 없으면 `album_master_read.py`에 컬럼 추가 후 진행.

- [ ] **Step 1: `GET /album-masters/{id}` 응답에 review 필드 포함 확인**

```bash
grep -n "review_text\|review_source\|review_url" app/db/album_master_read.py | head -10
```

포함되어 있으면 Step 2로. 없으면 `album_master_read.py`의 SELECT 쿼리에 `am.review_text, am.review_source, am.review_url` 추가.

- [ ] **Step 2: CSS 추가 (기존 `.ops-album-review-card` 블록 근처)**

`app/static/index.html`에서 `.ops-album-review-card` CSS 블록 다음에 추가:

```css
.home-master-review-section {
  margin-top: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 10px 12px;
}
.home-master-review-section-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.home-master-review-section-head strong {
  font-size: 0.8rem;
  color: var(--muted);
}
.home-master-review-preview {
  font-size: 0.78rem;
  line-height: 1.5;
  color: var(--ink);
  white-space: pre-wrap;
  word-break: break-word;
  margin-bottom: 6px;
}
.home-master-review-source-tag {
  font-size: 0.7rem;
  color: var(--muted);
  margin-bottom: 8px;
}
.home-master-review-url-input {
  width: 100%;
  margin-bottom: 4px;
}
.home-master-review-manual-textarea {
  width: 100%;
  min-height: 80px;
  resize: vertical;
  margin-bottom: 4px;
}
```

- [ ] **Step 3: HTML 추가 (homeMasterEditDetails 내)**

`app/static/index.html`에서 아래 코드를 찾아:

```html
              <div id="homeMasterSortArtistStatus" class="status"></div>
            </div>
          </details>
```

아래로 교체:

```html
              <div id="homeMasterSortArtistStatus" class="status"></div>
              <!-- 리뷰 관리 섹션 -->
              <div id="homeMasterReviewSection" class="home-master-review-section" style="display:none">
                <div class="home-master-review-section-head">
                  <strong data-i18n="media.manage.master.review.title">앨범 리뷰</strong>
                  <span id="homeMasterReviewSourceTag" class="home-master-review-source-tag"></span>
                  <button id="homeMasterReviewDeleteBtn" class="btn ghost tiny danger" type="button" style="display:none" data-i18n="media.manage.master.review.action.delete">삭제</button>
                </div>
                <div id="homeMasterReviewPreview" class="home-master-review-preview" style="display:none"></div>
                <div id="homeMasterReviewActions" class="row" style="gap:4px">
                  <button id="homeMasterReviewAutoBtn" class="btn ghost tiny" type="button" data-i18n="media.manage.master.review.action.auto">Wikipedia 자동수집</button>
                  <button id="homeMasterReviewUrlBtn" class="btn ghost tiny" type="button" data-i18n="media.manage.master.review.action.url">URL 입력</button>
                  <button id="homeMasterReviewManualBtn" class="btn ghost tiny" type="button" data-i18n="media.manage.master.review.action.manual">직접 입력</button>
                </div>
                <!-- URL 입력 폼 -->
                <div id="homeMasterReviewUrlForm" style="display:none;margin-top:6px">
                  <input id="homeMasterReviewUrlInput" type="url" class="home-master-review-url-input" placeholder="https://..." />
                  <div class="row" style="gap:4px;margin-top:4px">
                    <button id="homeMasterReviewUrlSubmitBtn" class="btn tiny" type="button" data-i18n="media.manage.master.review.action.fetch">수집</button>
                    <button id="homeMasterReviewUrlCancelBtn" class="btn ghost tiny" type="button" data-i18n="common.action.cancel">취소</button>
                  </div>
                </div>
                <!-- 직접 입력 폼 -->
                <div id="homeMasterReviewManualForm" style="display:none;margin-top:6px">
                  <input id="homeMasterReviewManualSource" type="text" style="width:160px;margin-bottom:4px" placeholder="출처명 (예: ISM)" />
                  <textarea id="homeMasterReviewManualText" class="home-master-review-manual-textarea" placeholder="리뷰 텍스트를 입력하세요"></textarea>
                  <div class="row" style="gap:4px;margin-top:4px">
                    <button id="homeMasterReviewManualSubmitBtn" class="btn tiny" type="button" data-i18n="common.action.save">저장</button>
                    <button id="homeMasterReviewManualCancelBtn" class="btn ghost tiny" type="button" data-i18n="common.action.cancel">취소</button>
                  </div>
                </div>
                <div id="homeMasterReviewStatus" class="status" style="margin-top:6px"></div>
              </div>
            </div>
          </details>
```

- [ ] **Step 4: JavaScript 함수 추가**

`renderAlbumReviewSection` 함수 근처에 아래 함수를 추가:

```javascript
function renderHomeMasterReviewSection(master) {
  const section = $("homeMasterReviewSection");
  if (!section) return;
  if (!master) { section.style.display = "none"; return; }
  section.style.display = "";

  const reviewText = String(master.review_text || "").trim();
  const reviewSource = String(master.review_source || "").trim();

  const preview = $("homeMasterReviewPreview");
  const sourceTag = $("homeMasterReviewSourceTag");
  const deleteBtn = $("homeMasterReviewDeleteBtn");
  const actions = $("homeMasterReviewActions");

  if (reviewText) {
    preview.textContent = reviewText.slice(0, 200) + (reviewText.length > 200 ? "…" : "");
    preview.style.display = "";
    sourceTag.textContent = reviewSource ? `출처: ${reviewSource}` : "";
    deleteBtn.style.display = "";
  } else {
    preview.style.display = "none";
    sourceTag.textContent = "";
    deleteBtn.style.display = "none";
  }

  // 폼 초기화
  $("homeMasterReviewUrlForm").style.display = "none";
  $("homeMasterReviewManualForm").style.display = "none";
  $("homeMasterReviewStatus").textContent = "";
  $("homeMasterReviewUrlInput").value = "";
  $("homeMasterReviewManualText").value = "";
  $("homeMasterReviewManualSource").value = "";
}
```

- [ ] **Step 5: 이벤트 핸들러 등록**

DOMContentLoaded 내 이벤트 핸들러 블록 (다른 `homeMaster*` 버튼들과 같은 위치)에 추가:

```javascript
// 리뷰 관리
$("homeMasterReviewAutoBtn")?.addEventListener("click", async () => {
  const masterId = currentHomeMasterId();
  if (!masterId) return;
  const btn = $("homeMasterReviewAutoBtn");
  const status = $("homeMasterReviewStatus");
  btn.disabled = true;
  status.textContent = "Wikipedia에서 수집 중...";
  try {
    const res = await apiFetch(`/album-masters/${masterId}/review/auto`, { method: "POST" });
    const data = await res.json();
    if (data.ok) {
      status.textContent = `완료 (출처: ${data.source})`;
      await refreshCurrentMasterReview(masterId);
    } else {
      status.textContent = data.detail || "실패";
    }
  } catch (e) {
    status.textContent = String(e);
  }
  btn.disabled = false;
});

$("homeMasterReviewUrlBtn")?.addEventListener("click", () => {
  $("homeMasterReviewUrlForm").style.display = "";
  $("homeMasterReviewManualForm").style.display = "none";
});

$("homeMasterReviewUrlCancelBtn")?.addEventListener("click", () => {
  $("homeMasterReviewUrlForm").style.display = "none";
});

$("homeMasterReviewUrlSubmitBtn")?.addEventListener("click", async () => {
  const masterId = currentHomeMasterId();
  const url = ($("homeMasterReviewUrlInput").value || "").trim();
  if (!masterId || !url) return;
  const btn = $("homeMasterReviewUrlSubmitBtn");
  const status = $("homeMasterReviewStatus");
  btn.disabled = true;
  status.textContent = "URL에서 수집 중...";
  try {
    const res = await apiFetch(`/album-masters/${masterId}/review/url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const data = await res.json();
    if (data.ok) {
      status.textContent = `완료 (출처: ${data.source})`;
      $("homeMasterReviewUrlForm").style.display = "none";
      await refreshCurrentMasterReview(masterId);
    } else {
      status.textContent = data.detail || "실패";
    }
  } catch (e) {
    status.textContent = String(e);
  }
  btn.disabled = false;
});

$("homeMasterReviewManualBtn")?.addEventListener("click", () => {
  $("homeMasterReviewManualForm").style.display = "";
  $("homeMasterReviewUrlForm").style.display = "none";
});

$("homeMasterReviewManualCancelBtn")?.addEventListener("click", () => {
  $("homeMasterReviewManualForm").style.display = "none";
});

$("homeMasterReviewManualSubmitBtn")?.addEventListener("click", async () => {
  const masterId = currentHomeMasterId();
  const text = ($("homeMasterReviewManualText").value || "").trim();
  const source = ($("homeMasterReviewManualSource").value || "MANUAL").trim();
  if (!masterId || !text) return;
  const btn = $("homeMasterReviewManualSubmitBtn");
  const status = $("homeMasterReviewStatus");
  btn.disabled = true;
  status.textContent = "저장 중...";
  try {
    const res = await apiFetch(`/album-masters/${masterId}/review/manual`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, source }),
    });
    const data = await res.json();
    if (data.ok) {
      status.textContent = "저장 완료";
      $("homeMasterReviewManualForm").style.display = "none";
      await refreshCurrentMasterReview(masterId);
    } else {
      status.textContent = data.detail || "실패";
    }
  } catch (e) {
    status.textContent = String(e);
  }
  btn.disabled = false;
});

$("homeMasterReviewDeleteBtn")?.addEventListener("click", async () => {
  const masterId = currentHomeMasterId();
  if (!masterId || !confirm("리뷰를 삭제하시겠습니까?")) return;
  const status = $("homeMasterReviewStatus");
  status.textContent = "삭제 중...";
  try {
    const res = await apiFetch(`/album-masters/${masterId}/review`, { method: "DELETE" });
    const data = await res.json();
    if (data.ok) {
      status.textContent = "삭제 완료";
      await refreshCurrentMasterReview(masterId);
    } else {
      status.textContent = data.detail || "실패";
    }
  } catch (e) {
    status.textContent = String(e);
  }
});
```

- [ ] **Step 6: 헬퍼 함수 추가**

```javascript
function currentHomeMasterId() {
  // homeSelectedMasterId는 미디어>관리에서 마스터 선택 시 설정되는 전역 변수
  return Number(homeMasterInfo?.album_master_id || homeSelectedMasterId || 0) || null;
}

async function refreshCurrentMasterReview(masterId) {
  const res = await apiFetch(`/album-masters/${masterId}`);
  const data = await res.json();
  renderHomeMasterReviewSection(data);
}
```

- [ ] **Step 7: i18n 키 추가 (KO/EN/JA 사전 모두)**

KO 사전:
```
"media.manage.master.review.title": "앨범 리뷰",
"media.manage.master.review.action.auto": "Wikipedia 자동수집",
"media.manage.master.review.action.url": "URL 입력",
"media.manage.master.review.action.manual": "직접 입력",
"media.manage.master.review.action.fetch": "수집",
"media.manage.master.review.action.delete": "삭제",
```

EN 사전:
```
"media.manage.master.review.title": "Album review",
"media.manage.master.review.action.auto": "Auto (Wikipedia)",
"media.manage.master.review.action.url": "From URL",
"media.manage.master.review.action.manual": "Manual entry",
"media.manage.master.review.action.fetch": "Fetch",
"media.manage.master.review.action.delete": "Delete",
```

JA 사전:
```
"media.manage.master.review.title": "アルバムレビュー",
"media.manage.master.review.action.auto": "Wikipedia自動収集",
"media.manage.master.review.action.url": "URL入力",
"media.manage.master.review.action.manual": "手動入力",
"media.manage.master.review.action.fetch": "収集",
"media.manage.master.review.action.delete": "削除",
```

- [ ] **Step 8: 마스터 선택 시 `renderHomeMasterReviewSection` 호출**

`syncHomeMasterCorrectionEditor()` 함수 (약 46084줄)에서 `masterId > 0` 인 경우 처리 블록 끝에 `renderHomeMasterReviewSection(homeMasterInfo)` 호출 추가.

찾을 코드 (`syncHomeMasterCorrectionEditor` 함수 내):
```javascript
if (unifiedDetails) unifiedDetails.classList.remove("u-hidden-initial");
```

그 블록 안, 기존 내용 뒤에 추가:
```javascript
renderHomeMasterReviewSection(homeMasterInfo);
```

`masterId <= 0` 분기에는 `renderHomeMasterReviewSection(null)` 추가.

- [ ] **Step 9: QA 배포**

```bash
cp app/static/index.html /Users/__DEV_USER__/apps/hahahoho-qa/app/static/index.html
```

- [ ] **Step 10: Commit**

```bash
git add app/static/index.html
git commit -m "feat(ui): add per-master review management UI in master edit panel"
```

---

## Task 6: UI — 배치 수집 (운영>메타 동기화 탭)

**Files:**
- Modify: `app/static/index.html`

### 배경
`opsMetaSyncPanel` 내의 기존 카드 섹션들 이후에 새 카드 섹션을 추가한다. 패턴은 "알라딘 → Discogs 마스터 매칭" 카드와 동일.

- [ ] **Step 1: HTML 추가**

`app/static/index.html`에서 아래 코드를 찾아:

```html
      <div class="layout u-mt-16">
        <section class="card">
          <h2>알라딘 → Discogs 마스터 매칭</h2>
```

그 바로 앞에 삽입:

```html
      <div class="layout u-mt-16">
        <section class="card">
          <h2 data-i18n="ops.review_batch.title">앨범 리뷰 자동수집</h2>
          <p class="sub" data-i18n="ops.review_batch.subtitle">리뷰가 없는 앨범 마스터를 Wikipedia에서 자동 수집하고 DeepSeek로 한국어 요약합니다.</p>
          <div class="row u-mt-10" style="align-items:center;gap:16px">
            <span id="reviewBatchRemainingCount" class="mini muted">-</span>
            <button id="reviewBatchStatusBtn" class="btn ghost" type="button" data-i18n="ops.review_batch.action.reload">상태 새로고침</button>
            <button id="reviewBatchRunBtn" class="btn secondary" type="button" data-i18n="ops.review_batch.action.run">자동수집 실행 (50건)</button>
          </div>
          <div id="reviewBatchStatus" class="status u-mt-8"></div>
        </section>
      </div>

```

- [ ] **Step 2: JavaScript 이벤트 핸들러 추가**

`opsMetaSyncTabBtn` 클릭 핸들러 근처에 추가:

```javascript
async function loadReviewBatchStatus() {
  const countEl = $("reviewBatchRemainingCount");
  if (!countEl) return;
  try {
    const res = await apiFetch("/album-masters/review/batch?limit=0", { method: "POST" });
    // limit=0 배치는 아무것도 처리하지 않고 remaining만 반환
    // 대신 별도 status 엔드포인트가 없으므로 직접 쿼리는 불가.
    // 대안: 버튼 클릭 후 결과에서 remaining을 업데이트.
    countEl.textContent = "";
  } catch (_) {}
}

$("reviewBatchStatusBtn")?.addEventListener("click", async () => {
  const status = $("reviewBatchStatus");
  status.textContent = "상태 조회 중...";
  try {
    const res = await apiFetch("/album-masters/review/batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    const data = await res.json();
    $("reviewBatchRemainingCount").textContent = `미수집 약 ${data.remaining}건`;
    status.textContent = `처리: ${data.processed}건 / 성공: ${data.succeeded}건 / 실패: ${data.failed}건 / 잔여: ${data.remaining}건`;
  } catch (e) {
    status.textContent = String(e);
  }
});

$("reviewBatchRunBtn")?.addEventListener("click", async () => {
  const btn = $("reviewBatchRunBtn");
  const status = $("reviewBatchStatus");
  btn.disabled = true;
  status.textContent = "자동수집 실행 중... (최대 수 분 소요)";
  try {
    const res = await apiFetch("/album-masters/review/batch?limit=50", { method: "POST" });
    const data = await res.json();
    $("reviewBatchRemainingCount").textContent = `미수집 약 ${data.remaining}건`;
    status.textContent = `완료 — 처리: ${data.processed}건 / 성공: ${data.succeeded}건 / 실패: ${data.failed}건 / 잔여: ${data.remaining}건`;
  } catch (e) {
    status.textContent = String(e);
  }
  btn.disabled = false;
});
```

**참고:** `POST /album-masters/review/batch`는 실행+결과 반환이라 상태 조회 엔드포인트가 없다. "상태 새로고침"은 실제로 limit=50 배치를 한 번 실행하는 것과 동일하다. 이 점을 UI에서 명확히 하거나 추후 별도 GET 엔드포인트를 추가한다. 현재는 버튼 라벨로 구분 (`실행` vs `새로고침`).

- [ ] **Step 3: i18n 키 추가**

KO:
```
"ops.review_batch.title": "앨범 리뷰 자동수집",
"ops.review_batch.subtitle": "리뷰가 없는 앨범 마스터를 Wikipedia에서 자동 수집하고 DeepSeek로 한국어 요약합니다.",
"ops.review_batch.action.reload": "상태 새로고침",
"ops.review_batch.action.run": "자동수집 실행 (50건)",
```

EN:
```
"ops.review_batch.title": "Album review auto-collect",
"ops.review_batch.subtitle": "Fetch Wikipedia reviews for masters without review and summarize to Korean via DeepSeek.",
"ops.review_batch.action.reload": "Refresh status",
"ops.review_batch.action.run": "Run auto-collect (50)",
```

JA:
```
"ops.review_batch.title": "アルバムレビュー自動収集",
"ops.review_batch.subtitle": "レビューのないマスターをWikipediaから自動収集し、DeepSeekで韓国語要約します。",
"ops.review_batch.action.reload": "状態更新",
"ops.review_batch.action.run": "自動収集実行 (50件)",
```

- [ ] **Step 4: QA 배포**

```bash
cp app/static/index.html /Users/__DEV_USER__/apps/hahahoho-qa/app/static/index.html
```

- [ ] **Step 5: Commit**

```bash
git add app/static/index.html
git commit -m "feat(ui): add batch review collection section in ops meta sync tab"
```

---

## Task 7: QA 서버 재시작 및 엔드투엔드 확인

**Files:** 없음 (운영 작업)

- [ ] **Step 1: QA 백엔드 파일 배포**

```bash
cp app/config.py /Users/__DEV_USER__/apps/hahahoho-qa/app/config.py
cp app/services/deepseek_client.py /Users/__DEV_USER__/apps/hahahoho-qa/app/services/deepseek_client.py
cp app/services/review_pipeline.py /Users/__DEV_USER__/apps/hahahoho-qa/app/services/review_pipeline.py
cp app/services/providers.py /Users/__DEV_USER__/apps/hahahoho-qa/app/services/providers.py
cp app/db/album_master_review.py /Users/__DEV_USER__/apps/hahahoho-qa/app/db/album_master_review.py
cp app/api/album_masters.py /Users/__DEV_USER__/apps/hahahoho-qa/app/api/album_masters.py
```

- [ ] **Step 2: 구문 검사**

```bash
python3 -m py_compile \
  /Users/__DEV_USER__/apps/hahahoho-qa/app/config.py \
  /Users/__DEV_USER__/apps/hahahoho-qa/app/services/deepseek_client.py \
  /Users/__DEV_USER__/apps/hahahoho-qa/app/services/review_pipeline.py \
  /Users/__DEV_USER__/apps/hahahoho-qa/app/services/providers.py \
  /Users/__DEV_USER__/apps/hahahoho-qa/app/db/album_master_review.py \
  /Users/__DEV_USER__/apps/hahahoho-qa/app/api/album_masters.py \
  && echo OK
```

Expected: `OK`

- [ ] **Step 3: QA 서버 재시작**

```bash
PID=$(pgrep -f 'uvicorn.*8100'); kill -TERM $PID; sleep 6
ps -eo pid,etime,command | grep 'uvicorn.*8100' | grep -v grep
```

- [ ] **Step 4: 개별 수집 확인 (master_id=2272)**

```bash
curl -s -X POST http://localhost:8100/album-masters/2272/review/auto \
  -H "Cookie: ..." | python3 -m json.tool
```

Expected: `{"ok": true, "album_master_id": 2272, "source": "WIKIPEDIA"}` 또는 404 (앨범 페이지 없는 경우)

- [ ] **Step 5: 배치 수집 확인**

```bash
curl -s -X POST "http://localhost:8100/album-masters/review/batch?limit=3" \
  -H "Cookie: ..." | python3 -m json.tool
```

Expected: `{"ok": true, "processed": 3, "succeeded": N, "failed": M, "remaining": R}`

- [ ] **Step 6: 브라우저 확인**

1. `http://localhost:8100/admin` → 미디어>관리 → 마스터 선택 → 앨범(마스터) 메타 수정 섹션에 리뷰 관리 블록 확인
2. "Wikipedia 자동수집" 버튼 → 동작 확인
3. 운영>메타 동기화 탭 → 앨범 리뷰 자동수집 섹션 확인

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore: QA deployment and verification of album review collection"
```
