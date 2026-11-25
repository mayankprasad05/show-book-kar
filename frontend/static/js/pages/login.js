/* Sign-in page. */

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
  const email = String(data.get("email") || "").trim();
  const password = String(data.get("password") || "");

  if (!email || !password) {
    showAlert(alertEl, "Enter your email and password.");
    return;
  }

  submit.disabled = true;
  submit.textContent = "Signing in…";

  try {
    await api.login(email, password);
    window.location.href = destination();
  } catch (error) {
    showAlert(alertEl, error.message);
    submit.disabled = false;
    submit.textContent = "Sign in";
    document.getElementById("password").select();
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
