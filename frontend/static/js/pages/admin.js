/* Admin console: reports, catalogue CRUD, seat setup and show scheduling. */

import { api } from "../api.js";
import { initLayout } from "../layout.js";
import { requireUser } from "../session.js";
import {
  escapeHtml,
  formatDateTime,
  hideAlert,
  money,
  showAlert,
  toast,
} from "../ui.js";

const TABS = ["overview", "movies", "theatres", "screens", "shows"];

let movies = [];
let theatres = [];
let screens = [];
let editingMovieId = null;
let referenceLoaded = false;

/* -------------------------------------------------------------------------
   Tabs
   ------------------------------------------------------------------------- */

function setTab(requested) {
  const tab = TABS.includes(requested) ? requested : "overview";

  document.querySelectorAll("[data-tab]").forEach((button) => {
    button.setAttribute("aria-selected", String(button.dataset.tab === tab));
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.hidden = panel.id !== `tab-${tab}`;
  });

  if (window.location.hash !== `#${tab}`) {
    window.history.replaceState({}, "", `#${tab}`);
  }

  const loaders = {
    overview: loadOverview,
    movies: loadMovies,
    theatres: loadTheatres,
    screens: loadScreens,
    shows: loadShows,
  };
  loaders[tab]();
}

/* -------------------------------------------------------------------------
   Overview / reports
   ------------------------------------------------------------------------- */

function reportRange() {
  return {
    from: document.getElementById("report-from").value,
    to: document.getElementById("report-to").value,
  };
}

function tableMessage(container, message) {
  container.innerHTML = `<p class="table-empty">${escapeHtml(message)}</p>`;
}

function renderStats(revenue) {
  document.getElementById("stat-gross").textContent = money(revenue.gross);
  document.getElementById("stat-gross-note").textContent =
    `${revenue.payment_count} successful payment${revenue.payment_count === 1 ? "" : "s"}` +
    (revenue.from || revenue.to ? " in range" : " all time");

  document.getElementById("stat-refunds").textContent = money(revenue.refunds);
  document.getElementById("stat-refund-note").textContent =
    `${revenue.refund_count} refund${revenue.refund_count === 1 ? "" : "s"} requested or approved`;

  document.getElementById("stat-net").textContent = money(revenue.net);
}

function renderOccupancy(shows) {
  const container = document.getElementById("occupancy-table");
  const countEl = document.getElementById("occupancy-count");
  countEl.textContent = `${shows.length} show${shows.length === 1 ? "" : "s"}`;

  if (!shows.length) {
    tableMessage(container, "No shows in this range.");
    return;
  }

  const rows = shows
    .map(
      (show) => `
      <tr>
        <td>${escapeHtml(show.movie_title)}</td>
        <td>${formatDateTime(show.show_start_at)}</td>
        <td>${escapeHtml(show.theatre_name)} · ${escapeHtml(show.screen_name)}</td>
        <td class="num">${show.booked_count}</td>
        <td class="num">${show.held_count}</td>
        <td class="num">${show.available_count}</td>
        <td class="num">${show.occupancy_pct === null ? "—" : `${Number(show.occupancy_pct).toFixed(1)}%`}</td>
      </tr>`
    )
    .join("");

  container.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Movie</th><th>Starts</th><th>Venue</th>
          <th class="num">Booked</th><th class="num">Held</th><th class="num">Available</th>
          <th class="num">Occupancy</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function renderTopMovies(list) {
  const container = document.getElementById("topmovies-table");

  if (!list.length) {
    tableMessage(container, "No confirmed bookings yet.");
    return;
  }

  const rows = list
    .map(
      (movie) => `
      <tr>
        <td>${escapeHtml(movie.title)}</td>
        <td class="num">${movie.booking_count}</td>
        <td class="num">${movie.seats_sold}</td>
        <td class="num">${money(movie.revenue)}</td>
      </tr>`
    )
    .join("");

  container.innerHTML = `
    <table>
      <thead>
        <tr><th>Movie</th><th class="num">Bookings</th><th class="num">Seats</th><th class="num">Revenue</th></tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}

async function loadOverview() {
  const alertEl = document.getElementById("report-alert");
  hideAlert(alertEl);

  const { from, to } = reportRange();
  tableMessage(document.getElementById("occupancy-table"), "Loading…");
  tableMessage(document.getElementById("topmovies-table"), "Loading…");

  try {
    const [revenue, occupancy, top] = await Promise.all([
      api.revenue(from, to),
      api.occupancy(from, to),
      api.topMovies(10),
    ]);
    renderStats(revenue);
    renderOccupancy(occupancy.shows);
    renderTopMovies(top.movies);
  } catch (error) {
    showAlert(alertEl, error.message);
    tableMessage(document.getElementById("occupancy-table"), "Could not load the report.");
    tableMessage(document.getElementById("topmovies-table"), "Could not load the report.");
  }
}

/* -------------------------------------------------------------------------
   Movies
   ------------------------------------------------------------------------- */

function movieRow(movie) {
  return `
    <tr>
      <td class="mono">${movie.id}</td>
      <td>${escapeHtml(movie.title)}</td>
      <td>${escapeHtml(movie.language)}</td>
      <td class="num">${movie.duration_minutes} min</td>
      <td><button class="btn btn--ghost btn--sm" type="button" data-edit-movie="${movie.id}">Edit</button></td>
    </tr>`;
}

function paintMoviesTable() {
  const container = document.getElementById("admin-movies-table");
  document.getElementById("admin-movie-count").textContent =
    `${movies.length} movie${movies.length === 1 ? "" : "s"}`;

  if (!movies.length) {
    tableMessage(container, "No movies yet. Add one above.");
    return;
  }

  container.innerHTML = `
    <table>
      <thead><tr><th>ID</th><th>Title</th><th>Language</th><th class="num">Duration</th><th></th></tr></thead>
      <tbody>${movies.map(movieRow).join("")}</tbody>
    </table>`;
}

function fillMovieSelect() {
  const select = document.getElementById("show-movie");
  if (!select) return;
  const current = select.value;
  select.innerHTML = movies.length
    ? movies.map((movie) => `<option value="${movie.id}">${escapeHtml(movie.title)}</option>`).join("")
    : '<option value="">No movies yet</option>';
  if (current && movies.some((movie) => String(movie.id) === current)) select.value = current;
}

function resetMovieForm() {
  editingMovieId = null;
  document.getElementById("movie-form").reset();
  document.getElementById("movie-language").value = "English";
  document.getElementById("movie-form-title").textContent = "Add a movie";
  document.getElementById("movie-submit").textContent = "Add movie";
  document.getElementById("movie-cancel").hidden = true;
  hideAlert(document.getElementById("movie-alert"));
}

function startMovieEdit(movieId) {
  const movie = movies.find((item) => item.id === movieId);
  if (!movie) return;

  editingMovieId = movieId;
  document.getElementById("movie-title").value = movie.title;
  document.getElementById("movie-language").value = movie.language;
  document.getElementById("movie-duration").value = movie.duration_minutes;
  document.getElementById("movie-form-title").textContent = `Edit movie #${movieId}`;
  document.getElementById("movie-submit").textContent = "Save changes";
  document.getElementById("movie-cancel").hidden = false;
  document.getElementById("tab-movies").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function submitMovie(event) {
  event.preventDefault();
  const alertEl = document.getElementById("movie-alert");
  hideAlert(alertEl);

  const title = document.getElementById("movie-title").value.trim();
  const language = document.getElementById("movie-language").value.trim() || "English";
  const duration = Number(document.getElementById("movie-duration").value);

  if (!title) {
    showAlert(alertEl, "Title is required.");
    return;
  }
  if (!Number.isInteger(duration) || duration <= 0) {
    showAlert(alertEl, "Duration must be a positive whole number of minutes.");
    return;
  }

  const button = document.getElementById("movie-submit");
  button.disabled = true;

  try {
    const body = { title, language, duration_minutes: duration };
    if (editingMovieId) {
      await api.updateMovie(editingMovieId, body);
      toast(`Movie #${editingMovieId} updated.`, "success");
    } else {
      await api.createMovie(body);
      toast("Movie added.", "success");
    }
    resetMovieForm();
    await loadMovies();
  } catch (error) {
    showAlert(alertEl, error.message);
  } finally {
    button.disabled = false;
  }
}

async function loadMovies() {
  const alertEl = document.getElementById("movie-alert");
  try {
    const data = await api.adminMovies();
    movies = data.movies;
    paintMoviesTable();
    fillMovieSelect();
  } catch (error) {
    showAlert(alertEl, error.message);
    tableMessage(document.getElementById("admin-movies-table"), "Could not load movies.");
  }
}

/* -------------------------------------------------------------------------
   Theatres
   ------------------------------------------------------------------------- */

function fillTheatreSelect() {
  const select = document.getElementById("screen-theatre");
  if (!select) return;
  const current = select.value;
  select.innerHTML = theatres.length
    ? theatres
        .map(
          (theatre) =>
            `<option value="${theatre.id}">${escapeHtml(theatre.name)} · ${escapeHtml(theatre.city)}</option>`
        )
        .join("")
    : '<option value="">No theatres yet</option>';
  if (current && theatres.some((theatre) => String(theatre.id) === current)) select.value = current;
}

async function loadTheatres() {
  const alertEl = document.getElementById("theatre-alert");
  try {
    const data = await api.theatres();
    theatres = data.theatres;
    document.getElementById("admin-theatre-count").textContent =
      `${theatres.length} theatre${theatres.length === 1 ? "" : "s"}`;

    const container = document.getElementById("admin-theatres-table");
    if (!theatres.length) {
      tableMessage(container, "No theatres yet. Add one above.");
    } else {
      container.innerHTML = `
        <table>
          <thead><tr><th>ID</th><th>Name</th><th>City</th><th class="num">Screens</th></tr></thead>
          <tbody>${theatres
            .map(
              (theatre) => `
              <tr>
                <td class="mono">${theatre.id}</td>
                <td>${escapeHtml(theatre.name)}</td>
                <td>${escapeHtml(theatre.city)}</td>
                <td class="num">${theatre.screen_count}</td>
              </tr>`
            )
            .join("")}</tbody>
        </table>`;
    }

    fillTheatreSelect();
  } catch (error) {
    showAlert(alertEl, error.message);
    tableMessage(document.getElementById("admin-theatres-table"), "Could not load theatres.");
  }
}

async function submitTheatre(event) {
  event.preventDefault();
  const alertEl = document.getElementById("theatre-alert");
  hideAlert(alertEl);

  const name = document.getElementById("theatre-name").value.trim();
  const city = document.getElementById("theatre-city").value.trim();

  if (!name || !city) {
    showAlert(alertEl, "Theatre name and city are both required.");
    return;
  }

  const button = document.getElementById("theatre-submit");
  button.disabled = true;

  try {
    await api.createTheatre({ name, city });
    document.getElementById("theatre-form").reset();
    toast("Theatre added.", "success");
    await loadTheatres();
  } catch (error) {
    showAlert(alertEl, error.message);
  } finally {
    button.disabled = false;
  }
}

/* -------------------------------------------------------------------------
   Screens and seats
   ------------------------------------------------------------------------- */

function fillScreenSelects() {
  const options = screens.length
    ? screens
        .map(
          (screen) =>
            `<option value="${screen.id}">${escapeHtml(screen.theatre_name)} — ${escapeHtml(screen.name)} (#${screen.id})</option>`
        )
        .join("")
    : '<option value="">No screens yet</option>';

  for (const id of ["show-screen", "seat-screen"]) {
    const select = document.getElementById(id);
    if (!select) continue;
    const current = select.value;
    select.innerHTML = options;
    if (current && screens.some((screen) => String(screen.id) === current)) select.value = current;
  }
}

async function loadScreens() {
  const alertEl = document.getElementById("screen-alert");
  try {
    const [screenData, theatreData] = await Promise.all([api.screens(), api.theatres()]);
    screens = screenData.screens;
    theatres = theatreData.theatres;

    document.getElementById("admin-screen-count").textContent =
      `${screens.length} screen${screens.length === 1 ? "" : "s"}`;

    const container = document.getElementById("admin-screens-table");
    if (!screens.length) {
      tableMessage(container, "No screens yet. Add one above.");
    } else {
      container.innerHTML = `
        <table>
          <thead>
            <tr><th>ID</th><th>Screen</th><th>Theatre</th><th class="num">Capacity</th><th class="num">Seats</th></tr>
          </thead>
          <tbody>${screens
            .map(
              (screen) => `
              <tr>
                <td class="mono">${screen.id}</td>
                <td>${escapeHtml(screen.name)}</td>
                <td>${escapeHtml(screen.theatre_name)} · ${escapeHtml(screen.theatre_city)}</td>
                <td class="num">${screen.capacity_total}</td>
                <td class="num">${screen.seat_count}</td>
              </tr>`
            )
            .join("")}</tbody>
        </table>`;
    }

    fillTheatreSelect();
    fillScreenSelects();
  } catch (error) {
    showAlert(alertEl, error.message);
    tableMessage(document.getElementById("admin-screens-table"), "Could not load screens.");
  }
}

async function submitScreen(event) {
  event.preventDefault();
  const alertEl = document.getElementById("screen-alert");
  hideAlert(alertEl);

  const theatreId = Number(document.getElementById("screen-theatre").value);
  const name = document.getElementById("screen-name").value.trim();
  const capacity = Number(document.getElementById("screen-capacity").value);

  if (!theatreId) {
    showAlert(alertEl, "Add a theatre first.");
    return;
  }
  if (!name) {
    showAlert(alertEl, "Screen name is required.");
    return;
  }
  if (!Number.isInteger(capacity) || capacity <= 0) {
    showAlert(alertEl, "Capacity must be a positive whole number.");
    return;
  }

  const button = document.getElementById("screen-submit");
  button.disabled = true;

  try {
    await api.createScreen({ theatre_id: theatreId, name, capacity_total: capacity });
    document.getElementById("screen-form").reset();
    toast("Screen added.", "success");
    await loadScreens();
  } catch (error) {
    showAlert(alertEl, error.message);
  } finally {
    button.disabled = false;
  }
}

function addSeatRow({ row_label = "A", count = 10, seat_type = "standard" } = {}) {
  const container = document.getElementById("seat-rows");
  const row = document.createElement("div");
  row.className = "seat-builder-row";
  row.innerHTML = `
    <div class="field">
      <label>Row</label>
      <input data-row-label type="text" maxlength="4" value="${escapeHtml(row_label)}" />
    </div>
    <div class="field">
      <label>Seats</label>
      <input data-row-count type="number" min="1" step="1" value="${Number(count)}" />
    </div>
    <div class="field">
      <label>Type</label>
      <select data-row-type>
        <option value="standard">standard</option>
        <option value="vip">vip</option>
      </select>
    </div>
    <button class="btn btn--ghost btn--sm" type="button" data-remove-row>Remove</button>`;

  row.querySelector("[data-row-type]").value = seat_type;
  row.querySelector("[data-remove-row]").addEventListener("click", () => row.remove());
  container.append(row);
}

async function submitSeats() {
  const alertEl = document.getElementById("seats-alert");
  hideAlert(alertEl);

  const screenId = Number(document.getElementById("seat-screen").value);
  const rows = [...document.querySelectorAll("#seat-rows .seat-builder-row")].map((row) => ({
    row_label: row.querySelector("[data-row-label]").value.trim().toUpperCase(),
    count: Number(row.querySelector("[data-row-count]").value),
    seat_type: row.querySelector("[data-row-type]").value,
  }));

  if (!screenId) {
    showAlert(alertEl, "Choose a screen first.");
    return;
  }
  if (!rows.length) {
    showAlert(alertEl, "Add at least one seat row.");
    return;
  }
  if (rows.some((row) => !row.row_label || !Number.isInteger(row.count) || row.count <= 0)) {
    showAlert(alertEl, "Every row needs a label and a positive whole number of seats.");
    return;
  }

  const button = document.getElementById("seat-submit");
  button.disabled = true;

  try {
    const data = await api.createScreenSeats(screenId, rows);
    toast(`Created ${data.created} seat${data.created === 1 ? "" : "s"}.`, "success");
    await loadScreens();
  } catch (error) {
    showAlert(alertEl, error.message);
  } finally {
    button.disabled = false;
  }
}

/* -------------------------------------------------------------------------
   Shows
   ------------------------------------------------------------------------- */

async function ensureReference() {
  if (referenceLoaded) return;
  const [movieData, screenData] = await Promise.all([api.adminMovies(), api.screens()]);
  movies = movieData.movies;
  screens = screenData.screens;
  fillMovieSelect();
  fillScreenSelects();
  referenceLoaded = true;
}

function renderShowsTable(shows) {
  const container = document.getElementById("admin-shows-table");
  document.getElementById("admin-show-count").textContent =
    `${shows.length} show${shows.length === 1 ? "" : "s"}`;

  if (!shows.length) {
    tableMessage(container, "No shows scheduled for this filter.");
    return;
  }

  container.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>ID</th><th>Movie</th><th>Venue</th><th>Start</th>
          <th class="num">Price</th><th class="num">Booked</th><th class="num">Held</th><th class="num">Available</th>
        </tr>
      </thead>
      <tbody>${shows
        .map(
          (show) => `
          <tr>
            <td class="mono">${show.show_id}</td>
            <td>${escapeHtml(show.movie_title)}</td>
            <td>${escapeHtml(show.theatre_name)} · ${escapeHtml(show.screen_name)}</td>
            <td>${formatDateTime(show.show_start_at)}</td>
            <td class="num">${money(show.show_base_price)}</td>
            <td class="num">${show.booked_count}</td>
            <td class="num">${show.held_count}</td>
            <td class="num">${show.available_count}</td>
          </tr>`
        )
        .join("")}</tbody>
    </table>`;
}

async function loadShows() {
  const alertEl = document.getElementById("show-alert");
  hideAlert(alertEl);

  try {
    await ensureReference();
    const date = document.getElementById("shows-date").value;
    const data = await api.adminShows(date);
    renderShowsTable(data.shows);
  } catch (error) {
    showAlert(alertEl, error.message);
    tableMessage(document.getElementById("admin-shows-table"), "Could not load shows.");
  }
}

async function submitShow(event) {
  event.preventDefault();
  const alertEl = document.getElementById("show-alert");
  hideAlert(alertEl);

  const movieId = Number(document.getElementById("show-movie").value);
  const screenId = Number(document.getElementById("show-screen").value);
  const start = document.getElementById("show-start").value;
  const end = document.getElementById("show-end").value;
  const price = document.getElementById("show-price").value;

  if (!movieId) {
    showAlert(alertEl, "Add a movie first.");
    return;
  }
  if (!screenId) {
    showAlert(alertEl, "Add a screen first.");
    return;
  }
  if (!start || !end) {
    showAlert(alertEl, "Both start and end times are required.");
    return;
  }
  if (new Date(end) <= new Date(start)) {
    showAlert(alertEl, "End time must be after the start time.");
    return;
  }
  if (price === "" || Number(price) < 0) {
    showAlert(alertEl, "Base price must be zero or more.");
    return;
  }

  const button = document.getElementById("show-submit");
  button.disabled = true;

  try {
    await api.createShow({
      movie_id: movieId,
      screen_id: screenId,
      start_at: new Date(start).toISOString(),
      end_at: new Date(end).toISOString(),
      base_price: String(price),
    });
    document.getElementById("show-form").reset();
    toast("Show scheduled and seat rows created.", "success");
    await loadShows();
  } catch (error) {
    showAlert(alertEl, error.message);
  } finally {
    button.disabled = false;
  }
}

/* -------------------------------------------------------------------------
   Wiring
   ------------------------------------------------------------------------- */

function wire() {
  document.querySelectorAll("[data-tab]").forEach((button) => {
    button.addEventListener("click", () => setTab(button.dataset.tab));
  });

  document.getElementById("report-form").addEventListener("submit", (event) => {
    event.preventDefault();
    loadOverview();
  });
  document.getElementById("report-reset").addEventListener("click", () => {
    document.getElementById("report-from").value = "";
    document.getElementById("report-to").value = "";
    loadOverview();
  });

  document.getElementById("movie-form").addEventListener("submit", submitMovie);
  document.getElementById("movie-cancel").addEventListener("click", resetMovieForm);
  document.getElementById("admin-movies-table").addEventListener("click", (event) => {
    const button = event.target.closest("[data-edit-movie]");
    if (button) startMovieEdit(Number(button.dataset.editMovie));
  });

  document.getElementById("theatre-form").addEventListener("submit", submitTheatre);
  document.getElementById("screen-form").addEventListener("submit", submitScreen);
  document.getElementById("seat-add-row").addEventListener("click", () => addSeatRow());
  document.getElementById("seat-submit").addEventListener("click", submitSeats);

  document.getElementById("show-form").addEventListener("submit", submitShow);
  document.getElementById("shows-filter").addEventListener("submit", (event) => {
    event.preventDefault();
    loadShows();
  });
  document.getElementById("shows-clear").addEventListener("click", () => {
    document.getElementById("shows-date").value = "";
    loadShows();
  });
}

async function main() {
  await initLayout({ active: "admin" });

  let user = null;
  try {
    user = await requireUser("admin/index.html");
  } catch {
    return;
  }

  if (user.role !== "admin") {
    document.getElementById("admin-denied").hidden = false;
    document.getElementById("admin-denied").innerHTML = `
      <h3>Administrator access required</h3>
      <p>You are signed in as ${escapeHtml(user.name)}, who is not an administrator.
         Customer accounts cannot use this console; the API enforces the same rule.</p>
      <a class="btn btn--secondary" href="../index.html">Back to movies</a>`;
    document.getElementById("admin-user").textContent = `${user.name} · ${user.email}`;
    return;
  }

  document.getElementById("admin-user").textContent = `${user.name} · ${user.email}`;
  document.getElementById("admin-app").hidden = false;

  wire();
  addSeatRow({});
  setTab(window.location.hash.replace("#", ""));

  window.addEventListener("hashchange", () => {
    setTab(window.location.hash.replace("#", ""));
  });
}

main();
