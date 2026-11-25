/* Registration page. */

import { api } from "../api.js";
import { BASE } from "../config.js";
import { initLayout } from "../layout.js";
import { loadUser, safeNext } from "../session.js";
import { hideAlert, param, showAlert } from "../ui.js";

const form = document.getElementById("auth-form");
const alertEl = document.getElementById("auth-alert");
const submit = document.getElementById("auth-submit");
const next = safeNext(param("next"), "index.html");

function destination() {
  return `${BASE}${next}`;
}

async function onSubmit(event) {
  event.preventDefault();
  hideAlert(alertEl);

  const data = new FormData(form);
  const name = String(data.get("name") || "").trim();
  const email = String(data.get("email") || "").trim();
  const password = String(data.get("password") || "");
  const confirm = String(data.get("confirm") || "");

  if (!name || !email || !password) {
    showAlert(alertEl, "Name, email and password are all required.");
    return;
  }
  if (password.length < 8) {
    showAlert(alertEl, "Password must be at least 8 characters.");
    return;
  }
  if (password !== confirm) {
    showAlert(alertEl, "The two passwords do not match.");
    return;
  }

  submit.disabled = true;
  submit.textContent = "Creating account…";

  try {
    await api.register(name, email, password);
    window.location.href = destination();
  } catch (error) {
    showAlert(alertEl, error.message);
    submit.disabled = false;
    submit.textContent = "Create account";
  }
}

async function main() {
  await initLayout();

  let user = null;
  try {
    user = await loadUser();
  } catch {
    user = null; // API unreachable: keep the form usable so the error is visible on submit.
  }
  if (user) {
    window.location.replace(destination());
    return;
  }

  form.addEventListener("submit", onSubmit);
}

main();
