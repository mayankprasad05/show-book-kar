/* Checkout: order summary, hold countdown and simulated payment. */

import { api } from "../api.js";
import { BASE, HOLD_DURATION_MINUTES } from "../config.js";
import { initLayout } from "../layout.js";
import { requireUser } from "../session.js";
import {
  escapeHtml,
  formatDateTime,
  hideAlert,
  intParam,
  money,
  renderError,
  seatLabels,
  showAlert,
  toast,
} from "../ui.js";

const bookingId = intParam("booking");
const root = document.getElementById("checkout-root");

let currentBooking = null;
let holdExpiry = null;
let timer = null;
let paying = false;

function readHoldExpiry() {
  try {
    const raw = sessionStorage.getItem(`sbk.hold.${bookingId}`);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    const date = parsed?.expires ? new Date(parsed.expires) : null;
    return date && !Number.isNaN(date.getTime()) ? date : null;
  } catch {
    return null;
  }
}

function clearTimer() {
  if (timer !== null) {
    window.clearInterval(timer);
    timer = null;
  }
}

function clearHold() {
  sessionStorage.removeItem(`sbk.hold.${bookingId}`);
  holdExpiry = null;
  clearTimer();
}

/* -------------------------------------------------------------------------
   Renderers
   ------------------------------------------------------------------------- */

function renderTicket(booking) {
  clearTimer();
  document.title = `Booking #${booking.booking_id} · Show-book-kar`;
  root.innerHTML = `
    <div class="ticket">
      <div class="ticket-icon" aria-hidden="true">✓</div>
      <p class="eyebrow">Payment successful</p>
      <h1>You're all set</h1>
      <p class="muted">Your seats are confirmed and booked in the database.</p>
      <div class="booking-ref">Booking #${booking.booking_id}</div>

      <dl class="summary-list ticket-details">
        <div><dt>Movie</dt><dd>${escapeHtml(booking.movie_title)}</dd></div>
        <div><dt>Venue</dt><dd>${escapeHtml(booking.theatre_name)} · ${escapeHtml(booking.screen_name)}</dd></div>
        <div><dt>Showtime</dt><dd>${formatDateTime(booking.show_start_at)}</dd></div>
        <div><dt>Seats</dt><dd>${escapeHtml(seatLabels(booking.seats))}</dd></div>
        <div class="total"><dt>Paid</dt><dd>${money(booking.booking_total_amount)}</dd></div>
      </dl>

      <div class="ticket-actions">
        <a class="btn btn--primary" href="bookings.html">My bookings</a>
        <a class="btn btn--secondary" href="index.html">Browse movies</a>
      </div>
    </div>`;
}

function renderPending(booking, flash = null) {
  paying = false;
  document.title = `Checkout · ${booking.movie_title} · Show-book-kar`;

  root.innerHTML = `
    <div class="checkout-layout">
      <section class="card" aria-labelledby="order-heading">
        <p class="eyebrow">Order summary</p>
        <h1 id="order-heading">${escapeHtml(booking.movie_title)}</h1>
        <p class="muted">${escapeHtml(booking.theatre_name)} · ${escapeHtml(booking.screen_name)} · ${escapeHtml(booking.theatre_city)}</p>

        <dl class="summary-list" style="margin-top:18px">
          <div><dt>Showtime</dt><dd>${formatDateTime(booking.show_start_at)}</dd></div>
          <div><dt>Seats</dt><dd>${escapeHtml(seatLabels(booking.seats))}</dd></div>
          <div><dt>Booking reference</dt><dd class="mono">#${booking.booking_id}</dd></div>
          <div><dt>Status</dt><dd>Pending payment</dd></div>
          <div class="total"><dt>Total (server-calculated)</dt><dd>${money(booking.booking_total_amount)}</dd></div>
        </dl>
        <p class="note" style="margin-top:14px">
          The amount comes from the database prices for these seats. Nothing is charged:
          payment is simulated for the project demo.
        </p>
      </section>

      <aside class="card" style="display:flex;flex-direction:column;gap:14px" aria-labelledby="pay-heading">
        <div id="hold-timer" class="countdown" hidden>
          <span>Seats held for</span>
          <strong id="hold-remaining">--:--</strong>
        </div>

        <div id="pay-alert" class="alert" hidden></div>

        <h2 id="pay-heading">Simulated payment</h2>
        <p class="note">
          Choose the outcome to demonstrate. A decline records a failed payment and keeps the
          booking pending so you can retry inside the hold window.
        </p>

        <div class="pay-actions">
          <button class="btn btn--primary btn--block" type="button" data-pay="success">Pay successfully</button>
          <button class="btn btn--secondary btn--block" type="button" data-pay="failure">Simulate a declined payment</button>
          <a class="btn btn--ghost btn--block" href="seats.html?show=${booking.show_id}">Back to seat map</a>
        </div>

        <p class="note">Booking holds expire ${HOLD_DURATION_MINUTES} minutes after they are created.</p>
      </aside>
    </div>`;

  wirePayment();
  startCountdown(booking);

  if (flash) {
    showAlert(document.getElementById("pay-alert"), flash.text, flash.type);
  }
}

function renderExpired(booking) {
  clearTimer();
  clearHold();
  document.title = "Hold expired · Show-book-kar";
  root.innerHTML = `
    <div class="card">
      <p class="eyebrow">Hold expired</p>
      <h1>These seats went back on sale</h1>
      <p class="muted" style="margin:12px 0 6px">
        The hold on booking <span class="mono">#${booking?.booking_id ?? bookingId}</span> has ended,
        so the database released the seats. Start again from the seat map.
      </p>
      <div class="ticket-actions" style="justify-content:flex-start">
        ${booking?.show_id ? `<a class="btn btn--primary" href="seats.html?show=${booking.show_id}">Pick seats again</a>` : ""}
        <a class="btn btn--secondary" href="bookings.html">My bookings</a>
        <a class="btn btn--ghost" href="index.html">Browse movies</a>
      </div>
    </div>`;
}

function renderClosed(booking) {
  clearTimer();
  const cancelled = booking.booking_status === "CANCELLED";
  document.title = `${cancelled ? "Cancelled" : "Expired"} booking · Show-book-kar`;
  root.innerHTML = `
    <div class="card">
      <p class="eyebrow">${cancelled ? "Booking cancelled" : "Hold expired"}</p>
      <h1>${cancelled ? "This booking was cancelled" : "This hold has expired"}</h1>
      <p class="muted" style="margin:12px 0 6px">
        ${cancelled
          ? "The seats were released and the refund is recorded as requested (simulated payment)."
          : "The five-minute hold ended before payment, so the seats went back on sale."}
        Booking <span class="mono">#${booking.booking_id}</span>.
      </p>
      <div class="ticket-actions" style="justify-content:flex-start">
        <a class="btn btn--primary" href="movie.html?id=${booking.movie_id}">Book this movie again</a>
        <a class="btn btn--secondary" href="bookings.html">My bookings</a>
      </div>
    </div>`;
}

/* -------------------------------------------------------------------------
   Behaviour
   ------------------------------------------------------------------------- */

function startCountdown(booking) {
  clearTimer();
  const box = document.getElementById("hold-timer");
  const value = document.getElementById("hold-remaining");
  if (!box || !value) return;

  if (!holdExpiry) {
    box.hidden = false;
    box.innerHTML = "<span>Hold expiry</span><strong>not available</strong>";
    return;
  }

  box.hidden = false;

  const tick = () => {
    const remaining = holdExpiry.getTime() - Date.now();
    if (remaining <= 0) {
      value.textContent = "expired";
      box.classList.add("is-urgent");
      renderExpired(booking);
      return;
    }
    const seconds = Math.floor(remaining / 1000);
    value.textContent = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
    box.classList.toggle("is-urgent", remaining < 60_000);
  };

  tick();
  timer = window.setInterval(tick, 1000);
}

function setPayButtons(disabled) {
  root.querySelectorAll("[data-pay]").forEach((button) => {
    button.disabled = disabled;
  });
}

async function pay(simulate) {
  if (paying) return;
  paying = true;
  setPayButtons(true);

  try {
    const data = await api.pay(bookingId, simulate);
    const result = data.booking;

    if (result.payment_status === "SUCCESS") {
      clearHold();
      toast("Payment confirmed — seats booked.", "success");
      await load();
      return;
    }

    await load({
      type: "warning",
      text:
        "The simulated payment was declined. No payment was collected, the booking is still " +
        "pending, and your seats stay held until the timer runs out.",
    });
  } catch (error) {
    paying = false;
    setPayButtons(false);

    if (error.code === "HOLD_EXPIRED") {
      renderExpired(currentBooking);
      return;
    }

    const alertEl = document.getElementById("pay-alert");
    showAlert(alertEl, error.message, "error");
  }
}

function wirePayment() {
  root.querySelectorAll("[data-pay]").forEach((button) => {
    button.addEventListener("click", () => pay(button.dataset.pay));
  });
}

async function load(flash = null) {
  try {
    const data = await api.booking(bookingId);
    const booking = data.booking;
    currentBooking = booking;

    if (booking.booking_status === "CONFIRMED") {
      renderTicket(booking);
    } else if (booking.booking_status === "PENDING") {
      if (holdExpiry && holdExpiry.getTime() <= Date.now()) {
        renderExpired(booking);
        return;
      }
      renderPending(booking, flash);
    } else {
      renderClosed(booking);
    }
  } catch (error) {
    renderError(root, error.message, () => load());
  }
}

async function main() {
  await initLayout({ active: "bookings" });

  if (!bookingId) {
    renderError(root, "No booking was specified.", null);
    return;
  }

  try {
    await requireUser(`checkout.html?booking=${bookingId}`);
  } catch {
    return;
  }

  holdExpiry = readHoldExpiry();
  await load();
}

main();
