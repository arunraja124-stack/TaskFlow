const state = { tasks: [], csrf: "", calendarTasks: [], activity: [], calendarDate: new Date(), statusUpdate: null };
const $ = (id) => document.getElementById(id);
const api = async (url, options = {}) => {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (["POST", "PUT", "PATCH", "DELETE"].includes(options.method)) { const csrf = await fetch("/api/auth/csrf").then((response) => response.json()); headers["X-CSRF-Token"] = csrf.data.csrf_token; }
  const response = await fetch(`/api${url}`, { ...options, headers });
  const body = await response.json().catch(() => ({}));
  if (response.status === 401) { window.location.href = "/login.html"; throw new Error("Authentication required."); }
  if (!response.ok) throw new Error(body.error?.message || "Request failed.");
  return body;
};
const showAlert = (message, type = "success") => { $("alertArea").innerHTML = `<div class="alert alert-${type} alert-dismissible fade show" role="alert">${message}<button class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>`; };
const setBoardStatus = (message, type = "") => {
  const status = $("boardStatus");
  status.textContent = message;
  status.className = `board-status${type ? ` ${type}` : ""}`;
};
const isOverdue = (task) => task.due_date && task.status !== "completed" && new Date(`${task.due_date}T23:59:59`) < new Date();
const taskCard = (task) => {
  const due = task.due_date ? `<span class="${isOverdue(task) ? "overdue" : "due-label"}">${isOverdue(task) ? "Overdue · " : "Due · "}${task.due_date}</span>` : "";
  const busy = state.statusUpdate === task.id;
  return `<article class="task-card priority-${task.priority}${busy ? " is-updating" : ""}" draggable="${!busy}" data-id="${task.id}" tabindex="0" aria-busy="${busy}"><h3>${escapeHtml(task.title)}</h3><p>${escapeHtml(task.description || "No description")}</p><div class="task-meta"><span class="priority-label">${task.priority}</span>${due}</div><div class="task-actions"><button class="btn btn-outline-secondary edit-task" data-id="${task.id}"${busy ? " disabled" : ""}>Edit</button><button class="btn btn-outline-danger delete-task" data-id="${task.id}"${busy ? " disabled" : ""}>Delete</button><select class="form-select form-select-sm status-select" data-id="${task.id}" aria-label="Change status for ${escapeHtml(task.title)}"${busy ? " disabled" : ""}><option value="todo" ${task.status === "todo" ? "selected" : ""}>To do</option><option value="in_progress" ${task.status === "in_progress" ? "selected" : ""}>In progress</option><option value="completed" ${task.status === "completed" ? "selected" : ""}>Completed</option></select></div></article>`;
};
const escapeHtml = (value) => { const div = document.createElement("div"); div.textContent = value; return div.innerHTML; };
function render() {
  const counts = { todo: 0, in_progress: 0, completed: 0 };
  document.querySelectorAll(".task-list").forEach((list) => { list.innerHTML = ""; });
  $("upcomingTasks").innerHTML = "";
  state.tasks.forEach((task) => { counts[task.status]++; $(`${task.status === "in_progress" ? "progress" : task.status}List`).insertAdjacentHTML("beforeend", taskCard(task)); });
  const upcoming = [...state.tasks].filter((task) => task.status !== "completed").slice(0, 4);
  $("upcomingTasks").innerHTML = upcoming.length ? upcoming.map(taskCard).join("") : '<div class="empty-state">No upcoming tasks. Create one to get started.</div>';
  ["todo", "progress", "completed"].forEach((name) => { const key = name === "progress" ? "in_progress" : name; $(`${name}Badge`).textContent = counts[key]; const list = $(`${name}List`); if (!list.children.length) list.innerHTML = '<div class="empty-state">No tasks here yet.</div>'; });
  const total = state.tasks.length, completed = counts.completed, rate = total ? Math.round((completed / total) * 100) : 0;
  $("totalCount").textContent = total; $("todoCount").textContent = counts.todo; $("progressCount").textContent = counts.in_progress; $("completedCount").textContent = completed; $("completionRate").textContent = `${rate}%`; $("completionBar").style.width = `${rate}%`; $("taskSummary").textContent = `${total} task${total === 1 ? "" : "s"}`;
  $("focusProgressBar").style.width = `${rate}%`;
  renderTodayTasks();
  bindTaskEvents();
}
async function loadTasks() {
  setBoardStatus("Loading tasks…", "loading");
  try {
    const params = new URLSearchParams({ search: $("search").value, status: $("statusFilter").value, priority: $("priorityFilter").value, due_date: $("dueDateFilter").value, sort: $("sort").value });
    const result = await api(`/tasks?${params}`);
    state.tasks = result.data.tasks;
    render();
    setBoardStatus(`${result.data.count} task${result.data.count === 1 ? "" : "s"} loaded.`);
  } catch (error) {
    setBoardStatus("Unable to load tasks.", "error");
    showAlert(error.message, "danger");
  }
}
async function downloadReport(path, button, successMessage) {
  const originalLabel = button.textContent;
  button.disabled = true;
  button.textContent = "Generating…";
  try {
    const params = new URLSearchParams({ search: $("search").value, status: $("statusFilter").value, priority: $("priorityFilter").value, due_date: $("dueDateFilter").value, sort: $("sort").value });
    const response = await fetch(`/api${path}?${params}`, { credentials: "same-origin" });
    if (response.status === 401) {
      window.location.href = "/login.html";
      return;
    }
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.error?.message || "Unable to generate report.");
    }
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const filename = disposition.match(/filename="?([^"]+)"?/)?.[1] || "taskflow-report";
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    const note = response.headers.get("X-TaskFlow-Report-Note");
    showAlert(note ? `${successMessage} ${note}` : successMessage, note ? "warning" : "success");
  } catch (error) {
    showAlert(error.message, "danger");
  } finally {
    button.disabled = false;
    button.textContent = originalLabel;
  }
}
async function loadAnalytics() { try { const result = await api("/analytics"); const data = result.data; $("overdueCount").textContent = data.overdue; $("weeklyCount").textContent = data.weekly_completed; } catch (error) { showAlert(error.message, "danger"); } }
async function loadProductivity() {
  try {
    const [calendar, activity, reminders] = await Promise.all([api("/calendar"), api("/activity"), api("/reminders")]);
    const reminderItems = reminders.data.reminders;
    state.calendarTasks = calendar.data.tasks;
    state.activity = activity.data.activity;
    $("notificationBadge").textContent = reminderItems.length;
    renderMiniCalendar();
    renderTodayTasks();
    renderWeeklyChart();
    $("activityList").innerHTML = state.activity.length ? state.activity.slice(0, 8).map((item) => `<div class="activity-item"><strong>${escapeHtml(item.action.replace("_", " "))}</strong><span>${escapeHtml(item.details || "Task update")} · ${escapeHtml(item.created_at)}</span></div>`).join("") : '<div class="empty-state">No activity yet.</div>';
  } catch (error) { showAlert(error.message, "danger"); }
}
function renderMiniCalendar() {
  const date = state.calendarDate;
  const year = date.getFullYear();
  const month = date.getMonth();
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const previousMonthDays = new Date(year, month, 0).getDate();
  const taskDates = new Set(state.calendarTasks.map((task) => task.due_date));
  const today = new Date();
  const todayKey = today.toISOString().slice(0, 10);
  $("calendarMonthLabel").textContent = date.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  const weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => `<span>${day}</span>`).join("");
  const cells = [];
  for (let index = firstDay - 1; index >= 0; index -= 1) cells.push(`<span class="calendar-day muted">${previousMonthDays - index}</span>`);
  for (let day = 1; day <= daysInMonth; day += 1) {
    const key = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    const classes = ["calendar-day"];
    if (key === todayKey) classes.push("today");
    if (taskDates.has(key)) classes.push("has-task");
    cells.push(`<span class="${classes.join(" ")}">${day}</span>`);
  }
  while (cells.length < 42) cells.push(`<span class="calendar-day muted">${cells.length - daysInMonth - firstDay + 1}</span>`);
  $("miniCalendar").innerHTML = `<div class="calendar-week">${weekdays}</div><div class="calendar-days">${cells.slice(0, 42).join("")}</div>`;
}
function renderTodayTasks() {
  const todayKey = new Date().toISOString().slice(0, 10);
  const todayTasks = state.tasks.filter((task) => task.due_date === todayKey);
  $("todayTaskCount").textContent = todayTasks.length;
  $("todayTasks").innerHTML = todayTasks.length ? todayTasks.map((task) => {
    const progress = task.status === "completed" ? 100 : task.status === "in_progress" ? 50 : 0;
    return `<article class="today-task"><strong>${escapeHtml(task.title)}</strong><p>${escapeHtml(task.description || "No description")}</p><div class="progress"><div class="progress-bar" style="width:${progress}%"></div></div><div class="today-task-meta"><span>${progress}% complete</span><a class="open-task edit-task" href="#taskModal" data-id="${task.id}" data-bs-toggle="modal">Open task</a></div></article>`;
  }).join("") : '<div class="empty-state">No tasks due today.</div>';
  document.querySelectorAll(".today-task .edit-task").forEach((button) => button.addEventListener("click", () => openEdit(Number(button.dataset.id))));
}
function renderWeeklyChart() {
  const now = new Date();
  const start = new Date(now);
  start.setDate(now.getDate() - 6);
  const counts = Array.from({ length: 7 }, (_, index) => {
    const day = new Date(start);
    day.setDate(start.getDate() + index);
    const key = day.toISOString().slice(0, 10);
    return { label: day.toLocaleDateString(undefined, { weekday: "short" }).slice(0, 1), value: state.activity.filter((item) => String(item.created_at).slice(0, 10) === key).length };
  });
  const max = Math.max(...counts.map((item) => item.value), 1);
  $("weeklyChart").innerHTML = counts.map((item) => `<div class="chart-column"><span class="chart-value">${item.value || ""}</span><span class="chart-bar ${item.value ? "active" : ""}" style="height:${Math.max(7, Math.round((item.value / max) * 53))}px"></span><span class="chart-day">${item.label}</span></div>`).join("");
}
async function changeTaskStatus(id, nextStatus, originalStatus) {
  if (nextStatus === originalStatus || state.statusUpdate === id) return;
  const task = state.tasks.find((item) => item.id === id);
  if (!task) return;
  task.status = nextStatus;
  state.statusUpdate = id;
  render();
  setBoardStatus("Saving status…", "loading");
  try {
    await api(`/tasks/${id}/status`, { method: "PATCH", body: JSON.stringify({ status: nextStatus }) });
    state.statusUpdate = null;
    render();
    setBoardStatus("Status saved.");
    showAlert("Task status updated.");
    loadAnalytics();
    loadProductivity();
  } catch (error) {
    task.status = originalStatus;
    state.statusUpdate = null;
    render();
    setBoardStatus("Status could not be saved. The task was restored.", "error");
    showAlert(error.message, "danger");
  }
}
function bindTaskEvents() {
  document.querySelectorAll(".edit-task").forEach((button) => button.addEventListener("click", () => openEdit(Number(button.dataset.id))));
  document.querySelectorAll(".delete-task").forEach((button) => button.addEventListener("click", async () => { if (!window.confirm("Delete this task? This cannot be undone.")) return; try { await api(`/tasks/${button.dataset.id}`, { method: "DELETE" }); showAlert("Task deleted."); await loadTasks(); } catch (error) { showAlert(error.message, "danger"); } }));
  document.querySelectorAll(".status-select").forEach((select) => select.addEventListener("change", () => {
    const task = state.tasks.find((item) => item.id === Number(select.dataset.id));
    changeTaskStatus(Number(select.dataset.id), select.value, task?.status);
  }));
  document.querySelectorAll(".task-card").forEach((card) => {
    card.addEventListener("dragstart", (event) => {
      if (state.statusUpdate) { event.preventDefault(); return; }
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", card.dataset.id);
      card.classList.add("is-dragging");
    });
    card.addEventListener("dragend", () => card.classList.remove("is-dragging"));
  });
}
function openEdit(id) { const task = state.tasks.find((item) => item.id === id); if (!task) return; $("taskId").value = id; $("title").value = task.title; $("description").value = task.description; $("priority").value = task.priority; $("dueDate").value = task.due_date || ""; $("modalTitle").textContent = "Edit task"; bootstrap.Modal.getOrCreateInstance($("taskModal")).show(); }
document.addEventListener("DOMContentLoaded", () => {
  document.body.classList.toggle("dark-mode", localStorage.getItem("taskflow-theme") === "dark");
  fetch("/api/auth/me").then(async (response) => { if (!response.ok) { window.location.href = "/login.html"; return; } const body = await response.json(); const user = body.data.user; const initial = user.name.charAt(0).toUpperCase(); if (user.role === "admin") $("adminAttendanceLink").hidden = false; $("userName").textContent = user.name; $("rightUserName").textContent = user.name; $("rightUserEmail").textContent = user.email || "Personal workspace"; $("greetingTitle").textContent = `Hi, ${user.name}`; $("sidebarUserName").textContent = user.name; $("sidebarAvatar").textContent = initial; document.querySelectorAll(".avatar-small,.avatar-large").forEach((avatar) => { avatar.textContent = initial; }); loadTasks(); loadAnalytics(); loadProductivity(); }).catch(() => { window.location.href = "/login.html"; });
  $("globalSearch").addEventListener("input", (event) => { $("search").value = event.target.value; loadTasks(); });
  $("mobileMenuButton").addEventListener("click", () => { document.body.classList.toggle("sidebar-open"); });
  document.querySelectorAll(".sidebar-link").forEach((link) => link.addEventListener("click", () => document.body.classList.remove("sidebar-open")));
  ["search", "statusFilter", "priorityFilter", "dueDateFilter", "sort"].forEach((id) => $(id).addEventListener(id === "search" ? "input" : "change", loadTasks));
  $("exportExcelButton").addEventListener("click", () => downloadReport("/reports/tasks.xlsx", $("exportExcelButton"), "Excel export downloaded."));
  $("generatePdfButton").addEventListener("click", () => downloadReport("/reports/productivity.pdf", $("generatePdfButton"), "Productivity PDF downloaded."));
  $("newTaskButton").addEventListener("click", () => { $("taskForm").reset(); $("taskId").value = ""; $("modalTitle").textContent = "New task"; });
  $("taskForm").addEventListener("submit", async (event) => { event.preventDefault(); if (!$("taskForm").checkValidity()) { $("taskForm").classList.add("was-validated"); return; } const id = $("taskId").value; const payload = { title: $("title").value.trim(), description: $("description").value, priority: $("priority").value, due_date: $("dueDate").value || null }; $("saveButton").disabled = true; try { await api(id ? `/tasks/${id}` : "/tasks", { method: id ? "PUT" : "POST", body: JSON.stringify(payload) }); bootstrap.Modal.getInstance($("taskModal")).hide(); showAlert(id ? "Task updated." : "Task created."); await loadTasks(); } catch (error) { showAlert(error.message, "danger"); } finally { $("saveButton").disabled = false; } });
  document.querySelectorAll(".kanban-column").forEach((column) => {
    column.addEventListener("dragover", (event) => { event.preventDefault(); event.dataTransfer.dropEffect = "move"; column.classList.add("drop-target"); });
    column.addEventListener("dragleave", (event) => { if (!column.contains(event.relatedTarget)) column.classList.remove("drop-target"); });
    column.addEventListener("drop", (event) => {
      event.preventDefault();
      column.classList.remove("drop-target");
      const id = Number(event.dataTransfer.getData("text/plain"));
      const task = state.tasks.find((item) => item.id === id);
      if (task) changeTaskStatus(id, column.dataset.status, task.status);
    });
  });
  $("logoutButton").addEventListener("click", async () => { await api("/auth/logout", { method: "POST" }); window.location.href = "/login.html"; });
  $("themeButton").onclick = () => { const dark = !document.body.classList.contains("dark-mode"); document.body.classList.toggle("dark-mode", dark); localStorage.setItem("taskflow-theme", dark ? "dark" : "light"); };
  $("calendarPrev").addEventListener("click", () => { state.calendarDate.setMonth(state.calendarDate.getMonth() - 1); renderMiniCalendar(); });
  $("calendarNext").addEventListener("click", () => { state.calendarDate.setMonth(state.calendarDate.getMonth() + 1); renderMiniCalendar(); });
  $("notificationButton").addEventListener("click", async () => { const reminders = await api("/reminders"); const message = reminders.data.reminders.length ? reminders.data.reminders.map((item) => `${escapeHtml(item.kind)}: ${escapeHtml(item.title)} (${escapeHtml(item.due_date)})`).join("<br>") : "No upcoming reminders."; showAlert(message, reminders.data.reminders.some((item) => item.kind === "overdue") ? "warning" : "info"); });
  $("aiButton").addEventListener("click", async () => {
    const result = $("aiResult"); const button = $("aiButton"); const description = $("aiGoal").value.trim();
    if (!description) { result.textContent = "Enter a task description first."; return; }
    button.disabled = true; result.textContent = "Generating suggestions...";
    try {
      const data = await api("/ai/suggest-tasks", { method: "POST", body: JSON.stringify({ description }) });
      const suggestion = data.data;
      result.innerHTML = `<div class="alert alert-light"><strong>Review this draft</strong><h3 class="h6 mt-2">${escapeHtml(suggestion.title)}</h3><p>${escapeHtml(suggestion.description)}</p><strong>Priority:</strong> ${escapeHtml(suggestion.priority)}<strong class="d-block mt-2">Subtasks</strong><ul>${suggestion.subtasks.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul><button class="btn btn-outline-primary btn-sm mt-2" id="useAiSuggestion">Review in task form</button></div>`;
      $("useAiSuggestion").addEventListener("click", () => { $("taskForm").reset(); $("taskId").value = ""; $("modalTitle").textContent = "Review AI task"; $("title").value = suggestion.title; $("description").value = `${suggestion.description}\n\nSubtasks:\n${suggestion.subtasks.map((item) => `- ${item}`).join("\n")}`; $("priority").value = suggestion.priority; bootstrap.Modal.getOrCreateInstance($("taskModal")).show(); });
    } catch (error) { result.innerHTML = `<div class="alert alert-warning">${escapeHtml(error.message)}</div>`; } finally { button.disabled = false; }
  });
});
