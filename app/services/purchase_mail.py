from __future__ import annotations

import base64
import os
import re
import secrets
from datetime import datetime
from email import policy as email_policy
from email.parser import BytesParser as EmailBytesParser
from email.parser import Parser as EmailParser
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException, Request

from .. import db
from ..config import get_settings
from ..db import DOMAIN_CODES, LABEL_PREFIX_BY_CATEGORY, LEGACY_DOMAIN_CODE_MAP
from ..schemas import (
    MusicDetailCreate,
    OwnedItemCreate,
    PurchaseImportCreateResponse,
    PurchaseImportPreviewItem,
    PurchaseImportPreviewRequest,
    PurchaseImportQueueItem,
    PurchaseImportWebhookRequest,
)
from ..services.providers import fetch_aladin_track_items

__all__ = [
    "_parse_price_number",
    "_parse_positive_int",
    "_normalize_purchase_date",
    "_purchase_message_from_raw_content",
    "_purchase_message_from_raw_bytes",
    "_resolve_purchase_import_vendor_code",
    "_extract_purchase_date_from_raw_content",
    "_resolve_purchase_import_purchase_date",
    "_split_artist_item_text",
    "_PURCHASE_CONDITION_TOKEN_PATTERN",
    "_normalize_purchase_condition_token",
    "_extract_purchase_condition_pair",
    "_strip_ebay_listing_search_suffix",
    "_parse_ebay_purchase_title",
    "_purchase_ebay_parse_source_text",
    "_purchase_queue_display_item_name",
    "_normalize_purchase_media_format",
    "_purchase_import_media_format_or_default",
    "_PurchaseMailTableParser",
    "_purchase_rows_from_html",
    "_purchase_rows_from_text",
    "_extract_html_from_mhtml",
    "_extract_html_from_mhtml_bytes",
    "_purchase_html_from_raw_content",
    "_decode_purchase_import_upload_bytes",
    "_purchase_html_from_upload_bytes",
    "_resolve_purchase_import_raw_input",
    "_purchase_compact_text",
    "_purchase_dense_text",
    "_purchase_normalize_item_url",
    "_purchase_currency_code",
    "_purchase_host_from_url",
    "_purchase_marketplace_currency",
    "_purchase_amazon_marketplace_from_raw_content",
    "_extract_purchase_price_from_text",
    "_extract_purchase_date_from_text",
    "_extract_purchase_total_from_text",
    "_build_purchase_preview_item_direct",
    "_purchase_amazon_asin_from_url",
    "_purchase_amazon_marketplace_from_url",
    "_purchase_fetch_item_page_html",
    "_purchase_extract_amazon_artist_name",
    "_purchase_normalize_amazon_detail_key",
    "_purchase_extract_amazon_detail_map",
    "_purchase_extract_amazon_detail_enrichment",
    "_purchase_extract_ebay_detail_enrichment",
    "_purchase_enrich_row_from_item_page",
    "_purchase_preview_items_from_amazon_html",
    "_purchase_preview_items_from_amazon_order_details_html",
    "_purchase_preview_items_from_ebay_html",
    "_purchase_import_empty_reason",
    "_build_purchase_preview_item",
    "_parse_purchase_import_preview",
    "_purchase_queue_item_from_row",
    "_purchase_import_webhook_allowed",
    "PURCHASE_IMPORT_WEBHOOK_MAX_BODY_BYTES",
    "_PURCHASE_IMPORT_WEBHOOK_ALLOWED_CONTENT_TYPES",
    "_purchase_import_webhook_validate_request",
    "_require_purchase_import_webhook_envelope",
    "_purchase_import_rows_for_save",
    "_purchase_queue_base_context",
    "_purchase_queue_memory_note",
    "_purchase_queue_candidate_query",
    "_build_owned_item_from_purchase_queue_row",
    "_purchase_import_duplicate_create_response",
]

MUSIC_CATEGORIES: frozenset[str] = frozenset({"LP", "CD", "CASSETTE", "8TRACK", "DIGITAL", "REEL_TO_REEL"})
RELEASE_TYPES: frozenset[str] = frozenset({"ALBUM", "EP", "SINGLE"})

PURCHASE_ITEM_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

PURCHASE_IMPORT_WEBHOOK_MAX_BODY_BYTES = int(
    os.getenv("LIBRARY_PURCHASE_IMPORT_WEBHOOK_MAX_BODY_BYTES", str(1 * 1024 * 1024))
)
_PURCHASE_IMPORT_WEBHOOK_ALLOWED_CONTENT_TYPES = ("application/json",)


def _clean_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _discogs_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _discogs_catalog_no(value: Any) -> str | None:
    text = _discogs_text(value)
    if not text:
        return None
    text = re.sub(r"^(?:cat\s*#?\s*:?)\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^[\s;:,/|]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text or text in {"-", "--", "---"}:
        return None
    return text


def _normalize_domain_code(value: Any) -> str | None:
    code = str(value or "").strip().upper()
    if not code:
        return None
    code = LEGACY_DOMAIN_CODE_MAP.get(code, code)
    return code if code in DOMAIN_CODES else None


def _build_label_id(category: str, owned_item_id: int) -> str:
    prefix = LABEL_PREFIX_BY_CATEGORY.get(category, "IT")
    return f"{prefix}-{owned_item_id:06d}"


def _normalize_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value) if value is not None and str(value).strip() else None
    except (TypeError, ValueError):
        parsed = None
    if parsed is not None and parsed <= 0:
        parsed = None
    return parsed


def _parse_price_number(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = re.sub(r"[^0-9.,-]", "", text)
    normalized = normalized.replace(",", "")
    if normalized in {"", "-", ".", "-."}:
        return None
    try:
        return float(normalized)
    except ValueError:
        return None


def _parse_positive_int(value: Any, default: int = 1) -> int:
    text = str(value or "").strip()
    if not text:
        return default
    digits = re.sub(r"[^0-9]", "", text)
    if not digits:
        return default
    try:
        parsed = int(digits)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _normalize_purchase_date(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    compact = text.replace(".", "-").replace("/", "-")
    if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", compact):
        y, m, d = compact.split("-")
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    for fmt in ("%B %d, %Y", "%d %B %Y", "%b %d, %Y", "%d %b %Y"):
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return parsed.strftime("%Y-%m-%d")
    return text


def _purchase_message_from_raw_content(raw_content: str):
    raw = str(raw_content or "").strip()
    if not raw:
        return None
    try:
        return EmailParser(policy=email_policy.default).parsestr(raw)
    except Exception:
        return None


def _purchase_message_from_raw_bytes(raw_content: bytes):
    raw = bytes(raw_content or b"").strip()
    if not raw:
        return None
    try:
        return EmailBytesParser(policy=email_policy.default).parsebytes(raw)
    except Exception:
        return None


def _resolve_purchase_import_vendor_code(
    vendor_code: Any = None,
    *,
    raw_content: str | None = None,
    items: list[Any] | None = None,
) -> str:
    explicit = str(vendor_code or "").strip().upper()
    if explicit and explicit != "OTHER":
        return explicit
    for item in items or []:
        payload = getattr(item, "raw_payload", None)
        if not isinstance(payload, dict):
            payload = item.get("raw_payload") if isinstance(item, dict) else None
        candidate = str((payload or {}).get("vendor_code") or "").strip().upper()
        if candidate and candidate != "OTHER":
            return candidate
    text = str(raw_content or "")
    upper = text.upper()
    has_ebay_marker = any(
        marker in upper
        for marker in (
            "EBAY.COM/MYE/MYEBAY/PURCHASE",
            "MY EBAY",
            "M-ITEM-CARD",
            "MODULE_PROVIDER",
        )
    )
    has_amazon_marker = "AMAZON." in upper and any(
        marker in upper
        for marker in (
            "ORDER-CARD",
            "ORDER PLACED",
            "YOUR ORDERS",
        )
    )
    if "__VENDOR_EMAIL__" in upper or "세일뮤직" in text:
        return "SAILMUSIC"
    if has_ebay_marker:
        return "EBAY"
    if has_amazon_marker:
        return "AMAZON"
    if "AMAZON." in upper:
        return "AMAZON"
    if "EBAY.COM" in upper:
        return "EBAY"
    return "OTHER"


def _extract_purchase_date_from_raw_content(raw_content: str, purchase_date: Any = None) -> str | None:
    normalized = _normalize_purchase_date(purchase_date)
    if normalized:
        return normalized
    candidates = [str(raw_content or "").strip()]
    html_content = _purchase_html_from_raw_content(str(raw_content or ""))
    if html_content:
        candidates.append(html_content)
    for candidate in candidates:
        parsed = _extract_purchase_date_from_text(candidate)
        if parsed:
            return parsed
        match = re.search(r"\b(20\d{2})[./-]\s*(\d{1,2})[./-]\s*(\d{1,2})\b", candidate)
        if match:
            return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    msg = _purchase_message_from_raw_content(str(raw_content or ""))
    if msg:
        header_date = str(msg.get("Date") or "").strip()
        if header_date:
            try:
                parsed = parsedate_to_datetime(header_date)
            except Exception:
                parsed = None
            if parsed is not None:
                return parsed.strftime("%Y-%m-%d")
    return None


def _resolve_purchase_import_purchase_date(purchase_date: Any = None, *, raw_content: str | None = None, items: list[Any] | None = None) -> str | None:
    normalized = _normalize_purchase_date(purchase_date)
    if normalized:
        return normalized
    for item in items or []:
        item_purchase_date = getattr(item, "purchase_date", None)
        if item_purchase_date is None and isinstance(item, dict):
            item_purchase_date = item.get("purchase_date")
        normalized_item = _normalize_purchase_date(item_purchase_date)
        if normalized_item:
            return normalized_item
    return _extract_purchase_date_from_raw_content(str(raw_content or ""))


def _split_artist_item_text(value: Any) -> tuple[str | None, str | None]:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" /")
    if not text:
        return None, None
    for separator in (" / ", "／", "/"):
        if separator in text:
            left, right = text.split(separator, 1)
            artist_name = _clean_text(left)
            item_name = _clean_text(right)
            if artist_name and item_name:
                return artist_name, item_name
    return None, text


_PURCHASE_CONDITION_TOKEN_PATTERN = r"(?:M-|M|NM-|NM|EX|VG\+|VG|G\+|G|F|P)"


def _normalize_purchase_condition_token(value: Any) -> str | None:
    token = _purchase_compact_text(value).upper().replace(" ", "")
    if token == "E":
        token = "EX"
    if token in {"M-", "M", "NM-", "NM", "EX", "VG+", "VG", "G+", "G", "F", "P"}:
        return token
    return None


def _extract_purchase_condition_pair(value: Any) -> tuple[str | None, str | None, str]:
    text = _purchase_compact_text(value)
    if not text:
        return None, None, ""
    match = re.search(
        rf"(?:^|\s)(?P<cover>{_PURCHASE_CONDITION_TOKEN_PATTERN})\s*/\s*(?P<disc>{_PURCHASE_CONDITION_TOKEN_PATTERN})\s*$",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None, None, text
    cover = _normalize_purchase_condition_token(match.group("cover"))
    disc = _normalize_purchase_condition_token(match.group("disc"))
    if not cover or not disc:
        return None, None, text
    stripped = text[: match.start()].strip(" -/|,")
    return cover, disc, stripped


def _strip_ebay_listing_search_suffix(value: Any) -> str:
    text = _purchase_compact_text(value)
    if not text:
        return ""
    text = re.sub(
        r"\s+(?:ORIG(?:INAL)?\.?|1ST|FIRST|PRESS(?:ING)?|PROMO|REISSUE|VINYL|RECORDS?|REC\.?|LP|LPS|ALBUM|EP|SINGLE|12\"|10\"|7\"|45RPM|33RPM|RPM|MONO|STEREO|GOLD\s+REC\.?|COLOR\s+VINYL|COLOUR\s+VINYL)\b.*$",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return text.strip(" -/|,")


def _parse_ebay_purchase_title(value: Any) -> tuple[str | None, str | None, str | None, str | None]:
    text = _purchase_compact_text(value)
    if not text:
        return None, None, None, None
    cover_condition, disc_condition, stripped_text = _extract_purchase_condition_pair(text)
    working_text = stripped_text or text
    artist_name: str | None = None
    item_name = working_text
    match = re.match(r"(?P<artist>.+?)\s[-–—]\s(?P<title>.+)$", working_text)
    if match:
        artist_name = _clean_text(match.group("artist"))
        item_name = _clean_text(match.group("title")) or working_text
    else:
        quoted_match = re.match(r'(?P<artist>.+?)\s*[""](?P<title>[^""]+)[""](?P<suffix>.*)$', working_text)
        if quoted_match:
            artist_name = _clean_text(quoted_match.group("artist"))
            suffix = _clean_text(quoted_match.group("suffix"))
            title_core = _clean_text(quoted_match.group("title"))
            item_name = _clean_text(" ".join(part for part in (title_core, suffix) if part)) or working_text
    item_name = _strip_ebay_listing_search_suffix(item_name) or _clean_text(item_name)
    return artist_name, item_name, cover_condition, disc_condition


def _purchase_ebay_parse_source_text(row: dict[str, Any], raw_payload: dict[str, Any] | None = None) -> str:
    payload = raw_payload if isinstance(raw_payload, dict) else dict(row.get("raw_payload") or {})
    listing_title = _clean_text(payload.get("listing_title"))
    item_name = _clean_text(row.get("item_name"))
    raw_line = _clean_text(row.get("raw_line"))
    return listing_title or item_name or raw_line


def _purchase_queue_display_item_name(row: dict[str, Any], raw_payload: dict[str, Any] | None = None) -> str:
    payload = raw_payload if isinstance(raw_payload, dict) else dict(row.get("raw_payload") or {})
    vendor_code = str(row.get("vendor_code") or payload.get("vendor_code") or "").strip().upper()
    listing_title = _clean_text(payload.get("listing_title"))
    item_name = _clean_text(row.get("item_name"))
    if vendor_code == "EBAY":
        return listing_title or item_name
    return item_name


def _normalize_purchase_media_format(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip().upper()
    if not text:
        return None
    if (
        "VINYL" in text
        or re.search(r"(?<![A-Z0-9])(?:LP|LPS|LP'S)(?![A-Z0-9])", text)
        or re.search(r"(?<![A-Z0-9])(?:12|10|7)\s*\"", text)
    ):
        return "LP"
    if "COMPACT DISC" in text or re.search(r"(?<![A-Z0-9])CDS?(?![A-Z0-9])", text):
        return "CD"
    if "CASSETTE" in text or re.search(r"(?<![A-Z0-9])(?:MC|TAPE|TAPES)(?![A-Z0-9])", text):
        return "CASSETTE"
    if "8-TRACK" in text or "8 TRACK" in text or "8TRACK" in text:
        return "8TRACK"
    if "DIGITAL" in text or "DOWNLOAD" in text or "FILE" in text:
        return "DIGITAL"
    if "REEL" in text:
        return "REEL_TO_REEL"
    return None


def _purchase_import_media_format_or_default(vendor_code: Any, value: Any) -> str | None:
    normalized = _normalize_purchase_media_format(value)
    if normalized:
        return normalized
    cleaned = _clean_text(value)
    if cleaned:
        return cleaned
    vendor = str(vendor_code or "").strip().upper()
    if vendor in {"ALADIN", "YES24"}:
        return "CD"
    return None


class _PurchaseMailTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None
        self._ignore_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = str(tag or "").lower()
        if name in {"script", "style"}:
            self._ignore_depth += 1
            return
        if self._ignore_depth:
            return
        if name == "tr":
            self._current_row = []
            return
        if name in {"td", "th"}:
            self._current_cell = []
            return
        if name == "br" and self._current_cell is not None:
            self._current_cell.append("\n")

    def handle_endtag(self, tag: str) -> None:
        name = str(tag or "").lower()
        if name in {"script", "style"} and self._ignore_depth:
            self._ignore_depth -= 1
            return
        if self._ignore_depth:
            return
        if name in {"td", "th"} and self._current_cell is not None and self._current_row is not None:
            cell_text = re.sub(r"\s+", " ", "".join(self._current_cell)).strip()
            self._current_row.append(cell_text)
            self._current_cell = None
            return
        if name == "tr" and self._current_row is not None:
            if any(_clean_text(cell) for cell in self._current_row):
                self.rows.append(self._current_row)
            self._current_row = None

    def handle_data(self, data: str) -> None:
        if self._ignore_depth or self._current_cell is None:
            return
        self._current_cell.append(str(data or ""))


def _purchase_rows_from_html(raw_content: str) -> list[list[str]]:
    parser = _PurchaseMailTableParser()
    parser.feed(raw_content)
    parser.close()
    return parser.rows


def _purchase_rows_from_text(raw_content: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in str(raw_content or "").splitlines():
        text = re.sub(r"\s+", " ", line).strip()
        if not text:
            continue
        cells = [part.strip() for part in re.split(r"\t+| {2,}", text) if part.strip()]
        if cells:
            rows.append(cells)
    return rows


def _extract_html_from_mhtml(raw_content: str) -> str | None:
    raw = str(raw_content or "").strip()
    if not raw:
        return None
    msg = _purchase_message_from_raw_content(raw)
    if msg is None:
        return None
    html_parts: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() != "text/html":
                continue
            try:
                content = part.get_content()
            except Exception:
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                content = payload.decode(charset, errors="replace") if isinstance(payload, bytes) else ""
            text = str(content or "").strip()
            if text:
                html_parts.append(text)
    elif msg.get_content_type() == "text/html":
        try:
            content = msg.get_content()
        except Exception:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            content = payload.decode(charset, errors="replace") if isinstance(payload, bytes) else ""
        text = str(content or "").strip()
        if text:
            html_parts.append(text)
    return html_parts[0] if html_parts else None


def _extract_html_from_mhtml_bytes(raw_content: bytes) -> str | None:
    raw = bytes(raw_content or b"").strip()
    if not raw:
        return None
    msg = _purchase_message_from_raw_bytes(raw)
    if msg is None:
        return None
    html_parts: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() != "text/html":
                continue
            try:
                content = part.get_content()
            except Exception:
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                content = payload.decode(charset, errors="replace") if isinstance(payload, bytes) else ""
            text = str(content or "").strip()
            if text:
                html_parts.append(text)
    elif msg.get_content_type() == "text/html":
        try:
            content = msg.get_content()
        except Exception:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            content = payload.decode(charset, errors="replace") if isinstance(payload, bytes) else ""
        text = str(content or "").strip()
        if text:
            html_parts.append(text)
    return html_parts[0] if html_parts else None


def _purchase_html_from_raw_content(raw_content: str) -> str | None:
    extracted = _extract_html_from_mhtml(raw_content)
    if extracted:
        return extracted
    text = str(raw_content or "").strip()
    if "<" in text and ">" in text:
        return text
    return None


def _decode_purchase_import_upload_bytes(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp949", "euc-kr", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise HTTPException(status_code=400, detail="구매 내역 파일 디코딩 실패: UTF-8/CP949/EUC-KR/LATIN-1 확인 필요")


def _purchase_html_from_upload_bytes(raw_content: bytes, *, fallback_text: str | None = None) -> str | None:
    extracted = _extract_html_from_mhtml_bytes(raw_content)
    if extracted:
        return extracted
    text = str(fallback_text or "").strip() or _decode_purchase_import_upload_bytes(raw_content)
    if "<" in text and ">" in text:
        return text
    return None


def _resolve_purchase_import_raw_input(
    payload: PurchaseImportPreviewRequest | PurchaseImportWebhookRequest,
) -> tuple[str, str | None]:
    raw_content = str(getattr(payload, "raw_content", "") or "").strip()
    raw_content_base64 = str(getattr(payload, "raw_content_base64", "") or "").strip()
    if not raw_content_base64:
        return raw_content, _purchase_html_from_raw_content(raw_content)
    try:
        raw_bytes = base64.b64decode(raw_content_base64, validate=True)
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"구매 내역 파일 디코딩 실패: {err}") from err
    decoded_text = _decode_purchase_import_upload_bytes(raw_bytes)
    html_content = _purchase_html_from_upload_bytes(raw_bytes, fallback_text=decoded_text)
    return (html_content or decoded_text), html_content


def _purchase_compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _purchase_dense_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def _purchase_normalize_item_url(value: Any, *, base_url: str | None = None) -> str | None:
    url = _clean_text(value)
    if not url:
        return None
    if base_url and url.startswith("/"):
        url = f"{base_url.rstrip('/')}{url}"
    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        normalized = parsed._replace(params="", query="", fragment="")
        return normalized.geturl()
    return url.split("#", 1)[0].split("?", 1)[0].strip() or None


def _purchase_currency_code(value: Any, default: str = "KRW") -> str:
    text = str(value or "").strip()
    upper = text.upper()
    if upper in {"KRW", "USD", "GBP", "EUR", "JPY"}:
        return upper
    if "US $" in upper or ("$" in text and "CA$" not in upper and "A$" not in upper):
        return "USD"
    if "GBP" in upper or "£" in text:
        return "GBP"
    if "EUR" in upper or "€" in text:
        return "EUR"
    if "JPY" in upper or "¥" in text or "￥" in text:
        return "JPY"
    return default


def _purchase_host_from_url(value: Any) -> str:
    url = _clean_text(value)
    if not url:
        return ""
    try:
        return str(urlparse(url).hostname or "").strip().lower()
    except Exception:
        return ""


def _purchase_marketplace_currency(vendor_code: str, marketplace: Any) -> str:
    vendor = str(vendor_code or "").strip().upper()
    market = str(marketplace or "").strip().upper()
    if vendor == "AMAZON":
        if market == "UK":
            return "GBP"
        if market == "JP":
            return "JPY"
        return "USD"
    if vendor == "EBAY":
        return "USD"
    return "KRW"


def _purchase_amazon_marketplace_from_raw_content(raw_content: str) -> str | None:
    text = str(raw_content or "")
    if "amazon.co.jp" in text:
        return "JP"
    if "amazon.co.uk" in text:
        return "UK"
    if "amazon.com" in text:
        return "US"
    return None


def _extract_purchase_price_from_text(value: Any, default_currency: str) -> tuple[float | None, str]:
    text = _purchase_compact_text(value)
    if not text:
        return None, default_currency
    text_variants = [text]
    dense_text = _purchase_dense_text(text)
    if dense_text and dense_text != text:
        text_variants.append(dense_text)
    patterns = (
        r"(US\s*\$\s*[0-9,\s]+(?:\.[0-9]{2})?)",
        r"(\$\s*[0-9,\s]+(?:\.[0-9]{2})?)",
        r"(£\s*[0-9,\s]+(?:\.[0-9]{2})?)",
        r"(¥\s*[0-9,\s]+(?:\.[0-9]{2})?)",
        r"(￥\s*[0-9,\s]+(?:\.[0-9]{2})?)",
        r"([0-9,\s]+(?:\.[0-9]{2})?\s*(?:USD|GBP|EUR|JPY))",
    )
    for candidate_text in text_variants:
        for pattern in patterns:
            match = re.search(pattern, candidate_text, re.IGNORECASE)
            if not match:
                continue
            price_text = str(match.group(1) or "").strip()
            amount = _parse_price_number(price_text)
            if amount is None:
                continue
            return amount, _purchase_currency_code(price_text, default_currency)
    return None, default_currency


def _extract_purchase_date_from_text(value: Any) -> str | None:
    text = _purchase_compact_text(value)
    patterns = (
        r"Order placed\s+([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})",
        r"Order placed\s+(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})",
        r"Placed on\s+([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})",
        r"Placed on\s+(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        normalized = _normalize_purchase_date(match.group(1))
        if normalized:
            return normalized
    return None


def _extract_purchase_total_from_text(value: Any, default_currency: str = "KRW") -> tuple[float | None, str]:
    text = _purchase_compact_text(value)
    text_variants = [text]
    dense_text = _purchase_dense_text(text)
    if dense_text and dense_text != text:
        text_variants.append(dense_text)
    patterns = (
        r"Total\s+((?:US\s*\$|\$|GBP\s*|EUR\s*|JPY\s*|¥|￥)[0-9,.\s]+)",
        r"Total\s+([0-9,.\s]+\s*(?:USD|GBP|EUR|JPY))",
        r"Total((?:US\$|\$|GBP|EUR|JPY|¥|￥)[0-9,.\s]+)",
        r"Total[^0-9]{0,6}([0-9][0-9,.\s]{0,20})",
    )
    for candidate_text in text_variants:
        for pattern in patterns:
            match = re.search(pattern, candidate_text, re.IGNORECASE)
            if not match:
                continue
            price_text = str(match.group(1) or "").strip()
            amount = _parse_price_number(price_text)
            if amount is None:
                continue
            return amount, _purchase_currency_code(price_text, default_currency)
    return None, default_currency


def _build_purchase_preview_item_direct(
    *,
    row_no: int,
    artist_name: str | None,
    item_name: str,
    media_format: str | None,
    quantity: int = 1,
    unit_price: float | None = None,
    line_total: float | None = None,
    currency_code: str = "KRW",
    purchase_date: str | None = None,
    raw_line: str | None = None,
    raw_payload: dict[str, Any] | None = None,
) -> PurchaseImportPreviewItem | None:
    item_title = _clean_text(item_name)
    if not item_title:
        return None
    normalized_media = _normalize_purchase_media_format(media_format)
    if normalized_media is None:
        return None
    return PurchaseImportPreviewItem(
        row_no=row_no,
        artist_name=_clean_text(artist_name),
        item_name=item_title,
        media_format=normalized_media,
        quantity=max(1, int(quantity or 1)),
        unit_price=unit_price,
        line_total=line_total,
        currency_code=_purchase_currency_code(currency_code),
        purchase_date=_normalize_purchase_date(purchase_date),
        raw_line=_clean_text(raw_line),
        raw_payload=dict(raw_payload or {}),
    )


def _purchase_amazon_asin_from_url(value: Any) -> str | None:
    url = _clean_text(value)
    if not url:
        return None
    patterns = (
        r"/dp/([A-Z0-9]{10})(?:[/?]|$)",
        r"/gp/product/([A-Z0-9]{10})(?:[/?]|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return str(match.group(1) or "").strip().upper() or None
    return None


def _purchase_amazon_marketplace_from_url(value: Any) -> str | None:
    url = _clean_text(value)
    if not url:
        return None
    try:
        hostname = str(urlparse(url).hostname or "").strip().lower()
    except Exception:
        return None
    if not hostname:
        return None
    if hostname.endswith("amazon.co.jp"):
        return "JP"
    if hostname.endswith("amazon.co.uk"):
        return "UK"
    if hostname.endswith("amazon.com"):
        return "US"
    if hostname.endswith("amazon.de"):
        return "DE"
    if hostname.endswith("amazon.fr"):
        return "FR"
    return hostname


def _purchase_fetch_item_page_html(item_url: str) -> str | None:
    url = _purchase_normalize_item_url(item_url)
    if not url:
        return None
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True, headers=PURCHASE_ITEM_FETCH_HEADERS) as client:
            response = client.get(url)
            response.raise_for_status()
    except httpx.HTTPError:
        return None
    text = str(response.text or "").strip()
    return text or None


def _purchase_extract_amazon_artist_name(soup: BeautifulSoup) -> str | None:
    byline = _purchase_compact_text(soup.select_one("#bylineInfo").get_text(" ", strip=True) if soup.select_one("#bylineInfo") else "")
    if byline:
        text = re.sub(r"\s+", " ", byline).strip()
        text = re.sub(r"\s*Visit the .*? Store\s*", " ", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\s*Brand:\s*", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\s*Format:.*$", "", text, flags=re.IGNORECASE).strip(" -|/")
        if text:
            return text
    detail_text = _purchase_compact_text(soup.select_one("#detailBullets_feature_div").get_text(" ", strip=True) if soup.select_one("#detailBullets_feature_div") else "")
    if detail_text:
        match = re.search(r"Artist\s*[:‏‎]*\s*(.+?)(?:Label\s*:|ASIN\s*:|Number of discs|$)", detail_text, re.IGNORECASE)
        if match:
            artist_name = _clean_text(match.group(1))
            if artist_name:
                return artist_name
    return None


def _purchase_normalize_amazon_detail_key(value: str) -> str:
    text = _purchase_compact_text(value).replace("‏", " ").replace("‎", " ")
    text = re.sub(r"\s+", " ", text).strip().rstrip(":").strip()
    return text.lower()


def _purchase_extract_amazon_detail_map(soup: BeautifulSoup) -> dict[str, str]:
    out: dict[str, str] = {}

    def _put(label: str | None, value: str | None) -> None:
        key = _purchase_normalize_amazon_detail_key(label or "")
        text = _clean_text(value)
        if not key or not text or key in out:
            return
        out[key] = text

    detail_root = soup.select_one("#detailBullets_feature_div") or soup.select_one("#detailBulletsWrapper_feature_div")
    if detail_root:
        for li in detail_root.select("li"):
            label_node = li.select_one(".a-text-bold")
            label_text = _purchase_compact_text(label_node.get_text(" ", strip=True) if label_node else "")
            full_text = _purchase_compact_text(li.get_text(" ", strip=True))
            if label_text and full_text.startswith(label_text):
                _put(label_text, full_text[len(label_text):])
            elif ":" in full_text:
                left, right = full_text.split(":", 1)
                _put(left, right)

    for selector in ("#productDetails_detailBullets_sections1", "#productDetails_techSpec_section_1"):
        table = soup.select_one(selector)
        if not table:
            continue
        for tr in table.select("tr"):
            label_text = _purchase_compact_text(tr.select_one("th").get_text(" ", strip=True) if tr.select_one("th") else "")
            value_text = _purchase_compact_text(tr.select_one("td").get_text(" ", strip=True) if tr.select_one("td") else "")
            _put(label_text, value_text)

    return out


def _purchase_extract_amazon_detail_enrichment(item_url: str) -> dict[str, Any] | None:
    html = _purchase_fetch_item_page_html(item_url)
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    title = _purchase_compact_text(soup.select_one("#productTitle").get_text(" ", strip=True) if soup.select_one("#productTitle") else "")
    artist_name = _purchase_extract_amazon_artist_name(soup)
    image_node = soup.select_one("#landingImage")
    image_url = _clean_text(image_node.get("data-old-hires") if image_node else None) or _clean_text(image_node.get("src") if image_node else None)
    track_text = _purchase_compact_text(soup.select_one("#musicTracks_feature_div").get_text(" ", strip=True) if soup.select_one("#musicTracks_feature_div") else "")
    detail_map = _purchase_extract_amazon_detail_map(soup)

    def _detail_value(*keys: str) -> str | None:
        for key in keys:
            text = _clean_text(detail_map.get(_purchase_normalize_amazon_detail_key(key)))
            if text:
                return text
        return None

    label_name = _detail_value("Label", "Manufacturer")
    released_date = _detail_value("Original Release Date", "Date First Available")
    track_samples: list[str] = []
    if track_text:
        sample_matches = re.findall(r"\d+\s+([^0-9].*?)(?=\s+\d+\s+|$)", track_text)
        for raw in sample_matches[:10]:
            cleaned = _clean_text(raw)
            if cleaned:
                track_samples.append(cleaned)
    return {
        "item_name": title or None,
        "artist_name": artist_name,
        "image_url": image_url,
        "label_name": label_name,
        "released_date": released_date,
        "track_samples": track_samples,
    }


def _purchase_extract_ebay_detail_enrichment(item_url: str) -> dict[str, Any] | None:
    html = _purchase_fetch_item_page_html(item_url)
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    title = _clean_text(soup.select_one("meta[property='og:title']").get("content") if soup.select_one("meta[property='og:title']") else None)
    image_url = _clean_text(soup.select_one("meta[property='og:image']").get("content") if soup.select_one("meta[property='og:image']") else None)
    seller_name = _purchase_compact_text(soup.select_one("[data-testid='ux-seller-section']").get_text(" ", strip=True) if soup.select_one("[data-testid='ux-seller-section']") else "")
    return {
        "item_name": title or None,
        "image_url": image_url,
        "seller_name": seller_name or None,
    }


def _purchase_enrich_row_from_item_page(row: dict[str, Any]) -> dict[str, Any]:
    raw_payload = dict(row.get("raw_payload") or {})
    item_url = _purchase_normalize_item_url(row.get("item_url") or raw_payload.get("item_url"))
    if not item_url:
        raise HTTPException(status_code=400, detail="구매 항목에 상품 상세 URL이 없습니다.")
    host = _purchase_host_from_url(item_url)
    enrichment: dict[str, Any] | None = None
    if "amazon." in host:
        enrichment = _purchase_extract_amazon_detail_enrichment(item_url)
    elif "ebay." in host:
        enrichment = _purchase_extract_ebay_detail_enrichment(item_url)
    if enrichment is None:
        raise HTTPException(status_code=400, detail="현재는 Amazon/eBay 상품 상세 페이지만 보강할 수 있습니다.")

    raw_payload["item_url"] = item_url
    if enrichment.get("image_url"):
        raw_payload["image_url"] = enrichment["image_url"]
    if "amazon." in host:
        raw_payload["detail_page_title"] = enrichment.get("item_name")
        raw_payload["detail_page_artist_name"] = enrichment.get("artist_name")
        raw_payload["detail_page_label_name"] = enrichment.get("label_name")
        raw_payload["detail_page_released_date"] = enrichment.get("released_date")
        raw_payload["detail_page_track_samples"] = list(enrichment.get("track_samples") or [])
    updated = db.update_purchase_import_row(
        int(row["id"]),
        artist_name=_clean_text(enrichment.get("artist_name")) or _clean_text(row.get("artist_name")),
        seller_name=_clean_text(enrichment.get("seller_name")) or _clean_text(row.get("seller_name")),
        item_url=item_url,
        image_url=_clean_text(enrichment.get("image_url")) or _clean_text(row.get("image_url")),
        raw_payload=raw_payload,
    )
    if updated is None:
        raise HTTPException(status_code=500, detail="purchase import row update failed")
    return updated


def _purchase_preview_items_from_amazon_html(raw_content: str, *, purchase_date: str | None) -> list[PurchaseImportPreviewItem]:
    detail_items = _purchase_preview_items_from_amazon_order_details_html(
        raw_content,
        purchase_date=purchase_date,
    )
    if detail_items:
        return detail_items
    soup = BeautifulSoup(raw_content, "html.parser")
    cards = soup.select(".order-card")
    preview_items: list[PurchaseImportPreviewItem] = []
    next_row_no = 1
    page_marketplace = _purchase_amazon_marketplace_from_raw_content(raw_content)
    for card in cards:
        card_text = _purchase_compact_text(card.get_text(" ", strip=True))
        order_date = _extract_purchase_date_from_text(card_text) or _normalize_purchase_date(purchase_date)
        order_default_currency = _purchase_marketplace_currency("AMAZON", page_marketplace)
        order_total, currency_code = _extract_purchase_total_from_text(card_text, order_default_currency)
        image_candidates = []
        for img in card.select("img[src]"):
            image_candidates.append(
                {
                    "title": _purchase_compact_text(img.get("alt")),
                    "image_url": _clean_text(img.get("src")),
                }
            )
        item_rows: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, str]] = set()
        for link in card.select("a[href]"):
            href = _clean_text(link.get("href"))
            if not href or ("/dp/" not in href and "/gp/product/" not in href):
                continue
            title = _purchase_compact_text(link.get_text(" ", strip=True))
            if not title:
                continue
            key = (title.lower(), href)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            image_url = None
            for image in image_candidates:
                image_title = str(image.get("title") or "")
                if image_title and (image_title in title or title in image_title):
                    image_url = image.get("image_url")
                    break
            item_marketplace = _purchase_amazon_marketplace_from_url(href) or page_marketplace
            item_default_currency = _purchase_marketplace_currency("AMAZON", item_marketplace)
            item_price = None
            item_currency = item_default_currency
            probe = link
            probe_depth = 0
            while probe is not None and probe is not card and probe_depth < 6:
                probe_text = _purchase_compact_text(probe.get_text(" ", strip=True))
                if probe_text:
                    parsed_price, parsed_currency = _extract_purchase_price_from_text(probe_text, item_default_currency)
                    if parsed_price is not None and not (order_total is not None and len(item_rows) > 1 and abs(parsed_price - order_total) < 0.0001):
                        item_price = parsed_price
                        item_currency = parsed_currency
                        break
                probe = getattr(probe, "parent", None)
                probe_depth += 1
            item_rows.append(
                {
                    "title": title,
                    "item_url": href,
                    "image_url": image_url,
                    "marketplace": item_marketplace,
                    "unit_price": item_price,
                    "currency_code": item_currency,
                }
            )
        for item_row in item_rows:
            item_url = item_row.get("item_url")
            item_marketplace = item_row.get("marketplace") or page_marketplace
            item_default_currency = _purchase_marketplace_currency("AMAZON", item_marketplace)
            item_price = item_row.get("unit_price")
            item_currency = str(item_row.get("currency_code") or item_default_currency).strip().upper() or item_default_currency
            item = _build_purchase_preview_item_direct(
                row_no=next_row_no,
                artist_name=None,
                item_name=item_row["title"],
                media_format=item_row["title"],
                quantity=1,
                unit_price=item_price if item_price is not None else (order_total if len(item_rows) == 1 else None),
                line_total=item_price if item_price is not None else (order_total if len(item_rows) == 1 else None),
                currency_code=item_currency if item_price is not None else currency_code,
                purchase_date=order_date,
                raw_line=card_text,
                raw_payload={
                    "vendor_code": "AMAZON",
                    "item_url": item_url,
                    "image_url": item_row.get("image_url"),
                    "asin": _purchase_amazon_asin_from_url(item_url),
                    "marketplace": item_marketplace,
                },
            )
            if item is None:
                continue
            preview_items.append(item)
            next_row_no += 1
    return preview_items


def _purchase_preview_items_from_amazon_order_details_html(raw_content: str, *, purchase_date: str | None) -> list[PurchaseImportPreviewItem]:
    soup = BeautifulSoup(raw_content, "html.parser")
    root = soup.select_one("#orderDetails") or soup.select_one("[id*='orderDetails']")
    if root is None:
        return []
    page_marketplace = _purchase_amazon_marketplace_from_raw_content(raw_content)
    order_text = _purchase_compact_text(root.get_text(" ", strip=True))
    order_date = _extract_purchase_date_from_text(order_text) or _normalize_purchase_date(purchase_date)
    order_default_currency = _purchase_marketplace_currency("AMAZON", page_marketplace)
    summary_node = root.select_one("#od-subtotals")
    order_total, currency_code = _extract_purchase_total_from_text(
        _purchase_compact_text(summary_node.get_text(" ", strip=True) if summary_node else order_text),
        order_default_currency,
    )
    blocks: list[Any] = []
    for block in root.select("div.a-fixed-left-grid"):
        title_links = [
            link for link in block.select("a[href]")
            if (
                "/dp/" in str(link.get("href") or "")
                or "/gp/product/" in str(link.get("href") or "")
            )
            and "ppx_hzod_" in str(link.get("href") or "")
        ]
        if title_links:
            blocks.append(block)
    preview_items: list[PurchaseImportPreviewItem] = []
    seen_keys: set[tuple[str, str]] = set()
    next_row_no = 1
    for block in blocks:
        block_text = _purchase_compact_text(block.get_text(" ", strip=True))
        if not block_text:
            continue
        title_link = None
        for link in block.select("a[href]"):
            href = _clean_text(link.get("href"))
            title = _purchase_compact_text(link.get_text(" ", strip=True))
            if not href or ("/dp/" not in href and "/gp/product/" not in href):
                continue
            if not title:
                continue
            title_link = link
            break
        if title_link is None:
            continue
        item_title = _purchase_compact_text(title_link.get_text(" ", strip=True))
        item_url = _purchase_normalize_item_url(title_link.get("href"))
        dedupe_key = (item_title.lower(), item_url or "")
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        item_marketplace = _purchase_amazon_marketplace_from_url(item_url) or page_marketplace
        item_default_currency = _purchase_marketplace_currency("AMAZON", item_marketplace)
        item_price, item_currency = _extract_purchase_price_from_text(block_text, item_default_currency)
        media_hint = _normalize_purchase_media_format(block_text) or _normalize_purchase_media_format(item_title)
        if media_hint is None:
            parent_row = block.find_parent("div", class_=lambda value: isinstance(value, str) and "a-row" in value and "a-spacing-top-base" in value)
            if parent_row is not None:
                sibling_has_music = False
                for sibling in parent_row.select("div.a-fixed-left-grid"):
                    if sibling is block:
                        continue
                    sibling_text = _purchase_compact_text(sibling.get_text(" ", strip=True))
                    if _normalize_purchase_media_format(sibling_text):
                        sibling_has_music = True
                        break
                if sibling_has_music and item_price is not None:
                    media_hint = "LP"
        if media_hint is None:
            continue
        image_node = block.select_one("img[src]")
        seller_text = None
        seller_match = re.search(r"Sold by:\s*([^$]+?)(?:Buy it again|View your item|Condition:|$)", block_text, re.IGNORECASE)
        if seller_match:
            seller_text = _clean_text(seller_match.group(1))
        item = _build_purchase_preview_item_direct(
            row_no=next_row_no,
            artist_name=None,
            item_name=item_title,
            media_format=media_hint,
            quantity=1,
            unit_price=item_price if item_price is not None else (order_total if len(blocks) == 1 else None),
            line_total=item_price if item_price is not None else (order_total if len(blocks) == 1 else None),
            currency_code=item_currency if item_price is not None else currency_code,
            purchase_date=order_date,
            raw_line=block_text,
            raw_payload={
                "vendor_code": "AMAZON",
                "item_url": item_url,
                "image_url": _clean_text(image_node.get("src") if image_node else None),
                "asin": _purchase_amazon_asin_from_url(item_url),
                "marketplace": item_marketplace,
                "seller_name": seller_text,
                "media_format_inferred": 1 if media_hint == "LP" and _normalize_purchase_media_format(block_text) is None and _normalize_purchase_media_format(item_title) is None else 0,
            },
        )
        if item is None:
            continue
        preview_items.append(item)
        next_row_no += 1
    return preview_items


def _purchase_preview_items_from_ebay_html(raw_content: str, *, purchase_date: str | None) -> list[PurchaseImportPreviewItem]:
    soup = BeautifulSoup(raw_content, "html.parser")
    cards = soup.select(".m-item-card")
    preview_items: list[PurchaseImportPreviewItem] = []
    next_row_no = 1
    for card in cards:
        title_node = card.select_one("h3.title-heading") or card.select_one("h3")
        title = _purchase_compact_text(title_node.get_text(" ", strip=True) if title_node else "")
        if not title:
            continue
        media_format = _normalize_purchase_media_format(title)
        if media_format is None:
            continue
        artist_name, item_name, cover_condition, disc_condition = _parse_ebay_purchase_title(title)
        price_node = card.select_one(".container-item-col__info-item-info-additionalPrice")
        price_text = _purchase_compact_text(price_node.get_text(" ", strip=True) if price_node else "")
        seller_link = card.select_one("a[href*='/usr/']")
        seller_name = _purchase_compact_text(seller_link.get_text(" ", strip=True) if seller_link else "")
        item_link = card.select_one("a[href*='/itm/']")
        item_url = _purchase_normalize_item_url(item_link.get("href") if item_link else None, base_url="https://www.ebay.com")
        image_node = card.select_one("img[src]")
        item = _build_purchase_preview_item_direct(
            row_no=next_row_no,
            artist_name=artist_name,
            item_name=item_name or title,
            media_format=media_format,
            quantity=1,
            unit_price=_parse_price_number(price_text),
            line_total=_parse_price_number(price_text),
            currency_code=_purchase_marketplace_currency("EBAY", None),
            purchase_date=_normalize_purchase_date(purchase_date),
            raw_line=_purchase_compact_text(card.get_text(" ", strip=True)),
            raw_payload={
                "vendor_code": "EBAY",
                "listing_title": title,
                "seller_name": seller_name or "EBAY",
                "item_url": item_url,
                "image_url": _clean_text(image_node.get("src") if image_node else None),
                "parsed_search_artist_name": artist_name,
                "parsed_search_item_name": item_name or title,
                "parsed_cover_condition": cover_condition,
                "parsed_disc_condition": disc_condition,
            },
        )
        if item is None:
            continue
        preview_items.append(item)
        next_row_no += 1
    return preview_items


def _purchase_import_empty_reason(vendor_code: str, raw_content: str) -> str | None:
    vendor = str(vendor_code or "").strip().upper()
    text = str(raw_content or "")
    if vendor == "AMAZON":
        has_order_list = ".order-card" in text or 'class=\"order-card' in text or "order-card" in text
        has_order_details = "#orderDetails" in text or 'id=\"orderDetails' in text or "/order-details?orderID=" in text or "Order Details" in text
        if not has_order_list and not has_order_details:
            return "Amazon 주문 카드(order-card) 또는 주문 상세(orderDetails)를 찾지 못했습니다. 주문목록/주문상세 페이지 MHTML인지 확인하세요."
        return "Amazon 주문 페이지에서 음악 상품 행을 찾지 못했습니다. 다른 주문 페이지 형식이거나 비음악 상품만 포함됐을 수 있습니다."
    if vendor == "EBAY":
        if ".m-item-card" not in text and 'class=\"m-item-card' not in text and "m-item-card" not in text:
            return "eBay 구매 카드(m-item-card)를 찾지 못했습니다. 구매내역 목록 페이지 MHTML인지 확인하세요."
        return "eBay 구매 페이지에서 음악 상품 행을 찾지 못했습니다. 현재 파서는 음악 미디어로 보이는 항목만 추출합니다."
    return None


def _build_purchase_preview_item(
    *,
    row_no: int,
    cells: list[str],
    purchase_date: str | None,
    vendor_code: str,
) -> PurchaseImportPreviewItem | None:
    if not cells:
        return None
    first_text = _clean_text(cells[0])
    if not first_text or "합계" in first_text:
        return None
    if any(str(cell or "").strip() in {"합계", "총계"} for cell in cells):
        return None

    media_idx: int | None = None
    media_format: str | None = None
    for idx, cell in enumerate(cells):
        normalized = _normalize_purchase_media_format(cell)
        if normalized:
            media_idx = idx
            media_format = normalized
            break
    if media_idx is None:
        normalized = _normalize_purchase_media_format(first_text)
        if normalized:
            media_idx = 1 if len(cells) > 1 else 0
            media_format = normalized
    if media_format is None:
        return None

    artist_name, item_name = _split_artist_item_text(first_text)
    if not item_name:
        return None
    quantity = _parse_positive_int(cells[media_idx + 1] if len(cells) > media_idx + 1 else None, 1)
    unit_price = _parse_price_number(cells[media_idx + 2] if len(cells) > media_idx + 2 else None)
    line_total = _parse_price_number(cells[media_idx + 3] if len(cells) > media_idx + 3 else None)
    if line_total is None and unit_price is not None:
        line_total = float(unit_price) * quantity
    raw_line = " | ".join(str(cell or "").strip() for cell in cells if str(cell or "").strip())
    return PurchaseImportPreviewItem(
        row_no=row_no,
        artist_name=artist_name,
        item_name=item_name,
        media_format=media_format,
        quantity=quantity,
        unit_price=unit_price,
        line_total=line_total,
        currency_code="KRW",
        purchase_date=_normalize_purchase_date(purchase_date),
        raw_line=raw_line,
        raw_payload={
            "vendor_code": vendor_code,
            "cells": cells,
        },
    )


def _parse_purchase_import_preview(payload: PurchaseImportPreviewRequest | PurchaseImportWebhookRequest) -> list[PurchaseImportPreviewItem]:
    raw_content, html_content = _resolve_purchase_import_raw_input(payload)
    if not raw_content:
        return []
    vendor_code = _resolve_purchase_import_vendor_code(getattr(payload, "vendor_code", "OTHER"), raw_content=raw_content)
    resolved_purchase_date = _resolve_purchase_import_purchase_date(
        getattr(payload, "purchase_date", None),
        raw_content=raw_content,
    )
    if html_content:
        if vendor_code == "AMAZON":
            preview_items = _purchase_preview_items_from_amazon_html(
                html_content,
                purchase_date=resolved_purchase_date,
            )
            if preview_items:
                return preview_items
        if vendor_code == "EBAY":
            preview_items = _purchase_preview_items_from_ebay_html(
                html_content,
                purchase_date=resolved_purchase_date,
            )
            if preview_items:
                return preview_items
    rows = _purchase_rows_from_html(html_content or raw_content) if html_content else _purchase_rows_from_text(raw_content)
    preview_items: list[PurchaseImportPreviewItem] = []
    next_row_no = 1
    for cells in rows:
        item = _build_purchase_preview_item(
            row_no=next_row_no,
            cells=cells,
            purchase_date=resolved_purchase_date,
            vendor_code=vendor_code,
        )
        if item is None:
            continue
        preview_items.append(item)
        next_row_no += 1
    return preview_items


def _purchase_queue_item_from_row(row: dict[str, Any]) -> PurchaseImportQueueItem:
    raw_payload = dict(row.get("raw_payload") or {})
    parsed_artist_name = _clean_text(raw_payload.get("parsed_search_artist_name"))
    parsed_item_name = _clean_text(raw_payload.get("parsed_search_item_name"))
    if str(row.get("vendor_code") or "").strip().upper() == "EBAY" and (not parsed_artist_name or not parsed_item_name):
        ebay_artist_name, ebay_item_name, ebay_cover_condition, ebay_disc_condition = _parse_ebay_purchase_title(
            _purchase_ebay_parse_source_text(row, raw_payload)
        )
        parsed_artist_name = parsed_artist_name or ebay_artist_name
        parsed_item_name = parsed_item_name or ebay_item_name
        if parsed_artist_name and not raw_payload.get("parsed_search_artist_name"):
            raw_payload["parsed_search_artist_name"] = parsed_artist_name
        if parsed_item_name and not raw_payload.get("parsed_search_item_name"):
            raw_payload["parsed_search_item_name"] = parsed_item_name
        if ebay_cover_condition and not raw_payload.get("parsed_cover_condition"):
            raw_payload["parsed_cover_condition"] = ebay_cover_condition
        if ebay_disc_condition and not raw_payload.get("parsed_disc_condition"):
            raw_payload["parsed_disc_condition"] = ebay_disc_condition
    return PurchaseImportQueueItem(
        id=int(row["id"]),
        vendor_code=str(row.get("vendor_code") or "OTHER"),  # type: ignore[arg-type]
        source_type=str(row.get("source_type") or "MANUAL"),  # type: ignore[arg-type]
        source_ref=_clean_text(row.get("source_ref")),
        email_from=_clean_text(row.get("email_from")),
        email_subject=_clean_text(row.get("email_subject")),
        artist_name=parsed_artist_name or _clean_text(row.get("artist_name")),
        item_name=_purchase_queue_display_item_name(row, raw_payload) or str(row.get("item_name") or "").strip(),
        media_format=_clean_text(row.get("media_format")),
        quantity=max(1, int(row.get("quantity") or 1)),
        unit_price=float(row["unit_price"]) if row.get("unit_price") is not None else None,
        line_total=float(row["line_total"]) if row.get("line_total") is not None else None,
        currency_code=_clean_text(row.get("currency_code")),
        purchase_date=_normalize_purchase_date(row.get("purchase_date")),
        seller_name=_clean_text(row.get("seller_name")),
        item_url=_clean_text(row.get("item_url")),
        image_url=_clean_text(row.get("image_url")),
        raw_line=_clean_text(row.get("raw_line")),
        raw_payload=raw_payload,
        queue_status=str(row.get("queue_status") or "PENDING"),  # type: ignore[arg-type]
        linked_owned_item_id=int(row["linked_owned_item_id"]) if row.get("linked_owned_item_id") is not None else None,
        created_at=str(row.get("created_at") or ""),
        updated_at=str(row.get("updated_at") or ""),
    )


def _purchase_import_webhook_allowed(request: Request) -> bool:
    expected = str(get_settings().purchase_import_webhook_token or "").strip()
    provided = str(request.headers.get("x-purchase-import-token") or "").strip()
    return bool(expected) and secrets.compare_digest(provided, expected)


def _purchase_import_webhook_validate_request(request: Request) -> None:
    """Hard checks on the incoming HTTP request before we let Pydantic parse it.

    Used as a FastAPI `Depends`. Dependencies run before the route's body
    parameter is parsed, so a wrong Content-Type or oversized body produces
    415/413 instead of falling through to Pydantic's 422 with a confusing
    "Input should be a valid dict" / "Field required" message.

    * Content-Type must be a JSON variant. Browsers / non-JSON callers get
      a 415.
    * Content-Length, when present, must fit our cap. We can't enforce a
      true streaming cap from inside FastAPI without a custom middleware,
      but the header check covers well-behaved clients (Gmail forwarders,
      Zapier).
    """
    content_type = str(request.headers.get("content-type") or "").lower().strip()
    base_type = content_type.split(";", 1)[0].strip()
    if base_type and base_type not in _PURCHASE_IMPORT_WEBHOOK_ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"unsupported content-type: {base_type or 'unknown'}",
        )

    raw_length = str(request.headers.get("content-length") or "").strip()
    if raw_length:
        try:
            declared = int(raw_length)
        except (TypeError, ValueError):
            declared = -1
        if declared > PURCHASE_IMPORT_WEBHOOK_MAX_BODY_BYTES:
            raise HTTPException(
                status_code=413,
                detail=(
                    "request body exceeds purchase import webhook limit of "
                    f"{PURCHASE_IMPORT_WEBHOOK_MAX_BODY_BYTES} bytes"
                ),
            )


def _require_purchase_import_webhook_envelope(request: Request) -> None:
    """Composite Depends: token + envelope checks together.

    Combines the token gate with the Content-Type / Content-Length check so
    a single `dependencies=[...]` on the route covers everything that has
    to happen before Pydantic parses the body.
    """
    if not _purchase_import_webhook_allowed(request):
        raise HTTPException(status_code=403, detail="purchase import webhook token mismatch")
    _purchase_import_webhook_validate_request(request)


def _purchase_import_rows_for_save(
    items: list[PurchaseImportPreviewItem],
    *,
    vendor_code: str,
    email_from: str | None,
) -> list[dict[str, Any]]:
    seller_name = _clean_text(email_from) or vendor_code
    rows: list[dict[str, Any]] = []
    for item in items:
        raw_payload = dict(item.raw_payload or {})
        raw_payload["row_no"] = max(1, int(item.row_no or 1))
        item_url = _purchase_normalize_item_url(raw_payload.get("item_url"))
        rows.append(
            {
                "artist_name": _clean_text(item.artist_name),
                "item_name": str(item.item_name or "").strip(),
                "media_format": _purchase_import_media_format_or_default(vendor_code, item.media_format),
                "quantity": max(1, int(item.quantity or 1)),
                "unit_price": float(item.unit_price) if item.unit_price is not None else None,
                "line_total": float(item.line_total) if item.line_total is not None else None,
                "currency_code": str(item.currency_code or "KRW").strip().upper() or "KRW",
                "purchase_date": _normalize_purchase_date(item.purchase_date),
                "seller_name": _clean_text(raw_payload.get("seller_name")) or seller_name,
                "item_url": item_url,
                "image_url": _clean_text(raw_payload.get("image_url")),
                "raw_line": _clean_text(item.raw_line),
                "raw_payload": raw_payload,
            }
        )
    return rows


def _purchase_queue_base_context(row: dict[str, Any]) -> tuple[str, str, str, str]:
    from app.main import _infer_music_category_from_format, _default_size_group_for_category
    media_format = _purchase_import_media_format_or_default(row.get("vendor_code"), row.get("media_format")) or "CD"
    category = _infer_music_category_from_format(media_format)
    size_group = _default_size_group_for_category(category)
    seller_name = _clean_text(row.get("seller_name")) or _clean_text(row.get("vendor_code")) or "PURCHASE_IMPORT"
    return media_format, category, size_group, seller_name


def _purchase_queue_memory_note(row: dict[str, Any], candidate: dict[str, Any] | None = None) -> str:
    seller_name = _clean_text(row.get("seller_name")) or _clean_text(row.get("vendor_code")) or "PURCHASE_IMPORT"
    memory_bits = [f"구매 수입 큐 #{int(row['id'])}"]
    email_subject = _clean_text(row.get("email_subject"))
    source_ref = _clean_text(row.get("source_ref"))
    if email_subject:
        memory_bits.append(f"메일 제목: {email_subject}")
    if source_ref:
        memory_bits.append(f"메일 ID: {source_ref}")
    if isinstance(candidate, dict):
        source = str(candidate.get("source") or "").strip().upper()
        external_id = str(candidate.get("external_id") or "").strip()
        if source and external_id:
            memory_bits.append(f"메타 후보: {source}#{external_id}")
        candidate_source_notes = _clean_text(candidate.get("source_notes"))
        if candidate_source_notes:
            memory_bits.append(f"소스 메모: {candidate_source_notes}")
    memory_note = " | ".join(memory_bits)
    return memory_note


def _purchase_queue_candidate_query(
    row: dict[str, Any],
    *,
    artist_name: str | None = None,
    item_name: str | None = None,
    query: str | None = None,
) -> str:
    override_query = _clean_text(query)
    if override_query:
        return override_query
    raw_payload = dict(row.get("raw_payload") or {})
    fallback_artist_name = _clean_text(raw_payload.get("parsed_search_artist_name")) or _clean_text(row.get("artist_name"))
    fallback_item_name = _clean_text(raw_payload.get("parsed_search_item_name")) or _clean_text(row.get("item_name"))
    parts = [
        _clean_text(artist_name) if artist_name is not None else fallback_artist_name,
        _clean_text(item_name) if item_name is not None else fallback_item_name,
    ]
    return " ".join(part for part in parts if part).strip()


def _build_owned_item_from_purchase_queue_row(
    row: dict[str, Any],
    candidate: dict[str, Any] | None = None,
) -> OwnedItemCreate:
    from app.main import _default_size_group_for_category, _candidate_collector_base, _clean_string_list, _clean_track_list
    media_format, fallback_category, fallback_size_group, seller_name = _purchase_queue_base_context(row)
    raw_payload = dict(row.get("raw_payload") or {})
    candidate_source = str((candidate or {}).get("source") or "").strip().upper()
    candidate_external_id = str((candidate or {}).get("external_id") or "").strip()
    candidate_format = str((candidate or {}).get("format_name") or "").strip().upper()
    category = fallback_category
    if category == "DIGITAL" and candidate_format in MUSIC_CATEGORIES:
        category = candidate_format
    size_group = _default_size_group_for_category(category)
    ebay_artist_name: str | None = None
    ebay_item_name: str | None = None
    if str(row.get("vendor_code") or "").strip().upper() == "EBAY":
        ebay_artist_name, ebay_item_name, _, _ = _parse_ebay_purchase_title(_purchase_ebay_parse_source_text(row, raw_payload))
    artist_name = _clean_text((candidate or {}).get("artist_or_brand")) or _clean_text(row.get("artist_name")) or ebay_artist_name
    item_name = _clean_text((candidate or {}).get("title")) or ebay_item_name or _clean_text(row.get("item_name")) or category
    cover_condition = _clean_text((candidate or {}).get("cover_condition")) or _clean_text(raw_payload.get("parsed_cover_condition"))
    disc_condition = _clean_text((candidate or {}).get("disc_condition")) or _clean_text(raw_payload.get("parsed_disc_condition"))
    mapped_domain = _normalize_domain_code((candidate or {}).get("domain_code"))
    release_type = str((candidate or {}).get("release_type") or "").strip().upper() or None
    if release_type not in RELEASE_TYPES:
        release_type = None
    collector = _candidate_collector_base(candidate or {})
    if candidate_source == "ALADIN" and candidate_external_id and not collector.get("track_items"):
        try:
            fetched_tracks = fetch_aladin_track_items(candidate_external_id)
            if fetched_tracks:
                collector["track_items"] = fetched_tracks
        except Exception:
            pass
    return OwnedItemCreate(
        category=category,  # type: ignore[arg-type]
        size_group=size_group,  # type: ignore[arg-type]
        preferred_storage_size_group=size_group,  # type: ignore[arg-type]
        auto_location_recommendation=False,
        quantity=max(1, int(row.get("quantity") or 1)),
        status="IN_COLLECTION",
        source_code=candidate_source or None,
        source_external_id=candidate_external_id or None,
        domain_code=mapped_domain,
        release_type=release_type,  # type: ignore[arg-type]
        item_name_override=item_name,
        acquisition_date=_normalize_purchase_date(row.get("purchase_date")),
        purchase_price=float(row["unit_price"]) if row.get("unit_price") is not None else None,
        currency_code=str(row.get("currency_code") or "KRW").strip().upper() or "KRW",
        purchase_source=seller_name,
        memory_note=_purchase_queue_memory_note(row, candidate),
        music_detail=(
            MusicDetailCreate(
                format_name=category,  # type: ignore[arg-type]
                artist_or_brand=artist_name,
                released_date=_clean_text((candidate or {}).get("released_date")),
                barcode=_clean_text((candidate or {}).get("barcode")),
                label_name=_clean_text((candidate or {}).get("label_name")),
                catalog_no=_discogs_catalog_no((candidate or {}).get("catalog_no")),
                media_type=_clean_text((candidate or {}).get("media_type")),
                cover_condition=cover_condition or None,
                disc_condition=disc_condition or None,
                sleeve_condition=cover_condition or None,
                media_condition=disc_condition or None,
                genres=_clean_string_list((candidate or {}).get("genres")),
                styles=_clean_string_list((candidate or {}).get("styles")),
                cover_image_url=_clean_text((candidate or {}).get("cover_image_url")),
                track_list=_clean_track_list((candidate or {}).get("track_list")),
                disc_count=_normalize_positive_int((candidate or {}).get("disc_count")),
                speed_rpm=_normalize_positive_int((candidate or {}).get("speed_rpm")),
                source_notes=collector.get("source_notes"),
                credits=collector.get("credits"),
                identifier_items=collector.get("identifier_items"),
                image_items=collector.get("image_items"),
                company_items=collector.get("company_items"),
                series=collector.get("series"),
                format_items=collector.get("format_items"),
                track_items=collector.get("track_items"),
                label_items=collector.get("label_items"),
                runout_matrix=collector.get("runout_matrix"),
                pressing_country=collector.get("pressing_country"),
            )
            if category in MUSIC_CATEGORIES
            else None
        ),
    )


def _purchase_import_duplicate_create_response(
    *,
    queue_id: int,
    row: dict[str, Any],
    existing_owned_item_id: int,
) -> PurchaseImportCreateResponse:
    existing_owned_item = db.get_owned_item(existing_owned_item_id)
    if existing_owned_item is None:
        raise HTTPException(status_code=404, detail="linked owned item not found")
    updated = db.update_purchase_import_row(
        queue_id,
        queue_status="CREATED",
        linked_owned_item_id=existing_owned_item_id,
    )
    if updated is None:
        raise HTTPException(status_code=500, detail="purchase import row update failed")
    category = str(existing_owned_item.get("category") or row.get("media_format") or "OTHER").strip().upper() or "OTHER"
    return PurchaseImportCreateResponse(
        queue_item=_purchase_queue_item_from_row(updated),
        owned_item_id=existing_owned_item_id,
        label_id=_build_label_id(category, existing_owned_item_id),
        linked_album_master_id=(
            int(existing_owned_item["linked_album_master_id"])
            if existing_owned_item.get("linked_album_master_id") is not None
            else None
        ),
        notices=["동일한 주문 상품이 이미 등록되어 기존 보유상품에 연결했습니다. 신규 등록은 생략했습니다."],
    )
