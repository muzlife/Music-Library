from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    db_path: str
    discogs_token: str | None
    aladin_ttb_key: str | None
    deepl_auth_key: str | None
    deepseek_api_key: str | None
    aladin_base_url: str
    aladin_lookup_url: str
    maniadb_base_url: str
    deepl_base_url: str
    discogs_user_agent: str
    musicbrainz_user_agent: str
    confidence_auto_approve: float
    confidence_review: float
    metadata_sync_interval_minutes: int
    metadata_sync_batch_limit: int
    auth_admin_username: str | None
    auth_admin_password: str | None
    auth_operator_username: str | None
    auth_operator_password: str | None
    auth_operator_accounts_raw: str | None
    auth_session_secret: str
    auth_cookie_secure: bool
    purchase_import_webhook_token: str | None
    home_assistant_base_url: str
    home_assistant_token: str | None
    office_climate_temperature_entity_id: str
    office_climate_humidity_entity_id: str
    spotify_client_id: str
    spotify_client_secret: str
    spotify_redirect_uri: str
    spotify_batch_webhook_token: str | None
    server_stdout_log_path: str | None
    server_stderr_log_path: str | None
    kakao_rest_api_key: str | None
    kakao_refresh_token: str | None
    perf_slow_api_ms: int
    perf_slow_batch_ms: int
    perf_slow_query_ms: int


def _default_db_path() -> str:
    root = Path(__file__).resolve().parents[1]
    return str(root / "data" / "library.db")


def _default_env_path() -> Path:
    return Path(__file__).resolve().parents[1] / ".env.local"


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


def _env_flag(name: str, default: bool = False) -> bool:
    value = str(os.getenv(name, "")).strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on", "y"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _load_env_file(_default_env_path())
    return Settings(
        db_path=os.getenv("LIBRARY_DB_PATH", _default_db_path()),
        discogs_token=os.getenv("DISCOGS_TOKEN"),
        aladin_ttb_key=os.getenv("ALADIN_TTB_KEY"),
        deepl_auth_key=os.getenv("DEEPL_AUTH_KEY"),
        deepseek_api_key=(os.getenv("DEEPSEEK_API_KEY") or "").strip() or None,
        aladin_base_url=os.getenv(
            "ALADIN_BASE_URL",
            "https://www.aladin.co.kr/ttb/api/ItemSearch.aspx",
        ),
        aladin_lookup_url=os.getenv(
            "ALADIN_LOOKUP_URL",
            "https://www.aladin.co.kr/ttb/api/ItemLookUp.aspx",
        ),
        maniadb_base_url=os.getenv(
            "MANIADB_BASE_URL",
            "http://www.maniadb.com",
        ),
        deepl_base_url=os.getenv(
            "DEEPL_BASE_URL",
            "https://api-free.deepl.com/v2/translate",
        ),
        discogs_user_agent=os.getenv(
            "DISCOGS_USER_AGENT",
            "__PROJECT_SLUG__-library/0.1 (contact: your-email@example.com)",
        ),
        musicbrainz_user_agent=os.getenv(
            "MUSICBRAINZ_USER_AGENT",
            "__PROJECT_SLUG__-library/0.1 (contact: your-email@example.com)",
        ),
        confidence_auto_approve=float(os.getenv("MATCH_CONFIDENCE_AUTO_APPROVE", "0.90")),
        confidence_review=float(os.getenv("MATCH_CONFIDENCE_REVIEW", "0.60")),
        metadata_sync_interval_minutes=max(0, int(os.getenv("METADATA_SYNC_INTERVAL_MINUTES", "0"))),
        metadata_sync_batch_limit=max(1, int(os.getenv("METADATA_SYNC_BATCH_LIMIT", "300"))),
        auth_admin_username=(
            os.getenv("LIBRARY_ADMIN_USERNAME")
            or os.getenv("LIBRARY_AUTH_USERNAME")
            or ""
        ).strip()
        or None,
        auth_admin_password=(
            os.getenv("LIBRARY_ADMIN_PASSWORD")
            or os.getenv("LIBRARY_AUTH_PASSWORD")
            or ""
        ).strip()
        or None,
        auth_operator_username=(os.getenv("LIBRARY_OPERATOR_USERNAME") or "").strip() or None,
        auth_operator_password=(os.getenv("LIBRARY_OPERATOR_PASSWORD") or "").strip() or None,
        auth_operator_accounts_raw=(os.getenv("LIBRARY_OPERATOR_ACCOUNTS") or "").strip() or None,
        auth_session_secret=(os.getenv("LIBRARY_AUTH_SESSION_SECRET") or "change-this-library-session-secret").strip(),
        auth_cookie_secure=_env_flag("LIBRARY_AUTH_COOKIE_SECURE", default=False),
        purchase_import_webhook_token=(os.getenv("LIBRARY_PURCHASE_IMPORT_TOKEN") or "").strip() or None,
        home_assistant_base_url=(os.getenv("HOME_ASSISTANT_BASE_URL") or "https://__HA_DOMAIN__").strip(),
        home_assistant_token=(os.getenv("HOME_ASSISTANT_TOKEN") or "").strip() or None,
        office_climate_temperature_entity_id=(
            os.getenv("OFFICE_CLIMATE_TEMPERATURE_ENTITY_ID") or "__HA_TEMP_SENSOR__"
        ).strip(),
        office_climate_humidity_entity_id=(
            os.getenv("OFFICE_CLIMATE_HUMIDITY_ENTITY_ID") or "__HA_HUMIDITY_SENSOR__"
        ).strip(),
        spotify_client_id=(os.getenv("SPOTIFY_CLIENT_ID") or "").strip(),
        spotify_client_secret=(os.getenv("SPOTIFY_CLIENT_SECRET") or "").strip(),
        spotify_redirect_uri=(os.getenv("SPOTIFY_REDIRECT_URI") or "http://localhost:8100/spotify/callback").strip(),
        spotify_batch_webhook_token=(os.getenv("SPOTIFY_BATCH_WEBHOOK_TOKEN") or "").strip() or None,
        server_stdout_log_path=(os.getenv("SERVER_STDOUT_LOG_PATH") or "").strip() or None,
        server_stderr_log_path=(os.getenv("SERVER_STDERR_LOG_PATH") or "").strip() or None,
        kakao_rest_api_key=(os.getenv("KAKAO_REST_API_KEY") or "").strip() or None,
        kakao_refresh_token=(os.getenv("KAKAO_REFRESH_TOKEN") or "").strip() or None,
        perf_slow_api_ms=int(os.getenv("PERF_SLOW_API_MS") or "300"),
        perf_slow_batch_ms=int(os.getenv("PERF_SLOW_BATCH_MS") or "60000"),
        perf_slow_query_ms=int(os.getenv("PERF_SLOW_QUERY_MS") or "200"),
    )
