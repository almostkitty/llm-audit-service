/** Блок «Оценка преподавателя» на главной и /report/{id}. */
(function (global) {
  "use strict";

  function init(cfg) {
    const section = document.getElementById(cfg.sectionId || "teacherFeedbackSection");
    if (!section) {
      return { refresh: function () {}, reset: function () {} };
    }

    const statusEl = document.getElementById("teacherFeedbackStatus");
    const errEl = document.getElementById("teacherFeedbackErr");
    const agreeBtn = document.getElementById("teacherAgreeBtn");
    const disagreeBtn = document.getElementById("teacherDisagreeBtn");

    function resolveCheckId() {
      if (typeof cfg.getCheckId === "function") return cfg.getCheckId();
      return cfg.checkId || null;
    }

    function showStatus(agrees) {
      if (!statusEl) return;
      statusEl.hidden = false;
      statusEl.className = "teacher-feedback__status text-success";
      statusEl.textContent = agrees
        ? "Вы отметили: согласен с результатом проверки."
        : "Вы отметили: не согласен с результатом проверки.";
      if (errEl) {
        errEl.hidden = true;
        errEl.textContent = "";
      }
    }

    async function loadExisting(checkId) {
      if (!checkId || !global.LlmAuditAuth || !global.LlmAuditAuth.isLoggedIn()) return;
      try {
        const res = await fetch(
          "/api/teacher-feedback/" + encodeURIComponent(checkId),
          { headers: global.LlmAuditAuth.authHeaders() }
        );
        const data = await global.LlmAuditApi.parseJsonOrEmpty(res);
        if (res.ok && data.feedback) {
          showStatus(data.feedback.agrees_with_detection);
        }
      } catch (_e) {
        /* ignore */
      }
    }

    async function submit(agrees) {
      const checkId = resolveCheckId();
      if (!checkId) return;
      if (cfg.canShow && !cfg.canShow()) return;

      if (errEl) {
        errEl.hidden = true;
        errEl.textContent = "";
      }
      if (!global.LlmAuditAuth || !global.LlmAuditAuth.isLoggedIn()) {
        if (errEl) {
          errEl.textContent = "Требуется вход под аккаунтом преподавателя.";
          errEl.hidden = false;
        }
        return;
      }

      try {
        const res = await fetch("/api/teacher-feedback", {
          method: "POST",
          headers: global.LlmAuditAuth.authHeaders({
            "Content-Type": "application/json",
          }),
          body: JSON.stringify({ audit_check_id: checkId, agrees: agrees }),
        });
        const data = await global.LlmAuditApi.parseJsonOrEmpty(res);
        if (!res.ok) {
          if (errEl) {
            errEl.textContent = data.detail || "Не удалось сохранить оценку.";
            errEl.hidden = false;
          }
          return;
        }
        showStatus(agrees);
      } catch (_e) {
        if (errEl) {
          errEl.textContent = "Ошибка запроса.";
          errEl.hidden = false;
        }
      }
    }

    function refresh() {
      if (cfg.alwaysVisible) {
        section.hidden = false;
        const checkId = resolveCheckId();
        if (checkId && cfg.reloadOnRefresh !== false) {
          loadExisting(checkId);
        }
        return;
      }
      const show = (!cfg.canShow || cfg.canShow()) && !!resolveCheckId();
      section.hidden = !show;
      if (show) {
        loadExisting(resolveCheckId());
      } else {
        if (statusEl) statusEl.hidden = true;
        if (errEl) errEl.hidden = true;
      }
    }

    function reset() {
      if (!cfg.alwaysVisible) section.hidden = true;
      if (statusEl) statusEl.hidden = true;
      if (errEl) errEl.hidden = true;
    }

    if (agreeBtn) agreeBtn.addEventListener("click", function () { submit(true); });
    if (disagreeBtn) disagreeBtn.addEventListener("click", function () { submit(false); });

    if (cfg.initialFeedback) {
      showStatus(cfg.initialFeedback.agrees_with_detection);
    }

    if (cfg.alwaysVisible) {
      section.hidden = false;
    } else {
      refresh();
    }

    return { refresh: refresh, reset: reset, showStatus: showStatus };
  }

  global.LlmAuditTeacherFeedback = { init: init };
})(window);
