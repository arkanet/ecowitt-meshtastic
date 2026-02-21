const REFRESH_MS = 5000;
const HISTORY_REFRESH_MS = 60000;
const MAX_LIVE_POINTS = 240;

function nowSec() { return Math.floor(Date.now() / 1000); }
function fmtTime(ts) {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function pushPoint(arr, x, y, maxLen) {
  arr.push({ x, y });
  if (arr.length > maxLen) arr.shift();
}

function setText(id, txt) {
  const el = document.getElementById(id);
  if (el) el.innerText = txt;
}

function setTrendIcon(elemId, trend) {
  const el = document.getElementById(elemId);
  if (!el) return;
  el.className = "trend-icon";
  if (trend === "up") {
    el.classList.add("trend-up");
    el.innerHTML = '<i class="fa-solid fa-arrow-trend-up"></i>';
  } else if (trend === "down") {
    el.classList.add("trend-down");
    el.innerHTML = '<i class="fa-solid fa-arrow-trend-down"></i>';
  } else {
    el.classList.add("trend-same");
    el.innerHTML = '<i class="fa-solid fa-minus"></i>';
  }
}

function badgeColorTemperature(t) {
  if (t < 5) return "bg-light text-dark";
  if (t < 10) return "bg-primary text-light";
  if (t < 20) return "bg-success text-light";
  if (t < 30) return "bg-warning text-dark";
  if (t < 40) return "bg-orange text-light";
  return "bg-danger text-light";
}
function badgeColorWind(w) {
  if (w < 10) return "bg-light text-dark";
  if (w < 30) return "bg-warning text-dark";
  if (w < 60) return "bg-orange text-light";
  return "bg-danger text-light";
}
function badgeColorSun(s) {
  if (s <= 0) return "bg-light text-dark";
  if (s < 250) return "bg-success text-light";
  if (s < 600) return "bg-warning text-dark";
  if (s < 900) return "bg-orange text-light";
  return "bg-danger text-light";
}
function badgeColorPressure(p) {
  const delta = Math.abs((Number(p) || 0) - 1013);
  if (delta < 5) return "bg-light text-dark";
  if (delta < 15) return "bg-success text-light";
  if (delta < 25) return "bg-warning text-dark";
  if (delta < 40) return "bg-orange text-light";
  return "bg-danger text-light";
}

let history = null;
let historyFetchedAt = 0;

async function fetchHistory(hours = 24) {
  const now = Date.now();
  if (history && (now - historyFetchedAt) < HISTORY_REFRESH_MS) return history;
  const r = await fetch(`/api/history?hours=${hours}`, { cache: "no-store" });
  history = await r.json();
  historyFetchedAt = now;
  return history;
}

function seriesFromHistory(key) {
  if (!history || !history[key]) return [];
  return history[key].map(([ts, v]) => ({ x: ts, y: v }));
}

// live buffers
const live = {
  temp: [],
  hum: [],
  ws: [],
  wd: [],
  sr: [],
  uv: [],
};

function makeLineChart(canvasId, datasets, scales) {
  return new Chart(document.getElementById(canvasId), {
    type: "line",
    data: { datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      parsing: false,
      plugins: { legend: { labels: { color: "#eee" } } },
      scales
    }
  });
}

// TEMP chart: live + 24h
const tempChart = makeLineChart("tempChart",
  [
    { label: "Temp (live) °C", data: [], borderWidth: 2, tension: 0.25, yAxisID: "yT" },
    { label: "Temp (24h) °C", data: [], borderWidth: 2, tension: 0.25, yAxisID: "yT" },
    { label: "Hum (live) %", data: [], borderWidth: 2, tension: 0.25, yAxisID: "yH" },
    { label: "Hum (24h) %", data: [], borderWidth: 2, tension: 0.25, yAxisID: "yH" },
  ],
  {
    x: { type: "linear", ticks: { color: "#eee", callback: v => fmtTime(v) } },
    yT: { type: "linear", position: "left", ticks: { color: "#eee" } },
    yH: { type: "linear", position: "right", min: 0, max: 100, ticks: { color: "#eee" }, grid: { drawOnChartArea: false } },
  }
);

// WIND chart: live + 24h
const windChart = makeLineChart("windChart",
  [
    { label: "Wind (live) km/h", data: [], borderWidth: 2, tension: 0.25, yAxisID: "yW" },
    { label: "Wind (24h) km/h", data: [], borderWidth: 2, tension: 0.25, yAxisID: "yW" },
    { label: "Dir (live) °", data: [], borderWidth: 2, tension: 0.25, yAxisID: "yD" },
    { label: "Dir (24h) °", data: [], borderWidth: 2, tension: 0.25, yAxisID: "yD" },
  ],
  {
    x: { type: "linear", ticks: { color: "#eee", callback: v => fmtTime(v) } },
    yW: { type: "linear", position: "left", beginAtZero: true, ticks: { color: "#eee" } },
    yD: { type: "linear", position: "right", min: 0, max: 360, ticks: { color: "#eee" }, grid: { drawOnChartArea: false } },
  }
);

// RAIN chart: default rainrate + yearly, but series contains all
const rainChart = makeLineChart("rainChart",
  [
    { label: "rainrate (mm/h)", data: [], borderWidth: 2, tension: 0.25 },
    { label: "yearly (mm)", data: [], borderWidth: 2, tension: 0.25 },
    { label: "event (mm)", data: [], borderWidth: 2, tension: 0.25, hidden: true },
    { label: "hourly (mm)", data: [], borderWidth: 2, tension: 0.25, hidden: true },
    { label: "last24h (mm)", data: [], borderWidth: 2, tension: 0.25, hidden: true },
    { label: "daily (mm)", data: [], borderWidth: 2, tension: 0.25, hidden: true },
    { label: "weekly (mm)", data: [], borderWidth: 2, tension: 0.25, hidden: true },
    { label: "monthly (mm)", data: [], borderWidth: 2, tension: 0.25, hidden: true },
  ],
  {
    x: { type: "linear", ticks: { color: "#eee", callback: v => fmtTime(v) } },
    y: { beginAtZero: true, ticks: { color: "#eee" } }
  }
);

// SOLAR/UV: live solar + live uv + 24h uv
const sunChart = makeLineChart("sunChart",
  [
    { label: "Solar (live) W/m²", data: [], borderWidth: 2, tension: 0.25, yAxisID: "yS" },
    { label: "UV (live)", data: [], borderWidth: 2, tension: 0.25, yAxisID: "yU" },
    { label: "UV (24h)", data: [], borderWidth: 2, tension: 0.25, yAxisID: "yU" },
  ],
  {
    x: { type: "linear", ticks: { color: "#eee", callback: v => fmtTime(v) } },
    yS: { type: "linear", position: "left", beginAtZero: true, ticks: { color: "#eee" } },
    yU: { type: "linear", position: "right", beginAtZero: true, ticks: { color: "#eee" }, grid: { drawOnChartArea: false } },
  }
);

async function refresh() {
  try {
    const r = await fetch("/api/latest", { cache: "no-store" });
    const d = await r.json();
    const t = nowSec();

    setText("lastUpdate", `Latest update: ${d.time || "--:--:--"}`);

    setText("locationName", d.location_name || "Unknown place");

    // pluscode + map (encode "+" as %2B for URL use)
    const pluscode = (d.location || "").trim();
    setText("locationPlus", pluscode);
    const plusEnc = encodeURIComponent(pluscode); // "+" -> "%2B"

    const mapUrl = `https://www.google.com/maps/search/?api=1&query=${plusEnc}`;
    const embedUrl = `https://www.google.com/maps?q=${plusEnc}&output=embed`;

    const a = document.getElementById("locationMapLink");
    if (a) a.href = mapUrl;

    const iframe = document.getElementById("locationMap");
    if (iframe && iframe.dataset.last !== plusEnc) {
      iframe.src = embedUrl;
      iframe.dataset.last = plusEnc;
    }

    setText("timeValue", d.time || "--:--:--");

    const temp = Number(d.temperature || 0);
    const hum = Number(d.humidity || 0);
    const ws = Number(d.windspeed || 0);
    const wd = Number(d.winddir || 0);
    const pr = Number(d.pressure || 0);
    const sr = Number(d.solarradiation || 0);
    const uv = Number(d.uv || 0);

    setText("tempValue", `${temp.toFixed(1)} °C`);
    setText("humValue", `${hum.toFixed(0)} %`);
    setText("windValue", `${ws.toFixed(1)} km/h`);
    setText("windCardinal", `${d.windcard || "--"} (${wd.toFixed(0)}°)`);
    const windArrow = document.getElementById("windArrow");
    if (windArrow) windArrow.style.transform = `rotate(${wd}deg)`;

    setText("pressureValue", `${pr.toFixed(1)} hPa`);
    setText("sunValue", `${sr.toFixed(0)} W/m²`);
    setText("uvValue", `${uv.toFixed(1)}`);

    const tr = d.trend || {};
    setTrendIcon("tempTrend", tr.temperature);
    setTrendIcon("humTrend", tr.humidity);
    setTrendIcon("windTrend", tr.windspeed);
    setTrendIcon("pressureTrend", tr.pressure);
    setTrendIcon("sunTrend", tr.solarradiation);
    setTrendIcon("uvTrend", tr.uv);

    // badges
    const tempBadge = document.getElementById("tempBadge");
    if (tempBadge) { tempBadge.className = `badge ${badgeColorTemperature(temp)}`; tempBadge.innerText = "Temp"; }
    const humBadge = document.getElementById("humBadge");
    if (humBadge) { humBadge.className = "badge bg-info text-dark ms-1"; humBadge.innerText = "Hum"; }
    const windBadge = document.getElementById("windBadge");
    if (windBadge) { windBadge.className = `badge ${badgeColorWind(ws)}`; windBadge.innerText = "Wind"; }
    const pressureBadge = document.getElementById("pressureBadge");
    if (pressureBadge) { pressureBadge.className = `badge ${badgeColorPressure(pr)}`; pressureBadge.innerText = "Pressure"; }
    const sunBadge = document.getElementById("sunBadge");
    if (sunBadge) { sunBadge.className = `badge ${badgeColorSun(sr)}`; sunBadge.innerText = "Realtime"; }

    // rain grid values from server (already mm)
    const mm = d.rain_mm || {};
    setText("rainratein", `${(mm.rainrate ?? 0).toFixed(2)} mm/h`);
    setText("eventrainin", `${(mm.eventrain ?? 0).toFixed(2)} mm`);
    setText("hourlyrainin", `${(mm.hourlyrain ?? 0).toFixed(2)} mm`);
    setText("last24hrainin", `${(mm.last24hrain ?? 0).toFixed(2)} mm`);
    setText("dailyrainin", `${(mm.dailyrain ?? 0).toFixed(2)} mm`);
    setText("weeklyrainin", `${(mm.weeklyrain ?? 0).toFixed(2)} mm`);
    setText("monthlyrainin", `${(mm.monthlyrain ?? 0).toFixed(2)} mm`);
    setText("yearlyrainin", `${(mm.yearlyrain ?? 0).toFixed(2)} mm`);

    // update live arrays
    pushPoint(live.temp, t, temp, MAX_LIVE_POINTS);
    pushPoint(live.hum, t, hum, MAX_LIVE_POINTS);
    pushPoint(live.ws, t, ws, MAX_LIVE_POINTS);
    pushPoint(live.wd, t, wd, MAX_LIVE_POINTS);
    pushPoint(live.sr, t, sr, MAX_LIVE_POINTS);
    pushPoint(live.uv, t, uv, MAX_LIVE_POINTS);

    // fetch 24h history (downsampled)
    await fetchHistory(24);

    // Temp chart datasets
    tempChart.data.datasets[0].data = live.temp;
    tempChart.data.datasets[1].data = seriesFromHistory("temperature");
    tempChart.data.datasets[2].data = live.hum;
    tempChart.data.datasets[3].data = seriesFromHistory("humidity");

    // Wind chart datasets
    windChart.data.datasets[0].data = live.ws;
    windChart.data.datasets[1].data = seriesFromHistory("windspeed");
    windChart.data.datasets[2].data = live.wd;
    windChart.data.datasets[3].data = seriesFromHistory("winddir");

    // Rain chart datasets (24h)
    rainChart.data.datasets[0].data = seriesFromHistory("rainrate_mm");
    rainChart.data.datasets[1].data = seriesFromHistory("yearly_mm");
    rainChart.data.datasets[2].data = seriesFromHistory("event_mm");
    rainChart.data.datasets[3].data = seriesFromHistory("hourly_mm");
    rainChart.data.datasets[4].data = seriesFromHistory("last24h_mm");
    rainChart.data.datasets[5].data = seriesFromHistory("daily_mm");
    rainChart.data.datasets[6].data = seriesFromHistory("weekly_mm");
    rainChart.data.datasets[7].data = seriesFromHistory("monthly_mm");

    // Solar chart datasets
    sunChart.data.datasets[0].data = live.sr;
    sunChart.data.datasets[1].data = live.uv;
    sunChart.data.datasets[2].data = seriesFromHistory("uv");

    tempChart.update("none");
    windChart.update("none");
    rainChart.update("none");
    sunChart.update("none");

  } catch (e) {
    console.error("refresh error:", e);
  }

  setTimeout(refresh, REFRESH_MS);
}

refresh();