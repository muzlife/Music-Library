from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote

import httpx

from ..config import get_settings

__all__ = [
    "_OFFICE_CLIMATE_CACHE",
    "_SEOUL_WEATHER_CACHE",
    "_home_assistant_api_base_url",
    "_fetch_home_assistant_state",
    "_coerce_home_assistant_number",
    "_office_climate_comfort_label",
    "_load_operator_office_climate",
    "_load_operator_seoul_weather",
    "_wmo_weather_code_to_desc",
]

_OFFICE_CLIMATE_CACHE: dict[str, Any] | None = None
_OFFICE_CLIMATE_CACHE_DATA: dict[str, Any] | None = None
_OFFICE_CLIMATE_CACHE_TS: float = 0.0
_OFFICE_CLIMATE_TTL = 60.0

_SEOUL_WEATHER_CACHE: dict[str, Any] | None = None
_SEOUL_WEATHER_CACHE_DATA: dict[str, Any] | None = None
_SEOUL_WEATHER_CACHE_TS: float = 0.0
_SEOUL_WEATHER_TTL = 600.0


def _home_assistant_api_base_url() -> str:
    raw = str(get_settings().home_assistant_base_url or "").strip().rstrip("/")
    if raw.endswith("/api"):
        return raw
    return f"{raw}/api" if raw else ""


def _fetch_home_assistant_state(entity_id: str) -> dict[str, Any] | None:
    token = str(get_settings().home_assistant_token or "").strip()
    api_base = _home_assistant_api_base_url()
    entity = str(entity_id or "").strip()
    if not (token and api_base and entity):
        return None
    url = f"{api_base}/states/{quote(entity, safe='._-')}"
    response = httpx.get(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=5.0,
        follow_redirects=True,
    )
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else None


def _coerce_home_assistant_number(value: Any) -> float | None:
    raw = str(value or "").strip().lower()
    if raw in {"", "unknown", "unavailable", "none"}:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _office_climate_comfort_label(temperature_c: float | None, humidity_percent: float | None) -> str | None:
    if humidity_percent is not None:
        if humidity_percent < 40:
            return "건조"
        if humidity_percent > 65:
            return "습함"
    if temperature_c is not None:
        if temperature_c < 18:
            return "서늘"
        if temperature_c > 27:
            return "따뜻함"
    if temperature_c is None and humidity_percent is None:
        return None
    return "쾌적"


def _load_operator_office_climate() -> dict[str, Any]:
    global _OFFICE_CLIMATE_CACHE, _OFFICE_CLIMATE_CACHE_DATA, _OFFICE_CLIMATE_CACHE_TS

    if (
        time.monotonic() - _OFFICE_CLIMATE_CACHE_TS < _OFFICE_CLIMATE_TTL
        and _OFFICE_CLIMATE_CACHE_DATA is not None
    ):
        return _OFFICE_CLIMATE_CACHE_DATA

    try:
        settings = get_settings()
        temperature_state = _fetch_home_assistant_state(settings.office_climate_temperature_entity_id)
        humidity_state = _fetch_home_assistant_state(settings.office_climate_humidity_entity_id)

        temperature_c = _coerce_home_assistant_number(temperature_state.get("state") if temperature_state else None)
        humidity_percent = _coerce_home_assistant_number(humidity_state.get("state") if humidity_state else None)

        updated_candidates = [
            str(temperature_state.get("last_updated") or temperature_state.get("last_changed") or "").strip()
            if temperature_state else "",
            str(humidity_state.get("last_updated") or humidity_state.get("last_changed") or "").strip()
            if humidity_state else "",
        ]
        updated_at = max([item for item in updated_candidates if item], default=None)

        comfort_label = _office_climate_comfort_label(temperature_c, humidity_percent)
        available = temperature_c is not None or humidity_percent is not None

        result = {
            "available": available,
            "source": "home_assistant",
            "location_label": "상주 사무실",
            "description": "온/습도계",
            "temperature_c": temperature_c,
            "humidity_percent": humidity_percent,
            "comfort_label": comfort_label,
            "updated_at": updated_at,
        }

        _OFFICE_CLIMATE_CACHE_DATA = result
        _OFFICE_CLIMATE_CACHE = result
        _OFFICE_CLIMATE_CACHE_TS = time.monotonic()
        return result

    except Exception:
        if _OFFICE_CLIMATE_CACHE_DATA is not None:
            return {**_OFFICE_CLIMATE_CACHE_DATA, "stale": True}
        raise


def _load_operator_seoul_weather() -> dict[str, Any]:
    global _SEOUL_WEATHER_CACHE, _SEOUL_WEATHER_CACHE_DATA, _SEOUL_WEATHER_CACHE_TS

    if (
        time.monotonic() - _SEOUL_WEATHER_CACHE_TS < _SEOUL_WEATHER_TTL
        and _SEOUL_WEATHER_CACHE_DATA is not None
    ):
        return _SEOUL_WEATHER_CACHE_DATA

    try:
        response = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": 37.5665,
                "longitude": 126.9780,
                "current": "temperature_2m,relative_humidity_2m,is_day,weather_code",
                "daily": "temperature_2m_max,temperature_2m_min",
                "forecast_days": 1,
                "timezone": "Asia/Seoul",
            },
            timeout=10.0,
            follow_redirects=True,
        )
        response.raise_for_status()
        payload = response.json() if response.content else {}
        current = payload.get("current") if isinstance(payload, dict) and isinstance(payload.get("current"), dict) else {}
        daily = payload.get("daily") if isinstance(payload, dict) and isinstance(payload.get("daily"), dict) else {}

        temperature_c = current.get("temperature_2m")
        humidity_percent = current.get("relative_humidity_2m")
        weather_code = current.get("weather_code")
        is_day = current.get("is_day")

        daily_max = daily.get("temperature_2m_max") if isinstance(daily.get("temperature_2m_max"), list) else []
        daily_min = daily.get("temperature_2m_min") if isinstance(daily.get("temperature_2m_min"), list) else []
        temperature_high_c = daily_max[0] if daily_max else None
        temperature_low_c = daily_min[0] if daily_min else None

        updated_at = str(current.get("time") or "").strip() or None
        available = temperature_c is not None

        result = {
            "available": available,
            "source": "seoul_weather",
            "location_label": "서울",
            "description": "",
            "temperature_c": float(temperature_c) if temperature_c is not None else None,
            "humidity_percent": float(humidity_percent) if humidity_percent is not None else None,
            "comfort_label": None,
            "temperature_high_c": float(temperature_high_c) if temperature_high_c is not None else None,
            "temperature_low_c": float(temperature_low_c) if temperature_low_c is not None else None,
            "weather_code": int(weather_code) if weather_code is not None else None,
            "is_day": bool(is_day) if is_day is not None else None,
            "updated_at": updated_at,
        }

        _SEOUL_WEATHER_CACHE_DATA = result
        _SEOUL_WEATHER_CACHE = result
        _SEOUL_WEATHER_CACHE_TS = time.monotonic()
        return result

    except Exception:
        if _SEOUL_WEATHER_CACHE_DATA is not None:
            return {**_SEOUL_WEATHER_CACHE_DATA, "stale": True}
        raise


def _wmo_weather_code_to_desc(code: int | None) -> str | None:
    if code is None:
        return None
    if code == 0:
        return "맑음"
    elif code in {1, 2, 3}:
        return "구름 조금/흐림"
    elif code in {45, 48}:
        return "안개"
    elif code in {51, 53, 55, 56, 57}:
        return "이슬비"
    elif code in {61, 63, 65, 66, 67, 80, 81, 82}:
        return "비"
    elif code in {71, 73, 75, 77, 85, 86}:
        return "눈"
    elif code in {95, 96, 99}:
        return "뇌우"
    return "기타"
