/** Формы входа и регистрации. */
(function (global) {
  "use strict";

  const PASSWORD_ICON_SHOW =
    '<svg class="auth-password-icon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>';
  const PASSWORD_ICON_HIDE =
    '<svg class="auth-password-icon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"></path>' +
    '<path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>';

  function syncPasswordToggle(btn, revealed) {
    btn.innerHTML = revealed ? PASSWORD_ICON_HIDE : PASSWORD_ICON_SHOW;
    btn.setAttribute("aria-label", revealed ? "Скрыть пароль" : "Показать пароль");
    btn.setAttribute("aria-pressed", revealed ? "true" : "false");
  }

  function initPasswordToggles(root) {
    const scope = root && root.querySelectorAll ? root : document;
    const toggles = scope.querySelectorAll
      ? scope.querySelectorAll(".auth-password-toggle")
      : [];
    toggles.forEach(function (btn) {
      const wrap = btn.closest(".auth-password-wrap");
      const input = wrap && wrap.querySelector("input");
      if (!input) return;

      syncPasswordToggle(btn, false);

      btn.addEventListener("click", function () {
        const reveal = input.type === "password";
        input.type = reveal ? "text" : "password";
        syncPasswordToggle(btn, reveal);
      });
    });
  }

  function bindAuthSubmit(formId, options) {
    const form = document.getElementById(formId);
    const errEl = document.getElementById(options.errorId || "authError");
    if (!form) return;

    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      if (errEl) errEl.textContent = "";

      const fd = new FormData(form);
      if (typeof options.validate === "function") {
        const validationError = options.validate(fd);
        if (validationError) {
          if (errEl) errEl.textContent = validationError;
          return;
        }
      }
      const res = await fetch(options.url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(options.buildBody(fd)),
      });

      if (!res.ok) {
        if (errEl) {
          errEl.textContent = await global.LlmAuditApi.readErrorDetail(
            res,
            options.errorFallback || "Ошибка"
          );
        }
        return;
      }

      const data = await global.LlmAuditApi.parseJsonOrEmpty(res);
      global.LlmAuditAuth.setAccessToken(data.access_token);
      window.location.href = options.redirect || "/";
    });
  }

  global.LlmAuditAuthPages = {
    bindAuthSubmit: bindAuthSubmit,
    initPasswordToggles: initPasswordToggles,
  };
})(window);
