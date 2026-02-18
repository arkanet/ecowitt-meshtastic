#!/usr/bin/env python3
import os
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
# PATHS (ABSOLUTE: fixes dashboard not updating when run as service)
# =========================
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # ~/ecowitt_server
INDEX_PATH = os.path.join(BASE_DIR, "index.html")
CSS_DIR = os.path.join(BASE_DIR, "css")
JS_DIR = os.path.join(BASE_DIR, "js")

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

logger.info("=== Ecowitt Server Started ===")

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

    "windspeed": 0.0,   # km/h
    "winddir": 0.0,     # deg

    # PRESSURE (from baromrelin) -> hPa in API
    "pressure": 0.0,

    # SOLAR
    "solarradiation": 0.0,  # W/m² instant
    "solardaily": 0.0,      # mapped from maxdailygust (as requested)
    "uv": 0.0,

    # RAIN (inches from GW1100)
    "rainratein": 0.0,
    "eventrainin": 0.0,
    "hourlyrainin": 0.0,
    "last24hrainin": 0.0,
    "dailyrainin": 0.0,
    "weeklyrainin": 0.0,
    "monthlyrainin": 0.0,
    "yearlyrainin": 0.0,
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
        return dirs[int((float(deg) + 11.25) / 22.5) % 16]
    except:
        return "--"


def inhg_to_hpa(inhg):
    # 1 inHg = 33.8639 hPa
    return float(inhg) * 33.8639


def inch_to_mm(x):
    return float(x) * 25.4


def f_to_c(tempf):
    return (float(tempf) - 32.0) * 5.0 / 9.0


def mph_to_kmh(mph):
    return float(mph) * 1.60934


# =========================
# PLUSCODE -> PLACE
# =========================
def pluscode_to_place(pluscode):
    now = time.time()
    if place_cache.get("value") and (now - place_cache.get("last_update", 0) < 86400):
        return place_cache["value"]

    lat, lng = pluscode_to_latlng(pluscode)
    if lat is None or lng is None:
        return "Unknown place"

    place = latlng_to_place(lat, lng)
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
            return data.get("display_name", "Unknown place")
    except:
        return "Unknown place"


# =========================
# MQTT CALLBACKS
# =========================
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info(f"[MQTT] Connected to {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(MQTT_TOPIC)
        logger.info(f"[MQTT] Subscribed: {MQTT_TOPIC}")
    else:
        logger.error(f"[MQTT] Connection failed, code: {rc}")


def on_message(client, userdata, msg):
    global latest_data
    try:
        payload = json.loads(msg.payload.decode(errors="ignore"))

        with data_lock:
            latest_data["location"] = LOCATION
            latest_data["time"] = time.strftime("%H:%M:%S")

            # keep compatibility if MQTT already publishes these in metric
            latest_data["temperature"] = safe_float(payload.get("temperature", latest_data["temperature"]))
            latest_data["humidity"] = int(safe_float(payload.get("humidity", latest_data["humidity"])))

            latest_data["windspeed"] = safe_float(payload.get("windspeed", latest_data["windspeed"]))
            latest_data["winddir"] = safe_float(payload.get("winddir", latest_data["winddir"]))

            latest_data["pressure"] = safe_float(payload.get("pressure", latest_data["pressure"]))

            latest_data["solarradiation"] = safe_float(payload.get("solarradiation", latest_data["solarradiation"]))
            latest_data["solardaily"] = safe_float(payload.get("solardaily", latest_data["solardaily"]))
            latest_data["uv"] = safe_float(payload.get("uv", latest_data["uv"]))

            for k in ["rainratein","eventrainin","hourlyrainin","last24hrainin","dailyrainin","weeklyrainin","monthlyrainin","yearlyrainin"]:
                if k in payload:
                    latest_data[k] = safe_float(payload.get(k, latest_data[k]))

        logger.info(f"[MQTT] Updated data: {latest_data}")

    except Exception as e:
        logger.error(f"[MQTT] Error parsing message: {e}")


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
    logger.error(f"[MQTT] Cannot connect to broker: {e}")


# =========================
# STATIC ROUTES (ABSOLUTE)
# =========================
@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/css/<path:filename>")
def css_files(filename):
    return send_from_directory(CSS_DIR, filename)


@app.route("/js/<path:filename>")
def js_files(filename):
    return send_from_directory(JS_DIR, filename)


# =========================
# API
# =========================
@app.route("/api/latest")
def api_latest():
    global prev_pressure

    with data_lock:
        d = dict(latest_data)

    d["windcard"] = deg_to_cardinal(d.get("winddir", 0.0))
    d["location_name"] = pluscode_to_place(d.get("location", LOCATION))

    # trend pressure (hPa)
    trend = "same"
    if prev_pressure is not None:
        if d["pressure"] > prev_pressure:
            trend = "up"
        elif d["pressure"] < prev_pressure:
            trend = "down"
    prev_pressure = d["pressure"]
    d["trend_pressure"] = trend

    # also expose rain in mm for UI convenience (raw stays as *in)
    d["rain_mm"] = {
        "rainrate": round(inch_to_mm(d.get("rainratein", 0.0)), 2),      # mm/h
        "eventrain": round(inch_to_mm(d.get("eventrainin", 0.0)), 2),
        "hourlyrain": round(inch_to_mm(d.get("hourlyrainin", 0.0)), 2),
        "last24hrain": round(inch_to_mm(d.get("last24hrainin", 0.0)), 2),
        "dailyrain": round(inch_to_mm(d.get("dailyrainin", 0.0)), 2),
        "weeklyrain": round(inch_to_mm(d.get("weeklyrainin", 0.0)), 2),
        "monthlyrain": round(inch_to_mm(d.get("monthlyrainin", 0.0)), 2),
        "yearlyrain": round(inch_to_mm(d.get("yearlyrainin", 0.0)), 2),
    }

    return jsonify(d)


# =========================
# GW1100 UPLOAD
# =========================
@app.route("/ecowitt", methods=["POST"])
def ecowitt_upload():
    global latest_data
    try:
        form = request.form.to_dict()
        if not form:
            logger.warning("[GW1100] Empty POST or not form-urlencoded")
            return "NO DATA", 400

        # logger.info(f"[GW1100 RAW FORM] {form}")  # enable if needed

        tempf = safe_float(form.get("tempf", 0))
        humidity = safe_float(form.get("humidity", 0))

        wind_mph = safe_float(form.get("windspeedmph", 0))
        winddir = safe_float(form.get("winddir", 0))

        # PRESSURE: baromrelin (inHg) -> hPa
        baromrelin = safe_float(form.get("baromrelin", 0))
        pressure_hpa = inhg_to_hpa(baromrelin)

        # SOLAR instant + "daily" mapped to maxdailygust as requested
        solarradiation = safe_float(form.get("solarradiation", 0))
        solardaily = safe_float(form.get("maxdailygust", 0))
        uv = safe_float(form.get("uv", 0))

        # RAIN: correct keys (inches)
        rainratein = safe_float(form.get("rainratein", 0))
        eventrainin = safe_float(form.get("eventrainin", 0))
        hourlyrainin = safe_float(form.get("hourlyrainin", 0))
        last24hrainin = safe_float(form.get("last24hrainin", 0))
        dailyrainin = safe_float(form.get("dailyrainin", 0))
        weeklyrainin = safe_float(form.get("weeklyrainin", 0))
        monthlyrainin = safe_float(form.get("monthlyrainin", 0))
        yearlyrainin = safe_float(form.get("yearlyrainin", 0))

        with data_lock:
            latest_data["location"] = LOCATION
            latest_data["time"] = time.strftime("%H:%M:%S")

            latest_data["temperature"] = round(f_to_c(tempf), 2)
            latest_data["humidity"] = int(round(humidity, 0))

            latest_data["windspeed"] = round(mph_to_kmh(wind_mph), 2)
            latest_data["winddir"] = round(winddir, 1)

            latest_data["pressure"] = round(pressure_hpa, 2)

            latest_data["solarradiation"] = round(solarradiation, 1)
            latest_data["solardaily"] = round(solardaily, 1)
            latest_data["uv"] = round(uv, 1)

            latest_data["rainratein"] = round(rainratein, 4)
            latest_data["eventrainin"] = round(eventrainin, 4)
            latest_data["hourlyrainin"] = round(hourlyrainin, 4)
            latest_data["last24hrainin"] = round(last24hrainin, 4)
            latest_data["dailyrainin"] = round(dailyrainin, 4)
            latest_data["weeklyrainin"] = round(weeklyrainin, 4)
            latest_data["monthlyrainin"] = round(monthlyrainin, 4)
            latest_data["yearlyrainin"] = round(yearlyrainin, 4)

        # publish to mqtt (optional, but kept because it's in your original)
        mqtt_payload = json.dumps(latest_data)
        mqtt_client.publish(MQTT_TOPIC, mqtt_payload)

        logger.info(f"[GW1100] OK: {latest_data}")
        return "OK", 200

    except Exception as e:
        logger.error(f"[GW1100] Error: {e}")
        return "ERROR", 500


# =========================
# RUN
# =========================
if __name__ == "__main__":
    logger.info(f"Web server listening on port {WEB_PORT}")
    logger.info(f"BASE_DIR = {BASE_DIR}")
    app.run(host="0.0.0.0", port=WEB_PORT, debug=False)
