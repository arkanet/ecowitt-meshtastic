let labels = [];

let tempData = [];
let humData = [];

let windData = [];
let windDirData = [];

let rainData = [];
let rain24Data = [];

let sunData = [];
let sun24Data = [];

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

function badgeColorRain(r) {
  if (r <= 0) return "bg-light text-dark";
  if (r < 10) return "bg-success text-light";
  if (r < 30) return "bg-warning text-dark";
  if (r < 60) return "bg-orange text-light";
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
  // centro ottimale 1013 hPa, estremi verso rosso sopra/sotto
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
  data: {
    labels,
    datasets: [
      { label: "Temp °C", data: tempData, borderWidth: 2, tension: 0.25 },
      { label: "Hum %", data: humData, borderWidth: 2, tension: 0.25 }
    ]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: { legend: { labels: { color: "#eee" } } },
    scales: {
      x: { ticks: { color: "#eee" } },
      y: { ticks: { color: "#eee" } }
    }
  }
});

const windChart = new Chart(document.getElementById("windChart"), {
  type: "line",
  data: {
    labels,
    datasets: [
      { label: "Vento km/h", data: windData, borderWidth: 2, tension: 0.25, yAxisID: "yWind" },
      { label: "Direzione °", data: windDirData, borderWidth: 2, tension: 0.25, yAxisID: "yDir" }
    ]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: { legend: { labels: { color: "#eee" } } },
    scales: {
      x: { ticks: { color: "#eee" } },
      yWind: {
        type: "linear",
        position: "left",
        beginAtZero: true,
        ticks: { color: "#eee" }
      },
      yDir: {
        type: "linear",
        position: "right",
        min: 0,
        max: 360,
        ticks: { color: "#eee" },
        grid: { drawOnChartArea: false }
      }
    }
  }
});

const rainChart = new Chart(document.getElementById("rainChart"), {
  type: "line",
  data: {
    labels,
    datasets: [
      { label: "Rain mm/h", data: rainData, borderWidth: 2, tension: 0.25 },
      { label: "Rain 24h mm", data: rain24Data, borderWidth: 2, tension: 0.25 }
    ]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: { legend: { labels: { color: "#eee" } } },
    scales: {
      x: { ticks: { color: "#eee" } },
      y: { beginAtZero: true, ticks: { color: "#eee" } }
    }
  }
});

const sunChart = new Chart(document.getElementById("sunChart"), {
  type: "line",
  data: {
    labels,
    datasets: [
      { label: "Sole W/m²", data: sunData, borderWidth: 2, tension: 0.25 },
      { label: "Sole 24h W/m²", data: sun24Data, borderWidth: 2, tension: 0.25 }
    ]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: { legend: { labels: { color: "#eee" } } },
    scales: {
      x: { ticks: { color: "#eee" } },
      y: { beginAtZero: true, ticks: { color: "#eee" } }
    }
  }
});

async function refreshData() {
  try {
    let r = await fetch("/api/latest");
    let d = await r.json();

    document.getElementById("lastUpdate").innerText = `Ultimo update: ${d.time}`;

    document.getElementById("locationName").innerText = d.location_name;
    document.getElementById("locationPlus").innerText = d.location;
    document.getElementById("timeValue").innerText = d.time;

    document.getElementById("tempValue").innerText = `${d.temperature.toFixed(1)} °C`;
    document.getElementById("humValue").innerText = `${d.humidity} %`;

    document.getElementById("windValue").innerText = `${d.windspeed.toFixed(1)} km/h`;
    document.getElementById("windCardinal").innerText = d.windcard;

    document.getElementById("pressureValue").innerText = `${d.pressure.toFixed(1)} hPa`;

    document.getElementById("rainValue").innerText = `${d.rain.toFixed(2)} mm/h`;
    document.getElementById("rain24Value").innerText = `${d.rain24h.toFixed(2)} mm`;

    document.getElementById("sunValue").innerText = `${d.sunlight.toFixed(0)} W/m²`;
    document.getElementById("sun24Value").innerText = `${d.sunlight24h.toFixed(0)} W/m²`;

    // rotazione freccia vento
    document.getElementById("windArrow").style.transform = `rotate(${d.winddir}deg)`;

    // trend pressione
    setTrendIcon("pressureTrend", d.trend_pressure);

    // badges colori
    document.getElementById("tempBadge").className = `badge ${badgeColorTemperature(d.temperature)}`;
    document.getElementById("tempBadge").innerText = "Temp";

    document.getElementById("humBadge").className = `badge bg-info text-dark`;
    document.getElementById("humBadge").innerText = "Hum";

    document.getElementById("windBadge").className = `badge ${badgeColorWind(d.windspeed)}`;
    document.getElementById("windBadge").innerText = "Wind";

    document.getElementById("pressureBadge").className = `badge ${badgeColorPressure(d.pressure)}`;
    document.getElementById("pressureBadge").innerText = "Pressure";

    document.getElementById("rainBadge").className = `badge ${badgeColorRain(d.rain)}`;
    document.getElementById("rainBadge").innerText = "Realtime";

    document.getElementById("rain24Badge").className = `badge ${badgeColorRain(d.rain24h)}`;
    document.getElementById("rain24Badge").innerText = "24h";

    document.getElementById("sunBadge").className = `badge ${badgeColorSun(d.sunlight)}`;
    document.getElementById("sunBadge").innerText = "Realtime";

    document.getElementById("sun24Badge").className = `badge ${badgeColorSun(d.sunlight24h)}`;
    document.getElementById("sun24Badge").innerText = "24h";

    // aggiorna grafici
    labels.push(d.time);

    tempData.push(d.temperature);
    humData.push(d.humidity);

    windData.push(d.windspeed);
    windDirData.push(d.winddir);

    rainData.push(d.rain);
    rain24Data.push(d.rain24h);

    sunData.push(d.sunlight);
    sun24Data.push(d.sunlight24h);

    if (labels.length > 40) {
      labels.shift();
      tempData.shift();
      humData.shift();
      windData.shift();
      windDirData.shift();
      rainData.shift();
      rain24Data.shift();
      sunData.shift();
      sun24Data.shift();
    }

    tempChart.update();
    windChart.update();
    rainChart.update();
    sunChart.update();

  } catch (e) {
    console.error("Errore refreshData:", e);
  }

  setTimeout(refreshData, 5000);
}

refreshData();

