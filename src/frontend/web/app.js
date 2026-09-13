const state = {
  dashboard: null,
  selectedIntersection: null,
  selectedSignalIntersection: null,
  signalDetail: null,
  sending: false,
  activeView: "overview",
  context: "DIST-CBD",
};

const $ = (selector) => document.querySelector(selector);

const VIEW_LABELS = {
  overview: "态势总览",
  network: "路网监控",
  signals: "信号控制",
  incidents: "事件处置",
};

const VIEW_ROUTES = {
  overview: "/command/dashboard",
  network: "/intersection/monitor",
  signals: "/signal/optimization",
  incidents: "/incident/active",
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatTime(value) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleTimeString("zh-CN", { hour12: false });
}

function formatTimestamp(value) {
  if (!value) return "等待数据";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return `${date.toLocaleDateString("zh-CN")} ${date.toLocaleTimeString("zh-CN", { hour12: false })}`;
}

function saturationClass(value) {
  if (value >= 1.0) return "critical";
  if (value >= 0.9) return "busy";
  if (value >= 0.75) return "watch";
  return "safe";
}

function saturationColor(value) {
  return {
    safe: "#19866e",
    watch: "#c9841f",
    busy: "#e5583f",
    critical: "#c73b32",
  }[saturationClass(value)];
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("is-visible");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("is-visible"), 2400);
}

function switchView(view, updateHash = true) {
  if (!VIEW_LABELS[view]) return;
  state.activeView = view;
  document.querySelectorAll(".rail-button").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.view === view);
  });
  document.querySelectorAll("[data-view-panel]").forEach((panel) => {
    panel.classList.toggle("is-active", panel.dataset.viewPanel === view);
  });
  $("#view-title").textContent = VIEW_LABELS[view];
  if (view === "network" && state.dashboard) renderNetworkTable(state.dashboard);
  if (view === "signals" && state.dashboard) {
    renderSignalBoard(state.dashboard);
    if (!state.selectedSignalIntersection && state.dashboard.intersections[0]) {
      loadSignalDetail(state.dashboard.intersections[0].id);
    }
  }
  if (view === "incidents" && state.dashboard) renderIncidentCommand(state.dashboard);
  if (updateHash && window.location.hash !== `#${view}`) {
    window.history.replaceState(null, "", `#${view}`);
  }
}

function renderKpis(data) {
  const city = data.city;
  const top = city.top5_congested_intersections?.[0];
  const index = Number(city.congestion_index);
  const speed = Number(city.avg_speed_kmh);
  $("#kpi-index").textContent = Number(city.congestion_index).toFixed(1);
  $("#kpi-index-trend").textContent = `${city.trend_vs_yesterday >= 0 ? "↑" : "↓"} ${Math.abs(city.trend_vs_yesterday).toFixed(1)}`;
  $("#kpi-index-bar").style.width = `${Math.min(100, index * 10)}%`;
  $("#kpi-speed").textContent = Number(city.avg_speed_kmh).toFixed(1);
  $("#kpi-peak").textContent = city.peak_level;
  $("#kpi-speed-bar").style.width = `${Math.min(100, (speed / 60) * 100)}%`;
  $("#kpi-incidents").textContent = city.active_incident_count;
  $("#top-alert-count").textContent = city.active_incident_count;
  $("#kpi-worst").textContent = top?.name || "暂无";
  $("#kpi-worst-note").textContent = top ? `饱和度 ${Number(top.saturation).toFixed(2)} · 排队 ${top.queue_m}m` : "当前无拥堵排行";
  $("#kpi-worst-bar").style.width = `${Math.min(100, (Number(top?.saturation || 0) * 100))}%`;
  $("#data-timestamp").textContent = formatTimestamp(data.timestamp);
  $("#map-city-index").textContent = Number(city.congestion_index).toFixed(1);
  $("#map-city-speed").textContent = `${Number(city.avg_speed_kmh).toFixed(1)} km/h`;
}

function createSvgElement(name, attributes = {}) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
  return element;
}

function renderNetwork(data) {
  const svg = $("#network-map");
  svg.replaceChildren();
  const corridorRows = data.corridors || [];
  const greenwaveCount = corridorRows.filter((item) => item.greenwave_status === "已实现").length;
  $("#map-intersection-count").textContent = data.intersections.length;
  $("#map-corridor-count").textContent = corridorRows.length;
  $("#map-greenwave-count").textContent = greenwaveCount;

  corridorRows.forEach((corridor, corridorIndex) => {
    const y = 76 + corridorIndex * 88;
    const band = createSvgElement("rect", {
      x: 0,
      y: y - 40,
      width: 1120,
      height: 78,
      class: `network-band${corridorIndex % 2 ? " alt" : ""}`,
    });
    svg.appendChild(band);

    const shadow = createSvgElement("line", {
      x1: 146,
      x2: 1060,
      y1: y,
      y2: y,
      class: "network-line-shadow",
    });
    svg.appendChild(shadow);

    const line = createSvgElement("line", {
      x1: 146,
      x2: 1060,
      y1: y,
      y2: y,
      class: `network-line${corridor.road_class === "快速路" ? " main" : ""}`,
    });
    svg.appendChild(line);

    const dashed = createSvgElement("line", {
      x1: 146,
      x2: 1060,
      y1: y,
      y2: y,
      class: "network-dash",
    });
    svg.appendChild(dashed);

    const label = createSvgElement("text", {
      x: 16,
      y: y - 4,
      class: "network-label",
    });
    label.textContent = corridor.name;
    svg.appendChild(label);

    const meta = createSvgElement("text", {
      x: 16,
      y: y + 14,
      class: "network-meta",
    });
    meta.textContent = `${corridor.road_class} · ${Number(corridor.avg_speed_kmh).toFixed(1)} km/h · 带宽 ${corridor.greenwave_bandwidth_s}s`;
    svg.appendChild(meta);

    const statusText = createSvgElement("text", {
      x: 1095,
      y: y + 4,
      class: "network-meta",
      "text-anchor": "end",
      fill: corridor.greenwave_status === "已实现" ? "#4fd1a5" : "#e0a232",
    });
    statusText.textContent = corridor.greenwave_status;
    svg.appendChild(statusText);

    const nodes = data.intersections.filter((item) => item.corridor_id === corridor.id);
    nodes.forEach((intersection, nodeIndex) => {
      const usableWidth = 830;
      const x = 175 + ((nodeIndex + 0.5) * usableWidth) / Math.max(nodes.length, 1);
      const color = saturationColor(intersection.saturation);
      const selected = intersection.id === state.selectedIntersection?.id;
      const halo = createSvgElement("circle", {
        cx: x,
        cy: y,
        r: selected ? 16 : 13,
        fill: color,
        opacity: selected ? 0.22 : 0.12,
        class: "network-node-halo",
      });
      svg.appendChild(halo);

      const circle = createSvgElement("circle", {
        cx: x,
        cy: y,
        r: selected ? 10 : 8,
        fill: color,
        class: "network-node",
        tabindex: "0",
        role: "button",
        "aria-label": `${intersection.name}，饱和度 ${intersection.saturation}`,
      });
      circle.addEventListener("click", () => selectIntersection(intersection));
      circle.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") selectIntersection(intersection);
      });
      svg.appendChild(circle);

      const id = createSvgElement("text", {
        x,
        y: y + 28,
        class: "network-id",
      });
      id.textContent = intersection.id;
      svg.appendChild(id);
    });
  });
}

function renderNetworkTable(data = state.dashboard) {
  if (!data) return;
  const query = ($("#intersection-search")?.value || "").trim().toLowerCase();
  const corridor = $("#corridor-filter")?.value || "";
  const filter = $("#corridor-filter");
  if (filter && filter.options.length === 1) {
    data.corridors.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.id;
      option.textContent = item.name;
      filter.appendChild(option);
    });
  }

  const rows = data.intersections.filter((item) => {
    const matchesQuery = !query || `${item.id} ${item.name}`.toLowerCase().includes(query);
    const matchesCorridor = !corridor || item.corridor_id === corridor;
    return matchesQuery && matchesCorridor;
  });

  $("#network-row-count").textContent = `${rows.length} / ${data.intersections.length} 个`;
  $("#intersection-table-body").innerHTML = rows.map((item) => `
    <tr data-intersection-id="${escapeHtml(item.id)}" class="${item.id === state.selectedIntersection?.id ? "is-selected" : ""}">
      <td><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.id)}</small></td>
      <td>${escapeHtml(item.corridor)}</td>
      <td><span class="status-text ${saturationClass(item.saturation)}">${escapeHtml(item.los)}</span></td>
      <td>${Number(item.saturation).toFixed(2)}</td>
      <td>${Number(item.avg_delay_s).toFixed(1)}s</td>
      <td>${item.queue_m}m</td>
      <td>${escapeHtml(item.current_phase || "--")}</td>
    </tr>
  `).join("");

  $("#intersection-table-body").querySelectorAll("tr").forEach((row) => {
    row.addEventListener("click", () => {
      const selected = data.intersections.find((item) => item.id === row.dataset.intersectionId);
      if (selected) selectIntersection(selected);
    });
  });
}

function renderNetworkDetail(intersection) {
  if (!intersection) return;
  $("#network-detail-id").textContent = intersection.id;
  const approaches = intersection.queue || [];
  $("#network-detail").innerHTML = `
    <section class="detail-hero">
      <span>${escapeHtml(intersection.corridor)} · ${escapeHtml(intersection.district)} · ${escapeHtml(intersection.road_class)}</span>
      <strong>${escapeHtml(intersection.name)}</strong>
    </section>
    <div class="detail-metrics">
      <div><span>服务水平</span><strong>${escapeHtml(intersection.los)}</strong></div>
      <div><span>平均饱和度</span><strong>${Number(intersection.saturation).toFixed(2)}</strong></div>
      <div><span>平均延误</span><strong>${Number(intersection.avg_delay_s).toFixed(1)}s</strong></div>
      <div><span>最大排队</span><strong>${intersection.queue_m}m</strong></div>
    </div>
    <div class="approach-list">
      ${approaches.map((item) => `
        <div class="approach-row">
          <span>${escapeHtml(item.approach)}</span>
          <div class="bar-track"><div class="bar-fill ${saturationClass(item.saturation)}" style="width:${Math.min(100, item.saturation * 100)}%"></div></div>
          <strong>${item.queue_m}m</strong>
        </div>
      `).join("")}
    </div>
    <button class="action-chip" id="network-detail-ask" type="button">提交 Copilot 深研判</button>
  `;
  $("#network-detail-ask").addEventListener("click", () => {
    $("#chat-input").value = `分析 ${intersection.id} ${intersection.name} 当前运行状态，并给出改善建议。`;
    $("#chat-input").focus();
  });
}

function selectIntersection(intersection) {
  state.selectedIntersection = intersection;
  const inspector = $("#intersection-inspector");
  inspector.innerHTML = `
    <span class="inspector-kicker">${escapeHtml(intersection.id)} · ${escapeHtml(intersection.road_class)}</span>
    <strong>${escapeHtml(intersection.name)}</strong>
    <span class="inspector-id">饱和度 ${Number(intersection.saturation).toFixed(2)} · ${escapeHtml(intersection.los)} 级 · 最大排队 ${intersection.queue_m}m</span>
    <button class="action-chip" id="inspect-ask" type="button">提交 Copilot 深研判</button>
  `;
  $("#inspect-ask").addEventListener("click", () => {
    $("#chat-input").value = `分析 ${intersection.id} ${intersection.name} 当前运行状态，并给出改善建议。`;
    $("#chat-input").focus();
  });
  renderNetwork(state.dashboard);
  renderNetworkDetail(intersection);
  renderNetworkTable(state.dashboard);
}

function renderIncidents(data) {
  const incidents = data.incidents || [];
  const critical = incidents.filter((item) => item.severity === "critical").length;
  const major = incidents.filter((item) => item.severity === "major").length;
  const construction = incidents.filter((item) => item.severity === "construction").length;
  $("#incident-count").textContent = incidents.length;
  $("#incident-critical").textContent = critical;
  $("#incident-major").textContent = major;
  $("#incident-construction").textContent = construction;
  $("#kpi-incident-note").textContent = incidents.length ? `${critical} 重大` : "无事件";

  const list = $("#incident-list");
  if (!incidents.length) {
    list.innerHTML = '<div class="empty-state">当前没有活跃交通事件</div>';
    return;
  }

  list.innerHTML = incidents.map((incident) => `
    <article class="event-item">
      <span class="severity-bar severity-${escapeHtml(incident.severity)}"></span>
      <div>
        <h3>${escapeHtml(incident.type)} · ${escapeHtml(incident.location)}</h3>
        <p>${escapeHtml(incident.lane_block)}，预计 ${formatTimestamp(incident.expected_clear)} 恢复</p>
        <div class="event-meta">
          <span class="tag">${escapeHtml(incident.severity_label)}</span>
          <span class="tag">影响${escapeHtml(incident.impact_level)}</span>
          <span class="tag">${escapeHtml(incident.status)}</span>
        </div>
      </div>
    </article>
  `).join("");
}

function renderIncidentCommand(data = state.dashboard) {
  if (!data) return;
  const incidents = data.incidents || [];
  $("#incident-queue-count").textContent = `${incidents.length} 起`;
  const queue = $("#incident-command-list");
  const board = $("#dispatch-board");

  if (!incidents.length) {
    queue.innerHTML = '<div class="empty-state">当前没有活跃交通事件</div>';
    board.innerHTML = `
      <div class="detail-metrics">
        <div><span>事件队列</span><strong>0</strong></div>
        <div><span>待恢复</span><strong>0</strong></div>
        <div><span>重大事件</span><strong>0</strong></div>
        <div><span>平均恢复时间</span><strong>--</strong></div>
      </div>
      <div class="empty-state">资源处于待命状态</div>
    `;
    return;
  }

  queue.innerHTML = incidents.map((incident) => `
    <article class="incident-command-item">
      <span class="incident-level ${escapeHtml(incident.severity)}">${escapeHtml(incident.severity_label)}</span>
      <div>
        <h3>${escapeHtml(incident.type)} · ${escapeHtml(incident.location)}</h3>
        <p>${escapeHtml(incident.lane_block)} · 影响等级${escapeHtml(incident.impact_level)}</p>
        <div class="event-meta">
          <span class="tag">${escapeHtml(incident.intersection_id)}</span>
          <span class="tag">${escapeHtml(incident.status)}</span>
        </div>
      </div>
      <div class="incident-time">
        <strong>${formatTime(incident.expected_clear)}</strong>
        <span>预计恢复</span>
      </div>
    </article>
  `).join("");

  const averageMinutes = incidents.reduce((total, incident) => {
    const start = new Date(incident.start_time).getTime();
    const end = new Date(incident.expected_clear).getTime();
    return total + Math.max(0, (end - start) / 60000);
  }, 0) / incidents.length;
  const critical = incidents.filter((item) => item.severity === "critical").length;
  board.innerHTML = `
    <div class="detail-metrics">
      <div><span>事件队列</span><strong>${incidents.length}</strong></div>
      <div><span>重大事件</span><strong>${critical}</strong></div>
      <div><span>平均恢复时间</span><strong>${Math.round(averageMinutes)}m</strong></div>
      <div><span>资源状态</span><strong>可调度</strong></div>
    </div>
    <div class="dispatch-timeline">
      ${incidents.map((incident) => `
        <div class="timeline-row">
          <span class="timeline-marker"></span>
          <div>
            <strong>${escapeHtml(incident.type)} · ${escapeHtml(incident.location)}</strong>
            <small>发现 ${formatTime(incident.start_time)} · 预计恢复 ${formatTime(incident.expected_clear)}</small>
          </div>
        </div>
      `).join("")}
    </div>
  `;
}

function renderCorridors(data) {
  const container = $("#corridor-list");
  if (!container) return;
  const greenwave = (data.corridors || []).filter((item) => item.greenwave_status === "已实现").length;
  const summary = $("#greenwave-summary");
  if (summary) summary.textContent = `${greenwave}/${data.corridors?.length || 0} 绿波正常`;
  container.innerHTML = (data.corridors || []).map((corridor) => {
    const level = saturationClass(corridor.saturation);
    return `
      <div class="metric-row">
        <div>
          <strong>${escapeHtml(corridor.name)}</strong>
          <small>${escapeHtml(corridor.road_class)} · ${escapeHtml(corridor.greenwave_status)}</small>
        </div>
        <div class="bar-track" title="平均饱和度 ${Number(corridor.saturation).toFixed(2)}">
          <div class="bar-fill ${level}" style="width:${Math.min(100, corridor.saturation * 100)}%"></div>
        </div>
        <span class="metric-value">${Number(corridor.avg_speed_kmh).toFixed(1)}<small> km/h</small></span>
      </div>
    `;
  }).join("");
}

function renderSignalBoard(data = state.dashboard) {
  if (!data) return;
  const container = $("#signal-corridor-board");
  container.innerHTML = data.corridors.map((corridor) => {
    const intersections = data.intersections.filter((item) => item.corridor_id === corridor.id);
    const level = saturationClass(corridor.saturation);
    return `
      <article class="signal-card">
        <div>
          <h3>${escapeHtml(corridor.name)}</h3>
          <p>${escapeHtml(corridor.road_class)} · ${Number(corridor.avg_speed_kmh).toFixed(1)} km/h</p>
          <div class="signal-intersections">
            ${intersections.map((item) => `<button type="button" data-signal-id="${escapeHtml(item.id)}">${escapeHtml(item.id)}</button>`).join("")}
          </div>
        </div>
        <div>
          <div class="bar-track"><div class="bar-fill ${level}" style="width:${Math.min(100, corridor.saturation * 100)}%"></div></div>
          <p>饱和度 ${Number(corridor.saturation).toFixed(2)} · 带宽 ${corridor.greenwave_bandwidth_s}s</p>
        </div>
        <span class="status status-text ${corridor.greenwave_status === "已实现" ? "safe" : "watch"}">${escapeHtml(corridor.greenwave_status)}</span>
      </article>
    `;
  }).join("");

  container.querySelectorAll("[data-signal-id]").forEach((button) => {
    button.addEventListener("click", () => loadSignalDetail(button.dataset.signalId));
  });
}

async function loadSignalDetail(intersectionId) {
  state.selectedSignalIntersection = intersectionId;
  $("#signal-detail-id").textContent = intersectionId;
  $("#signal-detail").innerHTML = '<div class="empty-state">正在读取配时方案</div>';
  try {
    const response = await fetch(`/traffic/intersection/${encodeURIComponent(intersectionId)}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.signalDetail = await response.json();
    renderSignalDetail(state.signalDetail);
  } catch (error) {
    $("#signal-detail").innerHTML = `<div class="empty-state">配时读取失败：${escapeHtml(error.message)}</div>`;
  }
}

function renderSignalDetail(data) {
  const status = data.status;
  const signal = data.signal;
  const optimization = data.optimization || {};
  const maxGreen = Math.max(...signal.phases.map((phase) => phase.green_s), 1);
  const suggestions = optimization.suggestions || [];
  $("#signal-detail").innerHTML = `
    <section class="detail-hero">
      <span>${escapeHtml(status.corridor)} · ${escapeHtml(status.district)}</span>
      <strong>${escapeHtml(status.name)}</strong>
    </section>
    <div class="detail-metrics">
      <div><span>当前方案</span><strong>${escapeHtml(signal.current_plan)}</strong></div>
      <div><span>周期</span><strong>${signal.cycle_s}s</strong></div>
      <div><span>相位差</span><strong>${signal.offset_s}s</strong></div>
      <div><span>协调组</span><strong>${escapeHtml(signal.coordination_group)}</strong></div>
    </div>
    <div class="phase-list">
      ${signal.phases.map((phase) => `
        <div class="phase-item">
          <div>
            <strong>${escapeHtml(phase.name)}</strong>
            <div class="phase-bar"><i style="width:${(phase.green_s / maxGreen) * 100}%"></i></div>
          </div>
          <span>${phase.green_s}s</span>
        </div>
      `).join("")}
    </div>
    <div class="resource-status">
      <div class="resource-head"><span>优化建议</span><small>${suggestions.length} 条</small></div>
      ${suggestions.length ? suggestions.map((item, index) => `
        <div class="insight-item">
          <span class="insight-index">${String(index + 1).padStart(2, "0")}</span>
          <div><strong>${escapeHtml(item.proposed)}</strong><p>${escapeHtml(item.expected_gain)}</p></div>
        </div>
      `).join("") : '<div class="empty-state">当前无需调整</div>'}
    </div>
  `;
}

function renderDistricts(data) {
  const container = $("#district-list");
  const worst = [...(data.districts || [])].sort(
    (left, right) => right.congestion_index - left.congestion_index
  )[0];
  $("#district-summary").textContent = worst ? `${worst.name}压力最高` : "--";
  container.innerHTML = (data.districts || []).map((district) => {
    const level = saturationClass(district.congestion_index / 10);
    return `
      <div class="metric-row">
        <div>
          <strong>${escapeHtml(district.name)}</strong>
          <small>全市排名 ${district.rank_in_city} · ${district.intersection_count} 个路口</small>
        </div>
        <div class="bar-track" title="拥堵指数 ${district.congestion_index}">
          <div class="bar-fill ${level}" style="width:${Math.min(100, district.congestion_index * 10)}%"></div>
        </div>
        <span class="metric-value">${Number(district.congestion_index).toFixed(1)}</span>
      </div>
    `;
  }).join("");
}

function renderInsights(data) {
  const intersections = [...(data.intersections || [])].sort(
    (left, right) => right.saturation - left.saturation
  );
  const corridors = [...(data.corridors || [])].sort(
    (left, right) => right.saturation - left.saturation
  );
  const districts = [...(data.districts || [])].sort(
    (left, right) => right.congestion_index - left.congestion_index
  );
  const incident = (data.incidents || [])[0];
  const insights = [];

  if (intersections[0]) {
    insights.push({
      title: `优先关注 ${intersections[0].name}`,
      detail: `饱和度 ${Number(intersections[0].saturation).toFixed(2)}，最大排队 ${intersections[0].queue_m}m，LOS ${intersections[0].los}。`,
    });
  }
  if (corridors[0]) {
    insights.push({
      title: `${corridors[0].name}干线负荷最高`,
      detail: `平均车速 ${Number(corridors[0].avg_speed_kmh).toFixed(1)} km/h，绿波状态为“${corridors[0].greenwave_status}”。`,
    });
  }
  if (districts[0]) {
    insights.push({
      title: `${districts[0].name}压力排名第一`,
      detail: `辖区指数 ${Number(districts[0].congestion_index).toFixed(1)}，建议联动周边路口观察排队外溢。`,
    });
  }
  if (incident) {
    insights.push({
      title: `${incident.type}影响 ${incident.location}`,
      detail: `${incident.lane_block}，预计 ${formatTimestamp(incident.expected_clear)} 恢复。`,
    });
  }

  const container = $("#insight-list");
  container.innerHTML = insights.slice(0, 4).map((item, index) => `
    <div class="insight-item">
      <span class="insight-index">${String(index + 1).padStart(2, "0")}</span>
      <div>
        <strong>${escapeHtml(item.title)}</strong>
        <p>${escapeHtml(item.detail)}</p>
      </div>
    </div>
  `).join("");
}

async function loadDashboard() {
  const refresh = $("#refresh-dashboard");
  refresh.classList.add("is-loading");
  try {
    const response = await fetch("/dashboard", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`Dashboard HTTP ${response.status}`);
    const data = await response.json();
    state.dashboard = data;
    renderKpis(data);
    renderNetwork(data);
    renderIncidents(data);
    renderCorridors(data);
    renderDistricts(data);
    renderInsights(data);
    renderNetworkTable(data);
    renderSignalBoard(data);
    renderIncidentCommand(data);
    if (!state.selectedIntersection && data.intersections[0]) {
      state.selectedIntersection = data.intersections[0];
      renderNetworkDetail(state.selectedIntersection);
    }
    if (state.activeView === "signals" && !state.selectedSignalIntersection && data.intersections[0]) {
      loadSignalDetail(data.intersections[0].id);
    }
  } catch (error) {
    showToast(`态势数据加载失败：${error.message}`);
  } finally {
    refresh.classList.remove("is-loading");
  }
}

function renderMarkdown(value) {
  const escaped = escapeHtml(value);
  const lines = escaped.split(/\r?\n/);
  const output = [];
  let listOpen = false;

  lines.forEach((line) => {
    if (/^- /.test(line)) {
      if (!listOpen) {
        output.push("<ul>");
        listOpen = true;
      }
      output.push(`<li>${line.slice(2)}</li>`);
      return;
    }
    if (listOpen) {
      output.push("</ul>");
      listOpen = false;
    }
    if (/^### /.test(line)) {
      output.push(`<h3>${line.slice(4)}</h3>`);
    } else if (/^## /.test(line)) {
      output.push(`<h3>${line.slice(3)}</h3>`);
    } else if (/^# /.test(line)) {
      output.push(`<h3>${line.slice(2)}</h3>`);
    } else if (line.trim()) {
      output.push(`<p>${line}</p>`);
    }
  });
  if (listOpen) output.push("</ul>");

  return output
    .join("")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`(.+?)`/g, "<code>$1</code>");
}

function appendUserMessage(text) {
  const log = $("#chat-log");
  const element = document.createElement("article");
  element.className = "message user";
  element.textContent = text;
  log.appendChild(element);
  log.scrollTop = log.scrollHeight;
}

function createAssistantMessage() {
  const log = $("#chat-log");
  const element = document.createElement("article");
  element.className = "message assistant streaming";
  element.innerHTML = `
    <div class="message-meta"><span>TRAFFICGRAPH</span><small>实时研判</small></div>
    <div class="trace"></div>
    <div class="message-body"><p>正在分析…</p></div>
    <div class="intent-stack"></div>
    <div class="action-stack"></div>
    <div class="card-stack"></div>
  `;
  log.appendChild(element);
  log.scrollTop = log.scrollHeight;
  return element;
}

function addTrace(message, label, detail) {
  const trace = message.querySelector(".trace");
  const item = document.createElement("div");
  item.className = "trace-item";
  item.innerHTML = `<strong>${escapeHtml(label)}</strong><span>${escapeHtml(detail)}</span>`;
  trace.appendChild(item);
  $("#chat-log").scrollTop = $("#chat-log").scrollHeight;
}

function numericValue(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function chartLabel(value, maxLength = 7) {
  const text = String(value ?? "");
  return text.length > maxLength ? `${text.slice(0, maxLength)}…` : text;
}

function aggregateChartRows(rows, xKey, valueKey) {
  const grouped = new Map();
  rows.forEach((row) => {
    const label = String(row[xKey] ?? "--");
    grouped.set(label, (grouped.get(label) || 0) + numericValue(row[valueKey]));
  });
  return Array.from(grouped, ([label, value]) => ({ label, value })).slice(0, 10);
}

function renderBarChart(chart, rows) {
  const series = chart.series[0];
  const data = aggregateChartRows(rows, chart.x_key, series.key);
  const maxValue = Math.max(...data.map((item) => item.value), 1);
  const width = 520;
  const height = 190;
  const left = 34;
  const right = 12;
  const top = 16;
  const bottom = 34;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const slot = plotWidth / Math.max(data.length, 1);
  const barWidth = Math.min(46, slot * 0.58);
  const bars = data.map((item, index) => {
    const barHeight = (item.value / maxValue) * plotHeight;
    const x = left + index * slot + (slot - barWidth) / 2;
    const y = top + plotHeight - barHeight;
    return `
      <rect x="${x}" y="${y}" width="${barWidth}" height="${barHeight}" rx="2" fill="${escapeHtml(series.color || "#36d39e")}"></rect>
      <text x="${x + barWidth / 2}" y="${y - 4}" class="chart-value" text-anchor="middle">${item.value.toFixed(item.value % 1 ? 1 : 0)}</text>
      <text x="${x + barWidth / 2}" y="${height - 11}" class="chart-label" text-anchor="middle">${escapeHtml(chartLabel(item.label))}</text>
    `;
  }).join("");
  return `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(chart.title)}">
      <line x1="${left}" y1="${top + plotHeight}" x2="${width - right}" y2="${top + plotHeight}" class="chart-axis"></line>
      <line x1="${left}" y1="${top}" x2="${left}" y2="${top + plotHeight}" class="chart-axis"></line>
      ${bars}
    </svg>
  `;
}

function renderLineChart(chart, rows) {
  const series = chart.series[0];
  const data = rows.slice(0, 48);
  const values = data.map((row) => numericValue(row[series.key]));
  const maxValue = Math.max(...values, 1);
  const minValue = Math.min(...values, 0);
  const range = Math.max(maxValue - minValue, 1);
  const width = 520;
  const height = 190;
  const left = 34;
  const right = 12;
  const top = 16;
  const bottom = 30;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const points = data.map((row, index) => {
    const x = left + (index / Math.max(data.length - 1, 1)) * plotWidth;
    const y = top + plotHeight - ((numericValue(row[series.key]) - minValue) / range) * plotHeight;
    return { x, y, label: row[chart.x_key] };
  });
  const polyline = points.map((point) => `${point.x},${point.y}`).join(" ");
  const pointDots = points.filter((_, index) => index % Math.max(1, Math.floor(points.length / 8)) === 0).map((point) => `
    <circle cx="${point.x}" cy="${point.y}" r="2.5" fill="${escapeHtml(series.color || "#36d39e")}"></circle>
  `).join("");
  const xLabels = points.filter((_, index) => index % Math.max(1, Math.floor(points.length / 5)) === 0).map((point) => `
    <text x="${point.x}" y="${height - 9}" class="chart-label" text-anchor="middle">${escapeHtml(chartLabel(String(point.label).slice(-5), 5))}</text>
  `).join("");
  return `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(chart.title)}">
      <line x1="${left}" y1="${top + plotHeight}" x2="${width - right}" y2="${top + plotHeight}" class="chart-axis"></line>
      <line x1="${left}" y1="${top}" x2="${left}" y2="${top + plotHeight}" class="chart-axis"></line>
      <polyline points="${polyline}" fill="none" stroke="${escapeHtml(series.color || "#36d39e")}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"></polyline>
      ${pointDots}
      ${xLabels}
    </svg>
  `;
}

function renderDonutChart(chart, rows) {
  const series = chart.series[0];
  const data = aggregateChartRows(rows, chart.x_key, series.key);
  const total = data.reduce((sum, item) => sum + item.value, 0) || 1;
  const colors = ["#36d39e", "#eab04a", "#ef704f", "#4abed0", "#a48be0"];
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  const circles = data.map((item, index) => {
    const length = (item.value / total) * circumference;
    const circle = `
      <circle cx="92" cy="90" r="${radius}" fill="none" stroke="${colors[index % colors.length]}"
        stroke-width="20" stroke-dasharray="${length} ${circumference - length}"
        stroke-dashoffset="${-offset}" transform="rotate(-90 92 90)"></circle>
    `;
    offset += length;
    return circle;
  }).join("");
  const legend = data.map((item, index) => `
    <g transform="translate(185 ${28 + index * 23})">
      <rect width="7" height="7" rx="2" fill="${colors[index % colors.length]}"></rect>
      <text x="13" y="6" class="chart-label">${escapeHtml(chartLabel(item.label, 12))}</text>
      <text x="315" y="6" class="chart-value" text-anchor="end">${item.value}</text>
    </g>
  `).join("");
  return `
    <svg viewBox="0 0 520 190" role="img" aria-label="${escapeHtml(chart.title)}">
      ${circles}
      <text x="92" y="87" class="chart-value" text-anchor="middle">${total}</text>
      <text x="92" y="101" class="chart-label" text-anchor="middle">${escapeHtml(chart.unit || "合计")}</text>
      ${legend}
    </svg>
  `;
}

function createChartElement(chart, rows) {
  const element = document.createElement("section");
  element.className = "chart-block";
  const renderer = {
    bar: renderBarChart,
    line: renderLineChart,
    donut: renderDonutChart,
  }[chart.type] || renderBarChart;
  element.innerHTML = `<h4>${escapeHtml(chart.title)}</h4>${renderer(chart, rows)}`;
  return element;
}

function createReportTable(card) {
  const columns = card.table?.columns || [];
  const rows = card.table?.rows || [];
  const download = card.download || {};
  const head = columns.map((column) => `<th>${escapeHtml(column.label)}${column.unit ? ` (${escapeHtml(column.unit)})` : ""}</th>`).join("");
  const body = rows.slice(0, 100).map((row) => `
    <tr>${columns.map((column) => `<td>${escapeHtml(row[column.key] ?? "")}</td>`).join("")}</tr>
  `).join("");
  const element = document.createElement("section");
  element.className = "report-table";
  element.innerHTML = `
    <div class="report-table-header">
      <strong>数据表</strong>
      ${download.task_id ? `<a href="/export/${encodeURIComponent(download.task_id)}" download>下载 CSV</a>` : ""}
    </div>
    <div class="report-table-scroll">
      <table class="data-table">
        <thead><tr>${head}</tr></thead>
        <tbody>${body}</tbody>
      </table>
    </div>
  `;
  return element;
}

function createReportContent(card) {
  const content = document.createElement("div");
  content.className = "report-content";
  const charts = document.createElement("div");
  charts.className = "report-charts";
  (card.charts || []).forEach((chart) => charts.appendChild(createChartElement(chart, card.table?.rows || [])));
  if (!card.charts?.length) {
    charts.innerHTML = '<div class="empty-state">该报告未配置图表</div>';
  }
  content.appendChild(charts);
  content.appendChild(createReportTable(card));
  return content;
}

function openReportDrawer(card) {
  $("#report-drawer-title").textContent = card.title || "数据报告";
  const body = $("#report-drawer-body");
  body.replaceChildren(createReportContent(card));
  const drawer = $("#report-drawer");
  drawer.classList.add("is-open");
  drawer.setAttribute("aria-hidden", "false");
}

function closeReportDrawer() {
  const drawer = $("#report-drawer");
  drawer.classList.remove("is-open");
  drawer.setAttribute("aria-hidden", "true");
}

function renderDataCard(message, card) {
  const element = document.createElement("section");
  element.className = "data-card-embedded";
  element.appendChild(createReportContent(card));
  message.querySelector(".card-stack").appendChild(element);
}

function routeToView(route = "") {
  if (route.startsWith("/signal/")) return "signals";
  if (route.startsWith("/incident/") || route.startsWith("/dispatch/") || route.startsWith("/alarm/")) return "incidents";
  if (route.startsWith("/intersection/") || route.startsWith("/analysis/flow") || route.startsWith("/video/")) return "network";
  return "overview";
}

function handleSseEvent(message, eventType, payload) {
  const body = message.querySelector(".message-body");
  if (eventType === "thinking") {
    if (body.querySelector("p")?.textContent === "正在分析…") body.replaceChildren();
    addTrace(message, "思考", payload.text || "");
  } else if (eventType === "tool_call") {
    addTrace(message, "调用", `${payload.name} ${JSON.stringify(payload.args || {})}`);
  } else if (eventType === "tool_result") {
    const result = payload.result;
    const summary = result?.error ? result.error : `${payload.name} 已返回`;
    addTrace(message, "结果", summary);
  } else if (eventType === "rag_sources") {
    const count = Array.isArray(payload.source_snippets) ? payload.source_snippets.length : 0;
    addTrace(message, "知识库", `命中 ${count} 条来源`);
  } else if (eventType === "intent_plan") {
    const stack = message.querySelector(".intent-stack");
    (payload.intents || []).forEach((intent) => {
      const chip = document.createElement("span");
      chip.className = "intent-chip";
      chip.textContent = `${intent.id}. ${intent.description}`;
      stack.appendChild(chip);
    });
  } else if (eventType === "text") {
    message.dataset.answer = `${message.dataset.answer || ""}${payload.text || ""}`;
    body.innerHTML = renderMarkdown(message.dataset.answer);
  } else if (eventType === "action") {
    const button = document.createElement("button");
    button.className = "action-chip";
    button.type = "button";
    button.textContent = `待确认 · ${payload.name || payload.route}`;
    button.addEventListener("click", () => {
      const view = routeToView(payload.route);
      switchView(view);
      showToast(`已定位到${VIEW_LABELS[view]}，未自动打开外部页面`);
    });
    message.querySelector(".action-stack").appendChild(button);
  } else if (eventType === "data_card") {
    renderDataCard(message, payload);
  } else if (eventType === "error") {
    body.innerHTML = `<p>执行失败：${escapeHtml(payload.error || "未知错误")}</p>`;
  }
  $("#chat-log").scrollTop = $("#chat-log").scrollHeight;
}

function parseSseBlock(block) {
  let eventType = "message";
  const dataLines = [];
  block.split(/\r?\n/).forEach((line) => {
    if (line.startsWith("event:")) eventType = line.slice(6).trim();
    if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  });
  if (!dataLines.length) return null;
  try {
    return { eventType, payload: JSON.parse(dataLines.join("\n")) };
  } catch {
    return { eventType, payload: { text: dataLines.join("\n") } };
  }
}

async function sendMessage(text) {
  if (!text.trim() || state.sending) return;
  state.sending = true;
  $("#send-button").disabled = true;
  $("#agent-state").textContent = "正在调度工具";
  appendUserMessage(text.trim());
  const message = createAssistantMessage();

  try {
    const response = await fetch("/stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify({
        user_input: text.trim(),
        thread_id: `web-${crypto.randomUUID()}`,
        page_context: {
          current_route: VIEW_ROUTES[state.activeView],
          area_id: state.context,
        },
      }),
    });
    if (!response.ok || !response.body) {
      throw new Error(`HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const blocks = buffer.split(/\r?\n\r?\n/);
      buffer = blocks.pop() || "";
      blocks.forEach((block) => {
        const parsed = parseSseBlock(block);
        if (parsed) handleSseEvent(message, parsed.eventType, parsed.payload);
      });
      if (done) break;
    }
  } catch (error) {
    handleSseEvent(message, "error", { error: error.message });
  } finally {
    message.classList.remove("streaming");
    const body = message.querySelector(".message-body");
    if (!body.textContent.trim() && !message.dataset.answer) body.innerHTML = "<p>本轮没有返回文本。</p>";
    state.sending = false;
    $("#send-button").disabled = false;
    $("#agent-state").textContent = "等待指令";
    $("#chat-input").focus();
  }
}

function buildCurrentReport() {
  const data = state.dashboard;
  if (!data) throw new Error("态势数据尚未加载");

  if (state.activeView === "overview") {
    const rows = (data.city.top5_congested_intersections || []).map((item, index) => ({
      rank: index + 1,
      name: item.name,
      saturation: item.saturation,
      queue_m: item.queue_m,
    }));
    return {
      title: "上海市全市交通态势 Top5 报告",
      columns: [
        { key: "rank", label: "排名" },
        { key: "name", label: "路口" },
        { key: "saturation", label: "饱和度" },
        { key: "queue_m", label: "排队长度", unit: "m" },
      ],
      rows,
      charts: [{
        type: "bar",
        title: "拥堵 Top5 饱和度",
        x_key: "name",
        series: [{ key: "saturation", label: "饱和度", color: "#36d39e" }],
        orientation: "vertical",
      }],
      filename: "shanghai_traffic_top5.csv",
    };
  }

  if (state.activeView === "network") {
    const rows = data.intersections.map((item) => ({
      id: item.id,
      name: item.name,
      corridor: item.corridor,
      los: item.los,
      saturation: item.saturation,
      avg_delay_s: item.avg_delay_s,
      queue_m: item.queue_m,
      current_phase: item.current_phase,
    }));
    return {
      title: "上海市路口实时运行台账",
      columns: [
        { key: "id", label: "路口 ID" },
        { key: "name", label: "路口名称" },
        { key: "corridor", label: "干线" },
        { key: "los", label: "LOS" },
        { key: "saturation", label: "饱和度" },
        { key: "avg_delay_s", label: "平均延误", unit: "s" },
        { key: "queue_m", label: "排队长度", unit: "m" },
        { key: "current_phase", label: "当前相位" },
      ],
      rows,
      charts: [{
        type: "bar",
        title: "路口饱和度排名",
        x_key: "name",
        series: [{ key: "saturation", label: "饱和度", color: "#4abed0" }],
        orientation: "vertical",
      }],
      filename: "shanghai_intersection_ledger.csv",
    };
  }

  if (state.activeView === "signals") {
    if (!state.signalDetail) throw new Error("请先选择信号路口");
    const signal = state.signalDetail.signal;
    const rows = signal.phases.map((phase) => ({
      phase: phase.name,
      green_s: phase.green_s,
      yellow_s: phase.yellow_s,
      min_green_s: phase.min_green_s,
    }));
    return {
      title: `${signal.intersection_name} 配时报告`,
      columns: [
        { key: "phase", label: "相位" },
        { key: "green_s", label: "绿灯", unit: "s" },
        { key: "yellow_s", label: "黄灯", unit: "s" },
        { key: "min_green_s", label: "最小绿灯", unit: "s" },
      ],
      rows,
      charts: [{
        type: "bar",
        title: "相位绿灯时间",
        x_key: "phase",
        series: [{ key: "green_s", label: "绿灯时间", color: "#eab04a" }],
        unit: "s",
      }, {
        type: "donut",
        title: "绿灯时间构成",
        x_key: "phase",
        series: [{ key: "green_s", label: "绿灯时间", color: "#36d39e" }],
        unit: "s",
      }],
      filename: `${signal.intersection_id}_${signal.current_plan}_signal_report.csv`,
    };
  }

  const incidents = data.incidents || [];
  const rows = incidents.map((incident, index) => ({
    sequence: index + 1,
    type: incident.type,
    severity: incident.severity_label,
    location: incident.location,
    lane_block: incident.lane_block,
    start_time: incident.start_time,
    expected_clear: incident.expected_clear,
    status: incident.status,
    incident_count: 1,
  }));
  return {
    title: "上海市交通事件处置报告",
    columns: [
      { key: "sequence", label: "序号" },
      { key: "type", label: "事件类型" },
      { key: "severity", label: "严重度" },
      { key: "location", label: "位置" },
      { key: "lane_block", label: "占道情况" },
      { key: "start_time", label: "发现时间" },
      { key: "expected_clear", label: "预计恢复" },
      { key: "status", label: "状态" },
    ],
    rows,
    charts: [{
      type: "donut",
      title: "事件严重度分布",
      x_key: "severity",
      series: [{ key: "incident_count", label: "事件数", color: "#ef704f" }],
      unit: "起",
    }],
    filename: "shanghai_incident_report.csv",
  };
}

async function exportCurrentView() {
  const button = $("#export-view");
  button.disabled = true;
  button.textContent = "生成中";
  try {
    const payload = buildCurrentReport();
    const response = await fetch("/report/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const card = await response.json();
    if (!response.ok) throw new Error(card.detail || `HTTP ${response.status}`);
    openReportDrawer(card);
  } catch (error) {
    showToast(`报告生成失败：${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = "导出当前视图";
  }
}

function bindInteractions() {
  $("#refresh-dashboard").addEventListener("click", loadDashboard);
  $("#export-view").addEventListener("click", exportCurrentView);
  $("#close-report").addEventListener("click", closeReportDrawer);
  $("#chat-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const input = $("#chat-input");
    const text = input.value;
    input.value = "";
    sendMessage(text);
  });
  $("#chat-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      $("#chat-form").requestSubmit();
    }
  });
  document.querySelectorAll("[data-prompt]").forEach((button) => {
    button.addEventListener("click", () => {
      sendMessage(button.dataset.prompt);
    });
  });
  document.querySelectorAll(".context-bar button").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".context-bar button").forEach((item) => item.classList.remove("is-active"));
      button.classList.add("is-active");
      state.context = button.dataset.context === "中心商务区" ? "DIST-CBD" : "上海全市";
      showToast(`分析上下文已切换为 ${button.textContent}`);
    });
  });
  document.querySelectorAll(".rail-button[data-view]").forEach((button) => {
    button.addEventListener("click", () => {
      switchView(button.dataset.view);
    });
  });
  $("#intersection-search").addEventListener("input", () => renderNetworkTable());
  $("#corridor-filter").addEventListener("change", () => renderNetworkTable());
  window.addEventListener("hashchange", () => switchView(window.location.hash.slice(1), false));
}

function startClock() {
  const update = () => {
    $("#live-clock").textContent = new Date().toLocaleTimeString("zh-CN", { hour12: false });
  };
  update();
  window.setInterval(update, 1000);
}

bindInteractions();
switchView(window.location.hash.slice(1) || "overview", false);
startClock();
loadDashboard().then(() => {
  if (new URLSearchParams(window.location.search).get("report") === "1") {
    exportCurrentView();
  }
});
window.setInterval(loadDashboard, 30000);
