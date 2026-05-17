/** Состояние шапки: гость vs авторизованный пользователь. */
(function () {
  async function refreshSiteNav() {
    const guest = document.getElementById("navAuthGuest");
    const userBlock = document.getElementById("navAuthUser");

    if (!guest || !userBlock) return;

    if (!window.LlmAuditAuth || !window.LlmAuditAuth.isLoggedIn()) {
      guest.hidden = false;
      userBlock.hidden = true;
      return;
    }

    try {
      const res = await fetch("/api/auth/me", {
        headers: window.LlmAuditAuth.authHeaders(),
      });
      if (!res.ok) {
        window.LlmAuditAuth.clearAccessToken();
        guest.hidden = false;
        userBlock.hidden = true;
        return;
      }
      guest.hidden = true;
      userBlock.hidden = false;

      const activePage = document.body.dataset.activePage || "";
      if (activePage === "login" || activePage === "register") {
        window.location.replace("/");
      }
    } catch (_e) {
      guest.hidden = false;
      userBlock.hidden = true;
    }

    bindLogoutOnce();
  }

  function bindLogoutOnce() {
    const logoutBtn = document.getElementById("navLogoutBtn");
    if (logoutBtn && !logoutBtn.dataset.bound) {
      logoutBtn.dataset.bound = "1";
      logoutBtn.addEventListener("click", function () {
        window.LlmAuditAuth.clearAccessToken();
        window.location.href = "/";
      });
    }
  }

  window.LlmAuditNav = { refreshSiteNav };

  bindLogoutOnce();
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", refreshSiteNav);
  } else {
    refreshSiteNav();
  }
})();
