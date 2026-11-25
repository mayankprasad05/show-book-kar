/* Movie detail: synopsis fields, date filter and showtimes grouped by venue. */

import { api } from "../api.js";
import { initLayout } from "../layout.js";
import {
  escapeHtml,
  formatTime,
  gradientFor,
  initials,
  intParam,
  money,
  param,
  renderError,
} from "../ui.js";

const root = document.getElementById("movie-root");
const movieId = intParam("id");
let date = param("date") || "";

function syncUrl() {
  const url = new URL(window.location.href);
  if (date) url.searchParams.set("date", date);
  else url.searchParams.delete("date");
  window.history.replaceState({}, "", url);
}

function showChip(show) {
  return `
    <a class="show-chip" href="seats.html?show=${show.id}"
       aria-label="${formatTime(show.start_at)} at ${escapeHtml(show.theatre_name)}, ${escapeHtml(show.screen_name)}">
      <strong>${formatTime(show.start_at)}</strong>
      <span>${escapeHtml(show.screen_name)}</span>
      <span class="price">${money(show.base_price)}</span>
    </a>`;
}

function showsSection(shows) {
  if (!shows.length) {
    const filtered = Boolean(date);
    return `
      <div class="state">
        <h3>${filtered ? "No shows on this date" : "No shows scheduled"}</h3>
        <p>${filtered
          ? "Try another date, or clear the filter to see every upcoming show."
          : "This movie has no showtimes yet. An administrator can schedule one from the admin panel."}</p>
        ${filtered ? '<button class="btn btn--secondary" type="button" id="empty-clear">Clear date filter</button>' : ""}
      </div>`;
  }

  const venues = new Map();
  for (const show of shows) {
    const key = show.theatre_id;
    if (!venues.has(key)) {
      venues.set(key, {
        name: show.theatre_name,
        city: show.city,
        shows: [],
      });
    }
    venues.get(key).shows.push(show);
  }

  return [...venues.values()]
    .map(
      (venue) => `
      <div class="venue">
        <div class="venue-head">
          <h3>${escapeHtml(venue.name)}</h3>
          <span class="muted">${escapeHtml(venue.city)} &middot; ${venue.shows.length} show${venue.shows.length === 1 ? "" : "s"}</span>
        </div>
        <div class="show-grid">${venue.shows.map(showChip).join("")}</div>
      </div>`
    )
    .join("");
}

function render(movie, shows) {
  document.title = `${movie.title} · Show-book-kar`;
  root.innerHTML = `
    <section class="movie-hero">
      <div class="movie-poster" style="${gradientFor(movie.id)}" aria-hidden="true">
        <span class="movie-initials">${escapeHtml(initials(movie.title))}</span>
      </div>
      <div class="movie-hero-body">
        <p class="eyebrow">Now showing</p>
        <h1>${escapeHtml(movie.title)}</h1>
        <div class="meta-row">
          <span class="meta-chip">${escapeHtml(movie.language)}</span>
          <span class="meta-chip">${Number(movie.duration_minutes)} minutes</span>
          <span class="meta-chip">${shows.length} show${shows.length === 1 ? "" : "s"} listed</span>
        </div>
        <div class="filter-row">
          <div class="field">
            <label for="date-filter">Filter by date</label>
            <input id="date-filter" type="date" value="${escapeHtml(date)}" />
          </div>
          <button id="date-clear" class="btn btn--ghost" type="button">Clear</button>
          <span class="note">Showtimes are shown in your local time zone.</span>
        </div>
      </div>
    </section>

    <section class="section" aria-labelledby="shows-heading">
      <div class="section-head">
        <h2 id="shows-heading">Showtimes</h2>
        <span class="muted small">${date ? `Filtered to ${escapeHtml(date)}` : "All upcoming shows"}</span>
      </div>
      <div id="shows-root">${showsSection(shows)}</div>
    </section>`;

  wireFilter();
}

function wireFilter() {
  const input = document.getElementById("date-filter");
  input?.addEventListener("change", () => {
    date = input.value;
    syncUrl();
    load();
  });

  document.getElementById("date-clear")?.addEventListener("click", () => {
    date = "";
    syncUrl();
    load();
  });

  document.getElementById("empty-clear")?.addEventListener("click", () => {
    date = "";
    syncUrl();
    load();
  });
}

async function load({ first = false } = {}) {
  if (!movieId) {
    renderError(root, "No movie was specified. Open a movie from the catalogue.");
    return;
  }

  if (first) {
    root.innerHTML = '<div class="state"><p>Loading movie&hellip;</p></div>';
  } else {
    const showsRoot = document.getElementById("shows-root");
    if (showsRoot) showsRoot.innerHTML = '<div class="state"><p>Loading showtimes&hellip;</p></div>';
  }

  try {
    const data = await api.movie(movieId, date);
    render(data.movie, data.shows);
  } catch (error) {
    renderError(root, error.message, () => load({ first: true }));
  }
}

async function main() {
  await initLayout({ active: "movies" });
  await load({ first: true });
}

main();
