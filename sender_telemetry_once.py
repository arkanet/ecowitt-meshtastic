#!/usr/bin/env python3
import json
import logging
from logging.handlers import RotatingFileHandler

import requests
import meshtastic.serial_interface

from meshtastic_imports import load_meshtastic_protos

# =========================
# CONFIG
# =========================
SERVER_API = "http://127.0.0.1:8080/api/latest"
SERIAL_PORT = "/dev/ttyUSB0"
CHANNEL_INDEX = 1

LOGFILE = "./meshtastic_telemetry_send.log"

# Se True invia anche un messaggio testo per debug (con vento)
SEND_DEBUG_TEXT = False

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
def safe_float(x):
    try:
        return float(x)
    except Exception:
        return 0.0

def _set_first_field(obj, candidates, value):
    """
    Setta il primo campo disponibile in `candidates`.
    Ritorna True se è riuscito.
    """
    for name in candidates:
        if hasattr(obj, name):
            try:
                setattr(obj, name, value)
                return True
            except Exception:
                pass
    return False

def fetch_latest():
    r = requests.get(SERVER_API, timeout=5)
    r.raise_for_status()
    return r.json()

def pick_custom_port(portnums_pb2):
    """
    Usa PRIVATE_APP se esiste, altrimenti ricade su TEXT_MESSAGE_APP.
    """
    if hasattr(portnums_pb2.PortNum, "PRIVATE_APP"):
        return portnums_pb2.PortNum.PRIVATE_APP, "PRIVATE_APP"
    return portnums_pb2.PortNum.TEXT_MESSAGE_APP, "TEXT_MESSAGE_APP"

def try_set_env_fields(env_obj, d):
    """
    Prova a impostare meteo base + anemometro su un oggetto env-like.
    Tenta alias multipli perché i nomi cambiano tra versioni protobuf.
    Ritorna True se almeno un campo viene impostato con successo.
    """
    ok = False

    # temperatura
    ok = _set_first_field(
        env_obj,
        ["temperature", "temperature_c", "temp_c", "temp"],
        safe_float(d.get("temperature")),
    ) or ok

    # umidità
    ok = _set_first_field(
        env_obj,
        ["relative_humidity", "humidity", "humidity_pct"],
        safe_float(d.get("humidity")),
    ) or ok

    # pressione
    ok = _set_first_field(
        env_obj,
        ["barometric_pressure", "pressure_hpa", "pressure"],
        safe_float(d.get("pressure")),
    ) or ok

    # anemometro: velocità, direzione, raffica
    ok = _set_first_field(
        env_obj,
        ["wind_speed", "wind_speed_kmh", "windspeed", "windspeed_kmh"],
        safe_float(d.get("windspeed")),
    ) or ok
    ok = _set_first_field(
        env_obj,
        ["wind_direction", "wind_direction_deg", "winddir", "wind_dir"],
        safe_float(d.get("winddir")),
    ) or ok
    ok = _set_first_field(
        env_obj,
        ["wind_gust", "wind_gust_kmh", "gust", "gust_kmh"],
        safe_float(d.get("windgust")),
    ) or ok

    return ok

def build_telemetry_payload_if_possible(d, telemetry_pb2):
    """
    Ritorna bytes protobuf se riesce a trovare un submessage 'environment-like'.
    Se non possibile, ritorna None.
    """
    t = telemetry_pb2.Telemetry()

    # caso classico
    if hasattr(t, "environment"):
        try:
            if try_set_env_fields(t.environment, d):
                logger.info("Telemetry: using t.environment")
                return t.SerializeToString()
        except Exception as e:
            logger.warning(f"Telemetry: t.environment present but failed: {e}")

    # fallback: cerca altri submessage potenzialmente corretti
    for attr in dir(t):
        if attr.startswith("_"):
            continue
        name = attr.lower()
        if ("env" in name) or ("environment" in name) or ("sensor" in name):
            try:
                sub = getattr(t, attr)
                if try_set_env_fields(sub, d):
                    logger.info(f"Telemetry: using t.{attr}")
                    return t.SerializeToString()
            except Exception:
                pass

    logger.warning("Telemetry: no environment-like fields found; skipping TELEMETRY_APP send")
    return None

def build_custom_weather_payload(d):
    """
    Payload custom (JSON compatto) con meteo extra + anemometro:
      - rain rate (mm/h)
      - UV index
      - solar W/m²
      - T/H/P + ts
      - vento (velocità/direzione/raffica)
    """
    rainrate = safe_float((d.get("rain_mm") or {}).get("rainrate"))  # mm/h
    windspeed = safe_float(d.get("windspeed"))                       # km/h
    winddir = safe_float(d.get("winddir"))                           # deg
    windgust = safe_float(d.get("windgust"))                         # km/h

    payload = {
        "rg_mmph": rainrate,
        "uv": safe_float(d.get("uv")),
        "sr_wm2": safe_float(d.get("solarradiation")),

        # opzionali utili (non sono vento, e aiutano debug/coerenza)
        "t_c": safe_float(d.get("temperature")),
        "h_pct": safe_float(d.get("humidity")),
        "p_hpa": safe_float(d.get("pressure")),
        "ws_kmh": windspeed,
        "wd_deg": winddir,
        "wg_kmh": windgust,
        "ts": d.get("time", "--:--:--"),
    }

    # JSON compatto (meno byte in LoRa)
    return json.dumps(payload, separators=(",", ":")).encode("utf-8"), payload

def build_debug_text(payload_dict):
    # Debug testo con anemometro
    return (
        f"WX | R {payload_dict['rg_mmph']:.2f}mm/h "
        f"UV {payload_dict['uv']:.1f} "
        f"SR {payload_dict['sr_wm2']:.0f}W/m² "
        f"T {payload_dict['t_c']:.1f}C H {payload_dict['h_pct']:.0f}% P {payload_dict['p_hpa']:.0f}hPa "
        f"W {payload_dict['ws_kmh']:.1f}km/h {payload_dict['wd_deg']:.0f}deg G {payload_dict['wg_kmh']:.1f}km/h"
    )

def main():
    portnums_pb2, telemetry_pb2 = load_meshtastic_protos()

    d = fetch_latest()
    logger.info("Fetched latest OK")

    # 1) Telemetry standard (se possibile)
    telemetry_payload = build_telemetry_payload_if_possible(d, telemetry_pb2)

    # 2) Custom meteo extra (sempre) - include anche anemometro
    custom_bytes, custom_dict = build_custom_weather_payload(d)
    custom_port, custom_port_name = pick_custom_port(portnums_pb2)

    iface = meshtastic.serial_interface.SerialInterface(devPath=SERIAL_PORT)
    try:
        if telemetry_payload is not None and hasattr(portnums_pb2.PortNum, "TELEMETRY_APP"):
            iface.sendData(
                telemetry_payload,
                portNum=portnums_pb2.PortNum.TELEMETRY_APP,
                channelIndex=CHANNEL_INDEX,
                wantAck=False,
            )
            logger.info("Sent TELEMETRY_APP (protobuf)")
        else:
            logger.info("Skipped TELEMETRY_APP send (not supported by current protobufs)")

        iface.sendData(
            custom_bytes,
            portNum=custom_port,
            channelIndex=CHANNEL_INDEX,
            wantAck=False,
        )
        logger.info(f"Sent CUSTOM weather payload on {custom_port_name} (len={len(custom_bytes)} bytes)")

        if SEND_DEBUG_TEXT:
            iface.sendText(build_debug_text(custom_dict), channelIndex=CHANNEL_INDEX)
            logger.info("Sent debug text")
    finally:
        iface.close()

if __name__ == "__main__":
    try:
        main()
        logger.info("[OK] Done")
    except Exception as e:
        logger.error(f"[ERROR] {e}")
        raise
    
