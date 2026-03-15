const LOG_LIMIT = 12;
const LOG_MAX_AGE_SECONDS = 90;
const REFRESH_MS = 5000;

const state = {
  overview: null,
  trends: [],
  report: null,
  recommendations: [],
  events: [],
  incidents: [],
};

const refs = {
  cityIndex: document.getElementById("city-index"),
  cityStatus: document.getElementById("city-status"),
  openIncidents: document.getElementById("open-incidents"),
  criticalIncidents: document.getElementById("critical-incidents"),
  avgIndex: document.getElementById("avg-index"),
  trends: document.getElementById("trends"),
  risks: document.getElementById("risks"),
  recommendations: document.getElementById("recommendations"),
  events: document.getElementById("events"),
  incidents: document.getElementById("incidents"),
  lastUpdate: document.getElementById("last-update"),
  refreshBtn: document.getElementById("refresh-btn"),
};

function normStatus(status) {
  if (!status) return "unknown";
  return String(status).toLowerCase();
}

function normDate(value) {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return new Date();
  return d;
}

function pruneEvents(events) {
  const now = Date.now();
  const ageMs = LOG_MAX_AGE_SECONDS * 1000;
  return events
    .filter((item) => now - normDate(item.created_at).getTime() <= ageMs)
    .slice(-LOG_LIMIT);
}

function renderOverview() {
  const o = state.overview;
  if (!o) return;
  refs.cityIndex.textContent = o.city_pulse_index.toFixed(1);
  refs.openIncidents.textContent = o.open_incidents;
  refs.criticalIncidents.textContent = o.critical_incidents;

  const status = normStatus(o.status);
  refs.cityStatus.textContent = status;
  refs.cityStatus.className = `badge ${status}`;

  refs.risks.innerHTML = "";
  o.top_risks.forEach((risk) => {
    const li = document.createElement("li");
    li.textContent = risk;
    refs.risks.appendChild(li);
  });
}

function renderTrends() {
  refs.trends.innerHTML = "";
  state.trends.forEach((item) => {
    const card = document.createElement("div");
    card.className = "trend-item";
    card.innerHTML = `
      <div class="trend-row">
        <strong>${item.metric}</strong>
        <span class="delta ${item.direction}">${item.delta > 0 ? "+" : ""}${item.delta.toFixed(2)}</span>
      </div>
      <div class="rec-meta">${item.previous.toFixed(2)} -> ${item.current.toFixed(2)}</div>
    `;
    refs.trends.appendChild(card);
  });
}

function renderReport() {
  if (!state.report) return;
  refs.avgIndex.textContent = state.report.average_index.toFixed(1);
}

function renderRecommendations() {
  refs.recommendations.innerHTML = "";
  state.recommendations.slice(0, 6).forEach((item) => {
    const el = document.createElement("article");
    el.className = "rec-item";
    const actions = item.actions.map((a) => `<li>${a}</li>`).join("");
    el.innerHTML = `
      <strong>${item.incident_id} (${item.severity})</strong>
      <p class="rec-meta">${item.domain} | ${item.recommended_team} | SLA: ${item.sla_minutes} мин</p>
      <ul class="rec-actions">${actions}</ul>
    `;
    refs.recommendations.appendChild(el);
  });
}

function renderEvents() {
  refs.events.innerHTML = "";
  if (!state.events.length) {
    refs.events.innerHTML = '<div class="event-item"><span class="event-time">сейчас</span><p>Событий нет</p></div>';
    return;
  }

  state.events
    .slice()
    .reverse()
    .forEach((item) => {
      const el = document.createElement("article");
      el.className = "event-item";
      const ts = normDate(item.created_at).toLocaleTimeString("ru-RU");
      const meta = [item.domain, item.severity].filter(Boolean).join(" | ");
      el.innerHTML = `
        <span class="event-time">${ts}</span>
        <p>${item.message}</p>
        <div class="rec-meta">${item.kind}${meta ? ` | ${meta}` : ""}</div>
      `;
      refs.events.appendChild(el);
    });
}

function renderIncidents() {
  refs.incidents.innerHTML = "";
  if (!state.incidents.length) {
    refs.incidents.innerHTML = '<div class="incident-item"><p>Открытых инцидентов нет</p></div>';
    return;
  }

  state.incidents.slice(0, 10).forEach((item) => {
    const el = document.createElement("article");
    el.className = "incident-item";
    el.innerHTML = `
      <div class="incident-head">
        <strong>${item.id}</strong>
        <span class="severity-pill ${item.severity}">${item.severity}</span>
      </div>
      <p>${item.description}</p>
      <div class="incident-meta">${item.domain} | ${new Date(item.created_at).toLocaleTimeString("ru-RU")}</div>
      <button class="close-btn" data-id="${item.id}">Закрыть</button>
    `;
    refs.incidents.appendChild(el);
  });

  refs.incidents.querySelectorAll(".close-btn").forEach((btn) => {
    btn.addEventListener("click", () => closeIncident(btn.dataset.id));
  });
}

function render() {
  renderOverview();
  renderTrends();
  renderReport();
  renderRecommendations();
  renderEvents();
  renderIncidents();
  refs.lastUpdate.textContent = `обновлено: ${new Date().toLocaleTimeString("ru-RU")}`;
}

async function closeIncident(incidentId) {
  if (!incidentId) return;
  try {
    const response = await fetch(`/v1/incidents/${encodeURIComponent(incidentId)}/resolve`, {
      method: "POST",
    });
    if (!response.ok) {
      throw new Error("Не удалось закрыть инцидент");
    }
    await loadData();
    refs.lastUpdate.textContent = `инцидент ${incidentId} закрыт`;
  } catch (err) {
    refs.lastUpdate.textContent = `ошибка закрытия ${incidentId}`;
  }
}

async function loadData() {
  const [overviewRes, trendsRes, reportRes, recRes, eventsRes, incidentsRes] = await Promise.all([
    fetch("/v1/analytics/overview"),
    fetch("/v1/analytics/trends?hours=12"),
    fetch("/v1/analytics/report?hours=12"),
    fetch("/v1/incidents/recommendations?min_severity=medium"),
    fetch("/v1/events/recent?limit=40&active_seconds=300"),
    fetch("/v1/incidents/open"),
  ]);

  if (![overviewRes, trendsRes, reportRes, recRes, eventsRes, incidentsRes].every((x) => x.ok)) {
    throw new Error("Ошибка загрузки данных");
  }

  state.overview = await overviewRes.json();
  state.trends = await trendsRes.json();
  state.report = await reportRes.json();
  state.recommendations = await recRes.json();
  state.events = pruneEvents(await eventsRes.json());
  state.incidents = await incidentsRes.json();
  render();
}

async function refresh() {
  refs.refreshBtn.disabled = true;
  refs.refreshBtn.textContent = "Загрузка...";
  try {
    await loadData();
  } catch (err) {
    refs.lastUpdate.textContent = "не удалось загрузить данные";
  } finally {
    refs.refreshBtn.disabled = false;
    refs.refreshBtn.textContent = "Обновить";
  }
}

refs.refreshBtn.addEventListener("click", refresh);
refresh();
setInterval(refresh, REFRESH_MS);
