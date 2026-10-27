const $ = (id) => document.getElementById(id);
const api = async (url, options = {}) => {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (options.method) { const csrf = await fetch("/api/auth/csrf").then((r) => r.json()); headers["X-CSRF-Token"] = csrf.data.csrf_token; }
  const response = await fetch(`/api${url}`, { ...options, headers });
  const body = await response.json().catch(() => ({}));
  if (response.status === 401) { window.location.href = "/login.html"; throw new Error("Authentication required."); }
  if (!response.ok) throw new Error(body.error?.message || "Request failed.");
  return body;
};
const alertUser = (message, type = "success") => { $("alertArea").innerHTML = `<div class="alert alert-${type}">${message}</div>`; };
const formatTime = (value) => value ? new Date(value).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "—";
function renderStatus(data) {
  $("businessDate").textContent = data.business_date;
  const record = data.record;
  $("statusText").textContent = record ? (record.status === "checked_out" ? "Checked out" : "Checked in") : "Not checked in";
  $("timeText").textContent = record ? `Check in: ${formatTime(record.check_in_at)} · Check out: ${formatTime(record.check_out_at)}` : "No attendance record yet.";
  $("checkInButton").disabled = Boolean(record);
  $("checkOutButton").disabled = !record || record.status === "checked_out";
}
async function load() { try { const [status, history] = await Promise.all([api("/attendance/status"), api("/attendance/history")]); renderStatus(status.data); const rows = history.data.records; $("historyState").hidden = rows.length > 0; $("historyState").textContent = rows.length ? "" : "No attendance history yet."; $("historyTable").hidden = !rows.length; $("historyTable").querySelector("tbody").innerHTML = rows.map((row) => `<tr><td>${row.attendance_date}</td><td>${formatTime(row.check_in_at)}</td><td>${formatTime(row.check_out_at)}</td><td>${row.status === "checked_out" ? "Checked out" : "Checked in"}</td></tr>`).join(""); } catch (error) { alertUser(error.message, "danger"); } }
async function action(path, button) { button.disabled = true; try { const result = await api(path, { method: "POST" }); alertUser(result.message); await load(); } catch (error) { alertUser(error.message, "danger"); await load(); } }
document.addEventListener("DOMContentLoaded", () => { load(); $("checkInButton").addEventListener("click", () => action("/attendance/check-in", $("checkInButton"))); $("checkOutButton").addEventListener("click", () => action("/attendance/check-out", $("checkOutButton"))); $("logoutButton").addEventListener("click", async () => { await api("/auth/logout", { method: "POST" }); window.location.href = "/login.html"; }); });
