/* Session helpers. Identity always comes from the API's signed cookie. */

import { api, ApiError } from "./api.js";
import { BASE } from "./config.js";

let cachedUser;
let loadPromise;

export function currentPagePath() {
  const file = window.location.pathname.split("/").pop() || "index.html";
  return (BASE === "../" ? "admin/" : "") + file + window.location.search;
}

export function safeNext(raw, fallback = "index.html") {
  if (!raw) return fallback;
  // Same-origin relative HTML paths only; blocks absolute and protocol URLs.
  if (!/^[A-Za-z0-9._~%\-/]+\.html(\?[A-Za-z0-9._~%\-&=]*)?(#[A-Za-z0-9._~\-]*)?$/.test(raw)) {
    return fallback;
  }
  if (raw.includes("://") || raw.startsWith("//") || raw.includes("..")) return fallback;
  return raw;
}

export function loginHref(next) {
  const target = safeNext(next || currentPagePath(), "index.html");
  return `${BASE}login.html?next=${encodeURIComponent(target)}`;
}

export async function loadUser(force = false) {
  if (!force && cachedUser !== undefined) return cachedUser;
  if (!force && loadPromise) return loadPromise;

  loadPromise = (async () => {
    try {
      const data = await api.me();
      cachedUser = data.user;
    } catch (error) {
      if (error instanceof ApiError && (error.isAuth || error.isForbidden)) {
        cachedUser = null;
      } else {
        cachedUser = null;
        throw error;
      }
    }
    return cachedUser;
  })();

  try {
    return await loadPromise;
  } finally {
    loadPromise = null;
  }
}

export function getUser() {
  return cachedUser ?? null;
}

export async function requireUser(next) {
  let user = null;
  try {
    user = await loadUser(true);
  } catch {
    user = null;
  }
  if (!user) {
    window.location.replace(loginHref(next));
    throw new Error("AUTH_REDIRECT");
  }
  return user;
}

export async function logout() {
  try {
    await api.logout();
  } catch {
    // The cookie may already be gone; the redirect below still applies.
  }
  cachedUser = null;
  window.location.href = `${BASE}index.html`;
}
