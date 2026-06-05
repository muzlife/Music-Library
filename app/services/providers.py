from __future__ import annotations

import html as html_lib
import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable
from urllib.parse import quote

import httpx

from ..config import get_settings
from . import artist_context as artist_context_service

logger = logging.getLogger(__name__)
PROVIDER_SLOW_SEC = float(os.getenv("PROVIDER_SLOW_SEC", "1.2"))

# --------------------------------------------------------------------------- #
# Shared HTTP client + retry helpers
# --------------------------------------------------------------------------- #
# External providers (Discogs, MusicBrainz, ManiaDB, Aladin) intermittently
# return 429 / 5xx and Discogs publishes an explicit per-minute quota. Without
# retry/backoff the metadata sync worker bunches up failures whenever the rate
# limit is touched. We centralise the transport here so every call site gets:
#   * connection-level retries (httpx HTTPTransport.retries) — covers DNS /
#     connection-reset errors that show up as transient httpx.ConnectError.
#   * a small `_request_with_retry` wrapper that respects Retry-After and
#     applies exponential backoff for 429 / 502 / 503 / 504.
#
# Long-form review note: PROVIDER_HTTP_RETRY_MAX_ATTEMPTS / _BACKOFF_BASE_SEC
# are env-tunable so QA/prod can dial it down without code changes.

PROVIDER_HTTP_TIMEOUT_SEC = float(os.getenv("PROVIDER_HTTP_TIMEOUT_SEC", "15.0"))
PROVIDER_HTTP_CONNECT_RETRIES = int(os.getenv("PROVIDER_HTTP_CONNECT_RETRIES", "2"))
PROVIDER_HTTP_RETRY_MAX_ATTEMPTS = max(0, int(os.getenv("PROVIDER_HTTP_RETRY_MAX_ATTEMPTS", "3")))
PROVIDER_HTTP_RETRY_BACKOFF_BASE_SEC = max(
    0.1, float(os.getenv("PROVIDER_HTTP_RETRY_BACKOFF_BASE_SEC", "1.0"))
)
PROVIDER_HTTP_RETRY_BACKOFF_CAP_SEC = max(
    PROVIDER_HTTP_RETRY_BACKOFF_BASE_SEC,
    float(os.getenv("PROVIDER_HTTP_RETRY_BACKOFF_CAP_SEC", "30.0")),
)
_PROVIDER_RETRY_STATUSES = frozenset({429, 502, 503, 504})


def _make_http_client(
    *,
    timeout: float | None = None,
    follow_redirects: bool = False,
    transport_retries: int | None = None,
) -> httpx.Client:
    """Construct an httpx.Client with shared defaults + connect-level retries."""
    retries = PROVIDER_HTTP_CONNECT_RETRIES if transport_retries is None else max(0, transport_retries)
    transport = httpx.HTTPTransport(retries=retries)
    return httpx.Client(
        timeout=timeout if timeout is not None else PROVIDER_HTTP_TIMEOUT_SEC,
        follow_redirects=follow_redirects,
        transport=transport,
    )


def _parse_retry_after_header(value: Any) -> float | None:
    """Best-effort parse of an HTTP Retry-After header.

    Accepts both the integer/float "seconds" form and an HTTP-date form. On
    any parse failure returns None so the caller can fall back to backoff.
    """
    text = str(value or "").strip()
    if not text:
        return None
    try:
        seconds = float(text)
        if seconds < 0:
            return None
        return seconds
    except (TypeError, ValueError):
        pass
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(text)
        if dt is None:
            return None
        from datetime import datetime, timezone
        delta = (dt - datetime.now(tz=dt.tzinfo or timezone.utc)).total_seconds()
        return max(0.0, delta)
    except Exception:
        return None


def _request_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    max_attempts: int | None = None,
    backoff_base_sec: float | None = None,
    backoff_cap_sec: float | None = None,
    **kwargs: Any,
) -> httpx.Response:
    """Perform an HTTP request with retry on 429/5xx + Retry-After honouring.

    Connection-layer transient errors (httpx.ConnectError / ReadTimeout) are
    retried with exponential backoff. The response is returned to the caller
    untouched — call ``response.raise_for_status()`` if you need it.
    """
    attempts = PROVIDER_HTTP_RETRY_MAX_ATTEMPTS if max_attempts is None else max(0, max_attempts)
    # Module-level defaults enforce a 0.1s floor to keep operators from
    # accidentally hammering providers with sub-100ms backoffs. Per-call
    # overrides intentionally bypass that floor (test fixtures want tight
    # backoffs to keep CI fast) — we only require non-negative.
    base = PROVIDER_HTTP_RETRY_BACKOFF_BASE_SEC if backoff_base_sec is None else max(0.0, backoff_base_sec)
    cap = PROVIDER_HTTP_RETRY_BACKOFF_CAP_SEC if backoff_cap_sec is None else max(base, backoff_cap_sec)

    last_exc: Exception | None = None
    last_response: httpx.Response | None = None
    method_upper = method.upper()
    # Real httpx.Client supports `.request(method, url, ...)`. Test mocks
    # often only implement the verbs they care about (e.g. `.get()`), so
    # we prefer the verb-specific helper when present and only fall back
    # to `.request()` when the client is a plain object without verbs.
    method_specific = getattr(client, method_upper.lower(), None)

    def _send_request() -> httpx.Response:
        if callable(method_specific):
            return method_specific(url, **kwargs)
        return client.request(method_upper, url, **kwargs)

    for attempt in range(attempts + 1):
        try:
            response = _send_request()
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as exc:
            last_exc = exc
            if attempt >= attempts:
                raise
            sleep_for = min(cap, base * (2 ** attempt))
            logger.warning(
                "provider %s %s connection error (%s); retry %d/%d in %.2fs",
                method_upper, url, exc.__class__.__name__, attempt + 1, attempts, sleep_for,
            )
            time.sleep(sleep_for)
            continue

        last_response = response
        # Test mocks (DummyResponse in tests/test_ops_route_access.py) only
        # implement what they need — `text` and `raise_for_status()`. Treat
        # absent `status_code` as 200 so the retry path doesn't second-guess
        # the mock and only kicks in for explicit 429/5xx responses.
        status_code = getattr(response, "status_code", 200)
        if status_code in _PROVIDER_RETRY_STATUSES and attempt < attempts:
            retry_headers = getattr(response, "headers", {}) or {}
            retry_after = _parse_retry_after_header(retry_headers.get("retry-after"))
            sleep_for = retry_after if retry_after is not None else min(cap, base * (2 ** attempt))
            logger.warning(
                "provider %s %s -> %s; retry %d/%d in %.2fs (retry-after=%s)",
                method_upper,
                url,
                status_code,
                attempt + 1,
                attempts,
                sleep_for,
                retry_headers.get("retry-after"),
            )
            try:
                response.close()
            except Exception:
                pass
            time.sleep(sleep_for)
            continue

        return response

    # Unreachable in normal flow: loop either returns or re-raises.
    if last_response is not None:
        return last_response
    if last_exc is not None:
        raise last_exc
    raise httpx.HTTPError(f"provider {method_upper} {url} failed without a response")


def _get_with_retry(client: httpx.Client, url: str, **kwargs: Any) -> httpx.Response:
    return _request_with_retry(client, "GET", url, **kwargs)


def _post_with_retry(client: httpx.Client, url: str, **kwargs: Any) -> httpx.Response:
    return _request_with_retry(client, "POST", url, **kwargs)


_DEFAULT_PROVIDER_USER_AGENT_PLACEHOLDER = "your-email@example.com"


def has_default_user_agent_placeholder() -> bool:
    """True when the configured Discogs/MusicBrainz UA still contains the
    placeholder contact address shipped in the example .env. Discogs and
    MusicBrainz both require a meaningful UA, so we surface this loudly at
    startup instead of silently sending a placeholder."""
    settings = get_settings()
    candidates = (settings.discogs_user_agent or "", settings.musicbrainz_user_agent or "")
    return any(_DEFAULT_PROVIDER_USER_AGENT_PLACEHOLDER in str(value) for value in candidates)


# --------------------------------------------------------------------------- #
# Persisted external response cache (TTL-only, see app.db.external_response_cache)
# --------------------------------------------------------------------------- #
import hashlib  # noqa: E402  — keep cache plumbing co-located with the helper
import json as _cache_json  # noqa: E402  — alias avoids shadowing other modules
from datetime import datetime, timezone  # noqa: E402

EXTERNAL_RESPONSE_CACHE_TTL_SECONDS = max(
    60, int(os.getenv("EXTERNAL_RESPONSE_CACHE_TTL_SECONDS", str(7 * 24 * 3600)))
)
EXTERNAL_RESPONSE_CACHE_DISABLED = os.getenv("EXTERNAL_RESPONSE_CACHE_DISABLED", "").strip().lower() in {
    "1", "true", "yes", "on", "y"
}


def build_external_cache_key(source_code: str, kind: str, identifier: str) -> str:
    """Produce a stable, opaque cache key for a (source, kind, id) tuple.

    We hash the joined tuple to keep the column compact and avoid relying on
    callers to URL-escape arbitrary identifiers. SHA-256 is overkill for
    non-cryptographic use but avoids any risk of collision in an
    operator-managed dataset.
    """
    raw = "|".join(
        str(v or "").strip().upper() if i == 0 else str(v or "").strip()
        for i, v in enumerate((source_code, kind, identifier))
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{str(source_code or 'UNKNOWN').strip().upper()}:{str(kind or 'misc').strip()}:{digest[:32]}"


def _cache_entry_is_fresh(row: dict[str, Any]) -> bool:
    expires_at_text = str(row.get("expires_at") or "").strip()
    if not expires_at_text:
        return False
    try:
        expires_at = datetime.fromisoformat(expires_at_text)
    except ValueError:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at > datetime.now(timezone.utc)


def cached_fetch_json(
    *,
    source_code: str,
    kind: str,
    identifier: str,
    fetcher: "Callable[[], httpx.Response | None]",
    ttl_seconds: int | None = None,
    allow_stale_on_error: bool = True,
) -> dict[str, Any] | None:
    """Fetch JSON from a provider with TTL-based disk caching.

    `fetcher` is a closure that performs the actual HTTP request and returns
    the httpx.Response (or None on caller-detected failure). On a fresh
    cache hit we never invoke `fetcher`; on a miss we call it, store the
    body, and return the parsed JSON. On a fetch error with a stale row
    available, we return the stale row so the metadata sync worker can keep
    making progress when a provider 5xx's.

    Returns None on hard failure (no cache + fetch failed).
    """
    # Imported here to avoid a circular import at module load time
    # (`app.db` imports nothing from services, but `app.main` wires both).
    from .. import db as _db_module

    if EXTERNAL_RESPONSE_CACHE_DISABLED:
        try:
            response = fetcher()
        except httpx.HTTPError:
            return None
        if response is None or response.status_code >= 400:
            return None
        try:
            return response.json()
        except ValueError:
            return None

    cache_key = build_external_cache_key(source_code, kind, identifier)
    ttl = EXTERNAL_RESPONSE_CACHE_TTL_SECONDS if ttl_seconds is None else max(60, int(ttl_seconds))

    cached_row = _db_module.get_cached_external_response(cache_key)
    if cached_row is not None and _cache_entry_is_fresh(cached_row):
        try:
            return _cache_json.loads(cached_row["body_json"])
        except (TypeError, ValueError):
            # Fall through to a refetch if the stored body became unreadable.
            pass

    try:
        response = fetcher()
    except httpx.HTTPError:
        response = None

    if response is not None and response.status_code < 400:
        try:
            body = response.json()
        except ValueError:
            body = None
        if body is not None:
            try:
                _db_module.upsert_cached_external_response(
                    cache_key=cache_key,
                    source_code=source_code,
                    body_json=_cache_json.dumps(body, ensure_ascii=False),
                    status_code=int(response.status_code),
                    ttl_seconds=ttl,
                    etag=response.headers.get("etag"),
                    last_modified=response.headers.get("last-modified"),
                )
            except Exception:
                logger.exception("failed to persist external response cache for %s", cache_key)
            return body

    if allow_stale_on_error and cached_row is not None:
        try:
            return _cache_json.loads(cached_row["body_json"])
        except (TypeError, ValueError):
            return None
    return None


@dataclass
class Candidate:
    source: str
    external_id: str
    title: str
    artist_or_brand: str | None
    release_year: int | None
    country: str | None
    format_name: str | None
    barcode: str | None
    catalog_no: str | None
    label_name: str | None
    cover_image_url: str | None
    track_list: list[str]
    confidence: float
    raw: dict[str, Any]
    media_type: str | None = None
    release_type: str | None = None
    domain_code: str | None = None
    genres: list[str] = field(default_factory=list)
    styles: list[str] = field(default_factory=list)
    released_date: str | None = None
    disc_count: int | None = None
    speed_rpm: int | None = None
    has_obi: bool | None = None
    runout_matrix: list[str] = field(default_factory=list)
    pressing_country: str | None = None
    source_notes: str | None = None
    credits: list[str] = field(default_factory=list)
    identifier_items: list[dict[str, Any]] = field(default_factory=list)
    image_items: list[dict[str, Any]] = field(default_factory=list)
    company_items: list[dict[str, Any]] = field(default_factory=list)
    series: list[str] = field(default_factory=list)
    format_items: list[dict[str, Any]] = field(default_factory=list)
    track_items: list[dict[str, Any]] = field(default_factory=list)
    label_items: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["confidence"] = round(self.confidence, 3)
        return data


def _normalize_text(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s.strip().lower())


def _normalize_compact_text(s: str | None) -> str:
    return re.sub(r"[\s\-\._/]+", "", _normalize_text(s))


def _validate_barcode_checksum(barcode_digits: str) -> bool:
    """EAN-13 또는 UPC-A 체크섬 검증. 형식이 유효하면 True."""
    if not barcode_digits.isdigit():
        return False
    if len(barcode_digits) == 13:  # EAN-13 (한국 880 포함)
        total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(barcode_digits[:12]))
        return (10 - total % 10) % 10 == int(barcode_digits[12])
    if len(barcode_digits) == 12:  # UPC-A
        total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(barcode_digits[:11]))
        return (10 - total % 10) % 10 == int(barcode_digits[11])
    return False


def _token_similarity(a: str, b: str) -> float:
    ta = set(_normalize_text(a).split())
    tb = set(_normalize_text(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _lookup_match_level(query_value: Any, candidate_value: Any) -> int:
    query_text = _normalize_text(str(query_value or ""))
    candidate_text = _normalize_text(str(candidate_value or ""))
    if not query_text or not candidate_text:
        return 0
    if candidate_text == query_text:
        return 3
    if query_text in candidate_text:
        return 2
    query_tokens = set(query_text.split())
    candidate_tokens = set(candidate_text.split())
    if query_tokens and query_tokens.issubset(candidate_tokens):
        return 1
    return 0


def _lookup_compact_match_level(query_value: Any, candidate_value: Any) -> int:
    query_text = _normalize_compact_text(str(query_value or ""))
    candidate_text = _normalize_compact_text(str(candidate_value or ""))
    if not query_text or not candidate_text:
        return 0
    if candidate_text == query_text:
        return 3
    if query_text in candidate_text:
        return 2
    return 0


def _safe_year(v: Any) -> int | None:
    if v is None:
        return None
    try:
        year = int(v)
    except (TypeError, ValueError):
        return None
    if 1900 <= year <= 2100:
        return year
    return None


def _pick_first_text(v: Any) -> str | None:
    if isinstance(v, list):
        for item in v:
            if item is None:
                continue
            s = str(item).strip()
            if s:
                return s
        return None
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _normalize_catalog_no(v: Any) -> str | None:
    text = _pick_first_text(v)
    if not text:
        return None
    text = re.sub(r"^(?:cat\s*#?\s*:?)\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^[\s;:,/|]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text or text in {"-", "--", "---"}:
        return None
    return text


LEGACY_DOMAIN_CODE_MAP = {
    "KOREAN": "KOREA",
    "JPOP": "JAPAN",
    "OTHER": "WORLD_OTHER",
}
DOMAIN_CODES = {"KOREA", "JAPAN", "GREATER_CHINA", "WESTERN", "OTHER_ASIA", "WORLD_OTHER", "UNKNOWN"}
GREATER_CHINA_COUNTRIES = {
    # 중국 본토
    "CN", "CHN", "CHINA", "MAINLAND CHINA", "PEOPLES REPUBLIC OF CHINA",
    # 대만
    "TW", "TWN", "TAIWAN", "REPUBLIC OF CHINA",
    # 홍콩
    "HK", "HKG", "HONG KONG",
    # 마카오
    "MO", "MAC", "MACAU", "MACAO",
}
OTHER_ASIA_COUNTRIES = {
    # 동남아
    "TH", "THA", "THAILAND",
    "VN", "VNM", "VIETNAM", "VIET NAM",
    "PH", "PHL", "PHILIPPINES",
    "ID", "IDN", "INDONESIA",
    "MY", "MYS", "MALAYSIA",
    "SG", "SGP", "SINGAPORE",
    "MM", "MMR", "MYANMAR", "BURMA",
    "KH", "KHM", "CAMBODIA",
    "LA", "LAO", "LAOS",
    "BN", "BRN", "BRUNEI",
    "TL", "TLS", "TIMOR LESTE", "EAST TIMOR",
    # 남아시아
    "IN", "IND", "INDIA",
    "PK", "PAK", "PAKISTAN",
    "BD", "BGD", "BANGLADESH",
    "LK", "LKA", "SRI LANKA", "CEYLON",
    "NP", "NPL", "NEPAL",
    "BT", "BTN", "BHUTAN",
    "MV", "MDV", "MALDIVES",
    # 중앙아시아
    "MN", "MNG", "MONGOLIA",
    "KZ", "KAZ", "KAZAKHSTAN",
    "UZ", "UZB", "UZBEKISTAN",
    "TM", "TKM", "TURKMENISTAN",
    "KG", "KGZ", "KYRGYZSTAN",
    "TJ", "TJK", "TAJIKISTAN",
}
WESTERN_COUNTRIES = {
    # 북미
    "US", "USA", "UNITED STATES", "UNITED STATES OF AMERICA",
    "CA", "CAN", "CANADA",
    "MX", "MEX", "MEXICO",
    # 영국·아일랜드
    "GB", "UK", "GBR", "UNITED KINGDOM", "ENGLAND", "SCOTLAND", "WALES",
    "IE", "IRL", "IRELAND",
    # 오세아니아
    "AU", "AUS", "AUSTRALIA",
    "NZ", "NZL", "NEW ZEALAND",
    # 서유럽
    "FR", "FRA", "FRANCE",
    "DE", "DEU", "GERMANY", "WEST GERMANY",
    "IT", "ITA", "ITALY",
    "ES", "ESP", "SPAIN",
    "PT", "PRT", "PORTUGAL",
    "NL", "NLD", "NETHERLANDS", "HOLLAND",
    "BE", "BEL", "BELGIUM",
    "CH", "CHE", "SWITZERLAND",
    "AT", "AUT", "AUSTRIA",
    "LU", "LUX", "LUXEMBOURG",
    # 북유럽
    "SE", "SWE", "SWEDEN",
    "NO", "NOR", "NORWAY",
    "DK", "DNK", "DENMARK",
    "FI", "FIN", "FINLAND",
    "IS", "ISL", "ICELAND",
    # 남유럽·지중해
    "GR", "GRC", "GREECE",
    "TR", "TUR", "TURKEY", "TURKIYE",
    "CY", "CYP", "CYPRUS",
    "MT", "MLT", "MALTA",
    "HR", "HRV", "CROATIA",
    "SI", "SVN", "SLOVENIA",
    "RS", "SRB", "SERBIA",
    "ME", "MNE", "MONTENEGRO",
    "BA", "BIH", "BOSNIA AND HERZEGOVINA", "BOSNIA",
    "MK", "MKD", "NORTH MACEDONIA", "MACEDONIA",
    "AL", "ALB", "ALBANIA",
    # 동유럽·발트
    "PL", "POL", "POLAND",
    "CZ", "CZE", "CZECH REPUBLIC", "CZECHIA", "CZECHOSLOVAKIA",
    "SK", "SVK", "SLOVAKIA",
    "HU", "HUN", "HUNGARY",
    "RO", "ROU", "ROMANIA",
    "BG", "BGR", "BULGARIA",
    "EE", "EST", "ESTONIA",
    "LV", "LVA", "LATVIA",
    "LT", "LTU", "LITHUANIA",
    "UA", "UKR", "UKRAINE",
    "BY", "BLR", "BELARUS",
    "MD", "MDA", "MOLDOVA",
    "RU", "RUS", "RUSSIA", "USSR", "SOVIET UNION",
    # 중동·이스라엘 (서양 음악 시장 주요국)
    "IL", "ISR", "ISRAEL",
    # 남아프리카·라틴 (Discogs에서 서양권 팝이 이 국가로 발매되는 경우가 많음)
    "ZA", "ZAF", "SOUTH AFRICA",
    "BR", "BRA", "BRAZIL",
    "AR", "ARG", "ARGENTINA",
    "CL", "CHL", "CHILE",
    "CO", "COL", "COLOMBIA",
    "VE", "VEN", "VENEZUELA",
    "PE", "PER", "PERU",
    "UY", "URY", "URUGUAY",
    # Discogs 특수값 — 유럽 공통반·전세계 공통반
    "EUROPE",
    "WORLDWIDE", "WORLD",
}


def _normalize_domain_code(value: Any) -> str | None:
    code = str(value or "").strip().upper()
    if not code:
        return None
    code = LEGACY_DOMAIN_CODE_MAP.get(code, code)
    return code if code in DOMAIN_CODES else None


def _contains_hangul(text: str) -> bool:
    return bool(re.search(r"[\uac00-\ud7a3]", text))


def _contains_kana(text: str) -> bool:
    return bool(re.search(r"[\u3040-\u30ff]", text))


def _normalize_country_token(value: Any) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return ""
    text = re.sub(r"[^A-Z ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _country_domain_code(value: Any) -> str | None:
    country = _normalize_country_token(value)
    if not country:
        return None
    if country in {"KR", "KOR", "KOREA", "SOUTH KOREA", "KOREA REPUBLIC OF"}:
        return "KOREA"
    if country in {"JP", "JPN", "JAPAN"}:
        return "JAPAN"
    if country in GREATER_CHINA_COUNTRIES:
        return "GREATER_CHINA"
    if country in OTHER_ASIA_COUNTRIES:
        return "OTHER_ASIA"
    if country in WESTERN_COUNTRIES:
        return "WESTERN"
    return "WORLD_OTHER"


def infer_domain_code(
    *,
    genres: list[str] | None = None,
    styles: list[str] | None = None,
    country: Any = None,
    artist_or_brand: Any = None,
    title: Any = None,
    label_name: Any = None,
    source: str | None = None,
) -> str | None:
    genre_text = " ".join(str(v or "").strip() for v in (genres or []) if str(v or "").strip())
    style_text = " ".join(str(v or "").strip() for v in (styles or []) if str(v or "").strip())
    artist_text = str(artist_or_brand or "").strip()
    title_text = str(title or "").strip()
    label_text = str(label_name or "").strip()
    # label_text 포함 전체 텍스트 (장르·스타일 키워드 검색에만 사용)
    combined = " ".join(v for v in [genre_text, style_text, artist_text, title_text, label_text] if v).strip()
    combined_lower = combined.lower()

    # NOTE: substring 검사(token in combined_lower)는 "k rock"이 "rock rock"에서
    #       false positive로 걸리는 버그가 있어 regex word boundary로 교체했다.
    _re_korea = re.compile(r"\b(k-pop|k\s+pop|k-rock|k\s+rock|k-indie|k\s+indie|trot)\b", re.I)
    _re_japan = re.compile(r"\b(j-pop|j\s+pop|j-rock|j\s+rock|kayokyoku|kayōkyoku|enka|shibuya-kei|shibuya\s+kei)\b", re.I)
    _re_china = re.compile(r"\b(c-pop|c\s+pop|mandopop|cantopop)\b", re.I)
    if _re_korea.search(combined):
        return "KOREA"
    if _re_japan.search(combined):
        return "JAPAN"
    if _re_china.search(combined):
        return "GREATER_CHINA"

    # 한글·가나 문자 판별은 콘텐츠 필드(장르·스타일·아티스트·타이틀)만 사용.
    # label_name은 배급사(유통사) 이름이므로 제외한다.
    content_combined = " ".join(v for v in [genre_text, style_text, artist_text, title_text] if v).strip()
    if _contains_hangul(content_combined):
        return "KOREA"
    if _contains_kana(content_combined):
        return "JAPAN"

    # country 신호는 제거: pressing/master country 모두 아티스트 국적을 보장하지 않음.
    # (근래 LP는 체코·독일 등 제3국 프레싱이 기본. label_domain_registry 조회로 대체)

    source_code = str(source or "").strip().upper()
    if source_code == "MANIADB":
        return "KOREA"
    return None


def _unique_text_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _safe_positive_int(v: Any) -> int | None:
    try:
        value = int(v)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return value


def _discogs_release_date_text(raw: dict[str, Any]) -> str | None:
    released = _pick_first_text(raw.get("released")) or _pick_first_text(raw.get("released_formatted"))
    if not released:
        return None
    return released.strip() or None


def _discogs_master_id_from_release(raw: dict[str, Any]) -> str | None:
    master_id = _pick_first_text(raw.get("master_id"))
    if master_id:
        return master_id
    master_url = _pick_first_text(raw.get("master_url"))
    if not master_url:
        return None
    m = re.search(r"/masters/(\d+)", master_url)
    if not m:
        return None
    return str(m.group(1))


def _fetch_discogs_master_detail(
    master_id: str,
    headers: dict[str, str],
    client: httpx.Client,
) -> dict[str, Any] | None:
    master_id_s = str(master_id or "").strip()
    if not master_id_s:
        return None

    def _fetch() -> httpx.Response:
        return _get_with_retry(
            client, f"https://api.discogs.com/masters/{master_id_s}", headers=headers
        )

    data = cached_fetch_json(
        source_code="DISCOGS",
        kind="master",
        identifier=master_id_s,
        fetcher=_fetch,
    )
    if not isinstance(data, dict):
        return None

    year = _safe_year(data.get("year"))
    artists = data.get("artists")
    artist_or_brand = None
    if isinstance(artists, list) and artists:
        first = artists[0]
        if isinstance(first, dict):
            artist_or_brand = _pick_first_text(first.get("anv")) or _pick_first_text(first.get("name"))

    # 마스터의 main_release(원반)를 조회해 원산지 국가를 구한다.
    # 개별 릴리즈의 country는 '제조국(pressing country)'이므로 한국반이면
    # "South Korea"가 되어 팝 앨범이 가요로 오분류된다.
    # 마스터 → main_release의 country는 원래 출신국이므로 도메인 추론에 적합하다.
    master_country: str | None = None
    main_release_id = str(data.get("main_release") or "").strip()
    if main_release_id:
        def _fetch_main() -> httpx.Response:
            return _get_with_retry(
                client, f"https://api.discogs.com/releases/{main_release_id}", headers=headers
            )
        main_data = cached_fetch_json(
            source_code="DISCOGS",
            kind="release",
            identifier=main_release_id,
            fetcher=_fetch_main,
        )
        if isinstance(main_data, dict):
            master_country = _pick_first_text(main_data.get("country")) or None

    return {
        "master_external_id": master_id_s,
        "master_title": _pick_first_text(data.get("title")),
        "master_artist_or_brand": artist_or_brand,
        "master_release_year": year,
        # Discogs master payload exposes original release year, not full YYYY-MM-DD in most cases.
        "master_released_date": str(year) if year is not None else None,
        "master_genres": _unique_text_list(data.get("genres")),
        "master_styles": _unique_text_list(data.get("styles")),
        "master_country": master_country,  # main_release 원산지 국가
        "raw_master": data,
    }


def _fetch_discogs_artist_detail(
    *,
    headers: dict[str, str],
    client: httpx.Client,
    artist_id: str | None = None,
    resource_url: str | None = None,
) -> dict[str, Any] | None:
    target_url = str(resource_url or "").strip()
    target_artist_id = str(artist_id or "").strip()
    if not target_url and not target_artist_id:
        return None

    # Cache key prefers the numeric artist id when available so the same
    # artist looked up by either resource_url or id maps to one entry.
    cache_id = target_artist_id or target_url

    def _fetch() -> httpx.Response:
        if target_url:
            return _get_with_retry(client, target_url, headers=headers)
        return _get_with_retry(
            client, f"https://api.discogs.com/artists/{target_artist_id}", headers=headers
        )

    data = cached_fetch_json(
        source_code="DISCOGS",
        kind="artist",
        identifier=cache_id,
        fetcher=_fetch,
    )
    return data if isinstance(data, dict) else None


def _discogs_artist_detail_name_candidates(detail: dict[str, Any] | None) -> list[str]:
    if not detail:
        return []
    names: list[str] = []
    seen: set[str] = set()

    def remember(value: Any) -> None:
        text = str(value or "").strip()
        if not text:
            return
        key = _normalize_text(text)
        if not key or key in seen:
            return
        seen.add(key)
        names.append(text)

    remember(detail.get("name"))
    remember(detail.get("realname"))
    for variation in detail.get("namevariations") or []:
        remember(variation)
    return names


def _discogs_identifier_items(identifiers: Any) -> list[dict[str, Any]]:
    if not isinstance(identifiers, list):
        return []
    out: list[dict[str, Any]] = []
    for row in identifiers:
        if not isinstance(row, dict):
            continue
        type_text = _pick_first_text(row.get("type"))
        value_text = _pick_first_text(row.get("value"))
        desc_text = _pick_first_text(row.get("description"))
        if not (type_text or value_text or desc_text):
            continue
        out.append(
            {
                "type": type_text,
                "value": value_text,
                "description": desc_text,
            }
        )
    return out


def _discogs_runout_from_identifiers(identifiers: Any) -> list[str]:
    if not isinstance(identifiers, list):
        return []
    values: list[str] = []
    seen: set[str] = set()
    for row in identifiers:
        if not isinstance(row, dict):
            continue
        type_text = str(row.get("type") or "").strip().lower()
        if "matrix" not in type_text and "runout" not in type_text:
            continue
        value = _pick_first_text(row.get("value"))
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        values.append(value)
    return values


def _discogs_credit_values(extraartists: Any) -> list[str]:
    if not isinstance(extraartists, list):
        return []
    out: list[str] = []
    for row in extraartists:
        if not isinstance(row, dict):
            continue
        name = _pick_first_text(row.get("anv")) or _pick_first_text(row.get("name"))
        role = _pick_first_text(row.get("role"))
        tracks = _pick_first_text(row.get("tracks"))
        core = f"{name} ({role})" if name and role else (name or role or "")
        if not core:
            continue
        out.append(f"{core} [{tracks}]" if tracks else core)
    return out


def _discogs_image_items(images: Any) -> list[dict[str, Any]]:
    if not isinstance(images, list):
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in images:
        if not isinstance(row, dict):
            continue
        uri = _pick_first_text(row.get("uri")) or _pick_first_text(row.get("uri150"))
        if not uri or uri in seen:
            continue
        seen.add(uri)
        out.append(
            {
                "type": _pick_first_text(row.get("type")) or "unknown",
                "uri": uri,
                "uri150": _pick_first_text(row.get("uri150")),
                "resource_url": _pick_first_text(row.get("resource_url")),
                "width": row.get("width"),
                "height": row.get("height"),
            }
        )
    return out


def _discogs_company_items(companies: Any) -> list[dict[str, Any]]:
    if not isinstance(companies, list):
        return []
    out: list[dict[str, Any]] = []
    for row in companies:
        if not isinstance(row, dict):
            continue
        entity_type = _pick_first_text(row.get("entity_type_name"))
        name = _pick_first_text(row.get("name"))
        catno = _normalize_catalog_no(row.get("catno"))
        if not (entity_type or name or catno):
            continue
        out.append({"entity_type": entity_type, "name": name, "catno": catno})
    return out


def _discogs_series_values(series_rows: Any) -> list[str]:
    if not isinstance(series_rows, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for row in series_rows:
        if not isinstance(row, dict):
            continue
        name = _pick_first_text(row.get("name"))
        catno = _normalize_catalog_no(row.get("catno"))
        if name and catno:
            text = f"{name} / {catno}"
        else:
            text = name or catno or ""
        text = text.strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _discogs_format_items(formats: Any) -> list[dict[str, Any]]:
    if not isinstance(formats, list):
        return []
    out: list[dict[str, Any]] = []
    for row in formats:
        if not isinstance(row, dict):
            continue
        name = _pick_first_text(row.get("name"))
        descriptions = _unique_text_list(row.get("descriptions"))
        qty = _pick_first_text(row.get("qty"))
        text = _pick_first_text(row.get("text"))
        if not (name or descriptions or qty or text):
            continue
        out.append(
            {
                "name": name,
                "descriptions": descriptions,
                "qty": qty,
                "text": text,
            }
        )
    return out


def _discogs_track_items(track_rows: Any) -> list[dict[str, Any]]:
    if not isinstance(track_rows, list):
        return []
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(track_rows):
        if not isinstance(row, dict):
            continue
        position = _pick_first_text(row.get("position")) or str(idx + 1)
        title = _pick_first_text(row.get("title"))
        duration = _pick_first_text(row.get("duration"))
        track_type = _pick_first_text(row.get("type_")) or "track"
        sub_track_titles: list[str] = []
        sub_tracks = row.get("sub_tracks")
        if isinstance(sub_tracks, list):
            for sub in sub_tracks:
                if not isinstance(sub, dict):
                    continue
                sub_title = _pick_first_text(sub.get("title"))
                if sub_title:
                    sub_track_titles.append(sub_title)
        if not title and sub_track_titles:
            title = " / ".join(sub_track_titles)
        if not title:
            continue
        credits = _discogs_credit_values(row.get("extraartists"))
        out.append(
            {
                "position": position,
                "title": title,
                "duration": duration,
                "type": track_type,
                "sub_tracks": sub_track_titles,
                "credits": credits,
            }
        )
    return out


def _discogs_label_items(labels: Any) -> list[dict[str, Any]]:
    if not isinstance(labels, list):
        return []
    out: list[dict[str, Any]] = []
    for row in labels:
        if not isinstance(row, dict):
            continue
        name = _pick_first_text(row.get("name"))
        catno = _normalize_catalog_no(row.get("catno"))
        if not (name or catno):
            continue
        out.append({"name": name, "catno": catno})
    return out


def _discogs_disc_count(formats: Any) -> int | None:
    if not isinstance(formats, list):
        return None
    total = 0
    found = False
    for row in formats:
        if not isinstance(row, dict):
            continue
        qty = _safe_positive_int(row.get("qty"))
        if qty is None:
            continue
        total += qty
        found = True
    if found and total > 0:
        return total
    return None


def _discogs_speed_rpm(formats: Any) -> int | None:
    texts: list[str] = []
    if isinstance(formats, list):
        for row in formats:
            if not isinstance(row, dict):
                continue
            name = _pick_first_text(row.get("name"))
            if name:
                texts.append(name)
            descriptions = row.get("descriptions")
            if isinstance(descriptions, list):
                texts.extend(str(v).strip() for v in descriptions if str(v).strip())
            text = _pick_first_text(row.get("text"))
            if text:
                texts.append(text)
    if not texts:
        return None
    blob = " ".join(texts)
    m = re.search(r"(\d{2,3})\s*RPM", blob, flags=re.IGNORECASE)
    if not m:
        return None
    return _safe_positive_int(m.group(1))


def _discogs_has_obi(formats: Any) -> bool | None:
    texts: list[str] = []
    if isinstance(formats, list):
        for row in formats:
            if not isinstance(row, dict):
                continue
            name = _pick_first_text(row.get("name"))
            if name:
                texts.append(name)
            descriptions = row.get("descriptions")
            if isinstance(descriptions, list):
                texts.extend(str(v).strip() for v in descriptions if str(v).strip())
            text = _pick_first_text(row.get("text"))
            if text:
                texts.append(text)
    if not texts:
        return None
    joined = " ".join(texts).lower()
    if "obi" in joined:
        return True
    return None


def _discogs_format_descriptions_flat(formats: Any) -> list[str]:
    """format_items의 모든 name + descriptions 를 소문자 정규화해서 반환."""
    texts: list[str] = []
    if isinstance(formats, list):
        for row in formats:
            if not isinstance(row, dict):
                continue
            name = _pick_first_text(row.get("name"))
            if name:
                texts.append(name.strip().lower())
            for d in (row.get("descriptions") or []):
                s = str(d).strip().lower()
                if s:
                    texts.append(s)
            t = _pick_first_text(row.get("text"))
            if t:
                texts.append(t.strip().lower())
    return texts


def _discogs_is_limited_edition(formats: Any) -> bool | None:
    """Limited Edition / Deluxe Edition / Special Edition / Club Edition → is_limited_edition."""
    KEYWORDS = {"limited edition", "limited"}
    texts = _discogs_format_descriptions_flat(formats)
    return True if any(t in KEYWORDS for t in texts) else None


def _discogs_is_promo(formats: Any) -> bool | None:
    """Promo description → is_promotional_not_for_sale."""
    texts = _discogs_format_descriptions_flat(formats)
    return True if "promo" in texts else None


def _discogs_disc_type(formats: Any) -> str | None:
    """
    Picture Disc → 'Picture'
    Etched      → 'Etched'
    Colored Vinyl / Colour Vinyl → 'Colored'
    Clear Vinyl  → 'Clear'
    Shaped Disc  → 'Shaped'
    """
    DISC_TYPE_MAP = {
        "picture disc": "Picture",
        "etched": "Etched",
        "colored vinyl": "Colored",
        "colour vinyl": "Colored",
        "coloured vinyl": "Colored",
        "clear vinyl": "Clear",
        "clear": "Clear",
        "shaped disc": "Shaped",
        "shaped": "Shaped",
    }
    texts = _discogs_format_descriptions_flat(formats)
    for t in texts:
        if t in DISC_TYPE_MAP:
            return DISC_TYPE_MAP[t]
    return None


def _discogs_is_numbered(formats: Any) -> bool | None:
    """Numbered description → edition_number 플래그 (번호 자체는 수동 입력)."""
    texts = _discogs_format_descriptions_flat(formats)
    return True if "numbered" in texts else None


def _discogs_release_type_from_text(format_text: str | None) -> str | None:
    text = str(format_text or "").strip().lower()
    if not text:
        return None
    if any(token in text for token in ["single", "maxi-single", "maxi single"]):
        return "SINGLE"
    if any(token in text for token in ["ep", "mini-album", "mini album"]):
        return "EP"
    if any(token in text for token in ["album", "lp", "full-length", "full length"]):
        return "ALBUM"
    return None


def _discogs_domain_code(genres: list[str], styles: list[str], country: Any, artist_or_brand: Any = None, title: Any = None, label_name: Any = None) -> str | None:
    return infer_domain_code(
        genres=genres,
        styles=styles,
        country=country,
        artist_or_brand=artist_or_brand,
        title=title,
        label_name=label_name,
        source="DISCOGS",
    )


def _discogs_format_meta(formats: Any, fallback_format_text: str | None = None) -> dict[str, str | None]:
    names: list[str] = []
    descs: list[str] = []
    media_type: str | None = None

    if isinstance(formats, list):
        for row in formats:
            if isinstance(row, dict):
                name = _pick_first_text(row.get("name"))
                if name:
                    names.append(name)
                    if media_type is None and name not in ("Box Set", "All Media"):
                        media_type = name
                for desc in _unique_text_list(row.get("descriptions")):
                    descs.append(desc)
                text = _pick_first_text(row.get("text"))
                if text:
                    descs.append(text)
            else:
                text = _pick_first_text(row)
                if text:
                    names.append(text)
                    if media_type is None and text not in ("Box Set", "All Media"):
                        media_type = text

    combined = " ".join([*names, *descs, str(fallback_format_text or "")]).strip()
    normalized_format = _infer_format_from_text(combined)
    release_type = _discogs_release_type_from_text(combined)
    return {
        "format_name": normalized_format,
        "media_type": media_type,
        "release_type": release_type,
    }


def _pick_artist_from_discogs_title(title: str) -> tuple[str | None, str]:
    # Discogs title often has format: "Artist - Release"
    # Artist may have disambiguation number like "Artist (2)"
    import re as _re
    if " - " not in title:
        return None, title
    left, right = title.split(" - ", 1)
    artist = left.strip()
    # Strip Discogs disambiguation number: "Asia (2)" → "Asia"
    artist = _re.sub(r'\s*\(\d+\)$', '', artist).strip()
    return artist or None, right.strip() or title


def _parse_discogs_candidates(data: dict[str, Any], barcode: str | None, query: str | None) -> list[Candidate]:
    rows = data.get("results") or []
    out: list[Candidate] = []

    for row in rows:
        full_title = row.get("title") or ""
        artist, release_title = _pick_artist_from_discogs_title(full_title)
        row_barcode = row.get("barcode")
        if isinstance(row_barcode, list):
            row_barcode = row_barcode[0] if row_barcode else None

        label_name = _pick_first_text(row.get("label"))
        cover_image_url = _pick_first_text(row.get("cover_image")) or _pick_first_text(row.get("thumb"))
        format_meta = _discogs_format_meta(row.get("format"), fallback_format_text=_pick_first_text(row.get("format")))
        genres = _unique_text_list(row.get("genre") or row.get("genres"))
        styles = _unique_text_list(row.get("style") or row.get("styles"))
        domain_code = _discogs_domain_code(
            genres=genres,
            styles=styles,
            country=row.get("country"),
            artist_or_brand=artist,
            title=release_title or full_title,
            label_name=label_name,
        )

        if barcode:
            confidence = 0.96 if _normalize_text(str(row_barcode)) == _normalize_text(barcode) else 0.88
        else:
            sim = _token_similarity(query or "", full_title)
            confidence = 0.55 + (0.40 * sim)

        out.append(
            Candidate(
                source="DISCOGS",
                external_id=str(row.get("id") or ""),
                title=release_title or full_title,
                artist_or_brand=artist,
                release_year=_safe_year(row.get("year")),
                country=row.get("country"),
                format_name=format_meta.get("format_name")
                or ((row.get("format") or [None])[0] if isinstance(row.get("format"), list) else row.get("format")),
                barcode=str(row_barcode) if row_barcode else None,
                catalog_no=_normalize_catalog_no(row.get("catno")) or _normalize_catalog_no((row.get("labels") or [{}])[0].get("catno") if row.get("labels") else None),
                label_name=label_name,
                cover_image_url=cover_image_url,
                track_list=[],
                confidence=min(max(confidence, 0.0), 1.0),
                raw=row,
                media_type=format_meta.get("media_type"),
                release_type=format_meta.get("release_type"),
                domain_code=domain_code,
                genres=genres,
                styles=styles,
            )
        )

    return out


def _parse_musicbrainz_candidates(data: dict[str, Any], barcode: str | None, query: str | None) -> list[Candidate]:
    rows = data.get("releases") or []
    out: list[Candidate] = []

    for row in rows:
        title = row.get("title") or ""
        artists = row.get("artist-credit") or []
        artist_name = None
        if artists and isinstance(artists, list):
            first = artists[0] or {}
            artist_obj = first.get("artist") if isinstance(first, dict) else None
            if isinstance(artist_obj, dict):
                artist_name = artist_obj.get("name")

        score_raw = row.get("score")
        try:
            score = float(score_raw)
        except (TypeError, ValueError):
            score = 50.0

        confidence = min(max(score / 100.0, 0.30), 0.90)

        row_barcode = row.get("barcode")
        if barcode and row_barcode and _normalize_text(str(row_barcode)) == _normalize_text(barcode):
            confidence = min(confidence + 0.08, 0.98)
        elif not barcode and query:
            sim = _token_similarity(query, f"{artist_name or ''} {title}".strip())
            confidence = min(confidence + (sim * 0.08), 0.95)

        out.append(
            Candidate(
                source="MUSICBRAINZ",
                external_id=str(row.get("id") or ""),
                title=title,
                artist_or_brand=artist_name,
                release_year=_safe_year((row.get("date") or "").split("-")[0] if row.get("date") else None),
                country=row.get("country"),
                format_name=None,
                barcode=str(row_barcode) if row_barcode else None,
                catalog_no=None,
                label_name=None,
                cover_image_url=None,
                track_list=[],
                confidence=min(max(confidence, 0.0), 1.0),
                raw=row,
                media_type=None,
                release_type=None,
                domain_code=infer_domain_code(
                    country=row.get("country"),
                    artist_or_brand=artist_name,
                    title=title,
                    source="MUSICBRAINZ",
                ),
                genres=[],
                styles=[],
            )
        )

    return out


def _infer_format_from_aladin_category(category_name: str | None) -> str | None:
    if not category_name:
        return None
    upper = category_name.upper()
    if "REEL" in upper:
        return "REEL_TO_REEL"
    if "8TRACK" in upper or "8-TRACK" in upper or "8 TRACK" in upper:
        return "8TRACK"
    if "DIGITAL" in upper or "MP3" in upper or "DOWNLOAD" in upper:
        return "DIGITAL"
    if "LP" in upper:
        return "LP"
    if "CD" in upper:
        return "CD"
    if "CASSETTE" in upper or "카세트" in category_name:
        return "CASSETTE"
    return None


def _format_name_to_media_type(format_name: str | None) -> str | None:
    if not format_name:
        return None
    upper = str(format_name).strip().upper()
    if upper in ("LP", "VINYL"):
        return "Vinyl"
    if upper == "CD":
        return "CD"
    if upper == "CASSETTE":
        return "Cassette"
    if upper == "DIGITAL":
        return "Digital"
    if upper == "8TRACK":
        return "8-Track Cartridge"
    if upper == "REEL_TO_REEL":
        return "Reel-to-Reel"
    return format_name


def _infer_format_from_text(format_text: str | None) -> str | None:
    if not format_text:
        return None
    upper = format_text.upper()
    if "REEL" in upper:
        return "REEL_TO_REEL"
    if "8TRACK" in upper or "8-TRACK" in upper or "8 TRACK" in upper:
        return "8TRACK"
    if "DIGITAL" in upper or "FILE" in upper or "DOWNLOAD" in upper:
        return "DIGITAL"
    if "LP" in upper or "VINYL" in upper:
        return "LP"
    if "CD" in upper:
        return "CD"
    if "CASSETTE" in upper or "TAPE" in upper:
        result = "CASSETTE"
    else:
        result = None
    
    # Append Box Set if present in descriptions
    if "BOX SET" in upper or "BOXSET" in upper:
        result = (result + ", Box Set") if result else "Box Set"
    
    return result


# --- Wikipedia album review ---

def _clean_review_text(text: str) -> str:
    """Remove Wikipedia boilerplate and tidy whitespace."""
    import re as _re
    # [ 1 ], [1], [ citation needed ], [edit], etc.
    text = _re.sub(r"\[\s*\d+\s*\]", "", text)
    text = _re.sub(r"\[\s*[a-zA-Z ]{1,30}\s*\]", "", text)
    # Footnote lines starting with ^ (certification notes, references)
    text = _re.sub(r"(?m)^\^[^\n]*$", "", text)
    # Stub notices (ko/en Wikipedia)
    text = _re.sub(
        r"[^\n]*(?:스텁입니다|stub article|위키백과를 도와주실|you can help|이 문서는 토막글)[^\n]*",
        "", text, flags=_re.I,
    )
    # Collapse multiple blank lines → single blank line
    text = _re.sub(r"\n{3,}", "\n\n", text)
    # collapse multiple spaces / clean up spacing before punctuation
    text = _re.sub(r" {2,}", " ", text)
    text = _re.sub(r" ([.,;:!?])", r"\1", text)
    return text.strip()


def fetch_wikipedia_album_review(
    artist: str,
    title: str,
    year: int | None = None,
    lang: str = "ko",
) -> dict[str, str | None] | None:
    """Fetch album page extract from Wikipedia API.

    lang="ko" uses Korean Wikipedia (가요/J-Pop etc.).
    lang="en" uses English Wikipedia (Western/Other domains).
    Retries once on 429 with a 10-second backoff.
    """
    import urllib.request, urllib.parse, json as _json, time as _time
    _base = f"https://{lang}.wikipedia.org"
    year_part = f" {year}" if year else ""
    album_keyword = "음반" if lang == "ko" else "album"
    query = f"{title} {artist}{year_part} {album_keyword}"
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
            f"{_base}/w/api.php?{params}",
            headers={"User-Agent": "__PROJECT_SLUG__-library/0.1 (album-review-bot)"},
        )
        for attempt in range(2):
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = _json.loads(resp.read())
                break
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt == 0:
                    _time.sleep(10)
                    continue
                raise
        pages = data.get("query", {}).get("search") or []
        if not pages:
            return None
        title_lower = title.lower()
        page_title = None
        import re as _re
        matched_pages = [
            page["title"] for page in pages
            if _re.search(r'\b' + _re.escape(title_lower) + r'\b', page["title"].lower())
        ]
        if matched_pages:
            # Prefer pages explicitly qualified as albums over plain artist pages
            album_qualified = [t for t in matched_pages if _re.search(r'\(.*album.*\)', t.lower())]
            page_title = album_qualified[0] if album_qualified else matched_pages[0]
        is_fallback = not page_title
        if not page_title:
            # Fallback: try fetching the page directly by album title only when
            # search returned no album-titled result (e.g. only artist pages).
            page_title = title
        params2 = urllib.parse.urlencode({
            "action": "query",
            "format": "json",
            "prop": "extracts",
            "exintro": "1",
            "explaintext": "1",
            "titles": page_title,
            "redirects": "1",
        })
        req2 = urllib.request.Request(
            f"{_base}/w/api.php?{params2}",
            headers={"User-Agent": "__PROJECT_SLUG__-library/0.1"},
        )
        with urllib.request.urlopen(req2, timeout=10) as resp2:
            data2 = _json.loads(resp2.read())
        pages_data = data2.get("query", {}).get("pages") or {}
        page_data = next(iter(pages_data.values()), {})
        if "missing" in page_data:
            return None
        extract = page_data.get("extract", "")
        if not extract:
            return None
        # For fallback fetches, verify the page is music-related: the extract
        # must mention the artist name OR contain an album/music keyword near
        # the start. This prevents picking up novels, films, etc. with the
        # same title as the album.
        if is_fallback:
            extract_head = extract[:400].lower()
            artist_lower = artist.lower()
            if lang == "ko":
                music_keywords = ("음반", "앨범", "싱글", "ep", "스튜디오",
                                  "album", "가수", "밴드", "singer", "band")
            else:
                music_keywords = ("album", "ep", "single", "studio album",
                                  "record", "hip-hop", "rap", "jazz",
                                  "musician", "singer", "band", "rapper")
            artist_match = artist_lower and artist_lower in extract_head
            music_match = any(kw in extract_head for kw in music_keywords)
            if not artist_match and not music_match:
                return None
        return {
            "review_text": _clean_review_text(extract),
            "review_source": "WIKIPEDIA",
            "review_url": f"{_base}/wiki/{urllib.parse.quote(page_title.replace(' ', '_'), safe='()')}",
        }
    except Exception as exc:
        import logging as _logging
        _logging.getLogger(__name__).warning("fetch_wikipedia_album_review failed: %s", exc)
    return None


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
            headers={"User-Agent": "__PROJECT_SLUG__-library/0.1"},
            follow_redirects=True,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
        container = soup.find("article") or soup.find("main") or soup.find("body")
        if not container:
            return None
        paragraphs = container.find_all("p")
        text = "\n".join(p.get_text(" ", strip=True) for p in paragraphs if p.get_text(strip=True))
        text = _clean_review_text(text)
        return text if text else None
    except Exception as exc:
        import logging as _logging
        _logging.getLogger(__name__).warning("fetch_review_from_url(%s) failed: %s", url, exc)
        return None


# ---------------------------------------------------------------------------
# Aladin title/artist cleaning helpers
#
# Aladin 상품명은 "Led Zeppelin II [LP]", "Abbey Road (2CD) 리마스터링 수입반" 처럼
# 미디어 포맷·디스크 수·에디션·유통 구분이 상품명에 혼재한다.
# 마스터 명(title)에는 순수 앨범 이름만 남기고 포맷 정보는 format_name 필드로 분리한다.
#
# author 필드는 "비틀즈 (아티스트)", "김광석 (가수)" 형태로 역할 표기가 붙는다.
# ---------------------------------------------------------------------------

# 대괄호 안 포맷 토큰 추출 – e.g. "[2LP]", "[CD+DVD]", "[카세트]"
_ALADIN_FORMAT_BRACKET_RE = re.compile(
    r"\["
    r"(\d*\s*(?:LP|VINYL|CD|SACD|DVD|BLU-?RAY|카세트|CASSETTE|TAPE)"
    r"(?:[^\]]*)?)"
    r"\]",
    re.IGNORECASE,
)

# 소괄호 안 포맷 토큰 추출 – e.g. "(2CD)", "(LP)", "(CD)", "(CD+도서)"
_ALADIN_FORMAT_PAREN_RE = re.compile(
    r"\("
    r"(\d*\s*(?:LP|VINYL|CD|SACD|DVD|BLU-?RAY|카세트|CASSETTE|TAPE)"
    r"(?:[^)]*)?)"
    r"\)",
    re.IGNORECASE,
)

# 대괄호 블록 전체 제거 (포맷 추출 후 적용)
_ALADIN_BRACKET_STRIP_RE = re.compile(r"\[[^\]]*\]")

# 소괄호 안 노이즈 패턴 제거 – 포맷/패키징/에디션/유통 구분
_ALADIN_PAREN_NOISE_RE = re.compile(
    r"\("
    r"(?:"
    # 디스크수 + 포맷 (e.g. 2CD, 3LP, CD+DVD)
    r"\d*\s*(?:LP|VINYL|CD|SACD|DVD|BLU-?RAY|카세트|CASSETTE|TAPE)[^)]*"
    # 유통 구분
    r"|수입반?|내수반?|일본반?|국내반?|정품"
    # 한정·에디션 (한국어)
    r"|한정반?|초도\s*한정|한정판|특별판|스탠다드\s*에디션|디럭스\s*에디션|스페셜\s*에디션"
    # 에디션 (영문)
    r"|(?:Deluxe|Standard|Limited|Special|Collector['’s]*|Expanded|Super\s*Deluxe)\s*(?:Box\s*)?Edition"
    # 주년 기념
    r"|\d+(?:th|st|nd|rd)\s*Anniversary(?:\s*Edition)?"
    r"|Anniversary\s*Edition"
    # 리마스터
    r"|(?:\d{4}\s*)?Remaster(?:ed|ing)?"
    r"|리마스터(?:링)?"
    # 세트 구성
    r"|전\s*\d+매|\d+매\s*세트|\d+\s*Disc\s*Set"
    # 재발매
    r"|재발매|재발|재반"
    r")"
    r"\)",
    re.IGNORECASE,
)

# 제목 끝에 붙는 독립 노이즈 단어 (공백 구분)
_ALADIN_TITLE_TRAILING_NOISE_RE = re.compile(
    r"\s+(?:수입반?|내수반?|일본반?|국내반?|한정반?|초도한정|리마스터링?|Remastered?|재발매|재반)$",
    re.IGNORECASE,
)

# 수상·홍보 정보 추출 – title 말미의 " - YYYY 한국대중음악상 xxx 수상" 등
# 해당 구간을 title에서 제거하고 source_notes로 이동한다.
_ALADIN_PROMO_NOTICE_RE = re.compile(
    r"\s*[-–—]\s*"
    r"("
    r"(?:\d{4}\s*)?"
    r"(?:한국대중음악상|대중음악상|가요대상|음악대상|음반대상|방송음악상|음악총연합|한국음반산업협회)"
    r"[^[\]（）【】\n]*"
    r"|(?:올해의\s*(?:음반|앨범|아티스트)|이달의\s*(?:음반|앨범))[^[\]（）【】\n]*"
    r"|(?:수상|선정|추천)\s*(?:음반|앨범)[^[\]（）【】\n]*"
    r")",
    re.IGNORECASE,
)

# 알라딘 title에 아티스트명이 접두어로 붙는 구분자 패턴: "아티스트 - 앨범", "아티스트 / 앨범"
_ALADIN_ARTIST_PREFIX_SEP_RE = re.compile(r"^(.+?)\s*[-–—/]\s*(.+)$")

# author 필드 역할 표기 제거 – e.g. "(아티스트)", "(가수)", "(작곡가)"
_ALADIN_AUTHOR_ROLE_RE = re.compile(
    r"\s*\((?:아티스트|가수|뮤지션|밴드|그룹|작곡가?|작사가?|편곡가?|연주|보컬|래퍼|프로듀서)\)",
    re.IGNORECASE,
)

# 복수 아티스트 구분자 정규화 – 알라딘은 쉼표로 여럿 연결하기도 함
_ALADIN_AUTHOR_MULTI_RE = re.compile(r"\s*,\s*(?=[가-힣A-Za-z])")


def _extract_format_from_aladin_title(title: str) -> str | None:
    """대괄호/소괄호 안 포맷 토큰에서 format_name 추출."""
    m = _ALADIN_FORMAT_BRACKET_RE.search(title) or _ALADIN_FORMAT_PAREN_RE.search(title)
    return _infer_format_from_text(m.group(1)) if m else None


def _clean_aladin_title(title: str) -> str:
    """알라딘 상품명에서 미디어 포맷·에디션·유통 노이즈를 제거하고 순수 앨범명만 반환."""
    t = _ALADIN_BRACKET_STRIP_RE.sub("", title)         # [...] 전체 제거
    t = _ALADIN_PAREN_NOISE_RE.sub("", t)               # (...) 노이즈 제거
    t = _ALADIN_TITLE_TRAILING_NOISE_RE.sub("", t)      # 말미 단독 노이즈어 제거
    t = re.sub(r"\s{2,}", " ", t).strip().rstrip("-–—·").strip()
    return t if t else title                             # 모두 지워지면 원본 유지


def _extract_aladin_promo_notice(title: str) -> tuple[str, str | None]:
    """수상·홍보 정보를 title에서 분리한다.

    Returns:
        (cleaned_title, notice_or_None)
        notice는 source_notes에 기록하고, title에는 순수 앨범명만 남긴다.
    """
    notices: list[str] = []

    def _collect(m: re.Match) -> str:
        notices.append(m.group(1).strip())
        return ""

    cleaned = _ALADIN_PROMO_NOTICE_RE.sub(_collect, title)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip().rstrip("-–—·").strip()
    cleaned = cleaned if cleaned else title
    notice = " | ".join(notices) if notices else None
    return cleaned, notice


def _clean_aladin_artist(author: str) -> str:
    """알라딘 author 필드에서 역할 표기를 제거하고 아티스트명만 반환."""
    a = _ALADIN_AUTHOR_ROLE_RE.sub("", author)
    # 복수 아티스트: 첫 번째만 사용 (대표 아티스트)
    a = _ALADIN_AUTHOR_MULTI_RE.split(a)[0]
    return a.strip() or author


def _parse_aladin_candidates(data: dict[str, Any], query: str | None) -> list[Candidate]:
    rows = data.get("item") or []
    out: list[Candidate] = []

    for row in rows:
        raw_title = str(row.get("title") or "")
        raw_artist = str(row.get("author") or "") or None
        barcode = row.get("isbn13") or row.get("isbn")
        category_name = row.get("categoryName")

        # --- 정제 ---
        title = _clean_aladin_title(raw_title)
        artist = _clean_aladin_artist(raw_artist) if raw_artist else None

        # --- 수상·홍보 정보 분리 (source_notes로 이동) ---
        title, promo_notice = _extract_aladin_promo_notice(title)

        # --- 아티스트 접두어 제거 ---
        # 알라딘은 상품명을 "아티스트명 - 앨범명" 형태로 제공하는 경우가 많다.
        # artist가 이미 별도 필드에 있으므로, title 앞의 아티스트 중복을 제거한다.
        # e.g. artist="제이통", title="제이통 - 흙" → title="흙"
        if artist and title:
            # 정규화된 아티스트명과 비교 (대소문자·공백 무시)
            artist_norm = re.sub(r"\s+", "", artist.lower())
            for sep in (" - ", " – ", " — ", " / "):
                candidate_prefix = artist + sep
                if title.lower().startswith(candidate_prefix.lower()):
                    stripped = title[len(candidate_prefix):].strip()
                    if stripped:  # 뒤에 내용이 있을 때만 적용
                        title = stripped
                    break
                # 공백 없는 정규화 비교 (아티스트명의 변형 대응)
                title_norm = re.sub(r"\s+", "", title.lower())
                if title_norm.startswith(artist_norm + re.sub(r"\s+", "", sep.lower())):
                    # sep 위치를 원본 title에서 찾아 분리
                    m = re.match(
                        r"^" + re.escape(artist) + r"\s*" + re.escape(sep.strip()) + r"\s*",
                        title,
                        re.IGNORECASE,
                    )
                    if m:
                        stripped = title[m.end():].strip()
                        if stripped:
                            title = stripped
                        break

        # --- 포맷: 상품명 토큰 우선, 카테고리 보완 ---
        format_name = (
            _extract_format_from_aladin_title(raw_title)
            or _infer_format_from_aladin_category(category_name)
        )

        sim = _token_similarity(query or "", f"{artist or ''} {title}".strip())
        confidence = 0.60 + (0.33 * sim)
        if barcode and query and _normalize_text(str(barcode)) == _normalize_text(query):
            confidence = max(confidence, 0.95)

        pub_date = str(row.get("pubDate") or "")
        year_token = pub_date.split("-")[0] if pub_date else None
        released_date = pub_date if pub_date else None

        raw_cover = str(row.get("cover") or "") or None
        cover_image_url = raw_cover.replace("/coversum/", "/cover/") if raw_cover else None

        out.append(
            Candidate(
                source="ALADIN",
                external_id=str(row.get("itemId") or row.get("isbn13") or row.get("isbn") or ""),
                title=title,
                artist_or_brand=artist,
                release_year=_safe_year(year_token),
                country="KR",
                format_name=format_name,
                barcode=str(barcode) if barcode else None,
                catalog_no=None,
                label_name=str(row.get("publisher") or "") or None,
                cover_image_url=cover_image_url,
                track_list=[],
                confidence=min(max(confidence, 0.0), 1.0),
                raw=row,
                media_type=None,
                release_type=None,
                source_notes=promo_notice,
                domain_code=infer_domain_code(
                    country="KR",
                    artist_or_brand=artist,
                    title=title,
                    label_name=row.get("publisher"),
                    source="ALADIN",
                ),
                genres=[],
                styles=[],
                released_date=released_date,
            )
        )

    return out


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s)


def _clean_html_text(s: str | None) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(_strip_html(s or ""))).strip()


def _parse_maniadb_release_text(text: str) -> tuple[str | None, str, int | None, str | None]:
    clean = _clean_html_text(text)
    label_name: str | None = None
    year: int | None = None

    tail = re.search(r"\((\d{4})(?:\s*,\s*([^)]+))?\)\s*$", clean)
    if tail:
        year = _safe_year(tail.group(1))
        label_name = tail.group(2).strip() if tail.group(2) else None
        clean = clean[: tail.start()].strip()

    artist = None
    title = clean
    if " - " in clean:
        left, right = clean.split(" - ", 1)
        artist = re.sub(r"\s+\d+\s*집$", "", left.strip()) or None
        title = right.strip() or clean

    return artist, title, year, label_name


def _parse_maniadb_album_candidates(
    html_text: str,
    query: str,
    limit: int,
    base_url: str,
) -> list[Candidate]:
    out: list[Candidate] = []
    seen: set[str] = set()
    pattern = re.compile(
        r'<div class="artist">\s*<a href="/album/(\d+)"[^>]*?(?:alt="([^"]*)")?[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )

    for match in pattern.finditer(html_text):
        album_id = str(match.group(1) or "").strip()
        if not album_id or album_id in seen:
            continue
        seen.add(album_id)

        raw_title = (match.group(2) or "").strip() or (match.group(3) or "").strip()
        artist, title, year, label_name = _parse_maniadb_release_text(raw_title)
        if not title:
            continue

        sim = _token_similarity(query, f"{artist or ''} {title}".strip())
        confidence = min(max(0.62 + (0.30 * sim), 0.0), 0.95)

        out.append(
            Candidate(
                source="MANIADB",
                external_id=f"album:{album_id}",
                title=title,
                artist_or_brand=artist,
                release_year=year,
                country="KR",
                format_name=None,
                barcode=None,
                catalog_no=None,
                label_name=label_name,
                cover_image_url=None,
                track_list=[],
                confidence=confidence,
                raw={
                    "kind": "album",
                    "album_id": album_id,
                    "label_hint": label_name,
                    "source_url": f"{base_url}/album/{album_id}",
                    "title_raw": _clean_html_text(raw_title),
                },
                media_type=None,
                release_type=None,
                domain_code="KOREA",
                genres=[],
                styles=[],
            )
        )
        if len(out) >= limit:
            break

    return out


def _parse_maniadb_artist_candidates(
    html_text: str,
    query: str,
    limit: int,
    base_url: str,
) -> list[Candidate]:
    out: list[Candidate] = []
    seen: set[str] = set()
    pattern = re.compile(
        r'<div class="artist">\s*<a href="/artist/(\d+)"[^>]*?(?:alt="([^"]*)")?[^>]*>(.*?)</a>(.*?)</div>',
        re.IGNORECASE | re.DOTALL,
    )

    for match in pattern.finditer(html_text):
        artist_id = str(match.group(1) or "").strip()
        if not artist_id or artist_id in seen:
            continue
        seen.add(artist_id)

        artist_text = _clean_html_text((match.group(2) or "").strip() or (match.group(3) or "").strip())
        artist_name = re.split(r"\s*\[", artist_text, maxsplit=1)[0].strip() or artist_text
        if not artist_name:
            continue
        trailing_text = _clean_html_text(match.group(4) or "")
        search_terms: list[str] = []
        seen_terms: set[str] = set()
        for value in [artist_name, *re.split(r"\s*/\s*", trailing_text)]:
            term = _clean_html_text(value)
            normalized_term = _normalize_text(term)
            if (
                not term
                or not normalized_term
                or normalized_term in seen_terms
                or re.fullmatch(r"\d{4}s", term, re.IGNORECASE)
                or term.endswith("그룹")
            ):
                continue
            seen_terms.add(normalized_term)
            search_terms.append(term)

        sim = _token_similarity(query, artist_name)
        confidence = min(max(0.48 + (0.22 * sim), 0.0), 0.82)

        out.append(
            Candidate(
                source="MANIADB",
                external_id=f"artist:{artist_id}",
                title=artist_name,
                artist_or_brand=artist_name,
                release_year=None,
                country="KR",
                format_name=None,
                barcode=None,
                catalog_no=None,
                label_name=None,
                cover_image_url=None,
                track_list=[],
                confidence=confidence,
                raw={
                    "kind": "artist",
                    "artist_id": artist_id,
                    "source_url": f"{base_url}/artist/{artist_id}",
                    "name_raw": artist_text,
                    "search_terms": search_terms,
                },
                media_type=None,
                release_type=None,
                domain_code=None,
                genres=[],
                styles=[],
            )
        )
        if len(out) >= limit:
            break

    return out


def _maniadb_search(query: str, limit: int = 5) -> list[Candidate]:
    settings = get_settings()
    base_url = settings.maniadb_base_url.rstrip("/")
    encoded_query = quote(query.strip(), safe="")
    if not encoded_query:
        return []

    with _make_http_client(follow_redirects=True) as client:
        album_started_at = time.perf_counter()
        album_res = _get_with_retry(client, f"{base_url}/search/{encoded_query}/", params={"sr": "L"})
        album_elapsed = time.perf_counter() - album_started_at
        if album_elapsed >= PROVIDER_SLOW_SEC:
            logger.warning(
                "provider_slow source=MANIADB op=search_album elapsed=%.3fs query=%s",
                album_elapsed,
                query,
            )
        album_res.raise_for_status()
        albums = _parse_maniadb_album_candidates(album_res.text, query=query, limit=limit, base_url=base_url)
        if len(albums) >= limit:
            return albums[:limit]

        artist_started_at = time.perf_counter()
        artist_res = _get_with_retry(client, f"{base_url}/search/{encoded_query}/", params={"sr": "P"})
        artist_elapsed = time.perf_counter() - artist_started_at
        if artist_elapsed >= PROVIDER_SLOW_SEC:
            logger.warning(
                "provider_slow source=MANIADB op=search_artist elapsed=%.3fs query=%s",
                artist_elapsed,
                query,
            )
        artist_res.raise_for_status()
        artists = _parse_maniadb_artist_candidates(
            artist_res.text,
            query=query,
            limit=max(1, limit - len(albums)),
            base_url=base_url,
        )

        album_ids = {
            str((candidate.raw or {}).get("album_id") or candidate.external_id.replace("album:", "", 1)).strip()
            for candidate in albums
            if str((candidate.raw or {}).get("kind") or "").strip().lower() == "album"
        }
        seen_queries: set[str] = {_normalize_text(query)}
        alias_search_terms: list[tuple[str, list[str]]] = []
        for artist_candidate in artists:
            raw = artist_candidate.raw if isinstance(artist_candidate.raw, dict) else {}
            terms = [str(term or "").strip() for term in (raw.get("search_terms") or [])]
            cleaned_terms = [term for term in terms if term]
            for term in cleaned_terms:
                normalized_term = _normalize_text(term)
                if not normalized_term or normalized_term in seen_queries:
                    continue
                seen_queries.add(normalized_term)
                alias_search_terms.append((term, cleaned_terms))

        for alias_query, artist_search_terms in alias_search_terms:
            alias_encoded_query = quote(alias_query.strip(), safe="")
            if not alias_encoded_query:
                continue
            alias_album_started_at = time.perf_counter()
            alias_album_res = _get_with_retry(client, f"{base_url}/search/{alias_encoded_query}/", params={"sr": "L"})
            alias_album_elapsed = time.perf_counter() - alias_album_started_at
            if alias_album_elapsed >= PROVIDER_SLOW_SEC:
                logger.warning(
                    "provider_slow source=MANIADB op=search_album_alias elapsed=%.3fs query=%s alias=%s",
                    alias_album_elapsed,
                    query,
                    alias_query,
                )
            alias_album_res.raise_for_status()
            alias_albums = _parse_maniadb_album_candidates(
                alias_album_res.text,
                query=query,
                limit=limit,
                base_url=base_url,
            )
            for alias_album in alias_albums:
                album_id = str((alias_album.raw or {}).get("album_id") or alias_album.external_id.replace("album:", "", 1)).strip()
                if not album_id or album_id in album_ids:
                    continue
                album_ids.add(album_id)
                alias_album.raw["artist_search_terms"] = artist_search_terms
                albums.append(alias_album)
                if len(albums) >= limit:
                    break
            if len(albums) >= limit:
                break

        return (albums + artists)[:limit]


def _discogs_search(params: dict[str, Any]) -> list[Candidate]:
    headers = _discogs_headers()
    if headers is None:
        return []

    with _make_http_client() as client:
        started_at = time.perf_counter()
        response = _get_with_retry(client, "https://api.discogs.com/database/search", params=params, headers=headers)
        elapsed = time.perf_counter() - started_at
        if elapsed >= PROVIDER_SLOW_SEC:
            logger.warning(
                "provider_slow source=DISCOGS op=search elapsed=%.3fs query=%s",
                elapsed,
                params.get("q") or params.get("barcode") or "",
            )
        response.raise_for_status()
        data = response.json()

    return _parse_discogs_candidates(
        data,
        barcode=str(params.get("barcode")) if params.get("barcode") else None,
        query=str(params.get("q")) if params.get("q") else None,
    )


def _discogs_headers(require_token: bool = False) -> dict[str, str] | None:
    settings = get_settings()
    token = str(settings.discogs_token or "").strip()
    if require_token and not token:
        return None
    headers = {
        "User-Agent": settings.discogs_user_agent,
    }
    if token:
        headers["Authorization"] = f"Discogs token={token}"
    return headers


def discogs_identity() -> dict[str, Any] | None:
    headers = _discogs_headers(require_token=True)
    if headers is None:
        return None

    try:
        with _make_http_client() as client:
            response = _get_with_retry(client, "https://api.discogs.com/oauth/identity", headers=headers)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError:
        return None

    username = str(data.get("username") or "").strip()
    if not username:
        return None
    return {"username": username, "resource_url": data.get("resource_url")}


def discogs_add_release_to_collection(release_id: str, folder_id: int = 1) -> dict[str, Any] | None:
    ident = discogs_identity()
    headers = _discogs_headers(require_token=True)
    release_id_s = str(release_id).strip()
    if ident is None or headers is None or not release_id_s:
        return None

    username = ident["username"]
    url = f"https://api.discogs.com/users/{username}/collection/folders/{folder_id}/releases/{release_id_s}"

    try:
        with _make_http_client() as client:
            response = _post_with_retry(client, url, headers=headers)
            response.raise_for_status()
            payload: dict[str, Any] = {}
            if response.text.strip():
                try:
                    payload = response.json()
                except ValueError:
                    payload = {}
    except httpx.HTTPError:
        return None

    return {
        "username": username,
        "release_id": release_id_s,
        "folder_id": folder_id,
        "payload": payload,
    }


def _parse_discogs_track_list(track_rows: Any) -> list[str]:
    if not isinstance(track_rows, list):
        return []
    out: list[str] = []
    for row in track_rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        position = str(row.get("position") or "").strip()
        out.append(f"{position} {title}".strip())
    return out


def _fetch_discogs_release_detail(
    release_id: str,
    headers: dict[str, str],
    client: httpx.Client,
    master_cache: dict[str, dict[str, Any] | None] | None = None,
) -> dict[str, Any] | None:
    if not release_id:
        return None

    try:
        response = _get_with_retry(client, f"https://api.discogs.com/releases/{release_id}", headers=headers)
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError:
        return None

    labels = data.get("labels")
    label_name = None
    if isinstance(labels, list) and labels:
        first = labels[0]
        if isinstance(first, dict):
            label_name = _pick_first_text(first.get("name"))
    label_items = _discogs_label_items(labels)

    images = data.get("images")
    cover_image_url = None
    if isinstance(images, list):
        for image in images:
            if isinstance(image, dict):
                cover_image_url = _pick_first_text(image.get("uri"))
                if cover_image_url:
                    break
    image_items = _discogs_image_items(images)

    barcode = None
    identifiers = data.get("identifiers")
    if isinstance(identifiers, list):
        for ident in identifiers:
            if not isinstance(ident, dict):
                continue
            if str(ident.get("type") or "").lower() != "barcode":
                continue
            barcode_raw = _pick_first_text(ident.get("value"))
            if barcode_raw:
                barcode = re.sub(r"[^0-9Xx]", "", barcode_raw) or barcode_raw
                break
    if not barcode:
        barcode = _pick_first_text(data.get("barcode"))

    tracks = _parse_discogs_track_list(data.get("tracklist"))
    track_items = _discogs_track_items(data.get("tracklist"))
    release_genres = _unique_text_list(data.get("genres"))
    release_styles = _unique_text_list(data.get("styles"))
    formats = data.get("formats")
    format_meta = _discogs_format_meta(formats)
    format_items = _discogs_format_items(formats)
    release_released_date = _discogs_release_date_text(data)
    runout_matrix = _discogs_runout_from_identifiers(identifiers)
    identifier_items = _discogs_identifier_items(identifiers)
    disc_count = _discogs_disc_count(formats)
    speed_rpm = _discogs_speed_rpm(formats)
    has_obi = _discogs_has_obi(formats)
    pressing_country = _pick_first_text(data.get("country"))
    source_notes = _pick_first_text(data.get("notes"))
    credits = _discogs_credit_values(data.get("extraartists"))
    company_items = _discogs_company_items(data.get("companies"))
    series = _discogs_series_values(data.get("series"))

    master_id = _discogs_master_id_from_release(data)
    master_detail: dict[str, Any] | None = None
    if master_id:
        if master_cache is not None and master_id in master_cache:
            master_detail = master_cache[master_id]
        else:
            master_detail = _fetch_discogs_master_detail(master_id=master_id, headers=headers, client=client)
            if master_cache is not None:
                master_cache[master_id] = master_detail

    master_released_date = _pick_first_text(master_detail.get("master_released_date")) if master_detail else None
    master_genres = _unique_text_list(master_detail.get("master_genres")) if master_detail else []
    master_styles = _unique_text_list(master_detail.get("master_styles")) if master_detail else []

    genres = release_genres or master_genres
    styles = release_styles or master_styles
    # 도메인 추론에 사용할 국가: 마스터(원반) 국가 우선, 없으면 이 릴리즈의 제조국.
    # 한국반(pressing country="South Korea")을 마스터 원산지(예: US/UK)로 교정해
    # 팝 앨범이 가요로 오분류되는 것을 방지한다.
    master_country = master_detail.get("master_country") if master_detail else None
    infer_country = master_country or data.get("country")
    domain_code = _discogs_domain_code(
        genres=genres,
        styles=styles,
        country=infer_country,
        artist_or_brand=_pick_first_text((data.get("artists") or [{}])[0].get("name")) if isinstance(data.get("artists"), list) and data.get("artists") else None,
        title=data.get("title"),
        label_name=label_name,
    )
    released_date = release_released_date

    return {
        "label_name": label_name,
        "label_items": label_items,
        "catalog_no": _normalize_catalog_no(data.get("catno")) or _normalize_catalog_no((data.get("labels") or [{}])[0].get("catno") if data.get("labels") else None),
        "cover_image_url": cover_image_url,
        "track_list": tracks,
        "track_items": track_items,
        "barcode": barcode,
        "format_name": format_meta.get("format_name"),
        "media_type": format_meta.get("media_type"),
        "release_type": format_meta.get("release_type"),
        "domain_code": domain_code,
        "genres": genres,
        "styles": styles,
        "master_external_id": master_id,
        "master_release_year": master_detail.get("master_release_year") if master_detail else None,
        "master_released_date": master_released_date,
        "master_genres": master_genres,
        "master_styles": master_styles,
        "master_country": master_country,
        "source_notes": source_notes,
        "credits": credits,
        "identifier_items": identifier_items,
        "image_items": image_items,
        "company_items": company_items,
        "series": series,
        "format_items": format_items,
        "released_date": released_date,
        "disc_count": disc_count,
        "speed_rpm": speed_rpm,
        "has_obi": has_obi,
        "is_limited_edition": _discogs_is_limited_edition(formats),
        "is_promotional_not_for_sale": True if _discogs_is_promo(formats) else None,
        "disc_type": _discogs_disc_type(formats),
        "runout_matrix": runout_matrix,
        "pressing_country": pressing_country,
        "raw_detail": data,
    }


def _enrich_discogs_candidates(candidates: list[Candidate], max_items: int = 5) -> None:
    headers = _discogs_headers()
    if headers is None:
        return

    slice_size = max(0, min(len(candidates), max_items))
    if slice_size == 0:
        return

    master_cache: dict[str, dict[str, Any] | None] = {}
    with _make_http_client() as client:
        for candidate in candidates[:slice_size]:
            detail = _fetch_discogs_release_detail(
                candidate.external_id,
                headers=headers,
                client=client,
                master_cache=master_cache,
            )
            if not detail:
                continue
            candidate.label_name = detail.get("label_name") or candidate.label_name
            candidate.catalog_no = detail.get("catalog_no") or candidate.catalog_no
            candidate.cover_image_url = detail.get("cover_image_url") or candidate.cover_image_url
            candidate.track_list = detail.get("track_list") or candidate.track_list
            candidate.barcode = detail.get("barcode") or candidate.barcode
            candidate.format_name = detail.get("format_name") or candidate.format_name
            candidate.media_type = detail.get("media_type") or candidate.media_type
            candidate.release_type = detail.get("release_type") or candidate.release_type
            candidate.domain_code = detail.get("domain_code") or candidate.domain_code
            candidate.genres = detail.get("genres") or candidate.genres
            candidate.styles = detail.get("styles") or candidate.styles
            candidate.released_date = detail.get("released_date") or candidate.released_date
            candidate.disc_count = detail.get("disc_count") if detail.get("disc_count") is not None else candidate.disc_count
            candidate.speed_rpm = detail.get("speed_rpm") if detail.get("speed_rpm") is not None else candidate.speed_rpm
            if detail.get("has_obi") is not None:
                candidate.has_obi = bool(detail.get("has_obi"))
            candidate.runout_matrix = detail.get("runout_matrix") or candidate.runout_matrix
            candidate.pressing_country = detail.get("pressing_country") or candidate.pressing_country
            candidate.source_notes = detail.get("source_notes") or candidate.source_notes
            candidate.credits = detail.get("credits") or candidate.credits
            candidate.identifier_items = detail.get("identifier_items") or candidate.identifier_items
            candidate.image_items = detail.get("image_items") or candidate.image_items
            candidate.company_items = detail.get("company_items") or candidate.company_items
            candidate.series = detail.get("series") or candidate.series
            candidate.format_items = detail.get("format_items") or candidate.format_items
            candidate.track_items = detail.get("track_items") or candidate.track_items
            candidate.label_items = detail.get("label_items") or candidate.label_items
            candidate.raw["detail"] = detail.get("raw_detail")


def _extract_maniadb_album_id(external_id: str) -> str | None:
    text = str(external_id or "").strip()
    if not text:
        return None
    if text.startswith("album:"):
        text = text.split(":", 1)[1]
    if ":" in text:
        text = text.split(":", 1)[0]
    text = text.strip()
    return text if text.isdigit() else None


def _enrich_maniadb_candidates(candidates: list[Candidate], max_items: int = 5) -> None:
    slice_size = max(0, min(len(candidates), max_items))
    if slice_size == 0:
        return

    for candidate in candidates[:slice_size]:
        album_id = _extract_maniadb_album_id(candidate.external_id)
        if not album_id:
            continue
        variants = get_maniadb_master_variants(master_external_id=album_id, limit=1)
        if not variants:
            continue
        detail = variants[0]
        candidate.format_name = detail.get("format_name") or candidate.format_name
        candidate.label_name = detail.get("label_name") or candidate.label_name
        candidate.catalog_no = detail.get("catalog_no") or candidate.catalog_no
        candidate.cover_image_url = detail.get("cover_image_url") or candidate.cover_image_url
        candidate.image_items = detail.get("image_items") or candidate.image_items
        candidate.track_list = detail.get("track_list") or candidate.track_list
        candidate.barcode = detail.get("barcode") or candidate.barcode
        if not candidate.domain_code:
            candidate.domain_code = "KOREA"
        candidate.raw["detail"] = detail.get("raw")


def search_discogs_by_barcode(barcode: str, limit: int = 5) -> list[dict[str, Any]]:
    try:
        candidates = _discogs_search({"barcode": barcode, "type": "release", "per_page": limit})
    except httpx.HTTPError:
        return []
    _enrich_discogs_candidates(candidates, max_items=min(limit, 5))
    return [c.to_dict() for c in candidates]


def search_discogs_by_query(query: str, limit: int = 5) -> list[dict[str, Any]]:
    try:
        candidates = _discogs_search({"q": query, "type": "release", "per_page": limit})
    except httpx.HTTPError:
        return []
    _enrich_discogs_candidates(candidates, max_items=min(limit, 5))
    return [c.to_dict() for c in candidates]


def search_discogs_artist_name_variations(
    artist_name: str,
    limit: int = 6,
    suppress_errors: bool = True,
) -> list[str]:
    artist_name_s = str(artist_name or "").strip()
    if not artist_name_s:
        return []
    headers = _discogs_headers()
    if headers is None:
        return []

    variation_limit = max(1, min(int(limit or 6), 12))
    names: list[str] = []
    seen: set[str] = set()

    def remember(value: Any) -> None:
        text = str(value or "").strip()
        if not text:
            return
        key = _normalize_text(text)
        if not key or key in seen:
            return
        seen.add(key)
        names.append(text)

    remember(artist_name_s)

    try:
        with _make_http_client() as client:
            response = _get_with_retry(
                client,
                "https://api.discogs.com/database/search",
                params={"q": artist_name_s, "type": "artist", "per_page": variation_limit},
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            rows = data.get("results") or []
            for row in rows:
                resource_url = _pick_first_text(row.get("resource_url"))
                artist_id = _pick_first_text(row.get("id"))
                remember(row.get("title"))
                detail = None
                if resource_url:
                    detail_response = _get_with_retry(client, resource_url, headers=headers)
                    detail_response.raise_for_status()
                    detail = detail_response.json()
                elif artist_id:
                    detail_response = _get_with_retry(client, f"https://api.discogs.com/artists/{artist_id}", headers=headers)
                    detail_response.raise_for_status()
                    detail = detail_response.json()
                if isinstance(detail, dict):
                    remember(detail.get("name"))
                    for variation in detail.get("namevariations") or []:
                        remember(variation)
                if len(names) >= variation_limit:
                    break
    except httpx.HTTPError:
        if suppress_errors:
            return names
        raise

    return names[:variation_limit]


def resolve_discogs_preferred_korean_artist_name(
    artist_name: str,
    *,
    external_id: str | None = None,
    raw: dict[str, Any] | None = None,
    domain_code: str | None = None,
) -> str | None:
    artist_text = str(artist_name or "").strip()
    if not artist_text:
        return None
    if _contains_hangul(artist_text):
        return artist_text

    normalized_domain_code = _normalize_domain_code(domain_code)
    if normalized_domain_code and normalized_domain_code != "KOREA":
        return None

    raw_detail = raw if isinstance(raw, dict) else {}
    headers = _discogs_headers()
    if headers is not None and raw_detail:
        try:
            with _make_http_client() as client:
                artists = raw_detail.get("artists")
                if isinstance(artists, list):
                    for row in artists:
                        if not isinstance(row, dict):
                            continue
                        for candidate in (
                            _pick_first_text(row.get("anv")),
                            _pick_first_text(row.get("name")),
                        ):
                            if candidate and _contains_hangul(candidate):
                                return candidate
                        detail = _fetch_discogs_artist_detail(
                            headers=headers,
                            client=client,
                            artist_id=_pick_first_text(row.get("id")),
                            resource_url=_pick_first_text(row.get("resource_url")),
                        )
                        for candidate in _discogs_artist_detail_name_candidates(detail):
                            if _contains_hangul(candidate):
                                return candidate
        except httpx.HTTPError:
            pass

    preferred_musicbrainz_name = artist_context_service.resolve_musicbrainz_preferred_korean_name(artist_text)
    if preferred_musicbrainz_name and _contains_hangul(preferred_musicbrainz_name):
        return preferred_musicbrainz_name
    return None


def _aladin_search(query: str, limit: int = 5) -> list[Candidate]:
    settings = get_settings()
    if not settings.aladin_ttb_key:
        return []

    # SearchTarget=Music 을 먼저 시도하고, 결과가 없으면 All 로 재시도.
    # 알라딘 TTB API 는 Music 카테고리 결과가 비어있거나 errorCode 를 내려주는 경우가 있음.
    for search_target in ("Music", "All"):
        params = {
            "ttbkey": settings.aladin_ttb_key,
            "Query": query,
            "QueryType": "Keyword",
            "SearchTarget": search_target,
            "MaxResults": max(1, min(limit, 50)),
            "start": 1,
            "output": "js",
            "Version": "20131101",
            "Cover": "Big",  # 200px (TTB API 공식 최대 해상도). 기본값 Mid=85px
        }

        with _make_http_client() as client:
            response = _get_with_retry(client, settings.aladin_base_url, params=params)
            response.raise_for_status()
            try:
                data = response.json()
            except ValueError:
                logger.warning(
                    "aladin search query=%r target=%s: non-JSON response (len=%d)",
                    query, search_target, len(response.text),
                )
                continue

        # 알라딘은 200 OK 이면서 errorCode 를 body 에 포함하는 경우가 있음
        if "errorCode" in data:
            logger.warning(
                "aladin search query=%r target=%s: API error %s – %s",
                query, search_target, data.get("errorCode"), data.get("errorMessage"),
            )
            continue

        candidates = _parse_aladin_candidates(data, query=query)
        if candidates:
            return candidates

        logger.debug(
            "aladin search query=%r target=%s: totalResults=%s, no items returned",
            query, search_target, data.get("totalResults"),
        )

    return []


def search_aladin_by_barcode(barcode: str, limit: int = 5) -> list[dict[str, Any]]:
    try:
        candidates = _aladin_search(barcode, limit=limit)
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("aladin barcode search %r failed: %s", barcode, exc)
        return []
    return [c.to_dict() for c in candidates]


def search_aladin_by_query(query: str, limit: int = 5) -> list[dict[str, Any]]:
    try:
        candidates = _aladin_search(query, limit=limit)
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("aladin query search %r failed: %s", query, exc)
        return []
    return [c.to_dict() for c in candidates]


def _fetch_aladin_item_detail(item_id: str) -> dict[str, Any] | None:
    """Fetch Aladin item detail via ItemLookUp API with Tracklist option."""
    settings = get_settings()
    if not settings.aladin_ttb_key:
        return None
    params = {
        "ttbkey": settings.aladin_ttb_key,
        "itemIdType": "ItemId",
        "ItemId": str(item_id).strip(),
        "output": "js",
        "Version": "20131101",
        "OptResult": "Tracklist",
        "Cover": "Big",
    }
    try:
        with _make_http_client() as client:
            response = _get_with_retry(client, settings.aladin_lookup_url, params=params)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("aladin item lookup %r failed: %s", item_id, exc)
        return None
    if "errorCode" in data:
        logger.warning(
            "aladin item lookup %r API error %s: %s",
            item_id, data.get("errorCode"), data.get("errorMessage"),
        )
        return None
    items = data.get("item") or []
    return items[0] if items else None


def _parse_aladin_track_items(subinfo: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse Aladin subInfo.trackList into [{position, title, duration}] format."""
    track_list = (subinfo or {}).get("trackList") or []
    items = []
    for track in track_list:
        if not isinstance(track, dict):
            continue
        title = str(track.get("title") or "").strip()
        if not title:
            continue
        position = str(track.get("no") or "").strip()
        duration = str(track.get("runningTime") or "").strip()
        items.append({"position": position, "title": title, "duration": duration})
    return items


def _fetch_aladin_tracks_from_web(item_id: str, isbn: str) -> list[dict[str, Any]]:
    """Fetch tracklist by scraping Aladin product Introduce section (getContents.aspx).

    The TTB API ``OptResult=Tracklist`` rarely returns trackList for music items;
    the Introduce AJAX endpoint is more reliable.
    """
    url = f"https://www.aladin.co.kr/shop/wproduct.aspx?ItemId={item_id}"
    params = {}
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": f"https://www.aladin.co.kr/shop/wproduct.aspx?ItemId={item_id}",
        "X-Requested-With": "XMLHttpRequest",
    }
    try:
        with _make_http_client() as client:
            response = _get_with_retry(client, url, params=params, headers=headers)
            response.raise_for_status()
            html = response.text
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("aladin web track fetch %r failed: %s", item_id, exc)
        return []

    # 수록곡 섹션 탐색
    idx = html.find("수록곡")
    if idx < 0:
        return []

    section = html[idx:]
    # 다음 섹션 블록 전까지만 파싱 (5000자 제한)
    next_section = section.find("Ere_prod_mconts_box", 100)
    if 0 < next_section < 5000:
        section = section[:next_section]
    else:
        section = section[:5000]

    raw_items = re.findall(r"<li[^>]*>\s*<span[^>]*>([^<]+)</span>\s*</li>", section)
    tracks: list[dict[str, Any]] = []
    for raw in raw_items:
        raw = raw.strip()
        if not raw:
            continue
        # "1-1. 제목", "A-1. 제목", "1. 제목" 형태에서 위치 분리
        pos_match = re.match(r"^(\d+-\d+|[A-Za-z]-\d+|\d+)\.\s+(.+)$", raw)
        if pos_match:
            position = pos_match.group(1)
            title = pos_match.group(2).strip()
        else:
            position = str(len(tracks) + 1)
            title = raw
        tracks.append({"position": position, "title": title, "duration": ""})
    return tracks



def _fetch_aladin_images_from_web(item_id: str, isbn: str) -> list[dict[str, Any]]:
    """Scrape product description images from Aladin product introduce page."""
    url = f"https://www.aladin.co.kr/shop/wproduct.aspx?ItemId={item_id}"
    params = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": f"https://www.aladin.co.kr/shop/wproduct.aspx?ItemId={item_id}",
    }
    try:
        import httpx as _httpx
        with _httpx.Client(follow_redirects=True, headers=headers, timeout=15.0) as client:
            response = client.get(url)
            response.raise_for_status()
            html = response.text
    except Exception:
        return []

    import re as _re
    images: list[dict[str, Any]] = []
    seen: set[str] = set()

    for m in _re.finditer(r'<img[^>]+(?:src|data-src)="([^"]+)"', html):
        src = m.group(1)
        if not src.startswith("http"):
            if src.startswith("//"):
                src = "https:" + src
            else:
                continue
        if not any(k in src for k in ("/product/", "/cover", "/img/img_content/")):
            continue
        if src in seen:
            continue
        seen.add(src)
        alt_match = _re.search(r'alt="([^"]*)"', m.group(0))
        alt = alt_match.group(1) if alt_match else ""
        label = alt or "상세"
        if "cover500" in src and images:
            label = "커버"
        images.append({"type": label, "uri": src})

    # 소개(Introduce) 섹션 AJAX 엔드포인트에서 추가 이미지 수집
    # 알라딘 상품 소개 HTML은 메인 페이지가 아닌 별도 endpoint로 lazy-load됨:
    # /shop/product/getContents.aspx?ISBN={isbn}&name=Introduce&type=0
    # C + 9자리 숫자 형태 (알라딘 이미지 서버 ISBN 패턴, e.g. C002938753)
    c_isbn_match = _re.search(r'\b(C\d{9})\b', html)
    if c_isbn_match:
        c_isbn = c_isbn_match.group(1)
        import httpx as _httpx
        from datetime import datetime as _dt
        intro_url = (
            f"https://www.aladin.co.kr/shop/product/getContents.aspx"
            f"?ISBN={c_isbn}&name=Introduce&type=0&date={_dt.now().hour}"
        )
        try:
            intro_headers = {
                "User-Agent": headers.get("User-Agent", "Mozilla/5.0"),
                "Accept-Language": "ko-KR,ko;q=0.9",
                "Referer": url,
            }
            with _httpx.Client(timeout=10.0, follow_redirects=True, headers=intro_headers) as ic:
                ir = ic.get(intro_url)
                if ir.status_code == 200 and ir.text:
                    for im in _re.finditer(r'<img[^>]+(?:src|data-src)=["\']([^"\']+)["\']', ir.text):
                        src = im.group(1).strip()
                        if src.startswith("//"):
                            src = "https:" + src
                        elif not src.startswith("http"):
                            continue
                        if "/img/img_content/" not in src and "/product/" not in src:
                            continue
                        if src in seen:
                            continue
                        seen.add(src)
                        images.append({"type": "소개", "uri": src})
        except Exception:
            pass

    # Probe img_content images using numeric ISBN pattern
    isbn_match = _re.search(r'ISBN[^0-9]*(\d{9})', html)
    if isbn_match:
        isbn = isbn_match.group(1)
        import httpx as _httpx
        probe_headers = {"User-Agent": headers.get("User-Agent", "Mozilla/5.0")}
        probe_url = f"https://image.aladin.co.kr/img/img_content/C{isbn}_P.jpg"
        if probe_url not in seen:
            try:
                with _httpx.Client(timeout=5.0, headers=probe_headers) as pc:
                    pr = pc.get(probe_url)
                    if pr.status_code == 200 and "image" in (pr.headers.get("content-type") or ""):
                        seen.add(probe_url)
                        images.append({"type": "상세", "uri": probe_url})
            except Exception:
                pass

    return images

def fetch_aladin_track_items(item_id: str) -> list[dict[str, Any]]:
    """Public helper: fetch Aladin tracklist for a given ItemId. Returns [] on failure."""
    try:
        detail = _fetch_aladin_item_detail(item_id)
        if not detail:
            return []
        # Web scraping (getContents.aspx Introduce) is more reliable than TTB API trackList
        isbn = str(detail.get("isbn") or "").strip()
        if isbn:
            web_tracks = _fetch_aladin_tracks_from_web(item_id, isbn)
            if web_tracks:
                return web_tracks
        # Fallback: TTB API subInfo.trackList
        subinfo = detail.get("subInfo") if isinstance(detail.get("subInfo"), dict) else {}
        return _parse_aladin_track_items(subinfo)
    except Exception as exc:
        logger.warning("fetch_aladin_track_items %r failed: %s", item_id, exc)
        return []


def search_maniadb_by_query(query: str, limit: int = 5) -> list[dict[str, Any]]:
    try:
        candidates = _maniadb_search(query=query, limit=limit)
    except httpx.HTTPError:
        return []
    expanded: list[dict[str, Any]] = []
    for candidate in candidates:
        album_id = _extract_maniadb_album_id(candidate.external_id)
        if not album_id or str(candidate.raw.get("kind") or "").strip().lower() != "album":
            expanded.append(candidate.to_dict())
            continue
        variants = get_maniadb_master_variants(master_external_id=album_id, limit=max(30, limit))
        if not variants:
            expanded.append(candidate.to_dict())
            continue
        for variant in variants:
            row = dict(variant)
            row["artist_or_brand"] = row.get("artist_or_brand") or candidate.artist_or_brand
            row["title"] = row.get("title") or candidate.title
            row["confidence"] = round(float(candidate.confidence or 0.0), 3)
            base_raw = dict(candidate.raw) if isinstance(candidate.raw, dict) else {}
            variant_raw = dict(row.get("raw") or {}) if isinstance(row.get("raw"), dict) else {}
            row["raw"] = {**base_raw, **variant_raw}
            expanded.append(row)

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in expanded:
        key = (str(row.get("source") or "").strip().upper(), str(row.get("external_id") or "").strip())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped[: max(1, limit)]


def search_discogs_master_by_query(query: str, limit: int = 10) -> list[dict[str, Any]]:
    headers = _discogs_headers()
    if headers is None:
        return []

    params = {
        "q": query,
        "type": "master",
        "per_page": max(1, min(limit, 100)),
    }

    try:
        with _make_http_client() as client:
            response = _get_with_retry(client, "https://api.discogs.com/database/search", params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError:
        return []

    rows = data.get("results") or []
    out: list[dict[str, Any]] = []
    for row in rows:
        full_title = str(row.get("title") or "")
        artist, title = _pick_artist_from_discogs_title(full_title)
        row_barcode = row.get("barcode")
        if isinstance(row_barcode, list):
            row_barcode = row_barcode[0] if row_barcode else None
        sim = _token_similarity(query, full_title)
        confidence = min(max(0.60 + (0.32 * sim), 0.0), 0.95)
        out.append(
            {
                "source": "DISCOGS",
                "master_external_id": str(row.get("id") or ""),
                "title": title or full_title,
                "artist_or_brand": artist,
                "release_year": _safe_year(row.get("year")),
                "label_name": _pick_first_text(row.get("label")),
                "catalog_no": _normalize_catalog_no(row.get("catno")) or _normalize_catalog_no((row.get("labels") or [{}])[0].get("catno") if row.get("labels") else None),
                "barcode": str(row_barcode).strip() if row_barcode else None,
                "variant_count": None,
                "confidence": round(confidence, 3),
                "raw": row,
            }
        )
    return out[: max(1, limit)]


def search_maniadb_master_by_query(query: str, limit: int = 10) -> list[dict[str, Any]]:
    try:
        candidates = _maniadb_search(query=query, limit=limit)
    except httpx.HTTPError:
        return []

    out: list[dict[str, Any]] = []
    for c in candidates:
        if c.raw.get("kind") != "album":
            continue
        master_external_id = str(c.raw.get("album_id") or c.external_id.replace("album:", "", 1))
        out.append(
            {
                "source": "MANIADB",
                "master_external_id": master_external_id,
                "title": c.title,
                "artist_or_brand": c.artist_or_brand,
                "release_year": c.release_year,
                "label_name": c.label_name,
                "catalog_no": c.catalog_no,
                "barcode": c.barcode,
                "variant_count": None,
                "confidence": round(c.confidence, 3),
                "raw": c.raw,
            }
        )
        if len(out) >= limit:
            break

    return out


def _get_album_master_candidate_preview(source: str, master_external_id: str) -> dict[str, Any]:
    source_u = str(source or "").strip().upper()
    ext = str(master_external_id or "").strip()
    if not source_u or not ext:
        return {}

    try:
        if source_u == "DISCOGS":
            page = get_discogs_master_variants_page(
                master_external_id=ext,
                page=1,
                page_size=5,
                include_details=True,
            )
            items = page.get("items") if isinstance(page, dict) else []
            rows = [row for row in items if isinstance(row, dict)] if isinstance(items, list) else []
            preferred = next(
                (row for row in rows if _clean_master_candidate_barcode(row.get("barcode"))),
                rows[0] if rows else None,
            )
            if not isinstance(preferred, dict):
                return {}
            return {
                "label_name": preferred.get("label_name"),
                "catalog_no": preferred.get("catalog_no"),
                "barcode": preferred.get("barcode"),
            }

        if source_u == "MANIADB":
            items = get_maniadb_master_variants(master_external_id=ext, limit=30)
            preferred = next(
                (row for row in items if isinstance(row, dict) and _clean_master_candidate_barcode(row.get("barcode"))),
                items[0] if items else None,
            )
            if not isinstance(preferred, dict):
                return {}
            return {
                "label_name": preferred.get("label_name"),
                "catalog_no": preferred.get("catalog_no"),
                "barcode": preferred.get("barcode"),
            }
    except httpx.HTTPError:
        return {}

    return {}


def _clean_master_candidate_barcode(value: Any) -> str | None:
    normalized = _normalize_barcode(value)
    if len(normalized) < 8:
        return None
    return normalized


def _parse_maniadb_album_header(html_text: str) -> tuple[str | None, str | None]:
    meta = re.search(r'<meta\s+name="keyword"\s+content="([^"]+)"', html_text, re.IGNORECASE)
    if not meta:
        return None, None
    keyword = _clean_html_text(meta.group(1))
    first_chunk = keyword.split(",", 1)[0].strip()
    if not first_chunk:
        return None, None
    artist, title, _, _ = _parse_maniadb_release_text(first_chunk)
    return artist, title


def _extract_maniadb_album_page_cover_image_url(html_text: str, album_id: str | None = None) -> str | None:
    if not html_text:
        return None
    patterns = (
        r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"',
        r'<div[^>]+id="COVERART_FRONT"[^>]*>.*?<a[^>]+href="([^"]+)"',
        r'<div[^>]+id="COVERART_FRONT"[^>]*>.*?<img[^>]+src="([^"]+)"',
    )
    for pattern in patterns:
        match = re.search(pattern, html_text, re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        normalized = _normalize_maniadb_image_url(match.group(1), album_id=album_id)
        if normalized:
            return normalized
    return None


def _maniadb_image_items_from_block(block_html: str | None) -> list[dict[str, Any]]:
    if not block_html:
        return []
    matches = re.findall(r'<img\s+src="([^"]+)"', block_html, re.IGNORECASE)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, src in enumerate(matches):
        src_clean = _clean_html_text(src)
        if not src_clean:
            continue
        lower = src_clean.lower()
        if any(
            token in lower
            for token in (
                "music_lp.gif",
                "music_cd.gif",
                "music_tape.gif",
                "icon_",
                "/icon/",
                "/icons/",
                "btn_",
                "spacer",
                "blank.gif",
            )
        ):
            continue
        if src_clean in seen:
            continue
        seen.add(src_clean)
        image_type = "뒷면" if "back" in lower or "rear" in lower else ("앞면" if index == 0 else f"추가 {len(out)}")
        out.append({"type": image_type, "uri": src_clean, "uri150": src_clean})
    return out


def _maniadb_album_image_group(album_id: str) -> str | None:
    digits = re.sub(r"\D", "", str(album_id or "").strip())
    if len(digits) < 4:
        return None
    return digits[:-3]


def _maniadb_album_image_leaf(album_id: str) -> str | None:
    digits = re.sub(r"\D", "", str(album_id or "").strip())
    if len(digits) < 4:
        return None
    return digits[-6:]


def _maniadb_variant_cover_url(album_id: str, variant_seq: str | None, side: str = "f") -> str | None:
    group = _maniadb_album_image_group(album_id)
    leaf = _maniadb_album_image_leaf(album_id)
    seq = re.sub(r"\D", "", str(variant_seq or "").strip())
    side_code = "b" if str(side or "").strip().lower() == "b" else "f"
    if not group or not leaf or not seq:
        return None
    return f"https://i.maniadb.com/images/album/{group}/{leaf}_{seq}_{side_code}.jpg"


def _maniadb_variant_image_matches(url: str | None, album_id: str | None, variant_seq: str | None) -> bool:
    normalized_url = _clean_html_text(url)
    digits = re.sub(r"\D", "", str(album_id or "").strip())
    leaf = digits[-6:] if len(digits) >= 4 else ""
    seq = re.sub(r"\D", "", str(variant_seq or "").strip())
    if not normalized_url or not digits or not seq:
        return False
    lower = normalized_url.lower()
    legacy_match = re.search(r"/(\d+)_([fb])_([0-9]+)\.jpg$", lower)
    if legacy_match:
        file_album_id = legacy_match.group(1).lstrip("0") or "0"
        file_seq = legacy_match.group(3).lstrip("0") or "0"
        return file_album_id in {
            digits.lstrip("0") or "0",
            (leaf.lstrip("0") or "0") if leaf else "",
        } and file_seq == seq.lstrip("0")
    current_match = re.search(r"/(\d+)_([0-9]+)_[fb]\.jpg$", lower)
    if not current_match:
        return False
    file_album_id = current_match.group(1).lstrip("0") or "0"
    file_seq = current_match.group(2).lstrip("0") or "0"
    return file_album_id in {
        digits.lstrip("0") or "0",
        (leaf.lstrip("0") or "0") if leaf else "",
    } and file_seq == seq.lstrip("0")


def _normalize_maniadb_image_url(url: str | None, album_id: str | None = None, variant_seq: str | None = None) -> str | None:
    cleaned = _clean_html_text(url)
    if not cleaned:
        return None
    normalized = re.sub(r"/images/album_t(?:/\d+)?/", "/images/album/", cleaned)
    normalized = normalized.replace("/images/album_t/", "/images/album/")
    normalized = re.sub(r"^http://i\.maniadb\.com/", "https://i.maniadb.com/", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"^//i\.maniadb\.com/", "https://i.maniadb.com/", normalized, flags=re.IGNORECASE)
    return normalized


def _maniadb_release_year_from_token(date_token: str | None) -> int | None:
    text = _clean_html_text(date_token)
    if not text:
        return None
    exact_year = _safe_year(text.split("-", 1)[0])
    if exact_year is not None:
        return exact_year
    year_match = re.search(r"\b((?:19|20)\d{2})\b", text)
    if not year_match:
        return None
    return _safe_year(year_match.group(1))


def _parse_maniadb_release_legend(
    legend_html: str,
    album_id: str,
    album_artist: str | None,
    album_title: str | None,
    block_html: str | None = None,
    album_cover_image_url: str | None = None,
    album_genres: list[str] | None = None,
) -> dict[str, Any] | None:
    sid_match = re.search(r"(?:[?&]|&amp;)s=(\d+)", legend_html, re.IGNORECASE)
    fmt_match = re.search(r'alt="([^"]+)"', legend_html, re.IGNORECASE)
    # <img alt="..."> 텍스트를 보존한 뒤 HTML 정리
    legend_with_alt = re.sub(r'<img[^>]+alt="([^"]+)"[^>]*/?>',
                             lambda m: m.group(1), legend_html, flags=re.IGNORECASE)
    clean = _clean_html_text(legend_with_alt)
    chunks = [c.strip() for c in clean.split("::") if c.strip()]
    # variant 링크(s=N)가 있으면 유효한 release 블록 — chunks 1개여도 허용
    if not chunks:
        return None
    if len(chunks) < 2 and not re.search(r"(?:[?&]|&amp;)s=\d+", legend_html):
        return None

    date_token = chunks[0]
    label_token = chunks[1] if len(chunks) >= 2 else ""
    year = _maniadb_release_year_from_token(date_token)
    released_date = date_token if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_token or "") else None

    # Detect swapped order: if chunk[0] is not a date but chunk[1] is
    if not released_date and re.fullmatch(r"\d{4}-\d{2}-\d{2}", label_token or ""):
        released_date = label_token
        label_token = date_token
        if not year:
            year = _maniadb_release_year_from_token(released_date)

    label_name = label_token
    catno: str | None = None
    barcode: str | None = None

    inner_match = re.search(r"\(([^)]+)\)", label_token)
    if inner_match:
        label_name = label_token[: inner_match.start()].strip() or None
        atoms = [a.strip() for a in inner_match.group(1).split(",") if a.strip()]
        catno_parts: list[str] = []
        for atom in atoms:
            if re.fullmatch(r"\d{8,14}", atom):
                barcode = atom
            else:
                catno_parts.append(atom)
        catno = ", ".join(catno_parts) if catno_parts else None
    else:
        label_name = label_token.strip() or None

    variant_seq = sid_match.group(1) if sid_match else ""
    external_id = f"{album_id}:{variant_seq}" if variant_seq else album_id
    format_name = _infer_format_from_text(fmt_match.group(1) if fmt_match else None)
    title = album_title or f"Album {album_id}"
    cover_image_url: str | None = None
    image_items: list[dict[str, Any]] = []
    track_list: list[str] = []

    if block_html:
        raw_image_items = _maniadb_image_items_from_block(block_html)
        seen_image_urls: set[str] = set()
        for image in raw_image_items:
            raw_uri = _pick_first_text(image.get("uri"))
            normalized_uri = _normalize_maniadb_image_url(raw_uri, album_id=album_id, variant_seq=variant_seq)
            if not normalized_uri or normalized_uri in seen_image_urls:
                continue
            expected_token = f"{album_id}_{variant_seq}_".lower() if album_id and variant_seq else ""
            if expected_token and expected_token not in normalized_uri.lower():
                if not _maniadb_variant_image_matches(normalized_uri, album_id, variant_seq):
                    continue
            image_type = _pick_first_text(image.get("type")) or ("추가" if image_items else "앞면")
            image_items.append({"type": image_type, "uri": normalized_uri, "uri150": normalized_uri})
            seen_image_urls.add(normalized_uri)
        if image_items and not cover_image_url:
            cover_image_url = _pick_first_text(image_items[0].get("uri"))
        if not image_items:
            # variant 전용 이미지가 없으면 다른 variant의 이미지를 사용하지 않음.
            # album_cover_image_url은 앨범 페이지의 첫 이미지(다른 variant일 수 있음)이므로 사용하지 않는다.
            # _maniadb_variant_cover_url로 직접 URL을 추측해 사용 (해당 variant 고유 이미지 경로).
            guessed = _maniadb_variant_cover_url(album_id, variant_seq, "f")
            if guessed:
                cover_image_url = guessed
                image_items = [{"type": "앞면", "uri": guessed, "uri150": guessed}]

        # class="tracks" 또는 class="trackno"/"song" 구조 모두 처리
        track_block_match = re.search(r'<td\s+class="tracks">(.*?)</td>', block_html, re.IGNORECASE | re.DOTALL)
        if track_block_match:
            track_html = track_block_match.group(1)
            tokens = re.findall(r"\d+\.\s*(?:<[^>]+>\s*)*([^/<]+)", track_html)
            track_list = [t for t in (_clean_html_text(tok) for tok in tokens) if t]
        else:
            # ManiaDB 신형 구조: <td class="trackno">N.</td> ... <td class="song">곡명</td>
            song_cells = re.findall(
                r'<td[^>]+class="song"[^>]*>(.*?)</td>',
                block_html, re.IGNORECASE | re.DOTALL,
            )
            parsed_titles: list[str] = []
            for cell in song_cells:
                # <div class="song"> 안의 <a> 링크 텍스트 추출
                a_match = re.search(r'<a[^>]*>(.*?)</a>', cell, re.IGNORECASE | re.DOTALL)
                raw = a_match.group(1) if a_match else cell
                # &nbsp; / 이미지 태그 제거
                raw = re.sub(r'&nbsp;', ' ', raw, flags=re.IGNORECASE)
                raw = re.sub(r'<img[^>]*/>', '', raw, flags=re.IGNORECASE)
                title = _clean_html_text(raw).strip()
                if title:
                    parsed_titles.append(title)
            track_list = parsed_titles
    else:
        # block_html 없는 경우: variant 고유 URL만 시도
        guessed = _maniadb_variant_cover_url(album_id, variant_seq, "f")
        cover_image_url = guessed or None
        if cover_image_url:
            image_items = [{"type": "앞면", "uri": cover_image_url, "uri150": cover_image_url}]

    return {
        "source": "MANIADB",
        "external_id": external_id,
        "title": title,
        "artist_or_brand": album_artist,
        "release_year": year,
        "released_date": released_date,
        "country": "KR",
        "format_name": format_name,
        "media_type": format_name,
        "release_type": None,
        "domain_code": "KOREA",
        "genres": album_genres or [],
        "styles": [],
        "label_name": label_name,
        "catalog_no": catno,
        "barcode": barcode,
        "cover_image_url": cover_image_url,
        "image_items": image_items,
        "track_list": track_list,
        "raw": {
            "album_id": album_id,
            "release_seq": variant_seq,
            "label_name": label_name,
            "legend_text": clean,
        },
    }


def _discogs_master_versions_fetch_page(
    master_external_id: str,
    page: int,
    per_page: int,
    headers: dict[str, str],
    client: httpx.Client,
) -> tuple[list[dict[str, Any]], int | None, int | None]:
    response = _get_with_retry(
        client,
        f"https://api.discogs.com/masters/{master_external_id}/versions",
        params={"page": max(1, int(page)), "per_page": max(1, min(int(per_page), 100))},
        headers=headers,
    )
    response.raise_for_status()
    data = response.json()
    rows_raw = data.get("versions")
    rows = [row for row in rows_raw if isinstance(row, dict)] if isinstance(rows_raw, list) else []
    pagination = data.get("pagination") if isinstance(data.get("pagination"), dict) else {}
    total_items = _safe_positive_int(pagination.get("items"))
    total_pages = _safe_positive_int(pagination.get("pages"))
    return rows, total_items, total_pages


def _normalize_barcode(v: Any) -> str:
    text = _pick_first_text(v) or ""
    if not text:
        return ""
    normalized = re.sub(r"[^0-9Xx]", "", text).upper()
    return normalized or text.strip().upper()


def _barcode_match(candidate: Any, query: str) -> bool:
    c = _normalize_barcode(candidate)
    q = _normalize_barcode(query)
    if not c or not q:
        return False
    return c == q or c.endswith(q) or q.endswith(c)


def _catalog_match(candidate: Any, query: str) -> bool:
    cand = str(_normalize_catalog_no(candidate) or "").strip().lower()
    q = str(_normalize_catalog_no(query) or query or "").strip().lower()
    if not q:
        return True
    if not cand:
        return False
    return q in cand


def _discogs_master_row_format_items(row: dict[str, Any]) -> list[dict[str, Any]]:
    major_formats = _unique_text_list(row.get("major_formats"))
    format_text = _pick_first_text(row.get("format"))
    qty = _pick_first_text(row.get("format_quantity"))
    if not major_formats and not format_text:
        return []

    if not major_formats:
        return [
            {
                "name": format_text,
                "descriptions": [],
                "qty": qty,
                "text": None,
            }
        ]

    items: list[dict[str, Any]] = []
    for idx, name in enumerate(major_formats):
        items.append(
            {
                "name": name,
                "descriptions": [],
                "qty": qty,
                "text": format_text if format_text and idx == 0 else None,
            }
        )
    return items


def _discogs_master_row_to_variant(
    row: dict[str, Any],
    detail: dict[str, Any] | None,
    master_detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    format_text = str(row.get("format") or "")
    major_formats = row.get("major_formats")
    major_text = " ".join(major_formats) if isinstance(major_formats, list) else ""
    normalized_format = _infer_format_from_text(major_text) or _infer_format_from_text(format_text)
    base_meta = _discogs_format_meta(row.get("format"), fallback_format_text=format_text)
    release_id = str(row.get("id") or "")
    thumb = _pick_first_text(row.get("thumb"))
    master_genres = _unique_text_list(master_detail.get("master_genres")) if master_detail else []
    master_styles = _unique_text_list(master_detail.get("master_styles")) if master_detail else []
    genres = (detail.get("genres") if detail else None) or master_genres
    styles = (detail.get("styles") if detail else None) or master_styles
    return {
        "source": "DISCOGS",
        "external_id": release_id,
        "title": str(row.get("title") or ""),
        "artist_or_brand": None,
        "release_year": _safe_year(row.get("released")),
        "master_release_year": detail.get("master_release_year") if detail else None,
        "released_date": (detail.get("released_date") if detail else None) or _pick_first_text(row.get("released")),
        "country": row.get("country"),
        "format_name": (detail.get("format_name") if detail else None) or normalized_format or base_meta.get("format_name") or format_text or None,
        "media_type": (detail.get("media_type") if detail else None) or base_meta.get("media_type"),
        "release_type": (detail.get("release_type") if detail else None) or base_meta.get("release_type"),
        "domain_code": (detail.get("domain_code") if detail else None),
        "genres": genres,
        "styles": styles,
        "label_name": detail.get("label_name") if detail else _pick_first_text(row.get("label")),
        "catalog_no": (detail.get("catalog_no") if detail else None) or _normalize_catalog_no(row.get("catno")),
        "barcode": detail.get("barcode") if detail else None,
        "cover_image_url": (detail.get("cover_image_url") if detail else None) or thumb,
        "track_list": detail.get("track_list") if detail else [],
        "disc_count": detail.get("disc_count") if detail else None,
        "speed_rpm": detail.get("speed_rpm") if detail else None,
        "has_obi": bool(detail.get("has_obi")) if detail and detail.get("has_obi") is not None else None,
        "runout_matrix": detail.get("runout_matrix") if detail else [],
        "pressing_country": (detail.get("pressing_country") if detail else None) or _pick_first_text(row.get("country")),
        "source_notes": detail.get("source_notes") if detail else None,
        "credits": detail.get("credits") if detail else [],
        "identifier_items": detail.get("identifier_items") if detail else [],
        "image_items": detail.get("image_items") if detail else [],
        "company_items": detail.get("company_items") if detail else [],
        "series": detail.get("series") if detail else [],
        "format_items": detail.get("format_items") if detail else _discogs_master_row_format_items(row),
        "track_items": detail.get("track_items") if detail else [],
        "label_items": detail.get("label_items") if detail else [],
        "raw": row,
        "raw_detail": detail.get("raw_detail") if detail else None,
    }


def get_discogs_master_variants_page(
    master_external_id: str,
    page: int = 1,
    page_size: int = 30,
    catalog_no: str | None = None,
    barcode: str | None = None,
    include_details: bool = False,
) -> dict[str, Any]:
    headers = _discogs_headers()
    if headers is None:
        return {
            "items": [],
            "page": max(1, int(page)),
            "page_size": max(1, min(int(page_size), 100)),
            "total_count": 0,
            "has_next": False,
            "filtered": False,
            "filter_catalog_no": None,
            "filter_barcode": None,
            "truncated": False,
        }

    page_n = max(1, int(page))
    page_size_n = max(1, min(int(page_size), 100))
    catalog_filter = str(catalog_no or "").strip()
    barcode_filter = str(barcode or "").strip()
    is_filtered = bool(catalog_filter or barcode_filter)
    detail_cache: dict[str, dict[str, Any] | None] = {}
    master_cache: dict[str, dict[str, Any] | None] = {}

    def fetch_detail(release_id: str, client: httpx.Client) -> dict[str, Any] | None:
        rid = str(release_id or "").strip()
        if not rid:
            return None
        if rid in detail_cache:
            return detail_cache[rid]
        detail = _fetch_discogs_release_detail(
            rid,
            headers=headers,
            client=client,
            master_cache=master_cache,
        )
        detail_cache[rid] = detail
        return detail

    try:
        with _make_http_client(timeout=20.0) as client:
            master_detail = _fetch_discogs_master_detail(master_external_id, headers=headers, client=client)
            if master_detail is not None:
                master_cache[str(master_external_id)] = master_detail
            if not is_filtered:
                rows, total_items, total_pages = _discogs_master_versions_fetch_page(
                    master_external_id=master_external_id,
                    page=page_n,
                    per_page=page_size_n,
                    headers=headers,
                    client=client,
                )
                items = [
                    _discogs_master_row_to_variant(
                        row=row,
                        detail=fetch_detail(str(row.get("id") or ""), client) if include_details else None,
                        master_detail=master_detail,
                    )
                    for row in rows
                ]
                return {
                    "items": items,
                    "page": page_n,
                    "page_size": page_size_n,
                    "total_count": total_items if total_items is not None else len(items),
                    "has_next": bool(total_pages and page_n < total_pages),
                    "filtered": False,
                    "filter_catalog_no": None,
                    "filter_barcode": None,
                    "truncated": False,
                }

            offset = (page_n - 1) * page_size_n
            matched_total = 0
            has_overflow = False
            selected_rows: list[tuple[dict[str, Any], dict[str, Any] | None]] = []
            scan_page = 1
            scan_per_page = 100
            total_pages_hint: int | None = None
            scanned_rows = 0
            max_scan_rows = 2500 if barcode_filter else 10000
            truncated = False

            while True:
                rows, _items, total_pages = _discogs_master_versions_fetch_page(
                    master_external_id=master_external_id,
                    page=scan_page,
                    per_page=scan_per_page,
                    headers=headers,
                    client=client,
                )
                if total_pages_hint is None:
                    total_pages_hint = total_pages
                if not rows:
                    break

                for row in rows:
                    scanned_rows += 1
                    if scanned_rows > max_scan_rows:
                        truncated = True
                        break

                    if catalog_filter and not _catalog_match(row.get("catno"), catalog_filter):
                        continue

                    detail: dict[str, Any] | None = None
                    if barcode_filter:
                        release_id = str(row.get("id") or "").strip()
                        detail = fetch_detail(release_id, client)
                        if not _barcode_match(detail.get("barcode") if detail else None, barcode_filter):
                            continue

                    matched_total += 1
                    if matched_total <= offset:
                        continue

                    if len(selected_rows) < page_size_n:
                        selected_rows.append((row, detail))
                    else:
                        has_overflow = True

                if truncated:
                    break
                if total_pages_hint is not None and scan_page >= total_pages_hint:
                    break
                scan_page += 1

            items: list[dict[str, Any]] = []
            for row, detail in selected_rows:
                row_detail = detail
                if include_details and row_detail is None:
                    row_detail = fetch_detail(str(row.get("id") or ""), client)
                items.append(
                    _discogs_master_row_to_variant(
                        row=row,
                        detail=row_detail,
                        master_detail=master_detail,
                    )
                )

            total_count: int | None = None
            if not truncated and total_pages_hint is not None and scan_page >= total_pages_hint:
                total_count = matched_total

            has_next = has_overflow
            if total_count is not None:
                has_next = (page_n * page_size_n) < total_count

            return {
                "items": items,
                "page": page_n,
                "page_size": page_size_n,
                "total_count": total_count,
                "has_next": has_next,
                "filtered": True,
                "filter_catalog_no": catalog_filter or None,
                "filter_barcode": barcode_filter or None,
                "truncated": truncated,
            }
    except httpx.HTTPError:
        return {
            "items": [],
            "page": page_n,
            "page_size": page_size_n,
            "total_count": 0,
            "has_next": False,
            "filtered": is_filtered,
            "filter_catalog_no": catalog_filter or None,
            "filter_barcode": barcode_filter or None,
            "truncated": False,
        }


def get_discogs_master_variants(
    master_external_id: str,
    limit: int = 30,
    include_details: bool = False,
) -> list[dict[str, Any]]:
    limit_n = max(1, int(limit))
    out: list[dict[str, Any]] = []
    page = 1
    while len(out) < limit_n:
        remaining = limit_n - len(out)
        page_size = min(remaining, 100)
        page_result = get_discogs_master_variants_page(
            master_external_id=master_external_id,
            page=page,
            page_size=page_size,
            include_details=include_details,
        )
        items = page_result.get("items")
        rows = [row for row in items if isinstance(row, dict)] if isinstance(items, list) else []
        if not rows:
            break
        out.extend(rows)
        if not bool(page_result.get("has_next")):
            break
        page += 1
    return out[:limit_n]


def get_maniadb_master_variants(master_external_id: str, limit: int = 30) -> list[dict[str, Any]]:
    settings = get_settings()
    base_url = settings.maniadb_base_url.rstrip("/")
    album_id = str(master_external_id).strip()
    if not album_id:
        return []

    try:
        with _make_http_client(follow_redirects=True) as client:
            response = _get_with_retry(client, f"{base_url}/album/{album_id}", params={"o": "l", "s": 0})
            response.raise_for_status()
            html_text = response.text
    except httpx.HTTPError:
        return []

    album_artist, album_title = _parse_maniadb_album_header(html_text)
    album_cover_image_url = _extract_maniadb_album_page_cover_image_url(html_text, album_id=album_id)

    # Extract genre/style info from album page (outside variant blocks)
    genre_match = re.search(r'GENRE/STYLE:\s*</td>\s*<td class="label-text">(.*?)</td>', html_text, re.DOTALL)
    album_genres: list[str] = []
    if genre_match:
        album_genres = [g.strip() for g in re.findall(r'<aa[^>]*>([^<]+)</a>', genre_match.group(1)) if g.strip()]

    block_pattern = re.compile(r"<fieldset[^>]*>(.*?)</fieldset>", re.IGNORECASE | re.DOTALL)
    out: list[dict[str, Any]] = []
    for block in block_pattern.finditer(html_text):
        block_html = block.group(1)
        legend_match = re.search(r"<legend>(.*?)</legend>", block_html, re.IGNORECASE | re.DOTALL)
        if not legend_match:
            continue
        parsed = _parse_maniadb_release_legend(
            legend_match.group(1),
            album_id=album_id,
            album_artist=album_artist,
            album_title=album_title,
            block_html=block_html,
            album_cover_image_url=album_cover_image_url,
            album_genres=album_genres,
        )
        if parsed is None:
            continue
        out.append(parsed)
        if len(out) >= limit:
            break

    if out:
        return out[:limit]

    # Fallback: at least return a single album-level row.
    return [
        {
            "source": "MANIADB",
            "external_id": album_id,
            "title": album_title or f"Album {album_id}",
            "artist_or_brand": album_artist,
            "release_year": None,
            "country": "KR",
            "format_name": None,
            "label_name": None,
            "catalog_no": None,
            "barcode": None,
            "cover_image_url": album_cover_image_url,
            "track_list": [],
            "raw": {"album_id": album_id},
        }
    ]


def _discogs_metadata_artist_match_level(candidate: dict[str, Any], artist_or_brand: str | None) -> int:
    return _lookup_match_level(artist_or_brand, candidate.get("artist_or_brand"))


def _discogs_metadata_title_match_level(candidate: dict[str, Any], title: str | None) -> int:
    return max(
        _lookup_match_level(title, candidate.get("title")),
        _lookup_compact_match_level(title, candidate.get("title")),
    )


def _filter_discogs_candidates(
    candidates: list[dict[str, Any]],
    *,
    artist_or_brand: str | None = None,
    title: str | None = None,
) -> list[dict[str, Any]]:
    narrowed = candidates

    if artist_or_brand:
        matched_artist = [candidate for candidate in narrowed if _discogs_metadata_artist_match_level(candidate, artist_or_brand) > 0]
        if matched_artist:
            narrowed = matched_artist

    if title:
        matched_title = [candidate for candidate in narrowed if _discogs_metadata_title_match_level(candidate, title) > 0]
        if matched_title:
            narrowed = matched_title

    if artist_or_brand or title:
        narrowed = sorted(
            narrowed,
            key=lambda candidate: (
                _discogs_metadata_artist_match_level(candidate, artist_or_brand),
                _discogs_metadata_title_match_level(candidate, title),
                float(candidate.get("confidence") or 0.0),
            ),
            reverse=True,
        )

    return narrowed


def _dedupe_discogs_candidates(
    candidates: list[dict[str, Any]],
    *,
    id_key: str,
    limit: int,
    artist_or_brand: str | None = None,
    title: str | None = None,
) -> list[dict[str, Any]]:
    dedup: dict[str, dict[str, Any]] = {}
    for row in candidates:
        candidate = dict(row)
        candidate_id = str(candidate.get(id_key) or "").strip()
        if not candidate_id:
            continue
        current = dedup.get(candidate_id)
        if current is None or float(candidate.get("confidence") or 0.0) > float(current.get("confidence") or 0.0):
            dedup[candidate_id] = candidate
    merged = list(dedup.values())
    filtered = _filter_discogs_candidates(
        merged,
        artist_or_brand=artist_or_brand,
        title=title,
    )
    return filtered[: max(1, int(limit or 1))]


def _search_discogs_release_with_artist_variations(
    *,
    query: str,
    artist_or_brand: str | None,
    title: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    artist_text = str(artist_or_brand or "").strip()
    title_text = str(title or "").strip()
    if not artist_text:
        return []

    variation_names = search_discogs_artist_name_variations(artist_text, limit=6, suppress_errors=True)
    if not variation_names:
        return []

    collected: list[dict[str, Any]] = []
    seen_queries: set[str] = {_normalize_text(query)}

    def run_query(search_query: str) -> list[dict[str, Any]]:
        normalized_query = _normalize_text(search_query)
        if not normalized_query or normalized_query in seen_queries:
            return []
        seen_queries.add(normalized_query)
        return search_discogs_by_query(search_query, limit=limit)

    for variation_name in variation_names:
        variation_text = str(variation_name or "").strip()
        if not variation_text:
            continue
        query_text = " ".join(part for part in [variation_text, title_text] if part).strip()
        results = run_query(query_text)
        if title_text:
            results = [candidate for candidate in results if _discogs_metadata_title_match_level(candidate, title_text) > 0]
        else:
            results = _filter_discogs_candidates(
                results,
                artist_or_brand=variation_text,
                title=title_text,
            )
        if results:
            collected.extend(results)
            break

    if not collected and title_text:
        for variation_name in variation_names:
            variation_text = str(variation_name or "").strip()
            if not variation_text:
                continue
            results = run_query(variation_text)
            matched = [candidate for candidate in results if _discogs_metadata_title_match_level(candidate, title_text) > 0]
            if matched:
                collected.extend(matched)
                break

    return _dedupe_discogs_candidates(
        collected,
        id_key="external_id",
        limit=limit,
        artist_or_brand=artist_text,
        title=title_text,
    )


def _search_discogs_master_with_artist_variations(
    *,
    query: str,
    artist_or_brand: str | None,
    title: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    artist_text = str(artist_or_brand or "").strip()
    title_text = str(title or "").strip()
    if not artist_text:
        return []

    variation_names = search_discogs_artist_name_variations(artist_text, limit=6, suppress_errors=True)
    if not variation_names:
        return []

    collected: list[dict[str, Any]] = []
    seen_queries: set[str] = {_normalize_text(query)}

    def run_query(search_query: str) -> list[dict[str, Any]]:
        normalized_query = _normalize_text(search_query)
        if not normalized_query or normalized_query in seen_queries:
            return []
        seen_queries.add(normalized_query)
        return search_discogs_master_by_query(search_query, limit=limit)

    for variation_name in variation_names:
        variation_text = str(variation_name or "").strip()
        if not variation_text:
            continue
        query_text = " ".join(part for part in [variation_text, title_text] if part).strip()
        results = _filter_discogs_candidates(
            run_query(query_text),
            artist_or_brand=variation_text,
            title=title_text,
        )
        if results:
            collected.extend(results)
            break

    if not collected and title_text:
        for variation_name in variation_names:
            variation_text = str(variation_name or "").strip()
            if not variation_text:
                continue
            results = _filter_discogs_candidates(
                run_query(variation_text),
                artist_or_brand=variation_text,
                title=title_text,
            )
            if results:
                collected.extend(results)
                break

    return _dedupe_discogs_candidates(
        collected,
        id_key="master_external_id",
        limit=limit,
        artist_or_brand=artist_text,
        title=title_text,
    )


def search_album_master_candidates(
    query: str,
    source: str = "AUTO",
    limit: int = 10,
    artist_or_brand: str | None = None,
    title: str | None = None,
) -> list[dict[str, Any]]:
    source_u = (source or "AUTO").upper()
    limit_n = max(1, min(limit, 50))
    has_korean_query = bool(re.search(r"[가-힣]", query))
    candidates: list[dict[str, Any]] = []

    if source_u in {"AUTO", "DISCOGS"}:
        discogs_candidates = search_discogs_master_by_query(query, limit=limit_n)
        if not discogs_candidates and (artist_or_brand or title):
            discogs_candidates = _search_discogs_master_with_artist_variations(
                query=query,
                artist_or_brand=artist_or_brand,
                title=title,
                limit=limit_n,
            )
        candidates.extend(discogs_candidates)

    if source_u in {"AUTO", "MANIADB"}:
        if source_u == "MANIADB" or has_korean_query:
            maniadb_limit = limit_n if source_u == "MANIADB" else max(1, min(limit_n, max(3, limit_n // 2)))
            candidates.extend(search_maniadb_master_by_query(query, limit=maniadb_limit))

    dedup: dict[tuple[str, str], dict[str, Any]] = {}
    for c in candidates:
        key = (str(c.get("source")), str(c.get("master_external_id")))
        if key not in dedup or float(c.get("confidence", 0)) > float(dedup[key].get("confidence", 0)):
            dedup[key] = c

    merged = sorted(dedup.values(), key=lambda x: float(x.get("confidence", 0)), reverse=True)
    out: list[dict[str, Any]] = []
    for row in merged[:limit_n]:
        candidate = dict(row)
        if not str(candidate.get("barcode") or "").strip():
            preview = _get_album_master_candidate_preview(
                source=str(candidate.get("source") or ""),
                master_external_id=str(candidate.get("master_external_id") or ""),
            )
            if preview:
                preview_barcode = _clean_master_candidate_barcode(preview.get("barcode"))
                if preview_barcode:
                    if preview.get("label_name"):
                        candidate["label_name"] = preview.get("label_name")
                    if preview.get("catalog_no"):
                        candidate["catalog_no"] = preview.get("catalog_no")
                    candidate["barcode"] = preview_barcode
                else:
                    if not candidate.get("label_name") and preview.get("label_name"):
                        candidate["label_name"] = preview.get("label_name")
                    if not candidate.get("catalog_no") and preview.get("catalog_no"):
                        candidate["catalog_no"] = preview.get("catalog_no")
        else:
            candidate["barcode"] = _clean_master_candidate_barcode(candidate.get("barcode"))
        out.append(candidate)
    return out


def get_album_master_variants(
    source: str,
    master_external_id: str,
    limit: int = 30,
    include_details: bool = False,
) -> list[dict[str, Any]]:
    source_u = (source or "").upper()
    if source_u == "DISCOGS":
        return get_discogs_master_variants(
            master_external_id=master_external_id,
            limit=limit,
            include_details=include_details,
        )
    if source_u == "MANIADB":
        return get_maniadb_master_variants(master_external_id=master_external_id, limit=limit)
    return []


def get_album_master_variants_page(
    source: str,
    master_external_id: str,
    page: int = 1,
    page_size: int = 30,
    catalog_no: str | None = None,
    barcode: str | None = None,
    include_details: bool = False,
) -> dict[str, Any]:
    source_u = (source or "").upper()
    page_n = max(1, int(page))
    page_size_n = max(1, min(int(page_size), 100))
    catalog_filter = str(catalog_no or "").strip()
    barcode_filter = str(barcode or "").strip()

    if source_u == "DISCOGS":
        return get_discogs_master_variants_page(
            master_external_id=master_external_id,
            page=page_n,
            page_size=page_size_n,
            catalog_no=catalog_filter or None,
            barcode=barcode_filter or None,
            include_details=include_details,
        )

    if source_u == "MANIADB":
        rows = get_maniadb_master_variants(master_external_id=master_external_id, limit=2000)
        filtered = rows
        if catalog_filter:
            filtered = [row for row in filtered if _catalog_match(row.get("catalog_no"), catalog_filter)]
        if barcode_filter:
            filtered = [row for row in filtered if _barcode_match(row.get("barcode"), barcode_filter)]
        total_count = len(filtered)
        offset = (page_n - 1) * page_size_n
        items = filtered[offset: offset + page_size_n]
        has_next = offset + page_size_n < total_count
        return {
            "items": items,
            "page": page_n,
            "page_size": page_size_n,
            "total_count": total_count,
            "has_next": has_next,
            "filtered": bool(catalog_filter or barcode_filter),
            "filter_catalog_no": catalog_filter or None,
            "filter_barcode": barcode_filter or None,
            "truncated": False,
        }

    return {
        "items": [],
        "page": page_n,
        "page_size": page_size_n,
        "total_count": 0,
        "has_next": False,
        "filtered": bool(catalog_filter or barcode_filter),
        "filter_catalog_no": catalog_filter or None,
        "filter_barcode": barcode_filter or None,
        "truncated": False,
    }


def _musicbrainz_search(query: str, limit: int = 5) -> list[Candidate]:
    settings = get_settings()
    headers = {"User-Agent": settings.musicbrainz_user_agent}

    with _make_http_client() as client:
        response = _get_with_retry(
            client,
            "https://musicbrainz.org/ws/2/release/",
            params={"query": query, "fmt": "json", "limit": limit},
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

    return _parse_musicbrainz_candidates(
        data,
        barcode=query.replace("barcode:", "", 1) if query.startswith("barcode:") else None,
        query=None if query.startswith("barcode:") else query,
    )


def _musicbrainz_cover_art_image_items(
    release_id: str,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    release_id_s = str(release_id or "").strip()
    if not release_id_s:
        return []
    settings = get_settings()
    headers = {"User-Agent": settings.musicbrainz_user_agent}
    own_client = client is None
    http_client = client or _make_http_client()

    def _fetch() -> httpx.Response:
        return _get_with_retry(
            http_client,
            f"https://coverartarchive.org/release/{quote(release_id_s)}",
            headers=headers,
        )

    try:
        data = cached_fetch_json(
            source_code="COVERARTARCHIVE",
            kind="release-images",
            identifier=release_id_s,
            fetcher=_fetch,
        )
    finally:
        if own_client:
            http_client.close()

    if not isinstance(data, dict):
        return []
    rows = data.get("images") or []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        uri = _pick_first_text(row.get("image"))
        if not uri or uri in seen:
            continue
        seen.add(uri)
        thumbs = row.get("thumbnails") if isinstance(row.get("thumbnails"), dict) else {}
        preview = (
            _pick_first_text(thumbs.get("250"))
            or _pick_first_text(thumbs.get("small"))
            or _pick_first_text(thumbs.get("500"))
            or uri
        )
        labels: list[str] = []
        if row.get("front"):
            labels.append("Front")
        if row.get("back"):
            labels.append("Back")
        for image_type in row.get("types") or []:
            text = _pick_first_text(image_type)
            if text and text not in labels:
                labels.append(text)
        out.append(
            {
                "type": " / ".join(labels) or f"Image {len(out) + 1}",
                "uri": uri,
                "uri150": preview,
            }
        )
    return out


def _fetch_musicbrainz_release_snapshot(
    release_id: str,
    client: httpx.Client | None = None,
) -> dict[str, Any] | None:
    release_id_s = str(release_id or "").strip()
    if not release_id_s:
        return None
    settings = get_settings()
    headers = {"User-Agent": settings.musicbrainz_user_agent}
    own_client = client is None
    http_client = client or _make_http_client()

    def _fetch() -> httpx.Response:
        return _get_with_retry(
            http_client,
            f"https://musicbrainz.org/ws/2/release/{quote(release_id_s)}",
            params={"fmt": "json", "inc": "release-groups+artists+labels+recordings+media"},
            headers=headers,
        )

    try:
        raw_detail = cached_fetch_json(
            source_code="MUSICBRAINZ",
            kind="release",
            identifier=release_id_s,
            fetcher=_fetch,
        )
    finally:
        if own_client:
            http_client.close()

    if not isinstance(raw_detail, dict):
        return None

    title = _pick_first_text(raw_detail.get("title"))
    artist_name = None
    artists = raw_detail.get("artist-credit")
    if isinstance(artists, list) and artists:
        first = artists[0] or {}
        artist_obj = first.get("artist") if isinstance(first, dict) else None
        if isinstance(artist_obj, dict):
            artist_name = _pick_first_text(artist_obj.get("name"))

    label_name = None
    catalog_no = None
    label_items: list[dict[str, Any]] = []
    for row in raw_detail.get("label-info") or []:
        if not isinstance(row, dict):
            continue
        label_obj = row.get("label") if isinstance(row.get("label"), dict) else {}
        row_label = _pick_first_text(label_obj.get("name"))
        row_catalog = _normalize_catalog_no(row.get("catalog-number"))
        if row_label and not label_name:
            label_name = row_label
        if row_catalog and not catalog_no:
            catalog_no = row_catalog
        if row_label or row_catalog:
            label_items.append({"name": row_label, "catalog_no": row_catalog})

    media_rows = raw_detail.get("media") or []
    first_media = media_rows[0] if isinstance(media_rows, list) and media_rows else {}
    format_name = _infer_format_from_text(_pick_first_text(first_media.get("format")) if isinstance(first_media, dict) else None)
    track_list: list[str] = []
    track_items: list[dict[str, Any]] = []
    for medium_index, media_row in enumerate(media_rows, start=1):
        if not isinstance(media_row, dict):
            continue
        for track_index, track_row in enumerate(media_row.get("tracks") or [], start=1):
            if not isinstance(track_row, dict):
                continue
            recording = track_row.get("recording") if isinstance(track_row.get("recording"), dict) else {}
            track_title = _pick_first_text(track_row.get("title")) or _pick_first_text(recording.get("title"))
            if not track_title:
                continue
            track_no = _pick_first_text(track_row.get("number")) or str(track_index)
            track_list.append(track_title)
            track_items.append({"disc": medium_index, "position": track_no, "title": track_title})

    image_items = _musicbrainz_cover_art_image_items(release_id_s, client=http_client if not own_client else None)
    cover_image_url = None
    for image in image_items:
        image_type = str(image.get("type") or "").lower()
        if "front" in image_type:
            cover_image_url = _pick_first_text(image.get("uri"))
            break
    if not cover_image_url and image_items:
        cover_image_url = _pick_first_text(image_items[0].get("uri"))

    date_text = _pick_first_text(raw_detail.get("date"))
    release_year = _safe_year(date_text.split("-", 1)[0] if date_text else None)
    country = _pick_first_text(raw_detail.get("country"))

    return {
        "cover_image_url": cover_image_url,
        "track_list": track_list,
        "label_name": label_name,
        "catalog_no": catalog_no,
        "barcode": _pick_first_text(raw_detail.get("barcode")),
        "format_name": format_name,
        "media_type": format_name,
        "release_type": None,
        "domain_code": infer_domain_code(
            country=country,
            artist_or_brand=artist_name,
            title=title,
            label_name=label_name,
            source="MUSICBRAINZ",
        ),
        "genres": [],
        "styles": [],
        "artist_or_brand": artist_name,
        "release_year": release_year,
        "released_date": date_text,
        "disc_count": len(media_rows) or None,
        "speed_rpm": None,
        "has_obi": None,
        "runout_matrix": [],
        "pressing_country": country,
        "source_notes": None,
        "credits": [],
        "identifier_items": [],
        "image_items": image_items,
        "company_items": [],
        "series": [],
        "format_items": [],
        "track_items": track_items,
        "label_items": label_items,
        "raw": raw_detail,
    }


def _enrich_musicbrainz_candidates(candidates: list[Candidate], max_items: int = 3) -> None:
    slice_size = max(0, min(len(candidates), max_items))
    if slice_size == 0:
        return
    with _make_http_client() as client:
        for candidate in candidates[:slice_size]:
            detail = _fetch_musicbrainz_release_snapshot(candidate.external_id, client=client)
            if not detail:
                continue
            candidate.cover_image_url = detail.get("cover_image_url") or candidate.cover_image_url
            candidate.image_items = detail.get("image_items") or candidate.image_items
            candidate.track_list = detail.get("track_list") or candidate.track_list
            candidate.label_name = detail.get("label_name") or candidate.label_name
            candidate.catalog_no = detail.get("catalog_no") or candidate.catalog_no
            candidate.barcode = detail.get("barcode") or candidate.barcode
            candidate.format_name = detail.get("format_name") or candidate.format_name
            candidate.media_type = detail.get("media_type") or candidate.media_type
            candidate.release_year = detail.get("release_year") or candidate.release_year
            candidate.raw["detail"] = detail.get("raw")


def search_musicbrainz_by_barcode(barcode: str, limit: int = 5) -> list[dict[str, Any]]:
    try:
        candidates = _musicbrainz_search(f"barcode:{barcode}", limit=limit)
    except httpx.HTTPError as exc:
        logger.warning("musicbrainz barcode search %r failed: %s", barcode, exc)
        return []
    _enrich_musicbrainz_candidates(candidates, max_items=min(limit, 3))
    return [c.to_dict() for c in candidates]


def search_musicbrainz_by_query(query: str, limit: int = 5) -> list[dict[str, Any]]:
    try:
        candidates = _musicbrainz_search(query, limit=limit)
    except httpx.HTTPError as exc:
        logger.warning("musicbrainz query search %r failed: %s", query, exc)
        return []
    _enrich_musicbrainz_candidates(candidates, max_items=min(limit, 3))
    return [c.to_dict() for c in candidates]


def search_music_metadata(
    barcode: str | None = None,
    query: str | None = None,
    category: str | None = None,
    source: str = "AUTO",
    limit: int = 5,
    artist_or_brand: str | None = None,
    title: str | None = None,
) -> list[dict[str, Any]]:
    """
    Provider priority:
      media: DISCOGS 중심, KR 보강 MANIADB/ALADIN, fallback MUSICBRAINZ
      Others: DISCOGS -> MUSICBRAINZ (+ KR query MANIADB/ALADIN)
    """
    candidates: list[dict[str, Any]] = []
    source_u = (source or "AUTO").upper()
    category_u = (category or "").upper()
    is_media = category_u in {"LP", "CD", "CASSETTE", "8TRACK", "DIGITAL", "REEL_TO_REEL"}
    has_korean_query = bool(query and re.search(r"[가-힣]", query))

    if source_u == "DISCOGS":
        if barcode:
            return search_discogs_by_barcode(barcode, limit=limit)[: max(1, limit)]
        if query:
            discogs = search_discogs_by_query(query, limit=limit)
            if discogs or not (artist_or_brand or title):
                return discogs[: max(1, limit)]
            return _search_discogs_release_with_artist_variations(
                query=query,
                artist_or_brand=artist_or_brand,
                title=title,
                limit=limit,
            )[: max(1, limit)]
        return []
    if source_u == "ALADIN":
        if barcode:
            return search_aladin_by_barcode(barcode, limit=limit)[: max(1, limit)]
        if query:
            return search_aladin_by_query(query, limit=limit)[: max(1, limit)]
        return []
    if source_u == "MANIADB":
        if barcode:
            return search_maniadb_by_query(barcode, limit=limit)[: max(1, limit)]
        if query:
            return search_maniadb_by_query(query, limit=limit)[: max(1, limit)]
        return []
    if source_u == "MUSICBRAINZ":
        if barcode:
            return search_musicbrainz_by_barcode(barcode, limit=limit)[: max(1, limit)]
        if query:
            return search_musicbrainz_by_query(query, limit=limit)[: max(1, limit)]
        return []
    if barcode:
        discogs = search_discogs_by_barcode(barcode, limit=limit)
        if discogs:
            candidates.extend(discogs)
        else:
            aladin = search_aladin_by_barcode(barcode, limit=limit)
            if aladin:
                candidates.extend(aladin)
    elif query:
        discogs: list[dict[str, Any]] = search_discogs_by_query(query, limit=limit)
        if not discogs and (artist_or_brand or title):
            discogs = _search_discogs_release_with_artist_variations(
                query=query,
                artist_or_brand=artist_or_brand,
                title=title,
                limit=limit,
            )
        if discogs:
            candidates.extend(discogs)
        if has_korean_query:
            maniadb = search_maniadb_by_query(query, limit=max(1, limit // 2 if discogs else limit))
            candidates.extend(maniadb)
            candidates.extend(search_aladin_by_query(query, limit=max(1, limit // 2)))

    # De-dup by source/external_id while keeping best confidence.
    dedup: dict[tuple[str, str], dict[str, Any]] = {}
    for c in candidates:
        key = (str(c.get("source")), str(c.get("external_id")))
        if key not in dedup or float(c.get("confidence", 0)) > float(dedup[key].get("confidence", 0)):
            dedup[key] = c

    merged = sorted(dedup.values(), key=lambda x: float(x.get("confidence", 0)), reverse=True)
    return merged[: max(1, limit)]


def _try_discogs_for_catalog_no(
    catalog_no: str,
    artist: str | None,
    title: str | None,
    format_name: str | None = None,
    pressing_country: str | None = None,
) -> dict[str, Any] | None:
    """카탈로그넘버 + 아티스트 + 앨범명으로 Discogs 검색 (바코드 없을 때 fallback).

    매칭 기준:
    - 카탈로그넘버 정규화(하이픈·공백 제거) 일치
    - 아티스트+앨범명 토큰 유사도 >= 0.85
    - 미디어 타입/발매국가: 같은 카탈로그넘버가 여러 포맷에 걸쳐 존재할 수 있으므로
      hard filter 대신 preference로 활용 (일치하면 우선 선택)
    """
    if not catalog_no:
        return None
    cat_norm = catalog_no.replace("-", "").replace(" ", "").upper()
    if not cat_norm:
        return None

    headers = _discogs_headers()
    if not headers:
        return None

    orig_text = f"{artist or ''} {title or ''}".strip()
    if not orig_text:
        return None

    try:
        candidates = _discogs_search({"catno": catalog_no, "type": "release", "per_page": 5})
        if not candidates:
            return None

        best_match = None
        best_score = -1.0

        for candidate in candidates:
            cand_cat = (candidate.catno or "").replace("-", "").replace(" ", "").upper()
            if cand_cat != cat_norm:
                continue

            disc_text = f"{candidate.artist_or_brand or ''} {candidate.title or ''}".strip()
            sim = _token_similarity(orig_text, disc_text) if disc_text else 0.0
            if sim < 0.85:
                continue

            ext = str(candidate.external_id or "").strip()
            if not ext:
                continue

            with _make_http_client() as client:
                detail = _fetch_discogs_release_detail(ext, headers=headers, client=client)
            if not detail:
                continue

            # preference 점수: 미디어·국가 일치 시 가산
            score = sim
            if format_name:
                disc_fmt = (detail.get("format_name") or "").upper()
                if disc_fmt and disc_fmt == format_name.upper():
                    score += 0.1
            if pressing_country:
                disc_country = (detail.get("pressing_country") or "").upper()
                if disc_country and disc_country == pressing_country.upper():
                    score += 0.05

            if score > best_score:
                best_score = score
                raw_detail = detail.get("raw_detail") if isinstance(detail.get("raw_detail"), dict) else {}
                artist_or_brand: str | None = None
                artists = raw_detail.get("artists")
                if isinstance(artists, list) and artists:
                    first = artists[0]
                    if isinstance(first, dict):
                        artist_or_brand = (
                            _pick_first_text(first.get("anv")) or _pick_first_text(first.get("name"))
                        )
                best_match = {
                    "external_id": ext,
                    "master_id": _discogs_master_id_from_release(raw_detail),
                    "title": candidate.title or raw_detail.get("title"),
                    "artist_or_brand": artist_or_brand or candidate.artist_or_brand,
                    "release_year": _safe_year(raw_detail.get("year")),
                    "released_date": detail.get("released_date"),
                    "cover_image_url": detail.get("cover_image_url"),
                    "label_name": detail.get("label_name"),
                    "catalog_no": detail.get("catalog_no"),
                    "barcode": detail.get("barcode"),
                    "format_name": detail.get("format_name"),
                    "domain_code": detail.get("domain_code"),
                    "genres": detail.get("genres") or [],
                    "styles": detail.get("styles") or [],
                    "disc_count": detail.get("disc_count"),
                    "speed_rpm": detail.get("speed_rpm"),
                    "has_obi": detail.get("has_obi"),
                    "runout_matrix": detail.get("runout_matrix") or [],
                    "pressing_country": detail.get("pressing_country"),
                    "source_notes": None,
                    "credits": detail.get("credits") or [],
                    "identifier_items": detail.get("identifier_items") or [],
                    "image_items": detail.get("image_items") or [],
                    "company_items": detail.get("company_items") or [],
                    "series": detail.get("series") or [],
                    "format_items": detail.get("format_items") or [],
                    "track_items": detail.get("track_items") or [],
                    "track_list": detail.get("track_list") or [],
                    "label_items": detail.get("label_items") or [],
                    "raw": raw_detail,
                }

        return best_match
    except Exception as e:
        logger.warning("_try_discogs_for_catalog_no error: %s", e)
        return None


def _try_discogs_for_barcode(barcode: str) -> dict[str, Any] | None:
    """바코드로 Discogs 릴리즈를 조회. 매칭 시 external_id·master_id 포함 핵심 필드 반환.

    EAN-13(13자리), UPC-A(12자리), EAN-8(8자리) 이상인 경우에만 검색.
    한국 음반(880 prefix) 등 Discogs에 없는 경우 None 반환.
    """
    if not barcode:
        return None
    # EAN-13(13자리) 또는 UPC-A(12자리) 체크섬 검증
    barcode_digits = barcode.replace(" ", "").replace("-", "")
    if not _validate_barcode_checksum(barcode_digits):
        return None
    headers = _discogs_headers()
    if not headers:
        return None
    try:
        candidates = _discogs_search({"barcode": barcode, "type": "release", "per_page": 3})
        if not candidates:
            return None
        best = candidates[0]
        ext = str(best.external_id or "").strip()
        if not ext:
            return None
        with _make_http_client() as client:
            detail = _fetch_discogs_release_detail(ext, headers=headers, client=client)
        if not detail:
            return None
        raw_detail = detail.get("raw_detail") if isinstance(detail.get("raw_detail"), dict) else {}
        artist_or_brand: str | None = None
        artists = raw_detail.get("artists")
        if isinstance(artists, list) and artists:
            first = artists[0]
            if isinstance(first, dict):
                artist_or_brand = (
                    _pick_first_text(first.get("anv")) or _pick_first_text(first.get("name"))
                )
        return {
            "external_id": ext,
            "master_id": _discogs_master_id_from_release(raw_detail),
            "title": best.title or raw_detail.get("title"),
            "artist_or_brand": artist_or_brand or best.artist_or_brand,
            "release_year": _safe_year(raw_detail.get("year")),
            "released_date": detail.get("released_date"),
            "cover_image_url": detail.get("cover_image_url"),
            "label_name": detail.get("label_name"),
            "catalog_no": detail.get("catalog_no"),
            "barcode": detail.get("barcode"),
            "format_name": detail.get("format_name"),
            "domain_code": detail.get("domain_code"),
            "genres": detail.get("genres") or [],
            "styles": detail.get("styles") or [],
            "disc_count": detail.get("disc_count"),
            "speed_rpm": detail.get("speed_rpm"),
            "has_obi": detail.get("has_obi"),
            "runout_matrix": detail.get("runout_matrix") or [],
            "pressing_country": detail.get("pressing_country"),
            "credits": detail.get("credits") or [],
            "identifier_items": detail.get("identifier_items") or [],
            "image_items": detail.get("image_items") or [],
            "company_items": detail.get("company_items") or [],
            "series": detail.get("series") or [],
            "format_items": detail.get("format_items") or [],
            "track_items": detail.get("track_items") or [],
            "track_list": detail.get("track_list") or [],
            "label_items": detail.get("label_items") or [],
            "raw": raw_detail,
        }
    except Exception as exc:
        logger.warning("Discogs barcode lookup failed (barcode=%s): %s", barcode, exc)
        return None


def get_discogs_snapshot_from_master_id(master_id: str) -> dict[str, Any] | None:
    """Discogs master ID → main_release snapshot (Discogs-exclusive fields only).

    ManiaDB 소스 아이템처럼 Discogs release ID를 직접 갖지 않는 경우,
    AlbumMaster의 Discogs master ID로 main_release를 조회해
    format_items, runout_matrix, identifier_items, pressing_country 등
    Discogs만 제공하는 부가 정보를 보강할 때 사용한다.
    """
    master_id_s = str(master_id or "").strip()
    if not master_id_s:
        return None
    headers = _discogs_headers()
    if headers is None:
        return None
    try:
        with _make_http_client() as client:
            # master 직접 조회해 main_release_id 추출
            master_resp = _get_with_retry(
                client, f"https://api.discogs.com/masters/{master_id_s}", headers=headers
            )
            master_resp.raise_for_status()
            master_data = master_resp.json()
            if not isinstance(master_data, dict):
                return None
            main_release_id = str(master_data.get("main_release") or "").strip()
            if not main_release_id:
                return None
            detail = _fetch_discogs_release_detail(
                main_release_id,
                headers=headers,
                client=client,
                master_cache={},
            )
    except httpx.HTTPError:
        return None
    if not detail:
        return None
    # Discogs 전용 필드만 반환 — 아티스트·발매일·레이블 등 ManiaDB가 이미
    # 채운 기본 필드는 덮어쓰지 않도록 None으로 채운다.
    return {
        "cover_image_url": None,
        "track_list": [],
        "label_name": None,
        "catalog_no": None,
        "barcode": None,
        "format_name": None,
        "media_type": None,
        "release_type": None,
        "domain_code": None,
        "genres": [],
        "styles": [],
        "artist_or_brand": None,
        "release_year": None,
        "released_date": None,
        "disc_count": detail.get("disc_count"),
        "speed_rpm": detail.get("speed_rpm"),
        "has_obi": detail.get("has_obi"),
        "runout_matrix": detail.get("runout_matrix") or [],
        "pressing_country": detail.get("pressing_country"),
        "source_notes": detail.get("source_notes"),
        "credits": detail.get("credits") or [],
        "identifier_items": detail.get("identifier_items") or [],
        "image_items": detail.get("image_items") or [],
        "company_items": detail.get("company_items") or [],
        "series": detail.get("series") or [],
        "format_items": detail.get("format_items") or [],
        "track_items": detail.get("track_items") or [],
        "label_items": detail.get("label_items") or [],
    }


def get_source_release_snapshot(source: str, external_id: str) -> dict[str, Any] | None:
    source_u = str(source or "").strip().upper()
    ext = str(external_id or "").strip()
    if not source_u or not ext:
        return None

    if source_u == "DISCOGS":
        headers = _discogs_headers()
        if headers is None:
            return None
        try:
            master_cache: dict[str, dict[str, Any] | None] = {}
            with _make_http_client() as client:
                detail = _fetch_discogs_release_detail(
                    ext,
                    headers=headers,
                    client=client,
                    master_cache=master_cache,
                )
        except httpx.HTTPError:
            return None
        if not detail:
            return None
        raw_detail = detail.get("raw_detail") if isinstance(detail.get("raw_detail"), dict) else {}
        artist_or_brand = None
        artists = raw_detail.get("artists")
        if isinstance(artists, list) and artists:
            first = artists[0]
            if isinstance(first, dict):
                artist_or_brand = _pick_first_text(first.get("anv")) or _pick_first_text(first.get("name"))
        release_year = _safe_year(raw_detail.get("year"))
        return {
            "cover_image_url": detail.get("cover_image_url"),
            "track_list": detail.get("track_list") or [],
            "label_name": detail.get("label_name"),
            "catalog_no": detail.get("catalog_no"),
            "barcode": detail.get("barcode"),
            "format_name": detail.get("format_name"),
            "media_type": detail.get("media_type"),
            "release_type": detail.get("release_type"),
            "domain_code": detail.get("domain_code"),
            "genres": detail.get("genres") or [],
            "styles": detail.get("styles") or [],
            "artist_or_brand": artist_or_brand,
            "release_year": release_year,
            "released_date": detail.get("released_date"),
            "disc_count": detail.get("disc_count"),
            "speed_rpm": detail.get("speed_rpm"),
            "has_obi": detail.get("has_obi"),
            "runout_matrix": detail.get("runout_matrix") or [],
            "pressing_country": detail.get("pressing_country"),
            "source_notes": detail.get("source_notes"),
            "credits": detail.get("credits") or [],
            "identifier_items": detail.get("identifier_items") or [],
            "image_items": detail.get("image_items") or [],
            "company_items": detail.get("company_items") or [],
            "series": detail.get("series") or [],
            "format_items": detail.get("format_items") or [],
            "track_items": detail.get("track_items") or [],
            "label_items": detail.get("label_items") or [],
            "raw": detail.get("raw_detail"),
        }

    if source_u == "MANIADB":
        album_id = _extract_maniadb_album_id(ext)
        if not album_id:
            return None
        variants = get_maniadb_master_variants(master_external_id=album_id, limit=30)
        if not variants:
            return None
        target = next((v for v in variants if str(v.get("external_id") or "") == ext), variants[0])
        return {
            "cover_image_url": target.get("cover_image_url"),
            "track_list": target.get("track_list") or [],
            "label_name": target.get("label_name"),
            "catalog_no": target.get("catalog_no"),
            "barcode": target.get("barcode"),
            "format_name": target.get("format_name"),
            "media_type": target.get("media_type"),
            "release_type": target.get("release_type"),
            "domain_code": target.get("domain_code") or "KOREA",
            "genres": target.get("genres") or [],
            "styles": target.get("styles") or [],
            "artist_or_brand": target.get("artist_or_brand"),
            "release_year": target.get("release_year"),
            "released_date": target.get("released_date"),
            "disc_count": None,
            "speed_rpm": None,
            "has_obi": None,
            "runout_matrix": [],
            "pressing_country": None,
            "source_notes": None,
            "credits": [],
            "identifier_items": [],
            "image_items": target.get("image_items") or [],
            "company_items": [],
            "series": [],
            "format_items": [],
            "track_items": [],
            "label_items": [],
            "raw": target.get("raw"),
        }

    if source_u == "MUSICBRAINZ":
        return _fetch_musicbrainz_release_snapshot(ext)

    if source_u == "ALADIN":
        detail = _fetch_aladin_item_detail(ext)
        if not detail:
            return None
        raw_title = str(detail.get("title") or "")
        raw_artist = str(detail.get("author") or "") or None
        title = _clean_aladin_title(raw_title)
        artist = _clean_aladin_artist(raw_artist) if raw_artist else None
        title, promo_notice = _extract_aladin_promo_notice(title)
        if artist and title:
            for sep in (" - ", " – ", " — ", " / "):
                if title.lower().startswith((artist + sep).lower()):
                    stripped = title[len(artist) + len(sep):].strip()
                    if stripped:
                        title = stripped
                    break
        barcode = str(detail.get("isbn13") or detail.get("isbn") or "") or None
        discogs_crossref = _try_discogs_for_barcode(barcode) if barcode else None
        pub_date = str(detail.get("pubDate") or "")
        year_token = pub_date.split("-")[0] if pub_date else None
        raw_cover = str(detail.get("cover") or "") or None
        cover_image_url = raw_cover.replace("/coversum/", "/cover/") if raw_cover else None
        format_name = (
            _extract_format_from_aladin_title(raw_title)
            or _infer_format_from_aladin_category(detail.get("categoryName"))
        )
        # 웹 스크래핑(getContents.aspx Introduce) → TTB API subInfo.trackList 순서로 시도
        isbn_code = str(detail.get("isbn") or "").strip()
        track_items = (
            _fetch_aladin_tracks_from_web(ext, isbn_code)
            if isbn_code
            else []
        )
        if not track_items:
            subinfo = detail.get("subInfo") if isinstance(detail.get("subInfo"), dict) else {}
            track_items = _parse_aladin_track_items(subinfo)
        return {
            "cover_image_url": cover_image_url,
            "track_list": [t["title"] for t in track_items],
            "track_items": track_items,
            "label_name": str(detail.get("publisher") or "") or None,
            "catalog_no": None,
            "barcode": barcode,
            "format_name": format_name,
            "media_type": _format_name_to_media_type(format_name),
            "release_type": None,
            "domain_code": infer_domain_code(
                country="KR",
                artist_or_brand=artist,
                title=title,
                label_name=detail.get("publisher"),
                source="ALADIN",
            ),
            "genres": [],
            "styles": [],
            "artist_or_brand": artist,
            "release_year": _safe_year(year_token),
            "released_date": pub_date if pub_date else None,
            "disc_count": None,
            "speed_rpm": None,
            "has_obi": None,
            "runout_matrix": [],
            "pressing_country": None,
            "source_notes": promo_notice,
            "credits": [],
            "identifier_items": [],
            "image_items": [],
            "company_items": [],
            "series": [],
            "format_items": [],
            "label_items": [],
            "title": title,
            "discogs_crossref": discogs_crossref,
            "raw": detail,
        }

    return None


def resolve_release_master_reference(source: str, external_id: str) -> dict[str, Any] | None:
    source_u = str(source or "").strip().upper()
    ext = str(external_id or "").strip()
    if not source_u or not ext:
        return None

    if source_u == "DISCOGS":
        headers = _discogs_headers()
        if headers is None:
            return None
        try:
            with _make_http_client() as client:
                started_at = time.perf_counter()
                detail = _fetch_discogs_release_detail(ext, headers=headers, client=client)
                elapsed = time.perf_counter() - started_at
                if elapsed >= PROVIDER_SLOW_SEC:
                    logger.warning(
                        "provider_slow source=DISCOGS op=release_detail elapsed=%.3fs release_id=%s",
                        elapsed,
                        ext,
                    )
        except httpx.HTTPError:
            return None
        if not detail:
            return None

        raw_detail = detail.get("raw_detail") if isinstance(detail.get("raw_detail"), dict) else {}
        master_id_raw = raw_detail.get("master_id")
        master_id = str(master_id_raw).strip() if master_id_raw is not None else ""
        if not master_id:
            master_url = _pick_first_text(raw_detail.get("master_url"))
            if master_url:
                m = re.search(r"/masters/(\d+)", master_url)
                if m:
                    master_id = str(m.group(1))
        if not master_id:
            master_id = str(detail.get("master_external_id") or "").strip()
        if not master_id:
            return None

        artist_name = None
        artists = raw_detail.get("artists")
        if isinstance(artists, list) and artists:
            first = artists[0]
            if isinstance(first, dict):
                artist_name = _pick_first_text(first.get("anv")) or _pick_first_text(first.get("name"))

        release_year = None
        year_raw = raw_detail.get("year")
        try:
            release_year = int(year_raw) if year_raw is not None else None
        except (TypeError, ValueError):
            release_year = None

        return {
            "source": "DISCOGS",
            "master_external_id": master_id,
            "title": _pick_first_text(raw_detail.get("title")),
            "artist_or_brand": artist_name,
            "release_year": release_year,
        }

    if source_u == "MANIADB":
        album_id = _extract_maniadb_album_id(ext)
        if not album_id:
            return None
        title = None
        artist = None
        release_year = None
        variants = get_maniadb_master_variants(master_external_id=album_id, limit=1)
        if variants:
            first = variants[0]
            title = _pick_first_text(first.get("title"))
            artist = _pick_first_text(first.get("artist_or_brand"))
            year_raw = first.get("release_year")
            try:
                release_year = int(year_raw) if year_raw is not None else None
            except (TypeError, ValueError):
                release_year = None

        return {
            "source": "MANIADB",
            "master_external_id": album_id,
            "title": title,
            "artist_or_brand": artist,
            "release_year": release_year,
        }

    if source_u == "MUSICBRAINZ":
        settings = get_settings()
        headers = {"User-Agent": settings.musicbrainz_user_agent}
        try:
            with _make_http_client() as client:
                response = _get_with_retry(
                    client,
                    f"https://musicbrainz.org/ws/2/release/{quote(ext)}",
                    params={"fmt": "json", "inc": "release-groups+artists"},
                    headers=headers,
                )
                response.raise_for_status()
                raw_detail = response.json()
        except httpx.HTTPError:
            return None

        if not isinstance(raw_detail, dict):
            return None

        release_group = raw_detail.get("release-group")
        if not isinstance(release_group, dict):
            return None
        master_external_id = _pick_first_text(release_group.get("id"))
        if not master_external_id:
            return None

        artist_name = None
        artists = raw_detail.get("artist-credit")
        if isinstance(artists, list) and artists:
            first = artists[0] or {}
            artist_obj = first.get("artist") if isinstance(first, dict) else None
            if isinstance(artist_obj, dict):
                artist_name = _pick_first_text(artist_obj.get("name"))

        release_year = None
        year_raw = (raw_detail.get("date") or "").split("-")[0] if raw_detail.get("date") else None
        try:
            release_year = int(year_raw) if year_raw is not None else None
        except (TypeError, ValueError):
            release_year = None

        return {
            "source": "MUSICBRAINZ",
            "master_external_id": master_external_id,
            "title": _pick_first_text(release_group.get("title")) or _pick_first_text(raw_detail.get("title")),
            "artist_or_brand": artist_name,
            "release_year": release_year,
        }

    return None
