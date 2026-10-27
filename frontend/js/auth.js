const authApi = async (url, options = {}) => {
  const csrf = await fetch("/api/auth/csrf").then((response) => response.json());
  const response = await fetch(url, { headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf.data.csrf_token }, ...options });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error?.message || "Request failed.");
  return body;
};
const authAlert = (message) => { document.getElementById("alertArea").innerHTML = `<div class="alert alert-danger" role="alert">${message}</div>`; };
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("loginForm") || document.getElementById("registerForm");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.checkValidity()) { form.classList.add("was-validated"); return; }
    const isLogin = form.id === "loginForm";
    const emailValue = document.getElementById("email").value;
    const passwordValue = document.getElementById("password").value;
    const payload = isLogin ? { email: emailValue, password: passwordValue } : { name: document.getElementById("name").value.trim(), email: emailValue, password: passwordValue, password_confirmation: document.getElementById("passwordConfirmation").value };
    const button = document.getElementById("submitButton"); button.disabled = true;
    try { await authApi(isLogin ? "/api/auth/login" : "/api/auth/register", { method: "POST", body: JSON.stringify(payload) }); window.location.href = "/"; }
    catch (error) { authAlert(error.message); button.disabled = false; }
  });
});
