/** Страница /history */
(function (global) {
  "use strict";

  const LLM_THRESHOLD = 0.5;
  const auditHistoryBody = document.getElementById("auditHistoryBody");
  const auditHistoryTable = document.getElementById("auditHistoryTable");
  const auditHistoryEmpty = document.getElementById("auditHistoryEmpty");
  const auditHistoryErr = document.getElementById("auditHistoryErr");
  const historyCount = document.getElementById("historyCount");

  function formatCheckedAt(iso) {
    try {
      return new Date(iso).toLocaleString("ru-RU");
    } catch (_e) {
      return iso;
    }
  }

  function formatPplCell(p) {
    if (typeof p !== "number" || Number.isNaN(p)) {
      return '<span class="num">—</span>';
    }
    const cls = p >= LLM_THRESHOLD ? "ppl-high" : "ppl-low";
    return '<span class="num ' + cls + '">' + p.toFixed(4) + "</span>";
  }

  async function loadAuditHistory() {
    if (!global.LlmAuditAuth.isLoggedIn()) {
      window.location.href = "/login";
      return;
    }

    if (auditHistoryErr) {
      auditHistoryErr.hidden = true;
      auditHistoryErr.textContent = "";
    }

    try {
      const res = await fetch("/api/audit-history?limit=100", {
        headers: global.LlmAuditAuth.authHeaders(),
      });
      const data = await global.LlmAuditApi.parseJsonOrEmpty(res);
      if (!res.ok) {
        if (auditHistoryErr) {
          auditHistoryErr.textContent = data.detail || "Не удалось загрузить историю.";
          auditHistoryErr.hidden = false;
        }
        return;
      }

      const items = data.items || [];
      if (historyCount) {
        historyCount.textContent = "Показано записей: " + items.length;
      }
      auditHistoryBody.innerHTML = "";

      if (!items.length) {
        if (auditHistoryEmpty) auditHistoryEmpty.hidden = false;
        if (auditHistoryTable) auditHistoryTable.hidden = true;
        return;
      }

      if (auditHistoryEmpty) auditHistoryEmpty.hidden = true;
      if (auditHistoryTable) auditHistoryTable.hidden = false;

      for (const row of items) {
        const tr = document.createElement("tr");
        tr.innerHTML =
          '<td class="num">' +
          global.LlmAuditApi.escapeHtml(formatCheckedAt(row.checked_at)) +
          "</td><td>" +
          global.LlmAuditApi.escapeHtml(row.filename || "—") +
          "</td><td>" +
          formatPplCell(row.llm_probability) +
          "</td><td>" +
          (row.has_report
            ? '<a href="/report/' + encodeURIComponent(row.id) + '">Открыть</a>'
            : "—") +
          "</td>";
        auditHistoryBody.appendChild(tr);
      }
    } catch (_e) {
      if (auditHistoryErr) {
        auditHistoryErr.textContent = "Ошибка запроса к API.";
        auditHistoryErr.hidden = false;
      }
    }
  }

  loadAuditHistory();
})(window);
