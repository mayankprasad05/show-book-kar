/* Shared page chrome: brand, role-aware navigation, user chip and footer. */

import { BASE } from "./config.js";
import { loadUser, logout } from "./session.js";
import { escapeHtml, initials } from "./ui.js";

const NAV = [
  { key: "movies", label: "Movies", href: "index.html" },
  { key: "bookings", label: "My bookings", href: "bookings.html" },
  { key: "admin", label: "Admin", href: "admin/index.html", adminOnly: true },
];

let wired = false;

export async function initLayout({ active = "" } = {}) {
  let user = null;
  try {
    user = await loadUser();
  } catch {
    user = null;
  }

  renderHeader(user, active);
  renderFooter();
  wireHeader();
  return user;
}

function renderHeader(user, active) {
  const header = document.getElementById("app-header");
  if (!header) return;

  const links = NAV.filter((item) => !item.adminOnly || user?.role === "admin")
    .map((item) => `
      <a class="nav-link${active === item.key ? " is-active" : ""}"
         href="${BASE}${item.href}"
         ${active === item.key ? 'aria-current="page"' : ""}>${item.label}</a>`)
    .join("");

  const account = user
    ? `<span class="user-chip" title="${escapeHtml(user.email)}">
         <span class="avatar">${escapeHtml(initials(user.name))}</span>
         <span>${escapeHtml(user.name)}</span>
         ${user.role === "admin" ? '<span class="role-tag">admin</span>' : ""}
       </span>
       <button class="btn btn--ghost btn--sm" type="button" data-action="logout">Sign out</button>`
    : `<a class="btn btn--ghost btn--sm" href="${BASE}login.html">Sign in</a>
       <a class="btn btn--primary btn--sm" href="${BASE}register.html">Create account</a>`;

  header.innerHTML = `
    <div class="header-inner">
      <a class="brand" href="${BASE}index.html">
        <span class="brand-mark" aria-hidden="true">▶</span>
        <span>Show-book-kar</span>
      </a>
      <nav class="nav" aria-label="Main">${links}</nav>
      <div class="header-user">${account}</div>
    </div>`;
}

function renderFooter() {
  const footer = document.getElementById("app-footer");
  if (!footer) return;
  footer.className = "site-footer";
  footer.innerHTML = `
    <div class="footer-inner">
      <span>Show-book-kar · movie ticket booking DBMS project</span>
      <span>PostgreSQL + Flask · seats are database-authoritative · simulated payments</span>
    </div>`;
}

function wireHeader() {
  if (wired) return;
  wired = true;
  document.getElementById("app-header")?.addEventListener("click", (event) => {
    const button = event.target.closest('[data-action="logout"]');
    if (!button) return;
    button.disabled = true;
    logout();
  });
}
