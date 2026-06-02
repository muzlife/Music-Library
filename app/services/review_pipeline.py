from __future__ import annotations

import httpx

from ..config import get_settings
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


def translate_to_korean_with_deepl(text: str) -> str:
    """Translate text to Korean using DeepL. Returns translated text.

    Raises RuntimeError if DeepL is not configured.
    Raises httpx.HTTPError on API failure.
    """
    content = str(text or "").strip()
    if not content:
        return content

    settings = get_settings()
    auth_key = str(settings.deepl_auth_key or "").strip()
    base_url = str(settings.deepl_base_url or "").strip()
    if not auth_key:
        raise RuntimeError("DEEPL_AUTH_KEY not configured")

    api_root = "https://api-free.deepl.com" if auth_key.endswith(":fx") else "https://api.deepl.com"
    if base_url:
        from urllib.parse import urlparse
        parsed = urlparse(base_url)
        if str(parsed.hostname or "").lower() in {"api-free.deepl.com", "api.deepl.com"}:
            api_root = f"{parsed.scheme or 'https'}://{parsed.hostname}"

    response = httpx.post(
        f"{api_root}/v2/translate",
        headers={
            "Authorization": f"DeepL-Auth-Key {auth_key}",
            "User-Agent": "hahahoho-library/0.1 (review translation)",
        },
        json={"text": [content], "target_lang": "KO"},
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json() or {}
    translations = payload.get("translations")
    if not isinstance(translations, list) or not translations:
        raise RuntimeError("DeepL returned empty translations")
    translated = str((translations[0] or {}).get("text") or "").strip()
    if not translated:
        raise RuntimeError("DeepL returned empty text")
    return translated


def summarize_to_korean(text: str) -> str:
    """Summarize text to Korean within 300 chars using DeepSeek.

    Raises RuntimeError if DeepSeek is not configured so callers can
    fall back to saving raw text.  Other API errors fall back to raw text.
    """
    truncated = text[:_MAX_INPUT]
    prompt_template = _SUMMARIZE_PROMPT_KO if _is_korean_text(truncated) else _SUMMARIZE_PROMPT_EN
    try:
        result = chat_complete(
            prompt=prompt_template.format(text=truncated),
            system=_SUMMARIZE_SYSTEM,
        )
        return result.strip()[:_MAX_RESULT * 2] or text[:_MAX_RESULT]
    except RuntimeError:
        raise
    except Exception:
        return text[:_MAX_RESULT]
