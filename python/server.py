#!/usr/bin/env python3
import os
import time
import json
import logging
import sqlite3
import urllib.request
import urllib.parse
from logging.handlers import RotatingFileHandler
from threading import Lock

from flask import Flask, jsonify, request, send_from_directory

# =========================
# CONFIG
# =========================
LOCATION = "8FHJVFRR+3W"
WEB_PORT = 8080
LOGFILE = "./ecowitt.log"

RETENTION_DAYS = 30
_CLEANUP_EVERY_SEC = 6 * 3600  # 6h

# =========================
# PATHS (keep current layout)
# repo root: ~/ecowitt_server
# python/server.py
# index.html
# js/dashboard.js
# css/style.css
# vendor/...
# data/ecowitt.db
# =========================
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CSS_DIR = os.path.join(BASE_DIR, "css")
JS_DIR = os.path.join(BASE_DIR, "js")
VENDOR_DIR = os.path.join(BASE_DIR, "vendor")
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "ecowitt.db")
os.makedirs(DATA_DIR, exist_ok=True)

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
# GLOBALS
# =========================
data_lock = Lock()
place_cache = {"value": None, "last_update": 0}
_last_cleanup = 0

latest_data = {
    "location": LOCATION,
    "time": "--:--:--",

    "temperature": 0.0,      # °C
    "humidity": 0,           # %
    "windspeed": 0.0,        # km/h
    "winddir": 0.0,          # deg
    "pressure": 0.0,         # hPa

    "solarradiation": 0.0,   # W/m²
    "uv": 0.0,               # UV index

    # rain (inches from GW1100)
    "rainratein": 0.0,
    "eventrainin": 0.0,
    "hourlyrainin": 0.0,
    "last24hrainin": 0.0,
    "dailyrainin": 0.0,
    "weeklyrainin": 0.0,
    "monthlyrainin": 0.0,
    "yearlyrainin": 0.0,
}

_prev = {
    "temperature": None,
    "humidity": None,
    "windspeed": None,
    "winddir": None,
    "pressure": None,
    "solarradiation": None,
    "uv": None,
    "rainratein": None,
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
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
            "S","SSW","SW","WSW","W","WNW","NW","NNW"]
    try:
        return dirs[int((float(deg) + 11.25) / 22.5) % 16]
    except:
        return "--"

def inhg_to_hpa(inhg):
    return float(inhg) * 33.8639

def inch_to_mm(x):
    return float(x) * 25.4

def f_to_c(tempf):
    return (float(tempf) - 32.0) * 5.0 / 9.0

def mph_to_kmh(mph):
    return float(mph) * 1.60934

def trend_of(key, new_val):
    old = _prev.get(key)
    _prev[key] = new_val
    if old is None:
        return "same"
    if new_val > old:
        return "up"
    if new_val < old:
        return "down"
    return "same"

def _yyyymmdd(ts):
    lt = time.localtime(ts)
    return lt.tm_year * 10000 + lt.tm_mon * 100 + lt.tm_mday

# =========================
# PLUSCODE -> PLACE (cached 24h)
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
    req = urllib.request.Request(url, headers={"User-Agent":"ecowitt-meshtastic"})
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
        req = urllib.request.Request(url, headers={"User-Agent":"ecowitt-meshtastic"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return data.get("display_name", "Unknown place")
    except:
        return "Unknown place"

# =========================
# SQLITE (readings + long-term rain rollup)
# =========================
def db_connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def db_init():
    conn = db_connect()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS readings (
        ts INTEGER NOT NULL,
        location TEXT,
        temperature REAL,
        humidity INTEGER,
        windspeed REAL,
        winddir REAL,
        pressure REAL,
        solarradiation REAL,
        uv REAL,

        rainratein REAL,
        eventrainin REAL,
        hourlyrainin REAL,
        last24hrainin REAL,
        dailyrainin REAL,
        weeklyrainin REAL,
        monthlyrainin REAL,
        yearlyrainin REAL
    );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_readings_ts ON readings(ts);")

    # 1 row/day, no retention
    conn.execute("""
    CREATE TABLE IF NOT EXISTS rain_rollup_daily (
        day INTEGER PRIMARY KEY,   -- YYYYMMDD
        ts INTEGER NOT NULL,
        rainrate_mm REAL,
        event_mm REAL,
        hourly_mm REAL,
        last24h_mm REAL,
        daily_mm REAL,
        weekly_mm REAL,
        monthly_mm REAL,
        yearly_mm REAL
    );
    """)
    conn.commit()
    conn.close()

db_init()

def db_cleanup_if_needed(now_ts):
    global _last_cleanup
    if (now_ts - _last_cleanup) < _CLEANUP_EVERY_SEC:
        return
    _last_cleanup = now_ts

    cutoff = now_ts - RETENTION_DAYS * 86400
    conn = db_connect()
    conn.execute("DELETE FROM readings WHERE ts < ?", (cutoff,))
    conn.commit()
    conn.close()
    logger.info(f"[DB] Retention cleanup: deleted rows older than {RETENTION_DAYS} days.")

def db_insert_reading(d, ts):
    conn = db_connect()
    conn.execute("""
      INSERT INTO readings (
        ts, location, temperature, humidity, windspeed, winddir, pressure, solarradiation, uv,
        rainratein, eventrainin, hourlyrainin, last24hrainin, dailyrainin, weeklyrainin, monthlyrainin, yearlyrainin
      ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        ts, d["location"], d["temperature"], d["humidity"], d["windspeed"], d["winddir"], d["pressure"], d["solarradiation"], d["uv"],
        d["rainratein"], d["eventrainin"], d["hourlyrainin"], d["last24hrainin"], d["dailyrainin"], d["weeklyrainin"], d["monthlyrainin"], d["yearlyrainin"]
    ))
    conn.commit()
    conn.close()

def db_upsert_rain_rollup(d, ts):
    day = _yyyymmdd(ts)
    rr = inch_to_mm(d.get("rainratein", 0.0))
    ev = inch_to_mm(d.get("eventrainin", 0.0))
    hr = inch_to_mm(d.get("hourlyrainin", 0.0))
    l24 = inch_to_mm(d.get("last24hrainin", 0.0))
    dy = inch_to_mm(d.get("dailyrainin", 0.0))
    wk = inch_to_mm(d.get("weeklyrainin", 0.0))
    mo = inch_to_mm(d.get("monthlyrainin", 0.0))
    yr = inch_to_mm(d.get("yearlyrainin", 0.0))

    conn = db_connect()
    conn.execute("""
      INSERT INTO rain_rollup_daily
        (day, ts, rainrate_mm, event_mm, hourly_mm, last24h_mm, daily_mm, weekly_mm, monthly_mm, yearly_mm)
      VALUES (?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(day) DO UPDATE SET
        ts=excluded.ts,
        rainrate_mm=excluded.rainrate_mm,
        event_mm=excluded.event_mm,
        hourly_mm=excluded.hourly_mm,
        last24h_mm=excluded.last24h_mm,
        daily_mm=excluded.daily_mm,
        weekly_mm=excluded.weekly_mm,
        monthly_mm=excluded.monthly_mm,
        yearly_mm=excluded.yearly_mm
    """, (day, ts, rr, ev, hr, l24, dy, wk, mo, yr))
    conn.commit()
    conn.close()

def db_history(hours=24):
    hours = max(1, min(int(hours), 168))
    since = int(time.time()) - hours * 3600

    conn = db_connect()
    rows = conn.execute("""
      SELECT
        (ts/60)*60 AS tmin,

        AVG(temperature) AS temperature,
        AVG(humidity) AS humidity,
        AVG(windspeed) AS windspeed,
        AVG(winddir) AS winddir,
        AVG(solarradiation) AS solarradiation,
        AVG(uv) AS uv,

        AVG(rainratein * 25.4) AS rainrate_mm,
        AVG(eventrainin * 25.4) AS event_mm,
        AVG(hourlyrainin * 25.4) AS hourly_mm,
        AVG(last24hrainin * 25.4) AS last24h_mm,
        AVG(dailyrainin * 25.4) AS daily_mm,
        AVG(weeklyrainin * 25.4) AS weekly_mm,
        AVG(monthlyrainin * 25.4) AS monthly_mm,
        AVG(yearlyrainin * 25.4) AS yearly_mm

      FROM readings
      WHERE ts >= ?
      GROUP BY tmin
      ORDER BY tmin ASC
    """, (since,)).fetchall()
    conn.close()

    keys = [
        "temperature","humidity","windspeed","winddir","solarradiation","uv",
        "rainrate_mm","event_mm","hourly_mm","last24h_mm","daily_mm","weekly_mm","monthly_mm","yearly_mm"
    ]
    out = {k: [] for k in keys}
    for r in rows:
        tmin = int(r["tmin"])
        for k in keys:
            out[k].append([tmin, float(r[k] or 0.0)])
    return out

# =========================
# STATIC ROUTES
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

@app.route("/vendor/<path:filename>")
def vendor_files(filename):
    return send_from_directory(VENDOR_DIR, filename)

# =========================
# API
# =========================
@app.route("/api/latest")
def api_latest():
    with data_lock:
        d = dict(latest_data)

    d["windcard"] = deg_to_cardinal(d.get("winddir", 0.0))
    d["location_name"] = pluscode_to_place(d.get("location", LOCATION))

    d["trend"] = {
        "temperature": trend_of("temperature", float(d["temperature"])),
        "humidity": trend_of("humidity", float(d["humidity"])),
        "windspeed": trend_of("windspeed", float(d["windspeed"])),
        "winddir": trend_of("winddir", float(d["winddir"])),
        "pressure": trend_of("pressure", float(d["pressure"])),
        "solarradiation": trend_of("solarradiation", float(d["solarradiation"])),
        "uv": trend_of("uv", float(d["uv"])),
        "rainratein": trend_of("rainratein", float(d["rainratein"])),
    }

    d["rain_mm"] = {
        "rainrate": round(inch_to_mm(d.get("rainratein", 0.0)), 2),  # mm/h
        "eventrain": round(inch_to_mm(d.get("eventrainin", 0.0)), 2),
        "hourlyrain": round(inch_to_mm(d.get("hourlyrainin", 0.0)), 2),
        "last24hrain": round(inch_to_mm(d.get("last24hrainin", 0.0)), 2),
        "dailyrain": round(inch_to_mm(d.get("dailyrainin", 0.0)), 2),
        "weeklyrain": round(inch_to_mm(d.get("weeklyrainin", 0.0)), 2),
        "monthlyrain": round(inch_to_mm(d.get("monthlyrainin", 0.0)), 2),
        "yearlyrain": round(inch_to_mm(d.get("yearlyrainin", 0.0)), 2),
    }

    return jsonify(d)

@app.route("/api/history")
def api_history():
    hours = request.args.get("hours", "24")
    try:
        hours = int(hours)
    except:
        hours = 24
    return jsonify(db_history(hours=hours))

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

        ts = int(time.time())

        tempf = safe_float(form.get("tempf", 0))
        humidity = safe_float(form.get("humidity", 0))
        wind_mph = safe_float(form.get("windspeedmph", 0))
        winddir = safe_float(form.get("winddir", 0))

        baromrelin = safe_float(form.get("baromrelin", 0))
        pressure_hpa = inhg_to_hpa(baromrelin)

        solarradiation = safe_float(form.get("solarradiation", 0))
        uv = safe_float(form.get("uv", 0))

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
            latest_data["uv"] = round(uv, 1)

            latest_data["rainratein"] = round(rainratein, 4)
            latest_data["eventrainin"] = round(eventrainin, 4)
            latest_data["hourlyrainin"] = round(hourlyrainin, 4)
            latest_data["last24hrainin"] = round(last24hrainin, 4)
            latest_data["dailyrainin"] = round(dailyrainin, 4)
            latest_data["weeklyrainin"] = round(weeklyrainin, 4)
            latest_data["monthlyrainin"] = round(monthlyrainin, 4)
            latest_data["yearlyrainin"] = round(yearlyrainin, 4)

            snap = dict(latest_data)

        db_insert_reading(snap, ts)
        db_upsert_rain_rollup(snap, ts)
        db_cleanup_if_needed(ts)

        return "OK", 200

    except Exception as e:
        logger.error(f"[GW1100] Error: {e}")
        return "ERROR", 500

# =========================
# RUN
# =========================
if __name__ == "__main__":
    logger.info(f"Web server listening on port {WEB_PORT}")
    logger.info(f"DB_PATH = {DB_PATH}")
    app.run(host="0.0.0.0", port=WEB_PORT, debug=False)