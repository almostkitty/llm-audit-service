/** Страница /account */
(function (global) {
  "use strict";

  const profileMsgEl = document.getElementById("profileMsg");
  const profileErrEl = document.getElementById("profileErr");

  function roleLabel(role) {
    const m = {
      student: "Студент",
      teacher: "Преподаватель",
      user: "Пользователь",
    };
    return m[role] || role;
  }

  function authJsonHeaders() {
    return global.LlmAuditAuth.authHeaders({ "Content-Type": "application/json" });
  }

  function clearProfileMessages() {
    if (profileMsgEl) {
      profileMsgEl.textContent = "";
      profileMsgEl.hidden = true;
    }
    if (profileErrEl) {
      profileErrEl.textContent = "";
      profileErrEl.hidden = true;
    }
  }

  function showErr(msg) {
    clearProfileMessages();
    if (profileErrEl) {
      profileErrEl.textContent = msg;
      profileErrEl.hidden = false;
    }
  }

  function showOk(msg) {
    clearProfileMessages();
    if (profileMsgEl) {
      profileMsgEl.textContent = msg;
      profileMsgEl.hidden = false;
    }
  }

  function fmtName(v) {
    return (v && String(v).trim()) || "—";
  }

  function redirectToLogin() {
    global.LlmAuditAuth.clearAccessToken();
    window.location.href = "/login";
  }

  async function loadAccount() {
    const loading = document.getElementById("accountLoading");
    const userEl = document.getElementById("accountUser");

    if (!global.LlmAuditAuth || !global.LlmAuditAuth.isLoggedIn()) {
      window.location.href = "/login";
      return;
    }

    const res = await fetch("/api/auth/me", {
      headers: global.LlmAuditAuth.authHeaders(),
    });

    if (loading) loading.hidden = true;

    if (!res.ok) {
      redirectToLogin();
      return;
    }

    const data = await res.json();
    document.getElementById("accFirstName").textContent = fmtName(data.first_name);
    document.getElementById("accLastName").textContent = fmtName(data.last_name);
    document.getElementById("accEmail").textContent = data.email;
    document.getElementById("accRole").textContent = roleLabel(data.role);

    const fn = document.getElementById("firstName");
    const ln = document.getElementById("lastName");
    if (fn) fn.value = data.first_name || "";
    if (ln) ln.value = data.last_name || "";
    const ne = document.getElementById("newEmail");
    if (ne) ne.value = data.email;
    if (userEl) userEl.hidden = false;
  }

  function bindForms() {
    const formProfile = document.getElementById("formProfile");
    if (formProfile) {
      formProfile.addEventListener("submit", async function (e) {
        e.preventDefault();
        clearProfileMessages();
        const fd = new FormData(e.target);
        const res = await fetch("/api/auth/me", {
          method: "PATCH",
          headers: authJsonHeaders(),
          body: JSON.stringify({
            first_name: fd.get("first_name"),
            last_name: fd.get("last_name"),
          }),
        });
        if (!res.ok) {
          showErr(await global.LlmAuditApi.readErrorDetail(res, "Ошибка сохранения"));
          return;
        }
        const data = await res.json();
        document.getElementById("accFirstName").textContent = fmtName(data.first_name);
        document.getElementById("accLastName").textContent = fmtName(data.last_name);
        showOk("Имя и фамилия обновлены.");
      });
    }

    const formEmail = document.getElementById("formEmail");
    if (formEmail) {
      formEmail.addEventListener("submit", async function (e) {
        e.preventDefault();
        clearProfileMessages();
        const fd = new FormData(e.target);
        const res = await fetch("/api/auth/me", {
          method: "PATCH",
          headers: authJsonHeaders(),
          body: JSON.stringify({
            email: fd.get("email"),
            current_password: fd.get("current_password"),
          }),
        });
        if (!res.ok) {
          showErr(await global.LlmAuditApi.readErrorDetail(res, "Ошибка сохранения"));
          return;
        }
        const data = await res.json();
        document.getElementById("accEmail").textContent = data.email;
        document.getElementById("newEmail").value = data.email;
        e.target.querySelector('[name="current_password"]').value = "";
        showOk("Email обновлён.");
        if (global.LlmAuditNav && global.LlmAuditNav.refreshSiteNav) {
          global.LlmAuditNav.refreshSiteNav();
        }
      });
    }

    const formPassword = document.getElementById("formPassword");
    if (formPassword) {
      formPassword.addEventListener("submit", async function (e) {
        e.preventDefault();
        clearProfileMessages();
        const cur = document.getElementById("pwdCur").value;
        const n1 = document.getElementById("pwdNew").value;
        const n2 = document.getElementById("pwdNew2").value;
        if (n1 !== n2) {
          showErr("Новые пароли не совпадают.");
          return;
        }
        const res = await fetch("/api/auth/me", {
          method: "PATCH",
          headers: authJsonHeaders(),
          body: JSON.stringify({
            current_password: cur,
            new_password: n1,
          }),
        });
        if (!res.ok) {
          showErr(await global.LlmAuditApi.readErrorDetail(res, "Ошибка смены пароля"));
          return;
        }
        document.getElementById("pwdCur").value = "";
        document.getElementById("pwdNew").value = "";
        document.getElementById("pwdNew2").value = "";
        showOk("Пароль обновлён.");
      });
    }

    const formDelete = document.getElementById("formDelete");
    if (formDelete) {
      formDelete.addEventListener("submit", async function (e) {
        e.preventDefault();
        clearProfileMessages();
        const pwd = document.getElementById("pwdDel").value;
        if (!window.confirm("Удалить аккаунт без возможности восстановления?")) return;

        const res = await fetch("/api/auth/me", {
          method: "DELETE",
          headers: authJsonHeaders(),
          body: JSON.stringify({ password: pwd }),
        });

        if (!res.ok) {
          showErr(await global.LlmAuditApi.readErrorDetail(res, "Ошибка удаления"));
          return;
        }
        redirectToLogin();
      });
    }
  }

  bindForms();
  loadAccount();
})(window);
