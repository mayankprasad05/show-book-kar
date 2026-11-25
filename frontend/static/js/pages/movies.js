/* Movie catalogue: the landing page. */

import { api } from "../api.js";
import { initLayout } from "../layout.js";
import {
  escapeHtml,
  gradientFor,
  initials,
  renderEmpty,
  renderError,
  skeletonGrid,
} from "../ui.js";

const grid = document.getElementById("movie-grid");
const countEl = document.getElementById("movie-count");

function movieCard(movie) {
  return `
    <a class="movie-card" href="movie.html?id=${movie.id}"
       aria-label="${escapeHtml(movie.title)}, ${escapeHtml(movie.language)}, showtimes">
      <div class="movie-poster" style="${gradientFor(movie.id)}">
        <span class="movie-initials" aria-hidden="true">${escapeHtml(initials(movie.title))}</span>
        <span class="movie-poster-badge">${Number(movie.duration_minutes)} min</span>
      </div>
      <div class="movie-body">
        <h3>${escapeHtml(movie.title)}</h3>
        <p class="muted small">${escapeHtml(movie.language)}</p>
        <span class="movie-cta">Showtimes &rarr;</span>
      </div>
    </a>`;
}

async function loadMovies() {
  skeletonGrid(grid, 6);
  countEl.textContent = "";
  try {
    const { movies } = await api.movies();
    countEl.textContent = `${movies.length} film${movies.length === 1 ? "" : "s"} in the catalogue`;

    if (!movies.length) {
      renderEmpty(
        grid,
        "No movies yet",
        "The catalogue is empty. An administrator can add a movie from the admin panel."
      );
      return;
    }
    grid.innerHTML = movies.map(movieCard).join("");
  } catch (error) {
    renderError(grid, error.message, loadMovies);
  }
}

async function main() {
  await initLayout({ active: "movies" });
  await loadMovies();
}

main();
