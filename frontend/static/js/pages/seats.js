/* Seat map and seat hold.
 *
 * Availability comes from the API; selection is local display state only.
 * The hold is all-or-nothing on the server, so a 409 just means "reload and
 * choose again".
 */

import { api } from "../api.js";
import { BASE, MAX_SEATS_PER_HOLD } from "../config.js";
import { initLayout } from "../layout.js";
import { loginHref } from "../session.js";
import {
  escapeHtml,
  formatDay,
  formatTime,
  hideAlert,
  intParam,
  money,
  renderError,
  showAlert,
} from "../ui.js";

const showId = intParam("show");
const showRoot = document.getElementById("show-root");
const mapEl = document.getElementById("seat-map");
const summarySeats = document.getElementById("summary-seats");
const summaryCount = document.getElementById("summary-count");
const summaryTotal = document.getElementById("summary-total");
const holdButton = document.getElementById("hold-button");
const alertEl = document.getElementById("seat-alert");
const backLink = document.getElementById("back-link");

let show = null;
let counts = null;
let seats = [];
let selected = new Set();
let submitting = false;

const pendingKey = `sbk.pending-selection.${showId}`;

function readPendingSelection() {
  try {
    const raw = sessionStorage.getItem(pendingKey);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.map(Number).filter(Number.isInteger) : [];
  } catch {
    return [];
  }
}

function rememberSelection() {
  try {
    sessionStorage.setItem(pendingKey, JSON.stringify([...selected]));
  } catch {
    /* storage disabled: nothing to restore, sign-in still works */
  }
}

function seatLabel(seat) {
  return `${seat.row_label}${seat.seat_number}`;
}

function selectedSeats() {
  return seats.filter((seat) => selected.has(seat.seat_id));
}

function renderShow() {
  if (!show) return;
  document.title = `${show.movie_title} · Choose seats · Show-book-kar`;
  backLink.href = `movie.html?id=${show.movie_id}`;
  backLink.textContent = `← ${show.movie_title}`;

  showRoot.innerHTML = `
    <section class="show-banner">
      <div>
        <p class="eyebrow">${escapeHtml(show.theatre_city)}</p>
        <h1>${escapeHtml(show.movie_title)}</h1>
        <div class="meta-row">
          <span class="meta-chip">${formatDay(show.show_start_at)} &middot; ${formatTime(show.show_start_at)}</span>
          <span class="meta-chip">${escapeHtml(show.theatre_name)}</span>
          <span class="meta-chip">${escapeHtml(show.screen_name)}</span>
        </div>
      </div>
      <div class="counts" id="seat-counts"></div>
    </section>`;

  renderCounts();
}

function renderCounts() {
  const element = document.getElementById("seat-counts");
  if (!element || !counts) return;
  element.innerHTML = `
    <span class="count-pill count-pill--available"><strong>${counts.available_count}</strong> available</span>
    <span class="count-pill count-pill--held"><strong>${counts.held_count}</strong> held</span>
    <span class="count-pill count-pill--booked"><strong>${counts.booked_count}</strong> booked</span>
    <span class="count-pill"><strong>${counts.total_count}</strong> total</span>`;
}

function renderSeat(seat) {
  const isSelected = selected.has(seat.seat_id);
  const unavailable = seat.status !== "AVAILABLE";
  const classes = ["seat", `seat--${seat.status.toLowerCase()}`];

  if (isSelected) classes.push("seat--selected");
  if (seat.seat_type === "vip") classes.push("seat--vip");

  const label = seatLabel(seat);
  const description = `Seat ${label}, ${seat.seat_type}, ${money(seat.price)}, ${seat.status.toLowerCase()}`;

  return `
    <button type="button"
            class="${classes.join(" ")}"
            data-seat-id="${seat.seat_id}"
            ${unavailable ? "disabled" : ""}
            aria-pressed="${isSelected}"
            aria-label="${escapeHtml(description)}"
            title="${escapeHtml(`${label} · ${seat.seat_type} · ${money(seat.price)}`)}">
      ${escapeHtml(label)}
    </button>`;
}

function renderMap() {
  if (!seats.length) {
    mapEl.innerHTML = '<p class="muted small">No seats are configured for this show.</p>';
    return;
  }

  const rows = new Map();
  for (const seat of seats) {
    if (!rows.has(seat.row_label)) rows.set(seat.row_label, []);
    rows.get(seat.row_label).push(seat);
  }

  mapEl.innerHTML = [...rows.entries()]
    .map(
      ([label, rowSeats]) => `
      <div class="seat-row">
        <span class="seat-row-label" aria-hidden="true">${escapeHtml(label)}</span>
        ${rowSeats.map(renderSeat).join("")}
      </div>`
    )
    .join("");
}

function renderSummary() {
  const chosen = selectedSeats();

  summarySeats.innerHTML = chosen.length
    ? chosen.map((seat) => `<span class="chip">${escapeHtml(seatLabel(seat))}</span>`).join("")
    : '<p class="muted small">No seats selected.</p>';

  summaryCount.textContent = String(chosen.length);
  const total = chosen.reduce((sum, seat) => sum + Number(seat.price), 0);
  summaryTotal.textContent = money(total);

  holdButton.disabled = submitting || chosen.length === 0;
  holdButton.textContent = submitting ? "Holding seats…" : "Continue to checkout";
}

function toggleSeat(seatId) {
  if (selected.has(seatId)) {
    selected.delete(seatId);
  } else {
    if (selected.size >= MAX_SEATS_PER_HOLD) {
      showAlert(
        alertEl,
        `You can hold at most ${MAX_SEATS_PER_HOLD} seats in one booking.`,
        "warning"
      );
      return;
    }
    selected.add(seatId);
    hideAlert(alertEl);
  }
  renderMap();
  renderSummary();
}

async function refreshSeats() {
  try {
    const data = await api.seats(showId);
    seats = data.seats;
    counts = data.counts;
    const stillAvailable = new Set(
      seats.filter((seat) => seat.status === "AVAILABLE").map((seat) => seat.seat_id)
    );
    selected = new Set([...selected].filter((seatId) => stillAvailable.has(seatId)));
    renderCounts();
    renderMap();
    renderSummary();
  } catch (error) {
    showAlert(alertEl, `Could not refresh the seat map. ${error.message}`, "error");
  }
}

async function holdSeats() {
  if (submitting || selected.size === 0) return;

  submitting = true;
  hideAlert(alertEl);
  renderSummary();

  try {
    const data = await api.hold(showId, [...selected]);
    const booking = data.booking;

    sessionStorage.setItem(
      `sbk.hold.${booking.booking_id}`,
      JSON.stringify({
        expires: booking.hold_expires_at,
        minutes: booking.hold_duration_minutes,
      })
    );
    sessionStorage.removeItem(pendingKey);

    window.location.href = `${BASE}checkout.html?booking=${booking.booking_id}`;
  } catch (error) {
    if (error.status === 401) {
      // Keep the selection across the sign-in round trip.
      rememberSelection();
      window.location.href = loginHref(`seats.html?show=${showId}`);
      return;
    }

    const conflict = error.code === "SEAT_UNAVAILABLE";
    showAlert(
      alertEl,
      conflict
        ? `${error.message} Someone took one of those seats first, so nothing was held. The map has been refreshed — pick again.`
        : error.message,
      "error"
    );

    submitting = false;
    renderSummary();

    if (conflict || error.status === 409) {
      await refreshSeats();
    }
  }
}

async function main() {
  await initLayout({ active: "movies" });

  if (!showId) {
    renderError(showRoot, "No show was specified. Open a showtime from a movie page.");
    return;
  }

  try {
    const [showData, seatsData] = await Promise.all([api.show(showId), api.seats(showId)]);
    show = showData.show;
    counts = seatsData.counts || showData.counts;
    seats = seatsData.seats;

    const pending = readPendingSelection();
    if (pending.length) {
      const available = new Set(
        seats.filter((seat) => seat.status === "AVAILABLE").map((seat) => seat.seat_id)
      );
      selected = new Set(pending.filter((seatId) => available.has(seatId)));
      sessionStorage.removeItem(pendingKey);
    }

    renderShow();
    renderMap();
    renderSummary();
  } catch (error) {
    renderError(showRoot, error.message, main);
  }
}

mapEl.addEventListener("click", (event) => {
  const button = event.target.closest("[data-seat-id]");
  if (!button || button.disabled) return;
  toggleSeat(Number(button.dataset.seatId));
});

holdButton.addEventListener("click", holdSeats);

main();
