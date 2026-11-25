/* Thin client for the Flask JSON API.
 *
 * Every call sends the session cookie (`credentials: "include"`) and every
 * failure becomes an ApiError carrying the server's {error, message} envelope.
 */

import { API_BASE } from "./config.js";

export class ApiError extends Error {
  constructor(status, code, message, payload = null) {
    super(message || "Something went wrong.");
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.payload = payload;
  }

  get isAuth() {
    return this.status === 401;
  }

  get isForbidden() {
    return this.status === 403;
  }

  get isNetwork() {
    return this.status === 0;
  }
}

function buildUrl(path, query) {
  const url = new URL(API_BASE + path);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, value);
      }
    }
  }
  return url.toString();
}

export async function request(path, { method = "GET", body, query, signal } = {}) {
  let response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      credentials: "include",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError(
      0,
      "NETWORK_ERROR",
      `Could not reach the API at ${API_BASE}. Check that PostgreSQL and the Flask server are running.`
    );
  }

  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    throw new ApiError(
      response.status,
      data?.error || "HTTP_ERROR",
      data?.message || `Request failed (${response.status}).`,
      data
    );
  }

  return data;
}

export const api = {
  // Session
  me: () => request("/auth/me"),
  login: (email, password) => request("/auth/login", { method: "POST", body: { email, password } }),
  register: (name, email, password) =>
    request("/auth/register", { method: "POST", body: { name, email, password } }),
  logout: () => request("/auth/logout", { method: "POST" }),

  // Catalogue
  movies: () => request("/movies"),
  movie: (movieId, date) => request(`/movies/${movieId}`, { query: { date } }),
  show: (showId) => request(`/shows/${showId}`),
  seats: (showId) => request(`/shows/${showId}/seats`),

  // Bookings
  bookings: () => request("/bookings"),
  booking: (bookingId) => request(`/bookings/${bookingId}`),
  hold: (showId, seatIds) =>
    request("/bookings", { method: "POST", body: { show_id: showId, seat_ids: seatIds } }),
  pay: (bookingId, simulate) =>
    request(`/bookings/${bookingId}/pay`, { method: "POST", body: { simulate } }),
  cancel: (bookingId) => request(`/bookings/${bookingId}/cancel`, { method: "POST" }),

  // Admin
  adminMovies: () => request("/admin/movies"),
  createMovie: (body) => request("/admin/movies", { method: "POST", body }),
  updateMovie: (movieId, body) => request(`/admin/movies/${movieId}`, { method: "PATCH", body }),
  theatres: () => request("/admin/theatres"),
  createTheatre: (body) => request("/admin/theatres", { method: "POST", body }),
  screens: () => request("/admin/screens"),
  createScreen: (body) => request("/admin/screens", { method: "POST", body }),
  createScreenSeats: (screenId, rows) =>
    request(`/admin/screens/${screenId}/seats`, { method: "POST", body: { rows } }),
  adminShows: (date) => request("/admin/shows", { query: { date } }),
  createShow: (body) => request("/admin/shows", { method: "POST", body }),

  // Reports
  revenue: (from, to) => request("/admin/reports/revenue", { query: { from, to } }),
  occupancy: (from, to) => request("/admin/reports/occupancy", { query: { from, to } }),
  topMovies: (limit = 10) => request("/admin/reports/top-movies", { query: { limit } }),
};
