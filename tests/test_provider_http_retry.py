"""Unit coverage for the shared provider HTTP retry helper.

The helper has to:
  * retry 429/5xx responses,
  * honour Retry-After when present (seconds form),
  * cap retries to PROVIDER_HTTP_RETRY_MAX_ATTEMPTS,
  * raise the final exception for connection-level errors,
  * return the response untouched for terminal status codes (e.g. 404).

These tests use httpx.MockTransport so we don't make real network calls.
"""

from __future__ import annotations

from typing import Callable

import httpx
import pytest

from app.services import providers as providers_module


def _client_with_handler(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    """Build a real httpx.Client that routes through MockTransport."""
    return httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)


def test_retry_helper_returns_immediately_on_2xx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(providers_module.time, "sleep", lambda *_a, **_kw: None)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"ok": True})

    with _client_with_handler(handler) as client:
        response = providers_module._get_with_retry(client, "https://example.test/api")
    assert response.status_code == 200
    assert calls["n"] == 1, "no retries should fire on a 200 response"


def test_retry_helper_retries_429_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(providers_module.time, "sleep", lambda d, *_a, **_kw: sleeps.append(d))

    sequence = iter(
        [
            httpx.Response(429, headers={"retry-after": "0.25"}),
            httpx.Response(429, headers={"retry-after": "0.5"}),
            httpx.Response(200, json={"ok": True}),
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return next(sequence)

    with _client_with_handler(handler) as client:
        response = providers_module._get_with_retry(
            client,
            "https://example.test/api",
            max_attempts=3,
            backoff_base_sec=0.01,
            backoff_cap_sec=0.05,
        )

    assert response.status_code == 200
    # Two 429s mean two sleeps; both must come from Retry-After (not the
    # exponential schedule), proving the header is honoured.
    assert sleeps == pytest.approx([0.25, 0.5])


def test_retry_helper_uses_exponential_backoff_when_no_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(providers_module.time, "sleep", lambda d, *_a, **_kw: sleeps.append(d))

    sequence = iter(
        [
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(200, json={"ok": True}),
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return next(sequence)

    with _client_with_handler(handler) as client:
        response = providers_module._get_with_retry(
            client,
            "https://example.test/api",
            max_attempts=3,
            backoff_base_sec=0.05,
            backoff_cap_sec=10.0,
        )

    assert response.status_code == 200
    # Exponential schedule: base * 2**0, base * 2**1.
    assert sleeps == pytest.approx([0.05, 0.10])


def test_retry_helper_returns_terminal_4xx_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(providers_module.time, "sleep", lambda d, *_a, **_kw: sleeps.append(d))
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(404, json={"error": "not found"})

    with _client_with_handler(handler) as client:
        response = providers_module._get_with_retry(client, "https://example.test/missing")

    assert response.status_code == 404
    assert calls["n"] == 1
    assert sleeps == []


def test_retry_helper_gives_up_and_returns_final_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(providers_module.time, "sleep", lambda *_a, **_kw: None)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(502)

    with _client_with_handler(handler) as client:
        response = providers_module._get_with_retry(
            client,
            "https://example.test/api",
            max_attempts=2,
            backoff_base_sec=0.01,
            backoff_cap_sec=0.02,
        )

    assert response.status_code == 502
    # max_attempts=2 means up to 3 total request attempts (initial + 2 retries).
    assert calls["n"] == 3


def test_retry_helper_retries_connection_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(providers_module.time, "sleep", lambda *_a, **_kw: None)
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        if state["n"] <= 2:
            raise httpx.ConnectError("connection reset", request=request)
        return httpx.Response(200, json={"ok": True})

    with _client_with_handler(handler) as client:
        response = providers_module._get_with_retry(
            client,
            "https://example.test/api",
            max_attempts=3,
            backoff_base_sec=0.01,
            backoff_cap_sec=0.02,
        )

    assert response.status_code == 200
    assert state["n"] == 3


def test_retry_helper_reraises_after_exhausting_connection_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(providers_module.time, "sleep", lambda *_a, **_kw: None)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("dns fail", request=request)

    with _client_with_handler(handler) as client:
        with pytest.raises(httpx.ConnectError):
            providers_module._get_with_retry(
                client,
                "https://example.test/api",
                max_attempts=1,
                backoff_base_sec=0.01,
                backoff_cap_sec=0.02,
            )


def test_parse_retry_after_seconds_and_invalid() -> None:
    parse = providers_module._parse_retry_after_header
    assert parse("0") == 0.0
    assert parse("3.5") == 3.5
    assert parse("") is None
    assert parse(None) is None
    assert parse("not-a-number") is None
    # Negative values are rejected.
    assert parse("-1") is None


def test_make_http_client_returns_httpx_client_with_transport() -> None:
    with providers_module._make_http_client() as client:
        assert isinstance(client, httpx.Client)
        # No public API exposes the retry count, but the client must at least
        # be configured with our timeout default.
        assert client.timeout.read == providers_module.PROVIDER_HTTP_TIMEOUT_SEC


def test_has_default_user_agent_placeholder_detects_example_contact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import config as config_module

    config_module.get_settings.cache_clear()
    monkeypatch.setenv(
        "DISCOGS_USER_AGENT", "__PROJECT_SLUG__-library/0.1 (contact: your-email@example.com)"
    )
    monkeypatch.setenv(
        "MUSICBRAINZ_USER_AGENT", "__PROJECT_SLUG__-library/0.1 (contact: __OPS_EMAIL__)"
    )
    try:
        assert providers_module.has_default_user_agent_placeholder() is True
    finally:
        config_module.get_settings.cache_clear()


def test_has_default_user_agent_placeholder_clean_when_replaced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import config as config_module

    config_module.get_settings.cache_clear()
    monkeypatch.setenv(
        "DISCOGS_USER_AGENT", "__PROJECT_SLUG__-library/0.1 (contact: __OPS_EMAIL__)"
    )
    monkeypatch.setenv(
        "MUSICBRAINZ_USER_AGENT", "__PROJECT_SLUG__-library/0.1 (contact: __OPS_EMAIL__)"
    )
    try:
        assert providers_module.has_default_user_agent_placeholder() is False
    finally:
        config_module.get_settings.cache_clear()
