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
