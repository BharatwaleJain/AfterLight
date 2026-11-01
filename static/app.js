const $ = (id) => document.getElementById(id);
const state = { records: [], currentId: null, output: null, model: "gemma3:4b", toastTimer: null };

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { ...(options.body ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}) },
  });
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) throw new Error(data?.error || `Request failed (${response.status})`);
  return data;
}

function toast(message) {
  const node = $("toast");
  node.textContent = message;
  node.classList.add("show");
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => node.classList.remove("show"), 2800);
}

function formData() {
  return {
    name: $("name").value.trim(),
    relationship: $("relationship").value.trim(),
    memory: $("memory").value.trim(),
    details: $("details").value.trim(),
    words: $("words").value.trim(),
  };
}

function fillForm(record) {
  $("name").value = record.name || "";
  $("relationship").value = record.relationship || "";
  $("memory").value = record.memory || "";
  $("details").value = record.details || "";
  $("words").value = record.words || "";
  state.currentId = record.id || null;
  state.output = record.output || null;
  if (state.output) renderOutput(state.output, state.model);
  else showEmpty();
  renderArchive();
}

function showEmpty() {
  $("emptyState").hidden = false;
  $("resultState").hidden = true;
  $("loadingState").hidden = true;
}

function renderOutput(output, model = state.model) {
  state.output = output;
  $("emptyState").hidden = true;
  $("loadingState").hidden = true;
  $("resultState").hidden = false;
  $("resultTitle").textContent = output.title || "A remembrance";
  $("resultRemembrance").textContent = output.remembrance || "";
  $("resultNote").textContent = output.lantern_note || "A remembered moment can keep giving light.";
  $("modelUsed").textContent = `WRITTEN LOCALLY · ${model.toUpperCase()}`;
}

function renderArchive() {
  const list = $("archiveList");
  $("archiveCount").textContent = `${state.records.length} KEEPSAKE${state.records.length === 1 ? "" : "S"}`;
  if (!state.records.length) {
    list.innerHTML = '<div class="archive-empty">Your saved memories will find a home here.</div>';
    return;
  }
  list.replaceChildren();
  for (const record of state.records) {
    const card = document.createElement("article");
    card.className = `archive-item${record.id === state.currentId ? " active" : ""}`;
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.setAttribute("aria-label", `Open memory for ${record.name}`);
    const heading = document.createElement("h3");
    heading.textContent = record.output?.title || record.name;
    const description = document.createElement("p");
    description.textContent = `${record.relationship ? `${record.relationship} · ` : ""}${record.memory.slice(0, 95)}${record.memory.length > 95 ? "…" : ""}`;
    const date = document.createElement("time");
    date.textContent = record.updated_at ? new Date(record.updated_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }).toUpperCase() : "SAVED MEMORY";
    const remove = document.createElement("button");
    remove.className = "delete-item";
    remove.type = "button";
    remove.textContent = "×";
    remove.title = "Delete this keepsake";
    remove.setAttribute("aria-label", `Delete ${record.name}`);
    remove.addEventListener("click", async (event) => {
      event.stopPropagation();
      if (!confirm(`Delete the saved memory for ${record.name}? This cannot be undone.`)) return;
      try {
        await api(`/api/keepsakes/${record.id}`, { method: "DELETE" });
        state.records = state.records.filter((item) => item.id !== record.id);
        if (state.currentId === record.id) { state.currentId = null; state.output = null; }
        renderArchive();
        if (state.currentId === null && state.output === null) showEmpty();
        toast("Keepsake removed from this device.");
      } catch (error) { toast(error.message); }
    });
    card.append(heading, description, date, remove);
    card.addEventListener("click", () => fillForm(record));
    card.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); fillForm(record); } });
    list.append(card);
  }
}

async function refreshArchive() {
  try {
    state.records = await api("/api/keepsakes");
    renderArchive();
  } catch (error) { toast(error.message); }
}

async function checkModel() {
  try {
    const health = await api("/api/health");
    state.model = health.model;
    if (health.connected && health.model_present) {
      $("statusDot").className = "status-dot online";
      $("statusText").textContent = `LOCAL MODEL READY · ${health.model.toUpperCase()}`;
      $("generateButton").title = "Generate with your local open-weight model";
    } else if (health.connected) {
      $("statusDot").className = "status-dot offline";
      $("statusText").textContent = "MODEL NOT INSTALLED";
      $("generateButton").title = `Run: ollama pull ${health.model}`;
    } else {
      $("statusDot").className = "status-dot offline";
      $("statusText").textContent = "OLLAMA NOT RUNNING";
      $("generateButton").title = "Start Ollama to generate a remembrance";
    }
  } catch {
    $("statusDot").className = "status-dot offline";
    $("statusText").textContent = "LOCAL MODEL UNAVAILABLE";
  }
}

$("memoryForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const memory = formData();
  if (!memory.name || !memory.memory) { toast("Add a name and a memory first."); return; }
  $("emptyState").hidden = true;
  $("resultState").hidden = true;
  $("loadingState").hidden = false;
  $("generateButton").disabled = true;
  $("generateButton").innerHTML = '<span class="button-icon">✧</span> Gathering…';
  try {
    const result = await api("/api/remember", { method: "POST", body: JSON.stringify(memory) });
    state.model = result.model;
    renderOutput(result.output, result.model);
    if (state.currentId) {
      const updated = await api("/api/keepsakes", { method: "POST", body: JSON.stringify({ ...memory, id: state.currentId, output: result.output }) });
      state.records = state.records.map((item) => item.id === updated.id ? updated : item);
      renderArchive();
    }
    toast("A remembrance has been written on this device.");
  } catch (error) {
    showEmpty();
    toast(error.message);
  } finally {
    $("generateButton").disabled = false;
    $("generateButton").innerHTML = '<span class="button-icon">✧</span> Light a lantern';
  }
});

$("saveButton").addEventListener("click", async () => {
  const memory = formData();
  if (!memory.name || !memory.memory) { toast("Add a name and a memory before saving."); return; }
  try {
    const saved = await api("/api/keepsakes", { method: "POST", body: JSON.stringify({ ...memory, id: state.currentId, output: state.output }) });
    state.currentId = saved.id;
    state.records = [saved, ...state.records.filter((item) => item.id !== saved.id)];
    renderArchive();
    toast("Memory saved to your local archive.");
  } catch (error) { toast(error.message); }
});


$("newButton").addEventListener("click", () => {
  $("memoryForm").reset();
  state.currentId = null;
  state.output = null;
  showEmpty();
  renderArchive();
  toast("Ready for a new memory.");
});

for (const field of document.querySelectorAll("#memoryForm input, #memoryForm textarea")) {
  field.addEventListener("input", () => {
    if (state.output) {
      state.output = null;
      showEmpty();
    }
  });
}

const sampleMemories = [
  {
    name: "Kusum",
    relationship: "Nani",
    memory: "This is a starter for a memory with Nani Kusum: a family visit, sitting together for a while, and hearing stories that connect one generation to another. I would replace this with one exact moment I remember — a particular visit, something she said, or a small thing we did together.",
    details: "Family photographs, time together at home, and Jain family occasions such as Paryushan or Diwali where they are part of our own routine.",
    words: ""
  },
  {
    name: "Sarika",
    relationship: "Mummy",
    memory: "A starter for a memory of Mummy Sarika: an ordinary call home while I am in Vellore for college, talking about how the day went and the small things happening on campus. It is the everyday check-in, more than a big occasion, that can make home feel close. I would replace this with an exact call or moment that I remember.",
    details: "Calls between Vellore and home, family updates, familiar meals, and everyday reminders to look after myself.",
    words: ""
  },
  {
    name: "Deepak",
    relationship: "Papa",
    memory: "A starter for a memory of Papa Deepak: a conversation about college, projects, plans, or what is happening back home. Even a short practical suggestion or a quick check-in can become something I want to remember. I would swap this description for one specific conversation that really happened.",
    details: "College updates, plans, practical advice, family calls, and time together when I am back home.",
    words: ""
  },
  {
    name: "Charvi",
    relationship: "Behen",
    memory: "One real detail I can build on is Charvi helping edit a reel from our photos and videos. It made me look back at little moments I might otherwise scroll past. A clip, an old photo, and the effort she put into arranging them can turn into a small record of time spent together.",
    details: "Old photos, short videos, editing a reel, choosing the right clips, and sibling moments.",
    words: ""
  },
  {
    name: "Naincy",
    relationship: "Dost",
    memory: "A starter for a memory with my friend Naincy: working through college ideas together, discussing what to build, dividing tasks, and trying to turn a rough idea into a working project. The process matters as much as the result — the conversations, the small fixes, and the moments when an idea finally clicks. I would replace this with a specific session or project memory.",
    details: "College activities, IET work, PlantEase brainstorming, project planning, deadlines, and small wins.",
    words: ""
  }
];
let previousSampleIndex = -1;

$("demoButton").addEventListener("click", () => {
  let sampleIndex = Math.floor(Math.random() * sampleMemories.length);
  if (sampleMemories.length > 1) {
    while (sampleIndex === previousSampleIndex) {
      sampleIndex = Math.floor(Math.random() * sampleMemories.length);
    }
  }
  previousSampleIndex = sampleIndex;
  const sample = sampleMemories[sampleIndex];
  $("name").value = sample.name;
  $("relationship").value = sample.relationship;
  $("memory").value = sample.memory;
  $("details").value = sample.details;
  $("words").value = sample.words;
  state.currentId = null;
  state.output = null;
  showEmpty();
  renderArchive();
  toast("An editable sample is ready. Replace the details with a memory that is true to you.");
});

$("copyButton").addEventListener("click", async () => {
  const text = `${$("resultTitle").textContent}\n\n${$("resultRemembrance").textContent}\n\n${$("resultNote").textContent}`;
  try { await navigator.clipboard.writeText(text); toast("Remembrance copied."); }
  catch { toast("Clipboard access is unavailable in this browser."); }
});

$("exportLink").addEventListener("click", () => toast("Your local archive export is being prepared."));

(async function init() {
  await Promise.all([checkModel(), refreshArchive()]);
})();
