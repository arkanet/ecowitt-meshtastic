#!/usr/bin/env python3
import logging
from logging.handlers import RotatingFileHandler
import requests
import meshtastic.serial_interface

# =========================
# CONFIG
# =========================
SERVER_API = "http://127.0.0.1:8080/api/latest"
SERIAL_PORT = "/dev/ttyUSB0"
CHANNEL_INDEX = 0
LOGFILE = "./meshtastic_send.log"

# =========================
# LOGGING
# =========================
logger = logging.getLogger("meshtastic_sender")
logger.setLevel(logging.INFO)

handler = RotatingFileHandler(LOGFILE, maxBytes=1_000_000, backupCount=5)
formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

console = logging.StreamHandler()
console.setFormatter(formatter)
logger.addHandler(console)

# =========================
# UTILS
# =========================
def safe_float(val):
    try:
        return float(val)
    except:
        return 0.0

def safe_int(val):
    try:
        return int(round(float(val), 0))
    except:
        return 0

def deg_to_cardinal_16(deg):
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
            "S","SSW","SW","WSW","W","WNW","NW","NNW"]
    try:
        return dirs[int((float(deg) + 11.25) / 22.5) % 16]
    except:
        return "--"

# =========================
# FETCH DATA
# =========================
def fetch_latest():
    r = requests.get(SERVER_API, timeout=5)
    r.raise_for_status()
    return r.json()

# =========================
# BUILD TEXT REPORT
# =========================
def build_report(d):

    location = d.get("location", "UNKNOWN")
    t = d.get("time", "--:--:--")

    temperature = safe_float(d.get("temperature"))
    humidity = safe_int(d.get("humidity"))
    windspeed = safe_float(d.get("windspeed"))       # km/h
    winddir = safe_float(d.get("winddir"))           # deg
    pressure = safe_float(d.get("pressure"))         # hPa

    solarradiation = safe_float(d.get("solarradiation"))  # W/m²
    uv = safe_float(d.get("uv"))                           # UV index

    rain_mm = d.get("rain_mm") or {}
    rainrate = safe_float(rain_mm.get("rainrate"))         # mm/h (già convertito nel server)

    wind_cardinal = deg_to_cardinal_16(winddir)

    # 4 righe
    report = (
        f"Map: {location} {t}\n"
        f"T: {temperature:.1f}°C  H: {humidity:d}%  UV: {uv:.1f}\n"
        f"W: {windspeed:.1f} km/h ({wind_cardinal})  R: {rainrate:.2f} mm/h\n"
        f"P: {pressure:.0f} hPa  SR: {solarradiation:.0f} W/m²"
    )
    return report

# =========================
# SEND
# =========================
def send_meshtastic_text(report):
    iface = meshtastic.serial_interface.SerialInterface(devPath=SERIAL_PORT)
    try:
        iface.sendText(report, channelIndex=CHANNEL_INDEX)
    finally:
        iface.close()

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    try:
        d = fetch_latest()
        logger.info("Dati ricevuti da server OK")

        report = build_report(d)
        logger.info(f"Report generato:\n{report}")

        send_meshtastic_text(report)
        logger.info(f"[OK] Messaggio inviato su Meshtastic CH={CHANNEL_INDEX}")

    except Exception as e:
        logger.error(f"[ERROR] Invio fallito: {e}")
        raise