const state = { tasks: [] };
const $ = (id) => document.getElementById(id);
const api = async (url, options = {}) => {
  const response = await fetch(`/api${url}`, { headers: { "Content-Type": "application/json" }, ...options });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error?.message || "Request failed.");
  return body;
};
const showAlert = (message, type = "success") => { $("alertArea").innerHTML = `<div class="alert alert-${type} alert-dismissible fade show" role="alert">${message}<button class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>`; };
const isOverdue = (task) => task.due_date && task.status !== "completed" && new Date(`${task.due_date}T23:59:59`) < new Date();
const taskCard = (task) => {
  const due = task.due_date ? `<span class="${isOverdue(task) ? "overdue" : "due-label"}">${isOverdue(task) ? "Overdue · " : "Due · "}${task.due_date}</span>` : "";
  return `<article class="task-card priority-${task.priority}" draggable="true" data-id="${task.id}" tabindex="0"><h3>${escapeHtml(task.title)}</h3><p>${escapeHtml(task.description || "No description")}</p><div class="task-meta"><span class="priority-label">${task.priority}</span>${due}</div><div class="task-actions"><button class="btn btn-outline-secondary edit-task" data-id="${task.id}">Edit</button><button class="btn btn-outline-danger delete-task" data-id="${task.id}">Delete</button><select class="form-select form-select-sm status-select" data-id="${task.id}" aria-label="Change status"><option value="todo" ${task.status === "todo" ? "selected" : ""}>To do</option><option value="in_progress" ${task.status === "in_progress" ? "selected" : ""}>In progress</option><option value="completed" ${task.status === "completed" ? "selected" : ""}>Completed</option></select></div></article>`;
};
const escapeHtml = (value) => { const div = document.createElement("div"); div.textContent = value; return div.innerHTML; };
function render() {
  const counts = { todo: 0, in_progress: 0, completed: 0 };
  document.querySelectorAll(".task-list").forEach((list) => { list.innerHTML = ""; });
  state.tasks.forEach((task) => { counts[task.status]++; $(`${task.status === "in_progress" ? "progress" : task.status}List`).insertAdjacentHTML("beforeend", taskCard(task)); });
  ["todo", "progress", "completed"].forEach((name) => { const key = name === "progress" ? "in_progress" : name; $(`${name}Badge`).textContent = counts[key]; const list = $(`${name}List`); if (!list.children.length) list.innerHTML = '<div class="empty-state">No tasks here yet.</div>'; });
  const total = state.tasks.length, completed = counts.completed, rate = total ? Math.round((completed / total) * 100) : 0;
  $("totalCount").textContent = total; $("todoCount").textContent = counts.todo; $("progressCount").textContent = counts.in_progress; $("completedCount").textContent = completed; $("completionRate").textContent = `${rate}%`; $("completionBar").style.width = `${rate}%`; $("taskSummary").textContent = `${total} task${total === 1 ? "" : "s"}`;
  bindTaskEvents();
}
async function loadTasks() { try { const params = new URLSearchParams({ search: $("search").value, status: $("statusFilter").value, priority: $("priorityFilter").value, sort: $("sort").value }); const result = await api(`/tasks?${params}`); state.tasks = result.data.tasks; render(); } catch (error) { showAlert(error.message, "danger"); } }
function bindTaskEvents() {
  document.querySelectorAll(".edit-task").forEach((button) => button.addEventListener("click", () => openEdit(Number(button.dataset.id))));
  document.querySelectorAll(".delete-task").forEach((button) => button.addEventListener("click", async () => { if (!window.confirm("Delete this task? This cannot be undone.")) return; try { await api(`/tasks/${button.dataset.id}`, { method: "DELETE" }); showAlert("Task deleted."); await loadTasks(); } catch (error) { showAlert(error.message, "danger"); } }));
  document.querySelectorAll(".status-select").forEach((select) => select.addEventListener("change", async () => { try { await api(`/tasks/${select.dataset.id}/status`, { method: "PATCH", body: JSON.stringify({ status: select.value }) }); await loadTasks(); } catch (error) { showAlert(error.message, "danger"); } }));
  document.querySelectorAll(".task-card").forEach((card) => { card.addEventListener("dragstart", (event) => event.dataTransfer.setData("text/plain", card.dataset.id)); });
}
function openEdit(id) { const task = state.tasks.find((item) => item.id === id); if (!task) return; $("taskId").value = id; $("title").value = task.title; $("description").value = task.description; $("priority").value = task.priority; $("dueDate").value = task.due_date || ""; $("modalTitle").textContent = "Edit task"; bootstrap.Modal.getOrCreateInstance($("taskModal")).show(); }
document.addEventListener("DOMContentLoaded", () => {
  ["search", "statusFilter", "priorityFilter", "sort"].forEach((id) => $(id).addEventListener(id === "search" ? "input" : "change", loadTasks));
  $("newTaskButton").addEventListener("click", () => { $("taskForm").reset(); $("taskId").value = ""; $("modalTitle").textContent = "New task"; });
  $("taskForm").addEventListener("submit", async (event) => { event.preventDefault(); if (!$("taskForm").checkValidity()) { $("taskForm").classList.add("was-validated"); return; } const id = $("taskId").value; const payload = { title: $("title").value.trim(), description: $("description").value, priority: $("priority").value, due_date: $("dueDate").value || null }; $("saveButton").disabled = true; try { await api(id ? `/tasks/${id}` : "/tasks", { method: id ? "PUT" : "POST", body: JSON.stringify(payload) }); bootstrap.Modal.getInstance($("taskModal")).hide(); showAlert(id ? "Task updated." : "Task created."); await loadTasks(); } catch (error) { showAlert(error.message, "danger"); } finally { $("saveButton").disabled = false; } });
  document.querySelectorAll(".kanban-column").forEach((column) => { column.addEventListener("dragover", (event) => event.preventDefault()); column.addEventListener("drop", async (event) => { event.preventDefault(); const id = event.dataTransfer.getData("text/plain"); try { await api(`/tasks/${id}/status`, { method: "PATCH", body: JSON.stringify({ status: column.dataset.status }) }); await loadTasks(); } catch (error) { showAlert(error.message, "danger"); } }); });
  loadTasks();
});
