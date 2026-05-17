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

  function buildReportUrl(checkId) {
    return window.location.origin + "/report/" + encodeURIComponent(String(checkId));
  }

  function copyTextToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).then(
        function () {
          return true;
        },
        function () {
          return false;
        }
      );
    }
    return new Promise(function (resolve) {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      resolve(ok);
    });
  }

  function copyReportLink(checkId) {
    return copyTextToClipboard(buildReportUrl(checkId));
  }

  global.LlmAuditApi = {
    escapeHtml: escapeHtml,
    parseJsonOrEmpty: parseJsonOrEmpty,
    readErrorDetail: readErrorDetail,
    buildReportUrl: buildReportUrl,
    copyReportLink: copyReportLink,
  };
})(window);
