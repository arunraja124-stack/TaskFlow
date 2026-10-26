const $ = (id) => document.getElementById(id);
const api = async (url, options = {}) => {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (["POST", "PUT", "PATCH", "DELETE"].includes(options.method)) {
    const csrf = await fetch("/api/auth/csrf").then((response) => response.json());
    headers["X-CSRF-Token"] = csrf.data.csrf_token;
  }
  const response = await fetch(`/api${url}`, { ...options, headers });
  const body = await response.json().catch(() => ({}));
  if (response.status === 401) { window.location.href = "/login.html"; throw new Error("Authentication required."); }
  if (!response.ok) throw new Error(body.error?.message || "Request failed.");
  return body;
};
const setStatus = (id, message, error = false) => { const element = $(id); element.textContent = message; element.classList.toggle("error", error); };
const applyTheme = (dark) => { document.body.classList.toggle("dark-mode", dark); localStorage.setItem("taskflow-theme", dark ? "dark" : "light"); $("themeLabel").textContent = dark ? "Dark mode" : "Light mode"; };
const submitForm = async (event, endpoint, payload, statusId, buttonId, successMessage) => {
  event.preventDefault();
  const button = $(buttonId);
  button.disabled = true;
  setStatus(statusId, "Saving...");
  try { await api(endpoint, { method: "PUT", body: JSON.stringify(payload) }); setStatus(statusId, successMessage); }
  catch (error) { setStatus(statusId, error.message, true); }
  finally { button.disabled = false; }
};
document.addEventListener("DOMContentLoaded", async () => {
  applyTheme(localStorage.getItem("taskflow-theme") === "dark");
  $("themeButton").addEventListener("click", () => applyTheme(!document.body.classList.contains("dark-mode")));
  $("appearanceToggle").addEventListener("click", () => applyTheme(!document.body.classList.contains("dark-mode")));
  $("mobileMenuButton").addEventListener("click", () => document.body.classList.toggle("sidebar-open"));
  $("logoutButton").addEventListener("click", async () => { await api("/auth/logout", { method: "POST" }); window.location.href = "/login.html"; });
  try {
    const [me, preferences] = await Promise.all([api("/auth/me"), api("/auth/preferences")]);
    const user = me.data.user;
    const initial = user.name.charAt(0).toUpperCase();
    $("profileName").value = user.name; $("profileEmail").value = user.email;
    $("userName").textContent = user.name; $("sidebarUserName").textContent = user.name; $("sidebarAvatar").textContent = initial;
    document.querySelectorAll(".avatar-small").forEach((avatar) => { avatar.textContent = initial; });
    const values = preferences.data.preferences;
    $("deadlineReminders").checked = Boolean(values.deadline_reminders); $("overdueAlerts").checked = Boolean(values.overdue_alerts);
    $("defaultView").value = values.default_view; $("defaultPriority").value = values.default_priority;
  } catch (error) { $("settingsAlert").innerHTML = `<div class="alert alert-danger">${error.message}</div>`; return; }
  $("profileForm").addEventListener("submit", (event) => submitForm(event, "/auth/profile", { name: $("profileName").value.trim(), email: $("profileEmail").value.trim() }, "profileStatus", "profileSave", "Profile saved."));
  $("preferencesForm").addEventListener("submit", (event) => submitForm(event, "/auth/preferences", { default_view: $("defaultView").value, default_priority: $("defaultPriority").value, deadline_reminders: $("deadlineReminders").checked, overdue_alerts: $("overdueAlerts").checked }, "preferencesStatus", "preferencesSave", "Preferences saved."));
  $("notificationsForm").addEventListener("submit", (event) => submitForm(event, "/auth/preferences", { default_view: $("defaultView").value, default_priority: $("defaultPriority").value, deadline_reminders: $("deadlineReminders").checked, overdue_alerts: $("overdueAlerts").checked }, "notificationsStatus", "notificationsSave", "Notification settings saved."));
  $("passwordForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    if ($("newPassword").value !== $("passwordConfirmation").value) { setStatus("passwordStatus", "Passwords do not match.", true); return; }
    const button = $("passwordSave"); button.disabled = true; setStatus("passwordStatus", "Updating...");
    try { await api("/auth/password", { method: "POST", body: JSON.stringify({ current_password: $("currentPassword").value, new_password: $("newPassword").value, password_confirmation: $("passwordConfirmation").value }) }); $("passwordForm").reset(); setStatus("passwordStatus", "Password updated."); }
    catch (error) { setStatus("passwordStatus", error.message, true); } finally { button.disabled = false; }
  });
});
