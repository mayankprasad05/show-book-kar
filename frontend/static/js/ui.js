/* Small UI helpers shared by every page: formatting, states and feedback. */

import { CURRENCY } from "./config.js";

const currency = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: CURRENCY,
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const dateTime = new Intl.DateTimeFormat("en-IN", {
  weekday: "short",
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

const dayMonth = new Intl.DateTimeFormat("en-IN", {
  weekday: "short",
  day: "numeric",
  month: "short",
});

const timeOnly = new Intl.DateTimeFormat("en-IN", {
  hour: "numeric",
  minute: "2-digit",
});

export function money(value) {
  const amount = Number(value);
  return currency.format(Number.isFinite(amount) ? amount : 0);
}

export function formatDateTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : dateTime.format(date);
}

export function formatDay(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : dayMonth.format(date);
}

export function formatTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : timeOnly.format(date);
}

export function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => {
    switch (character) {
      case "&": return "&amp;";
      case "<": return "&lt;";
      case ">": return "&gt;";
      case '"': return "&quot;";
      default: return "&#39;";
    }
  });
}

export function initials(title) {
  const words = String(title || "").trim().split(/\s+/).filter(Boolean);
  const letters = (words[0]?.[0] || "") + (words[1]?.[0] || "");
  return letters.toUpperCase() || "★";
}

const GRADIENTS = [
  ["#3b4f7d", "#131a29"],
  ["#6a3f63", "#161022"],
  ["#2f6a63", "#0e1a1c"],
  ["#7a5230", "#1a1208"],
  ["#455a90", "#101726"],
  ["#7b3b45", "#190d12"],
  ["#3f6b4a", "#0e1712"],
  ["#5c4a8a", "#141024"],
];

export function gradientFor(seed) {
  const index = Math.abs(Number(seed) || 0) % GRADIENTS.length;
  const [g1, g2] = GRADIENTS[index];
  return `--g1:${g1};--g2:${g2}`;
}

export function seatLabels(seats) {
  return (seats || []).map((seat) => `${seat.row_label}${seat.seat_number}`).join(", ");
}

const BADGE_TONES = {
  PENDING: "amber",
  HELD: "amber",
  CONFIRMED: "green",
  SUCCESS: "green",
  BOOKED: "blue",
  CANCELLED: "red",
  FAILED: "red",
  EXPIRED: "gray",
  AVAILABLE: "gray",
  REQUESTED: "amber",
  APPROVED: "green",
  REJECTED: "red",
};

export function statusBadge(status) {
  const tone = BADGE_TONES[status] || "gray";
  return `<span class="badge badge--${tone}">${escapeHtml(status)}</span>`;
}

export function param(name) {
  return new URLSearchParams(window.location.search).get(name);
}

export function intParam(name) {
  const raw = param(name);
  return raw && /^\d+$/.test(raw) ? Number(raw) : null;
}

/* -------------------------------------------------------------------------
   Feedback
   ------------------------------------------------------------------------- */

export function toast(message, type = "info", timeout = 4600) {
  let stack = document.getElementById("toasts");
  if (!stack) {
    stack = document.createElement("div");
    stack.id = "toasts";
    stack.className = "toast-stack";
    stack.setAttribute("aria-live", "polite");
    document.body.append(stack);
  }
  const node = document.createElement("div");
  node.className = `toast toast--${type}`;
  node.setAttribute("role", type === "error" ? "alert" : "status");
  node.textContent = message;
  stack.append(node);
  window.setTimeout(() => {
    node.style.opacity = "0";
    node.style.transition = "opacity 0.2s ease";
    window.setTimeout(() => node.remove(), 220);
  }, timeout);
}

export function showAlert(element, message, type = "error") {
  if (!element) return;
  element.className = `alert alert--${type}`;
  element.textContent = message;
  element.hidden = false;
}

export function hideAlert(element) {
  if (!element) return;
  element.hidden = true;
  element.textContent = "";
}

/* -------------------------------------------------------------------------
   Page states
   ------------------------------------------------------------------------- */

export function renderLoading(container, message = "Loading…") {
  container.innerHTML = `<div class="state"><p>${escapeHtml(message)}</p></div>`;
}

export function renderEmpty(container, title, message, actionHtml = "") {
  container.innerHTML = `
    <div class="state">
      <h3>${escapeHtml(title)}</h3>
      <p>${escapeHtml(message)}</p>
      ${actionHtml}
    </div>`;
}

export function renderError(container, message, onRetry) {
  container.innerHTML = `
    <div class="state state--error">
      <h3>Something went wrong</h3>
      <p>${escapeHtml(message)}</p>
    </div>`;
  if (typeof onRetry === "function") {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn--secondary";
    button.textContent = "Try again";
    button.addEventListener("click", onRetry);
    container.querySelector(".state").append(button);
  }
}

export function skeletonGrid(container, count = 6) {
  container.innerHTML = Array.from({ length: count }, () => `
    <div class="skeleton-card" aria-hidden="true">
      <div class="skeleton skeleton-poster"></div>
      <div class="skeleton skeleton-line"></div>
      <div class="skeleton skeleton-line short"></div>
    </div>`).join("");
}
