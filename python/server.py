#!/usr/bin/env python3
import time
import json
import logging
import urllib.request
import urllib.parse
from logging.handlers import RotatingFileHandler
from threading import Lock

from flask import Flask, jsonify, request, send_from_directory
import paho.mqtt.client as mqtt

# =========================
# CONFIG
# =========================

# LOCATION uses Google's plus code encoding ex: https://plus.codes/8FHJVHR9+RQ
LOCATION = "8FHJVHR9+RQ"

# WEB_PORT is defined in EcoWitt app
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
    "sunlight24h": 0.0,
    "rain": 0.0,
    "rain24h": 0.0
}

prev_pressure = None

# =========================
# PLACE CACHE
# =========================
place_cache = {"value": None, "last_update": 0}

# =========================
# UTILS
# =========================
def safe_float(val):
    try:
        return float(val)
    except:
        return 0.0


def deg_to_cardinal(deg):
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
            "S","SSW","SW","WSW","W","WNW","NW","NNW"]
    try:
        return dirs[int((deg + 11.25) / 22.5) % 16]
    except:
        return "--"


# =========================
# PLUSCODE -> PLACE (as requested)
# =========================
def pluscode_to_place(pluscode):
    now = time.time()
    if place_cache.get("value") and (now - place_cache.get("last_update", 0) < 86400):
        return place_cache["value"]

    lat, lng = pluscode_to_latlng(pluscode)
    if lat is None or lng is None:
        return "Unknown place"

    place = latlng_to_place(lat, lng)
    # aggiorna cache
    place_cache["value"] = place
    place_cache["last_update"] = now
    return place


def pluscode_to_latlng(pluscode):
    url = f"https://plus.codes/api?address={urllib.parse.quote(pluscode)}"
    req = urllib.request.Request(url, headers={"User-Agent": "ecowitt-meshtastic"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read())
        loc = data.get("plus_code", {}).get("geometry", {})
        lat = loc.get("location", {}).get("lat")
        lng = loc.get("location", {}).get("lng")
        if lat is not None and lng is not None:
            return lat, lng
    return None, None


def latlng_to_place(lat, lng):
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lng}&zoom=10"
        req = urllib.request.Request(url, headers={"User-Agent": "ecowitt-meshtastic"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            display = data.get("display_name", "Unknown place")
            return display
    except:
        return "Unknown place"


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
    global latest_data, prev_pressure

    try:
        payload = json.loads(msg.payload.decode(errors="ignore"))

        with data_lock:
            latest_data["location"] = LOCATION
            latest_data["time"] = time.strftime("%H:%M:%S")

            latest_data["temperature"] = safe_float(payload.get("temperature", latest_data["temperature"]))
            latest_data["humidity"] = int(safe_float(payload.get("humidity", latest_data["humidity"])))

            latest_data["windspeed"] = safe_float(payload.get("windspeed", latest_data["windspeed"]))
            latest_data["winddir"] = safe_float(payload.get("winddir", latest_data["winddir"]))

            latest_data["pressure"] = safe_float(payload.get("pressure", latest_data["pressure"]))

            latest_data["sunlight"] = safe_float(payload.get("sunlight", latest_data["sunlight"]))
            latest_data["sunlight24h"] = safe_float(payload.get("sunlight24h", latest_data["sunlight24h"]))

            latest_data["rain"] = safe_float(payload.get("rain", latest_data["rain"]))
            latest_data["rain24h"] = safe_float(payload.get("rain24h", latest_data["rain24h"]))

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
# STATIC ROUTES
# =========================
@app.route("/")
def index():
    return send_from_directory("../", "index.html")


@app.route("/css/<path:filename>")
def css_files(filename):
    return send_from_directory("../css", filename)


@app.route("/js/<path:filename>")
def js_files(filename):
    return send_from_directory("../js", filename)


# =========================
# API
# =========================
@app.route("/api/latest")
def api_latest():
    global prev_pressure

    with data_lock:
        d = dict(latest_data)

    d["windcard"] = deg_to_cardinal(d.get("winddir", 0.0))

    # pluscode -> place
    d["location_name"] = pluscode_to_place(d.get("location", LOCATION))

    # trend pressione
    trend = "same"
    if prev_pressure is not None:
        if d["pressure"] > prev_pressure:
            trend = "up"
        elif d["pressure"] < prev_pressure:
            trend = "down"

    prev_pressure = d["pressure"]
    d["trend_pressure"] = trend

    return jsonify(d)


# =========================
# GW1100 UPLOAD (fallback)
# =========================
@app.route("/ecowitt", methods=["POST"])
def ecowitt_upload():
    global latest_data

    try:
        form = request.form.to_dict()
        # troubleshooting research real data
        # uncommitt over
        # logger.info(f"[GW1100 RAW FORM] {form}")

	# use this for to do it
        # tail -f ecowitt.log
        # curl -X POST http://127.0.0.1:8080/ecowitt -d "tempf=68&humidity=55&windspeedmph=5&winddir=180&baromin=29.92&solarradiation=100&dailyrainin=1.5"
        # curl http://127.0.0.1:8080/api/latest

        if not form:
            logger.warning("[GW1100] POST vuoto o non form-urlencoded")
            return "NO DATA", 400

        tempf = safe_float(form.get("tempf", 0))
        humidity = safe_float(form.get("humidity", 0))
        wind_mph = safe_float(form.get("windspeedmph", 0))
        winddir = safe_float(form.get("winddir", 0))
        baromin = safe_float(form.get("baromin", 0))
        solar = safe_float(form.get("solarradiation", 0))
        # solar24h = safe_float(form.get("solarradiation24h", 0))
        rain_rate_in = safe_float(form.get("rainrate", 0))
        # rain_24h_in = safe_float(form.get("dailyrainin", 0))

        # --- RAIN 24H / DAILY ---
        rain_24h_in = safe_float(
            form.get("dailyrainin") or
            form.get("rain24hin") or
            form.get("rain24h") or
            0
        )

        rain_24h_mm = safe_float(
            form.get("dailyrainmm") or
            form.get("rain24hmm") or
            0
        )

        # conversion inch > mm
        if rain_24h_mm == 0 and rain_24h_in > 0:
            rain_24h_mm = rain_24h_in * 25.4

        # --- SUNLIGHT 24H ---
        solar24h = safe_float(
            form.get("solarradiation24h") or
            form.get("solar24h") or
            form.get("solarenergy") or
            form.get("solarenergy24h") or
            0
        )

        temperature_c = (tempf - 32.0) * 5.0 / 9.0
        wind_kmh = wind_mph * 1.60934
        pressure_hpa = baromin * 33.8639
        rain_mm_per_hour = rain_rate_in * 25.4
        rain_24h_mm = rain_24h_in * 25.4

        with data_lock:
            latest_data["location"] = LOCATION
            latest_data["time"] = time.strftime("%H:%M:%S")
            latest_data["temperature"] = round(temperature_c, 2)
            latest_data["humidity"] = int(round(humidity, 0))
            latest_data["windspeed"] = round(wind_kmh, 2)
            latest_data["winddir"] = round(winddir, 1)
            latest_data["pressure"] = round(pressure_hpa, 2)
            latest_data["sunlight"] = round(solar, 1)
            latest_data["sunlight24h"] = round(solar24h, 1)
            latest_data["rain"] = round(rain_mm_per_hour, 2)
            latest_data["rain24h"] = round(rain_24h_mm, 2)

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

