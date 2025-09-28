// static/networkinggamescript.js

// Load state on page ready
window.onload = loadState;

// Cache dom nodes
const pointsEl = document.getElementById("points");
const streakEl = document.getElementById("streak");
const barEl = document.getElementById("progress-bar");
const badgesEl = document.getElementById("badges");

// Containers for dynamic lists
const dailyListContainer = document.querySelector(".card ul"); // first UL under Daily Tasks
const weeklyListContainer = document.querySelectorAll(".card ul")[1]; // second UL under Weekly

async function loadState() {
  const res = await fetch("/get_state");
  const data = await res.json();
  renderState(data);
}

function renderState(data) {
  // Numbers
  pointsEl.textContent = data.points;
  streakEl.textContent = data.streak + " Days";

  // Simple progress bar based on points
  const pct = data.points % 100;
  barEl.style.width = pct + "%";
  barEl.textContent = pct + "% to Next Level";

  // Badges
  badgesEl.innerHTML = "";
  (data.badges || []).forEach(b => {
    const span = document.createElement("span");
    span.textContent = b;
    badgesEl.appendChild(span);
  });

  // Tasks (daily + weekly) from backend
  const dailyTasks = (data.tasks || []).filter(t => t.category === "daily");
  const weeklyTasks = (data.tasks || []).filter(t => t.category === "weekly");

  // Render daily
  dailyListContainer.innerHTML = "";
  dailyTasks.forEach(task => {
    const li = document.createElement("li");
    li.innerHTML = `
      ${task.description} (${task.points} XP)
      ${task.completed ? "<em>✔ Completed</em>" :
        `<button data-id="${task.id}">Complete</button>`}
    `;
    // Attach click if not completed
    if (!task.completed) {
      li.querySelector("button").addEventListener("click", () => completeTask(task.id));
    }
    dailyListContainer.appendChild(li);
  });

  // Render weekly
  weeklyListContainer.innerHTML = "";
  weeklyTasks.forEach(task => {
    const li = document.createElement("li");
    li.innerHTML = `
      ${task.description} (${task.points} XP)
      ${task.completed ? "<em>✔ Completed</em>" :
        `<button data-id="${task.id}">Complete</button>`}
    `;
    if (!task.completed) {
      li.querySelector("button").addEventListener("click", () => completeTask(task.id));
    }
    weeklyListContainer.appendChild(li);
  });
}

async function completeTask(taskId) {
  const res = await fetch("/complete_task", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ taskId })
  });
  const data = await res.json();
  if (res.ok) {
    renderState(data);
  } else {
    alert(data.error || "Could not complete task.");
  }
}

async function saveProgress() {
  await fetch("/save", { method: "POST" });
  alert("Progress saved!");
}

async function loadProgress() {
  const res = await fetch("/load");
  const data = await res.json();
  renderState(data);
}


