    const $ = (id) => document.getElementById(id);
    const valueOf = (id) => {
      const el = $(id);
      return el && "value" in el ? String(el.value || "") : "";
    };

    function setHtmlIfPresent(id, html) {
      const el = $(id);
      if (!el) return null;
      el.innerHTML = html;
      return el;
    }

    function setTextIfPresent(id, text) {
      const el = $(id);
      if (!el) return null;
      el.textContent = text;
      return el;
    }

    const DISPLAY_STATE_CLASS_BY_VALUE = Object.freeze({
      "block": "u-display-block",
      "flex": "u-display-flex",
      "grid": "u-display-grid",
      "inline-flex": "u-display-inline-flex",
    });

    function setDisplayMode(el, value) {
      if (!el) return null;
      el.classList.remove("u-hidden-initial", "u-hidden-initial-important", ...Object.values(DISPLAY_STATE_CLASS_BY_VALUE));
      const normalizedValue = typeof value === "string" ? value.trim().toLowerCase() : "";
      if (!normalizedValue || normalizedValue === "none") {
        el.classList.add("u-hidden-initial");
        return el;
      }
      const nextClass = DISPLAY_STATE_CLASS_BY_VALUE[normalizedValue] || DISPLAY_STATE_CLASS_BY_VALUE.block;
      el.classList.add(nextClass);
      return el;
    }

    function setDisplayIfPresent(id, value) {
      const el = $(id);
      return setDisplayMode(el, value);
    }

    function setHiddenState(el, hidden) {
      if (!el) return null;
      el.classList.remove("u-hidden-initial", "u-hidden-initial-important", ...Object.values(DISPLAY_STATE_CLASS_BY_VALUE));
      if (hidden) {
        el.classList.add("u-hidden-initial");
      }
      return el;
    }

    function setHiddenIfPresent(id, hidden) {
      const el = $(id);
      return setHiddenState(el, hidden);
    }

    function isElementDisplayNone(el) {
      if (!el) return true;
      return window.getComputedStyle(el).display === "none";
    }

    function isSupportedAppLocale(locale) {
      return SUPPORTED_APP_LOCALES.has(String(locale || "").trim());
    }

    function loadSavedLocale() {
      try {
        const saved = window.localStorage.getItem(APP_LOCALE_STORAGE_KEY);
        return isSupportedAppLocale(saved) ? String(saved).trim() : "ko";
      } catch (_) {
        return "ko";
      }
    }

    function saveLocale(locale) {
      const normalized = isSupportedAppLocale(locale) ? String(locale).trim() : "ko";
      try {
        window.localStorage.setItem(APP_LOCALE_STORAGE_KEY, normalized);
      } catch (_) {}
      return normalized;
    }

    function interpolateI18nMessage(template, params = {}) {
      return String(template || "").replace(/\{(\w+)\}/g, (_, key) => {
        if (!Object.prototype.hasOwnProperty.call(params, key)) return `{${key}}`;
        return String(params[key] ?? "");
      });
    }

    function t(key, params = {}) {
      const normalizedKey = String(key || "").trim();
      if (!normalizedKey) return "";
      const localeMessages = I18N_MESSAGES[appLocale] || I18N_MESSAGES.ko || {};
      const fallbackMessages = I18N_MESSAGES.ko || {};
      const message = Object.prototype.hasOwnProperty.call(localeMessages, normalizedKey)
        ? localeMessages[normalizedKey]
        : fallbackMessages[normalizedKey];
      if (typeof message !== "string") return normalizedKey;
      return interpolateI18nMessage(message, params);
    }

    function syncShellLocaleSelect() {
      const select = $("shellLocaleSelect");
      if (!select) return;
      select.value = appLocale;
      const optionTexts = {
        ko: t("locale.option.ko"),
        en: t("locale.option.en"),
        ja: t("locale.option.ja"),
      };
      Array.from(select.options || []).forEach((option) => {
        const code = String(option.value || "").trim();
        if (optionTexts[code]) option.textContent = optionTexts[code];
      });
    }

    function normalizeAppTheme(theme) {
      const normalized = String(theme || "").trim().toLowerCase();
      if (normalized === "day") return "light";
      return {night:1,light:1,paper:1,slate:1,ink:1,moss:1}[normalized] ? normalized : "night";
    }

    function loadSavedTheme() {
      try {
        return normalizeAppTheme(window.localStorage.getItem(APP_THEME_STORAGE_KEY));
      } catch (_) {
        return "night";
      }
    }

    function saveTheme(theme) {
      const normalized = normalizeAppTheme(theme);
      try {
        window.localStorage.setItem(APP_THEME_STORAGE_KEY, normalized);
      } catch (_) {}
      return normalized;
    }

    function syncShellThemeToggle() {
      const toggle = $("shellThemeToggle");
      const label = $("shellThemeToggleText");
      if (!toggle) return;
      const themeLabel = ({"night":"Night","ink":"Ink","moss":"Moss","light":"Light","paper":"Paper","slate":"Slate"})[appTheme] || appTheme;
      toggle.setAttribute("title", "Theme: " + themeLabel + " — click to cycle");
      toggle.setAttribute("aria-label", "Current theme: " + themeLabel + ". Click to cycle through themes.");
      if (label) {
        label.textContent = themeLabel;
      }
    }

    function applyAppTheme(theme = appTheme) {
      appTheme = saveTheme(theme);
      document.body.dataset.theme = appTheme;
      syncShellThemeToggle();
    }

    function toggleAppTheme() {
      const cycle = ["night","ink","moss","light","paper","slate"];
      const idx = cycle.indexOf(appTheme);
      applyAppTheme(cycle[(idx + 1) % cycle.length]);
    }

    function buildLocalizedToolDocHref(docKey) {
      const key = String(docKey || "").trim();
      if (!key) return "#";
      const params = new URLSearchParams();
      if (["manual", "erd-summary", "erd-detail", "go-live-checklist", "purchase-import"].includes(key) && appLocale !== "ko") {
        params.set("locale", appLocale);
      }
      const query = params.toString();
      return `/tool-docs/${encodeURIComponent(key)}${query ? `?${query}` : ""}`;
    }

    function syncLocalizedToolDocLinks() {
      document.querySelectorAll("[data-tool-doc-key]").forEach((el) => {
        const docKey = String(el.getAttribute("data-tool-doc-key") || "").trim();
        if (!docKey) return;
        el.setAttribute("href", buildLocalizedToolDocHref(docKey));
      });
    }

    function mediaDisplayLabel(value) {
      const raw = String(value || "").trim();
      if (!raw) return "-";
      const code = raw.toUpperCase();
      if (!MUSIC_CATEGORIES.has(code)) return raw;
      return MEDIA_DISPLAY_LABEL[code] || raw;
    }

    function mediaIconLabel(value) {
      const code = String(value || "").trim().toUpperCase();
      if (code === "LP") return "LP";
      if (code === "CD") return "CD";
      if (code === "CASSETTE") return "CS";
      if (code === "8TRACK") return "8T";
      if (code === "DIGITAL") return "DG";
      if (code === "REEL_TO_REEL") return "R2";
      const label = mediaDisplayLabel(code);
      return String(label || "-").slice(0, 2).toUpperCase();
    }

    function signatureTypeDisplayLabel(value) {
      const code = String(value || "").trim().toUpperCase();
      if (!code || code === "NONE") return t("common.signature.none");
      if (code === "IN_PERSON") return t("common.signature.in_person");
      if (code === "PURCHASE_INCLUDED") return t("common.signature.purchase_included");
      if (code === "UNKNOWN") return t("common.signature.unknown");
      return code;
    }

    function signatureIconLabel(value) {
      const code = String(value || "").trim().toUpperCase();
      if (code === "IN_PERSON") return t("common.signature_short.in_person");
      if (code === "PURCHASE_INCLUDED") return t("common.signature_short.purchase_included");
      if (code === "UNKNOWN") return "?";
      return "";
    }

    function signatureCoverBadgeHtml(value, extraClass = "") {
      const code = String(value || "").trim().toUpperCase();
      let toneClass = "";
      if (code === "IN_PERSON") toneClass = "cover-signature-badge--in-person";
      if (code === "PURCHASE_INCLUDED") toneClass = "cover-signature-badge--purchase-included";
      if (!toneClass) return "";
      const shortLabel = signatureIconLabel(code);
      if (!shortLabel) return "";
      const className = ["cover-signature-badge", toneClass, extraClass].filter(Boolean).join(" ");
      const title = t("dashboard.item.flag.signature", { value: signatureTypeDisplayLabel(code) });
      return `<span class="${className}" title="${escapeHtml(title)}">${escapeHtml(shortLabel)}</span>`;
    }

    function conditionIconLabel(prefix, value) {
      const normalized = normalizeConditionGradeValue(value);
      if (!normalized) return "";
      return `${prefix}/${normalized}`;
    }

    function statusIconLabel(value) {
      const code = String(value || "").trim().toUpperCase();
      if (code === "IN_COLLECTION") return "IN";
      if (code === "LOANED") return "LN";
      if (code === "SOLD") return "SO";
      if (code === "LOST") return "LS";
      if (code === "ARCHIVED") return "AR";
      return "";
    }

    function normalizeConditionGradeValue(value) {
      const raw = String(value || "").trim();
      if (!raw) return "";
      const code = raw
        .toUpperCase()
        .replaceAll(" ", "")
        .replaceAll("–", "-")
        .replaceAll("—", "-");
      if (code === "M" || code === "MINT") return "M";
      if (code === "NM" || code === "M-" || code === "NEARMINT") return "NM";
      if (code === "VG+" || code === "E" || code === "EX" || code === "EXCELLENT" || code === "VERYGOODPLUS") return "VG+";
      if (code === "VG" || code === "VERYGOOD") return "VG";
      if (code === "G+" || code === "VG-" || code === "GOODPLUS" || code === "VERYGOODMINUS") return "G+";
      if (code === "G" || code === "GOOD") return "G";
      if (code === "F" || code === "FAIR") return "F";
      if (code === "P" || code === "POOR") return "P";
      return raw;
    }

    function normalizePositiveIntOrNull(value) {
      if (value === null || value === undefined) return null;
      const text = String(value).trim();
      if (!text) return null;
      const parsed = Number(text);
      return Number.isFinite(parsed) && parsed > 0 ? Math.trunc(parsed) : null;
    }

    function normalizePurchasePriceOrNull(value) {
      if (value === null || value === undefined) return null;
      const text = String(value).trim();
      if (!text) return null;
      const parsed = Number(text.replaceAll(",", ""));
      return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
    }

    function normalizeCurrencyCodeOrNull(value, fallback = null) {
      const text = String(value || "").trim().toUpperCase();
      if (text) return text;
      const fallbackText = String(fallback || "").trim().toUpperCase();
      return fallbackText || null;
    }

    function splitCommaList(value) {
      if (Array.isArray(value)) {
        const out = [];
        const seen = new Set();
        for (const raw of value) {
          const text = String(raw || "").trim();
          if (!text) continue;
          const key = text.toLowerCase();
          if (seen.has(key)) continue;
          seen.add(key);
          out.push(text);
        }
        return out;
      }
      const text = String(value || "").trim();
      if (!text) return [];
      return splitCommaList(text.split(/[,|\n]/g).map((v) => String(v || "").trim()).filter((v) => v));
    }

    function joinCommaList(values) {
      const rows = splitCommaList(values);
      return rows.length ? rows.join(", ") : "";
    }

    function splitRunoutList(value) {
      if (Array.isArray(value)) {
        const out = [];
        for (const raw of value) {
          const text = String(raw || "").trim();
          if (text) out.push(text);
        }
        return out;
      }
      const text = String(value || "").trim();
      if (!text) return [];
      return text
        .split(/[|\n]/g)
        .map((v) => String(v || "").trim())
        .filter((v) => v);
    }

    function joinRunoutList(values) {
      const rows = splitRunoutList(values);
      return rows.length ? rows.join(" | ") : "";
    }

    function splitLineList(value) {
      if (Array.isArray(value)) {
        return value.map((v) => String(v || "").trim()).filter((v) => v);
      }
      const text = String(value || "").trim();
      if (!text) return [];
      return text
        .split(/\n/g)
        .map((v) => String(v || "").trim())
        .filter((v) => v);
    }

    function normalizeBarcodeLookupToken(value) {
      return String(value || "").replace(/[^0-9A-Za-z]+/g, "").toUpperCase();
    }

    function normalizeUrlList(values) {
      const out = [];
      const seen = new Set();
      const rows = Array.isArray(values) ? values : [];
      for (const raw of rows) {
        const text = String(raw || "").trim();
        if (!text) continue;
        if (seen.has(text)) continue;
        seen.add(text);
        out.push(text);
      }
      return out;
    }

    function normalizeCreditDisplay(value) {
      const text = String(value || "").trim();
      if (!text) return "";
      const match = text.match(/^(.+?)\s*\(([^)]+)\)\s*(\[[^\]]+\])?$/);
      if (!match) return text;
      const name = String(match[1] || "").trim();
      const role = String(match[2] || "").trim();
      const tracks = String(match[3] || "").trim();
      if (!name && !role) return text;
      return `${name || "-"}${role ? `/${role}` : ""}${tracks ? ` ${tracks}` : ""}`;
    }

    function formatIdentifierItem(row) {
      if (!row || typeof row !== "object" || Array.isArray(row)) return "";
      const type = String(row.type || row.kind || row.name || "").trim();
      const value = String(row.value || row.description || row.text || "").trim();
      if (type && value) return `${type}: ${value}`;
      return type || value || "";
    }

    function formatFormatItem(row) {
      if (!row || typeof row !== "object" || Array.isArray(row)) return "";
      const name = String(row.name || row.format_name || row.format || "").trim();
      const qtyRaw = String(row.qty ?? row.quantity ?? "").trim();
      const qtyText = qtyRaw && qtyRaw !== "1" ? ` x${qtyRaw}` : "";
      const descList = Array.isArray(row.descriptions)
        ? row.descriptions.map((v) => String(v || "").trim()).filter((v) => v)
        : (String(row.description || "").trim() ? [String(row.description || "").trim()] : []);
      const text = String(row.text || "").trim();
      const parts = [];
      if (name) parts.push(`${name}${qtyText}`);
      if (descList.length) parts.push(descList.join(", "));
      if (text) parts.push(text);
      if (!parts.length && qtyRaw) return `qty ${qtyRaw}`;
      return parts.join(" / ");
    }

    function formatOpsCollectorFormatItem(row) {
      return formatFormatItem(row);
    }

    function isRetryableFetchError(err) {
      const name = String(err?.name || "").trim();
      const message = String(err?.message || err || "").trim();
      if (name === "AbortError") return false;
      if (name === "TypeError") return true;
      return /failed to fetch|load failed|networkerror/i.test(message);
    }

    function escapeHtml(v) {
      return String(v ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function normalizeSourceCode(value) {
      return String(value || "").trim().toUpperCase();
    }

    function isDiscogsRepairCandidate({ ownedItemId, sourceCode, masterSourceCode, sourceExternalId }) {
      return Number(ownedItemId || 0) > 0
        && normalizeSourceCode(sourceCode) === "DISCOGS"
        && normalizeSourceCode(masterSourceCode) === "MANUAL"
        && Boolean(String(sourceExternalId || "").trim());
    }

    function formatCount(v) {
      return Number(v || 0).toLocaleString(currentLocaleTag());
    }

    function formatDateTimeCompact(value) {
      const text = String(value || "").trim();
      if (!text) return "-";
      const date = new Date(text);
      if (Number.isNaN(date.getTime())) return text;
      return date.toLocaleString(currentLocaleTag(), {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      });
    }

    function formatOperatorCardDateTime(value) {
      const text = String(value || "").trim();
      if (!text) return "-";
      const date = new Date(text);
      if (Number.isNaN(date.getTime())) return text;
      const yyyy = String(date.getFullYear()).padStart(4, "0");
      const mm = String(date.getMonth() + 1).padStart(2, "0");
      const dd = String(date.getDate()).padStart(2, "0");
      const hh = String(date.getHours()).padStart(2, "0");
      const min = String(date.getMinutes()).padStart(2, "0");
      return `${yyyy}.${mm}.${dd}. ${hh}:${min}`;
    }

    function normalizeDigits(value) {
      return String(value || "").replace(/\D+/g, "");
    }

    function normalizeOpsLookupQuery(input) {
      return String(input || "")
        .trim()
        .replace(/\s+/g, " ")
        .replace(/[\u200B-\u200D\uFEFF]/g, "");
    }

    function normalizeOpsLookupComparable(input) {
      return normalizeOpsLookupQuery(input).toLowerCase();
    }

    function isOperatorUnslottedLabel(value) {
      const normalized = String(value || "").trim();
      if (!normalized) return false;
      return normalized === "미배치"
        || normalized === "Unslotted"
        || normalized === "未配置"
        || normalized === t("operator.feed.state.unslotted");
    }


    function joinLineList(values) {
      const rows = splitLineList(values);
      return rows.length ? rows.join("\n") : "";
    }

    function extractUrlCandidates(value) {
      const text = String(value || "").trim();
      if (!text) return [];
      return text
        .split(/\s+/g)
        .map((v) => String(v || "").trim())
        .filter((v) => /^https?:\/\//i.test(v) || v.startsWith("/"));
    }

    function setHomeLinkedGoodsImageEntries(values) {
      homeLinkedGoodsImageEntries = normalizeUrlList(values);
      $("homeLinkedGoodsImageUrls").value = joinLineList(homeLinkedGoodsImageEntries);
      renderHomeLinkedGoodsImageList();
    }

    function addHomeLinkedGoodsImageEntries(values) {
      const merged = [...homeLinkedGoodsImageEntries, ...normalizeUrlList(values)];
      setHomeLinkedGoodsImageEntries(merged);
    }

    function clearHomeLinkedGoodsImages() {
      homeLinkedGoodsImageEntries = [];
      $("homeLinkedGoodsImageUrls").value = "";
      $("homeLinkedGoodsImagePaste").value = "";
      $("homeLinkedGoodsImageFiles").value = "";
      renderHomeLinkedGoodsImageList();
    }

    async function uploadUiImageFiles(fileList) {
      const files = Array.from(fileList || []).filter((f) => f);
      if (!files.length) return [];

      const uploadedUrls = [];
      for (const file of files) {
        const type = String(file.type || "").toLowerCase();
        if (type && !type.startsWith("image/")) {
          continue;
        }
        const form = new FormData();
        form.append("file", file, file.name || "image");
        const res = await fetch("/ui/upload-image", {
          method: "POST",
          body: form
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("common.request_failed"));
        const url = String(data.url || "").trim();
        if (url) uploadedUrls.push(url);
      }
      return uploadedUrls;
    }

    function setStatus(id, kind, text) {
      const el = $(id);
      if (!el) return;
      el.className = "status";
      if (!text) {
        el.textContent = "";
        return;
      }
      el.classList.add(kind === "err" ? "err" : "ok");
      el.textContent = text;
    }

    async function safeJson(res) {
      if (res.status === 401) {
        window.location.replace("/login");
        return { detail: "authentication required" };
      }
      const text = await res.text();
      if (!text) return {};
      try { return JSON.parse(text); } catch (_) { return { detail: text }; }
    }

    function buildClientRequestId() {
      const seed = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
      return seed.slice(0, 12);
    }

    async function fetchWithRetry(input, init = {}, options = {}) {
      const clientRequestId = String(options.requestId || buildClientRequestId()).trim();
      const retries = Math.max(0, Number(options.retries ?? 1) || 0);
      const retryDelayMs = Math.max(50, Number(options.retryDelayMs ?? 250) || 250);
      const onRetry = typeof options.onRetry === "function" ? options.onRetry : null;
      const headers = new Headers(init?.headers || {});
      if (clientRequestId && !headers.has("X-Client-Request-ID")) {
        headers.set("X-Client-Request-ID", clientRequestId);
      }
      const nextInit = { ...init, headers };
      for (let attempt = 0; ; attempt += 1) {
        try {
          return await fetch(input, nextInit);
        } catch (err) {
          if (!isRetryableFetchError(err) || attempt >= retries) {
            const errorMessage = detailText(err?.message ?? err) || t("common.request_failed");
            throw new Error(`${errorMessage} [ref: ${clientRequestId}]`);
          }
          if (onRetry) onRetry(attempt + 1, retries + 1, err);
          await new Promise((resolve) => window.setTimeout(resolve, retryDelayMs * (attempt + 1)));
        }
      }
    }

    function localizeServerDetailText(value) {
      const text = String(value || "").trim();
      if (!text) return "";
      if (text === "아이디 또는 비밀번호가 올바르지 않습니다.") return t("server.error.auth.invalid_credentials");
      if (text === "구매 항목에 상품 상세 URL이 없습니다.") return t("server.error.purchase.detail_url_missing");
      if (text === "현재는 Amazon/eBay 상품 상세 페이지만 보강할 수 있습니다.") return t("server.error.purchase.detail_page_unsupported");
      if (text === "구매 수입 큐 항목에서 후보 조회용 상품명/아티스트 정보를 찾지 못했습니다.") return t("server.error.purchase.lookup_query_missing");
      if (text === "이미 존재하는 계정입니다.") return t("server.error.account.exists");
      if (text === "계정을 찾을 수 없습니다.") return t("server.error.account.not_found");
      if (text === "관리 계정을 찾을 수 없습니다.") return t("server.error.account.managed_not_found");
      if (text === "계정 저장에 실패했습니다.") return t("server.error.account.save_failed");
      if (text === "계정 수정에 실패했습니다.") return t("server.error.account.update_failed");
      if (text === "계정 삭제에 실패했습니다.") return t("server.error.account.delete_failed");
      if (text === "유효한 ONVIF 장치 URL이 아닙니다.") return t("server.error.camera.invalid_url");
      if (text === "복구 파일의 SQLite 무결성 검사에 실패했습니다.") return t("server.error.restore.sqlite_integrity_failed");
      if (text === "복구 파일이 라이브러리 DB 형식이 아닙니다.") return t("server.error.restore.not_library_db");
      if (text === "복구 파일이 유효한 SQLite DB가 아닙니다.") return t("server.error.restore.invalid_sqlite");
      if (text === "메타 동기화 실행 중에는 DB 복구를 시작할 수 없습니다.") return t("server.error.restore.metadata_sync_running");
      if (text === "복구 파일이 유효한 ZIP 백업이 아닙니다.") return t("server.error.restore.invalid_zip");
      if (text === "복구 ZIP 파일이 손상되었습니다.") return t("server.error.restore.zip_corrupt");
      if (text === "복구 ZIP 파일 경로가 올바르지 않습니다.") return t("server.error.restore.zip_path_invalid");
      if (text === "복구 파일에 library.db가 없습니다.") return t("server.error.restore.zip_missing_db");
      if (text.startsWith("구매 내역 파일 디코딩 실패:")) {
        return t("server.error.purchase.decode_failed", { message: text.slice("구매 내역 파일 디코딩 실패:".length).trim() });
      }
      if (text.startsWith("ONVIF 응답 오류:")) {
        return t("server.error.camera.onvif_response", { status: text.slice("ONVIF 응답 오류:".length).trim() });
      }
      if (text.startsWith("ONVIF 연결 테스트 실패:")) {
        return t("server.error.camera.onvif_test_failed", { message: text.slice("ONVIF 연결 테스트 실패:".length).trim() });
      }
      if (text.startsWith("DB 복구 실패:")) {
        return t("server.error.restore.db_failed_detail", { message: text.slice("DB 복구 실패:".length).trim() });
      }
      if (text.startsWith("전체 백업 복구 실패:")) {
        return t("server.error.restore.bundle_failed_detail", { message: text.slice("전체 백업 복구 실패:".length).trim() });
      }
      return text;
    }

    function detailText(value) {
      if (value == null) return "";
      if (typeof value === "string") return localizeServerDetailText(value);
      if (Array.isArray(value)) {
        return value.map((row) => detailText(row)).filter((row) => row).join(" / ");
      }
      if (typeof value === "object") {
        const loc = Array.isArray(value.loc)
          ? value.loc.map((row) => String(row || "").trim()).filter((row) => row).join(".")
          : "";
        const msg = typeof value.msg === "string" ? localizeServerDetailText(value.msg) : "";
        if (loc || msg) return [loc, msg].filter((row) => row).join(": ");
        const detail = typeof value.detail === "string" ? localizeServerDetailText(value.detail) : "";
        if (detail) return detail;
        try {
          return JSON.stringify(value);
        } catch (_) {
          return String(value);
        }
      }
      return String(value || "").trim();
    }

    function responseDetailText(data, fallback) {
      return detailText(data?.detail) || fallback;
    }

    function errorMessageText(err, fallback = t("common.request_failed")) {
      return detailText(err?.message ?? err) || fallback;
    }

    function retryingStatusText(label, attempt, total) {
      return t("common.request_retrying", {
        label: String(label || "").trim() || t("common.request_failed"),
        attempt,
        total,
      });
    }

    function countWithUnit(v) {
      return t("common.count.items", { count: formatCount(v) });
    }

    function resolveOwnedAlbumName(row) {
      const name = String(row.item_name_override || "").trim();
      if (name) return name;
      const label = String(row.label_name || "").trim();
      const cat = String(row.catalog_no || "").trim();
      if (label || cat) return `${label || "Unknown Label"}${cat ? ` / ${cat}` : ""}`;
      return `${row.category || "ITEM"} #${row.id}`;
    }

    function normalizeRenderableCoverUrl(value) {
      const raw = String(value || "").trim();
      if (!raw) return "";
      return raw.replace(/^http:\/\/i\.maniadb\.com\//i, "https://i.maniadb.com/");
    }

    function resolveAlternateManiadbCoverUrl(value) {
      const normalized = normalizeRenderableCoverUrl(value);
      if (!normalized) return "";
      const currentMatch = normalized.match(/^(https:\/\/i\.maniadb\.com\/images\/album\/\d+\/\d+)_(\d+)_([fb])\.jpg$/i);
      if (currentMatch) {
        return `${currentMatch[1]}_${currentMatch[3]}_${currentMatch[2]}.jpg`;
      }
      const legacyMatch = normalized.match(/^(https:\/\/i\.maniadb\.com\/images\/album\/\d+\/\d+)_([fb])_(\d+)\.jpg$/i);
      if (legacyMatch) {
        return `${legacyMatch[1]}_${legacyMatch[3]}_${legacyMatch[2]}.jpg`;
      }
      return "";
    }

    function applyBrokenCoverFallback(img) {
      if (!(img instanceof HTMLImageElement)) return;
      const currentSrc = normalizeRenderableCoverUrl(img.currentSrc || img.src || img.getAttribute("src"));
      if (!currentSrc) return;
      const alternateSrc = resolveAlternateManiadbCoverUrl(currentSrc);
      if (alternateSrc && alternateSrc !== currentSrc && img.dataset.coverFallbackTried !== "1") {
        img.dataset.coverFallbackTried = "1";
        img.src = alternateSrc;
        return;
      }
      if (img.id === "imageGalleryPreviewImg") {
        img.removeAttribute("src");
        setDisplayMode(img, "none");
        $("imageGalleryOpenOriginal").href = "#";
        $("imageGalleryOpenOriginal").style.pointerEvents = "none";
        $("imageGalleryOpenOriginal").style.opacity = "0.45";
        $("imageGalleryPreviewMeta").innerHTML = `<span>${escapeHtml(t("common.no_cover"))}</span>`;
        return;
      }
      const coverHost = img.closest(".album-result-cover, .home-master-member-preview-cover, .table-cover-thumb, .dashboard-move-cover, .operator-cover, .image-gallery-thumb");
      if (!coverHost || coverHost.dataset.coverFallbackResolved === "1") return;
      coverHost.dataset.coverFallbackResolved = "1";
      coverHost.textContent = t("common.no_cover");
    }

    function resolveOwnedItemCoverUrl(row) {
      const primary = normalizeRenderableCoverUrl(row?.cover_image_url || row?.goods_primary_image_url);
      if (primary) return primary;
      return "";
    }

    function cleanLinkedGoodsMemoryNote(value) {
      const lines = String(value || "")
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => line && !/^\[LINKED_GOODS\]\s*/i.test(line));
      return lines.join(" / ");
    }

    function isMusicOwnedRow(row) {
      return MUSIC_CATEGORIES.has(String(row?.category || "").trim().toUpperCase());
    }

    function resolveAlbumMasterName(row) {
      const title = String(row?.title || "").trim();
      if (title) return title;
      const source = String(row?.source_code || "MASTER").trim();
      return `${source} master #${row?.id ?? "-"}`;
    }

    function normalizeLookupToken(value) {
      return String(value || "").replace(/[^0-9A-Za-z]/g, "").trim().toLowerCase();
    }


    function _labelHelpText(labelEl) {
      if (!labelEl) return "";
      const clone = labelEl.cloneNode(true);
      clone.querySelectorAll("input, select, textarea, button, .help-dot, .section-help-dot").forEach((el) => el.remove());
      const text = String(clone.textContent || "").replace(/\s+/g, " ").trim();
      if (text) return text;
      const spanText = String(labelEl.querySelector("span")?.textContent || "").replace(/\s+/g, " ").trim();
      return spanText;
    }

    const FIELD_HELP_MESSAGES = {
      ko: {
        aria: "필드 도움말",
        slot_id: "보관 슬롯 자체를 식별하는 내부 ID입니다. 새 슬롯 생성 시 비워두고, 기존 슬롯을 수정할 때 자동으로 채워집니다.",
        owned_item_id: "보유 상품 1건을 식별하는 내부 ID입니다. 수정, 삭제, 연계 작업의 기준값입니다.",
        album_master_id: "같은 앨범 묶음을 식별하는 내부 ID입니다. LP, CD, 카세트처럼 다른 상품을 하나의 앨범으로 연결할 때 사용합니다.",
        storage_slot: "실제 장식장 위치입니다. 장식장 등록에서 만든 장식장, 열, 칸 슬롯 중 하나를 선택합니다.",
        cabinet_name: "장식장 단위 이름입니다. 예: LP 주문제작장 01, CD 알루미늄장 03",
        floor_count: "이 장식장을 몇 개의 열로 나눌지 입력합니다. 입력한 수만큼 슬롯이 일괄 생성됩니다.",
        cell_count: "각 열에 몇 개의 칸을 만들지 입력합니다. 열 수와 곱해져 전체 슬롯 수가 결정됩니다.",
        floor_start: "열 번호 시작값입니다. 보통 1로 두고, 기존 번호 체계를 이어갈 때만 조정합니다.",
        cell_start: "칸 번호 시작값입니다. 보통 1로 두고, 기존 번호 체계를 이어갈 때만 조정합니다.",
        column_code: "장식장 안에서 위에서 아래로 내려가는 단위를 구분하는 열 번호입니다. 예: 01, 02, 03",
        cell_code: "해당 열 안에서 좌우 배치 위치를 구분하는 칸 번호입니다. 예: 01, 02, 03",
        domain_code: "장식장 대분류 기준입니다. 가요, 제이팝, 그 외 중 어디에 배치할지 정하는 값입니다.",
        release_type: "발매 성격 구분입니다. 정규 앨범, EP, 싱글처럼 앨범 단위 분류에 사용합니다.",
        size_group: "장식장에 들어가는 물리 규격입니다. CD, CD 확장형, LP, 10인치, 7인치, LP 박스셋, 카세트, 8-track, Reel-to-reel, 수집품을 구분합니다.",
        format_name: "내가 보유한 상품의 포맷입니다. LP, CD, Cassette 같은 실제 매체 구분입니다.",
        media_type: "원본 소스가 가진 매체 표기입니다. Discogs 등의 원문을 그대로 보존할 때 사용합니다.",
        released_date: "현재 선택한 상품 버전의 발매일입니다. 최초 발매일이 아니라 해당 버전 기준 날짜를 넣습니다.",
        barcode: "상품 식별용 바코드입니다. 최신 음반은 정확한 단건 조회에 가장 유효합니다.",
        catalog_no: "레이블이 붙인 발매 고유 번호입니다. 같은 앨범의 다른 버전을 구분할 때 중요합니다.",
        label_name: "발매사 또는 레이블 이름입니다. 카탈로그 번호와 함께 버전 구분의 핵심 기준입니다.",
        runout: "음반 데드왁스나 안쪽 링에 적힌 매트릭스 정보입니다. 같은 카탈로그 번호 내 세부 버전 구분에 유효합니다.",
        pressing_country: "이 상품이 실제로 프레싱된 국가입니다. 아티스트 국적이나 발매국과 다를 수 있습니다.",
        display_rank: "같은 위치권 안에서 화면상 노출 순서를 미세 조정할 때 쓰는 값입니다. 논리 순서(order_key) 보조용입니다.",
        purchase_source: "어디서 구했는지 기록합니다. 매장명, 사이트명, 행사 현장 같은 출처를 남길 때 사용합니다.",
        condition_grade: "커버/알판 개별 상태 외에 전체적으로 남길 컨디션 메모입니다. 예: 보관감 있음, 모서리 마모",
        memory_note: "구매 계기, 버전 특징, 기억할 만한 포인트를 자유롭게 적는 운영 메모입니다.",
        signature_type: "싸인 여부와 출처를 구분합니다. 직접 받았는지, 구매 시 포함이었는지 나눠 기록합니다.",
        meta_source: "메타를 어느 외부 소스에서 조회할지 정합니다. AUTO는 사용 가능한 소스를 순차적으로 사용합니다.",
        barcode_limit: "한 번에 불러올 메타 후보 수입니다. 결과가 많을 때 목록 길이를 조절합니다.",
        meta_query: "바코드가 없을 때 사용할 키워드입니다. 보통 아티스트명, 상품명, 카탈로그 번호를 함께 넣습니다.",
        artist: "아티스트명입니다. 조건 조회와 장식장 분류 기준으로 함께 사용합니다.",
        item_name: "화면과 리스트에 직접 보여줄 이름입니다. 필요하면 아티스트 - 상품명 형태로 정리합니다.",
        cover_condition: "중고 상품일 때 커버 상태를 따로 적습니다. 예: NM, VG+, 모서리 마모",
        disc_condition: "중고 상품일 때 알판이나 디스크 상태를 따로 적습니다. 예: EX, 스크래치 소량",
        cover_image_url: "대표 커버 이미지 주소입니다. 후보 교체 시 자동으로 채울 수 있고, 직접 교체할 수도 있습니다.",
        track_list: "트랙 목록입니다. 한 줄에 1곡씩 입력하며, 실제 상품 구성 확인용으로 관리합니다.",
        disc_count: "한 상품 안에 들어 있는 디스크 수입니다. 2LP, 2CD 같은 구성일 때 사용합니다.",
        speed_rpm: "LP나 싱글의 재생 속도입니다. 예: 33, 45",
        limited_edition: "음반의 한정 수량 에디션입니다. 체크 시 넘버링 항목이 활성화됩니다.",
        new_product: "개봉하지 않은 미개봉 새 상품입니다. 중고 여부를 구분하는 기준이 됩니다.",
        promo: "정규 판매용이 아닌 홍보 목적으로 제작된 음반입니다. 프로모 스탬프나 컷이 있는 경우가 많습니다.",
        sig_direct: "아티스트로부터 현장에서 직접 받은 친필 싸인입니다.",
        sig_purchase: "구매 시 앨범에 기본 포함된 인쇄 싸인입니다.",
        genre_missing: "장르 정보가 비어 있는 상품만 표시합니다.",
        format_missing: "미디어 포맷 정보가 없는 상품만 표시합니다.",
        catalog_missing: "카탈로그 번호가 없는 상품만 표시합니다.",
        checkbox: "{label} 여부를 설정합니다.",
        select: "{label} 값을 선택합니다.",
        textarea_with_example: "{label}을 입력합니다. 예: {example}",
        textarea: "{label}을 입력합니다.",
        number_with_example: "{label} 숫자를 입력합니다. 예: {example}",
        number: "{label} 숫자를 입력합니다.",
        input_with_example: "{label} 값을 입력합니다. 예: {example}",
        input: "{label} 값을 입력합니다.",
      },
      en: {
        aria: "Field help",
        slot_id: "This is the internal ID for the storage slot itself. Leave it blank for a new slot, and it fills automatically when editing an existing slot.",
        owned_item_id: "This is the internal ID for one owned item. It is the reference value for edit, delete, and link actions.",
        album_master_id: "This is the internal ID for one album grouping. Use it to connect LP, CD, cassette, and other variants under the same album.",
        storage_slot: "This is the actual cabinet location. Choose one of the cabinet, column, and cell slots created in cabinet setup.",
        cabinet_name: "This is the cabinet-level name. Example: LP custom cabinet 01, CD aluminum cabinet 03.",
        floor_count: "Enter how many columns this cabinet should have. That many slots are created in bulk.",
        cell_count: "Enter how many cells each column should have. Together with the column count, this determines the total slot count.",
        floor_start: "This is the starting column number. Usually keep it at 1 unless you are continuing an existing numbering scheme.",
        cell_start: "This is the starting cell number. Usually keep it at 1 unless you are continuing an existing numbering scheme.",
        column_code: "This is the column number inside the cabinet, used to distinguish vertical sections. Example: 01, 02, 03.",
        cell_code: "This is the cell number inside the selected column, used to distinguish left-right positions. Example: 01, 02, 03.",
        domain_code: "This is the cabinet domain grouping. It decides whether the cabinet is used for K-pop, J-pop, or another area.",
        release_type: "This is the release type. Use it to classify the album as a full album, EP, single, and so on.",
        size_group: "This is the physical storage size for the cabinet. It distinguishes CD, expanded CD, LP, 10-inch, 7-inch, LP box set, cassette, 8-track, reel-to-reel, and collectible.",
        format_name: "This is the format of the item you own. It is the actual media type such as LP, CD, or cassette.",
        media_type: "This is the media label from the source itself. Use it when preserving the original wording from Discogs or another provider.",
        released_date: "This is the release date of the currently selected product version. Enter the version date, not the first-ever release date.",
        barcode: "This is the product barcode. For modern releases it is usually the most reliable single-item lookup key.",
        catalog_no: "This is the release catalog number assigned by the label. It is important when distinguishing different versions of the same album.",
        label_name: "This is the label or publisher name. Together with the catalog number, it is a core clue for version identification.",
        runout: "This is the matrix or runout information written in the dead wax or inner ring. It helps distinguish detailed variants under the same catalog number.",
        pressing_country: "This is the country where this item was actually pressed. It can differ from the artist's country or release market.",
        display_rank: "Use this to fine-tune the on-screen order within the same location. It acts as a helper next to the logical order key.",
        purchase_source: "Record where the item came from. Use it for store names, websites, live events, and similar sources.",
        condition_grade: "This is the overall condition memo beyond separate cover/disc grades. Example: storage wear, corner wear.",
        memory_note: "This is a free-form operations note for purchase context, version traits, or anything worth remembering.",
        signature_type: "Use this to distinguish whether the item is signed and where the signature came from, such as signed in person or included at purchase.",
        meta_source: "Choose which external source to use for metadata lookup. AUTO tries available sources in sequence.",
        barcode_limit: "This is how many metadata candidates to load at once. Adjust it when result lists become too long.",
        meta_query: "This is the keyword query to use when no barcode is available. Usually combine artist name, item title, and catalog number.",
        artist: "This is the artist name. It is used together for lookup and cabinet classification.",
        item_name: "This is the display name shown in screens and lists. If needed, format it as Artist - Title.",
        cover_condition: "Use this to record the cover condition for second-hand items. Example: NM, VG+, corner wear.",
        disc_condition: "Use this to record the disc condition for second-hand items. Example: EX, light scratches.",
        cover_image_url: "This is the main cover image URL. It can be filled automatically during source replacement or changed manually.",
        track_list: "This is the track list. Enter one track per line for actual product composition reference.",
        disc_count: "This is the number of discs included in one product, such as 2LP or 2CD.",
        speed_rpm: "This is the playback speed for LPs and singles. Example: 33, 45.",
        limited_edition: "A limited-print edition. Checking this enables the edition numbering field.",
        new_product: "A sealed, never-opened item. This is the primary flag distinguishing new from used.",
        promo: "A release made for promotional use, not regular retail. Often stamped or cut.",
        sig_direct: "A handwritten signature received directly from the artist in person.",
        sig_purchase: "A printed or pre-applied signature included with the album at purchase.",
        genre_missing: "Show only items with no genre assigned.",
        format_missing: "Show only items with no media format assigned.",
        catalog_missing: "Show only items with no catalog number assigned.",
        checkbox: "Sets whether {label} is enabled.",
        select: "Select a value for {label}.",
        textarea_with_example: "Enter {label}. Example: {example}",
        textarea: "Enter {label}.",
        number_with_example: "Enter a number for {label}. Example: {example}",
        number: "Enter a number for {label}.",
        input_with_example: "Enter a value for {label}. Example: {example}",
        input: "Enter a value for {label}.",
      },
      ja: {
        aria: "フィールドヘルプ",
        slot_id: "保管スロット自体を識別する内部 ID です。新規スロット作成時は空欄のままにし、既存スロットを編集するときは自動入力されます。",
        owned_item_id: "保有商品 1 件を識別する内部 ID です。編集、削除、連携作業の基準値になります。",
        album_master_id: "同じアルバム束を識別する内部 ID です。LP、CD、カセットなど別商品を 1 つのアルバムとして結び付けるときに使います。",
        storage_slot: "実際のキャビネット位置です。キャビネット登録で作成したキャビネット・列・段のスロットから選択します。",
        cabinet_name: "キャビネット単位の名前です。例: LP 注文製作棚 01、CD アルミ棚 03。",
        floor_count: "このキャビネットを何列に分けるか入力します。入力した数だけスロットが一括生成されます。",
        cell_count: "各列に何段作るか入力します。列数と掛け合わせて全スロット数が決まります。",
        floor_start: "列番号の開始値です。通常は 1 のままにし、既存番号体系を続けるときだけ調整します。",
        cell_start: "段番号の開始値です。通常は 1 のままにし、既存番号体系を続けるときだけ調整します。",
        column_code: "キャビネット内で上下方向の区分を表す列番号です。例: 01、02、03。",
        cell_code: "その列の中で左右位置を区別する段番号です。例: 01、02、03。",
        domain_code: "キャビネットの大分類基準です。K-pop、J-pop、そのほかのどこへ配置するかを決めます。",
        release_type: "発売タイプの区分です。正規アルバム、EP、シングルなどアルバム単位の分類に使います。",
        size_group: "キャビネットに入る物理規格です。CD、拡張 CD、LP、10 インチ、7 インチ、LP ボックスセット、カセット、8-track、Reel-to-reel、コレクタブルを区別します。",
        format_name: "保有している商品のフォーマットです。LP、CD、Cassette など実際の媒体区分です。",
        media_type: "元ソースが持つ媒体表記です。Discogs などの原文表記をそのまま残したいときに使います。",
        released_date: "現在選択している商品バージョンの発売日です。初回発売日ではなく、そのバージョン基準の日付を入力します。",
        barcode: "商品の識別用バーコードです。最近の音源では単品照会で最も有効です。",
        catalog_no: "レーベルが付けた発売固有番号です。同じアルバムの別バージョンを区別するときに重要です。",
        label_name: "発売元またはレーベル名です。カタログ番号とあわせてバージョン判別の重要な基準になります。",
        runout: "盤のデッドワックスや内周リングに記載されたマトリクス情報です。同じカタログ番号内の細かなバージョン判別に有効です。",
        pressing_country: "この商品が実際にプレスされた国です。アーティスト国籍や発売国と異なる場合があります。",
        display_rank: "同じ位置圏内で画面表示順を微調整するための値です。論理順序(order_key)の補助として使います。",
        purchase_source: "どこで入手したかを記録します。店舗名、サイト名、イベント会場などの出所を残すときに使います。",
        condition_grade: "カバー/盤の個別状態とは別に残す全体コンディションメモです。例: 保管感あり、角スレ。",
        memory_note: "購入のきっかけ、バージョン特徴、覚えておきたいポイントを自由に書く運用メモです。",
        signature_type: "サインの有無と入手経路を区別します。直接受けたか、購入時に含まれていたかを分けて記録します。",
        meta_source: "どの外部ソースでメタデータを照会するかを選びます。AUTO は使えるソースを順に試します。",
        barcode_limit: "一度に読み込むメタ候補数です。結果が多いときに一覧の長さを調整します。",
        meta_query: "バーコードがないときに使うキーワードです。通常はアーティスト名、商品名、カタログ番号を一緒に入れます。",
        artist: "アーティスト名です。条件照会とキャビネット分類の両方に使います。",
        item_name: "画面や一覧に直接表示する名前です。必要ならアーティスト - 商品名の形で整えます。",
        cover_condition: "中古商品のカバー状態を別途記録します。例: NM、VG+、角スレ。",
        disc_condition: "中古商品の盤やディスク状態を別途記録します。例: EX、軽い擦り傷。",
        cover_image_url: "代表カバー画像 URL です。候補置換時に自動入力したり、手動で差し替えたりできます。",
        track_list: "トラック一覧です。1 行に 1 曲ずつ入力し、実際の商品構成確認用に管理します。",
        disc_count: "1 商品に含まれるディスク数です。2LP、2CD などの構成時に使います。",
        speed_rpm: "LP やシングルの再生速度です。例: 33、45。",
        limited_edition: "限定数量のエディションです。チェックするとナンバリング項目が有効になります。",
        new_product: "未開封の新品です。中古かどうかを区別する基準になります。",
        promo: "通常販売用ではなく、プロモーション目的で制作された音盤です。",
        sig_direct: "アーティストから直接もらった直筆サインです。",
        sig_purchase: "購入時にアルバムに含まれている印刷サインです。",
        genre_missing: "ジャンル情報がない商品のみ表示します。",
        format_missing: "メディアフォーマット情報がない商品のみ表示します。",
        catalog_missing: "カタログ番号がない商品のみ表示します。",
        checkbox: "{label} の有無を設定します。",
        select: "{label} の値を選択します。",
        textarea_with_example: "{label} を入力します。例: {example}",
        textarea: "{label} を入力します。",
        number_with_example: "{label} の数値を入力します。例: {example}",
        number: "{label} の数値を入力します。",
        input_with_example: "{label} の値を入力します。例: {example}",
        input: "{label} の値を入力します。",
      },
    };

    function fieldHelpT(key, params = {}) {
      const localeMessages = FIELD_HELP_MESSAGES[appLocale] || FIELD_HELP_MESSAGES.ko || {};
      const fallbackMessages = FIELD_HELP_MESSAGES.ko || {};
      const message = Object.prototype.hasOwnProperty.call(localeMessages, key)
        ? localeMessages[key]
        : fallbackMessages[key];
      if (typeof message !== "string") return key;
      return interpolateI18nMessage(message, params);
    }

    const FIELD_HELP_OVERRIDES = [
      {
        match: ({ id, label }) => id === "opsSlotId" || /slot_id/i.test(label),
        key: "slot_id",
      },
      {
        match: ({ id, label }) => /owned_item_id/i.test(label) || /OwnedId$/.test(id),
        key: "owned_item_id",
      },
      {
        match: ({ id, label }) => /album_master_id/i.test(label) || /연계 앨범 마스터 id/i.test(label) || /LinkedAlbumMasterId$/.test(id),
        key: "album_master_id",
      },
      {
        match: ({ id, label }) => /보관 슬롯/.test(label) || /SlotId$/.test(id),
        key: "storage_slot",
      },
      {
        match: ({ id, label }) => /장식장명/.test(label) || /CabinetName$/.test(id),
        key: "cabinet_name",
      },
      {
        match: ({ id, label }) => /열 수/.test(label) || /FloorCount$/.test(id),
        key: "floor_count",
      },
      {
        match: ({ id, label }) => /칸 수/.test(label) || /CellCount$/.test(id),
        key: "cell_count",
      },
      {
        match: ({ id, label }) => /열 시작/.test(label) || /FloorStart$/.test(id),
        key: "floor_start",
      },
      {
        match: ({ id, label }) => /칸 시작/.test(label) || /CellStart$/.test(id),
        key: "cell_start",
      },
      {
        match: ({ id, label }) => label === "열" || /ColumnCode$/.test(id),
        key: "column_code",
      },
      {
        match: ({ id, label }) => label === "칸" || /CellCode$/.test(id),
        key: "cell_code",
      },
      {
        match: ({ id, label }) => /도메인/.test(label) || /DomainCode$/.test(id),
        key: "domain_code",
      },
      {
        match: ({ id, label }) => /^타입$/.test(label) || /ReleaseType$/.test(id),
        key: "release_type",
      },
      {
        match: ({ id, label }) => /보관 규격/.test(label) || /SizeGroup$/.test(id),
        key: "size_group",
      },
      {
        match: ({ id, label }) => /^포맷$/.test(label) || /FormatName$/.test(id),
        key: "format_name",
      },
      {
        match: ({ id, label }) => /미디어 타입/.test(label) || /MediaType$/.test(id),
        key: "media_type",
      },
      {
        match: ({ id, label }) => /^발매일$/.test(label) || /ReleasedDate$/.test(id),
        key: "released_date",
      },
      {
        match: ({ id, label }) => /바코드/.test(label) || /Barcode/.test(id),
        key: "barcode",
      },
      {
        match: ({ id, label }) => /카탈로그 번호|카탈로그번호|cat#/.test(label) || /Catalog/.test(id),
        key: "catalog_no",
      },
      {
        match: ({ id, label }) => /^레이블$/.test(label) || /LabelName$/.test(id),
        key: "label_name",
      },
      {
        match: ({ id, label }) => /런아웃/.test(label) || /Runout/.test(id),
        key: "runout",
      },
      {
        match: ({ id, label }) => /프레싱 국가/.test(label) || /PressingCountry$/.test(id),
        key: "pressing_country",
      },
      {
        match: ({ id, label }) => /진열 순서/.test(label) || /DisplayRank$/.test(id),
        key: "display_rank",
      },
      {
        match: ({ id, label }) => /구매처/.test(label) || /PurchaseSource$/.test(id),
        key: "purchase_source",
      },
      {
        match: ({ id, label }) => /일반 컨디션 메모/.test(label) || /ConditionGrade$/.test(id),
        key: "condition_grade",
      },
      {
        match: ({ id, label }) => /기억 메모|메모/.test(label) || /MemoryNote$/.test(id),
        key: "memory_note",
      },
      {
        match: ({ id, label }) => /싸인 유형/.test(label) || /SignatureType$/.test(id),
        key: "signature_type",
      },
      {
        match: ({ id, label }) => /검색 소스/.test(label) || /MetaSource/.test(id) || /metaSourceFilter/.test(id),
        key: "meta_source",
      },
      {
        match: ({ id, label }) => /^개수$/.test(label) || /barcodeLimit/.test(id),
        key: "barcode_limit",
      },
      {
        match: ({ id, label }) => /조회어/.test(label) || /MetaQuery$/.test(id),
        key: "meta_query",
      },
      {
        match: ({ id, label }) => /^아티스트/.test(label) || /Artist/.test(id),
        key: "artist",
      },
      {
        match: ({ id, label }) => /표시명/.test(label) || /ItemName$/.test(id),
        key: "item_name",
      },
      {
        match: ({ id, label }) => /커버 컨디션/.test(label) || /CoverCondition$/.test(id),
        key: "cover_condition",
      },
      {
        match: ({ id, label }) => /알판 컨디션/.test(label) || /DiscCondition$/.test(id),
        key: "disc_condition",
      },
      {
        match: ({ id, label }) => /커버 이미지 URL/.test(label) || /CoverImageUrl$/.test(id),
        key: "cover_image_url",
      },
      {
        match: ({ id, label }) => /곡 리스트/.test(label) || /TrackList$/.test(id),
        key: "track_list",
      },
      {
        match: ({ id, label }) => /디스크 수/.test(label) || /DiscCount$/.test(id),
        key: "disc_count",
      },
      {
        match: ({ id, label }) => /RPM/.test(label) || /SpeedRpm$/.test(id),
        key: "speed_rpm",
      },
      {
        match: ({ id, label }) => /한정판|Limited/.test(label) || /LimitEd|LimitedEdition/.test(id),
        key: "limited_edition",
      },
      {
        match: ({ id, label }) => /새상품/.test(label) || /NewProduct/.test(id),
        key: "new_product",
      },
      {
        match: ({ id, label }) => /홍보반/.test(label) || /Promo/.test(id),
        key: "promo",
      },
      {
        match: ({ id, label }) => /^직접$/.test(label) || /SigDirect/.test(id),
        key: "sig_direct",
      },
      {
        match: ({ id, label }) => /^구매$/.test(label) || /SigPurchase/.test(id),
        key: "sig_purchase",
      },
      {
        match: ({ id, label }) => /장르 없음/.test(label) || /GenreMissing/.test(id),
        key: "genre_missing",
      },
      {
        match: ({ id, label }) => /미디어 없음/.test(label) || /FormatMissing/.test(id),
        key: "format_missing",
      },
      {
        match: ({ id, label }) => /카탈로그 없음/.test(label) || /CatalogMissing/.test(id),
        key: "catalog_missing",
      },
    ];

    function _fieldHelpOverride(labelText, controlEl) {
      const info = {
        id: String(controlEl?.id || "").trim(),
        label: String(labelText || "").replace(/\s+/g, " ").trim(),
      };
      for (const item of FIELD_HELP_OVERRIDES) {
        if (item.match(info)) return fieldHelpT(item.key);
      }
      return "";
    }

    function trimFieldHelpExamplePrefix(value) {
      return String(value || "").trim().replace(/^(예:|e\\.g\\.?[:]?|例[:：]?)\s*/i, "").trim();
    }

    function _fieldHelpFromLabel(labelText, controlEl) {
      const label = String(labelText || "").replace(/\s+/g, " ").trim();
      if (!label || !controlEl) return "";
      const overrideText = _fieldHelpOverride(label, controlEl);
      if (overrideText) return overrideText;
      const placeholderRaw = String(controlEl.getAttribute("placeholder") || "").trim();
      const placeholder = trimFieldHelpExamplePrefix(placeholderRaw);

      const tag = String(controlEl.tagName || "").toUpperCase();
      const type = String(controlEl.getAttribute("type") || "").toLowerCase();
      if (type === "checkbox" || type === "radio") {
        return fieldHelpT("checkbox", { label });
      }
      if (tag === "SELECT") {
        return fieldHelpT("select", { label });
      }
      if (tag === "TEXTAREA") {
        return placeholder
          ? fieldHelpT("textarea_with_example", { label, example: placeholder })
          : fieldHelpT("textarea", { label });
      }
      if (type === "number") {
        return placeholder
          ? fieldHelpT("number_with_example", { label, example: placeholder })
          : fieldHelpT("number", { label });
      }
      return placeholder
        ? fieldHelpT("input_with_example", { label, example: placeholder })
        : fieldHelpT("input", { label });
    }

    function _ensureFieldHelpBubble(labelEl, helpText) {
      if (!labelEl || !helpText) return;
      if (labelEl.classList.contains("option-pill")) return;
      let badge = labelEl.querySelector(".help-dot");
      if (!badge) {
        badge = document.createElement("span");
        badge.className = "help-dot";
        badge.textContent = "?";
        badge.setAttribute("tabindex", "-1");
        badge.setAttribute("role", "button");
        badge.setAttribute("aria-label", fieldHelpT("aria"));
        labelEl.appendChild(badge);
      }
      badge.setAttribute("data-help", helpText);
      badge.setAttribute("title", helpText);
      badge.setAttribute("tabindex", "-1");
      badge.setAttribute("aria-label", fieldHelpT("aria"));
    }

    function removeHelpDotsFromTabOrder(scope = document) {
      const root = scope && scope.querySelectorAll ? scope : document;
      root.querySelectorAll(".help-dot, .section-help-dot").forEach((badge) => {
        badge.setAttribute("tabindex", "-1");
      });
    }

    function applyFieldHelpTooltips(scope = document) {
      const root = scope && scope.querySelectorAll ? scope : document;
      const labels = Array.from(root.querySelectorAll("label"));
      for (const labelEl of labels) {
        const _i18nTitleKey = String(labelEl.getAttribute("data-i18n-title") || "").trim();
        if (_i18nTitleKey) {
          const _customHelp = t(_i18nTitleKey);
          if (_customHelp && _customHelp !== _i18nTitleKey) {
            const _ctrl = labelEl.querySelector("input, select, textarea");
            _ensureFieldHelpBubble(labelEl, _customHelp);
            if (_ctrl) _ctrl.setAttribute("title", _customHelp);
            labelEl.setAttribute("title", _customHelp);
            continue;
          }
        }
        const _pkgTipOpt = String(labelEl.getAttribute("data-packaging-tip") || "").trim();
        if (_pkgTipOpt) {
          const _lang = document.documentElement.getAttribute("data-lang") || "ko";
          const _allPkgTips = (typeof PACKAGING_TOOLTIPS !== "undefined" && PACKAGING_TOOLTIPS) || {};
          const _langTips = _allPkgTips[_lang] || _allPkgTips.ko || {};
          let _pkgHelp = "";
          for (const _mt in _langTips) { if (_langTips[_mt][_pkgTipOpt]) { _pkgHelp = _langTips[_mt][_pkgTipOpt]; break; } }
          if (_pkgHelp) {
            const _ctrl = labelEl.querySelector("input, select, textarea");
            _ensureFieldHelpBubble(labelEl, _pkgHelp);
            if (_ctrl) _ctrl.setAttribute("title", _pkgHelp);
            labelEl.setAttribute("title", _pkgHelp);
            continue;
          }
        }
        const htmlFor = String(labelEl.getAttribute("for") || "").trim();
        let controlEl = null;
        if (htmlFor) {
          controlEl = document.getElementById(htmlFor);
        }
        if (!controlEl) {
          controlEl = labelEl.querySelector("input, select, textarea");
        }
        if (!controlEl) continue;

        const labelText = _labelHelpText(labelEl);
        const helpText = _fieldHelpFromLabel(labelText, controlEl);
        if (!helpText) continue;

        _ensureFieldHelpBubble(labelEl, helpText);
        controlEl.setAttribute("title", helpText);
        labelEl.setAttribute("title", helpText);
      }
      removeHelpDotsFromTabOrder(root);
    }


    function discogsRepairButtonHtml(scope, ownedItemId) {
      const id = Number(ownedItemId || 0);
      if (id <= 0) return "";
      if (scope === "home") {
        return `<button class="btn ghost tiny home-master-member-preview-repair-btn" type="button" data-home-repair-discogs-master="${id}">${escapeHtml(t("media.manage.search.repair_discogs_master"))}</button>`;
      }
      return `<button class="btn ghost tiny operator-recent-repair-btn" type="button" data-operator-repair-discogs-master="${id}">${escapeHtml(t("operator.feed.action.repair_discogs_master"))}</button>`;
    }

    function discogsRepairSlotHtml(scope, { ownedItemId, sourceCode, masterSourceCode, sourceExternalId }) {
      if (!isDiscogsRepairCandidate({ ownedItemId, sourceCode, masterSourceCode, sourceExternalId })) return "";
      const id = Number(ownedItemId || 0);
      const slotClassName = scope === "home" ? "home-master-member-preview-repair-slot" : "operator-recent-actions";
      const scopeAttr = scope === "home" ? `data-home-discogs-repair-slot="${id}"` : `data-operator-discogs-repair-slot="${id}"`;
      return `<div class="${slotClassName}" ${scopeAttr} data-discogs-repair-slot-scope="${escapeHtml(scope)}" data-owned-item-id="${id}" data-source-code="${escapeHtml(normalizeSourceCode(sourceCode))}" data-master-source-code="${escapeHtml(normalizeSourceCode(masterSourceCode))}" data-source-external-id="${escapeHtml(String(sourceExternalId || "").trim())}"></div>`;
    }

    async function loadDiscogsRepairEligibilityStatus(ownedItemId, options = {}) {
      const id = Number(ownedItemId || 0);
      if (!isDiscogsRepairCandidate({
        ownedItemId: id,
        sourceCode: options?.sourceCode,
        masterSourceCode: options?.masterSourceCode,
        sourceExternalId: options?.sourceExternalId,
      })) {
        return { eligible: false, reason: "not_candidate" };
      }
      const cached = discogsRepairEligibilityCache.get(id);
      if (cached?.status) return cached.status;
      if (cached?.promise) return cached.promise;
      const promise = (async () => {
        try {
          const res = await fetchWithRetry(`/owned-items/${id}/discogs-repair-status`, {}, {
            retries: 1,
            retryDelayMs: 200,
          });
          const data = await safeJson(res);
          const status = {
            eligible: Boolean(res.ok && data?.eligible === true),
            reason: String(data?.reason || "").trim() || (res.ok ? "discogs_master_not_found" : "unavailable"),
          };
          discogsRepairEligibilityCache.set(id, { status });
          return status;
        } catch (_err) {
          const status = { eligible: false, reason: "unavailable" };
          discogsRepairEligibilityCache.set(id, { status });
          return status;
        }
      })();
      discogsRepairEligibilityCache.set(id, { promise });
      return promise;
    }

    async function hydrateDiscogsRepairButtons(root = document) {
      const scopeRoot = root && typeof root.querySelectorAll === "function" ? root : document;
      const slots = Array.from(scopeRoot.querySelectorAll("[data-discogs-repair-slot-scope]"));
      if (!slots.length) return;
      await Promise.all(slots.map(async (slot) => {
        if (!slot || slot.dataset.repairHydrated === "1") return;
        slot.dataset.repairHydrated = "1";
        const ownedItemId = Number(slot.getAttribute("data-owned-item-id") || 0);
        const sourceCode = slot.getAttribute("data-source-code") || "";
        const masterSourceCode = slot.getAttribute("data-master-source-code") || "";
        const sourceExternalId = slot.getAttribute("data-source-external-id") || "";
        const scope = String(slot.getAttribute("data-discogs-repair-slot-scope") || "").trim() || "operator";
        const status = await loadDiscogsRepairEligibilityStatus(ownedItemId, {
          sourceCode,
          masterSourceCode,
          sourceExternalId,
        });
        if (!slot.isConnected) return;
        if (!status?.eligible) {
          slot.remove();
          return;
        }
        slot.innerHTML = discogsRepairButtonHtml(scope, ownedItemId);
      }));
    }

    function queueDiscogsRepairEligibilityHydration(root = document) {
      window.requestAnimationFrame(() => {
        hydrateDiscogsRepairButtons(root).catch(() => {});
      });
    }

    function discogsReleaseUrl(externalId) {
      const id = String(externalId || "").trim();
      if (!id) return "";
      return `https://www.discogs.com/release/${encodeURIComponent(id)}`;
    }

    function discogsReleaseLinkHtml(sourceCode, externalId, label = "Discogs") {
      if (normalizeSourceCode(sourceCode) !== "DISCOGS") return "";
      const href = discogsReleaseUrl(externalId);
      if (!href) return "";
      return `<a href="${href}" target="_blank" rel="noreferrer noopener">${escapeHtml(label)}</a>`;
    }

    function discogsMasterLinkHtml(masterSourceId, label = "Discogs 마스터") {
      const id = String(masterSourceId || "").trim();
      if (!id) return "";
      return `<a href="https://www.discogs.com/master/${encodeURIComponent(id)}" target="_blank" rel="noreferrer noopener">${escapeHtml(label)}</a>`;
    }

    function maniadbAlbumLinkHtml(albumId, label = "ManiaDB 앨범") {
      // 마스터(앨범) 수준 링크 — 쿼리 파라미터 없음
      const id = String(albumId || "").trim();
      if (!id) return "";
      return `<a href="http://www.maniadb.com/album/${encodeURIComponent(id)}" target="_blank" rel="noreferrer noopener">${escapeHtml(label)}</a>`;
    }
    function itemSourceLinkHtml(sourceCode, externalId, label) {
      const source = normalizeSourceCode(sourceCode);
      const id = String(externalId || "").trim();
      if (!id) return "";
      if (source === "DISCOGS") {
        return discogsReleaseLinkHtml(sourceCode, externalId, label || "Discogs");
      }
      if (source === "MANIADB") {
        // external_id 형식: "{album_id}" 또는 "{album_id}:{variant_seq}"
        // URL: maniadb.com/album/{album_id}?o=l&s={variant_seq}
        const colonIdx = id.indexOf(":");
        const albumId = colonIdx >= 0 ? id.slice(0, colonIdx).trim() : id;
        const variantSeq = colonIdx >= 0 ? id.slice(colonIdx + 1).trim() : "";
        if (!albumId) return "";
        const href = variantSeq
          ? `http://www.maniadb.com/album/${encodeURIComponent(albumId)}?o=l&s=${encodeURIComponent(variantSeq)}`
          : `http://www.maniadb.com/album/${encodeURIComponent(albumId)}`;
        return `<a href="${href}" target="_blank" rel="noreferrer noopener">${escapeHtml(label || "ManiaDB")}</a>`;
      }
      if (source === "ALADIN") {
        return `<a href="https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=${encodeURIComponent(id)}" target="_blank" rel="noreferrer noopener">${escapeHtml(label || "Aladin")}</a>`;
      }
      return "";
    }

    function buildDiscogsStandardMetaHtml(row, opts = {}) {
      const sourceCode = normalizeSourceCode(row?.source || "");
      if (!sourceCode) return "";
      const includeOwnedCount = opts.includeOwnedCount === true;
      const ownedCountClassName = String(opts.ownedCountClassName || "").trim();
      const releaseDate = String(row?.released_date || row?.release_year || "").trim() || "-";
      const releaseCountry = String(row?.pressing_country || row?.country || "").trim() || "-";
      const labelName = String(row?.label_name || "").trim() || "-";
      const catalogNo = String(row?.catalog_no || "").trim() || "-";
      const barcode = String(row?.barcode || "").trim() || "-";
      const formatLabel = mediaDisplayLabel(row?.format_name || row?.category || row?.media_type || "-");
      const trackCount = Array.isArray(row?.track_list)
        ? row.track_list.length
        : Math.max(0, Number(row?.track_count || row?.tracks || 0));
      const parts = [
        t("common.meta.release_date", { value: escapeHtml(releaseDate) }),
        t("common.meta.release_country", { value: escapeHtml(releaseCountry) }),
        t("common.meta.label", { value: escapeHtml(labelName) }),
        t("common.meta.catalog_no", { value: escapeHtml(catalogNo) }),
        t("common.meta.barcode", { value: escapeHtml(barcode) }),
        t("common.meta.format", { value: escapeHtml(formatLabel) }),
        t("common.meta.track_count", { value: escapeHtml(String(trackCount)) }),
      ];
      if (includeOwnedCount && Number(row?.owned_count || 0) > 0) {
        const ownedText = escapeHtml(t("common.meta.already_owned", { count: formatCount(Number(row.owned_count || 0)) }));
        parts.push(ownedCountClassName
          ? `<span class="${escapeHtml(ownedCountClassName)}">${ownedText}</span>`
          : `<span>${ownedText}</span>`);
      }
      return parts.map((text) => text.startsWith("<span") ? text : `<span>${text}</span>`).join("");
    }

    function collectGalleryItems(row) {
      const out = [];
      const seen = new Set();
      const push = (url, thumb, label, type = "IMAGE") => {
        const src = normalizeRenderableCoverUrl(url);
        if (!src || seen.has(src)) return;
        seen.add(src);
        const normalizedThumb = normalizeRenderableCoverUrl(thumb) || src;
        out.push({
          url: src,
          thumb: normalizedThumb,
          label: String(label || "").trim() || t("common.image"),
          type: String(type || "IMAGE").trim().toUpperCase(),
        });
      };

      const coverUrl = normalizeRenderableCoverUrl(row?.cover_image_url);
      if (coverUrl) push(coverUrl, coverUrl, t("image_gallery.label.cover"), "COVER");

      const imageItems = Array.isArray(row?.image_items) ? row.image_items : [];
      for (const item of imageItems) {
        if (!item || typeof item !== "object") continue;
        const url = normalizeRenderableCoverUrl(item.uri || item.url || item.resource_url);
        const thumb = normalizeRenderableCoverUrl(item.uri150 || item.thumb || item.thumbnail_url || url);
        const type = String(item.type || item.kind || "IMAGE").trim().toUpperCase();
        const label = type === "PRIMARY"
          ? t("image_gallery.label.primary")
          : (type === "SECONDARY" ? t("image_gallery.label.secondary") : type);
        push(url, thumb, label, type);
      }
      return out;
    }

    function imageGalleryButtonHtml(key, label = "") {
      const galleryKey = String(key || "").trim();
      if (!galleryKey) return "";
      return `<button class="btn ghost image-gallery-open-btn" type="button" data-open-image-gallery="${escapeHtml(galleryKey)}">${escapeHtml(label || t("common.image"))}</button>`;
    }

    function renderImageGalleryModal() {
      const items = Array.isArray(imageGalleryCurrentItems) ? imageGalleryCurrentItems : [];
      const current = items[imageGalleryCurrentIndex] || null;
      $("imageGalleryPreviewImg").src = current?.url || "";
      setDisplayMode($("imageGalleryPreviewImg"), current?.url ? "block" : "none");
      $("imageGalleryPreviewImg").alt = current?.label || t("image_gallery.preview.alt");
      $("imageGallerySourceText").textContent = imageGalleryRegistry.get(imageGalleryCurrentKey)?.subtitle || t("image_gallery.subtitle.default");
      $("imageGalleryCountText").textContent = t("common.count.images", { count: items.length });
      $("imageGalleryOpenOriginal").href = current?.url || "#";
      $("imageGalleryOpenOriginal").style.pointerEvents = current?.url ? "auto" : "none";
      $("imageGalleryOpenOriginal").style.opacity = current?.url ? "1" : "0.45";
      $("imageGalleryPreviewMeta").innerHTML = current
        ? [
            `<span class="tag">${escapeHtml(current.label || t("common.image"))}</span>`,
            `<span>${escapeHtml(current.type || t("common.image"))}</span>`,
            `<span>${escapeHtml(current.url)}</span>`,
          ].join("")
        : `<span>${escapeHtml(t("image_gallery.meta.empty"))}</span>`;
      $("imageGalleryList").innerHTML = items.map((item, idx) => `
        <button class="image-gallery-thumb ${idx === imageGalleryCurrentIndex ? "active" : ""}" type="button" data-image-gallery-index="${idx}">
          <img src="${escapeHtml(item.thumb || item.url)}" alt="${escapeHtml(item.label || t("common.image"))}" />
          <div>
            <strong class="image-gallery-thumb-label">${escapeHtml(item.label || t("common.image"))}</strong>
            <div class="mini">${escapeHtml(item.type || t("common.image"))}</div>
          </div>
        </button>
      `).join("");
    }

    function openImageGallery(key) {
      const galleryKey = String(key || "").trim();
      const entry = imageGalleryRegistry.get(galleryKey);
      if (!entry || !Array.isArray(entry.items) || !entry.items.length) return;
      imageGalleryCurrentKey = galleryKey;
      imageGalleryCurrentItems = entry.items.slice();
      imageGalleryCurrentIndex = 0;
      $("imageGalleryTitle").textContent = entry.title || t("image_gallery.title.default");
      $("imageGalleryModal").classList.add("open");
      $("imageGalleryModal").setAttribute("aria-hidden", "false");
      renderImageGalleryModal();
    }

    function closeImageGallery() {
      imageGalleryCurrentKey = "";
      imageGalleryCurrentItems = [];
      imageGalleryCurrentIndex = 0;
      $("imageGalleryModal").classList.remove("open");
      $("imageGalleryModal").setAttribute("aria-hidden", "true");
    }

    function currentLocaleTag() {
      if (appLocale === "en") return "en-US";
      if (appLocale === "ja") return "ja-JP";
      return "ko-KR";
    }
