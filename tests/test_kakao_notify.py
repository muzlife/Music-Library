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
    import asyncio
    asyncio.run(send_kakao_message("test"))


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

    asyncio.run(run())
