// static/gamescript.js — Networking Game client (Snowflake-ready)
console.log("[game] script loaded");

let currentQuest = { type: "outreach", choice: "" };

// Prettier, game-like labels for badge IDs
const BADGE_LABELS = {
  badge_first_connection: "🛰️ First Contact",
  badge_week_streak_3: "🔥 3-Day Streak",
  badge_resource_share: "🎁 Reciprocity Rookie",
  badge_coffee_chat: "☕ Coffee Challenger",
  badge_outreach_pro: "📡 Outreach Pro"
};
function prettyBadge(id) {
  if (BADGE_LABELS[id]) return BADGE_LABELS[id];
  // fallback: Title-case unknown ids
  return id.replace(/_/g, " ").replace(/\b\w/g, m => m.toUpperCase());
}

/* ----------------------------- Leaderboard ----------------------------- */
async function loadLeaderboard() {
  try {
    const res = await fetch("/leaderboard");
    const rows = await res.json();

    const body = document.getElementById("leaderboard-body");
    if (!body) return console.error("[game] missing #leaderboard-body");
    body.innerHTML = "";

    if (!Array.isArray(rows) || rows.length === 0) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td class="rank"></td><td>No data yet</td><td class="pts">0</td>`;
      body.appendChild(tr);
      return;
    }

    const me = "Player-001";
    rows.forEach(r => {
      const tr = document.createElement("tr");
      if (r.username === me) tr.classList.add("me");
      tr.innerHTML = `
        <td class="rank">${r.rank ?? ""}</td>
        <td>${r.username ?? ""}</td>
        <td class="pts">${r.points ?? 0}</td>
      `;
      body.appendChild(tr);
    });
  } catch (e) {
    console.error("[game] loadLeaderboard error:", e);
  }
}

/* ---------------------------- State & Tasks ---------------------------- */
async function loadState() {
  try {
    const res = await fetch("/get_state");
    const data = await res.json();

    setText("points", data.points ?? 0);
    setText("streak", data.streak ?? 0);
    setText("level-name", data.level ?? "Rookie Connector");
    setWidth("xp-bar", Math.min(100, (data.points ?? 0) % 100) + "%");

    // badges
const badges = document.getElementById("badges");
if (badges) {
  badges.innerHTML = "";
  (data.badges || []).forEach(b => {
    const chip = document.createElement("span");
    chip.className = "badge";
    chip.textContent = prettyBadge(b);    // <-- use pretty label
    badges.appendChild(chip);
  });
}

    // tasks
    renderTasks("daily-list",  (data.tasks || []).filter(t => t.category === "daily"));
    renderTasks("weekly-list", (data.tasks || []).filter(t => t.category === "weekly"));
  } catch (e) {
    console.error("[game] loadState error:", e);
  }
}

function renderTasks(containerId, tasks) {
  const box = document.getElementById(containerId);
  if (!box) return console.warn("[game] missing container", containerId);
  box.innerHTML = "";
  (tasks || []).forEach(t => {
    const row = document.createElement("div");
    row.className = "task";
    row.innerHTML = `
      <div>
        <div>${t.description}</div>
        <small>${t.points} XP</small>
      </div>
      ${t.completed
        ? `<span class="done">✓ Completed</span>`
        : `<button data-id="${t.id}">Complete</button>`}
    `;
    if (!t.completed) {
      row.querySelector("button")?.addEventListener("click", () => completeTask(t.id));
    }
    box.appendChild(row);
  });
}

async function completeTask(taskId) {
  try {
    const res = await fetch("/complete_task", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ taskId })
    });
    const data = await res.json();
    if (!res.ok) {
      alert(data.error || "Could not complete task.");
      return;
    }
    await Promise.all([loadState(), loadLeaderboard()]);
  } catch (e) {
    console.error("[game] completeTask error:", e);
  }
}

/* -------------------------------- Quests ------------------------------- */
function wireQuests() {
  const modal = byId("quest-modal");
  const title = byId("quest-title");
  const prompt = byId("quest-prompt");
  const text   = byId("quest-text");
  const scoreR = byId("score-result");
  const follow = byId("followup-choices");

  function ensureModal() {
    if (!modal || !title || !prompt || !text || !scoreR || !follow) {
      console.error("[game] quest modal pieces missing");
      alert("Quest UI is missing in HTML. Add the Quest Modal block with required IDs.");
      return false;
    }
    return true;
  }

  async function openQuest(type) {
    if (!ensureModal()) return;
    currentQuest = { type, choice: "" };

    // Open quickly so the UI responds
    modal.style.display = "block";
    title.textContent = ({
      outreach:   "Outreach Craft",
      coffee:     "Coffee-Chat Prep",
      followup:   "Follow-Up Timing",
      reciprocity:"Reciprocity Builder"
    })[type] || "Quest";

    prompt.textContent = "Loading scenario…";
    text.value = "";
    scoreR.textContent = "";
    follow.style.display = (type === "followup") ? "flex" : "none";

    if (follow) {
      follow.querySelectorAll(".pill").forEach(b => {
        b.classList.remove("active");
        b.setAttribute("aria-pressed", "false");
      });
    }

    try {
      const res = await fetch("/quest/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type })
      });
      const j = await res.json();
      prompt.textContent = j?.scenario?.prompt || "Write your answer below.";
    } catch (e) {
      console.warn("[game] /quest/start failed; using fallback", e);
      prompt.textContent = "Write your answer below.";
    }
  }

  const bind = (id, fn) => {
    const el = document.getElementById(id);
    if (!el) return console.error("[game] missing button #" + id);
    el.onclick = fn;
  };

  bind("start-outreach",    () => openQuest("outreach"));
  bind("start-coffee",      () => openQuest("coffee"));
  bind("start-followup",    () => openQuest("followup"));
  bind("start-reciprocity", () => openQuest("reciprocity"));
  bind("close-quest",       () => { if (modal) modal.style.display = "none"; });

  // follow-up choice chips (e.g., Monday, 48h, Early next week)
 const followBtns = Array.from(document.querySelectorAll("#followup-choices .pill"));
followBtns.forEach(btn => {
  btn.setAttribute("role", "button");
  btn.setAttribute("aria-pressed", "false");
  btn.addEventListener("click", () => {
    currentQuest.choice = btn.dataset.choice || "";
    followBtns.forEach(b => {
      const on = (b === btn);
      b.classList.toggle("active", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
    // OPTIONAL: auto-insert the timing into your draft if not present
    // const ta = document.getElementById("quest-text");
    // if (ta && currentQuest.type === "followup" && !ta.value.toLowerCase().includes(currentQuest.choice.toLowerCase())) {
    //   ta.value = (ta.value + `\n\nProposed timing: ${currentQuest.choice}.`).trim();
    // }
  });
});

  bind("score-quest", async () => {
    if (!ensureModal()) return;
    try {
      const res = await fetch("/quest/score", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type: currentQuest.type,
          text: text.value,
          choice: currentQuest.choice
        })
      });
      const j = await res.json();
      scoreR.textContent = `+${j.earned} XP${(j.tips && j.tips.length) ? " • " + j.tips[0] : ""}`;
      await Promise.all([loadState(), loadLeaderboard()]);
    } catch (e) {
      console.error("[game] /quest/score failed", e);
      scoreR.textContent = "Could not score. Try again.";
    }
  });

  // NEW: rewrite handler
  
}

/* ------------------------------- Coach chat ---------------------------- */
function wireCoach() {
  const modal = byId("coach-modal");
  const feed  = byId("coach-feed");
  const input = byId("coach-input");
  const status= byId("coach-status");

  function push(role, text) {
    const div = document.createElement("div");
    div.style.margin = "6px 0";
    div.innerHTML = (role === "user")
      ? `<b>You:</b> ${escapeHtml(text)}`
      : `<b>Coach:</b> ${escapeHtml(text)}`;
    feed.appendChild(div);
    feed.scrollTop = feed.scrollHeight;
  }

  onClick("open-coach", () => {
    if (!modal || !feed || !input || !status) return;
    feed.innerHTML = "";
    input.value = "";
    status.textContent = "";
    modal.style.display = "block";
  });

  onClick("coach-close", () => { if (modal) modal.style.display = "none"; });

  onClick("coach-send", async () => {
    if (!feed || !input || !status) return;
    const txt = input.value.trim();
    if (!txt) return;
    push("user", txt);
    status.textContent = "Thinking…";
    input.value = "";
    try {
      const res = await fetch("/coach/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: txt })
      });
      const j = await res.json();
      push("assistant", j.reply || "Sorry, no reply.");
    } catch (e) {
      push("assistant", "I hit a snag. Try again.");
    } finally {
      status.textContent = "";
    }
  });
}

/* ------------------------------ Small utils --------------------------- */
function byId(id) {
  const el = document.getElementById(id);
  if (!el) console.error("[game] missing #" + id);
  return el;
}
function onClick(id, fn) {
  const el = byId(id);
  if (el) el.onclick = fn;
}
function setText(id, v) {
  const el = byId(id);
  if (el) el.textContent = v;
}
function setWidth(id, v) {
  const el = byId(id);
  if (el) el.style.width = v;
}
function escapeHtml(s) {
  return (s ?? "").replace(/[&<>"']/g, m => ({
    "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"
  }[m]));
}

/* ------------------------------ Wire tasks ---------------------------- */
function wireTasks() {
  // No-op: task buttons are bound in renderTasks()
}

/* --------------------------------- Init -------------------------------- */
async function init() {
  try {
    await Promise.all([loadLeaderboard(), loadState()]);
    wireQuests();
    wireTasks();
    wireCoach();
    console.log("[game] ready");
  } catch (e) {
    console.error("[game] init failed:", e);
  }
}
window.addEventListener("DOMContentLoaded", init);