"""카카오 나에게 보내기 알림 서비스.

카카오 REST API를 사용해 운영자 본인 카카오톡으로 메시지를 전송한다.
KAKAO_REST_API_KEY / KAKAO_REFRESH_TOKEN 미설정 시 조용히 스킵.
"""
from __future__ import annotations

import json as _json
import logging

import httpx

logger = logging.getLogger(__name__)

_KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
_KAKAO_SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


def _get_settings():
    from app.config import get_settings
    return get_settings()


async def _get_access_token(
    client: httpx.AsyncClient,
    refresh_token: str,
    rest_api_key: str,
    client_secret: str | None = None,
) -> str | None:
    """refresh_token으로 access_token을 발급받는다."""
    try:
        data: dict[str, str] = {
            "grant_type": "refresh_token",
            "client_id": rest_api_key,
            "refresh_token": refresh_token,
        }
        if client_secret:
            data["client_secret"] = client_secret
        resp = await client.post(
            _KAKAO_TOKEN_URL,
            data=data,
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
                client, settings.kakao_refresh_token, settings.kakao_rest_api_key,
                client_secret=settings.kakao_client_secret,
            )
            if not access_token:
                return

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
