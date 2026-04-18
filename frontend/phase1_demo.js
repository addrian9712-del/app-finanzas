const $ = (id) => document.getElementById(id);

const api = {
  baseUrl: () => $("baseUrl").value.trim(),
  auth: () => ({ Authorization: `Bearer ${$("userId").value.trim()}` }),
  async req(path, opts = {}) {
    const res = await fetch(`${this.baseUrl()}${path}`, {
      ...opts,
      headers: {
        "Content-Type": "application/json",
        ...this.auth(),
        ...(opts.headers || {}),
      },
    });
    if (res.status === 204) return null;
    const data = await res.json();
    if (!res.ok) throw new Error(data?.error?.message || data?.error?.code || `HTTP ${res.status}`);
    return data;
  },
};

function setStatus(msg, ok = true) {
  $("status").textContent = msg;
  $("status").className = ok ? "ok" : "err";
}

function itemHtml(title, meta = "") {
  return `<div class="item"><strong>${title}</strong>${meta ? `<div><small>${meta}</small></div>` : ""}</div>`;
}

async function loadTemplates() {
  const out = $("templates");
  out.innerHTML = "";
  const data = await api.req("/v1/card-templates");
  out.innerHTML = data.data
    .map(
      (t) =>
        `<div class="item">
          <div>${t.icon || "🧩"} <strong>${t.title}</strong> <span class="pill">${t.type}</span></div>
          <small>${t.description || ""}</small>
        </div>`
    )
    .join("");
  setStatus(`Templates cargadas: ${data.data.length}`);
}

async function loadCards() {
  const out = $("cards");
  const data = await api.req("/v1/user-cards");
  out.innerHTML = data.data.map((c) => itemHtml(`${c.title} (${c.type})`, c.id)).join("");
}

async function createCard() {
  const title = $("cardTitle").value.trim();
  if (!title) throw new Error("title requerido");
  const type = $("cardType").value;
  let config = {};
  try {
    config = JSON.parse($("cardConfig").value || "{}");
  } catch {
    throw new Error("config JSON inválido");
  }
  await api.req("/v1/user-cards", {
    method: "POST",
    body: JSON.stringify({ title, type, config }),
  });
  setStatus("Tarjeta creada");
  await loadCards();
}

async function generateInstances() {
  const date = $("instanceDate").value;
  if (!date) throw new Error("date requerido");
  const data = await api.req("/v1/card-instances/generate", {
    method: "POST",
    body: JSON.stringify({ date }),
  });
  setStatus(`Instancias generadas: ${data.data.created}`);
  await loadInstances();
}

async function loadInstances() {
  const date = $("instanceDate").value;
  if (!date) throw new Error("date requerido");
  const out = $("instances");
  const data = await api.req(`/v1/card-instances?date=${encodeURIComponent(date)}`);
  out.innerHTML = data.data
    .map(
      (i) => `<div class="item">
        <div><strong>${i.id}</strong> <span class="pill">${i.status}</span></div>
        <small>card: ${i.user_card_id}</small>
        <div class="row" style="margin-top:8px">
          <button onclick="completeInstance('${i.id}')">Completar</button>
        </div>
      </div>`
    )
    .join("");
}

async function completeInstance(id) {
  await api.req(`/v1/card-instances/${id}/complete`, {
    method: "POST",
    body: JSON.stringify({ notes: "completado desde demo" }),
  });
  setStatus(`Instancia completada: ${id}`);
  await loadInstances();
}
window.completeInstance = completeInstance;

async function pushSync() {
  const payload = {
    changes: [
      {
        change_id: `chg_${Date.now()}`,
        entity: "user_card",
        entity_id: "demo_card",
        operation: "update",
        version: 1,
        payload: { title: "Demo" },
      },
    ],
  };
  const data = await api.req("/v1/sync/push", { method: "POST", body: JSON.stringify(payload) });
  setStatus(`Push OK: ${data.data.accepted.length} cambio(s)`);
}

async function pullSync() {
  const data = await api.req("/v1/sync/pull");
  $("sync").innerHTML = data.data.changes.map((c) => itemHtml(`${c.entity} ${c.operation}`, c.change_id)).join("");
  setStatus(`Pull OK: ${data.data.changes.length} cambio(s)`);
}

$("btnLoadTemplates").addEventListener("click", () => run(loadTemplates));
$("btnCreateCard").addEventListener("click", () => run(createCard));
$("btnGenerate").addEventListener("click", () => run(generateInstances));
$("btnLoadInstances").addEventListener("click", () => run(loadInstances));
$("btnPush").addEventListener("click", () => run(pushSync));
$("btnPull").addEventListener("click", () => run(pullSync));

function run(fn) {
  fn().catch((e) => setStatus(e.message || String(e), false));
}

$("instanceDate").value = new Date().toISOString().slice(0, 10);
run(loadTemplates);
run(loadCards);
