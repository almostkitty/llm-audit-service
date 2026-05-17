/** Общие утилиты для fetch и разметки. */
(function (global) {
  "use strict";

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async function parseJsonOrEmpty(res) {
    return res.json().catch(function () {
      return {};
    });
  }

  async function readErrorDetail(res, fallback) {
    try {
      const j = await res.json();
      if (typeof j.detail === "string") return j.detail;
      if (Array.isArray(j.detail)) {
        return j.detail
          .map(function (d) {
            return typeof d === "object" && d && d.msg ? d.msg : String(d);
          })
          .join("; ");
      }
      return JSON.stringify(j.detail);
    } catch (_e) {
      return fallback;
    }
  }

  global.LlmAuditApi = {
    escapeHtml: escapeHtml,
    parseJsonOrEmpty: parseJsonOrEmpty,
    readErrorDetail: readErrorDetail,
  };
})(window);
