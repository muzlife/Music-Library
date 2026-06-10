
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
