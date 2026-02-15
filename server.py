#!/usr/bin/env python3
import time
import json
import logging
from logging.handlers import RotatingFileHandler
from threading import Lock

from flask import Flask, render_template_string, jsonify, request
import paho.mqtt.client as mqtt

# =========================
# CONFIG
# =========================

#LOCATION uses Google's "plus code" encoding ex: https://plus.codes/8FHJVHR9+RQ
LOCATION = "8FHJVHR9+VM"

#WEB_PORT is defined in EcoWitt app
WEB_PORT = 8080

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "ecowitt/data"

LOGFILE = "./ecowitt.log"

# =========================
# LOGGING
# =========================
logger = logging.getLogger("ecowitt_server")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(LOGFILE, maxBytes=2_000_000, backupCount=5)
formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
console = logging.StreamHandler()
console.setFormatter(formatter)
logger.addHandler(console)
logger.info("=== Ecowitt Server Avviato ===")

# =========================
# FLASK
# =========================
app = Flask(__name__)

# =========================
# GLOBAL DATA
# =========================
data_lock = Lock()
latest_data = {
    "location": LOCATION,
    "time": "--:--:--",
    "temperature": 0.0,
    "humidity": 0,
    "windspeed": 0.0,
    "winddir": 0,
    "pressure": 0.0,
    "sunlight": 0.0,
    "rain": 0.0
}

# =========================
# UTILS
# =========================
def safe_float(val):
    try:
        return float(val)
    except:
        return 0.0

def deg_to_cardinal(deg):
    dirs = ["N","NE","E","SE","S","SW","W","NW"]
    try:
        return dirs[int((deg + 22.5) / 45) % 8]
    except:
        return "--"

# =========================
# MQTT CALLBACKS
# =========================
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info(f"[MQTT] Connesso a {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(MQTT_TOPIC)
        logger.info(f"[MQTT] Subscribed: {MQTT_TOPIC}")
    else:
        logger.error(f"[MQTT] Connessione fallita, codice: {rc}")

def on_message(client, userdata, msg):
    global latest_data
    try:
        payload = json.loads(msg.payload.decode(errors="ignore"))
        with data_lock:
            latest_data["location"] = LOCATION
            latest_data["time"] = time.strftime("%H:%M:%S")
            latest_data["temperature"] = safe_float(payload.get("temperature", latest_data["temperature"]))
            latest_data["humidity"] = safe_float(payload.get("humidity", latest_data["humidity"]))
            latest_data["windspeed"] = safe_float(payload.get("windspeed", latest_data["windspeed"]))
            latest_data["winddir"] = safe_float(payload.get("winddir", latest_data["winddir"]))

            # PRESSIONE
            baromin = safe_float(payload.get("baromin", 0))
            latest_data["pressure"] = round(baromin * 33.8639, 2)

            latest_data["sunlight"] = safe_float(payload.get("sunlight", latest_data["sunlight"]))
            rainrate_in = safe_float(payload.get("rain", 0))
            latest_data["rain"] = round(rainrate_in, 2)

        logger.info(f"[MQTT] Dati aggiornati: {latest_data}")
    except Exception as e:
        logger.error(f"[MQTT] Errore parsing messaggio: {e}")

# =========================
# MQTT INIT
# =========================
mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
except Exception as e:
    logger.error(f"[MQTT] Impossibile connettersi al broker: {e}")

# =========================
# DASHBOARD HTML con grafici
# =========================
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ecowitt Dashboard</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body { background-color: #111; color: #eee; }
.card { margin: 10px; background-color: #222; color: #eee; }
canvas { background-color: #222; color: #eee; }
.chart-container { position: relative; height: 300px; width: 100%; background-color: #222; border-radius: 12px; padding: 10px; border: 1px solid #333; }
</style>
</head>
<body>
<div class="container-fluid px-3 px-md-5">
<h1 class="my-4">Ecowitt Dashboard</h1>

<div class="row">
  <div class="col-12 col-md-4">
    <div class="card p-3 text-light">
      <h5>Località / Ora / Temp</h5>
      <div id="card1">Caricamento...</div>
    </div>
  </div>
  <div class="col-12 col-md-4">
    <div class="card p-3 text-light">
      <h5>Vento / Pioggia</h5>
      <div id="card2">Caricamento...</div>
    </div>
  </div>
  <div class="col-12 col-md-4">
    <div class="card p-3 text-light">
      <h5>Pressione / Sole</h5>
      <div id="card3">Caricamento...</div>
    </div>
  </div>
</div>

<h3 class="mt-4">Grafici</h3>
<div class="row">
  <div class="col-12 col-lg-6">
    <div class="chart-container">
      <canvas id="tempChart"></canvas>
    </div>
  </div>
  <div class="col-12 col-lg-6">
    <div class="chart-container">
      <canvas id="windChart"></canvas>
    </div>
  </div>
</div>
<div class="row mt-3">
  <div class="col-12 col-lg-6">
    <div class="chart-container">
      <canvas id="rainChart"></canvas>
    </div>
  </div>
  <div class="col-12 col-lg-6">
    <div class="chart-container">
      <canvas id="sunChart"></canvas>
    </div>
  </div>
</div>
</div>

<script>
let tempData = [];
let windData = [];
let windDirData = [];
let rainData = [];
let sunData = [];
let labels = [];

const tempChart = new Chart(document.getElementById("tempChart"), {
    type: "line",
    data: { labels, datasets:[{label:"Temperatura °C", data: tempData, borderColor:"red", backgroundColor:"rgba(255,0,0,0.2)"}] },
    options:{scales:{y:{beginAtZero:false},x:{ticks:{color:"#eee"}},y:{ticks:{color:"#eee"}}}}
});

const windChart=new Chart(document.getElementById("windChart"),{type:"line",data:{labels,datasets:[{label:"Vento km/h",data:windData,borderColor:"blue",backgroundColor:"rgba(0,0,255,0.2)",borderWidth:2,tension:0.25,yAxisID:"yWind"},{label:"Direzione vento °",data:windDirData,borderColor:"cyan",backgroundColor:"rgba(0,255,255,0.2)",borderWidth:2,tension:0.25,yAxisID:"yDir"}]},options:{responsive:true,maintainAspectRatio:false,animation:false,plugins:{legend:{labels:{color:"#eee"}}},scales:{x:{ticks:{color:"#eee"}},yWind:{type:"linear",position:"left",beginAtZero:true,ticks:{color:"#eee"}},yDir:{type:"linear",position:"right",min:0,max:360,ticks:{color:"#eee"},grid:{drawOnChartArea:false}}}}});

const rainChart = new Chart(document.getElementById("rainChart"), {
    type: "line",
    data: { labels, datasets:[{label:"Pioggia mm/h", data: rainData, borderColor:"green", backgroundColor:"rgba(0,255,0,0.2)"}] },
    options:{scales:{y:{beginAtZero:true},x:{ticks:{color:"#eee"}},y:{ticks:{color:"#eee"}}}}
});

const sunChart = new Chart(document.getElementById("sunChart"), {
    type: "line",
    data: { labels, datasets:[{label:"Sole W/m²", data: sunData, borderColor:"yellow", backgroundColor:"rgba(255,255,0,0.2)"}] },
    options:{scales:{y:{beginAtZero:true},x:{ticks:{color:"#eee"}},y:{ticks:{color:"#eee"}}}}
});

async function refreshData() {
    try {
        let r = await fetch("/api/latest");
        let d = await r.json();

        document.getElementById("card1").innerText =
            `${d.location}  ${d.time}  Temp: ${d.temperature}°C  Hum: ${d.humidity}%`;

        document.getElementById("card2").innerText =
            `Vento: ${d.windspeed} km/h (${d.windcard}) Dir: ${d.winddir}°  Rain: ${d.rain} mm/h`;


        document.getElementById("card3").innerText =
            `Pressione: ${d.pressure} hPa  Sole: ${d.sunlight} W/m²`;

        // aggiorna grafici
        const t = d.time;
        labels.push(t);
        tempData.push(d.temperature);
        windData.push(d.windspeed);
        windDirData.push(d.winddir);
        rainData.push(d.rain);
        sunData.push(d.sunlight);

        if(labels.length > 20){ labels.shift(); tempData.shift(); windData.shift(); windDirData.shift(); rainData.shift(); sunData.shift(); }

        tempChart.update();
        windChart.update();
        rainChart.update();
        sunChart.update();

    } catch(e){ console.error("Errore aggiornamento:", e); }
    setTimeout(refreshData, 5000);
}
refreshData();
</script>

</body>
</html>
"""

# =========================
# ROUTES
# =========================
@app.route("/")
def dashboard():
    return render_template_string(DASHBOARD_HTML)

@app.route("/api/latest")
def api_latest():
    with data_lock:
        d = dict(latest_data)
    d["windcard"] = deg_to_cardinal(d.get("winddir", 0.0))
    return jsonify(d)

@app.route("/ecowitt", methods=["POST"])
def ecowitt_upload():
    global latest_data
    try:
        form = request.form.to_dict()
        if not form:
            logger.warning("[GW1100] POST vuoto o non form-urlencoded")
            return "NO DATA", 400

        tempf = safe_float(form.get("tempf", 0))
        humidity = safe_float(form.get("humidity", 0))
        wind_mph = safe_float(form.get("windspeedmph", 0))
        winddir = safe_float(form.get("winddir", 0))
        baromin = safe_float(form.get("baromin", 0))
        solar = safe_float(form.get("solarradiation", 0))
        rain_rate_in = safe_float(form.get("rainrate", 0))

        temperature_c = (tempf - 32.0) * 5.0 / 9.0
        wind_kmh = wind_mph * 1.60934
        pressure_hpa = baromin * 33.8639
        rain_mm_per_hour = rain_rate_in * 25.4

        with data_lock:
            latest_data["location"] = LOCATION
            latest_data["time"] = time.strftime("%H:%M:%S")
            latest_data["temperature"] = round(temperature_c, 2)
            latest_data["humidity"] = round(humidity, 1)
            latest_data["windspeed"] = round(wind_kmh, 2)
            latest_data["winddir"] = round(winddir, 1)
            latest_data["pressure"] = round(pressure_hpa, 2)
            latest_data["sunlight"] = round(solar, 1)
            latest_data["rain"] = round(rain_mm_per_hour, 2)

        mqtt_payload = json.dumps(latest_data)
        mqtt_client.publish(MQTT_TOPIC, mqtt_payload)
        logger.info(f"[GW1100] OK: {latest_data}")
        return "OK", 200

    except Exception as e:
        logger.error(f"[GW1100] Errore: {e}")
        return "ERROR", 500

# =========================
# RUN
# =========================
if __name__ == "__main__":
    logger.info(f"Server web in ascolto su porta {WEB_PORT}")
    app.run(host="0.0.0.0", port=WEB_PORT, debug=False)
