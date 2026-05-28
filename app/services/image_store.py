"""
app/services/image_store.py

로컬 이미지 다운로드 & 저장 서비스.

- 저장 경로: static/images/owned/{owned_item_id}/{NNN}_{md5}.jpg
- 서빙 URL:  /ui-static/images/owned/{owned_item_id}/{NNN}_{md5}.jpg
- 소스 URL은 local_image_items_json의 source_url 필드로 보존
- 파일이 이미 존재하면 다운로드 생략 (멱등)
- 소스별 요청 헤더(Referer, User-Agent)를 달리 적용
- 최대 MAX_IMAGES 개 제한 (Discogs는 이미지가 많을 수 있음)
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import re
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

MAX_IMAGES = 20          # 소스당 다운로드 상한
TIMEOUT    = 12.0        # 초
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# ─── 헬퍼 ──────────────────────────────────────────────────────────────

def _image_dir(static_dir: Path, owned_item_id: int) -> Path:
    d = static_dir / "images" / "owned" / str(owned_item_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _filename(url: str, idx: int, content_type: str | None = None) -> str:
    """URL + 순서로 결정론적 파일명 생성."""
    h = hashlib.md5(url.encode()).hexdigest()[:12]
    ext = ".jpg"
    if content_type:
        guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if guessed and guessed not in {".jpe"}:
            ext = guessed
    elif url.lower().endswith(".png"):
        ext = ".png"
    elif url.lower().endswith(".gif"):
        ext = ".gif"
    elif url.lower().endswith(".webp"):
        ext = ".webp"
    return f"{idx:03d}_{h}{ext}"


def _source_headers(source: str, source_external_id: str | None = None) -> dict[str, str]:
    headers: dict[str, str] = {"User-Agent": USER_AGENT}
    s = (source or "").upper()
    if s == "ALADIN":
        headers["Referer"] = (
            f"https://www.aladin.co.kr/shop/wproduct.aspx?ItemId={source_external_id}"
            if source_external_id else "https://www.aladin.co.kr/"
        )
        headers["Accept-Language"] = "ko-KR,ko;q=0.9"
    elif s == "DISCOGS":
        headers["Referer"] = "https://www.discogs.com/"
    elif s == "MANIADB":
        headers["Referer"] = "https://www.maniadb.com/"
    return headers


# ─── 메인 API ────────────────────────────────────────────────────────────

def download_images(
    owned_item_id: int,
    image_items: list[dict[str, Any]],
    source: str,
    static_dir: Path,
    source_external_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    image_items 의 uri 를 다운로드해 static_dir 아래에 저장.

    Parameters
    ----------
    owned_item_id       : owned_item.id
    image_items         : [{"type": "앞면", "uri": "https://...", ...}, ...]
    source              : "DISCOGS" | "ALADIN" | "MANIADB" | ...
    static_dir          : STATIC_DIR (Path)
    source_external_id  : Referer 헤더 구성에 사용

    Returns
    -------
    local_image_items : [{"type": ..., "local_path": "/ui-static/...", "source_url": "...", "source": ...}]
    """
    if not image_items:
        return []

    img_dir = _image_dir(static_dir, owned_item_id)
    headers = _source_headers(source, source_external_id)
    result: list[dict[str, Any]] = []

    with httpx.Client(
        timeout=TIMEOUT,
        follow_redirects=True,
        headers=headers,
    ) as client:
        for idx, item in enumerate(image_items[:MAX_IMAGES]):
            uri = str(item.get("uri") or "").strip()
            if not uri or not uri.startswith("http"):
                continue

            fname = _filename(uri, idx)
            local_file = img_dir / fname
            local_path = f"/ui-static/images/owned/{owned_item_id}/{fname}"

            # 이미 존재하면 skip
            if local_file.exists() and local_file.stat().st_size > 0:
                result.append({
                    "type":       item.get("type") or "추가",
                    "local_path": local_path,
                    "source_url": uri,
                    "source":     source,
                    "width":      item.get("width"),
                    "height":     item.get("height"),
                })
                continue

            try:
                resp = client.get(uri)
                if resp.status_code == 200 and resp.content:
                    # content-type 기반으로 확장자 재확인
                    ct = resp.headers.get("content-type", "")
                    fname2 = _filename(uri, idx, ct)
                    if fname2 != fname:
                        local_file  = img_dir / fname2
                        local_path  = f"/ui-static/images/owned/{owned_item_id}/{fname2}"

                    local_file.write_bytes(resp.content)
                    result.append({
                        "type":       item.get("type") or "추가",
                        "local_path": local_path,
                        "source_url": uri,
                        "source":     source,
                        "width":      item.get("width"),
                        "height":     item.get("height"),
                    })
                    logger.debug("image saved: %s → %s", uri, local_path)
                else:
                    logger.warning("image download %r → HTTP %s", uri, resp.status_code)
            except Exception as exc:
                logger.warning("image download %r failed: %s", uri, exc)

    return result


def get_local_image_dir(static_dir: Path, owned_item_id: int) -> Path:
    """외부에서 이미지 디렉터리 경로가 필요한 경우 사용."""
    return _image_dir(static_dir, owned_item_id)
