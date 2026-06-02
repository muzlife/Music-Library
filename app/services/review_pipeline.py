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
