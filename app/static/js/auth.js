/** JWT в localStorage + cookie (для SSR-страниц отчёта). */
(function () {
  const COOKIE_MAX_AGE_SEC = 60 * 60 * 24 * 3;

  function getCookieToken() {
    const parts = document.cookie.split(";").map(function (p) {
      return p.trim();
    });
    for (let i = 0; i < parts.length; i++) {
      if (parts[i].indexOf("access_token=") === 0) {
        return decodeURIComponent(parts[i].slice("access_token=".length));
      }
    }
    return null;
  }

  function getAccessToken() {
    return localStorage.getItem("access_token") || getCookieToken();
  }

  function authHeaders(extra) {
    const h = Object.assign({}, extra || {});
    const t = getAccessToken();
    if (t) h.Authorization = "Bearer " + t;
    return h;
  }

  function setAccessToken(token) {
    localStorage.setItem("access_token", token);
    document.cookie =
      "access_token=" +
      encodeURIComponent(token) +
      "; path=/; SameSite=Lax; max-age=" +
      COOKIE_MAX_AGE_SEC;
    if (window.LlmAuditNav && window.LlmAuditNav.refreshSiteNav) {
      window.LlmAuditNav.refreshSiteNav();
    }
  }

  function clearAccessToken() {
    localStorage.removeItem("access_token");
    document.cookie = "access_token=; path=/; max-age=0; SameSite=Lax";
    if (window.LlmAuditNav && window.LlmAuditNav.refreshSiteNav) {
      window.LlmAuditNav.refreshSiteNav();
    }
  }

  function isLoggedIn() {
    return !!getAccessToken();
  }

  window.LlmAuditAuth = {
    getAccessToken,
    authHeaders,
    setAccessToken,
    clearAccessToken,
    isLoggedIn,
  };
})();
