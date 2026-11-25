/* Booking history with policy-based cancellation. */

import { api } from "../api.js";
import { CANCELLATION_CUTOFF_HOURS } from "../config.js";
import { initLayout } from "../layout.js";
import { loginHref, requireUser } from "../session.js";
import {
  escapeHtml,
  formatDateTime,
  money,
  renderEmpty,
  renderError,
  seatLabels,
  statusBadge,
  toast,
} from "../ui.js";

const root = document.getElementById("bookings-root");
const countEl = document.getElementById("bookings-count");

let bookings = [];

function cancellationDeadline(booking) {
  return new Date(booking.show_start_at).getTime() - CANCELLATION_CUTOFF_HOURS * 3600 * 1000;
}

function isCancellable(booking) {
  return booking.booking_status === "CONFIRMED" && Date.now() <= cancellationDeadline(booking);
}

function footNote(booking) {
  switch (booking.booking_status) {
    case "PENDING":
      return "Seats are held temporarily. Complete the simulated payment before the hold expires.";
    case "CONFIRMED":
      return isCancellable(booking)
        ? `Cancellation is open until ${CANCELLATION_CUTOFF_HOURS} hours before the show.`
        : `The cancellation window has closed (${CANCELLATION_CUTOFF_HOURS} hours before the show).`;
    case "CANCELLED":
      return "Seats released. Refund status: requested (simulated payment).";
    case "EXPIRED":
      return "The hold expired and the seats were released.";
    default:
      return "";
  }
}

function actions(booking) {
  const id = booking.booking_id;

  if (booking.booking_status === "PENDING") {
    return `<a class="btn btn--primary btn--sm" href="checkout.html?booking=${id}">Complete payment</a>`;
  }

  if (booking.booking_status === "CONFIRMED" && isCancellable(booking)) {
    return `<button class="btn btn--danger btn--sm" type="button" data-cancel="${id}">Cancel booking</button>`;
  }

  if (booking.booking_status === "CANCELLED" || booking.booking_status === "EXPIRED") {
    return `<a class="btn btn--ghost btn--sm" href="movie.html?id=${booking.movie_id}">Book again</a>`;
  }

  return "";
}

function bookingCard(booking) {
  const seats = booking.seats || [];
  const seatChips = seats.length
    ? seats
        .map(
          (seat) =>
            `<span class="chip" title="${escapeHtml(`${seat.status} · ${money(seat.price)}`)}">${escapeHtml(
              `${seat.row_label}${seat.seat_number}`
            )}</span>`
        )
        .join("")
    : '<span class="muted small">No seats recorded</span>';

  return `
    <article class="booking-card" aria-label="Booking ${booking.booking_id}, ${escapeHtml(booking.movie_title)}">
      <div class="booking-head">
        <h3>${escapeHtml(booking.movie_title)}</h3>
        ${statusBadge(booking.booking_status)}
      </div>

      <div class="booking-body">
        <div>
          <div class="booking-meta">
            <span>${formatDateTime(booking.show_start_at)}</span>
            <span><strong>${escapeHtml(booking.theatre_name)}</strong> &middot; ${escapeHtml(booking.theatre_city)}</span>
            <span>${escapeHtml(booking.screen_name)}</span>
          </div>
          <div class="booking-seats chips">${seatChips}</div>
          <p class="note" style="margin-top:8px">
            Booked ${formatDateTime(booking.booking_created_at)} &middot; Ref #${booking.booking_id}
          </p>
        </div>
        <div class="booking-amount">${money(booking.booking_total_amount)}</div>
      </div>

      <div class="booking-foot">
        <span class="note">${escapeHtml(footNote(booking))}</span>
        <div class="booking-actions">${actions(booking)}</div>
      </div>
    </article>`;
}

async function cancelBooking(bookingId, button) {
  const booking = bookings.find((item) => item.booking_id === bookingId);
  const description = booking
    ? `${booking.movie_title} — ${seatLabels(booking.seats)}`
    : `booking #${bookingId}`;

  const confirmed = window.confirm(
    `Cancel ${description}?\n\nThe seats are released for other customers and a refund is requested. ` +
      "This cannot be undone."
  );
  if (!confirmed) return;

  button.disabled = true;
  try {
    const data = await api.cancel(bookingId);
    const refund = data.booking?.refund_amount;
    toast(
      `Booking #${bookingId} cancelled.${refund ? ` Refund requested: ${money(refund)}.` : ""}`,
      "success"
    );
    await load();
  } catch (error) {
    toast(error.message, "error");
    button.disabled = false;
  }
}

async function load() {
  root.innerHTML = '<div class="state"><p>Loading your bookings…</p></div>';
  countEl.textContent = "";

  try {
    const data = await api.bookings();
    bookings = data.bookings;
    countEl.textContent = `${bookings.length} booking${bookings.length === 1 ? "" : "s"}`;

    if (!bookings.length) {
      renderEmpty(
        root,
        "No bookings yet",
        "Choose a movie, pick a showtime and hold your first seats.",
        '<a class="btn btn--primary" href="index.html">Browse movies</a>'
      );
      return;
    }

    root.innerHTML = `<div class="booking-list">${bookings.map(bookingCard).join("")}</div>`;
  } catch (error) {
    if (error.status === 401) {
      window.location.href = loginHref("bookings.html");
      return;
    }
    renderError(root, error.message, load);
  }
}

root.addEventListener("click", (event) => {
  const button = event.target.closest("[data-cancel]");
  if (!button) return;
  cancelBooking(Number(button.dataset.cancel), button);
});

async function main() {
  await initLayout({ active: "bookings" });

  try {
    await requireUser("bookings.html");
  } catch {
    return;
  }

  await load();
}

main();
