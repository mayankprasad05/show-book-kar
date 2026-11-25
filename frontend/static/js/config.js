/* Shared frontend configuration.
 *
 * The Flask API and these static pages are served on different ports, so the
 * default API origin is the same host on port 5000. Keeping the host in step
 * with the page matters: the session cookie is SameSite=Lax, so a page served
 * from 127.0.0.1 that called localhost (or the reverse) would be a cross-site
 * request and the browser would drop the cookie. Override the API origin
 * before the module loads with `window.SBK_API_BASE = "https://host/api"`.
 */

const apiHost = window.location.hostname || "localhost";
const rawBase = window.SBK_API_BASE || `http://${apiHost}:5000/api`;

export const API_BASE = String(rawBase).replace(/\/+$/, "");

/* Pages live at frontend/ root and frontend/admin/, so links need a prefix. */
const segments = window.location.pathname.split("/").filter(Boolean);
export const BASE = segments.includes("admin") ? "../" : "";

/* Mirrors the backend defaults (.env: HOLD_DURATION_MINUTES / CUTOFF hours).
 * The server is always authoritative; these values only drive display hints. */
export const HOLD_DURATION_MINUTES = Number(window.SBK_HOLD_DURATION_MINUTES || 5);
export const CANCELLATION_CUTOFF_HOURS = Number(window.SBK_CANCELLATION_CUTOFF_HOURS || 2);
export const MAX_SEATS_PER_HOLD = 10;

export const CURRENCY = "INR";
