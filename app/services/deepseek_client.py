from __future__ import annotations

from functools import lru_cache

from openai import OpenAI

from ..config import get_settings


@lru_cache(maxsize=1)
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
    if not resp.choices:
        raise RuntimeError("DeepSeek returned no choices")
    return resp.choices[0].message.content or ""
