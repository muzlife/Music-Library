
    function resetOpsAuthForm() {
      opsAuthSelectedUsername = "";
      $("opsAuthDisplayName").value = "";
      $("opsAuthUsername").value = "";
      $("opsAuthPassword").value = "";
      $("opsAuthDescription").value = "";
      $("opsAuthRole").value = "OPERATOR";
      $("opsAuthIsActive").checked = true;
      $("opsAuthUsername").disabled = false;
      $("opsAuthRole").disabled = false;
      $("opsAuthIsActive").disabled = false;
      $("opsAuthPassword").disabled = false;
      $("opsAuthSaveBtn").disabled = false;
      $("opsAuthDeleteBtn").disabled = true;
      $("acctUserPermPanel").style.display = "none";
      $("permAccountSelect").value = "";
      setStatus("opsAuthStatus", "ok", "");
    }

    function fillOpsAuthForm(row) {
      opsAuthSelectedUsername = String(row?.username || "").trim();
      $("opsAuthDisplayName").value = String(row?.display_name || "").trim();
      $("opsAuthUsername").value = opsAuthSelectedUsername;
      $("opsAuthPassword").value = "";
      $("opsAuthDescription").value = String(row?.description || "").trim();
      $("opsAuthRole").value = String(row?.role || "OPERATOR").trim().toUpperCase() || "OPERATOR";
      $("opsAuthIsActive").checked = row?.is_active !== false;
      const editable = row?.editable !== false;
      $("opsAuthUsername").disabled = true;
      $("opsAuthRole").disabled = !editable;
      $("opsAuthIsActive").disabled = !editable;
      $("opsAuthPassword").disabled = !editable;
      $("opsAuthSaveBtn").disabled = !editable;
      $("opsAuthDeleteBtn").disabled = !editable || String(row?.source || "").trim().toUpperCase() !== "MANAGED";
      setStatus("opsAuthStatus", "ok", t("ops.account.state.selected", { username: opsAuthSelectedUsername }));
      const role = String(row?.role || "").toUpperCase();
      if (["OPERATOR", "CAFE_STAFF"].includes(role)) {
        $("acctUserPermPanel").style.display = "";
        $("permAccountSelect").value = opsAuthSelectedUsername;
        if (!_permData) loadPermissionData().then(() => loadAccountPermissions(opsAuthSelectedUsername));
        else loadAccountPermissions(opsAuthSelectedUsername);
      } else {
        $("acctUserPermPanel").style.display = "none";
        $("permAccountSelect").value = "";
      }
    }

    function renderOpsAuthTable() {
      const body = $("opsAuthTableBody");
      if (!body) return;
      const ROLE_LABELS = { ADMIN: "관리자", OPERATOR: "운영자", CAFE_STAFF: "스텝" };
      body.innerHTML = (Array.isArray(opsAuthItems) ? opsAuthItems : []).map((row) => {
        const username = String(row.username || "").trim();
        const selected = username && username === opsAuthSelectedUsername;
        const displayName = String(row.display_name || "").trim() || "—";
        const roleLabel = ROLE_LABELS[String(row.role || "").trim().toUpperCase()] || String(row.role || "-").trim();
        return `
          <tr data-ops-auth-username="${escapeHtml(username)}" class="${selected ? "pick" : ""}">
            <td>${escapeHtml(displayName)}</td>
            <td>${escapeHtml(username)}</td>
            <td>${escapeHtml(roleLabel)}</td>
            <td>${escapeHtml(row.is_active === false ? t("common.state.inactive") : t("common.state.active"))}</td>
            <td>${escapeHtml(row.editable ? t("common.answer.yes") : t("common.state.read_only"))}</td>
            <td>${escapeHtml(formatDateTimeCompact(row.updated_at || row.created_at || ""))}</td>
          </tr>
        `;
      }).join("") || `<tr><td colspan='6' class='mini muted'>${escapeHtml(t("ops.account.table.state.empty"))}</td></tr>`;
    }
    let _permData = null;
    let _permAccountEffective = null;

    const PERM_ROLE_LABELS = { OPERATOR: "카페 매니저", CAFE_STAFF: "카페 운영자" };
    const PERM_KEY_LABELS = {
      "ops.feed": "피드 보기", "ops.search": "카탈로그 검색",
      "ops.location": "위치 확인", "ops.requests": "요청곡 관리",
      "ops.playback": "음악 재생", "ops.move_item": "아이템 이동",
      "ops.edit_item": "아이템 편집", "ops.cabinet": "장식장 관리",
      "ops.exception_queue": "예외 큐", "hr.manage_staff": "스태프 계정 관리",
    };

    function renderRoleMatrix() {
      const el = $("permRoleMatrix");
      if (!el || !_permData) return;
      const perms = _permData.permissions || [];
      const defaults = _permData.role_defaults || {};
      const roles = ["OPERATOR", "CAFE_STAFF"];
      el.innerHTML = `
        <div style="overflow-x:auto;">
          <table style="min-width:460px;border-collapse:collapse;">
            <thead>
              <tr>
                <th style="text-align:left;padding:6px 10px;font-size:0.8rem;color:#64748B;font-weight:600;">권한</th>
                ${roles.map(r => `<th style="padding:6px 14px;font-size:0.8rem;color:#64748B;font-weight:600;text-align:center;">${escapeHtml(PERM_ROLE_LABELS[r] || r)}</th>`).join("")}
              </tr>
            </thead>
            <tbody>
              ${perms.map(p => `
                <tr style="border-top:1px solid rgba(15,23,42,0.06);">
                  <td style="padding:7px 10px;font-size:0.82rem;">
                    <span style="color:#0F172A;font-weight:500;">${escapeHtml(PERM_KEY_LABELS[p.key] || p.key)}</span>
                    <span class="mini muted" style="display:block;font-size:0.7rem;color:#94A3B8;">${escapeHtml(p.key)}</span>
                  </td>
                  ${roles.map(r => {
                    const checked = (defaults[r] || []).includes(p.key);
                    return `<td style="text-align:center;padding:7px 14px;">
                      <input type="checkbox" data-perm-role="${escapeHtml(r)}" data-perm-key="${escapeHtml(p.key)}" ${checked ? "checked" : ""} style="width:16px;height:16px;cursor:pointer;" />
                    </td>`;
                  }).join("")}
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      `;
    }

    function populatePermAccountSelect() {
      const sel = $("permAccountSelect");
      if (!sel) return;
      const accounts = Array.isArray(opsAuthItems) ? opsAuthItems : [];
      const cur = sel.value;
      sel.innerHTML = `<option value="">-- 계정 선택 --</option>` +
        accounts
          .filter(a => ["OPERATOR", "CAFE_STAFF"].includes(String(a.role || "").toUpperCase()))
          .map(a => `<option value="${escapeHtml(a.username)}" ${a.username === cur ? "selected" : ""}>${escapeHtml(a.username)} (${escapeHtml(a.role)})</option>`)
          .join("");
    }

    function renderAccountMatrix() {
      const el = $("permAccountMatrix");
      if (!el || !_permAccountEffective || !_permData) return;
      const { username, effective, role, overrides } = _permAccountEffective;
      const ovrMap = {};
      for (const o of overrides) ovrMap[o.permission_key] = o.granted;
      const perms = _permData.permissions || [];
      const roleDefaults = (_permData.role_defaults || {})[role] || [];
      el.innerHTML = `
        <div class="mini muted u-mb-8">역할: <strong>${escapeHtml(PERM_ROLE_LABELS[role] || role)}</strong> — 체크 상태가 실질 권한입니다. 역할 기본값과 다른 항목은 오버라이드입니다.</div>
        <div style="overflow-x:auto;">
          <table style="min-width:480px;border-collapse:collapse;">
            <thead>
              <tr>
                <th style="text-align:left;padding:6px 10px;font-size:0.8rem;color:#64748B;font-weight:600;">권한</th>
                <th style="padding:6px 14px;font-size:0.8rem;color:#64748B;font-weight:600;text-align:center;">역할 기본</th>
                <th style="padding:6px 14px;font-size:0.8rem;color:#64748B;font-weight:600;text-align:center;">계정 오버라이드</th>
                <th style="padding:6px 14px;font-size:0.8rem;color:#64748B;font-weight:600;text-align:center;">실질 권한</th>
              </tr>
            </thead>
            <tbody>
              ${perms.map(p => {
                const roleDef = roleDefaults.includes(p.key);
                const hasOverride = p.key in ovrMap;
                const ovrGranted = ovrMap[p.key];
                const isGranted = effective[p.key] === true;
                const overrideLabel = !hasOverride ? "—" : (ovrGranted ? "추가 부여" : "차단");
                const overrideColor = !hasOverride ? "#94A3B8" : (ovrGranted ? "#059669" : "#DC2626");
                return `
                  <tr style="border-top:1px solid rgba(15,23,42,0.06);" data-perm-key="${escapeHtml(p.key)}">
                    <td style="padding:7px 10px;font-size:0.82rem;">
                      <span style="font-weight:500;">${escapeHtml(PERM_KEY_LABELS[p.key] || p.key)}</span>
                      <span style="display:block;font-size:0.7rem;color:#94A3B8;">${escapeHtml(p.key)}</span>
                    </td>
                    <td style="text-align:center;padding:7px 14px;font-size:0.82rem;color:${roleDef ? "#059669" : "#94A3B8"};">${roleDef ? "O" : "—"}</td>
                    <td style="text-align:center;padding:7px 14px;font-size:0.82rem;">
                      <span style="color:${overrideColor};">${overrideLabel}</span>
                      ${hasOverride ? `<button class="btn ghost tiny" data-perm-clear="${escapeHtml(p.key)}" style="margin-left:4px;padding:1px 6px;font-size:0.7rem;" title="오버라이드 제거">✕</button>` : ""}
                    </td>
                    <td style="text-align:center;padding:7px 14px;">
                      <span style="font-size:1rem;color:${isGranted ? "#059669" : "#DC2626"};">${isGranted ? "✓" : "✗"}</span>
                    </td>
                  </tr>
                `;
              }).join("")}
            </tbody>
          </table>
        </div>
        <div class="row u-mt-8" style="gap:8px;flex-wrap:wrap;">
          ${perms.map(p => `
            <button class="btn ghost tiny" data-perm-grant="${escapeHtml(p.key)}" style="font-size:0.75rem;">+${escapeHtml(PERM_KEY_LABELS[p.key] || p.key)}</button>
          `).join("")}
        </div>
        <div class="mini muted u-mt-6">+버튼으로 추가 부여, ✕로 오버라이드 제거</div>
      `;
      // 오버라이드 제거 버튼
      el.querySelectorAll("[data-perm-clear]").forEach(btn => {
        btn.addEventListener("click", async () => {
          const key = btn.dataset.permClear;
          await deletePermOverride(username, key);
        });
      });
      // 추가 부여 버튼
      el.querySelectorAll("[data-perm-grant]").forEach(btn => {
        btn.addEventListener("click", async () => {
          const key = btn.dataset.permGrant;
          await grantPermOverride(username, key);
        });
      });
    }

    function renderAdminManageSurface() {
      const manageSurface = $("adminManageSurface");
      const emptyState = $("adminManageEmptyState");
      const hasSelection = Number(homeSelectedItemId || homeSelectedMasterId || 0) > 0;
      if (manageSurface) manageSurface.classList.add("active");
      if (emptyState) emptyState.classList.toggle("active", !hasSelection);
      setDisplayIfPresent("homeEditorCard", hasSelection ? "block" : "none");
    }

    function autoBackupIntervalDaysFromMinutes(value) {
      const minutes = Math.max(0, Number(value || 0));
      if (!Number.isFinite(minutes) || minutes <= 0) return 0;
      return Math.max(1, Math.ceil(minutes / 1440));
    }

    function autoBackupIntervalMinutesFromDays(value) {
      const days = Math.max(0, Number(value || 0));
      if (!Number.isFinite(days) || days <= 0) return 0;
      return Math.round(days * 1440);
    }

    function renderOpsBackupScheduleDetails(data) {
      const dailySchedule = String(data?.daily_schedule || "").trim();
      const weeklySchedule = String(data?.weekly_schedule || "").trim();
      const dailyLabel = dailySchedule
        ? t("ops.restore.summary.daily_schedule", { value: dailySchedule })
        : `${t("ops.restore.summary.daily_schedule", { value: "-" })}`;
      const weeklyLabel = weeklySchedule
        ? t("ops.restore.summary.weekly_schedule", { value: weeklySchedule })
        : `${t("ops.restore.summary.weekly_schedule", { value: "-" })}`;
      setTextIfPresent("opsAutoBackupDailySchedule", dailyLabel);
      setTextIfPresent("opsAutoBackupWeeklySchedule", weeklyLabel);
    }
    let _actAuditOffset = 0, _actAuditLimit = 50;
    let _actLocOffset = 0, _actLocLimit = 50;

    function _renderGlobalAuditRow(r) {
      const ts = (r.created_at || "").slice(0, 16).replace("T", " ");
      const entityTypeLabel = { owned_item: "상품", album_master: "마스터", storage_slot: "슬롯", auth_account: "계정" }[r.entity_type] || r.entity_type || "";

      const snap = (() => { try { return JSON.parse(r.snapshot_json || "null"); } catch { return null; } })();
      const fields = (() => { try { return JSON.parse(r.changed_fields || "[]"); } catch { return []; } })();
      const isDiff = snap && typeof snap === "object" && !Array.isArray(snap) &&
        Object.values(snap).some(v => v && typeof v === "object" && ("b" in v || "a" in v));

      const SHOW_LIMIT = 3;
      let diffHtml = "";

      if (isDiff) {
        const entries = Object.entries(snap);
        const renderEntry = ([field, ba]) => {
          const bVal = escapeHtml(_auditValueLabel(field, ba?.b));
          const aVal = escapeHtml(_auditValueLabel(field, ba?.a));
          return `<div style="display:flex;gap:4px;align-items:baseline;flex-wrap:wrap;font-size:0.73rem;line-height:1.6">
            <span style="color:var(--text-sub);font-weight:600;flex-shrink:0">${escapeHtml(_auditFieldLabel(field))}</span>
            <span style="color:#dc2626;text-decoration:line-through;flex-shrink:0">${bVal}</span>
            <span style="color:var(--text-muted);flex-shrink:0">→</span>
            <span style="color:#059669;font-weight:600;flex-shrink:0">${aVal}</span>
          </div>`;
        };
        const shown = entries.slice(0, SHOW_LIMIT).map(renderEntry).join("");
        const rest = entries.slice(SHOW_LIMIT);
        diffHtml = shown + (rest.length
          ? `<details style="margin-top:1px"><summary style="font-size:0.72rem;cursor:pointer;color:var(--accent);user-select:none">+${rest.length}개 더 보기</summary>${rest.map(renderEntry).join("")}</details>`
          : "");
      } else if (snap && typeof snap === "object") {
        diffHtml = Object.entries(snap).slice(0, SHOW_LIMIT).map(([field, val]) =>
          `<div style="font-size:0.73rem;line-height:1.6">
            <span style="color:var(--text-sub);font-weight:600">${escapeHtml(_auditFieldLabel(field))}</span>
            <span style="color:var(--text-muted)">: </span>
            <span>${escapeHtml(_auditValueLabel(field, val))}</span>
          </div>`
        ).join("");
      } else if (fields.length) {
        diffHtml = `<span style="font-size:0.73rem;color:var(--text-muted)">${fields.map(f => escapeHtml(_auditFieldLabel(f))).join(" · ")}</span>`;
      }

      return `<tr>
        <td style="white-space:nowrap;font-size:0.75rem;vertical-align:top;padding-top:6px">${ts}</td>
        <td style="vertical-align:top;padding-top:6px"><span style="font-size:0.72rem;background:var(--bg-dim,#f5f5f5);padding:1px 5px;border-radius:3px">${entityTypeLabel}</span></td>
        <td style="vertical-align:top;font-size:0.75rem;padding-top:6px">${r.entity_id || ""}</td>
        <td style="vertical-align:top;padding-top:6px">${_auditActionBadge(r.action || "")}</td>
        <td style="vertical-align:top;font-size:0.75rem;padding-top:6px">${escapeHtml(r.changed_by || "—")}</td>
        <td style="vertical-align:top">${diffHtml}</td>
      </tr>`;
    }

    let _srvAutoRefreshTimer = null;

    function _auditFieldLabel(field) {
      return _AUDIT_FIELD_LABELS[field] || field;
    }

    function _auditValueLabel(field, val) {
      if (val === null || val === undefined || val === "") return "—";
      const map = _AUDIT_VALUE_LABELS[field];
      if (map) return map[String(val)] || String(val);
      if (typeof val === "boolean") return val ? "예" : "아니오";
      if (Array.isArray(val)) return val.join(", ") || "—";
      return String(val);
    }

    function _auditActionBadge(action) {
      const c = _AUDIT_ACTION_COLORS[action] || { bg: "#f3f4f6", color: "#374151" };
      const label = _AUDIT_ACTION_LABELS[action] || action;
      return `<span style="display:inline-block;padding:1px 7px;border-radius:4px;font-size:0.7rem;font-weight:700;background:${c.bg};color:${c.color}">${label}</span>`;
    }

    function _renderAuditDiffRows(record) {
      // snapshot_json can be: {field: {b: before, a: after}} (new diff format)
      // or {field: value} (legacy snapshot) or null
      const snap = (() => { try { return JSON.parse(record.snapshot_json || "null"); } catch { return null; } })();
      const fields = (() => { try { return JSON.parse(record.changed_fields || "[]"); } catch { return []; } })();

      if (!snap && !fields.length) return "";

      // Detect diff format: first value is an object with "b" or "a" key
      const isDiff = snap && typeof snap === "object" && !Array.isArray(snap) &&
        Object.values(snap).some(v => v && typeof v === "object" && ("b" in v || "a" in v));

      if (isDiff) {
        // Render before/after table
        return Object.entries(snap).map(([field, ba]) => {
          const bVal = _auditValueLabel(field, ba?.b);
          const aVal = _auditValueLabel(field, ba?.a);
          return `<tr>
            <td style="padding:3px 8px;font-size:0.76rem;color:var(--text-sub);white-space:nowrap">${_auditFieldLabel(field)}</td>
            <td style="padding:3px 8px;font-size:0.76rem;color:#dc2626;text-decoration:line-through">${escapeHtml(bVal)}</td>
            <td style="padding:3px 4px;font-size:0.72rem;color:var(--text-muted)">→</td>
            <td style="padding:3px 8px;font-size:0.76rem;color:#059669;font-weight:600">${escapeHtml(aVal)}</td>
          </tr>`;
        }).join("");
      } else if (snap && typeof snap === "object") {
        // Legacy: just show snapshot values
        return Object.entries(snap).map(([field, val]) =>
          `<tr>
            <td style="padding:3px 8px;font-size:0.76rem;color:var(--text-sub)">${_auditFieldLabel(field)}</td>
            <td colspan="3" style="padding:3px 8px;font-size:0.76rem">${escapeHtml(_auditValueLabel(field, val))}</td>
          </tr>`
        ).join("");
      } else if (fields.length) {
        return fields.map(f =>
          `<tr><td style="padding:3px 8px;font-size:0.76rem;color:var(--text-sub)">${_auditFieldLabel(f)}</td><td colspan="3" style="padding:3px 8px;font-size:0.76rem;color:var(--text-muted)">—</td></tr>`
        ).join("");
      }
      return "";
    }

    function _renderAuditItem(r) {
      const diffRows = _renderAuditDiffRows(r);
      const ts = (r.created_at || "").slice(0, 16).replace("T", " ");
      return `<div style="border:1px solid var(--border-light,#e5e7eb);border-radius:8px;margin-bottom:8px;overflow:hidden">
        <div style="display:flex;align-items:center;gap:8px;padding:6px 10px;background:var(--bg-dim,#f9fafb);border-bottom:1px solid var(--border-light,#e5e7eb)">
          ${_auditActionBadge(r.action || "")}
          <span style="font-size:0.75rem;color:var(--text-muted)">${ts}</span>
          <span style="font-size:0.75rem;color:var(--text-sub);margin-left:auto">${escapeHtml(r.changed_by || "—")}</span>
        </div>
        ${diffRows ? `<table style="width:100%;border-collapse:collapse"><tbody>${diffRows}</tbody></table>` : ""}
      </div>`;
    }

    function _renderLocationItem(r) {
      const ts = (r.created_at || "").slice(0, 16).replace("T", " ");
      const kindLabels = { INITIAL_ASSIGN: "최초 배치", ASSIGN: "배치", MOVE: "이동", UNASSIGN: "회수", CABINET_DELETE: "장식장 삭제" };
      const kind = kindLabels[r.movement_kind] || r.movement_kind || "";
      const from_ = r.from_slot_display_name || r.from_slot_code || "—";
      const to_ = r.to_slot_display_name || r.to_slot_code || "—";
      return `<div style="display:flex;align-items:center;gap:6px;padding:5px 10px;border-bottom:1px solid var(--border-light,#e5e7eb);font-size:0.76rem">
        <span style="color:var(--text-muted);white-space:nowrap;min-width:95px">${ts}</span>
        <span style="background:#e0e7ff;color:#3730a3;padding:1px 6px;border-radius:4px;font-size:0.7rem;font-weight:700">${kind}</span>
        <span style="color:#dc2626">${escapeHtml(from_)}</span>
        <span style="color:var(--text-muted)">→</span>
        <span style="color:#059669;font-weight:600">${escapeHtml(to_)}</span>
        ${r.note ? `<span style="color:var(--text-muted);margin-left:4px">${escapeHtml(r.note)}</span>` : ""}
      </div>`;
    }


    function currentOpsExceptionPresetPayload() {
      const opsExPkgChecked = [];
      $("opsExPackagingList")?.querySelectorAll("input:checked").forEach(cb => opsExPkgChecked.push(cb.value));
      const opsExContentsChecked = [];
      $("opsExPackageContentsList")?.querySelectorAll("input:checked").forEach(cb => opsExContentsChecked.push(cb.value));
      return {
        type: String($("opsExceptionType")?.value || "UNSLOTTED").trim().toUpperCase(),
        limit: Math.max(10, Math.min(200, Number($("opsExceptionLimit")?.value || 50))),
        domain:      String($("opsExceptionDomain")?.value || "").trim(),
        artist:      String($("opsExArtist")?.value      || "").trim(),
        title:       String($("opsExTitle")?.value        || "").trim(),
        barcode:     String($("opsExBarcode")?.value      || "").trim(),
        catalogNo:   String($("opsExCatalogNo")?.value    || "").trim(),
        releaseYear: String($("opsExReleaseYear")?.value  || "").trim(),
        packaging:       opsExPkgChecked,
        packageContents: opsExContentsChecked,
        sigDirect:   Boolean($("opsExSigDirect")?.checked),
        sigPurchase: Boolean($("opsExSigPurchase")?.checked),
        isNew:       Boolean($("opsExNewProduct")?.checked),
        isPromo:     Boolean($("opsExPromo")?.checked),
        isLimited:   Boolean($("opsExLimitEd")?.checked),
      };
    }

    function loadOpsExceptionPresets() {
      try {
        const raw = window.localStorage.getItem(OPS_EXCEPTION_PRESET_KEY);
        const parsed = JSON.parse(raw || "[]");
        return Array.isArray(parsed) ? parsed.filter((row) => row && typeof row === "object") : [];
      } catch (_err) {
        return [];
      }
    }

    function saveOpsExceptionPresets(list) {
      const rows = Array.isArray(list) ? list : [];
      window.localStorage.setItem(OPS_EXCEPTION_PRESET_KEY, JSON.stringify(rows));
    }

    function loadDefaultOpsExceptionPresetName() {
      const role = String(appAuthSession?.role || "ADMIN").trim().toUpperCase();
      const scopedKey = `${OPS_EXCEPTION_PRESET_DEFAULT_KEY}.${role}`;
      try {
        return String(window.localStorage.getItem(scopedKey) || "").trim();
      } catch (_err) {
        return "";
      }
    }

    function saveDefaultOpsExceptionPresetName(name) {
      const role = String(appAuthSession?.role || "ADMIN").trim().toUpperCase();
      const scopedKey = `${OPS_EXCEPTION_PRESET_DEFAULT_KEY}.${role}`;
      try {
        if (!name) window.localStorage.removeItem(scopedKey);
        else window.localStorage.setItem(scopedKey, String(name).trim());
      } catch (_err) {
        // ignore localStorage write errors
      }
    }

    function loadRoleScopedMap(storageKey) {
      try {
        const raw = window.localStorage.getItem(storageKey);
        const parsed = JSON.parse(raw || "{}");
        return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
      } catch (_err) {
        return {};
      }
    }

    function saveRoleScopedMap(storageKey, nextValue) {
      try {
        window.localStorage.setItem(storageKey, JSON.stringify(nextValue || {}));
      } catch (_err) {
        // ignore localStorage write errors
      }
    }

    function currentSessionRoleCode() {
      return String(appAuthSession?.role || "ADMIN").trim().toUpperCase();
    }

    function loadRoleScopedValue(storageKey) {
      const role = currentSessionRoleCode();
      const map = loadRoleScopedMap(storageKey);
      return String(map?.[role] || "").trim();
    }

    function saveRoleScopedValue(storageKey, value) {
      const role = currentSessionRoleCode();
      const map = loadRoleScopedMap(storageKey);
      if (!value) delete map[role];
      else map[role] = String(value).trim();
      saveRoleScopedMap(storageKey, map);
    }

    function clearCurrentRoleDefaultPreferences() {
      saveRoleScopedValue(APP_MAIN_TAB_MEMORY_KEY, "");
      saveRoleScopedValue(APP_SUBTAB_MEMORY_KEY, "");
      saveDefaultOpsExceptionPresetName("");
    }

    function renderOpsExceptionPresetOptions() {
      const select = $("opsExceptionPresetSelect");
      const chips = $("opsExceptionPresetChips");
      if (!select) return;
      const rows = loadOpsExceptionPresets();
      const currentValue = String(select.value || "");
      const defaultName = loadDefaultOpsExceptionPresetName().toLowerCase();
      select.innerHTML = [
        `<option value="">${escapeHtml(t("common.none"))}</option>`,
        ...rows.map((row, idx) => {
          const name = String(row.name || t("ops.exception.field.preset.fallback_name", { index: idx + 1 }));
          const type = opsExceptionTypeLabel(row.type || "UNSLOTTED");
          const limit = Math.max(10, Math.min(200, Number(row.limit || 50)));
          const isDefault = name.trim().toLowerCase() === defaultName;
          return `<option value="${idx}">${escapeHtml(isDefault
            ? t("ops.exception.field.preset.option.default", { name, type, limit: countWithUnit(limit) })
            : t("ops.exception.field.preset.option.normal", { name, type, limit: countWithUnit(limit) }))}</option>`;
        })
      ].join("");
      if (currentValue && rows[Number(currentValue)]) {
        select.value = currentValue;
      }
      if (chips) {
        chips.innerHTML = rows.length
          ? rows.slice(0, 8).map((row, idx) => {
              const name = String(row.name || t("ops.exception.field.preset.fallback_name", { index: idx + 1 }));
              const type = opsExceptionTypeLabel(row.type || "UNSLOTTED");
              const limit = Math.max(10, Math.min(200, Number(row.limit || 50)));
              const isDefault = name.trim().toLowerCase() === defaultName;
              return `<button class="dashboard-workbench-source ${isDefault ? "active" : ""}" type="button" data-ops-exception-preset-chip="${idx}" title="${escapeHtml(`${name} / ${type} / ${countWithUnit(limit)}`)}">${escapeHtml(isDefault ? t("ops.exception.field.preset.chip.default", { name, limit }) : t("ops.exception.field.preset.chip.normal", { name, limit }))}</button>`;
            }).join("")
          : `<div class="mini muted">${escapeHtml(t("ops.exception.state.empty_presets"))}</div>`;
      }
    }

    function applyDefaultOpsExceptionPreset() {
      const defaultName = loadDefaultOpsExceptionPresetName().toLowerCase();
      if (!defaultName) return false;
      const rows = loadOpsExceptionPresets();
      const idx = rows.findIndex((row) => String(row?.name || "").trim().toLowerCase() === defaultName);
      if (idx < 0) return false;
      $("opsExceptionPresetSelect").value = String(idx);
      return applyOpsExceptionPresetByIndex(String(idx));
    }

    function applyOpsExceptionPresetByIndex(indexValue) {
      const idx = Number(indexValue);
      if (!Number.isInteger(idx) || idx < 0) return false;
      const rows = loadOpsExceptionPresets();
      const preset = rows[idx];
      if (!preset) return false;
      $("opsExceptionType").value = String(preset.type || "UNSLOTTED").trim().toUpperCase();
      $("opsExceptionLimit").value = String(Math.max(10, Math.min(200, Number(preset.limit || 50))));
      if ($("opsExceptionPresetName")) {
        $("opsExceptionPresetName").value = String(preset.name || "").trim();
      }
      if ($("opsExceptionDomain"))    $("opsExceptionDomain").value    = String(preset.domain    || "").trim();
      if ($("opsExArtist"))      $("opsExArtist").value      = String(preset.artist      || "").trim();
      if ($("opsExTitle"))       $("opsExTitle").value        = String(preset.title       || "").trim();
      if ($("opsExBarcode"))     $("opsExBarcode").value      = String(preset.barcode     || "").trim();
      if ($("opsExCatalogNo"))   $("opsExCatalogNo").value    = String(preset.catalogNo   || "").trim();
      if ($("opsExReleaseYear")) $("opsExReleaseYear").value  = String(preset.releaseYear || "").trim();
      // 상세 검색 조건 복원
      const pkgValues = new Set(Array.isArray(preset.packaging) ? preset.packaging : []);
      $("opsExPackagingList")?.querySelectorAll("input").forEach(cb => { cb.checked = pkgValues.has(cb.value); });
      const contentsValues = new Set(Array.isArray(preset.packageContents) ? preset.packageContents : []);
      $("opsExPackageContentsList")?.querySelectorAll("input").forEach(cb => { cb.checked = contentsValues.has(cb.value); });
      if ($("opsExSigDirect"))  $("opsExSigDirect").checked  = Boolean(preset.sigDirect);
      if ($("opsExSigPurchase")) $("opsExSigPurchase").checked = Boolean(preset.sigPurchase);
      if ($("opsExNewProduct")) $("opsExNewProduct").checked = Boolean(preset.isNew);
      if ($("opsExPromo"))      $("opsExPromo").checked      = Boolean(preset.isPromo);
      if ($("opsExLimitEd"))    $("opsExLimitEd").checked    = Boolean(preset.isLimited);
      syncOpsExceptionSelectionControls();
      return true;
    }

    function syncMasterExceptionBanner() {
      const el = $("masterExceptionBanner");
      const legacyCard = $("registerMasterLegacyCard");
      const count = masterOwnedPrefilledIds.size;
      const showLegacyCard = count > 0 || (Array.isArray(masterOwnedItems) && masterOwnedItems.length > 0);
      if (legacyCard) {
        legacyCard.hidden = !showLegacyCard;
        setDisplayMode(legacyCard, showLegacyCard ? "block" : "none");
      }
      if (!el) return;
      if (!count) {
        setDisplayMode(el, "none");
        el.textContent = "";
        return;
      }
      setDisplayMode(el, "block");
      el.textContent = t("ops.exception.banner.prefilled", { count: countWithUnit(count) });
    }

    function opsExceptionTypeLabel(value) {
      const code = String(value || "").trim().toUpperCase();
      if (code === "UNSLOTTED") return t("common.exception.unslotted");
      if (code === "SOURCE_MISSING") return t("common.exception.source_missing");
      if (code === "MASTER_MISSING") return t("common.exception.master_missing");
      if (code === "COVER_MISSING") return t("common.exception.cover_missing");
      if (code === "PREFERRED_SIZE_MISMATCH") return t("common.exception.preferred_size_mismatch");
      if (code === "TRACK_MISSING") return t("common.exception.track_missing");
      if (code === "SPOTIFY_UNMATCHED") return t("common.exception.spotify_unmatched");
      if (code === "REVIEW_MISSING") return t("common.exception.review_missing");
      if (code === "MEDIA_MISSING") return t("common.exception.media_missing");
      if (code === "SIZE_MISMATCH") return t("common.exception.size_mismatch");
      if (code === "GENRE_MISSING") return t("common.exception.genre_missing");
      if (code === "CATALOG_MISSING") return t("common.exception.catalog_missing");
      if (code === "RELEASE_TYPE_MISSING") return "앨범 타입 없음";
      return code || "-";
    }

    function opsExceptionTypeHint(value) {
      const code = String(value || "").trim().toUpperCase();
      if (code === "UNSLOTTED") return t("common.exception_hint.unslotted");
      if (code === "SOURCE_MISSING") return t("common.exception_hint.source_missing");
      if (code === "MASTER_MISSING") return t("common.exception_hint.master_missing");
      if (code === "COVER_MISSING") return t("common.exception_hint.cover_missing");
      if (code === "PREFERRED_SIZE_MISMATCH") return t("common.exception_hint.preferred_size_mismatch");
      if (code === "TRACK_MISSING") return t("common.exception_hint.track_missing");
      if (code === "SPOTIFY_UNMATCHED") return t("common.exception_hint.spotify_unmatched");
      if (code === "REVIEW_MISSING") return t("common.exception_hint.review_missing");
      if (code === "MEDIA_MISSING") return t("common.exception_hint.media_missing");
      if (code === "SIZE_MISMATCH") return t("common.exception_hint.size_mismatch");
      if (code === "GENRE_MISSING") return t("common.exception_hint.genre_missing");
      if (code === "CATALOG_MISSING") return t("common.exception_hint.catalog_missing");
      if (code === "LOCAL_MISSING") return "로컬 음원 미연결";
      if (code === "RELEASE_TYPE_MISSING") return "앨범 마스터 타입 미등록";
      return "";
    }

    function buildMasterExceptionUrl(type, limit, offset = 0) {
      let url;
      const artist = String($("opsExArtist")?.value || "").trim();
      const title  = String($("opsExTitle")?.value  || "").trim();
      const domain = String($("opsExceptionDomain")?.value || "").trim();
      const releaseYear = String($("opsExReleaseYear")?.value || "").trim();
      if (type === "CATALOG_MISSING") {
        url = `/owned-items?music_only=true&status=IN_COLLECTION&include_total=true&limit=${limit}&offset=${offset}&catalog_missing=true`;
        if (artist)      url += `&artist_or_brand=${encodeURIComponent(artist)}`;
        if (title)       url += `&q=${encodeURIComponent(title)}`;
        if (domain)      url += `&domain_code=${encodeURIComponent(domain)}`;
        if (releaseYear) url += `&release_year=${encodeURIComponent(releaseYear)}`;
      } else {
        url = `/album-masters?include_total=true&limit=${limit}&offset=${offset}`;
        if (type === "GENRE_MISSING")           url += "&genre_missing=true&media_only=true";
        else if (type === "SPOTIFY_UNMATCHED")  url += "&spotify_state=MISSING";
        else if (type === "REVIEW_MISSING")     url += "&review_missing=true&media_only=true";
        else if (type === "LOCAL_MISSING")      url += "&local_missing=true&media_only=true";
        else if (type === "RELEASE_TYPE_MISSING") url += "&release_type_missing=true&media_only=true";
        if (artist)      url += `&artist_or_brand=${encodeURIComponent(artist)}`;
        if (title)       url += `&q=${encodeURIComponent(title)}`;
        if (domain)      url += `&domain_code=${encodeURIComponent(domain)}`;
        if (releaseYear) url += `&release_year=${encodeURIComponent(releaseYear)}`;
      }
      return url;
    }

    function buildMasterExceptionCountUrl(type) {
      let url;
      const domain = String($("opsExceptionDomain")?.value || "").trim();
      if (type === "CATALOG_MISSING") {
        url = `/owned-items?music_only=true&status=IN_COLLECTION&include_total=true&limit=1&catalog_missing=true`;
        if (domain) url += `&domain_code=${encodeURIComponent(domain)}`;
      } else {
        url = `/album-masters?include_total=true&limit=1`;
        if (type === "GENRE_MISSING")           url += "&genre_missing=true&media_only=true";
        else if (type === "SPOTIFY_UNMATCHED")  url += "&spotify_state=MISSING";
        else if (type === "REVIEW_MISSING")     url += "&review_missing=true&media_only=true";
        else if (type === "LOCAL_MISSING")      url += "&local_missing=true&media_only=true";
        else if (type === "RELEASE_TYPE_MISSING") url += "&release_type_missing=true&media_only=true";
        if (domain) url += `&domain_code=${encodeURIComponent(domain)}`;
      }
      return url;
    }

    function buildOpsExceptionParams(type, opts = {}) {
      const params = new URLSearchParams({
        music_only: "true",
        status: "IN_COLLECTION",
        sort: "RECENT",
        limit: String(Math.max(1, Math.min(200, Number(opts.limit || 50)))),
        offset: String(Math.max(0, Number(opts.offset || 0))),
      });
      if (opts.includeTotal) params.set("include_total", "true");
      const code = String(type || "UNSLOTTED").trim().toUpperCase();
      if (code === "UNSLOTTED") params.set("slot_state", "UNSLOTTED");
      if (code === "SOURCE_MISSING") params.set("source_state", "MISSING");
      if (code === "MASTER_MISSING") params.set("master_state", "MISSING");
      if (code === "COVER_MISSING") params.set("cover_state", "MISSING");
      if (code === "PREFERRED_SIZE_MISMATCH") params.set("preferred_storage_state", "MISMATCH");
      if (code === "TRACK_MISSING") params.set("track_state", "MISSING");
      if (code === "MEDIA_MISSING") params.set("media_format_state", "MISSING");
      if (code === "SIZE_MISMATCH") params.set("size_group_state", "MISMATCH");

      // 검색 필터
      const artist = String($("opsExArtist")?.value || "").trim();
      const title  = String($("opsExTitle")?.value  || "").trim();
      const barcode = String($("opsExBarcode")?.value || "").trim();
      const catalogNo = String($("opsExCatalogNo")?.value || "").trim();
      const releaseYear = String($("opsExReleaseYear")?.value || "").trim();
      const domain = String($("opsExceptionDomain")?.value || "").trim();
      if (artist)      params.set("artist_or_brand", artist);
      if (title)       params.set("item_name", title);
      if (barcode)     params.set("barcode", barcode);
      if (catalogNo)   params.set("catalog_no", catalogNo);
      if (releaseYear) params.set("release_year", releaseYear);
      if (domain)      params.set("domain_code", domain);

      // 상세 검색 조건 (OwnedItem 예외 타입에만 적용)
      const opsExPkgVals = [];
      $("opsExPackagingList")?.querySelectorAll("input:checked").forEach(cb => opsExPkgVals.push(cb.value));
      const opsExContentsVals = [];
      $("opsExPackageContentsList")?.querySelectorAll("input:checked").forEach(cb => opsExContentsVals.push(cb.value));
      opsExPkgVals.forEach(v => params.append("packaging", v));
      opsExContentsVals.forEach(v => params.append("package_contents", v));
      if ($("opsExSigDirect")?.checked) params.append("signature_types", "IN_PERSON");
      if ($("opsExSigPurchase")?.checked) params.append("signature_types", "PURCHASE_INCLUDED");
      if ($("opsExNewProduct")?.checked) params.set("is_new", "true");
      if ($("opsExPromo")?.checked) params.set("is_promo", "true");
      if ($("opsExLimitEd")?.checked) params.set("is_limited", "true");
      return params;
    }

    function renderMetadataSyncSummary(data) {
      if (!data) {
        $("metaSyncSummary").textContent = "-";
        return;
      }
      const autoText = data.auto_enabled
        ? t("ops.meta_sync.summary.auto_on", { minutes: Number(data.interval_minutes || 0) })
        : t("ops.meta_sync.summary.auto_off");
      const runningText = data.running ? t("ops.meta_sync.summary.state.running") : t("ops.meta_sync.summary.state.idle");
      const last = data.last_result || null;
      const lastText = last
        ? t("ops.meta_sync.summary.last_result", {
            processed: last.processed_count,
            updated: last.updated_count,
            skipped: last.skipped_count,
            failed: last.failed_count,
            completed: last.completed_at,
          })
        : t("ops.meta_sync.summary.last_result_none");
      const lastError = String(data.last_error || "").trim();
      const errorText = lastError ? ` | ${t("ops.meta_sync.summary.last_error", { error: lastError })}` : "";
      $("metaSyncSummary").textContent =
        t("ops.meta_sync.summary.full", {
          auto: autoText,
          limit: Number(data.batch_limit || 0),
          state: runningText,
          last: lastText,
          error: errorText,
        });
    }

    async function loadMetadataSyncStatus() {
      try {
        setStatus("metaSyncStatusBox", "ok", t("ops.meta_sync.status.load_loading"));
        const res = await fetch("/metadata-sync/status");
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("ops.meta_sync.status.load_failed"));
        renderMetadataSyncSummary(data);
        if (!$("metaSyncLimit").value.trim()) {
          $("metaSyncLimit").value = String(Number(data.batch_limit || 300));
        }
        setStatus(
          "metaSyncStatusBox",
          "ok",
          t("ops.meta_sync.status.load_complete", {
            state: data.running ? t("ops.meta_sync.state.running") : t("ops.meta_sync.state.idle"),
          })
        );
      } catch (err) {
        setStatus("metaSyncStatusBox", "err", errorMessageText(err, t("ops.meta_sync.status.load_failed")));
      }
    }

    async function loadOpsSystemStatus() {
      const summaryEl = $("opsSystemStatusSummary");
      const lineEl = $("opsSystemStatusLine");
      const linksEl = $("opsSystemStatusLinks");
      const pathsEl = $("opsSystemStatusPaths");
      const recentLogEl = $("opsSystemStatusRecentLog");
      const qaLineEl = $("opsQaStatusLine");
      const qaPathsEl = $("opsQaStatusPaths");
      const qaRemainingEl = $("opsQaRemainingList");
      if (!summaryEl || !lineEl || !linksEl || !pathsEl || !recentLogEl || !qaLineEl || !qaPathsEl || !qaRemainingEl) return;
      summaryEl.textContent = t("ops.system.summary.loading");
      lineEl.textContent = t("ops.system.line.load");
      linksEl.innerHTML = "";
      pathsEl.textContent = "";
      recentLogEl.textContent = "";
      qaLineEl.textContent = t("ops.system.line.qa");
      qaPathsEl.textContent = "";
      qaRemainingEl.textContent = "";
      try {
        const res = await fetch("/system/status");
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("ops.status.load_failed")));
        const syncRunning = Boolean(data?.metadata_sync_running);
        const syncLastError = String(data?.metadata_sync_last_error || "").trim();
        const recentLaunchdLines = Array.isArray(data?.recent_launchd_lines)
          ? data.recent_launchd_lines.map((line) => String(line || "").trim()).filter(Boolean)
          : [];
        const qaSummary = data?.qa_summary || {};
        const qaRemaining = Array.isArray(qaSummary?.remaining_items) ? qaSummary.remaining_items : [];
        const summaryText = syncLastError
          ? t("ops.system.summary.warning_sync_error")
          : (syncRunning ? t("ops.system.summary.healthy_running") : t("ops.system.summary.healthy_idle"));
        summaryEl.textContent = summaryText;
        lineEl.textContent = t("ops.system.status_line", {
          health: String(data?.health || "-"),
          state: syncRunning ? t("ops.meta_sync.state.running") : t("ops.meta_sync.state.idle"),
          error: syncLastError ? t("ops.system.status_line_error_suffix", { error: syncLastError }) : "",
        });
        linksEl.innerHTML = t("ops.system.links", {
          login_link: `<a href="${escapeHtml(String(data?.external_login_url || "https://__PROD_DOMAIN__/login"))}" target="_blank" rel="noreferrer">__PROD_DOMAIN__/login</a>`,
          health_link: `<a href="${escapeHtml(String(data?.external_health_url || "https://__PROD_DOMAIN__/health"))}" target="_blank" rel="noreferrer">__PROD_DOMAIN__/health</a>`,
        });
        pathsEl.textContent = t("ops.system.paths", {
          path: String(data?.launchd_err_log || "/Volumes/Data/Works/07.__PROJECT_SLUG__/logs/launchd/library.err.log"),
        });
        recentLogEl.textContent = recentLaunchdLines.length
          ? t("ops.system.logs.recent", { lines: recentLaunchdLines.join(" | ") })
          : t("ops.system.logs.recent_none");
        qaLineEl.textContent = t("ops.system.qa.summary", {
          pass_count: formatCount(Number(qaSummary?.pass_count || 0)),
          total_count: formatCount(Number(qaSummary?.total_count || 0)),
          fail_count: formatCount(Number(qaSummary?.fail_count || 0)),
          blocked_count: formatCount(Number(qaSummary?.blocked_count || 0)),
          not_started_count: formatCount(Number(qaSummary?.not_started_count || 0)),
        });
        qaPathsEl.innerHTML = t("ops.system.qa.paths", {
          master_link: `<a href="${escapeHtml(String(qaSummary?.qa_master_sheet || "/Volumes/Data/Works/07.__PROJECT_SLUG__/docs/qa/qa_master_sheet.csv"))}" target="_blank" rel="noreferrer">qa_master_sheet.csv</a>`,
          manual_link: `<a href="${escapeHtml(String(qaSummary?.qa_manual_sheet || "/Volumes/Data/Works/07.__PROJECT_SLUG__/docs/qa/qa_manual_remaining.csv"))}" target="_blank" rel="noreferrer">qa_manual_remaining.csv</a>`,
          updated: qaSummary?.updated_at
            ? t("ops.system.qa.updated_suffix", { updated_at: escapeHtml(String(qaSummary.updated_at)) })
            : "",
        });
        qaRemainingEl.textContent = qaRemaining.length
          ? t("ops.system.qa.remaining_examples", {
              items: qaRemaining.map((row) => `[${String(row.priority || "-")}] ${String(row.suite_id || "-")} ${String(row.title || "-")}`).join(" | "),
            })
          : t("ops.system.qa.remaining_none");
      } catch (err) {
        summaryEl.textContent = t("ops.system.summary.failure");
        lineEl.textContent = errorMessageText(err, t("ops.status.load_failed"));
        linksEl.innerHTML = t("ops.system.links", {
          login_link: `<a href="https://__PROD_DOMAIN__/login" target="_blank" rel="noreferrer">__PROD_DOMAIN__/login</a>`,
          health_link: `<a href="https://__PROD_DOMAIN__/health" target="_blank" rel="noreferrer">__PROD_DOMAIN__/health</a>`,
        });
        pathsEl.textContent = t("ops.system.paths", {
          path: "/Volumes/Data/Works/07.__PROJECT_SLUG__/logs/launchd/library.err.log | /Volumes/Data/Works/07.__PROJECT_SLUG__/logs/launchd/library.out.log",
        });
        recentLogEl.textContent = t("ops.system.logs.recent_load_failed");
        qaLineEl.textContent = t("ops.system.qa.load_failed");
        qaPathsEl.textContent = t("ops.system.qa.paths", {
          master_link: "/Volumes/Data/Works/07.__PROJECT_SLUG__/docs/qa/qa_master_sheet.csv",
          manual_link: "/Volumes/Data/Works/07.__PROJECT_SLUG__/docs/qa/qa_manual_remaining.csv",
          updated: "",
        });
        qaRemainingEl.textContent = t("ops.system.qa.load_failed");
      }
    }

    function downloadFilenameFromResponse(res, fallback = "download.bin") {
      const disposition = String(res?.headers?.get("content-disposition") || "").trim();
      if (!disposition) return fallback;
      const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
      if (utf8Match && utf8Match[1]) {
        try {
          return decodeURIComponent(utf8Match[1]);
        } catch (_) {
          return utf8Match[1];
        }
      }
      const plainMatch = disposition.match(/filename=\"?([^\";]+)\"?/i);
      if (plainMatch && plainMatch[1]) return plainMatch[1];
      return fallback;
    }

    async function triggerBrowserDownload(url, fallbackFilename = "download.bin") {
      const res = await fetch(url, {
        method: "GET",
        credentials: "same-origin",
      });
      if (!res.ok) {
        const data = await safeJson(res);
        throw new Error(data.detail || t("common.download_failed_status", { status: res.status }));
      }
      const blob = await res.blob();
      const filename = downloadFilenameFromResponse(res, fallbackFilename);
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = filename;
      a.rel = "noreferrer";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
      return filename;
    }

    async function runMetadataSyncNow() {
      const limit = Math.max(1, Math.min(5000, Number($("metaSyncLimit").value || 300)));
      const inter_item_delay_sec = Math.max(0, Math.min(60, Number($("metaSyncDelay").value ?? 1.5)));
      const payload = {
        source: $("metaSyncSource").value,
        only_missing: $("metaSyncOnlyMissing").checked,
        supplement_discogs: $("metaSyncSupplementDiscogs").checked,
        limit,
        inter_item_delay_sec,
        include_item_results: true,
      };

      try {
        setStatus("metaSyncStatusBox", "ok", t("ops.meta_sync.status.run_loading"));
        const logEl = $("metaSyncItemLog");
        if (logEl) { logEl.hidden = true; logEl.innerHTML = ""; }

        // POST to start — server returns 202 immediately (avoids Cloudflare 524 timeout)
        const res = await fetch("/metadata-sync/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("ops.meta_sync.status.run_failed"));

        // Poll /metadata-sync/status until running=false; render items incrementally
        let renderedCount = 0;
        let dot = 0;
        while (true) {
          await new Promise(r => setTimeout(r, 2000));
          try {
            const sRes = await fetch("/metadata-sync/status");
            const sData = await safeJson(sRes);
            if (!sRes.ok) break;
            if (sData.running) {
              dot = (dot + 1) % 4;
              const liveItems = sData.in_progress_items || [];
              const total = liveItems.length;
              setStatus("metaSyncStatusBox", "ok",
                t("ops.meta_sync.status.run_loading") + " " + ".".repeat(dot + 1) +
                (total > 0 ? `  (${total})` : "")
              );
              // Append only newly processed items
              if (liveItems.length > renderedCount) {
                appendMetaSyncItemLogRows(liveItems.slice(renderedCount));
                renderedCount = liveItems.length;
              }
              continue;
            }
            // Completed — render any remaining items from final result
            const result = sData.last_result || {};
            const finalItems = result.item_results || [];
            if (finalItems.length > renderedCount) {
              appendMetaSyncItemLogRows(finalItems.slice(renderedCount));
            }
            setStatus(
              "metaSyncStatusBox",
              "ok",
              t("ops.meta_sync.status.run_complete", {
                processed: result.processed_count ?? 0,
                updated: result.updated_count ?? 0,
                skipped: result.skipped_count ?? 0,
                failed: result.failed_count ?? 0,
              })
            );
            updateMetaSyncItemLogFooter(finalItems);
            await loadMetadataSyncStatus();
            break;
          } catch (_) {
            break;
          }
        }
      } catch (err) {
        setStatus("metaSyncStatusBox", "err", errorMessageText(err, t("ops.meta_sync.status.run_failed")));
      }
    }

    function _buildSyncLogRow(item) {
      const STATUS_CLASS = { UPDATED: "updated", SKIPPED: "skipped", FAILED: "failed" };
      const row = document.createElement("div");
      row.className = "sync-log-row";
      const status = String(item.status || "").toUpperCase();
      const cls = STATUS_CLASS[status] || "skipped";

      let productHtml = "";
      const name = String(item.display_name || "").trim();
      const artist = String(item.artist_or_brand || "").trim();
      const catalog = String(item.catalog_no || "").trim();
      if (name) {
        productHtml = `<span class="sync-log-product-name">${name}</span>`;
        if (artist && artist !== name) productHtml += `<br><span style="color:var(--muted);font-size:0.65rem">${artist}</span>`;
        if (catalog) productHtml += `<span style="color:var(--muted);font-size:0.65rem"> · ${catalog}</span>`;
      } else if (artist || catalog) {
        productHtml = `<span class="sync-log-product-name">${artist || "-"}</span>`;
        if (catalog) productHtml += `<br><span style="color:var(--muted);font-size:0.65rem">${catalog}</span>`;
      } else {
        productHtml = `<span style="color:var(--muted)">-</span>`;
      }

      let detailHtml = "";
      if (status === "UPDATED" && Array.isArray(item.updated_fields) && item.updated_fields.length > 0) {
        const tags = item.updated_fields.map(f => `<span class="field-tag">${f}</span>`).join("");
        detailHtml = `<div class="fields">${tags}</div>`;
      } else if (item.reason) {
        detailHtml = `<span style="color:var(--muted)">${item.reason}</span>`;
      } else {
        detailHtml = `<span style="color:var(--muted)">${item.source_external_id || "-"}</span>`;
      }

      row.innerHTML = `
        <span><span class="sync-log-badge ${cls}">${status}</span></span>
        <span class="sync-log-id">#${item.owned_item_id}</span>
        <span class="sync-log-source">${item.source_code}</span>
        <span class="sync-log-detail">${productHtml}</span>
        <span class="sync-log-detail">${detailHtml}</span>
      `;
      return row;
    }

    function _getOrCreateSyncLogBody() {
      const el = $("metaSyncItemLog");
      if (!el) return null;
      el.hidden = false;
      if (!el.querySelector(".sync-item-log-header")) {
        const header = document.createElement("div");
        header.className = "sync-item-log-header";
        header.innerHTML = `<span>상태</span><span>ID</span><span>소스</span><span>상품</span><span>내용</span>`;
        el.appendChild(header);
        const body = document.createElement("div");
        body.className = "sync-item-log-body";
        el.appendChild(body);
        const foot = document.createElement("div");
        foot.className = "sync-log-count";
        el.appendChild(foot);
      }
      return el.querySelector(".sync-item-log-body");
    }

    function appendMetaSyncItemLogRows(newItems) {
      if (!newItems || newItems.length === 0) return;
      const body = _getOrCreateSyncLogBody();
      if (!body) return;
      newItems.forEach(item => body.appendChild(_buildSyncLogRow(item)));
      // Scroll to bottom to show newest items
      const el = $("metaSyncItemLog");
      if (el) el.scrollTop = el.scrollHeight;
    }

    function updateMetaSyncItemLogFooter(allItems) {
      const el = $("metaSyncItemLog");
      if (!el) return;
      const foot = el.querySelector(".sync-log-count");
      if (!foot) return;
      const updated = (allItems || []).filter(i => i.status === "UPDATED").length;
      const skipped = (allItems || []).filter(i => i.status === "SKIPPED").length;
      const failed  = (allItems || []).filter(i => i.status === "FAILED").length;
      foot.textContent = `총 ${(allItems || []).length}건 — 반영 ${updated} / 스킵 ${skipped} / 실패 ${failed}`;
    }

    function renderMetaSyncItemLog(items) {
      const el = $("metaSyncItemLog");
      if (!el) return;
      el.innerHTML = "";
      if (!items || items.length === 0) { el.hidden = true; return; }
      appendMetaSyncItemLogRows(items);
      updateMetaSyncItemLogFooter(items);
    }

    function renderAladinDiscogsBackfillStatus(data) {
      const summaryEl = $("aladinDiscogsBackfillSummary");
      const listEl = $("aladinDiscogsBackfillMatchedList");
      if (!summaryEl) return;

      const running = Boolean(data?.running);
      const lastErr = String(data?.last_error || "").trim();
      const r = data?.last_result;

      if (!r && !lastErr) {
        summaryEl.textContent = running ? "⏳ 실행 중..." : "실행 이력 없음";
        if (listEl) listEl.style.display = "none";
        return;
      }

      if (lastErr && !r) {
        summaryEl.textContent = `오류: ${lastErr}`;
        if (listEl) listEl.style.display = "none";
        return;
      }

      const dryTag = r.dry_run ? " [DRY-RUN]" : "";
      const finishedAt = r.finished_at ? ` | 완료: ${r.finished_at}` : (running ? " | 실행 중..." : "");
      summaryEl.textContent =
        `${dryTag} 스캔 ${r.scanned}건 | 매칭 신규 ${r.master_created}건 | 이미연결 ${r.already_discogs}건 | detail업데이트 ${r.detail_updated}건 | crossref없음 ${r.no_crossref}건 | 오류 ${r.error}건${finishedAt}`;

      const matched = Array.isArray(r.matched_items) ? r.matched_items : [];
      if (!listEl) return;
      if (matched.length === 0) {
        listEl.style.display = "none";
        return;
      }
      listEl.style.display = "";
      listEl.innerHTML = `<div class="result-head u-mt-8"><strong>매칭된 항목 (${matched.length}건)</strong></div>` +
        `<table style="width:100%;font-size:0.82em;border-collapse:collapse;margin-top:6px">` +
        `<thead><tr style="border-bottom:1px solid var(--border)">` +
        `<th style="text-align:left;padding:3px 6px">ID</th>` +
        `<th style="text-align:left;padding:3px 6px">아티스트 / 타이틀</th>` +
        `<th style="text-align:left;padding:3px 6px">포맷</th>` +
        `<th style="text-align:left;padding:3px 6px">바코드</th>` +
        `<th style="text-align:left;padding:3px 6px">레이블</th>` +
        `<th style="text-align:left;padding:3px 6px">액션</th>` +
        `</tr></thead><tbody>` +
        matched.map(m => {
          const discogsUrl = m.discogs_release_id
            ? `<a href="https://www.discogs.com/release/${escapeHtml(String(m.discogs_release_id))}" target="_blank" rel="noreferrer">${escapeHtml(String(m.discogs_release_id))}</a>`
            : "-";
          const actionLabel = m.action === "created" ? "마스터 생성" : m.action === "dry_run" ? "DRY-RUN" : "detail만 업데이트";
          return `<tr style="border-bottom:1px solid var(--border-light)">` +
            `<td style="padding:3px 6px">${m.owned_item_id} / ${discogsUrl}</td>` +
            `<td style="padding:3px 6px">${escapeHtml(String(m.artist || ""))} — ${escapeHtml(String(m.title || ""))}</td>` +
            `<td style="padding:3px 6px">${escapeHtml(String(m.format || "-"))}</td>` +
            `<td style="padding:3px 6px">${escapeHtml(String(m.barcode || "-"))}</td>` +
            `<td style="padding:3px 6px">${escapeHtml(String(m.label || "-"))}</td>` +
            `<td style="padding:3px 6px">${actionLabel}</td>` +
            `</tr>`;
        }).join("") +
        `</tbody></table>`;
    }

    async function loadAladinDiscogsBackfillStatus() {
      try {
        setStatus("aladinDiscogsBackfillStatusBox", "ok", "상태 확인 중...");
        const res = await fetch("/aladin-discogs-backfill/status");
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || "상태 조회 실패");
        renderAladinDiscogsBackfillStatus(data);

        if (data.running) {
          setStatus("aladinDiscogsBackfillStatusBox", "ok", "⏳ 실행 중... (자동 폴링 중)");
          _startAladinDiscogsBackfillPoller();
        } else {
          setStatus("aladinDiscogsBackfillStatusBox", data.last_error ? "err" : "ok",
            data.last_error ? `오류: ${data.last_error}` : "상태 확인 완료");
          _stopAladinDiscogsBackfillPoller();
        }
      } catch (err) {
        setStatus("aladinDiscogsBackfillStatusBox", "err", errorMessageText(err, "상태 조회 실패"));
      }
    }

    function _startAladinDiscogsBackfillPoller() {
      if (_aladinDiscogsBackfillPoller) return;
      _aladinDiscogsBackfillPoller = setInterval(async () => {
        try {
          const res = await fetch("/aladin-discogs-backfill/status");
          const data = await safeJson(res);
          renderAladinDiscogsBackfillStatus(data);
          if (!data.running) {
            _stopAladinDiscogsBackfillPoller();
            const runBtn = $("aladinDiscogsBackfillRunBtn");
            if (runBtn) runBtn.disabled = false;
            setStatus("aladinDiscogsBackfillStatusBox", data.last_error ? "err" : "ok",
              data.last_error ? `오류: ${data.last_error}` : "✅ 완료");
          }
        } catch (_) {}
      }, 5000);
    }

    function _stopAladinDiscogsBackfillPoller() {
      if (_aladinDiscogsBackfillPoller) {
        clearInterval(_aladinDiscogsBackfillPoller);
        _aladinDiscogsBackfillPoller = null;
      }
    }

    async function loadSpotifyBatchStatus() {
      try {
        const res = await fetchWithRetry("/album-masters/spotify/batch/status");
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || "상태 조회 실패");
        const running = data.running;
        const result = data.last_result;
        const err = data.last_error;
        if (running) {
          setStatus("spotifyBatchStatusBox", "ok", "⏳ 실행 중...");
          $("spotifyBatchSummary").textContent = "-";
          return;
        }
        if (err) {
          setStatus("spotifyBatchStatusBox", "err", `오류: ${err}`);
        } else if (result) {
          setStatus("spotifyBatchStatusBox", "ok", `✅ 완료 — 매칭 ${result.matched}건, 미매칭 ${result.skipped}건, 오류 ${result.errors}건`);
        } else {
          setStatus("spotifyBatchStatusBox", "", "대기 중");
        }
      } catch (err) {
        setStatus("spotifyBatchStatusBox", "err", errorMessageText(err, "상태 조회 실패"));
      }
    }

    function _startSpotifyBatchPoller() {
      _stopSpotifyBatchPoller();
      _spotifyBatchPoller = setInterval(async () => {
        try {
          const res = await fetchWithRetry("/album-masters/spotify/batch/status");
          const data = await safeJson(res);
          if (!res.ok) return;
          if (!data.running) {
            _stopSpotifyBatchPoller();
            const runBtn = $("spotifyBatchRunBtn");
            if (runBtn) runBtn.disabled = false;
            if (data.last_error) {
              setStatus("spotifyBatchStatusBox", "err", `오류: ${data.last_error}`);
            } else if (data.last_result) {
              const r = data.last_result;
              setStatus("spotifyBatchStatusBox", "ok", `✅ 완료 — 매칭 ${r.matched}건, 미매칭 ${r.skipped}건, 오류 ${r.errors}건`);
            }
          }
        } catch (_) {}
      }, 5000);
    }

    function _stopSpotifyBatchPoller() {
      if (_spotifyBatchPoller) {
        clearInterval(_spotifyBatchPoller);
        _spotifyBatchPoller = null;
      }
    }

    async function runSpotifyBatch() {
      const limit = Math.max(1, Math.min(500, Number($("spotifyBatchLimit").value || 50)));
      const requireTracks = $("spotifyBatchRequireTracks").checked;
      const runBtn = $("spotifyBatchRunBtn");
      try {
        setStatus("spotifyBatchStatusBox", "ok", "⏳ 배치 시작 요청 중...");
        if (runBtn) runBtn.disabled = true;
        const url = `/album-masters/spotify/batch/run?limit=${limit}&require_tracks=${requireTracks}`;
        const res = await fetchWithRetry(url, { method: "POST" });
        const data = await safeJson(res);
        if (!res.ok) {
          if (runBtn) runBtn.disabled = false;
          throw new Error(data.detail || "실행 요청 실패");
        }
        setStatus("spotifyBatchStatusBox", "ok", `⏳ 실행 중... ${limit}건 처리, 자동으로 결과를 불러옵니다.`);
        _startSpotifyBatchPoller();
      } catch (err) {
        if (runBtn) runBtn.disabled = false;
        setStatus("spotifyBatchStatusBox", "err", errorMessageText(err, "실행 요청 실패"));
      }
    }

    async function runAladinDiscogsBackfill() {
      const dryRun = $("aladinDiscogsBackfillDryRun").checked;
      const sleepSec = parseFloat($("aladinDiscogsBackfillSleep").value || "2.0");
      const runBtn = $("aladinDiscogsBackfillRunBtn");

      try {
        setStatus("aladinDiscogsBackfillStatusBox", "ok", "⏳ 매칭 시작 요청 중...");
        if (runBtn) runBtn.disabled = true;
        const url = `/aladin-discogs-backfill/run?dry_run=${dryRun}&sleep_sec=${sleepSec}`;
        const res = await fetch(url, { method: "POST" });
        const data = await safeJson(res);
        if (!res.ok) {
          if (runBtn) runBtn.disabled = false;
          throw new Error(data.detail || "실행 요청 실패");
        }
        setStatus("aladinDiscogsBackfillStatusBox", "ok",
          `⏳ 실행 중${dryRun ? " (DRY-RUN)" : ""}... 완료까지 수분 소요. 자동으로 결과를 불러옵니다.`);
        _startAladinDiscogsBackfillPoller();
      } catch (err) {
        if (runBtn) runBtn.disabled = false;
        setStatus("aladinDiscogsBackfillStatusBox", "err", errorMessageText(err, "실행 요청 실패"));
      }
    }

    function renderOpsExceptionSummary() {
      const root = $("opsExceptionSummary");
      if (!root) return;
      const activeType = String($("opsExceptionType")?.value || "UNSLOTTED").trim().toUpperCase();
      const types = ["UNSLOTTED", "SOURCE_MISSING", "MASTER_MISSING", "COVER_MISSING", "PREFERRED_SIZE_MISMATCH", "MEDIA_MISSING", "SIZE_MISMATCH", "TRACK_MISSING", "SPOTIFY_UNMATCHED", "REVIEW_MISSING", "GENRE_MISSING", "CATALOG_MISSING", "LOCAL_MISSING", "RELEASE_TYPE_MISSING"];
      root.innerHTML = types.map((type) => `
        <button
          class="ops-exception-box ${activeType === type ? "active" : ""}"
          type="button"
          data-ops-exception-summary="${type}"
        >
          <strong>${countWithUnit(opsExceptionCounts[type] || 0)}</strong>
          <span>${escapeHtml(opsExceptionTypeLabel(type))}</span>
          <span>${escapeHtml(opsExceptionTypeHint(type))}</span>
        </button>
      `).join("");
    }

    function getSelectedOpsExceptionRows() {
      return (Array.isArray(opsExceptionItems) ? opsExceptionItems : [])
        .filter((row) => opsExceptionSelectedIds.has(Number(row?.id || 0)));
    }

    function renderOpsExBulkEditRow(type, selectedCount) {
      const row = $("opsExBulkEditRow");
      if (!row) return;
      if (type === "MEDIA_MISSING") {
        row.innerHTML = `
          <label style="font-size:0.78rem;white-space:nowrap;">미디어 타입</label>
          <select id="opsExBulkMediaType" style="font-size:0.78rem;">
            <option value="">선택</option>
            <option value="Vinyl">Vinyl (LP)</option>
            <option value="CD">CD</option>
            <option value="Cassette">Cassette</option>
            <option value='7"'>7"</option>
            <option value='10"'>10"</option>
            <option value="DVD">DVD</option>
            <option value="Blu-ray">Blu-ray</option>
            <option value="8-Track Cartridge">8-Track</option>
            <option value="SACD">SACD</option>
            <option value="CDr">CDr</option>
            <option value="Reel-To-Reel">Reel-To-Reel</option>
          </select>
          <button id="opsExBulkApplyBtn" class="btn ghost tiny" type="button" disabled>
            선택 ${selectedCount}건 일괄 적용
          </button>
        `;
        $("opsExBulkMediaType")?.addEventListener("change", () => {
          if ($("opsExBulkApplyBtn")) $("opsExBulkApplyBtn").disabled = !$("opsExBulkMediaType").value;
        });
      } else if (type === "RELEASE_TYPE_MISSING") {
        row.innerHTML = `
          <label style="font-size:0.78rem;white-space:nowrap;">앨범 타입</label>
          <select id="opsExBulkReleaseType" style="font-size:0.78rem;">
            <option value="">선택</option>
            <option value="ALBUM">ALBUM</option>
            <option value="EP">EP</option>
            <option value="SINGLE">SINGLE</option>
          </select>
          <button id="opsExBulkApplyBtn" class="btn ghost tiny" type="button" disabled>
            선택 ${selectedCount}건 일괄 적용
          </button>
        `;
        $("opsExBulkReleaseType")?.addEventListener("change", () => {
          if ($("opsExBulkApplyBtn")) $("opsExBulkApplyBtn").disabled = !$("opsExBulkReleaseType").value;
        });
      } else if (type === "SIZE_MISMATCH") {
        const sizeGroupOptions = `
            <option value="">선택 안 함</option>
            <option value="LP">LP</option>
            <option value="STD">STD (CD)</option>
            <option value="LP7">LP 7"</option>
            <option value="LP10">LP 10"</option>
            <option value="CASSETTE">Cassette</option>
            <option value="8TRACK">8-Track</option>
            <option value="REEL_TO_REEL">Reel-to-Reel</option>
            <option value="BOOK">Book</option>
            <option value="OVERSIZE">Oversize</option>`;
        row.innerHTML = `
          <label style="font-size:0.78rem;white-space:nowrap;">규격 그룹</label>
          <select id="opsExBulkSizeGroup" style="font-size:0.78rem;">${sizeGroupOptions}</select>
          <label style="font-size:0.78rem;white-space:nowrap;">보관 규격</label>
          <select id="opsExBulkPrefSizeGroup" style="font-size:0.78rem;">${sizeGroupOptions}</select>
          <button id="opsExBulkApplyBtn" class="btn ghost tiny" type="button" disabled>
            선택 ${selectedCount}건 일괄 적용
          </button>
        `;
        const updateBulkSizeApplyBtn = () => {
          const hasVal = !!$("opsExBulkSizeGroup")?.value || !!$("opsExBulkPrefSizeGroup")?.value;
          if ($("opsExBulkApplyBtn")) $("opsExBulkApplyBtn").disabled = !hasVal;
        };
        $("opsExBulkSizeGroup")?.addEventListener("change", updateBulkSizeApplyBtn);
        $("opsExBulkPrefSizeGroup")?.addEventListener("change", updateBulkSizeApplyBtn);
      }
      $("opsExBulkApplyBtn")?.addEventListener("click", () => applyOpsExBulk(type));
    }

    async function applyOpsExBulk(type) {
      const btn = $("opsExBulkApplyBtn");
      const statusEl = $("opsExBulkEditStatus");
      const selectedIds = Array.from(opsExceptionSelectedIds);
      if (!selectedIds.length) return;

      if (btn) btn.disabled = true;
      if (statusEl) statusEl.textContent = `적용 중... (0/${selectedIds.length})`;

      try {
        let res;
        if (type === "MEDIA_MISSING") {
          const mediaType = $("opsExBulkMediaType")?.value;
          if (!mediaType) return;
          res = await fetchWithRetry("/owned-items/bulk-update-music-detail", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ owned_item_ids: selectedIds, media_type: mediaType }),
          });
        } else if (type === "SIZE_MISMATCH") {
          const sizeGroup = $("opsExBulkSizeGroup")?.value;
          const prefSizeGroup = $("opsExBulkPrefSizeGroup")?.value;
          if (!sizeGroup && !prefSizeGroup) return;
          const bulkBody = { owned_item_ids: selectedIds };
          if (sizeGroup) bulkBody.size_group = sizeGroup;
          if (prefSizeGroup) bulkBody.preferred_storage_size_group = prefSizeGroup;
          res = await fetchWithRetry("/owned-items/bulk-update", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(bulkBody),
          });
        } else if (type === "RELEASE_TYPE_MISSING") {
          const releaseType = $("opsExBulkReleaseType")?.value;
          if (!releaseType) return;
          let ok = 0, fail = 0;
          for (const masterId of selectedIds) {
            if (statusEl) statusEl.textContent = `적용 중... (${ok + fail + 1}/${selectedIds.length}) 성공: ${ok} 실패: ${fail}`;
            try {
              const r = await fetchWithRetry(`/album-masters/${masterId}/correction`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ release_type: releaseType }),
              });
              if (r.ok) { ok++; opsExceptionSelectedIds.delete(Number(masterId)); }
              else fail++;
            } catch (_) { fail++; }
          }
          if (statusEl) statusEl.textContent = `완료 — 성공: ${ok}건 / 실패: ${fail}건`;
          if (btn) btn.disabled = false;
          setTimeout(() => loadOpsExceptionItems({ silent: true }), 1000);
          return;
        } else {
          return;
        }

        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || "적용 실패");
        const okCount = Number(data.updated_count || 0);
        const failCount = selectedIds.length - okCount;
        if (statusEl) statusEl.textContent = `완료 — 성공: ${okCount}건 / 실패: ${failCount}건`;
        (data.updated_item_ids || []).forEach(id => opsExceptionSelectedIds.delete(Number(id)));
        setTimeout(() => loadOpsExceptionItems({ silent: true }), 1500);
      } catch (err) {
        if (statusEl) statusEl.textContent = `오류: ${escapeHtml(String(err.message || err))}`;
      } finally {
        if (btn) btn.disabled = false;
      }
    }

    function syncOpsExceptionSelectionControls() {
      const activeType = String($("opsExceptionType")?.value || "UNSLOTTED").trim().toUpperCase();
      const selectedRows = getSelectedOpsExceptionRows();
      const selectedCount = selectedRows.length;
      const summary = $("opsExceptionSelectionSummary");
      if (summary) {
        summary.textContent = t("ops.exception.selection.summary", {
          type: opsExceptionTypeLabel(activeType),
          total: countWithUnit(opsExceptionTotalCount),
          selected: countWithUnit(selectedCount),
        });
      }
      const allowSource = selectedCount > 0 && (activeType === "SOURCE_MISSING" || activeType === "TRACK_MISSING" || activeType === "COVER_MISSING");
      const allowAlign = selectedCount > 0 && activeType === "PREFERRED_SIZE_MISMATCH";
      const allowMaster = selectedCount > 0 && activeType === "MASTER_MISSING";
      const allowReview = selectedCount > 0 && activeType === "REVIEW_MISSING";
      if ($("opsExceptionBulkSourceBtn")) $("opsExceptionBulkSourceBtn").disabled = !allowSource;
      if ($("opsExceptionBulkAlignBtn")) $("opsExceptionBulkAlignBtn").disabled = !allowAlign;
      if ($("opsExceptionBulkMasterBtn")) $("opsExceptionBulkMasterBtn").disabled = !allowMaster;
      const reviewBtn = $("opsExceptionBulkReviewBtn");
      if (reviewBtn) { reviewBtn.style.display = activeType === "REVIEW_MISSING" ? "" : "none"; reviewBtn.disabled = !allowReview; }
      const isMasterType = (activeType === "SPOTIFY_UNMATCHED" || activeType === "GENRE_MISSING"
                            || activeType === "CATALOG_MISSING" || activeType === "REVIEW_MISSING"
                            || activeType === "LOCAL_MISSING" || activeType === "RELEASE_TYPE_MISSING");
      if ($("opsExceptionSelectAllBtn")) $("opsExceptionSelectAllBtn").disabled = !(Array.isArray(opsExceptionItems) && opsExceptionItems.length);
      if ($("opsExceptionClearBtn")) $("opsExceptionClearBtn").disabled = selectedCount <= 0;
      const BULK_EDIT_TYPES = new Set(["MEDIA_MISSING", "SIZE_MISMATCH", "RELEASE_TYPE_MISSING"]);
      const showBulkEdit = BULK_EDIT_TYPES.has(activeType) && selectedCount > 0;
      const bulkEditRow = $("opsExBulkEditRow");
      if (bulkEditRow) {
        bulkEditRow.style.display = showBulkEdit ? "flex" : "none";
        if (showBulkEdit) renderOpsExBulkEditRow(activeType, selectedCount);
      }
      if (!showBulkEdit && $("opsExBulkEditStatus")) $("opsExBulkEditStatus").textContent = "";
    }

    function _opsExCtxEditFormHtml(type, data) {
      if (type === "MEDIA_MISSING") {
        const cur = data.music_detail?.media_type || "";
        const opts = [
          "Vinyl","CD","Cassette",'7"','10"',"DVD","Blu-ray",
          "8-Track Cartridge","SACD","CDr","Reel-To-Reel",
        ].map(v => `<option value="${escapeHtml(v)}"${cur===v?" selected":""}>${escapeHtml(v)}</option>`).join("");
        return `
          <div style="display:flex;flex-direction:column;gap:6px;">
            <label style="font-size:0.72rem;color:var(--muted);">미디어 타입</label>
            <div style="display:flex;gap:6px;align-items:center;">
              <select id="opsExCtxMediaType" style="flex:1;font-size:0.78rem;">
                <option value="">선택</option>${opts}
              </select>
              <button id="opsExCtxSaveBtn" class="btn ghost tiny save" type="button">저장</button>
            </div>
            <div id="opsExCtxEditStatus" class="status mini"></div>
          </div>`;
      }
      if (type === "SIZE_MISMATCH") {
        const cur = data.size_group || "";
        const curPref = data.preferred_storage_size_group || "";
        const sizeOpts = [
          ["LP","LP"],["STD","STD (CD)"],["LP7",'LP 7"'],["LP10",'LP 10"'],
          ["CASSETTE","Cassette"],["8TRACK","8-Track"],["REEL_TO_REEL","Reel-to-Reel"],
          ["BOOK","Book"],["OVERSIZE","Oversize"],
        ].map(([v,l]) => `<option value="${v}"${cur===v?" selected":""}>${escapeHtml(l)}</option>`).join("");
        const prefOpts = [
          ["LP","LP"],["STD","STD (CD)"],["LP7",'LP 7"'],["LP10",'LP 10"'],
          ["CASSETTE","Cassette"],["8TRACK","8-Track"],["REEL_TO_REEL","Reel-to-Reel"],
          ["BOOK","Book"],["OVERSIZE","Oversize"],
        ].map(([v,l]) => `<option value="${v}"${curPref===v?" selected":""}>${escapeHtml(l)}</option>`).join("");
        return `
          <div style="display:flex;flex-direction:column;gap:6px;">
            <label style="font-size:0.72rem;color:var(--muted);">규격 그룹</label>
            <select id="opsExCtxSizeGroup" style="font-size:0.78rem;">
              <option value="">선택 안 함</option>${sizeOpts}
            </select>
            <label style="font-size:0.72rem;color:var(--muted);">보관 규격</label>
            <select id="opsExCtxPrefSizeGroup" style="font-size:0.78rem;">
              <option value="">선택 안 함</option>${prefOpts}
            </select>
            <div style="display:flex;gap:6px;align-items:center;">
              <button id="opsExCtxSaveBtn" class="btn ghost tiny save" type="button">저장</button>
            </div>
            <div id="opsExCtxEditStatus" class="status mini"></div>
          </div>`;
      }
      if (type === "CATALOG_MISSING") {
        const catalogNo = escapeHtml(data.music_detail?.catalog_no || "");
        const labelName = escapeHtml(data.music_detail?.label_name || "");
        return `
          <div style="display:flex;flex-direction:column;gap:6px;">
            <label style="font-size:0.72rem;color:var(--muted);">카탈로그 번호</label>
            <input id="opsExCtxCatalogNo" type="text" value="${catalogNo}" style="font-size:0.78rem;" />
            <label style="font-size:0.72rem;color:var(--muted);">레이블</label>
            <input id="opsExCtxLabelName" type="text" value="${labelName}" style="font-size:0.78rem;" />
            <div style="display:flex;gap:6px;">
              <button id="opsExCtxSaveBtn" class="btn ghost tiny save" type="button">저장</button>
            </div>
            <div id="opsExCtxEditStatus" class="status mini"></div>
          </div>`;
      }
      return "";
    }

    function _bindOpsExCtxEditForm(type, ownedItemId, data) {
      const saveBtn = $("opsExCtxSaveBtn");
      const statusEl = $("opsExCtxEditStatus");
      if (!saveBtn) return;

      saveBtn.addEventListener("click", async () => {
        saveBtn.disabled = true;
        if (statusEl) statusEl.textContent = "저장 중...";
        try {
          // PATCH는 OwnedItemCreate 전체 스키마를 필요로 하므로 기존 data와 병합
          const base = {
            category: data.category,
            size_group: data.size_group,
            preferred_storage_size_group: data.preferred_storage_size_group,
            status: data.status,
            is_second_hand: data.is_second_hand,
            quantity: data.quantity || 1,
            signature_type: data.signature_type,
            source_code: data.source_code,
            source_external_id: data.source_external_id,
            linked_album_master_id: data.linked_album_master_id,
            linked_artist_name: data.linked_artist_name,
            item_name_override: data.item_name_override,
            storage_slot_id: data.storage_slot_id,
            notes: data.notes,
            music_detail: data.music_detail || null,
          };
          let patch;
          if (type === "MEDIA_MISSING") {
            const v = $("opsExCtxMediaType")?.value;
            if (!v) throw new Error("미디어 타입을 선택하세요");
            patch = { music_detail: { ...(base.music_detail || {}), media_type: v } };
          } else if (type === "SIZE_MISMATCH") {
            const sg = $("opsExCtxSizeGroup")?.value;
            const psg = $("opsExCtxPrefSizeGroup")?.value;
            if (!sg && !psg) throw new Error("규격 그룹 또는 보관 규격을 선택하세요");
            patch = {};
            if (sg) patch.size_group = sg;
            if (psg) patch.preferred_storage_size_group = psg;
          } else if (type === "CATALOG_MISSING") {
            const catalogNo = String($("opsExCtxCatalogNo")?.value || "").trim();
            const labelName = String($("opsExCtxLabelName")?.value || "").trim();
            if (!catalogNo && !labelName) throw new Error("카탈로그 번호 또는 레이블을 입력하세요");
            patch = { music_detail: { ...(base.music_detail || {}), catalog_no: catalogNo || null, label_name: labelName || null } };
          } else {
            return;
          }
          const body = { ...base, ...patch };
          const res = await fetchWithRetry(`/owned-items/${ownedItemId}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          });
          const resp = await safeJson(res);
          if (!res.ok) throw new Error(resp.detail || "저장 실패");
          if (statusEl) statusEl.textContent = "저장됨";
          opsExceptionItems = opsExceptionItems.filter(r => Number(r.id) !== Number(ownedItemId));
          opsExceptionSelectedIds.delete(Number(ownedItemId));
          opsExceptionTotalCount = Math.max(0, opsExceptionTotalCount - 1);
          if (opsExceptionCounts && opsExceptionCounts[type] !== undefined) {
            opsExceptionCounts[type] = Math.max(0, opsExceptionCounts[type] - 1);
          }
          renderOpsExceptionSummary();
          renderOpsExceptionList();
          renderOpsExceptionContextPanel(null, "");
        } catch (err) {
          if (statusEl) statusEl.textContent = `오류: ${escapeHtml(String(err.message || err))}`;
        } finally {
          saveBtn.disabled = false;
        }
      });
    }

    async function renderOpsExceptionContextPanel(row, type) {
      const card = $("opsExContextCard");
      const body = $("opsExContextBody");
      const empty = $("opsExContextEmpty");
      if (!card || !body) return;
      if (!row) {
        card.style.display = "none";
        if (empty) empty.style.display = "";
        return;
      }
      card.style.display = "";
      if (empty) empty.style.display = "none";

      const isMasterType = (type === "SPOTIFY_UNMATCHED" || type === "REVIEW_MISSING" || type === "LOCAL_MISSING" || type === "RELEASE_TYPE_MISSING");

      if (isMasterType) {
        const masterId = Number(row.id || 0);
        const title = String(row.title || "-").trim();
        const artist = String(row.artist_or_brand || "-").trim();
        const year = row.release_year ? ` (${row.release_year})` : "";
        const cover = normalizeRenderableCoverUrl(row.cover_image_url);
        const coverHtml = cover
          ? `<img src="${escapeHtml(cover)}" style="width:64px;height:64px;object-fit:cover;border-radius:8px;border:1px solid var(--line);" />`
          : `<div style="width:64px;height:64px;border-radius:8px;border:1px solid var(--line);background:var(--paper);display:flex;align-items:center;justify-content:center;font-size:0.7rem;color:var(--muted);">${escapeHtml(artist.substring(0,2).toUpperCase()||"?")}</div>`;
        body.innerHTML = `
          <div style="display:flex;gap:10px;align-items:flex-start;margin-bottom:8px;">
            ${coverHtml}
            <div style="min-width:0;">
              <div style="font-weight:700;font-size:0.85rem;line-height:1.2;">${escapeHtml(artist)}</div>
              <div style="font-size:0.8rem;margin-top:2px;">${escapeHtml(title)}${escapeHtml(year)}</div>
              <div class="mini muted" style="margin-top:4px;">master #${masterId}</div>
            </div>
          </div>
          <div id="opsExCtxMasterItems" class="mini muted">보유 상품 조회 중...</div>
          <div id="opsExCtxMasterActions" style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;">
            <button class="btn ghost tiny" type="button"
              onclick="openMediaSearchDetailManage(${masterId},0)">관리 화면으로</button>
            <button class="btn ghost tiny search" type="button"
              data-ops-exception-review-auto="${masterId}">소스 자동수집</button>
          </div>
        `;
        try {
          const res = await fetchWithRetry(`/album-masters/${masterId}/members`);
          const data = await safeJson(res);
          const items = Array.isArray(data) ? data : [];
          const el = $("opsExCtxMasterItems");
          if (!el) return;
          if (!items.length) { el.textContent = "보유 상품 없음"; return; }
          const firstId = Number(items[0]?.id || 0);
          // 관리 화면으로 버튼에 첫 상품 ID 반영
          const actionsEl = $("opsExCtxMasterActions");
          if (actionsEl && firstId > 0) {
            const manageBtn = actionsEl.querySelector("button");
            if (manageBtn) manageBtn.setAttribute("onclick", `openMediaSearchDetailManage(${masterId},${firstId})`);
          }
          el.innerHTML = `<strong style="font-size:0.75rem;">보유 상품 ${items.length}건</strong><div style="margin-top:4px;display:flex;flex-direction:column;gap:2px;">${
            items.slice(0,5).map(it => {
              const name = resolveOwnedAlbumName(it);
              const loc = it.slot_code || t("common.unslotted");
              return `<div style="font-size:0.72rem;">${escapeHtml(name)} — ${escapeHtml(loc)}</div>`;
            }).join("")
          }${items.length > 5 ? `<div class="mini muted">외 ${items.length-5}건</div>` : ""}</div>`;
        } catch (_) {}
      } else {
        const ownedItemId = Number(row.id || 0);
        body.innerHTML = `<div class="mini muted">상품 #${ownedItemId} 상세 조회 중...</div>`;
        try {
          const res = await fetchWithRetry(`/owned-items/${ownedItemId}`);
          const data = await safeJson(res);
          if (!res.ok) throw new Error(data.detail || "조회 실패");
          const name = resolveOwnedAlbumName(data);
          const loc = data.slot_code || t("common.unslotted");
          const artist = data.music_detail?.artist_or_brand || data.linked_artist_name || "-";
          const label = data.music_detail?.label_name || "-";
          const catno = data.music_detail?.catalog_no || "-";
          const cover = normalizeRenderableCoverUrl(data.music_detail?.cover_image_url);
          const coverHtml = cover
            ? `<img src="${escapeHtml(cover)}" style="width:64px;height:64px;object-fit:cover;border-radius:8px;border:1px solid var(--line);" />`
            : "";
          body.innerHTML = `
            <div style="display:flex;gap:10px;align-items:flex-start;margin-bottom:8px;">
              ${coverHtml}
              <div style="min-width:0;">
                <div style="font-weight:700;font-size:0.85rem;">${escapeHtml(artist)}</div>
                <div style="font-size:0.8rem;margin-top:2px;">${escapeHtml(name)}</div>
                <div class="mini muted" style="margin-top:4px;">${escapeHtml(label)} / ${escapeHtml(catno)}</div>
                <div class="mini muted">위치: ${escapeHtml(loc)}</div>
              </div>
            </div>
            <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;">
              <button class="btn ghost tiny" type="button"
                onclick="openMediaSearchDetailManage(0,${ownedItemId})">관리 화면으로</button>
            </div>
          `;
          const editFormHtml = _opsExCtxEditFormHtml(type, data);
          if (editFormHtml) {
            body.innerHTML += `<div id="opsExCtxEditSection" style="margin-top:12px;border-top:1px solid var(--line);padding-top:10px;">${editFormHtml}</div>`;
            _bindOpsExCtxEditForm(type, ownedItemId, data);
          }
        } catch (err) {
          body.innerHTML = `<div class="mini muted" style="color:var(--err);">오류: ${escapeHtml(String(err.message||err))}</div>`;
        }
      }
    }

    function renderOpsExceptionList() {
      const root = $("opsExceptionList");
      if (!root) return;
      $("opsExceptionCount").textContent = countWithUnit(opsExceptionTotalCount);
      if (opsExceptionLoading) {
        root.innerHTML = `<div class='mini muted'>${escapeHtml(t("ops.exception.status.list_loading"))}</div>`;
        syncOpsExceptionSelectionControls();
        return;
      }
      if (!Array.isArray(opsExceptionItems) || !opsExceptionItems.length) {
        root.innerHTML = `<div class='mini muted'>${escapeHtml(t("ops.exception.status.list_empty"))}</div>`;
        syncOpsExceptionSelectionControls();
        return;
      }
      const activeType = String($("opsExceptionType")?.value || "UNSLOTTED").trim().toUpperCase();

      // --- Album Master rows (SPOTIFY_UNMATCHED / REVIEW_MISSING) ---
      // --- Owned Item rows with inline edit (GENRE_MISSING / CATALOG_MISSING) ---
      if (activeType === "SPOTIFY_UNMATCHED" || activeType === "GENRE_MISSING" || activeType === "CATALOG_MISSING" || activeType === "REVIEW_MISSING" || activeType === "LOCAL_MISSING" || activeType === "RELEASE_TYPE_MISSING") {
        root.innerHTML = opsExceptionItems.map((item, idx) => {
          const id = Number(item.id || 0);
          const rawTitle = String(item.title || item.master_title || item.item_name_override || "-").trim();
          const artist = String(item.artist_or_brand || item.master_artist_or_brand || "-").trim();
          const releaseYear = item.release_year || item.master_release_year || "";
          const displayTitle = artist !== "-" ? `${artist} - ${rawTitle}` : rawTitle;
          const displayTitleWithYear = releaseYear ? `${displayTitle} (${releaseYear})` : displayTitle;
          const coverUrl = normalizeRenderableCoverUrl(item.cover_image_url || item.thumbnail_url);
          const coverHtml = coverUrl
            ? `<img src="${escapeHtml(coverUrl)}" alt="${escapeHtml(rawTitle)}" />`
            : `<span class="ops-exception-cover-placeholder">${escapeHtml(artist.substring(0, 2).toUpperCase() || "?")}</span>`;

          if (activeType === "CATALOG_MISSING") {
            const labelName = item.label_name || "";
            const catalogNo = item.catalog_no || "";
            return `
              <div class="ops-exception-row" data-ops-ex-row-idx="${idx}">
                <div class="ops-exception-cover">${coverHtml}</div>
                <div class="ops-exception-main" style="flex:1;min-width:0;">
                  <div class="ops-exception-title">${escapeHtml(displayTitleWithYear)}</div>
                  <div class="ops-exception-meta">상품 #${id}</div>
                  <div class="ops-exception-edit-row">
                    <input type="text" class="ops-exception-inline-input" style="flex:1;min-width:100px;" placeholder="레이블" data-oi-id="${id}" data-field="label_name" value="${escapeHtml(labelName)}" />
                    <input type="text" class="ops-exception-inline-input" style="flex:1;min-width:120px;" placeholder="카탈로그 넘버" data-oi-id="${id}" data-field="catalog_no" value="${escapeHtml(catalogNo)}" />
                    <button class="btn ghost tiny save" data-ops-catalog-save="${id}" style="flex-shrink:0;">저장</button>
                    <span class="ops-catalog-save-status mini muted" data-save-status="${id}"></span>
                  </div>
                </div>
              </div>`;
          }

          if (activeType === "GENRE_MISSING") {
            const masterId = id;
            const genresJoined  = (Array.isArray(item.genres)  ? item.genres  : []).join(", ");
            const stylesJoined  = (Array.isArray(item.styles)  ? item.styles  : []).join(", ");
            return `
              <div class="ops-exception-row" data-ops-ex-row-idx="${idx}">
                <div class="ops-exception-cover">${coverHtml}</div>
                <div class="ops-exception-main" style="flex:1;min-width:0;">
                  <div class="ops-exception-title">${escapeHtml(displayTitleWithYear)}</div>
                  <div class="ops-exception-meta">master #${masterId}</div>
                  <div class="ops-exception-edit-row">
                    <input type="text" class="ops-exception-inline-input" style="flex:2;min-width:160px;"
                      placeholder="장르 (쉼표 구분, 예: Rock, Pop)"
                      data-master-id="${masterId}" data-field="genres"
                      value="${escapeHtml(genresJoined)}" />
                    <input type="text" class="ops-exception-inline-input" style="flex:2;min-width:160px;"
                      placeholder="스타일 (쉼표 구분, 예: Indie Rock, Shoegaze)"
                      data-master-id="${masterId}" data-field="styles"
                      value="${escapeHtml(stylesJoined)}" />
                    <button class="btn ghost tiny save" data-ops-genre-save="${masterId}" style="flex-shrink:0;">저장</button>
                    <span class="mini muted" data-save-status="${masterId}"></span>
                  </div>
                </div>
              </div>`;
          }

          if (activeType === "LOCAL_MISSING") {
            const masterId = id;
            const inputId = `opsLocalPath_${masterId}`;
            const dropId  = `opsLocalDrop_${masterId}`;
            return `
              <div class="ops-exception-row" data-ops-ex-row-idx="${idx}">
                <div class="ops-exception-cover">${coverHtml}</div>
                <div class="ops-exception-main" style="flex:1;min-width:0;">
                  <div class="ops-exception-title">${escapeHtml(displayTitleWithYear)}</div>
                  <div class="ops-exception-meta">master #${masterId}</div>
                  <div class="ops-exception-edit-row" style="flex-direction:column;align-items:stretch;">
                    <div style="display:flex;gap:4px;align-items:center;">
                      <input type="text" id="${escapeHtml(inputId)}"
                        class="ops-exception-inline-input" style="flex:1;"
                        placeholder="아티스트 또는 앨범명으로 검색…" autocomplete="off"
                        data-ops-local-master="${masterId}" />
                      <button class="btn ghost tiny save" data-ops-local-save="${masterId}" style="flex-shrink:0;">저장</button>
                      <span class="mini muted" data-save-status="${masterId}"></span>
                    </div>
                    <div id="${escapeHtml(dropId)}" style="display:none;border:1px solid var(--line);border-radius:6px;background:var(--paper);max-height:160px;overflow-y:auto;font-size:0.72rem;"></div>
                  </div>
                </div>
              </div>`;
          }

          if (activeType === "RELEASE_TYPE_MISSING") {
            const masterId = id;
            const checked = opsExceptionSelectedIds.has(masterId);
            return `
              <div class="ops-exception-row ops-exception-row--with-check ${checked ? "is-selected" : ""}" data-ops-ex-row-idx="${idx}">
                <label class="ops-exception-check"><input type="checkbox" data-ops-exception-release-type-check="${masterId}" ${checked ? "checked" : ""} /></label>
                <div class="ops-exception-cover">${coverHtml}</div>
                <div class="ops-exception-main" style="flex:1;min-width:0;">
                  <div class="ops-exception-title">${escapeHtml(displayTitleWithYear)}</div>
                  <div class="ops-exception-meta">master #${masterId}</div>
                  <div class="ops-exception-edit-row">
                    <select class="ops-exception-inline-input" data-master-id="${masterId}" data-field="release_type" style="flex:1;min-width:120px;">
                      <option value="">-- 선택 --</option>
                      <option value="ALBUM">ALBUM</option>
                      <option value="EP">EP</option>
                      <option value="SINGLE">SINGLE</option>
                    </select>
                    <button class="btn ghost tiny save" data-ops-release-type-save="${masterId}" style="flex-shrink:0;">저장</button>
                    <span class="mini muted" data-save-status="${masterId}"></span>
                  </div>
                </div>
              </div>`;
          }

          // SPOTIFY_UNMATCHED / REVIEW_MISSING — existing master logic
          const masterId2 = id;
          const metaBits = [`master #${masterId2}`, opsExceptionTypeHint(activeType)].filter(Boolean);
          const checked = opsExceptionSelectedIds.has(masterId2);
          const checkboxHtml = activeType === "REVIEW_MISSING"
            ? `<label class="ops-exception-check"><input type="checkbox" data-ops-exception-master-check="${masterId2}" ${checked ? "checked" : ""} /></label>`
            : "";
          const actionBtn = activeType === "REVIEW_MISSING"
            ? `<button class="btn ghost" type="button" data-ops-exception-review-auto="${masterId2}">${escapeHtml(t("media.manage.master.review.action.auto") || "Wikipedia 자동수집")}</button>`
            : `<button class="btn ghost" type="button" data-ops-exception-spotify-match="${masterId2}" data-spotify-match-title="${escapeHtml(rawTitle)}" data-spotify-match-artist="${escapeHtml(artist)}">${escapeHtml(t("ops.exception.action.spotify_match"))}</button>`;
          return `
            <div class="ops-exception-row${activeType === "REVIEW_MISSING" ? " ops-exception-row--with-check" : ""} ${checked ? "is-selected" : ""}" data-ops-ex-row-idx="${idx}">
              ${checkboxHtml}
              <div class="ops-exception-cover">${coverHtml}</div>
              <div class="ops-exception-main">
                <div class="ops-exception-title">${escapeHtml(displayTitleWithYear)}</div>
                <div class="ops-exception-meta">${escapeHtml(metaBits.join(" | "))}</div>
              </div>
              <div class="ops-exception-actions">${actionBtn}</div>
            </div>`;
        }).join("");

        // 페이징 컨트롤
        const pageSize = 50;
        const hasPrev = opsExceptionOffset > 0;
        const hasNext = (opsExceptionOffset + pageSize) < opsExceptionTotalCount;
        if (hasPrev || hasNext) {
          const pageInfo = `${opsExceptionOffset + 1}–${Math.min(opsExceptionOffset + opsExceptionItems.length, opsExceptionTotalCount)} / ${opsExceptionTotalCount}`;
          root.innerHTML += `
            <div style="display:flex;align-items:center;gap:8px;padding:8px 0;margin-top:4px;border-top:1px solid var(--line);">
              <button class="btn ghost tiny" id="opsExPrevBtn" ${hasPrev ? "" : "disabled"}>◀ 이전</button>
              <span class="mini muted" style="flex:1;text-align:center;">${escapeHtml(pageInfo)}</span>
              <button class="btn ghost tiny" id="opsExNextBtn" ${hasNext ? "" : "disabled"}>다음 ▶</button>
            </div>`;
          root.querySelector("#opsExPrevBtn")?.addEventListener("click", () => {
            opsExceptionOffset = Math.max(0, opsExceptionOffset - pageSize);
            loadOpsExceptionItems({ resetOffset: false });
          });
          root.querySelector("#opsExNextBtn")?.addEventListener("click", () => {
            opsExceptionOffset += pageSize;
            loadOpsExceptionItems({ resetOffset: false });
          });
        }

        // wire row click → context panel (SPOTIFY_UNMATCHED / REVIEW_MISSING)
        root.querySelectorAll(".ops-exception-row[data-ops-ex-row-idx]").forEach((rowEl) => {
          rowEl.style.cursor = "pointer";
          rowEl.addEventListener("click", (e) => {
            if (e.target.closest("input,button,a,label")) return;
            const idx = Number(rowEl.dataset.opsExRowIdx || -1);
            const it = Array.isArray(opsExceptionItems) ? opsExceptionItems[idx] : null;
            root.querySelectorAll(".ops-exception-row").forEach(r => r.classList.remove("is-ctx-selected"));
            rowEl.classList.add("is-ctx-selected");
            void renderOpsExceptionContextPanel(it, activeType);
          });
        });

        // wire REVIEW_MISSING checkboxes
        root.querySelectorAll("[data-ops-exception-master-check]").forEach((cb) => {
          cb.addEventListener("change", () => {
            const mid = Number(cb.getAttribute("data-ops-exception-master-check") || 0);
            if (cb.checked) opsExceptionSelectedIds.add(mid); else opsExceptionSelectedIds.delete(mid);
            renderOpsExceptionList();
          });
        });

        // wire CATALOG_MISSING save buttons
        root.querySelectorAll("[data-ops-catalog-save]").forEach((btn) => {
          btn.addEventListener("click", async (e) => {
            e.stopPropagation();
            const oiId = btn.dataset.opsCatalogSave;
            const rowEl = btn.closest(".ops-exception-row");
            const labelInput = rowEl.querySelector("[data-field='label_name']");
            const catalogInput = rowEl.querySelector("[data-field='catalog_no']");
            const statusEl = rowEl.querySelector(`[data-save-status='${oiId}']`);
            btn.disabled = true;
            if (statusEl) statusEl.textContent = "저장 중...";
            try {
              const res = await fetchWithRetry(`/owned-items/${oiId}/catalog`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ catalog_no: catalogInput?.value || null, label_name: labelInput?.value || null }),
              });
              if (!res.ok) throw new Error((await safeJson(res)).detail || "저장 실패");
              if (statusEl) statusEl.textContent = "저장됨";
              setTimeout(() => rowEl.remove(), 600);
            } catch (err) {
              if (statusEl) statusEl.textContent = `오류: ${escapeHtml(String(err.message || err))}`;
              btn.disabled = false;
            }
          });
        });

        // wire GENRE_MISSING save buttons
        root.querySelectorAll("[data-ops-genre-save]").forEach((btn) => {
          btn.addEventListener("click", async (e) => {
            e.stopPropagation();
            const masterId = btn.dataset.opsGenreSave;
            const rowEl = btn.closest(".ops-exception-row");
            const genreInput  = rowEl.querySelector("[data-field='genres']");
            const styleInput  = rowEl.querySelector("[data-field='styles']");
            const statusEl    = rowEl.querySelector(`[data-save-status='${masterId}']`);
            const genres = (genreInput?.value || "").split(",").map(s => s.trim()).filter(Boolean);
            const styles = (styleInput?.value  || "").split(",").map(s => s.trim()).filter(Boolean);
            if (!genres.length) { if (statusEl) statusEl.textContent = "장르를 입력하세요"; return; }
            btn.disabled = true;
            if (statusEl) statusEl.textContent = "저장 중...";
            try {
              const res = await fetchWithRetry(`/album-masters/${masterId}/correction`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ genres, styles }),
              });
              if (!res.ok) throw new Error((await safeJson(res)).detail || "저장 실패");
              if (statusEl) statusEl.textContent = "저장됨";
              setTimeout(() => rowEl.remove(), 600);
            } catch (err) {
              if (statusEl) statusEl.textContent = `오류: ${escapeHtml(String(err.message || err))}`;
              btn.disabled = false;
            }
          });
        });

        // wire RELEASE_TYPE_MISSING inline save
        root.querySelectorAll("[data-ops-release-type-save]").forEach((btn) => {
          btn.addEventListener("click", async (e) => {
            e.stopPropagation();
            const masterId = btn.dataset.opsReleaseTypeSave;
            const rowEl = btn.closest(".ops-exception-row");
            const sel = rowEl.querySelector("[data-field='release_type']");
            const statusEl = rowEl.querySelector(`[data-save-status='${masterId}']`);
            const releaseType = sel?.value || "";
            if (!releaseType) { if (statusEl) statusEl.textContent = "타입을 선택하세요"; return; }
            btn.disabled = true;
            if (statusEl) statusEl.textContent = "저장 중...";
            try {
              const res = await fetchWithRetry(`/album-masters/${masterId}/correction`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ release_type: releaseType }),
              });
              if (!res.ok) throw new Error((await safeJson(res)).detail || "저장 실패");
              if (statusEl) statusEl.textContent = "저장됨";
              setTimeout(() => rowEl.remove(), 600);
            } catch (err) {
              if (statusEl) statusEl.textContent = `오류: ${escapeHtml(String(err.message || err))}`;
              btn.disabled = false;
            }
          });
        });

        // wire RELEASE_TYPE_MISSING checkboxes
        root.querySelectorAll("[data-ops-exception-release-type-check]").forEach((cb) => {
          cb.addEventListener("change", () => {
            const mid = Number(cb.getAttribute("data-ops-exception-release-type-check") || 0);
            if (cb.checked) opsExceptionSelectedIds.add(mid); else opsExceptionSelectedIds.delete(mid);
            renderOpsExceptionList();
          });
        });

        // wire LOCAL_MISSING search + save
        root.querySelectorAll("[data-ops-local-master]").forEach((input) => {
          const masterId = input.dataset.opsLocalMaster;
          const dropEl = document.getElementById(`opsLocalDrop_${masterId}`);
          let _timer = null;
          let _composing = false;
          input.addEventListener("compositionstart", () => { _composing = true; });
          input.addEventListener("compositionend", () => {
            _composing = false;
            input.dispatchEvent(new Event("input"));
          });
          input.addEventListener("input", () => {
            if (_composing) return;
            clearTimeout(_timer);
            const q = input.value.trim();
            if (q.length < 2) { if (dropEl) dropEl.style.display = "none"; return; }
            _timer = setTimeout(async () => {
              try {
                const res = await fetchWithRetry(`/local-music/search-dirs?q=${encodeURIComponent(q)}&limit=15`);
                if (!res.ok) return;
                const data = await safeJson(res);
                const dirs = data.dirs || [];
                if (!dropEl) return;
                if (!dirs.length) { dropEl.style.display = "none"; return; }
                dropEl.innerHTML = dirs.map(d => `
                  <div class="local-dir-result-row" data-dir-path="${escapeHtml(d.dir_path)}" style="padding:5px 10px;cursor:pointer;border-bottom:1px solid var(--line);">
                    <div style="font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(d.dir_name)}</div>
                    <div style="color:var(--muted);font-size:0.65rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(d.dir_path.replace(/^\/Volumes\/Music\//, "…/"))}</div>
                  </div>`).join("");
                dropEl.style.display = "block";
                dropEl.querySelectorAll(".local-dir-result-row").forEach(row => {
                  row.addEventListener("mousedown", (e) => {
                    e.preventDefault();
                    input.value = row.dataset.dirPath;
                    dropEl.style.display = "none";
                  });
                });
              } catch (_) {}
            }, 250);
          });
          input.addEventListener("blur", () => setTimeout(() => { if (dropEl) dropEl.style.display = "none"; }, 150));
          input.addEventListener("keydown", (e) => { if (e.key === "Escape" && dropEl) dropEl.style.display = "none"; });
        });

        root.querySelectorAll("[data-ops-local-save]").forEach((btn) => {
          btn.addEventListener("click", async (e) => {
            e.stopPropagation();
            const masterId = btn.dataset.opsLocalSave;
            const rowEl = btn.closest(".ops-exception-row");
            const input = rowEl.querySelector(`[data-ops-local-master="${masterId}"]`);
            const statusEl = rowEl.querySelector(`[data-save-status="${masterId}"]`);
            const path = (input?.value || "").trim();
            if (!path) { if (statusEl) statusEl.textContent = "경로를 선택하세요"; return; }
            btn.disabled = true;
            if (statusEl) statusEl.textContent = "저장 중...";
            try {
              const res = await fetchWithRetry(`/album-masters/${masterId}/local-link`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ dir_path: path }),
              });
              if (!res.ok) throw new Error((await safeJson(res)).detail || "저장 실패");
              if (statusEl) statusEl.textContent = "저장됨";
              _localLinkedIds.add(Number(masterId));
              setTimeout(() => rowEl.remove(), 600);
            } catch (err) {
              if (statusEl) statusEl.textContent = `오류: ${escapeHtml(String(err.message || err))}`;
              btn.disabled = false;
            }
          });
        });

        syncOpsExceptionSelectionControls();
        return;
      }

      // --- Standard OwnedItem rows ---
      root.innerHTML = opsExceptionItems.map((row, idx) => {
        const ownedItemId = Number(row.id || 0);
        const checked = opsExceptionSelectedIds.has(ownedItemId);
        const title = resolveOwnedAlbumName(row);
        const coverUrl = normalizeRenderableCoverUrl(row.cover_image_url);
        const coverHtml = coverUrl
          ? `<img src="${escapeHtml(coverUrl)}" alt="${escapeHtml(title)}" />`
          : escapeHtml(mediaDisplayLabel(row.format_name || row.category || "-"));
        const barcodeText = String(row.barcode || "").trim();
        const locationText = row.slot_code || t("common.unslotted");
        const releaseText = String(row.released_date || row.release_year || "-").trim() || "-";
        const sourceText = row.source_code
          ? `${dashboardSourceLabel(row.source_code)}#${row.source_external_id || "-"}`
          : t("common.source.manual");
        const labelCatText = `${row.label_name || "-"} / ${row.catalog_no || "-"}${barcodeText ? ` (${barcodeText})` : ""}`;
        const sizeMismatchText = activeType === "PREFERRED_SIZE_MISMATCH"
          ? (function() {
              const fmtRaw = String(row.format_items_json || "").toUpperCase();
              const media = String(row.media_type || "").trim();
              const sg = String(row.size_group || "LP").trim().toUpperCase();
              const CD_LIKE = ["CD","CDr","SACD","Digital","DVD","Blu-ray","CD-ROM"];
              const VINYL_LIKE = ["Vinyl","LP",'7"','10"',"All Media"];
              const isLpStyle = fmtRaw.includes("LP-STYLE PACKAGING") || fmtRaw.includes("LP STYLE PACKAGING");
              const isBoxSet = fmtRaw.includes("BOX SET");
              const slotSg = String(row.slot_allowed_size_group || "").trim().toUpperCase() || "-";
              const slotLabel = slotSg !== "-" ? dashboardSizeGroupLabel(slotSg) : "-";
              if (isLpStyle) {
                return `슬롯 ${slotLabel} → LP-Style Packaging (LP 또는 OVERSIZE 허용)`;
              }
              if (isBoxSet) {
                // Box Set: 기본 규격 또는 OVERSIZE 모두 허용
                const base = CD_LIKE.includes(media) ? "STD" : media === "Cassette" ? "CASSETTE" : sg || "LP";
                const baseLabel = dashboardSizeGroupLabel(base);
                return `슬롯 ${slotLabel} → Box Set (${baseLabel} 또는 OVERSIZE 허용)`;
              }
              let required = null, reason = "";
              if (media === "Reel-To-Reel") { required = "REEL_TO_REEL"; }
              else if (media === "8-Track Cartridge") { required = "8TRACK"; }
              else if (media === "Cassette") { required = "CASSETTE"; }
              else if (CD_LIKE.includes(media)) {
                if (fmtRaw.includes("DIGIBOOK")) { required = "OVERSIZE"; reason = "Digibook"; }
                else if (fmtRaw.includes("DVD SIZE")) { required = "OVERSIZE"; reason = "DVD Size"; }
                else { required = "STD"; }
              } else if (VINYL_LIKE.includes(media)) { required = sg || "LP"; }
              const reqLabel = required ? dashboardSizeGroupLabel(required) : "-";
              const reasonSuffix = reason ? ` (${reason})` : "";
              return `슬롯 ${slotLabel} → 필요 ${reqLabel}${reasonSuffix}`;
            })()
          : "";
        const trackMissingText = activeType === "TRACK_MISSING"
          ? t("common.meta.track_count", { value: formatCount((Array.isArray(row.track_list) ? row.track_list.length : 0) || (Array.isArray(row.track_items) ? row.track_items.length : 0)) })
          : "";
        const metaBits = [
          row.label_id || `owned_item_id ${ownedItemId}`,
          row.artist_or_brand || row.linked_artist_name || "-",
          sourceText,
        ].filter(Boolean);
        const subBits = [
          t("common.meta.release_date", { value: releaseText }),
          t("common.meta.label_catalog", { value: labelCatText }),
          t("common.meta.location", { value: locationText }),
          sizeMismatchText,
          trackMissingText,
          opsExceptionTypeHint(activeType),
        ].filter(Boolean);
        return `
          <div class="ops-exception-row" data-ops-ex-row-idx="${idx}">
            <div class="ops-exception-cover">${coverHtml}</div>
            <div class="ops-exception-main">
              <div class="ops-exception-title">${escapeHtml(title)}</div>
              <div class="ops-exception-meta">${escapeHtml(metaBits.join(" | "))}</div>
              <div class="ops-exception-submeta">${escapeHtml(subBits.join(" | "))}</div>
            </div>
            <div class="ops-exception-actions">
              <label class="inline-check inline-check--compact">
                <input type="checkbox" data-ops-exception-select="${ownedItemId}" ${checked ? "checked" : ""} />
                <span>${escapeHtml(t("media.source.action.select"))}</span>
              </label>
              ${activeType === "SOURCE_MISSING" || activeType === "TRACK_MISSING" || activeType === "COVER_MISSING" ? `<button class="btn ghost" type="button" data-ops-exception-source="${ownedItemId}">${escapeHtml(t("ops.exception.action.source"))}</button>` : ""}
              ${activeType === "MASTER_MISSING" ? `<button class="btn ghost" type="button" data-ops-exception-master="${ownedItemId}">${escapeHtml(t("ops.exception.action.master"))}</button>` : ""}
              ${activeType === "PREFERRED_SIZE_MISMATCH" ? `<button class="btn ghost" type="button" data-ops-exception-align-size="${ownedItemId}">${escapeHtml(t("ops.exception.action.align_size"))}</button>` : ""}
              <button class="btn ghost" type="button" data-ops-exception-open="${ownedItemId}">${escapeHtml(t("ops.exception.action.edit"))}</button>
            </div>
          </div>
        `;
      }).join("");
      // wire row click → context panel
      root.querySelectorAll(".ops-exception-row[data-ops-ex-row-idx]").forEach((rowEl) => {
        rowEl.style.cursor = "pointer";
        rowEl.addEventListener("click", (e) => {
          if (e.target.closest("input,button,a,label")) return;
          const idx = Number(rowEl.dataset.opsExRowIdx || -1);
          const item = Array.isArray(opsExceptionItems) ? opsExceptionItems[idx] : null;
          root.querySelectorAll(".ops-exception-row").forEach(r => r.classList.remove("is-ctx-selected"));
          rowEl.classList.add("is-ctx-selected");
          void renderOpsExceptionContextPanel(item, activeType);
        });
      });
      syncOpsExceptionSelectionControls();
    }

    async function fetchOpsExceptionCount(type) {
      if (type === "SPOTIFY_UNMATCHED" || type === "GENRE_MISSING" || type === "CATALOG_MISSING" || type === "REVIEW_MISSING" || type === "LOCAL_MISSING" || type === "RELEASE_TYPE_MISSING") {
        const res = await fetchWithRetry(buildMasterExceptionCountUrl(type));
        if (!res.ok) throw new Error(t("ops.exception.status.count_failed", { type: opsExceptionTypeLabel(type) }));
        const headerTotal = Number(res.headers.get("X-Total-Count") || 0);
        return Number.isFinite(headerTotal) ? headerTotal : 0;
      }
      const params = buildOpsExceptionParams(type, { includeTotal: true, limit: 1 });
      const res = await fetchWithRetry(`/owned-items?${params.toString()}`);
      const data = await safeJson(res);
      if (!res.ok) throw new Error(data.detail || t("ops.exception.status.count_failed", { type: opsExceptionTypeLabel(type) }));
      const headerTotal = Number(res.headers.get("X-Total-Count") || 0);
      return Number.isFinite(headerTotal) ? headerTotal : 0;
    }

    async function loadOpsExceptionCounts(opts = {}) {
      const silent = Boolean(opts?.silent);
      const types = ["UNSLOTTED", "SOURCE_MISSING", "MASTER_MISSING", "COVER_MISSING", "PREFERRED_SIZE_MISMATCH", "MEDIA_MISSING", "SIZE_MISMATCH", "TRACK_MISSING", "SPOTIFY_UNMATCHED", "REVIEW_MISSING", "GENRE_MISSING", "CATALOG_MISSING", "LOCAL_MISSING", "RELEASE_TYPE_MISSING"];
      try {
        if (!silent) setStatus("opsExceptionStatus", "ok", t("ops.exception.status.count_loading"));
        const results = await Promise.all(types.map(async (type) => ({
          type,
          count: await fetchOpsExceptionCount(type),
        })));
        opsExceptionCounts = results.reduce((acc, entry) => {
          acc[entry.type] = Number(entry.count || 0);
          return acc;
        }, { UNSLOTTED: 0, SOURCE_MISSING: 0, MASTER_MISSING: 0, COVER_MISSING: 0, PREFERRED_SIZE_MISMATCH: 0, MEDIA_MISSING: 0, SIZE_MISMATCH: 0, TRACK_MISSING: 0, SPOTIFY_UNMATCHED: 0, REVIEW_MISSING: 0, GENRE_MISSING: 0, CATALOG_MISSING: 0, LOCAL_MISSING: 0, RELEASE_TYPE_MISSING: 0 });
        renderOpsExceptionSummary();
        if (!silent) setStatus("opsExceptionStatus", "ok", t("ops.exception.status.count_loaded"));
      } catch (err) {
        renderOpsExceptionSummary();
        if (!silent) setStatus("opsExceptionStatus", "err", err.message);
      }
    }

    async function loadOpsExceptionItems(opts = {}) {
      const silent = Boolean(opts?.silent);
      const resetOffset = Boolean(opts?.resetOffset !== false && !opts?.silent);
      const type = String($("opsExceptionType")?.value || "UNSLOTTED").trim().toUpperCase();
      const limit = 50;
      if (resetOffset) opsExceptionOffset = 0;
      try {
        opsExceptionLoading = true;
        renderOpsExceptionSummary();
        renderOpsExceptionList();
        if (!silent) setStatus("opsExceptionStatus", "ok", t("ops.exception.status.list_loading_type", { type: opsExceptionTypeLabel(type) }));
        let res, data;
        if (type === "SPOTIFY_UNMATCHED" || type === "GENRE_MISSING" || type === "CATALOG_MISSING" || type === "REVIEW_MISSING" || type === "LOCAL_MISSING" || type === "RELEASE_TYPE_MISSING") {
          res = await fetchWithRetry(buildMasterExceptionUrl(type, limit, opsExceptionOffset));
          data = await safeJson(res);
        } else {
          const params = buildOpsExceptionParams(type, { includeTotal: true, limit });
          res = await fetchWithRetry(`/owned-items?${params.toString()}`);
          data = await safeJson(res);
        }
        if (!res.ok) throw new Error(data.detail || t("ops.exception.status.list_failed", { type: opsExceptionTypeLabel(type) }));
        opsExceptionItems = Array.isArray(data) ? data : [];
        opsExceptionSelectedIds = new Set(
          opsExceptionItems
            .map((row) => Number(row?.id || 0))
            .filter((id) => id > 0 && opsExceptionSelectedIds.has(id))
        );
        const headerTotal = Number(res.headers.get("X-Total-Count") || opsExceptionItems.length || 0);
        opsExceptionTotalCount = Number.isFinite(headerTotal) ? headerTotal : opsExceptionItems.length;
        // 카운트 카드를 실제 로드된 총수로 동기화
        if (opsExceptionCounts[type] !== undefined) opsExceptionCounts[type] = opsExceptionTotalCount;
        renderOpsExceptionSummary();
        renderOpsExceptionList();
        if (!silent) setStatus("opsExceptionStatus", "ok", t("ops.exception.status.list_loaded", { type: opsExceptionTypeLabel(type), count: countWithUnit(opsExceptionTotalCount) }));
      } catch (err) {
        opsExceptionItems = [];
        opsExceptionTotalCount = 0;
        renderOpsExceptionSummary();
        renderOpsExceptionList();
        if (!silent) setStatus("opsExceptionStatus", "err", err.message);
      } finally {
        opsExceptionLoading = false;
        renderOpsExceptionList();
      }
    }

    async function loadOpsAuthAccounts() {
      try {
        setStatus("opsAuthStatus", "ok", t("ops.account.status.loading"));
        const res = await fetch("/ops-auth-accounts");
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("ops.account.status.load_failed"));
        opsAuthItems = Array.isArray(data.items) ? data.items : [];
        if (opsAuthSelectedUsername && !opsAuthItems.some((row) => String(row.username || "").trim() === opsAuthSelectedUsername)) {
          resetOpsAuthForm();
        }
        renderOpsAuthTable();
        setStatus("opsAuthStatus", "ok", t("ops.account.status.loaded", { count: countWithUnit(opsAuthItems.length) }));
      } catch (err) {
        opsAuthItems = [];
        renderOpsAuthTable();
        setStatus("opsAuthStatus", "err", errorMessageText(err, t("ops.account.status.load_failed")));
      }
    }

    async function saveOpsAuthAccount() {
      const username = $("opsAuthUsername").value.trim();
      const password = $("opsAuthPassword").value;
      const role = $("opsAuthRole").value;
      const isActive = $("opsAuthIsActive").checked;
      const displayName = $("opsAuthDisplayName").value.trim() || null;
      const description = $("opsAuthDescription").value.trim() || null;
      if (!username) {
        setStatus("opsAuthStatus", "err", t("ops.account.status.username_required"));
        return;
      }
      const selectedRow = (Array.isArray(opsAuthItems) ? opsAuthItems : []).find((row) => String(row.username || "").trim() === username) || null;
      const isExisting = Boolean(selectedRow);
      const isManagedExisting = Boolean(selectedRow && selectedRow.source === "MANAGED");
      if (selectedRow && selectedRow.editable === false) {
        setStatus("opsAuthStatus", "err", t("ops.account.status.built_in_locked"));
        return;
      }
      if (!isExisting && !password.trim()) {
        setStatus("opsAuthStatus", "err", t("ops.account.status.password_required_new"));
        return;
      }
      try {
        setStatus("opsAuthStatus", "ok", isExisting ? t("ops.account.status.saving_update") : t("ops.account.status.saving_create"));
        const method = isExisting ? "PATCH" : "POST";
        const url = isExisting ? `/ops-auth-accounts/${encodeURIComponent(username)}` : "/ops-auth-accounts";
        const payload = isExisting
          ? {
              role,
              is_active: isActive,
              display_name: displayName,
              description: description,
              ...(password.trim() ? { password } : {}),
            }
          : {
              username,
              password,
              role,
              display_name: displayName,
              description: description,
            };
        const res = await fetch(url, {
          method,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("ops.account.status.save_failed"));
        if (isManagedExisting && selectedRow && selectedRow.is_active !== isActive) {
          data.is_active = isActive;
        }
        opsAuthSelectedUsername = String(data.username || username).trim();
        $("opsAuthPassword").value = "";
        await loadOpsAuthAccounts();
        setStatus("opsAuthStatus", "ok", isExisting ? t("ops.account.status.saved_update") : t("ops.account.status.saved_create"));
      } catch (err) {
        setStatus("opsAuthStatus", "err", errorMessageText(err, t("ops.account.status.save_failed")));
      }
    }

    async function deleteOpsAuthAccount() {
      const username = $("opsAuthUsername").value.trim();
      if (!username) {
        setStatus("opsAuthStatus", "err", t("ops.account.status.delete_required"));
        return;
      }
      const selectedRow = (Array.isArray(opsAuthItems) ? opsAuthItems : []).find((row) => String(row.username || "").trim() === username) || null;
      if (!selectedRow || selectedRow.source !== "MANAGED") {
        setStatus("opsAuthStatus", "err", t("ops.account.status.delete_managed_only"));
        return;
      }
      if (!confirm(t("ops.account.status.delete_confirm", { username }))) {
        setStatus("opsAuthStatus", "ok", t("ops.account.status.delete_cancelled"));
        return;
      }
      try {
        setStatus("opsAuthStatus", "ok", t("ops.account.status.deleting"));
        const res = await fetch(`/ops-auth-accounts/${encodeURIComponent(username)}`, { method: "DELETE" });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("ops.account.status.delete_failed"));
        resetOpsAuthForm();
        await loadOpsAuthAccounts();
        setStatus("opsAuthStatus", "ok", t("ops.account.status.deleted"));
      } catch (err) {
        setStatus("opsAuthStatus", "err", errorMessageText(err, t("ops.account.status.delete_failed")));
      }
    }

    async function loadPermissionData() {
      try {
        setStatus("permRoleStatus", "ok", "로딩 중...");
        const res = await fetch("/admin/permissions");
        if (!res.ok) throw new Error("권한 데이터 로드 실패");
        _permData = await safeJson(res);
        renderRoleMatrix();
        populatePermAccountSelect();
        setStatus("permRoleStatus", "ok", "");
      } catch (err) {
        setStatus("permRoleStatus", "err", errorMessageText(err, "권한 데이터 로드 실패"));
      }
    }

    async function saveRolePermissions() {
      if (!_permData) return;
      const roles = ["OPERATOR", "CAFE_STAFF"];
      setStatus("permRoleStatus", "ok", "저장 중...");
      try {
        for (const role of roles) {
          const keys = [...document.querySelectorAll(`#permRoleMatrix input[data-perm-role="${role}"]:checked`)]
            .map(el => el.dataset.permKey);
          const res = await fetch(`/admin/permissions/role/${role}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ permission_keys: keys }),
          });
          if (!res.ok) { const d = await safeJson(res); throw new Error(d.detail || "저장 실패"); }
        }
        await loadPermissionData();
        setStatus("permRoleStatus", "ok", "저장 완료");
      } catch (err) {
        setStatus("permRoleStatus", "err", errorMessageText(err, "역할 권한 저장 실패"));
      }
    }

    async function loadAccountPermissions(usernameOverride) {
      const username = usernameOverride || $("permAccountSelect").value;
      if (!username) { setStatus("permAccountStatus", "err", "계정을 선택하세요"); return; }
      setStatus("permAccountStatus", "ok", "로딩 중...");
      try {
        const [effRes, ovrRes] = await Promise.all([
          fetch(`/admin/permissions/account/${encodeURIComponent(username)}/effective`),
          fetch(`/admin/permissions/account/${encodeURIComponent(username)}`),
        ]);
        if (!effRes.ok || !ovrRes.ok) throw new Error("계정 권한 로드 실패");
        const eff = await safeJson(effRes);
        const ovr = await safeJson(ovrRes);
        _permAccountEffective = { username, effective: eff.effective || {}, role: eff.role, overrides: ovr.overrides || [] };
        renderAccountMatrix();
        setStatus("permAccountStatus", "ok", `${username} 권한 로드 완료`);
      } catch (err) {
        setStatus("permAccountStatus", "err", errorMessageText(err, "계정 권한 로드 실패"));
      }
    }

    async function grantPermOverride(username, key) {
      setStatus("permAccountStatus", "ok", "저장 중...");
      try {
        const res = await fetch(`/admin/permissions/account/${encodeURIComponent(username)}/grant/${encodeURIComponent(key)}`, { method: "PUT" });
        if (!res.ok) { const d = await safeJson(res); throw new Error(d.detail || "저장 실패"); }
        await loadAccountPermissions(username);
      } catch (err) {
        setStatus("permAccountStatus", "err", errorMessageText(err, "권한 부여 실패"));
      }
    }

    async function deletePermOverride(username, key) {
      setStatus("permAccountStatus", "ok", "처리 중...");
      try {
        const res = await fetch(`/admin/permissions/account/${encodeURIComponent(username)}/${encodeURIComponent(key)}`, { method: "DELETE" });
        if (!res.ok) { const d = await safeJson(res); throw new Error(d.detail || "삭제 실패"); }
        await loadAccountPermissions(username);
      } catch (err) {
        setStatus("permAccountStatus", "err", errorMessageText(err, "오버라이드 제거 실패"));
      }
    }

    async function clearAllPermOverrides() {
      const username = $("permAccountSelect").value || opsAuthSelectedUsername;
      if (!username) return;
      setStatus("permAccountStatus", "ok", "처리 중...");
      try {
        const res = await fetch(`/admin/permissions/account/${encodeURIComponent(username)}`, { method: "DELETE" });
        const d = await safeJson(res);
        if (!res.ok) throw new Error(d.detail || "초기화 실패");
        await loadAccountPermissions();
        setStatus("permAccountStatus", "ok", `${username} 오버라이드 전체 초기화 완료 (${d.deleted_count || 0}건)`);
      } catch (err) {
        setStatus("permAccountStatus", "err", errorMessageText(err, "초기화 실패"));
      }
    }

    async function openSourceWorkbenchFromException(ownedItemId) {
      const targetId = Number(ownedItemId || 0);
      const row = (Array.isArray(opsExceptionItems) ? opsExceptionItems : [])
        .find((item) => Number(item?.id || 0) === targetId);
      if (!row) {
        setStatus("opsExceptionStatus", "err", t("ops.exception.status.item_missing"));
        return;
      }
      loadSourceWorkbenchRowsFromItems([row], t("ops.exception.status.source_loaded", { name: resolveOwnedAlbumName(row) }));
    }

    function bulkSendExceptionsToMasterWorkbench() {
      const rows = getSelectedOpsExceptionRows();
      if (!rows.length) {
        setStatus("opsExceptionStatus", "err", t("ops.exception.status.bulk_master_required"));
        return;
      }
      const sentCount = rows.length;
      loadMasterOwnedRowsFromItems(rows, t("ops.exception.status.bulk_master_loaded", { count: countWithUnit(sentCount) }));
      setStatus("opsExceptionStatus", "ok", `${countWithUnit(sentCount)}이 마스터 정리 대상으로 이동됐습니다`);
    }

    async function alignPreferredStorageFromException(ownedItemId) {
      const targetId = Number(ownedItemId || 0);
      const row = (Array.isArray(opsExceptionItems) ? opsExceptionItems : [])
        .find((item) => Number(item?.id || 0) === targetId);
      if (!row) {
        setStatus("opsExceptionStatus", "err", t("ops.exception.status.item_missing"));
        return;
      }
      const nextPreferred = String(row?.size_group || "").trim().toUpperCase();
      if (!nextPreferred) {
        setStatus("opsExceptionStatus", "err", t("ops.exception.status.align_missing_size"));
        return;
      }
      try {
        setStatus("opsExceptionStatus", "ok", t("ops.exception.status.align_saving"));
        const res = await fetch("/owned-items/bulk-update", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            owned_item_ids: [targetId],
            preferred_storage_size_group: nextPreferred,
          }),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("ops.exception.status.align_update_failed"));
        setStatus("opsExceptionStatus", "ok", t("ops.exception.status.align_saved", { size: dashboardSizeGroupLabel(nextPreferred) }));
        refreshOpsExceptionInBackground();
        refreshHomeSearchInBackground();
        refreshHomeDashboardInBackground();
        if (Number(homeSelectedItemId || 0) === targetId) {
          refreshHomeManageContext(targetId, {
            keepMasterContext: Boolean(homeSelectedMasterId),
            masterId: homeSelectedMasterId,
            reloadMaster: Boolean(homeSelectedMasterId),
          }).catch(() => {});
        }
      } catch (err) {
        setStatus("opsExceptionStatus", "err", err.message);
      }
    }

    async function bulkAlignPreferredStorageFromExceptions() {
      const rows = getSelectedOpsExceptionRows();
      if (!rows.length) {
        setStatus("opsExceptionStatus", "err", t("ops.exception.status.bulk_align_required"));
        return;
      }
      const payloadRows = rows.filter((row) => String(row?.size_group || "").trim());
      if (!payloadRows.length) {
        setStatus("opsExceptionStatus", "err", t("ops.exception.status.bulk_align_no_size"));
        return;
      }
      try {
        setStatus("opsExceptionStatus", "ok", t("ops.exception.status.bulk_align_saving", { count: countWithUnit(payloadRows.length) }));
        let updated = 0;
        for (const row of payloadRows) {
          const res = await fetch("/owned-items/bulk-update", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              owned_item_ids: [Number(row.id)],
              preferred_storage_size_group: String(row.size_group || "").trim().toUpperCase(),
            }),
          });
          const data = await safeJson(res);
          if (!res.ok) throw new Error(data.detail || t("ops.exception.status.align_update_failed"));
          updated += Number(data.updated_count || 0);
        }
        opsExceptionSelectedIds = new Set();
        const okCount = updated;
        setStatus("opsExceptionStatus", "ok", `실물 기준 맞춤 완료 — ${countWithUnit(okCount)} 변경됨`);
        refreshOpsExceptionInBackground();
        refreshHomeSearchInBackground();
        refreshHomeDashboardInBackground();
      } catch (err) {
        setStatus("opsExceptionStatus", "err", err.message);
      }
    }

    function bulkSendExceptionsToSourceWorkbench() {
      const rows = getSelectedOpsExceptionRows();
      if (!rows.length) {
        setStatus("opsExceptionStatus", "err", t("ops.exception.status.bulk_source_required"));
        return;
      }
      const sentCount = rows.length;
      loadSourceWorkbenchRowsFromItems(rows, t("ops.exception.status.bulk_source_loaded", { count: countWithUnit(sentCount) }));
      setStatus("opsExceptionStatus", "ok", `${countWithUnit(sentCount)}이 소스 보강 대상으로 이동됐습니다`);
    }

    function resetOpsSlotForm() {
      $("opsSlotId").value = "";
      $("opsSlotCabinetName").value = "";
      $("opsSlotColumnCode").value = "";
      $("opsSlotCellCode").value = "";
      $("opsSlotSizeGroup").value = "STD";
      setStatus("opsSlotStatus", "ok", "");
    }

    function recommendedCabinetSlotCapacityMm(sizeGroup) {
      const defaults = {
        STD: 142,
        BOOK: 320,
        LP: 360,
        LP10: 300,
        LP7: 200,
        OVERSIZE: 520,
        CASSETTE: 142,
        "8TRACK": 142,
        "REEL_TO_REEL": 320,
        GOODS: 220,
      };
      return Number(defaults[String(sizeGroup || "").trim().toUpperCase()] || 0);
    }

    function renderOpsCabinetSlotCapacityHint() {
      const hint = $("opsCabinetSlotCapacityHint");
      if (!hint) return;
      const recommended = recommendedCabinetSlotCapacityMm($("opsCabinetSizeGroup").value);
      const currentValue = Number($("opsCabinetSlotCapacityMm").value || 0);
      if (currentValue > 0 && currentValue !== recommended) {
        hint.textContent = t("ops.cabinet.slot_capacity.hint.custom", { recommended: formatCount(recommended) });
        return;
      }
      hint.textContent = t("ops.cabinet.slot_capacity.hint.default", { recommended: formatCount(recommended) });
    }

    function maybeAutofillOpsCabinetSlotCapacity(force = false) {
      const currentValue = String($("opsCabinetSlotCapacityMm").value || "").trim();
      if (!force && currentValue) {
        renderOpsCabinetSlotCapacityHint();
        return;
      }
      const suggested = recommendedCabinetSlotCapacityMm($("opsCabinetSizeGroup").value);
      $("opsCabinetSlotCapacityMm").value = suggested > 0 ? String(suggested) : "";
      renderOpsCabinetSlotCapacityHint();
    }

    function resetOpsCabinetForm() {
      $("opsCabinetSelectedName").value = "";
      $("opsCabinetName").value = "";
      $("opsCabinetGroupName").value = "";
      $("opsCabinetGroupOrder").value = "";
      $("opsCabinetDomainCode").value = "";
      $("opsCabinetSizeGroup").value = "STD";
      $("opsCabinetSortPolicy").value = "ARTIST_RELEASE_TITLE";
      $("opsCabinetFloorCount").value = "6";
      $("opsCabinetCellCount").value = "6";
      $("opsCabinetSlotCapacityMm").value = "";
      maybeAutofillOpsCabinetSlotCapacity(true);
      $("opsCabinetFloorStart").value = "1";
      $("opsCabinetCellStart").value = "1";
      setOpsCabinetFormMode(null);
      setStatus("opsCabinetStatus", "ok", "");
    }

    function fillOpsSlotForm(slot) {
      if (!slot) {
        resetOpsSlotForm();
        return;
      }
      $("opsSlotId").value = String(slot.id || "");
      $("opsSlotCabinetName").value = String(slot.cabinet_name || "");
      $("opsSlotColumnCode").value = String(slot.column_code || "");
      $("opsSlotCellCode").value = String(slot.cell_code || "");
      $("opsSlotSizeGroup").value = String(slot.allowed_size_group || "STD");
    }

    function renderOpsSlotTable(rows) {
      const body = $("opsSlotTableBody");
      if (!body) return;
      const list = Array.isArray(rows) ? rows : [];
      body.innerHTML = list.length ? list.map((slot) => `
        <tr data-slot-id="${slot.id}">
          <td>${slot.id}</td>
          <td>${escapeHtml(slot.cabinet_name || "-")}</td>
          <td>${escapeHtml(slot.column_code || "-")}</td>
          <td>${escapeHtml(slot.cell_code || "-")}</td>
          <td>${escapeHtml(storageSlotDisplayLabel(slot))}</td>
          <td>${escapeHtml(dashboardSizeGroupLabel(slot.allowed_size_group))}</td>
          <td>${escapeHtml(slot.slot_code || "-")}</td>
        </tr>
      `).join("") : `<tr><td colspan='7' class='muted'>${escapeHtml(t("ops.slot.list.state.empty"))}</td></tr>`;
    }

    function renderOpsCabinetTable(rows) {
      const body = $("opsCabinetTableBody");
      if (!body) return;
      const list = summarizeStorageCabinets(rows);
      body.innerHTML = list.length ? list.map((cabinet) => `
        <tr data-cabinet-name="${encodeURIComponent(cabinet.cabinet_name)}">
          <td>${escapeHtml(cabinet.cabinet_name)}</td>
          <td>${escapeHtml(cabinet.cabinet_group_name ? `${cabinet.cabinet_group_name} · ${formatCount(cabinet.cabinet_group_order || 0)}` : "-")}</td>
          <td>${escapeHtml(dashboardDomainLabel(cabinet.cabinet_domain_code || "UNASSIGNED"))}</td>
          <td>${escapeHtml(cabinet.size_group || "-")}</td>
          <td>${cabinet.max_thickness_mm ? `${formatCount(cabinet.max_thickness_mm)}mm` : t("common.default")}</td>
          <td>${escapeHtml(cabinetSortPolicyLabel(cabinet.cabinet_sort_policy))}</td>
          <td>${formatCount(cabinet.floor_count)}</td>
          <td>${formatCount(cabinet.cell_count)}</td>
          <td>${formatCount(cabinet.slot_count)}</td>
        </tr>
      `).join("") : `<tr><td colspan='9' class='muted'>${escapeHtml(t("ops.cabinet.list.state.empty"))}</td></tr>`;
    }

    function getOpsCabinetSummary(cabinetName) {
      const target = String(cabinetName || "").trim();
      if (!target) return null;
      return summarizeStorageCabinets(storageSlotCache)
        .find((item) => String(item.cabinet_name || "").trim() === target) || null;
    }

    function setOpsCabinetFormMode(summary = null) {
      const isEditMode = Boolean(summary && summary.cabinet_name);
      $("opsCabinetSelectedName").value = isEditMode ? String(summary.cabinet_name || "") : "";
      $("opsCabinetName").disabled = isEditMode;
      $("opsCabinetSizeGroup").disabled = isEditMode;
      $("opsCabinetFloorStart").disabled = isEditMode;
      $("opsCabinetCellStart").disabled = isEditMode;
      $("opsCabinetSaveBtn").textContent = isEditMode ? t("ops.cabinet.action.update") : t("ops.cabinet.action.save");
      const hint = $("opsCabinetModeHint");
      if (!hint) return;
      if (!isEditMode) {
        hint.textContent = t("ops.cabinet.mode_hint.create");
        return;
      }
      hint.textContent = summary.can_safe_edit
        ? t("ops.cabinet.mode_hint.safe_edit")
        : t("ops.cabinet.mode_hint.unsafe_edit");
    }

    function fillOpsCabinetForm(summary) {
      if (!summary) {
        resetOpsCabinetForm();
        return;
      }
      $("opsCabinetName").value = String(summary.cabinet_name || "");
      $("opsCabinetGroupName").value = String(summary.cabinet_group_name || "");
      $("opsCabinetGroupOrder").value = String(summary.cabinet_group_order || "");
      $("opsCabinetDomainCode").value = String(summary.cabinet_domain_code || "");
      $("opsCabinetSizeGroup").value = String(summary.size_group_code || "STD");
      $("opsCabinetSortPolicy").value = String(summary.cabinet_sort_policy || "ARTIST_RELEASE_TITLE");
      $("opsCabinetFloorCount").value = String(summary.floor_count || 1);
      $("opsCabinetCellCount").value = String(summary.cell_count || 1);
      $("opsCabinetSlotCapacityMm").value = String(summary.max_thickness_mm || "");
      renderOpsCabinetSlotCapacityHint();
      $("opsCabinetFloorStart").value = String(summary.floor_start || 1);
      $("opsCabinetCellStart").value = String(summary.cell_start || 1);
      $("opsSlotCabinetName").value = String(summary.cabinet_name || "");
      setOpsCabinetFormMode(summary);
    }

    function resetOpsCameraForm() {
      opsCameraSelectedId = null;
      $("opsCameraCabinetName").value = "";
      $("opsCameraName").value = "";
      $("opsCameraDescription").value = "";
      $("opsCameraOnvifUrl").value = "";
      $("opsCameraSnapshotUrl").value = "";
      $("opsCameraStreamUrl").value = "";
      $("opsCameraUsername").value = "";
      $("opsCameraPassword").value = "";
      $("opsCameraActive").checked = true;
      const advanced = $("opsCameraAdvancedSettings");
      if (advanced) advanced.open = false;
      const summary = $("opsCameraSelectionSummary");
      if (summary) {
        summary.classList.remove("active");
        summary.innerHTML = t("ops.camera.selection.new");
      }
      setStatus("opsCameraStatus", "", "");
    }

    function fillOpsCameraForm(item) {
      if (!item || typeof item !== "object") return;
      opsCameraSelectedId = Number(item.id || 0) || null;
      $("opsCameraCabinetName").value = String(item.cabinet_name || item.camera_name || "");
      $("opsCameraName").value = String(item.camera_name || "");
      $("opsCameraDescription").value = String(item.description || "");
      $("opsCameraOnvifUrl").value = String(item.onvif_device_url || "");
      $("opsCameraSnapshotUrl").value = String(item.snapshot_url || "");
      $("opsCameraStreamUrl").value = String(item.stream_url || "");
      $("opsCameraUsername").value = "";
      $("opsCameraPassword").value = "";
      $("opsCameraActive").checked = Boolean(item.is_active);
      const advanced = $("opsCameraAdvancedSettings");
      if (advanced) {
        advanced.open = Boolean(item.onvif_device_url || item.snapshot_url || item.stream_url || item.has_credentials);
      }
      const summary = $("opsCameraSelectionSummary");
      if (summary) {
        const detailBits = [
          String(item.description || "").trim() || t("shared_camera.state.no_description"),
          Boolean(item.stream_url)
            ? t("ops.camera.table.preview.stream_priority")
            : Boolean(item.snapshot_url)
              ? t("ops.camera.table.preview.snapshot")
              : t("ops.camera.table.preview.none"),
          Boolean(item.is_active) ? t("ops.camera.table.state.active") : t("ops.camera.table.state.inactive"),
        ];
        summary.classList.add("active");
        summary.innerHTML = `<strong>${escapeHtml(String(item.camera_name || "-"))}</strong><span>${escapeHtml(detailBits.join(" · "))}</span>`;
      }
      sharedCameraSelectedId = opsCameraSelectedId;
      renderSharedCameraPage();
      setStatus("opsCameraStatus", "ok", t("ops.camera.status.selected", { camera: String(item.camera_name || "-") }));
    }

    function renderOpsCameraTable(rows) {
      const body = $("opsCameraTableBody");
      if (!body) return;
      const list = Array.isArray(rows) ? rows : [];
      body.innerHTML = list.length ? list.map((item) => `
        <tr data-camera-id="${item.id}"${Number(item.id || 0) === Number(opsCameraSelectedId || 0) ? ' class="pick"' : ""}>
          <td>${escapeHtml(item.description || "-")}</td>
          <td>${escapeHtml(item.camera_name || "-")}</td>
          <td>${item.stream_url ? t("ops.camera.table.preview.stream_priority") : item.snapshot_url ? t("ops.camera.table.preview.snapshot") : t("ops.camera.table.preview.none")}</td>
          <td>${item.is_active ? t("ops.camera.table.state.active") : t("ops.camera.table.state.inactive")}</td>
        </tr>
      `).join("") : `<tr><td colspan='4' class='muted'>${escapeHtml(t("ops.camera.list.state.empty"))}</td></tr>`;
    }

    function renderOpsCameraDiscoverTable(rows) {
      const body = $("opsCameraDiscoverTableBody");
      if (!body) return;
      const list = Array.isArray(rows) ? rows : [];
      body.innerHTML = list.length ? list.map((item, index) => `
        <tr data-discover-index="${index}">
          <td>${escapeHtml(item.camera_name || "-")}</td>
          <td>${escapeHtml(item.host || "-")}</td>
          <td><button class="btn ghost tiny" type="button" data-ops-camera-discover-use="${index}" title="${escapeHtml(item.onvif_device_url || "-")}">${escapeHtml(t("ops.camera.discover.action.fill_form"))}</button></td>
        </tr>
      `).join("") : `<tr><td colspan='3' class='muted'>${escapeHtml(t("ops.camera.discover.state.empty"))}</td></tr>`;
    }

    function applyDiscoveredCamera(item) {
      if (!item || typeof item !== "object") return;
      $("opsCameraName").value = String(item.camera_name || item.host || "");
      $("opsCameraOnvifUrl").value = String(item.onvif_device_url || "");
      const advanced = $("opsCameraAdvancedSettings");
      if (advanced) advanced.open = true;
      const scopeLines = Array.isArray(item.scopes) ? item.scopes.filter((v) => String(v || "").trim()) : [];
      if (!$("opsCameraDescription").value.trim() && scopeLines.length) {
        $("opsCameraDescription").value = scopeLines[0];
      }
      setStatus("opsCameraStatus", "ok", t("ops.camera.status.discover_applied", {
        camera: String(item.camera_name || item.host || "camera"),
        url: String(item.onvif_device_url || "-"),
      }));
    }

    function ensureSharedCameraSelection(rows) {
      const list = Array.isArray(rows) ? rows : [];
      if (!list.length) {
        sharedCameraSelectedId = null;
        return null;
      }
      const current = list.find((item) => Number(item.id || 0) === Number(sharedCameraSelectedId || 0)) || null;
      if (current) return current;
      const firstActive = list.find((item) => Boolean(item?.is_active)) || list[0];
      sharedCameraSelectedId = Number(firstActive?.id || 0) || null;
      return firstActive || null;
    }

    function renderSharedCameraList(rows) {
      const listEl = $("sharedCameraList");
      const countEl = $("sharedCameraCount");
      if (!listEl || !countEl) return;
      const list = Array.isArray(rows) ? rows : [];
      countEl.textContent = countWithUnit(list.length);
      if (!list.length) {
        listEl.innerHTML = `<div class='dashboard-camera-placeholder'>${escapeHtml(t("shared_camera.list.empty"))}</div>`;
        return;
      }
      listEl.innerHTML = list.map((item) => {
        const cameraId = Number(item?.id || 0);
        const active = cameraId > 0 && cameraId === Number(sharedCameraSelectedId || 0);
        const description = String(item?.description || "").trim() || t("shared_camera.state.no_description");
        const stateText = Boolean(item?.is_active) ? t("shared_camera.state.active") : t("shared_camera.state.inactive");
        return `
          <button class="shared-camera-list-item${active ? " active" : ""}" type="button" data-shared-camera-id="${cameraId}">
            <strong>${escapeHtml(item?.camera_name || "-")}</strong>
            <div class="mini">${escapeHtml(description)}</div>
            <div class="mini">${escapeHtml(stateText)}</div>
          </button>
        `;
      }).join("");
    }

    function renderSharedCameraPreview(rows) {
      const titleEl = $("sharedCameraTitle");
      const metaEl = $("sharedCameraMeta");
      const bodyEl = $("sharedCameraPreviewBody");
      if (!titleEl || !metaEl || !bodyEl) return;
      const selected = ensureSharedCameraSelection(rows);
      if (!selected) {
        titleEl.textContent = t("shared_camera.empty.title");
        metaEl.textContent = t("shared_camera.empty.meta");
        bodyEl.innerHTML = `<div class='dashboard-camera-placeholder'>${escapeHtml(t("shared_camera.list.empty"))}</div>`;
        return;
      }
      const title = String(selected.camera_name || "").trim() || t("shared_camera.preview.title");
      const description = String(selected.description || "").trim() || t("shared_camera.state.no_description");
      const streamUrl = String(selected.stream_url || "").trim();
      const snapshotEnabled = Boolean(selected.snapshot_url);
      const metaBits = [
        description,
        Boolean(selected.is_active) ? t("shared_camera.state.active") : t("shared_camera.state.inactive"),
        /^https?:\/\//i.test(streamUrl) ? t("shared_camera.state.stream_preview") : snapshotEnabled ? t("shared_camera.state.snapshot_preview") : streamUrl ? t("shared_camera.state.external_stream_only") : t("shared_camera.state.no_preview"),
      ];
      titleEl.textContent = title;
      metaEl.textContent = metaBits.filter((value) => String(value || "").trim()).join(" · ");
      if (!selected.is_active) {
        bodyEl.innerHTML = `<div class='dashboard-camera-placeholder'>${escapeHtml(t("shared_camera.preview.inactive_body"))}</div>`;
        return;
      }
      if (/^https?:\/\//i.test(streamUrl)) {
        bodyEl.innerHTML = `<iframe class="shared-camera-stream-frame" src="${escapeHtml(streamUrl)}" title="${escapeHtml(title)}" loading="lazy"></iframe>`;
        return;
      }
      if (snapshotEnabled) {
        bodyEl.innerHTML = `<img class="dashboard-camera-image" src="/cabinet-cameras/${encodeURIComponent(String(selected.id))}/snapshot?ts=${Date.now()}" alt="${escapeHtml(title)}" />`;
        return;
      }
      if (/^rtsps?:\/\//i.test(streamUrl)) {
        bodyEl.innerHTML = `<div class='dashboard-camera-placeholder'>${escapeHtml(t("shared_camera.preview.rtsp_only_body"))}</div>`;
        return;
      }
      bodyEl.innerHTML = `<div class='dashboard-camera-placeholder'>${escapeHtml(t("shared_camera.preview.load_failed_body"))}</div>`;
    }

    function renderSharedCameraPage() {
      renderSharedCameraList(opsCameraItems);
      renderSharedCameraPreview(opsCameraItems);
    }

    async function discoverOpsCameras() {
      try {
        setStatus("opsCameraStatus", "ok", t("ops.camera.status.discover_loading"));
        const res = await fetch("/cabinet-cameras/discover?timeout_ms=2500");
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("ops.camera.status.discover_failed")));
        opsCameraDiscoverItems = Array.isArray(data) ? data : [];
        renderOpsCameraDiscoverTable(opsCameraDiscoverItems);
        setStatus("opsCameraStatus", "ok", t("ops.camera.status.discover_loaded", { count: countWithUnit(opsCameraDiscoverItems.length) }));
      } catch (err) {
        opsCameraDiscoverItems = [];
        renderOpsCameraDiscoverTable([]);
        setStatus("opsCameraStatus", "err", errorMessageText(err, t("ops.camera.status.discover_failed")));
      }
    }

    async function testOpsCameraConnection() {
      const onvifDeviceUrl = $("opsCameraOnvifUrl").value.trim();
      if (!onvifDeviceUrl) {
        setStatus("opsCameraStatus", "err", t("ops.camera.status.onvif_url_required"));
        return;
      }
      const payload = {
        camera_id: opsCameraSelectedId ? Number(opsCameraSelectedId) : null,
        onvif_device_url: onvifDeviceUrl,
        username: $("opsCameraUsername").value.trim() || null,
        password: $("opsCameraPassword").value || null,
      };
      try {
        const advanced = $("opsCameraAdvancedSettings");
        if (advanced) advanced.open = true;
        setStatus("opsCameraStatus", "ok", t("ops.camera.status.test_loading"));
        const res = await fetch("/cabinet-cameras/test-onvif", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("ops.camera.status.test_failed")));
        if (data.snapshot_url && !$("opsCameraSnapshotUrl").value.trim()) {
          $("opsCameraSnapshotUrl").value = String(data.snapshot_url || "");
        }
        if (data.stream_url && !$("opsCameraStreamUrl").value.trim()) {
          $("opsCameraStreamUrl").value = String(data.stream_url || "");
        }
        if (!$("opsCameraName").value.trim()) {
          const inferredName = [data.manufacturer, data.model].filter((v) => String(v || "").trim()).join(" ");
          if (inferredName) $("opsCameraName").value = inferredName;
        }
        const noteParts = [
          String(data.manufacturer || "").trim(),
          String(data.model || "").trim(),
          String(data.serial_number || "").trim() ? `S/N ${String(data.serial_number || "").trim()}` : "",
        ].filter((v) => v);
        if (noteParts.length && !$("opsCameraDescription").value.trim()) {
          $("opsCameraDescription").value = noteParts.join(" | ");
        }
        const statusParts = [];
        if (data.snapshot_url) statusParts.push(t("ops.camera.status.test_fill_snapshot"));
        if (data.stream_url) statusParts.push(t("ops.camera.status.test_fill_stream"));
        if (!statusParts.length) {
          statusParts.push((data.media_service_url || data.device_service_url) ? t("ops.camera.status.test_connection_verified") : t("ops.camera.status.test_device_info_verified"));
        }
        setStatus("opsCameraStatus", "ok", t("ops.camera.status.test_success", { details: statusParts.join(" / ") }));
      } catch (err) {
        setStatus("opsCameraStatus", "err", errorMessageText(err, t("ops.camera.status.test_failed")));
      }
    }

    async function loadOpsCameras({ silent = false } = {}) {
      try {
        const res = await fetch("/cabinet-cameras");
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || "camera list load failed");
        opsCameraItems = Array.isArray(data) ? data : [];
        renderOpsCameraTable(opsCameraItems);
        renderSharedCameraPage();
        if (!silent) {
          setStatus("opsCameraStatus", "ok", t("ops.camera.status.list_loaded", { count: countWithUnit(opsCameraItems.length) }));
          setStatus("sharedCameraStatus", "ok", t("ops.camera.status.list_loaded_shared", { count: countWithUnit(opsCameraItems.length) }));
        }
      } catch (err) {
        opsCameraItems = [];
        renderOpsCameraTable([]);
        renderSharedCameraPage();
        if (!silent) {
          setStatus("opsCameraStatus", "err", errorMessageText(err, t("ops.camera.status.list_failed")));
          setStatus("sharedCameraStatus", "err", errorMessageText(err, t("ops.camera.status.list_failed")));
        }
      }
    }

    async function saveOpsCamera() {
      const cameraName = $("opsCameraName").value.trim();
      const description = $("opsCameraDescription").value.trim();
      if (!cameraName) {
        setStatus("opsCameraStatus", "err", t("ops.camera.status.name_required"));
        return;
      }
      $("opsCameraCabinetName").value = $("opsCameraCabinetName").value.trim() || cameraName;
      const payload = {
        camera_id: opsCameraSelectedId ? Number(opsCameraSelectedId) : null,
        cabinet_name: $("opsCameraCabinetName").value.trim() || null,
        camera_name: cameraName,
        description: description || null,
        onvif_device_url: $("opsCameraOnvifUrl").value.trim() || null,
        snapshot_url: $("opsCameraSnapshotUrl").value.trim() || null,
        stream_url: $("opsCameraStreamUrl").value.trim() || null,
        username: $("opsCameraUsername").value.trim() || null,
        password: $("opsCameraPassword").value || null,
        notes: null,
        is_active: $("opsCameraActive").checked,
      };
      try {
        setStatus("opsCameraStatus", "ok", t("ops.camera.status.saving"));
        const res = await fetch("/cabinet-cameras", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("ops.camera.status.save_failed")));
        await loadOpsCameras({ silent: true });
        fillOpsCameraForm(data);
        setStatus("opsCameraStatus", "ok", t("ops.camera.status.saved", { camera: String(data.camera_name || "-") }));
      } catch (err) {
        setStatus("opsCameraStatus", "err", errorMessageText(err, t("ops.camera.status.save_failed")));
      }
    }

    async function deleteOpsCamera() {
      const cameraId = opsCameraSelectedId ? Number(opsCameraSelectedId) : 0;
      if (cameraId <= 0) {
        setStatus("opsCameraStatus", "err", t("ops.camera.status.delete_select_first"));
        return;
      }
      const item = opsCameraItems.find((row) => Number(row.id) === cameraId) || null;
      const ok = window.confirm(t("ops.camera.confirm_delete", {
        camera: String(item?.camera_name || "-"),
        description: String(item?.description || "-"),
      }));
      if (!ok) return;
      try {
        setStatus("opsCameraStatus", "ok", t("ops.camera.status.deleting"));
        const res = await fetch(`/cabinet-cameras/${encodeURIComponent(String(cameraId))}`, { method: "DELETE" });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("ops.camera.status.delete_failed")));
        resetOpsCameraForm();
        await loadOpsCameras({ silent: true });
        setStatus("opsCameraStatus", "ok", t("ops.camera.status.deleted"));
      } catch (err) {
        setStatus("opsCameraStatus", "err", errorMessageText(err, t("ops.camera.status.delete_failed")));
      }
    }

    async function loadStorageSlots() {
      try {
        const res = await fetch("/storage-slots");
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("ops.slot.status.list_failed")));

        storageSlotCache = Array.isArray(data) ? data : [];
        renderOpsCabinetTable(storageSlotCache);
        renderOpsSlotTable(storageSlotCache);

        const slotSel = $("slotId");
        const quickSlotSel = $("quickSlotId");
        const editSlotSel = $("editSlotId");
        const goodsSearchSlotSel = $("goodsSearchStorageSlotId");
        const goodsManageSlotSel = $("goodsManageSlotId");
        const goodsRegisterSlotSel = $("goodsRegisterSlotId");
        slotSel.innerHTML = `<option value="">${escapeHtml(t("common.unspecified"))}</option>`;
        quickSlotSel.innerHTML = `<option value="">${escapeHtml(t("common.unspecified"))}</option>`;
        editSlotSel.innerHTML = `<option value="">${escapeHtml(t("common.unspecified"))}</option>`;
        if (goodsSearchSlotSel) goodsSearchSlotSel.innerHTML = `<option value="">${escapeHtml(t("common.all"))}</option>`;
        if (goodsManageSlotSel) goodsManageSlotSel.innerHTML = `<option value="">${escapeHtml(t("common.unspecified"))}</option>`;
        if (goodsRegisterSlotSel) goodsRegisterSlotSel.innerHTML = `<option value="">${escapeHtml(t("common.unspecified"))}</option>`;
        for (const slot of storageSlotCache) {
          const opt = document.createElement("option");
          opt.value = String(slot.id);
          opt.textContent = `${slot.id} | ${storageSlotDisplayLabel(slot)} | ${dashboardSizeGroupLabel(slot.allowed_size_group)}`;
          slotSel.appendChild(opt);
          quickSlotSel.appendChild(opt.cloneNode(true));
          editSlotSel.appendChild(opt.cloneNode(true));
          if (goodsSearchSlotSel) goodsSearchSlotSel.appendChild(opt.cloneNode(true));
          if (goodsManageSlotSel) goodsManageSlotSel.appendChild(opt.cloneNode(true));
          if (goodsRegisterSlotSel) goodsRegisterSlotSel.appendChild(opt.cloneNode(true));
        }
      } catch (err) {
        setStatus("opsCabinetStatus", "err", errorMessageText(err, t("ops.slot.status.list_failed")));
        setStatus("opsSlotStatus", "err", errorMessageText(err, t("ops.slot.status.list_failed")));
        setStatus("quickCreateStatus", "err", errorMessageText(err, t("ops.slot.status.list_failed")));
        setStatus("createStatus", "err", errorMessageText(err, t("ops.slot.status.list_failed")));
        setStatus("homeEditStatus", "err", errorMessageText(err, t("ops.slot.status.list_failed")));
        setStatus("goodsManageStatusLine", "err", errorMessageText(err, t("ops.slot.status.list_failed")));
        setStatus("goodsRegisterStatusLine", "err", errorMessageText(err, t("ops.slot.status.list_failed")));
      }
    }

    function switchGoodsMode(mode) {
      const nextMode = ["search", "manage", "register"].includes(String(mode || "").trim())
        ? String(mode || "").trim()
        : "search";
      goodsMode = nextMode;
      syncGoodsModeUi();
    }

    async function openGoodsItemForManage(goodsItemId, options = {}) {
      const targetId = Number(goodsItemId || 0);
      if (targetId <= 0) return;
      try {
        setStatus("goodsManageStatusLine", "ok", t("collectibles.manage.status.loading", { id: targetId }));
        const res = await fetch(`/goods-items/${targetId}`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("collectibles.manage.status.load_failed"));
        applyGoodsManageItem(data);
        if (options.switchMode !== false) {
          switchGoodsMode("manage");
        }
      } catch (err) {
        setStatus("goodsManageStatusLine", "err", errorMessageText(err, t("collectibles.manage.status.load_failed")));
      }
    }

    async function loadGoodsSearchResults(options = {}) {
      try {
        goodsSearchLoading = true;
        renderGoodsSearchResults();
        if (!options.silent) {
          setStatus("goodsSearchStatus", "ok", t("collectibles.status.search.loading"));
        }
        const params = new URLSearchParams();
        const queryText = $("goodsSearchQuery").value.trim();
        const category = $("goodsSearchCategory").value;
        const albumMasterId = Number($("goodsSearchAlbumMasterId").value || 0);
        const status = $("goodsSearchStatusFilter").value || "";
        const domainCode = $("goodsSearchDomainCode").value || "";
        const storageSlotId = Number($("goodsSearchStorageSlotId").value || 0);
        const linkedState = $("goodsSearchLinkedState").value || "ANY";
        const collectibleRelationState = $("goodsSearchCollectibleRelationState").value || "ANY";
        const collectibleRelationType = $("goodsSearchCollectibleRelationType").value || "";
        if (queryText) params.set("q", queryText);
        if (category) params.set("category", category);
        if (status) params.set("status", status);
        if (domainCode) params.set("domain_code", domainCode);
        if (albumMasterId > 0) params.set("album_master_id", String(albumMasterId));
        if (storageSlotId > 0) params.set("storage_slot_id", String(storageSlotId));
        if (linkedState) params.set("linked_state", linkedState);
        if (collectibleRelationState) params.set("collectible_relation_state", collectibleRelationState);
        if (collectibleRelationType) params.set("collectible_relation_type", collectibleRelationType);
        params.set("limit", "80");
        params.set("offset", "0");
        const res = await fetch(`/goods-items?${params.toString()}`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("collectibles.status.search.failed"));
        goodsSearchResults = Array.isArray(data.items) ? data.items : [];
        goodsSearchTotalCount = Number(data.total_count || goodsSearchResults.length || 0);
        renderGoodsSearchResults();
        if (!options.silent) {
          setStatus("goodsSearchStatus", "ok", t("collectibles.status.search.complete", { count: formatCount(goodsSearchTotalCount) }));
        }
      } catch (err) {
        goodsSearchResults = [];
        goodsSearchTotalCount = 0;
        renderGoodsSearchResults();
        setStatus("goodsSearchStatus", "err", errorMessageText(err, t("collectibles.status.search.failed")));
      } finally {
        goodsSearchLoading = false;
        renderGoodsSearchResults();
      }
    }

    async function searchGoodsAlbumMasterTargets() {
      const query = $("goodsManageAlbumMasterQuery").value.trim();
      if (!query) {
        setHtmlIfPresent("goodsManageAlbumMasterResults", `<div class='mini muted'>${escapeHtml(t("collectibles.mapping.query_empty"))}</div>`);
        return;
      }
      try {
        setStatus("goodsManageMappingStatus", "ok", t("collectibles.mapping.status.lookup_progress"));
        const res = await fetch(`/goods-targets?kind=album_master&q=${encodeURIComponent(query)}&limit=12`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("collectibles.mapping.status.lookup_failed")));
        renderGoodsAlbumMasterTargetResults(Array.isArray(data.items) ? data.items : []);
        setStatus("goodsManageMappingStatus", "ok", t("collectibles.mapping.status.lookup_complete"));
      } catch (err) {
        renderGoodsAlbumMasterTargetResults([]);
        setStatus("goodsManageMappingStatus", "err", errorMessageText(err, t("collectibles.mapping.status.lookup_failed")));
      }
    }

    async function searchGoodsCollectibleTargets() {
      const goodsItemId = Number(goodsSelectedItemId || $("goodsManageId").value || 0);
      const query = $("goodsManageCollectibleQuery").value.trim();
      if (goodsItemId <= 0) {
        setStatus("goodsManageRelationStatus", "err", t("collectibles.mapping.status.select_first"));
        return;
      }
      if (!query) {
        setHtmlIfPresent("goodsManageCollectibleResults", `<div class='mini muted'>${escapeHtml(t("collectibles.mapping.query_empty"))}</div>`);
        return;
      }
      try {
        setStatus("goodsManageRelationStatus", "ok", t("collectibles.mapping.status.lookup_progress"));
        const params = new URLSearchParams({
          kind: "collectible",
          q: query,
          goods_item_id: String(goodsItemId),
          limit: "12",
        });
        const res = await fetch(`/goods-targets?${params.toString()}`);
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("collectibles.mapping.status.lookup_failed")));
        renderGoodsCollectibleTargetResults(Array.isArray(data.items) ? data.items : []);
        setStatus("goodsManageRelationStatus", "ok", t("collectibles.mapping.status.lookup_complete"));
      } catch (err) {
        renderGoodsCollectibleTargetResults([]);
        setStatus("goodsManageRelationStatus", "err", errorMessageText(err, t("collectibles.mapping.status.lookup_failed")));
      }
    }

    function addUniqueGoodsMappingValue(type, rawValue, extra = {}) {
      const value = String(rawValue || "").trim();
      if (!value) return;
      if (type === "artist") {
        if (!goodsManageArtistMappings.includes(value)) goodsManageArtistMappings.push(value);
      } else if (type === "label") {
        if (!goodsManageLabelMappings.includes(value)) goodsManageLabelMappings.push(value);
      } else if (type === "album_master") {
        const albumMasterId = Number(extra.album_master_id || rawValue || 0);
        if (albumMasterId <= 0) return;
        if (!goodsManageAlbumMasterMappings.some((row) => Number(row.album_master_id || 0) === albumMasterId)) {
          goodsManageAlbumMasterMappings.push({
            album_master_id: albumMasterId,
            title: String(extra.title || value || `album_master_id=${albumMasterId}`).trim(),
            artist_or_brand: String(extra.artist_or_brand || "").trim() || null,
          });
        }
      }
      renderGoodsManageMappings();
    }

    async function saveGoodsManageItem() {
      const goodsItemId = Number(goodsSelectedItemId || $("goodsManageId").value || 0);
      if (goodsItemId <= 0) {
        setStatus("goodsManageStatusLine", "err", t("collectibles.manage.status.select_first"));
        return;
      }
      try {
        const payload = {
          category: $("goodsManageCategory").value,
          goods_name: $("goodsManageName").value.trim(),
          quantity: Math.max(1, Number($("goodsManageQuantity").value || 1)),
          description: $("goodsManageDescription").value.trim() || null,
          size_group: $("goodsManageSizeGroup").value,
          storage_slot_id: $("goodsManageSlotId").value ? Number($("goodsManageSlotId").value) : null,
          status: $("goodsManageStatus").value,
          domain_code: $("goodsManageDomainCode").value || null,
          memory_note: $("goodsManageMemoryNote").value.trim() || null,
          image_urls: splitLineList($("goodsManageImageUrls").value),
        };
        setStatus("goodsManageStatusLine", "ok", t("collectibles.manage.status.save_progress"));
        const res = await fetch(`/goods-items/${goodsItemId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("collectibles.manage.status.save_failed"));
        goodsSearchResults = goodsSearchResults.map((row) => Number(row.id || 0) === goodsItemId ? data : row);
        applyGoodsManageItem(data);
        renderGoodsSearchResults();
        setStatus("goodsManageStatusLine", "ok", t("collectibles.manage.status.save_complete", { id: goodsItemId }));
      } catch (err) {
        setStatus("goodsManageStatusLine", "err", errorMessageText(err, t("collectibles.manage.status.save_failed")));
      }
    }

    async function deleteGoodsManageItem() {
      const goodsItemId = Number(goodsSelectedItemId || $("goodsManageId").value || 0);
      if (goodsItemId <= 0) {
        setStatus("goodsManageStatusLine", "err", t("collectibles.manage.status.delete_select_first"));
        return;
      }
      const goodsName = String($("goodsManageName").value || goodsSelectedItem?.goods_name || "-").trim() || "-";
      const ok = window.confirm(t("collectibles.manage.status.delete_confirm", { name: goodsName }));
      if (!ok) return;
      try {
        setStatus("goodsManageStatusLine", "ok", t("collectibles.manage.status.delete_progress"));
        const res = await fetch(`/goods-items/${goodsItemId}`, { method: "DELETE" });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("collectibles.manage.status.delete_failed"));
        goodsSearchResults = goodsSearchResults.filter((row) => Number(row.id || 0) !== goodsItemId);
        goodsSearchTotalCount = Math.max(0, goodsSearchTotalCount - 1);
        resetGoodsManageSelection();
        switchGoodsMode("search");
        renderGoodsSearchResults();
        setStatus("goodsSearchStatus", "ok", t("collectibles.manage.status.delete_complete", { name: goodsName }));
      } catch (err) {
        setStatus("goodsManageStatusLine", "err", errorMessageText(err, t("collectibles.manage.status.delete_failed")));
      }
    }

    async function saveGoodsManageMappings() {
      const goodsItemId = Number(goodsSelectedItemId || $("goodsManageId").value || 0);
      if (goodsItemId <= 0) {
        setStatus("goodsManageMappingStatus", "err", t("collectibles.mapping.status.select_first"));
        return;
      }
      try {
        const payload = {
          album_master_ids: goodsManageAlbumMasterMappings.map((row) => Number(row.album_master_id || 0)).filter((value) => value > 0),
          artist_names: goodsManageArtistMappings.filter((row) => String(row || "").trim()),
          label_names: goodsManageLabelMappings.filter((row) => String(row || "").trim()),
        };
        setStatus("goodsManageMappingStatus", "ok", t("collectibles.mapping.status.save_progress"));
        const res = await fetch(`/goods-items/${goodsItemId}/mappings`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("collectibles.mapping.status.save_failed")));
        goodsSearchResults = goodsSearchResults.map((row) => Number(row.id || 0) === goodsItemId ? data : row);
        applyGoodsManageItem(data);
        renderGoodsSearchResults();
        setStatus("goodsManageMappingStatus", "ok", t("collectibles.mapping.status.save_complete", { id: goodsItemId }));
      } catch (err) {
        setStatus("goodsManageMappingStatus", "err", errorMessageText(err, t("collectibles.mapping.status.save_failed")));
      }
    }

    async function saveGoodsManageRelations() {
      const goodsItemId = Number(goodsSelectedItemId || $("goodsManageId").value || 0);
      if (goodsItemId <= 0) {
        setStatus("goodsManageRelationStatus", "err", t("collectibles.mapping.status.select_first"));
        return;
      }
      try {
        const payload = {
          relations: goodsManageCollectibleRelations.map((row, index) => ({
            relation_type: String(row.relation_type || "").trim().toUpperCase(),
            linked_goods_item_id: Number(row.linked_goods_item_id || 0),
            note: String(row.note || "").trim() || null,
            display_order: Number(row.display_order ?? index) || index,
          })).filter((row) => row.linked_goods_item_id > 0 && row.relation_type),
        };
        setStatus("goodsManageRelationStatus", "ok", t("collectibles.mapping.status.save_progress"));
        const res = await fetch(`/goods-items/${goodsItemId}/relations`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("collectibles.mapping.status.save_failed")));
        goodsSearchResults = goodsSearchResults.map((row) => Number(row.id || 0) === goodsItemId ? data : row);
        applyGoodsManageItem(data);
        renderGoodsSearchResults();
        setStatus("goodsManageRelationStatus", "ok", t("collectibles.mapping.status.save_complete", { id: goodsItemId }));
      } catch (err) {
        setStatus("goodsManageRelationStatus", "err", errorMessageText(err, t("collectibles.mapping.status.save_failed")));
      }
    }

    async function createGoodsRegisterItem() {
      try {
        const payload = {
          category: $("goodsRegisterCategory").value,
          goods_name: $("goodsRegisterName").value.trim(),
          quantity: Math.max(1, Number($("goodsRegisterQuantity").value || 1)),
          description: $("goodsRegisterDescription").value.trim() || null,
          size_group: $("goodsRegisterSizeGroup").value,
          storage_slot_id: $("goodsRegisterSlotId").value ? Number($("goodsRegisterSlotId").value) : null,
          status: $("goodsRegisterStatus").value,
          domain_code: $("goodsRegisterDomainCode").value || null,
          memory_note: $("goodsRegisterMemoryNote").value.trim() || null,
          image_urls: splitLineList($("goodsRegisterImageUrls").value),
          album_master_ids: $("goodsRegisterAlbumMasterId").value ? [Number($("goodsRegisterAlbumMasterId").value)] : [],
          linked_owned_item_id: $("goodsRegisterLinkedOwnedItemId")?.value?.trim()
            ? Number($("goodsRegisterLinkedOwnedItemId").value)
            : null,
          artist_names: splitCommaList($("goodsRegisterArtistNames").value),
          label_names: splitCommaList($("goodsRegisterLabelNames").value),
        };
        setStatus("goodsRegisterStatusLine", "ok", t("collectibles.register.status.save_progress"));
        const res = await fetch("/goods-items", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("collectibles.register.status.save_failed"));
        resetGoodsRegisterForm({ preserveStatus: true });
        setStatus("goodsRegisterStatusLine", "ok", t("collectibles.register.status.save_complete", { id: data.id }));
        goodsSearchResults = [data, ...goodsSearchResults.filter((row) => Number(row.id || 0) !== Number(data.id || 0))];
        goodsSearchTotalCount += 1;
        renderGoodsSearchResults();
        switchGoodsMode("manage");
        applyGoodsManageItem(data);
      } catch (err) {
        setStatus("goodsRegisterStatusLine", "err", errorMessageText(err, t("collectibles.register.status.save_failed")));
      }
    }

    function openGoodsRegisterFromManageContext() {
      const { masterId, artist } = resolveHomeLinkedGoodsMasterContext();
      openAdminConsole("collectibles");
      switchGoodsMode("register");
      resetGoodsRegisterForm({ preserveStatus: true });
      if (masterId > 0) {
        $("goodsRegisterAlbumMasterId").value = String(masterId);
      }
      if (artist) {
        $("goodsRegisterArtistNames").value = artist;
      }
      setStatus(
        "goodsRegisterStatusLine",
        "ok",
        masterId > 0
          ? t("collectibles.register.status.start_linked", { id: masterId })
          : t("collectibles.register.status.start_independent")
      );
    }

    async function saveOpsStorageCabinet() {
      const cabinetName = $("opsCabinetName").value.trim();
      const selectedCabinetName = $("opsCabinetSelectedName").value.trim();
      const currentSummary = selectedCabinetName ? getOpsCabinetSummary(selectedCabinetName) : null;
      if (!cabinetName) {
        setStatus("opsCabinetStatus", "err", t("ops.cabinet.status.name_required"));
        return;
      }

      const payload = {
        cabinet_name: cabinetName,
        cabinet_domain_code: $("opsCabinetDomainCode").value || null,
        cabinet_group_name: $("opsCabinetGroupName").value.trim() || null,
        cabinet_group_order: Number($("opsCabinetGroupOrder").value || 0) || null,
        floor_count: Number($("opsCabinetFloorCount").value || 0),
        cell_count: Number($("opsCabinetCellCount").value || 0),
        floor_start: Number($("opsCabinetFloorStart").value || 0),
        cell_start: Number($("opsCabinetCellStart").value || 0),
        allowed_size_group: $("opsCabinetSizeGroup").value,
        cabinet_sort_policy: $("opsCabinetSortPolicy").value,
        max_thickness_mm: Number($("opsCabinetSlotCapacityMm").value || 0),
      };
      if (payload.floor_count <= 0 || payload.cell_count <= 0) {
        setStatus("opsCabinetStatus", "err", t("ops.cabinet.status.count_invalid"));
        return;
      }
      if (payload.floor_start <= 0 || payload.cell_start <= 0) {
        setStatus("opsCabinetStatus", "err", t("ops.cabinet.status.start_invalid"));
        return;
      }
      if (payload.max_thickness_mm < 0) {
        setStatus("opsCabinetStatus", "err", t("ops.cabinet.status.slot_capacity_invalid"));
        return;
      }
      if (currentSummary && !currentSummary.can_safe_edit) {
        setStatus("opsCabinetStatus", "err", t("ops.cabinet.status.unsafe_structure"));
        return;
      }
      if (currentSummary && cabinetName !== selectedCabinetName) {
        setStatus("opsCabinetStatus", "err", t("ops.cabinet.status.safe_edit_name_locked"));
        return;
      }
      if (currentSummary) {
        if (payload.floor_start !== currentSummary.floor_start || payload.cell_start !== currentSummary.cell_start) {
          setStatus("opsCabinetStatus", "err", t("ops.cabinet.status.safe_edit_start_locked"));
          return;
        }
        if (payload.floor_count < currentSummary.floor_count || payload.cell_count < currentSummary.cell_count) {
          setStatus("opsCabinetStatus", "err", t("ops.cabinet.status.safe_edit_count_locked"));
          return;
        }
        if (payload.allowed_size_group !== currentSummary.size_group_code) {
          setStatus("opsCabinetStatus", "err", t("ops.cabinet.status.safe_edit_size_locked"));
          return;
        }
      }

      try {
        setStatus("opsCabinetStatus", "ok", currentSummary ? t("ops.cabinet.status.saving_update") : t("ops.cabinet.status.saving_create"));
        const res = await fetch("/storage-cabinets/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || (currentSummary ? t("ops.cabinet.status.save_failed_update") : t("ops.cabinet.status.save_failed_create")));
        setStatus(
          "opsCabinetStatus",
          "ok",
          currentSummary
            ? t("ops.cabinet.status.save_done_update", {
                cabinet: String(data.cabinet_name || "-"),
                created: formatCount(data.created_count),
                updated: formatCount(data.updated_count),
                total: formatCount(data.total_slot_count),
              })
            : t("ops.cabinet.status.save_done_create", {
                cabinet: String(data.cabinet_name || "-"),
                created: formatCount(data.created_count),
                updated: formatCount(data.updated_count),
                total: formatCount(data.total_slot_count),
              })
        );
        $("opsSlotCabinetName").value = String(data.cabinet_name || "");
        $("opsSlotSizeGroup").value = $("opsCabinetSizeGroup").value;
        await loadStorageSlots();
        if (currentSummary) {
          const refreshedSummary = getOpsCabinetSummary(cabinetName);
          fillOpsCabinetForm(refreshedSummary || currentSummary);
        }
        await loadHomeDashboard();
      } catch (err) {
        setStatus("opsCabinetStatus", "err", err.message);
      }
    }

    async function deleteOpsStorageCabinet() {
      const cabinetName = $("opsCabinetName").value.trim();
      if (!cabinetName) {
        setStatus("opsCabinetStatus", "err", t("ops.cabinet.status.delete_select_first"));
        return;
      }
      const summary = summarizeStorageCabinets(storageSlotCache)
        .find((row) => String(row.cabinet_name || "") === cabinetName);
      const slotCount = Number(summary?.slot_count || 0);
      const ok = window.confirm(t("ops.cabinet.confirm_delete", { cabinet: cabinetName, slot_count: slotCount }));
      if (!ok) {
        setStatus("opsCabinetStatus", "ok", t("ops.cabinet.status.delete_cancelled"));
        return;
      }

      try {
        setStatus("opsCabinetStatus", "ok", t("ops.cabinet.status.deleting"));
        const params = new URLSearchParams({ cabinet_name: cabinetName });
        const res = await fetch(`/storage-cabinets?${params.toString()}`, { method: "DELETE" });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("ops.cabinet.status.delete_failed"));
        setStatus(
          "opsCabinetStatus",
          "ok",
          t("ops.cabinet.status.delete_done", {
            cabinet: data.cabinet_name,
            slot_count: formatCount(data.deleted_slot_count),
            item_count: formatCount(data.unassigned_item_count),
          })
        );
        resetOpsCabinetForm();
        resetOpsSlotForm();
        await loadStorageSlots();
        await loadHomeDashboard();
      } catch (err) {
        setStatus("opsCabinetStatus", "err", err.message);
      }
    }

    async function saveOpsStorageSlot() {
      const cabinetName = $("opsSlotCabinetName").value.trim();
      if (!cabinetName) {
        setStatus("opsSlotStatus", "err", t("ops.slot.status.cabinet_required"));
        return;
      }
      const currentSlotId = $("opsSlotId").value ? Number($("opsSlotId").value) : null;
      const currentSlot = currentSlotId
        ? storageSlotCache.find((item) => Number(item.id) === currentSlotId)
        : null;
      const cabinetSummary = summarizeStorageCabinets(storageSlotCache)
        .find((item) => String(item.cabinet_name || "").trim() === cabinetName);
      const payload = {
        slot_id: currentSlotId,
        cabinet_name: cabinetName,
        column_code: $("opsSlotColumnCode").value.trim() || null,
        cell_code: $("opsSlotCellCode").value.trim() || null,
        allowed_size_group: $("opsSlotSizeGroup").value,
        cabinet_sort_policy: String(
          currentSlot?.cabinet_sort_policy ||
          cabinetSummary?.cabinet_sort_policy ||
          $("opsCabinetSortPolicy")?.value ||
          "ARTIST_RELEASE_TITLE"
        ),
        is_overflow_zone: false,
      };
      try {
        setStatus("opsSlotStatus", "ok", t("ops.slot.status.saving"));
        const res = await fetch("/storage-slots", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(responseDetailText(data, t("ops.slot.status.save_failed")));
        setStatus("opsSlotStatus", "ok", t("ops.slot.status.saved", {
          slot: storageSlotDisplayLabel(data),
          slot_code: data.slot_code,
        }));
        await loadStorageSlots();
        await loadHomeDashboard();
        fillOpsSlotForm(data);
      } catch (err) {
        setStatus("opsSlotStatus", "err", errorMessageText(err, t("ops.slot.status.save_failed")));
      }
    }

    async function barcodeSearch() {
      const barcode = $("barcodeInput").value.trim();
      const selectedSource = String($("metaSourceFilter").value || "AUTO").trim().toUpperCase() || "AUTO";
      const requestSources = buildRegisterLookupSourceCandidates(selectedSource);
      const loadingStatusText = t("media.register.api_lookup.status.lookup_loading");
      if (!barcode) {
        renderRegisterLookupProviderStatusBadges([]);
        setStatus("barcodeStatus", "err", t("media.register.api_lookup.status.enter_barcode"));
        return;
      }
      const barcodeToken = normalizeBarcodeLookupToken(barcode);
      if (!barcodeToken) {
        renderRegisterLookupProviderStatusBadges([]);
        setStatus("barcodeStatus", "err", t("media.register.api_lookup.status.invalid_barcode"));
        return;
      }
      if (adminBarcodeConfirmToken && barcodeToken !== adminBarcodeConfirmToken) {
        clearAdminBarcodeConfirmation({ keepInput: true });
      }
      const now = Date.now();
      if (barcodeSearchInFlight) {
        barcodeSearchPendingToken = barcodeToken;
        barcodeSearchPendingValue = barcode;
        setStatus("barcodeStatus", "ok", t("media.register.api_lookup.status.lookup_inflight"));
        return;
      }
      if (barcodeSearchLastToken === barcodeToken && now - barcodeSearchLastTriggeredAt < BARCODE_SCAN_COOLDOWN_MS) {
        setStatus("barcodeStatus", "ok", t("media.register.api_lookup.status.lookup_duplicate_skipped"));
        return;
      }
      barcodeSearchInFlight = true;
      barcodeSearchLastToken = barcodeToken;
      barcodeSearchLastTriggeredAt = now;
      renderRegisterLookupProviderStatusBadges([]);
      setStatus("barcodeStatus", "ok", loadingStatusText);

      const payload = {
        barcode,
        category: $("category").value,
        limit: Math.max(1, Math.min(20, Number($("barcodeLimit").value || 5))
      )};

      try {
        let candidates = [];
        let usedSource = requestSources[0];
        let lastError = null;
        const providerStatusEntries = [];
        let fallbackMode = false;
        for (const source of requestSources) {
          const res = await fetchWithRetry("/ingest/barcode", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              ...payload,
              source,
            })
          }, {
            retries: 2,
            retryDelayMs: 250,
            onRetry: (attempt, total) => setStatus("barcodeStatus", "ok", retryingStatusText(loadingStatusText, attempt, total)),
          });
          const data = await safeJson(res);
          if (!res.ok) {
            if (res.status === 502 && selectedSource !== "AUTO") {
              providerStatusEntries.push({ kind: "unavailable", source });
              fallbackMode = true;
              lastError = new Error(responseDetailText(data, t("media.register.api_lookup.status.lookup_failed")));
              continue;
            }
            throw new Error(responseDetailText(data, t("media.register.api_lookup.status.lookup_failed")));
          }
          const nextCandidates = Array.isArray(data.candidates) ? data.candidates : [];
          usedSource = source;
          if (selectedSource !== "AUTO" && !fallbackMode && source === selectedSource) {
            candidates = nextCandidates;
            break;
          }
          if (nextCandidates.length) {
            candidates = nextCandidates;
            break;
          }
        }
        if (fallbackMode && candidates.length && usedSource !== selectedSource) {
          providerStatusEntries.push({ kind: "fallback_results", source: usedSource });
        }
        renderRegisterLookupProviderStatusBadges(providerStatusEntries);
        if (!candidates.length && lastError && providerStatusEntries.some((entry) => entry.kind === "unavailable")) throw lastError;

        renderBarcodeResults(candidates || []);
        if (Array.isArray(candidates) && candidates.length) {
          selectRegisterLookupCandidate(0, { focus: true, preventScroll: true, scroll: false });
          armAdminBarcodeConfirmation(barcodeToken, candidates[0]);
        } else {
          selectedCandidate = null;
          clearAdminBarcodeConfirmation({ keepInput: true });
        }
        setStatus(
          "barcodeStatus",
          "ok",
          Array.isArray(candidates) && candidates.length
            ? t("media.register.api_lookup.status.candidates_ready", { count: countWithUnit((candidates || []).length) })
            : t("media.register.api_lookup.status.no_candidates_register_direct")
        );
      } catch (err) {
        selectedCandidate = null;
        clearAdminBarcodeConfirmation({ keepInput: true });
        renderBarcodeResults([]);
        setStatus("barcodeStatus", "err", errorMessageText(err, t("media.register.api_lookup.status.lookup_failed")));
      } finally {
        barcodeSearchInFlight = false;
        const pendingToken = String(barcodeSearchPendingToken || "").trim();
        const pendingValue = String(barcodeSearchPendingValue || "").trim();
        barcodeSearchPendingToken = "";
        barcodeSearchPendingValue = "";
        if (pendingToken && pendingToken !== barcodeToken) {
          const input = $("barcodeInput");
          if (input) input.value = pendingValue;
          await barcodeSearch();
        }
      }
    }

    async function detectRegisterLookupCategoryMismatch(payload, source) {
      if (String(source || "").trim().toUpperCase() !== "MANIADB") return { categories: [], candidates: [] };
      const currentCategory = String(payload?.category || "").trim().toUpperCase();
      if (!MUSIC_CATEGORIES.has(currentCategory)) return { categories: [], candidates: [] };
      const res = await fetchWithRetry("/ingest/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...payload,
          category: null,
          source: "MANIADB",
        })
      }, {
        retries: 1,
        retryDelayMs: 200,
      });
      const data = await safeJson(res);
      if (!res.ok) return { categories: [], candidates: [] };
      const candidates = Array.isArray(data.candidates) ? data.candidates : [];
      const mismatchCandidates = candidates.filter((candidate) => {
        const inferredCategory = String(inferMusicCategoryFromMetadata(candidate) || "").trim().toUpperCase();
        return inferredCategory && inferredCategory !== currentCategory;
      });
      return {
        categories: Array.from(new Set(
          mismatchCandidates
            .map((candidate) => inferMusicCategoryFromMetadata(candidate))
            .filter((category) => MUSIC_CATEGORIES.has(String(category || "").trim().toUpperCase()))
            .map((category) => String(category || "").trim().toUpperCase())
        )),
        candidates: mismatchCandidates,
      };
    }

    async function querySearch() {
      const selectedSource = String($("metaSourceFilter").value || "AUTO").trim().toUpperCase() || "AUTO";
      const requestSources = buildRegisterLookupSourceCandidates(selectedSource);
      const payload = {
        category: $("category").value,
        query: $("querySourceRef").value.trim() || null,
        artist_or_brand: $("queryArtist").value.trim() || null,
        title: $("queryTitle").value.trim() || null,
        catalog_no: $("queryCatalog").value.trim() || null,
        limit: Math.max(1, Math.min(20, Number($("barcodeLimit").value || 5)))
      };
      const requestedCategory = payload.category;

      const hasAny = payload.query || payload.artist_or_brand || payload.title || payload.catalog_no;
      if (!hasAny) {
        renderRegisterLookupProviderStatusBadges([]);
        setStatus("barcodeStatus", "err", t("media.register.api_lookup.status.query_requires_term"));
        return;
      }
      clearAdminBarcodeConfirmation({ keepInput: true });

      $("barcodeCount").textContent = t("media.register.api_lookup.results.loading");
      $("barcodeResults").innerHTML = `<div class='muted'>${escapeHtml(t("media.register.api_lookup.results.loading"))}</div>`;
      const loadingStatusText = t("media.register.api_lookup.status.query_loading", { source: requestSources[0] });
      renderRegisterLookupProviderStatusBadges([]);
      setStatus("barcodeStatus", "ok", loadingStatusText);
      try {
        let items = [];
        let usedSource = requestSources[0];
        let lastError = null;
        const providerStatusEntries = [];
        let fallbackMode = false;
        for (const source of requestSources) {
          const res = await fetchWithRetry("/ingest/search", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              ...payload,
              source,
            })
          }, {
            retries: 2,
            retryDelayMs: 250,
            onRetry: (attempt, total) => setStatus("barcodeStatus", "ok", retryingStatusText(loadingStatusText, attempt, total)),
          });
          const data = await safeJson(res);
          if (!res.ok) {
            if (res.status === 502 && selectedSource !== "AUTO") {
              providerStatusEntries.push({ kind: "unavailable", source });
              fallbackMode = true;
              lastError = new Error(responseDetailText(data, t("media.register.api_lookup.status.lookup_failed")));
              continue;
            }
            throw new Error(responseDetailText(data, t("media.register.api_lookup.status.lookup_failed")));
          }
          const nextItems = Array.isArray(data.candidates) ? data.candidates : [];
          usedSource = source;
          if (selectedSource !== "AUTO" && !fallbackMode && source === selectedSource) {
            items = nextItems;
            break;
          }
          if (nextItems.length) {
            items = nextItems;
            break;
          }
        }
        if (fallbackMode && items.length && usedSource !== selectedSource) {
          providerStatusEntries.push({ kind: "fallback_results", source: usedSource });
        }
        renderRegisterLookupProviderStatusBadges(providerStatusEntries);
        if (!items.length && lastError && providerStatusEntries.some((entry) => entry.kind === "unavailable")) throw lastError;
        if (!items.length && selectedSource === "MANIADB") {
          const mismatchInfo = await detectRegisterLookupCategoryMismatch(payload, selectedSource);
          if (mismatchInfo.categories.length === 1 && mismatchInfo.candidates.length) {
            $("category").value = mismatchInfo.categories[0];
            payload.category = mismatchInfo.categories[0];
            items = mismatchInfo.candidates;
            renderBarcodeResults(items || []);
            setStatus("barcodeStatus", "ok", t("media.register.api_lookup.status.category_mismatch_autofix", {
              category: requestedCategory || "-",
              detected: mismatchInfo.categories.join(", "),
            }));
            return;
          }
          if (mismatchInfo.categories.length) {
            renderBarcodeResults([]);
            setStatus("barcodeStatus", "err", t("media.register.api_lookup.status.category_mismatch_hint", {
              category: payload.category || "-",
              detected: mismatchInfo.categories.join(", "),
            }));
            return;
          }
        }
        renderBarcodeResults(items || []);
        if (Array.isArray(items) && items.length) {
          selectRegisterLookupCandidate(0, { focus: true, preventScroll: true, scroll: false });
        } else {
          selectedCandidate = null;
        }
        const adjustedSourceText = usedSource !== selectedSource ? t("media.register.api_lookup.status.adjusted_source", { source: usedSource }) : "";
        setStatus("barcodeStatus", "ok", t("media.register.api_lookup.status.query_done", {
          count: countWithUnit((items || []).length),
          adjusted_source: adjustedSourceText,
        }));
      } catch (err) {
        renderBarcodeResults([]);
        setStatus("barcodeStatus", "err", errorMessageText(err, t("media.register.api_lookup.status.lookup_failed")));
      }
    }

    async function submitAdminRegisterLookupSearch() {
      const barcode = $("barcodeInput").value.trim();
      const hasQueryInput = [
        $("queryArtist").value.trim(),
        $("queryTitle").value.trim(),
        $("queryCatalog").value.trim(),
        $("querySourceRef").value.trim(),
      ].some(Boolean);
      if (barcode) {
        await barcodeSearch();
        return;
      }
      if (hasQueryInput) {
        await querySearch();
        return;
      }
      renderRegisterLookupProviderStatusBadges([]);
      setStatus("barcodeStatus", "err", t("media.register.api_lookup.status.lookup_requires_input"));
    }

    function buildOwnedPayload() {
      const category = $("category").value;
      const isSecondHand = $("isSecondHand").checked;
      const status = $("status").value;
      const displayRankRaw = $("displayRank").value.trim();
      const purchasePrice = normalizePurchasePriceOrNull($("purchasePrice").value);
      const mappedDomain = pickMappedDomain(selectedCandidate?.domain_code);
      const mappedReleaseType = pickMappedReleaseType(selectedCandidate?.release_type);
      const isMusic = isMusicCategory();
      const itemNameInput = isMusic
        ? $("itemNameOverride").value.trim()
        : $("goodsItemName").value.trim();

      const payload = {
        category,
        size_group: $("sizeGroup").value,
        preferred_storage_size_group: $("sizeGroup").value,
        auto_location_recommendation: !selectedCandidate,
        quantity: Number($("quantity").value || 1),
        is_second_hand: isSecondHand,
        status,
        signature_type: $("signatureType").value,
        source_code: selectedCandidate?.source || null,
        source_external_id: selectedCandidate?.external_id || null,
        domain_code: $("domainCode").value || mappedDomain || null,
        release_type: $("releaseType").value || mappedReleaseType || null,
        linked_album_master_id: $("linkedAlbumMasterId").value.trim()
          ? Number($("linkedAlbumMasterId").value)
          : null,
        linked_artist_name: $("linkedArtistName").value.trim() || null,
        purchase_price: purchasePrice,
        currency_code: purchasePrice !== null ? normalizeCurrencyCodeOrNull($("currencyCode").value, "KRW") : null,
        purchase_source: $("purchaseSource").value.trim() || null,
        condition_grade: $("conditionGrade").value.trim() || null,
        memory_note: $("memoryNote").value.trim() || null,
        item_name_override: itemNameInput || null,
        display_rank: displayRankRaw ? Number(displayRankRaw) : null,
        storage_slot_id: $("slotId").value ? Number($("slotId").value) : null
      };

      if (isMusic) {
        const candidateCollector = buildCollectorPayload(selectedCandidate?.source || null, selectedCandidate || {});
        const runoutInput = splitRunoutList($("runoutMatrix").value);
        const pressingInput = $("pressingCountry").value.trim();
        const cover = normalizeConditionGradeValue($("coverCondition").value);
        const disc = normalizeConditionGradeValue($("discCondition").value);
        const trackList = $("trackList").value
          .split("\n")
          .map((v) => v.trim())
          .filter((v) => v);

        payload.music_detail = {
          format_name: $("formatName").value,
          is_promotional_not_for_sale: $("promoNfs").checked,
          artist_or_brand: selectedCandidate?.artist_or_brand || null,
          released_date: $("releasedDate").value.trim() || selectedCandidate?.released_date || null,
          barcode: selectedCandidate?.barcode || null,
          label_name: $("labelName").value.trim() || null,
          catalog_no: $("catalogNo").value.trim() || null,
          media_type: $("mediaType").value.trim() || selectedCandidate?.media_type || null,
          genres: splitCommaList($("genres").value || selectedCandidate?.genres || []),
          styles: splitCommaList($("styles").value || selectedCandidate?.styles || []),
          cover_image_url: $("coverImageUrl").value.trim() || null,
          track_list: trackList,
          cover_condition: cover || null,
          disc_condition: disc || null,
          disc_count: $("discCount").value.trim() ? normalizePositiveIntOrNull($("discCount").value) : normalizePositiveIntOrNull(selectedCandidate?.disc_count),
          speed_rpm: $("speedRpm").value.trim() ? Number($("speedRpm").value) : (Number.isFinite(Number(selectedCandidate?.speed_rpm)) ? Number(selectedCandidate.speed_rpm) : null),
          has_obi: $("hasObi").checked ? true : null,
          runout_matrix: runoutInput.length ? runoutInput : candidateCollector.runout_matrix,
          pressing_country: pressingInput || candidateCollector.pressing_country || null,
          source_notes: candidateCollector.source_notes,
          credits: candidateCollector.credits,
          identifier_items: candidateCollector.identifier_items,
          image_items: candidateCollector.image_items,
          company_items: candidateCollector.company_items,
          series: candidateCollector.series,
          format_items: candidateCollector.format_items,
          track_items: candidateCollector.track_items,
          label_items: candidateCollector.label_items
        };
      } else {
        const goodsImageUrls = splitLineList($("goodsImageUrls").value);
        payload.goods_detail = {
          image_urls: goodsImageUrls,
          primary_image_url: goodsImageUrls.length ? goodsImageUrls[0] : null,
          poster_storage_spec: $("posterStorageSpec").value.trim() || null,
          tshirt_size: $("tshirtSize").value.trim() || null,
          cup_material: $("cupMaterial").value.trim() || null,
          hat_size: $("hatSize").value.trim() || null
        };
      }

      if (selectedCandidate && selectedCandidate.external_id && !payload.memory_note) {
        payload.memory_note = `[AUTO] ${selectedCandidate.source}#${selectedCandidate.external_id}`;
      }

      return payload;
    }

    async function createOwnedItem() {
      try {
        const payload = buildOwnedPayload();
        const createdTitle = String(payload.item_name_override || $("goodsItemName").value || "").trim() || t("common.new_item");
        if (!confirmSlotMismatchById(payload.storage_slot_id, [{
          label_id: t("common.new"),
          item_name_override: createdTitle,
          size_group: payload.size_group,
          preferred_storage_size_group: payload.preferred_storage_size_group,
        }], t("media.register.direct.action.save"))) {
          setStatus("createStatus", "ok", t("media.register.direct.status.cancelled"));
          return;
        }
        // ── 도메인 불일치 검증 ──────────────────────────────────────────────
        if (isMusicCategory()) {
          const _domainVal   = String(payload.domain_code || "").trim().toUpperCase();
          const _artistCheck = String(
            payload.music_detail?.artist_or_brand ||
            payload.linked_artist_name ||
            payload.item_name_override || ""
          ).trim();
          const _hasHangul = /[가-힣ㄱ-ㆎ]/.test(_artistCheck);
          const _hasKana   = /[぀-ヿ一-鿿]/.test(_artistCheck);
          // ManiaDB 후보는 항상 가요 — 영문 표기 한국 아티스트가 많으므로 도메인 검증 면제
          const _candidateSource = String(selectedCandidate?.source || "").trim().toUpperCase();
          const _isManiadb = _candidateSource === "MANIADB";
          if (!_isManiadb && _artistCheck && !_hasHangul && !_hasKana) {
            if (_domainVal === "KOREA") {
              setStatus("createStatus", "err",
                `⚠ 도메인 불일치: 아티스트 "${_artistCheck}"는 영문인데 도메인이 '가요'입니다. ` +
                `팝(WESTERN)으로 바꾸거나, 맞다면 다시 저장 버튼을 누르세요.`
              );
              $("domainCode").focus();
              return;
            }
            if (_domainVal === "JAPAN") {
              setStatus("createStatus", "err",
                `⚠ 도메인 불일치: 아티스트 "${_artistCheck}"는 영문인데 도메인이 '제이팝'입니다. ` +
                `팝(WESTERN)으로 바꾸거나, 맞다면 다시 저장 버튼을 누르세요.`
              );
              $("domainCode").focus();
              return;
            }
          }
          if (_artistCheck && _hasHangul && _domainVal === "WESTERN") {
            setStatus("createStatus", "err",
              `⚠ 도메인 불일치: 아티스트 "${_artistCheck}"는 한글인데 도메인이 '팝'입니다. ` +
              `가요(KOREA)로 바꾸거나, 맞다면 다시 저장 버튼을 누르세요.`
            );
            $("domainCode").focus();
            return;
          }
        }
        // ────────────────────────────────────────────────────────────────────
        setStatus("createStatus", "ok", t("media.register.direct.status.saving"));

        const res = await fetch("/owned-items", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || t("media.register.direct.status.failed"));

        const notices = Array.isArray(data.notices) ? data.notices : [];
        const mergeNotices = await maybeMergeDuplicateMastersForCreatedItem(
          Number(data.linked_album_master_id || 0),
          "createStatus"
        );
        for (const msg of mergeNotices) {
          notices.push(msg);
        }
        setStatus("createStatus", "ok", t("media.register.direct.status.done", {
          owned_id: data.owned_item_id,
          label_id: data.label_id,
          details: notices.length ? `\n${notices.map((v) => `- ${v}`).join("\n")}` : "",
        }));
        $("orderMoveItemId").value = String(data.owned_item_id);
        await loadOwnedItems();
        await loadHomeDashboard();
      } catch (err) {
        setStatus("createStatus", "err", err.message);
      }
    }
