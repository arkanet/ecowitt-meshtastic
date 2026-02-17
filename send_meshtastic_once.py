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

def deg_to_cardinal(deg):
    dirs = ["N","NE","E","SE","S","SW","W","NW"]
    try:
        return dirs[int((deg + 22.5) / 45) % 8]
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
    humidity = safe_float(d.get("humidity"))
    windspeed = safe_float(d.get("windspeed"))
    winddir = safe_float(d.get("winddir"))
    pressure = safe_float(d.get("pressure"))
    sunlight = safe_float(d.get("sunlight"))
    rain = safe_float(d.get("rain"))

    wind_cardinal = deg_to_cardinal(winddir)

    # 4 righe
    report = (
        f"Map: {location}\n"
        f"{t}  T: {temperature:.1f}°C  H: {humidity:.0f}%\n"
        f"W: {windspeed:.1f} km/h ({wind_cardinal})  R: {rain:.2f} mm/h\n"
        f"P: {pressure:.0f} hPa  SR: {sunlight:.0f} W/m²"
    )

    return report

# =========================
# SEND
# =========================
def send_meshtastic_text(report):
    iface = meshtastic.serial_interface.SerialInterface(devPath=SERIAL_PORT)
    iface.sendText(report, channelIndex=CHANNEL_INDEX)
    iface.close()

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    try:
        d = fetch_latest()
        logger.info(f"Dati ricevuti da server: {d}")

        report = build_report(d)
        logger.info(f"Report generato:\n{report}")

        send_meshtastic_text(report)
        logger.info(f"[OK] Messaggio inviato su Meshtastic CH={CHANNEL_INDEX}")

    except Exception as e:
        logger.error(f"[ERROR] Invio fallito: {e}")

