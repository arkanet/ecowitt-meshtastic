let labels = [];

let tempData = [];
let humData = [];

let windData = [];
let windDirData = [];

let rainRateInData = [];
let eventRainInData = [];
let hourlyRainInData = [];
let last24hRainInData = [];
let dailyRainInData = [];
let weeklyRainInData = [];
let monthlyRainInData = [];
let yearlyRainInData = [];

let sunNowData = [];
let sunDailyData = [];
let uvData = [];

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
  let delta = Math.abs(p - 1013);
  if (delta < 5) return "bg-light text-dark";
  if (delta < 15) return "bg-success text-light";
  if (delta < 25) return "bg-warning text-dark";
  if (delta < 40) return "bg-orange text-light";
  return "bg-danger text-light";
}

function setTrendIcon(elemId, trend) {
  const el = document.getElementById(elemId);
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

const tempChart = new Chart(document.getElementById("tempChart"), {
  type: "line",
  data: { labels, datasets: [
    { label: "Temp °C", data: tempData, borderWidth: 2, tension: 0.25 },
    { label: "Hum %", data: humData, borderWidth: 2, tension: 0.25 }
  ]},
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: { legend: { labels: { color: "#eee" } } },
    scales: { x: { ticks: { color: "#eee" } }, y: { ticks: { color: "#eee" } } }
  }
});

const windChart = new Chart(document.getElementById("windChart"), {
  type: "line",
  data: { labels, datasets: [
    { label: "Wind km/h", data: windData, borderWidth: 2, tension: 0.25, yAxisID: "yWind" },
    { label: "Direction °", data: windDirData, borderWidth: 2, tension: 0.25, yAxisID: "yDir" }
  ]},
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: { legend: { labels: { color: "#eee" } } },
    scales: {
      x: { ticks: { color: "#eee" } },
      yWind: { type: "linear", position: "left", beginAtZero: true, ticks: { color: "#eee" } },
      yDir: { type: "linear", position: "right", min: 0, max: 360, ticks: { color: "#eee" }, grid: { drawOnChartArea: false } }
    }
  }
});

const rainChart = new Chart(document.getElementById("rainChart"), {
  type: "line",
  data: { labels, datasets: [
    { label: "rainratein", data: rainRateInData, borderWidth: 2, tension: 0.25 },
    { label: "eventrainin", data: eventRainInData, borderWidth: 2, tension: 0.25 },
    { label: "hourlyrainin", data: hourlyRainInData, borderWidth: 2, tension: 0.25 },
    { label: "last24hrainin", data: last24hRainInData, borderWidth: 2, tension: 0.25 },
    { label: "dailyrainin", data: dailyRainInData, borderWidth: 2, tension: 0.25 },
    { label: "weeklyrainin", data: weeklyRainInData, borderWidth: 2, tension: 0.25 },
    { label: "monthlyrainin", data: monthlyRainInData, borderWidth: 2, tension: 0.25 },
    { label: "yearlyrainin", data: yearlyRainInData, borderWidth: 2, tension: 0.25 }
  ]},
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: { legend: { labels: { color: "#eee" } } },
    scales: { x: { ticks: { color: "#eee" } }, y: { beginAtZero: true, ticks: { color: "#eee" } } }
  }
});

const sunChart = new Chart(document.getElementById("sunChart"), {
  type: "line",
  data: { labels, datasets: [
    { label: "solarradiation (W/m²)", data: sunNowData, borderWidth: 2, tension: 0.25, yAxisID: "ySolar" },
    { label: "daily (mapped)", data: sunDailyData, borderWidth: 2, tension: 0.25, yAxisID: "ySolar" },
    { label: "uv", data: uvData, borderWidth: 2, tension: 0.25, yAxisID: "yUV" }
  ]},
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: { legend: { labels: { color: "#eee" } } },
    scales: {
      x: { ticks: { color: "#eee" } },
      ySolar: { type: "linear", position: "left", beginAtZero: true, ticks: { color: "#eee" } },
      yUV: { type: "linear", position: "right", beginAtZero: true, ticks: { color: "#eee" }, grid: { drawOnChartArea: false } }
    }
  }
});

async function refreshData() {
  try {
    const r = await fetch("/api/latest", { cache: "no-store" });
    const d = await r.json();

    document.getElementById("lastUpdate").innerText = `Latest update: ${d.time}`;

    document.getElementById("locationName").innerText = d.location_name || "Unknown place";
    document.getElementById("locationPlus").innerText = d.location || "";
    document.getElementById("timeValue").innerText = d.time || "--:--:--";

    document.getElementById("tempValue").innerText = `${Number(d.temperature).toFixed(1)} °C`;
    document.getElementById("humValue").innerText = `${d.humidity} %`;

    document.getElementById("windValue").innerText = `${Number(d.windspeed).toFixed(1)} km/h`;
    document.getElementById("windCardinal").innerText = d.windcard || "--";
    document.getElementById("windArrow").style.transform = `rotate(${Number(d.winddir) || 0}deg)`;

    document.getElementById("pressureValue").innerText = `${Number(d.pressure).toFixed(1)} hPa`;
    setTrendIcon("pressureTrend", d.trend_pressure || "same");

    // badges
    document.getElementById("tempBadge").className = `badge ${badgeColorTemperature(Number(d.temperature) || 0)}`;
    document.getElementById("tempBadge").innerText = "Temp";

    document.getElementById("humBadge").className = `badge bg-info text-dark`;
    document.getElementById("humBadge").innerText = "Hum";

    document.getElementById("windBadge").className = `badge ${badgeColorWind(Number(d.windspeed) || 0)}`;
    document.getElementById("windBadge").innerText = "Wind";

    document.getElementById("pressureBadge").className = `badge ${badgeColorPressure(Number(d.pressure) || 0)}`;
    document.getElementById("pressureBadge").innerText = "Pressure";

    // rain grid values (show mm in UI to be human-friendly)
    const mm = (d.rain_mm || {});
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };

    set("rainratein", `${mm.rainrate ?? 0} mm/h`);
    set("eventrainin", `${mm.eventrain ?? 0} mm`);
    set("hourlyrainin", `${mm.hourlyrain ?? 0} mm`);
    set("last24hrainin", `${mm.last24hrain ?? 0} mm`);
    set("dailyrainin", `${mm.dailyrain ?? 0} mm`);
    set("weeklyrainin", `${mm.weeklyrain ?? 0} mm`);
    set("monthlyrainin", `${mm.monthlyrain ?? 0} mm`);
    set("yearlyrainin", `${mm.yearlyrain ?? 0} mm`);

    // solar values
    document.getElementById("sunValue").innerText = `${Number(d.solarradiation || 0).toFixed(0)} W/m²`;
    document.getElementById("sun24Value").innerText = `${Number(d.solardaily || 0).toFixed(1)}`;
    document.getElementById("sunBadge").className = `badge ${badgeColorSun(Number(d.solarradiation) || 0)}`;
    document.getElementById("sunBadge").innerText = "Realtime";
    document.getElementById("sun24Badge").className = `badge bg-secondary text-light`;
    document.getElementById("sun24Badge").innerText = "Daily";

    // charts
    labels.push(d.time);

    tempData.push(Number(d.temperature) || 0);
    humData.push(Number(d.humidity) || 0);

    windData.push(Number(d.windspeed) || 0);
    windDirData.push(Number(d.winddir) || 0);

    rainRateInData.push(Number(d.rainratein) || 0);
    eventRainInData.push(Number(d.eventrainin) || 0);
    hourlyRainInData.push(Number(d.hourlyrainin) || 0);
    last24hRainInData.push(Number(d.last24hrainin) || 0);
    dailyRainInData.push(Number(d.dailyrainin) || 0);
    weeklyRainInData.push(Number(d.weeklyrainin) || 0);
    monthlyRainInData.push(Number(d.monthlyrainin) || 0);
    yearlyRainInData.push(Number(d.yearlyrainin) || 0);

    sunNowData.push(Number(d.solarradiation) || 0);
    sunDailyData.push(Number(d.solardaily) || 0);
    uvData.push(Number(d.uv) || 0);

    if (labels.length > 40) {
      labels.shift();
      tempData.shift(); humData.shift();
      windData.shift(); windDirData.shift();

      rainRateInData.shift();
      eventRainInData.shift();
      hourlyRainInData.shift();
      last24hRainInData.shift();
      dailyRainInData.shift();
      weeklyRainInData.shift();
      monthlyRainInData.shift();
      yearlyRainInData.shift();

      sunNowData.shift(); sunDailyData.shift(); uvData.shift();
    }

    tempChart.update();
    windChart.update();
    rainChart.update();
    sunChart.update();

  } catch (e) {
    console.error("refreshData error:", e);
  }

  setTimeout(refreshData, 5000);
}

refreshData();
