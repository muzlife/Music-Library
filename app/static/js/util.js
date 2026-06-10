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
