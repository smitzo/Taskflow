import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Download,
  FileUp,
  KeyRound,
  LogIn,
  LogOut,
  MessageSquare,
  Plus,
  RefreshCw,
  Search,
  Send,
  Trash2,
  UserPlus,
  Users,
} from "lucide-react";
import "./styles.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

const emptyWorkspaceForm = { name: "", description: "" };
const createEmptyTaskForm = () => ({
  title: "",
  description: "",
  assignee_id: "",
  priority: "medium",
  deadline: toDateTimeLocal(addHours(new Date(), 24)),
});
const emptyFilters = { status: "", priority: "", assignee_id: "", page: 1, size: 10 };
const statusOrder = ["todo", "in_progress", "review", "done"];

function App() {
  const [mode, setMode] = useState("login");
  const [authForm, setAuthForm] = useState({
    email: "ada@example.com",
    full_name: "Ada Lovelace",
    password: "1234",
  });
  const [tokens, setTokens] = useState(() => {
    const raw = localStorage.getItem("taskflow_tokens");
    return raw ? JSON.parse(raw) : null;
  });
  const [profile, setProfile] = useState(null);
  const [workspaces, setWorkspaces] = useState([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState("");
  const [workspaceDetail, setWorkspaceDetail] = useState(null);
  const [tasks, setTasks] = useState({ items: [], page: 1, size: 10, total: 0 });
  const [summary, setSummary] = useState(null);
  const [selectedTask, setSelectedTask] = useState(null);
  const [comments, setComments] = useState({ items: [], page: 1, size: 10, total: 0 });
  const [workspaceForm, setWorkspaceForm] = useState(emptyWorkspaceForm);
  const [inviteEmail, setInviteEmail] = useState("");
  const [taskForm, setTaskForm] = useState(createEmptyTaskForm);
  const [filters, setFilters] = useState(emptyFilters);
  const [commentBody, setCommentBody] = useState("");
  const [uploadFile, setUploadFile] = useState(null);
  const [activity, setActivity] = useState({ items: [], page: 1, size: 10, total: 0 });
  const [message, setMessage] = useState("Ready.");
  const [loading, setLoading] = useState(false);

  const isLoggedIn = Boolean(tokens?.access_token);
  const selectedWorkspace = workspaces.find((workspace) => workspace.id === selectedWorkspaceId);
  const members = workspaceDetail?.members ?? [];

  const statusTone = useMemo(() => {
    const lowered = message.toLowerCase();
    if (lowered.includes("failed") || lowered.includes("invalid") || lowered.includes("error")) return "error";
    if (lowered.includes("created") || lowered.includes("updated") || lowered.includes("loaded")) return "success";
    return "neutral";
  }, [message]);

  useEffect(() => {
    if (isLoggedIn) {
      bootstrapSession();
    }
  }, [isLoggedIn]);

  useEffect(() => {
    if (selectedWorkspaceId) {
      loadWorkspaceBundle(selectedWorkspaceId);
    }
  }, [selectedWorkspaceId]);

  async function request(path, options = {}) {
    const headers = {
      ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(tokens?.access_token ? { Authorization: `Bearer ${tokens.access_token}` } : {}),
      ...options.headers,
    };
    const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
    const contentType = response.headers.get("content-type") ?? "";
    const body = contentType.includes("application/json") ? await response.json() : await response.blob();
    if (!response.ok) {
      throw new Error(formatApiError(body?.detail));
    }
    return body;
  }

  function saveTokens(nextTokens) {
    setTokens(nextTokens);
    localStorage.setItem("taskflow_tokens", JSON.stringify(nextTokens));
  }

  function updateAuthField(event) {
    setAuthForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  async function submitAuth(event) {
    event.preventDefault();
    setLoading(true);
    try {
      if (mode === "register") {
        await request("/auth/register", { method: "POST", body: JSON.stringify(authForm) });
        setMode("login");
        setMessage("Account created. Log in to continue.");
      } else {
        const nextTokens = await request("/auth/login", {
          method: "POST",
          body: JSON.stringify({ email: authForm.email, password: authForm.password }),
        });
        saveTokens(nextTokens);
        setMessage("Logged in.");
      }
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function bootstrapSession() {
    setLoading(true);
    try {
      const [user, workspaceList] = await Promise.all([request("/auth/me"), request("/workspaces")]);
      setProfile(user);
      setWorkspaces(workspaceList);
      if (!selectedWorkspaceId && workspaceList.length > 0) {
        setSelectedWorkspaceId(workspaceList[0].id);
      }
      setMessage("Session loaded.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function refreshToken() {
    if (!tokens?.refresh_token) return;
    setLoading(true);
    try {
      const nextTokens = await request("/auth/refresh", {
        method: "POST",
        body: JSON.stringify({ refresh_token: tokens.refresh_token }),
      });
      saveTokens(nextTokens);
      setMessage("Token refreshed.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  function signOut() {
    setTokens(null);
    setProfile(null);
    setWorkspaces([]);
    setSelectedWorkspaceId("");
    setWorkspaceDetail(null);
    setTasks({ items: [], page: 1, size: 10, total: 0 });
    setSummary(null);
    setSelectedTask(null);
    localStorage.removeItem("taskflow_tokens");
    setMessage("Signed out.");
  }

  async function loadWorkspaceBundle(workspaceId = selectedWorkspaceId) {
    if (!workspaceId) return;
    setLoading(true);
    try {
      const [detail, taskPage, taskSummary] = await Promise.all([
        request(`/workspaces/${workspaceId}`),
        request(taskListPath(workspaceId, filters)),
        request(`/workspaces/${workspaceId}/tasks/summary`),
      ]);
      setWorkspaceDetail(detail);
      setTasks(taskPage);
      setSummary(taskSummary);
      setSelectedTask(null);
      setComments({ items: [], page: 1, size: 10, total: 0 });
      setActivity({ items: [], page: 1, size: 10, total: 0 });
      setMessage("Workspace loaded.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  function taskListPath(workspaceId, nextFilters) {
    const params = new URLSearchParams();
    params.set("page", nextFilters.page);
    params.set("size", nextFilters.size);
    if (nextFilters.status) params.set("status", nextFilters.status);
    if (nextFilters.priority) params.set("priority", nextFilters.priority);
    if (nextFilters.assignee_id) params.set("assignee_id", nextFilters.assignee_id);
    return `/workspaces/${workspaceId}/tasks?${params.toString()}`;
  }

  async function createWorkspace(event) {
    event.preventDefault();
    setLoading(true);
    try {
      const workspace = await request("/workspaces", {
        method: "POST",
        body: JSON.stringify({
          name: workspaceForm.name,
          description: workspaceForm.description || null,
        }),
      });
      setWorkspaceForm(emptyWorkspaceForm);
      const nextWorkspaces = await request("/workspaces");
      setWorkspaces(nextWorkspaces);
      setSelectedWorkspaceId(workspace.id);
      await loadWorkspaceBundle(workspace.id);
      setMessage("Workspace created.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function inviteMember(event) {
    event.preventDefault();
    if (!selectedWorkspaceId) return;
    setLoading(true);
    try {
      await request(`/workspaces/${selectedWorkspaceId}/members`, {
        method: "POST",
        body: JSON.stringify({ email: inviteEmail }),
      });
      setInviteEmail("");
      await loadWorkspaceBundle(selectedWorkspaceId);
      setMessage("Member invited.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function populateDemoData() {
    setLoading(true);
    try {
      const seed = await request("/demo/seed", { method: "POST" });
      const nextWorkspaces = await request("/workspaces");
      setWorkspaces(nextWorkspaces);
      setSelectedWorkspaceId(seed.workspace_id);
      await loadWorkspaceBundle(seed.workspace_id);
      setMessage(seed.message);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function removeDemoData() {
    setLoading(true);
    try {
      const result = await request("/demo/seed", { method: "DELETE" });
      const nextWorkspaces = await request("/workspaces");
      setWorkspaces(nextWorkspaces);
      setSelectedWorkspaceId(nextWorkspaces[0]?.id ?? "");
      setWorkspaceDetail(null);
      setTasks({ items: [], page: 1, size: 10, total: 0 });
      setSummary(null);
      setSelectedTask(null);
      setComments({ items: [], page: 1, size: 10, total: 0 });
      setActivity({ items: [], page: 1, size: 10, total: 0 });
      if (nextWorkspaces[0]) {
        await loadWorkspaceBundle(nextWorkspaces[0].id);
      }
      setMessage(result.message);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function removeMember(userId) {
    if (!selectedWorkspaceId) return;
    setLoading(true);
    try {
      await request(`/workspaces/${selectedWorkspaceId}/members/${userId}`, { method: "DELETE" });
      await loadWorkspaceBundle(selectedWorkspaceId);
      setMessage("Member removed.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function createTask(event) {
    event.preventDefault();
    if (!selectedWorkspaceId) return;
    setLoading(true);
    try {
      await request(`/workspaces/${selectedWorkspaceId}/tasks`, {
        method: "POST",
        body: JSON.stringify({
          ...taskForm,
          assignee_id: taskForm.assignee_id || null,
          description: taskForm.description || null,
          deadline: taskForm.deadline ? new Date(taskForm.deadline).toISOString() : null,
        }),
      });
      setTaskForm(createEmptyTaskForm());
      await loadWorkspaceBundle(selectedWorkspaceId);
      setMessage("Task created.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function applyFilters(event) {
    event.preventDefault();
    if (!selectedWorkspaceId) return;
    setLoading(true);
    try {
      const taskPage = await request(taskListPath(selectedWorkspaceId, filters));
      setTasks(taskPage);
      setSelectedTask(null);
      setMessage("Tasks loaded.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function loadTask(taskId) {
    setLoading(true);
    try {
      const detail = await request(`/tasks/${taskId}`);
      const [commentPage, activityPage] = await Promise.all([
        request(`/tasks/${taskId}/comments?page=1&size=10`),
        request(`/tasks/${taskId}/activity?page=1&size=10`),
      ]);
      setSelectedTask(detail);
      setComments(commentPage);
      setActivity(activityPage);
      setMessage("Task loaded.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function advanceTask(task) {
    const currentIndex = statusOrder.indexOf(task.status);
    const nextStatus = statusOrder[currentIndex + 1];
    if (!nextStatus) return;
    setLoading(true);
    try {
      const updated = await request(`/tasks/${task.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: nextStatus }),
      });
      await loadWorkspaceBundle(selectedWorkspaceId);
      if (updated.id === selectedTask?.id) {
        await loadTask(updated.id);
      }
      setMessage("Task status updated.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function deleteTask(taskId) {
    setLoading(true);
    try {
      await request(`/tasks/${taskId}`, { method: "DELETE" });
      await loadWorkspaceBundle(selectedWorkspaceId);
      setMessage("Task deleted.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function addComment(event) {
    event.preventDefault();
    if (!selectedTask || !commentBody.trim()) return;
    setLoading(true);
    try {
      await request(`/tasks/${selectedTask.id}/comments`, {
        method: "POST",
        body: JSON.stringify({ body: commentBody }),
      });
      setCommentBody("");
      await loadTask(selectedTask.id);
      setMessage("Comment added.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function uploadAttachment(event) {
    event.preventDefault();
    if (!selectedTask || !uploadFile) return;
    const formData = new FormData();
    formData.append("file", uploadFile);
    setLoading(true);
    try {
      await request(`/tasks/${selectedTask.id}/attachments`, { method: "POST", body: formData });
      setUploadFile(null);
      event.target.reset();
      await loadTask(selectedTask.id);
      setMessage("Attachment uploaded.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function downloadAttachment(attachment) {
    try {
      const blob = await request(`/attachments/${attachment.id}`);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = attachment.original_filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setMessage(error.message);
    }
  }

  if (!isLoggedIn) {
    return (
      <main className="auth-shell">
        <section className="auth-panel">
          <div className="brand-row">
            <div>
              <p className="eyebrow">TaskFlow</p>
              <h1>Sign in</h1>
            </div>
            <span className="pill">Guest</span>
          </div>

          <div className="tabs" role="tablist" aria-label="Authentication mode">
            <button className={mode === "login" ? "active" : ""} onClick={() => setMode("login")} type="button">
              <LogIn size={16} /> Login
            </button>
            <button className={mode === "register" ? "active" : ""} onClick={() => setMode("register")} type="button">
              <UserPlus size={16} /> Register
            </button>
          </div>

          <form onSubmit={submitAuth} className="form">
            <label>
              Email
              <input name="email" type="email" value={authForm.email} onChange={updateAuthField} required />
            </label>
            {mode === "register" && (
              <label>
                Full name
                <input name="full_name" value={authForm.full_name} onChange={updateAuthField} required minLength={2} />
              </label>
            )}
            <label>
              Password
              <input
                name="password"
                type="password"
                value={authForm.password}
                onChange={updateAuthField}
                required
                minLength={4}
              />
            </label>
            <button className="primary" disabled={loading} type="submit">
              <KeyRound size={17} /> {loading ? "Working..." : mode === "register" ? "Create account" : "Log in"}
            </button>
          </form>

          <div className={`notice ${statusTone}`}>{message}</div>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-row">
          <div>
            <p className="eyebrow">TaskFlow</p>
            <h1>Dashboard</h1>
          </div>
          <span className="pill success">Live</span>
        </div>

        <div className={`notice ${statusTone}`}>
          {statusTone === "error" ? <AlertCircle size={16} /> : <CheckCircle2 size={16} />}
          {message}
        </div>

        <div className="user-strip">
          <div>
            <strong>{profile?.full_name ?? "User"}</strong>
            <span>{profile?.email}</span>
          </div>
          <button title="Sign out" onClick={signOut} type="button">
            <LogOut size={16} />
          </button>
        </div>

        <div className="sidebar-actions">
          <button onClick={bootstrapSession} disabled={loading} type="button">
            <RefreshCw size={16} /> Reload
          </button>
          <button onClick={refreshToken} disabled={loading} type="button">
            <KeyRound size={16} /> Refresh token
          </button>
          <button onClick={populateDemoData} disabled={loading} type="button">
            <Plus size={16} /> Populate demo data
          </button>
          <button onClick={removeDemoData} disabled={loading} type="button">
            <Trash2 size={16} /> Remove demo data
          </button>
        </div>

        <form onSubmit={createWorkspace} className="form compact-form">
          <label>
            Workspace name
            <input
              value={workspaceForm.name}
              onChange={(event) => setWorkspaceForm((current) => ({ ...current, name: event.target.value }))}
              required
              minLength={2}
            />
          </label>
          <label>
            Description
            <input
              value={workspaceForm.description}
              onChange={(event) => setWorkspaceForm((current) => ({ ...current, description: event.target.value }))}
            />
          </label>
          <button className="primary" disabled={loading} type="submit">
            <Plus size={16} /> Create workspace
          </button>
        </form>

        <nav className="workspace-nav" aria-label="Workspaces">
          {workspaces.map((workspace) => (
            <button
              key={workspace.id}
              className={workspace.id === selectedWorkspaceId ? "workspace-link active" : "workspace-link"}
              onClick={() => setSelectedWorkspaceId(workspace.id)}
              type="button"
            >
              <span>{workspace.name}</span>
              <ArrowRight size={15} />
            </button>
          ))}
        </nav>
      </aside>

      <section className="workspace-area">
        {!selectedWorkspace ? (
          <section className="empty-state">
            <h2>No workspace selected</h2>
            <p>Create a workspace or populate demo data to start using the task board.</p>
          </section>
        ) : (
          <>
            <header className="workspace-header">
              <div>
                <p className="eyebrow">Workspace</p>
                <h2>{selectedWorkspace.name}</h2>
                <p>{workspaceDetail?.description || "No description"}</p>
              </div>
              <div className="summary-grid">
                <Metric label="Total" value={summary?.total ?? 0} />
                <Metric label="Todo" value={summary?.todo ?? 0} />
                <Metric label="Progress" value={summary?.in_progress ?? 0} />
                <Metric label="Review" value={summary?.review ?? 0} />
                <Metric label="Done" value={summary?.done ?? 0} />
              </div>
            </header>

            <section className="content-grid">
              <section className="panel">
                <div className="section-heading">
                  <div>
                    <p className="eyebrow">Members</p>
                    <h3>Team</h3>
                  </div>
                  <Users size={20} />
                </div>
                <form onSubmit={inviteMember} className="inline-form">
                  <input
                    type="email"
                    placeholder="teammate@example.com"
                    value={inviteEmail}
                    onChange={(event) => setInviteEmail(event.target.value)}
                    required
                  />
                  <button disabled={loading} type="submit">
                    <Send size={16} /> Invite
                  </button>
                </form>
                <div className="member-list">
                  {members.map((member) => (
                    <div key={member.user.id} className="member-row">
                      <div>
                        <strong>{member.user.full_name}</strong>
                        <span>{member.user.email}</span>
                      </div>
                      <div className="row-actions">
                        <span className="pill">{member.role}</span>
                        {member.role !== "owner" && (
                          <button title="Remove member" onClick={() => removeMember(member.user.id)} type="button">
                            <Trash2 size={15} />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              <section className="panel">
                <div className="section-heading">
                  <div>
                    <p className="eyebrow">New task</p>
                    <h3>Create</h3>
                  </div>
                  <Plus size={20} />
                </div>
                <form onSubmit={createTask} className="form split-form">
                  <label>
                    Title
                    <input
                      value={taskForm.title}
                      onChange={(event) => setTaskForm((current) => ({ ...current, title: event.target.value }))}
                      required
                      minLength={2}
                    />
                  </label>
                  <label>
                    Assignee
                    <select
                      value={taskForm.assignee_id}
                      onChange={(event) => setTaskForm((current) => ({ ...current, assignee_id: event.target.value }))}
                    >
                      <option value="">Unassigned</option>
                      {members.map((member) => (
                        <option key={member.user.id} value={member.user.id}>
                          {member.user.full_name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Priority
                    <select
                      value={taskForm.priority}
                      onChange={(event) => setTaskForm((current) => ({ ...current, priority: event.target.value }))}
                    >
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                      <option value="critical">Critical</option>
                    </select>
                  </label>
                  <label>
                    Deadline
                    <input
                      type="datetime-local"
                      value={taskForm.deadline}
                      onChange={(event) => setTaskForm((current) => ({ ...current, deadline: event.target.value }))}
                    />
                  </label>
                  <label className="wide">
                    Description
                    <input
                      value={taskForm.description}
                      onChange={(event) => setTaskForm((current) => ({ ...current, description: event.target.value }))}
                    />
                  </label>
                  <button className="primary wide" disabled={loading} type="submit">
                    <Plus size={16} /> Add task
                  </button>
                </form>
              </section>
            </section>

            <section className="panel">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">Tasks</p>
                  <h3>Board</h3>
                </div>
                <span className="pill">{tasks.total} total</span>
              </div>
              <form onSubmit={applyFilters} className="filter-bar">
                <select
                  value={filters.status}
                  onChange={(event) => setFilters((current) => ({ ...current, status: event.target.value, page: 1 }))}
                >
                  <option value="">Any status</option>
                  {statusOrder.map((statusValue) => (
                    <option key={statusValue} value={statusValue}>
                      {formatLabel(statusValue)}
                    </option>
                  ))}
                </select>
                <select
                  value={filters.priority}
                  onChange={(event) => setFilters((current) => ({ ...current, priority: event.target.value, page: 1 }))}
                >
                  <option value="">Any priority</option>
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
                <select
                  value={filters.assignee_id}
                  onChange={(event) => setFilters((current) => ({ ...current, assignee_id: event.target.value, page: 1 }))}
                >
                  <option value="">Any assignee</option>
                  {members.map((member) => (
                    <option key={member.user.id} value={member.user.id}>
                      {member.user.full_name}
                    </option>
                  ))}
                </select>
                <button disabled={loading} type="submit">
                  <Search size={16} /> Filter
                </button>
              </form>

              <div className="task-list">
                {tasks.items.map((task) => (
                  <article
                    key={task.id}
                    className={selectedTask?.id === task.id ? "task-row active" : "task-row"}
                    onClick={() => loadTask(task.id)}
                  >
                    <div>
                      <strong>{task.title}</strong>
                      <span>{task.description || "No description"}</span>
                    </div>
                    <div className="task-meta">
                      <span className={`status-dot ${task.status}`}>{formatLabel(task.status)}</span>
                      <span className={`priority ${task.priority}`}>{task.priority}</span>
                    </div>
                    <div className="row-actions">
                      {task.status !== "done" && (
                        <button
                          title="Advance status"
                          onClick={(event) => {
                            event.stopPropagation();
                            advanceTask(task);
                          }}
                          type="button"
                        >
                          <ArrowRight size={15} />
                        </button>
                      )}
                      <button
                        title="Delete task"
                        onClick={(event) => {
                          event.stopPropagation();
                          deleteTask(task.id);
                        }}
                        type="button"
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            </section>

            {selectedTask && (
              <section className="panel detail-panel">
                <div className="section-heading">
                  <div>
                    <p className="eyebrow">Task detail</p>
                    <h3>{selectedTask.title}</h3>
                  </div>
                  <span className={`status-dot ${selectedTask.status}`}>{formatLabel(selectedTask.status)}</span>
                </div>
                <p className="muted">{selectedTask.description || "No description"}</p>

                <div className="detail-grid">
                  <div>
                    <h4>Comments</h4>
                    <form onSubmit={addComment} className="inline-form">
                      <input
                        value={commentBody}
                        onChange={(event) => setCommentBody(event.target.value)}
                        placeholder="Add a comment"
                        required
                      />
                      <button disabled={loading} type="submit">
                        <MessageSquare size={16} /> Add
                      </button>
                    </form>
                    <div className="comment-list">
                      {comments.items.map((comment) => (
                        <div key={comment.id} className="comment">
                          <div className="comment-meta">
                            <strong>{comment.author?.full_name ?? comment.author_id}</strong>
                            <span>{formatDateTime(comment.created_at)}</span>
                          </div>
                          <p>{comment.body}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div>
                    <h4>Attachments</h4>
                    <form onSubmit={uploadAttachment} className="inline-form">
                      <input type="file" onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)} />
                      <button disabled={loading || !uploadFile} type="submit">
                        <FileUp size={16} /> Upload
                      </button>
                    </form>
                    <div className="attachment-list">
                      {selectedTask.attachments.map((attachment) => (
                        <button key={attachment.id} onClick={() => downloadAttachment(attachment)} type="button">
                          <Download size={15} /> {attachment.original_filename}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="activity-section">
                  <h4>Activity</h4>
                  <div className="activity-list">
                    {activity.items.length === 0 ? (
                      <p className="muted">No status changes yet.</p>
                    ) : (
                      activity.items.map((item) => (
                        <div key={item.id} className="activity-item">
                          <span>
                            <strong>{item.actor?.full_name ?? item.actor_id}</strong> moved status from{" "}
                            <strong>{item.from_status ? formatLabel(item.from_status) : "none"}</strong> to{" "}
                            <strong>{formatLabel(item.to_status)}</strong>
                          </span>
                          <time>{formatDateTime(item.created_at)}</time>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </section>
            )}
          </>
        )}
      </section>
    </main>
  );
}

function Metric({ label, value }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formatLabel(value) {
  return value.replaceAll("_", " ");
}

function addHours(date, hours) {
  return new Date(date.getTime() + hours * 60 * 60 * 1000);
}

function toDateTimeLocal(date) {
  const offsetDate = new Date(date.getTime() - date.getTimezoneOffset() * 60 * 1000);
  return offsetDate.toISOString().slice(0, 16);
}

function formatDateTime(value) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatApiError(detail) {
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg ?? JSON.stringify(item)).join(", ");
  }
  if (typeof detail === "string") {
    return detail;
  }
  if (detail) {
    return JSON.stringify(detail);
  }
  return "Request failed";
}

createRoot(document.getElementById("root")).render(<App />);
